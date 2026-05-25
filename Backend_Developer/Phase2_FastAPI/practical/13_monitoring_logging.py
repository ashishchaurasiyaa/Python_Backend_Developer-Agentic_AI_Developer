"""
PHASE 2 FastAPI — Practical 13: Monitoring, Metrics + Structured Logging
Run: uvicorn 13_monitoring_logging:app --reload
Docs: http://127.0.0.1:8000/docs
Metrics: http://127.0.0.1:8000/metrics  (Prometheus scrape endpoint)

Install: pip install prometheus-fastapi-instrumentator structlog python-json-logger

Topics:
  - Prometheus metrics — request count, latency, error rate
  - Custom metrics — business counters, gauges, histograms
  - /metrics endpoint for Prometheus scraping
  - structlog — structured JSON logging
  - Request context binding (request_id, user_id in every log)
  - Log levels + production config
  - Correlation ID propagation
  - Sentry integration pattern
"""

from __future__ import annotations

import logging
import time
import uuid
from contextlib import asynccontextmanager
from typing import Callable, Optional

import structlog
from fastapi import FastAPI, Request, Response, status
from fastapi.responses import JSONResponse
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    Counter,
    Gauge,
    Histogram,
    Summary,
    generate_latest,
    multiprocess,
    CollectorRegistry,
)
from prometheus_fastapi_instrumentator import Instrumentator
from pydantic import BaseModel
from starlette.middleware.base import BaseHTTPMiddleware


# ═══════════════════════════════════════════════════════
# SECTION 1: Structured Logging Setup (structlog)
# ═══════════════════════════════════════════════════════

def setup_structlog(json_logs: bool = False):
    """
    Configure structlog.
    Development: colored console output
    Production:  JSON output for log aggregators (ELK, Loki, CloudWatch)
    """
    shared_processors = [
        structlog.contextvars.merge_contextvars,          # add bound context vars
        structlog.stdlib.add_log_level,                   # add "level" key
        structlog.stdlib.add_logger_name,                 # add "logger" key
        structlog.processors.TimeStamper(fmt="iso"),      # ISO timestamp
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    if json_logs:
        # Production: JSON lines (parseable by ELK, Loki, etc.)
        processors = shared_processors + [
            structlog.processors.dict_tracebacks,
            structlog.processors.JSONRenderer(),          # output as JSON
        ]
    else:
        # Development: colored, pretty console
        processors = shared_processors + [
            structlog.dev.ConsoleRenderer(colors=True),
        ]

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(logging.DEBUG),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


# Initialize (False = colored console for development)
setup_structlog(json_logs=False)

log = structlog.get_logger("app")


# ═══════════════════════════════════════════════════════
# SECTION 2: Custom Prometheus Metrics
# ═══════════════════════════════════════════════════════

# ─── Counters (only go up) ───
http_requests_total = Counter(
    "http_requests_total",
    "Total HTTP requests",
    labelnames=["method", "endpoint", "status_code"],
)

user_registrations_total = Counter(
    "user_registrations_total",
    "Total user registrations",
    labelnames=["role"],
)

webhook_events_total = Counter(
    "webhook_events_total",
    "Total webhook events received",
    labelnames=["source", "event_type"],
)

errors_total = Counter(
    "errors_total",
    "Total application errors",
    labelnames=["error_type", "endpoint"],
)

# ─── Gauges (can go up and down) ───
active_connections = Gauge(
    "active_websocket_connections",
    "Current active WebSocket connections",
)

active_background_tasks = Gauge(
    "active_background_tasks",
    "Currently running background tasks",
)

cache_size = Gauge(
    "cache_size_items",
    "Number of items in cache",
    labelnames=["cache_name"],
)

# ─── Histograms (measure distributions) ───
llm_response_time = Histogram(
    "llm_response_time_seconds",
    "LLM API response time",
    labelnames=["model", "operation"],
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0],
)

db_query_duration = Histogram(
    "db_query_duration_seconds",
    "Database query execution time",
    labelnames=["operation", "table"],
    buckets=[0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0],
)

request_payload_size = Histogram(
    "request_payload_size_bytes",
    "Request payload size distribution",
    buckets=[100, 1024, 10240, 102400, 1048576],
)

# ─── Summary (percentiles over time window) ───
external_api_latency = Summary(
    "external_api_latency_seconds",
    "External API call latency",
    labelnames=["service"],
)


# ─── Context manager for timing ───
class timer:
    """Context manager for measuring and recording durations."""
    def __init__(self, histogram: Histogram, **labels):
        self.histogram = histogram
        self.labels    = labels
        self._start    = 0.0

    def __enter__(self):
        self._start = time.perf_counter()
        return self

    def __exit__(self, *args):
        duration = time.perf_counter() - self._start
        self.histogram.labels(**self.labels).observe(duration)


# ═══════════════════════════════════════════════════════
# SECTION 3: Structured Logging Middleware
# ═══════════════════════════════════════════════════════

class StructuredLoggingMiddleware(BaseHTTPMiddleware):
    """
    Bind request context to structlog for every request.
    Every log within a request automatically includes:
    request_id, method, path, client_ip
    """

    SKIP_PATHS = {"/metrics", "/health/live", "/favicon.ico"}

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if request.url.path in self.SKIP_PATHS:
            return await call_next(request)

        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        start_time = time.perf_counter()

        # Bind context vars — available in ALL log calls during this request
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            request_id=request_id,
            method=request.method,
            path=request.url.path,
            client_ip=request.client.host if request.client else "unknown",
        )

        # Log request start
        log.info("request_started", query_params=str(request.query_params))

        response = await call_next(request)

        duration_ms = (time.perf_counter() - start_time) * 1000

        # Log request completion with status
        log_fn = log.warning if response.status_code >= 400 else log.info
        log_fn(
            "request_completed",
            status_code=response.status_code,
            duration_ms=round(duration_ms, 2),
        )

        # Add headers
        response.headers["X-Request-ID"]    = request_id
        response.headers["X-Response-Time"] = f"{duration_ms:.2f}ms"

        # Record Prometheus metric
        http_requests_total.labels(
            method=request.method,
            endpoint=request.url.path,
            status_code=response.status_code,
        ).inc()

        return response


# ═══════════════════════════════════════════════════════
# SECTION 4: Business Metric Helpers
# ═══════════════════════════════════════════════════════

def track_user_registration(role: str = "user"):
    """Call this when a user registers."""
    user_registrations_total.labels(role=role).inc()
    log.info("user_registered", role=role)


def track_llm_call(model: str, operation: str, duration_seconds: float, tokens: int = 0):
    """Track every LLM API call."""
    llm_response_time.labels(model=model, operation=operation).observe(duration_seconds)
    log.info("llm_call", model=model, operation=operation,
             duration_s=round(duration_seconds, 3), tokens=tokens)


def track_db_query(operation: str, table: str, duration_seconds: float, rows: int = 0):
    """Track database query performance."""
    db_query_duration.labels(operation=operation, table=table).observe(duration_seconds)
    if duration_seconds > 0.5:  # slow query warning
        log.warning("slow_query", operation=operation, table=table,
                    duration_s=round(duration_seconds, 3), rows=rows)


def track_error(error_type: str, endpoint: str, exc: Exception):
    """Track application errors."""
    errors_total.labels(error_type=error_type, endpoint=endpoint).inc()
    log.error("application_error", error_type=error_type,
              endpoint=endpoint, error=str(exc), exc_info=True)


# ═══════════════════════════════════════════════════════
# SECTION 5: App Setup
# ═══════════════════════════════════════════════════════

@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("app_starting", version="1.0.0", environment="development")

    # Initialize cache metrics
    cache_size.labels(cache_name="redis").set(0)
    cache_size.labels(cache_name="in_memory").set(0)

    yield

    log.info("app_shutting_down")


app = FastAPI(
    title="Monitoring + Structured Logging",
    description="Prometheus metrics + structlog JSON logging for production FastAPI",
    version="1.0.0",
    lifespan=lifespan,
)

# ─── Auto-instrument with prometheus-fastapi-instrumentator ───
# Adds: http_request_duration_seconds, http_requests_total, http_request_size_bytes
Instrumentator(
    should_group_status_codes=True,
    should_ignore_untemplated=True,
    should_respect_env_var=True,
    excluded_handlers=["/metrics", "/health/live"],
).instrument(app).expose(app, endpoint="/metrics", include_in_schema=False)

# ─── Middleware ───
app.add_middleware(StructuredLoggingMiddleware)


# ═══════════════════════════════════════════════════════
# SECTION 6: Routes
# ═══════════════════════════════════════════════════════

@app.get("/", tags=["Root"])
async def root():
    log.info("root_accessed")
    return {
        "message": "Monitoring + Logging Practical",
        "metrics_url": "http://localhost:8000/metrics",
        "tip": "Open /metrics to see Prometheus output",
    }


@app.get("/health/live", tags=["Health"], include_in_schema=False)
async def liveness():
    return {"status": "ok"}


# ─── Simulate various scenarios for demo ───

class UserCreate(BaseModel):
    name: str
    email: str
    role: str = "user"


@app.post("/users", status_code=201, tags=["Demo"])
async def create_user(body: UserCreate):
    """Tracks registration metric + structured log."""
    with timer(db_query_duration, operation="insert", table="users"):
        await __import__("asyncio").sleep(0.01)  # simulate DB write

    track_user_registration(role=body.role)
    cache_size.labels(cache_name="in_memory").inc()

    log.info("user_created", user_email=body.email, role=body.role)
    return {"id": str(uuid.uuid4())[:8], **body.model_dump()}


@app.get("/llm/generate", tags=["Demo"])
async def llm_generate(prompt: str = "Hello", model: str = "gpt-4o"):
    """Simulates LLM call with timing metric."""
    import asyncio, random

    start = time.perf_counter()
    await asyncio.sleep(random.uniform(0.5, 2.0))  # simulate LLM latency
    duration = time.perf_counter() - start
    tokens   = len(prompt.split()) * 10

    track_llm_call(model=model, operation="chat_completion",
                   duration_seconds=duration, tokens=tokens)

    return {
        "response": f"Response to: {prompt}",
        "model": model,
        "tokens": tokens,
        "latency_ms": round(duration * 1000, 2),
    }


@app.get("/db/slow-query", tags=["Demo"])
async def slow_query_demo():
    """Simulates a slow DB query — triggers slow_query warning log."""
    import asyncio
    start = time.perf_counter()
    await asyncio.sleep(0.8)  # simulate slow query
    duration = time.perf_counter() - start

    track_db_query(operation="select", table="large_table",
                   duration_seconds=duration, rows=50000)

    return {"query_time_ms": round(duration * 1000, 2), "rows": 50000}


@app.get("/error/demo", tags=["Demo"])
async def error_demo():
    """Triggers error tracking metric."""
    try:
        raise ValueError("Demo business logic error")
    except ValueError as e:
        track_error(error_type="ValueError", endpoint="/error/demo", exc=e)
        raise __import__("fastapi").HTTPException(status_code=400, detail=str(e))


@app.get("/ws/gauge-demo", tags=["Demo"])
async def ws_gauge_demo(action: str = "connect"):
    """Simulate WebSocket gauge changes."""
    if action == "connect":
        active_connections.inc()
        log.info("ws_connected", total=active_connections._value.get())
    elif action == "disconnect":
        active_connections.dec()
        log.info("ws_disconnected", total=active_connections._value.get())
    return {"action": action, "active_connections": active_connections._value.get()}


@app.get("/metrics/summary", tags=["Metrics"])
async def metrics_summary():
    """Human-readable metrics summary."""
    return {
        "note": "For Prometheus format, visit /metrics",
        "key_metrics": {
            "total_requests":          "http_requests_total",
            "request_duration_p99":    "http_request_duration_seconds",
            "active_ws_connections":   "active_websocket_connections",
            "user_registrations":      "user_registrations_total",
            "llm_response_time_p95":   "llm_response_time_seconds",
            "db_query_duration_p99":   "db_query_duration_seconds",
            "error_rate":              "errors_total",
        },
        "grafana_setup": {
            "datasource": "Add Prometheus datasource pointing to :8000/metrics",
            "dashboard":  "Import FastAPI dashboard ID: 14898 from grafana.com",
        }
    }


# ═══════════════════════════════════════════════════════
# SECTION 7: Logging Patterns Reference
# ═══════════════════════════════════════════════════════

"""
# ─── Binding context for a request/session ───
structlog.contextvars.bind_contextvars(
    request_id="req-123",
    user_id=42,
    tenant="acme-corp",
)
# All subsequent log calls in this context include these fields

# ─── Temporary extra context ───
log.bind(order_id="ord-456").info("order_created", amount=999.0)

# ─── Log levels ───
log.debug("debug_info",    detail="verbose data")
log.info("event_happened", key="value")
log.warning("slow_op",     duration_ms=600)
log.error("op_failed",     error=str(exc), exc_info=True)
log.critical("db_down",    host="db.prod.internal")

# ─── Production JSON log output ───
# {"event": "request_completed", "status_code": 200, "duration_ms": 45.2,
#  "request_id": "abc-123", "method": "GET", "path": "/users",
#  "level": "info", "timestamp": "2024-01-15T10:30:00Z"}

# ─── Prometheus + Grafana setup ───
# 1. Run app: uvicorn 13_monitoring_logging:app --reload
# 2. Prometheus config (prometheus.yml):
#    scrape_configs:
#      - job_name: 'fastapi'
#        static_configs:
#          - targets: ['localhost:8000']
# 3. Run Prometheus: docker run -p 9090:9090 prom/prometheus
# 4. Run Grafana: docker run -p 3000:3000 grafana/grafana
# 5. Add Prometheus datasource in Grafana → import dashboard 14898

# ─── Key Prometheus queries (PromQL) ───
# Request rate:          rate(http_requests_total[5m])
# Error rate:            rate(http_requests_total{status_code=~"5.."}[5m])
# p99 latency:           histogram_quantile(0.99, rate(http_request_duration_seconds_bucket[5m]))
# LLM p95 latency:       histogram_quantile(0.95, rate(llm_response_time_seconds_bucket[5m]))
# Active WS connections: active_websocket_connections
"""

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("13_monitoring_logging:app", host="0.0.0.0", port=8012, reload=True)
