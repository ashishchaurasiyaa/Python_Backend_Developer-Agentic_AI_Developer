"""
Level 4 — Doc 2: OpenAI Function Calling (PRACTICAL)
======================================================
Topics:
  1. tool_choice variants (auto, none, required, specific)
  2. Strict mode
  3. Parallel tool calls (N tools at once)
  4. Auto-schema generation
  5. Production loop with error handling
  6. Pydantic-validated tool args

Install: pip install openai pydantic python-dotenv
Run: python 02_openai_function_calling_practical.py
"""

import os
import json
import inspect
from concurrent.futures import ThreadPoolExecutor
from typing import get_type_hints, Optional
from dotenv import load_dotenv

load_dotenv()


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 1: Define Tools
# ─────────────────────────────────────────────────────────────────────────────

def get_weather(city: str) -> dict:
    """Get current weather for a city. Returns temp, condition, humidity."""
    fake = {"Mumbai": (32, "sunny"), "Delhi": (28, "cloudy"), "Bangalore": (24, "rainy")}
    t, c = fake.get(city, (25, "unknown"))
    return {"city": city, "temp": t, "condition": c}


def get_stock_price(symbol: str) -> dict:
    """Get current stock price for a ticker symbol."""
    fake = {"AAPL": 178.5, "GOOGL": 142.3, "TSLA": 245.8}
    return {"symbol": symbol, "price": fake.get(symbol, 0)}


def calculator(expression: str) -> dict:
    """Safely evaluate a math expression."""
    try:
        # In production: use ast.literal_eval or sympy
        result = eval(expression, {"__builtins__": {}}, {})
        return {"expression": expression, "result": result}
    except Exception as e:
        return {"error": str(e)}


TOOL_FUNCTIONS = {
    "get_weather": get_weather,
    "get_stock_price": get_stock_price,
    "calculator": calculator,
}


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 2: Auto-Generate Schemas from Python Functions
# ─────────────────────────────────────────────────────────────────────────────

print("=" * 70)
print("SECTION 2: Auto-Generate Schemas from Function Signatures")
print("=" * 70)


def python_func_to_openai_schema(func) -> dict:
    """Generate OpenAI tool schema from a Python function."""
    type_map = {str: "string", int: "integer", float: "number", bool: "boolean", dict: "object", list: "array"}
    hints = get_type_hints(func)
    sig = inspect.signature(func)

    properties = {}
    required = []
    for name, param in sig.parameters.items():
        param_type = hints.get(name, str)
        properties[name] = {"type": type_map.get(param_type, "string")}
        if param.default is inspect.Parameter.empty:
            required.append(name)

    return {
        "type": "function",
        "function": {
            "name": func.__name__,
            "description": (func.__doc__ or "").strip(),
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required
            }
        }
    }


SCHEMAS = [python_func_to_openai_schema(f) for f in TOOL_FUNCTIONS.values()]
print(f"Generated {len(SCHEMAS)} schemas from Python functions")
print(f"\nExample (get_weather):\n{json.dumps(SCHEMAS[0], indent=2)}")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 3: tool_choice Variants
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("SECTION 3: tool_choice Variants")
print("=" * 70)


def call_with_tool_choice(query: str, tool_choice) -> dict:
    """Test different tool_choice values."""
    if not os.getenv("OPENAI_API_KEY"):
        return {"error": "no_api_key"}
    from openai import OpenAI
    client = OpenAI()
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": query}],
        tools=SCHEMAS,
        tool_choice=tool_choice
    )
    msg = response.choices[0].message
    return {
        "finish_reason": response.choices[0].finish_reason,
        "content": msg.content,
        "tool_calls": [{"name": tc.function.name, "args": tc.function.arguments} for tc in (msg.tool_calls or [])]
    }


query = "What is 5+3?"

print(f"\nQuery: {query}\n")
print(f"[3.1 tool_choice='auto']")
print(json.dumps(call_with_tool_choice(query, "auto"), indent=2))

print(f"\n[3.2 tool_choice='none' — force text answer]")
print(json.dumps(call_with_tool_choice(query, "none"), indent=2))

print(f"\n[3.3 tool_choice='required' — must use a tool]")
print(json.dumps(call_with_tool_choice(query, "required"), indent=2))

print(f"\n[3.4 tool_choice=specific tool — force calculator]")
specific = {"type": "function", "function": {"name": "calculator"}}
print(json.dumps(call_with_tool_choice(query, specific), indent=2))


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 4: Parallel Tool Calls
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("SECTION 4: Parallel Tool Calls (Multiple Tools at Once)")
print("=" * 70)


def run_parallel_demo():
    if not os.getenv("OPENAI_API_KEY"):
        print("Skipped (no API key)")
        return
    from openai import OpenAI
    client = OpenAI()

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": "What's the weather in Mumbai, Delhi, AND Bangalore?"}],
        tools=SCHEMAS,
        parallel_tool_calls=True
    )

    tool_calls = response.choices[0].message.tool_calls or []
    print(f"LLM requested {len(tool_calls)} parallel tool calls")
    for tc in tool_calls:
        print(f"  → {tc.function.name}({tc.function.arguments})")

    # Execute in parallel
    def run_one(tc):
        name = tc.function.name
        args = json.loads(tc.function.arguments)
        return tc.id, TOOL_FUNCTIONS[name](**args)

    with ThreadPoolExecutor() as ex:
        results = list(ex.map(run_one, tool_calls))

    print(f"\nParallel results:")
    for tc_id, result in results:
        print(f"  {tc_id}: {result}")


run_parallel_demo()


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 5: Strict Mode
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("SECTION 5: Strict Mode (Guaranteed Schema Match)")
print("=" * 70)


def strict_mode_demo():
    if not os.getenv("OPENAI_API_KEY"):
        print("Skipped (no API key)")
        return
    from openai import OpenAI

    strict_schema = {
        "type": "function",
        "function": {
            "name": "send_email",
            "description": "Send an email",
            "strict": True,
            "parameters": {
                "type": "object",
                "properties": {
                    "to": {"type": "string"},
                    "subject": {"type": "string"},
                    "body": {"type": "string"}
                },
                "required": ["to", "subject", "body"],
                "additionalProperties": False
            }
        }
    }
    client = OpenAI()
    try:
        response = client.chat.completions.create(
            model="gpt-4o-2024-08-06",  # Strict needs newer model
            messages=[{"role": "user", "content": "Email john@example.com about lunch meeting"}],
            tools=[strict_schema],
            tool_choice={"type": "function", "function": {"name": "send_email"}}
        )
        tc = response.choices[0].message.tool_calls[0]
        print(f"Strict mode output (guaranteed schema):")
        print(json.dumps(json.loads(tc.function.arguments), indent=2))
    except Exception as e:
        print(f"Note: {e}")


strict_mode_demo()


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 6: Production Loop with Error Handling
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("SECTION 6: Production-Grade Loop with Error Handling")
print("=" * 70)


def run_production_agent(user_message: str, max_iterations: int = 10) -> dict:
    """Production-grade tool use loop with full error handling."""
    if not os.getenv("OPENAI_API_KEY"):
        return {"error": "no_api_key"}

    from openai import OpenAI
    client = OpenAI()
    messages = [
        {"role": "system", "content": "You are a helpful assistant. Use tools for data, math, or actions."},
        {"role": "user", "content": user_message}
    ]
    trace = []  # Audit log

    for iteration in range(max_iterations):
        try:
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=messages,
                tools=SCHEMAS,
                tool_choice="auto"
            )
        except Exception as e:
            return {"error": f"LLM call failed: {e}", "trace": trace}

        msg = response.choices[0].message

        if not msg.tool_calls:
            return {"answer": msg.content, "iterations": iteration + 1, "trace": trace}

        # LLM wants tools — add request to messages
        messages.append(msg.model_dump(exclude_none=True))

        for tc in msg.tool_calls:
            name = tc.function.name
            try:
                args = json.loads(tc.function.arguments)
            except json.JSONDecodeError as e:
                result = {"error": f"Invalid JSON args: {e}"}
            else:
                if name not in TOOL_FUNCTIONS:
                    result = {"error": f"Unknown tool: {name}"}
                else:
                    try:
                        result = TOOL_FUNCTIONS[name](**args)
                    except Exception as e:
                        result = {"error": f"Tool execution failed: {e}"}

            trace.append({"tool": name, "args": args if isinstance(args, dict) else None, "result": result})

            messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": json.dumps(result)
            })

    return {"error": "max_iterations_reached", "trace": trace}


result = run_production_agent("Calculate (15 * 8) + the weather temperature in Mumbai")
print(f"\nFinal answer: {result.get('answer', result.get('error'))}")
print(f"Iterations: {result.get('iterations', 'N/A')}")
print(f"Tool calls made: {len(result.get('trace', []))}")
for t in result.get("trace", []):
    print(f"  {t['tool']}({t['args']}) → {t['result']}")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 7: Pydantic-Validated Tool Args
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("SECTION 7: Validate Tool Args with Pydantic")
print("=" * 70)


def pydantic_validation_demo():
    try:
        from pydantic import BaseModel, Field, ValidationError

        class WeatherArgs(BaseModel):
            city: str = Field(min_length=1, max_length=50, description="City name")

        # LLM-provided args (may be malformed)
        good_args = {"city": "Mumbai"}
        bad_args_empty = {"city": ""}
        bad_args_missing = {}

        for args in [good_args, bad_args_empty, bad_args_missing]:
            try:
                validated = WeatherArgs(**args)
                print(f"  ✓ Valid: {args} → {validated.model_dump()}")
            except ValidationError as e:
                print(f"  ✗ Invalid: {args} → {e.errors()[0]['msg']}")

    except ImportError:
        print("Install: pip install pydantic")


pydantic_validation_demo()


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 8: Exercises
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("SECTION 8: EXERCISES")
print("=" * 70)
print("""
EASY:
1. Add 3 more tools (search_news, set_reminder, get_calendar). Test routing.
2. Try tool_choice="none" — verify LLM gives text answer even with tools available.

MEDIUM:
3. Implement parallel execution with timeouts per tool (use ThreadPoolExecutor + timeout).
4. Build a "tool call validator" — uses Pydantic to validate args BEFORE calling function.

HARD:
5. Implement caching: same tool + args → cached result. TTL configurable.
6. Add structured logging: each tool call gets trace_id, span_id, latency tracked.

PRO:
7. Build a "tool versioning" system:
   - Multiple versions of same tool
   - LLM picks based on capability
   - Track which version succeeded most
""")

if __name__ == "__main__":
    print("\n✅ OpenAI function calling — production patterns covered!")
