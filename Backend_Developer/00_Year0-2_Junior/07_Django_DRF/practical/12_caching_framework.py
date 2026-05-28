"""
Django Caching Framework — Production Patterns

Coverage: per-view, low-level, fragment, conditional view, invalidation via signals,
cache stampede prevention, per-user rate limiting.
"""

# ==========================================================================
# 1. SETTINGS — Redis cache backend
# ==========================================================================
"""
# settings.py
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.redis.RedisCache',
        'LOCATION': 'redis://127.0.0.1:6379/1',
        'KEY_PREFIX': 'myapp',
        'TIMEOUT': 300,
    },
}
"""


# ==========================================================================
# 2. PER-VIEW CACHE
# ==========================================================================

from django.views.decorators.cache import cache_page, never_cache
from django.views.decorators.vary import vary_on_cookie, vary_on_headers
from django.http import JsonResponse


@cache_page(60 * 15)  # 15 min
def public_article_list(request):
    from blog.models import Article
    articles = list(Article.objects.published().values('id', 'title')[:50])
    return JsonResponse({'articles': articles})


@cache_page(60 * 5)
@vary_on_headers('Accept-Language')
def localized_view(request):
    return JsonResponse({'lang': request.LANGUAGE_CODE})


@cache_page(60 * 5)
@vary_on_cookie
def user_dashboard(request):
    # Per-user cache — small hit rate
    return JsonResponse({'user': request.user.username})


@never_cache  # explicit opt-out
def login_view(request):
    return JsonResponse({})


# ==========================================================================
# 3. LOW-LEVEL CACHE API
# ==========================================================================

from django.core.cache import cache


def get_top_articles():
    """Read-through cache pattern."""
    key = 'top_articles:v1'
    val = cache.get(key)
    if val is None:
        from blog.models import Article
        val = list(Article.objects.popular()[:10].values())
        cache.set(key, val, timeout=3600)
    return val


def get_top_articles_atomic():
    """get_or_set — slightly cleaner."""
    from blog.models import Article
    return cache.get_or_set(
        'top_articles:v2',
        lambda: list(Article.objects.popular()[:10].values()),
        timeout=3600,
    )


# Batch operations
def warm_cache_for_users(user_ids):
    from django.contrib.auth import get_user_model
    User = get_user_model()
    users = User.objects.filter(pk__in=user_ids)
    cache.set_many(
        {f'user:{u.pk}': {'name': u.username, 'email': u.email} for u in users},
        timeout=3600,
    )


def get_users_bulk(user_ids):
    keys = [f'user:{uid}' for uid in user_ids]
    cached = cache.get_many(keys)
    missing = [uid for uid in user_ids if f'user:{uid}' not in cached]
    if missing:
        # Fetch + cache misses
        warm_cache_for_users(missing)
        cached.update(cache.get_many([f'user:{uid}' for uid in missing]))
    return cached


# ==========================================================================
# 4. CACHE STAMPEDE PREVENTION
# ==========================================================================

import time


def get_top_articles_safe():
    """Single-flight pattern using cache.add() as lock."""
    key = 'top_articles:safe'
    val = cache.get(key)
    if val is not None:
        return val

    lock_key = f'{key}:lock'
    acquired = cache.add(lock_key, '1', timeout=30)
    if acquired:
        try:
            from blog.models import Article
            val = list(Article.objects.popular()[:10].values())
            cache.set(key, val, timeout=3600)
            return val
        finally:
            cache.delete(lock_key)
    else:
        # Wait briefly + retry
        for _ in range(10):
            time.sleep(0.2)
            val = cache.get(key)
            if val is not None:
                return val
        # Fallback: compute anyway
        from blog.models import Article
        return list(Article.objects.popular()[:10].values())


# ==========================================================================
# 5. CACHE INVALIDATION via SIGNALS
# ==========================================================================

from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver


# @receiver(post_save, sender=Article)
# @receiver(post_delete, sender=Article)
def invalidate_article_cache(sender, instance, **kwargs):
    cache.delete(f'article:{instance.pk}')
    # Invalidate aggregate caches too
    cache.delete_many([
        'top_articles:v1',
        'top_articles:v2',
        'top_articles:safe',
    ])


# Better pattern: cache versioning
def get_article(pk, version=None):
    version = version or cache.get('article_version', 1)
    return cache.get_or_set(
        f'article:{pk}',
        lambda: Article.objects.get(pk=pk),
        timeout=3600,
        version=version,
    )


def bump_article_version():
    """Bulk invalidate all article caches."""
    cache.incr('article_version', delta=1)


# ==========================================================================
# 6. CONDITIONAL VIEW PROCESSING (ETag / Last-Modified)
# ==========================================================================

from django.views.decorators.http import etag, last_modified
from django.shortcuts import get_object_or_404


def article_last_modified_fn(request, pk):
    from blog.models import Article
    try:
        return Article.objects.values('updated_at').get(pk=pk)['updated_at']
    except Article.DoesNotExist:
        return None


def article_etag_fn(request, pk):
    from blog.models import Article
    try:
        article = Article.objects.values('updated_at', 'view_count').get(pk=pk)
        return f'{article["updated_at"].timestamp()}-{article["view_count"]}'
    except Article.DoesNotExist:
        return None


@etag(article_etag_fn)
@last_modified(article_last_modified_fn)
def article_detail_conditional(request, pk):
    from blog.models import Article
    article = get_object_or_404(Article, pk=pk)
    return JsonResponse({
        'id': article.id,
        'title': article.title,
        'updated_at': article.updated_at,
    })


# ==========================================================================
# 7. PER-USER RATE LIMITING via CACHE
# ==========================================================================

def rate_limit_check(user_id, action='default', limit=10, window=60):
    """Returns (allowed, remaining)."""
    key = f'rl:{action}:{user_id}'
    try:
        # Redis-backed cache supports incr
        current = cache.get(key, 0)
        if current >= limit:
            return False, 0
        new_count = cache.incr(key) if current > 0 else None
        if new_count is None:
            cache.set(key, 1, timeout=window)
            new_count = 1
        return True, max(0, limit - new_count)
    except ValueError:
        # Key doesn't exist yet — initialize
        cache.set(key, 1, timeout=window)
        return True, limit - 1


# Usage in view
def expensive_endpoint(request):
    allowed, remaining = rate_limit_check(
        request.user.id,
        action='expensive',
        limit=10,
        window=60,
    )
    if not allowed:
        return JsonResponse({'error': 'Rate limit exceeded'}, status=429)
    # ... work
    return JsonResponse({'remaining': remaining})


# ==========================================================================
# 8. SESSION CACHE (settings.py)
# ==========================================================================
"""
# settings.py
SESSION_ENGINE = 'django.contrib.sessions.backends.cache'  # in-memory only
# Better:
SESSION_ENGINE = 'django.contrib.sessions.backends.cached_db'  # cache + DB fallback
"""


# ==========================================================================
# 9. TESTING WITH DUMMY CACHE
# ==========================================================================
"""
# settings/test.py
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'test-cache',
    },
}

# tests
from django.core.cache import cache

class CacheTests(TestCase):
    def setUp(self):
        cache.clear()  # IMPORTANT

    def test_get_top_articles_caches(self):
        get_top_articles()
        assert cache.get('top_articles:v1') is not None
"""


# ==========================================================================
# 10. CACHE MIDDLEWARE (per-site)
# ==========================================================================
"""
# settings.py
MIDDLEWARE = [
    'django.middleware.cache.UpdateCacheMiddleware',
    # ... other middleware
    'django.middleware.cache.FetchFromCacheMiddleware',
]

CACHE_MIDDLEWARE_SECONDS = 600
CACHE_MIDDLEWARE_KEY_PREFIX = 'site'
"""
