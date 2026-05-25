# RFC 7807 Problem Details — Standardized API Errors

## Why It Matters (Senior 5 YOE Context)

API errors should be **machine-readable, consistent, debuggable**. RFC 7807 is the IETF standard:

```json
{
  "type": "https://api.example.com/probs/insufficient-funds",
  "title": "Insufficient funds",
  "status": 400,
  "detail": "Account 12345 has balance $10.00, requested $20.00",
  "instance": "/transactions/abc-123",
  "balance": 10.00,
  "currency": "USD"
}
```

Benefits:
- **Standard** → SDKs can parse uniformly
- **Self-documenting** → `type` URL → docs
- **Extensible** → custom fields for context
- **Localizable** → title/detail can be translated

Senior interview: "Design error response format for your API." → RFC 7807 + extensions.

---

## Core Concepts

### RFC 7807 Required Fields

| Field | Description |
|---|---|
| `type` | URI identifying error type (URL to docs) |
| `title` | Short human-readable summary |
| `status` | HTTP status code |
| `detail` | Specific to this occurrence |
| `instance` | URI identifying this specific occurrence (often request path) |

Plus arbitrary extensions.

### Content-Type Header

```
Content-Type: application/problem+json
```

Distinguishes from regular JSON (signals errors).

### FastAPI Implementation

```python
from typing import Any
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel


class ProblemDetail(BaseModel):
    type: str = "about:blank"
    title: str
    status: int
    detail: str | None = None
    instance: str | None = None

    model_config = {
        'json_schema_extra': {
            'example': {
                'type': 'https://api.example.com/probs/insufficient-funds',
                'title': 'Insufficient funds',
                'status': 400,
                'detail': 'Account has balance $10, requested $20',
                'instance': '/transactions/abc-123',
            }
        }
    }


def problem_response(
    *,
    type: str = "about:blank",
    title: str,
    status_code: int,
    detail: str | None = None,
    instance: str | None = None,
    **extensions: Any,
) -> JSONResponse:
    """Build RFC 7807 response."""
    payload = {
        'type': type,
        'title': title,
        'status': status_code,
    }
    if detail:
        payload['detail'] = detail
    if instance:
        payload['instance'] = instance
    payload.update(extensions)

    return JSONResponse(
        status_code=status_code,
        content=payload,
        media_type='application/problem+json',
    )
```

### Custom Exception Hierarchy

```python
class APIException(Exception):
    """Base for all API errors."""

    type: str = "about:blank"
    title: str = "Server Error"
    status_code: int = 500

    def __init__(self, detail: str | None = None, **extensions):
        self.detail = detail
        self.extensions = extensions
        super().__init__(detail or self.title)


class InsufficientFundsError(APIException):
    type = "https://api.example.com/probs/insufficient-funds"
    title = "Insufficient funds"
    status_code = 400


class ResourceNotFoundError(APIException):
    type = "https://api.example.com/probs/not-found"
    title = "Resource not found"
    status_code = 404


class RateLimitedError(APIException):
    type = "https://api.example.com/probs/rate-limited"
    title = "Too many requests"
    status_code = 429


class ValidationFailedError(APIException):
    type = "https://api.example.com/probs/validation-failed"
    title = "Validation failed"
    status_code = 422
```

### Global Exception Handler

```python
app = FastAPI()


@app.exception_handler(APIException)
async def api_exception_handler(request: Request, exc: APIException):
    return problem_response(
        type=exc.type,
        title=exc.title,
        status_code=exc.status_code,
        detail=exc.detail,
        instance=str(request.url.path),
        **exc.extensions,
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return problem_response(
        title=f"HTTP {exc.status_code}",
        status_code=exc.status_code,
        detail=str(exc.detail) if exc.detail else None,
        instance=str(request.url.path),
    )


@app.exception_handler(RequestValidationError)
async def validation_handler(request: Request, exc: RequestValidationError):
    return problem_response(
        type="https://api.example.com/probs/validation-failed",
        title="Request validation failed",
        status_code=422,
        instance=str(request.url.path),
        errors=[
            {
                'loc': '.'.join(str(p) for p in e['loc']),
                'msg': e['msg'],
                'type': e['type'],
            }
            for e in exc.errors()
        ],
    )


@app.exception_handler(Exception)
async def unhandled_handler(request: Request, exc: Exception):
    # Generic — don't leak details
    import logging
    logging.exception("Unhandled", exc_info=exc)
    return problem_response(
        title="Internal server error",
        status_code=500,
        instance=str(request.url.path),
    )
```

### Usage in Endpoints

```python
@app.post("/transactions")
def create_transaction(amount: float, account_id: int):
    account = db.get_account(account_id)
    if not account:
        raise ResourceNotFoundError(
            detail=f"Account {account_id} not found",
            account_id=account_id,
        )

    if account.balance < amount:
        raise InsufficientFundsError(
            detail=f"Balance ${account.balance}, requested ${amount}",
            balance=account.balance,
            requested=amount,
            currency=account.currency,
        )

    # ...
```

Response:

```json
{
  "type": "https://api.example.com/probs/insufficient-funds",
  "title": "Insufficient funds",
  "status": 400,
  "detail": "Balance $10.00, requested $20.00",
  "instance": "/transactions",
  "balance": 10.0,
  "requested": 20.0,
  "currency": "USD"
}
```

### Validation Errors — Field-Level

```python
{
  "type": "https://api.example.com/probs/validation-failed",
  "title": "Request validation failed",
  "status": 422,
  "instance": "/users",
  "errors": [
    {"loc": "body.email", "msg": "invalid email format", "type": "string_pattern_mismatch"},
    {"loc": "body.age", "msg": "ensure this value >= 0", "type": "greater_than_equal"}
  ]
}
```

### Distributed Tracing Integration

Add trace_id to every problem response for support correlation:

```python
def problem_response_with_trace(request: Request, **kwargs):
    trace_id = request.headers.get('x-trace-id') or request.state.trace_id
    return problem_response(trace_id=trace_id, **kwargs)
```

---

## How It Works Internally

### Content Negotiation

Clients sending `Accept: application/problem+json` get RFC 7807 format. Others get regular JSON. Most clients accept both — default to problem+json.

### `type` URL Best Practices

- Each error type gets a unique URL
- URL should resolve to docs page describing the error
- Keep URLs stable (don't change once published)
- Use opaque URI if no docs site: `urn:problem-type:insufficient-funds`

### Localization

```python
# i18n integration
LOCALES = {
    'en': {'insufficient-funds': {'title': 'Insufficient funds', 'detail': '...'}},
    'hi': {'insufficient-funds': {'title': 'अपर्याप्त धनराशि', 'detail': '...'}},
}


def i18n_problem(request, error_key, **extensions):
    lang = request.headers.get('accept-language', 'en')[:2]
    locale = LOCALES.get(lang, LOCALES['en']).get(error_key, {})
    return problem_response(
        type=f'https://api.example.com/probs/{error_key}',
        title=locale.get('title', error_key),
        detail=locale.get('detail'),
        **extensions,
    )
```

---

## Common Pitfalls

### 1. Stack Traces in `detail`

Never include exception traces in detail — production info leak. Log server-side, return generic.

### 2. Inconsistent Error Shape

Half endpoints return RFC 7807, half return `{"error": "..."}` → client SDK complexity. Enforce via handler.

### 3. `type` as Relative URL

```python
"type": "/probs/insufficient-funds"  # ambiguous
```

Use absolute URL or `urn:...`.

### 4. Sensitive Data in Extensions

```python
raise InsufficientFundsError(
    balance=account.balance,
    customer_email=account.email,  # leaks PII if error logged
)
```

Don't include PII in error responses (logged + shown).

### 5. 500 Error with Sensitive Details

```python
raise APIException(detail=f"DB connection failed: {e}")  # leaks DB info
```

Generic 500: "Internal error, contact support with trace_id: X".

### 6. Not Logging Errors Server-Side

User sees error → support has nothing to debug with. Always log full exception + trace_id, return trace_id in response.

---

## Interview Q&A

**Q1:** API error response format kaisa hona chahiye?
**A:** RFC 7807 Problem Details — `type, title, status, detail, instance` standard fields + custom extensions. Content-Type `application/problem+json`. Allows clients to parse uniformly. Senior teams pick this over ad-hoc `{error, message}` formats.

**Q2:** Validation errors RFC 7807 mein kaise represent karoge?
**A:** Use `errors` array as extension: `errors: [{loc, msg, type}]`. Top-level title generic ("Validation failed"), individual field errors in array. FastAPI's `RequestValidationError.errors()` maps cleanly.

**Q3:** Production mein 500 errors mein kya include karoge?
**A:** Generic title ("Internal error"), no detail, just trace_id for support correlation. Log full exception + trace_id server-side. User gives trace_id to support, support looks up in logs. Never leak stack trace, DB schema, SQL, file paths in response.

**Q4:** `type` URL ka use kya hai?
**A:** Identifies error category — clients can branch on it. URL ideally resolves to docs explaining the error + retry guidance. Use `urn:problem-type:X` if no docs site. Keep stable — clients depend on it.

**Q5:** Custom exception hierarchy benefits?
**A:** (1) Code clarity — `raise InsufficientFundsError(...)` self-documenting. (2) Centralized handling via global handler. (3) Auto-mapping to HTTP status. (4) Easy to add cross-cutting concerns (logging, metrics) per error type. (5) Consistent error format without duplication.

**Q6:** Error extensions kab use karoge?
**A:** Domain-specific data clients need for retry/UX decisions: `retry_after` for rate limit, `balance/requested` for insufficient funds, `field_errors` for validation. Avoid PII; keep relevant context.

**Q7:** Multi-language API mein error messages?
**A:** Read Accept-Language header, look up localized title/detail. Keep `type` URL stable (don't translate). Extensions translatable too. Or: keep error codes stable, frontend handles localization based on `type`.

**Q8:** RFC 7807 vs GraphQL errors?
**A:** REST: 7807 for HTTP errors (4xx/5xx). GraphQL: errors in `errors` array with separate `path`. Different conventions but similar principles — structured, machine-readable, extensible. Don't mix in same API.

---

## Real-World Use Cases

### 1. Stripe-Style Detailed Errors

```python
class InvalidPaymentMethodError(APIException):
    type = "https://api.example.com/probs/invalid-payment-method"
    title = "Invalid payment method"
    status_code = 400


raise InvalidPaymentMethodError(
    detail="Card declined",
    decline_code="insufficient_funds",
    payment_method_id="pm_123",
    next_action="Try a different card",
)
```

### 2. Rate Limit with Retry-After

```python
@app.exception_handler(RateLimitedError)
async def rate_limit_handler(request, exc):
    response = problem_response(
        type=exc.type,
        title=exc.title,
        status_code=429,
        detail=exc.detail,
        retry_after_seconds=60,
    )
    response.headers['Retry-After'] = '60'
    return response
```

### 3. Multi-Tenant Errors

```python
raise TenantQuotaExceededError(
    detail="Monthly API quota exceeded",
    tenant_id=tenant.id,
    quota_limit=tenant.quota,
    quota_used=tenant.usage,
    quota_reset_at="2026-06-01T00:00:00Z",
)
```

---

## References

- [RFC 7807 — Problem Details](https://datatracker.ietf.org/doc/html/rfc7807)
- [RFC 9457 — successor of 7807](https://datatracker.ietf.org/doc/html/rfc9457)
- Stripe API errors documentation
- Microsoft REST API guidelines
