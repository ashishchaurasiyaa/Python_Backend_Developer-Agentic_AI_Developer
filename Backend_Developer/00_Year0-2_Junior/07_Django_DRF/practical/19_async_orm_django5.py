"""
Django Async ORM + Views — Production Patterns
"""

# ==========================================================================
# 1. BASIC ASYNC VIEW
# ==========================================================================

import asyncio
from django.http import JsonResponse


async def hello_async(request):
    await asyncio.sleep(0.1)  # simulate I/O
    return JsonResponse({'hello': 'world'})


# ==========================================================================
# 2. ASYNC ORM — Single object operations
# ==========================================================================

# from blog.models import Article
# from django.contrib.auth import get_user_model
# User = get_user_model()


async def get_article_async(request, pk):
    try:
        article = await Article.objects.aget(pk=pk)
    except Article.DoesNotExist:
        return JsonResponse({'error': 'not found'}, status=404)
    return JsonResponse({'id': article.pk, 'title': article.title})


async def create_article_async(request):
    title = request.POST.get('title')
    author = await User.objects.aget(pk=request.user.pk)
    article = await Article.objects.acreate(title=title, author=author)
    return JsonResponse({'id': article.pk})


async def update_articles_async(request):
    updated = await Article.objects.filter(status='draft').aupdate(status='published')
    return JsonResponse({'updated': updated})


async def article_exists_async(request, pk):
    exists = await Article.objects.filter(pk=pk).aexists()
    return JsonResponse({'exists': exists})


# ==========================================================================
# 3. ASYNC ITERATION
# ==========================================================================

async def list_articles_async(request):
    articles = []
    async for article in Article.objects.filter(status='published').select_related('author'):
        articles.append({
            'id': article.pk,
            'title': article.title,
            'author': article.author.username,
        })
    return JsonResponse({'articles': articles})


# ==========================================================================
# 4. PARALLEL QUERIES (the killer feature)
# ==========================================================================

async def dashboard_async(request):
    """3 parallel queries — total time ~ slowest, not sum."""
    from django.db.models import Sum, Count

    revenue_task = Article.objects.filter(status='published').aaggregate(
        total=Sum('view_count')
    )
    article_count_task = Article.objects.acount()
    user_count_task = User.objects.acount()

    revenue, article_count, user_count = await asyncio.gather(
        revenue_task,
        article_count_task,
        user_count_task,
    )

    return JsonResponse({
        'total_views': revenue['total'] or 0,
        'article_count': article_count,
        'user_count': user_count,
    })


# ==========================================================================
# 5. ASYNC + EXTERNAL API CALL (the real win)
# ==========================================================================

import httpx
from django.utils import timezone


async def enrich_user_async(request, user_id):
    # Parallel: DB query + 3 external API calls
    user_task = User.objects.aget(pk=user_id)

    async with httpx.AsyncClient(timeout=5.0) as client:
        # Three external calls + DB all in parallel
        profile_task = client.get(f'https://api.example.com/users/{user_id}')
        prefs_task = client.get(f'https://api.example.com/prefs/{user_id}')
        stats_task = client.get(f'https://api.example.com/stats/{user_id}')

        user, profile_resp, prefs_resp, stats_resp = await asyncio.gather(
            user_task,
            profile_task,
            prefs_task,
            stats_task,
        )

    # Update user with combined data
    user.external_profile = profile_resp.json()
    user.external_prefs = prefs_resp.json()
    user.external_stats = stats_resp.json()
    user.synced_at = timezone.now()
    await user.asave()

    return JsonResponse({'user_id': user.pk, 'synced': True})


# ==========================================================================
# 6. SYNC_TO_ASYNC — bridge legacy code
# ==========================================================================

from asgiref.sync import sync_to_async, async_to_sync


def legacy_sync_calculation(article_id):
    """Existing sync code we can't rewrite."""
    article = Article.objects.get(pk=article_id)
    return article.complex_computation()


async def use_legacy_async(request, pk):
    # thread_sensitive=True (default) for DB-touching code
    result = await sync_to_async(legacy_sync_calculation)(pk)
    return JsonResponse({'result': result})


# Decorator form
@sync_to_async
def fetch_article_sync(pk):
    return Article.objects.get(pk=pk)


async def view_with_decorated(request, pk):
    article = await fetch_article_sync(pk)
    return JsonResponse({'title': article.title})


# ==========================================================================
# 7. NATIVE ASYNC TRANSACTION (Django 5.1+)
# ==========================================================================

# from django.db import transaction
#
#
# async def transactional_async_view(request):
#     async with transaction.atomic():       # Django 5.1+
#         order = await Order.objects.acreate(
#             user_id=request.user.pk,
#             amount=99.99,
#         )
#         payment = await Payment.objects.acreate(
#             order=order,
#             status='pending',
#         )
#         # ... external charge call
#         async with httpx.AsyncClient() as c:
#             resp = await c.post('https://api.stripe.com/v1/charges', json={...})
#             if resp.status_code != 200:
#                 # Auto-rollback on raise
#                 raise Exception("Payment failed")
#
#         payment.status = 'paid'
#         await payment.asave()
#
#     return JsonResponse({'order_id': order.pk})


# ==========================================================================
# 8. ASYNC MIDDLEWARE
# ==========================================================================

import time


class AsyncTimingMiddleware:
    """Records request duration in async-compatible way."""

    sync_capable = True
    async_capable = True

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if asyncio.iscoroutinefunction(self.get_response):
            return self.__acall__(request)
        # Sync path
        start = time.monotonic()
        response = self.get_response(request)
        duration_ms = int((time.monotonic() - start) * 1000)
        response['X-Request-Duration-Ms'] = str(duration_ms)
        return response

    async def __acall__(self, request):
        start = time.monotonic()
        response = await self.get_response(request)
        duration_ms = int((time.monotonic() - start) * 1000)
        response['X-Request-Duration-Ms'] = str(duration_ms)
        return response


# ==========================================================================
# 9. ASGI CONFIGURATION
# ==========================================================================
"""
# config/asgi.py

import os
from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

application = get_asgi_application()
"""

# Run with uvicorn:
# uvicorn config.asgi:application --host 0.0.0.0 --port 8000 --workers 4
#
# Or daphne:
# daphne -b 0.0.0.0 -p 8000 config.asgi:application


# ==========================================================================
# 10. ASYNC URL CONFIG (same as sync — Django handles it)
# ==========================================================================
"""
# urls.py — works for both sync and async views

from django.urls import path
from . import views

urlpatterns = [
    path('dashboard/', views.dashboard_async),
    path('article/<int:pk>/', views.get_article_async),
    path('enrich/<int:user_id>/', views.enrich_user_async),
]
"""


# ==========================================================================
# 11. TEST ASYNC VIEWS WITH AsyncClient
# ==========================================================================

# import pytest
# from django.test import AsyncClient
#
#
# @pytest.mark.asyncio
# @pytest.mark.django_db
# async def test_dashboard():
#     client = AsyncClient()
#     response = await client.get('/dashboard/')
#     assert response.status_code == 200
#     assert 'article_count' in response.json()


# ==========================================================================
# 12. ASYNC + CELERY DISPATCH
# ==========================================================================

# from blog.tasks import send_email_task
#
#
# async def signup_async(request):
#     user = await User.objects.acreate(
#         username=request.POST['username'],
#         email=request.POST['email'],
#     )
#
#     # .delay() is sync but non-blocking — just queues
#     send_email_task.delay(user.pk, 'welcome')
#
#     return JsonResponse({'user_id': user.pk})


# ==========================================================================
# 13. PERFORMANCE NOTES
# ==========================================================================
"""
Performance characteristics:

1. Single-query view → NO benefit from async (overhead actually slightly higher)
2. Multi-query view → benefit if queries parallelizable
3. External API + DB → BIG benefit
4. Pure CPU work → NO benefit (still single-threaded under GIL)

Connection pool tuning:
- pgBouncer in front, transaction pooling
- DATABASE['default']['CONN_MAX_AGE'] = 0 with pgBouncer

Async sync_to_async cost:
- ~50 microseconds overhead per call
- Don't sprinkle everywhere; batch sync work in one wrapper

Profiling async:
- django-silk supports async views
- py-spy --gil for GIL contention
"""
