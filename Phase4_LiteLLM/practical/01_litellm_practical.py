"""
Phase4_LiteLLM — Complete Practical
=====================================
Topics:
  1. Unified interface for OpenAI / Claude / Gemini / Mistral
  2. Model routing + fallback
  3. Cost tracking
  4. Load balancing
  5. In-memory caching
  6. LiteLLM proxy server

Install: pip install litellm
Run: python 01_litellm_practical.py
"""

import os, json, time, asyncio

MOCK_MODE = not os.getenv("OPENAI_API_KEY") and not os.getenv("ANTHROPIC_API_KEY")
if MOCK_MODE:
    print("⚠  MOCK MODE — set OPENAI_API_KEY or ANTHROPIC_API_KEY\n")

try:
    import litellm
    from litellm import completion, acompletion, embedding
    LITELLM_AVAILABLE = True
except ImportError:
    LITELLM_AVAILABLE = False
    print("litellm not installed: pip install litellm\n")

# ─────────────────────────────────────────────────────────────────────────────
# SECTION 1: Unified Interface
# INTERVIEW: Same code, any provider — provider-agnostic
# ─────────────────────────────────────────────────────────────────────────────

print("=" * 60)
print("SECTION 1: LiteLLM Unified Interface")
print("=" * 60)

LITELLM_MODELS = {
    "gpt-4o":                  "OpenAI GPT-4o",
    "claude-sonnet-4-6":       "Anthropic Claude",
    "gemini/gemini-2.0-flash": "Google Gemini",
    "groq/llama3-70b-8192":    "Groq (Llama 3, very fast)",
    "ollama/llama3.2":         "Local Ollama",
    "azure/gpt-4o":            "Azure OpenAI",
}
print("\n  Supported models (same API for all):")
for m, d in LITELLM_MODELS.items():
    print(f"  {m:<30}: {d}")

def call_any_model(model: str, message: str) -> str:
    """
    INTERVIEW: LiteLLM = abstraction layer over all LLM providers.
    Change model string → different provider, same code.
    """
    if MOCK_MODE or not LITELLM_AVAILABLE:
        return f"[Mock response from {model}]: Hello! I understand your question."

    response = litellm.completion(
        model    = model,
        messages = [{"role": "user", "content": message}],
        max_tokens = 100,
    )
    return response.choices[0].message.content


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 2: Fallback Routing
# INTERVIEW: If primary fails → try fallback providers automatically
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 60)
print("SECTION 2: Fallback Routing")
print("=" * 60)

FALLBACK_CODE = '''\
import litellm

# INTERVIEW: fallbacks = list of models to try in order
# If gpt-4o fails → try claude → try gemini
response = litellm.completion(
    model    = "gpt-4o",
    messages = [{"role": "user", "content": "Hello"}],
    fallbacks = ["claude-sonnet-4-6", "gemini/gemini-2.0-flash"],
    # OR: model_list for more control:
)

# ── Router for advanced load balancing ──
from litellm import Router

router = Router(
    model_list = [
        {
            "model_name":    "fast-model",   # your name
            "litellm_params": {
                "model":   "gpt-4o-mini",
                "api_key": os.getenv("OPENAI_API_KEY"),
            },
            "tpm": 100_000,   # tokens per minute limit
            "rpm": 100,       # requests per minute limit
        },
        {
            "model_name":    "fast-model",  # same logical name → load balanced!
            "litellm_params": {
                "model":   "groq/llama3-70b-8192",
                "api_key": os.getenv("GROQ_API_KEY"),
            },
        },
    ],
    fallbacks              = [{"fast-model": ["claude-sonnet-4-6"]}],
    routing_strategy       = "least-busy",  # or "latency-based", "usage-based"
    retry_policy           = {"BadRequestError": 0, "TimeoutError": 2},
)

# Router usage:
response = await router.acompletion(
    model    = "fast-model",  # automatically routes
    messages = [{"role": "user", "content": "Hello"}],
)
'''
print(FALLBACK_CODE[:600])


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 3: Cost Tracking
# INTERVIEW: Monitor LLM spend across providers
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 60)
print("SECTION 3: Cost Tracking")
print("=" * 60)

COST_CODE = '''\
import litellm

# Per-call cost
response = litellm.completion(
    model    = "gpt-4o-mini",
    messages = [{"role": "user", "content": "Hello"}],
)
cost = litellm.completion_cost(completion_response=response)
print(f"Cost: ${cost:.6f}")
# → Cost: $0.000045

# Cumulative cost tracking
total_cost = 0.0
calls = [
    ("gpt-4o-mini",     "Simple question"),
    ("gpt-4o",          "Complex analysis"),
    ("claude-haiku-4-5","Classification task"),
]
for model, prompt in calls:
    resp  = litellm.completion(model=model, messages=[{"role": "user", "content": prompt}])
    cost  = litellm.completion_cost(resp)
    total_cost += cost
    print(f"  {model}: ${cost:.6f}")
print(f"  Total: ${total_cost:.6f}")

# Budget alerts
litellm.max_budget = 10.0   # $10 limit
# Raises litellm.BudgetExceededError when exceeded
'''
print(COST_CODE)

# Demo cost calculation without real API
COST_TABLE = [
    ("gpt-4o",               500, 200, 0.0050),
    ("gpt-4o-mini",          500, 200, 0.0003),
    ("claude-sonnet-4-6",    500, 200, 0.0045),
    ("claude-haiku-4-5",     500, 200, 0.0006),
]
print("\n  Estimated cost per 1000 calls (500 input, 200 output tokens):")
for model, inp, out, cost_per_call in COST_TABLE:
    total = cost_per_call * 1000
    print(f"  {model:<28}: ${cost_per_call:.4f}/call → ${total:.2f}/1000 calls")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 4: Caching
# INTERVIEW: Identical prompts → return cached result (zero cost)
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 60)
print("SECTION 4: LiteLLM Caching")
print("=" * 60)

CACHE_CODE = '''\
import litellm
from litellm.caching import Cache

# ── In-memory cache (local, single process) ──
litellm.cache = Cache()

# ── Redis cache (shared across instances) ──
litellm.cache = Cache(
    type="redis",
    host="localhost",
    port=6379,
    password=os.getenv("REDIS_PASSWORD"),
    ttl=3600,   # cache for 1 hour
)

# ── Semantic cache (similar prompts = cache hit) ──
litellm.cache = Cache(
    type="redis-semantic",
    similarity_threshold=0.8,   # 80% similar → cache hit
    embedding_model="text-embedding-3-small",
)

# Usage (cache is automatic):
response1 = litellm.completion(
    model="gpt-4o-mini",
    messages=[{"role": "user", "content": "What is Python?"}],
    caching=True,   # enable caching for this call
)
# First call: hits API, stores in cache

response2 = litellm.completion(
    model="gpt-4o-mini",
    messages=[{"role": "user", "content": "What is Python?"}],
    caching=True,
)
# Second call: cache HIT → no API call, instant response!
print(response2._hidden_params["cache_hit"])  # → True
'''
print(CACHE_CODE[:500])


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 5: LiteLLM Proxy Server
# INTERVIEW: Central LLM gateway for teams
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 60)
print("SECTION 5: LiteLLM Proxy Server")
print("=" * 60)

PROXY_CONFIG = """\
# config.yaml — LiteLLM Proxy config
model_list:
  - model_name: gpt-4o
    litellm_params:
      model: gpt-4o
      api_key: os.environ/OPENAI_API_KEY

  - model_name: claude-fast
    litellm_params:
      model: claude-haiku-4-5
      api_key: os.environ/ANTHROPIC_API_KEY

litellm_settings:
  set_verbose: false
  max_budget:  100    # $100 total budget

router_settings:
  routing_strategy: latency-based-routing
  fallbacks: [{gpt-4o: [claude-fast]}]

general_settings:
  master_key: sk-my-proxy-key   # team API key

# Start: litellm --config config.yaml --port 8000
# Use:   curl -X POST http://localhost:8000/chat/completions \\
#          -H 'Authorization: Bearer sk-my-proxy-key' \\
#          -d '{model: gpt-4o, messages: [...]}'
#
# INTERVIEW: Proxy benefits:
#   - One API key per team member (not individual provider keys)
#   - Centralized cost tracking + budget enforcement
#   - Provider switching without code changes
#   - Rate limit management
"""
print(PROXY_CONFIG)

print("\n" + "=" * 60)
print("LITELLM INTERVIEW SUMMARY:")
print("  LiteLLM = abstraction over all LLM providers (same API)")
print("  Fallbacks: if gpt-4o fails → claude → gemini (automatic)")
print("  Cost: litellm.completion_cost(response) → per-call pricing")
print("  Cache: identical prompts → instant return, zero cost")
print("  Proxy: team gateway — centralized keys, budgets, routing")
print("=" * 60)
