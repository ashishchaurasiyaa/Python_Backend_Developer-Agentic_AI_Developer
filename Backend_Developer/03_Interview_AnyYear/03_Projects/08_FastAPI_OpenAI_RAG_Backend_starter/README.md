# FastAPI + OpenAI RAG Backend (Multi-Tenant RAG-as-a-Service) — Starter

Spec: [../08_FastAPI_OpenAI_RAG_Backend.md](../08_FastAPI_OpenAI_RAG_Backend.md)

## What to build

Multi-tenant "ChatGPT for your docs" — document ingestion (PDF/DOCX/MD/HTML), hybrid search (pgvector + BM25 + Cohere rerank), streaming SSE answers with citations, semantic cache, usage quotas, and Stripe billing.  Target: 1M docs/tenant, p95 query < 2s.

## How to run

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Infrastructure
docker run -d --name pg -e POSTGRES_PASSWORD=dev -p 5432:5432 postgres:16
docker run -d --name redis -p 6379:6379 redis:7
docker run -d --name kafka -p 9092:9092 apache/kafka:3.7.0

# Enable pgvector extension (connect to Postgres and run):
# CREATE EXTENSION vector;

# Set environment variables
export OPENAI_API_KEY=sk-...
export ANTHROPIC_API_KEY=sk-ant-...
export COHERE_API_KEY=...
export DATABASE_URL=postgresql+asyncpg://postgres:dev@localhost/ragdb
export REDIS_URL=redis://localhost:6379/0

uvicorn main:app --reload

# Celery ingest worker
celery -A workers.ingest worker --concurrency=4
```

Open http://localhost:8000/docs.

## Milestones (from spec)

- **Phase 1** — FastAPI skeleton, multi-tenant JWT, Postgres schema, document upload (S3), Stripe tier check
- **Phase 2** — Kafka/Celery ingestion: parse → chunk (token-aware) → embed (batch) → pgvector HNSW index
- **Phase 3** — Hybrid search: pgvector cosine + BM25 (`tsvector`) + RRF merge + Cohere rerank
- **Phase 4** — `/query` and `/query/stream` (SSE), citation tracking, semantic cache (pgvector similarity on queries), cost tracking
- **Phase 5** — Row-Level Security tenant isolation, document permissions, API key management, rate limiting
- **Phase 6** — RAGAS evaluation pipeline, Langfuse integration, Prometheus metrics
- **Phase 7** — Dockerfile, K8s Helm chart, Terraform (AWS/GCP), CI/CD, k6 load test

## Key patterns to implement

1. Hybrid search SQL: `WITH vector_search AS (...), text_search AS (...), rrf AS (RRF fusion)` → Cohere rerank top-20 → return top-k.
2. Streaming: `async with anthropic.messages.stream(...) as stream: async for token in stream.text_stream: yield SSE event`.
3. Semantic cache: embed query → cosine search in `semantic_cache` table (`threshold=0.97`) → return cached answer.
4. Per-tenant cost tracking: `Redis HINCRBYFLOAT usage:tenant:{id}:{today} cost <usd>`; check before each LLM call.
5. Chunks table partitioned by `HASH (tenant_id)` for horizontal sharding.
