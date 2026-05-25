"""
Level 4 — Doc 7: The Tool Use Loop Deep (PRACTICAL)
=====================================================
Topics:
  1. Basic loop with max_iterations
  2. Stuck detection
  3. State management class
  4. Context window truncation
  5. Cost + budget tracking
  6. Force final answer
  7. Production-grade loop

Install: pip install openai tiktoken python-dotenv
Run: python 07_tool_use_loop_practical.py
"""

import os
import json
import time
from typing import Optional
from dotenv import load_dotenv

load_dotenv()


# ─────────────────────────────────────────────────────────────────────────────
# Mock tools
# ─────────────────────────────────────────────────────────────────────────────

def get_weather(city: str) -> dict:
    return {"city": city, "temp": 28, "condition": "sunny"}


def calculator(expr: str) -> dict:
    try:
        return {"result": eval(expr, {"__builtins__": {}}, {})}
    except Exception as e:
        return {"error": str(e)}


TOOL_FUNCTIONS = {"get_weather": get_weather, "calculator": calculator}

TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "Get weather for a city",
            "parameters": {
                "type": "object",
                "properties": {"city": {"type": "string"}},
                "required": ["city"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "calculator",
            "description": "Calculate math",
            "parameters": {
                "type": "object",
                "properties": {"expr": {"type": "string"}},
                "required": ["expr"]
            }
        }
    }
]


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 1: AgentState Class
# ─────────────────────────────────────────────────────────────────────────────

print("=" * 70)
print("SECTION 1: AgentState Management")
print("=" * 70)


class AgentState:
    def __init__(self, system_prompt: str = "You are a helpful agent."):
        self.messages: list = [{"role": "system", "content": system_prompt}]
        self.iteration: int = 0
        self.start_time: float = time.time()
        self.tools_used: list = []
        self.cost: float = 0.0

    def add_message(self, msg: dict):
        self.messages.append(msg)

    def add_tool_call(self, name: str, args: dict, result):
        self.tools_used.append({
            "iteration": self.iteration,
            "tool": name,
            "args": args,
            "result_summary": str(result)[:150]
        })

    def summary(self) -> dict:
        return {
            "iterations": self.iteration,
            "elapsed_seconds": round(time.time() - self.start_time, 2),
            "messages": len(self.messages),
            "tools_used": len(self.tools_used),
            "tool_breakdown": [t["tool"] for t in self.tools_used],
            "cost_dollars": round(self.cost, 6),
        }


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 2: Stuck Detection
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("SECTION 2: Stuck Pattern Detection")
print("=" * 70)


def is_stuck(messages: list, lookback: int = 4) -> bool:
    """Detect if LLM is repeating the same tool calls."""
    recent_calls = []
    for msg in messages[-lookback:]:
        if msg.get("role") == "assistant" and msg.get("tool_calls"):
            for tc in msg["tool_calls"]:
                if isinstance(tc, dict):
                    key = (tc["function"]["name"], tc["function"]["arguments"])
                else:
                    key = (tc.function.name, tc.function.arguments)
                recent_calls.append(key)
    if len(recent_calls) < 2:
        return False
    return len(recent_calls) != len(set(recent_calls))


# Test
fake_messages = [
    {"role": "user", "content": "weather Mumbai"},
    {"role": "assistant", "tool_calls": [{"function": {"name": "get_weather", "arguments": '{"city":"Mumbai"}'}}]},
    {"role": "tool", "content": "..."},
    {"role": "assistant", "tool_calls": [{"function": {"name": "get_weather", "arguments": '{"city":"Mumbai"}'}}]},  # Same call!
]
print(f"is_stuck(repeating calls)? {is_stuck(fake_messages)}")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 3: Context Window Truncation
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("SECTION 3: Context Window Truncation")
print("=" * 70)


def count_tokens_rough(text: str) -> int:
    """Quick token estimate."""
    return len(text) // 4


def count_messages_tokens(messages: list) -> int:
    total = 0
    for m in messages:
        content = m.get("content")
        if isinstance(content, str):
            total += count_tokens_rough(content)
        else:
            total += count_tokens_rough(str(content))
    return total


def truncate_messages(messages: list, max_tokens: int = 5000) -> list:
    """Keep system + last messages within token budget."""
    if not messages:
        return messages
    system = [m for m in messages if m.get("role") == "system"]
    other = [m for m in messages if m.get("role") != "system"]

    while count_messages_tokens(system + other) > max_tokens and len(other) > 2:
        other.pop(0)  # Drop oldest non-system

    return system + other


# Demo
long_messages = [{"role": "system", "content": "You are helpful"}] + [
    {"role": "user", "content": "x" * 1000} for _ in range(20)
]
print(f"Before: {len(long_messages)} msgs, ~{count_messages_tokens(long_messages)} tokens")
truncated = truncate_messages(long_messages, max_tokens=3000)
print(f"After:  {len(truncated)} msgs, ~{count_messages_tokens(truncated)} tokens")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 4: Cost-Tracking Loop
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("SECTION 4: Cost + Budget Tracking")
print("=" * 70)


def call_llm_with_cost(messages, tools=None, model="gpt-4o-mini"):
    """LLM call returning cost."""
    if not os.getenv("OPENAI_API_KEY"):
        return {"text": "[NO_API_KEY]", "tool_calls": None, "cost": 0}
    try:
        from openai import OpenAI
        client = OpenAI()
        kwargs = {"model": model, "messages": messages, "max_tokens": 500}
        if tools:
            kwargs["tools"] = tools
        resp = client.chat.completions.create(**kwargs)
        usage = resp.usage
        # gpt-4o-mini pricing
        cost = (usage.prompt_tokens * 0.15 + usage.completion_tokens * 0.60) / 1_000_000
        msg = resp.choices[0].message
        return {
            "text": msg.content,
            "tool_calls": msg.tool_calls,
            "cost": cost,
            "tokens": (usage.prompt_tokens, usage.completion_tokens),
            "raw_message": msg
        }
    except Exception as e:
        return {"text": f"[Error: {e}]", "tool_calls": None, "cost": 0}


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 5: Production-Grade Loop
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("SECTION 5: Production-Grade Loop")
print("=" * 70)


def production_loop(
    user_message: str,
    max_iter: int = 10,
    timeout_sec: int = 60,
    budget: float = 0.10,
):
    state = AgentState()
    state.add_message({"role": "user", "content": user_message})

    for state.iteration in range(max_iter):
        # Safety checks
        elapsed = time.time() - state.start_time
        if elapsed > timeout_sec:
            return {"status": "timeout", "answer": None, "state": state.summary()}
        if state.cost > budget:
            return {"status": "budget_exceeded", "answer": None, "state": state.summary()}

        # Truncate if needed
        state.messages = truncate_messages(state.messages)

        # Stuck?
        if state.iteration > 2 and is_stuck(state.messages):
            return {"status": "stuck", "answer": "I'm having trouble with this query.", "state": state.summary()}

        # Last iteration: force answer (no tools)
        tools_to_use = TOOL_SCHEMAS if state.iteration < max_iter - 1 else None

        # LLM call
        response = call_llm_with_cost(state.messages, tools_to_use)
        state.cost += response["cost"]

        # No tools → final answer
        if not response["tool_calls"]:
            return {
                "status": "success",
                "answer": response["text"],
                "state": state.summary()
            }

        # Add LLM's response with tool calls
        state.add_message(response["raw_message"].model_dump(exclude_none=True))

        # Execute tools
        for tc in response["tool_calls"]:
            name = tc.function.name
            args = json.loads(tc.function.arguments)
            try:
                result = TOOL_FUNCTIONS[name](**args)
            except Exception as e:
                result = {"error": str(e)}
            state.add_tool_call(name, args, result)
            state.add_message({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": json.dumps(result)
            })

    return {
        "status": "max_iterations",
        "answer": None,
        "state": state.summary()
    }


# Run
print("\n[Test query 1: Simple]")
result = production_loop("What's the weather in Mumbai?")
print(f"  Status: {result['status']}")
print(f"  Answer: {result.get('answer')}")
print(f"  Stats: {result['state']}")

print("\n[Test query 2: Multi-step]")
result = production_loop("What's 15 * 8 plus the temperature of Delhi?")
print(f"  Status: {result['status']}")
print(f"  Answer: {result.get('answer')}")
print(f"  Stats: {result['state']}")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 6: Exercises
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("SECTION 6: EXERCISES")
print("=" * 70)
print("""
EASY:
1. Add logging to every loop iteration. Track what LLM decided at each step.
2. Test loop with intentionally bad query (e.g., "use calculator 100 times"). Verify max_iter triggers.

MEDIUM:
3. Implement summarization-based context management (when > 10k tokens, summarize old).
4. Add streaming events — yield events as loop progresses.

HARD:
5. Build retry logic — if LLM call fails (rate limit), wait + retry with exponential backoff.
6. Implement multi-agent loop — supervisor delegates to specialist agents.

PRO:
7. Build a complete observability stack:
   - Each iteration logged with: messages, tool calls, latency, cost
   - Dashboard showing P50/P99 iterations per query
   - Alert when budget approaching limit
""")

if __name__ == "__main__":
    print("\n✅ Production loop = safety + observability + cost control!")
