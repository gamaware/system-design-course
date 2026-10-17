"""Read one key directly from every node and show whether the replicas agree.

Run it from the lab client container:

    docker exec lab05-client python /scripts/read_all.py color          # one read per node
    docker exec lab05-client python /scripts/read_all.py color --wait   # poll until all replicas agree
"""

import argparse
import http.client
import json
import time
import urllib.parse

NODES = ("node1", "node2", "node3")


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


def read(node, key):
    """Return a short description of what the node answered for the key."""
    try:
        status, _, raw = fetch(f"http://{node}:8080/kv/{key}", timeout=2)
    except (OSError, http.client.HTTPException) as error:
        return f"unreachable ({error})"
    body = json.loads(raw or b"{}")
    if 200 <= status < 300:
        return f"{body['value']} (version {body['version'][0]},{body['version'][1]})"
    return f"HTTP {status} {body.get('error', '')}".strip()


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("key")
    parser.add_argument("--wait", action="store_true", help="poll every 0.1 s until every node returns the same")
    parser.add_argument("--max-wait", type=float, default=30)
    args = parser.parse_args()

    start = time.monotonic()
    while True:
        answers = {node: read(node, args.key) for node in NODES}
        agree = len(set(answers.values())) == 1 and not next(iter(answers.values())).startswith(("HTTP", "unr"))
        if not args.wait or agree or time.monotonic() - start > args.max_wait:
            break
        time.sleep(0.1)

    for node, answer in answers.items():
        print(f"  {node}: {answer}")
    verdict = "replicas AGREE" if agree else "replicas DISAGREE"
    if args.wait:
        print(f"{verdict} after {time.monotonic() - start:.2f} s")
    else:
        print(verdict)


if __name__ == "__main__":
    main()
