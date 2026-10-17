"""Connection settings and the exchange and queue names shared by every script in the lab.

All topology lives in one place so that you can read, in a single file, how messages flow
from producers to consumers.
"""

import os
import time

import pika
from pika.exceptions import AMQPConnectionError

HOST = os.environ.get("RABBITMQ_HOST", "localhost")
USER = os.environ.get("RABBITMQ_USER", "lab14")
SECRET = os.environ.get("RABBITMQ_PASS", "lab14-pass")

# Work queue: one message goes to exactly one worker (Tasks 1, 3, 4 and 6).
ORDERS_QUEUE = "orders"
# A message the worker rejects is dead-lettered: the broker reroutes it to this exchange (Task 4).
DLX_EXCHANGE = "orders.dlx"
DLQ_QUEUE = "orders.dlq"

# Publish/subscribe: every bound queue receives its own copy (Task 2).
EVENTS_EXCHANGE = "order-events"
FANOUT_QUEUES = ("notification", "analytics", "inventory")

# Topic routing: each queue receives only the routing keys that match its pattern (Task 2).
TOPIC_EXCHANGE = "order-topic"
TOPIC_BINDINGS = {
    "mx-orders": "order.*.mx",
    "cancellations": "order.cancelled.*",
    "audit": "order.#",
}

# A classic queue for Task 3: it survives a broker restart, but transient messages in it do not.
SCRATCH_QUEUE = "scratch"

# Payments: the side effect that must not happen twice (Task 5).
PAYMENTS_QUEUE = "payments"


def connect(retries=30):
    """Open a blocking connection, retrying while the broker is still starting."""
    params = pika.ConnectionParameters(
        host=HOST,
        credentials=pika.PlainCredentials(USER, SECRET),
        heartbeat=30,
        # When the broker raises a memory or disk alarm it blocks publishers. Without a limit a
        # producer would wait forever; after 60 s pika closes the connection with an error instead.
        blocked_connection_timeout=60,
    )
    attempt = 1
    while True:
        try:
            return pika.BlockingConnection(params)
        except AMQPConnectionError:
            if attempt >= retries:
                raise
            print(f"RabbitMQ not reachable yet (attempt {attempt}/{retries}), retrying in 2 s", flush=True)
            attempt += 1
            time.sleep(2)


def declare_topology(channel):
    """Create every exchange, queue and binding. Safe to call many times: declarations are idempotent."""
    # Dead letter exchange and queue for messages that keep failing.
    channel.exchange_declare(DLX_EXCHANGE, exchange_type="fanout", durable=True)
    channel.queue_declare(DLQ_QUEUE, durable=True)
    channel.queue_bind(DLQ_QUEUE, DLX_EXCHANGE)

    # The work queue is a quorum queue: the replicated, always durable queue type of RabbitMQ 4.
    channel.queue_declare(
        ORDERS_QUEUE,
        durable=True,
        arguments={"x-queue-type": "quorum", "x-dead-letter-exchange": DLX_EXCHANGE},
    )

    channel.exchange_declare(EVENTS_EXCHANGE, exchange_type="fanout", durable=True)
    for queue in FANOUT_QUEUES:
        channel.queue_declare(queue, durable=True)
        channel.queue_bind(queue, EVENTS_EXCHANGE)

    channel.exchange_declare(TOPIC_EXCHANGE, exchange_type="topic", durable=True)
    for queue, pattern in TOPIC_BINDINGS.items():
        channel.queue_declare(queue, durable=True)
        channel.queue_bind(queue, TOPIC_EXCHANGE, routing_key=pattern)

    channel.queue_declare(SCRATCH_QUEUE, durable=True)
    channel.queue_declare(PAYMENTS_QUEUE, durable=True)
