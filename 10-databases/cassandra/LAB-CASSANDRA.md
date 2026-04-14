# Lab 10C: Cassandra Multi-node, Consistency, and Partition Keys

![Cassandra](https://img.shields.io/badge/Cassandra-%231287B1.svg?style=for-the-badge&logo=apachecassandra&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-%232496ED.svg?style=for-the-badge&logo=docker&logoColor=white)

## Overview

This lab explores three database scalability mechanisms using Apache
Cassandra: multi-node cluster replication with fault tolerance, tunable
consistency levels (ONE, QUORUM, ALL), and partition key design for
distributed data. Students work with a university enrollment dataset
across a three-node Cassandra ring with replication factor 3.

## Learning Objectives

- Deploy and verify a 3-node Cassandra cluster with RF=3
- Test fault tolerance by stopping a node and verifying reads still work
- Compare consistency levels and observe write failures when nodes are down
- Design effective partition keys and understand the impact of bad
  partition key choices

## Prerequisites

- **Docker Desktop** installed and running (allocate at least 4 GB RAM)
- Basic SQL familiarity (CQL is similar to SQL)
- No cloud account required (Option A) or AWS Academy credentials
  (Option B)

## Choose Your Environment

| Environment | What You Need | Setup |
| --- | --- | --- |
| **Option A: Local** | Docker Desktop + terminal | `./setup.sh` |
| **Option B: EC2** | Browser + SSH client | Upload `cloudformation.yaml` via AWS Console |

### Option A: Local Setup

```bash
cd 10-databases/cassandra
chmod +x setup.sh cleanup.sh
./setup.sh
```

Setup takes 2-4 minutes (Cassandra nodes join sequentially).
Then skip to **Task 1** below.

### Option B: EC2 Setup (AWS Academy)

1. Download `cloudformation.yaml` from this directory
2. In the AWS Console, go to **CloudFormation** > **Create stack**
3. Upload the template, name it `lab10c-cassandra`, click **Submit**
4. Wait ~5 minutes (Cassandra takes longer to start)
5. Find the **PublicIP** in Outputs, SSH in:

```bash
chmod 400 labsuser.pem
ssh -i labsuser.pem ec2-user@YOUR_PUBLIC_IP
ls ~/LAB_READY
cd ~/system-design-course/10-databases/cassandra
```

---

## Task 1: Verify the Cluster

### Step 1.1: Check cluster status

```bash
docker exec cass1 nodetool status
```

Expected output shows 3 nodes with status `UN` (Up/Normal):

```text
Datacenter: dc1
===============
Status=Up/Down
|/ State=Normal/Leaving/Joining/Moving
--  Address      Load       Tokens  ...  State   ...  Rack
UN  172.x.x.x    xxx KiB   16      ...  Normal  ...  rack1
UN  172.x.x.x    xxx KiB   16      ...  Normal  ...  rack2
UN  172.x.x.x    xxx KiB   16      ...  Normal  ...  rack3
```

### Step 1.2: Verify seed data

```bash
docker exec cass1 cqlsh -e "
USE university;
SELECT COUNT(*) FROM students;
SELECT COUNT(*) FROM courses;
"
```

Expected: 10 students, 4 courses.

### Step 1.3: Query students by partition key (major)

```bash
docker exec cass1 cqlsh -e "
USE university;
SELECT name, email FROM students WHERE major = 'Computer Science';
"
```

This query is efficient because `major` is the partition key.

> **Question:** Why does Cassandra require you to query by partition key?
>
> **Hint:** Data is distributed across nodes based on the partition key
> hash. Without it, Cassandra must scan all nodes.

---

## Task 2: Replication and Fault Tolerance

### Step 2.1: Insert data on cass1

```bash
docker exec cass1 cqlsh -e "
USE university;
INSERT INTO courses (code, title, capacity, enrolled)
VALUES ('ENG101', 'English Composition', 40, 0);
"
```

### Step 2.2: Read from cass2

```bash
docker exec cass2 cqlsh -e "
USE university;
SELECT * FROM courses WHERE code = 'ENG101';
"
```

The data is available on cass2 because RF=3 replicates to all nodes.

### Step 2.3: Stop a node

```bash
docker stop cass3
```

### Step 2.4: Verify reads still work

```bash
docker exec cass1 cqlsh -e "
USE university;
CONSISTENCY ONE;
SELECT * FROM courses WHERE code = 'ENG101';
"
```

The query succeeds because CL=ONE only needs one replica to respond,
and two nodes are still running.

### Step 2.5: Verify writes still work

```bash
docker exec cass1 cqlsh -e "
USE university;
CONSISTENCY ONE;
INSERT INTO courses (code, title, capacity, enrolled)
VALUES ('ART101', 'Art History', 20, 0);
SELECT * FROM courses WHERE code = 'ART101';
"
```

> **Question:** With RF=3 and one node down, what is the maximum
> consistency level that still allows reads and writes?
>
> **Hint:** QUORUM requires `(RF/2) + 1` nodes. With RF=3, that is 2.

---

## Task 3: Tunable Consistency Levels

### Step 3.1: Read with CL=QUORUM (2 of 3 nodes must respond)

```bash
docker exec cass1 cqlsh -e "
USE university;
CONSISTENCY QUORUM;
SELECT * FROM courses WHERE code = 'CS101';
"
```

This works because 2 of 3 nodes are up (cass3 is still stopped).

### Step 3.2: Attempt CL=ALL with a node down

```bash
docker exec cass1 cqlsh -e "
USE university;
CONSISTENCY ALL;
SELECT * FROM courses WHERE code = 'CS101';
"
```

Expected error:

```text
NoHostAvailable:
```

CL=ALL requires all 3 replicas to respond, but cass3 is down.

### Step 3.3: Restart the stopped node

```bash
docker start cass3
```

Wait about 30 seconds for the node to rejoin, then retry:

```bash
docker exec cass1 cqlsh -e "
USE university;
CONSISTENCY ALL;
SELECT * FROM courses WHERE code = 'CS101';
"
```

Now CL=ALL succeeds because all 3 nodes are up.

### Step 3.4: Verify the stopped node caught up

Check that data written while cass3 was down is now present:

```bash
docker exec cass3 cqlsh -e "
USE university;
CONSISTENCY ONE;
SELECT * FROM courses WHERE code = 'ART101';
"
```

Cassandra's hinted handoff delivered the missed writes.

> **Question:** When would you use CL=ALL in production?
>
> **Hint:** Almost never -- it sacrifices availability. CL=QUORUM
> gives strong consistency while tolerating one node failure.

---

## Task 4: Partition Key Design

### Step 4.1: Insert data with a BAD partition key

The `access_log_bad` table uses `log_type` as partition key. All rows
go to the same partition:

```bash
docker exec cass1 cqlsh -e "
USE university;
INSERT INTO access_log_bad (log_type, accessed_at, student_name, resource)
VALUES ('web', toTimestamp(now()), 'Alice', 'resource-1');
INSERT INTO access_log_bad (log_type, accessed_at, student_name, resource)
VALUES ('web', toTimestamp(now()), 'Bob', 'resource-2');
INSERT INTO access_log_bad (log_type, accessed_at, student_name, resource)
VALUES ('web', toTimestamp(now()), 'Carol', 'resource-3');
"
```

### Step 4.2: Insert data with a GOOD partition key

The `access_log_good` table uses `day` as partition key. Data spreads
across days:

```bash
docker exec cass1 cqlsh -e "
USE university;
INSERT INTO access_log_good (day, accessed_at, student_name, resource)
VALUES ('2025-01-15', toTimestamp(now()), 'Alice', 'resource-1');
INSERT INTO access_log_good (day, accessed_at, student_name, resource)
VALUES ('2025-01-16', toTimestamp(now()), 'Bob', 'resource-2');
INSERT INTO access_log_good (day, accessed_at, student_name, resource)
VALUES ('2025-01-17', toTimestamp(now()), 'Carol', 'resource-3');
"
```

### Step 4.3: Compare partition distribution

```bash
docker exec cass1 nodetool tablestats university.access_log_bad 2>/dev/null \
    | grep -E "Number of partitions|Compacted partition"
docker exec cass1 nodetool tablestats university.access_log_good 2>/dev/null \
    | grep -E "Number of partitions|Compacted partition"
```

The bad table has 1 partition (all data on one node = hotspot).
The good table has 3 partitions (data distributed across nodes).

### Step 4.4: Query efficiency

Querying by partition key is fast (single-node lookup):

```bash
docker exec cass1 cqlsh -e "
USE university;
SELECT * FROM access_log_good WHERE day = '2025-01-15';
"
```

Querying without partition key requires a full cluster scan:

```bash
docker exec cass1 cqlsh -e "
USE university;
SELECT * FROM access_log_good WHERE student_name = 'Alice'
ALLOW FILTERING;
"
```

The `ALLOW FILTERING` keyword is a red flag -- it means Cassandra must
scan all partitions. In production with millions of rows, this query
would be unacceptably slow.

> **Question:** Why is a single-value partition key (like `log_type =
> 'web'`) bad at scale?
>
> **Hint:** All data lands on the same set of replica nodes. Those
> nodes become hotspots while others sit idle.

---

## Cleanup

```bash
./cleanup.sh
```

For EC2, also delete the CloudFormation stack in the AWS Console.

## Troubleshooting

| Issue | Cause | Fix |
| --- | --- | --- |
| `nodetool status` shows DN | Node still starting | Wait 30-60 seconds, retry |
| `NoHostAvailable` error | Not enough replicas for CL | Lower consistency level or start the stopped node |
| `Cannot achieve consistency` | Node down + CL too high | Use CL=ONE or restart the node |
| Cassandra OOM crash | Not enough Docker memory | Allocate at least 4 GB RAM in Docker Desktop |
| `ALLOW FILTERING` timeout | Full scan on large data | Design queries around partition keys instead |

## Key Concepts

| Concept | Description |
| --- | --- |
| **Ring topology** | Cassandra distributes data across nodes in a hash ring |
| **Replication Factor** | Number of copies of each piece of data (RF=3 means 3 copies) |
| **Consistency Level** | How many replicas must respond for a read/write to succeed |
| **ONE** | Only 1 replica needed -- fastest, lowest consistency |
| **QUORUM** | Majority of replicas needed -- strong consistency, tolerates failures |
| **ALL** | All replicas needed -- strongest consistency, zero fault tolerance |
| **Partition Key** | Determines which node stores the data -- critical for performance |
| **Hinted Handoff** | Mechanism to deliver missed writes to a node that was temporarily down |

## Conclusions

1. **Cassandra is designed for fault tolerance.** With RF=3, losing
   one node has zero impact on reads and writes at CL=ONE or QUORUM.
   This is fundamentally different from MySQL where losing the primary
   halts all writes.

2. **Consistency is a dial, not a switch.** CL=ONE is fast but risks
   stale reads. CL=QUORUM is the sweet spot for most production
   workloads. CL=ALL gives maximum consistency but any single node
   failure makes the entire system unavailable.

3. **Partition key design determines everything.** A bad partition key
   creates hotspots and forces expensive full-cluster scans. A good
   partition key distributes data evenly and makes queries hit a
   single node. In Cassandra, you design the schema around your
   queries, not the other way around.

## Next Steps

- [Lab 10A -- MySQL](../mysql/LAB-MYSQL.md) -- compare with relational
  replication and ACID transactions
- [Lab 10B -- MongoDB](../mongodb/LAB-MONGODB.md) -- compare with
  document store replication and consistency
