"""Print queue depth and message rates read from the RabbitMQ management API.

    python monitor.py --queue orders --seconds 45

RabbitMQ refreshes queue statistics every 5 seconds, so the monitor samples at that pace.
Columns: ready = waiting in the queue, unacked = delivered but not yet acknowledged,
publish/s and ack/s = messages per second entering and leaving the queue, as the broker measures them,
trend/s = how fast the backlog grows (positive) or drains (negative) since the previous sample.
"""

import argparse
import base64
import http.client
import json
import os
import time
import urllib.parse

import broker

API_PORT = int(os.environ.get("RABBITMQ_API_PORT", "15672"))


def queue_stats(queue):
    path = "/api/queues/%2F/" + urllib.parse.quote(queue, safe="")
    token = base64.b64encode(f"{broker.USER}:{broker.SECRET}".encode()).decode()
    conn = http.client.HTTPConnection(broker.HOST, API_PORT, timeout=5)
    try:
        conn.request("GET", path, headers={"Authorization": f"Basic {token}"})
        response = conn.getresponse()
        if response.status != 200:
            raise RuntimeError(f"management API returned HTTP {response.status} for queue '{queue}'")
        return json.loads(response.read())
    finally:
        conn.close()


def rate(stats, key):
    return stats.get("message_stats", {}).get(f"{key}_details", {}).get("rate", 0.0)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--queue", default=broker.ORDERS_QUEUE)
    parser.add_argument("--seconds", type=int, default=45, help="how long to watch")
    parser.add_argument("--interval", type=int, default=5, help="seconds between samples")
    args = parser.parse_args()

    print(f"{'t(s)':>4} {'ready':>7} {'unacked':>7} {'consumers':>9} {'publish/s':>9} {'ack/s':>7} {'trend/s':>7}")
    previous = None
    for elapsed in range(0, args.seconds + 1, args.interval):
        stats = queue_stats(args.queue)
        ready = stats.get("messages_ready", 0)
        trend = "" if previous is None else f"{(ready - previous) / args.interval:+.0f}"
        previous = ready
        print(
            f"{elapsed:>4} {ready:>7} {stats.get('messages_unacknowledged', 0):>7} "
            f"{stats.get('consumers', 0):>9} {rate(stats, 'publish'):>9.0f} {rate(stats, 'ack'):>7.0f} {trend:>7}",
            flush=True,
        )
        if elapsed + args.interval <= args.seconds:
            time.sleep(args.interval)


if __name__ == "__main__":
    main()
