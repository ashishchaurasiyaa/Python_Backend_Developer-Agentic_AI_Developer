# 🐰 RabbitMQ

> **8 theory + 6 practical + 5 self-verifying exercises.**
> Kafka *stream* hai, RabbitMQ *work queue* hai — interview me yahi farq poocha jata hai.

---

## 🔴 Pehle yeh 3

| # | Topic | Classic question |
|---|---|---|
| [01](theory/01_basics_amqp_exchanges.md) | **AMQP + exchanges** | Direct vs fanout vs topic vs headers — kab kya |
| [02](theory/02_dlx_ttl_priority_confirms.md) | **DLX + TTL + confirms** | "Message process nahi hua to kahan jayega?" 🔥 |
| [07](theory/07_publisher_confirms_competing_consumers.md) | **Publisher confirms** | "Message publish hua ya nahi — pakka kaise?" |

---

## 📚 Poori list

| # | Theory | Practical |
|---|---|---|
| [01](theory/01_basics_amqp_exchanges.md) 🔴 | Basics, AMQP, exchange types | [`01_exchanges_all_types.py`](practical/01_exchanges_all_types.py) |
| [02](theory/02_dlx_ttl_priority_confirms.md) 🔴 | DLX, TTL, priority, confirms | [`03_retry_backoff_pattern.py`](practical/03_retry_backoff_pattern.py) |
| [03](theory/03_aiopika_fastapi_rpc.md) | aio-pika + FastAPI + RPC | [`02_aiopika_fastapi_complete.py`](practical/02_aiopika_fastapi_complete.py) |
| [04](theory/04_interview_qa_complete.md) | **Interview Q&A complete** | — |
| [05](theory/05_quorum_queues_ha.md) | Quorum queues + HA | [`05_quorum_queues_ha.py`](practical/05_quorum_queues_ha.py) |
| [06](theory/06_federation_shovel.md) | Federation + shovel | [`06_federation_shovel.py`](practical/06_federation_shovel.py) |
| [07](theory/07_publisher_confirms_competing_consumers.md) 🔴 | Publisher confirms, competing consumers | [`07_...py`](practical/07_publisher_confirms_competing_consumers.py) |
| [08](theory/08_clustering_delayed_alternate_exchange.md) | Clustering, delayed + alternate exchange | — |

---

## 🧪 Exercises — [`exercises/`](exercises/) ← self-verifying

Har exercise me **`verify.py`** hai — khud check karta hai ki tumhara code sahi hai ya nahi. Guessing nahi.

```bash
cd exercises && docker compose up -d
cd 01_fanout && python publisher.py    # ...phir: python verify.py
```

| Exercise | Kya |
|---|---|
| [01_fanout](exercises/01_fanout/) | Broadcast — sab subscribers ko message |
| [02_rpc](exercises/02_rpc/) | Request/reply over queues (correlation id) |
| [03_direct_routing](exercises/03_direct_routing/) | Routing key se selective delivery |
| [04_topic_routing](exercises/04_topic_routing/) | Wildcard patterns (`*.error`, `C2.#`) |
| [05_durability_confirms](exercises/05_durability_confirms/) | Durable queues + publisher confirms |

---

## ⚔️ Kafka vs RabbitMQ — interview ka jawab

| | RabbitMQ | Kafka |
|---|---|---|
| Model | **Smart broker**, routing logic broker me | **Dumb broker**, logic consumer me |
| Message | Consume hone pe **delete** | Log me **rehta hai** (retention), replay ho sakta hai |
| Best for | Task queues, RPC, complex routing, per-message ack | Event streaming, high throughput, multiple independent consumers |
| Ordering | Per-queue | Per-partition |

**Ek line:** *"RabbitMQ jab kaam baantna ho; Kafka jab events ka record rakhna ho."*

**Related:** [07_Kafka](../07_Kafka/README.md) · [09_Celery](../09_Celery/README.md) (RabbitMQ broker ke upar) · [DevOps messaging](../../../DevOps/16_Messaging_Systems/)
