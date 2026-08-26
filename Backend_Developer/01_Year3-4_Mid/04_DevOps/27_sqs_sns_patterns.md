# SQS + SNS — Queue & Pub/Sub Patterns

## SQS — Simple Queue Service

### Core Model
```
Producer              Queue              Consumer
(Django API) → [msg1, msg2, msg3] → Celery/Lambda worker
```

### Message Lifecycle (Critical)

```
1. Producer sends message → Queue stores it
2. Consumer "receives" message
   → Message becomes INVISIBLE (visibility timeout starts)
3a. Consumer processes successfully → DELETE message → gone forever ✅
3b. Consumer FAILS or times out → visibility timeout expires
   → Message becomes VISIBLE again → another consumer picks it up
```

**Visibility Timeout = at-least-once delivery ka mechanism**

```
visibility_timeout = 30s (default)

Timeline:
0s:  Message received by Worker A
     (message invisible to others for 30s)
10s: Worker A crashes
30s: Visibility timeout expires
     Message reappears in queue
32s: Worker B picks up same message → processes it

→ Message processed TWICE — idempotency REQUIRED
```

**Rule:** visibility_timeout > your longest expected processing time
- Celery task 5 min max → visibility_timeout = 360s (6 min with buffer)

---

## Standard vs FIFO Queue

| | Standard | FIFO |
|---|---|---|
| Throughput | Unlimited (very high) | 300 msg/s (3000 with batching) |
| Delivery | At-least-once (duplicates possible) | Exactly-once |
| Ordering | Best-effort | Strict FIFO |
| Use case | Email, notifications, async tasks | Financial transactions, order processing |
| Cost | Lower | Higher |
| Message dedup | Manual (idempotency key needed) | Built-in (deduplication ID) |

```
FIFO queue name MUST end in .fifo:
  my-orders-queue.fifo
```

---

## Dead Letter Queue (DLQ)

```
SQS Main Queue
    ↓ maxReceiveCount = 3 (if message received 3 times without delete)
SQS Dead Letter Queue

# Every failed message eventually lands here
# DLQ = investigation queue (alarm lagao jab depth > 0)
```

**Setup:**
```python
import boto3

sqs = boto3.client("sqs", region_name="ap-south-1")

# Create DLQ first
dlq = sqs.create_queue(QueueName="my-app-dlq")
dlq_arn = sqs.get_queue_attributes(
    QueueUrl=dlq["QueueUrl"],
    AttributeNames=["QueueArn"]
)["Attributes"]["QueueArn"]

# Main queue with DLQ redrive policy
main_queue = sqs.create_queue(
    QueueName="my-app-queue",
    Attributes={
        "RedrivePolicy": json.dumps({
            "deadLetterTargetArn": dlq_arn,
            "maxReceiveCount": "3",     # 3 attempts → DLQ
        }),
        "VisibilityTimeout": "300",
    }
)
```

---

## Long Polling

```
Short polling (default):
  Consumer → SQS: "any messages?"
  SQS → Consumer: "no" (even if message arrives 1ms later)
  Consumer → SQS: "any messages?"  (immediately again)
  → Lots of empty responses, wasted API calls, cost

Long polling (recommended):
  Consumer → SQS: "any messages? Wait up to 20s"
  SQS: (holds connection)
  (message arrives at 8s)
  SQS → Consumer: "yes, here it is" (at 8s)
  → Fewer API calls, lower cost, faster delivery
```

```python
response = sqs.receive_message(
    QueueUrl=queue_url,
    MaxNumberOfMessages=10,
    WaitTimeSeconds=20,        # long polling ← enable this
    VisibilityTimeout=300,
)
```

---

## Idempotency with SQS

Because at-least-once delivery = duplicates possible:

```python
import hashlib, redis

r = redis.Redis()

def process_message(message: dict) -> None:
    msg_id = message["MessageId"]
    key    = f"sqs_processed:{msg_id}"

    if r.exists(key):
        print(f"Duplicate {msg_id} — skip")
        return

    # Process
    send_email(message["Body"])

    # Mark processed (TTL = visibility_timeout × 2)
    r.setex(key, 600, "1")
```

---

## SQS with Django/Celery

```python
# settings.py — Celery with SQS broker
CELERY_BROKER_URL = "sqs://"   # IAM role handles auth — no keys!
CELERY_BROKER_TRANSPORT_OPTIONS = {
    "region": "ap-south-1",
    "visibility_timeout": 3600,
    "polling_interval": 1,
}

# boto3 based SQS directly
def enqueue_task(payload: dict) -> str:
    response = sqs.send_message(
        QueueUrl=QUEUE_URL,
        MessageBody=json.dumps(payload),
        MessageAttributes={
            "task_type": {
                "StringValue": "email",
                "DataType": "String",
            }
        }
    )
    return response["MessageId"]
```

---

## Message Retention & Other Settings

| Setting | Default | Range | Notes |
|---|---|---|---|
| Visibility timeout | 30s | 0s – 12hr | Set > processing time |
| Message retention | 4 days | 1min – 14 days | How long msg stays |
| Max message size | 256 KB | 1B – 256KB | Larger → S3 + pointer |
| Receive message wait | 0s | 0 – 20s | 20s = long polling |
| Max receive count | (DLQ) | 1 – 1000 | Retry limit |

---

## SNS — Simple Notification Service

### Core Model
```
Publisher → SNS Topic → [subscriptions]

Subscribers can be:
  - SQS Queue
  - Lambda function
  - HTTP/HTTPS endpoint
  - Email
  - SMS
  - Mobile Push
```

### Fan-out Pattern (Most Common Architecture)

```
Order Created Event
         ↓
     SNS Topic
    /    |    \
   ↓     ↓     ↓
SQS-1  SQS-2  SQS-3
  ↓      ↓      ↓
Email  Invoice  Analytics
Worker  Worker  Worker

One event → processed independently by N workers
Each worker at its own pace, failures independent
```

**Why SNS → SQS, not SNS directly to workers?**
- SQS = buffer (worker slow? messages queue up, no loss)
- Retry on failure (DLQ, visibility timeout)
- Decoupling (SNS publish rate ≠ consumer processing rate)

---

## SQS vs SNS — The Comparison

| | SQS | SNS |
|---|---|---|
| Pattern | Queue (pull) | Pub/Sub (push) |
| Consumer | One worker processes one message | All subscribers get every message |
| Delivery | Consumer polls (pull) | SNS pushes to subscribers |
| Persistence | Messages stored until consumed/expired | No persistence (fire and forget) |
| Use case | Async task processing | Event fanout, notifications |
| Retries | Built-in (visibility timeout + DLQ) | Limited (3 retries for HTTP) |
| Ordering | Best-effort (Standard) / FIFO | No ordering guarantee |

```
Use SQS when:   Task queue, one worker processes each job
Use SNS when:   One event → multiple systems need to know
Use SNS→SQS:    One event → multiple independent workers (most reliable)
```

---

## Common Patterns

### Pattern 1: Async Email on Signup
```
POST /signup
  → Create user in DB
  → sqs.send_message({"type": "welcome_email", "user_id": 123})
  → Return 201 (fast response)

Celery Worker:
  → picks up SQS message
  → sends email (3 seconds, doesn't slow down API)
```

### Pattern 2: Order Processing Fan-out
```
POST /orders
  → Create order in DB
  → sns.publish(topic=ORDER_TOPIC, message={"order_id": 456})
  → Return 201

SNS → SQS-email   → Email Worker: "Your order confirmed"
SNS → SQS-invoice → Invoice Worker: generates PDF
SNS → SQS-stock   → Stock Worker: reserve inventory
```

### Pattern 3: Failed Message Investigation
```
Message fails 3 times → DLQ
CloudWatch Alarm: DLQ depth > 0 → PagerDuty alert
Engineer: pull from DLQ → investigate → replay or discard
```

---

## Interview Q&A

**Q: Visibility timeout kya hai? Kyun zaroori hai?**
A: Jab consumer message receive karta hai toh message temporarily invisible ho jaata hai (for visibility_timeout seconds). Agar consumer delete nahi karta (crash, exception) toh timeout expire hone ke baad message wapas visible hota hai aur doosra consumer process karta hai. Yahi at-least-once delivery hai — isliye consumers idempotent hone chahiye.

**Q: SQS vs SNS kab use karte hain?**
A: SQS = ek message ek worker process karta hai (task queue). SNS = ek event sabko jaana chahiye (notifications, fan-out). Real systems mein SNS → multiple SQS queues use karte hain — reliability aur decoupling dono milte hain.

**Q: Failed SQS messages kaise handle karte hain?**
A: DLQ set karo with `maxReceiveCount=3`. 3 failures ke baad message DLQ mein jaata hai. DLQ pe CloudWatch Alarm lagao → depth > 0 pe alert. Failed messages investigate karo, fix karo, replay karo (SQS "start message move task" feature se).

**Q: Standard vs FIFO queue kab choose karo?**
A: Standard: email, notifications, most async tasks — ordering matter nahi, throughput chahiye. FIFO: bank transactions, order processing — ordering matter karta hai aur exactly-once processing chahiye. FIFO throughput limited hai (300/s) aur costly hai.

**Q: Large files (> 256KB) SQS se kaise bhejte hain?**
A: S3 Extended Client Library pattern — file S3 mein upload karo, SQS message mein sirf S3 bucket + key send karo. Consumer S3 se file download karta hai. SQS message sirf pointer hai.
