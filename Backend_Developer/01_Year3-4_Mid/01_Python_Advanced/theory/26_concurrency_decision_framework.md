# Concurrency Decision Framework — Threading vs Multiprocessing vs Asyncio

## Quick Concepts

**WHAT:**
- **Threading** = Multiple threads in same process (shared memory, GIL)
- **Multiprocessing** = Multiple processes (separate memory, no GIL)
- **Asyncio** = Single thread, cooperative scheduling (event loop)
- **GIL** = Global Interpreter Lock (one thread executes Python at a time)
- **CPU-bound** = Work limited by CPU speed (computation)
- **I/O-bound** = Work limited by I/O wait (network, disk)

**WHY this matters:**
- Wrong choice = 10x slowdown
- GIL trap for CPU-bound threading
- Memory cost for multiprocessing
- Complexity cost for asyncio

**HOW decision tree:**
```
What kind of work?
├── I/O-bound (network, DB, disk)
│   ├── Many small operations? → asyncio (best)
│   ├── Few operations? → threading (simpler)
│   └── Single operation? → sync
│
├── CPU-bound (computation)
│   ├── Pure Python? → multiprocessing (bypass GIL)
│   ├── Uses numpy/C ext? → threading (releases GIL)
│   └── Single core enough? → sync
│
└── Mixed
    ├── Mostly I/O? → asyncio + run_in_executor
    └── Mostly CPU? → multiprocessing + threading
```

---

## Interview Questions & Answers

### Q1: Threading vs Multiprocessing vs Asyncio — kab kya?

**Answer:**

**HOW — Comprehensive comparison:**

| Aspect | Threading | Multiprocessing | Asyncio |
|---|---|---|---|
| **Parallelism** | ❌ (GIL) | ✅ True parallel | ❌ (single thread) |
| **CPU work speedup** | ❌ | ✅ N-cores | ❌ |
| **I/O work speedup** | ✅ | ✅ | ✅ Best |
| **Memory overhead** | Low (~1MB/thread) | High (~100MB/process) | Lowest |
| **Startup cost** | Medium | High | Lowest |
| **Shared state** | Easy (same memory) | Hard (IPC) | Easy (same thread) |
| **Code complexity** | Low | Medium | High |
| **Number of "workers"** | 10-100 | 4-16 (cores) | 10K+ |
| **Best for** | Few I/O calls | CPU work | Many I/O calls |

**HOW — Quick rules:**

```python
# Rule 1: I/O bound (HTTP, DB, files) → asyncio
async def fetch_apis():
    async with httpx.AsyncClient() as client:
        results = await asyncio.gather(*[
            client.get(url) for url in 1000_urls
        ])


# Rule 2: CPU bound → multiprocessing
from multiprocessing import Pool

def cpu_heavy(x):
    return sum(i*i for i in range(x))

with Pool(8) as p:
    results = p.map(cpu_heavy, list_of_inputs)


# Rule 3: Mixed (e.g., heavy data processing per item)
import asyncio
from concurrent.futures import ProcessPoolExecutor

async def main():
    loop = asyncio.get_running_loop()
    with ProcessPoolExecutor(max_workers=4) as pool:
        # I/O concurrent, CPU parallel
        results = await asyncio.gather(*[
            loop.run_in_executor(pool, cpu_heavy, item)
            for item in items
        ])


# Rule 4: Few I/O calls, sync libraries → threading
from concurrent.futures import ThreadPoolExecutor

with ThreadPoolExecutor(max_workers=10) as pool:
    results = list(pool.map(legacy_sync_api_call, list_of_inputs))
```

---

### Q2: GIL — exactly what it does?

**Answer:**

**WHAT:** Global Interpreter Lock — mutex protecting Python interpreter state.

**WHY exists:**
- CPython memory management not thread-safe
- Simplifies C extension development
- Performance OK for single-threaded code

**HOW — When GIL is released:**

```python
# ✅ GIL RELEASED (concurrent execution possible)
import time
time.sleep(1)  # ⭐ GIL released during sleep

# I/O operations
file.read()
socket.recv()

# C extensions that release GIL
import numpy as np
arr.sum()  # numpy releases GIL


# ❌ GIL HELD (serial execution)
# Pure Python computation
sum(i*i for i in range(1_000_000))

# Python interpreter operations
list.append, dict.update, etc.
```

**HOW — Benchmark:**

```python
import threading
import multiprocessing
import time

def cpu_work():
    return sum(i*i for i in range(10_000_000))

def io_work():
    time.sleep(2)

# Single thread baseline
start = time.time()
for _ in range(4):
    cpu_work()
print(f"Sync CPU: {time.time() - start:.2f}s")  # ~8s


# Threading (GIL bottleneck for CPU)
start = time.time()
threads = [threading.Thread(target=cpu_work) for _ in range(4)]
for t in threads: t.start()
for t in threads: t.join()
print(f"Thread CPU: {time.time() - start:.2f}s")  # ~8s (NO speedup!)


# Multiprocessing (bypasses GIL)
start = time.time()
processes = [multiprocessing.Process(target=cpu_work) for _ in range(4)]
for p in processes: p.start()
for p in processes: p.join()
print(f"Process CPU: {time.time() - start:.2f}s")  # ~2s (4x speedup!)


# Threading for I/O (works!)
start = time.time()
threads = [threading.Thread(target=io_work) for _ in range(4)]
for t in threads: t.start()
for t in threads: t.join()
print(f"Thread I/O: {time.time() - start:.2f}s")  # ~2s (4x speedup!)
```

---

### Q3: When threading IS the right choice?

**Answer:**

**WHAT:** Despite GIL, threading useful in many cases.

**WHEN to use:**

```python
# 1. I/O-bound + sync library (can't use asyncio)
import requests
from concurrent.futures import ThreadPoolExecutor

def fetch(url):
    return requests.get(url).json()  # ⭐ Sync only

urls = [...]
with ThreadPoolExecutor(max_workers=20) as pool:
    results = list(pool.map(fetch, urls))


# 2. NumPy / Pandas CPU work (releases GIL)
import numpy as np
import threading

def compute(arr):
    return np.fft.fft(arr).real

arrays = [np.random.random(1_000_000) for _ in range(4)]
threads = [threading.Thread(target=compute, args=(a,)) for a in arrays]
# ⭐ True parallel because numpy releases GIL


# 3. Simple producer-consumer with stdlib
from queue import Queue
from threading import Thread

q = Queue()

def producer():
    for i in range(100):
        q.put(i)

def consumer():
    while True:
        item = q.get()
        process(item)
        q.task_done()

Thread(target=producer).start()
Thread(target=consumer).start()
q.join()


# 4. GUI applications (Tkinter, PyQt)
# Main thread = GUI
# Background thread = work
```

**HOW — Thread pool sizing:**

```python
import os
from concurrent.futures import ThreadPoolExecutor

# For I/O-bound (sync libraries)
# Many threads OK (most waiting)
io_pool = ThreadPoolExecutor(max_workers=50)

# For CPU + numpy (GIL releases)
cpu_threads = os.cpu_count()
np_pool = ThreadPoolExecutor(max_workers=cpu_threads)

# For mixed
# (2 × cores) + 1 = traditional rule
mixed_pool = ThreadPoolExecutor(max_workers=(2 * cpu_threads) + 1)
```

---

### Q4: Multiprocessing — patterns + gotchas?

**Answer:**

**HOW — Basic pool:**

```python
from multiprocessing import Pool

def square(x):
    return x * x

# ⭐ Pool of worker processes
with Pool(processes=4) as pool:
    # Map (preserves order)
    results = pool.map(square, [1, 2, 3, 4, 5])

    # imap (lazy, preserves order)
    for result in pool.imap(square, range(1000)):
        print(result)

    # imap_unordered (lazy, any order — fastest)
    for result in pool.imap_unordered(square, range(1000)):
        print(result)

    # apply_async (single task)
    future = pool.apply_async(square, (5,))
    print(future.get())
```

**HOW — ProcessPoolExecutor (modern):**

```python
from concurrent.futures import ProcessPoolExecutor

with ProcessPoolExecutor(max_workers=4) as pool:
    # map
    results = list(pool.map(square, [1, 2, 3]))

    # submit (returns Future)
    future = pool.submit(square, 5)
    print(future.result())

    # as_completed (process as ready)
    futures = [pool.submit(work, i) for i in range(10)]
    for future in as_completed(futures):
        print(future.result())
```

**HOW — Sharing data between processes:**

```python
from multiprocessing import Process, Queue, Value, Array, Manager

# 1. Queue (FIFO)
q = Queue()
def producer():
    q.put("data")

def consumer():
    print(q.get())


# 2. Shared Value (single)
counter = Value("i", 0)  # 'i' = int

def increment():
    with counter.get_lock():
        counter.value += 1


# 3. Shared Array (fixed size)
arr = Array("i", [0] * 100)
arr[0] = 42  # Thread-safe


# 4. Manager (more complex types)
manager = Manager()
shared_dict = manager.dict()
shared_list = manager.list()

def worker():
    shared_dict["key"] = "value"
    shared_list.append(1)


# 5. Pipe (1-to-1)
from multiprocessing import Pipe
parent_conn, child_conn = Pipe()
child_conn.send("hello")
print(parent_conn.recv())
```

**Gotchas:**

```python
# ❌ GOTCHA 1: Spawn vs Fork
# Linux: fork (faster, but copies state)
# macOS 3.8+: spawn (slower, but cleaner)
# Windows: spawn only

import multiprocessing
# Set explicitly for cross-platform
multiprocessing.set_start_method("spawn", force=True)


# ❌ GOTCHA 2: Pickling restrictions
class MyClass:
    def __init__(self):
        self.func = lambda x: x  # ⚠️ Can't pickle lambda!

# ProcessPool needs to pickle args
# Use functions, not lambdas or local classes


# ❌ GOTCHA 3: if __name__ == "__main__"
# Required on Windows / spawn

if __name__ == "__main__":
    with Pool(4) as p:
        p.map(square, [1, 2, 3])
# Without this: infinite spawn loop on Windows


# ❌ GOTCHA 4: Memory cost
# Each process copies parent state
# 100 MB parent × 8 processes = 800 MB
# Use Pool with maxtasksperchild for long-running
Pool(processes=8, maxtasksperchild=100)  # ⭐ Recycle after 100 tasks
```

---

### Q5: Asyncio — when WORST choice?

**Answer:**

**WHEN asyncio is BAD:**

```python
# ❌ 1. CPU-bound work
async def compute():
    return sum(i*i for i in range(10_000_000))
# ⚠️ Blocks event loop! Use multiprocessing


# ❌ 2. Sync libraries only
async def db_call():
    user = sync_db.fetch_user(1)  # ⚠️ Blocks loop
# Use asyncio.to_thread() or async library


# ❌ 3. Single sequential operation
async def single():
    result = await fetch_one()  # Just sync would work
    process(result)
# No benefit, just complexity


# ❌ 4. Mixing with sync code badly
async def main():
    # ⚠️ time.sleep blocks ALL coroutines
    time.sleep(5)  # Should be: await asyncio.sleep(5)
```

**WHEN asyncio shines:**

```python
# ✅ 1. Many concurrent I/O
async def main():
    async with httpx.AsyncClient() as client:
        results = await asyncio.gather(*[
            client.get(url) for url in 10_000_urls
        ])


# ✅ 2. Real-time apps (WebSocket, SSE)
async def chat_server():
    async with websockets.serve(handler, "0.0.0.0", 8080):
        await asyncio.Future()  # Run forever


# ✅ 3. Event-driven systems
@app.event("order.created")
async def on_order(event):
    await process_async(event)


# ✅ 4. Long-lived connections (chat, gaming)
async def connection_handler(ws):
    async for message in ws:
        await handle(message)
```

---

### Q6: Bridging async + sync code?

**Answer:**

**HOW — Sync function in async code:**

```python
import asyncio

def blocking_call():
    """Sync code (e.g., legacy library)."""
    time.sleep(2)
    return "result"

async def main():
    # ⭐ Run sync in thread pool (doesn't block event loop)
    result = await asyncio.to_thread(blocking_call)

    # OR with executor
    loop = asyncio.get_running_loop()
    result = await loop.run_in_executor(None, blocking_call)
```

**HOW — Async function in sync code:**

```python
async def async_function():
    await asyncio.sleep(1)
    return "result"

def sync_caller():
    # ⭐ Run async in sync context
    result = asyncio.run(async_function())
    return result


# In Jupyter (which already has loop)
import asyncio
import nest_asyncio
nest_asyncio.apply()

result = asyncio.run(async_function())
```

**HOW — CPU work in async:**

```python
import asyncio
from concurrent.futures import ProcessPoolExecutor

def cpu_heavy(data):
    return sum(i*i for i in range(data))

async def main():
    loop = asyncio.get_running_loop()

    # ⭐ ProcessPoolExecutor for CPU work
    with ProcessPoolExecutor(max_workers=4) as pool:
        results = await asyncio.gather(*[
            loop.run_in_executor(pool, cpu_heavy, n)
            for n in [1_000_000, 2_000_000, 3_000_000]
        ])
```

---

### Q7: Benchmark — real-world numbers?

**Answer:**

**HOW — Setup:**

```python
import asyncio
import threading
import multiprocessing
import requests
import httpx
import time

URLS = ["https://httpbin.org/delay/1"] * 20  # 20 × 1s = 20s sequential


# Test 1: Sequential
start = time.time()
results = [requests.get(url).text for url in URLS]
print(f"Sequential: {time.time() - start:.2f}s")
# ~20s


# Test 2: Threading
from concurrent.futures import ThreadPoolExecutor
start = time.time()
with ThreadPoolExecutor(max_workers=20) as pool:
    results = list(pool.map(lambda u: requests.get(u).text, URLS))
print(f"Threading: {time.time() - start:.2f}s")
# ~1.2s (great)


# Test 3: Multiprocessing
from concurrent.futures import ProcessPoolExecutor
start = time.time()
with ProcessPoolExecutor(max_workers=20) as pool:
    results = list(pool.map(lambda u: requests.get(u).text, URLS))
print(f"Multiprocessing: {time.time() - start:.2f}s")
# ~2s (process spawn overhead)


# Test 4: Asyncio
async def fetch_async():
    async with httpx.AsyncClient() as client:
        return await asyncio.gather(*[client.get(url) for url in URLS])

start = time.time()
results = asyncio.run(fetch_async())
print(f"Asyncio: {time.time() - start:.2f}s")
# ~1.1s (best for I/O)
```

**Typical benchmark results:**

```
Workload: 20 HTTP requests (1s delay each)

Sequential:        20.0s   (1x baseline)
Threading (20):     1.2s   (16x speedup)
Multiprocessing(8): 3.5s   (5.7x speedup, more overhead)
Asyncio:            1.1s   (18x speedup, best!)


Workload: 4 CPU computations (5s each)

Sequential:        20s     (1x)
Threading (4):     20s     (GIL — no speedup!)
Multiprocessing(4): 5.2s   (4x speedup, true parallel)
Asyncio:           20s     (GIL — no benefit!)
```

---

### Q8: Sub-interpreters (3.12+) — alternative?

**Answer:**

**WHAT:** Multiple isolated interpreters in same process (PEP 684).

**WHY:**
- Cheaper than multiprocessing (shared memory)
- Bypasses GIL (each interpreter has own)
- Cleaner isolation than threading

**HOW — Python 3.12:**

```python
import _xxsubinterpreters as interpreters

# Create
interp = interpreters.create()

# Run code
interpreters.run_string(interp, """
import math
result = math.sqrt(1000)
print(f"Result: {result}")
""")

interpreters.destroy(interp)
```

**HOW — Python 3.13 (public API, PEP 734):**

```python
# Coming in Python 3.13
from interpreters import create, destroy, run

interp = create()
try:
    run(interp, "print('Hello from sub-interpreter')")
finally:
    destroy(interp)
```

**Trade-offs vs multiprocessing:**

| Aspect | Sub-interpreters | Multiprocessing |
|---|---|---|
| Start cost | Lower | Higher |
| Memory | Lower (shared base) | Higher (full copy) |
| GIL | Each has own | No GIL |
| Communication | Future: shared mem | Pickle (slow) |
| Maturity | New (3.12+) | Stable |

---

### Q9: Python 3.13 free-threaded mode?

**Answer:**

**WHAT:** Build-time option to disable GIL entirely.

**WHY revolutionary:**
- Threads ACTUALLY parallel for CPU
- No more "use multiprocessing for CPU"
- Same code, much faster

**HOW — Build:**

```bash
# Get Python 3.13
git clone https://github.com/python/cpython
cd cpython
./configure --disable-gil
make
sudo make install

# Check
python3 --version
# Python 3.13.x experimental free-threading build
```

**HOW — Use:**

```python
import threading
import time

def cpu_work():
    return sum(i*i for i in range(10_000_000))

# Standard GIL Python:
# 4 threads = 4× baseline time (serial)

# Free-threaded Python:
# 4 threads = 1.2× baseline time (parallel!)


start = time.time()
threads = [threading.Thread(target=cpu_work) for _ in range(8)]
for t in threads: t.start()
for t in threads: t.join()
print(f"8 threads: {time.time() - start:.2f}s")
```

**HOW — Check at runtime:**

```python
import sys
import sysconfig

# Check if no-GIL build
if sysconfig.get_config_var("Py_GIL_DISABLED"):
    print("Free-threading enabled!")
else:
    print("Standard GIL build")
```

**Status:**
- Experimental in 3.13
- ~10% slower single-threaded
- C extensions need updates
- Stable target: Python 3.15+

---

### Q10: Production guidelines?

**Answer:**

**Decision flowchart for production:**

```
┌─────────────────────────────────────────────┐
│ What does your app PRIMARILY do?            │
└──────────────┬──────────────────────────────┘
               │
       ┌───────┴───────┬────────────────┐
       ▼               ▼                ▼
   I/O-bound       CPU-bound        Mixed
   (web, API)      (ML, video)
       │               │                │
       │               │                │
       ▼               ▼                ▼
   asyncio       multiprocessing   asyncio +
   (FastAPI)     (Pool/Executor)   run_in_executor
                                   (FastAPI + workers)


# Common production setups:

# Web API (FastAPI)
async def api_handler():
    # 90% I/O — use async
    user = await db.fetch_user(id)
    history = await api.get_history(id)

    # 10% CPU — offload to executor
    result = await asyncio.to_thread(process_data, user, history)
    return result


# Background workers (Celery)
@celery.task
def heavy_task(data):
    # CPU-bound — Celery uses processes by default
    return compute(data)


# Data pipeline (Pandas/NumPy)
import multiprocessing as mp
def process_chunk(df_chunk):
    return df_chunk.apply(transform)

with mp.Pool(8) as pool:
    chunks = np.array_split(big_df, 8)
    results = pool.map(process_chunk, chunks)
    final = pd.concat(results)


# Microservice with HTTP calls
import asyncio
import httpx

async def fanout(user_ids):
    async with httpx.AsyncClient() as client:
        responses = await asyncio.gather(*[
            client.get(f"/users/{uid}") for uid in user_ids
        ])
    return [r.json() for r in responses]
```

---

## Concurrency Cheatsheet

| Scenario | Best Choice | Why |
|---|---|---|
| FastAPI / aiohttp server | asyncio | Native async |
| Web scraping 1000s of URLs | asyncio (httpx) | Best I/O parallelism |
| Background tasks (Celery) | multiprocessing | True CPU parallel |
| Image/video processing | multiprocessing | CPU-bound |
| ML inference (PyTorch GPU) | threading (CPU coordination) | GPU does work |
| Pandas data processing | multiprocessing | CPU + memory |
| Legacy sync API + need concurrency | threading | Sync libs |
| Database queries + many | asyncio (asyncpg) | I/O bound |
| Gaming server | asyncio | Many connections |
| GUI app | threading | Main thread = GUI |
| File scanning | threading | I/O + ok memory |
| Cryptocurrency mining | multiprocessing | Pure CPU |

---

## Production Checklist

```markdown
### Choosing
- [ ] Identified I/O vs CPU bound
- [ ] Considered library constraints (sync vs async)
- [ ] Profiled before choosing
- [ ] Tested with realistic load

### Threading
- [ ] ThreadPoolExecutor (not raw threads)
- [ ] threading.Lock for shared state
- [ ] queue.Queue for thread communication
- [ ] Max worker count tuned

### Multiprocessing
- [ ] ProcessPoolExecutor (modern API)
- [ ] if __name__ == "__main__" guard
- [ ] No lambdas in args (pickle issue)
- [ ] maxtasksperchild for memory
- [ ] Shared state via Manager

### Asyncio
- [ ] No sync calls in async (use to_thread)
- [ ] uvloop installed (faster)
- [ ] TaskGroup (3.11+) over gather
- [ ] asyncio.timeout for cancellation
- [ ] CancelledError re-raised properly

### Production
- [ ] Graceful shutdown
- [ ] Resource cleanup (close connections)
- [ ] Monitoring (worker count, queue depth)
- [ ] Backpressure handling
```
