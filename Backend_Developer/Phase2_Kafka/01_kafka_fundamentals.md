# 01 — Kafka Fundamentals

> Distributed event streaming platform. Backbone of modern data pipelines, microservice event buses, and real-time analytics.

---

## What Kafka Is

A **distributed append-only commit log**.

- Producers append messages to topics.
- Topics are partitioned and replicated.
- Consumers read messages from topics at their own pace.
- Messages persist for a configured retention period (default 7 days, can be forever).

**Use cases:**
- Event-driven microservices.
- Real-time analytics pipelines.
- Log aggregation.
- Change Data Capture (CDC).
- Activity tracking.
- Stream processing (Kafka Streams, Flink).

---

## Core Concepts

### Topic
Named stream of messages. Logical category.
```
topics: orders, payments, user_events
```

### Partition
Each topic is split into N partitions for parallelism.

```
Topic "orders" with 3 partitions:
  Partition 0: [msg1, msg4, msg7, ...]
  Partition 1: [msg2, msg5, msg8, ...]
  Partition 2: [msg3, msg6, msg9, ...]
```

Messages within a partition are strictly ordered. Across partitions: no order guarantee.

### Offset
Each message has a sequential offset within its partition. Consumers track which offset they've processed.

```
Partition 0: [offset=0: msg1, offset=1: msg4, offset=2: msg7]
                                                    ↑
                                            consumer at offset 2
```

### Broker
A Kafka server. Cluster = multiple brokers.

### Replication
Each partition has N replicas (typically 3) across brokers. One is leader, rest are followers.

```
Partition 0:
  Leader   → Broker 1
  Follower → Broker 2
  Follower → Broker 3
```

All reads/writes go to leader. Followers sync. On leader failure, follower promotes.

### Producer
Writes messages to topics.

### Consumer
Reads messages from topics. Consumers grouped into **consumer groups**.

### Consumer Group
Set of consumers sharing the load. Each partition assigned to exactly one consumer in the group.

```
Topic with 6 partitions, group with 3 consumers:
  Consumer 1 → Partitions 0, 1
  Consumer 2 → Partitions 2, 3
  Consumer 3 → Partitions 4, 5

If consumer 2 dies → partitions reassigned.
```

If # consumers > # partitions → some idle.

### ZooKeeper / KRaft
Pre-KRaft: ZooKeeper managed cluster metadata.
KRaft (Kafka 3.3+): metadata in Kafka itself. No more ZooKeeper.

---

## Architecture Diagram

```
   Producers
      │ │ │
      ▼ ▼ ▼
  ┌─────────────────────────────┐
  │       Kafka Cluster         │
  │  ┌──────┐ ┌──────┐ ┌──────┐ │
  │  │Broker│ │Broker│ │Broker│ │
  │  │  1   │ │  2   │ │  3   │ │
  │  └──────┘ └──────┘ └──────┘ │
  └──────┬──────────────────────┘
         │ topics (replicated)
         ▼
   Consumer Groups
      │ │ │
   (multiple groups can read same topic independently)
```

---

## Message Anatomy

```python
ConsumerRecord(
    topic="orders",
    partition=2,
    offset=12345,
    key=b"user-123",
    value=b'{"order_id":1,"amount":100}',
    timestamp=1700000000000,
    headers=[("trace_id", b"abc...")]
)
```

- **key**: optional. Used for partitioning + compaction.
- **value**: the payload (bytes; can be JSON, Avro, Protobuf).
- **headers**: metadata key-value pairs.

---

## Partitioning Strategy

How a message goes to which partition:

1. **Key-based hashing (default):** `partition = hash(key) % num_partitions`. Same key → same partition → ordered per key.
2. **Round-robin (no key):** Spread evenly across partitions.
3. **Custom partitioner:** Implement `Partitioner` interface.

**Pattern:** Use `user_id` as key to ensure all events for a user go to same partition (preserving order).

---

## Replication & ISR (In-Sync Replicas)

ISR = replicas currently caught up with leader.

```
Producer write → Leader writes → Replicates to ISR followers
                      ↓
                  acks=all: wait for all ISR to ack
                  acks=1: wait for leader only
                  acks=0: fire and forget
```

### `min.insync.replicas`
Minimum ISR count required for writes.

```
min.insync.replicas = 2
replication.factor = 3
```

If only 1 replica in sync, writes with `acks=all` fail (NotEnoughReplicas error).

Trade-off: durability vs availability.

---

## Retention

```
log.retention.hours = 168    # 7 days
log.retention.bytes = -1     # unlimited (use time)
log.cleanup.policy = delete  # or "compact"
```

After retention, old messages deleted.

### Log Compaction
Keep only the latest value per key. Like a "snapshot" of state.

```
Before compaction:
  user-1 → email A
  user-2 → email B
  user-1 → email C (update)
  user-3 → email D
  user-1 → email E (update)

After compaction:
  user-2 → email B
  user-3 → email D
  user-1 → email E   (only latest)
```

Used for: storing latest state of entities (CDC, event sourcing snapshots).

---

## Delivery Semantics

| Semantic | What it means |
|---|---|
| **At-most-once** | Send and forget; loss possible (acks=0). |
| **At-least-once** | Retry on failure; duplicates possible (acks=all + retries). Default. |
| **Exactly-once** | Achieved via transactions + idempotent producer (Kafka 0.11+). |

**In practice:** Most pipelines use at-least-once + idempotent consumers.

---

## Kafka vs RabbitMQ vs SQS

| | Kafka | RabbitMQ | SQS |
|---|---|---|---|
| Model | Log (persistent) | Queue | Queue (managed) |
| Replay | ✓ (offset-based) | ✗ | ✗ |
| Throughput | Highest | High | Medium |
| Routing | Topics + partitions | Exchanges, complex routing | Simple |
| Ordering | Per partition | Per queue | FIFO queue only |
| Use case | Streams, events at scale | Task queues, complex routing | Managed simple queues |

---

## When to use Kafka

✅ Good fit:
- Event streaming (analytics, CDC).
- Multiple consumers of same data.
- Replay capability needed.
- High throughput (> 100K msg/sec).
- Decoupling between producers and consumers.
- Stream processing.

❌ Bad fit:
- Simple background jobs (Celery/RQ better).
- Low message volume (< 1K msg/sec).
- Need complex routing logic (RabbitMQ better).
- Managed environment with no ops capacity (SQS easier).

---

## Setup (Local Dev with Docker)

```yaml
# docker-compose.yml (KRaft mode, no ZooKeeper)
services:
  kafka:
    image: apache/kafka:3.7.0
    ports:
      - "9092:9092"
    environment:
      KAFKA_NODE_ID: 1
      KAFKA_PROCESS_ROLES: 'broker,controller'
      KAFKA_LISTENERS: 'PLAINTEXT://:9092,CONTROLLER://:9093'
      KAFKA_LISTENER_SECURITY_PROTOCOL_MAP: 'PLAINTEXT:PLAINTEXT,CONTROLLER:PLAINTEXT'
      KAFKA_CONTROLLER_QUORUM_VOTERS: '1@kafka:9093'
      KAFKA_CONTROLLER_LISTENER_NAMES: 'CONTROLLER'
      KAFKA_ADVERTISED_LISTENERS: 'PLAINTEXT://localhost:9092'
      KAFKA_AUTO_CREATE_TOPICS_ENABLE: 'true'
```

```bash
docker compose up -d
```

---

## Basic CLI Commands

```bash
# Create topic
kafka-topics.sh --create --topic orders --partitions 3 --replication-factor 1 --bootstrap-server localhost:9092

# List topics
kafka-topics.sh --list --bootstrap-server localhost:9092

# Produce
kafka-console-producer.sh --topic orders --bootstrap-server localhost:9092
> {"order_id":1,"amount":100}

# Consume from beginning
kafka-console-consumer.sh --topic orders --from-beginning --bootstrap-server localhost:9092

# Describe topic
kafka-topics.sh --describe --topic orders --bootstrap-server localhost:9092

# Consumer group lag
kafka-consumer-groups.sh --describe --group my-group --bootstrap-server localhost:9092
```

---

## Internal Storage Format

Each partition = a directory:
```
/var/lib/kafka/data/orders-0/
  00000000000000000000.log    (segment file)
  00000000000000000000.index
  00000000000000000000.timeindex
  00000000000010000000.log    (next segment after rollover)
  ...
```

- Segments roll over by size (1GB default) or time (7 days).
- Reads use OS page cache → very fast.

---

## Key Configuration Knobs

| Config | Default | Tuning |
|---|---|---|
| `num.partitions` | 1 | Set higher for parallelism (3-50 typical) |
| `replication.factor` | 1 | 3 for production |
| `min.insync.replicas` | 1 | 2 for production |
| `acks` (producer) | 1 | "all" for durability |
| `compression.type` | none | lz4 or snappy for throughput |
| `batch.size` (producer) | 16KB | Higher = fewer requests |
| `linger.ms` (producer) | 0 | 5-100ms = batch latency tradeoff |
| `fetch.min.bytes` (consumer) | 1 | Higher = more efficient |
| `enable.auto.commit` | true | false for at-least-once |

---

## Common Pitfalls

### 1. Single partition for everything
No parallelism. Can't scale consumers.
**Fix:** Plan partitions upfront. Hard to change later without resharding.

### 2. Wrong key choice → hot partition
All messages go to same partition because hash(key) == constant.
**Fix:** Salt keys for hot users, or pick better key.

### 3. `acks=0` in production
Messages lost on broker fail.
**Fix:** `acks=all` + retries.

### 4. Unbounded retention
Disk fills up.
**Fix:** Set retention.hours or use compaction.

### 5. Consumer not handling rebalances
Long-running processing gets killed during rebalance.
**Fix:** Use cooperative rebalancing + commit progress periodically.

### 6. Same group ID for unrelated consumers
Two services with same group ID share partitions accidentally.
**Fix:** Unique group IDs per service.

---

## TL;DR

- Kafka = distributed append-only log.
- Topics → partitions → ordered messages.
- Consumers in groups split partitions for parallelism.
- Persistent storage with configurable retention.
- Replication + ISR for durability.
- Use for streams, event-driven systems, CDC, analytics.
- Not a queue: it's a log. Different mental model from RabbitMQ.
