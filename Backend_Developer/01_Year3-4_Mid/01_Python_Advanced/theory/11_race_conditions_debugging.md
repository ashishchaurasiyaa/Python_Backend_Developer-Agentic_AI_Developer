# Race Conditions — Detection & Debugging

> **Interview angle:** "Production mein intermittent bug — counter wrong value de raha sometimes. Kaise debug karoge?"

---

## 1. Race Condition Kya Hai?

Jab **2 ya zyada threads/tasks** ek hi shared resource pe operate karte hain bina synchronization ke, aur **final result execution order pe depend karta hai** — that's a race condition.

**Classic example:**
```python
counter = 0

def increment():
    global counter
    counter += 1     # 3 operations: LOAD, ADD, STORE

# 2 threads call increment() simultaneously
# Expected: 2
# Actual:   sometimes 1
```

**Why?** `counter += 1` is **NOT atomic** in Python:
```
LOAD_FAST    counter   # Thread A reads 0
LOAD_CONST   1
BINARY_OP    +         # Thread A computes 1
                       # ← Thread B switches in, reads 0, writes 1
STORE_FAST   counter   # Thread A writes 1 (overwrites!)
```

GIL doesn't save you — GIL switches **every ~100 bytecode instructions** or on I/O.

---

## 2. Common Race Condition Patterns

### Pattern A: Read-Modify-Write (most common)
```python
balance += amount       # NOT atomic
list.append(item)       # atomic in CPython (bytecode-level)
dict[k] = dict[k] + 1   # NOT atomic
```

### Pattern B: Check-Then-Act (TOCTOU bug)
```python
if key not in cache:    # check
    cache[key] = compute()   # act — another thread may have inserted!
```

### Pattern C: Lazy Initialization
```python
_instance = None
def get_instance():
    global _instance
    if _instance is None:        # check
        _instance = Heavy()      # act — multiple instances created!
    return _instance
```

### Pattern D: Async — await releases control
```python
async def transfer(from_acc, to_acc, amt):
    from_acc.balance -= amt
    await save(from_acc)        # ← other coroutines run here!
    to_acc.balance += amt       # state may be stale
    await save(to_acc)
```

### Pattern E: Database row updates without locks
```python
user = User.objects.get(id=1)
user.credits -= 10
user.save()                     # lost update if 2 requests
# Fix: SELECT FOR UPDATE or atomic F() expressions
```

---

## 3. Detection Tools & Techniques

### a) `threading` module — `Lock` + try-except instrumentation
```python
import threading
lock = threading.Lock()

# Detect contention
acquired = lock.acquire(timeout=0.1)
if not acquired:
    logger.warning("Lock contention detected!")
```

### b) `faulthandler` — dump stacks on crash/signal
```python
import faulthandler
faulthandler.enable()
faulthandler.dump_traceback_later(10, repeat=True)
# Prints stack of all threads every 10 sec
```

### c) `threading.settrace()` — log every thread call
```python
import threading
threading.settrace(lambda *args: print(args))
```

### d) `py-spy dump` — Get live stack of all threads
```bash
py-spy dump --pid 12345
```

### e) Sanitizer-style: `pytest-repeat` + stress
```bash
pytest test_concurrency.py --count=1000
# Run same test 1000x — race conditions surface
```

### f) `asyncio` debug mode
```python
import asyncio
asyncio.run(main(), debug=True)
# Logs: long-running tasks, unawaited coroutines
# Set env var: PYTHONASYNCIODEBUG=1
```

### g) Custom: deterministic interleaving via `sys.setswitchinterval`
```python
import sys
sys.setswitchinterval(0.00001)   # force more switches → expose races
```

---

## 4. Fixes — Synchronization Primitives

### a) `threading.Lock` — mutual exclusion
```python
lock = threading.Lock()
def safe_increment():
    with lock:
        counter += 1
```

### b) `threading.RLock` — re-entrant (same thread can acquire again)
```python
lock = threading.RLock()
def outer():
    with lock:
        inner()              # would deadlock with regular Lock

def inner():
    with lock:
        pass
```

### c) `threading.Semaphore` — N concurrent allowed
```python
db_pool = threading.Semaphore(10)   # max 10 connections
def query():
    with db_pool:
        run_sql()
```

### d) `threading.Event` — signal between threads
```python
ready = threading.Event()
# Thread A
ready.wait()      # block until set
# Thread B
ready.set()
```

### e) `queue.Queue` — thread-safe FIFO (best for producer-consumer)
```python
from queue import Queue
q = Queue(maxsize=100)
q.put(item)       # thread-safe
item = q.get()
```

### f) `threading.local()` — per-thread storage
```python
local = threading.local()
def handle():
    local.user_id = get_current_user()  # isolated per thread
```

### g) Atomic operations — `itertools.count()`
```python
from itertools import count
counter = count()
next(counter)     # atomic — C implementation, GIL-protected
```

### h) `asyncio.Lock` — for async code
```python
lock = asyncio.Lock()
async def transfer():
    async with lock:
        from_acc.balance -= amt
        await save(from_acc)
        to_acc.balance += amt
        await save(to_acc)
```

### i) Database-level — atomic operations
```python
# Django F expressions
from django.db.models import F
User.objects.filter(id=1).update(credits=F('credits') - 10)
# Single UPDATE SQL — atomic at DB level

# SELECT FOR UPDATE
with transaction.atomic():
    user = User.objects.select_for_update().get(id=1)
    user.credits -= 10
    user.save()
```

---

## 5. Real Debugging Story (Template)

**Bug:** "User credits sometimes wrong after concurrent purchases."

**Step 1: Reproduce**
```python
import threading
def buy(user_id):
    user = User.get(user_id)
    user.credits -= 10
    user.save()

threads = [threading.Thread(target=buy, args=(1,)) for _ in range(100)]
for t in threads: t.start()
for t in threads: t.join()
# user.credits should be -1000, often shows -200
```

**Step 2: Identify pattern** — Read-modify-write without lock.

**Step 3: Fix at right layer**
- ❌ App-level lock — only works in single process
- ❌ Redis lock — extra network call per request
- ✅ **DB-level atomic update** — `UPDATE users SET credits = credits - 10`

**Step 4: Verify with stress test**
```python
pytest test_buy.py --count=1000 -n 8
```

---

## 6. Common Pitfalls

### Pitfall 1: "GIL protects me"
Wrong. GIL atomic operations limited:
- ✅ `list.append`, `dict[k] = v` (single bytecode)
- ❌ `counter += 1`, `dict[k] = dict[k] + 1`

### Pitfall 2: Lock granularity wrong
Too coarse → serialized, slow.
Too fine → race conditions persist.

### Pitfall 3: Forgotten `await` releases control
Async ke beech mein state mutate karna unsafe.

### Pitfall 4: Lock on different objects
```python
class Account:
    def __init__(self):
        self.lock = threading.Lock()    # ❌ per-instance lock
        # If shared resource is class-level, instance lock useless
```

### Pitfall 5: Race in cleanup paths
```python
try:
    ...
finally:
    cleanup()      # if another thread already cleaned up?
```

---

## 7. Interview Questions

**Q1: GIL race conditions kyu rok nahi sakta?**
GIL har bytecode instruction ke baad release ho sakta — multi-instruction operations (`+=`) interrupt ho sakte.

**Q2: `Lock` vs `RLock` difference?**
`Lock` — same thread re-acquire kare to deadlock. `RLock` — counter rakhta, same thread multiple acquire safe.

**Q3: Async mein race condition possible?**
Haan — `await` ke time control return hota event loop ko. Other coroutines mutate kar sakte shared state.

**Q4: Production race condition debug?**
1. `py-spy dump` — live stacks
2. `faulthandler` — periodic stack dump
3. Reproduce with stress test (`pytest-repeat`)
4. Add structured logging around shared state
5. Move atomicity to DB layer (best for multi-instance apps)

**Q5: `threading.local()` use case?**
Per-thread context — DB connections, request ID, user session. Each thread gets own copy.

**Q6: Lost update problem ka solution?**
- Optimistic locking (version column + retry)
- Pessimistic locking (`SELECT FOR UPDATE`)
- Atomic SQL (`UPDATE table SET col = col + 1`)
- CRDTs for distributed systems

---

## 8. Best Practices

1. **Prefer immutability** — no mutation = no race
2. **Keep critical sections small** — less time holding lock
3. **Lock at the right layer** — DB > app > thread
4. **Use queues** instead of shared mutable state
5. **Test with stress** — `pytest --count=N -n parallel`
6. **Log lock acquisitions** in suspect code
7. **Avoid Python-level synchronization** in async — use `asyncio.Lock`

---

## Related
- [[05_async_concurrency_deep_dive]] — asyncio patterns
- [[12_deadlock_debugging]] — locks gone wrong
- [[03_memory_gil]] — GIL semantics
