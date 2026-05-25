"""
============================================================
AWS SQS BROKER FOR CELERY — Practical
============================================================
Working examples:
1. Celery + SQS configuration
2. IAM permissions
3. DLQ setup via boto3 / Terraform
4. Visibility timeout heartbeat extension
5. CloudWatch monitoring
6. Cost optimization
"""


# ============================================================
# 1. CELERY APP CONFIG WITH SQS
# ============================================================
CELERY_SQS_CONFIG = '''
# celeryconfig.py

from celery import Celery

app = Celery("myapp")

app.conf.update(
    # Broker
    broker_url="sqs://",                # use AWS credentials from env/IAM
    broker_transport_options={
        "region": "us-east-1",
        "polling_interval": 1,           # poll every 1s
        "wait_time_seconds": 20,         # SQS long polling (max efficient)
        "visibility_timeout": 3600,      # 1 hour
        "queue_name_prefix": "celery-",
        "predefined_queues": {
            "default": {
                "url": "https://sqs.us-east-1.amazonaws.com/123/celery-default",
            },
            "priority_high": {
                "url": "https://sqs.us-east-1.amazonaws.com/123/celery-priority",
            },
            "heavy": {
                "url": "https://sqs.us-east-1.amazonaws.com/123/celery-heavy",
            },
        },
    },

    # Result backend (NOT SQS)
    result_backend="dynamodb://us-east-1/celery_results",
    # Or
    # result_backend="redis://elasticache:6379/0",

    # Task routing
    task_routes={
        "myapp.emails.*": {"queue": "default"},
        "myapp.payments.*": {"queue": "priority_high"},
        "myapp.video_encoding.*": {"queue": "heavy"},
    },

    # Worker settings
    worker_prefetch_multiplier=1,        # don't grab too many at once
    task_acks_late=True,                  # ack only after task done
    task_reject_on_worker_lost=True,      # requeue if worker crashes
    task_serializer="json",
    accept_content=["json"],
)
'''


# ============================================================
# 2. IAM POLICY (least privilege)
# ============================================================
IAM_POLICY = """
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "sqs:SendMessage",
        "sqs:SendMessageBatch",
        "sqs:ReceiveMessage",
        "sqs:DeleteMessage",
        "sqs:DeleteMessageBatch",
        "sqs:GetQueueAttributes",
        "sqs:GetQueueUrl",
        "sqs:ChangeMessageVisibility",
        "sqs:ChangeMessageVisibilityBatch"
      ],
      "Resource": [
        "arn:aws:sqs:us-east-1:123456789012:celery-*"
      ]
    },
    {
      "Effect": "Allow",
      "Action": [
        "dynamodb:GetItem",
        "dynamodb:PutItem",
        "dynamodb:DeleteItem"
      ],
      "Resource": "arn:aws:dynamodb:us-east-1:123456789012:table/celery_results"
    }
  ]
}
"""


# ============================================================
# 3. TERRAFORM — SQS QUEUES + DLQ
# ============================================================
TERRAFORM_SQS = """
# Dead letter queue (must exist before main queue)
resource "aws_sqs_queue" "celery_default_dlq" {
  name                       = "celery-default-dlq"
  message_retention_seconds  = 1209600   # 14 days
  visibility_timeout_seconds = 30
  tags = {
    Environment = "production"
    Purpose     = "celery-failures"
  }
}

# Main queue with DLQ redrive
resource "aws_sqs_queue" "celery_default" {
  name                       = "celery-default"
  visibility_timeout_seconds = 3600       # 1 hour
  message_retention_seconds  = 345600     # 4 days
  receive_wait_time_seconds  = 20         # long polling
  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.celery_default_dlq.arn
    maxReceiveCount     = 3   # → DLQ after 3 failed attempts
  })
  tags = { Environment = "production" }
}

# Priority queue (separate from default)
resource "aws_sqs_queue" "celery_priority_high" {
  name                       = "celery-priority"
  visibility_timeout_seconds = 600
  receive_wait_time_seconds  = 20
}

# FIFO queue (for ordering-required tasks)
resource "aws_sqs_queue" "celery_orders_fifo" {
  name                        = "celery-orders.fifo"
  fifo_queue                  = true
  content_based_deduplication = true     # auto-dedup based on body hash
  visibility_timeout_seconds  = 1800
}

# CloudWatch alarm — backlog
resource "aws_cloudwatch_metric_alarm" "celery_backlog" {
  alarm_name          = "celery-default-backlog"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "ApproximateNumberOfMessagesVisible"
  namespace           = "AWS/SQS"
  period              = 60
  statistic           = "Average"
  threshold           = 1000
  dimensions = {
    QueueName = aws_sqs_queue.celery_default.name
  }
  alarm_actions = [aws_sns_topic.pagerduty.arn]
}

# DLQ alarm — any message in DLQ is bad
resource "aws_cloudwatch_metric_alarm" "celery_dlq_alarm" {
  alarm_name          = "celery-default-dlq-not-empty"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "ApproximateNumberOfMessagesVisible"
  namespace           = "AWS/SQS"
  period              = 60
  statistic           = "Maximum"
  threshold           = 0
  dimensions = {
    QueueName = aws_sqs_queue.celery_default_dlq.name
  }
  alarm_actions = [aws_sns_topic.pagerduty.arn]
}
"""


# ============================================================
# 4. VISIBILITY TIMEOUT HEARTBEAT (long-running tasks)
# ============================================================
HEARTBEAT_PATTERN = '''
import asyncio
import boto3
from celery import Celery

app = Celery("myapp")
sqs = boto3.client("sqs", region_name="us-east-1")


@app.task(bind=True)
def long_running_task(self, data):
    """Task that takes longer than visibility_timeout — extend it."""
    queue_url = self.request.delivery_info["sqs_queue_url"]
    receipt_handle = self.request.delivery_info["sqs_receipt_handle"]

    # Background heartbeat to extend visibility every 5 min
    stop_heartbeat = threading.Event()

    def heartbeat():
        while not stop_heartbeat.is_set():
            try:
                sqs.change_message_visibility(
                    QueueUrl=queue_url,
                    ReceiptHandle=receipt_handle,
                    VisibilityTimeout=600,    # extend 10 min
                )
            except Exception as e:
                logger.warning(f"Heartbeat failed: {e}")
            stop_heartbeat.wait(300)   # extend every 5 min

    hb_thread = threading.Thread(target=heartbeat, daemon=True)
    hb_thread.start()

    try:
        # Do the long work
        for i in range(100):
            process_chunk(i, data)
        return "done"
    finally:
        stop_heartbeat.set()
        hb_thread.join(timeout=5)
'''


# ============================================================
# 5. DLQ MONITORING + REPROCESSING
# ============================================================
DLQ_REPROCESSING = '''
import boto3
import json

sqs = boto3.client("sqs", region_name="us-east-1")

DLQ_URL = "https://sqs.us-east-1.amazonaws.com/123/celery-default-dlq"
MAIN_QUEUE_URL = "https://sqs.us-east-1.amazonaws.com/123/celery-default"


def drain_dlq_back_to_main(max_messages=100):
    """Move messages from DLQ back to main queue (after fixing the bug)."""
    processed = 0
    while processed < max_messages:
        resp = sqs.receive_message(
            QueueUrl=DLQ_URL,
            MaxNumberOfMessages=10,
            WaitTimeSeconds=2,
        )
        messages = resp.get("Messages", [])
        if not messages:
            break

        for msg in messages:
            # Send to main
            sqs.send_message(
                QueueUrl=MAIN_QUEUE_URL,
                MessageBody=msg["Body"],
                MessageAttributes=msg.get("MessageAttributes", {}),
            )
            # Delete from DLQ
            sqs.delete_message(
                QueueUrl=DLQ_URL,
                ReceiptHandle=msg["ReceiptHandle"],
            )
            processed += 1
    return processed


def inspect_dlq(limit=10):
    """Look at DLQ messages without deleting them."""
    resp = sqs.receive_message(
        QueueUrl=DLQ_URL,
        MaxNumberOfMessages=min(limit, 10),
        VisibilityTimeout=0,    # don't hide
        AttributeNames=["All"],
        MessageAttributeNames=["All"],
    )
    for msg in resp.get("Messages", []):
        body = json.loads(msg["Body"])
        print(f"Task: {body.get('task')} | Args: {body.get('args')}")
        print(f"  Receive count: {msg['Attributes'].get('ApproximateReceiveCount')}")
        print(f"  Body: {msg['Body'][:200]}")
'''


# ============================================================
# 6. CHECKING CANCELLATION FLAG (since SQS doesn't support revoke)
# ============================================================
CANCELLATION_PATTERN = '''
import redis

r = redis.Redis()

def is_cancelled(task_id: str) -> bool:
    return bool(r.get(f"cancel:{task_id}"))

def cancel_task(task_id: str):
    """Mark task as cancelled (worker checks this flag)."""
    r.set(f"cancel:{task_id}", "1", ex=3600)


@app.task(bind=True)
def cancellable_task(self, data):
    """Worker periodically checks if cancelled.
    Required since SQS has no revoke support."""
    for i in range(100):
        if is_cancelled(self.request.id):
            logger.info(f"Task {self.request.id} cancelled at step {i}")
            return {"status": "cancelled", "completed": i}
        process_step(i, data)
    return {"status": "completed"}


# To cancel from API
@app.post("/api/tasks/{task_id}/cancel")
async def cancel_endpoint(task_id: str):
    cancel_task(task_id)
    return {"cancelled": task_id}
'''


# ============================================================
# 7. COST OPTIMIZATION
# ============================================================
COST_OPTIMIZATION = '''
# 1. LONG POLLING (most important — fewer API calls!)
broker_transport_options = {
    "wait_time_seconds": 20,    # max long poll
}

# 2. BATCH SEND/RECEIVE (10 messages per call)
group_tasks = group(my_task.s(i) for i in range(100))
group_tasks.apply_async()    # uses send_message_batch internally

# 3. APPROPRIATE POLLING INTERVAL
broker_transport_options = {
    "polling_interval": 5,    # don't poll too often when idle
}

# 4. MULTIPLE MESSAGES PER POLL
broker_transport_options = {
    "max_messages_per_receive": 10,    # max 10 per receive_message call
}

# 5. AUTOSCALE WORKERS DOWN WHEN IDLE
# Use KEDA — see 04_flower_prometheus_monitoring.py

# 6. RESERVED CAPACITY for predictable workload
# (not yet available for SQS, but watch for it)

# COST ESTIMATE:
# 100K tasks/day × 30 days = 3M messages
# 10 workers polling every 20s long-poll = ~1.3M polls/month
# Total: ~4.3M requests × $0.40/M = ~$1.72/month
# vs RabbitMQ EC2: ~$40/month minimum
'''


# ============================================================
# 8. CLOUDWATCH MONITORING
# ============================================================
CLOUDWATCH_DASHBOARD = """
# CloudWatch dashboard JSON

{
  "widgets": [
    {
      "type": "metric",
      "properties": {
        "title": "Queue Backlogs",
        "metrics": [
          ["AWS/SQS", "ApproximateNumberOfMessagesVisible", "QueueName", "celery-default"],
          [".", ".", ".", "celery-priority"],
          [".", ".", ".", "celery-heavy"]
        ]
      }
    },
    {
      "type": "metric",
      "properties": {
        "title": "Oldest Message Age",
        "metrics": [
          ["AWS/SQS", "ApproximateAgeOfOldestMessage", "QueueName", "celery-default"]
        ]
      }
    },
    {
      "type": "metric",
      "properties": {
        "title": "Messages Sent/Received/Deleted",
        "metrics": [
          ["AWS/SQS", "NumberOfMessagesSent", "QueueName", "celery-default"],
          [".", "NumberOfMessagesReceived", ".", "."],
          [".", "NumberOfMessagesDeleted", ".", "."]
        ]
      }
    },
    {
      "type": "metric",
      "properties": {
        "title": "DLQ Messages (should be 0)",
        "metrics": [
          ["AWS/SQS", "ApproximateNumberOfMessagesVisible", "QueueName", "celery-default-dlq"]
        ]
      }
    }
  ]
}
"""


# ============================================================
# 9. PROS/CONS SUMMARY
# ============================================================
TRADEOFFS = """
================================================================
SQS as Celery broker — Trade-offs
================================================================

✅ PROS:
- Zero ops (fully managed by AWS)
- Built-in HA (multi-AZ replication)
- Cheap at low-medium volume
- Built-in DLQ
- IAM integration (no broker creds)
- Long polling = efficient
- Unlimited storage

❌ CONS:
- No remote control (no revoke)
- No real-time events (Flower limited)
- No in-queue priority (use multiple queues)
- 12h visibility timeout maximum
- Less expressive routing (no exchange topology)
- Vendor lock-in (AWS)

WHEN TO USE:
- Cloud-native AWS deployments
- Low-medium message volume
- Want zero broker ops
- DLQ + retry pattern is enough

WHEN NOT:
- Need complex routing (RabbitMQ exchanges)
- Need in-process broker visibility
- Strict ordering across whole queue (not just per-group)
- Multi-cloud / on-premises
================================================================
"""


# ============================================================
# MAIN
# ============================================================
if __name__ == "__main__":
    print("=" * 60)
    print("CELERY + AWS SQS — Production Setup")
    print("=" * 60)

    print("\n--- 1. CELERY CONFIG ---")
    print(CELERY_SQS_CONFIG)

    print("\n--- 2. IAM POLICY ---")
    print(IAM_POLICY)

    print("\n--- 3. TERRAFORM (SQS + DLQ + CloudWatch) ---")
    print(TERRAFORM_SQS)

    print("\n--- 4. HEARTBEAT FOR LONG TASKS ---")
    print(HEARTBEAT_PATTERN)

    print("\n--- 5. DLQ MANAGEMENT ---")
    print(DLQ_REPROCESSING)

    print("\n--- 6. CANCELLATION (no SQS revoke) ---")
    print(CANCELLATION_PATTERN)

    print("\n--- 7. COST OPTIMIZATION ---")
    print(COST_OPTIMIZATION)

    print("\n--- 8. CLOUDWATCH DASHBOARD ---")
    print(CLOUDWATCH_DASHBOARD)

    print(TRADEOFFS)
