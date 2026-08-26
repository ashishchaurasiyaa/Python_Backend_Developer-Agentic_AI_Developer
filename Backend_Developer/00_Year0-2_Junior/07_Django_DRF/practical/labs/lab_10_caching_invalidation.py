"""
Lab 10 — Django Caching: Cache-Aside, Invalidation, Stampede Protection
═══════════════════════════════════════════════════════════════════════════════

ARCHITECTURE — Cache-Aside Pattern:

    READ flow (Cache-Aside):
        Client → get(key) from cache
                   ├── HIT  → return cached value
                   └── MISS → fetch from DB
                              → set(key, value, timeout=TTL) in cache
                              → return value

    WRITE flow (Write-Through / Invalidation):
        Client → save/update DB
               → cache.delete(key)    ← invalidate stale cache
        (Next read will be a cache MISS → re-populate from DB)

    CACHE STAMPEDE (Thundering Herd):
        Problem:
          Popular item's cache expires.
          100 concurrent requests → all get MISS → all hit DB simultaneously.
          DB gets 100x load spike!

        Solution 1 — Lock (mutex):
          First request gets CACHE_LOCK → fetches DB → sets cache
          Other 99 requests → wait for lock → then read from cache

        Solution 2 — Probabilistic early expiration (PER):
          Before TTL expires, randomly re-populate with increasing probability

        Solution 3 — Background refresh:
          Celery task refreshes cache before TTL

        We implement Solution 1 (simple lock) using Django cache.add():
          cache.add(lock_key, 1, timeout=30)  ← atomic test-and-set
          Returns True if key was added (lock acquired), False if already exists

CONTEXT:
  Blog has a "featured posts" widget shown on every page.
  100k requests/minute. DB getting overloaded.
  Solution: cache featured posts for 5 minutes.

RUN:
    cd practical/
    pytest labs/lab_10_caching_invalidation.py -v -p no:odoo

SOCH — Answer ALOUD:
  Q1: Cache-aside vs write-through vs write-behind — kab kaunsa pattern?
  Q2: TTL (Time-To-Live) choose karne ke criteria kya hain?
  Q3: Cache stampede kya hota hai? Lock-based solution kaise kaam karta hai?
  Q4: Cache invalidation problem kya hai? ("Two hard things in CS...")
  Q5: Redis mein atomic operations (SETNX, SET NX EX) kyon zaroor hain stampede prevention ke liye?
"""

import pytest
import time
from unittest.mock import patch, call, MagicMock

from django.test import override_settings
from django.core.cache import cache
from django.db.models import Q
from django.utils import timezone

import factory
from factory.django import DjangoModelFactory
from django.contrib.auth import get_user_model

from blog.models import Post, Category

User = get_user_model()

# ─── Test cache config — LocMem (in-process, no Redis needed) ──────────────
LOCMEM_CACHE = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "lab-10-test",
    }
}

FEATURED_POSTS_KEY   = "blog:featured_posts"
FEATURED_POSTS_TTL   = 300   # 5 minutes


# ════════════════════════════════════════════════════════════════════════════
# FACTORIES
# ════════════════════════════════════════════════════════════════════════════

class L10UserFactory(DjangoModelFactory):
    class Meta:
        model = User
    email    = factory.Sequence(lambda n: f"l10user{n}@test.com")
    username = factory.Sequence(lambda n: f"l10user{n}")
    password = factory.PostGenerationMethodCall('set_password', 'pass123')

class L10CategoryFactory(DjangoModelFactory):
    class Meta:
        model = Category
    name = factory.Sequence(lambda n: f"L10Cat{n}")

class L10PostFactory(DjangoModelFactory):
    class Meta:
        model = Post
    title        = factory.Sequence(lambda n: f"L10 Post {n}")
    content      = "Content word " * 60
    excerpt      = "Excerpt."
    author       = factory.SubFactory(L10UserFactory)
    category     = factory.SubFactory(L10CategoryFactory)
    status       = 'published'
    is_featured  = False
    published_at = factory.LazyFunction(timezone.now)


# ════════════════════════════════════════════════════════════════════════════
# TODO 1 — get_featured_posts_cached()
# ════════════════════════════════════════════════════════════════════════════
"""
Implement Cache-Aside pattern for featured posts:

  def get_featured_posts_cached(ttl: int = FEATURED_POSTS_TTL) -> list[dict]:

  Steps:
    1. Try cache.get(FEATURED_POSTS_KEY)
    2. If HIT: return cached value
    3. If MISS:
         a. Query DB: Post.objects.filter(is_featured=True, status='published')
                                  .select_related('author')
                                  .order_by('-published_at')[:10]
         b. Serialize to list of dicts (id, title, author_email, published_at)
         c. cache.set(FEATURED_POSTS_KEY, result, timeout=ttl)
         d. Return result

  Why list of dicts (not QuerySet)?
    QuerySets are not serializable — cache requires picklable objects.
    Dicts are picklable and lightweight.
"""

def get_featured_posts_cached(ttl: int = FEATURED_POSTS_TTL) -> list:
    raise NotImplementedError(
        "TODO 1: Implement cache-aside: cache.get → hit/miss → DB fetch → cache.set"
    )


# ════════════════════════════════════════════════════════════════════════════
# TODO 2 — invalidate_featured_cache()
# ════════════════════════════════════════════════════════════════════════════
"""
Invalidate the featured posts cache when a post is saved.

  def invalidate_featured_cache(post: Post) -> bool:
    - Only invalidate if post.is_featured == True OR
      post was previously featured (use update_fields hint: 'is_featured' in kwargs)
    - cache.delete(FEATURED_POSTS_KEY)
    - Return True if cache was deleted, False if key didn't exist

  Simple approach (always invalidate on Post save):
    def invalidate_featured_cache(post=None) -> bool:
        return cache.delete(FEATURED_POSTS_KEY)
    cache.delete returns True if key existed, False if not.
"""

def invalidate_featured_cache() -> bool:
    raise NotImplementedError(
        "TODO 2: cache.delete(FEATURED_POSTS_KEY) — return True if deleted"
    )


# ════════════════════════════════════════════════════════════════════════════
# TODO 3 — get_post_detail_cached()
# ════════════════════════════════════════════════════════════════════════════
"""
Per-post cache: cache individual post data.

  CACHE_KEY_PATTERN = "blog:post:{post_id}"

  def get_post_detail_cached(post_id: int, ttl: int = 600) -> dict | None:
    1. key = f"blog:post:{post_id}"
    2. cached = cache.get(key)
    3. If hit: return cached
    4. If miss:
         a. Try Post.objects.select_related('author', 'category').get(id=post_id)
         b. If DoesNotExist: return None
         c. Build dict: {id, title, content, author_email, category_name, likes_count}
         d. cache.set(key, result, timeout=ttl)
         e. Return result

  def invalidate_post_detail_cache(post_id: int) -> bool:
    cache.delete(f"blog:post:{post_id}")
"""

def get_post_detail_cached(post_id: int, ttl: int = 600) -> dict | None:
    raise NotImplementedError(
        "TODO 3a: Per-post cache-aside with key=f'blog:post:{post_id}'"
    )

def invalidate_post_detail_cache(post_id: int) -> bool:
    raise NotImplementedError(
        "TODO 3b: cache.delete(f'blog:post:{post_id}')"
    )


# ════════════════════════════════════════════════════════════════════════════
# TODO 4 — get_featured_posts_stampede_safe()
# ════════════════════════════════════════════════════════════════════════════
"""
Cache stampede prevention using lock pattern:

  LOCK_KEY = "blog:featured_posts:lock"
  LOCK_TTL = 30  # seconds

  def get_featured_posts_stampede_safe() -> list:
    1. Try cache.get(FEATURED_POSTS_KEY) → if hit, return
    2. Try to acquire lock: cache.add(LOCK_KEY, 1, timeout=LOCK_TTL)
       cache.add is ATOMIC — returns True only if key NOT already present
    3. If lock acquired (True):
         a. Re-check cache (another process may have populated while we waited)
         b. If still miss: fetch from DB + cache.set(...)
         c. cache.delete(LOCK_KEY)  # release lock
         d. Return data
    4. If lock NOT acquired (False):
         a. Retry loop: up to 10 times, sleep 0.1s between retries
         b. On each retry: check cache.get(FEATURED_POSTS_KEY)
         c. If populated by lock holder: return it
         d. If exhausted retries: fetch DB directly as fallback

  Note: In production use Redis native SETNX + TTL for true atomic lock.
        Django cache.add() is atomic only for Redis/Memcache backends.
"""

def get_featured_posts_stampede_safe() -> list:
    raise NotImplementedError(
        "TODO 4: Implement lock-based stampede prevention using cache.add()"
    )


# ════════════════════════════════════════════════════════════════════════════
# AUTOUSE FIXTURE — clear cache before each test
# ════════════════════════════════════════════════════════════════════════════

@pytest.fixture(autouse=True)
@override_settings(CACHES=LOCMEM_CACHE)
def clear_test_cache():
    """Clear all cache keys before each test."""
    cache.clear()
    yield
    cache.clear()


# ════════════════════════════════════════════════════════════════════════════
# TESTS
# ════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
@override_settings(CACHES=LOCMEM_CACHE)
def test_cache_miss_fetches_from_db():
    """First call (cold cache) must hit DB and return correct data."""
    cache.clear()
    p1 = L10PostFactory(is_featured=True, title="Featured A")
    p2 = L10PostFactory(is_featured=True, title="Featured B")
    L10PostFactory(is_featured=False, title="Not Featured")

    result = get_featured_posts_cached()

    assert isinstance(result, list), "FAIL: Should return a list"
    titles = [p['title'] for p in result]
    assert "Featured A" in titles, "FAIL: Featured A should be in result"
    assert "Featured B" in titles, "FAIL: Featured B should be in result"
    assert "Not Featured" not in titles, "FAIL: Non-featured post should be excluded"


@pytest.mark.django_db
@override_settings(CACHES=LOCMEM_CACHE)
def test_cache_hit_avoids_db_query():
    """Second call (warm cache) should NOT hit DB."""
    cache.clear()
    L10PostFactory(is_featured=True, title="Cached Post")

    # First call populates cache
    get_featured_posts_cached()

    # Second call should use cache — count DB queries
    from django.test.utils import CaptureQueriesContext
    from django.db import connection

    with CaptureQueriesContext(connection) as ctx:
        result = get_featured_posts_cached()

    assert len(ctx.captured_queries) == 0, (
        f"FAIL: Second call should hit cache (0 DB queries). "
        f"Got {len(ctx.captured_queries)} queries — cache miss?"
    )
    assert len(result) > 0, "FAIL: Cache hit returned empty result"


@pytest.mark.django_db
@override_settings(CACHES=LOCMEM_CACHE)
def test_invalidation_clears_cache():
    """After invalidation, next read re-fetches from DB."""
    cache.clear()
    L10PostFactory(is_featured=True, title="Original Featured")

    # Populate cache
    get_featured_posts_cached()
    assert cache.get(FEATURED_POSTS_KEY) is not None, "FAIL: Cache not populated"

    # Invalidate
    deleted = invalidate_featured_cache()
    assert deleted, "FAIL: invalidate_featured_cache() should return True (key existed)"
    assert cache.get(FEATURED_POSTS_KEY) is None, (
        "FAIL: Cache should be empty after invalidation"
    )


@pytest.mark.django_db
@override_settings(CACHES=LOCMEM_CACHE)
def test_invalidation_then_new_data_fetched():
    """After invalidating, new DB data should appear in next read."""
    cache.clear()
    L10PostFactory(is_featured=True, title="Old Featured")
    get_featured_posts_cached()   # cache: ["Old Featured"]

    # Add new featured post
    L10PostFactory(is_featured=True, title="New Featured")
    invalidate_featured_cache()   # clear stale cache

    result = get_featured_posts_cached()   # re-fetch from DB
    titles = [p['title'] for p in result]
    assert "New Featured" in titles, (
        "FAIL: New featured post should appear after cache invalidation + re-fetch"
    )


@pytest.mark.django_db
@override_settings(CACHES=LOCMEM_CACHE)
def test_post_detail_cache_miss_then_hit():
    """get_post_detail_cached: miss → DB → set cache → hit."""
    cache.clear()
    post = L10PostFactory(title="Detail Cache Test")

    # First call: miss
    result1 = get_post_detail_cached(post.id)
    assert result1 is not None, "FAIL: Should return post data"
    assert result1['title'] == "Detail Cache Test", f"FAIL: Wrong title: {result1}"
    assert 'author_email' in result1, "FAIL: 'author_email' should be in result dict"

    # Second call: hit (no DB)
    from django.test.utils import CaptureQueriesContext
    from django.db import connection

    with CaptureQueriesContext(connection) as ctx:
        result2 = get_post_detail_cached(post.id)

    assert result2['id'] == post.id, "FAIL: Cached result has wrong id"
    assert len(ctx.captured_queries) == 0, (
        f"FAIL: Second call should hit cache (0 queries). Got {len(ctx.captured_queries)}"
    )


@pytest.mark.django_db
@override_settings(CACHES=LOCMEM_CACHE)
def test_post_detail_returns_none_for_missing():
    """Non-existent post should return None, not raise DoesNotExist."""
    cache.clear()
    result = get_post_detail_cached(post_id=99999)
    assert result is None, "FAIL: Should return None for non-existent post"


@pytest.mark.django_db
@override_settings(CACHES=LOCMEM_CACHE)
def test_post_detail_invalidation():
    """After invalidating post cache, next fetch gets fresh data."""
    cache.clear()
    post = L10PostFactory(title="Original Title")
    get_post_detail_cached(post.id)   # populate cache

    # Simulate update
    Post.objects.filter(id=post.id).update(title="Updated Title")
    invalidate_post_detail_cache(post.id)

    result = get_post_detail_cached(post.id)
    assert result['title'] == "Updated Title", (
        f"FAIL: After invalidation, should see 'Updated Title'. Got: {result['title']}"
    )


@pytest.mark.django_db
@override_settings(CACHES=LOCMEM_CACHE)
def test_stampede_safe_returns_data():
    """Stampede-safe function should return correct data."""
    cache.clear()
    L10PostFactory(is_featured=True, title="Stampede Test Post")

    result = get_featured_posts_stampede_safe()
    assert isinstance(result, list), "FAIL: Should return a list"
    assert len(result) > 0, "FAIL: Should return at least 1 featured post"
    assert result[0]['title'] == "Stampede Test Post", "FAIL: Wrong data"


@pytest.mark.django_db
@override_settings(CACHES=LOCMEM_CACHE)
def test_stampede_safe_uses_lock():
    """Second concurrent call should find lock acquired and wait/retry."""
    cache.clear()
    L10PostFactory(is_featured=True)

    # Simulate: cache is empty, lock is pre-acquired by "another process"
    # Our call should retry until lock is released
    LOCK_KEY = "blog:featured_posts:lock"

    # Pre-set the data (simulates lock holder populating cache while we wait)
    cache.set(LOCK_KEY, 1, timeout=1)
    cache.set(FEATURED_POSTS_KEY, [{'title': 'Pre-set Data', 'id': 999}], timeout=60)

    result = get_featured_posts_stampede_safe()
    # Should get pre-set data (cache hit on retry)
    assert result is not None, "FAIL: Should return data even when lock is held"


# ════════════════════════════════════════════════════════════════════════════
# SOCH
# ════════════════════════════════════════════════════════════════════════════

"""
SOCH (Answer ALOUD):

Q1: Cache-aside pattern mein "stale data" kab hota hai?
    (DB updated but cache not invalidated yet — data inconsistency window = TTL)

Q2: TTL 5 minutes set karo ya 1 hour? Criteria kya hai?
    (Staleness tolerance × update frequency × DB load savings)
    Blog featured posts: 5 min ok. Stock prices: 0 (no cache or 1s TTL).

Q3: cache.add() vs cache.set() — kya fark hai stampede prevention mein?
    (add() is atomic test-and-set: returns False if key already exists.
     set() always overwrites — not safe for lock acquisition)

Q4: 20 Django instances (load balanced) hain. Redis cache shared hai.
    Ek instance cache delete kare toh dusre instances ko kya hoga?
    (All instances share same Redis → all see the invalidation → next read each does
     its own DB fetch → potential mini-stampede! Solution: Probabilistic early expiry
     or central lock in Redis)

Q5: Celery se cache warm-up pattern kya hai?
    (Background task refreshes cache BEFORE TTL expires, no user ever sees cold cache)
"""
