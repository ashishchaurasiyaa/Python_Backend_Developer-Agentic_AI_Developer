"""
╔══════════════════════════════════════════════════════════════════════════════╗
║   PYTHON COMPLETE THEORY — File 05                                           ║
║   Topic: collections / functools / itertools                                 ║
║   Format: WHAT → WHY → HOW → REAL LIFE → PRODUCTION CODE → Q&A              ║
╚══════════════════════════════════════════════════════════════════════════════╝

Topics Covered:
  ── collections ──
  A. defaultdict   — auto-initialize missing keys
  B. Counter        — frequency counting
  C. deque          — O(1) append/pop from both ends
  D. namedtuple     — lightweight struct / immutable record
  E. OrderedDict    — order-preserving dict (+ LRU cache)

  ── functools ──
  F. lru_cache / cache  — memoization
  G. cached_property    — compute once, cache on instance
  H. partial            — pre-fill function arguments
  I. reduce             — fold/accumulate over iterable
  J. singledispatch     — function overloading by type

  ── itertools ──
  K. Infinite iterators — count, cycle, repeat
  L. Combinatorics      — product, permutations, combinations
  M. Slicing/grouping   — islice, groupby, chain, zip_longest
  N. Accumulate         — running totals / prefix sums
  O. Lazy pipelines     — compose itertools for memory efficiency
"""

from collections import defaultdict, Counter, deque, namedtuple, OrderedDict
import functools
import itertools
from typing import Any, Callable, TypeVar, Iterable
import time


# ══════════════════════════════════════════════════════════════════════════════
# PART A: defaultdict
# ══════════════════════════════════════════════════════════════════════════════

"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
WHAT IS defaultdict?
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

defaultdict is a dict subclass that AUTOMATICALLY creates a default value
for missing keys — instead of raising KeyError.

WHY?
  Problem with plain dict:
    d = {}
    d["key"].append("value")  # KeyError! "key" doesn't exist yet
    # You must: d["key"] = d.get("key", [])
    #           d["key"].append("value")  # verbose!

  Solution with defaultdict:
    d = defaultdict(list)
    d["key"].append("value")  # works! auto-creates empty list

HOW:
  defaultdict(default_factory)
    where default_factory is called with NO arguments to create the default value.

  defaultdict(list)   → default = []
  defaultdict(int)    → default = 0
  defaultdict(set)    → default = set()
  defaultdict(dict)   → default = {}
  defaultdict(lambda: "N/A") → default = "N/A"

INTERNAL MECHANISM:
  When accessing a missing key, Python calls __missing__(key).
  defaultdict overrides __missing__ to call default_factory()
  and stores the result before returning it.

REAL LIFE ANALOGY:
  defaultdict = Smart filing cabinet:
  - Regular cabinet: you search for "January" → it's not there → error, you need to create it
  - defaultdict: you search for "January" → not there → cabinet AUTOMATICALLY creates empty folder
  Now just put documents in: cabinet["January"].append(doc)

PRODUCTION EXAMPLE — Grouping LLM tool calls by category:
"""

tool_calls = [
    ("web_search", "Python tutorials"),
    ("code_exec", "print('hello')"),
    ("web_search", "FastAPI docs"),
    ("file_read", "config.json"),
    ("code_exec", "import numpy"),
    ("file_read", "data.csv"),
]

# Regular dict — verbose
grouped_regular = {}
for tool, query in tool_calls:
    if tool not in grouped_regular:
        grouped_regular[tool] = []
    grouped_regular[tool].append(query)

# defaultdict — clean!
grouped = defaultdict(list)
for tool, query in tool_calls:
    grouped[tool].append(query)  # auto-creates list if key missing

print("=== defaultdict ===")
for tool, queries in grouped.items():
    print(f"  {tool}: {queries}")


# Nested defaultdict — for tree-like structures
nested = defaultdict(lambda: defaultdict(int))
nested["agent_1"]["web_search"] += 1
nested["agent_1"]["web_search"] += 1
nested["agent_2"]["code_exec"] += 3
print(f"\nNested defaultdict:")
for agent, tools in nested.items():
    print(f"  {agent}: {dict(tools)}")


# Counter per category
word_freq = defaultdict(int)
text = "the quick brown fox jumps over the lazy dog the fox"
for word in text.split():
    word_freq[word] += 1

top_3 = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)[:3]
print(f"\nWord frequency (defaultdict): {top_3}")


"""
Q&A — defaultdict

Q1: What happens when you access a missing key in defaultdict?
A:  __missing__(key) is called → default_factory() is called (with no args) →
    result stored at that key → result returned.
    The key NOW EXISTS in the dict with the default value.

Q2: What is the difference between defaultdict(list) and dict.setdefault(key, [])?
A:  Both work, but:
    defaultdict: ALWAYS uses list as default — simpler, set it once
    setdefault():  per-call default — more flexible (different defaults for different keys)
    defaultdict is preferred for "always the same default type" pattern.

Q3: Can you convert defaultdict back to regular dict?
A:  Yes: dict(my_defaultdict)   or   {**my_defaultdict}
"""


# ══════════════════════════════════════════════════════════════════════════════
# PART B: Counter
# ══════════════════════════════════════════════════════════════════════════════

"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
WHAT IS Counter?
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Counter is a dict subclass DESIGNED for counting hashable elements.
Counts how many times each element appears.

WHY?
  frequency counting, histogram building, top-N analysis,
  rate limiting, token usage tracking — all very common in AI/backend.

HOW:
  c = Counter(iterable)          # count each element
  c = Counter({"a": 3, "b": 1}) # from dict
  c = Counter(a=3, b=1)         # from kwargs

  c.most_common(n)    → top N elements
  c.update(iterable)  → add more counts
  c.subtract(iterable)→ subtract counts
  c + d, c - d        → combine counters
  c & d               → intersection (minimum counts)
  c | d               → union (maximum counts)

REAL LIFE ANALOGY:
  Counter = Vote tallying machine:
  Each time someone votes for a candidate, their count goes up by 1.
  At the end: counter.most_common(1) → winner!
"""

print("\n=== Counter ===")

# Token frequency for LLM context analysis
conversation = """
user: I want to build an AI agent with Python
assistant: Python is great for AI. Use LangChain or LangGraph for agents.
user: What about FastAPI for the backend?
assistant: Yes, FastAPI is perfect. Use async Python for best performance.
user: How do I handle Python errors in async code?
"""

words = [w.strip(".,!?:").lower() for w in conversation.split() if len(w) > 3]
word_counter = Counter(words)

print(f"Top 5 words: {word_counter.most_common(5)}")
print(f"'python' appears: {word_counter['python']} times")
print(f"'javascript' appears: {word_counter['javascript']} times")  # 0, not KeyError

# Rate limiting with Counter
class RateLimiter:
    """Token bucket using Counter — track API calls per user."""

    def __init__(self, limit: int = 5):
        self.limit = limit
        self.calls: Counter = Counter()

    def is_allowed(self, user_id: str) -> bool:
        if self.calls[user_id] >= self.limit:
            return False
        self.calls[user_id] += 1
        return True

    def reset(self, user_id: str) -> None:
        del self.calls[user_id]


limiter = RateLimiter(limit=3)
for i in range(5):
    allowed = limiter.is_allowed("user_001")
    print(f"  Call {i+1}: {'✅ allowed' if allowed else '❌ rate limited'}")

# Counter arithmetic
model_usage = Counter({"gpt-4": 100, "gpt-3.5": 200, "claude-3": 50})
more_usage  = Counter({"gpt-4": 50, "claude-3": 100})
combined = model_usage + more_usage
print(f"\nCombined model usage: {dict(combined)}")


"""
Q&A — Counter

Q1: What does Counter return for a missing key?
A:  0 (not KeyError) — Counter returns 0 for any missing key.
    This makes it safe to do counter["unknown"] without checking.

Q2: What does Counter.subtract() do differently from Counter minus Counter (-)?
A:  subtract(): allows NEGATIVE counts (key goes below 0)
    c1 - c2:     removes keys with count <= 0 (never negative results)
"""


# ══════════════════════════════════════════════════════════════════════════════
# PART C: deque
# ══════════════════════════════════════════════════════════════════════════════

"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
WHAT IS deque?
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

deque = Double-Ended Queue.
Supports O(1) append/pop from BOTH ENDS.
List is O(n) for insert/remove at front.

WHY?
  list.insert(0, x) → O(n) — all elements shift right
  deque.appendleft(x) → O(1) — no shifting needed

HOW:
  ┌─────────────────────────────────────────────────┐
  │              deque (doubly linked list)          │
  │  ◄──────────────────────────────────────────►   │
  │  appendleft   [a] ↔ [b] ↔ [c] ↔ [d]  append    │
  │  popleft      ◄─────────────────────  pop       │
  └─────────────────────────────────────────────────┘

  deque(iterable, maxlen=N):
    maxlen: fixed capacity! When full, OLDEST item auto-removed on add.
    Perfect for sliding window / rolling buffer.

OPERATIONS:
  d.append(x)         → add to right  O(1)
  d.appendleft(x)     → add to left   O(1)
  d.pop()             → remove from right O(1)
  d.popleft()         → remove from left  O(1)
  d.rotate(n)         → rotate n positions
  d.extend(iter)      → add multiple to right
  d.extendleft(iter)  → add multiple to left (reversed!)

REAL LIFE ANALOGY:
  deque = Sliding window of recent events:
  "Remember the last 10 user messages" → deque(maxlen=10)
  When 11th message arrives: oldest auto-drops, newest takes its place.
  Like a CCTV DVR that keeps last N hours of footage.
"""

print("\n=== deque ===")

# Conversation history with sliding window
conversation_buffer: deque[dict] = deque(maxlen=5)  # keep last 5 messages only

messages = [
    {"role": "user", "content": "What is Python?"},
    {"role": "assistant", "content": "Python is a programming language."},
    {"role": "user", "content": "Tell me about async."},
    {"role": "assistant", "content": "asyncio allows concurrent I/O."},
    {"role": "user", "content": "What about FastAPI?"},
    {"role": "assistant", "content": "FastAPI is built on asyncio."},
    {"role": "user", "content": "How do I deploy it?"},  # oldest will be dropped
]

for msg in messages:
    conversation_buffer.append(msg)

print(f"Buffer after {len(messages)} messages (maxlen=5):")
for m in conversation_buffer:
    print(f"  [{m['role']}]: {m['content'][:40]}")
print(f"Buffer size: {len(conversation_buffer)}")  # always ≤ 5

# BFS queue (classic use case)
def bfs_graph(graph: dict, start: str) -> list[str]:
    """BFS using deque — O(1) popleft is critical here."""
    visited = set()
    queue: deque[str] = deque([start])
    order = []

    while queue:
        node = queue.popleft()  # O(1) — if list: O(n)!
        if node in visited:
            continue
        visited.add(node)
        order.append(node)
        queue.extend(graph.get(node, []))

    return order

graph = {"A": ["B", "C"], "B": ["D", "E"], "C": ["F"], "D": [], "E": [], "F": []}
print(f"\nBFS order: {bfs_graph(graph, 'A')}")

# Performance comparison: list.pop(0) vs deque.popleft()
n = 50_000

lst = list(range(n))
start = time.perf_counter()
while lst:
    lst.pop(0)  # O(n) each time!
list_time = time.perf_counter() - start

dq = deque(range(n))
start = time.perf_counter()
while dq:
    dq.popleft()  # O(1) each time!
deque_time = time.perf_counter() - start

print(f"\nPop from front ({n} items):")
print(f"  list.pop(0): {list_time*1000:.1f}ms")
print(f"  deque.popleft(): {deque_time*1000:.1f}ms")


"""
Q&A — deque

Q1: When should you use list vs deque?
A:  Use LIST for: random access (list[42]), most append/pop from RIGHT end
    Use DEQUE for: frequent insert/remove from BOTH ends, sliding window (maxlen),
                   BFS/DFS queues, producer-consumer buffers

Q2: What does maxlen do when deque is full?
A:  When maxlen is set and deque is full:
    append() removes from the LEFT (oldest)
    appendleft() removes from the RIGHT (newest)
    This makes it a perfect CIRCULAR BUFFER / SLIDING WINDOW.
"""


# ══════════════════════════════════════════════════════════════════════════════
# PART D: namedtuple
# ══════════════════════════════════════════════════════════════════════════════

"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
WHAT IS namedtuple?
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

namedtuple = A tuple subclass where EACH POSITION has a NAME.
Lightweight, IMMUTABLE data record.

WHY?
  Problem with plain tuple:
    point = (10, 20)
    point[0]  # x? y? you need to remember positions!

  Problem with plain dict:
    point = {"x": 10, "y": 20}
    point.x  # AttributeError! dicts use [], not .

  namedtuple: tuple efficiency + named access like object attributes.
    Point = namedtuple("Point", ["x", "y"])
    p = Point(10, 20)
    p.x      # 10 — by name!
    p[0]     # 10 — by index! still a tuple

HOW:
  Classic:
    Point = namedtuple("Point", ["x", "y"])
    Point = namedtuple("Point", "x y")  # space-separated string also works

  Modern (typing.NamedTuple — preferred):
    class Point(NamedTuple):
        x: float
        y: float
        label: str = ""  # with default!

ADVANTAGES:
  ✅ Immutable (hashable — can be dict key, set member)
  ✅ Memory efficient (no __dict__ per instance)
  ✅ Tuple compatible (unpack, iterate, index)
  ✅ Named access (.x, .y) for readability
  ✅ Good repr: Point(x=10, y=20)
  ✅ Can add methods (with NamedTuple class)

REAL LIFE ANALOGY:
  namedtuple = A structured receipt:
  Regular tuple: (42.50, "USD", "2024-01-15")  ← which index is what?
  namedtuple:    Receipt(amount=42.50, currency="USD", date="2024-01-15") ← clear!
"""

from typing import NamedTuple

print("\n=== namedtuple ===")


class LLMResponse(NamedTuple):
    """Typed NamedTuple for LLM API responses."""
    model: str
    content: str
    tokens_used: int
    latency_ms: float
    finish_reason: str = "stop"  # default value

    def is_complete(self) -> bool:
        return self.finish_reason == "stop"

    def cost_estimate(self, price_per_1k: float = 0.03) -> float:
        return self.tokens_used / 1000 * price_per_1k


r = LLMResponse(
    model="gpt-4",
    content="Python is a versatile programming language.",
    tokens_used=450,
    latency_ms=1250.3,
)

print(f"Response: {r}")
print(f"Model: {r.model}")             # by name
print(f"Tokens: {r[2]}")              # by index (it's still a tuple)
print(f"Complete: {r.is_complete()}")
print(f"Cost: ${r.cost_estimate():.4f}")

# Unpack like regular tuple
model, content, tokens, latency, reason = r
print(f"Unpacked: model={model}, tokens={tokens}")

# Use as dict key (immutable → hashable)
cache: dict[LLMResponse, str] = {}
cache[r] = "cached_embedding"
print(f"Used as dict key: {cache[r]}")

# _asdict() → convert to OrderedDict
print(f"As dict: {r._asdict()}")

# _replace() → create modified copy
r2 = r._replace(model="claude-3", tokens_used=380)
print(f"Modified copy: {r2}")


"""
Q&A — namedtuple

Q1: namedtuple vs dataclass — when to use which?
A:  namedtuple: IMMUTABLE, lightweight, tuple-compatible, good for data records
                best when data shouldn't change and you need hashability
    dataclass:  MUTABLE by default (frozen=True for immutable), supports more features
                (validators, __post_init__, default_factory), better for complex objects

Q2: Can you add methods to namedtuple?
A:  Yes! With the NamedTuple class-style syntax (typing.NamedTuple),
    you add regular methods just like a class.
    With the function syntax (namedtuple("Point", "x y")), you can also
    add methods but it's less clean.

Q3: Is namedtuple faster than a regular class?
A:  Yes — namedtuple has no __dict__ per instance, similar to __slots__.
    Access by index is also faster than attribute lookup in some cases.
"""


# ══════════════════════════════════════════════════════════════════════════════
# PART E: OrderedDict
# ══════════════════════════════════════════════════════════════════════════════

"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
WHAT IS OrderedDict?
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Since Python 3.7+, regular dict maintains insertion order.
OrderedDict: dict subclass with extra ORDER-AWARE methods.

WHY STILL USE OrderedDict?
  Extra methods: move_to_end(), popitem(last=True/False)
  LRU CACHE implementation: move recently accessed item to end → oldest is always first

HOW:
  od = OrderedDict()
  od.move_to_end("key")           # move key to end (most recent)
  od.move_to_end("key", last=False) # move to front (oldest)
  od.popitem(last=True)           # remove & return last (most recent)
  od.popitem(last=False)          # remove & return first (oldest / LRU)

CLASSIC USE: LRU CACHE (Least Recently Used)
  - Fixed capacity cache
  - On access: move item to end (mark as recently used)
  - When full and new item added: remove FIRST item (least recently used)
  - O(1) get and put with OrderedDict

REAL LIFE ANALOGY:
  LRU Cache = Browser history:
  - You visit 10 pages (capacity)
  - Visit page 5 again → move to "most recent"
  - Open page 11 → browser drops OLDEST page from history
"""

class LRUCache:
    """LRU Cache using OrderedDict — classic interview question."""

    def __init__(self, capacity: int):
        self.capacity = capacity
        self.cache: OrderedDict = OrderedDict()

    def get(self, key: str) -> Any:
        if key not in self.cache:
            return None
        self.cache.move_to_end(key)  # mark as recently used
        return self.cache[key]

    def put(self, key: str, value: Any) -> None:
        if key in self.cache:
            self.cache.move_to_end(key)
        self.cache[key] = value
        if len(self.cache) > self.capacity:
            self.cache.popitem(last=False)  # remove least recently used (first item)

    def __repr__(self) -> str:
        return f"LRUCache(cap={self.capacity}, items={list(self.cache.keys())})"


print("\n=== OrderedDict — LRU Cache ===")
lru = LRUCache(capacity=3)
lru.put("gpt-4:prompt1", "response1")
lru.put("gpt-4:prompt2", "response2")
lru.put("claude:prompt1", "response3")
print(f"After 3 puts: {lru}")

lru.get("gpt-4:prompt1")  # access → moves to end (most recent)
print(f"After accessing prompt1: {lru}")

lru.put("claude:prompt2", "response4")  # capacity exceeded → removes LRU
print(f"After adding 4th: {lru}")      # gpt-4:prompt2 should be evicted (LRU)


"""
Q&A — OrderedDict

Q1: Do I still need OrderedDict in Python 3.7+?
A:  For basic ordered storage: No, regular dict maintains insertion order.
    For LRU cache or needing move_to_end() / popitem(last=): Yes, OrderedDict.

Q2: What is the time complexity of LRU Cache get/put?
A:  Both O(1) — dict lookup is O(1) and move_to_end() is O(1) in OrderedDict.
    This is why OrderedDict is the CLASSIC data structure for LRU cache.
"""


# ══════════════════════════════════════════════════════════════════════════════
# PART F: functools.lru_cache / cache
# ══════════════════════════════════════════════════════════════════════════════

"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
WHAT IS lru_cache?
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@functools.lru_cache(maxsize=128):
  MEMOIZE a function — cache results of previous calls.
  Same arguments → return cached result instead of computing again.

@functools.cache (Python 3.9+):
  Equivalent to lru_cache(maxsize=None) — unlimited cache (never evicts).
  Slightly faster than lru_cache.

WHY?
  Expensive function called many times with same arguments?
  → First call: compute result, store in cache
  → Subsequent calls: return cached result instantly

HOW (Internal):
  Cache is a dict: args_tuple → return_value
  LRU policy: when maxsize is reached, evict least recently used entry

  Requirements for cacheability:
  - Arguments must be HASHABLE (dicts, lists cannot be cache keys)
  - Function must be PURE (same args → same result, no side effects)

REAL LIFE ANALOGY:
  lru_cache = Your brain remembering answers:
  "What's 17 × 23?" — first time: calculate (391) → remember it
  Next time someone asks: immediately answer 391, no calculation.
  LRU: forget LEAST RECENTLY asked questions when memory is full.
"""

import functools

print("\n=== functools.lru_cache ===")

# Classic: Fibonacci with memoization
call_count = 0

@functools.lru_cache(maxsize=None)
def fib_cached(n: int) -> int:
    global call_count
    call_count += 1
    if n < 2:
        return n
    return fib_cached(n - 1) + fib_cached(n - 2)

start = time.perf_counter()
result = fib_cached(40)
elapsed = (time.perf_counter() - start) * 1000
print(f"fib(40) = {result}")
print(f"Time: {elapsed:.3f}ms, Unique calls: {call_count}")
print(f"Cache info: {fib_cached.cache_info()}")

# Clear cache
fib_cached.cache_clear()
print(f"After clear: {fib_cached.cache_info()}")

# Production: Cache expensive embedding computation
@functools.lru_cache(maxsize=1000)
def get_embedding(text: str, model: str = "text-embedding-ada-002") -> tuple[float, ...]:
    """Cache embeddings — same text always returns same vector."""
    # In reality: calls OpenAI/Anthropic API
    import hashlib
    hash_val = int(hashlib.md5(text.encode()).hexdigest(), 16)
    # Return fake 4-dim embedding
    return tuple((hash_val >> (i * 8)) % 256 / 255.0 for i in range(4))

e1 = get_embedding("Hello world")
e2 = get_embedding("Hello world")  # cached — no API call!
e3 = get_embedding("Python rocks")

print(f"\nEmbedding cache:")
print(f"  e1 = e2: {e1 == e2}")  # True (cached)
print(f"  e1 ≠ e3: {e1 != e3}")  # True (different text)
print(f"  Cache: {get_embedding.cache_info()}")


# ══════════════════════════════════════════════════════════════════════════════
# PART G: functools.cached_property
# ══════════════════════════════════════════════════════════════════════════════

"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
WHAT IS cached_property?
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@cached_property: compute a property ONCE on first access, cache on the instance.
Subsequent accesses return the cached value — no recomputation.

WHY?
  @property: called EVERY time you access it (recomputes each time)
  @cached_property: computed ONCE, stored in instance.__dict__

  Perfect for: expensive computations, tokenization, embedding generation
  that only needs to happen once per instance.

HOW:
  On first access: calls the function, stores result in instance.__dict__[name]
  On subsequent access: instance.__dict__[name] takes PRIORITY over the descriptor
  → the function is NEVER called again!

IMPORTANT: cached_property is NOT thread-safe by default.
           Use with care in multi-threaded code (use Lock or lru_cache for threads).
"""

class Document:
    """Document class with expensive cached operations."""

    def __init__(self, text: str):
        self.text = text
        self._compute_count = 0

    @functools.cached_property
    def word_count(self) -> int:
        """Expensive: computed once, cached forever on instance."""
        self._compute_count += 1
        print(f"    [Computing word_count] (compute #{self._compute_count})")
        return len(self.text.split())

    @functools.cached_property
    def token_ids(self) -> list[int]:
        """Simulated tokenization — expensive operation."""
        self._compute_count += 1
        print(f"    [Computing token_ids] (compute #{self._compute_count})")
        return [ord(c) for c in self.text[:20]]  # simplified

    @functools.cached_property
    def sentences(self) -> list[str]:
        """Split into sentences — computed once."""
        self._compute_count += 1
        return [s.strip() for s in self.text.split(".") if s.strip()]


doc = Document("The quick brown fox jumps over the lazy dog. Python is amazing.")

print(f"\n@cached_property demo:")
print(f"  First access:")
wc1 = doc.word_count        # computed here
print(f"  word_count: {wc1}")

print(f"  Second access:")
wc2 = doc.word_count        # cached! no recomputation
print(f"  word_count: {wc2}")

print(f"  Total compute calls: {doc._compute_count}")  # only 1!

# The cached value lives in the instance dict
print(f"  In instance dict: {'word_count' in doc.__dict__}")


# ══════════════════════════════════════════════════════════════════════════════
# PART H: functools.partial
# ══════════════════════════════════════════════════════════════════════════════

"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
WHAT IS functools.partial?
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

partial() creates a NEW function with SOME ARGUMENTS pre-filled.
Also called "partial application" or "currying-lite."

WHY?
  Problem: You have a general function, but you always call it with the same arg.
           Instead of repeating that arg every call, pre-fill it.

  Example:
    def log(level, message): ...
    log_error = partial(log, "ERROR")   # pre-fill level
    log_error("File not found")         # now just: log_error(message)

HOW:
  new_func = functools.partial(original_func, *args, **kwargs)
  When you call new_func(*more_args): original_func(*args + more_args, **kwargs)

REAL LIFE ANALOGY:
  partial = Pre-filling a form:
  Regular form: fill in name, address, city, country every time
  partial form: country="India" already filled in → you only fill the rest
"""

print("\n=== functools.partial ===")


def call_llm(model: str, prompt: str, temperature: float = 0.7, max_tokens: int = 1000) -> str:
    """General LLM calling function."""
    return f"[{model}|temp={temperature}|max={max_tokens}] {prompt[:30]}..."


# Create specialized callers with pre-filled args
call_gpt4         = functools.partial(call_llm, "gpt-4")
call_claude       = functools.partial(call_llm, "claude-3-sonnet")
call_gpt4_precise = functools.partial(call_llm, "gpt-4", temperature=0.1)
call_creative     = functools.partial(call_llm, "gpt-4", temperature=1.5, max_tokens=2000)

print(f"gpt4: {call_gpt4('What is Python?')}")
print(f"claude: {call_claude('What is Python?')}")
print(f"precise: {call_gpt4_precise('Write a factual summary')}")
print(f"creative: {call_creative('Write a poem about code')}")

# partial with map()
temperatures = [0.0, 0.5, 1.0, 1.5, 2.0]
get_responses = list(map(
    functools.partial(call_llm, "gpt-4", "Hello"),
    temperatures
))
print(f"\nDifferent temperatures:")
for r in get_responses:
    print(f"  {r}")


# ══════════════════════════════════════════════════════════════════════════════
# PART I: functools.reduce
# ══════════════════════════════════════════════════════════════════════════════

"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
WHAT IS functools.reduce?
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

reduce(func, iterable, initial) → applies func cumulatively:
  [a, b, c, d] → func(func(func(a, b), c), d)

Reduces a sequence to a SINGLE VALUE by repeatedly applying a function.

HOW:
  reduce(lambda acc, x: acc + x, [1, 2, 3, 4])
  → ((1 + 2) + 3) + 4 = 10

  Step by step:
    acc=1,    x=2 → 1+2=3
    acc=3,    x=3 → 3+3=6
    acc=6,    x=4 → 6+4=10
    Result: 10

WHEN TO USE:
  - Accumulating/combining values where order matters
  - Composing functions in a pipeline
  - Building complex structures from parts

NOTE: For simple sum/product, use sum() or math.prod() instead.
      reduce() is for custom fold operations.

REAL LIFE ANALOGY:
  reduce = Running total on a shopping receipt:
  Start with 0, add each item's price → final total.
  Or: Start with identity, apply each discount → final discounted price.
"""

print("\n=== functools.reduce ===")

from functools import reduce
from operator import add, mul

# Simple reduction
numbers = [1, 2, 3, 4, 5]
total = reduce(add, numbers)
product = reduce(mul, numbers)
print(f"Sum: {total}, Product: {product}")

# Pipeline composition with reduce
def compose(*functions):
    """Compose functions right-to-left: compose(f, g, h)(x) = f(g(h(x)))"""
    return reduce(lambda f, g: lambda x: f(g(x)), functions)

# Build a text processing pipeline
strip_text      = str.strip
lower_text      = str.lower
remove_newlines = lambda s: s.replace("\n", " ")

process = compose(strip_text, lower_text, remove_newlines)
raw_text = "  HELLO\nWORLD  "
print(f"Processed: '{process(raw_text)}'")

# Merge list of dicts (reduce-based)
patches = [
    {"model": "gpt-4"},
    {"temperature": 0.7},
    {"max_tokens": 2048},
    {"system": "You are helpful."},
]
merged = reduce(lambda a, b: {**a, **b}, patches)
print(f"Merged config: {merged}")


# ══════════════════════════════════════════════════════════════════════════════
# PART J: functools.singledispatch
# ══════════════════════════════════════════════════════════════════════════════

"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
WHAT IS singledispatch?
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

singledispatch: OVERLOAD a function based on the TYPE of the first argument.
Different type → different implementation → same function name.

WHY?
  Instead of: if isinstance(x, str): ... elif isinstance(x, list): ...
  singledispatch: define each type handler separately → cleaner, extensible.

HOW:
  @functools.singledispatch
  def process(data):          # fallback for unknown types
      raise TypeError(...)

  @process.register(str)
  def _(data: str): ...       # handle str

  @process.register(dict)
  def _(data: dict): ...      # handle dict

  @process.register(list)
  def _(data: list): ...      # handle list

  process("hello")  → calls str handler
  process({"a": 1}) → calls dict handler
"""

print("\n=== functools.singledispatch ===")


@functools.singledispatch
def format_tool_result(result: Any) -> str:
    """Default handler for unknown types."""
    return f"Unknown type: {type(result).__name__}: {result}"

@format_tool_result.register(str)
def _(result: str) -> str:
    return f"Text: {result}"

@format_tool_result.register(dict)
def _(result: dict) -> str:
    import json
    return f"JSON: {json.dumps(result, indent=2)}"

@format_tool_result.register(list)
def _(result: list) -> str:
    return f"List ({len(result)} items): {result[:3]}{'...' if len(result) > 3 else ''}"

@format_tool_result.register(int)
@format_tool_result.register(float)
def _(result) -> str:
    return f"Number: {result:,}"


print(format_tool_result("Hello world"))
print(format_tool_result({"name": "Alice", "score": 95}))
print(format_tool_result([1, 2, 3, 4, 5, 6]))
print(format_tool_result(1_234_567))
print(format_tool_result(b"bytes data"))  # falls to default


# ══════════════════════════════════════════════════════════════════════════════
# PART K: itertools — INFINITE ITERATORS
# ══════════════════════════════════════════════════════════════════════════════

"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
WHAT IS itertools?
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

itertools: a standard library module of LAZY ITERATOR building blocks.
All itertools are LAZY — they produce values on demand (no memory until needed).

THREE CATEGORIES:
  1. Infinite iterators: count, cycle, repeat
  2. Combinatorics:      product, permutations, combinations, combinations_with_replacement
  3. Slicing/grouping:   islice, groupby, chain, zip_longest, compress, dropwhile, takewhile

WHY LAZY?
  If you need first 5 items from an infinite sequence,
  you don't want to generate ALL infinity — just the first 5.

REAL LIFE ANALOGY:
  itertools = Assembly line tools:
  Each tool does ONE thing to the stream of items coming through.
  Chain multiple tools → powerful pipeline that processes items one by one.
"""

print("\n=== itertools — infinite iterators ===")

# count(start, step) — infinite counter
counter = itertools.count(start=1, step=2)
odd_numbers = list(itertools.islice(counter, 5))  # take first 5
print(f"count(1, 2) → first 5: {odd_numbers}")

# cycle(iterable) — repeat forever
strategies = ["GPT-4", "Claude-3", "Gemini"]
strategy_cycle = itertools.cycle(strategies)
load_balanced = [next(strategy_cycle) for _ in range(9)]
print(f"Round-robin (9 calls): {load_balanced}")

# repeat(value, n) — repeat n times (or infinite)
defaults = list(itertools.repeat("gpt-4", times=3))
print(f"repeat('gpt-4', 3): {defaults}")


# ══════════════════════════════════════════════════════════════════════════════
# PART L: itertools — COMBINATORICS
# ══════════════════════════════════════════════════════════════════════════════

print("\n=== itertools — combinatorics ===")

# product — Cartesian product
models = ["gpt-4", "claude-3"]
temperatures = [0.0, 0.7, 1.5]
experiments = list(itertools.product(models, temperatures))
print(f"Experiments (model × temp): {experiments}")

# permutations — ordered arrangements
tools = ["A", "B", "C"]
perms = list(itertools.permutations(tools, 2))
print(f"permutations(['A','B','C'], 2): {perms}")

# combinations — unordered selections (no repeats)
combs = list(itertools.combinations(tools, 2))
print(f"combinations(['A','B','C'], 2): {combs}")

# combinations_with_replacement — can repeat
combs_r = list(itertools.combinations_with_replacement(["a", "b"], 2))
print(f"combinations_with_replacement(['a','b'], 2): {combs_r}")


# ══════════════════════════════════════════════════════════════════════════════
# PART M: itertools — SLICING AND GROUPING
# ══════════════════════════════════════════════════════════════════════════════

print("\n=== itertools — slicing and grouping ===")

# chain — concatenate iterables (lazy)
list1 = [1, 2, 3]
list2 = [4, 5, 6]
list3 = [7, 8, 9]
chained = list(itertools.chain(list1, list2, list3))
print(f"chain: {chained}")

# chain.from_iterable — flatten one level
nested = [[1, 2], [3, 4], [5, 6]]
flat = list(itertools.chain.from_iterable(nested))
print(f"chain.from_iterable: {flat}")

# islice — lazy slicing (works on infinite iterables)
gen = itertools.count(0)
sliced = list(itertools.islice(gen, 3, 10, 2))  # start=3, stop=10, step=2
print(f"islice(count, 3, 10, 2): {sliced}")

# groupby — group consecutive elements by key
events = [
    ("user", "Hello"),
    ("user", "How are you?"),
    ("assistant", "I am fine."),
    ("assistant", "How can I help?"),
    ("user", "Tell me about Python"),
]

print("groupby (consecutive):")
for role, group in itertools.groupby(events, key=lambda x: x[0]):
    messages = [m[1] for m in group]
    print(f"  {role}: {messages}")

# zip_longest — zip with fill value
short = [1, 2, 3]
long = [10, 20, 30, 40, 50]
zipped = list(itertools.zip_longest(short, long, fillvalue=0))
print(f"zip_longest: {zipped}")

# Batching (chunk iterable into groups) — Python 3.12+ has batched()
def batch(iterable: Iterable, n: int):
    """Split iterable into batches of size n."""
    it = iter(iterable)
    while chunk := list(itertools.islice(it, n)):
        yield chunk

prompts = [f"prompt_{i}" for i in range(10)]
print("Batches of 3:")
for b in batch(prompts, 3):
    print(f"  {b}")


# ══════════════════════════════════════════════════════════════════════════════
# PART N: itertools.accumulate
# ══════════════════════════════════════════════════════════════════════════════

"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
WHAT IS accumulate?
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

accumulate(iterable, func=add, initial=None):
  Returns running/cumulative values at each step.
  Like reduce() but KEEPS ALL INTERMEDIATE VALUES.

WHY?
  - Running token count (cumulative sum)
  - Running max/min (cumulative max)
  - Prefix sums for range queries
  - Sliding window statistics

HOW:
  accumulate([1, 2, 3, 4]) → [1, 3, 6, 10]  (running sum)
  accumulate([3, 1, 4, 1, 5], max) → [3, 3, 4, 4, 5]  (running max)
"""

print("\n=== itertools.accumulate ===")

from operator import add, mul

# Running token count
token_usage = [150, 320, 85, 440, 200]
cumulative = list(itertools.accumulate(token_usage, add))
print(f"Token usage: {token_usage}")
print(f"Cumulative:  {cumulative}")
print(f"Total: {cumulative[-1]}")

# Running maximum score
scores = [72, 85, 68, 91, 77, 95, 88]
running_max = list(itertools.accumulate(scores, max))
print(f"\nScores:      {scores}")
print(f"Running max: {running_max}")

# Compound interest (initial=1.0, multiply each rate)
monthly_rates = [1.01, 1.02, 0.98, 1.03, 1.015]
growth = list(itertools.accumulate(monthly_rates, mul, initial=1000.0))
print(f"\nInvestment growth: {[f'{v:.2f}' for v in growth]}")


# ══════════════════════════════════════════════════════════════════════════════
# PART O: LAZY PIPELINE PATTERN
# ══════════════════════════════════════════════════════════════════════════════

"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
LAZY PIPELINE — THE POWER OF itertools + generators
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Chain itertools and generators to process MILLIONS of items with constant memory.
Nothing materializes until the final consumer (e.g., list(), sum(), for loop).

EXAMPLE: Process log file for AI agent events
  logs → filter errors → parse → extract tool calls → count
"""

print("\n=== Lazy Pipeline ===")

import random
random.seed(42)

def generate_logs(n: int):
    """Infinite log generator — simulates real log stream."""
    levels = ["INFO", "INFO", "INFO", "WARNING", "ERROR"]
    tools = ["web_search", "code_exec", "file_read", "db_query"]
    for i in range(n):
        yield {
            "id": i,
            "level": random.choice(levels),
            "tool": random.choice(tools),
            "tokens": random.randint(50, 500),
        }

# Lazy pipeline — NO intermediate lists created
def error_logs(logs):
    return (log for log in logs if log["level"] == "ERROR")

def expensive_tools(logs):
    return (log for log in logs if log["tokens"] > 300)

def extract_tool_name(logs):
    return (log["tool"] for log in logs)

# Compose: errors → expensive → extract tool name → count
pipeline = extract_tool_name(
    expensive_tools(
        error_logs(generate_logs(10_000))  # process 10k logs
    )
)

tool_counts = Counter(pipeline)  # only materializes when consumed
print(f"Expensive error tools: {dict(tool_counts)}")
print(f"(Processed 10k logs with O(1) memory via lazy pipeline)")


"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Q&A — collections / functools / itertools
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Q1: What is the difference between lru_cache and cached_property?
A:  lru_cache: for functions (standalone or methods), with LRU eviction policy
              arguments must be hashable, works on any function
    cached_property: for class methods ONLY, cached PER INSTANCE in instance.__dict__
                     computed once per instance, not per argument set

Q2: When would itertools be faster than a list comprehension?
A:  When you DON'T need all values at once:
    - Iterating over millions of items (memory)
    - Taking first N items from large/infinite sequence (speed — no full generation)
    - Pipeline where only final result matters
    List comprehension builds entire list in memory first.
    itertools generators produce items ONE AT A TIME on demand.

Q3: What is the difference between chain() and chain.from_iterable()?
A:  chain(a, b, c):               flattens multiple separate iterables
    chain.from_iterable([[a,b],[c,d]]): flattens one iterable OF iterables
    Use chain.from_iterable when you have a list of lists.

Q4: Why is groupby() in itertools different from SQL GROUP BY?
A:  itertools.groupby() only groups CONSECUTIVE elements with the same key.
    You MUST sort the data first if you want SQL-style grouping.
    SQL: groups all rows with same key regardless of order.
    itertools: only groups adjacent rows with same key.

    Before using groupby():
      data.sort(key=lambda x: x["category"])  # sort first!
      for key, group in groupby(data, key=lambda x: x["category"]):
          ...
"""

print("\n✅ 05_Collections_Functools_Itertools_Theory.py complete — all sections covered.")
