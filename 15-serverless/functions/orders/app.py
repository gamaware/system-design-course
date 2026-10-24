"""lab15-orders: the REST backend of the store, behind the HTTP gateway.

The gateway (or Amazon API Gateway, in AWS) turns each HTTP request into an event with the HTTP API
payload format 2.0 and expects a response with statusCode, headers and body. Routes:

  POST /orders        create an order          body: {"item": "book", "amount": 12.5}
  GET  /orders/{id}   read one order
  GET  /visits        count visits twice: in the memory of the environment and in DynamoDB
"""

import json
import os
import socket
import time
import uuid
from decimal import Decimal

import boto3

# Change this value in Task 3 to deploy a new version of this function only.
VERSION = "v1"

# INIT phase: runs once per execution environment and is reused by every warm invocation.
_init_started = time.perf_counter()
TABLE = boto3.resource("dynamodb", endpoint_url=os.environ.get("DYNAMODB_ENDPOINT") or None).Table(
    os.environ.get("TABLE_NAME", "lab15")
)
INIT_MS = round((time.perf_counter() - _init_started) * 1000, 1)

_cold_start = True
_invocations = 0
_visits_in_memory = 0


# Business limit that also keeps every amount inside the DynamoDB Number range.
MAX_AMOUNT = Decimal("1000000")


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


def _to_json(value):
    if isinstance(value, Decimal):
        return int(value) if value == value.to_integral_value() else float(value)
    raise TypeError(f"cannot serialize {type(value).__name__}")


def _response(status, payload, environment):
    payload = {**payload, "version": VERSION, "environment": environment}
    return {
        "statusCode": status,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(payload, default=_to_json),
    }


def _create_order(event, environment):
    try:
        body = json.loads(event.get("body") or "{}")
        item = str(body["item"])
        amount = Decimal(str(body["amount"]))
    except (ValueError, KeyError, TypeError, ArithmeticError):
        return _response(400, {"error": 'send a JSON body like {"item": "book", "amount": 12.5}'}, environment)
    if not amount.is_finite() or amount <= 0 or amount > MAX_AMOUNT:
        return _response(400, {"error": f"amount must be a positive number up to {MAX_AMOUNT}"}, environment)

    order = {
        "pk": f"ORDER#ORD-{uuid.uuid4().hex[:8]}",
        "item": item,
        "amount": amount,
        "status": "PLACED",
        "created_by": environment["id"],
    }
    TABLE.put_item(Item=order)
    order["order_id"] = order.pop("pk").removeprefix("ORDER#")
    return _response(201, {"order": order}, environment)


def _route(event):
    """Return the route key and path parameters of an HTTP API event (payload format 2.0).

    A route such as "GET /orders/{id}" arrives in routeKey. An API created with quick create has a
    single "$default" route that sends every request here, so the route comes from method and path.
    """
    route = event.get("routeKey", "")
    if route != "$default":
        return route, event.get("pathParameters") or {}
    method = event.get("requestContext", {}).get("http", {}).get("method", "")
    parts = event.get("rawPath", "").strip("/").split("/")
    if len(parts) == 2 and parts[0] == "orders":
        return f"{method} /orders/{{id}}", {"id": parts[1]}
    return f"{method} /{'/'.join(parts)}", {}


def _get_order(path_parameters, environment):
    order_id = path_parameters.get("id", "")
    order = TABLE.get_item(Key={"pk": f"ORDER#{order_id}"}).get("Item")
    if order is None:
        return _response(404, {"error": f"order {order_id} not found"}, environment)
    order["order_id"] = order.pop("pk").removeprefix("ORDER#")
    return _response(200, {"order": order}, environment)


def _count_visit(environment):
    global _visits_in_memory
    _visits_in_memory += 1
    stored = TABLE.update_item(
        Key={"pk": "COUNTER#visits"},
        UpdateExpression="ADD visits :one",
        ExpressionAttributeValues={":one": 1},
        ReturnValues="UPDATED_NEW",
    )["Attributes"]["visits"]
    return _response(200, {"visits_in_memory": _visits_in_memory, "visits_in_dynamodb": stored}, environment)


def handler(event, context):
    environment = _environment()
    route, path_parameters = _route(event)
    if route == "POST /orders":
        response = _create_order(event, environment)
    elif route == "GET /orders/{id}":
        response = _get_order(path_parameters, environment)
    elif route == "GET /visits":
        response = _count_visit(environment)
    else:
        response = _response(404, {"error": f"no route for {route!r}"}, environment)
    print(json.dumps({"function": context.function_name, "route": route, "status": response["statusCode"]}))
    return response
