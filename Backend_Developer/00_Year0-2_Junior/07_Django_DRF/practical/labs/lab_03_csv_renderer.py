"""
Lab 03 — Custom DRF Renderer: CSV Export
═══════════════════════════════════════════════════════════════════════════════

CONTEXT: Clients want the same data in different formats.
         Finance teams want CSV. Mobile apps want JSON.
         DRF's content negotiation handles this via the Accept header.

GOAL: Build a CSVRenderer. Wire it into a view alongside JSONRenderer.
      The same endpoint returns JSON or CSV based on the client's Accept header.

HOW DRF CONTENT NEGOTIATION WORKS:
  1. Client sends: Accept: text/csv
  2. DRF matches 'text/csv' to CSVRenderer (via media_type)
  3. DRF calls renderer.render(data, ...)
  4. renderer returns bytes → response body

RUN:
    cd practical/
    pytest labs/lab_03_csv_renderer.py -v -p no:odoo

SOCH — Answer ALOUD after completing each TODO:
  Q1: Accept: */* pe DRF kaunsa renderer choose karega agar dono hain?
      (Hint: order of renderer_classes matters)
  Q2: render() ko string dene ki jagah bytes kyon dena padta hai?
  Q3: Paginated responses mein data ek dict hota hai {'results': [...], 'count': N}.
      Aapka render() yahan kya kare?
  Q4: CSV mein special characters (commas, newlines in titles) handle kaise hote hain?
      (csv.DictWriter automatically handles this — kaise?)
  Q5: Large exports (100K rows) ke liye CSVRenderer mein kya change karoge?
      (Hint: streaming response — StreamingHttpResponse)
"""

import csv
import io
import pytest
import factory
from factory.django import DjangoModelFactory
from django.contrib.auth import get_user_model
from django.test import override_settings
from django.urls import path
from django.utils import timezone

from rest_framework.permissions import AllowAny
from rest_framework.renderers import BaseRenderer, JSONRenderer
from rest_framework.response import Response
from rest_framework.test import APIClient
from rest_framework.views import APIView

from blog.models import Post, Category

User = get_user_model()


# ════════════════════════════════════════════════════════════════════════════
# FACTORIES (don't modify)
# ════════════════════════════════════════════════════════════════════════════

class L3UserFactory(DjangoModelFactory):
    class Meta:
        model = User
    email    = factory.Sequence(lambda n: f"l3user{n}@test.com")
    username = factory.Sequence(lambda n: f"l3user{n}")
    password = factory.PostGenerationMethodCall('set_password', 'pass123')


class L3CategoryFactory(DjangoModelFactory):
    class Meta:
        model = Category
    name = factory.Sequence(lambda n: f"L3Cat {n}")


class L3PostFactory(DjangoModelFactory):
    class Meta:
        model = Post
    title        = factory.Sequence(lambda n: f"L3 Post {n}")
    content      = "Content word " * 50
    excerpt      = "Short excerpt."
    author       = factory.SubFactory(L3UserFactory)
    category     = factory.SubFactory(L3CategoryFactory)
    status       = 'published'
    likes_count  = 10
    published_at = factory.LazyFunction(timezone.now)


# ════════════════════════════════════════════════════════════════════════════
# TODO 1 — CSVRenderer
# ════════════════════════════════════════════════════════════════════════════
"""
Implement a DRF renderer that produces CSV output.

Required class attributes (already set — don't change):
  media_type = 'text/csv'
  format = 'csv'

Implement render(self, data, accepted_media_type=None, renderer_context=None):

  data can be:
    - A list of dicts: [{'id': 1, 'title': 'Post A'}, ...]
    - A paginated dict: {'count': 2, 'results': [{...}, ...]}

  Steps:
    1. Resolve the actual rows:
         if isinstance(data, list):
             rows = data
         elif isinstance(data, dict) and 'results' in data:
             rows = data['results']
         else:
             rows = [data] if data else []

    2. If no rows, return b''

    3. Create buffer = io.StringIO()

    4. Get fieldnames from first row: fieldnames = list(rows[0].keys())

    5. writer = csv.DictWriter(buffer, fieldnames=fieldnames)
       writer.writeheader()
       writer.writerows(rows)

    6. return buffer.getvalue().encode('utf-8')
"""

class CSVRenderer(BaseRenderer):
    media_type = 'text/csv'
    format = 'csv'

    def render(self, data, accepted_media_type=None, renderer_context=None):
        raise NotImplementedError("TODO 1: Implement CSVRenderer.render()")


# ════════════════════════════════════════════════════════════════════════════
# TODO 2 — PostExportView
# ════════════════════════════════════════════════════════════════════════════
"""
A view that returns post data as JSON or CSV.
The client chooses via the Accept header.

Steps:
  1. Set renderer_classes = [JSONRenderer, CSVRenderer]
     (JSON first = default when Accept: */* or no header)

  2. Implement get(self, request):
       posts = Post.objects.filter(
           status='published',
           deleted_at__isnull=True,
       ).values('id', 'title', 'status', 'likes_count', 'views_count')
       return Response(list(posts))
"""

class PostExportView(APIView):
    permission_classes = [AllowAny]
    renderer_classes = []  # TODO: Set to [JSONRenderer, CSVRenderer]

    def get(self, request):
        raise NotImplementedError("TODO 2: Implement PostExportView.get()")


# ── URL patterns ──────────────────────────────────────────────────────────
urlpatterns = [
    path('api/lab/export/', PostExportView.as_view(), name='post-export'),
]


# ════════════════════════════════════════════════════════════════════════════
# TESTS — Don't modify. They verify your TODOs.
# ════════════════════════════════════════════════════════════════════════════

# ── Unit tests: CSVRenderer.render() in isolation ─────────────────────────

def test_render_returns_bytes():
    """render() must return bytes, not str."""
    renderer = CSVRenderer()
    data = [{'id': 1, 'title': 'Test', 'status': 'published'}]
    result = renderer.render(data)
    assert isinstance(result, bytes), \
        f"FAIL: render() bytes return kare, mila {type(result).__name__}"


def test_render_list_produces_correct_csv():
    """render() converts list of dicts to proper CSV with header + data rows."""
    renderer = CSVRenderer()
    data = [
        {'id': 1, 'title': 'First Post', 'status': 'published', 'likes': 10},
        {'id': 2, 'title': 'Second Post', 'status': 'draft',     'likes': 0},
    ]
    result = renderer.render(data)
    text = result.decode('utf-8')
    reader = csv.DictReader(io.StringIO(text))
    rows = list(reader)
    assert len(rows) == 2, f"FAIL: 2 data rows chahiye, mila {len(rows)}"
    assert rows[0]['title'] == 'First Post', \
        f"FAIL: First row title galat: {rows[0]['title']}"
    assert rows[1]['status'] == 'draft', \
        f"FAIL: Second row status galat: {rows[1]['status']}"


def test_render_has_header_row():
    """CSV output ka pehla row header hona chahiye."""
    renderer = CSVRenderer()
    data = [{'id': 1, 'title': 'Post', 'likes_count': 5}]
    text = renderer.render(data).decode('utf-8')
    reader = csv.reader(io.StringIO(text))
    headers = next(reader)
    assert 'id' in headers,          "FAIL: CSV header mein 'id' nahi"
    assert 'title' in headers,       "FAIL: CSV header mein 'title' nahi"
    assert 'likes_count' in headers, "FAIL: CSV header mein 'likes_count' nahi"


def test_render_handles_paginated_dict():
    """render() paginated {'count': N, 'results': [...]} data ko handle kare."""
    renderer = CSVRenderer()
    data = {
        'count': 2,
        'next': None,
        'results': [
            {'id': 1, 'title': 'Post A'},
            {'id': 2, 'title': 'Post B'},
        ]
    }
    result = renderer.render(data)
    text = result.decode('utf-8')
    reader = csv.DictReader(io.StringIO(text))
    rows = list(reader)
    assert len(rows) == 2, \
        f"FAIL: Paginated data se 2 rows chahiye, mila {len(rows)}"


def test_render_empty_data_returns_empty_bytes():
    """render([]) returns b'' (empty bytes)."""
    renderer = CSVRenderer()
    result = renderer.render([])
    assert result == b'', \
        f"FAIL: Empty list pe b'' return hona chahiye, mila {result!r}"


# ── HTTP integration tests ─────────────────────────────────────────────────

@pytest.mark.django_db
@override_settings(ROOT_URLCONF='labs.lab_03_csv_renderer')
def test_json_when_accept_json():
    """Accept: application/json → JSON response."""
    L3PostFactory.create_batch(2)
    client = APIClient()
    response = client.get('/api/lab/export/', HTTP_ACCEPT='application/json')
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    content_type = response.get('Content-Type', '')
    assert 'application/json' in content_type, \
        f"FAIL: JSON accept pe application/json content-type chahiye, mila: {content_type}"


@pytest.mark.django_db
@override_settings(ROOT_URLCONF='labs.lab_03_csv_renderer')
def test_csv_when_accept_csv():
    """Accept: text/csv → CSV response with correct content type."""
    L3PostFactory.create_batch(3)
    client = APIClient()
    response = client.get('/api/lab/export/', HTTP_ACCEPT='text/csv')
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    content_type = response.get('Content-Type', '')
    assert 'text/csv' in content_type, \
        f"FAIL: CSV accept pe text/csv chahiye, mila: {content_type}"


@pytest.mark.django_db
@override_settings(ROOT_URLCONF='labs.lab_03_csv_renderer')
def test_csv_contains_all_posts():
    """CSV export mein sab published posts honein chahiye."""
    L3PostFactory.create_batch(4)
    client = APIClient()
    response = client.get('/api/lab/export/', HTTP_ACCEPT='text/csv')
    assert response.status_code == 200

    text = response.content.decode('utf-8')
    reader = csv.reader(io.StringIO(text))
    rows = list(reader)
    # Header + 4 data rows
    assert len(rows) >= 5, \
        f"FAIL: CSV mein header + 4 data rows chahiye, mila {len(rows)} rows"


@pytest.mark.django_db
@override_settings(ROOT_URLCONF='labs.lab_03_csv_renderer')
def test_json_is_default_format():
    """No Accept header → JSON (first renderer = default)."""
    L3PostFactory()
    client = APIClient()
    response = client.get('/api/lab/export/')
    assert response.status_code == 200
    content_type = response.get('Content-Type', '')
    assert 'application/json' in content_type or 'text/csv' in content_type, \
        "FAIL: Response kisi valid format mein nahi"
    # If JSON: data should be parseable
    if 'application/json' in content_type:
        assert isinstance(response.json(), list), \
            "FAIL: JSON response list honi chahiye"


# ═══════════════════════════════════════════════════════════════════════════
# SOCH — Answer ALOUD before moving to Lab 04
# ═══════════════════════════════════════════════════════════════════════════
#
#  Q1: renderer_classes = [JSONRenderer, CSVRenderer] — order matter karta hai.
#      Agar client Accept: */* bheje, kaunsa renderer pick hoga?
#      (First one — JSONRenderer. Always put your default renderer first.)
#
#  Q2: render() ko bytes kyon dena padta hai, str kyon nahi?
#      (HTTP response body = bytes. Django automatically nahi karega encode.)
#
#  Q3: Comma wala title: "Hello, World" CSV mein kaise safe hota hai?
#      (csv.DictWriter automatically quotes fields with commas — try it.)
#
#  Q4: 100,000 rows export karna ho toh CSVRenderer kya problem create karega?
#      (Memory — sab rows ek saath memory mein load honge. Fix: StreamingHttpResponse.)
#
#  Q5: Interview mein: "Aapne multi-format export implement kiya hai kabhi?"
#      Ab bolo — implementation approach, tradeoffs, and production consideration.
# ═══════════════════════════════════════════════════════════════════════════
