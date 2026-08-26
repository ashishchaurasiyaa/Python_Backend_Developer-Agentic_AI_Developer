"""
Lab 05 — DRF Throttling: Rate Limiting
═══════════════════════════════════════════════════════════════════════════════

CONTEXT: Public API ka abuse rokna zaroori hai.
  - Anonymous users: 3 requests/minute (demo limit — production mein 60+)
  - Authenticated users: 30 requests/minute
  - Premium users: 200 requests/minute

DRF THROTTLE FLOW:
  1. Request aata hai → view's throttle_classes check hote hain
  2. Har throttle class check_throttle(request, view) call karti hai
  3. Agar any throttle fail kare → 429 Too Many Requests
  4. Cache key = throttle scope + user identifier (IP for anon, user.pk for auth)
  5. Remaining count cache mein store hota hai

HOW SCOPE WORKS:
  throttle.scope = 'guest_browse'
  settings.REST_FRAMEWORK['DEFAULT_THROTTLE_RATES']['guest_browse'] = '3/minute'
  → LocMemCache (ya Redis) mein key: throttle_guest_browse_<IP>
  → 3 hits mein count 3 ho, 4th hit pe 429

RUN:
    cd practical/
    pytest labs/lab_05_throttling.py -v -p no:odoo

NOTE: Tests override CACHES to use LocMemCache (no Redis needed).
      Each test clears cache in fixture to avoid inter-test state leakage.

SOCH — Answer ALOUD after completing each TODO:
  Q1: Throttle cache key mein user identifier kya hota hai?
      (Anon: IP address. Auth: user.pk. Why? To throttle per-user not per-server)
  Q2: AnonRateThrottle vs UserRateThrottle — kaunsa phele check hoga agar dono lage?
      (Both check, both must pass — ko OR nahi, AND hai)
  Q3: Rate limit headers client ko return karna best practice hai — kaunse headers?
      (X-RateLimit-Limit, X-RateLimit-Remaining, X-RateLimit-Reset, Retry-After)
  Q4: Redis vs LocMemCache for throttling — production mein kya use karoge?
      (Redis — LocMemCache per-process hai, multiple dynos/workers pe work nahi karta)
  Q5: Sliding window vs fixed window rate limiting — DRF kaunsa use karta hai?
      (Sliding window — parse_rate() + cache key TTL = window duration)
"""

import pytest
import factory
from factory.django import DjangoModelFactory
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import override_settings
from django.urls import path

from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.test import APIClient
from rest_framework.throttling import AnonRateThrottle, UserRateThrottle
from rest_framework.views import APIView

User = get_user_model()


# ════════════════════════════════════════════════════════════════════════════
# FACTORIES (don't modify)
# ════════════════════════════════════════════════════════════════════════════

class L5UserFactory(DjangoModelFactory):
    class Meta:
        model = User
    email    = factory.Sequence(lambda n: f"l5user{n}@test.com")
    username = factory.Sequence(lambda n: f"l5user{n}")
    password = factory.PostGenerationMethodCall('set_password', 'pass123')


# ════════════════════════════════════════════════════════════════════════════
# TODO 1 — GuestBrowseThrottle
# ════════════════════════════════════════════════════════════════════════════
"""
Anonymous users get 3 requests per minute (demo; production = 60+).

Steps:
  class GuestBrowseThrottle(AnonRateThrottle):
      scope = 'guest_browse'

That's it. AnonRateThrottle handles:
  - Cache key = 'throttle_guest_browse_<IP>'
  - Rate parsing from DEFAULT_THROTTLE_RATES['guest_browse']
  - allow_request() increment + check logic
"""

class GuestBrowseThrottle(AnonRateThrottle):
    scope = None  # TODO 1: Set scope = 'guest_browse'


# ════════════════════════════════════════════════════════════════════════════
# TODO 2 — AuthenticatedUserThrottle
# ════════════════════════════════════════════════════════════════════════════
"""
Authenticated users get 10 requests per minute (demo limit).

Steps:
  class AuthenticatedUserThrottle(UserRateThrottle):
      scope = 'authenticated'

UserRateThrottle uses user.pk as the cache key identifier (not IP).
"""

class AuthenticatedUserThrottle(UserRateThrottle):
    scope = None  # TODO 2: Set scope = 'authenticated'


# ════════════════════════════════════════════════════════════════════════════
# TODO 3 — PublicPostView
# ════════════════════════════════════════════════════════════════════════════
"""
A view that applies GuestBrowseThrottle to anonymous users.

Steps:
  class PublicPostView(APIView):
      permission_classes = [AllowAny]
      throttle_classes = [GuestBrowseThrottle]

      def get(self, request):
          return Response({'status': 'ok', 'user': str(request.user)})
"""

class PublicPostView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = []   # TODO 3: Add GuestBrowseThrottle

    def get(self, request):
        return Response({'status': 'ok', 'user': str(request.user)})


# ── URL patterns ──────────────────────────────────────────────────────────
urlpatterns = [
    path('api/lab/public/', PublicPostView.as_view(), name='public-posts'),
]


# ── Settings override used by all tests ──────────────────────────────────
THROTTLE_SETTINGS = {
    'DEFAULT_THROTTLE_RATES': {
        'guest_browse':  '3/minute',   # low for testing
        'authenticated': '10/minute',
    }
}


# ════════════════════════════════════════════════════════════════════════════
# Fixture: clear cache between tests so throttle counts don't bleed over
# ════════════════════════════════════════════════════════════════════════════

@pytest.fixture(autouse=True)
def clear_throttle_cache():
    cache.clear()
    yield
    cache.clear()


# ════════════════════════════════════════════════════════════════════════════
# TESTS — Don't modify. They verify your TODOs.
# ════════════════════════════════════════════════════════════════════════════

# ── Scope name tests (instant pass/fail, no HTTP needed) ──────────────────

def test_guest_throttle_scope_name():
    """GuestBrowseThrottle.scope must be 'guest_browse'."""
    assert GuestBrowseThrottle.scope == 'guest_browse', (
        f"FAIL: GuestBrowseThrottle.scope = {GuestBrowseThrottle.scope!r}, "
        "expected 'guest_browse'"
    )


def test_auth_throttle_scope_name():
    """AuthenticatedUserThrottle.scope must be 'authenticated'."""
    assert AuthenticatedUserThrottle.scope == 'authenticated', (
        f"FAIL: AuthenticatedUserThrottle.scope = {AuthenticatedUserThrottle.scope!r}, "
        "expected 'authenticated'"
    )


def test_public_view_has_guest_throttle():
    """PublicPostView.throttle_classes mein GuestBrowseThrottle hona chahiye."""
    assert GuestBrowseThrottle in PublicPostView.throttle_classes, (
        "FAIL: PublicPostView.throttle_classes mein GuestBrowseThrottle nahi. "
        "TODO 3 check karo."
    )


# ── HTTP throttle behaviour tests ─────────────────────────────────────────

@pytest.mark.django_db
@override_settings(
    ROOT_URLCONF='labs.lab_05_throttling',
    REST_FRAMEWORK=THROTTLE_SETTINGS,
    CACHES={'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}},
)
def test_first_three_requests_allowed():
    """Limit ke andar requests (1, 2, 3) → 200 OK."""
    client = APIClient()
    for i in range(1, 4):
        r = client.get('/api/lab/public/')
        assert r.status_code == 200, (
            f"FAIL: Request {i} ko 200 chahiye tha, mila {r.status_code}. "
            "throttle_classes sahi set hai?"
        )


@pytest.mark.django_db
@override_settings(
    ROOT_URLCONF='labs.lab_05_throttling',
    REST_FRAMEWORK=THROTTLE_SETTINGS,
    CACHES={'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}},
)
def test_fourth_request_is_throttled():
    """Limit exhaust hone ke baad 4th request → 429."""
    client = APIClient()
    for _ in range(3):
        client.get('/api/lab/public/')
    r = client.get('/api/lab/public/')
    assert r.status_code == 429, (
        f"FAIL: 4th request pe 429 (Too Many Requests) chahiye, mila {r.status_code}. "
        "Kya PublicPostView.throttle_classes mein GuestBrowseThrottle hai? "
        "Kya scope = 'guest_browse' set hai?"
    )


@pytest.mark.django_db
@override_settings(
    ROOT_URLCONF='labs.lab_05_throttling',
    REST_FRAMEWORK=THROTTLE_SETTINGS,
    CACHES={'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}},
)
def test_retry_after_header_in_429_response():
    """429 response mein Retry-After header hona chahiye."""
    client = APIClient()
    for _ in range(3):
        client.get('/api/lab/public/')
    r = client.get('/api/lab/public/')
    if r.status_code == 429:
        assert 'Retry-After' in r, \
            "FAIL: 429 response mein Retry-After header nahi. DRF default mein deta hai."


@pytest.mark.django_db
@override_settings(
    ROOT_URLCONF='labs.lab_05_throttling',
    REST_FRAMEWORK=THROTTLE_SETTINGS,
    CACHES={'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}},
)
def test_different_ips_have_separate_counters():
    """
    IP A limit exhaust kare toh IP B ka counter independent rehna chahiye.
    AnonRateThrottle IP-based caching use karta hai.
    """
    ip_a = '10.0.0.1'
    ip_b = '10.0.0.2'

    client_a = APIClient()
    client_b = APIClient()

    # IP A apna limit exhaust kare
    for _ in range(3):
        client_a.get('/api/lab/public/', REMOTE_ADDR=ip_a)
    r_a = client_a.get('/api/lab/public/', REMOTE_ADDR=ip_a)
    assert r_a.status_code == 429, "Setup check: IP A throttled honi chahiye"

    # IP B ka fresh counter hona chahiye
    r_b = client_b.get('/api/lab/public/', REMOTE_ADDR=ip_b)
    assert r_b.status_code == 200, (
        f"FAIL: IP B ko throttle nahi hona chahiye, mila {r_b.status_code}. "
        "AnonRateThrottle IP-based caching se ye automatic hona chahiye."
    )


@pytest.mark.django_db
@override_settings(
    ROOT_URLCONF='labs.lab_05_throttling',
    REST_FRAMEWORK=THROTTLE_SETTINGS,
    CACHES={'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}},
)
def test_authenticated_user_not_throttled_by_guest_throttle():
    """
    GuestBrowseThrottle sirf ANONYMOUS users ko throttle karta hai.
    Authenticated user should not be blocked by this throttle.
    (AnonRateThrottle.get_cache_key() returns None for authenticated users
     → allow_request() returns True → not throttled)
    """
    user = L5UserFactory()
    auth_client = APIClient()
    auth_client.force_authenticate(user=user)

    # Exhaust anon limit (but we're authenticated — should not matter)
    for _ in range(5):
        r = auth_client.get('/api/lab/public/')
        assert r.status_code == 200, (
            f"FAIL: Authenticated user request {_ + 1} throttled ({r.status_code}). "
            "AnonRateThrottle authenticated users ko throttle nahi karta."
        )


# ═══════════════════════════════════════════════════════════════════════════
# SOCH — Answer ALOUD after completing all labs
# ═══════════════════════════════════════════════════════════════════════════
#
#  Q1: AnonRateThrottle ka cache key kya hota hai?
#      (f"throttle_{scope}_{ip_address}")
#      UserRateThrottle ka cache key kya hota hai?
#      (f"throttle_{scope}_{user.pk}")
#
#  Q2: Production mein LocMemCache kyon wrong hai throttling ke liye?
#      (Multiple workers = separate memory = per-worker limits, not per-user)
#      Solution? (Redis — shared, atomic INCR)
#
#  Q3: Per-endpoint alag throttle lagana ho, jaise upload API pe 5/hour?
#      (Custom throttle class + apply per-view: throttle_classes = [...])
#
#  Q4: Client ko rate limit info kaise dikhao?
#      Headers: X-RateLimit-Limit, X-RateLimit-Remaining, X-RateLimit-Reset
#      DRF default mein sirf Retry-After bhejta hai 429 pe.
#      Full headers ke liye: custom throttle + override throttled() method.
#
#  Q5: Interview mein: "Aapne rate limiting implement ki hai?" — Ab bolo approach,
#      scope naming, Redis choice, production gotchas.
# ═══════════════════════════════════════════════════════════════════════════
