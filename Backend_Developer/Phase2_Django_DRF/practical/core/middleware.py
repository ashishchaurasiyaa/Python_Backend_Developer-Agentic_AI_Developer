"""
Custom Django Middleware
═══════════════════════════
INTERVIEW: Django middleware kaise kaam karta hai?
  - MIDDLEWARE list top-down process_request, bottom-up process_response
  - __init__(get_response) — server start par ek baar call
  - __call__(request) — har request par call

INTERVIEW: Middleware vs DRF Middleware (permission/throttle) fark?
  - Django middleware — ALL requests (static, admin, DRF, views)
  - DRF permission/throttle — only DRF API views
"""

import time
import uuid
import logging

log = logging.getLogger(__name__)


class RequestIDMiddleware:
    """
    Attach a unique request_id to every request.
    Used for log correlation and response header X-Request-ID.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Accept from header (for frontend-generated IDs) or generate
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        request.request_id = request_id

        response = self.get_response(request)
        response["X-Request-ID"] = request_id
        return response


class RequestLoggingMiddleware:
    """
    Structured request/response logging.

    INTERVIEW: Ye middleware FastAPI ke StructuredLoggingMiddleware ka
    Django equivalent hai. Same pattern — timing, method, path, status.
    """
    SKIP_PATHS = {"/favicon.ico", "/static/", "/media/", "/health/"}

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Skip noise paths
        if any(request.path.startswith(p) for p in self.SKIP_PATHS):
            return self.get_response(request)

        start = time.perf_counter()

        log.info(
            "request_started",
            extra={
                "request_id": getattr(request, "request_id", "-"),
                "method": request.method,
                "path": request.path,
                "user_id": getattr(getattr(request, "user", None), "id", None),
            },
        )

        response = self.get_response(request)

        duration_ms = round((time.perf_counter() - start) * 1000, 2)
        level = logging.WARNING if response.status_code >= 400 else logging.INFO

        log.log(
            level,
            "request_finished",
            extra={
                "request_id": getattr(request, "request_id", "-"),
                "status": response.status_code,
                "duration_ms": duration_ms,
                "method": request.method,
                "path": request.path,
            },
        )

        response["X-Response-Time"] = f"{duration_ms}ms"
        return response


class MaintenanceModeMiddleware:
    """
    Block all traffic during maintenance window.

    Usage:
        MAINTENANCE_MODE = True  # in settings
    """
    EXCLUDED_PATHS = ["/admin/", "/health/"]

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        from django.conf import settings
        from django.http import JsonResponse

        if (
            getattr(settings, "MAINTENANCE_MODE", False)
            and not any(request.path.startswith(p) for p in self.EXCLUDED_PATHS)
            and not getattr(request.user, "is_staff", False)
        ):
            return JsonResponse(
                {"detail": "Service temporarily unavailable. Try again later."},
                status=503,
                headers={"Retry-After": "3600"},
            )
        return self.get_response(request)
