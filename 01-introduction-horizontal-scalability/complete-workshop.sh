#!/bin/bash
set -euo pipefail

# complete-workshop.sh - Runs the complete ECS Workshop autoscaling demo

# Resolve script directory so it works from any working directory
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd -P)"

# Cleanup background processes on exit/interrupt
LOG_PID=""
WATCH_PID=""
cleanup() {
    [[ -n "$LOG_PID" ]] && kill "$LOG_PID" 2>/dev/null
    [[ -n "$WATCH_PID" ]] && kill "$WATCH_PID" 2>/dev/null
}
trap cleanup EXIT INT TERM

echo "Starting ECS Workshop Autoscaling Demo"

# Activate environment
if [[ ! -f "$SCRIPT_DIR/activate.sh" ]]; then
    echo "Error: activate.sh not found in $SCRIPT_DIR" >&2
    exit 1
fi
# shellcheck disable=SC1091
source "$SCRIPT_DIR/activate.sh"

# Deploy autoscaling changes
echo "Deploying autoscaling configuration..."
cd "$SCRIPT_DIR/ecsdemo-frontend/cdk" || exit 1
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
log_group=$(awslogs groups -p ecsworkshop-frontend 2>/dev/null || true)
if [[ -z "$log_group" ]]; then
    echo "Warning: Could not find log group for ecsworkshop-frontend" >&2
else
    awslogs get -G -S --timestamp --start 1m --watch "$log_group" &
    LOG_PID=$!
fi

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

echo "Workshop complete! Check the AWS Console for detailed metrics."
