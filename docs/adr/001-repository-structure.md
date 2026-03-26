# ADR-001: Repository Structure and Module Naming

## Status

Accepted

## Context

The course "Scalable Systems Design" (ITE3901) covers 17 topics across an 18-week semester.
Each topic may include hands-on labs, demos, or theoretical content. The repository needs a
consistent structure that maps directly to the syllabus while remaining navigable for students.

## Decision

- Each module is a top-level directory named `NN-topic-name` where `NN` is the two-digit
  module number matching the syllabus order (01 through 17).
- Directory names use lowercase kebab-case with no spaces.
- Topic names in directories reflect both the syllabus topic and the primary technology used
  in the lab (e.g., `03-load-balancing-haproxy`, `06-security-https-oauth2-keycloak`).
- Every module directory contains a `README.md` with lab instructions or a placeholder for
  modules under development.
- Shared documentation lives under `docs/` (e.g., ADRs).
- GitHub configuration lives under `.github/` (workflows, templates, dependabot).

### Module mapping

| Module | Syllabus Topic | Directory |
| ------ | ------------- | --------- |
| 01 | Introduction and Horizontal Scalability | `01-introduction-horizontal-scalability` |
| 02 | Compute | `02-compute-ec2-basics` |
| 03 | Load Balancing | `03-load-balancing-haproxy` |
| 04 | DNS | `04-dns-dig-bind9` |
| 05 | Key Characteristics of Distributed Systems | `05-distributed-systems-high-availability` |
| 06 | Security | `06-security-https-oauth2-keycloak` |
| 07 | Networking | `07-networking` |
| 08 | Cloud Networking | `08-cloud-networking-vpc` |
| 09 | Distributed File Systems | `09-distributed-file-systems` |
| 10 | Databases | `10-databases` |
| 11 | Caching and CDN | `11-caching-cdn` |
| 12 | Proxies | `12-proxies` |
| 13 | Solutions Architecture | `13-solutions-architecture` |
| 14 | Distributed Messaging | `14-distributed-messaging` |
| 15 | Serverless | `15-serverless` |
| 16 | Artificial Intelligence | `16-artificial-intelligence` |
| 17 | Containers | `17-containers` |

## Consequences

- Students can navigate the repository in syllabus order.
- New modules are added by creating a directory with the next available number.
- The numbered prefix ensures correct sort order in file explorers and GitHub.
- Renaming a module requires updating the README, PR template, and this ADR.
