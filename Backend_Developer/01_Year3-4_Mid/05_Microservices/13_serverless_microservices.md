# Serverless Microservices — Lambda, Step Functions, EventBridge

## Quick Concepts

**WHAT:**
- **Serverless** = No server management, pay per execution
- **Lambda** = AWS function-as-a-service (FaaS)
- **API Gateway** = Lambda HTTP front-end
- **Step Functions** = Workflow orchestration (state machine)
- **EventBridge** = Event bus for serverless event routing
- **SQS/SNS** = Decoupling messaging
- **Cold start** = First-invocation latency (Python ~1-3s)

**WHY serverless for microservices:**
- ✅ No infrastructure to manage
- ✅ Auto-scale to zero (cost when idle)
- ✅ Pay per invocation
- ❌ Cold starts (latency-sensitive apps suffer)
- ❌ 15-min execution limit
- ❌ Vendor lock-in
- ❌ Debugging harder

**HOW serverless architecture:**

```
┌──────────────────┐
│  API Gateway     │
└────────┬─────────┘
         │
         ▼
   ┌─────────┐    ┌─────────┐    ┌─────────┐
   │ Lambda  │───►│ Lambda  │───►│ Lambda  │
   │ users   │    │ orders  │    │ payments│
   └─────────┘    └─────────┘    └─────────┘
         │              │              │
         ▼              ▼              ▼
   ┌─────────┐    ┌─────────┐    ┌─────────┐
   │DynamoDB │    │DynamoDB │    │Stripe   │
   └─────────┘    └─────────┘    └─────────┘

         ┌──────────────────┐
         │  EventBridge      │  ← Event routing
         └─────┬────────────┘
               │
         ┌─────┴───────┬────────────┐
         ▼             ▼            ▼
    SQS Queue    Lambda     SNS Topic
```

---

## Interview Questions & Answers

### Q1: When use serverless vs containers (Lambda vs ECS/EKS)?

**Answer:**

**WHAT:** Decision matrix for compute choice.

**HOW — Comparison:**

| Aspect | Lambda | ECS Fargate | EKS |
|---|---|---|---|
| **Server management** | None | None | Some |
| **Scaling** | Auto, instant | Auto, ~minute | Auto, ~minute |
| **Cost (low traffic)** | Cheapest | Higher | Highest |
| **Cost (high traffic)** | Higher | Lower | Lowest |
| **Cold starts** | 1-3s | None | None |
| **Max runtime** | 15 min | Unlimited | Unlimited |
| **WebSocket** | Limited (separate API) | ✅ | ✅ |
| **Long-running** | ❌ | ✅ | ✅ |
| **Custom runtime** | Limited | Any | Any |

**WHEN to use Lambda:**

```
✅ Great fit:
- Webhooks (POST /webhooks/stripe)
- Cron jobs (daily reports)
- Image processing on S3 upload
- API endpoints with bursty traffic
- Backend for mobile (low traffic per user)
- DynamoDB streams processors
- IoT data ingestion

❌ Bad fit:
- WebSocket-heavy (use API Gateway WebSocket carefully)
- Long-running jobs (> 15 min)
- High RPS with consistent load
- Apps needing custom binaries
- ML inference with large models
```

**HOW — Cost crossover analysis:**

```
Lambda pricing: $0.20 per 1M invocations + $0.0000166667 per GB-second

Example: 1000 RPS average, 100ms execution, 512MB memory

Lambda:
- 1000 * 86400 = 86.4M invocations/day
- 86.4M * $0.20 / 1M = $17.28/day (invocations)
- 86.4M * 0.1s * 0.5GB * $0.0000166 = $72/day (compute)
- Total: ~$90/day = $2700/month

ECS Fargate equivalent (3 tasks, 1 vCPU, 2GB each):
- $35/month per task = $105/month

🎯 ECS wins for steady high load
🎯 Lambda wins for sporadic bursts
```

---

### Q2: Cold start mitigation — provisioned concurrency, SnapStart?

**Answer:**

**WHAT:** Cold start = first invocation after idle (initialize runtime, load code).

**WHY:**
- Python Lambda: ~1-3s cold start
- Java: ~3-8s
- Affects p99 latency badly

**HOW — Mitigation strategies:**

**1. Provisioned Concurrency (Pre-warmed instances)**

```yaml
# template.yaml (AWS SAM)
Resources:
  ApiFunction:
    Type: AWS::Serverless::Function
    Properties:
      Runtime: python3.12
      Handler: app.handler
      MemorySize: 1024
      ProvisionedConcurrencyConfig:
        ProvisionedConcurrentExecutions: 10    # ⭐ 10 always-warm
      AutoPublishAlias: live
```

**Cost:** Pay for provisioned capacity (~50% of full instance cost)

**2. Reduce Package Size**

```python
# ❌ Bad: import heavy libraries at module level
import pandas as pd
import numpy as np
import tensorflow as tf
import requests

def handler(event, context):
    ...

# ✅ Good: import inside function (only when needed)
def handler(event, context):
    if needs_data_processing(event):
        import pandas as pd     # Lazy
        ...
    return {"status": "ok"}
```

**3. Use Lambda Layers (shared deps)**

```bash
# Create layer for heavy deps
mkdir -p layer/python
pip install pandas numpy -t layer/python

cd layer
zip -r9 ../layer.zip .

# Upload as layer
aws lambda publish-layer-version \
  --layer-name data-processing-deps \
  --zip-file fileb://layer.zip \
  --compatible-runtimes python3.12

# Use in function (don't duplicate deps)
```

**4. ARM64 (Graviton) — Faster + Cheaper**

```yaml
# template.yaml
Architectures: [arm64]    # ⭐ 20% cheaper, 19% faster
```

**5. Use Init Code Caching**

```python
# ⭐ Module-level code runs ONCE per cold start
# Reuse expensive setups

import boto3

# Module-level — runs once per container
# Connection pools, DB clients, etc.
dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table('users')

def handler(event, context):
    # Function-level — runs each invocation
    user_id = event['user_id']
    response = table.get_item(Key={'id': user_id})    # Reuses 'table'
    return response['Item']
```

**6. Keep Functions Warm (anti-pattern, prefer #1)**

```python
# CloudWatch scheduled event every 5 min
@app.scheduled("cron(0/5 * * * ? *)")
def keep_warm(event, context):
    """Anti-pattern: schedule pings to keep warm."""
    return {"warmed": True}

# Modern approach: use Provisioned Concurrency
```

---

### Q3: FastAPI on Lambda — Mangum pattern?

**Answer:**

**WHAT:** Run FastAPI app on Lambda via Mangum adapter.

**WHY:**
- Familiar framework (vs writing raw Lambda handlers)
- Type validation (Pydantic)
- OpenAPI docs
- Reuse existing FastAPI code

**HOW:**

```python
# pip install fastapi mangum

# app/main.py
from fastapi import FastAPI, HTTPException
from mangum import Mangum

app = FastAPI(title="Serverless API")

@app.get("/users/{user_id}")
async def get_user(user_id: int):
    # Lambda code here
    return {"id": user_id, "name": "Alice"}


@app.post("/users")
async def create_user(user: dict):
    return {"id": 1, **user}


# ⭐ Lambda handler
handler = Mangum(app, lifespan="off")
```

```yaml
# template.yaml (SAM)
Resources:
  ApiFunction:
    Type: AWS::Serverless::Function
    Properties:
      Runtime: python3.12
      Handler: app.main.handler        # ⭐ Mangum handler
      MemorySize: 1024
      Timeout: 30
      Architectures: [arm64]

      Events:
        ApiEvents:
          Type: HttpApi               # ⭐ HTTP API (cheaper than REST API)
          Properties:
            Path: /{proxy+}
            Method: ANY
```

```bash
# Build + deploy
sam build
sam deploy --guided
```

**HOW — Local testing:**

```bash
# Test locally
sam local start-api

# Now: curl http://localhost:3000/users/1
```

---

### Q4: Step Functions — workflow orchestration?

**Answer:**

**WHAT:** State machine for orchestrating Lambda functions + other AWS services.

**WHY:**
- Visual workflow
- Built-in retry, error handling
- Wait for human approval
- Parallel execution
- Long-running (1 year max)

**HOW — State machine definition:**

```json
{
  "Comment": "Order processing workflow",
  "StartAt": "ValidateOrder",
  "States": {
    "ValidateOrder": {
      "Type": "Task",
      "Resource": "arn:aws:lambda:..:function:validate-order",
      "Next": "ChargePayment",
      "Retry": [
        {
          "ErrorEquals": ["States.TaskFailed"],
          "IntervalSeconds": 2,
          "MaxAttempts": 3,
          "BackoffRate": 2.0
        }
      ],
      "Catch": [
        {
          "ErrorEquals": ["States.ALL"],
          "Next": "OrderFailed"
        }
      ]
    },

    "ChargePayment": {
      "Type": "Task",
      "Resource": "arn:aws:states:::lambda:invoke",
      "Parameters": {
        "FunctionName": "charge-payment",
        "Payload.$": "$"
      },
      "Next": "ReserveInventory"
    },

    "ReserveInventory": {
      "Type": "Parallel",
      "Branches": [
        {
          "StartAt": "ReserveWarehouseA",
          "States": {
            "ReserveWarehouseA": {
              "Type": "Task",
              "Resource": "arn:aws:lambda:..:function:reserve-warehouse-a",
              "End": true
            }
          }
        },
        {
          "StartAt": "ReserveWarehouseB",
          "States": {
            "ReserveWarehouseB": {
              "Type": "Task",
              "Resource": "arn:aws:lambda:..:function:reserve-warehouse-b",
              "End": true
            }
          }
        }
      ],
      "Next": "ShipOrder"
    },

    "ShipOrder": {
      "Type": "Task",
      "Resource": "arn:aws:lambda:..:function:ship-order",
      "Next": "WaitForDelivery"
    },

    "WaitForDelivery": {
      "Type": "Wait",
      "Seconds": 86400,    // Wait 24 hours
      "Next": "ConfirmDelivery"
    },

    "ConfirmDelivery": {
      "Type": "Task",
      "Resource": "arn:aws:lambda:..:function:confirm-delivery",
      "End": true
    },

    "OrderFailed": {
      "Type": "Task",
      "Resource": "arn:aws:lambda:..:function:refund-order",
      "End": true
    }
  }
}
```

**HOW — Start execution:**

```python
import boto3

sfn = boto3.client('stepfunctions')

response = sfn.start_execution(
    stateMachineArn='arn:aws:states:..:stateMachine:order-processing',
    input=json.dumps({
        "order_id": "12345",
        "user_id": "67890",
        "items": [...]
    })
)

execution_arn = response['executionArn']

# Poll status
status = sfn.describe_execution(executionArn=execution_arn)
print(status['status'])    # RUNNING, SUCCEEDED, FAILED
```

**HOW — Human approval workflow:**

```json
{
  "WaitForApproval": {
    "Type": "Task",
    "Resource": "arn:aws:states:::lambda:invoke.waitForTaskToken",
    "Parameters": {
      "FunctionName": "send-approval-request",
      "Payload": {
        "TaskToken.$": "$$.Task.Token",
        "OrderId.$": "$.order_id"
      }
    },
    "Next": "ProcessApproval"
  }
}
```

```python
# Lambda waits for human to approve via API
def send_approval_request(event, context):
    task_token = event['TaskToken']
    order_id = event['OrderId']

    # Send Slack message with approve/reject buttons
    # Buttons call API that resumes execution

    # API endpoint:
    @app.post("/admin/orders/{order_id}/approve")
    async def approve_order(order_id, task_token):
        sfn.send_task_success(
            taskToken=task_token,
            output=json.dumps({"approved": True})
        )
```

---

### Q5: EventBridge — event-driven serverless?

**Answer:**

**WHAT:** Managed event bus for routing events to multiple targets.

**WHY:**
- Decoupling (producers don't know consumers)
- Built-in event filtering
- Multiple targets per event (fan-out)
- Schema registry

**HOW — Setup event bus:**

```yaml
# template.yaml
Resources:
  AppEventBus:
    Type: AWS::Events::EventBus
    Properties:
      Name: app-events


  # Rule: route order.placed events to multiple targets
  OrderPlacedRule:
    Type: AWS::Events::Rule
    Properties:
      EventBusName: !Ref AppEventBus
      EventPattern:
        source: ["order-service"]
        detail-type: ["order.placed"]
      Targets:
        # Send confirmation email
        - Arn: !GetAtt SendEmailFunction.Arn
          Id: SendEmail

        # Update inventory
        - Arn: !GetAtt UpdateInventoryFunction.Arn
          Id: UpdateInventory

        # Push to analytics queue
        - Arn: !GetAtt AnalyticsQueue.Arn
          Id: Analytics

        # Send to SNS for fan-out
        - Arn: !Ref OrderEventTopic
          Id: BroadcastSNS
```

**HOW — Producer publishes event:**

```python
import boto3
import json

events_client = boto3.client('events')

def handler(event, context):
    # Process order
    order_id = create_order(event)

    # Publish event
    response = events_client.put_events(
        Entries=[
            {
                'Source': 'order-service',
                'DetailType': 'order.placed',
                'Detail': json.dumps({
                    'order_id': order_id,
                    'user_id': event['user_id'],
                    'total': event['total'],
                    'timestamp': time.time()
                }),
                'EventBusName': 'app-events'
            }
        ]
    )

    return {"order_id": order_id}
```

**HOW — Consumer (subscribed Lambda):**

```python
def send_email_handler(event, context):
    """Triggered by EventBridge rule."""
    detail = event['detail']
    order_id = detail['order_id']
    user_id = detail['user_id']

    user = get_user(user_id)
    send_email(user.email, f"Order {order_id} confirmed!")

    return {"sent": True}
```

**HOW — Schema Registry:**

```bash
# Auto-discover schemas
aws events create-discoverer --source-arn arn:aws:events:..:event-bus/app-events

# View discovered schemas
aws schemas list-schemas --registry-name discovered-schemas

# Generate code bindings for type safety
aws schemas get-code-binding-source \
  --registry-name discovered-schemas \
  --schema-name order-service@OrderPlaced \
  --language Python36
```

---

### Q6: SQS + Lambda — async processing pattern?

**Answer:**

**WHAT:** SQS queue triggers Lambda function.

**WHY:**
- Decoupling
- Retry built-in
- DLQ for failures
- Batching

**HOW:**

```yaml
# template.yaml
Resources:
  OrderQueue:
    Type: AWS::SQS::Queue
    Properties:
      QueueName: order-processing
      VisibilityTimeout: 300            # 5 min — must be > Lambda timeout
      MessageRetentionPeriod: 1209600   # 14 days max
      RedrivePolicy:
        deadLetterTargetArn: !GetAtt OrderDLQ.Arn
        maxReceiveCount: 3              # Try 3 times, then DLQ

  OrderDLQ:
    Type: AWS::SQS::Queue
    Properties:
      QueueName: order-processing-dlq

  ProcessOrderFunction:
    Type: AWS::Serverless::Function
    Properties:
      Runtime: python3.12
      Handler: app.process_order
      Timeout: 60
      MemorySize: 512
      Events:
        SQSEvent:
          Type: SQS
          Properties:
            Queue: !GetAtt OrderQueue.Arn
            BatchSize: 10                    # ⭐ Process up to 10 per invocation
            MaximumBatchingWindowInSeconds: 5
            FunctionResponseTypes:
              - ReportBatchItemFailures     # ⭐ Partial batch failures
```

**HOW — Handler with partial failure:**

```python
def process_order(event, context):
    """
    Process SQS batch.
    Report individual failures so successful ones aren't reprocessed.
    """
    batch_item_failures = []

    for record in event['Records']:
        try:
            message_body = json.loads(record['body'])

            # Process
            order_id = message_body['order_id']
            process_individual_order(order_id)

        except Exception as e:
            print(f"Failed: {e}")
            # ⭐ Mark this message for retry (others still committed)
            batch_item_failures.append({
                "itemIdentifier": record['messageId']
            })

    return {"batchItemFailures": batch_item_failures}
```

---

### Q7: Serverless monitoring — observability?

**Answer:**

**WHAT:** Lambda doesn't have always-on agents like containers.

**HOW — Built-in CloudWatch:**

```python
import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)

def handler(event, context):
    # All print/logger.info → CloudWatch Logs automatically
    logger.info(f"Processing event: {event}", extra={
        "request_id": context.aws_request_id,
        "function_name": context.function_name,
    })

    # Metrics
    # CloudWatch automatically tracks:
    # - Invocations
    # - Duration
    # - Errors
    # - Throttles

    # Custom metrics
    cloudwatch = boto3.client('cloudwatch')
    cloudwatch.put_metric_data(
        Namespace='MyApp',
        MetricData=[{
            'MetricName': 'OrdersProcessed',
            'Value': 1,
            'Unit': 'Count'
        }]
    )

    return {"status": "ok"}
```

**HOW — X-Ray tracing:**

```python
from aws_xray_sdk.core import xray_recorder
from aws_xray_sdk.core import patch_all

patch_all()    # ⭐ Auto-instrument boto3, requests, etc.

def handler(event, context):
    with xray_recorder.in_subsegment('process_order'):
        # Custom span
        xray_recorder.put_annotation('user_id', event['user_id'])
        result = process_order(event)

    return result
```

**HOW — Structured logging with embedded metrics:**

```python
import json

def handler(event, context):
    # Embedded Metric Format (EMF) — auto-extracts metrics from logs
    log_entry = {
        "_aws": {
            "Timestamp": int(time.time() * 1000),
            "CloudWatchMetrics": [{
                "Namespace": "MyApp",
                "Dimensions": [["Service", "Operation"]],
                "Metrics": [
                    {"Name": "OrderProcessingTime", "Unit": "Milliseconds"},
                    {"Name": "OrderValue", "Unit": "None"}
                ]
            }]
        },
        "Service": "OrderService",
        "Operation": "ProcessOrder",
        "OrderProcessingTime": 123,
        "OrderValue": 99.99,
        "request_id": context.aws_request_id
    }

    print(json.dumps(log_entry))    # CloudWatch extracts metrics
```

---

### Q8: Cost optimization for serverless?

**Answer:**

**HOW — Key optimizations:**

**1. Right-size memory (it scales CPU too)**

```python
# Lambda CPU is proportional to memory
# Sometimes MORE memory = LESS cost (faster execution)

# Tool: aws-lambda-power-tuning
# https://github.com/alexcasalboni/aws-lambda-power-tuning

# Tests function at different memory sizes
# Returns optimal cost/performance
```

**2. Use ARM64 (Graviton)**

```yaml
Architectures: [arm64]    # 20% cheaper than x86_64
```

**3. Reduce duration**

```python
# Reuse connections (module-level)
import boto3
client = boto3.client('dynamodb')    # ⭐ Outside handler

def handler(event, context):
    # Reuses existing client (no init cost)
    ...
```

**4. Smaller packages**

```bash
# Remove dev deps
pip install --target ./package -r requirements.txt --no-dev

# Use Lambda Layers for heavy deps
```

**5. HTTP API over REST API**

```yaml
Events:
  Api:
    Type: HttpApi        # ⭐ ~70% cheaper than REST API
    # NOT Type: Api      # REST API more features but expensive
```

**6. Set sane timeouts**

```yaml
Timeout: 30   # ⭐ Not default 900 (15 min)
# Pay only for actual execution time anyway, but timeout = max wait
```

**7. Use S3 lifecycle for Lambda logs**

```yaml
# CloudWatch Logs are expensive long-term
# Archive to S3 after 30 days
LogGroup:
  Type: AWS::Logs::LogGroup
  Properties:
    LogGroupName: /aws/lambda/my-function
    RetentionInDays: 30    # ⭐ Don't keep forever
```

---

## Serverless Architecture Patterns

```markdown
### Good Patterns
- [ ] API Gateway + Lambda for HTTP endpoints
- [ ] EventBridge for event routing
- [ ] SQS + Lambda for async processing
- [ ] Step Functions for workflows
- [ ] DynamoDB streams → Lambda for CDC
- [ ] S3 events → Lambda for file processing
- [ ] EventBridge Scheduler for cron

### Anti-Patterns
- [ ] Lambda calling Lambda synchronously (use Step Functions)
- [ ] Lambda with > 5 min execution (use Step Functions or ECS)
- [ ] Direct DB connection per invocation (use RDS Proxy)
- [ ] Lambda for high-RPS steady traffic (use ECS)
- [ ] WebSocket with Lambda (use API Gateway WebSocket carefully)
```

---

## Serverless Decision Tree

```
Need HTTP API?
├─ Sporadic traffic? → Lambda + API Gateway HTTP API
├─ Steady high load? → ECS Fargate
└─ WebSocket-heavy? → ECS Fargate

Need background processing?
├─ Triggered by event? → Lambda + SQS/SNS/EventBridge
├─ Scheduled? → Lambda + EventBridge Scheduler
├─ Long workflow? → Step Functions
└─ Constant work? → ECS Fargate

Need file processing?
├─ Upload-triggered? → Lambda + S3 events
└─ Batch processing? → AWS Batch or ECS

Need stream processing?
├─ DynamoDB changes? → Lambda + DynamoDB Streams
├─ Kafka events? → MSK + Lambda OR Kafka Connect
└─ Kinesis? → Lambda + Kinesis triggers
```

---

## Common Pitfalls

| Pitfall | Risk | Fix |
|---|---|---|
| Lambda → Lambda sync calls | Latency stack, errors | Step Functions or async |
| Connection per invocation | Exhausted DB pool | RDS Proxy + connection reuse |
| No DLQ | Lost messages | Always configure DLQ |
| 15-min timeout | Long jobs fail | Step Functions or ECS |
| No cold start mitigation | High p99 latency | Provisioned Concurrency |
| Heavy deps in deployment | Slow cold start | Lambda Layers + tree-shaking |
| Synchronous between functions | Cost + latency | Async via SQS/EventBridge |
| Default memory (128MB) | Slow execution | Right-size with power tuning |
