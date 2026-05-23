# FastAPI — Webhooks, APScheduler, Monitoring & Logging

## Quick Concepts
- **Webhook** = HTTP callback — event hone pe external URL pe POST bhejo
- **HMAC-SHA256** = webhook signature verification — tampering detect karo
- **APScheduler** = periodic background jobs — cron, interval triggers
- **Prometheus** = time-series metrics DB — pull-based (scrapes `/metrics`)
- **Counter** = only goes up (requests, errors, signups)
- **Gauge** = up and down (active connections, queue size)
- **Histogram** = distribution (request latency, payload size)
- **structlog** = structured JSON logging — key-value pairs in every log line

---

## Interview Questions & Answers

### Q1: Incoming webhook HMAC verification kaise karte hain?

**Answer:**
```python
import hmac
import hashlib
import time
from fastapi import Request, HTTPException

SECRET = "webhook-secret-key"

async def verify_hmac_signature(request: Request) -> bytes:
    """
    Verify webhook payload wasn't tampered with.

    INTERVIEW: HMAC kaise kaam karta hai?
      sender = HMAC(secret, payload) → signature
      receiver = HMAC(same_secret, received_payload) → expected_sig
      hmac.compare_digest(received_sig, expected_sig) → True/False
      compare_digest = timing-safe comparison (no timing attack)
    """
    body      = await request.body()
    signature = request.headers.get("X-Webhook-Signature", "")

    expected = hmac.new(
        SECRET.encode(), body, hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(f"sha256={expected}", signature):
        raise HTTPException(status_code=401, detail="Invalid webhook signature")

    return body

# Stripe-style with timestamp tolerance (replay attack prevention)
def verify_stripe_signature(payload: bytes, sig_header: str, tolerance: int = 300):
    """
    Stripe signature format: t=1234567890,v1=abc123...
    tolerance = 5 minutes — reject old webhooks (replay attack)
    """
    parts = dict(p.split("=", 1) for p in sig_header.split(","))
    timestamp = int(parts.get("t", 0))
    signature = parts.get("v1", "")

    if abs(time.time() - timestamp) > tolerance:
        raise ValueError("Webhook timestamp too old — possible replay attack")

    signed_payload = f"{timestamp}.{payload.decode()}".encode()
    expected = hmac.new(SECRET.encode(), signed_payload, hashlib.sha256).hexdigest()

    if not hmac.compare_digest(expected, signature):
        raise ValueError("Invalid Stripe webhook signature")
```

---

### Q2: Outgoing webhook — retry with exponential backoff kaise karte hain?

**Answer:**
```python
import asyncio
import httpx
import logging

log = logging.getLogger(__name__)

async def send_webhook(url: str, payload: dict, max_retries: int = 3):
    """
    Send outgoing webhook with exponential backoff retry.

    INTERVIEW: Exponential backoff kyu?
      Linear retry → server already busy pe aur load
      Exponential: 2s → 4s → 8s → spread load, give server time to recover
      + Jitter: random(0, 1)s add karo → thundering herd prevent karo
    """
    async with httpx.AsyncClient(timeout=10.0) as client:
        for attempt in range(1, max_retries + 1):
            try:
                response = await client.post(url, json=payload)
                response.raise_for_status()
                log.info("Webhook delivered: attempt=%d url=%s", attempt, url)
                return response
            except httpx.HTTPStatusError as e:
                if e.response.status_code < 500:
                    # 4xx — client error, don't retry
                    raise
                log.warning("Webhook 5xx: attempt=%d/%d", attempt, max_retries)
            except (httpx.ConnectError, httpx.TimeoutException):
                log.warning("Webhook network error: attempt=%d/%d", attempt, max_retries)

            if attempt < max_retries:
                delay = (2 ** attempt) + (0.1 * attempt)  # exponential + jitter
                await asyncio.sleep(delay)

        raise RuntimeError(f"Webhook failed after {max_retries} attempts: {url}")
```

---

### Q3: APScheduler — periodic jobs FastAPI mein kaise add karte hain?

**Answer:**
```python
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from contextlib import asynccontextmanager
from fastapi import FastAPI

scheduler = AsyncIOScheduler(timezone="UTC")

# ─── Job definitions ───
async def daily_report():
    """Runs at 9 AM UTC every day."""
    print("Generating daily report...")

async def cleanup_expired_tokens():
    """Runs every 30 minutes."""
    print("Cleaning up expired tokens...")

async def health_check_external_services():
    """Runs every 5 minutes."""
    print("Checking external services...")

# ─── Lifespan — start/stop scheduler ───
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Add jobs before starting
    scheduler.add_job(daily_report,
                      CronTrigger(hour=9, minute=0),
                      id="daily_report")
    scheduler.add_job(cleanup_expired_tokens,
                      IntervalTrigger(minutes=30),
                      id="cleanup_tokens")
    scheduler.add_job(health_check_external_services,
                      IntervalTrigger(minutes=5),
                      id="health_check")
    scheduler.start()
    yield
    scheduler.shutdown()

# ─── Runtime job management API ───
@app.post("/scheduler/jobs/{job_id}/pause")
async def pause_job(job_id: str):
    scheduler.pause_job(job_id)
    return {"status": "paused", "job_id": job_id}

@app.post("/scheduler/jobs/{job_id}/resume")
async def resume_job(job_id: str):
    scheduler.resume_job(job_id)
    return {"status": "resumed", "job_id": job_id}

# INTERVIEW: APScheduler vs Celery Beat kab use karo?
# APScheduler:
#   + Simple, in-process, no Redis/RabbitMQ needed
#   + Great for lightweight periodic tasks
#   - Not distributed — only 1 instance runs jobs
#   - Not persistent across restarts (unless jobstore configured)
#   Use: small projects, simple cron jobs

# Celery Beat:
#   + Distributed — multiple workers
#   + Persistent job state in Redis/DB
#   + Retry, chord, chain support
#   Use: production, heavy tasks, distributed systems
```

---

### Q4: Prometheus metrics — Counter, Gauge, Histogram kab use karte hain?

**Answer:**
```python
from prometheus_client import Counter, Gauge, Histogram, Summary

# ─── Counter — sirf badhta hai ───
# Use: total requests, total errors, total signups
http_requests_total = Counter(
    "http_requests_total",
    "Total HTTP requests",
    labelnames=["method", "endpoint", "status_code"],
)

# Increment
http_requests_total.labels(method="GET", endpoint="/users", status_code=200).inc()

# ─── Gauge — up and down ───
# Use: active connections, queue size, cache items, memory usage
active_connections = Gauge("active_websocket_connections", "Active WS connections")
active_connections.inc()    # +1
active_connections.dec()    # -1
active_connections.set(42)  # absolute value

# ─── Histogram — distribution / latency ───
# Use: request duration, payload size, LLM token count
# Creates buckets: count of observations falling in each range
request_duration = Histogram(
    "http_request_duration_seconds",
    "Request duration",
    labelnames=["endpoint"],
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0],
)

import time
start = time.perf_counter()
# ... do work ...
request_duration.labels(endpoint="/users").observe(time.perf_counter() - start)

# Context manager pattern
with request_duration.labels(endpoint="/users").time():
    pass  # automatically records duration

# ─── PromQL queries (Grafana dashboards) ───
# Request rate (per second over 5 min):
#   rate(http_requests_total[5m])
# Error rate:
#   rate(http_requests_total{status_code=~"5.."}[5m])
# p99 latency:
#   histogram_quantile(0.99, rate(http_request_duration_seconds_bucket[5m]))
# Active connections:
#   active_websocket_connections
```

---

### Q5: structlog — structured JSON logging kaise setup karte hain?

**Answer:**
```python
import structlog
import logging

def setup_logging(json_logs: bool = False):
    """
    Development: colored console
    Production:  JSON lines (parseable by ELK/Loki/CloudWatch)
    """
    shared_processors = [
        structlog.contextvars.merge_contextvars,   # bind_contextvars se add hoga
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    if json_logs:
        processors = shared_processors + [structlog.processors.JSONRenderer()]
    else:
        processors = shared_processors + [structlog.dev.ConsoleRenderer(colors=True)]

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(logging.DEBUG),
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )

log = structlog.get_logger("app")

# ─── Request context binding ───
# Middleware mein:
structlog.contextvars.clear_contextvars()
structlog.contextvars.bind_contextvars(
    request_id="req-abc-123",
    method="GET",
    path="/users",
    user_id=42,
)
# Ab is request ke baad ke SAARE log calls mein ye fields automatically aayenge

log.info("user_fetched", email="user@test.com")
# Output: {"event": "user_fetched", "email": "user@test.com",
#           "request_id": "req-abc-123", "method": "GET", "level": "info"}

# ─── Temporary extra context ───
log.bind(order_id="ord-456").info("order_created", amount=999.0)

# ─── Log levels ───
log.debug("debug_info", detail="verbose data")
log.info("event_happened", key="value")
log.warning("slow_op", duration_ms=600)
log.error("op_failed", error=str(exc), exc_info=True)

# INTERVIEW: structlog vs standard logging?
# Standard logging: positional message string — hard to parse
#   logging.info("User 42 created order 456 for $99")
# structlog: key-value pairs — searchable, filterable
#   log.info("order_created", user_id=42, order_id=456, amount=99)
```

---

### Q6: Prometheus + Grafana setup (production)?

**Answer:**
```yaml
# prometheus.yml — scrape config
scrape_configs:
  - job_name: 'fastapi'
    static_configs:
      - targets: ['localhost:8000']
    metrics_path: '/metrics'
    scrape_interval: 15s
```

```bash
# Docker Compose
docker run -d -p 9090:9090 \
  -v ./prometheus.yml:/etc/prometheus/prometheus.yml \
  prom/prometheus

docker run -d -p 3000:3000 grafana/grafana
# Grafana → Add datasource → Prometheus → http://localhost:9090
# Import dashboard ID: 14898 (FastAPI metrics)
```

```python
# FastAPI mein auto-instrumentation
from prometheus_fastapi_instrumentator import Instrumentator

Instrumentator(
    should_group_status_codes=True,
    excluded_handlers=["/metrics", "/health/live"],
).instrument(app).expose(app, endpoint="/metrics", include_in_schema=False)

# Adds automatically:
# http_request_duration_seconds (histogram)
# http_requests_total (counter)
# http_request_size_bytes (histogram)
```

---

## Summary Table

| Metric Type | Goes | Use For |
|------------|------|---------|
| Counter | Only UP | Total requests, errors, signups |
| Gauge | UP + DOWN | Active connections, queue depth |
| Histogram | N/A | Latency distribution, payload size |
| Summary | N/A | Latency percentiles (pre-computed) |

| Logging Style | Example | Searchable |
|--------------|---------|-----------|
| Standard | `"User 42 created order"` | ❌ |
| structlog JSON | `{"user_id": 42, "event": "order_created"}` | ✅ |

| Scheduler | Best For | Distributed |
|-----------|---------|-------------|
| APScheduler | Simple cron, in-process | ❌ |
| Celery Beat | Heavy tasks, production | ✅ |
