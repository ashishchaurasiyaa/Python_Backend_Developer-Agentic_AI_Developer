# Project 4 Starter — Production AI API (Mini SaaS)

Spec file: [../04_project4_production_ai_saas.md](../04_project4_production_ai_saas.md)

## How to Run

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Set env vars (optional — runs in placeholder mode without them)
export ANTHROPIC_API_KEY=sk-ant-...
export OPENAI_API_KEY=sk-...
export REDIS_URL=redis://localhost:6379
export DATABASE_URL=postgresql+asyncpg://...
export STRIPE_SECRET_KEY=sk_test_...
export LANGFUSE_PUBLIC_KEY=...
export LANGFUSE_SECRET_KEY=...

# 3. Run the skeleton
python main.py
```

## Milestones

| # | Milestone | Key Files |
|---|-----------|-----------|
| 1 | Multi-tenant DB model + API key hashing | `app/models/tenant.py` |
| 2 | Auth middleware: API key → Tenant (Redis cache) | `app/middleware/auth.py` |
| 3 | Rate limiting per tier (sliding window, Redis INCR) | `app/middleware/rate_limit.py` |
| 4 | Token budget enforcement (check before LLM call) | `app/middleware/rate_limit.py` |
| 5 | LiteLLM Router: Claude → GPT-4o → Bedrock fallback | `app/llm/router.py` |
| 6 | Semantic cache (Redis + cosine similarity) | `app/cache/semantic_cache.py` |
| 7 | Langfuse observability decorator | `app/observability/langfuse_client.py` |
| 8 | Stripe subscription + webhook handler | `app/billing/stripe_client.py` |
| 9 | Admin dashboard API (MRR, usage, top spenders) | `app/api/admin.py` |

## Stack

FastAPI + LiteLLM + Redis + Langfuse + Stripe + Multi-tenant PostgreSQL
