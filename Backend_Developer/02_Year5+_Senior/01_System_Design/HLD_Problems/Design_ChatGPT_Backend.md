# Design ChatGPT-Style Backend

---

## 1. Requirements

### Functional
- User can start new conversation or continue existing
- Send messages, receive AI response (text-only for V1, multimodal V2)
- **Token-by-token streaming** (SSE) for low TTFT
- Conversation history persists across sessions
- Multiple models (GPT-4o, Claude Opus, cheap fallback)
- File upload + RAG over user's documents
- Code execution sandbox (V2)
- Multi-device sync (web, iOS, Android)
- Free tier (limited) + Plus tier (unlimited, faster)
- Stop generation mid-stream
- Regenerate response

### Non-Functional
- **100M MAU, 25M DAU**
- **10M concurrent users at peak**
- TTFT (Time To First Token) < 1s P95
- Tokens/sec ≥ 30 (faster than reading speed)
- Conversation history available forever
- 99.95% uptime
- GDPR + India DPDP compliant (data residency)
- Cost-efficient: avg cost/user/month < $0.50

---

## 2. Scale Estimation

| Metric | Calculation | Result |
|---|---|---|
| Messages/day | 25M DAU × 20 msg/user | 500M msg/day |
| Messages/sec (peak) | 500M / 86400 × 3 (peak factor) | ~17K msg/sec |
| Concurrent streams | 10M × 5% chatting | 500K streams |
| LLM tokens/day (input + output) | 500M × 1000 avg tokens | 500B tokens/day |
| LLM cost (Sonnet @ $5/M tokens avg) | 500B × $5 / 1M | $2.5M/day = $912M/year |
| Storage (conversations) | 500M × 5KB | 2.5 TB/day = 912 TB/year |
| Embeddings storage (RAG) | 50M docs × 100 chunks × 1.5KB | 7.5 TB |
| Redis memory (sessions) | 10M × 10KB | 100 GB |

**Implication:** LLM cost dominates ($75M+/month). Caching + smart routing essential.

---

## 3. High-Level Architecture

```
                                    ┌──────────────┐
   Clients (Web/iOS/Android) ──────→│  CDN/Edge    │ (Cloudflare)
                                    └──────┬───────┘
                                           │ WSS / HTTPS
                                    ┌──────▼───────┐
                                    │ API Gateway  │ auth, rate limit
                                    └──────┬───────┘
                       ┌───────────────────┼────────────────────┐
                       │                   │                    │
              ┌────────▼────────┐  ┌──────▼────────┐  ┌────────▼────────┐
              │ Chat Service    │  │ Conversation  │  │ File / RAG       │
              │ (FastAPI)       │  │ Service       │  │ Service          │
              │ - streaming     │  │ - history     │  │ - ingest         │
              │ - model routing │  │ - search      │  │ - retrieve       │
              └────────┬────────┘  └──────┬────────┘  └────────┬────────┘
                       │                   │                    │
        ┌──────────────┼───────────────────┼────────────────────┘
        │              │                   │
┌───────▼─────┐  ┌─────▼──────┐    ┌──────▼─────┐
│ LLM Router  │  │ Redis      │    │ Postgres   │
│ (LiteLLM)   │  │ - sessions │    │ - convos   │
│ - failover  │  │ - cache    │    │ - users    │
│ - cost opt  │  │ - quota    │    │ - billing  │
└───┬─────┬───┘  └────────────┘    └────────────┘
    │     │
┌───▼─┐ ┌─▼───┐    ┌──────────┐    ┌──────────┐
│OpenAI│ │Anthr│    │ pgvector │    │   S3     │
│  GPT │ │opic │    │ (RAG)    │    │ (files,  │
└─────┘ └─────┘    └──────────┘    │  media)  │
                                    └──────────┘
                       │
              ┌────────▼─────────┐
              │  Kafka           │ ← async events
              │  - chat_logs     │   (analytics, audit)
              │  - llm_usage     │
              └──────────────────┘
```

---

## 4. Core Components

### 4.1 Chat Service — Streaming endpoint

```python
from fastapi import FastAPI, Depends, HTTPException
from fastapi.responses import StreamingResponse
from anthropic import AsyncAnthropic
from openai import AsyncOpenAI
import json
import asyncio
from uuid import uuid4, UUID

app = FastAPI()

class ChatRequest(BaseModel):
    conversation_id: UUID | None = None
    message: str
    model: str = "claude-opus-4-7"
    attachments: list[str] = []  # file IDs

@app.post("/chat/stream")
async def chat_stream(
    req: ChatRequest,
    user: User = Depends(get_current_user),
):
    # 1. Quota check
    await enforce_quota(user)

    # 2. Get or create conversation
    conv_id = req.conversation_id or uuid4()
    history = await load_history(conv_id, user.id) if req.conversation_id else []

    # 3. RAG context (if attachments)
    rag_context = await retrieve_rag(req.message, req.attachments) if req.attachments else ""

    # 4. Build messages array
    system = build_system_prompt(user, rag_context)
    messages = history + [{"role": "user", "content": req.message}]

    # 5. Save user message immediately (so refresh shows it)
    await save_message(conv_id, user.id, "user", req.message)

    # 6. Stream from LLM
    async def stream():
        assistant_text = []
        input_tokens, output_tokens = 0, 0

        try:
            async with anthropic.messages.stream(
                model=req.model,
                system=system,
                messages=messages,
                max_tokens=4096,
            ) as stream:
                # First event: conversation ID (so client can reload)
                yield f"data: {json.dumps({'type':'meta','conversation_id':str(conv_id)})}\n\n"

                async for text in stream.text_stream:
                    assistant_text.append(text)
                    yield f"data: {json.dumps({'type':'token','text':text})}\n\n"

                final = await stream.get_final_message()
                input_tokens = final.usage.input_tokens
                output_tokens = final.usage.output_tokens

                yield f"data: {json.dumps({'type':'done','input_tokens':input_tokens,'output_tokens':output_tokens})}\n\n"

        except asyncio.CancelledError:
            # Client disconnected mid-stream — still save partial
            pass
        finally:
            # Save assistant message + track usage
            full_text = "".join(assistant_text)
            await save_message(conv_id, user.id, "assistant", full_text, model=req.model)
            await track_usage(user.id, req.model, input_tokens, output_tokens)

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={
            "X-Accel-Buffering": "no",  # disable Nginx buffering
            "Cache-Control": "no-cache",
        },
    )
```

### 4.2 Conversation Service — history

```sql
-- Schema
CREATE TABLE conversations (
    id UUID PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(id),
    title TEXT,                    -- auto-generated from first message
    model_default TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    archived BOOLEAN DEFAULT FALSE,
    is_shared BOOLEAN DEFAULT FALSE
);
CREATE INDEX idx_conv_user_updated ON conversations(user_id, updated_at DESC) WHERE NOT archived;

CREATE TABLE messages (
    id UUID PRIMARY KEY,
    conversation_id UUID REFERENCES conversations(id) ON DELETE CASCADE,
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
    content TEXT NOT NULL,
    model TEXT,                    -- which model generated (for assistant)
    input_tokens INT,
    output_tokens INT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_msg_conv_created ON messages(conversation_id, created_at);

-- Partitioning by month for scale (500M msg/day = huge table)
CREATE TABLE messages_2026_05 PARTITION OF messages
    FOR VALUES FROM ('2026-05-01') TO ('2026-06-01');
```

```python
async def load_history(conv_id: UUID, user_id: int, limit: int = 50) -> list[dict]:
    """Last N messages from conversation for LLM context."""
    rows = await db.fetch_all(
        """
        SELECT role, content FROM messages
        WHERE conversation_id = :cid AND conversation_id IN (
            SELECT id FROM conversations WHERE user_id = :uid
        )
        ORDER BY created_at DESC LIMIT :lim
        """,
        {"cid": conv_id, "uid": user_id, "lim": limit},
    )
    return [{"role": r.role, "content": r.content} for r in reversed(rows)]

async def auto_title_conversation(conv_id: UUID, first_message: str):
    """Background task — LLM generates short title from first message."""
    response = await anthropic.messages.create(
        model="claude-haiku-4-5",  # cheap
        max_tokens=30,
        messages=[{
            "role": "user",
            "content": f"Generate a 3-6 word title for this conversation:\n\n{first_message[:500]}",
        }],
    )
    title = response.content[0].text.strip().strip('"')[:80]
    await db.execute("UPDATE conversations SET title = :t WHERE id = :id", {"t": title, "id": conv_id})
```

### 4.3 LLM Router — multi-provider, cost-optimized

```python
import litellm

# Model tiers
MODEL_TIERS = {
    "fast": "claude-haiku-4-5",
    "balanced": "claude-sonnet-4-6",
    "smart": "claude-opus-4-7",
    "vision": "gpt-4o",
}

# Routing logic
async def route_request(req: ChatRequest, user: User) -> str:
    """Pick optimal model based on request + user tier."""

    # Free tier → cheap model
    if user.tier == "free":
        return MODEL_TIERS["fast"]

    # Code/math detection → smart model
    if any(kw in req.message.lower() for kw in ["code", "algorithm", "proof", "math"]):
        return MODEL_TIERS["smart"]

    # Image attachment → vision model
    if any(att.endswith((".jpg", ".png", ".gif")) for att in req.attachments):
        return MODEL_TIERS["vision"]

    # Default for paid users
    return MODEL_TIERS["balanced"]

# Fallback chain
FALLBACKS = {
    "claude-opus-4-7": ["gpt-4o", "claude-sonnet-4-6"],
    "claude-sonnet-4-6": ["gpt-4o", "claude-haiku-4-5"],
}

async def call_with_fallback(model: str, messages: list, **kwargs):
    fallback_chain = [model] + FALLBACKS.get(model, [])
    last_error = None
    for m in fallback_chain:
        try:
            return await litellm.acompletion(model=m, messages=messages, **kwargs)
        except Exception as e:
            last_error = e
            logger.warning(f"Model {m} failed, trying next: {e}")
    raise last_error
```

### 4.4 Prompt Caching (huge cost saver)

```python
SYSTEM_PROMPT_BASE = """You are ChatGPT, a large language model trained by OpenAI.
Knowledge cutoff: 2026-01.
You are helpful, harmless, honest...
[10,000 tokens of behavior instructions]
"""

async def call_with_cache(user_message: str, history: list):
    # Anthropic prompt caching — system prompt cached (90% cheaper on hit)
    response = await anthropic.messages.create(
        model="claude-opus-4-7",
        max_tokens=4096,
        system=[
            {
                "type": "text",
                "text": SYSTEM_PROMPT_BASE,
                "cache_control": {"type": "ephemeral"},  # 5-min TTL
            }
        ],
        messages=history + [{"role": "user", "content": user_message}],
    )
    # First call: full price
    # Calls within 5 min: ~10% of input cost
    return response
```

**Cost impact:** System prompt 10K tokens, used 17K times/sec → 170M tokens/sec input
- Without caching: $3,400/sec input cost ($150K/sec at scale — unsustainable)
- With caching (90% hit rate): $340/sec ($15K/sec)
- **Savings: $130M+/year**

### 4.5 Semantic Cache (skip LLM for repeat queries)

```python
import hashlib

async def check_semantic_cache(query: str) -> dict | None:
    """Find similar past queries in cache."""
    embedding = await embed(query)

    result = await db.fetch_one(
        """
        SELECT response, hit_count
        FROM semantic_cache
        WHERE 1 - (query_embedding <=> :emb) > 0.97
          AND created_at > NOW() - INTERVAL '7 days'
        ORDER BY query_embedding <=> :emb
        LIMIT 1
        """,
        {"emb": embedding},
    )

    if result:
        await db.execute("UPDATE semantic_cache SET hit_count = hit_count + 1 WHERE response = :r", {"r": result.response})
        return {"text": result.response, "from_cache": True}
    return None

async def save_to_cache(query: str, response: str):
    embedding = await embed(query)
    await db.execute(
        "INSERT INTO semantic_cache (query, query_embedding, response) VALUES (:q, :e, :r)",
        {"q": query, "e": embedding, "r": response},
    )
```

**Hit rate analysis:**
- Common queries ("hello", "what can you do") → 60-80% hit rate
- Domain-specific → 10-30% hit rate
- Personal/contextual → < 5% hit rate
- Overall: ~20% hits = 20% LLM cost saved on cached portion

---

## 5. Streaming Architecture (Critical for UX)

### Why streaming matters

```
WITHOUT STREAMING:
─────────────
User sends → wait 8s → see full response
   UX: feels broken, "did it work?"

WITH STREAMING:
─────────────
User sends → 800ms TTFT → tokens flow at 30/sec → done
   UX: feels conversational, can read while generating
```

### Stack choices

| Layer | Choice | Why |
|---|---|---|
| Client ↔ API | **SSE** over HTTPS | Simpler than WebSocket, auto-reconnect, works over HTTP/2 |
| API ↔ LLM | LLM provider streaming SDK | OpenAI/Anthropic native |
| Nginx config | `X-Accel-Buffering: no` | Must not buffer |
| Load balancer | Layer 7 with long timeouts | LLM responses can take 30+ sec |
| CDN | **Bypass** for /chat/stream | Cloudflare buffers below Enterprise |

### Backpressure handling

```python
# Client disconnects mid-stream — must clean up
@app.post("/chat/stream")
async def chat_stream(req: ChatRequest, request: Request):
    async def stream():
        try:
            async for token in llm_stream():
                # Check if client disconnected
                if await request.is_disconnected():
                    logger.info("Client disconnected, stopping LLM")
                    break
                yield f"data: {json.dumps({'text': token})}\n\n"
        finally:
            # Still save partial response + track tokens used
            pass
    return StreamingResponse(stream(), media_type="text/event-stream")
```

---

## 6. Rate Limiting + Quota

```python
# Tiered quotas
QUOTAS = {
    "free": {
        "messages_per_3h": 10,
        "models_allowed": ["claude-haiku-4-5"],
        "tokens_per_day": 100_000,
    },
    "plus": {
        "messages_per_3h": 80,
        "models_allowed": ["all"],
        "tokens_per_day": 5_000_000,
    },
    "enterprise": {
        "messages_per_3h": float("inf"),
        "models_allowed": ["all"],
        "tokens_per_day": 50_000_000,
    },
}

async def enforce_quota(user: User):
    quota = QUOTAS[user.tier]
    redis_key = f"quota:msg:{user.id}:{datetime.utcnow().strftime('%Y%m%d%H') // 3}"

    # Use Redis INCR for atomic counter
    count = await redis.incr(redis_key)
    if count == 1:
        await redis.expire(redis_key, 3 * 3600)  # 3h TTL

    if count > quota["messages_per_3h"]:
        raise HTTPException(429, "Rate limit reached. Upgrade for unlimited.")
```

**Sliding window for smoother UX:**
```python
async def sliding_window_check(user_id: int, limit: int, window_sec: int) -> bool:
    now = time.time()
    key = f"sw:{user_id}"
    # Remove expired entries
    await redis.zremrangebyscore(key, 0, now - window_sec)
    # Count current
    count = await redis.zcard(key)
    if count >= limit:
        return False
    # Add current
    await redis.zadd(key, {str(uuid4()): now})
    await redis.expire(key, window_sec)
    return True
```

---

## 7. RAG Integration (file Q&A)

```python
@app.post("/files/upload")
async def upload_file(file: UploadFile, user: User = Depends(get_user)):
    file_id = uuid4()

    # 1. Store in S3
    s3.upload_fileobj(file.file, "chatgpt-files", f"{user.id}/{file_id}")

    # 2. Schedule background ingestion
    await kafka.send("rag.ingest", {"file_id": str(file_id), "user_id": user.id})

    return {"file_id": file_id, "status": "processing"}

# Background worker
async def ingest_worker():
    async for msg in kafka_consumer("rag.ingest"):
        file_id = msg["file_id"]
        # Parse → chunk → embed → store in pgvector
        text = parse_file(file_id)
        chunks = chunk_by_paragraphs(text, max_tokens=500)
        embeddings = await embed_batch(chunks)
        for i, (chunk, emb) in enumerate(zip(chunks, embeddings)):
            await db.execute(
                "INSERT INTO rag_chunks (file_id, chunk_index, content, embedding) VALUES (:f, :i, :c, :e)",
                {"f": file_id, "i": i, "c": chunk, "e": emb},
            )
```

(Full RAG details in `Design_RAG_System.md`)

---

## 8. Data Model

```sql
-- Users (PostgreSQL)
CREATE TABLE users (
    id BIGSERIAL PRIMARY KEY,
    email TEXT UNIQUE,
    tier TEXT NOT NULL DEFAULT 'free',  -- 'free' | 'plus' | 'enterprise'
    region TEXT NOT NULL,                -- 'us', 'eu', 'in' (data residency)
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Conversations
CREATE TABLE conversations (
    id UUID PRIMARY KEY,
    user_id BIGINT NOT NULL,
    title TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    archived BOOLEAN DEFAULT FALSE
);

-- Messages (partitioned by month)
CREATE TABLE messages (
    id UUID PRIMARY KEY,
    conversation_id UUID,
    role TEXT,
    content TEXT,
    model TEXT,
    input_tokens INT,
    output_tokens INT,
    created_at TIMESTAMPTZ NOT NULL
) PARTITION BY RANGE (created_at);

-- Usage tracking (for billing)
CREATE TABLE usage_events (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT,
    model TEXT,
    input_tokens INT,
    output_tokens INT,
    cost_usd NUMERIC(10, 6),
    created_at TIMESTAMPTZ DEFAULT NOW()
) PARTITION BY RANGE (created_at);

-- RAG chunks (pgvector)
CREATE TABLE rag_chunks (
    id UUID PRIMARY KEY,
    file_id UUID,
    user_id BIGINT,
    chunk_index INT,
    content TEXT,
    embedding vector(1536)
);
CREATE INDEX ON rag_chunks USING hnsw (embedding vector_cosine_ops);

-- Semantic cache
CREATE TABLE semantic_cache (
    id UUID PRIMARY KEY,
    query TEXT,
    query_embedding vector(1536),
    response TEXT,
    hit_count INT DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

---

## 9. Multi-Region Deployment

```
US-EAST-1 (primary)        EU-WEST-1                AP-SOUTH-1
─────────────              ────────                 ──────────
US users                   EU users (GDPR)          IN users (DPDP)
   │                          │                       │
PostgreSQL primary         PG primary (EU data)     PG primary (IN data)
   │  async replication       │                       │
PostgreSQL replica         (independent shard)      (independent shard)

Global services (in all regions):
- LLM API calls (route to nearest provider region)
- pgvector (RAG) — per-region
- Redis (sessions, quota) — per-region
- S3 (files) — per-region with cross-region replication
```

**Why sharded by region:** EU/India data residency requires user data stays in-region.

---

## 10. LLM Cost Optimization (CRITICAL)

```python
# Cost-aware routing
async def smart_routing(message: str, user: User) -> str:
    # 1. Try semantic cache first (free)
    cached = await check_semantic_cache(message)
    if cached:
        return cached["text"]

    # 2. Classify intent — short queries → cheap model
    if len(message) < 50 and not requires_reasoning(message):
        return await call_haiku(message)

    # 3. Default routing
    model = route_request(message, user)
    return await call_llm(model, message)
```

**Cost breakdown (50M MAU):**

| Strategy | Daily Cost | Annual |
|---|---|---|
| All Opus, no caching | $50M | $18B (impossible!) |
| Mixed models, no caching | $8M | $2.9B |
| Mixed models + prompt cache | $1.5M | $548M |
| + Semantic cache (20%) | $1.2M | $440M |
| + Smart routing | $0.8M | $292M |
| + Self-hosted Llama for free tier | $0.4M | $146M |

**Self-hosted option:**
- Free tier (50% of users) → Llama 3.3 70B on H100 GPUs
- $400/H100/day × 100 GPUs = $40K/day for serving 25M users free tier
- vs $20M/day with API → 500x cheaper

---

## 11. Scaling Considerations

| Concern | Solution |
|---|---|
| **17K msg/sec write to DB** | Partition by month; async write via Kafka |
| **500K concurrent SSE streams** | FastAPI workers × N (each holds 1000s); use uvloop |
| **Conversation history infinite growth** | Archive to cold storage after 90 days; keep last 50 msgs hot |
| **RAG over millions of docs** | Per-user pgvector index; HNSW |
| **LLM provider goes down** | LiteLLM fallback chain |
| **Region outage** | Read replicas; Route53 failover |
| **DDoS** | Cloudflare; per-IP rate limits |
| **Token cost spike** | Daily budget alarms; auto-throttle |

---

## 12. Observability

```python
# Metrics to track (Prometheus)
ttft_seconds = Histogram("ttft_seconds", "Time to first token")
tokens_per_second = Histogram("tokens_per_second", "Output token rate")
llm_cost_usd = Counter("llm_cost_usd_total", "LLM cost", ["model", "tier"])
semantic_cache_hits = Counter("semantic_cache_hits_total")
quota_violations = Counter("quota_violations_total", "label", ["tier"])

# Distributed tracing — track every chat through stack
@app.post("/chat/stream")
@trace.start_as_current_span("chat_stream")
async def chat_stream(req: ChatRequest):
    span = trace.get_current_span()
    span.set_attribute("user.id", user.id)
    span.set_attribute("model", req.model)
    span.set_attribute("conversation.id", str(req.conversation_id))
    # ... LLM calls auto-instrumented
```

**Key SLOs:**
- TTFT P95 < 1s
- Streaming success rate > 99.5%
- LLM error rate < 0.5%
- Cost/active user < $0.50/month

---

## 13. Security Considerations

| Threat | Mitigation |
|---|---|
| **Prompt injection** | Input classifier (Haiku-based), system prompt isolation |
| **Data exfiltration** | Output filter for PII, system prompt leak detection |
| **Account takeover** | MFA mandatory; session binding; anomaly detection |
| **Cost-DoS** | Per-user daily $ cap; auto-throttle on anomaly |
| **Abuse (illegal content)** | Output classifier; report flow; account suspension |
| **Model jailbreak** | Constitutional AI; safety classifier on outputs |
| **GDPR data deletion** | Tombstone + 30-day grace; cascade delete to embeddings |

(See `00_Year0-2_Junior/06_FastAPI/33_prompt_injection_security.md`)

---

## 14. Trade-offs & Alternatives

| Decision | Alternative | Trade-off |
|---|---|---|
| SSE over WebSocket | WebSocket | SSE simpler, HTTP-friendly; WS for true bidirectional |
| pgvector for RAG | Pinecone/Weaviate | pgvector = one less service; managed = less ops |
| PostgreSQL for messages | Cassandra/ScyllaDB | PG simpler; Cassandra better for huge writes |
| LiteLLM for routing | Custom | LiteLLM done; custom = more control |
| Anthropic + OpenAI | Single provider | Multi = resilience; single = simpler |
| Streaming via HTTP | gRPC streaming | HTTP works everywhere; gRPC faster |
| Kafka for events | Redis Streams | Kafka mature; Redis simpler |

---

## 15. Interview Talking Points

**"What's the hardest part?"**
1. LLM cost at scale ($10M+/month for 50M MAU)
2. Streaming with reliable backpressure
3. RAG over user files (millions of small indices)
4. Quota across geo-distributed regions

**"What if traffic 10x's overnight?"**
- LLM provider becomes bottleneck — add more providers
- DB write throughput — partition further, move to Cassandra for messages
- Vector DB cost — tier into hot (recent) + cold (archive)

**"How do you A/B test models?"**
- Header-based routing: 5% traffic to new model
- Compare: completion rate, user thumbs up, cost
- Use shadow mode first (call both, return primary, log secondary)

**"Conversation > 100 messages — context window full?"**
- Summarize old messages into rolling system message
- Or use retrieval over conversation itself
- Or just truncate (worst UX)

---

## 16. Related Concepts

- `Design_RAG_System.md` — RAG architecture deep dive
- `Design_Agent_Orchestration.md` — multi-agent extension
- `Notification_System.md` — push notifications for new messages
- `Rate_Limiter.md` — rate limiting deep
- `Payment_System.md` — subscription billing
- `00_Year0-2_Junior/06_FastAPI/31_llm_integration_fastapi.md` — code-level LLM patterns
- `00_Year0-2_Junior/06_FastAPI/34_rag_backend_architecture.md` — RAG implementation
