"""
Level 6 — Doc 7: Multi-Agent Supervisor (PRACTICAL)
=====================================================
Build supervisor + specialists from scratch. No framework.

Topics:
  1. Specialist agent class
  2. Supervisor (routing logic)
  3. Sequential multi-agent flow
  4. Parallel multi-agent execution
  5. Shared state between agents
  6. Code reviewer demo (security + performance + style)

Install: pip install openai python-dotenv
Run: python 07_multi_agent_supervisor_practical.py
"""

import os
import json
from typing import Optional
from concurrent.futures import ThreadPoolExecutor
from dotenv import load_dotenv

load_dotenv()


def llm_call(prompt: str, model: str = "gpt-4o-mini", system: Optional[str] = None,
             temperature: float = 0, max_tokens: int = 500) -> dict:
    """LLM call returning text + usage."""
    if not os.getenv("OPENAI_API_KEY"):
        return {"text": "[NO_API_KEY]", "tokens": 0, "cost": 0}
    try:
        from openai import OpenAI
        client = OpenAI()
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        resp = client.chat.completions.create(
            model=model, messages=messages, temperature=temperature, max_tokens=max_tokens
        )
        usage = resp.usage
        # gpt-4o-mini pricing
        cost = (usage.prompt_tokens * 0.15 + usage.completion_tokens * 0.60) / 1_000_000
        return {
            "text": resp.choices[0].message.content,
            "tokens": usage.total_tokens,
            "cost": cost
        }
    except Exception as e:
        return {"text": f"[Error: {e}]", "tokens": 0, "cost": 0}


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 1: Specialist Agent Class
# ─────────────────────────────────────────────────────────────────────────────

print("=" * 70)
print("SECTION 1: Specialist Agents")
print("=" * 70)


class SpecialistAgent:
    """A specialist focused on a specific domain."""

    def __init__(self, name: str, role: str, system_prompt: str, model: str = "gpt-4o-mini"):
        self.name = name
        self.role = role
        self.system_prompt = system_prompt
        self.model = model
        self.call_count = 0
        self.total_cost = 0

    def execute(self, task: str, context: Optional[dict] = None) -> dict:
        self.call_count += 1
        prompt = task
        if context:
            prompt = f"Context: {json.dumps(context, indent=2)}\n\nTask: {task}"

        result = llm_call(prompt, model=self.model, system=self.system_prompt, max_tokens=400)
        self.total_cost += result["cost"]
        return {
            "agent": self.name,
            "output": result["text"],
            "cost": result["cost"]
        }


# Define 3 specialists for code review
security_specialist = SpecialistAgent(
    name="security_reviewer",
    role="Security expert — finds OWASP Top 10 vulnerabilities",
    system_prompt="""You are a security code reviewer with 15 years of experience.
Focus EXCLUSIVELY on security issues:
- SQL injection
- XSS, CSRF
- Insecure deserialization
- Hardcoded credentials
- Path traversal
- Crypto issues

Format your review as:
- Severity: HIGH/MEDIUM/LOW
- Issue: ...
- Fix: ...

If no security issues, say "No security issues found."
Do NOT comment on performance or style."""
)

performance_specialist = SpecialistAgent(
    name="performance_reviewer",
    role="Performance expert — analyzes time/space complexity",
    system_prompt="""You are a performance engineer.
Focus EXCLUSIVELY on:
- Time complexity (Big O)
- Memory usage
- N+1 query problems
- Unnecessary computations
- Caching opportunities

Format:
- Issue: ...
- Current complexity: O(...)
- Recommended: O(...)
- Fix: ...

Do NOT comment on security or style."""
)

style_specialist = SpecialistAgent(
    name="style_reviewer",
    role="Code style and readability expert",
    system_prompt="""You are a Python style reviewer.
Focus EXCLUSIVELY on:
- PEP 8 compliance
- Naming conventions
- Type hints
- Docstrings
- Code readability

Format:
- Issue: ...
- Recommendation: ...

Do NOT comment on security or performance."""
)


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 2: Supervisor Agent (Sequential Routing)
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("SECTION 2: Supervisor — Sequential Multi-Agent")
print("=" * 70)


class SequentialSupervisor:
    """Routes task through specialists one-by-one based on supervisor's decisions."""

    def __init__(self, specialists: list[SpecialistAgent], model: str = "gpt-4o-mini"):
        self.specialists = {s.name: s for s in specialists}
        self.model = model
        self.history = []

    def decide(self, query: str) -> dict:
        """Decide next action."""
        specs_text = "\n".join(f"- {s.name}: {s.role}" for s in self.specialists.values())
        history_text = "\n".join(
            f"[{h['agent']} ran] → output preview: {h['output'][:120]}..."
            for h in self.history
        )

        prompt = f"""You are a supervisor managing specialist agents.

USER QUERY:
{query}

AVAILABLE SPECIALISTS:
{specs_text}

ALREADY CONSULTED:
{history_text if history_text else "(none yet)"}

DECIDE NEXT ACTION. Output ONLY JSON:
{{"action": "delegate", "agent": "name", "task": "specific task for that agent"}}
OR
{{"action": "finish", "final_answer": "synthesized answer from all results"}}

CRITICAL: Only call each specialist ONCE. Once you've used all specialists relevant to the query, finish."""

        result = llm_call(prompt, model=self.model, max_tokens=400)
        try:
            return json.loads(result["text"])
        except json.JSONDecodeError:
            # Try to extract JSON from text
            import re
            match = re.search(r"\{.*\}", result["text"], re.DOTALL)
            if match:
                try:
                    return json.loads(match.group())
                except json.JSONDecodeError:
                    pass
            return {"action": "finish", "final_answer": result["text"]}

    def run(self, query: str, max_iter: int = 5) -> dict:
        self.history = []
        for i in range(max_iter):
            decision = self.decide(query)
            print(f"\n[Iteration {i + 1}] Supervisor decision: {decision.get('action')}")

            if decision["action"] == "finish":
                return {
                    "final_answer": decision.get("final_answer", "Complete"),
                    "history": self.history,
                    "iterations": i + 1
                }

            agent_name = decision["agent"]
            task = decision["task"]

            if agent_name not in self.specialists:
                print(f"  ⚠️ Unknown agent: {agent_name}")
                continue

            print(f"  → Delegating to '{agent_name}': {task[:80]}...")
            result = self.specialists[agent_name].execute(task)
            print(f"  ← Got {len(result['output'])} chars from {agent_name}")
            self.history.append(result)

        # Reached max iter — synthesize
        return {
            "final_answer": "Max iterations. Reviews from: " +
                          ", ".join(h["agent"] for h in self.history),
            "history": self.history,
            "iterations": max_iter
        }


# Demo: review buggy code
BUGGY_CODE = """
def get_user_orders(user_id):
    query = f"SELECT * FROM orders WHERE user_id = {user_id}"
    orders = db.execute(query)

    enriched = []
    for o in orders:
        product = db.execute(f"SELECT * FROM products WHERE id = {o.product_id}")
        enriched.append({"order": o, "product": product})

    return enriched
"""

supervisor = SequentialSupervisor([security_specialist, performance_specialist, style_specialist])
print(f"\nReviewing code:\n{BUGGY_CODE}")
print("\n=== Sequential review starting ===")
result = supervisor.run(f"Review this Python function: {BUGGY_CODE}")

print(f"\n=== FINAL OUTPUT ===")
print(f"Iterations used: {result['iterations']}")
print(f"\nFinal synthesized answer:\n{result['final_answer'][:500]}")
print(f"\n--- Individual specialist outputs ---")
for h in result["history"]:
    print(f"\n[{h['agent']} — cost: ${h['cost']:.6f}]")
    print(h["output"][:300])


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 3: Parallel Multi-Agent
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("SECTION 3: Parallel Multi-Agent (All at Once)")
print("=" * 70)


class ParallelSupervisor:
    """Runs all specialists in parallel, then synthesizes."""

    def __init__(self, specialists: list[SpecialistAgent], synthesizer_model: str = "gpt-4o-mini"):
        self.specialists = specialists
        self.synthesizer_model = synthesizer_model

    def run(self, query: str) -> dict:
        # Run all specialists in parallel
        with ThreadPoolExecutor(max_workers=len(self.specialists)) as executor:
            future_to_specialist = {
                executor.submit(s.execute, query): s for s in self.specialists
            }
            results = []
            for future, specialist in future_to_specialist.items():
                try:
                    results.append(future.result(timeout=30))
                except Exception as e:
                    results.append({"agent": specialist.name, "output": f"Error: {e}", "cost": 0})

        # Synthesize
        results_text = "\n\n".join(
            f"=== {r['agent']} ===\n{r['output']}" for r in results
        )
        synthesis_prompt = f"""Multiple specialist agents reviewed the same code.
Synthesize their reviews into a final cohesive review.

INDIVIDUAL REVIEWS:
{results_text}

Provide:
1. Summary of issues (prioritized by severity)
2. Specific fixes recommended
3. Overall verdict (safe to merge? needs changes?)"""

        synthesis = llm_call(synthesis_prompt, model=self.synthesizer_model, max_tokens=600)

        return {
            "final_answer": synthesis["text"],
            "specialist_results": results,
            "total_cost": sum(r.get("cost", 0) for r in results) + synthesis["cost"]
        }


# Run parallel review on same code
import time
print("\n=== Running parallel review ===")
parallel_sup = ParallelSupervisor([security_specialist, performance_specialist, style_specialist])
t1 = time.time()
result = parallel_sup.run(f"Review this Python function: {BUGGY_CODE}")
parallel_time = time.time() - t1
print(f"Parallel time: {parallel_time:.2f}s")
print(f"Total cost: ${result['total_cost']:.6f}")
print(f"\nSynthesized review:\n{result['final_answer'][:600]}")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 4: Customer Support Multi-Agent
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("SECTION 4: Customer Support Multi-Agent System")
print("=" * 70)


# Specialized customer support agents
billing_agent = SpecialistAgent(
    name="billing_agent",
    role="Handles payments, refunds, invoices, subscriptions",
    system_prompt="You are a billing specialist for FreshMart. Handle ONLY payment/refund issues. Be empathetic. If issue is technical, say 'Route to technical agent'."
)

technical_agent = SpecialistAgent(
    name="technical_agent",
    role="Handles app bugs, login issues, error messages",
    system_prompt="You are a technical support specialist. Handle ONLY technical issues (login, app bugs, errors). Walk users through troubleshooting."
)

shipping_agent = SpecialistAgent(
    name="shipping_agent",
    role="Handles delivery, tracking, returns",
    system_prompt="You are a shipping specialist. Handle ONLY shipping/delivery questions. Be helpful about logistics."
)


support_supervisor = SequentialSupervisor(
    [billing_agent, technical_agent, shipping_agent]
)

customer_queries = [
    "I want a refund for my last order #12345 — the food was cold",
    "I can't log into the app, it shows error 500",
    "Where is my package? It's been 3 days since order",
]

for query in customer_queries:
    print(f"\n💬 Customer: {query}")
    result = support_supervisor.run(query, max_iter=3)
    print(f"   ➜ Routed to: {[h['agent'] for h in result['history']]}")
    print(f"   ➜ Response: {result['final_answer'][:200]}...")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 5: Stats & Metrics
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("SECTION 5: Stats Across Agents")
print("=" * 70)

print("\nAgent call statistics:")
for agent in [security_specialist, performance_specialist, style_specialist,
              billing_agent, technical_agent, shipping_agent]:
    print(f"  {agent.name}: {agent.call_count} calls, total cost ${agent.total_cost:.6f}")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 6: Exercises
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("SECTION 6: EXERCISES")
print("=" * 70)
print("""
EASY:
1. Add a 4th specialist (e.g., test_reviewer). Test routing.
2. Add cost limits — supervisor refuses to delegate if budget exceeded.

MEDIUM:
3. Implement state sharing — specialists can read each other's outputs.
4. Build error recovery — if one specialist fails, retry with different one.

HARD:
5. Multi-level hierarchy:
   - Top supervisor → Mid-supervisors → Specialists
   - Like a real company structure
6. Add debate mechanism — 2 specialists disagree, judge agent picks winner.

PRO:
7. Build a "self-improving" multi-agent system:
   - Each agent rates its own confidence
   - Supervisor learns which agents are best for which tasks
   - Routing improves over time based on feedback
""")

if __name__ == "__main__":
    print("\n✅ Multi-agent supervisor — production-grade pattern mastered!")
