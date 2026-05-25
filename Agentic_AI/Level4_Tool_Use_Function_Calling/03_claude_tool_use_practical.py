"""
Level 4 — Doc 3: Anthropic Claude Tool Use (PRACTICAL)
========================================================
Topics:
  1. Claude tool schema (vs OpenAI)
  2. Full Claude tool use loop
  3. Tool results in user message
  4. Prompt caching with tools
  5. Parallel tool execution
  6. Error handling with is_error flag

Install: pip install anthropic python-dotenv
Run: python 03_claude_tool_use_practical.py
"""

import os
import json
from concurrent.futures import ThreadPoolExecutor
from typing import Optional
from dotenv import load_dotenv

load_dotenv()


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 1: Define Tools (same as before)
# ─────────────────────────────────────────────────────────────────────────────

def get_weather(city: str) -> dict:
    fake = {"Mumbai": (32, "sunny"), "Delhi": (28, "cloudy"), "Bangalore": (24, "rainy")}
    t, c = fake.get(city, (25, "unknown"))
    return {"city": city, "temp": t, "condition": c}


def calculator(expression: str) -> dict:
    try:
        result = eval(expression, {"__builtins__": {}}, {})
        return {"expression": expression, "result": result}
    except Exception as e:
        return {"error": str(e)}


TOOL_FUNCTIONS = {"get_weather": get_weather, "calculator": calculator}


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 2: Claude Tool Schema (Note Differences from OpenAI)
# ─────────────────────────────────────────────────────────────────────────────

print("=" * 70)
print("SECTION 2: Claude Tool Schema Format")
print("=" * 70)

# Claude uses `input_schema`, NOT `parameters`. No `function` wrapper.
CLAUDE_TOOLS = [
    {
        "name": "get_weather",
        "description": "Get current weather for a city. Returns temp and condition.",
        "input_schema": {
            "type": "object",
            "properties": {
                "city": {"type": "string", "description": "City name"}
            },
            "required": ["city"]
        }
    },
    {
        "name": "calculator",
        "description": "Safely evaluate a math expression like '5 + 3 * 2'.",
        "input_schema": {
            "type": "object",
            "properties": {
                "expression": {"type": "string", "description": "Math expression"}
            },
            "required": ["expression"]
        }
    }
]

print(f"Claude tools:\n{json.dumps(CLAUDE_TOOLS[0], indent=2)}")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 3: Full Claude Tool Use Loop
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("SECTION 3: Claude Tool Use Loop")
print("=" * 70)


def run_claude_agent(user_message: str, max_iter: int = 5) -> dict:
    if not os.getenv("ANTHROPIC_API_KEY"):
        return {"error": "no_api_key"}
    try:
        from anthropic import Anthropic
    except ImportError:
        return {"error": "install: pip install anthropic"}

    client = Anthropic()
    messages = [{"role": "user", "content": user_message}]
    trace = []

    for iteration in range(max_iter):
        try:
            response = client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=1024,
                tools=CLAUDE_TOOLS,
                messages=messages
            )
        except Exception as e:
            return {"error": str(e), "trace": trace}

        # Add assistant response to messages
        messages.append({"role": "assistant", "content": response.content})

        # Check if Claude is done
        if response.stop_reason != "tool_use":
            text_blocks = [b.text for b in response.content if b.type == "text"]
            return {"answer": "\n".join(text_blocks), "iterations": iteration + 1, "trace": trace}

        # Claude wants to use tools — execute them
        tool_results = []
        for block in response.content:
            if block.type == "tool_use":
                trace.append({"tool": block.name, "args": block.input})
                try:
                    result = TOOL_FUNCTIONS[block.name](**block.input)
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": json.dumps(result)
                    })
                except Exception as e:
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": f"Error: {e}",
                        "is_error": True
                    })

        # Send tool results back as user message (Claude's quirk!)
        messages.append({"role": "user", "content": tool_results})

    return {"error": "max_iterations_reached", "trace": trace}


# Test
result = run_claude_agent("What's the weather in Mumbai and what is 15 * 8?")
if "answer" in result:
    print(f"\nAnswer: {result['answer']}")
    print(f"Iterations: {result['iterations']}")
    for t in result["trace"]:
        print(f"  Tool: {t['tool']}({t['args']})")
else:
    print(f"Error: {result.get('error')}")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 4: Prompt Caching for Cost Savings
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("SECTION 4: Prompt Caching (90% Cost Savings)")
print("=" * 70)

LONG_SYSTEM_PROMPT = """You are an advanced AI assistant for FreshMart, an Indian grocery delivery service.

CONTEXT:
- FreshMart serves Mumbai, Delhi, Bangalore from 4 PM to 10 PM
- 50,000+ products across grocery, dairy, vegetables, electronics
- Customer base: 2 million users
- Average order value: ₹800

CAPABILITIES:
- Order tracking and status
- Returns and refunds processing
- Product recommendations
- Address and payment management
- Subscription management

RULES:
- Always greet by name when known
- Use Hinglish for warmth (yaar, theek hai)
- Never share other customers' data
- Refunds up to ₹500 — auto-approve; > ₹500 — escalate to human
- For technical issues: try 1 troubleshooting step before escalating
- Always end response with a follow-up question

[... imagine 1000 more tokens here ...]
"""


def claude_with_caching(user_message: str):
    if not os.getenv("ANTHROPIC_API_KEY"):
        return "Skipped (no API key)"
    try:
        from anthropic import Anthropic
        client = Anthropic()
        response = client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=200,
            system=[{
                "type": "text",
                "text": LONG_SYSTEM_PROMPT,
                "cache_control": {"type": "ephemeral"}  # ← Cache this
            }],
            messages=[{"role": "user", "content": user_message}]
        )
        # Check cache usage
        usage = response.usage
        print(f"Input tokens: {usage.input_tokens}")
        print(f"Cache creation: {getattr(usage, 'cache_creation_input_tokens', 0)}")
        print(f"Cache read: {getattr(usage, 'cache_read_input_tokens', 0)}")
        return response.content[0].text
    except Exception as e:
        return f"Error: {e}"


print("\n[First call — creates cache]")
print(claude_with_caching("What products do you have?"))
print("\n[Second call — should HIT cache]")
print(claude_with_caching("Tell me about your delivery hours."))


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 5: Parallel Tool Execution (Claude Style)
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("SECTION 5: Parallel Tool Execution")
print("=" * 70)


def claude_parallel_demo():
    if not os.getenv("ANTHROPIC_API_KEY"):
        return
    try:
        from anthropic import Anthropic
        client = Anthropic()

        response = client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=1024,
            tools=CLAUDE_TOOLS,
            messages=[{"role": "user", "content": "What's the weather in Mumbai, Delhi, AND Bangalore?"}]
        )

        # Extract all tool_use blocks
        tool_blocks = [b for b in response.content if b.type == "tool_use"]
        print(f"Claude requested {len(tool_blocks)} parallel tool calls")

        # Execute in parallel
        def run_one(block):
            return block.id, TOOL_FUNCTIONS[block.name](**block.input)

        with ThreadPoolExecutor() as ex:
            results = list(ex.map(run_one, tool_blocks))

        for tc_id, result in results:
            print(f"  {tc_id}: {result}")
    except Exception as e:
        print(f"Error: {e}")


claude_parallel_demo()


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 6: Error Handling with is_error Flag
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("SECTION 6: Error Handling with is_error Flag")
print("=" * 70)


def buggy_tool(x: int) -> dict:
    """A tool that always fails."""
    raise ValueError("This tool is intentionally broken")


def claude_with_failing_tool():
    if not os.getenv("ANTHROPIC_API_KEY"):
        return
    try:
        from anthropic import Anthropic
        client = Anthropic()

        tools = [{
            "name": "buggy_tool",
            "description": "A tool that does important work",
            "input_schema": {
                "type": "object",
                "properties": {"x": {"type": "integer"}},
                "required": ["x"]
            }
        }]

        messages = [{"role": "user", "content": "Use buggy_tool with x=5, then tell me what happened"}]

        response = client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=512,
            tools=tools,
            messages=messages
        )

        messages.append({"role": "assistant", "content": response.content})

        # Try to execute, fail, send error back with is_error=True
        tool_results = []
        for block in response.content:
            if block.type == "tool_use":
                try:
                    buggy_tool(**block.input)
                except Exception as e:
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": f"Error: {e}",
                        "is_error": True  # ← Tells Claude something failed
                    })

        if tool_results:
            messages.append({"role": "user", "content": tool_results})
            final = client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=512,
                tools=tools,
                messages=messages
            )
            text = next((b.text for b in final.content if b.type == "text"), "")
            print(f"Claude's response after error:\n{text}")
    except Exception as e:
        print(f"Error: {e}")


claude_with_failing_tool()


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 7: Compare Cost — Cached vs Uncached
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("SECTION 7: Cost Comparison — Caching Math")
print("=" * 70)

# Claude 3.5 Sonnet pricing (May 2026, may change):
# Input: $3 / 1M tokens
# Output: $15 / 1M tokens
# Cache write: $3.75 / 1M tokens (25% premium)
# Cache read: $0.30 / 1M tokens (90% off)

LONG_PROMPT_TOKENS = 1500  # System prompt length

def cost(tokens, rate_per_million):
    return tokens * rate_per_million / 1_000_000


print(f"\nScenario: Long system prompt ({LONG_PROMPT_TOKENS} tokens) used 100 times")
print(f"\n[Without caching]")
total_cost_uncached = 100 * cost(LONG_PROMPT_TOKENS, 3)
print(f"  Cost: ${total_cost_uncached:.4f}")

print(f"\n[With caching]")
first_call = cost(LONG_PROMPT_TOKENS, 3.75)  # Write cache
subsequent = 99 * cost(LONG_PROMPT_TOKENS, 0.30)  # Read cache
total_cached = first_call + subsequent
print(f"  First call (write): ${first_call:.4f}")
print(f"  Next 99 calls (read): ${subsequent:.4f}")
print(f"  Total: ${total_cached:.4f}")

savings = total_cost_uncached - total_cached
print(f"\n💰 Savings: ${savings:.4f} ({savings / total_cost_uncached * 100:.0f}%)")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 8: Exercises
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("SECTION 8: EXERCISES")
print("=" * 70)
print("""
EASY:
1. Port your OpenAI agent code to Claude. Note 3 differences.
2. Add 2 more tools, test parallel execution with Claude.

MEDIUM:
3. Implement prompt caching for a long system prompt. Measure cost savings.
4. Add cache_control to multiple positions (4 max). Test cache hit rates.

HARD:
5. Build an agent that uses extended thinking (Claude 3.7+).
   Compare to standard Claude on hard math problem.

6. Implement Computer Use:
   - screenshot tool
   - click(x, y) tool
   - type(text) tool
   Have Claude open a calculator app and compute something.

PRO:
7. Build a hybrid agent:
   - Use Claude for complex reasoning + tool use (with caching)
   - Use OpenAI for high-volume cheap classification
   - Route based on task complexity
""")

if __name__ == "__main__":
    print("\n✅ Claude tool use = OpenAI + caching + extended thinking superpowers!")
