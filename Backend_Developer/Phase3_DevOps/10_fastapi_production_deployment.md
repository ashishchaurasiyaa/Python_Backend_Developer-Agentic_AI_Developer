# FastAPI Production Deployment — Async, Uvicorn, ASGI Stack

## Quick Concepts
- **ASGI server** = FastAPI ke liye production server (Uvicorn) — Django ke WSGI ka async version
- **Gunicorn + Uvicorn workers** = Gunicorn process manager + Uvicorn ASGI workers (best of both)
- **Hypercorn** = Uvicorn ka alternative (HTTP/2, HTTP/3 support)
- **uvloop** = libuv-based event loop — 2-4x faster than default asyncio loop
- **httptools** = C-based HTTP parser — Uvicorn ke saath performance boost
- **FastAPI async-first** = `async def` endpoints non-blocking — single worker bahut zyada requests handle
- **Celery / RQ / ARQ** = background task queue (Django jaisa — FastAPI built-in nahi)
- **Pydantic v2** = serialization + validation (Rust-powered, fast)

---

## When to Use FastAPI vs Django (Quick Decision)

| Criteria | Django | FastAPI |
|---|---|---|
| Admin panel needed | ✅ Built-in | ❌ Build separately |
| ORM needed | ✅ Django ORM | ⚠️ SQLAlchemy (manual) |
| Sync workload (DB queries) | ✅ Fine | ⚠️ Same as Django |
| **Async-heavy (LLM, WebSocket, streaming)** | ❌ Limited | ✅ Built for this |
| **High RPS (10K+ req/s)** | ❌ Slower | ✅ 3-5x faster |
| Team familiarity | Often higher | Newer |
| **AI/Agentic backend** | ⚠️ Possible | ✅ Ideal (async, streaming) |
| **Microservices** | ❌ Heavy | ✅ Lightweight |
| Auth, permissions, middleware | Built-in | Manual (`fastapi-users`) |

**Rule of thumb:** Tumhare YAM-jaise CRUD-heavy ERP → Django. AI agent, real-time chat, LLM streaming, microservice → FastAPI.

---

## Stack Reference (Production FastAPI)

```
Backend:
- Python 3.12 + FastAPI 0.115
- Pydantic v2 (validation + settings)
- SQLAlchemy 2.0 async + Alembic
- PostgreSQL 15 + asyncpg
- Redis 7 (cache + rate limit)
- Celery / ARQ / Dramatiq (background tasks)
- httpx (async HTTP client)
- Uvicorn + Gunicorn (ASGI server)
- structlog (JSON logging)
- python-jose / authlib (JWT)
- OpenTelemetry (tracing)
```

---

## Interview Questions & Answers

### Q1: FastAPI production deployment ka architecture Django se kaise different hai?

**Answer:**
Architecturally similar (ALB + ECS + RDS + Redis), but **3 critical differences**:

```
1. SERVER:
   Django  → Gunicorn (WSGI, sync workers)
   FastAPI → Gunicorn + Uvicorn workers (ASGI, async)
              OR Uvicorn standalone (--workers N)

2. ORM:
   Django  → Django ORM (sync default, async limited)
   FastAPI → SQLAlchemy 2.0 async (asyncpg driver)

3. BACKGROUND TASKS:
   Django  → Celery (mature, Django-integrated)
   FastAPI → 3 options:
              - Celery (heavy but battle-tested)
              - ARQ (Redis-based, async-native, lightweight)
              - Built-in BackgroundTasks (simple, in-process only)
```

**Full architecture:**
```
                ┌──────────┐
                │   ALB    │ (HTTPS)
                └────┬─────┘
                     │
   ┌─────────────────┼─────────────────┐
   │ WEB LAYER (ASYNC)                 │
   │ ┌──────────────▼──┐ ┌─────────────▼─┐
   │ │ ECS Task:        │ │ ECS Task:    │
   │ │ Gunicorn +       │ │ Gunicorn +   │
   │ │ UvicornWorker(s) │ │ UvicornWorker│
   │ │ Port 8000        │ │              │
   │ └──────────────────┘ └──────────────┘
   │
   │ BACKGROUND LAYER:
   │ ┌──────────────────┐ ┌──────────────┐
   │ │ ARQ Worker(s)    │ │ ARQ Cron     │
   │ │ (async tasks)    │ │ (scheduled)  │
   │ └──────────────────┘ └──────────────┘
   │
   │ DATA LAYER:
   │ RDS PostgreSQL (asyncpg) | Redis | S3
```

---

### Q2: FastAPI ke liye Dockerfile production-ready kaise likhoge?

**Answer:**
```dockerfile
# ============================================================
# Stage 1: Builder
# ============================================================
FROM python:3.12-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1

WORKDIR /app

# System deps (asyncpg needs libpq, httptools needs build tools)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Use uv (faster than pip) — optional but recommended
# RUN pip install uv && uv pip install --prefix=/install -r requirements.txt
COPY requirements.txt .
RUN pip install --prefix=/install -r requirements.txt

# ============================================================
# Stage 2: Runtime
# ============================================================
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 curl \
    && rm -rf /var/lib/apt/lists/*

RUN addgroup --system app && adduser --system --ingroup app app

WORKDIR /app
COPY --from=builder /install /usr/local
COPY --chown=app:app . .

USER app
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s \
    CMD curl -f http://localhost:8000/health || exit 1

# ⭐ Production: Gunicorn + UvicornWorker
# Why? Gunicorn = process manager (auto-restart, scaling)
#      UvicornWorker = ASGI async support
CMD ["gunicorn", "app.main:app", \
     "--workers", "4", \
     "--worker-class", "uvicorn.workers.UvicornWorker", \
     "--bind", "0.0.0.0:8000", \
     "--timeout", "120", \
     "--graceful-timeout", "30", \
     "--keep-alive", "5", \
     "--max-requests", "1000", \
     "--max-requests-jitter", "50", \
     "--access-logfile", "-", \
     "--error-logfile", "-", \
     "--log-level", "info"]

# Alternative: Pure Uvicorn (simpler, less production-tested at scale)
# CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", \
#      "--workers", "4", "--loop", "uvloop", "--http", "httptools"]
```

**requirements.txt (production essentials):**
```txt
fastapi==0.115.0
uvicorn[standard]==0.32.0   # includes uvloop + httptools
gunicorn==23.0.0
sqlalchemy[asyncio]==2.0.36
asyncpg==0.30.0
alembic==1.14.0
pydantic==2.10.0
pydantic-settings==2.6.0
redis[hiredis]==5.2.0
httpx==0.27.0
python-jose[cryptography]==3.3.0
passlib[bcrypt]==1.7.4
structlog==24.4.0
sentry-sdk[fastapi]==2.18.0
arq==0.26.0                 # async task queue (Celery alternative)
opentelemetry-instrumentation-fastapi==0.49b0
```

---

### Q3: Gunicorn + UvicornWorker config production ke liye kaise tune karte hain?

**Answer:**

**Worker count formula:**
- **Sync workloads (DB queries):** `(2 × CPU) + 1` (same as Django)
- **Async I/O heavy:** `CPU count` (kyunki ek worker hi 1000s concurrent connections handle karta hai)
- **Mixed:** Start with `CPU count`, monitor, tune

```bash
# Fargate 1 vCPU example
# Async-heavy app: --workers 1 (single worker, async handles concurrency)
# Mixed: --workers 2-4

gunicorn app.main:app \
  --workers 4 \                        # ECS task ke vCPU se match karo
  --worker-class uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8000 \
  --timeout 120 \                      # request timeout
  --graceful-timeout 30 \              # shutdown ke liye 30s
  --keep-alive 5 \                     # connection reuse
  --max-requests 1000 \                # memory leak prevent — worker recycle
  --max-requests-jitter 50 \           # randomize taaki sab ek saath restart na ho
  --backlog 2048 \                     # pending connection queue
  --access-logfile - --error-logfile -
```

**Critical settings explained:**
| Setting | Why |
|---|---|
| `--worker-class uvicorn.workers.UvicornWorker` | ASGI support (FastAPI ke liye MUST) |
| `--max-requests 1000` | Memory leak prevent (sklearn, transformers leak common) |
| `--max-requests-jitter 50` | Workers ek saath restart na ho (thundering herd) |
| `--timeout 120` | Default 30s — LLM/heavy endpoints ke liye 120s safe |
| `--graceful-timeout 30` | Active requests complete hone ka time (zero-downtime) |
| `--keep-alive 5` | HTTP keep-alive — connection reuse |

---

### Q4: Async SQLAlchemy + asyncpg kaise setup karte hain production mein?

**Answer:**
```python
# app/database.py
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from contextlib import asynccontextmanager
from app.config import settings

class Base(DeclarativeBase):
    pass

# ⭐ Async engine with connection pooling
engine = create_async_engine(
    settings.database_url,  # postgresql+asyncpg://user:pass@host/db
    pool_size=10,           # base connections
    max_overflow=20,        # burst connections (max 30 total)
    pool_pre_ping=True,     # dead connection detect
    pool_recycle=3600,      # recycle every hour (avoid stale)
    echo=False,             # SQL logs off in prod
    poolclass=None,         # default QueuePool
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)

# Dependency for FastAPI
async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

# Startup/shutdown hooks
@asynccontextmanager
async def lifespan(app):
    # Startup
    yield
    # Shutdown — close all DB connections gracefully
    await engine.dispose()
```

```python
# app/main.py
from fastapi import FastAPI, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db, lifespan

app = FastAPI(lifespan=lifespan)

@app.get("/users/{user_id}")
async def get_user(user_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()
```

**Settings management (Pydantic v2):**
```python
# app/config.py
from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    
    # Database
    database_url: str          # postgresql+asyncpg://...
    redis_url: str
    
    # Auth
    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    
    # AWS
    aws_region: str = "ap-south-1"
    s3_bucket: str
    
    # CORS
    cors_origins: list[str] = []
    
    # Observability
    sentry_dsn: str | None = None
    environment: str = "production"

@lru_cache
def get_settings() -> Settings:
    return Settings()

settings = get_settings()
```

---

### Q5: Background tasks FastAPI mein kaise handle karte hain? Celery vs ARQ vs BackgroundTasks?

**Answer:**

**3 Options Decision Tree:**

```
Task < 30 seconds + Same process OK?
  → FastAPI BackgroundTasks (built-in, simplest)

Task < 5 min + Need retries/scheduling?
  → ARQ (Redis-based, async-native, lightweight)

Task complex (chains, chords, multiple brokers)?
  → Celery (mature, battle-tested, heavy)
```

**Option 1: BackgroundTasks (built-in)**
```python
from fastapi import BackgroundTasks

@app.post("/send-email")
async def send_email(email: EmailRequest, bg: BackgroundTasks):
    bg.add_task(send_email_smtp, email.to, email.body)
    return {"status": "queued"}

# ⚠️ Runs in SAME process as web — only for quick tasks
# Crashes ke baad lost
```

**Option 2: ARQ (recommended for FastAPI)**
```python
# app/worker.py
from arq import create_pool, cron
from arq.connections import RedisSettings

async def send_email(ctx, to: str, body: str):
    # Async task body
    ...

async def generate_pdf(ctx, quotation_id: int):
    ...

async def daily_sync(ctx):
    # Cron job
    ...

class WorkerSettings:
    functions = [send_email, generate_pdf]
    cron_jobs = [
        cron(daily_sync, hour=2, minute=0),  # 2 AM daily
    ]
    redis_settings = RedisSettings(host="redis", port=6379, database=2)
    max_jobs = 50
    job_timeout = 600
```

```python
# In FastAPI app — enqueue task
from arq import create_pool

@app.on_event("startup")
async def startup():
    app.state.arq = await create_pool(RedisSettings(host="redis"))

@app.post("/generate-pdf/{quotation_id}")
async def trigger_pdf(quotation_id: int):
    await app.state.arq.enqueue_job("generate_pdf", quotation_id)
    return {"status": "queued"}
```

```bash
# Run ARQ worker
arq app.worker.WorkerSettings
```

**Option 3: Celery (if you need Django-level features)**
```python
# Same as Django Celery — just use without Django integration
from celery import Celery
celery_app = Celery("myapp", broker="redis://redis:6379/1")

@celery_app.task
def heavy_task(data):
    ...
```

**ECS task definitions for ARQ:**
```json
// task-definition-arq-worker.json
{
  "family": "myapp-arq-worker",
  "containerDefinitions": [{
    "name": "arq",
    "image": "ECR_URL/myapp-fastapi:latest",
    "command": ["arq", "app.worker.WorkerSettings"],
    "environment": [...]
  }]
}
```

---

### Q6: WebSocket / SSE / Streaming endpoints production mein kaise deploy karte hain?

**Answer:**
FastAPI ka **biggest deployment gotcha** — WebSocket aur SSE ko special handling chahiye.

**WebSocket endpoint:**
```python
@app.websocket("/ws/chat/{user_id}")
async def chat(websocket: WebSocket, user_id: int):
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_text()
            await websocket.send_text(f"Echo: {data}")
    except WebSocketDisconnect:
        ...
```

**SSE (Server-Sent Events) — LLM streaming ke liye perfect:**
```python
from fastapi.responses import StreamingResponse

@app.get("/stream-llm")
async def stream_llm(prompt: str):
    async def generator():
        async for chunk in llm_client.stream(prompt):
            yield f"data: {chunk}\n\n"
        yield "data: [DONE]\n\n"
    
    return StreamingResponse(generator(), media_type="text/event-stream")
```

**Production gotchas:**

| Issue | Fix |
|---|---|
| **ALB timeout (default 60s) kills WebSocket** | Set `idle_timeout = 4000` on ALB target group |
| **ALB doesn't support sticky WS** | Use NLB OR enable stickiness on ALB target group |
| **Gunicorn workers ko WS state share nahi** | Use Redis pub/sub for multi-worker WS broadcast |
| **Scaling: Connection state pod-bound** | Sticky sessions OR external state (Redis) |
| **CloudFront strips SSE headers** | Disable CloudFront for `/api/stream/*` routes |

**ALB config for WebSocket:**
```hcl
resource "aws_lb_target_group" "fastapi_ws" {
  name        = "fastapi-ws-tg"
  port        = 8000
  protocol    = "HTTP"  # HTTP1.1 upgrades to WS
  target_type = "ip"
  vpc_id      = aws_vpc.main.id

  stickiness {
    type            = "lb_cookie"
    cookie_duration = 86400      # 24 hours
    enabled         = true
  }

  health_check {
    path                = "/health"
    interval            = 30
    timeout             = 5
    healthy_threshold   = 2
    unhealthy_threshold = 3
  }
}

# ALB attribute
resource "aws_lb" "main" {
  ...
  idle_timeout = 4000  # 60s → 4000s for long-running WS/SSE
}
```

**Multi-worker WebSocket broadcast (Redis pub/sub):**
```python
import redis.asyncio as redis

redis_client = redis.from_url("redis://redis:6379/3")

async def broadcast_message(channel: str, message: dict):
    await redis_client.publish(channel, json.dumps(message))

@app.websocket("/ws/{channel}")
async def ws_endpoint(websocket: WebSocket, channel: str):
    await websocket.accept()
    pubsub = redis_client.pubsub()
    await pubsub.subscribe(channel)
    
    try:
        async for msg in pubsub.listen():
            if msg["type"] == "message":
                await websocket.send_text(msg["data"])
    finally:
        await pubsub.unsubscribe(channel)
```

---

### Q7: ECS Fargate par FastAPI deploy karne ke complete steps kya hain?

**Answer:**

Steps similar to Django, but with **3 key differences**:

```bash
# Step 1: Same as Django — ECR, RDS, ElastiCache, Secrets
(skip duplicate steps)

# Step 2: Run Alembic migrations (instead of Django migrate)
aws ecs run-task --cluster myapp-cluster \
  --task-definition myapp-fastapi-migrate \
  --overrides '{"containerOverrides":[{"name":"fastapi","command":["alembic","upgrade","head"]}]}'

# Step 3: Deploy 3 services
# 1. FastAPI web (with UvicornWorker)
# 2. ARQ worker (async tasks)
# 3. ARQ cron (scheduled tasks) — desired_count=1
```

**Task definition (FastAPI web):**
```json
{
  "family": "myapp-fastapi",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "1024",
  "memory": "2048",
  "containerDefinitions": [{
    "name": "fastapi",
    "image": "ECR_URL/myapp-fastapi:latest",
    "portMappings": [{"containerPort": 8000}],
    "environment": [
      {"name": "DATABASE_URL", "value": "postgresql+asyncpg://django:PASS@HOST:5432/myapp"},
      {"name": "REDIS_URL", "value": "redis://CACHE_URL:6379/0"},
      {"name": "ENVIRONMENT", "value": "production"}
    ],
    "secrets": [
      {"name": "JWT_SECRET_KEY", "valueFrom": "arn:aws:secretsmanager:..:secret:myapp/jwt"},
      {"name": "SENTRY_DSN", "valueFrom": "arn:aws:secretsmanager:..:secret:myapp/sentry"}
    ],
    "healthCheck": {
      "command": ["CMD-SHELL", "curl -f http://localhost:8000/health || exit 1"],
      "interval": 30, "timeout": 5, "retries": 3, "startPeriod": 15
    },
    "logConfiguration": {
      "logDriver": "awslogs",
      "options": {
        "awslogs-group": "/ecs/myapp-fastapi",
        "awslogs-region": "ap-south-1",
        "awslogs-stream-prefix": "fastapi"
      }
    }
  }]
}
```

---

### Q8: AWS Lambda par FastAPI deploy kar sakte hain? Kab use karein?

**Answer:**
**Haan, possible hai via Mangum adapter.** But sirf specific cases mein.

```python
# app/main.py
from fastapi import FastAPI
from mangum import Mangum

app = FastAPI()

@app.get("/")
def root():
    return {"hello": "world"}

# ⭐ Lambda handler
handler = Mangum(app, lifespan="off")
```

**When to use Lambda for FastAPI:**

| Use Lambda ✅ | Don't Use Lambda ❌ |
|---|---|
| Sporadic traffic (cost savings) | Constant traffic (ECS sasta) |
| Webhook receivers | WebSocket / SSE (15-min limit) |
| Image processing on S3 upload | Long-running tasks |
| Cron jobs / scheduled | Real-time chat |
| API Gateway → Lambda → FastAPI | High-throughput APIs |
| Internal admin tools | LLM streaming responses |

**Lambda limitations:**
- **15-minute timeout max** — long requests die
- **Cold start** — first request ~1-3s (Python heavy)
- **No persistent connections** — DB connection pool reset every cold start (use RDS Proxy)
- **Async limited** — Lambda freezes between invocations
- **Package size 250MB unzipped** — heavy deps (Pillow, asyncpg) eat budget

**Deployment via SAM:**
```yaml
# template.yaml
AWSTemplateFormatVersion: '2010-09-09'
Transform: AWS::Serverless-2016-10-31

Resources:
  FastAPIFunction:
    Type: AWS::Serverless::Function
    Properties:
      CodeUri: ./
      Handler: app.main.handler
      Runtime: python3.12
      MemorySize: 1024
      Timeout: 30
      Architectures: [arm64]   # Graviton — 20% cheaper
      Environment:
        Variables:
          DATABASE_URL: !Sub '{{resolve:secretsmanager:myapp/db-url}}'
      Events:
        Api:
          Type: HttpApi
          Properties:
            ApiId: !Ref HttpApi
            Path: /{proxy+}
            Method: ANY
      Layers:
        - !Ref DepsLayer    # Heavy deps in layer (reuse across functions)

  HttpApi:
    Type: AWS::Serverless::HttpApi
    Properties:
      CorsConfiguration:
        AllowOrigins: ['https://app.yourapp.com']
```

```bash
# Deploy
sam build
sam deploy --guided
```

**Cold start mitigation:**
```yaml
# Provisioned concurrency (always-warm instances)
Properties:
  ProvisionedConcurrencyConfig:
    ProvisionedConcurrentExecutions: 5

# OR Lambda SnapStart (Java only as of 2024)
```

---

### Q9: FastAPI ke async-specific monitoring + observability kaise setup karte hain?

**Answer:**

**OpenTelemetry instrumentation (one-line setup):**
```python
# app/main.py
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter

# Setup tracing
trace.set_tracer_provider(TracerProvider())
trace.get_tracer_provider().add_span_processor(
    BatchSpanProcessor(OTLPSpanExporter(endpoint="otel-collector:4317"))
)

app = FastAPI()

# Auto-instrument FastAPI, SQLAlchemy, httpx
FastAPIInstrumentor.instrument_app(app)
SQLAlchemyInstrumentor().instrument(engine=engine.sync_engine)
HTTPXClientInstrumentor().instrument()
```

**Prometheus metrics:**
```python
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from starlette.responses import Response
import time

REQUEST_COUNT = Counter("http_requests_total", "Total HTTP requests", ["method", "endpoint", "status"])
REQUEST_DURATION = Histogram("http_request_duration_seconds", "Request duration", ["method", "endpoint"])

# AI-specific metrics
LLM_TOKENS = Counter("llm_tokens_used_total", "LLM tokens used", ["model", "operation"])
LLM_LATENCY = Histogram("llm_request_duration_seconds", "LLM call duration", ["model"])

@app.middleware("http")
async def metrics_middleware(request, call_next):
    start = time.time()
    response = await call_next(request)
    duration = time.time() - start
    
    REQUEST_COUNT.labels(request.method, request.url.path, response.status_code).inc()
    REQUEST_DURATION.labels(request.method, request.url.path).observe(duration)
    return response

@app.get("/metrics")
def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
```

**Structured logging (request_id correlation):**
```python
import structlog
from starlette.middleware.base import BaseHTTPMiddleware
import uuid

log = structlog.get_logger()

class RequestIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        structlog.contextvars.bind_contextvars(request_id=request_id)
        
        start = time.time()
        try:
            response = await call_next(request)
            log.info("request_completed",
                     method=request.method, path=request.url.path,
                     status=response.status_code,
                     duration_ms=round((time.time() - start) * 1000, 2))
            response.headers["X-Request-ID"] = request_id
            return response
        except Exception as e:
            log.error("request_failed", error=str(e), exc_info=True)
            raise
        finally:
            structlog.contextvars.clear_contextvars()

app.add_middleware(RequestIDMiddleware)
```

**Sentry integration:**
```python
import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration

sentry_sdk.init(
    dsn=settings.sentry_dsn,
    integrations=[FastApiIntegration(transaction_style="endpoint"),
                  SqlalchemyIntegration()],
    traces_sample_rate=0.1,
    profiles_sample_rate=0.1,    # Performance profiling
    environment=settings.environment,
)
```

---

### Q10: FastAPI deployment ke 7 production gotchas kya hain?

**Answer:**

| # | Gotcha | Symptom | Fix |
|---|---|---|---|
| 1 | **Sync code in async endpoint** | All requests slow (event loop blocked) | Use `run_in_threadpool()` or async libs (asyncpg not psycopg) |
| 2 | **DB connection leak** | Connection pool exhausted | Always use `Depends(get_db)` with try/finally |
| 3 | **Pydantic v2 migration breaks** | Validation errors after upgrade | `model_config` instead of `Config` class |
| 4 | **CORS misconfigured** | Frontend can't call API | Exact origin match, `allow_credentials=True` if cookies |
| 5 | **Lifespan not used** | DB pool not closed gracefully | Use `@asynccontextmanager` lifespan, not `@on_event` |
| 6 | **JWT validation slow** | High CPU | Cache decoded JWT (Redis) for short TTL |
| 7 | **WebSocket scaling broken** | Messages don't reach all clients | Redis pub/sub for multi-worker broadcast |

**Bonus gotcha — Alembic in async setup:**
```python
# alembic/env.py — async migration runner
import asyncio
from sqlalchemy.ext.asyncio import async_engine_from_config

def do_run_migrations(connection):
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()

async def run_async_migrations():
    connectable = async_engine_from_config(config.get_section(config.config_ini_section), prefix="sqlalchemy.")
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()

def run_migrations_online():
    asyncio.run(run_async_migrations())
```

---

## Production Checklist (FastAPI Specific)

```markdown
### Async-specific
- [ ] All DB calls use async (asyncpg, not psycopg2)
- [ ] All HTTP calls use httpx (not requests)
- [ ] CPU-bound work in `run_in_threadpool()` or Celery
- [ ] Lifespan context manager (not deprecated on_event)
- [ ] uvloop enabled (`uvicorn[standard]`)

### Server config
- [ ] Gunicorn + UvicornWorker (not uvicorn alone)
- [ ] Workers = vCPU count (async) or (2×CPU+1) (mixed)
- [ ] --max-requests 1000 (memory leak prevention)
- [ ] --timeout 120 (LLM endpoints)
- [ ] --graceful-timeout 30

### Database
- [ ] asyncpg driver in DATABASE_URL
- [ ] Pool size tuned (10-20 base, 30 max)
- [ ] pool_pre_ping=True
- [ ] pool_recycle=3600
- [ ] RDS Proxy if using Lambda

### Background tasks
- [ ] ARQ for async tasks (or Celery if complex)
- [ ] Beat/Cron single instance only
- [ ] Task timeout configured

### Streaming (if applicable)
- [ ] ALB idle_timeout = 4000 for WebSocket/SSE
- [ ] Sticky sessions enabled
- [ ] Redis pub/sub for multi-worker broadcast
- [ ] CloudFront bypass for streaming routes

### Common (same as Django)
- [ ] DEBUG = False
- [ ] HTTPS enforced
- [ ] CORS restrictive
- [ ] Secrets in AWS Secrets Manager
- [ ] Health check + readiness endpoints
- [ ] Auto-scaling configured
- [ ] Sentry + CloudWatch alarms
```

---

## FastAPI vs Django Deployment — Quick Diff Table

| Aspect | Django | FastAPI |
|---|---|---|
| Server | Gunicorn (sync) | Gunicorn + UvicornWorker (async) |
| ORM | Django ORM | SQLAlchemy 2.0 async |
| Migrations | `manage.py migrate` | `alembic upgrade head` |
| Background tasks | Celery | ARQ / Celery / BackgroundTasks |
| Admin panel | Built-in | Build separately (or fastapi-admin) |
| WebSocket | Django Channels (complex) | Native (simple) |
| Best for | CRUD ERP, admin-heavy | AI APIs, streaming, microservices |
| Production server image size | ~400MB (with PostGIS + WeasyPrint) | ~250MB |
| Cold start (Lambda) | 2-4s | 1-2s |
| Memory per worker | ~150MB | ~80MB |
