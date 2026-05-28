# Celery Task Routing — Deep Dive

> **Interview angle:** "GPU tasks chahiye GPU nodes pe. Email tasks small workers pe. Same Celery cluster mein kaise?"

---

## 1. The Routing Problem

Without routing:
- All tasks land in single queue
- All workers process everything
- Heavy task can block lightweight workers
- No specialization possible

**Solution:** Route tasks to specific queues, run specialized workers per queue.

---

## 2. Routing Mechanisms

### Mechanism 1: `task_routes` mapping (declarative)
```python
app.conf.task_routes = {
    "myapp.emails.*": {"queue": "emails"},
    "myapp.ml.train": {"queue": "gpu"},
    "myapp.heavy.*": {"queue": "cpu_intensive", "priority": 5},
}
```

### Mechanism 2: Explicit per-call
```python
my_task.apply_async(args=[1], queue="gpu", exchange="ml", routing_key="train")
```

### Mechanism 3: Class-based routers
```python
class MyRouter:
    def route_for_task(self, task, args=None, kwargs=None, **opts):
        if task == "myapp.video.encode":
            return {"queue": "gpu" if kwargs.get("hires") else "cpu"}
        if task.startswith("myapp.heavy."):
            return {"queue": "heavy"}
        return None  # default routing

app.conf.task_routes = (MyRouter(),)
```

---

## 3. RabbitMQ Exchanges + Routing Keys

For complex routing, understand AMQP topology.

### Direct Exchange (default)
- Routing key = queue name
- Simplest

### Topic Exchange (pattern matching)
```python
from kombu import Exchange, Queue

exchange = Exchange("notifications", type="topic")

queues = [
    Queue("emails",      exchange=exchange, routing_key="notif.email.*"),
    Queue("sms",         exchange=exchange, routing_key="notif.sms.*"),
    Queue("urgent_only", exchange=exchange, routing_key="notif.*.urgent"),
]
```

Routing keys: `notif.email.welcome`, `notif.sms.urgent`, etc.

`urgent_only` queue catches: `notif.email.urgent` AND `notif.sms.urgent`.

### Fanout (broadcast)
```python
broadcast_exchange = Exchange("broadcast", type="fanout")
# Ignores routing key — sends to ALL bound queues
```

Useful for cache invalidation: "tell all workers to drop cache".

### Headers Exchange (key-value matching)
```python
header_exchange = Exchange("headers_ex", type="headers")
# Match messages based on header values, not routing key
```

Rarely used — topic exchange usually sufficient.

---

## 4. Real-World Routing Setup

```python
from kombu import Queue, Exchange

# Exchanges
emails_ex   = Exchange("emails",  type="topic")
ml_ex       = Exchange("ml",       type="topic")
default_ex  = Exchange("default")

app.conf.task_queues = (
    # Email queues — topic exchange
    Queue("emails_transactional", emails_ex, routing_key="email.txn.*"),
    Queue("emails_marketing",     emails_ex, routing_key="email.mkt.*"),
    Queue("emails_critical",      emails_ex, routing_key="email.*.critical"),

    # ML queues
    Queue("ml_gpu",  ml_ex, routing_key="ml.gpu.*"),
    Queue("ml_cpu",  ml_ex, routing_key="ml.cpu.*"),

    # Default
    Queue("default", default_ex, routing_key="default"),
)

app.conf.task_routes = {
    "myapp.emails.welcome":           {"exchange": "emails", "routing_key": "email.txn.welcome"},
    "myapp.emails.alert_critical":    {"exchange": "emails", "routing_key": "email.txn.critical"},
    "myapp.emails.newsletter":        {"exchange": "emails", "routing_key": "email.mkt.newsletter"},
    "myapp.ml.train_model":           {"exchange": "ml",     "routing_key": "ml.gpu.train"},
    "myapp.ml.score_predictions":     {"exchange": "ml",     "routing_key": "ml.cpu.score"},
}
```

### Workers
```bash
# Transactional email workers
celery -A myapp worker -Q emails_transactional --concurrency=10

# Marketing (slower, rate-limited)
celery -A myapp worker -Q emails_marketing --concurrency=2

# Critical email worker (high priority)
celery -A myapp worker -Q emails_critical --concurrency=4

# GPU node (only ml_gpu)
celery -A myapp worker -Q ml_gpu --concurrency=1 -n gpu@%h

# Default
celery -A myapp worker -Q default --concurrency=8
```

---

## 5. Specialized Workers (per-queue env)

Different requirements per task type → different worker configs.

```bash
# CPU-bound — prefork (default), low concurrency
celery -A myapp worker -Q cpu_heavy --pool=prefork --concurrency=4

# I/O-bound — eventlet/gevent, high concurrency
celery -A myapp worker -Q io_heavy --pool=gevent --concurrency=100

# Memory-heavy — single process, lots of RAM
celery -A myapp worker -Q memory_heavy --concurrency=1 -n big@%h

# GPU node
CUDA_VISIBLE_DEVICES=0 celery -A myapp worker -Q gpu --concurrency=1 -n gpu@%h
```

---

## 6. Conditional Routing (dynamic)

Route based on argument value at apply time.

```python
def enqueue_image_processing(image_id, hires=False):
    if hires:
        queue = "gpu"
    elif image_size > 10_000_000:
        queue = "heavy_cpu"
    else:
        queue = "default"

    process_image.apply_async(args=[image_id], queue=queue)
```

Or via router class:
```python
class ImageRouter:
    def route_for_task(self, task, args=None, kwargs=None, **opts):
        if task != "myapp.image.process":
            return None
        if kwargs.get("hires"):
            return {"queue": "gpu"}
        if kwargs.get("size", 0) > 10_000_000:
            return {"queue": "heavy_cpu"}
        return {"queue": "default"}
```

---

## 7. Multi-Tenant Routing

Different queues per customer.

```python
class TenantRouter:
    def route_for_task(self, task, args=None, kwargs=None, **opts):
        tenant_id = kwargs.get("tenant_id") if kwargs else None
        if tenant_id:
            # Premium tenants get dedicated queue
            tenant = lookup_tenant(tenant_id)
            if tenant.tier == "enterprise":
                return {"queue": f"tenant_{tenant_id}"}
        return None
```

**Caution:** Don't create infinite queues. Map to fixed tiers.

---

## 8. Geographic Routing

```python
class GeoRouter:
    def route_for_task(self, task, args=None, kwargs=None, **opts):
        region = kwargs.get("region") if kwargs else None
        if region == "us-east-1":
            return {"queue": "tasks_us_east"}
        if region == "eu-west-1":
            return {"queue": "tasks_eu"}
        return {"queue": "tasks_global"}
```

Run workers in specific regions consuming regional queues.

---

## 9. Direct Worker Routing (avoid)

```python
my_task.apply_async(args=[1], queue="celery@hostname")
```
- Targets specific worker
- Brittle (worker hostname changes)
- Use only for debugging

---

## 10. Examining Routing Decisions

```python
# Get current routing without sending
sig = my_task.signature(args=[1], queue="custom")
print(sig.options)   # {'queue': 'custom', ...}

# Apply with explicit options
my_task.apply_async(args=[1], queue="x", exchange="y", routing_key="z")
```

### Inspect bindings
```bash
# RabbitMQ
rabbitmqctl list_bindings
rabbitmqctl list_queues name messages consumers
rabbitmqctl list_exchanges
```

---

## 11. Worker Specialization Patterns

### Pattern: ML/AI worker
```bash
celery -A myapp worker \
    -Q ml_inference \
    --pool=solo \                  # single process — GPU lock
    --concurrency=1 \
    -n ml-inference@%h
```

### Pattern: Email worker (I/O-bound)
```bash
celery -A myapp worker \
    -Q emails \
    --pool=gevent \
    --concurrency=200 \           # many concurrent I/O
    -n emails@%h
```

### Pattern: PDF generation (memory)
```bash
celery -A myapp worker \
    -Q pdf_gen \
    --max-memory-per-child=500000 \  # 500MB kill threshold
    --concurrency=2
```

### Pattern: External API (rate-limited)
```bash
celery -A myapp worker \
    -Q external_api \
    --concurrency=5 \             # limit total concurrency
    --pool=gevent
```

---

## 12. Routing + Priority Combined

```python
app.conf.task_routes = {
    "myapp.critical.payment": {
        "queue": "priority_high",
        "priority": 9,                # within priority_high queue
    },
    "myapp.bulk.newsletter": {
        "queue": "priority_low",
        "rate_limit": "100/m",
    },
}
```

---

## 13. Common Pitfalls

### Pitfall 1: Queue exists but no worker
Task sits forever. Monitor backlog.

### Pitfall 2: Typo in queue name
Task disappears (goes to default? depends on config).

### Pitfall 3: Routing config not propagated
Update broker config, restart workers. Old workers may have stale bindings.

### Pitfall 4: Too many queues
100+ queues = ops nightmare. Group related tasks.

### Pitfall 5: Per-tenant queues without limit
1M tenants = 1M queues = broker dies.

### Pitfall 6: Default exchange != queue name
Beware: default exchange has special semantics.

---

## 14. Inspecting Queue State

```python
# Programmatically check queue length
from celery import Celery

app = Celery("myapp")
inspect = app.control.inspect()

# Active tasks
print(inspect.active())     # {worker: [task1, task2]}

# Reserved (claimed but not started)
print(inspect.reserved())

# Stats
print(inspect.stats())      # broker + queue info per worker

# Queue length (RabbitMQ)
import pyrabbit2
client = pyrabbit2.Client("localhost:15672", "guest", "guest")
queue_info = client.get_queue("/", "emails")
print(queue_info["messages_ready"])
```

---

## 15. Interview Questions

**Q1: task_routes vs apply_async queue=?**
- `task_routes` declarative, central, by task name pattern
- `apply_async(queue=...)` explicit per-call, overrides task_routes

**Q2: Topic exchange use case?**
Pattern-matching routes. E.g., `email.*.urgent` matches `email.welcome.urgent` AND `email.alert.urgent`.

**Q3: Specialized worker config?**
Per-queue worker with optimal pool/concurrency. GPU=solo, I/O=gevent, CPU=prefork.

**Q4: Conditional routing?**
Router class with logic. Returns dict with queue/exchange or None for default.

**Q5: How many queues max?**
~50-100 in practice. More = ops burden. Group by purpose, not granularity.

**Q6: Routing keys vs queue names?**
Queue names = destinations. Routing keys = "address" written on message. Exchange decides delivery via key + bindings.

**Q7: Default exchange?**
Empty-string exchange. Routing key = queue name. Simplest case.

---

## 16. Best Practices

1. **Task_routes for static patterns**
2. **Apply_async queue= for explicit override**
3. **Router class for dynamic logic**
4. **Specialized workers per queue** (pool, concurrency, env vars)
5. **Topic exchange for fan-out by pattern**
6. **Don't proliferate queues** — group sensibly
7. **Monitor each queue's backlog**
8. **Document routing decisions** for the team
9. **Test routing** in CI with task fixtures
10. **Don't route by hostname** — use queues

---

## Related
- [[06_celery_priority_queues]]
- [[01_celery_basics]]
- [[05_aws_sqs_broker]]
- [[../../01_Year3-4_Mid/08_RabbitMQ/]]
