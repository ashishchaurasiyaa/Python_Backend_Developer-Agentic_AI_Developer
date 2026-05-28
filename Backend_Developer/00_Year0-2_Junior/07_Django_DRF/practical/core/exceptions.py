"""
Custom Exception Handler + App Exceptions
═══════════════════════════════════════════
INTERVIEW: DRF default exception handler kya return karta hai?
  {"detail": "..."} format

INTERVIEW: Custom exception handler kab chahiye?
  - Consistent API response format {"success": false, "error": {...}}
  - Non-DRF exceptions handle karna (Django 404, PermissionDenied)
  - Sentry/logging integration
  - Different error codes for frontend
"""

import logging
from rest_framework.views import exception_handler
from rest_framework.response import Response
from rest_framework import status
from rest_framework.exceptions import APIException

log = logging.getLogger(__name__)


# ─── Custom App Exceptions ────────────────────────────────

class AppError(APIException):
    """Base exception for all application errors."""
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "An error occurred"
    default_code = "error"


class NotFoundError(AppError):
    status_code = status.HTTP_404_NOT_FOUND
    default_detail = "Resource not found"
    default_code = "not_found"


class ConflictError(AppError):
    status_code = status.HTTP_409_CONFLICT
    default_detail = "Resource already exists"
    default_code = "conflict"


class UnauthorizedError(AppError):
    status_code = status.HTTP_401_UNAUTHORIZED
    default_detail = "Authentication required"
    default_code = "unauthorized"


class ForbiddenError(AppError):
    status_code = status.HTTP_403_FORBIDDEN
    default_detail = "You do not have permission to perform this action"
    default_code = "forbidden"


class BusinessRuleError(AppError):
    """Domain/business logic violations."""
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    default_code = "business_rule_violation"


# ─── Custom Exception Handler ─────────────────────────────

def custom_exception_handler(exc, context):
    """
    Wraps DRF's default handler to return a consistent envelope:

    Success:
        {"success": true, "data": {...}}

    Error:
        {
            "success": false,
            "error": {
                "code": "validation_error",
                "message": "...",
                "details": {...}   # field errors if any
            }
        }

    INTERVIEW: DRF settings mein register kaise karte hain?
        REST_FRAMEWORK = {
            "EXCEPTION_HANDLER": "core.exceptions.custom_exception_handler"
        }
    """
    # Call DRF's default handler first
    response = exception_handler(exc, context)

    if response is None:
        # Unhandled exception — log and return 500
        log.exception("Unhandled exception", exc_info=exc)
        return Response(
            {
                "success": False,
                "error": {
                    "code": "server_error",
                    "message": "An unexpected error occurred",
                },
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    # Normalize error details
    detail = response.data
    if isinstance(detail, dict) and "detail" in detail:
        message = str(detail["detail"])
        details = None
    elif isinstance(detail, dict):
        # Validation errors — field → error list
        message = "Validation failed"
        details = {
            field: [str(e) for e in errors] if isinstance(errors, list) else [str(errors)]
            for field, errors in detail.items()
        }
    elif isinstance(detail, list):
        message = str(detail[0]) if detail else "Error"
        details = None
    else:
        message = str(detail)
        details = None

    error_code = getattr(getattr(exc, "detail", None), "code", None) or "error"

    response.data = {
        "success": False,
        "error": {
            "code": error_code,
            "message": message,
            **({"details": details} if details else {}),
        },
    }

    # Log 5xx errors
    if response.status_code >= 500:
        log.error("Server error", exc_info=exc)
    elif response.status_code >= 400:
        log.warning("Client error: %s", message, extra={"code": error_code})

    return response
