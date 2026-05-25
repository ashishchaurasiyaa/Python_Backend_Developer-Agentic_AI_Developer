# Multi-Tenant Architecture in FastAPI

> **Interview angle:** "SaaS app design karo jisme 1000 companies hain — data isolation kaise karoge?"

---

## 1. What is Multi-Tenancy?

**Single app instance serving multiple customers (tenants)** with strict data isolation.

Examples: Slack workspaces, Shopify stores, Stripe accounts, Notion teams.

**Each tenant:**
- Has separate users
- Has own data
- Can't see other tenants' data
- Has own settings, billing, limits

---

## 2. Three Tenancy Models

### Model A: Shared Database, Shared Schema (Row-Level)
**All tenants in one DB, one schema. Every table has `tenant_id` column.**

```sql
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    tenant_id INT NOT NULL,
    email TEXT,
    INDEX idx_tenant (tenant_id)
);
```

Every query MUST filter by `tenant_id`.

**Pros:** Cheapest, easiest scaling, single migration
**Cons:** Bug = data leak. Hard to back up per-tenant. Noisy neighbor.

---

### Model B: Shared Database, Schema-per-Tenant
**One DB, separate Postgres schema per tenant.**

```sql
CREATE SCHEMA tenant_acme;
CREATE TABLE tenant_acme.users (...);

CREATE SCHEMA tenant_corp;
CREATE TABLE tenant_corp.users (...);
```

Connection sets `SET search_path TO tenant_acme;` per request.

**Pros:** Strong isolation, can backup per schema, easy to delete tenant
**Cons:** N schemas = N migrations to apply, Postgres scales to ~1000 schemas

---

### Model C: Database-per-Tenant
**Each tenant gets own Postgres database (or instance).**

**Pros:** Strongest isolation, can be in different regions, billing per DB
**Cons:** Expensive, ops nightmare with 1000+ DBs, migration coordination

---

## 3. Decision Matrix

| Factor | Row-Level | Schema | DB-per-Tenant |
|---|---|---|---|
| **Cost** | $ | $$ | $$$$ |
| **Isolation** | Weakest | Medium | Strongest |
| **Scale (# tenants)** | 100K+ | ~1K | ~100 |
| **Compliance (HIPAA/SOC2)** | Tough | OK | Best |
| **Operational complexity** | Low | Medium | High |
| **Performance isolation** | Noisy neighbor | Some noise | Best |
| **Backup/restore per tenant** | Hard | Easy | Trivial |

**Common pick: Row-Level for SMB SaaS, Schema for enterprise SaaS, DB for healthcare/finance.**

---

## 4. Implementation: Row-Level (Most Common)

### 4.1 Tenant Resolution Strategies

How does the app know WHICH tenant on each request?

#### Strategy 1: Subdomain
`acme.myapp.com` → tenant=acme
```python
from fastapi import Request

def get_tenant(request: Request) -> str:
    host = request.headers.get("host", "")
    return host.split(".")[0]   # "acme" from "acme.myapp.com"
```

#### Strategy 2: URL Path
`/api/v1/tenants/acme/users` → tenant=acme

#### Strategy 3: JWT Claim
```json
{"sub": "user-42", "tenant_id": "acme"}
```
Decoded from `Authorization: Bearer <jwt>`.

#### Strategy 4: Custom Header
`X-Tenant-ID: acme`

**Best for production:** JWT claim (no spoofing, signed).

---

### 4.2 Tenant Context (Request-Scoped)

```python
from contextvars import ContextVar
from typing import Optional

current_tenant: ContextVar[Optional[str]] = ContextVar("current_tenant", default=None)

class TenantMiddleware:
    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            # Extract from JWT
            tenant = extract_tenant_from_jwt(scope)
            token = current_tenant.set(tenant)
            try:
                await self.app(scope, receive, send)
            finally:
                current_tenant.reset(token)
```

Now anywhere in code:
```python
tenant = current_tenant.get()
```

---

### 4.3 SQLAlchemy: Automatic Tenant Filter

```python
from sqlalchemy import event

class TenantMixin:
    tenant_id = Column(String, nullable=False, index=True)

# Auto-add WHERE tenant_id=X to every query
@event.listens_for(Session, "do_orm_execute")
def add_tenant_filter(execute_state):
    if execute_state.is_select and not execute_state.is_relationship_load:
        tenant_id = current_tenant.get()
        if tenant_id:
            execute_state.statement = execute_state.statement.where(
                User.tenant_id == tenant_id
            )
```

Now your code is **automatically tenant-safe**:
```python
users = db.query(User).all()   # SQL: WHERE tenant_id = 'acme'
```

---

### 4.4 Postgres Row-Level Security (RLS)

**Defense in depth — even if app forgets WHERE clause, DB enforces.**

```sql
ALTER TABLE users ENABLE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation ON users
    USING (tenant_id = current_setting('app.current_tenant')::text);
```

Set per connection:
```python
await db.execute(text("SET LOCAL app.current_tenant = :tenant"), {"tenant": "acme"})
# Now ALL queries on this connection are filtered to acme
```

**Highly recommended for production.**

---

## 5. Implementation: Schema-per-Tenant

### 5.1 Setup
```python
# Create schema for new tenant
await db.execute(text(f"CREATE SCHEMA tenant_{tenant_id}"))
# Run Alembic migrations targeting that schema
```

### 5.2 Per-Request Schema Switch
```python
class SchemaMiddleware:
    async def __call__(self, scope, receive, send):
        tenant = extract_tenant(scope)
        # On every request, switch search_path
        async with engine.connect() as conn:
            await conn.execute(text(f"SET search_path TO tenant_{tenant}, public"))
```

### 5.3 Migrations
With Alembic + multiple schemas, use:
```python
# Run migration on EACH tenant schema
for tenant in get_all_tenants():
    op.execute(f"SET search_path TO tenant_{tenant}")
    # ... migration ops
```

Or use `tenant_schemas` library.

---

## 6. Implementation: Database-per-Tenant

### 6.1 Connection Pool per Tenant
```python
class TenantDBRouter:
    def __init__(self):
        self.pools: dict[str, AsyncEngine] = {}

    def get_engine(self, tenant_id: str) -> AsyncEngine:
        if tenant_id not in self.pools:
            url = f"postgresql+asyncpg://user:pass@host/db_{tenant_id}"
            self.pools[tenant_id] = create_async_engine(url, pool_size=5)
        return self.pools[tenant_id]
```

### 6.2 LRU Cache Connection Pools
With 1000+ tenants, you can't keep all pools open. LRU cache:
```python
from functools import lru_cache

@lru_cache(maxsize=100)
def get_engine_cached(tenant_id):
    return create_engine_for(tenant_id)
```

Trade-off: cold start when LRU evicts and re-connects.

---

## 7. Tenant Onboarding Flow

```python
async def onboard_tenant(tenant_id: str, plan: str):
    # 1. Create tenant row in central DB
    await central_db.execute(
        "INSERT INTO tenants (id, plan, created_at) VALUES (?, ?, NOW())",
        tenant_id, plan
    )
    # 2. (Schema/DB model) Provision storage
    await db.execute(f"CREATE SCHEMA tenant_{tenant_id}")
    # 3. Run migrations
    await run_migrations_for_schema(f"tenant_{tenant_id}")
    # 4. Seed default data
    await seed_default_roles(tenant_id)
    # 5. Provision external resources
    await create_s3_bucket(f"tenant-{tenant_id}-uploads")
    # 6. Notify via webhook/email
```

---

## 8. Cross-Tenant Concerns

### Reporting / Analytics
Querying across all tenants:
```python
# DON'T use tenant filter for admin analytics
with bypass_tenant_filter():
    total_users = db.query(User).count()   # all tenants
```

Use a separate **data warehouse** (Snowflake, BigQuery) replicated from OLTP.

### Background Jobs
Celery task must include tenant_id in payload + restore context:
```python
@celery.task
def send_email(tenant_id, user_id):
    with tenant_context(tenant_id):
        # safe to query
        ...
```

### Caching
Always include tenant_id in cache key:
```python
cache_key = f"user:{tenant_id}:{user_id}"
```

### Rate Limiting
Per-tenant limits — prevent one tenant DoSing the platform:
```python
limiter = TokenBucket(per_tenant_rate=1000)   # 1000 req/min per tenant
```

---

## 9. Migration Strategies

### Migrating from single-tenant to multi-tenant
1. Add `tenant_id` column to all tables (NULL allowed initially)
2. Backfill — assign all existing data to "default" tenant
3. Add NOT NULL constraint
4. Add tenant filter middleware
5. Enable RLS

### Schema evolution per tenant
- Stagger rollout — new column added to one tenant first
- Feature flags per tenant
- Beta tenants get new schema first

---

## 10. Real Examples

### Slack
Row-level + workspace_id. Some heavy customers on dedicated DBs.

### Stripe
Tenant = account. Row-level with strong RLS.

### Shopify
Pod architecture — groups of shops on same DB. Re-shards as needed.

### Notion
Row-level with workspace_id. PostgreSQL with very deep indexing.

### Salesforce
Org-per-tenant with shared schema. Industry-leading multi-tenant ORM.

---

## 11. Security Pitfalls

### Pitfall 1: Forgetting tenant filter
**Fix:** RLS in database. Belt + suspenders.

### Pitfall 2: ID enumeration leak
`/api/users/12345` — if no tenant check, returns user from ANOTHER tenant.

**Fix:** Always check `user.tenant_id == current_tenant` before serving.

### Pitfall 3: Caching bug
Cached response from tenant A served to tenant B.

**Fix:** Include tenant_id in every cache key.

### Pitfall 4: Background job leak
Job processes tenant A's data with tenant B's context.

**Fix:** Pass tenant_id in payload; restore context strictly.

### Pitfall 5: Logs cross-contaminate
Log shows tenant A's data in tenant B's investigation.

**Fix:** Structured logs with tenant_id field. Per-tenant log retention rules.

---

## 12. Interview Questions

**Q1: Three tenancy models?**
Row-level (cheapest), Schema-per-tenant (middle), DB-per-tenant (most isolated).

**Q2: Pros/cons of row-level?**
+ Cheap, scales to 100K tenants
- Bug = data leak. Use RLS as backup.

**Q3: Tenant context kaise propagate?**
Middleware extracts from JWT → `contextvars.ContextVar` → accessible anywhere.

**Q4: 1000 schemas — Postgres handles?**
Yes but slow. Connection setup overhead, schema metadata bloat. ~1000 is practical limit.

**Q5: Row-level security kya hai?**
Postgres RLS = DB-enforced WHERE clause. Even if app forgets filter, DB rejects.

**Q6: Caching multi-tenant safe karna?**
Tenant_id in every cache key. Reset cache on tenant changes.

**Q7: Noisy neighbor problem?**
One tenant's heavy queries slow others. Mitigation: per-tenant rate limit, query timeout, separate read replicas.

---

## 13. Best Practices

1. **Pick model early** — migration later is expensive
2. **Defense in depth** — App filter + DB RLS + audit logs
3. **Tenant ID in EVERY log line** — for debugging
4. **Cache keys include tenant_id**
5. **Background jobs pass tenant context explicitly**
6. **Test isolation in CI** — fixture creates 2 tenants, verifies cross-access blocked
7. **Per-tenant rate limits** — noisy neighbor protection
8. **Tenant lifecycle hooks** — onboard/offboard/suspend
9. **Compliance**: data residency, audit, encryption per tenant
10. **Observability**: per-tenant metrics, SLAs

---

## Related
- [[../Phase2_Django_DRF/10_multitenant_apidocs]]
- [[14_opentelemetry_distributed_tracing]] — tenant_id as span attribute
- [[../Phase3_Security/]] — RBAC interaction
