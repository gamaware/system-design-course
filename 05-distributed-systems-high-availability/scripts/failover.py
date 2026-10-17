"""Crash one node under load and measure detection (MTTD) and recovery (MTTR).

Two clients send requests at the same rate, one through the load balancer frontend WITH health
checks (port 18080) and one through the frontend WITHOUT them (port 18081). After a short baseline
the script crashes a node and records, on a single timeline:

- when the node process died and came back (Docker restart policy),
- when the node finished warming up and reported ready,
- when HAProxy marked it DOWN (detection) and UP again (recovery),
- which client requests failed.

Run it from the lab client container:

    docker exec lab05-client python /scripts/failover.py --node node2
"""

import argparse
import csv
import http.client
import io
import threading
import time
import urllib.parse
from collections import Counter

HAPROXY = "http://haproxy"
STATS_URL = f"{HAPROXY}:18090/stats;csv"


def fetch(url, timeout, method="GET"):
    """Send one HTTP request and return (status, headers, body). Only http:// URLs are accepted."""
    parts = urllib.parse.urlsplit(url)
    if parts.scheme != "http" or not parts.hostname:
        raise ValueError(f"only http:// URLs are supported: {url}")
    path = (parts.path or "/") + (f"?{parts.query}" if parts.query else "")
    connection = http.client.HTTPConnection(parts.hostname, parts.port or 80, timeout=timeout)
    try:
        connection.request(method, path)
        response = connection.getresponse()
        return response.status, response.headers, response.read()
    finally:
        connection.close()


def get_status(url, timeout):
    try:
        status, _, _ = fetch(url, timeout)
    except (OSError, http.client.HTTPException):
        return 0
    return status


def server_status(backend, server):
    """Status of one server as HAProxy sees it, read from the stats CSV (for example 'UP' or 'DOWN')."""
    try:
        status, _, body = fetch(STATS_URL, timeout=1)
    except (OSError, http.client.HTTPException):
        return "unknown"
    if not 200 <= status < 300:
        return "unknown"
    text = body.decode().lstrip("# ")
    for row in csv.DictReader(io.StringIO(text)):
        if row["pxname"] == backend and row["svname"] == server:
            return row["status"]
    return "unknown"


class Client(threading.Thread):
    """Sends GET requests at a fixed rate and remembers when each one failed."""

    def __init__(self, name, url, rate, origin, stop):
        super().__init__(daemon=True)
        self.label, self.url, self.period, self.origin, self.stop = name, url, 1 / rate, origin, stop
        self.total, self.failures = 0, []

    def run(self):
        while not self.stop.is_set():
            sent = time.monotonic()
            status = get_status(self.url, timeout=3)
            self.total += 1
            if not 200 <= status < 300:
                self.failures.append((sent - self.origin(), status))
            time.sleep(max(0.0, self.period - (time.monotonic() - sent)))


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--node", default="node2", choices=["node1", "node2", "node3"])
    parser.add_argument("--key", default="greeting")
    parser.add_argument("--rate", type=float, default=20, help="requests per second per client (default 20)")
    parser.add_argument("--baseline", type=float, default=2, help="seconds of traffic before the crash")
    parser.add_argument("--max-wait", type=float, default=60, help="give up after this many seconds")
    args = parser.parse_args()

    crash_at = [time.monotonic() + args.baseline]

    def since_crash():
        return time.monotonic() - crash_at[0]

    def crash_time():
        return crash_at[0]

    stop = threading.Event()
    clients = [
        Client("with checks (18080)", f"{HAPROXY}:18080/kv/{args.key}", args.rate, crash_time, stop),
        Client("no checks   (18081)", f"{HAPROXY}:18081/kv/{args.key}", args.rate, crash_time, stop),
    ]
    if server_status("be_checks", args.node) != "UP":
        raise SystemExit(f"{args.node} is not UP in HAProxy yet; wait a few seconds and run again.")

    for client in clients:
        client.start()
    print(f"Baseline: {args.baseline:.0f}s of traffic at {args.rate:.0f} req/s per client...")
    time.sleep(args.baseline)

    node_url = f"http://{args.node}:8080"
    crash_at[0] = time.monotonic()
    try:
        status, _, _ = fetch(f"{node_url}/admin/crash", timeout=1, method="POST")
    except (OSError, http.client.HTTPException) as error:
        stop.set()
        raise SystemExit(f"Could not send the crash request to {args.node}: {error}") from error
    if not 200 <= status < 300:
        stop.set()
        raise SystemExit(f"Could not send the crash request to {args.node}: HTTP Error {status}")
    events = {"crash": 0.0}

    def mark(name):
        if name not in events:
            events[name] = since_crash()

    while since_crash() < args.max_wait:
        live = get_status(f"{node_url}/health/live", timeout=0.2) == 200
        if not live:
            mark("process down")
        elif "process down" in events:
            mark("process alive")
            if get_status(f"{node_url}/health/ready", timeout=0.2) == 200:
                mark("node ready")
        status = server_status("be_checks", args.node)
        if status.startswith("DOWN"):
            mark("haproxy DOWN")
        elif status == "UP" and "haproxy DOWN" in events:
            mark("haproxy UP")
            break
        if "node ready" in events and "haproxy DOWN" not in events and since_crash() > events["node ready"] + 10:
            break  # the node recovered before the health checks noticed anything
        time.sleep(0.1)
    time.sleep(2)
    stop.set()
    for client in clients:
        client.join()

    labels = {
        "crash": f"crash sent to {args.node}",
        "process down": "process gone (connections refused)",
        "process alive": "process restarted by Docker (live)",
        "node ready": "warm-up finished (ready)",
        "haproxy DOWN": "HAProxy marks node DOWN",
        "haproxy UP": "HAProxy marks node UP",
    }
    print("\nTimeline (seconds after the crash)")
    for name, at in sorted(events.items(), key=lambda item: item[1]):
        print(f"  t={at:6.2f}s  {labels[name]}")

    print("\nMeasurements")
    mttd = events.get("haproxy DOWN")
    mttr = events.get("haproxy UP")
    print(
        f"  MTTD (crash -> HAProxy DOWN): {mttd:.2f} s"
        if mttd is not None
        else "  MTTD: never detected (the node came back before HAProxy noticed)"
    )
    print(
        f"  MTTR (crash -> HAProxy UP):   {mttr:.2f} s" if mttr is not None else "  MTTR: no DOWN/UP cycle in HAProxy"
    )

    print(f"\n  {'Client':<22}{'Requests':>9}{'Errors':>8}{'Availability':>14}   Error window, codes")
    for client in clients:
        errors = len(client.failures)
        availability = 100 * (client.total - errors) / max(1, client.total)
        if errors:
            first, last = client.failures[0][0], client.failures[-1][0]
            codes = Counter("conn-error" if code == 0 else str(code) for _, code in client.failures)
            window = f"t={first:.2f}s .. t={last:.2f}s, " + " ".join(f"{c}={n}" for c, n in sorted(codes.items()))
        else:
            window = "none"
        print(f"  {client.label:<22}{client.total:>9}{errors:>8}{availability:>13.1f}%   {window}")


if __name__ == "__main__":
    main()
