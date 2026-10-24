# Lab 15: Serverless

> For the lab overview, architecture diagram, and key concepts, see
> [README.md](README.md).

## Prerequisites

- **Docker Desktop** installed and running (includes Docker Compose)
- A terminal that supports bash (macOS Terminal, Linux shell, Git Bash
  on Windows, or WSL)
- `curl`, used to call the gateway
- Free local port **8080**
- About 3 GB of free disk space for the images

You do not need Python, the AWS CLI or an AWS account on your machine:
the functions run in Lambda containers and the lab scripts run inside the
`lab15-gateway` container. Only the optional Task 9 uses AWS.

**Verify Docker:**

```bash
docker --version
docker compose version
```

## Quick Start

```bash
cd 15-serverless
chmod +x setup.sh cleanup.sh
./setup.sh
```

Then continue with **Task 1** below. A second terminal in the same
directory helps to follow the function logs with
`docker compose logs -f fn-orders fn-processor fn-work`.

## How to Read the Output

All outputs below come from a real run of this lab. Order IDs, request
IDs and message IDs are random, so yours differ. Timings depend on your
machine: compare your own cold and warm numbers with each other, not with
the ones printed here. The commands that read the container logs remove
the timestamp at the start of each line.

Each function container runs the **Lambda Runtime Interface Emulator**
(RIE), the same program that AWS ships in its base images for local
testing. It behaves like Lambda in most of what this lab measures, with
four differences that the tasks point out when they matter:

- The emulator prints the cold start as `INIT REPORT(durationMs: ...)`.
  Its `REPORT` line shows `Init Duration: 0.05 ms` and a `Max Memory
  Used` equal to the memory size; both numbers are placeholders.
- The emulator starts the timeout clock before the INIT phase, so a cold
  invocation has less time left than a warm one.
- One container is one execution environment. Lambda creates more
  environments by itself; here you start them with `--scale` in Task 7.
- The emulator accepts one request at a time and crashes if two arrive
  together. The gateway prevents that, so always call the functions
  through port 8080.

---

## Task 1: Deploy and Invoke a Function

In a serverless platform you do not deploy a server or an application.
You deploy a **function**: code plus its configuration (memory, timeout,
environment variables). This lab has three, each in its own directory and
its own container image.

### Step 1.1: Run the setup script

```bash
./setup.sh
```

The script builds the three function images and the gateway, starts
DynamoDB Local, the functions and the gateway, waits until every
container is healthy and the gateway answers, and creates the `lab15`
table.

Expected output (abbreviated):

```text
=== Lab 15: Serverless (AWS Lambda on Docker) ===
...
Waiting for the gateway to be healthy...
  Gateway: ready (http://localhost:8080)

Creating the DynamoDB table...
Table lab15 created (partition key pk, on-demand capacity).

Containers:
NAME                 IMAGE                         STATUS
lab15-dynamodb       amazon/dynamodb-local:3.3.2   Up 6 seconds
lab15-fn-orders      lab15-fn-orders:local         Up 6 seconds (healthy)
lab15-fn-processor   lab15-fn-processor:local      Up 6 seconds (healthy)
lab15-fn-work-1      lab15-fn-work:local           Up 5 seconds (healthy)
lab15-gateway        lab15-gateway:local           Up 6 seconds (healthy)

=== Environment ready ===
```

The first run downloads the AWS Lambda Python base image and DynamoDB
Local, which takes a few minutes.

### Step 1.2: One image per function

```bash
docker image ls 'lab15-fn-*' --format 'table {{.Repository}}\t{{.Tag}}\t{{.Size}}'
docker history lab15-fn-orders:local --format 'table {{.CreatedBy}}\t{{.Size}}' | head -5
```

Expected output:

```text
REPOSITORY           TAG       SIZE
lab15-fn-orders      local     779MB
lab15-fn-processor   local     779MB
lab15-fn-work        local     779MB
CREATED BY                                      SIZE
CMD ["app.handler"]                             0B
HEALTHCHECK {Test:[CMD bash -c exec 3<>/dev/…   0B
USER 10001                                      0B
COPY app.py /var/task/ # buildkit               20.5kB
```

Each image is the AWS Lambda Python base image plus **one layer** with the
code of that function. Open `functions/orders/Dockerfile`: `FROM` names
the base image, `COPY` adds the code, `USER` runs the function as an
unprivileged user, and `HEALTHCHECK` tells Docker when the emulator
accepts connections. `CMD ["app.handler"]` is the **handler** setting, the
same value you give Lambda in AWS: the module `app`, the function
`handler`. `USER`, `HEALTHCHECK` and `CMD` only change the metadata of the
image, so their layers are empty.
The 779 MB of runtime are shared by the three images, and the part you
deploy is about 20 KB.

**Record:** the size of the `COPY app.py` layer of `lab15-fn-orders`.

### Step 1.3: Invoke a function through the Lambda invoke API

The gateway serves the same path as the Lambda `Invoke` API of AWS:
`POST /2015-03-31/functions/<function name>/invocations`. The request
body is the **event**.

```bash
curl -s -X POST http://localhost:8080/2015-03-31/functions/lab15-work/invocations -d '{}'
```

Expected output:

```text
{
  "function": "lab15-work",
  "environment": {
    "id": "b21928c499eb",
    "cold_start": true,
    "invocations": 1,
    "init_ms": 285.4
  },
  "handler_ms": 0.0,
  "remaining_time_in_millis": 2154
}
```

The function reports which execution environment ran it (`id`, the
container ID), whether that environment was new (`cold_start`), and how
many invocations it has served. Run the command again: `cold_start` turns
`false` and `invocations` grows.

### Step 1.4: Call the REST API

The gateway also plays the role of **Amazon API Gateway**: the route
`POST /orders` invokes `lab15-orders`.

```bash
curl -s -i -X POST http://localhost:8080/orders -d '{"item": "book", "amount": 12.5}'
```

Expected output:

```text
HTTP/1.0 201 Created
Server: lab15-gateway Python/3.13.16
Content-Length: 292
Content-Type: application/json
X-Lab-Function: lab15-orders
X-Lab-Environment: lab15-fn-orders
X-Lab-Duration-Ms: 447.0

{
  "order": {
    "item": "book",
    "amount": 12.5,
    "status": "PLACED",
    "created_by": "lab15-fn-orders",
    "order_id": "ORD-8b524dc3"
  },
  "version": "v1",
  "environment": {
    "id": "lab15-fn-orders",
    "cold_start": true,
    "invocations": 1,
    "init_ms": 193.4
  }
}
```

Read the order back. Replace `<your-order-id>` with the `order_id` of
your own output, because every run creates a new one:

```bash
curl -s http://localhost:8080/orders/<your-order-id>
```

Expected output:

```text
{
  "order": {
    "item": "book",
    "amount": 12.5,
    "created_by": "lab15-fn-orders",
    "status": "PLACED",
    "order_id": "ORD-8b524dc3"
  },
  "version": "v1",
  "environment": {
    "id": "lab15-fn-orders",
    "cold_start": false,
    "invocations": 2,
    "init_ms": 193.4
  }
}
```

The `X-Lab-*` headers come from the gateway: which function and which
environment answered, and how long the invocation took. The first request
took about 450 ms because the environment was cold.

**Record:** your order ID and the `X-Lab-Duration-Ms` of the first
`POST /orders`.

> **Question:** The three functions share the same runtime and the same
> table. Why does the lab build three images instead of one image with
> three handlers?
>
> **Hint:** Think about what you change, test and roll back when a bug
> appears in the payment code only. Step 3.4 tries it.

---

## Task 2: The Event and the Context

Lambda calls the handler with two arguments: `handler(event, context)`.
The **event** is JSON whose shape depends on who triggered the function.
The **context** describes the invocation and the environment. Open
`functions/work/app.py` and find both.

### Step 2.1: A direct invocation

```bash
curl -s -X POST http://localhost:8080/2015-03-31/functions/lab15-work/invocations \
    -d '{"echo": true, "customer": "ana"}'
```

Expected output:

```text
{
  "function": "lab15-work",
  "environment": {
    "id": "b21928c499eb",
    "cold_start": false,
    "invocations": 2,
    "init_ms": 285.4
  },
  "event": {
    "echo": true,
    "customer": "ana"
  },
  "context": {
    "function_name": "lab15-work",
    "function_version": "$LATEST",
    "memory_limit_in_mb": "256",
    "aws_request_id": "cd261854-6017-4600-abb9-d378e28a6a29",
    "log_group_name": "/aws/lambda/Functions",
    "log_stream_name": "$LATEST",
    "remaining_time_in_millis": 3000
  },
  "handler_ms": 0.0,
  "remaining_time_in_millis": 3000
}
```

With a direct invocation, the event is exactly the JSON you sent. The
context carries a new `aws_request_id` per invocation, the configured
memory (`256`) and the time left before the timeout (`3000` ms of 3 s).

### Step 2.2: The same function behind an HTTP route

```bash
curl -s 'http://localhost:8080/work?echo=true&customer=ana'
```

Expected output (abbreviated):

```text
{
  "function": "lab15-work",
  ...
  "event": {
    "version": "2.0",
    "routeKey": "GET /work",
    "rawPath": "/work",
    "rawQueryString": "echo=true&customer=ana",
    "headers": {
      "host": "localhost:8080",
      "user-agent": "curl/8.7.1",
      "accept": "*/*"
    },
    "requestContext": {
      "accountId": "000000000000",
      "apiId": "lab15-gateway",
      "http": {
        "method": "GET",
        "path": "/work",
        ...
      },
      "requestId": "627f79f8-6a77-48b1-ac1d-7d8369527aaa",
      "routeKey": "GET /work",
      "stage": "$default",
      ...
    },
    "isBase64Encoded": false,
    "queryStringParameters": {
      "echo": "true",
      "customer": "ana"
    }
  },
  ...
}
```

Same function, same handler, a different event. This is the **payload
format version 2.0** that API Gateway HTTP APIs send to Lambda. Your
values became strings inside `queryStringParameters`, so the handler of
`lab15-work` checks for `requestContext` to know where to read them
(`_parameters` in `app.py`).

`lab15-work` returned a plain JSON object. API Gateway answers with
status 200 and that object as the body, which is what you see. Functions
that need another status code, like `lab15-orders`, return `statusCode`,
`headers` and `body` instead.

### Step 2.3: An SQS event

```bash
head -16 events/sqs-batch.json
```

Expected output:

```text
{
  "Records": [
    {
      "messageId": "6f1c1a52-8a39-4c1e-9a77-0c0f3c7e1001",
      "receiptHandle": "AQEBlab15receipthandle1001",
      "body": "{\"order_id\": \"ORD-1001\", \"amount\": 25.0}",
      "attributes": {
        "ApproximateReceiveCount": "1",
        "SentTimestamp": "1700000000000",
        "SenderId": "lab15-checkout",
        "ApproximateFirstReceiveTimestamp": "1700000000100"
      },
      "messageAttributes": {},
      "eventSource": "aws:sqs",
      "eventSourceARN": "arn:aws:sqs:us-east-1:000000000000:lab15-orders",
      "awsRegion": "us-east-1"
```

A queue delivers a **batch**: a `Records` array, each with its own
`messageId`, a `body` that is a JSON string, and a receive count. You
send this file to the payment function in Task 6.

### Step 2.4: The remaining time

```bash
curl -s -X POST http://localhost:8080/2015-03-31/functions/lab15-work/invocations \
    -d '{"echo": true, "sleep_ms": 1000}' | grep -o '"remaining_time_in_millis": [0-9]*'
```

Expected output:

```text
"remaining_time_in_millis": 2999
"remaining_time_in_millis": 1998
```

The first value was read when the handler started, the second after one
second of work. A function that processes a long list can check
`context.get_remaining_time_in_millis()` and stop cleanly before Lambda
stops it.

**Record:** the top-level keys of each of the three events (direct, HTTP
route, SQS) and the two remaining-time values.

> **Question:** The same handler code could serve both the direct
> invocation and the HTTP route. What is the risk of a handler that
> accepts "any" event shape?
>
> **Hint:** Look at the types: in Step 2.1 `echo` was a boolean, in
> Step 2.2 it was the string `"true"`.

---

## Task 3: Stateless Functions, State in DynamoDB

An execution environment keeps its memory between warm invocations, so a
global variable seems to work as storage. It stops working as soon as
Lambda replaces the environment, which it does after errors, after
deployments, after idle periods and whenever it scales.

### Step 3.1: Count visits in two places

`GET /visits` increments a global variable of `lab15-orders` and an item
in DynamoDB (`_count_visit` in `functions/orders/app.py`).

```bash
for i in 1 2 3; do curl -s http://localhost:8080/visits | grep -E '"visits_'; done
```

Expected output:

```text
  "visits_in_memory": 1,
  "visits_in_dynamodb": 1,
  "visits_in_memory": 2,
  "visits_in_dynamodb": 2,
  "visits_in_memory": 3,
  "visits_in_dynamodb": 3,
```

Both counters agree while the same environment serves every request.

### Step 3.2: Replace the execution environment

```bash
docker compose restart fn-orders
docker compose up -d --wait fn-orders
curl -s http://localhost:8080/visits
```

Expected output:

```text
{
  "visits_in_memory": 1,
  "visits_in_dynamodb": 4,
  "version": "v1",
  "environment": {
    "id": "lab15-fn-orders",
    "cold_start": true,
    "invocations": 1,
    "init_ms": 100.2
  }
}
```

`docker compose up -d --wait` returns when the healthcheck of the
container passes, that is, when the emulator accepts connections on port
8080. The check only opens a TCP connection and never calls the handler,
so the next request still finds a cold environment.

The restart started a new Python process, the way Lambda starts a new
environment. The counter in memory went back to 1. The counter in
DynamoDB continued at 4.

### Step 3.3: Look at the table

```bash
docker exec lab15-gateway python table.py scan
```

Expected output:

```text
COUNTER#visits               visits=4
ORDER#ORD-8b524dc3           amount=12.5  created_by=lab15-fn-orders  item=book  status=PLACED
2 item(s)
```

The table uses one partition key, `pk`, and a prefix per kind of item:
`ORDER#`, `COUNTER#`, and in Task 6 `PAYMENT#` and `IDEMPOTENCY#`.

### Step 3.4: Deploy a new version of one function

Change the `VERSION` constant of `lab15-orders` and redeploy only that
function. First note the state of `lab15-work`:

```bash
curl -s -X POST http://localhost:8080/2015-03-31/functions/lab15-work/invocations -d '{}' \
    | grep -E '"(id|cold_start|invocations)"'
```

```text
    "id": "b21928c499eb",
    "cold_start": false,
    "invocations": 5,
```

Now deploy `v2` of `lab15-orders`:

```bash
sed -i.bak 's/^VERSION = "v1"/VERSION = "v2"/' functions/orders/app.py && rm functions/orders/app.py.bak
docker compose up -d --build --wait fn-orders
curl -s http://localhost:8080/visits
curl -s -X POST http://localhost:8080/2015-03-31/functions/lab15-work/invocations -d '{}' \
    | grep -E '"(id|cold_start|invocations)"'
```

Expected output (Compose lines abbreviated):

```text
 Container lab15-fn-orders Recreate
 Container lab15-fn-orders Recreated
 Container lab15-fn-orders Started
 Container lab15-fn-orders Healthy
{
  "visits_in_memory": 1,
  "visits_in_dynamodb": 5,
  "version": "v2",
  "environment": {
    "id": "lab15-fn-orders",
    "cold_start": true,
    "invocations": 1,
    "init_ms": 113.4
  }
}
    "id": "b21928c499eb",
    "cold_start": false,
    "invocations": 6,
```

Only `lab15-fn-orders` was rebuilt and recreated. It answers with `v2`
from a cold environment, and the data in DynamoDB is intact. The
environment of `lab15-work` stayed warm: same ID, invocation 6. In AWS,
`aws lambda update-function-code` does the same for one function.

Put `v1` back:

```bash
git checkout -- functions/orders/app.py
docker compose up -d --build --wait fn-orders
```

**Record:** `visits_in_memory` and `visits_in_dynamodb` after the restart
of Step 3.2, and the `invocations` value of `lab15-work` before and after
the deployment.

> **Question:** A developer caches the shopping cart of each user in a
> global dictionary of the function "to avoid a database call". Describe
> two ways in which a user loses items from the cart.
>
> **Hint:** One appears in Step 3.2. The other appears in Task 7, when
> two environments of the same function serve the same user.

---

## Task 4: Cold Start Versus Warm Start

A **cold start** happens when Lambda creates an execution environment: it
downloads the code, starts the runtime and runs the module-level code of
your function (the **INIT** phase) before the first handler call. Every
later request to that environment is a **warm start** and skips all of
that.

### Step 4.1: Force a cold start and time five requests

```bash
docker compose restart fn-orders
docker compose up -d --wait fn-orders
for i in 1 2 3 4 5; do
    curl -s -o /dev/null -w '%{http_code} %{time_total}\n' http://localhost:8080/visits
done
```

Expected output (HTTP status and seconds, measured by `curl`; Compose
lines omitted). Every line must start with `200`: any other status means
that the request failed, and its time says nothing about cold starts.

```text
200 0.382684
200 0.013208
200 0.010503
200 0.009695
200 0.009878
```

### Step 4.2: Read the log lines of the runtime

```bash
docker compose logs --no-log-prefix fn-orders | grep -E 'INIT REPORT|^REPORT' | tail -6 \
    | sed -E 's/^[0-9]+ [A-Z][a-z]+ [0-9]+ [0-9:,]+ //' | sed -E 's/RequestId: [0-9a-f-]+[[:space:]]+//'
```

Expected output:

```text
[INFO] (rapid) INIT REPORT(durationMs: 367.478000)
REPORT Init Duration: 0.02 ms Duration: 377.36 ms Billed Duration: 378 ms Memory Size: 512 MB Max Memory Used: 512 MB
REPORT Duration: 7.50 ms Billed Duration: 8 ms Memory Size: 512 MB Max Memory Used: 512 MB
REPORT Duration: 5.96 ms Billed Duration: 6 ms Memory Size: 512 MB Max Memory Used: 512 MB
REPORT Duration: 5.84 ms Billed Duration: 6 ms Memory Size: 512 MB Max Memory Used: 512 MB
REPORT Duration: 6.68 ms Billed Duration: 7 ms Memory Size: 512 MB Max Memory Used: 512 MB
```

Lambda writes one `REPORT` line per invocation to CloudWatch Logs. The
emulator writes it to the container log. Read it with the emulator's
differences in mind:

- `INIT REPORT(durationMs: 367.478000)` is the cold start: 367 ms of INIT.
- The first `REPORT` shows `Duration: 377.36 ms` because the emulator
  adds INIT to the first invocation. Its `Init Duration: 0.03 ms` is a
  placeholder.
- The warm invocations took 6 to 8 ms.

The `sed` commands remove the timestamps and the request IDs so that each
line fits on the screen; in the log the fields are separated by tabs.

A real Lambda `REPORT` line keeps INIT in its own field. This example
comes from the
[Lambda Python logging guide](https://docs.aws.amazon.com/lambda/latest/dg/python-logging.html):

```text
REPORT RequestId: 1c8df7d3-xmpl-46da-9778-518e6eca8125 Duration: 15.74 ms Billed Duration: 147 ms
Memory Size: 128 MB Max Memory Used: 56 MB Init Duration: 130.49 ms
```

`Billed Duration` (147 ms) is `Duration` plus `Init Duration`, rounded
up: Lambda bills the INIT phase of functions that use a managed runtime
([execution environment lifecycle](https://docs.aws.amazon.com/lambda/latest/dg/lambda-runtime-environment.html)).

### Step 4.3: What INIT does

Open `functions/orders/app.py`. The code between the imports and the
first `def` runs during INIT: it creates the DynamoDB resource and
measures how long that took in `INIT_MS`.

```bash
curl -s http://localhost:8080/visits | grep -E '"(cold_start|init_ms)"'
```

```text
    "cold_start": false,
    "init_ms": 180.6
```

Of the 367 ms of INIT, 181 ms went to creating the DynamoDB resource
(`init_ms`). The rest is the start of the Python runtime and the import
of `boto3`. All of it happens once per environment, and every warm
invocation reuses the client.

### Step 4.4: Record your measurements

| Measurement | Your value |
| --- | --- |
| Client latency of the cold request (ms) | |
| Client latency of a warm request (ms) | |
| `INIT REPORT` duration (ms) | |
| `Duration` of a warm `REPORT` line (ms) | |
| `init_ms` reported by the function (ms) | |

> **Question:** Your API must answer in under 100 ms for 99% of requests,
> and traffic drops to zero every night. What does the first customer of
> the morning experience, and which Lambda feature removes most of that
> delay?
>
> **Hint:** Read about
> [Provisioned Concurrency](https://docs.aws.amazon.com/lambda/latest/dg/provisioned-concurrency.html)
> and [SnapStart](https://docs.aws.amazon.com/lambda/latest/dg/snapstart.html),
> which supports Python 3.12 and later.
>
> **Question:** Why should the DynamoDB client be created at module level
> and not inside the handler?
>
> **Hint:** Move it inside the handler in your head and multiply its cost
> by the number of warm invocations of Step 4.1.

---

## Task 5: Timeouts and Memory

A Lambda function has two main settings: the **timeout** (default 3 s,
maximum 900 s) and the **memory** (128 MB to 10,240 MB). Lambda assigns
CPU in proportion to memory: 1,769 MB equals one full vCPU. The
`fn-work` service copies that rule with Docker limits: `mem_limit`
follows `WORK_MEMORY_MB` and `cpus` follows `WORK_CPUS` (open
`docker-compose.yml`). The default is 256 MB and 0.15 CPU.

### Step 5.1: Hit the timeout

`lab15-work` has a timeout of 3 seconds. Ask it to work for 5:

```bash
curl -s -i -X POST http://localhost:8080/2015-03-31/functions/lab15-work/invocations \
    -d '{"sleep_ms": 5000}' | grep -E '^HTTP|X-Amz|X-Lab-Env|Task'
docker compose logs --no-log-prefix fn-work | grep -E 'Reset|SIGKILL|Duration: 3000' | tail -3 \
    | sed -E 's/^[0-9]+ [A-Z][a-z]+ [0-9]+ [0-9:,]+ //' | sed -E 's/RequestId: [0-9a-f-]+[[:space:]]+//'
curl -s -X POST http://localhost:8080/2015-03-31/functions/lab15-work/invocations -d '{}' \
    | grep -E '"(cold_start|invocations)"'
```

Expected output:

```text
HTTP/1.0 200 OK
X-Lab-Environment: lab15-fn-work-1
X-Amz-Function-Error: Unhandled
Task timed out after 3.00 seconds
[WARNING] (rapid) Reset initiated: Timeout
[INFO] (rapid) Sending SIGKILL to runtime-1(28).
REPORT Duration: 3000.00 ms Billed Duration: 3000 ms Memory Size: 256 MB Max Memory Used: 256 MB
    "cold_start": true,
    "invocations": 1,
```

Like the Lambda `Invoke` API, the gateway answers 200 and marks the
failure with the `X-Amz-Function-Error` header: the call reached the
function, the function failed. The runtime killed the process at exactly
3,000 ms, billed all 3,000 ms, and **reset the environment**: the next
invocation was a cold start with `invocations` back to 1.

### Step 5.2: Memory buys CPU

Run the same CPU-bound task (200,000 SHA-256 hashes) three times at the
default 256 MB:

```bash
for i in 1 2 3; do
    curl -s -X POST http://localhost:8080/2015-03-31/functions/lab15-work/invocations \
        -d '{"iterations": 200000}' | grep -o '"cpu_ms": [0-9.]*'
done
```

Expected output:

```text
"cpu_ms": 174.4
"cpu_ms": 269.0
"cpu_ms": 277.5
```

Redeploy `lab15-work` with 1,769 MB and one full CPU, and run it again:

```bash
WORK_MEMORY_MB=1769 WORK_CPUS=1.0 docker compose up -d --wait fn-work
for i in 1 2 3 4; do
    curl -s -X POST http://localhost:8080/2015-03-31/functions/lab15-work/invocations \
        -d '{"iterations": 200000}' | grep -oE '"cold_start": [a-z]+|"cpu_ms": [0-9.]*' | paste -sd' ' -
done
docker compose logs --no-log-prefix fn-work | grep -E 'INIT REPORT' | tail -1 \
    | sed -E 's/^[0-9]+ [A-Z][a-z]+ [0-9]+ [0-9:,]+ //'
```

Expected output:

```text
"cold_start": true "cpu_ms": 34.9
"cold_start": false "cpu_ms": 37.3
"cold_start": false "cpu_ms": 34.4
"cold_start": false "cpu_ms": 33.3
[INFO] (rapid) INIT REPORT(durationMs: 127.681000)
```

The task ran about seven times faster. The INIT phase also benefits: go
back to the default size and look at the cold start there:

```bash
docker compose up -d --wait fn-work
curl -s -X POST http://localhost:8080/2015-03-31/functions/lab15-work/invocations -d '{}' > /dev/null
docker compose logs --no-log-prefix fn-work | grep -E 'INIT REPORT' | tail -1 \
    | sed -E 's/^[0-9]+ [A-Z][a-z]+ [0-9]+ [0-9:,]+ //'
```

```text
[INFO] (rapid) INIT REPORT(durationMs: 848.749000)
```

Without the variables, Compose recreated the container with the defaults
again. At 256 MB the same INIT took 849 ms instead of 128 ms.

### Step 5.3: Cost per invocation

Lambda bills **GB-seconds**: memory in GB times billed duration in
seconds. Compute it for both sizes with your `cpu_ms` values (warm runs):

| Memory | GB | Warm duration (s) | GB-seconds per invocation |
| --- | --- | --- | --- |
| 256 MB | 0.25 | 0.240 | 0.25 x 0.240 = 0.0600 |
| 1,769 MB | 1.7275 | 0.035 | 1.7275 x 0.035 = 0.0605 |

Multiply by the price per GB-second of the
[AWS Lambda pricing page](https://aws.amazon.com/lambda/pricing/) (its
examples use USD 0.0000166667 for x86). For one million invocations the
two sizes cost about USD 1.00 and USD 1.01 of compute: 7 times the memory
cost about 1% more and answered about seven times faster. For CPU-bound
code a larger memory setting often costs little extra, and for I/O-bound
code (like `sleep_ms`) it only adds cost.

### Step 5.4: Run out of memory

At 256 MB, ask for 300 MB, then for 100 MB:

```bash
curl -s -i -X POST http://localhost:8080/2015-03-31/functions/lab15-work/invocations \
    -d '{"allocate_mb": 300}' | grep -E '^HTTP|X-Amz|"error'
curl -s -X POST http://localhost:8080/2015-03-31/functions/lab15-work/invocations \
    -d '{"allocate_mb": 100}' | grep -oE '"cold_start": [a-z]+|"allocated_mb": [0-9]+' | paste -sd' ' -
docker compose logs --no-log-prefix fn-work | grep -E 'exited: signal' | tail -1 \
    | sed -E 's/^[0-9]+ [A-Z][a-z]+ [0-9]+ [0-9:,]+ //'
```

Expected output:

```text
HTTP/1.0 200 OK
X-Amz-Function-Error: Unhandled
  "errorType": "Runtime.ExitError",
  "errorMessage": "RequestId: 856ada18-010e-48ef-8745-5976c4deda56 Error: Runtime exited with error: signal: killed"
"cold_start": true "allocated_mb": 100
[WARNING] (rapid) Process runtime-1 exited: signal: killed
```

The kernel killed the runtime when it passed the limit, and the next
invocation needed a new environment. Lambda reports the same error
(`Runtime exited with error: signal: killed`), and its `REPORT` line then
shows `Max Memory Used` equal to `Memory Size`.

**Record:** the timeout error message; the warm `cpu_ms` and the INIT
duration at 256 MB and at 1,769 MB; your GB-seconds per invocation for
both sizes; the error type of the out-of-memory invocation.

> **Question:** A function calls an external API that sometimes hangs for
> two minutes. The timeout is 15 minutes "to be safe". What does that
> cost when the API hangs during a traffic peak?
>
> **Hint:** Billed duration, plus the concurrency of Task 7: a hanging
> invocation keeps its environment busy.
>
> **Question:** The memory setting grew about 7 times. Why did the cost
> of the CPU-bound task grow by less than half?
>
> **Hint:** GB-seconds multiply two numbers. One went up about 7 times;
> what happened to the other?

---

## Task 6: Events, Retries and Idempotency

Most functions run because an **event** happened, not because a user
waited for them. Here a checkout publishes payments to an SQS queue, and
`lab15-processor` charges them. Lambda reads the queue through an
**event source mapping**: it polls, sends batches to the function, and
deletes the messages that succeeded. SQS delivers each message **at
least once**, so the function must survive duplicates.

Open `functions/processor/app.py` and read `_charge` and `handler`.

### Step 6.1: Process a batch

Send the SQS event of Step 2.3 directly to the function:

```bash
docker exec lab15-gateway python table.py reset
curl -s -X POST http://localhost:8080/2015-03-31/functions/lab15-processor/invocations \
    -d @events/sqs-batch.json
docker exec lab15-gateway python table.py scan PAYMENT#
```

Expected output:

```text
Deleted 2 item(s) from lab15.
{
  "batchItemFailures": []
}
PAYMENT#ORD-1001             charged_total=25  charges=1
PAYMENT#ORD-1002             charged_total=40  charges=1
2 item(s)
```

`batchItemFailures` is the **partial batch response**: the IDs of the
messages that failed. Empty means the event source mapping can delete the
whole batch.

### Step 6.2: A duplicate without idempotency

Redeploy the processor with idempotency turned off, and deliver the same
batch twice, as SQS does after a timeout or a lost acknowledgment:

```bash
docker exec lab15-gateway python table.py reset
IDEMPOTENCY=off docker compose up -d --wait fn-processor
curl -s -X POST http://localhost:8080/2015-03-31/functions/lab15-processor/invocations \
    -d @events/sqs-batch.json
curl -s -X POST http://localhost:8080/2015-03-31/functions/lab15-processor/invocations \
    -d @events/sqs-batch.json
docker exec lab15-gateway python table.py scan PAYMENT#
```

Expected output (Compose lines omitted):

```text
Deleted 4 item(s) from lab15.
{
  "batchItemFailures": []
}
{
  "batchItemFailures": []
}
PAYMENT#ORD-1001             charged_total=50  charges=2
PAYMENT#ORD-1002             charged_total=80  charges=2
2 item(s)
```

Both customers paid twice. Each delivery succeeded, and that is the
problem.

### Step 6.3: The same duplicate with idempotency

Redeploy with the default (`IDEMPOTENCY=on`) and repeat:

```bash
docker exec lab15-gateway python table.py reset
docker compose up -d --wait fn-processor
curl -s -X POST http://localhost:8080/2015-03-31/functions/lab15-processor/invocations \
    -d @events/sqs-batch.json
curl -s -X POST http://localhost:8080/2015-03-31/functions/lab15-processor/invocations \
    -d @events/sqs-batch.json
docker compose logs --no-log-prefix fn-processor | grep '"outcome"' | tail -4
docker exec lab15-gateway python table.py scan
```

Expected output (Compose lines omitted):

```text
Deleted 2 item(s) from lab15.
{
  "batchItemFailures": []
}
{
  "batchItemFailures": []
}
{"message_id": "6f1c1a52-8a39-4c1e-9a77-0c0f3c7e1001", "receives": 1, "order_id": "ORD-1001", "outcome": "charged"}
{"message_id": "6f1c1a52-8a39-4c1e-9a77-0c0f3c7e1002", "receives": 1, "order_id": "ORD-1002", "outcome": "charged"}
{"message_id": "6f1c1a52-8a39-4c1e-9a77-0c0f3c7e1001", "receives": 1, "order_id": "ORD-1001", "outcome": "duplicate"}
{"message_id": "6f1c1a52-8a39-4c1e-9a77-0c0f3c7e1002", "receives": 1, "order_id": "ORD-1002", "outcome": "duplicate"}
IDEMPOTENCY#ORD-1001         message_id=6f1c1a52-8a39-4c1e-9a77-0c0f3c7e1001
IDEMPOTENCY#ORD-1002         message_id=6f1c1a52-8a39-4c1e-9a77-0c0f3c7e1002
PAYMENT#ORD-1001             charged_total=25  charges=1
PAYMENT#ORD-1002             charged_total=40  charges=1
4 item(s)
```

The function writes `IDEMPOTENCY#<order_id>` and the charge in **one
DynamoDB transaction**, with the condition that the idempotency item does
not exist yet. The second delivery fails that condition, the transaction
is cancelled, and nothing is charged twice. This is the idempotent
consumer of Lab 14, with DynamoDB in place of SQLite.

### Step 6.4: A poison message and the dead letter queue

Now use the queue of the gateway, which works like an SQS standard queue
with a redrive policy (visibility timeout 12 s, `maxReceiveCount` 3) and
an event source mapping that sends batches of up to 10 messages. Send
three payments; the second one has a negative amount and can never
succeed:

```bash
docker exec lab15-gateway python table.py reset
curl -s -X POST http://localhost:8080/queues/orders -d '[
    {"order_id": "ORD-2001", "amount": 10},
    {"order_id": "ORD-2002", "amount": -5},
    {"order_id": "ORD-2003", "amount": 30}
]'
```

Wait 30 seconds, then look at the queue and at the gateway log:

```bash
sleep 30
curl -s http://localhost:8080/queues/orders
docker logs lab15-gateway 2>&1 | grep -E 'esm' | tail -4
docker exec lab15-gateway python table.py scan PAYMENT#
```

Expected output:

```text
{
  "queue": "lab15-orders",
  "visible": 0,
  "in_flight": 0,
  "deleted": 2,
  "dead_letter_queue": [
    {
      "messageId": "60c38bed-343d-4693-9fcd-f788f0530262",
      "body": "{\"order_id\": \"ORD-2002\", \"amount\": -5}",
      "receiveCount": 3
    }
  ],
  "visibility_timeout_s": 12.0,
  "max_receive_count": 3
}
[gateway] esm batch of 3 (receive counts 1,1,1): 2 deleted, 1 failed
[gateway] esm batch of 1 (receive counts 2): 0 deleted, 1 failed
[gateway] esm batch of 1 (receive counts 3): 0 deleted, 1 failed
[gateway] esm moved 60c38bed to the dead letter queue after 3 receives
PAYMENT#ORD-2001             charged_total=10  charges=1
PAYMENT#ORD-2003             charged_total=30  charges=1
2 item(s)
```

The first batch had three messages. The function charged two and named
the third in `batchItemFailures`, so only that one stayed in the queue.
It became visible again after the visibility timeout, failed twice more,
and moved to the dead letter queue with its receive count. The two good
payments were never retried.

### Step 6.5: One crash fails the whole batch

A body of `{"crash": true}` makes the function raise an exception before
it answers. Empty the queue and its DLQ, and send a crash between two
good payments:

```bash
curl -s -X DELETE http://localhost:8080/queues/orders
curl -s -X POST http://localhost:8080/queues/orders -d '[
    {"order_id": "ORD-3001", "amount": 10},
    {"crash": true},
    {"order_id": "ORD-3003", "amount": 30}
]'
sleep 30
curl -s http://localhost:8080/queues/orders | grep -E '"(visible|in_flight|deleted|body|receiveCount)"'
docker compose logs --no-log-prefix fn-processor | grep -E 'ORD-3001' | tail -3
docker exec lab15-gateway python table.py scan PAYMENT#ORD-3
```

Expected output (the two `curl -X` answers omitted):

```text
  "visible": 0,
  "in_flight": 0,
  "deleted": 0,
      "body": "{\"order_id\": \"ORD-3001\", \"amount\": 10}",
      "receiveCount": 3
      "body": "{\"crash\": true}",
      "receiveCount": 3
      "body": "{\"order_id\": \"ORD-3003\", \"amount\": 30}",
      "receiveCount": 3
{"message_id": "05efc246-3422-419f-86a2-1bdc1ccdcf7a", "receives": 1, "order_id": "ORD-3001", "outcome": "charged"}
{"message_id": "05efc246-3422-419f-86a2-1bdc1ccdcf7a", "receives": 2, "order_id": "ORD-3001", "outcome": "duplicate"}
{"message_id": "05efc246-3422-419f-86a2-1bdc1ccdcf7a", "receives": 3, "order_id": "ORD-3001", "outcome": "duplicate"}
PAYMENT#ORD-3001             charged_total=10  charges=1
1 item(s)
```

When the invocation fails, the event source mapping cannot know which
messages succeeded, so the **whole batch** returns to the queue. All three
messages reached the DLQ. `ORD-3001` was charged on the first attempt and
skipped as a duplicate on the next two: idempotency saved that customer
from paying three times. `ORD-3003` came after the crash and was never
charged, although it was valid.

**Record:** the `charges` of `ORD-1001` in Steps 6.2 and 6.3; the number
of messages in the DLQ and their receive counts in Steps 6.4 and 6.5; the
outcome of each delivery of `ORD-3001`.

> **Question:** The processor uses `order_id` as the idempotency key, not
> `messageId`. When would a key based on `messageId` let a double charge
> through?
>
> **Hint:** The checkout times out and publishes the same payment again.
> Does SQS give the new message the same `messageId`?
>
> **Question:** AWS recommends a queue visibility timeout of at least six
> times the function timeout. What happens if it is shorter than one
> invocation?
>
> **Hint:** The message becomes visible while the first invocation is
> still processing it. Read
> [Configuring an SQS event source](https://docs.aws.amazon.com/lambda/latest/dg/services-sqs-configure.html).
>
> **Question:** Steps 6.4 and 6.5 put a valid payment in the DLQ in one
> case and not in the other. What did the function do differently?
>
> **Hint:** Compare an exception that escapes the handler with an entry
> in `batchItemFailures`
> ([partial batch responses](https://docs.aws.amazon.com/lambda/latest/dg/services-sqs-errorhandling.html)).

---

## Task 7: Concurrency and Throttling

On the default Lambda compute, an execution environment processes **one
request at a time**. When more
requests arrive than there are idle environments, Lambda creates new ones,
each with its own cold start, up to the concurrency quota of the account
or the limit you set on the function. Above that limit Lambda answers
**429 TooManyRequestsException**: the function is **throttled**.

The emulator cannot create environments by itself, so in this lab the
number of `fn-work` containers is the concurrency limit, and you change
it with `--scale`. The gateway gives each request to an idle container and
throttles when none is idle. `load.py` starts N requests at the same
moment, each one working for one second.

### Step 7.1: One environment, six requests

```bash
docker exec lab15-gateway python load.py --requests 6 --sleep-ms 1000
```

Expected output:

```text
req  status  environment        start      ms
  1     429  -                              8
  2     200  lab15-fn-work-1    warm     1010
  3     429  -                              7
  4     429  -                              8
  5     429  -                              6
  6     429  -                              8
1 succeeded, 5 throttled (429), 0 failed, 1 environment(s) used, 0 cold start(s), wall time 1.01 s
```

One request got the environment; the other five were rejected within
milliseconds. A function with a reserved concurrency of 1 behaves exactly
like this in AWS.

### Step 7.2: Three environments

```bash
docker compose up -d --wait --scale fn-work=3 fn-work
docker exec lab15-gateway python load.py --requests 6 --sleep-ms 1000
docker exec lab15-gateway python load.py --requests 6 --sleep-ms 1000
```

Expected output:

```text
req  status  environment        start      ms
  1     200  lab15-fn-work-2    cold     1694
  2     200  lab15-fn-work-3    cold     1724
  3     429  -                             11
  4     200  lab15-fn-work-1    warm     1022
  5     429  -                             11
  6     429  -                             11
3 succeeded, 3 throttled (429), 0 failed, 3 environment(s) used, 2 cold start(s), wall time 1.73 s
req  status  environment        start      ms
  1     200  lab15-fn-work-2    warm     1014
  2     200  lab15-fn-work-3    warm     1015
  3     200  lab15-fn-work-1    warm     1013
  4     429  -                             13
  5     429  -                             14
  6     429  -                             13
3 succeeded, 3 throttled (429), 0 failed, 3 environment(s) used, 0 cold start(s), wall time 1.02 s
```

The two new environments paid a cold start of about 0.7 s on top of the
one second of work. In the second round all three were warm.

### Step 7.3: Six environments

```bash
docker compose up -d --wait --scale fn-work=6 fn-work
docker exec lab15-gateway python load.py --requests 6 --sleep-ms 1000
```

Expected output:

```text
req  status  environment        start      ms
  1     200  lab15-fn-work-5    cold     1704
  2     200  lab15-fn-work-6    cold     1720
  3     200  lab15-fn-work-3    warm     1014
  4     200  lab15-fn-work-2    warm     1015
  5     200  lab15-fn-work-4    cold     1721
  6     200  lab15-fn-work-1    warm     1015
6 succeeded, 0 throttled (429), 0 failed, 6 environment(s) used, 3 cold start(s), wall time 1.72 s
```

Six simultaneous requests need six environments. Each environment also
has its own memory. Requests sent one after another would all reach the
same idle environment, so send six that overlap, twice:

```bash
for round in 1 2; do
    for i in 1 2 3 4 5 6; do
        curl -s -i 'http://localhost:8080/work?sleep_ms=500' \
            | grep -oE 'X-Lab-Environment: [a-z0-9-]+|"invocations": [0-9]+' | paste -sd' ' - &
    done
    wait
done
```

Expected output (the order of the lines changes from run to run):

```text
X-Lab-Environment: lab15-fn-work-1 "invocations": 5
X-Lab-Environment: lab15-fn-work-2 "invocations": 4
X-Lab-Environment: lab15-fn-work-3 "invocations": 4
X-Lab-Environment: lab15-fn-work-4 "invocations": 2
X-Lab-Environment: lab15-fn-work-5 "invocations": 2
X-Lab-Environment: lab15-fn-work-6 "invocations": 2
X-Lab-Environment: lab15-fn-work-1 "invocations": 6
X-Lab-Environment: lab15-fn-work-2 "invocations": 5
X-Lab-Environment: lab15-fn-work-3 "invocations": 5
X-Lab-Environment: lab15-fn-work-4 "invocations": 3
X-Lab-Environment: lab15-fn-work-5 "invocations": 3
X-Lab-Environment: lab15-fn-work-6 "invocations": 3
```

Each environment counts only the requests that it served, so the same
global variable holds a different value in each one. That is the second
answer to the question of Step 3.4.

### Step 7.4: What real Lambda does differently

| Behavior | This lab | AWS Lambda |
| --- | --- | --- |
| New environments | You start containers with `--scale` | Created on demand, each with a cold start |
| Default ceiling | The number of containers | 1,000 concurrent executions per Region for the account (a quota you can raise) |
| Scaling rate | Instant, the containers already exist | Up to 1,000 new execution environments every 10 seconds per function |
| Limit per function | The number of containers | Reserved concurrency, which also reserves that capacity |
| Above the limit | 429 from the gateway | The invocation is throttled; what happens next depends on who invoked the function (below) |

Sources: [Lambda scaling behavior](https://docs.aws.amazon.com/lambda/latest/dg/scaling-behavior.html)
and [Lambda quotas](https://docs.aws.amazon.com/lambda/latest/dg/gettingstarted-limits.html).

Who retries a throttled invocation depends on how the function was
invoked:

- **Synchronous calls** (API Gateway, the `Invoke` API) receive the 429
  `TooManyRequestsException`, and the caller decides whether to retry.
- **SQS** reaches the function through an event source mapping, which
  invokes it synchronously. When the function is throttled, Lambda backs
  off and reduces the concurrency of the mapping, and the messages stay
  in the queue until they become visible again
  ([SQS error handling](https://docs.aws.amazon.com/lambda/latest/dg/services-sqs-errorhandling.html)).
- **Asynchronous invocations** (S3, SNS, EventBridge) wait in an internal
  queue of Lambda. Lambda retries a throttled event for up to 6 hours by
  default, and a function error 2 more times
  ([asynchronous error handling](https://docs.aws.amazon.com/lambda/latest/dg/invocation-async-error-handling.html)).

Scale back to one environment:

```bash
docker compose up -d --wait --scale fn-work=1 fn-work
```

**Record:** for 1, 3 and 6 environments, the number of successful and
throttled requests, the number of cold starts and the wall time.

> **Question:** A function behind an API receives 300 requests per second
> and each takes 200 ms. How many execution environments does it need at
> the same time?
>
> **Hint:** Concurrency = requests per second x duration in seconds
> (Little's law).
>
> **Question:** The same function writes to a database that accepts 50
> connections. What happens at 300 requests per second, and how would you
> protect the database?
>
> **Hint:** Each environment opens its own connection. Think about
> reserved concurrency and about a queue between the API and the writes.

---

## Task 8: AWS Lambda Versus Azure Functions

Everything you measured exists on Azure under different names. Read the
table, then answer the questions. Every value links to the official
documentation; check it before you quote a limit in a design, because
providers change their limits.

| Topic | AWS Lambda | Azure Functions |
| --- | --- | --- |
| Unit of deployment | One function, as a .zip file or a container image, with its own memory, timeout and permissions | A **function app**: several functions deployed together and sharing one hosting plan |
| How events arrive | Services that push events (API Gateway, S3, SNS, EventBridge) and **event source mappings** that poll queues and streams (SQS, Kinesis, DynamoDB Streams, Kafka); other services are called with the SDK | **Triggers** plus declarative **input and output bindings** that read from and write to Blob Storage, Queue Storage, Service Bus, Event Hubs, Cosmos DB and others without SDK code ([triggers and bindings](https://learn.microsoft.com/en-us/azure/azure-functions/functions-triggers-bindings)) |
| Hosting and billing | One serverless model: requests plus GB-seconds, INIT included ([pricing](https://aws.amazon.com/lambda/pricing/)) | A choice of plans: **Flex Consumption** (the recommended serverless plan), Consumption (legacy), Premium, Dedicated (App Service) and Container Apps ([hosting options](https://learn.microsoft.com/en-us/azure/azure-functions/functions-scale), [pricing](https://azure.microsoft.com/en-us/pricing/details/functions/)) |
| Memory and CPU | 128 MB to 10,240 MB; CPU in proportion, 1,769 MB = 1 vCPU ([memory](https://docs.aws.amazon.com/lambda/latest/dg/configuration-memory.html)) | Flex Consumption instances of 512 MB, 2,048 MB or 4,096 MB; Consumption instances of 1.5 GB ([Flex Consumption](https://learn.microsoft.com/en-us/azure/azure-functions/flex-consumption-plan)) |
| Maximum duration | 900 s, default 3 s ([timeout](https://docs.aws.amazon.com/lambda/latest/dg/configuration-timeout.html)) | Consumption 10 min (default 5); Flex Consumption, Premium and Dedicated default 30 min and no fixed maximum; an HTTP trigger must answer within 230 s ([hosting options](https://learn.microsoft.com/en-us/azure/azure-functions/functions-scale)) |
| Requests per instance | One invocation per environment on the default compute ([concurrency](https://docs.aws.amazon.com/lambda/latest/dg/lambda-concurrency.html)); with **Lambda Managed Instances**, one environment handles several invocations at once ([Managed Instances](https://docs.aws.amazon.com/lambda/latest/dg/lambda-managed-instances.html)) | Several per instance; Flex Consumption defaults to 4, 16 or 32 concurrent HTTP requests for the 512, 2,048 and 4,096 MB sizes, and 1 for Python apps ([concurrency](https://learn.microsoft.com/en-us/azure/azure-functions/functions-concurrency)) |
| Scale-out limit | 1,000 concurrent executions per Region by default; 1,000 new environments every 10 s per function ([scaling](https://docs.aws.amazon.com/lambda/latest/dg/scaling-behavior.html)) | Consumption 200 instances (Windows) or 100 (Linux); Flex Consumption up to 1,000 (default 100); Premium 100 (Windows) or 20 to 100 (Linux) ([event-driven scaling](https://learn.microsoft.com/en-us/azure/azure-functions/event-driven-scaling)) |
| Cold start mitigation | **Provisioned Concurrency**; **SnapStart** for Java 11+, Python 3.12+ and .NET 8+ ([SnapStart](https://docs.aws.amazon.com/lambda/latest/dg/snapstart.html)) | **Premium**: always-ready and prewarmed instances ([Premium plan](https://learn.microsoft.com/en-us/azure/azure-functions/functions-premium-plan)); **Flex Consumption**: always-ready instances |
| Long workflows with state | AWS Step Functions, and Lambda durable functions ([durable functions](https://docs.aws.amazon.com/lambda/latest/dg/durable-functions.html)) | Durable Functions ([overview](https://learn.microsoft.com/en-us/azure/durable-task/durable-functions/durable-functions-overview)) |
| Run it locally | The Runtime Interface Emulator of this lab ([container images](https://docs.aws.amazon.com/lambda/latest/dg/python-image.html)) | Azure Functions Core Tools ([run locally](https://learn.microsoft.com/en-us/azure/azure-functions/functions-run-local)) |

Map what you did in this lab to Azure:

| In this lab | On Azure |
| --- | --- |
| `handler(event, context)` reading an SQS batch | A function with a Queue Storage or Service Bus trigger |
| `TABLE.put_item(...)` with the SDK | An output binding to Cosmos DB, or the SDK |
| `WORK_MEMORY_MB=1769` | The instance memory size of a Flex Consumption app |
| Six environments for six requests | One instance can take several HTTP requests at once (not for Python apps on Flex Consumption) |
| Provisioned Concurrency against cold starts | Always-ready instances (Flex Consumption) or prewarmed instances (Premium) |

**Record:** for 100 simultaneous HTTP requests, the number of AWS Lambda
execution environments needed on the default compute, and the number of Flex Consumption
instances of 2,048 MB needed for a Node.js app and for a Python app with
the default concurrency.

> **Question:** A team runs a 20-minute video conversion per uploaded
> file. Which services and plans of the table can run it as a single
> invocation, and what would you do on Lambda instead?
>
> **Hint:** Compare the maximum durations, then think about splitting the
> work or about the workflow services of the table.
>
> **Question:** Why does the per-instance concurrency of Azure Functions
> change how you would write the visit counter of Task 3?
>
> **Hint:** On the default Lambda compute, one environment runs one
> request at a time. What happens to a global variable when 16 requests
> share one process?

---

## Task 9 (Optional): Deploy the Same Handler to AWS Academy

> **Optional.** This task needs an active **AWS Academy Learner Lab**
> session and uses its credits. Everything before it runs without AWS.
> Learner Lab accounts cannot create IAM roles, so the function uses the
> pre-created `LabRole`. Work in `us-east-1`.

The handler of `lab15-orders` runs unchanged in AWS: without
`DYNAMODB_ENDPOINT`, `boto3` connects to the real DynamoDB, and the
credentials come from the role of the function instead of environment
variables.

### Step 9.1: Open a terminal with the AWS CLI

Start the Learner Lab, open the AWS console, and open **AWS CloudShell**
from its toolbar (or use the terminal of the Learner Lab page, where the
AWS CLI is configured). Clone the repository and check the account:

```bash
git clone https://github.com/gamaware/system-design-course.git
cd system-design-course/15-serverless
aws sts get-caller-identity --query Account --output text
```

The last command prints your 12-digit account ID. The next steps read it
into `ACCOUNT_ID`; never paste it into files you share.

### Step 9.2: Create the table and the function

```bash
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
aws dynamodb create-table --table-name lab15 \
    --attribute-definitions AttributeName=pk,AttributeType=S \
    --key-schema AttributeName=pk,KeyType=HASH --billing-mode PAY_PER_REQUEST
aws dynamodb wait table-exists --table-name lab15

(cd functions/orders && python3 -m zipfile -c ../../orders.zip app.py)
aws lambda create-function --function-name lab15-orders \
    --runtime python3.12 --handler app.handler \
    --role "arn:aws:iam::${ACCOUNT_ID}:role/LabRole" \
    --zip-file fileb://orders.zip --timeout 3 --memory-size 512 \
    --environment 'Variables={TABLE_NAME=lab15}'
aws lambda wait function-active-v2 --function-name lab15-orders
```

The deployment package is a .zip file with `app.py`, not a container
image: the runtime `python3.12` is the same one that the base image of
this lab contains.

### Step 9.3: Invoke it twice and read the real REPORT lines

```bash
for i in 1 2; do
    aws lambda invoke --function-name lab15-orders --cli-binary-format raw-in-base64-out \
        --payload '{"routeKey": "GET /visits"}' response.json > /dev/null
    cat response.json; echo
done
sleep 10
aws logs tail /aws/lambda/lab15-orders --since 10m | grep REPORT
```

The first invocation reports `"cold_start": true` and the second
`false`. The first `REPORT` line has a real `Init Duration` and a real
`Max Memory Used`, which the emulator could not give you.

**Record:** both `REPORT` lines, and compare `Init Duration` and `Max
Memory Used` with your local numbers of Task 4.

### Step 9.4: Clean up the AWS resources

```bash
aws lambda delete-function --function-name lab15-orders
aws dynamodb delete-table --table-name lab15
aws logs delete-log-group --log-group-name /aws/lambda/lab15-orders
rm -f orders.zip response.json
```

---

## Cleanup

```bash
./cleanup.sh
```

Expected output (Compose lines omitted). If any lab container, network
or image survives, the script lists it and exits with an error instead.

```text
=== Lab 15: Cleanup ===

Stopping and removing all lab resources...

Cleanup complete. All containers, the network, and the lab images removed.
```

Verify cleanup:

```bash
docker ps -a --filter name=lab15
docker network ls --filter name=lab15
docker image ls 'lab15-*'
```

None of the commands should list anything after its header line: no
`lab15-*` containers, no `lab15_default` network and no `lab15-*` images.
The base images (`public.ecr.aws/lambda/python` and
`amazon/dynamodb-local`) stay in your Docker cache; remove them with
`docker image rm` if you need the disk space.
