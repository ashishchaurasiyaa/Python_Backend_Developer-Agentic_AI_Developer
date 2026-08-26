# Worker Scaling — Celery

## 1. Horizontal Scaling (Add More Workers)

The simplest form of scaling: run more worker processes.

```
Broker (Redis/RabbitMQ)
         │
    ┌────┼────┐
    ↓    ↓    ↓
Worker1 Worker2 Worker3   ← 3 separate OS processes / containers
   ↓      ↓      ↓
DB    DB    DB            ← each opens its own connection pool
```

```bash
# Manual: start 3 separate worker processes
celery -A myapp worker --loglevel=info --concurrency=4 -n worker1@%h
celery -A myapp worker --loglevel=info --concurrency=4 -n worker2@%h
celery -A myapp worker --loglevel=info --concurrency=4 -n worker3@%h

# Each worker has 4 child processes → 12 concurrent tasks total
```

---

## 2. Celery Built-in Autoscale

Celery can manage its own concurrency within one worker process.

```bash
# --autoscale=max,min
# Starts with min processes, scales up to max based on queue backlog
celery -A myapp worker --autoscale=20,4 --loglevel=info
```

```
Queue empty:     Worker uses 4 processes (min)
Queue growing:   Worker spawns up to 20 processes (max)
Queue drains:    Worker kills idle processes, returns to 4

Limits: autoscale only scales WITHIN one worker process.
        For more machines, need external orchestration.
```

**Configuration:**
```python
# celery config
app.conf.worker_autoscaler = "celery.worker.autoscale:Autoscaler"
app.conf.worker_max_tasks_per_child = 1000   # restart child after 1000 tasks (memory leak prevention)
```

---

## 3. Queue-Depth Based Scaling — KEDA (Kubernetes)

KEDA (Kubernetes Event Driven Autoscaling) scales worker PODS based on broker queue depth.

```yaml
# keda-scaledobject.yaml
apiVersion: keda.sh/v1alpha1
kind: ScaledObject
metadata:
  name: celery-worker-scaler
spec:
  scaleTargetRef:
    name: celery-worker           # Deployment to scale
  minReplicaCount: 2              # always keep 2 warm
  maxReplicaCount: 50             # hard cap
  triggers:
    - type: redis
      metadata:
        address: redis:6379
        listName: celery          # default Celery queue name in Redis
        listLength: "10"          # scale up if queue has > 10 tasks per pod
```

```
Queue depth = 0:   KEDA keeps 2 pods (minReplicaCount)
Queue depth = 100: KEDA scales to ceil(100/10) = 10 pods
Queue depth = 500: KEDA scales to min(50, ceil(500/10)) = 50 pods
Queue depth → 0:   KEDA scales back down to 2 pods (with cooldown)
```

---

## 4. What NOT to Do — Anti-Patterns

### Anti-pattern 1: Blindly adding workers

```
Problem: 50 workers, DB pool_size=10 → 50×5 = 250 potential connections
                     PostgreSQL max_connections=100 → CONNECTION REFUSED

Fix: total_connections = workers × concurrency × db_pool_size ≤ max_connections
     Plan: 10 workers × concurrency=4 × pool_size=2 = 80 < 100 ✓
```

```python
# celery config — limit DB connections per worker
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "CONN_MAX_AGE": 60,
        "OPTIONS": {"pool_size": 2, "max_overflow": 3},  # pgbouncer / SQLAlchemy pool
    }
}
```

### Anti-pattern 2: All tasks in one queue

```
Problem:
  100,000 email tasks queued → 5 payment tasks queued
  Workers busy with emails → payment tasks wait 2 hours

Fix: separate queues + dedicated workers
  email_queue:   10 workers (ok to be slow)
  payment_queue:  3 workers (must be fast, high priority)
```

### Anti-pattern 3: Scale workers when API is the bottleneck

```
Problem: External API allows 20 req/sec. You have 100 workers.
         Adding workers doesn't increase throughput — just more 429 errors.

Fix: Rate limit at the task level (see theory/11_rate_limiting_external_apis.md)
     NOT at the worker count level.
```

---

## 5. Metrics to Scale On

```
Metric                  Signal
─────────────────────────────────────────────────────
Queue depth             Primary scaling signal
                        > 100 tasks → add workers
                        < 10 tasks → shrink workers

Task latency            Time from enqueue to start execution
                        High latency → workers can't keep up → scale up

Task throughput         Tasks/sec actually completed
                        Plateauing despite adding workers → bottleneck elsewhere

Worker CPU              > 80% → CPU-bound, add more processes/machines
                        < 20% → I/O-bound, consider gevent (not more processes)

Worker memory           > 80% → memory leak, max_tasks_per_child, or reduce concurrency

Failed task rate        Spike in failures → likely an upstream issue, NOT a scaling issue
                        Don't scale workers when the upstream API is down
```

---

## 6. Multi-Queue Scaling Strategy

```
                    Broker
                   /  |  \
                  ↓   ↓   ↓
           email  pay  rep  ← separate queues
            ↓     ↓    ↓
          10w    3w   2w    ← dedicated workers per queue
          auto  fix  auto   ← autoscale email+report, fixed for payment
```

```bash
# Payment workers — fixed 3 (predictable, don't want autoscale surprises)
celery -A myapp worker -Q payment_queue --concurrency=4 -n payment@%h

# Email workers — autoscale 2–20
celery -A myapp worker -Q email_queue --autoscale=20,2 -n email@%h

# Report workers — autoscale 1–10 (batch jobs, ok to be slow)
celery -A myapp worker -Q report_queue --autoscale=10,1 -n report@%h
```

---

## 7. Scaling Decision Tree

```
Queue depth growing?
  YES → Is worker CPU high (>80%)?
         YES → CPU-bound → add more workers / increase concurrency
         NO  → I/O-bound → try gevent/eventlet OR more workers
              → Is DB connection pool exhausted?
                YES → fix pool size first, don't just add workers
  NO → Is task latency high?
        YES → Is the external API slow?
               YES → rate limit / circuit breaker, not more workers
              → Is DB slow?
               YES → query optimization / read replicas, not more workers
        NO → Scaling is not the problem
```

---

## 8. Worker Lifecycle & Graceful Shutdown

```bash
# Graceful shutdown — finish current tasks, don't accept new ones
celery -A myapp control shutdown      # broadcast to all workers
kill -TERM <worker_pid>               # SIGTERM → graceful

# Immediate kill (tasks are lost if no acks_late)
kill -KILL <worker_pid>               # SIGKILL → hard kill

# Restart with new code (rolling deploy)
celery -A myapp control pool_restart  # restart child processes (hot reload)
```

```python
# Prevent tasks from being interrupted on shutdown
app.conf.worker_cancel_long_running_tasks_on_connection_loss = True
app.conf.task_soft_time_limit = 3600    # task gets SoftTimeLimitExceeded → can clean up
app.conf.task_time_limit      = 3900    # hard kill after this
```

---

## 9. Interview Questions

**Q: Celery workers kitne rakhne chahiye?**
Queue depth, task latency, worker CPU/memory dekho. Formula: `workers = ceil(queue_depth / tasks_per_worker_per_second)`. DB connections bhi consider karo: `total_conns = workers × concurrency × pool_size ≤ DB max_connections`.

**Q: `--autoscale` kab use karo?**
Variable load ke liye — peak pe 20 workers chahiye, off-peak pe 2. One worker process ke andar concurrency scale karta hai. Cross-machine scaling ke liye KEDA (Kubernetes) ya manual worker scaling chahiye.

**Q: Worker add karne se performance improve nahi ho rahi — kya hua?**
Bottleneck somewhere else: DB pool exhausted, external API rate-limited, network bandwidth, or I/O-bound tasks (use gevent instead of more processes). Scale karne se pehle `celery inspect` + Flower se diagnose karo.

**Q: Graceful shutdown kya hai? Kyun zaroori hai?**
SIGTERM pe worker current tasks finish karta hai phir exit karta hai. SIGKILL pe mid-task kill → with `acks_late=True` task re-queued, else lost. Graceful shutdown ensures no task is lost during deploy or scale-in.
