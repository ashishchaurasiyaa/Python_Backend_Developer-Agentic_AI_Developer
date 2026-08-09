# 🌿 Celery

> **10 theory + 8 practical + 4 labs.** Har Django/FastAPI project me background jobs aate hain —
> aur har interview me "email bhejne se request block hoga?" wala sawal aata hai.

---

## 🔴 Pehle yeh 4

| # | Topic | Classic question |
|---|---|---|
| [01](theory/01_celery_basics.md) | **Basics** | Broker vs result backend, worker, task lifecycle |
| [10](theory/10_testing_idempotency.md) | **Idempotency** | "Task do baar chal gaya to?" 🔥 sabse important |
| [09](theory/09_celery_canvas_workflows.md) | **Canvas workflows** | chain / group / chord — multi-step pipelines |
| [08](theory/08_long_running_task_cancellation.md) | **Long tasks + cancellation** | "2 ghante ka task, user cancel karna chahe?" |

---

## 📚 Poori list

| # | Theory | Practical |
|---|---|---|
| [01](theory/01_celery_basics.md) 🔴 | Celery basics, broker, workers | [`01_celery_practical.py`](practical/01_celery_practical.py) |
| [02](theory/02_celery_advanced.md) | Advanced — retries, beat scheduling | — |
| [03](theory/03_celery_advanced_patterns.md) | Advanced patterns | [`02_celery_advanced_patterns.py`](practical/02_celery_advanced_patterns.py) |
| [04](theory/04_flower_prometheus_monitoring.md) | Flower + Prometheus monitoring | [`04_...py`](practical/04_flower_prometheus_monitoring.py) |
| [05](theory/05_aws_sqs_broker.md) | AWS SQS as broker | [`05_aws_sqs_broker.py`](practical/05_aws_sqs_broker.py) |
| [06](theory/06_celery_priority_queues.md) | Priority queues | [`06_...py`](practical/06_celery_priority_queues.py) |
| [07](theory/07_celery_task_routing.md) | Task routing | [`07_celery_task_routing.py`](practical/07_celery_task_routing.py) |
| [08](theory/08_long_running_task_cancellation.md) 🔴 | Long-running tasks + cancellation | [`08_...py`](practical/08_long_running_task_cancellation.py) |
| [09](theory/09_celery_canvas_workflows.md) 🔴 | Canvas — chain/group/chord | [`09_...py`](practical/09_celery_canvas_workflows.py) |
| [10](theory/10_testing_idempotency.md) 🔴 | Testing + idempotency | — |

---

## 🧪 Labs — [`labs/`](labs/)

```bash
cd labs && docker compose up -d      # broker + worker
```

4 TODO-stub labs — [labs/README.md](labs/README.md) padho.

---

## 🎯 Interview ka sabse common sawal

> *"User signup karta hai, welcome email jana hai. Tumhara endpoint kya karega?"*

1. Request me email **mat bhejo** — SMTP slow hai, request block hogi
2. Task queue me daalo → `send_welcome_email.delay(user_id)`
3. **Poora object mat bhejo, ID bhejo** — payload chhota, data fresh
4. **Idempotent banao** — task retry hoga, do email nahi jane chahiye ([10](theory/10_testing_idempotency.md))
5. Failure pe retry with backoff + DLQ
6. Guarantee chahiye? → **outbox pattern** ([04_outbox](../05_Microservices/04_outbox_event_sourcing.md)) — DB commit aur task enqueue atomic nahi hain

**Related:** [08_RabbitMQ](../08_RabbitMQ/README.md) (default broker) · [07_Kafka](../07_Kafka/README.md) · [Email/Notifications](../../00_Year0-2_Junior/12_Email_Notifications/README.md) · [Temporal](../05_Microservices/15_temporal_durable_workflows.md)
