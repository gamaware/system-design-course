"""lab15-processor: charges payments that arrive as a batch of Amazon SQS messages.

Each record body is a payment: {"order_id": "ORD-1001", "amount": 25.0}. The function charges it by
adding to the PAYMENT#<order_id> item in DynamoDB and reports the messages it could not process in
batchItemFailures, so that only those return to the queue (a partial batch response).

IDEMPOTENCY=on   record the order ID and the charge in one DynamoDB transaction, so a message
                 delivered twice charges once (the default)
IDEMPOTENCY=off  charge every delivery: a duplicate becomes a double charge

Two bodies fail on purpose: an amount that is not positive is rejected (the message is reported as
a failure and retried), and {"crash": true} raises an exception that fails the whole batch.
"""

import json
import os
import socket
import time
from decimal import Decimal, InvalidOperation

import boto3

_init_started = time.perf_counter()
DYNAMODB = boto3.client("dynamodb", endpoint_url=os.environ.get("DYNAMODB_ENDPOINT") or None)
TABLE_NAME = os.environ.get("TABLE_NAME", "lab15")
IDEMPOTENT = os.environ.get("IDEMPOTENCY", "on").lower() != "off"
INIT_MS = round((time.perf_counter() - _init_started) * 1000, 1)

_cold_start = True
_invocations = 0


class InvalidPaymentError(Exception):
    """The message can never succeed: retrying it will fail again."""


# Business limit that also keeps every amount inside the DynamoDB Number range.
MAX_AMOUNT = Decimal("1000000")


def _environment():
    global _cold_start, _invocations
    _invocations += 1
    info = {"id": socket.gethostname(), "cold_start": _cold_start, "invocations": _invocations}
    _cold_start = False
    return info


def _parse(body):
    try:
        payment = json.loads(body)
    except json.JSONDecodeError as exc:
        raise InvalidPaymentError("body is not JSON") from exc
    if not isinstance(payment, dict):
        raise InvalidPaymentError("body is not a JSON object")
    if payment.get("crash"):
        raise RuntimeError("simulated crash: the function fails before it answers")
    order_id = payment.get("order_id")
    if not isinstance(order_id, str) or not order_id.strip():
        raise InvalidPaymentError("order_id must be a non-empty string")
    try:
        amount = Decimal(str(payment["amount"]))
    except (KeyError, InvalidOperation) as exc:
        raise InvalidPaymentError("body needs order_id and a numeric amount") from exc
    if not amount.is_finite() or amount <= 0 or amount > MAX_AMOUNT:
        raise InvalidPaymentError(f"amount {amount} is not a positive number up to {MAX_AMOUNT}")
    return order_id, amount


def _charge_update(order_id, amount):
    return {
        "TableName": TABLE_NAME,
        "Key": {"pk": {"S": f"PAYMENT#{order_id}"}},
        "UpdateExpression": "ADD charges :one, charged_total :amount",
        "ExpressionAttributeValues": {":one": {"N": "1"}, ":amount": {"N": str(amount)}},
    }


def _charge(order_id, amount, message_id):
    """Charge the payment. Return "charged" or "duplicate"."""
    if not IDEMPOTENT:
        DYNAMODB.update_item(**_charge_update(order_id, amount))
        return "charged"
    # The idempotency record and the charge commit together or not at all. If the record already
    # exists, the condition fails, the transaction is cancelled and nothing is charged twice.
    try:
        DYNAMODB.transact_write_items(
            TransactItems=[
                {
                    "Put": {
                        "TableName": TABLE_NAME,
                        "Item": {"pk": {"S": f"IDEMPOTENCY#{order_id}"}, "message_id": {"S": message_id}},
                        "ConditionExpression": "attribute_not_exists(pk)",
                    }
                },
                {"Update": _charge_update(order_id, amount)},
            ]
        )
    except DYNAMODB.exceptions.TransactionCanceledException as exc:
        reasons = exc.response.get("CancellationReasons", [])
        if reasons and reasons[0].get("Code") == "ConditionalCheckFailed":
            return "duplicate"
        raise
    return "charged"


def handler(event, context):
    environment = _environment()
    failures = []
    for record in event.get("Records", []):
        message_id = record["messageId"]
        receive_count = record.get("attributes", {}).get("ApproximateReceiveCount", "1")
        log = {"message_id": message_id, "receives": int(receive_count)}
        try:
            order_id, amount = _parse(record["body"])
            log.update(order_id=order_id, outcome=_charge(order_id, amount, message_id))
        except InvalidPaymentError as exc:
            log.update(outcome="failed", reason=str(exc))
            failures.append({"itemIdentifier": message_id})
        print(json.dumps(log))
    print(
        json.dumps(
            {
                "function": context.function_name,
                "records": len(event.get("Records", [])),
                "failed": len(failures),
                "idempotency": "on" if IDEMPOTENT else "off",
                **environment,
            }
        )
    )
    return {"batchItemFailures": failures}
