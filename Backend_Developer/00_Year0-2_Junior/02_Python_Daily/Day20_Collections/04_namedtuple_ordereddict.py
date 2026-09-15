"""
DAY 26 — collections.namedtuple + OrderedDict
Architecture Level: Senior Python Backend + Agentic AI
"""

from collections import namedtuple, OrderedDict
from typing import NamedTuple


# ═══════════════════════════════════════════════════════
# PART A: namedtuple
# ═══════════════════════════════════════════════════════

# ─────────────────────────────────────────────
# 1. OLD STYLE — namedtuple factory function
# ─────────────────────────────────────────────

Point = namedtuple("Point", ["x", "y"])
p = Point(10, 20)
print(p.x, p.y)         # 10 20
print(p[0], p[1])       # 10 20 — still indexable
print(p._asdict())      # {'x': 10, 'y': 20}
p2 = p._replace(x=99)  # creates new instance (immutable)
print(p2)               # Point(x=99, y=20)


# ─────────────────────────────────────────────
# 2. MODERN STYLE — class-based NamedTuple (preferred at senior level)
# ─────────────────────────────────────────────

class LLMResponse(NamedTuple):
    """Structured response from any LLM provider."""
    model: str
    content: str
    input_tokens: int
    output_tokens: int
    finish_reason: str = "stop"

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens

    @property
    def cost_usd(self) -> float:
        return (self.input_tokens / 1000 * 0.003) + (self.output_tokens / 1000 * 0.015)


resp = LLMResponse(
    model="gpt-4",
    content="Python is great for AI development.",
    input_tokens=50,
    output_tokens=10,
)

print(f"\nModel: {resp.model}")
print(f"Total tokens: {resp.total_tokens}")
print(f"Cost: ${resp.cost_usd:.6f}")
print(f"As dict: {resp._asdict()}")

# Unpacking — works like tuple
model, content, *_ = resp
print(f"Unpacked model: {model}")


# ─────────────────────────────────────────────
# 3. BACKEND USE CASE — DB Row result (before Pydantic)
# ─────────────────────────────────────────────

class UserRecord(NamedTuple):
    id: int
    email: str
    role: str
    is_active: bool

# Simulating DB rows — memory efficient vs dict, readable vs plain tuple
rows = [
    UserRecord(1, "alice@example.com", "admin", True),
    UserRecord(2, "bob@example.com", "user", True),
    UserRecord(3, "charlie@example.com", "user", False),
]

active_admins = [u for u in rows if u.is_active and u.role == "admin"]
print(f"\nActive admins: {active_admins}")

# Why NamedTuple over dataclass for read-only DB rows?
# - Immutable by default (no accidental mutation)
# - 40% less memory than dict
# - Supports tuple unpacking and indexing
# - Faster than dataclass for read operations


# ─────────────────────────────────────────────
# 4. AGENTIC AI — Tool call result structure
# ─────────────────────────────────────────────

class ToolResult(NamedTuple):
    tool_name: str
    success: bool
    output: str
    error: str | None = None
    execution_time_ms: float = 0.0


results = [
    ToolResult("web_search", True, "Found 10 results", execution_time_ms=250.5),
    ToolResult("run_code", False, "", error="SyntaxError", execution_time_ms=12.0),
]

for r in results:
    status = "OK" if r.success else f"FAILED: {r.error}"
    print(f"{r.tool_name}: {status} ({r.execution_time_ms}ms)")


# ═══════════════════════════════════════════════════════
# PART B: OrderedDict
# ═══════════════════════════════════════════════════════

# NOTE: In Python 3.7+, regular dict preserves insertion order.
# OrderedDict is still useful for:
# 1. move_to_end() method
# 2. Equality comparison considers ORDER
# 3. LRU Cache implementation

# ─────────────────────────────────────────────
# 1. ARCHITECTURE PATTERN — LRU Cache with OrderedDict
# ─────────────────────────────────────────────

class LRUCache:
    """
    Least Recently Used cache — classic interview question.
    Uses OrderedDict for O(1) get and put.
    This is exactly how functools.lru_cache works internally.
    """

    def __init__(self, capacity: int):
        self.capacity = capacity
        self._cache: OrderedDict[str, any] = OrderedDict()

    def get(self, key: str):
        if key not in self._cache:
            return None
        self._cache.move_to_end(key)   # mark as recently used
        return self._cache[key]

    def put(self, key: str, value) -> None:
        if key in self._cache:
            self._cache.move_to_end(key)
        self._cache[key] = value
        if len(self._cache) > self.capacity:
            self._cache.popitem(last=False)  # remove least recently used

    def __repr__(self):
        return f"LRUCache({dict(self._cache)})"


cache = LRUCache(capacity=3)
cache.put("user:1", {"name": "Alice"})
cache.put("user:2", {"name": "Bob"})
cache.put("user:3", {"name": "Charlie"})
cache.get("user:1")               # access user:1 — moves to end
cache.put("user:4", {"name": "Dave"})  # evicts user:2 (LRU)

print(f"\nLRU Cache: {cache}")   # user:3, user:1, user:4


# ─────────────────────────────────────────────
# 2. ORDERED EQUALITY vs DICT EQUALITY
# ─────────────────────────────────────────────

d1 = {"a": 1, "b": 2}
d2 = {"b": 2, "a": 1}
print(f"\ndict equality (order ignored): {d1 == d2}")  # True

od1 = OrderedDict([("a", 1), ("b", 2)])
od2 = OrderedDict([("b", 2), ("a", 1)])
print(f"OrderedDict equality (order matters): {od1 == od2}")  # False


# ─────────────────────────────────────────────
# INTERVIEW SUMMARY
# ─────────────────────────────────────────────
# namedtuple  → immutable, memory-efficient, great for DB rows/value objects
# NamedTuple  → class syntax, supports methods and properties, preferred
# dataclass   → mutable by default, more features, heavier than namedtuple
# OrderedDict → use when you need move_to_end() or order-sensitive equality
# dict        → sufficient for insertion-order preservation in Python 3.7+
