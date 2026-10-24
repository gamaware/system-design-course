"""lab15 gateway: the managed services around the functions, in about 400 lines of Python.

It plays three roles that AWS runs for you:

1. Lambda invoke API. POST /2015-03-31/functions/<name>/invocations runs a function synchronously.
   Each running container of a function is one execution environment, and an environment
   processes one request at a time. The gateway gives each request to an idle environment and
   answers 429 TooManyRequestsException when every environment is busy, the way Lambda throttles
   a function that reached its concurrency limit.
2. API Gateway (HTTP API). REST routes such as POST /orders become an event with payload format 2.0,
   and the statusCode, headers and body that the function returns become the HTTP response.
3. SQS event source mapping. POST /queues/orders adds messages to an in-memory queue. A poller sends
   them to lab15-processor in batches, deletes what succeeded, makes failed messages visible again
   after the visibility timeout, and moves a message to the dead letter queue after
   MAX_RECEIVE_COUNT failed receives.
"""

import base64
import contextlib
import hashlib
import http.client
import json
import os
import re
import socket
import threading
import time
import uuid
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qsl, urlsplit

RIE_PATH = "/2015-03-31/functions/function/invocations"
RIE_PORT = 8080
# Function name -> Compose service. Docker DNS returns one address per running container (replica).
FUNCTIONS = {
    "lab15-orders": "fn-orders",
    "lab15-processor": "fn-processor",
    "lab15-work": "fn-work",
}
# API Gateway routes: (method, path template, function).
ROUTES = [
    ("POST", "/orders", "lab15-orders"),
    ("GET", "/orders/{id}", "lab15-orders"),
    ("GET", "/visits", "lab15-orders"),
    ("GET", "/work", "lab15-work"),
]
QUEUE_BATCH_SIZE = int(os.environ.get("QUEUE_BATCH_SIZE", "10"))
QUEUE_VISIBILITY_TIMEOUT_S = float(os.environ.get("QUEUE_VISIBILITY_TIMEOUT_S", "12"))
QUEUE_MAX_RECEIVE_COUNT = int(os.environ.get("QUEUE_MAX_RECEIVE_COUNT", "3"))
QUEUE_ARN = "arn:aws:sqs:us-east-1:000000000000:lab15-orders"
# The longest a function may run (lab15-work allows 3 s) plus a margin for a slow cold start.
INVOKE_HTTP_TIMEOUT_S = 30


def log(message):
    print(f"[gateway] {message}", flush=True)


class EnvironmentPool:
    """Tracks which execution environments (containers) of each function are busy."""

    def __init__(self):
        self._lock = threading.Condition()
        self._busy = set()
        self._order = {}  # address -> first time seen, so warm environments are preferred
        self._names = {}

    def _addresses(self, function):
        try:
            infos = socket.getaddrinfo(FUNCTIONS[function], RIE_PORT, type=socket.SOCK_STREAM)
        except socket.gaierror:
            return []
        addresses = {info[4][0] for info in infos}
        for address in addresses:
            self._order.setdefault(address, time.monotonic())
        return sorted(addresses, key=self._order.get)

    def name(self, address):
        """Container name of an address, from reverse DNS (lab15-fn-work-2.lab15_default)."""
        if address not in self._names:
            try:
                self._names[address] = socket.gethostbyaddr(address)[0].split(".")[0]
            except OSError:
                self._names[address] = address
        return self._names[address]

    def acquire(self, function, wait):
        """Reserve an idle environment. Without wait, return None when all are busy (throttle)."""
        with self._lock:
            while True:
                addresses = self._addresses(function)
                if not addresses:
                    return None, 0
                for address in addresses:
                    if address not in self._busy:
                        self._busy.add(address)
                        return address, len(addresses)
                if not wait:
                    return None, len(addresses)
                self._lock.wait(timeout=0.5)

    def release(self, address):
        with self._lock:
            self._busy.discard(address)
            self._lock.notify_all()


POOL = EnvironmentPool()


class Invocation:
    def __init__(self, function):
        self.function = function
        self.status = 200
        self.payload = b""
        self.environment = ""
        # "" on success, "Unhandled" when the function failed, or why it never ran: NoEnvironment,
        # TooManyRequestsException or ConnectionError (failures of the platform, not of the function).
        self.error = ""
        self.duration_ms = 0.0


def invoke(function, payload, wait=False):
    """Run one synchronous invocation on an idle execution environment."""
    result = Invocation(function)
    address, environments = POOL.acquire(function, wait)
    if address is None:
        if environments == 0:
            result.status, result.error = 502, "NoEnvironment"
            result.payload = json.dumps(
                {"errorType": "NoEnvironment", "errorMessage": f"no running container for {function}"}
            ).encode()
        else:
            result.status, result.error = 429, "TooManyRequestsException"
            result.payload = json.dumps(
                {"errorType": "TooManyRequestsException", "errorMessage": "Rate Exceeded."}
            ).encode()
            log(f"throttled {function}: {environments} of {environments} environment(s) busy")
        return result

    result.environment = POOL.name(address)
    started = time.perf_counter()
    try:
        connection = http.client.HTTPConnection(address, RIE_PORT, timeout=INVOKE_HTTP_TIMEOUT_S)
        connection.request("POST", RIE_PATH, body=payload, headers={"Content-Type": "application/json"})
        response = connection.getresponse()
        result.payload = response.read()
        connection.close()
        rie_status = response.status
    except (OSError, http.client.HTTPException) as exc:
        # The gateway could not reach the environment: a platform failure, reported as 502.
        result.duration_ms = round((time.perf_counter() - started) * 1000, 1)
        result.status, result.error = 502, "ConnectionError"
        result.payload = json.dumps({"errorType": "ConnectionError", "errorMessage": str(exc)}).encode()
        log(f"invoke {function} on {result.environment}: cannot reach the environment: {exc}")
        return result
    finally:
        POOL.release(address)
    result.duration_ms = round((time.perf_counter() - started) * 1000, 1)

    # The emulator answers 200 even when the function failed or timed out; Lambda marks those
    # responses with the X-Amz-Function-Error header. Detect them the same way here.
    if rie_status != 200 or _is_function_error(result.payload):
        result.error = "Unhandled"
    log(f"invoke {function} on {result.environment}: {result.duration_ms} ms{' ERROR' if result.error else ''}")
    return result


def _is_function_error(payload):
    if payload.startswith(b"Task timed out"):
        return True
    try:
        body = json.loads(payload)
    except ValueError:
        return False
    return isinstance(body, dict) and "errorType" in body and "errorMessage" in body


def _match_route(method, path):
    for route_method, template, function in ROUTES:
        pattern = "^" + re.sub(r"\{(\w+)\}", r"(?P<\1>[^/]+)", template) + "$"
        match = re.match(pattern, path)
        if route_method == method and match:
            return f"{route_method} {template}", function, match.groupdict()
    return None, None, None


def _api_event(method, path, query, headers, body, route_key, path_parameters):
    """The event that API Gateway sends for an HTTP API route (payload format version 2.0)."""
    now = datetime.now(UTC)
    event = {
        "version": "2.0",
        "routeKey": route_key,
        "rawPath": path,
        "rawQueryString": query,
        "headers": {key.lower(): value for key, value in headers.items()},
        "requestContext": {
            "accountId": "000000000000",
            "apiId": "lab15-gateway",
            "domainName": headers.get("Host", "localhost"),
            "http": {
                "method": method,
                "path": path,
                "protocol": "HTTP/1.1",
                "sourceIp": headers.get("X-Forwarded-For", "127.0.0.1"),
                "userAgent": headers.get("User-Agent", ""),
            },
            "requestId": str(uuid.uuid4()),
            "routeKey": route_key,
            "stage": "$default",
            "time": now.strftime("%d/%b/%Y:%H:%M:%S +0000"),
            "timeEpoch": int(now.timestamp() * 1000),
        },
        "isBase64Encoded": False,
    }
    if query:
        event["queryStringParameters"] = dict(parse_qsl(query))
    if path_parameters:
        event["pathParameters"] = path_parameters
    if body:
        event["body"] = body.decode("utf-8", errors="replace")
    return event


class Queue:
    """An in-memory stand-in for an SQS standard queue with a redrive policy to a DLQ."""

    def __init__(self):
        self._lock = threading.Lock()
        self.messages = {}  # message ID -> message
        self.dead_letters = []
        self.deleted = 0

    def send(self, bodies):
        ids = []
        with self._lock:
            for body in bodies:
                message_id = str(uuid.uuid4())
                text = body if isinstance(body, str) else json.dumps(body)
                self.messages[message_id] = {
                    "messageId": message_id,
                    "body": text,
                    "receive_count": 0,
                    "visible_at": 0.0,
                    "sent_ms": int(time.time() * 1000),
                    "first_receive_ms": None,
                }
                ids.append(message_id)
        return ids

    def receive(self, limit):
        """Take up to limit visible messages and hide them for the visibility timeout."""
        now = time.monotonic()
        batch = []
        with self._lock:
            for message in self.messages.values():
                if message["visible_at"] <= now and len(batch) < limit:
                    message["receive_count"] += 1
                    message["visible_at"] = now + QUEUE_VISIBILITY_TIMEOUT_S
                    message["first_receive_ms"] = message["first_receive_ms"] or int(time.time() * 1000)
                    batch.append(dict(message))
        return batch

    def delete(self, message_id):
        with self._lock:
            if self.messages.pop(message_id, None) is not None:
                self.deleted += 1

    def fail(self, message_id):
        """Leave a failed message hidden until its visibility timeout ends, or dead-letter it."""
        with self._lock:
            message = self.messages.get(message_id)
            if message and message["receive_count"] >= QUEUE_MAX_RECEIVE_COUNT:
                del self.messages[message_id]
                self.dead_letters.append(
                    {"messageId": message_id, "body": message["body"], "receiveCount": message["receive_count"]}
                )
                return True
        return False

    def purge(self):
        with self._lock:
            removed = len(self.messages) + len(self.dead_letters)
            self.messages.clear()
            self.dead_letters.clear()
            self.deleted = 0
        return removed

    def stats(self):
        now = time.monotonic()
        with self._lock:
            visible = sum(1 for m in self.messages.values() if m["visible_at"] <= now)
            return {
                "queue": "lab15-orders",
                "visible": visible,
                "in_flight": len(self.messages) - visible,
                "deleted": self.deleted,
                "dead_letter_queue": list(self.dead_letters),
                "visibility_timeout_s": QUEUE_VISIBILITY_TIMEOUT_S,
                "max_receive_count": QUEUE_MAX_RECEIVE_COUNT,
            }


QUEUE = Queue()


def _sqs_record(message):
    return {
        "messageId": message["messageId"],
        "receiptHandle": base64.b64encode(f"{message['messageId']}:{message['receive_count']}".encode()).decode(),
        "body": message["body"],
        "attributes": {
            "ApproximateReceiveCount": str(message["receive_count"]),
            "SentTimestamp": str(message["sent_ms"]),
            "SenderId": "lab15-gateway",
            "ApproximateFirstReceiveTimestamp": str(message["first_receive_ms"]),
        },
        "messageAttributes": {},
        "md5OfBody": hashlib.md5(message["body"].encode(), usedforsecurity=False).hexdigest(),
        "eventSource": "aws:sqs",
        "eventSourceARN": QUEUE_ARN,
        "awsRegion": "us-east-1",
    }


def _reason(error):
    if not error:
        return ""
    return " (function error)" if error == "Unhandled" else f" ({error})"


def poll_queue():
    """The event source mapping: poll forever. One bad batch must never stop the poller."""
    while True:
        try:
            if not poll_once():
                time.sleep(0.5)
        except Exception as exc:  # noqa: BLE001 - log any failure and keep polling, like Lambda's pollers
            log(f"esm poller error, retrying in 1 s: {type(exc).__name__}: {exc}")
            time.sleep(1)


def poll_once():
    """Receive one batch, invoke the processor and settle each message. Return False if the queue was empty."""
    batch = QUEUE.receive(QUEUE_BATCH_SIZE)
    if not batch:
        return False
    event = {"Records": [_sqs_record(message) for message in batch]}
    result = invoke("lab15-processor", json.dumps(event).encode(), wait=True)
    ids = [message["messageId"] for message in batch]
    failed = set(ids)  # a failed invocation returns the whole batch to the queue
    if not result.error:
        try:
            reported = json.loads(result.payload).get("batchItemFailures", [])
            failed = {item["itemIdentifier"] for item in reported}
        except (ValueError, AttributeError, KeyError, TypeError):
            log("processor returned an invalid batch response: retrying the whole batch")
    receives = ",".join(str(message["receive_count"]) for message in batch)
    log(
        f"esm batch of {len(ids)} (receive counts {receives}): "
        f"{len(ids) - len(failed)} deleted, {len(failed)} failed{_reason(result.error)}"
    )
    for message_id in ids:
        if message_id not in failed:
            QUEUE.delete(message_id)
        elif QUEUE.fail(message_id):
            log(f"esm moved {message_id[:8]} to the dead letter queue after {QUEUE_MAX_RECEIVE_COUNT} receives")
    return True


class Handler(BaseHTTPRequestHandler):
    server_version = "lab15-gateway"

    def log_message(self, format, *args):  # noqa: A002 - signature defined by BaseHTTPRequestHandler
        pass  # every route logs its own line

    def _send(self, status, body, headers=None):
        if isinstance(body, bytes):
            # Indent JSON so that every field of a response is readable in the terminal.
            with contextlib.suppress(ValueError):
                body = json.loads(body)
        data = body if isinstance(body, bytes) else json.dumps(body, indent=2).encode()
        if not data.endswith(b"\n"):
            data += b"\n"  # so the shell prompt starts on a new line after curl
        headers = {"Content-Type": "application/json", **(headers or {})}
        self.send_response(status)
        self.send_header("Content-Length", str(len(data)))
        for key, value in headers.items():
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(data)

    def _body(self):
        length = int(self.headers.get("Content-Length") or 0)
        return self.rfile.read(length) if length else b""

    def _lab_headers(self, result):
        headers = {
            "X-Lab-Function": result.function,
            "X-Lab-Environment": result.environment or "-",
            "X-Lab-Duration-Ms": str(result.duration_ms),
        }
        if result.error == "Unhandled":
            headers["X-Amz-Function-Error"] = "Unhandled"
        return headers

    def do_GET(self):  # noqa: N802 - name defined by BaseHTTPRequestHandler
        self._dispatch("GET")

    def do_POST(self):  # noqa: N802 - name defined by BaseHTTPRequestHandler
        self._dispatch("POST")

    def do_DELETE(self):  # noqa: N802 - name defined by BaseHTTPRequestHandler
        self._dispatch("DELETE")

    def _dispatch(self, method):
        url = urlsplit(self.path)
        path = url.path.rstrip("/") or "/"
        body = self._body()

        if method == "GET" and path == "/health":
            return self._send(200, {"status": "ok"})
        if method == "GET" and path == "/":
            return self._send(200, {"routes": [f"{m} {p} -> {f}" for m, p, f in ROUTES], "functions": list(FUNCTIONS)})

        invoke_match = re.match(r"^/2015-03-31/functions/([\w-]+)/invocations$", path)
        if invoke_match and method == "POST":
            function = invoke_match.group(1)
            if function not in FUNCTIONS:
                return self._send(404, {"errorType": "ResourceNotFoundException", "errorMessage": function})
            result = invoke(function, body or b"{}")
            return self._send(result.status, result.payload, self._lab_headers(result))

        if path == "/queues/orders":
            if method == "GET":
                return self._send(200, QUEUE.stats())
            if method == "DELETE":
                removed = QUEUE.purge()
                log(f"queue purged: {removed} message(s) removed, dead letter queue included")
                return self._send(200, {"purged": removed})
            try:
                messages = json.loads(body or b"null")
            except ValueError:
                return self._send(400, {"error": "send a JSON object or a JSON array of objects"})
            messages = messages if isinstance(messages, list) else [messages]
            ids = QUEUE.send(messages)
            log(f"queue received {len(ids)} message(s)")
            return self._send(200, {"queued": len(ids), "message_ids": ids})

        route_key, function, path_parameters = _match_route(method, path)
        if function is None:
            return self._send(404, {"message": "Not Found"})
        event = _api_event(method, path, url.query, dict(self.headers), body, route_key, path_parameters)
        result = invoke(function, json.dumps(event).encode())
        headers = self._lab_headers(result)
        if result.error == "TooManyRequestsException":
            return self._send(429, {"message": "Too Many Requests"}, headers)
        if result.error in ("NoEnvironment", "ConnectionError"):
            return self._send(502, {"message": "Bad Gateway", "error": result.error}, headers)
        if result.error:
            log(f"api {route_key}: function error {result.payload[:200]!r}")
            return self._send(500, {"message": "Internal Server Error"}, headers)
        try:
            answer = json.loads(result.payload)
            if isinstance(answer, dict) and "statusCode" in answer:
                status = int(answer["statusCode"])
                headers.update(answer.get("headers") or {})
                return self._send(status, str(answer.get("body") or "").encode(), headers)
        except (ValueError, TypeError) as exc:
            log(f"api {route_key}: invalid function response ({exc}): {result.payload[:200]!r}")
            return self._send(502, {"message": "Bad Gateway", "error": "InvalidResponse"}, headers)
        # Payload format 2.0: a function that returns plain JSON gets a 200 with that JSON as body.
        return self._send(200, answer, headers)


def healthcheck():
    """Exit 0 when the gateway answers /health (the Docker Compose healthcheck)."""
    connection = http.client.HTTPConnection("localhost", 8080, timeout=2)
    connection.request("GET", "/health")
    raise SystemExit(0 if connection.getresponse().status == 200 else 1)


def main():
    threading.Thread(target=poll_queue, name="event-source-mapping", daemon=True).start()
    # All interfaces inside the container; Compose publishes the port on 127.0.0.1 only.
    server = ThreadingHTTPServer(("0.0.0.0", 8080), Handler)  # nosec B104
    log(
        f"listening on :8080 (queue: batch {QUEUE_BATCH_SIZE}, visibility {QUEUE_VISIBILITY_TIMEOUT_S:g} s, "
        f"max receives {QUEUE_MAX_RECEIVE_COUNT})"
    )
    server.serve_forever()


if __name__ == "__main__":
    main()
