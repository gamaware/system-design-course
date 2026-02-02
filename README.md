# System Design Course

![AWS](https://img.shields.io/badge/AWS-%23FF9900.svg?style=for-the-badge&logo=amazon-aws&logoColor=white)
![Python](https://img.shields.io/badge/Python-3670A0?style=for-the-badge&logo=python&logoColor=ffdd54)
![Bash](https://img.shields.io/badge/Bash-%23121011.svg?style=for-the-badge&logo=gnu-bash&logoColor=white)
![CDK](https://img.shields.io/badge/AWS_CDK-%23FF9900.svg?style=for-the-badge&logo=amazon-aws&logoColor=white)
![IaC](https://img.shields.io/badge/IaC-%23326CE5.svg?style=for-the-badge&logoColor=white)
![Scalability](https://img.shields.io/badge/Scalability-%234285F4.svg?style=for-the-badge&logo=googlecloud&logoColor=white)

## 🚀 Diseño de Sistemas Escalables - ITESO

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
