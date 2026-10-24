"""Create, inspect and reset the lab15 table in DynamoDB Local.

  python table.py create          create the table if it does not exist (setup.sh runs this)
  python table.py scan [PREFIX]   print every item, or only those whose key starts with PREFIX
  python table.py reset           delete every item
"""

import argparse
import os
import sys
import time
from decimal import Decimal

import boto3
from botocore.exceptions import ClientError, EndpointConnectionError

TABLE_NAME = os.environ.get("TABLE_NAME", "lab15")
DYNAMODB = boto3.resource("dynamodb", endpoint_url=os.environ.get("DYNAMODB_ENDPOINT") or None)


def create():
    for attempt in range(1, 31):
        try:
            existing = DYNAMODB.meta.client.list_tables()["TableNames"]
            break
        except EndpointConnectionError:
            if attempt == 30:
                sys.exit("DynamoDB Local did not answer within 30 seconds")
            time.sleep(1)
    if TABLE_NAME in existing:
        print(f"Table {TABLE_NAME} already exists.")
        return
    table = DYNAMODB.create_table(
        TableName=TABLE_NAME,
        KeySchema=[{"AttributeName": "pk", "KeyType": "HASH"}],
        AttributeDefinitions=[{"AttributeName": "pk", "AttributeType": "S"}],
        BillingMode="PAY_PER_REQUEST",
    )
    table.wait_until_exists()
    print(f"Table {TABLE_NAME} created (partition key pk, on-demand capacity).")


def _items(prefix):
    table = DYNAMODB.Table(TABLE_NAME)
    response = table.scan()
    items = response["Items"]
    while "LastEvaluatedKey" in response:
        response = table.scan(ExclusiveStartKey=response["LastEvaluatedKey"])
        items.extend(response["Items"])
    return sorted((i for i in items if i["pk"].startswith(prefix)), key=lambda i: i["pk"])


def _show(value):
    if isinstance(value, Decimal):
        return str(int(value)) if value == value.to_integral_value() else str(value)
    return str(value)


def scan(prefix):
    items = _items(prefix)
    for item in items:
        fields = "  ".join(f"{k}={_show(v)}" for k, v in sorted(item.items()) if k != "pk")
        print(f"{item['pk']:<28} {fields}")
    print(f"{len(items)} item(s)")


def reset():
    table = DYNAMODB.Table(TABLE_NAME)
    items = _items("")
    with table.batch_writer() as batch:
        for item in items:
            batch.delete_item(Key={"pk": item["pk"]})
    print(f"Deleted {len(items)} item(s) from {TABLE_NAME}.")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("action", choices=["create", "scan", "reset"])
    parser.add_argument("prefix", nargs="?", default="", help="only for scan, for example PAYMENT#")
    args = parser.parse_args()
    try:
        if args.action == "create":
            create()
        elif args.action == "scan":
            scan(args.prefix)
        else:
            reset()
    except ClientError as exc:
        sys.exit(f"DynamoDB error: {exc}")


if __name__ == "__main__":
    main()
