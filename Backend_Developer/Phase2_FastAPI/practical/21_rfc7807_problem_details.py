"""
RFC 7807 Problem Details — Production Patterns
"""

from typing import Any
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel


app = FastAPI()


# ==========================================================================
# 1. PROBLEM RESPONSE BUILDER
# ==========================================================================

def problem_response(
    *,
    type: str = "about:blank",
    title: str,
    status_code: int,
    detail: str | None = None,
    instance: str | None = None,
    **extensions: Any,
) -> JSONResponse:
    """Build RFC 7807 problem+json response."""
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


# ==========================================================================
# 2. CUSTOM EXCEPTION HIERARCHY
# ==========================================================================

class APIException(Exception):
    type: str = "about:blank"
    title: str = "Server Error"
    status_code: int = 500

    def __init__(self, detail: str | None = None, **extensions):
        self.detail = detail
        self.extensions = extensions
        super().__init__(detail or self.title)


class ResourceNotFoundError(APIException):
    type = "https://api.example.com/probs/not-found"
    title = "Resource not found"
    status_code = 404


class InsufficientFundsError(APIException):
    type = "https://api.example.com/probs/insufficient-funds"
    title = "Insufficient funds"
    status_code = 400


class InvalidStateError(APIException):
    type = "https://api.example.com/probs/invalid-state"
    title = "Invalid state for operation"
    status_code = 409


class RateLimitedError(APIException):
    type = "https://api.example.com/probs/rate-limited"
    title = "Too many requests"
    status_code = 429


class UnauthenticatedError(APIException):
    type = "https://api.example.com/probs/unauthenticated"
    title = "Authentication required"
    status_code = 401


class ForbiddenError(APIException):
    type = "https://api.example.com/probs/forbidden"
    title = "Access denied"
    status_code = 403


class ValidationFailedError(APIException):
    type = "https://api.example.com/probs/validation-failed"
    title = "Validation failed"
    status_code = 422


class ExternalServiceError(APIException):
    type = "https://api.example.com/probs/external-service"
    title = "Upstream service error"
    status_code = 502


# ==========================================================================
# 3. GLOBAL EXCEPTION HANDLERS
# ==========================================================================

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
    """Catch FastAPI's HTTPException."""
    return problem_response(
        title=f"HTTP {exc.status_code}",
        status_code=exc.status_code,
        detail=str(exc.detail) if exc.detail else None,
        instance=str(request.url.path),
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Pydantic validation errors → 7807."""
    errors = []
    for e in exc.errors():
        errors.append({
            'loc': '.'.join(str(p) for p in e['loc']),
            'msg': e['msg'],
            'type': e['type'],
            'input': str(e.get('input', ''))[:200],
        })

    return problem_response(
        type="https://api.example.com/probs/validation-failed",
        title="Request validation failed",
        status_code=422,
        instance=str(request.url.path),
        errors=errors,
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """Catch-all — generic message, log server-side."""
    import logging
    import uuid

    trace_id = str(uuid.uuid4())
    logging.error(
        f"Unhandled exception trace_id={trace_id}",
        exc_info=exc,
        extra={'trace_id': trace_id, 'path': str(request.url.path)},
    )

    return problem_response(
        title="Internal server error",
        status_code=500,
        detail="An unexpected error occurred. Please contact support with the trace_id below.",
        instance=str(request.url.path),
        trace_id=trace_id,
    )


# ==========================================================================
# 4. USAGE IN ENDPOINTS
# ==========================================================================

# Mock DB
accounts_db = {
    1: {"id": 1, "balance": 100.0, "currency": "USD"},
    2: {"id": 2, "balance": 0.0, "currency": "USD"},
}


class TransactionRequest(BaseModel):
    account_id: int
    amount: float


@app.post("/transactions")
def create_transaction(payload: TransactionRequest):
    account = accounts_db.get(payload.account_id)
    if not account:
        raise ResourceNotFoundError(
            detail=f"Account {payload.account_id} not found",
            account_id=payload.account_id,
        )

    if payload.amount <= 0:
        raise ValidationFailedError(
            detail="Amount must be positive",
            errors=[{'loc': 'amount', 'msg': 'must be > 0', 'value': payload.amount}],
        )

    if account['balance'] < payload.amount:
        raise InsufficientFundsError(
            detail=f"Balance ${account['balance']:.2f}, requested ${payload.amount:.2f}",
            balance=account['balance'],
            requested=payload.amount,
            currency=account['currency'],
        )

    account['balance'] -= payload.amount
    return {"new_balance": account['balance']}


@app.get("/transactions/{tx_id}")
def get_transaction(tx_id: str):
    raise ResourceNotFoundError(
        detail=f"Transaction {tx_id} not found",
        transaction_id=tx_id,
    )


# ==========================================================================
# 5. RATE LIMIT WITH 7807 + Retry-After header
# ==========================================================================

@app.exception_handler(RateLimitedError)
async def rate_limited_handler(request: Request, exc: RateLimitedError):
    retry_after = exc.extensions.get('retry_after_seconds', 60)
    response = problem_response(
        type=exc.type,
        title=exc.title,
        status_code=429,
        detail=exc.detail,
        instance=str(request.url.path),
        **exc.extensions,
    )
    response.headers['Retry-After'] = str(retry_after)
    return response


@app.post("/expensive-action")
async def expensive_action():
    # Pseudo-rate-limit check
    if False:  # placeholder
        raise RateLimitedError(
            detail="Limit: 10 requests per minute",
            retry_after_seconds=60,
            limit=10,
            window_seconds=60,
        )
    return {"ok": True}


# ==========================================================================
# 6. EXTERNAL SERVICE ERROR (502 with details)
# ==========================================================================

import httpx


@app.get("/external-data")
async def external_data():
    try:
        async with httpx.AsyncClient(timeout=5.0) as c:
            resp = await c.get("https://api.partner.example.com/data")
            resp.raise_for_status()
    except httpx.HTTPStatusError as e:
        raise ExternalServiceError(
            detail=f"Upstream returned {e.response.status_code}",
            upstream_status=e.response.status_code,
            upstream_url=str(e.request.url),
        )
    except httpx.RequestError as e:
        raise ExternalServiceError(
            detail="Upstream unreachable",
            upstream_url=str(e.request.url),
            error_kind=type(e).__name__,
        )

    return resp.json()


# ==========================================================================
# 7. LOCALIZED ERRORS
# ==========================================================================

LOCALES = {
    'en': {
        'insufficient-funds': {
            'title': 'Insufficient funds',
            'detail_template': 'Balance ${balance:.2f}, requested ${requested:.2f}',
        },
    },
    'hi': {
        'insufficient-funds': {
            'title': 'अपर्याप्त शेष राशि',
            'detail_template': 'शेष ${balance:.2f}, अनुरोध ${requested:.2f}',
        },
    },
}


def i18n_problem(
    request: Request,
    error_key: str,
    status_code: int,
    **extensions,
):
    lang_header = request.headers.get('accept-language', 'en')
    lang = lang_header.split(',')[0][:2]
    locale = LOCALES.get(lang, LOCALES['en']).get(error_key, {})
    title = locale.get('title', error_key)
    template = locale.get('detail_template', '')
    detail = template.format(**extensions) if template else None

    return problem_response(
        type=f'https://api.example.com/probs/{error_key}',
        title=title,
        status_code=status_code,
        detail=detail,
        instance=str(request.url.path),
        **extensions,
    )


# ==========================================================================
# 8. SAMPLE RESPONSES
# ==========================================================================

# POST /transactions {"account_id": 1, "amount": 200}
# Status: 400
# Content-Type: application/problem+json
# {
#     "type": "https://api.example.com/probs/insufficient-funds",
#     "title": "Insufficient funds",
#     "status": 400,
#     "detail": "Balance $100.00, requested $200.00",
#     "instance": "/transactions",
#     "balance": 100.0,
#     "requested": 200.0,
#     "currency": "USD"
# }
