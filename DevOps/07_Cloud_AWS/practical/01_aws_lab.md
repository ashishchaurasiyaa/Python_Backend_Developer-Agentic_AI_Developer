# Cloud (AWS) — Hands-On Lab
**DevOps Track · Phase 7 Practical**

## Prerequisites

Be honest with yourself about cost here: most of these labs use AWS Free Tier-eligible resources, but a few (NAT Gateway, RDS Multi-AZ left running, ALB idle time) accrue small hourly charges even on Free Tier if you forget to tear them down. **Every lab ends with a teardown step — actually run it.**

- An AWS account with the AWS CLI configured (`aws configure`) and a non-root IAM user with sufficient permissions (never do hands-on labs as the root account). Free tier covers t2/t3.micro EC2, 750 hours/month for 12 months, and a small RDS allowance.
- **No AWS account / want zero cost**: [LocalStack](https://localstack.cloud/) runs a local emulation of S3, IAM, DynamoDB, SQS/SNS, and more in Docker (`pip install localstack && localstack start`, or `docker run localstack/localstack`) — the CLI commands in Labs 1 and 4 work against it by adding `--endpoint-url=http://localhost:4566`. VPC/EC2/RDS/ALB emulation in LocalStack's free tier is limited, so Labs 2-3 are best done on a real (free-tier) AWS account if you can.
- Set a budget alert before you start anything: AWS Console → Billing → Budgets → create a $5 threshold alert. This costs nothing and will save you from a surprise bill.
- Pick one region and stick with it for all labs, e.g. `ap-south-1` (Mumbai) — set `export AWS_DEFAULT_REGION=ap-south-1` once and forget about it.

---

## Lab 1: IAM Least Privilege and S3 Lifecycle

**Objective:** Write and test a scoped IAM policy the way the lesson describes — one bucket, two verbs, no wildcards — and prove it actually restricts access, not just trust the JSON.

**Task:**
1. Create an S3 bucket with a unique name, enable versioning on it.
2. Write an IAM policy that allows `s3:GetObject` and `s3:PutObject` ONLY on that one bucket (not `s3:*`, not `Resource: "*"`), and explicitly `Deny`s `s3:DeleteObject`.
3. Create an IAM user (or role, if you want to practice assuming a role instead — either is fine for this lab) with ONLY that policy attached, generate access keys for it, and configure a second AWS CLI profile for it.
4. Using the SCOPED profile, upload a file, download it back, and confirm both succeed.
5. Using the SAME scoped profile, attempt to delete the object, and attempt to list/access a DIFFERENT bucket (create a second throwaway bucket first) — confirm both are denied with an `AccessDenied` error, proving the policy's blast radius really is one bucket, two verbs.
6. Add a lifecycle policy to the bucket: objects under prefix `logs/` move to `STANDARD_IA` after 30 days, `GLACIER` after 90, and expire after 365. Apply it and verify with `aws s3api get-bucket-lifecycle-configuration`.
7. Clean up: delete the test objects, the lifecycle policy is harmless to leave but delete the bucket and the IAM user/policy when done to avoid any orphaned credentials lying around.

<details>
<summary>Solution / walkthrough</summary>

```bash
BUCKET="iam-lab-$(whoami)-$(date +%s)"   # unique name, S3 buckets are globally unique
aws s3api create-bucket --bucket "$BUCKET" --region ap-south-1 \
  --create-bucket-configuration LocationConstraint=ap-south-1
aws s3api put-bucket-versioning --bucket "$BUCKET" --versioning-configuration Status=Enabled

cat > scoped-policy.json << EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "AllowGetPutOnOneBucket",
      "Effect": "Allow",
      "Action": ["s3:GetObject", "s3:PutObject"],
      "Resource": "arn:aws:s3:::$BUCKET/*"
    },
    {
      "Sid": "AllowListOnlyThatBucket",
      "Effect": "Allow",
      "Action": "s3:ListBucket",
      "Resource": "arn:aws:s3:::$BUCKET"
    },
    {
      "Sid": "DenyDeleteAlways",
      "Effect": "Deny",
      "Action": "s3:DeleteObject",
      "Resource": "arn:aws:s3:::$BUCKET/*"
    }
  ]
}
EOF

aws iam create-policy --policy-name iam-lab-scoped-policy --policy-document file://scoped-policy.json
POLICY_ARN=$(aws iam list-policies --query "Policies[?PolicyName=='iam-lab-scoped-policy'].Arn" --output text)

aws iam create-user --user-name iam-lab-user
aws iam attach-user-policy --user-name iam-lab-user --policy-arn "$POLICY_ARN"
aws iam create-access-key --user-name iam-lab-user
# note the AccessKeyId and SecretAccessKey from the output

aws configure --profile iam-lab-scoped
# paste in the access key / secret from above, region ap-south-1

# 4. Prove the ALLOWED actions work
echo "test content" > testfile.txt
aws s3 cp testfile.txt "s3://$BUCKET/testfile.txt" --profile iam-lab-scoped
# upload: ./testfile.txt to s3://.../testfile.txt   <- succeeds
aws s3 cp "s3://$BUCKET/testfile.txt" downloaded.txt --profile iam-lab-scoped
# download: s3://.../testfile.txt to ./downloaded.txt   <- succeeds

# 5. Prove the DENIED actions are actually denied
aws s3 rm "s3://$BUCKET/testfile.txt" --profile iam-lab-scoped
# An error occurred (AccessDenied) when calling the DeleteObject operation

SECOND_BUCKET="iam-lab-second-$(date +%s)"
aws s3api create-bucket --bucket "$SECOND_BUCKET" --region ap-south-1 \
  --create-bucket-configuration LocationConstraint=ap-south-1   # using your default/admin profile
aws s3 ls "s3://$SECOND_BUCKET" --profile iam-lab-scoped
# An error occurred (AccessDenied) when calling the ListObjectsV2 operation
# — confirmed: the scoped user can touch exactly ONE bucket, two verbs,
# nothing else, exactly as the policy JSON describes. This is the
# concrete proof behind the lesson's "blast radius" framing.

# 6. Lifecycle policy
cat > lifecycle.json << 'EOF'
{
  "Rules": [
    {
      "ID": "logs-tiering",
      "Filter": {"Prefix": "logs/"},
      "Status": "Enabled",
      "Transitions": [
        {"Days": 30, "StorageClass": "STANDARD_IA"},
        {"Days": 90, "StorageClass": "GLACIER"}
      ],
      "Expiration": {"Days": 365}
    }
  ]
}
EOF
aws s3api put-bucket-lifecycle-configuration --bucket "$BUCKET" --lifecycle-configuration file://lifecycle.json
aws s3api get-bucket-lifecycle-configuration --bucket "$BUCKET"

# 7. Teardown — IMPORTANT, don't skip
aws s3 rm "s3://$BUCKET" --recursive
aws s3api delete-bucket --bucket "$BUCKET"
aws s3api delete-bucket --bucket "$SECOND_BUCKET"
aws iam detach-user-policy --user-name iam-lab-user --policy-arn "$POLICY_ARN"
aws iam list-access-keys --user-name iam-lab-user   # get the key id
aws iam delete-access-key --user-name iam-lab-user --access-key-id <KEY_ID_FROM_ABOVE>
aws iam delete-user --user-name iam-lab-user
aws iam delete-policy --policy-arn "$POLICY_ARN"
```
</details>

---

## Lab 2: Build a 2-AZ VPC With Public/Private Subnets and a Bastion (or SSM) Path

**Objective:** Turn the "sketch it on a whiteboard from memory" senior-tip VPC design into a real, working set of resources, by hand via CLI (not a wizard) so every piece is deliberate.

> This lab creates a NAT Gateway, which has an hourly charge even under Free Tier — budget roughly $0.05-0.10/hour while it's up, and tear down promptly per step 7.

**Task:**
1. Create a VPC (`10.30.0.0/16`), an Internet Gateway, and attach it.
2. Create 2 public subnets and 2 private subnets across 2 AZs (following the CIDR pattern from the Networking phase's Lab 4 — reuse that math here).
3. Create a public route table with a `0.0.0.0/0` route to the IGW, associate both public subnets with it. Create a NAT Gateway in one public subnet (needs an Elastic IP), and a private route table with `0.0.0.0/0` routed to the NAT Gateway, associated with both private subnets.
4. Launch a `t3.micro` EC2 instance in a PRIVATE subnet (no public IP). Launch a second `t3.micro` in a PUBLIC subnet to act as a bastion, WITH a public IP and a security group allowing SSH only from your own IP (`curl ifconfig.me` to find it).
5. From your laptop, SSH to the bastion, then from the bastion, SSH to the private instance's private IP (SSH agent forwarding, or copy the key temporarily — either works for a lab). Confirm you reached it, and confirm you CANNOT reach the private instance directly from your laptop (connection times out).
6. From the private instance, confirm outbound internet works despite having no public IP (`curl -I https://example.com` should succeed) — this is the NAT Gateway doing its job.
7. **Teardown, in this order** (dependencies matter): terminate both instances, delete the NAT Gateway (wait for it to fully delete, this takes a minute or two), release the Elastic IP, delete both route table associations and the route tables, detach and delete the IGW, delete all 4 subnets, delete the VPC, delete the security groups.

<details>
<summary>Solution / walkthrough</summary>

```bash
# 1. VPC + IGW
VPC_ID=$(aws ec2 create-vpc --cidr-block 10.30.0.0/16 --query 'Vpc.VpcId' --output text)
aws ec2 create-tags --resources "$VPC_ID" --tags Key=Name,Value=lab-vpc

IGW_ID=$(aws ec2 create-internet-gateway --query 'InternetGateway.InternetGatewayId' --output text)
aws ec2 attach-internet-gateway --vpc-id "$VPC_ID" --internet-gateway-id "$IGW_ID"

# 2. Subnets across 2 AZs (reusing the /20-style math from the
# Networking phase lab — using /24s here since this VPC is smaller)
AZ_A="ap-south-1a"
AZ_B="ap-south-1b"

PUB_A=$(aws ec2 create-subnet --vpc-id "$VPC_ID" --cidr-block 10.30.0.0/24 --availability-zone "$AZ_A" --query 'Subnet.SubnetId' --output text)
PUB_B=$(aws ec2 create-subnet --vpc-id "$VPC_ID" --cidr-block 10.30.1.0/24 --availability-zone "$AZ_B" --query 'Subnet.SubnetId' --output text)
PRIV_A=$(aws ec2 create-subnet --vpc-id "$VPC_ID" --cidr-block 10.30.10.0/24 --availability-zone "$AZ_A" --query 'Subnet.SubnetId' --output text)
PRIV_B=$(aws ec2 create-subnet --vpc-id "$VPC_ID" --cidr-block 10.30.11.0/24 --availability-zone "$AZ_B" --query 'Subnet.SubnetId' --output text)

# 3. Public route table -> IGW
PUB_RT=$(aws ec2 create-route-table --vpc-id "$VPC_ID" --query 'RouteTable.RouteTableId' --output text)
aws ec2 create-route --route-table-id "$PUB_RT" --destination-cidr-block 0.0.0.0/0 --gateway-id "$IGW_ID"
aws ec2 associate-route-table --subnet-id "$PUB_A" --route-table-id "$PUB_RT"
aws ec2 associate-route-table --subnet-id "$PUB_B" --route-table-id "$PUB_RT"

# NAT Gateway (needs an Elastic IP, sits in a PUBLIC subnet)
EIP_ALLOC=$(aws ec2 allocate-address --domain vpc --query 'AllocationId' --output text)
NAT_ID=$(aws ec2 create-nat-gateway --subnet-id "$PUB_A" --allocation-id "$EIP_ALLOC" --query 'NatGateway.NatGatewayId' --output text)
aws ec2 wait nat-gateway-available --nat-gateway-ids "$NAT_ID"   # takes a minute or two

# Private route table -> NAT
PRIV_RT=$(aws ec2 create-route-table --vpc-id "$VPC_ID" --query 'RouteTable.RouteTableId' --output text)
aws ec2 create-route --route-table-id "$PRIV_RT" --destination-cidr-block 0.0.0.0/0 --nat-gateway-id "$NAT_ID"
aws ec2 associate-route-table --subnet-id "$PRIV_A" --route-table-id "$PRIV_RT"
aws ec2 associate-route-table --subnet-id "$PRIV_B" --route-table-id "$PRIV_RT"

# 4. Security groups + instances
MY_IP=$(curl -s ifconfig.me)
BASTION_SG=$(aws ec2 create-security-group --group-name lab-bastion-sg --description "bastion" --vpc-id "$VPC_ID" --query 'GroupId' --output text)
aws ec2 authorize-security-group-ingress --group-id "$BASTION_SG" --protocol tcp --port 22 --cidr "${MY_IP}/32"

PRIVATE_SG=$(aws ec2 create-security-group --group-name lab-private-sg --description "private instance" --vpc-id "$VPC_ID" --query 'GroupId' --output text)
aws ec2 authorize-security-group-ingress --group-id "$PRIVATE_SG" --protocol tcp --port 22 --source-group "$BASTION_SG"
# ^ SG-to-SG reference, not a CIDR — the senior-tip pattern from the
# networking lesson: only the bastion's SG can reach this on port 22,
# regardless of what IP the bastion instance ends up with

AMI_ID=$(aws ec2 describe-images --owners amazon --filters "Name=name,Values=al2023-ami-*-x86_64" "Name=state,Values=available" --query 'sort_by(Images,&CreationDate)[-1].ImageId' --output text)

aws ec2 create-key-pair --key-name lab-key --query 'KeyMaterial' --output text > lab-key.pem
chmod 400 lab-key.pem

BASTION_ID=$(aws ec2 run-instances --image-id "$AMI_ID" --instance-type t3.micro \
  --key-name lab-key --subnet-id "$PUB_A" --security-group-ids "$BASTION_SG" \
  --associate-public-ip-address --query 'Instances[0].InstanceId' --output text)

PRIVATE_ID=$(aws ec2 run-instances --image-id "$AMI_ID" --instance-type t3.micro \
  --key-name lab-key --subnet-id "$PRIV_A" --security-group-ids "$PRIVATE_SG" \
  --no-associate-public-ip-address --query 'Instances[0].InstanceId' --output text)

aws ec2 wait instance-running --instance-ids "$BASTION_ID" "$PRIVATE_ID"
BASTION_IP=$(aws ec2 describe-instances --instance-ids "$BASTION_ID" --query 'Reservations[0].Instances[0].PublicIpAddress' --output text)
PRIVATE_IP=$(aws ec2 describe-instances --instance-ids "$PRIVATE_ID" --query 'Reservations[0].Instances[0].PrivateIpAddress' --output text)

# 5. Reach the private instance THROUGH the bastion
scp -i lab-key.pem lab-key.pem "ec2-user@$BASTION_IP:~/lab-key.pem"   # simplest approach for a lab
ssh -i lab-key.pem "ec2-user@$BASTION_IP"
#   (on the bastion:)
#   chmod 400 lab-key.pem
#   ssh -i lab-key.pem ec2-user@<PRIVATE_IP>     <- works, reached via the bastion

# From your laptop directly — confirm it's genuinely unreachable
ssh -i lab-key.pem -o ConnectTimeout=5 "ec2-user@$PRIVATE_IP"
# ssh: connect to host ... port 22: Operation timed out
# (there's no route from the public internet to a private-subnet IP at
# all — this isn't even a security-group block, the packet has nowhere
# to go without a NAT/IGW route pointing at it)

# 6. From INSIDE the private instance (via the bastion hop), confirm
# outbound internet works through the NAT Gateway
curl -I https://example.com
# HTTP/1.1 200 OK   <- outbound works despite no public IP on this instance

# 7. Teardown — order matters (dependencies)
aws ec2 terminate-instances --instance-ids "$BASTION_ID" "$PRIVATE_ID"
aws ec2 wait instance-terminated --instance-ids "$BASTION_ID" "$PRIVATE_ID"

aws ec2 delete-nat-gateway --nat-gateway-id "$NAT_ID"
aws ec2 wait nat-gateway-deleted --nat-gateway-ids "$NAT_ID"
aws ec2 release-address --allocation-id "$EIP_ALLOC"

aws ec2 disassociate-route-table --association-id <assoc-id-from-describe-route-tables>  # for each association
aws ec2 delete-route-table --route-table-id "$PUB_RT"
aws ec2 delete-route-table --route-table-id "$PRIV_RT"

aws ec2 detach-internet-gateway --vpc-id "$VPC_ID" --internet-gateway-id "$IGW_ID"
aws ec2 delete-internet-gateway --internet-gateway-id "$IGW_ID"

aws ec2 delete-subnet --subnet-id "$PUB_A"
aws ec2 delete-subnet --subnet-id "$PUB_B"
aws ec2 delete-subnet --subnet-id "$PRIV_A"
aws ec2 delete-subnet --subnet-id "$PRIV_B"

aws ec2 delete-security-group --group-id "$PRIVATE_SG"
aws ec2 delete-security-group --group-id "$BASTION_SG"

aws ec2 delete-vpc --vpc-id "$VPC_ID"
aws ec2 delete-key-pair --key-name lab-key
rm -f lab-key.pem
```
</details>

---

## Lab 3: Auto Scaling Group Behind an ALB, Driven by a Health-Check Failure

**Objective:** Prove that Auto Scaling replaces a genuinely unhealthy instance — not just a powered-off one — by making an instance LOOK alive at the EC2 level while failing its actual health endpoint, exactly the gap the lesson calls out about `health-check-type ELB` vs `EC2`.

**Task:**
1. Build a Launch Template using a small EC2 user-data script that starts a trivial HTTP server serving `/health` (Python's `http.server` is enough — no real app needed).
2. Create a target group with a health check pointed at `/health`, and an ALB in your public subnets (reuse the VPC from Lab 2, or a fresh simple VPC — either is fine) with a listener forwarding to that target group.
3. Create an ASG using the launch template, `min-size 2`, `max-size 4`, `desired-capacity 2`, spanning 2 AZs, with `--health-check-type ELB` (not the default EC2-only check) and a reasonable grace period.
4. Confirm both instances register as healthy in the target group (`aws elbv2 describe-target-health`) and that the ALB's DNS name serves traffic successfully.
5. SSH into one instance and deliberately break JUST the health endpoint (kill the http.server process, or `iptables` block port 80 — don't terminate/stop the instance itself, it must stay EC2-status "running" and "healthy" the whole time).
6. Watch the target group mark that instance `unhealthy` while EC2 status checks for the same instance still show fully healthy — this is the exact gap the lesson's `health-check-type ELB` note describes. Watch the ASG terminate it and launch a replacement, entirely because of the ELB-level check.
7. Confirm the replacement instance comes up healthy and the ALB's traffic is fully served by 2 healthy instances again.
8. Teardown: delete the ASG (it will terminate its instances), delete the launch template, ALB, target group, and any security groups/VPC resources you created just for this lab.

<details>
<summary>Solution / walkthrough</summary>

```bash
cat > user-data.sh << 'EOF'
#!/bin/bash
mkdir -p /var/www
echo "OK" > /var/www/health
cd /var/www && nohup python3 -m http.server 80 > /var/log/health-server.log 2>&1 &
EOF

aws ec2 create-launch-template \
  --launch-template-name asg-lab-template \
  --launch-template-data "{
    \"ImageId\": \"$AMI_ID\",
    \"InstanceType\": \"t3.micro\",
    \"KeyName\": \"lab-key\",
    \"SecurityGroupIds\": [\"$PRIVATE_SG\"],
    \"UserData\": \"$(base64 -i user-data.sh)\"
  }"

# Target group with a real /health check
TG_ARN=$(aws elbv2 create-target-group --name asg-lab-tg --protocol HTTP --port 80 \
  --vpc-id "$VPC_ID" --health-check-path /health --health-check-interval-seconds 10 \
  --healthy-threshold-count 2 --unhealthy-threshold-count 2 \
  --query 'TargetGroups[0].TargetGroupArn' --output text)

ALB_SG=$(aws ec2 create-security-group --group-name asg-lab-alb-sg --description "alb" --vpc-id "$VPC_ID" --query 'GroupId' --output text)
aws ec2 authorize-security-group-ingress --group-id "$ALB_SG" --protocol tcp --port 80 --cidr 0.0.0.0/0
aws ec2 authorize-security-group-ingress --group-id "$PRIVATE_SG" --protocol tcp --port 80 --source-group "$ALB_SG"

ALB_ARN=$(aws elbv2 create-load-balancer --name asg-lab-alb --subnets "$PUB_A" "$PUB_B" \
  --security-groups "$ALB_SG" --query 'LoadBalancers[0].LoadBalancerArn' --output text)
aws elbv2 create-listener --load-balancer-arn "$ALB_ARN" --protocol HTTP --port 80 \
  --default-actions "Type=forward,TargetGroupArn=$TG_ARN"

# 3. ASG with ELB health checks
aws autoscaling create-auto-scaling-group \
  --auto-scaling-group-name asg-lab \
  --launch-template LaunchTemplateName=asg-lab-template,Version='$Latest' \
  --min-size 2 --max-size 4 --desired-capacity 2 \
  --vpc-zone-identifier "$PRIV_A,$PRIV_B" \
  --target-group-arns "$TG_ARN" \
  --health-check-type ELB \
  --health-check-grace-period 90

sleep 120   # let instances launch and pass their first health checks

# 4. Confirm healthy targets + working ALB
aws elbv2 describe-target-health --target-group-arn "$TG_ARN"
# both targets show "State": "healthy"

ALB_DNS=$(aws elbv2 describe-load-balancers --load-balancer-arns "$ALB_ARN" --query 'LoadBalancers[0].DNSName' --output text)
curl "http://$ALB_DNS/health"
# OK

# 5. Break ONE instance's health endpoint without touching the instance's power state
INSTANCE_IDS=$(aws autoscaling describe-auto-scaling-groups --auto-scaling-group-names asg-lab \
  --query 'AutoScalingGroups[0].Instances[0].InstanceId' --output text)
TARGET_IP=$(aws ec2 describe-instances --instance-ids "$INSTANCE_IDS" --query 'Reservations[0].Instances[0].PrivateIpAddress' --output text)

# SSH via the Lab 2 bastion (or a temporary bastion if this is a fresh VPC)
ssh -i lab-key.pem "ec2-user@$BASTION_IP" "ssh -i lab-key.pem ec2-user@$TARGET_IP 'sudo pkill -f http.server'"

# 6. Watch the divergence between EC2 status and ELB target health
aws ec2 describe-instance-status --instance-ids "$INSTANCE_IDS"
# InstanceStatus / SystemStatus both still "ok" — the EC2-level checks
# have NO idea the app-level health endpoint is dead, because they only
# verify the VM/hypervisor and basic OS reachability, not YOUR /health path

watch -n 15 "aws elbv2 describe-target-health --target-group-arn $TG_ARN"
# within ~20-30s (2 x 10s unhealthy-threshold), that target flips to
# "State": "unhealthy", "Reason": "Target.FailedHealthChecks"

aws autoscaling describe-scaling-activities --auto-scaling-group-name asg-lab --max-records 5
# shows an activity: "Terminating EC2 instance ... due to user request"
# or an ELB-health-triggered replacement, then a new "Launching a new
# EC2 instance" activity for the replacement — THIS is exactly what
# --health-check-type ELB buys you over the EC2-only default: an
# instance that's "up" but serving nothing useful gets cycled out
# automatically, instead of silently sitting in rotation forever.

# 7. Confirm recovery
sleep 120
aws elbv2 describe-target-health --target-group-arn "$TG_ARN"
# 2 healthy targets again, one of them a brand new instance ID

# 8. Teardown
aws autoscaling update-auto-scaling-group --auto-scaling-group-name asg-lab --min-size 0 --desired-capacity 0
aws autoscaling delete-auto-scaling-group --auto-scaling-group-name asg-lab --force-delete
aws elbv2 delete-listener --listener-arn <listener-arn-from-describe-listeners>
aws elbv2 delete-load-balancer --load-balancer-arn "$ALB_ARN"
aws elbv2 wait load-balancers-deleted --load-balancer-arns "$ALB_ARN"
aws elbv2 delete-target-group --target-group-arn "$TG_ARN"
aws ec2 delete-launch-template --launch-template-name asg-lab-template
aws ec2 delete-security-group --group-id "$ALB_SG"
# then continue with the rest of the Lab 2 VPC teardown if this reused that VPC
```
</details>

---

## Lab 4: Diagnose a Security Group Lockout (Production-Style Scenario)

**Objective:** Reproduce the "I opened port 443 but clients still can't connect" and "I locked myself out of SSH" scenarios from the lesson, and practice the exact diagnostic order the lesson lays out.

**Task:**
1. Launch a single EC2 instance in a public subnet with a security group that ONLY allows inbound SSH (port 22) from your IP — deliberately do NOT open port 80/443 yet.
2. Install and start a simple web server on it (`python3 -m http.server 80` via SSH, or user-data at launch).
3. From your laptop, `curl http://<public-ip>` — confirm it times out (not "connection refused" — note the DIFFERENCE and explain why a timeout specifically points at a firewall/SG issue rather than "nothing is listening").
4. Fix it: add an inbound rule for port 80 from `0.0.0.0/0`. Re-test — confirm it now works.
5. Now reproduce the classic self-lockout: revoke the SSH (port 22) inbound rule entirely while you have NO other active session to the box. Attempt to SSH in again — confirm it times out.
6. Recover WITHOUT waiting for a support ticket: use `aws ec2 authorize-security-group-ingress` FROM THE CLI (which uses your IAM credentials, not SSH, so it works even though you're locked out of the box itself) to re-add the rule. Confirm SSH access returns immediately.
7. Bonus — reproduce the NACL-specific trap from the networking lesson: create a custom NACL on the instance's subnet, add an inbound ALLOW rule for port 80, but do NOT add a matching outbound rule for the ephemeral port range (1024-65535). Confirm inbound requests reach the server (visible in the server's own access log / a packet capture if you want to go that far) but the RESPONSE never makes it back to the client — explain why, tying it to the stateless-vs-stateful distinction.
8. Teardown: delete the custom NACL (revert the subnet to the default), terminate the instance, delete the security group.

<details>
<summary>Solution / walkthrough</summary>

```bash
SG_ID=$(aws ec2 create-security-group --group-name lockout-lab-sg --description "lockout lab" --vpc-id "$VPC_ID" --query 'GroupId' --output text)
MY_IP=$(curl -s ifconfig.me)
aws ec2 authorize-security-group-ingress --group-id "$SG_ID" --protocol tcp --port 22 --cidr "${MY_IP}/32"

INSTANCE_ID=$(aws ec2 run-instances --image-id "$AMI_ID" --instance-type t3.micro \
  --key-name lab-key --subnet-id "$PUB_A" --security-group-ids "$SG_ID" \
  --associate-public-ip-address --query 'Instances[0].InstanceId' --output text)
aws ec2 wait instance-running --instance-ids "$INSTANCE_ID"
PUB_IP=$(aws ec2 describe-instances --instance-ids "$INSTANCE_ID" --query 'Reservations[0].Instances[0].PublicIpAddress' --output text)

ssh -i lab-key.pem "ec2-user@$PUB_IP" "nohup python3 -m http.server 80 > /tmp/http.log 2>&1 &"

# 3. Confirm the timeout, and WHY it's a timeout not a refusal
curl --connect-timeout 5 "http://$PUB_IP"
# curl: (28) Connection timed out after 5000 milliseconds
#
# A TIMEOUT means packets are being silently DROPPED somewhere before
# reaching (or the response reaching back from) the destination — the
# classic security-group-deny fingerprint, since SGs drop with no
# response at all. A "Connection refused" would instead mean the
# packet arrived fine but nothing was listening on that port — a very
# different problem (app not running) with a very different fix.

# 4. Fix — open port 80
aws ec2 authorize-security-group-ingress --group-id "$SG_ID" --protocol tcp --port 80 --cidr 0.0.0.0/0
curl --connect-timeout 5 "http://$PUB_IP"
# Directory listing HTML   <- works now

# 5. Reproduce the SSH self-lockout
RULE_ID=$(aws ec2 describe-security-group-rules --filters "Name=group-id,Values=$SG_ID" \
  --query "SecurityGroupRules[?FromPort==\`22\`].SecurityGroupRuleId" --output text)
aws ec2 revoke-security-group-ingress --group-id "$SG_ID" --security-group-rule-ids "$RULE_ID"

ssh -i lab-key.pem -o ConnectTimeout=5 "ec2-user@$PUB_IP"
# ssh: connect to host ... port 22: Operation timed out
# — locked out, exactly like an accidental prod incident

# 6. Recover via the CLI (IAM-authenticated, not SSH-dependent)
aws ec2 authorize-security-group-ingress --group-id "$SG_ID" --protocol tcp --port 22 --cidr "${MY_IP}/32"
ssh -i lab-key.pem "ec2-user@$PUB_IP" "echo back in"
# back in    <- recovered in seconds, no console/support-ticket detour
# needed, because the fix path (IAM API calls) is entirely independent
# of the broken path (SSH network access) — this is exactly why SSM
# Session Manager (also IAM-based, no SG port 22 needed at all) is the
# modern preferred access pattern the lesson mentions.

# 7. NACL stateless trap
SUBNET_ID="$PUB_A"
NACL_ID=$(aws ec2 create-network-acl --vpc-id "$VPC_ID" --query 'NetworkAcl.NetworkAclId' --output text)

aws ec2 create-network-acl-entry --network-acl-id "$NACL_ID" --rule-number 100 \
  --protocol tcp --port-range From=80,To=80 --cidr-block 0.0.0.0/0 --rule-action allow --ingress
# deliberately NOT adding an egress rule for ephemeral ports 1024-65535

# also need the default "allow everything for existing rules" DENY
# baseline explicit for a custom NACL — custom NACLs deny all until
# you add rules, so this NACL currently allows ONLY inbound 80, nothing
# outbound at all

aws ec2 replace-network-acl-association --association-id \
  "$(aws ec2 describe-network-acls --filters "Name=association.subnet-id,Values=$SUBNET_ID" --query 'NetworkAcls[0].Associations[0].NetworkAclAssociationId' --output text)" \
  --network-acl-id "$NACL_ID"

curl --connect-timeout 5 "http://$PUB_IP"
# curl: (28) Connection timed out
# The inbound SYN packet DOES reach the instance (visible if you tcpdump
# on the instance itself — the request arrives), but the RESPONSE
# packet, which uses a high-numbered EPHEMERAL source port on the way
# back out, has no matching NACL outbound rule to permit it — so it's
# silently dropped on the way out. Unlike the Security Group (stateful,
# auto-allows return traffic for an allowed inbound connection), the
# NACL has no memory of the inbound request at all and evaluates the
# outbound response as an entirely independent, unrelated packet that
# must be explicitly allowed.

# Fix: add the missing outbound rule
aws ec2 create-network-acl-entry --network-acl-id "$NACL_ID" --rule-number 100 \
  --protocol tcp --port-range From=1024,To=65535 --cidr-block 0.0.0.0/0 --rule-action allow --egress
curl --connect-timeout 5 "http://$PUB_IP"
# works now

# 8. Teardown
DEFAULT_NACL=$(aws ec2 describe-network-acls --filters "Name=vpc-id,Values=$VPC_ID" "Name=default,Values=true" --query 'NetworkAcls[0].NetworkAclId' --output text)
aws ec2 replace-network-acl-association --association-id \
  "$(aws ec2 describe-network-acls --filters "Name=association.subnet-id,Values=$SUBNET_ID" --query 'NetworkAcls[0].Associations[0].NetworkAclAssociationId' --output text)" \
  --network-acl-id "$DEFAULT_NACL"
aws ec2 delete-network-acl --network-acl-id "$NACL_ID"
aws ec2 terminate-instances --instance-ids "$INSTANCE_ID"
aws ec2 wait instance-terminated --instance-ids "$INSTANCE_ID"
aws ec2 delete-security-group --group-id "$SG_ID"
```
</details>

---

## Self-Check Checklist

- [ ] Can you write a scoped IAM policy (one resource, specific verbs, explicit deny) instead of reaching for `Action: "*"` / `Resource: "*"`?
- [ ] Can you explain, and have you PROVEN with `kubectl`-style `auth can-i` equivalents (`aws sts` / actual denied API calls), that a scoped policy really restricts access?
- [ ] Can you sketch and actually build a 2-AZ public/private VPC with a working NAT path, from CLI commands, not a console wizard?
- [ ] Can you explain why an instance in a private subnet with no public IP can still reach the internet outbound?
- [ ] Do you know the difference between `Multi-AZ` and a `Read Replica` well enough to say which one you'd add for a read-heavy workload vs a failover requirement?
- [ ] Can you explain, having watched it happen, why `health-check-type ELB` catches failures that EC2-only status checks miss?
- [ ] Can you diagnose "curl times out" vs "connection refused" and know which one points at a firewall/SG problem?
- [ ] Have you recovered from a self-inflicted SSH security-group lockout using the CLI instead of a support ticket?
- [ ] Can you explain the stateful-vs-stateless distinction between Security Groups and NACLs well enough to debug the "opened port 80 inbound, still doesn't work" NACL trap?
- [ ] Do you know, from memory, the order you'd check things when a client says "ALB endpoint works but one path times out" (listener rules → target health → security groups → NACLs)?
