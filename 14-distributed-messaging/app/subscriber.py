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


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--queue", required=True, help="queue to read")
    parser.add_argument("--peek", action="store_true", help="return the messages to the queue after reading")
    args = parser.parse_args()

    connection = broker.connect()
    channel = connection.channel()
    channel.basic_qos(prefetch_count=100)
    received = 0
    for method, properties, body in channel.consume(args.queue, inactivity_timeout=IDLE_SECONDS):
        if method is None:  # nothing arrived for IDLE_SECONDS: the queue is drained
            break
        received += 1
        order = json.loads(body)
        print(f"[{args.queue}] {order['order_id']} key={method.routing_key} amount={order['amount']}")
        death = describe_death(properties.headers or {})
        if death:
            print(death)
        if not args.peek:
            channel.basic_ack(method.delivery_tag)
    channel.cancel()  # with --peek, cancelling returns every unacknowledged message to the queue
    connection.close()
    action = "peeked at" if args.peek else "consumed"
    print(f"[{args.queue}] {action} {received} message(s)")


if __name__ == "__main__":
    main()
