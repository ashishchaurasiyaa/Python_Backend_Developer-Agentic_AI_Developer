# Design Multi-Tenant SaaS Platform — HLD

## WHAT

Multi-tenancy = **one software instance serves multiple customers (tenants)** with data isolation. Each tenant thinks they have their own private system.

Examples: Salesforce, Slack, GitHub, any B2B SaaS

---

## Requirements

### Functional
- Organizations (tenants) sign up independently
- Each tenant has users, data, settings isolated from others
- Tenant-specific: custom domain, branding, feature flags
- Admin of one tenant cannot access another's data
- Billing per tenant (usage-based or seat-based)

### Non-Functional
- 10,000 tenants, avg 50 users/tenant = 500,000 users total
- Data isolation: no cross-tenant data leaks (critical!)
- 99.9% availability per tenant
- Custom domain: `tenant1.app.com` or `app.tenant1.com`
- Horizontal scaling

---

## Tenancy Models — 3 Options

### Model 1: Silo (Separate DB per Tenant)

```
Tenant A → DB-A
Tenant B → DB-B
Tenant C → DB-C

Pros:
  ✅ Complete isolation (no data leak possible)
  ✅ Per-tenant backup, scaling, compliance
  ✅ Custom DB config per tenant (GDPR: EU tenant → EU DB)
Cons:
  ❌ Expensive (N databases for N tenants)
  ❌ Hard to query across tenants (analytics)
  ❌ Schema migrations are painful (N times)
Use for: Enterprise customers with strict compliance (banking, healthcare)
```

### Model 2: Shared DB, Separate Schema

```
Database "saas_prod"
  ├── schema "tenant_a" → users, posts, settings (tenant A's tables)
  ├── schema "tenant_b" → users, posts, settings (tenant B's tables)
  └── schema "tenant_c" → users, posts, settings

Pros:
  ✅ Moderate isolation
  ✅ Cheaper than full DB per tenant
Cons:
  ❌ Schema migrations still complex (N schemas)
  ❌ Schema limit in PostgreSQL (~8000 schemas)
Use for: Mid-sized SaaS, dozens to hundreds of tenants
```

### Model 3: Shared DB, Shared Schema (tenant_id column)

```
Table "posts":
  id | tenant_id | user_id | content | created_at
   1 |    t-abc  |   u-1   |   ...   |  2025-05-20
   2 |    t-xyz  |   u-5   |   ...   |  2025-05-20

Pros:
  ✅ Cheapest — one DB for all tenants
  ✅ Easy analytics across tenants
  ✅ One schema to migrate
Cons:
  ❌ Must add tenant_id to EVERY query (risk of forgetting = data leak!)
  ❌ One noisy tenant can affect others (resource contention)
  ❌ Harder compliance (data physically mixed)
Use for: Startups, thousands of small tenants
```

### Hybrid (Most Production SaaS)

```
Small tenants  → Shared DB (Model 3)
Large tenants  → Dedicated DB (Model 1)
                 (Enterprise tier with SLA)
```

---

## Core Architecture

```
                    ┌──────────────────────────────┐
                    │  Custom Domain Routing        │
                    │  tenant-a.app.com → tenant-a  │
                    │  tenant-b.app.com → tenant-b  │
                    └───────────────┬──────────────┘
                                    │
                    ┌───────────────▼──────────────┐
                    │  API Gateway                  │
                    │  - Tenant Resolution          │
                    │  - Auth (JWT with tenant_id)  │
                    │  - Rate limiting per tenant   │
                    └───────────────┬──────────────┘
                                    │
              ┌─────────────────────┼──────────────────────┐
              │                     │                      │
   ┌──────────▼────────┐  ┌─────────▼────────┐  ┌─────────▼───────┐
   │  Auth Service     │  │  Core API         │  │  Billing Service│
   │  (tenant-scoped)  │  │  Services         │  │  (per tenant)   │
   └──────────┬────────┘  └─────────┬────────┘  └─────────────────┘
              │                     │
   ┌──────────▼─────────────────────▼──────────┐
   │  Data Layer                                │
   │  Shared Pool DB (small tenants)            │
   │  Dedicated DBs (enterprise tenants)        │
   └────────────────────────────────────────────┘
```

---

## Tenant Isolation in Code (Shared Schema)

```python
from fastapi import FastAPI, Depends, HTTPException, Request
from sqlalchemy.orm import Session
import jwt

app = FastAPI()

# ── Tenant context ─────────────────────────────────────────────────────────

def get_tenant_id(request: Request) -> str:
    """Extract tenant from JWT or subdomain."""
    # Method 1: From JWT payload
    token   = request.headers.get("Authorization", "").removeprefix("Bearer ")
    payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
    return payload["tenant_id"]

    # Method 2: From subdomain
    # host = request.headers.get("host", "")
    # tenant_slug = host.split(".")[0]   # "acme.app.com" → "acme"
    # return lookup_tenant_id(tenant_slug)


# ── Database session with tenant filter ────────────────────────────────────

class TenantSession:
    """
    Database session that automatically adds tenant_id filter.
    This prevents cross-tenant data access — critical for isolation.
    """
    def __init__(self, db: Session, tenant_id: str):
        self.db        = db
        self.tenant_id = tenant_id
    
    def query(self, model):
        """All queries automatically scoped to current tenant."""
        return self.db.query(model).filter(model.tenant_id == self.tenant_id)
    
    def add(self, obj):
        """Automatically set tenant_id on new objects."""
        obj.tenant_id = self.tenant_id
        return self.db.add(obj)


def get_tenant_db(
    db: Session        = Depends(get_db),
    tenant_id: str     = Depends(get_tenant_id),
) -> TenantSession:
    return TenantSession(db, tenant_id)


# ── Endpoints — always use TenantSession ────────────────────────────────────

@app.get("/posts")
def list_posts(tenant_db: TenantSession = Depends(get_tenant_db)):
    # No risk of cross-tenant data — filter applied automatically
    return tenant_db.query(Post).order_by(Post.created_at.desc()).all()


@app.post("/posts")
def create_post(body: PostCreate, tenant_db: TenantSession = Depends(get_tenant_db)):
    post = Post(content=body.content)
    tenant_db.add(post)   # tenant_id auto-set
    tenant_db.db.commit()
    return post
```

---

## Database Schema

```sql
-- Tenant registry
CREATE TABLE tenants (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    slug         VARCHAR(63) UNIQUE NOT NULL,   -- subdomain: "acme"
    name         VARCHAR(255) NOT NULL,
    plan         TEXT DEFAULT 'starter',        -- 'starter', 'pro', 'enterprise'
    db_pool      TEXT DEFAULT 'shared',         -- 'shared' or 'dedicated'
    custom_domain TEXT,                         -- 'app.acme.com'
    settings     JSONB DEFAULT '{}',
    created_at   TIMESTAMPTZ DEFAULT NOW()
);

-- All tenant data tables have tenant_id FK + index
CREATE TABLE posts (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id   UUID NOT NULL REFERENCES tenants(id),
    user_id     UUID NOT NULL,
    content     TEXT,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);
-- CRITICAL: index on tenant_id for all tenant-scoped tables
CREATE INDEX idx_posts_tenant ON posts(tenant_id, created_at DESC);

-- Tenant users
CREATE TABLE users (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id   UUID NOT NULL REFERENCES tenants(id),
    email       VARCHAR(255) NOT NULL,
    role        TEXT DEFAULT 'member',
    UNIQUE (tenant_id, email)   -- email unique WITHIN tenant
);
```

---

## Feature Flags per Tenant

```python
import json
import redis

r = redis.Redis()

class TenantFeatureFlags:
    """Control which features each tenant can access."""
    
    def __init__(self, tenant_id: str):
        self.tenant_id = tenant_id
        self._flags: dict | None = None
    
    def _load(self) -> dict:
        cached = r.get(f"features:{self.tenant_id}")
        if cached:
            return json.loads(cached)
        flags = db.get_tenant_settings(self.tenant_id).get("features", {})
        r.setex(f"features:{self.tenant_id}", 300, json.dumps(flags))
        return flags
    
    def is_enabled(self, feature: str) -> bool:
        flags = self._load()
        return flags.get(feature, False)

# Usage in API endpoint
@app.post("/llm/generate")
def generate_text(request, tenant_db, features=Depends(get_feature_flags)):
    if not features.is_enabled("llm_generation"):
        raise HTTPException(403, "LLM generation not available on your plan")
    # ...proceed
```

---

## Tenant-Specific Rate Limiting

```python
class TenantRateLimiter:
    """Different rate limits per plan tier."""
    
    PLAN_LIMITS = {
        "starter":    {"api_calls": 100,   "llm_tokens": 10_000},
        "pro":        {"api_calls": 1_000,  "llm_tokens": 100_000},
        "enterprise": {"api_calls": 100_000,"llm_tokens": 10_000_000},
    }
    
    def check_limit(self, tenant_id: str, plan: str, resource: str) -> bool:
        limit  = self.PLAN_LIMITS[plan][resource]
        key    = f"rl:{tenant_id}:{resource}:{int(time.time())//60}"   # per minute
        count  = r.incr(key)
        r.expire(key, 60)
        return count <= limit
```

---

## Billing Integration

```python
# Usage-based billing: track per tenant
async def track_usage(tenant_id: str, resource: str, amount: float):
    """Track resource usage for billing."""
    month_key = datetime.now().strftime("%Y-%m")
    await r.incrbyfloat(f"usage:{tenant_id}:{resource}:{month_key}", amount)

# Monthly: flush to billing system (Stripe)
async def generate_invoice(tenant_id: str):
    month = datetime.now().strftime("%Y-%m")
    llm_tokens = float(r.get(f"usage:{tenant_id}:llm_tokens:{month}") or 0)
    api_calls  = float(r.get(f"usage:{tenant_id}:api_calls:{month}") or 0)
    
    amount_usd = (llm_tokens / 1_000_000 * 0.50) + (api_calls * 0.0001)
    await stripe.create_invoice(tenant_id, amount_usd, month)
```

---

## Interview Q&A

**Q: How do you prevent cross-tenant data leaks?**
A: (1) tenant_id on every table + indexed (2) TenantSession wrapper that auto-filters all queries (3) JWT includes tenant_id — backend validates (4) Row-level Security in PostgreSQL (5) Comprehensive tests with 2 tenants verifying isolation.

**Q: When to use separate DB per tenant vs shared schema?**
A: Shared schema: startups, 100s-1000s of small tenants, cost-sensitive. Separate DB: enterprise customers, strict compliance (GDPR, HIPAA), large tenants. Hybrid: most production SaaS.

**Q: How do you handle schema migrations across tenants?**
A: Shared schema: one migration for all (easy). Separate schemas: run migration per schema (use Alembic with multi-schema support). Key: migrations must be backward-compatible (add columns, don't rename/drop).

**Q: How do you handle noisy neighbor problem?**
A: Per-tenant rate limiting. Separate DB/resources for high-usage tenants. Monitor per-tenant resource consumption. Auto-upgrade noisy free-tier tenants or throttle them.
