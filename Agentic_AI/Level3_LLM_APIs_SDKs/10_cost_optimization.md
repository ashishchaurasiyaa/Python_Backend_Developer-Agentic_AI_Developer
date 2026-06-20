# Level 3 — Doc 10: Cost Tracking & Optimization

> **Goal:** LLM costs scale fast. Track every call, optimize hot paths. Save 50-90% with right techniques.

---

## 1. The Cost Reality

Naive: gpt-4o at $2.50/$10 per 1M tokens.
For 1000 users × 100 queries/day × 1000 tokens average:
```
100M tokens/day input + 50M output 
= $250 input + $500 output 
= $750/day = $22,500/month
```

That's BEFORE growth. Optimization can drop this 90%.

---

## 2. Cost Tracking Pattern

```python
PRICING = {
    "gpt-4o-mini":      {"input": 0.15,  "output": 0.60},
    "gpt-4o":           {"input": 2.50,  "output": 10.00},
    "claude-3-5-haiku": {"input": 0.25,  "output": 1.25},
    "claude-3-5-sonnet":{"input": 3.00,  "output": 15.00},
    "o1-mini":          {"input": 3.00,  "output": 12.00},
    "o1":               {"input": 15.00, "output": 60.00},
}


def calculate_cost(model: str, usage) -> float:
    p = PRICING[model]
    return (
        usage.prompt_tokens * p["input"] +
        usage.completion_tokens * p["output"]
    ) / 1_000_000


# Wrap your LLM calls
class CostTrackingClient:
    def __init__(self, openai_client):
        self.client = openai_client
        self.total_cost = 0
        self.calls = []
    
    def call(self, **kwargs):
        response = self.client.chat.completions.create(**kwargs)
        cost = calculate_cost(kwargs["model"], response.usage)
        self.total_cost += cost
        self.calls.append({
            "model": kwargs["model"],
            "input_tokens": response.usage.prompt_tokens,
            "output_tokens": response.usage.completion_tokens,
            "cost": cost,
            "timestamp": time.time()
        })
        return response
```

---

## 3. Cost Per User (Multi-tenant)

```python
class TenantCostTracker:
    def __init__(self):
        self.costs = defaultdict(float)
        self.limits = {}
    
    def track(self, user_id, cost):
        self.costs[user_id] += cost
    
    def can_call(self, user_id):
        limit = self.limits.get(user_id, 1.0)  # Default $1/day
        return self.costs[user_id] < limit
    
    def reset_daily(self):
        # Cron job
        self.costs = defaultdict(float)

tracker = TenantCostTracker()

def serve(user_id, query):
    if not tracker.can_call(user_id):
        return "Daily budget exceeded"
    response = llm_call(query)
    tracker.track(user_id, response.cost)
    return response
```

---

## 4. Cost Optimization Strategies

### A. Use Cheaper Model When Possible
```python
def smart_model_router(query, complexity):
    if complexity == "simple":
        return "gpt-4o-mini"   # 16x cheaper than gpt-4o
    elif complexity == "medium":
        return "claude-3-5-haiku-20241022"
    else:
        return "claude-3-5-sonnet-20241022"
```

10-100x cost difference. Most queries → cheap model.

### B. Anthropic Prompt Caching (90% Discount!)
```python
client = anthropic.Anthropic()          # pehle client banao — module pe seedha .messages nahi hota
response = client.messages.create(
    model="claude-3-5-sonnet-20241022",
    system=[{
        "type": "text",
        "text": LONG_SYSTEM_PROMPT,
        "cache_control": {"type": "ephemeral"}
    }],
    messages=[...]
)
```

Long prompts → 90% cheaper on subsequent calls (5-min cache TTL).

### C. Semantic Caching
Same QUESTION → same ANSWER, no LLM call needed.

```python
import hashlib
from sentence_transformers import SentenceTransformer

class SemanticCache:
    def __init__(self, threshold=0.95):
        self.cache = {}  # embedding → answer
        self.embedder = SentenceTransformer('all-MiniLM-L6-v2')
        self.threshold = threshold
    
    def get(self, query):
        q_emb = self.embedder.encode(query)
        for cached_emb, answer in self.cache.items():
            sim = cosine_sim(q_emb, cached_emb)
            if sim > self.threshold:
                return answer  # Cache hit!
        return None
    
    def set(self, query, answer):
        emb = self.embedder.encode(query)
        self.cache[tuple(emb)] = answer

cache = SemanticCache()
def cached_llm_call(query):
    cached = cache.get(query)
    if cached:
        return cached
    answer = llm_call(query)
    cache.set(query, answer)
    return answer
```

In production: use Redis Vector or Pinecone for cache.

### D. Batch API (50% Discount)
For non-real-time:
```python
client.batches.create(
    input_file_id="file-...",
    endpoint="/v1/chat/completions",
    completion_window="24h"
)
```
- 24h turnaround
- 50% cheaper
- Good for: data labeling, bulk processing, eval runs

### E. Compress Prompts
```python
# Verbose: 50 tokens
"Please carefully read the following text and provide a detailed summary..."

# Compact: 5 tokens
"Summarize:"
```

Cut filler words. LLM doesn't need pleasantries.

### F. Limit Output Length
```python
client.chat.completions.create(
    max_tokens=200,  # Don't pay for unnecessary long output
    ...
)
```

Specify in prompt too: "Answer in 1 sentence."

### G. Cache LLM Tools (Like Tavily)
Search results from same query → cached:
```python
@lru_cache(maxsize=1000)
def cached_search(query):
    return tavily.search(query)
```

---

## 5. Reduce Context Size

### Summarize old conversation
```python
# Bad — keep full 50-turn history (huge prompt)
messages = full_history  # 50 messages

# Good — summarize older
if len(messages) > 20:
    old = messages[:-10]
    summary = llm_call(f"Summarize this conversation: {old}")
    messages = [
        {"role": "system", "content": f"Summary so far: {summary}"},
        *messages[-10:]  # Last 10
    ]
```

### RAG instead of stuffing context
Don't pass 50 docs to LLM. Retrieve top 3-5.

---

## 6. Cost Monitoring Dashboard

```python
# Aggregate stats
def daily_report():
    return {
        "total_cost": sum(call.cost for call in today_calls),
        "by_model": {
            model: sum(c.cost for c in today_calls if c.model == model)
            for model in PRICING
        },
        "by_user": {
            user_id: tracker.costs[user_id]
            for user_id in tracker.costs
        },
        "p99_cost": np.percentile([c.cost for c in today_calls], 99)
    }
```

Visualize in Grafana/Datadog.

---

## 7. Alerts

```python
# Set thresholds
ALERTS = [
    ("daily_cost > $100", "notify_engineering"),
    ("user_cost > $10", "rate_limit_user"),
    ("hourly_cost > $20", "investigate_spike"),
    ("cost_per_query > $0.10", "review_prompts"),
]
```

---

## 8. ROI Per Feature

Track which features cost most:
```python
@track_cost
def feature_summarize(text):
    return llm_call(f"Summarize: {text}")

@track_cost
def feature_translate(text):
    return llm_call(f"Translate: {text}")

# After a week:
# summarize: $50, 1000 uses → $0.05/use, popular feature, OK
# translate: $200, 50 uses → $4/use, expensive, optimize or charge
```

---

## 9. Cost Calculator

```python
def estimate_monthly_cost(
    users_per_day: int,
    queries_per_user: int,
    avg_input_tokens: int,
    avg_output_tokens: int,
    model: str = "gpt-4o-mini"
):
    p = PRICING[model]
    daily_input = users_per_day * queries_per_user * avg_input_tokens
    daily_output = users_per_day * queries_per_user * avg_output_tokens
    
    daily_cost = (daily_input * p["input"] + daily_output * p["output"]) / 1_000_000
    return daily_cost * 30

# Estimate
print(estimate_monthly_cost(
    users_per_day=1000,
    queries_per_user=10,
    avg_input_tokens=500,
    avg_output_tokens=300,
    model="gpt-4o-mini"
))  # ~$23/month
```

---

## 10. Key Takeaways

✅ Track every LLM call's cost
✅ Per-user budgets and limits
✅ **Use cheapest model that works** (10-100x savings)
✅ Anthropic prompt caching = 90% savings
✅ Semantic caching = huge savings for repeated queries
✅ Batch API = 50% off (when 24h delay OK)
✅ Compress prompts, limit output length
✅ Cache external tool calls (search results)
✅ Monitor + alert on cost spikes
✅ Calculate ROI per feature

**Next:** Modern topics — voice agents, computer use, local serving.
