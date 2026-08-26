"""
Lab 09 — Cursor vs Offset/PageNumber Pagination
═══════════════════════════════════════════════════════════════════════════════

ARCHITECTURE — Two Pagination Strategies:

    OFFSET / PAGE-NUMBER PAGINATION:
        GET /posts/?page=3&page_size=10
        SQL: SELECT * FROM posts ORDER BY id LIMIT 10 OFFSET 20

        Internally:
          1. COUNT(*) on full table      ← EXPENSIVE on 10M rows
          2. SKIP first (page-1)*size rows (OFFSET) — DB still scans them!
          3. Return next `size` rows

        Problems:
          - COUNT(*) = full table scan on large tables (no index helps)
          - "Page drift": if a new post is added/deleted between requests,
            items shift → duplicate or missing items across pages
          - Deep pagination (page=50000) = very expensive OFFSET scan

    CURSOR PAGINATION:
        GET /posts/?cursor=<encoded_timestamp>
        SQL: SELECT * FROM posts WHERE created_at < '2024-01-15T10:30:00'
             ORDER BY created_at DESC LIMIT 20

        Internally:
          1. Encode last-seen item position as opaque cursor token
          2. WHERE clause instead of OFFSET — uses INDEX (B-tree on created_at)
          3. No COUNT(*) needed

        Benefits:
          ✅ O(log N) — index-based lookup, scales to 100M rows
          ✅ No page drift — cursor points to exact position, new items don't shift it
          ✅ Consistent — safe for real-time feeds, infinite scroll

        Limitations:
          ❌ Cannot jump to arbitrary page (no "page 500")
          ❌ Requires stable, unique ordering column (created_at, id)
          ❌ Cursor token is opaque — not human-readable

    LIMIT-OFFSET PAGINATION:
        GET /posts/?limit=10&offset=20
        Same as page-number but client controls offset directly.
        Same problems as page-number.

CONTEXT:
  Blog API has 1000+ posts. Product team wants:
    - Admin panel: page-number (can jump to page 50)
    - Mobile app feed: cursor (infinite scroll, no drift)

RUN:
    cd practical/
    pytest labs/lab_09_cursor_vs_offset_pagination.py -v -p no:odoo

SOCH — Answer ALOUD:
  Q1: Cursor pagination kyon page drift se safe hai? Offset kyon nahi?
  Q2: DRF CursorPagination mein 'ordering' field important kyon hai?
      Kya hoga agar ordering field unique nahi hai?
  Q3: Mobile app infinite scroll ke liye cursor better kyon hai?
  Q4: Admin panel mein cursor pagination kyon problematic hai?
  Q5: Instagram-style feed mein kaunsa pagination? (Millions of posts, real-time)
"""

import pytest
from rest_framework.test import APIRequestFactory, force_authenticate
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.pagination import CursorPagination, PageNumberPagination
from rest_framework import serializers
from django.test import override_settings

import factory
from factory.django import DjangoModelFactory
from django.contrib.auth import get_user_model
from django.utils import timezone

from blog.models import Post, Category

User = get_user_model()


# ════════════════════════════════════════════════════════════════════════════
# FACTORIES
# ════════════════════════════════════════════════════════════════════════════

class L9UserFactory(DjangoModelFactory):
    class Meta:
        model = User
    email    = factory.Sequence(lambda n: f"l9user{n}@test.com")
    username = factory.Sequence(lambda n: f"l9user{n}")
    password = factory.PostGenerationMethodCall('set_password', 'pass123')

class L9CategoryFactory(DjangoModelFactory):
    class Meta:
        model = Category
    name = factory.Sequence(lambda n: f"L9Cat{n}")

class L9PostFactory(DjangoModelFactory):
    class Meta:
        model = Post
    title        = factory.Sequence(lambda n: f"L9 Post {n:04d}")
    content      = "Content word " * 60
    excerpt      = "Excerpt."
    author       = factory.SubFactory(L9UserFactory)
    category     = factory.SubFactory(L9CategoryFactory)
    status       = 'published'
    published_at = factory.LazyFunction(timezone.now)


# ════════════════════════════════════════════════════════════════════════════
# MINIMAL SERIALIZER
# ════════════════════════════════════════════════════════════════════════════

class PostListSerializer(serializers.ModelSerializer):
    class Meta:
        model  = Post
        fields = ['id', 'title', 'status', 'published_at']


# ════════════════════════════════════════════════════════════════════════════
# TODO 1 — BlogCursorPagination
# ════════════════════════════════════════════════════════════════════════════
"""
Implement BlogCursorPagination(CursorPagination):
  page_size             = 5
  page_size_query_param = 'page_size'
  max_page_size         = 50
  ordering              = '-published_at'   ← must be indexed column, unique enough

  Override get_paginated_response to return:
  {
    "pagination": {
        "next":      <next_cursor_url or null>,
        "previous":  <previous_cursor_url or null>,
        "page_size": <int>
    },
    "results": [...]
  }
"""

class BlogCursorPagination(CursorPagination):
    page_size              = None   # TODO 1: set to 5
    page_size_query_param  = None   # TODO 1: set to 'page_size'
    max_page_size          = None   # TODO 1: set to 50
    ordering               = None   # TODO 1: set to '-published_at'

    def get_paginated_response(self, data):
        raise NotImplementedError(
            "TODO 1: Return Response({'pagination': {'next':..., 'previous':..., 'page_size':...}, 'results': data})"
        )


# ════════════════════════════════════════════════════════════════════════════
# TODO 2 — BlogPageNumberPagination
# ════════════════════════════════════════════════════════════════════════════
"""
Implement BlogPageNumberPagination(PageNumberPagination):
  page_size             = 5
  page_size_query_param = 'page_size'
  max_page_size         = 50
  page_query_param      = 'page'

  Override get_paginated_response to return:
  {
    "pagination": {
        "count":       <total item count>,
        "total_pages": <total pages>,
        "page":        <current page number>,
        "next":        <url or null>,
        "previous":    <url or null>
    },
    "results": [...]
  }
"""

class BlogPageNumberPagination(PageNumberPagination):
    page_size             = None   # TODO 2: set to 5
    page_size_query_param = None   # TODO 2: set to 'page_size'
    max_page_size         = None   # TODO 2: set to 50
    page_query_param      = None   # TODO 2: set to 'page'

    def get_paginated_response(self, data):
        raise NotImplementedError(
            "TODO 2: Return Response({'pagination': {'count':..., 'total_pages':..., 'page':..., 'next':..., 'previous':...}, 'results': data})"
        )


# ════════════════════════════════════════════════════════════════════════════
# TODO 3 — CursorPostListView
# ════════════════════════════════════════════════════════════════════════════
"""
Implement CursorPostListView(APIView):
  Uses BlogCursorPagination.

  get(self, request):
    1. queryset = Post.objects.filter(status='published').order_by('-published_at')
    2. paginator = BlogCursorPagination()
    3. page = paginator.paginate_queryset(queryset, request, view=self)
    4. serializer = PostListSerializer(page, many=True)
    5. return paginator.get_paginated_response(serializer.data)
"""

class CursorPostListView(APIView):
    permission_classes = []

    def get(self, request):
        raise NotImplementedError(
            "TODO 3: Paginate posts using BlogCursorPagination"
        )


# ════════════════════════════════════════════════════════════════════════════
# TODO 4 — PageNumberPostListView
# ════════════════════════════════════════════════════════════════════════════
"""
Implement PageNumberPostListView(APIView) — same structure as TODO 3 but
  uses BlogPageNumberPagination instead.
"""

class PageNumberPostListView(APIView):
    permission_classes = []

    def get(self, request):
        raise NotImplementedError(
            "TODO 4: Paginate posts using BlogPageNumberPagination"
        )


# ════════════════════════════════════════════════════════════════════════════
# TESTS
# ════════════════════════════════════════════════════════════════════════════

api_factory = APIRequestFactory()

DRF_OVERRIDE = {
    'DEFAULT_AUTHENTICATION_CLASSES': [],
    'DEFAULT_PERMISSION_CLASSES': [],
}


@pytest.mark.django_db
@override_settings(REST_FRAMEWORK=DRF_OVERRIDE)
def test_cursor_pagination_returns_correct_page_size():
    """Cursor pagination should return page_size=5 results."""
    for _ in range(12):
        L9PostFactory()

    request  = api_factory.get('/posts/')
    view     = CursorPostListView.as_view()
    response = view(request)

    assert response.status_code == 200, f"FAIL: {response.status_code} — {response.data}"
    assert 'results' in response.data, f"FAIL: 'results' key missing. Got: {list(response.data.keys())}"
    assert len(response.data['results']) == 5, (
        f"FAIL: Expected 5 results (page_size). Got {len(response.data['results'])}"
    )


@pytest.mark.django_db
@override_settings(REST_FRAMEWORK=DRF_OVERRIDE)
def test_cursor_response_has_pagination_wrapper():
    """Cursor response should have 'pagination' key with next/previous."""
    for _ in range(8):
        L9PostFactory()

    request  = api_factory.get('/posts/')
    response = CursorPostListView.as_view()(request)

    assert 'pagination' in response.data, (
        f"FAIL: 'pagination' key missing. Got: {list(response.data.keys())}"
    )
    pagination = response.data['pagination']
    assert 'next' in pagination,     "FAIL: 'next' missing from pagination"
    assert 'previous' in pagination, "FAIL: 'previous' missing from pagination"
    assert 'page_size' in pagination, "FAIL: 'page_size' missing from pagination"


@pytest.mark.django_db
@override_settings(REST_FRAMEWORK=DRF_OVERRIDE)
def test_cursor_next_is_not_none_when_more_pages():
    """If total > page_size, next cursor should not be null."""
    for _ in range(10):
        L9PostFactory()

    request  = api_factory.get('/posts/')
    response = CursorPostListView.as_view()(request)

    next_url = response.data['pagination']['next']
    assert next_url is not None, (
        "FAIL: next cursor should be set when total (10) > page_size (5)"
    )


@pytest.mark.django_db
@override_settings(REST_FRAMEWORK=DRF_OVERRIDE)
def test_page_number_returns_count_and_total_pages():
    """Page-number response must include total count and total_pages."""
    for _ in range(13):
        L9PostFactory()

    request  = api_factory.get('/posts/')
    response = PageNumberPostListView.as_view()(request)

    assert response.status_code == 200, f"FAIL: {response.status_code}"
    assert 'pagination' in response.data, "FAIL: 'pagination' missing"
    pag = response.data['pagination']
    assert 'count' in pag,       "FAIL: 'count' missing — page-number pagination needs total count"
    assert 'total_pages' in pag, "FAIL: 'total_pages' missing"
    assert pag['count'] >= 13,   f"FAIL: count should be >= 13. Got {pag['count']}"
    assert pag['total_pages'] >= 3, f"FAIL: 13 items / page_size=5 = 3 pages. Got {pag['total_pages']}"


@pytest.mark.django_db
@override_settings(REST_FRAMEWORK=DRF_OVERRIDE)
def test_page_number_page_param_works():
    """Page-number accepts ?page=2 param."""
    for _ in range(10):
        L9PostFactory()

    request  = api_factory.get('/posts/?page=2')
    response = PageNumberPostListView.as_view()(request)

    assert response.status_code == 200, f"FAIL: page=2 request failed: {response.data}"
    assert response.data['pagination']['page'] == 2, (
        f"FAIL: pagination.page should be 2. Got {response.data['pagination'].get('page')}"
    )


@pytest.mark.django_db
@override_settings(REST_FRAMEWORK=DRF_OVERRIDE)
def test_cursor_no_count_in_response():
    """
    Cursor pagination must NOT have 'count' or 'total_pages'.
    This is the key difference — cursor doesn't do COUNT(*).
    """
    for _ in range(8):
        L9PostFactory()

    request  = api_factory.get('/posts/')
    response = CursorPostListView.as_view()(request)

    pag = response.data.get('pagination', {})
    assert 'count' not in pag, (
        f"FAIL: Cursor pagination should NOT have 'count' (no COUNT(*) query). "
        f"Got: {pag}"
    )
    assert 'total_pages' not in pag, (
        "FAIL: Cursor pagination should NOT have 'total_pages'"
    )


@pytest.mark.django_db
@override_settings(REST_FRAMEWORK=DRF_OVERRIDE)
def test_page_size_custom_via_param():
    """?page_size=2 should override default page_size."""
    for _ in range(8):
        L9PostFactory()

    request  = api_factory.get('/posts/?page_size=2')
    response = CursorPostListView.as_view()(request)

    assert len(response.data['results']) == 2, (
        f"FAIL: ?page_size=2 should return 2 items. Got {len(response.data['results'])}"
    )


# ════════════════════════════════════════════════════════════════════════════
# SOCH
# ════════════════════════════════════════════════════════════════════════════

"""
SOCH (Answer ALOUD):

Q1: "Page drift" problem kya hai? Example deke explain karo:
    User page=1 dekh raha hai (posts 1-10). Koi naya post add hota hai.
    Ab user page=2 request kare toh kya hoga? (Post 10 dono pages pe!)

Q2: Cursor token mein kya store hota hai? (Encoded timestamp + direction)
    Kyon URL mein plain timestamp nahi dete? (Security + opaqueness)

Q3: Cursor pagination ke liye ordering column unique hona kyon zaroori hai?
    Agar do posts same published_at pe create hon toh kya? (Use id as tiebreaker)

Q4: DRF ka CursorPagination internally kya SQL generate karta hai?
    (WHERE published_at < '...' ORDER BY published_at DESC LIMIT n)

Q5: Admin panel ke liye cursor kyon problematic hai?
    ("Go to page 500" feature impossible with cursor — no random access)
"""
