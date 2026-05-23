"""
DAY 27 — functools: partial, wraps, reduce, singledispatch
Architecture Level: Senior Python Backend + Agentic AI
"""

import functools
from typing import Callable, TypeVar, Any

F = TypeVar("F", bound=Callable)


# ═══════════════════════════════════════════════════════
# PART A: functools.partial
# ═══════════════════════════════════════════════════════

# ─────────────────────────────────────────────
# 1. BASICS — freeze arguments of a function
# ─────────────────────────────────────────────

def power(base: float, exponent: float) -> float:
    return base ** exponent

square = functools.partial(power, exponent=2)
cube   = functools.partial(power, exponent=3)

print(square(5))   # 25.0
print(cube(3))     # 27.0


# ─────────────────────────────────────────────
# 2. BACKEND USE CASE — Pre-configured API clients
# ─────────────────────────────────────────────

import json

def make_api_request(
    endpoint: str,
    method: str = "GET",
    base_url: str = "http://localhost:8000",
    timeout: int = 30,
    headers: dict | None = None,
) -> dict:
    """Simulate HTTP request."""
    print(f"  {method} {base_url}{endpoint} (timeout={timeout}s)")
    return {"status": 200, "endpoint": endpoint}


# Create environment-specific clients
dev_request = functools.partial(
    make_api_request,
    base_url="http://localhost:8000",
    timeout=5,
)
prod_request = functools.partial(
    make_api_request,
    base_url="https://api.example.com",
    timeout=30,
    headers={"Authorization": "Bearer prod_token"},
)

dev_request("/api/users")
prod_request("/api/users")


# ─────────────────────────────────────────────
# 3. AGENTIC AI — Pre-configured LLM callers
# ─────────────────────────────────────────────

def call_llm(
    prompt: str,
    model: str,
    temperature: float,
    max_tokens: int,
    system: str = "You are a helpful assistant.",
) -> str:
    """Simulate LLM call."""
    return f"[{model}|t={temperature}] Response to: {prompt[:30]}..."


# Create specialized agents using partial
creative_agent = functools.partial(
    call_llm,
    model="gpt-4",
    temperature=0.9,
    max_tokens=2000,
    system="You are a creative writer.",
)

precise_agent = functools.partial(
    call_llm,
    model="gpt-4",
    temperature=0.1,
    max_tokens=500,
    system="You are a precise technical analyst.",
)

fast_agent = functools.partial(
    call_llm,
    model="gpt-3.5-turbo",
    temperature=0.5,
    max_tokens=200,
)

print(creative_agent("Write a story about Python"))
print(precise_agent("Analyze this code for bugs"))
print(fast_agent("Summarize this text", system="You are a summarizer."))


# ─────────────────────────────────────────────
# 4. partial with sorted() / map() — functional style
# ─────────────────────────────────────────────

users = [
    {"name": "Alice", "role": "admin", "score": 95},
    {"name": "Bob", "role": "user", "score": 80},
    {"name": "Charlie", "role": "admin", "score": 75},
]

get_score = functools.partial(dict.get, __default=0)  # not common but possible

# More practical: use partial with key functions
sort_by = functools.partial(sorted, key=lambda u: u["score"])
print(sort_by(users, reverse=True))


# ═══════════════════════════════════════════════════════
# PART B: functools.wraps — CRITICAL for decorators
# ═══════════════════════════════════════════════════════

# ─────────────────────────────────────────────
# 1. PROBLEM without @wraps
# ─────────────────────────────────────────────

def bad_decorator(func):
    def wrapper(*args, **kwargs):
        return func(*args, **kwargs)
    return wrapper  # loses __name__, __doc__, __annotations__

@bad_decorator
def my_function():
    """This is my function."""
    pass

print(f"\nWithout @wraps: {my_function.__name__}")  # 'wrapper' — WRONG!


# ─────────────────────────────────────────────
# 2. CORRECT — always use @wraps in decorators
# ─────────────────────────────────────────────

def retry(max_attempts: int = 3, delay: float = 1.0):
    """Production-grade retry decorator."""
    def decorator(func: F) -> F:
        @functools.wraps(func)  # preserves __name__, __doc__, __annotations__
        def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    print(f"  Attempt {attempt}/{max_attempts} failed: {e}")
                    if attempt < max_attempts:
                        import time; time.sleep(delay * attempt)
            raise last_exception
        return wrapper  # type: ignore
    return decorator


@retry(max_attempts=3, delay=0.01)
def call_external_api(endpoint: str) -> dict:
    """Call external API with retry logic."""
    import random
    if random.random() < 0.6:
        raise ConnectionError(f"Failed to connect to {endpoint}")
    return {"status": 200}

print(f"With @wraps: {call_external_api.__name__}")  # 'call_external_api' — correct
print(f"Docstring preserved: {call_external_api.__doc__}")


# ═══════════════════════════════════════════════════════
# PART C: functools.reduce
# ═══════════════════════════════════════════════════════

from functools import reduce
from operator import add, mul

# Basic reduce — sum and product
numbers = [1, 2, 3, 4, 5]
total   = reduce(add, numbers)      # 15
product = reduce(mul, numbers)      # 120
print(f"\nReduce sum: {total}, product: {product}")

# Deep merge of dicts — common in config systems
configs = [
    {"model": "gpt-4", "temperature": 0.5},
    {"max_tokens": 1000, "temperature": 0.7},  # overrides
    {"system": "You are helpful."},
]
merged = reduce(lambda acc, cfg: {**acc, **cfg}, configs)
print(f"Merged config: {merged}")

# Pipeline execution — function composition
def compose(*funcs):
    """Compose multiple functions right-to-left."""
    return reduce(lambda f, g: lambda x: f(g(x)), funcs)

strip_text  = str.strip
lower_text  = str.lower
add_prefix  = lambda s: f"[PROCESSED] {s}"

pipeline = compose(add_prefix, lower_text, strip_text)
result = pipeline("  Hello World  ")
print(f"Pipeline: {result}")


# ═══════════════════════════════════════════════════════
# PART D: functools.singledispatch — type-based dispatch
# ═══════════════════════════════════════════════════════

@functools.singledispatch
def process_input(data) -> str:
    raise NotImplementedError(f"Cannot process type: {type(data)}")

@process_input.register(str)
def _(data: str) -> str:
    return f"Text: {data.upper()}"

@process_input.register(list)
def _(data: list) -> str:
    return f"List with {len(data)} items"

@process_input.register(dict)
def _(data: dict) -> str:
    return f"Dict with keys: {list(data.keys())}"

print(process_input("hello"))
print(process_input([1, 2, 3]))
print(process_input({"model": "gpt-4"}))

# AGENTIC AI use: dispatch different agent tools by input type
