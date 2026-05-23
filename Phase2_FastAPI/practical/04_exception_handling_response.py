"""
PHASE 2 FastAPI — Practical 04: Exception Handling + BaseResponse Pattern
Run: uvicorn 04_exception_handling_response:app --reload
Docs: http://127.0.0.1:8000/docs

Topics:
  - Domain exceptions (AppException subclasses)
  - App-level exception handlers
  - RequestValidationError handler (all errors at once)
  - BaseResponse[T] — standard wrapper for every response
  - ErrorDetail with machine-readable codes
"""

from __future__ import annotations

import uuid
from typing import Annotated, Any, Generic, Optional, TypeVar

from fastapi import FastAPI, HTTPException, Path, Query, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, EmailStr, Field, field_validator

T = TypeVar("T")


# ═══════════════════════════════════════════════════════
# SECTION 1: Standard Response Schema
# ═══════════════════════════════════════════════════════

class ErrorDetail(BaseModel):
    code: str                       # machine-readable: "USER_NOT_FOUND"
    message: str                    # human-readable
    field: Optional[str] = None     # for validation errors


class Meta(BaseModel):
    request_id: Optional[str] = None
    page: Optional[int] = None
    total: Optional[int] = None
    took_ms: Optional[float] = None


class BaseResponse(BaseModel, Generic[T]):
    """
    Standard envelope — every API response uses this.
    Client always checks 'success' first.
    """
    success: bool
    data: Optional[T] = None
    error: Optional[ErrorDetail] = None
    meta: Optional[Meta] = None

    @classmethod
    def ok(cls, data: T, meta: Meta | None = None) -> "BaseResponse[T]":
        return cls(success=True, data=data, meta=meta)

    @classmethod
    def fail(
        cls,
        code: str,
        message: str,
        field: str | None = None,
    ) -> "BaseResponse[None]":
        return cls(success=False, error=ErrorDetail(code=code, message=message, field=field))


class PaginatedResponse(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    page_size: int
    has_next: bool


# ═══════════════════════════════════════════════════════
# SECTION 2: Domain Exceptions
# ═══════════════════════════════════════════════════════

class AppException(Exception):
    """Base domain exception — maps to HTTP response via handler."""
    def __init__(self, code: str, message: str, http_status: int = 400):
        self.code = code
        self.message = message
        self.http_status = http_status
        super().__init__(message)


class UserNotFoundException(AppException):
    def __init__(self, user_id: int):
        super().__init__(
            code="USER_NOT_FOUND",
            message=f"User with id {user_id} not found",
            http_status=404,
        )


class DuplicateEmailException(AppException):
    def __init__(self, email: str):
        super().__init__(
            code="DUPLICATE_EMAIL",
            message=f"Email '{email}' is already registered",
            http_status=409,
        )


class InsufficientStockException(AppException):
    def __init__(self, product_id: int, requested: int, available: int):
        super().__init__(
            code="INSUFFICIENT_STOCK",
            message=f"Product {product_id}: requested {requested}, available {available}",
            http_status=400,
        )


class PermissionDeniedException(AppException):
    def __init__(self, action: str):
        super().__init__(
            code="PERMISSION_DENIED",
            message=f"You don't have permission to: {action}",
            http_status=403,
        )


# ═══════════════════════════════════════════════════════
# SECTION 3: App + Exception Handlers
# ═══════════════════════════════════════════════════════

app = FastAPI(
    title="FastAPI Exception Handling + BaseResponse",
    description="Phase 2 — Standard error + response pattern",
    version="1.0.0",
)


@app.exception_handler(AppException)
async def app_exception_handler(request: Request, exc: AppException):
    """Handle all domain exceptions → standard error response."""
    return JSONResponse(
        status_code=exc.http_status,
        content=BaseResponse.fail(
            code=exc.code,
            message=exc.message,
        ).model_dump(),
        headers={"X-Request-ID": getattr(request.state, "request_id", str(uuid.uuid4()))},
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """
    Return ALL Pydantic validation errors — not just the first.
    Groups them into a list for the client.
    """
    errors = []
    for err in exc.errors():
        # loc = ("body", "email") → field = "email"
        field = ".".join(str(l) for l in err["loc"] if l != "body")
        errors.append({
            "field": field or None,
            "code": err["type"].upper(),
            "message": err["msg"],
        })

    return JSONResponse(
        status_code=422,
        content={
            "success": False,
            "error": {
                "code": "VALIDATION_ERROR",
                "message": f"{len(errors)} validation error(s)",
            },
            "errors": errors,  # all field errors
            "data": None,
        },
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Wrap standard HTTPException into BaseResponse format."""
    return JSONResponse(
        status_code=exc.status_code,
        content=BaseResponse.fail(
            code=f"HTTP_{exc.status_code}",
            message=str(exc.detail),
        ).model_dump(),
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """Catch-all — never expose internal details in production."""
    import logging
    logging.getLogger("app").exception(f"Unhandled: {exc}")
    return JSONResponse(
        status_code=500,
        content=BaseResponse.fail(
            code="INTERNAL_ERROR",
            message="An unexpected error occurred. Please try again.",
        ).model_dump(),
    )


# ═══════════════════════════════════════════════════════
# SECTION 4: Pydantic Models
# ═══════════════════════════════════════════════════════

class UserCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=50)
    email: EmailStr
    age: int = Field(..., ge=1, le=120)
    password: str = Field(..., min_length=8)

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if not any(c.isupper() for c in v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one digit")
        return v


class UserOut(BaseModel):
    id: int
    name: str
    email: str
    age: int


class OrderCreate(BaseModel):
    product_id: int
    quantity: int = Field(..., ge=1)


class OrderOut(BaseModel):
    id: int
    product_id: int
    quantity: int
    total_price: float


# ─── Fake data stores ───
USERS: dict[int, dict] = {
    1: {"id": 1, "name": "Alice", "email": "alice@example.com", "age": 28},
    2: {"id": 2, "name": "Bob",   "email": "bob@example.com",   "age": 32},
}
REGISTERED_EMAILS = {"alice@example.com", "bob@example.com"}
PRODUCTS: dict[int, dict] = {
    1: {"id": 1, "name": "Laptop",   "price": 75000.0, "stock": 5},
    2: {"id": 2, "name": "Keyboard", "price": 2500.0,  "stock": 0},
    3: {"id": 3, "name": "Monitor",  "price": 18000.0, "stock": 10},
}
ORDERS: dict[int, dict] = {}
_order_counter = 0


# ═══════════════════════════════════════════════════════
# SECTION 5: Routes
# ═══════════════════════════════════════════════════════

@app.get("/", tags=["Root"])
async def root():
    return {"message": "Exception Handling + BaseResponse — visit /docs"}


# ─── User routes ───
@app.get("/users", response_model=BaseResponse[PaginatedResponse[UserOut]], tags=["Users"])
async def list_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
):
    users = list(USERS.values())
    start = (page - 1) * page_size
    page_items = users[start : start + page_size]

    return BaseResponse.ok(
        data=PaginatedResponse(
            items=page_items,
            total=len(users),
            page=page,
            page_size=page_size,
            has_next=(start + page_size) < len(users),
        ),
        meta=Meta(total=len(users), page=page),
    )


@app.get("/users/{user_id}", response_model=BaseResponse[UserOut], tags=["Users"])
async def get_user(user_id: int = Path(..., ge=1)):
    user = USERS.get(user_id)
    if not user:
        raise UserNotFoundException(user_id)  # clean domain exception
    return BaseResponse.ok(data=UserOut(**user))


@app.post("/users", response_model=BaseResponse[UserOut], status_code=201, tags=["Users"])
async def create_user(body: UserCreate):
    """
    Test validation errors: POST with bad data to see all errors at once.
    Try: {"name": "A", "email": "bad-email", "age": 200, "password": "weak"}
    """
    if body.email in REGISTERED_EMAILS:
        raise DuplicateEmailException(body.email)

    new_id = max(USERS.keys(), default=0) + 1
    user = {"id": new_id, "name": body.name, "email": body.email, "age": body.age}
    USERS[new_id] = user
    REGISTERED_EMAILS.add(body.email)

    return BaseResponse.ok(data=UserOut(**user))


# ─── Order routes — demonstrates multi-exception scenarios ───
@app.post("/orders", response_model=BaseResponse[OrderOut], status_code=201, tags=["Orders"])
async def create_order(body: OrderCreate):
    """
    Demonstrates: InsufficientStockException, UserNotFoundException patterns.
    Try: product_id=2 (stock=0), product_id=99 (not found)
    """
    global _order_counter

    # Check product exists
    product = PRODUCTS.get(body.product_id)
    if not product:
        raise HTTPException(status_code=404, detail=f"Product {body.product_id} not found")

    # Check stock
    if product["stock"] < body.quantity:
        raise InsufficientStockException(
            product_id=body.product_id,
            requested=body.quantity,
            available=product["stock"],
        )

    # Create order
    _order_counter += 1
    order = {
        "id": _order_counter,
        "product_id": body.product_id,
        "quantity": body.quantity,
        "total_price": product["price"] * body.quantity,
    }
    ORDERS[_order_counter] = order
    product["stock"] -= body.quantity

    return BaseResponse.ok(data=OrderOut(**order))


# ─── Force-trigger various error scenarios for testing ───
@app.get("/errors/not-found", tags=["Error Demos"])
async def demo_not_found():
    raise UserNotFoundException(user_id=999)


@app.get("/errors/conflict", tags=["Error Demos"])
async def demo_conflict():
    raise DuplicateEmailException(email="test@example.com")


@app.get("/errors/forbidden", tags=["Error Demos"])
async def demo_forbidden():
    raise PermissionDeniedException(action="delete_all_users")


@app.get("/errors/unhandled", tags=["Error Demos"])
async def demo_unhandled():
    """This triggers the catch-all 500 handler."""
    data: dict = {}
    return data["missing_key"]  # KeyError — caught by unhandled handler


@app.post("/errors/validation-demo", tags=["Error Demos"])
async def demo_validation(body: UserCreate):
    """
    Try sending invalid data to see all validation errors at once:
    {
        "name": "A",
        "email": "not-an-email",
        "age": 999,
        "password": "weak"
    }
    """
    return BaseResponse.ok(data={"message": "Valid data received"})


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("04_exception_handling_response:app", host="0.0.0.0", port=8003, reload=True)
