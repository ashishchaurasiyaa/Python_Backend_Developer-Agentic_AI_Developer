# Lecture 1 — Practical Hands-On: Architecting a System

> **Theory file:** [01_What_is_Software_Architecture.md](01_What_is_Software_Architecture.md)
>
> Yeh practical companion file hai. Theory padhne ke baad yahan **hands-on** karenge.

---

## 🎯 Is Practical Mein Kya Karenge?

1. **Architecturally Significant Requirements (ASRs)** identify karna
2. **Real SaaS system** ka architecture banayenge — from scratch
3. **4 elements (Components, Connectors, Configuration, Constraints)** code mein dekhna
4. **Folder structure** different architecture styles ke liye
5. **Architecture diagram** Mermaid se banayenge
6. **Infrastructure as Code (IaC)** ka introduction
7. **Real architecture checklist** banayenge

---

## 1. Theory Recap — Quick Reference

```
Software Architecture =
    Components + Connectors + Configuration + Constraints
                    +
        High-level decisions about
        WHY they exist & HOW they interact
```

**5 Quality dials (jo har architecture mein tune karne hain):**
- 📈 Scalability
- ⚡ Performance
- ✅ Availability
- 🔒 Security
- 🔧 Maintainability

---

## 2. ASRs — Architecturally Significant Requirements

### Theory Deep Dive

Sirf functional requirements (kya karna hai) se architecture nahi banti. **ASRs** woh requirements hain jo **structurally significant** hain.

**ASR ke 4 characteristics:**

1. **Quality attribute related** (NFR)
2. **High business impact** if violated
3. **High effort/cost to change** later
4. **Cross-cutting concern** (multiple components affect karta hai)

### Hands-on Exercise — Identify ASRs

Imagine ek **B2B SaaS analytics platform** bana rahe ho. Yeh **stakeholder requirements** list hain:

```
1. "Users login karke dashboards dekh sakte hain"
2. "System 100K concurrent users handle kare"
3. "Page load < 2 seconds rakhna hai"
4. "Multi-tenant isolation hona chahiye (tenant ka data leak na ho)"
5. "Pricing in INR, USD, EUR support karein"
6. "GDPR compliant rehna hai"
7. "Mobile responsive dashboards"
8. "99.95% uptime guaranteed"
9. "Daily data refresh 6 AM IST pe"
10. "Custom branding support karein (white-label)"
```

**Aapka task:** Inko categorize karein:

```
Functional Requirements (features):    ASRs (architecturally significant):
- 1, 5, 7, 9, 10                       - 2, 3, 4, 6, 8
```

**Why these are ASRs:**

| # | Requirement | Why ASR |
|---|---|---|
| 2 | 100K concurrent users | Drives whole scaling approach (horizontal scaling, stateless services) |
| 3 | < 2s page load | Drives caching strategy, CDN, DB indexing |
| 4 | Multi-tenant isolation | Drives data partitioning (shared DB w/ tenant_id vs DB-per-tenant) |
| 6 | GDPR compliance | Drives data residency, encryption, audit logs, deletion APIs |
| 8 | 99.95% uptime | Drives redundancy, multi-AZ deployment, failover strategy |

### Practical Template — ASR Identification

```markdown
## ASR Worksheet

For each requirement, ask:

[ ] Is it a Quality Attribute? (perf/security/scale/availability)
[ ] Would changing it require major refactoring?
[ ] Does it affect multiple components?
[ ] High business cost if violated?

If 2+ checkboxes → it's an ASR. Document it!
```

---

## 3. Hands-on: Architect a Real SaaS System

### The Problem

> **"Build me a SaaS analytics platform jo charge karta hai per user per month."**

### Step 1 — Define ASRs

```
ASRs:
- Multi-tenant (1000+ tenants)
- 100K concurrent users at peak
- p95 latency < 500ms for dashboard load
- 99.95% uptime
- GDPR compliant (EU data in EU)
- Pay-as-you-go billing via Stripe
- Real-time analytics (data < 1 hour old)
```

### Step 2 — Identify Components

```python
# Architectural Components (Python pseudocode showing structure)

# ─── User-facing components ───
class WebFrontend:
    """React SPA — user dashboard"""
    pass

class MobileApp:
    """React Native app"""
    pass

# ─── Edge components ───
class CDN:
    """Cloudflare — static assets + edge caching"""
    pass

class APIGateway:
    """Kong/Envoy — auth, rate limiting, routing"""
    pass

# ─── Application services ───
class AuthService:
    """JWT + OAuth2"""
    pass

class TenantService:
    """Multi-tenant management"""
    pass

class DashboardService:
    """Render dashboards"""
    pass

class AnalyticsService:
    """Process analytics queries"""
    pass

class BillingService:
    """Stripe integration"""
    pass

# ─── Data tier ───
class PostgreSQL:
    """OLTP data — users, tenants, settings"""
    pass

class ClickHouse:
    """OLAP — analytical queries (billions of rows)"""
    pass

class Redis:
    """Cache + sessions"""
    pass

class S3:
    """Static assets, reports"""
    pass

# ─── Async layer ───
class Kafka:
    """Event streaming for analytics ingestion"""
    pass

class Celery:
    """Background jobs — report generation"""
    pass
```

### Step 3 — Define Connectors

```yaml
# How components talk to each other

Frontend ──HTTPS/REST──→ APIGateway
APIGateway ──HTTPS──→ AuthService
APIGateway ──HTTPS──→ DashboardService
DashboardService ──gRPC──→ AnalyticsService
AnalyticsService ──ClickHouse Protocol──→ ClickHouse
AllServices ──Redis Protocol──→ Redis  # cache + sessions
DataIngestion ──Kafka──→ Topics ──Kafka──→ ClickHouse Consumer
BillingService ──HTTPS──→ Stripe API
ReportGeneration ──Celery Tasks──→ Background Workers
```

### Step 4 — Configuration (Runtime Behavior)

```yaml
# config/production.yaml
environment: production
region: ap-south-1

scaling:
  api_gateway:
    min_replicas: 3
    max_replicas: 20
    cpu_threshold: 70%

  dashboard_service:
    min_replicas: 5
    max_replicas: 50

database:
  postgresql:
    primary: pg-primary.internal:5432
    replicas:
      - pg-replica-1.internal:5432
      - pg-replica-2.internal:5432
    connection_pool_size: 50
    max_overflow: 20

  clickhouse:
    shards: 4
    replicas_per_shard: 2

cache:
  redis:
    mode: cluster
    nodes: 6
    ttl_default: 300

secrets:
  manager: vault
  rotation_days: 90
```

### Step 5 — Constraints

```markdown
## Architecture Constraints

### Performance
- p95 latency < 500ms for dashboard load
- Dashboard queries return in < 2 seconds

### Scale
- Support 1000 tenants × 100 users each = 100K concurrent
- Ingest 1B events/day to ClickHouse

### Availability
- 99.95% uptime (~22 min/month downtime budget)
- Multi-AZ deployment mandatory

### Security
- All data encrypted at rest (AES-256)
- TLS 1.3 for all communication
- Multi-tenant isolation (no cross-tenant data leak)
- OWASP Top 10 mitigated

### Compliance
- GDPR: EU customer data in eu-west-1
- DPDP: Indian customer data in ap-south-1
- SOC 2 Type II ready

### Cost
- Cloud bill < ₹15L/month at 1000 tenants
- Per-tenant unit economics positive

### Tech mandates
- Python 3.12 (team expertise)
- PostgreSQL (managed via RDS)
- Kubernetes for compute
```

### Step 6 — Architecture Diagram (Mermaid)

```mermaid
flowchart TB
    subgraph "Client Tier"
        Web[Web Frontend - React]
        Mobile[Mobile App - React Native]
    end

    subgraph "Edge"
        CDN[Cloudflare CDN]
        WAF[WAF + DDoS]
    end

    subgraph "API Gateway Layer"
        Gateway[Kong API Gateway]
    end

    subgraph "Application Services"
        Auth[Auth Service]
        Tenant[Tenant Service]
        Dashboard[Dashboard Service]
        Analytics[Analytics Service]
        Billing[Billing Service]
    end

    subgraph "Data Tier"
        Postgres[(PostgreSQL Primary)]
        PostgresR[(PG Replicas x2)]
        ClickHouse[(ClickHouse Cluster)]
        Redis[(Redis Cluster)]
        S3[S3 Storage]
    end

    subgraph "Async Layer"
        Kafka[Kafka Cluster]
        Celery[Celery Workers]
    end

    subgraph "External"
        Stripe[Stripe API]
    end

    Web -->|HTTPS| CDN
    Mobile -->|HTTPS| CDN
    CDN -->|cache miss| WAF
    WAF --> Gateway
    Gateway --> Auth
    Gateway --> Tenant
    Gateway --> Dashboard
    Gateway --> Billing

    Dashboard -->|gRPC| Analytics
    Analytics --> ClickHouse
    Analytics --> Redis

    Auth --> Postgres
    Tenant --> Postgres
    Postgres -.->|read| PostgresR

    Billing -->|HTTPS| Stripe

    Kafka --> Celery
    Celery --> S3
    Celery --> Postgres

    style Postgres fill:#336791
    style ClickHouse fill:#FFCC01
    style Redis fill:#DC382D
    style Kafka fill:#231F20,color:#fff
```

> **Tip:** Yeh Mermaid syntax markdown files mein directly render hota hai GitHub par. Save karke commit karo, GitHub par dekho.

---

## 4. Folder Structures for Different Architectures

### A. Monolithic (Layered)

```
saas_monolith/
├── pyproject.toml
├── alembic.ini
├── docker-compose.yml
├── src/
│   ├── presentation/        # Controllers, API endpoints
│   │   ├── api/
│   │   │   ├── auth.py
│   │   │   ├── dashboard.py
│   │   │   └── billing.py
│   │   └── middleware/
│   ├── application/         # Business logic / use cases
│   │   ├── auth_service.py
│   │   ├── dashboard_service.py
│   │   └── billing_service.py
│   ├── domain/              # Domain entities + interfaces
│   │   ├── entities/
│   │   │   ├── user.py
│   │   │   ├── tenant.py
│   │   │   └── subscription.py
│   │   └── interfaces/
│   │       ├── repositories.py
│   │       └── services.py
│   ├── infrastructure/      # External adapters
│   │   ├── database/
│   │   ├── stripe_client.py
│   │   ├── redis_client.py
│   │   └── email_client.py
│   └── main.py
├── tests/
└── migrations/
```

### B. Microservices

```
saas_microservices/
├── README.md
├── docker-compose.yml             # Local dev all services
├── kubernetes/                     # K8s manifests
│   ├── auth-service/
│   ├── dashboard-service/
│   └── ingress.yaml
├── services/
│   ├── auth-service/
│   │   ├── src/
│   │   ├── tests/
│   │   ├── Dockerfile
│   │   ├── pyproject.toml
│   │   └── README.md
│   ├── tenant-service/
│   │   └── ...
│   ├── dashboard-service/
│   │   └── ...
│   ├── analytics-service/
│   │   └── ...
│   └── billing-service/
│       └── ...
├── shared/                        # Shared libraries
│   ├── proto/                     # gRPC definitions
│   └── pylib/                     # Common Python utilities
└── infra/                         # Terraform
    ├── main.tf
    └── modules/
```

### C. Hexagonal (Clean Architecture)

```
hex_service/
├── src/
│   ├── domain/               # Pure business logic (no I/O)
│   │   ├── entities/
│   │   ├── value_objects/
│   │   └── ports/             # Interfaces (input + output)
│   │       ├── inbound/       # What can call us (API, CLI, ...)
│   │       └── outbound/      # What we depend on (DB, Email, ...)
│   ├── application/           # Use cases (orchestration)
│   │   └── use_cases/
│   └── adapters/              # Implementations of ports
│       ├── inbound/
│       │   ├── rest_api/
│       │   ├── grpc/
│       │   └── cli/
│       └── outbound/
│           ├── postgres_repo/
│           ├── stripe_client/
│           └── ses_email/
├── tests/
│   ├── unit/                   # Domain + use cases
│   ├── integration/            # Adapters
│   └── e2e/
└── main.py
```

> **Insight:** Folder structure architecture decisions ko **physically reflect** karta hai. Code base dekhke aapko architecture ka pata chal jana chahiye.

---

## 5. Practical — 4 Elements in Code

### Element 1: Components (Python Module Structure)

```python
# src/components/__init__.py
"""
Architectural components — each as a separate module.
Clear responsibility per component.
"""

# src/components/auth.py
from fastapi import APIRouter, Depends
from src.application.auth_service import AuthService

router = APIRouter(prefix="/auth")

@router.post("/login")
async def login(credentials: LoginRequest, svc: AuthService = Depends()):
    """Component: Auth — owns authentication concerns only."""
    return await svc.authenticate(credentials)


# src/components/dashboard.py
@router.get("/dashboard/{tenant_id}")
async def get_dashboard(tenant_id: str, svc: DashboardService = Depends()):
    """Component: Dashboard — owns rendering dashboards only."""
    return await svc.get_dashboard(tenant_id)
```

### Element 2: Connectors (Communication Patterns)

```python
# src/connectors/grpc_client.py — gRPC connector
import grpc
from generated import analytics_pb2_grpc

class AnalyticsGrpcConnector:
    """Connector: Dashboard → Analytics (gRPC)"""

    def __init__(self, host: str = "analytics-service:50051"):
        self.channel = grpc.aio.insecure_channel(host)
        self.stub = analytics_pb2_grpc.AnalyticsServiceStub(self.channel)

    async def query(self, request):
        return await self.stub.Query(request, timeout=5)


# src/connectors/kafka_producer.py — Kafka connector
from aiokafka import AIOKafkaProducer

class EventConnector:
    """Connector: Services → Kafka (async events)"""

    def __init__(self):
        self.producer = AIOKafkaProducer(
            bootstrap_servers="kafka:9092",
            value_serializer=lambda v: json.dumps(v).encode(),
        )

    async def publish(self, topic: str, event: dict):
        await self.producer.send_and_wait(topic, event)


# src/connectors/redis_cache.py — Cache connector
import redis.asyncio as aioredis

class CacheConnector:
    """Connector: All services → Redis (cache)"""

    def __init__(self):
        self.client = aioredis.from_url("redis://redis:6379")

    async def get(self, key: str):
        return await self.client.get(key)

    async def set(self, key: str, value: str, ttl: int = 300):
        await self.client.setex(key, ttl, value)
```

### Element 3: Configuration (Runtime Behavior)

```python
# src/config.py — Configuration loaded from env
from pydantic_settings import BaseSettings, SettingsConfigDict

class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")

    # Environment
    environment: str = "development"
    region: str = "ap-south-1"

    # Database
    db_primary_url: str
    db_replica_urls: list[str] = []
    db_pool_size: int = 50

    # Cache
    redis_url: str = "redis://localhost:6379"
    cache_ttl_default: int = 300

    # External
    stripe_secret_key: str
    stripe_webhook_secret: str

    # Scaling
    api_workers: int = 4
    background_workers: int = 8

    # Quality controls
    rate_limit_per_minute: int = 60
    request_timeout_seconds: int = 30
    circuit_breaker_threshold: int = 5

settings = AppSettings()
```

### Element 4: Constraints (Validation + Enforcement)

```python
# src/constraints/performance.py — Performance constraint enforcement
import time
import logging
from functools import wraps

PERFORMANCE_SLA_MS = 500   # constraint: p95 < 500ms

def enforce_sla(threshold_ms: int = PERFORMANCE_SLA_MS):
    """Decorator: log violations of performance SLA."""

    def decorator(fn):
        @wraps(fn)
        async def wrapper(*args, **kwargs):
            start = time.perf_counter()
            try:
                return await fn(*args, **kwargs)
            finally:
                duration_ms = (time.perf_counter() - start) * 1000
                if duration_ms > threshold_ms:
                    logging.warning(
                        f"SLA VIOLATION: {fn.__name__} took {duration_ms:.0f}ms (limit: {threshold_ms}ms)"
                    )
        return wrapper
    return decorator

# Usage
@router.get("/dashboard/{tenant_id}")
@enforce_sla(threshold_ms=500)
async def get_dashboard(tenant_id: str):
    ...


# src/constraints/multi_tenant.py — Multi-tenant isolation constraint
from fastapi import HTTPException, Depends

async def enforce_tenant_isolation(
    current_tenant: str = Depends(get_current_tenant),
    target_tenant: str = None,
):
    """Constraint: tenant can only access own data."""
    if target_tenant and target_tenant != current_tenant:
        raise HTTPException(403, f"Cross-tenant access denied")
```

---

## 6. Infrastructure as Code (IaC) — Architecture in Terraform

### Why IaC Matters

Architecture sirf code mein nahi rehni chahiye — **infrastructure** bhi declare karna chahiye. Terraform/Pulumi se infrastructure version-controlled ho jata hai.

### Example — Minimal SaaS Setup

```hcl
# infra/main.tf

terraform {
  required_version = ">= 1.5"
  backend "s3" {
    bucket = "acme-tfstate"
    key    = "saas/production.tfstate"
    region = "ap-south-1"
  }
}

provider "aws" {
  region = "ap-south-1"
}

# ─── VPC (network boundary) ───
module "vpc" {
  source = "terraform-aws-modules/vpc/aws"
  name   = "saas-prod-vpc"
  cidr   = "10.0.0.0/16"

  azs                = ["ap-south-1a", "ap-south-1b", "ap-south-1c"]
  private_subnets    = ["10.0.1.0/24", "10.0.2.0/24", "10.0.3.0/24"]
  public_subnets     = ["10.0.101.0/24", "10.0.102.0/24", "10.0.103.0/24"]
  enable_nat_gateway = true
  single_nat_gateway = false   # multi-AZ NAT for HA
}

# ─── Kubernetes (compute platform) ───
module "eks" {
  source  = "terraform-aws-modules/eks/aws"
  version = "~> 19.0"

  cluster_name    = "saas-prod"
  cluster_version = "1.29"

  vpc_id          = module.vpc.vpc_id
  subnet_ids      = module.vpc.private_subnets

  eks_managed_node_groups = {
    general = {
      desired_size = 5
      min_size     = 3
      max_size     = 20
      instance_types = ["m5.xlarge"]
    }
  }
}

# ─── PostgreSQL (RDS Multi-AZ for HA) ───
module "rds" {
  source  = "terraform-aws-modules/rds/aws"
  version = "~> 6.0"

  identifier             = "saas-prod-pg"
  engine                 = "postgres"
  engine_version         = "16.2"
  instance_class         = "db.r6g.xlarge"
  allocated_storage      = 500
  storage_encrypted      = true

  db_name                = "saas"
  username               = "saas_admin"
  manage_master_user_password = true

  multi_az               = true              # constraint: 99.95% uptime
  backup_retention_period = 7
  performance_insights_enabled = true

  vpc_security_group_ids = [aws_security_group.rds.id]
  db_subnet_group_name   = module.vpc.database_subnet_group
}

# ─── Redis (ElastiCache) ───
resource "aws_elasticache_replication_group" "redis" {
  replication_group_id = "saas-prod-redis"
  description          = "SaaS cache cluster"

  node_type            = "cache.r6g.large"
  num_cache_clusters   = 3                  # multi-AZ
  automatic_failover_enabled = true         # constraint: HA
  multi_az_enabled     = true
  engine_version       = "7.0"

  at_rest_encryption_enabled = true         # constraint: security
  transit_encryption_enabled = true
}

# ─── S3 (object storage) ───
resource "aws_s3_bucket" "reports" {
  bucket = "acme-saas-reports"
}

resource "aws_s3_bucket_server_side_encryption_configuration" "reports" {
  bucket = aws_s3_bucket.reports.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

# ─── CloudFront (CDN) ───
resource "aws_cloudfront_distribution" "static" {
  enabled = true

  origin {
    domain_name = aws_s3_bucket.reports.bucket_regional_domain_name
    origin_id   = "S3-reports"
  }

  default_cache_behavior {
    viewer_protocol_policy = "redirect-to-https"
    target_origin_id       = "S3-reports"
    cached_methods         = ["GET", "HEAD"]
    allowed_methods        = ["GET", "HEAD"]
  }
}

output "cluster_endpoint" {
  value = module.eks.cluster_endpoint
}

output "rds_endpoint" {
  value = module.rds.db_instance_endpoint
}
```

### Run It

```bash
cd infra/
terraform init
terraform plan
terraform apply
# Now infrastructure matches architecture decisions
```

> **Architecture decision** → **IaC code** → **Real infrastructure**. Full traceability!

---

## 7. Docker Compose for Local Architecture

Local development mein bhi architecture **declare karo** — `docker-compose.yml` se.

```yaml
# docker-compose.yml — Local equivalent of production architecture

version: '3.8'

services:
  # ─── App services ───
  auth-service:
    build: ./services/auth-service
    environment:
      DATABASE_URL: postgres://saas:saas@postgres:5432/saas
      REDIS_URL: redis://redis:6379/0
    ports: ["8001:8000"]
    depends_on: [postgres, redis]

  dashboard-service:
    build: ./services/dashboard-service
    environment:
      DATABASE_URL: postgres://saas:saas@postgres:5432/saas
      REDIS_URL: redis://redis:6379/0
      ANALYTICS_GRPC_HOST: analytics-service:50051
    ports: ["8002:8000"]
    depends_on: [postgres, redis, analytics-service]

  analytics-service:
    build: ./services/analytics-service
    environment:
      CLICKHOUSE_URL: clickhouse://clickhouse:8123/default
    ports: ["50051:50051"]
    depends_on: [clickhouse]

  # ─── Data tier ───
  postgres:
    image: postgres:16
    environment:
      POSTGRES_USER: saas
      POSTGRES_PASSWORD: saas
      POSTGRES_DB: saas
    volumes:
      - pgdata:/var/lib/postgresql/data
    ports: ["5432:5432"]

  clickhouse:
    image: clickhouse/clickhouse-server:24
    volumes:
      - chdata:/var/lib/clickhouse
    ports: ["8123:8123"]
    ulimits:
      nofile:
        soft: 262144
        hard: 262144

  redis:
    image: redis:7
    ports: ["6379:6379"]

  # ─── Async layer ───
  kafka:
    image: confluentinc/cp-kafka:7.6.0
    environment:
      KAFKA_PROCESS_ROLES: broker,controller
      # ... (kafka config)
    ports: ["9092:9092"]

  # ─── Observability ───
  prometheus:
    image: prom/prometheus
    ports: ["9090:9090"]
    volumes:
      - ./monitoring/prometheus.yml:/etc/prometheus/prometheus.yml

  grafana:
    image: grafana/grafana
    ports: ["3000:3000"]
    environment:
      GF_SECURITY_ADMIN_PASSWORD: admin

volumes:
  pgdata:
  chdata:
```

### Run It

```bash
docker-compose up -d
# Local architecture running on your laptop
# Same components as production!
```

---

## 8. Real Architecture Checklist

Yeh checklist ek **new project start** karne se pehle bharo:

```markdown
# Architecture Pre-Flight Checklist

## 1. Functional Requirements
- [ ] Core features documented?
- [ ] User personas defined?
- [ ] Success metrics defined?

## 2. Non-Functional Requirements (ASRs)
- [ ] Expected scale (users, RPS, data volume)?
- [ ] Latency targets (p50, p95, p99)?
- [ ] Availability target (99.9%, 99.95%, etc.)?
- [ ] Security/compliance requirements?
- [ ] Cost ceiling?

## 3. Constraints
- [ ] Tech stack mandates (e.g., must use Python)?
- [ ] Team expertise (what they know vs need to learn)?
- [ ] Existing systems to integrate with?
- [ ] Time-to-market deadline?
- [ ] Budget constraints?

## 4. Components Identification
- [ ] Major services/modules listed?
- [ ] Each component has single responsibility?
- [ ] No "god" components?

## 5. Connectors
- [ ] Sync vs async decided per integration?
- [ ] Protocols chosen (REST, gRPC, message queue)?
- [ ] Error handling strategy per connector?

## 6. Configuration
- [ ] Env-based config (12-factor app)?
- [ ] Secrets in vault (not in code)?
- [ ] Feature flags planned?

## 7. Constraints Enforcement
- [ ] How will SLA be measured?
- [ ] How will tenant isolation be enforced?
- [ ] How will security boundaries be checked?

## 8. Quality Attributes
- [ ] Caching strategy?
- [ ] Scaling strategy (vertical, horizontal, hybrid)?
- [ ] Failover strategy?
- [ ] Backup + DR plan?

## 9. Documentation
- [ ] ADR(s) for major decisions?
- [ ] C4 diagram (at least Level 1 + 2)?
- [ ] README explains how to run locally?
- [ ] API contracts documented?

## 10. Observability
- [ ] Logging strategy (structured logs)?
- [ ] Metrics to track (RED method: Rate, Errors, Duration)?
- [ ] Tracing (OpenTelemetry)?
- [ ] Alerting rules?

## 11. Deployment
- [ ] CI/CD pipeline?
- [ ] Rollback plan?
- [ ] Blue-green or canary deploy?
```

---

## 9. Common Mistakes (Real-World Failures)

### Mistake 1: No ASRs

```
❌ Problem: Started building without identifying ASRs.
❌ Result: 6 months in, realized DB can't handle expected scale.
❌ Cost: 3-month refactor.

✅ Fix: ASR workshop in first week. Document. Validate with stakeholders.
```

### Mistake 2: Tight Coupling

```python
# ❌ BAD — direct DB calls in dashboard component
class DashboardComponent:
    def render(self, tenant_id):
        # Direct PostgreSQL access — couples dashboard to DB schema!
        with psycopg.connect(...) as conn:
            data = conn.execute("SELECT ...").fetchall()
        return data

# ✅ GOOD — abstracted via repository
class DashboardComponent:
    def __init__(self, repo: DashboardRepository):
        self.repo = repo

    async def render(self, tenant_id):
        # Repository abstracts away DB details
        return await self.repo.get_dashboard_data(tenant_id)
```

### Mistake 3: No Boundaries

```yaml
# ❌ BAD — every service hits every DB directly
service-a → postgres
service-a → mysql
service-a → mongodb
service-b → postgres
service-b → mysql

# ✅ GOOD — each service owns its data
service-a → postgres-for-a (only)
service-b → mysql-for-b (only)
# Services communicate via APIs, not DB sharing
```

### Mistake 4: Over-engineering

```
❌ Real scenario at startup (10 employees, 100 users):
- 25 microservices
- Service mesh (Istio)
- 3 message brokers (Kafka, RabbitMQ, NATS)
- Custom monitoring system
- Multi-region deployment

❌ Result: 1 engineer spent 80% time on infra. Product velocity = 0.

✅ Fix: Monolith first. Split when team > 10 OR scale > 1M users.
```

---

## 10. Hands-on Exercise

### Exercise 1: Architect a Pizza Delivery App

You're tasked with architecting a pizza delivery app like Dominos.

**Given:**
- 1000 orders/hour at peak
- 500 active delivery agents
- 200 stores
- Real-time order tracking
- Indian market focus

**Your task:** Fill the following:

```markdown
## 1. ASRs

- ASR 1: ___________
- ASR 2: ___________
- ASR 3: ___________
- ASR 4: ___________
- ASR 5: ___________

## 2. Components (list 8-10)

1. ___________
2. ___________
...

## 3. Connectors (how do they communicate?)

- ___________ → ___________: ___________

## 4. Configuration (key runtime settings)

```yaml
___________
```

## 5. Constraints

- Performance: ___________
- Scale: ___________
- Availability: ___________
- Compliance: ___________

## 6. C4 Level 1 Diagram (Mermaid)

```mermaid
flowchart LR
    ...
```
```

**Sample solution skeleton:**

```markdown
## 1. ASRs
- Real-time tracking (GPS, websocket)
- < 5 second order placement
- 99.9% uptime during peak hours
- Indian DPDP compliance
- Handle 1000 RPS at peak

## 2. Components
1. Customer App (mobile)
2. Store Dashboard
3. Delivery Agent App
4. Order Service
5. Inventory Service
6. Payment Service (Stripe + UPI)
7. Notification Service (SMS + Push)
8. Tracking Service (real-time location)
9. Pricing Service
10. Admin Panel

## 3. Connectors
- Customer App → API Gateway: HTTPS REST
- API Gateway → Services: HTTP/gRPC
- Tracking Service → Customer App: WebSocket
- Order Service → Payment Service: HTTP
- Order Service → Notification: Kafka events
- Delivery Agent App → Tracking Service: WebSocket (GPS updates)

## 4. Configuration
```yaml
auto_scaling:
  order_service:
    min: 5
    max: 50

cache:
  redis: cluster mode

db:
  postgres: multi-AZ
```

## 5. Constraints
- Performance: Order placement < 5s
- Scale: 1000 orders/hour peak (= 0.28/sec, but bursty)
- Availability: 99.9% during dinner hours (7-10 PM)
- Compliance: India DPDP, no tracking minors

## 6. C4 Level 1
[Mermaid diagram showing system + external partners]
```

---

## 11. Real-World Architecture Decision Examples

### Decision 1: Database Choice for Multi-Tenant SaaS

**Context:** SaaS with 1000 tenants, varying sizes (10 users to 10K users).

**Options:**
1. Single DB, tenant_id column → simple, but noisy neighbor risk
2. DB-per-tenant → isolation, but 1000 DBs ops nightmare
3. Schema-per-tenant in single DB → middle ground

**Decision:** Schema-per-tenant for big tenants, shared DB for small ones (hybrid).

**Trade-offs:**
- ✅ Big tenants get isolation
- ✅ Small tenants don't waste resources
- ❌ Migration code more complex (must handle both)

### Decision 2: Sync vs Async for Order Placement

**Context:** Order placement needs to feel fast to user but involves: inventory check, payment, notification, fulfillment.

**Decision tree:**

```
User clicks "Place Order"
    ↓
1. SYNCHRONOUS (must complete before response):
   - Validate cart
   - Check inventory (atomic decrement)
   - Charge payment (Stripe)
   → Return order ID to user (< 2s)

2. ASYNCHRONOUS (after response):
   - Send confirmation email (Kafka → email worker)
   - Notify warehouse (Kafka → warehouse worker)
   - Update analytics (Kafka → analytics worker)
   - Send push notification
```

**Why this split?**
- User cares about: order confirmed + payment succeeded
- User doesn't care: when email arrives, when analytics updates
- Sync only what's essential. Everything else → async.

---

## 12. Tools & Cheatsheet

### Architecture Tools

| Tool | Use |
|---|---|
| [Mermaid](https://mermaid.js.org) | Diagrams in markdown (this lecture used it!) |
| [PlantUML](https://plantuml.com) | More detailed diagrams |
| [Draw.io](https://draw.io) | Free drag-drop |
| [Structurizr DSL](https://structurizr.com) | C4 diagrams as code |
| [Terraform](https://terraform.io) | Infrastructure as Code |
| [Pulumi](https://pulumi.com) | IaC in Python/TypeScript |
| [Docker Compose](https://docs.docker.com/compose/) | Local architecture |

### Decision Quick-Pick

```
Building new system?
  ↓
Start with monolith (modular, layered)
  ↓
Team > 10 people OR scale > 1M users?
  ↓ Yes
Split into 2-5 microservices on team boundaries
  ↓
Scale > 10M users?
  ↓ Yes
Cell-based architecture, multi-region, sharding
```

---

## 13. Summary

**Theory + Practical = Real Architecture Skill**

```
THEORY (Lecture 1):                  PRACTICAL (This file):
  • Definition of architecture        • ASRs identification
  • 4 elements                         • Real SaaS architect-up exercise
  • Goals                              • Folder structures per style
  • Impact on quality                  • Terraform IaC examples
  • Poor architecture risks            • Docker Compose local arch
                                       • Real architecture checklist
                                       • Common mistakes from production
```

### Action Items

1. ✅ **Do the pizza app exercise** (Exercise 1 above)
2. ✅ **Create your own architecture checklist** for current/next project
3. ✅ **Draw a Mermaid C4 Level 1** for any system you've worked on
4. ✅ **Identify 3 ASRs** for any product you use daily

---

## 14. Related Backend_Developer Resources

- [02_Year5+_Senior/01_System_Design/HLD_Theory/Udemy_MasteringSystemDesign/11_Blueprint.md](../../01_System_Design/HLD_Theory/Udemy_MasteringSystemDesign/11_Blueprint.md) — System design framework
- [01_Year3-4_Mid/05_Microservices/](../../../01_Year3-4_Mid/05_Microservices) — Microservices patterns
- [01_Year3-4_Mid/04_DevOps/07_terraform.md](../../../01_Year3-4_Mid/04_DevOps/07_terraform.md) — Terraform deep dive
- [01_Year3-4_Mid/04_DevOps/01_docker.md](../../../01_Year3-4_Mid/04_DevOps/01_docker.md) — Docker fundamentals
- [02_Year5+_Senior/01_System_Design/HLD_Problems/Design_Multi_Tenant_SaaS.md](../../01_System_Design/HLD_Problems/Design_Multi_Tenant_SaaS.md) — Multi-tenant SaaS HLD
