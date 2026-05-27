# Lecture 7 — Practical Hands-On: Observability

> **Theory file:** [07_Observability.md](07_Observability.md)

---

## 🎯 Is Practical Mein Kya Banayenge?

Complete observability stack:

1. ✅ **Structured logging** with JSON + correlation IDs
2. ✅ **Prometheus** metrics with custom dimensions
3. ✅ **Jaeger** distributed tracing
4. ✅ **OpenTelemetry** auto-instrumentation
5. ✅ **Grafana** dashboards
6. ✅ **SLO tracking** with error budgets
7. ✅ **Alerting** rules + runbooks
8. ✅ **ELK stack** for log aggregation
9. ✅ **Multi-service** trace correlation
10. ✅ **Production-ready** monitoring

By end: aap **production observability** setup kar sakte ho.

---

## 1. Project Structure

```
observability_demo/
├── docker-compose.yml
│
├── app/
│   ├── main.py                    # FastAPI app
│   ├── tracing.py                  # OpenTelemetry
│   ├── metrics.py                  # Prometheus
│   ├── logging_config.py           # Structured logs
│   └── slo_tracker.py             # Error budgets
│
├── prometheus/
│   ├── prometheus.yml
│   └── alerts.yml
│
├── grafana/
│   └── dashboards/
│       ├── golden-signals.json
│       ├── slo-tracking.json
│       └── application.json
│
├── alertmanager/
│   └── config.yml
│
└── runbooks/
    ├── high-error-rate.md
    └── high-latency.md
```

---

## 2. 📊 Structured Logging

### `app/logging_config.py`

```python
"""
Structured JSON logging with correlation IDs.
"""
import logging
import sys
import json
from datetime import datetime
from contextvars import ContextVar

correlation_id: ContextVar[str] = ContextVar("correlation_id", default="")
user_id: ContextVar[str] = ContextVar("user_id", default="")

class JSONFormatter(logging.Formatter):
    def format(self, record):
        log = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
            
            # Context from ContextVar
            "correlation_id": correlation_id.get(""),
            "user_id": user_id.get(""),
        }
        
        # Exception info
        if record.exc_info:
            log["exception"] = self.formatException(record.exc_info)
        
        # Extra fields from logger calls
        for key, value in record.__dict__.items():
            if key not in ["name", "msg", "args", "created", "filename",
                           "funcName", "levelname", "levelno", "lineno",
                           "module", "msecs", "message", "pathname",
                           "process", "processName", "relativeCreated",
                           "thread", "threadName", "exc_info", "exc_text",
                           "stack_info"]:
                log[key] = value
        
        return json.dumps(log, default=str)

def setup_logging(level="INFO"):
    root = logging.getLogger()
    root.setLevel(level)
    
    # Remove default handlers
    for handler in root.handlers[:]:
        root.removeHandler(handler)
    
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JSONFormatter())
    root.addHandler(handler)
    
    # Quiet noisy libraries
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
```

### Usage with Context

```python
# app/main.py
from fastapi import FastAPI, Request
import uuid
import logging

from app.logging_config import correlation_id, user_id

logger = logging.getLogger(__name__)

app = FastAPI()

@app.middleware("http")
async def add_correlation_id(request: Request, call_next):
    """Set correlation ID for entire request"""
    cid = request.headers.get("X-Correlation-Id") or str(uuid.uuid4())
    correlation_id.set(cid)
    
    response = await call_next(request)
    response.headers["X-Correlation-Id"] = cid
    return response

@app.post("/orders")
async def create_order(req: dict):
    user_id.set(str(req["user_id"]))
    
    # All logs in this request scope have correlation_id + user_id!
    logger.info("Creating order", extra={
        "items_count": len(req["items"]),
        "amount": req["amount"],
    })
    
    try:
        # Business logic
        result = await process_order(req)
        logger.info("Order created", extra={"order_id": result["id"]})
        return result
    except Exception as e:
        logger.error("Order failed", exc_info=True, extra={"error": str(e)})
        raise
```

### Sample Log Output

```json
{
  "timestamp": "2026-05-26T10:00:00.123Z",
  "level": "INFO",
  "logger": "app.main",
  "message": "Order created",
  "module": "main",
  "function": "create_order",
  "line": 42,
  "correlation_id": "550e8400-e29b-41d4-a716-446655440000",
  "user_id": "123",
  "order_id": "ORD-abc12345"
}
```

---

## 3. 📈 Prometheus Metrics

### `app/metrics.py`

```python
"""
Prometheus metrics with the four golden signals.
"""
from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST
from fastapi import Response
import time

# ─────────────────────────────────────────────────────────────
# THE FOUR GOLDEN SIGNALS
# ─────────────────────────────────────────────────────────────

# 1. TRAFFIC
http_requests = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "status"]
)

# 2. ERRORS
http_errors = Counter(
    "http_errors_total",
    "Total HTTP errors (4xx/5xx)",
    ["method", "endpoint", "status"]
)

# 3. LATENCY
http_duration = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration",
    ["method", "endpoint"],
    buckets=[0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0]
)

# 4. SATURATION
active_connections = Gauge(
    "active_connections",
    "Currently active connections"
)

# ─────────────────────────────────────────────────────────────
# BUSINESS METRICS
# ─────────────────────────────────────────────────────────────
orders_total = Counter(
    "orders_total",
    "Total orders placed",
    ["status"]
)

order_value = Histogram(
    "order_value_dollars",
    "Order value distribution",
    buckets=[10, 50, 100, 500, 1000, 5000, 10000]
)

# ─────────────────────────────────────────────────────────────
# RESOURCE METRICS (from process)
# ─────────────────────────────────────────────────────────────
db_pool_size = Gauge("db_pool_size", "Current DB pool size")
cache_hits = Counter("cache_hits_total", "Cache hits")
cache_misses = Counter("cache_misses_total", "Cache misses")

# ─────────────────────────────────────────────────────────────
# MIDDLEWARE
# ─────────────────────────────────────────────────────────────
def metrics_middleware(app):
    @app.middleware("http")
    async def track_metrics(request, call_next):
        active_connections.inc()
        start = time.time()
        
        try:
            response = await call_next(request)
            duration = time.time() - start
            
            # Sanitize path (avoid high cardinality!)
            endpoint = sanitize_path(request.url.path)
            
            http_requests.labels(
                method=request.method,
                endpoint=endpoint,
                status=response.status_code
            ).inc()
            
            if response.status_code >= 400:
                http_errors.labels(
                    method=request.method,
                    endpoint=endpoint,
                    status=response.status_code
                ).inc()
            
            http_duration.labels(
                method=request.method,
                endpoint=endpoint
            ).observe(duration)
            
            return response
        finally:
            active_connections.dec()

def sanitize_path(path: str) -> str:
    """Replace IDs with placeholders to avoid high cardinality"""
    import re
    # /users/123 → /users/:id
    path = re.sub(r'/\d+', '/:id', path)
    # /orders/UUID → /orders/:id
    path = re.sub(r'/[a-f0-9-]{36}', '/:id', path)
    return path

# Metrics endpoint
@app.get("/metrics")
async def metrics():
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
```

### Custom Business Metrics

```python
# Track order placement
@app.post("/orders")
async def create_order(req: dict):
    try:
        order = await process_order(req)
        
        orders_total.labels(status="success").inc()
        order_value.observe(order["total"])
        
        return order
    
    except Exception as e:
        orders_total.labels(status="failure").inc()
        raise
```

---

## 4. 🔍 Distributed Tracing with OpenTelemetry

### `app/tracing.py`

```python
"""
OpenTelemetry distributed tracing setup.
"""
from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.instrumentation.asyncpg import AsyncPGInstrumentor
from opentelemetry.instrumentation.redis import RedisInstrumentor
import os

def setup_tracing(app, service_name: str):
    """Configure tracing for the entire app"""
    
    # Resource (identifies this service)
    resource = Resource.create({
        "service.name": service_name,
        "service.version": os.getenv("APP_VERSION", "1.0.0"),
        "deployment.environment": os.getenv("ENVIRONMENT", "production"),
    })
    
    # Provider
    provider = TracerProvider(resource=resource)
    trace.set_tracer_provider(provider)
    
    # OTLP exporter (Jaeger, Tempo, etc.)
    otlp_exporter = OTLPSpanExporter(
        endpoint=os.getenv("OTEL_EXPORTER_ENDPOINT", "http://jaeger:4317"),
        insecure=True,
    )
    provider.add_span_processor(BatchSpanProcessor(otlp_exporter))
    
    # Auto-instrument frameworks
    FastAPIInstrumentor.instrument_app(app)
    HTTPXClientInstrumentor().instrument()
    AsyncPGInstrumentor().instrument()
    RedisInstrumentor().instrument()
    
    print(f"[Tracing] Configured for {service_name}")

# Manual span creation
tracer = trace.get_tracer(__name__)

@app.post("/orders")
async def create_order(req: dict):
    with tracer.start_as_current_span("create_order_workflow") as span:
        # Add custom attributes
        span.set_attribute("user.id", req["user_id"])
        span.set_attribute("items.count", len(req["items"]))
        span.set_attribute("amount", req["amount"])
        
        # Nested span for sub-operation
        with tracer.start_as_current_span("validate_order"):
            await validate_order(req)
        
        with tracer.start_as_current_span("check_inventory"):
            available = await check_inventory(req["items"])
            if not available:
                span.set_status(trace.Status(trace.StatusCode.ERROR))
                raise InsufficientStockError()
        
        with tracer.start_as_current_span("charge_payment"):
            charge_result = await charge_payment(req["amount"])
            span.set_attribute("charge.id", charge_result["id"])
        
        return {"order_id": "..."}
```

---

## 5. 🐳 Docker Compose Stack

### `docker-compose.yml`

```yaml
version: '3.8'

services:
  # ─────────────────────────────────────────────────────────
  # APP (instrumented)
  # ─────────────────────────────────────────────────────────
  app:
    build: .
    ports: ["8000:8000"]
    environment:
      OTEL_EXPORTER_ENDPOINT: http://jaeger:4317
      OTEL_SERVICE_NAME: my-app
      LOG_LEVEL: INFO
    depends_on: [prometheus, jaeger, loki]
  
  # ─────────────────────────────────────────────────────────
  # METRICS (Prometheus)
  # ─────────────────────────────────────────────────────────
  prometheus:
    image: prom/prometheus:latest
    ports: ["9090:9090"]
    volumes:
      - ./prometheus/prometheus.yml:/etc/prometheus/prometheus.yml
      - ./prometheus/alerts.yml:/etc/prometheus/alerts.yml
      - prometheus_data:/prometheus
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
      - '--storage.tsdb.retention.time=30d'
      - '--web.enable-lifecycle'
  
  # ─────────────────────────────────────────────────────────
  # DASHBOARDS (Grafana)
  # ─────────────────────────────────────────────────────────
  grafana:
    image: grafana/grafana:latest
    ports: ["3000:3000"]
    environment:
      GF_SECURITY_ADMIN_PASSWORD: admin
      GF_INSTALL_PLUGINS: grafana-piechart-panel
    volumes:
      - ./grafana/dashboards:/var/lib/grafana/dashboards
      - grafana_data:/var/lib/grafana
    depends_on: [prometheus, loki, jaeger]
  
  # ─────────────────────────────────────────────────────────
  # TRACES (Jaeger)
  # ─────────────────────────────────────────────────────────
  jaeger:
    image: jaegertracing/all-in-one:latest
    ports:
      - "16686:16686"   # UI
      - "4317:4317"     # OTLP gRPC
      - "4318:4318"     # OTLP HTTP
    environment:
      COLLECTOR_OTLP_ENABLED: "true"
  
  # ─────────────────────────────────────────────────────────
  # LOGS (Loki)
  # ─────────────────────────────────────────────────────────
  loki:
    image: grafana/loki:latest
    ports: ["3100:3100"]
    command: -config.file=/etc/loki/local-config.yaml
  
  promtail:
    image: grafana/promtail:latest
    volumes:
      - /var/log:/var/log
      - /var/lib/docker/containers:/var/lib/docker/containers:ro
      - ./promtail/promtail.yml:/etc/promtail/promtail.yml
    command: -config.file=/etc/promtail/promtail.yml
    depends_on: [loki]
  
  # ─────────────────────────────────────────────────────────
  # ALERTS (Alertmanager)
  # ─────────────────────────────────────────────────────────
  alertmanager:
    image: prom/alertmanager:latest
    ports: ["9093:9093"]
    volumes:
      - ./alertmanager/config.yml:/etc/alertmanager/config.yml

volumes:
  prometheus_data:
  grafana_data:
```

---

## 6. ⚙️ Prometheus Configuration

### `prometheus/prometheus.yml`

```yaml
global:
  scrape_interval: 15s
  evaluation_interval: 15s
  external_labels:
    cluster: production
    region: us-east-1

rule_files:
  - "/etc/prometheus/alerts.yml"

alerting:
  alertmanagers:
    - static_configs:
        - targets: ['alertmanager:9093']

scrape_configs:
  # App metrics
  - job_name: 'app'
    metrics_path: '/metrics'
    static_configs:
      - targets: ['app:8000']
  
  # Prometheus itself
  - job_name: 'prometheus'
    static_configs:
      - targets: ['localhost:9090']
  
  # Node exporter (system metrics)
  - job_name: 'node'
    static_configs:
      - targets: ['node-exporter:9100']
  
  # Kubernetes service discovery
  - job_name: 'kubernetes-pods'
    kubernetes_sd_configs:
      - role: pod
    relabel_configs:
      - source_labels: [__meta_kubernetes_pod_annotation_prometheus_io_scrape]
        action: keep
        regex: true
```

### `prometheus/alerts.yml`

```yaml
groups:
- name: golden_signals
  interval: 30s
  rules:
  
  # High error rate
  - alert: HighErrorRate
    expr: |
      sum(rate(http_errors_total[5m])) by (endpoint) 
        / sum(rate(http_requests_total[5m])) by (endpoint) > 0.01
    for: 5m
    labels:
      severity: warning
      pager: oncall
    annotations:
      summary: "High error rate on {{ $labels.endpoint }}"
      description: "{{ $value | humanizePercentage }} error rate on {{ $labels.endpoint }}"
      runbook: "https://wiki.example.com/runbooks/high-error-rate"
  
  # High latency
  - alert: HighLatencyP95
    expr: |
      histogram_quantile(0.95, 
        rate(http_request_duration_seconds_bucket[5m])
      ) > 1.0
    for: 5m
    labels:
      severity: warning
    annotations:
      summary: "P95 latency > 1s"
      description: "P95 latency is {{ $value }}s"
  
  # SLO burn rate (fast)
  - alert: SLOBurnRateFast
    expr: |
      (
        sum(rate(http_errors_total[1h]))
        / sum(rate(http_requests_total[1h]))
      ) > (1 - 0.999) * 14.4  # 14.4x burn rate = 2% of monthly budget in 1 hour
    for: 5m
    labels:
      severity: critical
      pager: oncall
    annotations:
      summary: "SLO burn rate FAST - consuming error budget too quickly"
  
  # Pod restart
  - alert: PodRestartingFrequently
    expr: |
      rate(kube_pod_container_status_restarts_total[15m]) > 0.1
    for: 5m
    labels:
      severity: warning
    annotations:
      summary: "Pod {{ $labels.pod }} restarting frequently"
  
  # Disk space
  - alert: DiskSpaceLow
    expr: |
      node_filesystem_free_bytes / node_filesystem_size_bytes < 0.1
    for: 5m
    labels:
      severity: warning
    annotations:
      summary: "Disk space < 10% on {{ $labels.instance }}"
```

---

## 7. 📊 Grafana Dashboard

### Golden Signals Dashboard JSON (Excerpt)

```json
{
  "title": "Golden Signals",
  "panels": [
    {
      "title": "Request Rate",
      "type": "graph",
      "targets": [{
        "expr": "sum(rate(http_requests_total[5m])) by (endpoint)",
        "legendFormat": "{{endpoint}}"
      }]
    },
    {
      "title": "Error Rate",
      "type": "graph",
      "targets": [{
        "expr": "sum(rate(http_errors_total[5m])) by (endpoint) / sum(rate(http_requests_total[5m])) by (endpoint)",
        "legendFormat": "{{endpoint}}"
      }],
      "alert": {
        "conditions": [{
          "evaluator": {"type": "gt", "params": [0.01]}
        }]
      }
    },
    {
      "title": "P50 / P95 / P99 Latency",
      "type": "graph",
      "targets": [
        {"expr": "histogram_quantile(0.50, rate(http_request_duration_seconds_bucket[5m]))", "legendFormat": "P50"},
        {"expr": "histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m]))", "legendFormat": "P95"},
        {"expr": "histogram_quantile(0.99, rate(http_request_duration_seconds_bucket[5m]))", "legendFormat": "P99"}
      ]
    },
    {
      "title": "Saturation - Active Connections",
      "type": "graph",
      "targets": [{
        "expr": "active_connections",
        "legendFormat": "Active"
      }]
    }
  ]
}
```

---

## 8. 🎯 SLO Tracking

### `app/slo_tracker.py`

```python
"""
Track SLOs + error budgets.
"""
from prometheus_client import Gauge

# SLO definitions
SLO_AVAILABILITY = 0.999  # 99.9%
SLO_LATENCY_P95 = 0.500   # 500ms

# Gauges to expose current SLO status
slo_availability = Gauge("slo_availability_current", "Current availability")
slo_error_budget = Gauge("slo_error_budget_remaining", "Error budget remaining %")
slo_burn_rate = Gauge("slo_burn_rate", "Error budget burn rate")
```

### SLO Burn Rate Query

```promql
# Error budget burn rate over different windows

# 1-hour burn rate
sum(rate(http_errors_total[1h])) / sum(rate(http_requests_total[1h])) / (1 - 0.999)

# If > 1: faster than allowed
# If > 14.4: will consume 30-day budget in 2 days (CRITICAL)
# If > 6: will consume in 5 days (WARNING)
```

### Multi-Window Burn Rate Alerts

```yaml
# Best practice: alert on burn rate, not just errors
- alert: SLOBurnRate2Pct1Hour
  expr: |
    sum(rate(http_errors_total[1h])) / sum(rate(http_requests_total[1h])) > 14.4 * 0.001
  for: 5m
  labels:
    severity: critical

- alert: SLOBurnRate5Pct6Hours
  expr: |
    sum(rate(http_errors_total[6h])) / sum(rate(http_requests_total[6h])) > 6 * 0.001
  for: 5m
  labels:
    severity: warning
```

---

## 9. 📝 Runbooks

### `runbooks/high-error-rate.md`

```markdown
# Runbook: High Error Rate

## Alert
HighErrorRate firing - error rate > 1% for 5 minutes

## Severity
WARNING / CRITICAL based on duration

## Initial Response (5 minutes)

### Check current state
```bash
# Get current error rate
curl http://prometheus:9090/api/v1/query?query=sum(rate(http_errors_total[5m]))/sum(rate(http_requests_total[5m]))

# Check which endpoints
curl http://prometheus:9090/api/v1/query?query=sum(rate(http_errors_total[5m])) by (endpoint, status)
```

### Check recent changes
```bash
# Recent deployments?
kubectl rollout history deployment/myapp

# Recent config changes?
kubectl get events --sort-by='.metadata.creationTimestamp'
```

## Common Causes

### 1. Database issues
```bash
kubectl exec deploy/postgres -- pg_isready
kubectl logs deploy/postgres --tail=100
```

### 2. Downstream service down
```bash
# Check service mesh dashboard
# Check service health endpoints
curl http://payment-service/health
```

### 3. Bad release
```bash
# Rollback
kubectl rollout undo deployment/myapp
```

## Investigation Tools

- Jaeger: http://jaeger:16686 (find error traces)
- Grafana: http://grafana:3000 (visual investigation)
- Logs: http://grafana:3000/explore (Loki queries)

## Loki Queries

```
# Recent errors
{app="myapp"} |= "ERROR"

# Specific error type
{app="myapp"} |= "ERROR" | json | error="connection timeout"

# By correlation_id
{app="myapp"} | json | correlation_id="abc-123"
```

## Escalation

If not resolved in 15 minutes:
- Page senior on-call
- Notify in #incidents Slack channel
- Begin incident response process

## Post-Incident

After resolution:
- Update runbook with new findings
- Schedule postmortem
- Track action items
```

---

## 10. 🔔 Alertmanager Configuration

### `alertmanager/config.yml`

```yaml
global:
  resolve_timeout: 5m
  slack_api_url: 'https://hooks.slack.com/services/...'
  smtp_smarthost: 'smtp.gmail.com:587'

route:
  group_by: ['alertname', 'severity']
  group_wait: 30s
  group_interval: 5m
  repeat_interval: 4h
  
  receiver: 'team-default'
  
  routes:
    # Critical → page on-call
    - match:
        severity: critical
      receiver: 'pagerduty-critical'
      repeat_interval: 1h
    
    # Warnings → Slack
    - match:
        severity: warning
      receiver: 'slack-warnings'

receivers:
- name: 'team-default'
  email_configs:
    - to: 'team@example.com'

- name: 'pagerduty-critical'
  pagerduty_configs:
    - service_key: 'YOUR_PAGERDUTY_KEY'
      description: '{{ .CommonAnnotations.summary }}'

- name: 'slack-warnings'
  slack_configs:
    - channel: '#alerts'
      title: '⚠️ {{ .CommonAnnotations.summary }}'
      text: '{{ .CommonAnnotations.description }}'
      send_resolved: true

inhibit_rules:
  # If critical alert firing, don't send warnings
  - source_match:
      severity: 'critical'
    target_match:
      severity: 'warning'
    equal: ['alertname']
```

---

## 11. 🌐 Multi-Service Trace Correlation

### Service A (Producer)

```python
@app.post("/orders")
async def create_order(req):
    # Auto-instrumented - trace continues to downstream services
    
    async with httpx.AsyncClient() as client:
        # Trace context automatically propagated via headers
        inventory_response = await client.post(
            "http://inventory-service/reserve",
            json={"items": req["items"]}
        )
        
        payment_response = await client.post(
            "http://payment-service/charge",
            json={"amount": req["amount"]}
        )
    
    return {"order_id": "..."}
```

### Service B (Consumer)

```python
# Auto-instrumented - trace context auto-extracted from headers
@app.post("/reserve")
async def reserve_inventory(req):
    # All operations here are part of the same trace!
    
    async with db.transaction():
        # DB queries traced
        result = await db.fetch("SELECT * FROM inventory ...")
    
    return {"reserved": True}
```

### View in Jaeger

```
http://localhost:16686

Service: order-service
   ↓ Search by trace
   
Trace:
   order-service: POST /orders         (1500ms total)
   ├─ inventory-service: POST /reserve  (200ms)
   │   └─ postgres: SELECT FROM inventory (50ms)
   ├─ payment-service: POST /charge     (1200ms)  ← BOTTLENECK!
   │   └─ stripe-api: POST /charges     (1100ms)
   └─ db.save_order                     (50ms)
```

---

## 12. 🧪 Chaos Engineering

### Inject Failures

```python
"""Verify observability captures real failures"""
import random

@app.post("/orders")
async def create_order(req):
    # Chaos: randomly fail
    if os.getenv("CHAOS_MODE") == "true" and random.random() < 0.1:
        logger.error("Simulated failure")
        raise HTTPException(500, "Simulated failure")
    
    if random.random() < 0.05:
        # Simulate slow response
        await asyncio.sleep(5)
    
    return await process_order(req)
```

```bash
# Enable chaos
$ kubectl set env deployment/myapp CHAOS_MODE=true

# Watch alerts fire!
# Verify:
# - Error rate alerts trigger
# - Latency alerts trigger
# - Traces show errors
# - Logs capture failures
```

---

## 13. Key Learnings Summary

```
✅ Structured JSON logs with correlation IDs
✅ Prometheus metrics (counters, gauges, histograms)
✅ Four golden signals tracked
✅ OpenTelemetry auto-instrumentation
✅ Jaeger for distributed tracing
✅ Grafana dashboards for visualization
✅ SLO definition + burn rate alerts
✅ Runbooks for on-call response
✅ Alertmanager routing
✅ Chaos testing validates observability

🎯 Production observability stack:
   Logs: stdout → Promtail → Loki → Grafana
   Metrics: app → Prometheus → Grafana + Alertmanager
   Traces: app → OTLP → Jaeger → Grafana
   All unified in Grafana for single-pane-of-glass
```

---

## 🎬 Section Complete!

Congratulations! You've completed **Section 7: Cloud-Native & Scalable Architecture Styles**!

### Files Created (14 total)

```
Section_07_Cloud_Native_Scalable/
├── 01_Cloud_Service_Models.md
├── 01_Practical_Hands_On.md
├── 02_12_Factor_App.md
├── 02_Practical_Hands_On.md
├── 03_Serverless_Architecture.md
├── 03_Practical_Hands_On.md
├── 04_Docker_Kubernetes.md
├── 04_Practical_Hands_On.md
├── 05_Load_Balancing_Auto_Scaling.md
├── 05_Practical_Hands_On.md
├── 06_Edge_Architecture.md
├── 06_Practical_Hands_On.md
├── 07_Observability.md
└── 07_Practical_Hands_On.md  ← you are here
```

### What You Can Now Build

```
✓ Cloud architectures across all service models
✓ 12-factor compliant applications
✓ Serverless event-driven systems
✓ Containerized apps on Kubernetes
✓ Auto-scaling load-balanced systems
✓ Edge-optimized global apps
✓ Fully observable systems
```

---

## 🚀 Next Steps

Continue with:
- **Section 8**: UI Architecture Patterns
- **Section 9**: Architectural Decision-Making
- **Section 10**: Conclusion & Next Steps

---

## 📚 Try It Yourself

1. Set up **full observability stack** locally
2. Build **custom Grafana dashboards** for your app
3. Define **SLOs** for your services + track burn rate
4. Run **chaos experiments** + verify alerts fire
5. Write **runbooks** for top 5 alerts
