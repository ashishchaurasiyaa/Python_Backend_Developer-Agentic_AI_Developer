# Celery — Production Architecture

## 1. Full Production Stack

```
                        Load Balancer (Nginx / ALB)
                                    │
                    ┌───────────────┼───────────────┐
                    ↓               ↓               ↓
              App Server 1    App Server 2    App Server 3
             (Django/FastAPI) (Django/FastAPI) (Django/FastAPI)
                    │               │               │
                    └───────────────┴───────────────┘
                                    │
                            ┌───────┴───────┐
                            │   PostgreSQL   │   ← source of truth
                            └───────┬───────┘
                                    │
                       ┌────────────┴────────────┐
                       │    Celery Producers      │  (app servers call .delay())
                       └────────────┬────────────┘
                                    │
                    ┌───────────────┼───────────────┐
                    ↓               ↓               ↓
             Redis (Broker)  RabbitMQ (alt)  Redis (Result Backend)
               DB 0                             DB 1
                    │
       ┌────────────┼────────────┬────────────┐
       ↓            ↓            ↓            ↓
  email_queue  payment_queue  report_queue  high_priority
       │            │            │            │
  10 workers    3 workers    2 workers    5 workers
  (autoscale)  (fixed)      (autoscale)  (fixed)
       │            │            │            │
       └────────────┴────────────┴────────────┘
                            │
                     PostgreSQL / Redis
                   (task writes results here)
                            │
                   Celery Beat (1 instance)
                   (periodic task scheduler)
                            │
                   Flower (monitoring UI)
                   + Prometheus metrics
```

---

## 2. Queue Design

| Queue | Tasks | Workers | Priority |
|-------|-------|---------|----------|
| `payment_queue` | Payment processing, refunds | 3 (fixed) | Critical — never starved |
| `high_queue` | OTP/notifications, order confirmation | 5 (fixed) | High |
| `email_queue` | Marketing emails, invoices | 2–20 (autoscale) | Medium |
| `report_queue` | PDF reports, Excel exports, batch jobs | 1–10 (autoscale) | Low |
| `default` | Everything else | 4 (autoscale) | Normal |

```python
# celery config
app.conf.task_routes = {
    "payments.tasks.charge_card":        {"queue": "payment_queue"},
    "payments.tasks.process_refund":     {"queue": "payment_queue"},
    "notifications.tasks.send_otp":      {"queue": "high_queue"},
    "reports.tasks.generate_pdf":        {"queue": "report_queue"},
    "emails.tasks.send_marketing":       {"queue": "email_queue"},
}
app.conf.task_default_queue = "default"
```

---

## 3. Production Configuration Checklist

```python
# celery.py
app.conf.update(
    # Serialization
    task_serializer    = "json",
    result_serializer  = "json",
    accept_content     = ["json"],        # never accept pickle in prod

    # Reliability
    task_acks_late                 = True,   # ack AFTER completion
    task_reject_on_worker_lost     = True,   # requeue if worker crashes
    worker_prefetch_multiplier     = 1,      # one task at a time per child (fair)

    # Timeouts
    task_soft_time_limit = 1800,             # 30 min → SoftTimeLimitExceeded
    task_time_limit      = 1860,             # 31 min → hard kill

    # Results
    result_expires       = 3600,             # clean up results after 1 hour
    task_ignore_result   = True,             # set per-task if result not needed

    # Beat
    beat_scheduler = "django_celery_beat.schedulers:DatabaseScheduler",

    # Worker
    worker_max_tasks_per_child = 1000,       # prevent memory leaks
    worker_max_memory_per_child = 200_000,   # 200MB per child (in kB)
)
```

---

## 4. Failure Scenarios — Interview Q&A

### "Worker crash ho jaaye task ke beech mein — kya hota hai?"

```
Default (acks_late=False):
  Worker crashes after task STARTED → broker acked → task LOST

With acks_late=True:
  Worker crashes → broker NOT acked → broker redelivers → task reruns
  BUT: if task already completed part of the work → duplicate execution
  → Task must be IDEMPOTENT

Best setup:
  task_acks_late = True        ← redelivery on crash
  task_reject_on_worker_lost = True  ← explicit requeue
  + idempotent tasks           ← duplicate-safe
```

### "Redis/RabbitMQ (Broker) down ho jaaye?"

```
Producers (.delay() calls):
  → ConnectionError → task NOT queued → lost if no retry
  → Fix: wrap .delay() in try/except, Celery has retry on connection error

Workers:
  → Can't pick up new tasks → idle (no crash)
  → Will reconnect when broker comes back

In-flight tasks:
  → If RabbitMQ: durable queues → messages survive restart
  → If Redis: AOF persistence → messages survive if configured

Django setting:
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True
CELERY_BROKER_CONNECTION_MAX_RETRIES = None  # retry forever
```

### "Result Backend (Redis) down ho jaaye?"

```
Workers:
  → Tasks execute normally but result.get() fails
  → If task_ignore_result=True → no impact

Application:
  → .get() raises Exception
  → Fix: wrap in try/except, serve stale data or return "pending"

Separation of concern:
  → Broker failure = tasks not processed (critical)
  → Backend failure = results unavailable (less critical, often survivable)
```

### "Ek task hang ho jaaye (infinite loop)?"

```
Without timeouts:
  → Worker child process hangs forever → takes up a concurrency slot
  → Other tasks queue up → latency spikes

With timeouts:
  task_soft_time_limit = 1800   → SoftTimeLimitExceeded raised → task can clean up
  task_time_limit      = 1860   → SIGKILL to child process → forceful termination

Per-task override:
@app.task(soft_time_limit=60, time_limit=70)
def slow_task(): ...
```

### "Duplicate tasks aa rahe hain — customer double charged?"

```
Root causes:
  1. acks_late=True + worker crash after task completed but before ACK
  2. Task submitted twice (race condition in producer)
  3. Visibility timeout exceeded → broker redelivers

Fix: Idempotency
  → Store result in Redis with idempotency_key (24h TTL)
  → On retry: check key → return cached result → skip payment
  → External APIs: pass Idempotency-Key header (Stripe, Razorpay support this)
```

### "Queue depth barhti ja rahi hai — tasks process nahi ho rahe?"

```
Diagnose:
  1. Flower/redis-cli LLEN → queue depth
  2. Worker logs → are workers running? Any errors?
  3. celery inspect active → any stuck tasks?
  4. Is an external dependency (DB, API) slow?

Fix based on root cause:
  Worker died → restart workers
  Tasks too slow → reduce complexity, add workers, chunk large tasks
  External API bottleneck → rate limiting (see theory/11)
  DB slow → query optimization, read replicas
  Memory leak → worker_max_tasks_per_child=1000
```

### "Celery Beat duplicate tasks aa rahe hain (multiple Beat instances)?"

```
Problem: 2 Beat instances running same schedule → tasks submitted twice

Fix:
  → Run EXACTLY ONE Beat instance (not with replica=2)
  → Kubernetes: use Deployment with replicas=1 for Beat
  → Or: django-celery-beat with DB scheduler (handles distributed locking internally)
  → Or: use Redis-based distributed lock in the periodic task itself
```

---

## 5. Scaling Decisions

```
When to ADD workers:
  ✓ Queue depth consistently > 100 tasks
  ✓ Task latency (enqueue → start) > SLA threshold
  ✓ Worker CPU consistently > 70%
  ✓ DB connections not at limit

When NOT to add workers:
  ✗ External API rate-limited → rate limit first
  ✗ DB connection pool exhausted → fix pool or use pgbouncer
  ✗ Tasks failing not slow → debug the failure, don't scale
  ✗ Only one queue is backed up → scale that queue's workers specifically
```

---

## 6. Monitoring Production Celery

```bash
# Flower — web UI
pip install flower
celery -A myapp flower --port=5555

# CLI inspection
celery -A myapp inspect active        # running tasks
celery -A myapp inspect reserved      # prefetched, not started
celery -A myapp inspect scheduled     # ETA/countdown tasks
celery -A myapp inspect stats         # worker stats
celery -A myapp inspect registered    # registered task names

# Redis queue depth (for email_queue)
redis-cli LLEN email_queue

# Key metrics to alert on:
# - queue depth > 1000 → scale workers
# - task failure rate > 1% → investigate
# - celery.task.runtime > P99 threshold → performance regression
# - worker count < expected → worker crash
```

---

## 7. Complete Production Interview Answer

**"SDE-2 interview: Design a Celery setup for an e-commerce platform."**

```
1. Queues: payment, high (OTP), email, reports, default
2. Workers per queue: payment=3 fixed, high=5 fixed, email=autoscale(2,20),
   reports=autoscale(1,10)
3. Broker: RabbitMQ (durable queues) or Redis with AOF persistence
4. Result backend: Redis (short TTL — 1hr)
5. Reliability: acks_late=True, task_reject_on_worker_lost=True,
   idempotent payment tasks, on_commit() dispatch
6. Retries: autoretry_for=(TransientError,), retry_backoff=True,
   retry_jitter=True, max_retries=5
7. Timeouts: soft=1800, hard=1860 for all tasks
8. Beat: single instance with DB scheduler (django-celery-beat)
9. Monitoring: Flower + Prometheus (celery-prometheus-exporter) + Grafana
10. Scaling: KEDA for email/report queues based on queue depth
```

---

## 8. Interview Questions

**Q: Payment queue kyun alag rakhte hain?**
Payment tasks are latency-sensitive and must not be blocked by thousands of email tasks. Dedicated workers with fixed concurrency give predictable SLA.

**Q: acks_late=True vs acks_late=False — production mein kya use karoge?**
`acks_late=True` for critical tasks (payments, order processing) — task redelivered on crash, idempotency mandatory. `acks_late=False` for fast, idempotent tasks (cache invalidation, event logging) — less overhead.

**Q: Celery Beat ke liye replicas=2 kyun nahi karte?**
Two Beat instances same schedule pe tasks dobara submit karte hain — duplicate tasks. Beat EXACTLY ONE instance hona chahiye. Kubernetes mein Deployment replicas=1.

**Q: Task result backend kyun optional hai?**
Bahut saare tasks ka result application ko chahiye hi nahi (send_email → fire-and-forget). `task_ignore_result=True` pe result backend call hi nahi hota → less Redis load. Result sirf tab use karo jab `.get()` call karna ho.
