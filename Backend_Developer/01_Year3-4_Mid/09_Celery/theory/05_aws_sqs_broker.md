# AWS SQS as Celery Broker

> **Interview angle:** "Self-hosted RabbitMQ ops headache. Cloud-native, fully-managed broker chahiye. SQS sahi hai?"

---

## 1. Why Consider SQS?

| Aspect | RabbitMQ | Redis | **SQS** |
|---|---|---|---|
| Ops burden | High | Medium | **Zero (managed)** |
| HA | Manual setup | Sentinel | **Built-in** |
| Cost | Server cost | Server cost | Pay per message |
| Throughput | 50K+/sec | 100K+/sec | Unlimited (FIFO: 3K/sec) |
| Persistence | ✅ | Optional | ✅ (built-in) |
| Long polling | ❌ | ❌ | ✅ |
| Region replication | Manual | Manual | Cross-region built-in |
| Cost (1M msg/month) | $50-100 server | $20-50 | ~$0.40 |

**Trade-off:** SQS = simplest ops, but limited Celery features.

---

## 2. SQS Limitations with Celery

### What WORKS
- Basic task queue (apply_async, delay)
- Multiple queues
- Visibility timeout (retry on failure)
- Dead-letter queues (DLQ)
- Long polling (efficient)

### What DOESN'T work
- **No remote control** (can't `revoke` a task in flight)
- **No events** (Flower can't show real-time state via SQS)
- **No priority queues** within single queue (use separate queues)
- **No broadcast** to all workers (need SNS)
- **No transactions** (chains/chords need separate orchestration)
- **Visibility timeout limit:** 12 hours max

---

## 3. Two SQS Queue Types

### Standard SQS
- At-least-once delivery (duplicates possible)
- Best-effort ordering (not strict FIFO)
- Unlimited throughput
- **Use for:** general task queues

### FIFO SQS
- Exactly-once processing (via dedup ID)
- Strict ordering per message group
- **Throughput limit:** 3,000 TPS (with high throughput mode)
- More expensive
- **Use for:** order processing, financial txns

---

## 4. Setup Celery with SQS

```bash
pip install celery[sqs]
# Or
pip install celery boto3 pycurl
```

```python
# celeryconfig.py
broker_url = "sqs://"   # uses AWS credentials from env/IAM

broker_transport_options = {
    "region": "us-east-1",
    "predefined_queues": {
        "default": {
            "url": "https://sqs.us-east-1.amazonaws.com/123456789/celery-default",
            "access_key_id": "...",   # or use IAM role
            "secret_access_key": "...",
        },
        "priority_high": {
            "url": "https://sqs.us-east-1.amazonaws.com/123456789/celery-priority",
        },
    },
    "polling_interval": 1,         # seconds between polls
    "wait_time_seconds": 20,       # long polling — efficient!
    "visibility_timeout": 3600,    # 1 hour
    "queue_name_prefix": "celery-",
}

# Result backend — NOT SQS (SQS isn't for results)
result_backend = "dynamodb://us-east-1/celery_results"
# Or
result_backend = "redis://elasticache:6379/0"
```

### IAM permissions
```json
{
    "Version": "2012-10-17",
    "Statement": [{
        "Effect": "Allow",
        "Action": [
            "sqs:SendMessage",
            "sqs:ReceiveMessage",
            "sqs:DeleteMessage",
            "sqs:GetQueueAttributes",
            "sqs:ChangeMessageVisibility"
        ],
        "Resource": "arn:aws:sqs:us-east-1:*:celery-*"
    }]
}
```

---

## 5. Visibility Timeout — Critical Setting

When a worker takes a message:
- Message becomes "invisible" to others for `visibility_timeout` seconds
- If worker completes + deletes → done
- If worker crashes before deleting → message reappears after timeout → retried

### Sizing
- **Visibility timeout = (1.5 × max_task_duration)**
- Too short → task running gets reprocessed → duplicate work
- Too long → crashes cause long delay before retry

### Default 30s is dangerous for slow tasks!

```python
broker_transport_options = {
    "visibility_timeout": 3600,    # 1 hour for slow tasks
}
```

### Heartbeat extension for very long tasks
```python
import boto3
sqs = boto3.client("sqs")

@app.task(bind=True)
def long_task(self):
    receipt_handle = self.request.delivery_info["sqs_message_id"]
    queue_url = "..."

    # Extend visibility every 5 min
    async def heartbeat():
        while still_working:
            sqs.change_message_visibility(
                QueueUrl=queue_url,
                ReceiptHandle=receipt_handle,
                VisibilityTimeout=600,
            )
            await asyncio.sleep(300)
```

---

## 6. Dead-Letter Queue (DLQ)

If a message fails N times, send to DLQ for inspection.

### Create DLQ in AWS Console / Terraform
```hcl
resource "aws_sqs_queue" "celery_dlq" {
  name = "celery-default-dlq"
}

resource "aws_sqs_queue" "celery_default" {
  name = "celery-default"
  visibility_timeout_seconds = 3600
  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.celery_dlq.arn
    maxReceiveCount     = 3       # → DLQ after 3 failures
  })
}
```

### Monitor DLQ
- Set alert on `ApproximateNumberOfMessages > 0` in DLQ
- Manually inspect failed messages
- Reprocess after fix (drain DLQ back to main queue)

---

## 7. Cost Considerations

### AWS SQS pricing
- **First 1M requests/month: FREE**
- After: $0.40 per million requests
- Long polling counts as 1 request per poll (efficient!)
- Standard vs FIFO: FIFO ~3x more expensive

### Reduce request count
```python
broker_transport_options = {
    "polling_interval": 5,        # higher = fewer polls = cheaper
    "wait_time_seconds": 20,      # max long-poll wait
    # Receive multiple messages per poll
    "max_messages_per_receive": 10,
}
```

### Cost example
- 100K tasks/day × 30 days = 3M messages
- Polling: 24h × 60min × 60sec / 20s long-poll = 4,320 polls/worker/day
- 10 workers × 30 days = 1.3M polls
- Total: ~4.3M requests × $0.40/M = **$1.72/month**

vs running RabbitMQ on EC2 = $40/month minimum.

---

## 8. SQS-Specific Patterns

### Batch send
```python
# Single API call to enqueue 10 tasks (saves $$)
group = group(my_task.s(i) for i in range(10))
group.apply_async()    # uses sqs.send_message_batch under hood
```

### Long polling = efficient
```python
# Each worker idle? Long polls SQS for up to 20s waiting for message
broker_transport_options = {"wait_time_seconds": 20}
# 1 request per 20s idle vs 1 per polling_interval
```

### Multi-queue routing
```python
task_routes = {
    "myapp.emails.*": {"queue": "emails"},
    "myapp.heavy.*": {"queue": "heavy"},
    "myapp.priority.*": {"queue": "priority_high"},
}
```

### Per-queue workers
```bash
# Worker only processes "emails" queue
celery -A myapp worker -Q emails

# Worker for heavy tasks (fewer concurrency)
celery -A myapp worker -Q heavy -c 4
```

---

## 9. SQS + Lambda Pattern (Serverless Alternative)

You don't NEED Celery if using AWS:
```
SQS → triggers Lambda function → processes message
```
- Zero workers to manage
- Auto-scales to traffic
- Pay per execution
- Not Python-only

But: Celery + SQS still useful for complex workflows, retries, chains.

---

## 10. Migration Path: RabbitMQ → SQS

### Phase 1: Add SQS as second broker
```python
# Keep RabbitMQ as primary, add SQS for new tasks
broker_url = "amqp://broker"  # primary

task_routes = {
    "myapp.new_tasks.*": {
        "queue": "new_queue_sqs",
        "exchange": "...",
    },
}
```

### Phase 2: Migrate tasks gradually
- Move task by task
- Monitor success rate
- Update routing

### Phase 3: Cutover
- All tasks routed to SQS
- Stop RabbitMQ
- Delete RabbitMQ servers

### Watch out for
- **No Flower visibility** for SQS — switch to CloudWatch + Prometheus
- **No revoke** — tasks must check cancellation flag
- **Result backend** — use DynamoDB or Redis (NOT SQS)
- **Retry behavior** subtle differences

---

## 11. SQS vs Other Cloud Options

| Service | Pros | Cons |
|---|---|---|
| **AWS SQS** | Simple, cheap, reliable | Limited Celery features |
| **AWS SNS+SQS** | Pub/sub + queue | More complex |
| **GCP Pub/Sub** | Multi-region, ordering | More expensive |
| **Azure Service Bus** | Sessions, dead letters | Azure lock-in |
| **CloudAMQP** | RabbitMQ-as-a-service | Costlier than SQS |

---

## 12. Monitoring SQS

### CloudWatch metrics
- `ApproximateNumberOfMessagesVisible` — current backlog
- `ApproximateNumberOfMessagesNotVisible` — in flight
- `NumberOfMessagesSent`, `NumberOfMessagesDeleted`
- `ApproximateAgeOfOldestMessage` — alert if > X seconds

### Alerts
```yaml
# CloudWatch alarm
ComparisonOperator: GreaterThanThreshold
EvaluationPeriods: 2
MetricName: ApproximateAgeOfOldestMessage
Threshold: 300   # 5 minutes
```

---

## 13. Interview Questions

**Q1: SQS Celery broker as kab use karte?**
Cloud-native AWS deployment + don't want broker ops. Simpler than self-hosted RabbitMQ.

**Q2: SQS limitations Celery ke saath?**
No remote control (revoke), no events (Flower limited), no priority within queue (use separate queues), visibility timeout 12h max.

**Q3: Standard vs FIFO SQS?**
Standard = at-least-once, unlimited throughput. FIFO = exactly-once, ordering, 3K TPS limit.

**Q4: Visibility timeout kya?**
Time before message reappears if not deleted. Must be > task duration to avoid duplicates.

**Q5: DLQ setup?**
SQS native — redrive_policy: maxReceiveCount=3, deadLetterTargetArn=DLQ ARN.

**Q6: SQS vs RabbitMQ cost?**
SQS pay-per-message often cheaper than running RabbitMQ on EC2 (especially low volume).

**Q7: Result backend for SQS-based Celery?**
NOT SQS. Use DynamoDB or Redis. SQS isn't for results.

---

## 14. Best Practices

1. **Visibility timeout = 1.5× max task duration**
2. **Long polling (wait_time_seconds=20)** for efficiency
3. **DLQ always** — maxReceiveCount=3
4. **Separate queues** for priority (no in-queue priority)
5. **CloudWatch alerts** on backlog + DLQ
6. **DynamoDB result backend** (or Redis)
7. **IAM role** instead of access keys
8. **Batch send/receive** to reduce costs
9. **Don't use SQS for chains/chords** — orchestrate in app
10. **Test failover** — simulate AWS region outage

---

## Related
- [[01_celery_basics]]
- [[02_celery_advanced]]
- [[06_celery_priority_queues]]
- [[07_celery_task_routing]]
- [[../../01_Year3-4_Mid/04_DevOps/04_aws_ec2_s3_rds]]
