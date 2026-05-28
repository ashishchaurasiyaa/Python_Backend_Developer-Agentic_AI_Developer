# RabbitMQ Federation & Shovel

## Why It Matters

Single RabbitMQ cluster = single AZ/region. For multi-region:
- **Federation** → declarative cross-cluster replication
- **Shovel** → reliable message moving between brokers

Use cases: cross-DC DR, edge → cloud aggregation, broker migration.

Senior interview: "Multi-region RabbitMQ setup?" → not clustering across regions (too slow), use Federation or Shovel.

---

## Federation

### Federated Exchange

Messages published to upstream exchange replicated to downstream:

```
[Upstream Broker]         [Downstream Broker]
  exchange-X        →     exchange-X-fed
  (publishes)              (consumers subscribe here)
```

### Setup

```bash
# Enable plugin
rabbitmq-plugins enable rabbitmq_federation rabbitmq_federation_management


# Define upstream (on downstream broker)
rabbitmqctl set_parameter federation-upstream my-upstream \
    '{"uri":"amqp://user:pass@upstream-host:5672/%2f","expires":3600000}'


# Policy: federate exchanges matching pattern
rabbitmqctl set_policy --apply-to exchanges federate-all "events\..*" \
    '{"federation-upstream-set":"all"}'
```

### Federated Queue

Multiple downstream consumers pull from upstream queue:

```
[Upstream]
  queue-X (messages)
    ↓ federation pulls
[Downstream]
  queue-X (mirror)
  ← consumers
```

```bash
rabbitmqctl set_policy --apply-to queues federate-queue "^federated\." \
    '{"federation-upstream-set":"all"}'
```

## Shovel

### Static Shovel (Config-Based)

```ini
# rabbitmq.conf
shovel.my-shovel.source.protocol = amqp091
shovel.my-shovel.source.uri = amqp://user:pass@source-host
shovel.my-shovel.source.queue = source-queue
shovel.my-shovel.destination.protocol = amqp091
shovel.my-shovel.destination.uri = amqp://user:pass@dest-host
shovel.my-shovel.destination.exchange = dest-exchange
```

### Dynamic Shovel (Runtime API)

```bash
rabbitmqctl set_parameter shovel my-shovel \
    '{"src-uri":"amqp://...source",
      "src-queue":"source-q",
      "dest-uri":"amqp://...dest",
      "dest-exchange":"dest-ex"}'
```

```python
# Via management API
import requests

requests.put(
    'http://broker:15672/api/parameters/shovel/%2f/my-shovel',
    auth=('admin', 'admin'),
    json={
        'value': {
            'src-uri': 'amqp://...source',
            'src-queue': 'source-q',
            'dest-uri': 'amqp://...dest',
            'dest-exchange': 'dest-ex',
            'src-prefetch-count': 100,
        },
    },
)
```

### Shovel Use Cases

- **Migration**: move messages from old broker to new
- **Integration**: bridge two systems
- **Selective Forward**: send only certain queue's messages
- **Buffering**: pull from edge to central reliable broker

## Federation vs Shovel — Choose

| | Federation | Shovel |
|---|---|---|
| Setup | Plugin + upstream config | Plugin + per-route config |
| Topology | Hub-spoke implied | Point-to-point |
| Dynamic | Policy-based | Per-shovel |
| Use case | Cross-region replication | Message routing between brokers |
| Complexity | Lower | Higher (more flexible) |

**Rule of thumb:** Federation for "make exchange/queue visible across brokers". Shovel for "move messages between specific points".

## Cross-DC Patterns

### Hub-Spoke

```
        [Central Broker]
              │
   ┌──────────┼──────────┐
[Edge-1]  [Edge-2]  [Edge-3]
```

Edges publish to local broker. Federation/Shovel forwards to central. Central aggregates.

### Multi-Master with Federation

```
[Region A] ←federation→ [Region B]
```

Both can publish; both replicate. Application careful about loops (use TTL or exchange prefix).

### Disaster Recovery

```
[Primary DC]  ←shovel→  [DR DC (read-only mirror)]
```

Continuous shovel from primary to DR. On disaster, promote DR.

---

## Common Pitfalls

### 1. Federation Loops

```
A → B (federated)
B → A (federated)
→ message bounces forever
```

Use `max-hops` parameter (default 1).

### 2. Federation Lag

Latency between brokers = federation lag. For high-throughput, may need to tune `prefetch-count` higher.

### 3. Shovel Failed = Silent

Without monitoring, shovel can stop working. Use management UI / API to check status:

```bash
rabbitmqctl shovel_status
```

Or HTTP:

```
GET /api/shovels
```

### 4. Different Exchange Types Between Brokers

Federated exchange must exist with compatible type. Topic ↔ topic, fanout ↔ fanout.

### 5. Auth Across Regions

URI includes credentials → leak risk. Use vhost-specific limited credentials. SSL/TLS for transit.

### 6. No Acknowledgement Pattern

If shovel destination unreachable, messages buffer in source. Need destination-side dead-letter to detect.

---

## Interview Q&A

**Q1:** Federation aur Shovel mein difference?
**A:** Federation: declarative, policy-based, replicates exchanges/queues across brokers. Hub-spoke topology natural. Shovel: imperative, per-route configuration, moves messages from specific source to specific destination. Federation for "be everywhere", Shovel for "move from A to B".

**Q2:** Multi-region RabbitMQ pattern?
**A:** Don't cluster across regions (RabbitMQ clustering requires LAN). Use Federation: each region has own cluster, Federation links exchanges. Or hub-spoke with Shovel from edge brokers to central. SSL for transit. Watch for replication lag.

**Q3:** Federation loops kaise prevent?
**A:** Each message carries hop count. `max-hops` parameter (default 1) — message dropped after N hops. So A→B works, but B→A→B→A loop stops at hop 2. Design topology so no cycles.

**Q4:** Shovel failure detection?
**A:** Management API: `GET /api/shovels` shows status per shovel. Alert on state != 'running' or `last_changed` > N seconds. Prometheus exporter: `rabbitmq_shovel_state` metric. Also queue length on source — if growing, shovel may be stuck.

**Q5:** Federation security?
**A:** URIs contain credentials — use vhost-specific limited user. SSL/TLS between brokers. Mutual TLS for stricter. Audit federation links via management UI. Don't federate sensitive data across untrusted networks.

**Q6:** When NOT to use Federation/Shovel?
**A:** Within same DC: use clustering instead (lower latency, stronger consistency). For event streaming high-throughput: consider Kafka MirrorMaker or native streaming. For simple migration: Shovel works; for ongoing cross-DC sync: Federation cleaner.

**Q7:** Shovel vs application-level forwarding?
**A:** Shovel: broker-level, no app code, durable in face of broker restart, configurable rate. App-level: more flexible (transform, filter), language-specific code. Shovel preferred for raw message movement; app code for transformation/business logic.

**Q8:** Federation prefetch tuning?
**A:** `prefetch-count` controls how many messages federated link pulls at once. Higher = better throughput, more memory used on downstream. Default 1000. Tune based on observed lag + memory pressure.

---

## Real-World Use Cases

### 1. Edge → Cloud Aggregation

IoT devices publish to nearest regional broker (lower latency). Federation streams to central broker for processing.

### 2. Migration Between Versions

```
[Old RabbitMQ 3.7]  ──shovel──→  [New RabbitMQ 3.13]
```

Drain old, start using new without app changes.

### 3. Multi-DC DR

```
[Primary DC]  ──shovel/federation──→  [DR DC]
```

Continuous mirroring. On disaster, app switches to DR cluster.

### 4. Subscriber Pattern Across Apps

App A publishes to its exchange. App B (different cluster) needs subset. Federation policy on App B's broker pulls App A's events.

---

## References

- [RabbitMQ Federation](https://www.rabbitmq.com/federation.html)
- [Shovel Plugin](https://www.rabbitmq.com/shovel.html)
- [Distributed Messaging](https://www.rabbitmq.com/distributed.html)
- "RabbitMQ in Depth" — Distributed chapter
