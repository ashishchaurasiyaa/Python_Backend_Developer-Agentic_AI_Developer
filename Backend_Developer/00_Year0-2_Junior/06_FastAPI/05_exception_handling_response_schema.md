# FastAPI — Exception Handling + API Response Standardization
**FastAPI · Year 0-2 | Senior Backend + Agentic AI**

## Quick Concepts
- **Custom exception handlers** = `@app.exception_handler(ExceptionClass)` — global error catch
- **HTTPException** = FastAPI ka standard error — status code + detail
- **RequestValidationError** = Pydantic validation fail → 422 response
- **BaseResponse** = standard wrapper — har response same shape mein
- **Error schema** = consistent error format — clients ko same structure milti hai
- **Domain exceptions** = business logic errors (`UserNotFoundError`) → HTTP errors map karo

---

## Interview Questions & Answers

### Q1: Custom exception handler kaise banate hain? Multiple exceptions handle karo.
**Answer:**
```python
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Any, Optional

app = FastAPI()

# ─── Standard Error Response Schema ───
class ErrorDetail(BaseModel):
    code: str           # machine-readable: "USER_NOT_FOUND"
    message: str        # human-readable: "User with id 42 not found"
    field: Optional[str] = None  # for validation errors

class ErrorResponse(BaseModel):
    success: bool = False
    error: ErrorDetail
    request_id: Optional[str] = None

# ─── Domain Exceptions ───
class AppException(Exception):
    """Base for all domain exceptions."""
    def __init__(self, code: str, message: str, status_code: int = 400):
        self.code = code
        self.message = message
        self.status_code = status_code

class UserNotFoundException(AppException):
    def __init__(self, user_id: int):
        super().__init__(
            code="USER_NOT_FOUND",
            message=f"User with id {user_id} not found",
            status_code=404
        )

class InsufficientFundsException(AppException):
    def __init__(self, required: float, available: float):
        super().__init__(
            code="INSUFFICIENT_FUNDS",
            message=f"Required {required:.2f}, available {available:.2f}",
            status_code=400
        )

class DuplicateEmailException(AppException):
    def __init__(self, email: str):
        super().__init__(
            code="DUPLICATE_EMAIL",
            message=f"Email '{email}' already registered",
            status_code=409
        )

# ─── Exception Handlers ───

@app.exception_handler(AppException)
async def app_exception_handler(request: Request, exc: AppException):
    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorResponse(
            error=ErrorDetail(code=exc.code, message=exc.message),
            request_id=request.headers.get("X-Request-ID")
        ).model_dump()
    )

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Convert Pydantic validation errors to our standard error format."""
    first_error = exc.errors()[0]
    field = ".".join(str(loc) for loc in first_error["loc"] if loc != "body")

    return JSONResponse(
        status_code=422,
        content=ErrorResponse(
            error=ErrorDetail(
                code="VALIDATION_ERROR",
                message=first_error["msg"],
                field=field or None
            ),
            request_id=request.headers.get("X-Request-ID")
        ).model_dump()
    )

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorResponse(
            error=ErrorDetail(
                code=f"HTTP_{exc.status_code}",
                message=str(exc.detail)
            ),
            request_id=request.headers.get("X-Request-ID")
        ).model_dump()
    )

@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """Catch-all — never expose internal error details in production."""
    import logging
    logging.getLogger("app").exception(f"Unhandled error: {exc}")
    return JSONResponse(
        status_code=500,
        content=ErrorResponse(
            error=ErrorDetail(
                code="INTERNAL_ERROR",
                message="An unexpected error occurred"
            )
        ).model_dump()
    )

# ─── Usage in routes ───
@app.get("/users/{user_id}")
async def get_user(user_id: int):
    if user_id == 999:
        raise UserNotFoundException(user_id)  # clean — no HTTP coupling
    return {"id": user_id, "name": "Alice"}
```

---

### Q2: API Response Standardization — BaseResponse pattern kya hai?
**Answer:**
```python
from pydantic import BaseModel
from typing import Generic, TypeVar, Optional, Any
from datetime import datetime, timezone

T = TypeVar("T")

# ─── Standard Response Wrapper ───
class BaseResponse(BaseModel, Generic[T]):
    """
    Every API response uses this wrapper.
    Client code checks 'success' first, then reads 'data' or 'error'.
    """
    success: bool
    data: Optional[T] = None
    error: Optional[ErrorDetail] = None
    meta: Optional[dict[str, Any]] = None
    timestamp: str = ""

    def __init__(self, **data):
        super().__init__(**data)
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()

    @classmethod
    def ok(cls, data: T, meta: dict | None = None) -> "BaseResponse[T]":
        return cls(success=True, data=data, meta=meta)

    @classmethod
    def fail(cls, code: str, message: str, field: str | None = None) -> "BaseResponse[T]":
        return cls(success=False, error=ErrorDetail(code=code, message=message, field=field))


# ─── Response models ───
class UserOut(BaseModel):
    id: int
    name: str
    email: str

class PaginatedData(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    page_size: int
    has_next: bool

# ─── Routes using BaseResponse ───
@app.get("/users/{user_id}", response_model=BaseResponse[UserOut])
async def get_user_v2(user_id: int):
    # Success case
    return BaseResponse.ok(
        data=UserOut(id=user_id, name="Alice", email="alice@example.com")
    )

@app.get("/users", response_model=BaseResponse[PaginatedData[UserOut]])
async def list_users(page: int = 1, page_size: int = 10):
    users = [UserOut(id=i, name=f"User{i}", email=f"u{i}@x.com") for i in range(1, 6)]
    return BaseResponse.ok(
        data=PaginatedData(
            items=users,
            total=100,
            page=page,
            page_size=page_size,
            has_next=page * page_size < 100
        ),
        meta={"query_time_ms": 12}
    )
```

**Response shape — always same:**
```json
// Success
{
  "success": true,
  "data": { "id": 1, "name": "Alice", "email": "alice@example.com" },
  "error": null,
  "meta": null,
  "timestamp": "2024-01-15T10:30:00+00:00"
}

// Error
{
  "success": false,
  "data": null,
  "error": { "code": "USER_NOT_FOUND", "message": "User with id 999 not found" },
  "timestamp": "2024-01-15T10:30:01+00:00"
}
```

---

### Q3: All validation errors kaise show karte hain (ek saath multiple errors)?
**Answer:**
```python
from fastapi.exceptions import RequestValidationError

@app.exception_handler(RequestValidationError)
async def all_validation_errors_handler(request: Request, exc: RequestValidationError):
    """Return ALL validation errors, not just the first one."""
    errors = []
    for error in exc.errors():
        field = ".".join(str(loc) for loc in error["loc"] if loc != "body")
        errors.append({
            "field": field,
            "code": error["type"].upper(),
            "message": error["msg"]
        })

    return JSONResponse(
        status_code=422,
        content={
            "success": False,
            "errors": errors,   # LIST of all errors
            "message": f"{len(errors)} validation error(s)"
        }
    )
```

---

### Q4: Route-level vs app-level error handling — difference?
**Answer:**
```python
# 1. Route-level try/except — for specific business logic
@app.post("/transfer")
async def transfer_funds(from_id: int, to_id: int, amount: float):
    try:
        result = await payment_service.transfer(from_id, to_id, amount)
        return BaseResponse.ok(data=result)
    except InsufficientFundsException as e:
        # Specific handling with extra logging
        logger.warning(f"Transfer failed: {e.message}")
        raise  # re-raise so app-level handler formats it

# 2. App-level handler — global, catches all unhandled exceptions
# (defined with @app.exception_handler above)

# 3. Router-level — for a specific group of routes
from fastapi.routing import APIRouter
from fastapi import Request
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/payments")
# No router-level exception handler in FastAPI — use app-level or route-level
```

---

### Q5: HTTPException vs custom AppException — when to use which?
**Answer:**
```python
# Use HTTPException when:
# - Simple, framework-level errors (auth, not found, forbidden)
# - No domain context needed
raise HTTPException(status_code=404, detail="Item not found")
raise HTTPException(status_code=401, detail="Not authenticated")
raise HTTPException(
    status_code=403,
    detail="Not enough permissions",
    headers={"WWW-Authenticate": "Bearer"}
)

# Use custom AppException when:
# - Domain/business logic errors with specific codes
# - Need machine-readable error codes for frontend
# - Want to add context (which field, which value)
raise UserNotFoundException(user_id=42)
raise InsufficientFundsException(required=1000.0, available=500.0)
raise DuplicateEmailException(email="user@example.com")

# NEVER expose raw Python exceptions — always wrap in a handler
# BAD:
@app.get("/bad")
async def bad_handler():
    data = {}
    return data["missing_key"]  # KeyError leaks to client!

# GOOD: catch-all handler above handles this
```

---

### Q6: Error logging + Sentry integration kaise karte hain?
**Answer:**
```python
import logging
import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration

# In main.py
sentry_sdk.init(
    dsn="https://your-dsn@sentry.io/project",
    integrations=[FastApiIntegration(), SqlalchemyIntegration()],
    traces_sample_rate=0.1,   # 10% of requests traced
    environment="production",
)

app = FastAPI()

@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    # Sentry auto-captures unhandled exceptions via integration
    # For manual capture:
    sentry_sdk.capture_exception(exc)

    logging.getLogger("app").exception(
        "Unhandled error",
        extra={
            "url": str(request.url),
            "method": request.method,
            "request_id": request.headers.get("X-Request-ID")
        }
    )
    return JSONResponse(status_code=500, content={"error": "Internal server error"})
```

---

## Summary Table

| Scenario | Use |
|---|---|
| Auth failed, 401/403 | `HTTPException` |
| Business rule broken | Custom `AppException` |
| Pydantic validation fails | `RequestValidationError` handler |
| All unhandled errors | `Exception` handler (catch-all) |
| Consistent API contract | `BaseResponse[T]` wrapper |
| Machine-readable errors | `code` field in `ErrorDetail` |
