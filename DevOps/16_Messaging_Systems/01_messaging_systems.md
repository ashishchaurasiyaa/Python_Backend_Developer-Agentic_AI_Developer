# Messaging Systems — RabbitMQ, Kafka, Redis Streams, SQS/SNS Ops

**DevOps Track · Phase 16: Messaging Systems**

> Complementary to the app-level coverage in Backend_Developer/ — this covers the infra/ops angle: hardening, deployment, and operating these systems.

## Quick Concepts

- **Exchange (RabbitMQ)** = routing entity that receives published messages and routes them to queues based on bindings/rules
- **Queue (RabbitMQ)** = ordered buffer holding messages until a consumer processes them
- **Binding** = rule connecting an exchange to a queue, optionally with a routing key
- **Broker (Kafka)** = a single Kafka server; a cluster is made of multiple brokers
- **Partition** = a Kafka topic is split into partitions for parallelism — each partition is an ordered, append-only log
- **Replication factor** = how many broker copies of each partition exist, for durability
- **Consumer group** = a set of consumers that split a topic's partitions among themselves for parallel, non-duplicate processing
- **DLQ (Dead Letter Queue)** = destination for messages that fail processing repeatedly, so they don't block the main queue forever
- **Visibility timeout (SQS)** = how long a message stays invisible to other consumers after being received, before it's assumed failed and reappears

---

## Why This Matters for Ops

```
Backend_Developer/07_Kafka and 08_RabbitMQ teach "how do I produce
and consume messages from Python." This file is about running and
choosing between the brokers themselves:

   - Which system do you deploy for a given throughput/durability need?
   - How do you cluster it so a single broker dying doesn't lose messages?
   - How do you configure DLQs and timeouts so failures don't silently
     drop work or infinitely retry-loop a poison message?

Choosing the wrong messaging system for the job is an architecture-
level mistake that's expensive to walk back once services depend on it.
```

---

## RabbitMQ — Ops Model

### Exchanges / Queues / Bindings

```
Producer → Exchange → (binding + routing key) → Queue → Consumer

Exchange types:
   direct  — routes to queue(s) with exact matching routing key
   topic   — routes by pattern (e.g. "orders.*.created")
   fanout  — broadcasts to ALL bound queues, ignores routing key
   headers — routes based on message header attributes, not routing key
```

```bash
# rabbitmqctl — day-to-day ops
rabbitmqctl list_queues name messages consumers
rabbitmqctl list_exchanges name type
rabbitmqctl list_bindings

# Queue health at a glance
rabbitmqctl list_queues name messages messages_ready messages_unacknowledged

# Management UI (enable the plugin) — visual queue/exchange inspection
rabbitmq-plugins enable rabbitmq_management
# http://host:15672
```

### Clustering

```
RabbitMQ clusters replicate metadata (exchanges, bindings, users)
across all nodes automatically. Queue CONTENTS need explicit
mirroring/quorum configuration — a plain queue lives on one node
only, and that node dying loses the queue's messages.

Quorum queues (modern, replaces classic mirrored queues) use a
Raft-based consensus protocol — a queue is replicated across N
nodes, survives the loss of a minority of them.
```

```bash
# Join a node to an existing cluster
rabbitmqctl stop_app
rabbitmqctl join_cluster rabbit@node1
rabbitmqctl start_app

# Declare a quorum queue (durable, replicated) via policy
rabbitmqctl set_policy ha-quorum "^important\." \
    '{"queue-mode":"quorum"}' --apply-to queues

rabbitmqctl cluster_status
```

### When to Choose RabbitMQ

```
Good fit:
   - Complex routing logic (topic/header-based routing between services)
   - Task-queue / work-queue patterns (job dispatch, RPC-style requests)
   - Moderate throughput, strong delivery guarantee semantics per-message
   - You need per-message ack/nack/requeue control

Less of a fit:
   - Very high sustained throughput (millions of msgs/sec) — Kafka wins
   - Need to replay historical messages / long retention — RabbitMQ
     queues drain on consume, not designed as a persistent log
```

---

## Kafka — Ops Model

### Brokers / Partitions / Replication Factor

```
Topic "orders" with 6 partitions, replication factor 3, on a
5-broker cluster:

   Partition 0: leader on broker 2, replicas on brokers 3,4
   Partition 1: leader on broker 1, replicas on brokers 2,5
   ... (each partition independently replicated and load-balanced
        across brokers)

Producers write to partition leaders. Consumers can read from
leaders (default) or followers (rack-aware reads, reduces cross-AZ
cost). Replication factor 3 tolerates 2 broker failures per partition
without data loss (as long as min.insync.replicas is respected).
```

```bash
# Create a topic with explicit partition count + replication factor
kafka-topics.sh --create --topic orders \
    --partitions 6 --replication-factor 3 \
    --bootstrap-server broker1:9092

# Inspect topic + partition leader/replica assignment
kafka-topics.sh --describe --topic orders --bootstrap-server broker1:9092

# Check under-replicated partitions — key health signal
kafka-topics.sh --describe --under-replicated-partitions \
    --bootstrap-server broker1:9092
```

### Consumer Groups

```
All consumers sharing the same group.id split a topic's partitions
among themselves — each partition consumed by exactly ONE consumer
in the group at a time. More consumers than partitions = some
consumers sit idle. This is how Kafka achieves parallel consumption
without message duplication within a group.
```

```bash
# List consumer groups, check lag (messages produced - messages consumed)
kafka-consumer-groups.sh --bootstrap-server broker1:9092 --list
kafka-consumer-groups.sh --bootstrap-server broker1:9092 \
    --describe --group order-processors
# LAG column — the #1 metric for "is this consumer keeping up"
```

### When to Choose Kafka Over RabbitMQ

| | RabbitMQ | Kafka |
|---|---|---|
| Throughput ceiling | High (10k-100k msgs/sec range) | Very high (millions/sec) |
| Message retention | Drains on consume (queue semantics) | Configurable retention (hours to forever) — replayable log |
| Ordering guarantee | Per-queue | Per-partition |
| Routing complexity | Rich (exchange types, routing keys) | Simple (topic + partition key) |
| Replay historical data | No (not designed for it) | Yes — core use case (event sourcing, reprocessing) |
| Operational complexity | Lower | Higher (ZooKeeper/KRaft, partition rebalancing) |
| Best fit | Task queues, RPC, complex routing | Event streaming, high-throughput logs, event sourcing |

```
Rule of thumb: if you need "process this job once" → RabbitMQ.
If you need "many consumers replaying/re-deriving state from an
ordered event history" → Kafka.
```

---

## Redis Streams — The Lightweight Alternative

```
Redis Streams gives an append-only log data structure (XADD/XREAD/
XREADGROUP) inside Redis itself — consumer groups, acknowledgment,
pending-entry lists, similar mental model to Kafka but far lighter
operationally, since it's just Redis.

Good enough when:
   - You already run Redis and don't want to stand up a whole
     Kafka/RabbitMQ cluster for a moderate messaging need
   - Throughput/retention needs are modest (Streams live in Redis
     memory/AOF, not designed for months of retention at high volume)
   - You want consumer-group semantics without new infra

Not a fit when:
   - You need Kafka-scale throughput or long-term event retention
   - You need cross-datacenter replication guarantees messaging
     systems purpose-build for
```

```bash
# Add to a stream, consume via a consumer group
redis-cli XADD orders '*' order_id 123 status created
redis-cli XGROUP CREATE orders processors '$' MKSTREAM
redis-cli XREADGROUP GROUP processors worker1 COUNT 10 STREAMS orders '>'
redis-cli XACK orders processors <message-id>

# Check pending (unacked) messages — health signal
redis-cli XPENDING orders processors
```

---

## AWS SQS vs SNS — Ops Focus

```
SQS = queue (pull-based, one consumer group processes each message)
SNS = pub/sub (push-based, fans out to multiple subscribers —
      often SQS queues, Lambda, HTTP endpoints)

Common pattern: SNS topic fans out to multiple SQS queues (one per
consuming service) — combines pub/sub fan-out with SQS's durable,
poll-based consumption and DLQ support per subscriber.
```

### DLQ Configuration

```bash
# Create a DLQ, then attach it to the main queue with a redrive policy
aws sqs create-queue --queue-name orders-dlq

aws sqs set-queue-attributes --queue-url $MAIN_QUEUE_URL \
  --attributes '{
    "RedrivePolicy": "{\"deadLetterTargetArn\":\"arn:aws:sqs:...:orders-dlq\",\"maxReceiveCount\":5}"
  }'
```

```
maxReceiveCount = 5 means: if a message is received (and not deleted,
i.e. processing failed) 5 times, SQS automatically moves it to the
DLQ instead of redelivering forever. Without a DLQ, a poison message
(one that always crashes the consumer) blocks/cycles indefinitely
and can starve the queue of throughput for OTHER messages.

Always alert on DLQ depth > 0 — a message landing in the DLQ means
something failed 5 times and needs a human to look at it.
```

### Visibility Timeout Tuning

```
When a consumer receives a message, it becomes invisible to other
consumers for the visibility timeout duration. If the consumer
doesn't delete it (ack) within that window, SQS assumes it failed
and makes it visible again for redelivery.

Set it too SHORT: message reappears and gets processed twice while
the first consumer is still legitimately working on it (duplicate
processing — make sure your consumer is idempotent regardless).

Set it too LONG: a genuinely failed/crashed consumer's message sits
invisible and unprocessed for a long time before anyone else picks
it up — delays failure recovery.

Rule of thumb: set visibility timeout to at least 6x your consumer's
expected processing time (AWS's own recommendation), and use
ChangeMessageVisibility to extend it dynamically for long-running jobs.
```

```bash
aws sqs set-queue-attributes --queue-url $QUEUE_URL \
    --attributes VisibilityTimeout=120     # seconds

# Extend visibility mid-processing for a long-running job
aws sqs change-message-visibility --queue-url $QUEUE_URL \
    --receipt-handle $HANDLE --visibility-timeout 300
```

---

## Decision Summary

```
Task queue, complex routing, moderate throughput  → RabbitMQ
High-throughput event streaming, replay needed     → Kafka
Already on Redis, moderate need, avoid new infra   → Redis Streams
AWS-native, pull-based durable queue                → SQS
AWS-native, pub/sub fan-out                         → SNS (+ SQS subscribers)
```

---

## Senior Tip

```
A DLQ with no alerting on its depth is a silent failure sink —
messages die there quietly and nobody notices until a customer
complains their order never processed. Wiring "DLQ depth > 0 →
page someone" is a five-minute config change that prevents a whole
class of "we just... lost that" incidents.
```

## Interview Angle

**Q: Why would a high-throughput analytics pipeline choose Kafka over RabbitMQ?**
Kafka's partitioned log model sustains far higher throughput and
supports replaying historical events (reprocessing, backfills, new
consumers joining and reading from the beginning) — capabilities
RabbitMQ's drain-on-consume queue model doesn't provide.

**Q: What happens to a message that keeps failing processing, with no DLQ configured?**
It gets redelivered indefinitely (SQS: reappears after each visibility
timeout expiry; RabbitMQ: requeued on nack) — a "poison message" like
this can block or slow processing of every message behind it, and
without a DLQ there's no automatic escape hatch or alert.

**Q: How do you decide visibility timeout for an SQS queue feeding a job that takes ~20 seconds on average but occasionally 2 minutes?**
Base it on the worst realistic case, not the average — set it to
several times the p99 processing time (e.g. 8-10 minutes), and use
`ChangeMessageVisibility` to extend it further if a specific job runs
even longer, rather than picking a timeout that risks duplicate
delivery for the slow-but-normal cases.

---

## Related

- [../14_Security/03_iam_vuln_scanning.md](../14_Security/03_iam_vuln_scanning.md) — IAM least-privilege applies to queue/topic access too
- [../../Backend_Developer/01_Year3-4_Mid/07_Kafka/](../../Backend_Developer/01_Year3-4_Mid/07_Kafka/) — app-level Kafka producer/consumer code
- [../../Backend_Developer/01_Year3-4_Mid/08_RabbitMQ/](../../Backend_Developer/01_Year3-4_Mid/08_RabbitMQ/) — app-level RabbitMQ usage
