"""
Phase3_DevOps — Monitoring + Logging Practical
================================================
Topics covered:
  1. Prometheus metrics in FastAPI (Counter, Histogram, Gauge)
  2. Custom business metrics (request rate, latency p99)
  3. Prometheus alert rules
  4. Structured JSON logging with stdlib
  5. ELK stack patterns (elasticsearch-py)
  6. Loki logging format
  7. SLI/SLO/SLA definitions

Run:
  pip install prometheus-client fastapi uvicorn
  python 04_monitoring_logging_practical.py
"""

import logging
import json
import time
import random
import threading
import os
from datetime import datetime, timezone
from typing import Any

# ─────────────────────────────────────────────────────────────────────────────
# SECTION 1: Prometheus Metrics
# INTERVIEW: 4 metric types — Counter, Gauge, Histogram, Summary
# ─────────────────────────────────────────────────────────────────────────────

print("=" * 60)
print("SECTION 1: Prometheus Metric Types")
print("=" * 60)

METRIC_TYPES = {
    "Counter": {
        "description": "Monotonically increasing — never goes down",
        "use_for":     "requests total, errors total, bytes sent",
        "example":     "http_requests_total{method='POST', status='200'} 1234",
        "query":       "rate(http_requests_total[5m])  → requests/sec",
    },
    "Gauge": {
        "description": "Can go up AND down",
        "use_for":     "active connections, memory usage, queue size, temperature",
        "example":     "active_connections 42",
        "query":       "active_connections > 100  → alert if > 100",
    },
    "Histogram": {
        "description": "Samples observations into configurable buckets",
        "use_for":     "Request latency, response size, DB query time",
        "example":     "http_request_duration_seconds_bucket{le='0.1'} 150",
        "query":       "histogram_quantile(0.99, rate(http_request_duration_seconds_bucket[5m]))",
    },
    "Summary": {
        "description": "Similar to Histogram but calculates quantiles client-side",
        "use_for":     "When you need exact quantiles, not estimates",
        "note":        "Histogram preferred (server-side aggregation, more flexible)",
    },
}

for name, info in METRIC_TYPES.items():
    print(f"\n  {name}:")
    for k, v in info.items():
        print(f"    {k:<12}: {v}")

# Try to use real prometheus_client
try:
    from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST
    PROMETHEUS_AVAILABLE = True

    # ── Define Metrics ──────────────────────────────────────────────
    # INTERVIEW: Use descriptive names with units in name
    http_requests_total = Counter(
        "http_requests_total",
        "Total HTTP requests",
        ["method", "endpoint", "status_code"],
    )

    http_request_duration = Histogram(
        "http_request_duration_seconds",
        "HTTP request duration",
        ["method", "endpoint"],
        buckets=[0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0],
    )

    active_connections = Gauge(
        "active_connections_total",
        "Number of active connections",
    )

    db_query_duration = Histogram(
        "db_query_duration_seconds",
        "Database query duration",
        ["operation", "table"],
        buckets=[0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0],
    )

    # Business metric
    orders_created = Counter(
        "orders_created_total",
        "Total orders created",
        ["plan", "payment_method"],
    )

    cache_hit_ratio = Gauge(
        "cache_hit_ratio",
        "Cache hit ratio (0-1)",
        ["cache_type"],
    )

    print("\n" + "=" * 60)
    print("SECTION 2: Prometheus Metrics Demo (prometheus_client)")
    print("=" * 60)

    # Simulate some metrics
    for _ in range(50):
        method   = random.choice(["GET", "POST", "PUT"])
        endpoint = random.choice(["/users", "/posts", "/auth/login"])
        status   = random.choice(["200", "200", "200", "404", "500"])
        duration = random.gauss(0.1, 0.05)

        http_requests_total.labels(
            method=method, endpoint=endpoint, status_code=status
        ).inc()

        with http_request_duration.labels(method=method, endpoint=endpoint).time():
            time.sleep(max(0, duration * 0.001))  # tiny sleep to simulate

    active_connections.set(random.randint(10, 50))
    orders_created.labels(plan="premium", payment_method="stripe").inc(5)
    cache_hit_ratio.labels(cache_type="redis").set(0.87)

    print("\n  Metrics output (Prometheus text format):")
    output = generate_latest().decode()
    # Show just a few lines
    lines = [l for l in output.split('\n') if l and not l.startswith('#')][:10]
    for line in lines:
        print(f"  {line}")

except ImportError:
    PROMETHEUS_AVAILABLE = False
    print("\n  prometheus_client not installed: pip install prometheus-client")

# FastAPI Integration
PROMETHEUS_FASTAPI_CODE = '''\
# FastAPI + Prometheus middleware
from fastapi import FastAPI, Request, Response
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
import time

app = FastAPI()

REQUEST_COUNT    = Counter("http_requests_total", "Total requests", ["method", "path", "status"])
REQUEST_LATENCY  = Histogram("http_request_duration_seconds", "Latency", ["method", "path"])

@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    duration = time.perf_counter() - start

    path = request.url.path
    REQUEST_COUNT.labels(request.method, path, response.status_code).inc()
    REQUEST_LATENCY.labels(request.method, path).observe(duration)
    return response

# INTERVIEW: /metrics endpoint for Prometheus scraping
@app.get("/metrics")
async def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
'''

print("\n  FastAPI Prometheus Middleware code shown above.")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 3: Prometheus Alert Rules
# INTERVIEW: alertmanager.yml + rules.yml
# ─────────────────────────────────────────────────────────────────────────────

ALERT_RULES = """\
# prometheus/alerts.yml
groups:
  - name: api_alerts
    rules:
      # High error rate
      - alert: HighErrorRate
        expr: |
          rate(http_requests_total{status_code=~"5.."}[5m])
          / rate(http_requests_total[5m]) > 0.05
        for: 2m          # sustained for 2 minutes before firing
        labels:
          severity: critical
        annotations:
          summary:     "High error rate: {{ $value | humanizePercentage }}"
          description: "Error rate exceeds 5% for 2 minutes"

      # High latency
      - alert: HighP99Latency
        expr: |
          histogram_quantile(0.99,
            rate(http_request_duration_seconds_bucket[5m])
          ) > 1.0
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "P99 latency > 1s"

      # Low cache hit ratio
      - alert: LowCacheHitRatio
        expr: cache_hit_ratio{cache_type="redis"} < 0.5
        for: 10m
        labels:
          severity: warning

      # DB connection pool near limit
      - alert: DBConnectionPoolExhausted
        expr: db_pool_checkedout / db_pool_size > 0.9
        for: 1m
        labels:
          severity: critical
"""


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 4: Structured JSON Logging
# INTERVIEW: Logs as data — queryable, filterable, aggregatable
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 60)
print("SECTION 4: Structured JSON Logging")
print("=" * 60)


class JSONFormatter(logging.Formatter):
    """
    INTERVIEW: Structured logging = JSON format per line.
    Queryable in Elasticsearch/Loki: { level: ERROR, service: "api", user_id: 42 }
    """

    def format(self, record: logging.LogRecord) -> str:
        log_data: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level":     record.levelname,
            "logger":    record.name,
            "message":   record.getMessage(),
            "service":   os.getenv("SERVICE_NAME", "api"),
            "environment": os.getenv("ENVIRONMENT", "development"),
        }

        # Include extra fields
        for key in ["user_id", "request_id", "trace_id", "duration_ms",
                    "method", "path", "status_code", "error"]:
            if hasattr(record, key):
                log_data[key] = getattr(record, key)

        # Include exception info
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_data)


def setup_structured_logging():
    handler = logging.StreamHandler()
    handler.setFormatter(JSONFormatter())

    logger = logging.getLogger("app")
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)
    logger.propagate = False
    return logger


app_logger = setup_structured_logging()

# Demo structured log entries
print("\n  Structured JSON log examples:")

app_logger.info(
    "HTTP request processed",
    extra={"user_id": 42, "method": "POST", "path": "/api/orders",
           "status_code": 201, "duration_ms": 45.2, "request_id": "req-abc123"}
)

app_logger.error(
    "Database connection failed",
    extra={"error": "Connection timeout after 5s", "request_id": "req-def456"}
)

app_logger.warning(
    "Rate limit threshold approaching",
    extra={"user_id": 99, "requests_in_window": 85, "limit": 100}
)


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 5: ELK Stack Overview
# INTERVIEW: Elasticsearch + Logstash + Kibana
# ─────────────────────────────────────────────────────────────────────────────

ELK_PATTERN = """\
# ELK Stack Data Flow:
# App → Filebeat → Logstash → Elasticsearch → Kibana

# Python → Elasticsearch directly:
from elasticsearch import AsyncElasticsearch
import asyncio

async def log_to_elasticsearch(log_entry: dict):
    es = AsyncElasticsearch(["http://elasticsearch:9200"])
    await es.index(
        index  = f"logs-{datetime.now().strftime('%Y.%m.%d')}",
        document = log_entry,
    )

# ── Elasticsearch Queries ──────────────────────────────────────
# Find all errors for user 42 in last hour:
query = {
    "query": {
        "bool": {
            "must": [
                {"term":  {"level": "ERROR"}},
                {"term":  {"user_id": 42}},
                {"range": {"timestamp": {"gte": "now-1h"}}},
            ]
        }
    },
    "sort": [{"timestamp": {"order": "desc"}}],
    "size": 100
}
"""

# Loki labels
LOKI_CONFIG = """\
# Loki log labels (Grafana Loki — like Prometheus but for logs)
# Labels should have LOW cardinality (not user_id!)
# Good labels: service, level, environment, region
# Bad labels:  user_id, request_id, trace_id (too many unique values → performance)

# Promtail config (ships logs to Loki):
scrape_configs:
  - job_name: fastapi
    static_configs:
      - targets: [localhost]
        labels:
          service:     api
          environment: production
          __path__:    /var/log/app/*.log

# LogQL query in Grafana:
{service="api", level="ERROR"} | json | duration_ms > 1000
"""


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 6: SLI/SLO/SLA
# INTERVIEW: Service reliability definitions
# ─────────────────────────────────────────────────────────────────────────────

SLI_SLO_SLA = {
    "SLI (Service Level Indicator)": {
        "definition": "Quantitative measure of service behavior",
        "examples": [
            "Availability: % requests returning 2xx/3xx",
            "Latency: % requests < 200ms",
            "Error rate: % requests returning 5xx",
        ]
    },
    "SLO (Service Level Objective)": {
        "definition": "Target value for SLI (internal goal)",
        "examples": [
            "Availability: 99.9% per month",
            "Latency p99 < 500ms for 95% of time",
            "Error rate < 0.1%",
        ]
    },
    "SLA (Service Level Agreement)": {
        "definition": "Contract with customers (with penalties for breach)",
        "examples": [
            "99.9% uptime or 10% bill credit",
            "AWS EC2 SLA: 99.99% region availability",
        ]
    },
    "Error Budget": {
        "definition": "Allowed downtime before SLO breach",
        "example": "99.9% SLO = 43.8 min/month error budget\n"
                   "           Use budget for experiments/risky deploys",
    },
}

print("\n" + "=" * 60)
print("SECTION 6: SLI / SLO / SLA")
print("=" * 60)

for term, info in SLI_SLO_SLA.items():
    print(f"\n  {term}:")
    print(f"    {info['definition']}")
    examples = info.get("examples", [info.get("example", "")])
    for ex in (examples if isinstance(examples, list) else [examples]):
        print(f"    → {ex}")


# ─────────────────────────────────────────────────────────────────────────────
# Main Summary
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 60)
print("MONITORING INTERVIEW QUICK ANSWERS:")
print("=" * 60)
print("  Q: 4 Prometheus metric types?")
print("     Counter (only up), Gauge (up/down), Histogram (buckets), Summary (quantiles)")
print("  Q: Histogram vs Summary?")
print("     Histogram: server calculates quantiles (aggregatable across instances)")
print("     Summary: client calculates (can't aggregate, but more accurate)")
print("  Q: P99 latency query?")
print("     histogram_quantile(0.99, rate(http_request_duration_seconds_bucket[5m]))")
print("  Q: Why structured logging?")
print("     JSON lines = queryable in Elasticsearch/Loki (filter by user_id, error, etc.)")
print("  Q: Error budget?")
print("     99.9% SLO = 43.8 min/month. Use budget wisely for risky deployments.")
print("=" * 60)
