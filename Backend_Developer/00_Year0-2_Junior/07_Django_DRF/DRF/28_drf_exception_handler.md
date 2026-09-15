# DRF Custom Exception Handler

## Why It Matters

Default DRF errors = inconsistent shapes. Production needs:
- **Single error format** across all endpoints
- **RFC 7807 Problem Details** for standards
- **Field-level errors** for forms
- **Trace IDs** for support correlation
- **No information leaks** (stack traces, SQL)

Senior interview: "Error response format design?" → custom exception_handler with consistent envelope.

---

## Core Concepts

### Default DRF Errors

```python
# Validation error
{
    "field_name": ["This field is required."],
    "another_field": ["Invalid value."]
}


# HTTP errors
{
    "detail": "Not found."
}


# Inconsistent → hard to parse uniformly
```

### Custom Exception Handler

```python
# myapp/exceptions.py

import uuid
import logging
from rest_framework.views import exception_handler as drf_exception_handler
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.exceptions import APIException
from rest_framework.response import Response
from django.core.exceptions import ValidationError as DjangoValidationError
from django.http import Http404
from django.db import IntegrityError


log = logging.getLogger(__name__)


def custom_exception_handler(exc, context):
    """
    Returns RFC 7807-like structure for all errors.
    
    {
        "type": "https://api.example.com/errors/validation",
        "title": "Validation failed",
        "status": 400,
        "detail": "...",
        "instance": "/api/users/",
        "trace_id": "abc-123",
        "errors": [
            {"loc": "email", "msg": "Invalid email", "type": "format"}
        ]
    }
    """
    trace_id = str(uuid.uuid4())
    request = context.get('request')
    instance = request.path if request else None

    # Handle Django ValidationError
    if isinstance(exc, DjangoValidationError):
        exc = DRFValidationError(detail=_django_error_to_dict(exc))

    # Get default response
    response = drf_exception_handler(exc, context)

    if response is None:
        # Unhandled exception
        log.exception(f'Unhandled exception trace_id={trace_id}', exc_info=exc)
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
        )

    # Transform DRF response
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
    else:
        data = {
            'type': _error_type_url(exc),
            'title': _error_title(exc, status_code),
            'status': status_code,
            'detail': str(response.data.get('detail', '')) if isinstance(response.data, dict) else str(response.data),
            'instance': instance,
            'trace_id': trace_id,
        }

    response.data = data
    response['Content-Type'] = 'application/problem+json'
    return response


def _django_error_to_dict(exc):
    if hasattr(exc, 'error_dict'):
        return {k: [str(e) for e in v] for k, v in exc.error_dict.items()}
    elif hasattr(exc, 'error_list'):
        return [str(e) for e in exc.error_list]
    return str(exc)


def _format_validation_errors(detail):
    """Transform DRF's field: [errors] into list of {loc, msg, type}."""
    errors = []
    if isinstance(detail, dict):
        for field, messages in detail.items():
            if isinstance(messages, list):
                for msg in messages:
                    errors.append({
                        'loc': field,
                        'msg': str(msg),
                        'type': getattr(msg, 'code', 'invalid'),
                    })
            elif isinstance(messages, dict):
                # Nested serializer errors
                for nested_field, nested_msgs in messages.items():
                    for msg in (nested_msgs if isinstance(nested_msgs, list) else [nested_msgs]):
                        errors.append({
                            'loc': f'{field}.{nested_field}',
                            'msg': str(msg),
                            'type': getattr(msg, 'code', 'invalid'),
                        })
            else:
                errors.append({'loc': field, 'msg': str(messages), 'type': 'invalid'})
    elif isinstance(detail, list):
        for msg in detail:
            errors.append({'loc': '_global', 'msg': str(msg), 'type': 'invalid'})
    else:
        errors.append({'loc': '_global', 'msg': str(detail), 'type': 'invalid'})
    return errors


def _error_type_url(exc):
    code = getattr(exc, 'default_code', None) or exc.__class__.__name__.lower()
    return f'https://api.example.com/errors/{code}'


def _error_title(exc, status):
    if hasattr(exc, 'default_detail'):
        return str(exc.default_detail)
    return f'HTTP {status}'


# settings.py
REST_FRAMEWORK = {
    'EXCEPTION_HANDLER': 'myapp.exceptions.custom_exception_handler',
}
```

### Custom Exception Classes

```python
from rest_framework.exceptions import APIException


class BusinessLogicError(APIException):
    status_code = 400
    default_detail = 'Business logic error'
    default_code = 'business_logic_error'


class InsufficientFundsError(APIException):
    status_code = 402  # Payment Required
    default_detail = 'Insufficient funds'
    default_code = 'insufficient_funds'


class RateLimitExceededError(APIException):
    status_code = 429
    default_detail = 'Rate limit exceeded'
    default_code = 'rate_limit_exceeded'


class TenantQuotaExceeded(APIException):
    status_code = 402
    default_detail = 'Tenant quota exceeded'
    default_code = 'quota_exceeded'


# Use in views
@api_view(['POST'])
def transfer(request):
    if account.balance < amount:
        raise InsufficientFundsError(
            detail=f'Balance ${account.balance}, requested ${amount}',
        )
```

### Adding Extensions (Domain-Specific Data)

```python
class InsufficientFundsError(APIException):
    status_code = 402
    default_detail = 'Insufficient funds'
    default_code = 'insufficient_funds'

    def __init__(self, balance, requested, currency='USD', **kwargs):
        super().__init__(
            detail=f'Balance {currency} {balance}, requested {currency} {requested}',
            **kwargs,
        )
        # Store extras for handler
        self.extensions = {
            'balance': balance,
            'requested': requested,
            'currency': currency,
        }


# Update exception_handler to merge extensions
def custom_exception_handler(exc, context):
    response = drf_exception_handler(exc, context)
    # ... build data
    if hasattr(exc, 'extensions'):
        data.update(exc.extensions)
    response.data = data
    return response
```

### Integrity Error Handling

```python
def custom_exception_handler(exc, context):
    # Catch DB integrity errors → 409 Conflict
    if isinstance(exc, IntegrityError):
        from django.db import transaction
        # Rollback
        transaction.set_rollback(True)

        return Response(
            {
                'type': 'https://api.example.com/errors/conflict',
                'title': 'Conflict',
                'status': 409,
                'detail': 'Operation conflicts with existing data',
                'trace_id': str(uuid.uuid4()),
            },
            status=409,
            content_type='application/problem+json',
        )
    # ... rest of handler
```

### Logging Strategy

```python
def custom_exception_handler(exc, context):
    request = context.get('request')

    if response is None:  # 5xx
        log.exception(
            'Unhandled API exception',
            extra={
                'trace_id': trace_id,
                'path': request.path,
                'user_id': getattr(request.user, 'id', None),
                'method': request.method,
            },
            exc_info=exc,
        )
    elif response.status_code >= 500:
        log.error('API 5xx', extra={...})
    elif response.status_code == 429:
        log.warning('Rate limit hit', extra={...})
    # 4xx generally don't log (too noisy)
```

### Per-View Override

```python
class SpecialView(APIView):
    def get_exception_handler(self):
        return special_exception_handler

    def special_exception_handler(self, exc, context):
        # Custom for this view
        ...
```

---

## Common Pitfalls

### 1. Leaking Stack Traces

```python
return Response({'error': str(exc)})   # may include path info, schema
```

Generic message for 5xx + log details server-side.

### 2. Returning 500 for 4xx Issues

```python
try:
    obj = Model.objects.get(pk=X)
except Model.DoesNotExist:
    return Response({'error': 'Internal error'}, status=500)
```

Should be 404. Django's `DoesNotExist` should map to 404.

### 3. Inconsistent Schemas

Half endpoints return `{detail: ...}`, others `{error: ..., message: ...}`. Use global handler.

### 4. Not Handling Django ValidationError

DRF's handler doesn't auto-catch Django's `ValidationError`. Add conversion:

```python
if isinstance(exc, DjangoValidationError):
    exc = DRFValidationError(...)
```

### 5. Sentry Not Configured

Without Sentry/error tracker, 500s invisible to developers. Add `sentry-sdk`:

```python
sentry_sdk.init(
    dsn=os.environ['SENTRY_DSN'],
    integrations=[DjangoIntegration()],
)
```

### 6. No Trace ID

User reports "got an error" — without trace ID, impossible to debug. Always include.

### 7. Catching All Exceptions

```python
try:
    ...
except Exception:
    return Response({'error': 'Something went wrong'}, status=500)
```

Generic catch hides bugs. Let handler do its job; catch only specific known cases.

---

## Interview Q&A

**Q1:** DRF custom exception handler kab zaroori?
**A:** When you need consistent error response shape across all endpoints, or to map domain exceptions to HTTP status, or to add trace IDs / structured logging. Default DRF responses are inconsistent (`{detail: ...}` for HTTP errors, `{field: [...]}` for validation).

**Q2:** RFC 7807 Django mein implement kaise?
**A:** Custom exception handler returns dict with `type, title, status, detail, instance` + extensions. Content-Type `application/problem+json`. Map DRF errors to this shape: validation → `errors[]`, HTTP errors → standard fields. Available via npm libs in clients for parsing.

**Q3:** 500 vs 4xx differentiation?
**A:** Log 500s with full exception + alert. 4xx generally don't log (user error). Use Sentry for 500 tracking. Include `trace_id` so user can give it to support → server lookup. Never expose stack trace / SQL / paths in 500 response body.

**Q4:** IntegrityError DB se kaise handle?
**A:** Catch in exception_handler, return 409 Conflict with descriptive message (e.g., "Email already exists"). Use `transaction.set_rollback(True)` to ensure ATOMIC_REQUESTS doesn't break. Don't expose constraint name (`users_email_key` leaks schema).

**Q5:** Nested serializer errors flatten?
**A:** DRF returns nested dict: `{user: {email: [...]}, items: [{name: [...]}]}`. Flatten to list: `[{loc: "user.email", msg: ...}, {loc: "items.0.name", msg: ...}]`. Use dot/index notation for path. Easier for client to map to form fields.

**Q6:** Field-level vs request-level errors?
**A:** Field-level: validation error on specific input (`email format invalid`). Request-level: general (`Insufficient permissions`). RFC 7807 uses `loc: "_global"` or `errors: []` for global. Frontend shows: field errors next to inputs, global as toast/banner.

**Q7:** Custom exception class design?
**A:** Subclass `APIException`. Set `status_code`, `default_detail`, `default_code`. Optional `extensions` dict for domain-specific data. Raise in views/services. Global handler picks up via class hierarchy. Naming: `InsufficientFundsError`, `TenantQuotaExceeded` — self-documenting.

**Q8:** Production debugging without exposing internals?
**A:** Include `trace_id` in every error response. Log to Sentry/Datadog with same trace_id. User reports "got error abc-123" — engineer searches logs by trace_id, sees full stack trace + request data. No info leak in response.

---

## Real-World Use Cases

### 1. Multi-Tenant SaaS Errors

```python
class TenantQuotaExceeded(APIException):
    status_code = 402
    default_code = 'tenant_quota_exceeded'

    def __init__(self, tenant, quota_type, **kwargs):
        super().__init__(**kwargs)
        self.extensions = {
            'tenant_id': tenant.id,
            'quota_type': quota_type,
            'limit': getattr(tenant, f'{quota_type}_limit'),
            'used': getattr(tenant, f'{quota_type}_used'),
            'upgrade_url': f'/billing/upgrade?tenant={tenant.id}',
        }
```

### 2. Stripe-Style Errors

```python
class CardDeclinedError(APIException):
    status_code = 402
    default_code = 'card_declined'

    def __init__(self, decline_code, **kwargs):
        super().__init__(detail=f'Card declined: {decline_code}', **kwargs)
        self.extensions = {
            'decline_code': decline_code,
            'next_steps': self._next_steps(decline_code),
        }

    def _next_steps(self, code):
        return {
            'insufficient_funds': 'Try a different card',
            'expired_card': 'Update card details',
        }.get(code, 'Contact bank')
```

### 3. Rate Limit with Retry-After

```python
class RateLimitExceededError(APIException):
    status_code = 429
    default_code = 'rate_limited'

    def __init__(self, retry_after_seconds, **kwargs):
        super().__init__(**kwargs)
        self.extensions = {'retry_after': retry_after_seconds}


# In handler, set Retry-After header
response['Retry-After'] = str(exc.extensions['retry_after'])
```

---

## References

- [DRF Exceptions](https://www.django-rest-framework.org/api-guide/exceptions/)
- [RFC 7807 — Problem Details](https://datatracker.ietf.org/doc/html/rfc7807)
- [RFC 9457 — Successor to 7807](https://datatracker.ietf.org/doc/html/rfc9457)
- Sentry integration docs
