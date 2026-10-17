"""Send a steady stream of GET requests and summarize latency and availability.

Run it from the lab client container:

    docker exec lab05-client python /scripts/probe.py http://haproxy:18080/kv/greeting --count 200
"""

import argparse
import http.client
import time
import urllib.parse
from collections import Counter


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


def percentile(values, pct):
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, round(pct / 100 * (len(ordered) - 1)))
    return ordered[index]


def request(url, timeout):
    """Return (status, latency_ms, node). Status 0 means the connection itself failed."""
    start = time.perf_counter()
    try:
        status, headers, _ = fetch(url, timeout)
        node = headers.get("X-Node", "-")
    except (OSError, http.client.HTTPException):
        status, node = 0, "-"
    return status, (time.perf_counter() - start) * 1000, node


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("url")
    parser.add_argument("--count", type=int, default=100, help="number of requests (default 100)")
    parser.add_argument("--interval", type=float, default=0.05, help="seconds between requests (default 0.05)")
    parser.add_argument("--timeout", type=float, default=5, help="client timeout in seconds (default 5)")
    args = parser.parse_args()

    statuses, nodes, latencies = Counter(), Counter(), []
    for _ in range(args.count):
        status, latency, node = request(args.url, args.timeout)
        statuses[status] += 1
        if 200 <= status < 300:
            nodes[node] += 1
            latencies.append(latency)
        time.sleep(args.interval)

    ok = len(latencies)
    errors = args.count - ok
    print(f"Requests: {args.count}  OK: {ok}  Errors: {errors}  Availability: {100 * ok / args.count:.1f}%")
    print(
        f"Latency of OK responses (ms): p50={percentile(latencies, 50):.1f}  p95={percentile(latencies, 95):.1f}"
        f"  p99={percentile(latencies, 99):.1f}  max={max(latencies, default=0):.1f}"
    )
    print("Responses by node: " + "  ".join(f"{name}={count}" for name, count in sorted(nodes.items())))
    labels = {0: "conn-error"}
    print("Status codes: " + "  ".join(f"{labels.get(code, code)}={n}" for code, n in sorted(statuses.items())))


if __name__ == "__main__":
    main()
