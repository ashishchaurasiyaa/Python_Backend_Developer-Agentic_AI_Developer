"""
Phase3_DevOps — Django Production Deployment Practical
========================================================
Topics covered:
  1. Production Dockerfile (PostGIS + WeasyPrint + Pillow deps)
  2. docker-compose.yml (Django + PostgreSQL+PostGIS + Redis + Celery + Beat + Nginx)
  3. Django production settings (security, DB pool, S3, CORS, logging)
  4. Celery worker + Beat configuration patterns
  5. ECS Fargate task definitions (web + worker + beat + migrate)
  6. Database migration strategies (expand-contract pattern)
  7. GitHub Actions full CI/CD pipeline with OIDC
  8. Health check + readiness endpoints
  9. Production deployment checklist

Run:
  pip install boto3 docker
  python 05_django_deployment_practical.py
"""

import json
import os
import textwrap

# ─────────────────────────────────────────────────────────────────────────────
# SECTION 1: Production Dockerfile for Django
# INTERVIEW: PostGIS + WeasyPrint need specific system libs
# ─────────────────────────────────────────────────────────────────────────────

DJANGO_DOCKERFILE = """\
# ─── Production Dockerfile for Django (DRF + PostGIS + WeasyPrint) ───
# INTERVIEW: Multi-stage build → image size ~400MB → ~200MB

# ══ Stage 1: Builder ══════════════════════════════════════════════
FROM python:3.12-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \\
    PYTHONUNBUFFERED=1 \\
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# INTERVIEW: System deps needed at BUILD time
# - libpq-dev  → psycopg compilation
# - gdal-bin   → PostGIS Python bindings (django.contrib.gis)
# - libpango   → WeasyPrint PDF generation
# - libcairo   → WeasyPrint canvas rendering
# - libjpeg    → Pillow image processing
RUN apt-get update && apt-get install -y --no-install-recommends \\
    build-essential \\
    libpq-dev \\
    gdal-bin libgdal-dev \\
    libpango-1.0-0 libpangoft2-1.0-0 \\
    libcairo2 libffi-dev shared-mime-info \\
    libjpeg-dev zlib1g-dev \\
    && rm -rf /var/lib/apt/lists/*

# Layer caching: requirements first → if code changes, deps don't rebuild
COPY requirements.txt .
RUN pip install --prefix=/install -r requirements.txt

# ══ Stage 2: Runtime ══════════════════════════════════════════════
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \\
    PYTHONUNBUFFERED=1 \\
    DJANGO_SETTINGS_MODULE=config.settings.production

# INTERVIEW: Runtime deps ONLY (no -dev packages → smaller image)
RUN apt-get update && apt-get install -y --no-install-recommends \\
    libpq5 \\
    gdal-bin \\
    libpango-1.0-0 libpangoft2-1.0-0 libcairo2 \\
    libjpeg62-turbo \\
    curl \\
    && rm -rf /var/lib/apt/lists/*

# INTERVIEW: Non-root user = security best practice (prevents root escape)
RUN addgroup --system app && adduser --system --ingroup app app

WORKDIR /app
COPY --from=builder /install /usr/local
COPY --chown=app:app . .

# INTERVIEW: collectstatic at BUILD time → fast container start
RUN python manage.py collectstatic --noinput --clear

USER app
EXPOSE 8000

# INTERVIEW: HEALTHCHECK = Docker/ECS knows when container is ready
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \\
    CMD curl -f http://localhost:8000/health/ || exit 1

# INTERVIEW: Gunicorn workers formula = (2 × vCPU) + 1
# --max-requests prevents memory leaks (worker recycled after N requests)
# --max-requests-jitter prevents thundering herd (random restart times)
CMD ["gunicorn", "config.wsgi:application", \\
     "--bind", "0.0.0.0:8000", \\
     "--workers", "4", \\
     "--worker-class", "gthread", \\
     "--threads", "2", \\
     "--max-requests", "1000", \\
     "--max-requests-jitter", "50", \\
     "--timeout", "120", \\
     "--graceful-timeout", "30", \\
     "--keep-alive", "5", \\
     "--access-logfile", "-", \\
     "--error-logfile", "-"]
"""

# ─────────────────────────────────────────────────────────────────────────────
# SECTION 2: docker-compose.yml — Full Django Stack
# INTERVIEW: 6 services — web + worker + beat + postgres + redis + nginx
# ─────────────────────────────────────────────────────────────────────────────

DJANGO_DOCKER_COMPOSE = """\
# docker-compose.yml — Django + DRF + PostGIS + Celery production-style
# INTERVIEW: Beat must be SINGLE instance (no replicas) to avoid duplicate tasks

version: "3.9"

services:

  # ══ Web Layer ════════════════════════════════════════════════════
  django:
    build: .
    ports:
      - "8000:8000"
    environment:
      DATABASE_URL: postgis://django:django@postgres:5432/myapp
      REDIS_URL: redis://redis:6379/0
      CELERY_BROKER_URL: redis://redis:6379/1
      DJANGO_SETTINGS_MODULE: config.settings.production
      SECRET_KEY: ${SECRET_KEY}
      ALLOWED_HOSTS: localhost,127.0.0.1
      AWS_ACCESS_KEY_ID: ${AWS_ACCESS_KEY_ID}
      AWS_SECRET_ACCESS_KEY: ${AWS_SECRET_ACCESS_KEY}
      AWS_STORAGE_BUCKET_NAME: ${S3_BUCKET}
    depends_on:
      postgres:
        condition: service_healthy   # INTERVIEW: wait for healthcheck pass
      redis:
        condition: service_started
    restart: unless-stopped

  # ══ Background Layer ════════════════════════════════════════════
  celery-worker:
    build: .
    # INTERVIEW: -Q default,high_priority → consume from multiple queues
    command: celery -A config worker -l info --concurrency=4 -Q default,high_priority
    environment:
      DATABASE_URL: postgis://django:django@postgres:5432/myapp
      REDIS_URL: redis://redis:6379/0
      CELERY_BROKER_URL: redis://redis:6379/1
    depends_on:
      - postgres
      - redis
    restart: unless-stopped
    # INTERVIEW: Scale workers as needed
    deploy:
      replicas: 2

  celery-beat:
    build: .
    # ⚠️ CRITICAL: Beat must be SINGLE instance only
    # If 2+ instances → duplicate scheduled tasks
    # DatabaseScheduler stores schedule in Django DB (django-celery-beat)
    command: celery -A config beat -l info --scheduler django_celery_beat.schedulers:DatabaseScheduler
    environment:
      DATABASE_URL: postgis://django:django@postgres:5432/myapp
      CELERY_BROKER_URL: redis://redis:6379/1
    depends_on:
      - postgres
      - redis
    restart: unless-stopped
    # ⚠️ NO replicas key here — single instance only

  flower:
    # INTERVIEW: Flower = Celery monitoring UI (dev/staging only)
    build: .
    command: celery -A config flower --port=5555
    ports:
      - "5555:5555"
    depends_on:
      - redis

  # ══ Data Layer ═══════════════════════════════════════════════════
  postgres:
    # ⭐ INTERVIEW: postgis/postgis image (NOT regular postgres)
    # Regular postgres → PostGIS extension installed manually
    # postgis/postgis → PostGIS pre-installed, just CREATE EXTENSION
    image: postgis/postgis:15-3.4
    environment:
      POSTGRES_USER: django
      POSTGRES_PASSWORD: django
      POSTGRES_DB: myapp
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./scripts/init-postgis.sql:/docker-entrypoint-initdb.d/init.sql:ro
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U django -d myapp"]
      interval: 5s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    volumes:
      - redis_data:/data
    # INTERVIEW: LRU eviction when memory full (cache use case)
    command: redis-server --maxmemory 256mb --maxmemory-policy allkeys-lru

  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx/nginx.conf:/etc/nginx/conf.d/default.conf:ro
      - ./nginx/certs:/etc/nginx/certs:ro
    depends_on:
      - django
    restart: unless-stopped

volumes:
  postgres_data:
  redis_data:
"""

POSTGIS_INIT_SQL = """\
-- scripts/init-postgis.sql — Auto-run on first PostgreSQL start
-- INTERVIEW: PostGIS extension required for django.contrib.gis (spatial queries)

CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS postgis_topology;
CREATE EXTENSION IF NOT EXISTS pg_trgm;             -- Trigram fuzzy search
CREATE EXTENSION IF NOT EXISTS pg_stat_statements;  -- Query performance tracking
"""

# ─────────────────────────────────────────────────────────────────────────────
# SECTION 3: Django Production Settings
# INTERVIEW: Security + Performance + Observability
# ─────────────────────────────────────────────────────────────────────────────

DJANGO_PRODUCTION_SETTINGS = """\
# config/settings/production.py
from .base import *
from decouple import config
from datetime import timedelta
import structlog
import sentry_sdk
from sentry_sdk.integrations.django import DjangoIntegration
from sentry_sdk.integrations.celery import CeleryIntegration

# ══ Security ══════════════════════════════════════════════════════
DEBUG = False
SECRET_KEY = config("SECRET_KEY")
ALLOWED_HOSTS = config("ALLOWED_HOSTS", default="").split(",")

# INTERVIEW: Behind ALB → HTTPS terminated at LB → app sees X-Forwarded-Proto
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 31536000           # 1 year HSTS
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"

# ══ Database with psycopg3 connection pooling ════════════════════
DATABASES = {
    "default": {
        "ENGINE": "django.contrib.gis.db.backends.postgis",  # ⭐ PostGIS backend
        "NAME": config("DB_NAME"),
        "USER": config("DB_USER"),
        "PASSWORD": config("DB_PASSWORD"),
        "HOST": config("DB_HOST"),
        "PORT": config("DB_PORT", default="5432"),
        "CONN_MAX_AGE": 600,             # Reuse connections for 10 min
        "CONN_HEALTH_CHECKS": True,      # Detect dead connections
        "OPTIONS": {
            "pool": {                    # psycopg3 native pooling
                "min_size": 4,
                "max_size": 20,
                "timeout": 10,
            }
        }
    }
}

# ══ Redis Cache ═══════════════════════════════════════════════════
CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": config("REDIS_URL"),
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
            "CONNECTION_POOL_KWARGS": {"max_connections": 50},
        },
        "KEY_PREFIX": "myapp:prod",
    }
}

SESSION_ENGINE = "django.contrib.sessions.backends.cache"

# ══ Celery ════════════════════════════════════════════════════════
CELERY_BROKER_URL = config("CELERY_BROKER_URL")
CELERY_RESULT_BACKEND = config("REDIS_URL")
CELERY_TASK_SERIALIZER = "json"
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TIMEZONE = "Asia/Kolkata"
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = 30 * 60         # 30 min hard limit
CELERY_TASK_SOFT_TIME_LIMIT = 25 * 60    # 25 min soft (raises warning)
CELERY_BEAT_SCHEDULER = "django_celery_beat.schedulers:DatabaseScheduler"

# INTERVIEW: Route heavy tasks to dedicated queue
CELERY_TASK_ROUTES = {
    "myapp.tasks.generate_pdf": {"queue": "high_priority"},  # WeasyPrint heavy
    "myapp.tasks.send_email": {"queue": "default"},
    "myapp.tasks.sync_inventory": {"queue": "background"},
}

# ══ S3 Storage ════════════════════════════════════════════════════
DEFAULT_FILE_STORAGE = "storages.backends.s3boto3.S3Boto3Storage"
STATICFILES_STORAGE = "storages.backends.s3boto3.S3StaticStorage"
AWS_STORAGE_BUCKET_NAME = config("AWS_STORAGE_BUCKET_NAME")
AWS_S3_REGION_NAME = config("AWS_S3_REGION_NAME", default="ap-south-1")
AWS_S3_OBJECT_PARAMETERS = {"CacheControl": "max-age=86400"}
AWS_QUERYSTRING_AUTH = False              # Public-read URLs (no signed query strings)
AWS_S3_FILE_OVERWRITE = False

# CloudFront CDN URLs
STATIC_URL = f"https://{config('CLOUDFRONT_DOMAIN')}/static/"
MEDIA_URL = f"https://{config('CLOUDFRONT_DOMAIN')}/media/"

# ══ CORS (React frontend) ═════════════════════════════════════════
CORS_ALLOWED_ORIGINS = config("CORS_ALLOWED_ORIGINS").split(",")
CORS_ALLOW_CREDENTIALS = True

# ══ SimpleJWT ═════════════════════════════════════════════════════
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=15),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,     # Prevents refresh token reuse
    "ALGORITHM": "HS256",
    "SIGNING_KEY": config("JWT_SIGNING_KEY", default=SECRET_KEY),
}

# ══ Structured JSON Logging ═══════════════════════════════════════
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "json": {
            "()": structlog.stdlib.ProcessorFormatter,
            "processor": structlog.processors.JSONRenderer(),
        },
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "json"},
    },
    "root": {"handlers": ["console"], "level": "INFO"},
}

structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.dict_tracebacks,
        structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.stdlib.BoundLogger,
    logger_factory=structlog.stdlib.LoggerFactory(),
)

# ══ Sentry Error Tracking ═════════════════════════════════════════
sentry_sdk.init(
    dsn=config("SENTRY_DSN"),
    integrations=[DjangoIntegration(), CeleryIntegration()],
    traces_sample_rate=0.1,               # 10% of requests traced
    send_default_pii=False,               # GDPR compliance
    environment="production",
    release=config("APP_VERSION", default="unknown"),
)
"""

# ─────────────────────────────────────────────────────────────────────────────
# SECTION 4: Health Check + Readiness Endpoints
# INTERVIEW: K8s/ECS use these for traffic routing decisions
# ─────────────────────────────────────────────────────────────────────────────

DJANGO_HEALTH_VIEWS = """\
# myapp/views/health.py
from django.http import JsonResponse
from django.db import connection
from django_redis import get_redis_connection
from datetime import datetime
import structlog

log = structlog.get_logger()

def health_check(request):
    \"\"\"
    Liveness probe — basic alive check.
    INTERVIEW: K8s livenessProbe failure → pod restart
    \"\"\"
    return JsonResponse({
        "status": "ok",
        "timestamp": datetime.utcnow().isoformat()
    })


def readiness_check(request):
    \"\"\"
    Readiness probe — deep check (DB + Redis).
    INTERVIEW: K8s readinessProbe failure → traffic stopped (no restart)
    Return 503 if dependencies down → ALB stops routing requests.
    \"\"\"
    checks = {}
    all_ok = True

    # Database check
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
        checks["database"] = "ok"
    except Exception as e:
        checks["database"] = f"error: {str(e)[:100]}"
        all_ok = False
        log.error("readiness_db_failed", error=str(e))

    # Redis check
    try:
        redis_conn = get_redis_connection("default")
        redis_conn.ping()
        checks["redis"] = "ok"
    except Exception as e:
        checks["redis"] = f"error: {str(e)[:100]}"
        all_ok = False
        log.error("readiness_redis_failed", error=str(e))

    return JsonResponse(
        {
            "status": "ready" if all_ok else "not_ready",
            "checks": checks,
            "timestamp": datetime.utcnow().isoformat(),
        },
        status=200 if all_ok else 503    # ⭐ Critical: 503 stops traffic
    )


# myapp/urls.py
# from django.urls import path
# from myapp.views.health import health_check, readiness_check
# urlpatterns = [
#     path("health/", health_check),         # for liveness (ECS, ALB)
#     path("health/ready/", readiness_check), # for readiness
# ]
"""

# ─────────────────────────────────────────────────────────────────────────────
# SECTION 5: ECS Task Definitions
# INTERVIEW: 3 separate tasks for web, worker, beat
# ─────────────────────────────────────────────────────────────────────────────

ECS_TASK_DEFINITIONS = {
    "django_web": {
        "family": "myapp-django",
        "networkMode": "awsvpc",
        "requiresCompatibilities": ["FARGATE"],
        "cpu": "1024",      # 1 vCPU
        "memory": "2048",   # 2 GB
        "executionRoleArn": "arn:aws:iam::ACCOUNT:role/ecsTaskExecutionRole",
        "taskRoleArn": "arn:aws:iam::ACCOUNT:role/myapp-task-role",
        "containerDefinitions": [{
            "name": "django",
            "image": "ECR_URL/myapp-django:latest",
            "portMappings": [{"containerPort": 8000, "protocol": "tcp"}],
            "environment": [
                {"name": "DJANGO_SETTINGS_MODULE", "value": "config.settings.production"},
                {"name": "DB_HOST", "value": "myapp-postgres.xxx.rds.amazonaws.com"},
                {"name": "DB_NAME", "value": "myapp"},
                {"name": "DB_USER", "value": "django"},
                {"name": "REDIS_URL", "value": "redis://myapp-redis.xxx.cache.amazonaws.com:6379/0"},
                {"name": "ALLOWED_HOSTS", "value": "api.yourapp.com"},
            ],
            "secrets": [
                # INTERVIEW: Inject from AWS Secrets Manager (no plaintext)
                {"name": "SECRET_KEY",
                 "valueFrom": "arn:aws:secretsmanager:..:secret:myapp/prod/secret-key"},
                {"name": "DB_PASSWORD",
                 "valueFrom": "arn:aws:secretsmanager:..:secret:myapp/prod/db-password"},
            ],
            "logConfiguration": {
                "logDriver": "awslogs",
                "options": {
                    "awslogs-group": "/ecs/myapp-django",
                    "awslogs-region": "ap-south-1",
                    "awslogs-stream-prefix": "django",
                }
            },
            "healthCheck": {
                "command": ["CMD-SHELL", "curl -f http://localhost:8000/health/ || exit 1"],
                "interval": 30, "timeout": 5, "retries": 3, "startPeriod": 30,
            },
        }],
    },

    "celery_worker": {
        "family": "myapp-celery-worker",
        "cpu": "512", "memory": "1024",
        "containerDefinitions": [{
            "name": "worker",
            "image": "ECR_URL/myapp-django:latest",
            # INTERVIEW: Override Dockerfile CMD with Celery command
            "command": ["celery", "-A", "config", "worker", "-l", "info",
                       "--concurrency=4", "-Q", "default,high_priority"],
            # ... environment, secrets same as web
        }],
    },

    "celery_beat": {
        "family": "myapp-celery-beat",
        "cpu": "256", "memory": "512",  # Lightweight
        "containerDefinitions": [{
            "name": "beat",
            "image": "ECR_URL/myapp-django:latest",
            "command": ["celery", "-A", "config", "beat", "-l", "info",
                       "--scheduler", "django_celery_beat.schedulers:DatabaseScheduler"],
        }],
    },

    "migrate": {
        # ⭐ INTERVIEW: One-off task — runs before service update
        # If migration fails → don't deploy new service version
        "family": "myapp-django-migrate",
        "cpu": "512", "memory": "1024",
        "containerDefinitions": [{
            "name": "migrate",
            "image": "ECR_URL/myapp-django:latest",
            "command": ["python", "manage.py", "migrate", "--noinput"],
        }],
    },
}

# ─────────────────────────────────────────────────────────────────────────────
# SECTION 6: GitHub Actions CI/CD Pipeline
# INTERVIEW: OIDC = no long-lived AWS keys (modern security)
# ─────────────────────────────────────────────────────────────────────────────

GITHUB_ACTIONS_DEPLOY = """\
# .github/workflows/deploy.yml
name: Deploy Django to ECS

on:
  push:
    branches: [main]
    paths: ['backend/**']

env:
  AWS_REGION: ap-south-1
  ECR_REPOSITORY: myapp-django
  ECS_CLUSTER: myapp-cluster-prod

jobs:
  # ── Stage 1: Tests ───────────────────────────────────────────────
  test:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgis/postgis:15-3.4    # ⭐ PostGIS image for tests
        env:
          POSTGRES_USER: django
          POSTGRES_PASSWORD: django
          POSTGRES_DB: testdb
        ports: ["5432:5432"]
        options: --health-cmd "pg_isready -U django" --health-interval 5s
      redis:
        image: redis:7
        ports: ["6379:6379"]
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: {python-version: "3.12", cache: "pip"}
      - run: |
          cd backend
          pip install -r requirements.txt
          ruff check .
          mypy .
          python manage.py check --deploy
          python manage.py test
        env:
          DATABASE_URL: postgis://django:django@localhost:5432/testdb
          REDIS_URL: redis://localhost:6379/0
          SECRET_KEY: test-key-not-for-prod

  # ── Stage 2: Build + Push to ECR ────────────────────────────────
  build-push:
    needs: test
    runs-on: ubuntu-latest
    permissions:
      id-token: write        # ⭐ OIDC — no long-lived AWS keys
      contents: read
    outputs:
      image-uri: ${{ steps.build.outputs.image-uri }}
    steps:
      - uses: actions/checkout@v4

      # INTERVIEW: OIDC assume-role (no AWS_ACCESS_KEY in secrets!)
      - uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: arn:aws:iam::ACCOUNT:role/github-actions-deploy
          aws-region: ${{ env.AWS_REGION }}

      - uses: aws-actions/amazon-ecr-login@v2
        id: login-ecr

      - name: Build & push image
        id: build
        run: |
          IMAGE_URI=${{ steps.login-ecr.outputs.registry }}/${{ env.ECR_REPOSITORY }}:${{ github.sha }}
          docker build -t $IMAGE_URI ./backend
          docker push $IMAGE_URI
          docker tag $IMAGE_URI ${{ steps.login-ecr.outputs.registry }}/${{ env.ECR_REPOSITORY }}:latest
          docker push ${{ steps.login-ecr.outputs.registry }}/${{ env.ECR_REPOSITORY }}:latest
          echo "image-uri=$IMAGE_URI" >> $GITHUB_OUTPUT

  # ── Stage 3: Run Migrations (one-off task) ───────────────────────
  migrate:
    needs: build-push
    runs-on: ubuntu-latest
    permissions:
      id-token: write
      contents: read
    steps:
      - uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: arn:aws:iam::ACCOUNT:role/github-actions-deploy
          aws-region: ${{ env.AWS_REGION }}

      - name: Run migrations
        run: |
          # INTERVIEW: Run migration as one-off task, WAIT for completion
          TASK_ARN=$(aws ecs run-task --cluster $ECS_CLUSTER \\
            --task-definition myapp-django-migrate \\
            --launch-type FARGATE \\
            --network-configuration 'awsvpcConfiguration={subnets=[subnet-xxx],securityGroups=[sg-xxx]}' \\
            --query 'tasks[0].taskArn' --output text)

          aws ecs wait tasks-stopped --cluster $ECS_CLUSTER --tasks $TASK_ARN

          EXIT_CODE=$(aws ecs describe-tasks --cluster $ECS_CLUSTER --tasks $TASK_ARN \\
            --query 'tasks[0].containers[0].exitCode' --output text)

          # ⭐ Migration failure → fail entire pipeline (don't deploy)
          [ "$EXIT_CODE" = "0" ] || (echo "Migration failed!" && exit 1)

  # ── Stage 4: Rolling Deploy ─────────────────────────────────────
  deploy:
    needs: migrate
    runs-on: ubuntu-latest
    permissions:
      id-token: write
      contents: read
    steps:
      - uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: arn:aws:iam::ACCOUNT:role/github-actions-deploy
          aws-region: ${{ env.AWS_REGION }}

      - name: Update ECS services
        run: |
          # INTERVIEW: --force-new-deployment = pick up :latest tag
          for svc in django-web celery-worker celery-beat; do
            aws ecs update-service --cluster $ECS_CLUSTER --service $svc --force-new-deployment
          done

          # Wait for all to stabilize (new tasks healthy, old terminated)
          aws ecs wait services-stable --cluster $ECS_CLUSTER \\
            --services django-web celery-worker celery-beat

      - name: Notify Slack
        if: always()
        run: |
          curl -X POST -H 'Content-type: application/json' \\
            --data "{\\"text\\":\\"Deploy ${{ job.status }}: ${{ github.sha }}\\"}" \\
            ${{ secrets.SLACK_WEBHOOK }}
"""

# ─────────────────────────────────────────────────────────────────────────────
# SECTION 7: Database Migration Patterns
# INTERVIEW: Zero-downtime schema changes (expand-contract)
# ─────────────────────────────────────────────────────────────────────────────

MIGRATION_PATTERNS = """\
# myapp/migrations/0042_add_tracking_id.py
# ════════════════════════════════════════════════════════════════════
# Pattern 1: Add nullable column (SAFE — backward compatible)
# ════════════════════════════════════════════════════════════════════

from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [("myapp", "0041_previous")]

    operations = [
        migrations.AddField(
            "order",
            "tracking_id",
            models.CharField(max_length=50, null=True, blank=True),
        ),
    ]
    # ✅ Safe: Old code ignores new column, new code uses it


# ════════════════════════════════════════════════════════════════════
# Pattern 2: Add index on large table (use CONCURRENTLY)
# INTERVIEW: CREATE INDEX locks table → CREATE INDEX CONCURRENTLY doesn't
# ════════════════════════════════════════════════════════════════════

class Migration(migrations.Migration):
    atomic = False  # ⚠️ CONCURRENTLY can't run in transaction
    dependencies = [("myapp", "0042_previous")]

    operations = [
        migrations.RunSQL(
            sql="CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_orders_status ON orders(status);",
            reverse_sql="DROP INDEX IF EXISTS idx_orders_status;",
        ),
    ]


# ════════════════════════════════════════════════════════════════════
# Pattern 3: Rename column safely (3-step expand-contract)
# ════════════════════════════════════════════════════════════════════

# ──── Deploy 1: Add new column, dual-write, read from OLD ────
class Migration_v1(migrations.Migration):
    operations = [
        migrations.AddField("order", "customer_email_v2",
                           models.EmailField(null=True, blank=True)),
    ]

# In code (Release v1):
class Order(models.Model):
    customer_email = models.EmailField()           # OLD field
    customer_email_v2 = models.EmailField(null=True)  # NEW field

    def save(self, *args, **kwargs):
        # Dual-write — keep both in sync
        if self.customer_email and not self.customer_email_v2:
            self.customer_email_v2 = self.customer_email
        super().save(*args, **kwargs)


# ──── Deploy 2: Backfill via Celery task ────
@celery_app.task
def backfill_customer_email():
    from myapp.models import Order
    qs = Order.objects.filter(customer_email_v2__isnull=True)
    for batch in chunked(qs.iterator(), 1000):
        for order in batch:
            order.customer_email_v2 = order.customer_email
            order.save(update_fields=["customer_email_v2"])


# ──── Deploy 3: Read from NEW, drop OLD ────
# In code (Release v3): Use customer_email_v2 everywhere
class Migration_v3(migrations.Migration):
    operations = [
        migrations.RemoveField("order", "customer_email"),
    ]
"""

# ─────────────────────────────────────────────────────────────────────────────
# SECTION 8: Demo Function — Boto3 ECS Deploy
# ─────────────────────────────────────────────────────────────────────────────

def demo_ecs_deploy_workflow():
    """
    INTERVIEW: Programmatic ECS deploy workflow with boto3.
    Real use: deployment automation scripts beyond GitHub Actions.
    """
    print("\n[ECS Deploy Workflow Demo]")
    try:
        import boto3
        ecs = boto3.client("ecs", region_name="ap-south-1")

        # Real workflow (commented to avoid actual deploy):
        # 1. Run migration task
        # response = ecs.run_task(
        #     cluster="myapp-cluster-prod",
        #     taskDefinition="myapp-django-migrate",
        #     launchType="FARGATE",
        #     networkConfiguration={
        #         "awsvpcConfiguration": {
        #             "subnets": ["subnet-xxx"],
        #             "securityGroups": ["sg-xxx"],
        #         }
        #     },
        # )
        # task_arn = response["tasks"][0]["taskArn"]
        #
        # 2. Wait for migration to complete
        # waiter = ecs.get_waiter("tasks_stopped")
        # waiter.wait(cluster="myapp-cluster-prod", tasks=[task_arn])
        #
        # 3. Check exit code
        # task = ecs.describe_tasks(cluster="myapp-cluster-prod", tasks=[task_arn])
        # exit_code = task["tasks"][0]["containers"][0].get("exitCode", -1)
        # if exit_code != 0:
        #     raise Exception(f"Migration failed with code {exit_code}")
        #
        # 4. Force new deployment
        # ecs.update_service(
        #     cluster="myapp-cluster-prod",
        #     service="django-web",
        #     forceNewDeployment=True,
        # )

        print("  Workflow steps:")
        print("  1. boto3.client('ecs').run_task(migrate_task_def)")
        print("  2. waiter.wait(tasks_stopped)")
        print("  3. check exit_code == 0")
        print("  4. ecs.update_service(forceNewDeployment=True)")
        print("  5. waiter.wait(services_stable)")
    except ImportError:
        print("  boto3 not installed. Run: pip install boto3")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 9: Production Checklist + Common Issues
# ─────────────────────────────────────────────────────────────────────────────

PRODUCTION_CHECKLIST = {
    "Security": [
        "DEBUG = False",
        "SECRET_KEY from AWS Secrets Manager",
        "ALLOWED_HOSTS configured",
        "HTTPS enforced (SECURE_SSL_REDIRECT)",
        "CORS restrictive (exact origins)",
        "JWT short expiry + refresh rotation",
    ],
    "Performance": [
        "psycopg3 connection pool (min=4, max=20)",
        "Redis cache configured",
        "N+1 fixes (select_related, prefetch_related)",
        "Gunicorn workers = (2 × CPU) + 1",
        "Static files on CloudFront",
    ],
    "Reliability": [
        "/health/ + /health/ready/ endpoints",
        "RDS Multi-AZ enabled",
        "Auto-scaling configured (2-10 tasks)",
        "RDS PITR backups (7 days)",
        "Celery beat single instance only",
    ],
    "Observability": [
        "structlog JSON logs",
        "Request ID in all logs",
        "Sentry integration",
        "CloudWatch alarms (5xx, CPU, queue depth)",
    ],
    "CI/CD": [
        "Tests block PR merge",
        "OIDC for AWS (no long-lived keys)",
        "Migrations run BEFORE service update",
        "Rollback script ready",
    ],
}

COMMON_ISSUES_FIXES = [
    ("502 Bad Gateway", "Gunicorn worker timeout", "--timeout 120, check slow queries"),
    ("PostGIS missing", "Wrong Postgres image", "Use postgis/postgis:15-3.4"),
    ("WeasyPrint crash", "Missing libpango", "Install libpango-1.0-0 in Dockerfile"),
    ("Celery duplicate task", "Multiple Beat instances", "desired_count=1 for beat service"),
    ("Memory leak", "Workers not recycling", "Gunicorn --max-requests 1000"),
    ("Slow API", "N+1 queries", "select_related, prefetch_related, debug toolbar"),
    ("S3 upload 403", "IAM permissions", "Task role: s3:PutObject on bucket ARN"),
    ("JWT refresh fail", "Token blacklist not configured", "BLACKLIST_AFTER_ROTATION=True"),
]

# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

DJANGO_DEPLOY_QA = [
    ("Why postgis/postgis image instead of postgres?",
     "django.contrib.gis needs PostGIS extension. postgis/postgis pre-installs it.\n"
     "     Regular postgres → manually run CREATE EXTENSION postgis after each deploy."),

    ("Why Gunicorn over Uvicorn for Django?",
     "Django is WSGI (sync). Gunicorn = WSGI server.\n"
     "     Uvicorn = ASGI server (FastAPI). Django ASGI exists but limited."),

    ("Why Celery Beat must be single instance?",
     "If 2 Beat instances → both fire scheduled tasks → duplicate execution.\n"
     "     Solutions: 1) desired_count=1, 2) RedBeat (Redis lock), 3) celery-singleton."),

    ("Why collectstatic at build time?",
     "Faster container start (no startup delay).\n"
     "     Image immutable (same files across all replicas).\n"
     "     S3 sync as separate CI step is alternative pattern."),

    ("How to handle migrations safely?",
     "1. Backward-compatible migrations (additive only)\n"
     "     2. Run as one-off ECS task BEFORE service update\n"
     "     3. Use CONCURRENTLY for indexes on large tables\n"
     "     4. Expand-contract pattern for renames"),

    ("Why JWT BLACKLIST_AFTER_ROTATION?",
     "Refresh token rotation → old refresh token blacklisted\n"
     "     Prevents replay attack if attacker steals old refresh token."),
]


def main():
    print("=" * 60)
    print("DJANGO PRODUCTION DEPLOYMENT PRACTICAL")
    print("=" * 60)

    print("\n[1] Production Dockerfile — Critical System Deps:")
    deps = {
        "libpq-dev / libpq5":   "psycopg PostgreSQL driver",
        "gdal-bin":             "django.contrib.gis (PostGIS)",
        "libpango / libcairo":  "WeasyPrint PDF generation",
        "libjpeg":              "Pillow image processing",
    }
    for dep, why in deps.items():
        print(f"  {dep:<22}: {why}")

    print("\n[2] docker-compose.yml — 6 Services:")
    services = {
        "django":        "Gunicorn web server (ports 8000)",
        "celery-worker": "Async task processor (scale freely)",
        "celery-beat":   "Scheduler (SINGLE instance only!)",
        "postgres":      "postgis/postgis:15-3.4 (NOT postgres image)",
        "redis":         "Cache + Celery broker",
        "nginx":         "Reverse proxy + SSL termination",
    }
    for svc, role in services.items():
        print(f"  {svc:<15}: {role}")

    print("\n[3] Production Settings Highlights:")
    settings_highlights = {
        "DEBUG":                 "False (always)",
        "SECURE_PROXY_SSL_HEADER": "Trust X-Forwarded-Proto from ALB",
        "CONN_MAX_AGE = 600":    "Reuse DB connections 10 min",
        "psycopg3 pool":         "min=4, max=20 connections",
        "BLACKLIST_AFTER_ROTATION": "Refresh token security",
        "structlog JSON":        "Searchable logs in CloudWatch",
    }
    for k, v in settings_highlights.items():
        print(f"  {k:<28}: {v}")

    print("\n[4] ECS Deployment — Required Tasks:")
    print("  myapp-django         → web service (count: 2-10, auto-scale)")
    print("  myapp-celery-worker  → background tasks (count: 1-N)")
    print("  myapp-celery-beat    → scheduler (count: 1 ONLY)")
    print("  myapp-django-migrate → one-off (run before deploy)")

    demo_ecs_deploy_workflow()

    print("\n[5] Production Checklist Summary:")
    for category, items in PRODUCTION_CHECKLIST.items():
        print(f"\n  [{category}]")
        for item in items:
            print(f"    ✓ {item}")

    print("\n[6] Common Issues in Production:")
    print(f"  {'Issue':<25} {'Cause':<35} {'Fix'}")
    print(f"  {'-'*25} {'-'*35} {'-'*20}")
    for issue, cause, fix in COMMON_ISSUES_FIXES:
        print(f"  {issue:<25} {cause:<35} {fix}")

    print("\n[7] Django Deployment Interview Q&A:")
    for q, a in DJANGO_DEPLOY_QA:
        print(f"\n  Q: {q}")
        print(f"  A: {a}")

    print("\n" + "=" * 60)
    print("FILES TO KNOW:")
    print("  Dockerfile                        → multi-stage + non-root + healthcheck")
    print("  docker-compose.yml                → 6 services (web/worker/beat/db/redis/nginx)")
    print("  config/settings/production.py     → security + pooling + S3 + structlog")
    print("  myapp/views/health.py             → /health/ + /health/ready/")
    print("  .github/workflows/deploy.yml      → OIDC + test + migrate + deploy")
    print("  Terraform: ECS tasks (web/worker/beat/migrate) + RDS + Redis")
    print("=" * 60)


if __name__ == "__main__":
    main()
