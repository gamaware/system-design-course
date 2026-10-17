"""Order producer: publishes order messages and returns without waiting for anyone to process them.

Examples:
    python producer.py --count 20                          # 20 orders to the "orders" work queue
    python producer.py --count 20 --sync                   # the same orders, processed synchronously
    python producer.py --exchange order-events --count 1   # one event, fanned out to every subscriber
    python producer.py --exchange order-topic --routing-key order.placed.mx
    python producer.py --count 5 --poison 1                # one of the five orders always fails
    python producer.py --count 20000 --confirm             # wait for the broker to confirm each message
"""

import argparse
import json
import time

import broker
import pika
import worker


def make_order(number, poison=False):
    return {
        "order_id": f"ORD-{number}",
        "customer": f"customer-{number % 7}",
        "amount": round(10 + (number * 7.5) % 90, 2),
        "poison": poison,
    }


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--count", type=int, default=10, help="number of messages to publish")
    parser.add_argument("--start-id", type=int, default=1001, help="first order number (default 1001)")
    parser.add_argument("--queue", default=broker.ORDERS_QUEUE, help="queue to publish to (default exchange)")
    parser.add_argument("--exchange", default="", help="exchange to publish to instead of a queue")
    parser.add_argument("--routing-key", default="order.placed.mx", help="routing key when --exchange is set")
    parser.add_argument("--rate", type=float, default=0, help="messages per second (0 = as fast as possible)")
    parser.add_argument("--poison", type=int, default=0, help="how many of the messages are poison")
    parser.add_argument("--transient", action="store_true", help="publish non-persistent messages")
    parser.add_argument("--confirm", action="store_true", help="wait for a publisher confirm per message")
    parser.add_argument("--sync", action="store_true", help="process the orders inline instead of publishing")
    return parser.parse_args()


def run_sync(args):
    """What the checkout does without a queue: it calls the order logic and waits for every order."""
    start = time.perf_counter()
    for number in range(args.start_id, args.start_id + args.count):
        worker.process_order(make_order(number))
    elapsed = time.perf_counter() - start
    print(f"Processed {args.count} orders synchronously in {elapsed:.2f} s: the caller waited for all of them.")


def main():
    args = parse_args()
    if args.sync:
        run_sync(args)
        return

    connection = broker.connect()
    channel = connection.channel()
    if args.confirm:
        # Publisher confirms: basic_publish now blocks until the broker has stored the message.
        channel.confirm_delivery()

    exchange = args.exchange
    routing_key = args.routing_key if exchange else args.queue
    target = f"exchange '{exchange}' (routing key {routing_key})" if exchange else f"queue '{routing_key}'"
    delivery_mode = pika.DeliveryMode.Transient if args.transient else pika.DeliveryMode.Persistent
    interval = 1 / args.rate if args.rate > 0 else 0

    start = time.perf_counter()
    for index in range(args.count):
        number = args.start_id + index
        order = make_order(number, poison=index < args.poison)
        properties = pika.BasicProperties(
            content_type="application/json",
            delivery_mode=delivery_mode,
            # The message ID is the order ID: a producer that retries publishes the same ID again.
            message_id=order["order_id"],
        )
        channel.basic_publish(exchange, routing_key, json.dumps(order), properties, mandatory=args.confirm)
        if interval:
            next_send = start + (index + 1) * interval
            time.sleep(max(0.0, next_send - time.perf_counter()))
    elapsed = time.perf_counter() - start
    connection.close()

    rate = args.count / elapsed if elapsed > 0 else float("inf")
    mode = "transient" if args.transient else "persistent"
    mode += ", with publisher confirms" if args.confirm else ", no confirms"
    print(f"Published {args.count} message(s) to {target} in {elapsed:.3f} s ({rate:,.0f} msg/s, {mode}).")


if __name__ == "__main__":
    main()
