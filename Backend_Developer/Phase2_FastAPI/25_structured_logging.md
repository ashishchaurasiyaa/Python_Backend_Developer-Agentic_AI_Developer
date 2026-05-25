# Structured Logging — structlog, Correlation IDs, JSON Logs

## Why It Matters

Plain text logs = unparseable in production. Structured (JSON) logs:
- **Searchable** → query by user_id, request_id, status_code
- **Aggregatable** → count errors per endpoint
- **Correlatable** → trace request across services
- **Indexable** → Loki/ELK/Datadog parse automatically

Senior interview: "Production issue, find all requests user X made in last hour." → structured logs make this 10 seconds.

---

## Core Concepts

### structlog Setup

```python
# pip install structlog python-json-logger
import structlog
import logging
import sys


def configure_logging(log_level: str = "INFO", json_format: bool = True):
    timestamper = structlog.processors.TimeStamper(fmt="iso", utc=True)
    shared = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        timestamper,
        structlog.processors.StackInfoRenderer(),
    ]

    if json_format:
        processors = shared + [
            structlog.processors.dict_tracebacks,
            structlog.processors.JSONRenderer(),
        ]
    else:
        processors = shared + [structlog.dev.ConsoleRenderer(colors=True)]

    structlog.configure(
        processors=processors,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, log_level.upper()),
    )


# Use
log = structlog.get_logger()
log.info("user_login", user_id=123, ip="1.2.3.4")
# → {"event": "user_login", "user_id": 123, "ip": "1.2.3.4", "level": "info", "timestamp": "..."}
```

### Correlation ID (Request ID)

```python
from contextvars import ContextVar
import uuid
from fastapi import FastAPI, Request
import structlog


request_id_var: ContextVar[str] = ContextVar('request_id', default='-')


app = FastAPI()


@app.middleware("http")
async def correlation_id_middleware(request: Request, call_next):
    request_id = request.headers.get('x-request-id') or str(uuid.uuid4())
    token = request_id_var.set(request_id)

    # Bind to structlog context
    structlog.contextvars.bind_contextvars(
        request_id=request_id,
        method=request.method,
        path=request.url.path,
        client_ip=request.client.host,
    )

    try:
        response = await call_next(request)
        response.headers['X-Request-ID'] = request_id
        return response
    finally:
        request_id_var.reset(token)
        structlog.contextvars.clear_contextvars()


log = structlog.get_logger()


@app.get("/items/{item_id}")
async def get_item(item_id: int):
    log.info("fetching_item", item_id=item_id)
    return {"id": item_id}

# Log will include request_id automatically!
# {"event": "fetching_item", "item_id": 5, "request_id": "abc-123", ...}
```

### Trace ID Propagation (Distributed Tracing)

```python
import os


@app.middleware("http")
async def trace_id_middleware(request: Request, call_next):
    # Honor incoming trace context (W3C traceparent)
    traceparent = request.headers.get('traceparent', '')
    if traceparent:
        # Format: 00-<trace_id>-<span_id>-<flags>
        parts = traceparent.split('-')
        trace_id = parts[1] if len(parts) >= 2 else None
    else:
        trace_id = uuid.uuid4().hex

    structlog.contextvars.bind_contextvars(trace_id=trace_id)

    response = await call_next(request)
    response.headers['traceparent'] = f'00-{trace_id}-{uuid.uuid4().hex[:16]}-01'
    return response
```

### Request Logging Middleware

```python
import time


@app.middleware("http")
async def access_log_middleware(request: Request, call_next):
    start = time.monotonic()
    log.info("request_started", method=request.method, path=request.url.path)

    try:
        response = await call_next(request)
    except Exception as e:
        duration_ms = int((time.monotonic() - start) * 1000)
        log.exception("request_failed", duration_ms=duration_ms, error=str(e))
        raise

    duration_ms = int((time.monotonic() - start) * 1000)
    log.info(
        "request_completed",
        status=response.status_code,
        duration_ms=duration_ms,
    )
    return response
```

### loguru Alternative (Simpler)

```python
# pip install loguru
from loguru import logger
import sys


logger.remove()
logger.add(
    sys.stdout,
    format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}",
    serialize=True,  # JSON output
    level="INFO",
)


logger.info("user_login", user_id=123)
```

### Auto-Inject User Context

```python
from contextvars import ContextVar
import structlog


current_user_id: ContextVar[int | None] = ContextVar('current_user_id', default=None)


async def get_current_user(...):
    user = await ...
    current_user_id.set(user.id)
    structlog.contextvars.bind_contextvars(user_id=user.id)
    return user


# Now every log line in this request has user_id automatically
```

### Filtering Sensitive Data

```python
SENSITIVE_KEYS = {'password', 'token', 'secret', 'api_key', 'authorization'}


def censor_sensitive(_, __, event_dict):
    for key in list(event_dict.keys()):
        if any(s in key.lower() for s in SENSITIVE_KEYS):
            event_dict[key] = '***'
    return event_dict


# Add to processors chain
structlog.configure(
    processors=[
        # ... others
        censor_sensitive,
        structlog.processors.JSONRenderer(),
    ],
)
```

### Log Levels — When to Use

| Level | Use |
|---|---|
| DEBUG | Verbose, dev-only |
| INFO | Normal flow (request started/completed) |
| WARNING | Recoverable issues (retries, fallbacks) |
| ERROR | Failed requests, exceptions caught |
| CRITICAL | Service-down events |

---

## How It Works Internally

### ContextVar Propagation

ContextVar values propagate through `await` automatically. Each request gets isolated context. No thread-local issues in async.

### structlog Processors Pipeline

```
log.info("event", key=val)
    ↓
processors run in order:
    ↓
add_log_level
    ↓
TimeStamper
    ↓
merge_contextvars
    ↓
... custom processors
    ↓
JSONRenderer → string output
    ↓
Stdlib logging handler → stdout/file
```

### Datadog / ELK Ingestion

JSON logs → log shipper (Fluent Bit / Vector / Filebeat) → backend (Loki / ES / Datadog) → searchable index. Standard fields (`@timestamp`, `level`, `message`) auto-detected.

---

## Common Pitfalls

### 1. Plain Text in Production

```python
print(f"User {user.id} did {action}")  # unparseable
```

### 2. Logging Secrets

```python
log.info("login_attempt", email=email, password=password)  # NEVER
```

Add sanitizer processor.

### 3. Logging in Hot Loops

```python
for row in million_rows:
    log.debug("processing", row_id=row.id)  # I/O bottleneck
```

Use sampling: log every N or only when slow.

### 4. No Correlation ID

Without request_id, can't trace user's journey across logs. Add middleware.

### 5. Stack Trace Disposal

```python
try:
    ...
except Exception as e:
    log.error("failed")  # NO STACK TRACE
```

Use `log.exception()` or pass `exc_info=True`.

### 6. JSON Logs Hard to Read in Dev

```python
# Dev: human-readable
configure_logging(json_format=False)

# Prod: JSON
configure_logging(json_format=True)
```

### 7. Log Size Explosion

GB/day of logs = expensive in Datadog. Sample/rate-limit verbose endpoints. Use INFO+ in prod.

---

## Interview Q&A

**Q1:** Structured logs ka benefit kya hai?
**A:** (1) Query-able — filter by user_id, status, duration. (2) Aggregatable — count errors per endpoint per minute. (3) Correlatable — trace request across services via request_id. (4) Indexed in log platforms (Loki, ELK, Datadog). Plain text logs need regex parsing — fragile.

**Q2:** Correlation ID kaise propagate karte ho?
**A:** Middleware reads `X-Request-ID` header (or generates UUID). Binds to ContextVar → structlog `bind_contextvars`. All log lines in same request include request_id automatically. Forward to downstream services in HTTP calls — they include same ID in their logs.

**Q3:** ContextVar vs threading.local for request context?
**A:** ContextVar is async-aware — propagates through `await`. threading.local breaks in async (multiple coroutines share thread). Use ContextVar for both sync and async FastAPI.

**Q4:** Sensitive data logging se kaise prevent karoge?
**A:** Sanitizer processor in structlog chain — scans event_dict, replaces values for keys like `password`, `token`. Combined with code review (PR checks). Plus structured Pydantic models with `repr=False` for SecretStr fields.

**Q5:** Log levels production mein?
**A:** Default INFO. DEBUG only when troubleshooting (set via env var, no restart needed). WARNING for retries/fallbacks. ERROR for caught exceptions returned to user. CRITICAL for service-down. Sample DEBUG (1% only) if needed.

**Q6:** Trace ID vs request ID?
**A:** Request ID = per-request, generated by edge proxy or app. Trace ID = part of distributed tracing (W3C traceparent), spans multiple services. Use both — trace_id for cross-service, request_id for app-local. structlog binds both to context.

**Q7:** loguru vs structlog?
**A:** loguru = simpler API, less config, JSON serialization built-in. structlog = more flexible processors, better stdlib integration, more configurable. Both fine for FastAPI. structlog is more standard in larger codebases.

**Q8:** Performance impact of logging?
**A:** Async logging (background handler thread/queue) — minimal blocking. JSON serialization cost ~100μs per log line. Hot loops: sample (`log.info(...) if i % 100 == 0`). Avoid log strings in hot path that are then dropped (use lazy formatting).

---

## Real-World Use Cases

### 1. Production Issue Triage

```
# Datadog query
@request_id:abc-123
→ all logs from one user request, including downstream service calls
```

### 2. SLI/SLO Tracking

```
# Aggregate query
status:5xx by:endpoint over 5m
→ identify failing endpoints
```

### 3. Audit Log

```python
log.info(
    "audit_event",
    event_type="user_data_export",
    actor_id=request.state.user_id,
    target_id=target_user_id,
    ip=request.client.host,
    user_agent=request.headers.get('user-agent'),
)
```

---

## References

- [structlog docs](https://www.structlog.org/)
- [loguru](https://github.com/Delgan/loguru)
- [W3C Trace Context](https://www.w3.org/TR/trace-context/)
- Twelve-Factor: Logs (XI)
