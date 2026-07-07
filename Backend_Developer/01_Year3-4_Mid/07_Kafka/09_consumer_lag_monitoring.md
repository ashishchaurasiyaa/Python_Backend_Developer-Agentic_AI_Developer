# 09 — Consumer Lag Monitoring

> Lag = how far behind a consumer group is from the latest message in a partition. The single most important Kafka health metric — and the one most commonly missing from a first production deployment.

---

## Why It Matters

Consumer lag is the earliest warning sign of almost every Kafka production
problem: a slow consumer, a stuck/crashed consumer, a sudden traffic spike
outpacing processing capacity, or a poison-pill message stalling a partition.
Without lag monitoring, these all present the same way to users — "data is
stale" — with no visibility into why until someone manually checks.

Senior interview: "Your event-driven pipeline's data is 20 minutes stale.
First thing you check?" → consumer lag per partition, not just "is the
consumer running."

---

## What lag actually is

```
Partition 0 log:  [msg 1][msg 2][msg 3][msg 4][msg 5][msg 6][msg 7]
                                              ↑                  ↑
                                    consumer's committed      latest offset
                                    offset (last processed)   (log end offset)

Lag = latest_offset - committed_offset = 7 - 4 = 3 messages behind
```

Lag is measured **per partition**, then usually summed/maxed across a
consumer group's partitions for an overview metric. A group with 10
partitions and lag `[0, 0, 500, 0, ...]` has ONE stuck/slow partition, not a
uniformly slow group — critical detail for diagnosis (see below).

---

## Checking lag manually (CLI, always know this cold)

```bash
kafka-consumer-groups.sh --bootstrap-server localhost:9092 \
  --describe --group order-processing-group

# Output:
# TOPIC   PARTITION  CURRENT-OFFSET  LOG-END-OFFSET  LAG   CONSUMER-ID
# orders  0           1000            1000            0     consumer-1
# orders  1           850             1350            500   consumer-2   ← stuck!
# orders  2           1200            1200            0     consumer-3
```

This single command is the fastest diagnostic in a Kafka incident — run it
before anything else when data looks stale.

---

## Programmatic monitoring (Python)

```python
from kafka import KafkaConsumer, TopicPartition

consumer = KafkaConsumer(
    bootstrap_servers="localhost:9092",
    group_id="order-processing-group",
    enable_auto_commit=False,
)

partitions = [TopicPartition("orders", p) for p in range(3)]
consumer.assign(partitions)

end_offsets = consumer.end_offsets(partitions)   # log-end-offset per partition
for tp in partitions:
    committed = consumer.committed(tp) or 0
    lag = end_offsets[tp] - committed
    print(f"partition={tp.partition} lag={lag}")
```

### Production pattern — Prometheus + Grafana (ties into existing repo coverage)

```
Burrow / kafka-lag-exporter (standalone lag-monitoring tools) or
kminion → scrape consumer-group lag → expose as Prometheus metrics →
        ↓
kafka_consumergroup_lag{group="order-processing-group", partition="1"} 500
        ↓
Grafana dashboard + Prometheus alert rule:
  ALERT HighConsumerLag
  IF kafka_consumergroup_lag > 1000 FOR 5m
```

This slots directly into the existing [05_prometheus_grafana.md](../04_DevOps/05_prometheus_grafana.md)
setup — lag is just another metric to scrape and alert on, not a separate
monitoring stack.

---

## Diagnosing WHY lag is growing (the actual interview depth)

| Symptom | Likely cause |
|---|---|
| Lag growing on ALL partitions evenly | Consumer group under-provisioned — add more consumer instances (up to partition count) |
| Lag growing on ONE partition only | Poison-pill message stuck retrying, or a hot key sending disproportionate traffic to that partition |
| Lag spikes then recovers on its own | Normal traffic burst, consumer catching up — often fine, alert on sustained lag not instantaneous spikes |
| Lag flat but non-zero forever | Consumer crashed/paused but still shows as a group member (hasn't been kicked by session timeout yet) |
| Lag suddenly appears after a deploy | New consumer code is slower per-message (e.g., added a synchronous external API call inside the processing loop) |

**Key point for "one partition only" cases:** you cannot fix this by adding
more consumer instances beyond the partition count — a partition is only
ever consumed by ONE consumer within a group at a time. The fix is either
re-keying to spread that hot entity's load, or speeding up processing of
that specific message pattern.

---

## Interview Q&A

**Q: How do you monitor Kafka consumer health in production?**
A: Per-partition consumer lag, exported via a tool like Burrow/kminion into
Prometheus, alerted on sustained (not instantaneous) lag growth in Grafana —
plus consumer group rebalance frequency, since frequent rebalances themselves
cause processing pauses that show up as lag spikes.

**Q: Lag is high on exactly one partition out of ten — what does that tell you?**
A: NOT a general under-provisioning problem (the other 9 partitions are
fine) — it's either a poison-pill message stuck retrying on that partition,
or a hot key concentrating disproportionate traffic there. Adding more
consumers won't help since only one consumer processes a given partition at
a time within a group.

**Q: Why alert on sustained lag rather than any lag > 0?**
A: Lag briefly spiking during a traffic burst and recovering on its own is
normal and expected — alerting on every non-zero blip creates alert fatigue.
Alert on lag exceeding a threshold for a sustained duration (e.g., > 1000 for
5+ minutes), which distinguishes real problems from normal burst-and-recover.

---

Related: [08_ordering_guarantees.md](08_ordering_guarantees.md) (hot-key
partitions causing lag imbalance are the same root cause as ordering
concerns — both trace back to partition-key design), [05_prometheus_grafana.md](../04_DevOps/05_prometheus_grafana.md).
