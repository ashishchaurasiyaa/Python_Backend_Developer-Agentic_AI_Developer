# RabbitMQ Quorum Queues & HA

## Why It Matters

Classic mirrored queues = deprecated in 3.13. Quorum queues = modern HA via Raft consensus:
- **Strong consistency** via Raft
- **Durable by default** (always replicated)
- **No data loss** on majority of replicas
- **Better behavior under network partition**

Senior interview: "RabbitMQ HA production setup?" → 3-node cluster + quorum queues + load balancer.

---

## Cluster Setup (3-Node)

### Erlang Cookie

All nodes share `/var/lib/rabbitmq/.erlang.cookie`:

```bash
# On all nodes, same file content
echo "shared-secret" > /var/lib/rabbitmq/.erlang.cookie
chmod 400 /var/lib/rabbitmq/.erlang.cookie
chown rabbitmq:rabbitmq /var/lib/rabbitmq/.erlang.cookie
```

### Cluster Formation

```bash
# Start RabbitMQ on all nodes
systemctl start rabbitmq-server


# On node 2 + 3, join cluster
rabbitmqctl stop_app
rabbitmqctl reset
rabbitmqctl join_cluster rabbit@node1
rabbitmqctl start_app


# Verify
rabbitmqctl cluster_status
```

### Auto-Formation (Kubernetes / Docker)

```yaml
# rabbitmq.conf
cluster_formation.peer_discovery_backend = rabbit_peer_discovery_k8s
cluster_formation.k8s.host = kubernetes.default.svc
cluster_formation.node_cleanup.only_log_warning = true
```

## Quorum Queue Declaration

```python
import pika


channel.queue_declare(
    queue='orders',
    durable=True,
    arguments={
        'x-queue-type': 'quorum',
        'x-quorum-initial-group-size': 3,    # replicas
        'x-delivery-limit': 10,               # max redeliveries
        'x-max-length-bytes': 5 * 1024 ** 3,  # 5 GB cap
        'x-max-in-memory-length': 10000,
    },
)
```

### Replica Management

```bash
# Add member
rabbitmq-queues add_member orders rabbit@node-4

# Remove member
rabbitmq-queues delete_member orders rabbit@node-4

# Check status
rabbitmq-queues quorum_status orders
```

### Quorum Queue Limits

- Multi-DC: not recommended (Raft latency)
- Per-queue memory + disk per replica
- Slower than classic queues for low-redundancy use cases

## Classic vs Quorum vs Stream

| Feature | Classic | Quorum | Stream |
|---|---|---|---|
| Replication | Manual (mirrored) | Built-in Raft | Replicated log |
| Use case | Simple work queues | HA work queues | Event streaming |
| Throughput | High | Medium-high | Very high |
| Replay | No | No | Yes |
| Deprecated | Mirrored 3.13+ | No | No |

## Lazy Queues (Huge Backlogs)

```python
channel.queue_declare(
    queue='lazy_queue',
    durable=True,
    arguments={
        'x-queue-mode': 'lazy',
    },
)
```

Lazy = messages immediately to disk. Use for:
- Large backlogs expected
- Memory constrained
- Consumer slower than producer

Trade-off: slower throughput.

## Streams (Persistent Log)

```python
channel.queue_declare(
    queue='events',
    durable=True,
    arguments={
        'x-queue-type': 'stream',
        'x-max-length-bytes': 100 * 1024 ** 3,    # 100 GB cap
        'x-stream-max-segment-size-bytes': 500 * 1024 ** 2,
    },
)
```

Replayable. Multiple consumers from different positions.

## Network Partition Handling

```ini
# rabbitmq.conf
cluster_partition_handling = pause_minority
```

**Modes:**
- `ignore` (default for old setups): each side continues — split brain risk
- `pause_minority`: minority side stops accepting messages
- `autoheal`: lose one side, heal automatically
- `pause_if_all_down`: configurable list of nodes

**Recommendation:** `pause_minority` for 3+ node clusters.

## Cluster vs Federation vs Shovel

| | Cluster | Federation | Shovel |
|---|---|---|---|
| Purpose | HA + shard same logical broker | Cross-broker, async copy | Move messages between brokers |
| Latency | Low (LAN only) | High OK | High OK |
| Use case | Single DC | Multi-DC, edge | Migration, integration |

## Performance Tuning

### Connection + Channel Limits

```ini
# rabbitmq.conf
connection_max = 10000
channel_max = 2000
```

### Memory + Disk Watermarks

```ini
vm_memory_high_watermark.relative = 0.6   # 60% of RAM
disk_free_limit.absolute = 5GB             # need 5GB free disk
```

When watermark hit, publishers blocked.

### Consumer Prefetch

```python
channel.basic_qos(prefetch_count=10)   # max 10 unacked per consumer
```

Higher prefetch = better throughput but worse load balance. 10-100 typical.

## Production HA Pattern

```
       Load Balancer (HAProxy / nginx)
              │
    ┌─────────┼─────────┐
    │         │         │
  Node1    Node2     Node3
    │         │         │
  ───── Quorum Queue ─────
```

App connects via LB. LB has all 3 nodes. Connection sticks until disconnect. App reconnects → new node.

---

## Common Pitfalls

### 1. Classic Mirrored Queues in Production

Deprecated 3.13+. Switch to quorum queues.

### 2. Even Cluster Size

```
4 nodes → ties possible
3, 5 → clear quorum
```

### 3. Cluster Across Slow Network

Raft requires low latency. Don't cluster across DCs (use Federation/Shovel).

### 4. No Prefetch Limit

Consumer grabs all messages → memory blowup or one consumer hogs everything. Always set prefetch.

### 5. No Connection Recovery

```python
# Connection drops → no auto-reconnect
connection = pika.BlockingConnection(...)
```

Use `pika.ConnectionParameters(connection_attempts=N, retry_delay=N)` or aio-pika.

### 6. Queue Mirroring Misconfiguration (classic)

Policy `ha-mode=all` on huge queue = every node holds copy = disk full.

### 7. Unbounded Queue Growth

No TTL, no max-length → memory full → publisher blocked → cascading.

```python
arguments={
    'x-max-length': 1_000_000,
    'x-message-ttl': 86400000,  # 24h
}
```

---

## Interview Q&A

**Q1:** RabbitMQ HA architecture production mein?
**A:** 3-node cluster (or 5 for higher HA) + Quorum Queues. LB in front. `pause_minority` partition handling. Federation/Shovel for cross-DC if needed. Avoid classic mirrored queues (deprecated).

**Q2:** Classic vs Quorum queues?
**A:** Classic mirrored: manual replication via policy. Deprecated in 3.13. Quorum: Raft-based, built-in replication, strong consistency, durable by default. Quorum slower in some scenarios but safer. Use quorum for all new setups.

**Q3:** Streams kab use?
**A:** When you need replay + multiple consumers + persistent log. Like Kafka-lite. Use for event sourcing, audit logs, fan-out to many slow consumers. Not for traditional work queues — use Quorum for that.

**Q4:** Lazy queue use case?
**A:** Huge backlogs expected (jobs queue up faster than consumed). Lazy stores messages on disk immediately rather than RAM → no memory blowup. Trade-off: slower throughput. For predictable, fast queues: regular (non-lazy).

**Q5:** Cluster partition handling modes?
**A:** `ignore`: each side continues — split brain risk (DON'T use). `pause_minority`: minority stops — safe for 3+ nodes. `autoheal`: bring back smallest cluster, heal. `pause_if_all_down`: pause if specific nodes down. Recommended: pause_minority.

**Q6:** Memory watermark hit hua — kya hota hai?
**A:** Publishers receive `connection.blocked` signal — they must stop publishing until cleared. Helps prevent OOM. Configure: `vm_memory_high_watermark.relative=0.6` (60% RAM). Mitigate: lazy queues, smaller messages, more consumers.

**Q7:** Replica count change?
**A:** Quorum queues: `rabbitmq-queues add_member / delete_member`. Don't go below 3 for HA. Increasing replicas = more durability + replication cost. Even number of voters allowed but odd preferred for clean quorum.

**Q8:** RabbitMQ vs Kafka — kab kya?
**A:** RabbitMQ: traditional message broker — routing patterns, RPC, fanout. Lower throughput, lower latency, more features. Kafka: persistent log streaming — high throughput, replay, multi-consumer. For < 100k msg/sec + flexible routing: RabbitMQ. For event streaming + replay: Kafka.

---

## Real-World Use Cases

### 1. Order Processing (Quorum)

3-node cluster, quorum queue `orders` with replication=3. App publishes order events. Worker consumers process. Even if 1 node fails, queue + messages safe.

### 2. Audit Stream

Stream queue `audit-events` for all app activity. Multiple consumers: real-time alert system, S3 archiver, analytics ingester. Replayable for new consumers.

### 3. Email Queue (Lazy)

Marketing emails — millions queued, sent slowly over hours. Lazy queue keeps memory low.

---

## References

- [Quorum Queues](https://www.rabbitmq.com/quorum-queues.html)
- [Cluster Formation](https://www.rabbitmq.com/cluster-formation.html)
- [Streams](https://www.rabbitmq.com/streams.html)
- [HA Best Practices](https://www.rabbitmq.com/ha.html)
