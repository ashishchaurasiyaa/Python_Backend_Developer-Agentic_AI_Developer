"""
=============================================================================
DAY 49 — DOCKER FOR PYTHON DEVELOPERS
=============================================================================
Topics:
  1.  Dockerfile          — multi-stage build (builder + slim final)
  2.  docker-compose.yml  — FastAPI + PostgreSQL + Redis + Celery
  3.  Python Patterns     — wait-for-db, BaseSettings, graceful shutdown
  4.  Layers & Caching    — why requirements.txt goes first
  5.  Networking          — service names as hostnames, bridge network
  6.  Volumes             — named volumes, bind mounts for hot-reload
  7.  Security            — non-root user, secrets best practices
  8.  Commands            — build, run, exec, logs, ps, stop, rm
  9.  Python Specific     — .dockerignore, PYTHONDONTWRITEBYTECODE, PYTHONUNBUFFERED
  10. Health Checks       — HEALTHCHECK in Dockerfile, depends_on in compose
  11. Interview Q&A       — 10 questions
=============================================================================
"""

# ─────────────────────────────────────────────────────────────────────────────
# SECTION 1 — DOCKERFILE (multi-stage build)
# ─────────────────────────────────────────────────────────────────────────────
print("\n" + "=" * 70)
print("SECTION 1 — DOCKERFILE (multi-stage, production-grade)")
print("=" * 70)

DOCKERFILE = """
# ── Dockerfile ────────────────────────────────────────────────────────────
# Multi-stage build: keeps the final image small by separating
# build-time dependencies (compilers, pip cache) from runtime.

# ╔══════════════════════════════════════════════════════════╗
# ║  STAGE 1: builder — installs deps into a virtual env    ║
# ╚══════════════════════════════════════════════════════════╝
FROM python:3.12-slim AS builder

# Set environment variables for build stage
ENV PYTHONDONTWRITEBYTECODE=1 \\
    PYTHONUNBUFFERED=1 \\
    PIP_NO_CACHE_DIR=1 \\
    PIP_DISABLE_PIP_VERSION_CHECK=1 \\
    VIRTUAL_ENV=/app/venv

# Install system build dependencies (needed only during build)
RUN apt-get update && apt-get install -y --no-install-recommends \\
    build-essential \\
    libpq-dev \\
    && rm -rf /var/lib/apt/lists/*

# Create and activate venv
RUN python -m venv $VIRTUAL_ENV
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

WORKDIR /build

# ── CRITICAL: copy requirements BEFORE the rest of the code ──────────────
# Docker caches each layer. If requirements.txt hasn't changed,
# the pip install layer is reused from cache — saves minutes per build.
COPY requirements.txt .
RUN pip install --upgrade pip && \\
    pip install -r requirements.txt

# ╔══════════════════════════════════════════════════════════╗
# ║  STAGE 2: final — lean runtime image                    ║
# ╚══════════════════════════════════════════════════════════╝
FROM python:3.12-slim AS final

# Runtime env vars
ENV PYTHONDONTWRITEBYTECODE=1 \\
    PYTHONUNBUFFERED=1 \\
    VIRTUAL_ENV=/app/venv \\
    PATH="/app/venv/bin:$PATH" \\
    APP_ENV=production

# Install only runtime system libraries (no build tools)
RUN apt-get update && apt-get install -y --no-install-recommends \\
    libpq5 \\
    curl \\
    && rm -rf /var/lib/apt/lists/*

# ── SECURITY: create non-root user ────────────────────────────────────────
RUN groupadd --gid 1001 appgroup && \\
    useradd  --uid 1001 --gid appgroup --no-create-home appuser

WORKDIR /app

# Copy the pre-built venv from builder stage
COPY --from=builder /app/venv ./venv

# Copy application source (after venv — so code changes don't invalidate venv cache)
COPY --chown=appuser:appgroup . .

# Switch to non-root user
USER appuser

EXPOSE 8000

# ── HEALTHCHECK ────────────────────────────────────────────────────────────
# Docker will run this every 30s. If it fails 3 times, container = unhealthy.
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \\
    CMD curl -f http://localhost:8000/health || exit 1

# ── Entrypoint ────────────────────────────────────────────────────────────
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
# ──────────────────────────────────────────────────────────────────────────
"""

print(DOCKERFILE)

# ─────────────────────────────────────────────────────────────────────────────
# SECTION 2 — docker-compose.yml
# ─────────────────────────────────────────────────────────────────────────────
print("\n" + "=" * 70)
print("SECTION 2 — docker-compose.yml (FastAPI + PostgreSQL + Redis + Celery)")
print("=" * 70)

DOCKER_COMPOSE = """
# ── docker-compose.yml ────────────────────────────────────────────────────
# Stack: FastAPI web app | PostgreSQL DB | Redis | Celery worker
# Usage:
#   docker compose up --build          # start everything
#   docker compose up -d               # detached
#   docker compose logs -f web         # follow logs of one service
#   docker compose down -v             # stop + remove volumes

services:

  # ── FastAPI Web App ──────────────────────────────────────────────────────
  web:
    build:
      context: .
      dockerfile: Dockerfile
      target: final                   # use the 'final' stage of multi-stage build
    container_name: myapp_web
    ports:
      - "8000:8000"                   # host:container
    env_file:
      - .env                          # load from .env file (not baked into image)
    environment:
      - DATABASE_URL=postgresql://postgres:${POSTGRES_PASSWORD}@db:5432/${POSTGRES_DB}
      - REDIS_URL=redis://redis:6379/0
      - CELERY_BROKER_URL=redis://redis:6379/1
    volumes:
      # Bind mount for hot-reload in development (comment out for production)
      - ./app:/app/app
    depends_on:
      db:
        condition: service_healthy    # wait until DB passes its HEALTHCHECK
      redis:
        condition: service_healthy
    networks:
      - app_network
    restart: unless-stopped

  # ── Celery Worker ────────────────────────────────────────────────────────
  celery_worker:
    build:
      context: .
      dockerfile: Dockerfile
      target: final
    container_name: myapp_celery
    command: celery -A app.tasks worker --loglevel=info --concurrency=4
    env_file:
      - .env
    environment:
      - DATABASE_URL=postgresql://postgres:${POSTGRES_PASSWORD}@db:5432/${POSTGRES_DB}
      - REDIS_URL=redis://redis:6379/0
      - CELERY_BROKER_URL=redis://redis:6379/1
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_healthy
    networks:
      - app_network
    restart: unless-stopped

  # ── Celery Beat (scheduler) ─────────────────────────────────────────────
  celery_beat:
    build:
      context: .
      dockerfile: Dockerfile
      target: final
    container_name: myapp_beat
    command: celery -A app.tasks beat --loglevel=info
    env_file:
      - .env
    depends_on:
      - redis
    networks:
      - app_network
    restart: unless-stopped

  # ── PostgreSQL ──────────────────────────────────────────────────────────
  db:
    image: postgres:16-alpine
    container_name: myapp_postgres
    environment:
      POSTGRES_USER:     ${POSTGRES_USER:-postgres}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:?POSTGRES_PASSWORD required}
      POSTGRES_DB:       ${POSTGRES_DB:-myapp}
    volumes:
      - postgres_data:/var/lib/postgresql/data   # named volume — persists data
      - ./scripts/init.sql:/docker-entrypoint-initdb.d/init.sql  # init script
    ports:
      - "5432:5432"    # expose only in dev; remove in production
    networks:
      - app_network
    restart: unless-stopped
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER:-postgres} -d ${POSTGRES_DB:-myapp}"]
      interval: 10s
      timeout: 5s
      retries: 5
      start_period: 10s

  # ── Redis ───────────────────────────────────────────────────────────────
  redis:
    image: redis:7-alpine
    container_name: myapp_redis
    command: redis-server --maxmemory 256mb --maxmemory-policy allkeys-lru
    ports:
      - "6379:6379"    # expose only in dev
    volumes:
      - redis_data:/data
    networks:
      - app_network
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5

  # ── Flower (Celery monitoring) ──────────────────────────────────────────
  flower:
    image: mher/flower:2.0
    container_name: myapp_flower
    environment:
      - CELERY_BROKER_URL=redis://redis:6379/1
      - FLOWER_PORT=5555
    ports:
      - "5555:5555"
    depends_on:
      - redis
    networks:
      - app_network

# ── Named volumes (Docker manages the storage location) ────────────────────
volumes:
  postgres_data:
    driver: local
  redis_data:
    driver: local

# ── Custom bridge network ──────────────────────────────────────────────────
# Services communicate using their service name as hostname (e.g., "db", "redis")
networks:
  app_network:
    driver: bridge
# ──────────────────────────────────────────────────────────────────────────
"""

print(DOCKER_COMPOSE)


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 3 — PYTHON PATTERNS
# ─────────────────────────────────────────────────────────────────────────────
print("\n" + "=" * 70)
print("SECTION 3 — PYTHON PATTERNS IN DOCKER")
print("=" * 70)

# ── 3a. Wait-for-DB Pattern ────────────────────────────────────────────────
WAIT_FOR_DB = '''
# app/startup.py — wait for Postgres to be ready before starting FastAPI

import asyncio
import asyncpg
import os
import sys

DATABASE_URL = os.environ["DATABASE_URL"]

async def wait_for_db(retries: int = 10, delay: float = 2.0) -> None:
    """Poll the database until it accepts connections."""
    for attempt in range(1, retries + 1):
        try:
            conn = await asyncpg.connect(DATABASE_URL)
            await conn.close()
            print(f"[startup] Database ready (attempt {attempt})")
            return
        except Exception as e:
            print(f"[startup] DB not ready (attempt {attempt}/{retries}): {e}")
            if attempt == retries:
                print("[startup] Could not connect to DB. Exiting.")
                sys.exit(1)
            await asyncio.sleep(delay)


# Alternative: use depends_on: condition: service_healthy in compose
# The healthcheck approach is cleaner — but wait_for_db is useful
# when you need fine-grained control or retries inside the app.
'''

print("── 3a. Wait-for-DB Pattern ──")
print(WAIT_FOR_DB)

# ── 3b. BaseSettings for environment config ────────────────────────────────
BASE_SETTINGS = '''
# app/config.py — environment configuration with Pydantic BaseSettings

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, SecretStr
from functools import lru_cache


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # App
    app_name:    str = "MyApp"
    app_env:     str = Field("development", pattern="^(development|staging|production)$")
    debug:       bool = False
    secret_key:  SecretStr = "changeme-in-production"

    # Database — read from DATABASE_URL env var (set by docker-compose)
    database_url: str = "postgresql://postgres:password@localhost:5432/myapp"

    # Redis
    redis_url:    str = "redis://localhost:6379/0"

    # Celery
    celery_broker_url:  str = "redis://localhost:6379/1"
    celery_result_backend: str = "redis://localhost:6379/2"

    # Workers
    workers: int = Field(4, ge=1, le=32)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Singleton: read settings once, cache for the app lifetime."""
    return Settings()


# Usage in FastAPI:
# from app.config import get_settings
# settings = get_settings()
# print(settings.database_url)
'''

print("── 3b. BaseSettings Pattern ──")
print(BASE_SETTINGS)

# ── 3c. Graceful Shutdown ──────────────────────────────────────────────────
GRACEFUL_SHUTDOWN = '''
# app/main.py — graceful SIGTERM handler for Docker

import asyncio
import signal
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI lifespan: startup → yield → shutdown."""
    # ── Startup ─────────────────────────────────────────────────────────────
    logger.info("Starting up — connecting to DB and Redis...")
    # await database.connect()
    # await redis_client.ping()
    logger.info("Startup complete")

    yield  # application is running

    # ── Shutdown ─────────────────────────────────────────────────────────────
    # Docker sends SIGTERM → process has grace period (default 10s) to finish
    logger.info("Shutting down — closing connections...")
    # await database.disconnect()
    # await redis_client.close()
    logger.info("Shutdown complete")


app = FastAPI(lifespan=lifespan)


# Low-level SIGTERM handler (alternative to lifespan, useful for workers)
def setup_signal_handlers():
    loop = asyncio.get_event_loop()

    def handle_sigterm():
        logger.info("SIGTERM received — initiating graceful shutdown")
        loop.stop()

    loop.add_signal_handler(signal.SIGTERM, handle_sigterm)
    loop.add_signal_handler(signal.SIGINT,  handle_sigterm)
'''

print("── 3c. Graceful Shutdown Pattern ──")
print(GRACEFUL_SHUTDOWN)


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 4 — LAYER CACHING
# ─────────────────────────────────────────────────────────────────────────────
print("\n" + "=" * 70)
print("SECTION 4 — DOCKER LAYERS & CACHING")
print("=" * 70)

LAYER_CACHING = """
HOW DOCKER LAYER CACHING WORKS:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Each Dockerfile instruction creates a layer. Docker caches layers
and reuses them if the instruction AND its inputs haven't changed.
Once any layer is invalidated, ALL subsequent layers are rebuilt.

WRONG ORDER (slow) — code changes invalidate pip install:
  COPY . .                  ← copies entire code
  RUN pip install -r requirements.txt  ← ALWAYS re-runs if any file changed

CORRECT ORDER (fast) — pip install is cached:
  COPY requirements.txt .   ← only copy the dependency file
  RUN pip install -r requirements.txt  ← cached if requirements.txt unchanged
  COPY . .                  ← copy source code AFTER (won't affect pip cache)

Timeline comparison:
  First build:         ~3 min (pip downloads all packages)
  Code change, BAD:    ~3 min (pip re-downloads — cache invalidated by COPY .)
  Code change, GOOD:   ~10 sec (pip layer cached, only COPY . recomputed)

Other caching tips:
  - Sort apt-get packages alphabetically for stable layer hashing
  - Combine RUN commands with && to reduce layer count
  - Use .dockerignore to prevent unnecessary file changes from busting cache
  - BuildKit cache mounts: RUN --mount=type=cache,target=/root/.cache/pip pip install ...
"""
print(LAYER_CACHING)

BUILDKIT_EXAMPLE = '''
# With BuildKit (Docker 20.10+) — pip cache persists across builds
# syntax=docker/dockerfile:1
FROM python:3.12-slim AS builder

# Cache pip downloads between builds — HUGE speedup
RUN --mount=type=cache,target=/root/.cache/pip \\
    --mount=type=bind,source=requirements.txt,target=requirements.txt \\
    pip install -r requirements.txt

# Set DOCKER_BUILDKIT=1 before docker build, or use: docker buildx build
'''

print(BUILDKIT_EXAMPLE)


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 5 — NETWORKING
# ─────────────────────────────────────────────────────────────────────────────
print("\n" + "=" * 70)
print("SECTION 5 — DOCKER NETWORKING")
print("=" * 70)

NETWORKING = """
HOW DOCKER NETWORKING WORKS:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Docker Compose creates a BRIDGE NETWORK for the stack by default.
Services can reach each other using the SERVICE NAME as the hostname.

Service Name Resolution (inside the container network):
  web → db       via hostname: "db"       (not "localhost" or IP)
  web → redis    via hostname: "redis"
  web → worker   via hostname: "celery_worker"

Why service names work:
  Docker embeds a DNS server that maps service names to container IPs.
  The IP can change on restart — always use the service name, never hardcode IPs.

Example connection strings IN the container environment:
  DATABASE_URL = "postgresql://user:pass@db:5432/mydb"
                                          ^^
                                          service name — resolves inside network

  REDIS_URL    = "redis://redis:6379/0"
                          ^^^^^
                          service name

Port mapping: HOST:CONTAINER
  ports:
    - "8000:8000"   # host port 8000 → container port 8000
    - "5432:5432"   # expose DB to host machine (dev only!)

  The left side is accessible from your laptop.
  The right side is the container's internal port.
  Services on the same Docker network talk directly on the CONTAINER port.

Network types:
  bridge  — default; isolated from host, services can talk to each other
  host    — container shares host network stack (Linux only, no isolation)
  none    — fully isolated (no network)
  overlay — multi-host (Docker Swarm / Kubernetes)
"""
print(NETWORKING)


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 6 — VOLUMES
# ─────────────────────────────────────────────────────────────────────────────
print("\n" + "=" * 70)
print("SECTION 6 — VOLUMES")
print("=" * 70)

VOLUMES = """
DOCKER VOLUMES — two main types:

1. NAMED VOLUMES (managed by Docker) — for persistent data:
   ─────────────────────────────────────────────────────────
   volumes:
     - postgres_data:/var/lib/postgresql/data   # data survives container restart
     - redis_data:/data

   volumes:          # top-level declaration
     postgres_data:
     redis_data:

   - Docker stores data in /var/lib/docker/volumes/ on the host
   - Survives `docker compose down` but destroyed by `docker compose down -v`
   - Better performance than bind mounts for databases

2. BIND MOUNTS (host path ↔ container path) — for hot-reload in development:
   ─────────────────────────────────────────────────────────────────────────
   volumes:
     - ./app:/app/app    # host ./app directory → /app/app in container

   - Changes on host are immediately visible in container (no rebuild)
   - uvicorn --reload detects file changes and restarts automatically
   - NEVER use bind mounts for node_modules or __pycache__ (performance hit)

3. tmpfs mounts — RAM-backed temporary storage:
   ─────────────────────────────────────────────────────────────────────────
   tmpfs:
     - /tmp
     - /run

   - Fast, but lost when container stops
   - Good for secrets or temp files that shouldn't touch disk

Development vs Production:
  Development:  use bind mounts for hot-reload
  Production:   copy code into image (no bind mount), use named volumes for data

Override with docker-compose.override.yml (auto-merged in dev):
  # docker-compose.override.yml
  services:
    web:
      volumes:
        - ./app:/app/app          # only in dev
      command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
"""
print(VOLUMES)


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 7 — SECURITY
# ─────────────────────────────────────────────────────────────────────────────
print("\n" + "=" * 70)
print("SECTION 7 — DOCKER SECURITY BEST PRACTICES")
print("=" * 70)

SECURITY = '''
# ── 7a: NON-ROOT USER ─────────────────────────────────────────────────────
# By default containers run as root — dangerous if there's a breakout.
# Create a dedicated user:

RUN groupadd --gid 1001 appgroup && \\
    useradd  --uid 1001 --gid appgroup --shell /bin/bash --no-create-home appuser

COPY --chown=appuser:appgroup . /app
USER appuser   # all subsequent RUN, CMD, ENTRYPOINT run as appuser

# ── 7b: SECRETS — NEVER bake secrets into the image ─────────────────────
# BAD:
ENV DATABASE_PASSWORD="mysecret"   # visible in `docker inspect` and image layers

# GOOD options:
# 1. .env file (not committed to git, passed at runtime):
#    docker run --env-file .env myimage
#    Or in compose: env_file: - .env

# 2. Docker secrets (Swarm):
#    secrets:
#      db_password:
#        file: ./secrets/db_password.txt

# 3. Cloud secret managers (AWS Secrets Manager, GCP Secret Manager)
#    Inject into container at startup via entrypoint script or init container.

# 4. BuildKit secret mounts (build time only, NOT in final image):
#    RUN --mount=type=secret,id=pip_token pip install --extra-index-url ...

# ── 7c: ARG vs ENV ────────────────────────────────────────────────────────
# ARG  — build-time variable (NOT in final image, NOT in `docker inspect`)
# ENV  — runtime variable (IN the image, visible in `docker inspect`)

ARG BUILD_VERSION=dev          # only available during docker build
ENV APP_VERSION=$BUILD_VERSION  # baked into image (OK for non-sensitive data)

# NEVER do: ARG DATABASE_PASSWORD → ENV DATABASE_PASSWORD=$DATABASE_PASSWORD
# ARG values can be extracted from the build cache even if not in ENV.
# For secrets at build time: use BuildKit secret mounts (--mount=type=secret).

# ── 7d: Minimal base images ───────────────────────────────────────────────
# python:3.12-slim    — ~45 MB (stripped Debian, no extras)
# python:3.12-alpine  — ~20 MB (musl libc — may break some C extensions)
# gcr.io/distroless/python3 — ~30 MB (no shell, no package manager — hardened)

# ── 7e: Scan images for vulnerabilities ───────────────────────────────────
# docker scout cves myimage:latest
# trivy image myimage:latest
# snyk container test myimage:latest
'''

print(SECURITY)


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 8 — ESSENTIAL DOCKER COMMANDS
# ─────────────────────────────────────────────────────────────────────────────
print("\n" + "=" * 70)
print("SECTION 8 — ESSENTIAL DOCKER COMMANDS")
print("=" * 70)

COMMANDS = {
    "BUILD": [
        ("docker build -t myapp:latest .",
         "Build image from Dockerfile in current dir, tag as myapp:latest"),
        ("docker build -t myapp:v1.2 --target final .",
         "Multi-stage: build only up to the 'final' stage"),
        ("docker build --no-cache -t myapp:latest .",
         "Force full rebuild, ignore all layer cache"),
        ("docker buildx build --platform linux/amd64,linux/arm64 -t myapp:latest --push .",
         "Multi-platform build and push to registry"),
    ],
    "RUN": [
        ("docker run -d -p 8000:8000 --name myapp myapp:latest",
         "Run container detached (-d), map port, give it a name"),
        ("docker run --env-file .env -v $(pwd)/data:/app/data myapp:latest",
         "Pass .env file and mount a volume"),
        ("docker run --rm -it myapp:latest bash",
         "Interactive shell, auto-remove container on exit"),
        ("docker run --memory=512m --cpus=1.0 myapp:latest",
         "Resource limits: 512 MB RAM, 1 CPU core"),
    ],
    "INSPECT / DEBUG": [
        ("docker logs myapp",           "Show stdout/stderr of running container"),
        ("docker logs -f --tail=100 myapp", "Follow logs, last 100 lines"),
        ("docker exec -it myapp bash",  "Open interactive shell inside running container"),
        ("docker exec myapp python -c \"from app.config import get_settings; print(get_settings())\"",
         "Run one-off Python command inside container"),
        ("docker inspect myapp",        "Full container metadata (JSON)"),
        ("docker stats",                "Live CPU/memory usage for all containers"),
        ("docker top myapp",            "Processes running inside the container"),
    ],
    "MANAGE": [
        ("docker ps",                   "List running containers"),
        ("docker ps -a",                "List ALL containers (including stopped)"),
        ("docker stop myapp",           "Send SIGTERM → wait grace period → SIGKILL"),
        ("docker kill myapp",           "Send SIGKILL immediately (no graceful stop)"),
        ("docker rm myapp",             "Remove stopped container"),
        ("docker rm -f myapp",          "Force remove (stop + rm) running container"),
        ("docker rmi myapp:latest",     "Remove image"),
        ("docker system prune -a",      "Remove ALL unused images, containers, volumes"),
    ],
    "COMPOSE": [
        ("docker compose up --build",   "Build and start all services"),
        ("docker compose up -d",        "Start detached (background)"),
        ("docker compose down",         "Stop and remove containers (keep volumes)"),
        ("docker compose down -v",      "Stop, remove containers AND volumes"),
        ("docker compose logs -f web",  "Follow logs of the 'web' service only"),
        ("docker compose exec web bash","Shell into the running 'web' service"),
        ("docker compose ps",           "Status of all services in the stack"),
        ("docker compose restart web",  "Restart one service without rebuilding"),
        ("docker compose scale worker=3", "Run 3 replicas of the worker service"),
    ],
    "REGISTRY": [
        ("docker login registry.example.com", "Authenticate with a registry"),
        ("docker tag myapp:latest registry.example.com/team/myapp:v1.2",
         "Tag for registry"),
        ("docker push registry.example.com/team/myapp:v1.2", "Push to registry"),
        ("docker pull registry.example.com/team/myapp:v1.2", "Pull from registry"),
    ],
}

for category, cmd_list in COMMANDS.items():
    print(f"\n── {category} {'─' * (50 - len(category))}")
    for cmd, explanation in cmd_list:
        print(f"  $ {cmd}")
        print(f"    → {explanation}")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 9 — PYTHON-SPECIFIC BEST PRACTICES
# ─────────────────────────────────────────────────────────────────────────────
print("\n" + "=" * 70)
print("SECTION 9 — PYTHON-SPECIFIC DOCKER PRACTICES")
print("=" * 70)

DOCKERIGNORE = """
── .dockerignore ─────────────────────────────────────────────────────────────
(same syntax as .gitignore — files here are NOT sent to Docker build context)

# Python
__pycache__/
*.py[cod]
*.pyo
*.pyd
.Python
*.egg-info/
dist/
build/
*.egg

# Virtual environments (NEVER copy venv into image)
venv/
.venv/
env/
.env/

# Secrets (NEVER copy into image)
.env
.env.*
*.pem
*.key
secrets/

# Dev tools
.git/
.gitignore
.pytest_cache/
.mypy_cache/
.ruff_cache/
htmlcov/
.coverage
*.log

# Docker files themselves (optional)
Dockerfile*
docker-compose*.yml

# IDE
.idea/
.vscode/
*.swp
"""

PYTHON_ENV_VARS = """
── Python ENV vars in Dockerfile ────────────────────────────────────────────

ENV PYTHONDONTWRITEBYTECODE=1
  - Prevents Python from writing .pyc bytecode files
  - Reduces image size and eliminates container-to-host cache pollution
  - Without this, Python creates __pycache__/ everywhere

ENV PYTHONUNBUFFERED=1
  - Forces stdout/stderr to be unbuffered (no line-buffering)
  - Critical for Docker: logs appear immediately in `docker logs`
  - Without this, log output may be delayed or lost on crash

ENV PYTHONFAULTHANDLER=1
  - Enables Python fault handler (prints traceback on segfault / SIGABRT)
  - Very helpful for debugging native extension crashes in containers

ENV PYTHONHASHSEED=0
  - Deterministic hash randomization (useful for reproducible tests)
  - Leave unset in production (randomization is a security feature)

Example combined:
  ENV PYTHONDONTWRITEBYTECODE=1 \\
      PYTHONUNBUFFERED=1 \\
      PYTHONFAULTHANDLER=1
"""

print(DOCKERIGNORE)
print(PYTHON_ENV_VARS)


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 10 — HEALTH CHECKS
# ─────────────────────────────────────────────────────────────────────────────
print("\n" + "=" * 70)
print("SECTION 10 — HEALTH CHECKS")
print("=" * 70)

HEALTH_CHECKS = '''
# ── FastAPI health endpoint ───────────────────────────────────────────────
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncSession

app = FastAPI()

@app.get("/health")
async def health_check():
    """Lightweight health endpoint — Docker HEALTHCHECK hits this."""
    return {"status": "ok"}

@app.get("/health/ready")
async def readiness_check(db: AsyncSession = Depends(get_db)):
    """Deep health — checks DB and Redis connectivity."""
    try:
        await db.execute("SELECT 1")
        # await redis.ping()
        return {"status": "ready", "db": "ok", "redis": "ok"}
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Not ready: {e}")

# ──────────────────────────────────────────────────────────────────────────────
# HEALTHCHECK in Dockerfile:
# ──────────────────────────────────────────────────────────────────────────────
HEALTHCHECK_DOCKERFILE = """
HEALTHCHECK --interval=30s    # how often to check
            --timeout=10s     # how long to wait for a response
            --start-period=15s # grace period on container start (don't fail yet)
            --retries=3       # fail after 3 consecutive failures
    CMD curl -f http://localhost:8000/health || exit 1
"""

# ──────────────────────────────────────────────────────────────────────────────
# depends_on with service_healthy in docker-compose.yml:
# ──────────────────────────────────────────────────────────────────────────────
DEPENDS_ON_COMPOSE = """
services:
  web:
    depends_on:
      db:
        condition: service_healthy      # wait until db HEALTHCHECK passes
      redis:
        condition: service_healthy

  db:
    image: postgres:16-alpine
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 10s
      timeout: 5s
      retries: 5
      start_period: 10s                 # extra grace for postgres to initialize

  redis:
    image: redis:7-alpine
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 3s
      retries: 5
"""
# Container states: starting → healthy | unhealthy | (no healthcheck)
# depends_on: service_healthy blocks until the condition is met.
'''

print(HEALTH_CHECKS)


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 11 — INTERVIEW Q&A
# ─────────────────────────────────────────────────────────────────────────────
print("\n" + "=" * 70)
print("SECTION 11 — INTERVIEW Q&A (10 Questions)")
print("=" * 70)

QA = """
Q1. Why do we COPY requirements.txt before COPY . . in a Dockerfile?
A1. Docker caches each layer. If requirements.txt is copied first and hasn't
    changed, the pip install layer is reused from cache — even if source code
    changed. Copying all code first means any code change busts the pip cache
    and triggers a full reinstall (slow). Correct order: COPY requirements.txt →
    RUN pip install → COPY . .

Q2. What is a multi-stage Docker build and why is it valuable for Python?
A2. Multi-stage uses multiple FROM instructions. Stage 1 (builder) installs
    build tools and compiles/installs Python packages into a venv.
    Stage 2 (final) uses a slim base, copies only the venv from the builder,
    and runs the app. Build tools (gcc, libpq-dev, pip cache) never appear
    in the final image — smaller, faster, more secure.

Q3. What is the difference between CMD and ENTRYPOINT in a Dockerfile?
A3. ENTRYPOINT defines the fixed executable; CMD provides default arguments.
    If you use CMD only: the whole command is replaceable at `docker run`.
    Combined: ENTRYPOINT ["python"] + CMD ["app.py"] → docker run image script.py
    overrides CMD but not ENTRYPOINT. Most Python apps use CMD only for flexibility.

Q4. Why are named volumes better than bind mounts for databases?
A4. Named volumes are managed by Docker, stored in Docker's internal path
    (/var/lib/docker/volumes/). They have better I/O performance on non-Linux
    hosts (macOS/Windows use VM-based translation for bind mounts — slow).
    Named volumes are also portable — they don't depend on the host directory
    structure. Use bind mounts only for hot-reload of source code in development.

Q5. How do containers on the same Compose network reach each other?
A5. Docker Compose creates a bridge network and runs an embedded DNS server.
    Each service's name is a valid hostname within that network. So `web`
    connects to Postgres via hostname `db` and port 5432 (container port,
    not the host-mapped port). IPs can change on restart — always use names.

Q6. What do PYTHONDONTWRITEBYTECODE and PYTHONUNBUFFERED do?
A6. PYTHONDONTWRITEBYTECODE=1: prevents .pyc file creation → smaller image,
    no cache pollution when source is mounted as a bind mount.
    PYTHONUNBUFFERED=1: forces unbuffered stdout/stderr → logs appear
    immediately in `docker logs` without delay. Critical for debugging.

Q7. How should you handle secrets in Docker — what NOT to do?
A7. NEVER: bake secrets into ENV in Dockerfile (visible in `docker inspect`),
    copy .env files into the image, or use ARG → ENV for passwords.
    DO: pass secrets at runtime via --env-file .env (not in image), use
    Docker secrets for Swarm, cloud secret managers (AWS SM, GCP SM), or
    BuildKit --mount=type=secret for build-time secrets.

Q8. What is HEALTHCHECK in Docker and how does depends_on use it?
A8. HEALTHCHECK defines a command Docker runs periodically to test container
    health (healthy / unhealthy). In docker-compose, `depends_on: condition:
    service_healthy` makes a service wait until the dependency's HEALTHCHECK
    passes before starting — ensuring Postgres is ready before the web app starts.

Q9. How do you gracefully shut down a Python app in Docker?
A9. Docker sends SIGTERM on `docker stop` (default 10s grace period, then SIGKILL).
    Python handles SIGTERM via signal.signal(signal.SIGTERM, handler) or
    FastAPI's lifespan context manager. In the handler: close DB connections,
    finish in-flight requests, flush logs. Set --stop-timeout in compose for
    longer grace periods (e.g., for batch workers).

Q10. What should always be in .dockerignore for a Python project?
A10. At minimum: venv/, .venv/ (never copy venv into image), __pycache__/,
     *.pyc (bytecode), .env / .env.* (secrets), .git/ (version history),
     .pytest_cache/, .mypy_cache/ (tool caches), and test fixtures if large.
     Keeping .dockerignore tight reduces build context size (speeds up
     `docker build`) and prevents accidental secret inclusion.
"""
print(QA)
