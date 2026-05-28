"""
DRF Custom Exception Handler — Production Patterns
"""

import uuid
import logging
from typing import Any

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, transaction
from django.http import Http404
from rest_framework import status
from rest_framework.exceptions import (
    APIException,
    ValidationError as DRFValidationError,
    AuthenticationFailed,
    NotAuthenticated,
    PermissionDenied,
    NotFound,
    Throttled,
)
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler


log = logging.getLogger(__name__)


# ==========================================================================
# 1. CUSTOM EXCEPTION CLASSES
# ==========================================================================

class BaseAPIException(APIException):
    """Base for all custom API exceptions."""

    status_code = 500
    default_detail = 'An error occurred'
    default_code = 'error'

    def __init__(self, detail=None, **extensions):
        super().__init__(detail)
        self.extensions = extensions


class BusinessLogicError(BaseAPIException):
    status_code = 400
    default_detail = 'Business logic error'
    default_code = 'business_logic_error'


class InsufficientFundsError(BaseAPIException):
    status_code = 402
    default_detail = 'Insufficient funds'
    default_code = 'insufficient_funds'


class TenantQuotaExceeded(BaseAPIException):
    status_code = 402
    default_detail = 'Tenant quota exceeded'
    default_code = 'quota_exceeded'


class RateLimitExceededError(BaseAPIException):
    status_code = 429
    default_detail = 'Rate limit exceeded'
    default_code = 'rate_limited'


class ExternalServiceError(BaseAPIException):
    status_code = 502
    default_detail = 'Upstream service error'
    default_code = 'external_service'


class IdempotencyConflictError(BaseAPIException):
    status_code = 409
    default_detail = 'Idempotency key conflict'
    default_code = 'idempotency_conflict'


# ==========================================================================
# 2. EXCEPTION HANDLER
# ==========================================================================

def custom_exception_handler(exc, context):
    """RFC 7807-like response for all DRF errors."""
    trace_id = str(uuid.uuid4())
    request = context.get('request')
    view = context.get('view')
    instance = request.path if request else None
    user_id = getattr(getattr(request, 'user', None), 'id', None)

    # Convert Django ValidationError to DRF
    if isinstance(exc, DjangoValidationError):
        exc = DRFValidationError(_django_error_to_dict(exc))

    # Convert Http404 to NotFound (DRF already does this for some cases)
    if isinstance(exc, Http404):
        exc = NotFound()

    # Handle IntegrityError (uncaught DB constraint violation)
    if isinstance(exc, IntegrityError):
        transaction.set_rollback(True)
        log.warning(
            f'IntegrityError trace_id={trace_id}',
            extra={'trace_id': trace_id, 'path': instance, 'user_id': user_id},
            exc_info=exc,
        )
        return Response(
            {
                'type': 'https://api.example.com/errors/conflict',
                'title': 'Resource conflict',
                'status': 409,
                'detail': 'The operation conflicts with existing data.',
                'instance': instance,
                'trace_id': trace_id,
            },
            status=409,
            content_type='application/problem+json',
            headers={'X-Trace-Id': trace_id},
        )

    response = drf_exception_handler(exc, context)

    # Unhandled (response is None) = 5xx
    if response is None:
        log.exception(
            f'Unhandled exception trace_id={trace_id}',
            extra={
                'trace_id': trace_id,
                'path': instance,
                'user_id': user_id,
                'method': request.method if request else None,
                'view': view.__class__.__name__ if view else None,
            },
            exc_info=exc,
        )
        return Response(
            {
                'type': 'about:blank',
                'title': 'Internal server error',
                'status': 500,
                'detail': 'An unexpected error occurred. Contact support with trace_id.',
                'instance': instance,
                'trace_id': trace_id,
            },
            status=500,
            content_type='application/problem+json',
            headers={'X-Trace-Id': trace_id},
        )

    # Build problem+json body
    status_code = response.status_code

    if isinstance(exc, DRFValidationError):
        data = {
            'type': 'https://api.example.com/errors/validation',
            'title': 'Validation failed',
            'status': status_code,
            'detail': 'One or more fields are invalid',
            'instance': instance,
            'trace_id': trace_id,
            'errors': _format_validation_errors(response.data),
        }
    elif isinstance(exc, Throttled):
        # Rate limit — add Retry-After header
        data = {
            'type': 'https://api.example.com/errors/rate-limited',
            'title': 'Too many requests',
            'status': status_code,
            'detail': str(exc.detail),
            'instance': instance,
            'trace_id': trace_id,
            'retry_after': exc.wait,
        }
        response['Retry-After'] = str(int(exc.wait or 60))
    else:
        data = {
            'type': _error_type_url(exc),
            'title': _error_title(exc, status_code),
            'status': status_code,
            'detail': _extract_detail(response.data),
            'instance': instance,
            'trace_id': trace_id,
        }

    # Merge custom exception extensions
    if isinstance(exc, BaseAPIException) and exc.extensions:
        data.update(exc.extensions)

    response.data = data
    response['Content-Type'] = 'application/problem+json'
    response['X-Trace-Id'] = trace_id

    # Log warnings for client errors that suggest issues
    if 400 <= status_code < 500 and status_code not in {401, 404, 422}:
        log.warning(
            f'Client error {status_code} trace_id={trace_id}',
            extra={'trace_id': trace_id, 'path': instance},
        )

    return response


# ==========================================================================
# 3. HELPERS
# ==========================================================================

def _django_error_to_dict(exc: DjangoValidationError):
    """Convert Django's ValidationError to dict shape DRF understands."""
    if hasattr(exc, 'error_dict'):
        return {
            field: [str(e) for e in errors]
            for field, errors in exc.error_dict.items()
        }
    elif hasattr(exc, 'error_list'):
        return [str(e) for e in exc.error_list]
    return [str(exc)]


def _format_validation_errors(detail: Any) -> list[dict]:
    """Flatten DRF nested errors into list of {loc, msg, type}."""
    errors = []
    _flatten_errors(detail, [], errors)
    return errors


def _flatten_errors(node, path: list[str], errors: list[dict]):
    if isinstance(node, dict):
        for key, value in node.items():
            _flatten_errors(value, path + [str(key)], errors)
    elif isinstance(node, list):
        if all(isinstance(x, (str, type(None))) or hasattr(x, '__str__') and not isinstance(x, (dict, list)) for x in node):
            # List of error messages
            for msg in node:
                errors.append({
                    'loc': '.'.join(path) if path else '_global',
                    'msg': str(msg),
                    'type': getattr(msg, 'code', 'invalid'),
                })
        else:
            # List of items (nested serializer)
            for i, item in enumerate(node):
                _flatten_errors(item, path + [str(i)], errors)
    else:
        errors.append({
            'loc': '.'.join(path) if path else '_global',
            'msg': str(node),
            'type': 'invalid',
        })


def _extract_detail(data):
    if isinstance(data, dict):
        return str(data.get('detail', '') or '')
    if isinstance(data, list) and data:
        return str(data[0])
    return str(data) if data else ''


def _error_type_url(exc):
    code = getattr(exc, 'default_code', None) or exc.__class__.__name__.lower()
    return f'https://api.example.com/errors/{code}'


def _error_title(exc, status_code):
    if hasattr(exc, 'default_detail') and isinstance(exc.default_detail, str):
        return exc.default_detail
    return f'HTTP {status_code}'


# ==========================================================================
# 4. SETTINGS REGISTRATION
# ==========================================================================

"""
# settings.py

REST_FRAMEWORK = {
    'EXCEPTION_HANDLER': 'myapp.exceptions.custom_exception_handler',
    # ... other settings
}
"""


# ==========================================================================
# 5. USAGE IN VIEWS
# ==========================================================================

from rest_framework.views import APIView
from rest_framework.decorators import api_view


@api_view(['POST'])
def transfer(request):
    from_account = request.data.get('from_account')
    amount = request.data.get('amount')

    # Mock account
    account = type('A', (), {'balance': 50.0, 'currency': 'USD'})()

    if account.balance < amount:
        raise InsufficientFundsError(
            detail=f'Balance {account.currency} {account.balance:.2f}, requested {account.currency} {amount:.2f}',
            balance=account.balance,
            requested=amount,
            currency=account.currency,
        )

    return Response({'status': 'transferred'})


@api_view(['POST'])
def upgrade_plan(request):
    tenant = request.user.tenant

    if tenant.users_count >= tenant.users_limit:
        raise TenantQuotaExceeded(
            detail=f'Tenant has {tenant.users_count} users (limit: {tenant.users_limit})',
            tenant_id=tenant.id,
            quota_type='users',
            limit=tenant.users_limit,
            used=tenant.users_count,
            upgrade_url=f'/billing/upgrade?tenant={tenant.id}',
        )
    return Response({'status': 'upgraded'})


# ==========================================================================
# 6. SENTRY INTEGRATION
# ==========================================================================

"""
# settings.py

import sentry_sdk
from sentry_sdk.integrations.django import DjangoIntegration


sentry_sdk.init(
    dsn=os.environ['SENTRY_DSN'],
    integrations=[DjangoIntegration()],
    traces_sample_rate=0.1,
    send_default_pii=False,
    environment='production',
    before_send=lambda event, hint: None if event.get('level') in {'warning', 'info'} else event,
)


# In exception handler, link Sentry event to trace_id
import sentry_sdk

def custom_exception_handler(exc, context):
    trace_id = str(uuid.uuid4())

    with sentry_sdk.push_scope() as scope:
        scope.set_tag('trace_id', trace_id)
        scope.set_context('request', {...})
        # ... handle exception
"""


# ==========================================================================
# 7. SAMPLE RESPONSES
# ==========================================================================

SAMPLE_RESPONSES = """
# Validation error (422)
POST /api/users/ {"email": "invalid", "age": -1}

HTTP/1.1 400 Bad Request
Content-Type: application/problem+json
X-Trace-Id: abc-123

{
    "type": "https://api.example.com/errors/validation",
    "title": "Validation failed",
    "status": 400,
    "detail": "One or more fields are invalid",
    "instance": "/api/users/",
    "trace_id": "abc-123",
    "errors": [
        {"loc": "email", "msg": "Enter a valid email address.", "type": "invalid"},
        {"loc": "age", "msg": "Ensure this value is greater than or equal to 0.", "type": "min_value"}
    ]
}


# Custom business error
POST /api/transfers/ {"amount": 100}

HTTP/1.1 402 Payment Required
Content-Type: application/problem+json
X-Trace-Id: def-456

{
    "type": "https://api.example.com/errors/insufficient_funds",
    "title": "Insufficient funds",
    "status": 402,
    "detail": "Balance USD 50.00, requested USD 100.00",
    "instance": "/api/transfers/",
    "trace_id": "def-456",
    "balance": 50.0,
    "requested": 100.0,
    "currency": "USD"
}


# Rate limit (429)
HTTP/1.1 429 Too Many Requests
Content-Type: application/problem+json
Retry-After: 60
X-Trace-Id: ghi-789

{
    "type": "https://api.example.com/errors/rate-limited",
    "title": "Too many requests",
    "status": 429,
    "detail": "Request was throttled. Expected available in 60 seconds.",
    "instance": "/api/expensive/",
    "trace_id": "ghi-789",
    "retry_after": 60
}


# 500 (production safe)
HTTP/1.1 500 Internal Server Error
Content-Type: application/problem+json
X-Trace-Id: xyz-000

{
    "type": "about:blank",
    "title": "Internal server error",
    "status": 500,
    "detail": "An unexpected error occurred. Contact support with trace_id.",
    "instance": "/api/...",
    "trace_id": "xyz-000"
}
# Full exception logged server-side with trace_id
"""


# ==========================================================================
# 8. TESTING THE HANDLER
# ==========================================================================

"""
# tests/test_exceptions.py

from rest_framework.test import APITestCase


class ExceptionHandlerTests(APITestCase):
    def test_validation_error_format(self):
        response = self.client.post('/api/users/', {'email': 'invalid'})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response['Content-Type'], 'application/problem+json')
        self.assertIn('type', response.data)
        self.assertIn('errors', response.data)
        self.assertIn('trace_id', response.data)

    def test_custom_exception(self):
        # Trigger InsufficientFundsError in view
        response = self.client.post('/api/transfer/', {'amount': 999999})
        self.assertEqual(response.status_code, 402)
        self.assertEqual(response.data['type'].endswith('/insufficient_funds'), True)
        self.assertIn('balance', response.data)

    def test_500_doesnt_leak(self):
        with mock.patch('myapp.views.some_function', side_effect=Exception('secret schema')):
            response = self.client.get('/api/some/')
        self.assertEqual(response.status_code, 500)
        self.assertNotIn('secret schema', response.content.decode())
        self.assertIn('trace_id', response.data)
"""
