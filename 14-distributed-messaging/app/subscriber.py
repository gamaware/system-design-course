"""Read every message waiting in one queue, print it, and exit when the queue stays empty.

Examples:
    python subscriber.py --queue notification     # consume (acknowledge) what is waiting
    python subscriber.py --queue orders.dlq --peek  # look without removing anything
"""

import argparse
import json

import broker

IDLE_SECONDS = 2


def describe_death(headers):
    """Summarize the headers RabbitMQ adds when it dead-letters a message."""
    reason = headers.get("x-first-death-reason")
    if not reason:
        return ""
    source = headers.get("x-first-death-queue", "?")
    attempts = headers.get("attempt", 1)
    return f"  dead-lettered from '{source}', reason: {reason}, attempts: {attempts}"


def describe_order(body, routing_key):
    """Show the order ID and amount, or the raw body when the message is not a readable order."""
    try:
        order = json.loads(body)
        return f"{order['order_id']} key={routing_key} amount={order['amount']}"
    except (UnicodeDecodeError, json.JSONDecodeError, TypeError, KeyError):
        # The worker dead-letters unreadable messages, so the DLQ is exactly where they show up.
        return f"unreadable message key={routing_key} body={body!r}"


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--queue", required=True, help="queue to read")
    parser.add_argument("--peek", action="store_true", help="return the messages to the queue after reading")
    args = parser.parse_args()

    connection = broker.connect()
    channel = connection.channel()
    received = 0

    def show(method, properties, body):
        print(f"[{args.queue}] {describe_order(body, method.routing_key)}")
        death = describe_death(properties.headers or {})
        if death:
            print(death)

    if args.peek:
        # A peek never acknowledges. basic_get takes one message at a time with no prefetch limit (a
        # quorum queue caps a consumer with prefetch 0 at 2,000 messages), and a message this channel
        # holds unacknowledged is not handed out again, so each one is seen once.
        last_tag = None
        try:
            while True:
                method, properties, body = channel.basic_get(args.queue, auto_ack=False)
                if method is None:  # the queue has no more ready messages
                    break
                last_tag = method.delivery_tag
                received += 1
                show(method, properties, body)
        finally:
            # Give every message back explicitly. Closing the channel would also requeue them, but a
            # quorum queue counts that as a failed delivery, and repeated peeks would dead-letter them.
            if last_tag is not None:
                channel.basic_nack(delivery_tag=last_tag, multiple=True, requeue=True)
            connection.close()
    else:
        channel.basic_qos(prefetch_count=100)
        for method, properties, body in channel.consume(args.queue, inactivity_timeout=IDLE_SECONDS):
            if method is None:  # nothing arrived for IDLE_SECONDS: the queue is drained
                break
            received += 1
            show(method, properties, body)
            channel.basic_ack(method.delivery_tag)
        channel.cancel()
        connection.close()
    action = "peeked at" if args.peek else "consumed"
    print(f"[{args.queue}] {action} {received} message(s)")


if __name__ == "__main__":
    main()
