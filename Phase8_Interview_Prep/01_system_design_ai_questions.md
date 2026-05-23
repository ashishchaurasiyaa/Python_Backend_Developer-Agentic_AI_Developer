# System Design — AI/Backend Interview Questions

## How to Answer System Design Questions
```
Framework (RADIO):
1. Requirements     — functional + non-functional, clarify scope
2. API Design       — endpoints, request/response schemas
3. Data Model       — tables, indexes, relationships
4. Implementation   — components, services, flow
5. Optimization     — scale, caching, bottlenecks
```

---

## Q1: Design a RAG-based Customer Support Chatbot (10M users)

**Answer:**
```
REQUIREMENTS:
  Functional:
    - User asks question → AI answers from knowledge base
    - Multi-turn conversation (context aware)
    - Source citations in answers
    - Escalation to human agent
  Non-functional:
    - Latency < 2s for 95th percentile
    - 10M users, 100K concurrent
    - Knowledge base: 500K documents, updated daily
    - Uptime 99.9%

ARCHITECTURE:
  ┌─────────────┐    ┌───────────┐    ┌──────────────────┐
  │   Client    │───►│  FastAPI  │───►│  RAG Pipeline    │
  │  (React)    │    │  Gateway  │    │                  │
  └─────────────┘    └───────────┘    │  1. Retriever    │
                                      │     pgvector      │
  ┌─────────────┐    ┌───────────┐    │  2. Reranker     │
  │  Redis      │    │  Celery   │    │     CrossEncoder  │
  │  Cache +    │    │  Workers  │    │  3. LLM           │
  │  Session    │    │ (indexing)│    │     Claude Sonnet │
  └─────────────┘    └───────────┘    └──────────────────┘

DATA FLOW:
  1. User sends message
  2. Session history load (Redis)
  3. Semantic cache check — similar query answered before?
  4. Query embedding (text-embedding-3-small)
  5. Hybrid search: pgvector (dense) + tsvector (sparse)
  6. Rerank top 10 → top 3 with CrossEncoder
  7. Claude Sonnet generates answer with citations
  8. Stream response to user via SSE
  9. Save to conversation history (Redis + PostgreSQL)

DATABASE SCHEMA:
  documents(id, content, embedding vector(1536), metadata jsonb, updated_at)
  conversations(id, user_id, created_at, metadata)
  messages(id, conversation_id, role, content, sources jsonb, created_at)
  users(id, email, tier, created_at)

  Indexes:
  - documents: HNSW on embedding, tsvector GIN index
  - messages: (conversation_id, created_at)
  - conversations: (user_id, created_at)

CACHING LAYERS:
  L1: Semantic cache (Redis) — similar queries, 1hr TTL
  L2: Document cache — recently accessed chunks
  L3: Session history — last 20 messages

SCALING:
  - Read replicas for pgvector queries
  - Horizontal scaling: FastAPI behind load balancer
  - Celery for background: nightly document re-indexing
  - CDN for static assets

COST OPTIMIZATION:
  - Route simple FAQs → Claude Haiku ($0.25/1M vs $3/1M)
  - Semantic cache → 60-70% cache hit rate
  - Batch document embedding → Batch API (50% cheaper)
  - Prompt caching → repeated system prompt (90% cheaper)

MONITORING:
  - RAGAS scores weekly: faithfulness, relevancy
  - Latency P50/P95/P99 per endpoint
  - Cost per conversation by user tier
  - Human escalation rate (quality signal)
```

---

## Q2: Design a Multi-Agent Code Review System

**Answer:**
```
REQUIREMENTS:
  - PR submitted → automated review comments
  - Multiple specialized agents (security, performance, style)
  - Human-in-the-loop for critical issues
  - Supports Python, JavaScript, Go
  - < 5 min review time for PRs < 1000 lines

AGENT ARCHITECTURE (LangGraph):

  GitHub Webhook → Orchestrator Agent
                        │
          ┌─────────────┼─────────────┐
          ▼             ▼             ▼
  Security Agent  Performance    Style Agent
  (OWASP checks)  Agent          (PEP8/ESLint)
          │             │             │
          └─────────────┼─────────────┘
                        ▼
               Synthesizer Agent
                        │
               ┌────────┴────────┐
               ▼                 ▼
        Auto-approve       Human Review
        (minor issues)     Queue (critical)

AGENT DEFINITIONS:
  Orchestrator:
    - Splits PR into file chunks
    - Routes to specialized agents in parallel
    - Tracks state with LangGraph checkpointing

  Security Agent:
    - Tools: SAST scanner, CVE lookup, OWASP checker
    - Model: Claude Opus (most critical → best model)
    - Output: SecurityIssue(severity, location, description, fix)

  Performance Agent:
    - Tools: complexity analyzer, query detector (N+1 finder)
    - Model: Claude Sonnet
    - Output: PerformanceIssue(type, impact, suggestion)

  Style Agent:
    - Tools: ruff/eslint runner
    - Model: Claude Haiku (simple → cheapest)
    - Output: StyleIssue(rule, line, autofix)

STATE MANAGEMENT:
  class ReviewState(TypedDict):
      pr_id: str
      files: list[str]
      diff: str
      security_issues: list[SecurityIssue]
      performance_issues: list[PerformanceIssue]
      style_issues: list[StyleIssue]
      decision: Literal["approve", "request_changes", "human_review"]
      review_comment: str

HUMAN-IN-THE-LOOP:
  if any(issue.severity == "CRITICAL" for issue in security_issues):
      interrupt({"reason": "Critical security issue", "issues": critical_issues})
      # Waits for human to approve or reject

COST PER REVIEW:
  Small PR (<100 lines):  ~$0.05
  Medium PR (100-500):    ~$0.20
  Large PR (>500 lines):  ~$0.50

GITHUB INTEGRATION:
  - Webhook: PR opened/updated → trigger review
  - GitHub API: post inline comments at exact line numbers
  - Status check: block merge on CRITICAL issues
```

---

## Q3: Design an LLM Cost Monitoring System

**Answer:**
```
REQUIREMENTS:
  - Track cost per user, per feature, per model
  - Real-time budget alerts
  - Per-tenant cost allocation (SaaS)
  - Historical analysis + forecasting

COMPONENTS:
  ┌──────────────┐
  │  FastAPI App │──► LLM Call ──► Anthropic/OpenAI
  │              │                      │
  │  Middleware  │◄─── Usage Data ──────┘
  └──────┬───────┘
         │ async
         ▼
  ┌──────────────┐    ┌───────────────┐
  │  Kafka/Redis │───►│  Cost Service │
  │  (event bus) │    │  (FastAPI)    │
  └──────────────┘    └───────┬───────┘
                              │
              ┌───────────────┼───────────────┐
              ▼               ▼               ▼
       ┌─────────┐    ┌─────────────┐  ┌──────────┐
       │TimescaleDB│  │  Redis      │  │Prometheus│
       │(raw data)│  │(real-time   │  │(metrics) │
       └─────────┘    │ aggregates) │  └──────────┘
                      └─────────────┘

DATABASE:
  llm_usage (TimescaleDB hypertable for time-series):
    - time, user_id, tenant_id, feature, model
    - prompt_tokens, completion_tokens, cost_usd
    - latency_ms, cache_hit (bool)

  budgets:
    - tenant_id, period (daily/monthly), limit_usd
    - alert_threshold_pct (e.g., 80%)

ALERT PIPELINE:
  1. Usage event arrives
  2. Redis INCR for real-time spend
  3. Compare with budget threshold
  4. If exceeded → Slack/email alert
  5. If 100% → rate limit or block LLM calls

API ENDPOINTS:
  GET /costs/users/{user_id}?days=30
  GET /costs/features?start=2026-05-01&end=2026-05-31
  GET /costs/tenants/{tenant_id}/dashboard
  POST /budgets/{tenant_id}
  GET /costs/forecast?horizon=30

MATERIALIZED VIEWS (TimescaleDB):
  daily_costs: aggregated per day per feature per model
  monthly_costs: billing summary per tenant

MULTI-TENANT ISOLATION:
  - Row-level security in PostgreSQL (tenant_id filter)
  - Redis namespacing: "tenant:{id}:cost:daily"
  - Each tenant sees ONLY their data
```

---

## Q4: Design a Semantic Search Engine (100M documents)

**Answer:**
```
SCALE REQUIREMENTS:
  - 100M documents, 1536-dim vectors
  - 100K QPS (queries per second)
  - < 100ms P95 latency
  - Real-time document updates

STORAGE CALCULATION:
  100M × 1536 dims × 4 bytes (float32) = 614 GB raw vectors
  With HNSW index overhead (~1.5x): ~900 GB
  → Need distributed vector DB (not single pgvector instance)

ARCHITECTURE:
  ┌──────────────────────────────────────────────┐
  │                API Layer                      │
  │         FastAPI + Redis Rate Limiting         │
  └──────────────────┬───────────────────────────┘
                     │
       ┌─────────────┼──────────────┐
       ▼             ▼              ▼
  ┌─────────┐  ┌──────────┐  ┌──────────┐
  │  Shard 1 │  │  Shard 2 │  │  Shard N │   ← Qdrant cluster
  │ (25M docs)│  │ (25M docs)│  │ (25M docs)│
  └─────────┘  └──────────┘  └──────────┘
       │             │              │
       └─────────────┼──────────────┘
                     ▼
            ┌─────────────────┐
            │  Result Merger  │
            │ + Reranker      │
            └─────────────────┘

QUERY FLOW:
  1. User query → embedding (GPU-accelerated, batch)
  2. Parallel search across all shards (fan-out)
  3. Collect top-K from each shard (K * N total)
  4. Merge + deduplicate
  5. Rerank top-50 → return top-10
  6. Cache result in Redis (1hr TTL)

EMBEDDING SERVICE:
  - Dedicated GPU instances for embedding generation
  - Model: text-embedding-3-small (OpenAI) or bge-large-en-v1.5 (local)
  - Batching: group 100 queries → single API call
  - Async queue for high-throughput periods

INDEXING PIPELINE (Kafka + Celery):
  Document added → Kafka topic
  Celery worker pulls → generate embedding → upsert to Qdrant
  Near-real-time (< 30s delay for new documents)

SHARDING STRATEGY:
  - Hash-based: document_id % N_shards
  - OR: Category-based (e.g., by domain/language)
  - Qdrant native clustering handles this

CACHING:
  - Semantic cache: exact + near-duplicate query results (Redis)
  - Popular queries: pre-computed results stored
  - Embedding cache: same text → same embedding (Redis)
```

---

## Q5: Common Follow-up Questions

**Answer:**
```
Q: How would you handle LLM rate limits in production?
A: 
  1. LiteLLM Router with multiple API keys
  2. Exponential backoff + jitter (tenacity)
  3. Request queue (Redis) for burst traffic
  4. Fallback to different provider (Claude → GPT-4o)
  5. Tiered users: premium = priority queue

Q: How do you ensure RAG answer quality doesn't degrade?
A:
  1. RAGAS evaluation on golden dataset weekly
  2. Faithfulness score monitoring (hallucination detection)
  3. User feedback signals (thumbs up/down)
  4. A/B testing prompts → champion/challenger
  5. Automated alerts when score drops > 5%

Q: How would you reduce latency in your LLM pipeline?
A:
  1. Stream responses (SSE) — perceived latency drops
  2. Semantic cache — 60-70% cache hit → near-zero latency
  3. Smaller model for simple queries (Haiku < Sonnet < Opus)
  4. Parallel tool execution in agents
  5. Prompt compression (remove redundant tokens)
  6. Regional API endpoints (us-east vs eu-west)

Q: How to handle context window overflow?
A:
  1. Sliding window: keep last N messages
  2. Summarization: old history → compact summary
  3. Reranking: keep only most relevant chunks (not all retrieved)
  4. Map-reduce: process large docs in chunks, combine
  5. Parent-child chunking: small retrieve, large context

Q: Multi-tenant AI SaaS cost isolation?
A:
  1. Per-tenant API key budget limits
  2. Rate limiting per tenant tier (Free/Pro/Enterprise)
  3. Cost tracking with tenant_id in every LLM call metadata
  4. Monthly budget reset + overage notifications
  5. Separate vector namespaces per tenant
```
