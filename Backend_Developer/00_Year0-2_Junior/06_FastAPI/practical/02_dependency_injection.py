"""
PHASE 2 FastAPI — Practical 02: Dependency Injection (DI) System
Run: uvicorn 02_dependency_injection:app --reload
Docs: http://127.0.0.1:8000/docs

Topics:
  - Basic Depends()
  - Annotated style (FastAPI 0.95+)
  - DB session dependency (yield)
  - Auth dependency (JWT verify)
  - Nested / chained dependencies
  - Class-based dependencies
  - Dependency overrides in tests
  - Redis / Cache dependency
"""

from __future__ import annotations

import time
from contextlib import asynccontextmanager
from typing import Annotated, Optional

from fastapi import Depends, FastAPI, HTTPException, Query, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from pydantic import BaseModel


# ═══════════════════════════════════════════════════════
# SECTION 1: App Config
# ═══════════════════════════════════════════════════════

SECRET_KEY = "super-secret-key-for-learning"
ALGORITHM  = "HS256"

FAKE_USERS_DB: dict[str, dict] = {
    "alice@example.com": {
        "id": 1, "name": "Alice", "email": "alice@example.com",
        "role": "admin", "is_active": True,
    },
    "bob@example.com": {
        "id": 2, "name": "Bob", "email": "bob@example.com",
        "role": "user", "is_active": True,
    },
    "inactive@example.com": {
        "id": 3, "name": "Inactive User", "email": "inactive@example.com",
        "role": "user", "is_active": False,
    },
}

bearer_scheme = HTTPBearer(auto_error=False)


# ═══════════════════════════════════════════════════════
# SECTION 2: Basic Dependencies
# ═══════════════════════════════════════════════════════

# ─── Simple function dependency ───
def get_pagination(
    skip: int = Query(0, ge=0, description="Records to skip"),
    limit: int = Query(10, ge=1, le=100, description="Max records"),
) -> dict:
    return {"skip": skip, "limit": limit}

# Annotated style — reusable type alias (recommended)
Pagination = Annotated[dict, Depends(get_pagination)]


# ─── Request-info dependency ───
def get_request_info(request: Request) -> dict:
    return {
        "client_ip": request.client.host if request.client else "unknown",
        "user_agent": request.headers.get("user-agent", ""),
        "request_id": request.headers.get("X-Request-ID", ""),
    }

RequestInfo = Annotated[dict, Depends(get_request_info)]


# ═══════════════════════════════════════════════════════
# SECTION 3: DB Session Dependency (yield pattern)
# ═══════════════════════════════════════════════════════

class FakeDB:
    """Simulated async DB session."""
    def __init__(self, conn_id: str):
        self.conn_id = conn_id
        self._closed = False
        print(f"  [DB] Connection opened: {conn_id}")

    async def execute(self, query: str) -> list:
        if self._closed:
            raise RuntimeError("DB connection already closed")
        return [{"query": query, "conn": self.conn_id}]

    async def close(self):
        self._closed = True
        print(f"  [DB] Connection closed: {self.conn_id}")

    async def rollback(self):
        print(f"  [DB] Rollback: {self.conn_id}")


async def get_db():
    """
    DB session dependency with yield.
    - Opens connection BEFORE yield → given to route handler
    - Closes connection AFTER yield → always, even on error
    """
    import uuid
    db = FakeDB(uuid.uuid4().hex[:8])
    try:
        yield db               # route handler gets this
    except Exception:
        await db.rollback()    # rollback on error
        raise
    finally:
        await db.close()       # always close

DB = Annotated[FakeDB, Depends(get_db)]


# ═══════════════════════════════════════════════════════
# SECTION 4: Auth Dependencies
# ═══════════════════════════════════════════════════════

class TokenData(BaseModel):
    user_id: int
    email: str
    role: str


def create_test_token(email: str) -> str:
    """Helper to create tokens for testing (call /token endpoint)."""
    from datetime import datetime, timedelta, timezone
    payload = {
        "sub": email,
        "exp": datetime.now(timezone.utc) + timedelta(hours=1),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
) -> TokenData:
    """
    Dependency: Verifies JWT Bearer token.
    Raises 401 if token is missing/invalid/expired.
    """
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub", "")
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = FAKE_USERS_DB.get(email)
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    if not user["is_active"]:
        raise HTTPException(status_code=403, detail="Inactive user")

    return TokenData(user_id=user["id"], email=user["email"], role=user["role"])


CurrentUser = Annotated[TokenData, Depends(get_current_user)]


# ─── Role-based dependency ───
def require_role(*roles: str):
    def checker(current_user: CurrentUser):
        if current_user.role not in roles:
            raise HTTPException(
                status_code=403,
                detail=f"Role '{current_user.role}' not allowed. Need: {roles}"
            )
        return current_user
    return Depends(checker)


# ═══════════════════════════════════════════════════════
# SECTION 5: Nested (Chained) Dependencies
# ═══════════════════════════════════════════════════════

class AuditLogger:
    """Logs every action with user context — uses CurrentUser."""
    def __init__(self, current_user: CurrentUser):
        self.user = current_user
        self._logs: list[str] = []

    def log(self, action: str):
        entry = f"[AUDIT] user={self.user.email} role={self.user.role} action={action}"
        self._logs.append(entry)
        print(entry)

    @property
    def logs(self) -> list[str]:
        return self._logs


async def get_audit_logger(current_user: CurrentUser) -> AuditLogger:
    """Nested dependency: depends on get_current_user."""
    return AuditLogger(current_user)

AuditLog = Annotated[AuditLogger, Depends(get_audit_logger)]


# ═══════════════════════════════════════════════════════
# SECTION 6: Class-based Dependency
# ═══════════════════════════════════════════════════════

class PaginationParams:
    """Class-based dep — useful when you have multiple related params."""

    def __init__(
        self,
        page: int = Query(1, ge=1),
        page_size: int = Query(20, ge=1, le=100),
        sort_by: str = Query("id", pattern="^(id|name|created_at)$"),
        order: str = Query("asc", pattern="^(asc|desc)$"),
    ):
        self.page = page
        self.page_size = page_size
        self.sort_by = sort_by
        self.order = order

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size


class RateLimiter:
    """Class-based dep with configuration — creates instances per config."""

    def __init__(self, max_calls: int, window_seconds: int):
        self.max_calls = max_calls
        self.window = window_seconds
        self._counts: dict[str, list[float]] = {}

    async def __call__(self, request: Request):
        ip = request.client.host if request.client else "unknown"
        now = time.time()
        window_start = now - self.window

        calls = [t for t in self._counts.get(ip, []) if t > window_start]
        if len(calls) >= self.max_calls:
            raise HTTPException(
                status_code=429,
                detail=f"Rate limit: {self.max_calls} calls per {self.window}s",
                headers={"Retry-After": str(self.window)},
            )
        calls.append(now)
        self._counts[ip] = calls


# Create singleton instances (shared across requests)
strict_limiter  = RateLimiter(max_calls=5,  window_seconds=60)
relaxed_limiter = RateLimiter(max_calls=60, window_seconds=60)


# ═══════════════════════════════════════════════════════
# SECTION 7: Redis / Cache Dependency
# ═══════════════════════════════════════════════════════

class FakeRedis:
    """Simulated Redis — replace with redis.asyncio in production."""
    def __init__(self):
        self._store: dict[str, tuple] = {}  # key → (value, expires_at)
        print("  [Redis] Connected")

    async def get(self, key: str):
        item = self._store.get(key)
        if item and (item[1] is None or item[1] > time.time()):
            return item[0]
        return None

    async def setex(self, key: str, ttl: int, value):
        self._store[key] = (value, time.time() + ttl)

    async def delete(self, key: str):
        self._store.pop(key, None)

    async def close(self):
        print("  [Redis] Disconnected")


_redis_instance: Optional[FakeRedis] = None


async def get_redis() -> FakeRedis:
    """Reuse single Redis connection across requests (lifespan manages it)."""
    return _redis_instance  # type: ignore

Redis = Annotated[FakeRedis, Depends(get_redis)]


# ═══════════════════════════════════════════════════════
# SECTION 8: App Setup + Routes
# ═══════════════════════════════════════════════════════

@asynccontextmanager
async def lifespan(app: FastAPI):
    global _redis_instance
    _redis_instance = FakeRedis()
    yield
    await _redis_instance.close()


app = FastAPI(
    title="FastAPI DI Practical",
    description="Phase 2 — Dependency Injection Patterns",
    version="1.0.0",
    lifespan=lifespan,
)


# ─── Token generator (for testing in Swagger) ───
@app.post("/token", tags=["Auth"])
async def get_token(email: str = Query(..., examples=["alice@example.com"])):
    """Generate test JWT token. Use this in Swagger Authorize button."""
    if email not in FAKE_USERS_DB:
        raise HTTPException(status_code=404, detail="Unknown email")
    token = create_test_token(email)
    return {"access_token": token, "token_type": "bearer"}


# ─── Basic dependency usage ───
@app.get("/products", tags=["Products"])
async def list_products(pagination: Pagination, req_info: RequestInfo):
    """Uses pagination + request info deps."""
    return {
        "pagination": pagination,
        "request_info": req_info,
        "products": [{"id": i, "name": f"Product {i}"} for i in range(1, 6)],
    }


# ─── DB session dependency ───
@app.get("/db-demo", tags=["DB"])
async def db_demo(db: DB):
    """DB session opened before this, closed after."""
    result = await db.execute("SELECT * FROM users")
    return {"conn_id": db.conn_id, "result": result}


# ─── Auth protected route ───
@app.get("/me", tags=["Auth"])
async def get_me(current_user: CurrentUser):
    """Protected: requires valid JWT."""
    return {"user": current_user.model_dump()}


# ─── Role-based route ───
@app.get("/admin/stats", tags=["Admin"])
async def admin_stats(
    current_user: CurrentUser = require_role("admin"),
):
    return {"message": f"Hello Admin {current_user.email}", "total_users": len(FAKE_USERS_DB)}


# ─── Nested dependency ───
@app.post("/orders", tags=["Orders"])
async def create_order(
    item_id: str,
    current_user: CurrentUser,
    audit: AuditLog,
    db: DB,
):
    """Uses nested deps: current_user → audit_logger → db."""
    audit.log(f"create_order item_id={item_id}")
    result = await db.execute(f"INSERT INTO orders (user={current_user.user_id}, item={item_id})")
    return {"order": result, "audit_logs": audit.logs}


# ─── Class-based dep ───
@app.get("/reports", tags=["Reports"])
async def get_reports(
    params: Annotated[PaginationParams, Depends()],
    current_user: CurrentUser,
):
    """Class-based pagination dependency."""
    return {
        "page": params.page,
        "page_size": params.page_size,
        "offset": params.offset,
        "sort": f"{params.sort_by} {params.order}",
        "requested_by": current_user.email,
    }


# ─── Rate-limited route ───
@app.post(
    "/ai/generate",
    tags=["AI"],
    dependencies=[Depends(strict_limiter)],  # 5 calls/min
)
async def generate_ai(prompt: str, current_user: CurrentUser):
    """Rate-limited LLM endpoint — 5 calls/minute per IP."""
    return {"prompt": prompt, "response": f"AI response for: {prompt[:30]}...", "user": current_user.email}


# ─── Cache dependency ───
@app.get("/products/{product_id}", tags=["Products"])
async def get_product_cached(
    product_id: str,
    redis: Redis,
    current_user: CurrentUser,
):
    """Cache-aside pattern using Redis dep."""
    cache_key = f"product:{product_id}"

    # Try cache first
    cached = await redis.get(cache_key)
    if cached:
        return {"source": "cache", "data": cached}

    # Simulate DB fetch
    data = {"id": product_id, "name": f"Product {product_id}", "price": 999.0}

    # Cache for 5 minutes
    await redis.setex(cache_key, 300, data)

    return {"source": "database", "data": data}


# ─── Override deps in tests ───
# In tests/conftest.py:
#
# from fastapi.testclient import TestClient
# from 02_dependency_injection import app, get_current_user, TokenData
#
# def mock_user():
#     return TokenData(user_id=999, email="test@test.com", role="admin")
#
# app.dependency_overrides[get_current_user] = mock_user
# client = TestClient(app)
#
# def test_protected():
#     resp = client.get("/me")
#     assert resp.status_code == 200
#     assert resp.json()["user"]["email"] == "test@test.com"
#
# # Always clean up overrides
# app.dependency_overrides.clear()


@app.get("/", tags=["Root"])
async def root():
    return {
        "message": "FastAPI DI Practical",
        "tip": "Use POST /token?email=alice@example.com to get JWT, then click Authorize",
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("02_dependency_injection:app", host="0.0.0.0", port=8001, reload=True)
