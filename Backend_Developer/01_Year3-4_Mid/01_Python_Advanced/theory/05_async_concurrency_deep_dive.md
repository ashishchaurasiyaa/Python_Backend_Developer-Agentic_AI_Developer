# 05 — Async & Concurrency Deep Dive
## Python Backend Developer Interview Prep | Target: 40 LPA

> **Hinglish Note:** Theory Hindi mein explain ki gayi hai taaki concepts clearly samajh aayein.
> Code, terms, aur technical keywords English mein hi rahenge.

---

## Table of Contents

1. [Concurrency vs Parallelism vs Async](#1-concurrency-vs-parallelism-vs-async)
2. [asyncio Event Loop Internals](#2-asyncio-event-loop-internals)
3. [gather vs create_task vs wait vs as_completed](#3-gather-vs-create_task-vs-wait-vs-as_completed)
4. [asyncio Synchronization Primitives](#4-asyncio-synchronization-primitives)
5. [Timeouts and Cancellation](#5-timeouts-and-cancellation)
6. [loop.run_in_executor()](#6-looprun_in_executor)
7. [concurrent.futures](#7-concurrentfutures)
8. [Threading Deep Dive](#8-threading-deep-dive)
9. [Multiprocessing Deep Dive](#9-multiprocessing-deep-dive)
10. [contextvars](#10-contextvars)
11. [Async Generators + Context Managers](#11-async-generators--context-managers)
12. [Real-World Patterns](#12-real-world-patterns)
13. [Decision Matrix](#13-decision-matrix)
14. [Interview Q&As](#14-interview-qas)

---

## 1. Concurrency vs Parallelism vs Async

### Definitions — Ek baar theek se samjho

**Concurrency (Samaankalik Kaam):**
> Ek se zyada kaam ek saath *chalu* hote hain, lekin exactly ek hi waqt pe ek kaam chal raha hota hai.
> CPU time-sharing karta hai. Jaise ek chef 3 dishes bana raha hai — ek ubaal ke rakh di, doosri chop kar raha hai.

**Parallelism (Saath-Saath Kaam):**
> Ek se zyada kaam literally ek hi waqt pe chal rahe hain — alag-alag CPU cores pe.
> Jaise 3 chef hain, teeno alag-alag dishes bana rahe hain simultaneously.

**Asynchronous (Pratiksha-Mukt Kaam):**
> Concurrency ka ek tarika. Koi kaam wait kar raha hai (jaise network response), toh CPU ko rok ke nahi rakhte —
> dusra kaam shuru kar do. Callback/await se result aane pe wapas aaoge.

```
CONCURRENCY (Single Core, Time-Shared):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Time → → → → → → → → → → → → → → →

Core 0: [Task A][Task B][Task A][Task C][Task B][Task C]
         ↑ switch  ↑ switch  ↑ switch  ↑ switch

Har task thodi der chalti hai, fir switch.
Ek hi core hai, lekin sab "running" lag raha hai.

PARALLELISM (Multi Core):
━━━━━━━━━━━━━━━━━━━━━━━━━
Time → → → → → → → → → → → → → →

Core 0: [Task A━━━━━━━━━━━━━━━━━━]
Core 1: [Task B━━━━━━━━━━━━━━━━━━]
Core 2: [Task C━━━━━━━━━━━━━━━━━━]

Teeno alag-alag cores pe literally ek saath chal rahe hain.

ASYNC (I/O Wait ka Smart Use):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Time → → → → → → → → → → → →

Core 0: [Task A: send req]...[Task B: send req]...[Task A: got resp][Task B: got resp]
                         ↑                    ↑
                    Task A wait karta hai,   Task B bhi wait karta hai,
                    CPU khali nahi chodta,   kaam karta rehta hai.
```

### Kab Kya Use Karein

| Situation | Best Approach | Reason |
|-----------|--------------|--------|
| 1000 HTTP requests | `asyncio` + `aiohttp` | I/O-bound, async is best |
| 8 image resize ops | `ProcessPoolExecutor` | CPU-bound, real parallel needed |
| Django sync view mein async | `asyncio.run()` / `sync_to_async` | Event loop naya banana padega |
| Sync DB driver async context mein | `run_in_executor(ThreadPool)` | Blocking code ko thread mein daal do |
| Log file parse karna | `ThreadPoolExecutor` | I/O + GIL doesn't matter much here |

### The GIL Problem — Samjho Ek Baar

```
GIL = Global Interpreter Lock

Python ka ek "mutex" jo kehta hai:
"Ek waqt pe sirf ek thread Python bytecode execute kar sakta hai."

Impact:
- CPU-bound kaam: threads se speedup NAHI milta (GIL block karta hai)
- I/O-bound kaam: threads kaam karte hain (I/O pe GIL release hota hai)
- Process: har process ka apna GIL — real parallelism milti hai
- C extensions (numpy, pandas): apna GIL release kar sakte hain
```

---

## 2. asyncio Event Loop Internals

### Event Loop — Dil Ki Dhadkan

```
asyncio Event Loop kya hai?
━━━━━━━━━━━━━━━━━━━━━━━━━━
Ek infinite loop jo 3 kaam karta hai:
1. Dekhta hai koi I/O ready hai? (epoll/kqueue syscall)
2. Ready callbacks ko execute karta hai
3. Scheduled callbacks (call_later) ko time pe run karta hai
```

### Event Loop Phases — Internal Architecture

```
┌─────────────────────────────────────────────────────────┐
│                   asyncio Event Loop                     │
│                                                         │
│  ┌──────────┐    ┌─────────────┐    ┌───────────────┐  │
│  │ I/O Poll │ →  │ Ready Queue │ →  │ Callbacks Run │  │
│  │ (epoll/  │    │ (callbacks  │    │ (actual Python│  │
│  │ kqueue/  │    │ waiting to  │    │  code runs)   │  │
│  │ select)  │    │  execute)   │    │               │  │
│  └──────────┘    └─────────────┘    └───────────────┘  │
│        ↑                                     │          │
│        └─────────────────────────────────────┘          │
│                  (loop continues)                        │
│                                                         │
│  ┌─────────────────────────────────────────────────┐   │
│  │ Scheduled Queue (call_later, call_at)           │   │
│  │ Jab time aata hai, Ready Queue mein daal do     │   │
│  └─────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘

OS Level:
- Linux: epoll (efficient, O(1) for large fd sets)
- macOS/BSD: kqueue
- Windows: IOCP (I/O Completion Ports)
- Fallback: select (older, O(n))
```

### `await` Kaise Kaam Karta Hai

```python
async def fetch_data():
    # Line 1: HTTP request bheja
    response = await http_get("https://api.example.com/data")
    # Line 2: Response aaya, process karo
    return response.json()
```

```
await ka matlab:
━━━━━━━━━━━━━━
1. fetch_data() chal raha tha
2. await http_get(...) pe pahuncha
3. http_get() ek Future/Coroutine return karta hai
4. Event loop ko control wapas deta hai: "Mujhe wait karna hai"
5. Event loop doosra kaam karta hai
6. Jab http response aata hai (I/O ready event), event loop
   fetch_data() ko wahan se resume karta hai jahan chhodha tha
7. response variable mein value milti hai
8. aage execution jari rehti hai

Yeh coroutine stack pe suspended rahti hai — memory mein,
not on OS thread stack. Isliye lakh coroutines chal sakti hain.
```

### `asyncio.get_event_loop()` vs `asyncio.get_running_loop()`

```python
import asyncio

# get_event_loop() — deprecated way
loop = asyncio.get_event_loop()  
# ⚠️ Python 3.10+ pe DeprecationWarning deta hai
# Agar koi loop nahi chal raha toh naya bana deta tha (dangerous)

# get_running_loop() — correct way
async def my_coro():
    loop = asyncio.get_running_loop()  # ✅ Current running loop milta hai
    # Agar koi loop nahi chal raha toh RuntimeError raise karta hai

# Best Practice:
# - Async function ke andar: get_running_loop()
# - Sync code mein loop chahiye: asyncio.get_event_loop() (careful!)
# - New code mein: asyncio.run() use karo, loop manually mat manage karo
```

### `asyncio.run()` — Recommended Entry Point

```python
import asyncio

async def main():
    print("Hello from async world!")
    await asyncio.sleep(1)
    print("Done!")

# asyncio.run() kya karta hai:
# 1. Naya event loop banata hai
# 2. main() coroutine run karta hai
# 3. Khatam hone pe loop close karta hai
# 4. Thread-safe nahi — main thread se hi call karo

asyncio.run(main())

# Internally roughly:
# loop = asyncio.new_event_loop()
# asyncio.set_event_loop(loop)
# try:
#     return loop.run_until_complete(main())
# finally:
#     loop.close()
```

### Tasks vs Coroutines vs Futures — Teen Alag Cheezein

```
COROUTINE:
━━━━━━━━━
- async def se define hota hai
- Call karne se coroutine object milta hai, execute nahi hota
- await karne pe actually run hota hai
- Ek "lazy" computation

async def greet(name):         # yeh coroutine function hai
    return f"Hello {name}"

coro = greet("Ashish")         # coroutine object mila, kuch nahi hua
result = await coro             # ab execute hua

FUTURE:
━━━━━━
- Low-level object
- "Ek promise ki tarah" — abhi value nahi hai, baad mein aayegi
- loop.run_in_executor() Future return karta hai
- Generally directly use nahi karte

TASK:
━━━━━
- Future ka subclass
- Ek coroutine ko wrap karta hai
- Immediately scheduled hota hai event loop mein
- Cancel kiya ja sakta hai
- State: PENDING → RUNNING → DONE/CANCELLED

task = asyncio.create_task(greet("Ashish"))
# Ab loop mein scheduled hai, jaldi execute hoga
result = await task  # wait for completion
```

### `asyncio.ensure_future()` vs `asyncio.create_task()`

```python
import asyncio

async def work():
    await asyncio.sleep(0.1)
    return 42

async def main():
    # ensure_future — purana tarika, 3.4.4+
    # Coroutine ya Future dono handle karta hai
    future = asyncio.ensure_future(work())
    
    # create_task — naya tarika, Python 3.7+
    # SIRF coroutine leta hai, Future nahi
    task = asyncio.create_task(work())
    
    # Difference:
    # ensure_future: agar Future mila toh return kar do, coroutine mila toh Task banao
    # create_task: hamesha Task banata hai, coroutine required
    
    # 2024 mein: create_task prefer karo, clearer hai
    
    r1 = await future
    r2 = await task
    print(r1, r2)  # 42 42

asyncio.run(main())
```

---

## 3. gather vs create_task vs wait vs as_completed

### `asyncio.gather()` — Sab Ka Intezaar Karo

```python
import asyncio
import time

async def fetch(n, delay):
    await asyncio.sleep(delay)
    return f"Result {n}"

async def demo_gather():
    start = time.perf_counter()
    
    # gather: sab coroutines ek saath start, sab ka wait karo
    # Return: list of results, same order as input
    results = await asyncio.gather(
        fetch(1, 0.3),
        fetch(2, 0.1),
        fetch(3, 0.2),
    )
    print(f"Time: {time.perf_counter()-start:.2f}s")  # ~0.3s (max)
    print(results)  # ['Result 1', 'Result 2', 'Result 3'] — order preserved!
    
    # return_exceptions=True — exception ko result ki tarah treat karo
    results = await asyncio.gather(
        fetch(1, 0.1),
        asyncio.sleep(0),  # this will succeed
        fetch(3, 0.2),
        return_exceptions=True
    )
    # Bina return_exceptions: pehli exception pe sab cancel
    # return_exceptions=True: exception bhi list mein aa jaati hai

asyncio.run(demo_gather())
```

### `asyncio.create_task()` — Individual Control Chahiye

```python
async def demo_create_task():
    # create_task: immediately scheduled, independent
    t1 = asyncio.create_task(fetch(1, 0.5), name="task-1")
    t2 = asyncio.create_task(fetch(2, 0.3), name="task-2")
    t3 = asyncio.create_task(fetch(3, 0.1), name="task-3")
    
    # Individual cancel kar sakte hain
    await asyncio.sleep(0.2)  # thoda wait karo
    t1.cancel()  # Task 1 cancel (abhi complete nahi hua)
    
    results = []
    for task in [t1, t2, t3]:
        try:
            results.append(await task)
        except asyncio.CancelledError:
            results.append(f"{task.get_name()} was cancelled")
    
    print(results)
    # ['task-1 was cancelled', 'Result 2', 'Result 3']
```

### `asyncio.wait()` — Fine-Grained Control

```python
async def demo_wait():
    tasks = {asyncio.create_task(fetch(i, 0.1*i)) for i in range(1, 6)}
    
    # FIRST_COMPLETED: pehla complete hote hi return karo
    done, pending = await asyncio.wait(
        tasks,
        return_when=asyncio.FIRST_COMPLETED
    )
    print(f"First done: {[t.result() for t in done]}")
    print(f"Still pending: {len(pending)}")
    
    # Baaki cancel karo ya process karo
    for task in pending:
        task.cancel()
    
    # FIRST_EXCEPTION: pehli exception pe return
    # ALL_COMPLETED: sab complete hone pe (gather jaisa lekin more control)
    
    # NOTE: wait() ke saath Tasks chahiye, Coroutines nahi
    # NOTE: wait() return_exceptions nahi karta, manually handle karo
```

### `asyncio.as_completed()` — Jaise Complete Ho, Process Karo

```python
async def demo_as_completed():
    coros = [fetch(i, (5-i)*0.1) for i in range(1, 6)]
    # Delays: 0.4, 0.3, 0.2, 0.1, 0.0 — last wala pehle complete hoga
    
    start = time.perf_counter()
    for coro in asyncio.as_completed(coros):
        result = await coro
        print(f"{result} at {time.perf_counter()-start:.2f}s")
    # Output order: Result 5, Result 4, Result 3, Result 2, Result 1
    # Jaise complete hue, waise print

    # gather vs as_completed:
    # gather: sab complete hone ka wait, result order preserve
    # as_completed: jaise done ho result lo, order of completion
```

### Timing Comparison Summary

```
5 tasks with delays [0.1, 0.2, 0.3, 0.4, 0.5]:

Sequential await:         ~1.5s  (0.1+0.2+0.3+0.4+0.5)
gather(*coros):           ~0.5s  (max delay)
create_task + gather:     ~0.5s  (same)
wait(ALL_COMPLETED):      ~0.5s  (same)
as_completed (first):     ~0.1s  (first result milta hai)
```

---

## 4. asyncio Synchronization Primitives

### `asyncio.Lock` — Race Condition Rokna

```
Race Condition kya hota hai?
━━━━━━━━━━━━━━━━━━━━━━━━━━━
Jab do coroutines ek shared resource pe kaam karti hain
aur ek doosre ke beech mein switch ho jaati hai — wrong result.

Example: counter = 0
Task A reads: 0
Task B reads: 0  (A ne abhi increment nahi kiya)
Task A writes: 1
Task B writes: 1  (Should be 2!)
Final: 1 (WRONG!)
```

```python
import asyncio

counter = 0
lock = asyncio.Lock()

async def increment():
    global counter
    async with lock:
        # Critical section — ek waqt pe sirf ek coroutine
        current = counter
        await asyncio.sleep(0)  # yield to show the problem without lock
        counter = current + 1

async def demo_lock():
    tasks = [asyncio.create_task(increment()) for _ in range(1000)]
    await asyncio.gather(*tasks)
    print(f"Counter: {counter}")  # 1000 (correct with lock)
```

### `asyncio.Semaphore` — Concurrency Limit

```python
# Use case: Zyada concurrent requests server ko overwhelm kar sakte hain
# Semaphore ek "token pool" ki tarah kaam karta hai

sem = asyncio.Semaphore(5)  # Max 5 concurrent

async def limited_api_call(url_id):
    async with sem:  # Token liya
        await asyncio.sleep(0.1)  # API call
        return f"data_{url_id}"
    # Token wapas — agla coroutine le sakta hai

# 20 tasks, max 5 ek waqt:
# Batch 1 (0-4): start immediately
# Batch 2 (5-9): wait for slot
# Batch 3 (10-14): wait
# Batch 4 (15-19): wait
# Total time: 4 * 0.1 = 0.4s (instead of all at once)
```

### `asyncio.Event` — One-Time Signal

```python
event = asyncio.Event()

async def waiter(name):
    print(f"{name}: waiting for signal...")
    await event.wait()  # Block until event is set
    print(f"{name}: signal received!")

async def signaler():
    await asyncio.sleep(0.5)
    print("Signaling all waiters!")
    event.set()  # Sab waiters ko unblock karo

async def demo_event():
    await asyncio.gather(
        waiter("W1"), waiter("W2"), waiter("W3"),
        signaler()
    )
    # event.clear() se reset kar sakte hain
    # event.is_set() se check kar sakte hain
```

### `asyncio.Queue` — Producer-Consumer Pattern

```python
# Queue ka use: producer aur consumer alag speed pe kaam karte hain
# Queue buffer ki tarah kaam karta hai

async def producer(q: asyncio.Queue, n: int):
    for i in range(n):
        item = f"item-{i}"
        await q.put(item)  # Agar queue full hai, wait karo
        print(f"Produced: {item}")
        await asyncio.sleep(0.1)

async def consumer(q: asyncio.Queue, cid: int):
    while True:
        item = await q.get()  # Agar queue empty hai, wait karo
        if item is None:
            q.task_done()
            break
        print(f"Consumer {cid} processing: {item}")
        await asyncio.sleep(0.05)  # Consumer faster hai
        q.task_done()

# Queue types:
# asyncio.Queue() — unlimited size
# asyncio.Queue(maxsize=10) — bounded
# asyncio.LifoQueue() — stack (last in, first out)
# asyncio.PriorityQueue() — priority order
```

### `asyncio.Condition` — Complex Synchronization

```python
# Condition = Lock + Event combined
# Jab kisi specific condition ka wait karna ho

condition = asyncio.Condition()
shared_resource = []

async def consumer_cond():
    async with condition:
        await condition.wait_for(lambda: len(shared_resource) > 0)
        item = shared_resource.pop()
        return item

async def producer_cond(item):
    async with condition:
        shared_resource.append(item)
        condition.notify()  # Ek waiter ko jagao
        # condition.notify_all()  # Sab waiters ko jagao
```

---

## 5. Timeouts and Cancellation

### `asyncio.wait_for()` — Simple Timeout

```python
import asyncio

async def slow_operation():
    await asyncio.sleep(10)
    return "done"

async def demo_wait_for():
    try:
        # 5 second timeout
        result = await asyncio.wait_for(slow_operation(), timeout=5.0)
    except asyncio.TimeoutError:
        print("Operation timed out!")
    
    # Wait_for internally:
    # 1. Task banata hai slow_operation() ka
    # 2. 5s baad task.cancel() call karta hai
    # 3. CancelledError ko TimeoutError mein convert karta hai
```

### `asyncio.timeout()` — Python 3.11+ Context Manager

```python
# Python 3.11+ ka naya clean syntax

async def demo_timeout_context():
    try:
        async with asyncio.timeout(5.0):
            result1 = await step1()
            result2 = await step2()  # Agar 5s ke andar dono complete nahi hue
            result3 = await step3()
    except TimeoutError:
        print("Total operation exceeded 5s")
    
    # Advantage over wait_for:
    # Multiple awaits ek timeout ke under rakh sakte hain
    # More readable code
```

### `task.cancel()` aur `CancelledError` Handling

```python
async def cancellable_task():
    try:
        while True:
            print("Working...")
            await asyncio.sleep(0.1)
    except asyncio.CancelledError:
        print("Task cancelled! Cleaning up...")
        # Cleanup karo — DB connections close karo, files close karo
        # await cleanup()  # Async cleanup bhi ho sakta hai
        raise  # IMPORTANT: CancelledError ko re-raise KARO!
        # Re-raise nahi kiya toh task "done" nahi hoga properly

async def demo_cancel():
    task = asyncio.create_task(cancellable_task())
    await asyncio.sleep(0.3)
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        print("Task is confirmed cancelled")
    
    # task.cancelled() → True
    # task.done() → True
```

### `asyncio.shield()` — Cancellation Se Bachao

```python
# Kab use karein: Koi critical operation hai jo cancel NAHI honi chahiye
# Jaise: payment transaction, important DB write

async def critical_save(data):
    await asyncio.sleep(0.5)  # DB save
    print(f"Saved: {data}")
    return True

async def demo_shield():
    task = asyncio.create_task(wrapper())
    
    async def wrapper():
        # Shield critical_save ko cancellation se bachata hai
        # Agar wrapper cancel hua toh shield wali task continue karti hai
        result = await asyncio.shield(critical_save("important_data"))
        return result
    
    task = asyncio.create_task(wrapper())
    await asyncio.sleep(0.1)
    task.cancel()  # wrapper cancel hogi, lekin critical_save nahi
    
    try:
        await task
    except asyncio.CancelledError:
        print("Wrapper cancelled but critical_save still ran!")
        await asyncio.sleep(1)  # critical_save finish hone do
```

---

## 6. loop.run_in_executor()

### Kyun Chahiye — The Blocking Problem

```
Problem:
━━━━━━━
Event loop single-threaded hai.
Agar koi blocking call karte hain (sync file read, sync DB query),
pura event loop ROOK jaata hai.

Jab tak blocking call complete nahi hoti,
KOI BAHI coroutine run nahi kar sakti!

Solution:
━━━━━━━━
Blocking kaam ko alag thread/process mein bhej do.
Wahan se result aa jaane pe event loop resume karo.
```

```python
import asyncio
import time
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor

def blocking_db_call(query: str) -> dict:
    """Sync psycopg2 call — blocks the thread"""
    time.sleep(0.2)  # Simulate DB query
    return {"result": f"data for {query}"}

def cpu_intensive(n: int) -> int:
    """Pure CPU work — no I/O"""
    return sum(i * i for i in range(n))

async def demo_run_in_executor():
    loop = asyncio.get_running_loop()
    
    # 1. Thread Pool for blocking I/O (sync drivers, file ops)
    with ThreadPoolExecutor(max_workers=4) as thread_pool:
        # Yeh event loop ko block nahi karega!
        result = await loop.run_in_executor(
            thread_pool,
            blocking_db_call,
            "SELECT * FROM users"
        )
        print(f"DB Result: {result}")
    
    # 2. Process Pool for CPU-bound work
    with ProcessPoolExecutor(max_workers=2) as proc_pool:
        result = await loop.run_in_executor(
            proc_pool,
            cpu_intensive,
            1_000_000
        )
        print(f"CPU Result: {result}")
    
    # 3. asyncio.to_thread() — Python 3.9+ shortcut (uses default thread pool)
    result = await asyncio.to_thread(blocking_db_call, "SELECT count(*) FROM orders")
    print(f"to_thread Result: {result}")
    
    # 4. None as executor — default thread pool use karo
    result = await loop.run_in_executor(None, blocking_db_call, "SELECT 1")
```

### ThreadPoolExecutor vs ProcessPoolExecutor — Kab Kya

```
ThreadPoolExecutor:
━━━━━━━━━━━━━━━━━
✓ Blocking I/O (sync DB drivers, sync file ops, legacy code)
✓ GIL I/O ke waqt release hoti hai
✗ CPU-bound kaam mein GIL ki wajah se speedup nahi
✓ Low overhead (threads cheap hain compared to processes)
✓ Shared memory — data share kar sakte hain

ProcessPoolExecutor:
━━━━━━━━━━━━━━━━━━
✓ CPU-bound kaam (image processing, ML inference, crypto)
✓ Real parallelism — har process ka apna GIL
✗ High overhead — process start karna time-consuming
✗ Data serialization (pickle) — slow for large objects
✗ Shared memory nahi — IPC se communicate karna padta hai

GIL and Threads:
━━━━━━━━━━━━━━━
- Pure Python CPU code: threads help nahi karte (GIL)
- NumPy/Pandas heavy ops: GIL release hoti hai, threads work karte hain
- File I/O: GIL release hoti hai during syscall
- Network I/O: GIL release hoti hai
- C extensions: apni marzi se GIL release kar sakte hain
```

---

## 7. concurrent.futures

### `ThreadPoolExecutor` — Thread Pool with Context Manager

```python
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor, as_completed, wait, FIRST_COMPLETED
import time

def fetch_url(url_id: int) -> str:
    time.sleep(0.1)  # Simulate network request
    return f"Response from URL {url_id}"

# Method 1: submit() — individual Future objects
def demo_thread_submit():
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(fetch_url, i) for i in range(10)]
        
        for future in futures:
            result = future.result()  # Blocking! Waits for this specific future
            print(result)

# Method 2: map() — cleaner, same order as input
def demo_thread_map():
    with ThreadPoolExecutor(max_workers=5) as executor:
        # map() is lazy — results milte hain as you iterate
        results = list(executor.map(fetch_url, range(10)))
        # Timeout support: executor.map(fn, items, timeout=5)
        print(results)

# Method 3: as_completed() — jaise done ho, process karo
def demo_as_completed_futures():
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {executor.submit(fetch_url, i): i for i in range(10)}
        
        for future in as_completed(futures):
            url_id = futures[future]
            try:
                result = future.result()
                print(f"URL {url_id}: {result}")
            except Exception as e:
                print(f"URL {url_id} failed: {e}")
```

### Future Methods

```python
from concurrent.futures import ThreadPoolExecutor

def slow_task(n):
    time.sleep(n)
    return n * 2

with ThreadPoolExecutor() as executor:
    future = executor.submit(slow_task, 2)
    
    # State check
    print(future.done())      # False (abhi chal raha hai)
    print(future.running())   # True
    print(future.cancelled()) # False
    
    # Cancel — sirf pending tasks cancel ho sakte hain, running nahi
    future.cancel()  # Returns True/False based on success
    
    # Result get karna
    try:
        result = future.result(timeout=3)  # 3s timeout
    except TimeoutError:
        print("Too slow!")
    except Exception as e:
        print(f"Task failed: {e}")
    
    # Callbacks add karna
    future.add_done_callback(lambda f: print(f"Done: {f.result()}"))
```

### `wait()` with FIRST_COMPLETED

```python
from concurrent.futures import wait, FIRST_COMPLETED, FIRST_EXCEPTION, ALL_COMPLETED

with ThreadPoolExecutor(max_workers=5) as executor:
    futures = [executor.submit(slow_task, i*0.1) for i in range(10)]
    
    # Pehle wala complete hote hi
    done, not_done = wait(futures, return_when=FIRST_COMPLETED)
    print(f"First done: {[f.result() for f in done]}")
    
    # Pehle exception aate hi
    done, not_done = wait(futures, return_when=FIRST_EXCEPTION)
    
    # Sab complete hone pe
    done, not_done = wait(futures, return_when=ALL_COMPLETED, timeout=5)
```

### `ProcessPoolExecutor` — Pickling Requirements

```python
# IMPORTANT: ProcessPoolExecutor mein sirf picklable objects bhej sakte hain
# Kya pickle nahi hota:
# - Lambda functions
# - Nested functions (mostly)
# - Open file handles
# - Database connections
# - Threading/asyncio primitives

# ✓ Top-level functions pickle hoti hain
def process_image(image_path: str) -> dict:
    # Yeh pickle hoga
    return {"processed": image_path, "size": "1024x768"}

# ✗ Yeh nahi chalega
def bad_example():
    processor = lambda x: x * 2  # Lambda!
    with ProcessPoolExecutor() as executor:
        executor.submit(processor, 5)  # PicklingError!

# ✓ Starmap for multiple args
def add(a, b):
    return a + b

with ProcessPoolExecutor(max_workers=4) as executor:
    # map() sirf ek iterable leta hai
    # starmap equivalent:
    from itertools import starmap
    args = [(1, 2), (3, 4), (5, 6)]
    futures = [executor.submit(add, a, b) for a, b in args]
    results = [f.result() for f in futures]
    print(results)  # [3, 7, 11]
```

---

## 8. Threading Deep Dive

### `threading.Thread` Basics

```python
import threading
import time

def worker(name: str, delay: float):
    time.sleep(delay)
    print(f"Thread {name} done")

# Method 1: Function threading
t1 = threading.Thread(target=worker, args=("A", 0.1), name="WorkerA")
t2 = threading.Thread(target=worker, args=("B", 0.2), name="WorkerB")

t1.start()  # Start both threads
t2.start()

t1.join()   # Main thread wait karega jab tak t1 finish ho
t2.join()

# Daemon Threads:
# Main program khatam hone ke baad daemon threads automatically kill ho jaate hain
# Non-daemon threads ke liye main thread unke khatam hone ka wait karta hai

t_daemon = threading.Thread(target=worker, args=("Daemon", 10), daemon=True)
t_daemon.start()
# Program yahan exit kar sakta hai, t_daemon ko khatam hone ka wait nahi karega
```

### Threading Synchronization Primitives

```python
import threading

# 1. Lock — Basic mutex
lock = threading.Lock()
shared_counter = 0

def safe_increment():
    global shared_counter
    with lock:  # Acquire, execute, release
        shared_counter += 1

# 2. RLock — Reentrant Lock
# Same thread baar baar acquire kar sakta hai
rlock = threading.RLock()

def recursive_fn(n):
    with rlock:
        if n <= 0:
            return 0
        return n + recursive_fn(n - 1)  # Nested acquire — RLock zaroori

# 3. Semaphore — Thread count limit
db_sem = threading.Semaphore(5)  # Max 5 DB connections

def db_operation():
    with db_sem:
        time.sleep(0.1)  # DB query

# 4. Event — Thread signaling
event = threading.Event()

def waiter_thread():
    event.wait()  # Block until set
    print("Event received!")

def setter_thread():
    time.sleep(1)
    event.set()  # Wake up all waiters
    # event.clear() — reset
    # event.is_set() — check

# 5. Condition — Complex coordination
condition = threading.Condition()
buffer = []

def producer_thread():
    with condition:
        buffer.append("item")
        condition.notify()

def consumer_thread():
    with condition:
        while not buffer:
            condition.wait()  # Release lock and wait
        item = buffer.pop()
```

### `threading.local()` — Thread-Local Storage

```python
# Ek variable jo har thread ka apna alag value rakhta hai
# Global variable ki tarah access, lekin har thread ka isolated

import threading

thread_local = threading.local()

def process_request(request_id):
    thread_local.request_id = request_id  # Is thread ka apna value
    thread_local.user = f"user_{request_id}"
    
    # Doosri function mein bhi milega
    log_request()

def log_request():
    # Isko request_id pass nahi kiya, fir bhi milega
    rid = getattr(thread_local, 'request_id', 'unknown')
    print(f"Processing request: {rid}")

# 5 threads, har ek ka apna request_id
threads = [threading.Thread(target=process_request, args=(i,)) for i in range(5)]
for t in threads: t.start()
for t in threads: t.join()
```

### GIL — Detailed Understanding

```
GIL (Global Interpreter Lock) — Full Story:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
History: Python reference counting ke liye thread-safety chahiye thi.
         Simplest solution: ek lock jo sab threads share karein.

How it works:
- Har 100 bytecodes (ya I/O) pe GIL switch ho sakta hai
- Python 3.2+ mein "new GIL" — 5ms interval (sys.getswitchinterval())

Kab threads help karte hain:
- I/O operations (file, network, socket) — GIL release hoti hai
- time.sleep() — GIL release hoti hai
- C extensions jo GIL release karte hain

Kab threads help nahi karte:
- Pure Python computation (loops, string ops, list comprehension)
- CPython bytecode execution

Bypass karne ke tarike:
1. ProcessPoolExecutor — har process ka apna GIL
2. Cython — GIL release directive
3. NumPy/SciPy — C code mein GIL release karte hain
4. ctypes — C functions call pe GIL release
5. Python 3.13 "free-threaded" mode (experimental)

Practical Impact:
def cpu_task(n): return sum(range(n))

# 4 threads: SLOWER than sequential (GIL contention)
# 4 processes: ~4x faster (true parallelism)
```

---

## 9. Multiprocessing Deep Dive

### `multiprocessing.Process` — Direct Process Control

```python
import multiprocessing
import os

def worker_process(name: str, result_queue: multiprocessing.Queue):
    pid = os.getpid()
    result = f"Process {name} (PID:{pid}) done"
    result_queue.put(result)

def demo_process():
    result_queue = multiprocessing.Queue()
    
    processes = [
        multiprocessing.Process(
            target=worker_process,
            args=(f"P{i}", result_queue)
        )
        for i in range(4)
    ]
    
    for p in processes:
        p.start()
    
    for p in processes:
        p.join()  # Sab processes khatam hone ka wait
    
    results = [result_queue.get() for _ in range(4)]
    print(results)

# multiprocessing.cpu_count() — available CPU cores
print(f"CPUs: {multiprocessing.cpu_count()}")
```

### Pool — High-Level Process Pool

```python
from multiprocessing import Pool
import os

def heavy_computation(n: int) -> int:
    """CPU-intensive task"""
    return sum(i * i for i in range(n))

def process_item(args):
    """For starmap"""
    x, y = args
    return x ** y

def demo_pool():
    with Pool(processes=4) as pool:
        
        # map() — simple, one arg per call
        results = pool.map(heavy_computation, [100000] * 8)
        print(f"map results: {results[:3]}...")
        
        # starmap() — multiple args per call
        args_list = [(2, 10), (3, 5), (4, 4)]
        results = pool.starmap(heavy_computation, [[n] for n in [100, 200, 300]])
        
        # apply_async() — non-blocking submit
        async_results = [
            pool.apply_async(heavy_computation, (n,))
            for n in [100000] * 8
        ]
        results = [r.get(timeout=10) for r in async_results]
        
        # imap() — lazy map (memory efficient for large datasets)
        for result in pool.imap(heavy_computation, range(10)):
            print(result, end=" ")
```

### IPC — Inter-Process Communication

```python
from multiprocessing import Queue, Pipe, Manager

# 1. Queue — Process-safe queue
def producer_proc(q: Queue, items: list):
    for item in items:
        q.put(item)
    q.put(None)  # Sentinel

def consumer_proc(q: Queue, results: list):
    while True:
        item = q.get()
        if item is None:
            break
        results.append(item * 2)

# 2. Pipe — Two-way communication (faster than Queue)
def sender(conn):
    conn.send([1, 2, 3])
    conn.send("Hello from sender")
    conn.close()

def receiver(conn):
    data1 = conn.recv()
    data2 = conn.recv()
    print(f"Received: {data1}, {data2}")

parent_conn, child_conn = Pipe()
# parent_conn.send(), parent_conn.recv()
# child_conn.send(), child_conn.recv()

# 3. Manager — Shared Python objects (proxy objects)
def modify_list(managed_list, n):
    managed_list.append(n)

with Manager() as manager:
    shared_list = manager.list()
    shared_dict = manager.dict()
    
    procs = [multiprocessing.Process(target=modify_list, args=(shared_list, i))
             for i in range(5)]
    for p in procs: p.start()
    for p in procs: p.join()
    print(list(shared_list))
```

### Shared Memory — Fast IPC

```python
from multiprocessing import Value, Array
import ctypes

# Value — single shared value
counter = Value(ctypes.c_int, 0)  # c_int type, initial value 0

def increment_counter(counter, n):
    for _ in range(n):
        with counter.get_lock():  # Thread/process safe
            counter.value += 1

# Array — shared array
shared_array = Array(ctypes.c_double, [1.0, 2.0, 3.0, 4.0, 5.0])

def scale_array(arr, factor):
    for i in range(len(arr)):
        arr[i] *= factor

# Note: Manager se zyada fast hai (direct shared memory)
# Lekin sirf primitive types support karta hai (int, float, char)
```

---

## 10. contextvars

### `ContextVar` — Per-Task Storage

```
contextvars ka problem solution:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Problem: Ek async application mein 100 concurrent requests handle ho rahe hain.
Har request ka apna request_id, user_id, trace_id hota hai.

Option 1: Har function mein parameter pass karo
→ Boilerplate zyada, every function signature mein

Option 2: threading.local()
→ Async context mein kaam nahi karta (coroutines threads nahi hote)

Option 3: ContextVar ✓
→ Har asyncio Task ka apna isolated context
→ Automatically inherit hota hai child tasks mein
→ Clean, no parameter passing needed
```

```python
from contextvars import ContextVar, copy_context
import asyncio

# Module level pe define karo
request_id: ContextVar[str] = ContextVar('request_id', default='unknown')
user_id: ContextVar[int] = ContextVar('user_id', default=0)

async def process_request(req_id: str, uid: int):
    # Set context for this task
    token_r = request_id.set(req_id)
    token_u = user_id.set(uid)
    
    try:
        await do_database_query()
        await send_response()
    finally:
        # Context reset — important for reuse
        request_id.reset(token_r)
        user_id.reset(token_u)

async def do_database_query():
    # No parameters needed — context se milta hai
    rid = request_id.get()
    uid = user_id.get()
    print(f"DB Query for request={rid}, user={uid}")
    await asyncio.sleep(0.1)

async def send_response():
    # Same request context available
    print(f"Response sent for request={request_id.get()}")

async def main():
    # 5 concurrent requests — sab ka apna isolated context
    await asyncio.gather(*[
        process_request(f"req-{i}", i * 100)
        for i in range(5)
    ])
```

### `copy_context()` — Context Isolation

```python
from contextvars import copy_context

# Background tasks ke liye — parent context copy karo
async def handle_request():
    request_id.set("req-123")
    
    # Background task — parent context ka copy milega
    ctx = copy_context()
    asyncio.create_task(ctx.run(background_job))
    
    # Agar background task context change kare,
    # parent pe koi effect nahi

async def background_job():
    print(f"BG task: {request_id.get()}")  # "req-123" milega
    request_id.set("bg-modified")  # Sirf is context mein
```

### contextvars vs threading.local()

```
threading.local():                  ContextVar:
━━━━━━━━━━━━━━━━━━                  ━━━━━━━━━━━
Per-thread storage                  Per-context storage
Works with threads                  Works with asyncio tasks
Not inherited                       Inherited by child tasks
No token/reset                      Token-based reset
Old API (Python 2 era)              New API (Python 3.7+)

IMPORTANT: asyncio mein sirf ContextVar use karo!
threading.local() ko asyncio mein use karne pe:
- Sab coroutines SAME thread pe run karti hain
- Sab coroutines SAME threading.local() value dekhti hain
- Data leakage between requests!
```

---

## 11. Async Generators + Context Managers

### Async Generators — `async def` + `yield`

```python
import asyncio
from typing import AsyncIterator

# Normal generator: yield se pause, next() se resume
# Async generator: yield se pause, await bhi kar sakta hai

async def fetch_pages(base_url: str, total_pages: int) -> AsyncIterator[dict]:
    """Paginated data ko lazily fetch karo"""
    for page in range(1, total_pages + 1):
        await asyncio.sleep(0.05)  # Simulate API call
        yield {
            "page": page,
            "data": [f"item_{page}_{i}" for i in range(10)]
        }

async def process_pages():
    # async for — async generator iterate karo
    async for page_data in fetch_pages("https://api.example.com", 5):
        print(f"Processing page {page_data['page']}: {len(page_data['data'])} items")
    
    # List comprehension with async generator
    pages = [page async for page in fetch_pages("https://api.example.com", 3)]
    
    # Filtering
    large_pages = [
        page async for page in fetch_pages("url", 10)
        if len(page["data"]) > 5
    ]
```

### `__aenter__` / `__aexit__` — Async Context Manager

```python
class AsyncDatabaseConnection:
    def __init__(self, url: str):
        self.url = url
        self.conn = None
    
    async def __aenter__(self):
        print(f"Connecting to {self.url}")
        await asyncio.sleep(0.1)  # Connection time
        self.conn = {"status": "connected", "url": self.url}
        return self.conn
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        print("Closing connection...")
        await asyncio.sleep(0.05)  # Close time
        self.conn["status"] = "closed"
        # Return True to suppress exceptions, False to propagate
        return False

async def use_db():
    async with AsyncDatabaseConnection("postgres://localhost/mydb") as conn:
        print(f"Using: {conn}")
        # Use connection
    print("Connection closed automatically")
```

### `@asynccontextmanager` — Decorator Way

```python
from contextlib import asynccontextmanager
import asyncio

@asynccontextmanager
async def managed_resource(name: str):
    # Setup
    print(f"Setting up {name}")
    resource = {"name": name, "active": True}
    
    try:
        yield resource  # Consumer code yahan run karta hai
    except Exception as e:
        print(f"Error in {name}: {e}")
        raise
    finally:
        # Cleanup — hamesha hoga (exception ke bawajood)
        resource["active"] = False
        print(f"Cleaned up {name}")

async def demo():
    async with managed_resource("redis-pool") as res:
        print(f"Working with: {res}")
        # Exception bhi raise karo — finally block phir bhi chalega
```

### `aiofiles` — Async File I/O

```python
# pip install aiofiles
import aiofiles
import asyncio

async def async_file_operations():
    # Write
    async with aiofiles.open("/tmp/test.txt", mode='w') as f:
        await f.write("Hello from async!\n")
        await f.write("Line 2\n")
    
    # Read
    async with aiofiles.open("/tmp/test.txt", mode='r') as f:
        content = await f.read()
        print(content)
    
    # Read line by line
    async with aiofiles.open("/tmp/test.txt") as f:
        async for line in f:
            print(line.strip())
    
    # Multiple files concurrently
    async def read_file(path: str) -> str:
        async with aiofiles.open(path) as f:
            return await f.read()
    
    # Read 10 files at the same time
    results = await asyncio.gather(*[
        read_file(f"/tmp/file_{i}.txt")
        for i in range(10)
    ])
```

---

## 12. Real-World Patterns

### Pattern 1: Async HTTP Client with Session Reuse

```python
import asyncio
import httpx

# ❌ Galat tarika — har request pe naya client
async def bad_http():
    for url in urls:
        async with httpx.AsyncClient() as client:
            resp = await client.get(url)  # New connection pool har baar!

# ✓ Sahi tarika — session reuse, connection pooling
async def good_http(urls: list[str]) -> list[str]:
    async with httpx.AsyncClient(
        timeout=10.0,
        limits=httpx.Limits(max_connections=100, max_keepalive_connections=20)
    ) as client:
        tasks = [client.get(url) for url in urls]
        responses = await asyncio.gather(*tasks, return_exceptions=True)
        
        results = []
        for url, resp in zip(urls, responses):
            if isinstance(resp, Exception):
                results.append(f"Error: {resp}")
            else:
                results.append(resp.text[:100])
        return results
```

### Pattern 2: Semaphore-Limited Concurrent API Calls

```python
async def fetch_with_rate_limit(
    urls: list[str],
    max_concurrent: int = 10
) -> list[str]:
    """Real-world rate limiting pattern"""
    semaphore = asyncio.Semaphore(max_concurrent)
    
    async def fetch_one(url: str) -> str:
        async with semaphore:
            await asyncio.sleep(0.1)  # Simulate API call
            return f"Response for {url}"
    
    return await asyncio.gather(*[fetch_one(url) for url in urls])
```

### Pattern 3: Async Retry with Exponential Backoff

```python
import asyncio
import random
from typing import TypeVar, Callable, Awaitable

T = TypeVar('T')

async def with_retry(
    coro_fn: Callable[[], Awaitable[T]],
    max_retries: int = 3,
    base_delay: float = 0.1,
    max_delay: float = 30.0,
    exceptions: tuple = (Exception,)
) -> T:
    """
    Exponential backoff with jitter.
    Delay formula: min(base * 2^attempt + jitter, max_delay)
    """
    for attempt in range(max_retries):
        try:
            return await coro_fn()
        except exceptions as e:
            if attempt == max_retries - 1:
                raise  # Last attempt — propagate
            
            delay = min(
                base_delay * (2 ** attempt) + random.uniform(0, 0.1),
                max_delay
            )
            print(f"Attempt {attempt + 1} failed: {e}. Retrying in {delay:.2f}s")
            await asyncio.sleep(delay)
    
    raise RuntimeError("Should not reach here")

# Usage
async def unstable_api():
    if random.random() < 0.7:
        raise ConnectionError("Server unavailable")
    return "Success!"

async def main():
    result = await with_retry(unstable_api, max_retries=5, base_delay=0.05)
    print(result)
```

### Pattern 4: Background Task Queue (Producer-Consumer)

```python
import asyncio
from dataclasses import dataclass
from typing import Any, Callable

@dataclass
class Task:
    id: str
    fn: Callable
    args: tuple
    kwargs: dict

class AsyncTaskQueue:
    def __init__(self, num_workers: int = 3):
        self.queue: asyncio.Queue = asyncio.Queue()
        self.num_workers = num_workers
        self.results: dict = {}
        self._workers: list = []
    
    async def start(self):
        self._workers = [
            asyncio.create_task(self._worker(i))
            for i in range(self.num_workers)
        ]
    
    async def stop(self):
        for _ in range(self.num_workers):
            await self.queue.put(None)  # Sentinels
        await asyncio.gather(*self._workers)
    
    async def _worker(self, worker_id: int):
        while True:
            task = await self.queue.get()
            if task is None:
                self.queue.task_done()
                return
            
            try:
                result = await task.fn(*task.args, **task.kwargs)
                self.results[task.id] = {"status": "done", "result": result}
            except Exception as e:
                self.results[task.id] = {"status": "error", "error": str(e)}
            finally:
                self.queue.task_done()
    
    async def submit(self, task: Task):
        await self.queue.put(task)
    
    async def wait_all(self):
        await self.queue.join()
```

### Pattern 5: Async Cache with Lock (Prevent Cache Stampede)

```python
import asyncio
import time
from typing import Any, Optional

class AsyncCache:
    """
    Cache stampede: Jab cache expire hota hai aur 1000 requests
    ek saath miss karti hain — sab DB pe jaaengi!
    
    Solution: Lock se sirf ek ko DB query karne do,
    baaki wait karein aur result share karein.
    """
    
    def __init__(self, ttl: float = 60.0):
        self._cache: dict[str, tuple[Any, float]] = {}
        self._locks: dict[str, asyncio.Lock] = {}
        self.ttl = ttl
    
    def _is_valid(self, key: str) -> bool:
        if key not in self._cache:
            return False
        _, timestamp = self._cache[key]
        return time.time() - timestamp < self.ttl
    
    async def get(self, key: str, fetch_fn: Callable) -> Any:
        # Fast path — cache hit, no lock needed
        if self._is_valid(key):
            value, _ = self._cache[key]
            return value
        
        # Slow path — cache miss, acquire lock
        if key not in self._locks:
            self._locks[key] = asyncio.Lock()
        
        async with self._locks[key]:
            # Double-check after acquiring lock
            # (Another coroutine might have filled it while we waited)
            if self._is_valid(key):
                value, _ = self._cache[key]
                return value
            
            # Actually fetch
            value = await fetch_fn(key)
            self._cache[key] = (value, time.time())
            return value

# Usage
cache = AsyncCache(ttl=30.0)

async def get_user(user_id: str) -> dict:
    async def fetch_from_db(key: str) -> dict:
        await asyncio.sleep(0.5)  # DB query
        return {"id": key, "name": "Ashish"}
    
    return await cache.get(f"user:{user_id}", fetch_from_db)
```

---

## 13. Decision Matrix

| Scenario | Recommended Approach | Reason |
|----------|---------------------|--------|
| 1000 HTTP requests | `asyncio` + `aiohttp`/`httpx` | I/O-bound, async is most efficient |
| Image processing 1000 files | `ProcessPoolExecutor` | CPU-bound, real parallelism needed |
| Calling sync DB driver (psycopg2) | `run_in_executor(ThreadPool)` / `asyncio.to_thread()` | Blocking I/O in async context |
| CPU + I/O mixed workload | `asyncio` (main) + `ProcessPoolExecutor` for CPU parts | Best of both worlds |
| Django sync view with async work | `asyncio.run()` or `sync_to_async` | New event loop for sync context |
| Rate-limited API calls | `asyncio.Semaphore` | Concurrent limit on coroutines |
| Request context propagation | `ContextVar` | Per-task isolated storage |
| Legacy sync library in FastAPI | `run_in_executor(ThreadPool)` | Don't block event loop |
| Shared state between processes | `multiprocessing.Manager` or `Value/Array` | Cross-process communication |
| Parallel ML inference | `ProcessPoolExecutor` | CPU + GIL bypass |
| File-based batch processing | `ProcessPoolExecutor` or `ThreadPoolExecutor` | Depends on processing type |
| Background email sending | `asyncio.Queue` + worker tasks | Decouple producer/consumer |
| Database connection pooling | `asyncpg` (async) / `SQLAlchemy async` | Native async drivers |
| 10 microservice calls in parallel | `asyncio.gather()` | Concurrent HTTP |
| Complex workflow (some steps depend on others) | `create_task()` + `await` | Flexible task graph |

### Quick Decision Tree

```
Kaam kya hai?
│
├─ I/O Heavy (Network, DB, Files)?
│   │
│   ├─ Async driver available? (aiohttp, asyncpg, aioredis)
│   │   └─ asyncio + async driver ✓ (BEST)
│   │
│   └─ Only sync driver?
│       └─ asyncio + run_in_executor(ThreadPool)
│
├─ CPU Heavy (Math, ML, Image Processing)?
│   │
│   ├─ Single machine?
│   │   └─ ProcessPoolExecutor ✓
│   │
│   └─ Distributed?
│       └─ Celery / Ray / Dask
│
└─ Mixed CPU + I/O?
    └─ asyncio for I/O parts + ProcessPool for CPU parts
```

---

## 14. Interview Q&As

### Q1: Event loop ko block karne se kya hota hai? Kaise bachein?

**Answer:**

> Event loop ko block karne se saari concurrent coroutines ruk jaati hain. Ek blocking call (jaise `time.sleep()`, sync DB query, CPU-heavy loop) puri application ko freeze kar deta hai.

```python
# ❌ Event loop block ho jaata hai
async def bad():
    time.sleep(5)  # Puri application 5 seconds ruk jaayegi!

# ✓ Sahi tarika
async def good():
    await asyncio.sleep(5)  # Sirf yeh coroutine ruke, loop chale

# ✓ Blocking I/O ke liye
async def good_blocking():
    result = await asyncio.to_thread(time.sleep, 5)

# Rule: Async function mein kabhi bhi time.sleep(), sync DB calls,
# ya CPU-heavy code directly mat likho
```

### Q2: GIL hai toh Python mein threads se speedup kyun milta hai I/O mein?

**Answer:**

> GIL sirf Python bytecode execution protect karta hai. Jab thread I/O syscall karta hai (read, write, recv, send), Python GIL release kar deta hai. Isliye doosra thread Python code run kar sakta hai jab pehla thread OS ke saath kaam kar raha hota hai.

```python
# CPU-bound: GIL nahi chhodta during computation
def cpu_task(n): return sum(range(n))
# 2 threads: sequential se SLOWER (GIL contention overhead bhi)

# I/O-bound: GIL release hoti hai during syscall
def io_task(): return requests.get("https://httpbin.org/delay/1")
# 2 threads: ~2x faster (dono requests parallel)
```

### Q3: asyncio vs threading — I/O-bound kaam ke liye kaun better?

**Answer:**

> `asyncio` zyada efficient hai because:
> - Ek thread mein lakho coroutines
> - Thread switching overhead nahi (OS ke bina context switch)
> - Memory: thread ~1MB stack vs coroutine ~few KB
> - Threading mein lock/race condition bugs zyada likely hain
>
> Threading useful hai jab:
> - Legacy sync libraries use karni ho
> - Code mein `await` nahi daal sakte (external library)
> - Thread-per-connection models mein

### Q4: ProcessPoolExecutor vs ThreadPoolExecutor — kab kaunsa?

| | ThreadPoolExecutor | ProcessPoolExecutor |
|--|--|--|
| CPU-bound | ❌ (GIL) | ✓ (True parallel) |
| I/O-bound | ✓ | Overkill |
| Shared memory | ✓ | ❌ (IPC needed) |
| Startup overhead | Low | High |
| Data passing | Cheap | Pickle needed |
| Max safe count | ~100 threads | CPU count |

### Q5: `asyncio.gather()` aur `asyncio.create_task()` mein kya fark hai?

**Answer:**

```python
# gather: ek call mein sab schedule, sab ka await
results = await asyncio.gather(coro1(), coro2(), coro3())
# - Coroutines ko wrap karta hai Tasks mein internally
# - Sab ka results ek saath milta hai
# - Ek exception pe default mein sab cancel (return_exceptions=True se nahi)

# create_task: early scheduling, individual control
t1 = asyncio.create_task(coro1())  # Already scheduled!
t2 = asyncio.create_task(coro2())
# ... kuch aur kaam...
t1.cancel()  # Individual cancel
r2 = await t2  # Individually await

# Key difference:
# gather() mein tasks simultaneously start honge
# create_task() pe hone se task tabhi scheduled ho jaata hai,
# even before await — useful for "fire and forget" style
```

### Q6: `asyncio.Semaphore` ka real-world use case batao

**Answer:**

> Semaphore use cases:
> 1. **Rate limiting:** Third-party API mein max 10 requests/second
> 2. **Connection limiting:** DB pool mein max 20 connections
> 3. **Resource limiting:** Memory-heavy operations ek saath max 5

```python
# Rate limiting example
rate_limiter = asyncio.Semaphore(10)  # Max 10 concurrent API calls

async def api_call(endpoint: str):
    async with rate_limiter:
        # Max 10 simultaneously
        async with httpx.AsyncClient() as client:
            return await client.get(f"https://api.example.com/{endpoint}")

# 1000 calls, max 10 at a time
results = await asyncio.gather(*[api_call(f"item/{i}") for i in range(1000)])
```

### Q7: `contextvars` vs `threading.local()` — async mein kaunsa use karein?

**Answer:**

> **Hamesha `ContextVar` use karo asyncio mein.**
>
> `threading.local()` thread-specific hai. Asyncio mein sab coroutines ek hi thread pe run karti hain, isliye sab ko same `threading.local()` value dikhti hai — **data leak between requests!**
>
> `ContextVar` asyncio-aware hai — har `create_task()` apna context copy karta hai.

```python
# ❌ Dangerous in asyncio
import threading
local_data = threading.local()
local_data.request_id = "req-1"  # Sab coroutines yeh dekhenge!

# ✓ Correct
from contextvars import ContextVar
request_id: ContextVar[str] = ContextVar('request_id')
# Har Task ka apna isolated value
```

### Q8: Async generator ka use case kya hai? Normal list return kyun nahi karte?

**Answer:**

> Async generator use cases:
> 1. **Paginated APIs:** Pehle page process karo, fir next fetch karo (lazy)
> 2. **Large datasets:** Saara data memory mein mat load karo
> 3. **Streaming data:** WebSocket ya SSE streams
> 4. **Database cursors:** Row by row process karo

```python
# ❌ Sab memory mein
async def get_all_users() -> list[User]:
    all_users = []
    for page in range(total_pages):
        users = await fetch_page(page)
        all_users.extend(users)  # 10 lakh users memory mein!
    return all_users

# ✓ Lazy — memory efficient
async def stream_users() -> AsyncIterator[User]:
    for page in range(total_pages):
        users = await fetch_page(page)
        for user in users:
            yield user  # Ek ek process karo

async for user in stream_users():
    await process_user(user)  # Sirf ek user memory mein
```

### Q9: `CancelledError` ko re-raise kyun karna chahiye?

**Answer:**

> `CancelledError` ko catch karke suppress karna dangerous hai:
> - Task cancel ho gayi toh caller ko pata nahi chalega
> - `asyncio.wait()` aur `gather()` ko pata nahi chalega ki task cancel hui
> - Cleanup karo zaroor, lekin hamesha `raise` karo

```python
async def safe_cancel():
    try:
        await long_operation()
    except asyncio.CancelledError:
        await cleanup()  # Cleanup karo
        raise  # ← MUST re-raise!
    
# CancelledError Python 3.8+ mein BaseException hai, Exception nahi
# Isliye broad except clauses se bachta hai
```

### Q10: `run_in_executor()` kab use karna chahiye?

**Answer:**

> Use karo jab:
> 1. **Sync DB drivers** (psycopg2, pymysql) ko async context mein call karna ho
> 2. **Blocking file I/O** (aiofiles available nahi ho)
> 3. **Legacy libraries** jo async support nahi karti
> 4. **CPU-heavy computation** (ProcessPoolExecutor ke saath)

```python
async def use_sync_library():
    loop = asyncio.get_running_loop()
    
    # Sync library call — thread mein bhejo
    result = await loop.run_in_executor(
        None,  # default thread pool
        sync_legacy_function,  # blocking function
        arg1, arg2  # arguments (no kwargs!)
    )
    
    # With kwargs — use functools.partial
    import functools
    fn_with_kwargs = functools.partial(sync_fn, key=value)
    result = await loop.run_in_executor(None, fn_with_kwargs)
```

### Q11: `asyncio.shield()` kab use karein?

**Answer:**

> `shield()` use karo jab koi critical operation (payment, DB write, audit log) cancel nahi honi chahiye, chahe calling task cancel ho jaaye.

```python
async def payment_handler(amount: float):
    # Payment process hone do even if request is cancelled
    try:
        result = await asyncio.shield(process_payment(amount))
        return result
    except asyncio.CancelledError:
        # Payment abhi bhi ho rahi hai background mein
        print("Request cancelled but payment continues")
        raise

# Note: Shield ke andar kisi ne cancel kiya toh cancel hogi
# Sirf outer task ka cancel andar propagate nahi hota
```

### Q12: FastAPI mein event loop kaise manage hota hai?

**Answer:**

> FastAPI Uvicorn/Starlette pe run hota hai jo asyncio event loop manage karta hai:
> - Uvicorn startup pe event loop create karta hai
> - Har HTTP request ke liye ek coroutine schedule hoti hai
> - `async def` routes directly event loop pe run hote hain
> - `def` (sync) routes thread pool mein run hote hain

```python
from fastapi import FastAPI
import asyncio

app = FastAPI()

# Async route — directly event loop pe
@app.get("/async")
async def async_route():
    await asyncio.sleep(0.1)  # Non-blocking
    return {"msg": "async"}

# Sync route — FastAPI thread pool mein run karta hai
@app.get("/sync")
def sync_route():
    time.sleep(0.1)  # Blocking — FastAPI ne thread mein bheja
    return {"msg": "sync"}

# Startup/shutdown events
@app.on_event("startup")
async def startup():
    # DB connections, cache warmup
    pass

@app.on_event("shutdown")
async def shutdown():
    # Cleanup resources
    pass
```

---

## Summary — Key Takeaways

```
1. asyncio: I/O-bound concurrent tasks ke liye best (network, DB async drivers)
2. ThreadPoolExecutor: Sync blocking code ko async context mein run karne ke liye
3. ProcessPoolExecutor: CPU-bound parallel work ke liye (GIL bypass)
4. Semaphore: Rate limiting, connection pooling
5. ContextVar: Per-request context in async apps (not threading.local!)
6. gather(): Simple concurrent execution, all or nothing
7. create_task(): Early scheduling, individual control
8. wait(): Fine-grained control with return_when
9. CancelledError: Hamesha re-raise karo cleanup ke baad
10. Event loop: Kabhi block mat karo — to_thread/run_in_executor use karo
```

---

*File created for 40 LPA Python Backend Developer Interview Prep*
*Series: Python Advanced (Year 3-4) | Topic 05*
