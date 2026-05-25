# Deadlock — Detection & Debugging

> **Interview angle:** "Production hang ho gaya — kuch requests respond nahi kar rahe. Kaise diagnose karoge?"

---

## 1. Deadlock Kya Hai?

Jab 2+ threads/tasks **ek-dusre ka lock release karne ka wait** kar rahe — koi proceed nahi kar sakta.

**Classic example (lock ordering):**
```python
lock_a = threading.Lock()
lock_b = threading.Lock()

def task1():
    with lock_a:
        with lock_b:    # waits for B
            ...

def task2():
    with lock_b:
        with lock_a:    # waits for A
            ...

# task1 holds A, wants B
# task2 holds B, wants A
# DEADLOCK
```

---

## 2. Four Necessary Conditions (Coffman conditions)

Deadlock hone ke liye **chaaron** chahiye:

1. **Mutual Exclusion** — resource ek hi thread use kar sakta
2. **Hold and Wait** — thread ek lock hold kar ke doosra wait kar raha
3. **No Preemption** — lock forcefully cheen nahi sakte
4. **Circular Wait** — A→B→C→A chain

**Break any one → no deadlock.**

---

## 3. Common Deadlock Patterns in Python

### Pattern A: Lock Ordering Inversion
```python
# Thread 1: lock A, then B
# Thread 2: lock B, then A
# Cross — deadlock
```

### Pattern B: Re-entrant Lock with `Lock` (not `RLock`)
```python
lock = threading.Lock()
def outer():
    with lock:
        inner()        # inner also acquires same lock
def inner():
    with lock:         # ❌ DEADLOCK — same thread, blocked
        ...
```

### Pattern C: Async + sync mixing
```python
async def handler():
    lock.acquire()        # threading.Lock blocks event loop!
    await some_io()
    lock.release()
```

### Pattern D: Database deadlock (table-level)
```python
# Txn 1: UPDATE users WHERE id=1 → UPDATE users WHERE id=2
# Txn 2: UPDATE users WHERE id=2 → UPDATE users WHERE id=1
# Postgres detects + kills one with: ERROR: deadlock detected
```

### Pattern E: Async event-loop deadlock
```python
async def producer():
    await queue.put(item)        # blocks if full

async def consumer():
    while True:
        item = await queue.get()
        await heavy_work_calling_producer()    # cycle
```

### Pattern F: Subprocess + PIPE buffer full
```python
proc = subprocess.Popen(cmd, stdout=PIPE, stderr=PIPE)
out, err = proc.communicate()    # if you forget to drain — pipe fills → child blocks
```

### Pattern G: Forking with locks held
```python
lock.acquire()
pid = os.fork()        # child inherits LOCKED lock — never released → deadlock
```

---

## 4. Detection Tools

### a) `faulthandler` — periodic stack dump
```python
import faulthandler
faulthandler.dump_traceback_later(timeout=30, repeat=True)
# Prints all thread stacks every 30s — if hung, you see exact lines
```

### b) `py-spy dump` — production-safe, no code change needed
```bash
pip install py-spy
py-spy dump --pid 12345
# Output shows every thread's current Python frame
# Look for `lock.acquire`, `queue.get`, `time.sleep`
```

### c) `signal` handler for SIGQUIT (Linux)
```python
import signal, faulthandler
signal.signal(signal.SIGUSR1, lambda *_: faulthandler.dump_traceback())
# kill -USR1 <pid>  → prints all stacks
```

### d) `asyncio` debug mode
```python
asyncio.run(main(), debug=True)
# Detects:
# - Coroutine never awaited
# - Task taking > 100ms
# - Synchronous code blocking event loop
```

### e) `threading.enumerate()` — live thread inspection
```python
import threading, traceback
for t in threading.enumerate():
    print(t.name, t.ident)
    traceback.print_stack(sys._current_frames()[t.ident])
```

### f) PostgreSQL deadlock log
```sql
-- postgresql.conf
log_lock_waits = on
deadlock_timeout = 1s
-- Logs include offending queries + lock graph
```

### g) GDB / lldb on live process
```bash
gdb -p 12345
(gdb) py-bt    # if py-bt extension installed
```

---

## 5. Prevention Techniques

### Technique 1: Consistent Lock Ordering
```python
# Define global order: ALWAYS acquire alphabetically / by id
def transfer(from_acc, to_acc, amt):
    first, second = sorted([from_acc, to_acc], key=lambda a: a.id)
    with first.lock:
        with second.lock:
            ...
```

### Technique 2: Use `RLock` for re-entrant code
```python
lock = threading.RLock()    # same thread can acquire N times
```

### Technique 3: Timeout on lock acquisition
```python
acquired = lock.acquire(timeout=5.0)
if not acquired:
    raise TimeoutError("Lock contention — possible deadlock")
```

### Technique 4: try-lock with backoff
```python
def try_lock_both(a, b):
    while True:
        if a.acquire(timeout=0.1):
            if b.acquire(timeout=0.1):
                return
            a.release()        # release first if can't get second
        time.sleep(random.uniform(0, 0.05))  # avoid livelock
```

### Technique 5: Single-thread design (avoid altogether)
```python
# Use async + single event loop
# Or actor model (one mailbox per actor)
```

### Technique 6: Use higher-level primitives
- `queue.Queue` instead of manual locks
- `concurrent.futures.ThreadPoolExecutor`
- `asyncio` patterns

### Technique 7: DB — `SELECT ... FOR UPDATE` in consistent order
```python
# All transactions sort IDs before locking rows
users = User.objects.select_for_update().filter(id__in=sorted_ids)
```

### Technique 8: Drop locks across I/O
```python
def buggy():
    with lock:
        result = http_call()    # ❌ blocks others for seconds

def fixed():
    with lock:
        data = prepare()
    result = http_call(data)    # ✅ outside lock
```

---

## 6. Async-Specific Deadlocks

### a) `asyncio.gather()` with same lock
```python
lock = asyncio.Lock()
async def task():
    async with lock:
        await asyncio.sleep(1)

await asyncio.gather(task(), task())   # serialized but no deadlock
```

### b) Calling sync blocking code without `run_in_executor`
```python
async def bad():
    time.sleep(10)         # ❌ blocks ENTIRE event loop

async def good():
    await asyncio.sleep(10)
    # or
    await loop.run_in_executor(None, blocking_func)
```

### c) `await` inside lock acquired in different task
```python
async def task1():
    await lock.acquire()
    await some_op()
    # Forgot to release on exception!
    lock.release()

# FIX: use `async with`
async def fixed():
    async with lock:
        await some_op()
```

---

## 7. Real Debugging Example

**Symptom:** FastAPI app — 5 out of 100 requests hang forever, others fine.

**Steps:**

```bash
# 1. Find the PID
ps aux | grep gunicorn

# 2. Dump stacks
py-spy dump --pid 12345
```

**Output:**
```
Thread 0x7f8b (idle): 5 active threads
  - /app/handlers.py:42 - acquire (in process_payment)
  - /app/handlers.py:55 - acquire (in update_inventory)
  - /app/db.py:101 - _commit
```

**Analysis:**
- `process_payment` holds `payment_lock`, wants `inventory_lock`
- `update_inventory` holds `inventory_lock`, wants `payment_lock`
- Classic lock ordering inversion

**Fix:** Always acquire in alphabetical order: inventory_lock → payment_lock.

**Verify:** `py-spy dump` again after deploy — no more lock waits.

---

## 8. Interview Questions

**Q1: Deadlock vs Livelock difference?**
- **Deadlock:** Threads stuck forever waiting for each other.
- **Livelock:** Threads keep changing state but no progress (both yielding to each other).

**Q2: Production mein deadlock detect kaise karoge?**
1. Hang detect — request latency monitoring
2. `py-spy dump --pid` for stack snapshot
3. Look for `lock.acquire` across threads → identify cycle
4. PostgreSQL: `pg_stat_activity` + `pg_locks`

**Q3: 4 conditions yaad hain?**
Mutex, Hold-and-Wait, No Preemption, Circular Wait.

**Q4: `Lock` vs `RLock`?**
RLock: re-entrant — same thread multiple acquire safe. Lock: same thread re-acquire = deadlock.

**Q5: Async deadlock kaise hota?**
- Sync `Lock` inside coroutine (blocks loop)
- Forgetting to release lock on exception
- Mutual `await` between tasks (cycle in awaitables)

**Q6: DB deadlock prevention?**
- Acquire locks in same order across txns
- Keep transactions short
- Use lower isolation levels where possible
- App-level retry on `deadlock_detected` error

**Q7: `signal.SIGKILL` se deadlock fix kar sakte?**
Process kar sakte, lock state corrupt ho sakta (e.g., file locks). Restart with cleanup.

---

## 9. Best Practices

1. **Avoid multi-lock acquisition** where possible
2. **Always use consistent ordering** if you must
3. **Set timeouts** on every `lock.acquire()`
4. **Prefer `RLock`** for ANY non-trivial code path
5. **Don't hold locks across I/O / RPC**
6. **Use `async with`** for async locks
7. **Enable `faulthandler` in production** — cheap insurance
8. **Monitor `pg_stat_activity`** for DB locks
9. **Test with stress + timeout** — catch hangs in CI
10. **Document lock hierarchy** in code comments

---

## Related
- [[11_race_conditions_debugging]] — race conditions
- [[05_async_concurrency_deep_dive]] — async patterns
- [[07_performance_profiling]] — py-spy usage
