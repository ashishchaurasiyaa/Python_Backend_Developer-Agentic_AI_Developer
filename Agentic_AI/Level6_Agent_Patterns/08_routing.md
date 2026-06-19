# Level 6.8 — Routing & Classification
**Phase: Agent Patterns | Production-Critical**

## Quick Concepts

- **Routing** = sending a query to the right handler (agent / model / skill)
- **Classification** = labeling a query (intent, category, complexity)
- **Semantic router** = match by embedding similarity to predefined intents
- **LLM router** = classify with LLM call
- **Rule-based router** = keyword/regex matching
- **Model router** = pick between models by query complexity
- **Skill / Tool router** = pick which tools/agents handle the request

---

## Why Routing Matters

```
Naive setup:
   Every query → biggest, most expensive model
   ✗ Costs $$$ on simple queries
   ✗ Slow on simple queries (overkill)

With routing:
   Query → classify → pick best model
   ✓ Simple "yes/no" → cheap gpt-4o-mini ($0.15/1M)
   ✓ Complex reasoning → claude-opus ($15/1M)
   → 5-10x cost savings + faster simple queries

Use cases:
   ✓ Multi-tenant SaaS (route by tenant tier)
   ✓ Multi-agent systems (specialist agents)
   ✓ Cost optimization (cheap vs expensive models)
   ✓ Domain routing (support vs sales vs technical)
   ✓ Complexity-based escalation
```

---

## Pattern 1: Rule-Based Router (Cheapest)

```python
def rule_route(query: str) -> str:
    """Keyword / regex based routing. Free + instant."""
    
    q = query.lower()
    
    if any(w in q for w in ["price", "cost", "billing", "invoice"]):
        return "billing_agent"
    
    if any(w in q for w in ["bug", "error", "crash", "broken"]):
        return "tech_support_agent"
    
    if "refund" in q or "cancel" in q:
        return "retention_agent"
    
    return "general_agent"


# Routes to ZERO LLM call. Fast, free.
agent = get_agent(rule_route(user_query))
response = await agent.handle(user_query)
```

**When good:** Clear keywords, narrow domain, high volume.
**When bad:** Nuanced queries, paraphrasing, multilingual.

---

## Pattern 2: Semantic Router

Match query embedding to predefined intent embeddings.

```python
from sentence_transformers import SentenceTransformer
import numpy as np

# Define intents with example queries
INTENT_EXAMPLES = {
    "billing": [
        "What's my invoice for last month?",
        "How much does the pro plan cost?",
        "Can I get a refund?",
    ],
    "tech_support": [
        "The app crashes when I click submit",
        "I'm getting a 500 error",
        "Login is broken",
    ],
    "general": [
        "How do I use this feature?",
        "Where is X menu?",
        "Tell me about the product",
    ],
}

model = SentenceTransformer("BAAI/bge-small-en-v1.5")

# Pre-compute intent centroids
intent_centroids = {}
for intent, examples in INTENT_EXAMPLES.items():
    embeddings = model.encode(examples)
    intent_centroids[intent] = np.mean(embeddings, axis=0)


def semantic_route(query: str) -> tuple[str, float]:
    """Return (intent, confidence)."""
    query_emb = model.encode([query])[0]
    
    scores = {
        intent: np.dot(query_emb, centroid)
        for intent, centroid in intent_centroids.items()
    }
    
    best_intent = max(scores, key=scores.get)
    confidence = scores[best_intent]
    
    return best_intent, confidence


# Usage
intent, conf = semantic_route("My credit card was charged twice!")
if conf > 0.6:
    agent = get_agent(intent)
else:
    agent = get_agent("general")  # fallback
```

**Pros:** Handles paraphrasing, multilingual, no LLM call.
**Cons:** Need example queries, embedding model dependency.

---

## Pattern 3: LLM-Based Router

```python
ROUTER_SYSTEM = """
You are a router. Classify the user query into ONE of these categories:

- billing: questions about pricing, invoices, refunds, subscriptions
- tech_support: bugs, errors, things not working
- product_info: how features work, documentation queries
- sales: pricing inquiries from potential customers
- other: anything that doesn't fit

Respond with ONLY the category name. No explanation.
"""


async def llm_route(query: str) -> str:
    response = await client.chat.completions.create(
        model="gpt-4o-mini",  # cheap router
        messages=[
            {"role": "system", "content": ROUTER_SYSTEM},
            {"role": "user", "content": query},
        ],
        temperature=0,
        max_tokens=10,
    )
    return response.choices[0].message.content.strip().lower()
```

**Pros:** Most accurate, handles nuance.
**Cons:** ~$0.0001/query + 100-200ms latency.

---

## Pattern 4: Model-Complexity Router

Route by query complexity → cheaper for simple, expensive for hard.

```python
async def complexity_route(query: str) -> str:
    """Decide which model handles this query."""
    
    # Quick classification with cheap model
    classification = await client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{
            "role": "user",
            "content": f"""
            Classify this query:
            - simple: one-liner answer, lookup, basic fact
            - medium: requires reasoning, multi-step
            - complex: math, deep analysis, complex code
            
            Query: {query}
            
            Answer with one word: simple/medium/complex
            """,
        }],
        max_tokens=5,
        temperature=0,
    )
    
    complexity = classification.choices[0].message.content.strip().lower()
    
    model_map = {
        "simple": "gpt-4o-mini",      # $0.15 input / $0.60 output per 1M
        "medium": "gpt-4o",           # $2.50 / $10
        "complex": "claude-opus-4",   # $15 / $75
    }
    
    return model_map.get(complexity, "gpt-4o-mini")


async def smart_answer(query: str):
    model = await complexity_route(query)
    response = await client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": query}],
    )
    return response.choices[0].message.content, model
```

**Savings:** If 70% queries are simple, you save ~80% on model cost vs using GPT-4o for everything.

---

## Pattern 5: Hybrid Router (Production)

Combine multiple routers for best of all worlds:

```python
class HybridRouter:
    def __init__(self):
        self.semantic = SemanticRouter()
        self.rule_patterns = {
            r"\$|\bcost\b|\bprice\b": "billing",
            r"\berror\b|\bbug\b|\bcrash\b": "tech_support",
        }
    
    async def route(self, query: str) -> str:
        # Step 1: Quick rule check (free)
        for pattern, intent in self.rule_patterns.items():
            if re.search(pattern, query.lower()):
                return intent
        
        # Step 2: Semantic match (cheap)
        intent, confidence = self.semantic.route(query)
        if confidence > 0.7:
            return intent
        
        # Step 3: LLM fallback (most accurate)
        return await llm_route(query)
```

**Result:**
- 70% queries: rule match (0 cost)
- 25% queries: semantic match (~$0.000001)
- 5% queries: LLM route (~$0.0001)

Avg cost: ~$0.000006 per query routing.

---

## Pattern 6: Multi-Skill Router (Tool Use)

Route to specialized agents/tools:

```python
SKILLS = {
    "search_kb": {
        "description": "Search the knowledge base for documentation",
        "handler": kb_agent,
        "examples": ["how does X work", "documentation for Y"],
    },
    "create_ticket": {
        "description": "File a support ticket for bugs",
        "handler": ticket_agent,
        "examples": ["report a bug", "something is broken"],
    },
    "billing_query": {
        "description": "Answer billing and pricing questions",
        "handler": billing_agent,
        "examples": ["my invoice", "pricing tiers"],
    },
    "general_chat": {
        "description": "Conversational fallback",
        "handler": chat_agent,
        "examples": [],
    },
}


async def route_to_skill(query: str):
    skills_desc = "\n".join([
        f"- {name}: {s['description']}"
        for name, s in SKILLS.items()
    ])
    
    response = await client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{
            "role": "user",
            "content": f"""
            Available skills:
            {skills_desc}
            
            User query: {query}
            
            Which skill should handle this? Respond with skill name only.
            """,
        }],
        max_tokens=20,
        temperature=0,
    )
    
    skill_name = response.choices[0].message.content.strip()
    skill = SKILLS.get(skill_name, SKILLS["general_chat"])
    return await skill["handler"](query)
```

---

## Production Pattern: Confidence + Fallback

```python
async def confident_route(query: str):
    # Try cheap router first
    intent, confidence = semantic_router.route(query)
    
    if confidence < CONFIDENCE_THRESHOLD:
        # Escalate to LLM router
        intent = await llm_router.route(query)
        log_low_confidence(query, intent)  # learning signal
    
    # Get agent
    agent = AGENTS.get(intent, AGENTS["general"])
    
    try:
        response = await agent.handle(query)
        log_routing_success(query, intent)
        return response
    except CannotHandleError:
        # Agent doesn't think it can handle — try general
        return await AGENTS["general"].handle(query)
```

---

## Routing for RAG

Route to different document collections / indexes:

```python
COLLECTIONS = {
    "docs": vector_db.collection("documentation"),
    "code": vector_db.collection("codebase"),
    "support": vector_db.collection("support_tickets"),
    "blog": vector_db.collection("blog_posts"),
}


async def rag_route(query: str) -> list[str]:
    """Decide which collections to search."""
    
    response = await client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{
            "role": "user",
            "content": f"""
            Which of these collections should we search for this query?
            (Choose 1-3, comma-separated, no explanation):
            
            - docs: official documentation
            - code: source code examples
            - support: past customer issues
            - blog: blog posts and articles
            
            Query: {query}
            """,
        }],
        max_tokens=20,
        temperature=0,
    )
    
    collections = [c.strip() for c in response.choices[0].message.content.split(",")]
    return [c for c in collections if c in COLLECTIONS]


async def routed_rag(query: str):
    collections_to_search = await rag_route(query)
    
    all_results = []
    for c_name in collections_to_search:
        c_results = COLLECTIONS[c_name].search(
            await embed(query), top_k=3,
        )
        all_results.extend(c_results)
    
    # Rerank combined results, generate answer
    return await answer_from(query, all_results)
```

---

## Caching Routing Decisions

```python
from functools import lru_cache
import hashlib


def query_fingerprint(query: str) -> str:
    """Normalize + hash for caching."""
    normalized = query.lower().strip()
    return hashlib.md5(normalized.encode()).hexdigest()


@lru_cache(maxsize=10000)
def cached_route_decision(fingerprint: str) -> str:
    """Cache routing for repeat queries."""
    # Actual routing logic
    return llm_route(...)


async def cached_route(query: str) -> str:
    fp = query_fingerprint(query)
    return cached_route_decision(fp)
```

Or use Redis with TTL for distributed caching:

```python
import redis.asyncio as redis

cache = redis.Redis()


async def cached_route(query: str) -> str:
    key = f"route:{query_fingerprint(query)}"
    cached = await cache.get(key)
    if cached:
        return cached.decode()
    
    intent = await llm_route(query)
    await cache.setex(key, 3600, intent)  # 1hr TTL
    return intent
```

---

## Routing Quality Metrics

```python
class RoutingTracker:
    def __init__(self):
        self.decisions = []
    
    def log(self, query, route, confidence, outcome):
        self.decisions.append({
            "query": query,
            "route": route,
            "confidence": confidence,
            "outcome": outcome,  # "success" / "wrong_route" / "no_answer"
        })
    
    def routing_accuracy(self):
        successful = sum(1 for d in self.decisions if d["outcome"] == "success")
        return successful / len(self.decisions)
    
    def low_confidence_rate(self):
        low_conf = sum(1 for d in self.decisions if d["confidence"] < 0.5)
        return low_conf / len(self.decisions)
    
    def confusion_matrix(self):
        # build matrix of routed → actual_intent
        ...
```

Metrics to track:
- Routing accuracy (vs ground truth labels)
- Low-confidence rate (need better examples?)
- Fallback rate (going to "general"?)
- Cost per routed query
- Latency per route type

---

## Cost Comparison

```
Strategy                  Cost/query    Accuracy   Latency
─────────────────────────────────────────────────────────────
Rule-based                $0            70-85%     <1ms
Semantic (embedding)      ~$0.000001    85-92%     20-50ms
LLM (gpt-4o-mini)        ~$0.0001      92-98%     150-300ms
Hybrid (rules→semantic→LLM)  ~$0.000006  95-98%   ~30ms avg

Best practice:
   1. Rules for top 50% volume (known patterns)
   2. Semantic for next 40%
   3. LLM for hard 10%
```

---

## Common Pitfalls

```
1. ✗ LLM-routing every query
   → Cost compounds quickly
   ✓ Hybrid with rules/semantic first

2. ✗ Stale intent examples
   → Semantic router drifts as language evolves
   ✓ Re-update example queries quarterly

3. ✗ No fallback for "other"
   → Queries that don't match any intent crash
   ✓ Always have "general" or "unsure" route

4. ✗ Confidence threshold too aggressive
   → Routes to wrong place often
   ✓ Calibrate threshold with eval set

5. ✗ Not logging routing decisions
   → Can't improve later
   ✓ Log query + decision + outcome

6. ✗ Same router for all tenants
   → Domain-specific routing missed
   ✓ Per-tenant intent sets (if multi-tenant)

7. ✗ Routing without query rewriting
   → Bad query phrasing fails router
   ✓ Light normalization first
```

---

## LangGraph Routing Example

```python
from langgraph.graph import StateGraph, END


def route_decision(state):
    """Conditional edge function."""
    query = state["query"]
    
    if "billing" in query.lower():
        return "billing"
    if "error" in query.lower():
        return "support"
    return "general"


graph = StateGraph(dict)
graph.add_node("billing", billing_agent)
graph.add_node("support", support_agent)
graph.add_node("general", general_agent)

graph.set_entry_point("router")  # virtual
graph.add_conditional_edges("router", route_decision, {
    "billing": "billing",
    "support": "support",
    "general": "general",
})

# All routes end the graph
graph.add_edge("billing", END)
graph.add_edge("support", END)
graph.add_edge("general", END)
```

---

## Interview Questions

### Q1: How would you design a router for a multi-tenant LLM chat app?

Hybrid:
1. Rules for keyword patterns (free, fast)
2. Semantic router using pre-computed intent centroids (cheap, ~50ms)
3. LLM fallback for low-confidence queries
4. Per-tenant: allow custom intent sets
5. Cache decisions for hot queries
6. Track accuracy + low-confidence rates for tuning

### Q2: When use semantic router vs LLM router?

- **Semantic**: high volume, latency-sensitive, intent set rarely changes
- **LLM**: low volume, nuanced queries, intents change frequently

Hybrid is usually best.

### Q3: How do you handle a query that doesn't match any intent?

(1) Confidence threshold — if below, route to "general" or "human escalation". (2) Log the query for review (likely new intent emerging). (3) Periodically review unrouted queries → expand intent set.

### Q4: What metrics matter for routing quality?

- Accuracy (vs ground truth)
- Latency per route
- Cost per query
- Fallback rate (going to "general")
- Coverage (% of queries with high confidence)

### Q5: How do you A/B test a new router?

(1) Mirror traffic: route 100% through old, also route through new (no user impact). (2) Compare decisions. (3) Where they differ, sample for human review. (4) Calibrate confidence threshold. (5) Gradual rollout (5% → 25% → 100%).

---

## Senior Mantras

```
1. Routing is the cheapest LLM cost optimization.

2. Hybrid > pure LLM router. 80/20 rule applies.

3. Always have a fallback intent ("general").

4. Cache routing decisions for hot queries.

5. Log every routing decision. You'll need it.

6. Confidence thresholds need calibration on your data.

7. Re-evaluate intent examples quarterly.

8. Different model complexity = different routing.
   GPT-4o-mini for routing, GPT-4o for hard tasks.

9. Semantic router beats LLM router on latency.

10. Test routing in isolation before integration.
```

---

## Related

- [04_react_pattern.md](04_react_pattern.md) — ReAct picks tools
- [07_multi_agent_supervisor.md](07_multi_agent_supervisor.md) — supervisor IS a router
- [10_agent_evaluation.md](10_agent_evaluation.md) — measure routing quality
- [../Level5_RAG_Vector_Databases/08_query_transformation.md](../Level5_RAG_Vector_Databases/08_query_transformation.md) — route to collections
- [../../Backend_Developer/00_Year0-2_Junior/06_FastAPI/32_function_calling_endpoints.md](../../Backend_Developer/00_Year0-2_Junior/06_FastAPI/32_function_calling_endpoints.md) — tool calling
