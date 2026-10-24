"""lab15-work: a tunable function to measure cold starts, timeouts, memory and concurrency.

Every field of the event is optional. When the gateway invokes it from an HTTP route, the same
fields arrive as query string parameters (GET /work?sleep_ms=500).

  sleep_ms     wait this long, like a call to a slow API: it uses no CPU
  iterations   hash this many times: CPU-bound work, so its duration depends on the CPU share
  allocate_mb  hold this much memory during the invocation
  echo         return the event and the fields of the context object
"""

import hashlib
import json
import os
import socket
import time

import boto3

# Module-level code runs once per execution environment, during the INIT phase. A real function
# creates its SDK clients here so that every warm invocation reuses them; this one does the same,
# which is what makes its cold start measurable in Task 4 and Task 5.
_init_started = time.perf_counter()
DYNAMODB = boto3.client("dynamodb", endpoint_url=os.environ.get("DYNAMODB_ENDPOINT") or None)
INIT_MS = round((time.perf_counter() - _init_started) * 1000, 1)

# Memory of this execution environment. It survives between warm invocations and is lost when the
# environment is replaced: never keep data here that another invocation must see.
_cold_start = True
_invocations = 0


def _environment():
    global _cold_start, _invocations
    _invocations += 1
    info = {
        "id": socket.gethostname(),
        "cold_start": _cold_start,
        "invocations": _invocations,
        "init_ms": INIT_MS,
    }
    _cold_start = False
    return info


def _parameters(event):
    """Return the work parameters, whether the event came from an HTTP route or a direct call."""
    if "requestContext" in event:
        return event.get("queryStringParameters") or {}
    return event


def handler(event, context):
    started = time.perf_counter()
    params = _parameters(event)
    result = {"function": context.function_name, "environment": _environment()}

    if str(params.get("echo", "")).lower() in ("1", "true"):
        result["event"] = event
        result["context"] = {
            "function_name": context.function_name,
            "function_version": context.function_version,
            "memory_limit_in_mb": context.memory_limit_in_mb,
            "aws_request_id": context.aws_request_id,
            "log_group_name": context.log_group_name,
            "log_stream_name": context.log_stream_name,
            "remaining_time_in_millis": context.get_remaining_time_in_millis(),
        }

    sleep_ms = int(params.get("sleep_ms", 0))
    if sleep_ms:
        time.sleep(sleep_ms / 1000)

    iterations = int(params.get("iterations", 0))
    if iterations:
        cpu_started = time.perf_counter()
        digest = b"lab15"
        for _ in range(iterations):
            digest = hashlib.sha256(digest).digest()
        result["cpu_ms"] = round((time.perf_counter() - cpu_started) * 1000, 1)

    allocate_mb = int(params.get("allocate_mb", 0))
    if allocate_mb:
        # Multiplying writes every byte, so the memory is really used (a plain bytearray(n) is not).
        block = bytearray(b"\x01") * (allocate_mb * 1024 * 1024)
        result["allocated_mb"] = len(block) // (1024 * 1024)

    result["handler_ms"] = round((time.perf_counter() - started) * 1000, 1)
    result["remaining_time_in_millis"] = context.get_remaining_time_in_millis()
    # One structured log line per invocation, printed between the START and END lines.
    print(json.dumps({"function": context.function_name, **result["environment"], "handler_ms": result["handler_ms"]}))
    return result
