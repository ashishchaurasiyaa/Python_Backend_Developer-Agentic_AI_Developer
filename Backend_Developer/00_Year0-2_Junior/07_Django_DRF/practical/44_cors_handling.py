"""
CORS Handling — Production Patterns

pip install django-cors-headers
See 44_cors_handling.md for the full explanation of preflight/credentials/CSRF interaction.
"""

# ==========================================================================
# 1. SETTINGS — explicit allowlist (recommended over CORS_ALLOW_ALL_ORIGINS)
# ==========================================================================

CORS_SETTINGS = """
# settings.py
INSTALLED_APPS = [
    'corsheaders',
    # ...
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',      # HIGH in the list —
    'django.middleware.common.CommonMiddleware',  # before CommonMiddleware,
    'django.middleware.security.SecurityMiddleware',
    # ...
]

CORS_ALLOWED_ORIGINS = [
    'https://app.example.com',
    'https://staging.example.com',
]

# Cookie/session auth across origins needs BOTH of these:
CORS_ALLOW_CREDENTIALS = True
CSRF_TRUSTED_ORIGINS = [
    'https://app.example.com',
]

CORS_ALLOW_METHODS = ['GET', 'POST', 'PATCH', 'DELETE']
CORS_ALLOW_HEADERS = ['accept', 'authorization', 'content-type', 'x-csrftoken']
CORS_EXPOSE_HEADERS = ['X-Total-Count']   # custom headers JS is allowed to read
CORS_PREFLIGHT_MAX_AGE = 86400            # cache preflight result 24h
"""


# ==========================================================================
# 2. PER-TENANT WILDCARD SUBDOMAINS — regex allowlist, tightly anchored
# ==========================================================================

CORS_REGEX_SETTINGS = """
# settings.py — {tenant}.app.example.com, any tenant
CORS_ALLOWED_ORIGIN_REGEXES = [
    r'^https://[\\w-]+\\.app\\.example\\.com$',   # anchored + literal dot escaped
]
# WRONG (too loose — unescaped '.' matches ANY char, could match
# https://evilXapp0example0com if an attacker controls DNS/hosts creatively):
#   r'^https://.*\\.app\\.example\\.com$'
"""


# ==========================================================================
# 3. A VIEW BEHIND CORS — nothing special needed in the view itself,
#    CorsMiddleware handles the headers; this just shows what the client sees
# ==========================================================================

from rest_framework.views import APIView
from rest_framework.response import Response


class OrdersView(APIView):
    """Consumed cross-origin by app.example.com. No CORS-specific code here —
    it's entirely a middleware + settings concern."""

    def get(self, request):
        response = Response(
            [{'id': 1, 'total': 499}, {'id': 2, 'total': 120}]
        )
        response['X-Total-Count'] = '2'   # needs CORS_EXPOSE_HEADERS to be JS-readable
        return response


# ==========================================================================
# 4. VERIFYING CORS HEADERS SERVER-SIDE — no real browser needed
# ==========================================================================

"""
# tests/test_cors.py
# Django's test client doesn't enforce Same-Origin Policy (nothing does
# outside a real browser), but CorsMiddleware still attaches headers based
# on the Origin header you send — so you CAN assert the headers themselves
# without needing a browser or Selenium/Playwright.

from rest_framework.test import APITestCase


class CORSHeaderTests(APITestCase):
    def test_allowed_origin_gets_acao_header(self):
        response = self.client.get(
            '/api/orders/', HTTP_ORIGIN='https://app.example.com',
        )
        self.assertEqual(
            response['Access-Control-Allow-Origin'], 'https://app.example.com',
        )

    def test_disallowed_origin_gets_no_acao_header(self):
        response = self.client.get(
            '/api/orders/', HTTP_ORIGIN='https://evil.com',
        )
        # Server still processes and returns 200 — CorsMiddleware just
        # withholds the header. A REAL browser would then refuse to hand
        # this response to JS. This is the exact "works in Postman, fails
        # in browser" gap from the theory doc's Why It Matters section.
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('Access-Control-Allow-Origin', response)

    def test_preflight_options_request(self):
        response = self.client.options(
            '/api/orders/1/',
            HTTP_ORIGIN='https://app.example.com',
            HTTP_ACCESS_CONTROL_REQUEST_METHOD='PATCH',
            HTTP_ACCESS_CONTROL_REQUEST_HEADERS='content-type, authorization',
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn('PATCH', response['Access-Control-Allow-Methods'])

    def test_expose_headers_lists_custom_header(self):
        response = self.client.get(
            '/api/orders/', HTTP_ORIGIN='https://app.example.com',
        )
        self.assertIn('X-Total-Count', response['Access-Control-Expose-Headers'])

    def test_credentials_echoes_specific_origin_not_wildcard(self):
        # With CORS_ALLOW_CREDENTIALS=True, django-cors-headers must NEVER
        # return '*' — it has to echo the specific matched origin, per spec.
        response = self.client.get(
            '/api/orders/', HTTP_ORIGIN='https://app.example.com',
        )
        self.assertEqual(response['Access-Control-Allow-Credentials'], 'true')
        self.assertNotEqual(response['Access-Control-Allow-Origin'], '*')
"""


# ==========================================================================
# 5. MIDDLEWARE ORDERING BUG — reproduce it, then fix it
# ==========================================================================

MIDDLEWARE_ORDERING_BUG = """
# BROKEN — CorsMiddleware after CommonMiddleware
MIDDLEWARE = [
    'django.middleware.common.CommonMiddleware',   # APPEND_SLASH redirect
    'corsheaders.middleware.CorsMiddleware',        # never reached on redirect
]
# Symptom: preflight (OPTIONS) succeeds, but the REAL request to a URL
# missing a trailing slash gets redirected by CommonMiddleware BEFORE
# CorsMiddleware attaches Access-Control-Allow-Origin — browser blocks the
# redirected response, error looks identical to a bad allowlist entry.

# FIXED — CorsMiddleware first
MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.common.CommonMiddleware',
]
"""


# ==========================================================================
# 6. TOKEN AUTH vs COOKIE AUTH — what CORS config each actually needs
# ==========================================================================

AUTH_MODE_COMPARISON = """
Token/JWT auth (Authorization: Bearer <token>):
  - CORS_ALLOW_CREDENTIALS: not needed (no cookie involved)
  - CSRF_TRUSTED_ORIGINS:   not needed (no ambient cookie for CSRF to exploit)
  - Still need:             CORS_ALLOWED_ORIGINS (browser still gates JS read access)

Session/cookie auth across origins:
  - CORS_ALLOW_CREDENTIALS: True (browser must be told to send/receive cookies)
  - Client fetch():         credentials: 'include'
  - CSRF_TRUSTED_ORIGINS:   required (see 16_security_hardening.md)
  - CORS_ALLOWED_ORIGINS:   must be an explicit list — '*' is REJECTED by
                            browsers when credentials are involved
"""
