"""
Level 1 — Doc 5: LLM Models Landscape (PRACTICAL)
===================================================
Topics covered:
  1. A runnable model-selection decision tree (turn the doc's flowchart into code)
  2. Real cost comparison across providers, for a realistic workload
  3. Live "same query, different model" comparison (when keys are available)
  4. Closed vs open-source trade-off, as a scoring function you can actually call

Install:
  pip install openai anthropic litellm python-dotenv

Run: python 05_models_landscape_practical.py
"""

import os
import time
from dotenv import load_dotenv

load_dotenv()


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 1: Model Selection — the Decision Tree, as Actual Code
# ─────────────────────────────────────────────────────────────────────────────

print("=" * 70)
print("SECTION 1: Model Selection Decision Tree")
print("=" * 70)


def recommend_model(task: str, latency_sensitive: bool, budget_conscious: bool, needs_reasoning: bool) -> str:
    """Turns the doc's prose flowchart into something you can actually call
    from a router in a real app, instead of eyeballing a diagram each time."""
    if needs_reasoning:
        return "o3 / DeepSeek R1 — extended reasoning worth the latency+cost hit"
    if task == "code" and not budget_conscious:
        return "Claude Sonnet — strongest at code, worth the premium"
    if latency_sensitive and budget_conscious:
        return "gpt-4o-mini / Claude Haiku / Gemini Flash — cheapest + fastest tier"
    if task == "embedding" or task == "classification":
        return "gpt-4o-mini or a self-hosted small model — this task rarely needs a frontier model"
    if budget_conscious:
        return "open-source self-hosted (Llama/Mistral/Qwen) — pay compute, not per-token"
    return "gpt-4o / Claude Sonnet — general-purpose default, no special constraint"


scenarios = [
    {"task": "chat support widget", "latency_sensitive": True, "budget_conscious": True, "needs_reasoning": False},
    {"task": "code", "latency_sensitive": False, "budget_conscious": False, "needs_reasoning": False},
    {"task": "math word problems", "latency_sensitive": False, "budget_conscious": False, "needs_reasoning": True},
    {"task": "classification", "latency_sensitive": True, "budget_conscious": True, "needs_reasoning": False},
    {"task": "internal batch summarization, huge volume", "latency_sensitive": False, "budget_conscious": True, "needs_reasoning": False},
]

for s in scenarios:
    rec = recommend_model(s["task"], s["latency_sensitive"], s["budget_conscious"], s["needs_reasoning"])
    print(f"\n  Scenario: {s['task']}")
    print(f"    -> {rec}")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 2: Real Cost Comparison for a Realistic Workload
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("SECTION 2: Cost Comparison (per 1M tokens, as of doc writing)")
print("=" * 70)

PRICING = {
    "gpt-4o-mini": {"input": 0.15, "output": 0.60, "tier": "cheap"},
    "gpt-4o": {"input": 2.50, "output": 10.00, "tier": "mid"},
    "claude-3-5-haiku-20241022": {"input": 0.25, "output": 1.25, "tier": "cheap"},
    "claude-3-5-sonnet-20241022": {"input": 3.00, "output": 15.00, "tier": "mid"},
}

# A realistic workload: 100k requests/day, 500 input tokens + 150 output tokens each
requests_per_day = 100_000
input_tok, output_tok = 500, 150

print(f"\n  Workload: {requests_per_day:,} requests/day, {input_tok} in + {output_tok} out tokens each\n")
for model, p in PRICING.items():
    daily_cost = (requests_per_day * input_tok * p["input"] + requests_per_day * output_tok * p["output"]) / 1_000_000
    monthly = daily_cost * 30
    print(f"  {model:30s} [{p['tier']:5s}]  ${daily_cost:8.2f}/day   ${monthly:9.2f}/month")

print("\n  This is the actual math behind 'why not just use the best model for everything' —")
print("  at 100k req/day, the gap between cheap and mid tier is thousands of dollars/month.")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 3: Live Comparison — Same Query, Different Models
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("SECTION 3: Same Query, Different Models (live if keys available)")
print("=" * 70)

query = "In one sentence, what's the main trade-off between a bigger and a smaller LLM?"


def try_model(model: str, env_key: str):
    if not os.getenv(env_key):
        return f"[skipped — no {env_key}]"
    try:
        from litellm import completion
        t0 = time.time()
        resp = completion(model=model, messages=[{"role": "user", "content": query}], max_tokens=60)
        elapsed = time.time() - t0
        return f"({elapsed:.2f}s) {resp.choices[0].message.content}"
    except ImportError:
        return "[litellm not installed — pip install litellm]"
    except Exception as e:
        return f"[error: {e}]"


for model, env_key in [("gpt-4o-mini", "OPENAI_API_KEY"), ("claude-3-5-haiku-20241022", "ANTHROPIC_API_KEY")]:
    print(f"\n  [{model}]")
    print(f"  {try_model(model, env_key)}")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 4: Closed vs Open-Source — a Scoring Function
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("SECTION 4: Closed vs Open-Source Trade-off, Quantified")
print("=" * 70)


def should_self_host(monthly_requests: int, has_ml_infra_team: bool, data_sensitivity: str) -> str:
    """A real decision has to weigh volume + team capability + compliance —
    not just 'open source is cheaper'. This encodes that trade-off explicitly."""
    if data_sensitivity == "high" and not has_ml_infra_team:
        return "Closed-source, but check for a private/VPC deployment option (compliance > raw cost here)"
    if monthly_requests > 10_000_000 and has_ml_infra_team:
        return "Self-host — at this volume, GPU cost amortizes below API cost, and you have the team to run it"
    if data_sensitivity == "high" and has_ml_infra_team:
        return "Self-host — full data control, and you can operate the infra"
    return "Closed-source API — simpler, and volume/sensitivity don't yet justify the ops burden"


test_cases = [
    (500_000, False, "low"),
    (50_000_000, True, "low"),
    (200_000, False, "high"),
    (20_000_000, True, "high"),
]
for reqs, has_team, sensitivity in test_cases:
    decision = should_self_host(reqs, has_team, sensitivity)
    print(f"\n  {reqs:,} req/month, ML infra team: {has_team}, data sensitivity: {sensitivity}")
    print(f"    -> {decision}")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 5: Exercises
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("SECTION 5: EXERCISES")
print("=" * 70)
print("""
EASY:
1. Add a 5th scenario to `scenarios` from your own current project. What
   does recommend_model() suggest, and do you agree?

MEDIUM:
2. Extend the cost model in Section 2 with a 3rd tier — a reasoning model
   (o3-class) at ~10x mid-tier pricing. Recompute monthly cost for 1% of
   requests routed there.

HARD:
3. Build a real "smart router": given a prompt, classify it as easy/medium/hard
   using a cheap model first, THEN route to the appropriate tier from Section 1.
   Measure total cost vs always using the mid-tier model.

PRO:
4. `should_self_host()` currently ignores latency requirements. Add a
   `latency_slo_ms` parameter and change the logic — self-hosting near your
   users can beat a shared API's latency at high enough volume. Justify the
   threshold you pick.
""")

if __name__ == "__main__":
    print("\nDone. Next: 06_dev_environment_setup_practical.py")
