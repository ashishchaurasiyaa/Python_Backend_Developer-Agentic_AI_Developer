# 06 — Messaging

## Why messaging?

Synchronous request/response (REST, RPC) works until you hit:
- **Coupling** — caller must know callee's location and uptime
- **Blocking** — caller waits for slow downstream
- **Burst overload** — spikes overwhelm callees
- **Cross-service transactions** — hard to coordinate
- **Multiple consumers** — same event must trigger many actions

Asynchronous messaging decouples producer and consumer in **time, space, and concurrency**. Producer fires-and-forgets; broker holds the message; consumer processes when ready.

## Three categories

### 1. Message Queue

A queue holds messages until a consumer pulls them. Each message is delivered to **one** consumer (point-to-point).

- Examples: **RabbitMQ**, **Amazon SQS**, **ActiveMQ**, Redis Lists, BeanstalkD
- Use case: task queue — image resize, email send, video transcode, payment processing

### 2. Publish-Subscribe (pub/sub)

A topic broadcasts messages to **all** subscribers.

- Examples: **Redis Pub/Sub**, **Google Pub/Sub**, **NATS**, AWS SNS
- Use case: notifications, fanout to multiple downstream services

### 3. Streaming / Log

An append-only, durable, replayable log partitioned across machines. Consumers track their own position (offset).

- Examples: **Apache Kafka**, **AWS Kinesis**, **Apache Pulsar**, **Redpanda**
- Use case: event sourcing, CDC, analytics pipeline, audit log, system-of-record

## Kafka vs RabbitMQ vs SQS — pick one

| | **Kafka** | **RabbitMQ** | **SQS** |
|---|-----------|--------------|---------|
| Model | Log (commit log) | Queue (AMQP) | Queue (managed) |
| Throughput | Millions msgs/sec | ~50K msgs/sec | High (managed scale) |
| Latency | ms | µs-ms | 10-100ms |
| Ordering | Per-partition | Per-queue (single consumer) | FIFO queues only |
| Replay | Yes (offset-based, retention period) | No (delete on ack) | No (delete on receive+delete) |
| Persistence | Yes (mandatory disk log) | Optional | Yes (managed) |
| Routing | Topics + partitions | Exchanges (direct/fanout/topic/headers) | Queue only (or SNS+SQS for fanout) |
| Multi-consumer | Yes (consumer groups) | Yes (competing consumers) | Yes (visibility timeout) |
| Operational cost | High (run cluster) | Medium | Zero (managed) |
| Best for | Event streaming, analytics, log aggregation, CDC | Task queues with complex routing | Simple async work in AWS |

**Rule of thumb:**
- Need replay or > 100K msgs/sec → **Kafka**
- Complex routing (priorities, headers, RPC-style) → **RabbitMQ**
- In AWS, simple task queue → **SQS**

## Delivery semantics

### At-most-once

Send and forget. Possible loss, never duplicates. Use for: metrics where loss is acceptable.

### At-least-once

Retry until ack. Possible duplicates, never loss. **Most common.** Use for: 99% of business workflows. Requires **idempotent** consumers.

### Exactly-once

The holy grail. Achieved by:
- **Transactions** at the producer (Kafka transactions, idempotent producers)
- **Idempotency** at the consumer (dedupe by message ID, check-then-act)
- **End-to-end commit protocols** (Kafka Streams, Flink with checkpointing)

True exactly-once *between systems* (Kafka → DB → Cache → notification) is essentially impossible without idempotency. So: aim for at-least-once delivery + idempotent processing.

## Idempotency — the workhorse

A consumer is idempotent if processing the same message twice has the same effect as once.

**Techniques:**

1. **Use a deterministic ID** for the message and check before acting.
   ```python
   if not seen_message(msg.id):
       process(msg)
       record_seen(msg.id)
   ```
2. **Upsert** (insert or update) instead of insert. `INSERT ... ON CONFLICT DO NOTHING`.
3. **Conditional updates** by version: `UPDATE x SET v=v+1 WHERE v=expected_v`.
4. **Make the operation naturally idempotent**: "set status to PAID" vs "increment payment count."

## Ordering guarantees

Strict ordering across the system is expensive. Common compromises:

- **Per-partition ordering** (Kafka): messages with same key go to same partition, ordered.
- **Per-queue ordering** (RabbitMQ): one consumer per queue → ordered.
- **No global ordering** in general — accept it.

**Design pattern:** key by `entity_id` so all events for that entity stay in order.

## Backpressure

Consumer slower than producer → queue grows unboundedly → eventually broker OOM or producer blocked.

**Strategies:**

1. **Drop on overflow** (lossy) — for non-critical messages (metrics).
2. **Block the producer** (backpressure signal) — natural in RabbitMQ; producer must handle.
3. **Spill to disk** — Kafka does this by default (it's a log).
4. **Scale consumers horizontally** — add more workers.
5. **Reactive flow control** — Kafka pause/resume, BackPressure in reactive frameworks.
6. **Buffer + sample** — for metrics, send only 1% under load.

## Dead-letter queues (DLQ)

Messages that fail processing repeatedly go to a DLQ for human inspection.

**Pattern:**
```
process(msg):
    try: handle(msg)
    except: 
        if msg.retries < N:
            requeue_with_backoff(msg)
        else:
            send_to_DLQ(msg)
            alert()
```

DLQ contents reveal bugs, schema mismatches, poison pills. **Monitor DLQ depth** as an SLI.

## Kafka — the architecture you must know

### Concepts

- **Topic:** named stream of messages
- **Partition:** topic divided into N partitions; each is an ordered log
- **Offset:** position in a partition; consumers track their own
- **Producer:** writes to a topic, picks partition (round-robin, hash by key, custom)
- **Consumer group:** set of consumers cooperating; each partition consumed by exactly one consumer in the group
- **Broker:** Kafka node; partitions replicated across brokers (ISR = in-sync replicas)
- **Retention:** time-based (e.g., 7 days) or size-based; old messages deleted regardless of consumption

### Why it's fast

- Sequential disk I/O (faster than random RAM access for streaming)
- Zero-copy via `sendfile()`
- Batched compression
- Page cache reuse

### Replication

- Each partition has a leader and N replicas.
- Producer writes go to leader; replicas pull and ack.
- `acks=all` waits for all ISR replicas (durable).
- On leader failure, controller elects a new leader from ISR.

## Event-Driven Architecture (EDA)

Services communicate by emitting and reacting to events rather than calling each other.

**Benefits:**
- Loose coupling (producers don't know consumers)
- Easy to add new consumers (just subscribe)
- Natural audit log
- Resilient to downstream failure

**Patterns:**
- **Event notification** — "OrderPlaced" event, others react.
- **Event-carried state transfer** — event contains the data, consumers don't query source. Reduces calls but enlarges events.
- **Event sourcing** — store events as the source of truth; rebuild state by replay.
- **CQRS** — separate command (write) and query (read) models, often event-driven.

## Outbox pattern (transactional messaging)

Problem: write to DB *and* publish event must be atomic. Otherwise: write succeeds, publish fails → state diverges.

**Solution:** in the same DB transaction, write the business state AND insert into an `outbox` table. A separate process reads the outbox and publishes (with idempotency). CDC streams can do this automatically (Debezium).

## Saga pattern (for distributed transactions)

Long-running business txn = sequence of local txns + compensations.

```
Order → Reserve Inventory → Charge Card → Confirm Shipping
     ↑       ↓ (fail)       ↓ (fail)        ↓ (fail)
     +— Release Inventory ←— Refund Card ←— Cancel Shipping
```

Two implementations:
- **Choreography:** each service publishes events, others react. Decentralized.
- **Orchestration:** central saga executor coordinates steps. Easier to reason about.

## Messaging anti-patterns

1. **Using a queue as a DB** — message broker isn't long-term storage; use Kafka with long retention or move data to DB.
2. **Synchronous over async** — calling `await response_from_queue()` in user request path; you've reinvented sync RPC with worse latency.
3. **No DLQ** — failed messages either lost or loop forever.
4. **Non-idempotent consumers** with at-least-once delivery — duplicates cause double-charges, double-emails.
5. **Unversioned message schemas** — producer upgrades, consumers crash. Use Avro/Protobuf with backward compatibility.
6. **Logging every message body** — easy GDPR violation.

## Interview Q&A

**Q1: User signs up. Should sending the welcome email be sync or async?**
*A:* Async via a queue. Email service might be slow/unavailable; user shouldn't wait. Pattern: signup service writes user to DB, publishes `UserSignedUp` event; email worker consumes and sends. Use idempotent send (dedupe by user_id) to prevent duplicates from retries.

**Q2: How do you pick between Kafka and RabbitMQ?**
*A:* Kafka if you need: high throughput (>10K msgs/sec), event replay, durable log, stream processing. RabbitMQ if you need: complex routing rules, lower throughput is fine, RPC-style messaging, traditional queue semantics. Many systems use both — Kafka for events, Rabbit for task queues.

**Q3: A consumer is slow and the queue is growing. What do you do?**
*A:* Short-term: scale consumers horizontally (more workers in the consumer group). Verify Kafka has enough partitions (consumer parallelism is bounded by partition count). Add backpressure / autoscaling. Long-term: profile the consumer (DB query slow? external API?). If messages have varied cost, partition by cost class (slow vs fast queue).

**Q4: How do you achieve exactly-once processing?**
*A:* End-to-end exactly-once requires: (1) idempotent producer (Kafka transactional API), (2) idempotent consumer (dedupe by message ID + transactional DB write), (3) the consumer's side effect must be transactional with its offset commit. Kafka Streams and Flink offer this within their pipeline. Cross-system, idempotent design is the only reliable path.

**Q5: Order events are arriving out of order. How do you guarantee in-order processing per user?**
*A:* In Kafka, key messages by `user_id`. Same key → same partition → ordered. Within a partition, consumer processes serially. Tradeoff: max parallelism = number of partitions. If `user_id` has skew (one user with 1M events), revisit partitioning.

**Q6: What's the outbox pattern and why?**
*A:* It solves "write to DB AND publish event" atomicity. Instead of doing both as separate operations (which can fail half-way), write the business data and an "outbox" row in one DB transaction. A separate publisher reads new outbox rows and emits events. Ensures: every committed business change has a corresponding event (eventually).

**Q7: Walk through how Kafka achieves durability.**
*A:* Producer sets `acks=all` → leader doesn't ack until all in-sync replicas have appended. Partitions are replicated; failure of one broker doesn't lose data if `min.insync.replicas >= 2`. Disk fsync is configurable. Topics have retention (e.g., 7 days) so even consumer crashes can replay. Combined: very durable, but configuration-sensitive.

## Further reading

- *DDIA* — Ch 11 (Stream Processing)
- "Designing Event-Driven Systems" — Ben Stopford (free)
- Kafka official docs + Confluent blog
- Existing notes: `../*_Message*.md`, `../*_Kafka*.md` if present
