# 08 — Kafka Ordering Guarantees

> Kafka guarantees order only within a single partition — never across a whole topic. Most "why did my events arrive out of order" bugs trace back to not knowing this.

---

## Why It Matters

This is one of the most commonly misunderstood Kafka facts, and it directly
causes production bugs: a team assumes "Kafka preserves order" without the
partition qualifier, ships an event-driven feature, then sees events for the
same entity processed out of order under load.

Senior interview: "You publish `OrderCreated` then `OrderShipped` for the
same order — can the consumer ever see `OrderShipped` first?" → yes, if they
land on different partitions, or with certain producer configs even on retries.

---

## The core guarantee

```
Topic: orders (3 partitions)

Partition 0: [msg A] [msg B] [msg C]     ← order WITHIN this partition guaranteed
Partition 1: [msg D] [msg E]             ← order WITHIN this partition guaranteed
Partition 2: [msg F] [msg G] [msg H]     ← order WITHIN this partition guaranteed

NO guarantee about interleaving ACROSS partitions.
Msg D could be processed before or after msg A — Kafka gives zero ordering
promise between partitions, even on the same topic.
```

Kafka appends messages to a partition in the order the broker receives them
(a partition is literally an append-only log) — that's where the "ordering"
guarantee lives, and it goes no further than the partition boundary.

---

## The fix — key-based partitioning (this repo's existing coverage)

```python
# Same key → same partition (guaranteed, via hash(key) % partition_count)
producer.send("orders", key=order_id.encode(), value=event_data)

# ALL events for order_id=123 always land on the SAME partition,
# so they're processed in send order relative to each other.
# Different order_ids may land on different partitions — no ordering
# guarantee BETWEEN different orders, which is usually fine (they're
# independent entities anyway).
```

**The design rule to say out loud:** partition key = the entity whose event
order matters. Order events by `order_id`, user events by `user_id`, etc. —
never partition by something unrelated (like a random UUID per message) if
order matters for that entity.

---

## Where ordering STILL breaks even with correct keying

### 1. Producer retries without idempotence

```python
# WITHOUT idempotent producer: a retried send can land AFTER a later
# message that succeeded on the first try, reordering within the partition
producer = KafkaProducer(
    bootstrap_servers="localhost:9092",
    enable_idempotence=True,   # ⚠️ REQUIRED to prevent reorder-on-retry
    max_in_flight_requests_per_connection=5,  # safe up to 5 WITH idempotence
)
```

Without `enable_idempotence=True`, having `max_in_flight_requests_per_connection > 1`
means a failed-then-retried request can be acknowledged out of order relative
to requests sent after it — breaking even within-partition ordering.

### 2. Consumer-side parallel processing

```python
# BREAKS ordering — processing partition messages in a thread pool means
# msg B might finish processing before msg A even though A was consumed first
from concurrent.futures import ThreadPoolExecutor

executor = ThreadPoolExecutor(max_workers=10)
for message in consumer:
    executor.submit(process, message)   # ⚠️ no ordering guarantee anymore

# FIX — process sequentially per partition (or per key within a partition)
for message in consumer:
    process(message)   # single-threaded per partition = order preserved
```

If you need parallelism AND ordering, the standard pattern is: parallelize
**across** partitions (each partition processed by its own thread/consumer),
never **within** a partition.

### 3. Consumer group rebalancing mid-processing

A rebalance can reassign a partition to a different consumer instance
mid-stream — if the old consumer hadn't committed its offset yet, the new
owner may reprocess a message, and if your processing has side effects
without idempotency, you get duplicate/out-of-order side effects even though
Kafka itself preserved the log order correctly.

---

## Interview Q&A

**Q: Does Kafka guarantee global ordering across a topic?**
A: No — only within a single partition. A topic with N partitions has N
independent ordered logs; there's no ordering relationship between them.

**Q: How do you guarantee two events for the same entity are processed in order?**
A: Use that entity's ID as the partition key (`producer.send(topic, key=entity_id, ...)`)
so all its events hash to the same partition, combined with
`enable_idempotence=True` on the producer and single-threaded (per-partition)
consumption on the consumer side.

**Q: If ordering matters, can you still get consumer-side parallelism?**
A: Yes — parallelize ACROSS partitions (multiple consumers in a group, one
partition each), never within a partition. Ordering is only a per-partition
property, so cross-partition parallel consumption doesn't break it for any
given entity as long as that entity's events all live in one partition.

**Q: What's a subtle way ordering breaks even with correct partition keys?**
A: Producer retries without `enable_idempotence=True` — a retried message can
be appended after a later message that succeeded first, reordering the log
itself, not just consumer-side processing.

---

Related: [05_exactly_once_transactions.md](05_exactly_once_transactions.md)
(idempotent producer config lives here too — ordering and exactly-once share
the same root fix), [09_consumer_lag_monitoring.md](09_consumer_lag_monitoring.md).
