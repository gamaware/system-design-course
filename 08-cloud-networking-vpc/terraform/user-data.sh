#!/bin/bash
# user-data.sh — EC2 instance bootstrap script
#
# This script runs automatically when the EC2 instance first launches.
# It installs and starts the Apache web server (httpd), then creates a
# simple HTML page displaying the instance ID and Availability Zone.
# This page is used in Task 6 to verify that both instances are running
# and serving traffic from different AZs.

dnf install -y httpd
systemctl start httpd
systemctl enable httpd

INSTANCE_ID=$(ec2-metadata -i | cut -d' ' -f2)
AZ=$(ec2-metadata -z | cut -d' ' -f2)
HOSTNAME=$(hostname)

cat > /var/www/html/index.html <<HTML
<html>
<body>
  <h1>${instance_name}</h1>
  <p>Instance: $INSTANCE_ID</p>
  <p>AZ: $AZ</p>
  <p>Hostname: $HOSTNAME</p>
</body>
</html>
HTML
