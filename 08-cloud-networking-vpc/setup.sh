#!/bin/bash
# setup.sh — Lab 08 initial infrastructure deployment
#
# This script automates the first phase of the lab:
#   1. Validates that AWS CLI and Terraform are installed
#   2. Verifies that AWS credentials are active (sts get-caller-identity)
#   3. Deploys the CloudFormation stack (VPC, subnets, IGW, route tables)
#   4. Initializes Terraform (downloads the AWS provider)
#
# After running this script, students must manually:
#   - Create a key pair (Task 3)
#   - Create a security group (Task 4)
#   - Run terraform plan and terraform apply (Task 5)
#
# Usage: ./setup.sh

set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd -P)"
cd "$SCRIPT_DIR"

STACK_NAME="vpc-lab-network"

echo "========================================="
echo "Lab 08 — Cloud Networking VPC Setup"
echo "========================================="
echo ""

# --- Prerequisite checks ---
echo "Checking prerequisites..."

if ! command -v aws >/dev/null 2>&1; then
  echo "ERROR: AWS CLI not found. Install it first (see README Task 1)."
  exit 1
fi
echo "  AWS CLI: $(aws --version 2>&1 | head -1)"

if ! command -v terraform >/dev/null 2>&1; then
  echo "ERROR: Terraform not found. Install it first (see README Task 1)."
  exit 1
fi
echo "  Terraform: $(terraform --version | head -1)"

echo ""
echo "Verifying AWS credentials..."
if ! aws sts get-caller-identity >/dev/null 2>&1; then
  echo "ERROR: AWS credentials not configured."
  echo "Export your AWS Academy Learner Lab credentials as environment variables."
  echo "See README Task 1 for instructions."
  exit 1
fi
aws sts get-caller-identity --output table
echo ""

# --- Deploy CloudFormation stack ---
echo "Deploying CloudFormation stack: $STACK_NAME ..."
echo "This creates: VPC, 2 public subnets, Internet Gateway, route tables."
echo ""

aws cloudformation deploy \
  --template-file cloudformation/vpc-network.yaml \
  --stack-name "$STACK_NAME" \
  --no-fail-on-empty-changeset

echo ""
echo "Waiting for stack to complete..."
aws cloudformation wait stack-create-complete --stack-name "$STACK_NAME" 2>/dev/null || true

# --- Show outputs ---
echo ""
echo "CloudFormation stack outputs:"
aws cloudformation describe-stacks \
  --stack-name "$STACK_NAME" \
  --query 'Stacks[0].Outputs[*].[OutputKey,OutputValue]' \
  --output table

# --- Initialize Terraform ---
echo ""
echo "Initializing Terraform..."
cd "$SCRIPT_DIR/terraform"
terraform init -input=false

echo ""
echo "========================================="
echo "Network infrastructure deployed!"
echo "========================================="
echo ""
echo "Next steps (see README for full instructions):"
echo ""
echo "  1. Create a key pair:"
echo "     aws ec2 create-key-pair --key-name vpc-lab-key \\"
echo "       --query 'KeyMaterial' --output text > vpc-lab-key.pem"
echo "     chmod 400 vpc-lab-key.pem"
echo ""
echo "  2. Create a security group (see README Task 4)"
echo ""
echo "  3. Deploy EC2 instances:"
echo "     cd terraform"
echo "     cp terraform.tfvars.example terraform.tfvars"
echo "     terraform plan"
echo "     terraform apply"
echo ""
