# Flower + Prometheus — Celery Monitoring

> **Interview angle:** "Production mein Celery worker hang ho gaya — kaise pata? Queue backlog grow ho raha — alert kaise?"

---

## 1. Why Monitor Celery?

Celery in production = many moving parts:
- N worker processes
- M queues with varying load
- Tasks succeeding, failing, retrying, timing out
- Workers crashing silently
- Broker (RabbitMQ/Redis) connectivity issues

**Without monitoring:** You discover problems via customer complaints.

---

## 2. Three Layers of Monitoring

| Layer | What | Tool |
|---|---|---|
| **Real-time UI** | Live tasks, workers, queues | Flower |
| **Metrics** | Time-series for alerting | Prometheus + Grafana |
| **Logs** | Detailed task execution | Loki / ELK / Datadog |
| **Tracing** | Cross-service task flow | OpenTelemetry / Jaeger |

---

## 3. Flower — Real-Time Web UI

### What it shows
- Live worker status (online/offline)
- Active tasks per worker
- Task history (success/failure/retry)
- Queue lengths
- Real-time charts (tasks/sec)
- Per-task duration distribution

### Install
```bash
pip install flower
```

### Run
```bash
celery -A myapp flower \
    --port=5555 \
    --basic_auth=admin:secret_password \
    --persistent=true \
    --db=/var/lib/flower/db
```

### Connect to existing Celery
```bash
celery -A myapp flower --broker=redis://localhost:6379/0
```

### URL
http://localhost:5555 → dashboard

### Key Flower Features
- **Inspect tasks:** click any task ID to see args, kwargs, result, traceback
- **Cancel/revoke** tasks from UI
- **Rate limit** workers from UI (`worker.rate_limit('my_task', '10/m')`)
- **Pool size** changes from UI (scale up/down workers)
- **REST API** for automation

### Flower REST API
```bash
# Workers
curl http://localhost:5555/api/workers

# Tasks
curl http://localhost:5555/api/tasks?state=FAILURE&limit=20

# Specific task
curl http://localhost:5555/api/task/info/<task_id>

# Revoke task
curl -X POST http://localhost:5555/api/task/revoke/<task_id>?terminate=true
```

### Security
Flower exposes ALL task data. In production:
```bash
celery flower \
    --basic_auth=admin:strong_password \
    --url_prefix=/flower \
    --certfile=/etc/ssl/flower.crt \
    --keyfile=/etc/ssl/flower.key
```

Better: put Flower behind Nginx with OAuth (e.g., oauth2-proxy).

---

## 4. Prometheus + Grafana

For **alerts and long-term metrics**.

### Option 1: celery-exporter (recommended)
```bash
# Run exporter alongside Celery
docker run -p 9540:9540 \
    -e CELERY_BROKER_URL=redis://localhost:6379/0 \
    ovalmoney/celery-exporter
```

Or:
```bash
pip install celery-exporter
celery-exporter --broker=redis://localhost:6379/0
```

### Option 2: Flower's Prometheus endpoint
```bash
celery flower --prometheus-listen-address=0.0.0.0:5555
# Exposes /metrics endpoint
```

### prometheus.yml
```yaml
scrape_configs:
  - job_name: celery
    static_configs:
      - targets: ['celery-exporter:9540']
```

---

## 5. Key Metrics to Watch

### Task-level
- `celery_tasks_total{state="SUCCESS"}` — successful tasks
- `celery_tasks_total{state="FAILURE"}` — failed
- `celery_tasks_total{state="RETRY"}` — retries
- `celery_task_runtime_seconds` — duration histogram

### Worker-level
- `celery_workers` — active worker count
- `celery_worker_tasks_active` — currently running per worker
- `celery_worker_up` — heartbeat (1 = alive)

### Queue-level
- `celery_queue_length{queue="default"}` — backlog
- `celery_queue_length{queue="priority_high"}`

### Broker
- `rabbitmq_queue_messages_ready` (RabbitMQ)
- `redis_db_keys` (Redis broker)

---

## 6. Critical Alerts

```yaml
# alerts.yml for Prometheus Alertmanager

groups:
  - name: celery
    rules:
      # Worker down
      - alert: CeleryWorkerDown
        expr: celery_worker_up == 0
        for: 5m
        labels: { severity: page }
        annotations:
          summary: "Celery worker {{ $labels.worker }} is down"

      # Backlog growing
      - alert: CeleryQueueBacklog
        expr: celery_queue_length > 1000
        for: 10m
        labels: { severity: warning }
        annotations:
          summary: "Queue {{ $labels.queue }} has {{ $value }} pending tasks"

      # High failure rate
      - alert: CeleryHighFailureRate
        expr: |
          rate(celery_tasks_total{state="FAILURE"}[5m])
            /
          rate(celery_tasks_total[5m]) > 0.05
        for: 5m
        annotations:
          summary: "{{ $value | humanizePercentage }} task failure rate"

      # Tasks stuck
      - alert: CeleryStuckTask
        expr: celery_task_runtime_seconds{quantile="0.99"} > 600
        for: 10m
        annotations:
          summary: "p99 task runtime > 10 min"

      # No tasks processed (worker not consuming)
      - alert: CeleryNoTaskActivity
        expr: rate(celery_tasks_total[5m]) == 0
        for: 10m
```

---

## 7. Grafana Dashboard Panels

### Recommended panels
1. **Workers online** (gauge)
2. **Tasks per second** by state (success/failure/retry)
3. **Queue lengths** by queue (time series)
4. **Task runtime p50/p95/p99**
5. **Top failing tasks** (table)
6. **Worker memory/CPU** (from node-exporter)
7. **Broker health** (RabbitMQ/Redis metrics)

### Import existing dashboards
- Grafana dashboard ID: 12572 (celery-exporter)
- Or: 12056 (Celery Tasks Overview)

---

## 8. Application-Level Monitoring

### Celery signals → custom metrics
```python
from celery.signals import task_success, task_failure, task_retry
from prometheus_client import Counter, Histogram

task_counter = Counter("celery_tasks", "Total tasks", ["name", "state"])
task_duration = Histogram("celery_duration_seconds", "Task duration", ["name"])

@task_success.connect
def on_success(sender=None, result=None, **kwargs):
    task_counter.labels(name=sender.name, state="success").inc()

@task_failure.connect
def on_failure(sender=None, exception=None, **kwargs):
    task_counter.labels(name=sender.name, state="failure").inc()

@task_retry.connect
def on_retry(sender=None, **kwargs):
    task_counter.labels(name=sender.name, state="retry").inc()

# Task wrapper with duration
class TimedTask(celery.Task):
    def __call__(self, *args, **kwargs):
        with task_duration.labels(name=self.name).time():
            return super().__call__(*args, **kwargs)
```

---

## 9. OpenTelemetry Tracing

For multi-service task tracing:
```python
from opentelemetry.instrumentation.celery import CeleryInstrumentor

CeleryInstrumentor().instrument()
# Now every task gets a span. Cross-service tracing if HTTP → Celery → DB.
```

In Jaeger UI:
- See the full request flow: HTTP → Celery enqueue → worker pick-up → DB query → return
- p99 latency breakdown per service

---

## 10. Logging Best Practices

### Structured logging with task_id
```python
import logging
from celery.signals import task_prerun, task_postrun

@task_prerun.connect
def setup_log_context(task_id=None, task=None, **kwargs):
    logging.getLogger().setLevel(logging.INFO)
    # Inject task_id into all log records
    old_factory = logging.getLogRecordFactory()
    def factory(*args, **kwargs):
        rec = old_factory(*args, **kwargs)
        rec.task_id = task_id
        rec.task_name = task.name if task else ""
        return rec
    logging.setLogRecordFactory(factory)

# Logger format:
# %(asctime)s [%(task_name)s %(task_id)s] %(message)s
```

### Ship logs to centralized place
- Loki (Grafana)
- ELK / OpenSearch
- Datadog

Filter by task_id in UI → see full lifecycle of one task.

---

## 11. SLO Targets (Reasonable Defaults)

| Metric | Target |
|---|---|
| Worker uptime | 99.9% |
| Task success rate | > 99% |
| Queue backlog (default) | < 100 |
| Queue backlog (priority) | < 10 |
| Task p99 latency | < 30s (varies by task) |
| Task processing lag | < 5s |

Track these. Alert on violations.

---

## 12. Production Deployment Checklist

- [ ] Flower behind authenticated reverse proxy
- [ ] Prometheus scraping celery-exporter
- [ ] Grafana dashboard imported
- [ ] Alerts configured (worker down, queue backlog, failures)
- [ ] Structured logs with task_id
- [ ] Shipped to log aggregator
- [ ] OpenTelemetry traces enabled
- [ ] Pager rules in PagerDuty/Opsgenie
- [ ] Runbook for common alerts
- [ ] Worker autoscaling based on queue length (HPA/KEDA in k8s)

---

## 13. KEDA — Autoscale Workers Based on Queue

```yaml
apiVersion: keda.sh/v1alpha1
kind: ScaledObject
metadata:
  name: celery-worker-scaler
spec:
  scaleTargetRef:
    name: celery-worker          # Deployment to scale
  minReplicaCount: 2
  maxReplicaCount: 50
  triggers:
    - type: rabbitmq
      metadata:
        queueName: default
        queueLength: "20"        # 20 messages per replica
        host: amqp://broker:5672
```

Workers scale from 2 to 50 based on queue length. Auto-saves money.

---

## 14. Interview Questions

**Q1: Flower kya hai?**
Web UI for live Celery monitoring. Real-time view of workers, tasks, queues. Good for ops/oncall, not great for long-term metrics.

**Q2: Flower vs Prometheus?**
Flower = live snapshot. Prometheus = time-series for alerts. Use BOTH.

**Q3: Key Celery metrics?**
- Worker count online
- Queue length per queue
- Task success/failure rate
- Task p99 latency
- Broker health

**Q4: Stuck worker detect kaise?**
- Heartbeat absent → `celery_worker_up == 0` alert
- Tasks active for too long → `celery_task_runtime > threshold`
- Queue backlog growing → `celery_queue_length > X`

**Q5: Autoscaling Celery workers?**
KEDA in k8s — scales worker pod count based on queue length. SQS, RabbitMQ, Kafka, Redis triggers supported.

**Q6: Logs aggregation strategy?**
Structured logs with task_id → ship to Loki/ELK → filter by task_id to see full lifecycle.

**Q7: OpenTelemetry for Celery?**
`CeleryInstrumentor().instrument()` — automatic spans for every task. Trace HTTP → Celery → DB cross-service.

---

## 15. Best Practices

1. **Always run Flower** (cheap insurance)
2. **Prometheus + Grafana** for alerts
3. **Alert on: worker down, backlog, failure rate**
4. **Structured logs with task_id** for debugging
5. **OpenTelemetry tracing** for distributed flows
6. **KEDA autoscaling** based on queue
7. **Document SLOs + alert thresholds**
8. **Runbook for each alert**
9. **Backup Flower DB** for historical data
10. **Restrict Flower access** — never public

---

## Related
- [[../../01_Year3-4_Mid/04_DevOps/05_prometheus_grafana]]
- [[../../00_Year0-2_Junior/06_FastAPI/14_opentelemetry_distributed_tracing]]
- [[01_celery_basics]]
- [[02_celery_advanced]]
