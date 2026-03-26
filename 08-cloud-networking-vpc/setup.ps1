# setup.ps1 — Lab 08 initial infrastructure deployment (Windows/PowerShell)
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
# Usage: .\setup.ps1

$ErrorActionPreference = "Stop"

$STACK_NAME = "vpc-lab-network"

Write-Output "========================================="
Write-Output "Lab 08 — Cloud Networking VPC Setup"
Write-Output "========================================="
Write-Output ""

# --- Prerequisite checks ---
Write-Output "Checking prerequisites..."

try {
    $awsVersion = aws --version 2>&1
    Write-Output "  AWS CLI: $awsVersion"
} catch {
    Write-Output "ERROR: AWS CLI not found. Install it first (see LAB-WINDOWS Task 1)."
    exit 1
}

try {
    $tfVersion = terraform --version 2>&1 | Select-Object -First 1
    Write-Output "  Terraform: $tfVersion"
} catch {
    Write-Output "ERROR: Terraform not found. Install it first (see LAB-WINDOWS Task 1)."
    exit 1
}

Write-Output ""
Write-Output "Verifying AWS credentials..."
try {
    aws sts get-caller-identity --output table
} catch {
    Write-Output "ERROR: AWS credentials not configured."
    Write-Output "Set your AWS Academy Learner Lab credentials as environment variables."
    Write-Output "See LAB-WINDOWS Task 1 for instructions."
    exit 1
}
Write-Output ""

# --- Deploy CloudFormation stack ---
Write-Output "Deploying CloudFormation stack: $STACK_NAME ..."
Write-Output "This creates: VPC, 2 public subnets, Internet Gateway, route tables."
Write-Output ""

aws cloudformation deploy `
    --template-file cloudformation\vpc-network.yaml `
    --stack-name $STACK_NAME `
    --no-fail-on-empty-changeset

Write-Output ""
Write-Output "Waiting for stack to complete..."
aws cloudformation wait stack-create-complete --stack-name $STACK_NAME 2>$null

# --- Show outputs ---
Write-Output ""
Write-Output "CloudFormation stack outputs:"
aws cloudformation describe-stacks `
    --stack-name $STACK_NAME `
    --query 'Stacks[0].Outputs[*].[OutputKey,OutputValue]' `
    --output table

# --- Initialize Terraform ---
Write-Output ""
Write-Output "Initializing Terraform..."
Push-Location terraform
terraform init -input=false
Pop-Location

Write-Output ""
Write-Output "========================================="
Write-Output "Network infrastructure deployed!"
Write-Output "========================================="
Write-Output ""
Write-Output "Next steps (see LAB-WINDOWS for full instructions):"
Write-Output ""
Write-Output "  1. Create a key pair:"
Write-Output "     aws ec2 create-key-pair --key-name vpc-lab-key ``"
Write-Output "       --query 'KeyMaterial' --output text > vpc-lab-key.pem"
Write-Output ""
Write-Output "  2. Create a security group (see LAB-WINDOWS Task 4)"
Write-Output ""
Write-Output "  3. Deploy EC2 instances:"
Write-Output "     cd terraform"
Write-Output "     Copy-Item terraform.tfvars.example terraform.tfvars"
Write-Output "     terraform plan"
Write-Output "     terraform apply"
Write-Output ""
