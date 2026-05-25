# Async Advanced Patterns — Queues, Cancellation, Executors, Backpressure

## Quick Concepts

**WHAT:**
- **asyncio.Queue** = Async-safe FIFO queue (producer-consumer)
- **CancelledError** = Exception raised when task cancelled
- **TaskGroup** (3.11+) = Better than gather for error handling
- **run_in_executor** = Run blocking code in thread/process pool
- **Backpressure** = Prevent fast producer overwhelming slow consumer
- **asyncio.Semaphore** = Limit concurrent tasks
- **asyncio.gather vs as_completed** = All at once vs streaming results

**WHY async patterns matter:**
- Wrong patterns → memory leak, missed shutdowns, lost data
- Async ≠ magic — need patterns for production
- Most async bugs are in patterns, not basic syntax

**HOW async ecosystem fits:**
```
┌────────────────────────────────────────────────┐
│ Event Loop (asyncio.get_event_loop)            │
├────────────────────────────────────────────────┤
│ Tasks (asyncio.create_task)                    │
├────────────────────────────────────────────────┤
│ Coroutines (async def)                         │
├────────────────────────────────────────────────┤
│ Awaitables (Coroutine, Task, Future)           │
├────────────────────────────────────────────────┤
│ Sync I/O bridge (run_in_executor)              │
└────────────────────────────────────────────────┘
```

---

## Interview Questions & Answers

### Q1: asyncio.Queue — Producer-Consumer pattern?

**Answer:**

**WHAT:** Thread-safe queue for coordinating async producers + consumers.

**WHY:**
- Decouple producer speed from consumer speed
- Built-in backpressure (maxsize blocks producer)
- Multiple producers + multiple consumers

**HOW — Basic pattern:**

```python
import asyncio
from typing import AsyncIterator

async def producer(queue: asyncio.Queue, items: list):
    """Producer adds items to queue."""
    for item in items:
        await queue.put(item)
        print(f"Produced: {item}")
        await asyncio.sleep(0.1)

    # ⭐ Signal end with sentinel
    await queue.put(None)


async def consumer(queue: asyncio.Queue, consumer_id: int):
    """Consumer processes items until sentinel."""
    while True:
        item = await queue.get()
        if item is None:
            # ⭐ Pass sentinel to other consumers
            await queue.put(None)
            break
        print(f"Consumer {consumer_id} got: {item}")
        await asyncio.sleep(0.3)
        queue.task_done()


async def main():
    queue = asyncio.Queue(maxsize=10)  # ⭐ Backpressure: producer blocks if full

    # Spawn producers + consumers
    await asyncio.gather(
        producer(queue, ['A', 'B', 'C', 'D']),
        consumer(queue, 1),
        consumer(queue, 2),
    )

asyncio.run(main())
```

**HOW — With backpressure:**

```python
# Producer is FAST, Consumer is SLOW
# maxsize=10 → producer blocks when queue full
# Natural rate limiting

async def fast_producer(queue):
    for i in range(1000):
        await queue.put(i)  # Blocks if queue full
        # No sleep needed — backpressure handles rate

async def slow_consumer(queue):
    while True:
        item = await queue.get()
        await process(item)  # Slow: 100ms each
        queue.task_done()
```

**HOW — Wait for all items processed:**

```python
async def main():
    queue = asyncio.Queue()

    # Add items
    for i in range(10):
        await queue.put(i)

    # Spawn consumers as tasks
    consumers = [
        asyncio.create_task(worker(queue))
        for _ in range(3)
    ]

    # ⭐ Wait for queue drained
    await queue.join()

    # Cancel consumers (they're in infinite loop)
    for c in consumers:
        c.cancel()
    await asyncio.gather(*consumers, return_exceptions=True)
```

---

### Q2: asyncio.gather vs as_completed vs TaskGroup?

**Answer:**

**HOW — Decision matrix:**

| Pattern | Returns | When to use | Error handling |
|---|---|---|---|
| `asyncio.gather` | List of results (in order) | All results needed | One fails = others continue (or cancel with `return_exceptions=True`) |
| `asyncio.as_completed` | Iterator (as ready) | Stream results | Manual per-task |
| `asyncio.TaskGroup` (3.11+) | Context manager | Modern, error-grouping | All cancel on first error |
| `asyncio.wait` | (done, pending) sets | Fine control | Manual |

**HOW — gather (legacy, common):**

```python
async def fetch_user(user_id):
    await asyncio.sleep(0.1)
    return f"User-{user_id}"

# All at once, get results in input order
results = await asyncio.gather(
    fetch_user(1),
    fetch_user(2),
    fetch_user(3),
)
# results = ["User-1", "User-2", "User-3"]

# ⚠️ If one raises, others continue but result is exception
# Use return_exceptions to NOT raise immediately
results = await asyncio.gather(
    fetch_user(1),
    failing_function(),
    fetch_user(3),
    return_exceptions=True
)
# results = ["User-1", Exception(...), "User-3"]
```

**HOW — as_completed (streaming results):**

```python
async def fetch_with_priority():
    """Process results as they complete (not input order)."""
    tasks = [fetch_user(i) for i in range(10)]

    for coro in asyncio.as_completed(tasks):
        result = await coro
        print(f"Got: {result}")  # First to complete printed first
        # Useful: process fast results immediately, don't wait for slow
```

**HOW — TaskGroup (Python 3.11+, RECOMMENDED):**

```python
async def main():
    """
    ⭐ Modern pattern: TaskGroup
    - All tasks cancelled if ANY raises
    - Errors grouped (ExceptionGroup)
    - Cleaner than gather
    """
    async with asyncio.TaskGroup() as tg:
        task1 = tg.create_task(fetch_user(1))
        task2 = tg.create_task(fetch_user(2))
        task3 = tg.create_task(fetch_user(3))

    # ⭐ All tasks complete (or all cancelled if any failed)
    # Access results AFTER block
    results = [task1.result(), task2.result(), task3.result()]


# Error handling with TaskGroup
async def main_with_errors():
    try:
        async with asyncio.TaskGroup() as tg:
            tg.create_task(might_fail_1())
            tg.create_task(might_fail_2())
            tg.create_task(might_fail_3())
    except* ValueError as eg:  # ⭐ except* for ExceptionGroup
        for e in eg.exceptions:
            print(f"ValueError: {e}")
    except* TypeError as eg:
        print(f"Got {len(eg.exceptions)} TypeErrors")
```

---

### Q3: Cancellation patterns — CancelledError + cleanup?

**Answer:**

**WHAT:** Tasks can be cancelled mid-execution. Must handle gracefully.

**WHY:**
- Timeout cancellation (asyncio.wait_for)
- User-initiated cancellation (Ctrl-C, API request cancel)
- TaskGroup cancels siblings on error
- Shutdown cleanup

**HOW — Basic cancellation:**

```python
import asyncio

async def long_task():
    try:
        for i in range(100):
            print(f"Working: {i}")
            await asyncio.sleep(1)  # ⭐ CancelledError raised here
    except asyncio.CancelledError:
        # ⭐ CLEANUP — close files, connections, etc.
        print("Task cancelled, cleaning up...")
        await cleanup_resources()
        # ⭐ MUST re-raise (or asyncio gets confused)
        raise


async def main():
    task = asyncio.create_task(long_task())
    await asyncio.sleep(3)
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        print("Task fully cancelled")
```

**HOW — Timeout cancellation (3.11+ asyncio.timeout):**

```python
# Old way (still works)
try:
    result = await asyncio.wait_for(slow_operation(), timeout=5.0)
except asyncio.TimeoutError:
    print("Timed out!")


# ⭐ NEW (Python 3.11+): asyncio.timeout context manager
try:
    async with asyncio.timeout(5.0):
        result = await slow_operation()
except TimeoutError:  # Note: built-in TimeoutError now
    print("Timed out!")


# ⭐ Reschedule timeout
async def with_dynamic_timeout():
    async with asyncio.timeout(5.0) as cm:
        await operation1()
        cm.reschedule(asyncio.get_running_loop().time() + 10.0)  # Extend
        await operation2()
```

**HOW — Shield from cancellation (critical operations):**

```python
async def transaction():
    """Don't cancel mid-transaction (data corruption)."""
    await begin_transaction()
    try:
        # ⭐ Shield protects from outer cancellation
        await asyncio.shield(commit_critical_step())
    except asyncio.CancelledError:
        await rollback()
        raise
    await complete_transaction()
```

**HOW — Detect cancellation in tasks:**

```python
async def cooperative_task():
    """Long task that checks for cancellation."""
    for i in range(1000):
        # ⭐ Yield control periodically
        await asyncio.sleep(0)  # Or await some real I/O

        # Optionally check if we should stop
        if i % 100 == 0:
            current_task = asyncio.current_task()
            if current_task.cancelling() > 0:
                # Cancellation requested
                cleanup()
                raise asyncio.CancelledError()

        # Heavy CPU work
        result = compute_heavy(i)
```

---

### Q4: run_in_executor — Sync code in async?

**Answer:**

**WHAT:** Run blocking (sync) code in thread pool without blocking event loop.

**WHY:**
- Library is sync-only (e.g., older DB drivers)
- CPU-bound work (use ProcessPoolExecutor)
- File I/O without async libs
- Blocking system calls

**HOW — Basic usage:**

```python
import asyncio
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
import time

def blocking_operation(x):
    """Sync function that blocks."""
    time.sleep(1)  # Simulates I/O
    return x * 2


async def main():
    loop = asyncio.get_running_loop()

    # ⭐ Option 1: Default executor (ThreadPoolExecutor)
    result = await loop.run_in_executor(None, blocking_operation, 5)
    print(result)  # 10

    # ⭐ Option 2: Custom executor (more control)
    with ThreadPoolExecutor(max_workers=4) as executor:
        result = await loop.run_in_executor(executor, blocking_operation, 5)


# ⭐ Modern (Python 3.9+): asyncio.to_thread (simpler)
async def modern():
    result = await asyncio.to_thread(blocking_operation, 5)
    return result
```

**HOW — CPU-bound work (ProcessPoolExecutor):**

```python
import math

def cpu_heavy(n):
    """CPU-bound — needs ProcessPoolExecutor (bypass GIL)."""
    return sum(math.sqrt(i) for i in range(n))


async def main():
    loop = asyncio.get_running_loop()

    # ⭐ ProcessPoolExecutor for CPU work (true parallelism)
    with ProcessPoolExecutor(max_workers=4) as executor:
        results = await asyncio.gather(*[
            loop.run_in_executor(executor, cpu_heavy, 1_000_000)
            for _ in range(4)
        ])
        # ⭐ Runs on 4 CPU cores in parallel (no GIL contention)
```

**HOW — Bridge async to sync (rare reverse case):**

```python
import asyncio

async def async_function():
    return "async result"

def sync_caller():
    # ⭐ Run async in sync context
    result = asyncio.run(async_function())
    return result

# Or with existing loop
def sync_caller_with_loop():
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(async_function())
    finally:
        loop.close()
```

---

### Q5: Async iterators + generators — production patterns?

**Answer:**

**WHAT:** `async for` over async iterables + `yield` in async functions.

**WHY:**
- Stream large data without loading into memory
- Database cursors
- API pagination
- WebSocket message streams

**HOW — Async generator (most common):**

```python
import asyncio
from typing import AsyncIterator

async def stream_users(batch_size: int = 100) -> AsyncIterator[dict]:
    """Async generator — yields users one at a time."""
    offset = 0
    while True:
        users = await db.fetch(
            "SELECT * FROM users LIMIT $1 OFFSET $2",
            batch_size, offset
        )
        if not users:
            break
        for user in users:
            yield user  # ⭐ yield works in async def
        offset += batch_size


# Consume
async def main():
    async for user in stream_users():
        print(user["email"])
        await process_user(user)
```

**HOW — Async iterator class:**

```python
class AsyncPaginator:
    """Custom async iterator class."""
    def __init__(self, url: str, page_size: int = 100):
        self.url = url
        self.page = 0
        self.page_size = page_size
        self.buffer = []

    def __aiter__(self):
        return self

    async def __anext__(self):
        if not self.buffer:
            # Fetch next page
            response = await httpx.get(f"{self.url}?page={self.page}")
            self.buffer = response.json()["items"]
            self.page += 1

            if not self.buffer:
                raise StopAsyncIteration

        return self.buffer.pop(0)


# Usage
async def main():
    async for item in AsyncPaginator("https://api.example.com/users"):
        print(item)
```

**HOW — Async context manager:**

```python
class AsyncDBConnection:
    """Custom async context manager."""
    async def __aenter__(self):
        self.conn = await asyncpg.connect("postgresql://...")
        return self.conn

    async def __aexit__(self, exc_type, exc, tb):
        await self.conn.close()


# Usage
async def main():
    async with AsyncDBConnection() as conn:
        users = await conn.fetch("SELECT * FROM users")


# ⭐ Simpler: @asynccontextmanager decorator
from contextlib import asynccontextmanager

@asynccontextmanager
async def get_db():
    conn = await asyncpg.connect("postgresql://...")
    try:
        yield conn
    finally:
        await conn.close()


# Usage
async def main():
    async with get_db() as conn:
        users = await conn.fetch("SELECT * FROM users")
```

---

### Q6: Semaphore + Rate limiting in async?

**Answer:**

**WHAT:** asyncio.Semaphore limits concurrent tasks.

**WHY:**
- API rate limits (max 10 concurrent)
- Connection pool limits
- Memory limits (don't load 10000 items at once)

**HOW:**

```python
import asyncio
import httpx

async def fetch_with_limit(url: str, semaphore: asyncio.Semaphore):
    async with semaphore:  # ⭐ Acquire slot
        async with httpx.AsyncClient() as client:
            response = await client.get(url)
        return response.json()


async def main():
    urls = [f"https://api.example.com/items/{i}" for i in range(1000)]

    # ⭐ Max 10 concurrent fetches (others queue)
    semaphore = asyncio.Semaphore(10)

    # All 1000 tasks created, but only 10 run at once
    results = await asyncio.gather(*[
        fetch_with_limit(url, semaphore)
        for url in urls
    ])
```

**HOW — Token bucket rate limiter:**

```python
import asyncio
import time

class AsyncRateLimiter:
    """
    Rate limit: N requests per second.
    Uses token bucket.
    """
    def __init__(self, rate: int, per_seconds: float = 1.0):
        self.rate = rate
        self.per = per_seconds
        self.tokens = rate
        self.last_refill = time.monotonic()
        self.lock = asyncio.Lock()

    async def acquire(self):
        async with self.lock:
            now = time.monotonic()
            elapsed = now - self.last_refill
            # Refill tokens
            self.tokens = min(self.rate, self.tokens + elapsed * (self.rate / self.per))
            self.last_refill = now

            if self.tokens >= 1:
                self.tokens -= 1
                return

            # Wait for next token
            wait_time = (1 - self.tokens) * (self.per / self.rate)
            await asyncio.sleep(wait_time)
            self.tokens = 0


# Usage
limiter = AsyncRateLimiter(rate=10, per_seconds=1)  # 10 req/sec

async def rate_limited_call(url):
    await limiter.acquire()
    return await httpx.get(url)
```

---

### Q7: Backpressure handling — slow consumer?

**Answer:**

**WHAT:** Mechanism to signal "slow down" when consumer can't keep up.

**WHY:**
```
Fast producer + slow consumer = memory explosion
- Producer: 10K msg/sec
- Consumer: 100 msg/sec
- Without backpressure: queue grows unbounded → OOM
```

**HOW — Pattern 1: Bounded queue (automatic backpressure)**

```python
async def main():
    # ⭐ maxsize=100 → producer blocks when queue full
    queue = asyncio.Queue(maxsize=100)

    async def producer():
        for i in range(1_000_000):
            await queue.put(i)  # Blocks if queue full
            # Implicit rate limiting

    async def consumer():
        while True:
            item = await queue.get()
            await slow_process(item)
            queue.task_done()
```

**HOW — Pattern 2: Drop old items (sampling)**

```python
class DroppingQueue:
    """Keep only latest N items (drop oldest)."""
    def __init__(self, maxsize: int):
        self._queue = asyncio.Queue(maxsize=maxsize)
        self._maxsize = maxsize

    async def put(self, item):
        if self._queue.full():
            try:
                # Drop oldest
                self._queue.get_nowait()
                self._queue.task_done()
            except asyncio.QueueEmpty:
                pass
        await self._queue.put(item)

    async def get(self):
        return await self._queue.get()
```

**HOW — Pattern 3: Adaptive throttling**

```python
class AdaptiveProducer:
    """Slow down when consumer falls behind."""
    def __init__(self, queue):
        self.queue = queue
        self.sleep_time = 0.0

    async def produce(self, items):
        for item in items:
            # ⭐ Adjust sleep based on queue depth
            depth_ratio = self.queue.qsize() / self.queue.maxsize
            if depth_ratio > 0.8:
                self.sleep_time = min(self.sleep_time + 0.01, 1.0)
            elif depth_ratio < 0.2:
                self.sleep_time = max(self.sleep_time - 0.01, 0)

            await self.queue.put(item)
            if self.sleep_time > 0:
                await asyncio.sleep(self.sleep_time)
```

---

### Q8: Graceful shutdown — async server pattern?

**Answer:**

**WHAT:** Cleanly stop async app on SIGTERM/SIGINT.

**WHY:**
- Don't drop in-flight requests
- Close DB connections cleanly
- Flush logs/metrics
- K8s/Docker need this

**HOW:**

```python
import asyncio
import signal

class AsyncServer:
    def __init__(self):
        self.tasks = []
        self.shutdown_event = asyncio.Event()

    async def start(self):
        # Register signal handlers
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(
                sig,
                lambda: asyncio.create_task(self.shutdown())
            )

        # Start workers
        for i in range(10):
            task = asyncio.create_task(self.worker(i))
            self.tasks.append(task)

        # Wait for shutdown
        await self.shutdown_event.wait()

        # ⭐ Cancel all tasks
        for task in self.tasks:
            task.cancel()

        # ⭐ Wait for cleanup (with timeout)
        await asyncio.gather(*self.tasks, return_exceptions=True)

    async def shutdown(self):
        print("Shutdown signal received")
        self.shutdown_event.set()

    async def worker(self, worker_id):
        try:
            while True:
                # Do work
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            print(f"Worker {worker_id} cleaning up...")
            await self.cleanup_resources()
            raise


async def main():
    server = AsyncServer()
    await server.start()


asyncio.run(main())
```

**HOW — FastAPI lifespan (newer pattern):**

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    print("Starting up...")
    app.state.db = await asyncpg.create_pool("postgresql://...")
    app.state.redis = await aioredis.from_url("redis://...")

    yield  # ⭐ Server runs here

    # Shutdown (graceful)
    print("Shutting down...")
    await app.state.db.close()
    await app.state.redis.close()


app = FastAPI(lifespan=lifespan)
```

---

### Q9: Common asyncio bugs + debugging?

**Answer:**

**Bug 1: Forgetting await**
```python
# ❌ WRONG
async def main():
    result = fetch_data()  # ⚠️ Returns coroutine, not result!
    print(result)  # <coroutine object ...>

# ✅ CORRECT
async def main():
    result = await fetch_data()
```

**Bug 2: Running sync code in async**
```python
# ❌ WRONG — blocks entire event loop
async def handler():
    time.sleep(5)  # ⚠️ Blocks ALL other coroutines!

# ✅ CORRECT
async def handler():
    await asyncio.sleep(5)
# OR for true blocking lib:
async def handler():
    await asyncio.to_thread(blocking_lib_call)
```

**Bug 3: Not handling CancelledError**
```python
# ❌ WRONG — silently swallows cancel
async def task():
    try:
        await long_op()
    except Exception:
        pass  # ⚠️ Catches CancelledError too

# ✅ CORRECT
async def task():
    try:
        await long_op()
    except asyncio.CancelledError:
        raise  # ⭐ Re-raise cancellation
    except Exception as e:
        handle(e)
```

**Bug 4: Creating task without awaiting/storing**
```python
# ❌ WRONG — task may be garbage collected
async def main():
    asyncio.create_task(background_work())  # ⚠️ Reference lost!
    await main_work()

# ✅ CORRECT
async def main():
    bg_task = asyncio.create_task(background_work())
    await main_work()
    await bg_task
```

**Bug 5: Mixing event loops**
```python
# ❌ WRONG — multiple loops
loop1 = asyncio.new_event_loop()
loop2 = asyncio.new_event_loop()
# ⚠️ Tasks from loop1 can't run on loop2

# ✅ CORRECT — single loop via asyncio.run
asyncio.run(main())
```

**HOW — Debug tools:**

```python
# Enable debug mode
import asyncio
asyncio.run(main(), debug=True)
# Logs slow tasks (>100ms), unawaited coroutines

# Or env var
# PYTHONASYNCIODEBUG=1 python main.py


# Detect blocking callbacks
loop = asyncio.get_event_loop()
loop.slow_callback_duration = 0.1  # Log if callback >100ms


# Get all tasks
all_tasks = asyncio.all_tasks()
for task in all_tasks:
    print(f"Task: {task.get_name()}, State: {task.done()}")


# Task introspection (3.12+)
task = asyncio.current_task()
print(task.get_stack())
print(task.cancelling())  # Cancel count
```

---

## Production Async Checklist

```markdown
### Patterns
- [ ] Use TaskGroup over gather (3.11+)
- [ ] asyncio.timeout context manager (3.11+)
- [ ] Bounded queues for backpressure
- [ ] Semaphore for concurrent limits
- [ ] Graceful shutdown handlers (SIGTERM)

### Performance
- [ ] uvloop installed (2-4x faster)
- [ ] asyncio.to_thread for blocking calls
- [ ] ProcessPoolExecutor for CPU work
- [ ] httpx not requests
- [ ] asyncpg not psycopg2

### Error Handling
- [ ] CancelledError re-raised (not swallowed)
- [ ] Shield critical operations
- [ ] return_exceptions=True for gather (where needed)
- [ ] ExceptionGroup handling (3.11+)

### Debugging
- [ ] Debug mode in dev (asyncio.run(debug=True))
- [ ] Slow callback monitoring
- [ ] Task naming (asyncio.create_task(..., name="..."))

### Common Bugs Avoided
- [ ] All coroutines awaited
- [ ] No time.sleep / blocking calls in async
- [ ] Tasks stored (not lost to GC)
- [ ] Single event loop
- [ ] DB pools closed on shutdown
```

---

## uvloop — Production Drop-in Replacement

```python
# pip install uvloop

import uvloop
import asyncio

# ⭐ One line — 2-4x faster
uvloop.install()

# Now asyncio.run uses uvloop
asyncio.run(main())


# Or explicitly
uvloop.run(main())  # Python 3.12+
```

Benefits:
- Built on libuv (Node.js event loop)
- 2-4x faster than asyncio default
- Drop-in (no code changes)
- Used by FastAPI, Sanic in production
