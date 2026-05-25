# 47 — Multi-Tenancy Patterns

> SaaS architecture fundamentals: how to host many customers (tenants) on shared infrastructure.

---

## What is Multi-Tenancy?

**Multi-tenant** = one software instance serves multiple customers (tenants). Each tenant's data is logically isolated from others.

**Single-tenant** = each customer gets dedicated instance.

### Spectrum

```
Shared everything ←─────────────────────────→ Dedicated everything
       │                                              │
   Pool model                                    Silo model
   (cheap, scales)                              (expensive, isolated)
       │                                              │
   ┌───┴────────────────────────────────────────────┴────┐
   │  Bridge: shared infra, partitioned data per tenant   │
   └──────────────────────────────────────────────────────┘
```

### Examples
- **Pool**: Slack (one cluster for all workspaces, partitioned data).
- **Bridge**: Salesforce orgs (shared app, dedicated schema per org).
- **Silo**: SAP HANA Enterprise (dedicated VMs per customer).

---

## Why Multi-Tenant SaaS?

### Benefits
- **Lower cost** per customer (utilization).
- **Easier ops** (one codebase, one deploy).
- **Faster features** (one place to update).
- **Better analytics** (cross-tenant insights, anonymized).

### Costs
- **Noisy neighbor** risk.
- **Data isolation** is critical and hard.
- **Per-tenant customization** is constrained.
- **Compliance** complexity (e.g., GDPR, HIPAA).

---

## Database Patterns

The biggest design decision: how to isolate tenant data?

### Pattern 1: Shared Database, Shared Schema

```sql
CREATE TABLE users (
    id BIGSERIAL PRIMARY KEY,
    tenant_id BIGINT NOT NULL,    -- discriminator column
    email TEXT,
    ...
);
CREATE INDEX ON users(tenant_id);
```

Every query: `WHERE tenant_id = ?`.

**Pros:**
- Easiest to develop.
- Most efficient (high tenant density).
- Cross-tenant analytics trivial.

**Cons:**
- Risk of missing `tenant_id` filter → data leak.
- Hard to scale "single big tenant".
- Backup/restore per tenant complex.

**Use:** Early-stage SaaS, < 1000 tenants.

---

### Pattern 2: Shared Database, Schema per Tenant

```sql
-- Postgres schemas (namespaces, not separate DBs)
CREATE SCHEMA tenant_acme;
CREATE TABLE tenant_acme.users (...);

CREATE SCHEMA tenant_globex;
CREATE TABLE tenant_globex.users (...);
```

At connect time, set `search_path = tenant_acme`.

**Pros:**
- Better isolation than shared schema.
- Per-tenant backup/restore via `pg_dump --schema`.
- Schema migration per tenant (advanced; usually you migrate all).

**Cons:**
- Connection switching overhead.
- Migration complexity (apply to N schemas).
- Postgres has limits (~1000s of schemas before perf degrades).

**Use:** Mid-stage SaaS, regulated industries (financial, healthcare).

---

### Pattern 3: Database per Tenant

```
DB cluster 1: db_acme
DB cluster 2: db_globex
DB cluster 3: db_initech
```

**Pros:**
- Strong isolation.
- Independent scale (per tenant).
- Easy "give us our data" (backup one DB).
- Independent migrations possible.

**Cons:**
- Operational nightmare at scale (thousands of DBs).
- No cross-tenant queries.
- Cost-heavy.

**Use:** Enterprise SaaS, < 100 customers paying $$$$.

---

### Pattern 4: Hybrid (Common in Practice)

Bucket tenants by size:
- Small tenants (95%) → shared database, shared schema.
- Medium tenants → shared database, dedicated schema.
- Enterprise tenants → dedicated database.

```
Routing layer:
  tenant.tier == "starter" → shared_db_cluster_1
  tenant.tier == "pro"     → tenant_schema_in_shared_db
  tenant.tier == "enterprise" → dedicated_db_for_tenant
```

---

## Compute & Network Isolation

### Shared Compute
- All tenants run on same K8s cluster, same pods.
- Resource limits (cgroups) prevent one tenant from CPU-hogging.

### Dedicated Compute
- Each tenant gets own pods / VMs.
- Stronger isolation, higher cost.
- Used by Snowflake, BigQuery dedicated warehouses.

### VPC per Tenant
- Each tenant has own VPC / subnet.
- Network-level isolation.
- Used in enterprise B2B (Snowflake Private Link, AWS).

---

## Tenant Identification (Routing)

### Subdomain
```
acme.app.com    → tenant_id = acme
globex.app.com  → tenant_id = globex
```
Pros: Clean URLs, SSL per tenant optional.
Cons: DNS wildcard required, cert management.

### URL Path
```
app.com/t/acme/dashboard
app.com/t/globex/dashboard
```
Pros: Single SSL cert, easier load balancing.
Cons: Less branded for customer.

### Header
```
GET /dashboard
X-Tenant-ID: acme
```
Pros: Clean for API.
Cons: Easy to spoof (must validate against auth token).

### JWT Claim
```json
{
  "sub": "user_123",
  "tenant_id": "acme",
  "role": "admin"
}
```
Tenant ID baked into auth token. Validated server-side.

**Best practice:** Combine — subdomain for UX, JWT for trusted enforcement.

---

## Code Architecture

### Tenant Context

```python
from contextvars import ContextVar

current_tenant: ContextVar[str] = ContextVar("tenant", default=None)

@app.middleware("http")
async def tenant_middleware(request, call_next):
    token = request.headers.get("Authorization")
    payload = verify_jwt(token)
    current_tenant.set(payload["tenant_id"])
    return await call_next(request)

# In any handler:
async def get_users():
    return await db.fetch(
        "SELECT * FROM users WHERE tenant_id = $1",
        current_tenant.get()
    )
```

### Avoiding "forgot tenant_id" bugs

**Option A: Make tenant_id implicit in ORM**
```python
class TenantSession(Session):
    def query(self, *args):
        q = super().query(*args)
        return q.filter_by(tenant_id=current_tenant.get())
```

All queries auto-filtered.

**Option B: Row-level security (Postgres)**

```sql
ALTER TABLE users ENABLE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation ON users
    USING (tenant_id = current_setting('app.tenant_id')::bigint);
```

```python
async def per_request():
    await conn.execute(
        f"SET app.tenant_id = {current_tenant.get()}"
    )
```

Postgres enforces filter even if app code forgets.

**Option C: Tenant-aware connection pool**

Each tenant gets dedicated connection pool with their context already set.

---

## Quota & Rate Limiting

### Per-tenant quotas
- Storage GB.
- API calls/day.
- Users in workspace.
- Concurrent connections.

### Implementation
```python
async def check_quota(tenant_id, resource, requested=1):
    key = f"quota:{tenant_id}:{resource}:{date.today()}"
    usage = await redis.incrby(key, requested)
    if usage == requested:
        await redis.expire(key, 86400)

    limit = await get_tenant_limit(tenant_id, resource)
    if usage > limit:
        raise QuotaExceeded()
```

### Soft vs hard limits
- Soft: warn but allow → email tenant.
- Hard: 429 reject.
- Some allow overage with billing.

---

## Per-Tenant Customization

### Configuration
Allow tenants to configure:
- Branding (logo, colors).
- Feature flags ("enable beta features").
- Integrations.
- Workflows.

```sql
CREATE TABLE tenant_config (
    tenant_id BIGINT PRIMARY KEY,
    branding JSONB,
    features JSONB,    -- {"chat": true, "ai_search": false}
    integrations JSONB
);
```

### Per-tenant feature flags
```python
async def is_feature_enabled(tenant_id, feature):
    config = await get_tenant_config(tenant_id)
    return config.features.get(feature, default_value(feature))

# Usage
if await is_feature_enabled(tenant_id, "ai_search"):
    return ai_powered_search()
return regular_search()
```

---

## Migrations

### Single shared DB
- One migration applies to all tenants.
- Run on deploy.

### Schema-per-tenant
- Apply migration to each schema.
- Sequential: long with many tenants.
- Parallel: stress on DB.

```python
async def migrate_all_tenants(migration_sql):
    schemas = await db.fetch("SELECT schema_name FROM information_schema.schemata WHERE schema_name LIKE 'tenant_%'")
    for schema in schemas:
        await db.execute(f"SET search_path = {schema}")
        await db.execute(migration_sql)
```

Be cautious: backward compatibility critical — old code may run during partial rollout.

---

## Backups & Disaster Recovery

### Shared DB
- Backup entire DB.
- Restore: per-tenant data via export tool.
- Per-tenant recovery: messy.

### DB per tenant
- Backup per DB.
- Restore one tenant: trivial.

### Compliance
GDPR right-to-be-forgotten:
- Shared DB: delete from each table where tenant_id = ?, plus cascading deletes.
- Per tenant DB: drop DB.

---

## Analytics & Monitoring

### Per-tenant metrics
Tag all metrics with tenant_id:
```python
metrics.increment(
    "api.request",
    tags={"tenant_id": current_tenant.get(), "endpoint": request.path}
)
```

### Dashboards
- One dashboard with tenant filter.
- Per-tenant SLA tracking.
- Top tenants by usage.

### Noisy-neighbor detection
- Track p99 latency per tenant.
- Alert if one tenant's usage degrades others.

---

## Pricing Models

### Per-seat
$X per user per month. Common for collaboration tools.

### Per-usage
$Y per API call, $Z per GB stored. Common for infra products.

### Tiered
Starter/Pro/Enterprise with feature & limit differences.

Architecture must support:
- Track usage per dimension.
- Aggregate monthly.
- Display in dashboard.
- Invoice generation.

---

## Security Patterns

### Tenant ID validation
Always validate that the requesting user belongs to the claimed tenant:
```python
def assert_tenant_access(user, tenant_id):
    if user.tenant_id != tenant_id:
        raise PermissionDenied()
```

### Encryption
- At rest: KMS-encrypted DB. Per-tenant key (BYOK) for enterprise.
- In transit: TLS.

### Audit logs
- Every cross-tenant access by support staff logged.
- Per-tenant export of their audit log.

---

## Anti-patterns

### Don't:
- Hardcode tenant_id checks in every query. → Use middleware/RLS.
- Cache without including tenant_id in key. → Cross-tenant data leak.
- Allow one tenant to query "all users" without filter. → Use parameterized queries enforced by ORM.
- Use sequential IDs visible across tenants. → Use UUID or per-tenant scoped IDs.

### Caching keys
**Wrong:** `user:123 → ...`
**Right:** `tenant:acme:user:123 → ...`

---

## Real-World Examples

### Slack
- Pool model: one Kafka cluster, one Cassandra cluster.
- Tenant = workspace, identified by URL path.
- Free tier shares everything; Enterprise can request dedicated cell.

### Salesforce
- Bridge model: shared infrastructure, schema per org.
- Each "org" is a tenant with metadata-driven UI.

### Snowflake
- Storage shared via S3; compute can be per-tenant (warehouses).
- Cross-region replication for enterprise.

### Stripe
- Pool model; account_id partitions everything.
- Strong account_id discipline; data leaks would be catastrophic.

### AWS
- Each AWS account = tenant.
- Strong VPC isolation.
- Backed by ARN namespacing.

---

## Bridge / Cell Architecture

Modern pattern: divide all tenants into "cells" (small clusters).

```
Cell-1: tenants 1-10000
Cell-2: tenants 10001-20000
...
```

Each cell:
- Fully isolated infra.
- Failure of one cell doesn't affect others.
- Easier to roll out changes (canary by cell).
- Limit blast radius.

Used by:
- Slack ("Enterprise Grid" = dedicated cell).
- AWS (some services internally).
- Shopify.

---

## TL;DR

| Pattern | Isolation | Cost | Scale |
|---|---|---|---|
| Shared schema, tenant_id | Low | Lowest | Highest density |
| Schema per tenant | Medium | Medium | Medium |
| DB per tenant | High | High | Low density |
| Cell-based | High | High | Best of both worlds |

**Pick:**
- Early SaaS: shared schema, RLS for safety.
- Mid: introduce cells, hybrid storage.
- Enterprise tier: dedicated DB / VPC.

**Tenant ID propagation:**
- JWT → middleware → context var → all queries auto-scope.
- Defense in depth: RLS in DB.

**Most common mistake:** Caching without tenant prefix.
