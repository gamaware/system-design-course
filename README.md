# System Design Course

![AWS](https://img.shields.io/badge/AWS-%23FF9900.svg?style=for-the-badge&logo=amazon-aws&logoColor=white)
![Python](https://img.shields.io/badge/Python-3670A0?style=for-the-badge&logo=python&logoColor=ffdd54)
![Bash](https://img.shields.io/badge/Bash-%23121011.svg?style=for-the-badge&logo=gnu-bash&logoColor=white)
![CDK](https://img.shields.io/badge/AWS_CDK-%23FF9900.svg?style=for-the-badge&logo=amazon-aws&logoColor=white)
![IaC](https://img.shields.io/badge/IaC-%23326CE5.svg?style=for-the-badge&logoColor=white)
![Scalability][badge-scalability]

## 🚀 Scalable Systems Design - ITESO

Course materials and demos for Scalable Systems Design.

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
>
> Coming soon — content being migrated from AWS Academy.

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

#### [07 — Networking](./07-networking) _(coming soon)_

#### [08 — Distributed File Systems](./08-distributed-file-systems) _(coming soon)_

#### [09 — Databases](./09-databases) _(coming soon)_

#### [10 — Caching and CDN](./10-caching-cdn) _(coming soon)_

#### [11 — Proxies](./11-proxies) _(coming soon)_

#### [12 — Solutions Architecture](./12-solutions-architecture) _(coming soon)_

#### [13 — Distributed Messaging](./13-distributed-messaging) _(coming soon)_

#### [14 — Serverless](./14-serverless) _(coming soon)_

#### [15 — Artificial Intelligence](./15-artificial-intelligence) _(coming soon)_

#### [16 — Containers](./16-containers) _(coming soon)_

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

- [LinkedIn Profile](https://www.linkedin.com/in/gamaware/)
- [Personal Website](https://alexgarcia.info/)

[badge-scalability]: https://img.shields.io/badge/Scalability-%234285F4.svg?style=for-the-badge&logo=googlecloud&logoColor=white
