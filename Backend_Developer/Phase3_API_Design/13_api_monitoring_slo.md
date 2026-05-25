# API Monitoring + SLOs

## Why It Matters

You can't improve what you can't measure. Production APIs need:
- **Metrics** — latency, throughput, errors
- **SLIs / SLOs** — quantitative reliability targets
- **Error budgets** — balance reliability vs feature velocity
- **Alerts** — catch issues before users do
- **Tracing** — debug latency across services

Senior interview: "How do you know your API is reliable?" — SLOs + monitoring.

---

## Golden Signals (Google SRE)

### 1. Latency

Time to serve request. Measure P50, P95, P99 (avoid mean — hidden by outliers).

```python
@app.middleware('http')
async def measure_latency(request, call_next):
    start = time.monotonic()
    response = await call_next(request)
    duration = time.monotonic() - start
    REQUEST_DURATION.labels(
        method=request.method,
        path=request.url.path,
        status=response.status_code,
    ).observe(duration)
    return response
```

### 2. Traffic

Requests per second per endpoint.

### 3. Errors

Failed requests (5xx primarily, 4xx contextually).

### 4. Saturation

Resource utilization — CPU, memory, DB connections, queue depth.

---

## RED Method (request-driven)

- **Rate** — requests/second
- **Errors** — error rate %
- **Duration** — latency distribution

```python
from prometheus_client import Counter, Histogram


REQUEST_COUNT = Counter(
    'http_requests_total',
    'HTTP requests',
    ['method', 'path', 'status'],
)

REQUEST_DURATION = Histogram(
    'http_request_duration_seconds',
    'HTTP request latency',
    ['method', 'path'],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)


# Query in PromQL
rate(http_requests_total[5m])                                  # Rate
sum(rate(http_requests_total{status=~"5.."}[5m])) / sum(rate(http_requests_total[5m])) # Error rate
histogram_quantile(0.99, rate(http_request_duration_seconds_bucket[5m]))  # P99 latency
```

---

## USE Method (resource-driven)

- **Utilization** — % time resource busy
- **Saturation** — queue length
- **Errors** — error count

For DB, Redis, CPU, network.

---

## SLI / SLO / SLA

| Term | Definition | Example |
|---|---|---|
| **SLI** | Service Level Indicator (measurement) | "% of requests < 200ms" |
| **SLO** | Service Level Objective (target) | "99% of requests < 200ms" |
| **SLA** | Service Level Agreement (contract) | "Refund if SLO breached" |

### Good SLI Properties

- **User-centric** — measures what users experience
- **Aggregatable** — can roll up across instances
- **Comparable** — same definition over time

### Common SLIs

```
Availability: successful requests / total requests
Latency:      % of requests under threshold
Throughput:   requests handled per second
Correctness:  % of responses matching expected (synthetic)
Freshness:    age of data served
```

### Setting SLOs

```
99.9% availability = 43 min downtime/month
99.95% = 22 min
99.99% = 4 min
```

Match SLO to user expectations. Don't promise 99.99% if 99.5% acceptable.

---

## Error Budget

```
Error budget = 1 - SLO

99.9% SLO → 0.1% error budget
Over 30 days: 0.1% * 30 * 24 * 60 = 43 min "allowed" failure
```

**Usage:**
- Budget remaining → ship features
- Budget exhausted → freeze deploys, fix reliability
- Budget allows risk-taking — chaos engineering, dark launches

---

## Prometheus + FastAPI

```python
from prometheus_client import (
    Counter, Histogram, Gauge,
    CollectorRegistry, generate_latest, CONTENT_TYPE_LATEST,
    make_asgi_app,
)


REQUEST_COUNT = Counter(
    'http_requests_total',
    'Total requests',
    ['method', 'path', 'status'],
)


REQUEST_DURATION = Histogram(
    'http_request_duration_seconds',
    'Request latency',
    ['method', 'path'],
)


ACTIVE_REQUESTS = Gauge(
    'http_requests_active',
    'In-flight requests',
    ['method', 'path'],
)


DB_QUERIES = Histogram(
    'db_query_duration_seconds',
    'DB query duration',
    ['operation', 'table'],
)


CACHE_HITS = Counter(
    'cache_hits_total',
    'Cache hits',
    ['layer', 'result'],
)


# Mount /metrics
app.mount('/metrics', make_asgi_app())
```

### Middleware Instrumentation

```python
@app.middleware('http')
async def prometheus_middleware(request: Request, call_next):
    method = request.method
    path = request.url.path

    # Normalize path (don't explode cardinality)
    path_template = normalize_path(path, request)

    ACTIVE_REQUESTS.labels(method, path_template).inc()
    start = time.monotonic()

    try:
        response = await call_next(request)
        status = response.status_code
    except Exception:
        status = 500
        raise
    finally:
        duration = time.monotonic() - start
        REQUEST_COUNT.labels(method, path_template, str(status)).inc()
        REQUEST_DURATION.labels(method, path_template).observe(duration)
        ACTIVE_REQUESTS.labels(method, path_template).dec()

    return response


def normalize_path(path, request):
    """Replace /users/123 → /users/{id} to limit cardinality."""
    if request.scope.get('route'):
        return request.scope['route'].path
    return path
```

---

## Cardinality Control

```python
# BAD — high cardinality (per user_id, per query string)
REQUEST_COUNT.labels(path='/users/12345?include=profile')
```

Each unique label = separate time series. 1M users = 1M series = Prometheus OOM.

```python
# GOOD — bounded cardinality
REQUEST_COUNT.labels(path='/users/{id}', status='200', method='GET')
```

Rules:
- Use route templates (`/users/{id}` not `/users/123`)
- Don't label by user_id, request_id, trace_id
- Status code as 2xx/3xx/4xx/5xx if too many distinct

---

## Distributed Tracing

OpenTelemetry — standard tracing protocol.

```python
# pip install opentelemetry-distro opentelemetry-instrumentation-fastapi
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor


FastAPIInstrumentor.instrument_app(app)


# Or manual spans
from opentelemetry import trace


tracer = trace.get_tracer(__name__)


@app.get('/article/{id}')
async def get_article(id: int):
    with tracer.start_as_current_span('fetch_from_db'):
        article = await db.get(id)

    with tracer.start_as_current_span('serialize'):
        return ArticleSerializer(article).data
```

Export to Jaeger, Tempo, Datadog, Honeycomb.

### Trace ID Propagation

```python
# W3C traceparent header
async def downstream_call(url):
    async with httpx.AsyncClient() as client:
        # OpenTelemetry instrument auto-injects traceparent
        resp = await client.get(url)
    return resp
```

---

## Structured Logging

```python
import structlog


log = structlog.get_logger()

log.info(
    'request_completed',
    method=request.method,
    path=request.url.path,
    status=response.status_code,
    duration_ms=duration_ms,
    user_id=user.id,
    trace_id=trace_id,
)
```

Logs queryable in Loki/Datadog/Elasticsearch:

```
{level="error", trace_id="abc-123"}
{method="POST", path="/checkout", status>=500}
```

---

## Alerting

### Symptom-Based Alerts (Page Humans)

```yaml
- alert: HighErrorRate
  expr: |
    sum(rate(http_requests_total{status=~"5.."}[5m]))
    /
    sum(rate(http_requests_total[5m]))
    > 0.05
  for: 5m
  labels:
    severity: page
  annotations:
    summary: "Error rate > 5% for 5 minutes"


- alert: HighLatency
  expr: |
    histogram_quantile(0.99, rate(http_request_duration_seconds_bucket[5m])) > 2
  for: 5m
  labels:
    severity: page


- alert: ErrorBudgetExhausted
  expr: |
    (1 - slo_target) - error_rate < 0
  labels:
    severity: page
```

### Cause-Based Alerts (Diagnostic Info)

```yaml
- alert: DBConnectionsHigh
  expr: db_connections_active / db_connections_max > 0.8
  for: 10m
  labels:
    severity: warn

- alert: QueueDepthHigh
  expr: celery_queue_depth > 10000
  for: 15m
```

### Alert Philosophy

- **Page** for user-visible issues (page on-call)
- **Ticket** for non-urgent issues (next business day)
- **Email** for info (no action required)

Don't alert on every blip — alert fatigue kills response.

---

## Dashboards

### Per-Service Dashboard

- Request rate (RED)
- Error rate %
- P50/P95/P99 latency
- Active requests gauge
- DB query times
- Cache hit rate
- External dependency status

### Per-Endpoint Dashboard

- Top 10 slowest endpoints
- Top 10 highest error rate
- Per-endpoint latency distribution

### SLO Dashboard

- SLO target line
- Actual SLI over time
- Error budget remaining
- Burn rate (how fast budget exhausted)

---

## Common Pitfalls

### 1. Measuring Mean Latency Only

Mean hides outliers. Always P50/P95/P99.

### 2. High Label Cardinality

`user_id` as label → millions of series → Prometheus OOM. Use route templates.

### 3. Alerting on Single Sample

```yaml
expr: http_5xx_count > 0
```

Flapping. Use `rate()` over window + `for: 5m`.

### 4. No Trace ID in Logs

User reports error → can't find related logs. Always include trace_id.

### 5. Internal Metrics Endpoint Exposed

`/metrics` reveals internal counters. Restrict via auth, firewall, or separate port.

### 6. SLI Doesn't Match User Experience

Measuring "all requests" but users only care about checkout. Per-endpoint SLOs.

### 7. SLO Too Strict

99.999% SLO costs 100x more than 99.9%. Match user need.

### 8. Logging in Hot Loops

Per-request log = OK. Per-row in loop = log explosion. Sample or aggregate.

---

## Interview Q&A

**Q1:** API health monitoring strategy?
**A:** Golden signals (latency, traffic, errors, saturation) via Prometheus. RED method (Rate, Errors, Duration) per endpoint. SLIs tied to user experience. SLOs as targets. Error budgets balance reliability vs velocity. Alerts on SLO breach + symptom-based (5xx rate, latency P99).

**Q2:** P99 vs P95 vs mean latency?
**A:** Mean hides outliers (90 requests at 10ms + 10 at 1000ms → mean 109ms looks OK). P95 = "95% under this". P99 = "tail experience". For 100k req/min, 1% = 1000 affected users — significant. Always measure P99 for user-facing.

**Q3:** SLO design?
**A:** Choose user-centric SLIs (e.g., "% of checkout requests < 500ms"). Set SLO with stakeholder agreement (99.9% common). Calculate error budget (43 min/month for 99.9%). Track burn rate. Use budget for reliability investments when low, feature work when high.

**Q4:** Cardinality control in Prometheus?
**A:** Each unique label combination = time series. Avoid labels with unbounded values (user_id, query_string, timestamp). Use route templates instead of raw paths. Bucket status codes (2xx/3xx) if needed. Monitor `prometheus_tsdb_head_series` for series count.

**Q5:** Distributed tracing benefits?
**A:** Single request crosses multiple services → tracing connects spans. Visualize latency breakdown (DB 100ms, cache 5ms, external API 300ms). Debug "why is this slow?". Standard: OpenTelemetry, export to Jaeger/Tempo. Correlation via trace_id in logs.

**Q6:** Symptom vs cause alerts?
**A:** Symptom: user-visible (high error rate, latency). Page on-call. Cause: internal indicators (DB conns, queue depth). Often warnings, may not require immediate action. Symptom alerts catch unknown unknowns; cause alerts give diagnostic hints.

**Q7:** Logs vs metrics vs traces — when each?
**A:** Metrics: high-volume, low-cardinality, aggregatable (rate, percentiles). Logs: text, contextual, debuggable (per-request detail). Traces: cross-service request flow, latency breakdown. Use all three — different lenses.

**Q8:** Alert fatigue?
**A:** Too many alerts → ignored → real issues missed. Mitigate: only page for user-visible (SLO breach). Aggregate related (10 errors in 1 minute = 1 alert, not 10). Tune thresholds based on history. Postmortem on every page; remove false positives.

---

## Real-World Use Cases

### 1. SaaS API SLOs

- Availability: 99.95% (per region)
- Latency: 99% of requests < 500ms
- Per-tier: enterprise gets stricter

### 2. LLM API

- TTFT (time to first token): P95 < 1s
- Total completion: P99 < 30s
- Error rate < 1%
- Cost per request tracked

### 3. Payment API

- Availability: 99.99% (4 min/month)
- Idempotent ops: zero data loss
- Latency: P99 < 2s
- Strict SLA with refund clauses

---

## References

- [Google SRE Book](https://sre.google/sre-book/)
- [Prometheus best practices](https://prometheus.io/docs/practices/naming/)
- [OpenTelemetry](https://opentelemetry.io/)
- [Honeycomb on observability](https://www.honeycomb.io/observability)
- [Implementing SLOs (book)](https://www.alex-hidalgo.com/the-book)
