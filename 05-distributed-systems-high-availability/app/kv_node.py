"""Replicated key-value node for Lab 05.

Each node keeps the whole data set in memory and replicates every write to its peers. The peers are
reached through Toxiproxy, so the lab can slow down or cut any link between two nodes.

Two replication modes show the CAP trade-off during a network partition:

- ap: a write is applied locally and acknowledged at once; peers receive it in the background.
      Every node stays available, but replicas can disagree until the partition heals.
- cp: a write is acknowledged only after a majority (quorum) of nodes stored it, and a node serves
      reads only while it can reach a majority. The minority side of a partition stops answering.

Conflicts are resolved with last-writer-wins on a logical (Lamport) clock, never on wall-clock time.

Only the Python standard library is used, so the node runs on the stock python image.
"""

import http.client
import json
import os
import sys
import threading
import time
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

NODE_ID = os.environ.get("NODE_ID", "node1")
PORT = int(os.environ.get("PORT", "8080"))
MODE_DEFAULT = os.environ.get("MODE", "ap")
WARMUP_SECONDS = float(os.environ.get("WARMUP_SECONDS", "5"))
REPL_TIMEOUT = float(os.environ.get("REPL_TIMEOUT", "0.5"))
SYNC_INTERVAL = float(os.environ.get("SYNC_INTERVAL", "1"))

# PEERS="node2=http://toxiproxy:18012,node3=http://toxiproxy:18013"
PEERS = dict(item.split("=", 1) for item in os.environ.get("PEERS", "").split(",") if item)
CLUSTER_SIZE = len(PEERS) + 1
QUORUM = CLUSTER_SIZE // 2 + 1

STARTED_AT = time.monotonic()
POOL = ThreadPoolExecutor(max_workers=16)  # outgoing calls to peers


def log(message):
    stamp = time.strftime("%H:%M:%S")
    print(f"{stamp} [{NODE_ID}] {message}", flush=True)


def is_newer(record, current):
    """Last-writer-wins: True when record beats current (Lamport counter first, node id breaks ties)."""
    return current is None or tuple(record["version"]) > tuple(current["version"])


class Store:
    """In-memory data, Lamport clock, and the queue of writes each peer still has to receive."""

    def __init__(self):
        self.lock = threading.Lock()
        self.data = {}  # key -> {"value": str, "version": [counter, node]}
        self.clock = 0
        self.pending = {peer: {} for peer in PEERS}  # peer -> {key: record}
        self.mode = MODE_DEFAULT
        self.ready = False

    def new_record(self, value):
        with self.lock:
            self.clock += 1
            return {"value": value, "version": [self.clock, NODE_ID]}

    def apply(self, key, record):
        """Store a record if it is newer than the local one. Returns True when it was applied."""
        with self.lock:
            self.clock = max(self.clock, record["version"][0])
            if is_newer(record, self.data.get(key)):
                self.data[key] = record
                return True
            return False

    def enqueue(self, peers, key, record):
        """Queue a record for peers, keeping only the newest version per key.

        Two concurrent writes can reach this point in either order. Without the version check an
        older record queued second would replace the newer one, and the peers would converge on a
        value that this node already discarded.
        """
        with self.lock:
            for peer in peers:
                if is_newer(record, self.pending[peer].get(key)):
                    self.pending[peer][key] = record

    def snapshot(self):
        with self.lock:
            return {"clock": self.clock, "data": dict(self.data)}


STORE = Store()


class HTTPStatusError(http.client.HTTPException):
    """A peer answered with a status outside 2xx."""


# What a call to a peer can raise when the peer is down, slow, cut off or answers with an error.
PEER_ERRORS = (OSError, ValueError, http.client.HTTPException)


def http_json(method, url, payload=None, timeout=REPL_TIMEOUT):
    """Send one JSON request to a peer and return the decoded answer. Only http:// URLs are accepted."""
    parts = urllib.parse.urlsplit(url)
    if parts.scheme != "http" or not parts.hostname:
        raise ValueError(f"only http:// URLs are supported: {url}")
    body = json.dumps(payload).encode() if payload is not None else None
    connection = http.client.HTTPConnection(parts.hostname, parts.port or 80, timeout=timeout)
    try:
        connection.request(method, parts.path or "/", body=body, headers={"Content-Type": "application/json"})
        response = connection.getresponse()
        data = response.read()
    finally:
        connection.close()
    if not 200 <= response.status < 300:
        raise HTTPStatusError(f"{method} {url}: HTTP {response.status}")
    return json.loads(data or b"{}")


def send_to_peer(peer, records):
    """Push a batch of records to one peer. Returns True when the peer acknowledged them."""
    try:
        http_json("POST", f"{PEERS[peer]}/internal/replicate", {"records": records})
        return True
    except PEER_ERRORS:
        return False


def count_until_quorum(futures):
    """Wait for peer answers until a majority (counting this node) is reached or every peer answered.

    Returns the number of nodes that answered positively, this node included. Like a real quorum
    system, it does not wait for the slowest peer once a majority is known.
    """
    votes = 1
    for future in as_completed(futures):
        if future.result():
            votes += 1
        if votes >= QUORUM:
            break
    return votes


def visible_nodes():
    """CP read path: how many nodes (this one included) answer a liveness probe right now."""

    def probe(peer):
        try:
            http_json("GET", f"{PEERS[peer]}/health/live")
            return True
        except PEER_ERRORS:
            return False

    return count_until_quorum([POOL.submit(probe, peer) for peer in PEERS])


def replicate_sync(key, record):
    """CP write path: send to every peer in parallel and return as soon as a quorum acknowledged.

    Returns the number of acknowledgements, this node included. Peers that miss the write (now or
    after the reply was sent) are queued for the background sync, but only if the write committed.
    """
    batch = [{"key": key, "record": record}]
    futures = {POOL.submit(send_to_peer, peer, batch): peer for peer in PEERS}
    acks = count_until_quorum(futures)
    if acks >= QUORUM:
        for future, peer in futures.items():
            future.add_done_callback(lambda done, peer=peer: done.result() or STORE.enqueue([peer], key, record))
    return acks


def sync_loop():
    """Background anti-entropy: retry every write a peer has not acknowledged yet."""
    while True:
        time.sleep(SYNC_INTERVAL)
        for peer in PEERS:
            with STORE.lock:
                queued = dict(STORE.pending[peer])
            if not queued:
                continue
            records = [{"key": key, "record": record} for key, record in queued.items()]
            if send_to_peer(peer, records):
                with STORE.lock:
                    for key, record in queued.items():
                        if STORE.pending[peer].get(key) is record:
                            del STORE.pending[peer][key]
                log(f"delivered {len(records)} pending write(s) to {peer}")


def warm_up():
    """Simulate a node that must load state before it can serve: copy peers' data, then wait."""
    log(f"starting in {STORE.mode} mode, warming up for {WARMUP_SECONDS:.0f}s")
    for peer in PEERS:
        try:
            snap = http_json("GET", f"{PEERS[peer]}/internal/snapshot", timeout=1)
        except PEER_ERRORS:
            continue
        for key, record in snap.get("data", {}).items():
            STORE.apply(key, record)
    remaining = WARMUP_SECONDS - (time.monotonic() - STARTED_AT)
    if remaining > 0:
        time.sleep(remaining)
    STORE.ready = True
    log(f"ready with {len(STORE.data)} key(s)")


class Handler(BaseHTTPRequestHandler):
    server_version = "kv-node/1.0"

    def log_message(self, format, *args):  # noqa: A002 - signature defined by BaseHTTPRequestHandler
        return  # keep the container log for state changes only

    def reply(self, status, payload):
        body = json.dumps(payload).encode() + b"\n"
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Node", NODE_ID)
        self.end_headers()
        self.wfile.write(body)

    def read_body(self):
        length = int(self.headers.get("Content-Length") or 0)
        return self.rfile.read(length).decode() if length else ""

    def not_ready(self):
        self.reply(503, {"node": NODE_ID, "error": "warming up"})

    def do_GET(self):  # noqa: N802 - name required by BaseHTTPRequestHandler
        if self.path == "/health/live":
            uptime = round(time.monotonic() - STARTED_AT, 1)
            self.reply(200, {"node": NODE_ID, "status": "alive", "uptime_s": uptime})
        elif self.path == "/health/ready":
            status = 200 if STORE.ready else 503
            self.reply(status, {"node": NODE_ID, "status": "ready" if STORE.ready else "warming up"})
        elif self.path == "/internal/snapshot":
            self.reply(200, STORE.snapshot())
        elif self.path == "/admin/state":
            with STORE.lock:
                pending = {peer: len(queue) for peer, queue in STORE.pending.items()}
                self.reply(
                    200,
                    {
                        "node": NODE_ID,
                        "mode": STORE.mode,
                        "ready": STORE.ready,
                        "clock": STORE.clock,
                        "keys": len(STORE.data),
                        "pending": pending,
                    },
                )
        elif self.path.startswith("/kv/"):
            self.get_key(self.path[len("/kv/") :])
        else:
            self.reply(404, {"error": "not found"})

    def get_key(self, key):
        if not STORE.ready:
            return self.not_ready()
        if STORE.mode == "cp":
            visible = visible_nodes()
            if visible < QUORUM:
                return self.reply(
                    503, {"node": NODE_ID, "error": "no quorum", "visible_nodes": visible, "quorum": QUORUM}
                )
        record = STORE.data.get(key)
        if record is None:
            return self.reply(404, {"node": NODE_ID, "key": key, "error": "not found"})
        return self.reply(200, {"node": NODE_ID, "key": key, "value": record["value"], "version": record["version"]})

    def do_PUT(self):  # noqa: N802 - name required by BaseHTTPRequestHandler
        if not self.path.startswith("/kv/"):
            return self.reply(404, {"error": "not found"})
        if not STORE.ready:
            return self.not_ready()
        key = self.path[len("/kv/") :]
        record = STORE.new_record(self.read_body().strip())
        if STORE.mode == "cp":
            acks = replicate_sync(key, record)
            if acks < QUORUM:
                log(f"rejected write {key}: {acks}/{CLUSTER_SIZE} acks, quorum is {QUORUM}")
                return self.reply(
                    503, {"node": NODE_ID, "mode": "cp", "error": "no quorum", "acks": acks, "quorum": QUORUM}
                )
            STORE.apply(key, record)
            return self.reply(
                200,
                {
                    "node": NODE_ID,
                    "mode": "cp",
                    "key": key,
                    "version": record["version"],
                    "acks": acks,
                    "quorum": QUORUM,
                },
            )
        STORE.apply(key, record)
        STORE.enqueue(PEERS, key, record)
        return self.reply(
            200,
            {
                "node": NODE_ID,
                "mode": "ap",
                "key": key,
                "version": record["version"],
                "acks": 1,
                "replication": "async",
            },
        )

    def do_POST(self):  # noqa: N802 - name required by BaseHTTPRequestHandler
        if self.path == "/internal/replicate":
            payload = json.loads(self.read_body() or "{}")
            applied = sum(STORE.apply(item["key"], item["record"]) for item in payload.get("records", []))
            return self.reply(200, {"node": NODE_ID, "applied": applied})
        if self.path == "/admin/mode":
            mode = self.read_body().strip()
            if mode not in ("ap", "cp"):
                return self.reply(400, {"error": "mode must be ap or cp"})
            STORE.mode = mode
            log(f"mode set to {mode}")
            return self.reply(200, {"node": NODE_ID, "mode": mode})
        if self.path == "/admin/crash":
            log("crash requested: exiting with status 1")
            self.reply(200, {"node": NODE_ID, "status": "crashing"})
            threading.Timer(0.1, os._exit, args=(1,)).start()
            return None
        return self.reply(404, {"error": "not found"})


class Server(ThreadingHTTPServer):
    daemon_threads = True

    def handle_error(self, request, client_address):
        # A client that gives up early (a short health-check timeout) is normal here, not a bug.
        if isinstance(sys.exc_info()[1], (BrokenPipeError, ConnectionResetError)):
            return
        super().handle_error(request, client_address)


def main():
    if not PEERS:
        sys.exit("PEERS is empty: set PEERS=name=url,name=url")
    threading.Thread(target=warm_up, daemon=True).start()
    threading.Thread(target=sync_loop, daemon=True).start()
    log(f"listening on :{PORT}, peers={','.join(PEERS)}, quorum={QUORUM}/{CLUSTER_SIZE}")
    Server(("0.0.0.0", PORT), Handler).serve_forever()  # noqa: S104 - container listens on all interfaces


if __name__ == "__main__":
    main()
