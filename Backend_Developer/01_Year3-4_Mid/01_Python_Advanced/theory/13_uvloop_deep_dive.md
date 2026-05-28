# `uvloop` — High-Performance asyncio Event Loop

> **Interview angle:** "FastAPI app slow hai under load — kya tune karoge before scaling horizontally?"

---

## 1. Background — What is an Event Loop?

`asyncio` ka core component event loop hai — ye:
- Coroutines schedule karta hai
- I/O events (socket ready, timer fired) handle karta hai
- Callbacks fire karta hai

Default Python `asyncio` event loop **pure Python mein implemented** hai (`selectors` module wraps `epoll`/`kqueue`/`select`). Functional but **slow** kyunki Python overhead har step pe lagta hai.

---

## 2. `uvloop` Kya Hai?

`uvloop` = **drop-in replacement** for asyncio's default event loop, built on **libuv** (same as Node.js).

- Written in **Cython** (Python ke liye C performance)
- Uses **libuv** for event polling (battle-tested, used by Node.js)
- **2-4x faster** than default asyncio
- API 100% compatible with `asyncio`

```bash
pip install uvloop
```

```python
import asyncio
import uvloop

uvloop.install()              # one line, replaces default loop
# OR with asyncio.run:
asyncio.run(main(), loop_factory=uvloop.new_event_loop)  # Python 3.12+
```

---

## 3. Performance Comparison (Real Benchmarks)

### HTTP server (echo benchmark)
| Stack | Requests/sec |
|---|---|
| Flask (sync, single worker) | ~600 |
| Node.js (V8 + libuv) | ~45,000 |
| asyncio + aiohttp (default loop) | ~30,000 |
| **asyncio + aiohttp + uvloop** | **~75,000** |
| Go net/http | ~80,000 |

### TCP echo (raw)
| Loop | Throughput |
|---|---|
| Default asyncio | 100k msg/sec |
| **uvloop** | **350k msg/sec** |
| C epoll loop | 400k msg/sec |

**Takeaway:** uvloop closes the gap between Python and Node.js / Go.

---

## 4. How It Works Internally

```
Your coroutine (async def)
       ↓
asyncio Task (Python)
       ↓
uvloop event loop (Cython wrapper)
       ↓
libuv (C — epoll/kqueue/IOCP)
       ↓
OS kernel
```

**Why faster than default:**
1. **No Python overhead** in hot path — Cython compiled
2. **libuv is mature** — Node.js team optimized for years
3. **Batched syscalls** — fewer kernel transitions
4. **Faster callback dispatch** — direct C call vs Python function call

---

## 5. Usage Patterns

### Pattern 1: Plain script
```python
import asyncio
import uvloop

async def main():
    print("Hello uvloop")

uvloop.install()
asyncio.run(main())
```

### Pattern 2: FastAPI / Starlette
```python
# uvicorn picks uvloop automatically if installed
# uvicorn main:app --loop uvloop
```

Run:
```bash
uvicorn app:app --loop uvloop --http httptools
```

### Pattern 3: Explicit loop policy (older code)
```python
import asyncio
import uvloop

asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
loop = asyncio.get_event_loop()
loop.run_until_complete(main())
```

### Pattern 4: Python 3.12+ new API
```python
import asyncio
import uvloop

with asyncio.Runner(loop_factory=uvloop.new_event_loop) as runner:
    runner.run(main())
```

---

## 6. When uvloop helps (and when not)

### ✅ HELPS A LOT
- **High-concurrency network I/O** — HTTP servers, WebSockets, TCP
- **Many small async tasks** — each task has overhead
- **Latency-sensitive apps** — chat, real-time
- **Database connection pools** (asyncpg, aiomysql)

### ⚠️ MARGINAL HELP
- CPU-heavy workloads — GIL still dominates
- Single-task long-running coroutines
- Mostly synchronous code with little async

### ❌ DOESN'T WORK
- **Windows** — libuv works but uvloop officially doesn't support Windows
- **Code using selectors module directly**
- Some niche asyncio APIs (transport.get_extra_info quirks)

---

## 7. Compatibility Notes

```python
# These work identically:
- asyncio.create_task()
- asyncio.gather()
- asyncio.sleep()
- asyncio.Queue, Lock, Semaphore, Event
- aiohttp, asyncpg, redis-py async, motor (MongoDB)
- FastAPI, Starlette, Sanic
- aioredis, aiokafka
```

```python
# These have edge cases:
- subprocess on some platforms
- Signal handlers (custom)
- watch_fd patterns
```

**Rule of thumb:** 99% of asyncio code works unchanged.

---

## 8. Production Setup (FastAPI)

```bash
pip install fastapi uvicorn[standard] uvloop httptools
```

```bash
# Production command
uvicorn app:app \
  --host 0.0.0.0 \
  --port 8000 \
  --workers 4 \
  --loop uvloop \
  --http httptools \
  --proxy-headers
```

**Stack breakdown:**
- `uvloop` — event loop (libuv)
- `httptools` — HTTP parser (Node.js's parser, in C)
- Together = **~2-3x faster** than default `asyncio` + `h11`

---

## 9. Benchmarking Your Code

```python
import asyncio
import uvloop
import time

async def workload():
    tasks = [asyncio.sleep(0) for _ in range(100_000)]
    await asyncio.gather(*tasks)

# Default
start = time.perf_counter()
asyncio.run(workload())
print(f"asyncio: {time.perf_counter()-start:.3f}s")

# uvloop
uvloop.install()
start = time.perf_counter()
asyncio.run(workload())
print(f"uvloop:  {time.perf_counter()-start:.3f}s")
```

Typical output:
```
asyncio: 1.2s
uvloop:  0.3s    (4x faster)
```

---

## 10. Limitations & Gotchas

### Gotcha 1: Debugger compatibility
Some debuggers (older versions) struggle with uvloop frames. Modern PyCharm/VSCode handle it fine.

### Gotcha 2: `asyncio.run()` overrides loop policy
```python
uvloop.install()
asyncio.run(main())   # ✅ uses uvloop
```

### Gotcha 3: Test frameworks
`pytest-asyncio` works fine. Use:
```python
@pytest.fixture(scope="session")
def event_loop_policy():
    return uvloop.EventLoopPolicy()
```

### Gotcha 4: Subprocess on macOS
Old uvloop versions had `subprocess` quirks on macOS — upgrade to latest.

---

## 11. Alternatives

| Loop | Speed | Windows | Notes |
|---|---|---|---|
| `asyncio` (default) | 1x | ✅ | Standard |
| **uvloop** | **3-4x** | ❌ | Best for Linux/macOS |
| `winloop` | 2-3x | ✅ | uvloop port for Windows |
| `Trio` | 1x | ✅ | Different API — structured concurrency |

---

## 12. Interview Questions

**Q1: uvloop kyu fast hai default asyncio se?**
- Cython compiled (no Python overhead in hot path)
- Uses libuv (mature C library from Node.js)
- Faster callback dispatch
- Batched syscalls

**Q2: FastAPI mein uvloop enable kaise?**
```bash
uvicorn app:app --loop uvloop --http httptools
```

**Q3: uvloop kab nahi use karoge?**
- Windows production
- CPU-bound work (GIL is bottleneck, not loop)
- Need to use unsupported APIs

**Q4: libuv kya hai?**
Cross-platform async I/O library written in C — backs Node.js. Wraps epoll/kqueue/IOCP.

**Q5: Real-world performance gain?**
- HTTP throughput: 2-3x more req/sec
- Latency: 30-50% lower p99
- Especially good for high-concurrency (1000s of connections)

**Q6: uvloop production-ready?**
Haan — used by Sanic, FastAPI deployments, many large companies (Yelp, etc.). Stable since 2017.

---

## 13. Best Practices

1. **Always install uvloop** for Linux/macOS production
2. **Pair with httptools** for FastAPI/Starlette
3. **Benchmark your specific workload** — gains vary
4. **Pin version** in requirements (uvloop==0.20.0)
5. **Test in staging** first — rare edge cases
6. **Don't use on Windows** — use winloop or default loop

---

## Related
- [[05_async_concurrency_deep_dive]] — asyncio internals
- [[03_memory_gil]] — GIL still limits CPU work
- [[07_performance_profiling]] — measure before optimizing
