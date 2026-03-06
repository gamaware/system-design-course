# System Design Course

![AWS](https://img.shields.io/badge/AWS-%23FF9900.svg?style=for-the-badge&logo=amazon-aws&logoColor=white)
![Python](https://img.shields.io/badge/Python-3670A0?style=for-the-badge&logo=python&logoColor=ffdd54)
![Bash](https://img.shields.io/badge/Bash-%23121011.svg?style=for-the-badge&logo=gnu-bash&logoColor=white)
![CDK](https://img.shields.io/badge/AWS_CDK-%23FF9900.svg?style=for-the-badge&logo=amazon-aws&logoColor=white)
![IaC](https://img.shields.io/badge/IaC-%23326CE5.svg?style=for-the-badge&logoColor=white)
![Scalability](https://img.shields.io/badge/Scalability-%234285F4.svg?style=for-the-badge&logo=googlecloud&logoColor=white)

## 🚀 Scalable Systems Design - ITESO

Course materials and demos for Scalable Systems Design.

### 📚 Demos

#### [01 Horizontal Scalability Demo](./01%20Horizontal%20Scalability%20Demo)
Hands-on workshop demonstrating horizontal scaling with AWS ECS Fargate, Application Load Balancer, and autoscaling. Students learn to:
- Deploy containerized microservices using AWS CDK (Infrastructure as Code)
- Configure Application Load Balancers for traffic distribution
- Implement CPU-based autoscaling policies
- Monitor and observe scaling behavior with CloudWatch
- Perform load testing to trigger autoscaling events

**Technologies**: AWS ECS Fargate, AWS CDK (Python), Application Load Balancer, CloudWatch, Docker, Ruby on Rails (frontend), Node.js, Crystal

**Key Concepts**: Horizontal scaling, load balancing, autoscaling, containerization, infrastructure as code, observability

#### [02 HAProxy Load Balancing Demo](./02%20HAProxy%20Load%20Balancing%20Demo)
Comprehensive lab exploring load balancing algorithms with HAProxy on AWS EC2. Students learn to:
- Configure HAProxy as a load balancer
- Test and compare 6 different load balancing algorithms (Round Robin, Least Connections, Random, Weighted, Source Hash, URI Hash)
- Implement health checks and automatic failover
- Monitor load balancer statistics and performance
- Understand session persistence and content-based routing

**Technologies**: HAProxy, Python HTTP Server, AWS EC2, Linux

**Key Concepts**: Load balancing algorithms, health checks, failover, session persistence, high availability

### 🧪 Labs

#### [01 EC2 Basics Lab](./01%20EC2%20Basics%20Lab)
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

#### [03 DNS and BIND Lab](./03%20DNS%20and%20BIND%20Lab)
Hands-on lab teaching DNS fundamentals through practical exercises. Students learn to:
- Use `dig` to query and diagnose DNS records
- Explore different DNS record types (A, AAAA, CNAME, MX, NS, TXT, PTR)
- Configure BIND9 as an authoritative DNS server
- Implement DNS-based load balancing with Round Robin
- Compare DNS load balancing vs HAProxy load balancing
- Validate DNS configurations with diagnostic tools

**Technologies**: BIND9, dig, AWS EC2, Linux

**Key Concepts**: DNS resolution, DNS record types, authoritative DNS servers, DNS load balancing, Round Robin

#### [04 Keycloak OAuth Lab](./04%20Keycloak%20OAuth%20Lab)
Comprehensive lab exploring OAuth 2.0 authentication with Keycloak as an Identity and Access Management solution. Students learn to:
- Deploy Keycloak on EC2 with SSL/TLS encryption
- Configure OAuth 2.0 realms, clients, and users
- Implement JWT token-based authentication
- Build a Flask API with OAuth 2.0 token validation
- Understand authentication vs authorization in distributed systems
- Compare IAM solutions (Keycloak, AWS Cognito, Auth0, Firebase)
- Test security patterns and token lifecycle management

**Technologies**: Keycloak, Docker, Python Flask, OAuth 2.0, OpenID Connect, JWT, SSL/TLS, AWS EC2

**Key Concepts**: OAuth 2.0, OpenID Connect, JWT tokens, token introspection, identity federation, multi-tenancy, distributed authentication, API security

### 👨🏫 Instructor

**Mtro. Jorge Alejandro García Martínez**
- Email: alejandrogarcia@iteso.mx
- Canvas: [https://canvas.iteso.mx/courses/55229](https://canvas.iteso.mx/courses/55229)

### 📅 Schedule

- **Days**: Wednesday 7:00-9:00 AM, Friday 9:00-11:00 AM
- **Location**: T216
- **Semester**: Spring 2026

### 👤 Author

Created by [Alex Garcia](https://github.com/gamaware)

- [LinkedIn Profile](https://www.linkedin.com/in/gamaware/)
- [Personal Website](https://alexgarcia.info/)
