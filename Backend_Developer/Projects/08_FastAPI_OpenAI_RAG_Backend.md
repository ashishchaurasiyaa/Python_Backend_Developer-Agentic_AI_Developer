# Project 8: FastAPI + OpenAI RAG Backend (Production SaaS)

**Stack:** FastAPI + PostgreSQL + pgvector + OpenAI/Claude + Redis + Celery + Cohere Rerank + Stripe + Docker + AWS/GCP
**Build Time:** 3-4 weeks
**Difficulty:** ⭐⭐⭐⭐⭐ (Full-stack AI engineering)
**Resume Strength:** ⭐⭐⭐⭐⭐ (Hottest skillset in 2026)

---

## 1. Project Overview & Business Problem

### What it is
A multi-tenant **RAG-as-a-Service** platform — like "ChatGPT for your docs". Companies upload documents (PDFs, Notion, web), users ask natural language questions, system returns grounded answers with citations.

### Why build this
- **#1 AI use case in enterprise** (2026) — most companies want this for internal knowledge bases
- **Demonstrates full AI engineering** — embeddings, vector search, hybrid retrieval, reranking, LLM orchestration, streaming
- **Resume gold** — backend + AI + scaling all in one
- **Productizable** — can pitch as actual SaaS

### Real-world analogues
- Glean
- Notion AI
- Mendable
- Vectara
- Hebbia

---

## 2. Requirements

### Functional
- **Document ingestion**: Upload PDFs, DOCX, MD, HTML, scrape URLs
- **Multi-tenant**: Per-organization knowledge bases, isolated
- **Query API**: Natural language → answer with citations
- **Streaming**: SSE token-by-token responses
- **Hybrid search**: Vector + keyword (BM25) + rerank
- **Chat sessions**: Multi-turn conversations with history
- **User permissions**: Who can access which documents
- **Re-ingestion**: Detect document changes, re-embed
- **Evaluations**: RAGAS metrics tracked per deployment
- **Citation tracking**: Every answer links back to source chunks
- **API + Web UI**: REST API for integrations + minimal web UI for testing

### Non-Functional
- 1M documents per tenant
- 10K queries/day per tenant
- p95 query latency < 2s (including LLM)
- 99.9% uptime
- Cost < $0.01/query (avg)
- GDPR + India DPDP compliant
- SOC 2 Type II ready

---

## 3. Scale Estimation

| Metric | Number |
|---|---|
| Tenants | 1000 |
| Documents/tenant | 100K avg |
| Total chunks | 100K × 100 × 1000 = 10B |
| Embedding storage | 1.5 KB × 10B = 15 TB |
| Queries/day | 10M |
| QPS peak | 500 |
| LLM cost (Sonnet, ~1K tokens) | $25K/day = $9M/year |
| With caching + smart routing | $5K/day = $1.8M/year |

---

## 4. Architecture

```
┌─────────────────────────────────────┐
│  Web Client / API Consumer           │
└──────────────┬──────────────────────┘
               │
        ┌──────▼──────┐
        │  CDN / WAF  │ (Cloudflare)
        └──────┬──────┘
               │
        ┌──────▼──────┐
        │ API Gateway │
        │ (Kong/Caddy)│ rate limit, auth
        └──────┬──────┘
       ┌───────┴────────┐
       │                │
 ┌─────▼─────┐    ┌─────▼─────┐
 │ Query     │    │ Ingestion │
 │ Service   │    │ Service   │
 │ (FastAPI) │    │ (FastAPI) │
 └─────┬─────┘    └─────┬─────┘
       │                │
       │           ┌────▼────┐
       │           │  Kafka  │ topic: docs.ingest
       │           └────┬────┘
       │                │
       │      ┌─────────▼─────────┐
       │      │  Celery Workers   │
       │      │  - parse           │
       │      │  - chunk           │
       │      │  - embed (batch)   │
       │      └─────────┬─────────┘
       │                │
       └────────────────┼──────────────┐
                        │              │
                ┌───────▼──────┐ ┌─────▼──────┐
                │  PostgreSQL  │ │   S3       │
                │  pgvector    │ │ (files)    │
                │  + BM25      │ └────────────┘
                └──────────────┘
                        │
                ┌───────▼──────┐
                │   Redis      │
                │ - sessions   │
                │ - sem cache  │
                │ - quotas     │
                └──────────────┘

External:
- OpenAI / Anthropic (LLM + embeddings)
- Cohere (reranking)
- Stripe (billing)
- LangSmith / Langfuse (observability)
```

---

## 5. Implementation Phases

### Phase 1: Core API (Week 1)
- [ ] FastAPI app skeleton with multi-tenant auth (JWT)
- [ ] Postgres schema + Alembic migrations (users, tenants, documents, chunks, queries)
- [ ] Document upload endpoint (S3)
- [ ] Basic Stripe integration (tier check)
- [ ] OpenAPI docs

### Phase 2: Ingestion Pipeline (Week 1-2)
- [ ] Kafka producer + Celery workers
- [ ] PDF/DOCX/MD/HTML parsers
- [ ] Token-aware paragraph chunking
- [ ] OpenAI embedding batch processing
- [ ] pgvector HNSW index
- [ ] Re-ingestion on document update

### Phase 3: Retrieval (Week 2)
- [ ] Vector search via pgvector cosine
- [ ] BM25 full-text search (PostgreSQL `tsvector`)
- [ ] RRF hybrid scoring
- [ ] Cohere rerank integration
- [ ] Query rewriting (HyDE)

### Phase 4: Query API + Streaming (Week 2-3)
- [ ] Chat sessions (conversation history in Postgres)
- [ ] LLM call with retrieved context
- [ ] SSE streaming responses
- [ ] Citation tracking in response
- [ ] Semantic cache (Redis + pgvector)
- [ ] Cost tracking per query

### Phase 5: Multi-Tenancy + Permissions (Week 3)
- [ ] Tenant isolation (Row-Level Security)
- [ ] Document-level permissions (sharing)
- [ ] API key management per tenant
- [ ] Usage quotas + rate limiting

### Phase 6: Evaluation + Monitoring (Week 3-4)
- [ ] RAGAS evaluation pipeline
- [ ] LangSmith/Langfuse integration
- [ ] Prometheus metrics
- [ ] Grafana dashboards
- [ ] Sentry error tracking

### Phase 7: Production-Ready (Week 4)
- [ ] Dockerfile + docker-compose
- [ ] Kubernetes Helm chart
- [ ] Terraform (AWS/GCP) for infra
- [ ] CI/CD (GitHub Actions)
- [ ] Load testing (k6)
- [ ] Security audit (Bandit, ZAP)
- [ ] Documentation

---

## 6. Key Code Patterns to Implement

```python
# Pattern 1: Hybrid search with metadata filter
async def search(tenant_id, query, filter, top_k=5):
    emb = await embed(query)
    # Vector + BM25 with RRF fusion
    candidates = await db.fetch_all(HYBRID_SQL, ...)
    return await rerank(query, candidates, top_k)

# Pattern 2: Streaming with citations
async def stream_answer(query, chunks):
    async with anthropic.messages.stream(...) as stream:
        async for token in stream.text_stream:
            yield f"data: {json.dumps({'token': token})}\n\n"
        yield f"data: {json.dumps({'type':'citations', 'sources':[c.id for c in chunks]})}\n\n"

# Pattern 3: Semantic cache check
async def query_with_cache(question):
    cache_hit = await check_semantic_cache(question, threshold=0.97)
    if cache_hit:
        return cache_hit
    answer = await rag_pipeline(question)
    await save_to_cache(question, answer)
    return answer

# Pattern 4: Per-tenant LLM cost tracking
async def track_usage(tenant_id, model, in_tok, out_tok):
    cost = calc_cost(model, in_tok, out_tok)
    await redis.hincrbyfloat(f"usage:tenant:{tenant_id}:{today}", "cost", cost)
    if cost > daily_cap(tenant_id):
        raise HTTPException(402, "Daily quota exceeded")
```

---

## 7. Database Schema (Highlights)

```sql
CREATE EXTENSION vector;

CREATE TABLE tenants (
    id UUID PRIMARY KEY,
    name TEXT,
    plan TEXT,  -- free/pro/enterprise
    api_key_hash TEXT UNIQUE,
    monthly_quota_queries INT,
    monthly_quota_docs INT
);

CREATE TABLE documents (
    id UUID PRIMARY KEY,
    tenant_id UUID REFERENCES tenants(id),
    filename TEXT,
    source_url TEXT,
    content_hash TEXT,   -- detect changes
    status TEXT,         -- processing/ready/failed
    indexed_at TIMESTAMPTZ,
    permissions JSONB    -- {users: [...], groups: [...]}
);

CREATE TABLE chunks (
    id UUID PRIMARY KEY,
    document_id UUID REFERENCES documents(id) ON DELETE CASCADE,
    tenant_id UUID NOT NULL,
    chunk_index INT,
    content TEXT,
    embedding vector(1536),
    metadata JSONB,
    token_count INT
) PARTITION BY HASH (tenant_id);  -- shard by tenant

CREATE INDEX ON chunks USING hnsw (embedding vector_cosine_ops);
CREATE INDEX ON chunks USING gin (to_tsvector('english', content));

CREATE TABLE chat_sessions (
    id UUID PRIMARY KEY,
    tenant_id UUID,
    user_id UUID,
    title TEXT,
    created_at TIMESTAMPTZ
);

CREATE TABLE messages (
    id UUID PRIMARY KEY,
    session_id UUID REFERENCES chat_sessions(id),
    role TEXT,
    content TEXT,
    citations JSONB,
    tokens_in INT,
    tokens_out INT,
    cost_usd NUMERIC(10, 6),
    created_at TIMESTAMPTZ
);

CREATE TABLE semantic_cache (
    id UUID PRIMARY KEY,
    tenant_id UUID,
    query_hash TEXT,
    query_embedding vector(1536),
    answer TEXT,
    citations JSONB,
    hit_count INT DEFAULT 0,
    created_at TIMESTAMPTZ
);
CREATE INDEX ON semantic_cache USING hnsw (query_embedding vector_cosine_ops);
```

---

## 8. Tech Decisions to Make

| Decision | Options | Recommendation |
|---|---|---|
| Vector DB | pgvector / Pinecone / Weaviate | **pgvector** (simpler ops) |
| LLM provider | OpenAI / Anthropic / both | **Both** (LiteLLM proxy) |
| Embedding | OpenAI / Voyage / BGE local | **OpenAI text-embedding-3-small** |
| Reranker | Cohere / BGE local | **Cohere** initially |
| Auth | Auth0 / custom JWT | **Custom JWT** |
| Billing | Stripe / Paddle | **Stripe** |
| File storage | S3 / GCS / R2 | **S3 / R2** |
| Observability | LangSmith / Langfuse | **Langfuse** (open-source) |
| Queue | Celery / RQ / Arq | **Celery** (mature) |
| Deploy | K8s / ECS / Cloud Run | **K8s** (most production-realistic) |

---

## 9. Testing Strategy

```python
# Unit tests
def test_chunking():
    chunks = chunk_text(text, max_tokens=500)
    assert all(count_tokens(c) <= 500 for c in chunks)

# Integration tests
async def test_e2e_ingest_query():
    doc_id = await upload_test_pdf()
    await wait_for_ingestion(doc_id)
    result = await query("What does the test pdf say?", tenant_id)
    assert "expected phrase" in result.answer
    assert len(result.citations) > 0

# RAGAS eval
def test_eval_score_above_threshold():
    scores = evaluate_rag(test_questions)
    assert scores["faithfulness"] > 0.85
    assert scores["context_precision"] > 0.75

# Load tests (k6)
# 100 concurrent users, 5 min, assert p95 < 2s
```

---

## 10. Cost Estimation (Production)

**Per tenant per month (10K queries):**

| Component | Cost |
|---|---|
| LLM (Sonnet, mixed) | $50 |
| Embeddings (initial 100K docs) | $200 one-time |
| Embedding (queries) | $1 |
| Reranking (Cohere) | $25 |
| Compute (FastAPI, K8s) | $50 |
| PostgreSQL (RDS) | $100 |
| Redis | $30 |
| S3 storage | $20 |
| **Total per tenant** | **$276/month** |

**Charge tier examples:**
- Starter ($99/mo): 1K queries, 1K docs
- Pro ($499/mo): 10K queries, 100K docs
- Enterprise ($2500+/mo): unlimited + dedicated infra

---

## 11. Stretch Goals

- [ ] Slack/Notion/Confluence connectors (auto-sync docs)
- [ ] Multi-modal RAG (images, tables)
- [ ] GraphRAG for entity-rich corpora
- [ ] Agent mode (LLM picks which docs to retrieve)
- [ ] Fine-tuned embeddings on domain corpus
- [ ] Privacy mode (local LLM via vLLM)
- [ ] Mobile SDK (iOS/Android)
- [ ] Browser extension (highlight any text → RAG)
- [ ] Compliance: SOC 2 audit, ISO 27001

---

## 12. Resume Bullets (after building)

- Built **multi-tenant RAG SaaS** serving 1M+ documents per tenant with sub-2-second query latency
- Implemented **hybrid search** (pgvector + BM25 + Cohere reranking) achieving 89% faithfulness on RAGAS
- Designed **semantic caching layer** reducing LLM costs by 35% on repeat queries
- Engineered **streaming SSE pipeline** with citation tracking across 10K daily queries
- Deployed on **Kubernetes** with Terraform IaC, achieving 99.9% uptime SLO
- Integrated **Stripe billing** with usage-based quotas + per-tenant rate limiting
- Built **RAGAS evaluation pipeline** preventing quality regressions in CI

---

## 13. Related Resources
- `Phase2_FastAPI/34_rag_backend_architecture.md` — implementation deep dive
- `Phase2_FastAPI/31_llm_integration_fastapi.md` — LLM patterns
- `Phase2_FastAPI/33_prompt_injection_security.md` — security
- `Phase2_Database/06_pgvector_schema_design.md` — pgvector
- `Phase2_Caching/06_semantic_caching_llm.md` — cache layer
- `PythonBackend_SystemDesign/HLD_Problems/Design_RAG_System.md` — HLD reference
- `Phase3_Security/17_india_dpdp_compliance.md` — compliance for India
