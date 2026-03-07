# ADR-004: Module Progression and Semester Mapping

## Status

Accepted

## Context

The 18-week semester includes 16 technical topics plus evaluation weeks. Topics build on
each other progressively: foundational concepts (compute, networking) precede advanced
topics (distributed messaging, serverless, containers). The repository structure must
reflect this pedagogical progression.

## Decision

The module order follows the syllabus progression:

1. **Weeks 1-2**: Introduction and horizontal scalability (ECS demo with Kubernetes/AWS Copilot).
2. **Week 3**: Compute fundamentals (EC2 basics).
3. **Week 4**: Load balancing (HAProxy lab with multiple algorithms).
4. **Week 5**: DNS (dig queries and BIND9 configuration).
5. **Week 6**: Key characteristics of distributed systems (availability, consistency,
   partition tolerance).
6. **Week 7**: Security (HTTPS, TLS certificates, OAuth 2.0, Keycloak OIDC).
7. **Week 8**: Networking (TCP/IP, traffic capture, analysis).
8. **Week 9**: Distributed file systems.
9. **Weeks 10-11**: Databases (SQL, NoSQL, replication, sharding).
10. **Week 12**: Caching and CDN.
11. **Week 13**: Proxies (forward, reverse).
12. **Week 14**: Solutions architecture (AWS Well-Architected).
13. **Week 15**: Distributed messaging (queues, pub/sub).
14. **Week 16**: Serverless (Lambda, API Gateway).
15. **Week 17**: Artificial intelligence (LLMs, cloud AI services).
16. **Week 18**: Containers (Docker, Kubernetes deep dive).

Evaluation checkpoints:

- Partial exam after module 06 (security).
- Final exam after module 16 (containers).
- Quizzes distributed throughout the semester.

## Consequences

- Modules can be taught independently but are designed for sequential delivery.
- Labs in later modules may reference concepts from earlier ones.
- The numbering scheme allows inserting new modules by adjusting numbers, though this
  requires updating the README, PR template, and ADR-001.
