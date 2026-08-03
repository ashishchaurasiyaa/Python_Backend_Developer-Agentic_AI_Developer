# Design Distributed Message Queue (Kafka-Style) — HLD

## WHAT

Design the **broker itself** — a distributed, persistent, ordered log that producers append to and consumers read from at their own pace. This is different from *using* Kafka (see [`07_Kafka/`](../../../01_Year3-4_Mid/07_Kafka/)) — here the interviewer wants you to build Kafka's internals from first principles.

**Examples:** Kafka, Pulsar, RabbitMQ (different model), AWS Kinesis, Redpanda

---

## Requirements

### Functional
- Publish(topic, message) — durable once acked
- Subscribe(topic, consumer_group) — each group gets every message once
- Ordering guarantee within a partition
- Consumer tracks its own position (offset) and can replay
- Retention: messages kept N days regardless of consumption

### Non-Functional
- 1M messages/sec ingest, avg 1 KB each
- P99 publish latency < 20ms
- No message loss once acked (durability)
- Horizontal scalability for both throughput and storage
- At-least-once delivery baseline; exactly-once as an extension

---

## Back-of-Envelope

```
Ingest:      1M msg/sec × 1 KB = 1 GB/sec
Retention:   7 days → 1 GB/s × 86400 × 7 ≈ 600 TB (×3 replication = 1.8 PB)
Per broker:  ~20 TB usable disk → ~90 brokers for storage
Throughput:  a single disk does ~500 MB/s SEQUENTIAL writes
             → 1 GB/s needs only a handful of brokers for WRITE throughput;
             storage, not write speed, drives the node count
```

Key insight to say out loud: **sequential disk I/O is fast** (~500 MB/s) — the whole design exists to turn random-looking messaging into sequential appends.

---

## Architecture

```
 Producers                    Brokers                       Consumers
┌─────────┐      ┌────────────────────────────────┐      ┌───────────┐
│ P1      │─────►│ Broker 1                       │◄─────│ Group A   │
│ P2      │      │  topic-orders/partition-0 (L)  │      │  C1 → p0  │
└─────────┘      │  topic-orders/partition-1 (F)  │      │  C2 → p1  │
     │           ├────────────────────────────────┤      └───────────┘
     │           │ Broker 2                       │      ┌───────────┐
     └──────────►│  partition-1 (L), partition-0(F)│◄────│ Group B   │
                 ├────────────────────────────────┤      │  C1 → p0,p1│
                 │ Broker 3                       │      └───────────┘
                 │  partition-0 (F), partition-1(F)│   (each group has its
                 └────────────────────────────────┘    own offsets)
                        ▲
                 ┌──────┴───────┐
                 │ Metadata /   │  leader election, partition→broker map,
                 │ Coordinator  │  consumer group membership
                 │ (Raft quorum)│
                 └──────────────┘
   (L) = leader replica    (F) = follower replica
```

---

## Core Concepts

### 1. Partitioned Append-Only Log — the storage engine

A topic is split into **partitions**; each partition is an append-only log stored as **segment files**. Old segments are deleted whole (cheap retention — no per-message delete).

```python
import os, struct, time

class LogSegment:
    """
    One segment file of a partition. Messages are appended sequentially;
    an in-memory SPARSE index maps offset -> byte position every 4KB
    (index stays small; a lookup = index seek + short linear scan).
    """
    def __init__(self, base_offset: int, path: str):
        self.base_offset = base_offset          # offset of first message here
        self.file = open(path, "ab+")
        self.index: list[tuple[int, int]] = []  # (offset, byte_pos), sparse
        self.next_offset = base_offset
        self.bytes_since_index = 0

    def append(self, payload: bytes) -> int:
        pos = self.file.tell()
        record = struct.pack(">QIQ", self.next_offset, len(payload),
                             int(time.time() * 1000)) + payload
        self.file.write(record)                 # SEQUENTIAL write — fast path
        if self.bytes_since_index >= 4096 or not self.index:
            self.index.append((self.next_offset, pos))
            self.bytes_since_index = 0
        self.bytes_since_index += len(record)
        offset, self.next_offset = self.next_offset, self.next_offset + 1
        return offset

    def read_from(self, offset: int) -> int:
        """Find byte position to start reading a fetch at `offset`."""
        import bisect
        i = bisect.bisect_right([o for o, _ in self.index], offset) - 1
        _, pos = self.index[max(i, 0)]
        return pos   # caller scans forward from pos to exact offset
```

Why segments matter (say this in the interview):
- Retention = **delete oldest segment files**, O(1), no compaction needed
- Active segment is the only one written → all others are immutable → easy replication, page-cache friendly, zero-copy `sendfile()` to consumers

### 2. Partitioning — ordering + parallelism

```
Ordering is ONLY guaranteed within a partition.
Producer picks partition by:  hash(key) % num_partitions
→ all events for order_123 land in the same partition, in order.
→ parallelism = number of partitions (max consumers in a group that do work)
```

Choosing partition count is a real trade-off: too few = consumer parallelism capped; too many = more open files, slower leader elections, more metadata.

### 3. Replication & the acked-message contract

Each partition has 1 **leader** + N **followers**. All produce/fetch goes through the leader; followers pull from the leader like consumers.

```
ISR (In-Sync Replicas) = followers caught up within a lag threshold.

Producer ack modes:
  acks=0    fire-and-forget            (can lose data)
  acks=1    leader wrote it            (lost if leader dies before replicating)
  acks=all  all ISR members wrote it   (durable — this is the "no loss" answer)

High Watermark = highest offset replicated to ALL of ISR.
Consumers can only read UP TO the high watermark
→ a consumer never sees a message that could still be lost in a failover.
```

**Failover:** coordinator (Raft-backed metadata service — ZooKeeper's replacement in modern Kafka, i.e. KRaft) detects dead leader via heartbeats → elects a new leader **from the ISR only** → no acked data lost. See [62_Raft_Paxos_Consensus](../HLD_Theory/62_Raft_Paxos_Consensus.md).

### 4. Consumer groups & offset management

```python
class ConsumerGroupCoordinator:
    """
    Assigns partitions to consumers in a group (rebalance on join/leave/death),
    and stores committed offsets — themselves written to an internal
    compacted topic (__consumer_offsets), so offsets get the SAME durability
    machinery as data. No separate database needed.
    """
    def rebalance(self, group: str, members: list[str], partitions: list[int]):
        assignment: dict[str, list[int]] = {m: [] for m in members}
        for i, p in enumerate(sorted(partitions)):
            assignment[members[i % len(members)]].append(p)
        return assignment   # round-robin; range/sticky strategies also exist
```

- **Pull model** (consumer asks for data) not push: consumers control their own rate → no overwhelmed consumers, free replay, simple backpressure. This is a favorite interview question — see [08_ordering_guarantees](../../../01_Year3-4_Mid/07_Kafka/08_ordering_guarantees.md).
- Commit *after* processing = at-least-once (duplicates possible → consumers must be idempotent, see [51_Idempotency_Tokens](../HLD_Theory/51_Idempotency_Tokens.md)). Commit *before* = at-most-once.

### 5. Delivery semantics ladder

```
at-most-once   : commit offset before processing   (may drop)
at-least-once  : commit after processing           (may duplicate) ← default
exactly-once   : idempotent producer (dedup by producer-id + sequence number)
                 + transactional offset commit (process + commit atomically)
```

---

## Bottlenecks & Scaling

| Problem | Fix |
|---|---|
| Hot partition (one key dominates) | Better key choice, or key-salting `key:0..7` (loses per-key total order) |
| Slow consumer lags forever | Monitor consumer lag (offset gap); scale group up to partition count; beyond that, repartition |
| Rebalance storms (consumers churn) | Sticky/cooperative assignment, static membership, longer session timeouts |
| Too many partitions cluster-wide | Metadata + election cost grows — cap partitions/broker; Raft-based metadata (KRaft) scales far beyond ZooKeeper |
| Disk fills | Tiered storage: old segments to S3, brokers keep hot tail only |

---

## Interview Q&A

**Q: Why is Kafka fast despite writing everything to disk?**
A: Sequential appends (disks do ~500 MB/s sequential vs ~1 MB/s random), OS page cache serves most reads with zero application buffering, and zero-copy `sendfile()` moves bytes from page cache to socket without entering user space. The design never fights the disk — it uses it the one way it's fast.

**Q: How do you guarantee no acked message is ever lost?**
A: `acks=all` + min ISR size ≥ 2: the leader acks only after every in-sync replica has the message, consumers read only up to the high watermark, and failover elects a new leader from the ISR only. Any single-node failure then can't lose acked data.

**Q: Push vs pull — why do log-based queues pull?**
A: Pull lets each consumer control its own rate (natural backpressure), makes replay trivial (just re-fetch an old offset), and keeps the broker simple/stateless per consumer. Push is lower latency but overruns slow consumers and makes replay/fan-out hard. Long-polling closes most of the latency gap.

**Q: Queue (RabbitMQ) vs log (Kafka) — when each?**
A: RabbitMQ = smart broker, per-message ack/delete, routing exchanges, work-queue semantics — great for task distribution where each job is consumed once and thrown away. Kafka = dumb broker/smart consumer, retained ordered log, multiple independent consumer groups, replay — great for event streaming, fan-out to many systems, and event sourcing.

---

## Related
- Using Kafka (producers/consumers, exactly-once, ops) → [`07_Kafka/`](../../../01_Year3-4_Mid/07_Kafka/)
- Consensus for the metadata plane → [62_Raft_Paxos_Consensus](../HLD_Theory/62_Raft_Paxos_Consensus.md)
- Dead letter queues → [65_Dead_Letter_Queue](../HLD_Theory/65_Dead_Letter_Queue.md)
- Consumers surviving duplicates → [51_Idempotency_Tokens](../HLD_Theory/51_Idempotency_Tokens.md)
