# Concurrency & Thread Safety — LLD Interview Guide
> **Category:** Must Know | **Frequency:** ★★★★★ | **Mapped to:** Niroskos real concurrency problems

---

## What Interviewers Ask

```
1. "Race condition kya hai — apne project mein kahan tha?"
2. "Double booking kaise rokoge?" → Lock / select_for_update
3. "Deadlock — kya hai, kaise avoid karoge?"
4. "Thread-safe Singleton kaise banate ho?"
5. "Python GIL — kya hota hai, kab problem hai, kab nahi?"
6. "Distributed lock — Redis ka use karo"
7. "Optimistic vs Pessimistic locking — kab kya use karo?"
8. "Producer-Consumer pattern implement karo"
```

---

## PART 1: RACE CONDITION

### Kya hota hai?

```
Two threads ek saath ek hi resource access karte hain →
final result thread execution order pe depend karta hai →
unpredictable / wrong output

Classic example — bank balance:
  balance = 1000
  Thread 1: read(1000) → subtract(200) → write(800)
  Thread 2: read(1000) → subtract(500) → write(500)

  If Thread 2 reads BEFORE Thread 1 writes:
    Both read 1000
    Thread 1 writes 800
    Thread 2 writes 500     ← Thread 1's -200 lost!
  Final balance: 500 (should be 300)

This is the LOST UPDATE problem.
```

### Niroskos mein kahan tha?

```
Double booking problem:
  Safari package capacity = 10 guests
  Two customers book simultaneously for same date

  Request 1: check availability(10 guests) → available ✓ → creating booking...
  Request 2: check availability(10 guests) → available ✓ → creating booking...
  Both succeed → 20 guests booked → capacity exceeded!

  Time window between check and reserve = TOCTOU race condition
  (Time Of Check To Time Of Use)
```

---

## PART 2: PYTHON THREADING PRIMITIVES

```python
import threading
import time
from contextlib import contextmanager
from typing import Optional


# ─── Lock (Mutex) ─────────────────────────────────────────────
# Only one thread at a time — exclusive access

lock = threading.Lock()

# Bad — manual acquire/release (easy to forget release on exception)
lock.acquire()
try:
    shared_resource += 1
finally:
    lock.release()

# Good — context manager (auto-release even on exception)
with lock:
    shared_resource += 1


# ─── RLock (Reentrant Lock) ───────────────────────────────────
# Same thread can acquire multiple times — won't deadlock itself
# Count-based: must release as many times as acquired

rlock = threading.RLock()

def outer():
    with rlock:          # acquire count = 1
        inner()          # same thread — allowed

def inner():
    with rlock:          # acquire count = 2
        do_work()        # both layers acquired
    # release → count = 1
# outer releases → count = 0 → truly free

# Use when: recursive functions or method calls that both need same lock


# ─── Event ────────────────────────────────────────────────────
# Signal between threads — one thread waits, another signals

ready = threading.Event()

def worker():
    ready.wait()         # Block until event set
    print("Worker running!")

def main_thread():
    time.sleep(1)
    ready.set()          # Unblock all waiters

# Clear event to reuse
ready.clear()


# ─── Condition ────────────────────────────────────────────────
# Lock + wait/notify — Producer-Consumer
# More precise than Event — can wake specific waiters

condition = threading.Condition()

def producer(items):
    with condition:
        items.append("new_item")
        condition.notify_all()   # Wake all waiting consumers

def consumer(items):
    with condition:
        while not items:
            condition.wait()     # Release lock + sleep until notified
        item = items.pop()
        return item


# ─── Semaphore ────────────────────────────────────────────────
# Allow N threads simultaneously (not just 1 like Lock)

# Max 3 concurrent DB connections
db_pool = threading.Semaphore(3)

def query_db():
    with db_pool:        # Acquire slot (blocks if all 3 taken)
        result = execute_query()
    return result        # Slot released

# BoundedSemaphore — prevents releasing more than acquired
bounded = threading.BoundedSemaphore(3)  # Raises ValueError if over-released


# ─── Barrier ──────────────────────────────────────────────────
# All N threads reach barrier → all proceed together

barrier = threading.Barrier(3)  # Wait for 3 threads

def phase_one(thread_id):
    do_phase_one_work(thread_id)
    barrier.wait()       # Block until all 3 threads reach here
    do_phase_two_work(thread_id)  # All start phase 2 together


# ─── Timer ────────────────────────────────────────────────────
# Run function after delay (non-blocking)

def cleanup():
    print("Draft expired — releasing resource")

# BookingDraft expiry: 40 minutes
timer = threading.Timer(interval=40 * 60, function=cleanup)
timer.start()
timer.cancel()  # Cancel if booking confirmed before expiry
```

---

## PART 3: COMMON PATTERNS

### 3.1 Thread-Safe Counter

```python
class ThreadSafeCounter:
    """
    Shared counter — multiple threads increment.
    Without lock: lost updates.
    """
    def __init__(self):
        self._value = 0
        self._lock  = threading.Lock()

    def increment(self) -> int:
        with self._lock:
            self._value += 1
            return self._value

    def decrement(self) -> int:
        with self._lock:
            self._value -= 1
            return self._value

    @property
    def value(self) -> int:
        with self._lock:
            return self._value


# ─── Demo: without lock vs with lock ──────────────────────────
import threading

unsafe_counter = 0
safe_counter   = ThreadSafeCounter()

def unsafe_increment():
    global unsafe_counter
    for _ in range(10000):
        unsafe_counter += 1    # read-modify-write — NOT atomic in Python

def safe_increment():
    for _ in range(10000):
        safe_counter.increment()

threads = [threading.Thread(target=unsafe_increment) for _ in range(5)]
for t in threads: t.start()
for t in threads: t.join()
print(f"Unsafe: {unsafe_counter}")   # Should be 50000, likely less (lost updates)

threads = [threading.Thread(target=safe_increment) for _ in range(5)]
for t in threads: t.start()
for t in threads: t.join()
print(f"Safe: {safe_counter.value}")  # Always exactly 50000 ✓
```

### 3.2 Thread-Safe Singleton

```python
class SingletonMeta(type):
    """
    Thread-safe Singleton using double-checked locking.
    _instance check outside lock = fast path (no lock needed after init).
    _instance check inside lock  = race condition safe.
    """
    _instances = {}
    _lock: threading.Lock = threading.Lock()

    def __call__(cls, *args, **kwargs):
        # First check — no lock (fast path for already-created)
        if cls not in cls._instances:
            with cls._lock:
                # Second check — inside lock (race condition safe)
                if cls not in cls._instances:
                    instance = super().__call__(*args, **kwargs)
                    cls._instances[cls] = instance
        return cls._instances[cls]


class RedisClient(metaclass=SingletonMeta):
    def __init__(self):
        print("[REDIS] Connection pool created")
        # self._pool = redis.ConnectionPool(host='redis', port=6379)

redis1 = RedisClient()
redis2 = RedisClient()
print(redis1 is redis2)   # True — same instance
```

### 3.3 Read-Write Lock (RWLock)

```python
class ReadWriteLock:
    """
    Multiple readers simultaneously — no blocking.
    Writers get exclusive access — blocks readers.

    Use: cache (many reads, occasional write invalidation)
    Niroskos: booking cache — many list views (read) vs signal refresh (write)
    """

    def __init__(self):
        self._read_ready  = threading.Condition(threading.Lock())
        self._readers     = 0

    @contextmanager
    def read_lock(self):
        """Multiple threads can hold read lock simultaneously"""
        with self._read_ready:
            self._readers += 1
        try:
            yield
        finally:
            with self._read_ready:
                self._readers -= 1
                if self._readers == 0:
                    self._read_ready.notify_all()

    @contextmanager
    def write_lock(self):
        """Exclusive — blocks until all readers done"""
        with self._read_ready:
            while self._readers > 0:
                self._read_ready.wait()
            yield


# Usage
rwlock = ReadWriteLock()

def read_cache(key):
    with rwlock.read_lock():     # Non-blocking if no writer
        return cache.get(key)

def refresh_cache(key, value):
    with rwlock.write_lock():    # Exclusive — waits for readers
        cache.set(key, value)
```

### 3.4 Producer-Consumer with Queue

```python
import queue

class TaskQueue:
    """
    Producer puts tasks, Consumer gets and processes.
    threading.Queue is thread-safe — no manual locking needed.

    Celery mein: this is exactly what happens.
    Producer: Django app → task.delay()
    Queue: Redis LIST (LPUSH/BRPOP)
    Consumer: Celery Worker
    """

    def __init__(self, maxsize: int = 0):
        # maxsize=0 → unlimited
        # maxsize=N → put() blocks if full (backpressure)
        self._queue: queue.Queue = queue.Queue(maxsize=maxsize)
        self._running = True

    def produce(self, item):
        self._queue.put(item)              # Blocks if maxsize reached
        print(f"[PRODUCER] Enqueued: {item}")

    def consume(self, worker_id: int):
        while self._running:
            try:
                item = self._queue.get(timeout=1.0)   # BRPOP equivalent
                print(f"[WORKER-{worker_id}] Processing: {item}")
                time.sleep(0.1)                        # Simulate work
                self._queue.task_done()               # Mark item done
            except queue.Empty:
                continue   # No item — loop again

    def wait_completion(self):
        self._queue.join()   # Block until all items processed

    def stop(self):
        self._running = False


# Demo
tq = TaskQueue(maxsize=10)

# Start 2 consumer threads
consumers = [
    threading.Thread(target=tq.consume, args=(i,), daemon=True)
    for i in range(2)
]
for c in consumers: c.start()

# Produce 5 tasks
for i in range(5):
    tq.produce(f"task_{i}")

tq.wait_completion()
tq.stop()
```

### 3.5 Double Booking Prevention

```python
import threading
from decimal import Decimal
from datetime import date

class PackageAvailability:
    """
    TOCTOU race: check availability → reserve → confirm
    Lock between check and reserve to prevent double booking.

    Niroskos equivalent:
      select_for_update() on BookingDraft creation
      Row-level DB lock = distributed lock across all web workers
    """

    def __init__(self, capacity: int):
        self.capacity = capacity
        self._booked  = 0
        self._lock    = threading.Lock()

    def book(self, guests: int) -> bool:
        """Atomic check-and-reserve"""
        with self._lock:
            # Check and reserve inside same lock — no TOCTOU
            if self._booked + guests <= self.capacity:
                self._booked += guests
                print(f"[AVAIL] Booked {guests} | Total: {self._booked}/{self.capacity}")
                return True
            print(f"[AVAIL] REJECTED: {guests} guests, only {self.capacity - self._booked} left")
            return False

    def release(self, guests: int) -> None:
        with self._lock:
            self._booked = max(0, self._booked - guests)


# Demo: concurrent booking attempts
avail    = PackageAvailability(capacity=10)
results  = []
res_lock = threading.Lock()

def attempt_booking(guests: int, customer_id: int):
    success = avail.book(guests)
    with res_lock:
        results.append((customer_id, guests, success))

# 5 customers all booking 3 guests each (15 total, capacity=10)
threads = [
    threading.Thread(target=attempt_booking, args=(3, i))
    for i in range(5)
]
for t in threads: t.start()
for t in threads: t.join()

successful = [(c, g) for c, g, s in results if s]
print(f"Successful bookings: {successful}")   # Max 3 (9 guests of 10)
print(f"Total booked: {avail._booked}")        # ≤ 10
```

---

## PART 4: DEADLOCK

### Kya hota hai?

```
Thread A holds Lock 1 → waiting for Lock 2
Thread B holds Lock 2 → waiting for Lock 1
Both waiting forever → deadlock

Example:
  Thread A:
    with lock_account_A:      # acquired
        with lock_account_B:  # waiting...
            transfer(A → B)

  Thread B:
    with lock_account_B:      # acquired
        with lock_account_A:  # waiting...
            transfer(B → A)

  Neither can proceed!
```

### Prevention Strategies

```python
# ─── Strategy 1: Lock Ordering ────────────────────────────────
# Always acquire locks in same order — deadlock impossible

def transfer(from_account, to_account, amount):
    # Sort by ID — always lower ID first
    first  = min(from_account, to_account, key=lambda a: a.id)
    second = max(from_account, to_account, key=lambda a: a.id)

    with first._lock:
        with second._lock:
            from_account.balance -= amount
            to_account.balance   += amount

# Thread A: transfer(A→B) → acquires A first, then B ✓
# Thread B: transfer(B→A) → acquires A first (lower ID), then B ✓
# No circular wait → no deadlock


# ─── Strategy 2: Lock Timeout ─────────────────────────────────
# Try to acquire — give up after timeout

def safe_acquire(lock, timeout=5.0):
    acquired = lock.acquire(blocking=True, timeout=timeout)
    if not acquired:
        raise TimeoutError("Could not acquire lock — possible deadlock")
    return acquired


# ─── Strategy 3: trylock (non-blocking) ───────────────────────
# Try once — if can't get, back off and retry later

def try_acquire_both(lock1, lock2):
    if lock1.acquire(blocking=False):
        if lock2.acquire(blocking=False):
            return True   # Got both
        lock1.release()   # Couldn't get lock2, release lock1
    return False          # Back off, retry later


# ─── Strategy 4: Single Lock for Related Resources ────────────
# One lock covers both — simpler, less deadlock-prone

class BankTransfer:
    _global_lock = threading.Lock()    # One lock for all transfers

    @classmethod
    def transfer(cls, from_acc, to_acc, amount):
        with cls._global_lock:         # Serialized — but safe
            from_acc.balance -= amount
            to_acc.balance   += amount
```

---

## PART 5: PYTHON GIL

```
GIL = Global Interpreter Lock
CPython mein ek time pe sirf ek thread Python bytecode execute kar sakta hai.

Matlab:
  CPU-bound tasks   → threading helps NOTHING (single CPU core used)
  I/O-bound tasks   → threading HELPS (GIL released during I/O wait)

┌─────────────────────────────────────────────────────────┐
│          GIL Release kab hota hai?                      │
├─────────────────────────────────────────────────────────┤
│ ✓ I/O operations    → file read, network call, DB query │
│ ✓ time.sleep()      → explicitly releases               │
│ ✓ C extensions      → numpy, pandas (release GIL)       │
│ ✗ Pure Python code  → loop, calculation, dict ops       │
└─────────────────────────────────────────────────────────┘

Niroskos impact:
  Web workers: Gunicorn with multiple PROCESSES (not threads)
    → each process has its own GIL → true parallelism
  Celery workers: separate processes → no GIL issue
  Django views: I/O-bound (DB, Redis, external API) → threading fine

When to use what:
  I/O-bound → threading.Thread or asyncio
  CPU-bound → multiprocessing.Process (bypasses GIL)
```

```python
import time
import threading
import multiprocessing

# CPU-bound task — GIL means threads won't parallelize this
def cpu_work(n):
    count = 0
    for _ in range(n):
        count += 1
    return count

# I/O-bound task — GIL releases during sleep (simulating DB query)
def io_work(n):
    time.sleep(0.1)    # GIL released here — other threads run
    return n

# Threading benchmark (I/O-bound) — GOOD
start = time.time()
threads = [threading.Thread(target=io_work, args=(1000000,)) for _ in range(4)]
for t in threads: t.start()
for t in threads: t.join()
print(f"Threading I/O: {time.time()-start:.2f}s")  # ~0.1s (concurrent)

# Threading benchmark (CPU-bound) — BAD (GIL)
start = time.time()
threads = [threading.Thread(target=cpu_work, args=(5000000,)) for _ in range(4)]
for t in threads: t.start()
for t in threads: t.join()
print(f"Threading CPU: {time.time()-start:.2f}s")   # ~same as sequential

# Multiprocessing (CPU-bound) — GOOD (bypasses GIL)
start = time.time()
with multiprocessing.Pool(4) as pool:
    pool.map(cpu_work, [5000000] * 4)
print(f"Multiprocessing CPU: {time.time()-start:.2f}s")  # ~4x faster
```

---

## PART 6: DISTRIBUTED LOCKING (Redis)

```python
import time
import uuid
import threading
from typing import Optional

class RedisDistributedLock:
    """
    Multiple server processes → shared Redis lock.
    In-process threading.Lock doesn't help across servers.

    Redis SET NX EX:
      SET key value NX EX seconds
      NX = only set if key Not eXists (atomic check-and-set)
      EX = auto-expire (prevents lock leak on crash)

    Niroskos:
      Payment processing: prevent concurrent payment confirms
      SAP sync: prevent duplicate sync while one is running
      Booking confirmation: prevent double-confirm across web workers
    """

    def __init__(self, redis_client, key: str, expire_seconds: int = 30):
        self._redis   = redis_client
        self._key     = f"lock:{key}"
        self._expire  = expire_seconds
        self._token   = str(uuid.uuid4())    # Unique per lock holder
        self._acquired = False

    def acquire(self, timeout: float = 10.0) -> bool:
        """
        Try to acquire lock within timeout.
        Redis SET key token NX EX 30
        If key doesn't exist → set it → return True (acquired)
        If key exists       → blocked → retry
        """
        deadline = time.time() + timeout
        while time.time() < deadline:
            # Atomic: check-and-set in one Redis command
            # result = self._redis.set(self._key, self._token, nx=True, ex=self._expire)
            result = True   # Simulated for demo
            if result:
                self._acquired = True
                print(f"[DLOCK] Acquired: {self._key} | token={self._token[:8]}")
                return True
            time.sleep(0.05)   # Retry interval
        print(f"[DLOCK] Timeout acquiring: {self._key}")
        return False

    def release(self) -> bool:
        """
        CRITICAL: only release if we own the lock (token check).
        Without token check: Thread A's lock could be released by Thread B.

        Lua script — atomic check-and-delete:
          if redis.call('GET', KEYS[1]) == ARGV[1] then
              return redis.call('DEL', KEYS[1])
          else
              return 0
          end
        """
        if not self._acquired:
            return False

        RELEASE_SCRIPT = """
        if redis.call('GET', KEYS[1]) == ARGV[1] then
            return redis.call('DEL', KEYS[1])
        else
            return 0
        end
        """
        # result = self._redis.eval(RELEASE_SCRIPT, 1, self._key, self._token)
        result = 1   # Simulated
        self._acquired = (result == 0)
        if result:
            print(f"[DLOCK] Released: {self._key}")
        return bool(result)

    def __enter__(self):
        if not self.acquire():
            raise TimeoutError(f"Could not acquire distributed lock: {self._key}")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.release()
        return False   # Don't suppress exceptions

    def extend(self, additional_seconds: int) -> bool:
        """Extend lock TTL if operation taking longer than expected"""
        # result = self._redis.expire(self._key, self._expire + additional_seconds)
        return True


# ─── Usage ────────────────────────────────────────────────────

def confirm_payment_distributed(payment_id: str, redis_client):
    """
    Two web servers simultaneously process same webhook.
    Only one should confirm the payment.
    """
    lock = RedisDistributedLock(
        redis_client   = redis_client,
        key            = f"payment_confirm:{payment_id}",
        expire_seconds = 30
    )
    try:
        with lock:
            # Only one server executes this block
            payment = get_payment(payment_id)
            if payment.status == 'PROCESSING':
                payment.status = 'COMPLETED'
                payment.save()
                allocate_payment(payment)
    except TimeoutError:
        print(f"[PAYMENT] Could not get lock for {payment_id} — another server processing")


# ─── Redlock (Multi-node Redis) ───────────────────────────────
"""
Single Redis → SPOF (single point of failure).
Redlock algorithm: acquire on N/2+1 Redis nodes.

1. Get current time t1
2. Try to acquire lock on all N Redis nodes sequentially
3. If acquired on majority (N/2+1) AND total time < lock TTL:
   → Lock acquired
4. Else: release on all nodes, retry

Niroskos: single Redis node (acceptable SPOF for non-critical ops)
High availability: Redis Sentinel or Redis Cluster
"""
```

---

## PART 7: OPTIMISTIC vs PESSIMISTIC LOCKING

```python
from dataclasses import dataclass
from decimal import Decimal

# ─── PESSIMISTIC — Lock first, work second ────────────────────
# Use: high contention, short operations, can't afford conflicts

"""
Django ORM:
  Booking.objects.select_for_update().get(id=booking_id)

SQL:
  SELECT * FROM bookings WHERE id = %s FOR UPDATE;

Database holds row-level lock until transaction ends.
Other transactions trying to read/update this row → WAIT.

When to use:
  - Payment confirmation (milliseconds, high contention)
  - Booking status change (multiple agents, same booking)
  - Inventory reservation (available → booked)

Downside:
  - Lock held for transaction duration
  - Low throughput if transactions are long
  - Deadlock risk if multiple rows locked in different orders
"""

# Niroskos pattern (Django):
# @transaction.atomic
# def confirm_booking(booking_id):
#     booking = Booking.objects.select_for_update().get(id=booking_id)
#     if booking.status != 'CONFIRMED':
#         raise InvalidStateError()
#     booking.status = 'PAID'
#     booking.save()


# ─── OPTIMISTIC — Work first, check conflict at commit ────────
# Use: low contention, long operations, conflict = rare

@dataclass
class Wallet:
    id:      int
    balance: Decimal
    version: int         # Incremented on every update

def debit_wallet_optimistic(wallet_id: int, amount: Decimal, db):
    """
    Read wallet → compute new balance → update WHERE version matches.
    If another transaction updated wallet → our version stale → 0 rows → retry.
    No lock held during computation → high throughput.
    """
    MAX_RETRIES = 3
    for attempt in range(MAX_RETRIES):
        wallet = db.get_wallet(wallet_id)

        if wallet.balance < amount:
            raise ValueError("Insufficient balance")

        new_balance = wallet.balance - amount

        # Atomic: UPDATE only if version unchanged
        rows_updated = db.execute("""
            UPDATE wallets
            SET balance = %s, version = %s
            WHERE id = %s AND version = %s
        """, (new_balance, wallet.version + 1, wallet_id, wallet.version))

        if rows_updated == 1:
            print(f"[WALLET] Debited {amount} | attempt={attempt+1}")
            return new_balance

        # version mismatch → someone else updated → retry
        print(f"[WALLET] Conflict on attempt {attempt+1} — retrying")
        time.sleep(0.01 * (2 ** attempt))   # backoff

    raise ConcurrentUpdateError("Max retries exceeded")


class ConcurrentUpdateError(Exception):
    pass


# ─── Comparison ───────────────────────────────────────────────
"""
                  PESSIMISTIC          OPTIMISTIC
─────────────────────────────────────────────────────────────
Lock timing       Before work          At commit
Blocking?         Yes — waiters queue  No — fail-fast
Throughput        Low (serialized)     High (parallel reads)
Conflict handling Prevented upfront    Detected at commit
Best for          High contention      Low contention
                  Short transactions   Long read-compute-write
Example           Booking confirm      Wallet balance
                  Inventory reserve    User profile update
Deadlock risk?    Yes                  No (no locks held)
DB support        SELECT FOR UPDATE    Optimistic via version col
"""
```

---

## PART 8: ASYNCIO (Async Concurrency)

```python
import asyncio
from typing import List

"""
asyncio = single-threaded concurrency.
Event loop switches between coroutines at await points.
No GIL issue — only one coroutine runs at a time.

Best for: I/O-bound tasks (HTTP calls, DB queries, Redis ops)
NOT for: CPU-bound (blocks event loop)

Niroskos: if using async Django (ASGI) or httpx for async external API calls
"""

import asyncio
import time

async def fetch_package_details(package_id: int) -> dict:
    """Simulate async DB query"""
    await asyncio.sleep(0.1)   # DB I/O — non-blocking
    return {"id": package_id, "name": f"Package {package_id}", "price": 50000}

async def check_booking_eligibility(booking_id: int) -> bool:
    await asyncio.sleep(0.05)
    return True

async def process_booking_async(booking_id: int, package_id: int):
    """
    Run multiple I/O operations concurrently with asyncio.gather().
    Both DB calls happen in parallel — not sequentially.
    """
    # Sequential: 0.1 + 0.05 = 0.15s
    # Concurrent: max(0.1, 0.05) = 0.1s
    package, eligible = await asyncio.gather(
        fetch_package_details(package_id),
        check_booking_eligibility(booking_id)
    )
    print(f"[ASYNC] Booking {booking_id}: package={package['name']}, eligible={eligible}")
    return package

async def main():
    # Process 5 bookings concurrently
    tasks = [
        process_booking_async(i, i % 3 + 1)
        for i in range(5)
    ]
    start = time.time()
    results = await asyncio.gather(*tasks)
    print(f"All {len(results)} bookings processed in {time.time()-start:.2f}s")

asyncio.run(main())


# ─── asyncio Lock ─────────────────────────────────────────────
# Same concept as threading.Lock but for coroutines

async def safe_counter_async():
    lock    = asyncio.Lock()
    counter = 0

    async def increment():
        nonlocal counter
        async with lock:
            val = counter
            await asyncio.sleep(0)   # yield — another coroutine could run
            counter = val + 1        # safe — lock held

    await asyncio.gather(*[increment() for _ in range(100)])
    print(f"Counter: {counter}")   # Always 100
```

---

## PART 9: THREAD POOL & EXECUTOR

```python
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor, as_completed

# ─── ThreadPoolExecutor — I/O bound tasks ────────────────────

def send_sms(phone: str) -> dict:
    time.sleep(0.1)   # Simulate Exotel API call
    return {"phone": phone, "status": "sent"}

phones = [f"+2547{i:08d}" for i in range(10)]

# Sequential: 10 × 0.1s = 1s
# Parallel with thread pool: ~0.1s (all concurrent)
with ThreadPoolExecutor(max_workers=5) as executor:
    # Submit all tasks
    futures = {
        executor.submit(send_sms, phone): phone
        for phone in phones
    }
    # Collect results as they complete
    for future in as_completed(futures):
        phone  = futures[future]
        result = future.result()
        print(f"SMS sent to {result['phone']}")


# ─── ProcessPoolExecutor — CPU bound tasks ────────────────────

def generate_report(booking_ids: List[int]) -> dict:
    # CPU-intensive: aggregations, PDF generation
    total = sum(booking_ids)   # Simulate computation
    return {"count": len(booking_ids), "total": total}

booking_chunks = [[1,2,3], [4,5,6], [7,8,9], [10,11,12]]

with ProcessPoolExecutor(max_workers=4) as executor:
    futures  = [executor.submit(generate_report, chunk) for chunk in booking_chunks]
    results  = [f.result() for f in futures]
    combined = sum(r["total"] for r in results)
    print(f"Total across all chunks: {combined}")
```

---

## PART 10: CONCURRENCY IN NIROSKOS — REAL SCENARIOS

```python
"""
SCENARIO 1: Double Booking (most asked!)
─────────────────────────────────────────
Problem:  Two agents book same safari date simultaneously
Solution: select_for_update() in DB transaction

# Django/PostgreSQL:
@transaction.atomic
def create_booking(package_id, travel_date, guests, customer_id):
    # Row-level lock — concurrent requests queue here
    package = Package.objects.select_for_update().get(id=package_id)

    # Check capacity (with lock held — no TOCTOU)
    booked = Booking.objects.filter(
        package_id=package_id,
        travel_date=travel_date,
        status__in=['CONFIRMED', 'PAID']
    ).aggregate(total=Sum('guests'))['total'] or 0

    if booked + guests > package.capacity:
        raise CapacityExceededError(f"Only {package.capacity - booked} spots left")

    booking = Booking.objects.create(
        package_id=package_id,
        travel_date=travel_date,
        guests=guests,
        customer_id=customer_id,
        status='CONFIRMED'
    )
    return booking
# Lock released at end of @transaction.atomic


SCENARIO 2: Concurrent Payment Webhook
─────────────────────────────────────────
Problem:  Stripe fires same webhook twice → double allocation
Solution: Three-layer protection
  1. provider_event_id UNIQUE constraint (DB level)
  2. payment._lock (in-process thread safety)
  3. Redis distributed lock (cross-process)

# If DB raises IntegrityError on provider_event_id → already processed → return 200
try:
    transaction = Transaction.objects.create(
        provider_event_id=event_id,   # UNIQUE constraint
        ...
    )
except IntegrityError:
    return HttpResponse(status=200)   # Already processed — tell Stripe to stop retrying


SCENARIO 3: SAP HANA Token Cache
─────────────────────────────────────────
Problem:  Multiple requests simultaneously hit SAP token endpoint → rate limit
Solution: Singleton with lock — only one token refresh at a time

class SAPTokenCache:
    _instance  = None
    _lock      = threading.Lock()
    _token     = None
    _expiry    = None
    _token_lock = threading.Lock()

    @classmethod
    def get_token(cls):
        with cls._token_lock:
            if cls._token and datetime.now() < cls._expiry:
                return cls._token
            # Token expired or missing → refresh (with lock → only one refresh)
            cls._token  = cls._fetch_new_token()
            cls._expiry = datetime.now() + timedelta(minutes=5)
            return cls._token

    @classmethod
    def _fetch_new_token(cls):
        # POST to SAP token endpoint
        pass


SCENARIO 4: Celery Task Idempotency
─────────────────────────────────────────
Problem:  Beat + signal + webhook all enqueue same task
Solution: Task-level idempotency check + DB flag

@shared_task(bind=True)
def send_booking_reminder(self, booking_id):
    # Idempotency check inside task
    booking = Booking.objects.get(id=booking_id)
    if booking.reminder_sent:
        return "already_sent"   # Early return — idempotent

    # Atomic: check + set flag to prevent concurrent execution
    updated = Booking.objects.filter(
        id=booking_id,
        reminder_sent=False    # Optimistic — only update if not yet sent
    ).update(reminder_sent=True)

    if updated == 0:
        return "already_sent"  # Another worker beat us to it

    notification_service.send(booking)
    return "sent"
"""
```

---

## Interview Q&A

**Q: "Race condition kya hai — apne project mein kahan tha?"**
> "Race condition tab hoti hai jab do threads ek shared resource ko simultaneously access karte hain aur result execution order pe depend karta hai. Niroskos mein classic TOCTOU problem tha — double booking. Do agents simultaneously same safari date check karte — dono ko available dikhta — dono booking create karte — capacity exceed ho jaati. Fix: Django ORM ka select_for_update() use kiya — ye PostgreSQL row-level lock laata hai. Check aur reserve ek hi transaction mein locked row pe hota tha. Lock transaction complete hone pe release hoti — iska matlab concurrent requests queue hote hain, double booking possible nahi."

**Q: "Optimistic vs Pessimistic locking — kab kya use kiya?"**
> "Pessimistic locking use kiya booking confirmation aur payment processing mein — high contention, millisecond operations, conflict afford nahi kar sakte. select_for_update() DB lock laata hai row pe — conflict impossible. Optimistic locking use kiya wallet balance updates mein — low contention, longer read-compute-write cycle. version field wa column DB mein — UPDATE WHERE id=X AND version=current_version. Agar zero rows updated → kisi aur ne update kiya — retry. Koi lock held nahi during computation — high throughput. Rule: pessimistic = can't afford to retry. Optimistic = conflicts rare, retry cheap."

**Q: "Python GIL — kya problem hai Celery mein?"**
> "GIL sirf ek thread ko ek time pe Python bytecode execute karne deta hai. Celery workers separate processes hain — har process ka apna GIL. Toh Celery pe GIL koi problem nahi — true parallelism milti hai. Issue sirf tab hota agar hum ek process mein threading.Thread se CPU-bound kaam karte. Niroskos mein Celery workers I/O-bound tasks karte the — DB queries, Redis operations, HTTP calls (Exotel, SAP, Stripe). I/O ke time GIL release hoti hai — threading fine hai for these. Gunicorn bhi multiple worker processes use karta hai — GIL bypass."

**Q: "Distributed lock kab chahiye, in-process lock kab?"**
> "In-process threading.Lock sirf ek Python process ke threads ke beech kaam karta hai. Production mein Gunicorn 4 worker processes laata hai — har process ka apna memory space. Thread A (process 1) aur Thread B (process 2) ek hi payment webhook process karne ki koshish karein — dono ke apne alag locks — conflict prevention nahi. Solution: Redis distributed lock — SET key token NX EX 30. NX means 'set only if not exists' — atomic operation. Token unique per lock holder — sirf lock lene wala hi release kar sakta hai (Lua script se atomic check). In Niroskos: critical payment confirmation Redis lock use karta tha, regular booking lock DB select_for_update() se handle hota tha."

**Q: "Deadlock kaise avoid karte ho?"**
> "Two main strategies. First: lock ordering — agar do resources lock karne hain, hamesha same order mein acquire karo. Bank transfer example: hamesha lower account ID wala pehle lock karo — circular wait impossible. Second: timeout with backoff — lock acquire karte waqt timeout set karo. Agar timeout hota hai → deadlock suspected → release jo locks held hain → wait → retry. Third strategy jo actually use ki: minimize lock scope — smallest possible critical section, kisi bhi I/O ya external call se lock ke bahar. Locking DB transaction ke andar rakhna — PostgreSQL automatically deadlock detect karta hai aur ek transaction rollback karta hai."

---

## Quick Reference

```
Primitive          | Use Case                        | Niroskos Use
───────────────────────────────────────────────────────────────────────
threading.Lock     | Mutual exclusion                | TokenBucketState, Payment._lock
threading.RLock    | Reentrant (recursive) lock      | Nested method calls
threading.Event    | Thread signaling                | Worker ready signal
threading.Condition| Producer-consumer               | PriorityTaskQueue
threading.Semaphore| N concurrent access             | DB connection pool
queue.Queue        | Thread-safe task passing        | TaskQueue (Celery simulation)
select_for_update  | DB row-level pessimistic lock   | Booking confirm, capacity check
version field      | Optimistic locking              | Wallet balance
Redis SET NX EX    | Distributed lock across servers | Payment webhook, SAP sync
threading.Lock     | Singleton protection            | SAPTokenCache, RedisClient
asyncio.Lock       | Async coroutine mutex           | Async Django / httpx
```

---

*Last Updated: April 2026 | SDE-2 Interview Prep — Niroskos Concurrency Patterns*
