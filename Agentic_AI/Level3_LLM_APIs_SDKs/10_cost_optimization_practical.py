"""
Level3 — Doc 10: Cost Tracking & Optimization — PRACTICAL LAB
==============================================================
KYA SEEKHENGE (What we will learn):
  1. Cost tracking pattern — har LLM call ka paisa count karo
  2. Pricing table — different models ke rates
  3. Smart model router — complexity dekho, sahi model chuno
  4. Token compression — prompt ko chhota karo, cost bachao
  5. Semantic cache (offline demo) — same question → same answer, no API call
  6. Per-user budget tracker (TenantCostTracker)
  7. Monthly cost estimator / calculator
  8. ROI per feature — kaunsa feature kitna costly hai
  9. Alert thresholds — kab engineer ko ping karna hai
 10. Daily report / dashboard summary

KAISE CHALANA (How to run):
  uv run python Level3_LLM_APIs_SDKs/10_cost_optimization_practical.py

  With live Groq calls:
  GROQ_API_KEY=gsk_... uv run python Level3_LLM_APIs_SDKs/10_cost_optimization_practical.py

NOTE: Bina key ke bhi EXIT 0 hoga — offline demo mode chalega.
"""

# ─── Standard imports ─────────────────────────────────────────────────────────
import os
import sys
import time
import json
import hashlib
import math
from collections import defaultdict
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Optional, List, Dict, Any

# ─── API key check — crash nahi karna, gracefully degrade karna ───────────────
# IMPORTANT: OpenAI() constructor None key pe crash karta hai, isliye fallback placeholder use karo
GROQ_API_KEY = os.getenv("GROQ_API_KEY") or "placeholder"
LIVE_MODE = GROQ_API_KEY != "placeholder"

if not LIVE_MODE:
    print("[INFO] GROQ_API_KEY nahi mila — OFFLINE DEMO MODE chalega, EXIT 0 guarantee hai.")
else:
    print(f"[INFO] GROQ_API_KEY mila — LIVE mode active.")

print("=" * 65)
print("  Level3 — Cost Tracking & Optimization — PRACTICAL LAB")
print("=" * 65)


# ─── Helper: get_client() — Groq free tier use karo (OpenAI-compatible) ───────
def get_client():
    """
    Groq ka free-tier client return karo (OpenAI SDK compatible).
    Agar key nahi hai to None return hoga — callers check karein.
    """
    if not LIVE_MODE:
        return None
    try:
        from openai import OpenAI
        client = OpenAI(
            api_key=GROQ_API_KEY,
            base_url="https://api.groq.com/openai/v1",
        )
        return client
    except ImportError:
        print("  [WARN] openai package nahi mila — pip install openai")
        return None


# =============================================================================
# SECTION 1: PRICING TABLE — theory doc se seedha liya
# =============================================================================
print("\n" + "=" * 65)
print("SECTION 1: PRICING TABLE — model costs per 1M tokens")
print("=" * 65)

# Ye rates theory doc se hain: $/1M tokens
PRICING: Dict[str, Dict[str, float]] = {
    "gpt-4o-mini":              {"input": 0.15,  "output": 0.60},
    "gpt-4o":                   {"input": 2.50,  "output": 10.00},
    "claude-3-5-haiku-20241022": {"input": 0.25,  "output": 1.25},
    "claude-3-5-sonnet-20241022":{"input": 3.00,  "output": 15.00},
    "o1-mini":                  {"input": 3.00,  "output": 12.00},
    "o1":                       {"input": 15.00, "output": 60.00},
    # Groq free tier models (inference fast + free quota)
    "llama-3.1-8b-instant":     {"input": 0.05,  "output": 0.08},
    "llama-3.3-70b-versatile":  {"input": 0.59,  "output": 0.79},
    "gemma2-9b-it":             {"input": 0.20,  "output": 0.20},
}

print(f"\n  {'Model':<35} {'Input $/1M':>12} {'Output $/1M':>12}")
print("  " + "-" * 60)
for model, rates in PRICING.items():
    print(f"  {model:<35} {rates['input']:>12.2f} {rates['output']:>12.2f}")

print("\n  INSIGHT: gpt-4o vs gpt-4o-mini — input mein ~16x farq hai!")
print("  Zyada tar queries cheap model se ho jati hain.")


# =============================================================================
# SECTION 2: COST CALCULATION FUNCTION — theory doc pattern
# =============================================================================
print("\n" + "=" * 65)
print("SECTION 2: COST CALCULATION — har call ka paisa calculate karo")
print("=" * 65)


def calculate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """
    Theory doc formula:
      cost = (input_tokens * input_price + output_tokens * output_price) / 1_000_000
    """
    if model not in PRICING:
        # Unknown model — default to gpt-4o-mini estimate
        p = PRICING["gpt-4o-mini"]
    else:
        p = PRICING[model]
    return (input_tokens * p["input"] + output_tokens * p["output"]) / 1_000_000


# Demo: ek call ka cost kitna hoga
demo_calls = [
    ("gpt-4o",              500, 200),
    ("gpt-4o-mini",         500, 200),
    ("llama-3.1-8b-instant",500, 200),
    ("claude-3-5-haiku-20241022", 500, 200),
]

print(f"\n  Same query (500 input + 200 output tokens) — different models:")
print(f"  {'Model':<35} {'Cost (USD)':>12}")
print("  " + "-" * 50)
for model, inp, out in demo_calls:
    cost = calculate_cost(model, inp, out)
    print(f"  {model:<35} ${cost:>11.6f}")


# =============================================================================
# SECTION 3: COST TRACKING CLIENT — theory doc ka CostTrackingClient
# =============================================================================
print("\n" + "=" * 65)
print("SECTION 3: COST TRACKING CLIENT — wrap karo LLM calls ko")
print("=" * 65)


@dataclass
class CallRecord:
    """Ek LLM call ka complete record."""
    model: str
    input_tokens: int
    output_tokens: int
    cost: float
    timestamp: float
    feature: str = "unknown"  # ROI tracking ke liye


class CostTrackingClient:
    """
    Theory doc ka CostTrackingClient — har call track karta hai.
    Real OpenAI client ko wrap karta hai, ya MOCK mode mein fake data deta hai.
    """

    def __init__(self, openai_client=None, default_model: str = "llama-3.1-8b-instant"):
        self.client = openai_client          # None = mock mode
        self.default_model = default_model
        self.total_cost: float = 0.0
        self.calls: List[CallRecord] = []

    def call(
        self,
        messages: List[Dict],
        model: Optional[str] = None,
        max_tokens: int = 200,
        feature: str = "unknown",
    ) -> str:
        """
        LLM call karo — real ya mock.
        Har call ke baad cost accumulate hoti hai.
        """
        model = model or self.default_model

        if self.client is not None:
            # LIVE MODE — real API call
            try:
                response = self.client.chat.completions.create(
                    model=model,
                    messages=messages,
                    max_tokens=max_tokens,
                )
                inp_tok = response.usage.prompt_tokens
                out_tok = response.usage.completion_tokens
                text    = response.choices[0].message.content or ""
            except Exception as e:
                print(f"  [WARN] Live call failed: {e} — mock data use kar raha hai")
                inp_tok, out_tok, text = 120, 60, f"[Mock fallback: {model}]"
        else:
            # OFFLINE MOCK — fake tokens aur response
            inp_tok = sum(len(m.get("content", "").split()) * 1.3 for m in messages)
            inp_tok = int(max(inp_tok, 50))
            out_tok = min(max_tokens, 80)
            text    = f"[MOCK RESPONSE from {model} | feature={feature}]"

        cost = calculate_cost(model, inp_tok, out_tok)
        record = CallRecord(
            model=model,
            input_tokens=inp_tok,
            output_tokens=out_tok,
            cost=cost,
            timestamp=time.time(),
            feature=feature,
        )
        self.total_cost += cost
        self.calls.append(record)
        return text

    def summary(self) -> Dict[str, Any]:
        """Cost summary nikalo — monitoring dashboard ke liye."""
        by_model: Dict[str, float] = defaultdict(float)
        by_feature: Dict[str, float] = defaultdict(float)
        for c in self.calls:
            by_model[c.model] += c.cost
            by_feature[c.feature] += c.cost
        return {
            "total_calls": len(self.calls),
            "total_cost_usd": self.total_cost,
            "by_model": dict(by_model),
            "by_feature": dict(by_feature),
        }


# Demo — tracking client banao aur kuch calls karo
tracker_client = CostTrackingClient(openai_client=get_client())

print("\n  Kuch mock/live calls kar ke cost track karte hain...")

for feature, prompt in [
    ("summarize", "Summarize: Python is a high-level programming language."),
    ("translate",  "Translate to Hindi: Hello, how are you?"),
    ("summarize",  "Summarize: Machine learning is a subset of AI."),
    ("classify",   "Classify sentiment: I love this product!"),
]:
    result = tracker_client.call(
        messages=[{"role": "user", "content": prompt}],
        feature=feature,
        max_tokens=100,
    )
    print(f"  [{feature}] -> {result[:60]}...")

summary = tracker_client.summary()
print(f"\n  SUMMARY:")
print(f"    Total calls:    {summary['total_calls']}")
print(f"    Total cost:     ${summary['total_cost_usd']:.6f}")
print(f"    By feature:     {summary['by_feature']}")


# =============================================================================
# SECTION 4: SMART MODEL ROUTER — complexity ke hisab se model chuno
# =============================================================================
print("\n" + "=" * 65)
print("SECTION 4: SMART MODEL ROUTER — sahi model, sahi jagah")
print("=" * 65)

# Theory doc: "Use Cheaper Model When Possible" — 10-100x savings


def classify_complexity(query: str) -> str:
    """
    Heuristic se query complexity estimate karo.
    Real system mein: ek cheap LLM call se classify karo.

    SIMPLE  — factual, short, exact answer chahiye
    MEDIUM  — explanation, kuch reasoning chahiye
    COMPLEX — multi-step, coding, creative, analysis
    """
    q = query.lower()
    # Simple signals — calculation, lookup, yes/no
    simple_keywords = ["what is", "define", "how many", "calculate", "when did", "who is"]
    complex_keywords = ["explain", "analyze", "compare", "write code", "design", "pros and cons", "strategy"]

    if any(kw in q for kw in complex_keywords):
        return "complex"
    elif any(kw in q for kw in simple_keywords):
        return "simple"
    else:
        return "medium"


def smart_model_router(query: str) -> str:
    """
    Theory doc ka smart_model_router:
      simple  -> cheapest model (16x cheaper)
      medium  -> mid-tier
      complex -> best model
    """
    complexity = classify_complexity(query)
    route_map = {
        "simple":  "llama-3.1-8b-instant",       # Groq — near free
        "medium":  "gemma2-9b-it",                # Groq — cheap
        "complex": "llama-3.3-70b-versatile",     # Groq — stronger
    }
    return route_map[complexity]


# Demo router
test_queries = [
    "What is the capital of France?",
    "Explain the difference between REST and GraphQL APIs.",
    "Analyze the trade-offs in choosing a microservices vs monolith architecture.",
    "Define recursion.",
    "Write code to implement a binary search tree with insertion and deletion.",
]

print(f"\n  {'Query':<55} {'Complexity':<10} {'Routed Model'}")
print("  " + "-" * 100)
for q in test_queries:
    complexity = classify_complexity(q)
    model = smart_model_router(q)
    print(f"  {q[:53]:<55} {complexity:<10} {model}")

print("\n  COST IMPACT: Agar 70% queries simple hain to ~80% cost bachta hai!")


# =============================================================================
# SECTION 5: PROMPT COMPRESSION — filler words hatao, tokens bachao
# =============================================================================
print("\n" + "=" * 65)
print("SECTION 5: PROMPT COMPRESSION — chote prompts, kam tokens")
print("=" * 65)

# Theory doc: Verbose 50 tokens vs Compact 5 tokens


def count_approx_tokens(text: str) -> int:
    """Approximate token count — words * 1.3 (rough estimate)."""
    return max(1, int(len(text.split()) * 1.3))


VERBOSE_PROMPTS = [
    (
        "Please carefully read the following text and provide a detailed and comprehensive "
        "summary that captures all the key points mentioned in the passage below:",
        "Summarize:",
    ),
    (
        "Could you kindly help me by translating the following text from English to Hindi? "
        "Please make sure the translation is accurate and natural sounding:",
        "Translate to Hindi:",
    ),
    (
        "I would really appreciate it if you could please classify the sentiment of the "
        "following customer review as either positive, negative, or neutral:",
        "Sentiment (positive/negative/neutral):",
    ),
]

print(f"\n  {'Verbose':<65} {'Tokens':>6}  {'Compact':<35} {'Tokens':>6}  {'Savings':>8}")
print("  " + "-" * 125)
total_verbose = 0
total_compact = 0
for verbose, compact in VERBOSE_PROMPTS:
    v_tok = count_approx_tokens(verbose)
    c_tok = count_approx_tokens(compact)
    savings_pct = (v_tok - c_tok) / v_tok * 100
    total_verbose += v_tok
    total_compact += c_tok
    print(f"  {verbose[:63]:<65} {v_tok:>6}  {compact:<35} {c_tok:>6}  {savings_pct:>7.0f}%")

overall_savings = (total_verbose - total_compact) / total_verbose * 100
print(f"\n  Overall token savings: ~{overall_savings:.0f}% sirf filler words hatane se!")
print("  Tip: max_tokens bhi set karo — unnecessary long output se bachao.")


# =============================================================================
# SECTION 6: SEMANTIC CACHE (OFFLINE DEMO) — same question → no API call
# =============================================================================
print("\n" + "=" * 65)
print("SECTION 6: SEMANTIC CACHE — repeated queries ko intercept karo")
print("=" * 65)

# Theory doc: sentence_transformers optional — heavy library hai, lazy import karo


class SimpleHashCache:
    """
    Offline demo ke liye exact-match hash cache.
    Production mein: SentenceTransformer embeddings + cosine similarity use karo
    (threshold ~0.95 for near-duplicate queries).
    """

    def __init__(self):
        self._store: Dict[str, str] = {}
        self.hits = 0
        self.misses = 0

    def _key(self, query: str) -> str:
        return hashlib.sha256(query.strip().lower().encode()).hexdigest()

    def get(self, query: str) -> Optional[str]:
        k = self._key(query)
        if k in self._store:
            self.hits += 1
            return self._store[k]
        self.misses += 1
        return None

    def set(self, query: str, answer: str) -> None:
        self._store[self._key(query)] = answer

    @property
    def hit_rate(self) -> float:
        total = self.hits + self.misses
        return self.hits / total if total > 0 else 0.0


# Optional: try sentence_transformers for semantic similarity demo
_semantic_available = False
try:
    from sentence_transformers import SentenceTransformer as _ST  # noqa: F401
    _semantic_available = True
    print("  sentence_transformers available — semantic similarity bhi dikh sakti hai.")
except ImportError:
    print("  sentence_transformers nahi mila (optional) — exact-hash cache demo chalega.")
    print("  Install: pip install sentence-transformers  (for production-grade semantic cache)")

cache = SimpleHashCache()

# Simulate a cached_llm_call using our tracker_client


def cached_llm_call(query: str, feature: str = "cached") -> str:
    """
    Cache check karo pehle — hit hone par LLM call hi nahi hoti!
    Theory doc ka exact pattern: get → call if miss → set.
    """
    cached = cache.get(query)
    if cached:
        print(f"  [CACHE HIT]  '{query[:50]}' -> answer mila, API nahi laga!")
        return cached
    answer = tracker_client.call(
        messages=[{"role": "user", "content": query}],
        feature=feature,
        max_tokens=80,
    )
    cache.set(query, answer)
    print(f"  [CACHE MISS] '{query[:50]}' -> API call hua, answer store kiya.")
    return answer


# Demo — same query baar baar aaye to cache hit hoga
cache_demo_queries = [
    "What is Python?",
    "Explain async/await in Python.",
    "What is Python?",                    # duplicate — cache hit hona chahiye
    "Explain async/await in Python.",     # duplicate — cache hit
    "What is Python?",                    # phir se
    "How does garbage collection work?",  # new
]

print(f"\n  Cache demo — {len(cache_demo_queries)} queries, kuch repeated hain:")
for q in cache_demo_queries:
    cached_llm_call(q, feature="summarize")

print(f"\n  Cache stats:")
print(f"    Hits:     {cache.hits}")
print(f"    Misses:   {cache.misses}")
print(f"    Hit rate: {cache.hit_rate:.1%}")
print(f"    API calls saved: {cache.hits} (yani {cache.hits} ka paisa bacha!)")


# =============================================================================
# SECTION 7: PER-USER BUDGET TRACKER (TenantCostTracker)
# =============================================================================
print("\n" + "=" * 65)
print("SECTION 7: PER-USER BUDGET TRACKER — multi-tenant cost control")
print("=" * 65)


class TenantCostTracker:
    """
    Theory doc ka TenantCostTracker — har user ka alag budget.
    Multi-tenant apps mein zaroori: ek user doosre ka budget khali na kare.
    """

    def __init__(self):
        self.costs: Dict[str, float] = defaultdict(float)
        self.limits: Dict[str, float] = {}           # user-specific daily limits
        self.default_limit: float = 1.00             # $1/day default

    def set_limit(self, user_id: str, daily_limit_usd: float) -> None:
        self.limits[user_id] = daily_limit_usd

    def track(self, user_id: str, cost: float) -> None:
        self.costs[user_id] += cost

    def can_call(self, user_id: str) -> bool:
        limit = self.limits.get(user_id, self.default_limit)
        return self.costs[user_id] < limit

    def remaining_budget(self, user_id: str) -> float:
        limit = self.limits.get(user_id, self.default_limit)
        return max(0.0, limit - self.costs[user_id])

    def reset_daily(self) -> None:
        """Cron job se call karo — har raat midnight pe."""
        self.costs = defaultdict(float)
        print("  [CRON] Daily cost reset ho gaya — nayi raat, naya budget.")


def serve_user_query(
    user_id: str,
    query: str,
    tenant_tracker: TenantCostTracker,
    llm_client: CostTrackingClient,
) -> str:
    """
    Theory doc ka serve() function — budget check karo pehle.
    """
    if not tenant_tracker.can_call(user_id):
        remaining = tenant_tracker.remaining_budget(user_id)
        return f"[BUDGET EXCEEDED] user={user_id}, remaining=${remaining:.4f}. Kal try karo."

    answer = llm_client.call(
        messages=[{"role": "user", "content": query}],
        feature="user_query",
        max_tokens=60,
    )
    # Track cost for this user (last call ki cost)
    if llm_client.calls:
        last_cost = llm_client.calls[-1].cost
        tenant_tracker.track(user_id, last_cost)

    return answer


tenant = TenantCostTracker()
tenant.set_limit("user_premium", 5.00)   # Premium user — $5/day
tenant.set_limit("user_free",    0.10)   # Free user — 10 cents/day

print(f"\n  Simulating user queries with budget enforcement:")
print(f"  user_premium limit: $5.00/day")
print(f"  user_free    limit: $0.10/day")

test_users = [
    ("user_premium", "Explain quantum computing in simple terms."),
    ("user_free",    "What is 2+2?"),
    ("user_free",    "Tell me about AI."),
    ("user_free",    "Another query that might exceed budget."),
    ("user_premium", "Write a Python function for binary search."),
]

for uid, query in test_users:
    result = serve_user_query(uid, query, tenant, tracker_client)
    remaining = tenant.remaining_budget(uid)
    print(f"  [{uid}] query='{query[:35]}...' | result='{result[:40]}...' | remaining=${remaining:.4f}")


# =============================================================================
# SECTION 8: MONTHLY COST ESTIMATOR — theory doc ka estimate_monthly_cost
# =============================================================================
print("\n" + "=" * 65)
print("SECTION 8: MONTHLY COST ESTIMATOR — scale pe kya hoga?")
print("=" * 65)


def estimate_monthly_cost(
    users_per_day: int,
    queries_per_user: int,
    avg_input_tokens: int,
    avg_output_tokens: int,
    model: str = "gpt-4o-mini",
) -> Dict[str, float]:
    """
    Theory doc formula:
      daily_cost = (daily_input * input_price + daily_output * output_price) / 1M
      monthly_cost = daily_cost * 30
    """
    if model not in PRICING:
        model = "gpt-4o-mini"
    p = PRICING[model]

    daily_queries = users_per_day * queries_per_user
    daily_input   = daily_queries * avg_input_tokens
    daily_output  = daily_queries * avg_output_tokens

    daily_cost   = (daily_input * p["input"] + daily_output * p["output"]) / 1_000_000
    monthly_cost = daily_cost * 30

    return {
        "model": model,
        "daily_queries": daily_queries,
        "daily_input_tokens": daily_input,
        "daily_output_tokens": daily_output,
        "daily_cost_usd": daily_cost,
        "monthly_cost_usd": monthly_cost,
    }


# Theory doc ka exact scenario: 1000 users × 100 queries × 1000 tokens
scenarios = [
    {
        "label": "Theory doc example (gpt-4o)",
        "users_per_day": 1000, "queries_per_user": 100,
        "avg_input_tokens": 1000, "avg_output_tokens": 500,
        "model": "gpt-4o",
    },
    {
        "label": "Same traffic, gpt-4o-mini",
        "users_per_day": 1000, "queries_per_user": 100,
        "avg_input_tokens": 1000, "avg_output_tokens": 500,
        "model": "gpt-4o-mini",
    },
    {
        "label": "Startup scale, Groq free",
        "users_per_day": 1000, "queries_per_user": 10,
        "avg_input_tokens": 500, "avg_output_tokens": 300,
        "model": "llama-3.1-8b-instant",
    },
    {
        "label": "Growth stage, Groq 70B",
        "users_per_day": 5000, "queries_per_user": 10,
        "avg_input_tokens": 500, "avg_output_tokens": 300,
        "model": "llama-3.3-70b-versatile",
    },
]

print(f"\n  {'Scenario':<42} {'Daily $':>10} {'Monthly $':>12}")
print("  " + "-" * 68)
for s in scenarios:
    est = estimate_monthly_cost(
        s["users_per_day"], s["queries_per_user"],
        s["avg_input_tokens"], s["avg_output_tokens"],
        s["model"],
    )
    print(f"  {s['label']:<42} ${est['daily_cost_usd']:>9.2f} ${est['monthly_cost_usd']:>11.2f}")

print("\n  TAKEAWAY: gpt-4o → gpt-4o-mini se akele 90%+ savings ho sakti hai!")


# =============================================================================
# SECTION 9: ROI PER FEATURE — kaunsa feature kitna mehenga hai?
# =============================================================================
print("\n" + "=" * 65)
print("SECTION 9: ROI PER FEATURE — cost vs usage analysis")
print("=" * 65)


def roi_analysis(calls: List[CallRecord]) -> List[Dict]:
    """
    Theory doc: track karo har feature ka cost + usage.
    ROI = feature kitne users ne use kiya vs kitna cost aaya.
    """
    by_feature: Dict[str, Dict] = {}
    for c in calls:
        if c.feature not in by_feature:
            by_feature[c.feature] = {"count": 0, "total_cost": 0.0}
        by_feature[c.feature]["count"]      += 1
        by_feature[c.feature]["total_cost"] += c.cost

    result = []
    for feature, data in by_feature.items():
        cost_per_use = data["total_cost"] / data["count"] if data["count"] > 0 else 0
        result.append({
            "feature":      feature,
            "uses":         data["count"],
            "total_cost":   data["total_cost"],
            "cost_per_use": cost_per_use,
        })
    # Sort by total cost descending
    result.sort(key=lambda x: x["total_cost"], reverse=True)
    return result


roi = roi_analysis(tracker_client.calls)
print(f"\n  {'Feature':<20} {'Uses':>6} {'Total $':>10} {'$/use':>10}  {'Verdict'}")
print("  " + "-" * 70)
for r in roi:
    # Verdict: > $0.05/use is expensive, needs optimization
    verdict = "REVIEW — too costly" if r["cost_per_use"] > 0.001 else "OK"
    print(
        f"  {r['feature']:<20} {r['uses']:>6} "
        f"  ${r['total_cost']:>8.6f}   ${r['cost_per_use']:>8.6f}  {verdict}"
    )

print("\n  Theory doc insight: track karo, phir decide karo — optimize ya charge users.")


# =============================================================================
# SECTION 10: ALERT THRESHOLDS — kab alarm bajao
# =============================================================================
print("\n" + "=" * 65)
print("SECTION 10: ALERT THRESHOLDS — spike detect karo")
print("=" * 65)


@dataclass
class Alert:
    severity: str   # "CRITICAL" | "WARNING" | "INFO"
    message: str


ALERT_CONFIG = [
    # (check_fn, severity, message_template)
    (lambda total, per_q, _calls: total > 100,      "CRITICAL", "Daily cost $100 cross ho gaya — engineering team ko notify karo!"),
    (lambda total, per_q, _calls: total > 20,       "WARNING",  "Hourly cost spike — investigate karo."),
    (lambda total, per_q, _calls: per_q > 0.10,     "WARNING",  "Per-query cost $0.10 se zyada — prompts review karo."),
    (lambda total, per_q, _calls: len(_calls) > 50, "INFO",     "50+ calls — normal traffic."),
]


def check_alerts(calls: List[CallRecord]) -> List[Alert]:
    """
    Theory doc ke alert thresholds — real system mein Grafana/Datadog pe configure karo.
    """
    if not calls:
        return []
    total_cost = sum(c.cost for c in calls)
    per_query  = total_cost / len(calls)
    alerts     = []
    for check_fn, severity, msg in ALERT_CONFIG:
        if check_fn(total_cost, per_query, calls):
            alerts.append(Alert(severity=severity, message=msg))
    return alerts


alerts = check_alerts(tracker_client.calls)
if alerts:
    print(f"\n  {len(alerts)} alert(s) triggered:")
    for a in alerts:
        print(f"  [{a.severity}] {a.message}")
else:
    print("\n  Koi alert nahi — cost normal hai.")

# Manually demo an alert (simulate high cost)
print("\n  Simulating high-cost scenario alerts:")
fake_high_cost_calls = [
    CallRecord("gpt-4o", 5000, 2000, 0.0325, time.time(), "heavy_feature")
    for _ in range(10)
]
high_alerts = check_alerts(fake_high_cost_calls)
for a in high_alerts:
    print(f"  [{a.severity}] {a.message}")


# =============================================================================
# SECTION 11: DAILY COST REPORT — theory doc ka daily_report()
# =============================================================================
print("\n" + "=" * 65)
print("SECTION 11: DAILY COST REPORT — dashboard summary")
print("=" * 65)


def daily_report(calls: List[CallRecord]) -> Dict[str, Any]:
    """
    Theory doc ka daily_report() — aggregate stats nikalo.
    Real system mein: Grafana / Datadog pe visualize karo.
    """
    if not calls:
        return {"error": "Koi calls nahi aaj ke liye."}

    total_cost  = sum(c.cost for c in calls)
    by_model    = defaultdict(float)
    by_feature  = defaultdict(float)
    costs_list  = [c.cost for c in calls]

    for c in calls:
        by_model[c.model]     += c.cost
        by_feature[c.feature] += c.cost

    # p99 manually (no numpy required)
    sorted_costs = sorted(costs_list)
    p99_idx      = min(int(math.ceil(0.99 * len(sorted_costs))) - 1, len(sorted_costs) - 1)
    p99_cost     = sorted_costs[p99_idx]

    return {
        "total_calls":     len(calls),
        "total_cost_usd":  total_cost,
        "avg_cost_usd":    total_cost / len(calls),
        "p99_cost_usd":    p99_cost,
        "by_model":        dict(by_model),
        "by_feature":      dict(by_feature),
        "most_expensive_model": max(by_model, key=by_model.get) if by_model else "N/A",
    }


report = daily_report(tracker_client.calls)
print(f"\n  Daily Report:")
print(f"    Total calls:          {report['total_calls']}")
print(f"    Total cost:           ${report['total_cost_usd']:.6f}")
print(f"    Avg cost/call:        ${report['avg_cost_usd']:.6f}")
print(f"    P99 cost/call:        ${report['p99_cost_usd']:.6f}")
print(f"    Most expensive model: {report['most_expensive_model']}")
print(f"    Cost by feature:")
for feat, cost in report["by_feature"].items():
    print(f"      {feat:<20}: ${cost:.6f}")


# =============================================================================
# SECTION 12: LIVE GROQ CALL (only if key present)
# =============================================================================
print("\n" + "=" * 65)
print("SECTION 12: LIVE GROQ CALL — real token count dekho")
print("=" * 65)

if LIVE_MODE:
    print("\n  Live Groq call kar raha hai (llama-3.1-8b-instant)...")
    live_client = CostTrackingClient(openai_client=get_client(), default_model="llama-3.1-8b-instant")
    response_text = live_client.call(
        messages=[
            {"role": "system", "content": "Answer in 1 sentence."},
            {"role": "user",   "content": "What is prompt caching and how does it save cost?"},
        ],
        max_tokens=80,
        feature="live_demo",
    )
    live_summary = live_client.summary()
    print(f"  Response: {response_text[:120]}")
    print(f"  Real tokens used — input: {live_client.calls[-1].input_tokens}, output: {live_client.calls[-1].output_tokens}")
    print(f"  Actual cost: ${live_client.calls[-1].cost:.8f}")
    print(f"\n  GROQ FREE TIER pe yeh nahi laga — amazing!")
else:
    print("\n  [SKIP] GROQ_API_KEY nahi hai — live call skip kar raha hai.")
    print("  Set GROQ_API_KEY=gsk_... to see real token counts and costs.")


# =============================================================================
# FINAL SUMMARY — key takeaways
# =============================================================================
print("\n" + "=" * 65)
print("  COST OPTIMIZATION — KEY TAKEAWAYS (Theory se)")
print("=" * 65)

takeaways = [
    "Har LLM call ka cost track karo — CostTrackingClient use karo",
    "Smart routing: simple query -> cheap model (10-100x savings)",
    "Prompt compress karo — filler words hatao, tokens bachao",
    "Semantic cache: same question -> no API call (max savings)",
    "Per-user budget: TenantCostTracker se limits enforce karo",
    "Anthropic prompt caching: 90% discount on repeated system prompts",
    "Batch API: 50% off, 24h delay OK ho to use karo",
    "max_tokens set karo — unnecessary long output se bachao",
    "ROI track karo: cost per use vs feature value",
    "Alerts set karo: daily $100, per-query $0.10 thresholds",
]

for i, t in enumerate(takeaways, 1):
    print(f"  {i:2}. {t}")

print("\n" + "=" * 65)
print("  LAB COMPLETE — EXIT 0")
print("=" * 65)

sys.exit(0)
