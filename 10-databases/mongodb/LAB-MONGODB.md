# Lab 10B: MongoDB Replica Set, Consistency, and Schema Design

![MongoDB](https://img.shields.io/badge/MongoDB-%2347A248.svg?style=for-the-badge&logo=mongodb&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-%232496ED.svg?style=for-the-badge&logo=docker&logoColor=white)

## Overview

This lab explores three database scalability mechanisms using MongoDB:
replica set replication with automatic failover, tunable read/write
concerns for consistency control, and schema design trade-offs between
normalized and denormalized documents. Students work with a university
enrollment dataset across a three-node MongoDB replica set.

## Learning Objectives

- Deploy and verify a MongoDB replica set with three nodes
- Observe replication by writing to the primary and reading from
  secondaries
- Compare read and write concern levels and their consistency guarantees
- Contrast normalized (multi-collection lookups) vs denormalized
  (embedded) schema design using explain plans

## Prerequisites

- **Docker Desktop** installed and running
- Basic familiarity with JSON documents
- No cloud account required (Option A) or AWS Academy credentials
  (Option B)

## Choose Your Environment

| Environment | What You Need | Setup |
| --- | --- | --- |
| **Option A: Local** | Docker Desktop + terminal | `./setup.sh` |
| **Option B: EC2** | Browser + SSH client | Upload `cloudformation.yaml` via AWS Console |

### Option A: Local Setup

```bash
cd 10-databases/mongodb
chmod +x setup.sh cleanup.sh
./setup.sh
```

Then skip to **Task 1** below.

### Option B: EC2 Setup (AWS Academy)

1. Download `cloudformation.yaml` from this directory
2. In the AWS Console, go to **CloudFormation** > **Create stack**
3. Upload the template, name it `lab10b-mongodb`, click **Submit**
4. Wait ~3 minutes, find the **PublicIP** in Outputs
5. SSH in:

```bash
chmod 400 labsuser.pem
ssh -i labsuser.pem ec2-user@YOUR_PUBLIC_IP
ls ~/LAB_READY
cd ~/system-design-course/10-databases/mongodb
```

---

## Task 1: Verify the Replica Set

### Step 1.1: Check replica set status

```bash
docker exec mongo1 mongosh --quiet --eval "rs.status().members.forEach(
  m => print(m.name + ' -> ' + m.stateStr)
)"
```

Expected output shows one PRIMARY and two SECONDARY nodes.

### Step 1.2: Verify seed data

```bash
docker exec mongo1 mongosh --quiet --eval "
use('university');
print('Students: ' + db.students.countDocuments());
print('Courses: ' + db.courses.countDocuments());
print('Enrollments: ' + db.enrollments.countDocuments());
"
```

Expected: 10 students, 4 courses, 10 enrollments.

> **Question:** What happens if the PRIMARY node goes down?
>
> **Hint:** MongoDB replica sets automatically elect a new primary
> from the remaining secondaries.

---

## Task 2: Replication in Action

### Step 2.1: Write to the primary

```bash
docker exec mongo1 mongosh --quiet --eval "
use('university');
db.students.insertOne({
  name: 'Zoe Adams',
  email: 'zoe@university.edu',
  major: 'Engineering'
});
print('Inserted on primary.');
"
```

### Step 2.2: Read from a secondary

```bash
docker exec mongo2 mongosh --quiet --eval "
db.getMongo().setReadPref('secondary');
use('university');
const zoe = db.students.findOne({ name: 'Zoe Adams' });
print('Found on secondary: ' + zoe.name + ' (' + zoe.major + ')');
"
```

The document replicated from mongo1 (primary) to mongo2 (secondary).

### Step 2.3: Verify secondaries reject direct writes

```bash
docker exec mongo2 mongosh --quiet --eval "
use('university');
try {
  db.students.insertOne({ name: 'Test', email: 'test@u.edu', major: 'X' });
} catch(e) {
  print('Error: ' + e.message);
}
"
```

Expected: error about not being primary.

> **Question:** How does MongoDB replication differ from MySQL
> replication?
>
> **Hint:** Think about automatic failover. MySQL requires manual
> promotion; MongoDB does it automatically via election.

---

## Task 3: Tunable Consistency

### Step 3.1: Write with w:1 (acknowledge from primary only)

```bash
docker exec mongo1 mongosh --quiet --eval "
use('university');
const start = Date.now();
db.courses.insertOne(
  { code: 'BIO101', title: 'Biology I', capacity: 30, enrolled: 0 },
  { writeConcern: { w: 1 } }
);
print('w:1 took ' + (Date.now() - start) + 'ms');
"
```

### Step 3.2: Write with w:majority (acknowledge from majority)

```bash
docker exec mongo1 mongosh --quiet --eval "
use('university');
const start = Date.now();
db.courses.insertOne(
  { code: 'CHEM101', title: 'Chemistry I', capacity: 25, enrolled: 0 },
  { writeConcern: { w: 'majority' } }
);
print('w:majority took ' + (Date.now() - start) + 'ms');
"
```

Compare the two timings. `w:majority` waits for 2 of 3 nodes to
acknowledge, so it takes longer but guarantees the write survives a
single node failure.

### Step 3.3: Read with different concerns

```bash
docker exec mongo1 mongosh --quiet --eval "
use('university');
// Read from local -- fastest, may read uncommitted data
let result = db.courses.find({ code: 'BIO101' })
  .readConcern('local').toArray();
print('readConcern local: ' + result.length + ' result(s)');

// Read majority -- only returns data committed to majority
result = db.courses.find({ code: 'CHEM101' })
  .readConcern('majority').toArray();
print('readConcern majority: ' + result.length + ' result(s)');
"
```

> **Question:** When would you use `w:1` instead of `w:majority`?
>
> **Hint:** Think about use cases where speed matters more than
> durability -- logging, analytics, non-critical data.

---

## Task 4: Schema Design -- Normalized vs Denormalized

### Step 4.1: Query normalized data (3 collections + lookup)

Fetch a student with their enrolled courses using `$lookup` (join):

```bash
docker exec mongo1 mongosh --quiet --eval "
use('university');
const result = db.students.aggregate([
  { \$match: { name: 'Alice Johnson' } },
  { \$lookup: {
      from: 'enrollments',
      localField: '_id',
      foreignField: 'studentId',
      as: 'enrollments'
  }},
  { \$lookup: {
      from: 'courses',
      localField: 'enrollments.courseId',
      foreignField: '_id',
      as: 'courses'
  }},
  { \$project: { name: 1, 'courses.code': 1, 'courses.title': 1 } }
]).toArray();
printjson(result);
"
```

### Step 4.2: Query denormalized data (single collection)

The same information, but embedded in a single document:

```bash
docker exec mongo1 mongosh --quiet --eval "
use('university');
const result = db.students_denormalized.findOne(
  { name: 'Alice Johnson' },
  { name: 1, enrollments: 1 }
);
printjson(result);
"
```

### Step 4.3: Compare with explain

```bash
docker exec mongo1 mongosh --quiet --eval "
use('university');
// Normalized: aggregation explain
const norm = db.students.explain('executionStats').aggregate([
  { \$match: { name: 'Alice Johnson' } },
  { \$lookup: {
      from: 'enrollments',
      localField: '_id',
      foreignField: 'studentId',
      as: 'enrollments'
  }}
]);
print('Normalized stages: ' + norm.stages.length);
print('Docs examined: ' + norm.stages[0].\$cursor.executionStats.totalDocsExamined);

// Denormalized: simple find explain
const denorm = db.students_denormalized.find(
  { name: 'Alice Johnson' }
).explain('executionStats');
print('Denormalized docs examined: ' +
  denorm.executionStats.totalDocsExamined);
"
```

The denormalized query examines fewer documents because all data is
in a single collection -- no joins needed.

> **Question:** What is the downside of denormalization?
>
> **Hint:** If a course title changes, you must update it in every
> student document that embeds it, not just one place.

---

## Cleanup

```bash
./cleanup.sh
```

For EC2, also delete the CloudFormation stack in the AWS Console.

## Troubleshooting

| Issue | Cause | Fix |
| --- | --- | --- |
| `MongoServerError: not primary` | Writing to a secondary | Connect to mongo1 (the initial primary) |
| Replica set shows no primary | Election not complete | Wait 10-15 seconds, re-check `rs.status()` |
| `readPref` has no effect | Must call before query | Call `db.getMongo().setReadPref()` first |
| `$lookup` returns empty arrays | Data not seeded | Re-run `setup.sh` |
| Container exits immediately | Port conflict | Check `docker ps` for conflicts on 27017-27019 |

## Key Concepts

| Concept | Description |
| --- | --- |
| **Replica Set** | A group of MongoDB nodes that maintain the same data, with automatic failover |
| **Primary** | The node that accepts all write operations |
| **Secondary** | Nodes that replicate data from the primary; can serve reads |
| **Write Concern** | How many nodes must acknowledge a write before it is considered successful |
| **Read Concern** | What level of data consistency is guaranteed for read operations |
| **$lookup** | MongoDB's aggregation operator for joining data across collections |
| **Denormalization** | Embedding related data in a single document to avoid joins |

## Conclusions

1. **Replica sets provide automatic failover.** Unlike MySQL where
   promoting a replica is manual, MongoDB automatically elects a new
   primary when one fails.

2. **Write concern is a speed vs safety trade-off.** `w:1` is fast
   but risks data loss if the primary crashes before replicating.
   `w:majority` is slower but survives single-node failures.

3. **Denormalization trades write complexity for read speed.** Embedding
   related data eliminates joins and reduces query time, but updates
   become harder when the same data appears in multiple documents.

## Next Steps

- [Lab 10A -- MySQL](../mysql/LAB-MYSQL.md) -- compare with relational
  replication and ACID transactions
- [Lab 10C -- Cassandra](../cassandra/LAB-CASSANDRA.md) -- compare
  with wide-column store and partition key design
