# Cloud & DevOps Deep Guide — AWS · Docker · CI/CD
### Resume Skills: AWS, Docker, GitHub Actions, CI/CD, ECS, CloudWatch
### PwC Interview Ready · 3-4 baar padho

> **Reading plan:**
> - Pass 1: Poora padho — architecture samjho
> - Pass 2: Interview answers loud bolke practice karo
> - Pass 3: Architecture diagrams haath se draw karo
> - Pass 4: Quick Recall Card only

---

## TABLE OF CONTENTS

| # | Topic | Tera Resume Project |
|---|---|---|
| 1 | Docker — containers + internals | All deployments |
| 2 | Dockerfile — best practices | Niroskos, Youngman |
| 3 | Docker Compose — local dev | Local stack |
| 4 | AWS Core Services — backend dev ke liye | Cloud deployment |
| 5 | AWS IAM + Security | Zero-trust auth |
| 6 | AWS ECS Fargate — container deployment | Production |
| 7 | AWS CloudWatch — logging + monitoring | Observability |
| 8 | CI/CD — GitHub Actions pipeline | Automated deploy |
| 9 | Full pipeline — code to prod | End-to-end |
| 10 | Interview Q&A — 18 Questions | PwC specific |
| 11 | Quick Recall Card | 1 ghanta pehle |

---

## TOPIC 1: DOCKER — CONTAINERS + INTERNALS

### Definition

```
Docker = Application ko container mein package karo.
"Works on my machine" problem solve karta hai.
Container = isolated process with its own filesystem, network, PID.
NOT a VM — shares host OS kernel, much lighter.
```

### Container vs VM

```
VIRTUAL MACHINE:                    CONTAINER:
────────────────────────────        ────────────────────────────
┌──────────────────────────┐        ┌──────────────────────────┐
│  App A  │  App B  │ App C│        │  App A  │ App B  │ App C │
├─────────┼─────────┼──────┤        ├─────────┼────────┼───────┤
│  OS A   │  OS B   │ OS C │        │  Libs A │ Libs B │Libs C │
├─────────┴─────────┴──────┤        ├──────────────────────────┤
│      Hypervisor          │        │       Docker Engine       │
├──────────────────────────┤        ├──────────────────────────┤
│       Host OS            │        │         Host OS          │
├──────────────────────────┤        ├──────────────────────────┤
│       Hardware           │        │         Hardware         │
└──────────────────────────┘        └──────────────────────────┘

VM: Each has full OS (5-10GB each, minutes to start)
Container: Shares host kernel (50-500MB, seconds to start)

ISOLATION:
Container: Process isolation (namespaces), resource limits (cgroups)
VM: Full OS isolation (stronger, but heavier)
```

### How Docker works — internals

```
DOCKER INTERNALS
────────────────────────────────────────────────────────────────

DOCKER CLI            DOCKER DAEMON           CONTAINERD
docker build ────────► dockerd ──────────────► containerd
docker run            (REST API server)        (container runtime)
docker push                │                       │
                           │                       │
                    IMAGE REGISTRY              runc (OCI runtime)
                    (ECR / DockerHub)           (actual process)
                           │
                    LOCAL IMAGE CACHE
                    (layered filesystem)

LAYERS (Union filesystem — OverlayFS):
────────────────────────────────────────
┌─────────────────────────────────────┐ ← CONTAINER LAYER (writable)
├─────────────────────────────────────┤ ← COPY: app code (read-only)
├─────────────────────────────────────┤ ← COPY: requirements (read-only)
├─────────────────────────────────────┤ ← RUN: pip install (read-only)
├─────────────────────────────────────┤ ← FROM: python:3.11-slim (read-only)
└─────────────────────────────────────┘ ← base OS (read-only)

Each layer = result of one Dockerfile instruction
Layers are CACHED — only changed layers rebuild
This is why order in Dockerfile matters!
```

---

## TOPIC 2: DOCKERFILE — BEST PRACTICES

### Basic Dockerfile (wrong way first)

```dockerfile
# ❌ BAD Dockerfile — teri galtiyan aur why
FROM python:3.11

WORKDIR /app

# BAD: Copy everything first → code change invalidates ALL subsequent cache
COPY . .

# BAD: pip install after copy → every code change = full reinstall
RUN pip install -r requirements.txt

# BAD: Running as root → security risk
EXPOSE 8000
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
# BAD: runserver in production!
```

### Production Dockerfile (correct)

```dockerfile
# ✅ GOOD Dockerfile — Niroskos production
# MULTI-STAGE BUILD: builder + final (smaller image)

# ─── Stage 1: Builder ─────────────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /app

# System deps (rare change → cached forever after first build)
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*   # clean apt cache (smaller image)

# Copy ONLY requirements first (changes rarely → cache stays warm)
COPY requirements.txt .
RUN pip install --user --no-cache-dir -r requirements.txt
# --user: installs to ~/.local (easy to copy to final stage)
# --no-cache-dir: don't cache pip downloads (smaller layer)

# ─── Stage 2: Final (production image) ────────────────────────
FROM python:3.11-slim AS final

WORKDIR /app

# Runtime system deps only (no build-essential)
RUN apt-get update && apt-get install -y \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy installed packages from builder (not pip itself)
COPY --from=builder /root/.local /root/.local

# Create non-root user (security)
RUN addgroup --system appgroup && adduser --system --ingroup appgroup appuser

# Copy application code (changes frequently → last layer)
COPY --chown=appuser:appgroup . .

# Use non-root user
USER appuser

# Collect static files
RUN python manage.py collectstatic --noinput

EXPOSE 8000

# Production server: gunicorn (not runserver!)
CMD ["gunicorn", \
     "--bind", "0.0.0.0:8000", \
     "--workers", "4", \
     "--worker-class", "uvicorn.workers.UvicornWorker", \
     "--timeout", "120", \
     "--access-logfile", "-", \
     "--error-logfile", "-", \
     "config.asgi:application"]
```

### .dockerignore — important

```
# .dockerignore
__pycache__/
*.pyc
*.pyo
.env
.env.*
.git/
.gitignore
*.md
tests/
.pytest_cache/
.coverage
coverage/
node_modules/
*.log
*.sqlite3
.DS_Store
```

### Multi-stage build benefits

```
WITHOUT multi-stage:
├── build-essential (gcc, make, etc.)  → 200MB
├── pip cache                           → 100MB
├── dev dependencies                    → 50MB
Total image: 800MB+

WITH multi-stage:
Builder stage: all of the above (used only during build)
Final stage: only runtime deps
Total image: 150MB

SMALLER IMAGE =
✅ Faster push/pull (ECR → ECS → prod)
✅ Less attack surface (no build tools in prod)
✅ Less storage cost
✅ Faster container startup
```

---

## TOPIC 3: DOCKER COMPOSE — LOCAL DEV

### Full local stack

```yaml
# docker-compose.yml — Niroskos local dev

version: "3.9"

services:
  # ─── PostgreSQL ────────────────────────────────────────
  db:
    image: postgres:15-alpine
    environment:
      POSTGRES_DB: niroskos_db
      POSTGRES_USER: niroskos
      POSTGRES_PASSWORD: localpass
    volumes:
      - postgres_data:/var/lib/postgresql/data   # persist data
    ports:
      - "5432:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U niroskos"]
      interval: 5s
      timeout: 5s
      retries: 5

  # ─── Redis ─────────────────────────────────────────────
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    command: redis-server --appendonly yes

  # ─── Django app ────────────────────────────────────────
  web:
    build:
      context: .
      target: final        # use final stage of multi-stage
    command: >
      sh -c "python manage.py migrate &&
             python manage.py runserver 0.0.0.0:8000"
    volumes:
      - .:/app             # live reload: code changes reflected instantly
    ports:
      - "8000:8000"
    environment:
      DATABASE_URL: postgresql://niroskos:localpass@db:5432/niroskos_db
      REDIS_URL: redis://redis:6379/0
      DEBUG: "True"
    env_file:
      - .env.local
    depends_on:
      db:
        condition: service_healthy   # wait for DB ready
      redis:
        condition: service_started

  # ─── Celery worker ─────────────────────────────────────
  celery_worker:
    build:
      context: .
      target: final
    command: celery -A config worker -Q high,default -l info
    volumes:
      - .:/app
    environment:
      DATABASE_URL: postgresql://niroskos:localpass@db:5432/niroskos_db
      CELERY_BROKER_URL: redis://redis:6379/0
    depends_on:
      - db
      - redis

  # ─── Celery Beat ───────────────────────────────────────
  celery_beat:
    build:
      context: .
      target: final
    command: celery -A config beat -l info
    volumes:
      - .:/app
    depends_on:
      - redis

  # ─── Flower (Celery monitoring) ────────────────────────
  flower:
    build:
      context: .
      target: final
    command: celery -A config flower --port=5555
    ports:
      - "5555:5555"
    depends_on:
      - redis

volumes:
  postgres_data:
  redis_data:
```

### Useful commands

```bash
# Start everything
docker compose up -d

# Logs (all services)
docker compose logs -f

# Logs (specific service)
docker compose logs -f web

# Execute command in running container
docker compose exec web python manage.py shell
docker compose exec web python manage.py createsuperuser
docker compose exec web python manage.py migrate

# Rebuild after Dockerfile change
docker compose up -d --build web

# Stop everything
docker compose down

# Stop + delete volumes (clean slate)
docker compose down -v

# See what's running
docker compose ps

# Resource usage
docker stats
```

---

## TOPIC 4: AWS CORE SERVICES

### Backend developer ko kya kya jaanna chahiye

```
AWS SERVICE MAP (tera interview relevant)
────────────────────────────────────────────────────────────────

COMPUTE:
├── EC2        → Virtual servers (when you need full control)
├── ECS        → Docker container orchestration (production!)
│   ├── Fargate  → Serverless containers (no EC2 to manage)
│   └── EC2 mode → You manage EC2 instances
├── Lambda     → Serverless functions (event-driven, short tasks)
└── App Runner → Deploy from ECR directly (simpler than ECS)

STORAGE:
├── S3         → Object storage (files, backups, static assets)
├── EBS        → EC2 block storage (like hard drive for EC2)
└── EFS        → Shared filesystem (multiple EC2/ECS can mount)

DATABASE:
├── RDS        → Managed PostgreSQL/MySQL (automated backups, patching)
├── Aurora     → AWS's PostgreSQL/MySQL (faster, auto-scaling)
├── ElastiCache→ Managed Redis / Memcached
└── DynamoDB   → NoSQL key-value (serverless, infinite scale)

MESSAGING:
├── SQS        → Message queue (Topic 7 mein covered)
├── SNS        → Pub/Sub notifications (send to SQS/Lambda/email/SMS)
└── EventBridge→ Event bus (route events between AWS services)

NETWORKING:
├── VPC        → Virtual Private Cloud (your private network in AWS)
├── ALB        → Application Load Balancer (HTTP/HTTPS routing)
├── CloudFront → CDN (cache static assets globally)
└── Route 53   → DNS management

SECURITY:
├── IAM        → Identity & Access Management (Topic 5)
├── Secrets Manager → Store API keys, DB passwords securely
└── ACM        → SSL/TLS certificates (free)

OBSERVABILITY:
├── CloudWatch → Logs + Metrics + Alarms (Topic 7)
├── X-Ray      → Distributed tracing (like Jaeger for AWS)
└── CloudTrail → Who did what (audit log)

CONTAINERS:
└── ECR        → Elastic Container Registry (private Docker hub)
```

### Typical Django on AWS architecture

```
PRODUCTION ARCHITECTURE — Niroskos on AWS
────────────────────────────────────────────────────────────────

                           ┌─────────────┐
                           │  Route 53   │
                           │  (DNS)      │
                           └──────┬──────┘
                                  │
                           ┌──────▼──────┐
                           │   ALB       │
                           │ (HTTPS:443) │
                           │ ACM cert    │
                           └──────┬──────┘
                                  │
              ┌───────────────────┼───────────────────┐
              │                   │                   │
       ┌──────▼──────┐    ┌──────▼──────┐    ┌──────▼──────┐
       │ECS Fargate  │    │ECS Fargate  │    │ECS Fargate  │
       │Task: web    │    │Task: web    │    │Task: web    │
       │(Django+     │    │(Django+     │    │(Django+     │
       │ gunicorn)   │    │ gunicorn)   │    │ gunicorn)   │
       └──────┬──────┘    └──────┬──────┘    └──────┬──────┘
              │                   │                   │
              └───────────────────┼───────────────────┘
                                  │
              ┌───────────────────┼───────────────────┐
              │                   │                   │
       ┌──────▼──────┐    ┌──────▼──────┐    ┌──────▼──────┐
       │  RDS         │    │ ElastiCache │    │     S3      │
       │  PostgreSQL  │    │   Redis     │    │   Media +   │
       │  (Multi-AZ)  │    │  (cluster)  │    │   Static    │
       └──────────────┘    └─────────────┘    └─────────────┘

       ┌──────────────────────────────────────────────────────┐
       │        ECS Fargate — Celery Workers                  │
       │  ┌────────────┐ ┌────────────┐ ┌──────────────────┐  │
       │  │ worker:high│ │worker:def  │ │  celery-beat     │  │
       │  │ (count: 2) │ │(count: 4)  │ │  (count: 1)      │  │
       │  └────────────┘ └────────────┘ └──────────────────┘  │
       └──────────────────────────────────────────────────────┘

VPC:
  Public subnets: ALB (internet-facing)
  Private subnets: ECS tasks, RDS, ElastiCache (no direct internet)
  NAT Gateway: Private resources → internet (outbound only)
```

---

## TOPIC 5: AWS IAM + SECURITY

### IAM hierarchy

```
IAM CONCEPTS:
────────────────────────────────────────────────────────────────

USER    → Human user (you, developer)
GROUP   → Collection of users (Developers, Admins)
ROLE    → Identity for AWS services (EC2 role, ECS task role, Lambda role)
POLICY  → JSON document defining permissions

BEST PRACTICES:
✅ Least privilege: give ONLY what's needed
✅ Use roles for services (not access keys)
✅ Never hardcode AWS keys in code
✅ Enable MFA for human users
✅ Rotate credentials regularly

ECS TASK ROLE (tera app se AWS services access):
App → (no keys needed) → AWS SDK → IAM → checks Task Role → allowed!
```

### IAM policy — JSON

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "S3MediaAccess",
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:PutObject",
        "s3:DeleteObject"
      ],
      "Resource": "arn:aws:s3:::niroskos-media/*"
    },
    {
      "Sid": "S3ListBucket",
      "Effect": "Allow",
      "Action": "s3:ListBucket",
      "Resource": "arn:aws:s3:::niroskos-media"
    },
    {
      "Sid": "SQSAccess",
      "Effect": "Allow",
      "Action": [
        "sqs:SendMessage",
        "sqs:ReceiveMessage",
        "sqs:DeleteMessage",
        "sqs:GetQueueAttributes"
      ],
      "Resource": "arn:aws:sqs:ap-south-1:123456789:niroskos-*"
    },
    {
      "Sid": "SecretsAccess",
      "Effect": "Allow",
      "Action": [
        "secretsmanager:GetSecretValue"
      ],
      "Resource": "arn:aws:secretsmanager:ap-south-1:123456789:secret:niroskos/*"
    }
  ]
}
```

### Secrets Manager in Django

```python
# settings.py — never hardcode secrets!

# ❌ BAD
DATABASE_PASSWORD = "my_db_password_123"

# ✅ GOOD — AWS Secrets Manager
import boto3
import json

def get_secret(secret_name: str) -> dict:
    client = boto3.client("secretsmanager", region_name="ap-south-1")
    response = client.get_secret_value(SecretId=secret_name)
    return json.loads(response["SecretString"])

# Load DB secrets at startup
if not DEBUG:   # only in production
    db_secrets = get_secret("niroskos/production/database")
    DATABASE_PASSWORD = db_secrets["password"]
    DATABASE_HOST = db_secrets["host"]

# OR use environment variables (ECS injects from Secrets Manager):
# Task definition pe:
# "secrets": [{"name": "DB_PASSWORD", "valueFrom": "arn:..."}]
# ECS automatically injects as env var → Django reads normally
DATABASE_PASSWORD = os.environ.get("DB_PASSWORD")
```

---

## TOPIC 6: AWS ECS FARGATE — CONTAINER DEPLOYMENT

### What is ECS Fargate

```
ECS = Elastic Container Service (AWS's Kubernetes-like orchestrator)
Fargate = Serverless compute for containers

YOU DEFINE:
- Docker image (from ECR)
- CPU + Memory (e.g., 0.5 vCPU, 1GB)
- Environment variables (from Secrets Manager)
- Task role (IAM permissions)
- Networking (VPC, subnets, security groups)

AWS MANAGES:
- Underlying EC2 instances (you never see them)
- Scaling
- Health checks + restart on failure
- Log delivery to CloudWatch
```

### ECS Task Definition (JSON)

```json
{
  "family": "niroskos-web",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "512",
  "memory": "1024",
  "executionRoleArn": "arn:aws:iam::123:role/ecsTaskExecutionRole",
  "taskRoleArn": "arn:aws:iam::123:role/niroskos-task-role",
  "containerDefinitions": [
    {
      "name": "web",
      "image": "123456789.dkr.ecr.ap-south-1.amazonaws.com/niroskos:latest",
      "portMappings": [{"containerPort": 8000, "protocol": "tcp"}],
      "environment": [
        {"name": "DEBUG", "value": "False"},
        {"name": "ALLOWED_HOSTS", "value": "*.niroskos.com"}
      ],
      "secrets": [
        {
          "name": "DATABASE_URL",
          "valueFrom": "arn:aws:secretsmanager:ap-south-1:123:secret:niroskos/db_url"
        },
        {
          "name": "SECRET_KEY",
          "valueFrom": "arn:aws:secretsmanager:ap-south-1:123:secret:niroskos/secret_key"
        }
      ],
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "/ecs/niroskos-web",
          "awslogs-region": "ap-south-1",
          "awslogs-stream-prefix": "ecs"
        }
      },
      "healthCheck": {
        "command": ["CMD-SHELL", "curl -f http://localhost:8000/health/ || exit 1"],
        "interval": 30,
        "timeout": 5,
        "retries": 3,
        "startPeriod": 60
      }
    }
  ]
}
```

---

## TOPIC 7: AWS CLOUDWATCH — LOGGING + MONITORING

### Log architecture

```
CLOUDWATCH LOGS ARCHITECTURE
────────────────────────────────────────────────────────────────

ECS Container (Django app)
    │  stdout / stderr
    │  (gunicorn access log, Django logger)
    │
    ▼
CloudWatch Logs Agent (built into Fargate)
    │  automatic forwarding
    ▼
CloudWatch Logs
├── Log Group: /ecs/niroskos-web
│   ├── Log Stream: ecs/web/task-abc123
│   └── Log Stream: ecs/web/task-def456
└── Log Group: /ecs/niroskos-celery
    └── Log Stream: ecs/celery/task-xyz789

QUERY (CloudWatch Insights):
fields @timestamp, @message
| filter @message like /ERROR/
| sort @timestamp desc
| limit 50

METRIC FILTER:
Create metric from log pattern:
Pattern: "[ERROR]"
→ ErrorCount metric per minute
→ Alarm: ErrorCount > 10 → SNS → Slack alert
```

### Django logging for CloudWatch

```python
# settings.py
import logging

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "json": {
            "()": "pythonjsonlogger.jsonlogger.JsonFormatter",
            "format": "%(asctime)s %(name)s %(levelname)s %(message)s",
        },
        "verbose": {
            "format": "{levelname} {asctime} {module} {process:d} {thread:d} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "json",   # JSON format → CloudWatch Insights parseable
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "INFO",
    },
    "loggers": {
        "django": {"handlers": ["console"], "level": "WARNING"},
        "django.db.backends": {"handlers": ["console"], "level": "WARNING"},
        "niroskos": {"handlers": ["console"], "level": "INFO"},
        "celery": {"handlers": ["console"], "level": "INFO"},
    },
}

# Usage in code:
logger = logging.getLogger("niroskos.bookings")

logger.info(
    "Booking created",
    extra={
        "booking_id": booking.id,
        "user_id": request.user.id,
        "amount": str(booking.total_amount),
        "tour": booking.tour.slug,
    }
)
# CloudWatch Insights query:
# fields @timestamp, booking_id, amount
# | filter message = "Booking created"
# | stats count() by bin(1h)
```

### CloudWatch alarms

```python
import boto3

cloudwatch = boto3.client("cloudwatch", region_name="ap-south-1")

# Create alarm: p95 latency > 500ms → alert
cloudwatch.put_metric_alarm(
    AlarmName="niroskos-high-latency",
    MetricName="TargetResponseTime",
    Namespace="AWS/ApplicationELB",
    Dimensions=[
        {"Name": "LoadBalancer", "Value": "app/niroskos-alb/abc123"}
    ],
    Statistic="p95",
    Period=60,           # 1 minute
    EvaluationPeriods=3, # 3 consecutive minutes
    Threshold=0.5,       # 500ms
    ComparisonOperator="GreaterThanThreshold",
    AlarmActions=["arn:aws:sns:ap-south-1:123:niroskos-alerts"],
    TreatMissingData="notBreaching",
)
```

---

## TOPIC 8: CI/CD — GITHUB ACTIONS PIPELINE

### What is CI/CD

```
CI = Continuous Integration
  Every push → automated: lint + test + build
  Catch bugs before merge

CD = Continuous Deployment
  Every merge to main → automated deploy to production

WITHOUT CI/CD:
dev: "code likha, local pe test kiya, ship!"
ops: "kuch toot gaya prod pe"
dev: "mere machine pe kaam kar raha tha..."

WITH CI/CD:
Push → Tests auto-run → Build Docker → Push to ECR → Deploy to ECS
5-15 minutes, fully automated, consistent, repeatable
```

### Full GitHub Actions pipeline

```yaml
# .github/workflows/deploy.yml

name: CI/CD — Test, Build, Deploy

on:
  push:
    branches: [main]        # prod deploy
  pull_request:
    branches: [main]        # just test on PR

env:
  AWS_REGION: ap-south-1
  ECR_REGISTRY: 123456789.dkr.ecr.ap-south-1.amazonaws.com
  ECR_REPOSITORY: niroskos
  ECS_CLUSTER: niroskos-cluster
  ECS_SERVICE: niroskos-web
  ECS_CELERY_SERVICE: niroskos-celery

jobs:
  # ═══════════════════════════════════════════════════
  # JOB 1: Test (runs on every push + PR)
  # ═══════════════════════════════════════════════════
  test:
    name: Lint + Test
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:15
        env:
          POSTGRES_DB: test_db
          POSTGRES_USER: postgres
          POSTGRES_PASSWORD: postgres
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
        ports:
          - 5432:5432
      redis:
        image: redis:7
        ports:
          - 6379:6379

    env:
      DATABASE_URL: postgresql://postgres:postgres@localhost:5432/test_db
      REDIS_URL: redis://localhost:6379/0
      SECRET_KEY: test-secret-key-not-real
      DEBUG: "True"

    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"
          cache: "pip"      # cache pip packages

      - name: Install dependencies
        run: pip install -r requirements.txt -r requirements-dev.txt

      - name: Lint — ruff
        run: ruff check .

      - name: Type check — mypy
        run: mypy config/ bookings/ invoicing/

      - name: Run migrations
        run: python manage.py migrate --settings=config.settings.test

      - name: Run tests
        run: |
          pytest tests/ \
            --cov=. \
            --cov-report=xml \
            --cov-fail-under=80 \
            -v \
            --tb=short

      - name: Upload coverage
        uses: codecov/codecov-action@v4
        with:
          file: coverage.xml

  # ═══════════════════════════════════════════════════
  # JOB 2: Build + Push to ECR (only on main push)
  # ═══════════════════════════════════════════════════
  build:
    name: Build Docker + Push ECR
    runs-on: ubuntu-latest
    needs: test               # only if tests pass
    if: github.ref == 'refs/heads/main'

    outputs:
      image-tag: ${{ steps.meta.outputs.tags }}

    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Configure AWS credentials
        uses: aws-actions/configure-aws-credentials@v4
        with:
          aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
          aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
          aws-region: ${{ env.AWS_REGION }}

      - name: Login to Amazon ECR
        id: ecr-login
        uses: aws-actions/amazon-ecr-login@v2

      - name: Set up Docker Buildx (for caching)
        uses: docker/setup-buildx-action@v3

      - name: Build + push Docker image
        id: build
        uses: docker/build-push-action@v5
        with:
          context: .
          target: final           # multi-stage: use final stage
          push: true
          tags: |
            ${{ env.ECR_REGISTRY }}/${{ env.ECR_REPOSITORY }}:latest
            ${{ env.ECR_REGISTRY }}/${{ env.ECR_REPOSITORY }}:${{ github.sha }}
          cache-from: type=gha    # GitHub Actions cache
          cache-to: type=gha,mode=max

  # ═══════════════════════════════════════════════════
  # JOB 3: Deploy to ECS (only on main push)
  # ═══════════════════════════════════════════════════
  deploy:
    name: Deploy to ECS
    runs-on: ubuntu-latest
    needs: build
    if: github.ref == 'refs/heads/main'
    environment: production    # GitHub environment + approval gate

    steps:
      - name: Configure AWS credentials
        uses: aws-actions/configure-aws-credentials@v4
        with:
          aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
          aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
          aws-region: ${{ env.AWS_REGION }}

      - name: Download task definition
        run: |
          aws ecs describe-task-definition \
            --task-definition niroskos-web \
            --query taskDefinition \
            > task-definition.json

      - name: Update ECS task definition with new image
        id: task-def
        uses: aws-actions/amazon-ecs-render-task-definition@v1
        with:
          task-definition: task-definition.json
          container-name: web
          image: ${{ env.ECR_REGISTRY }}/${{ env.ECR_REPOSITORY }}:${{ github.sha }}

      - name: Run DB migrations (one-off ECS task)
        run: |
          aws ecs run-task \
            --cluster ${{ env.ECS_CLUSTER }} \
            --task-definition niroskos-migrate \
            --launch-type FARGATE \
            --network-configuration "awsvpcConfiguration={subnets=[subnet-abc],securityGroups=[sg-xyz],assignPublicIp=DISABLED}" \
            --overrides '{"containerOverrides":[{"name":"web","command":["python","manage.py","migrate","--no-input"]}]}'

      - name: Deploy web service
        uses: aws-actions/amazon-ecs-deploy-task-definition@v1
        with:
          task-definition: ${{ steps.task-def.outputs.task-definition }}
          service: ${{ env.ECS_SERVICE }}
          cluster: ${{ env.ECS_CLUSTER }}
          wait-for-service-stability: true    # wait for rollout complete

      - name: Deploy celery workers
        uses: aws-actions/amazon-ecs-deploy-task-definition@v1
        with:
          task-definition: ${{ steps.task-def.outputs.task-definition }}
          service: ${{ env.ECS_CELERY_SERVICE }}
          cluster: ${{ env.ECS_CLUSTER }}
          wait-for-service-stability: true

      - name: Slack deploy notification
        if: always()
        uses: 8398a7/action-slack@v3
        with:
          status: ${{ job.status }}
          text: "Niroskos deployed: ${{ github.sha }}"
        env:
          SLACK_WEBHOOK_URL: ${{ secrets.SLACK_WEBHOOK_URL }}
```

---

## TOPIC 9: FULL PIPELINE — CODE TO PRODUCTION

### End-to-end flow

```
DEVELOPER WORKFLOW
────────────────────────────────────────────────────────────────

1. Feature branch banaao
   git checkout -b feature/booking-webhook

2. Code likho + local test karo
   docker compose up -d
   pytest tests/bookings/

3. PR open karo → GitHub
   → CI pipeline triggers automatically:
      ✅ ruff lint (30s)
      ✅ mypy type check (1min)
      ✅ pytest + coverage (3min)
      ❌ If any fail → PR blocked

4. Code review → Approve → Merge to main

5. CI/CD pipeline (on main push):
   ┌──────────────────────────────────────────────────────┐
   │ Step 1: test job runs (same as PR but final gate)    │ 4 min
   │ Step 2: Docker build with cache                      │ 3 min
   │   → Multi-stage build (builder + final)              │
   │   → Push to ECR:latest + ECR:sha                     │
   │ Step 3: Deploy to ECS                                │ 5 min
   │   → Run migrations (one-off ECS task)                │
   │   → Update web service task definition               │
   │   → Rolling deploy (old tasks → new tasks)           │
   │   → Update celery workers                            │
   │   → Wait for stability                               │
   └──────────────────────────────────────────────────────┘
   Total: ~12-15 minutes

6. ECS rolling deploy:
   OLD:  [task-v1] [task-v1] [task-v1]
   STEP: [task-v2] [task-v1] [task-v1]  ← health check v2
   STEP: [task-v2] [task-v2] [task-v1]
   DONE: [task-v2] [task-v2] [task-v2]
   Zero downtime! ALB routes only to healthy tasks.

7. Slack notification → "Deployed: feature/booking-webhook"
```

### Rollback strategy

```bash
# If deployment goes wrong:

# Option 1: Re-deploy previous image tag
aws ecs update-service \
  --cluster niroskos-cluster \
  --service niroskos-web \
  --task-definition niroskos-web:42   # previous task def version

# Option 2: GitHub — revert merge commit → triggers deploy pipeline

# Option 3: Force new deployment with previous tag
# (CI/CD stores image:sha → can deploy any previous sha)

# DEPLOYMENT PROTECTION:
# CloudWatch alarm pe rollback:
# - Error rate > 5% → auto-rollback (ECS Deployment Circuit Breaker)
# ECS setting:
# deploymentConfiguration:
#   deploymentCircuitBreaker:
#     enable: true
#     rollback: true
```

---

## TOPIC 10: INTERVIEW Q&A — 18 Questions

---

**Q1. Docker ka ek real problem solve karo — "works on my machine" issue?**

```
ANSWER:
Classic problem: local pe Python 3.10, prod pe 3.8 → f-string feature
kaam nahi kar raha.

DOCKER SOLUTION:
Dockerfile mein exact environment define karo:
FROM python:3.11.9-slim

Ab har jagah same:
- Same Python version
- Same OS (Debian slim)
- Same system libraries
- Same pip packages (requirements.txt pinned)

docker build → same image → same behavior everywhere
Dev machine, CI, staging, production — identical.

ADDITIONAL BENEFITS:
- New team member → docker compose up → 5 min mein running
- No "install PostgreSQL locally" instructions
- Isolated: different projects different Python versions
- Reproducible: git sha → exact image → exact behavior
```

---

**Q2. Multi-stage Docker build kyun use karte ho?**

```
ANSWER:
Production image size minimize karna.

WITHOUT:
FROM python:3.11
RUN apt-get install build-essential gcc    # 200MB build tools
COPY requirements.txt .
RUN pip install -r requirements.txt        # includes build cache
COPY . .
Final image: 800MB+

WITH MULTI-STAGE:
Stage 1 (builder): build-essential + pip install → packages built
Stage 2 (final): COPY --from=builder only the installed packages
Final image: 150MB

WHY MATTERS:
✅ Faster ECR push/pull (650MB less)
✅ Less attack surface (no gcc, make in prod)
✅ Smaller CVE surface (security scans)
✅ Faster container startup
✅ Less ECR storage cost

Niroskos image: 800MB → 180MB after multi-stage.
Deploy time: 4min → 90 seconds.
```

---

**Q3. CI/CD pipeline mein kya stages hain — tera actual setup?**

```
ANSWER (3 jobs, ~12 minutes):

Job 1: test (every PR + main push)
  - ruff lint (code style)
  - mypy type checking
  - pytest with coverage (80% minimum)
  - Real Postgres + Redis services in CI
  - If fails → deployment blocked

Job 2: build (main push only, after test passes)
  - AWS credentials configure
  - ECR login
  - Docker build (multi-stage, with GitHub Actions cache)
  - Push: ECR:latest + ECR:sha (for rollback)

Job 3: deploy (main push only, after build)
  - GitHub environment: "production" (optional manual approval)
  - Run migrations as one-off ECS task (before web deploy)
  - Update ECS web service task definition
  - Rolling deploy (zero downtime)
  - Update Celery workers
  - Slack notification

LESSON: Migration BEFORE web deploy.
Web containers come up expecting new schema → migration must be done.
```

---

**Q4. ECS Fargate kya hai — EC2 se kya different?**

```
EC2 (traditional):
→ Virtual machine rented from AWS
→ You: OS patch karo, Docker install karo, capacity manage karo
→ You pay whether app runs or not
→ Over/under provisioning problem

ECS on EC2:
→ ECS schedules containers on YOUR EC2 instances
→ Still manage EC2 fleet

ECS Fargate (tera choice):
→ No EC2 to manage!
→ Define: CPU + Memory per task (0.5 vCPU, 1GB)
→ AWS runs it somewhere, you don't care where
→ Pay per task per second (no idle EC2 cost)
→ Scale: 0 → 100 tasks in seconds

WHY FARGATE FOR NIROSKOS:
- Small team, no DevOps engineer
- Don't want to patch OS/Docker on EC2
- Variable traffic (weekend high, weekday low)
- Auto-scaling handles peaks without manual intervention
- Pay only for actual usage
```

---

**Q5. Zero-downtime deployment kaise achieve karte ho ECS pe?**

```
ECS ROLLING DEPLOYMENT:
ALB health check target: /health/ endpoint
Django view:

@api_view(["GET"])
def health_check(request):
    # Check DB + Redis
    try:
        with connection.cursor() as c:
            c.execute("SELECT 1")
        cache.get("health_check")
        return Response({"status": "ok"})
    except Exception as e:
        return Response({"status": "error"}, status=503)

DEPLOY FLOW:
1. New task starts → ECS waits for health check ✅
2. ALB adds new task to target group
3. ALB removes one old task from rotation
4. Old task: in-flight requests complete (drain timeout: 30s)
5. Old task terminated
6. Repeat until all tasks updated

CIRCUIT BREAKER:
If new task unhealthy (health check fails) →
ECS stops deployment → rolls back to old version
Automatic, no manual intervention needed.

RESULT: 0 seconds downtime during deploy.
```

---

**Q6. AWS IAM — tera app kaise AWS services access karta hai?**

```
ANSWER:
Never hardcode AWS keys in application code.

CORRECT APPROACH: IAM Roles

ECS Task Role:
→ ECS task ko IAM role attach karte hain
→ App code → boto3 → calls AWS → IAM checks task role → allowed/denied
→ No access key needed! Credentials automatically injected by AWS

TASK ROLE PERMISSIONS (niroskos-task-role):
{
  "Effect": "Allow",
  "Action": ["s3:GetObject", "s3:PutObject"],
  "Resource": "arn:aws:s3:::niroskos-media/*"
}

CODE:
import boto3
s3 = boto3.client("s3")   # no keys! uses task role automatically
s3.upload_file("invoice.pdf", "niroskos-media", "invoices/123.pdf")

PRINCIPLE OF LEAST PRIVILEGE:
Web task role → S3 (media), SQS (queue), SecretsManager (config)
NOT: full admin, not S3 buckets list, not other services

LOCAL DEV:
~/.aws/credentials mein personal IAM user keys
Dev keys ≠ prod keys (separate AWS accounts ideally)
```

---

**Q7. S3 file upload Django mein kaise karte ho?**

```python
# settings.py
DEFAULT_FILE_STORAGE = "storages.backends.s3boto3.S3Boto3Storage"
STATICFILES_STORAGE = "storages.backends.s3boto3.StaticS3Boto3Storage"
AWS_STORAGE_BUCKET_NAME = "niroskos-media"
AWS_S3_REGION_NAME = "ap-south-1"
AWS_S3_FILE_OVERWRITE = False
AWS_DEFAULT_ACL = None   # bucket policy controls access
# No AWS keys needed → uses ECS task role

# model.py
class TourImage(models.Model):
    tour = models.ForeignKey(Tour, on_delete=models.CASCADE)
    image = models.ImageField(upload_to="tours/images/")   # → S3!
    thumbnail = models.ImageField(upload_to="tours/thumbs/")

# views.py — presigned URL (direct browser upload)
import boto3

def get_upload_url(request):
    s3 = boto3.client("s3")
    key = f"uploads/user-{request.user.id}/{uuid4()}.jpg"

    # Generate presigned URL → browser uploads directly to S3
    # (doesn't go through Django server → fast, saves bandwidth)
    url = s3.generate_presigned_post(
        Bucket="niroskos-media",
        Key=key,
        Fields={"Content-Type": "image/jpeg"},
        Conditions=[
            {"Content-Type": "image/jpeg"},
            ["content-length-range", 1, 5*1024*1024],  # max 5MB
        ],
        ExpiresIn=300   # 5 minutes to upload
    )
    return JsonResponse({"upload_url": url, "key": key})
```

---

**Q8. Docker layer caching — CI mein kaise optimize kiya?**

```
PROBLEM:
Every CI run → full Docker build → 10 minutes
Wasted time, wasted money

SOLUTION: GitHub Actions cache + layer ordering

# Dockerfile layer order matters:
COPY requirements.txt .          # changes rarely
RUN pip install -r requirements.txt  # cached if requirements.txt same
COPY . .                         # changes every commit (but cached layers above)

# GitHub Actions:
- uses: docker/build-push-action@v5
  with:
    cache-from: type=gha      # use GitHub Actions cache
    cache-to: type=gha,mode=max

RESULT:
First build: 10 minutes (no cache)
Code change only: 2 minutes (requirements layer cached)
No code change: 30 seconds (all layers cached)

SAVINGS (30 deployments/month):
10min → 2min = 4 hours saved
GitHub Actions minutes cost: real money
```

---

**Q9. Log-based alerting kaise setup kiya?**

```
SETUP (CloudWatch):
1. Log Group: /ecs/niroskos-web

2. Metric Filter:
   Pattern: [level="ERROR"]
   Metric: ErrorCount
   Namespace: Niroskos/Application

3. CloudWatch Alarm:
   Metric: ErrorCount
   Threshold: > 5 errors per minute
   For: 2 consecutive minutes
   Action: SNS → Lambda → Slack message

4. Slack message:
   "🚨 ERROR spike in niroskos-web
    5+ errors/min for 2 minutes
    CloudWatch link: [link]"

STRUCTURED LOGGING (JSON → parseable):
logger.error("SAP sync failed", extra={
    "invoice_id": 123,
    "error": str(e),
    "attempt": 2,
})
# CloudWatch Insights:
# fields @timestamp, invoice_id, error
# | filter level = "ERROR"
# | stats count() by invoice_id

RESULT: Know about prod errors in < 3 minutes.
Before: users report → check logs → 30 min to diagnose.
After: alert fires → direct link → structured data → 5 min.
```

---

**Q10. GitHub Actions secrets kaise manage karte ho?**

```
TYPES OF SECRETS:
1. Repository secrets (Settings → Secrets):
   AWS_ACCESS_KEY_ID
   AWS_SECRET_ACCESS_KEY
   SLACK_WEBHOOK_URL

2. Environment secrets (production environment):
   Extra protection: require reviewer approval
   Only available to "deploy" job with environment: production

3. Organization secrets (multi-repo):
   AWS keys shared across all repos in org

USAGE:
${{ secrets.AWS_ACCESS_KEY_ID }}   # in workflow YAML
→ Masked in logs (shown as ***)
→ Cannot be read back, only used

BEST PRACTICES:
✅ Separate AWS IAM user for CI (not your personal keys)
✅ Minimal permissions (ECR push + ECS deploy only)
✅ Rotate quarterly
✅ Use OIDC instead of long-lived keys (most secure):
   AWS OIDC → GitHub token → temporary credentials
   No stored secret key at all!
```

---

**Q11. Docker health check kya hai?**

```
DOCKER HEALTHCHECK:
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
  CMD curl -f http://localhost:8000/health/ || exit 1

WHAT IT DOES:
Every 30s: curl /health/
If fails 3 times → container marked UNHEALTHY
Docker Compose / ECS → restart or remove unhealthy container

DJANGO HEALTH ENDPOINT:
@api_view(["GET"])
@permission_classes([AllowAny])
def health(request):
    checks = {}
    status_code = 200

    # DB check
    try:
        with connection.cursor() as c:
            c.execute("SELECT 1")
        checks["db"] = "ok"
    except Exception as e:
        checks["db"] = str(e)
        status_code = 503

    # Redis check
    try:
        cache.set("health", "1", timeout=1)
        checks["redis"] = "ok"
    except Exception as e:
        checks["redis"] = str(e)
        status_code = 503

    return Response(checks, status=status_code)

ECS: ALB checks /health/ → unhealthy → removes from rotation
     → new task starts → health passes → added back
     Zero-downtime recovery on crashes.
```

---

## QUICK RECALL CARD

```
╔══════════════════════════════════════════════════════════════════╗
║         AWS · DOCKER · CI/CD RECALL CARD                        ║
╠══════════════════════════════════════════════════════════════════╣
║                                                                  ║
║  DOCKER                                                          ║
║  Container = isolated process (not VM, shares host kernel)       ║
║  Layer cache = COPY requirements BEFORE COPY . (freq change last)║
║  Multi-stage = builder stage (big) + final stage (small)        ║
║  Non-root user = security (adduser appuser)                     ║
║  Healthcheck = curl /health/ → ECS auto-restart on fail         ║
║  .dockerignore = .git, __pycache__, .env, tests/                ║
║  Compose = local stack (db + redis + web + celery + flower)     ║
║                                                                  ║
║  AWS (backend relevant)                                          ║
║  EC2  = VM (you manage)                                         ║
║  ECS Fargate = serverless containers (AWS manages)              ║
║  RDS  = managed PostgreSQL/MySQL                                ║
║  ElastiCache = managed Redis                                    ║
║  S3   = object storage (media, static, backups)                 ║
║  ECR  = private Docker registry                                 ║
║  ALB  = HTTP load balancer (routes to ECS tasks)               ║
║  IAM  = permissions (task role, no hardcoded keys!)            ║
║  SecretsManager = store DB password, API keys                   ║
║  CloudWatch = logs + metrics + alarms                           ║
║  SQS  = message queue (Topic 11)                               ║
║                                                                  ║
║  CI/CD (GitHub Actions)                                          ║
║  Job 1: test  → lint + typecheck + pytest (80% coverage)       ║
║  Job 2: build → Docker build + push to ECR (with cache)        ║
║  Job 3: deploy→ migrate → ECS web → ECS celery → Slack        ║
║  Secrets: Settings → Secrets (masked in logs)                  ║
║  Environment: production gate (optional manual approval)        ║
║                                                                  ║
║  DEPLOYMENT                                                      ║
║  Rolling deploy = new tasks up → health check → old tasks down  ║
║  Zero downtime = ALB drains in-flight before removing old task  ║
║  Circuit breaker = unhealthy new task → auto-rollback           ║
║  Migration = run BEFORE web deploy (one-off ECS task)          ║
║                                                                  ║
║  TERA RESUME:                                                    ║
║  Niroskos  → Docker + ECS Fargate + GitHub Actions + S3        ║
║  Youngman  → Docker + AWS deployment + CloudWatch logs          ║
║  Pattern   → IAM task role (no keys), Secrets Manager           ║
╚══════════════════════════════════════════════════════════════════╝
```

---

*Last updated: 2026-08-15 · PwC Interview 2026-08-18*
*Resume skills: AWS · Docker · ECS · CI/CD · GitHub Actions · CloudWatch*