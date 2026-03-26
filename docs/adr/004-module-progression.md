# ADR-004: Module Progression and Semester Mapping

## Status

Accepted

## Context

The 18-week semester includes 17 technical topics plus evaluation weeks. Topics build on
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
8. **Week 9**: Cloud networking (AWS VPC, CloudFormation, Terraform, IaC).
9. **Week 10**: Distributed file systems.
10. **Weeks 11-12**: Databases (SQL, NoSQL, replication, sharding).
11. **Week 13**: Caching and CDN.
12. **Week 14**: Proxies (forward, reverse).
13. **Week 15**: Solutions architecture (AWS Well-Architected).
14. **Week 16**: Distributed messaging (queues, pub/sub).
15. **Week 17**: Serverless (Lambda, API Gateway).
16. **Week 18**: Artificial intelligence (LLMs, cloud AI services).
17. **Week 18**: Containers (Docker, Kubernetes deep dive).

Evaluation checkpoints:

- Partial exam after module 06 (security).
- Final exam after module 17 (containers).
- Quizzes distributed throughout the semester.

## Consequences

- Modules can be taught independently but are designed for sequential delivery.
- Labs in later modules may reference concepts from earlier ones.
- The numbering scheme allows inserting new modules by adjusting numbers, though this
  requires updating the README, PR template, and ADR-001.
