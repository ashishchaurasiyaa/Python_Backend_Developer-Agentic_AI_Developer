# Deployment Decision Framework — Django vs FastAPI + AWS Service Choice

## Quick Concepts
- **Framework choice** = workload nature (CRUD vs Async, ERP vs AI) decide karta hai
- **Deployment choice** = traffic pattern, team size, budget, latency requirements
- **AWS me 5 compute options** = EC2, ECS Fargate, ECS EC2, EKS, Lambda — sab ke trade-offs alag
- **Premature optimization** = Lambda/EKS sirf real need par. Start with ECS Fargate (sweet spot)
- **TCO (Total Cost of Ownership)** = sirf hosting cost nahi — ops time, monitoring, debugging bhi count

---

## Decision Tree #1: Django vs FastAPI (Framework)

```
START
  │
  ├─ Admin panel chahiye out-of-box?
  │   YES → Django (Django Admin saves weeks)
  │
  ├─ Workload type?
  │   ├─ CRUD-heavy ERP/SaaS (form-driven) → Django + DRF
  │   ├─ AI/LLM/Streaming → FastAPI
  │   ├─ WebSocket/Real-time → FastAPI
  │   ├─ Microservice (small, focused) → FastAPI
  │   └─ Mixed (REST + occasional WS) → Either OK
  │
  ├─ Team size?
  │   ├─ Solo / 2-person → FastAPI (less boilerplate)
  │   └─ 5+ team → Django (conventions matter)
  │
  ├─ Expected RPS?
  │   ├─ < 1000 RPS → Either works
  │   ├─ 1000-10K RPS → FastAPI (async wins)
  │   └─ > 10K RPS → FastAPI + Lua/Go services
  │
  ├─ Database access pattern?
  │   ├─ Heavy ORM (joins, aggregates) → Django ORM more mature
  │   └─ Mostly raw SQL / simple → SQLAlchemy 2.0 (FastAPI) fine
  │
  └─ AI/Agentic features?
      ├─ Yes (LangGraph, MCP, RAG) → FastAPI (async-native)
      └─ No → Either fine
```

---

## Decision Tree #2: AWS Compute Service Choice

```
START
  │
  ├─ Traffic pattern?
  │   ├─ Spiky / Sporadic (< 1 req/min avg) → Lambda
  │   ├─ Steady (24/7 traffic) → ECS Fargate
  │   └─ Massive (1000+ pods, multi-team) → EKS
  │
  ├─ Cost sensitivity?
  │   ├─ Very low budget (< ₹5K/mo) → Single EC2 + Docker Compose
  │   ├─ Medium → ECS Fargate (no server mgmt)
  │   └─ High scale → ECS EC2 (cheaper at scale) OR EKS
  │
  ├─ Ops expertise?
  │   ├─ Minimal DevOps → Lambda OR Fargate
  │   ├─ Medium → Fargate
  │   └─ Full DevOps team → EKS
  │
  ├─ Latency requirements?
  │   ├─ < 100ms p99 → ECS Fargate (always warm)
  │   ├─ < 500ms p99 → Lambda (with provisioned concurrency)
  │   └─ > 1s OK → Lambda (cold starts OK)
  │
  ├─ Long-running connections (WebSocket, SSE)?
  │   ├─ Yes → ECS Fargate / EKS (NOT Lambda — 15min limit)
  │   └─ No → Any
  │
  └─ Need GPU (AI inference)?
      ├─ Yes → ECS EC2 (GPU instance) OR EKS with GPU node pool
      └─ No → Fargate fine
```

---

## Interview Questions & Answers

### Q1: Tum apne project ke liye Django use kar rahe ho ya FastAPI? Why?

**Answer Template (for YAM-like ERP):**

> "Maine **Django + DRF** choose kiya kyunki yeh project ek **ERP / CRUD-heavy** application hai — godowns, jobsites, inventory, quotations, invoices. Main reasons:
>
> 1. **Django Admin** out-of-box mil gaya — internal admin users data manage kar sakte hain bina extra UI banaye.
> 2. **Django ORM** ne `select_related` / `prefetch_related` se complex joins easy banaye (e.g., quotation → items → product → category).
> 3. **PostGIS integration** Django ke `django.contrib.gis` se native support — spatial queries (nearest godown, area within radius) simple.
> 4. **SimpleJWT, django-celery-beat, drf-spectacular** — pre-built ecosystem libraries ne weeks bachaye.
> 5. **Team familiarity** — backend devs Django jaante hain, ramp-up faster.
>
> **Agar yeh AI/streaming project hota** (LLM chat, RAG endpoint, real-time updates) to maine **FastAPI** choose kiya hota — async-native, streaming responses, WebSocket simpler, LangGraph/MCP ke saath ergonomic."

**Answer Template (for AI Agent project):**

> "Maine **FastAPI** choose kiya kyunki:
> 1. **Async-first** — LLM API calls (Claude, OpenAI) inherently I/O bound. Ek async worker hi 1000s concurrent streaming connections handle kar leta hai jabki Django ko har request pe thread chahiye.
> 2. **SSE/WebSocket native** — LLM token streaming, agent thought streaming directly `StreamingResponse` se kar sakte hain.
> 3. **Pydantic v2** — LLM structured outputs (Instructor library) ke saath seamless integration.
> 4. **Lightweight** — microservice as MCP server / agent service — Django ki heaviness yahan overkill thi.
> 5. **OpenAPI auto-gen** — frontend `openapi-typescript` se types directly generate kar leta hai."

---

### Q2: AWS pe deploy karne ke kya options hain? Tumne kya choose kiya aur why?

**Answer:**

**5 Main Options + When to Use:**

| Option | Best For | Cost | Ops Complexity | Tumhare ERP ke liye? |
|---|---|---|---|---|
| **EC2 + Docker Compose** | MVP, <500 users, dev/staging | ₹2-5K/mo | Low | ⚠️ Single point of failure |
| **ECS Fargate** ⭐ | Production CRUD/API, auto-scale | ₹15-30K/mo | Medium | ✅ Sweet spot |
| **ECS EC2** | High scale, cost optimization at scale | ₹10-20K/mo (50+ tasks) | Medium-High | ✅ When scaling |
| **EKS (Kubernetes)** | Multi-team, polyglot, advanced ops | ₹40K+/mo | High | ❌ Overkill |
| **Lambda + API Gateway** | Sporadic traffic, event-driven | Pay-per-use | Low | ❌ Not for CRUD ERP |

**Answer Template:**

> "Maine **ECS Fargate** choose kiya production ke liye kyunki:
>
> 1. **No server management** — Fargate me tasks define karke deploy karo, AWS scaling/patching handle karta hai. EC2 ki tarah SSH/Linux patches manage nahi karne.
>
> 2. **Granular auto-scaling** — Django web service (2-10 tasks based on CPU), Celery worker (2-20 tasks based on SQS queue depth) — independently scale ho sakte hain.
>
> 3. **Cost-effective for our scale** — 500-5000 users daily. EKS overkill hota (cluster fee + cognitive load), EC2 cheaper but ops time chahiye.
>
> 4. **AWS-native integration** — IAM roles via task role, Secrets Manager direct injection, CloudWatch logs auto, ECR + ECS native CI/CD pattern.
>
> 5. **Staging me single EC2 + Docker Compose** — saving cost on non-prod (~₹3K/mo).
>
> **Migration path defined:** Agar future me hum 50+ services + multi-team setup karte hain, to **EKS** migrate karenge. Abhi YAGNI."

---

### Q3: Single EC2 par sab kuch chala sakte ho — kyu chahiye yeh ECS/Fargate complexity?

**Answer:**
**Valid question, depends on scale.** Single EC2 fine hai jab:
- < 500 daily active users
- Downtime tolerable (1-2 hrs/month)
- Single developer / no team
- Dev/staging environment

**Single EC2 ke problems jab scale aata hai:**

| Problem | Single EC2 | ECS Fargate |
|---|---|---|
| **High availability** | Server down → 100% down | Multi-AZ tasks → no downtime |
| **Auto-scaling** | Manual EC2 launch | Automatic based on metrics |
| **Deployment downtime** | Restart needed (5-30s) | Rolling deploy (zero downtime) |
| **Rollback** | Manual SSH + git revert | `aws ecs update-service` with old image |
| **Patching/Updates** | Manual apt-get + reboot | Fargate auto-patches |
| **Container crashes** | Manual restart | Auto-restart by ECS |
| **Logs** | SSH karke `tail -f` | CloudWatch Logs centralized |
| **Secret rotation** | Manual update + restart | Secrets Manager rotation |
| **Resource isolation** | All services share resources | Each task has guaranteed CPU/mem |

**Cost comparison (rough):**

```
Single EC2 t3.medium (Docker Compose):
  EC2:        ₹2,500/mo
  EBS:          ₹200/mo  
  Total:      ~₹3,000/mo (but DB+Redis on same machine)

ECS Fargate production:
  2 × Django:  ₹3,500/mo
  Celery × 2:  ₹2,000/mo  
  Beat × 1:      ₹600/mo
  ALB:         ₹2,000/mo
  RDS db.t3.small (Multi-AZ): ₹6,000/mo
  ElastiCache: ₹1,200/mo
  CloudFront+S3: ₹500/mo
  Total:      ~₹16,000/mo
```

**Decision rule:**
- **Revenue/Users < critical** → Single EC2
- **Users complain about downtime** → Migrate to ECS Fargate
- **5+ services / multi-team** → Migrate to EKS

---

### Q4: Container orchestration: ECS vs EKS — kab kya?

**Answer:**

| Aspect | ECS (Elastic Container Service) | EKS (Elastic Kubernetes Service) |
|---|---|---|
| **Vendor lock-in** | AWS-only | Portable (Kubernetes standard) |
| **Learning curve** | Easy (AWS-native concepts) | Steep (K8s ecosystem) |
| **Control plane cost** | Free | $73/mo per cluster |
| **YAML complexity** | Simple JSON task defs | Many YAML files (Deployment, Service, Ingress...) |
| **Ecosystem** | AWS services tight integration | Helm charts, Operators, vast K8s ecosystem |
| **Multi-cloud** | ❌ AWS only | ✅ Same code on GKE/AKS |
| **Best for** | AWS-committed, simple deployments | Polyglot, multi-team, advanced features (Istio, Argo, KEDA) |
| **Auto-scaling** | Application Auto Scaling | HPA, VPA, KEDA, Cluster Autoscaler, Karpenter |

**When ECS Fargate wins:**
- Small-to-medium team (< 20 engineers)
- AWS-committed
- Standard 3-tier apps (web + worker + DB)
- Need to ship fast

**When EKS wins:**
- 50+ microservices
- Multi-cloud requirement
- Advanced features needed (service mesh, GitOps with ArgoCD)
- Need ecosystem (Operators for DB, Kafka, etc.)
- Hiring K8s-experienced engineers

**Hybrid approach:** EKS with Fargate profile = K8s API + serverless compute.

---

### Q5: Lambda kab use karein FastAPI/Django ke saath?

**Answer:**

**Lambda is GREAT for:**
- ✅ Webhook receivers (`POST /webhook/stripe`)
- ✅ S3 event triggers (image upload → resize → save)
- ✅ Scheduled jobs (EventBridge → Lambda → process)
- ✅ Lightweight APIs (< 100 req/min)
- ✅ Internal admin APIs (sporadic use)
- ✅ Cron alternative (no always-on cost)

**Lambda is BAD for:**
- ❌ High-throughput APIs (cold starts hurt p99 latency)
- ❌ Long-running tasks (15-min hard limit)
- ❌ WebSocket / SSE (use API Gateway WebSocket separately)
- ❌ Heavy frameworks (Django boot ~3-5s cold start)
- ❌ DB connection pooling (use RDS Proxy mandatory)
- ❌ Stateful operations
- ❌ Large dependencies (250MB unzipped limit)

**FastAPI on Lambda — Mangum:**
```python
from fastapi import FastAPI
from mangum import Mangum

app = FastAPI()
# ... routes

handler = Mangum(app, lifespan="off")  # Lambda handler
```

**Django on Lambda — Zappa / serverless-wsgi:**
```python
# zappa_settings.json
{
  "production": {
    "django_settings": "myapp.settings",
    "s3_bucket": "myapp-lambda-deploy",
    "runtime": "python3.12",
    "memory_size": 1024,
    "timeout_seconds": 30,
    "environment_variables": {...}
  }
}
```
```bash
zappa deploy production
zappa update production
```

**⚠️ Anti-pattern:** Putting entire Django ERP on Lambda. Cold starts + connection pool issues + heavy boot time. Use ECS Fargate instead.

**✅ Good pattern:** Hybrid — Django on ECS for main app, Lambda for specific async events:
```
Main app:     ECS Fargate (Django)
Webhooks:     Lambda + API Gateway
S3 triggers:  Lambda (file upload → thumbnail generation)
Cron jobs:    EventBridge + Lambda
```

---

### Q6: Production deployment ke liye DB kahan host karoge — RDS, Aurora, Self-managed?

**Answer:**

| Option | When to Use | Cost (db.t3.small Multi-AZ) | Ops |
|---|---|---|---|
| **RDS PostgreSQL** ⭐ | Default choice | ₹6,000/mo | Managed (patches, backups) |
| **Aurora PostgreSQL** | High RPS, multi-region | ₹10,000/mo | Best performance, costly |
| **Aurora Serverless v2** | Variable load, dev/staging | Pay-per-ACU | Auto-scaling |
| **RDS for PostgreSQL + RDS Proxy** | Lambda-heavy | RDS + ₹1500/mo proxy | Connection pooling managed |
| **Self-managed on EC2** | Cost-extreme, < 100 users | ₹2,000/mo (small instance) | Manual everything ❌ |

**Recommendation for ERP (Django + PostGIS):**
- **Production:** RDS PostgreSQL 15 Multi-AZ, db.t3.small to start, scale to db.m6g.large at growth
- **Staging:** RDS db.t3.micro single-AZ
- **Dev:** Local PostgreSQL in Docker

**Critical setup:**
```bash
# After RDS creation
psql -h <rds-endpoint> -U admin -d postgres
CREATE DATABASE myapp;
\c myapp
CREATE EXTENSION postgis;            # ⭐ For Django GIS
CREATE EXTENSION postgis_topology;
CREATE EXTENSION pg_trgm;             # For trigram fuzzy search
CREATE EXTENSION pg_stat_statements;  # Query performance
```

**Security:**
- ❌ Never `0.0.0.0/0` in security group
- ✅ Only allow from ECS task SG
- ✅ Enable encryption at rest
- ✅ Use AWS Secrets Manager for password
- ✅ Enable Performance Insights

---

### Q7: Frontend (React) deployment ka best approach kya hai?

**Answer:**

**3 Options:**

| Option | Cost | Performance | Best For |
|---|---|---|---|
| **S3 + CloudFront** ⭐ | ₹500/mo | 50ms global (edge cached) | SPA, default choice |
| **AWS Amplify** | ₹1500/mo | Excellent (CDN + CI/CD) | Want fully managed |
| **Nginx container on ECS** | ₹3000/mo | Single region | Avoid — overkill |
| **Vercel/Netlify** | Free-₹2000 | Excellent | If OK with non-AWS |

**Why S3 + CloudFront wins:**
1. **Cheapest** — pay only for storage + bandwidth (~₹100-500/mo)
2. **Global** — CloudFront edge locations cache files near users
3. **Scales infinitely** — no server to manage
4. **HTTPS free** via ACM
5. **SPA routing** — CloudFront 404 → index.html rewrite

**Full setup:**
```bash
# 1. Build
cd frontend
VITE_API_URL=https://api.yourapp.com npm run build

# 2. S3 sync (immutable assets — long cache)
aws s3 sync dist/ s3://myapp-frontend-prod/ \
  --delete \
  --cache-control "public, max-age=31536000, immutable" \
  --exclude "index.html"

# 3. index.html separate (no cache — always latest)
aws s3 cp dist/index.html s3://myapp-frontend-prod/index.html \
  --cache-control "public, max-age=0, must-revalidate"

# 4. CloudFront invalidation
aws cloudfront create-invalidation \
  --distribution-id E1234ABCD \
  --paths "/index.html"
```

**CloudFront config (SPA routing):**
```hcl
custom_error_response {
  error_code         = 404
  response_code      = 200
  response_page_path = "/index.html"   # React Router handle karega
}

custom_error_response {
  error_code         = 403
  response_code      = 200
  response_page_path = "/index.html"
}
```

---

### Q8: Multi-environment (dev/staging/prod) kaise manage karoge?

**Answer:**

**Account strategy:**

| Approach | Setup | Cost | Isolation |
|---|---|---|---|
| **Single AWS account, separate VPCs** ⭐ | Easy | Low | OK |
| **AWS Organizations + separate accounts** | Complex | Same | Best (security + billing) |

**Naming convention:**
```
Resources:
- myapp-dev-cluster        myapp-staging-cluster     myapp-prod-cluster
- myapp-dev-rds-postgres   myapp-staging-rds         myapp-prod-rds
- myapp-dev-uploads-bucket myapp-staging-uploads     myapp-prod-uploads
- api-dev.yourapp.com      api-staging.yourapp.com   api.yourapp.com
- app-dev.yourapp.com      app-staging.yourapp.com   app.yourapp.com
```

**Terraform workspaces / separate state:**
```hcl
# Recommended: Separate state files per env
# infra/environments/dev/main.tf
# infra/environments/staging/main.tf
# infra/environments/prod/main.tf

# Common modules in infra/modules/
module "ecs_app" {
  source = "../../modules/ecs_app"
  
  environment   = "prod"
  desired_count = 2
  cpu           = 1024
  memory        = 2048
}
```

**Terraform code structure:**
```
infra/
├── modules/
│   ├── ecs_app/
│   ├── rds/
│   ├── redis/
│   └── networking/
└── environments/
    ├── dev/
    │   ├── main.tf
    │   ├── terraform.tfvars
    │   └── backend.tf       # state in S3
    ├── staging/
    └── prod/
```

**Sizing per environment:**

| Resource | Dev | Staging | Prod |
|---|---|---|---|
| ECS task CPU/Mem | 256 / 512 | 512 / 1024 | 1024 / 2048 |
| Desired count | 1 | 1 | 2-10 (auto-scale) |
| RDS instance | db.t3.micro | db.t3.small | db.t3.small Multi-AZ |
| Redis | cache.t3.micro | cache.t3.micro | cache.t3.small |
| ALB | 1 (or share) | 1 | 1 |
| **Monthly cost** | ₹3K | ₹8K | ₹16-25K |

---

### Q9: Disaster recovery aur backup strategy kya hogi?

**Answer:**

**RTO/RPO targets:**
- **RTO (Recovery Time Objective)** = downtime tolerable. Most ERPs: 1-4 hours
- **RPO (Recovery Point Objective)** = data loss tolerable. Most ERPs: < 1 hour

**Backup strategy:**

| Component | Backup Method | Frequency | Retention |
|---|---|---|---|
| **RDS PostgreSQL** | Automated backups + PITR | Continuous | 7-30 days |
| **RDS** | Manual snapshots before major release | Per release | 90 days |
| **S3 uploads** | Versioning + lifecycle | Real-time | 1 year (then Glacier) |
| **S3 frontend** | Versioning | Per deploy | 30 days |
| **Terraform state** | S3 with versioning + DynamoDB lock | Real-time | Forever |
| **ECR images** | Image tags + lifecycle policy | Per build | Last 50 |
| **Secrets** | Secrets Manager auto-backup | Real-time | Managed by AWS |

**RDS PITR (Point-in-Time Recovery):**
```bash
# Restore to any point in last 7 days
aws rds restore-db-instance-to-point-in-time \
  --source-db-instance-identifier myapp-postgres-prod \
  --target-db-instance-identifier myapp-postgres-restored \
  --restore-time "2024-01-15T03:00:00Z"
```

**Multi-region strategy (advanced):**
```
Primary region:    ap-south-1 (Mumbai)
DR region:         ap-southeast-1 (Singapore)

- RDS cross-region read replica
- S3 cross-region replication
- Route 53 health check + failover routing
- DR runbook documented
```

**Disaster recovery runbook (document):**
```markdown
1. RDS down (Mumbai)?
   - Promote read replica in Singapore
   - Update Route 53 to Singapore ALB
   - Estimated RTO: 15 min, RPO: < 5 min

2. ECS service unable to deploy?
   - Rollback: aws ecs update-service --task-definition <previous-arn>
   - Estimated RTO: 5 min

3. CloudFront down?
   - Update Route 53 to S3 direct (fallback config)
   - Estimated RTO: 5 min

4. S3 data accidentally deleted?
   - S3 versioning → restore previous version
   - Estimated RPO: 0 (versioned)
```

---

### Q10: CI/CD pipeline strategy kya hogi? Branch model + deployment flow?

**Answer:**

**Branching strategy (GitHub Flow + protected branches):**
```
main          ──●──────●──────●─── (production)
                │      │      │
release/v1.2  ●─┘      │      │     (release candidate, staging)
                       │      │
develop       ●────────●──────●─── (integration, auto-deploy to dev)
                       │      │
feature/abc   ●────────┘      │     (feature branch — PR to develop)
feature/xyz   ●───────────────┘
```

**Pipeline flow:**
```
1. Developer pushes feature branch
   ↓
2. PR to develop
   ↓ (GitHub Actions)
3. Run tests, lint, type check
   ↓ (if pass)
4. Merge to develop → auto-deploy to DEV environment
   ↓
5. PR develop → release/v1.2
   ↓ (GitHub Actions)
6. Auto-deploy to STAGING
   ↓ (manual QA)
7. PR release/v1.2 → main
   ↓ (GitHub Actions, manual approval required)
8. Deploy to PRODUCTION
   ↓
9. Tag release v1.2.0
```

**GitHub Actions workflows:**
```
.github/workflows/
├── pr-checks.yml          # Run on PR — tests + lint
├── deploy-dev.yml         # Run on push to develop
├── deploy-staging.yml     # Run on push to release/*
├── deploy-prod.yml        # Run on push to main (manual approval)
├── rollback.yml           # Manual workflow_dispatch
└── nightly.yml            # Cron: dependency scan, DB backup test
```

**Production deploy with manual approval:**
```yaml
# .github/workflows/deploy-prod.yml
jobs:
  deploy:
    environment:
      name: production
      url: https://api.yourapp.com
    # ⭐ environment with required reviewers
    runs-on: ubuntu-latest
    steps:
      - name: Deploy
        run: # ... ECS update
```

GitHub Settings → Environments → production → Required reviewers (2 people)

**Rollback strategy:**
```yaml
# .github/workflows/rollback.yml
on:
  workflow_dispatch:
    inputs:
      task_def_revision:
        description: "Task definition revision to rollback to"
        required: true

jobs:
  rollback:
    runs-on: ubuntu-latest
    steps:
      - run: |
          aws ecs update-service --cluster prod \
            --service django-web \
            --task-definition myapp-django:${{ inputs.task_def_revision }}
```

---

## Decision Matrix — Tumhare Specific Project ke Liye

### YAM-like ERP Project (Django + DRF + React)

```
Framework:        Django + DRF ✅ (CRUD-heavy, admin panel needed)
Production:       AWS ECS Fargate ✅ (sweet spot for medium scale)
Database:         RDS PostgreSQL 15 + PostGIS, Multi-AZ ✅
Cache:            ElastiCache Redis ✅
Background:       Celery + django-celery-beat ✅
Storage:          S3 + CloudFront ✅
Frontend:         S3 + CloudFront ✅ (static React build)
CI/CD:            GitHub Actions + OIDC ✅
Monitoring:       CloudWatch + Sentry + structlog ✅
Cost (prod):      ~₹16-25K/mo
Cost (staging):   ~₹3K/mo (single EC2)

Alternative considered:
- EKS: Overkill for team size
- Single EC2: Not HA, manual ops
- Aurora: Costlier, no need for Aurora-specific features yet
- Lambda: Wrong fit for ERP CRUD
```

### AI Agent Project (FastAPI + LangGraph + RAG)

```
Framework:        FastAPI ✅ (async-native, streaming)
Production:       AWS ECS Fargate ✅
Database:         RDS PostgreSQL + pgvector ✅
Cache:            ElastiCache Redis ✅
Background:       ARQ ✅ (async-native, lightweight)
Vector DB:        pgvector (or Pinecone if scale > 100M vectors)
Storage:          S3 ✅
Frontend:         S3 + CloudFront ✅
LLM:              AWS Bedrock (Claude) or direct Anthropic API
Cost (prod):      ~₹20-40K/mo (LLM API costs dominate)

Alternative considered:
- Lambda for FastAPI: Cold starts hurt streaming UX
- EKS: Overkill
- Django: Async limited, streaming awkward
```

---

## Final Recommendation Cheat Sheet

| Project Type | Framework | Compute | DB |
|---|---|---|---|
| CRUD ERP / SaaS | Django + DRF | ECS Fargate | RDS Postgres |
| AI Agent / RAG | FastAPI | ECS Fargate | RDS + pgvector |
| Microservice (single endpoint) | FastAPI | Lambda + API Gateway | DynamoDB / RDS Proxy |
| Real-time chat | FastAPI | ECS Fargate (NOT Lambda) | RDS + Redis |
| Webhooks / events | FastAPI | Lambda | DynamoDB |
| Internal admin | Django (Admin) | ECS Fargate (small task) | RDS |
| Streaming AI / LLM proxy | FastAPI | ECS Fargate | Redis only |
| Massive scale (100K+ RPS) | FastAPI + Go services | EKS | Aurora |
