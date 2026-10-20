# Lab 05: Key Characteristics of Distributed Systems

> For the lab overview, architecture diagram, and key concepts, see
> [README.md](README.md).

## Prerequisites

- **Docker Desktop** installed and running (includes Docker Compose)
- **curl** on the host (preinstalled on macOS, Linux, and Git Bash)
- A terminal that supports bash (macOS Terminal, Linux shell, Git Bash
  on Windows, or WSL)
- Lab 03 (load balancing with HAProxy) is recommended background

No cloud account is needed. Everything runs locally in Docker Compose.

> **Git Bash on Windows:** Git Bash rewrites any argument that starts with `/` into a Windows path, which breaks
> commands such as `docker exec lab05-client python /scripts/probe.py`. Run `export MSYS_NO_PATHCONV=1` once in
> each new terminal before you start. The scripts of this lab already do it for their own commands.

**Verify Docker:**

```bash
docker --version
docker compose version
```

### Ports used by this lab

The lab only publishes ports in the `18000-18099` range plus `8474`, so it can run next to the
other labs of the course. Every port listens on `127.0.0.1` only, so other machines on your network
cannot reach the nodes or the Toxiproxy API:

| Port | Service |
| --- | --- |
| `18001`, `18002`, `18003` | node1, node2, node3 (direct access) |
| `18080` | HAProxy frontend **with** health checks |
| `18081` | HAProxy frontend **without** health checks |
| `18090` | HAProxy stats page (`/stats`) |
| `8474` | Toxiproxy API |

### Quick Start

```bash
cd 05-distributed-systems-high-availability
chmod +x setup.sh cleanup.sh scripts/*.sh
./setup.sh
```

Then follow the tasks below. Every number you measure goes into the results table of Task 8, so keep
a text file open and write each value down as you go.

> **Your numbers will differ.** The outputs in this guide are real runs on a laptop. Latencies of a
> few milliseconds, the exact second a health check fires, and request counts change from run to run.
> What should match is the *shape* of the result: which requests fail, which ones do not, and why.

---

## Task 1: Start the Environment

Start three replicated key-value nodes, Toxiproxy in front of every network link, HAProxy as the load
balancer, and a client container that runs the measurement scripts.

### Step 1.1: Run the setup script

```bash
./setup.sh
```

The script starts six containers, waits until every node reports ready and HAProxy sees all three as
healthy, and writes one key (`greeting`) so all tasks start from the same data.

Expected output (abbreviated):

```text
=== Lab 05: Key Characteristics of Distributed Systems ===
...
Waiting for services to be healthy...
  Nodes:     ready (node1, node2, node3)
  Toxiproxy: ready (9 proxies)
  HAProxy:   ready (health checks passing)

Seeding key 'greeting'...
  {"node": "node1", "key": "greeting", "value": "hello", "version": [1, "node1"]}
  {"node": "node2", "key": "greeting", "value": "hello", "version": [1, "node1"]}
  {"node": "node3", "key": "greeting", "value": "hello", "version": [1, "node1"]}

=== Environment ready ===
```

The key was written once, on node1, and all three nodes return it: the write was **replicated**.

### Step 1.2: List the containers

```bash
docker compose ps --format 'table {{.Name}}\t{{.Image}}\t{{.Status}}'
```

Expected output:

```text
NAME              IMAGE                              STATUS
lab05-client      python:3.13.16-alpine3.24          Up 9 seconds
lab05-haproxy     haproxy:3.2.26-alpine              Up 3 seconds
lab05-node1       python:3.13.16-alpine3.24          Up 9 seconds (health: starting)
lab05-node2       python:3.13.16-alpine3.24          Up 9 seconds (health: starting)
lab05-node3       python:3.13.16-alpine3.24          Up 9 seconds (health: starting)
lab05-toxiproxy   ghcr.io/shopify/toxiproxy:2.13.0   Up 9 seconds (healthy)
```

Each node is a small Python program (`app/kv_node.py`) that keeps the data in memory, has its own
clock, and talks to the other nodes only over the network. That is the definition of a distributed
system from the lecture: independent computers, no shared memory, no shared clock.

### Step 1.3: Inspect the network links

```bash
docker exec lab05-toxiproxy /toxiproxy-cli list
```

Expected output:

```text
front-node1     [::]:18041      node1:8080      enabled 0
front-node2     [::]:18042      node2:8080      enabled 0
front-node3     [::]:18043      node3:8080      enabled 0
repl-1-2        [::]:18012      node2:8080      enabled 0
repl-1-3        [::]:18013      node3:8080      enabled 0
repl-2-1        [::]:18021      node1:8080      enabled 0
repl-2-3        [::]:18023      node3:8080      enabled 0
repl-3-1        [::]:18031      node1:8080      enabled 0
repl-3-2        [::]:18032      node2:8080      enabled 0
```

Toxiproxy is a TCP proxy that can misbehave on purpose. The `front-*` proxies sit between HAProxy and
each node. The `repl-<from>-<to>` proxies carry replication traffic: `repl-1-2` is the link node1 uses
to reach node2. The last column (`0`) is the number of active **toxics**, the faults you will inject.

### Step 1.4: Check what HAProxy sees

```bash
curl -s "http://localhost:18090/stats;csv" | cut -d, -f1,2,18 | grep "^be_"
```

Expected output:

```text
be_checks,node1,UP
be_checks,node2,UP
be_checks,node3,UP
be_checks,BACKEND,UP
be_nochecks,node1,no check
be_nochecks,node2,no check
be_nochecks,node3,no check
be_nochecks,BACKEND,UP
```

HAProxy has two backends with the **same three nodes**. `be_checks` (port 18080) asks every node
`GET /health/ready` once per second. `be_nochecks` (port 18081) never asks. You can also open
<http://localhost:18090/stats> in a browser and watch the colors change during the next tasks.

Send three requests through the load balancer:

```bash
for i in 1 2 3; do curl -s http://localhost:18080/kv/greeting; done
```

Expected output:

```text
{"node": "node1", "key": "greeting", "value": "hello", "version": [1, "node1"]}
{"node": "node2", "key": "greeting", "value": "hello", "version": [1, "node1"]}
{"node": "node3", "key": "greeting", "value": "hello", "version": [1, "node1"]}
```

Round robin spreads the requests, and every replica answers with the same value.

### Step 1.5: Liveness is not readiness

Restart node3 and ask it two different health questions during its first seconds:

```bash
docker restart lab05-node3
sleep 1
curl -s -w " HTTP %{http_code}\n" http://localhost:18003/health/live
curl -s -w " HTTP %{http_code}\n" http://localhost:18003/health/ready
curl -s -w " HTTP %{http_code}\n" http://localhost:18003/kv/greeting
```

Expected output:

```text
{"node": "node3", "status": "alive", "uptime_s": 1.0}
 HTTP 200
{"node": "node3", "status": "warming up"}
 HTTP 503
{"node": "node3", "error": "warming up"}
 HTTP 503
```

The process is **alive** (liveness check passes) but not **ready** (readiness check fails): it is
copying data from its peers and warming up, like a cold standby that must boot and load state before it
can serve. Wait a few seconds and check the log:

```bash
sleep 6
curl -s -w " HTTP %{http_code}\n" http://localhost:18003/health/ready
docker logs lab05-node3 | tail -3
```

Expected output:

```text
{"node": "node3", "status": "ready"}
 HTTP 200
05:36:26 [node3] starting in ap mode, warming up for 5s
05:36:26 [node3] listening on :8080, peers=node1,node2, quorum=2/3
05:36:31 [node3] ready with 1 key(s)
```

node3 lost its memory when it restarted, yet it came back with `1 key(s)`: it rebuilt its state from
the other replicas. That is replication working as a recovery mechanism.

> **Question:** A load balancer should send traffic only to nodes that can answer correctly. Which
> endpoint should its health check call, `/health/live` or `/health/ready`? What would go wrong with the
> other one?
>
> **Hint:** Look at the third `curl` of Step 1.5. What does a client receive if the load balancer
> trusts `/health/live` while node3 is still warming up?

---

## Task 2: Measure the Baseline

Before breaking anything, measure how the healthy system behaves. Without a baseline you cannot tell
degradation from normal noise.

### Step 2.1: Measure latency through the load balancer

The `probe.py` script sends requests one after another (one every 50 ms by default) and summarizes
availability, latency percentiles, and which node answered. It runs inside the client container, on
the same network as the nodes.

```bash
docker exec lab05-client python /scripts/probe.py http://haproxy:18080/kv/greeting --count 200
```

Expected output:

```text
Requests: 200  OK: 200  Errors: 0  Availability: 100.0%
Latency of OK responses (ms): p50=2.8  p95=4.5  p99=7.2  max=11.4
Responses by node: node1=67  node2=67  node3=66
Status codes: 200=200
```

`p50` is the median: half of the requests were faster. `p95` means 95 % of requests were faster than
that value, so it describes the slowest 5 %. **Write down p50 and p95.**

### Step 2.2: Measure one node directly

```bash
docker exec lab05-client python /scripts/probe.py http://node1:8080/kv/greeting --count 200
```

Expected output:

```text
Requests: 200  OK: 200  Errors: 0  Availability: 100.0%
Latency of OK responses (ms): p50=1.5  p95=2.4  p99=4.9  max=8.3
Responses by node: node1=200
Status codes: 200=200
```

> **Question:** The path through HAProxy and Toxiproxy is about 1 ms slower than calling node1 directly.
> Why accept that cost? What does the extra hop give you that a direct call does not?
>
> **Hint:** Count how many nodes can answer each URL. What happens to each client if node1 fails?

---

## Task 3: Inject Latency: Degradation Without Failure

The lecture states that a slow node is harder to handle than a dead one. In this task you slow down a
single replica and watch what the clients experience.

### Step 3.1: Add 300 ms of latency to node2

```bash
docker exec lab05-toxiproxy /toxiproxy-cli toxic add -t latency -a latency=300 -a jitter=50 front-node2
docker exec lab05-toxiproxy /toxiproxy-cli inspect front-node2
```

Expected output:

```text
Added downstream latency toxic 'latency_downstream' on proxy 'front-node2'
latency_downstream type=latency stream=downstream toxicity=1.00 attributes=[jitter=50 latency=300]
```

Every response from node2 to HAProxy is now delayed 300 ms (plus or minus 50 ms).

### Step 3.2: Measure again

```bash
docker exec lab05-client python /scripts/probe.py http://haproxy:18080/kv/greeting --count 200
curl -s "http://localhost:18090/stats;csv" | cut -d, -f1,2,18 | grep "^be_checks,node"
```

Expected output:

```text
Requests: 200  OK: 200  Errors: 0  Availability: 100.0%
Latency of OK responses (ms): p50=3.4  p95=341.7  p99=350.5  max=355.0
Responses by node: node1=67  node2=66  node3=67
Status codes: 200=200
be_checks,node1,UP
be_checks,node2,UP
be_checks,node3,UP
```

Availability is still 100 % and the median barely moved, but p95 went from ~4 ms to ~340 ms. One user
in three now waits a third of a second. The system is **degraded, not down**, and the health checks
see nothing wrong because 300 ms is below their 1 s timeout. **Write down the new p95.**

### Step 3.3: Make node2 slower than the timeout

HAProxy cuts any request that takes longer than `timeout server 2s` (see `haproxy/haproxy.cfg`).
Raise the latency to 3 seconds:

```bash
docker exec lab05-toxiproxy /toxiproxy-cli toxic update -n latency_downstream -a latency=3000 -a jitter=0 front-node2
sleep 5
```

Compare both frontends. The frontend without health checks takes about 20 seconds because every
request that lands on node2 waits for the 2 s timeout:

```bash
docker exec lab05-client python /scripts/probe.py http://haproxy:18081/kv/greeting --count 30
docker exec lab05-client python /scripts/probe.py http://haproxy:18080/kv/greeting --count 30
```

Expected output:

```text
Requests: 30  OK: 20  Errors: 10  Availability: 66.7%
Latency of OK responses (ms): p50=2.4  p95=4.2  p99=8.0  max=8.0
Responses by node: node1=10  node3=10
Status codes: 200=20  504=10
Requests: 30  OK: 30  Errors: 0  Availability: 100.0%
Latency of OK responses (ms): p50=2.7  p95=4.8  p99=6.7  max=6.7
Responses by node: node1=15  node3=15
Status codes: 200=30
```

Without health checks, one request in three ends in `504 Gateway Timeout` after waiting two seconds.
With health checks, node2 no longer receives traffic. Find out why in the HAProxy log:

```bash
docker logs lab05-haproxy 2>/dev/null | grep "be_checks/node2" | tail -3
```

Expected output:

```text
Health check for server be_checks/node2 failed, reason: Layer7 timeout, check duration: 1001ms, status: 1/2 UP.
Health check for server be_checks/node2 failed, reason: Layer7 timeout, check duration: 1001ms, status: 0/2 DOWN.
Server be_checks/node2 is DOWN. 2 active and 0 backup servers left. 0 sessions active, 0 requeued, ...
```

The health check did not find a crashed process. It found a node too **slow** to be useful and removed
it, which is how a timeout turns a slow node into a node that is treated as failed.

### Step 3.4: Remove the toxic

```bash
docker exec lab05-toxiproxy /toxiproxy-cli toxic remove -n latency_downstream front-node2
sleep 4
curl -s "http://localhost:18090/stats;csv" | cut -d, -f1,2,18 | grep "^be_checks,node2"
```

Expected output:

```text
Removed toxic 'latency_downstream' on proxy 'front-node2'
be_checks,node2,UP
```

> **Question:** In Step 3.2 the median stayed at ~3 ms while p95 jumped to ~340 ms. If your monitoring
> dashboard showed only the average or the median, would anyone notice the problem?
>
> **Hint:** Two thirds of the requests never touch node2. Which percentile is the first to include the
> requests that do?
>
> **Question:** Without the 2 s `timeout server`, how long would the clients of port 18081 wait for
> node2? What happens to a web server whose worker threads all wait on a slow dependency?
>
> **Hint:** The lecture calls this a cascading failure. A timeout bounds the wait; it does not remove
> the error.

---

## Task 4: Replication and a Network Partition (AP Mode)

The nodes start in **AP mode**: a write is stored on the node that receives it, acknowledged at once,
and copied to the other nodes in the background. In this task you cut the network and see what that
choice means.

### Step 4.1: Write and watch replication

Write a key on node1 and read it from every node. `read_all.py --wait` polls the three nodes every
100 ms until they agree:

```bash
curl -s -X PUT --data "blue" http://localhost:18001/kv/color
docker exec lab05-client python /scripts/read_all.py color --wait
```

Expected output:

```text
{"node": "node1", "mode": "ap", "key": "color", "version": [2, "node1"], "acks": 1, "replication": "async"}
  node1: blue (version 2,node1)
  node2: blue (version 2,node1)
  node3: blue (version 2,node1)
replicas AGREE after 0.11 s
```

`acks: 1` means only node1 had the value when the client got its answer. For about 0.1 s the replicas
disagreed: that is **eventual consistency** even without any failure. **Write down the time.**

The `version` is `[counter, node]`. The counter is a **logical clock** (a Lamport clock): every node
increments it on each write and moves it forward when it sees a higher value from a peer. Wall-clock
time is never used to order writes, because the nodes do not share a clock.

### Step 4.2: Partition node1 from the cluster

```bash
bash scripts/partition.sh isolate node1
```

Expected output:

```text
  + toxiproxy-cli toxic add -t timeout -a timeout=0 -u -n partition repl-1-2
  + toxiproxy-cli toxic add -t timeout -a timeout=0 -u -n partition repl-1-3
  + toxiproxy-cli toxic add -t timeout -a timeout=0 -u -n partition repl-2-1
  + toxiproxy-cli toxic add -t timeout -a timeout=0 -u -n partition repl-3-1
Partition active: node1 is isolated from the other nodes.
```

The `timeout` toxic accepts the connection but never delivers a byte. That is what a real partition
looks like to the sender: silence, not an error. The only way to notice is a timeout (0.5 s here).

### Step 4.3: Write on both sides of the partition

Write on the isolated node:

```bash
curl -s -X PUT --data "red" http://localhost:18001/kv/color
sleep 3
docker exec lab05-client python /scripts/read_all.py color
curl -s http://localhost:18001/admin/state
```

Expected output:

```text
{"node": "node1", "mode": "ap", "key": "color", "version": [3, "node1"], "acks": 1, "replication": "async"}
  node1: red (version 3,node1)
  node2: blue (version 2,node1)
  node3: blue (version 2,node1)
replicas DISAGREE
{"node": "node1", "mode": "ap", "ready": true, "clock": 3, "keys": 2, "pending": {"node2": 1, "node3": 1}}
```

node1 accepted the write (it is **available**), but node2 and node3 still return `blue` (they are
**not consistent**). node1 keeps the write in a pending queue for each peer and retries every second.

Now write a different value on the majority side:

```bash
curl -s -X PUT --data "green" http://localhost:18002/kv/color
sleep 3
docker exec lab05-client python /scripts/read_all.py color
```

Expected output:

```text
{"node": "node2", "mode": "ap", "key": "color", "version": [3, "node2"], "acks": 1, "replication": "async"}
  node1: red (version 3,node1)
  node2: green (version 3,node2)
  node3: green (version 3,node2)
replicas DISAGREE
```

Two clients wrote two different values for the same key and both got a success. This is a
**conflict**, the price of staying available during a partition.

### Step 4.4: Heal the partition and measure convergence

```bash
bash scripts/partition.sh heal
docker exec lab05-client python /scripts/read_all.py color --wait
```

Expected output:

```text
  - toxiproxy-cli toxic remove -n partition repl-1-2
  - toxiproxy-cli toxic remove -n partition repl-1-3
  - toxiproxy-cli toxic remove -n partition repl-2-1
  - toxiproxy-cli toxic remove -n partition repl-3-1
Partition healed: every replication link is open.
  node1: green (version 3,node2)
  node2: green (version 3,node2)
  node3: green (version 3,node2)
replicas AGREE after 0.12 s
```

The replicas converged on one value. The rule is **last-writer-wins** on the version: the higher
counter wins and, on a tie, the higher node name wins. In this run both writes had counter 3, so
`node2` beat `node1` and `red` was discarded. In another run the counters may differ and `red` may
win. Either way, one client's acknowledged write was silently lost. **Write down the convergence time.**

The time is counted from the moment `partition.sh heal` returns. Each node retries its pending writes
once per second, so any value between 0 and about 1 s is normal; a run close to 0 means the retry fired
while the heal command was still removing toxics.

> **Question:** In the CAP theorem, which two properties did the cluster keep during the partition,
> and which one did it give up?
>
> **Hint:** Did any write or read fail during Step 4.3? Did every read return the latest write?
>
> **Question:** `green` was written several seconds *after* `red`, yet in some runs `red` wins. Why
> does the cluster not just compare the time of day of each write?
>
> **Hint:** Each node has its own clock and the clocks drift. Look at the lecture slide on clock
> synchronization.
>
> **Question:** A shopping cart and a bank balance both live in a key-value store. Which one tolerates
> last-writer-wins, and which one cannot afford to lose an acknowledged write?
>
> **Hint:** What does the customer lose in each case if one of two concurrent updates disappears?

---

## Task 5: The Other CAP Choice: CP Mode With a Quorum

Switch the cluster to **CP mode**. Now a write succeeds only when a **quorum** (a majority, 2 of 3
nodes) stores it, and a node answers reads only while it can reach a majority.

### Step 5.1: Switch the mode and write

```bash
bash scripts/set-mode.sh cp
curl -s -X PUT --data "10" http://localhost:18001/kv/stock
docker exec lab05-client python /scripts/read_all.py stock --wait
```

Expected output:

```text
{"node": "node1", "mode": "cp"}
{"node": "node2", "mode": "cp"}
{"node": "node3", "mode": "cp"}
{"node": "node1", "mode": "cp", "key": "stock", "version": [4, "node1"], "acks": 2, "quorum": 2}
  node1: 10 (version 4,node1)
  node2: 10 (version 4,node1)
  node3: 10 (version 4,node1)
replicas AGREE after 0.01 s
```

`acks: 2` means the client received its answer only after two nodes, node1 and one peer, stored the
value. The third replica may still be storing it when the answer returns, which is why `read_all.py`
runs with `--wait`. All three agree within a few milliseconds, but only two were guaranteed to have
the value.

### Step 5.2: Partition node1 again

```bash
bash scripts/partition.sh isolate node1 > /dev/null
bash scripts/partition.sh status
```

Expected output:

```text
  repl-1-2  CUT
  repl-1-3  CUT
  repl-2-1  CUT
  repl-2-3  open
  repl-3-1  CUT
  repl-3-2  open
```

### Step 5.3: Write on the minority and on the majority

```bash
curl -s -w "HTTP %{http_code} in %{time_total}s\n" -X PUT --data "9" http://localhost:18001/kv/stock
curl -s -w "HTTP %{http_code} in %{time_total}s\n" -X PUT --data "8" http://localhost:18002/kv/stock
docker exec lab05-client python /scripts/read_all.py stock
```

Expected output:

```text
{"node": "node1", "mode": "cp", "error": "no quorum", "acks": 1, "quorum": 2}
HTTP 503 in 0.504712s
{"node": "node2", "mode": "cp", "key": "stock", "version": [5, "node2"], "acks": 2, "quorum": 2}
HTTP 200 in 0.006709s
  node1: HTTP 503 no quorum
  node2: 8 (version 5,node2)
  node3: 8 (version 5,node2)
replicas DISAGREE
```

The minority side (node1) **refuses** both the write and the read rather than risk a wrong answer. It
took 0.5 s to refuse, the replication timeout it waited before giving up on its peers. The majority
side (node2 and node3) keeps working and returns the latest value. The output says `DISAGREE` only
because node1 gives no value at all; no node returns stale data.

### Step 5.4: Measure what the load balancer clients see

```bash
docker exec lab05-client python /scripts/probe.py http://haproxy:18080/kv/stock --count 60
```

Expected output:

```text
Requests: 60  OK: 40  Errors: 20  Availability: 66.7%
Latency of OK responses (ms): p50=5.4  p95=7.3  p99=8.0  max=8.0
Responses by node: node2=20  node3=20
Status codes: 200=40  503=20
```

A third of the requests still land on node1 and fail, because its readiness check says nothing about
quorum. **Write down this availability.**

### Step 5.5: Heal and return to AP mode

```bash
bash scripts/partition.sh heal > /dev/null
docker exec lab05-client python /scripts/read_all.py stock --wait
bash scripts/set-mode.sh ap
```

Expected output:

```text
  node1: 8 (version 5,node2)
  node2: 8 (version 5,node2)
  node3: 8 (version 5,node2)
replicas AGREE after 0.78 s
{"node": "node1", "mode": "ap"}
{"node": "node2", "mode": "ap"}
{"node": "node3", "mode": "ap"}
```

No write was lost: the rejected write `9` was never acknowledged, and node1 caught up with `8`.

> **Question:** Compare Task 4 and Task 5 during the same partition. Fill in for each mode: did node1
> accept writes, did node1 answer reads, could a client read a stale value, was any acknowledged write
> lost?
>
> **Hint:** AP keeps every node answering and fixes conflicts later. CP keeps the answers correct and
> stops answering where it cannot guarantee that.
>
> **Question:** With 3 nodes the quorum is 2. With 5 nodes, how many can fail before writes stop? Why do
> clusters use an odd number of nodes?
>
> **Hint:** The majority of N is `N // 2 + 1`. Compute it for 4 and 5 nodes and compare.
>
> **Question:** In Step 5.4 HAProxy kept sending traffic to node1. How would you change node1's readiness
> check so the load balancer stops doing that during a partition?
>
> **Hint:** What does node1 already know when it answers `no quorum`?

---

## Task 6: Failure Detection and Recovery: MTTD and MTTR

The lecture defines availability as `MTBF / (MTBF + MTTR)` and splits the outage into detection (MTTD)
and repair (MTTR). Here you crash a node under load and measure both on one timeline.

### Step 6.1: Run the failover measurement

`failover.py` sends 20 requests per second through **each** frontend (18080 with health checks, 18081
without), crashes node2 after a 2 s baseline, and records what happens. The node exits with status 1,
and Docker's restart policy (`restart: on-failure` in `docker-compose.yml`) starts it again, like an
orchestrator would.

```bash
docker exec lab05-client python /scripts/failover.py --node node2
```

Expected output:

```text
Baseline: 2s of traffic at 20 req/s per client...

Timeline (seconds after the crash)
  t=  0.00s  crash sent to node2
  t=  0.11s  process gone (connections refused)
  t=  0.51s  process restarted by Docker (live)
  t=  2.31s  HAProxy marks node DOWN
  t=  5.44s  warm-up finished (ready)
  t=  7.33s  HAProxy marks node UP

Measurements
  MTTD (crash -> HAProxy DOWN): 2.31 s
  MTTR (crash -> HAProxy UP):   7.33 s

  Client                 Requests  Errors  Availability   Error window, codes
  with checks (18080)         203       8         96.1%   t=0.11s .. t=2.11s, 502=1 503=7
  no checks   (18081)         202      28         86.1%   t=0.21s .. t=5.33s, 503=28
```

Read the timeline from top to bottom:

1. The process dies at 0.1 s and Docker restarts it at 0.5 s. The process is alive again almost at
   once, but it is warming up.
2. HAProxy needs two failed checks one second apart, so it marks node2 DOWN at 2.3 s. That is the
   **MTTD**. Every error on port 18080 happens inside this window. Depending on when the next check
   fires after the crash, your MTTD will land between about 1 and 3 s.
3. node2 is ready at 5.4 s, and after two good checks HAProxy marks it UP at 7.3 s. That is the
   **MTTR**: the time until the system has its full capacity again.

**Write down MTTD, MTTR, and both availability values.**

### Step 6.2: Confirm the restart

```bash
docker logs lab05-haproxy 2>/dev/null | grep "be_checks/node2 is" | tail -2
docker inspect -f 'restarts={{.RestartCount}} status={{.State.Status}}' lab05-node2
```

Expected output:

```text
Server be_checks/node2 is DOWN. 2 active and 0 backup servers left. 0 sessions active, 0 requeued, ...
Server be_checks/node2 is UP. 3 active and 0 backup servers online. 0 sessions requeued, 0 total in queue.
restarts=1 status=running
```

> **Question:** The process was alive again at 0.5 s, yet HAProxy marked it DOWN at 2.3 s. Why did it
> not stay UP, and was that the right decision?
>
> **Hint:** Go back to Step 1.5. What does `/health/ready` return during warm-up?
>
> **Question:** All three nodes are active and serve traffic at the same time. Which redundancy model
> from the lecture is this: hot-cold, hot-warm, or hot-hot? What did that model cost in Task 4?
>
> **Hint:** The lecture says hot-hot needs conflict resolution for concurrent writes.

---

## Task 7: With and Without Health Checks

Health checks helped in Task 6, but node2 came back on its own in half a second. Real failures are
often longer, and the detection settings themselves are a trade-off. In this task you change one
variable at a time.

### Step 7.1: A failure that does not repair itself

`docker stop` is a manual stop, so the restart policy does not bring the node back: a human has to.

```bash
docker stop lab05-node2
sleep 3
docker exec lab05-client python /scripts/probe.py http://haproxy:18081/kv/greeting --count 100
docker exec lab05-client python /scripts/probe.py http://haproxy:18080/kv/greeting --count 100
```

Expected output:

```text
lab05-node2
Requests: 100  OK: 66  Errors: 34  Availability: 66.0%
Latency of OK responses (ms): p50=2.9  p95=4.5  p99=4.6  max=5.4
Responses by node: node1=33  node3=33
Status codes: 200=66  502=34
Requests: 100  OK: 100  Errors: 0  Availability: 100.0%
Latency of OK responses (ms): p50=3.1  p95=4.7  p99=5.9  max=8.2
Responses by node: node1=50  node3=50
Status codes: 200=100
```

Without health checks, the client keeps failing one request in three for as long as the node is down,
whether that is five seconds or five hours. With health checks, the outage cost a couple of seconds and
the remaining two nodes absorbed the load. Bring node2 back:

```bash
docker start lab05-node2
```

### Step 7.2: Slower detection

The check interval comes from the `CHECK_INTER` variable. Recreate HAProxy with checks every 3 seconds
instead of 1, wait for the checks to settle, and repeat the crash:

```bash
CHECK_INTER=3s docker compose up -d haproxy
sleep 10
docker exec lab05-client python /scripts/failover.py --node node2
```

Expected output (abbreviated):

```text
Timeline (seconds after the crash)
  t=  0.00s  crash sent to node2
  t=  0.11s  process gone (connections refused)
  t=  0.42s  process restarted by Docker (live)
  t=  3.96s  HAProxy marks node DOWN
  t=  5.42s  warm-up finished (ready)
  t= 10.02s  HAProxy marks node UP

Measurements
  MTTD (crash -> HAProxy DOWN): 3.96 s
  MTTR (crash -> HAProxy UP):   10.02 s

  Client                 Requests  Errors  Availability   Error window, codes
  with checks (18080)         275      25         90.9%   t=0.20s .. t=3.89s, 502=2 503=23
  no checks   (18081)         275      34         87.6%   t=0.20s .. t=5.26s, 502=2 503=32
```

MTTD grew, the errors on port 18080 grew with it, and MTTR grew too: slow checks are slow to notice a
failure **and** slow to notice the recovery. Depending on when the checks fire, MTTD can land anywhere
between 3 and 6 s, and HAProxy may even notice nothing at all if the node is ready again first.
Restore the default interval:

```bash
docker compose up -d haproxy
```

### Step 7.3: Faster recovery

Now leave detection alone and shorten the repair. Recreate node2 with a 1 second warm-up:

```bash
WARMUP_SECONDS=1 docker compose up -d node2
sleep 8
docker exec lab05-client python /scripts/failover.py --node node2
```

Expected output (abbreviated):

```text
Timeline (seconds after the crash)
  t=  0.00s  crash sent to node2
  t=  0.10s  process gone (connections refused)
  t=  0.42s  process restarted by Docker (live)
  t=  1.46s  warm-up finished (ready)

Measurements
  MTTD: never detected (the node came back before HAProxy noticed)
  MTTR: no DOWN/UP cycle in HAProxy

  Client                 Requests  Errors  Availability   Error window, codes
  with checks (18080)         305       8         97.4%   t=0.22s .. t=1.29s, 502=2 503=6
  no checks   (18081)         305       8         97.4%   t=0.17s .. t=1.24s, 502=2 503=6
```

The node recovered in 1.5 s, before two checks could fail, so HAProxy never marked it DOWN and both
frontends saw the same 8 errors. A fast repair made the health checks irrelevant for this failure.
Restore the default warm-up:

```bash
docker compose up -d node2
```

> **Question:** Why not set `CHECK_INTER` to 100 ms and `fall` to 1, so failures are detected almost
> instantly?
>
> **Hint:** Remember Step 3.2: a node that is merely slow for one moment would be removed and added back
> over and over (flapping). Each check is also extra traffic on every node.
>
> **Question:** In Step 7.1 the health checks saved availability. In Step 7.3 they changed nothing. What
> does that tell you about where to invest: faster detection or faster recovery?
>
> **Hint:** Errors happen between the failure and whichever comes first, detection or repair.

---

## Task 8: Your Measurements and the Nines

Gather your own numbers in one table. The *Reference run* column holds the values from this guide,
so you can check that yours have the same shape.

### Step 8.1: Fill in the results table

| # | Measurement | Task | Your value | Reference run |
| --- | --- | --- | --- | --- |
| 1 | Baseline p50 / p95 through HAProxy | 2.1 | | 2.8 / 4.5 ms |
| 2 | Baseline p50 through a single node | 2.2 | | 1.5 ms |
| 3 | p50 / p95 with 300 ms latency on node2 | 3.2 | | 3.4 / 341.7 ms |
| 4 | Availability with node2 at 3 s latency, no checks / checks | 3.3 | | 66.7 % / 100 % |
| 5 | Replication lag without a partition (AP) | 4.1 | | 0.11 s |
| 6 | Convergence after healing the partition (AP) | 4.4 | | 0.12 s |
| 7 | Minority write during the partition (CP): status and time | 5.3 | | HTTP 503 in 0.50 s |
| 8 | Availability through HAProxy during the partition (CP) | 5.4 | | 66.7 % |
| 9 | MTTD with `CHECK_INTER=1s` | 6.1 | | 2.31 s |
| 10 | MTTR with `CHECK_INTER=1s` | 6.1 | | 7.33 s |
| 11 | Errors during the crash, checks / no checks | 6.1 | | 8 / 28 |
| 12 | Availability with node2 stopped, no checks / checks | 7.1 | | 66.0 % / 100 % |
| 13 | MTTD / MTTR with `CHECK_INTER=3s` | 7.2 | | 3.96 / 10.02 s |
| 14 | Errors during the crash with `WARMUP_SECONDS=1` | 7.3 | | 8 / 8 |

### Step 8.2: Turn your numbers into nines

The clients sent 20 requests per second, so each failed request represents 1/20 s of user-visible
outage. Use row 11 to estimate the downtime that one crash costs each client:

```text
downtime per crash = errors / 20 req/s
  with checks:     8 / 20 = 0.40 s
  without checks: 28 / 20 = 1.40 s
```

Assume node2 crashes once per hour (MTBF = 3600 s) and apply the lecture's formula with that
user-visible downtime in place of MTTR:

```text
availability = MTBF / (MTBF + downtime)
  with checks:     3600 / (3600 + 0.40) = 99.989 %   (three nines, just short of four)
  without checks:  3600 / (3600 + 1.40) = 99.961 %   (three nines)
```

Compute the same two values with your own error counts, and a third one with your errors from
Step 7.2 (`CHECK_INTER=3s`).

> **Question:** The nines table says 99.99 % allows 52 minutes of downtime per year. Using your
> numbers, how many crashes per year can this cluster absorb before it drops below four nines, with and
> without health checks?
>
> **Hint:** Divide 52 minutes (3,120 s) by your downtime per crash.
>
> **Question:** Which of the levers you tried in this lab (redundancy, timeouts, health checks, check
> interval, automatic restart, warm-up time, CP vs AP) moved availability the most for the least cost?
>
> **Hint:** Compare rows 4, 11, 12, and 14 of your table.

### Step 8.3: Cleanup

```bash
./cleanup.sh
```

---

## Cleanup

If you have not already cleaned up, run:

```bash
./cleanup.sh
```

Verify cleanup:

```bash
docker ps -a --filter "name=lab05-"
```

Expected output: only the header line, with no `lab05-` containers. The lab creates no named volumes
and builds no images; the pinned images (`python`, `haproxy`, `toxiproxy`) stay in the local cache.
Remove them with `docker image rm` if you need the disk space.
