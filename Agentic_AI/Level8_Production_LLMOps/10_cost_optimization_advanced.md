# Level 8.10 — Cost Optimization Advanced
**Phase: Production LLMOps | Production-Critical**

## Quick Concepts

- **Model routing** = pick cheapest model that meets quality bar
- **Semantic caching** = cache responses by query similarity, not exact match
- **Prompt compression** = shorten prompts without quality loss (LLMLingua etc.)
- **Batching** = combine multiple requests into one
- **Context trimming** = remove irrelevant history before each call
- **Prompt caching** = providers cache identical prefixes (Anthropic, OpenAI)
- **Distillation** = train smaller model to mimic larger one
- **Quantization** = lower precision = lower cost (self-host)

---

## Why Cost Engineering Matters in 2026

```
LLM cost reality:
   ✗ GPT-4o: $2.50 input / $10 output per 1M tokens
   ✗ Naive setup: $5,000+/month for moderate-volume app
   ✗ Most apps: 80% spend on simple queries that don't need GPT-4o

After optimization:
   ✓ Right model for right job: 60% savings
   ✓ Semantic cache: another 30% savings
   ✓ Prompt compression: another 20% savings
   ✓ Total: 60-90% cost reduction common

In interviews: "How do you reduce LLM costs at scale?"
   → This doc is your answer.
```

---

## Strategy 1: Model Routing

Route by query complexity. Covered deep in [Level6/08_routing.md](../Level6_Agent_Patterns/08_routing.md) — here's the cost-focused version:

```python
COST_TIERS = {
    "tier_0": {
        "model": "gpt-4o-mini",
        "cost_in":  0.15 / 1_000_000,
        "cost_out": 0.60 / 1_000_000,
    },
    "tier_1": {
        "model": "gpt-4o",
        "cost_in":  2.50 / 1_000_000,
        "cost_out": 10.0 / 1_000_000,
    },
    "tier_2": {
        "model": "claude-opus-4",
        "cost_in":  15.0 / 1_000_000,
        "cost_out": 75.0 / 1_000_000,
    },
}


async def route_by_complexity(query: str) -> str:
    """Quick classification to pick tier."""
    
    # Use cheapest model to classify
    classification = await openai.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{
            "role": "user",
            "content": f"""Classify complexity: 'simple', 'medium', 'complex'.
            Query: {query}
            One word answer."""
        }],
        max_tokens=5,
        temperature=0,
    )
    
    level = classification.choices[0].message.content.strip().lower()
    return {
        "simple": "tier_0",
        "medium": "tier_1",
        "complex": "tier_2",
    }.get(level, "tier_0")


# Avg cost savings: 70% if 60% queries are "simple"
```

---

## Strategy 2: Semantic Caching

Don't re-run LLMs on similar queries. Already in [Backend_Developer/Phase2_Caching/06](../../Backend_Developer/00_Year0-2_Junior/09_Caching/theory/06_semantic_caching_llm.md) and [Level3/10](../Level3_LLM_APIs_SDKs/10_cost_optimization.md). Quick recap:

```python
import numpy as np
from openai import AsyncOpenAI

client = AsyncOpenAI()
cache = {}  # in production: Redis with vector search


async def get_or_compute(query: str, threshold=0.95):
    # Embed query
    q_emb = await embed(query)
    
    # Search cache for similar
    for cached_emb, cached_response in cache.items():
        similarity = np.dot(q_emb, cached_emb)
        if similarity > threshold:
            return cached_response, True  # cache hit
    
    # Cache miss — compute
    response = await llm_call(query)
    cache[tuple(q_emb)] = response  # in production: use proper KV store
    return response, False
```

### Tuning Threshold

```
0.99 = very strict (low cache hit rate, no false positives)
0.95 = balanced (most production)
0.90 = aggressive (high hit rate, risk false hits)
< 0.85 = too loose, often returns wrong cached response

A/B test on your data.
```

### Real Cache Hit Rates

```
Customer support:  60-80% (repetitive questions)
Code assistant:    20-40% (varied queries)
Generic chat:      30-50%
Documentation Q&A: 40-60%
```

---

## Strategy 3: Prompt Caching (Provider-Side)

Anthropic + OpenAI cache identical prompt prefixes:

### Anthropic Prompt Caching

```python
response = await anthropic.messages.create(
    model="claude-3-7-sonnet-latest",
    max_tokens=1024,
    system=[
        {
            "type": "text",
            "text": LONG_SYSTEM_PROMPT,  # 10k tokens of instructions/examples
            "cache_control": {"type": "ephemeral"},  # ← cache this part
        },
    ],
    messages=[{"role": "user", "content": user_query}],
)
```

**Pricing:**
- Cache WRITE: 25% more expensive than normal input
- Cache READ: 10% of normal input cost (90% discount!)
- Cache TTL: 5 minutes default

**Win scenario:** 10k-token system prompt + 100 user queries within 5 min:
- Without caching: 10k × 100 × $3 = $3.00
- With caching: 10k × $3 × 1.25 (1st) + 10k × 99 × $0.30 = $0.34
- Savings: **89%**

### OpenAI Prompt Caching (Auto)

OpenAI automatically caches prefixes ≥ 1024 tokens. Cache hits get 50% input discount. No code needed — just structure prompts with stable prefix first.

```python
# Good for caching
messages = [
    {"role": "system", "content": LONG_SYSTEM_PROMPT},  # stable
    {"role": "user", "content": "First few examples for context..."},  # stable
    {"role": "assistant", "content": "Got it"},  # stable
    # ... varying part at end:
    {"role": "user", "content": current_query},  # only this changes
]
```

---

## Strategy 4: Context Window Trimming

Don't send entire conversation history every time.

```python
def trim_history(history: list, max_tokens: int = 4000) -> list:
    """Keep system + last N messages within budget."""
    import tiktoken
    
    enc = tiktoken.encoding_for_model("gpt-4o-mini")
    
    # Always keep system
    system = [m for m in history if m["role"] == "system"]
    others = [m for m in history if m["role"] != "system"]
    
    # Trim from oldest (keep recent context)
    trimmed = []
    total_tokens = sum(len(enc.encode(m["content"])) for m in system)
    
    for msg in reversed(others):
        msg_tokens = len(enc.encode(msg["content"]))
        if total_tokens + msg_tokens > max_tokens:
            break
        trimmed.insert(0, msg)
        total_tokens += msg_tokens
    
    return system + trimmed
```

### Summary-Based Trimming

For very long histories:

```python
async def summarize_older_history(history: list, keep_recent=5) -> list:
    if len(history) <= keep_recent + 1:  # +1 for system
        return history
    
    system = [m for m in history if m["role"] == "system"]
    others = [m for m in history if m["role"] != "system"]
    
    to_summarize = others[:-keep_recent]
    recent = others[-keep_recent:]
    
    summary = await llm_call(
        f"Summarize this conversation history concisely:\n\n"
        f"{format_messages(to_summarize)}",
        model="gpt-4o-mini",
    )
    
    return system + [
        {"role": "system", "content": f"Earlier summary: {summary}"}
    ] + recent
```

---

## Strategy 5: Prompt Compression

Use techniques/tools to shorten prompts without quality loss:

### LLMLingua (Microsoft)

```python
from llmlingua import PromptCompressor

compressor = PromptCompressor()

original = """Long detailed prompt with lots of context here..."""

compressed = compressor.compress_prompt(
    original,
    instruction="Summarize the document",
    question="What are the key points?",
    target_token=500,  # compress to ~500 tokens
)

# Use compressed prompt with LLM
response = await llm_call(compressed["compressed_prompt"])
```

**Results:** Often 2-5x compression with < 5% quality loss.

### Manual Techniques

```
✗ "Please could you kindly help me understand..."
✓ "Explain:"

✗ "Here are the instructions: 1. First..."
✓ Bulleted list

✗ Verbose few-shot examples
✓ Concise examples (5 instead of 10)

✗ Repeating context across messages
✓ Reference: "as established earlier..."
```

---

## Strategy 6: Output Length Capping

Output tokens cost 2-4x more than input:

```python
# Tight max_tokens for each task
TASK_LIMITS = {
    "classification":    10,
    "yes_no":            3,
    "short_answer":      150,
    "summary":           500,
    "article":           2000,
    "code":              4000,
}


async def call_with_limit(task_type: str, prompt: str):
    return await client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=TASK_LIMITS[task_type],
    )
```

### Stop Sequences

```python
# Stop early when expected pattern emerges
response = await client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[...],
    stop=["\n\n", "END_OF_RESPONSE", "</answer>"],
)
```

---

## Strategy 7: Batching Embeddings

For RAG indexing:

```python
# ✗ Slow + expensive
for doc in 1000_docs:
    embedding = await embed(doc.content)
    db.store(doc.id, embedding)

# ✓ Batch (one API call per 100 docs)
for batch in chunked(1000_docs, size=100):
    texts = [d.content for d in batch]
    embeddings = await embed_batch(texts)
    db.bulk_store(zip([d.id for d in batch], embeddings))
```

**Speed:** 100x faster
**Cost:** Marginal savings + lower overhead

---

## Strategy 8: Provider Cascade (Cheapest First)

Try cheap provider, fall back to expensive only if quality fails:

```python
PROVIDERS_BY_COST = [
    {"name": "groq", "model": "llama-3-8b", "cost": "$0.05/1M"},
    {"name": "openai", "model": "gpt-4o-mini", "cost": "$0.15/1M"},
    {"name": "openai", "model": "gpt-4o", "cost": "$2.50/1M"},
    {"name": "anthropic", "model": "claude-opus", "cost": "$15/1M"},
]


async def cascade_call(query: str, quality_check):
    for provider in PROVIDERS_BY_COST:
        response = await call_provider(provider, query)
        
        if await quality_check(query, response):
            return response  # cheap one worked
    
    raise Exception("All providers failed quality")


# quality_check could be:
# - Regex (does response contain expected pattern?)
# - LLM-as-judge (smaller model rates quality)
# - Confidence score from response logprobs
```

**Win:** 60-70% queries served by cheapest, only hard ones escalate.

---

## Strategy 9: Distillation (Train Small Models)

For high-volume tasks, fine-tune a small model to mimic GPT-4o:

```
1. Collect: (input, GPT-4o output) pairs from production
   → ~5,000-10,000 examples typically enough
2. Fine-tune: Llama-3-8B or Mistral-7B on this data
3. Deploy: self-hosted, replaces GPT-4o calls
4. Result: 95% of GPT-4o quality at 5% of cost
```

### When Distillation Wins

```
✓ Narrow task (sentiment, classification, structured extraction)
✓ High volume (>100k calls/day)
✓ Have GPU infra or can use cheap inference
✗ Wide-domain general chat (large model wins)
✗ Tasks needing reasoning chain (still use bigger)
```

---

## Strategy 10: Quantization (Self-Host)

If self-hosting:

```python
# vLLM serving with FP8 quantization (50% memory + faster)
# llm = LLM(model="meta-llama/Llama-3-70B", quantization="fp8")

# 4-bit quantization (75% memory savings, slight quality loss)
# llm = LLM(model="meta-llama/Llama-3-70B", quantization="awq")
```

For self-hosted serving:
- FP16: standard, no quality loss
- FP8: 50% smaller, ~no quality loss
- AWQ/INT4: 75% smaller, ~5% quality loss

→ Run larger models on smaller GPUs = cheaper infra.

---

## Strategy 11: Cost Tracking + Budget Alerts

```python
class CostTracker:
    def __init__(self, redis_client):
        self.redis = redis_client
    
    async def record(self, model: str, prompt_tokens: int, completion_tokens: int, tenant_id: str = None):
        cost = self.calculate_cost(model, prompt_tokens, completion_tokens)
        
        date = datetime.utcnow().strftime("%Y-%m-%d")
        
        # Daily totals
        await self.redis.incrbyfloat(f"cost:daily:{date}", cost)
        await self.redis.incrbyfloat(f"cost:model:{model}:{date}", cost)
        
        if tenant_id:
            await self.redis.incrbyfloat(f"cost:tenant:{tenant_id}:{date}", cost)
        
        # Alert if daily budget exceeded
        daily_total = await self.redis.get(f"cost:daily:{date}")
        if float(daily_total) > DAILY_BUDGET:
            await alert(f"Daily LLM budget exceeded: ${daily_total}")
    
    def calculate_cost(self, model, in_tokens, out_tokens):
        pricing = COST_TIERS[model]
        return (in_tokens * pricing["cost_in"] +
                out_tokens * pricing["cost_out"])
```

### Per-Tenant Quotas

```python
async def enforce_quota(tenant_id: str, estimated_cost: float):
    today = datetime.utcnow().strftime("%Y-%m-%d")
    current = float(await redis.get(f"cost:tenant:{tenant_id}:{today}") or 0)
    
    plan = await get_tenant_plan(tenant_id)
    daily_budget = plan["llm_daily_budget"]
    
    if current + estimated_cost > daily_budget:
        raise QuotaExceededError(
            f"Tenant {tenant_id} exceeded daily budget ${daily_budget}"
        )
```

---

## Cost Optimization Roadmap

```
Step 1: Measure where money goes (per-endpoint, per-tenant, per-model)
   → CostTracker + dashboard

Step 2: Apply quick wins
   ✓ Trim history to last N messages
   ✓ Set max_tokens aggressively
   ✓ Use cheap model for embedding routing
   → Often 30-40% savings

Step 3: Implement semantic caching
   ✓ Redis + vector search
   ✓ Tune similarity threshold
   → Additional 20-40% on repetitive workloads

Step 4: Provider-side prompt caching
   ✓ Refactor prompts: stable prefix first
   ✓ Use Anthropic's explicit cache_control for long contexts
   → 50-90% on system prompts

Step 5: Model routing by complexity
   ✓ Cheap → expensive cascade
   ✓ Per-task tier mapping
   → 50-70% on average queries

Step 6: Prompt compression
   ✓ LLMLingua or manual
   → 2-5x input reduction

Step 7: Distillation (last resort, high effort)
   ✓ Fine-tune small model for narrow task
   → 95% cost reduction on specific tasks

Cumulative possible savings: 80-95%
```

---

## Cost Dashboard Metrics

```
✓ Daily/monthly LLM spend
✓ Spend per model (which is dominant?)
✓ Spend per endpoint (which endpoints are expensive?)
✓ Spend per tenant (any whale tenants?)
✓ Avg input tokens per call (catch prompt bloat)
✓ Avg output tokens per call (catch runaway responses)
✓ Cache hit rate
✓ Provider mix
✓ Cost per query (per endpoint)
✓ Cost per user (DAU normalization)
```

---

## Pricing Examples (2026)

```
Provider / Model         Input ($/1M)  Output ($/1M)
─────────────────────────────────────────────────────
OpenAI gpt-4o            2.50          10.00
OpenAI gpt-4o-mini       0.15          0.60
OpenAI o1                15.00         60.00
OpenAI o1-mini           3.00          12.00
Anthropic Claude Sonnet  3.00          15.00
Anthropic Claude Opus    15.00         75.00
Anthropic Claude Haiku   0.25          1.25
Google Gemini Pro        1.25          5.00
Groq Llama-3-70B         0.59          0.79
DeepSeek V3              0.27          1.10
Together Llama-3-70B     0.88          0.88

Embedding models:
OpenAI text-embed-3-small  0.02 (input only)
OpenAI text-embed-3-large  0.13
Voyage voyage-3            0.06
Cohere embed-v3            0.10
```

---

## Common Pitfalls

```
1. ✗ Not measuring before optimizing
   ✓ Cost tracker FIRST

2. ✗ Over-aggressive caching → wrong responses
   ✓ Tune threshold; sample audit cache hits

3. ✗ Sending full history every turn
   ✓ Trim or summarize

4. ✗ Forgetting max_tokens
   ✓ Tight caps by task

5. ✗ One model for everything
   ✓ Route by complexity

6. ✗ No per-tenant quotas
   → One bad tenant burns budget
   ✓ Quotas + alerts

7. ✗ Prompts bloat over time
   → "Just one more example..."
   ✓ Regular prompt audits

8. ✗ Optimizing the wrong endpoint
   ✓ Pareto: 80% of cost from 20% of endpoints

9. ✗ Not using prompt caching when applicable
   → Free 50-90% savings on long contexts
   ✓ Anthropic explicit, OpenAI automatic

10. ✗ Self-hosting too early
    → Ops overhead > API savings until very high volume
    ✓ Stay on APIs until 10M+ tokens/day
```

---

## Interview Questions

### Q1: How would you reduce LLM costs by 80%?

Layered approach:
1. **Measure** with cost tracker
2. **Cache** semantically (20-40% savings)
3. **Route** by complexity (50-70% on average)
4. **Compress** prompts (2-5x reduction)
5. **Trim** history (avoid resending)
6. **Prompt cache** at provider (50-90% on stable prefixes)
7. **Distill** to small models for narrow tasks (95% on those)

Combined: 80-95% achievable.

### Q2: What's the ROI of semantic caching?

Build cost: 1-2 engineer-weeks (Redis setup, embeddings, similarity check). Savings depend on cache hit rate. For 60% hit rate on $10k/month spend: ~$6k/month saved = 4-week payback.

### Q3: When does it make sense to fine-tune your own model?

When: (a) high volume (>1M calls/day), (b) narrow task, (c) you have 5k+ labeled examples (or can generate from GPT-4o), (d) ops capacity for serving. Common: distill GPT-4o on customer support intent classification.

### Q4: How does Anthropic prompt caching work?

You mark parts of the prompt with `cache_control: {"type": "ephemeral"}`. First call: 25% surcharge on cached tokens (write). Subsequent calls within 5 min TTL: 90% discount on those tokens (read). Best for long, stable system prompts + few-shot examples.

### Q5: What's the cost difference between input and output tokens?

Output is 2-4x more expensive than input (varies by provider). e.g., GPT-4o: $2.50 in / $10.00 out. **Implication**: minimizing output (`max_tokens`, stop sequences) often saves more than minimizing input.

---

## Senior Mantras

```
1. MEASURE first. Optimize specific costs, not vague feelings.

2. Cheap model for 80% of queries. Expensive for hard 20%.

3. Semantic cache pays for itself in weeks.

4. Provider prompt caching = free if you structure right.

5. Output tokens cost 2-4x input. Cap them.

6. Trim conversation history. Don't resend everything.

7. Batch embeddings. 100 at a time.

8. Per-tenant quotas prevent budget surprises.

9. Distillation = 95% savings on narrow high-volume tasks.

10. Self-host only when API costs exceed ~$50k/month.
```

---

## Related

- [08_observability.md](08_observability.md) — cost monitoring infrastructure
- [09_guardrails.md](09_guardrails.md) — prevent runaway costs from prompts
- [../Level3_LLM_APIs_SDKs/10_cost_optimization.md](../Level3_LLM_APIs_SDKs/10_cost_optimization.md) — basics
- [../Level3_LLM_APIs_SDKs/05_streaming_responses.md](../Level3_LLM_APIs_SDKs/05_streaming_responses.md) — cancel on disconnect
- [../Level6_Agent_Patterns/08_routing.md](../Level6_Agent_Patterns/08_routing.md) — model routing deep
- [../../Backend_Developer/00_Year0-2_Junior/09_Caching/theory/06_semantic_caching_llm.md](../../Backend_Developer/00_Year0-2_Junior/09_Caching/theory/06_semantic_caching_llm.md) — semantic cache implementation
