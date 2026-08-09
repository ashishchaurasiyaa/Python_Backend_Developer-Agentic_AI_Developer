# 📨 Kafka

> **10 theory + 5 practical + 6 runnable labs** (docker-compose ke saath).
> Event-driven architecture ki reedh. System design round me "events kaise handle karoge" ka jawab yahin se.

---

## 🔴 Pehle yeh 5

| # | Topic | Classic question |
|---|---|---|
| [01](01_kafka_fundamentals.md) | **Fundamentals** | Topics, partitions, offsets, consumer groups |
| [08](08_ordering_guarantees.md) | **Ordering guarantees** | "Order events sequence me kaise rahenge?" — key → partition 🔥 |
| [05](05_exactly_once_transactions.md) | **Exactly-once** | "At-least-once vs exactly-once — sach me possible hai?" |
| [09](09_consumer_lag_monitoring.md) | **Consumer lag** | "Consumer peeche reh gaya — kaise pata, kya karoge?" |
| [10](10_schema_registry_avro.md) | **Schema Registry + Avro** | "Event schema evolve kaise karoge bina consumer tode?" |

---

## 📚 Poori list

| # | Topic | Practical |
|---|---|---|
| [01](01_kafka_fundamentals.md) 🔴 | Architecture, topics, partitions, replication | ✅ |
| [02](02_producers_consumers_python.md) | Producers/consumers in Python | ✅ |
| [03](03_kafka_streams_processing.md) | Kafka Streams processing | — |
| [04](04_kafka_connect_integration.md) | Kafka Connect + CDC | ✅ |
| [05](05_exactly_once_transactions.md) 🔴 | Exactly-once semantics, transactions | ✅ |
| [06](06_kafka_production_ops.md) | Production ops — sizing, retention, rebalancing | ✅ |
| [07](07_nats_pulsar_broker_comparison.md) | NATS vs Pulsar vs Kafka | — |
| [08](08_ordering_guarantees.md) 🔴 | Ordering guarantees | — |
| [09](09_consumer_lag_monitoring.md) 🔴 | Consumer lag monitoring | — |
| [10](10_schema_registry_avro.md) 🔴 | Schema Registry, Avro, compatibility modes | — (lab 6 me hai) |

---

## 🧪 Labs — [`labs/`](labs/) ← asli kaam yahan

```bash
cd labs && docker compose up -d          # kafka + kafka-ui
python 01_produce_consume.py
```

| Lab | Kya sikhata hai |
|---|---|
| [01_produce_consume](labs/01_produce_consume.py) | Producer/consumer basics, offsets |
| [02_consumer_groups](labs/02_consumer_groups.py) | Partition assignment, rebalancing |
| [03_ordering_keys](labs/03_ordering_keys.py) | Key → partition, per-key ordering |
| [04_manual_commit_redelivery](labs/04_manual_commit_redelivery.py) | At-least-once, crash → redelivery |
| [05_consumer_lag](labs/05_consumer_lag.py) | Lag measure karna |
| [06_schema_registry_evolution](labs/06_schema_registry_evolution.py) | Avro + compatibility modes |

> **Lab 6 ko Schema Registry chahiye** — extra overlay se chalao:
> ```bash
> docker compose -f docker-compose.yml -f docker-compose.schema-registry.yml up -d
> ```
> Yeh overlay broker ke listeners bhi theek karta hai (container-internal clients ke liye) — file ke comments padho, wo khud ek interview answer hai.

**Related:** [08_RabbitMQ](../08_RabbitMQ/README.md) (kab kya chuno) · [09_Celery](../09_Celery/README.md) · [05_Microservices](../05_Microservices/README.md) · [DevOps messaging](../../../DevOps/16_Messaging_Systems/)
