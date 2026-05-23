# 37 — Monitoring & Observability

---

## Three Pillars of Observability

```
┌──────────────────────────────────────────────────────────────┐
│                    OBSERVABILITY                              │
│                                                              │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │   METRICS   │  │    LOGS     │  │      TRACES         │  │
│  │             │  │             │  │                     │  │
│  │ "What is    │  │ "What       │  │ "Where did time     │  │
│  │  happening  │  │  happened   │  │  go across          │  │
│  │  right now" │  │  exactly"   │  │  services"          │  │
│  │             │  │             │  │                     │  │
│  │ Prometheus  │  │ ELK Stack   │  │ OpenTelemetry       │  │
│  │ Grafana     │  │ structlog   │  │ Jaeger / Zipkin     │  │
│  └─────────────┘  └─────────────┘  └─────────────────────┘  │
└──────────────────────────────────────────────────────────────┘
```

| Pillar | Question Answered | Tool | Storage |
|--------|-----------------|------|---------|
| Metrics | Is the system healthy? | Prometheus + Grafana | Time-series DB |
| Logs | What went wrong exactly? | ELK / Loki | Object storage |
| Traces | Where did this request spend time? | Jaeger / Zipkin | Column store |

---

## Metrics — Prometheus

### 4 Metric Types

| Type | Description | Example |
|------|-------------|---------|
| Counter | Monotonically increasing | `http_requests_total` |
| Gauge | Can go up or down | `active_connections`, `memory_bytes` |
| Histogram | Bucketed observations | `request_duration_seconds` |
| Summary | Quantiles over sliding window | `rpc_duration_seconds{quantile="0.99"}` |

### Python Code — prometheus_client

```python
from prometheus_client import Counter, Histogram, Gauge, start_http_server
from starlette.middleware.base import BaseHTTPMiddleware
import time

# Define metrics
REQUEST_COUNT = Counter(
    'http_requests_total',
    'Total HTTP requests',
    ['method', 'endpoint', 'status_code']
)
REQUEST_LATENCY = Histogram(
    'http_request_duration_seconds',
    'HTTP request latency',
    ['endpoint'],
    buckets=[0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0]
)
ACTIVE_CONNECTIONS = Gauge('active_connections', 'Current active connections')
DB_POOL_SIZE = Gauge('db_pool_size', 'Database connection pool size')

# FastAPI Middleware
class PrometheusMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        ACTIVE_CONNECTIONS.inc()
        start = time.perf_counter()
        try:
            response = await call_next(request)
            status = response.status_code
        except Exception:
            status = 500
            raise
        finally:
            duration = time.perf_counter() - start
            endpoint = request.url.path
            REQUEST_COUNT.labels(request.method, endpoint, status).inc()
            REQUEST_LATENCY.labels(endpoint).observe(duration)
            ACTIVE_CONNECTIONS.dec()
        return response

# Expose metrics endpoint
# app.add_middleware(PrometheusMiddleware)
# @app.get("/metrics") → use prometheus_client.make_asgi_app()
```

### PromQL Examples

```promql
# Request rate (per second, 5-minute window)
rate(http_requests_total[5m])

# Error rate
rate(http_requests_total{status_code=~"5.."}[5m])
  / rate(http_requests_total[5m])

# P99 latency from histogram
histogram_quantile(0.99,
  rate(http_request_duration_seconds_bucket[5m])
)

# Availability (successful requests)
1 - (
  rate(http_requests_total{status_code=~"5.."}[30d])
  / rate(http_requests_total[30d])
)
```

---

## Logging — Structured Logs

### Why Structured (JSON) Logs?

```
❌ Plain text:  "2024-01-15 ERROR User 42 failed login from 1.2.3.4 in 12ms"
✅ JSON:        {"timestamp":"2024-01-15T10:30:00Z","level":"ERROR",
                 "event":"login_failed","user_id":42,"ip":"1.2.3.4",
                 "duration_ms":12,"request_id":"abc-123"}
```

JSON logs are **queryable**, **filterable**, and **parseable** by ELK/Loki.

### Python structlog Setup

```python
import structlog
import logging
import sys

def setup_logging(level: str = "INFO"):
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.ExceptionRenderer(),
            structlog.processors.JSONRenderer(),   # → JSON output
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, level)
        ),
        logger_factory=structlog.PrintLoggerFactory(sys.stdout),
        cache_logger_on_first_use=True,
    )

logger = structlog.get_logger()

# Usage
logger.info("user_login", user_id=42, ip="1.2.3.4", duration_ms=12)
logger.error("payment_failed", order_id="ord-789", reason="card_declined",
             amount=99.99, currency="USD")

# Bind context for request lifetime
structlog.contextvars.bind_contextvars(request_id="req-abc-123", user_id=42)
logger.info("processing_started")   # auto-includes request_id, user_id
structlog.contextvars.clear_contextvars()
```

### Log Levels — When to Use

| Level | When | Example |
|-------|------|---------|
| DEBUG | Detailed dev info | SQL queries, variable values |
| INFO | Normal operations | User logged in, order created |
| WARNING | Unexpected but handled | Retry attempt, cache miss |
| ERROR | Operation failed, needs attention | DB connection failed |
| CRITICAL | System-level failure | OOM, data corruption |

### ELK Stack

```
App → Filebeat/Fluentd → Logstash (parse/transform) → Elasticsearch → Kibana
                  OR
App → direct JSON → Elasticsearch → Kibana
```

---

## Distributed Tracing — OpenTelemetry

### Concepts

```
TRACE = one end-to-end request journey
  └── SPAN = one unit of work (service call, DB query)
        ├── attributes (key-value metadata)
        ├── events (timestamped log within span)
        └── status (OK / ERROR)

Context Propagation: traceparent header carries trace_id + span_id across services
W3C format: traceparent: 00-{trace_id}-{parent_span_id}-{flags}
```

### Python — OpenTelemetry

```python
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor

def setup_tracing(service_name: str):
    provider = TracerProvider()
    exporter = OTLPSpanExporter(endpoint="http://jaeger:4317")
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)

    # Auto-instrument FastAPI and SQLAlchemy
    FastAPIInstrumentor.instrument()
    SQLAlchemyInstrumentor.instrument()

tracer = trace.get_tracer(__name__)

# Manual instrumentation
async def process_order(order_id: str):
    with tracer.start_as_current_span("process_order") as span:
        span.set_attribute("order.id", order_id)
        span.set_attribute("service.name", "order-service")

        with tracer.start_as_current_span("validate_payment"):
            span.add_event("payment_validation_started")
            # ... payment logic
            span.add_event("payment_validated")

        with tracer.start_as_current_span("update_inventory") as inv_span:
            try:
                # ... inventory logic
                inv_span.set_status(trace.StatusCode.OK)
            except Exception as e:
                inv_span.set_status(trace.StatusCode.ERROR, str(e))
                inv_span.record_exception(e)
                raise
```

---

## Alerting

### Prometheus AlertManager Rules

```yaml
# alerts.yml
groups:
  - name: slo_alerts
    rules:
      # Fast burn alert: consuming 5% budget in 1 hour (14.4x burn rate)
      - alert: HighErrorRateFastBurn
        expr: |
          (
            rate(http_requests_total{status_code=~"5.."}[1h])
            / rate(http_requests_total[1h])
          ) > 0.001 * 14.4
        for: 2m
        labels:
          severity: critical
          team: backend
        annotations:
          summary: "High error rate - fast SLO burn"
          description: "Error rate {{ $value | humanizePercentage }} exceeds fast burn threshold"

      # Slow burn alert: P99 latency > 500ms
      - alert: HighP99Latency
        expr: |
          histogram_quantile(0.99,
            rate(http_request_duration_seconds_bucket[5m])
          ) > 0.5
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "P99 latency above 500ms"
```

### SLO Burn Rate Alerting (Two Windows)

| Window | Burn Rate | Budget Consumed | Action |
|--------|-----------|-----------------|--------|
| 1h + 5m | 14.4x | 5% in 1h | 🔴 Page immediately |
| 6h + 30m | 6x | 10% in 6h | 🔴 Page immediately |
| 1d + 2h | 3x | 10% in 1d | 🟡 Create ticket |
| 3d + 6h | 1x | 10% in 3d | 🟢 Monitor |

---

## Four Golden Signals (Google SRE)

| Signal | Definition | Example Metric | Alert Condition |
|--------|-----------|----------------|-----------------|
| **Latency** | Time to serve a request | `histogram_quantile(0.99, ...)` | P99 > 500ms |
| **Traffic** | Demand on the system | `rate(http_requests_total[5m])` | Unexpected drop/spike |
| **Errors** | Rate of failed requests | `rate(...{status=~"5.."}[5m])` | Error rate > 0.1% |
| **Saturation** | How "full" the service is | `process_cpu_seconds_total` | CPU > 80% |

### RED Method (for services) vs USE Method (for resources)

```
RED (for microservices):
  Rate     — requests per second
  Errors   — error rate
  Duration — latency distribution

USE (for infrastructure resources):
  Utilization  — % time resource is busy
  Saturation   — queue length / wait time
  Errors       — error events count
```

---

## Health Checks

```python
from fastapi import FastAPI, status
from fastapi.responses import JSONResponse
import asyncpg
import redis.asyncio as aioredis

app = FastAPI()
DATABASE_URL = "postgresql://user:pass@postgres/db"
REDIS_URL = "redis://redis:6379"

@app.get("/health/live")
async def liveness():
    """Kubernetes liveness probe: is process alive?"""
    return {"status": "ok"}

@app.get("/health/ready")
async def readiness():
    """Kubernetes readiness probe: can serve traffic?"""
    checks = {}
    http_status = status.HTTP_200_OK

    # Check PostgreSQL
    try:
        conn = await asyncpg.connect(DATABASE_URL, timeout=2)
        await conn.fetchval("SELECT 1")
        await conn.close()
        checks["postgresql"] = {"status": "ok"}
    except Exception as e:
        checks["postgresql"] = {"status": "error", "detail": str(e)}
        http_status = status.HTTP_503_SERVICE_UNAVAILABLE

    # Check Redis
    try:
        r = aioredis.from_url(REDIS_URL, socket_connect_timeout=2)
        await r.ping()
        await r.close()
        checks["redis"] = {"status": "ok"}
    except Exception as e:
        checks["redis"] = {"status": "error", "detail": str(e)}
        http_status = status.HTTP_503_SERVICE_UNAVAILABLE

    overall = "ready" if http_status == 200 else "degraded"
    return JSONResponse(
        content={"status": overall, "checks": checks},
        status_code=http_status
    )
```

---

## Error Budget Tracking

```python
class ErrorBudgetTracker:
    """
    Track SLO error budget consumption.
    
    Example: 99.9% SLO over 30 days
      Total error budget = 0.1% of 30 days = 43.2 minutes
    """
    def __init__(self, slo_percent: float, window_days: int = 30):
        self.slo = slo_percent / 100
        self.window_seconds = window_days * 86_400
        self.error_budget_total = (1 - self.slo) * self.window_seconds

    def compute(self, total_requests: int, error_requests: int) -> dict:
        if total_requests == 0:
            return {"error": "no data"}

        error_rate   = error_requests / total_requests
        budget_spent = error_rate * self.window_seconds
        budget_remaining = max(0, self.error_budget_total - budget_spent)
        budget_remaining_pct = budget_remaining / self.error_budget_total * 100
        burn_rate = budget_spent / self.error_budget_total

        return {
            "slo_target":            f"{self.slo*100:.2f}%",
            "error_rate":            f"{error_rate:.4%}",
            "budget_total_min":      round(self.error_budget_total / 60, 1),
            "budget_spent_min":      round(budget_spent / 60, 1),
            "budget_remaining_min":  round(budget_remaining / 60, 1),
            "budget_remaining_pct":  f"{budget_remaining_pct:.1f}%",
            "burn_rate":             f"{burn_rate:.2f}x",
            "alert_fast_burn":       burn_rate > 14.4,   # 1h window
            "alert_slow_burn":       burn_rate > 1.0,    # consuming > budget
        }

# Example
tracker = ErrorBudgetTracker(slo_percent=99.9, window_days=30)
report = tracker.compute(total_requests=1_000_000, error_requests=500)
for k, v in report.items():
    print(f"  {k}: {v}")
```

---

## Grafana Dashboard Patterns

```
Dashboard: Service Health Overview
├── Row 1: Traffic
│   ├── RPS by endpoint (line chart)
│   └── Total requests (stat panel)
├── Row 2: Errors
│   ├── Error rate % (gauge, red if > 0.1%)
│   └── Error count by type (bar chart)
├── Row 3: Latency
│   ├── P50/P95/P99 (line chart)
│   └── Latency heatmap
└── Row 4: Saturation
    ├── CPU usage (line chart)
    ├── Memory usage (gauge)
    └── DB connection pool (gauge)
```

---

## Interview Q&A

**Q1: Monitoring vs Observability — what's the difference?**
> Monitoring = watching predefined metrics (you know what to watch). Observability = ability to understand any internal state from external outputs (metrics + logs + traces). Observable systems let you answer questions you didn't know to ask upfront.

**Q2: Why does Prometheus use a pull model instead of push?**
> Pull: Prometheus scrapes targets at configured intervals. Benefits: Prometheus controls the rate, easier to detect dead targets (scrape fails = alert), no need for agents to know Prometheus address. Pushgateway handles ephemeral jobs that can't be scraped.

**Q3: What is the cardinality problem in Prometheus?**
> Each unique combination of label values creates a new time series. High-cardinality labels (user_id, request_id, IP) → millions of series → OOM. Rule: never use unbounded values as labels. Use bounded labels only (method, endpoint, status_code).

**Q4: How does distributed tracing work?**
> A unique trace_id is generated at the entry point (API gateway). It's propagated via HTTP headers (traceparent) to all downstream services. Each service creates spans (units of work) tagged with trace_id + parent_span_id. A trace collector (Jaeger) assembles all spans into a trace waterfall view.

**Q5: What sampling strategies exist for tracing?**
> Head-based (decision at trace start): simple but can miss rare errors. Tail-based (decision after trace complete): can sample 100% of errors, 1% of success — but needs buffer. Adaptive: adjust rate based on traffic volume. For production: 1% head-based + 100% for errors.

**Q6: How to handle high log volume at scale?**
> (1) Structured JSON logs for efficient parsing. (2) Log levels: only INFO+ in prod. (3) Sampling: log 1% of DEBUG for high-traffic paths. (4) Async log shipping: Filebeat/Fluentd with buffering. (5) Log retention tiers: hot (7d in Elasticsearch), warm (30d in S3 + Athena).

**Q7: What is a burn rate alert?**
> If SLO is 99.9% (30d window), error budget = 43.2 min. Burn rate = how fast you're consuming it. 14.4x burn rate means consuming the monthly budget in 1 hour → page immediately. Two windows (fast + slow) reduce false positives.

**Q8: P99 latency vs P50 — which matters more?**
> Both. P50 = median user experience. P99 = worst 1% of users (often hit by large customers). P99.9 = worst 0.1%. SLOs often set on P99. P99 degradation while P50 is fine suggests a subset of requests (specific query, cache miss pattern) is slow.

**Q9: What is OpenTelemetry?**
> Vendor-neutral CNCF standard for instrumentation (metrics, logs, traces). Replaces vendor-specific SDKs. Code once, export to any backend (Jaeger, Datadog, New Relic, Prometheus). Includes auto-instrumentation for popular frameworks (FastAPI, Django, SQLAlchemy, requests).

**Q10: Liveness vs Readiness probe — difference?**
> Liveness: "Is the process alive?" — Kubernetes restarts container if fails. Readiness: "Can it serve traffic?" — Kubernetes removes from load balancer if fails (but doesn't restart). Use readiness to signal during startup (DB connection pending) or graceful shutdown.

**Q11: How to implement distributed log correlation?**
> Generate unique request_id (UUID) at API gateway. Pass as X-Request-ID header to all downstream calls. Log request_id in every log line via structlog contextvars. Now any log from any service for a single request can be found by filtering on request_id in Kibana/Loki.

**Q12: What's the difference between ELK and Loki?**
> ELK (Elasticsearch+Logstash+Kibana): indexes log content → full-text search on any field. Expensive storage. Loki (Grafana): indexes only labels (service, level), stores log content compressed. Cheaper but only label-based filtering + regex. ELK for complex queries, Loki for high-volume cost-efficient logging.

**Q13: How to alert on SLO without too many false positives?**
> Multi-window multi-burn-rate alerting (Google SRE Book Ch 5). Use two time windows: fast (1h, burn=14.4x) for immediate page + slow (6h, burn=6x) for confirmation. Single-window alerts are either too slow or too noisy.

**Q14: What metrics would you track for a payment service?**
> payment_requests_total (by status: success/failed/declined), payment_processing_duration_seconds (histogram), payment_amount_total (counter by currency), third_party_api_errors_total (by provider), fraud_checks_total, refund_requests_total. Alert on: error rate > 0.01%, P99 > 2s, fraud rate spike.

**Q15: What is the USE vs RED method and when to use each?**
> USE (Utilization/Saturation/Errors) = for infrastructure resources (CPU, disk, network). "Is the hardware struggling?" RED (Rate/Errors/Duration) = for services/APIs. "Is the service serving users well?" Use USE in infra dashboards, RED in service dashboards. The Four Golden Signals (Latency/Traffic/Errors/Saturation) combine both.
