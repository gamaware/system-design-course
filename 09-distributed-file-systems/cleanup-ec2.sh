#!/usr/bin/env bash
set -euo pipefail

# Terminates the EC2 instance and cleans up resources created by setup-ec2.sh.
#
# Usage:
#   bash cleanup-ec2.sh

TAG_NAME="lab09-distributed-fs"
KEY_NAME="lab09-key"
SG_NAME="lab09-sg"

echo "=== Lab 09: EC2 Cleanup ==="
echo ""

# Find the instance
INSTANCE_ID=$(aws ec2 describe-instances \
    --filters "Name=tag:Name,Values=$TAG_NAME" \
              "Name=instance-state-name,Values=running,stopped,pending" \
    --query "Reservations[0].Instances[0].InstanceId" \
    --output text 2>/dev/null || echo "None")

if [ "$INSTANCE_ID" = "None" ] || [ "$INSTANCE_ID" = "" ]; then
    echo "  No running instance found with tag: $TAG_NAME"
else
    echo "Terminating instance $INSTANCE_ID..."
    aws ec2 terminate-instances --instance-ids "$INSTANCE_ID" > /dev/null
    echo "  Waiting for termination..."
    aws ec2 wait instance-terminated --instance-ids "$INSTANCE_ID"
    echo "  Instance terminated."
fi

# Delete key pair
if aws ec2 describe-key-pairs --key-names "$KEY_NAME" > /dev/null 2>&1; then
    echo "Deleting key pair..."
    aws ec2 delete-key-pair --key-name "$KEY_NAME"
    rm -f "${KEY_NAME}.pem"
    echo "  Key pair deleted."
fi

# Delete security group
VPC_ID=$(aws ec2 describe-vpcs \
    --filters "Name=isDefault,Values=true" \
    --query "Vpcs[0].VpcId" \
    --output text 2>/dev/null || echo "")

if [ "$VPC_ID" != "" ]; then
    SG_ID=$(aws ec2 describe-security-groups \
        --filters "Name=group-name,Values=$SG_NAME" "Name=vpc-id,Values=$VPC_ID" \
        --query "SecurityGroups[0].GroupId" \
        --output text 2>/dev/null || echo "None")

    if [ "$SG_ID" != "None" ] && [ "$SG_ID" != "" ]; then
        echo "Deleting security group..."
        aws ec2 delete-security-group --group-id "$SG_ID" 2>/dev/null || true
        echo "  Security group deleted."
    fi
fi

echo ""
echo "Cleanup complete. All EC2 resources removed."
