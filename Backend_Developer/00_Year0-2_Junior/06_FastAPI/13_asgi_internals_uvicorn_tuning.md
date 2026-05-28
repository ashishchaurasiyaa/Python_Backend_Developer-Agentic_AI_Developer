# ASGI Internals + Uvicorn/Gunicorn Tuning

> **Interview angle:** "FastAPI app slow under load — kya tune karoge before scaling horizontally?"

---

## 1. ASGI Kya Hai?

**ASGI** = Asynchronous Server Gateway Interface — successor of WSGI.

### WSGI vs ASGI

| Aspect | WSGI | ASGI |
|---|---|---|
| Sync/Async | Synchronous only | Both sync + async |
| WebSockets | ❌ No | ✅ Yes |
| Long-poll/SSE | Hard | Native |
| HTTP/2 | No | Yes |
| Used by | Django (old), Flask | FastAPI, Starlette, Django Channels |
| Spec | PEP 3333 | asgi.readthedocs.io |

---

## 2. ASGI App Protocol — 3 Arguments

```python
async def app(scope, receive, send):
    """Every ASGI app boils down to this signature."""
```

### `scope` — request metadata
```python
scope = {
    "type": "http",           # or "websocket", "lifespan"
    "method": "GET",
    "path": "/api/users",
    "query_string": b"page=1",
    "headers": [(b"host", b"localhost")],
    "client": ("127.0.0.1", 54321),
    "server": ("127.0.0.1", 8000),
    "asgi": {"version": "3.0", "spec_version": "2.3"},
}
```

### `receive` — async callable to get incoming events
```python
event = await receive()
# {"type": "http.request", "body": b"...", "more_body": False}
```

### `send` — async callable to send outgoing events
```python
await send({"type": "http.response.start", "status": 200, "headers": [...]})
await send({"type": "http.response.body", "body": b"Hello"})
```

### Minimal ASGI app
```python
async def app(scope, receive, send):
    assert scope["type"] == "http"
    await send({
        "type": "http.response.start",
        "status": 200,
        "headers": [(b"content-type", b"text/plain")],
    })
    await send({"type": "http.response.body", "body": b"Hello ASGI"})
```

---

## 3. Lifespan Protocol

```python
async def app(scope, receive, send):
    if scope["type"] == "lifespan":
        while True:
            message = await receive()
            if message["type"] == "lifespan.startup":
                # Initialize DB pools, load ML models
                await send({"type": "lifespan.startup.complete"})
            elif message["type"] == "lifespan.shutdown":
                # Close pools, save state
                await send({"type": "lifespan.shutdown.complete"})
                return
```

In FastAPI:
```python
@asynccontextmanager
async def lifespan(app):
    # startup
    await db.connect()
    yield
    # shutdown
    await db.disconnect()

app = FastAPI(lifespan=lifespan)
```

---

## 4. Starlette Internals (FastAPI's foundation)

FastAPI = Starlette + Pydantic + DI + OpenAPI.

```
HTTP Request
  ↓
Uvicorn (HTTP parser via httptools)
  ↓
ASGI Application (Starlette)
  ↓
Middleware Stack (CORS, auth, etc.)
  ↓
Router (matches URL pattern)
  ↓
Endpoint (your handler)
  ↓
Response
```

### Middleware is ASGI-wrapped
```python
class CORSMiddleware:
    def __init__(self, app):
        self.app = app
    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        # Inspect, modify, then forward
        await self.app(scope, receive, send)
```

### Request/Response are convenience wrappers
```python
# Inside FastAPI endpoint, this is what happens:
request = Request(scope, receive)
body = await request.body()
# Your code runs
response = JSONResponse({"data": "ok"})
await response(scope, receive, send)
```

---

## 5. Uvicorn — The ASGI Server

### Architecture
```
┌────────────────────────────────────┐
│  Uvicorn Master Process            │
│  ┌──────────────────────────────┐  │
│  │ Worker 1 (asyncio loop)      │  │
│  │   ├─ httptools (parse HTTP)  │  │
│  │   ├─ asyncio TCP             │  │
│  │   └─ Your ASGI app           │  │
│  └──────────────────────────────┘  │
│  ┌──────────────────────────────┐  │
│  │ Worker 2 (separate process)  │  │
│  └──────────────────────────────┘  │
└────────────────────────────────────┘
```

### Key Flags

```bash
uvicorn app:app \
  --host 0.0.0.0 \
  --port 8000 \
  --workers 4 \                    # number of worker processes
  --loop uvloop \                  # 2-4x faster event loop
  --http httptools \               # fast C HTTP parser
  --backlog 2048 \                 # TCP listen backlog
  --limit-concurrency 1000 \       # max concurrent reqs per worker
  --limit-max-requests 50000 \     # restart worker after N reqs (mem)
  --timeout-keep-alive 5 \         # close idle connections
  --proxy-headers \                # trust X-Forwarded-* from proxy
  --forwarded-allow-ips '*' \      # which proxies to trust
  --access-log \                   # log requests
  --no-server-header \             # hide "server: uvicorn"
  --ssl-keyfile key.pem \
  --ssl-certfile cert.pem
```

### Worker Sizing Formula
**Workers = (2 × CPU_cores) + 1**  (Gunicorn classic guidance)

For I/O-heavy FastAPI: workers = CPU_cores (since async handles concurrency per worker).

Example on 4 CPU machine:
- CPU-bound work → 4-8 workers
- I/O-bound (most APIs) → 2-4 workers

---

## 6. Gunicorn + Uvicorn (Production Combo)

Gunicorn = process manager, Uvicorn = worker class.

```bash
gunicorn app:app \
  --workers 4 \
  --worker-class uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8000 \
  --timeout 60 \
  --graceful-timeout 30 \
  --keep-alive 5 \
  --max-requests 50000 \
  --max-requests-jitter 5000 \    # randomize to avoid all workers reload together
  --preload \                      # share read-only memory
  --access-logfile - \
  --error-logfile -
```

### Why Gunicorn + Uvicorn (vs Uvicorn alone)?

| Feature | Uvicorn alone | Gunicorn + Uvicorn |
|---|---|---|
| Worker management | Basic | Advanced (graceful reload, max_requests) |
| Process supervision | ❌ | ✅ Restart on crash |
| Hot reload (deploy) | ❌ | ✅ HUP signal |
| Memory leak handling | ❌ | ✅ max_requests rotation |
| Production-grade | OK | Better |

**Modern alternative:** Use `--workers N` with `uvicorn` directly. Gunicorn less necessary in 2025+.

---

## 7. Performance Tuning Cheatsheet

### Worker Count
| Workload | Workers | Why |
|---|---|---|
| CPU-bound | 1-2 × CPU | Limited by GIL, processes give parallelism |
| I/O-bound | 2-4 (regardless of CPU) | Asyncio handles concurrency |
| Mixed | 2 × CPU + 1 | Gunicorn classic |
| Memory-heavy | Lower (model in RAM) | Avoid duplicating models |

### Connection Pool Sizing
DB pool size **per worker** = (workers × pool_size) ≤ db_max_connections

Example: PostgreSQL max=100, workers=4 → pool_size ≤ 25 per worker.

### Limit Settings

```bash
--limit-concurrency 1000      # backpressure — reject new conn if 1000 active
--limit-max-requests 50000    # restart worker → release memory leaks
--timeout-keep-alive 5        # close idle conn faster → save memory
--backlog 2048                # OS-level queued connections (default 2048)
```

---

## 8. Real Production Setup (Docker + K8s)

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml poetry.lock ./
RUN pip install poetry && poetry install --no-dev
COPY . .

# Run as non-root
RUN useradd -m appuser
USER appuser

CMD ["uvicorn", "app:app", \
     "--host", "0.0.0.0", \
     "--port", "8000", \
     "--workers", "4", \
     "--loop", "uvloop", \
     "--http", "httptools", \
     "--proxy-headers", \
     "--forwarded-allow-ips", "*"]
```

### Kubernetes Deployment
```yaml
resources:
  requests:
    cpu: "500m"
    memory: "512Mi"
  limits:
    cpu: "2000m"
    memory: "2Gi"

readinessProbe:
  httpGet:
    path: /health/ready
    port: 8000
  periodSeconds: 5

livenessProbe:
  httpGet:
    path: /health/live
    port: 8000
  periodSeconds: 30
  failureThreshold: 3
```

---

## 9. Debugging Performance

### Step 1: Profile under load
```bash
# Generate load
ab -c 100 -n 10000 http://localhost:8000/api/users

# OR locust
locust -f loadtest.py --host http://localhost:8000
```

### Step 2: Check what's bottleneck
```bash
# CPU profile via py-spy
py-spy record -o flame.svg --pid <uvicorn_pid> --duration 60

# Check connection counts
ss -s    # socket stats
netstat -an | grep :8000 | wc -l
```

### Step 3: Look at slow log
```python
# Add middleware to log slow requests
@app.middleware("http")
async def log_slow(request, call_next):
    t = time.perf_counter()
    response = await call_next(request)
    duration = time.perf_counter() - t
    if duration > 0.5:
        logger.warning(f"SLOW {request.method} {request.url.path} {duration:.2f}s")
    return response
```

---

## 10. Common Production Mistakes

### Mistake 1: Sync function inside async endpoint
```python
@app.get("/data")
async def get_data():
    data = blocking_io_call()    # ❌ blocks entire worker!
    return data

# Fix
@app.get("/data")
async def get_data():
    loop = asyncio.get_event_loop()
    data = await loop.run_in_executor(None, blocking_io_call)
    return data
```

### Mistake 2: Wrong worker count
- Too few → 503s under load
- Too many → memory OOM, context switching
- Sweet spot: load test + measure

### Mistake 3: No connection pool tuning
Pool exhausted → all requests wait → cascade failure.

### Mistake 4: No graceful shutdown
SIGTERM → drop in-flight requests → 502s.

Fix: handle SIGTERM in app, wait for in-flight to finish, then exit.

### Mistake 5: Logging blocking I/O
Default print → stdout buffered → can block. Use async logger.

---

## 11. Interview Questions

**Q1: ASGI vs WSGI?**
ASGI = async + WebSocket support. WSGI = sync only. ASGI superset.

**Q2: scope/receive/send kya hain?**
- scope: request metadata (path, headers)
- receive: async fetch incoming events (body chunks)
- send: async push outgoing events (response)

**Q3: How many workers for 4-CPU machine?**
I/O-bound: 4. CPU-bound: 8 (2N+1 rule). Always profile.

**Q4: Gunicorn vs Uvicorn?**
Gunicorn = process manager, Uvicorn = ASGI worker. Combined for graceful restart, max_requests.

**Q5: max_requests kyu zaroori?**
Memory leaks accumulate over time. Restarting worker after N reqs releases memory. Add jitter so all workers don't restart together.

**Q6: Async endpoint mein sync code call kiya — kya hoga?**
Entire worker blocks during that call. All concurrent requests wait. Use `run_in_executor` for blocking I/O.

**Q7: --preload flag kya karta?**
Loads app once in master, forks workers. Saves memory (read-only pages shared). But disables hot reload.

---

## 12. Best Practices

1. **uvloop + httptools** = ~3x faster
2. **Workers = 2-4 for I/O apps** (don't overprovision)
3. **max_requests with jitter** = handles memory leaks
4. **proxy-headers + forwarded-allow-ips** = behind nginx/ALB
5. **Health checks** = `/health/live` (process up) + `/health/ready` (deps ready)
6. **Graceful shutdown** = handle SIGTERM
7. **Connection pool sizing** = workers × pool ≤ db_max
8. **Profile before tuning** — guesses are wrong

---

## Related
- [[../01_Year3-4_Mid/01_Python_Advanced/theory/13_uvloop_deep_dive]]
- [[14_opentelemetry_distributed_tracing]]
- [[../01_Year3-4_Mid/04_DevOps/06_kubernetes_helm]]
