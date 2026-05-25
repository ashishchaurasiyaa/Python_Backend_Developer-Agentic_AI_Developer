# 05 — Exactly-Once Semantics & Transactions

> The hardest correctness guarantee in distributed systems. Kafka delivers it through idempotent producers + transactions + read-process-write isolation.

---

## Why It Matters

Real example: payment service consumes orders, charges card, writes audit log.

```
Consumer reads order msg → charges card → writes audit msg
                                              ↓
                                      crashes before commit
                                              ↓
                          on restart: reads same order msg → CHARGES AGAIN
```

Customer charged twice. Disaster.

Exactly-once: guarantees each message processed exactly one time across the whole pipeline.

---

## The Three Layers

### Layer 1: Idempotent Producer
Avoid duplicate writes due to network retries.

```python
producer = AIOKafkaProducer(
    enable_idempotence=True,    # producer assigns sequence numbers
    acks="all"                   # broker dedupes by sequence
)
```

How: producer gets a Producer ID (PID) from broker. Each message has PID + sequence number. Broker rejects duplicates with same (PID, seq).

**Result:** producer retry doesn't cause double-write.

### Layer 2: Transactional Producer
Multiple writes atomic across topics/partitions.

```python
producer = AIOKafkaProducer(
    transactional_id="payment-processor",
    enable_idempotence=True
)
await producer.start()
await producer.init_transactions()

async with producer.transaction():
    await producer.send("audit_log", value={"order_id": 1})
    await producer.send("notifications", value={"to": "user@x.com"})
    # Either both commit or both abort
```

How: producer writes "transaction begin" marker → writes messages → writes "transaction commit" marker. Consumers configured with `read_committed` skip aborted txns.

### Layer 3: Read-Process-Write (RPW)
Consumer commits its offset *as part of* the producer's transaction.

```python
async with producer.transaction():
    # Process message
    await producer.send("downstream", value=processed)

    # Commit consumer offset as part of same transaction
    await producer.send_offsets_to_transaction(
        offsets={TopicPartition("orders", 0): OffsetAndMetadata(msg.offset + 1, "")},
        group_id="payment-processor"
    )

# Atomic: either consumer offset committed AND downstream written, or neither
```

If processing crashes: txn aborts, consumer offset NOT advanced, message re-delivered.
If transaction commits: consumer offset advanced AND downstream written. Exactly once.

---

## Read Committed Isolation

Consumers must opt-in to see only committed transactions:

```python
consumer = AIOKafkaConsumer(
    "orders",
    isolation_level="read_committed"   # default: read_uncommitted
)
```

With `read_committed`: consumer waits for transaction marker before showing messages. Slight latency increase.

Without (default): consumer might read messages from aborted transactions.

---

## Full Example: Exactly-Once Pipeline

```python
import asyncio
from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
from aiokafka.structs import TopicPartition, OffsetAndMetadata

async def exactly_once_processor():
    producer = AIOKafkaProducer(
        bootstrap_servers="localhost:9092",
        transactional_id="payment-svc-1",
        enable_idempotence=True
    )
    consumer = AIOKafkaConsumer(
        "orders",
        bootstrap_servers="localhost:9092",
        group_id="payment-svc",
        isolation_level="read_committed",
        enable_auto_commit=False
    )

    await producer.start()
    await consumer.start()
    await producer.init_transactions()

    try:
        async for msg in consumer:
            async with producer.transaction():
                # Process the order
                result = await process_payment(msg.value)

                # Write to downstream topics
                await producer.send("audit", value=result)
                await producer.send("notifications", value=result)

                # Commit consumer offset atomically
                await producer.send_offsets_to_transaction(
                    {TopicPartition(msg.topic, msg.partition):
                     OffsetAndMetadata(msg.offset + 1, "")},
                    "payment-svc"
                )
    finally:
        await producer.stop()
        await consumer.stop()

asyncio.run(exactly_once_processor())
```

This is the canonical Kafka "exactly-once" pattern.

---

## The Catch: Side Effects Outside Kafka

Exactly-once works inside Kafka. The moment you do something outside (call payment gateway, hit DB), all bets are off.

```python
async with producer.transaction():
    # External side effect — NOT in transaction
    await payment_gateway.charge(order)   # ← what if this succeeds but txn aborts?

    await producer.send("audit", ...)
```

Two strategies:
1. **Outbox pattern**: write to DB + outbox table in same DB transaction; separate process reads outbox → Kafka.
2. **Idempotent external systems**: Stripe etc. support idempotency keys.

---

## Outbox Pattern (Recommended)

Avoid Kafka transactions entirely for service-DB-Kafka consistency.

```sql
BEGIN;
  UPDATE orders SET status = 'paid' WHERE id = $1;
  INSERT INTO outbox (event_type, payload, created_at)
    VALUES ('order.paid', '{"order_id":1}', now());
COMMIT;
```

Outbox poller (or Debezium reading outbox):
```python
async def outbox_publisher():
    while True:
        rows = await db.fetch("SELECT * FROM outbox WHERE published_at IS NULL LIMIT 100")
        for row in rows:
            await producer.send(row.event_type, value=row.payload)
            await db.execute("UPDATE outbox SET published_at = now() WHERE id = $1", row.id)
        await asyncio.sleep(0.5)
```

**Benefits:**
- DB and outbox writes are in one DB transaction (atomicity).
- Kafka publish is at-least-once (with idempotent consumer = effectively exactly-once).
- No Kafka transactions needed.

---

## Costs of Exactly-Once

| Aspect | Cost |
|---|---|
| Throughput | 10-30% slower than at-least-once |
| Latency | +5-50ms per message |
| Complexity | Higher (transactional state) |
| Recovery | Slower (need to rebuild state on crash) |

Most teams use **at-least-once + idempotent consumers**. Reserve full Kafka transactions for cases where:
- Multiple downstream writes must be atomic.
- DB writes mixed with Kafka writes.

---

## Idempotent Consumers (Cheaper Alternative)

Often you don't need Kafka transactions. Just make your consumer idempotent.

### Pattern: dedupe via DB unique constraint
```python
async def process(msg):
    try:
        await db.execute(
            "INSERT INTO processed (msg_id) VALUES ($1)",
            msg.headers["msg_id"]
        )
        await actual_work(msg.value)
    except UniqueViolationError:
        return  # already processed
```

### Pattern: Redis dedupe
```python
async def process(msg):
    if await redis.set(f"processed:{msg.id}", 1, nx=True, ex=86400):
        await actual_work(msg.value)
```

### Pattern: Conditional updates
```python
# Only apply event if not already applied
await db.execute(
    "UPDATE accounts SET balance = balance + $1, last_event_id = $2 "
    "WHERE id = $3 AND last_event_id != $2",
    msg.amount, msg.id, msg.account_id
)
```

---

## Stream Processing Exactly-Once (Faust/Flink)

Faust:
```python
app = faust.App(..., processing_guarantee="exactly_once")
```

Flink:
```python
env.get_checkpoint_config().set_checkpointing_mode(CheckpointingMode.EXACTLY_ONCE)
```

Internally use the same Kafka transaction pattern.

---

## When NOT to use Exactly-Once

- Logging / analytics (lossy is fine).
- Hot-path low-latency (overhead unacceptable).
- External side effects already idempotent (Stripe charges via Idempotency-Key).
- Counters that you reconcile periodically.

---

## When You MUST use Exactly-Once

- Money movement (payments, transfers).
- Inventory deduction.
- Order placement.
- Anything where duplicates have legal/financial cost.

For these: Kafka transactions OR outbox + idempotent consumer.

---

## Transactional Producer Internals

```
Producer init:
  1. Producer requests TransactionalCoordinator (some broker).
  2. Coordinator assigns PID.

producer.begin_transaction():
  3. Producer notifies coordinator.

producer.send():
  4. Producer writes message with PID + seq + txnId to partition.
  5. Broker buffers; not yet visible to read_committed consumers.

producer.commit_transaction():
  6. Producer notifies coordinator → all partitions get "commit marker".
  7. read_committed consumers now see the messages.

producer.abort_transaction():
  6'. Coordinator writes "abort marker".
  7'. read_committed consumers skip those messages.
```

Two-phase commit-like protocol coordinated by the broker.

---

## Failure Scenarios

### Producer crashes mid-transaction
On restart with same `transactional_id`, coordinator detects stale instance → aborts old transaction. New instance proceeds.

### Network partition during commit
Coordinator either commits or aborts based on quorum. Producer client may retry; idempotent.

### Consumer crashes mid-process
Offset never committed → next consumer reads same message → process again.

### Broker crashes
Replicas take over; transactions persist via replicated state.

---

## Comparison Summary

| Guarantee | How | Use case |
|---|---|---|
| At-most-once | acks=0, fire-forget | Logs, metrics |
| At-least-once | acks=all + retries | Most pipelines |
| Exactly-once (Kafka-internal) | Txn + read_committed + RPW | Critical pipelines |
| Effectively exactly-once | At-least-once + idempotent consumer | Most production |

---

## Practical Recipe

For 90% of teams:

```python
# Producer
producer = AIOKafkaProducer(
    enable_idempotence=True,   # safe retries
    acks="all"
)

# Consumer
consumer = AIOKafkaConsumer(
    enable_auto_commit=False,  # manual commit
    isolation_level="read_committed"
)

# Process
async for msg in consumer:
    if await already_processed(msg.id):  # idempotency check
        await consumer.commit()
        continue
    await process(msg.value)
    await mark_processed(msg.id)
    await consumer.commit()
```

Effectively exactly-once with simple code.

---

## TL;DR

- Exactly-once requires: idempotent producer + transactions + RPW pattern.
- Costs 10-30% throughput.
- Use Kafka transactions only when multi-topic atomicity matters.
- Outbox pattern is cleaner when DB is involved.
- For most pipelines: at-least-once + idempotent consumer.
- Reserve full exactly-once for money/orders.
