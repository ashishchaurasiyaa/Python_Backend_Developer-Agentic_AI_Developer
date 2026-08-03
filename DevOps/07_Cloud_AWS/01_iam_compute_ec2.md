# Cloud (AWS) — Identity & Compute: IAM, EC2, Auto Scaling
**DevOps Track · Phase 7: Cloud (AWS)**

> Complementary to Backend_Developer/01_Year3-4_Mid/04_DevOps/ (app-deployment angle) — this covers the fuller AWS/Terraform service and design-pattern picture.

## Quick Concepts

- **IAM** = Identity and Access Management — the global (not region-scoped) service that controls *who* can do *what* on *which* resource
- **Principal** = the "who" — an IAM user, role, or federated identity making a request
- **Policy** = JSON document attached to a principal or resource that grants or denies actions
- **Role** = an identity with no long-term credentials, assumed temporarily by a user, service, or another AWS account
- **Least privilege** = grant only the permissions required for the task, nothing more
- **MFA** = Multi-Factor Authentication — password + a second factor (TOTP app, hardware key)
- **EC2** = Elastic Compute Cloud — resizable virtual machines billed by the second/hour
- **AMI** = Amazon Machine Image — a snapshot template (OS + packages) used to launch instances
- **Key pair** = public/private RSA key used for SSH access instead of a password
- **Security Group** = a virtual, stateful firewall attached to an instance's network interface
- **Auto Scaling Group (ASG)** = a fleet of EC2 instances that grows/shrinks automatically to match demand
- **Launch Template** = versioned blueprint (AMI, instance type, security groups, user data) an ASG uses to create instances

---

## Why This Matters — The AWS Well-Architected Lens

AWS structures its own certification exams and reference architectures around four design pillars that map directly onto real production incidents:

```
SECURE            → who can touch this, and how do we stop the wrong person? (IAM, MFA, encryption)
RESILIENT         → what happens when an AZ, instance, or process dies? (Auto Scaling, Multi-AZ)
HIGH-PERFORMING   → is the right resource size/type doing the job? (instance types, caching)
COST-OPTIMIZED    → are we paying for capacity we don't use? (Reserved/Spot, right-sizing)
```

This phase file covers the **Secure** pillar via IAM and the **Resilient** pillar via Auto Scaling. Every AWS architecture decision you make in an interview or in production should be defensible against these four questions — that framing itself is often the difference between a mid-level and senior-level answer.

A backend engineer who only knows `docker compose up` on a single EC2 box hits a wall the moment: a key gets leaked (no least privilege), a box dies at 3 AM (no Auto Scaling), or a bill review shows $4k/month for workloads that idle 80% of the time (no cost design). This file is about not hitting that wall.

---

## AWS CLI Setup — Configuration and Profiles

Every `aws` command in this entire phase assumes credentials are already working. Here's the part that makes them work.

```bash
aws configure                    # interactive — prompts for Access Key ID, Secret
                                    # Access Key, default region, output format
                                    # (writes to ~/.aws/credentials and ~/.aws/config)

aws configure --profile staging     # a NAMED profile — for working across multiple
                                       # AWS accounts (personal, staging, prod) without
                                       # overwriting your default credentials each time
aws s3 ls --profile staging            # use a specific profile for one command
export AWS_PROFILE=staging               # or set it for the whole shell session
```

```
~/.aws/credentials                    ~/.aws/config
[default]                             [default]
aws_access_key_id = AKIA...           region = ap-south-1
aws_secret_access_key = ...           output = json

[staging]                             [profile staging]
aws_access_key_id = AKIA...           region = us-east-1
aws_secret_access_key = ...           output = json
```

```bash
aws sts get-caller-identity        # the single most useful debugging command —
                                      # "who am I actually authenticated as, RIGHT NOW"
# {
#   "UserId": "AIDACKCEVSQ6C2EXAMPLE",
#   "Account": "123456789012",
#   "Arn": "arn:aws:iam::123456789012:user/ashish"
# }
```

```
Credential resolution order (first found wins) — worth knowing when
"it's using the wrong account" happens:
  1. CLI flags               (--profile, or explicit keys — rare/discouraged)
  2. Environment variables    (AWS_ACCESS_KEY_ID, AWS_PROFILE)
  3. ~/.aws/credentials         (the "default" profile, or whichever --profile names)
  4. Instance/task/container role   (EC2 instance profile, ECS task role, EKS
                                       IRSA — this is what a WORKLOAD running
                                       ON AWS should use, never static keys)
```

**Senior tip:** `aws sts get-caller-identity` is the first command to run whenever an AWS CLI action does something unexpected (wrong account, wrong permissions) — it costs nothing and immediately answers "am I even authenticated as who I think I am," before you go debugging IAM policies that were never the actual problem.

---

## IAM — Identity and Access Management

### The Core Objects

```
Account root user   → full access, created with the AWS account. Never use day-to-day. Enable MFA, lock away.
IAM User            → long-term identity for a person or an application that isn't a role
IAM Group           → collection of users, policies attached to the group apply to all members
IAM Role            → temporary identity assumed via STS (Security Token Service) — no static credentials
IAM Policy          → JSON document listing allowed/denied actions on resources
```

### Users vs Roles — When to Use Which

| | IAM User | IAM Role |
|---|---|---|
| Credentials | Long-term access key + secret (or password) | Temporary, auto-rotated STS tokens |
| Typical holder | A human, or legacy service needing static keys | EC2 instance, Lambda function, another AWS account, federated SSO user |
| Rotation | Manual — you must rotate keys yourself | Automatic — tokens expire in minutes/hours |
| Best practice | Avoid for services; use only for humans without SSO | **Always** prefer for EC2/Lambda/ECS workloads |

**Senior rule of thumb**: if you find yourself hardcoding an `AWS_ACCESS_KEY_ID` in an application's environment variables or a `.env` file, you are almost certainly doing it wrong. Attach an IAM **role** to the EC2 instance / ECS task / Lambda function instead — the AWS SDK (boto3, etc.) picks up temporary credentials automatically from the instance metadata service, no secret ever touches your codebase.

### Anatomy of a Policy Document

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "AllowReadOnlyOnOneBucket",
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:ListBucket"
      ],
      "Resource": [
        "arn:aws:s3:::my-app-uploads",
        "arn:aws:s3:::my-app-uploads/*"
      ],
      "Condition": {
        "StringEquals": {
          "aws:RequestedRegion": "ap-south-1"
        }
      }
    },
    {
      "Sid": "DenyDeleteAlways",
      "Effect": "Deny",
      "Action": "s3:DeleteObject",
      "Resource": "arn:aws:s3:::my-app-uploads/*"
    }
  ]
}
```

Reading a policy statement:

```
Effect      → Allow or Deny (explicit Deny always wins over Allow, even from another policy)
Action      → the API call(s) being permitted, in "service:Action" form
Resource    → the ARN(s) the action applies to — "*" means all resources (dangerous, avoid)
Condition   → optional narrowing — IP range, MFA presence, time window, tag match, region
```

### Policy Types You'll Actually Encounter

```
Identity-based policy   → attached to a user/group/role ("this role can do X")
Resource-based policy   → attached to the resource itself, e.g. an S3 bucket policy
                          ("this bucket allows account 123456789 to read")
Permissions boundary    → a ceiling — the *maximum* permissions a role can ever have,
                          even if its attached policies grant more
Service Control Policy  → org-level guardrail (AWS Organizations) — applies across
                          many accounts, cannot be overridden by account admins
```

### Principle of Least Privilege — a Worked Example

Bad (common junior mistake):

```json
{ "Effect": "Allow", "Action": "s3:*", "Resource": "*" }
```

This grants full S3 control over every bucket in the account — including buckets that belong to other teams, and destructive actions like `DeleteBucket`.

Good:

```json
{
  "Effect": "Allow",
  "Action": ["s3:GetObject", "s3:PutObject"],
  "Resource": "arn:aws:s3:::billing-service-invoices/*"
}
```

Scoped to exactly one bucket, exactly two verbs (read + write, no delete, no list-all-buckets). If this role's credentials leak, blast radius is one bucket, two actions.

### MFA (Multi-Factor Authentication)

```
Why: a leaked password alone is no longer sufficient to log in or make API calls
     when MFA is enforced on sensitive actions.

Where to enforce it:
  - Root account            → MANDATORY, no exceptions, ever
  - IAM users with console
    access to production     → mandatory via policy condition:
                               "Condition": {"BoolIfExists": {"aws:MultiFactorAuthPresent": "false"}}
                               combined with Effect: Deny on sensitive actions
  - Break-glass admin roles → require MFA to assume the role via STS
```

A common interview question: "how do you force MFA for an action instead of just recommending it?" Answer: deny the action unless `aws:MultiFactorAuthPresent` is `true` in the policy condition — recommendation is not enforcement, a Deny statement is.

---

## EC2 — Elastic Compute Cloud

### Instance Type Families (What the Letters Mean)

```
t3.medium     T = burstable general purpose   (dev/test, low steady CPU, credits for spikes)
m6i.large     M = balanced general purpose    (typical app servers)
c6i.xlarge    C = compute-optimized           (CPU-bound: batch processing, media encoding)
r6i.large     R = memory-optimized            (in-memory caches, large JVM heaps, Redis)
i3.large      I = storage-optimized, local NVMe (high-IOPS databases needing local disk)
g5.xlarge     G = GPU-accelerated             (ML inference/training, rendering)

Suffix letters:
  i  → Intel processor
  a  → AMD processor
  g  → AWS Graviton (ARM) — usually 20-40% cheaper for the same performance class
```

Interview-relevant rule: for a stateless web/API tier, prefer **Graviton (`m7g`, `c7g`)** instances if your stack supports ARM — same workload, meaningfully lower cost, and AWS increasingly makes Graviton the default recommendation.

### AMI (Amazon Machine Image)

```
An AMI is a snapshot template that captures:
  - Root volume (OS + installed packages)
  - Launch permissions (which accounts may use it)
  - Block device mapping (additional volumes)

Sources:
  - AWS-provided (Amazon Linux 2023, Ubuntu via Canonical, Windows Server)
  - AWS Marketplace (vendor-published, e.g. hardened CIS images)
  - Custom / "golden" AMI — you bake your own with app + deps preinstalled,
    so instances boot ready-to-serve instead of running a slow bootstrap script
```

Building a golden AMI (commonly done with Packer, covered alongside Terraform tooling) trades a slower, less-frequent build step for much faster instance boot time — directly improves Auto Scaling responsiveness because new instances don't need to `apt install` and `git clone` on every scale-out event.

### Basic Instance Lifecycle — The Commands Before Auto Scaling Enters the Picture

Auto Scaling (below) is how PRODUCTION fleets work — but every one of those instances is still, underneath, created/inspected/torn down via these same primitives.

```bash
aws ec2 run-instances \
  --image-id ami-0abcdef1234567890 \
  --instance-type t3.micro \
  --key-name prod-api-key \
  --security-group-ids sg-0123456789abcdef0 \
  --subnet-id subnet-0aaa111 \
  --count 1 \
  --tag-specifications 'ResourceType=instance,Tags=[{Key=Name,Value=test-box}]'

aws ec2 describe-instances \
  --filters "Name=tag:Name,Values=test-box" \
  --query 'Reservations[].Instances[].{ID:InstanceId,State:State.Name,IP:PublicIpAddress}'

aws ec2 stop-instances --instance-ids i-0123456789abcdef0    # keeps the EBS root
                                                                 # volume, stops billing
                                                                 # for compute (not storage)
aws ec2 start-instances --instance-ids i-0123456789abcdef0      # boot it back up — gets a
                                                                   # NEW public IP unless an
                                                                   # Elastic IP is attached (below)
aws ec2 terminate-instances --instance-ids i-0123456789abcdef0    # DESTROYS it — root volume
                                                                     # is deleted too by default
                                                                     # unless DeleteOnTermination
                                                                     # was set to false
```

```
stop vs terminate — the distinction that actually matters:
  stop      → instance shuts down, EBS root volume PERSISTS, you can
              start it again later with the same volume/data, same
              instance ID. Still billed for the attached EBS storage,
              just not compute.
  terminate → instance AND (by default) its root EBS volume are gone
              permanently. No "start it again" — you'd launch a
              genuinely new instance from an AMI/snapshot instead.
```

### Elastic IP — A Static Public IP You Own

By default, an instance's public IP changes every time it's stopped and restarted. An **Elastic IP** is a static public IPv4 address you allocate to your account and explicitly attach — it stays the same across stop/start cycles until you release it.

```bash
aws ec2 allocate-address --domain vpc                # get a new Elastic IP, returns an AllocationId
aws ec2 associate-address \
  --instance-id i-0123456789abcdef0 \
  --allocation-id eipalloc-0abc123def456              # attach it to a specific instance

aws ec2 disassociate-address --association-id eipassoc-0abc123    # detach without releasing
aws ec2 release-address --allocation-id eipalloc-0abc123            # release it back to AWS —
                                                                        # do this once you're
                                                                        # actually done, an
                                                                        # unattached Elastic IP
                                                                        # is billed hourly
```

```
Real-world use: a partner's firewall needs to allowlist a fixed IP
for your API, or a bastion host needs a stable address for everyone's
SSH config. For anything behind a load balancer (the normal production
case), you generally DON'T need Elastic IPs on individual instances —
the ALB/NLB's own stable endpoint (Phase 7's networking file) is what
clients actually connect to.
```

### Key Pairs

```bash
# Generate locally (or let AWS generate and download the .pem once)
aws ec2 create-key-pair --key-name prod-api-key \
  --query 'KeyMaterial' --output text > prod-api-key.pem
chmod 400 prod-api-key.pem     # SSH refuses to use an over-permissioned key

ssh -i prod-api-key.pem ec2-user@<public-ip>
```

```
Lost private key → cannot recover it, AWS never stores it after creation.
Recovery path     → detach the EBS root volume, attach to a rescue instance,
                    inject a new authorized_keys entry, reattach. Painful —
                    this is why SSM Session Manager (no key pair needed,
                    IAM-governed shell access) is the modern preferred path.
```

### Security Groups — A First Look (full comparison with NACLs in the networking file)

```
Security Group = stateful firewall at the ENI (network interface) level
  - Only ALLOW rules — no explicit deny
  - Stateful: response traffic to an allowed inbound request is auto-allowed out
  - Evaluated per-instance, can attach multiple SGs to one instance

Example: web-tier-sg
  Inbound:  443/tcp  from 0.0.0.0/0        (public HTTPS)
            22/tcp   from 10.0.0.0/16      (SSH only from within VPC / bastion)
  Outbound: all traffic to 0.0.0.0/0       (default — usually tightened later)
```

The full stateful-vs-stateless breakdown against Network ACLs lives in `03_networking_dns_lb.md` — flagged here because Security Groups are chosen at instance launch time, so you need the concept now.

---

## Auto Scaling — Designing for the Resilient Pillar

### Why a Single EC2 Instance Is a Liability

```
One instance = one AZ = one point of failure.
  - Instance fails hardware check     → app is down until someone notices + replaces it
  - Traffic spikes 5x                 → instance saturates, requests time out
  - Scheduled maintenance / patching  → downtime window required

Auto Scaling Groups solve both the failure-recovery problem AND the
capacity-matching problem with the same mechanism.
```

### Launch Templates

A Launch Template is the versioned "recipe" an ASG uses to create new instances — it replaced the older Launch Configuration (which AWS now recommends against for new work, mainly because it's immutable and can't be versioned).

```bash
aws ec2 create-launch-template \
  --launch-template-name api-server-template \
  --version-description "v3 - bumped instance type" \
  --launch-template-data '{
    "ImageId": "ami-0abcdef1234567890",
    "InstanceType": "m6i.large",
    "KeyName": "prod-api-key",
    "SecurityGroupIds": ["sg-0123456789abcdef0"],
    "IamInstanceProfile": {"Name": "api-server-role"},
    "UserData": "'"$(base64 -w0 bootstrap.sh)"'",
    "TagSpecifications": [{
      "ResourceType": "instance",
      "Tags": [{"Key": "Name", "Value": "api-server"}]
    }]
  }'
```

`UserData` is the bootstrap script that runs once on first boot — typical use: pull the latest container image and start it, register with a service discovery mechanism, or run configuration management (Ansible pull, cloud-init).

### Auto Scaling Group Definition

```bash
aws autoscaling create-auto-scaling-group \
  --auto-scaling-group-name api-server-asg \
  --launch-template LaunchTemplateName=api-server-template,Version='$Latest' \
  --min-size 2 \
  --max-size 10 \
  --desired-capacity 2 \
  --vpc-zone-identifier "subnet-aaa,subnet-bbb,subnet-ccc" \
  --target-group-arns arn:aws:elasticloadbalancing:...:targetgroup/api-tg \
  --health-check-type ELB \
  --health-check-grace-period 120
```

```
min-size / max-size / desired-capacity
  → floor / ceiling / current target instance count

vpc-zone-identifier with 3 subnets in 3 different AZs
  → instances spread across Availability Zones = resilient to a single AZ outage

health-check-type ELB (not just EC2)
  → ASG asks the load balancer's target group health check, not just
    "is the VM powered on" — catches app-level failures (process crashed,
    health endpoint returning 500) that EC2-only checks would miss

health-check-grace-period
  → time given to a freshly launched instance before ASG starts judging
    its health — prevents killing instances still booting/warming up
```

### Scaling Policies

```
Target Tracking     → "keep average CPU at 50%" — ASG computes the math itself,
                       simplest and most common in production
Step Scaling        → explicit thresholds: CPU > 70% add 2, CPU > 90% add 4
Scheduled Scaling    → known traffic patterns, e.g. scale up before 9am IST daily
Predictive Scaling   → ML-based, pre-provisions ahead of forecasted load
```

```bash
aws autoscaling put-scaling-policy \
  --auto-scaling-group-name api-server-asg \
  --policy-name cpu-target-tracking \
  --policy-type TargetTrackingScaling \
  --target-tracking-configuration '{
    "PredefinedMetricSpecification": {
      "PredefinedMetricType": "ASGAverageCPUUtilization"
    },
    "TargetValue": 50.0
  }'
```

### Multi-AZ Is Not Optional for "Resilient"

```
Single AZ                 Multi-AZ (3 AZs)
     ┌────┐                    ┌────┐  ┌────┐  ┌────┐
     │ EC2│                    │ EC2│  │ EC2│  │ EC2│
     └────┘                    └────┘  └────┘  └────┘
   1 AZ fails →              1 AZ fails → ASG still has
   100% down                 capacity in the other 2 AZs,
                              and launches replacements there
```

An ASG spanning 3 AZs with `min-size 2` technically survives one full AZ outage only if the remaining AZs have room — in practice, size `min-size` so that losing one AZ still leaves enough capacity (e.g., 3 AZs, min 3, so losing one AZ leaves 2 healthy instances, not zero).

---

## Senior Tip

```
In interviews, don't just say "I'd use Auto Scaling." Say WHY:

  "I'd put the fleet in an ASG spanning 3 AZs with a target-tracking policy
   on CPU, min 3 / max 10, health checks pointed at the ALB target group
   instead of raw EC2 status — because EC2 status checks won't catch an
   app that's up but returning 500s. The launch template pulls a versioned
   golden AMI so scale-out is fast, and the instance role has a scoped IAM
   policy — no wildcard actions, no static keys anywhere in the app."

That one paragraph touches: resilience (Multi-AZ), performance (target
tracking + golden AMI), and security (IAM role, least privilege) — three
of the four Well-Architected pillars in one breath. That's the level
interviewers are listening for past mid-level.
```

## Interview Angle

**Q: Your ASG shows `desired-capacity: 4` but only 2 healthy instances are running. How do you debug it?**

Check, in order: (1) launch template errors — bad AMI ID, invalid security group, IAM instance profile that doesn't exist; (2) subnet capacity — no IPs left in the subnet; (3) health check failures causing ASG to terminate instances right after launch (check the ALB target group health, not just EC2 status); (4) service quota limits on the instance type in that region. `aws autoscaling describe-scaling-activities` is the first command to run — it shows the actual failure reason for each launch attempt.

**Q: An `aws` CLI command is behaving unexpectedly — wrong account, or "access denied" on something you thought you had access to. What's the first command to run?**
`aws sts get-caller-identity` — it costs nothing and immediately shows which IAM user/role you're actually authenticated as, right now. Credentials resolve in a specific order (CLI flags → environment variables → `~/.aws/credentials` profile → instance/task role), and it's common to be authenticated as a different identity than you assumed — confirming WHO you are is faster than debugging IAM policies that were never the actual problem.

**Q: You stopped an EC2 instance to save cost overnight, and now the app that connects to it via a hardcoded IP can't reach it. What happened?**
A stopped-then-started instance gets a NEW public IP by default (unless an Elastic IP was attached) — the old IP is released back to AWS's pool the moment the instance stops. Fix: attach an Elastic IP if you need a stable address for a stop/start-cycled instance, or better, don't hardcode instance IPs at all — put it behind a load balancer (Phase 7's networking file) whose endpoint doesn't change.

---

## Related

- [02_storage_database.md](02_storage_database.md) — S3, EBS/EFS, RDS/DynamoDB/Aurora
- [03_networking_dns_lb.md](03_networking_dns_lb.md) — full Security Group vs NACL comparison, VPC design
- [../08_Terraform/01_terraform_iac.md](../08_Terraform/01_terraform_iac.md) — provisioning EC2 + security groups as code
- [../../Backend_Developer/01_Year3-4_Mid/04_DevOps/04_aws_ec2_s3_rds.md](../../Backend_Developer/01_Year3-4_Mid/04_DevOps/04_aws_ec2_s3_rds.md) — app-deployment angle (boto3, single-box deploys)
