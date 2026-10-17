"""Order worker: a competing consumer on the "orders" work queue.

Each message is processed by exactly one worker. The worker acknowledges a message only after it
finishes the work, so a worker that dies mid-message gives the message back to the broker.

A message marked as poison always fails. The worker retries it up to MAX_ATTEMPTS times by
publishing a copy with an "attempt" header, then rejects it so the broker dead-letters it. The
channel uses publisher confirms: the worker acknowledges the original only after the broker
confirms that it stored the copy.

Environment variables:
    WORKER_NAME  name printed in the logs (default: worker)
    WORK_MS      simulated processing time per message, in milliseconds (default: 200)
    PREFETCH     unacknowledged messages the broker may push to this worker at once (default: 1)
    LOG_EVERY    print one line every N processed messages (default: 1)
"""

import json
import os
import time

import broker
import pika
from pika.exceptions import NackError, UnroutableError

WORKER_NAME = os.environ.get("WORKER_NAME", "worker")
WORK_MS = int(os.environ.get("WORK_MS", "200"))
PREFETCH = int(os.environ.get("PREFETCH", "1"))
LOG_EVERY = int(os.environ.get("LOG_EVERY", "1"))
MAX_ATTEMPTS = 3
RETRY_DELAY_S = 1.0


class PoisonMessageError(Exception):
    """Raised for an order that can never be processed, no matter how many times it is retried."""


def process_order(order, work_ms=WORK_MS):
    """The business logic: validate the order and simulate the work it takes (reserve stock, etc.)."""
    if order.get("poison"):
        raise PoisonMessageError(f"{order['order_id']} has an invalid payload")
    time.sleep(work_ms / 1000)


def parse_order(body):
    """Decode a message body. Returns the order, or None when it is not a JSON object with an order_id."""
    try:
        order = json.loads(body)
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    if not isinstance(order, dict) or "order_id" not in order:
        return None
    return order


def retry_later(channel, method, properties, body, attempt):
    """Publish a copy carrying the next attempt number and acknowledge the original once it is confirmed."""
    time.sleep(RETRY_DELAY_S)  # back off before retrying, so a bad message cannot spin the CPU
    headers = dict(properties.headers or {})
    headers["attempt"] = attempt + 1
    retry_properties = pika.BasicProperties(
        content_type=properties.content_type,
        delivery_mode=properties.delivery_mode,
        message_id=properties.message_id,
        headers=headers,
    )
    try:
        # With confirms on, basic_publish waits for the broker. mandatory=True turns "no queue took it"
        # into an error instead of a silent drop.
        channel.basic_publish("", broker.ORDERS_QUEUE, body, retry_properties, mandatory=True)
    except (NackError, UnroutableError) as error:
        # The copy is not stored: keep the original by giving it back, so the order cannot disappear.
        print(f"[{WORKER_NAME}] retry copy not confirmed ({error!r}) -> original requeued", flush=True)
        channel.basic_nack(delivery_tag=method.delivery_tag, requeue=True)
        return
    channel.basic_ack(delivery_tag=method.delivery_tag)


def main():
    connection = broker.connect()
    channel = connection.channel()
    broker.declare_topology(channel)
    channel.basic_qos(prefetch_count=PREFETCH)
    channel.confirm_delivery()  # publisher confirms for the retry copies
    processed = 0

    def on_message(ch, method, properties, body):
        nonlocal processed
        order = parse_order(body)
        if order is None:
            # Malformed JSON never becomes valid: retrying it would only restart the worker in a loop.
            print(f"[{WORKER_NAME}] REJECTED unreadable message {properties.message_id or '-'} "
                  "-> dead letter queue", flush=True)
            ch.basic_reject(delivery_tag=method.delivery_tag, requeue=False)
            return
        attempt = int((properties.headers or {}).get("attempt", 1))
        try:
            process_order(order)
        except PoisonMessageError as error:
            if attempt < MAX_ATTEMPTS:
                print(f"[{WORKER_NAME}] FAILED {order['order_id']} attempt {attempt}/{MAX_ATTEMPTS}: {error} "
                      f"-> retry in {RETRY_DELAY_S:.0f} s", flush=True)
                retry_later(ch, method, properties, body, attempt)
            else:
                print(f"[{WORKER_NAME}] FAILED {order['order_id']} attempt {attempt}/{MAX_ATTEMPTS}: {error} "
                      "-> dead letter queue", flush=True)
                # requeue=False: the broker routes the message to the queue's dead letter exchange.
                ch.basic_reject(delivery_tag=method.delivery_tag, requeue=False)
            return
        ch.basic_ack(delivery_tag=method.delivery_tag)
        processed += 1
        if processed % LOG_EVERY == 0:
            print(
                f"[{WORKER_NAME}] processed {order['order_id']} "
                f"(redelivered={method.redelivered}, total={processed})",
                flush=True,
            )

    channel.basic_consume(broker.ORDERS_QUEUE, on_message, auto_ack=False)
    print(f"[{WORKER_NAME}] waiting for orders (work={WORK_MS} ms, prefetch={PREFETCH})", flush=True)
    channel.start_consuming()


if __name__ == "__main__":
    main()
