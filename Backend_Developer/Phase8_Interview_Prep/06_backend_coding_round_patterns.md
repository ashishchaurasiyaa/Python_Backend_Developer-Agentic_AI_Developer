# Backend Coding Round Patterns — Implementation Recipes

> What gets asked in 45-min coding rounds for backend engineer roles.
> Pattern → full working code → edge cases → "what if I scale this?"

---

## Pattern 1 — Rate Limiter (Token Bucket)

**Ask:** "Implement an in-memory rate limiter: max N requests per second per user."

```python
import time
from threading import Lock
from collections import defaultdict

class TokenBucket:
    def __init__(self, capacity: int, refill_rate: float):
        self.capacity = capacity
        self.refill_rate = refill_rate  # tokens/sec
        self.tokens = capacity
        self.last_refill = time.monotonic()
        self.lock = Lock()

    def allow(self) -> bool:
        with self.lock:
            now = time.monotonic()
            elapsed = now - self.last_refill
            self.tokens = min(self.capacity, self.tokens + elapsed * self.refill_rate)
            self.last_refill = now
            if self.tokens >= 1:
                self.tokens -= 1
                return True
            return False


class RateLimiter:
    def __init__(self, capacity: int, refill_rate: float):
        self.capacity = capacity
        self.refill_rate = refill_rate
        self.buckets: dict[str, TokenBucket] = defaultdict(
            lambda: TokenBucket(capacity, refill_rate)
        )

    def allow(self, user_id: str) -> bool:
        return self.buckets[user_id].allow()
```

**Edge cases interviewers probe:**
- Thread safety → Lock ✓.
- Clock skew → use `monotonic()` not `time()`.
- Memory leak (unbounded users) → add LRU eviction or TTL on buckets.
- Distributed → use Redis with Lua script (atomic).

---

## Pattern 2 — LRU Cache (from scratch, O(1))

**Ask:** "Implement an LRU cache with `get` and `put` in O(1)."

```python
class Node:
    __slots__ = ("key", "value", "prev", "next")
    def __init__(self, key=None, value=None):
        self.key = key
        self.value = value
        self.prev = None
        self.next = None

class LRUCache:
    def __init__(self, capacity: int):
        self.cap = capacity
        self.map: dict[int, Node] = {}
        # Sentinel head <-> tail. head.next = MRU, tail.prev = LRU.
        self.head = Node()
        self.tail = Node()
        self.head.next = self.tail
        self.tail.prev = self.head

    def _remove(self, node: Node):
        node.prev.next = node.next
        node.next.prev = node.prev

    def _add_front(self, node: Node):
        node.next = self.head.next
        node.prev = self.head
        self.head.next.prev = node
        self.head.next = node

    def get(self, key: int) -> int:
        if key not in self.map:
            return -1
        node = self.map[key]
        self._remove(node)
        self._add_front(node)
        return node.value

    def put(self, key: int, value: int) -> None:
        if key in self.map:
            self._remove(self.map[key])
        node = Node(key, value)
        self._add_front(node)
        self.map[key] = node
        if len(self.map) > self.cap:
            lru = self.tail.prev
            self._remove(lru)
            del self.map[lru.key]
```

**Variations interviewers ask:**
- LFU (least frequently used) — extra freq counter, harder.
- LRU with TTL — store expiry, lazy-delete on access.
- Thread-safe LRU — wrap with `threading.RLock`.
- Use `collections.OrderedDict` (shortcut for Python — `move_to_end`).

---

## Pattern 3 — Sliding Window Rate Limiter (Redis-backed)

**Ask:** "Rate limit 100 req/min per user, must survive process restart."

```python
import time
import redis.asyncio as redis

LUA_SLIDING = """
local key = KEYS[1]
local now = tonumber(ARGV[1])
local window = tonumber(ARGV[2])
local limit = tonumber(ARGV[3])

redis.call('ZREMRANGEBYSCORE', key, '-inf', now - window)
local count = redis.call('ZCARD', key)
if count < limit then
    redis.call('ZADD', key, now, now)
    redis.call('EXPIRE', key, window)
    return 1
end
return 0
"""

class SlidingWindowLimiter:
    def __init__(self, r: redis.Redis, limit: int = 100, window_sec: int = 60):
        self.r = r
        self.limit = limit
        self.window = window_sec
        self._script = None

    async def _load_script(self):
        if not self._script:
            self._script = await self.r.script_load(LUA_SLIDING)

    async def allow(self, user_id: str) -> bool:
        await self._load_script()
        now_ms = int(time.time() * 1000)
        result = await self.r.evalsha(
            self._script, 1,
            f"rl:{user_id}", now_ms, self.window * 1000, self.limit
        )
        return bool(result)
```

**Why Lua:** atomicity — `ZCARD` + `ZADD` are one operation, no race.

---

## Pattern 4 — Async Concurrency Limiter

**Ask:** "Download 10,000 URLs but only 10 at a time."

```python
import asyncio
import httpx

async def fetch(client: httpx.AsyncClient, url: str, sem: asyncio.Semaphore):
    async with sem:
        try:
            r = await client.get(url, timeout=10)
            return url, r.status_code, len(r.content)
        except Exception as e:
            return url, None, str(e)

async def fetch_all(urls: list[str], concurrency: int = 10):
    sem = asyncio.Semaphore(concurrency)
    async with httpx.AsyncClient() as client:
        tasks = [fetch(client, u, sem) for u in urls]
        return await asyncio.gather(*tasks, return_exceptions=False)
```

**Edge cases:**
- Use `return_exceptions=True` if you want partial results on error.
- `asyncio.as_completed()` if you want results as they finish.
- Don't create one client per request → pool reuse via `AsyncClient()`.

---

## Pattern 5 — Retry with Exponential Backoff + Jitter

```python
import asyncio
import random
from typing import Callable, Awaitable, TypeVar

T = TypeVar("T")

async def retry_async(
    fn: Callable[[], Awaitable[T]],
    max_attempts: int = 5,
    base: float = 1.0,
    cap: float = 30.0,
    retryable_excs: tuple = (Exception,),
) -> T:
    last_exc = None
    for attempt in range(max_attempts):
        try:
            return await fn()
        except retryable_excs as e:
            last_exc = e
            if attempt == max_attempts - 1:
                raise
            # Exponential backoff with full jitter
            delay = min(cap, base * (2 ** attempt))
            sleep_for = random.uniform(0, delay)
            await asyncio.sleep(sleep_for)
    raise last_exc
```

**Why jitter:** Without it, 1000 clients retry at exactly 1s, 2s, 4s → thundering herd.

**Don't retry:** 4xx (client error), idempotency-unsafe POSTs without idempotency key.

---

## Pattern 6 — Connection Pool

```python
import asyncio
from contextlib import asynccontextmanager

class ConnectionPool:
    def __init__(self, factory, min_size=2, max_size=10):
        self.factory = factory
        self.min_size = min_size
        self.max_size = max_size
        self._pool: asyncio.Queue = asyncio.Queue(maxsize=max_size)
        self._size = 0
        self._lock = asyncio.Lock()

    async def _maybe_create(self):
        async with self._lock:
            if self._size < self.max_size and self._pool.empty():
                self._size += 1
                conn = await self.factory()
                await self._pool.put(conn)

    @asynccontextmanager
    async def acquire(self):
        await self._maybe_create()
        conn = await self._pool.get()
        try:
            yield conn
        finally:
            await self._pool.put(conn)

    async def close(self):
        while not self._pool.empty():
            conn = await self._pool.get()
            await conn.close()

# Usage
pool = ConnectionPool(factory=lambda: asyncpg.connect(DSN))
async with pool.acquire() as conn:
    await conn.execute("...")
```

**Edge cases:**
- Connection death → ping before use, evict dead.
- Idle timeout → cull connections older than 10min.
- Pool exhaustion → timeout on `get()`.

---

## Pattern 7 — Circuit Breaker

```python
import time
from enum import Enum
from threading import Lock

class State(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"

class CircuitBreaker:
    def __init__(self, failure_threshold: int = 5, timeout: float = 30.0):
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.failure_count = 0
        self.state = State.CLOSED
        self.opened_at = 0.0
        self.lock = Lock()

    def call(self, fn, *args, **kwargs):
        with self.lock:
            if self.state == State.OPEN:
                if time.monotonic() - self.opened_at > self.timeout:
                    self.state = State.HALF_OPEN
                else:
                    raise CircuitOpenError()

        try:
            result = fn(*args, **kwargs)
        except Exception:
            self._on_failure()
            raise
        else:
            self._on_success()
            return result

    def _on_failure(self):
        with self.lock:
            self.failure_count += 1
            if self.failure_count >= self.failure_threshold:
                self.state = State.OPEN
                self.opened_at = time.monotonic()

    def _on_success(self):
        with self.lock:
            self.failure_count = 0
            self.state = State.CLOSED


class CircuitOpenError(Exception):
    pass
```

**Production:** Use `pybreaker` or `purgatory` libs.

---

## Pattern 8 — Bounded Producer-Consumer

```python
import asyncio
import random

async def producer(queue: asyncio.Queue, items: list):
    for item in items:
        await queue.put(item)
    await queue.put(None)  # poison pill

async def consumer(queue: asyncio.Queue, name: str):
    while True:
        item = await queue.get()
        if item is None:
            await queue.put(None)  # signal other consumers
            break
        await asyncio.sleep(random.random())  # process
        print(f"{name}: {item}")
        queue.task_done()

async def main():
    queue = asyncio.Queue(maxsize=10)  # bounded!
    items = list(range(100))
    await asyncio.gather(
        producer(queue, items),
        consumer(queue, "C1"),
        consumer(queue, "C2"),
        consumer(queue, "C3"),
    )
```

**Why bounded:** unbounded queue → producer outpaces consumer → memory explosion.

---

## Pattern 9 — Token Bucket vs Leaky Bucket (Implement Both)

```python
# Leaky bucket (queue-based, smooths bursts to constant rate)
import asyncio

class LeakyBucket:
    def __init__(self, rate: float, capacity: int):
        self.rate = rate  # leaks per second
        self.capacity = capacity
        self.q = asyncio.Queue(maxsize=capacity)
        asyncio.create_task(self._leak())

    async def _leak(self):
        while True:
            await asyncio.sleep(1 / self.rate)
            try:
                self.q.get_nowait()
                self.q.task_done()
            except asyncio.QueueEmpty:
                pass

    async def add(self, item) -> bool:
        try:
            self.q.put_nowait(item)
            return True
        except asyncio.QueueFull:
            return False
```

**Difference:**
- Token bucket: allows burst up to capacity, then steady.
- Leaky bucket: always steady output, no bursts.

---

## Pattern 10 — Trie for Autocomplete

```python
class TrieNode:
    __slots__ = ("children", "is_word", "word_freq")
    def __init__(self):
        self.children: dict[str, TrieNode] = {}
        self.is_word = False
        self.word_freq = 0

class Autocomplete:
    def __init__(self):
        self.root = TrieNode()

    def insert(self, word: str, freq: int = 1):
        node = self.root
        for ch in word:
            node = node.children.setdefault(ch, TrieNode())
        node.is_word = True
        node.word_freq += freq

    def suggest(self, prefix: str, k: int = 10) -> list[str]:
        node = self.root
        for ch in prefix:
            if ch not in node.children:
                return []
            node = node.children[ch]

        results = []
        self._dfs(node, prefix, results)
        results.sort(key=lambda x: -x[1])
        return [w for w, _ in results[:k]]

    def _dfs(self, node, path, results):
        if node.is_word:
            results.append((path, node.word_freq))
        for ch, child in node.children.items():
            self._dfs(child, path + ch, results)
```

**Scaling:** For 100M words, use compressed trie (radix tree) or Elasticsearch completion suggester.

---

## Pattern 11 — Webhook Signature Verification

```python
import hmac
import hashlib
import time

def verify_webhook(
    body: bytes,
    signature_header: str,
    secret: str,
    max_age_sec: int = 300,
) -> bool:
    # signature_header = "t=1234567890,v1=abc..."
    parts = dict(p.split("=", 1) for p in signature_header.split(","))
    timestamp = int(parts["t"])
    received_sig = parts["v1"]

    # Reject old (replay attack)
    if abs(time.time() - timestamp) > max_age_sec:
        return False

    # Recompute
    payload = f"{timestamp}.{body.decode()}".encode()
    expected = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()

    # Constant-time compare (no timing leak)
    return hmac.compare_digest(expected, received_sig)
```

**Why HMAC, not plain hash:** prevents length-extension attacks. Why constant-time: prevents timing side-channel.

---

## Pattern 12 — Distributed Lock (Redis)

```python
import uuid
import redis.asyncio as redis

LUA_RELEASE = """
if redis.call('get', KEYS[1]) == ARGV[1] then
    return redis.call('del', KEYS[1])
end
return 0
"""

class RedisLock:
    def __init__(self, r: redis.Redis, key: str, ttl: int = 30):
        self.r = r
        self.key = f"lock:{key}"
        self.ttl = ttl
        self.token = uuid.uuid4().hex

    async def acquire(self) -> bool:
        return bool(await self.r.set(self.key, self.token, nx=True, ex=self.ttl))

    async def release(self):
        await self.r.eval(LUA_RELEASE, 1, self.key, self.token)

    async def __aenter__(self):
        if not await self.acquire():
            raise LockNotAcquired()
        return self

    async def __aexit__(self, *_):
        await self.release()


class LockNotAcquired(Exception):
    pass
```

**Why token:** prevents accidental release of another holder's lock when our work took longer than TTL.

---

## Pattern 13 — Bloom Filter

```python
import math
import mmh3  # murmurhash3
from bitarray import bitarray

class BloomFilter:
    def __init__(self, expected_items: int, false_positive_rate: float = 0.01):
        self.size = self._optimal_size(expected_items, false_positive_rate)
        self.hash_count = self._optimal_hashes(self.size, expected_items)
        self.bits = bitarray(self.size)
        self.bits.setall(False)

    @staticmethod
    def _optimal_size(n, p):
        return int(-n * math.log(p) / (math.log(2) ** 2))

    @staticmethod
    def _optimal_hashes(m, n):
        return max(1, int((m / n) * math.log(2)))

    def add(self, item: str):
        for seed in range(self.hash_count):
            idx = mmh3.hash(item, seed) % self.size
            self.bits[idx] = True

    def __contains__(self, item: str) -> bool:
        for seed in range(self.hash_count):
            idx = mmh3.hash(item, seed) % self.size
            if not self.bits[idx]:
                return False
        return True  # may be false positive!
```

**Use:** Quick "definitely not in DB" check before expensive lookup. Cassandra, URL shortener, content moderation.

---

## Pattern 14 — Consistent Hashing

```python
import hashlib
import bisect

class ConsistentHashRing:
    def __init__(self, nodes: list[str], replicas: int = 100):
        self.replicas = replicas
        self.ring: dict[int, str] = {}
        self.sorted_keys: list[int] = []
        for node in nodes:
            self.add_node(node)

    def _hash(self, key: str) -> int:
        return int(hashlib.md5(key.encode()).hexdigest(), 16)

    def add_node(self, node: str):
        for i in range(self.replicas):
            h = self._hash(f"{node}:{i}")
            self.ring[h] = node
            bisect.insort(self.sorted_keys, h)

    def remove_node(self, node: str):
        for i in range(self.replicas):
            h = self._hash(f"{node}:{i}")
            del self.ring[h]
            self.sorted_keys.remove(h)

    def get_node(self, key: str) -> str:
        if not self.ring:
            return None
        h = self._hash(key)
        idx = bisect.bisect(self.sorted_keys, h) % len(self.sorted_keys)
        return self.ring[self.sorted_keys[idx]]
```

**Why replicas (vnodes):** with 1 hash per node, distribution is uneven; 100-200 vnodes per physical node smooths it.

---

## Pattern 15 — Snowflake ID Generator

```python
import time
import threading

class SnowflakeID:
    """
    64-bit ID: 1 sign + 41 timestamp_ms + 10 worker_id + 12 sequence
    """
    EPOCH = 1704067200000  # 2024-01-01

    def __init__(self, worker_id: int):
        assert 0 <= worker_id < 1024
        self.worker_id = worker_id
        self.sequence = 0
        self.last_ts = -1
        self.lock = threading.Lock()

    def next_id(self) -> int:
        with self.lock:
            ts = int(time.time() * 1000)
            if ts == self.last_ts:
                self.sequence = (self.sequence + 1) & 0xFFF
                if self.sequence == 0:
                    while ts <= self.last_ts:
                        ts = int(time.time() * 1000)
            else:
                self.sequence = 0
            self.last_ts = ts

            return (
                ((ts - self.EPOCH) << 22)
                | (self.worker_id << 12)
                | self.sequence
            )
```

**Why this design:**
- Time-ordered → DB index friendly.
- No DB roundtrip.
- 4096 IDs/ms/worker = 4M/sec/worker.

**Watch out:** Clock skew between workers, NTP backwards-step → halt or wait.

---

## Pattern 16 — Chunked File Upload (Server)

```python
from fastapi import FastAPI, UploadFile, File, Header
import aiofiles
import os

app = FastAPI()

@app.post("/upload/chunk")
async def upload_chunk(
    upload_id: str = Header(...),
    chunk_index: int = Header(...),
    total_chunks: int = Header(...),
    chunk: UploadFile = File(...),
):
    chunk_dir = f"/tmp/uploads/{upload_id}"
    os.makedirs(chunk_dir, exist_ok=True)
    chunk_path = f"{chunk_dir}/{chunk_index:06d}"

    async with aiofiles.open(chunk_path, "wb") as f:
        while data := await chunk.read(1024 * 1024):
            await f.write(data)

    chunks = sorted(os.listdir(chunk_dir))
    if len(chunks) == total_chunks:
        # Assemble
        final = f"/uploads/{upload_id}.bin"
        async with aiofiles.open(final, "wb") as out:
            for cname in chunks:
                async with aiofiles.open(f"{chunk_dir}/{cname}", "rb") as inp:
                    while data := await inp.read(1024 * 1024):
                        await out.write(data)
        # Cleanup
        for c in chunks:
            os.remove(f"{chunk_dir}/{c}")
        os.rmdir(chunk_dir)
        return {"status": "complete", "file": final}
    return {"status": "partial", "received": len(chunks)}
```

**Production:** Use multipart S3 uploads + presigned URLs (don't proxy through your server).

---

## Pattern 17 — Pub/Sub Event Emitter

```python
import asyncio
from collections import defaultdict
from typing import Callable, Awaitable

class EventBus:
    def __init__(self):
        self._subs: dict[str, list[Callable[..., Awaitable]]] = defaultdict(list)

    def subscribe(self, event: str, handler: Callable[..., Awaitable]):
        self._subs[event].append(handler)

    def unsubscribe(self, event: str, handler):
        if handler in self._subs[event]:
            self._subs[event].remove(handler)

    async def publish(self, event: str, *args, **kwargs):
        handlers = list(self._subs.get(event, []))
        # Fire all handlers concurrently, isolate failures
        results = await asyncio.gather(
            *(h(*args, **kwargs) for h in handlers),
            return_exceptions=True,
        )
        for h, r in zip(handlers, results):
            if isinstance(r, Exception):
                print(f"Handler {h.__name__} failed: {r}")
```

**For cross-process:** swap impl with Redis pub/sub, NATS, or Kafka.

---

## Pattern 18 — TTL Cache (with passive eviction)

```python
import time
from collections import OrderedDict

class TTLCache:
    def __init__(self, maxsize: int = 1024, ttl: float = 300):
        self.maxsize = maxsize
        self.ttl = ttl
        self.data: OrderedDict[str, tuple[float, object]] = OrderedDict()

    def get(self, key):
        if key not in self.data:
            return None
        expiry, val = self.data[key]
        if time.monotonic() > expiry:
            del self.data[key]
            return None
        self.data.move_to_end(key)
        return val

    def set(self, key, value):
        self.data[key] = (time.monotonic() + self.ttl, value)
        self.data.move_to_end(key)
        if len(self.data) > self.maxsize:
            self.data.popitem(last=False)  # evict LRU
```

**Active eviction:** Background task periodically sweeps expired keys.

---

## Pattern 19 — Health Check Endpoint

```python
from fastapi import FastAPI, HTTPException
import asyncio

app = FastAPI()

async def check_db():
    try:
        await asyncio.wait_for(db.execute("SELECT 1"), timeout=1.0)
        return True
    except Exception:
        return False

async def check_redis():
    try:
        return await asyncio.wait_for(redis.ping(), timeout=0.5)
    except Exception:
        return False

@app.get("/healthz")  # liveness — minimal
async def liveness():
    return {"status": "ok"}

@app.get("/readyz")   # readiness — full
async def readiness():
    results = await asyncio.gather(check_db(), check_redis())
    healthy = all(results)
    if not healthy:
        raise HTTPException(503, {"db": results[0], "redis": results[1]})
    return {"status": "ready"}
```

**Don't:** put DB check in `/healthz` (liveness). It causes pod restarts during DB hiccups.

---

## Pattern 20 — Backpressure-Aware HTTP Server

```python
from fastapi import FastAPI, HTTPException, Request
import asyncio

app = FastAPI()
semaphore = asyncio.Semaphore(100)  # max 100 concurrent requests

@app.middleware("http")
async def limit_concurrency(request: Request, call_next):
    if not semaphore.locked() or semaphore._value > 0:  # quick check
        async with semaphore:
            return await call_next(request)
    raise HTTPException(503, "Server busy, retry later")
```

**Production:** Use Uvicorn `--limit-concurrency` flag, or LB-level limits (NGINX `limit_conn`).

---

## Pattern 21 — Backoff Iterator (utility)

```python
import random
from typing import Iterator

def backoff(
    base: float = 1.0,
    cap: float = 60.0,
    max_attempts: int = 10,
    jitter: bool = True,
) -> Iterator[float]:
    for attempt in range(max_attempts):
        delay = min(cap, base * (2 ** attempt))
        yield random.uniform(0, delay) if jitter else delay

# Usage
for delay in backoff(base=0.5, cap=30):
    try:
        do_thing()
        break
    except RetryableError:
        await asyncio.sleep(delay)
```

---

## Pattern 22 — JWT Issue + Verify

```python
import jwt
import time

SECRET = "super-secret"

def issue_token(user_id: int, ttl: int = 900) -> str:
    payload = {
        "sub": str(user_id),
        "iat": int(time.time()),
        "exp": int(time.time()) + ttl,
        "iss": "myapp",
    }
    return jwt.encode(payload, SECRET, algorithm="HS256")

def verify_token(token: str) -> dict:
    try:
        return jwt.decode(token, SECRET, algorithms=["HS256"], issuer="myapp")
    except jwt.ExpiredSignatureError:
        raise AuthError("Token expired")
    except jwt.InvalidTokenError as e:
        raise AuthError(str(e))


class AuthError(Exception):
    pass
```

**Production:** RS256 with public/private keys (microservices verify without sharing secret), `jti` claim for revocation list, refresh tokens in DB.

---

## Pattern 23 — Graceful Shutdown

```python
import asyncio
import signal
from contextlib import asynccontextmanager
from fastapi import FastAPI

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    app.state.shutdown_event = asyncio.Event()
    yield
    # Shutdown — drain in-flight requests, close connections
    print("Shutdown signal received, draining...")
    await asyncio.sleep(5)  # let in-flight finish
    await db.close()
    await redis.close()
    print("Drained, exiting.")

app = FastAPI(lifespan=lifespan)
```

**SIGTERM handling:** K8s sends SIGTERM, waits `terminationGracePeriodSeconds` (default 30s), then SIGKILL. Make sure your app exits cleanly within that window.

---

## Pattern 24 — Top-K Elements Stream (Heap)

```python
import heapq
from collections import Counter

class TopK:
    def __init__(self, k: int):
        self.k = k
        self.counts = Counter()
        self.heap = []  # min-heap of (count, item)

    def add(self, item):
        self.counts[item] += 1
        cnt = self.counts[item]
        # Rebuild heap if item already there (lazy approach)
        self.heap = [(c, i) for c, i in self.heap if i != item]
        heapq.heappush(self.heap, (cnt, item))
        if len(self.heap) > self.k:
            heapq.heappop(self.heap)

    def top(self) -> list[tuple]:
        return sorted(self.heap, key=lambda x: -x[0])
```

**At scale:** Count-Min Sketch + heap (approximate but constant memory).

---

## Pattern 25 — Idempotency Middleware

```python
from fastapi import FastAPI, Request, Response
import hashlib, json
import redis.asyncio as redis

app = FastAPI()
r = redis.Redis(decode_responses=True)

@app.middleware("http")
async def idempotency(request: Request, call_next):
    if request.method != "POST":
        return await call_next(request)
    idem_key = request.headers.get("Idempotency-Key")
    if not idem_key:
        return await call_next(request)

    body = await request.body()
    body_hash = hashlib.sha256(body).hexdigest()

    cache_key = f"idem:{idem_key}"
    cached = await r.get(cache_key)
    if cached:
        data = json.loads(cached)
        if data["hash"] != body_hash:
            return Response(status_code=422, content="Idempotency-Key reused with different body")
        return Response(
            status_code=data["status"],
            content=data["body"],
            headers=data["headers"],
        )

    # Process
    response = await call_next(request)
    resp_body = b"".join([chunk async for chunk in response.body_iterator])
    await r.set(
        cache_key,
        json.dumps({
            "hash": body_hash,
            "status": response.status_code,
            "body": resp_body.decode(errors="ignore"),
            "headers": dict(response.headers),
        }),
        ex=86400,
    )
    return Response(content=resp_body, status_code=response.status_code, headers=response.headers)
```

---

## Interview tactics

### Time budget for a 45-min coding round

| Phase | Time | What to do |
|---|---|---|
| Clarify | 5 min | Constraints, throughput, single/multi-thread, in-memory or persisted |
| Design | 5 min | Pick data structures, draw on whiteboard |
| Code | 25 min | Type the solution, narrate while coding |
| Test | 5 min | Walk through 1 happy + 2 edge cases |
| Discuss | 5 min | "How to scale?", complexity, trade-offs |

### Red flags interviewer notices
- Jumping to code without clarification.
- No type hints.
- No edge case handling (empty input, null, max size).
- Silent thinking — narrate.
- Defending wrong answer instead of accepting feedback.

### Green signals
- "Let me clarify before I start."
- "Time complexity: O(N log N). Can we do better? Let me think..."
- "I'd add a unit test for this edge case in real code."
- "In production, I'd replace this with `Redis.SET NX EX` for distributed-safety."
