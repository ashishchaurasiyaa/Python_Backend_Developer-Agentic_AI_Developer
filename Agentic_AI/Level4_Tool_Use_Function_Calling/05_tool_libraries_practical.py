"""
Level 4 — Doc 5: Building Tool Libraries (PRACTICAL)
=====================================================
Topics:
  1. Safe calculator (sympy)
  2. File I/O with path traversal protection
  3. HTTP tool with domain allowlist
  4. DB query tool (read-only enforcement)
  5. Tool registry pattern
  6. Logging + rate limiting decorators

Install: pip install sympy requests python-dotenv
Run: python 05_tool_libraries_practical.py
"""

import os
import time
import logging
from pathlib import Path
from collections import defaultdict
from functools import wraps
from typing import Optional
from urllib.parse import urlparse

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 1: Safe Calculator (sympy)
# ─────────────────────────────────────────────────────────────────────────────

print("=" * 70)
print("SECTION 1: Safe Calculator with sympy")
print("=" * 70)


def calculator(expression: str) -> dict:
    """Safe math evaluator using sympy."""
    try:
        from sympy import sympify
        result = float(sympify(expression).evalf())
        return {"expression": expression, "result": result}
    except ImportError:
        # Fallback: very simple ast-based eval
        import ast
        try:
            tree = ast.parse(expression, mode='eval')
            # Validate only safe nodes
            for node in ast.walk(tree):
                if not isinstance(node, (ast.Expression, ast.BinOp, ast.UnaryOp,
                                         ast.Constant, ast.Num, ast.Add, ast.Sub,
                                         ast.Mult, ast.Div, ast.USub, ast.Pow)):
                    return {"error": f"unsafe expression: {type(node).__name__}"}
            return {"result": eval(compile(tree, "<safe>", "eval"))}
        except Exception as e:
            return {"error": str(e)}
    except Exception as e:
        return {"error": str(e)}


tests = ["2 + 3 * 4", "10 / 3", "sqrt(16) + 5", "import os", "eval('1+1')"]
for t in tests:
    print(f"  {t!r} → {calculator(t)}")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 2: Safe File I/O (Path Traversal Protection)
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("SECTION 2: Safe File I/O")
print("=" * 70)

# Create a sandbox directory
SANDBOX = Path("./tool_sandbox").resolve()
SANDBOX.mkdir(exist_ok=True)


def safe_path(user_path: str) -> Path:
    """Validate path stays within sandbox."""
    resolved = (SANDBOX / user_path).resolve()
    if not str(resolved).startswith(str(SANDBOX)):
        raise ValueError(f"Path traversal blocked: {user_path}")
    return resolved


def read_file(path: str) -> dict:
    try:
        p = safe_path(path)
        if not p.exists():
            return {"error": "not_found", "path": path}
        return {"path": path, "content": p.read_text()[:5000]}
    except ValueError as e:
        return {"error": str(e)}


def write_file(path: str, content: str) -> dict:
    try:
        p = safe_path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content)
        return {"path": path, "bytes_written": len(content)}
    except ValueError as e:
        return {"error": str(e)}


def list_directory(path: str = ".") -> dict:
    try:
        p = safe_path(path)
        if not p.is_dir():
            return {"error": "not_a_directory"}
        return {"path": path, "files": [f.name for f in p.iterdir()]}
    except ValueError as e:
        return {"error": str(e)}


# Tests
print("  write_file('test.txt', 'hello') →", write_file("test.txt", "hello world"))
print("  read_file('test.txt') →", read_file("test.txt"))
print("  list_directory('.') →", list_directory("."))
print("  read_file('../../etc/passwd') →", read_file("../../etc/passwd"))  # BLOCKED
print("  write_file('/etc/evil', 'pwn') →", write_file("/etc/evil", "pwn"))  # BLOCKED


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 3: HTTP Tool with Domain Allowlist
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("SECTION 3: HTTP Tool with Domain Allowlist")
print("=" * 70)

ALLOWED_DOMAINS = {"api.github.com", "jsonplaceholder.typicode.com"}


def http_get(url: str) -> dict:
    """Safe HTTP GET — only to allowlist domains."""
    try:
        domain = urlparse(url).netloc
        if domain not in ALLOWED_DOMAINS:
            return {"error": f"domain not allowed: {domain}", "allowed": list(ALLOWED_DOMAINS)}

        import requests
        response = requests.get(url, timeout=5)
        return {
            "status": response.status_code,
            "body": response.text[:1000],
            "url": url
        }
    except ImportError:
        return {"error": "install: pip install requests"}
    except Exception as e:
        return {"error": str(e)}


print("  GET github.com (allowed):", http_get("https://api.github.com/users/octocat").get("status", "skipped"))
print("  GET evil.com (blocked):", http_get("https://evil.com/steal").get("error", "?")[:60])


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 4: Read-Only DB Tool (SQL Injection Protection)
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("SECTION 4: Read-Only DB Tool")
print("=" * 70)


def execute_sql_readonly(sql: str) -> dict:
    """Execute only SELECT queries. Block all writes."""
    sql_lower = sql.lower().strip()
    forbidden = ["insert", "update", "delete", "drop", "alter", "create", "truncate", ";"]

    for f in forbidden:
        if f in sql_lower:
            return {"error": f"forbidden SQL keyword: '{f}'"}

    if not sql_lower.startswith("select"):
        return {"error": "only SELECT queries allowed"}

    # In production, actually connect to DB. Here, mock response.
    return {
        "query": sql,
        "rows": [{"id": 1, "name": "John"}, {"id": 2, "name": "Sarah"}],
        "count": 2
    }


tests = [
    "SELECT * FROM users LIMIT 5",
    "DROP TABLE users",
    "DELETE FROM orders",
    "SELECT * FROM users; DROP TABLE users",
    "INSERT INTO logs VALUES (1, 'hack')",
]

for q in tests:
    print(f"  {q[:50]:50s} → {execute_sql_readonly(q)}")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 5: Tool Registry Pattern
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("SECTION 5: Tool Registry Pattern")
print("=" * 70)


class ToolRegistry:
    def __init__(self):
        self._tools = {}
        self._schemas = []

    def register(self, schema: dict):
        """Decorator to register a tool with its schema."""
        def decorator(func):
            name = schema.get("function", schema).get("name", func.__name__)
            self._tools[name] = func
            self._schemas.append(schema)
            return func
        return decorator

    def get_function(self, name: str):
        return self._tools.get(name)

    def get_schemas(self) -> list:
        return self._schemas

    def list_tools(self) -> list:
        return list(self._tools.keys())


registry = ToolRegistry()


@registry.register({
    "type": "function",
    "function": {
        "name": "calc",
        "description": "Calculate math expression",
        "parameters": {
            "type": "object",
            "properties": {"expression": {"type": "string"}},
            "required": ["expression"]
        }
    }
})
def calc(expression: str) -> dict:
    return calculator(expression)


@registry.register({
    "type": "function",
    "function": {
        "name": "read",
        "description": "Read a file",
        "parameters": {
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"]
        }
    }
})
def read(path: str) -> dict:
    return read_file(path)


print(f"Registered tools: {registry.list_tools()}")
print(f"\nFirst schema:\n{registry.get_schemas()[0]}")
print(f"\nCalling registered tool 'calc':")
print(f"  {registry.get_function('calc')('2 + 2')}")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 6: Decorators — Logging + Rate Limiting
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("SECTION 6: Logging + Rate Limiting Decorators")
print("=" * 70)


def with_logging(tool_func):
    """Decorator: log every tool call with latency."""
    @wraps(tool_func)
    def wrapper(*args, **kwargs):
        start = time.time()
        try:
            result = tool_func(*args, **kwargs)
            elapsed = time.time() - start
            logger.info(f"{tool_func.__name__}({kwargs or args}) → ok in {elapsed:.3f}s")
            return result
        except Exception as e:
            elapsed = time.time() - start
            logger.error(f"{tool_func.__name__}({kwargs or args}) → error: {e} (in {elapsed:.3f}s)")
            return {"error": str(e)}
    return wrapper


_call_history = defaultdict(list)


def rate_limit(max_per_minute: int):
    """Decorator: rate limit tool calls per function."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            now = time.time()
            history = _call_history[func.__name__]
            history[:] = [t for t in history if now - t < 60]
            if len(history) >= max_per_minute:
                return {"error": f"rate limit exceeded ({max_per_minute}/min)"}
            history.append(now)
            return func(*args, **kwargs)
        return wrapper
    return decorator


@with_logging
@rate_limit(max_per_minute=5)
def rate_limited_search(query: str) -> dict:
    """Mock search with rate limit."""
    return {"query": query, "results": ["result1", "result2"]}


print("\n[Testing rate limit — 7 calls, limit=5/min]")
for i in range(7):
    result = rate_limited_search(f"query_{i}")
    print(f"  Call {i + 1}: {result}")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 7: Caching with TTL
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("SECTION 7: Caching with TTL")
print("=" * 70)


class TTLCache:
    """Simple TTL cache."""

    def __init__(self, ttl_seconds: int = 60):
        self._store: dict = {}
        self._ttl = ttl_seconds

    def get(self, key):
        if key in self._store:
            value, expiry = self._store[key]
            if time.time() < expiry:
                return value
            del self._store[key]
        return None

    def set(self, key, value):
        self._store[key] = (value, time.time() + self._ttl)


def with_cache(cache: TTLCache):
    """Decorator: cache tool results."""
    def decorator(func):
        @wraps(func)
        def wrapper(**kwargs):
            key = (func.__name__, tuple(sorted(kwargs.items())))
            cached = cache.get(key)
            if cached is not None:
                logger.info(f"Cache HIT: {func.__name__}")
                return cached
            result = func(**kwargs)
            cache.set(key, result)
            return result
        return wrapper
    return decorator


_cache = TTLCache(ttl_seconds=30)


@with_cache(_cache)
def expensive_search(query: str) -> dict:
    time.sleep(0.1)  # Simulate slow API
    return {"query": query, "result": f"results for {query}"}


print("First call (slow):", expensive_search(query="python"))
print("Second call (cached):", expensive_search(query="python"))


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 8: Cleanup + Exercises
# ─────────────────────────────────────────────────────────────────────────────

# Clean up sandbox
import shutil
if SANDBOX.exists():
    shutil.rmtree(SANDBOX)

print("\n" + "=" * 70)
print("SECTION 8: EXERCISES")
print("=" * 70)
print("""
EASY:
1. Add 3 more tools to the registry: send_email, get_calendar, search_web (mocked).
2. Test all tools through the registry.

MEDIUM:
3. Add input validation with Pydantic to all tools.
4. Implement caching with Redis instead of in-memory (use redis-py).

HARD:
5. Build a sandboxed code execution tool using Docker + timeout.
6. Add OpenTelemetry tracing — every tool call gets trace_id, span_id.

PRO:
7. Build a "tool marketplace":
   - Tools as plugins (entry points)
   - Auto-discover from setup.py
   - Permission system (which tools each agent can use)
""")

if __name__ == "__main__":
    print("\n✅ Tool libraries — security and reusability are everything!")
