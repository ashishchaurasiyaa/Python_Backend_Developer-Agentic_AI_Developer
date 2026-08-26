"""
Lab 12 — Async Django Views + sync_to_async + WSGI vs ASGI
═══════════════════════════════════════════════════════════════════════════════

ARCHITECTURE — Django's Async Support:

    WSGI (traditional):
        Nginx → Gunicorn (worker processes) → Django (sync)
        Each request blocks a worker thread until done.
        Concurrency = number of workers (typically CPU * 2 + 1)
        ✅ Simple, battle-tested
        ❌ Blocking I/O wastes worker time (waiting for DB, external APIs)

    ASGI (modern):
        Nginx → Uvicorn/Hypercorn (async event loop) → Django
        One event loop handles thousands of concurrent connections.
        While waiting for DB/API, loop serves other requests.
        ✅ High I/O concurrency
        ✅ WebSocket support (Django Channels)
        ❌ Blocking code (time.sleep, sync ORM) FREEZES the event loop

    DJANGO ASYNC VIEW:
        async def my_view(request):
            data = await some_async_operation()
            return JsonResponse(data)

        Django runs async views in the event loop (via ASGI).
        Django runs async views in a thread (via WSGI) — no real benefit.

    SYNC → ASYNC BOUNDARY (the critical skill):
        Django ORM is SYNCHRONOUS. In async views, you CANNOT call it directly.
        Calling ORM synchronously inside an async context raises:
            SynchronousOnlyOperation: You cannot call this from an async context

        Solution: sync_to_async()
            from asgiref.sync import sync_to_async

            # Wrap a sync function
            get_posts = sync_to_async(Post.objects.filter(status='published').get)

            # Or use as decorator
            @sync_to_async
            def get_featured_posts():
                return list(Post.objects.filter(is_featured=True).select_related('author'))

    ASYNC → SYNC BOUNDARY:
        In sync code calling async functions: async_to_sync()
            from asgiref.sync import async_to_sync
            result = async_to_sync(some_async_func)()

    PARALLEL I/O with asyncio.gather:
        async def enrich_post(post_id):
            # Call 3 services concurrently (not sequentially!)
            post_data, author_stats, similar_posts = await asyncio.gather(
                fetch_post(post_id),
                fetch_author_stats(post_id),
                fetch_similar_posts(post_id),
            )

        Without gather: 3 sequential API calls = 3 * latency
        With gather:    3 concurrent API calls = max(latency) + overhead

CONTEXT:
  Blog API needs to:
  1. Async view: list posts using sync_to_async wrapper
  2. Async external API: parallel calls to fetch post metadata from 3 services

RUN:
    cd practical/
    pytest labs/lab_12_async_views_sync_boundary.py -v -p no:odoo

SOCH — Answer ALOUD:
  Q1: Async view mein sync ORM seedha call karne se kya hota hai?
  Q2: sync_to_async ka thread_sensitive parameter kya karta hai?
  Q3: asyncio.gather vs sequential await — kab kaunsa? Performance difference?
  Q4: WSGI server pe async view run karo — kya hoga? Benefit milta hai?
  Q5: Django 4.1+ async ORM: Post.objects.aget(), afilter() — sync_to_async ki zaroorat kab nahi?
"""

import asyncio
import pytest
import time
from unittest.mock import AsyncMock, patch, MagicMock

from django.http import JsonResponse
from django.test import RequestFactory, AsyncRequestFactory, override_settings
from asgiref.sync import sync_to_async, async_to_sync

import factory
from factory.django import DjangoModelFactory
from django.contrib.auth import get_user_model
from django.utils import timezone

from blog.models import Post, Category

User = get_user_model()


# ════════════════════════════════════════════════════════════════════════════
# FACTORIES
# ════════════════════════════════════════════════════════════════════════════

class L12UserFactory(DjangoModelFactory):
    class Meta:
        model = User
    email    = factory.Sequence(lambda n: f"l12user{n}@test.com")
    username = factory.Sequence(lambda n: f"l12user{n}")
    password = factory.PostGenerationMethodCall('set_password', 'pass123')

class L12CategoryFactory(DjangoModelFactory):
    class Meta:
        model = Category
    name = factory.Sequence(lambda n: f"L12Cat{n}")

class L12PostFactory(DjangoModelFactory):
    class Meta:
        model = Post
    title        = factory.Sequence(lambda n: f"L12 Post {n}")
    content      = "Content word " * 60
    excerpt      = "Excerpt."
    author       = factory.SubFactory(L12UserFactory)
    category     = factory.SubFactory(L12CategoryFactory)
    status       = 'published'
    published_at = factory.LazyFunction(timezone.now)


# ════════════════════════════════════════════════════════════════════════════
# TODO 1 — async_get_posts() — sync ORM wrapped in sync_to_async
# ════════════════════════════════════════════════════════════════════════════
"""
Implement async_get_posts(n: int = 10) -> list[dict]:

  The ORM call is SYNCHRONOUS. We must wrap it:

  @sync_to_async
  def _fetch_posts(n):
      return list(
          Post.objects.filter(status='published')
                      .select_related('author')
                      .order_by('-published_at')[:n]
      )

  async def async_get_posts(n: int = 10) -> list[dict]:
      posts = await _fetch_posts(n)
      return [
          {'id': p.id, 'title': p.title, 'author': p.author.email}
          for p in posts
      ]

Why list() inside sync_to_async?
  QuerySets are lazy — evaluated when iterated.
  Iterating outside the sync_to_async context = SynchronousOnlyOperation.
  Always evaluate (list/values_list) INSIDE the wrapped function.
"""

@sync_to_async
def _fetch_posts_sync(n: int):
    raise NotImplementedError(
        "TODO 1a: list(Post.objects.filter(status='published').select_related('author')[:n])"
    )

async def async_get_posts(n: int = 10) -> list:
    raise NotImplementedError(
        "TODO 1b: await _fetch_posts_sync(n), return list of dicts"
    )


# ════════════════════════════════════════════════════════════════════════════
# TODO 2 — async_post_list_view — async Django view
# ════════════════════════════════════════════════════════════════════════════
"""
Implement async def async_post_list_view(request) → JsonResponse:

  1. posts = await async_get_posts(n=10)
  2. return JsonResponse({'posts': posts, 'count': len(posts)})

Django recognizes async views automatically when the view function is
defined with `async def`. No special decorator needed.
"""

async def async_post_list_view(request):
    raise NotImplementedError(
        "TODO 2: await async_get_posts(), return JsonResponse({'posts': ..., 'count': ...})"
    )


# ════════════════════════════════════════════════════════════════════════════
# TODO 3 — fetch_external_metadata() — simulate parallel async API calls
# ════════════════════════════════════════════════════════════════════════════
"""
Implement async def fetch_external_metadata(post_id: int) -> dict:

  Simulates calling 3 external services for a single post:
    - fetch_view_count(post_id)  ← analytics service (0.1s)
    - fetch_share_count(post_id) ← social service (0.1s)
    - fetch_related_ids(post_id) ← recommendation engine (0.1s)

  SEQUENTIAL (wrong — 0.3s total):
    views  = await fetch_view_count(post_id)
    shares = await fetch_share_count(post_id)
    related = await fetch_related_ids(post_id)

  PARALLEL (correct — 0.1s total):
    views, shares, related = await asyncio.gather(
        fetch_view_count(post_id),
        fetch_share_count(post_id),
        fetch_related_ids(post_id),
    )

  Return: {'post_id': post_id, 'views': views, 'shares': shares, 'related': related}
"""

async def _mock_fetch_view_count(post_id: int) -> int:
    await asyncio.sleep(0.05)   # simulate network I/O
    return post_id * 100

async def _mock_fetch_share_count(post_id: int) -> int:
    await asyncio.sleep(0.05)
    return post_id * 10

async def _mock_fetch_related_ids(post_id: int) -> list:
    await asyncio.sleep(0.05)
    return [post_id + 1, post_id + 2]

async def fetch_external_metadata(post_id: int) -> dict:
    raise NotImplementedError(
        "TODO 3: Use asyncio.gather() to call all 3 mock functions concurrently"
    )


# ════════════════════════════════════════════════════════════════════════════
# TODO 4 — async_post_detail_view — async view with gather
# ════════════════════════════════════════════════════════════════════════════
"""
Implement async def async_post_detail_view(request, post_id: int) -> JsonResponse:

  1. Get post from DB: use sync_to_async to wrap ORM
     post_data = await sync_to_async(
         lambda: Post.objects.select_related('author').get(id=post_id)
     )()

  2. Get external metadata concurrently (it's already async):
     metadata = await fetch_external_metadata(post_id)

  3. Combine and return:
     return JsonResponse({
         'id': post_data.id,
         'title': post_data.title,
         'author': post_data.author.email,
         **metadata
     })

  Handle Post.DoesNotExist → return JsonResponse({'error': 'Not found'}, status=404)
"""

async def async_post_detail_view(request, post_id: int):
    raise NotImplementedError(
        "TODO 4: Fetch post from DB (sync_to_async) + fetch_external_metadata concurrently"
    )


# ════════════════════════════════════════════════════════════════════════════
# DEMO — Blocking code freezes async (educational, not a TODO)
# ════════════════════════════════════════════════════════════════════════════

async def _good_async_task(name: str, delay: float) -> str:
    """Non-blocking — yields to event loop."""
    await asyncio.sleep(delay)
    return f"{name}: done"

async def _bad_blocking_task(name: str, delay: float) -> str:
    """BLOCKING — freezes event loop for `delay` seconds."""
    time.sleep(delay)   # time.sleep is SYNCHRONOUS — blocks everything!
    return f"{name}: done (but blocked loop)"

async def demo_blocking_vs_nonblocking():
    """Show the difference between blocking and non-blocking in async."""
    # Concurrent async tasks — all run in parallel
    start = time.perf_counter()
    results = await asyncio.gather(
        _good_async_task("A", 0.1),
        _good_async_task("B", 0.1),
        _good_async_task("C", 0.1),
    )
    async_time = time.perf_counter() - start

    # Sequential blocking calls — each blocks the loop
    start = time.perf_counter()
    r1 = await _bad_blocking_task("A", 0.1)
    r2 = await _bad_blocking_task("B", 0.1)
    r3 = await _bad_blocking_task("C", 0.1)
    blocking_time = time.perf_counter() - start

    return {
        'async_time':    round(async_time * 1000),   # ~100ms
        'blocking_time': round(blocking_time * 1000), # ~300ms
    }


# ════════════════════════════════════════════════════════════════════════════
# TESTS
# ════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
def test_async_get_posts_returns_list():
    """async_get_posts wraps ORM in sync_to_async — must return list of dicts."""
    L12PostFactory(title="Async Post A")
    L12PostFactory(title="Async Post B")

    result = asyncio.run(async_get_posts(n=10))

    assert isinstance(result, list), "FAIL: Should return a list"
    assert len(result) >= 2, f"FAIL: Expected >= 2 posts. Got {len(result)}"
    assert 'title' in result[0], "FAIL: Each item should have 'title'"
    assert 'author' in result[0], "FAIL: Each item should have 'author'"


@pytest.mark.django_db
def test_async_get_posts_respects_n():
    """async_get_posts(n=2) should return max 2 items."""
    for _ in range(5):
        L12PostFactory()

    result = asyncio.run(async_get_posts(n=2))
    assert len(result) == 2, f"FAIL: n=2 should return exactly 2 posts. Got {len(result)}"


@pytest.mark.django_db
def test_async_post_list_view_returns_200():
    """async_post_list_view should return 200 with posts key."""
    L12PostFactory(title="View Test Post")

    factory = RequestFactory()
    request = factory.get('/posts/')

    response = asyncio.run(async_post_list_view(request))

    assert response.status_code == 200, f"FAIL: Expected 200. Got {response.status_code}"

    import json
    body = json.loads(response.content)
    assert 'posts' in body, f"FAIL: Response should have 'posts' key. Got: {list(body.keys())}"
    assert 'count' in body, f"FAIL: Response should have 'count' key"
    assert body['count'] >= 1, "FAIL: At least 1 post should be in response"


def test_fetch_external_metadata_uses_gather():
    """
    Parallel gather should complete in ~max(latency), not sum(latency).
    Each mock service takes 0.05s → parallel = ~0.05s, sequential = ~0.15s
    """
    start  = time.perf_counter()
    result = asyncio.run(fetch_external_metadata(post_id=42))
    elapsed = time.perf_counter() - start

    assert 'views' in result,   f"FAIL: 'views' missing from result: {result}"
    assert 'shares' in result,  f"FAIL: 'shares' missing from result: {result}"
    assert 'related' in result, f"FAIL: 'related' missing from result: {result}"
    assert result['post_id'] == 42, "FAIL: post_id should be 42"

    # Parallel: ~0.05s. Sequential: ~0.15s. Allow up to 0.12s as parallel proof.
    assert elapsed < 0.12, (
        f"FAIL: fetch_external_metadata took {elapsed:.3f}s — "
        f"should be ~0.05s with gather(), not ~0.15s sequential. "
        f"Are you using asyncio.gather()?"
    )


def test_fetch_external_metadata_values():
    """Mock service values should be computed correctly."""
    result = asyncio.run(fetch_external_metadata(post_id=5))

    assert result['views'] == 500,     f"FAIL: views should be 5*100=500. Got {result['views']}"
    assert result['shares'] == 50,     f"FAIL: shares should be 5*10=50. Got {result['shares']}"
    assert result['related'] == [6, 7], f"FAIL: related should be [6,7]. Got {result['related']}"


@pytest.mark.django_db
def test_async_post_detail_view_returns_post_data():
    """async_post_detail_view should return combined post + metadata."""
    post = L12PostFactory(title="Detail Async Post")

    factory = RequestFactory()
    request = factory.get(f'/posts/{post.id}/')

    result = asyncio.run(async_post_detail_view(request, post_id=post.id))

    import json
    body = json.loads(result.content)

    assert 'title' in body, f"FAIL: 'title' missing. Got: {body}"
    assert body['title'] == "Detail Async Post", f"FAIL: Wrong title: {body['title']}"
    assert 'views' in body,  "FAIL: 'views' from external metadata missing"
    assert 'shares' in body, "FAIL: 'shares' from external metadata missing"


@pytest.mark.django_db
def test_async_post_detail_view_404_for_missing():
    """Non-existent post_id should return 404."""
    factory = RequestFactory()
    request = factory.get('/posts/99999/')

    result = asyncio.run(async_post_detail_view(request, post_id=99999))
    assert result.status_code == 404, (
        f"FAIL: Non-existent post should return 404. Got {result.status_code}"
    )


def test_blocking_vs_nonblocking_timing():
    """Educational: async gather is ~3x faster than sequential blocking calls."""
    result = asyncio.run(demo_blocking_vs_nonblocking())

    assert result['async_time'] < result['blocking_time'], (
        f"FAIL: Async gather ({result['async_time']}ms) should be faster than "
        f"sequential blocking ({result['blocking_time']}ms)"
    )
    # async ~100ms, blocking ~300ms — ratio should be > 2x
    ratio = result['blocking_time'] / max(result['async_time'], 1)
    assert ratio > 1.5, (
        f"FAIL: Expected ~3x speedup. Got {ratio:.1f}x. "
        f"Async: {result['async_time']}ms, Blocking: {result['blocking_time']}ms"
    )


# ════════════════════════════════════════════════════════════════════════════
# SOCH
# ════════════════════════════════════════════════════════════════════════════

"""
SOCH (Answer ALOUD):

Q1: Async Django view mein Post.objects.filter() seedha call karne se kya error aata hai?
    (django.core.exceptions.SynchronousOnlyOperation: You cannot call this from an async context)
    Kyon? (Django ORM uses DB connections that aren't async-safe)

Q2: sync_to_async(@sync_to_async) decorator aur sync_to_async(callable) call mein fark?
    Both same — decorator form is cleaner for named functions.

Q3: Django 4.1+ mein Post.objects.aget(), afilter(), aall() kya hai?
    (Native async ORM methods — no sync_to_async wrapper needed)
    Kab use karo: Django 4.1+, ASGI server, async view.

Q4: asyncio.gather mein ek task fail ho jaye toh kya?
    (By default: raises exception, cancels all other tasks)
    Fix: gather(return_exceptions=True) → failed tasks return exception object

Q5: WSGI pe async view ka benefit nahi — kyon?
    (WSGI server runs async view in thread via async_to_sync() wrapper.
     No event loop — just a thread per request. No concurrency benefit.
     ASGI (Uvicorn/Hypercorn) chahiye for real async benefit)
"""
