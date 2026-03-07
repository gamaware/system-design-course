# ADR-002: Lab Environment and Technology Stack

## Status

Accepted

## Context

The course requires students to work with cloud infrastructure, networking, security, and
distributed systems. Labs must be reproducible, cost-effective, and aligned with industry
tools. The syllabus references AWS, Azure, Linux, Docker, Kubernetes, Python, and LLMs as
core technologies.

## Decision

- **Primary cloud provider**: AWS (EC2, ECS, Lambda, S3, CloudFront, Route 53).
- **Secondary cloud provider**: Azure (introduced for multi-cloud awareness).
- **Operating system**: Amazon Linux 2023 as the default EC2 AMI for labs.
- **Containerization**: Docker and Kubernetes for modules 01 and 16.
- **Scripting**: Bash scripts for lab setup and automation; Python for application-level code.
- **Lab tools by module**:
  - Load balancing: HAProxy
  - DNS: dig and BIND9
  - Security: OpenSSL, Keycloak, OAuth 2.0 / OIDC
  - Networking: tcpdump, Wireshark, netcat
  - Caching: Redis, CloudFront
  - Messaging: Amazon SQS, SNS, or Apache Kafka
  - Serverless: AWS Lambda, API Gateway
  - AI: AWS Bedrock, LLM APIs

## Consequences

- Students need an AWS account (AWS Academy or personal) for most labs.
- Setup scripts (`setup.sh`) in each module automate environment configuration.
- Labs are designed for Amazon Linux but should work on most RPM-based distributions.
- Cost is minimized by using free-tier eligible resources where possible.
