#!/bin/bash

# Quick Start Script for ECS Workshop
# This script automates the entire deployment process

set -e

echo "🚀 ECS Workshop Quick Start"
echo "This will deploy the platform and frontend service using CDK"
echo ""

# Check if environment is activated
if [[ "$VIRTUAL_ENV" == "" ]]; then
    echo "⚠️  Virtual environment not activated. Running setup first..."
    source activate.sh
fi

# Verify AWS credentials
echo "🔍 Verifying AWS credentials..."
if ! aws sts get-caller-identity &>/dev/null; then
    echo "❌ AWS credentials not configured. Please run 'aws configure' first."
    exit 1
fi

echo "✅ AWS credentials verified"

# Check CDK bootstrap
echo "🔍 Checking CDK bootstrap..."
if ! aws cloudformation describe-stacks --stack-name CDKToolkit --region $AWS_REGION &>/dev/null; then
    echo "📦 Bootstrapping CDK..."
    cdk bootstrap
fi

echo "✅ CDK is ready"

# Deploy Platform
echo ""
echo "🏗️  Deploying Platform (VPC, ECS Cluster, etc.)..."
cd ecsdemo-platform/cdk

echo "📋 Synthesizing platform templates..."
cdk synth > /dev/null

echo "🚀 Deploying platform..."
cdk deploy --require-approval never

if [ $? -eq 0 ]; then
    echo "✅ Platform deployed successfully!"
else
    echo "❌ Platform deployment failed!"
    exit 1
fi

# Deploy Frontend
echo ""
echo "🌐 Deploying Frontend Service..."
cd ../../ecsdemo-frontend/cdk

echo "📋 Synthesizing frontend templates..."
cdk synth > /dev/null

echo "🚀 Deploying frontend service..."
cdk deploy --require-approval never

if [ $? -eq 0 ]; then
    echo "✅ Frontend deployed successfully!"
else
    echo "❌ Frontend deployment failed!"
    exit 1
fi

# Get the application URL
echo ""
echo "🎉 Deployment Complete!"
echo ""

# Try to get the load balancer URL
FRONTEND_URL=$(aws cloudformation describe-stacks \
  --stack-name ecsdemo-frontend \
  --query 'Stacks[0].Outputs[?OutputKey==`LoadBalancerDNS`].OutputValue' \
  --output text 2>/dev/null || echo "")

if [ ! -z "$FRONTEND_URL" ]; then
    echo "🌐 Frontend URL: http://$FRONTEND_URL"
    echo ""
    echo "📱 Open this URL in your browser to see the application!"
else
    echo "🔍 To get the frontend URL, run:"
    echo "aws cloudformation describe-stacks --stack-name ecsdemo-frontend --query 'Stacks[0].Outputs'"
fi

echo ""
echo "📊 To monitor your deployment:"
echo "• View logs: awslogs get /ecs/ecsdemo-frontend --start='1 hour ago'"
echo "• Check service: aws ecs describe-services --cluster container-demo --services ecsdemo-frontend"
echo "• Scale service: Edit desired_count in ecsdemo-frontend/cdk/app.py and redeploy"
echo ""
echo "🧹 To clean up later:"
echo "• cd ecsdemo-frontend/cdk && cdk destroy"
echo "• cd ../../ecsdemo-platform/cdk && cdk destroy"

cd ../../
