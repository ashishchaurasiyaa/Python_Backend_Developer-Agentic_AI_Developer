"""
DAY 32 — contextlib + Full Python Data Model (Dunder Methods)
Architecture Level: Senior Python Backend + Agentic AI
"""

import contextlib
import asyncio
import time
from typing import Generator, AsyncGenerator


# ═══════════════════════════════════════════════════════
# PART A: contextlib — beyond simple context managers
# ═══════════════════════════════════════════════════════

# ─────────────────────────────────────────────
# 1. @contextmanager — the Pythonic way
# ─────────────────────────────────────────────

@contextlib.contextmanager
def timer(label: str) -> Generator[None, None, None]:
    """Measure execution time of a block."""
    start = time.perf_counter()
    try:
        yield
    finally:
        elapsed = time.perf_counter() - start
        print(f"[TIMER] {label}: {elapsed*1000:.2f}ms")


with timer("Database query"):
    time.sleep(0.01)


@contextlib.contextmanager
def managed_connection(url: str):
    """Simulate DB connection context manager."""
    print(f"[DB] Connecting to {url}")
    connection = {"url": url, "active": True}
    try:
        yield connection
    except Exception as e:
        print(f"[DB] Rolling back due to: {e}")
        raise
    finally:
        connection["active"] = False
        print(f"[DB] Connection closed")


with managed_connection("postgresql://localhost/mydb") as conn:
    print(f"[DB] Running query, connection active: {conn['active']}")


# ─────────────────────────────────────────────
# 2. @asynccontextmanager — for async code
# ─────────────────────────────────────────────

@contextlib.asynccontextmanager
async def async_timer(label: str) -> AsyncGenerator[None, None]:
    start = time.perf_counter()
    try:
        yield
    finally:
        elapsed = time.perf_counter() - start
        print(f"[ASYNC TIMER] {label}: {elapsed*1000:.2f}ms")


@contextlib.asynccontextmanager
async def llm_session(model: str):
    """Manage LLM API session — initialize, yield, cleanup."""
    print(f"[LLM] Opening session for {model}")
    session = {"model": model, "tokens_used": 0}
    try:
        yield session
    finally:
        print(f"[LLM] Session closed. Tokens used: {session['tokens_used']}")


async def demo_async_context():
    async with async_timer("LLM call"):
        async with llm_session("gpt-4") as session:
            await asyncio.sleep(0.01)  # simulate API call
            session["tokens_used"] = 500
            print(f"[LLM] Called {session['model']}")

asyncio.run(demo_async_context())


# ─────────────────────────────────────────────
# 3. contextlib.suppress — clean error suppression
# ─────────────────────────────────────────────

# BAD:
# try:
#     os.remove("maybe_exists.txt")
# except FileNotFoundError:
#     pass

# GOOD:
import os
with contextlib.suppress(FileNotFoundError):
    os.remove("/tmp/nonexistent_file.txt")
print("No crash — file didn't exist, suppressed cleanly")


# ─────────────────────────────────────────────
# 4. contextlib.ExitStack — dynamic context managers
# ─────────────────────────────────────────────

@contextlib.contextmanager
def open_tool(name: str):
    print(f"  Opening tool: {name}")
    yield {"name": name, "active": True}
    print(f"  Closing tool: {name}")


def run_with_tools(tool_names: list[str]):
    """Open a variable number of tools dynamically."""
    with contextlib.ExitStack() as stack:
        tools = [stack.enter_context(open_tool(name)) for name in tool_names]
        print(f"  Active tools: {[t['name'] for t in tools]}")
        # All tools close automatically when ExitStack exits


print("\nExitStack demo:")
run_with_tools(["web_search", "calculator", "file_reader"])


# ═══════════════════════════════════════════════════════
# PART B: Full Python Data Model — Dunder Methods
# ═══════════════════════════════════════════════════════

class TokenBucket:
    """
    Production-grade token bucket for rate limiting.
    Demonstrates the full Python data model.
    """

    def __init__(self, capacity: int, name: str = "default"):
        self._capacity = capacity
        self._tokens = capacity
        self._name = name
        self._refill_rate = capacity  # tokens per second

    # ── Representation ────────────────────────────────
    def __repr__(self) -> str:
        """Developer representation — used in REPL and logs."""
        return f"TokenBucket(name={self._name!r}, tokens={self._tokens}/{self._capacity})"

    def __str__(self) -> str:
        """User-friendly string — used in print()."""
        return f"[{self._name}] {self._tokens}/{self._capacity} tokens available"

    # ── Comparison ────────────────────────────────────
    def __eq__(self, other: object) -> bool:
        if not isinstance(other, TokenBucket):
            return NotImplemented
        return self._name == other._name and self._capacity == other._capacity

    def __lt__(self, other: "TokenBucket") -> bool:
        return self._tokens < other._tokens

    def __le__(self, other: "TokenBucket") -> bool:
        return self._tokens <= other._tokens

    # ── Numeric operations ────────────────────────────
    def __len__(self) -> int:
        """len(bucket) returns current token count."""
        return self._tokens

    def __bool__(self) -> bool:
        """bool(bucket) is True if tokens available."""
        return self._tokens > 0

    def __contains__(self, cost: int) -> bool:
        """cost in bucket — checks if affordable."""
        return self._tokens >= cost

    # ── Context manager ───────────────────────────────
    def __enter__(self) -> "TokenBucket":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        return False  # don't suppress exceptions

    # ── Callable ──────────────────────────────────────
    def __call__(self, cost: int) -> bool:
        """bucket(cost) — consume tokens."""
        if self._tokens >= cost:
            self._tokens -= cost
            return True
        return False

    # ── Arithmetic ────────────────────────────────────
    def __add__(self, tokens: int) -> "TokenBucket":
        """bucket + 10 — create new bucket with more tokens."""
        new = TokenBucket(self._capacity, self._name)
        new._tokens = min(self._tokens + tokens, self._capacity)
        return new

    def __iadd__(self, tokens: int) -> "TokenBucket":
        """bucket += 10 — refill tokens in place."""
        self._tokens = min(self._tokens + tokens, self._capacity)
        return self

    # ── Iterator ──────────────────────────────────────
    def __iter__(self):
        """Iterate over tokens one at a time (consume all)."""
        while self._tokens > 0:
            self._tokens -= 1
            yield 1


# Demo all dunder methods:
bucket = TokenBucket(100, "api_rate_limiter")
print(f"\n{bucket!r}")                  # __repr__
print(f"{bucket}")                       # __str__
print(f"Has 50 tokens? {50 in bucket}") # __contains__
print(f"bool: {bool(bucket)}")          # __bool__
print(f"len: {len(bucket)}")            # __len__

# __call__
success = bucket(30)  # consume 30 tokens
print(f"Consumed 30: {success}, remaining: {len(bucket)}")

# __iadd__
bucket += 20          # refill 20
print(f"After refill: {len(bucket)}")

# __add__
new_bucket = bucket + 100  # new bucket
print(f"New bucket: {new_bucket!r}")

# Context manager
with bucket as b:
    print(f"In context: {b}")

# Comparison
b1 = TokenBucket(100, "b1")
b2 = TokenBucket(100, "b2")
b1(60)  # consume 60, b1 has 40
print(f"b1 < b2: {b1 < b2}")  # True


# ─────────────────────────────────────────────
# INTERVIEW — Complete Dunder Reference
# ─────────────────────────────────────────────
DUNDER_CHEATSHEET = """
LIFECYCLE:     __init__, __new__, __del__
REPRESENTATION:__repr__, __str__, __format__, __bytes__
COMPARISON:    __eq__, __ne__, __lt__, __le__, __gt__, __ge__
ARITHMETIC:    __add__, __sub__, __mul__, __truediv__, __floordiv__, __mod__, __pow__
               __radd__ (reflected), __iadd__ (in-place)
UNARY:         __neg__, __pos__, __abs__, __invert__
CONTAINER:     __len__, __getitem__, __setitem__, __delitem__, __contains__, __iter__, __next__
CALLABLE:      __call__
CONTEXT:       __enter__, __exit__, __aenter__, __aexit__
ATTRIBUTE:     __getattr__, __setattr__, __delattr__, __getattribute__
DESCRIPTOR:    __get__, __set__, __delete__
CLASS:         __init_subclass__, __class_getitem__
HASHING:       __hash__  (set to None if __eq__ defined without __hash__)
BOOL:          __bool__
"""
print(DUNDER_CHEATSHEET)
