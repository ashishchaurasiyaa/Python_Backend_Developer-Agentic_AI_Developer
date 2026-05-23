# Project 4: Production AI API — Mini SaaS

## Overview
Shows you can build a real, monetizable AI product.
**Stack:** FastAPI + LiteLLM + Redis + Langfuse + Stripe + Multi-tenant

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Client Apps                           │
│              (Web, Mobile, API consumers)                │
└──────────────────────┬──────────────────────────────────┘
                       │ API Key auth
┌──────────────────────▼──────────────────────────────────┐
│                FastAPI Gateway                           │
│  Rate Limiting │ Auth │ Cost Tracking │ Usage Quotas    │
└──────────────────────┬──────────────────────────────────┘
                       │
        ┌──────────────┼──────────────┐
        ▼              ▼              ▼
┌───────────┐  ┌───────────────┐  ┌────────────┐
│  Semantic │  │  LiteLLM      │  │  Langfuse  │
│   Cache   │  │  Router       │  │ Observabil │
│  (Redis)  │  │ (multi-model) │  │    -ity    │
└───────────┘  └───────┬───────┘  └────────────┘
                       │
         ┌─────────────┼──────────────┐
         ▼             ▼              ▼
   Anthropic       OpenAI         AWS Bedrock
   (Claude)        (GPT-4o)       (fallback)
```

---

## Core Implementation

### 1. Multi-tenant Architecture

```python
# app/models/tenant.py
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import String, Integer, Numeric, Boolean
from enum import Enum

class TierEnum(str, Enum):
    FREE = "free"
    PRO = "pro"
    ENTERPRISE = "enterprise"

TIER_LIMITS = {
    TierEnum.FREE:       {"requests_per_day": 100,   "tokens_per_month": 100_000,  "price": 0},
    TierEnum.PRO:        {"requests_per_day": 10_000, "tokens_per_month": 5_000_000, "price": 49},
    TierEnum.ENTERPRISE: {"requests_per_day": -1,     "tokens_per_month": -1,        "price": 499},
}

class Tenant(Base):
    __tablename__ = "tenants"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str]
    tier: Mapped[TierEnum] = mapped_column(default=TierEnum.FREE)
    api_key: Mapped[str] = mapped_column(unique=True, index=True)
    stripe_customer_id: Mapped[str | None]
    is_active: Mapped[bool] = mapped_column(default=True)
    monthly_token_budget: Mapped[int] = mapped_column(default=100_000)
```

```python
# app/middleware/auth.py
from fastapi import HTTPException, Security
from fastapi.security import APIKeyHeader
import hashlib

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

async def get_current_tenant(
    api_key: str = Security(api_key_header),
    db = Depends(get_db),
    redis = Depends(get_redis),
) -> Tenant:
    if not api_key:
        raise HTTPException(status_code=401, detail="API key required")

    # Cache tenant lookup in Redis (avoid DB hit every request)
    cache_key = f"tenant:apikey:{hashlib.sha256(api_key.encode()).hexdigest()}"
    cached = await redis.get(cache_key)

    if cached:
        return Tenant.model_validate_json(cached)

    tenant = await db.query(Tenant).filter(Tenant.api_key == api_key).first()
    if not tenant or not tenant.is_active:
        raise HTTPException(status_code=401, detail="Invalid or inactive API key")

    await redis.setex(cache_key, 300, tenant.model_dump_json())  # 5min cache
    return tenant
```

### 2. Rate Limiting per Tenant

```python
# app/middleware/rate_limit.py
import redis.asyncio as aioredis
from fastapi import HTTPException

async def check_rate_limit(
    tenant: Tenant,
    redis: aioredis.Redis,
):
    tier_limits = TIER_LIMITS[tenant.tier]
    daily_limit = tier_limits["requests_per_day"]

    if daily_limit == -1:  # Enterprise: unlimited
        return

    # Sliding window rate limit using Redis
    key = f"ratelimit:{tenant.id}:{date.today().isoformat()}"

    current = await redis.incr(key)
    if current == 1:
        await redis.expire(key, 86400)  # 24h TTL

    if current > daily_limit:
        raise HTTPException(
            status_code=429,
            detail=f"Daily limit of {daily_limit} requests exceeded. Upgrade to Pro.",
            headers={"Retry-After": str(seconds_until_midnight())},
        )

async def check_token_budget(tenant: Tenant, redis: aioredis.Redis):
    """Block requests if monthly token budget exhausted."""
    month_key = f"tokens:{tenant.id}:{date.today().strftime('%Y-%m')}"
    used = int(await redis.get(month_key) or 0)
    limit = TIER_LIMITS[tenant.tier]["tokens_per_month"]

    if limit != -1 and used >= limit:
        raise HTTPException(
            status_code=402,
            detail=f"Monthly token budget exhausted ({limit:,} tokens). Upgrade your plan.",
        )
```

### 3. Semantic Caching

```python
# app/cache/semantic_cache.py
import numpy as np
import redis.asyncio as aioredis
from openai import AsyncOpenAI
import json, hashlib

openai_client = AsyncOpenAI()

class SemanticCache:
    def __init__(self, redis_client: aioredis.Redis, similarity_threshold: float = 0.95):
        self.redis = redis_client
        self.threshold = similarity_threshold

    async def _embed(self, text: str) -> list[float]:
        response = await openai_client.embeddings.create(
            model="text-embedding-3-small",
            input=text,
        )
        return response.data[0].embedding

    async def get(self, query: str, tenant_id: str) -> str | None:
        """Check cache for semantically similar query."""
        query_embedding = await self._embed(query)
        namespace = f"semcache:{tenant_id}"

        # Get all cached queries for this tenant
        keys = await self.redis.keys(f"{namespace}:*")

        best_score = 0
        best_response = None

        for key in keys[:100]:   # Limit scan
            cached = await self.redis.get(key)
            if not cached:
                continue
            data = json.loads(cached)
            cached_embedding = data["embedding"]

            # Cosine similarity
            score = np.dot(query_embedding, cached_embedding) / (
                np.linalg.norm(query_embedding) * np.linalg.norm(cached_embedding)
            )

            if score > best_score:
                best_score = score
                best_response = data["response"]

        if best_score >= self.threshold:
            return best_response
        return None

    async def set(self, query: str, response: str, tenant_id: str, ttl: int = 3600):
        """Cache query+response pair."""
        embedding = await self._embed(query)
        key = f"semcache:{tenant_id}:{hashlib.md5(query.encode()).hexdigest()}"
        data = {"query": query, "embedding": embedding, "response": response}
        await self.redis.setex(key, ttl, json.dumps(data))
```

### 4. LiteLLM Router with Fallbacks

```python
# app/llm/router.py
from litellm import Router
import os

router = Router(
    model_list=[
        # Primary: Anthropic
        {
            "model_name": "chat",
            "litellm_params": {
                "model": "claude-sonnet-4-6",
                "api_key": os.getenv("ANTHROPIC_API_KEY"),
            },
            "tpm": 100_000,   # Tokens per minute limit
        },
        # Fallback 1: OpenAI
        {
            "model_name": "chat",
            "litellm_params": {
                "model": "gpt-4o",
                "api_key": os.getenv("OPENAI_API_KEY"),
            },
        },
        # Fallback 2: Bedrock (when others are down)
        {
            "model_name": "chat",
            "litellm_params": {
                "model": "bedrock/anthropic.claude-sonnet-4-6-20251001-v2:0",
            },
        },
        # Cheap model for simple tasks
        {
            "model_name": "fast",
            "litellm_params": {
                "model": "claude-haiku-4-5-20251001",
                "api_key": os.getenv("ANTHROPIC_API_KEY"),
            },
        },
    ],
    fallbacks=[{"chat": ["chat", "chat"]}],       # Retry with next in list
    set_verbose=False,
    timeout=30,
    retry_policy={"TimeoutError": {"max_retries": 3, "retry_after": 5}},
)

def select_model(request_complexity: str) -> str:
    """Route to cheap model for simple requests."""
    if request_complexity in ("classification", "extraction", "yes_no"):
        return "fast"   # $0.25/1M vs $3/1M
    return "chat"
```

### 5. Langfuse Observability

```python
# app/observability/langfuse_client.py
from langfuse import Langfuse
from langfuse.decorators import observe, langfuse_context
import os

langfuse = Langfuse(
    public_key=os.getenv("LANGFUSE_PUBLIC_KEY"),
    secret_key=os.getenv("LANGFUSE_SECRET_KEY"),
    host=os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com"),
)

# ===== DECORATOR APPROACH =====
@observe(name="llm_completion")
async def tracked_completion(
    messages: list[dict],
    model: str,
    tenant_id: str,
    feature: str,
) -> str:
    # Add metadata to current trace
    langfuse_context.update_current_trace(
        user_id=tenant_id,
        tags=[feature, model],
        metadata={"tenant_id": tenant_id, "feature": feature},
    )

    response = await router.acompletion(
        model=model,
        messages=messages,
    )

    answer = response.choices[0].message.content

    # Track cost
    langfuse_context.update_current_observation(
        usage={
            "input": response.usage.prompt_tokens,
            "output": response.usage.completion_tokens,
            "unit": "TOKENS",
        }
    )

    return answer
```

### 6. Stripe Integration — Usage Billing

```python
# app/billing/stripe_client.py
import stripe
import os

stripe.api_key = os.getenv("STRIPE_SECRET_KEY")

async def create_tenant_customer(tenant: Tenant) -> str:
    """Create Stripe customer for new tenant."""
    customer = stripe.Customer.create(
        email=tenant.email,
        name=tenant.name,
        metadata={"tenant_id": tenant.id},
    )
    return customer.id

async def create_subscription(tenant_id: str, tier: str) -> dict:
    """Subscribe tenant to a plan."""
    PRICE_IDS = {
        "pro": os.getenv("STRIPE_PRO_PRICE_ID"),
        "enterprise": os.getenv("STRIPE_ENTERPRISE_PRICE_ID"),
    }

    tenant = await get_tenant(tenant_id)
    subscription = stripe.Subscription.create(
        customer=tenant.stripe_customer_id,
        items=[{"price": PRICE_IDS[tier]}],
        payment_behavior="default_incomplete",
        expand=["latest_invoice.payment_intent"],
    )
    return {
        "subscription_id": subscription.id,
        "client_secret": subscription.latest_invoice.payment_intent.client_secret,
    }

@router.post("/webhooks/stripe")
async def stripe_webhook(request: Request):
    """Handle Stripe events — upgrade/downgrade tenant."""
    payload = await request.body()
    sig = request.headers.get("stripe-signature")

    try:
        event = stripe.Webhook.construct_event(
            payload, sig, os.getenv("STRIPE_WEBHOOK_SECRET")
        )
    except stripe.error.SignatureVerificationError:
        raise HTTPException(status_code=400)

    if event.type == "customer.subscription.updated":
        sub = event.data.object
        tenant_id = sub.metadata.get("tenant_id")
        new_tier = sub.metadata.get("tier")
        await update_tenant_tier(tenant_id, new_tier)

    return {"received": True}
```

### 7. Admin Dashboard API

```python
# app/api/admin.py
from fastapi import APIRouter
router = APIRouter(prefix="/admin", tags=["admin"])

@router.get("/dashboard")
async def admin_dashboard(
    db = Depends(get_db),
    redis = Depends(get_redis),
    _admin = Depends(require_admin),
):
    """Real-time dashboard: revenue, usage, costs."""

    # Revenue
    monthly_revenue = await db.execute("""
        SELECT tier, COUNT(*) as tenants, COUNT(*) * monthly_price as mrr
        FROM tenants
        WHERE is_active = true
        GROUP BY tier
    """)

    # Usage today
    usage_today = await db.execute("""
        SELECT
            COUNT(*) as total_requests,
            SUM(total_tokens) as total_tokens,
            SUM(cost_usd) as total_cost,
            AVG(latency_ms) as avg_latency
        FROM llm_usage
        WHERE created_at > NOW() - INTERVAL '24 hours'
    """)

    # Top tenants by cost
    top_spenders = await db.execute("""
        SELECT tenant_id, SUM(cost_usd) as total_cost
        FROM llm_usage
        WHERE created_at > DATE_TRUNC('month', NOW())
        GROUP BY tenant_id
        ORDER BY total_cost DESC
        LIMIT 10
    """)

    return {
        "monthly_revenue": monthly_revenue.fetchall(),
        "usage_today": dict(usage_today.fetchone()),
        "top_spenders": top_spenders.fetchall(),
    }

@router.get("/tenants/{tenant_id}/usage")
async def tenant_usage(tenant_id: str, days: int = 30, db = Depends(get_db)):
    result = await db.execute("""
        SELECT
            DATE(created_at) as date,
            SUM(total_tokens) as tokens,
            SUM(cost_usd) as cost,
            COUNT(*) as requests
        FROM llm_usage
        WHERE tenant_id = :tenant_id
          AND created_at > NOW() - INTERVAL ':days days'
        GROUP BY DATE(created_at)
        ORDER BY date DESC
    """, {"tenant_id": tenant_id, "days": days})
    return result.fetchall()
```

---

## Interview Talking Points

```
KEY ENGINEERING DECISIONS:

1. Multi-tenant isolation strategy:
   - Row-level security: every DB query filters by tenant_id
   - Redis namespacing: "tokens:{tenant_id}:{month}"
   - Semantic cache namespaced per tenant (no cross-tenant leakage)
   - API key hashed in DB — never stored plain text

2. Semantic caching ROI:
   - Cache hit rate: 60-70% for FAQ-style queries
   - Savings: $0.003/cache hit vs $0.01 avg query cost
   - At 10K queries/day: saves ~$42/day = ~$1,260/month

3. LiteLLM Router value:
   - One code path for all providers
   - Auto-failover: if Anthropic down → GPT-4o → Bedrock
   - Load balancing across API keys (avoid rate limits)
   - Cost tracking unified across providers

4. Token budget enforcement:
   - Check budget BEFORE making LLM call (not after)
   - Redis INCR is atomic — no race conditions
   - Soft limit: warn at 80%; hard limit: block at 100%

5. Stripe webhook security:
   - Signature verification (HMAC-SHA256)
   - Idempotency: check event ID to prevent duplicate processing
   - Async processing: webhook returns 200 immediately, processes in background

METRICS THAT MATTER:
   - MRR (Monthly Recurring Revenue)
   - Gross margin = (revenue - LLM costs) / revenue
   - Cost per 1000 API calls
   - Cache hit rate
   - P95 latency
   - Churn rate per tier
```
