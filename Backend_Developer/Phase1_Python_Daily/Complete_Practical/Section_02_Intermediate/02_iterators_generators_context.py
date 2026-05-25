"""
╔══════════════════════════════════════════════════════════════╗
║  PYTHON COMPLETE PRACTICAL — Section 02                      ║
║  Topic: Iterators, Generators, Context Managers              ║
╚══════════════════════════════════════════════════════════════╝
"""

import contextlib
import asyncio
import time
from typing import Generator, Iterator, AsyncGenerator, TypeVar, Generic

T = TypeVar("T")

# ══════════════════════════════════════════════════════════════
# PART A: ITERATORS
# ══════════════════════════════════════════════════════════════

# ─────────────────────────────────────────────────────────────
# 1. THE ITERATOR PROTOCOL
# ─────────────────────────────────────────────────────────────

# An object is iterable if it has __iter__()
# An iterator has both __iter__() and __next__()

# How for loop works internally:
items = [1, 2, 3]
iterator = iter(items)          # calls items.__iter__()
print(next(iterator))           # calls iterator.__next__() → 1
print(next(iterator))           # 2
print(next(iterator))           # 3
# next(iterator)  → StopIteration


# ─────────────────────────────────────────────────────────────
# 2. CUSTOM ITERATOR CLASS
# ─────────────────────────────────────────────────────────────

class TokenStream:
    """
    Streams tokens from text — simulates LLM streaming.
    Implements the iterator protocol manually.
    """

    def __init__(self, text: str, chunk_size: int = 1):
        self._tokens = text.split()
        self._chunk_size = chunk_size
        self._index = 0

    def __iter__(self) -> "TokenStream":
        return self  # iterator returns itself

    def __next__(self) -> str:
        if self._index >= len(self._tokens):
            raise StopIteration
        chunk = " ".join(self._tokens[self._index:self._index + self._chunk_size])
        self._index += self._chunk_size
        return chunk

    def __len__(self) -> int:
        return len(self._tokens)


stream = TokenStream("Hello from the Python backend developer guide", chunk_size=2)
for chunk in stream:
    print(chunk, end=" | ")
print()


# ─────────────────────────────────────────────────────────────
# 3. CUSTOM ITERABLE (not iterator — can iterate multiple times)
# ─────────────────────────────────────────────────────────────

class ConversationHistory:
    """
    Iterable (not iterator) — can be iterated multiple times.
    """

    def __init__(self):
        self._messages: list[dict] = []

    def add(self, role: str, content: str) -> None:
        self._messages.append({"role": role, "content": content})

    def __iter__(self) -> Iterator[dict]:
        return iter(self._messages)  # returns a NEW iterator each time

    def __len__(self) -> int:
        return len(self._messages)

    def __getitem__(self, index: int) -> dict:
        return self._messages[index]

    def __reversed__(self) -> Iterator[dict]:
        return reversed(self._messages)


history = ConversationHistory()
history.add("user", "Hello!")
history.add("assistant", "Hi there!")
history.add("user", "Tell me about Python.")

# Can iterate multiple times (unlike a raw iterator)
for msg in history:
    print(f"  {msg['role']}: {msg['content']}")

print(f"Last: {history[-1]}")
for msg in reversed(history):
    print(f"  reversed: {msg['role']}")


# ══════════════════════════════════════════════════════════════
# PART B: GENERATORS
# ══════════════════════════════════════════════════════════════

# ─────────────────────────────────────────────────────────────
# 4. GENERATOR FUNCTIONS
# ─────────────────────────────────────────────────────────────

def fibonacci() -> Generator[int, None, None]:
    """Infinite Fibonacci sequence — lazy, no memory limit."""
    a, b = 0, 1
    while True:
        yield a
        a, b = b, a + b

def take(n: int, gen: Generator) -> list:
    """Take first n items from generator."""
    return [next(gen) for _ in range(n)]

fib = fibonacci()
print(f"\nFirst 10 Fibonacci: {take(10, fib)}")


# Generator with send() — two-way communication
def accumulator() -> Generator[float, float, str]:
    """
    Receives values via send(), yields running total.
    Returns summary when closed.
    """
    total = 0.0
    count = 0
    try:
        while True:
            value = yield total    # yield sends total, receives next value
            total += value
            count += 1
    except GeneratorExit:
        return f"Final: total={total:.2f}, count={count}"


acc = accumulator()
next(acc)           # prime the generator (advance to first yield)
print(acc.send(10.0))   # 10.0
print(acc.send(20.0))   # 30.0
print(acc.send(5.5))    # 35.5
acc.close()


# ─────────────────────────────────────────────────────────────
# 5. YIELD FROM — sub-generators
# ─────────────────────────────────────────────────────────────

def flatten(nested) -> Generator:
    """Flatten arbitrarily nested iterables."""
    for item in nested:
        if hasattr(item, "__iter__") and not isinstance(item, str):
            yield from flatten(item)  # delegate to sub-generator
        else:
            yield item

data = [1, [2, 3], [4, [5, 6]], [[7, [8, 9]]]]
print(f"\nFlattened: {list(flatten(data))}")


def chain_generators(*generators) -> Generator:
    """Chain multiple generators together."""
    for gen in generators:
        yield from gen

g1 = (x**2 for x in range(3))
g2 = (x**3 for x in range(3))
combined = list(chain_generators(g1, g2))
print(f"Chained: {combined}")


# ─────────────────────────────────────────────────────────────
# 6. GENERATOR PIPELINES — real production pattern
# ─────────────────────────────────────────────────────────────

def read_log_file(filename: str) -> Generator[str, None, None]:
    """Lazily read log lines (won't load entire file into memory)."""
    import io
    # Simulate file reading
    fake_content = "\n".join([
        "2025-05-20 INFO Agent started",
        "2025-05-20 DEBUG Tool called: web_search",
        "2025-05-20 ERROR Connection failed",
        "2025-05-20 INFO Retry successful",
        "2025-05-20 ERROR Token limit exceeded",
        "2025-05-20 INFO Task complete",
    ])
    for line in io.StringIO(fake_content):
        yield line.rstrip()

def filter_level(lines: Generator, level: str) -> Generator[str, None, None]:
    for line in lines:
        if level in line:
            yield line

def parse_log(lines: Generator) -> Generator[dict, None, None]:
    for line in lines:
        parts = line.split(" ", 3)
        if len(parts) >= 4:
            yield {"date": parts[0], "time": parts[1], "level": parts[2], "message": parts[3]}

def add_metadata(records: Generator, source: str) -> Generator[dict, None, None]:
    for record in records:
        yield {**record, "source": source}


# Pipeline — processes one line at a time, minimal memory
pipeline = add_metadata(
    parse_log(
        filter_level(
            read_log_file("agent.log"),
            "ERROR"
        )
    ),
    source="production"
)

print("\nError log pipeline:")
for record in pipeline:
    print(f"  [{record['level']}] {record['message']} (source={record['source']})")


# ─────────────────────────────────────────────────────────────
# 7. GENERATOR EXPRESSIONS (lazy comprehensions)
# ─────────────────────────────────────────────────────────────

# List comprehension — eager, all in memory
squares_list = [x**2 for x in range(1_000_000)]    # 8MB in memory

# Generator expression — lazy, minimal memory
squares_gen  = (x**2 for x in range(1_000_000))    # almost no memory

# Use in functions that accept iterables
total = sum(x**2 for x in range(1000))       # no list created!
maximum = max(len(s) for s in ["a", "bbb", "cc"])

# Chaining generator expressions
data = range(100)
result = sum(x**2 for x in data if x % 2 == 0)   # filter + map + reduce
print(f"\nSum of even squares: {result}")


# ══════════════════════════════════════════════════════════════
# PART C: CONTEXT MANAGERS
# ══════════════════════════════════════════════════════════════

# ─────────────────────────────────────────────────────────────
# 8. CLASS-BASED CONTEXT MANAGER
# ─────────────────────────────────────────────────────────────

class DatabaseConnection:
    """Context manager for DB connections."""

    def __init__(self, url: str, timeout: int = 30):
        self.url = url
        self.timeout = timeout
        self.connection = None
        self._transaction_active = False

    def __enter__(self) -> "DatabaseConnection":
        print(f"[DB] Connecting to {self.url}")
        self.connection = {"url": self.url, "active": True}
        return self   # returned to 'as' variable

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        """
        exc_type, exc_val, exc_tb: exception info if error occurred, else None.
        Return True to SUPPRESS the exception, False to let it propagate.
        """
        if exc_type is not None:
            print(f"[DB] Rolling back due to: {exc_type.__name__}: {exc_val}")
            self._transaction_active = False
        else:
            print(f"[DB] Committing transaction")
        print(f"[DB] Closing connection")
        self.connection = None
        return False  # don't suppress exceptions

    def execute(self, query: str) -> list:
        if not self.connection:
            raise RuntimeError("Not connected")
        print(f"[DB] Executing: {query[:40]}")
        return [{"id": 1, "name": "result"}]

    def begin(self):
        self._transaction_active = True


# Normal usage
with DatabaseConnection("postgresql://localhost/mydb") as db:
    results = db.execute("SELECT * FROM users WHERE active = true")
    print(f"Found {len(results)} users")

print()

# Error handling
try:
    with DatabaseConnection("postgresql://localhost/mydb") as db:
        db.execute("INSERT INTO logs VALUES (1, 'test')")
        raise ValueError("Something went wrong!")   # __exit__ handles cleanup
except ValueError as e:
    print(f"Error caught after cleanup: {e}")


# ─────────────────────────────────────────────────────────────
# 9. @contextmanager — generator-based context manager
# ─────────────────────────────────────────────────────────────

@contextlib.contextmanager
def timer(label: str) -> Generator[None, None, None]:
    """Measure block execution time."""
    start = time.perf_counter()
    try:
        yield                                # code inside 'with' runs here
    finally:
        elapsed = (time.perf_counter() - start) * 1000
        print(f"[TIMER] {label}: {elapsed:.2f}ms")

with timer("data processing"):
    total = sum(range(100_000))


@contextlib.contextmanager
def managed_resource(name: str) -> Generator[dict, None, None]:
    """Manage a resource with acquire/release."""
    resource = {"name": name, "acquired": False}
    print(f"[RESOURCE] Acquiring: {name}")
    resource["acquired"] = True
    try:
        yield resource
    except Exception as e:
        print(f"[RESOURCE] Error while using {name}: {e}")
        raise
    finally:
        resource["acquired"] = False
        print(f"[RESOURCE] Released: {name}")

with managed_resource("llm_session") as res:
    print(f"[RESOURCE] Using {res['name']}: acquired={res['acquired']}")


# ─────────────────────────────────────────────────────────────
# 10. @asynccontextmanager — for async code
# ─────────────────────────────────────────────────────────────

@contextlib.asynccontextmanager
async def async_llm_session(model: str) -> AsyncGenerator[dict, None]:
    """Async context manager for LLM API session."""
    print(f"[LLM] Opening session: {model}")
    session = {"model": model, "tokens": 0, "active": True}
    try:
        yield session
    finally:
        session["active"] = False
        print(f"[LLM] Session closed. Tokens used: {session['tokens']}")


async def demo_async_cm():
    async with async_llm_session("gpt-4") as session:
        await asyncio.sleep(0.01)
        session["tokens"] += 500
        print(f"[LLM] Used model: {session['model']}")

asyncio.run(demo_async_cm())


# ─────────────────────────────────────────────────────────────
# 11. ADVANCED CONTEXTLIB TOOLS
# ─────────────────────────────────────────────────────────────

# contextlib.suppress — clean exception suppression
import os
with contextlib.suppress(FileNotFoundError, PermissionError):
    os.remove("/tmp/does_not_exist.txt")
print("Suppressed error cleanly")

# contextlib.ExitStack — dynamic number of context managers
def process_files(filenames: list[str]) -> None:
    """Open variable number of files using ExitStack."""
    with contextlib.ExitStack() as stack:
        files = [
            stack.enter_context(
                contextlib.suppress(FileNotFoundError)
            )
            for name in filenames
        ]
        # stack auto-closes all on exit

# contextlib.redirect_stdout — capture stdout
import io
captured = io.StringIO()
with contextlib.redirect_stdout(captured):
    print("This goes to captured, not terminal")
output = captured.getvalue()
print(f"Captured: {output.strip()!r}")


# ─────────────────────────────────────────────────────────────
# INTERVIEW QUESTIONS
# ─────────────────────────────────────────────────────────────
"""
Q: What's the difference between an iterable and an iterator?
A: Iterable has __iter__() — can be iterated, gives fresh iterator each time.
   Iterator has __iter__() AND __next__() — stateful, single-use.
   A list is iterable. iter(list) gives an iterator.

Q: What is a generator and how is it different from a function?
A: Generator uses 'yield' instead of 'return'. It's lazy — pauses at each
   yield, resuming when next() is called. Returns a generator object.
   Benefits: memory efficiency (no full list), infinite sequences possible.

Q: What does 'yield from' do?
A: Delegates to a sub-generator. More efficient than 'for x in sub: yield x'.
   Also properly passes send() values and handles StopIteration.

Q: What is __enter__ and __exit__?
A: Context manager protocol. __enter__ runs at start of 'with' block,
   returns value assigned to 'as'. __exit__ runs at end (always).
   Return True from __exit__ to suppress exceptions.

Q: When would you use @contextmanager vs a class-based CM?
A: @contextmanager is simpler for linear acquire/release patterns.
   Class-based CM when you need more control (multiple methods, state).
"""
