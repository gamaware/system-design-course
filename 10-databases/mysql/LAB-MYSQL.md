# Lab 10A: MySQL Replication, ACID, and Indexing

![MySQL](https://img.shields.io/badge/MySQL-%234479A1.svg?style=for-the-badge&logo=mysql&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-%232496ED.svg?style=for-the-badge&logo=docker&logoColor=white)

## Overview

This lab explores three database scalability mechanisms using MySQL:
GTID-based replication (primary-replica), ACID transactions with
rollback behavior, and query optimization through indexing. Students
work with a university enrollment dataset across a two-node MySQL
cluster running in Docker.

## Learning Objectives

- Configure and verify MySQL GTID-based primary-replica replication
- Observe replication lag and understand its implications
- Execute ACID transactions and observe rollback on constraint violations
- Use EXPLAIN to analyze query execution plans before and after indexing

## Prerequisites

- **Docker Desktop** installed and running
- Basic SQL knowledge (SELECT, INSERT, UPDATE)
- No cloud account required (Option A) or AWS Academy credentials
  (Option B)

## Choose Your Environment

| Environment | What You Need | Setup |
| --- | --- | --- |
| **Option A: Local** | Docker Desktop + terminal | `./setup.sh` |
| **Option B: EC2** | Browser + SSH client | Upload `cloudformation.yaml` via AWS Console |

Both options run the same Docker containers and the same 4 tasks.

### Option A: Local Setup

```bash
cd 10-databases/mysql
chmod +x setup.sh cleanup.sh
./setup.sh
```

Then skip to **Task 1** below.

### Option B: EC2 Setup (AWS Academy)

1. Download `cloudformation.yaml` from this directory
1. In the AWS Console, go to **CloudFormation** > **Create stack**
1. Upload the template, name it `lab10a-mysql`, click **Submit**
1. Wait ~3 minutes for the stack to complete
1. Find the **PublicIP** in the Outputs tab
1. SSH in:

   ```bash
   chmod 400 labsuser.pem
   ssh -i labsuser.pem ec2-user@YOUR_PUBLIC_IP
   ```

1. Wait for setup to complete:

   ```bash
   ls ~/LAB_READY
   cd ~/system-design-course/10-databases/mysql
   ```

Then continue with **Task 1** below.

---

## Task 1: Verify the Cluster

Start the environment and confirm both MySQL nodes are running with
active replication.

### Step 1.1: Check containers

```bash
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
```

Expected output shows `mysql-primary` and `mysql-replica` both healthy.

### Step 1.2: Connect to the primary

```bash
docker exec -it mysql-primary mysql -u root -prootpass university
```

Verify the seed data:

```sql
SELECT COUNT(*) AS total_students FROM students;
SELECT COUNT(*) AS total_enrollments FROM enrollments;
```

Expected: 10 students, 10 enrollments. Type `exit` to leave.

### Step 1.3: Check replication status

```bash
docker exec mysql-replica mysql -u root -prootpass \
    -e "SHOW REPLICA STATUS\G" 2>/dev/null | grep -E \
    "Replica_IO_Running|Replica_SQL_Running|Seconds_Behind"
```

Expected output:

```text
         Replica_IO_Running: Yes
        Replica_SQL_Running: Yes
      Seconds_Behind_Source: 0
```

> **Question:** What do the IO and SQL threads do in MySQL replication?
>
> **Hint:** One fetches the binary log from the primary, the other
> replays it locally.

---

## Task 2: Replication in Action

Write data to the primary and observe it appear on the replica.

### Step 2.1: Insert on the primary

```bash
docker exec mysql-primary mysql -u root -prootpass university -e "
INSERT INTO students (name, email, major)
VALUES ('Zoe Adams', 'zoe@university.edu', 'Engineering');
"
```

### Step 2.2: Read from the replica

```bash
docker exec mysql-replica mysql -u root -prootpass university -e "
SELECT student_id, name, major FROM students WHERE name = 'Zoe Adams';
"
```

The row should appear. Replication propagated the write automatically.

### Step 2.3: Check replication lag

```bash
docker exec mysql-replica mysql -u root -prootpass \
    -e "SHOW REPLICA STATUS\G" 2>/dev/null \
    | grep "Seconds_Behind_Source"
```

Expected: `Seconds_Behind_Source: 0` (near-instant in a local setup).

### Step 2.4: Verify the replica is read-only

```bash
docker exec mysql-replica mysql -u root -prootpass university -e "
INSERT INTO students (name, email, major)
VALUES ('Test User', 'test@university.edu', 'Test');
"
```

Expected error:

```text
ERROR 1290 (HY000): The MySQL server is running with the
--super-read-only option so it cannot execute this statement
```

> **Question:** Why would you configure a replica as read-only?
>
> **Hint:** Think about what happens if clients accidentally write
> to the replica instead of the primary.

---

## Task 3: ACID Transactions

Test atomicity and isolation by transferring a student between courses
inside a transaction.

### Step 3.1: Check current enrollment counts

```bash
docker exec mysql-primary mysql -u root -prootpass university -e "
SELECT c.code, c.title, c.enrolled
FROM courses c ORDER BY c.code;
"
```

### Step 3.2: Successful transaction (transfer enrollment)

Transfer student Alice (ID 1) from CS101 to PHYS101:

```bash
docker exec mysql-primary mysql -u root -prootpass university -e "
START TRANSACTION;

DELETE FROM enrollments WHERE student_id = 1 AND course_id = 1;
UPDATE courses SET enrolled = enrolled - 1 WHERE course_id = 1;

INSERT INTO enrollments (student_id, course_id) VALUES (1, 4);
UPDATE courses SET enrolled = enrolled + 1 WHERE course_id = 4;

COMMIT;
"
```

Verify the counts changed:

```bash
docker exec mysql-primary mysql -u root -prootpass university -e "
SELECT c.code, c.enrolled FROM courses c WHERE c.code IN ('CS101', 'PHYS101');
"
```

Expected: CS101 has 3, PHYS101 has 3.

### Step 3.3: Failed transaction (constraint violation)

Try to enroll Alice in CS201 twice (violates unique constraint):

```bash
docker exec mysql-primary mysql -u root -prootpass university -e "
START TRANSACTION;
INSERT INTO enrollments (student_id, course_id) VALUES (1, 2);
INSERT INTO enrollments (student_id, course_id) VALUES (1, 2);
COMMIT;
" 2>&1 || true
```

The second INSERT fails due to the unique constraint. Check that Alice
has exactly one enrollment in CS201:

```bash
docker exec mysql-primary mysql -u root -prootpass university -e "
SELECT COUNT(*) AS alice_cs201
FROM enrollments WHERE student_id = 1 AND course_id = 2;
"
```

> **Question:** What ACID property ensures that both the DELETE and
> INSERT in step 3.2 either both succeed or both fail?
>
> **Hint:** Think about what happens if the server crashes between
> the DELETE and the INSERT.

---

## Task 4: Indexing for Query Performance

Compare query performance with and without an index using the
`access_log` table (10,000 rows).

### Step 4.1: Update table statistics and run a query without an index

First, update MySQL's statistics so EXPLAIN shows accurate row counts:

```bash
docker exec mysql-primary mysql -u root -prootpass university -e "
ANALYZE TABLE access_log;
"
```

Now run EXPLAIN on a query with no index:

```bash
docker exec mysql-primary mysql -u root -prootpass university -e "
EXPLAIN SELECT * FROM access_log
WHERE student_id = 3 AND resource = 'resource-10'\G
"
```

Look at the `rows` field. Without an index, MySQL scans all ~10,000
rows (full table scan). The `type` shows `ALL` (full scan).

### Step 4.2: Add a composite index

```bash
docker exec mysql-primary mysql -u root -prootpass university -e "
CREATE INDEX idx_student_resource ON access_log (student_id, resource);
"
```

### Step 4.3: Re-run the same query with EXPLAIN

```bash
docker exec mysql-primary mysql -u root -prootpass university -e "
EXPLAIN SELECT * FROM access_log
WHERE student_id = 3 AND resource = 'resource-10'\G
"
```

Compare the `rows` field. With the index, MySQL scans far fewer rows
(typically under 100 instead of 10,000).

### Step 4.4: Verify the index replicated

```bash
docker exec mysql-replica mysql -u root -prootpass university -e "
SHOW INDEX FROM access_log WHERE Key_name = 'idx_student_resource'\G
"
```

The index exists on the replica too -- DDL changes replicate
automatically.

> **Question:** Why does over-indexing hurt write performance?
>
> **Hint:** Every INSERT and UPDATE must also update all indexes on
> that table.

---

## Cleanup

```bash
./cleanup.sh
```

For EC2, also delete the CloudFormation stack:

1. Go to **CloudFormation** in the AWS Console
2. Select `lab10a-mysql`, click **Delete**

## Troubleshooting

| Issue | Cause | Fix |
| --- | --- | --- |
| `Can't connect to MySQL server` | Container not ready | Wait 30s, retry |
| Replica shows `Connecting` | Primary not reachable | Check `docker compose logs mysql-replica` |
| `Seconds_Behind_Source: NULL` | Replication not started | Re-run `setup.sh` |
| `super-read-only` on INSERT | Writing to replica | Connect to primary (port 3306) instead |
| EXPLAIN shows full scan after index | Wrong column order | Ensure index matches query WHERE clause |

## Key Concepts

| Concept | Description |
| --- | --- |
| **GTID Replication** | Global Transaction IDs let replicas track exactly which transactions they have applied |
| **Primary-Replica** | One node handles writes, replicas handle reads for horizontal read scaling |
| **Replication Lag** | Delay between a write on the primary and its appearance on replicas |
| **ACID** | Atomicity, Consistency, Isolation, Durability -- guarantees for relational transactions |
| **EXPLAIN** | Shows the query execution plan: which indexes are used and how many rows are scanned |
| **Composite Index** | An index on multiple columns, effective when queries filter on those columns together |

## Conclusions

1. **Replication scales reads, not writes.** Adding replicas lets you
   distribute SELECT queries but all writes still go to one primary.

2. **ACID transactions prevent partial updates.** The enrollment
   transfer either fully succeeds or fully rolls back -- no
   inconsistent state.

3. **Indexes dramatically reduce query cost.** A composite index
   turned a 10,000-row scan into a targeted lookup. But each index
   adds overhead to writes.

## Next Steps

- [Lab 10B -- MongoDB](../mongodb/LAB-MONGODB.md) -- compare with
  document store replication and tunable consistency
- [Lab 10C -- Cassandra](../cassandra/LAB-CASSANDRA.md) -- compare
  with wide-column store and partition key design
