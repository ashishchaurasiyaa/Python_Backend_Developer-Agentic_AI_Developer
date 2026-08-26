"""
Lab 02 — API Versioning with DRF
═══════════════════════════════════════════════════════════════════════════════

CONTEXT: Real APIs evolve over time. v1 clients expect minimal fields.
         v2 clients expect richer data. Breaking v1 clients = production incident.

GOAL: Learn DRF's QueryParameterVersioning — route to different serializers
      based on ?version= query param.

RUN:
    cd practical/
    pytest labs/lab_02_api_versioning.py -v -p no:odoo

SOCH — Answer ALOUD after completing each TODO:
  Q1: URLPathVersioning vs QueryParameterVersioning vs AcceptHeaderVersioning —
      production mein kaunsa prefer karoge aur kyon?
  Q2: request.version ka default value kya hota hai agar version param nahi diya?
  Q3: v1 serializer mein ek field add karna = backward compatible change ya breaking change?
  Q4: Ye versioning pattern kab BREAK ho jaata hai?
      (Hint: jab tum model delete karte ho jo v1 use karta hai)
  Q5: Interview mein "API versioning strategies explain karo" — 3 strategies bolo.
"""

import pytest
import factory
from factory.django import DjangoModelFactory
from django.contrib.auth import get_user_model
from django.test import override_settings
from django.urls import path
from django.utils import timezone

from rest_framework import serializers, versioning
from rest_framework.generics import ListAPIView
from rest_framework.permissions import AllowAny
from rest_framework.test import APIClient

from blog.models import Post, Category

User = get_user_model()


# ════════════════════════════════════════════════════════════════════════════
# FACTORIES (don't modify)
# ════════════════════════════════════════════════════════════════════════════

class L2UserFactory(DjangoModelFactory):
    class Meta:
        model = User
    email    = factory.Sequence(lambda n: f"l2user{n}@test.com")
    username = factory.Sequence(lambda n: f"l2user{n}")
    password = factory.PostGenerationMethodCall('set_password', 'pass123')


class L2CategoryFactory(DjangoModelFactory):
    class Meta:
        model = Category
    name = factory.Sequence(lambda n: f"L2Cat {n}")


class L2PostFactory(DjangoModelFactory):
    class Meta:
        model = Post
    title            = factory.Sequence(lambda n: f"L2 Post {n}")
    content          = "Content word " * 50
    excerpt          = "Lab 02 excerpt."
    author           = factory.SubFactory(L2UserFactory)
    category         = factory.SubFactory(L2CategoryFactory)
    status           = 'published'
    likes_count      = 42
    views_count      = 200
    published_at     = factory.LazyFunction(timezone.now)


# ════════════════════════════════════════════════════════════════════════════
# TODO 1 — PostV1Serializer
# ════════════════════════════════════════════════════════════════════════════
"""
V1 clients only need minimal data to display a post list.
Fields to expose: id, title, status

Fill in the Meta class:
  model = Post
  fields = ['id', 'title', 'status']
"""

class PostV1Serializer(serializers.ModelSerializer):
    class Meta:
        pass  # TODO: Add model = Post and fields = ['id', 'title', 'status']


# ════════════════════════════════════════════════════════════════════════════
# TODO 2 — PostV2Serializer
# ════════════════════════════════════════════════════════════════════════════
"""
V2 clients need richer data for analytics and better UX.
Fields to expose: id, title, status, likes_count, views_count,
                  read_time_minutes, excerpt, published_at

Fill in the Meta class:
  model = Post
  fields = ['id', 'title', 'status', 'likes_count', 'views_count',
            'read_time_minutes', 'excerpt', 'published_at']
"""

class PostV2Serializer(serializers.ModelSerializer):
    class Meta:
        pass  # TODO: Add model and fields for v2


# ════════════════════════════════════════════════════════════════════════════
# TODO 3 — VersionedPostListView.get_serializer_class()
# ════════════════════════════════════════════════════════════════════════════
"""
The view reads request.version and returns the correct serializer.

With QueryParameterVersioning:
  GET /api/lab/posts/?version=1  → request.version == '1'
  GET /api/lab/posts/?version=2  → request.version == '2'
  GET /api/lab/posts/            → request.version == None (default to v1)

Implement get_serializer_class():
  if self.request.version == '2':
      return PostV2Serializer
  return PostV1Serializer  # default
"""

class VersionedPostListView(ListAPIView):
    versioning_class = versioning.QueryParameterVersioning
    permission_classes = [AllowAny]

    def get_queryset(self):
        return Post.objects.filter(
            status='published',
            deleted_at__isnull=True,
        ).select_related('author', 'category')

    def get_serializer_class(self):
        raise NotImplementedError("TODO 3: Implement get_serializer_class()")


# ── URL patterns — override_settings(ROOT_URLCONF=...) points here ─────────
urlpatterns = [
    path('api/lab/posts/', VersionedPostListView.as_view(), name='lab-versioned-posts'),
]


# ════════════════════════════════════════════════════════════════════════════
# TESTS — Don't modify. They verify your TODOs.
# ════════════════════════════════════════════════════════════════════════════

# ── Unit tests: serializer field coverage ────────────────────────────────

@pytest.mark.django_db
def test_v1_serializer_has_exactly_three_fields():
    """PostV1Serializer should expose exactly 3 fields: id, title, status."""
    post = L2PostFactory()
    data = PostV1Serializer(post).data
    assert set(data.keys()) == {'id', 'title', 'status'}, (
        f"FAIL: v1 fields should be exactly {{id, title, status}}, "
        f"got {set(data.keys())}"
    )


@pytest.mark.django_db
def test_v2_serializer_has_extended_fields():
    """PostV2Serializer must include likes_count, views_count, excerpt, published_at."""
    post = L2PostFactory()
    data = PostV2Serializer(post).data
    required = {'id', 'title', 'status', 'likes_count', 'views_count',
                'read_time_minutes', 'excerpt'}
    missing = required - set(data.keys())
    assert not missing, f"FAIL: v2 serializer missing fields: {missing}"


@pytest.mark.django_db
def test_v1_does_not_leak_analytics_fields():
    """v1 must NOT return likes_count or views_count (save bandwidth for old clients)."""
    post = L2PostFactory()
    data = PostV1Serializer(post).data
    assert 'likes_count' not in data, \
        "FAIL: v1 should not expose likes_count — backward-compat risk"
    assert 'views_count' not in data, \
        "FAIL: v1 should not expose views_count"


# ── Unit test: view routing logic ─────────────────────────────────────────

@pytest.mark.django_db
def test_view_routes_version_2_to_v2_serializer():
    """get_serializer_class() returns PostV2Serializer for version='2'."""

    class MockRequest:
        version = '2'
        query_params = {}

    view = VersionedPostListView()
    view.request = MockRequest()
    view.format_kwarg = None
    assert view.get_serializer_class() == PostV2Serializer, \
        "FAIL: version='2' pe PostV2Serializer return hona chahiye"


@pytest.mark.django_db
def test_view_defaults_to_v1_serializer():
    """get_serializer_class() returns PostV1Serializer by default (version=None or '1')."""

    class MockRequest:
        version = None  # no version param
        query_params = {}

    view = VersionedPostListView()
    view.request = MockRequest()
    view.format_kwarg = None
    assert view.get_serializer_class() == PostV1Serializer, \
        "FAIL: default (no version) pe PostV1Serializer return hona chahiye"


# ── HTTP integration tests ────────────────────────────────────────────────

@pytest.mark.django_db
@override_settings(ROOT_URLCONF='labs.lab_02_api_versioning')
def test_http_v1_returns_minimal_fields():
    """?version=1 via HTTP → only 3 fields per post item."""
    L2PostFactory.create_batch(2)
    client = APIClient()
    response = client.get('/api/lab/posts/?version=1')
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"

    items = response.data.get('results', response.data)
    if isinstance(items, list) and items:
        item_keys = set(items[0].keys())
        assert item_keys == {'id', 'title', 'status'}, (
            f"FAIL: v1 HTTP response has unexpected fields: {item_keys}"
        )


@pytest.mark.django_db
@override_settings(ROOT_URLCONF='labs.lab_02_api_versioning')
def test_http_v2_returns_extended_fields():
    """?version=2 via HTTP → includes analytics fields."""
    L2PostFactory()
    client = APIClient()
    response = client.get('/api/lab/posts/?version=2')
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"

    items = response.data.get('results', response.data)
    if isinstance(items, list) and items:
        assert 'likes_count' in items[0], \
            "FAIL: v2 HTTP response missing likes_count"
        assert 'views_count' in items[0], \
            "FAIL: v2 HTTP response missing views_count"


@pytest.mark.django_db
@override_settings(ROOT_URLCONF='labs.lab_02_api_versioning')
def test_http_no_version_defaults_to_v1():
    """No version param → defaults to v1 (3 fields only)."""
    L2PostFactory()
    client = APIClient()
    response = client.get('/api/lab/posts/')
    assert response.status_code == 200

    items = response.data.get('results', response.data)
    if isinstance(items, list) and items:
        # Default = v1 → should NOT have analytics fields
        assert 'likes_count' not in items[0], \
            "FAIL: Default (no version) should use v1, but got likes_count"


# ═══════════════════════════════════════════════════════════════════════════
# SOCH — Answer ALOUD before moving to Lab 03
# ═══════════════════════════════════════════════════════════════════════════
#
#  Q1: QueryParameterVersioning, URLPathVersioning, AcceptHeaderVersioning —
#      production mein tum kaunsa use karoge?
#      URLPath: /api/v1/posts/ and /api/v2/posts/ (most common)
#      QueryParam: /api/posts/?version=2 (easier for clients)
#      AcceptHeader: Accept: application/json; version=2 (REST purist approach)
#
#  Q2: Request.version = None kab hota hai? Default version configure kaise karte hain?
#      Hint: DEFAULT_VERSION in REST_FRAMEWORK settings.
#
#  Q3: Ek field v1 se remove karna = breaking change?
#      (Yes — old clients crash. Instead: deprecate, then remove in v3)
#
#  Q4: 3 serializer versions maintain karna costly hai. Alternative kya hai?
#      Hint: SerializerMethodField + field exclusion based on version.
#
#  Q5: Interview script: "Aapne API versioning kaise ki hai?" — Bolte jao.
# ═══════════════════════════════════════════════════════════════════════════
