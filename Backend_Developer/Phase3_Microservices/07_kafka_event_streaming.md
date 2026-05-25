# Kafka + Event Streaming — Topics, Partitions, Consumer Groups, Schema Registry

## Quick Concepts

**WHAT:**
- **Apache Kafka** = Distributed event streaming platform
- **Topic** = Named stream of events (like a queue)
- **Partition** = Topic split into ordered logs (parallelism)
- **Consumer Group** = Set of consumers sharing topic load
- **Producer** = Writes events to topic
- **Consumer** = Reads events from topic
- **Broker** = Kafka server (node in cluster)
- **Schema Registry** = Manages event schemas (Avro/Protobuf/JSON)
- **Connect** = Kafka's integration framework (DB → Kafka → DB)

**WHY Kafka:**
- ✅ Massive scale (millions msg/sec)
- ✅ Durable (events persisted to disk)
- ✅ Replayable (consumer can re-read)
- ✅ Multiple consumers per topic
- ✅ Event sourcing-friendly
- ❌ Operational complexity
- ❌ Higher latency than RabbitMQ (10ms vs 1ms)

**HOW Kafka architecture:**

```
                    ┌─────────────────────┐
                    │   Producer (app)    │
                    └──────────┬──────────┘
                               │ publish
                               ▼
        ┌──────────────────────────────────────────┐
        │           Kafka Cluster                   │
        │  ┌─────────┐  ┌─────────┐  ┌─────────┐  │
        │  │Broker 1 │  │Broker 2 │  │Broker 3 │  │
        │  └─────────┘  └─────────┘  └─────────┘  │
        │                                          │
        │  Topic: orders                           │
        │  ├─ Partition 0 (on broker 1, replica 2) │
        │  ├─ Partition 1 (on broker 2, replica 3) │
        │  └─ Partition 2 (on broker 3, replica 1) │
        └──────────────┬───────────────────────────┘
                       │ subscribe
                ┌──────┴──────┐
                ▼             ▼
        ┌──────────┐    ┌──────────┐
        │Consumer 1│    │Consumer 2│  (same group)
        │ (Part 0) │    │ (Part 1) │
        └──────────┘    └──────────┘
```

---

## Interview Questions & Answers

### Q1: Kafka vs RabbitMQ vs SQS — kab kya use karein?

**Answer:**

**WHAT — Architecture differences:**

| Feature | Kafka | RabbitMQ | AWS SQS |
|---|---|---|---|
| **Model** | Log-based | Queue-based | Queue-based |
| **Persistence** | Disk (always) | Optional | 14 days max |
| **Throughput** | Very high (1M+ msg/s) | High (50K msg/s) | High (managed) |
| **Latency** | ~10ms | ~1ms | ~10ms |
| **Replay** | ✅ Yes (re-read) | ❌ No | ❌ No |
| **Multiple consumers** | ✅ Yes | Via fanout exchange | One per message |
| **Ordering** | Per partition | Per queue | FIFO queues |
| **Routing** | Topic-based | Complex (headers, topic, fanout) | Topic-based |
| **Ops** | Complex | Moderate | None (managed) |
| **Best for** | Event streaming, analytics | Task queues, RPC | AWS-native, simple |

**WHEN to use which:**

```
Use Kafka when:
- High volume (>10K msg/s)
- Event sourcing
- Multiple consumers need same events
- Need replay capability
- Stream processing (real-time analytics)
- Log aggregation

Use RabbitMQ when:
- Complex routing
- Task queues (Celery)
- Lower volume (<10K msg/s)
- Lower latency needed
- RPC patterns

Use SQS when:
- AWS-native
- Want zero ops
- Decoupling services
- Simple queue semantics
```

---

### Q2: Topics, Partitions, Replication — kya hota hai?

**Answer:**

**WHAT:**
- **Topic** = Named stream (e.g., "orders", "user-events")
- **Partition** = Topic split into independent ordered logs
- **Replication factor** = Copies of each partition (HA)

**WHY partitions:**
- Parallelism (consumers can process in parallel)
- Scalability (split data across brokers)
- Ordering (within partition only — NOT globally)

**HOW — Create topic:**

```bash
# Create topic with 6 partitions, replication factor 3
kafka-topics --create \
  --bootstrap-server localhost:9092 \
  --topic orders \
  --partitions 6 \
  --replication-factor 3

# Describe topic
kafka-topics --describe --bootstrap-server localhost:9092 --topic orders
# Output:
# Topic: orders  PartitionCount: 6  ReplicationFactor: 3
#   Topic: orders  Partition: 0  Leader: 1  Replicas: 1,2,3  Isr: 1,2,3
#   Topic: orders  Partition: 1  Leader: 2  Replicas: 2,3,1  Isr: 2,3,1
#   ...
```

**HOW — Partition strategy:**

```python
# Producer chooses partition based on KEY
# Same key → same partition → ordering guaranteed for that key

# Option 1: Auto (hash of key)
producer.send("orders", key=b"customer-123", value=b"order data")
# All events for customer-123 go to same partition

# Option 2: Explicit partition number
producer.send("orders", value=b"data", partition=0)

# Option 3: Random (no key)
producer.send("orders", value=b"data")
# Round-robin across partitions
```

**Critical: Choosing partition count**
- Too few: bottleneck
- Too many: overhead
- Rule: 2-3x number of consumers
- Hard to increase later (rebalances ordering)

---

### Q3: Producer patterns — at-least-once, exactly-once?

**Answer:**

**WHAT:** Delivery semantics for producer.

**HOW — At-most-once (fastest, can lose):**

```python
from kafka import KafkaProducer

producer = KafkaProducer(
    bootstrap_servers=['kafka:9092'],
    acks=0,                    # ⭐ Don't wait for confirmation
    retries=0,                 # No retries
)

producer.send("events", b"data")
# If broker down → message lost
# But: fastest, lowest latency
```

**HOW — At-least-once (default):**

```python
producer = KafkaProducer(
    bootstrap_servers=['kafka:9092'],
    acks='all',                # ⭐ Wait for ALL replicas
    retries=10,                # Retry on failure
    max_in_flight_requests_per_connection=5,
)

# Might cause DUPLICATES if retry succeeds but original also delivered
producer.send("events", b"data")
```

**HOW — Exactly-once (idempotent + transactional):**

```python
producer = KafkaProducer(
    bootstrap_servers=['kafka:9092'],
    acks='all',
    enable_idempotence=True,           # ⭐ Dedup on producer side
    max_in_flight_requests_per_connection=5,
    retries=2147483647,                 # Effectively infinite
    transactional_id='order-service-1',  # ⭐ For transactions
)

producer.init_transactions()

try:
    producer.begin_transaction()

    # Multiple sends in transaction
    producer.send("orders", b"order-1")
    producer.send("order-events", b"order-created")
    producer.send("audit", b"audit-log")

    # All commit together OR all rollback
    producer.commit_transaction()
except KafkaError:
    producer.abort_transaction()
```

**Trade-offs:**

| Semantic | Latency | Throughput | Use Case |
|---|---|---|---|
| At-most-once | Lowest | Highest | Metrics, logs |
| At-least-once | Medium | High | Most apps |
| Exactly-once | Higher | Lower | Financial, billing |

---

### Q4: Consumer groups — load balancing + scaling?

**Answer:**

**WHAT:** Group of consumers sharing topic load.

**WHY:**
- Multiple consumers process partitions in parallel
- Auto rebalance when consumers join/leave
- Each partition assigned to ONE consumer in group

**HOW — Rebalancing:**

```
Topic: orders (6 partitions)

Consumer Group "order-processors"
- Consumer 1: assigned partitions [0, 1]
- Consumer 2: assigned partitions [2, 3]
- Consumer 3: assigned partitions [4, 5]

Add Consumer 4 → rebalance:
- Consumer 1: [0, 1]
- Consumer 2: [2]
- Consumer 3: [3, 4]
- Consumer 4: [5]
(Brief pause during rebalance — consumers stop)
```

**HOW — Python consumer:**

```python
from kafka import KafkaConsumer
import json

consumer = KafkaConsumer(
    'orders',                                  # Topic
    bootstrap_servers=['kafka:9092'],
    group_id='order-processors',               # ⭐ Consumer group
    auto_offset_reset='earliest',              # Where to start (earliest|latest)
    enable_auto_commit=False,                  # ⭐ Manual commit for at-least-once
    value_deserializer=lambda v: json.loads(v.decode('utf-8')),
    max_poll_records=100,                      # Batch size
)

for message in consumer:
    try:
        # Process message
        order = message.value
        print(f"Topic: {message.topic}, Partition: {message.partition}, "
              f"Offset: {message.offset}, Order: {order['id']}")

        await process_order(order)

        # ⭐ Manually commit offset AFTER successful processing
        consumer.commit()
    except Exception as e:
        # Don't commit → message will be redelivered
        print(f"Error processing {message.offset}: {e}")
```

**HOW — Critical settings:**

| Setting | Description | Production |
|---|---|---|
| `group_id` | Consumer group name | Required, unique per service |
| `enable_auto_commit` | Auto commit offsets | `False` for safety |
| `auto_offset_reset` | Where to start | `earliest` for new, `latest` for active |
| `max_poll_records` | Batch size per poll | 100-1000 |
| `max_poll_interval_ms` | Max time between polls | 300000 (5 min) |
| `session_timeout_ms` | Heartbeat timeout | 30000 (30 sec) |
| `fetch_min_bytes` | Min batch size | 1024 (1 KB) |

---

### Q5: Schema Registry — Avro vs Protobuf vs JSON?

**Answer:**

**WHAT:** Centralized schema management for Kafka events.

**WHY:**
- Without: producer changes break consumers
- Schemas evolve, need versioning
- Compatibility checks (backward, forward)

**HOW — Confluent Schema Registry:**

```bash
# Install (Docker)
docker run -d --name schema-registry \
  -p 8081:8081 \
  -e SCHEMA_REGISTRY_HOST_NAME=localhost \
  -e SCHEMA_REGISTRY_KAFKASTORE_BOOTSTRAP_SERVERS=PLAINTEXT://kafka:9092 \
  confluentinc/cp-schema-registry:latest

# Register schema
curl -X POST http://localhost:8081/subjects/orders-value/versions \
  -H "Content-Type: application/vnd.schemaregistry.v1+json" \
  -d '{
    "schema": "{\"type\":\"record\",\"name\":\"Order\",\"fields\":[{\"name\":\"id\",\"type\":\"string\"},{\"name\":\"amount\",\"type\":\"double\"}]}"
  }'
```

**HOW — Avro vs Protobuf vs JSON:**

| Format | Size | Speed | Schema Required | Use Case |
|---|---|---|---|---|
| **JSON** | Largest | Slow | No | Quick prototyping |
| **Avro** | Small | Fast | Yes (Schema Registry) | Confluent standard |
| **Protobuf** | Smallest | Fastest | Yes | Polyglot, gRPC users |

**HOW — Avro producer (Python):**

```python
# pip install confluent-kafka[avro]

from confluent_kafka import Producer
from confluent_kafka.schema_registry import SchemaRegistryClient
from confluent_kafka.schema_registry.avro import AvroSerializer

schema_registry_conf = {'url': 'http://schema-registry:8081'}
schema_registry_client = SchemaRegistryClient(schema_registry_conf)

# Schema (.avsc)
order_schema_str = """
{
  "type": "record",
  "name": "Order",
  "namespace": "com.example",
  "fields": [
    {"name": "id", "type": "string"},
    {"name": "user_id", "type": "long"},
    {"name": "amount", "type": "double"},
    {"name": "currency", "type": "string", "default": "USD"},
    {"name": "created_at", "type": "long", "logicalType": "timestamp-millis"}
  ]
}
"""

avro_serializer = AvroSerializer(
    schema_registry_client,
    order_schema_str,
)

producer = Producer({'bootstrap.servers': 'kafka:9092'})

# Send
order = {
    "id": "order-123",
    "user_id": 42,
    "amount": 99.99,
    "currency": "USD",
    "created_at": int(time.time() * 1000),
}

producer.produce(
    topic='orders',
    key=order['id'].encode(),
    value=avro_serializer(order, SerializationContext('orders', MessageField.VALUE))
)
producer.flush()
```

**HOW — Schema evolution rules:**

```
BACKWARD compatible (default, recommended):
- Old consumers can read new producer messages
- Allowed: ADD optional field (with default), REMOVE optional field
- Not allowed: REMOVE required field, CHANGE type

FORWARD compatible:
- New consumers can read old producer messages
- Allowed: ADD required field (consumers ignore), REMOVE optional field
- Not allowed: CHANGE type

FULL compatible:
- Both backward and forward
- Most restrictive

NONE:
- No compatibility check (dangerous!)
```

---

### Q6: Producer idempotence + transactional patterns?

**Answer:**

**HOW — Idempotent producer (no duplicate within partition):**

```python
producer = KafkaProducer(
    bootstrap_servers=['kafka:9092'],
    enable_idempotence=True,    # ⭐ Producer assigns sequence number
    acks='all',
    max_in_flight_requests_per_connection=5,
    retries=2147483647,
)

# Even if retry, broker dedupes by (producer_id, partition, sequence_number)
```

**HOW — Transactional producer (cross-partition atomicity):**

```python
producer = KafkaProducer(
    bootstrap_servers=['kafka:9092'],
    enable_idempotence=True,
    transactional_id='order-service-tx-1',   # ⭐ Unique per producer instance
    acks='all',
)

producer.init_transactions()

# Atomic write across multiple topics/partitions
try:
    producer.begin_transaction()

    # All in same transaction
    producer.send('orders', key=b'order-1', value=order_data)
    producer.send('inventory', key=b'product-1', value=inventory_update)
    producer.send('audit', key=b'event-1', value=audit_log)

    producer.commit_transaction()    # ⭐ All commit OR all rollback
except Exception:
    producer.abort_transaction()
```

**HOW — Read-process-write pattern (KStreams-style):**

```python
# Common: read from topic A → process → write to topic B
# Need: exactly-once across consume + produce

consumer = KafkaConsumer(
    'input-topic',
    group_id='processor',
    enable_auto_commit=False,
    isolation_level='read_committed',   # ⭐ Skip uncommitted transactional writes
)

producer = KafkaProducer(
    enable_idempotence=True,
    transactional_id='processor-tx',
)
producer.init_transactions()

for msg in consumer:
    try:
        producer.begin_transaction()

        # Transform
        result = transform(msg.value)

        # Write to output
        producer.send('output-topic', value=result)

        # Commit consumer offsets WITHIN the transaction
        producer.send_offsets_to_transaction(
            {msg.partition: msg.offset + 1},
            consumer.config['group_id']
        )

        producer.commit_transaction()
    except Exception:
        producer.abort_transaction()
```

---

### Q7: Kafka Streams vs ksqlDB — stream processing?

**Answer:**

**WHAT:**
- **Kafka Streams** = Java/Scala library for stream processing
- **ksqlDB** = SQL interface for Kafka Streams
- **Faust / Bytewax** = Python alternatives (less mature)

**WHY for stream processing:**
- Real-time analytics
- Stateful aggregations
- Joins between streams
- Windowing

**HOW — ksqlDB example:**

```sql
-- Define stream from Kafka topic
CREATE STREAM orders (
    id STRING,
    user_id BIGINT,
    amount DOUBLE,
    created_at BIGINT
) WITH (
    KAFKA_TOPIC='orders',
    VALUE_FORMAT='JSON'
);

-- Aggregate: hourly revenue
CREATE TABLE hourly_revenue AS
    SELECT
        TIMESTAMPTOSTRING(WINDOWSTART, 'yyyy-MM-dd HH:00:00') AS hour,
        SUM(amount) AS total_revenue,
        COUNT(*) AS order_count
    FROM orders
    WINDOW TUMBLING (SIZE 1 HOUR)
    GROUP BY 1;

-- Real-time materialized view
SELECT * FROM hourly_revenue EMIT CHANGES;

-- Join streams
CREATE STREAM enriched_orders AS
    SELECT o.id, o.amount, u.name, u.email
    FROM orders o
    LEFT JOIN users_table u ON o.user_id = u.id;
```

**HOW — Faust (Python alternative):**

```python
# pip install faust-streaming

import faust

app = faust.App(
    'order-processor',
    broker='kafka://localhost:9092',
    store='rocksdb://',
)

class Order(faust.Record):
    id: str
    user_id: int
    amount: float

orders_topic = app.topic('orders', value_type=Order)

# Stateful aggregation
revenue_by_user = app.Table(
    'revenue_by_user',
    default=float,
    partitions=4,
)

@app.agent(orders_topic)
async def process_orders(orders):
    async for order in orders:
        revenue_by_user[str(order.user_id)] += order.amount
        print(f"User {order.user_id} total: ${revenue_by_user[str(order.user_id)]}")

# Run
# faust -A myapp worker
```

---

### Q8: CDC (Change Data Capture) with Debezium?

**Answer:**

**WHAT:** Capture database changes as events in Kafka.

**WHY:**
- Sync DB → Kafka (event sourcing from existing DB)
- Avoid dual-write problem (outbox pattern)
- Real-time replication
- Microservices migration (Strangler Fig)

**HOW — Debezium architecture:**

```
┌─────────────┐
│ PostgreSQL  │
│  (source)   │
└──────┬──────┘
       │ WAL (Write-Ahead Log)
       ↓
┌─────────────────┐
│ Debezium        │  Reads WAL, converts to Kafka events
│ Connector       │
└──────┬──────────┘
       │
       ↓
┌─────────────────────────────────────┐
│ Kafka Topics                         │
│ ├─ db.public.users                  │
│ ├─ db.public.orders                 │
│ └─ db.public.payments               │
└──────┬──────────────────────────────┘
       │
       ↓
┌─────────────────┐
│ Consumers       │
│ (microservices) │
└─────────────────┘
```

**HOW — Setup Debezium for PostgreSQL:**

```json
// Debezium connector config
{
  "name": "postgres-orders-connector",
  "config": {
    "connector.class": "io.debezium.connector.postgresql.PostgresConnector",
    "database.hostname": "postgres",
    "database.port": "5432",
    "database.user": "debezium",
    "database.password": "secret",
    "database.dbname": "myapp",
    "database.server.name": "db",
    "table.include.list": "public.orders,public.users",
    "plugin.name": "pgoutput",
    "publication.autocreate.mode": "filtered",

    // Schema Registry
    "key.converter": "io.confluent.connect.avro.AvroConverter",
    "value.converter": "io.confluent.connect.avro.AvroConverter",
    "key.converter.schema.registry.url": "http://schema-registry:8081",
    "value.converter.schema.registry.url": "http://schema-registry:8081"
  }
}
```

```python
# Sample Debezium event
{
  "before": null,              # State before change
  "after": {                   # State after change
    "id": 123,
    "user_id": 42,
    "amount": 99.99
  },
  "source": {
    "table": "orders",
    "ts_ms": 1700000000000,
    "lsn": 12345                # PostgreSQL log position
  },
  "op": "c",                   # c=create, u=update, d=delete, r=read
  "ts_ms": 1700000000000
}
```

---

## Kafka Production Checklist

```markdown
### Cluster Setup
- [ ] 3+ brokers (HA)
- [ ] Replication factor ≥ 3
- [ ] min.insync.replicas = 2
- [ ] Multi-AZ deployment
- [ ] Monitoring (Prometheus + Grafana)

### Topic Configuration
- [ ] Partition count = 2-3x consumer count
- [ ] Retention period set (7 days default)
- [ ] Compaction enabled for tables
- [ ] Schema Registry for production topics

### Producer
- [ ] enable_idempotence=True
- [ ] acks='all' for important data
- [ ] Transactional ID for cross-topic atomicity
- [ ] Error handling + retry logic
- [ ] Schema validation before send

### Consumer
- [ ] Manual offset commits (enable_auto_commit=False)
- [ ] Process AFTER commit (at-least-once)
- [ ] Idempotent processing logic
- [ ] Consumer group naming convention
- [ ] Lag monitoring alerts

### Security
- [ ] SASL/SSL authentication
- [ ] ACLs per topic
- [ ] Encrypted at rest
- [ ] Schema Registry auth

### Operations
- [ ] Kafka Manager / Conduktor UI
- [ ] Consumer lag alerts
- [ ] Disk usage alerts
- [ ] Throttling configured
- [ ] Backup strategy (MirrorMaker 2)
```

---

## Common Pitfalls

| Pitfall | Risk | Fix |
|---|---|---|
| Default partition (1) | No parallelism | 6-12 partitions to start |
| No replication | Data loss on broker fail | Replication factor 3 |
| Auto-commit consumer | Lost messages on crash | Manual commit after process |
| No schema management | Producer changes break consumers | Schema Registry + compatibility |
| Too many partitions | Overhead, slow rebalancing | 2-3x consumer count |
| Acks=0 for important data | Silent data loss | Acks=all |
| Same group across services | Wrong consumer load balancing | Unique group_id per service |
| Forget to handle errors | Stuck consumer | Try/except + DLQ |
| Synchronous send + slow consumer | Producer blocks | Use async + buffer |
| No offset reset strategy | Lost data when group new | earliest for new consumers |
