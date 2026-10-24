# System Design Course

![AWS](https://img.shields.io/badge/AWS-%23FF9900.svg?style=for-the-badge&logo=amazon-aws&logoColor=white)
![Python](https://img.shields.io/badge/Python-3670A0?style=for-the-badge&logo=python&logoColor=ffdd54)
![Bash](https://img.shields.io/badge/Bash-%23121011.svg?style=for-the-badge&logo=gnu-bash&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-%230db7ed.svg?style=for-the-badge&logo=docker&logoColor=white)
![CDK](https://img.shields.io/badge/AWS_CDK-%23FF9900.svg?style=for-the-badge&logo=amazon-aws&logoColor=white)
![IaC](https://img.shields.io/badge/IaC-%23326CE5.svg?style=for-the-badge&logoColor=white)
![Scalability][badge-scalability]

## 🚀 Scalable Systems Design - ITESO

Course materials and demos for Scalable Systems Design.

### Canvas equivalence

The folders follow the order of the topics, while Canvas numbers labs in the order they are
due. Use this table to find the folder for each Canvas item.

| Folder | Canvas module | Canvas item |
| --- | --- | --- |
| [01](./01-introduction-horizontal-scalability) | Módulo 1: Introducción | 🎬 Demo (no report) |
| [02](./02-compute-ec2-basics) | Módulo 2: Cómputo | 🧪 Lab 1 |
| [03](./03-load-balancing-haproxy) | Módulo 3: Balanceo de Carga | Demo for Actividad 2 |
| [04](./04-dns-dig-bind9) | Módulo 4: DNS | 🧪 Lab 2 |
| [05](./05-distributed-systems-high-availability) | Módulo 5: Características clave | Optional (🧪 Lab 3 is in AWS Academy) |
| [06](./06-security-https-oauth2-keycloak) | Módulo 6: Seguridad | 🧪 Lab 4 |
| [07](./07-networking) | Módulo 7: Redes | 🧪 Lab 5 |
| [08](./08-cloud-networking-vpc) | Módulo 7: Redes | Follow-up linked from 🧪 Lab 5 |
| [09](./09-distributed-file-systems) | Módulo 8: Sistemas de Archivos Distribuidos | 🧪 Lab 6 |
| [10](./10-databases) | Módulo 9: Bases de Datos | 🧪 Lab 7 |
| [11](./11-caching) | Módulo 10: Caché y CDN | 🧪 Lab 8 |
| [12](./12-proxies) | Módulo 11: Proxies | 🧪 Lab 9 |
| [13](./13-solutions-architecture) | Módulo 14: Arquitectura de Soluciones | Actividad 10 (in class) |
| [14](./14-distributed-messaging) | Módulo 12: Sistema de Mensajería Distribuida | 🧪 Lab 10 |
| [15](./15-serverless) | Módulo 13: Serverless | Lab (Canvas number pending) |
| [16](./16-artificial-intelligence) | Módulo 16: Inteligencia Artificial | Coming soon |
| [17](./17-containers) | Módulo 15: Contenedores | Coming soon |

### 📚 Course Modules

#### [01 — Introduction: Horizontal Scalability](./01-introduction-horizontal-scalability)

Hands-on demo demonstrating horizontal scaling with AWS ECS Fargate, Application Load Balancer, and
autoscaling. Students learn to:

- Deploy containerized microservices using AWS CDK (Infrastructure as Code)
- Configure Application Load Balancers for traffic distribution
- Implement CPU-based autoscaling policies
- Monitor and observe scaling behavior with CloudWatch
- Perform load testing to trigger autoscaling events

**Technologies**: AWS ECS Fargate, AWS CDK (Python), Application Load Balancer, CloudWatch, Docker,
Ruby on Rails (frontend), Node.js, Crystal

**Key Concepts**: Horizontal scaling, load balancing, autoscaling, containerization, infrastructure as code, observability

#### [02 — Compute: EC2 Basics](./02-compute-ec2-basics)

Foundational lab teaching Amazon EC2 fundamentals through hands-on exercises. Students learn to:

- Understand key EC2 components (AMI, instance type, key pair, security group, VPC)
- Create and manage SSH key pairs for secure access
- Launch and configure EC2 instances
- Connect to Linux instances via SSH
- Navigate the EC2 console and view instance details
- Manage instance lifecycle (start, stop, terminate)
- Understand EC2 pricing and Free Tier eligibility

**Technologies**: AWS EC2, Amazon Linux 2023, SSH, Security Groups

**Key Concepts**: Virtual servers, SSH authentication, security groups, instance lifecycle, cloud computing basics

#### [03 — Load Balancing: HAProxy](./03-load-balancing-haproxy)

Lab exploring load balancing algorithms with HAProxy on AWS EC2. Students learn to:

- Configure HAProxy as a load balancer
- Test and compare 6 different load balancing algorithms (Round Robin, Least Connections, Random,
  Weighted, Source Hash, URI Hash)
- Implement health checks and automatic failover
- Monitor load balancer statistics and performance
- Understand session persistence and content-based routing

**Technologies**: HAProxy, Python HTTP Server, AWS EC2, Linux

**Key Concepts**: Load balancing algorithms, health checks, failover, session persistence, high availability

#### [04 — DNS: dig and BIND9](./04-dns-dig-bind9)

Lab teaching DNS fundamentals through practical exercises. Students learn to:

- Use `dig` to query and diagnose DNS records
- Explore different DNS record types (A, AAAA, CNAME, MX, NS, TXT, PTR)
- Configure BIND9 as an authoritative DNS server
- Implement DNS-based load balancing with Round Robin
- Compare DNS load balancing vs HAProxy load balancing
- Validate DNS configurations with diagnostic tools

**Technologies**: BIND9, dig, AWS EC2, Linux

**Key Concepts**: DNS resolution, DNS record types, authoritative DNS servers, DNS load balancing, Round Robin

#### [05 — Key Characteristics of Distributed Systems: High Availability](./05-distributed-systems-high-availability)

#### [06 — Security: HTTPS, OAuth 2.0 and Keycloak](./06-security-https-oauth2-keycloak)

Lab exploring OAuth 2.0 authentication with Keycloak as an Identity and Access Management solution. Students learn to:

- Deploy Keycloak on EC2 with SSL/TLS encryption
- Configure OAuth 2.0 realms, clients, and users
- Implement JWT token-based authentication
- Build a Flask API with OAuth 2.0 token validation
- Understand authentication vs authorization in distributed systems
- Compare IAM solutions (Keycloak, AWS Cognito, Auth0, Firebase)
- Test security patterns and token lifecycle management

**Technologies**: Keycloak, Docker, Python Flask, OAuth 2.0, OpenID Connect, JWT, SSL/TLS, AWS EC2

**Key Concepts**: OAuth 2.0, OpenID Connect, JWT tokens, token introspection, identity federation,
multi-tenancy, distributed authentication, API security

#### [07 — Networking](./07-networking)

Lab teaching Linux networking fundamentals through a Docker-based troubleshooting scenario, with an
optional AWS VPC extension. Students learn to:

- Inspect network interfaces, IP addresses, and routing tables
- Diagnose broken network configurations (downed interfaces, missing routes)
- Fix network issues using `ip link` and `ip route` commands
- Use SSH to access remote systems for troubleshooting
- (Optional) Create an AWS VPC and compare Linux networking to cloud equivalents

**Technologies**: Docker, Docker Compose, Linux networking tools (ip, ping, telnet, curl), SSH, AWS VPC

**Key Concepts**: Network interfaces, routing tables, default gateways, subnets, DNS resolution,
network troubleshooting, VPC networking

#### [08 — Cloud Networking: AWS VPC](./08-cloud-networking-vpc)

Lab adapting the AWS General Immersion Day VPC Hands-on Lab into an Infrastructure as Code experience.
Students learn to:

- Deploy a VPC with public subnets and an Internet Gateway using CloudFormation
- Create security groups and key pairs using the AWS CLI
- Launch EC2 instances across multiple Availability Zones using Terraform
- Test cross-AZ connectivity with ping, curl, and SSH
- Compare declarative IaC (CloudFormation, Terraform) with imperative CLI commands

**Technologies**: AWS CloudFormation, Terraform, AWS CLI, VPC, EC2, Amazon Linux 2023

**Key Concepts**: VPC, subnets, Internet Gateway, route tables, security groups, Infrastructure as Code,
CloudFormation, Terraform, Availability Zones, cross-AZ communication

#### [09 — Distributed File Systems](./09-distributed-file-systems)

#### [10 — Databases](./10-databases)

#### [11 — Caching](./11-caching)

Lab exploring caching as a system design pattern using Redis. Students
implement four caching strategies in their choice of C++, C#, or Java and
observe eviction policies in action. Students learn to:

- Implement cache-aside, read-through, write-through, and write-back patterns
- Configure and observe LRU, LFU, and TTL eviction policies under memory pressure
- Measure cache hit vs miss performance quantitatively
- Choose appropriate caching strategies for different system requirements

**Technologies**: Redis, Docker, Docker Compose, C++ (hiredis), C# (StackExchange.Redis),
Java (Jedis)

**Key Concepts**: cache-aside, read-through, write-through, write-back, LRU eviction,
LFU eviction, TTL expiration, cache invalidation, eviction policies

#### [12 — Proxies](./12-proxies)

#### [13 — Solutions Architecture](./13-solutions-architecture)

Browser-based "complete the diagram" exercise: 9 scenarios, each on AWS, Azure, Google Cloud, and
Oracle Cloud. Students learn to:

- Map written requirements to the managed service that meets them
- Rebuild the multi-Region DNS plus load balancer pattern from Lab 04
- Compare how four cloud providers implement the same topology
- Identify services without a clean equivalent on another cloud

**Technologies**: AWS, Azure, Google Cloud, Oracle Cloud, static HTML/JavaScript site

**Key Concepts**: Requirement-driven design, managed services, multi-Region high availability,
DNS failover, cross-cloud service equivalence

#### [14 — Distributed Messaging](./14-distributed-messaging)

#### [15 — Serverless](./15-serverless)

Local lab that runs real AWS Lambda functions in Docker with the Runtime Interface Emulator,
DynamoDB Local and a small gateway in the role of API Gateway and SQS. Students learn to:

- Deploy one function at a time and read the event and context objects of a handler
- Measure cold and warm starts, timeouts, and how the memory setting changes CPU and cost
- Process SQS batches with partial failures, retries, a dead letter queue and an idempotent consumer
- Observe concurrency and throttling, and compare AWS Lambda with Azure Functions

**Technologies**: AWS Lambda (Python 3.12 base image), Lambda Runtime Interface Emulator, DynamoDB Local,
Docker, Docker Compose, Python (boto3)

**Key Concepts**: Function as a Service, execution environments, cold starts, stateless compute,
event source mappings, partial batch responses, idempotency, concurrency, throttling

#### [16 — Artificial Intelligence](./16-artificial-intelligence) _(coming soon)_

#### [17 — Containers](./17-containers) _(coming soon)_

### 👨🏫 Instructor

#### Mtro. Jorge Alejandro García Martínez

- Email: <alejandrogarcia@iteso.mx>
- Canvas: Check your semester's Canvas page for the course link

### 📅 Schedule

- **Days**: Wednesday 7:00-9:00 AM, Friday 9:00-11:00 AM
- **Location**: T216
- **Frequency**: Every semester

### 👤 Author

Created by [Alex Garcia](https://github.com/gamaware)

- [Personal Website](https://alexgarcia.info/)

[badge-scalability]: https://img.shields.io/badge/Scalability-%234285F4.svg?style=for-the-badge&logo=googlecloud&logoColor=white
