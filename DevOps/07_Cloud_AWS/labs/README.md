# AWS Labs — Runnable Exercises (no AWS account needed)

`../practical/01_aws_lab.md` already has 4 walkthroughs (IAM least-privilege
+ S3 lifecycle, a 2-AZ VPC with a bastion, an Auto Scaling Group behind an
ALB, diagnosing a Security Group lockout) — but those need a **real AWS
account** (EC2/VPC/ALB/ASG aren't things a free local emulator can do well).
This folder is 5 **different** labs, chosen specifically for services
**LocalStack's free community edition genuinely supports**: SQS, SNS,
DynamoDB, Secrets Manager, S3 — so you can run all of them with zero AWS
account and zero cost. Each has a TODO-stub `lab.py` (boto3) and a
`verify.sh` that runs it and independently double-checks the result via the
AWS CLI, not just trusting the script's own printed output.

## Setup

```bash
cd DevOps/07_Cloud_AWS/labs
(cd _setup && docker compose up -d)     # starts LocalStack (SQS/SNS/DynamoDB/SecretsManager/S3), ~15s
pip install boto3
```

## Labs

| # | Lab | What it proves |
|---|---|---|
| 1 | [01_sqs_dlq_redrive](01_sqs_dlq_redrive) | Without a DLQ, a message that keeps failing loops through the queue forever; a `RedrivePolicy` moves it to a dead-letter queue after N failures |
| 2 | [02_sns_sqs_fanout_filter](02_sns_sqs_fanout_filter) | A `FilterPolicy` on an SNS subscription filters at the SNS layer — the queue never even receives what it doesn't match |
| 3 | [03_dynamodb_conditional_writes](03_dynamodb_conditional_writes) | A client-side read-modify-write race silently loses an update; a `ConditionExpression` rejects the stale writer instead of corrupting data |
| 4 | [04_secrets_manager_versioning](04_secrets_manager_versioning) | `AWSPREVIOUS` genuinely holds the pre-rotation secret value — code that ignores `VersionStage` can never retrieve it during a rotation window |
| 5 | [05_s3_event_notifications](05_s3_event_notifications) | An S3 upload can push an event straight to SQS with zero polling — plus a real discovery: S3 also fires a one-time `s3:TestEvent` the moment notifications are configured |

## Protocol

```
1. Open the lab's lab.py, read the module docstring
2. Fill in the TODO
3. Run ./verify.sh -> PASS moves you to the next lab; FAIL tells you
   specifically what it expected vs what it saw
4. Answer the README's SOCH questions out loud before moving on
```

## Checklist

- [ ] Lab 1 — SQS dead-letter queue redrive
- [ ] Lab 2 — SNS → SQS fan-out with a message filter policy
- [ ] Lab 3 — DynamoDB conditional writes prevent lost updates
- [ ] Lab 4 — Secrets Manager AWSCURRENT vs AWSPREVIOUS
- [ ] Lab 5 — S3 event notifications → SQS
