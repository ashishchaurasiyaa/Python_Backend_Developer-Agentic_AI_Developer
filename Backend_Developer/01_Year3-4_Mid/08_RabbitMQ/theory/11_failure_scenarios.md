# RabbitMQ — Production Failure Scenarios

## 1. RabbitMQ Goes Down

### What happens

```
Producers (.publish()):
  → pika.exceptions.AMQPConnectionError
  → If using connect_robust() → auto-reconnect (blocks until broker back)
  → If using connect()        → crash (must restart manually)

Consumers:
  → Connection drops → consumer process exits or reconnects
  → In-flight messages (unacked) → requeued by broker when connection closes
  → Durable queues + persistent messages → survive broker restart

Timeline:
  T=0  Broker crashes (OOM / process killed)
  T=Xs Broker restarts, loads durable queues from disk
  T=Ys connect_robust() clients reconnect automatically
  T=Zs Processing resumes
```

### Fix: connect_robust() always in production

```python
import aio_pika

# ❌ WRONG — one network blip crashes the consumer
connection = await aio_pika.connect("amqp://guest:guest@localhost/")

# ✅ CORRECT — auto-reconnect with exponential backoff
connection = await aio_pika.connect_robust(
    "amqp://guest:guest@localhost/",
    reconnect_interval=5,
    fail_fast=False,
)
```

### What gets LOST if broker was not configured for durability

```
Lost:                              Survives:
Non-durable queues     ←→    Durable queues (durable=True)
Non-persistent messages ←→   Persistent messages (delivery_mode=2)
Unconfirmed publishes  ←→    Publisher confirms + retry on NACK
```

---

## 2. Consumer Crashes Mid-Processing

```
Timeline:
  T=0  Consumer receives message (broker marks as unacked)
  T=5s Consumer processes payment... crashes
  T=5s Broker detects closed connection → requeues message
  T=6s Another consumer picks up the message → processes again

Risk: DOUBLE PROCESSING (at-least-once delivery)
Fix:  IDEMPOTENT consumers
```

```python
# Consumer with manual ACK — correct pattern
def on_message(ch, method, properties, body):
    try:
        process(body)                           # do the work
        ch.basic_ack(delivery_tag=method.delivery_tag)   # success
    except TransientError as e:
        # Retry: requeue=True → message goes back to queue
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)
    except PermanentError as e:
        # Drop: requeue=False → goes to DLX (if configured) or discarded
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)

channel.basic_qos(prefetch_count=1)
channel.basic_consume(queue="tasks", on_message_callback=on_message)
```

---

## 3. Poison Message (Consumer Keeps Failing)

```
Scenario:
  Message: {"order_id": "INVALID_UUID_FORMAT"}
  Consumer: tries to parse → ValueError → NACK + requeue
  → Immediately redelivered → same error → NACK + requeue
  → Loop: millions of failed deliveries, logs flooded
```

### Fix 1: Max retry count via x-death header

```python
MAX_RETRIES = 3

def on_message(ch, method, properties, body):
    # x-death header added by RabbitMQ each time message is dead-lettered
    x_death = (properties.headers or {}).get("x-death", [])
    retry_count = sum(d.get("count", 0) for d in x_death)

    try:
        process(body)
        ch.basic_ack(delivery_tag=method.delivery_tag)
    except Exception as e:
        if retry_count >= MAX_RETRIES:
            # Exhausted retries → send to DLQ for manual inspection
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
            log.error(f"Poison message after {retry_count} retries: {body}")
        else:
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
            # Goes to DLX → retry_queue (TTL) → back to main queue
```

### Fix 2: Configure DLX at queue level

```python
# Queue with DLX — failed messages automatically go to dead_letter_queue
channel.queue_declare(
    queue="main_queue",
    arguments={
        "x-dead-letter-exchange":    "dlx_exchange",
        "x-dead-letter-routing-key": "failed",
        "x-message-ttl":             60000,   # message expires after 60s
    },
    durable=True,
)
```

---

## 4. Queue Grows to Millions of Messages

```
Scenario:
  payment_queue: 3,000,000 messages
  Consumer throughput: 100 msg/sec
  Time to drain: 3,000,000 / 100 = 30,000 seconds ≈ 8 hours

Diagnosis steps:
  1. Are consumers running? → management UI → Consumers tab
  2. Consumer count = 0? → workers crashed, restart them
  3. Consumers running but queue not draining?
      a. Downstream DB slow → EXPLAIN ANALYZE, connection pool
      b. External API rate-limited → rate limiting (see theory/11 Celery)
      c. Prefetch too high → 1 worker holding thousands of messages
  4. Queue maxed → messages being dropped? → check x-overflow setting
```

### Emergency: Purge queue (DESTRUCTIVE)

```bash
# Management UI → Queue → Purge
# Or CLI:
rabbitmqctl purge_queue payment_queue

# Only do this if messages are stale/irrelevant — they are permanently deleted
```

---

## 5. Duplicate Messages

```
Scenario:
  Consumer processes payment → DB updated → consumer crashes before ACK
  Broker redelivers message → consumer processes again → double charge

Causes:
  1. Consumer crash after processing but before ACK
  2. Network timeout → broker thinks consumer dead → redelivers
  3. Visibility timeout exceeded (long-running task)
```

### Fix: Idempotent consumer

```python
import sqlite3

conn = sqlite3.connect("processed.db")
conn.execute("""
    CREATE TABLE IF NOT EXISTS processed_messages (
        message_id TEXT PRIMARY KEY,
        processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
""")

def on_message(ch, method, properties, body):
    message_id = properties.message_id or str(body)  # unique ID

    # Check if already processed (idempotency check)
    existing = conn.execute(
        "SELECT message_id FROM processed_messages WHERE message_id=?",
        (message_id,)
    ).fetchone()

    if existing:
        print(f"Duplicate detected: {message_id} — skipping")
        ch.basic_ack(delivery_tag=method.delivery_tag)   # ACK to remove from queue
        return

    try:
        process_payment(body)
        conn.execute(
            "INSERT INTO processed_messages (message_id) VALUES (?)",
            (message_id,)
        )
        conn.commit()
        ch.basic_ack(delivery_tag=method.delivery_tag)
    except Exception as e:
        conn.rollback()
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)
```

---

## 6. One Slow Consumer Affecting Others

```
Scenario:
  payment_queue → 3 consumers
  Consumer A: processing large PDF attachment (30s per message)
  Consumer B: processing normal payments (0.5s per message)
  Consumer C: processing normal payments (0.5s per message)

  prefetch_count=10 (default):
    Consumer A grabs 10 messages → all stuck for 30s each
    Consumer B + C share remaining messages (fair, but A is a bottleneck)
```

### Fix 1: prefetch_count=1 (fair dispatch)

```python
channel.basic_qos(prefetch_count=1)
# Consumer A finishes 1 message (30s) → gets next
# Consumer B/C finish quickly → pick up more messages
# Queue drains faster overall
```

### Fix 2: Separate queues by message type

```python
# Route large attachments to different queue with dedicated slow workers
app.conf.task_routes = {
    "tasks.process_pdf":     {"queue": "pdf_queue"},      # 2 dedicated workers
    "tasks.process_payment": {"queue": "payment_queue"},  # 5 fast workers
}
```

---

## 7. Network Partition

```
Scenario:
  RabbitMQ Cluster: Node A (EU) ←→ Node B (US)
  Network splits: A and B can't reach each other

  Without partition handling:
    → Both nodes accept writes ("split brain")
    → Cluster heals → conflicting state, messages lost

RabbitMQ response:
  Depending on partition_handling config:
    ignore:    both sides continue (default — risk: split brain)
    pause_minority: minority partition PAUSES (stops accepting writes)
    autoheal:  automatic winner selection after partition heals
```

```bash
# rabbitmq.conf
cluster_partition_handling = pause_minority  # safer for production
# Minority side pauses → no writes lost to split-brain
# Majority side continues → brief availability loss but no inconsistency
```

---

## 8. Failure Scenarios — Quick Reference

| Scenario | Root Cause | Detection | Fix |
|----------|-----------|-----------|-----|
| Broker down | OOM, crash | Connection errors | `connect_robust()`, durable queue + persistent msg |
| Consumer crash | Bug, OOM | Queue depth growing | Manual ACK, idempotent consumer |
| Poison message | Malformed data | High NACK rate | x-death retry limit + DLQ |
| Queue millions | Consumer lag | Queue depth metric | Scale consumers, fix downstream |
| Duplicate message | Crash after process, before ACK | Double payments | Idempotency key + DB unique constraint |
| Slow consumer | CPU/IO bound | Unacked count high per consumer | prefetch=1, separate queue |
| Network partition | Split brain | Cluster health check | `pause_minority` partition handling |
| Memory alarm | Queue too large | Broker blocks publishers | `x-max-length`, consumer scaling |

---

## 9. Checklist — Before Production

```
□ All queues durable=True
□ All messages delivery_mode=2 (persistent)
□ Publisher confirms enabled on producer
□ Manual ACK on all consumers (no auto_ack=True)
□ prefetch_count set (not default unlimited)
□ DLX configured for all queues (no poison message loops)
□ connect_robust() used in all services
□ consumers are idempotent (at-least-once is normal)
□ Monitoring: queue depth, unacked, consumer count alerts
□ cluster_partition_handling = pause_minority (for clusters)
```

---

## 10. Interview Questions

**Q: Worker crash ke baad message ka kya hota hai?**
Depends on ACK mode. `auto_ack=True`: message permanently gone. Manual ACK with `acks_late` behavior: broker requeues message when connection closes. Re-consumer ko message dobara milta hai. Isiliye consumers idempotent hone chahiye.

**Q: Poison message ko infinite retry loop se kaise rokein?**
x-death header mein RabbitMQ retry count track karta hai. Consumer check kare — agar count >= max_retries: `basic_nack(requeue=False)` → DLX → DLQ. Wahan manual inspection ya separate alert.

**Q: RabbitMQ mein at-least-once delivery ka matlab kya hai?**
Har message kam se kam ek baar deliver hoga — lekin duplicate possible hai (consumer crash after processing but before ACK). Isliye consumers ko idempotent design karo: message_id check karo before processing.

**Q: Network partition mein cluster kya kare — `ignore` ya `pause_minority`?**
Production mein `pause_minority`. `ignore` se split-brain ho sakta hai — dono sides writes accept karte hain, cluster heal hone pe conflicting state. `pause_minority` se minority side stop ho jaata hai — consistency prefer hoti hai availability ke upar.
