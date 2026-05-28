# 04 — Kafka Connect & Integration

> Connect Kafka to external systems (DBs, S3, Elasticsearch, REST APIs) without writing custom producers/consumers.

---

## What Kafka Connect Is

Standalone JVM tool (separate from Kafka brokers) that runs **connectors**:
- **Source connectors**: pull data from external systems into Kafka.
- **Sink connectors**: push Kafka data to external systems.

Hundreds of pre-built connectors. Configured via JSON, no code.

---

## Why Use Connect

Without Connect:
```python
# Write your own pipeline
async def cdc_to_kafka():
    while True:
        changes = await db.poll_changes()
        for row in changes:
            await producer.send("db_changes", value=row)
```

Brittle, error-prone, no fault-tolerance.

With Connect:
- Configure once → runs forever.
- Auto-resume on crash.
- Schema management.
- Monitoring built-in.
- Exactly-once for many connectors.

---

## Architecture

```
┌──────────────────────────────────┐
│    Kafka Connect Cluster         │
│  ┌────────┐ ┌────────┐ ┌────────┐│
│  │Worker  │ │Worker  │ │Worker  ││
│  └────────┘ └────────┘ └────────┘│
└──────┬─────────────────┬─────────┘
       │ pull/push       │ pull/push
       ▼                 ▼
   ┌────────┐         ┌────────┐
   │Postgres│         │ Kafka   │ ← cluster
   │ MySQL  │         │ topics  │
   │ S3     │         └────────┘
   └────────┘
```

Workers form a cluster; tasks distributed across them.

---

## Common Source Connectors

### Debezium (CDC — Change Data Capture)
Read DB transaction log (WAL for Postgres, binlog for MySQL) and stream changes to Kafka.

```json
{
  "name": "postgres-orders-connector",
  "config": {
    "connector.class": "io.debezium.connector.postgresql.PostgresConnector",
    "database.hostname": "postgres",
    "database.port": "5432",
    "database.user": "debezium",
    "database.password": "...",
    "database.dbname": "shop",
    "database.server.name": "shop_db",
    "table.include.list": "public.orders,public.customers",
    "plugin.name": "pgoutput"
  }
}
```

Result: every `INSERT/UPDATE/DELETE` on `orders` → message in topic `shop_db.public.orders` like:
```json
{
  "op": "u",
  "before": {"id": 1, "amount": 100},
  "after":  {"id": 1, "amount": 150},
  "ts_ms": 1700000000000
}
```

### JDBC Source
Periodic polling of any JDBC database.

```json
{
  "connector.class": "io.confluent.connect.jdbc.JdbcSourceConnector",
  "connection.url": "jdbc:mysql://mysql:3306/shop",
  "mode": "incrementing",
  "incrementing.column.name": "id",
  "topic.prefix": "shop_",
  "poll.interval.ms": "5000"
}
```

Less efficient than Debezium (polls vs log-tail).

### MongoDB Source
Stream MongoDB change streams to Kafka.

### File Source
Tail a file → Kafka topic.

### REST Source
Periodically GET an API endpoint → Kafka.

### Salesforce, ServiceNow, Zendesk
Tons of SaaS connectors.

---

## Common Sink Connectors

### Elasticsearch Sink
Index every Kafka message into Elasticsearch.

```json
{
  "connector.class": "io.confluent.connect.elasticsearch.ElasticsearchSinkConnector",
  "topics": "logs",
  "connection.url": "http://elasticsearch:9200",
  "type.name": "_doc",
  "key.ignore": "true",
  "schema.ignore": "true"
}
```

### S3 Sink
Stream to S3 in Parquet/JSON/Avro format. Used for data lake archival.

```json
{
  "connector.class": "io.confluent.connect.s3.S3SinkConnector",
  "topics": "orders",
  "s3.bucket.name": "data-lake",
  "s3.region": "us-east-1",
  "format.class": "io.confluent.connect.s3.format.parquet.ParquetFormat",
  "partitioner.class": "io.confluent.connect.storage.partitioner.TimeBasedPartitioner",
  "path.format": "'year'=YYYY/'month'=MM/'day'=dd",
  "flush.size": "10000"
}
```

### JDBC Sink
Write Kafka messages to relational DB.

### Snowflake / BigQuery / Redshift
Stream into data warehouses.

### Webhook Sink
HTTP POST each message to an external service.

---

## CDC Pattern (Most Important)

Use Debezium to convert DB changes into events:

```
App → writes to Postgres
                ↓
Debezium reads Postgres WAL
                ↓
Kafka topic: shop_db.orders
                ↓
Downstream consumers:
  - Search indexer → updates Elasticsearch
  - Cache invalidator → invalidates Redis
  - Analytics → writes to data warehouse
  - Notifications → triggers email
```

**Benefits:**
- One source of truth.
- Decoupled consumers.
- Replay capability.

---

## Schema Registry

Confluent Schema Registry: central schema management for Kafka.

```
Producer publishes message → embeds schema ID → broker stores it
Consumer reads message → fetches schema by ID → deserializes
```

### Avro/Protobuf/JSON Schema support

```python
from confluent_kafka.schema_registry import SchemaRegistryClient
from confluent_kafka.schema_registry.avro import AvroSerializer

schema = """
{
  "type": "record",
  "name": "Order",
  "fields": [
    {"name": "id", "type": "long"},
    {"name": "amount", "type": "double"}
  ]
}
"""

client = SchemaRegistryClient({"url": "http://schema-registry:8081"})
avro_serializer = AvroSerializer(client, schema, lambda o, ctx: {"id": o.id, "amount": o.amount})

producer.produce(
    topic="orders",
    value=avro_serializer(order, SerializationContext("orders", MessageField.VALUE))
)
```

### Schema evolution
Schema Registry enforces compatibility:
- BACKWARD: new schema can read old data.
- FORWARD: old schema can read new data.
- FULL: both.

Reject incompatible changes → safe schema evolution.

---

## Connect REST API

Connect cluster exposes REST API for management:

```bash
# List connectors
curl http://connect:8083/connectors

# Create connector
curl -X POST -H "Content-Type: application/json" \
  --data '{"name":"my-conn","config":{...}}' \
  http://connect:8083/connectors

# Get status
curl http://connect:8083/connectors/my-conn/status

# Pause/Resume
curl -X PUT http://connect:8083/connectors/my-conn/pause
curl -X PUT http://connect:8083/connectors/my-conn/resume

# Restart
curl -X POST http://connect:8083/connectors/my-conn/restart

# Delete
curl -X DELETE http://connect:8083/connectors/my-conn
```

GitOps: store connector config as YAML/JSON in git, apply via CI.

---

## Single Message Transforms (SMT)

In-flight transformations without writing code:

```json
"transforms": "extractKey,unwrap",
"transforms.extractKey.type": "org.apache.kafka.connect.transforms.ExtractField$Key",
"transforms.extractKey.field": "id",
"transforms.unwrap.type": "io.debezium.transforms.ExtractNewRecordState"
```

Common SMTs:
- Filter rows by predicate.
- Mask sensitive fields (`MaskField`).
- Rename fields.
- Add timestamps.
- Convert types.

---

## Dead Letter Queue (Connect)

```json
"errors.tolerance": "all",
"errors.deadletterqueue.topic.name": "dlq-my-conn",
"errors.deadletterqueue.context.headers.enable": "true"
```

Failed messages → DLQ instead of stopping the connector.

---

## Connect vs Application-Level Pipelines

| | Kafka Connect | Custom Producer/Consumer |
|---|---|---|
| Setup time | Hours (config) | Days (code) |
| Maintenance | Auto-managed | Your code |
| Flexibility | Limited to connector capabilities | Full control |
| Languages | JVM-based | Any |
| Best for | Standard integrations | Complex business logic |

**Rule:** If a connector exists, use it. If your logic is custom, write your own consumer.

---

## Strimzi & MSK (Managed Connect)

Running Connect yourself: cluster ops complexity.

### Strimzi
Kubernetes operator for Kafka + Connect.

```yaml
apiVersion: kafka.strimzi.io/v1beta2
kind: KafkaConnect
metadata:
  name: my-connect
spec:
  replicas: 3
  bootstrapServers: kafka-bootstrap:9093
  config:
    config.storage.replication.factor: 3
    offset.storage.replication.factor: 3
    status.storage.replication.factor: 3
```

Connectors as K8s `KafkaConnector` CRDs.

### Amazon MSK Connect
Managed Connect on AWS.

### Confluent Cloud Connect
Managed by Confluent.

---

## Common Pipelines

### 1. Postgres → Elasticsearch (search index)
- Debezium (PG source) → Kafka topic → Elasticsearch sink.

### 2. Microservice events → Data Lake
- Service publishes events → Kafka → S3 sink (Parquet).

### 3. Microservice → Warehouse
- App → Kafka → Snowflake sink → analytics.

### 4. MySQL → Postgres (DB migration)
- Debezium MySQL source → Kafka → JDBC PG sink.

### 5. SaaS → Internal
- Salesforce source connector → Kafka → app consumers.

---

## Monitoring

- Connector status (RUNNING, FAILED, PAUSED).
- Task-level errors.
- Lag for source connectors.
- DLQ size.
- JMX metrics (heap, GC).

Tools: Confluent Control Center, Datadog, Grafana with Kafka exporter.

---

## TL;DR

- Kafka Connect = no-code data pipelines.
- Source connectors pull data into Kafka.
- Sink connectors push data out.
- Debezium (CDC) is the most important source connector.
- Use Schema Registry for safe schema evolution.
- Run via Strimzi on K8s or managed service.
- DLQ for failed messages.
- 80% of "Kafka pipelines" should use Connect, not custom code.
