# Semantic Caching for LLMs

> **Interview angle:** "OpenAI bill $10K/month. 60% requests semantically similar to past ones. Kya karoge?"

---

## 1. The Problem with Exact-Match Caching

```python
# Traditional cache — exact key match
cache_key = f"prompt:{hash(prompt)}"
```

LLM users phrase questions differently:
- "What is Python?"
- "Tell me about Python"
- "Can you explain Python?"

**All same intent. Exact-match cache: 0% hit rate.**

---

## 2. Semantic Caching — Embedding-Based Match

Idea: Cache by **meaning** (vector similarity), not exact text.

```
1. User sends prompt
2. Compute embedding of prompt (e.g., 1536-dim vector via OpenAI ada-002)
3. Search cache for embeddings within similarity threshold (e.g., cosine > 0.95)
4. If match → return cached response (skip LLM call)
5. If no match → call LLM, store (prompt, embedding, response)
```

### Math
**Cosine similarity:**
```
cos(A, B) = (A · B) / (|A| × |B|)
```
- 1.0 = identical
- 0.95+ = very similar (often safe to reuse)
- 0.8 = related but might differ
- 0 = unrelated

---

## 3. Architecture

```
                        ┌─────────────┐
User prompt ────────────│  Embed      │── 1536-dim vector
                        └──────┬──────┘
                               │
                        ┌──────▼──────┐
                        │ Vector DB   │  search top-1 nearest
                        │ (Redis,     │  similarity ≥ threshold?
                        │  Qdrant,    │
                        │  Pinecone)  │
                        └──────┬──────┘
                               │
                ┌──────────────┴──────────────┐
                ▼                              ▼
        ┌──────────────┐              ┌──────────────┐
        │ Cache HIT    │              │ Cache MISS   │
        │ Return cached│              │ Call LLM     │
        │ response     │              │ Cache result │
        └──────────────┘              └──────────────┘
```

---

## 4. Implementation Sketch

```python
from openai import OpenAI
import numpy as np

client = OpenAI()

def embed(text: str) -> list[float]:
    resp = client.embeddings.create(model="text-embedding-3-small", input=text)
    return resp.data[0].embedding

def cosine(a, b):
    a, b = np.array(a), np.array(b)
    return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))

class SemanticCache:
    def __init__(self, threshold: float = 0.95):
        self.threshold = threshold
        self.entries = []   # list of (embedding, prompt, response)

    def get(self, prompt: str) -> str | None:
        emb = embed(prompt)
        best_sim = 0
        best_response = None
        for cached_emb, cached_prompt, cached_resp in self.entries:
            sim = cosine(emb, cached_emb)
            if sim > best_sim:
                best_sim = sim
                best_response = cached_resp
        if best_sim >= self.threshold:
            return best_response
        return None

    def put(self, prompt: str, response: str):
        emb = embed(prompt)
        self.entries.append((emb, prompt, response))
```

For production: use real vector DB (linear scan = O(N) bad).

---

## 5. Vector DB Options

| DB | Pros | Cons |
|---|---|---|
| **Redis** + `RediSearch` | Already in stack | Setup complex |
| **Qdrant** | Fast, easy Python SDK | Extra service |
| **Pinecone** | Managed | Cost, vendor lock |
| **pgvector** | In Postgres | Slower at scale |
| **Chroma** | Embedded option | Less production-ready |
| **Weaviate** | Feature-rich | Heavier |

### Redis + RediSearch example
```python
from redis import Redis
from redis.commands.search.field import VectorField, TextField

r = Redis()
r.ft("llm_cache").create_index([
    TextField("prompt"),
    TextField("response"),
    VectorField("embedding", "HNSW", {
        "TYPE": "FLOAT32",
        "DIM": 1536,
        "DISTANCE_METRIC": "COSINE",
    }),
])

# Insert
r.hset("cache:1", mapping={
    "prompt": "What is Python?",
    "response": "Python is a programming language...",
    "embedding": np.array(embedding, dtype=np.float32).tobytes(),
})

# Search
query = f"*=>[KNN 1 @embedding $vec AS score]"
res = r.ft("llm_cache").search(
    query,
    query_params={"vec": np.array(query_emb, dtype=np.float32).tobytes()},
)
```

---

## 6. Threshold Tuning

The threshold determines hit rate vs accuracy trade-off.

| Threshold | Behavior |
|---|---|
| 0.99 | Very strict — near-identical prompts |
| 0.95 | Strict — small rewording OK |
| 0.90 | Moderate — paraphrases hit |
| 0.85 | Loose — different but related |
| 0.80 | Very loose — risky |

**Recommended starting point: 0.92-0.95**

### How to tune
1. Collect 100 query pairs (similar + different)
2. Compute similarity for each
3. Find threshold that maximizes (TP - FP)
4. Sample-check responses for false positives

### Per-domain thresholds
- Factual Q&A: 0.97 (precision matters)
- Conversational: 0.90 (lossy OK)
- Creative writing: don't cache (each unique)

---

## 7. Cache Key Augmentation

Pure prompt embedding isn't enough — context matters.

```python
def cache_key_text(prompt, model, temperature, system_prompt):
    return f"[model={model}|temp={temperature}|sys={system_prompt[:50]}]: {prompt}"

# Embedding of this augmented text → better separation
```

**Why:** Same prompt with different system prompts → different responses. Cache must differentiate.

---

## 8. TTL and Invalidation

### TTL strategy
- Time-sensitive ("Latest news"): short TTL (1 hour)
- Stable knowledge ("What is Python?"): long TTL (7 days)
- LLM model version change → invalidate ALL

```python
class SemanticCache:
    def put(self, prompt, response, ttl=86400):
        # Store with TTL
        ...

    def invalidate_on_model_change(self, old_model, new_model):
        # Delete all entries for old model
        ...
```

### Don't cache if
- User says "regenerate" or similar
- Temperature > 0 (variability desired)
- Tool calls / function calls (results may have side effects)
- Streaming response (cache final result only)
- User is identified (personalized response)

---

## 9. Cost Savings Analysis

Suppose:
- 1M LLM calls/month at $0.03 each = $30K
- 40% hit rate via semantic cache
- Embedding cost: $0.02/1M tokens
- Cache infra: $200/month

**Savings:** $30K × 40% = $12K - $200 - $20 = **$11.78K/month**

Even 20% hit rate saves $6K/month.

### Critical: cache the EXPENSIVE LLM call
- Cache OpenAI GPT-4 responses (expensive)
- Don't cache cheap embedding calls themselves

---

## 10. Quality Concerns

### Problem: Wrong cache hit
"What is Python?" → cached
"What is Python 2 vs Python 3?" → similarity 0.95 → WRONG cached response

### Solutions
- Higher threshold (0.96+)
- LLM-as-judge verifier
- Track user feedback (thumbs down → invalidate)

### Tracking
```python
def get(self, prompt, user_id):
    cached = self._semantic_lookup(prompt)
    if cached:
        await analytics.track("semantic_cache_hit", {
            "user_id": user_id,
            "similarity": cached.similarity,
            "cache_age_seconds": cached.age,
        })
    return cached
```

Compare hit-rate, user satisfaction (thumbs up/down), regenerate-clicks.

---

## 11. Hybrid Cache (Exact + Semantic)

```python
class HybridCache:
    def get(self, prompt):
        # 1. Exact match first (faster)
        if cached := self.exact_cache.get(hash(prompt)):
            return cached

        # 2. Semantic match
        return self.semantic_cache.get(prompt)
```

Exact match = 0% false positives.
Semantic = catches paraphrases.

---

## 12. Other LLM Caching Patterns

### Pattern 1: Prefix caching
GPT-4 turbo + Anthropic Claude support **prompt caching** at API level:
```python
# Anthropic: mark system prompt as cacheable
messages = [
    {"role": "system", "content": "Long system prompt...", "cache_control": {"type": "ephemeral"}},
    {"role": "user", "content": prompt},
]
# 90% cheaper on repeated calls with same prefix
```

### Pattern 2: Conversation-level cache
Cache entire conversation by session — replay if same questions.

### Pattern 3: Embedding cache
Cache embeddings themselves (text → embedding is deterministic).
Saves embedding API calls.

---

## 13. Production Libraries

### `GPTCache` (open source)
```python
from gptcache import cache, Config
from gptcache.adapter.openai import openai

cache.init(config=Config(similarity_threshold=0.95))
cache.set_openai_key()

# Now openai.ChatCompletion.create() uses semantic cache transparently
```

### `langchain`'s caching
```python
from langchain.cache import RedisSemanticCache
from langchain.embeddings import OpenAIEmbeddings
import langchain

langchain.llm_cache = RedisSemanticCache(
    redis_url="redis://localhost:6379",
    embedding=OpenAIEmbeddings(),
    score_threshold=0.2,    # distance, not similarity
)
```

### `LiteLLM` + `redis-cache`
Built into LiteLLM proxy.

---

## 14. Interview Questions

**Q1: Semantic caching kya hai?**
Cache by vector similarity of prompts (not exact match). Catches paraphrased queries.

**Q2: Threshold kaise pick?**
Start 0.95. Tune on validation set of (query, expected) pairs. Higher = precise, lower = more hits.

**Q3: Embedding cost vs LLM cost?**
Embedding ~100x cheaper than GPT-4. Net savings even with cache misses.

**Q4: Vector DB choice?**
- Already on stack: extend Redis with RediSearch / pgvector
- Pure managed: Pinecone
- Self-hosted balance: Qdrant

**Q5: Wrong cache hit problem?**
Similarity not perfect signal. Mitigate with higher threshold + LLM judge + user feedback loop.

**Q6: TTL for LLM cache?**
Depends. Stable knowledge: days. News/realtime: minutes. Reset on model upgrade.

**Q7: Prompt caching vs semantic?**
- Prompt caching (Anthropic, OpenAI): same prefix tokens → API-side discount
- Semantic: similar meaning → skip LLM entirely

---

## 15. Best Practices

1. **Hybrid: exact + semantic** — exact first, semantic fallback
2. **Threshold 0.93-0.95** — start here, tune empirically
3. **Augment cache key** with model + temperature + system prompt
4. **Per-user cache** when responses are personalized
5. **Track hit/miss metrics** + user feedback
6. **TTL based on content stability**
7. **Use vector DB** (not linear scan)
8. **Cache embeddings** too (deterministic)
9. **Invalidate on model upgrade**
10. **A/B test thresholds** before rollout

---

## Related
- [[../../Phase2_Redis/theory/04_vector_search_fastapi]]
- [[07_multi_level_caching]]
- [[../../Phase4_OpenAI_API/]]
- [[../../Phase6_Production_AI/]]
