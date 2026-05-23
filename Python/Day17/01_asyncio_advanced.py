"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ASYNCIO ADVANCED — Semaphore, Queue, TaskGroup, Timeout
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

ALREADY COVERED (Day14):
  ✓ async/await basics
  ✓ asyncio.gather()
  ✓ aiohttp
  ✓ race condition, deadlock

THIS FILE — ADVANCED PATTERNS:
  asyncio.Semaphore     → limit concurrent tasks
  asyncio.Queue         → async producer/consumer
  asyncio.TaskGroup     → structured concurrency (Python 3.11+)
  asyncio.timeout       → cancel slow tasks
  asyncio.Event         → synchronize coroutines
  asyncio.create_task   → background tasks
  asyncio.to_thread     → run blocking code in thread pool

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import asyncio
import time
import random
import httpx

# ━━━━━━━━━━━━━━━━━━━━━━━━━━
# 1. SEMAPHORE — LIMIT CONCURRENCY
# ━━━━━━━━━━━━━━━━━━━━━━━━━━

"""
INTERVIEW Q: asyncio.Semaphore kab use karte hain?
A: When you want CONCURRENT execution but limited at a time.
   Example: 100 URLs ko fetch karna but max 10 at a time
   (respect API rate limits, avoid overwhelming server)
"""

async def fetch_url(session: httpx.AsyncClient, url: str, sem: asyncio.Semaphore) -> dict:
    async with sem:                             # acquire semaphore — blocks if 10 already running
        print(f"Fetching: {url}")
        try:
            response = await session.get(url, timeout=10)
            return {"url": url, "status": response.status_code}
        except Exception as e:
            return {"url": url, "error": str(e)}


async def fetch_all_with_limit(urls: list[str], max_concurrent: int = 10):
    """Fetch all URLs, max 10 at a time."""
    semaphore = asyncio.Semaphore(max_concurrent)

    async with httpx.AsyncClient() as session:
        tasks = [fetch_url(session, url, semaphore) for url in urls]
        results = await asyncio.gather(*tasks, return_exceptions=True)

    return results


# Without semaphore (WRONG for 1000 URLs):
# tasks = [fetch(url) for url in 1000_urls]  # 1000 concurrent requests!
# await asyncio.gather(*tasks)               # overwhelms server/rate limit

# ━━━━━━━━━━━━━━━━━━━━━━━━━━
# 2. ASYNCIO.QUEUE — PRODUCER/CONSUMER
# ━━━━━━━━━━━━━━━━━━━━━━━━━━

"""
INTERVIEW Q: asyncio.Queue kab use karte hain?
A: Async producer/consumer pattern.
   Producer generates work items.
   Consumer processes them.
   Queue decouples them — producer doesn't wait for consumer.
"""

async def producer(queue: asyncio.Queue, items: list):
    """Put items into queue."""
    for item in items:
        await queue.put(item)
        print(f"Produced: {item}")
        await asyncio.sleep(0.01)   # simulate production delay

    # Signal consumers to stop (sentinel)
    await queue.put(None)

async def consumer(queue: asyncio.Queue, consumer_id: int):
    """Process items from queue."""
    while True:
        item = await queue.get()    # wait until item available

        if item is None:            # sentinel — stop signal
            await queue.put(None)   # forward sentinel to other consumers
            queue.task_done()
            break

        print(f"Consumer {consumer_id} processing: {item}")
        await asyncio.sleep(0.05)   # simulate processing
        queue.task_done()           # MUST call after processing


async def producer_consumer_demo():
    queue = asyncio.Queue(maxsize=10)   # maxsize prevents queue overflow

    items = list(range(20))

    # Start 1 producer + 3 consumers concurrently
    await asyncio.gather(
        producer(queue, items),
        consumer(queue, 1),
        consumer(queue, 2),
        consumer(queue, 3),
    )

    await queue.join()  # wait until all items processed


asyncio.run(producer_consumer_demo())

# ━━━━━━━━━━━━━━━━━━━━━━━━━━
# 3. TASKGROUP — STRUCTURED CONCURRENCY (Python 3.11+)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━

"""
INTERVIEW Q: TaskGroup vs gather() difference?
A: gather() — one exception → others still running → messy cleanup
   TaskGroup → one exception → ALL tasks cancelled → clean
   TaskGroup = safer, more structured concurrency
"""

async def fetch_with_taskgroup(urls: list[str]) -> list[str]:
    results = []

    async with asyncio.TaskGroup() as tg:
        async def fetch(url):
            async with httpx.AsyncClient() as c:
                r = await c.get(url)
                results.append(r.text[:50])

        for url in urls:
            tg.create_task(fetch(url))
        # If ANY task raises exception → all cancelled → exception propagates

    return results

# ━━━━━━━━━━━━━━━━━━━━━━━━━━
# 4. TIMEOUT — CANCEL SLOW TASKS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━

async def slow_api_call(delay: float) -> str:
    await asyncio.sleep(delay)
    return f"Result after {delay}s"


# Method 1: asyncio.timeout (Python 3.11+)
async def with_timeout_new():
    try:
        async with asyncio.timeout(2.0):    # cancel if takes > 2s
            result = await slow_api_call(1.0)
            print(result)
    except TimeoutError:
        print("Request timed out!")

# Method 2: asyncio.wait_for (older Python)
async def with_timeout_old():
    try:
        result = await asyncio.wait_for(slow_api_call(5.0), timeout=2.0)
    except asyncio.TimeoutError:
        print("Timed out!")

asyncio.run(with_timeout_old())

# ━━━━━━━━━━━━━━━━━━━━━━━━━━
# 5. CREATE_TASK — BACKGROUND TASKS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━

"""
INTERVIEW Q: create_task vs gather vs await — difference?
A: await coro()         → run ONE coroutine, wait for it
   asyncio.gather()     → run MULTIPLE coroutines, wait for ALL
   asyncio.create_task()→ SCHEDULE coroutine to run concurrently,
                          DON'T wait — get Task object, use later

   create_task = "fire and continue" (background job pattern)
"""

async def background_demo():
    async def send_email(to: str, subject: str):
        await asyncio.sleep(2)      # slow operation
        print(f"Email sent to {to}")

    # Without create_task — sequential
    print("User registered")
    # await send_email("user@example.com", "Welcome!")  # blocks 2s!
    # return response

    # With create_task — concurrent
    print("User registered")
    task = asyncio.create_task(
        send_email("user@example.com", "Welcome!")
    )
    # Return response IMMEDIATELY — email sends in background
    print("Response returned to user (email sending in background)")

    # Optionally wait later
    await task
    print("Email confirmed sent")

asyncio.run(background_demo())

# ━━━━━━━━━━━━━━━━━━━━━━━━━━
# 6. TO_THREAD — BLOCKING CODE IN ASYNC CONTEXT
# ━━━━━━━━━━━━━━━━━━━━━━━━━━

"""
INTERVIEW Q: asyncio mein blocking library (requests, pandas) kaise use karein?
A: asyncio.to_thread() — runs in thread pool, doesn't block event loop.
"""

import requests  # BLOCKING library

async def fetch_blocking_safe(url: str) -> str:
    """Run blocking requests in thread pool."""
    response = await asyncio.to_thread(requests.get, url)
    return response.text[:100]

# Equivalent to:
# loop = asyncio.get_event_loop()
# response = await loop.run_in_executor(None, requests.get, url)

async def main_blocking_demo():
    # Run multiple blocking calls concurrently (each in own thread)
    results = await asyncio.gather(
        asyncio.to_thread(requests.get, "https://httpbin.org/get"),
        asyncio.to_thread(requests.get, "https://httpbin.org/ip"),
    )
    for r in results:
        print(r.status_code)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━
# 7. EVENT — COROUTINE SYNCHRONIZATION
# ━━━━━━━━━━━━━━━━━━━━━━━━━━

async def event_demo():
    event = asyncio.Event()

    async def waiter(name: str):
        print(f"{name}: waiting for event...")
        await event.wait()              # blocks until event.set()
        print(f"{name}: event received, continuing!")

    async def setter():
        await asyncio.sleep(1)          # simulate some work
        print("Setting event!")
        event.set()                     # all waiters unblocked

    await asyncio.gather(
        waiter("Task 1"),
        waiter("Task 2"),
        waiter("Task 3"),
        setter(),
    )

asyncio.run(event_demo())

# ━━━━━━━━━━━━━━━━━━━━━━━━━━
# 8. REAL-WORLD: RATE-LIMITED API CLIENT
# ━━━━━━━━━━━━━━━━━━━━━━━━━━

class RateLimitedAPIClient:
    """
    API client that:
    - Limits to max_concurrent simultaneous requests
    - Retries on failure with exponential backoff
    - Tracks total requests and errors
    """

    def __init__(self, base_url: str, max_concurrent: int = 5):
        self.base_url = base_url
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._total_requests = 0
        self._errors = 0

    async def get(self, path: str, retries: int = 3) -> dict:
        async with self._semaphore:
            self._total_requests += 1
            delay = 1.0

            for attempt in range(retries):
                try:
                    async with httpx.AsyncClient() as client:
                        async with asyncio.timeout(10):
                            r = await client.get(f"{self.base_url}{path}")
                            r.raise_for_status()
                            return r.json()
                except Exception as e:
                    if attempt == retries - 1:
                        self._errors += 1
                        raise
                    await asyncio.sleep(delay)
                    delay *= 2      # exponential backoff

    @property
    def stats(self) -> dict:
        return {"total": self._total_requests, "errors": self._errors}

"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
INTERVIEW Q&A:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Q: asyncio.Semaphore vs threading.Semaphore?
A: asyncio.Semaphore → cooperative, for async code, single thread
   threading.Semaphore → for multi-threaded code, OS-level blocking
   Don't mix them — use asyncio in async code, threading in sync code.

Q: gather() mein ek task fail ho jaye to?
A: By default: exception propagates, other tasks still finish.
   return_exceptions=True: all exceptions returned as results, no crash.
   TaskGroup: any exception → ALL tasks cancelled immediately.

Q: asyncio.Queue maxsize kab use karein?
A: Jab producer bahut fast ho aur consumer slow.
   Without maxsize: queue grows unbounded → memory leak.
   With maxsize: producer blocks when queue full → backpressure.

Q: CPU-bound code ko async mein kaise run karein?
A: asyncio.to_thread() → thread pool (for I/O-bound blocking code)
   loop.run_in_executor(ProcessPoolExecutor()) → process pool (for CPU-bound)
   Don't use to_thread for heavy CPU work — use multiprocessing.
"""
