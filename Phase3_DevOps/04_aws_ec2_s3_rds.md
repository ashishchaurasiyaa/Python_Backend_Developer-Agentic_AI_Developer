# AWS — EC2, S3, RDS, SQS/SNS, IAM Roles

## Quick Concepts
- **EC2** = Virtual Machine (cloud mein server)
- **S3** = Object storage (files, images, backups)
- **RDS** = Managed relational database (PostgreSQL, MySQL)
- **SQS** = Message queue (async tasks ke liye)
- **SNS** = Pub/Sub notifications (email, SMS, SQS trigger)
- **IAM** = Identity & Access Management — who can do what

---

## Interview Questions & Answers

### Q1: FastAPI app ko EC2 par deploy karne ka full process kya hai?
**Answer:**

**Step 1: EC2 Instance launch karo**
- Ubuntu 22.04 AMI choose karo
- Security Group: Port 22 (SSH), 80 (HTTP), 443 (HTTPS) open karo
- Key pair download karo (.pem file)

**Step 2: Server setup karo**
```bash
# Connect
ssh -i mykey.pem ubuntu@<EC2_PUBLIC_IP>

# Docker install karo
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker ubuntu
newgrp docker

# App deploy karo
git clone https://github.com/myuser/myapp.git
cd myapp
docker compose up -d
```

**Step 3: Elastic IP assign karo** (restart par IP change na ho)

**Step 4: Domain → EC2 Elastic IP map karo** (Route 53 ya DNS provider)

---

### Q2: S3 mein file upload/download Python mein kaise karte hain?
**Answer:**
```python
import boto3
from botocore.exceptions import ClientError

s3 = boto3.client(
    "s3",
    aws_access_key_id="YOUR_KEY",       # production mein IAM role use karo
    aws_secret_access_key="YOUR_SECRET",
    region_name="ap-south-1"
)

# Upload file
def upload_file(local_path: str, bucket: str, s3_key: str) -> str:
    s3.upload_file(local_path, bucket, s3_key)
    return f"https://{bucket}.s3.amazonaws.com/{s3_key}"

# Upload file object (memory mein)
def upload_fileobj(file_bytes: bytes, bucket: str, s3_key: str, content_type: str):
    import io
    s3.upload_fileobj(
        io.BytesIO(file_bytes),
        bucket,
        s3_key,
        ExtraArgs={"ContentType": content_type, "ACL": "public-read"}
    )

# Download
def download_file(bucket: str, s3_key: str, local_path: str):
    s3.download_file(bucket, s3_key, local_path)

# Presigned URL (temporary access — 1 hour)
def get_presigned_url(bucket: str, s3_key: str, expiry: int = 3600) -> str:
    return s3.generate_presigned_url(
        "get_object",
        Params={"Bucket": bucket, "Key": s3_key},
        ExpiresIn=expiry
    )

# Delete
def delete_file(bucket: str, s3_key: str):
    s3.delete_object(Bucket=bucket, Key=s3_key)

# List files
def list_files(bucket: str, prefix: str = "") -> list:
    response = s3.list_objects_v2(Bucket=bucket, Prefix=prefix)
    return [obj["Key"] for obj in response.get("Contents", [])]
```

---

### Q3: FastAPI mein S3 file upload endpoint kaise banate hain?
**Answer:**
```python
from fastapi import FastAPI, UploadFile, File
import boto3
import uuid

app = FastAPI()
s3 = boto3.client("s3", region_name="ap-south-1")
BUCKET = "my-app-uploads"

@app.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    file_extension = file.filename.split(".")[-1]
    s3_key = f"uploads/{uuid.uuid4()}.{file_extension}"

    contents = await file.read()
    s3.put_object(
        Bucket=BUCKET,
        Key=s3_key,
        Body=contents,
        ContentType=file.content_type,
    )

    url = f"https://{BUCKET}.s3.amazonaws.com/{s3_key}"
    return {"url": url, "key": s3_key}
```

---

### Q4: RDS PostgreSQL setup aur connection kaise karte hain?
**Answer:**
**RDS Setup:**
- Multi-AZ: Yes (production ke liye)
- Storage: GP3, 20GB+ with autoscaling
- Security Group: sirf EC2 Security Group se port 5432 allow karo (0.0.0.0 nahi!)
- Backup retention: 7 days

**Python connection:**
```python
# .env
DATABASE_URL=postgresql://admin:password@mydb.xyz.ap-south-1.rds.amazonaws.com:5432/myapp

# SQLAlchemy async
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

engine = create_async_engine(
    DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://"),
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,  # dead connections detect karo
)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
```

---

### Q5: SQS se async tasks kaise handle karte hain?
**Answer:**
```python
import boto3
import json

sqs = boto3.client("sqs", region_name="ap-south-1")
QUEUE_URL = "https://sqs.ap-south-1.amazonaws.com/123456789/my-queue"

# Message send karo
def send_task(task_type: str, payload: dict):
    sqs.send_message(
        QueueUrl=QUEUE_URL,
        MessageBody=json.dumps({"task": task_type, "data": payload}),
        MessageGroupId="default",           # FIFO queue ke liye
        MessageDeduplicationId=str(uuid.uuid4())
    )

# Consumer (worker process)
def process_messages():
    while True:
        response = sqs.receive_message(
            QueueUrl=QUEUE_URL,
            MaxNumberOfMessages=10,
            WaitTimeSeconds=20,     # long polling — efficient
        )
        messages = response.get("Messages", [])
        for msg in messages:
            body = json.loads(msg["Body"])
            # process karo...
            handle_task(body["task"], body["data"])
            # process hone ke baad delete karo
            sqs.delete_message(
                QueueUrl=QUEUE_URL,
                ReceiptHandle=msg["ReceiptHandle"]
            )
```

---

### Q6: IAM Role kya hai? EC2 ko S3/SQS access dene ka best practice kya hai?
**Answer:**
**Kabhi bhi hardcode mat karo** AWS keys EC2 pe. Instead:

1. **IAM Role banao** (e.g., `MyAppRole`) with S3 + SQS permissions
2. EC2 instance launch karte waqt ya baad mein us role ko attach karo
3. Python code automatically instance metadata se credentials lega

```json
// IAM Policy (S3 + SQS permissions)
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": ["s3:GetObject", "s3:PutObject", "s3:DeleteObject"],
      "Resource": "arn:aws:s3:::my-app-bucket/*"
    },
    {
      "Effect": "Allow",
      "Action": ["sqs:SendMessage", "sqs:ReceiveMessage", "sqs:DeleteMessage"],
      "Resource": "arn:aws:sqs:ap-south-1:123456789:my-queue"
    }
  ]
}
```

```python
# IAM Role attached hone ke baad — no keys needed!
s3 = boto3.client("s3")   # automatically role credentials use karega
sqs = boto3.client("sqs")
```

---

### Q7: SNS kaise kaam karta hai?
**Answer:**
SNS = fan-out pattern. Ek message publish karo → multiple subscribers ko jaata hai.

```python
sns = boto3.client("sns", region_name="ap-south-1")
TOPIC_ARN = "arn:aws:sns:ap-south-1:123456789:order-notifications"

# Publish karo
def notify_order_placed(order_id: str):
    sns.publish(
        TopicArn=TOPIC_ARN,
        Message=json.dumps({"order_id": order_id, "status": "placed"}),
        Subject="New Order",
        MessageAttributes={
            "event_type": {
                "DataType": "String",
                "StringValue": "ORDER_PLACED"
            }
        }
    )

# Subscribers: SQS queue, Lambda, Email, HTTP endpoint
```

---

## AWS Services Quick Reference

| Service | Use Case | Python Library |
|---|---|---|
| EC2 | Virtual server | SSH / boto3 |
| S3 | File storage | boto3 s3 |
| RDS | PostgreSQL/MySQL | SQLAlchemy + asyncpg |
| SQS | Message queue | boto3 sqs |
| SNS | Notifications / fan-out | boto3 sns |
| Lambda | Serverless functions | boto3 lambda |
| CloudWatch | Logs + Metrics | boto3 cloudwatch |
| Secrets Manager | Store secrets safely | boto3 secretsmanager |
| ECR | Docker image registry | docker + aws ecr |

```bash
# AWS CLI useful commands
aws s3 ls s3://my-bucket/
aws s3 cp localfile.txt s3://my-bucket/
aws ec2 describe-instances --region ap-south-1
aws sqs list-queues
aws rds describe-db-instances
aws logs tail /aws/ec2/myapp --follow
```
