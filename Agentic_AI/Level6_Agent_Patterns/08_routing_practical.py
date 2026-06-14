"""
Level 6.8 — Routing & Classification (PRACTICAL, Hinglish)
==========================================================

KYA SEEKHENGE:
  Routing = query ko sahi handler (agent / model / tool / collection) tak bhejna.
  6 router patterns, basic se advanced:
    1. Rule-based router   — keyword/regex, FREE + instant
    2. Semantic router     — embedding similarity se intent match (offline hash-embed fallback)
    3. LLM router          — LLM se classify (sabse accurate, thoda mehenga)
    4. Complexity router   — query complexity ke hisaab se cheap vs costly model
    5. Hybrid router        — rules -> semantic -> LLM (production best-practice, 80/20)
    6. Confidence + fallback + RoutingTracker metrics

KAISE CHALANA (repo root se):
    uv run Agentic_AI/Level6_Agent_Patterns/08_routing_practical.py
  Bina kisi API key ke chalta hai (rule/semantic offline; LLM router gracefully skip).

CONNECT: ReAct (04) tools pick karta hai, Supervisor (07) khud ek router HAI,
  aur RAG query-transformation (Level5/08) collection-routing karta hai — sab routing ke roop.
"""

import os
import re
import math
import hashlib
from dotenv import load_dotenv

load_dotenv(override=True)


# ===========================================================================
# get_client — default groq free. NOTE `or "placeholder"`: OpenAI() None key
# par CONSTRUCTION time hi crash karta hai, isliye placeholder rakhte hain.
# ===========================================================================
def get_client(provider: str = "groq"):
    from openai import OpenAI
    if provider == "groq":
        return OpenAI(base_url="https://api.groq.com/openai/v1",
                      api_key=os.getenv("GROQ_API_KEY") or "placeholder"), "llama-3.3-70b-versatile"
    raise ValueError(provider)


# LIVE_MODE: sirf tab true jab asli GROQ key ho. Warna LLM router skip -> rule fallback.
LIVE_MODE = bool(os.getenv("GROQ_API_KEY"))


# ===========================================================================
# PATTERN 1 — Rule-Based Router (sabse sasta: $0, <1ms)
# Keyword/regex match. Clear keywords + narrow domain ke liye best.
# ===========================================================================
def rule_route(query: str) -> str:
    """Keyword-based routing. Zero LLM call — fast aur free."""
    q = query.lower()
    if any(w in q for w in ["price", "cost", "billing", "invoice", "refund", "subscription"]):
        return "billing_agent"
    if any(w in q for w in ["bug", "error", "crash", "broken", "not working", "500"]):
        return "tech_support_agent"
    if any(w in q for w in ["cancel", "downgrade", "leave"]):
        return "retention_agent"
    return "general_agent"   # <-- hamesha ek fallback intent rakho


# ===========================================================================
# PATTERN 2 — Semantic Router (embedding similarity)
# Theory mein SentenceTransformer use hota hai. Yahan OFFLINE chalane ke liye
# ek deterministic hash-based embedder use karte hain (koi model download nahi).
# Asli production mein BAAI/bge-small-en-v1.5 jaisa model use karo.
# ===========================================================================
def _hash_embed(text: str, dim: int = 64) -> list:
    """Deterministic bag-of-words hashing vectorizer. Pure-python, no deps.
    Har token ko ek bucket mein hash karke count badhate hain, phir L2-normalize."""
    vec = [0.0] * dim
    for tok in re.findall(r"[a-z0-9]+", text.lower()):
        h = int(hashlib.md5(tok.encode()).hexdigest(), 16)
        vec[h % dim] += 1.0
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]


def _cosine(a: list, b: list) -> float:
    return sum(x * y for x, y in zip(a, b))   # already L2-normalized


# Intents define karo example queries ke saath (theory ka INTENT_EXAMPLES pattern)
INTENT_EXAMPLES = {
    "billing":      ["What's my invoice last month?", "How much is the pro plan?", "I want a refund"],
    "tech_support": ["The app crashes on submit", "I'm getting a 500 error", "Login is broken"],
    "general":      ["How do I use this feature?", "Where is the X menu?", "Tell me about the product"],
}

# Pre-compute intent CENTROIDS (har intent ke examples ka average vector)
_INTENT_CENTROIDS = {}
for _intent, _examples in INTENT_EXAMPLES.items():
    _embs = [_hash_embed(e) for e in _examples]
    _dim = len(_embs[0])
    _centroid = [sum(e[i] for e in _embs) / len(_embs) for i in range(_dim)]
    _norm = math.sqrt(sum(v * v for v in _centroid)) or 1.0
    _INTENT_CENTROIDS[_intent] = [v / _norm for v in _centroid]


def semantic_route(query: str):
    """Return (intent, confidence). Paraphrasing/multilingual handle karta hai, no LLM call."""
    q_emb = _hash_embed(query)
    scores = {intent: _cosine(q_emb, cen) for intent, cen in _INTENT_CENTROIDS.items()}
    best = max(scores, key=scores.get)
    return best, scores[best]


# ===========================================================================
# PATTERN 3 — LLM-Based Router (sabse accurate, ~$0.0001 + 100-300ms)
# Cheap model (gpt-4o-mini / groq) se intent classify karte hain.
# No key -> gracefully rule_route pe fall back.
# ===========================================================================
ROUTER_SYSTEM = """You are a router. Classify the user query into ONE category:
- billing: pricing, invoices, refunds, subscriptions
- tech_support: bugs, errors, things not working
- product_info: how features work, documentation
- general: anything else
Respond with ONLY the category name. No explanation."""


def llm_route(query: str) -> str:
    """LLM se classify. Temperature 0 + max_tokens chhota (sirf label chahiye)."""
    if not LIVE_MODE:
        # No key -> sasta fallback. Production mein yahan asli LLM call hoti.
        print("    [llm_route] GROQ_API_KEY missing -> rule_route fallback")
        return rule_route(query).replace("_agent", "")
    client, model = get_client("groq")
    resp = client.chat.completions.create(
        model=model, temperature=0, max_tokens=10,
        messages=[{"role": "system", "content": ROUTER_SYSTEM},
                  {"role": "user", "content": query}],
    )
    return resp.choices[0].message.content.strip().lower()


# ===========================================================================
# PATTERN 4 — Model-Complexity Router (cost optimization)
# Query complexity classify karke cheap/medium/costly model pick karo.
# 70% queries simple -> ~80% model-cost bachat.
# ===========================================================================
MODEL_MAP = {
    "simple":  ("gpt-4o-mini",    "$0.15/1M"),
    "medium":  ("gpt-4o",          "$2.50/1M"),
    "complex": ("claude-opus-4",   "$15/1M"),
}


def _heuristic_complexity(query: str) -> str:
    """Offline heuristic (no LLM): length + reasoning-keywords se complexity guess."""
    q = query.lower()
    if any(w in q for w in ["why", "analyze", "compare", "design", "prove", "optimize", "trade-off"]) or len(query) > 200:
        return "complex"
    if any(w in q for w in ["how", "explain", "steps", "calculate"]) or len(query) > 80:
        return "medium"
    return "simple"


def complexity_route(query: str) -> tuple:
    """Return (model, complexity). LIVE_MODE mein LLM classify; warna heuristic."""
    complexity = _heuristic_complexity(query)   # offline-safe default
    model, price = MODEL_MAP.get(complexity, MODEL_MAP["simple"])
    return model, complexity, price


# ===========================================================================
# PATTERN 5 — Hybrid Router (PRODUCTION best-practice: 80/20)
#   Step 1: rules (free)  -> Step 2: semantic (cheap) -> Step 3: LLM (accurate)
# Avg cost ~$0.000006/query. Yahi real-world mein use hota hai.
# ===========================================================================
RULE_PATTERNS = {
    r"\$|\bcost\b|\bprice\b|\bbilling\b|\brefund\b": "billing",
    r"\berror\b|\bbug\b|\bcrash\b|\bbroken\b": "tech_support",
}
CONFIDENCE_THRESHOLD = 0.45   # apne eval-set pe calibrate karo


def hybrid_route(query: str) -> tuple:
    """Return (intent, method). 3-tier: rule -> semantic -> llm."""
    # Tier 1: rule (0 cost)
    for pattern, intent in RULE_PATTERNS.items():
        if re.search(pattern, query.lower()):
            return intent, "rule"
    # Tier 2: semantic (cheap)
    intent, conf = semantic_route(query)
    if conf > CONFIDENCE_THRESHOLD:
        return intent, f"semantic(conf={conf:.2f})"
    # Tier 3: LLM fallback (accurate) — low confidence queries
    return llm_route(query), "llm"


# ===========================================================================
# PATTERN 6 — Confidence + Fallback + RoutingTracker (metrics)
# Har routing decision LOG karo — accuracy/fallback-rate baad mein chahiye.
# ===========================================================================
class RoutingTracker:
    def __init__(self):
        self.decisions = []

    def log(self, query, route, confidence, outcome):
        self.decisions.append({"query": query, "route": route,
                               "confidence": confidence, "outcome": outcome})

    def routing_accuracy(self) -> float:
        if not self.decisions:
            return 0.0
        ok = sum(1 for d in self.decisions if d["outcome"] == "success")
        return ok / len(self.decisions)

    def fallback_rate(self) -> float:
        if not self.decisions:
            return 0.0
        fb = sum(1 for d in self.decisions if d["route"] in ("general", "general_agent"))
        return fb / len(self.decisions)


# ===========================================================================
# SELF-DEMO — `uv run <file>` se sab patterns offline chalte hain, exit 0.
# ===========================================================================
SAMPLE_QUERIES = [
    "My credit card was charged twice this month!",
    "The login page keeps showing a 500 error",
    "How do I export my data to CSV?",
    "Why is my vector search returning irrelevant chunks and how do I fix the reranking?",
    "I want to cancel my subscription",
]


def _demo():
    print("=" * 70)
    print("ROUTING & CLASSIFICATION — 6 patterns (offline demo)")
    print("LIVE_MODE =", LIVE_MODE, "(GROQ key present?)")
    print("=" * 70)

    print("\n--- 1. RULE-BASED ROUTER (keyword, free) ---")
    for q in SAMPLE_QUERIES:
        print(f"  {rule_route(q):18s} <- {q[:50]}")

    print("\n--- 2. SEMANTIC ROUTER (offline hash-embed, with confidence) ---")
    for q in SAMPLE_QUERIES:
        intent, conf = semantic_route(q)
        print(f"  {intent:10s} conf={conf:.2f}  <- {q[:50]}")

    print("\n--- 3. LLM ROUTER (groq if key; else rule fallback) ---")
    for q in SAMPLE_QUERIES[:2]:
        print(f"  {llm_route(q):14s} <- {q[:50]}")

    print("\n--- 4. COMPLEXITY ROUTER (cost optimization) ---")
    for q in SAMPLE_QUERIES:
        model, cx, price = complexity_route(q)
        print(f"  {cx:8s} -> {model:16s} ({price})  <- {q[:45]}")

    print("\n--- 5. HYBRID ROUTER (rule -> semantic -> LLM) ---")
    tracker = RoutingTracker()
    for q in SAMPLE_QUERIES:
        intent, method = hybrid_route(q)
        tracker.log(q, intent, 1.0, "success")
        print(f"  {intent:14s} via {method:22s} <- {q[:45]}")

    print("\n--- 6. ROUTING METRICS ---")
    print(f"  routing_accuracy = {tracker.routing_accuracy():.0%}")
    print(f"  fallback_rate    = {tracker.fallback_rate():.0%}")

    print("\nTakeaway: Hybrid (rules->semantic->LLM) = best cost/accuracy."
          " Hamesha ek 'general' fallback rakho aur har decision LOG karo.")
    print("Done. (exit 0)")


if __name__ == "__main__":
    _demo()
