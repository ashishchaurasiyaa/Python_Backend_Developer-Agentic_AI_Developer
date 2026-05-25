# FastAPI Performance Profiling

## Why It Matters

Profile, don't guess. Common bottlenecks: synchronous DB calls in async, N+1 queries, JSON serialization, missing indexes, sync code in async event loop.

Tools: cProfile, py-spy, Scalene, async-profiler, Locust load testing.

---

## Core Concepts

### py-spy (Sampling Profiler, No Code Change)

```bash
# Install
pip install py-spy

# Top — live CPU view
py-spy top --pid <PID>

# Flame graph (record N seconds)
py-spy record -o profile.svg --pid <PID> --duration 30

# Native mode (C extensions)
py-spy record -o profile.svg --pid <PID> --native --duration 30
```

Production-safe: no slowdown, no code change.

### cProfile (Deterministic Profiler)

```python
import cProfile
import pstats


def profile_endpoint():
    profiler = cProfile.Profile()
    profiler.enable()
    # Code to profile
    result = expensive_function()
    profiler.disable()

    stats = pstats.Stats(profiler).sort_stats('cumulative')
    stats.print_stats(20)


# Decorator
from functools import wraps


def profile(func):
    @wraps(func)
    async def wrapper(*args, **kwargs):
        profiler = cProfile.Profile()
        profiler.enable()
        try:
            return await func(*args, **kwargs)
        finally:
            profiler.disable()
            pstats.Stats(profiler).sort_stats('cumulative').print_stats(20)
    return wrapper


@app.get("/expensive")
@profile
async def expensive():
    return await heavy_work()
```

### Scalene (CPU + Memory + GPU)

```bash
pip install scalene
scalene --html --outfile profile.html app.py
```

Shows per-line: CPU time, memory allocation, GPU usage. Excellent for ML/data workloads.

### async-profiler / pyinstrument

```python
# pip install pyinstrument
from pyinstrument import Profiler


@app.middleware("http")
async def profile_middleware(request: Request, call_next):
    if request.query_params.get('_profile') == '1':
        profiler = Profiler(async_mode='enabled')
        profiler.start()
        response = await call_next(request)
        profiler.stop()
        # Return HTML profile
        from fastapi.responses import HTMLResponse
        return HTMLResponse(profiler.output_html())
    return await call_next(request)
```

`GET /endpoint?_profile=1` → see flame graph.

### Identifying Sync-in-Async (Event Loop Blocking)

```python
# BAD — blocks event loop
@app.get("/bad")
async def bad():
    time.sleep(1)            # blocks all requests
    result = requests.get("...")  # blocks all requests
    return {}


# GOOD
@app.get("/good")
async def good():
    await asyncio.sleep(1)
    async with httpx.AsyncClient() as c:
        result = await c.get("...")
    return {}
```

Detect:
```bash
# Aiomonitor — live event loop monitoring
pip install aiomonitor
# Add aiomonitor.start_monitor() to startup

# uvicorn flag for detecting blocking
uvicorn app:app --loop uvloop  # faster, surfaces blocking patterns
```

### Locust Load Testing

```python
# locustfile.py
from locust import HttpUser, task, between


class APIUser(HttpUser):
    wait_time = between(1, 3)

    def on_start(self):
        # Login once
        resp = self.client.post("/login", json={"email": "x@y.com", "password": "..."})
        self.token = resp.json()["token"]
        self.client.headers["Authorization"] = f"Bearer {self.token}"

    @task(3)
    def get_articles(self):
        self.client.get("/articles?limit=20")

    @task(1)
    def create_article(self):
        self.client.post("/articles", json={"title": "X", "body": "..."})
```

Run:
```bash
locust -f locustfile.py --host=http://localhost:8000 --users 100 --spawn-rate 10
# Web UI: http://localhost:8089
```

### Prometheus + Grafana Metrics

```python
from prometheus_client import Histogram, Counter
import time


REQUEST_DURATION = Histogram(
    'http_request_duration_seconds',
    'HTTP request duration',
    ['method', 'path', 'status'],
)
REQUEST_COUNT = Counter(
    'http_requests_total',
    'Total requests',
    ['method', 'path', 'status'],
)


@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    start = time.monotonic()
    response = await call_next(request)
    duration = time.monotonic() - start
    REQUEST_DURATION.labels(request.method, request.url.path, response.status_code).observe(duration)
    REQUEST_COUNT.labels(request.method, request.url.path, response.status_code).inc()
    return response


from prometheus_client import make_asgi_app
app.mount("/metrics", make_asgi_app())
```

### Identifying Slow DB Queries

```python
# SQLAlchemy
import logging
logging.basicConfig()
logging.getLogger('sqlalchemy.engine').setLevel(logging.INFO)


# Or hook for slow queries
from sqlalchemy import event


@event.listens_for(engine.sync_engine, "before_cursor_execute")
def before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    context._query_start_time = time.monotonic()


@event.listens_for(engine.sync_engine, "after_cursor_execute")
def after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    duration = time.monotonic() - context._query_start_time
    if duration > 0.5:  # > 500ms
        logging.warning(f"Slow query ({duration:.2f}s): {statement[:200]}")
```

---

## How It Works Internally

### CPU Profiling vs Wall-Clock

- **CPU**: only time CPU executing your code (excludes I/O waits)
- **Wall-clock**: total time, including I/O

Async apps: wall-clock more useful. Use pyinstrument with `async_mode='enabled'`.

### Sampling vs Tracing

- **Sampling** (py-spy, pyinstrument): collects stack snapshots periodically. Low overhead. Good for prod.
- **Tracing** (cProfile): tracks every function call. High overhead. Dev only.

### Event Loop Blocking Detection

```python
# Asyncio debug mode
import asyncio
asyncio.run(main(), debug=True)
# Logs warnings for sync calls taking too long
```

---

## Common Pitfalls

### 1. Profiling in Dev — Different Bottlenecks

Dev: SQLite, cold caches, 1 user. Prod: Postgres, warm caches, 1000 RPS. Always load test + profile in staging.

### 2. JSON Serialization Underestimated

Pydantic v1 was slow. Pydantic v2 (Rust) much faster. Use `orjson` for ultra-fast:

```python
import orjson
from fastapi.responses import ORJSONResponse


app = FastAPI(default_response_class=ORJSONResponse)
```

### 3. Sync Calls in Async Endpoints

`requests.get()` instead of `httpx.AsyncClient().get()` blocks event loop. All concurrent requests stall.

### 4. Profiler Affects Performance

cProfile = 10-100x slowdown. py-spy/Scalene = ~5% overhead. Pick right tool for context.

### 5. Premature Optimization

Profile FIRST. Code "looks slow" rarely matches reality.

---

## Interview Q&A

**Q1:** Production FastAPI profile karne ke tools?
**A:** py-spy (sampling, no code change, prod-safe) — top + record. pyinstrument middleware for per-request flame graphs. Scalene for memory. Locust for load testing. Prometheus + Grafana for SLI tracking.

**Q2:** Async endpoint mein block hone ka cause kya?
**A:** Sync call in async function: `requests.get`, `time.sleep`, `psycopg2.connect`, blocking ORM. Use `await asyncio.sleep`, `httpx.AsyncClient`, `asyncpg`/`psycopg3.AsyncConnection`. Detect: asyncio debug mode warnings, py-spy showing sleep in CPU samples.

**Q3:** JSON serialization slow ho — kya optimize karoge?
**A:** (1) Pydantic v2 (Rust core, 10x v1). (2) ORJSONResponse for fastest serialization. (3) Reduce response size — only return needed fields. (4) Streaming response for large arrays. (5) gzip compression at edge.

**Q4:** N+1 detect kaise karoge?
**A:** SQLAlchemy event listeners for query logging. pgBadger on Postgres logs. APM (Datadog, NewRelic) shows query count per request. Or: integration test with `assert_num_queries`.

**Q5:** Locust setup quickly?
**A:** `locustfile.py` with `HttpUser` class + `@task` methods. Run with `locust -f file.py --host URL`. Web UI at :8089. Configure users, spawn rate. Watch RPS + P50/P95/P99 latencies. Use for capacity planning.

**Q6:** Memory profiling Python mein?
**A:** Scalene (per-line memory). tracemalloc (built-in, snapshots). memory-profiler (@profile decorator). For prod: `objgraph` to find leaks (growing reference counts).

**Q7:** Single endpoint optimize from 500ms to 50ms — strategy?
**A:** (1) Profile to find bottleneck. (2) DB: add index, batch, use `select_related`/`prefetch`. (3) Cache (Redis/in-memory). (4) Parallel I/O (`asyncio.gather`). (5) Reduce payload. (6) Compile/JIT hot code path. (7) Move heavy compute to background task.

**Q8:** uvicorn vs gunicorn vs hypercorn?
**A:** uvicorn = ASGI server, fast (uvloop), default for FastAPI. gunicorn = manager for uvicorn workers (`gunicorn -w 4 -k uvicorn.workers.UvicornWorker`). Hypercorn = pure Python, supports HTTP/3. Use gunicorn + uvicorn workers in prod.

---

## Real-World Use Cases

### 1. CI Performance Budgets

```yaml
# .github/workflows/perf.yml
- run: locust --headless -u 50 -r 5 -t 60s --host http://app
- run: python check_p99.py  # fail if P99 > 500ms
```

### 2. Production Profiling on Demand

```bash
# SSH into pod
kubectl exec -it pod-x -- bash
py-spy top --pid 1
# Watch live CPU breakdown
```

### 3. APM Integration

DataDog APM auto-instruments FastAPI → per-endpoint traces, query counts, error rates.

---

## References

- [py-spy](https://github.com/benfred/py-spy)
- [pyinstrument](https://pyinstrument.readthedocs.io/)
- [Scalene](https://github.com/plasma-umass/scalene)
- [Locust](https://locust.io/)
- [Prometheus FastAPI integration](https://github.com/trallnag/prometheus-fastapi-instrumentator)
