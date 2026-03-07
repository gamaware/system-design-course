#!/bin/bash
# complete-workshop.sh - Runs the complete ECS Workshop autoscaling demo

echo "Starting ECS Workshop Autoscaling Demo"

# Activate environment
source activate.sh

# Deploy autoscaling changes
echo "Deploying autoscaling configuration..."
cd ecsdemo-frontend/cdk || exit 1
cdk diff
cdk deploy --require-approval never

# Get ALB URL
echo "Getting Load Balancer URL..."
alb_url=$(aws cloudformation describe-stacks \
  --stack-name ecsworkshop-frontend \
  --query "Stacks" \
  --output json | jq -r '.[].Outputs[] | select(.OutputKey | contains("LoadBalancer")) | .OutputValue')

echo "Load Balancer URL: http://$alb_url"

# Start log monitoring in background
echo "Starting log monitoring..."
log_group=$(awslogs groups -p ecsworkshop-frontend)
awslogs get -G -S --timestamp --start 1m --watch "$log_group" &
LOG_PID=$!

# Start service monitoring in background
echo "Starting service monitoring..."
watch -n 10 'aws ecs describe-services \
  --cluster container-demo \
  --services ecsdemo-frontend \
  --query "services[0].{DesiredCount:desiredCount,RunningCount:runningCount,PendingCount:pendingCount}" \
  --output table' &
WATCH_PID=$!

# Run load test
echo "Starting load test..."
echo "Press Ctrl+C to stop monitoring after load test completes"
siege -c 20 -t 2m "http://$alb_url"

# Cleanup background processes
kill "$LOG_PID" "$WATCH_PID" 2>/dev/null

echo "Workshop complete! Check the AWS Console for detailed metrics."
