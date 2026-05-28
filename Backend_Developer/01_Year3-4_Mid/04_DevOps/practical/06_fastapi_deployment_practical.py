"""
Phase3_DevOps — FastAPI Production Deployment Practical
=========================================================
Topics covered:
  1. Production Dockerfile (Gunicorn + UvicornWorker)
  2. docker-compose.yml (FastAPI + ARQ + PostgreSQL + Redis)
  3. Async SQLAlchemy 2.0 + asyncpg setup with connection pooling
  4. Background tasks: BackgroundTasks vs ARQ vs Celery
  5. WebSocket / SSE production patterns (ALB sticky, Redis pub/sub)
  6. AWS Lambda + Mangum (when to use, when not)
  7. OpenTelemetry instrumentation
  8. Health check + lifespan patterns
  9. FastAPI production gotchas

Run:
  pip install fastapi uvicorn sqlalchemy asyncpg arq httpx boto3
  python 06_fastapi_deployment_practical.py
"""

import json
import os
import textwrap

# ─────────────────────────────────────────────────────────────────────────────
# SECTION 1: Production Dockerfile for FastAPI
# INTERVIEW: Gunicorn (process manager) + UvicornWorker (ASGI worker)
# ─────────────────────────────────────────────────────────────────────────────

FASTAPI_DOCKERFILE = """\
# ─── Production Dockerfile for FastAPI ───
# INTERVIEW: Why Gunicorn + UvicornWorker (not Uvicorn alone)?
# - Gunicorn = process manager (auto-restart, worker lifecycle)
# - UvicornWorker = ASGI async support (FastAPI requirement)
# - Combined = battle-tested production setup

# ══ Stage 1: Builder ══════════════════════════════════════════════
FROM python:3.12-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1

WORKDIR /app

# INTERVIEW: System deps
# - libpq-dev for asyncpg compilation
# - build-essential for httptools (C-based HTTP parser)
RUN apt-get update && apt-get install -y --no-install-recommends \\
    build-essential \\
    libpq-dev \\
    curl \\
    && rm -rf /var/lib/apt/lists/*

# INTERVIEW: uv = faster alternative to pip (10-100x speed)
# Optional but recommended for CI/CD speed
COPY requirements.txt .
RUN pip install --prefix=/install -r requirements.txt

# ══ Stage 2: Runtime ══════════════════════════════════════════════
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PORT=8000

# Runtime deps only
RUN apt-get update && apt-get install -y --no-install-recommends \\
    libpq5 curl \\
    && rm -rf /var/lib/apt/lists/*

RUN addgroup --system app && adduser --system --ingroup app app

WORKDIR /app
COPY --from=builder /install /usr/local
COPY --chown=app:app . .

USER app
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s \\
    CMD curl -f http://localhost:8000/health || exit 1

# ⭐ INTERVIEW: Gunicorn + UvicornWorker (production)
# Workers count strategy:
#   - Async-heavy (LLM, I/O):  workers = CPU count (1 worker handles 1000s connections)
#   - Mixed (DB + logic):      workers = (2 × CPU) + 1
#   - CPU-bound:               workers = CPU count
CMD ["gunicorn", "app.main:app", \\
     "--workers", "4", \\
     "--worker-class", "uvicorn.workers.UvicornWorker", \\
     "--bind", "0.0.0.0:8000", \\
     "--timeout", "120", \\
     "--graceful-timeout", "30", \\
     "--keep-alive", "5", \\
     "--max-requests", "1000", \\
     "--max-requests-jitter", "50", \\
     "--access-logfile", "-", \\
     "--error-logfile", "-", \\
     "--log-level", "info"]

# Alternative: Pure Uvicorn (simpler, less production-tested at scale)
# CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", \\
#      "--workers", "4", "--loop", "uvloop", "--http", "httptools"]
"""

FASTAPI_REQUIREMENTS = """\
# requirements.txt — Production FastAPI essentials

# Core
fastapi==0.115.0
uvicorn[standard]==0.32.0       # ⭐ [standard] includes uvloop + httptools (perf)
gunicorn==23.0.0

# Database
sqlalchemy[asyncio]==2.0.36     # Async ORM
asyncpg==0.30.0                 # Async PostgreSQL driver (NOT psycopg)
alembic==1.14.0                 # Migrations

# Validation + Settings
pydantic==2.10.0                # Rust-powered, fast
pydantic-settings==2.6.0        # Env var loading

# Cache + Background
redis[hiredis]==5.2.0           # hiredis = C parser (10x faster)
arq==0.26.0                     # Async task queue (Celery alternative)

# HTTP
httpx==0.27.0                   # Async HTTP client (replaces requests)

# Auth
python-jose[cryptography]==3.3.0
passlib[bcrypt]==1.7.4

# Observability
structlog==24.4.0
sentry-sdk[fastapi]==2.18.0
opentelemetry-instrumentation-fastapi==0.49b0
prometheus-client==0.21.0
"""

# ─────────────────────────────────────────────────────────────────────────────
# SECTION 2: Async SQLAlchemy + asyncpg Setup
# INTERVIEW: Critical — sync vs async drivers
# ─────────────────────────────────────────────────────────────────────────────

ASYNC_DATABASE_CODE = """\
# app/database.py
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from contextlib import asynccontextmanager
from app.config import settings

class Base(DeclarativeBase):
    pass

# ⭐ INTERVIEW: Async engine setup
# - URL format: postgresql+asyncpg://...  (NOT postgresql://)
# - Pool sizes: tuned for production load
engine = create_async_engine(
    settings.database_url,         # postgresql+asyncpg://user:pass@host/db
    pool_size=10,                  # Base connections always open
    max_overflow=20,               # Burst: max 30 total connections
    pool_pre_ping=True,            # Detect dead connections (RDS failover)
    pool_recycle=3600,             # Recycle every hour (avoid stale)
    echo=False,                    # SQL logs off in prod (perf + security)
)

# INTERVIEW: expire_on_commit=False = objects accessible after commit
# (default True breaks lazy loading after commit)
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)

# Dependency for FastAPI routes
async def get_db():
    \"\"\"
    INTERVIEW: try/finally ensures connection returned to pool.
    Without this → connection leak → pool exhausted → 500 errors.
    \"\"\"
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


# ── Lifespan Context (NEW pattern, replaces @on_event) ───────────
@asynccontextmanager
async def lifespan(app):
    \"\"\"
    Startup: connect to external services.
    Shutdown: close gracefully.
    INTERVIEW: @on_event is DEPRECATED in FastAPI 0.93+
    \"\"\"
    # Startup
    # ... initialize Redis, warm cache, etc.
    yield
    # Shutdown
    await engine.dispose()        # Close all DB connections


# app/main.py
from fastapi import FastAPI, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db, lifespan
from app.models import User

app = FastAPI(lifespan=lifespan)

@app.get("/users/{user_id}")
async def get_user(user_id: int, db: AsyncSession = Depends(get_db)):
    # INTERVIEW: SQLAlchemy 2.0 style — execute(select(...))
    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()
"""

# ─────────────────────────────────────────────────────────────────────────────
# SECTION 3: Background Tasks — 3 Options Compared
# INTERVIEW: BackgroundTasks vs ARQ vs Celery
# ─────────────────────────────────────────────────────────────────────────────

BACKGROUND_TASKS_COMPARISON = """\
# ════════════════════════════════════════════════════════════════════
# OPTION 1: FastAPI BackgroundTasks (built-in)
# WHEN: Quick tasks (<30s), OK to lose on crash, same process
# ════════════════════════════════════════════════════════════════════
from fastapi import BackgroundTasks

@app.post("/send-email")
async def send_email(email: EmailRequest, bg: BackgroundTasks):
    # Runs AFTER response sent — but in same process
    bg.add_task(send_email_smtp, email.to, email.body)
    return {"status": "queued"}

# ⚠️ Lost if container crashes
# ⚠️ No retries, no scheduling
# ✅ Zero infra (no Redis/RabbitMQ)


# ════════════════════════════════════════════════════════════════════
# OPTION 2: ARQ (recommended for FastAPI — async-native)
# WHEN: <5 min tasks, need retries/scheduling, lightweight
# ════════════════════════════════════════════════════════════════════
# app/worker.py
from arq import cron
from arq.connections import RedisSettings

async def send_email(ctx, to: str, body: str):
    # ctx = context dict (job ID, retry count, etc.)
    ...

async def generate_pdf(ctx, quotation_id: int):
    ...

async def daily_sync(ctx):
    # Scheduled task
    ...

class WorkerSettings:
    functions = [send_email, generate_pdf]
    cron_jobs = [
        cron(daily_sync, hour=2, minute=0),  # 2 AM daily
    ]
    redis_settings = RedisSettings(host="redis", port=6379, database=2)
    max_jobs = 50              # Concurrent jobs per worker
    job_timeout = 600          # 10 min per job

# In FastAPI app — enqueue task
from arq import create_pool

@app.on_event("startup")
async def startup():
    app.state.arq = await create_pool(RedisSettings(host="redis"))

@app.post("/generate-pdf/{quotation_id}")
async def trigger_pdf(quotation_id: int):
    await app.state.arq.enqueue_job("generate_pdf", quotation_id)
    return {"status": "queued"}

# Run worker:
# arq app.worker.WorkerSettings


# ════════════════════════════════════════════════════════════════════
# OPTION 3: Celery (if you need Django-level features)
# WHEN: Complex workflows (chains, chords), multi-broker, mature ecosystem
# ════════════════════════════════════════════════════════════════════
from celery import Celery
celery_app = Celery("myapp", broker="redis://redis:6379/1")

@celery_app.task(bind=True, max_retries=3)
def complex_workflow(self, data):
    try:
        # process
        pass
    except Exception as exc:
        # Auto-retry with exponential backoff
        raise self.retry(exc=exc, countdown=2 ** self.request.retries)

# Chain example: task1 result → task2 input
from celery import chain
chain(task1.s(arg), task2.s(), task3.s()).apply_async()
"""

# ─────────────────────────────────────────────────────────────────────────────
# SECTION 4: WebSocket / SSE Production Patterns
# INTERVIEW: ALB config, sticky sessions, Redis pub/sub for scaling
# ─────────────────────────────────────────────────────────────────────────────

WEBSOCKET_PRODUCTION = """\
# ════════════════════════════════════════════════════════════════════
# SSE (Server-Sent Events) — perfect for LLM streaming
# INTERVIEW: One-way streaming, simpler than WebSocket, just HTTP
# ════════════════════════════════════════════════════════════════════
from fastapi import FastAPI
from fastapi.responses import StreamingResponse

@app.get("/stream-llm")
async def stream_llm(prompt: str):
    async def generator():
        async for chunk in llm_client.stream(prompt):
            # SSE format: data: <content>\\n\\n
            yield f"data: {chunk}\\n\\n"
        yield "data: [DONE]\\n\\n"

    return StreamingResponse(
        generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",   # ⭐ Disable Nginx buffering
        }
    )


# ════════════════════════════════════════════════════════════════════
# WebSocket — bidirectional, real-time chat
# ════════════════════════════════════════════════════════════════════
from fastapi import WebSocket, WebSocketDisconnect

@app.websocket("/ws/chat/{user_id}")
async def chat_ws(websocket: WebSocket, user_id: int):
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_text()
            await websocket.send_text(f"Echo: {data}")
    except WebSocketDisconnect:
        # Clean up: remove from active connections
        ...


# ════════════════════════════════════════════════════════════════════
# Multi-Worker Broadcast — Redis Pub/Sub
# INTERVIEW: Gunicorn workers don't share state → use Redis as bus
# Without this: messages only reach clients on same worker process
# ════════════════════════════════════════════════════════════════════
import redis.asyncio as redis
import json

redis_client = redis.from_url("redis://redis:6379/3")

async def broadcast_message(channel: str, message: dict):
    \"\"\"Publish from anywhere (REST endpoint, background task)\"\"\"
    await redis_client.publish(channel, json.dumps(message))

@app.websocket("/ws/{channel}")
async def ws_endpoint(websocket: WebSocket, channel: str):
    await websocket.accept()

    # Subscribe to Redis channel
    pubsub = redis_client.pubsub()
    await pubsub.subscribe(channel)

    try:
        async for msg in pubsub.listen():
            if msg["type"] == "message":
                # Forward Redis message to WebSocket client
                await websocket.send_text(msg["data"])
    except WebSocketDisconnect:
        pass
    finally:
        await pubsub.unsubscribe(channel)
"""

# INTERVIEW: ALB configuration for WebSocket/SSE
ALB_WEBSOCKET_CONFIG = """\
# Terraform — ALB config for WebSocket/SSE
# INTERVIEW: Default ALB idle_timeout is 60s → kills long connections

resource "aws_lb" "main" {
  name               = "fastapi-alb"
  load_balancer_type = "application"
  idle_timeout       = 4000      # ⭐ 60s → 4000s for long WS/SSE
}

resource "aws_lb_target_group" "fastapi_ws" {
  name        = "fastapi-ws-tg"
  port        = 8000
  protocol    = "HTTP"           # HTTP1.1 upgrades to WebSocket
  target_type = "ip"
  vpc_id      = aws_vpc.main.id

  # ⭐ INTERVIEW: Sticky sessions for stateful WebSocket
  # Same client always routes to same target (preserves WS state)
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
"""

# ─────────────────────────────────────────────────────────────────────────────
# SECTION 5: AWS Lambda + Mangum (FastAPI on Serverless)
# INTERVIEW: When to use Lambda, when NOT to
# ─────────────────────────────────────────────────────────────────────────────

LAMBDA_FASTAPI_CODE = """\
# ════════════════════════════════════════════════════════════════════
# FastAPI on AWS Lambda via Mangum adapter
# WHEN ✅: Webhooks, S3 triggers, sporadic APIs, cron jobs
# WHEN ❌: WebSocket, SSE, high-throughput APIs, long-running tasks
# ════════════════════════════════════════════════════════════════════

# app/main.py
from fastapi import FastAPI
from mangum import Mangum

app = FastAPI()

@app.get("/")
def root():
    return {"hello": "world"}

@app.post("/webhook/stripe")
async def stripe_webhook(payload: dict):
    # Lambda handles webhook spikes well
    return {"received": True}

# ⭐ INTERVIEW: Lambda handler
handler = Mangum(app, lifespan="off")   # lifespan="off" for Lambda
"""

LAMBDA_SAM_TEMPLATE = """\
# template.yaml — AWS SAM (Serverless Application Model)
# Deploy: sam build && sam deploy --guided

AWSTemplateFormatVersion: '2010-09-09'
Transform: AWS::Serverless-2016-10-31

Resources:
  FastAPIFunction:
    Type: AWS::Serverless::Function
    Properties:
      CodeUri: ./
      Handler: app.main.handler
      Runtime: python3.12
      MemorySize: 1024            # INTERVIEW: more memory = more CPU
      Timeout: 30                 # Max 900s (15 min hard limit)
      Architectures: [arm64]      # ⭐ Graviton = 20% cheaper, faster

      Environment:
        Variables:
          DATABASE_URL: !Sub '{{resolve:secretsmanager:myapp/db-url}}'

      # API Gateway integration
      Events:
        Api:
          Type: HttpApi
          Properties:
            ApiId: !Ref HttpApi
            Path: /{proxy+}
            Method: ANY

      Layers:
        - !Ref DepsLayer          # Heavy deps in layer (shared)

      # ⭐ INTERVIEW: Mitigate cold starts
      ProvisionedConcurrencyConfig:
        ProvisionedConcurrentExecutions: 5    # Always-warm instances

  DepsLayer:
    Type: AWS::Serverless::LayerVersion
    Properties:
      ContentUri: layers/deps/
      CompatibleRuntimes: [python3.12]

  HttpApi:
    Type: AWS::Serverless::HttpApi
    Properties:
      CorsConfiguration:
        AllowOrigins: ['https://app.yourapp.com']
"""

# ─────────────────────────────────────────────────────────────────────────────
# SECTION 6: OpenTelemetry Instrumentation
# INTERVIEW: Distributed tracing for microservices
# ─────────────────────────────────────────────────────────────────────────────

OPENTELEMETRY_SETUP = """\
# app/observability.py
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.instrumentation.redis import RedisInstrumentor

def setup_observability(app, engine):
    \"\"\"
    INTERVIEW: One-line auto-instrumentation for FastAPI app.
    Traces: HTTP requests, DB queries, external HTTP calls.
    Export to: AWS X-Ray, Jaeger, Tempo, Honeycomb, Datadog.
    \"\"\"
    # Setup tracer with OTLP exporter
    trace.set_tracer_provider(TracerProvider())
    trace.get_tracer_provider().add_span_processor(
        BatchSpanProcessor(
            OTLPSpanExporter(endpoint="otel-collector:4317", insecure=True)
        )
    )

    # Auto-instrument
    FastAPIInstrumentor.instrument_app(app)
    SQLAlchemyInstrumentor().instrument(engine=engine.sync_engine)
    HTTPXClientInstrumentor().instrument()
    RedisInstrumentor().instrument()


# Prometheus metrics endpoint
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from starlette.responses import Response
import time

REQUEST_COUNT = Counter("http_requests_total", "Total HTTP requests",
                         ["method", "endpoint", "status"])
REQUEST_DURATION = Histogram("http_request_duration_seconds", "Request duration",
                              ["method", "endpoint"])

# AI-specific metrics
LLM_TOKENS = Counter("llm_tokens_used_total", "LLM tokens used",
                     ["model", "operation"])
LLM_LATENCY = Histogram("llm_request_duration_seconds", "LLM call duration",
                         ["model"])

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
"""

# ─────────────────────────────────────────────────────────────────────────────
# SECTION 7: Demo Function — Boto3 + Mangum Test
# ─────────────────────────────────────────────────────────────────────────────

def demo_fastapi_async_patterns():
    """
    INTERVIEW: Async patterns that distinguish FastAPI from Django.
    """
    print("\n[FastAPI Async Patterns Demo]")
    try:
        import asyncio

        async def async_db_query():
            await asyncio.sleep(0.1)
            return {"id": 1, "name": "User"}

        async def parallel_io_demo():
            # INTERVIEW: 3 async calls run in parallel (not sequential)
            results = await asyncio.gather(
                async_db_query(),
                async_db_query(),
                async_db_query(),
            )
            return results

        results = asyncio.run(parallel_io_demo())
        print(f"  Parallel async calls: {len(results)} results in ~0.1s (not 0.3s)")
        print("  ⭐ FastAPI advantage: async I/O without thread pool")

    except Exception as e:
        print(f"  Demo error: {e}")


def demo_check_uvicorn_workers():
    """INTERVIEW: How to determine optimal worker count."""
    print("\n[Worker Count Calculator]")
    try:
        import multiprocessing
        cpu_count = multiprocessing.cpu_count()
        print(f"  Detected CPU cores: {cpu_count}")
        print(f"  Async-heavy app:   --workers {cpu_count}")
        print(f"  Mixed workload:    --workers {(2 * cpu_count) + 1}")
        print(f"  CPU-bound:         --workers {cpu_count}")
        print("\n  Fargate guidance:")
        print("    1 vCPU task → 2-4 workers")
        print("    2 vCPU task → 4-8 workers")
        print("    4 vCPU task → 8-16 workers")
    except Exception as e:
        print(f"  Error: {e}")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 8: FastAPI Production Gotchas
# ─────────────────────────────────────────────────────────────────────────────

PRODUCTION_GOTCHAS = [
    ("Sync code in async endpoint",
     "All requests slow (event loop blocked)",
     "Use run_in_threadpool() OR async libs (asyncpg not psycopg2)"),

    ("DB connection leak",
     "Connection pool exhausted, 500 errors",
     "Always use Depends(get_db) with try/finally"),

    ("Pydantic v2 migration",
     "Validation errors after upgrade",
     "model_config instead of class Config, .model_dump() not .dict()"),

    ("CORS misconfigured",
     "Frontend can't call API",
     "Exact origin match, allow_credentials=True if cookies"),

    ("Lifespan not used",
     "DB pool not closed gracefully on shutdown",
     "@asynccontextmanager lifespan (NOT deprecated @on_event)"),

    ("JWT validation slow",
     "High CPU usage",
     "Cache decoded JWT in Redis with short TTL"),

    ("WebSocket scaling broken",
     "Messages don't reach all clients",
     "Redis pub/sub for multi-worker broadcast"),

    ("ALB kills WebSocket at 60s",
     "Connections drop randomly",
     "Set ALB idle_timeout = 4000"),

    ("Lambda cold start",
     "First request 1-3 seconds",
     "Provisioned concurrency OR avoid Lambda for FastAPI"),

    ("requests library used",
     "Blocks event loop, all requests slow",
     "Use httpx for async HTTP calls"),
]

# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

FASTAPI_DEPLOY_QA = [
    ("Gunicorn + UvicornWorker vs Uvicorn alone?",
     "Gunicorn = process manager (auto-restart, scaling, lifecycle)\n"
     "     UvicornWorker = ASGI worker (async support)\n"
     "     Combined = best for production. Uvicorn alone OK for simple cases."),

    ("Why asyncpg not psycopg?",
     "asyncpg = native async PostgreSQL driver (3-5x faster than psycopg)\n"
     "     psycopg2 = sync only (blocks event loop in FastAPI)\n"
     "     psycopg3 = supports async but asyncpg still faster"),

    ("ARQ vs Celery for FastAPI?",
     "ARQ:    async-native, Redis-only, lightweight, simpler\n"
     "     Celery: sync workers, multiple brokers, mature, complex\n"
     "     Use ARQ for new FastAPI apps, Celery if you need chains/chords"),

    ("Why not Lambda for FastAPI?",
     "Lambda limitations:\n"
     "     - 15-min timeout (no long-running)\n"
     "     - Cold starts hurt streaming UX\n"
     "     - No WebSocket (use API Gateway WS separately)\n"
     "     - DB connection per cold start (use RDS Proxy)\n"
     "     Use ECS Fargate for full FastAPI apps."),

    ("How to scale WebSocket across workers?",
     "1. Sticky sessions on ALB (same client → same worker)\n"
     "     2. Redis pub/sub for broadcast (messages reach all workers)\n"
     "     3. ALB idle_timeout = 4000 (prevent 60s timeout kills)"),

    ("Why max_requests in Gunicorn?",
     "Workers leak memory over time (Pillow, transformers, etc.)\n"
     "     --max-requests 1000 → worker recycled after 1000 requests\n"
     "     --max-requests-jitter 50 → random recycle (no thundering herd)"),
]


def main():
    print("=" * 60)
    print("FASTAPI PRODUCTION DEPLOYMENT PRACTICAL")
    print("=" * 60)

    print("\n[1] Production Server Stack:")
    stack = {
        "Process manager":      "Gunicorn (auto-restart, lifecycle)",
        "ASGI worker":          "UvicornWorker (async support)",
        "Event loop":           "uvloop (libuv-based, 2-4x faster)",
        "HTTP parser":          "httptools (C-based)",
        "DB driver":            "asyncpg (NOT psycopg2)",
        "Background tasks":     "ARQ (lightweight) or Celery (complex)",
    }
    for k, v in stack.items():
        print(f"  {k:<22}: {v}")

    print("\n[2] Background Tasks Decision Matrix:")
    print(f"  {'Option':<20} {'When':<35} {'Pros'}")
    print(f"  {'-'*20} {'-'*35} {'-'*30}")
    options = [
        ("BackgroundTasks", "Quick tasks <30s, same process", "Built-in, zero infra"),
        ("ARQ", "<5min, async-native, lightweight", "Redis-only, simple"),
        ("Celery", "Complex workflows (chains/chords)", "Mature, multi-broker"),
    ]
    for opt, when, pros in options:
        print(f"  {opt:<20} {when:<35} {pros}")

    print("\n[3] WebSocket/SSE Production Requirements:")
    ws_reqs = {
        "ALB idle_timeout":       "4000 (default 60s kills connections)",
        "Sticky sessions":        "lb_cookie (state preserved across requests)",
        "Multi-worker broadcast": "Redis pub/sub (shared state)",
        "Nginx buffering":        "X-Accel-Buffering: no (for SSE)",
        "CloudFront":             "Bypass for streaming routes",
    }
    for k, v in ws_reqs.items():
        print(f"  {k:<25}: {v}")

    print("\n[4] AWS Lambda Decision:")
    lambda_decision = {
        "✅ Good for": "Webhooks, S3 triggers, sporadic APIs, cron",
        "❌ Bad for":  "WebSocket, SSE, high-throughput, long-running",
        "Adapter":     "Mangum (handler = Mangum(app, lifespan='off'))",
        "Cold start":  "Mitigate with ProvisionedConcurrency",
        "Cost benefit": "Pay-per-use, free up to 1M requests/month",
    }
    for k, v in lambda_decision.items():
        print(f"  {k:<15}: {v}")

    demo_fastapi_async_patterns()
    demo_check_uvicorn_workers()

    print("\n[5] FastAPI Production Gotchas:")
    print(f"  {'Issue':<32} {'Symptom':<35} {'Fix'}")
    print(f"  {'-'*32} {'-'*35} {'-'*30}")
    for issue, symptom, fix in PRODUCTION_GOTCHAS:
        print(f"  {issue:<32} {symptom:<35} {fix}")

    print("\n[6] FastAPI Deployment Interview Q&A:")
    for q, a in FASTAPI_DEPLOY_QA:
        print(f"\n  Q: {q}")
        print(f"  A: {a}")

    print("\n" + "=" * 60)
    print("FILES TO KNOW:")
    print("  Dockerfile                       → Gunicorn + UvicornWorker")
    print("  app/database.py                  → async engine, get_db dependency")
    print("  app/main.py                      → lifespan context manager")
    print("  app/worker.py                    → ARQ WorkerSettings")
    print("  app/observability.py             → OpenTelemetry + Prometheus")
    print("  template.yaml                    → AWS SAM (if using Lambda)")
    print("=" * 60)


if __name__ == "__main__":
    main()
