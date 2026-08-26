# IAM — Identity & Access Management (Deep Dive)

## Core Concept: Who Can Do What

IAM answers one question: **"Yeh entity yeh action kar sakti hai is resource pe?"**

```
Principal   →   Action   →   Resource
(Who)           (What)        (Which)

EC2 Instance → s3:GetObject → arn:aws:s3:::my-bucket/*
Lambda Fn    → sqs:SendMessage → arn:aws:sqs:ap-south-1:123:my-queue
Developer    → rds:CreateSnapshot → arn:aws:rds:*:*:db:prod-db
```

---

## 4 Identity Types

### 1. IAM User
- Ek actual person ya service (long-term credentials)
- Has: username + password (console) + access key + secret key (CLI/API)
- **Problem:** Static credentials leak ho sakti hai → prefer Roles for apps

### 2. IAM Group
- Users ka collection (e.g., `developers`, `devops`, `readonly`)
- Group ko policy attach karo → saare members ko inherit hoti hai
- Group mein Group nahi hota

### 3. IAM Role
- **No permanent credentials** — temporary credentials milti hain (STS)
- Assume kiya jaata hai: EC2, Lambda, ECS task, another AWS account
- **Golden rule: application code mein KABHI access keys mat daalo — Role use karo**

```
# WRONG ❌
import boto3
s3 = boto3.client('s3',
    aws_access_key_id='AKIAIOSFODNN7',     # hardcoded = leaked someday
    aws_secret_access_key='wJalrXUtn...'
)

# CORRECT ✅
import boto3
s3 = boto3.client('s3')   # boto3 automatically uses EC2 Instance Role
```

### 4. Service Role
- AWS service ko permission deta hai (e.g., EC2 Auto Scaling ko ENI manage karne ki)

---

## Policy Types

### Managed Policy (Preferred)
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": ["s3:GetObject", "s3:PutObject"],
      "Resource": "arn:aws:s3:::my-app-bucket/*"
    }
  ]
}
```
- AWS-managed (e.g., `AmazonS3ReadOnlyAccess`) — AWS maintains karta hai
- Customer-managed — tum banate ho, multiple roles/users ko attach kar sakte ho

### Inline Policy
- Directly ek user/role ke andar embed hoti hai
- Us entity ke saath delete hoti hai
- Avoid unless policy is specific to one entity

### Resource-Based Policy
- Resource PE lagti hai (not on identity)
- Example: S3 Bucket Policy — bucket batata hai kise access milegi

```json
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Principal": {"AWS": "arn:aws:iam::123456789:role/MyEC2Role"},
    "Action": "s3:GetObject",
    "Resource": "arn:aws:s3:::my-bucket/*"
  }]
}
```

---

## IAM Policy Evaluation Logic

```
Explicit DENY anywhere? → DENY (overrides everything)
    ↓ No
Explicit ALLOW? → ALLOW
    ↓ No
Default → DENY (implicit)
```

**Key:** DENY always wins. Ek policy mein allow karo, doosri mein deny karo → DENY.

---

## Least Privilege Principle

**Definition:** Sirf woh permissions do jo kaam ke liye zaroori hain, kuch nahi.

```
# Bad: Too permissive ❌
"Action": ["s3:*"]              # everything on S3
"Resource": "*"                 # on all buckets

# Good: Least privilege ✅
"Action": ["s3:GetObject", "s3:PutObject"]
"Resource": "arn:aws:s3:::my-app-bucket/uploads/*"
```

---

## IAM Role for EC2 (Most Common Pattern)

```
EC2 Instance
    ↓ (attached at launch or after)
IAM Instance Profile
    ↓
IAM Role: "MyDjangoAppRole"
    ↓
Policies:
  - s3:GetObject, s3:PutObject on my-bucket
  - sqs:SendMessage, sqs:ReceiveMessage on my-queue
  - secretsmanager:GetSecretValue on my-db-secret
```

**How boto3 finds credentials (in order):**
1. Environment variables (`AWS_ACCESS_KEY_ID`)
2. `~/.aws/credentials` file
3. EC2 Instance Metadata Service (IMDS) — Role credentials ← **production mein yahi use hota hai**
4. ECS Task Role / Lambda Execution Role

---

## STS — Temporary Credentials

```
EC2 with Role → calls STS AssumeRole → gets:
  - AccessKeyId (temporary)
  - SecretAccessKey (temporary)
  - SessionToken
  - Expiration (1hr default, max 12hr)
```

**Cross-account access pattern:**
```
Account A (your app) → AssumeRole → Account B's role → Access B's S3
```

---

## Common Patterns

### Django on EC2 accessing S3 + SQS + Secrets Manager
```python
# settings.py — No credentials needed if EC2 has correct Role
import boto3, json

def get_secret(secret_name: str) -> dict:
    client = boto3.client("secretsmanager", region_name="ap-south-1")
    return json.loads(client.get_secret_value(SecretId=secret_name)["SecretString"])

secrets = get_secret("prod/myapp/db")
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "HOST": secrets["host"],
        "NAME": secrets["dbname"],
        "USER": secrets["username"],
        "PASSWORD": secrets["password"],
    }
}
```

### Lambda accessing DynamoDB
```python
import boto3
# Lambda execution role mein DynamoDB permissions honi chahiye
dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table("my-table")
table.put_item(Item={"pk": "user#123", "name": "Ashish"})
```

---

## Interview Q&A

**Q: IAM User vs IAM Role kya fark hai?**
A: User ke paas permanent credentials hain (access key). Role ke paas temporary credentials hain jo assume karne pe milti hain. Applications ke liye always Role use karo — static keys leak ho sakti hain, rotate karna padhta hai, aur IMDS se automatic rotate hoti hain.

**Q: EC2 ko S3 access dene ka best practice kya hai?**
A: IAM Role banao with S3 permissions → EC2 launch karte waqt Instance Profile mein attach karo → boto3 automatically IMDS se credentials uthata hai. Code mein koi key nahi.

**Q: Policy evaluation mein kya hota hai agar ek policy Allow kare aur doosri Deny?**
A: Explicit Deny ALWAYS wins. Allow kabhi Deny ko override nahi karta.

**Q: Least privilege kaise implement karte hain practically?**
A: AWS Access Analyzer use karo — actual API calls monitor karta hai aur minimum required permissions suggest karta hai. IAM Access Advisor bhi dekhta hai kaunsi services last 90 days mein access nahi hui.

**Q: Kya Groups mein Groups ho sakte hain?**
A: Nahi. IAM Groups flat hain — nested groups nahi hote.
