#!/bin/bash
# cleanup.sh — Lab 08 full resource teardown
#
# This script deletes ALL AWS resources created during the lab, in the
# correct dependency order:
#   1. Terraform destroy (EC2 instances — must go first, they depend on VPC)
#   2. Delete security group via AWS CLI
#   3. Delete key pair via AWS CLI and remove local .pem file
#   4. Delete CloudFormation stack (VPC, subnets, IGW, route tables)
#
# Safe to run multiple times — each step checks if the resource exists
# before attempting deletion.
#
# Usage: ./cleanup.sh

set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd -P)"
cd "$SCRIPT_DIR"

STACK_NAME="vpc-lab-network"
KEY_NAME="vpc-lab-key"
SG_NAME="vpc-lab-sg"

echo "========================================="
echo "Lab 08 — Cleanup"
echo "========================================="
echo ""

# --- Step 1: Destroy Terraform resources (EC2 instances) ---
echo "Step 1: Destroying Terraform-managed resources (EC2 instances)..."
cd "$SCRIPT_DIR/terraform"
if [ -f terraform.tfstate ]; then
  terraform destroy -auto-approve
else
  echo "  No Terraform state found, skipping."
fi
cd "$SCRIPT_DIR"

# --- Step 2: Delete security group ---
echo ""
echo "Step 2: Deleting security group..."
VPC_ID=$(aws cloudformation describe-stacks \
  --stack-name "$STACK_NAME" \
  --query 'Stacks[0].Outputs[?OutputKey==`VpcId`].OutputValue' \
  --output text 2>/dev/null || echo "")

if [ "$VPC_ID" != "" ]; then
  SG_ID=$(aws ec2 describe-security-groups \
    --filters "Name=group-name,Values=$SG_NAME" "Name=vpc-id,Values=$VPC_ID" \
    --query 'SecurityGroups[0].GroupId' \
    --output text 2>/dev/null || echo "None")

  if [ "$SG_ID" != "None" ] && [ "$SG_ID" != "" ]; then
    aws ec2 delete-security-group --group-id "$SG_ID"
    echo "  Deleted security group: $SG_ID"
  else
    echo "  Security group not found, skipping."
  fi
else
  echo "  CloudFormation stack not found, skipping security group."
fi

# --- Step 3: Delete key pair ---
echo ""
echo "Step 3: Deleting key pair..."
if aws ec2 describe-key-pairs --key-names "$KEY_NAME" >/dev/null 2>&1; then
  aws ec2 delete-key-pair --key-name "$KEY_NAME"
  echo "  Deleted key pair: $KEY_NAME"
else
  echo "  Key pair not found, skipping."
fi

if [ -f "$SCRIPT_DIR/vpc-lab-key.pem" ]; then
  rm "$SCRIPT_DIR/vpc-lab-key.pem"
  echo "  Removed local vpc-lab-key.pem file."
fi

# --- Step 4: Delete CloudFormation stack ---
echo ""
echo "Step 4: Deleting CloudFormation stack: $STACK_NAME ..."
if aws cloudformation describe-stacks --stack-name "$STACK_NAME" >/dev/null 2>&1; then
  aws cloudformation delete-stack --stack-name "$STACK_NAME"
  echo "  Waiting for stack deletion (this may take a few minutes)..."
  aws cloudformation wait stack-delete-complete --stack-name "$STACK_NAME"
  echo "  Stack deleted."
else
  echo "  Stack not found, skipping."
fi

echo ""
echo "========================================="
echo "Cleanup complete!"
echo "========================================="
echo ""
echo "All AWS resources have been deleted."
