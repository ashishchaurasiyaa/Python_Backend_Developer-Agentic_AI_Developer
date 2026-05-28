# Lecture 3 — Practical Hands-On: Serverless Architecture

> **Theory file:** [03_Serverless_Architecture.md](03_Serverless_Architecture.md)

---

## 🎯 Is Practical Mein Kya Banayenge?

Production serverless implementations:

1. ✅ **AWS Lambda** with Serverless Framework
2. ✅ **HTTP API** with API Gateway
3. ✅ **S3-triggered** image processing
4. ✅ **DynamoDB Streams** triggered function
5. ✅ **Scheduled jobs** (EventBridge)
6. ✅ **Step Functions** for orchestration
7. ✅ **Cold start optimization**
8. ✅ **Multi-region deployment**
9. ✅ **Cost monitoring**
10. ✅ **End-to-end** event pipeline

By end: aap **production serverless apps** bana sakte ho.

---

## 1. Project Structure

```
serverless_demo/
├── serverless.yml
├── package.json
├── requirements.txt
├── README.md
│
├── functions/
│   ├── api/
│   │   ├── users.py
│   │   ├── orders.py
│   │   └── auth.py
│   ├── triggers/
│   │   ├── image_processor.py
│   │   ├── stream_handler.py
│   │   └── scheduled_cleanup.py
│   ├── workflows/
│   │   └── order_saga.py
│   └── shared/
│       ├── auth.py
│       └── db.py
│
├── infrastructure/
│   ├── dynamodb.yml
│   ├── s3.yml
│   └── step_functions.json
│
└── tests/
    └── test_handlers.py
```

---

## 2. Setup

```bash
# Install Serverless Framework
$ npm install -g serverless

# Install plugins
$ serverless plugin install -n serverless-python-requirements

# AWS credentials
$ export AWS_ACCESS_KEY_ID=...
$ export AWS_SECRET_ACCESS_KEY=...
```

---

## 3. 🌐 HTTP API Function

### `functions/api/users.py`

```python
"""
HTTP API endpoint - Lambda + API Gateway
"""
import json
import boto3
from datetime import datetime
import os
import uuid

# Initialize OUTSIDE handler (reused across warm invocations)
dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(os.environ["USERS_TABLE"])

def get_user(event, context):
    """GET /users/{id}"""
    user_id = event["pathParameters"]["id"]
    
    try:
        response = table.get_item(Key={"id": user_id})
        
        if "Item" not in response:
            return {
                "statusCode": 404,
                "body": json.dumps({"error": "User not found"})
            }
        
        return {
            "statusCode": 200,
            "body": json.dumps(response["Item"])
        }
    
    except Exception as e:
        print(f"Error: {e}")
        return {
            "statusCode": 500,
            "body": json.dumps({"error": "Internal server error"})
        }

def create_user(event, context):
    """POST /users"""
    body = json.loads(event["body"])
    
    user = {
        "id": str(uuid.uuid4()),
        "email": body["email"],
        "name": body["name"],
        "created_at": datetime.utcnow().isoformat(),
    }
    
    table.put_item(Item=user)
    
    return {
        "statusCode": 201,
        "body": json.dumps(user)
    }

def list_users(event, context):
    """GET /users"""
    response = table.scan()
    
    return {
        "statusCode": 200,
        "body": json.dumps({
            "users": response["Items"],
            "count": response["Count"],
        })
    }
```

### `serverless.yml`

```yaml
service: my-serverless-app

frameworkVersion: '3'

provider:
  name: aws
  runtime: python3.11
  region: us-east-1
  stage: ${opt:stage, 'dev'}
  
  memorySize: 256
  timeout: 30
  
  environment:
    USERS_TABLE: ${self:service}-${self:provider.stage}-users
    LOG_LEVEL: INFO
  
  # IAM permissions
  iam:
    role:
      statements:
        - Effect: Allow
          Action:
            - dynamodb:GetItem
            - dynamodb:PutItem
            - dynamodb:Scan
            - dynamodb:Query
          Resource:
            - "arn:aws:dynamodb:${self:provider.region}:*:table/${self:provider.environment.USERS_TABLE}"

functions:
  getUser:
    handler: functions/api/users.get_user
    events:
      - httpApi:
          path: /users/{id}
          method: get
  
  createUser:
    handler: functions/api/users.create_user
    events:
      - httpApi:
          path: /users
          method: post
  
  listUsers:
    handler: functions/api/users.list_users
    events:
      - httpApi:
          path: /users
          method: get

resources:
  Resources:
    UsersTable:
      Type: AWS::DynamoDB::Table
      Properties:
        TableName: ${self:provider.environment.USERS_TABLE}
        AttributeDefinitions:
          - AttributeName: id
            AttributeType: S
        KeySchema:
          - AttributeName: id
            KeyType: HASH
        BillingMode: PAY_PER_REQUEST
```

### Deploy & Test

```bash
$ serverless deploy

# Output:
# endpoints:
#   POST - https://abc123.execute-api.us-east-1.amazonaws.com/users
#   GET - https://abc123.execute-api.us-east-1.amazonaws.com/users/{id}
#   GET - https://abc123.execute-api.us-east-1.amazonaws.com/users

# Test
$ curl -X POST https://abc123.../users \
    -H "Content-Type: application/json" \
    -d '{"email": "ashish@example.com", "name": "Ashish"}'

$ curl https://abc123.../users/UUID
```

---

## 4. 📸 S3-Triggered Image Processing

### `functions/triggers/image_processor.py`

```python
"""
S3 trigger: process images on upload.
"""
import boto3
from PIL import Image
import io
import os

s3 = boto3.client("s3")
OUTPUT_BUCKET = os.environ["OUTPUT_BUCKET"]

def process_image(event, context):
    """
    Triggered when image uploaded to S3.
    Generates thumbnails in multiple sizes.
    """
    for record in event["Records"]:
        bucket = record["s3"]["bucket"]["name"]
        key = record["s3"]["object"]["key"]
        
        print(f"Processing s3://{bucket}/{key}")
        
        # Download original
        response = s3.get_object(Bucket=bucket, Key=key)
        image_bytes = response["Body"].read()
        
        # Open with PIL
        img = Image.open(io.BytesIO(image_bytes))
        
        # Generate multiple sizes
        sizes = {
            "thumbnail": (150, 150),
            "small": (300, 300),
            "medium": (600, 600),
            "large": (1200, 1200),
        }
        
        for size_name, dimensions in sizes.items():
            # Resize maintaining aspect ratio
            img_copy = img.copy()
            img_copy.thumbnail(dimensions, Image.Resampling.LANCZOS)
            
            # Save to buffer
            buffer = io.BytesIO()
            img_copy.save(buffer, format="JPEG", quality=85, optimize=True)
            buffer.seek(0)
            
            # Upload to output bucket
            output_key = f"{size_name}/{key}"
            s3.put_object(
                Bucket=OUTPUT_BUCKET,
                Key=output_key,
                Body=buffer.getvalue(),
                ContentType="image/jpeg",
                Metadata={
                    "original_key": key,
                    "size": size_name,
                }
            )
            
            print(f"  ✓ Uploaded {size_name}: {output_key}")
    
    return {"processed": len(event["Records"])}
```

### Add to `serverless.yml`

```yaml
functions:
  processImage:
    handler: functions/triggers/image_processor.process_image
    memorySize: 512   # More memory = faster CPU
    timeout: 60
    events:
      - s3:
          bucket: ${self:service}-${self:provider.stage}-uploads
          event: s3:ObjectCreated:*
          rules:
            - suffix: .jpg
            - suffix: .png
    environment:
      OUTPUT_BUCKET: ${self:service}-${self:provider.stage}-processed
    layers:
      # Pillow needs C library layer for Lambda
      - arn:aws:lambda:us-east-1:770693421928:layer:Klayers-p311-Pillow:1
```

### Test

```bash
# Upload an image
$ aws s3 cp photo.jpg s3://my-serverless-app-dev-uploads/

# Lambda triggers automatically
# Check processed bucket
$ aws s3 ls s3://my-serverless-app-dev-processed/ --recursive
# thumbnail/photo.jpg
# small/photo.jpg
# medium/photo.jpg
# large/photo.jpg
```

---

## 5. 🔄 DynamoDB Streams Handler

### `functions/triggers/stream_handler.py`

```python
"""
React to changes in DynamoDB.
Use cases: send notifications, sync to search index, analytics.
"""
import json
import boto3

sns = boto3.client("sns")
opensearch = boto3.client("opensearch")

def handle_stream(event, context):
    """
    Triggered on DynamoDB table changes.
    """
    for record in event["Records"]:
        event_name = record["eventName"]  # INSERT, MODIFY, REMOVE
        
        if event_name == "INSERT":
            handle_new_user(record["dynamodb"]["NewImage"])
        
        elif event_name == "MODIFY":
            handle_user_update(
                old_image=record["dynamodb"]["OldImage"],
                new_image=record["dynamodb"]["NewImage"],
            )
        
        elif event_name == "REMOVE":
            handle_user_delete(record["dynamodb"]["OldImage"])
    
    return {"batchItemFailures": []}  # Return failures for retry

def handle_new_user(item):
    """When new user added"""
    user_id = item["id"]["S"]
    email = item["email"]["S"]
    
    # Send welcome notification
    sns.publish(
        TopicArn=os.environ["WELCOME_TOPIC"],
        Message=json.dumps({
            "user_id": user_id,
            "email": email,
        })
    )
    
    # Index in search
    # opensearch.index(...)
    
    print(f"Processed new user: {user_id}")

def handle_user_update(old_image, new_image):
    """When user updated"""
    user_id = new_image["id"]["S"]
    print(f"User {user_id} updated")
    # Re-index in search...

def handle_user_delete(item):
    """When user removed"""
    user_id = item["id"]["S"]
    print(f"User {user_id} deleted")
    # Remove from search index...
```

### Configuration

```yaml
functions:
  handleStream:
    handler: functions/triggers/stream_handler.handle_stream
    events:
      - stream:
          type: dynamodb
          arn:
            Fn::GetAtt: [UsersTable, StreamArn]
          batchSize: 10
          startingPosition: LATEST
          maximumRetryAttempts: 3
    environment:
      WELCOME_TOPIC: !Ref WelcomeTopic

resources:
  Resources:
    UsersTable:
      Type: AWS::DynamoDB::Table
      Properties:
        StreamSpecification:
          StreamViewType: NEW_AND_OLD_IMAGES   # Stream changes!
        # ... rest of table config
```

---

## 6. ⏰ Scheduled Jobs

### `functions/triggers/scheduled_cleanup.py`

```python
"""
Scheduled batch job - runs on cron schedule.
"""
import boto3
from datetime import datetime, timedelta

dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(os.environ["USERS_TABLE"])

def cleanup_old_sessions(event, context):
    """
    Runs daily at 3 AM UTC.
    Cleans up expired sessions.
    """
    cutoff = (datetime.utcnow() - timedelta(days=30)).isoformat()
    
    print(f"Cleaning up sessions older than {cutoff}")
    
    deleted_count = 0
    
    # Scan and delete (use Query in production with proper index!)
    response = table.scan(
        FilterExpression="last_active < :cutoff",
        ExpressionAttributeValues={":cutoff": cutoff}
    )
    
    for item in response["Items"]:
        table.delete_item(Key={"id": item["id"]})
        deleted_count += 1
    
    print(f"Deleted {deleted_count} expired sessions")
    
    return {"deleted": deleted_count}

def daily_report(event, context):
    """Generate daily metrics report"""
    print("Generating daily report...")
    
    # Query metrics
    yesterday = (datetime.utcnow() - timedelta(days=1)).strftime("%Y-%m-%d")
    
    # Send via email, Slack, etc.
    # ...
    
    return {"date": yesterday}
```

### Configuration

```yaml
functions:
  cleanupOldSessions:
    handler: functions/triggers/scheduled_cleanup.cleanup_old_sessions
    timeout: 300  # 5 minutes
    events:
      - schedule:
          rate: cron(0 3 * * ? *)  # Daily at 3 AM UTC
          description: "Clean up old sessions daily"
  
  dailyReport:
    handler: functions/triggers/scheduled_cleanup.daily_report
    events:
      - schedule: rate(1 day)
```

---

## 7. 🎼 Step Functions Orchestration

### Complex Workflow Example

```yaml
# infrastructure/step_functions.json
{
  "Comment": "Order processing workflow",
  "StartAt": "ValidateOrder",
  "States": {
    "ValidateOrder": {
      "Type": "Task",
      "Resource": "arn:aws:lambda:us-east-1:123:function:validate-order",
      "Next": "ReserveInventory",
      "Catch": [{
        "ErrorEquals": ["States.ALL"],
        "Next": "OrderFailed"
      }]
    },
    "ReserveInventory": {
      "Type": "Task",
      "Resource": "arn:aws:lambda:us-east-1:123:function:reserve-inventory",
      "Next": "ChargePayment",
      "Catch": [{
        "ErrorEquals": ["InsufficientStock"],
        "Next": "OrderFailed"
      }]
    },
    "ChargePayment": {
      "Type": "Task",
      "Resource": "arn:aws:lambda:us-east-1:123:function:charge-payment",
      "Next": "ShipOrder",
      "Retry": [{
        "ErrorEquals": ["PaymentDeclined"],
        "MaxAttempts": 3,
        "IntervalSeconds": 2,
        "BackoffRate": 2
      }],
      "Catch": [{
        "ErrorEquals": ["States.ALL"],
        "Next": "ReleaseInventory"
      }]
    },
    "ShipOrder": {
      "Type": "Task",
      "Resource": "arn:aws:lambda:us-east-1:123:function:ship-order",
      "Next": "Success"
    },
    "ReleaseInventory": {
      "Type": "Task",
      "Resource": "arn:aws:lambda:us-east-1:123:function:release-inventory",
      "Next": "OrderFailed"
    },
    "Success": {
      "Type": "Succeed"
    },
    "OrderFailed": {
      "Type": "Fail",
      "Cause": "Order processing failed"
    }
  }
}
```

### Start Workflow

```python
import boto3
import json

sfn = boto3.client("stepfunctions")

def start_order_workflow(event, context):
    """Trigger workflow on new order"""
    response = sfn.start_execution(
        stateMachineArn=os.environ["WORKFLOW_ARN"],
        name=f"order-{event['order_id']}",
        input=json.dumps(event),
    )
    
    return {"execution_arn": response["executionArn"]}
```

---

## 8. ⚡ Cold Start Optimization

### Tip 1: Smaller Deployment Package

```python
# Bad: importing unused libraries
import pandas as pd  # Heavy!
import numpy as np
import boto3

def handler(event, context):
    # Just need boto3
    pass

# Good: import only what's needed
import boto3
```

### Tip 2: Initialization Outside Handler

```python
# Bad: Recreate client on every invocation
def handler(event, context):
    client = boto3.client("s3")  # Slow!
    # ...

# Good: Reuse across warm invocations
import boto3
client = boto3.client("s3")  # ← Created once per container

def handler(event, context):
    # Use existing client
    pass
```

### Tip 3: Lazy Loading

```python
# Heavy imports only when needed
def handler(event, context):
    if event.get("send_email"):
        from sendgrid import SendGridAPIClient  # Only loaded if needed
        # ...
```

### Tip 4: Provisioned Concurrency

```yaml
functions:
  api:
    handler: handler.api
    provisionedConcurrency: 5  # Keep 5 instances warm always!
```

### Tip 5: Smaller Memory = Slower CPU

```
Memory affects CPU allocation!

256MB: 0.4 CPU
512MB: 0.7 CPU
1024MB: 1.5 CPU
2048MB: 3.0 CPU

Sometimes MORE memory = LOWER total cost
because function runs faster.

Test it! Use Lambda Power Tuning:
https://github.com/alexcasalboni/aws-lambda-power-tuning
```

### Tip 6: Use ARM (Graviton)

```yaml
functions:
  api:
    handler: handler.api
    architecture: arm64  # 20% cheaper + faster!
```

---

## 9. 💰 Cost Monitoring

### Set Budget Alerts

```yaml
# Add CloudFormation for budget
resources:
  Resources:
    Budget:
      Type: AWS::Budgets::Budget
      Properties:
        Budget:
          BudgetName: serverless-monthly
          BudgetType: COST
          TimeUnit: MONTHLY
          BudgetLimit:
            Amount: 50
            Unit: USD
        NotificationsWithSubscribers:
          - Notification:
              NotificationType: ACTUAL
              ComparisonOperator: GREATER_THAN
              Threshold: 80  # Alert at 80% of budget
            Subscribers:
              - SubscriptionType: EMAIL
                Address: alerts@example.com
```

### Track Per-Function Costs

```python
# Tag functions for cost allocation
functions:
  api:
    handler: handler.api
    tags:
      Service: api
      Environment: production
      CostCenter: engineering
```

### Cost Calculation

```python
"""
Estimate Lambda cost per month.
"""
def estimate_cost(invocations_per_month, avg_duration_ms, memory_mb):
    # AWS Lambda pricing (us-east-1)
    REQUEST_COST = 0.20 / 1_000_000  # per request
    GB_SEC_COST = 0.0000166667        # per GB-second
    
    request_cost = invocations_per_month * REQUEST_COST
    
    gb = memory_mb / 1024
    duration_sec = avg_duration_ms / 1000
    compute_cost = invocations_per_month * gb * duration_sec * GB_SEC_COST
    
    return {
        "request_cost": request_cost,
        "compute_cost": compute_cost,
        "total": request_cost + compute_cost,
    }

# Example: 1M req/month, 200ms avg, 256MB
print(estimate_cost(1_000_000, 200, 256))
# {'request_cost': 0.20, 'compute_cost': 0.83, 'total': 1.03}
```

---

## 10. 🌍 Multi-Region Deployment

```yaml
# Deploy to multiple regions for low latency
provider:
  name: aws
  # Use different regions

# Deploy to us-east-1
$ serverless deploy --region us-east-1

# Deploy to eu-west-1
$ serverless deploy --region eu-west-1

# Use Route53 for geo-routing!
```

---

## 11. 🧪 Local Testing

```python
# tests/test_handlers.py
import pytest
from functions.api.users import get_user

def test_get_user_success(monkeypatch):
    """Mock DynamoDB"""
    def mock_get_item(*args, **kwargs):
        return {"Item": {"id": "123", "name": "Ashish"}}
    
    monkeypatch.setattr("functions.api.users.table.get_item", mock_get_item)
    
    event = {"pathParameters": {"id": "123"}}
    result = get_user(event, None)
    
    assert result["statusCode"] == 200
    assert "Ashish" in result["body"]
```

### Invoke Locally

```bash
# Test function locally
$ serverless invoke local --function getUser --data '{"pathParameters":{"id":"123"}}'

# With SAM Local
$ sam local invoke -e events/test.json
```

---

## 12. Key Learnings Summary

```
✅ Serverless Framework for declarative deployment
✅ HTTP APIs via API Gateway
✅ S3-triggered functions for file processing
✅ DynamoDB Streams for CDC
✅ Scheduled jobs replace cron servers
✅ Step Functions for complex workflows
✅ Cold start optimization techniques
✅ Memory affects CPU - tune both!
✅ ARM (Graviton) = 20% cheaper

🎯 Production serverless stack:
   API Gateway → Lambda → DynamoDB
   + S3 triggers for media processing
   + Step Functions for orchestration
   + EventBridge for scheduled tasks
   + CloudWatch for observability
```

---

## 🎬 What's Next?

In **Lecture 4**, we'll explore **Docker + Kubernetes** — the foundation of containerized cloud-native deployment.

> **Next lecture:** [04_Docker_Kubernetes.md](04_Docker_Kubernetes.md)

---

## 📚 Try It Yourself

1. Build complete **CRUD API** with Lambda + DynamoDB
2. Add **authentication** with API Gateway + Cognito
3. Create **image resize pipeline** with S3 + Lambda
4. Implement **saga workflow** with Step Functions
5. Compare **costs** vs equivalent EC2 setup
