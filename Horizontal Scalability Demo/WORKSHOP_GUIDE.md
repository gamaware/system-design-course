# ECS Workshop Guide - Local macOS Setup

This guide walks you through the ECS Workshop adapted for local macOS development, replacing the original Cloud9 environment.

## Prerequisites Setup

### 1. Initial Setup
```bash
# Run the setup script
chmod +x setup.sh
./setup.sh

# Configure AWS credentials
aws configure
# Enter your AWS Access Key ID: [your-access-key]
# Enter your AWS Secret Access Key: [your-secret-key]
# Default region name: us-east-1
# Default output format: json

# Activate the workshop environment
source activate.sh

# Bootstrap CDK (one-time setup)
cdk bootstrap
```

## Workshop Architecture

This workshop demonstrates a microservices architecture with:
- **Platform**: VPC, ECS Cluster, Security Groups, Load Balancer
- **Frontend**: Ruby on Rails web application
- **Backend Services**: Node.js and Crystal services (optional)

## Deployment Options

You can choose between two deployment methods:
1. **CDK (Recommended for learning)**: Infrastructure as Code with Python
2. **Copilot CLI**: Simplified container deployment tool

---

## Part 1: Deploy the Platform (Infrastructure)

The platform creates the foundational AWS resources needed for your microservices.

### Using CDK (Recommended)

```bash
# Navigate to platform directory
cd ecsdemo-platform/cdk

# Review the infrastructure code
cat app.py

# Synthesize CloudFormation templates (dry run)
cdk synth

# Review proposed changes
cdk diff

# Deploy the platform
cdk deploy --require-approval never
```

**What gets deployed:**
- VPC with public/private subnets across AZs
- ECS Cluster named "container-demo"
- Service Discovery namespace
- Security Groups for service communication
- EC2 bastion host for load testing
- NAT Gateways and Internet Gateway

### Using Copilot CLI (Alternative)

```bash
# Copilot handles platform creation automatically
# Skip to Part 2 if using Copilot
```

---

## Part 2: Deploy the Frontend Service

### Option A: Using CDK

```bash
# Navigate to frontend directory
cd ../ecsdemo-frontend/cdk

# Review the service code
cat app.py

# Synthesize the templates
cdk synth

# Review changes
cdk diff

# Deploy the frontend service
cdk deploy --require-approval never
```

**What gets deployed:**
- Application Load Balancer (ALB)
- ECS Fargate Service
- Task Definition with container specs
- Target Groups and Health Checks
- Service Discovery registration

### Option B: Using Copilot CLI

```bash
# Navigate to frontend directory
cd ../ecsdemo-frontend

# Initialize the application
copilot init

# Answer the prompts:
# Application name: ecsworkshop
# Service Type: Load Balanced Web Service
# Service name: ecsdemo-frontend
# Dockerfile: ./Dockerfile

# Add backend service URLs (for later integration)
cat << EOF >> copilot/ecsdemo-frontend/manifest.yml
variables:
  CRYSTAL_URL: "http://ecsdemo-crystal.test.ecsworkshop.local:3000/crystal"
  NODEJS_URL: "http://ecsdemo-nodejs.test.ecsworkshop.local:3000"
EOF

# Generate git hash for version display
git rev-parse --short=7 HEAD > code_hash.txt

# Initialize test environment
copilot env init --name test --profile default --default-config

# Deploy the service
copilot svc deploy
```

---

## Part 3: Verify and Test Deployment

### Get the Application URL

**CDK:**
```bash
# Get the load balancer URL from CloudFormation outputs
aws cloudformation describe-stacks \
  --stack-name ecsdemo-frontend \
  --query 'Stacks[0].Outputs[?OutputKey==`LoadBalancerDNS`].OutputValue' \
  --output text
```

**Copilot:**
```bash
# Get the service URL
copilot svc show -n ecsdemo-frontend --json | jq -r .routes[].url
```

### Test the Application

1. Open the URL in your browser
2. You should see the frontend application
3. Initially, it may not show the full architecture diagram (backend services not deployed yet)

---

## Part 4: Scaling and Management

### Manual Scaling

**CDK:**
```bash
# Edit the desired_count in app.py, then redeploy
cd ecsdemo-frontend/cdk
# Modify the desired_count parameter in app.py
cdk deploy --require-approval never
```

**Copilot:**
```bash
# Edit the manifest file
vim copilot/ecsdemo-frontend/manifest.yml
# Change count from 1 to 3
count: 3

# Redeploy
copilot svc deploy
```

### Auto Scaling

**CDK:**
```bash
# Add auto scaling configuration to your CDK code
# Example: Configure target tracking scaling based on CPU utilization
```

**Copilot:**
```bash
# Add to manifest.yml
count:
  min: 1
  max: 10
  cooldown:
    scale_in_cooldown: 60s
    scale_out_cooldown: 60s
  target_cpu: 70
  target_memory: 80
```

---

## Part 5: Monitoring and Debugging

### View Service Status

**CDK:**
```bash
# Check ECS service status
aws ecs describe-services \
  --cluster container-demo \
  --services ecsdemo-frontend
```

**Copilot:**
```bash
# Check service status
copilot svc status -n ecsdemo-frontend

# View application overview
copilot app show ecsworkshop
```

### View Logs

**CDK:**
```bash
# Using awslogs (installed in requirements.txt)
awslogs get /ecs/ecsdemo-frontend --start='1 hour ago'
```

**Copilot:**
```bash
# Tail logs in real-time
copilot svc logs -n ecsdemo-frontend --follow

# View recent logs
copilot svc logs -n ecsdemo-frontend
```

### Load Testing

```bash
# Connect to the bastion host (CDK deployment creates one)
aws ssm start-session --target i-xxxxxxxxx

# Or use siege locally (installed via setup.sh)
siege -c 10 -t 60s http://your-load-balancer-url
```

---

## Part 6: Adding Backend Services (Optional)

### Deploy Node.js Backend

```bash
cd ../ecsdemo-nodejs

# Using Copilot
copilot init
# Service Type: Backend Service
# Service name: ecsdemo-nodejs

copilot svc deploy

# Using CDK
cd cdk
cdk deploy --require-approval never
```

### Deploy Crystal Backend

```bash
cd ../ecsdemo-crystal

# Similar process as Node.js service
copilot init
copilot svc deploy
```

---

## Part 7: Cleanup

### Remove All Resources

**CDK:**
```bash
# Delete in reverse order
cd ecsdemo-frontend/cdk
cdk destroy

cd ../../ecsdemo-platform/cdk
cdk destroy
```

**Copilot:**
```bash
# Delete services
copilot svc delete -n ecsdemo-frontend

# Delete environment
copilot env delete -n test

# Delete application
copilot app delete ecsworkshop
```

---

## Troubleshooting

### Common Issues

1. **CDK Bootstrap Error**
   ```bash
   cdk bootstrap aws://311141527383/us-east-1
   ```

2. **Docker Not Running**
   ```bash
   # Start Docker Desktop manually
   open /Applications/Docker.app
   ```

3. **AWS Credentials Not Set**
   ```bash
   aws configure
   # Or set environment variables
   export AWS_ACCESS_KEY_ID=your-key
   export AWS_SECRET_ACCESS_KEY=your-secret
   ```

4. **Service Not Accessible**
   - Check security groups
   - Verify load balancer health checks
   - Check ECS service events

### Useful Commands

```bash
# Check AWS CLI configuration
aws sts get-caller-identity

# List ECS clusters
aws ecs list-clusters

# List running tasks
aws ecs list-tasks --cluster container-demo

# Describe task definition
aws ecs describe-task-definition --task-definition ecsdemo-frontend
```

---

## Learning Objectives

By completing this workshop, you will understand:

1. **Infrastructure as Code**: Using CDK to define AWS resources
2. **Container Orchestration**: ECS Fargate for serverless containers
3. **Service Discovery**: AWS Cloud Map for service-to-service communication
4. **Load Balancing**: Application Load Balancer configuration
5. **Scaling**: Manual and automatic scaling strategies
6. **Monitoring**: CloudWatch logs and metrics
7. **Security**: Security groups and IAM roles

---

## Next Steps

1. **Add CI/CD Pipeline**: Implement automated deployments
2. **Add Monitoring**: Set up CloudWatch dashboards and alarms
3. **Implement Blue/Green Deployments**: Zero-downtime deployments
4. **Add Database**: RDS integration with backend services
5. **Implement Caching**: ElastiCache for improved performance

---

## Resources

- [ECS Workshop Official Site](https://ecsworkshop.com/)
- [AWS CDK Documentation](https://docs.aws.amazon.com/cdk/)
- [AWS Copilot Documentation](https://aws.github.io/copilot-cli/)
- [ECS Best Practices](https://docs.aws.amazon.com/AmazonECS/latest/bestpracticesguide/)
