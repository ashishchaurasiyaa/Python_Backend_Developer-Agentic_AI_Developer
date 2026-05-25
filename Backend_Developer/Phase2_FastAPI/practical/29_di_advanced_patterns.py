"""
FastAPI DI Advanced — Production Patterns
"""

import asyncio
from contextlib import asynccontextmanager
from typing import AsyncIterator, Annotated

from fastapi import FastAPI, Depends, HTTPException, Request, BackgroundTasks
from fastapi.testclient import TestClient


# ==========================================================================
# 1. APP-SCOPED RESOURCES via Lifespan
# ==========================================================================

class DBEngine:
    """Mock DB engine."""
    async def connect(self):
        print("DB connected")

    async def close(self):
        print("DB closed")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    engine = DBEngine()
    await engine.connect()
    app.state.db_engine = engine
    app.state.redis_client = "redis-mock"
    yield
    # Shutdown
    await engine.close()


app = FastAPI(lifespan=lifespan)


# ==========================================================================
# 2. REQUEST-SCOPED DB SESSION (yield pattern)
# ==========================================================================

class DBSession:
    def __init__(self):
        self.changes = []

    async def commit(self):
        print(f"COMMIT {self.changes}")

    async def rollback(self):
        print(f"ROLLBACK {self.changes}")


async def get_db_session(request: Request) -> AsyncIterator[DBSession]:
    """Per-request session with commit/rollback semantics."""
    engine = request.app.state.db_engine
    session = DBSession()
    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise


# Modern type alias pattern
DB = Annotated[DBSession, Depends(get_db_session)]


@app.post("/items")
async def create_item(name: str, db: DB):
    db.changes.append(('insert', name))
    return {"created": name}


# ==========================================================================
# 3. SUB-DEPENDENCIES
# ==========================================================================

def get_token_header(authorization: str = "") -> str:
    if not authorization.startswith("Bearer "):
        raise HTTPException(401, "Invalid auth header")
    return authorization[7:]


async def get_current_user_id(token: str = Depends(get_token_header)) -> int:
    # Validate token, return user_id
    return 1  # mock


async def get_current_user(user_id: int = Depends(get_current_user_id)) -> dict:
    # Fetch from DB
    return {"id": user_id, "name": "Alice", "tier": "pro"}


@app.get("/me")
async def me(user=Depends(get_current_user)):
    return user


# ==========================================================================
# 4. CLASS-BASED DEPENDENCY (configurable)
# ==========================================================================

class RoleRequired:
    """Reusable dep — accepts role param."""

    def __init__(self, role: str):
        self.role = role

    async def __call__(self, user=Depends(get_current_user)):
        if user.get('role', 'user') != self.role:
            raise HTTPException(403, f"Requires role: {self.role}")
        return user


@app.get("/admin", dependencies=[Depends(RoleRequired('admin'))])
async def admin_only():
    return {"status": "admin OK"}


@app.get("/moderator", dependencies=[Depends(RoleRequired('moderator'))])
async def moderator_only():
    return {"status": "mod OK"}


# ==========================================================================
# 5. FEATURE FLAG DEP
# ==========================================================================

class FeatureFlag:
    def __init__(self, flag: str):
        self.flag = flag

    async def __call__(self, user=Depends(get_current_user)):
        # Check flag (Redis/DB/Unleash)
        enabled = await check_flag(self.flag, user['id'])
        if not enabled:
            raise HTTPException(403, f"Feature '{self.flag}' not enabled")
        return True


async def check_flag(flag: str, user_id: int) -> bool:
    # Mock — Redis SISMEMBER or Unleash API
    return True


@app.get("/beta", dependencies=[Depends(FeatureFlag('new_ui'))])
async def beta():
    return {"feature": "available"}


# ==========================================================================
# 6. CACHING / DISABLE CACHE
# ==========================================================================

import random


def random_value():
    return random.random()


@app.get("/cached")
async def cached(
    a: float = Depends(random_value),
    b: float = Depends(random_value),                       # same as a (cached)
    c: float = Depends(random_value, use_cache=False),       # different
    d: float = Depends(random_value, use_cache=False),       # different
):
    return {'a': a, 'b': b, 'c': c, 'd': d}


# ==========================================================================
# 7. PATH / ROUTER-LEVEL DEPS
# ==========================================================================

from fastapi import APIRouter


async def log_access(request: Request):
    print(f"ACCESS: {request.method} {request.url.path}")


# Router with global deps
admin_router = APIRouter(
    prefix="/admin",
    dependencies=[Depends(RoleRequired('admin')), Depends(log_access)],
)


@admin_router.get("/users")
async def list_users():
    return []


@admin_router.delete("/users/{user_id}")
async def delete_user(user_id: int):
    return {"deleted": user_id}


app.include_router(admin_router)


# ==========================================================================
# 8. BACKGROUND TASKS
# ==========================================================================

async def send_welcome_email(email: str):
    print(f"Sending email to {email}...")
    await asyncio.sleep(2)
    print(f"Email sent to {email}")


@app.post("/signup")
async def signup(email: str, background: BackgroundTasks):
    # ... save user
    # Schedule background work — runs AFTER response
    background.add_task(send_welcome_email, email)
    return {"status": "registered"}


# ==========================================================================
# 9. DEPENDENCY_OVERRIDES for TESTING
# ==========================================================================

# Real prod dep
async def get_db_session_real() -> AsyncIterator[DBSession]:
    session = DBSession()
    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise


# Test fixture
async def get_db_session_test() -> AsyncIterator[DBSession]:
    """Test DB — never commits."""
    session = DBSession()
    try:
        yield session
        # No commit — rollback at end
    finally:
        await session.rollback()


# In tests
def test_create_item():
    app.dependency_overrides[get_db_session] = get_db_session_test
    client = TestClient(app)
    response = client.post("/items?name=foo")
    assert response.status_code == 200
    app.dependency_overrides = {}


# ==========================================================================
# 10. PARAMETERIZED ENDPOINT DEPS
# ==========================================================================

class Pagination:
    def __init__(
        self,
        skip: int = 0,
        limit: int = 20,
        max_limit: int = 100,
    ):
        if skip < 0:
            raise HTTPException(400, "skip must be >= 0")
        if limit < 1 or limit > max_limit:
            raise HTTPException(400, f"limit 1..{max_limit}")
        self.skip = skip
        self.limit = limit


def get_pagination(skip: int = 0, limit: int = 20) -> Pagination:
    return Pagination(skip=skip, limit=limit)


@app.get("/items-paginated")
async def list_paginated(p: Pagination = Depends(get_pagination)):
    return {'skip': p.skip, 'limit': p.limit, 'items': []}


# ==========================================================================
# 11. CONDITIONAL DEPENDENCY
# ==========================================================================

async def maybe_require_auth(authorization: str = ""):
    """Optional auth — returns None if no token."""
    if not authorization:
        return None
    return await get_current_user_id(authorization)


@app.get("/public-or-private")
async def both(user_id: int | None = Depends(maybe_require_auth)):
    if user_id:
        return {'authenticated': True, 'user_id': user_id}
    return {'authenticated': False}


# ==========================================================================
# 12. ASYNC GENERATOR DEP with multiple yields (NOT supported)
# ==========================================================================

# Only ONE yield allowed in dependency
async def good_dep() -> AsyncIterator[int]:
    yield 1   # OK


# async def bad_dep() -> AsyncIterator[int]:
#     yield 1
#     yield 2   # ERROR — multiple yields


# ==========================================================================
# 13. COMBINED CACHING PATTERN
# ==========================================================================

# Common pattern: load + cache in app state
_settings_cache = None


@asynccontextmanager
async def lifespan_with_settings(app: FastAPI):
    global _settings_cache
    # Load once at startup
    _settings_cache = {'app_name': 'MyApp', 'version': '1.0'}
    yield
    _settings_cache = None


def get_settings():
    if _settings_cache is None:
        raise RuntimeError("Settings not loaded")
    return _settings_cache


@app.get("/settings")
async def settings_endpoint(settings: dict = Depends(get_settings)):
    return settings


# ==========================================================================
# 14. DEPS IN MIDDLEWARE? NO — use middleware separately
# ==========================================================================
"""
# Middleware != dependency
# Middleware runs for EVERY request automatically
# Deps run only when route requires them

@app.middleware("http")
async def add_request_id(request: Request, call_next):
    import uuid
    request.state.request_id = str(uuid.uuid4())
    response = await call_next(request)
    response.headers['X-Request-ID'] = request.state.request_id
    return response


# Then dep can read it
def get_request_id(request: Request) -> str:
    return request.state.request_id
"""
