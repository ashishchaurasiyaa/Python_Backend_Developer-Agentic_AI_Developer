# Celery Priority Queues

> **Interview angle:** "VIP user ka email instantly bhejna, but bulk newsletter slow chal sakti. Same Celery setup mein kaise?"

---

## 1. Why Priority Queues?

In a single FIFO queue, all tasks treated equal:
- VIP payment confirmation → enters queue
- 100K bulk newsletter emails → enter queue first
- VIP waits behind newsletter = bad UX

**Solution:** Process VIP/high-priority before low-priority tasks.

---

## 2. Two Approaches

### Approach A: Multiple Queues (recommended)
Different queues for different priorities. Workers consume in order.

### Approach B: RabbitMQ Native Priority Queues
Single queue with priority field on messages.

**Multi-queue is more flexible and broker-agnostic.**

---

## 3. Approach A: Multiple Queues

### Define queues
```python
from kombu import Queue

app.conf.task_queues = (
    Queue("priority_high", routing_key="priority_high"),
    Queue("default",       routing_key="default"),
    Queue("priority_low",  routing_key="priority_low"),
)

app.conf.task_default_queue = "default"
app.conf.task_default_exchange = "tasks"
app.conf.task_default_routing_key = "default"
```

### Route tasks
```python
app.conf.task_routes = {
    "myapp.payments.confirm_payment": {"queue": "priority_high"},
    "myapp.emails.send_welcome": {"queue": "default"},
    "myapp.bulk.newsletter": {"queue": "priority_low"},
}

# OR explicit per-call
my_task.apply_async(args=[1], queue="priority_high")
```

### Workers consume in order
```bash
# Worker reads priority_high first, falls back to default, then low
celery -A myapp worker -Q priority_high,default,priority_low
```

**`-Q` order matters.** Worker greedily reads from first non-empty queue.

### Dedicated workers per queue
```bash
# High-priority worker (always available)
celery -A myapp worker -Q priority_high -n vip@%h --concurrency=4

# Default workers
celery -A myapp worker -Q default --concurrency=10

# Low-priority (limited resources)
celery -A myapp worker -Q priority_low -n bulk@%h --concurrency=2
```

Best practice: **dedicated workers for high-priority** so they're never starved.

---

## 4. Approach B: RabbitMQ Native Priority

RabbitMQ supports per-message priority within ONE queue (0-255).

### Setup
```python
from kombu import Queue, Exchange

app.conf.task_queues = [
    Queue(
        "default",
        Exchange("default"),
        routing_key="default",
        queue_arguments={"x-max-priority": 10},     # max priority value
    ),
]

# Apply task with priority
my_task.apply_async(args=[1], priority=9)    # high
my_task.apply_async(args=[2], priority=1)    # low
```

### Limitations
- **RabbitMQ only** (Redis/SQS don't support)
- Memory overhead per message (modest)
- All workers consume same queue (can't dedicate)
- Priority doesn't preempt — current task finishes first
- **Max priority 10 recommended** (255 max but performance degrades)

---

## 5. Comparison

| Aspect | Multi-Queue | RabbitMQ Priority |
|---|---|---|
| Broker support | All | RabbitMQ only |
| Dedicated workers | ✅ | ❌ |
| Granularity | Coarse (N queues) | Fine (0-10 levels) |
| Operations | More queues to manage | Single queue |
| Best for | Different worker pools | Same workers, varying urgency |

**Most production: Multi-queue approach.**

---

## 6. Worker Concurrency Strategies

### Strategy 1: Separate pools per priority
```bash
# Critical pool — never starved
celery -A myapp worker -Q priority_high --concurrency=4 -n vip@%h

# Bulk pool — limited
celery -A myapp worker -Q priority_low --concurrency=2 -n bulk@%h
```

### Strategy 2: Mixed pools with priority order
```bash
# Each worker tries high first, then default
celery -A myapp worker -Q priority_high,default --concurrency=10
```

**Problem:** if high-priority queue surges, workers ignore default → starvation.

### Strategy 3: Weighted (using prefetch + fair scheduling)
Workers process from multiple queues but bias toward high.

---

## 7. Avoiding Priority Inversion

**Priority inversion:** Low-priority task holds resource needed by high-priority.

### Example
```python
# Low-priority task holds Redis lock for 5 min
@app.task(queue="priority_low")
def slow_cleanup():
    with redis_lock("cleanup"):
        time.sleep(300)

# High-priority task waits for same lock
@app.task(queue="priority_high")
def urgent_with_lock():
    with redis_lock("cleanup"):    # waits!
        do_urgent_work()
```

**Mitigations:**
- Don't share locks between priority tiers
- Use timeouts on locks
- Detect long-holders + interrupt

---

## 8. Real-World Priority Tiers

### E-commerce platform
```python
task_routes = {
    "payments.charge_card":          {"queue": "critical"},   # P0
    "orders.confirm":                {"queue": "high"},       # P1
    "notifications.send_email":      {"queue": "default"},    # P2
    "analytics.update_views":        {"queue": "low"},        # P3
    "reports.generate_daily":        {"queue": "batch"},      # P4 — nightly
}
```

### SaaS platform
```python
task_routes = {
    # Per-tier customer
    "render.enterprise":             {"queue": "tier_1"},     # paying $$$
    "render.pro":                    {"queue": "tier_2"},
    "render.free":                   {"queue": "tier_3"},
}
```

---

## 9. Throttling Low-Priority

Limit low-priority tasks' rate to prevent resource hogging.

```python
@app.task(queue="priority_low", rate_limit="100/m")    # 100/min max
def newsletter_email(user_id):
    send_email(user_id)
```

Or globally:
```python
app.conf.task_annotations = {
    "myapp.bulk.*": {"rate_limit": "10/s"},
}
```

---

## 10. Priority + Retries Trap

```python
# Failed high-priority task retries with default priority by default!
@app.task(queue="priority_high", autoretry_for=(Exception,))
def urgent_task():
    do_work()

# Retry goes to default queue → loses priority
```

### Fix: explicit retry queue
```python
@app.task(bind=True, queue="priority_high")
def urgent_task(self):
    try:
        do_work()
    except Exception as exc:
        raise self.retry(exc=exc, queue="priority_high", countdown=30)
```

---

## 11. SQS Priority Workaround

SQS doesn't support priorities. Use multi-queue:

```python
# 3 SQS queues, 1 worker pool
broker_transport_options = {
    "predefined_queues": {
        "priority_high": {"url": "..."},
        "default": {"url": "..."},
        "priority_low": {"url": "..."},
    }
}

# Worker greedily reads in order
# celery worker -Q priority_high,default,priority_low
```

---

## 12. Visualization in Flower / Prometheus

```promql
# Backlog by priority
celery_queue_length{queue=~"priority_.*|default"}

# Alert on high-priority backlog
celery_queue_length{queue="priority_high"} > 10 → page
celery_queue_length{queue="default"} > 1000 → warn
celery_queue_length{queue="priority_low"} > 100000 → notice
```

---

## 13. Common Pitfalls

### Pitfall 1: All tasks marked high-priority
Defeats the purpose. Reserve high for genuinely critical.

### Pitfall 2: No dedicated high-priority workers
Surge in default → high-priority workers also busy → defeats purpose.

### Pitfall 3: Priority inversion via shared resources
Low-pri locks DB row → high-pri waits.

### Pitfall 4: Retries go to default queue
Sets up subtle delays.

### Pitfall 5: Too many queues
5+ priority tiers → operational nightmare. 3 (high/default/low) usually enough.

### Pitfall 6: Memory overhead in RabbitMQ priority queues
Priority queues store messages in heap → ~30% more memory than FIFO.

---

## 14. Interview Questions

**Q1: Celery priority queue ka best approach?**
Multi-queue with dedicated workers per priority. Broker-agnostic, flexible.

**Q2: RabbitMQ priority vs multi-queue?**
RabbitMQ priority = single queue, 0-255 levels, only RabbitMQ.
Multi-queue = multiple queues, dedicated workers possible, works on all brokers.

**Q3: -Q order kya matter karta?**
`-Q high,default` — worker reads `high` first. If high empty, reads default.

**Q4: Starvation kaise prevent?**
Dedicated workers for high-pri queue. Never share workers across pri levels.

**Q5: Retries lose priority?**
Yes by default. Use `self.retry(queue="priority_high")` to keep.

**Q6: SQS priority?**
SQS doesn't support. Use multiple SQS queues with `-Q` ordering.

**Q7: How many priority tiers?**
3 max in practice — critical/default/bulk. More = complexity, less benefit.

---

## 15. Best Practices

1. **3 priority tiers max** — critical/default/low
2. **Dedicated workers** for high-priority queue
3. **Reserve "critical" for truly time-sensitive** (payments, auth)
4. **Rate limit low-priority** to prevent resource hogging
5. **Monitor backlog per queue**
6. **Different alert thresholds** per priority
7. **Explicit retry queue** to preserve priority
8. **Avoid shared resources** across tiers
9. **Test starvation scenarios** in load tests
10. **Document priority criteria** for the team

---

## Related
- [[01_celery_basics]]
- [[07_celery_task_routing]]
- [[02_celery_advanced]]
