# Complete ECS Workshop Implementation Guide

Based on the official ECS Workshop, this guide provides step-by-step instructions for implementing autoscaling and monitoring.

## Part 1: Setup Autoscaling in CDK Code

### Step 1: Modify the Frontend Service Code

Navigate to your frontend CDK directory and edit the `app.py` file:

```bash
cd ecsdemo-frontend/cdk
```

### Step 2: Add Autoscaling Configuration

In your `app.py` file, find the section after the `fargate_load_balanced_service` is created and add this autoscaling code:

```python
# Enable Service Autoscaling
self.autoscale = self.fargate_load_balanced_service.service.auto_scale_task_count(
    min_capacity=1,
    max_capacity=10
)

self.autoscale.scale_on_cpu_utilization(
    "CPUAutoscaling",
    target_utilization_percent=50,
    scale_in_cooldown=core.Duration.seconds(30),
    scale_out_cooldown=core.Duration.seconds(30)
)
```

**Key Points from the Workshop:**
- Search for `Enable Service Autoscaling` in the code
- Remove the comments (#) from the autoscaling code
- This creates a target tracking policy for CPU utilization
- Min capacity: 1 task, Max capacity: 10 tasks
- Target CPU utilization: 50%
- Cooldown periods: 30 seconds

## Part 2: Deploy the Autoscaling Changes

### Step 1: Review Changes with CDK Diff

```bash
cdk diff
```

**What you should see:**
- Addition of two resources (as shown in the workshop image)
- `AWS::ApplicationAutoScaling::ScalableTarget`
- `AWS::ApplicationAutoScaling::ScalingPolicy`

These resources enable ECS to use the Application Autoscaling service to manage scaling.

### Step 2: Deploy the Changes

```bash
cdk deploy --require-approval never
```

## Part 3: Load Testing and Monitoring

### Step 1: Get the Load Balancer URL

```bash
alb_url=$(aws cloudformation describe-stacks \
  --stack-name ecsworkshop-frontend \
  --query "Stacks" \
  --output json | jq -r '.[].Outputs[] | select(.OutputKey | contains("LoadBalancer")) | .OutputValue')

echo "Load Balancer URL: $alb_url"
```

### Step 2: Run Load Test with Siege

```bash
siege -c 20 -t 1m $alb_url
```

**Parameters:**
- `-c 20`: 20 concurrent users
- `-t 1m`: Run for 1 minute
- This will generate load to trigger autoscaling

### Step 3: Monitor Autoscaling Activity

While siege is running, monitor the scaling in another terminal:

```bash
# Watch ECS service scaling
watch -n 10 'aws ecs describe-services \
  --cluster container-demo \
  --services ecsdemo-frontend \
  --query "services[0].{DesiredCount:desiredCount,RunningCount:runningCount,PendingCount:pendingCount}" \
  --output table'
```

## Part 4: Review Service Logs

### Step 1: Get Log Group Name

```bash
log_group=$(awslogs groups -p ecsworkshop-frontend)
echo "Log group: $log_group"
```

### Step 2: Monitor Logs in Real-Time

```bash
awslogs get -G -S --timestamp --start 1m --watch $log_group
```

**Command Breakdown:**
- `-G`: Don't group by log stream
- `-S`: Don't show log stream names
- `--timestamp`: Show timestamps
- `--start 1m`: Start from 1 minute ago
- `--watch`: Follow logs in real-time

### Alternative Log Commands

```bash
# View recent logs
awslogs get /ecs/ecsdemo-frontend --start='5 minutes ago'

# Filter for errors
awslogs get /ecs/ecsdemo-frontend --filter-pattern='ERROR' --start='10 minutes ago'

# Watch logs during load test
awslogs get /ecs/ecsdemo-frontend --watch --start='now'
```

## Part 5: Verify Autoscaling Behavior

### Expected Behavior

1. **Initial State**: 1 running task
2. **Under Load**: CPU utilization increases above 50%
3. **Scale Out**: Additional tasks are launched (up to 10)
4. **After Load**: Tasks scale back down to minimum (1)

### Monitoring Commands

```bash
# Check current task count
aws ecs describe-services \
  --cluster container-demo \
  --services ecsdemo-frontend \
  --query 'services[0].{desired:desiredCount,running:runningCount,pending:pendingCount}'

# View scaling activities
aws application-autoscaling describe-scaling-activities \
  --service-namespace ecs \
  --resource-id service/container-demo/ecsdemo-frontend

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

## Part 6: Complete Workshop Script

Create a script to run the complete workshop:

```bash
#!/bin/bash
# complete-workshop.sh

echo "🚀 Starting ECS Workshop Autoscaling Demo"

# Activate environment
source activate.sh

# Deploy autoscaling changes
echo "📦 Deploying autoscaling configuration..."
cd ecsdemo-frontend/cdk
cdk diff
cdk deploy --require-approval never

# Get ALB URL
echo "🔍 Getting Load Balancer URL..."
alb_url=$(aws cloudformation describe-stacks \
  --stack-name ecsworkshop-frontend \
  --query "Stacks" \
  --output json | jq -r '.[].Outputs[] | select(.OutputKey | contains("LoadBalancer")) | .OutputValue')

echo "🌐 Load Balancer URL: http://$alb_url"

# Start log monitoring in background
echo "📊 Starting log monitoring..."
log_group=$(awslogs groups -p ecsworkshop-frontend)
awslogs get -G -S --timestamp --start 1m --watch $log_group &
LOG_PID=$!

# Start service monitoring in background
echo "📈 Starting service monitoring..."
watch -n 10 'aws ecs describe-services \
  --cluster container-demo \
  --services ecsdemo-frontend \
  --query "services[0].{DesiredCount:desiredCount,RunningCount:runningCount,PendingCount:pendingCount}" \
  --output table' &
WATCH_PID=$!

# Run load test
echo "⚡ Starting load test..."
echo "Press Ctrl+C to stop monitoring after load test completes"
siege -c 20 -t 2m http://$alb_url

# Cleanup background processes
kill $LOG_PID $WATCH_PID 2>/dev/null

echo "✅ Workshop complete! Check the AWS Console for detailed metrics."
```

## Key Learning Points

1. **Autoscaling Configuration**: CDK makes it easy to add autoscaling with just a few lines of code
2. **Monitoring**: Use `awslogs` for real-time log monitoring
3. **Load Testing**: `siege` is effective for generating load to trigger scaling
4. **Metrics**: CloudWatch automatically tracks CPU utilization and scaling activities

This implementation follows the exact workshop pattern shown in your images and provides a complete hands-on experience with ECS autoscaling.
