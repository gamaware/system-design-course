# Presentation Assets

## AWS Architecture Icons

Official AWS Architecture Icons (2026 edition), 48px SVG format.
Organized by service category. Source: AWS Architecture Icons download page.

### Categories

- `aws-icons/analytics/` --- Kinesis, Athena, Redshift, etc.
- `aws-icons/compute/` --- Lambda, EC2, Fargate, ECS, etc.
- `aws-icons/containers/` --- ECS, EKS, ECR, etc.
- `aws-icons/databases/` --- RDS, DynamoDB, ElastiCache, Neptune, etc.
- `aws-icons/integration/` --- SNS, SQS, Step Functions, EventBridge, etc.
- `aws-icons/management/` --- CloudWatch, CloudFormation, Config, etc.
- `aws-icons/networking/` --- API Gateway, CloudFront, Route 53, ELB, etc.
- `aws-icons/security/` --- Cognito, IAM, KMS, WAF, etc.
- `aws-icons/storage/` --- S3, EBS, EFS, FSx, etc.

### Usage

Reference from any module presentation via relative path:

```html
<img src="../../shared/presentation/assets/aws-icons/databases/Arch_Amazon-RDS_48.svg"
     alt="Amazon RDS" width="48" height="48">
```

## Database Engine Logos

Downloaded from [icons8.com](https://icons8.com) at 96px resolution.
Visit icons8.com for additional technology logos for future presentations.

### Source URLs

- `mysql.png` --- <https://img.icons8.com/color/96/mysql-logo.png>
- `postgresql.png` --- <https://img.icons8.com/color/96/postgreesql.png>
- `aurora.png` --- <https://img.icons8.com/color/96/amazon-web-services.png>
- `oracle.png` --- <https://img.icons8.com/color/96/oracle-logo.png>
- `sqlserver.png` --- <https://img.icons8.com/color/96/microsoft-sql-server.png>
- `mariadb.png` --- <https://img.icons8.com/color/96/maria-db.png>

### DB Logo Usage

```html
<img src="../../shared/presentation/assets/db-logos/mysql.png"
     alt="MySQL" width="32" height="32">
```

## Generic Technology Icons

Downloaded from [icons8.com](https://icons8.com) at 96px resolution.
Cloud-agnostic icons for architecture diagrams that are not tied to any specific vendor.

### Available Icons

- `api.png`, `cloud.png`, `database.png`, `server.png` --- generic infrastructure
- `redis.png`, `memcached.png`, `mongodb.png` --- databases and caching
- `nginx.png`, `cloudflare.png` --- proxies and CDN
- `kafka.png`, `rabbitmq.png` --- messaging
- `docker.png`, `kubernetes.png` --- containers
- `globe.png`, `laptop.png`, `lock.png` --- clients and security

### Generic Icon Usage

```html
<img src="../../shared/presentation/assets/generic-icons/redis.png"
     alt="Redis" width="48" height="48">
```
