"""
Level 4 — Doc 1: What is Tool Use? (PRACTICAL)
================================================
Topics:
  1. Define a simple tool
  2. Tool schema (JSON Schema format)
  3. The full tool use loop (manual, no abstractions)
  4. Inspect what LLM returns when calling a tool
  5. Pass result back to LLM
  6. Multiple tools — see LLM route

Install: pip install openai python-dotenv
Run: python 01_what_is_tool_use_practical.py
"""

import os
import json
from typing import Optional
from dotenv import load_dotenv

load_dotenv()


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 1: Define Real Python Functions (the "tools")
# ─────────────────────────────────────────────────────────────────────────────

print("=" * 70)
print("SECTION 1: Define Python Functions That Will Be Tools")
print("=" * 70)


def get_weather(city: str) -> dict:
    """Mock weather API."""
    # In production, this calls a real weather API
    fake_data = {
        "Mumbai": {"temp": 32, "condition": "sunny", "humidity": 78},
        "Delhi": {"temp": 28, "condition": "cloudy", "humidity": 65},
        "Bangalore": {"temp": 24, "condition": "rainy", "humidity": 85},
    }
    return fake_data.get(city, {"temp": 25, "condition": "unknown", "city": city})


def get_stock_price(symbol: str) -> dict:
    """Mock stock price API."""
    fake_prices = {
        "AAPL": 178.50,
        "GOOGL": 142.30,
        "TSLA": 245.80,
    }
    return {"symbol": symbol, "price": fake_prices.get(symbol, 0), "currency": "USD"}


def get_time(timezone: str = "UTC") -> dict:
    """Get current time."""
    from datetime import datetime
    return {"timezone": timezone, "time": datetime.now().isoformat()}


# Quick test
print("Tools defined:")
print(f"  get_weather('Mumbai') → {get_weather('Mumbai')}")
print(f"  get_stock_price('AAPL') → {get_stock_price('AAPL')}")
print(f"  get_time('IST') → {get_time('IST')}")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 2: Tool Schemas — How LLM "Sees" Your Tools
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("SECTION 2: Tool Schemas (OpenAI Format)")
print("=" * 70)

TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "Get current weather conditions for a city. Returns temperature, condition, and humidity.",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {
                        "type": "string",
                        "description": "Name of the city, e.g., 'Mumbai', 'Delhi'"
                    }
                },
                "required": ["city"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_stock_price",
            "description": "Get the current stock price for a symbol. Use for stock-related queries.",
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol": {
                        "type": "string",
                        "description": "Stock ticker symbol, e.g., 'AAPL', 'TSLA'"
                    }
                },
                "required": ["symbol"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_time",
            "description": "Get the current date and time, optionally in a specific timezone.",
            "parameters": {
                "type": "object",
                "properties": {
                    "timezone": {
                        "type": "string",
                        "description": "Timezone name, e.g., 'UTC', 'IST', 'PST'. Defaults to UTC."
                    }
                },
                "required": []
            }
        }
    }
]

print(f"Defined {len(TOOL_SCHEMAS)} tool schemas.")
print(f"Example schema (get_weather):\n{json.dumps(TOOL_SCHEMAS[0], indent=2)}")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 3: The Full Tool Use Loop
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("SECTION 3: Full Tool Use Loop (Manual, Step-by-Step)")
print("=" * 70)


# Map function names → Python functions
TOOL_FUNCTIONS = {
    "get_weather": get_weather,
    "get_stock_price": get_stock_price,
    "get_time": get_time,
}


def run_tool_use_loop(user_message: str, max_iterations: int = 5) -> str:
    """The complete tool use loop, no abstractions."""
    if not os.getenv("OPENAI_API_KEY"):
        return "[NO_API_KEY]"

    from openai import OpenAI
    client = OpenAI()

    messages = [
        {"role": "system", "content": "You are a helpful assistant. Use tools when needed for real-time data."},
        {"role": "user", "content": user_message}
    ]

    for iteration in range(max_iterations):
        print(f"\n[Iteration {iteration + 1}]")

        # Send messages + tools to LLM
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            tools=TOOL_SCHEMAS,
            tool_choice="auto"  # Let LLM decide whether to call a tool
        )

        msg = response.choices[0].message
        finish_reason = response.choices[0].finish_reason

        # Did LLM ask to call a tool?
        if msg.tool_calls:
            print(f"  LLM requests tool calls: {len(msg.tool_calls)}")
            # Add LLM's request to messages
            messages.append({
                "role": "assistant",
                "content": msg.content,
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {"name": tc.function.name, "arguments": tc.function.arguments}
                    }
                    for tc in msg.tool_calls
                ]
            })

            # Execute each tool call
            for tool_call in msg.tool_calls:
                func_name = tool_call.function.name
                func_args = json.loads(tool_call.function.arguments)
                print(f"    → Calling {func_name}({func_args})")

                if func_name in TOOL_FUNCTIONS:
                    result = TOOL_FUNCTIONS[func_name](**func_args)
                else:
                    result = {"error": f"Unknown tool: {func_name}"}

                print(f"    ← Result: {result}")

                # Append tool result to messages
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": json.dumps(result)
                })

            # Loop back — let LLM see results and continue
            continue

        # No tool calls → LLM has final answer
        print(f"  LLM final answer: {msg.content}")
        return msg.content

    return "[Max iterations reached]"


# Run examples
queries = [
    "What's the weather in Mumbai right now?",
    "What's Apple stock price?",
    "What's the time and weather in Delhi?",  # Multi-tool!
]

for q in queries:
    print(f"\n{'=' * 50}")
    print(f"USER: {q}")
    answer = run_tool_use_loop(q)
    print(f"\nFINAL ANSWER: {answer}")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 4: Inspect LLM Response Structure
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("SECTION 4: Inspect Raw LLM Tool-Call Response")
print("=" * 70)


def inspect_tool_call_response():
    if not os.getenv("OPENAI_API_KEY"):
        return
    from openai import OpenAI
    client = OpenAI()
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": "What's the weather in Mumbai?"}],
        tools=TOOL_SCHEMAS
    )
    msg = response.choices[0].message
    print(f"finish_reason: {response.choices[0].finish_reason}")
    print(f"content: {msg.content}")
    print(f"tool_calls: {msg.tool_calls}")
    if msg.tool_calls:
        for tc in msg.tool_calls:
            print(f"  Tool call ID: {tc.id}")
            print(f"  Function: {tc.function.name}")
            print(f"  Arguments (raw string): {tc.function.arguments}")
            print(f"  Arguments (parsed): {json.loads(tc.function.arguments)}")


inspect_tool_call_response()


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 5: What Happens Without Tools? (Comparison)
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("SECTION 5: Without Tools, LLM Can Only Guess")
print("=" * 70)


def no_tools_call(query: str) -> str:
    if not os.getenv("OPENAI_API_KEY"):
        return "[NO_API_KEY]"
    from openai import OpenAI
    client = OpenAI()
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are a helpful assistant. You have NO real-time data access."},
            {"role": "user", "content": query}
        ]
    )
    return response.choices[0].message.content


query = "What's the current weather in Mumbai?"
print(f"\nQuery: {query}")
print(f"\nWithout tools:\n{no_tools_call(query)}")
print(f"\nWith tools:\n{run_tool_use_loop(query)}")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 6: Exercises
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("SECTION 6: EXERCISES")
print("=" * 70)
print("""
EASY:
1. Add a 4th tool: get_news(topic) — mock news API. Test routing.
2. Run the loop with a query that needs NO tools (e.g., "What is 2+2?").
   Verify LLM doesn't call any tool.

MEDIUM:
3. Add error handling: when tool raises exception, send error message back to LLM.
4. Add tool call logging (which tools used, how often, success/failure).

HARD:
5. Build a 'tool registry' — auto-generate schemas from Python function signatures + docstrings.
   Use `inspect` module + Pydantic.

6. Implement parallel tool calls — LLM may request 2-3 tools simultaneously.
   Execute them in parallel using ThreadPoolExecutor.

PRO:
7. Build a "tool use trace" — full audit log of:
   - User query
   - LLM tool selection reasoning
   - Tool calls with args + results
   - Final answer
   Export as JSON for debugging.
""")

if __name__ == "__main__":
    print("\n✅ Tool use = the bridge from LLM to real world. Master this!")
