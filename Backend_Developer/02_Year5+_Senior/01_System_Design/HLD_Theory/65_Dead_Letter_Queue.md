# Dead Letter Queue (DLQ)

---

## What is a DLQ?
A special queue that holds messages that could NOT be processed successfully after N retry attempts.

Instead of losing failed messages or blocking the main queue, they go to the DLQ for inspection and reprocessing.

---

## Why You Need a DLQ

Without DLQ:
```
Main Queue: [msg1] [msg2_BROKEN] [msg3] [msg4]
                        │
                Consumer fails on msg2
                Retries 3 times → still fails
                Consumer stuck or message lost forever
```

With DLQ:
```
Main Queue: [msg1] [msg2_BROKEN] [msg3] [msg4]
                        │
                Consumer fails on msg2
                Retries 3 times → still fails
                msg2 → Dead Letter Queue
                Consumer moves on → processes msg3, msg4
```

---

## How it Works

### Flow
```
Producer ──► Main Queue ──► Consumer
                                │
                          Processing fails
                                │
                    ┌───────────▼───────────┐
                    │     Retry Policy       │
                    │  Attempt 1: wait 1s    │
                    │  Attempt 2: wait 5s    │
                    │  Attempt 3: wait 30s   │
                    │  Max retries reached   │
                    └───────────┬───────────┘
                                │
                    ┌───────────▼───────────┐
                    │   Dead Letter Queue   │
                    │   (msg stored safely) │
                    └───────────────────────┘
                                │
                    ┌───────────▼───────────┐
                    │  Alert + Dashboard    │
                    │  Engineer investigates│
                    │  Fix bug + replay msg │
                    └───────────────────────┘
```

### DLQ Message Metadata
Each DLQ message includes:
- Original message content
- Error reason / exception stack trace
- Number of retry attempts
- Timestamp of each failure
- Original queue name
- Message ID

---

## When Does a Message Go to DLQ?

1. **Max retries exceeded** — processed N times, always fails
2. **Message too old** — exceeded visibility timeout / TTL
3. **Poison message** — malformed JSON, schema mismatch, unexpected format
4. **Consumer bug** — code throws unhandled exception
5. **Dependency down** — DB or downstream service unavailable (though this should be retried)

---

## DLQ Patterns

### 1. Replay after fix
```
Bug found → fix deployed → replay all DLQ messages back to main queue
```

### 2. Manual inspection
```
DLQ consumer → reads messages → engineer reviews → decides: replay or discard
```

### 3. DLQ alerting
```
DLQ depth > 0 → trigger alert → Slack / PagerDuty notification
```

### 4. DLQ consumer (automated)
```
Separate service reads DLQ → tries to transform / fix message → re-enqueue to main queue
```

---

## Retry Strategy (Exponential Backoff)

Don't retry immediately — give downstream time to recover.

```python
attempt 1: wait 1 second
attempt 2: wait 2 seconds
attempt 3: wait 4 seconds
attempt 4: wait 8 seconds
attempt 5: → DLQ

# With jitter (prevent thundering herd)
wait = min(base * 2^attempt + random(0, 1), max_wait)
```

---

## DLQ in AWS SQS

```
Main Queue (SQS)
    └── Dead Letter Queue policy:
        maxReceiveCount: 5         ← after 5 failures → DLQ
        deadLetterTargetArn: arn:aws:sqs:...:my-dlq

DLQ (SQS)
    └── MessageRetentionPeriod: 14 days
    └── Alert: CloudWatch alarm if ApproximateNumberOfMessagesVisible > 0
```

---

## DLQ in Kafka

Kafka doesn't have built-in DLQ, but common patterns:

```
Normal flow:   Producer → Topic: orders → Consumer Group
Failure flow:  Consumer fails → writes to Topic: orders.DLQ
               DLQ consumer → reads → alerts / replays
```

Libraries like **kafka-retry** or **Spring Kafka** handle this automatically.

---

## Real World Usage

| System | DLQ Use |
|--------|---------|
| Payment systems | Failed payment events — must not lose |
| Order processing | Failed order state transitions |
| Email/notification | Failed delivery attempts |
| ETL pipelines | Bad records that fail transformation |
| Webhook delivery | Failed HTTP callbacks to customers |

---

## DLQ vs Retry Queue

| | Retry Queue | DLQ |
|--|-------------|-----|
| Purpose | Temporary retry with backoff | Final resting place for unfixable failures |
| Consumer | Same as main queue | Separate consumer / manual review |
| TTL | Short | Long (days to weeks) |
| Action | Auto retry | Alert + investigate |

---

## Interview Tip
> "Every message queue in our system has a DLQ configured. After 5 failed attempts with exponential backoff, the message moves to DLQ. We have CloudWatch alarms on DLQ depth — any message in DLQ triggers a PagerDuty alert. Engineers investigate, fix the bug, and replay the messages. This guarantees we never silently lose events."
