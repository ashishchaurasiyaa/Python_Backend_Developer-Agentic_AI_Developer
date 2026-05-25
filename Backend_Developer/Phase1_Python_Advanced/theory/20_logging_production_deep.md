# Logging Production Deep — structlog, contextvars, JSON, Centralized

## Quick Concepts

**WHAT:**
- **logging** = Python stdlib logging
- **structlog** = Structured logging (key-value pairs, JSON output)
- **dictConfig** = Configure logging via dict (YAML/JSON friendly)
- **contextvars** = Per-task context (request_id propagation)
- **JSON logs** = Machine-readable for ELK/CloudWatch/Loki
- **Log levels** = DEBUG, INFO, WARNING, ERROR, CRITICAL
- **Handlers** = Where logs go (file, console, syslog, HTTP)
- **Filters** = Conditionally include/exclude logs

**WHY production logging matters:**
- Debug production issues without restart
- Audit trail for compliance
- Performance monitoring
- Security alerts

**HOW logging architecture:**

```
┌──────────────────────────────────────────────────┐
│  Application code                                 │
│  ┌────────────────┐                              │
│  │ logger.info(   │                              │
│  │   "user_login",│                              │
│  │    user_id=42) │                              │
│  └────────┬───────┘                              │
└───────────┼──────────────────────────────────────┘
            │
   ┌────────▼─────────┐
   │   Logger         │  (filter level, name)
   └────────┬─────────┘
            │
   ┌────────▼─────────┐
   │   Filters        │  (per-record decisions)
   └────────┬─────────┘
            │
   ┌────────▼─────────┐
   │   Formatters     │  (structure: JSON, text)
   └────────┬─────────┘
            │
   ┌────────▼──────────────┐
   │      Handlers         │  (where to send)
   ├───────────────────────┤
   │  StreamHandler        │  → stdout
   │  FileHandler          │  → file (rotating)
   │  SyslogHandler        │  → syslog
   │  SMTPHandler          │  → email
   │  HTTPHandler          │  → CloudWatch/Datadog
   └───────────────────────┘
```

---

## Interview Questions & Answers

### Q1: Why structlog over stdlib logging?

**Answer:**

**WHAT:** structlog = structured logging with key-value pairs.

**WHY:**
```
Old (text logging):
> 2024-01-15 10:30:45 INFO User Alice (id=42) logged in from 192.168.1.1

Hard to:
- Search by user_id (need regex)
- Filter by IP
- Aggregate by event type
- Send to CloudWatch/Datadog


New (structured JSON):
{
  "timestamp": "2024-01-15T10:30:45Z",
  "level": "info",
  "event": "user_login",
  "user_id": 42,
  "user_name": "Alice",
  "ip": "192.168.1.1"
}

Easy to:
- Query: event=user_login AND user_id=42
- Aggregate: count by event type
- Pipe directly to ELK/CloudWatch
- Index in Splunk
```

**HOW — Basic structlog:**

```python
# pip install structlog

import structlog

# Configure once at startup
structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.add_log_level,
        structlog.processors.JSONRenderer(),  # ⭐ JSON output
    ],
)

log = structlog.get_logger()

# Use anywhere
log.info("user_login", user_id=42, ip="192.168.1.1")
# Output: {"event": "user_login", "user_id": 42, "ip": "192.168.1.1", "level": "info", "timestamp": "2024-01-15T..."}

log.error("payment_failed", order_id=123, error="card_declined")
log.warning("rate_limit_approaching", user_id=42, current=95, limit=100)
```

---

### Q2: Production structlog config?

**Answer:**

**HOW — Full production setup:**

```python
# app/logging_config.py
import logging
import structlog
import sys
from typing import Any

def setup_logging(env: str = "production"):
    """
    Configure structured logging.
    Dev: human-readable
    Prod: JSON for log aggregators
    """
    # Shared processors
    shared_processors = [
        structlog.contextvars.merge_contextvars,  # ⭐ Inject context
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.stdlib.add_logger_name,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.dict_tracebacks,  # ⭐ Exception tracebacks as dicts
    ]

    if env == "production":
        # ⭐ JSON for prod (ELK, CloudWatch)
        processors = shared_processors + [
            structlog.processors.JSONRenderer(),
        ]
    else:
        # ⭐ Pretty colors for dev
        processors = shared_processors + [
            structlog.dev.ConsoleRenderer(colors=True),
        ]

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,  # ⭐ Performance
    )

    # Configure stdlib logging too (for libraries that use it)
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=logging.INFO,
    )

    # ⭐ Tune library loggers
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)


# Call once at startup
setup_logging(env=os.getenv("ENV", "development"))
```

**HOW — Use in app:**

```python
import structlog

log = structlog.get_logger(__name__)


@app.post("/orders")
async def create_order(order: OrderCreate, user: User):
    log.info("creating_order", user_id=user.id, item_count=len(order.items))

    try:
        order_id = await order_service.create(order, user.id)
        log.info("order_created", order_id=order_id, user_id=user.id)
        return {"order_id": order_id}
    except InsufficientInventoryError as e:
        log.warning("inventory_insufficient", item_id=e.item_id, user_id=user.id)
        raise
    except Exception as e:
        log.error("order_creation_failed", error=str(e), exc_info=True)
        raise
```

---

### Q3: contextvars — request_id propagation?

**Answer:**

**WHAT:** Per-task context (works with asyncio + threads).

**WHY:**
- Track request through service
- Correlate logs from same request
- Distributed tracing

**HOW — structlog with contextvars:**

```python
import structlog
import uuid
from contextvars import ContextVar

# Configure structlog to merge contextvars
structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,  # ⭐ Critical
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ],
)

log = structlog.get_logger()


# Middleware: bind context per request
@app.middleware("http")
async def logging_middleware(request, call_next):
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))

    # ⭐ Bind to context — auto-injected in ALL logs from this request
    structlog.contextvars.bind_contextvars(
        request_id=request_id,
        method=request.method,
        path=request.url.path,
    )

    try:
        response = await call_next(request)
        log.info("request_completed", status_code=response.status_code)
        response.headers["X-Request-ID"] = request_id
        return response
    except Exception as e:
        log.error("request_failed", error=str(e), exc_info=True)
        raise
    finally:
        # ⭐ Clear context (important!)
        structlog.contextvars.clear_contextvars()


# In any handler — context auto-injected
@app.get("/users/{user_id}")
async def get_user(user_id: int):
    log.info("fetching_user", user_id=user_id)
    # Output includes: request_id, method, path, user_id

    user = await db.get_user(user_id)
    log.info("user_fetched")
    # Same context still present

    return user
```

**Sample output:**
```json
{"event": "fetching_user", "user_id": 123, "request_id": "abc-123", "method": "GET", "path": "/users/123", "level": "info"}
{"event": "user_fetched", "request_id": "abc-123", "method": "GET", "path": "/users/123", "level": "info"}
```

**HOW — Bind additional context (e.g., user):**

```python
@app.get("/users/{user_id}")
async def get_user(user_id: int, current_user: User = Depends(auth)):
    # ⭐ Bind authenticated user (auto-added to all logs)
    structlog.contextvars.bind_contextvars(
        authenticated_user_id=current_user.id,
        authenticated_user_role=current_user.role,
    )

    log.info("fetching_user", user_id=user_id)
    # Includes: request_id, method, path, user_id, authenticated_user_id, ...
```

---

### Q4: Sensitive data redaction?

**Answer:**

**WHAT:** Remove/mask PII, passwords, tokens from logs.

**WHY:**
- GDPR compliance
- Prevent leaks
- Security audit

**HOW — Custom processor:**

```python
import re
import structlog
from typing import Any

SENSITIVE_KEYS = {
    "password", "token", "api_key", "secret", "authorization",
    "ssn", "credit_card", "cvv", "private_key",
}

def redact_sensitive(logger, method_name, event_dict):
    """Mask sensitive values in log records."""
    for key, value in list(event_dict.items()):
        key_lower = key.lower()

        # Check exact match or substring
        if any(s in key_lower for s in SENSITIVE_KEYS):
            event_dict[key] = "[REDACTED]"

        # Redact card numbers in string values
        elif isinstance(value, str):
            event_dict[key] = re.sub(
                r"\b\d{13,19}\b",  # Card numbers
                "[REDACTED-CARD]",
                value
            )

    return event_dict


# Add to processors
structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        redact_sensitive,  # ⭐ Redact before render
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ],
)


# Usage
log.info("user_login",
         email="alice@x.com",
         password="secret123",  # → [REDACTED]
         token="abc123")        # → [REDACTED]
```

**HOW — Field-level redaction (recursive):**

```python
def redact_recursive(obj):
    """Recursively redact sensitive fields."""
    if isinstance(obj, dict):
        return {
            k: "[REDACTED]" if k.lower() in SENSITIVE_KEYS else redact_recursive(v)
            for k, v in obj.items()
        }
    elif isinstance(obj, list):
        return [redact_recursive(i) for i in obj]
    elif isinstance(obj, str):
        # Mask card-like patterns
        return re.sub(r"\b\d{13,19}\b", "[REDACTED]", obj)
    return obj


def deep_redact_processor(logger, method_name, event_dict):
    return redact_recursive(event_dict)
```

---

### Q5: Log levels strategy?

**Answer:**

**WHAT:** When to use which level.

**HOW — Production rules:**

```python
# ⭐ DEBUG: Detailed dev info (off in prod)
log.debug("query_built", sql="SELECT...", params=[1, 2])

# ⭐ INFO: Normal business events
log.info("user_login", user_id=42)
log.info("order_created", order_id=123)
log.info("payment_processed", amount=99.99)

# ⭐ WARNING: Unexpected but recoverable
log.warning("rate_limit_approaching", current=95, limit=100)
log.warning("cache_miss", key="user-123")
log.warning("retry_attempted", attempt=2, max_attempts=3)

# ⭐ ERROR: Something failed but app continues
log.error("payment_failed", order_id=123, error="card_declined")
log.error("api_call_failed", url="https://...", status=500)

# ⭐ CRITICAL: Immediate attention needed
log.critical("database_unreachable", error="connection refused")
log.critical("disk_full", path="/var/lib/db")
```

**HOW — Production levels:**

```python
# settings.py
import os

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# Override per-module
logging.getLogger("urllib3").setLevel("WARNING")  # Too noisy
logging.getLogger("asyncio").setLevel("WARNING")
logging.getLogger("sqlalchemy.engine").setLevel("WARNING")  # Set DEBUG to see SQL

# App
logging.getLogger("myapp").setLevel(LOG_LEVEL)
```

---

### Q6: Log rotation + retention?

**Answer:**

**WHAT:** Prevent log files from filling disk.

**HOW — RotatingFileHandler (size-based):**

```python
import logging
from logging.handlers import RotatingFileHandler

handler = RotatingFileHandler(
    "/var/log/myapp/app.log",
    maxBytes=100 * 1024 * 1024,  # 100 MB per file
    backupCount=5,                 # Keep 5 old files
)

logger = logging.getLogger("myapp")
logger.addHandler(handler)
```

**HOW — TimedRotatingFileHandler (date-based):**

```python
from logging.handlers import TimedRotatingFileHandler

handler = TimedRotatingFileHandler(
    "/var/log/myapp/app.log",
    when="midnight",      # Rotate at midnight
    interval=1,           # Every day
    backupCount=30,       # Keep 30 days
    encoding="utf-8",
    utc=True,
)
```

**HOW — Production pattern (logrotate, not Python):**

```bash
# /etc/logrotate.d/myapp
/var/log/myapp/*.log {
    daily
    rotate 30
    compress
    delaycompress
    missingok
    notifempty
    create 644 myapp myapp
    sharedscripts
    postrotate
        /usr/bin/killall -SIGUSR1 myapp
    endscript
}
```

**HOW — Containerized (just stdout):**

```python
# In Docker/K8s, log to stdout
# Let orchestrator (CloudWatch, Loki) handle rotation

import sys
import logging

handler = logging.StreamHandler(sys.stdout)
logger = logging.getLogger("myapp")
logger.addHandler(handler)
```

---

### Q7: dictConfig — declarative configuration?

**Answer:**

**WHAT:** Configure logging via dict (YAML/JSON friendly).

**HOW:**

```python
import logging.config

LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,

    "formatters": {
        "default": {
            "format": "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        },
        "json": {
            "()": "pythonjsonlogger.jsonlogger.JsonFormatter",
            "format": "%(asctime)s %(name)s %(levelname)s %(message)s",
        },
    },

    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "level": "INFO",
            "formatter": "json",
            "stream": "ext://sys.stdout",
        },
        "file": {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": "/var/log/myapp/app.log",
            "maxBytes": 100_000_000,
            "backupCount": 5,
            "formatter": "json",
            "level": "INFO",
        },
        "error_file": {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": "/var/log/myapp/errors.log",
            "maxBytes": 100_000_000,
            "backupCount": 5,
            "formatter": "json",
            "level": "ERROR",  # Only errors
        },
        "syslog": {
            "class": "logging.handlers.SysLogHandler",
            "address": "/dev/log",
            "facility": "local0",
            "formatter": "default",
        },
    },

    "loggers": {
        "myapp": {
            "handlers": ["console", "file", "error_file"],
            "level": "INFO",
            "propagate": False,
        },
        "sqlalchemy.engine": {
            "level": "WARNING",
        },
        "urllib3": {
            "level": "WARNING",
        },
    },

    "root": {
        "handlers": ["console"],
        "level": "INFO",
    },
}

logging.config.dictConfig(LOGGING_CONFIG)
```

**HOW — YAML config (cleaner):**

```yaml
# logging.yaml
version: 1
disable_existing_loggers: False

formatters:
  json:
    "()": pythonjsonlogger.jsonlogger.JsonFormatter

handlers:
  console:
    class: logging.StreamHandler
    formatter: json
    level: INFO

loggers:
  myapp:
    handlers: [console]
    level: INFO
```

```python
import logging.config
import yaml

with open("logging.yaml") as f:
    config = yaml.safe_load(f)

logging.config.dictConfig(config)
```

---

### Q8: Centralized logging — CloudWatch, ELK, Loki?

**Answer:**

**WHAT:** Aggregate logs from many services to central system.

**WHY:**
- Search across services
- Long-term retention
- Alerts on patterns
- Compliance

**HOW — CloudWatch (AWS):**

```python
# Option 1: ECS/Lambda auto-ships stdout to CloudWatch
# Just print to stdout — done automatically

# Option 2: Explicit CloudWatch handler
# pip install watchtower

import logging
import watchtower

cloudwatch_handler = watchtower.CloudWatchLogHandler(
    log_group="myapp",
    stream_name="api-server",
    create_log_group=True,
    boto3_session=boto3.Session(),
)

logger = logging.getLogger("myapp")
logger.addHandler(cloudwatch_handler)
```

**HOW — Loki (Grafana stack):**

```python
# Option 1: stdout → Promtail → Loki (recommended)
# Just print JSON to stdout
# Promtail tails and ships to Loki

# Option 2: Direct HTTP to Loki
# pip install python-logging-loki

import logging_loki

handler = logging_loki.LokiHandler(
    url="https://loki.example.com/loki/api/v1/push",
    tags={"app": "myapp", "env": "production"},
    version="1",
)
logger.addHandler(handler)
```

**HOW — ELK / Elasticsearch:**

```python
# Option 1: stdout → Filebeat → Logstash → Elasticsearch
# Just print JSON to stdout

# Option 2: Direct ES handler (less common)
from elasticsearch import Elasticsearch
from cmreslogging.handlers import CMRESHandler

es_handler = CMRESHandler(
    hosts=[{"host": "elasticsearch", "port": 9200}],
    auth_type=CMRESHandler.AuthType.NO_AUTH,
    es_index_name="myapp-logs",
)
logger.addHandler(es_handler)
```

**HOW — Best practice (stdout + collector):**

```
App → stdout (JSON) → CloudWatch / Fluent Bit / Promtail → Backend

Don't:
- Direct ship from app (network failure = lost logs)
- File logs in containers (lost on restart)
- Complex handlers (use simple stdout)

Do:
- JSON to stdout
- Let infrastructure handle shipping
- Use sidecars/agents for buffering
```

---

### Q9: Performance — async logging?

**Answer:**

**WHAT:** Don't block app for log writes.

**WHY:**
- Disk I/O slow
- Network I/O slower (CloudWatch)
- Synchronous logs = latency hit

**HOW — QueueHandler (built-in):**

```python
import logging
import queue
from logging.handlers import QueueHandler, QueueListener

# Create queue
log_queue = queue.Queue(-1)  # Unlimited

# Queue handler (non-blocking, just adds to queue)
queue_handler = QueueHandler(log_queue)
root_logger = logging.getLogger()
root_logger.addHandler(queue_handler)


# Background listener (does actual writing)
file_handler = logging.FileHandler("/var/log/app.log")
listener = QueueListener(log_queue, file_handler)
listener.start()

# App code (non-blocking)
logger.info("Hello")  # Just adds to queue, returns immediately

# On shutdown
listener.stop()
```

**HOW — concurrent_log_handler (thread-safe + fast):**

```python
# pip install concurrent-log-handler

from concurrent_log_handler import ConcurrentRotatingFileHandler

handler = ConcurrentRotatingFileHandler(
    "/var/log/app.log",
    maxBytes=100_000_000,
    backupCount=5,
)
```

**HOW — Sampling (for high-volume):**

```python
import random

class SamplingFilter(logging.Filter):
    """Log only 1% of DEBUG messages."""
    def __init__(self, sample_rate=0.01):
        super().__init__()
        self.sample_rate = sample_rate

    def filter(self, record):
        if record.levelno > logging.DEBUG:
            return True  # Always log warnings+
        return random.random() < self.sample_rate


debug_handler = logging.StreamHandler()
debug_handler.addFilter(SamplingFilter(0.01))
```

---

### Q10: Production logging gotchas?

**Answer:**

**Gotcha 1: Logging in tight loops**

```python
# ❌ BAD: 1M log lines (kill perf, fill disk)
for item in items:
    log.info("processing", item_id=item.id)

# ✅ GOOD: log summary
log.info("processing_batch", item_count=len(items))
for item in items:
    process(item)
log.info("batch_complete", item_count=len(items))
```

**Gotcha 2: Eager string formatting**

```python
# ❌ BAD: formats even if DEBUG disabled
log.debug(f"Expensive: {expensive_computation()}")

# ✅ GOOD: only formats if level enabled
log.debug("expensive", value=expensive_computation())  # structlog
# OR
log.debug("Expensive: %s", expensive_computation())  # stdlib lazy
```

**Gotcha 3: Logging exception info**

```python
# ❌ INCOMPLETE: just message
try:
    do_thing()
except Exception as e:
    log.error("failed", error=str(e))  # No traceback!


# ✅ COMPLETE: full traceback
try:
    do_thing()
except Exception as e:
    log.error("failed", error=str(e), exc_info=True)  # ⭐ Include traceback

# OR with structlog
log.error("failed", exc_info=True)
```

**Gotcha 4: Logger creation overhead**

```python
# ❌ BAD: get logger in hot path
def handler():
    log = logging.getLogger(__name__)  # Slow if called millions
    log.info("...")

# ✅ GOOD: get once at module level
log = logging.getLogger(__name__)  # ⭐ Module level

def handler():
    log.info("...")
```

**Gotcha 5: Forgetting to clear contextvars**

```python
# ❌ BAD: context leaks between requests
async def handle_request(req):
    structlog.contextvars.bind_contextvars(user_id=req.user_id)
    # Context never cleared → leaks to next request!


# ✅ GOOD: clear on completion
async def handle_request(req):
    structlog.contextvars.bind_contextvars(user_id=req.user_id)
    try:
        return await process(req)
    finally:
        structlog.contextvars.clear_contextvars()  # ⭐ Always clear
```

---

## Production Logging Checklist

```markdown
### Configuration
- [ ] structlog configured (not raw logging)
- [ ] JSON output in production
- [ ] Pretty colors in development
- [ ] dictConfig in pyproject.toml or YAML

### Context
- [ ] contextvars for request_id
- [ ] Bind user_id, trace_id
- [ ] Clear context on request end
- [ ] Middleware for request tracking

### Levels
- [ ] DEBUG off in production
- [ ] INFO for business events
- [ ] WARNING for recoverable issues
- [ ] ERROR for failures
- [ ] CRITICAL for outages

### Quality
- [ ] No PII in logs (redaction)
- [ ] No passwords/tokens
- [ ] Card numbers masked
- [ ] Structured fields (not f-strings)
- [ ] Exception info included (exc_info=True)

### Performance
- [ ] Don't log in tight loops
- [ ] Module-level logger creation
- [ ] Async handlers for high volume
- [ ] Sampling for DEBUG/INFO

### Centralization
- [ ] Stdout to CloudWatch/Loki/ELK
- [ ] No file logs in containers
- [ ] Retention policy set
- [ ] Alerts on ERROR+ patterns

### Monitoring
- [ ] Log-based metrics (count by level)
- [ ] Alert on error spikes
- [ ] Dashboard for top errors
- [ ] Runbook links in error messages
```

---

## Sample Production Setup (Complete)

```python
# app/logging_config.py
import logging
import logging.config
import os
import re
import sys
import structlog


SENSITIVE_PATTERNS = re.compile(
    r"\b(password|token|secret|api_key|authorization|ssn|credit_card)\b",
    re.IGNORECASE
)


def redact_processor(logger, method_name, event_dict):
    """Redact sensitive fields."""
    for key in list(event_dict.keys()):
        if SENSITIVE_PATTERNS.search(key):
            event_dict[key] = "[REDACTED]"

        # Mask card numbers
        if isinstance(event_dict[key], str):
            event_dict[key] = re.sub(
                r"\b\d{13,19}\b",
                "[REDACTED-CARD]",
                event_dict[key]
            )

    return event_dict


def setup_logging():
    env = os.getenv("ENV", "development")
    log_level = os.getenv("LOG_LEVEL", "INFO")

    timestamper = structlog.processors.TimeStamper(fmt="iso", utc=True)

    shared_processors = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.stdlib.add_logger_name,
        timestamper,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.dict_tracebacks,
        redact_processor,
    ]

    if env == "production":
        final_processor = structlog.processors.JSONRenderer()
    else:
        final_processor = structlog.dev.ConsoleRenderer(colors=True)

    structlog.configure(
        processors=shared_processors + [final_processor],
        wrapper_class=structlog.stdlib.BoundLogger,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # stdlib config
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=log_level,
    )

    # Tune library loggers
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)


# Call at startup
setup_logging()


# Use
import structlog
log = structlog.get_logger(__name__)
log.info("app_started", env=os.getenv("ENV"))
```
