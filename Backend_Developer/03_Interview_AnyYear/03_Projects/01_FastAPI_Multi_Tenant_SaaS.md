# Project 1: Multi-Tenant SaaS API Platform

**Stack:** FastAPI + Postgres + Redis + Celery + Stripe + Docker + AWS
**Build Time:** 2-3 weeks
**Difficulty:** ⭐⭐⭐⭐ (Architecturally complex but well-defined)
**Resume Strength:** ⭐⭐⭐⭐⭐ (Foundation template, reusable)

---

## 1. Project Overview & Business Problem

### What it is
A production-ready B2B SaaS API template that supports multiple customers (tenants) on shared infrastructure with isolated data, role-based access control, billing integration, and audit logging.

### Why build this
- **Reusable foundation:** Every B2B SaaS startup needs this. Build once, reuse forever.
- **Covers most senior-level patterns:** Multi-tenancy, RBAC, billing, webhooks, audit, async tasks.
- **Interview gold:** Demonstrates architectural thinking, not just CRUD.

### Real-world analogues
- Slack workspaces
- Notion teams
- Linear organizations
- Stripe accounts
- Salesforce orgs

---

## 2. Requirements

### Functional
- **Tenant management:** Create, suspend, delete tenants (organizations).
- **User management:** Sign up, invite, manage members within a tenant.
- **Authentication:** Email/password, JWT, refresh tokens, password reset.
- **Authorization (RBAC):** Owner / Admin / Member / Viewer roles with permissions.
- **Billing:** Stripe subscription integration (plans, usage-based, trials).
- **Webhooks:** Receive Stripe webhooks, send outbound webhooks to customers.
- **Audit logging:** Track all sensitive actions (login, settings change, billing).
- **Email notifications:** Welcome, invites, password reset, billing.
- **API rate limiting:** Per-tenant + per-user limits.
- **Settings:** Per-tenant configuration (branding, feature flags).

### Non-Functional
- 10K+ tenants on shared infrastructure.
- 100K+ users total.
- API latency p99 < 200ms.
- 99.95% uptime SLO.
- GDPR-compliant (data export, deletion).
- SOC 2-ready (audit logs, encryption).
- Horizontally scalable.

---

## 3. Scale Estimation

| Metric | Number |
|---|---|
| Tenants | 10K |
| Users per tenant (avg) | 10 |
| Total users | 100K |
| API requests/sec (avg) | 1K |
| API requests/sec (peak) | 5K |
| Daily active tenants | 3K |
| Stripe webhook events/day | 50K |
| Audit log entries/day | 1M |
| Storage (rows) | 10M (across all tenants) |

---

## 4. High-Level Architecture

```
                          ┌─────────────────┐
                          │   CloudFront    │
                          │  (CDN + WAF)    │
                          └────────┬────────┘
                                   │
                          ┌────────▼────────┐
                          │ Application LB  │
                          └────────┬────────┘
                                   │
              ┌────────────────────┼───────────────────────┐
              │                    │                       │
        ┌─────▼──────┐      ┌──────▼─────┐         ┌──────▼─────┐
        │  FastAPI   │      │  FastAPI   │         │  FastAPI   │
        │  Instance 1│      │  Instance 2│   ...   │  Instance N│
        └─────┬──────┘      └──────┬─────┘         └──────┬─────┘
              │                    │                       │
              └────────────────────┼───────────────────────┘
                                   │
        ┌──────────┬───────────────┼──────────────┬──────────────┐
        │          │               │              │              │
   ┌────▼──┐  ┌────▼──┐    ┌───────▼─────┐  ┌────▼─────┐  ┌─────▼─────┐
   │Postgres│  │ Redis │    │   Celery    │  │ Stripe   │  │   SES     │
   │(RDS)   │  │       │    │  Workers    │  │ Webhooks │  │  (Email)  │
   │+Replicas│ │Cluster│    └─────────────┘  └──────────┘  └───────────┘
   └────────┘  └───────┘
                    │
              ┌─────┴─────┐
              │  RabbitMQ │
              │ (broker)  │
              └───────────┘
```

---

## 5. Multi-Tenancy Architecture

### Decision: Shared Database, Shared Schema with `tenant_id`

Three options exist:
1. **Schema-per-tenant** (Postgres schemas): strong isolation, painful at scale (10K schemas).
2. **DB-per-tenant**: maximum isolation, very expensive, hard to manage.
3. **Shared schema with `tenant_id` column**: best for most SaaS. Easier scaling, cross-tenant analytics easy.

For this template: **Option 3** with row-level security as defense-in-depth.

### Tenant context

```
Every request:
  1. JWT decoded → user_id + tenant_id extracted.
  2. Tenant context set in ContextVar.
  3. All ORM queries auto-filtered by tenant_id (via middleware).
  4. RLS in Postgres as backup defense.
```

### Why RLS?
Even if developer forgets `WHERE tenant_id = $1`, Postgres rejects the query.

```sql
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON users
    USING (tenant_id = current_setting('app.tenant_id')::bigint);
```

App sets `app.tenant_id` per connection via middleware.

---

## 6. Data Model

```sql
-- Tenants (organizations)
CREATE TABLE tenants (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    slug            TEXT UNIQUE NOT NULL,        -- 'acme-inc'
    name            TEXT NOT NULL,
    plan            TEXT NOT NULL,                -- 'free', 'pro', 'enterprise'
    status          TEXT NOT NULL DEFAULT 'active',  -- 'active', 'suspended', 'deleted'
    stripe_customer_id TEXT UNIQUE,
    stripe_subscription_id TEXT,
    settings        JSONB NOT NULL DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at      TIMESTAMPTZ
);

-- Users (within a tenant)
CREATE TABLE users (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL REFERENCES tenants(id),
    email           TEXT NOT NULL,
    password_hash   TEXT NOT NULL,
    full_name       TEXT,
    role            TEXT NOT NULL DEFAULT 'member',  -- 'owner', 'admin', 'member', 'viewer'
    email_verified  BOOL NOT NULL DEFAULT false,
    last_login_at   TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(tenant_id, email)
);
CREATE INDEX idx_users_tenant ON users(tenant_id);

-- Invitations (pending user invites)
CREATE TABLE invitations (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL REFERENCES tenants(id),
    email           TEXT NOT NULL,
    role            TEXT NOT NULL,
    invited_by      UUID NOT NULL REFERENCES users(id),
    token           TEXT UNIQUE NOT NULL,
    expires_at      TIMESTAMPTZ NOT NULL,
    accepted_at     TIMESTAMPTZ
);
CREATE INDEX idx_invitations_token ON invitations(token);

-- Refresh tokens (for JWT)
CREATE TABLE refresh_tokens (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES users(id),
    token_hash      TEXT UNIQUE NOT NULL,
    expires_at      TIMESTAMPTZ NOT NULL,
    revoked_at      TIMESTAMPTZ,
    user_agent      TEXT,
    ip_address      INET,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- API keys (for programmatic access)
CREATE TABLE api_keys (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL REFERENCES tenants(id),
    name            TEXT NOT NULL,
    key_hash        TEXT UNIQUE NOT NULL,
    last_used_at    TIMESTAMPTZ,
    expires_at      TIMESTAMPTZ,
    scopes          TEXT[] NOT NULL DEFAULT '{}',
    created_by      UUID NOT NULL REFERENCES users(id),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    revoked_at      TIMESTAMPTZ
);

-- Audit logs
CREATE TABLE audit_logs (
    id              BIGSERIAL PRIMARY KEY,
    tenant_id       UUID NOT NULL,
    user_id         UUID,                       -- can be null (system action)
    action          TEXT NOT NULL,               -- 'user.created', 'tenant.plan_changed'
    resource_type   TEXT,                        -- 'user', 'subscription'
    resource_id     TEXT,
    metadata        JSONB,
    ip_address      INET,
    user_agent      TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_audit_tenant_created ON audit_logs(tenant_id, created_at DESC);
-- Partition by month for big tenants

-- Webhooks (outbound, customer-defined)
CREATE TABLE webhook_endpoints (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL REFERENCES tenants(id),
    url             TEXT NOT NULL,
    secret          TEXT NOT NULL,                -- for HMAC signing
    events          TEXT[] NOT NULL,              -- which events to subscribe to
    active          BOOL NOT NULL DEFAULT true,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE webhook_deliveries (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    endpoint_id     UUID NOT NULL REFERENCES webhook_endpoints(id),
    event_type      TEXT NOT NULL,
    payload         JSONB NOT NULL,
    status          TEXT NOT NULL,                -- 'pending', 'success', 'failed'
    attempts        INT NOT NULL DEFAULT 0,
    last_attempt_at TIMESTAMPTZ,
    response_code   INT,
    response_body   TEXT,
    next_retry_at   TIMESTAMPTZ
);
CREATE INDEX idx_webhook_deliveries_pending ON webhook_deliveries(next_retry_at) WHERE status = 'pending';
```

---

## 7. API Design

### Auth endpoints (public)
```
POST   /auth/signup                  { email, password, tenant_name }
POST   /auth/login                   { email, password } → { access, refresh }
POST   /auth/refresh                 { refresh_token } → { access, refresh }
POST   /auth/logout                  { refresh_token }
POST   /auth/password/reset/request  { email }
POST   /auth/password/reset/confirm  { token, new_password }
POST   /auth/email/verify            { token }
```

### Tenant endpoints
```
GET    /tenants/me                   (current tenant info)
PATCH  /tenants/me                   (update name, settings)
DELETE /tenants/me                   (delete tenant — soft delete)
GET    /tenants/me/usage             (current usage vs quota)
```

### User endpoints (within tenant)
```
GET    /users                         (list users in tenant)
GET    /users/me                      (current user)
PATCH  /users/me                      (update own profile)
GET    /users/{id}                    (get user — admin)
PATCH  /users/{id}                    (update — admin)
DELETE /users/{id}                    (remove from tenant)
POST   /users/invite                  (invite by email)
POST   /users/accept-invite           (accept invitation)
```

### Billing endpoints
```
GET    /billing/subscription         (current sub)
POST   /billing/subscribe            (create sub via Stripe)
PATCH  /billing/subscription         (change plan)
DELETE /billing/subscription         (cancel)
GET    /billing/invoices             (history)
GET    /billing/usage                (usage metering)
POST   /billing/webhook              (Stripe → us)
```

### API keys endpoints
```
GET    /api-keys                     (list)
POST   /api-keys                     (create)
DELETE /api-keys/{id}                (revoke)
```

### Webhooks (outbound)
```
GET    /webhook-endpoints
POST   /webhook-endpoints
DELETE /webhook-endpoints/{id}
GET    /webhook-endpoints/{id}/deliveries
POST   /webhook-endpoints/{id}/test
```

### Audit logs
```
GET    /audit-logs?action=&from=&to= (paginated)
```

---

## 8. Authentication & Authorization

### JWT structure

```json
{
  "sub": "user-uuid",
  "tenant_id": "tenant-uuid",
  "role": "admin",
  "permissions": ["users:read", "billing:write"],
  "iat": 1700000000,
  "exp": 1700001800,                  // 30 min
  "iss": "saas-platform.com"
}
```

- **Access token**: 30-minute TTL, signed with RS256.
- **Refresh token**: 30-day TTL, stored hashed in DB, single-use rotation.

### RBAC permissions

```python
PERMISSIONS = {
    "owner": ["*:*"],   # everything
    "admin": [
        "users:*", "billing:read", "billing:write",
        "audit:read", "settings:write", "api_keys:*"
    ],
    "member": [
        "users:read", "users:write_self",
        "audit:read_self", "settings:read"
    ],
    "viewer": ["users:read", "settings:read"]
}

def has_permission(user, perm):
    user_perms = PERMISSIONS[user.role]
    for p in user_perms:
        if p == "*:*": return True
        if matches(p, perm): return True
    return False
```

### Authentication dependency

```python
from fastapi import Depends, HTTPException, Header

async def get_current_user(authorization: str = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Missing token")
    token = authorization[7:]
    try:
        payload = jwt.decode(token, PUBLIC_KEY, algorithms=["RS256"])
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(401, "Invalid token")
    user = await get_user_by_id(payload["sub"])
    if not user or user.tenant.status != "active":
        raise HTTPException(401, "Inactive user/tenant")

    # Set tenant context for ORM
    current_tenant.set(payload["tenant_id"])
    return user

def require_permission(perm):
    def dependency(user: User = Depends(get_current_user)):
        if not has_permission(user, perm):
            raise HTTPException(403, f"Missing permission: {perm}")
        return user
    return dependency

# Usage
@app.post("/users/invite", dependencies=[Depends(require_permission("users:write"))])
async def invite_user(...): ...
```

### API key authentication

```python
async def get_api_key_user(x_api_key: str = Header(None)):
    if not x_api_key:
        return None
    key_hash = hashlib.sha256(x_api_key.encode()).hexdigest()
    api_key = await db.fetch_one(
        "SELECT * FROM api_keys WHERE key_hash = $1 AND revoked_at IS NULL",
        key_hash
    )
    if not api_key: raise HTTPException(401)
    if api_key.expires_at and api_key.expires_at < now(): raise HTTPException(401)

    await db.execute("UPDATE api_keys SET last_used_at = now() WHERE id = $1", api_key.id)
    return api_key
```

---

## 9. Caching Strategy

| Cache | Key Pattern | TTL |
|---|---|---|
| Tenant metadata | `tenant:{id}` | 5 min |
| User profile | `user:{id}` | 5 min |
| Permissions check | `perms:{user_id}` | 5 min |
| Stripe customer | `stripe:cust:{tenant_id}` | 1 hour |
| Rate limit counter | `rl:{user_id}:{endpoint}` | window-based |
| JWT blacklist | `jwt:blacklisted:{jti}` | until expiry |

### Per-tenant cache namespacing

```python
def cache_key(*parts, tenant_id=None):
    tenant_id = tenant_id or current_tenant.get()
    return f"tenant:{tenant_id}:" + ":".join(str(p) for p in parts)

# Usage
key = cache_key("user", user_id)   # → "tenant:abc:user:xyz"
```

**Critical:** Never share keys across tenants. Cross-tenant cache leak = data leak.

---

## 10. Rate Limiting

```python
async def rate_limit(
    user_id: str,
    endpoint: str,
    limit: int = 100,
    window_sec: int = 60
):
    key = f"rl:{user_id}:{endpoint}"
    pipe = redis.pipeline()
    pipe.zremrangebyscore(key, 0, time.time() - window_sec)
    pipe.zadd(key, {str(uuid.uuid4()): time.time()})
    pipe.zcard(key)
    pipe.expire(key, window_sec)
    results = await pipe.execute()

    count = results[2]
    if count > limit:
        retry_after = window_sec
        raise HTTPException(429, headers={"Retry-After": str(retry_after)})

# Per-tenant quota check
async def check_tenant_quota(tenant_id, resource, amount=1):
    tenant = await get_tenant(tenant_id)
    quota = PLAN_QUOTAS[tenant.plan][resource]
    used = await redis.get(f"quota:{tenant_id}:{resource}:{date.today()}") or 0
    if int(used) + amount > quota:
        raise QuotaExceededError(resource, quota)
    await redis.incrby(f"quota:{tenant_id}:{resource}:{date.today()}", amount)
```

---

## 11. Stripe Billing Integration

### Plans

```python
PLANS = {
    "free": {
        "price_id": None,
        "users_limit": 3,
        "api_calls_per_day": 1000,
        "storage_gb": 1
    },
    "pro": {
        "price_id": "price_1234",
        "monthly_price_usd": 49,
        "users_limit": 25,
        "api_calls_per_day": 100000,
        "storage_gb": 50
    },
    "enterprise": {
        "price_id": "price_5678",
        "monthly_price_usd": 499,
        "users_limit": None,
        "api_calls_per_day": None,
        "storage_gb": 500
    }
}
```

### Subscribe flow

```python
@app.post("/billing/subscribe")
async def subscribe(plan: str, payment_method_id: str, user: User = Depends(...)):
    tenant = user.tenant
    plan_config = PLANS[plan]

    # Create Stripe customer if not exists
    if not tenant.stripe_customer_id:
        customer = stripe.Customer.create(
            email=user.email,
            metadata={"tenant_id": str(tenant.id)}
        )
        await db.execute(
            "UPDATE tenants SET stripe_customer_id = $1 WHERE id = $2",
            customer.id, tenant.id
        )
        tenant.stripe_customer_id = customer.id

    # Attach payment method
    stripe.PaymentMethod.attach(payment_method_id, customer=tenant.stripe_customer_id)
    stripe.Customer.modify(
        tenant.stripe_customer_id,
        invoice_settings={"default_payment_method": payment_method_id}
    )

    # Create subscription
    subscription = stripe.Subscription.create(
        customer=tenant.stripe_customer_id,
        items=[{"price": plan_config["price_id"]}],
        expand=["latest_invoice.payment_intent"]
    )

    # Save
    await db.execute(
        "UPDATE tenants SET plan = $1, stripe_subscription_id = $2 WHERE id = $3",
        plan, subscription.id, tenant.id
    )

    await audit_log(tenant.id, user.id, "billing.subscribed", {"plan": plan})

    return {"status": subscription.status, "client_secret": subscription.latest_invoice.payment_intent.client_secret}
```

### Webhook handler

```python
@app.post("/billing/webhook")
async def stripe_webhook(request: Request):
    payload = await request.body()
    sig = request.headers.get("Stripe-Signature")

    try:
        event = stripe.Webhook.construct_event(payload, sig, WEBHOOK_SECRET)
    except (ValueError, stripe.error.SignatureVerificationError):
        raise HTTPException(400, "Invalid signature")

    # Idempotency
    if await redis.set(f"stripe:event:{event.id}", "1", nx=True, ex=86400) is None:
        return {"received": True}    # already processed

    if event.type == "invoice.payment_succeeded":
        await handle_payment_success(event.data.object)
    elif event.type == "customer.subscription.deleted":
        await handle_subscription_cancelled(event.data.object)
    elif event.type == "invoice.payment_failed":
        await handle_payment_failed(event.data.object)
    # ... other events

    return {"received": True}
```

### Usage-based billing

```python
# Track API call usage
async def record_usage(tenant_id, metric, quantity=1):
    today = date.today()
    await redis.hincrby(f"usage:{tenant_id}:{today}", metric, quantity)

# Daily flush to Stripe
@celery.task
def flush_usage_to_stripe():
    yesterday = date.today() - timedelta(days=1)
    for tenant in get_active_tenants():
        usage = await redis.hgetall(f"usage:{tenant.id}:{yesterday}")
        for metric, qty in usage.items():
            stripe.SubscriptionItem.create_usage_record(
                subscription_item=tenant.usage_item_id,
                quantity=int(qty),
                timestamp=int(yesterday.strftime("%s")),
                action="increment"
            )
```

---

## 12. Async Tasks (Celery)

### Tasks

```python
@celery.task(autoretry_for=(Exception,), retry_kwargs={"max_retries": 5, "countdown": 60})
def send_welcome_email(user_id):
    user = get_user(user_id)
    email_service.send_template("welcome", user.email, {"name": user.full_name})

@celery.task
def send_invitation_email(invitation_id):
    invitation = get_invitation(invitation_id)
    email_service.send_template("invitation", invitation.email, {
        "tenant_name": invitation.tenant.name,
        "invite_link": f"https://app.example.com/accept?token={invitation.token}"
    })

@celery.task
def deliver_webhook(delivery_id):
    delivery = get_webhook_delivery(delivery_id)
    endpoint = delivery.endpoint
    sig = hmac.new(
        endpoint.secret.encode(),
        json.dumps(delivery.payload).encode(),
        hashlib.sha256
    ).hexdigest()

    try:
        response = requests.post(
            endpoint.url,
            json=delivery.payload,
            headers={"X-Signature": sig, "X-Event-Type": delivery.event_type},
            timeout=30
        )
        if 200 <= response.status_code < 300:
            update_delivery(delivery_id, status="success", response_code=response.status_code)
        else:
            schedule_retry(delivery_id, response.status_code)
    except requests.RequestException as e:
        schedule_retry(delivery_id, error=str(e))

def schedule_retry(delivery_id, error_code=None):
    delivery = get_webhook_delivery(delivery_id)
    if delivery.attempts >= 5:
        update_delivery(delivery_id, status="failed")
        return
    backoff_sec = 2 ** delivery.attempts * 60   # 1m, 2m, 4m, 8m, 16m
    next_retry = datetime.utcnow() + timedelta(seconds=backoff_sec)
    update_delivery(delivery_id, attempts=delivery.attempts + 1, next_retry_at=next_retry)
    deliver_webhook.apply_async(args=[delivery_id], eta=next_retry)
```

### Scheduled tasks

```python
celery.conf.beat_schedule = {
    "flush-usage-daily": {
        "task": "tasks.flush_usage_to_stripe",
        "schedule": crontab(hour=2, minute=0),
    },
    "cleanup-expired-tokens": {
        "task": "tasks.cleanup_refresh_tokens",
        "schedule": crontab(hour=3, minute=0),
    },
    "purge-old-audit-logs": {
        "task": "tasks.purge_old_audit_logs",
        "schedule": crontab(day_of_month=1, hour=4),
    },
    "send-billing-alerts": {
        "task": "tasks.send_billing_alerts",
        "schedule": crontab(hour=9, minute=0),
    },
}
```

---

## 13. Audit Logging

### Structured logger

```python
async def audit_log(
    tenant_id, user_id, action, metadata=None,
    resource_type=None, resource_id=None
):
    await db.execute(
        "INSERT INTO audit_logs "
        "(tenant_id, user_id, action, resource_type, resource_id, metadata, ip_address, user_agent) "
        "VALUES ($1, $2, $3, $4, $5, $6, $7, $8)",
        tenant_id, user_id, action,
        resource_type, resource_id,
        json.dumps(metadata or {}),
        request.client.host, request.headers.get("user-agent")
    )

# Usage
@app.post("/users/invite")
async def invite(req: InviteRequest, user=Depends(...)):
    invitation = create_invitation(...)
    await audit_log(
        user.tenant_id, user.id,
        "user.invited",
        metadata={"invited_email": req.email, "role": req.role},
        resource_type="invitation", resource_id=str(invitation.id)
    )
    return invitation
```

### Partitioning (large tenants)

```sql
-- Partition audit_logs by month for big tenants
CREATE TABLE audit_logs_2024_01 PARTITION OF audit_logs
    FOR VALUES FROM ('2024-01-01') TO ('2024-02-01');
-- Auto-create monthly via cron or pg_partman
```

---

## 14. Deployment Architecture

### Docker Compose (Dev)

```yaml
version: "3.9"
services:
  api:
    build: .
    ports: ["8000:8000"]
    environment:
      DATABASE_URL: postgres://app:app@postgres:5432/saas
      REDIS_URL: redis://redis:6379/0
      STRIPE_SECRET: ${STRIPE_SECRET}
    depends_on: [postgres, redis, rabbitmq]

  worker:
    build: .
    command: celery -A app.celery_app worker --loglevel=info
    depends_on: [postgres, redis, rabbitmq]

  beat:
    build: .
    command: celery -A app.celery_app beat --loglevel=info
    depends_on: [postgres, redis, rabbitmq]

  postgres:
    image: postgres:16
    environment:
      POSTGRES_USER: app
      POSTGRES_PASSWORD: app
      POSTGRES_DB: saas
    volumes:
      - postgres_data:/var/lib/postgresql/data

  redis:
    image: redis:7

  rabbitmq:
    image: rabbitmq:3-management
    ports: ["15672:15672"]

volumes:
  postgres_data:
```

### Production (AWS)

```
                 ┌──────────────┐
                 │  CloudFront  │
                 │   + WAF      │
                 └──────┬───────┘
                        │
                 ┌──────▼───────┐
                 │  ALB         │
                 └──────┬───────┘
                        │
              ┌─────────┼─────────┐
              ▼         ▼         ▼
         ┌────────┐┌────────┐┌────────┐
         │ ECS    ││ ECS    ││ ECS    │
         │ FastAPI││ FastAPI││ FastAPI│
         └────┬───┘└────┬───┘└────┬───┘
              └─────────┼─────────┘
                        │
        ┌───────────────┼───────────────┐
        ▼               ▼               ▼
   ┌─────────┐   ┌──────────┐   ┌──────────┐
   │ RDS     │   │ElastiCache│   │   AmazonMQ│
   │ Postgres│   │ Redis    │   │  (RabbitMQ)│
   │+ Replicas│  └──────────┘   └──────────┘
   └─────────┘
                        │
                  ┌─────▼─────┐
                  │ ECS Worker│  (Celery)
                  └───────────┘
```

### Kubernetes (alternative)

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: saas-api
spec:
  replicas: 3
  template:
    spec:
      containers:
      - name: api
        image: myrepo/saas-api:v1
        env:
        - name: DATABASE_URL
          valueFrom: { secretKeyRef: { name: db-credentials, key: url } }
        resources:
          requests: { cpu: 500m, memory: 512Mi }
          limits: { cpu: 1000m, memory: 1Gi }
        livenessProbe:
          httpGet: { path: /health, port: 8000 }
        readinessProbe:
          httpGet: { path: /ready, port: 8000 }
---
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: saas-api-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: saas-api
  minReplicas: 3
  maxReplicas: 20
  metrics:
  - type: Resource
    resource:
      name: cpu
      target: { type: Utilization, averageUtilization: 70 }
```

---

## 15. Senior-Level Showcases

These are the "wow" details that elevate this from a CRUD app:

### A. Row-Level Security as Defense-in-Depth
Even if app code forgets `WHERE tenant_id = ...`, Postgres rejects the query. Critical for compliance.

### B. JWT with RS256 (asymmetric)
Microservices can verify tokens without sharing the signing secret. Public key distributed; private key on auth service only.

### C. Refresh Token Rotation
Each refresh issues a new refresh token; old one invalidated. Detects token theft (if old one used after rotation → revoke all).

### D. Idempotent Stripe Webhooks
Same Stripe event delivered twice → processed once (via Redis SET NX).

### E. Outbound Webhook Retries with Exponential Backoff
Failed delivery → retry 1m, 2m, 4m, 8m, 16m. After 5 failures → dead letter.

### F. Per-Tenant Quota with Redis Atomic Operations
Atomic INCR with daily key; checked before each metered action.

### G. Audit Log Partitioning
Tables partitioned by month for fast queries on huge tables.

### H. Multi-Region Read Replicas
Read-heavy endpoints route to nearest replica; writes go to primary.

### I. Health Checks & Graceful Shutdown
Liveness (process alive) vs readiness (DB/Redis reachable). SIGTERM triggers graceful drain.

### J. GDPR Data Export/Deletion
On request: package all tenant data → ZIP; deletion cascades through all tables + Redis.

---

## 16. Implementation Roadmap

### Week 1: Foundation
- [ ] Project scaffolding (FastAPI + SQLAlchemy 2.0 + Alembic).
- [ ] Database schema (tenants, users, basic relations).
- [ ] Auth: signup, login, JWT issue + verify.
- [ ] Tenant context middleware + RLS setup.
- [ ] Basic CRUD for tenants + users.

### Week 2: RBAC + Billing
- [ ] Permission system (decorator-based).
- [ ] Invite flow with email.
- [ ] Stripe integration: create customer, subscribe.
- [ ] Webhook receiver with idempotency.
- [ ] Plan-based quota enforcement.

### Week 3: Async + Polish
- [ ] Celery setup with RabbitMQ.
- [ ] Email tasks (welcome, invite, password reset).
- [ ] Outbound webhook system with retries.
- [ ] Audit logging on all sensitive actions.
- [ ] API key authentication.
- [ ] Rate limiting middleware.

### Week 4: Production
- [ ] Health endpoints + graceful shutdown.
- [ ] Dockerize + docker-compose.
- [ ] Deploy to AWS ECS or K8s.
- [ ] Set up CloudWatch / Prometheus metrics.
- [ ] Load test with Locust (target 5K RPS).
- [ ] Write README + API docs.

---

## 17. Common Pitfalls & Solutions

### Pitfall 1: Forgetting tenant filter
**Symptom:** User A sees User B's data.
**Solution:** RLS in Postgres + middleware-injected query filter.

### Pitfall 2: Cross-tenant cache keys
**Symptom:** Random data leak via Redis.
**Solution:** Mandatory tenant prefix in `cache_key()` helper.

### Pitfall 3: JWT not revocable
**Symptom:** User logged out but token still works.
**Solution:** Short JWT TTL (30 min) + refresh token revocation in DB.

### Pitfall 4: Stripe webhook timeout
**Symptom:** Stripe retries; double-processing.
**Solution:** Acknowledge fast (< 5 sec) + idempotency via Redis.

### Pitfall 5: Connection pool exhaustion
**Symptom:** "remaining connection slots reserved..." errors.
**Solution:** PgBouncer + per-tenant connection limit.

### Pitfall 6: Stale tenant settings
**Symptom:** User updates settings; old cached value persists.
**Solution:** Invalidate cache on write + short TTL.

### Pitfall 7: Audit log growth
**Symptom:** audit_logs table 1B rows.
**Solution:** Monthly partitioning + delete partitions older than retention (1 year typical).

---

## 18. Performance Benchmarks (Target)

| Metric | Target |
|---|---|
| API p50 latency | < 50ms |
| API p99 latency | < 200ms |
| Signup time | < 500ms |
| Login time | < 100ms |
| Concurrent connections | 5K |
| RPS | 5K (sustained) |
| Database connections | < 200 |
| Memory per pod | < 512MB |

### Load testing

```python
# locustfile.py
from locust import HttpUser, task, between

class APIUser(HttpUser):
    wait_time = between(1, 3)

    def on_start(self):
        response = self.client.post("/auth/login", json={
            "email": "test@example.com", "password": "..."
        })
        self.token = response.json()["access"]
        self.client.headers["Authorization"] = f"Bearer {self.token}"

    @task(3)
    def list_users(self):
        self.client.get("/users")

    @task(1)
    def get_billing(self):
        self.client.get("/billing/subscription")
```

```bash
locust -f locustfile.py --host=https://api.example.com
```

---

## 19. Resume Bullets & Interview Talking Points

### Resume bullets
- Built a multi-tenant SaaS API platform in FastAPI with row-level security and per-tenant Stripe billing, supporting 10K+ tenants on shared infrastructure.
- Implemented RBAC, audit logging, and asynchronous outbound webhooks with exponential backoff retry (5K RPS, p99 < 200ms).
- Designed a horizontally scalable architecture deployed on AWS ECS with auto-scaling, achieving 99.95% uptime SLO.

### Interview talking points
- **Multi-tenancy decision tree:** "Why shared schema vs schema-per-tenant?" → Cost, scaling, ops simplicity.
- **RLS as defense-in-depth:** "What if developer forgets WHERE tenant_id?" → DB rejects via policy.
- **Stripe webhook idempotency:** "Same event delivered twice — how do you not process twice?" → Redis SET NX.
- **JWT vs sessions:** Trade-offs of stateless vs stateful auth.
- **Audit log scaling:** Monthly partitioning + cold storage for compliance.

---

## 20. Stretch Goals (Post-MVP)

- **Single Sign-On (SAML / OIDC)**: SSO for enterprise tier.
- **Custom roles & permissions:** Per-tenant role definitions, not just preset.
- **Audit log export:** Async export to S3 (CSV/JSON).
- **Multi-region failover:** Replicate to second region; DNS failover.
- **Tenant data export:** GDPR-compliant download.
- **Usage analytics dashboard:** Charts in customer dashboard.
- **API versioning:** /v1, /v2 with sunset headers.
- **GraphQL endpoint:** Alongside REST.
- **Public API documentation:** Stripe-style with auto-generated SDK.
- **Webhook UI:** Replay, debugging, deliveries explorer.

---

## 21. Tech Stack Summary

| Layer | Choice | Why |
|---|---|---|
| **Framework** | FastAPI | Async, type hints, OpenAPI built-in |
| **DB** | Postgres 16 | RLS, JSONB, mature, scalable |
| **ORM** | SQLAlchemy 2.0 | Modern async API |
| **Migrations** | Alembic | Industry standard |
| **Cache** | Redis | Fast, atomic ops, pub/sub |
| **Queue** | RabbitMQ | Mature, complex routing |
| **Tasks** | Celery | Mature Python task framework |
| **Email** | AWS SES | Cheapest at scale |
| **Billing** | Stripe | Best DX, mature |
| **Container** | Docker | Standard |
| **Orchestration** | ECS or K8s | Scaling |
| **Monitoring** | CloudWatch + Sentry | Observability |
| **CI/CD** | GitHub Actions | Native |

---

## TL;DR

- Multi-tenant SaaS API in FastAPI with row-level security.
- RBAC, Stripe billing, audit logs, async webhooks, rate limiting.
- 10K+ tenants, 5K RPS target, p99 < 200ms.
- Foundation template for any B2B SaaS — reusable forever.
- 3-4 weeks build time.
- **Resume gold:** demonstrates architectural depth, not just CRUD.
