"""
Level 8.10 — Cost Optimization Advanced: Practical Lab
=======================================================

KYA SEEKHENGE (What we will learn):
  1. Cost Tracker — har LLM call ka paisa count karo
  2. Model Routing — simple query => cheap model, hard query => expensive model
  3. Semantic Caching — similar queries ke liye LLM dobara mat call karo
  4. Context / History Trimming — purana history kat ke token bachao
  5. Prompt Compression — manual techniques se prompt chhota karo
  6. Output Length Capping — max_tokens tight rakho, output tokens 2-4x mehenga hota hai
  7. Provider Cascade — sabse saste provider se start karo, zaroorat ho tab hi mehenga use karo
  8. Batching — ek saath kai documents embed karo
  9. Per-Tenant Quota — ek bura tenant poora budget na jala de

KAISE CHALANA (How to run):
  uv run /Users/youngmanindia/Documents/PythonRevision/Agentic_AI/Level8_Production_LLMOps/10_cost_optimization_advanced_practical.py

  Keys ke bina (offline mode): sab demos chalenge, live LLM calls skip honge — EXIT 0
  Key ke saath: GROQ_API_KEY set karo, Section 2 live call bhi karega

THEORY REFERENCE:
  Level8_Production_LLMOps/10_cost_optimization_advanced.md
"""

import os
import math
import time
import asyncio
import hashlib
from dataclasses import dataclass, field
from typing import Optional

# ─── GROQ_API_KEY check ────────────────────────────────────────────────────────
# Agar key nahi hai to MOCK_MODE = True — sab gracefully degrade hoga
GROQ_API_KEY = os.getenv("GROQ_API_KEY") or "placeholder"
LIVE_MODE = GROQ_API_KEY != "placeholder"

if not LIVE_MODE:
    print("[INFO] GROQ_API_KEY not set — MOCK MODE chalega, EXIT 0 guarantee hai.")
print()


# ─── get_client() — OpenAI-compatible Groq client ─────────────────────────────
# RULE: api_key kabhi None nahi dena — OpenAI() crash karta hai None pe
def get_client():
    """
    Groq ka free tier use karo by default.
    GROQ_API_KEY nahi hai to 'placeholder' string pass karo — import tak to chalega,
    actual call pe HTTPError aayega, jo hum MOCK_MODE mein skip karte hain.
    """
    try:
        from openai import OpenAI  # Groq OpenAI-compatible API expose karta hai
        client = OpenAI(
            base_url="https://api.groq.com/openai/v1",
            api_key=GROQ_API_KEY,  # kabhi None nahi — "placeholder" fallback hai
        )
        return client
    except ImportError:
        return None


print("=" * 65)
print("COST OPTIMIZATION ADVANCED — PRACTICAL LAB")
print("=" * 65)

# ─────────────────────────────────────────────────────────────────────────────
# SECTION 1: Cost Tracker — Pehle MEASURE karo, phir optimize
# THEORY: "Measure first. Optimize specific costs, not vague feelings."
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 65)
print("SECTION 1: Cost Tracker — Token Counting + Cost Calculation")
print("=" * 65)

# 2026 ke real pricing (theory doc se liya)
# Format: model_name -> (cost_per_input_1M, cost_per_output_1M)
PRICING_TABLE = {
    "gpt-4o":              (2.50,  10.00),
    "gpt-4o-mini":         (0.15,   0.60),
    "claude-sonnet":       (3.00,  15.00),
    "claude-haiku":        (0.25,   1.25),
    "claude-opus":        (15.00,  75.00),
    "groq-llama3-70b":     (0.59,   0.79),
    "groq-llama3-8b":      (0.05,   0.10),   # approx free tier
    "deepseek-v3":         (0.27,   1.10),
}

print("\n  2026 Pricing Table (theory doc se):")
print(f"  {'Model':<22} {'Input $/1M':>12} {'Output $/1M':>12}")
print("  " + "-" * 48)
for model, (inp, out) in PRICING_TABLE.items():
    print(f"  {model:<22} {inp:>12.2f} {out:>12.2f}")


@dataclass
class CallRecord:
    """Ek LLM call ka record — cost calculate karne ke liye."""
    model: str
    prompt_tokens: int
    completion_tokens: int
    tenant_id: str = "default"

    @property
    def cost_usd(self) -> float:
        """
        Cost formula:
          (input_tokens / 1_000_000) * input_price
        + (output_tokens / 1_000_000) * output_price
        Output tokens 2-4x mehenga hota hai — isliye max_tokens tight rakho!
        """
        if self.model not in PRICING_TABLE:
            return 0.0
        inp_price, out_price = PRICING_TABLE[self.model]
        return (
            (self.prompt_tokens / 1_000_000) * inp_price
            + (self.completion_tokens / 1_000_000) * out_price
        )


class CostTracker:
    """
    In-memory cost tracker (production mein Redis use karo).
    Theory: per-model, per-tenant, daily totals track karo.
    """

    def __init__(self, daily_budget_usd: float = 10.0):
        self.daily_budget = daily_budget_usd
        self.records: list[CallRecord] = []
        self._daily_cost: float = 0.0
        self._tenant_costs: dict[str, float] = {}

    def record(self, rec: CallRecord) -> dict:
        """
        Call record karo.
        Alert return karo agar daily budget exceed ho.
        """
        self.records.append(rec)
        self._daily_cost += rec.cost_usd
        self._tenant_costs[rec.tenant_id] = (
            self._tenant_costs.get(rec.tenant_id, 0.0) + rec.cost_usd
        )
        result = {
            "cost_this_call": rec.cost_usd,
            "daily_total":    self._daily_cost,
            "budget_alert":   self._daily_cost > self.daily_budget,
        }
        return result

    def summary(self) -> dict:
        by_model: dict[str, float] = {}
        for r in self.records:
            by_model[r.model] = by_model.get(r.model, 0.0) + r.cost_usd
        return {
            "total_calls":   len(self.records),
            "total_cost":    self._daily_cost,
            "by_model":      by_model,
            "by_tenant":     dict(self._tenant_costs),
        }


tracker = CostTracker(daily_budget_usd=1.0)

# Kuch fake calls log karte hain — jaise production mein kuch requests aayi hon
fake_calls = [
    CallRecord("gpt-4o",          prompt_tokens=800,  completion_tokens=200, tenant_id="acme"),
    CallRecord("gpt-4o-mini",     prompt_tokens=500,  completion_tokens=150, tenant_id="acme"),
    CallRecord("groq-llama3-70b", prompt_tokens=1200, completion_tokens=300, tenant_id="beta"),
    CallRecord("claude-haiku",    prompt_tokens=400,  completion_tokens=100, tenant_id="beta"),
    CallRecord("gpt-4o",          prompt_tokens=2000, completion_tokens=500, tenant_id="acme"),
]

print("\n  Simulated call log:")
for call in fake_calls:
    info = tracker.record(call)
    alert_str = " *** BUDGET ALERT ***" if info["budget_alert"] else ""
    print(
        f"  {call.model:<22}  in={call.prompt_tokens:>5}  out={call.completion_tokens:>4}"
        f"  cost=${info['cost_this_call']:.6f}  daily=${info['daily_total']:.5f}{alert_str}"
    )

summ = tracker.summary()
print(f"\n  --- Tracker Summary ---")
print(f"  Total calls : {summ['total_calls']}")
print(f"  Total cost  : ${summ['total_cost']:.5f}")
print(f"  By model    : { {k: f'${v:.6f}' for k, v in summ['by_model'].items()} }")
print(f"  By tenant   : { {k: f'${v:.6f}' for k, v in summ['by_tenant'].items()} }")
print("\n  INTERVIEW TIP: Output tokens 2-4x mehenga — isliye max_tokens cap ZAROOR lagao.")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 2: Model Routing — Cheap Model for Simple, Expensive for Hard
# THEORY: "80% queries simple hoti hain — wahan GPT-4o waste hai"
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 65)
print("SECTION 2: Model Routing — Query Complexity ke basis pe Route karo")
print("=" * 65)

# Cost tiers — theory doc se exactly liya
COST_TIERS = {
    "tier_0": {"model": "groq-llama3-8b",   "cost_in": 0.05 / 1_000_000,  "cost_out": 0.10 / 1_000_000},
    "tier_1": {"model": "gpt-4o-mini",      "cost_in": 0.15 / 1_000_000,  "cost_out": 0.60 / 1_000_000},
    "tier_2": {"model": "gpt-4o",           "cost_in": 2.50 / 1_000_000,  "cost_out": 10.0 / 1_000_000},
    "tier_3": {"model": "claude-opus",      "cost_in": 15.0 / 1_000_000,  "cost_out": 75.0 / 1_000_000},
}

ROUTING_CODE_DEMO = '''
# Router ka kaam — cheapest model se classify karo
async def route_by_complexity(query: str) -> str:
    classification = await client.chat.completions.create(
        model="groq-llama3-8b",       # sabse sasta model classify kare
        messages=[{
            "role": "user",
            "content": f"Classify: simple/medium/complex/expert. Query: {query}. One word."
        }],
        max_tokens=5,                  # classification ke liye sirf 5 tokens!
        temperature=0,
    )
    level = classification.choices[0].message.content.strip().lower()
    return {"simple": "tier_0", "medium": "tier_1",
            "complex": "tier_2", "expert": "tier_3"}.get(level, "tier_0")
'''
print(ROUTING_CODE_DEMO)

# Offline heuristic router — words aur length se complexity estimate karo
SIMPLE_WORDS = {"hi", "hello", "thanks", "ok", "yes", "no", "what", "who", "when", "where"}
COMPLEX_WORDS = {"architect", "tradeoff", "design", "system", "algorithm", "optimize",
                 "implement", "compare", "evaluate", "reasoning"}


def heuristic_router(query: str) -> str:
    """
    Offline complexity router — live key nahi hai to yeh use karo.
    Production mein: cheapest model se classify karo (1-2 tokens).
    """
    words = set(query.lower().split())
    if len(query) < 30 and words & SIMPLE_WORDS:
        return "tier_0"   # simple greeting / yes-no
    elif len(query) < 80 and not (words & COMPLEX_WORDS):
        return "tier_1"   # medium question
    elif words & COMPLEX_WORDS or len(query) > 200:
        return "tier_2"   # hard technical
    else:
        return "tier_1"   # default: tier_1


def route_and_estimate(query: str) -> dict:
    tier_key = heuristic_router(query)
    tier = COST_TIERS[tier_key]
    # Estimate: assume 100 token input, 200 token output
    est_cost = 100 * tier["cost_in"] + 200 * tier["cost_out"]
    return {
        "query":     query[:50],
        "tier":      tier_key,
        "model":     tier["model"],
        "est_cost":  est_cost,
    }


# Agar LIVE_MODE hai — actual Groq call bhi karo
def live_groq_call(query: str, model: str = "llama3-8b-8192") -> Optional[str]:
    """
    Groq free tier call — key hai to karo, nahi to gracefully skip.
    Groq model IDs alag hain: 'llama3-8b-8192', 'llama3-70b-8192'
    """
    if not LIVE_MODE:
        return None
    client = get_client()
    if client is None:
        return None
    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": query}],
            max_tokens=50,
            temperature=0,
        )
        return resp.choices[0].message.content.strip()
    except Exception as exc:
        print(f"  [LIVE CALL ERROR] {exc}")
        return None


test_queries = [
    "Hi, how are you?",
    "What is Python used for?",
    "Design a distributed semantic cache with vector similarity search for production LLM infra.",
    "Compare tradeoffs between quantization strategies AWQ vs FP8 for self-hosted LLM serving.",
]

print("  Query routing demo:")
print(f"  {'Query (trimmed)':<52} {'Tier':<8} {'Model':<20} {'Est Cost':>12}")
print("  " + "-" * 96)

for q in test_queries:
    info = route_and_estimate(q)
    print(f"  {info['query']:<52} {info['tier']:<8} {info['model']:<20} ${info['est_cost']:>11.8f}")

if LIVE_MODE:
    print("\n  [LIVE] Groq se ek simple call kar rahe hain...")
    answer = live_groq_call("What is 2 + 2? Answer in one word.", model="llama3-8b-8192")
    if answer:
        print(f"  Groq response: {answer}")
        tracker.record(CallRecord("groq-llama3-8b", 20, 5))
else:
    print("\n  [MOCK] Live Groq call skip — GROQ_API_KEY nahi hai.")

print("\n  INTERVIEW TIP: 60-70% queries sabse saste tier mein serve ho sakti hain.")
print("  Avg 70% cost savings milta hai agar 60% queries 'simple' hain.")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 3: Semantic Caching — Similar Queries Ko Re-Run Mat Karo
# THEORY: "Cache hit rate 60-80% customer support mein, 20-40% code assistant mein"
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 65)
print("SECTION 3: Semantic Caching — Similar Queries Cache Se Serve Karo")
print("=" * 65)

print("""
  Full semantic cache = embeddings + cosine similarity + Redis.
  Heavy optional deps: sentence-transformers, chromadb, redis.
  In-memory toy implementation neeche hai — concept same hai.

  Production flow:
    1. Query aai -> embed karo (text-embed-3-small, voyage-3, etc.)
    2. Cache mein similar embedding dhundo (cosine similarity)
    3. similarity > threshold (0.95) -> cache hit, LLM call skip
    4. Miss -> LLM call karo, response cache mein daal do
    5. Threshold tuning: 0.99=strict, 0.95=balanced, 0.90=aggressive
""")

# Lazy import — agar sentence-transformers install nahi hai to fallback
_sentence_transformer = None
try:
    from sentence_transformers import SentenceTransformer  # type: ignore
    _sentence_transformer = SentenceTransformer("all-MiniLM-L6-v2")
    print("  [INFO] sentence-transformers mila — real embeddings use honge.")
except ImportError:
    print("  [INFO] sentence-transformers nahi mila — fake hash embeddings use honge.")


def _fake_embed(text: str) -> list[float]:
    """
    Jab sentence-transformers nahi hai tab fallback.
    Real embedding jaisi nahi hai — sirf structure demonstrate karne ke liye.
    Character frequency vector: ASCII 32-127 range.
    """
    vec = [0.0] * 96
    for ch in text.lower():
        idx = ord(ch) - 32
        if 0 <= idx < 96:
            vec[idx] += 1.0
    # Normalize
    norm = math.sqrt(sum(x * x for x in vec)) or 1.0
    return [x / norm for x in vec]


def embed_text(text: str) -> list[float]:
    if _sentence_transformer is not None:
        return _sentence_transformer.encode(text).tolist()
    return _fake_embed(text)


def cosine_sim(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


@dataclass
class SemanticCache:
    """
    In-memory semantic cache — production mein Redis + pgvector / ChromaDB use karo.
    Theory: threshold 0.95 balanced hai zyaadatar production ke liye.
    """
    threshold: float = 0.95
    _store: list = field(default_factory=list)  # list of (embedding, response, query)
    hits: int = 0
    misses: int = 0

    def get(self, query: str) -> Optional[str]:
        q_emb = embed_text(query)
        for stored_emb, stored_resp, stored_q in self._store:
            sim = cosine_sim(q_emb, stored_emb)
            if sim >= self.threshold:
                self.hits += 1
                print(f"    [CACHE HIT]  sim={sim:.3f} >= {self.threshold}  cached_q='{stored_q[:40]}'")
                return stored_resp
        self.misses += 1
        return None

    def put(self, query: str, response: str):
        q_emb = embed_text(query)
        self._store.append((q_emb, response, query))

    def hit_rate(self) -> float:
        total = self.hits + self.misses
        return self.hits / total if total > 0 else 0.0


cache = SemanticCache(threshold=0.92)

# Kuch queries cache mein daal do
seed_data = [
    ("What is Python?",               "Python ek high-level programming language hai."),
    ("Explain machine learning",       "ML algorithms data se patterns seekhte hain."),
    ("How does semantic caching work?", "Query ko embed karo, similar cached responses dhundo."),
]
for q, r in seed_data:
    cache.put(q, r)

print("  Semantic cache demo (threshold=0.92):")
test_queries_cache = [
    "What is Python programming language?",   # should hit (similar to seed[0])
    "Tell me about machine learning basics",   # should hit (similar to seed[1])
    "How do LLM APIs stream tokens?",          # should miss
    "What is Python?",                         # exact match — should hit
    "Explain deep reinforcement learning",     # maybe hit or miss depending on embedding
]

for tq in test_queries_cache:
    print(f"\n  Query: '{tq}'")
    cached = cache.get(tq)
    if cached:
        print(f"    Response (from cache): {cached}")
    else:
        # LLM call karni padti — here we fake it
        fake_resp = f"[LLM response for: {tq[:40]}]"
        cache.put(tq, fake_resp)
        print(f"    [CACHE MISS] LLM call kiya. Response cached.")

print(f"\n  Cache stats: hits={cache.hits}, misses={cache.misses}, hit_rate={cache.hit_rate():.1%}")
print("\n  INTERVIEW TIP:")
print("  Customer support mein 60-80% cache hit possible hai (repetitive questions).")
print("  Code assistant mein 20-40% (varied queries).")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 4: Context / History Trimming — Token Budget Mein Rakho
# THEORY: "Don't send full history every turn — trim or summarize"
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 65)
print("SECTION 4: Context / History Trimming — Token Waste Rokna")
print("=" * 65)

print("""
  Problem: Har turn pe poori history bhejne se tokens badhte hain.
  Example: 20 message history => 3000 tokens => $0.0075 per call (gpt-4o)
           1000 calls/day => $7.50/day sirf history se!

  Solutions:
    A. Last N messages rakhna (simple, fast)
    B. Summary-based trimming (better for very long histories)
""")

# History trimming — theory doc ka trim_history() reimplemented
def count_tokens_approx(text: str) -> int:
    """
    Approximate token count — 4 characters ~= 1 token (rough heuristic).
    Production mein tiktoken use karo: tiktoken.encoding_for_model("gpt-4o-mini")
    Tiktoken heavy hai isliye yahan lazy load karenge.
    """
    try:
        import tiktoken  # type: ignore  # optional heavy dep
        enc = tiktoken.encoding_for_model("gpt-4o-mini")
        return len(enc.encode(text))
    except ImportError:
        return max(1, len(text) // 4)


def trim_history(
    history: list[dict],
    max_tokens: int = 2000,
) -> list[dict]:
    """
    Theory doc se: system message hamesha rakhna, oldest messages pehle katna.
    Recent context zyaada useful hota hai.
    """
    system_msgs = [m for m in history if m.get("role") == "system"]
    other_msgs  = [m for m in history if m.get("role") != "system"]

    # System tokens count karo
    sys_tokens = sum(count_tokens_approx(m.get("content", "")) for m in system_msgs)
    budget = max_tokens - sys_tokens

    # Peeche se messages lo jab tak budget mein hain
    trimmed: list[dict] = []
    used = 0
    for msg in reversed(other_msgs):
        t = count_tokens_approx(msg.get("content", ""))
        if used + t > budget:
            break
        trimmed.insert(0, msg)
        used += t

    kept = len(trimmed)
    cut  = len(other_msgs) - kept
    return system_msgs + trimmed, kept, cut, used + sys_tokens


# Demo conversation history
long_history = [
    {"role": "system",    "content": "Tum ek helpful AI ho. Concise jawab do."},
    {"role": "user",      "content": "Python kya hai?"},
    {"role": "assistant", "content": "Python ek high-level interpreted language hai."},
    {"role": "user",      "content": "Iske kya use cases hain?"},
    {"role": "assistant", "content": "Web dev, ML, data science, scripting, automation."},
    {"role": "user",      "content": "Django vs FastAPI?"},
    {"role": "assistant", "content": "Django batteries-included hai, FastAPI async/fast hai."},
    {"role": "user",      "content": "Kaunsa seekhna chahiye pehle?"},
    {"role": "assistant", "content": "Beginner ke liye Django, production API ke liye FastAPI."},
    {"role": "user",      "content": "Async programming kya hoti hai?"},
    {"role": "assistant", "content": "asyncio + await se concurrent tasks bina threads ke."},
    {"role": "user",      "content": "Ab mujhe cost optimization batao LLM ke liye."},  # latest
]

print(f"  Original history: {len(long_history)} messages")
orig_tokens = sum(count_tokens_approx(m.get("content", "")) for m in long_history)
print(f"  Approximate tokens: ~{orig_tokens}")

trimmed_hist, kept, cut, final_tokens = trim_history(long_history, max_tokens=300)
print(f"  After trimming (max_tokens=300): {len(trimmed_hist)} messages kept ({kept} non-system), {cut} cut")
print(f"  Final token estimate: ~{final_tokens}")

print("\n  Trimmed history:")
for m in trimmed_hist:
    role = m["role"].upper()
    content = m["content"][:60]
    print(f"    [{role}] {content}")

savings_pct = (1 - final_tokens / orig_tokens) * 100 if orig_tokens > 0 else 0
print(f"\n  Token savings: ~{savings_pct:.0f}%")
print("\n  INTERVIEW TIP: Summary-based trimming aur bhi acha hai —")
print("  older messages ko summarize karke ek system message bana do.")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 5: Prompt Compression — Manual Techniques
# THEORY: LLMLingua jaise tools 2-5x compression dete hain, <5% quality loss
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 65)
print("SECTION 5: Prompt Compression — Manual + Heuristic Techniques")
print("=" * 65)

print("""
  Heavy lib (LLMLingua, Microsoft) lazy import:
""")
# Lazy import — llmlingua heavy hai
try:
    from llmlingua import PromptCompressor  # type: ignore
    _llmlingua_available = True
    print("  [INFO] llmlingua mila — library available hai.")
except ImportError:
    _llmlingua_available = False
    print("  [INFO] llmlingua nahi mila — manual compression demo chalega.")
    print("         Install: pip install llmlingua")


# Manual compression techniques — theory doc se
def manual_compress(prompt: str) -> tuple[str, float]:
    """
    Theory doc ke manual techniques:
      - Polite filler remove karo ('please', 'kindly', 'could you')
      - Redundant phrases hataao
      - Verbose hedging remove karo
    Returns (compressed_prompt, compression_ratio)
    """
    import re

    # Polite/filler words jo meaning nahi rakhte
    filler_patterns = [
        (r"\bplease\s+could\s+you\s+(kindly\s+)?", ""),
        (r"\bplease\s+(kindly\s+)?", ""),
        (r"\bkindly\s+", ""),
        (r"\bcould\s+you\s+please\s+", ""),
        (r"\bi\s+would\s+appreciate\s+it\s+if\s+you\s+could\s+", ""),
        (r"\bit\s+is\s+important\s+to\s+note\s+that\s+", ""),
        (r"\bplease\s+note\s+that\s+", ""),
        (r"\bas\s+mentioned\s+earlier[,.]?\s*", ""),
        (r"\bin\s+order\s+to\s+", "to "),
        (r"\bdue\s+to\s+the\s+fact\s+that\s+", "because "),
        (r"\bat\s+this\s+point\s+in\s+time\s+", "now "),
        (r"\bthe\s+reason\s+why\s+is\s+that\s+", "because "),
        (r"\s{2,}", " "),  # multiple spaces
    ]

    compressed = prompt
    for pattern, repl in filler_patterns:
        compressed = re.sub(pattern, repl, compressed, flags=re.IGNORECASE)

    compressed = compressed.strip()
    ratio = len(compressed) / len(prompt) if len(prompt) > 0 else 1.0
    return compressed, ratio


# Demo
verbose_prompts = [
    "Please could you kindly help me understand what Python is? It is important to note that I am a beginner.",
    "In order to complete this task, due to the fact that you are an AI assistant, please note that I would appreciate it if you could kindly explain async programming to me at this point in time.",
    "Explain: What is semantic caching?",   # already concise — almost no change
]

print("  Manual compression demo:")
for vp in verbose_prompts:
    cp, ratio = manual_compress(vp)
    savings = (1 - ratio) * 100
    print(f"\n  BEFORE ({len(vp)} chars): {vp[:70]}...")
    print(f"  AFTER  ({len(cp)} chars): {cp[:70]}{'...' if len(cp) > 70 else ''}")
    print(f"  Compression: {ratio:.2f}x ratio, {savings:.0f}% savings")

print("\n  INTERVIEW TIP:")
print("  LLMLingua 2-5x compression deta hai <5% quality loss pe.")
print("  Manual techniques: filler remove, bullet points use karo, concise examples.")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 6: Output Length Capping — max_tokens Tight Rakho
# THEORY: "Output tokens 2-4x mehenga — cap them per task type"
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 65)
print("SECTION 6: Output Length Capping — max_tokens Per Task Type")
print("=" * 65)

# Theory doc ka TASK_LIMITS exactly
TASK_LIMITS = {
    "classification":  10,
    "yes_no":           3,
    "short_answer":   150,
    "summary":        500,
    "article":       2000,
    "code":          4000,
}

print("\n  Task type -> max_tokens mapping (theory doc se):")
for task, limit in TASK_LIMITS.items():
    # GPT-4o output pricing: $10/1M = $0.00001 per token
    cost_per_call = limit * 10.0 / 1_000_000
    print(f"  {task:<18} max={limit:<6} est_cost_per_call=${cost_per_call:.6f}")

print("""
  Code example:
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=TASK_LIMITS["classification"],   # sirf 10 tokens!
        stop=["\\n", "END_OF_RESPONSE"],            # stop sequences bhi use karo
    )

  Stop sequences bhi cost bachaate hain:
    stop=["\\n\\n", "END_OF_RESPONSE", "</answer>"]
    -> LLM zaroorat se zyaada nahi likhta

  Real savings example:
    Without cap: summary task, avg 1200 tokens output, $0.012/call
    With cap 500: avg 480 tokens, $0.0048/call
    Savings: 60% per call!
""")

# Demonstrate stop sequence logic (offline simulation)
def simulate_output_cap(raw_output: str, max_tokens: int, stop_seqs: list[str]) -> str:
    """
    Simulate how max_tokens + stop sequences work.
    Actual truncation API karta hai — yeh sirf concept demo hai.
    """
    # Approximate: 4 chars ~= 1 token
    char_limit = max_tokens * 4
    truncated = raw_output[:char_limit]

    # Stop sequence check
    for stop in stop_seqs:
        idx = truncated.find(stop)
        if idx != -1:
            truncated = truncated[:idx]
            break
    return truncated


long_output = "Paris hai France ki rajdhani.\n\nAur bhi bohot kuch batane wala tha lekin yahan rok do.\n\nEND_OF_RESPONSE"
capped = simulate_output_cap(long_output, max_tokens=20, stop_seqs=["\n\n", "END_OF_RESPONSE"])
print(f"  Stop sequence demo:")
print(f"  Raw output: {repr(long_output)}")
print(f"  Capped (max=20 tokens, stop=['\\n\\n']): {repr(capped)}")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 7: Provider Cascade — Cheapest Pehle, Mehenga Last Resort
# THEORY: "60-70% queries cheapest provider se serve ho sakti hain"
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 65)
print("SECTION 7: Provider Cascade — Sasta Pehle, Mehenga Baad Mein")
print("=" * 65)

# Theory doc ka PROVIDERS_BY_COST
PROVIDERS_BY_COST = [
    {"name": "groq",      "model": "llama3-8b-8192",   "cost_per_1m": 0.05},
    {"name": "groq",      "model": "llama3-70b-8192",  "cost_per_1m": 0.59},
    {"name": "openai",    "model": "gpt-4o-mini",      "cost_per_1m": 0.15},
    {"name": "openai",    "model": "gpt-4o",           "cost_per_1m": 2.50},
    {"name": "anthropic", "model": "claude-opus",      "cost_per_1m": 15.0},
]


def simple_quality_check(query: str, response: str) -> bool:
    """
    Heuristic quality check — production mein LLM-as-judge use karo.
    Yahan: response minimum length check + error string check.
    """
    if not response or len(response) < 10:
        return False
    error_patterns = ["i don't know", "i cannot", "i'm not sure", "error", "failed"]
    resp_lower = response.lower()
    return not any(p in resp_lower for p in error_patterns)


def cascade_call_mock(query: str) -> dict:
    """
    Mock cascade — providers ko order mein try karo.
    Production mein: actual API call karo, quality_check pe escalate karo.
    """
    import random
    random.seed(hash(query) % 1000)

    for provider in PROVIDERS_BY_COST:
        # Mock: simple queries pe cheapest kaam karta hai
        is_simple = len(query) < 50
        cheap = provider["cost_per_1m"] < 1.0

        # Simulate: cheap models 80% simple queries handle kar lete hain
        if cheap and is_simple:
            success_prob = 0.85
        elif cheap:
            success_prob = 0.50
        else:
            success_prob = 0.95

        succeeded = random.random() < success_prob
        mock_response = (
            f"[{provider['model']}] Response to: {query[:30]}"
            if succeeded else
            "i don't know"
        )

        print(f"    Trying {provider['name']}/{provider['model']}: ", end="")
        if simple_quality_check(query, mock_response):
            print(f"OK (cost=${provider['cost_per_1m']:.2f}/1M)")
            return {
                "response": mock_response,
                "provider": provider["name"],
                "model":    provider["model"],
                "cost_tier": provider["cost_per_1m"],
            }
        else:
            print(f"FAILED quality — escalating...")

    return {"response": "[All providers failed]", "provider": "none", "model": "none", "cost_tier": 999}


test_cascade_queries = [
    "Hi!",                                          # simple — cheapest handle karega
    "What is 2 + 2?",                              # simple
    "Explain transformer architecture in detail.",  # complex — escalate ho sakta hai
]

print("  Provider cascade demo:")
total_saved = 0.0
for q in test_cascade_queries:
    print(f"\n  Query: '{q}'")
    result = cascade_call_mock(q)
    expensive_cost = 15.0  # claude-opus agar hamesha use karte
    actual_cost    = result["cost_tier"]
    saved = (expensive_cost - actual_cost) / expensive_cost * 100
    print(f"  Served by: {result['model']}, saved ~{saved:.0f}% vs always-expensive")

print("\n  INTERVIEW TIP: Quality check options:")
print("  1. Regex — expected pattern mein response hai?")
print("  2. LLM-as-judge — chhota model rate kare response ki quality")
print("  3. Logprobs — confidence score se decide karo")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 8: Batching — Ek Saath Kai Documents Embed Karo
# THEORY: "100x faster — batch embeddings rather than one by one"
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 65)
print("SECTION 8: Batching — Kai Documents Ek Saath Embed Karo")
print("=" * 65)

BATCH_CODE = '''
# GALAT tarika (slow + overhead zyaada):
for doc in docs_1000:
    embedding = embed(doc.content)    # 1000 API calls!
    db.store(doc.id, embedding)

# SAHI tarika (batch processing):
BATCH_SIZE = 100
for i in range(0, len(docs_1000), BATCH_SIZE):
    batch = docs_1000[i : i + BATCH_SIZE]
    texts = [d.content for d in batch]

    # OpenAI batch embed — 1 API call for 100 docs
    response = client.embeddings.create(
        model="text-embedding-3-small",
        input=texts,
    )
    embeddings = [e.embedding for e in response.data]
    db.bulk_store(zip([d.id for d in batch], embeddings))

# Result: 1000/100 = 10 API calls instead of 1000
# Speed: ~100x faster
# Cost: marginal savings + much lower latency
'''
print(BATCH_CODE)

# Timing demo — sequential vs batch simulation
import random

docs = [f"Document {i}: " + "x" * random.randint(50, 200) for i in range(20)]


async def fake_single_embed(text: str) -> list[float]:
    """Simulate single embed API call — 10ms latency."""
    await asyncio.sleep(0.01)
    return [0.1] * 5  # fake 5-dim vector


async def fake_batch_embed(texts: list[str]) -> list[list[float]]:
    """Simulate batch embed API call — 15ms regardless of batch size."""
    await asyncio.sleep(0.015)
    return [[0.1] * 5 for _ in texts]


async def demo_batching():
    BATCH_SIZE = 5

    # Sequential
    start = time.perf_counter()
    seq_embeddings = []
    for doc in docs:
        emb = await fake_single_embed(doc)
        seq_embeddings.append(emb)
    seq_time = time.perf_counter() - start

    # Batch
    start = time.perf_counter()
    batch_embeddings = []
    for i in range(0, len(docs), BATCH_SIZE):
        batch = docs[i: i + BATCH_SIZE]
        embs = await fake_batch_embed(batch)
        batch_embeddings.extend(embs)
    batch_time = time.perf_counter() - start

    print(f"  {len(docs)} documents embed karne ka time:")
    print(f"  Sequential (1 doc/call):  {seq_time:.3f}s  ({len(docs)} API calls)")
    n_batches = math.ceil(len(docs) / BATCH_SIZE)
    print(f"  Batch (size={BATCH_SIZE}):           {batch_time:.3f}s  ({n_batches} API calls)")
    if batch_time > 0:
        print(f"  Speedup: {seq_time/batch_time:.1f}x faster")


asyncio.run(demo_batching())
print("\n  INTERVIEW TIP: text-embedding-3-small = $0.02/1M tokens — cheapest option.")
print("  Voyage-3 ($0.06/1M) aur Cohere embed-v3 ($0.10/1M) quality mein aage hain.")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 9: Per-Tenant Quota — Ek Bura Tenant Sab Budget Na Jale
# THEORY: "No per-tenant quotas -> one bad tenant burns budget"
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 65)
print("SECTION 9: Per-Tenant Quota — Budget Protection")
print("=" * 65)

@dataclass
class TenantQuota:
    """
    Per-tenant quota system.
    Production mein: Redis incrbyfloat se atomic increment karo.
    Yahan in-memory dict use kar rahe hain.
    """
    plans: dict = field(default_factory=lambda: {
        "free":       {"daily_budget": 0.10},
        "starter":    {"daily_budget": 1.00},
        "pro":        {"daily_budget": 10.0},
        "enterprise": {"daily_budget": 100.0},
    })
    _usage: dict = field(default_factory=dict)  # tenant_id -> daily spend

    def check_and_deduct(self, tenant_id: str, plan: str, estimated_cost: float) -> tuple[bool, str]:
        """
        Quota check + deduction.
        Returns (allowed: bool, message: str)
        """
        budget = self.plans.get(plan, self.plans["free"])["daily_budget"]
        current = self._usage.get(tenant_id, 0.0)

        if current + estimated_cost > budget:
            return False, (
                f"Quota exceeded! Tenant={tenant_id}, plan={plan}, "
                f"budget=${budget:.2f}, used=${current:.4f}, "
                f"requested=${estimated_cost:.4f}"
            )
        self._usage[tenant_id] = current + estimated_cost
        remaining = budget - self._usage[tenant_id]
        return True, f"OK — remaining=${remaining:.4f}"


quota_mgr = TenantQuota()

# Simulate various tenants making requests
tenant_requests = [
    ("tenant_free_1",  "free",       0.05),   # almost hits limit
    ("tenant_free_1",  "free",       0.08),   # should FAIL — exceeds $0.10
    ("tenant_pro_1",   "pro",        2.50),   # should pass
    ("tenant_pro_1",   "pro",        8.00),   # should pass (total 10.5 > 10.0 = FAIL)
    ("tenant_ent_1",   "enterprise", 50.0),   # should pass
]

print("  Per-tenant quota simulation:")
for tid, plan, cost in tenant_requests:
    allowed, msg = quota_mgr.check_and_deduct(tid, plan, cost)
    status = "ALLOWED" if allowed else "BLOCKED"
    print(f"  [{status}] {tid:<20} plan={plan:<12} cost=${cost:.2f}  {msg}")

print("\n  INTERVIEW TIP:")
print("  Redis incrbyfloat atomic hai — race conditions nahi aati concurrent requests mein.")
print("  Daily budget = UTC midnight pe reset karo.")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 10: Cost Optimization Roadmap Summary
# THEORY: "Cumulative possible savings: 80-95%"
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 65)
print("SECTION 10: Cost Optimization Roadmap — Sabka Summary")
print("=" * 65)

print("""
  Theory doc ka roadmap (in order of implementation priority):

  Step 1: MEASURE (CostTracker + dashboard)
          -> Jab tak measure nahi karte, optimize kya karoge?
          -> per-endpoint, per-tenant, per-model breakdown chahiye

  Step 2: Quick wins (30-40% savings)
          -> History trim karo last N messages pe
          -> max_tokens aggressively set karo per task
          -> Cheap model for embedding routing

  Step 3: Semantic caching (additional 20-40%)
          -> Redis + vector search
          -> threshold 0.95 se start karo
          -> Customer support mein 60-80% hit rate possible

  Step 4: Provider-side prompt caching (50-90% on stable prefixes)
          -> Stable system prompt + few-shot examples pehle
          -> Anthropic: explicit cache_control, 10% of input cost on read
          -> OpenAI: automatic for >= 1024 token prefixes

  Step 5: Model routing (50-70% on average)
          -> Simple queries -> cheapest tier (Groq free tier!)
          -> Complexity classify karne ke liye bhi cheapest model use karo

  Step 6: Prompt compression (2-5x input reduction)
          -> LLMLingua ya manual techniques
          -> Output tokens 2-4x mehenga — max_tokens + stop sequences

  Step 7: Distillation (95% on specific narrow tasks)
          -> Fine-tune LLaMA-8B on GPT-4o outputs
          -> Sirf high-volume narrow tasks ke liye worth hai
          -> >100k calls/day, 5k+ labeled examples chahiye

  Cumulative: 80-95% cost reduction POSSIBLE!
""")

# Final cost comparison demo
print("  Real cost comparison example:")
print(f"  {'Scenario':<35} {'Monthly Cost':>14} {'Savings':>10}")
print("  " + "-" * 62)

scenarios = [
    ("Naive (GPT-4o everything)",          5000.0, 0.0),
    ("After Step 2 (trim + max_tokens)",   3500.0, 30.0),
    ("After Step 3 (semantic cache)",      2100.0, 58.0),
    ("After Step 4 (prompt caching)",      1050.0, 79.0),
    ("After Step 5 (model routing)",        420.0, 91.6),
    ("After Step 6 (compression)",          280.0, 94.4),
    ("After Step 7 (distillation)",         150.0, 97.0),
]

for scenario, cost, savings in scenarios:
    print(f"  {scenario:<35} ${cost:>12,.0f}  {savings:>8.1f}%")

print()
print("  INTERVIEW TIP — Senior mantra from theory doc:")
print("  'MEASURE first. Cheap model for 80%. Cache pays in weeks.")
print("   Output tokens 2-4x input — cap them. Self-host ONLY at >$50k/month.'")


# ─────────────────────────────────────────────────────────────────────────────
# FINAL SUMMARY
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 65)
print("COST OPTIMIZATION ADVANCED — LAB COMPLETE")
print("=" * 65)
print("""
  Strategies covered (theory doc se):
  S1  Cost Tracker       — Measure karo, tabhi optimize karo
  S2  Model Routing      — Complexity se tier decide karo
  S3  Semantic Cache     — Similar queries pe LLM skip karo
  S4  Context Trimming   — Purana history mat bhejo
  S5  Prompt Compression — Manual techniques + LLMLingua
  S6  Output Capping     — max_tokens + stop sequences
  S7  Provider Cascade   — Cheapest pehle, mehenga fallback
  S8  Batching           — 100 docs ek call mein embed karo
  S9  Per-Tenant Quota   — Ek tenant sab budget na jale
  S10 Roadmap            — Step-by-step 80-95% savings

  INTERVIEW QUESTIONS:
  Q: LLM costs 80% kaise reduce karo?
  A: Layered approach — Measure -> Cache -> Route -> Compress ->
     Trim -> Prompt cache -> Distill. Cumulative: 80-95%.

  Q: Semantic caching ROI kya hai?
  A: 60% hit rate on $10k/month = $6k saved/month. 1-2 week build. 4-week payback.

  Q: Output vs input tokens?
  A: Output 2-4x mehenga (GPT-4o: $2.50 in / $10 out). max_tokens LAGAO.
""")
print("Done! EXIT 0.")
