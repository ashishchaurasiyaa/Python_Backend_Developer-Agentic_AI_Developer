# Multi-Tenant SaaS API Platform — Starter

Spec: [../01_FastAPI_Multi_Tenant_SaaS.md](../01_FastAPI_Multi_Tenant_SaaS.md)

## What to build

A production-ready B2B SaaS API with multi-tenancy (shared schema + `tenant_id`), RBAC, Stripe billing, audit logs, async outbound webhooks, and API rate limiting.  Target: 10K tenants, 5K RPS, p99 < 200ms.

## How to run

```bash
# 1. Create and activate a virtual environment
python -m venv .venv && source .venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Start infrastructure (Postgres, Redis, RabbitMQ)
docker run -d --name pg -e POSTGRES_PASSWORD=dev -p 5432:5432 postgres:16
docker run -d --name redis -p 6379:6379 redis:7
docker run -d --name rabbit -p 5672:5672 rabbitmq:3

# 4. Copy and fill environment variables
cp .env.example .env   # create this file with DATABASE_URL, REDIS_URL, STRIPE_SECRET, etc.

# 5. Run the API
uvicorn main:app --reload
```

Open http://localhost:8000/docs for the auto-generated OpenAPI UI.

## Milestones (from spec)

- **Week 1** — Tenant + user models, JWT auth (RS256), tenant-context middleware, RLS setup
- **Week 2** — RBAC permissions, invite flow, Stripe subscription, webhook idempotency, quota enforcement
- **Week 3** — Celery tasks (email, outbound webhooks with backoff), audit logs, API keys, rate limiting
- **Week 4** — Health endpoints, Dockerize, AWS ECS/K8s deploy, Locust load test (5K RPS)

## Key patterns to implement

1. `tenant_id` injected into every ORM query via middleware + Postgres RLS as defense-in-depth.
2. JWT payload includes `tenant_id` + `role` + `permissions`; RS256 so microservices can verify without secret.
3. Refresh token rotation: each refresh issues new token and invalidates old one.
4. Stripe webhook idempotency: `Redis SET NX stripe:event:{event.id}`.
5. Outbound webhook retries with exponential backoff (1m, 2m, 4m, 8m, 16m).
