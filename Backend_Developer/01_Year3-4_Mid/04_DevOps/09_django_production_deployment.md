# Django Production Deployment — Full Stack (DRF + PostgreSQL + PostGIS + Celery + Redis + S3)

## Quick Concepts
- **WSGI server** = Django ke liye production server (Gunicorn / uWSGI) — `runserver` production ke liye NAHI
- **Reverse proxy** = Nginx Gunicorn ke aage — SSL, static files, rate limiting
- **Worker process** = Gunicorn ke multiple workers parallel requests handle karte hain
- **Celery** = async tasks (PDF generation, email, sync jobs) — web request ko block nahi karta
- **Celery Beat** = scheduled/periodic tasks (cron jaisa) — sirf 1 instance run karo
- **collectstatic** = saari static files ek folder mein collect karta hai (S3/CDN ke liye)
- **migrations** = database schema changes — deployment se PEHLE run karo, application start hone se PEHLE

---

## Stack Reference (Tumhara Actual Project)

```
Backend:
- Python 3.12 + Django 5.1.3 + DRF 3.15.2
- PostgreSQL 15 + PostGIS (spatial queries)
- psycopg 3.2.3 (with connection pooling)
- Redis 5.4 (cache + Celery broker)
- Celery 5.4 + django-celery-beat
- WeasyPrint (PDF) + Pillow + openpyxl
- Gunicorn (WSGI server)
- django-storages + boto3 (S3)
- SimpleJWT (auth)
- structlog (JSON logging)

Frontend:
- React 18 + TypeScript + Vite
- Ant Design + TanStack Query + Zustand
- Static build → S3 + CloudFront
```

---

## Interview Questions & Answers

### Q1: Django production deployment ka complete architecture explain karo?

**Answer:**
Django production deployment mein 3 layer hote hain — **Web Layer**, **Background Layer**, aur **Data Layer**:

```
┌─────────────────────────────────────────────────────────────┐
│                    INTERNET                                  │
└────────────────────┬────────────────────────────────────────┘
                     │ HTTPS (443)
                ┌────▼────┐
                │ Route53 │  api.yourapp.com
                └────┬────┘
                     │
                ┌────▼────┐
                │   ALB   │  ← SSL termination (ACM cert)
                │  (HTTPS)│
                └────┬────┘
                     │
   ┌─────────────────┼─────────────────┐
   │ WEB LAYER       │                 │
   │ ┌───────────────▼─────┐ ┌─────────▼──────────┐
   │ │ ECS Task: Django    │ │ ECS Task: Django   │
   │ │ (Gunicorn workers)  │ │ (Gunicorn workers) │
   │ │ Port 8000           │ │ Port 8000          │
   │ └─────────────────────┘ └────────────────────┘
   │                                                │
   └────────────────────────────────────────────────┘
                     │
   ┌─────────────────┼─────────────────┐
   │ BACKGROUND      │                 │
   │ ┌───────────────▼─────┐ ┌─────────▼──────────┐
   │ │ ECS Task:           │ │ ECS Task:          │
   │ │ Celery Worker(s)    │ │ Celery Beat (×1)   │
   │ │ (async jobs)        │ │ (scheduler)        │
   │ └─────────────────────┘ └────────────────────┘
   │                                                │
   └────────────────────────────────────────────────┘
                     │
   ┌─────────────────┼─────────────────┬───────────┐
   │ DATA LAYER      │                 │           │
   │ ┌───────────────▼──┐ ┌────────────▼──┐ ┌─────▼──┐
   │ │ RDS PostgreSQL   │ │ ElastiCache   │ │   S3   │
   │ │ + PostGIS        │ │ Redis         │ │ Bucket │
   │ │ (Multi-AZ)       │ │ (cache+broker)│ │uploads │
   │ └──────────────────┘ └───────────────┘ └────────┘
   │
   │ Frontend (separate):
   │ React → S3 Bucket → CloudFront CDN → app.yourapp.com
   └────────────────────────────────────────────────────
```

**Flow:**
1. User browser → CloudFront (React SPA serve)
2. React `fetch("https://api.yourapp.com")` → Route53 → ALB → ECS Django Task
3. Django request handle karta hai → PostgreSQL query / Redis cache check
4. Heavy task (PDF, email) → Celery queue mein push → Worker async process
5. Files upload → directly S3 mein (django-storages)

---

### Q2: Tumhara Dockerfile production-ready kaise banaoge? PostGIS aur WeasyPrint ke liye special dependencies kya hain?

**Answer:**
Production Dockerfile mein **multi-stage build** + **non-root user** + **system dependencies** important hote hain. Tumhare stack ke liye:
- **PostgreSQL/PostGIS** → `libpq-dev`, `gdal-bin`
- **WeasyPrint** → `libpango`, `libcairo`, `libffi-dev`
- **Pillow** → `libjpeg`, `zlib1g-dev`

```dockerfile
# ============================================================
# Stage 1: Builder — heavy build tools yahan
# ============================================================
FROM python:3.12-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# System dependencies for psycopg, PostGIS, WeasyPrint, Pillow
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    gdal-bin libgdal-dev \
    libpango-1.0-0 libpangoft2-1.0-0 \
    libcairo2 libffi-dev shared-mime-info \
    libjpeg-dev zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --prefix=/install -r requirements.txt

# ============================================================
# Stage 2: Runtime — sirf runtime deps + app code
# ============================================================
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DJANGO_SETTINGS_MODULE=config.settings.production

# Runtime deps only (no build tools — image size kam)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    gdal-bin \
    libpango-1.0-0 libpangoft2-1.0-0 libcairo2 \
    libjpeg62-turbo \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Non-root user (security best practice)
RUN addgroup --system app && adduser --system --ingroup app app

WORKDIR /app
COPY --from=builder /install /usr/local
COPY --chown=app:app . .

# Static files collect karo build time pe
RUN python manage.py collectstatic --noinput --clear

USER app
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8000/health/ || exit 1

# Gunicorn with optimal config
CMD ["gunicorn", "config.wsgi:application", \
     "--bind", "0.0.0.0:8000", \
     "--workers", "4", \
     "--worker-class", "gthread", \
     "--threads", "2", \
     "--max-requests", "1000", \
     "--max-requests-jitter", "50", \
     "--timeout", "120", \
     "--graceful-timeout", "30", \
     "--keep-alive", "5", \
     "--access-logfile", "-", \
     "--error-logfile", "-"]
```

**Gunicorn workers formula:** `(2 × CPU cores) + 1` — Fargate 1 vCPU = 3-4 workers safe hai.

---

### Q3: docker-compose.yml local + staging ke liye kaise likhoge?

**Answer:**
```yaml
# docker-compose.yml
version: "3.9"

services:
  # ─── Web Layer ────────────────────────────────────
  django:
    build: .
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgis://django:django@postgres:5432/myapp
      - REDIS_URL=redis://redis:6379/0
      - CELERY_BROKER_URL=redis://redis:6379/1
      - DJANGO_SETTINGS_MODULE=config.settings.production
      - SECRET_KEY=${SECRET_KEY}
      - ALLOWED_HOSTS=localhost,127.0.0.1
      - AWS_ACCESS_KEY_ID=${AWS_ACCESS_KEY_ID}
      - AWS_SECRET_ACCESS_KEY=${AWS_SECRET_ACCESS_KEY}
      - AWS_STORAGE_BUCKET_NAME=${S3_BUCKET}
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_started
    restart: unless-stopped

  # ─── Background Layer ─────────────────────────────
  celery-worker:
    build: .
    command: celery -A config worker -l info --concurrency=4 -Q default,high_priority
    environment:
      - DATABASE_URL=postgis://django:django@postgres:5432/myapp
      - REDIS_URL=redis://redis:6379/0
      - CELERY_BROKER_URL=redis://redis:6379/1
      - DJANGO_SETTINGS_MODULE=config.settings.production
    depends_on:
      - postgres
      - redis
    restart: unless-stopped

  celery-beat:
    build: .
    # ⚠️ Beat ka sirf EK instance run karo (duplicate task se bachne ke liye)
    command: celery -A config beat -l info --scheduler django_celery_beat.schedulers:DatabaseScheduler
    environment:
      - DATABASE_URL=postgis://django:django@postgres:5432/myapp
      - CELERY_BROKER_URL=redis://redis:6379/1
      - DJANGO_SETTINGS_MODULE=config.settings.production
    depends_on:
      - postgres
      - redis
    restart: unless-stopped

  flower:  # Celery monitoring UI (optional, dev only)
    build: .
    command: celery -A config flower --port=5555
    ports:
      - "5555:5555"
    depends_on:
      - redis

  # ─── Data Layer ───────────────────────────────────
  postgres:
    image: postgis/postgis:15-3.4   # ⭐ NOT regular postgres image — postgis bundled
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
    command: redis-server --maxmemory 256mb --maxmemory-policy allkeys-lru

  # ─── Reverse Proxy ────────────────────────────────
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
```

```sql
-- scripts/init-postgis.sql — PostGIS extension auto-enable
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS postgis_topology;
```

---

### Q4: Production Django settings (`config/settings/production.py`) kya hone chahiye?

**Answer:**
```python
# config/settings/production.py
from .base import *
from decouple import config
import structlog

# ─── Security ─────────────────────────────────────────
DEBUG = False
SECRET_KEY = config("SECRET_KEY")
ALLOWED_HOSTS = config("ALLOWED_HOSTS", default="").split(",")

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
SECURE_REFERRER_POLICY = "same-origin"

# ─── Database with psycopg3 pooling ──────────────────
DATABASES = {
    "default": {
        "ENGINE": "django.contrib.gis.db.backends.postgis",  # ⭐ PostGIS backend
        "NAME": config("DB_NAME"),
        "USER": config("DB_USER"),
        "PASSWORD": config("DB_PASSWORD"),
        "HOST": config("DB_HOST"),
        "PORT": config("DB_PORT", default="5432"),
        "CONN_MAX_AGE": 600,                # connection reuse 10 min
        "CONN_HEALTH_CHECKS": True,
        "OPTIONS": {
            "pool": {                       # psycopg3 native pooling
                "min_size": 4,
                "max_size": 20,
                "timeout": 10,
            }
        }
    }
}

# ─── Redis Cache ─────────────────────────────────────
CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": config("REDIS_URL"),
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
            "CONNECTION_POOL_KWARGS": {"max_connections": 50},
            "PASSWORD": config("REDIS_PASSWORD", default=None),
        },
        "KEY_PREFIX": "myapp:prod",
    }
}

SESSION_ENGINE = "django.contrib.sessions.backends.cache"

# ─── Celery ──────────────────────────────────────────
CELERY_BROKER_URL = config("CELERY_BROKER_URL")
CELERY_RESULT_BACKEND = config("REDIS_URL")
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TIMEZONE = "Asia/Kolkata"
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = 30 * 60          # 30 min hard limit
CELERY_TASK_SOFT_TIME_LIMIT = 25 * 60     # 25 min soft (warning)
CELERY_BEAT_SCHEDULER = "django_celery_beat.schedulers:DatabaseScheduler"

# Task routing — heavy tasks alag queue mein
CELERY_TASK_ROUTES = {
    "myapp.tasks.generate_pdf": {"queue": "high_priority"},
    "myapp.tasks.send_email": {"queue": "default"},
}

# ─── S3 Storage ──────────────────────────────────────
DEFAULT_FILE_STORAGE = "storages.backends.s3boto3.S3Boto3Storage"
STATICFILES_STORAGE = "storages.backends.s3boto3.S3StaticStorage"
AWS_STORAGE_BUCKET_NAME = config("AWS_STORAGE_BUCKET_NAME")
AWS_S3_REGION_NAME = config("AWS_S3_REGION_NAME", default="ap-south-1")
AWS_S3_OBJECT_PARAMETERS = {"CacheControl": "max-age=86400"}
AWS_QUERYSTRING_AUTH = False               # Public-read URLs
AWS_S3_FILE_OVERWRITE = False

# CDN URLs (CloudFront)
STATIC_URL = f"https://{config('CLOUDFRONT_DOMAIN')}/static/"
MEDIA_URL = f"https://{config('CLOUDFRONT_DOMAIN')}/media/"

# ─── CORS (React frontend) ───────────────────────────
CORS_ALLOWED_ORIGINS = config("CORS_ALLOWED_ORIGINS").split(",")
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_HEADERS = [
    "accept", "accept-encoding", "authorization", "content-type",
    "dnt", "origin", "user-agent", "x-csrftoken", "x-requested-with",
]

# ─── SimpleJWT ───────────────────────────────────────
from datetime import timedelta
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=15),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "ALGORITHM": "HS256",
    "SIGNING_KEY": config("JWT_SIGNING_KEY", default=SECRET_KEY),
}

# ─── Structured Logging (JSON) ───────────────────────
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
    "loggers": {
        "django.db.backends": {"level": "WARNING"},  # SQL logs off in prod
        "celery": {"level": "INFO"},
    },
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

# ─── Sentry Error Tracking ───────────────────────────
import sentry_sdk
from sentry_sdk.integrations.django import DjangoIntegration
from sentry_sdk.integrations.celery import CeleryIntegration

sentry_sdk.init(
    dsn=config("SENTRY_DSN"),
    integrations=[DjangoIntegration(), CeleryIntegration()],
    traces_sample_rate=0.1,           # 10% requests trace
    send_default_pii=False,           # GDPR compliance
    environment="production",
    release=config("APP_VERSION", default="unknown"),
)
```

---

### Q5: ECS Fargate par Django deploy karne ka step-by-step process kya hai?

**Answer:**

**Step 1: ECR repository banao + image push karo**
```bash
# ECR repo create
aws ecr create-repository --repository-name myapp-django --region ap-south-1

# Docker login
aws ecr get-login-password --region ap-south-1 | \
  docker login --username AWS --password-stdin <account-id>.dkr.ecr.ap-south-1.amazonaws.com

# Build + push
docker build -t myapp-django:latest .
docker tag myapp-django:latest <ecr-url>/myapp-django:latest
docker push <ecr-url>/myapp-django:latest
```

**Step 2: RDS PostgreSQL + PostGIS provision karo**
```bash
# Terraform se ya AWS Console se
aws rds create-db-instance \
  --db-instance-identifier myapp-postgres-prod \
  --engine postgres --engine-version 15.4 \
  --db-instance-class db.t3.small \
  --allocated-storage 20 --storage-type gp3 \
  --master-username django --master-user-password '<strong-password>' \
  --multi-az --backup-retention-period 7 \
  --vpc-security-group-ids sg-xxx --db-subnet-group-name my-subnet-group

# Connect karke PostGIS enable karo
psql -h <rds-endpoint> -U django -d postgres
CREATE DATABASE myapp;
\c myapp
CREATE EXTENSION postgis;
CREATE EXTENSION postgis_topology;
```

**Step 3: ElastiCache Redis provision karo**
```bash
aws elasticache create-cache-cluster \
  --cache-cluster-id myapp-redis-prod \
  --engine redis --engine-version 7.0 \
  --cache-node-type cache.t3.micro \
  --num-cache-nodes 1
```

**Step 4: Secrets Manager mein secrets store karo**
```bash
aws secretsmanager create-secret --name myapp/prod/django-secret-key \
  --secret-string "$(openssl rand -base64 64)"
aws secretsmanager create-secret --name myapp/prod/db-password --secret-string "your-db-pass"
aws secretsmanager create-secret --name myapp/prod/jwt-key --secret-string "$(openssl rand -base64 64)"
```

**Step 5: ECS Task Definitions banao (3 separate — Django, Worker, Beat)**

```json
// task-definition-django.json
{
  "family": "myapp-django",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "1024",
  "memory": "2048",
  "executionRoleArn": "arn:aws:iam::ACCOUNT:role/ecsTaskExecutionRole",
  "taskRoleArn": "arn:aws:iam::ACCOUNT:role/myapp-task-role",
  "containerDefinitions": [{
    "name": "django",
    "image": "ACCOUNT.dkr.ecr.ap-south-1.amazonaws.com/myapp-django:latest",
    "portMappings": [{"containerPort": 8000}],
    "environment": [
      {"name": "DJANGO_SETTINGS_MODULE", "value": "config.settings.production"},
      {"name": "DB_HOST", "value": "myapp-postgres-prod.xxx.rds.amazonaws.com"},
      {"name": "DB_NAME", "value": "myapp"},
      {"name": "DB_USER", "value": "django"},
      {"name": "REDIS_URL", "value": "redis://myapp-redis-prod.xxx.cache.amazonaws.com:6379/0"},
      {"name": "ALLOWED_HOSTS", "value": "api.yourapp.com"},
      {"name": "CORS_ALLOWED_ORIGINS", "value": "https://app.yourapp.com"}
    ],
    "secrets": [
      {"name": "SECRET_KEY", "valueFrom": "arn:aws:secretsmanager:..:secret:myapp/prod/django-secret-key"},
      {"name": "DB_PASSWORD", "valueFrom": "arn:aws:secretsmanager:..:secret:myapp/prod/db-password"}
    ],
    "logConfiguration": {
      "logDriver": "awslogs",
      "options": {
        "awslogs-group": "/ecs/myapp-django",
        "awslogs-region": "ap-south-1",
        "awslogs-stream-prefix": "django"
      }
    },
    "healthCheck": {
      "command": ["CMD-SHELL", "curl -f http://localhost:8000/health/ || exit 1"],
      "interval": 30, "timeout": 5, "retries": 3, "startPeriod": 30
    }
  }]
}
```

```bash
aws ecs register-task-definition --cli-input-json file://task-definition-django.json
aws ecs register-task-definition --cli-input-json file://task-definition-celery-worker.json
aws ecs register-task-definition --cli-input-json file://task-definition-celery-beat.json
```

**Step 6: Migrations run karo (one-off ECS task)**
```bash
aws ecs run-task \
  --cluster myapp-cluster \
  --task-definition myapp-django \
  --launch-type FARGATE \
  --overrides '{"containerOverrides":[{"name":"django","command":["python","manage.py","migrate"]}]}' \
  --network-configuration '{"awsvpcConfiguration":{"subnets":["subnet-xxx"],"securityGroups":["sg-xxx"]}}'
```

**Step 7: ECS Services create karo (Django, Worker, Beat)**
```bash
# Django service (behind ALB, desired count 2 for HA)
aws ecs create-service \
  --cluster myapp-cluster \
  --service-name django-web \
  --task-definition myapp-django \
  --desired-count 2 \
  --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={subnets=[subnet-xxx],securityGroups=[sg-xxx]}" \
  --load-balancers "targetGroupArn=arn:aws:elasticloadbalancing:..,containerName=django,containerPort=8000"

# Celery worker (no LB needed)
aws ecs create-service --cluster myapp-cluster --service-name celery-worker \
  --task-definition myapp-celery-worker --desired-count 2 --launch-type FARGATE \
  --network-configuration "..."

# Celery Beat (CRITICAL: desired-count = 1, no scaling)
aws ecs create-service --cluster myapp-cluster --service-name celery-beat \
  --task-definition myapp-celery-beat --desired-count 1 --launch-type FARGATE \
  --network-configuration "..."
```

**Step 8: ALB + ACM SSL setup**
```bash
# Request SSL cert
aws acm request-certificate --domain-name api.yourapp.com --validation-method DNS

# ALB listener 443 with cert
aws elbv2 create-listener --load-balancer-arn <alb-arn> \
  --protocol HTTPS --port 443 \
  --certificates CertificateArn=<acm-arn> \
  --default-actions Type=forward,TargetGroupArn=<tg-arn>
```

**Step 9: Auto-scaling configure karo**
```bash
aws application-autoscaling register-scalable-target \
  --service-namespace ecs \
  --resource-id service/myapp-cluster/django-web \
  --scalable-dimension ecs:service:DesiredCount \
  --min-capacity 2 --max-capacity 10

aws application-autoscaling put-scaling-policy \
  --service-namespace ecs \
  --resource-id service/myapp-cluster/django-web \
  --scalable-dimension ecs:service:DesiredCount \
  --policy-name cpu-scaling --policy-type TargetTrackingScaling \
  --target-tracking-scaling-policy-configuration '{
    "TargetValue": 70.0,
    "PredefinedMetricSpecification": {"PredefinedMetricType": "ECSServiceAverageCPUUtilization"}
  }'
```

**Step 10: React frontend → S3 + CloudFront**
```bash
cd frontend/
npm run build
aws s3 sync dist/ s3://myapp-frontend-prod/ --delete \
  --cache-control "public,max-age=31536000,immutable" --exclude "index.html"
aws s3 cp dist/index.html s3://myapp-frontend-prod/index.html \
  --cache-control "public,max-age=0,must-revalidate"
aws cloudfront create-invalidation --distribution-id E1234ABCD --paths "/*"
```

---

### Q6: Database migrations production mein safely kaise run karte hain? Zero-downtime kaise karte hain?

**Answer:**
**WRONG approach:** Container start hote hi `python manage.py migrate` run karna — race condition, multiple tasks parallel migrate → corrupt schema.

**RIGHT approach: 3 patterns:**

**Pattern 1: One-off ECS Task (recommended for Fargate)**
```bash
# Deploy script
1. New image build + push to ECR
2. Run migration as one-off task (waits for completion)
3. Update ECS service to use new image
```

```yaml
# .github/workflows/deploy.yml mein
- name: Run migrations
  run: |
    TASK_ARN=$(aws ecs run-task \
      --cluster $ECS_CLUSTER \
      --task-definition myapp-django-migrate \
      --launch-type FARGATE \
      --network-configuration "..." \
      --query 'tasks[0].taskArn' --output text)
    
    aws ecs wait tasks-stopped --cluster $ECS_CLUSTER --tasks $TASK_ARN
    
    EXIT_CODE=$(aws ecs describe-tasks --cluster $ECS_CLUSTER --tasks $TASK_ARN \
      --query 'tasks[0].containers[0].exitCode' --output text)
    
    [ "$EXIT_CODE" = "0" ] || exit 1

- name: Deploy new version
  run: aws ecs update-service --cluster $ECS_CLUSTER --service django-web --force-new-deployment
```

**Pattern 2: Init container (Kubernetes)**
- Pod start hone se pehle init container migrations chalata hai
- App container tabhi start hota hai jab init container exit 0 ho

**Pattern 3: Expand-Contract for zero-downtime schema changes**
```python
# Step 1 (Release N): NEW column add karo as nullable (additive only)
class User(models.Model):
    email = models.EmailField()
    phone = models.CharField(max_length=20, null=True, blank=True)  # NEW

# Step 2 (Release N): Code dual-write karo (purana + naya field)
# Step 3 (Release N+1): Backfill data via Celery task
# Step 4 (Release N+1): Code naya field hi use kare
# Step 5 (Release N+2): Old field/column DROP karo
```

**Common pitfalls:**
- ❌ `ALTER TABLE ADD COLUMN NOT NULL` without default → table lock
- ❌ `CREATE INDEX` non-concurrent → table lock
- ✅ Always use `CREATE INDEX CONCURRENTLY` for big tables (PostgreSQL)
- ✅ Django: `migrations.AddIndex` with `atomic=False` for concurrent index

---

### Q7: Celery workers production mein kaise scale karte hain? Beat duplicate task problem kaise solve karte hain?

**Answer:**

**Worker scaling:**
```bash
# Option 1: ECS auto-scaling based on SQS queue depth (KEDA jaisa)
# CloudWatch metric: ApproximateNumberOfMessagesVisible per queue
aws application-autoscaling put-scaling-policy \
  --policy-name celery-queue-scaling --policy-type TargetTrackingScaling \
  --target-tracking-scaling-policy-configuration '{
    "TargetValue": 100,
    "CustomizedMetricSpecification": {
      "MetricName": "ApproximateNumberOfMessagesVisible",
      "Namespace": "AWS/SQS",
      "Dimensions": [{"Name":"QueueName","Value":"celery-queue"}]
    }
  }'
```

**Multiple queues, priority-based:**
```python
# celery.py
app.conf.task_routes = {
    "myapp.tasks.send_otp": {"queue": "critical"},      # fast worker
    "myapp.tasks.generate_pdf": {"queue": "heavy"},     # high-mem worker
    "myapp.tasks.sync_inventory": {"queue": "default"},
}
```

```bash
# Different worker types
celery -A config worker -Q critical -c 8 -n critical@%h    # 8 concurrency
celery -A config worker -Q heavy -c 2 -n heavy@%h          # 2 (memory heavy)
celery -A config worker -Q default -c 4 -n default@%h
```

**Celery Beat duplicate problem:**
```
PROBLEM: Agar Beat ke 2+ instances chalein → same scheduled task 2x execute
SOLUTION 1: Always desired_count=1 in ECS for beat service
SOLUTION 2: Use RedBeat (Redis-based scheduler with lock)
SOLUTION 3: Use celery-singleton library for task-level locking
```

```python
# RedBeat — beat-level locking (safer for HA scenarios)
# pip install celery-redbeat
CELERY_BEAT_SCHEDULER = "redbeat.RedBeatScheduler"
CELERY_REDBEAT_REDIS_URL = config("REDIS_URL")
CELERY_REDBEAT_LOCK_KEY = "redbeat:lock"

# OR celery-singleton (task-level idempotency)
from celery_singleton import Singleton

@app.task(base=Singleton, lock_expiry=600)
def daily_sync_inventory():
    # Even if scheduled 2x, only 1 runs at a time
    ...
```

---

### Q8: Static files aur media files (S3) kaise handle karte hain? Frontend kaise serve karte hain?

**Answer:**

**Static files (CSS/JS — collectstatic se):**
```python
# settings/production.py
STATIC_URL = "https://d1234.cloudfront.net/static/"
STATIC_ROOT = "/app/staticfiles"  # collectstatic yahan collect karta hai
STATICFILES_STORAGE = "storages.backends.s3boto3.S3StaticStorage"

AWS_STORAGE_BUCKET_NAME = "myapp-prod-assets"
AWS_S3_CUSTOM_DOMAIN = "d1234.cloudfront.net"
AWS_LOCATION = "static"  # bucket ke andar /static/ folder
```

```bash
# Build time pe Dockerfile mein
RUN python manage.py collectstatic --noinput --clear
# Ya CI/CD pipeline mein S3 sync
```

**Media files (user uploads):**
```python
DEFAULT_FILE_STORAGE = "storages.backends.s3boto3.S3Boto3Storage"

# Model
class Quotation(models.Model):
    pdf = models.FileField(upload_to="quotations/%Y/%m/")
    # Automatic: S3 par https://bucket.s3.amazonaws.com/quotations/2024/01/abc.pdf

# Presigned URL for private files
import boto3
s3 = boto3.client("s3")
url = s3.generate_presigned_url(
    "get_object",
    Params={"Bucket": "myapp-prod-uploads", "Key": "private/invoice.pdf"},
    ExpiresIn=3600
)
```

**React frontend deployment (BEST: S3 + CloudFront):**
```bash
# Build
cd frontend
VITE_API_URL=https://api.yourapp.com npm run build

# Sync to S3 (with cache headers)
aws s3 sync dist/ s3://myapp-frontend-prod/ \
  --delete \
  --cache-control "public, max-age=31536000, immutable" \
  --exclude "index.html"

# index.html — never cache (always fetch latest)
aws s3 cp dist/index.html s3://myapp-frontend-prod/index.html \
  --cache-control "public, max-age=0, must-revalidate"

# Invalidate CloudFront
aws cloudfront create-invalidation \
  --distribution-id E1234ABCD \
  --paths "/index.html"
```

**Why S3+CloudFront for React (not Nginx container)?**
| Approach | Cost | Performance | Maintenance |
|---|---|---|---|
| S3+CloudFront | ₹500/mo | Edge cached (50ms global) | Zero |
| Nginx container | ₹3000/mo | Single region | Container management |

---

### Q9: GitHub Actions se complete CI/CD pipeline kaise likhoge?

**Answer:**
```yaml
# .github/workflows/deploy.yml
name: Deploy Backend to ECS

on:
  push:
    branches: [main]
    paths: ['backend/**']

env:
  AWS_REGION: ap-south-1
  ECR_REPOSITORY: myapp-django
  ECS_CLUSTER: myapp-cluster-prod

jobs:
  test:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgis/postgis:15-3.4
        env: {POSTGRES_USER: django, POSTGRES_PASSWORD: django, POSTGRES_DB: testdb}
        ports: ["5432:5432"]
        options: --health-cmd "pg_isready -U django" --health-interval 5s --health-retries 5
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
          python manage.py check --deploy
          python manage.py test
        env:
          DATABASE_URL: postgis://django:django@localhost:5432/testdb
          REDIS_URL: redis://localhost:6379/0
          SECRET_KEY: test-key

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
      - name: Run migrations as one-off task
        run: |
          TASK_ARN=$(aws ecs run-task --cluster $ECS_CLUSTER \
            --task-definition myapp-django-migrate \
            --launch-type FARGATE \
            --network-configuration 'awsvpcConfiguration={subnets=[subnet-xxx],securityGroups=[sg-xxx]}' \
            --query 'tasks[0].taskArn' --output text)
          aws ecs wait tasks-stopped --cluster $ECS_CLUSTER --tasks $TASK_ARN
          EXIT=$(aws ecs describe-tasks --cluster $ECS_CLUSTER --tasks $TASK_ARN \
            --query 'tasks[0].containers[0].exitCode' --output text)
          [ "$EXIT" = "0" ] || (echo "Migration failed" && exit 1)

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
      - name: Update ECS services (rolling deploy)
        run: |
          for svc in django-web celery-worker celery-beat; do
            aws ecs update-service --cluster $ECS_CLUSTER --service $svc --force-new-deployment
          done
          aws ecs wait services-stable --cluster $ECS_CLUSTER \
            --services django-web celery-worker celery-beat

      - name: Notify Slack
        if: always()
        run: |
          curl -X POST -H 'Content-type: application/json' \
            --data "{\"text\":\"Deploy ${{ job.status }}: ${{ github.sha }}\"}" \
            ${{ secrets.SLACK_WEBHOOK }}
```

---

### Q10: Monitoring + logging production mein kya setup karte hain?

**Answer:**

**3-layer observability stack:**

```
1. Metrics → CloudWatch + Prometheus (scrape /metrics endpoint)
2. Logs    → CloudWatch Logs → CloudWatch Insights (query)
3. Errors  → Sentry (real-time alerts + stack traces)
4. Tracing → AWS X-Ray ya Datadog APM
```

**CloudWatch alarms:**
```bash
# High 5xx error rate
aws cloudwatch put-metric-alarm \
  --alarm-name django-high-5xx \
  --metric-name HTTPCode_Target_5XX_Count \
  --namespace AWS/ApplicationELB \
  --statistic Sum --period 60 --evaluation-periods 2 \
  --threshold 10 --comparison-operator GreaterThanThreshold \
  --alarm-actions arn:aws:sns:..:alerts-topic

# RDS CPU
aws cloudwatch put-metric-alarm \
  --alarm-name rds-high-cpu \
  --metric-name CPUUtilization --namespace AWS/RDS \
  --statistic Average --period 300 --evaluation-periods 2 \
  --threshold 80 --comparison-operator GreaterThanThreshold

# Celery queue depth
aws cloudwatch put-metric-alarm \
  --alarm-name celery-queue-backlog \
  --metric-name ApproximateNumberOfMessagesVisible \
  --namespace AWS/SQS --period 60 --threshold 1000
```

**Sentry setup (already in settings):**
```python
# settings/production.py mein already added
sentry_sdk.init(
    dsn=config("SENTRY_DSN"),
    integrations=[DjangoIntegration(), CeleryIntegration()],
    traces_sample_rate=0.1,
)
```

**Django request logging (request_id ke saath):**
```python
# middleware.py
import uuid
import structlog
import time

log = structlog.get_logger()

class RequestLoggingMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        structlog.contextvars.bind_contextvars(request_id=request_id)
        
        start = time.time()
        response = self.get_response(request)
        duration_ms = (time.time() - start) * 1000

        log.info("request_completed",
                 method=request.method, path=request.path,
                 status=response.status_code,
                 duration_ms=round(duration_ms, 2),
                 user_id=getattr(request.user, "id", None))
        
        response["X-Request-ID"] = request_id
        return response
```

---

## Production Checklist (Deploy Karne Se Pehle)

```markdown
### Security
- [ ] DEBUG = False
- [ ] SECRET_KEY env var se (hardcoded nahi)
- [ ] ALLOWED_HOSTS configured
- [ ] HTTPS enforced (SECURE_SSL_REDIRECT, HSTS)
- [ ] CORS sirf trusted origins
- [ ] CSRF tokens enabled
- [ ] SQL injection — Django ORM use kar rahe ho (raw SQL avoid)
- [ ] Secrets AWS Secrets Manager mein (env vars mein nahi)
- [ ] Dependencies vulnerabilities scan (safety, snyk)

### Performance
- [ ] DB connection pooling (psycopg3 pool)
- [ ] Redis cache configured
- [ ] N+1 queries removed (select_related, prefetch_related)
- [ ] Gunicorn workers tuned ((2×CPU)+1)
- [ ] Static files on CDN (CloudFront)
- [ ] DB indexes on filter/order columns

### Reliability
- [ ] Health check endpoint (/health/)
- [ ] Readiness check (/health/ready - DB + Redis check)
- [ ] Multi-AZ RDS (production)
- [ ] Auto-scaling configured
- [ ] Backup strategy (RDS PITR + S3 versioning)
- [ ] Celery beat single instance
- [ ] Graceful shutdown (Gunicorn --graceful-timeout)

### Observability
- [ ] Structured JSON logs
- [ ] Request ID in all logs
- [ ] Sentry integration
- [ ] CloudWatch alarms (5xx, CPU, memory, queue depth)
- [ ] Prometheus /metrics endpoint
- [ ] Slack alerts wired

### CI/CD
- [ ] All tests pass before deploy
- [ ] OIDC for AWS (no long-lived keys)
- [ ] Migrations run before service update
- [ ] Rolling deploy with health checks
- [ ] Rollback script ready
```

---

## Common Production Issues + Fixes

| Issue | Cause | Fix |
|---|---|---|
| **502 Bad Gateway** | Gunicorn worker timeout | `--timeout 120`, check slow queries |
| **PostGIS missing** | Wrong DB image | Use `postgis/postgis:15-3.4` not `postgres:15` |
| **WeasyPrint crash** | Missing libpango | Install in Dockerfile (already shown) |
| **Celery duplicate task** | Multiple Beat instances | desired_count=1 for beat service |
| **Memory leak** | Workers not recycling | Gunicorn `--max-requests 1000` |
| **Slow API** | N+1 queries | `select_related`, `prefetch_related`, debug toolbar |
| **High RDS CPU** | Missing indexes | `EXPLAIN ANALYZE`, add indexes |
| **JWT refresh fail** | Token blacklist not configured | `BLACKLIST_AFTER_ROTATION=True` |
| **CORS error in frontend** | Missing origin | `CORS_ALLOWED_ORIGINS` exact match |
| **S3 upload 403** | IAM permissions | Task role mein `s3:PutObject` |
