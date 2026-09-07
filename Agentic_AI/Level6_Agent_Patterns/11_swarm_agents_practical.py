"""
Level 6 — Doc 11: Swarm Agents (PRACTICAL)
============================================
Manual swarm implementation from scratch, using OpenAI function calling —
no dependency on the (now largely superseded) `swarm` package, matching
Part 3 of the theory doc but built on OpenAI's tool-calling API for
consistency with the rest of this repo's Level 6 practicals.

Topics covered:
  1. Handoff mechanism — a triage agent routes to specialist agents via a
     function call, not a central supervisor deciding everything
  2. Context variables carried across handoffs
  3. Parallel swarm (multiple specialists reviewing the same input at once —
     related pattern, not a handoff)
  4. Swarm vs Supervisor — same input run through both, compared

Install: pip install openai python-dotenv
Run: python 11_swarm_agents_practical.py
"""

import os
import json
from concurrent.futures import ThreadPoolExecutor
from dotenv import load_dotenv

load_dotenv()
HAS_KEY = bool(os.getenv("OPENAI_API_KEY"))


def llm_call(messages, tools=None, system=None, model="gpt-4o-mini"):
    if not HAS_KEY:
        return None
    from openai import OpenAI
    client = OpenAI()
    full_messages = ([{"role": "system", "content": system}] if system else []) + messages
    kwargs = {"model": model, "messages": full_messages, "max_tokens": 300}
    if tools:
        kwargs["tools"] = tools
    return client.chat.completions.create(**kwargs)


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 1: Handoff Mechanism — Triage Routes to Specialists
# ─────────────────────────────────────────────────────────────────────────────

print("=" * 70)
print("SECTION 1: Swarm Handoff — Triage -> Billing/Technical")
print("=" * 70)

HANDOFF_TOOLS = [
    {"type": "function", "function": {
        "name": "transfer_to_billing",
        "description": "Route to the billing specialist for payment/invoice/refund queries.",
        "parameters": {"type": "object", "properties": {}},
    }},
    {"type": "function", "function": {
        "name": "transfer_to_technical",
        "description": "Route to the technical specialist for bugs/errors/system issues.",
        "parameters": {"type": "object", "properties": {}},
    }},
]

AGENTS = {
    "triage": {
        "system": "You route customer queries. Billing/payment -> transfer_to_billing. "
                  "Technical issue -> transfer_to_technical. General question -> answer directly.",
        "tools": HANDOFF_TOOLS,
    },
    "billing": {
        "system": "You are the billing specialist. Handle payment and invoice questions directly, concisely.",
        "tools": None,
    },
    "technical": {
        "system": "You are the technical specialist. Debug and explain the issue concisely.",
        "tools": None,
    },
}


def run_swarm(user_message: str, context: dict, max_hops: int = 3) -> tuple[str, str]:
    """Returns (final_agent_name, final_response_text)."""
    current = "triage"
    messages = [{"role": "user", "content": user_message}]

    for hop in range(max_hops):
        agent = AGENTS[current]
        resp = llm_call(messages, tools=agent["tools"], system=agent["system"])
        if resp is None:
            return current, "[NO_API_KEY]"

        msg = resp.choices[0].message
        if msg.tool_calls:
            call = msg.tool_calls[0]
            next_agent = call.function.name.replace("transfer_to_", "")
            print(f"  [Handoff: {current} -> {next_agent}]")
            current = next_agent
            # New agent gets a fresh view — just the original user message, not the
            # triage agent's internal tool-call turn. This is the actual mechanism:
            # each agent in the swarm only sees what it needs, not the routing history.
            messages = [{"role": "user", "content": user_message}]
            continue

        return current, msg.content

    return current, "[max hops reached]"


test_queries = [
    "I don't see my last invoice, can you help?",
    "My API keeps returning 500 errors since this morning.",
    "What are your business hours?",
]

for q in test_queries:
    agent, response = run_swarm(q, context={})
    print(f"\n  Query: {q}")
    print(f"  Final agent: {agent}")
    print(f"  Response: {response}")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 2: Context Variables Carried Across Handoffs
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("SECTION 2: Context Variables Across Handoffs")
print("=" * 70)

print("""
  The doc's key point: handoffs must carry STATE, not just the conversation.
  A returns agent needs to know the order_id the support agent already looked up —
  re-asking the user for it after a silent handoff is a classic swarm UX bug.
""")


def lookup_order(order_id: str, context: dict) -> str:
    context["last_order_id"] = order_id
    context["order_status"] = "shipped"
    return f"Order {order_id}: shipped, arriving in 3 days."


context = {"user_name": "Rahul", "user_tier": "premium"}
print(f"  Context before: {context}")
result = lookup_order("1234", context)
print(f"  Tool result: {result}")
print(f"  Context after: {context}")
print("\n  When the handoff to 'returns' fires next, it receives THIS context dict,")
print("  not just the chat history — so it can process a return on order 1234")
print("  without asking the user to repeat the order number.")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 3: Parallel Swarm — Related Pattern, Not a Handoff
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("SECTION 3: Parallel Review (multiple specialists, same input, at once)")
print("=" * 70)

print("""
  Not a handoff — no routing decision. Multiple specialists see the SAME
  input simultaneously and a synthesis step combines their outputs. Useful
  for review/analysis tasks where every angle matters, not just one.
""")

document = "We're proposing to store user session tokens in localStorage and skip refresh-token rotation to simplify the frontend."


def specialist_review(role: str, focus: str, doc: str) -> str:
    resp = llm_call(
        [{"role": "user", "content": doc}],
        system=f"You are a {role}. Review ONLY for {focus}. One sentence.",
    )
    return resp.choices[0].message.content if resp else "[NO_API_KEY]"


specialists = [
    ("security engineer", "security risks"),
    ("frontend architect", "implementation complexity"),
    ("compliance officer", "regulatory/data-protection concerns"),
]

with ThreadPoolExecutor(max_workers=3) as pool:
    futures = {pool.submit(specialist_review, role, focus, document): role for role, focus in specialists}
    reviews = {futures[f]: f.result() for f in futures}

for role, review in reviews.items():
    print(f"\n  [{role}]")
    print(f"  {review}")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 4: Swarm vs Supervisor — When Each Wins
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("SECTION 4: Swarm vs Supervisor — Same Query, Both Patterns")
print("=" * 70)

print("""
  Swarm  : decentralized — each agent decides when to hand off. No central
           bottleneck, but harder to audit "why did it route there?"
  Supervisor (Doc 7) : centralized — one LLM makes every routing decision.
           Easier to reason about and log, but that LLM is a bottleneck and
           single point of failure.

  Rule of thumb from the doc's comparison table: reach for Swarm when the
  domains are genuinely separate (billing vs technical never need to
  collaborate mid-task) — reach for Supervisor when tasks need active
  decomposition and coordination, not just routing.
""")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 5: Exercises
# ─────────────────────────────────────────────────────────────────────────────

print("=" * 70)
print("SECTION 5: EXERCISES")
print("=" * 70)
print("""
EASY:
1. Add a 4th agent ("returns") and a transfer_to_returns tool from billing.
   Run a query that should hop triage -> billing -> returns.

MEDIUM:
2. Add a max_hops guard that returns a graceful "let me get a human" message
   instead of "[max hops reached]" — what a real product needs, not a stack trace.

HARD:
3. Make context ACTUALLY flow between agents in run_swarm() — right now each
   handoff resets messages to just the user's original text. Thread the
   context dict through and have the technical agent's system prompt
   reference context["last_order_id"] if the user was already routed once.

PRO:
4. Compare cost + latency of this swarm's 2-hop query against a single
   Supervisor call handling the same triage+resolve in one LLM call with a
   bigger system prompt. Which one is actually cheaper for THIS use case?
""")

if __name__ == "__main__":
    print("\nDone. Next: 12_agent_harness_engineering_practical.py")
