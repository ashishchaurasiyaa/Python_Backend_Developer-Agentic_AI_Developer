"""
N+1 Detection — Test patterns + diagnostic tools.

Use in Django project. Some sections are settings snippets, others are runnable.
"""

# ==========================================================================
# 1. DEMONSTRATING N+1 (the bug)
# ==========================================================================

# from blog.models import Article
#
# # BAD — N+1 (1 + 10 queries)
# for a in Article.objects.all()[:10]:
#     print(a.author.username)
#
# # GOOD — 1 query with JOIN
# for a in Article.objects.select_related('author')[:10]:
#     print(a.author.username)


# ==========================================================================
# 2. TEST PATTERN — assertNumQueries
# ==========================================================================

from django.test import TestCase


class ArticleListN1Test(TestCase):
    """Lock down expected query count for an endpoint."""

    @classmethod
    def setUpTestData(cls):
        from django.contrib.auth import get_user_model
        from blog.models import Article  # noqa
        User = get_user_model()
        for i in range(20):
            u = User.objects.create(username=f'user{i}')
            # Article.objects.create(title=f'T{i}', author=u)

    def test_list_query_count(self):
        # Adjust based on actual endpoint needs
        with self.assertNumQueries(3):
            response = self.client.get('/api/articles/')
        self.assertEqual(response.status_code, 200)


# ==========================================================================
# 3. CaptureQueriesContext — debug what queries run
# ==========================================================================

from django.test.utils import CaptureQueriesContext
from django.db import connection


def debug_view_queries():
    """Run from shell to see what queries execute."""
    # from blog.models import Article
    with CaptureQueriesContext(connection) as ctx:
        # Replace with code under test
        # for a in Article.objects.all()[:5]:
        #     _ = a.author.username
        pass

    print(f"Total queries: {len(ctx.captured_queries)}")
    for i, q in enumerate(ctx.captured_queries, 1):
        print(f"\n[{i}] ({q['time']}s)")
        print(f"  {q['sql']}")


# Usage in test:
# def test_with_capture(self):
#     with CaptureQueriesContext(connection) as ctx:
#         list(Article.objects.select_related('author'))
#     assert len(ctx.captured_queries) == 1


# ==========================================================================
# 4. SETTINGS — django-debug-toolbar (dev only)
# ==========================================================================
"""
# settings/dev.py

if DEBUG:
    INSTALLED_APPS += ['debug_toolbar']
    MIDDLEWARE = ['debug_toolbar.middleware.DebugToolbarMiddleware'] + MIDDLEWARE
    INTERNAL_IPS = ['127.0.0.1']

    DEBUG_TOOLBAR_CONFIG = {
        'SHOW_TOOLBAR_CALLBACK': lambda request: True,
    }

# urls.py
if settings.DEBUG:
    from django.urls import include, path
    urlpatterns += [path('__debug__/', include('debug_toolbar.urls'))]
"""


# ==========================================================================
# 5. SETTINGS — django-silk (staging profiling)
# ==========================================================================
"""
# settings/staging.py

INSTALLED_APPS += ['silk']
MIDDLEWARE = ['silk.middleware.SilkyMiddleware'] + MIDDLEWARE

SILKY_PYTHON_PROFILER = True
SILKY_PYTHON_PROFILER_BINARY = True   # for cProfile dumps
SILKY_AUTHENTICATION = True
SILKY_AUTHORISATION = True
SILKY_PERMISSIONS = lambda user: user.is_superuser

# urls.py
urlpatterns += [path('silk/', include('silk.urls', namespace='silk'))]
"""


# ==========================================================================
# 6. SETTINGS — nplusone (auto-detect, raise in tests)
# ==========================================================================
"""
# settings/test.py

INSTALLED_APPS += ['nplusone.ext.django']
MIDDLEWARE = ['nplusone.ext.django.NPlusOneMiddleware'] + MIDDLEWARE

# Fail tests on any N+1 detected
NPLUSONE_RAISE = True

# Or just log warnings (dev)
# import logging
# NPLUSONE_LOGGER = logging.getLogger('nplusone')
# NPLUSONE_LOG_LEVEL = logging.WARNING
"""


# ==========================================================================
# 7. PROPER PREFETCHING PATTERNS
# ==========================================================================

# from django.db.models import Prefetch, Count, Sum, Q, Subquery, OuterRef
# from blog.models import Article, Comment

# # Pattern 1: select_related for forward FK (single related row)
# Article.objects.select_related('author', 'category')

# # Pattern 2: prefetch_related for M2M / reverse FK
# Article.objects.prefetch_related('tags', 'comments')

# # Pattern 3: Multi-level
# Article.objects.select_related('author__profile').prefetch_related('comments__author')

# # Pattern 4: Filtered prefetch via Prefetch
# Article.objects.prefetch_related(
#     Prefetch(
#         'comments',
#         queryset=Comment.objects.filter(approved=True).order_by('-created_at')[:5],
#         to_attr='top_comments',
#     )
# )

# # Pattern 5: Annotate to avoid count loops
# Article.objects.annotate(
#     comment_count=Count('comments', filter=Q(comments__approved=True), distinct=True)
# )

# # Pattern 6: Subquery for accurate aggregations (avoid JOIN fanout)
# Article.objects.annotate(
#     comment_count=Subquery(
#         Comment.objects.filter(article=OuterRef('pk'), approved=True)
#         .values('article')
#         .annotate(c=Count('*'))
#         .values('c')
#     )
# )

# # Pattern 7: only() for big-column avoidance
# Article.objects.only('id', 'title', 'author_id').select_related('author')

# # Pattern 8: values() for read-only fast paths
# Article.objects.values('id', 'title', 'author__username')


# ==========================================================================
# 8. DRF — Fix N+1 in get_queryset
# ==========================================================================

# from rest_framework import generics, serializers
# from blog.models import Article
#
# class ArticleSerializer(serializers.ModelSerializer):
#     author_name = serializers.CharField(source='author.username')
#     comment_count = serializers.IntegerField(read_only=True)
#
#     class Meta:
#         model = Article
#         fields = ('id', 'title', 'author_name', 'comment_count')
#
#
# class ArticleListView(generics.ListAPIView):
#     serializer_class = ArticleSerializer
#
#     def get_queryset(self):
#         from django.db.models import Count
#         return (
#             Article.objects
#             .select_related('author')
#             .annotate(comment_count=Count('comments'))
#             .order_by('-created_at')
#         )


# ==========================================================================
# 9. ENABLE SQL LOGGING (last-resort debugging)
# ==========================================================================
"""
# settings/dev.py

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {'class': 'logging.StreamHandler'},
    },
    'loggers': {
        'django.db.backends': {
            'level': 'DEBUG',
            'handlers': ['console'],
        },
    },
}
"""


# ==========================================================================
# 10. PRODUCTION — pg_stat_statements query
# ==========================================================================
"""
-- Enable extension (DBA)
CREATE EXTENSION IF NOT EXISTS pg_stat_statements;

-- Top 20 queries by total time
SELECT
    calls,
    total_exec_time::int AS total_ms,
    mean_exec_time::int AS mean_ms,
    rows,
    LEFT(query, 100) AS query_snippet
FROM pg_stat_statements
ORDER BY total_exec_time DESC
LIMIT 20;

-- Top by call count (high freq = likely N+1 candidate)
SELECT
    calls,
    mean_exec_time::int AS mean_ms,
    LEFT(query, 100) AS query_snippet
FROM pg_stat_statements
ORDER BY calls DESC
LIMIT 20;
"""


# ==========================================================================
# 11. CI ASSERTION HELPER
# ==========================================================================

from contextlib import contextmanager


@contextmanager
def max_queries(max_count):
    """Assert that block runs in <= max_count queries."""
    with CaptureQueriesContext(connection) as ctx:
        yield ctx
    actual = len(ctx.captured_queries)
    assert actual <= max_count, (
        f"Expected at most {max_count} queries, got {actual}:\n"
        + "\n".join(q['sql'][:120] for q in ctx.captured_queries)
    )


# Usage
# def test_view_under_limit():
#     with max_queries(5):
#         response = client.get('/api/articles/')
