# ECS Workshop - Complete Step-by-Step Guide

This guide walks you through the complete ECS workshop experience: setting up prerequisites, deploying platform infrastructure, deploying the frontend service, manual scaling, and implementing autoscaling.

## Phase 1: Prerequisites and Setup

### Step 1.1: Environment Setup

```bash
# Make setup script executable
chmod +x setup.sh

# Run the setup script
./setup.sh
```

### Step 1.2: Configure AWS Credentials

```bash
# Configure your AWS credentials
aws configure

# Enter when prompted:
# AWS Access Key ID: [your-access-key]
# AWS Secret Access Key: [your-secret-key]  
# Default region name: us-east-1
# Default output format: json
```

### Step 1.3: Activate Workshop Environment

```bash
# Activate the workshop environment
source activate.sh

# Verify everything is working
aws sts get-caller-identity
```

### Step 1.4: Bootstrap CDK (One-time setup)

```bash
# Bootstrap CDK for your account/region
cdk bootstrap

# Verify bootstrap was successful
aws cloudformation describe-stacks --stack-name CDKToolkit
```

**✅ Prerequisites Complete!** You should see:
- AWS credentials configured
- CDK bootstrapped
- Virtual environment activated
- All tools installed (jq, node, siege, awslogs, cdk)

---

## Phase 2: Deploy the Platform Infrastructure

### Step 2.1: Navigate to Platform Directory

```bash
cd ecsdemo-platform/cdk
```

### Step 2.2: Review Platform Code

```bash
# Look at what will be created
cat app.py | grep -A 5 -B 5 "class BaseVPCStack"
```

### Step 2.3: Synthesize CloudFormation Templates

```bash
# Generate CloudFormation templates (dry run)
cdk synth
```

**What you should see:** CloudFormation YAML/JSON templates for VPC, ECS Cluster, Security Groups, etc.

### Step 2.4: Review Proposed Changes

```bash
# See what resources will be created
cdk diff
```

**Expected output:** Since this is the first deployment, you'll see all new resources being created:
- VPC with subnets
- ECS Cluster
- Security Groups
- Service Discovery namespace
- EC2 bastion host

### Step 2.5: Deploy the Platform

```bash
# Deploy the infrastructure
cdk deploy --require-approval never
```

**⏱️ This takes about 3-5 minutes**

### Step 2.6: Verify Platform Deployment

```bash
# Check if ECS cluster was created
aws ecs describe-clusters --clusters container-demo

# Check VPC
aws ec2 describe-vpcs --filters "Name=tag:Name,Values=ecsworkshop-base/BaseVPC"

# View all stack outputs
aws cloudformation describe-stacks --stack-name ecsworkshop-base --query 'Stacks[0].Outputs'
```

**✅ Platform Complete!** You should see:
- ECS Cluster: `container-demo`
- VPC with public/private subnets
- Service Discovery namespace: `service.local`
- Security groups for service communication
- EC2 bastion host for load testing

---

## Phase 3: Deploy the Frontend Service

### Step 3.1: Navigate to Frontend Directory

```bash
cd ../../ecsdemo-frontend/cdk
```

### Step 3.2: Review Frontend Code

```bash
# Look at the frontend service configuration
cat app.py | grep -A 10 -B 5 "ApplicationLoadBalancedFargateService"
```

### Step 3.3: Synthesize Frontend Templates

```bash
# Generate CloudFormation templates
cdk synth
```

### Step 3.4: Review Frontend Changes

```bash
# See what will be created for the frontend
cdk diff
```

**Expected output:** New resources for:
- Application Load Balancer (ALB)
- ECS Fargate Service
- Task Definition
- Target Groups
- CloudWatch Log Groups

### Step 3.5: Deploy Frontend Service

```bash
# Deploy the frontend service
cdk deploy --require-approval never
```

**⏱️ This takes about 2-3 minutes**

### Step 3.6: Get Application URL

```bash
# Get the Load Balancer URL
alb_url=$(aws cloudformation describe-stacks \
  --stack-name ecsworkshop-frontend \
  --query "Stacks[0].Outputs[?OutputKey=='FrontendFargateLBServiceLoadBalancerDNS'].OutputValue" \
  --output text)

echo "🌐 Frontend URL: http://$alb_url"
```

### Step 3.7: Test the Application

```bash
# Open in browser or test with curl
curl -I http://$alb_url

# Or copy the URL and open in your browser
echo "Open this URL in your browser: http://$alb_url"
```

**✅ Frontend Complete!** You should see:
- Working web application
- Load balancer distributing traffic
- ECS service running 1 task
- Application accessible via ALB URL

---

## Phase 4: Manual Scaling

### Step 4.1: Check Current Service Status

```bash
# Check current task count
aws ecs describe-services \
  --cluster container-demo \
  --services ecsdemo-frontend \
  --query 'services[0].{ServiceName:serviceName,DesiredCount:desiredCount,RunningCount:runningCount,PendingCount:pendingCount}'
```

**Expected output:** 1 desired, 1 running, 0 pending

### Step 4.2: Scale Up Manually (Method 1: AWS CLI)

```bash
# Scale to 3 tasks
aws ecs update-service \
  --cluster container-demo \
  --service ecsdemo-frontend \
  --desired-count 3

echo "✅ Scaling to 3 tasks initiated"
```

### Step 4.3: Monitor Manual Scaling

```bash
# Watch the scaling happen
watch -n 5 'aws ecs describe-services \
  --cluster container-demo \
  --services ecsdemo-frontend \
  --query "services[0].{DesiredCount:desiredCount,RunningCount:runningCount,PendingCount:pendingCount}" \
  --output table'
```

**Press Ctrl+C to stop watching**

### Step 4.4: Scale Up Manually (Method 2: CDK)

```bash
# Alternative: Edit the CDK code and redeploy
# Open app.py and change desired_count from 1 to 5
sed -i '' 's/desired_count=1/desired_count=5/' app.py

# Deploy the change
cdk diff  # Review the change
cdk deploy --require-approval never
```

### Step 4.5: Verify Multiple Tasks

```bash
# List all running tasks
aws ecs list-tasks --cluster container-demo --service-name ecsdemo-frontend

# Get detailed task information
aws ecs describe-tasks \
  --cluster container-demo \
  --tasks $(aws ecs list-tasks --cluster container-demo --service-name ecsdemo-frontend --query 'taskArns[0]' --output text) \
  --query 'tasks[0].{TaskArn:taskArn,LastStatus:lastStatus,HealthStatus:healthStatus,CreatedAt:createdAt}'
```

### Step 4.6: Test Load Distribution

```bash
# Test multiple requests to see different task IPs
for i in {1..10}; do
  curl -s http://$alb_url | grep -o "Task ID: [^<]*" || echo "Request $i completed"
  sleep 1
done
```

### Step 4.7: Scale Down Manually

```bash
# Scale back down to 2 tasks
aws ecs update-service \
  --cluster container-demo \
  --service ecsdemo-frontend \
  --desired-count 2

# Watch it scale down
aws ecs describe-services \
  --cluster container-demo \
  --services ecsdemo-frontend \
  --query 'services[0].{DesiredCount:desiredCount,RunningCount:runningCount}'
```

**✅ Manual Scaling Complete!** You've learned:
- How to scale ECS services manually via CLI
- How to scale via CDK code changes
- How to monitor scaling operations
- How load balancers distribute traffic across tasks

---

## Phase 5: Implement Autoscaling

### Step 5.1: Review Current Code

```bash
# Look for the commented autoscaling code
grep -n -A 8 "Enable Service Autoscaling" app.py
```

**You should see commented lines around line 65-75**

### Step 5.2: Enable Autoscaling Code

```bash
# Create a backup first
cp app.py app.py.backup

# Uncomment the autoscaling lines
sed -i '' 's/#self\.autoscale/self.autoscale/g' app.py
sed -i '' 's/#    /    /g' app.py
```

**Or manually edit the file:**
```bash
# Open the file in your preferred editor
nano app.py
# or
vim app.py
# or
code app.py
```

Find these lines and remove the `#` symbols:
```python
        # Enable Service Autoscaling
        #self.autoscale = self.fargate_load_balanced_service.service.auto_scale_task_count(
        #    min_capacity=1,
        #    max_capacity=10
        #)
        
        #self.autoscale.scale_on_cpu_utilization(
        #    "CPUAutoscaling",
        #    target_utilization_percent=50,
        #    scale_in_cooldown=Duration.seconds(30),
        #    scale_out_cooldown=Duration.seconds(30)
        #)
```

### Step 5.3: Review Autoscaling Changes

```bash
# See what autoscaling resources will be added
cdk diff
```

**Expected output:** Two new resources:
- `AWS::ApplicationAutoScaling::ScalableTarget`
- `AWS::ApplicationAutoScaling::ScalingPolicy`

### Step 5.4: Deploy Autoscaling Configuration

```bash
# Deploy the autoscaling changes
cdk deploy --require-approval never
```

### Step 5.5: Verify Autoscaling Setup

```bash
# Check scalable targets
aws application-autoscaling describe-scalable-targets \
  --service-namespace ecs \
  --resource-ids service/container-demo/ecsdemo-frontend

# Check scaling policies
aws application-autoscaling describe-scaling-policies \
  --service-namespace ecs \
  --resource-id service/container-demo/ecsdemo-frontend
```

### Step 5.6: Prepare Load Testing

```bash
# Start log monitoring in background (optional)
log_group=$(awslogs groups -p ecsworkshop-frontend)
echo "📊 Log group: $log_group"

# Monitor logs (run in separate terminal)
awslogs get -G -S --timestamp --start 1m --watch $log_group &
LOG_PID=$!
```

### Step 5.7: Generate Load to Trigger Autoscaling

```bash
# Start service monitoring (run in separate terminal)
watch -n 10 'aws ecs describe-services \
  --cluster container-demo \
  --services ecsdemo-frontend \
  --query "services[0].{DesiredCount:desiredCount,RunningCount:runningCount,PendingCount:pendingCount}" \
  --output table' &
WATCH_PID=$!

# Generate load with siege
echo "🚀 Starting load test to trigger autoscaling..."
siege -c 20 -t 3m http://$alb_url
```

### Step 5.8: Monitor Autoscaling Activity

```bash
# Check scaling activities
aws application-autoscaling describe-scaling-activities \
  --service-namespace ecs \
  --resource-id service/container-demo/ecsdemo-frontend \
  --max-items 5

# Check CloudWatch metrics
aws cloudwatch get-metric-statistics \
  --namespace AWS/ECS \
  --metric-name CPUUtilization \
  --dimensions Name=ServiceName,Value=ecsdemo-frontend Name=ClusterName,Value=container-demo \
  --start-time $(date -u -d '10 minutes ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 300 \
  --statistics Average
```

### Step 5.9: Observe Scale Down

```bash
# After load test ends, watch tasks scale back down
echo "⏳ Waiting for scale down (this may take a few minutes due to cooldown)..."

# Monitor for 5 minutes
for i in {1..10}; do
  echo "Check $i/10:"
  aws ecs describe-services \
    --cluster container-demo \
    --services ecsdemo-frontend \
    --query 'services[0].{DesiredCount:desiredCount,RunningCount:runningCount}'
  sleep 30
done
```

### Step 5.10: Clean Up Background Processes

```bash
# Stop background monitoring
kill $LOG_PID $WATCH_PID 2>/dev/null || true
```

**✅ Autoscaling Complete!** You've learned:
- How to configure ECS autoscaling with CDK
- How autoscaling responds to CPU utilization
- How to monitor scaling activities
- How cooldown periods affect scaling behavior

---

## Phase 6: Monitoring and Observability

### Step 6.1: View Service Logs

```bash
# View recent logs
awslogs get /ecs/ecsdemo-frontend --start='10 minutes ago'

# Filter for specific patterns
awslogs get /ecs/ecsdemo-frontend --filter-pattern='GET' --start='5 minutes ago'

# Monitor logs in real-time
awslogs get /ecs/ecsdemo-frontend --watch
```

### Step 6.2: Check CloudWatch Metrics

```bash
# View ECS service metrics in AWS Console
echo "🔗 CloudWatch Console: https://console.aws.amazon.com/cloudwatch/home?region=us-east-1#metricsV2:graph=~();search=ECS;namespace=AWS/ECS"

# Or get metrics via CLI
aws cloudwatch list-metrics --namespace AWS/ECS --metric-name CPUUtilization
```

### Step 6.3: Review Application Load Balancer

```bash
# Get ALB details
aws elbv2 describe-load-balancers \
  --names $(aws cloudformation describe-stacks \
    --stack-name ecsworkshop-frontend \
    --query "Stacks[0].Outputs[?OutputKey=='FrontendFargateLBServiceLoadBalancerFullName'].OutputValue" \
    --output text)
```

---

## Phase 7: Cleanup

### Step 7.1: Delete Frontend Stack

```bash
cd ecsdemo-frontend/cdk
cdk destroy
```

### Step 7.2: Delete Platform Stack

```bash
cd ../../ecsdemo-platform/cdk
cdk destroy
```

### Step 7.3: Deactivate Environment

```bash
cd ../../
source deactivate.sh
```

---

## Summary

**What You've Accomplished:**

1. ✅ **Prerequisites**: Set up local macOS environment with all required tools
2. ✅ **Platform**: Deployed VPC, ECS Cluster, and supporting infrastructure
3. ✅ **Frontend**: Deployed containerized web application with load balancer
4. ✅ **Manual Scaling**: Learned to scale ECS services manually via CLI and CDK
5. ✅ **Autoscaling**: Implemented CPU-based autoscaling with load testing
6. ✅ **Monitoring**: Used CloudWatch logs and metrics to observe behavior

**Key Learning Points:**
- Infrastructure as Code with AWS CDK
- ECS Fargate for serverless containers
- Application Load Balancer for traffic distribution
- Manual vs. automatic scaling strategies
- CloudWatch monitoring and observability
- Load testing with siege

**Next Steps:**
- Add backend services (Node.js, Crystal)
- Implement blue/green deployments
- Add database integration
- Set up CI/CD pipelines
- Explore service mesh with App Mesh
