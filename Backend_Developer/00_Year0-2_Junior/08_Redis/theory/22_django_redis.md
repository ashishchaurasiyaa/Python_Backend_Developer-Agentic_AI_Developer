# Redis + Django — Complete Guide

## 1. Setup

```bash
pip install django-redis redis
```

```python
# settings.py
CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": "redis://127.0.0.1:6379/1",
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
            "CONNECTION_POOL_KWARGS": {"max_connections": 50},
            "SOCKET_CONNECT_TIMEOUT": 5,
            "SOCKET_TIMEOUT": 5,
            "IGNORE_EXCEPTIONS": True,   # degrade gracefully if Redis down
        },
        "KEY_PREFIX": "myapp",          # prevents key collisions between envs
        "TIMEOUT": 300,                 # default TTL in seconds (None = no expiry)
    }
}
```

---

## 2. Low-Level Cache API

```python
from django.core.cache import cache

# SET — stores any picklable Python object
cache.set("user:42:profile", {"name": "Alice", "role": "admin"}, timeout=3600)

# GET — returns None on miss
profile = cache.get("user:42:profile")
if profile is None:
    profile = User.objects.get(pk=42).to_dict()
    cache.set("user:42:profile", profile, timeout=3600)

# GET_OR_SET — atomic: fetch from DB only on miss
def get_profile():
    return User.objects.get(pk=42).to_dict()

profile = cache.get_or_set("user:42:profile", get_profile, timeout=3600)

# DELETE
cache.delete("user:42:profile")

# DELETE MANY
cache.delete_many(["user:42:profile", "user:43:profile"])

# EXISTS
if cache.has_key("user:42:profile"):
    ...

# INCR / DECR (atomic)
cache.set("page_views:home", 0)
cache.incr("page_views:home")
cache.decr("page_views:home")

# SET MANY
cache.set_many({
    "user:42:profile": profile_42,
    "user:43:profile": profile_43,
}, timeout=3600)

# GET MANY
results = cache.get_many(["user:42:profile", "user:43:profile"])
# returns dict: {"user:42:profile": ..., "user:43:profile": ...}
```

---

## 3. View-Level Caching — @cache_page

Caches the entire HTTP response (HTML or JSON) for a given URL.

```python
from django.views.decorators.cache import cache_page
from django.utils.decorators import method_decorator

# Function-based view
@cache_page(60 * 15)   # cache for 15 minutes
def product_list(request):
    products = Product.objects.all()
    return JsonResponse({"products": list(products.values())})

# Class-based view
@method_decorator(cache_page(60 * 15), name='dispatch')
class ProductListView(View):
    def get(self, request):
        ...

# DRF ViewSet — cache list action
from rest_framework.decorators import action
class ProductViewSet(viewsets.ModelViewSet):
    @method_decorator(cache_page(60 * 15))
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)
```

**Important:** `@cache_page` caches per URL. Query params create different cache entries. POST requests are NOT cached.

---

## 4. Template Fragment Caching

```html
{% load cache %}

{% cache 300 sidebar_menu %}
    <!-- This block is cached for 5 minutes -->
    <nav>
        {% for item in menu_items %}
            <a href="{{ item.url }}">{{ item.name }}</a>
        {% endfor %}
    </nav>
{% endcache %}

<!-- Cache per-user (vary by user id) -->
{% cache 300 user_dashboard request.user.id %}
    <div>Welcome, {{ request.user.username }}</div>
{% endcache %}
```

---

## 5. Session Storage in Redis

Redis-backed sessions survive process restarts and work across multiple app servers.

```python
# settings.py
SESSION_ENGINE = "django.contrib.sessions.backends.cache"
SESSION_CACHE_ALIAS = "default"   # uses the Redis CACHES["default"]

# Optional: separate Redis DB for sessions
CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": "redis://127.0.0.1:6379/1",   # DB 1 = app cache
    },
    "sessions": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": "redis://127.0.0.1:6379/2",   # DB 2 = sessions
    }
}
SESSION_CACHE_ALIAS = "sessions"
```

In views:
```python
def login_view(request):
    request.session["user_id"] = 42
    request.session["role"] = "admin"
    # Django stores this in Redis automatically

def logout_view(request):
    request.session.flush()   # delete session from Redis
```

---

## 6. Cache Invalidation Patterns in Django

### Pattern 1: Delete on write

```python
def update_product(product_id: int, data: dict):
    product = Product.objects.get(pk=product_id)
    for key, value in data.items():
        setattr(product, key, value)
    product.save()
    # Invalidate all related cache keys
    cache.delete(f"product:{product_id}")
    cache.delete("product_list")
```

### Pattern 2: Django signals for automatic invalidation

```python
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

@receiver(post_save, sender=Product)
def invalidate_product_cache(sender, instance, **kwargs):
    cache.delete(f"product:{instance.pk}")
    cache.delete("product_list")

@receiver(post_delete, sender=Product)
def invalidate_product_cache_on_delete(sender, instance, **kwargs):
    cache.delete(f"product:{instance.pk}")
    cache.delete("product_list")
```

### Pattern 3: Versioned cache keys

```python
def get_product_cache_key(product_id: int) -> str:
    version = cache.get(f"product:{product_id}:version", 1)
    return f"product:{product_id}:v{version}"

def invalidate_product(product_id: int):
    # Increment version — old cached values become unreachable
    cache.incr(f"product:{product_id}:version")
    # Old key "product:42:v1" still in Redis but no one accesses it → expires naturally
```

---

## 7. Redis as Celery Broker + Result Backend

```python
# settings.py
CELERY_BROKER_URL        = "redis://localhost:6379/0"   # tasks go here
CELERY_RESULT_BACKEND    = "redis://localhost:6379/0"   # results stored here
CELERY_TASK_SERIALIZER   = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_ACCEPT_CONTENT    = ["json"]
CELERY_TASK_TRACK_STARTED = True
CELERY_RESULT_EXPIRES    = 3600   # results expire after 1 hour
```

```python
# tasks.py
from celery import shared_task
from django.core.cache import cache

@shared_task
def process_order(order_id: int):
    order = Order.objects.get(pk=order_id)
    # ... process ...
    # Invalidate order cache after processing
    cache.delete(f"order:{order_id}")
    return {"status": "processed", "order_id": order_id}

# views.py — enqueue a task
result = process_order.delay(order_id=42)
task_id = result.id

# Check status later
from celery.result import AsyncResult
task = AsyncResult(task_id)
print(task.status)   # PENDING / STARTED / SUCCESS / FAILURE
print(task.result)   # return value after SUCCESS
```

**Redis DB separation (recommended):**
```
Redis DB 0 → Celery broker (task queue)
Redis DB 1 → Django app cache
Redis DB 2 → Session storage
```

---

## 8. Rate Limiting with Django + Redis

```python
from django.core.cache import cache
from django.http import JsonResponse
import time

def rate_limit(key: str, limit: int, window: int):
    """Fixed window rate limiter. Returns True if allowed."""
    window_key = int(time.time() // window)
    full_key = f"ratelimit:{key}:{window_key}"
    count = cache.get(full_key, 0)
    if count >= limit:
        return False
    cache.set(full_key, count + 1, timeout=window)
    return True

# Middleware usage
class RateLimitMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        ip = request.META.get("REMOTE_ADDR")
        if not rate_limit(f"ip:{ip}", limit=100, window=60):
            return JsonResponse({"detail": "Rate limit exceeded"}, status=429)
        return self.get_response(request)
```

---

## 9. Direct Redis Client Access (django-redis)

```python
from django_redis import get_redis_connection

r = get_redis_connection("default")

# Use native Redis commands (not available via Django cache API)
r.zadd("leaderboard", {"user:42": 1500, "user:99": 2300})
top_players = r.zrevrange("leaderboard", 0, 9, withscores=True)

# Pipeline for batch ops
pipe = r.pipeline()
for user_id in user_ids:
    pipe.get(f"user:{user_id}:score")
scores = pipe.execute()
```

---

## 10. Production Settings

```python
# settings.py — production Redis config
CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": [
            "redis://replica1:6379/1",
            "redis://replica2:6379/1",
        ],   # read from replicas
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.HerdClient",   # stampede prevention
            "CONNECTION_POOL_KWARGS": {
                "max_connections": 100,
                "retry_on_timeout": True,
            },
            "SOCKET_CONNECT_TIMEOUT": 2,
            "SOCKET_TIMEOUT": 2,
            "IGNORE_EXCEPTIONS": True,  # return None on Redis failure (graceful degrade)
            "COMPRESSOR": "django_redis.compressors.zlib.ZlibCompressor",  # compress large values
        },
        "KEY_PREFIX": "prod",
        "TIMEOUT": 300,
    }
}
```

---

## 11. Interview Questions

**Q: Django mein Redis cache kaise configure karte hain?**
`CACHES` setting mein `django_redis.cache.RedisCache` backend set karo. `LOCATION` mein Redis URL, `TIMEOUT` mein default TTL.

**Q: `@cache_page` kab use karo aur kab low-level `cache.set()` use karo?**
`@cache_page` = full HTTP response cache (public pages, no user-specific data). `cache.set()` = fine-grained control, user-specific data, partial caching.

**Q: Django sessions Redis mein kyu store karte hain?**
Multiple app servers ke beech shared state. Process restart survive karta hai. DB-based sessions slow hoti hain; cookie-based sessions large aur insecure ho sakte hain.

**Q: Celery broker aur result backend mein kya fark hai?**
Broker = task queue (Redis pe LPUSH/BRPOP). Result backend = task ka return value store karta hai (Redis pe SET). Dono alag Redis DBs mein rakhna achha practice hai.

**Q: Django mein cache invalidation kaise karte ho?**
`cache.delete(key)` on write. Ya signals use karo (`post_save`). Ya versioned keys — version increment karo, purana key stale ho jaata hai naturally.
