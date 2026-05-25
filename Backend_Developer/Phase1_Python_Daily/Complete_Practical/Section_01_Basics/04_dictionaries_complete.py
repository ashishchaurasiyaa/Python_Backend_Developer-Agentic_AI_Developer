"""
╔══════════════════════════════════════════════════════════════╗
║  PYTHON COMPLETE PRACTICAL — Section 01                      ║
║  Topic: Dictionaries — Complete Reference                    ║
╚══════════════════════════════════════════════════════════════╝
"""

from collections import defaultdict, Counter, OrderedDict
from typing import Any

# ─────────────────────────────────────────────────────────────
# 1. CREATION
# ─────────────────────────────────────────────────────────────

empty: dict = {}
basic: dict[str, int] = {"a": 1, "b": 2, "c": 3}

# From sequences
keys   = ["name", "model", "temperature"]
values = ["Alice", "gpt-4", 0.7]
from_zip = dict(zip(keys, values))

# dict() constructor
d1 = dict(name="Alice", model="gpt-4")

# From list of tuples
d2 = dict([("x", 1), ("y", 2)])

# dict.fromkeys — same default value for all keys
defaults = dict.fromkeys(["retry", "timeout", "debug"], 0)
print(defaults)   # {'retry': 0, 'timeout': 0, 'debug': 0}

# GOTCHA: don't use mutable default!
# bad = dict.fromkeys(["a","b"], [])   # all share same list!
# good = {k: [] for k in ["a","b"]}   # each gets own list


# ─────────────────────────────────────────────────────────────
# 2. ACCESS PATTERNS
# ─────────────────────────────────────────────────────────────

config = {
    "model": "gpt-4",
    "temperature": 0.7,
    "max_tokens": 2000,
    "stream": True,
}

# Direct access — KeyError if missing
print(config["model"])

# .get() — safe access
print(config.get("model"))                    # "gpt-4"
print(config.get("top_p"))                    # None
print(config.get("top_p", 1.0))              # 1.0 (default)

# .setdefault() — get if exists, else set and return default
config.setdefault("top_p", 1.0)
print(config["top_p"])                        # 1.0 (set and returned)
config.setdefault("temperature", 999)          # does NOT overwrite
print(config["temperature"])                   # 0.7 (unchanged)


# ─────────────────────────────────────────────────────────────
# 3. MUTATION METHODS
# ─────────────────────────────────────────────────────────────

d = {"a": 1, "b": 2}

# Add / Update
d["c"] = 3                          # add new key
d["a"] = 99                         # update existing

# update() — merge another dict (modifies in place)
d.update({"d": 4, "e": 5})
d.update(f=6, g=7)                  # keyword syntax

# pop — remove and return
val = d.pop("a")                    # removes "a", returns 99
val = d.pop("z", None)              # safe pop with default

# popitem — remove and return last inserted (LIFO, Python 3.7+)
key, val = d.popitem()

# del
del d["b"]

# clear
# d.clear()


# ─────────────────────────────────────────────────────────────
# 4. ITERATION PATTERNS
# ─────────────────────────────────────────────────────────────

config = {"model": "gpt-4", "temp": 0.7, "max_tokens": 2000}

# Keys (default iteration)
for key in config:
    print(key)

# Keys explicitly
for key in config.keys():
    print(key)

# Values
for val in config.values():
    print(val)

# Items — KEY: the one you use most
for key, val in config.items():
    print(f"  {key}: {val}")

# Dict views are dynamic (reflect changes)
keys_view = config.keys()
config["new_key"] = "new_val"
print("new_key" in keys_view)  # True — view updated


# ─────────────────────────────────────────────────────────────
# 5. DICT COMPREHENSIONS
# ─────────────────────────────────────────────────────────────

# {key_expr: value_expr for item in iterable if condition}

nums = [1, 2, 3, 4, 5]
squares = {n: n**2 for n in nums}
print(squares)    # {1:1, 2:4, 3:9, 4:16, 5:25}

# Filter
even_sq = {n: n**2 for n in nums if n % 2 == 0}
print(even_sq)    # {2:4, 4:16}

# Invert dict (swap keys and values)
original = {"a": 1, "b": 2, "c": 3}
inverted = {v: k for k, v in original.items()}
print(inverted)   # {1:'a', 2:'b', 3:'c'}

# From list of dicts — index by a field
users = [
    {"id": 1, "name": "Alice", "role": "admin"},
    {"id": 2, "name": "Bob",   "role": "user"},
    {"id": 3, "name": "Charlie","role": "user"},
]
users_by_id   = {u["id"]: u for u in users}
users_by_name = {u["name"]: u for u in users}
print(users_by_id[2])   # {"id":2, "name":"Bob", "role":"user"}


# ─────────────────────────────────────────────────────────────
# 6. MERGING DICTS — Python 3.9+ operators
# ─────────────────────────────────────────────────────────────

base    = {"model": "gpt-4", "temperature": 0.5, "max_tokens": 1000}
override = {"temperature": 0.9, "stream": True}

# Python 3.9+ — | operator (creates new dict)
merged = base | override
print(merged)   # temperature=0.9 from override wins

# Python 3.9+ — |= in place
base |= override

# Old style — unpacking (Python 3.5+)
merged_old = {**base, **override}   # right side wins

# Merge with priority (first dict wins — reverse of |)
def merge_with_priority(*dicts: dict) -> dict:
    """Later dicts override earlier ones."""
    result = {}
    for d in dicts:
        result.update(d)
    return result


# ─────────────────────────────────────────────────────────────
# 7. NESTED DICTS — safe access
# ─────────────────────────────────────────────────────────────

api_response = {
    "status": "success",
    "data": {
        "user": {
            "id": 123,
            "profile": {
                "name": "Alice",
                "email": "alice@example.com",
            }
        }
    }
}

# Safe nested access
name = api_response.get("data", {}).get("user", {}).get("profile", {}).get("name")
print(f"Name: {name}")

# Helper for deep get
def deep_get(d: dict, *keys: str, default=None) -> Any:
    """Safely get nested dict value."""
    for key in keys:
        if not isinstance(d, dict):
            return default
        d = d.get(key, default)
    return d

email = deep_get(api_response, "data", "user", "profile", "email")
missing = deep_get(api_response, "data", "user", "address", "city", default="Unknown")
print(f"Email: {email}, City: {missing}")


# ─────────────────────────────────────────────────────────────
# 8. SORTING DICTS
# ─────────────────────────────────────────────────────────────

data = {"banana": 3, "apple": 5, "cherry": 1, "date": 4}

# Sort by key
by_key  = dict(sorted(data.items()))
print(by_key)   # {'apple':5, 'banana':3, 'cherry':1, 'date':4}

# Sort by value
by_val  = dict(sorted(data.items(), key=lambda x: x[1]))
by_val_desc = dict(sorted(data.items(), key=lambda x: x[1], reverse=True))
print(by_val_desc)   # {'apple':5, 'date':4, 'banana':3, 'cherry':1}

# Top N items
from heapq import nlargest
top2 = dict(nlargest(2, data.items(), key=lambda x: x[1]))
print(top2)   # {'apple':5, 'date':4}


# ─────────────────────────────────────────────────────────────
# 9. PRODUCTION PATTERNS
# ─────────────────────────────────────────────────────────────

# ── Pattern 1: Config management with override hierarchy ─────
class ConfigManager:
    """Layered config: defaults → env → user → runtime."""

    _defaults: dict = {
        "model": "gpt-3.5-turbo",
        "temperature": 0.7,
        "max_tokens": 1000,
        "timeout": 30,
        "retry": 3,
    }

    def __init__(self):
        self._layers: list[dict] = [self._defaults.copy()]

    def load_env(self, env_overrides: dict) -> "ConfigManager":
        self._layers.append(env_overrides)
        return self

    def load_user(self, user_config: dict) -> "ConfigManager":
        self._layers.append(user_config)
        return self

    def get(self, key: str, default=None):
        for layer in reversed(self._layers):
            if key in layer:
                return layer[key]
        return default

    @property
    def resolved(self) -> dict:
        result = {}
        for layer in self._layers:
            result.update(layer)
        return result


cfg = ConfigManager()
cfg.load_env({"model": "gpt-4", "timeout": 60})
cfg.load_user({"temperature": 0.9, "stream": True})

print(f"\nResolved config: {cfg.resolved}")
print(f"Model: {cfg.get('model')}")    # gpt-4 (from env)
print(f"Stream: {cfg.get('stream')}")  # True (from user)


# ── Pattern 2: Inverted index (search engine pattern) ────────
def build_inverted_index(documents: dict[int, str]) -> dict[str, set[int]]:
    """Build word → document IDs mapping."""
    index: dict[str, set[int]] = defaultdict(set)
    for doc_id, text in documents.items():
        for word in text.lower().split():
            index[word].add(doc_id)
    return dict(index)


docs = {
    1: "Python backend developer guide",
    2: "Python agentic AI engineer",
    3: "Backend API design patterns",
}

index = build_inverted_index(docs)
print(f"\n'python' appears in docs: {index.get('python')}")
print(f"'backend' appears in docs: {index.get('backend')}")

# Search for documents containing ALL query words
def search(index: dict, query: str) -> set[int]:
    words = query.lower().split()
    if not words:
        return set()
    results = index.get(words[0], set())
    for word in words[1:]:
        results = results & index.get(word, set())
    return results

print(f"Search 'python backend': {search(index, 'python backend')}")


# ── Pattern 3: JSON-like response builder ────────────────────
def api_response(
    *,
    data: Any = None,
    error: str | None = None,
    status: str = "success",
    meta: dict | None = None,
) -> dict:
    """Standard API response envelope."""
    response: dict[str, Any] = {"status": status}
    if error:
        response["error"] = error
        response["status"] = "error"
    if data is not None:
        response["data"] = data
    if meta:
        response["meta"] = meta
    return response


print(api_response(data={"user_id": 1}))
print(api_response(error="Not found", status="error"))


# ── Pattern 4: memoization with dict ─────────────────────────
_cache: dict[tuple, Any] = {}

def memoize(func):
    def wrapper(*args, **kwargs):
        key = (func.__name__, args, tuple(sorted(kwargs.items())))
        if key not in _cache:
            _cache[key] = func(*args, **kwargs)
        return _cache[key]
    return wrapper

@memoize
def expensive_compute(n: int) -> int:
    return sum(i**2 for i in range(n))

print(expensive_compute(1000))
print(expensive_compute(1000))  # cached — instant


# ─────────────────────────────────────────────────────────────
# INTERVIEW QUESTIONS
# ─────────────────────────────────────────────────────────────
"""
Q: Are Python dicts ordered?
A: Yes, since Python 3.7+, dicts maintain insertion order.
   This is now a language guarantee, not just CPython implementation detail.

Q: What's the time complexity of dict operations?
A: get/set/delete: O(1) average, O(n) worst (hash collision — rare)
   keys/values/items: O(n) to iterate

Q: What's the difference between dict.get() and dict[]?
A: dict[] raises KeyError if key missing.
   dict.get(key, default) returns default (None if not specified).
   Always use .get() when key absence is possible.

Q: How do you merge dicts in Python 3.9+?
A: merged = dict1 | dict2  (right side wins on conflict)
   dict1 |= dict2          (in-place)

Q: What's the difference between dict.update() and the | operator?
A: update() modifies in place. | creates a new dict.

Q: When would you use defaultdict over regular dict?
A: When you need auto-initialized values for missing keys.
   defaultdict(list) for grouping, defaultdict(int) for counting.
   Counter is even better for counting.
"""
