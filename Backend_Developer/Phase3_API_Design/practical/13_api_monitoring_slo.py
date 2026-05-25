"""
API Monitoring + SLOs — Production Patterns
"""

import logging
import time
from contextlib import contextmanager

from fastapi import FastAPI, Request, Response
from prometheus_client import (
    Counter,
    Histogram,
    Gauge,
    Summary,
    make_asgi_app,
    CollectorRegistry,
    generate_latest,
    CONTENT_TYPE_LATEST,
)


app = FastAPI()
log = logging.getLogger(__name__)


# ==========================================================================
# 1. PROMETHEUS METRICS
# ==========================================================================

REQUEST_COUNT = Counter(
    'http_requests_total',
    'Total HTTP requests',
    labelnames=['method', 'route', 'status'],
)

REQUEST_DURATION = Histogram(
    'http_request_duration_seconds',
    'HTTP request latency in seconds',
    labelnames=['method', 'route'],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)

ACTIVE_REQUESTS = Gauge(
    'http_requests_active',
    'Currently in-flight requests',
    labelnames=['method', 'route'],
)

REQUEST_SIZE = Summary(
    'http_request_size_bytes',
    'Request body size',
    labelnames=['method', 'route'],
)

RESPONSE_SIZE = Summary(
    'http_response_size_bytes',
    'Response body size',
    labelnames=['method', 'route'],
)


# DB metrics
DB_QUERY_DURATION = Histogram(
    'db_query_duration_seconds',
    'DB query time',
    labelnames=['operation', 'table'],
    buckets=(0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0, 5.0),
)

DB_QUERY_COUNT = Counter(
    'db_queries_total',
    'DB query count',
    labelnames=['operation', 'table', 'status'],
)

DB_CONNECTIONS_ACTIVE = Gauge(
    'db_connections_active',
    'Active DB connections',
)


# Cache metrics
CACHE_HITS = Counter(
    'cache_operations_total',
    'Cache hits/misses',
    labelnames=['layer', 'result'],   # result: hit|miss|error
)


# External API
EXTERNAL_API_DURATION = Histogram(
    'external_api_duration_seconds',
    'External API call duration',
    labelnames=['service', 'endpoint', 'status'],
)


# Business metrics
ORDERS_CREATED = Counter('orders_created_total', 'Orders created')
ORDER_VALUE = Histogram(
    'order_value_dollars',
    'Order amounts',
    buckets=(10, 50, 100, 500, 1000, 5000),
)


# ==========================================================================
# 2. MIDDLEWARE INSTRUMENTATION
# ==========================================================================

def normalize_route(request: Request) -> str:
    """Get route template, not raw path (prevent high cardinality)."""
    route = request.scope.get('route')
    if route and hasattr(route, 'path'):
        return route.path
    return request.url.path


@app.middleware('http')
async def prometheus_middleware(request: Request, call_next):
    # Skip /metrics + health
    if request.url.path in ('/metrics', '/health/live', '/health/ready'):
        return await call_next(request)

    method = request.method
    route = normalize_route(request)

    ACTIVE_REQUESTS.labels(method, route).inc()
    start = time.monotonic()

    status = 500
    try:
        response = await call_next(request)
        status = response.status_code
        return response
    finally:
        duration = time.monotonic() - start
        REQUEST_COUNT.labels(method, route, str(status)).inc()
        REQUEST_DURATION.labels(method, route).observe(duration)
        ACTIVE_REQUESTS.labels(method, route).dec()


# Mount /metrics endpoint
app.mount('/metrics', make_asgi_app())


# ==========================================================================
# 3. DB INSTRUMENTATION
# ==========================================================================

@contextmanager
def track_db_query(operation: str, table: str):
    """Wrap DB queries to track latency + count."""
    start = time.monotonic()
    status = 'success'
    try:
        yield
    except Exception:
        status = 'error'
        raise
    finally:
        duration = time.monotonic() - start
        DB_QUERY_DURATION.labels(operation=operation, table=table).observe(duration)
        DB_QUERY_COUNT.labels(operation=operation, table=table, status=status).inc()


# Usage:
# with track_db_query('select', 'users'):
#     users = User.objects.filter(...)


# ==========================================================================
# 4. CACHE INSTRUMENTATION
# ==========================================================================

class InstrumentedCache:
    def __init__(self, layer_name: str):
        self.layer = layer_name

    async def get(self, key):
        try:
            value = await actual_cache.get(key)
            if value is None:
                CACHE_HITS.labels(layer=self.layer, result='miss').inc()
            else:
                CACHE_HITS.labels(layer=self.layer, result='hit').inc()
            return value
        except Exception:
            CACHE_HITS.labels(layer=self.layer, result='error').inc()
            return None


# Mock
class actual_cache:
    @staticmethod
    async def get(key):
        return None


# ==========================================================================
# 5. EXTERNAL API INSTRUMENTATION
# ==========================================================================

import httpx


async def instrumented_get(service: str, endpoint: str, url: str):
    start = time.monotonic()
    status = 'error'

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url)
            status = str(resp.status_code)
            return resp
    finally:
        duration = time.monotonic() - start
        EXTERNAL_API_DURATION.labels(
            service=service,
            endpoint=endpoint,
            status=status,
        ).observe(duration)


# ==========================================================================
# 6. STRUCTURED LOGGING with TRACE ID
# ==========================================================================

import uuid
import structlog
from contextvars import ContextVar


trace_id_var: ContextVar[str] = ContextVar('trace_id', default='-')


def configure_logging():
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt='iso', utc=True),
            structlog.processors.dict_tracebacks,
            structlog.processors.JSONRenderer(),
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
    )


@app.middleware('http')
async def trace_id_middleware(request: Request, call_next):
    # W3C traceparent or generate
    traceparent = request.headers.get('traceparent', '')
    if traceparent and len(traceparent.split('-')) >= 2:
        trace_id = traceparent.split('-')[1]
    else:
        trace_id = uuid.uuid4().hex

    token = trace_id_var.set(trace_id)
    structlog.contextvars.bind_contextvars(
        trace_id=trace_id,
        method=request.method,
        path=request.url.path,
    )

    try:
        response = await call_next(request)
        response.headers['X-Trace-Id'] = trace_id
        return response
    finally:
        trace_id_var.reset(token)
        structlog.contextvars.clear_contextvars()


# ==========================================================================
# 7. OPENTELEMETRY DISTRIBUTED TRACING
# ==========================================================================

"""
# pip install opentelemetry-distro opentelemetry-instrumentation-fastapi \\
#             opentelemetry-instrumentation-sqlalchemy \\
#             opentelemetry-instrumentation-redis \\
#             opentelemetry-instrumentation-httpx \\
#             opentelemetry-exporter-otlp


from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.instrumentation.redis import RedisInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor


# Configure tracer
resource = Resource.create({
    'service.name': 'my-api',
    'service.version': '1.0.0',
    'deployment.environment': os.environ.get('ENV', 'dev'),
})

trace.set_tracer_provider(TracerProvider(resource=resource))

# Export to Jaeger/Tempo/Datadog
otlp_exporter = OTLPSpanExporter(endpoint='http://otel-collector:4317', insecure=True)
trace.get_tracer_provider().add_span_processor(BatchSpanProcessor(otlp_exporter))


# Auto-instrument
FastAPIInstrumentor.instrument_app(app)
SQLAlchemyInstrumentor.instrument()
RedisInstrumentor.instrument()
HTTPXClientInstrumentor.instrument()


# Manual span
tracer = trace.get_tracer(__name__)


@app.get('/article/{id}')
async def get_article(id: int):
    with tracer.start_as_current_span('business_logic'):
        with tracer.start_as_current_span('fetch_from_db'):
            article = await db.get(id)

        with tracer.start_as_current_span('enrich'):
            article['author'] = await fetch_author(article['author_id'])

    return article
"""


# ==========================================================================
# 8. SLI / SLO TRACKING
# ==========================================================================

# Custom SLI metrics
SLO_REQUEST_OUTCOME = Counter(
    'slo_request_outcome',
    'SLI: was request successful (under latency budget)?',
    labelnames=['service', 'endpoint', 'outcome'],   # outcome: success|fail
)


SLO_LATENCY_THRESHOLD_SECONDS = 0.5   # P99 target


@app.middleware('http')
async def slo_middleware(request: Request, call_next):
    if request.url.path in ('/metrics', '/health/live'):
        return await call_next(request)

    start = time.monotonic()
    response = await call_next(request)
    duration = time.monotonic() - start

    # SLO: success = status < 500 AND duration < threshold
    is_success = (
        response.status_code < 500 and
        duration < SLO_LATENCY_THRESHOLD_SECONDS
    )

    SLO_REQUEST_OUTCOME.labels(
        service='my-api',
        endpoint=normalize_route(request),
        outcome='success' if is_success else 'fail',
    ).inc()

    return response


# PromQL queries:
# Current SLI:
#   sum(rate(slo_request_outcome{outcome="success"}[30d])) /
#   sum(rate(slo_request_outcome[30d]))
#
# Error budget remaining (30-day window):
#   1 - 0.999 - error_rate
#
# Burn rate (current vs budget):
#   error_rate_5m / (1 - slo_target)


# ==========================================================================
# 9. ERROR BUDGET DASHBOARD QUERIES
# ==========================================================================

PROMETHEUS_QUERIES = """
# === Golden Signals ===

# Request rate
sum(rate(http_requests_total[5m])) by (route)

# Error rate (5xx)
sum(rate(http_requests_total{status=~"5.."}[5m]))
/
sum(rate(http_requests_total[5m]))

# Error rate (4xx + 5xx)
sum(rate(http_requests_total{status=~"[45].."}[5m]))
/
sum(rate(http_requests_total[5m]))

# P50, P95, P99 latency
histogram_quantile(0.50, sum(rate(http_request_duration_seconds_bucket[5m])) by (le))
histogram_quantile(0.95, sum(rate(http_request_duration_seconds_bucket[5m])) by (le))
histogram_quantile(0.99, sum(rate(http_request_duration_seconds_bucket[5m])) by (le))

# Per-endpoint P99
histogram_quantile(0.99, sum(rate(http_request_duration_seconds_bucket[5m])) by (le, route))

# Saturation
http_requests_active
db_connections_active / db_connections_max


# === SLO Tracking ===

# Current SLI (30-day rolling)
sum(rate(slo_request_outcome{outcome="success"}[30d]))
/
sum(rate(slo_request_outcome[30d]))

# Error budget remaining
1 - 0.999 - (1 - SLI)

# Burn rate (how fast budget consumed)
(1 - SLI_5m) / (1 - 0.999)
# > 1 = burning faster than allowed
# > 14.4 = burning 24h budget in 1h


# === Top 10 slowest endpoints ===
topk(10, histogram_quantile(0.95, sum(rate(http_request_duration_seconds_bucket[5m])) by (le, route)))

# Top 10 highest error rates
topk(10,
    sum(rate(http_requests_total{status=~"5.."}[5m])) by (route)
    /
    sum(rate(http_requests_total[5m])) by (route)
)
"""


# ==========================================================================
# 10. ALERT RULES (Prometheus AlertManager)
# ==========================================================================

ALERT_RULES_YAML = """
groups:
- name: api_slo
  interval: 30s
  rules:
  - alert: HighErrorRate
    expr: |
      sum(rate(http_requests_total{status=~"5.."}[5m]))
      /
      sum(rate(http_requests_total[5m]))
      > 0.05
    for: 5m
    labels:
      severity: page
      service: my-api
    annotations:
      summary: "Error rate > 5% for 5 minutes"
      description: "API serving {{ $value | humanizePercentage }} errors"

  - alert: HighLatency
    expr: |
      histogram_quantile(0.99,
        sum(rate(http_request_duration_seconds_bucket[5m])) by (le)
      ) > 2
    for: 5m
    labels:
      severity: page

  - alert: SLOBudgetBurn
    expr: |
      (
        1 - 0.999 - (
          sum(rate(slo_request_outcome{outcome="success"}[1h]))
          /
          sum(rate(slo_request_outcome[1h]))
        )
      ) < 0
    labels:
      severity: page
    annotations:
      summary: "SLO error budget exhausted in 1h window"

  - alert: SaturationHigh
    expr: db_connections_active / db_connections_max > 0.8
    for: 10m
    labels:
      severity: warn

  - alert: NoTraffic
    expr: |
      sum(rate(http_requests_total[5m])) == 0
    for: 5m
    labels:
      severity: page
    annotations:
      summary: "Zero traffic — service may be down"
"""


# ==========================================================================
# 11. GRAFANA DASHBOARD JSON (excerpt)
# ==========================================================================

GRAFANA_PANELS = """
# Recommended panels for API dashboard:

1. RED Panel
   - Rate: requests/sec
   - Errors: error rate %
   - Duration: P50/P95/P99

2. Per-Endpoint Heatmap
   - Top 10 endpoints
   - Latency heatmap

3. SLO Panel
   - SLO target line
   - Actual SLI over time
   - Error budget remaining %
   - Burn rate

4. Saturation
   - DB connections
   - CPU/memory per pod
   - Queue depth

5. Errors Detail
   - Top error types
   - Error rate per endpoint
   - Error log link
"""


# ==========================================================================
# 12. STRUCTURED LOG EXAMPLES
# ==========================================================================

"""
log.info(
    'request_completed',
    method='GET',
    path='/articles/123',
    status=200,
    duration_ms=42,
    user_id=5,
    trace_id='abc-123',
)

# Query in Loki/Datadog:
# {service="my-api", trace_id="abc-123"} → all logs for request
# {service="my-api"} | json | status >= 500 → all errors
# {service="my-api"} | json | duration_ms > 1000 → slow requests
"""


# ==========================================================================
# 13. SYNTHETIC MONITORING
# ==========================================================================

"""
# External health checks (Datadog Synthetics, Pingdom, Uptime Robot)
# Probe endpoints from multiple regions every 1-5 minutes
# Verify:
# - Endpoint responds 2xx
# - Response time < threshold
# - Response body contains expected content
# - SSL cert valid (not expiring soon)


# Custom synthetics
@shared_task
def synthetic_check():
    \"\"\"Run every 5 minutes — synthetic transaction.\"\"\"

    # Create user
    resp = httpx.post('https://api.example.com/v1/users', json={...})
    assert resp.status_code == 201
    user_id = resp.json()['id']

    # Login
    resp = httpx.post('https://api.example.com/v1/login', json={...})
    assert resp.status_code == 200
    token = resp.json()['token']

    # Use token
    resp = httpx.get(
        'https://api.example.com/v1/me',
        headers={'Authorization': f'Bearer {token}'},
    )
    assert resp.status_code == 200

    # Cleanup
    httpx.delete(f'https://api.example.com/v1/users/{user_id}', ...)


# If fails, page on-call (real user impact)
"""


# ==========================================================================
# 14. PROD CHECKLIST
# ==========================================================================

PROD_CHECKLIST = """
[ ] Prometheus metrics exposed at /metrics
[ ] /metrics behind firewall / auth
[ ] Route templates used (not raw paths) — cardinality control
[ ] P50/P95/P99 latency tracked per endpoint
[ ] Error rate alerts (5xx > N%)
[ ] Latency alerts (P99 > threshold)
[ ] SLO defined + tracked
[ ] Error budget dashboard
[ ] Distributed tracing (OpenTelemetry) enabled
[ ] Trace ID in every log line
[ ] Structured JSON logs
[ ] Log shipping to central system (Loki/Datadog/ELK)
[ ] Alert routing (PagerDuty / OpsGenie)
[ ] Runbooks linked in alert annotations
[ ] Synthetic monitoring for critical user flows
[ ] Dashboard for service owner + SRE
[ ] Postmortem template + blameless culture
"""
