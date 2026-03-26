terraform {
  required_version = ">= 1.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

# ---------------------------------------------------------------------------
# Data sources: read CloudFormation stack outputs and CLI-created resources
# ---------------------------------------------------------------------------

data "aws_cloudformation_stack" "vpc" {
  name = var.cf_stack_name
}

data "aws_security_group" "vpc_lab_sg" {
  filter {
    name   = "group-name"
    values = [var.security_group_name]
  }

  filter {
    name   = "vpc-id"
    values = [data.aws_cloudformation_stack.vpc.outputs["VpcId"]]
  }
}

data "aws_ami" "amazon_linux_2023" {
  most_recent = true
  owners      = ["amazon"]

  filter {
    name   = "name"
    values = ["al2023-ami-2023.*-x86_64"]
  }

  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }

  filter {
    name   = "architecture"
    values = ["x86_64"]
  }
}

# ---------------------------------------------------------------------------
# EC2 Instances
# ---------------------------------------------------------------------------

resource "aws_instance" "ec2_1" {
  ami                         = data.aws_ami.amazon_linux_2023.id
  instance_type               = var.instance_type
  subnet_id                   = data.aws_cloudformation_stack.vpc.outputs["PublicSubnetAId"]
  vpc_security_group_ids      = [data.aws_security_group.vpc_lab_sg.id]
  key_name                    = var.key_pair_name
  associate_public_ip_address = true

  user_data = templatefile("${path.module}/user-data.sh", {
    instance_name = "EC2-1"
  })

  tags = {
    Name = "EC2-1"
  }
}

resource "aws_instance" "ec2_2" {
  ami                         = data.aws_ami.amazon_linux_2023.id
  instance_type               = var.instance_type
  subnet_id                   = data.aws_cloudformation_stack.vpc.outputs["PublicSubnetCId"]
  vpc_security_group_ids      = [data.aws_security_group.vpc_lab_sg.id]
  key_name                    = var.key_pair_name
  associate_public_ip_address = true

  user_data = templatefile("${path.module}/user-data.sh", {
    instance_name = "EC2-2"
  })

  tags = {
    Name = "EC2-2"
  }
}
