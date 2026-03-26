# cleanup.ps1 — Lab 08 full resource teardown (Windows/PowerShell)
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
# Usage: .\cleanup.ps1

$ErrorActionPreference = "Stop"

$STACK_NAME = "vpc-lab-network"
$KEY_NAME = "vpc-lab-key"
$SG_NAME = "vpc-lab-sg"

Write-Output "========================================="
Write-Output "Lab 08 — Cleanup"
Write-Output "========================================="
Write-Output ""

# --- Step 1: Destroy Terraform resources (EC2 instances) ---
Write-Output "Step 1: Destroying Terraform-managed resources (EC2 instances)..."
Push-Location terraform
if (Test-Path terraform.tfstate) {
    terraform destroy -auto-approve
} else {
    Write-Output "  No Terraform state found, skipping."
}
Pop-Location

# --- Step 2: Delete security group ---
Write-Output ""
Write-Output "Step 2: Deleting security group..."
try {
    $VPC_ID = aws cloudformation describe-stacks `
        --stack-name $STACK_NAME `
        --query 'Stacks[0].Outputs[?OutputKey==``VpcId``].OutputValue' `
        --output text 2>$null
} catch {
    $VPC_ID = ""
}

if ($VPC_ID -and $VPC_ID -ne "None") {
    try {
        $SG_ID = aws ec2 describe-security-groups `
            --filters "Name=group-name,Values=$SG_NAME" "Name=vpc-id,Values=$VPC_ID" `
            --query 'SecurityGroups[0].GroupId' `
            --output text 2>$null
    } catch {
        $SG_ID = "None"
    }

    if ($SG_ID -and $SG_ID -ne "None") {
        aws ec2 delete-security-group --group-id $SG_ID
        Write-Output "  Deleted security group: $SG_ID"
    } else {
        Write-Output "  Security group not found, skipping."
    }
} else {
    Write-Output "  CloudFormation stack not found, skipping security group."
}

# --- Step 3: Delete key pair ---
Write-Output ""
Write-Output "Step 3: Deleting key pair..."
try {
    aws ec2 describe-key-pairs --key-names $KEY_NAME 2>$null | Out-Null
    aws ec2 delete-key-pair --key-name $KEY_NAME
    Write-Output "  Deleted key pair: $KEY_NAME"
} catch {
    Write-Output "  Key pair not found, skipping."
}

if (Test-Path "vpc-lab-key.pem") {
    Remove-Item -Force "vpc-lab-key.pem"
    Write-Output "  Removed local vpc-lab-key.pem file."
}

# --- Step 4: Delete CloudFormation stack ---
Write-Output ""
Write-Output "Step 4: Deleting CloudFormation stack: $STACK_NAME ..."
try {
    aws cloudformation describe-stacks --stack-name $STACK_NAME 2>$null | Out-Null
    aws cloudformation delete-stack --stack-name $STACK_NAME
    Write-Output "  Waiting for stack deletion (this may take a few minutes)..."
    aws cloudformation wait stack-delete-complete --stack-name $STACK_NAME
    Write-Output "  Stack deleted."
} catch {
    Write-Output "  Stack not found, skipping."
}

Write-Output ""
Write-Output "========================================="
Write-Output "Cleanup complete!"
Write-Output "========================================="
Write-Output ""
Write-Output "All AWS resources have been deleted."
