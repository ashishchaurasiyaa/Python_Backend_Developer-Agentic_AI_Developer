# Debugging Production — pdb, debugpy, tracemalloc, py-spy

## Quick Concepts

**WHAT:**
- **pdb** = Python's built-in interactive debugger
- **ipdb** = pdb with IPython enhancements (colors, autocomplete)
- **debugpy** = Microsoft's debugger (VS Code uses this)
- **breakpoint()** = Built-in function (3.7+) to drop into debugger
- **tracemalloc** = Memory profiling (stdlib)
- **py-spy** = Sampling profiler (no code changes)
- **memray** = Bloomberg's memory profiler
- **Sentry** = Production error tracking

**WHY production debugging matters:**
- Can't always reproduce locally
- Stack overflow / memory leak under load
- Need to debug without restart (3 AM PagerDuty)

---

## Interview Questions & Answers

### Q1: pdb essentials — basic commands?

**Answer:**

**HOW — Drop into debugger:**

```python
def buggy_function(x, y):
    result = x * y
    breakpoint()  # ⭐ Built-in (Python 3.7+)
    return result

# When called, drops into pdb at this line
```

**HOW — Old way (pre-3.7):**

```python
import pdb

def buggy_function(x, y):
    pdb.set_trace()  # ⭐ Old way
    return x * y
```

**Essential pdb commands:**

| Command | Description |
|---|---|
| `n` (next) | Execute current line, go to next |
| `s` (step) | Step into function call |
| `c` (continue) | Continue until next breakpoint |
| `r` (return) | Continue until function returns |
| `l` (list) | Show current code |
| `ll` (long list) | Show entire function |
| `p var` | Print variable |
| `pp var` | Pretty print |
| `w` (where) | Show call stack |
| `u` (up) | Move up the stack |
| `d` (down) | Move down the stack |
| `b 25` | Set breakpoint at line 25 |
| `b file.py:25` | Breakpoint in specific file |
| `cl 1` | Clear breakpoint 1 |
| `q` (quit) | Quit debugger |
| `h` (help) | Show help |
| `!stmt` | Execute Python statement |

**HOW — Interactive session example:**

```python
def calculate(x, y):
    breakpoint()
    intermediate = x * 2
    final = intermediate + y
    return final


calculate(5, 10)

# In pdb:
# (Pdb) p x          → 5
# (Pdb) p y          → 10
# (Pdb) n            → Execute intermediate = x * 2
# (Pdb) p intermediate → 10
# (Pdb) p type(x)    → <class 'int'>
# (Pdb) !x = 100     → Change x to 100
# (Pdb) c            → Continue execution
```

---

### Q2: ipdb + better debugging UX?

**Answer:**

**HOW — Install ipdb:**

```bash
pip install ipdb

# Use environment variable to make breakpoint() use ipdb
export PYTHONBREAKPOINT=ipdb.set_trace
```

```python
def my_function():
    breakpoint()  # ⭐ Now uses ipdb (colors, autocomplete)
```

**HOW — Better alternative: pudb (TUI)**

```bash
pip install pudb
export PYTHONBREAKPOINT=pudb.set_trace
```

**HOW — Disable in production:**

```bash
# Production: skip breakpoint() calls
export PYTHONBREAKPOINT=0
```

---

### Q3: Conditional breakpoints?

**Answer:**

**WHAT:** Only break when condition met.

**HOW:**

```python
def process(items):
    for i, item in enumerate(items):
        # ⭐ Only break on specific iteration
        if i == 50 and item.value > 100:
            breakpoint()
        do_thing(item)


# Or in pdb session:
# (Pdb) b 25, x > 100   ← Break at line 25 only if x > 100
# (Pdb) c
```

**HOW — Catch only specific exceptions:**

```python
import sys

def excepthook(exc_type, exc_value, exc_tb):
    if isinstance(exc_value, ValueError):
        import pdb
        pdb.post_mortem(exc_tb)  # ⭐ Drop into debugger at exception
    else:
        sys.__excepthook__(exc_type, exc_value, exc_tb)

sys.excepthook = excepthook


# Or with `--pdb` flag in pytest
# pytest --pdb  → Drops into pdb on test failure
```

---

### Q4: debugpy — remote debugging from VS Code?

**Answer:**

**WHAT:** Debug Python running on remote server / Docker / K8s from local IDE.

**HOW — Server side:**

```python
# Add to your code
import debugpy

# Listen for debugger to attach
debugpy.listen(("0.0.0.0", 5678))
print("Waiting for debugger to attach...")
debugpy.wait_for_client()  # Optional: pause until attached
print("Debugger attached")

# Your normal code
def my_app():
    x = 10
    debugpy.breakpoint()  # ⭐ Break here when VS Code attached
    y = 20
    return x + y

my_app()
```

**HOW — VS Code launch.json:**

```json
{
    "version": "0.2.0",
    "configurations": [
        {
            "name": "Python: Remote Attach",
            "type": "debugpy",
            "request": "attach",
            "connect": {
                "host": "localhost",
                "port": 5678
            },
            "pathMappings": [
                {
                    "localRoot": "${workspaceFolder}",
                    "remoteRoot": "/app"
                }
            ]
        }
    ]
}
```

**HOW — Docker container debugging:**

```dockerfile
# Dockerfile.debug
FROM python:3.12-slim

RUN pip install debugpy

WORKDIR /app
COPY . .

# Expose debug port
EXPOSE 5678

CMD ["python", "-m", "debugpy", "--listen", "0.0.0.0:5678", "--wait-for-client", "app.py"]
```

```bash
# Run with debug port exposed
docker run -p 5678:5678 -p 8000:8000 myapp:debug

# VS Code → Attach to localhost:5678
```

---

### Q5: tracemalloc — memory leak detection?

**Answer:**

**WHAT:** Track memory allocations in pure Python.

**WHY:**
- Find memory leaks
- See top memory consumers
- No external dependencies

**HOW — Basic usage:**

```python
import tracemalloc

# Start tracking
tracemalloc.start()

# Code that may leak
my_list = []
for i in range(100000):
    my_list.append([i] * 100)

# Snapshot
snapshot = tracemalloc.take_snapshot()

# Top memory allocations
top_stats = snapshot.statistics("lineno")
print("[Top 10 memory consumers]")
for stat in top_stats[:10]:
    print(stat)
# Output:
# myapp.py:5: size=80000 KiB, count=100000, average=800 B
```

**HOW — Compare snapshots (find leaks):**

```python
import tracemalloc

tracemalloc.start()

# Baseline
snapshot1 = tracemalloc.take_snapshot()

# Run suspicious code
for _ in range(100):
    my_function_that_might_leak()

# After
snapshot2 = tracemalloc.take_snapshot()

# Compare
top_stats = snapshot2.compare_to(snapshot1, "lineno")
print("[Top 10 increases]")
for stat in top_stats[:10]:
    print(stat)
# Shows EXACTLY what allocated more memory
```

**HOW — Group by file:**

```python
top_stats = snapshot.statistics("filename")
for stat in top_stats[:5]:
    print(f"{stat.size_diff / 1024:.1f} KB - {stat.traceback}")
```

**HOW — Track specific limit:**

```python
import tracemalloc

# ⭐ Track 25 stack frames per allocation (slower but more context)
tracemalloc.start(25)


# ⭐ Get current memory
size, peak = tracemalloc.get_traced_memory()
print(f"Current: {size / 1024 / 1024:.1f} MB, Peak: {peak / 1024 / 1024:.1f} MB")
```

---

### Q6: py-spy — production profiling without restart?

**Answer:**

**WHAT:** Sampling profiler that attaches to running Python process.

**WHY:**
- No code changes needed
- Works on production processes
- Low overhead (~5%)
- Cross-platform

**HOW — Install:**

```bash
pip install py-spy

# Or system-wide
sudo pip install py-spy
```

**HOW — Profile running process:**

```bash
# Find Python process
ps aux | grep python

# Profile it (creates flamegraph SVG)
sudo py-spy record -o profile.svg --pid 12345 --duration 60

# Open profile.svg in browser
# Visual flame graph shows where time is spent
```

**HOW — Live top (like Linux top):**

```bash
sudo py-spy top --pid 12345

# Shows:
# - Current function on each thread
# - Time spent in each function
# - Updates in real-time
```

**HOW — Get current stack:**

```bash
# Print all threads' current stack
sudo py-spy dump --pid 12345

# Useful for: "what is process doing RIGHT NOW?"
```

**HOW — Profile script:**

```bash
# Run + profile in one command
py-spy record -o profile.svg -- python my_script.py
```

**WHY sampling > deterministic profiling:**
- cProfile slows app 10-100x (records every call)
- py-spy samples (e.g., 100 times/sec) → negligible overhead
- Good enough for finding bottlenecks

---

### Q7: Common Python bugs + how to debug?

**Answer:**

**Bug 1: Mutable default argument**

```python
# ❌ BUG
def add_item(item, items=[]):
    items.append(item)
    return items

print(add_item(1))  # [1]
print(add_item(2))  # [1, 2] ⚠️ Carries over!
print(add_item(3))  # [1, 2, 3]


# ✅ FIX
def add_item(item, items=None):
    if items is None:
        items = []
    items.append(item)
    return items
```

**Bug 2: Late binding closures**

```python
# ❌ BUG
funcs = []
for i in range(5):
    funcs.append(lambda: i)

for f in funcs:
    print(f())  # 4, 4, 4, 4, 4 ⚠️ All print last i


# ✅ FIX 1: Default argument captures i
funcs = [lambda x=i: x for i in range(5)]

# ✅ FIX 2: functools.partial
from functools import partial
funcs = [partial(lambda x: x, i) for i in range(5)]


for f in funcs:
    print(f())  # 0, 1, 2, 3, 4
```

**Bug 3: == vs is**

```python
a = 1000
b = 1000

print(a == b)  # True (equality)
print(a is b)  # False ⚠️ (different objects)


# ⚠️ Small ints (-5 to 256) cached, may appear is True
a = 1
b = 1
print(a is b)  # True (cached!)


# ✅ RULE
# Use ==  for value equality (lists, strings, ints)
# Use is for identity (None, True, False)
if x is None:  # ✅
if x == None:  # ⚠️ Works but unpythonic
```

**Bug 4: Modifying list during iteration**

```python
# ❌ BUG
items = [1, 2, 3, 4, 5]
for i in items:
    if i % 2 == 0:
        items.remove(i)  # ⚠️ Skips items
print(items)  # [1, 3, 5] but might be wrong


# ✅ FIX 1: Iterate over copy
for i in items[:]:  # Copy
    if i % 2 == 0:
        items.remove(i)


# ✅ FIX 2: Comprehension (preferred)
items = [i for i in items if i % 2 != 0]
```

**Bug 5: Shared state in threading**

```python
# ❌ BUG
counter = 0

def increment():
    global counter
    counter += 1  # ⚠️ Not atomic!

threads = [Thread(target=increment) for _ in range(10000)]
# Run all
# counter might be < 10000 (race condition)


# ✅ FIX 1: Lock
import threading
lock = threading.Lock()

def increment():
    global counter
    with lock:
        counter += 1


# ✅ FIX 2: threading.local
local = threading.local()
local.counter = 0  # Per-thread


# ✅ FIX 3: queue.Queue (thread-safe)
import queue
q = queue.Queue()
```

**Bug 6: Circular imports**

```python
# a.py
from b import B

class A:
    def use(self):
        return B()


# b.py
from a import A  # ⚠️ Circular import error

class B:
    pass


# ✅ FIX 1: Move import inside function
# a.py
class A:
    def use(self):
        from b import B  # ⭐ Import here
        return B()


# ✅ FIX 2: Restructure (move shared code to c.py)
```

---

### Q8: Debug strategy — production performance issue?

**Answer:**

**WHAT:** Step-by-step approach for "production is slow" complaint.

**HOW — Diagnostic workflow:**

```markdown
### 1. Confirm + Quantify
- [ ] Is it actually slow? (measure with curl + time)
- [ ] How slow? (200ms vs 5s vs timeout?)
- [ ] All endpoints or specific?
- [ ] All users or specific?
- [ ] Started when? (after deploy?)

### 2. Quick Diagnosis
- [ ] Check CloudWatch/Grafana dashboards
- [ ] Check error rate (5xx spike?)
- [ ] Check DB CPU/connections
- [ ] Check recent deployments
- [ ] Check external API health

### 3. Deep Dive
- [ ] py-spy on production process
- [ ] EXPLAIN ANALYZE slow queries
- [ ] Check application logs for slow_query warnings
- [ ] Sentry for error patterns
```

**HOW — py-spy investigation:**

```bash
# 1. Find process
ps aux | grep python

# 2. See what it's doing RIGHT NOW
sudo py-spy dump --pid 12345

# 3. Profile for 60 seconds
sudo py-spy record -o profile.svg --pid 12345 --duration 60

# 4. Open profile.svg
# Look for:
# - Tallest bars = most time spent
# - Unexpected functions
# - DB driver in stack (= waiting for DB)
# - JSON encode/decode (= use orjson)
# - GIL contention (= threading issue)
```

**HOW — SQL slow query investigation:**

```sql
-- Enable slow query log
ALTER SYSTEM SET log_min_duration_statement = '1000ms';
SELECT pg_reload_conf();

-- Then check logs for slow queries

-- Or find currently running queries
SELECT pid, query, state, query_start, NOW() - query_start AS duration
FROM pg_stat_activity
WHERE state = 'active' AND query NOT LIKE '%pg_stat_activity%'
ORDER BY duration DESC;

-- Top slow queries (with pg_stat_statements)
SELECT query, calls, mean_exec_time, max_exec_time
FROM pg_stat_statements
ORDER BY mean_exec_time DESC LIMIT 10;
```

---

### Q9: Sentry — production error tracking?

**Answer:**

**WHAT:** Centralized error tracking with context.

**HOW — Basic setup:**

```python
# pip install sentry-sdk

import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration

sentry_sdk.init(
    dsn="https://abc@sentry.io/123",
    integrations=[FastApiIntegration()],

    # Tracing
    traces_sample_rate=0.1,        # 10% of transactions

    # Profiling (Python 3.8+)
    profiles_sample_rate=0.1,

    # Environment
    environment="production",
    release="myapp@1.2.0",

    # PII
    send_default_pii=False,        # Don't send user data automatically

    # Server name
    server_name="api-server-1",
)


# Errors auto-captured
@app.get("/error")
async def trigger_error():
    raise ValueError("Test error")  # ⭐ Auto-reported to Sentry
```

**HOW — Add custom context:**

```python
# Add user context
sentry_sdk.set_user({
    "id": user.id,
    "email": user.email,
    "role": user.role,
})

# Add request context
sentry_sdk.set_context("request", {
    "endpoint": "/api/orders",
    "user_id": 123,
})

# Add tags (searchable)
sentry_sdk.set_tag("feature", "payments")
sentry_sdk.set_tag("subscription_tier", "pro")


# Manual capture
try:
    do_thing()
except Exception as e:
    sentry_sdk.capture_exception(e)
    raise


# Custom event
sentry_sdk.capture_message("Important event", level="info")


# Breadcrumbs (timeline of events)
sentry_sdk.add_breadcrumb(
    category="auth",
    message="User logged in",
    level="info",
    data={"user_id": 123},
)
```

**HOW — Filter sensitive data:**

```python
def before_send(event, hint):
    # Remove sensitive fields
    if "request" in event:
        request = event["request"]
        if "data" in request:
            data = request["data"]
            for key in ["password", "credit_card", "ssn"]:
                if key in data:
                    data[key] = "[REDACTED]"
    return event


sentry_sdk.init(
    dsn="...",
    before_send=before_send,
)
```

---

### Q10: Long-running process debugging?

**Answer:**

**WHAT:** Debug worker / long-running script that's stuck.

**HOW — Signal handler for stack dump:**

```python
import signal
import traceback
import sys

def dump_stack(signum, frame):
    """Print current stack when signal received."""
    print("===== Stack dump =====", file=sys.stderr)
    traceback.print_stack(frame, file=sys.stderr)

# Register: send SIGUSR1 → dump stack
signal.signal(signal.SIGUSR1, dump_stack)


# Now from terminal:
# kill -SIGUSR1 <PID>
# Process prints current stack without dying
```

**HOW — All threads dump:**

```python
import signal
import sys
import threading
import traceback

def dump_all_threads(signum, frame):
    print("===== ALL THREADS =====", file=sys.stderr)
    for thread_id, frame in sys._current_frames().items():
        print(f"\n=== Thread {thread_id} ===", file=sys.stderr)
        traceback.print_stack(frame, file=sys.stderr)

signal.signal(signal.SIGUSR2, dump_all_threads)
```

**HOW — Hot reload during development:**

```python
# pip install watchdog

# Use uvicorn --reload (for FastAPI)
# uvicorn main:app --reload

# Or manual watch
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import sys

class RestartHandler(FileSystemEventHandler):
    def on_modified(self, event):
        if event.src_path.endswith(".py"):
            print(f"Reloading {event.src_path}")
            os.execv(sys.executable, ["python"] + sys.argv)
```

---

## Debugging Toolkit Summary

| Tool | Use Case | Setup |
|---|---|---|
| `breakpoint()` | Interactive debug | None |
| `ipdb` | Better pdb (colors) | `pip install ipdb` |
| `debugpy` | VS Code remote | Add `import debugpy` |
| `tracemalloc` | Memory leaks | stdlib |
| `py-spy` | Production profile | `pip install py-spy` |
| `memray` | Memory profile (deep) | `pip install memray` |
| `cProfile` | Function profile | stdlib |
| `line_profiler` | Line-level | `pip install line_profiler` |
| `Sentry` | Error tracking | `pip install sentry-sdk` |
| `Datadog/New Relic` | APM | Paid |

---

## Production Debugging Checklist

```markdown
### Before Production
- [ ] Structured logging with request_id
- [ ] Sentry configured with environment + release
- [ ] py-spy installed on production
- [ ] Health check endpoints
- [ ] Slow query logging enabled

### During Incident
- [ ] py-spy dump to see current state
- [ ] py-spy record to profile (60s)
- [ ] Check CloudWatch / Grafana
- [ ] Check Sentry recent errors
- [ ] Check DB slow query log
- [ ] Check upstream service health

### After Incident
- [ ] Post-mortem (what, why, how prevent)
- [ ] Add monitoring/alerts
- [ ] Update runbook
- [ ] Add tests for regression
```

---

## Common Debugging Patterns

```python
# 1. Drop into pdb on exception
try:
    do_thing()
except Exception:
    import pdb; pdb.post_mortem()


# 2. Conditional breakpoint
if condition:
    breakpoint()


# 3. Profile single function
import cProfile
cProfile.runctx("my_function()", globals(), locals())


# 4. Time block
import time
start = time.perf_counter()
do_work()
print(f"Took {time.perf_counter() - start:.3f}s")


# 5. Memory snapshot
import tracemalloc
tracemalloc.start()
do_work()
snapshot = tracemalloc.take_snapshot()
for stat in snapshot.statistics("lineno")[:10]:
    print(stat)


# 6. Print to stderr (don't break stdout)
import sys
print("debug info", file=sys.stderr)


# 7. Logging vs print
import logging
log = logging.getLogger(__name__)
log.debug("var=%s", var)  # ⭐ Lazy eval (only if DEBUG enabled)
```
