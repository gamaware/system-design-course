# Lab 14: Distributed Messaging

> For the lab overview, architecture diagram, and key concepts, see
> [README.md](README.md).

## Prerequisites

- **Docker Desktop** installed and running (includes Docker Compose)
- A terminal that supports bash (macOS Terminal, Linux shell, Git Bash
  on Windows, or WSL)
- `curl`, used by `setup.sh` to check the RabbitMQ management API
- A web browser for the RabbitMQ management console
- Free local ports **5672** (AMQP) and **15672** (console)

You do not need Python on your machine: every script runs inside the
`lab14-tools` container.

**Verify Docker:**

```bash
docker --version
docker compose version
```

## Quick Start

```bash
cd 14-distributed-messaging
chmod +x setup.sh cleanup.sh
./setup.sh
```

Then continue with **Task 1** below. You will use two terminals most of
the time: one to run commands, one to follow the worker logs.

## How to Read the Output

All outputs below come from a real run of this lab. Your order IDs match
because every command sets `--start-id`. Timings, message rates and the
way work splits between two workers will differ on your machine.

`rabbitmqctl` separates columns with tabs; the outputs here show them
aligned with spaces. RabbitMQ refreshes the queue counters it reports every 5 seconds. When a
step says "wait a few seconds" before `rabbitmqctl list_queues` or before
looking at the console, it is because of that refresh, not because the
messages are slow.

---

## Task 1: Publish Without Waiting

The producer is the checkout of an online store. It publishes one message
per order and moves on. A worker processes each order at its own pace,
200 ms per order. You will compare this with the synchronous version, in
which the checkout waits for every order to finish.

### Step 1.1: Run the setup script

```bash
./setup.sh
```

The script builds the Python image, starts RabbitMQ, one worker and the
tools container, waits for the broker, and declares every exchange, queue
and binding the lab uses.

Expected output (abbreviated):

```text
=== Lab 14: Distributed Messaging (RabbitMQ) ===
...
Waiting for RabbitMQ to be healthy...
  RabbitMQ AMQP:     ready (localhost:5672)
  RabbitMQ console:  ready (http://localhost:15672)

Declaring exchanges, queues and bindings...
Topology declared: exchanges, queues and bindings are in place.

Queues:
name                                                             type     durable  messages  consumers
orders.dlq                                                       classic  true     0         0
orders                                                           quorum   true     0         0
analytics                                                        classic  true     0         0
inventory                                                        classic  true     0         0
mx-orders                                                        classic  true     0         0
audit                                                            classic  true     0         0
payments                                                         classic  true     0         0
cancellations                                                    classic  true     0         0
scratch                                                          classic  true     0         0
notification                                                     classic  true     0         0

=== Environment ready ===
```

The `orders` queue may report `0` consumers here: the worker attaches a
second or two after the script prints the list.

### Step 1.2: Check the containers

```bash
docker compose ps --format 'table {{.Name}}\t{{.Image}}\t{{.Status}}'
```

Expected output:

```text
NAME             IMAGE                              STATUS
lab14-rabbitmq   rabbitmq:4.3.5-management-alpine   Up 7 seconds (healthy)
lab14-tools      lab14-app:local                    Up 1 second
lab14-worker-1   lab14-app:local                    Up 2 seconds
```

### Step 1.3: Open the management console

Open <http://localhost:15672> in your browser and log in with:

- **Username:** `lab14`
- **Password:** `lab14-pass`

Go to the **Queues and Streams** tab. You should see the ten queues from
Step 1.1. Click `orders`: it is a **quorum** queue with one consumer.
Keep this page open; you will watch it in every task.

### Step 1.4: Follow the worker logs

In a **second terminal**, in the same directory:

```bash
docker compose logs -f worker-1
```

Leave it running.

### Step 1.5: Publish 50 orders

Back in the first terminal:

```bash
docker exec lab14-tools python producer.py --count 50
```

Expected output:

```text
Published 50 message(s) to queue 'orders' in 0.002 s (30,657 msg/s, persistent, no confirms).
```

The producer finished in about 2 milliseconds. The work itself takes
50 x 200 ms = 10 seconds, and it is happening now in the worker. Wait 5
seconds and look at the queue:

```bash
docker exec lab14-rabbitmq rabbitmqctl -q list_queues name messages_ready messages_unacknowledged consumers
```

Expected output (the line for `orders`):

```text
orders  35  1  1
```

35 orders wait in the queue (**ready**), one is being processed
(**unacknowledged**), and one worker is attached. The second terminal
shows the worker draining the queue:

```text
lab14-worker-1  | [worker-1] waiting for orders (work=200 ms, prefetch=1)
lab14-worker-1  | [worker-1] processed ORD-1001 (redelivered=False, total=1)
lab14-worker-1  | [worker-1] processed ORD-1002 (redelivered=False, total=2)
...
lab14-worker-1  | [worker-1] processed ORD-1050 (redelivered=False, total=50)
```

In the console, the `orders` page shows the **Queued messages** chart
climbing and then falling back to zero.

### Step 1.6: Do the same work synchronously

```bash
docker exec lab14-tools python producer.py --count 20 --sync
```

Expected output:

```text
Processed 20 orders synchronously in 4.03 s: the caller waited for all of them.
```

With `--sync` the producer calls the same order logic the worker uses,
directly, the way a checkout would call an order service over HTTP. The
caller is blocked for the full 4 seconds. Nothing appears in the worker
logs because no message was published.

> **Question:** In Step 1.5 the producer returned in milliseconds, but the
> orders were not processed yet. What did the checkout actually guarantee
> to the customer when it returned?
>
> **Hint:** The producer only knows that it tried to publish the message:
> without publisher confirms (Task 6) it does not even know whether the
> broker received it. Think about what the customer sees ("order
> received") versus what has happened ("order fulfilled").
>
> **Question:** If the order logic were down for 30 seconds, what would
> happen to the synchronous checkout? And to the asynchronous one?
>
> **Hint:** Recall the "Sync vs Async" slide of the class: in one case the
> failure propagates to the caller, in the other it waits in a buffer.

---

## Task 2: Queue Versus Topic

A queue distributes work: each message goes to **one** consumer. An
exchange that fans out distributes events: **every** bound queue receives
its own copy. You will run both models and compare them side by side.

### Step 2.1: Start a second worker

```bash
docker compose up -d worker-2
```

`worker-2` belongs to the `scale` profile, so `setup.sh` did not start it.
Naming it on the command line starts it. In your second terminal, stop the
log command with `Ctrl+C` and follow both workers:

```bash
docker compose logs -f worker-1 worker-2
```

### Step 2.2: Competing consumers on one queue

```bash
docker exec lab14-tools python producer.py --count 6 --start-id 2001
```

Expected worker logs:

```text
[worker-2] processed ORD-2002 (redelivered=False, total=1)
[worker-2] processed ORD-2004 (redelivered=False, total=2)
[worker-2] processed ORD-2005 (redelivered=False, total=3)
[worker-1] processed ORD-2001 (redelivered=False, total=51)
[worker-1] processed ORD-2003 (redelivered=False, total=52)
[worker-1] processed ORD-2006 (redelivered=False, total=53)
```

Each order appears **once**, in one worker or the other. The workers
compete for the messages of one queue. With a prefetch of 1, the broker
hands the next message to whichever worker acknowledged its previous one,
so the split is roughly even but not a strict alternation.

### Step 2.3: Fanout: one event, a copy for every subscriber

The `order-events` exchange is a **fanout** exchange bound to three
queues: `notification`, `analytics` and `inventory`. Publish one event:

```bash
docker exec lab14-tools python producer.py --exchange order-events --count 1 --start-id 2101
```

Read each queue with the subscriber script, which prints what is waiting
and exits when the queue is empty:

```bash
for q in notification analytics inventory; do
    docker exec lab14-tools python subscriber.py --queue "$q"
done
```

Expected output:

```text
[notification] ORD-2101 key=order.placed.mx amount=17.5
[notification] consumed 1 message(s)
[analytics] ORD-2101 key=order.placed.mx amount=17.5
[analytics] consumed 1 message(s)
[inventory] ORD-2101 key=order.placed.mx amount=17.5
[inventory] consumed 1 message(s)
```

The producer sent **one** message, and three services received it. The
producer does not know these services exist: it knows only the exchange.

### Step 2.4: Topic: route by pattern

The `order-topic` exchange is a **topic** exchange. List its bindings:

```bash
docker exec lab14-rabbitmq rabbitmqctl -q list_bindings source_name destination_name routing_key \
    | grep -E '^source|^order-'
```

Expected output:

```text
source_name   destination_name  routing_key
order-events  analytics         analytics
order-events  inventory         inventory
order-events  notification      notification
order-topic   mx-orders         order.*.mx
order-topic   cancellations     order.cancelled.*
order-topic   audit             order.#
```

In a pattern, `*` matches exactly one word and `#` matches zero or more.
(A fanout exchange ignores the routing key of its bindings.) Publish four
events with different routing keys, then read the three queues:

```bash
i=2301
for key in order.placed.mx order.placed.us order.cancelled.mx order.cancelled.us; do
    docker exec lab14-tools python producer.py --exchange order-topic --routing-key "$key" \
        --count 1 --start-id "$i"
    i=$((i + 1))
done
for q in mx-orders cancellations audit; do
    docker exec lab14-tools python subscriber.py --queue "$q"
done
```

Expected output (subscriber part):

```text
[mx-orders] ORD-2301 key=order.placed.mx amount=77.5
[mx-orders] ORD-2303 key=order.cancelled.mx amount=92.5
[mx-orders] consumed 2 message(s)
[cancellations] ORD-2303 key=order.cancelled.mx amount=92.5
[cancellations] ORD-2304 key=order.cancelled.us amount=10.0
[cancellations] consumed 2 message(s)
[audit] ORD-2301 key=order.placed.mx amount=77.5
[audit] ORD-2302 key=order.placed.us amount=85.0
[audit] ORD-2303 key=order.cancelled.mx amount=92.5
[audit] ORD-2304 key=order.cancelled.us amount=10.0
[audit] consumed 4 message(s)
```

`ORD-2303` (`order.cancelled.mx`) matched two patterns and landed in two
queues. `ORD-2302` (`order.placed.us`) matched only `order.#`.

### Step 2.5: Both models at once

Publish four orders to the work queue and four events to the fanout
exchange:

```bash
docker exec lab14-tools python producer.py --count 4 --start-id 2401
docker exec lab14-tools python producer.py --exchange order-events --count 4 --start-id 2401
```

Wait a few seconds, then compare the worker logs with the fanout queues:

```bash
docker exec lab14-rabbitmq rabbitmqctl -q list_queues name messages_ready \
    | grep -E 'notification|analytics|inventory'
```

Expected output:

```text
analytics     4
inventory     4
notification  4
```

```text
lab14-worker-2  | [worker-2] processed ORD-2401 (redelivered=False, total=4)
lab14-worker-2  | [worker-2] processed ORD-2403 (redelivered=False, total=5)
lab14-worker-1  | [worker-1] processed ORD-2402 (redelivered=False, total=54)
lab14-worker-1  | [worker-1] processed ORD-2404 (redelivered=False, total=55)
```

The work queue **split** four orders between two workers (2 + 2). The
fanout exchange **copied** four events into three queues (4 + 4 + 4 = 12
messages stored). Empty the fanout queues before you continue:

```bash
for q in notification analytics inventory; do
    docker exec lab14-tools python subscriber.py --queue "$q" > /dev/null
done
```

> **Question:** The store adds a fraud detection service that must see
> every order. Should it consume from `orders` or get its own queue bound
> to `order-events`? What would go wrong with the other choice?
>
> **Hint:** If fraud detection joins the `orders` queue as a third
> competing consumer, which orders would it see?
>
> **Question:** How many changes to the producer does adding that service
> require?
>
> **Hint:** Count the lines you would change in `producer.py` versus the
> declarations you would add in `broker.py`.

---

## Task 3: The Consumer Goes Down

A queue is a buffer between services that fail independently. You will
stop every worker, keep publishing, restart the broker, and bring the
workers back.

### Step 3.1: Stop both workers

```bash
docker compose stop worker-1 worker-2
```

### Step 3.2: Publish while nobody is listening

```bash
docker exec lab14-tools python producer.py --count 30 --start-id 3001
```

The producer succeeds exactly as before: it does not depend on the
workers. Wait a few seconds and check the queue:

```bash
docker exec lab14-rabbitmq rabbitmqctl -q list_queues name messages_ready consumers | grep -E '^orders\s'
```

Expected output:

```text
orders  30  0
```

In the console, the `orders` row shows **Ready 30** and **Consumers 0**.

### Step 3.3: Restart the broker

Messages can be **persistent** (written to disk) or **transient** (kept in
memory). Publish 20 transient and 5 persistent messages to the `scratch`
queue, then wait a few seconds and look at both queues:

```bash
docker exec lab14-tools python producer.py --queue scratch --count 20 --transient --start-id 3101
docker exec lab14-tools python producer.py --queue scratch --count 5 --start-id 3201
docker exec lab14-rabbitmq rabbitmqctl -q list_queues name messages_ready | grep -E '^(orders|scratch)\s'
```

Expected output:

```text
orders   30
scratch  25
```

Restart RabbitMQ, wait until it accepts connections again, and list the
queues:

```bash
docker compose restart rabbitmq
until docker exec lab14-rabbitmq rabbitmq-diagnostics -q check_port_connectivity > /dev/null 2>&1; do
    sleep 2
done
docker exec lab14-rabbitmq rabbitmqctl -q list_queues name messages_ready | grep -E '^(orders|scratch)\s'
```

Expected output:

```text
orders   30
scratch  5
```

Every persistent message survived. The 20 transient messages were lost.
Both queues are durable; durability of the queue and persistence of the
message are separate decisions.

### Step 3.4: Kill a worker in the middle of a message

Start one worker and kill it two seconds later, while it is processing:

```bash
docker compose start worker-1
sleep 2
docker kill lab14-worker-1
docker compose logs --no-log-prefix worker-1 | tail -2
```

Expected output:

```text
[worker-1] processed ORD-3008 (redelivered=False, total=8)
[worker-1] processed ORD-3009 (redelivered=False, total=9)
```

In this run the worker was processing `ORD-3010` when it died, and it
had not acknowledged it. Your order ID may differ: it depends on the exact
moment of the kill. `docker kill` counts as a manual stop, so the
`restart: on-failure` policy does not bring the worker back.

### Step 3.5: Bring the workers back

```bash
docker compose start worker-1 worker-2
docker compose logs --no-log-prefix worker-1 worker-2 | grep 'redelivered=True'
```

Expected output:

```text
[worker-2] processed ORD-3010 (redelivered=True, total=1)
```

The broker gave the unacknowledged message to the next worker and marked
it `redelivered`. After a few seconds the queue is empty:

```bash
docker exec lab14-rabbitmq rabbitmqctl -q list_queues name messages_ready consumers | grep -E '^orders\s'
```

```text
orders  0  2
```

In the console, the **Queued messages** chart for `orders` shows the
plateau at 30 while the workers were down and the drop when they
returned.

Empty the `scratch` queue before you continue:

```bash
docker exec lab14-rabbitmq rabbitmqctl -q purge_queue scratch
```

> **Question:** In Step 3.4 the worker died after doing part of the work
> for `ORD-3010`. Another worker processed it from the beginning. Name
> one real side effect for which that is harmless, and one for which it is
> a problem.
>
> **Hint:** Compare "reserve stock for an order" with "send a confirmation
> email" or "charge the card". Task 5 explores the second kind.
>
> **Question:** Why does the worker acknowledge a message only *after*
> processing it? What would change if it acknowledged on arrival?
>
> **Hint:** Re-run Step 3.4 in your head with the acknowledgment moved to
> the first line of the handler. Where would `ORD-3010` be?

---

## Task 4: Retries and the Dead Letter Queue

Some messages fail every time: a malformed payload, a reference to a
product that does not exist. Retrying them forever blocks the worker and
hides the problem. The worker in this lab retries a failed message up to
three times, then rejects it, and the broker moves it to a **dead letter
queue** (DLQ).

Open `app/worker.py` and read `on_message` and `retry_later` before you
run the steps.

### Step 4.1: Publish one poison order among good ones

```bash
docker exec lab14-tools python producer.py --count 5 --poison 1 --start-id 4001
```

`ORD-4001` is poison. Wait about 5 seconds and read the worker logs:

```bash
docker compose logs worker-1 worker-2 | grep 'ORD-400'
```

Expected output:

```text
lab14-worker-2  | [worker-2] processed ORD-4002 (redelivered=False, total=12)
lab14-worker-2  | [worker-2] processed ORD-4003 (redelivered=False, total=13)
lab14-worker-2  | [worker-2] processed ORD-4004 (redelivered=False, total=14)
lab14-worker-2  | [worker-2] processed ORD-4005 (redelivered=False, total=15)
lab14-worker-2  | [worker-2] FAILED ORD-4001 attempt 2/3: ORD-4001 has an invalid payload -> retry in 1 s
lab14-worker-1  | [worker-1] FAILED ORD-4001 attempt 1/3: ORD-4001 has an invalid payload -> retry in 1 s
lab14-worker-1  | [worker-1] FAILED ORD-4001 attempt 3/3: ORD-4001 has an invalid payload -> dead letter queue
```

The four good orders went through while the poison one was being retried.
Each retry is a new copy of the message with an `attempt` header; the
attempts can land on different workers. The worker acknowledges the
original only after the broker confirms that it stored the copy (a
publisher confirm, measured in Task 6); if the copy is not confirmed, the
worker requeues the original instead. After the third failure the worker
calls `basic_reject(requeue=False)`.

### Step 4.2: Find the message in the DLQ

```bash
docker exec lab14-rabbitmq rabbitmqctl -q list_queues name messages_ready | grep -E '^orders'
```

Expected output:

```text
orders.dlq  1
orders      0
```

The `orders` queue declares `x-dead-letter-exchange: orders.dlx`. When a
consumer rejects a message without requeueing, the broker publishes it to
that exchange, which routes it to `orders.dlq`.

### Step 4.3: Inspect the dead message

```bash
docker exec lab14-tools python subscriber.py --queue orders.dlq --peek
```

Expected output:

```text
[orders.dlq] ORD-4001 key=orders amount=47.5
  dead-lettered from 'orders', reason: rejected, attempts: 3
[orders.dlq] peeked at 1 message(s)
```

`--peek` puts the message back. RabbitMQ added the `x-first-death-*`
headers that tell an operator where the message came from and why it
died. In the console, open `orders.dlq`, expand **Get messages** and
click **Get Message(s)** to see the same headers and the payload.

> **Question:** Why a dead letter queue instead of simply dropping the
> message after the third failure?
>
> **Hint:** Somebody has to fix the bug and decide what to do with the
> order. What do they need in order to do that?
>
> **Question:** `retry_later` publishes the copy, waits for the broker to
> confirm it, and then acknowledges the original. What happens if the
> worker dies after the confirm but before the acknowledgment?
>
> **Hint:** Count how many copies of the message exist afterwards. Keep
> the answer in mind for Task 5.
>
> **Question:** The worker sleeps one second before each retry, which
> blocks it for everyone else. How would you delay retries without
> blocking the worker?
>
> **Hint:** Look up RabbitMQ queues with a message TTL whose dead letter
> exchange points back to the main queue.

---

## Task 5: At-Least-Once Versus Exactly-Once

This is the most important task of the lab. The `payments` queue feeds a
consumer that charges each order in a ledger (an SQLite database). The
`payment.py` script can crash at the worst possible moments on purpose.
You will see three delivery behaviors:

| Behavior | How the consumer acknowledges | What can go wrong |
| --- | --- | --- |
| At-most-once | Automatically, when the broker sends the message | A crash loses the message |
| At-least-once | Manually, after doing the work | A crash causes a duplicate |
| Effectively-once | At-least-once plus an idempotent consumer | Nothing visible to the customer |

Read `app/payment.py` before you start. Notice where `charge()` commits
and where `basic_ack()` happens.

### Step 5.1: At-most-once: the broker forgets too early

```bash
docker exec lab14-tools python ledger.py --reset
docker exec lab14-tools python producer.py --queue payments --count 3 --start-id 5001
docker exec lab14-tools python payment.py --ack-mode auto --crash before-charge
```

Expected output:

```text
Ledger is empty.
Published 3 message(s) to queue 'payments' in 0.000 s (15,232 msg/s, persistent, no confirms).
payment consumer: ack-mode=auto crash=before-charge idempotent=False
  received ORD-5001 (message_id=ORD-5001, redelivered=False)
  CRASH before charging. The process dies now.
```

Now look at the queue and the ledger:

```bash
docker exec lab14-rabbitmq rabbitmqctl -q list_queues name messages_ready messages_unacknowledged \
    | grep -E '^payments'
docker exec lab14-tools python ledger.py
```

Expected output:

```text
payments                      0  0
order      charges   charged
0 order(s), 0 charge(s)
```

All three payments are gone, and nobody was charged. With automatic
acknowledgment the broker deletes a message the moment it sends it, and it
had already pushed all three to the consumer before the crash.

### Step 5.2: At-least-once: provoke a duplicate

Now the consumer acknowledges manually, after charging. It crashes after
the charge is committed and **before** the acknowledgment reaches the
broker, the way a container killed during a deploy would:

```bash
docker exec lab14-tools python ledger.py --reset
docker exec lab14-tools python producer.py --queue payments --count 3 --start-id 5101
docker exec lab14-tools python payment.py --crash after-charge
```

Expected output:

```text
payment consumer: ack-mode=manual crash=after-charge idempotent=False
  received ORD-5101 (message_id=ORD-5101, redelivered=False)
  charged ORD-5101 $17.50
  CRASH after charging, before the ack. The process dies now.
```

The broker still holds all three messages, because it never received an
acknowledgment for `ORD-5101`:

```bash
docker exec lab14-rabbitmq rabbitmqctl -q list_queues name messages_ready messages_unacknowledged \
    | grep -E '^payments'
```

```text
payments  3  0
```

Restart the consumer, as the orchestrator would, and check the ledger:

```bash
docker exec lab14-tools python payment.py
docker exec lab14-tools python ledger.py
```

Expected output:

```text
payment consumer: ack-mode=manual crash=none idempotent=False
  received ORD-5101 (message_id=ORD-5101, redelivered=True)
  charged ORD-5101 $17.50
  received ORD-5102 (message_id=ORD-5102, redelivered=False)
  charged ORD-5102 $25.00
  received ORD-5103 (message_id=ORD-5103, redelivered=False)
  charged ORD-5103 $32.50
payment consumer: queue drained, exiting
order      charges   charged
ORD-5101         2     35.00  <-- DOUBLE CHARGE
ORD-5102         1     25.00
ORD-5103         1     32.50
3 order(s), 4 charge(s)
```

Nothing was lost, but the customer of `ORD-5101` paid twice. The broker
did exactly what it promised: deliver every message **at least** once.
It cannot know that the work behind a missing acknowledgment already
happened.

### Step 5.3: Make the consumer idempotent

Run the same crash with `--idempotent`. The consumer now stores the
message ID in a `processed_messages` table **in the same transaction** as
the charge, and skips any message ID it has already stored:

```bash
docker exec lab14-tools python ledger.py --reset
docker exec lab14-tools python producer.py --queue payments --count 3 --start-id 5201
docker exec lab14-tools python payment.py --idempotent --crash after-charge
docker exec lab14-tools python payment.py --idempotent
docker exec lab14-tools python ledger.py
```

Expected output (consumer runs and ledger):

```text
payment consumer: ack-mode=manual crash=after-charge idempotent=True
  received ORD-5201 (message_id=ORD-5201, redelivered=False)
  charged ORD-5201 $47.50
  CRASH after charging, before the ack. The process dies now.
payment consumer: ack-mode=manual crash=none idempotent=True
  received ORD-5201 (message_id=ORD-5201, redelivered=True)
  duplicate ORD-5201: already charged, acknowledging without charging again
  received ORD-5202 (message_id=ORD-5202, redelivered=False)
  charged ORD-5202 $55.00
  received ORD-5203 (message_id=ORD-5203, redelivered=False)
  charged ORD-5203 $62.50
payment consumer: queue drained, exiting
order      charges   charged
ORD-5201         1     47.50
ORD-5202         1     55.00
ORD-5203         1     62.50
3 order(s), 3 charge(s)
```

The broker delivered `ORD-5201` twice, as before. The **effect** happened
once. This is what systems mean in practice by "exactly-once": at-least-once
delivery plus a consumer that makes duplicates harmless.

### Step 5.4: A duplicate the broker cannot see

Duplicates also come from producers. A producer that publishes, loses
its connection before the broker confirms, and publishes again creates two
messages. Simulate that retry by publishing `ORD-5202` a second time:

```bash
docker exec lab14-tools python producer.py --queue payments --count 1 --start-id 5202
docker exec lab14-tools python payment.py --idempotent
```

Expected output:

```text
payment consumer: ack-mode=manual crash=none idempotent=True
  received ORD-5202 (message_id=ORD-5202, redelivered=False)
  duplicate ORD-5202: already charged, acknowledging without charging again
payment consumer: queue drained, exiting
```

This time `redelivered=False`: for the broker it is a brand-new message.
Only the message ID, which the producer derives from the order ID,
reveals the duplicate. A consumer that relies on the `redelivered` flag
would charge twice.

> **Question:** Why must the processed-ID record and the charge commit in
> the **same** transaction? Describe what goes wrong if the consumer
> commits the charge first and records the ID in a second step.
>
> **Hint:** Put a crash between the two commits and replay Step 5.2.
>
> **Question:** The real payment provider is an external HTTP API, not a
> table in your database. How do you get the same protection?
>
> **Hint:** Look up "idempotency key" in the documentation of a payment
> API and compare it with the message ID.
>
> **Question:** If the producer generated a new random message ID on
> every publish, would Step 5.4 still detect the duplicate?
>
> **Hint:** Look at how `producer.py` sets `message_id`.

---

## Task 6: Measure Throughput and Queue Depth

Two numbers describe a queue in production: how many messages per second
go in and out, and how many are waiting. You will measure both.

### Step 6.1: Publish throughput and the cost of confirms

Stop the workers so they do not consume what you publish, then publish
as fast as possible with and without **publisher confirms** (the broker
acknowledges each message to the producer once it is safely stored):

```bash
docker compose stop worker-1 worker-2
docker exec lab14-tools python producer.py --count 20000
docker exec lab14-tools python producer.py --count 20000 --transient
docker exec lab14-tools python producer.py --count 2000 --confirm
docker exec lab14-tools python producer.py --count 2000 --queue scratch --confirm
```

Expected output (your numbers will differ):

```text
Published 20000 message(s) to queue 'orders' in 0.432 s (46,320 msg/s, persistent, no confirms).
Published 20000 message(s) to queue 'orders' in 0.432 s (46,284 msg/s, transient, no confirms).
Published 2000 message(s) to queue 'orders' in 1.962 s (1,019 msg/s, persistent, with publisher confirms).
Published 2000 message(s) to queue 'scratch' in 1.621 s (1,234 msg/s, persistent, with publisher confirms).
```

Without confirms the producer writes into a socket buffer and moves on: it
does not know whether the broker stored anything. With a confirm per
message the producer waits for the disk write (and, for the quorum queue
`orders`, for its replication log) on every publish: throughput drops by
more than an order of magnitude. In repeated runs the classic `scratch`
queue confirmed between about 1,200 and 2,500 messages per second.

Empty both queues:

```bash
docker exec lab14-rabbitmq rabbitmqctl -q purge_queue orders
docker exec lab14-rabbitmq rabbitmqctl -q purge_queue scratch
```

### Step 6.2: Start one fast worker

Recreate `worker-1` with 10 ms of work per message and one log line every
500 messages:

```bash
WORK_MS=10 LOG_EVERY=500 docker compose up -d worker-1
```

Wait about 10 seconds so the counters of the purge settle.

### Step 6.3: Watch the queue grow and drain

In the **second terminal**, start the monitor (it samples every 5
seconds, the pace at which RabbitMQ refreshes its statistics):

```bash
docker exec lab14-tools python monitor.py --queue orders --seconds 50
```

In the **first terminal**, publish 4,500 orders at 150 per second. The
command runs for 30 seconds:

```bash
docker exec lab14-tools python producer.py --count 4500 --rate 150
```

About 15 seconds after the producer started, start the second worker from
a **third terminal** in the same directory:

```bash
WORK_MS=10 LOG_EVERY=500 docker compose up -d worker-2
```

Expected monitor output:

```text
t(s)   ready unacked consumers publish/s   ack/s trend/s
   0       0       0         1         0       0
   5       0       0         1        37       0      +0
  10     330       1         1       150      76     +66
  15     704       1         1       150      74     +75
  20    1090       1         1       150      77     +77
  25    1206       2         2       150     150     +23
  30    1217       2         2       150     144      +2
  35    1237       2         2       113     150      +4
  40     573       2         2         0     147    -133
  45       0       0         2         0      63    -115
  50       0       0         2         0       0      +0
```

Read it in three phases:

1. **One worker (t = 10 to 20 s).** 150 messages per second arrive and one
   worker acknowledges about 76: the backlog grows by about 75 per second.
2. **Two workers (t = 25 to 35 s).** The consumers keep up with the
   arrival rate, so the backlog stops growing, but it does not shrink: the
   1,200 messages already waiting stay there.
3. **Producer stopped (t = 40 s onward).** With no arrivals, the two
   workers drain the backlog at about 150 per second.

### Step 6.4: Record your measurements

Fill in this table with your own numbers:

| Measurement | Your value |
| --- | --- |
| Publish rate without confirms (msg/s) | |
| Publish rate with confirms, quorum queue (msg/s) | |
| Ack rate of one worker at `WORK_MS=10` (msg/s) | |
| Backlog growth with one worker (msg/s) | |
| Peak queue depth (messages) | |
| Time to drain the backlog after the producer stopped (s) | |

Put the workers back to their default speed for any further experiment:

```bash
docker compose up -d worker-1 worker-2
```

> **Question:** At 76 messages per second per worker, how many workers do
> you need for a peak of 600 orders per second? What else would you
> watch before adding them?
>
> **Hint:** Divide, then think about what the workers call: a database,
> a payment API. A queue can absorb a peak, but the downstream services
> still have to process it.
>
> **Question:** In phase 2 the queue stopped growing but stayed at 1,200
> messages. What does that mean for the delay a new order experiences?
>
> **Hint:** A new message waits behind everything that is ahead of it.
> Divide the depth by the drain rate.
>
> **Question:** Which number would you alert on in production: the queue
> depth, the publish rate, or the age of the oldest message? Why?
>
> **Hint:** A deep queue that drains quickly may be fine; a shallow queue
> whose consumers stopped is not.

---

## Cleanup

```bash
./cleanup.sh
```

Expected output:

```text
=== Lab 14: Cleanup ===

Stopping and removing all lab resources...

Cleanup complete. All containers, volumes, the network, and the lab image removed.
```

Verify cleanup:

```bash
docker ps -a --filter name=lab14-
docker volume ls --filter name=lab14
```

Neither command should list anything: no `lab14-*` containers and no
`lab14_rabbitmq-data` or `lab14_ledger-data` volumes.
