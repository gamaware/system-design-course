# Lab audit

This document records which labs run end to end, and which ones needed a fix because something outside
the course changed underneath them.

## Why this audit exists

Labs pin third-party images, packages and links. When an upstream project retires an image, raises its
memory footprint or moves a URL, a lab that worked last semester stops working, and the student sees a
failure that teaches nothing. This audit runs every lab and separates that class of breakage from the
exercises themselves.

## Scope

Labs that run on Docker were started with their own `setup.sh`, driven through their tasks with the
real commands, and torn down with their `cleanup.sh`. That covers modules 03, 07, 09, 10 and 11.

Labs that deploy to AWS were checked statically, never deployed: `cfn-lint`, `terraform validate`,
dependency resolution and link checks. That covers modules 01, 02, 04 and 08. The status table below
says which treatment each module received.

## Status

| Module | Lab                                    | Runs         | Upstream fix applied |
|--------|----------------------------------------|--------------|----------------------|
| 01     | Introduction, horizontal scalability   | static check | Node.js requirement  |
| 02     | Compute, EC2 basics                    | static check | none                 |
| 03     | Load balancing with HAProxy            | yes          | none                 |
| 04     | DNS with dig and BIND9                 | static check | RFC index link       |
| 05     | Distributed systems, high availability | no lab yet   | not applicable       |
| 06     | Security, HTTPS, OAuth 2.0, Keycloak   | yes          | none                 |
| 07     | Networking                             | yes          | none                 |
| 08     | Cloud networking, VPC                  | static check | none                 |
| 09     | Distributed file systems               | yes          | MinIO images         |
| 10     | Databases, all four sub-labs           | yes          | none                 |
| 11     | Caching with Redis                     | yes          | Redis version        |
| 12     | Proxies                                | no lab yet   | not applicable       |
| 13     | Solutions architecture                 | no lab yet   | not applicable       |
| 14     | Distributed messaging                  | no lab yet   | not applicable       |
| 15     | Serverless                             | no lab yet   | not applicable       |
| 16     | Artificial intelligence                | no lab yet   | not applicable       |
| 17     | Containers                             | no lab yet   | not applicable       |

## Fixes applied

### Lab 11, Redis eviction

Task 6 lowers `maxmemory` to 1 MB and asks the student to watch the `allkeys-lru` policy evict keys.
The `redis:7-alpine` tag now resolves to 7.4, which reports 1,044,520 bytes of used memory on an empty
instance. That already sits at the 1 MB ceiling, so every write returns `OOM command not allowed` and
the server never evicts anything. Measured on both versions with the task's own configuration:

| Image                       | Memory when empty | 200 writes               | Keys evicted |
|-----------------------------|-------------------|--------------------------|--------------|
| `redis:7-alpine` (7.4.11)   | 1,044,520 bytes   | 0 accepted, 200 rejected | 0            |
| `redis:7.2-alpine` (7.2.16) | 961,992 bytes     | 200 accepted             | 71           |

The compose file now pins `redis:7.2-alpine`. Because 7.4 writes an RDB file that 7.2 refuses to load,
`setup.sh` also starts the stack with `--renew-anon-volumes`, so a student who already ran the lab
does not meet `Can't handle RDB format version 12` on the next run.

### Lab 01, Node.js requirement

The README asked for Node.js 14 or later. The `jsii` runtime that AWS CDK depends on now declares
`node >= 20.16.0`, and Node 20 has left support, so the README asks for Node.js 22 or later.

### Lab 04, RFC index link

`https://www.ietf.org/rfc/` returns 404 and redirects to another address that also returns 404. The
README now links `https://www.rfc-editor.org/standards`.

### Lab 09, MinIO images

MinIO removed `minio/minio` and `minio/mc` from Docker Hub when the project became AIStor, so the lab
failed during `docker compose up`. Both services now use the `bitnamilegacy` images.

## Pinning risk

A floating tag moves under the lab without warning, which is exactly how the Redis breakage reached
the student. The lab images that floated on a major or minor tag are now pinned to an exact version:
`mysql:8.4.11`, `mongo:7.0.45`, `cassandra:4.1.12`, `python:3.13.16-slim-trixie`,
`maven:3.9.16-eclipse-temurin-21`, `eclipse-temurin:21.0.12.1_1-jre-noble`, `gcc:14.3.0-bookworm`,
the .NET `8.0.426` SDK and `8.0.32` runtime, and Keycloak `26.8.1`. The `alpine:latest` base image
lives only in the third-party `ecsdemo-crystal` application, which this audit does not modify.

`redis:7.2-alpine` still tracks patch releases inside 7.2. That is a deliberate trade: patch releases
carry security fixes and keep the memory footprint that Task 6 depends on, while the jump that broke
the lab was a minor one, from 7.2 to 7.4.

## How to repeat this audit

```bash
cd NN-topic
./setup.sh
# drive the tasks in LAB.md or README.md with the real commands
./cleanup.sh
docker ps -a
```
