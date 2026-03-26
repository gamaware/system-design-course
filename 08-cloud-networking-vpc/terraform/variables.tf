variable "aws_region" {
  description = "AWS region where resources are deployed"
  type        = string
  default     = "us-east-1"
}

variable "cf_stack_name" {
  description = "Name of the CloudFormation stack that created the VPC"
  type        = string
  default     = "vpc-lab-network"
}

variable "key_pair_name" {
  description = "Name of the EC2 key pair created via AWS CLI"
  type        = string
}

variable "security_group_name" {
  description = "Name of the security group created via AWS CLI"
  type        = string
  default     = "vpc-lab-sg"
}

variable "instance_type" {
  description = "EC2 instance type (t2.micro is Free Tier eligible)"
  type        = string
  default     = "t2.micro"
}
