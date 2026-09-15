# Django Caching Framework — Per-View, Low-Level, Conditional

## Why It Matters (Senior 5 YOE Context)

Caching = **single biggest perf lever** in Django prod. Without it, every request hits DB → P99 latency goes vertical. Django's cache framework supports:

- **Per-site cache** → entire site behind a CDN-like middleware
- **Per-view cache** → expensive views cached
- **Template fragment cache** → reusable HTML chunks
- **Low-level API** → arbitrary computed values (querysets, API responses)
- **Conditional view processing** → ETag/Last-Modified for 304 Not Modified

Senior interview: "How do you cache an expensive aggregation that updates every hour?" — `cache.set/get` + invalidation strategy.

---

## Core Concepts

### Backend Configuration

```python
# settings.py
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.redis.RedisCache',
        'LOCATION': 'redis://127.0.0.1:6379/1',
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
            'CONNECTION_POOL_KWARGS': {'max_connections': 50},
        },
        'KEY_PREFIX': 'myapp',
        'TIMEOUT': 300,  # 5 min default
    },
    'sessions': {
        'BACKEND': 'django.core.cache.backends.redis.RedisCache',
        'LOCATION': 'redis://127.0.0.1:6379/2',
    },
}

# Session backend
SESSION_ENGINE = 'django.contrib.sessions.backends.cache'
SESSION_CACHE_ALIAS = 'sessions'
```

Backends: `RedisCache` (prod), `LocMemCache` (dev), `MemcachedCache`, `DatabaseCache`, `FileBasedCache`, `DummyCache` (tests).

### Per-View Cache (`@cache_page`)

```python
from django.views.decorators.cache import cache_page

@cache_page(60 * 15)  # 15 min
def article_list(request):
    articles = Article.objects.published()
    return render(request, 'list.html', {'articles': articles})

# urls.py — alternative
path('list/', cache_page(60 * 15)(views.article_list))
```

**Pitfall:** `cache_page` keys include URL + GET params + Vary headers. Authenticated views need `Vary: Cookie` (auto) — but per-user caching = small cache hit rate. Use `@vary_on_cookie` or skip cache for logged in users.

### `Vary` Headers

```python
from django.views.decorators.vary import vary_on_headers, vary_on_cookie

@cache_page(60 * 15)
@vary_on_headers('User-Agent', 'Accept-Language')
def view(request):
    ...

@cache_page(60 * 15)
@vary_on_cookie  # per-user cache
def dashboard(request):
    ...
```

### Low-Level Cache API

```python
from django.core.cache import cache

# Set/get
cache.set('mykey', value, timeout=300)
value = cache.get('mykey', default=None)

# Get-or-compute pattern
def get_top_articles():
    key = 'top_articles:v1'
    articles = cache.get(key)
    if articles is None:
        articles = list(Article.objects.popular()[:10])
        cache.set(key, articles, timeout=3600)
    return articles

# get_or_set — atomic
articles = cache.get_or_set(
    'top_articles:v1',
    lambda: list(Article.objects.popular()[:10]),
    timeout=3600,
)

# Batch ops
cache.set_many({'a': 1, 'b': 2}, timeout=300)
cache.get_many(['a', 'b'])  # returns dict
cache.delete_many(['a', 'b'])

# Counter (atomic in Redis)
cache.incr('hits')
cache.decr('hits')

# Add (only if not exists — distributed lock-ish)
acquired = cache.add('lock:job', 'owner', timeout=30)
```

### Template Fragment Caching

```django
{% load cache %}
{% cache 600 sidebar request.user.id %}
    {% include 'sidebar.html' %}
{% endcache %}
```

Vary by user — `request.user.id` is the vary key.

### Conditional View Processing (ETag + Last-Modified)

```python
from django.views.decorators.http import etag, last_modified
from django.utils.http import quote_etag

def article_etag(request, article_id):
    return quote_etag(Article.objects.values('updated_at').get(pk=article_id)['updated_at'].isoformat())

def article_last_modified(request, article_id):
    return Article.objects.values('updated_at').get(pk=article_id)['updated_at']

@etag(article_etag)
@last_modified(article_last_modified)
def article_detail(request, article_id):
    article = get_object_or_404(Article, pk=article_id)
    return JsonResponse({'id': article.id, 'title': article.title})
```

**Result:** Client sends `If-None-Match: "abc"` → Django returns `304 Not Modified` (no body). Huge bandwidth save.

---

## How It Works Internally

### Key Generation

```python
# cache.set('mykey', value)
# Actual Redis key:
# f'{KEY_PREFIX}:{VERSION}:{key}'
# Default: 'myapp:1:mykey'

# Per-view cache keys (cache_page):
# f'views.decorators.cache.cache_page.{prefix}.{method}.{url}.{vary_headers_hash}'
```

### Cache Versioning (Bulk Invalidation)

```python
# Manual version bump (clears all keys at once)
cache.set('mykey', value, version=2)
cache.get('mykey', version=2)

# Pattern: bump global version on deploy
CACHE_VERSION = int(os.environ.get('CACHE_VERSION', '1'))
```

### Locking via `cache.add()`

```python
# add() returns True only if key didn't exist — atomic
def expensive_task():
    if not cache.add('lock:expensive', 'owner', timeout=60):
        return  # someone else is running
    try:
        do_work()
    finally:
        cache.delete('lock:expensive')
```

**Pitfall:** Not crash-safe — owner dies, lock stuck till timeout. Use Redlock for serious distributed locks.

---

## Common Pitfalls

### 1. Caching User-Specific Data without Vary

```python
# BAD — first user's data served to all
@cache_page(300)
def dashboard(request):
    return JsonResponse({'name': request.user.username})

# GOOD
@cache_page(300)
@vary_on_cookie
def dashboard(request):
    ...
```

### 2. Stale Data after Mutations

Cache doesn't auto-invalidate. Use signals:

```python
from django.db.models.signals import post_save
from django.dispatch import receiver

@receiver(post_save, sender=Article)
def invalidate_article_cache(sender, instance, **kwargs):
    cache.delete(f'article:{instance.pk}')
    cache.delete('top_articles:v1')  # if affects list
```

### 3. Cache Stampede (Dogpile)

100 requests hit empty cache simultaneously → 100 DB queries:

```python
# Solution 1: cache.add()-based lock
def get_top_articles():
    key = 'top_articles'
    val = cache.get(key)
    if val is not None:
        return val
    lock_key = f'{key}:lock'
    if cache.add(lock_key, '1', timeout=30):
        try:
            val = expensive_computation()
            cache.set(key, val, timeout=3600)
        finally:
            cache.delete(lock_key)
    else:
        # Brief wait + retry
        time.sleep(0.5)
        val = cache.get(key) or expensive_computation()
    return val
```

### 4. Pickle Security

Django Redis cache uses pickle by default — only cache trusted data. Untrusted input + pickle = RCE.

### 5. Cache Backend Doesn't Support `incr()`

`LocMemCache` is fine. Memcached: yes. Redis (`django-redis`): yes. DatabaseCache: not atomic.

### 6. `cache_page` Breaks for Authenticated Users

`Vary: Cookie` is auto-added, but per-user keys explode in cache. For per-user data, use template fragment cache or low-level API, not `cache_page`.

---

## Interview Q&A

**Q1:** Django caching ke kitne layers hain?
**A:** 5 layers — per-site middleware, per-view (`@cache_page`), template fragment (`{% cache %}`), low-level (`cache.set/get`), conditional view (ETag/Last-Modified). Choose based on granularity needed.

**Q2:** Cache stampede kya hai aur kaise prevent karte ho?
**A:** Empty cache + concurrent requests → all hit DB simultaneously. Prevention: (1) `cache.add()` lock for single-flight computation, (2) probabilistic early expiry (recompute before TTL), (3) Redis Lua scripts for atomic check-or-compute.

**Q3:** ETag vs Last-Modified — kab kya?
**A:** Last-Modified = timestamp-based, simpler, second-level precision. ETag = content hash, exact, can detect any change. ETag is more reliable; Last-Modified is cheaper to compute. Both can coexist — Django checks both.

**Q4:** `@vary_on_cookie` ka effect kya hai?
**A:** Adds `Vary: Cookie` header → cache key includes cookie value → per-user caching. Tradeoff: cache hit rate drops since each user has unique cookie. For auth views, prefer low-level cache with explicit user-keyed keys.

**Q5:** Cache invalidation strategies?
**A:** (1) Time-based TTL (simplest, allows stale data), (2) Event-based via signals (precise, but signals brittle), (3) Version bumping (`cache.set(key, val, version=2)`) for bulk invalidation, (4) Tag-based (custom; not built-in — use `django-cache-machine` or Redis sets).

**Q6:** Production mein cache backend Redis hi kyun?
**A:** Redis = atomic ops (`incr`, `add`, Lua scripts), persistence (AOF), pub/sub, data structures (sets, hashes, sorted sets), HA via Sentinel/Cluster. Memcached is simpler but pure-volatile, no pub/sub, no data structures.

**Q7:** Per-site cache middleware kab use karoge?
**A:** Mostly static, mostly anonymous-user sites — blog, marketing pages. Add `UpdateCacheMiddleware` + `FetchFromCacheMiddleware` to MIDDLEWARE. Skip for personalized sites — cache miss for every authenticated user.

**Q8:** `cache.add()` vs `cache.set()`?
**A:** `set` always writes. `add` writes only if key doesn't exist — atomic compare-and-swap. Used for lightweight distributed locks: `cache.add('lock', 'owner', 60)` → True if acquired, False if locked.

---

## Real-World Use Cases

### 1. Expensive Aggregation Cache

```python
def revenue_dashboard():
    return cache.get_or_set(
        'revenue:today',
        lambda: Order.objects.paid().today().aggregate(Sum('amount'))['amount__sum'],
        timeout=300,  # 5 min freshness OK
    )
```

### 2. Per-User Throttle Counter

```python
def rate_limit(user_id, action, limit=10, window=60):
    key = f'rl:{action}:{user_id}'
    count = cache.get(key, 0)
    if count >= limit:
        return False
    pipe = cache.client.get_client().pipeline()
    pipe.incr(key)
    pipe.expire(key, window)
    pipe.execute()
    return True
```

### 3. Conditional API Response (Saves Bandwidth)

```python
@etag(lambda r, pk: User.objects.values('updated_at').get(pk=pk)['updated_at'].isoformat())
def user_profile(request, pk):
    user = get_object_or_404(User, pk=pk)
    return JsonResponse({'id': user.id, 'name': user.username})
```

---

## References

- [Django caching docs](https://docs.djangoproject.com/en/5.0/topics/cache/)
- [django-redis package](https://github.com/jazzband/django-redis)
- [Conditional view processing](https://docs.djangoproject.com/en/5.0/topics/conditional-view-processing/)
- Eugene Yan — "Cache Patterns" blog
