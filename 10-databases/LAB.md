# Lab 10: Database Scalability

## Main Lab (Interactive Visualizer)

The primary lab for this module is an interactive web visualizer
connected to a live MySQL primary-replica cluster. It covers three
scalability mechanisms through animated diagrams, real SQL execution,
and a built-in SQL console.

| Lab | What It Covers | Time |
| --- | --- | --- |
| [Interactive Visualizer](visualizer/LAB-VISUALIZER.md) | Replication, ACID transactions, indexing -- all via browser | ~45 min |

```bash
cd 10-databases/visualizer
./setup.sh
# Open http://localhost:8081
```

## Optional Labs (CLI-based, deeper dive)

For students who want to go deeper with other database paradigms,
three optional CLI labs use the same university enrollment data model:

| Lab | Database | Scalability Mechanisms | Time |
| --- | --- | --- | --- |
| [10A: MySQL](mysql/LAB-MYSQL.md) | MySQL 8 (Relational) | GTID replication, ACID transactions, indexing | ~30 min |
| [10B: MongoDB](mongodb/LAB-MONGODB.md) | MongoDB 7 (Document) | Replica set, read/write concerns, denormalization | ~30 min |
| [10C: Cassandra](cassandra/LAB-CASSANDRA.md) | Cassandra 4.1 (Wide-column) | Multi-node ring, tunable consistency, partition keys | ~30 min |

## Scalability Mechanisms Compared

| Mechanism | MySQL | MongoDB | Cassandra |
| --- | --- | --- | --- |
| **Replication** | Primary + replica (GTID) | 3-node replica set | 3-node ring (RF=3) |
| **Failover** | Manual promotion | Automatic election | No single point of failure |
| **Consistency** | ACID transactions | Tunable write/read concern | Tunable CL (ONE/QUORUM/ALL) |
| **Schema** | Rigid, normalized | Flexible, denormalized | Query-driven, partition keys |
| **Scaling reads** | Add read replicas | Read from secondaries | Read from any node |
| **Scaling writes** | Vertical only | Sharding (manual) | Add nodes to ring |

## Shared Data Model

All labs use the same university enrollment scenario:

- **Students** -- 10 students with name, email, major
- **Courses** -- 4 courses with code, title, capacity
- **Enrollments** -- student-to-course relationships

This lets you compare how the same data is modeled differently in
each paradigm (tables with foreign keys vs embedded documents vs
partition-key-driven tables).

## Environment Options

Each lab supports two environments:

| Environment | What You Need | Setup |
| --- | --- | --- |
| **Local** | Docker Desktop | `./setup.sh` in the lab directory |
| **EC2** | Browser + SSH | Upload `cloudformation.yaml` via AWS Console |

Run one lab at a time to avoid port conflicts and resource contention.
