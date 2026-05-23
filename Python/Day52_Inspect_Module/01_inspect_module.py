"""
DAY 52 — inspect Module: Introspection for Framework Builders
Architecture Level: Senior Python Backend + Agentic AI

WHY THIS MATTERS:
  FastAPI uses inspect to auto-discover route parameters and types.
  LangChain uses inspect to auto-generate tool schemas from function signatures.
  Pydantic uses inspect to build validators.
  Every decorator library uses inspect.
  Senior devs who build reusable utilities need this.
"""

import asyncio
import inspect
import textwrap
from typing import Any, Callable, Optional, TypeVar, get_type_hints

F = TypeVar("F", bound=Callable)


# ═══════════════════════════════════════════════════════
# PART A: Inspect Function Signatures
# ═══════════════════════════════════════════════════════

# ─────────────────────────────────────────────
# 1. inspect.signature — full parameter info
# ─────────────────────────────────────────────

def create_user(
    name: str,
    email: str,
    age: int = 0,
    *,
    role: str = "user",
    active: bool = True,
) -> dict:
    return {"name": name, "email": email, "age": age, "role": role, "active": active}


sig = inspect.signature(create_user)
print("=== Function Signature ===")
print(f"Signature: {sig}")

for param_name, param in sig.parameters.items():
    has_default = param.default is not inspect.Parameter.empty
    kind = param.kind.name
    annotation = param.annotation if param.annotation is not inspect.Parameter.empty else "no annotation"
    print(f"  {param_name}: kind={kind}, type={annotation}, default={has_default}")


# ─────────────────────────────────────────────
# 2. Parameter kinds
# ─────────────────────────────────────────────

# inspect.Parameter.POSITIONAL_ONLY       → def f(x, /, y)  — x is positional only
# inspect.Parameter.POSITIONAL_OR_KEYWORD → def f(x, y)     — normal params
# inspect.Parameter.VAR_POSITIONAL        → *args
# inspect.Parameter.KEYWORD_ONLY         → def f(*, x)      — after *
# inspect.Parameter.VAR_KEYWORD          → **kwargs


def example(pos_only: int, /, normal: str, *args, kw_only: bool = False, **kwargs):
    pass

sig2 = inspect.signature(example)
for name, p in sig2.parameters.items():
    print(f"  {name:12} → {p.kind.name}")


# ─────────────────────────────────────────────
# 3. get_type_hints — resolves string annotations (PEP 563)
# ─────────────────────────────────────────────

from __future__ import annotations  # noqa: E402 — makes all annotations strings

def process_items(items: list[str], limit: int = 10) -> dict[str, Any]:
    return {}

# sig.parameters has string annotations when from __future__ import annotations
# get_type_hints resolves them to actual types
hints = get_type_hints(process_items)
print(f"\nType hints (resolved): {hints}")


# ═══════════════════════════════════════════════════════
# PART B: Building Auto-Schema Tools (LangChain pattern)
# ═══════════════════════════════════════════════════════

# ─────────────────────────────────────────────
# 1. Auto-generate JSON schema from function signature
#    This is exactly how LangChain/LangGraph creates tool schemas
# ─────────────────────────────────────────────

PYTHON_TO_JSON_TYPE = {
    int:   "integer",
    float: "number",
    str:   "string",
    bool:  "boolean",
    list:  "array",
    dict:  "object",
}


def function_to_tool_schema(fn: Callable) -> dict:
    """
    Convert a Python function into an OpenAI/Claude tool schema.
    Used by LangChain @tool decorator internally.
    """
    sig = inspect.signature(fn)
    hints = get_type_hints(fn)
    doc = inspect.getdoc(fn) or ""

    properties = {}
    required = []

    for name, param in sig.parameters.items():
        if name == "return":
            continue

        annotation = hints.get(name, Any)
        json_type = PYTHON_TO_JSON_TYPE.get(annotation, "string")

        prop: dict[str, Any] = {"type": json_type}

        # Extract field description from docstring (simple heuristic)
        for line in doc.splitlines():
            if line.strip().startswith(f"{name}:"):
                prop["description"] = line.split(":", 1)[1].strip()
                break

        properties[name] = prop

        if param.default is inspect.Parameter.empty:
            required.append(name)

    return_type = hints.get("return", Any)

    return {
        "name": fn.__name__,
        "description": doc.split("\n")[0] if doc else "",
        "parameters": {
            "type": "object",
            "properties": properties,
            "required": required,
        },
        "return_type": PYTHON_TO_JSON_TYPE.get(return_type, "object"),
    }


def search_web(query: str, max_results: int = 5) -> list:
    """Search the web and return results.

    query: The search query string
    max_results: Maximum number of results to return
    """
    return []


def calculate_price(base_price: float, quantity: int, discount: float = 0.0) -> float:
    """Calculate final price with discount.

    base_price: Unit price before discount
    quantity: Number of units
    discount: Discount rate between 0.0 and 1.0
    """
    return base_price * quantity * (1 - discount)


import json
schema = function_to_tool_schema(search_web)
print(f"\n=== Auto-generated Tool Schema ===")
print(json.dumps(schema, indent=2))

schema2 = function_to_tool_schema(calculate_price)
print(json.dumps(schema2, indent=2))


# ═══════════════════════════════════════════════════════
# PART C: inspect for Decorator Utilities
# ═══════════════════════════════════════════════════════

# ─────────────────────────────────────────────
# 1. Check if a function is async — critical for decorators
# ─────────────────────────────────────────────

def smart_decorator(fn: F) -> F:
    """Decorator that works on BOTH sync and async functions."""
    import functools

    if inspect.iscoroutinefunction(fn):
        @functools.wraps(fn)
        async def async_wrapper(*args, **kwargs):
            print(f"[LOG] async call: {fn.__name__}")
            result = await fn(*args, **kwargs)
            print(f"[LOG] async done: {fn.__name__}")
            return result
        return async_wrapper  # type: ignore
    else:
        @functools.wraps(fn)
        def sync_wrapper(*args, **kwargs):
            print(f"[LOG] sync call: {fn.__name__}")
            result = fn(*args, **kwargs)
            print(f"[LOG] sync done: {fn.__name__}")
            return result
        return sync_wrapper  # type: ignore


@smart_decorator
def sync_task(x: int) -> int:
    return x * 2

@smart_decorator
async def async_task(x: int) -> int:
    await asyncio.sleep(0)
    return x * 2

print("\n=== Smart Decorator ===")
sync_task(5)
asyncio.run(async_task(5))


# ─────────────────────────────────────────────
# 2. Validate function signature in decorator
#    FastAPI does this to enforce route handler signatures
# ─────────────────────────────────────────────

def require_param(param_name: str, param_type: type):
    """Decorator that asserts a function has a specific typed parameter."""
    def decorator(fn: F) -> F:
        sig = inspect.signature(fn)
        hints = get_type_hints(fn)

        if param_name not in sig.parameters:
            raise TypeError(
                f"{fn.__name__} must have parameter '{param_name}'"
            )
        actual_type = hints.get(param_name)
        if actual_type is not param_type:
            raise TypeError(
                f"{fn.__name__}.{param_name} must be {param_type.__name__}, "
                f"got {actual_type}"
            )
        return fn
    return decorator


@require_param("user_id", str)
def get_user_orders(user_id: str, limit: int = 10) -> list:
    return []

print("\n=== require_param decorator: OK ===")

try:
    @require_param("user_id", str)
    def bad_handler(user_id: int) -> list:  # wrong type
        return []
except TypeError as e:
    print(f"require_param caught: {e}")


# ═══════════════════════════════════════════════════════
# PART D: inspect for Class Introspection
# ═══════════════════════════════════════════════════════

# ─────────────────────────────────────────────
# 1. inspect.getmembers — list all methods of a class
# ─────────────────────────────────────────────

class UserService:
    def create_user(self, name: str) -> dict: return {}
    def get_user(self, user_id: str) -> dict: return {}
    def delete_user(self, user_id: str) -> None: pass
    async def async_update(self, user_id: str, data: dict) -> dict: return {}
    def _private_method(self) -> None: pass


print("\n=== Class Introspection ===")
public_methods = [
    (name, member)
    for name, member in inspect.getmembers(UserService, predicate=inspect.isfunction)
    if not name.startswith("_")
]
for name, method in public_methods:
    is_async = inspect.iscoroutinefunction(method)
    sig = inspect.signature(method)
    print(f"  {'async ' if is_async else '      '}{name}{sig}")


# ─────────────────────────────────────────────
# 2. inspect.isclass, isfunction, ismethod
# ─────────────────────────────────────────────

print("\n=== Type Checks ===")
print(f"isclass(UserService):        {inspect.isclass(UserService)}")
print(f"isfunction(create_user):     {inspect.isfunction(UserService.create_user)}")
print(f"iscoroutinefunction(async):  {inspect.iscoroutinefunction(UserService.async_update)}")

svc = UserService()
print(f"ismethod(svc.create_user):   {inspect.ismethod(svc.create_user)}")


# ─────────────────────────────────────────────
# 3. inspect.getmro — Method Resolution Order
# ─────────────────────────────────────────────

class Base:
    def method(self): pass

class Mixin:
    def helper(self): pass

class Child(Mixin, Base):
    pass

print(f"\nMRO for Child: {[c.__name__ for c in inspect.getmro(Child)]}")
# ['Child', 'Mixin', 'Base', 'object']


# ═══════════════════════════════════════════════════════
# PART E: Source Code Introspection
# ═══════════════════════════════════════════════════════

# ─────────────────────────────────────────────
# 1. inspect.getsource — get source code at runtime
# ─────────────────────────────────────────────

def my_function(x: int, y: int) -> int:
    """Add two numbers."""
    return x + y

source = inspect.getsource(my_function)
print(f"\n=== getsource ===")
print(source)

# Get file and line number
file = inspect.getfile(my_function)
lines, start_line = inspect.getsourcelines(my_function)
print(f"Defined in: {file.split('/')[-1]}:{start_line}")


# ─────────────────────────────────────────────
# 2. inspect.currentframe — caller info in logging/debugging
# ─────────────────────────────────────────────

def log_with_caller(message: str) -> None:
    """Log message with caller's file and line info."""
    frame = inspect.currentframe()
    if frame and frame.f_back:
        caller = frame.f_back
        print(f"[{caller.f_code.co_filename.split('/')[-1]}:{caller.f_lineno}] {message}")

log_with_caller("This is logged with caller info")


# ═══════════════════════════════════════════════════════
# PART F: Interview Questions
# ═══════════════════════════════════════════════════════

"""
Q1: What is the inspect module used for?
    Runtime introspection of Python objects — signatures, type hints, source code,
    class hierarchy, method types (sync/async). Used by FastAPI, LangChain, Pydantic.

Q2: How does FastAPI auto-discover route parameters?
    inspect.signature(route_fn) to get parameters, get_type_hints() to resolve
    annotation strings to actual types, then builds Pydantic validators automatically.

Q3: How do you write a decorator that works for both sync and async functions?
    Use inspect.iscoroutinefunction(fn) to detect async. Return an async wrapper
    with await for async, regular wrapper for sync.

Q4: What is inspect.Parameter.empty?
    Sentinel value indicating a parameter has no default. Use
    param.default is inspect.Parameter.empty to check.

Q5: How does LangChain build tool schemas from functions?
    inspect.signature() + get_type_hints() to extract param names, types, defaults.
    inspect.getdoc() to get the docstring as tool description.
    This is exactly what @tool decorator does internally.

Q6: What is inspect.getmro vs __mro__?
    Both return the Method Resolution Order. inspect.getmro(cls) is the function,
    cls.__mro__ is the attribute — same result, use whichever is cleaner.
"""
