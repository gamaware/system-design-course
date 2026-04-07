#!/usr/bin/env bash
set -euo pipefail

# Launches an EC2 instance (Amazon Linux 2023), installs Docker, clones the
# repo, and starts the lab environment. Requires AWS CLI configured with
# AWS Academy Learner Lab credentials.
#
# Usage:
#   export AWS_ACCESS_KEY_ID=...
#   export AWS_SECRET_ACCESS_KEY=...
#   export AWS_SESSION_TOKEN=...
#   export AWS_DEFAULT_REGION=us-east-1
#   bash setup-ec2.sh

INSTANCE_TYPE="t3.medium"
KEY_NAME="lab09-key"
SG_NAME="lab09-sg"
TAG_NAME="lab09-distributed-fs"
REGION="${AWS_DEFAULT_REGION:-us-east-1}"

echo "=== Lab 09: EC2 Setup ==="
echo ""

# Verify AWS credentials
echo "Verifying AWS credentials..."
if ! aws sts get-caller-identity > /dev/null 2>&1; then
    echo "ERROR: AWS credentials not configured."
    echo ""
    echo "Get your credentials from AWS Academy Learner Lab:"
    echo "  1. Go to your Learner Lab course"
    echo "  2. Click 'Start Lab' and wait for the green indicator"
    echo "  3. Click 'AWS Details' then 'Show' next to AWS CLI"
    echo "  4. Copy the credentials and export them:"
    echo ""
    echo "  export AWS_ACCESS_KEY_ID=your-key"
    echo "  export AWS_SECRET_ACCESS_KEY=your-secret"
    echo "  export AWS_SESSION_TOKEN=your-token"
    echo "  export AWS_DEFAULT_REGION=us-east-1"
    exit 1
fi

ACCOUNT_ID=$(aws sts get-caller-identity --query "Account" --output text)
echo "  Account: $ACCOUNT_ID"
echo "  Region:  $REGION"
echo ""

# Get latest Amazon Linux 2023 AMI
echo "Finding latest Amazon Linux 2023 AMI..."
AMI_ID=$(aws ec2 describe-images \
    --owners amazon \
    --filters "Name=name,Values=al2023-ami-2023.*-x86_64" \
              "Name=state,Values=available" \
    --query "sort_by(Images, &CreationDate)[-1].ImageId" \
    --output text)
echo "  AMI: $AMI_ID"

# Create key pair (if not exists)
if ! aws ec2 describe-key-pairs --key-names "$KEY_NAME" > /dev/null 2>&1; then
    echo "Creating SSH key pair..."
    aws ec2 create-key-pair \
        --key-name "$KEY_NAME" \
        --query "KeyMaterial" \
        --output text > "${KEY_NAME}.pem"
    chmod 400 "${KEY_NAME}.pem"
    echo "  Key saved to ${KEY_NAME}.pem"
else
    echo "  Using existing key pair: $KEY_NAME"
fi

# Create security group (if not exists)
VPC_ID=$(aws ec2 describe-vpcs \
    --filters "Name=isDefault,Values=true" \
    --query "Vpcs[0].VpcId" \
    --output text)

SG_ID=$(aws ec2 describe-security-groups \
    --filters "Name=group-name,Values=$SG_NAME" "Name=vpc-id,Values=$VPC_ID" \
    --query "SecurityGroups[0].GroupId" \
    --output text 2>/dev/null || echo "None")

if [ "$SG_ID" = "None" ] || [ "$SG_ID" = "" ]; then
    echo "Creating security group..."
    SG_ID=$(aws ec2 create-security-group \
        --group-name "$SG_NAME" \
        --description "Lab 09 - Distributed File Systems" \
        --vpc-id "$VPC_ID" \
        --query "GroupId" \
        --output text)

    # Allow SSH
    aws ec2 authorize-security-group-ingress \
        --group-id "$SG_ID" \
        --protocol tcp --port 22 --cidr 0.0.0.0/0 > /dev/null

    # Allow MinIO Console
    aws ec2 authorize-security-group-ingress \
        --group-id "$SG_ID" \
        --protocol tcp --port 9001 --cidr 0.0.0.0/0 > /dev/null

    echo "  Security group: $SG_ID (SSH + MinIO Console)"
else
    echo "  Using existing security group: $SG_ID"
fi

# User data script to install Docker and run the lab
USER_DATA=$(cat <<'USERDATA'
#!/bin/bash
set -ex

# Install Docker
dnf update -y
dnf install -y docker git
systemctl enable docker
systemctl start docker
usermod -aG docker ec2-user

# Install Docker Compose plugin
mkdir -p /usr/local/lib/docker/cli-plugins
curl -fsSL "https://github.com/docker/compose/releases/latest/download/docker-compose-linux-$(uname -m)" \
    -o /usr/local/lib/docker/cli-plugins/docker-compose
chmod +x /usr/local/lib/docker/cli-plugins/docker-compose

# Clone the repo and run the lab as ec2-user
su - ec2-user -c '
    git clone https://github.com/gamaware/system-design-course.git
    cd system-design-course/09-distributed-file-systems
    chmod +x setup.sh cleanup.sh scripts/*.sh
    ./setup.sh
'

# Signal that setup is complete
touch /home/ec2-user/LAB_READY
USERDATA
)

# Launch EC2 instance
echo ""
echo "Launching EC2 instance ($INSTANCE_TYPE)..."
INSTANCE_ID=$(aws ec2 run-instances \
    --image-id "$AMI_ID" \
    --instance-type "$INSTANCE_TYPE" \
    --key-name "$KEY_NAME" \
    --security-group-ids "$SG_ID" \
    --user-data "$USER_DATA" \
    --tag-specifications "ResourceType=instance,Tags=[{Key=Name,Value=$TAG_NAME}]" \
    --query "Instances[0].InstanceId" \
    --output text)

echo "  Instance ID: $INSTANCE_ID"

# Wait for instance to be running
echo "Waiting for instance to be running..."
aws ec2 wait instance-running --instance-ids "$INSTANCE_ID"

# Get public IP
PUBLIC_IP=$(aws ec2 describe-instances \
    --instance-ids "$INSTANCE_ID" \
    --query "Reservations[0].Instances[0].PublicIpAddress" \
    --output text)

echo ""
echo "=== EC2 Instance Ready ==="
echo ""
echo "  Instance ID: $INSTANCE_ID"
echo "  Public IP:   $PUBLIC_IP"
echo ""
echo "  SSH into the instance:"
echo "    ssh -i ${KEY_NAME}.pem ec2-user@$PUBLIC_IP"
echo ""
echo "  Docker and the lab are being installed automatically."
echo "  Wait 2-3 minutes, then SSH in and check:"
echo "    ls ~/LAB_READY     # exists when setup is complete"
echo ""
echo "  The lab runs at:"
echo "    cd ~/system-design-course/09-distributed-file-systems"
echo "    Follow LAB.md for the full walkthrough."
echo ""
echo "  MinIO Console (after setup completes):"
echo "    http://$PUBLIC_IP:9001"
echo "    User: minioadmin / Password: minioadmin123"
echo ""
echo "  When done, clean up:"
echo "    bash cleanup-ec2.sh"
