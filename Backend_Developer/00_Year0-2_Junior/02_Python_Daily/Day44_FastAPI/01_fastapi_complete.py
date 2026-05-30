"""
Day44 — FastAPI Deep Dive
==========================
Level: Intermediate → Advanced
Target: 5 YOE Python Backend Developer Interview

Topics Covered:
  1. Basics — app creation, path/query params, request body (Pydantic)
  2. Path Operations — GET/POST/PUT/DELETE/PATCH, status codes, response_model
  3. Dependency Injection — Depends(), nested deps, dep with yield (DB session)
  4. Middleware — BaseHTTPMiddleware, timing, correlation-id
  5. Background Tasks — BackgroundTasks, fire-and-forget
  6. Lifespan Events — asynccontextmanager lifespan (new style)
  7. WebSockets — WebSocket endpoint, connection manager with broadcast
  8. Error Handling — HTTPException, custom handlers, RequestValidationError
  9. Security — OAuth2PasswordBearer, JWT with jose, get_current_user dep
 10. Routers — APIRouter, prefix, tags, include_router
 11. Testing — TestClient, AsyncClient (httpx), override_dependencies
 12. Advanced Patterns — Repository, Request ID, Rate Limiting, Pagination
"""

# ============================================================
# IMPORTS
# ============================================================
from __future__ import annotations

import asyncio
import logging
import time
import uuid
from collections.abc import AsyncGenerator, Generator
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from typing import Annotated, Any

import httpx
import pytest
import redis.asyncio as aioredis
from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    FastAPI,
    HTTPException,
    Request,
    Response,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.base import BaseHTTPMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.testclient import TestClient
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel, EmailStr, Field, field_validator
from starlette.middleware.base import RequestResponseEndpoint

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ============================================================
# SECTION 1: BASICS — Pydantic Models & App Setup
# ============================================================

# --- Pydantic Models ---

class Address(BaseModel):
    street: str
    city: str
    country: str = "India"


class UserBase(BaseModel):
    name: str = Field(..., min_length=2, max_length=100, examples=["Alice"])
    email: EmailStr
    age: int = Field(..., ge=1, le=120)

    @field_validator("name")
    @classmethod
    def name_must_not_be_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("name cannot be blank")
        return v.title()


class UserCreate(UserBase):
    password: str = Field(..., min_length=8)
    address: Address | None = None


class UserResponse(UserBase):
    id: int
    created_at: datetime
    is_active: bool = True

    model_config = {"from_attributes": True}


class UserUpdate(BaseModel):
    name: str | None = None
    age: int | None = None


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class TokenData(BaseModel):
    username: str | None = None


# ============================================================
# SECTION 2: PATH OPERATIONS — Full CRUD with status codes
# ============================================================

# In-memory "database" for demo purposes
FAKE_USERS_DB: dict[int, dict] = {
    1: {
        "id": 1,
        "name": "Alice",
        "email": "alice@example.com",
        "age": 30,
        "hashed_password": "$2b$12$placeholder",
        "created_at": datetime.now(timezone.utc),
        "is_active": True,
    }
}
_next_id = 2


def get_next_id() -> int:
    global _next_id
    uid = _next_id
    _next_id += 1
    return uid


# ============================================================
# SECTION 6: LIFESPAN EVENTS — Startup / Shutdown (new style)
# ============================================================

redis_client: aioredis.Redis | None = None


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    New-style lifespan replaces @app.on_event("startup"/"shutdown").
    Code before 'yield' = startup.
    Code after  'yield' = shutdown.
    """
    global redis_client
    logger.info("Starting up — connecting to Redis...")
    # In production: redis_client = await aioredis.from_url("redis://localhost:6379")
    redis_client = None  # skipped for demo; remove in real app
    logger.info("Startup complete.")

    yield  # Application runs here

    logger.info("Shutting down — closing Redis connection...")
    if redis_client:
        await redis_client.aclose()
    logger.info("Shutdown complete.")


# ============================================================
# APP CREATION
# ============================================================

app = FastAPI(
    title="FastAPI Deep Dive",
    description="Comprehensive FastAPI patterns for senior backend interviews",
    version="1.0.0",
    lifespan=lifespan,
)

# ============================================================
# SECTION 4: MIDDLEWARE
# ============================================================

class TimingMiddleware(BaseHTTPMiddleware):
    """Logs how long each request takes."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        start = time.perf_counter()
        response = await call_next(request)
        duration_ms = (time.perf_counter() - start) * 1000
        response.headers["X-Process-Time-Ms"] = f"{duration_ms:.2f}"
        logger.info(
            "method=%s path=%s status=%d duration_ms=%.2f",
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
        )
        return response


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """
    Injects/propagates a correlation-id header for distributed tracing.
    Frontend sends X-Correlation-ID; if missing, we generate one.
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        correlation_id = request.headers.get("X-Correlation-ID", str(uuid.uuid4()))
        # Store on request state so route handlers can access it
        request.state.correlation_id = correlation_id
        response = await call_next(request)
        response.headers["X-Correlation-ID"] = correlation_id
        return response


class RequestIdMiddleware(BaseHTTPMiddleware):
    """Unique request-id per request (different from correlation-id)."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        request.state.request_id = str(uuid.uuid4())
        response = await call_next(request)
        response.headers["X-Request-ID"] = request.state.request_id
        return response


# Order matters: first added = outermost wrapper
app.add_middleware(TimingMiddleware)
app.add_middleware(CorrelationIdMiddleware)
app.add_middleware(RequestIdMiddleware)

# ============================================================
# SECTION 8: ERROR HANDLING
# ============================================================

class AppError(Exception):
    """Base custom exception."""

    def __init__(self, message: str, error_code: str = "APP_ERROR") -> None:
        self.message = message
        self.error_code = error_code
        super().__init__(message)


class UserNotFoundError(AppError):
    def __init__(self, user_id: int) -> None:
        super().__init__(f"User {user_id} not found", "USER_NOT_FOUND")


@app.exception_handler(UserNotFoundError)
async def user_not_found_handler(request: Request, exc: UserNotFoundError) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={"error_code": exc.error_code, "detail": exc.message},
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """
    Override FastAPI's default 422 handler to return a cleaner payload.
    Also logs the error for observability.
    """
    logger.warning("Validation error on %s: %s", request.url, exc.errors())
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "detail": "Request validation failed",
            "errors": exc.errors(),
        },
    )


@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={"error_code": exc.error_code, "detail": exc.message},
    )


# ============================================================
# SECTION 3: DEPENDENCY INJECTION
# ============================================================

# --- Simple dependency ---

def get_db() -> Generator[dict, None, None]:
    """
    Simulates a DB session with yield.
    In real app: yield SessionLocal(); finally: db.close()
    """
    db = FAKE_USERS_DB  # pretend this is a real Session
    try:
        yield db
    finally:
        pass  # db.close() in real code


DBDep = Annotated[dict, Depends(get_db)]


# --- Nested dependency ---

def get_current_settings() -> dict:
    return {"max_page_size": 100, "app_name": "FastAPI Demo"}


def get_pagination(
    limit: int = 10,
    offset: int = 0,
    settings: dict = Depends(get_current_settings),
) -> dict:
    max_size = settings["max_page_size"]
    limit = min(limit, max_size)
    return {"limit": limit, "offset": offset}


PaginationDep = Annotated[dict, Depends(get_pagination)]


# ============================================================
# SECTION 9: SECURITY — JWT + OAuth2
# ============================================================

SECRET_KEY = "CHANGE_ME_IN_PRODUCTION_USE_SECRETS_MODULE"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token")


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def hash_password(plain: str) -> str:
    return pwd_context.hash(plain)


def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=15))
    to_encode["exp"] = expire
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def authenticate_user(db: dict, username: str, password: str) -> dict | None:
    user = next((u for u in db.values() if u["email"] == username), None)
    if not user:
        return None
    if not verify_password(password, user.get("hashed_password", "")):
        return None
    return user


async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    db: DBDep,
) -> dict:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str | None = payload.get("sub")
        if username is None:
            raise credentials_exception
        token_data = TokenData(username=username)
    except JWTError:
        raise credentials_exception

    user = next((u for u in db.values() if u["email"] == token_data.username), None)
    if user is None:
        raise credentials_exception
    return user


CurrentUserDep = Annotated[dict, Depends(get_current_user)]


# ============================================================
# SECTION 10: ROUTERS
# ============================================================

# --- Auth Router ---
auth_router = APIRouter(prefix="/auth", tags=["Authentication"])


@auth_router.post("/token", response_model=Token)
async def login_for_access_token(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: DBDep,
) -> Token:
    user = authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token = create_access_token(
        data={"sub": user["email"]},
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    )
    return Token(access_token=access_token)


# --- Users Router ---
users_router = APIRouter(prefix="/users", tags=["Users"])


@users_router.get("/", response_model=list[UserResponse])
async def list_users(pagination: PaginationDep, db: DBDep) -> list[dict]:
    """GET with query params handled via dependency injection."""
    users = list(db.values())
    start = pagination["offset"]
    end = start + pagination["limit"]
    return users[start:end]


@users_router.get("/me", response_model=UserResponse)
async def get_me(current_user: CurrentUserDep) -> dict:
    """Protected endpoint — requires valid JWT."""
    return current_user


@users_router.get("/{user_id}", response_model=UserResponse)
async def get_user(user_id: int, db: DBDep) -> dict:
    """Path parameter example with custom exception."""
    if user_id not in db:
        raise UserNotFoundError(user_id)
    return db[user_id]


@users_router.post("/", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(payload: UserCreate, db: DBDep) -> dict:
    """POST with request body (Pydantic model)."""
    # Check duplicate email
    if any(u["email"] == payload.email for u in db.values()):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Email {payload.email} already registered",
        )
    uid = get_next_id()
    user = {
        "id": uid,
        "name": payload.name,
        "email": payload.email,
        "age": payload.age,
        "hashed_password": hash_password(payload.password),
        "created_at": datetime.now(timezone.utc),
        "is_active": True,
    }
    db[uid] = user
    return user


@users_router.put("/{user_id}", response_model=UserResponse)
async def replace_user(user_id: int, payload: UserCreate, db: DBDep) -> dict:
    """PUT = full replacement."""
    if user_id not in db:
        raise UserNotFoundError(user_id)
    user = db[user_id]
    user.update(
        name=payload.name,
        email=payload.email,
        age=payload.age,
        hashed_password=hash_password(payload.password),
    )
    return user


@users_router.patch("/{user_id}", response_model=UserResponse)
async def partial_update_user(user_id: int, payload: UserUpdate, db: DBDep) -> dict:
    """PATCH = partial update. Only supplied fields are updated."""
    if user_id not in db:
        raise UserNotFoundError(user_id)
    user = db[user_id]
    update_data = payload.model_dump(exclude_unset=True)
    user.update(update_data)
    return user


@users_router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(user_id: int, db: DBDep) -> None:
    """DELETE returns 204 No Content on success."""
    if user_id not in db:
        raise UserNotFoundError(user_id)
    del db[user_id]


# Include routers into the app
app.include_router(auth_router)
app.include_router(users_router)

# ============================================================
# SECTION 5: BACKGROUND TASKS
# ============================================================

def send_welcome_email(email: str, name: str) -> None:
    """
    Fire-and-forget task. Runs in the background after response is sent.
    In production, use Celery for reliability (this is not retried on failure).
    """
    logger.info("Sending welcome email to %s <%s>", name, email)
    time.sleep(2)  # simulate email sending latency
    logger.info("Welcome email sent to %s", email)


def generate_user_report(user_id: int) -> None:
    """Simulate a heavy report generation task."""
    logger.info("Generating report for user %d", user_id)
    time.sleep(5)
    logger.info("Report ready for user %d", user_id)


@app.post("/users/{user_id}/send-welcome", status_code=status.HTTP_202_ACCEPTED)
async def send_welcome(
    user_id: int,
    background_tasks: BackgroundTasks,
    db: DBDep,
) -> dict:
    """
    Returns 202 immediately; email is sent in background.
    BackgroundTasks runs after the response is sent to the client.
    """
    if user_id not in db:
        raise UserNotFoundError(user_id)
    user = db[user_id]
    background_tasks.add_task(send_welcome_email, user["email"], user["name"])
    background_tasks.add_task(generate_user_report, user_id)
    return {"message": "Welcome email queued", "user_id": user_id}


# ============================================================
# SECTION 7: WEBSOCKETS
# ============================================================

class ConnectionManager:
    """Manages active WebSocket connections and broadcasts messages."""

    def __init__(self) -> None:
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info("WebSocket connected. Total: %d", len(self.active_connections))

    def disconnect(self, websocket: WebSocket) -> None:
        self.active_connections.remove(websocket)
        logger.info("WebSocket disconnected. Total: %d", len(self.active_connections))

    async def send_personal(self, message: str, websocket: WebSocket) -> None:
        await websocket.send_text(message)

    async def broadcast(self, message: str) -> None:
        """Send message to ALL connected clients."""
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except Exception:
                disconnected.append(connection)
        for ws in disconnected:
            self.active_connections.remove(ws)


manager = ConnectionManager()


@app.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str) -> None:
    """
    WebSocket endpoint for real-time chat/notifications.
    Protocol: client sends text, server broadcasts to all.
    """
    await manager.connect(websocket)
    await manager.broadcast(f"[Server] {client_id} joined the room.")
    try:
        while True:
            data = await websocket.receive_text()
            await manager.broadcast(f"[{client_id}]: {data}")
    except WebSocketDisconnect:
        manager.disconnect(websocket)
        await manager.broadcast(f"[Server] {client_id} left the room.")


# ============================================================
# SECTION 12: ADVANCED PATTERNS
# ============================================================

# --- 12a. Repository Pattern with Depends ---

class UserRepository:
    """
    Abstracts data access. In real code, this wraps SQLAlchemy session.
    Injected via Depends — easy to swap for testing.
    """

    def __init__(self, db: dict) -> None:
        self.db = db

    def find_by_id(self, user_id: int) -> dict | None:
        return self.db.get(user_id)

    def find_by_email(self, email: str) -> dict | None:
        return next((u for u in self.db.values() if u["email"] == email), None)

    def save(self, user: dict) -> dict:
        self.db[user["id"]] = user
        return user

    def delete(self, user_id: int) -> None:
        self.db.pop(user_id, None)

    def list_all(self, limit: int = 10, offset: int = 0) -> list[dict]:
        items = list(self.db.values())
        return items[offset : offset + limit]


def get_user_repository(db: DBDep) -> UserRepository:
    return UserRepository(db)


UserRepoDep = Annotated[UserRepository, Depends(get_user_repository)]


@app.get("/v2/users/{user_id}", response_model=UserResponse, tags=["V2 Users"])
async def get_user_v2(user_id: int, repo: UserRepoDep) -> dict:
    """Repository pattern — decouples route from data access logic."""
    user = repo.find_by_id(user_id)
    if not user:
        raise UserNotFoundError(user_id)
    return user


# --- 12b. Rate Limiting Middleware with Redis ---

class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Sliding window rate limiter using Redis.
    Allows max_requests per window_seconds per IP.

    In production: Use a library like slowapi or implement this with
    Redis ZADD/ZREMRANGEBYSCORE for true sliding window.
    """

    def __init__(
        self,
        app: Any,
        max_requests: int = 100,
        window_seconds: int = 60,
    ) -> None:
        super().__init__(app)
        self.max_requests = max_requests
        self.window_seconds = window_seconds

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if redis_client is None:
            # Redis not available in demo — skip rate limiting
            return await call_next(request)

        client_ip = request.client.host if request.client else "unknown"
        key = f"rate_limit:{client_ip}"
        now = time.time()
        window_start = now - self.window_seconds

        pipe = redis_client.pipeline()
        pipe.zremrangebyscore(key, "-inf", window_start)  # Remove old entries
        pipe.zadd(key, {str(now): now})                   # Add current request
        pipe.zcard(key)                                    # Count requests in window
        pipe.expire(key, self.window_seconds)
        results = await pipe.execute()
        request_count = results[2]

        if request_count > self.max_requests:
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={"detail": "Rate limit exceeded. Try again later."},
                headers={"Retry-After": str(self.window_seconds)},
            )
        return await call_next(request)


# Uncomment to enable: app.add_middleware(RateLimitMiddleware, max_requests=60, window_seconds=60)


# --- 12c. Pagination Patterns ---

class PaginatedResponse(BaseModel):
    items: list[Any]
    total: int
    limit: int
    offset: int
    has_next: bool
    has_prev: bool


@app.get("/users-paginated/", response_model=PaginatedResponse, tags=["Pagination"])
async def list_users_paginated(
    db: DBDep,
    limit: int = Field(default=10, ge=1, le=100),
    offset: int = Field(default=0, ge=0),
) -> dict:
    """Limit/offset pagination — simple but can be slow on large datasets."""
    all_users = list(db.values())
    total = len(all_users)
    items = all_users[offset : offset + limit]
    return {
        "items": items,
        "total": total,
        "limit": limit,
        "offset": offset,
        "has_next": offset + limit < total,
        "has_prev": offset > 0,
    }


class CursorPaginatedResponse(BaseModel):
    items: list[Any]
    next_cursor: int | None
    has_next: bool


@app.get("/users-cursor/", response_model=CursorPaginatedResponse, tags=["Pagination"])
async def list_users_cursor(
    db: DBDep,
    cursor: int | None = None,  # last seen user_id
    limit: int = 10,
) -> dict:
    """
    Cursor-based pagination — stable under inserts/deletes, ideal for feeds.
    Cursor = last seen ID. Returns items with ID > cursor.
    """
    all_users = sorted(db.values(), key=lambda u: u["id"])
    if cursor is not None:
        all_users = [u for u in all_users if u["id"] > cursor]
    items = all_users[:limit]
    has_next = len(all_users) > limit
    next_cursor = items[-1]["id"] if items and has_next else None
    return {"items": items, "next_cursor": next_cursor, "has_next": has_next}


# ============================================================
# ROOT HEALTH CHECK
# ============================================================

@app.get("/health", tags=["Health"])
async def health_check(request: Request) -> dict:
    return {
        "status": "ok",
        "request_id": getattr(request.state, "request_id", None),
        "correlation_id": getattr(request.state, "correlation_id", None),
    }


# ============================================================
# SECTION 11: TESTING
# ============================================================

# --- TestClient (sync) ---

def test_health_check() -> None:
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_create_and_get_user() -> None:
    client = TestClient(app)
    payload = {
        "name": "Bob",
        "email": "bob@example.com",
        "age": 25,
        "password": "securepass",
    }
    create_resp = client.post("/users/", json=payload)
    assert create_resp.status_code == 201
    user_id = create_resp.json()["id"]

    get_resp = client.get(f"/users/{user_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["email"] == "bob@example.com"


def test_user_not_found() -> None:
    client = TestClient(app)
    response = client.get("/users/99999")
    assert response.status_code == 404
    assert response.json()["error_code"] == "USER_NOT_FOUND"


# --- Dependency Override for Testing ---

def override_get_db() -> Generator[dict, None, None]:
    """Use a fresh in-memory DB for each test."""
    test_db: dict = {}
    yield test_db


def test_with_dependency_override() -> None:
    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    try:
        # Fresh DB — list should be empty
        response = client.get("/users/")
        assert response.status_code == 200
        assert response.json() == []
    finally:
        app.dependency_overrides.clear()  # Always clean up!


# --- AsyncClient (httpx) for async tests ---

@pytest.mark.anyio
async def test_async_health_check() -> None:
    """Use httpx.AsyncClient for testing async endpoints."""
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/health")
    assert response.status_code == 200


# ============================================================
# DEMO: Running with uvicorn
# ============================================================

if __name__ == "__main__":
    import uvicorn

    # uvicorn 01_fastapi_complete:app --reload --port 8000
    uvicorn.run("01_fastapi_complete:app", host="0.0.0.0", port=8000, reload=True)


# ============================================================
# INTERVIEW Q&A (20 Questions)
# ============================================================

"""
=== FastAPI Interview Q&A — Senior Level ===

Q1. What is the difference between FastAPI's dependency injection and a simple
    function call?
A1. Depends() is declarative: FastAPI resolves the dependency graph, handles
    caching (same dep called once per request by default), supports yield for
    teardown, and makes mocking trivial via dependency_overrides. A plain
    function call gives you none of this.

Q2. When would you use BackgroundTasks vs Celery?
A2. BackgroundTasks runs in the same process after the response is sent — no
    retry, no persistence. Use it for lightweight fire-and-forget (e.g., audit
    log). Celery has a broker, retry logic, scheduling, and monitoring; use it
    for reliability-critical jobs (email, payments, heavy processing).

Q3. Explain how dependency_with_yield works (the DB session pattern).
A3. FastAPI calls the generator, gives you what's yielded, runs the route
    handler, then resumes the generator after yield (the finally block). This
    guarantees cleanup (db.close()) even if the route raises an exception.

Q4. What is the difference between response_model and the return type hint?
A4. response_model controls serialization/filtering of the outgoing JSON and
    generates the OpenAPI docs. The return type hint is used by type checkers
    (mypy). response_model takes precedence for the actual HTTP response.

Q5. How does FastAPI handle validation errors by default?
A5. Pydantic raises ValidationError internally; FastAPI catches it and returns
    HTTP 422 with a structured JSON body listing each field error. You can
    override this with @app.exception_handler(RequestValidationError).

Q6. What is the difference between PUT and PATCH semantics?
A6. PUT = idempotent full replacement (all fields required). PATCH = partial
    update (only supplied fields). In FastAPI, use model_dump(exclude_unset=True)
    with a Pydantic model that has all Optional fields for PATCH.

Q7. How do you implement request-scoped state in FastAPI middleware?
A7. Store data on request.state (e.g., request.state.user_id = ...). It's a
    SimpleNamespace — not thread-local, but safe because FastAPI is async and
    each request has its own Request object.

Q8. Explain the new lifespan pattern vs the deprecated on_event.
A8. @asynccontextmanager lifespan(app) is the modern approach. Code before
    yield = startup, after yield = shutdown. It's a single context manager,
    composable, and avoids the global @app.on_event decorator pattern.

Q9. How do you share a connection pool (e.g., Redis, DB) across requests
    without creating a new connection per request?
A9. Create the pool at startup (in lifespan) and store it as a module-level
    variable or in app.state. The dependency just references app.state.redis —
    the pool is shared, individual connections are checked out and returned.

Q10. What is the order of middleware execution in FastAPI?
A10. Middleware added last is executed first (innermost). Add middleware in
     reverse order of desired execution. The actual request flow is:
     outermost middleware → ... → innermost middleware → route handler.

Q11. How do you test a FastAPI endpoint that has an external dependency
     (e.g., DB, Redis)?
A11. Use app.dependency_overrides[original_dep] = mock_dep before the test,
     and clear it in a finally block. For async tests, use httpx.AsyncClient
     with app=app, base_url="http://test".

Q12. What is OAuth2PasswordBearer and what does it do?
A12. It's a FastAPI security scheme that reads the Bearer token from the
     Authorization header. It also marks the endpoint as secured in OpenAPI
     docs (shows a lock icon). You then decode/validate the token in
     get_current_user.

Q13. Explain cursor-based vs offset-based pagination and when to prefer each.
A13. Offset-based: simple, but slow on large tables (DB must scan N rows) and
     unstable (inserts shift pages). Cursor-based: uses an opaque cursor (e.g.,
     last seen ID or timestamp), O(log N) with index, stable. Prefer cursor for
     large datasets, infinite scroll, and real-time feeds.

Q14. How does FastAPI's OpenAPI schema generation work?
A14. FastAPI introspects route decorators, type hints, Pydantic models, and
     Depends() at startup to build the OpenAPI JSON. Pydantic's JSON Schema
     is embedded. The /docs (Swagger UI) and /redoc endpoints serve this schema.

Q15. What happens if a middleware raises an exception?
A15. It propagates up and FastAPI returns a 500 Internal Server Error (or the
     relevant HTTP exception). You should catch exceptions inside middleware
     and return appropriate Response objects instead of letting them propagate.

Q16. How do you handle file uploads in FastAPI?
A16. Use UploadFile and File from fastapi. Declare the parameter as
     file: UploadFile = File(...). Read content with await file.read() or
     stream with file.file. For large files, stream to disk to avoid OOM.

Q17. What is the difference between APIRouter and the main app for including
     routes?
A17. APIRouter is a mini-app for organizing routes. It supports prefix, tags,
     dependencies (applied to all routes in the router), and responses. You
     include it with app.include_router(). No functional difference at runtime.

Q18. How do you implement versioned APIs in FastAPI?
A18. Three common approaches:
     (a) URL prefix: /v1/, /v2/ via APIRouter prefix
     (b) Header versioning: read Accept-Version in middleware
     (c) Subdomain: handled at the load balancer/Nginx level
     URL prefix is most common and easiest to document in OpenAPI.

Q19. How does FastAPI achieve high performance compared to Flask?
A19. FastAPI uses Starlette (ASGI) under the hood, enabling true async I/O
     without blocking threads. Pydantic v2 (Rust-based) provides fast
     validation. The event loop handles thousands of concurrent connections
     without threading overhead. Flask is WSGI (sync) by default.

Q20. Describe a pattern for handling idempotency in POST requests.
A20. Accept an Idempotency-Key header from the client. On arrival, check Redis:
     if key exists, return the cached response. If not, process the request,
     cache the response in Redis with a TTL (e.g., 24h), and return it. This
     prevents duplicate operations (e.g., double payments) on retried requests.
"""
