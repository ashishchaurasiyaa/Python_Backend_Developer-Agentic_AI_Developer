"""
Phase3_DevOps — Docker + Nginx Practical
=========================================
Topics covered:
  1. Dockerfile patterns (multi-stage, non-root user, layer caching)
  2. docker-compose.yml (FastAPI + PostgreSQL + Redis + Nginx)
  3. Docker networking, volumes, health checks
  4. Nginx reverse proxy config (upstream, proxy_pass, SSL)
  5. Nginx rate limiting, caching, security headers
  6. docker-py SDK demo (list/run containers programmatically)
  7. Production best practices

Run:
  pip install docker
  python 01_docker_nginx_practical.py
"""

import json
import os
import textwrap

# ─────────────────────────────────────────────────────────────────────────────
# SECTION 1: Dockerfile Patterns
# INTERVIEW: Multi-stage build, non-root user, layer caching order
# ─────────────────────────────────────────────────────────────────────────────

DOCKERFILE_FASTAPI = """\
# ─── Multi-stage Dockerfile for FastAPI ───
# INTERVIEW: Multi-stage = smaller final image (no build tools in prod)

# ── Stage 1: Builder ──────────────────────────────────────────────
FROM python:3.12-slim AS builder

WORKDIR /build

# INTERVIEW: Copy requirements FIRST → cache this layer
# If code changes but requirements don't → this layer stays cached
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ── Stage 2: Final Image ──────────────────────────────────────────
FROM python:3.12-slim AS final

# INTERVIEW: Non-root user = security best practice
RUN groupadd -r appuser && useradd -r -g appuser appuser

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /install /usr/local

# Copy application code
COPY --chown=appuser:appuser . .

# Switch to non-root
USER appuser

# INTERVIEW: EXPOSE is documentation only (doesn't publish port)
EXPOSE 8000

# INTERVIEW: Healthcheck = Docker knows if container is healthy
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \\
    CMD curl -f http://localhost:8000/health || exit 1

# INTERVIEW: Use exec form (JSON array) — not shell form
# Shell form: CMD uvicorn main:app  ← PID 1 = shell, signals not forwarded!
# Exec form:  CMD ["uvicorn", ...]  ← PID 1 = uvicorn, signals handled correctly
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
"""

DOCKERFILE_OPTIMIZED_TIPS = {
    "Layer order": "COPY requirements.txt before COPY . (cache dependencies separately)",
    "Multi-stage": "Builder stage installs deps; Final stage is slim (no gcc, pip, etc.)",
    "Non-root":    "RUN useradd → USER appuser (security: no root in container)",
    "No secrets":  "NEVER add API keys in Dockerfile — use env vars or secrets",
    ".dockerignore": "Exclude: .git, .venv, __pycache__, *.pyc, .env, tests/",
    "COPY vs ADD": "COPY for files, ADD only for URLs/tar extraction",
    "CMD exec form": "CMD ['uvicorn'...] not CMD uvicorn (PID 1 signal handling)",
}

# ─────────────────────────────────────────────────────────────────────────────
# SECTION 2: docker-compose.yml
# INTERVIEW: Multi-service local dev + production patterns
# ─────────────────────────────────────────────────────────────────────────────

DOCKER_COMPOSE = """\
# docker-compose.yml — FastAPI + PostgreSQL + Redis + Nginx
# INTERVIEW: version: "3.9" (compose spec)

services:

  # ── FastAPI Application ──────────────────────────────────────────
  api:
    build:
      context: .
      dockerfile: Dockerfile
      target: final              # multi-stage target
    image: myapp:latest
    container_name: myapp-api
    restart: unless-stopped      # INTERVIEW: always/unless-stopped/on-failure
    environment:
      DATABASE_URL: postgresql+asyncpg://user:password@db:5432/myapp
      REDIS_URL:    redis://redis:6379/0
      SECRET_KEY:   ${SECRET_KEY}  # from .env file
    depends_on:
      db:
        condition: service_healthy   # wait for DB healthcheck
      redis:
        condition: service_started
    networks:
      - backend
    volumes:
      - ./logs:/app/logs            # log persistence
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3

  # ── PostgreSQL ───────────────────────────────────────────────────
  db:
    image: postgres:16-alpine
    container_name: myapp-db
    restart: unless-stopped
    environment:
      POSTGRES_USER:     user
      POSTGRES_PASSWORD: password
      POSTGRES_DB:       myapp
    volumes:
      - postgres_data:/var/lib/postgresql/data   # named volume = persistent
      - ./init.sql:/docker-entrypoint-initdb.d/init.sql  # runs on first start
    networks:
      - backend
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U user -d myapp"]
      interval: 10s
      timeout: 5s
      retries: 5

  # ── Redis ────────────────────────────────────────────────────────
  redis:
    image: redis:7-alpine
    container_name: myapp-redis
    restart: unless-stopped
    command: redis-server --appendonly yes  # AOF persistence
    volumes:
      - redis_data:/data
    networks:
      - backend

  # ── Nginx Reverse Proxy ──────────────────────────────────────────
  nginx:
    image: nginx:alpine
    container_name: myapp-nginx
    restart: unless-stopped
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx/nginx.conf:/etc/nginx/nginx.conf:ro
      - ./nginx/certs:/etc/nginx/certs:ro
      - static_files:/var/www/static:ro
    depends_on:
      - api
    networks:
      - frontend
      - backend

  # ── Celery Worker ────────────────────────────────────────────────
  worker:
    build: .
    command: celery -A tasks worker --loglevel=info --concurrency=4
    environment:
      CELERY_BROKER_URL: redis://redis:6379/1
    depends_on:
      - redis
      - db
    networks:
      - backend
    deploy:
      replicas: 2     # INTERVIEW: docker stack deploy se scaling

# ── Networks ─────────────────────────────────────────────────────
networks:
  frontend:  # Nginx ↔ public internet
  backend:   # Internal services (not exposed to internet)

# ── Volumes ──────────────────────────────────────────────────────
volumes:
  postgres_data:   # Named volume: survives container restart
  redis_data:
  static_files:
"""

# ─────────────────────────────────────────────────────────────────────────────
# SECTION 3: Nginx Configuration
# INTERVIEW: Upstream, proxy_pass, rate limiting, SSL, caching
# ─────────────────────────────────────────────────────────────────────────────

NGINX_CONF = """\
# nginx.conf — Production FastAPI reverse proxy

worker_processes auto;    # INTERVIEW: auto = CPU core count
events {
    worker_connections 1024;
    use epoll;            # Linux epoll = best performance
}

http {
    # ── Rate Limiting ──────────────────────────────────────────────
    # INTERVIEW: limit_req_zone = shared memory zone for counters
    limit_req_zone $binary_remote_addr zone=api_limit:10m rate=10r/s;
    limit_req_zone $binary_remote_addr zone=auth_limit:10m rate=5r/m;

    # ── Upstream (load balancing) ──────────────────────────────────
    # INTERVIEW: upstream = pool of backend servers
    upstream fastapi_app {
        # least_conn = route to server with fewest active connections
        least_conn;
        server api:8000;          # container name:port
        # server api2:8000;       # add more for horizontal scaling
        keepalive 32;             # connection pool size
    }

    # ── HTTP → HTTPS redirect ──────────────────────────────────────
    server {
        listen 80;
        server_name example.com www.example.com;
        return 301 https://$server_name$request_uri;
    }

    # ── HTTPS Server ──────────────────────────────────────────────
    server {
        listen 443 ssl http2;
        server_name example.com www.example.com;

        # SSL
        ssl_certificate     /etc/nginx/certs/cert.pem;
        ssl_certificate_key /etc/nginx/certs/key.pem;
        ssl_protocols       TLSv1.2 TLSv1.3;
        ssl_ciphers         HIGH:!aNULL:!MD5;

        # HSTS
        add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;

        # Security headers
        add_header X-Content-Type-Options nosniff;
        add_header X-Frame-Options DENY;
        add_header Referrer-Policy strict-origin-when-cross-origin;

        # ── API endpoints ──────────────────────────────────────────
        location /api/ {
            # INTERVIEW: Rate limiting
            limit_req zone=api_limit burst=20 nodelay;
            limit_req_status 429;

            # Proxy settings
            proxy_pass         http://fastapi_app;
            proxy_set_header   Host              $host;
            proxy_set_header   X-Real-IP         $remote_addr;
            proxy_set_header   X-Forwarded-For   $proxy_add_x_forwarded_for;
            proxy_set_header   X-Forwarded-Proto $scheme;

            # Timeouts
            proxy_connect_timeout 10s;
            proxy_send_timeout    60s;
            proxy_read_timeout    60s;

            # Buffer settings
            proxy_buffering    on;
            proxy_buffer_size  4k;
        }

        # ── Auth endpoints (stricter rate limit) ──────────────────
        location /api/auth/ {
            limit_req zone=auth_limit burst=5 nodelay;
            proxy_pass http://fastapi_app;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        }

        # ── WebSocket ─────────────────────────────────────────────
        location /ws/ {
            proxy_pass         http://fastapi_app;
            proxy_http_version 1.1;
            proxy_set_header   Upgrade    $http_upgrade;
            proxy_set_header   Connection "upgrade";  # INTERVIEW: WebSocket handshake
            proxy_read_timeout 3600s;   # Long timeout for WS connections
        }

        # ── Static files (served directly by Nginx) ───────────────
        location /static/ {
            alias /var/www/static/;
            expires 1y;                    # Cache for 1 year
            add_header Cache-Control "public, immutable";
        }

        # ── Health check (no logging) ─────────────────────────────
        location /health {
            proxy_pass http://fastapi_app;
            access_log off;               # Don't log health checks
        }
    }
}
"""

# ─────────────────────────────────────────────────────────────────────────────
# SECTION 4: docker-py SDK (programmatic Docker control)
# INTERVIEW: CI/CD, monitoring, auto-scaling scripts
# ─────────────────────────────────────────────────────────────────────────────

def demo_docker_sdk():
    """
    INTERVIEW: docker-py = Python SDK for Docker daemon.
    Use cases: CI/CD automation, health monitoring, dynamic scaling.
    """
    print("\n[Docker SDK Demo]")
    try:
        import docker
        client = docker.from_env()

        # List running containers
        containers = client.containers.list()
        print(f"  Running containers: {len(containers)}")
        for c in containers[:3]:
            print(f"    {c.name}: {c.status} ({c.image.tags})")

        # Pull image
        # image = client.images.pull("python:3.12-slim")
        # print(f"  Pulled: {image.tags}")

        # Run a container
        # result = client.containers.run(
        #     "python:3.12-slim",
        #     command="python -c 'print(\"hello from container\")'",
        #     remove=True,          # auto-remove after exit
        #     detach=False,
        # )
        # print(f"  Output: {result.decode()}")

        # Container stats
        if containers:
            stats = containers[0].stats(stream=False)
            cpu_delta = stats["cpu_stats"]["cpu_usage"]["total_usage"] - \
                        stats["precpu_stats"]["cpu_usage"]["total_usage"]
            print(f"  Container stats available: CPU delta = {cpu_delta}")

    except ImportError:
        print("  docker-py not installed. Run: pip install docker")
    except Exception as e:
        print(f"  Docker not available in this environment: {type(e).__name__}")
        print("  In production: use docker.from_env() to connect to Docker daemon")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 5: Production Best Practices
# ─────────────────────────────────────────────────────────────────────────────

DOCKER_INTERVIEW_QA = [
    ("Docker vs VM?",
     "Docker: shared OS kernel, ms startup, MB size\n"
     "     VM: full OS copy, mins startup, GB size\n"
     "     Docker = process isolation via namespaces+cgroups"),

    ("CMD vs ENTRYPOINT?",
     "ENTRYPOINT = main command (always runs)\n"
     "     CMD = default args (can be overridden)\n"
     "     Best: ENTRYPOINT ['python'] CMD ['app.py']"),

    ("COPY vs ADD?",
     "COPY: simple file copy (preferred)\n"
     "     ADD: can extract .tar, fetch URLs (avoid unless needed)"),

    ("How to reduce image size?",
     "1. Multi-stage builds\n"
     "     2. python:3.12-slim not python:3.12\n"
     "     3. --no-cache-dir in pip install\n"
     "     4. Clean apt cache: rm -rf /var/lib/apt/lists/*\n"
     "     5. .dockerignore: exclude tests/, .git/, .venv/"),

    ("Docker networking types?",
     "bridge (default), host, overlay (swarm), none\n"
     "     Custom bridge: containers resolve by name\n"
     "     host: container shares host network (performance but no isolation)"),

    ("Nginx: worker_processes auto?",
     "auto = number of CPU cores\n"
     "     worker_connections 1024: max connections per worker\n"
     "     Total = worker_processes × worker_connections"),
]


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("DOCKER + NGINX PRACTICAL")
    print("=" * 60)

    print("\n[1] Dockerfile Best Practices:")
    for tip, explanation in DOCKERFILE_OPTIMIZED_TIPS.items():
        print(f"  {tip:<15}: {explanation}")

    print("\n[2] Key docker-compose concepts:")
    compose_tips = {
        "depends_on + condition": "service_healthy waits for healthcheck to pass",
        "Named volumes":          "postgres_data: survives container recreation",
        "Networks":               "backend: internal only, frontend: internet-facing",
        "restart: unless-stopped": "auto-restart on crash but not on manual stop",
    }
    for k, v in compose_tips.items():
        print(f"  {k:<30}: {v}")

    print("\n[3] Nginx Key Directives:")
    nginx_tips = {
        "upstream + least_conn": "Load balance, route to least-busy server",
        "limit_req_zone":        "Rate limiting with shared memory",
        "proxy_set_header":      "Pass real client IP to FastAPI",
        "keepalive 32":          "Connection pool to upstream (reuse TCP)",
        "expires 1y + immutable": "Static files cached forever (use content hash in URL)",
    }
    for k, v in nginx_tips.items():
        print(f"  {k:<30}: {v}")

    demo_docker_sdk()

    print("\n[5] Docker/Nginx Interview Q&A:")
    for q, a in DOCKER_INTERVIEW_QA:
        print(f"\n  Q: {q}")
        print(f"  A: {a}")

    print("\n" + "=" * 60)
    print("FILES TO KNOW:")
    print("  Dockerfile          → multi-stage, non-root, HEALTHCHECK")
    print("  docker-compose.yml  → services, networks, volumes, depends_on")
    print("  nginx.conf          → upstream, proxy_pass, rate limiting, SSL")
    print("  .dockerignore       → .git, .venv, __pycache__, .env")
    print("=" * 60)


if __name__ == "__main__":
    main()
