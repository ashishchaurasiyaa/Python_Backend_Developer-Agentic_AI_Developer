# Cloud (AWS) — Monitoring, Messaging & Secrets: CloudWatch, CloudTrail, SNS/SQS, Secrets Manager
**DevOps Track · Phase 7: Cloud (AWS)**

## Quick Concepts

- **CloudWatch** = AWS's metrics, logs, alarms, and dashboards service — "what is my system doing"
- **CloudTrail** = AWS's API call audit log — "who did what, when, from where"
- **Metric** = a time-series numeric datapoint (CPUUtilization, RequestCount, custom app metrics)
- **Alarm** = a rule that watches a metric and fires an action when a threshold is breached
- **SNS** = Simple Notification Service — pub/sub messaging, pushes to many subscribers at once
- **SQS** = Simple Queue Service — a durable message queue, one consumer processes each message
- **Fanout** = one SNS topic pushing the same message to multiple SQS queues/subscribers
- **Secrets Manager** = stores secrets (DB passwords, API keys) with automatic rotation support
- **Parameter Store** = part of Systems Manager, stores config/secrets, no built-in rotation, cheaper

---

## CloudWatch vs CloudTrail — The Distinction Interviewers Check For

```
CloudWatch answers: "IS MY SYSTEM HEALTHY?"
  - CPU at 95%? Memory leaking? Error rate spiking? Disk filling up?
  - Operational, performance-focused, real-time-ish

CloudTrail answers: "WHO DID WHAT?"
  - Who deleted that S3 bucket? Who changed this security group at 2am?
  - Security/audit-focused, records every API call made against your account

They are not interchangeable and not redundant — a production incident
review typically needs BOTH: CloudWatch to see the symptom (error rate
spiked at 14:32), CloudTrail to find the cause (an IAM policy was
changed at 14:30 by user X, right before the spike).
```

### CloudWatch — Metrics, Alarms, Logs, Dashboards

#### Metrics

```
Namespace   → grouping, e.g. AWS/EC2, AWS/RDS, or a custom namespace like MyApp/Orders
Dimension   → a way to filter/slice a metric, e.g. InstanceId, AutoScalingGroupName
Resolution  → Standard (1-minute) or High-Resolution (down to 1-second, custom metrics only)
```

```bash
# Publish a custom application metric
aws cloudwatch put-metric-data \
  --namespace "MyApp/Orders" \
  --metric-name OrdersProcessed \
  --value 1 \
  --unit Count \
  --dimensions Environment=production
```

```python
import boto3
cloudwatch = boto3.client("cloudwatch")

def emit_order_processed():
    cloudwatch.put_metric_data(
        Namespace="MyApp/Orders",
        MetricData=[{
            "MetricName": "OrdersProcessed",
            "Value": 1,
            "Unit": "Count",
            "Dimensions": [{"Name": "Environment", "Value": "production"}],
        }],
    )
```

#### Alarms

```bash
aws cloudwatch put-metric-alarm \
  --alarm-name high-cpu-orders-asg \
  --namespace AWS/EC2 \
  --metric-name CPUUtilization \
  --dimensions Name=AutoScalingGroupName,Value=orders-api-asg \
  --statistic Average \
  --period 300 \
  --evaluation-periods 2 \
  --threshold 80 \
  --comparison-operator GreaterThanThreshold \
  --alarm-actions arn:aws:sns:ap-south-1:123456789012:ops-alerts
```

```
period 300, evaluation-periods 2
  → checks the 5-minute average, and only fires after 2 CONSECUTIVE
    periods breach the threshold (10 minutes sustained, not one blip) —
    this is how you avoid alert fatigue from single spiky datapoints

alarm-actions → an SNS topic, which can fan out to email, Slack (via
    Lambda/webhook subscriber), PagerDuty, or trigger an Auto Scaling
    action directly
```

#### Logs

```
Log Group   → a named collection of log streams, usually one per app/service
              (e.g. /ecs/orders-api, /aws/lambda/my-function)
Log Stream  → a sequence of log events from one source (one task, one instance)
Metric Filter → extracts a numeric metric FROM log lines matching a pattern
              (e.g. count occurrences of "ERROR" per minute, turn that into
              an alarmable CloudWatch metric)
```

```bash
aws logs put-metric-filter \
  --log-group-name /ecs/orders-api \
  --filter-name error-count \
  --filter-pattern "ERROR" \
  --metric-transformations \
      metricName=OrdersApiErrorCount,metricNamespace=MyApp/Orders,metricValue=1
```

This is how unstructured log text ("plain log lines with 'ERROR' in them") becomes something you can alarm on — the metric filter bridges logs and metrics, avoiding the anti-pattern of someone manually watching a log tail for errors.

#### Dashboards

A CloudWatch Dashboard is a saved, shareable JSON-defined layout of widgets (graphs, alarms, log queries) — the standard artifact you point an on-call engineer at during an incident instead of them hunting through the console from scratch.

### CloudTrail — API Audit Logging

```
Every API call made in the account — via console, CLI, SDK, or another
AWS service acting on your behalf — is recorded as an EVENT:

  Who        → IAM user/role ARN, or "AWS service" for service-linked calls
  What       → the API action (e.g. ec2:TerminateInstances, iam:CreatePolicy)
  When       → timestamp
  From where → source IP address
  Result     → success or the specific error/denial reason
```

```bash
aws cloudtrail lookup-events \
  --lookup-attributes AttributeKey=EventName,AttributeValue=TerminateInstances \
  --max-results 10
```

```
Management events   → control-plane operations (create/delete/modify
                       resources) — logged by default, free for the last
                       90 days via Event History
Data events          → high-volume operations on data itself (S3 GetObject,
                       Lambda Invoke) — NOT logged by default, must opt in,
                       higher cost due to volume

For long-term retention/analysis beyond 90 days, or for compliance
requirements, CloudTrail is configured to deliver logs continuously to
an S3 bucket (and often analyzed via Athena or forwarded to a SIEM).
```

**A classic incident-response question**: "a security group was opened to `0.0.0.0/0` on port 22 — how do you find out who did it?" Answer: CloudTrail, filtered on `EventName=AuthorizeSecurityGroupIngress`, cross-referenced with the timestamp the change was noticed.

---

## SNS vs SQS — Pub/Sub vs Queue

| | SNS | SQS |
|---|---|---|
| Pattern | Publish/Subscribe (fanout) | Point-to-point queue |
| Delivery | Pushed to ALL current subscribers | Pulled by ONE consumer per message (competing consumers) |
| Message retention | Not retained — if no subscriber is listening, message is lost (unless subscriber is itself a durable queue) | Retained up to 14 days, survives consumer downtime |
| Ordering | Standard: no guarantee. FIFO topics: ordered | Standard queue: best-effort, may duplicate/reorder. FIFO queue: strict order, exactly-once processing |
| Typical use | Notify multiple, independent systems of an event | Decouple a producer from a slower/unreliable consumer, buffer work |
| Protocols supported | HTTP/S, email, SMS, Lambda, SQS, mobile push | Consumed via API/SDK polling only |

### Standard vs FIFO Queues (SQS)

```
Standard Queue
  - At-least-once delivery (a message MIGHT be delivered more than once
    — your consumer must be idempotent)
  - Best-effort ordering (usually close to order, not guaranteed)
  - Nearly unlimited throughput

FIFO Queue (suffix ".fifo" required on the queue name)
  - Exactly-once processing within a 5-minute deduplication window
  - Strict ordering, but ONLY within a MessageGroupId
  - Throughput capped (300 msg/sec without batching, 3000 with batching)
```

**Interview-relevant**: "process payment events in the exact order they occurred, per customer, and never process the same payment twice" → FIFO queue, `MessageGroupId = customer_id` (so ordering is guaranteed per-customer while different customers' messages can still process in parallel across group IDs).

### Worked Example — SNS Fanning Out to Multiple SQS Queues

A common real architecture: one event ("order placed") needs to trigger several independent, unrelated downstream actions — send a confirmation email, update inventory, log to an analytics pipeline. Instead of the order service calling three different systems directly (tight coupling, and if one is slow/down it blocks the others), it publishes once to SNS:

```
                              ┌──> SQS: email-queue        ──> Email Lambda
Order Service ──> SNS Topic ─┼──> SQS: inventory-queue     ──> Inventory Service
   (publishes                └──> SQS: analytics-queue     ──> Analytics pipeline
    "OrderPlaced" once)
```

```bash
# 1. Create the topic
aws sns create-topic --name order-events

# 2. Create each queue
aws sqs create-queue --queue-name email-queue
aws sqs create-queue --queue-name inventory-queue
aws sqs create-queue --queue-name analytics-queue

# 3. Subscribe each queue to the topic
aws sns subscribe \
  --topic-arn arn:aws:sns:ap-south-1:123456789012:order-events \
  --protocol sqs \
  --notification-endpoint arn:aws:sqs:ap-south-1:123456789012:email-queue

# (repeat subscribe for inventory-queue, analytics-queue)

# 4. Each SQS queue needs a policy allowing SNS to send to it
aws sqs set-queue-attributes \
  --queue-url https://sqs.ap-south-1.amazonaws.com/123456789012/email-queue \
  --attributes '{
    "Policy": "{\"Version\":\"2012-10-17\",\"Statement\":[{\"Effect\":\"Allow\",\"Principal\":{\"Service\":\"sns.amazonaws.com\"},\"Action\":\"sqs:SendMessage\",\"Resource\":\"arn:aws:sqs:ap-south-1:123456789012:email-queue\",\"Condition\":{\"ArnEquals\":{\"aws:SourceArn\":\"arn:aws:sns:ap-south-1:123456789012:order-events\"}}}]}"
  }'
```

```python
import boto3, json

sns = boto3.client("sns")

def publish_order_placed(order_id: str, customer_email: str):
    sns.publish(
        TopicArn="arn:aws:sns:ap-south-1:123456789012:order-events",
        Message=json.dumps({"order_id": order_id, "email": customer_email}),
        MessageAttributes={
            "event_type": {"DataType": "String", "StringValue": "OrderPlaced"}
        },
    )
```

Why this beats direct service-to-service calls: the order service doesn't know or care how many downstream consumers exist. Adding a fourth consumer (say, a fraud-detection queue) later is a subscribe call — zero changes to the order service. Each queue also buffers independently, so a slow analytics pipeline doesn't back-pressure the email flow.

---

## Secrets Manager vs Parameter Store

| | Secrets Manager | Systems Manager Parameter Store |
|---|---|---|
| Cost | ~$0.40/secret/month + API call charges | Standard tier: free. Advanced tier: small monthly charge |
| Automatic rotation | Built-in, native integration for RDS/Redshift/DocumentDB, custom Lambda rotation for anything else | No built-in rotation — you'd script it yourself |
| Max value size | 64 KB | Standard: 4 KB. Advanced: 8 KB |
| Cross-account access | Native resource policies | Supported but less commonly used this way |
| Versioning | Yes, with staging labels (AWSCURRENT, AWSPREVIOUS) | Yes, simple version history |
| Typical use | Database credentials, API keys needing rotation, anything security-sensitive with a rotation requirement | App config values, feature flags, non-rotating secrets, cost-sensitive high-volume lookups |

**The decision in practice**: if it's a credential that should rotate (database password, third-party API key with a rotation policy) → Secrets Manager. If it's a config value or a secret that genuinely doesn't need automatic rotation and you're optimizing cost at scale (hundreds of parameters, e.g. per-microservice config) → Parameter Store. Many real production setups use both side by side, not one exclusively — this "it depends, use both where each fits" answer is what distinguishes a design conversation from a memorized fact.

```python
import boto3, json

def get_db_credentials(secret_name: str) -> dict:
    client = boto3.client("secretsmanager")
    resp = client.get_secret_value(SecretId=secret_name)
    return json.loads(resp["SecretString"])

def get_config_param(param_name: str) -> str:
    client = boto3.client("ssm")
    resp = client.get_parameter(Name=param_name, WithDecryption=True)
    return resp["Parameter"]["Value"]
```

---

## Senior Tip

```
When you describe an incident-response story in an interview, naming
BOTH CloudWatch and CloudTrail signals real production experience:

  "We saw the alarm fire in CloudWatch — error rate crossed 5% for two
   consecutive periods — and traced the root cause through CloudTrail,
   which showed a security group rule had been modified nine minutes
   earlier by a CI/CD role that shouldn't have had that permission.
   We tightened the role's policy and added a CloudWatch alarm on that
   specific CloudTrail event going forward."

That's monitoring (CloudWatch) + audit (CloudTrail) + a security fix
(IAM least privilege) + a durable improvement (alarm on the audit event
itself) — a complete incident response narrative, not just "we looked
at the logs."
```

## Interview Angle

**Q: Messages are piling up in an SQS queue faster than they're processed. What are your options, and how do you decide?**

Check whether the bottleneck is the consumer or the queue design first (`ApproximateNumberOfMessagesVisible` trending up in CloudWatch confirms it's a real backlog, not a blip). Then: scale consumers horizontally (more Lambda concurrency, or more ECS tasks polling — SQS supports many parallel consumers by design for Standard queues), increase the batch size per poll to reduce per-call overhead, or, if the queue is FIFO and messages share one `MessageGroupId`, recognize that ordering constraint is capping throughput to a single consumer for that group — splitting into more group IDs (if the business logic allows) is often the actual fix, not just "add more workers."

---

## Related

- [04_containers_ecs_eks.md](04_containers_ecs_eks.md) — `awslogs` driver piping ECS task logs into CloudWatch
- [02_storage_database.md](02_storage_database.md) — Secrets Manager for RDS master password rotation
- [../11_Monitoring/](../11_Monitoring/) and [../12_Logging/](../12_Logging/) — broader monitoring/logging stack beyond AWS-native tooling
- [../16_Messaging_Systems/](../16_Messaging_Systems/) — messaging patterns beyond SNS/SQS (Kafka, RabbitMQ)
