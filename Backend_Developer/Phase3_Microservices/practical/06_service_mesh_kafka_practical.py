"""
Phase3_Microservices — Service Mesh + Kafka Practical
========================================================
Topics covered:
  1. Istio installation + sidecar injection patterns
  2. Istio mTLS configuration (STRICT mode)
  3. Istio traffic management (canary deployment)
  4. Linkerd vs Istio comparison
  5. Kafka producer patterns (idempotent, transactional)
  6. Kafka consumer groups + rebalancing
  7. Schema Registry with Avro
  8. Exactly-once semantics
  9. CDC with Debezium
  10. Kafka vs RabbitMQ vs SQS decision

Run:
  pip install kafka-python confluent-kafka
  python 06_service_mesh_kafka_practical.py
"""

import asyncio
import json
import time
import uuid
from dataclasses import dataclass
from typing import Optional

# ─────────────────────────────────────────────────────────────────────────────
# SECTION 1: Istio mTLS Configuration
# INTERVIEW: Zero-trust networking via service mesh
# ─────────────────────────────────────────────────────────────────────────────

ISTIO_MTLS_STRICT = """
# Cluster-wide STRICT mTLS
apiVersion: security.istio.io/v1beta1
kind: PeerAuthentication
metadata:
  name: default
  namespace: istio-system        # ⭐ istio-system = whole mesh
spec:
  mtls:
    mode: STRICT                  # ⭐ Modes: DISABLE | PERMISSIVE | STRICT
"""

ISTIO_AUTHORIZATION = """
# AuthorizationPolicy — RBAC at mesh level
apiVersion: security.istio.io/v1beta1
kind: AuthorizationPolicy
metadata:
  name: payment-access
  namespace: production
spec:
  selector:
    matchLabels:
      app: payment-service
  action: ALLOW
  rules:
    - from:
        - source:
            principals:
              - "cluster.local/ns/production/sa/order-service"
              - "cluster.local/ns/production/sa/admin-service"
      to:
        - operation:
            methods: ["GET", "POST"]
            paths: ["/api/payments/*"]
      when:
        - key: request.auth.claims[role]
          values: ["admin", "operator"]
"""

# ─────────────────────────────────────────────────────────────────────────────
# SECTION 2: Istio Traffic Management — Canary Deploy
# INTERVIEW: Gradual rollout pattern
# ─────────────────────────────────────────────────────────────────────────────

ISTIO_CANARY = """
# 1. DestinationRule — define subsets
apiVersion: networking.istio.io/v1beta1
kind: DestinationRule
metadata:
  name: myapp-subsets
spec:
  host: myapp
  subsets:
    - name: v1
      labels:
        version: v1
    - name: v2
      labels:
        version: v2

---
# 2. VirtualService — 90/10 traffic split
apiVersion: networking.istio.io/v1beta1
kind: VirtualService
metadata:
  name: myapp-canary
spec:
  hosts: [myapp]
  http:
    - route:
        - destination:
            host: myapp
            subset: v1
          weight: 90              # ⭐ 90% stable
        - destination:
            host: myapp
            subset: v2
          weight: 10              # ⭐ 10% canary

---
# 3. Gradual rollout (header-based)
apiVersion: networking.istio.io/v1beta1
kind: VirtualService
metadata:
  name: myapp-internal-canary
spec:
  hosts: [myapp]
  http:
    # Internal users → v2 (full canary)
    - match:
        - headers:
            x-user-type:
              exact: internal
      route:
        - destination: { host: myapp, subset: v2 }

    # Everyone else → v1
    - route:
        - destination: { host: myapp, subset: v1 }
"""

# ─────────────────────────────────────────────────────────────────────────────
# SECTION 3: Linkerd vs Istio
# ─────────────────────────────────────────────────────────────────────────────

LINKERD_VS_ISTIO = """
| Feature           | Istio              | Linkerd         |
|-------------------|--------------------|--------------------|
| Language          | Go + Envoy (C++)   | Rust            |
| Sidecar memory    | 50-100 MB          | 10-20 MB        |
| Sidecar CPU       | High               | Low             |
| Complexity        | Very high          | Moderate        |
| Learning curve    | Steep              | Gentler         |
| mTLS              | Yes                | Yes             |
| Traffic mgmt      | Advanced           | Basic           |
| Multi-cluster     | Complex            | Simpler         |
| WebAssembly       | Yes                | No              |
| Best for          | Enterprise advanced| Quick wins      |

# Linkerd install (simpler)
curl -sL https://run.linkerd.io/install | sh
linkerd install --crds | kubectl apply -f -
linkerd install | kubectl apply -f -

# Inject sidecar
kubectl annotate namespace default linkerd.io/inject=enabled
kubectl rollout restart deployment/myapp

# View dashboard
linkerd viz dashboard
"""

# ─────────────────────────────────────────────────────────────────────────────
# SECTION 4: Kafka Producer Patterns
# INTERVIEW: At-most-once, at-least-once, exactly-once
# ─────────────────────────────────────────────────────────────────────────────

class FakeKafkaProducer:
    """Simulates kafka-python KafkaProducer for demo."""

    def __init__(self, **config):
        self.config = config
        self.messages = []
        self.acks = config.get("acks", 1)
        self.enable_idempotence = config.get("enable_idempotence", False)
        self.transactional = config.get("transactional_id") is not None
        self._tx_active = False

    def send(self, topic, value, key=None):
        msg_id = uuid.uuid4()
        self.messages.append({
            "id": msg_id,
            "topic": topic,
            "key": key,
            "value": value,
            "timestamp": time.time(),
            "acks": self.acks,
            "in_transaction": self._tx_active,
        })
        return msg_id

    def init_transactions(self):
        if not self.transactional:
            raise Exception("Not transactional producer")

    def begin_transaction(self):
        self._tx_active = True

    def commit_transaction(self):
        self._tx_active = False
        print(f"  ✅ Transaction committed ({len([m for m in self.messages if m['in_transaction']])} messages)")

    def abort_transaction(self):
        self.messages = [m for m in self.messages if not m["in_transaction"]]
        self._tx_active = False
        print("  ❌ Transaction aborted")


def demo_at_most_once_producer():
    """Fast, can lose messages."""
    producer = FakeKafkaProducer(
        bootstrap_servers=['kafka:9092'],
        acks=0,           # ⭐ Don't wait for confirmation
        retries=0,        # No retries
    )
    producer.send("events", b"data")
    print("  At-most-once: fast, may lose if broker down")


def demo_at_least_once_producer():
    """Default — may duplicate on retry."""
    producer = FakeKafkaProducer(
        bootstrap_servers=['kafka:9092'],
        acks='all',           # ⭐ Wait for ALL replicas
        retries=10,
    )
    producer.send("events", b"data")
    print("  At-least-once: safer, may duplicate on retry")


def demo_exactly_once_producer():
    """Idempotent + transactional."""
    producer = FakeKafkaProducer(
        bootstrap_servers=['kafka:9092'],
        acks='all',
        enable_idempotence=True,                # ⭐ Dedup on producer side
        transactional_id='order-service-1',     # ⭐ Transactions
    )
    producer.init_transactions()

    try:
        producer.begin_transaction()
        producer.send("orders", b"order-1")
        producer.send("order-events", b"order-created")
        producer.send("audit", b"audit-log")
        producer.commit_transaction()
    except Exception:
        producer.abort_transaction()


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 5: Kafka Consumer Groups
# INTERVIEW: Load balancing + rebalancing
# ─────────────────────────────────────────────────────────────────────────────

CONSUMER_PATTERN = """
from kafka import KafkaConsumer
import json

consumer = KafkaConsumer(
    'orders',
    bootstrap_servers=['kafka:9092'],
    group_id='order-processors',               # ⭐ Consumer group
    auto_offset_reset='earliest',              # earliest | latest
    enable_auto_commit=False,                  # ⭐ Manual commit
    value_deserializer=lambda v: json.loads(v.decode('utf-8')),
    max_poll_records=100,
    max_poll_interval_ms=300000,               # 5 min between polls
    session_timeout_ms=30000,                  # 30s heartbeat timeout
)

for message in consumer:
    try:
        order = message.value
        print(f"Partition: {message.partition}, "
              f"Offset: {message.offset}, "
              f"Order: {order['id']}")

        # Process
        await process_order(order)

        # ⭐ Commit AFTER successful processing (at-least-once)
        consumer.commit()
    except Exception as e:
        # Don't commit → message will be redelivered
        print(f"Error processing {message.offset}: {e}")
"""

# ─────────────────────────────────────────────────────────────────────────────
# SECTION 6: Schema Registry with Avro
# INTERVIEW: Schema evolution management
# ─────────────────────────────────────────────────────────────────────────────

AVRO_SCHEMA = """
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

CONFLUENT_AVRO_PRODUCER = """
from confluent_kafka import Producer
from confluent_kafka.schema_registry import SchemaRegistryClient
from confluent_kafka.schema_registry.avro import AvroSerializer

schema_registry_client = SchemaRegistryClient({
    'url': 'http://schema-registry:8081'
})

avro_serializer = AvroSerializer(
    schema_registry_client,
    AVRO_SCHEMA_STR,
)

producer = Producer({'bootstrap.servers': 'kafka:9092'})

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
"""

# Schema compatibility rules
SCHEMA_COMPATIBILITY = {
    "BACKWARD": "Old consumers can read new producer messages (default, recommended)",
    "FORWARD": "New consumers can read old producer messages",
    "FULL": "Both backward and forward",
    "NONE": "No compatibility check (dangerous!)"
}

# ─────────────────────────────────────────────────────────────────────────────
# SECTION 7: Exactly-Once Read-Process-Write
# INTERVIEW: Consume from one topic, produce to another atomically
# ─────────────────────────────────────────────────────────────────────────────

EXACTLY_ONCE_PIPELINE = """
# Read from input → process → write to output
# All in single transaction (exactly-once)

consumer = KafkaConsumer(
    'input-topic',
    group_id='processor',
    enable_auto_commit=False,
    isolation_level='read_committed',   # ⭐ Skip uncommitted txn writes
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

        # Write output
        producer.send('output-topic', value=result)

        # ⭐ Commit consumer offsets WITHIN transaction
        producer.send_offsets_to_transaction(
            {msg.partition: msg.offset + 1},
            consumer.config['group_id']
        )

        producer.commit_transaction()
    except Exception:
        producer.abort_transaction()
"""

# ─────────────────────────────────────────────────────────────────────────────
# SECTION 8: CDC with Debezium
# INTERVIEW: Stream DB changes to Kafka
# ─────────────────────────────────────────────────────────────────────────────

DEBEZIUM_CONFIG = """
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

    "key.converter": "io.confluent.connect.avro.AvroConverter",
    "value.converter": "io.confluent.connect.avro.AvroConverter",
    "key.converter.schema.registry.url": "http://schema-registry:8081",
    "value.converter.schema.registry.url": "http://schema-registry:8081"
  }
}
"""

DEBEZIUM_EVENT_SHAPE = """
{
  "before": null,                  // State before change
  "after": {                        // State after change
    "id": 123,
    "user_id": 42,
    "amount": 99.99
  },
  "source": {
    "table": "orders",
    "ts_ms": 1700000000000,
    "lsn": 12345                    // PostgreSQL log position
  },
  "op": "c",                        // c=create, u=update, d=delete, r=snapshot
  "ts_ms": 1700000000000
}
"""

CDC_CONSUMER = """
from kafka import KafkaConsumer
import json

consumer = KafkaConsumer(
    'db.public.users',     # Debezium topic naming
    bootstrap_servers='kafka:9092',
    group_id='user-search-indexer',
    value_deserializer=lambda v: json.loads(v.decode('utf-8')),
)

for message in consumer:
    event = message.value
    op = event['op']
    after = event.get('after')
    before = event.get('before')

    if op == 'c':
        # New user created
        await elasticsearch.index('users', after['id'], {
            'name': after['name'],
            'email': after['email'],
        })
    elif op == 'u':
        await elasticsearch.update('users', after['id'], after)
    elif op == 'd':
        await elasticsearch.delete('users', before['id'])

    consumer.commit()
"""

# ─────────────────────────────────────────────────────────────────────────────
# SECTION 9: Kafka vs RabbitMQ vs SQS Decision
# ─────────────────────────────────────────────────────────────────────────────

MESSAGE_SYSTEM_COMPARISON = """
| Feature           | Kafka         | RabbitMQ     | AWS SQS      |
|-------------------|---------------|--------------|--------------|
| Model             | Log-based     | Queue-based  | Queue-based  |
| Persistence       | Disk (always) | Optional     | 14 days max  |
| Throughput        | 1M+ msg/s     | 50K msg/s    | High (managed)|
| Latency           | ~10ms         | ~1ms         | ~10ms        |
| Replay            | Yes           | No           | No           |
| Multiple consumers| Yes           | Fanout       | One per msg  |
| Ordering          | Per partition | Per queue    | FIFO queue   |
| Routing           | Topic-based   | Complex      | Topic-based  |
| Ops               | Complex       | Moderate     | None         |
| Best for          | Event streaming| Task queues | AWS-native   |

# Decision:
# - >10K msg/s + replay needed → Kafka
# - Complex routing + low latency → RabbitMQ
# - AWS-only + zero ops → SQS
"""

# ─────────────────────────────────────────────────────────────────────────────
# Demos
# ─────────────────────────────────────────────────────────────────────────────

def demo_kafka_producer_patterns():
    print("\n[Kafka Producer Patterns Demo]")
    print("\n  1. At-most-once:")
    demo_at_most_once_producer()

    print("\n  2. At-least-once (default):")
    demo_at_least_once_producer()

    print("\n  3. Exactly-once (idempotent + transactional):")
    demo_exactly_once_producer()


def demo_consumer_group_rebalancing():
    print("\n[Consumer Group Rebalancing Demo]")
    print("""
  Topic: orders (6 partitions)

  Consumer Group: order-processors
  Initial state (3 consumers):
    - Consumer 1: partitions [0, 1]
    - Consumer 2: partitions [2, 3]
    - Consumer 3: partitions [4, 5]

  Add Consumer 4 → REBALANCE:
    - Consumer 1: partitions [0, 1]
    - Consumer 2: partitions [2]
    - Consumer 3: partitions [3, 4]
    - Consumer 4: partitions [5]

  Brief pause during rebalance (~few seconds)
  All consumers stop consuming briefly
    """)


def demo_schema_compatibility():
    print("\n[Schema Compatibility Modes]")
    for mode, description in SCHEMA_COMPATIBILITY.items():
        print(f"\n  {mode}:")
        print(f"    {description}")

    print("\n  Examples of SAFE changes:")
    safe = [
        "Add field with default value",
        "Remove optional field",
        "Rename field (same number)",
        "Widen type (int32 → int64)",
        "Add enum value",
    ]
    for s in safe:
        print(f"    ✅ {s}")

    print("\n  Examples of BREAKING changes:")
    breaking = [
        "Remove field without reserved",
        "Change field type incompatibly",
        "Add required field (no default)",
        "Make optional field required",
    ]
    for b in breaking:
        print(f"    ❌ {b}")


def demo_message_system_decision():
    print("\n[Message System Decision Tree]")
    scenarios = [
        ("High volume event streaming (>10K msg/s)", "Kafka"),
        ("Complex routing (header-based)", "RabbitMQ"),
        ("Task queue with simple semantics", "RabbitMQ or SQS"),
        ("AWS-native, zero ops", "SQS"),
        ("Event replay capability needed", "Kafka"),
        ("Multiple consumers same events", "Kafka or RabbitMQ fanout"),
        ("Low latency (<1ms)", "RabbitMQ"),
        ("Real-time analytics (CDC, streams)", "Kafka"),
        ("Existing AWS infrastructure", "SQS"),
        ("Polyglot environment", "Kafka"),
    ]
    for scenario, recommendation in scenarios:
        print(f"  {scenario:<45} → {recommendation}")


def demo_istio_traffic_split():
    print("\n[Istio Canary Deployment Pattern]")
    print("""
  Step 1: Deploy v2 alongside v1
    - 5 replicas of v1 (stable)
    - 1 replica of v2 (canary)

  Step 2: Configure VirtualService — 90/10 split
    - 90% traffic → v1
    - 10% traffic → v2

  Step 3: Monitor v2 metrics
    - Error rate < threshold?
    - Latency p99 < threshold?
    - Custom business metrics OK?

  Step 4: Gradual increase (if healthy)
    - Day 1: 90/10
    - Day 2: 75/25
    - Day 3: 50/50
    - Day 4: 25/75
    - Day 5: 0/100 → v1 deleted

  Step 5 (if unhealthy):
    - Immediate rollback to 100/0
    - Delete v2 deployment
    - Investigate metrics + logs
    """)


# ─────────────────────────────────────────────────────────────────────────────
# Q&A
# ─────────────────────────────────────────────────────────────────────────────

QA = [
    ("When to use service mesh?",
     "10+ services + polyglot + need uniform mTLS/retry/observability.\n"
     "     Not for: small projects, single language, simple needs."),

    ("Istio vs Linkerd?",
     "Istio: feature-rich but heavy + complex (Go + Envoy)\n"
     "     Linkerd: lightweight (Rust), simpler, less features\n"
     "     Start with Linkerd if unsure."),

    ("Kafka partitions — how many?",
     "2-3x consumer count\n"
     "     Too few: bottleneck\n"
     "     Too many: overhead, slow rebalances\n"
     "     Hard to increase later (affects ordering)."),

    ("Why manual commit consumer?",
     "Auto-commit = commit BEFORE processing\n"
     "     If app crashes mid-process → message lost\n"
     "     Manual commit AFTER processing = at-least-once"),

    ("How exactly-once works?",
     "Idempotent producer (dedup by seq#)\n"
     "     + Transactional producer (atomic multi-topic)\n"
     "     + isolation_level=read_committed on consumer\n"
     "     = exactly-once across consume + produce"),

    ("Why Schema Registry?",
     "Without: producer change breaks consumers\n"
     "     Compatibility checks before schema accepted\n"
     "     Code generation for type safety"),

    ("CDC vs application events?",
     "App events: explicit (code emits), but dual-write problem\n"
     "     CDC: implicit (DB log), always consistent with DB\n"
     "     CDC for legacy migration, app events for clean separation"),

    ("Kafka vs RabbitMQ — TL;DR?",
     "Kafka: log (replay, high throughput)\n"
     "     RabbitMQ: queue (routing, low latency)\n"
     "     Event streaming → Kafka, task queue → RabbitMQ"),
]


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("SERVICE MESH + KAFKA PRACTICAL")
    print("=" * 60)

    demo_kafka_producer_patterns()
    demo_consumer_group_rebalancing()
    demo_schema_compatibility()
    demo_message_system_decision()
    demo_istio_traffic_split()

    print("\n[Service Mesh Decision]")
    print("  Need mesh?")
    print("  - 10+ services? → Yes")
    print("  - Polyglot? → Yes (mesh > library per language)")
    print("  - Need mTLS everywhere? → Yes")
    print("  - Small project (<5 services)? → No (over-engineering)")

    print("\n[Q&A Summary]")
    for q, a in QA:
        print(f"\n  Q: {q}")
        print(f"  A: {a}")

    print("\n" + "=" * 60)
    print("FILES TO KNOW:")
    print("  istio/peer-authentication.yaml  → mTLS STRICT mode")
    print("  istio/virtual-service.yaml      → traffic management")
    print("  istio/authorization-policy.yaml → RBAC at mesh")
    print("  kafka/producer.py               → idempotent + transactional")
    print("  kafka/consumer.py               → manual commits")
    print("  schemas/order.avsc              → Avro schema")
    print("  debezium/postgres-connector.json → CDC config")
    print("=" * 60)


if __name__ == "__main__":
    main()
