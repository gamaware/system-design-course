output "ec2_1_public_ip" {
  description = "Public IP address of EC2-1 (Public Subnet A)"
  value       = aws_instance.ec2_1.public_ip
}

output "ec2_1_private_ip" {
  description = "Private IP address of EC2-1"
  value       = aws_instance.ec2_1.private_ip
}

output "ec2_2_public_ip" {
  description = "Public IP address of EC2-2 (Public Subnet C)"
  value       = aws_instance.ec2_2.public_ip
}

output "ec2_2_private_ip" {
  description = "Private IP address of EC2-2"
  value       = aws_instance.ec2_2.private_ip
}

output "ec2_1_instance_id" {
  description = "Instance ID of EC2-1"
  value       = aws_instance.ec2_1.id
}

output "ec2_2_instance_id" {
  description = "Instance ID of EC2-2"
  value       = aws_instance.ec2_2.id
}

output "ssh_to_ec2_1" {
  description = "SSH command to connect to EC2-1"
  value       = "ssh -i vpc-lab-key.pem ec2-user@${aws_instance.ec2_1.public_ip}"
}

output "ssh_to_ec2_2" {
  description = "SSH command to connect to EC2-2"
  value       = "ssh -i vpc-lab-key.pem ec2-user@${aws_instance.ec2_2.public_ip}"
}
