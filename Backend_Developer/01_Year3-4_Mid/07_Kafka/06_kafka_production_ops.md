# 06 — Kafka Production Operations

> Configuring, monitoring, and scaling Kafka in production. Common pitfalls and how to avoid them.

---

## Cluster Sizing

### Brokers
- **Minimum:** 3 brokers (for replication factor 3).
- **Typical:** 5-15 brokers for mid-scale.
- **Large scale:** 50-200+ brokers (LinkedIn, Netflix).

### Per-broker resources
- **CPU:** 8-16 cores.
- **RAM:** 32-64GB (page cache for hot data).
- **Disk:** NVMe SSD for high throughput; HDD for bulk archive.
- **Network:** 10 Gbps+ for production.

### Disk
- Sequential writes/reads → SSD vs HDD less critical for throughput.
- BUT for latency-sensitive consumers, SSD is critical.
- Avoid network storage (EBS, NAS) → adds latency.

---

## Topic Configuration

### Partitions
- Initial: target ~1MB/sec per partition for throughput, or to match # of consumers in largest consumer group.
- Common: 12-50 partitions per topic.
- Hard limit: too many (10K+) hurts cluster.

**Rule:** Plan partitions upfront. Increasing later is allowed but breaks key-based ordering for keys that shift.

### Replication Factor
- Production: 3.
- Critical data: keep 3, set `min.insync.replicas=2`.
- Dev: 1 (cost saving).

### Retention
- Time: `log.retention.hours=168` (7 days default).
- Size: `log.retention.bytes` (per partition cap).
- After: deleted or compacted based on `cleanup.policy`.

### Compaction
For topics that store latest-state-per-key (CDC, snapshots):
```
log.cleanup.policy=compact
```

---

## Producer Tuning

### Throughput-focused
```python
producer = AIOKafkaProducer(
    acks=1,                       # leader only
    compression_type="lz4",
    linger_ms=20,                  # batch
    batch_size=131072,             # 128KB batches
    max_in_flight_requests_per_connection=5,
)
```

### Durability-focused
```python
producer = AIOKafkaProducer(
    acks="all",
    enable_idempotence=True,
    retries=2147483647,            # max int (effectively infinite)
    max_in_flight_requests_per_connection=5,  # with idempotence, can be > 1
)
```

### Latency-focused
```python
producer = AIOKafkaProducer(
    acks=1,
    linger_ms=0,                   # no batching
    batch_size=16384,
    compression_type="none",
)
```

---

## Consumer Tuning

### Throughput
```python
consumer = AIOKafkaConsumer(
    fetch_min_bytes=51200,         # wait for 50KB before fetching
    fetch_max_wait_ms=500,
    max_partition_fetch_bytes=1048576,  # 1MB per partition
    max_poll_records=1000,
)
```

### Reliability
```python
consumer = AIOKafkaConsumer(
    enable_auto_commit=False,
    max_poll_interval_ms=300000,   # 5 min — must finish batch in this time
    session_timeout_ms=45000,
    heartbeat_interval_ms=3000,
)
```

### Latency
```python
consumer = AIOKafkaConsumer(
    fetch_min_bytes=1,
    fetch_max_wait_ms=10,
    max_poll_records=1,
)
```

---

## Monitoring Essentials

### Cluster-level metrics
- Under-replicated partitions (must be 0).
- Offline partitions (must be 0).
- Active controllers (must be 1).
- ISR shrinkage (alarming).

### Broker metrics
- CPU, disk IO, network throughput.
- JVM heap, GC pauses.
- Active connections.
- Request handler queue depth.

### Topic / Partition metrics
- Messages in/out rate.
- Bytes in/out rate.
- Partition size.
- Log end offset vs replica offsets.

### Consumer metrics
- **Lag** (most important!): how far behind partition tip.
- Commit rate.
- Records consumed/sec.
- Rebalance frequency.

### Tools
- **Prometheus + JMX exporter**: scrape JMX metrics.
- **Grafana dashboards**: pre-built ones available.
- **Confluent Control Center**: managed, paid.
- **Burrow (LinkedIn)**: consumer lag monitor.
- **kafka-ui / akhq / kowl**: web UI for cluster inspection.

---

## Consumer Lag Alerting

```promql
# Prometheus: alert if lag > 10000 for 5 minutes
kafka_consumergroup_lag > 10000
```

Lag accumulating = consumer can't keep up. Either:
- Scale up consumers.
- Optimize processing.
- Reduce producer rate.

---

## Common Production Issues

### 1. Under-replicated partitions
ISR shrunk → durability at risk.

**Causes:** broker overload, GC pauses, network issues.

**Fix:** Investigate broker, reassign partitions if persistent.

### 2. Consumer lag growing
Consumer slower than producer.

**Fix:**
- Add consumer instances (up to partition count).
- Optimize processing logic.
- Batch processing.

### 3. Rebalance storms
Consumer group keeps rebalancing → no progress.

**Cause:** `max.poll.interval.ms` too low; processing takes too long.

**Fix:** Increase, OR reduce batch size, OR move long work to async worker.

### 4. Disk full
Old data not deleted.

**Cause:** retention misconfigured, log compaction not running.

**Fix:** Check `log.retention.hours`, `cleaner` daemon health.

### 5. Hot partition
One partition gets disproportionate traffic.

**Cause:** poor key distribution.

**Fix:** Salt keys, or repartition with better key.

### 6. Producer queue full
Producer's internal buffer fills.

**Cause:** sends faster than broker accepts, or network slow.

**Fix:** Increase `buffer.memory`, reduce send rate, or scale brokers.

### 7. Coordinator failure
Consumer group offsets fail to commit.

**Cause:** the broker hosting `__consumer_offsets` partition is down.

**Fix:** Distribute load across brokers; ensure `__consumer_offsets` replicated properly.

---

## Security

### TLS encryption
```properties
ssl.keystore.location=/path/to/kafka.server.keystore.jks
ssl.keystore.password=...
ssl.truststore.location=...
listeners=SSL://:9093
security.inter.broker.protocol=SSL
```

### SASL Authentication
- **SASL/PLAIN:** username/password (use over TLS).
- **SASL/SCRAM:** stronger; default for managed services.
- **SASL/OAUTHBEARER:** OAuth2 tokens.
- **mTLS:** client cert authentication.

### Authorization (ACLs)
```bash
kafka-acls.sh --bootstrap-server localhost:9092 \
  --add --allow-principal User:alice \
  --operation Read --operation Write \
  --topic orders
```

Role-based: granular per-topic, per-consumer-group access.

### Encryption at rest
Native: Kafka doesn't encrypt disk. Use disk-level encryption (LUKS, EBS encryption).

---

## Backup & Disaster Recovery

### Cross-cluster replication
- **MirrorMaker 2**: replicate topics to another cluster.
- **Confluent Replicator**: managed mirroring.

Use for:
- Multi-region active-active.
- Disaster recovery (warm standby).
- Migrations.

### Point-in-time recovery
Combine MM2 + log compaction allows replay to any offset.

---

## Capacity Planning

### Storage
```
storage_per_day = avg_msg_size × msgs/sec × 86400
storage_total = storage_per_day × retention_days × replication_factor
```

Example: 1KB × 10K msg/sec × 7 days × 3 RF = 18.1 TB.

### Throughput
- Per broker: ~1 GB/sec read+write on tuned hardware.
- Multiple brokers scale linearly until network/disk bottleneck.

### Connections
Each producer/consumer = 1 connection per broker. 10K consumers × 5 brokers = 50K connections. Tune file descriptors:
```
ulimit -n 1048576
```

---

## Cluster Lifecycle Operations

### Adding a broker
1. Bring up new broker with same cluster.
2. Reassign partitions to include it:
   ```bash
   kafka-reassign-partitions.sh --execute --reassignment-json-file plan.json
   ```
3. Verify completion.

### Removing a broker
1. Move all its partitions to others via reassignment.
2. Verify no leadership remains.
3. Shut down.

### Rolling restart
For config changes / version upgrade:
1. One broker at a time.
2. Wait for ISR to recover after each.
3. Use `kafka-preferred-replica-election.sh` after.

---

## Topic Compaction Best Practices

For state-store topics:
```
log.cleanup.policy=compact
log.compression.type=lz4
delete.retention.ms=86400000   # 1 day for tombstones
min.cleanable.dirty.ratio=0.1   # aggressive cleaning
```

Tombstone = null value = "delete this key".

---

## KRaft Mode (No ZooKeeper)

Kafka 3.3+: KRaft (Kafka Raft) replaces ZooKeeper for metadata.

Benefits:
- Simpler deployment.
- Faster controller failover.
- Single binary, single config.

Migration: stage-by-stage rollout via documented upgrade path.

New deployments: KRaft is default.

---

## Cloud-Managed Options

| Service | Pros | Cons |
|---|---|---|
| **AWS MSK** | Native AWS, IAM auth | Limited customization |
| **Confluent Cloud** | Full-featured, multi-cloud | Expensive at scale |
| **Aiven for Kafka** | Multi-cloud, mid-priced | Smaller player |
| **WarpStream** | S3-backed (cheap) | Higher latency |
| **Redpanda Cloud** | Kafka-compatible, faster | Different internals |

Self-managed: lower cost, higher ops burden. Most teams < 100 brokers: managed is better.

---

## Cost Optimization

### Storage
- Tiered storage (Kafka 3.6+): old segments on S3/cheap storage.
- Compaction over delete-retention where applicable.
- Compression always on.

### Network
- Cross-AZ traffic is $$$. Co-locate consumers with brokers.
- MM2 between clouds is expensive.

### Broker count
- Fewer brokers, bigger machines = cheaper at low-mid scale.
- More smaller brokers = better fault isolation.

---

## Schema Evolution Guide

Use Schema Registry (Confluent or Apicurio):

### BACKWARD compatibility (default, recommended)
New schema can read old data. Safe for consumers to upgrade first.

### FORWARD
Old schema can read new data. Safe for producers to upgrade first.

### FULL
Both. Safest.

### Rules
- Add fields with defaults: safe.
- Remove fields: only if optional or default.
- Rename: NOT compatible. Add new + deprecate old.
- Change type: NOT compatible unless promoted (int → long).

---

## Audit & Compliance

- Audit logs of all admin operations.
- Topic-level data classification.
- Retention aligned with GDPR (auto-delete after period).
- Encryption at rest + in transit.
- Access logs.

---

## Common Anti-Patterns

| Anti-pattern | Why bad | Fix |
|---|---|---|
| 1 partition for all topics | No parallelism | Plan partitions per topic |
| Same group ID for unrelated services | Accidentally share workload | Unique groups |
| `acks=0` | Data loss on broker fail | acks=all in prod |
| Auto-commit in critical path | Lost messages on crash | Manual commit |
| Long-running sync work in consumer | Triggers rebalance | Offload to async / shorten |
| Storing huge messages (>1MB) | Performance + memory issues | Use S3 pointer pattern |
| No retention policy | Disk fills | Set retention always |
| Schema-less topics | Breaking changes silent | Use Schema Registry |

---

## TL;DR

- 3 brokers minimum; replication factor 3.
- Plan partitions upfront.
- Monitor: under-replicated, lag, ISR.
- Tune producers/consumers for throughput or latency, not both.
- Manual offset commit for at-least-once.
- Use KRaft (no ZooKeeper) for new clusters.
- Managed (MSK / Confluent) for most teams under 100 brokers.
- Schema Registry mandatory in any non-trivial system.
- Monitor consumer lag religiously.
