# Django Async ORM & Views — Django 4/5

## Why It Matters (Senior 5 YOE Context)

Django historically synchronous. Django 4+ introduced async views, Django 5 added async ORM. Why important:

- **External API calls** in views — async lets you `await httpx.get(...)` without blocking
- **Multiple parallel queries** — `asyncio.gather(query1, query2)` faster than serial
- **WebSocket compatibility** — Channels needs async-friendly code
- **AI/LLM workflows** — long-running LLM calls + DB writes from same view

But: ORM + middleware + signals + auth = lots of sync-only code. Bridging requires care.

Senior interview: "Should we rewrite our Django app async?" → Almost always **no**, but use async for specific endpoints making external calls.

---

## Core Concepts

### Async Views (Django 4+)

```python
import asyncio
from django.http import JsonResponse


async def async_view(request):
    # await whatever async work
    await asyncio.sleep(0.1)
    return JsonResponse({'status': 'ok'})


# Class-based async view
from django.views import View


class AsyncView(View):
    async def get(self, request):
        return JsonResponse({'data': await fetch_data()})
```

### Async ORM (Django 4.1+ basics, Django 5+ much improved)

```python
# Async equivalents of ORM methods — prefix 'a'
from blog.models import Article


async def get_article(pk):
    return await Article.objects.aget(pk=pk)


async def list_articles():
    articles = []
    async for article in Article.objects.filter(status='published'):
        articles.append({'id': article.pk, 'title': article.title})
    return articles


async def create_article(title, author_id):
    return await Article.objects.acreate(title=title, author_id=author_id)


async def update_articles():
    return await Article.objects.filter(status='draft').aupdate(status='published')


async def count_articles():
    return await Article.objects.filter(status='published').acount()


async def filter_async():
    qs = Article.objects.filter(status='published')
    first = await qs.afirst()
    all_articles = [a async for a in qs]
    exists = await qs.aexists()
```

### Async-Compatible Methods Available

| Sync | Async |
|---|---|
| `.get()` | `.aget()` |
| `.create()` | `.acreate()` |
| `.update()` | `.aupdate()` |
| `.delete()` | `.adelete()` |
| `.first()` | `.afirst()` |
| `.last()` | `.alast()` |
| `.count()` | `.acount()` |
| `.exists()` | `.aexists()` |
| `.get_or_create()` | `.aget_or_create()` |
| `.update_or_create()` | `.aupdate_or_create()` |
| `.bulk_create()` | `.abulk_create()` |
| `.bulk_update()` | `.abulk_update()` |
| `.in_bulk()` | `.ain_bulk()` |
| `.contains()` | `.acontains()` |
| Iteration | `async for` |

### Parallel Queries (the big win)

```python
async def dashboard(request):
    # Without async: ~300ms serial
    # With async: ~100ms (limited by slowest)
    articles, comments, users_count = await asyncio.gather(
        sync_to_async_query_or_just_async(),
        Comment.objects.filter(recent=True).acount(),
        User.objects.acount(),
    )
    return JsonResponse({'articles': articles, 'comments': comments, 'users': users_count})
```

### `sync_to_async` and `async_to_sync` Adapters

```python
from asgiref.sync import sync_to_async, async_to_sync


# Wrap sync function for use in async view
async def my_async_view(request):
    # Old sync code
    result = await sync_to_async(legacy_sync_function)(arg1, arg2)
    # Thread-safe: pass thread_sensitive=False for parallelism
    result = await sync_to_async(some_func, thread_sensitive=False)()
    return JsonResponse({'data': result})


# Call async from sync context (rarely needed)
def sync_view(request):
    result = async_to_sync(async_function)()
    return JsonResponse({'data': result})
```

### Async Middleware

```python
import asyncio


class AsyncTimingMiddleware:
    """Capability-detect: works both sync and async."""

    sync_capable = True
    async_capable = True

    def __init__(self, get_response):
        self.get_response = get_response
        # Test if get_response is coroutine
        if asyncio.iscoroutinefunction(get_response):
            self._is_coroutine = asyncio.coroutines._is_coroutine

    def __call__(self, request):
        if asyncio.iscoroutinefunction(self.get_response):
            return self.__acall__(request)
        # Sync path
        response = self.get_response(request)
        return response

    async def __acall__(self, request):
        response = await self.get_response(request)
        return response
```

### Async with Transactions (Django 5+)

```python
from django.db import transaction


async def transactional_async_view(request):
    @sync_to_async
    def do_work():
        with transaction.atomic():
            order = Order.objects.create(...)
            Payment.objects.create(order=order)

    await do_work()
    return JsonResponse({'ok': True})


# Django 5.1+: native async transaction support
async def native_async_txn():
    async with transaction.atomic():       # Django 5.1+
        order = await Order.objects.acreate(...)
        await Payment.objects.acreate(order=order)
```

### Async External API + ORM Pattern

```python
import httpx
from django.utils import timezone


async def enrich_user(request, user_id):
    # Parallel external call + DB
    user_task = User.objects.aget(pk=user_id)
    async with httpx.AsyncClient() as client:
        external_task = client.get(f'https://api.example.com/users/{user_id}')
        user, external_response = await asyncio.gather(user_task, external_task)

    external_data = external_response.json()

    # Update user with external data
    user.external_data = external_data
    user.synced_at = timezone.now()
    await user.asave()

    return JsonResponse({'user_id': user.pk, 'synced': True})
```

---

## How It Works Internally

### `ASGI_APPLICATION`

For async views, you need ASGI (not WSGI):

```python
# asgi.py
import os
from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
application = get_asgi_application()


# Serve with daphne/uvicorn
# daphne -b 0.0.0.0 -p 8000 config.asgi:application
# uvicorn config.asgi:application --host 0.0.0.0 --port 8000
```

### Database Connections in Async

Django wraps each query in `sync_to_async` internally (Django 4) or uses dedicated async cursor (Django 5+ pending). DB driver itself isn't async — Django uses thread pool.

**Postgres-specific:** `psycopg3` has async support (Django 5+ leverages this).

### Async + Signals

Django signals are sync by default. Pre/post save handlers fire synchronously in async views via `sync_to_async`. Avoid heavy work in signals when using async views.

---

## Common Pitfalls

### 1. Calling Sync ORM from Async Without `sync_to_async`

```python
# WRONG — raises SynchronousOnlyOperation
async def view(request):
    user = User.objects.get(pk=1)

# RIGHT
async def view(request):
    user = await User.objects.aget(pk=1)
```

### 2. Async View But Sync Middleware Blocks

If middleware is sync-only, Django downgrades the async view to sync via `async_to_sync`. Performance lost.

### 3. Database Pool Exhaustion

Async = more concurrent DB connections. With Postgres + 100 async workers + 5 queries each = 500 connections. Use pgBouncer.

### 4. `select_related` in Async Iteration

```python
# OK
async for a in Article.objects.select_related('author'):
    print(a.author.username)
```

`select_related` works fine. But `prefetch_related` requires `apreload()` or sync wrapper currently.

### 5. Thread-Sensitive Issues

Default `sync_to_async(func, thread_sensitive=True)` ensures DB connection thread-safety. Setting `thread_sensitive=False` parallelizes but breaks transactions.

### 6. Mix of Async View + Sync Decorators

```python
# Some decorators don't support async
@cache_page(60)  # sync only — wraps async into sync
async def my_view(request): ...
```

Check decorator docs; many decorators got async support in Django 4.1+.

---

## Interview Q&A

**Q1:** Django async views ka kya benefit hai?
**A:** Sirf when you do I/O-bound work — external API calls, file I/O, multiple parallel DB queries. CPU-bound work mein no benefit. Best use: views that hit slow external APIs + DB.

**Q2:** Sync code async view mein kaise use karoge?
**A:** Wrap with `sync_to_async()` from `asgiref.sync`. `thread_sensitive=True` (default) for DB code; `False` for CPU/IO with no DB. Or upgrade to async-native ORM methods (`aget`, `acreate`).

**Q3:** Async ORM Django mein production-ready hai?
**A:** Django 4.1+ basic async ORM available. Django 5+ extended (most methods). Production: yes for simple queries, watch for `prefetch_related` and complex aggregations. Run load tests before adopting.

**Q4:** Async views serve karne ke liye kya setup chahiye?
**A:** ASGI server (daphne, uvicorn, hypercorn) instead of gunicorn (WSGI). Configure `asgi.py`. Middleware must be async-capable (most Django built-ins are; check 3rd-party). Behind nginx, configure `proxy_http_version 1.1`.

**Q5:** Async + transaction kaise handle karte ho?
**A:** Django 5.1+ supports `async with transaction.atomic()`. Before that: wrap sync transaction in `sync_to_async`. For complex flows: do all writes in one sync_to_async block to keep DB connection consistent.

**Q6:** sync_to_async ka `thread_sensitive` flag explain karo.
**A:** `True` = all sync_to_async calls in a request share a single thread (for DB connection thread-affinity). `False` = each call gets a free thread, allowing parallelism but breaking transactions/connection sharing. Use False only for stateless work (CPU-bound, no DB).

**Q7:** Async view se Celery task call kar sakte ho?
**A:** Yes — `task.delay()` is sync but non-blocking (just queues). Wrap in `sync_to_async` if you want to await it cleanly. For result, use `task.delay().get()` is bad (blocks); poll Redis result backend or use webhook.

**Q8:** Channels vs async views — kya difference?
**A:** Channels = full async framework for WebSocket/long-lived connections, has consumer model + routing. Async views = single HTTP request handlers. Use Channels for WS/SSE/long-poll; async views for HTTP that needs concurrent I/O.

---

## Real-World Use Cases

### 1. AI Chat Endpoint

```python
async def chat(request):
    user_msg = request.POST['message']
    user_id = request.user.id

    # Parallel: log message + call LLM
    log_task = ChatLog.objects.acreate(user_id=user_id, message=user_msg)

    async with httpx.AsyncClient() as c:
        llm_task = c.post('https://api.anthropic.com/v1/messages', json={...})
        _, llm_response = await asyncio.gather(log_task, llm_task)

    reply = llm_response.json()['content'][0]['text']
    await ChatLog.objects.acreate(user_id=user_id, message=reply, is_bot=True)

    return JsonResponse({'reply': reply})
```

### 2. Dashboard Aggregations

```python
async def dashboard(request):
    revenue, orders_count, top_products = await asyncio.gather(
        Order.objects.filter(status='paid').aaggregate(total=Sum('amount')),
        Order.objects.acount(),
        sync_to_async(get_top_products)(),
    )
    return JsonResponse({...})
```

### 3. Webhook Forwarder

```python
async def forward_webhook(request):
    event = json.loads(request.body)
    # Forward to 3 downstream services in parallel
    async with httpx.AsyncClient() as c:
        results = await asyncio.gather(
            c.post('https://svc1.example.com/webhook', json=event),
            c.post('https://svc2.example.com/webhook', json=event),
            c.post('https://svc3.example.com/webhook', json=event),
            return_exceptions=True,
        )
    return JsonResponse({'sent_to': len([r for r in results if not isinstance(r, Exception)])})
```

---

## References

- [Django async docs](https://docs.djangoproject.com/en/5.0/topics/async/)
- [Django ORM async](https://docs.djangoproject.com/en/5.0/topics/db/queries/#async-queries)
- [asgiref docs](https://github.com/django/asgiref)
- Andrew Godwin's talks on Django async
