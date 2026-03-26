# Lab 08 -- macOS/Linux Instructions

> For an overview, architecture diagrams, and key concepts, see [README.md](README.md).
> For Windows/PowerShell, see [LAB-WINDOWS.md](LAB-WINDOWS.md).

## Prerequisites

### Required Tools

You need three tools installed on your machine. Follow the instructions for your
operating system.

#### AWS CLI v2

The AWS Command Line Interface is how you interact with AWS from your terminal.

**macOS (recommended -- official `.pkg` installer):**

Download the official installer from the
[AWS CLI install page](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html)
and run the `.pkg` file. This installs to `/usr/local/aws-cli` and creates a
symlink in `/usr/local/bin`.

Alternatively, if you already have Homebrew:

```bash
brew install awscli
```

**Linux (Ubuntu/Debian):**

```bash
curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
unzip awscliv2.zip
sudo ./aws/install
rm -rf aws awscliv2.zip
```

**Verify the installation:**

```bash
aws --version
```

Expected output (version may differ):

```text
aws-cli/2.x.x Python/3.x.x ...
```

#### Terraform

Terraform is an open-source IaC tool that lets you define infrastructure in
declarative configuration files.

**macOS (recommended -- binary download):**

Download the binary for your architecture from the
[Terraform install page](https://developer.hashicorp.com/terraform/install). Unzip
it and move the `terraform` binary to a directory in your PATH:

```bash
unzip terraform_*_darwin_*.zip
sudo mv terraform /usr/local/bin/
```

Alternatively, if you already have Homebrew:

```bash
brew tap hashicorp/tap
brew install hashicorp/tap/terraform
```

**Linux (recommended -- binary download):**

```bash
curl -fsSL \
  https://releases.hashicorp.com/terraform/1.12.1/terraform_1.12.1_linux_amd64.zip \
  -o terraform.zip
unzip terraform.zip
sudo mv terraform /usr/local/bin/
rm terraform.zip
```

Alternatively, add the HashiCorp APT or YUM repository:

```bash
wget -O - https://apt.releases.hashicorp.com/gpg \
  | sudo gpg --dearmor -o /usr/share/keyrings/hashicorp-archive-keyring.gpg
echo "deb [signed-by=/usr/share/keyrings/hashicorp-archive-keyring.gpg] \
  https://apt.releases.hashicorp.com $(lsb_release -cs) main" \
  | sudo tee /etc/apt/sources.list.d/hashicorp.list
sudo apt update && sudo apt install terraform
```

**Verify the installation:**

```bash
terraform --version
```

Expected output:

```text
Terraform v1.x.x
```

#### SSH Client

SSH is pre-installed on macOS and Linux. No additional installation is needed.

### AWS Academy Learner Lab Credentials

This lab uses the AWS Academy Learner Lab sandbox. Credentials are temporary and
expire when your lab session ends.

**Step 1:** Log in to your AWS Academy course on Canvas.

**Step 2:** Open the **Learner Lab** module and click **Start Lab**. Wait for the
status indicator to turn green.

**Step 3:** Click **AWS Details** (to the right of the Start Lab button). You will
see three values:

- `AWS_ACCESS_KEY_ID`
- `AWS_SECRET_ACCESS_KEY`
- `AWS_SESSION_TOKEN`

Copy all three values. You can also download them as a file by clicking **Show**
next to "AWS CLI" and copying the entire block.

**Step 4:** Export these as environment variables in your terminal. Do **not** use
`aws configure` -- these are ephemeral credentials that expire after your session.

```bash
export AWS_ACCESS_KEY_ID="YOUR_ACCESS_KEY_ID"
export AWS_SECRET_ACCESS_KEY="YOUR_SECRET_ACCESS_KEY"
export AWS_SESSION_TOKEN="YOUR_SESSION_TOKEN"
export AWS_DEFAULT_REGION="us-east-1"
```

> **Why environment variables instead of `aws configure`?**
>
> `aws configure` writes credentials to `~/.aws/credentials`, which persists after
> the session ends. When the Learner Lab session expires, those stale credentials
> cause confusing errors. Environment variables are automatically cleared when you
> close the terminal -- matching the ephemeral nature of the credentials.

**Step 5:** Verify your identity:

```bash
aws sts get-caller-identity
```

Expected output (account number will differ):

```json
{
    "UserId": "AROA...:user...",
    "Account": "123456789012",
    "Arn": "arn:aws:sts::123456789012:assumed-role/..."
}
```

### Prior Knowledge

- Completion of [Lab 07 -- Networking](../07-networking/) is recommended. This lab
  references concepts from that lab (network interfaces, routing tables,
  connectivity testing).
- Basic terminal/command line familiarity.

## Quick Start

```bash
cd 08-cloud-networking-vpc
chmod +x setup.sh cleanup.sh scripts/validate-connectivity.sh
./setup.sh
```

Then follow the task instructions below to create the key pair, security group,
and deploy EC2 instances.

---

## Task 1: Verify Prerequisites

Before starting, confirm all tools are installed and credentials are active.

### Step 1.1: Verify AWS CLI

```bash
aws --version
```

### Step 1.2: Verify Terraform

```bash
terraform --version
```

### Step 1.3: Verify AWS credentials

```bash
aws sts get-caller-identity
```

You should see your account ID and ARN. If you get an error about expired
credentials, go back to AWS Academy Learner Lab, click **AWS Details**, and
re-export the environment variables.

> **Question:** What does the `Arn` field in the output tell you about your
> identity?
>
> **Hint:** The ARN shows you are using an assumed role from the Learner Lab,
> not a permanent IAM user. This is why the credentials are temporary.

---

## Task 2: Deploy VPC Network with CloudFormation

> **Why CloudFormation?**
>
> CloudFormation is AWS's native Infrastructure as Code service. You write a
> YAML template describing your desired infrastructure, and AWS creates or
> updates all resources to match. It is declarative -- you describe WHAT you
> want, not HOW to create it. For your final project, CloudFormation is ideal
> when your infrastructure is 100% on AWS and you want tight integration with
> AWS services.

In this task, you deploy the network foundation: a VPC with two public subnets,
an Internet Gateway, and route tables. All of this is defined in a single
CloudFormation template.

### Step 2.1: Review the CloudFormation template

Open `cloudformation/vpc-network.yaml` and read through it. The template creates
these resources:

| Resource | Purpose |
| --- | --- |
| `AWS::EC2::VPC` | The virtual network (`10.0.0.0/16`) |
| `AWS::EC2::InternetGateway` | Enables internet access for the VPC |
| `AWS::EC2::Subnet` (x2) | Public Subnet A and C in different AZs |
| `AWS::EC2::RouteTable` | Routes traffic -- `0.0.0.0/0` goes to the IGW |
| `AWS::EC2::SubnetRouteTableAssociation` (x2) | Links each subnet to the route table |

> **Question:** Which CloudFormation resource is the equivalent of running
> `ip route add default via 172.16.238.1` in Lab 07?
>
> **Hint:** Look for `AWS::EC2::Route` with `DestinationCidrBlock: 0.0.0.0/0`.
> This declarative route entry does the same thing as the imperative `ip route`
> command -- it tells the system where to send traffic that does not match any
> local subnet.

### Step 2.2: Deploy the stack

```bash
./setup.sh
```

Or deploy manually:

```bash
aws cloudformation deploy \
  --template-file cloudformation/vpc-network.yaml \
  --stack-name vpc-lab-network
```

The deployment takes about 1-2 minutes. You will see output showing the stack
creation progress.

### Step 2.3: Verify the stack outputs

```bash
aws cloudformation describe-stacks \
  --stack-name vpc-lab-network \
  --query 'Stacks[0].Outputs[*].[OutputKey,OutputValue]' \
  --output table
```

You should see five outputs: `VpcId`, `InternetGatewayId`, `PublicSubnetAId`,
`PublicSubnetCId`, and `PublicRouteTableId`.

### Step 2.4: Inspect resources in the AWS Console

Open the VPC Console and walk through the resources CloudFormation created:

1. Open [https://console.aws.amazon.com/vpc](https://console.aws.amazon.com/vpc)
   in your browser.
2. Click **Your VPCs** in the left sidebar. Find **VPC-Lab** and note the VPC ID.
   Confirm the CIDR is `10.0.0.0/16`.
3. Click **Subnets** in the left sidebar. Verify you see two subnets:
   - **public subnet A** with CIDR `10.0.10.0/24` in `us-east-1a`
   - **public subnet C** with CIDR `10.0.20.0/24` in `us-east-1c`
4. Click **Route Tables** in the left sidebar. Find the public route table and
   verify it has a route `0.0.0.0/0` pointing to `igw-xxx` (the Internet
   Gateway).
5. Click **Internet Gateways** in the left sidebar. Verify the gateway is
   **attached** to VPC-Lab.

### Step 2.5: (Optional) Verify via CLI

List the subnets in your new VPC using the CLI:

```bash
VPC_ID=$(aws cloudformation describe-stacks \
  --stack-name vpc-lab-network \
  --query 'Stacks[0].Outputs[?OutputKey==`VpcId`].OutputValue' \
  --output text)

aws ec2 describe-subnets \
  --filters "Name=vpc-id,Values=$VPC_ID" \
  --query 'Subnets[*].[Tags[?Key==`Name`].Value|[0],CidrBlock,AvailabilityZone]' \
  --output table
```

You should see two subnets in different Availability Zones:

```text
-------------------------------------------------
|                DescribeSubnets                |
+------------------+---------------+------------+
|  public subnet A |  10.0.10.0/24 |  us-east-1a|
|  public subnet C |  10.0.20.0/24 |  us-east-1c|
+------------------+---------------+------------+
```

> **Question:** Why are the subnets in different Availability Zones?
>
> **Hint:** Availability Zones are physically separate data centers within
> an AWS Region. Placing subnets in different AZs provides high availability --
> if one AZ has an outage, resources in the other AZ remain operational.

---

## Task 3: Create a Key Pair via AWS CLI

> **Why the AWS CLI?**
>
> The AWS CLI is an imperative tool -- you tell AWS exactly what to do, step
> by step. It is great for one-off operations, quick experiments, and tasks
> that do not need to be repeated. For your final project, use the CLI for
> debugging and ad-hoc operations, but prefer IaC tools for reproducible
> infrastructure.

A key pair lets you SSH into your EC2 instances. You will create one using the
AWS CLI.

### Step 3.1: Create the key pair

```bash
aws ec2 create-key-pair \
  --key-name vpc-lab-key \
  --query 'KeyMaterial' \
  --output text > vpc-lab-key.pem
```

### Step 3.2: Set file permissions

```bash
chmod 400 vpc-lab-key.pem
```

### Step 3.3: Verify the key pair exists

```bash
aws ec2 describe-key-pairs --key-names vpc-lab-key
```

> **Question:** Why must the `.pem` file have `400` permissions (read-only
> for the owner)?
>
> **Hint:** SSH refuses to use a private key file that other users can read.
> This is a security feature -- if the key were world-readable, any user on
> the system could impersonate you. The `400` permission means only the file
> owner can read it, and nobody can write to it.

---

## Task 4: Create a Security Group via AWS CLI

A security group acts as a virtual firewall for your EC2 instances. You will
create one that allows SSH and ICMP (ping) traffic.

### Step 4.1: Get the VPC ID from CloudFormation

```bash
VPC_ID=$(aws cloudformation describe-stacks \
  --stack-name vpc-lab-network \
  --query 'Stacks[0].Outputs[?OutputKey==`VpcId`].OutputValue' \
  --output text)

echo "VPC ID: $VPC_ID"
```

### Step 4.2: Create the security group

```bash
SG_ID=$(aws ec2 create-security-group \
  --group-name vpc-lab-sg \
  --description "Security group for VPC lab EC2 access" \
  --vpc-id "$VPC_ID" \
  --query 'GroupId' \
  --output text)

echo "Security Group ID: $SG_ID"
```

### Step 4.3: Add an ICMP rule (for ping testing)

```bash
aws ec2 authorize-security-group-ingress \
  --group-id "$SG_ID" \
  --protocol icmp \
  --port -1 \
  --cidr 0.0.0.0/0
```

### Step 4.4: Add an SSH rule (restricted to your IP)

```bash
MY_IP=$(curl -s https://checkip.amazonaws.com)

aws ec2 authorize-security-group-ingress \
  --group-id "$SG_ID" \
  --protocol tcp \
  --port 22 \
  --cidr "$MY_IP/32"

echo "SSH allowed from: $MY_IP/32"
```

### Step 4.5: Add an HTTP rule (for web server testing)

```bash
aws ec2 authorize-security-group-ingress \
  --group-id "$SG_ID" \
  --protocol tcp \
  --port 80 \
  --cidr 0.0.0.0/0
```

### Step 4.6: Verify the security group rules

```bash
aws ec2 describe-security-groups \
  --group-ids "$SG_ID" \
  --query 'SecurityGroups[0].IpPermissions[*].[IpProtocol,FromPort,ToPort,IpRanges[0].CidrIp]' \
  --output table
```

> **Question:** Why do we restrict SSH to your specific IP (`/32`) instead of
> opening it to `0.0.0.0/0` (the entire internet)?
>
> **Hint:** Opening SSH to the world is one of the most common security
> mistakes in cloud infrastructure. Anyone on the internet could attempt to
> brute-force your instance. Restricting to your IP means only your machine
> can connect. This follows the principle of least privilege.

<!-- -->

> **Question:** How does this security group compare to network isolation in
> Lab 07?
>
> **Hint:** In Lab 07, Docker bridge networks isolated containers by default --
> only containers on the same bridge could communicate. In AWS, security groups
> serve a similar role: they define which traffic is allowed to reach an
> instance. The key difference is that security groups are stateful -- if you
> allow inbound traffic, the response is automatically allowed outbound.

---

## Task 5: Deploy EC2 Instances with Terraform

> **Why Terraform?**
>
> Terraform is an open-source IaC tool by HashiCorp that works across ALL cloud
> providers (AWS, Azure, GCP). Like CloudFormation, it is declarative, but it
> adds a `plan` step that shows you exactly what will change before applying.
> For your final project, Terraform is ideal if you want multi-cloud support or
> prefer its plan-before-apply workflow.

Now you will use Terraform to launch two EC2 instances -- one in each public
subnet. Terraform reads the CloudFormation stack outputs and the CLI-created
security group to place the instances in the right network.

### Step 5.1: Review the Terraform configuration

Open `terraform/main.tf` and read through it. Key elements:

- **`data "aws_cloudformation_stack"`** -- reads VPC and subnet IDs from the
  CloudFormation stack. This is how Terraform "talks to" CloudFormation.
- **`data "aws_security_group"`** -- finds the security group you created via
  the CLI.
- **`data "aws_ami"`** -- dynamically finds the latest Amazon Linux 2023 AMI.
- **`resource "aws_instance"`** -- defines the two EC2 instances with a
  `user_data` script that installs and starts a web server.

> **Question:** Why does the Terraform config **not** define the VPC, subnets,
> or security group?
>
> **Hint:** Those resources are managed by CloudFormation and the CLI. Terraform
> only manages the EC2 instances. It **reads** the other resources as data
> sources. This demonstrates that different IaC tools can work together -- each
> managing its own piece of the infrastructure.

### Step 5.2: Create your variable file

```bash
cd terraform
cp terraform.tfvars.example terraform.tfvars
```

The default values should work. If you used a different key pair name in Task 3,
edit `terraform.tfvars` to match.

### Step 5.3: Initialize Terraform

```bash
terraform init
```

This downloads the AWS provider plugin. You only need to run this once.

Expected output:

```text
Terraform has been successfully initialized!
```

### Step 5.4: Preview the deployment plan

```bash
terraform plan
```

Terraform shows you exactly what it will create **before** making any changes.
You should see **2 resources to add** (the two EC2 instances).

> **Question:** What does `terraform plan` show you that
> `aws cloudformation deploy` does not provide?
>
> **Hint:** CloudFormation deploys directly -- you see the result after the
> fact. Terraform's `plan` command shows a detailed preview of every resource
> that will be created, modified, or destroyed **before** any action is taken.
> This gives you a chance to review and catch mistakes.

### Step 5.5: Apply the configuration

```bash
terraform apply
```

Type `yes` when prompted. Terraform creates both EC2 instances. This takes
about 30-60 seconds.

### Step 5.6: Note the output values

After the apply completes, Terraform prints the instance details:

```bash
terraform output
```

Record the `ec2_1_public_ip` and `ec2_2_public_ip` values -- you will need them
for connectivity testing.

### Step 5.7: Verify EC2 instances in the AWS Console

Open the EC2 Console and confirm both instances are running:

1. Open [https://console.aws.amazon.com/ec2](https://console.aws.amazon.com/ec2)
   in your browser.
2. Click **Instances** in the left sidebar.
3. You should see two instances named **EC2-1** and **EC2-2**, both in the
   **running** state.
4. Click on **EC2-1** and verify:
   - **Availability Zone** is `us-east-1a`
   - **VPC ID** matches the VPC-Lab VPC
   - **Subnet ID** matches public subnet A
   - **Public IPv4 address** matches the Terraform output
   - **Security groups** shows `vpc-lab-sg`
5. Repeat for **EC2-2**, confirming it is in `us-east-1c` and public subnet C.

### Step 5.8: (Optional) Verify via CLI

```bash
QUERY='Reservations[*].Instances[*]'
QUERY="$QUERY.[Tags[?Key==\`Name\`].Value|[0],"
QUERY="$QUERY PublicIpAddress,"
QUERY="$QUERY Placement.AvailabilityZone,"
QUERY="$QUERY State.Name]"

aws ec2 describe-instances \
  --filters "Name=tag:Name,Values=EC2-1,EC2-2" \
  --query "$QUERY" \
  --output table
```

---

## Task 6: Test Connectivity

Now test that your instances can communicate with each other and the internet,
using the same networking commands from Lab 07.

### Step 6.1: SSH into EC2-1

```bash
ssh -i ../vpc-lab-key.pem ec2-user@<EC2-1-PUBLIC-IP>
```

Replace `<EC2-1-PUBLIC-IP>` with the actual IP from Terraform output. Type
`yes` to accept the host key on first connection.

### Step 6.2: Explore the network configuration

Run the same commands you used in Lab 07:

```bash
# View network interfaces
ip a

# View routing table
ip r
```

> **Question:** How many interfaces does this EC2 instance have? What is the
> default gateway?
>
> **Hint:** Unlike the Docker lab where containers had multiple interfaces
> (`eth0`, `eth1`), EC2 instances typically have one interface (`eth0`) with
> a private IP from the subnet CIDR (e.g., `10.0.10.x`). The default gateway
> is automatically set to the first IP in the subnet (`10.0.10.1`) -- you did
> **not** need to run `ip route add` like in Lab 07. AWS configures this via
> DHCP.

### Step 6.3: Ping EC2-2 from EC2-1

```bash
ping -c 4 <EC2-2-PUBLIC-IP>
```

You should see successful ping responses. This confirms cross-Availability Zone
communication over ICMP, allowed by the security group rule you created.

### Step 6.4: Test internet connectivity

```bash
curl example.com
```

You should see HTML output from example.com. This confirms that the route table
entry (`0.0.0.0/0` -> Internet Gateway) is working -- traffic from EC2-1 reaches
the internet through the IGW.

### Step 6.5: Test the local web server

```bash
curl localhost
```

You should see:

```html
<html><body><h1>EC2-1</h1><p>Instance: i-xxxxx</p><p>AZ: us-east-1a</p></body></html>
```

> **Note:** If `curl localhost` returns an empty response, the instance is
> still installing the web server. The `user-data.sh` bootstrap script takes
> about 30-40 seconds to install and start Apache after the instance
> launches. Wait a minute and try again.

### Step 6.6: Exit and connect to EC2-2

```bash
exit
ssh -i ../vpc-lab-key.pem ec2-user@<EC2-2-PUBLIC-IP>
```

Repeat the same tests (`ip a`, `ip r`, `ping`, `curl`) on EC2-2 to verify
both instances are fully functional.

> **Question:** Both instances can ping each other across Availability Zones.
> Which AWS resource controls whether this traffic is allowed?
>
> **Hint:** The security group. You added an ICMP inbound rule that allows
> ping from `0.0.0.0/0`. If you removed that rule, pings would stop working
> even though the network path (subnets, route tables, IGW) is unchanged.
> Security groups operate at the instance level, not the network level.

```bash
exit
```

---

## Task 7: Infrastructure as Code Comparison

Now that you have used three different tools to build the same infrastructure,
reflect on their differences.

### Step 7.1: Fill in the comparison table

Copy this table and fill in each cell based on your experience:

| Aspect | AWS Console | CloudFormation | AWS CLI | Terraform |
| --- | --- | --- | --- | --- |
| Approach | ? | ? | ? | ? |
| Reproducibility | ? | ? | ? | ? |
| Version control friendly | ? | ? | ? | ? |
| Preview before changes | ? | ? | ? | ? |
| Rollback support | ? | ? | ? | ? |
| Cross-tool integration | ? | ? | ? | ? |

> **Question:** If you needed to create this exact VPC in 5 different AWS
> regions, which tool(s) would you use and why?
>
> **Hint:** CloudFormation and Terraform both support parameterized
> deployments -- you could change the region and redeploy the same template.
> The console would require clicking through the same steps 5 times. The CLI
> could be scripted but lacks the state tracking that Terraform provides.

---

## Task 8: Cleanup

Delete all resources to avoid charges. The order matters -- EC2 instances must
be deleted before the VPC network they depend on.

### Option A: Automated cleanup

```bash
./cleanup.sh
```

### Option B: Manual cleanup

**Step 8.1:** Destroy Terraform resources (EC2 instances):

```bash
cd terraform
terraform destroy
```

Type `yes` when prompted.

**Step 8.2:** Delete the security group:

```bash
cd ..
VPC_ID=$(aws cloudformation describe-stacks \
  --stack-name vpc-lab-network \
  --query 'Stacks[0].Outputs[?OutputKey==`VpcId`].OutputValue' \
  --output text)

SG_ID=$(aws ec2 describe-security-groups \
  --filters "Name=group-name,Values=vpc-lab-sg" "Name=vpc-id,Values=$VPC_ID" \
  --query 'SecurityGroups[0].GroupId' \
  --output text)

aws ec2 delete-security-group --group-id "$SG_ID"
```

**Step 8.3:** Delete the key pair:

```bash
aws ec2 delete-key-pair --key-name vpc-lab-key
rm -f vpc-lab-key.pem
```

**Step 8.4:** Delete the CloudFormation stack:

```bash
aws cloudformation delete-stack --stack-name vpc-lab-network
aws cloudformation wait stack-delete-complete --stack-name vpc-lab-network
```

**Step 8.5:** Verify everything is deleted:

```bash
aws ec2 describe-vpcs \
  --filters "Name=tag:Name,Values=VPC-Lab" \
  --query 'Vpcs[*].VpcId' \
  --output text
```

This should return no results.

---

## Troubleshooting

| Symptom | Cause | Fix |
| --- | --- | --- |
| `aws sts get-caller-identity` fails | Expired or missing credentials | Re-export env vars from AWS Academy Learner Lab |
| CloudFormation stack fails with AZ error | AZ `c` not available in region | Change `!Select [2, ...]` to `[1, ...]` in template for AZ `b` |
| `terraform init` fails | No internet or provider registry unreachable | Check internet connection; retry |
| `terraform plan` cannot find security group | SG not created yet or wrong name | Complete Task 4 before running Terraform |
| SSH `Permission denied (publickey)` | Wrong key file or permissions | Verify `chmod 400 vpc-lab-key.pem` and correct key name |
| SSH `Connection timed out` | Security group SSH rule missing your IP | Re-run Step 4.4 with your current IP |
| Ping between instances fails | ICMP rule not added to security group | Verify the ICMP rule exists (Step 4.6) |
| `cleanup.sh` fails | Resources already partially deleted | Run individual delete commands from Option B |
