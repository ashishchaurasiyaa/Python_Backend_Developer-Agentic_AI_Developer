"""
DRF Content Negotiation — Production Patterns

Renderers pick the response format (driven by `Accept`), parsers pick the
accepted request format (driven by `Content-Type`). See 43_drf_content_negotiation.md.
"""

# ==========================================================================
# 1. SETTINGS — default renderers (dev vs prod)
# ==========================================================================

REST_FRAMEWORK_NEGOTIATION_SETTINGS = """
# settings/base.py — dev-friendly, browsable API on
REST_FRAMEWORK = {
    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',
        'rest_framework.renderers.BrowsableAPIRenderer',
    ],
    'DEFAULT_PARSER_CLASSES': [
        'rest_framework.parsers.JSONParser',
        'rest_framework.parsers.MultiPartParser',
        'rest_framework.parsers.FormParser',
    ],
}

# settings/prod.py — strip BrowsableAPIRenderer, JSON only
REST_FRAMEWORK['DEFAULT_RENDERER_CLASSES'] = [
    'rest_framework.renderers.JSONRenderer',
]
"""


# ==========================================================================
# 2. CUSTOM RENDERER — CSV export
# ==========================================================================

from rest_framework.renderers import BaseRenderer
import csv
import io


class CSVRenderer(BaseRenderer):
    """Client opts in via `Accept: text/csv` or `?format=csv`."""

    media_type = 'text/csv'
    format = 'csv'
    charset = 'utf-8'

    def render(self, data, accepted_media_type=None, renderer_context=None):
        rows = data if isinstance(data, list) else [data]
        buf = io.StringIO()
        fieldnames = list(rows[0].keys()) if rows else []
        writer = csv.DictWriter(buf, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
        return buf.getvalue()


# ==========================================================================
# 3. VIEW WITH MULTIPLE RENDERERS — format suffix + Accept header both work
# ==========================================================================

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.renderers import JSONRenderer, BrowsableAPIRenderer


class ReportExportView(APIView):
    """
    GET /api/reports/?format=csv   → CSVRenderer
    GET /api/reports/ + Accept: text/csv → CSVRenderer
    GET /api/reports/               → JSONRenderer (default, first in list)
    """

    renderer_classes = [JSONRenderer, CSVRenderer, BrowsableAPIRenderer]

    def get(self, request):
        rows = [
            {'id': 1, 'name': 'Alpha', 'total': 120},
            {'id': 2, 'name': 'Beta', 'total': 340},
        ]
        return Response(rows)


# ==========================================================================
# 4. FORCE JSON-ONLY ON A SENSITIVE VIEW — no browsable API leak
# ==========================================================================

class PaymentWebhookView(APIView):
    """Webhooks are machine-to-machine — no HTML form UI needed or wanted."""

    renderer_classes = [JSONRenderer]
    parser_classes = None  # keep default JSON/MultiPart/Form parsers

    def post(self, request):
        return Response({'received': True})


# ==========================================================================
# 5. CUSTOM CONTENT NEGOTIATION — ignore Accept header, always use first renderer
# ==========================================================================

from rest_framework.negotiation import BaseContentNegotiation


class IgnoreClientContentNegotiation(BaseContentNegotiation):
    """
    Use when a gateway/proxy in front of Django already normalizes Accept
    headers and you want the API itself to be deterministic regardless of
    what a misbehaving client sends.
    """

    def select_parser(self, request, parsers):
        return parsers[0]

    def select_renderer(self, request, renderers, format_suffix):
        return renderers[0], renderers[0].media_type


class DeterministicView(APIView):
    content_negotiation_class = IgnoreClientContentNegotiation
    renderer_classes = [JSONRenderer]

    def get(self, request):
        return Response({'ok': True})


# ==========================================================================
# 6. VERSION + FORMAT COMBINED — Accept: application/json; version=2.0
# ==========================================================================

"""
# settings.py
REST_FRAMEWORK['DEFAULT_VERSIONING_CLASS'] = 'rest_framework.versioning.AcceptHeaderVersioning'

# Client sends:
# Accept: application/json; version=2.0

# request.version == '2.0' inside the view — negotiation (format) and
# versioning (representation) are resolved independently from the SAME header.
# See 26_drf_api_versioning.md for the versioning side of this.
"""


# ==========================================================================
# 7. TESTING NEGOTIATION — 415 on unsupported Content-Type, format suffix
# ==========================================================================

"""
# tests/test_content_negotiation.py
from rest_framework.test import APITestCase
from rest_framework import status


class ContentNegotiationTests(APITestCase):
    def test_default_json(self):
        response = self.client.get('/api/reports/')
        self.assertEqual(response['Content-Type'], 'application/json')

    def test_csv_via_accept_header(self):
        response = self.client.get('/api/reports/', HTTP_ACCEPT='text/csv')
        self.assertEqual(response['Content-Type'], 'text/csv; charset=utf-8')
        self.assertIn('Alpha', response.content.decode())

    def test_csv_via_format_suffix(self):
        response = self.client.get('/api/reports/?format=csv')
        self.assertIn('text/csv', response['Content-Type'])

    def test_unregistered_content_type_returns_415(self):
        response = self.client.post(
            '/api/reports/', data='<xml/>', content_type='application/xml',
        )
        self.assertEqual(response.status_code, status.HTTP_415_UNSUPPORTED_MEDIA_TYPE)

    def test_unacceptable_media_type_returns_406(self):
        response = self.client.get('/api/reports/', HTTP_ACCEPT='application/pdf')
        self.assertEqual(response.status_code, status.HTTP_406_NOT_ACCEPTABLE)
"""


# ==========================================================================
# 8. GOTCHA — BrowsableAPIRenderer swallows Accept: */* as a browser default
# ==========================================================================

BROWSABLE_API_GOTCHA = """
A plain browser tab sends `Accept: text/html,application/xhtml+xml,...`
DRF's negotiation walks your renderer list and the FIRST renderer whose
media_type matches ANY part of that Accept header wins — if
BrowsableAPIRenderer is anywhere in DEFAULT_RENDERER_CLASSES, browser
requests silently get HTML instead of JSON, which surprises people testing
an endpoint by pasting the URL into a browser and then wondering why a
`curl` from a JSON client behaves differently. Nothing is broken — it's
negotiation working exactly as designed on two different Accept headers.
"""
