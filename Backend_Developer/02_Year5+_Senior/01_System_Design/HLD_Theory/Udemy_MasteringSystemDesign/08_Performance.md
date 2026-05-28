# 08. Performance — Latency, Throughput, Optimization

## Why Performance Matters

```
Real impact of latency:
- Amazon: +100ms latency = -1% sales
- Google: +400ms = -8% search traffic
- Walmart: -100ms = +1% revenue
- Pinterest: -40% latency = +15% SEO traffic

Real impact of throughput:
- 10x more concurrent users with same hardware = 90% cost reduction
- Higher throughput = better headroom for spikes
```

---

## Core Metrics

### Latency
Time for one operation.

| Percentile | What it means |
|---|---|
| p50 (median) | Typical user experience |
| p95 | 5% of users see this or worse |
| p99 | 1% of users see this or worse |
| p99.9 | "Tail latency" — the 1-in-1000 case |
| Mean | **Misleading** — outliers skew it |

**Always report percentiles, never just mean.**

### Throughput
Operations per unit time.

- **RPS** = Requests Per Second
- **QPS** = Queries Per Second
- **TPS** = Transactions Per Second
- **MBps** = Bandwidth

### Utilization
How "full" a resource is.

- CPU at 80% = healthy
- CPU at 95% = approaching saturation (queueing starts)
- Disk I/O at 90% = bottleneck imminent

**Little's Law:** `Concurrent requests = Throughput × Latency`
- 1000 RPS × 100ms latency = 100 concurrent
- Useful for capacity planning

---

## Latency Breakdown — Jeff Dean's Numbers (2026 updated)

| Operation | Time |
|---|---|
| L1 cache | 0.5 ns |
| Branch misprediction | 5 ns |
| L2 cache | 7 ns |
| Mutex lock/unlock | 25 ns |
| Main memory access | 100 ns |
| Compress 1KB (Zippy) | 3 μs |
| Send 1KB over 1Gbps | 10 μs |
| Read 1MB from SSD | 50 μs |
| Round trip same DC | 0.5 ms |
| Read 1MB from disk | 30 ms |
| Cross-region RTT | 80-150 ms |
| HTTP request (typical) | 100-500 ms |
| Database query (simple) | 1-10 ms |
| Database query (complex) | 100ms - 10s |
| LLM API call | 500ms - 30s |
| Stripe payment | 200-2000 ms |

**Use these for back-of-envelope estimation.**

---

## Latency Sources (Stack)

```
Total request latency = sum of:
─────────────────────
1. DNS lookup           20-200 ms (cached after first)
2. TCP handshake        50-150 ms
3. TLS handshake        50-200 ms (0 with session resumption)
4. Request transit      50-300 ms (depends on network)
5. Server processing    1ms - seconds
6. DB queries           1-100 ms
7. External API calls   100-2000 ms
8. Response transit     50-300 ms
9. Client rendering     50-500 ms

= Total user-perceived latency
```

**Optimization targets** = the biggest contributor to your latency.

---

## Common Performance Patterns

### 1. Reduce Latency

**Strategy: Move computation closer to user**
- CDN for static assets
- Edge computing (Cloudflare Workers, Fastly)
- Multi-region deployment
- Regional caches

**Strategy: Avoid unnecessary work**
- Caching (covered in [04_Caching.md](04_Caching.md))
- Lazy loading (compute on demand)
- Memoization (cache function results)
- Materialized views (precompute joins)

**Strategy: Parallelize**
- Fan-out parallel requests (`asyncio.gather`)
- Multi-threaded processing
- Batch operations
- Pipeline stages

**Strategy: Reduce data**
- Compression (gzip, brotli)
- Pagination (don't return 10K rows)
- Field selection (GraphQL, OData $select)
- Image optimization (WebP, AVIF)

---

### 2. Increase Throughput

**Strategy: Horizontal scaling**
- More servers
- Load balancer in front
- Stateless services (so any server can handle)

**Strategy: Async processing**
- Queue + worker (smooth spikes)
- Don't block on slow operations
- Event-driven architecture

**Strategy: Better algorithms**
- O(n²) → O(n log n) → O(n) where possible
- Right data structures (hash map vs list)
- Avoid N+1 queries (DataLoader)

**Strategy: Resource pooling**
- Connection pools (DB, HTTP)
- Thread pools
- Object pools

---

## Bottleneck Identification

### USE Method (Brendan Gregg)
For every resource, check:

- **Utilization**: % time resource was busy
- **Saturation**: queued work waiting
- **Errors**: error events

| Resource | U | S | E |
|---|---|---|---|
| CPU | `top` %us+sy | load avg vs cores | hardware errors |
| Memory | `free` used | swap activity, OOM kills | ECC errors |
| Disk | `iostat` %util | `iostat` avgqu-sz | I/O errors |
| Network | `sar` %ifutil | tx/rx queue drops | retransmits |

### RED Method (for services)
- **Rate** — requests/sec
- **Errors** — error rate
- **Duration** — latency distribution

Use for HTTP services dashboards.

### Four Golden Signals (Google SRE)
- **Latency**
- **Traffic**
- **Errors**
- **Saturation**

---

## Profiling

### CPU Profiling

**Python:**
```python
# Sampling profiler — minimal overhead
import py_spy
# Run: py-spy record -o profile.svg --pid <pid>

# Or with scalene (also profiles memory)
# scalene myapp.py

# Or cProfile (deterministic, high overhead)
import cProfile
cProfile.run('main()', 'profile.out')
import pstats
pstats.Stats('profile.out').sort_stats('cumulative').print_stats(20)
```

**Production (sampling, low overhead):**
- py-spy (Python)
- Pyroscope (continuous, eBPF-based)
- Parca

### Memory Profiling

```python
# memray
# memray run --live myapp.py

# tracemalloc (built-in)
import tracemalloc
tracemalloc.start()
# ... run code ...
snapshot = tracemalloc.take_snapshot()
top = snapshot.statistics('lineno')
for stat in top[:10]:
    print(stat)
```

### I/O Profiling

```python
# Look for: slow DB queries, blocking syscalls, network waits
# Tools: strace (syscalls), tcpdump (network), bpftrace (kernel)

# Python async — find blocking calls
import asyncio
asyncio.get_event_loop().set_debug(True)
# Logs warnings for callbacks > 100ms
```

### Flame Graphs

Visual representation of where time is spent:
- Width = time spent
- Height = stack depth
- Color = random (or by category)

```bash
# Generate flame graph from py-spy
py-spy record -f flamegraph -o flame.svg --pid <pid> --duration 60

# Or use Pyroscope for continuous flamegraphs
```

---

## Database Performance

### Indexing Strategy

```sql
-- Cover the WHERE clause
CREATE INDEX idx_orders_user_status ON orders(user_id, status);

-- Cover the ORDER BY (avoid sort)
CREATE INDEX idx_orders_created ON orders(created_at DESC);

-- Composite for multi-column
CREATE INDEX idx_compound ON orders(user_id, status, created_at DESC);

-- Partial indexes (when only a subset matters)
CREATE INDEX idx_active_orders ON orders(user_id) WHERE status = 'active';

-- Expression indexes
CREATE INDEX idx_lower_email ON users(LOWER(email));
```

**Verify usage:** `EXPLAIN ANALYZE` shows query plan.

### Query Optimization Checklist
- [ ] EXPLAIN shows index used? (not Seq Scan)
- [ ] LIMIT applied early?
- [ ] No SELECT *? (only needed columns)
- [ ] JOINs use indexed columns?
- [ ] No correlated subqueries in WHERE?
- [ ] Bulk inserts vs row-by-row?
- [ ] Transactions appropriately scoped?

### N+1 Query Problem

```python
# BAD: N+1
orders = await db.fetch_all("SELECT * FROM orders LIMIT 100")
for order in orders:
    user = await db.fetch_one("SELECT * FROM users WHERE id = :id", {"id": order.user_id})
# = 101 queries

# GOOD: JOIN or batch
result = await db.fetch_all("""
    SELECT o.*, u.* FROM orders o
    JOIN users u ON u.id = o.user_id
    LIMIT 100
""")
# = 1 query

# OR DataLoader pattern
loader = DataLoader(lambda ids: db.fetch_all("SELECT * FROM users WHERE id = ANY(:ids)", {"ids": ids}))
for order in orders:
    user = await loader.load(order.user_id)
# = 2 queries (1 for orders, 1 batched for users)
```

### Connection Pooling

```python
# Without pool — TCP handshake + auth per query
import asyncpg
conn = await asyncpg.connect(...)  # 50-100ms
result = await conn.fetch("...")
await conn.close()

# With pool
pool = await asyncpg.create_pool(
    dsn,
    min_size=10,
    max_size=50,
)
async with pool.acquire() as conn:
    result = await conn.fetch("...")  # < 1ms checkout
```

**For massive scale:** use **PgBouncer** in front of PG.

---

## API Performance

### Latency Optimization

```python
# 1. Parallel calls
async def get_dashboard(user_id):
    # Sequential — bad
    orders = await get_orders(user_id)            # 100ms
    profile = await get_profile(user_id)          # 100ms
    notifications = await get_notifications(user_id)  # 100ms
    # Total: 300ms

    # Parallel — good
    orders, profile, notifications = await asyncio.gather(
        get_orders(user_id),
        get_profile(user_id),
        get_notifications(user_id),
    )
    # Total: 100ms

# 2. Streaming responses (for large payloads)
from fastapi.responses import StreamingResponse

@app.get("/export")
async def export():
    async def generator():
        async for row in db.iterate_huge_query():
            yield json.dumps(row) + "\n"
    return StreamingResponse(generator(), media_type="application/x-ndjson")

# 3. Connection reuse
import httpx
client = httpx.AsyncClient(http2=True)  # reuse connection
# DON'T create new client per request
```

### Throughput Optimization

```python
# 1. Async everywhere (no blocking calls)
# Use asyncpg, aioredis, httpx — not psycopg2, redis-py-sync, requests

# 2. Increase worker count
# uvicorn main:app --workers 4   # one per CPU

# 3. Use Gunicorn + Uvicorn workers
# gunicorn -w 4 -k uvicorn.workers.UvicornWorker

# 4. Tune kernel
# /etc/sysctl.conf
# net.core.somaxconn = 4096
# net.ipv4.tcp_max_syn_backlog = 4096
```

---

## Caching Decisions

| Data | TTL | Layer |
|---|---|---|
| Static assets (CSS, JS) | 1 year + hash | CDN |
| Public API responses | 5-60 sec | CDN + Redis |
| User profile | 5 min | Redis |
| Session | 24 hours | Redis |
| Database query result | 1-30 sec | App-level |
| Computed (rankings) | 1-5 min | Redis + precompute |
| Sensitive | 0 (don't cache) | — |

(See [04_Caching.md](04_Caching.md) for deep dive.)

---

## Compression

```python
# FastAPI middleware
from fastapi.middleware.gzip import GZipMiddleware
app.add_middleware(GZipMiddleware, minimum_size=1000)

# Better: brotli (10-25% smaller than gzip)
from brotli_asgi import BrotliMiddleware
app.add_middleware(BrotliMiddleware, quality=4)
```

**Trade-off:** CPU cost vs bandwidth savings. For mobile users with slow networks, compression is huge win.

---

## CDN Strategy

```
Static (definitely cache):
- Images, videos, fonts, CSS, JS
- Cache headers: max-age=31536000 (1 year) + hash in filename

Semi-dynamic (cache with short TTL):
- Product catalog API
- Public profiles
- max-age=60 + stale-while-revalidate=600

Personalized (don't cache or cache per-user):
- User dashboard
- Cart
- Set: Cache-Control: private, no-store

Real-time (don't cache):
- Live chat, stock prices
- Cache-Control: no-cache
```

---

## Async Processing

### When to Make Async

```
Sync (in request):              Async (queue):
─────────────                   ─────────────
- Auth                          - Send emails
- Validation                    - Process images
- Quick DB read/write           - Generate reports
- Cache hit                     - ML inference
                                - External API calls
                                - Webhooks
                                - Bulk operations
```

### Patterns

```python
# Pattern 1: Background tasks (FastAPI built-in — for quick stuff)
@app.post("/signup")
async def signup(req, background_tasks: BackgroundTasks):
    user = await create_user(req)
    background_tasks.add_task(send_welcome_email, user.email)
    return user

# Pattern 2: Celery (durable, retry, distributed)
from celery import Celery
celery = Celery("tasks", broker="redis://")

@celery.task(bind=True, max_retries=3)
def process_image(self, image_url: str):
    try:
        # ...
        pass
    except Exception as e:
        raise self.retry(exc=e, countdown=60)

# Pattern 3: Kafka event-driven
await kafka_producer.send("user.signed_up", value=user_data)
# Multiple consumers process in parallel: email, analytics, CRM
```

---

## Performance Anti-Patterns

| Anti-pattern | Fix |
|---|---|
| Sync calls in async code | Use async clients |
| Loop with await inside | Use `asyncio.gather` |
| Loading 10K rows then filtering in Python | Filter in SQL |
| Creating new connections per request | Use connection pool |
| No timeouts on external calls | Always set timeouts |
| Logging everything synchronously | Async logging |
| Premature optimization | Profile first |
| Optimizing wrong thing | Measure first |
| No caching of expensive computations | Cache results |
| Recomputing the same value repeatedly | Memoize |

---

## Load Testing

```python
# k6 example
import http from 'k6/http';
import { check, sleep } from 'k6';

export const options = {
    stages: [
        { duration: '1m', target: 100 },
        { duration: '3m', target: 500 },
        { duration: '1m', target: 0 },
    ],
    thresholds: {
        http_req_duration: ['p(95)<300'],
        http_req_failed: ['rate<0.01'],
    },
};

export default function() {
    const res = http.get('https://api.example.com/users/123');
    check(res, { 'status 200': r => r.status === 200 });
    sleep(1);
}
```

**Locust (Python):**
```python
from locust import HttpUser, task, between

class APIUser(HttpUser):
    wait_time = between(1, 3)

    @task
    def view_dashboard(self):
        self.client.get("/dashboard")
```

(See [00_Year0-2_Junior/10_Testing/load_testing_locust_k6.md](../../../../00_Year0-2_Junior/10_Testing/load_testing_locust_k6.md))

---

## Performance Budget

Set explicit budgets before optimizing:

```
Page load:
- Total: < 3s on 3G
- TTFB: < 200ms
- First Contentful Paint: < 1.5s
- Time to Interactive: < 3s

API:
- p50: < 100ms
- p95: < 300ms
- p99: < 1s

Database:
- Single query: < 50ms
- Connection acquire: < 5ms

LLM (separate budget):
- TTFT: < 1s
- Throughput: > 30 tok/s
```

---

## Interview Q&A

### Q: How do you debug a slow API?

**Answer:**
1. **Reproduce locally** with realistic data
2. **Measure** — add timing logs at each step
3. **Profile** — py-spy or scalene on the live process
4. **Look at DB** — slow query log, EXPLAIN ANALYZE
5. **Check external** — are downstream APIs slow?
6. **Trace** — distributed tracing (OpenTelemetry) shows full path
7. **Form hypothesis** → test → iterate

### Q: How do you handle the C10K / C100K problem?

**Answer:**
- C10K: 10,000 concurrent connections solved by async I/O (epoll/kqueue)
- C100K-1M: requires careful tuning + fewer connections per server
- Tools: nginx, uvloop, Go, Rust, Erlang
- Key: never block the event loop

### Q: What's the difference between latency and throughput?

**Answer:**
- Latency = time for ONE operation
- Throughput = operations per second
- Often inverse: improving one can hurt the other
- Example: batching improves throughput (more ops/sec) but increases latency per request (waiting for batch)

### Q: How do you scale a slow database?

**Answer:**
1. **Index** — analyze slow queries, add indexes
2. **Query optimization** — rewrite expensive queries
3. **Cache** — Redis in front
4. **Read replicas** — offload reads
5. **Vertical scale** — bigger machine
6. **Partition** — break into chunks
7. **Shard** — multiple DBs
8. **Denormalize** — pre-join data
9. **Different DB** — NoSQL for specific use cases

### Q: How do you measure performance in production?

**Answer:**
- **APM** (Datadog, New Relic) — request traces
- **Prometheus + Grafana** — metrics
- **Continuous profiling** (Pyroscope) — code-level
- **RUM** (Real User Monitoring) — actual user experience
- **Synthetic checks** (Pingdom) — uptime, latency
- **SLOs** — define acceptable performance, alert on burn

---

## Cheat Sheet

```
Optimize this if metrics are bad:
─────────────────────────
Latency p99 high   → cache, parallel, async
Throughput low     → scale horizontally, async
DB CPU 100%        → optimize queries, cache, replicas
Memory growth      → memory leak, fix
GC pauses          → reduce allocations, tune GC
Network bottleneck → compression, fewer round trips
Disk I/O          → SSD, cache, batch writes
```

---

## Related Docs
- [04_Caching.md](04_Caching.md) — caching strategies
- [02_Scalability.md](02_Scalability.md) — scaling patterns
- [05_LoadBalancing.md](05_LoadBalancing.md) — distributing load
- [01_Year3-4_Mid/01_Python_Advanced/theory/07_performance_profiling.md](../../../../01_Year3-4_Mid/01_Python_Advanced/theory/07_performance_profiling.md) — Python profiling
- [00_Year0-2_Junior/10_Testing/load_testing_locust_k6.md](../../../../00_Year0-2_Junior/10_Testing/load_testing_locust_k6.md) — load testing
- [01_Year3-4_Mid/04_DevOps/05_prometheus_grafana.md](../../../../01_Year3-4_Mid/04_DevOps/05_prometheus_grafana.md) — observability
