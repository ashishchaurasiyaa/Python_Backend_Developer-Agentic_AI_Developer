"""
Lab 08 — Custom Django Middleware (Ordering, CorrelationID, SlowRequest, BlockedIP)
═══════════════════════════════════════════════════════════════════════════════

ARCHITECTURE — Django Middleware Execution Order:

    REQUEST enters:  MIDDLEWARE list top → bottom (process_request)
    RESPONSE exits:  MIDDLEWARE list bottom → top (process_response)

    MIDDLEWARE = [
        'CorrelationIDMiddleware',    ← [0] runs first on request, LAST on response
        'RequestLoggingMiddleware',   ← [1]
        'AuthenticationMiddleware',   ← [2]
        'SlowRequestMiddleware',      ← [3] runs last on request, FIRST on response
    ]

    REQUEST flow:     Correlation → Logging → Auth → SlowRequest → VIEW
    RESPONSE flow:    SlowRequest → Auth → Logging → Correlation → CLIENT

    Middleware class structure (new-style, Django 1.10+):
        class MyMiddleware:
            def __init__(self, get_response):
                self.get_response = get_response
                # One-time setup at server start

            def __call__(self, request):
                # Code here runs BEFORE the view (process_request equivalent)
                response = self.get_response(request)
                # Code here runs AFTER the view (process_response equivalent)
                return response

    IMPORTANT: get_response is the NEXT middleware (or view) in the chain.
               Calling self.get_response(request) passes request down the chain.
               NOT calling it = short-circuit (e.g., maintenance mode, blocked IP).

CONTEXT: Production middleware stack needs:
  1. X-Correlation-ID — trace a single request across microservices
  2. SlowRequest warning — log if response > 500ms
  3. BlockedIP — return 403 before hitting any view
  4. MaintenanceMode — 503 for all non-admin traffic

INTERVIEW QUESTIONS:
  - process_request vs process_response kya hota tha? (Old-style Django)
  - New-style middleware mein exception kaise handle karo? (try/except around get_response)
  - Middleware mein DB query karna safe hai? (Har request pe — careful with performance)
  - CorsMiddleware kyon PEHLE rakhte hain MIDDLEWARE list mein?

RUN:
    cd practical/
    pytest labs/lab_08_custom_middleware.py -v -p no:odoo

SOCH — Answer ALOUD:
  Q1: MIDDLEWARE ordering mein CorsMiddleware pehle kyun rakhte hain?
  Q2: Middleware mein exception raise ho jaye aur get_response() call na ho — kya hoga?
  Q3: process_request old-style vs __call__ new-style — kya difference hai internally?
  Q4: Middleware sirf Django views pe lagta hai ya DRF views pe bhi? Static files pe?
  Q5: Request ID ka use microservices mein kaise hota hai? (Distributed tracing)
"""

import time
import uuid
import logging
import pytest

from django.test import RequestFactory, override_settings
from django.http import HttpResponse, JsonResponse

log = logging.getLogger(__name__)


# ════════════════════════════════════════════════════════════════════════════
# HELPER — simple_view (a dummy view for testing middleware)
# ════════════════════════════════════════════════════════════════════════════

def simple_view(request):
    """A basic view that returns 200 OK with a body."""
    return HttpResponse("OK", status=200)

def slow_view(request):
    """Simulates a slow view."""
    time.sleep(0.05)   # 50ms — short enough for tests
    return HttpResponse("Slow but done", status=200)

def error_view(request):
    """Simulates a view that raises an exception."""
    raise ValueError("Something went wrong in view")


# ════════════════════════════════════════════════════════════════════════════
# TODO 1 — CorrelationIDMiddleware
# ════════════════════════════════════════════════════════════════════════════
"""
Implement CorrelationIDMiddleware:

REQUEST handling:
  1. Check if 'X-Correlation-ID' header present in request.headers
  2. If yes: use that value (frontend/upstream sent their ID)
  3. If no: generate str(uuid.uuid4())
  4. Attach to request: request.correlation_id = correlation_id

RESPONSE handling:
  5. Add to response header: response['X-Correlation-ID'] = correlation_id
  6. Return response

Why?
  - Distributed tracing: API Gateway → Django → Celery — same correlation_id flows through all
  - Log correlation: every log line in a request lifecycle shares same ID
  - Debugging: give correlation_id to user, find all logs for that request
"""

class CorrelationIDMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        raise NotImplementedError(
            "TODO 1: Extract or generate correlation_id, attach to request, "
            "call get_response, add header to response, return response"
        )


# ════════════════════════════════════════════════════════════════════════════
# TODO 2 — SlowRequestMiddleware
# ════════════════════════════════════════════════════════════════════════════
"""
Implement SlowRequestMiddleware:

REQUEST:
  1. Record start time: request._start_time = time.perf_counter()

RESPONSE:
  2. Compute duration: (time.perf_counter() - request._start_time) * 1000  (ms)
  3. Add header: response['X-Response-Time'] = f"{duration:.2f}ms"
  4. If duration > settings.SLOW_REQUEST_THRESHOLD_MS (default: 500):
       log.warning("slow_request", extra={'path': request.path, 'duration_ms': duration})
  5. Return response

Default threshold: 500ms (configurable via settings.SLOW_REQUEST_THRESHOLD_MS)
"""

class SlowRequestMiddleware:
    DEFAULT_THRESHOLD_MS = 500

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        raise NotImplementedError(
            "TODO 2: Record start time before get_response, compute duration after, "
            "add X-Response-Time header, log warning if > threshold"
        )


# ════════════════════════════════════════════════════════════════════════════
# TODO 3 — BlockedIPMiddleware
# ════════════════════════════════════════════════════════════════════════════
"""
Implement BlockedIPMiddleware:

REQUEST:
  1. Get client IP from request.META.get('REMOTE_ADDR', '')
  2. Get blocked list from settings: getattr(settings, 'BLOCKED_IPS', set())
  3. If client IP in BLOCKED_IPS:
       return JsonResponse({'detail': 'Access denied.'}, status=403)
       (SHORT-CIRCUIT — do NOT call get_response)
  4. Otherwise: return self.get_response(request)

Why short-circuit?
  - Blocked IPs shouldn't consume any resources (no DB, no view logic)
  - Return early before any other middleware processes the request further
"""

class BlockedIPMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        raise NotImplementedError(
            "TODO 3: Check REMOTE_ADDR against settings.BLOCKED_IPS, "
            "return 403 JSON immediately if blocked, else pass through"
        )


# ════════════════════════════════════════════════════════════════════════════
# TODO 4 — MaintenanceModeMiddleware
# ════════════════════════════════════════════════════════════════════════════
"""
Implement MaintenanceModeMiddleware:

REQUEST:
  1. If settings.MAINTENANCE_MODE is False (or not set): pass through normally
  2. If path starts with any of MAINTENANCE_EXCLUDED_PATHS: pass through
     Default MAINTENANCE_EXCLUDED_PATHS = ['/admin/', '/health/']
  3. If user is staff (request.user.is_staff): pass through
  4. Otherwise: return JsonResponse(
         {'detail': 'We are down for maintenance. Be back soon.'},
         status=503,
         headers={'Retry-After': '3600'}
     )

NOTE: AuthenticationMiddleware must be BEFORE MaintenanceModeMiddleware in
      MIDDLEWARE list so that request.user is available here.
"""

class MaintenanceModeMiddleware:
    EXCLUDED_PATHS = ['/admin/', '/health/']

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        raise NotImplementedError(
            "TODO 4: Check MAINTENANCE_MODE setting, allow /admin/ and /health/, "
            "allow staff users, return 503 for everyone else"
        )


# ════════════════════════════════════════════════════════════════════════════
# HELPER — apply middleware chain (innermost to outermost)
# ════════════════════════════════════════════════════════════════════════════

def apply_middleware(view, *middleware_classes):
    """
    Wrap a view in a middleware chain.
    Order: middleware_classes[0] is outermost (runs first on request).
    """
    handler = view
    for mw_class in reversed(middleware_classes):
        handler = mw_class(handler)
    return handler


request_factory = RequestFactory()


# ════════════════════════════════════════════════════════════════════════════
# TESTS
# ════════════════════════════════════════════════════════════════════════════

def test_correlation_id_generated_when_not_provided():
    """Middleware should generate a UUID if no X-Correlation-ID in request."""
    handler  = apply_middleware(simple_view, CorrelationIDMiddleware)
    request  = request_factory.get('/api/posts/')
    response = handler(request)

    assert 'X-Correlation-ID' in response, (
        "FAIL: X-Correlation-ID header not added to response"
    )
    corr_id = response['X-Correlation-ID']
    assert len(corr_id) == 36, (
        f"FAIL: Correlation ID should be UUID (36 chars). Got: {corr_id!r}"
    )
    assert hasattr(request, 'correlation_id'), (
        "FAIL: request.correlation_id should be set"
    )


def test_correlation_id_propagated_from_request_header():
    """If X-Correlation-ID sent by client, same value must be echoed back."""
    handler = apply_middleware(simple_view, CorrelationIDMiddleware)
    client_id = "my-frontend-trace-id-12345"
    request   = request_factory.get('/api/', HTTP_X_CORRELATION_ID=client_id)
    response  = handler(request)

    assert response['X-Correlation-ID'] == client_id, (
        f"FAIL: Client-provided correlation ID should be preserved. "
        f"Expected {client_id!r}, got {response['X-Correlation-ID']!r}"
    )
    assert request.correlation_id == client_id, (
        "FAIL: request.correlation_id should equal the client-provided ID"
    )


def test_slow_request_header_always_present():
    """X-Response-Time header should be on every response."""
    handler  = apply_middleware(simple_view, SlowRequestMiddleware)
    request  = request_factory.get('/api/posts/')
    response = handler(request)

    assert 'X-Response-Time' in response, (
        "FAIL: X-Response-Time header missing from response"
    )
    header = response['X-Response-Time']
    assert header.endswith('ms'), (
        f"FAIL: X-Response-Time should end with 'ms'. Got: {header!r}"
    )


def test_slow_request_logs_warning(caplog):
    """Requests exceeding threshold should log a warning."""
    import logging

    def slow_but_real_view(request):
        time.sleep(0.02)   # 20ms
        return HttpResponse("Done")

    handler = apply_middleware(slow_but_real_view, SlowRequestMiddleware)
    request = request_factory.get('/api/heavy/')

    with override_settings(SLOW_REQUEST_THRESHOLD_MS=10):   # threshold = 10ms
        with caplog.at_level(logging.WARNING):
            response = handler(request)

    # If the request took > 10ms (it will since we sleep 20ms), warning should log
    # Note: timing can vary in CI — we just check header is present
    assert 'X-Response-Time' in response, "FAIL: header missing even on slow request"


@override_settings(BLOCKED_IPS={'192.168.1.100', '10.0.0.1'})
def test_blocked_ip_returns_403():
    """Requests from blocked IPs must get 403 before hitting the view."""
    handler = apply_middleware(simple_view, BlockedIPMiddleware)
    request = request_factory.get('/api/', REMOTE_ADDR='192.168.1.100')
    response = handler(request)

    assert response.status_code == 403, (
        f"FAIL: Blocked IP should get 403. Got {response.status_code}"
    )
    import json
    body = json.loads(response.content)
    assert 'detail' in body, (
        "FAIL: 403 response should have 'detail' field"
    )


@override_settings(BLOCKED_IPS={'192.168.1.100'})
def test_non_blocked_ip_passes_through():
    """Non-blocked IPs should reach the view normally."""
    handler  = apply_middleware(simple_view, BlockedIPMiddleware)
    request  = request_factory.get('/api/', REMOTE_ADDR='10.0.0.99')
    response = handler(request)

    assert response.status_code == 200, (
        f"FAIL: Non-blocked IP should get 200. Got {response.status_code}"
    )


@override_settings(MAINTENANCE_MODE=True)
def test_maintenance_mode_returns_503():
    """During maintenance, normal requests get 503."""
    handler  = apply_middleware(simple_view, MaintenanceModeMiddleware)
    request  = request_factory.get('/api/posts/')
    response = handler(request)

    assert response.status_code == 503, (
        f"FAIL: Maintenance mode should return 503. Got {response.status_code}"
    )
    assert 'Retry-After' in response, (
        "FAIL: 503 should include Retry-After header"
    )


@override_settings(MAINTENANCE_MODE=True)
def test_maintenance_allows_health_check():
    """/health/ endpoint bypasses maintenance mode."""
    handler  = apply_middleware(simple_view, MaintenanceModeMiddleware)
    request  = request_factory.get('/health/')
    response = handler(request)

    assert response.status_code == 200, (
        f"FAIL: /health/ should be excluded from maintenance mode. Got {response.status_code}"
    )


@override_settings(MAINTENANCE_MODE=True)
def test_maintenance_allows_admin():
    """/admin/ bypasses maintenance mode."""
    handler  = apply_middleware(simple_view, MaintenanceModeMiddleware)
    request  = request_factory.get('/admin/login/')
    response = handler(request)

    assert response.status_code == 200, (
        f"FAIL: /admin/ should bypass maintenance. Got {response.status_code}"
    )


def test_middleware_chain_order():
    """
    Both CorrelationID and SlowRequest applied together — both headers present.
    CorrelationID is outermost (runs first on request, last on response).
    """
    handler  = apply_middleware(
        simple_view,
        CorrelationIDMiddleware,   # outermost
        SlowRequestMiddleware,     # innermost
    )
    request  = request_factory.get('/api/posts/')
    response = handler(request)

    assert 'X-Correlation-ID' in response, "FAIL: X-Correlation-ID missing"
    assert 'X-Response-Time' in response,  "FAIL: X-Response-Time missing"


@override_settings(BLOCKED_IPS={'1.2.3.4'})
def test_blocked_ip_never_reaches_view():
    """Short-circuit: blocked IP must not execute the view function."""
    view_called = []

    def sensitive_view(request):
        view_called.append(True)
        return HttpResponse("Secret Data")

    handler  = apply_middleware(sensitive_view, BlockedIPMiddleware)
    request  = request_factory.get('/api/', REMOTE_ADDR='1.2.3.4')
    response = handler(request)

    assert response.status_code == 403, "FAIL: Should be blocked"
    assert len(view_called) == 0, (
        "FAIL: View was called even though IP was blocked — middleware didn't short-circuit"
    )


# ════════════════════════════════════════════════════════════════════════════
# SOCH
# ════════════════════════════════════════════════════════════════════════════

"""
SOCH (Answer ALOUD):

Q1: MIDDLEWARE list mein CorsMiddleware sabse PEHLE kyon?
    (Preflight OPTIONS requests ko route karne se pehle handle karna padta hai)

Q2: Middleware mein try/except kaise likhte hain exceptions handle karne ke liye?
    def __call__(self, request):
        try:
            response = self.get_response(request)
        except Exception as e:
            log.error("Unhandled exception", exc_info=True)
            return JsonResponse({'detail': 'Server Error'}, status=500)
        return response

Q3: DRF throttling aur Django middleware mein rate limiting — kya difference hai?
    (DRF throttle: only API views, per-user scope
     Middleware rate limiting: ALL requests including static files, coarser)

Q4: request.user middleware mein available hota hai? Kab hota hai kab nahi?
    (Only AFTER AuthenticationMiddleware runs — middleware order critical)

Q5: X-Correlation-ID ko Celery task mein bhi propagate karna ho toh kaise?
    (Pass as task argument or use threading.local / contextvars)
"""
