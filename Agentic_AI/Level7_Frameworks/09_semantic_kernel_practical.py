"""
Level 7 — Doc 9: Semantic Kernel (PRACTICAL)
==============================================
Tries the real `semantic-kernel` SDK first; falls back to a manual
reimplementation of the same core concepts if it's not installed, so this
still runs and teaches the right thing either way — same philosophy as the
theory doc's own "Swarm without the library" approach elsewhere in Level 6.

Topics covered:
  1. Kernel as a DI container (not "the agent") — register 2 services, route by service_id
  2. Native plugin -> auto-generated JSON schema (mirrors @kernel_function)
  3. Multi-model routing pattern — cheap model classifies, expensive model generates
  4. Auto function calling loop

Install (optional, real SDK): pip install semantic-kernel
Falls back to: pip install openai python-dotenv (already needed elsewhere)

Run: python 09_semantic_kernel_practical.py
"""

import os
import json
from typing import Callable
from dotenv import load_dotenv

load_dotenv()
HAS_KEY = bool(os.getenv("OPENAI_API_KEY"))

try:
    import semantic_kernel  # noqa: F401
    HAS_SK = True
except ImportError:
    HAS_SK = False


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 1: Kernel = DI Container, Not "The Agent"
# ─────────────────────────────────────────────────────────────────────────────

print("=" * 70)
print("SECTION 1: Kernel as a DI Container")
print("=" * 70)

if not HAS_SK:
    print("\n  [semantic-kernel not installed — demonstrating the CONCEPT with a")
    print("   minimal manual kernel. `pip install semantic-kernel` for the real SDK.]")


class MiniKernel:
    """Everything SK's Kernel really is: a registry you resolve services/functions
    FROM. The kernel itself does no work — it's a lookup table + invoker."""

    def __init__(self):
        self.services: dict[str, str] = {}   # service_id -> model name
        self.plugins: dict[str, dict] = {}    # plugin_name -> {func_name: callable}

    def add_service(self, model: str, service_id: str):
        self.services[service_id] = model

    def add_plugin(self, plugin_name: str, functions: dict):
        self.plugins[plugin_name] = functions

    def invoke(self, plugin_name: str, function_name: str, service_id: str, **kwargs):
        model = self.services.get(service_id, "unknown-model")
        fn = self.plugins[plugin_name][function_name]
        result = fn(**kwargs)
        return f"[via {service_id}={model}] {result}"


kernel = MiniKernel()
kernel.add_service("gpt-4o-mini", service_id="fast")   # cheap tier
kernel.add_service("gpt-4o", service_id="smart")        # expensive tier

print(f"\n  Registered services: {kernel.services}")
print("  Same kernel, two models registered — this is the multi-model-routing")
print("  pattern the doc calls out: register once, choose per-call via service_id.")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 2: Native Plugin -> Auto-Generated Schema
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("SECTION 2: Native Plugin Schema Generation")
print("=" * 70)


def get_order_status(order_id: str) -> str:
    """Get the current delivery status of an order by its order ID."""
    fake_db = {"ORD-4521": "shipped", "ORD-9001": "processing"}
    return f"Order {order_id} is {fake_db.get(order_id, 'not found')}"


def function_to_schema(fn: Callable, plugin_name: str) -> dict:
    """Mirrors what @kernel_function + Annotated does under the hood — reads
    the function signature/docstring and builds a JSON schema an LLM can call.
    This is the SAME idea FastAPI uses for OpenAPI, just for tool schemas."""
    import inspect
    sig = inspect.signature(fn)
    properties = {name: {"type": "string", "description": f"parameter: {name}"} for name in sig.parameters}
    required = [name for name, p in sig.parameters.items() if p.default is inspect.Parameter.empty]
    return {
        "type": "function",
        "function": {
            "name": f"{plugin_name}-{fn.__name__}",   # SK namespaces: plugin-function, not flat
            "description": fn.__doc__ or "",
            "parameters": {"type": "object", "properties": properties, "required": required},
        },
    }


schema = function_to_schema(get_order_status, plugin_name="orders")
print(f"\n  Generated schema for get_order_status:")
print(json.dumps(schema, indent=2))
print("\n  Function name becomes 'orders-get_order_status' — namespaced by plugin,")
print("  not flat like most other frameworks. At 40+ tools this avoids collisions.")

kernel.add_plugin("orders", {"get_order_status": get_order_status})
result = kernel.invoke("orders", "get_order_status", service_id="fast", order_id="ORD-4521")
print(f"\n  kernel.invoke result: {result}")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 3: Multi-Model Routing — Cheap Classifies, Expensive Generates
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("SECTION 3: Multi-Model Routing (the actual cost-control pattern)")
print("=" * 70)


def llm_call(prompt: str, model: str) -> str:
    if not HAS_KEY:
        return f"[NO_API_KEY — would call {model}]"
    from openai import OpenAI
    client = OpenAI()
    resp = client.chat.completions.create(model=model, messages=[{"role": "user", "content": prompt}], max_tokens=60)
    return resp.choices[0].message.content


ticket = "My payment failed twice and I'm being charged for a subscription I cancelled last month."

classification = llm_call(f"Classify this support ticket in one word (billing/technical/general): {ticket}", model=kernel.services["fast"])
print(f"\n  [service_id='fast', model={kernel.services['fast']}] Classification: {classification}")

response = llm_call(f"Write a helpful, empathetic reply to this billing complaint: {ticket}", model=kernel.services["smart"])
print(f"  [service_id='smart', model={kernel.services['smart']}] Reply: {response}")

print("\n  Same kernel, two service_ids picked per-call based on task difficulty —")
print("  classification doesn't need the expensive model, the customer-facing reply does.")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 4: Auto Function Calling Loop
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("SECTION 4: Auto Function Calling")
print("=" * 70)


def auto_invoke(user_message: str, plugin_name: str, functions: dict, service_id: str, max_iterations: int = 3) -> str:
    if not HAS_KEY:
        return "[NO_API_KEY — auto function calling needs a live model to decide when to call a tool]"
    from openai import OpenAI
    client = OpenAI()

    tools = [function_to_schema(fn, plugin_name) for fn in functions.values()]
    messages = [{"role": "user", "content": user_message}]

    for _ in range(max_iterations):
        resp = client.chat.completions.create(model=kernel.services[service_id], messages=messages, tools=tools, max_tokens=150)
        msg = resp.choices[0].message
        if not msg.tool_calls:
            return msg.content
        messages.append({"role": "assistant", "content": msg.content, "tool_calls": msg.tool_calls})
        for tc in msg.tool_calls:
            fn_name = tc.function.name.split("-")[-1]  # strip plugin- prefix
            args = json.loads(tc.function.arguments)
            result = functions[fn_name](**args)
            messages.append({"role": "tool", "tool_call_id": tc.id, "content": result})
    return "[max iterations reached]"


answer = auto_invoke("What's the status of order ORD-9001?", plugin_name="orders", functions={"get_order_status": get_order_status}, service_id="fast")
print(f"\n  {answer}")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 5: Exercises
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("SECTION 5: EXERCISES")
print("=" * 70)
print("""
EASY:
1. Add a second plugin function `cancel_order(order_id)` to the orders plugin.
   Regenerate its schema and confirm the namespaced name is 'orders-cancel_order'.

MEDIUM:
2. If you have `semantic-kernel` installed: rewrite Section 1-2 using the
   REAL Kernel, OpenAIChatCompletion, and @kernel_function decorator. Compare
   the generated schema against function_to_schema()'s manual version.

HARD:
3. Add a second plugin ("billing") with its own functions, and extend
   auto_invoke() to route tool calls to the correct plugin's function dict
   based on the plugin-name prefix in the tool call.

PRO:
4. Implement the OpenAPI-import pattern from the doc conceptually: write a
   function that takes a tiny fake OpenAPI spec (2-3 endpoints) and generates
   tool schemas from it automatically, the way `add_plugin_from_openapi` does.
""")

if __name__ == "__main__":
    print("\nDone. Next: 10_a2a_protocol_practical.py")
