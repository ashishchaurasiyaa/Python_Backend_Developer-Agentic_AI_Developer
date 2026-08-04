# Kafka Labs — Runnable Exercises

> `../practical/` me production-quality **reference modules** hain (padhne ke liye). Yeh folder **chalane** ke liye hai: real broker, TODO stubs jo tum bharoge, aur har lab ka apna verification step.

## Setup (ek baar)

```bash
cd Backend_Developer/01_Year3-4_Mid/07_Kafka/labs
docker compose up -d                    # KRaft mode, no ZooKeeper
docker compose ps                       # kafka healthy hona chahiye (~20s)
pip install aiokafka                    # async client (labs isi pe hain)

# UI (optional, bahut useful): http://localhost:8080
```

Cleanup: `docker compose down -v`

## Labs

| # | Lab | Kya sikhata hai | Verify kaise |
|---|---|---|---|
| 1 | [01_produce_consume](01_produce_consume.py) | Producer/consumer basics, offsets, `auto_offset_reset` | Consumer wahi messages print kare jo produce hue |
| 2 | [02_consumer_groups](02_consumer_groups.py) | Partition assignment, parallelism, rebalancing | 3 partitions, 2 consumers → partitions baant jaayein; teesra consumer idle |
| 3 | [03_ordering_keys](03_ordering_keys.py) | Key → partition mapping, per-key ordering | Ek `order_id` ke saare events ek hi partition me, sahi order me |
| 4 | [04_manual_commit_redelivery](04_manual_commit_redelivery.py) | At-least-once, crash-before-commit → redelivery | Crash simulate karo, restart pe wahi message dobara aaye |
| 5 | [05_consumer_lag](05_consumer_lag.py) | Lag measure karna, slow consumer ka effect | Fast producer + slow consumer → lag badhta dikhe |

Har file me **TODO** blocks hain — pehle khud bharo, phir `python 0N_....py` chalao. Har lab apna verification khud print karta hai (✅/❌).

## Protocol

```
1. Lab file kholo, docstring me OBJECTIVE + TASK padho
2. TODO bharo (reference: ../practical/ aur ../0N_*.md)
3. Chalao → ✅ mile to agla lab; ❌ mile to output padho, fix karo
4. Lab ke end me "SOCH" section hota hai — usme diye sawaalon ka
   jawab bolke do. Interview me yahi poocha jaata hai, code nahi.
```

## Troubleshooting

| Problem | Fix |
|---|---|
| `NoBrokersAvailable` | `docker compose ps` — kafka healthy hai? ~20s lagta hai boot me |
| Consumer kuch receive nahi karta | `auto_offset_reset="earliest"` set hai? Naya group id use karo |
| Purane messages aate rehte hain | `docker compose down -v` (volume delete) ya naya topic naam |
| Port 9092 busy | Koi aur Kafka chal raha hai — `docker ps` check karo |

---

**Related:** [theory files](../) · [reference modules](../practical/) · [RabbitMQ exercises](../../08_RabbitMQ/exercises/) · [Celery labs](../../09_Celery/labs/)
