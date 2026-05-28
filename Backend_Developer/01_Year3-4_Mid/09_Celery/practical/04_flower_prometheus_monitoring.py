"""
============================================================
FLOWER + PROMETHEUS MONITORING — Practical
============================================================
Templates + setup for production Celery monitoring.

Includes:
1. Flower configuration
2. celery-exporter for Prometheus
3. Custom metrics via Celery signals
4. OpenTelemetry instrumentation
5. KEDA autoscaling config
6. Grafana dashboard + alert rules
"""


# ============================================================
# 1. FLOWER SETUP
# ============================================================
FLOWER_SETUP = """
# Install
pip install flower

# Basic run
celery -A myapp flower --port=5555

# Production run
celery -A myapp flower \\
    --port=5555 \\
    --address=0.0.0.0 \\
    --basic_auth=admin:strong_password \\
    --url_prefix=/flower \\
    --max_tasks=10000 \\
    --persistent=true \\
    --db=/var/lib/flower/db \\
    --certfile=/etc/ssl/flower.crt \\
    --keyfile=/etc/ssl/flower.key

# Docker
docker run -p 5555:5555 \\
    -e CELERY_BROKER_URL=redis://broker:6379/0 \\
    -e FLOWER_BASIC_AUTH=admin:strong_password \\
    mher/flower:latest

# Behind Nginx (recommended)
location /flower/ {
    proxy_pass http://flower:5555/flower/;
    auth_request /oauth2/auth;
    error_page 401 = /oauth2/sign_in;
}

# Useful REST endpoints
curl http://localhost:5555/api/workers
curl http://localhost:5555/api/tasks?state=FAILURE
curl http://localhost:5555/api/task/info/<task_id>
curl -X POST http://localhost:5555/api/task/revoke/<task_id>?terminate=true
"""


# ============================================================
# 2. PROMETHEUS EXPORTER (celery-exporter)
# ============================================================
PROMETHEUS_EXPORTER = """
# Install
pip install celery-exporter

# OR Docker
docker run -d -p 9540:9540 \\
    -e CELERY_BROKER_URL=redis://broker:6379/0 \\
    ovalmoney/celery-exporter

# prometheus.yml
scrape_configs:
  - job_name: celery
    static_configs:
      - targets: ['celery-exporter:9540']
    metrics_path: /metrics
    scrape_interval: 15s

# Exposed metrics (sample):
# - celery_workers_count
# - celery_workers_active
# - celery_tasks_total{task_name, state}
# - celery_task_runtime_bucket{task_name}
# - celery_queue_length{queue_name}
"""


# ============================================================
# 3. CUSTOM METRICS VIA SIGNALS
# ============================================================
CUSTOM_METRICS = '''
from celery.signals import (
    task_prerun, task_postrun, task_success, task_failure,
    task_retry, task_revoked, worker_ready, worker_shutdown,
)
from prometheus_client import Counter, Histogram, Gauge, start_http_server

# Counters
TASK_COUNTER = Counter(
    "celery_tasks_total",
    "Total tasks processed",
    ["task_name", "state"],
)

# Histogram (duration)
TASK_DURATION = Histogram(
    "celery_task_duration_seconds",
    "Task duration in seconds",
    ["task_name"],
    buckets=(0.01, 0.05, 0.1, 0.5, 1, 5, 10, 30, 60, 300, 600),
)

# Gauges
WORKER_GAUGE = Gauge("celery_worker_up", "Worker is alive", ["worker"])
ACTIVE_TASKS = Gauge(
    "celery_worker_active_tasks",
    "Currently running tasks",
    ["worker"],
)

# Start metrics endpoint on each worker
@worker_ready.connect
def start_metrics_server(sender=None, **kwargs):
    start_http_server(9100)
    WORKER_GAUGE.labels(worker=sender.hostname).set(1)

@worker_shutdown.connect
def shutdown_metrics(sender=None, **kwargs):
    WORKER_GAUGE.labels(worker=sender.hostname).set(0)

@task_prerun.connect
def task_started(task_id=None, task=None, **kwargs):
    task._start_time = time.time()
    ACTIVE_TASKS.labels(worker=os.uname().nodename).inc()

@task_postrun.connect
def task_finished(task_id=None, task=None, **kwargs):
    duration = time.time() - task._start_time
    TASK_DURATION.labels(task_name=task.name).observe(duration)
    ACTIVE_TASKS.labels(worker=os.uname().nodename).dec()

@task_success.connect
def on_success(sender=None, **kwargs):
    TASK_COUNTER.labels(task_name=sender.name, state="success").inc()

@task_failure.connect
def on_failure(sender=None, **kwargs):
    TASK_COUNTER.labels(task_name=sender.name, state="failure").inc()

@task_retry.connect
def on_retry(sender=None, **kwargs):
    TASK_COUNTER.labels(task_name=sender.name, state="retry").inc()

@task_revoked.connect
def on_revoked(sender=None, **kwargs):
    TASK_COUNTER.labels(task_name=sender.name, state="revoked").inc()
'''


# ============================================================
# 4. OPENTELEMETRY TRACING
# ============================================================
OPENTELEMETRY_SETUP = """
# Install
pip install opentelemetry-instrumentation-celery
pip install opentelemetry-exporter-otlp

# In celeryconfig.py or app __init__
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.celery import CeleryInstrumentor
from opentelemetry.sdk.resources import Resource

# Setup once at app startup
resource = Resource.create({"service.name": "celery-workers"})
provider = TracerProvider(resource=resource)
provider.add_span_processor(BatchSpanProcessor(
    OTLPSpanExporter(endpoint="http://otel-collector:4317")
))
trace.set_tracer_provider(provider)

# Auto-instrument Celery
CeleryInstrumentor().instrument()

# Now every task creates a span. Cross-service traces work.

# Manual span inside task
from opentelemetry import trace
tracer = trace.get_tracer(__name__)

@app.task
def process_order(order_id):
    with tracer.start_as_current_span("validate_order"):
        validate(order_id)
    with tracer.start_as_current_span("charge_payment"):
        charge(order_id)
"""


# ============================================================
# 5. KEDA AUTOSCALING
# ============================================================
KEDA_AUTOSCALING = """
# KEDA — Kubernetes Event-Driven Autoscaling
# Scales worker pods based on queue length

apiVersion: keda.sh/v1alpha1
kind: ScaledObject
metadata:
  name: celery-default-worker-scaler
  namespace: prod
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: celery-default-worker
  pollingInterval: 15        # check every 15s
  cooldownPeriod: 60         # wait 60s before scale-down
  minReplicaCount: 2
  maxReplicaCount: 30
  triggers:
    - type: rabbitmq
      metadata:
        queueName: default
        mode: QueueLength
        value: "20"            # 20 messages = 1 worker
        host: amqp://broker:5672
      authenticationRef:
        name: rabbitmq-auth

---
# For Redis broker
apiVersion: keda.sh/v1alpha1
kind: ScaledObject
metadata:
  name: celery-redis-scaler
spec:
  scaleTargetRef:
    name: celery-worker
  minReplicaCount: 1
  maxReplicaCount: 20
  triggers:
    - type: redis
      metadata:
        listName: celery        # default Celery queue list name
        listLength: "50"
        host: redis-master
        port: "6379"
"""


# ============================================================
# 6. PROMETHEUS ALERT RULES
# ============================================================
PROMETHEUS_ALERTS = """
# /etc/prometheus/alerts/celery.yml

groups:
  - name: celery
    interval: 30s
    rules:
      # ===== WORKER ALERTS =====
      - alert: CeleryWorkerDown
        expr: celery_worker_up == 0
        for: 2m
        labels:
          severity: page
          team: backend
        annotations:
          summary: "Celery worker {{ $labels.worker }} down"
          description: "Worker hasn't sent heartbeat for 2+ minutes"

      - alert: NoCeleryWorkers
        expr: sum(celery_worker_up) < 1
        for: 1m
        labels: { severity: critical }
        annotations:
          summary: "NO Celery workers running!"

      # ===== QUEUE BACKLOG =====
      - alert: CeleryQueueBacklog
        expr: celery_queue_length{queue="default"} > 1000
        for: 10m
        labels: { severity: warning }
        annotations:
          summary: "Default queue backlog: {{ $value }}"

      - alert: CeleryHighPriorityBacklog
        expr: celery_queue_length{queue=~"priority_.*"} > 50
        for: 2m
        labels: { severity: critical }
        annotations:
          summary: "Priority queue {{ $labels.queue }} backed up"

      # ===== FAILURE RATE =====
      - alert: CeleryHighFailureRate
        expr: |
          sum(rate(celery_tasks_total{state="failure"}[5m]))
          /
          sum(rate(celery_tasks_total[5m])) > 0.05
        for: 5m
        labels: { severity: warning }
        annotations:
          summary: "Celery failure rate {{ $value | humanizePercentage }}"

      # ===== TASK DURATION =====
      - alert: CeleryTaskTooSlow
        expr: |
          histogram_quantile(0.99,
            rate(celery_task_duration_seconds_bucket[5m])
          ) > 600
        for: 10m
        annotations:
          summary: "Tasks running > 10 min at p99"

      # ===== STUCK TASKS =====
      - alert: CeleryNoActivity
        expr: sum(rate(celery_tasks_total[5m])) == 0
        for: 10m
        labels: { severity: warning }
        annotations:
          summary: "No tasks processed in 10 minutes"
"""


# ============================================================
# 7. GRAFANA DASHBOARD JSON (overview)
# ============================================================
GRAFANA_DASHBOARD_SAMPLE = """
{
  "dashboard": {
    "title": "Celery Overview",
    "panels": [
      {
        "type": "stat",
        "title": "Active Workers",
        "targets": [{"expr": "sum(celery_worker_up)"}]
      },
      {
        "type": "timeseries",
        "title": "Tasks per Second by State",
        "targets": [
          {"expr": "sum by (state) (rate(celery_tasks_total[1m]))"}
        ]
      },
      {
        "type": "timeseries",
        "title": "Queue Lengths",
        "targets": [
          {"expr": "celery_queue_length"}
        ]
      },
      {
        "type": "timeseries",
        "title": "Task Duration p50/p95/p99",
        "targets": [
          {"expr": "histogram_quantile(0.5,  rate(celery_task_duration_seconds_bucket[5m]))"},
          {"expr": "histogram_quantile(0.95, rate(celery_task_duration_seconds_bucket[5m]))"},
          {"expr": "histogram_quantile(0.99, rate(celery_task_duration_seconds_bucket[5m]))"}
        ]
      },
      {
        "type": "table",
        "title": "Failure Rate by Task",
        "targets": [
          {"expr": "topk(10, sum by (task_name) (rate(celery_tasks_total{state=\\"failure\\"}[5m])))"}
        ]
      }
    ]
  }
}

# Or import from Grafana.com:
# - ID 12572 (celery-exporter dashboard)
# - ID 12056 (Celery Overview)
"""


# ============================================================
# 8. STRUCTURED LOGGING WITH TASK_ID
# ============================================================
STRUCTURED_LOGGING = '''
import logging
from celery.signals import task_prerun, task_postrun
from contextvars import ContextVar

task_id_var: ContextVar[str] = ContextVar("task_id", default="")
task_name_var: ContextVar[str] = ContextVar("task_name", default="")

@task_prerun.connect
def setup_log_context(task_id=None, task=None, **kwargs):
    task_id_var.set(task_id or "")
    task_name_var.set(task.name if task else "")

@task_postrun.connect
def clear_log_context(**kwargs):
    task_id_var.set("")
    task_name_var.set("")

class TaskContextFilter(logging.Filter):
    def filter(self, record):
        record.task_id = task_id_var.get()
        record.task_name = task_name_var.get()
        return True

# Configure root logger
logging.basicConfig(
    format='%(asctime)s [%(task_name)s %(task_id)s] %(levelname)s %(message)s',
    level=logging.INFO,
)
for handler in logging.getLogger().handlers:
    handler.addFilter(TaskContextFilter())

# Now every log inside a task includes task_id automatically
@app.task
def my_task():
    logging.info("Processing...")
    # Output: 2024-... [myapp.my_task 28d7-...] INFO Processing...
'''


# ============================================================
# 9. FLOWER + OAUTH2 PROXY
# ============================================================
FLOWER_NGINX = """
# Nginx + oauth2-proxy (Google OAuth) for Flower

# docker-compose.yml
services:
  flower:
    image: mher/flower:latest
    command: celery flower --broker=redis://redis:6379/0 --url_prefix=/flower

  oauth2-proxy:
    image: quay.io/oauth2-proxy/oauth2-proxy:latest
    environment:
      OAUTH2_PROXY_PROVIDER: google
      OAUTH2_PROXY_CLIENT_ID: ${GOOGLE_CLIENT_ID}
      OAUTH2_PROXY_CLIENT_SECRET: ${GOOGLE_CLIENT_SECRET}
      OAUTH2_PROXY_EMAIL_DOMAINS: yourcompany.com
      OAUTH2_PROXY_COOKIE_SECRET: 32-char-random-secret
      OAUTH2_PROXY_UPSTREAMS: http://flower:5555
      OAUTH2_PROXY_HTTP_ADDRESS: 0.0.0.0:4180
    ports: ["4180:4180"]

# Access: https://yourapp.com/flower → forwards to Google → authenticated → Flower
"""


# ============================================================
# MAIN
# ============================================================
if __name__ == "__main__":
    print("=" * 60)
    print("CELERY MONITORING — Production Setup")
    print("=" * 60)

    print("\n--- 1. FLOWER ---")
    print(FLOWER_SETUP)

    print("\n--- 2. PROMETHEUS EXPORTER ---")
    print(PROMETHEUS_EXPORTER)

    print("\n--- 3. CUSTOM METRICS VIA SIGNALS ---")
    print(CUSTOM_METRICS)

    print("\n--- 4. OPENTELEMETRY ---")
    print(OPENTELEMETRY_SETUP)

    print("\n--- 5. KEDA AUTOSCALING ---")
    print(KEDA_AUTOSCALING)

    print("\n--- 6. PROMETHEUS ALERTS ---")
    print(PROMETHEUS_ALERTS)

    print("\n--- 7. GRAFANA DASHBOARD ---")
    print(GRAFANA_DASHBOARD_SAMPLE)

    print("\n--- 8. STRUCTURED LOGGING ---")
    print(STRUCTURED_LOGGING)

    print("\n--- 9. FLOWER + OAuth ---")
    print(FLOWER_NGINX)
