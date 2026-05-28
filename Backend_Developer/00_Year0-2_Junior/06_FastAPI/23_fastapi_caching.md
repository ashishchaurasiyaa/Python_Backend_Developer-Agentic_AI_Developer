# FastAPI Caching — fastapi-cache2, ETag, Conditional GET

## Why It Matters

Caching = **biggest perf lever** for read-heavy APIs:
- **Cache layer** → skip DB/computation entirely
- **ETag / Cache-Control** → client-side cache, save bandwidth
- **Conditional GET** → 304 Not Modified responses
- **Stampede prevention** → single-flight for hot keys

Senior interview: "Endpoint hits DB 1000 RPS. Cache strategy?" → Redis + ETag + invalidation via Pub/Sub.

---

## Core Concepts

### Basic fastapi-cache2 Setup

```python
# pip install fastapi-cache2 redis
from fastapi import FastAPI
from fastapi_cache import FastAPICache
from fastapi_cache.backends.redis import RedisBackend
from fastapi_cache.decorator import cache
from redis import asyncio as aioredis


app = FastAPI()


@app.on_event("startup")
async def startup():
    redis_client = aioredis.from_url("redis://localhost:6379/0")
    FastAPICache.init(RedisBackend(redis_client), prefix="myapp-cache:")


@app.get("/articles")
@cache(expire=60)  # cache 60s
async def get_articles():
    # expensive DB query
    return await fetch_articles_from_db()
```

### Per-User Cache (key_builder)

```python
def user_key_builder(func, namespace="", request=None, response=None, *args, **kwargs):
    user_id = request.state.user_id if request else 'anon'
    return f'{namespace}:{func.__module__}.{func.__name__}:user:{user_id}'


@app.get("/my-feed")
@cache(expire=300, key_builder=user_key_builder)
async def my_feed(request: Request):
    user_id = request.state.user_id
    return await fetch_feed_for(user_id)
```

### Invalidation on Mutation

```python
from fastapi_cache import FastAPICache


@app.post("/articles")
async def create_article(payload: ArticleIn):
    article = await db.create(payload)
    # Invalidate list cache
    await FastAPICache.clear(namespace='articles')
    return article


@app.put("/articles/{article_id}")
async def update_article(article_id: int, payload: ArticleIn):
    await db.update(article_id, payload)
    # Invalidate specific keys
    await FastAPICache.clear(namespace=f'article:{article_id}')
```

### ETag (Strong Cache Validation)

```python
import hashlib
from fastapi import Request, Response


@app.get("/articles/{article_id}")
async def get_article(article_id: int, request: Request, response: Response):
    article = await db.get_article(article_id)
    if not article:
        raise HTTPException(404)

    # Compute ETag from content
    content = article.model_dump_json()
    etag = hashlib.md5(content.encode()).hexdigest()

    # Check client's If-None-Match
    if_none_match = request.headers.get('if-none-match', '')
    if if_none_match == etag:
        return Response(status_code=304)  # Not Modified

    response.headers['ETag'] = etag
    response.headers['Cache-Control'] = 'private, max-age=300'
    return article
```

### Last-Modified (Weak Validation)

```python
from datetime import datetime
from email.utils import format_datetime, parsedate_to_datetime


@app.get("/articles/{article_id}")
async def get_article(article_id: int, request: Request, response: Response):
    article = await db.get_article(article_id)

    last_modified = article.updated_at
    if_modified_since = request.headers.get('if-modified-since')
    if if_modified_since:
        try:
            client_time = parsedate_to_datetime(if_modified_since)
            if last_modified <= client_time:
                return Response(status_code=304)
        except (TypeError, ValueError):
            pass

    response.headers['Last-Modified'] = format_datetime(last_modified, usegmt=True)
    return article
```

### Cache-Control Header Variants

```
Cache-Control: public, max-age=3600        # CDN + browser cache 1h
Cache-Control: private, max-age=300        # browser only, 5 min
Cache-Control: no-cache                    # cache but always validate
Cache-Control: no-store                    # don't cache (sensitive)
Cache-Control: must-revalidate, max-age=0  # always check freshness
Cache-Control: stale-while-revalidate=60   # serve stale + refresh background
```

### Stampede Prevention (single-flight)

```python
from contextlib import asynccontextmanager
import asyncio


_locks: dict[str, asyncio.Lock] = {}


@asynccontextmanager
async def single_flight(key: str):
    lock = _locks.setdefault(key, asyncio.Lock())
    async with lock:
        yield


@app.get("/expensive")
async def expensive():
    cached = await r.get('expensive')
    if cached:
        return json.loads(cached)

    async with single_flight('expensive'):
        # Re-check after acquiring lock
        cached = await r.get('expensive')
        if cached:
            return json.loads(cached)

        result = await compute_expensive()
        await r.set('expensive', json.dumps(result), ex=300)
        return result
```

### Conditional GET with Strong + Weak ETags

```python
# Strong: byte-identical
# Weak: semantically equivalent (W/"abc")

response.headers['ETag'] = f'W/"{etag}"'   # weak
response.headers['ETag'] = f'"{etag}"'     # strong
```

### Vary Header

Cache different versions per request feature:

```python
response.headers['Vary'] = 'Accept-Encoding, Authorization'
# Browser/CDN cache separate versions for compressed vs not, per-auth
```

---

## How It Works Internally

### fastapi-cache2 Key Generation

```python
# Default: f'{prefix}:{module}.{function_name}:{args}:{kwargs_hash}'
# Override via key_builder for custom logic (e.g., per-user)
```

### Redis Backend Operations

```python
# cache hit: GET key → return cached
# cache miss: execute function → SETEX key value expire
# clear namespace: SCAN MATCH 'prefix:*' → DEL keys
```

### Browser Cache Validation Flow

```
1. Browser: GET /article/1 → Server returns ETag: "abc"
2. Browser stores response + ETag
3. Next request: GET /article/1, If-None-Match: "abc"
4. Server: same content → returns 304 (no body)
5. Browser uses cached body
```

---

## Common Pitfalls

### 1. Caching User-Specific Without Key Differentiation

Default `@cache` ignores user context → first user's data served to all.

### 2. ETag from `time.time()`

Defeats the purpose — every request gets unique ETag, no 304s.

### 3. Cache-Control on Sensitive Data

```python
# WRONG — bank balance cached on CDN!
Cache-Control: public, max-age=300
```

Use `private, max-age=N` for per-user. `no-store` for highly sensitive (passwords, tokens).

### 4. No Invalidation Strategy

Stale data forever. Either short TTL OR explicit invalidation on mutation.

### 5. Cache Stampede Ignored

100 concurrent requests after cache miss = 100 DB queries. Use single-flight.

### 6. Cache Backend Single Point of Failure

Redis down = total outage. Use multi-tier (LRU in-memory L1 + Redis L2 + DB L3) or graceful degradation.

### 7. Forgetting `Vary: Authorization`

Anonymous response cached → served to authenticated user. Always vary on auth header.

### 8. ETag Computation Cost > DB Query

If computing ETag = serializing the model = same cost as fetching, no win. ETag from `updated_at + id` is cheap.

---

## Interview Q&A

**Q1:** API caching strategy for 1000 RPS read-heavy endpoint?
**A:** Multi-layer: (1) Browser cache via `Cache-Control: public, max-age=300`. (2) CDN (Cloudflare/Fastly) honors same headers — serves from edge. (3) App-level Redis cache via fastapi-cache2. (4) DB query as fallback. (5) Cache invalidation on mutation via Pub/Sub. Stampede prevention via single-flight at app layer.

**Q2:** ETag vs Last-Modified?
**A:** ETag = content hash, exact match. Last-Modified = timestamp, second precision. ETag handles "changed within same second" cases. ETag is more expensive to compute (need content). Use both for compatibility — Django/FastAPI honors either header.

**Q3:** Cache invalidation strategies?
**A:** (1) TTL-based (stale tolerated). (2) Event-based (post-save signal clears cache). (3) Version-based (cache key includes `v{N}` from DB). (4) Tag-based (Redis sets of related keys). (5) CDN purge API for edge invalidation.

**Q4:** Stale-while-revalidate kya hai?
**A:** `Cache-Control: max-age=60, stale-while-revalidate=300` — fresh for 60s, after that serve stale for up to 300s while async refresh runs. User never waits for cache miss. CDN + browser support varies.

**Q5:** Per-user cache vs shared cache trade-offs?
**A:** Per-user: cache hit rate low (each user unique data), but accurate. Shared: high hit rate, but only for public data. Hybrid: public list shared, per-user filters in client. For SaaS dashboards, per-user is unavoidable; for product catalog, shared.

**Q6:** Cache hit rate kaise measure karoge?
**A:** Instrument with metrics: counter `cache_hits` + `cache_misses` per endpoint. Hit ratio = hits / (hits + misses). Target 80%+ for stable data. fastapi-cache2 + Prometheus integration. Investigate misses < 50% — bad key strategy or short TTL.

**Q7:** Redis cache down hone pe app crash kyun nahi karna chahiye?
**A:** Fallback to DB on cache miss/error. Wrap `cache.get()` in try/except, log error, return None → forces compute. For writes, log to deadletter for eventual cache update. Don't block writes on cache.

**Q8:** ETag SPA-friendly kaise banaoge?
**A:** Strong ETags for JSON resources (content hash). Weak ETags (W/"...") for HTML pages (whitespace insensitive). Combined with Vary header (`Vary: Accept, Authorization`). Service worker can also cache by ETag.

---

## Real-World Use Cases

### 1. Product Catalog (Shared, Long TTL)

```python
@app.get("/products")
@cache(expire=3600, namespace='products')
async def list_products(category: str = None):
    return await db.products(category=category)


@app.post("/products")
async def create_product(p: ProductIn):
    await db.create(p)
    await FastAPICache.clear(namespace='products')
```

### 2. User Dashboard (Per-User, Short TTL)

```python
@app.get("/dashboard")
@cache(expire=60, key_builder=user_key_builder)
async def dashboard(user=Depends(get_user)):
    return {'unread': await db.unread_count(user.id), ...}
```

### 3. Article Detail with ETag

Saves bandwidth — repeat hits return 304 with no body.

---

## References

- [fastapi-cache2](https://github.com/long2ice/fastapi-cache)
- [HTTP caching RFC 9111](https://datatracker.ietf.org/doc/html/rfc9111)
- [MDN HTTP Caching](https://developer.mozilla.org/en-US/docs/Web/HTTP/Caching)
- Fastly + Cloudflare cache guides
