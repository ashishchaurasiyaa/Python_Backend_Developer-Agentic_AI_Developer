# Lecture 2 — Practical Hands-On: 12-Factor App

> **Theory file:** [02_12_Factor_App.md](02_12_Factor_App.md)

---

## 🎯 Is Practical Mein Kya Banayenge?

Build a fully 12-factor compliant app:

1. ✅ **All 12 factors** demonstrated in code
2. ✅ **Single codebase** with multiple deploys
3. ✅ **Environment-based config** with Pydantic Settings
4. ✅ **Stateless** FastAPI app
5. ✅ **Backing services** via env vars
6. ✅ **Graceful shutdown** with SIGTERM
7. ✅ **Procfile** for concurrency
8. ✅ **Dockerfile** for dev/prod parity
9. ✅ **Migrations** as admin processes
10. ✅ **Logs as streams** for centralized collection

By end: aap **production-ready 12-factor app** bana sakte ho.

---

## 1. Project Structure

```
twelve_factor_demo/
├── README.md
├── Procfile                  # Factor 8: Concurrency
├── Dockerfile                # Factor 10: Dev/prod parity
├── docker-compose.yml
├── requirements.txt          # Factor 2: Dependencies
├── .env.example              # Factor 3: Config template
├── .gitignore                # Never commit .env!
│
├── app/
│   ├── __init__.py
│   ├── main.py               # FastAPI app
│   ├── config.py             # Factor 3: Config from env
│   ├── db.py                 # Factor 4: Backing service
│   ├── cache.py              # Factor 4: Another backing service
│   ├── logging_setup.py      # Factor 11: Logs to stdout
│   └── lifespan.py           # Factor 9: Disposability
│
├── workers/
│   ├── celery_app.py         # Factor 8: Worker process
│   └── tasks.py
│
├── scripts/                  # Factor 12: Admin processes
│   ├── migrate.py
│   ├── seed_data.py
│   └── cleanup_old_data.py
│
└── tests/
    └── test_app.py
```

---

## 2. ⚙️ Factor 3: Config — Environment Variables

### `app/config.py`

```python
"""
12-factor Config: ALL configuration from environment.
Uses Pydantic Settings for type safety.
"""
from pydantic_settings import BaseSettings
from pydantic import Field
from functools import lru_cache

class Settings(BaseSettings):
    """All app configuration from environment variables"""
    
    # App
    app_name: str = "MyApp"
    debug: bool = False
    log_level: str = "INFO"
    
    # Server
    host: str = "0.0.0.0"
    port: int = 8000
    workers: int = 4
    
    # Backing services
    database_url: str = Field(..., description="PostgreSQL connection")
    redis_url: str = Field(..., description="Redis connection")
    
    # External services
    stripe_secret_key: str = Field(..., description="Stripe API key")
    sendgrid_api_key: str = Field(..., description="SendGrid API key")
    
    # Feature flags
    enable_new_signup_flow: bool = False
    
    # Limits
    max_upload_size_mb: int = 10
    request_timeout_seconds: int = 30
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

@lru_cache
def get_settings() -> Settings:
    """Cached settings (read once)"""
    return Settings()
```

### `.env.example` (committed to git)

```bash
# Application
APP_NAME=MyApp
DEBUG=false
LOG_LEVEL=INFO

# Server
PORT=8000
WORKERS=4

# Backing Services
DATABASE_URL=postgresql://user:password@localhost:5432/myapp
REDIS_URL=redis://localhost:6379/0

# External Services (use TEST keys for dev!)
STRIPE_SECRET_KEY=sk_test_...
SENDGRID_API_KEY=SG.test_...

# Feature Flags
ENABLE_NEW_SIGNUP_FLOW=false
```

### `.gitignore`

```bash
# NEVER commit actual .env!
.env
.env.local
.env.production

# Other secrets
*.pem
*.key
secrets/
```

### Usage

```python
# Anywhere in app
from app.config import get_settings

settings = get_settings()
print(f"Using DB: {settings.database_url[:30]}...")  # Mask in logs!
print(f"Debug mode: {settings.debug}")
```

---

## 3. 📊 Factor 11: Logs to Stdout

### `app/logging_setup.py`

```python
"""
12-factor logging: emit to stdout, let environment handle the rest.
"""
import logging
import sys
import json
from datetime import datetime
from app.config import get_settings

class JSONFormatter(logging.Formatter):
    """Structured JSON logs for easy parsing by aggregators"""
    
    def format(self, record):
        log_data = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        # Include exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
        
        # Include extra fields
        for key, value in record.__dict__.items():
            if key not in ["name", "msg", "args", "created", "filename", 
                           "funcName", "levelname", "levelno", "lineno", 
                           "module", "msecs", "message", "pathname", 
                           "process", "processName", "relativeCreated", 
                           "thread", "threadName", "exc_info", "exc_text",
                           "stack_info"]:
                log_data[key] = value
        
        return json.dumps(log_data)

def setup_logging():
    """Configure logging - emit to stdout, JSON formatted"""
    settings = get_settings()
    
    # Root logger
    root = logging.getLogger()
    root.setLevel(settings.log_level)
    
    # Remove default handlers
    for handler in root.handlers[:]:
        root.removeHandler(handler)
    
    # Stream to stdout (NOT files!)
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JSONFormatter())
    root.addHandler(handler)
    
    # Quiet noisy libraries
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)

# Initialize at import
setup_logging()
```

### Usage with Context

```python
import logging

logger = logging.getLogger(__name__)

@app.post("/orders")
async def create_order(req: OrderRequest):
    # Structured logging with context
    logger.info(
        "Creating order",
        extra={
            "user_id": req.user_id,
            "amount": req.amount,
            "items_count": len(req.items),
        }
    )
    # ...
```

### Sample Log Output (JSON)

```json
{
  "timestamp": "2026-05-26T10:00:00.123Z",
  "level": "INFO",
  "logger": "app.main",
  "message": "Creating order",
  "module": "main",
  "function": "create_order",
  "line": 42,
  "user_id": 123,
  "amount": 500.0,
  "items_count": 3
}
```

### Log Aggregation Pipeline

```
App → stdout → Container runtime → Fluentd/Logstash → Elasticsearch
                                                    → S3 archive
                                                    → Datadog
                                                    → Splunk
```

---

## 4. 💾 Factor 4: Backing Services

### `app/db.py`

```python
"""
Database connection - treats DB as attached resource.
URL from environment, no hardcoded info.
"""
import asyncpg
from app.config import get_settings
import logging

logger = logging.getLogger(__name__)

class Database:
    """Async DB connection pool"""
    
    def __init__(self):
        self.pool: asyncpg.Pool = None
    
    async def connect(self):
        """Connect using DATABASE_URL from env"""
        settings = get_settings()
        
        logger.info(f"Connecting to database...")
        self.pool = await asyncpg.create_pool(
            settings.database_url,
            min_size=2,
            max_size=20,
            command_timeout=settings.request_timeout_seconds,
        )
        logger.info("Database connected")
    
    async def disconnect(self):
        """Cleanly close pool"""
        if self.pool:
            await self.pool.close()
            logger.info("Database disconnected")
    
    async def execute(self, query: str, *args):
        async with self.pool.acquire() as conn:
            return await conn.execute(query, *args)
    
    async def fetch_one(self, query: str, *args):
        async with self.pool.acquire() as conn:
            return await conn.fetchrow(query, *args)
    
    async def fetch_all(self, query: str, *args):
        async with self.pool.acquire() as conn:
            return await conn.fetch(query, *args)

# Singleton instance
db = Database()
```

### `app/cache.py`

```python
"""
Redis cache - another backing service.
URL from environment.
"""
import redis.asyncio as redis
from app.config import get_settings
import logging

logger = logging.getLogger(__name__)

class Cache:
    """Async Redis cache"""
    
    def __init__(self):
        self.client: redis.Redis = None
    
    async def connect(self):
        settings = get_settings()
        logger.info("Connecting to Redis...")
        self.client = redis.from_url(settings.redis_url)
        await self.client.ping()
        logger.info("Redis connected")
    
    async def disconnect(self):
        if self.client:
            await self.client.close()
            logger.info("Redis disconnected")

cache = Cache()
```

---

## 5. 🚦 Factor 9: Disposability — Graceful Shutdown

### `app/lifespan.py`

```python
"""
12-factor disposability: fast startup, graceful shutdown.
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
import asyncio
import signal
import logging

from app.db import db
from app.cache import cache

logger = logging.getLogger(__name__)

# Track in-flight requests
in_flight_requests = 0
shutdown_event = asyncio.Event()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Manages app startup + shutdown.
    Fast startup, graceful shutdown.
    """
    # ── STARTUP (Factor 9: Fast) ──
    logger.info("App starting...")
    
    try:
        # Connect backing services
        await db.connect()
        await cache.connect()
        
        # Setup signal handlers
        loop = asyncio.get_event_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, _initiate_shutdown)
        
        logger.info("App ready")
        
        yield  # ← App runs here
        
    finally:
        # ── SHUTDOWN (Factor 9: Graceful) ──
        logger.info("Shutting down...")
        
        # 1. Stop accepting new requests (FastAPI handles this)
        
        # 2. Wait for in-flight requests to complete (with timeout)
        await _wait_for_in_flight(timeout=30)
        
        # 3. Close backing services
        await db.disconnect()
        await cache.disconnect()
        
        logger.info("Shutdown complete")

def _initiate_shutdown():
    """Triggered on SIGTERM/SIGINT"""
    logger.info("Shutdown signal received")
    shutdown_event.set()

async def _wait_for_in_flight(timeout: float):
    """Wait for active requests to finish"""
    start = asyncio.get_event_loop().time()
    
    while in_flight_requests > 0:
        elapsed = asyncio.get_event_loop().time() - start
        if elapsed > timeout:
            logger.warning(f"Timeout: {in_flight_requests} requests still in flight")
            break
        
        logger.info(f"Waiting for {in_flight_requests} in-flight requests...")
        await asyncio.sleep(1)
```

### `app/main.py`

```python
"""
Main FastAPI app - 12-factor compliant.
"""
from fastapi import FastAPI, Request
from app.config import get_settings
from app.lifespan import lifespan, in_flight_requests
from app.db import db
from app.cache import cache
import logging

logger = logging.getLogger(__name__)
settings = get_settings()

# Factor 9: Lifespan manages startup + shutdown
app = FastAPI(
    title=settings.app_name,
    lifespan=lifespan,
)

@app.middleware("http")
async def track_in_flight(request: Request, call_next):
    """Track requests for graceful shutdown"""
    global in_flight_requests
    in_flight_requests += 1
    try:
        return await call_next(request)
    finally:
        in_flight_requests -= 1

# Factor 6: Stateless endpoints
@app.get("/health")
async def health():
    """Liveness check"""
    return {"status": "alive"}

@app.get("/ready")
async def ready():
    """Readiness check"""
    try:
        # Check backing services
        await db.fetch_one("SELECT 1")
        await cache.client.ping()
        return {"status": "ready"}
    except Exception as e:
        logger.error(f"Not ready: {e}")
        return {"status": "not ready"}, 503

@app.get("/users/{user_id}")
async def get_user(user_id: int):
    """Stateless endpoint - state from DB"""
    # Try cache first
    cached = await cache.client.get(f"user:{user_id}")
    if cached:
        return json.loads(cached)
    
    # Fetch from DB
    user = await db.fetch_one("SELECT * FROM users WHERE id = $1", user_id)
    if not user:
        raise HTTPException(404, "User not found")
    
    # Cache for next time
    await cache.client.setex(f"user:{user_id}", 300, json.dumps(dict(user)))
    
    return dict(user)
```

---

## 6. ⚙️ Factor 8: Concurrency — Procfile

### `Procfile`

```
# Factor 8: Different process types

# Web process (handles HTTP)
web: gunicorn app.main:app --workers $WORKERS --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:$PORT --graceful-timeout 30

# Background worker (handles async jobs)
worker: celery -A workers.celery_app worker --concurrency=4 --loglevel=$LOG_LEVEL

# Scheduled jobs (cron-like)
beat: celery -A workers.celery_app beat --loglevel=$LOG_LEVEL

# Release process (runs migrations)
release: python scripts/migrate.py
```

### Scaling

```bash
# On Heroku
$ heroku ps:scale web=3 worker=2

# On Kubernetes - deploy with multiple replicas
$ kubectl scale deployment my-app-web --replicas=3
$ kubectl scale deployment my-app-worker --replicas=2

# Each process type scales independently!
```

### `workers/celery_app.py`

```python
"""Celery worker process"""
from celery import Celery
from app.config import get_settings

settings = get_settings()

celery_app = Celery(
    "myapp",
    broker=settings.redis_url,
    backend=settings.redis_url,
)

# Beat schedule
celery_app.conf.beat_schedule = {
    "cleanup-every-hour": {
        "task": "workers.tasks.cleanup_old_records",
        "schedule": 3600,
    },
}
```

### `workers/tasks.py`

```python
"""Background tasks"""
from workers.celery_app import celery_app
import logging

logger = logging.getLogger(__name__)

@celery_app.task
def send_welcome_email(user_id: int):
    """Stateless task - all data in arguments + backing services"""
    logger.info(f"Sending welcome email to user {user_id}")
    # ... 

@celery_app.task
def cleanup_old_records():
    """Scheduled task"""
    logger.info("Running cleanup")
    # ...
```

---

## 7. 🐳 Factor 10: Dev/Prod Parity — Dockerfile

### `Dockerfile`

```dockerfile
# Same image runs in dev, staging, prod
FROM python:3.11-slim as base

# Factor 9: Fast startup - minimal base image
WORKDIR /app

# Factor 2: Explicit dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Non-root user (security best practice)
RUN useradd -m -u 1000 appuser
USER appuser

# Copy app code
COPY --chown=appuser:appuser . .

# Factor 7: Port binding (env decides actual port)
EXPOSE 8000

# Factor 9: Disposability - handle SIGTERM gracefully
STOPSIGNAL SIGTERM

# Factor 11: Logs go to stdout (Python unbuffered)
ENV PYTHONUNBUFFERED=1

# Factor 8: Default command (overridden per process type)
CMD ["gunicorn", "app.main:app", \
     "--workers", "4", \
     "--worker-class", "uvicorn.workers.UvicornWorker", \
     "--bind", "0.0.0.0:8000", \
     "--graceful-timeout", "30"]
```

### `docker-compose.yml` (Local Dev)

```yaml
version: '3.8'

services:
  # Factor 10: Same Postgres in dev as prod
  db:
    image: postgres:15
    environment:
      POSTGRES_USER: app
      POSTGRES_PASSWORD: app
      POSTGRES_DB: myapp
    ports: ["5432:5432"]
    volumes:
      - postgres_data:/var/lib/postgresql/data
  
  # Factor 10: Same Redis in dev as prod
  redis:
    image: redis:7-alpine
    ports: ["6379:6379"]
  
  # Factor 8: Web process
  web:
    build: .
    ports: ["8000:8000"]
    environment:
      DATABASE_URL: postgresql://app:app@db:5432/myapp
      REDIS_URL: redis://redis:6379/0
      DEBUG: "true"
      LOG_LEVEL: DEBUG
      STRIPE_SECRET_KEY: sk_test_...
    depends_on: [db, redis]
    command: gunicorn app.main:app --workers 2 --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000 --reload
  
  # Factor 8: Worker process (same image!)
  worker:
    build: .
    environment:
      DATABASE_URL: postgresql://app:app@db:5432/myapp
      REDIS_URL: redis://redis:6379/0
      LOG_LEVEL: DEBUG
    depends_on: [db, redis]
    command: celery -A workers.celery_app worker --concurrency=2 --loglevel=DEBUG
  
  # Factor 8: Beat process
  beat:
    build: .
    environment:
      DATABASE_URL: postgresql://app:app@db:5432/myapp
      REDIS_URL: redis://redis:6379/0
    depends_on: [db, redis]
    command: celery -A workers.celery_app beat --loglevel=INFO

volumes:
  postgres_data:
```

### Run

```bash
# Local dev (matches prod environment!)
$ docker-compose up

# Scale workers locally
$ docker-compose up --scale worker=3
```

---

## 8. 🛠 Factor 12: Admin Processes

### `scripts/migrate.py`

```python
"""
Database migrations - admin process.
Runs in SAME environment as app.
Uses SAME code and config.
"""
import asyncio
import asyncpg
from app.config import get_settings
import logging

logger = logging.getLogger(__name__)

async def migrate():
    """Apply database migrations"""
    settings = get_settings()
    
    logger.info("Starting migration...")
    conn = await asyncpg.connect(settings.database_url)
    
    try:
        # Track applied migrations
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version INTEGER PRIMARY KEY,
                applied_at TIMESTAMPTZ DEFAULT NOW()
            )
        """)
        
        # Get applied migrations
        applied = set(row["version"] for row in await conn.fetch(
            "SELECT version FROM schema_migrations"
        ))
        
        # Apply pending migrations
        migrations = [
            (1, "CREATE TABLE users (id SERIAL PRIMARY KEY, email VARCHAR UNIQUE NOT NULL)"),
            (2, "ALTER TABLE users ADD COLUMN name VARCHAR"),
            (3, "CREATE INDEX idx_users_email ON users(email)"),
        ]
        
        for version, sql in migrations:
            if version not in applied:
                logger.info(f"Applying migration {version}")
                await conn.execute(sql)
                await conn.execute(
                    "INSERT INTO schema_migrations (version) VALUES ($1)",
                    version
                )
                logger.info(f"✓ Migration {version} applied")
            else:
                logger.info(f"Migration {version} already applied")
        
        logger.info("✓ All migrations complete")
    
    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(migrate())
```

### Run Migration

```bash
# Locally
$ python scripts/migrate.py

# In Docker (same env as app)
$ docker-compose run web python scripts/migrate.py

# In production (Heroku)
$ heroku run python scripts/migrate.py

# In Kubernetes (as a Job)
$ kubectl run migrate --image=myapp:latest \
    --env-from secretRef:app-secrets \
    --command -- python scripts/migrate.py
```

### `scripts/seed_data.py`

```python
"""Seed test data - another admin process"""
import asyncio
from app.db import db

async def seed():
    await db.connect()
    
    users = [
        ("ashish@example.com", "Ashish Chaurasiya"),
        ("rahul@example.com", "Rahul Singh"),
        ("priya@example.com", "Priya Sharma"),
    ]
    
    for email, name in users:
        await db.execute(
            "INSERT INTO users (email, name) VALUES ($1, $2) ON CONFLICT DO NOTHING",
            email, name
        )
        print(f"✓ Added {email}")
    
    await db.disconnect()

if __name__ == "__main__":
    asyncio.run(seed())
```

---

## 9. 🎯 Putting It All Together

### Local Development

```bash
# 1. Clone repo (Factor 1: single codebase)
$ git clone https://github.com/example/myapp
$ cd myapp

# 2. Set up config (Factor 3)
$ cp .env.example .env
$ # Edit .env with your local settings

# 3. Start with Docker Compose (Factor 10: parity)
$ docker-compose up -d db redis

# 4. Run migrations (Factor 12: admin process)
$ docker-compose run web python scripts/migrate.py

# 5. Start app (Factor 8: concurrent processes)
$ docker-compose up

# 6. View logs (Factor 11: streamed to stdout)
$ docker-compose logs -f web
```

### Production Deployment (Kubernetes)

```yaml
# k8s/deployment.yaml

# ConfigMap (Factor 3: config from env)
apiVersion: v1
kind: ConfigMap
metadata:
  name: app-config
data:
  LOG_LEVEL: "INFO"
  WORKERS: "4"

---
# Secret (sensitive config)
apiVersion: v1
kind: Secret
metadata:
  name: app-secrets
stringData:
  DATABASE_URL: "postgresql://..."
  REDIS_URL: "redis://..."
  STRIPE_SECRET_KEY: "sk_live_..."

---
# Web deployment (Factor 8: web process)
apiVersion: apps/v1
kind: Deployment
metadata:
  name: app-web
spec:
  replicas: 3  # Horizontal scaling (Factor 6: stateless)
  selector:
    matchLabels:
      app: myapp
      tier: web
  template:
    metadata:
      labels:
        app: myapp
        tier: web
    spec:
      terminationGracePeriodSeconds: 30  # Factor 9: graceful shutdown
      containers:
      - name: web
        image: myapp:v1.2.3
        ports:
        - containerPort: 8000
        envFrom:
        - configMapRef:
            name: app-config
        - secretRef:
            name: app-secrets
        
        # Factor 9: Health checks
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 10
          periodSeconds: 30
        
        readinessProbe:
          httpGet:
            path: /ready
            port: 8000
          initialDelaySeconds: 5
          periodSeconds: 5
        
        # Graceful shutdown
        lifecycle:
          preStop:
            exec:
              command: ["sleep", "5"]  # Drain load balancer

---
# Worker deployment (separate process type!)
apiVersion: apps/v1
kind: Deployment
metadata:
  name: app-worker
spec:
  replicas: 2
  selector:
    matchLabels:
      app: myapp
      tier: worker
  template:
    metadata:
      labels:
        app: myapp
        tier: worker
    spec:
      containers:
      - name: worker
        image: myapp:v1.2.3
        command: ["celery", "-A", "workers.celery_app", "worker"]
        envFrom:
        - configMapRef:
            name: app-config
        - secretRef:
            name: app-secrets

---
# Migration Job (Factor 12: admin process)
apiVersion: batch/v1
kind: Job
metadata:
  name: app-migrate-v1-2-3
spec:
  template:
    spec:
      containers:
      - name: migrate
        image: myapp:v1.2.3
        command: ["python", "scripts/migrate.py"]
        envFrom:
        - secretRef:
            name: app-secrets
      restartPolicy: Never
```

---

## 10. ✅ Compliance Checklist

```
Factor 1: Codebase
   ☐ Single Git repo per app
   ☐ Same code deploys to dev/staging/prod
   ☐ No vendored deps in repo

Factor 2: Dependencies
   ☐ All deps in requirements.txt (no hidden!)
   ☐ Virtualenv or container isolation
   ☐ No system-wide assumptions

Factor 3: Config
   ☐ All config from env vars
   ☐ .env NOT committed (only .env.example)
   ☐ Secrets via secret manager in prod

Factor 4: Backing services
   ☐ DB/cache URL from env
   ☐ Can swap services without code changes

Factor 5: Build/release/run
   ☐ Build phase: docker build
   ☐ Release phase: tag image + config
   ☐ Run phase: kubectl apply
   ☐ No "hot fixes" in prod

Factor 6: Processes
   ☐ App is stateless
   ☐ Sessions in Redis (not memory)
   ☐ Filesystem ephemeral

Factor 7: Port binding
   ☐ App listens on PORT env var
   ☐ Embedded web server (Gunicorn)
   ☐ No external server dependencies

Factor 8: Concurrency
   ☐ Procfile defines process types
   ☐ Scale each type independently
   ☐ No "main process" pattern

Factor 9: Disposability
   ☐ App starts in < 30s
   ☐ Handles SIGTERM gracefully
   ☐ Finishes in-flight requests

Factor 10: Dev/prod parity
   ☐ Same services in all envs (Docker)
   ☐ Frequent deployments
   ☐ DevOps culture

Factor 11: Logs
   ☐ Logs to stdout (not files)
   ☐ Structured (JSON)
   ☐ Aggregated externally

Factor 12: Admin processes
   ☐ Migrations as scripts in repo
   ☐ Same image, different command
   ☐ Same config as app
```

---

## 11. Key Learnings Summary

```
✅ Pydantic Settings for type-safe env config
✅ Structured JSON logging to stdout
✅ Lifespan manager for startup/shutdown
✅ Procfile defines process types
✅ Docker Compose for dev/prod parity
✅ Migration scripts as admin processes
✅ Kubernetes Job for one-off tasks
✅ Health + readiness probes
✅ Graceful shutdown with SIGTERM
✅ Same image, multiple processes

🎯 Production 12-factor stack:
   ✓ Git repo + Dockerfile
   ✓ ConfigMap + Secret in K8s
   ✓ Multiple deployments per process type
   ✓ Logs → Fluentd → Elasticsearch
   ✓ Auto-scaling via HPA
   ✓ Graceful shutdown via preStop hook
```

---

## 🎬 What's Next?

In **Lecture 3**, we'll explore **Serverless Architecture** — Functions-as-a-Service, cold starts, and event-driven compute.

> **Next lecture:** [03_Serverless_Architecture.md](03_Serverless_Architecture.md)

---

## 📚 Try It Yourself

1. Audit your existing app against 12-factor checklist
2. Migrate config from files to env vars
3. Move sessions from memory to Redis
4. Convert logs from files to stdout
5. Deploy same image to dev/staging/prod
