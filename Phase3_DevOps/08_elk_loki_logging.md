# ELK / Loki — Logging, Health Checks, Readiness Probes

## Quick Concepts
- **ELK Stack**: Elasticsearch (store) + Logstash (process) + Kibana (visualize)
- **Loki** = Grafana ka log aggregation system — Prometheus jaisa but logs ke liye (lighter than ELK)
- **Structured logging** = JSON format mein logs — searchable aur parseable
- **Health check** = app alive hai ya nahi
- **Readiness probe** = app traffic handle karne ke liye ready hai ya nahi
- **Liveness probe** = app crash hua ya deadlock mein hai ya nahi

---

## Interview Questions & Answers

### Q1: Structured logging Python mein kaise karte hain?
**Answer:**
Plain text logs `grep` se zyada useful nahi hote production mein. JSON logs → search, filter, alert easy hota hai.

```python
import logging
import json
import sys
from datetime import datetime
import structlog

# Option 1: structlog (recommended)
# pip install structlog
structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.stdlib.add_log_level,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.JSONRenderer()
    ],
    wrapper_class=structlog.BoundLogger,
    context_class=dict,
    logger_factory=structlog.PrintLoggerFactory(),
)

log = structlog.get_logger()

# Usage
log.info("order_placed", order_id="123", user_id="456", amount=999.0)
log.error("payment_failed", order_id="123", error="card_declined", attempt=2)

# Output:
# {"event": "order_placed", "order_id": "123", "user_id": "456", "amount": 999.0, "level": "info", "timestamp": "2024-01-15T10:30:00Z"}


# Option 2: Python stdlib with JSON formatter
class JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
        }
        if hasattr(record, "extra"):
            log_data.update(record.extra)
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_data)

handler = logging.StreamHandler(sys.stdout)
handler.setFormatter(JSONFormatter())
logger = logging.getLogger("myapp")
logger.addHandler(handler)
logger.setLevel(logging.INFO)
```

---

### Q2: FastAPI mein request logging middleware kaise banate hain?
**Answer:**
```python
import time
import uuid
import structlog
from fastapi import FastAPI, Request
from starlette.middleware.base import BaseHTTPMiddleware

log = structlog.get_logger()
app = FastAPI()

class LoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = str(uuid.uuid4())
        start_time = time.time()

        # Request log
        log.info(
            "request_started",
            request_id=request_id,
            method=request.method,
            path=request.url.path,
            client_ip=request.client.host,
        )

        # Request ID header se downstream services ko pass karo
        request.state.request_id = request_id

        try:
            response = await call_next(request)
            duration_ms = (time.time() - start_time) * 1000

            log.info(
                "request_completed",
                request_id=request_id,
                method=request.method,
                path=request.url.path,
                status_code=response.status_code,
                duration_ms=round(duration_ms, 2),
            )
            response.headers["X-Request-ID"] = request_id
            return response

        except Exception as exc:
            log.error(
                "request_failed",
                request_id=request_id,
                method=request.method,
                path=request.url.path,
                error=str(exc),
                exc_info=True,
            )
            raise

app.add_middleware(LoggingMiddleware)
```

---

### Q3: Health check endpoint kaise banate hain?
**Answer:**
```python
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncSession
import redis.asyncio as aioredis
from datetime import datetime

app = FastAPI()

@app.get("/health")
async def health_check():
    """Basic liveness check — sirf 200 return karo"""
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}


@app.get("/health/ready")
async def readiness_check(db: AsyncSession = Depends(get_db)):
    """Deep readiness — DB, Redis sab check karo"""
    checks = {}

    # Database check
    try:
        await db.execute("SELECT 1")
        checks["database"] = "ok"
    except Exception as e:
        checks["database"] = f"error: {e}"

    # Redis check
    try:
        redis_client = aioredis.from_url("redis://redis:6379")
        await redis_client.ping()
        checks["redis"] = "ok"
        await redis_client.close()
    except Exception as e:
        checks["redis"] = f"error: {e}"

    all_ok = all(v == "ok" for v in checks.values())
    status_code = 200 if all_ok else 503

    from fastapi.responses import JSONResponse
    return JSONResponse(
        content={"status": "ready" if all_ok else "not_ready", "checks": checks},
        status_code=status_code,
    )
```

---

### Q4: Loki + Promtail setup kaise karte hain? (Grafana Loki — ELK ka lightweight alternative)
**Answer:**
```yaml
# docker-compose.yml mein add karo
services:
  loki:
    image: grafana/loki:latest
    ports:
      - "3100:3100"
    volumes:
      - loki_data:/loki
      - ./monitoring/loki-config.yml:/etc/loki/config.yml:ro
    command: -config.file=/etc/loki/config.yml

  promtail:
    image: grafana/promtail:latest
    volumes:
      - /var/log:/var/log:ro
      - /var/lib/docker/containers:/var/lib/docker/containers:ro
      - ./monitoring/promtail-config.yml:/etc/promtail/config.yml:ro
    command: -config.file=/etc/promtail/config.yml

volumes:
  loki_data:
```

```yaml
# promtail-config.yml
server:
  http_listen_port: 9080

clients:
  - url: http://loki:3100/loki/api/v1/push

scrape_configs:
  - job_name: docker
    static_configs:
      - targets: [localhost]
        labels:
          job: docker
          __path__: /var/lib/docker/containers/*/*.log

  - job_name: fastapi
    static_configs:
      - targets: [localhost]
        labels:
          job: fastapi
          app: myapp
          __path__: /var/log/myapp/*.log
    pipeline_stages:
      - json:
          expressions:
            level: level
            message: message
            request_id: request_id
```

---

### Q5: ELK Stack kaise kaam karta hai? Kab use karna chahiye?
**Answer:**
```
App → Logstash/Filebeat → Elasticsearch → Kibana
```

```yaml
# docker-compose.elk.yml (production ke liye heavy — 4GB+ RAM chahiye)
services:
  elasticsearch:
    image: docker.elastic.co/elasticsearch/elasticsearch:8.11.0
    environment:
      - discovery.type=single-node
      - xpack.security.enabled=true
      - ELASTIC_PASSWORD=changeme
      - "ES_JAVA_OPTS=-Xms1g -Xmx1g"
    volumes:
      - es_data:/usr/share/elasticsearch/data
    ports:
      - "9200:9200"

  logstash:
    image: docker.elastic.co/logstash/logstash:8.11.0
    volumes:
      - ./monitoring/logstash.conf:/usr/share/logstash/pipeline/logstash.conf:ro
    depends_on:
      - elasticsearch

  kibana:
    image: docker.elastic.co/kibana/kibana:8.11.0
    ports:
      - "5601:5601"
    environment:
      - ELASTICSEARCH_HOSTS=http://elasticsearch:9200
      - ELASTICSEARCH_USERNAME=kibana_system
      - ELASTICSEARCH_PASSWORD=changeme
    depends_on:
      - elasticsearch

  filebeat:
    image: docker.elastic.co/beats/filebeat:8.11.0
    volumes:
      - ./monitoring/filebeat.yml:/usr/share/filebeat/filebeat.yml:ro
      - /var/lib/docker/containers:/var/lib/docker/containers:ro
    depends_on:
      - elasticsearch
```

**ELK vs Loki:**
| | ELK | Loki |
|---|---|---|
| Storage | Index-based (high) | Label-based (low) |
| Full-text search | Yes | Limited |
| RAM usage | 4-8GB+ | 500MB |
| Cost | High | Low |
| Best for | Complex log analytics | Simple aggregation + Grafana already use |

---

### Q6: K8s mein readiness vs liveness probe ka fark kya hai?
**Answer:**
```yaml
containers:
  - name: app
    livenessProbe:
      # App crash hua ya deadlock mein hai? → Pod restart karo
      httpGet:
        path: /health        # sirf 200 chahiye
        port: 8000
      initialDelaySeconds: 30   # startup ke liye wait karo
      periodSeconds: 10
      failureThreshold: 3       # 3 fail → restart

    readinessProbe:
      # App traffic handle karne ke liye ready hai? → Ready nahi → traffic mat bhejo
      httpGet:
        path: /health/ready  # DB/Redis bhi check karo
        port: 8000
      initialDelaySeconds: 10
      periodSeconds: 5
      failureThreshold: 3       # 3 fail → Service se remove karo (restart nahi)

    startupProbe:
      # Slow startup apps ke liye — pehle yahi check hoga
      httpGet:
        path: /health
        port: 8000
      failureThreshold: 30      # 30 * 10s = 5 minutes startup time allow
      periodSeconds: 10
```

**Summary:**
- `livenessProbe` fail → **Pod restart**
- `readinessProbe` fail → **Traffic stop** (pod restart nahi, sirf Service se remove)
- `startupProbe` → slow-starting apps ke liye liveness/readiness ko wait karwata hai

---

## Log Levels — Kab Kya Use Karo

```python
import structlog
log = structlog.get_logger()

log.debug("db_query", sql="SELECT...", params={})      # sirf dev mein on raho
log.info("user_login", user_id=123)                    # normal business events
log.warning("rate_limit_approaching", user_id=123)    # kuch galat ho sakta hai
log.error("payment_failed", order_id=456, error="...")  # kuch galat hua — investigate karo
log.critical("db_down", error="connection refused")   # system down — immediately alert
```
