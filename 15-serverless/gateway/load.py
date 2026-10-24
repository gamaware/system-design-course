"""Send concurrent invocations to a function through the gateway and summarize what happened.

  python load.py --requests 6 --sleep-ms 1000
  python load.py --requests 6 --sleep-ms 1000 --function lab15-work

All requests start at the same moment. Each line shows the HTTP status, the execution environment
(container) that ran the request, whether that environment was cold, and the latency.
"""

import argparse
import http.client
import json
import threading
import time


def call(index, args, barrier, results):
    payload = json.dumps({"sleep_ms": args.sleep_ms}).encode()
    barrier.wait()
    started = time.perf_counter()
    try:
        connection = http.client.HTTPConnection("localhost", 8080, timeout=60)
        connection.request("POST", f"/2015-03-31/functions/{args.function}/invocations", body=payload)
        response = connection.getresponse()
        body = response.read()
        connection.close()
    except OSError as exc:
        print(f"request {index + 1} failed: {exc}")
        results[index] = (0, "-", "error", (time.perf_counter() - started) * 1000)
        return
    elapsed = (time.perf_counter() - started) * 1000
    start = ""
    if response.getheader("X-Amz-Function-Error"):
        start = "error"  # the function ran and failed (a timeout, a crash): not a success
    elif response.status == 200:
        try:
            start = "cold" if json.loads(body)["environment"]["cold_start"] else "warm"
        except (ValueError, KeyError, TypeError):
            start = "error"
    results[index] = (response.status, response.getheader("X-Lab-Environment", "-"), start, elapsed)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--requests", type=int, default=6, help="how many requests start at once")
    parser.add_argument("--sleep-ms", type=int, default=1000, help="how long each invocation works")
    parser.add_argument("--function", default="lab15-work")
    args = parser.parse_args()

    results = [None] * args.requests
    barrier = threading.Barrier(args.requests)
    threads = [threading.Thread(target=call, args=(i, args, barrier, results)) for i in range(args.requests)]
    started = time.perf_counter()
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    wall = time.perf_counter() - started

    print(f"{'req':>3}  {'status':>6}  {'environment':<18} {'start':<5} {'ms':>7}")
    for index, (status, environment, start, elapsed) in enumerate(results, start=1):
        print(f"{index:>3}  {status:>6}  {environment:<18} {start:<5} {elapsed:>7.0f}")
    ok = [r for r in results if r[0] == 200 and r[2] in ("cold", "warm")]
    throttled = sum(1 for r in results if r[0] == 429)
    errors = len(results) - len(ok) - throttled
    environments = len({r[1] for r in results if r[1] != "-"})  # every environment that ran a request
    cold_starts = sum(1 for r in ok if r[2] == "cold")
    print(
        f"{len(ok)} succeeded, {throttled} throttled (429), {errors} failed, {environments} environment(s) used, "
        f"{cold_starts} cold start(s), wall time {wall:.2f} s"
    )


if __name__ == "__main__":
    main()
