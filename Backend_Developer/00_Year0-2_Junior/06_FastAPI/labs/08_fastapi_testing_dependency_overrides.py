"""
FastAPI Lab 08 — Testing with Dependency Overrides
====================================================
ARCHITECTURE — Why Dependency Override Testing:

    PRODUCTION CODE:                    TEST CODE:
    ┌─────────────────┐                ┌──────────────────────────┐
    │ @app.get("/me") │                │ async with lifespan(app):│
    │   user = Depends│                │   app.dependency_overrides│
    │   (get_current  │  ──override──► │   [get_current_user] =   │
    │   _user)        │                │   lambda: fake_user      │
    └─────────────────┘                └──────────────────────────┘
              │                                    │
              ▼                                    ▼
    Real JWT decode + DB lookup       Returns FakeUser immediately
    (needs real DB + valid token)     (no DB, no token needed)

WHAT dependency_overrides DOES:
  app.dependency_overrides is a dict: {original_dep: replacement_callable}
  FastAPI checks this dict BEFORE calling the real dependency.
  The replacement can be any callable — function, lambda, async def.

  After tests: app.dependency_overrides.clear()  ← MUST restore state

HTTPX + ASGITransport:
  AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
  Sends HTTP requests DIRECTLY to the ASGI app — no network, no port.
  Same request/response as a real HTTP client, but in-process.

INTERVIEW ANSWER:
  "FastAPI testing mein dependency_overrides dict mein original dependency ko
   key banake uski jagah test replacement inject karte hain. Isse real DB,
   real JWT, real external APIs sab mock ho jaate hain. httpx.AsyncClient +
   ASGITransport se in-process HTTP requests bhejte hain — TestClient se fast
   aur async-friendly."

TASK:
  1. TODO 1: implement get_db() yield-dependency + get_current_user() JWT-dependency
  2. TODO 2: implement /me endpoint (protected by get_current_user)
             and /items/ endpoint (protected by get_current_user + get_db)
  3. TODO 3: write override_db() test helper that replaces get_db with FakeDB
  4. TODO 4: write override_current_user() that replaces get_current_user with a fake
  5. Run: pytest 08_fastapi_testing_dependency_overrides.py -v  (or -v -p no:odoo)

Prereq: pip install fastapi httpx pytest pytest-asyncio pyjwt
"""

from __future__ import annotations

import asyncio
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from fastapi import Depends, FastAPI, HTTPException, status
from httpx import ASGITransport, AsyncClient

app = FastAPI(title="Lab 08 — Dependency Override Testing")


# ════════════════════════════════════════════════════════════════════════════
# FAKE INFRASTRUCTURE (stands in for real DB / real JWT)
# ════════════════════════════════════════════════════════════════════════════

class FakeDB:
    """Tracks how many times it was opened + closed (for fixture teardown proof)."""
    open_count  = 0
    close_count = 0

    def __init__(self):
        FakeDB.open_count += 1
        self.items = {
            1: {"id": 1, "name": "Widget",  "owner_id": 42},
            2: {"id": 2, "name": "Gadget",  "owner_id": 42},
            3: {"id": 3, "name": "Thingus", "owner_id": 99},
        }

    def get_items_for_user(self, user_id: int):
        return [v for v in self.items.values() if v["owner_id"] == user_id]

    def close(self):
        FakeDB.close_count += 1


class UserModel:
    def __init__(self, id: int, email: str, role: str = "user"):
        self.id    = id
        self.email = email
        self.role  = role


# ════════════════════════════════════════════════════════════════════════════
# TODO 1 — Real dependencies (stubs to override in tests)
# ════════════════════════════════════════════════════════════════════════════
"""
Implement get_db() and get_current_user():

  get_db():
    A yield-dependency that opens FakeDB, yields it, closes in finally.
    In production this would open a real AsyncSession.

    async def get_db() -> AsyncGenerator[FakeDB, None]:
        db = FakeDB()
        try:
            yield db
        finally:
            db.close()

  get_current_user(token: str = Header(alias="X-Auth-Token")):
    Reads X-Auth-Token header.
    If token == "valid-token" → return UserModel(id=42, email="alice@test.com")
    Else → raise HTTPException(401, "Invalid token")

    Hint:
      from fastapi import Header

      async def get_current_user(
          token: str = Header(alias="X-Auth-Token", default=None)
      ) -> UserModel:
          if token != "valid-token":
              raise HTTPException(status_code=401, detail="Invalid token")
          return UserModel(id=42, email="alice@test.com")
"""

from fastapi import Header  # noqa: E402


async def get_db() -> AsyncGenerator[FakeDB, None]:
    raise NotImplementedError(
        "TODO 1a: yield FakeDB(), close in finally"
    )


async def get_current_user(
    token: str = Header(alias="X-Auth-Token", default=None)
) -> UserModel:
    raise NotImplementedError(
        "TODO 1b: check token == 'valid-token', return UserModel or raise 401"
    )


# ════════════════════════════════════════════════════════════════════════════
# TODO 2 — Endpoints
# ════════════════════════════════════════════════════════════════════════════
"""
Implement two endpoints:

  GET /me
    → Depends(get_current_user) only
    → returns {"id": user.id, "email": user.email, "role": user.role}

  GET /items/
    → Depends(get_current_user) + Depends(get_db)
    → returns list of items owned by current user from db.get_items_for_user(user.id)

  Hint:
    @app.get("/me")
    async def read_me(user: UserModel = Depends(get_current_user)):
        return {"id": user.id, "email": user.email, "role": user.role}

    @app.get("/items/")
    async def read_items(
        user: UserModel = Depends(get_current_user),
        db:   FakeDB    = Depends(get_db),
    ):
        return db.get_items_for_user(user.id)
"""

# TODO 2a: @app.get("/me") endpoint
# TODO 2b: @app.get("/items/") endpoint


# ════════════════════════════════════════════════════════════════════════════
# TODO 3 — Test helper: fake DB dependency
# ════════════════════════════════════════════════════════════════════════════
"""
Define get_fake_db() — a replacement for get_db that tests will inject:

  async def get_fake_db() -> AsyncGenerator[FakeDB, None]:
      db = FakeDB()
      try:
          yield db
      finally:
          db.close()

This is identical to get_db() in structure — the point is that tests
can inject this specific instance to track open/close counts or
pre-populate items.

In tests:
  app.dependency_overrides[get_db] = get_fake_db
"""

async def get_fake_db() -> AsyncGenerator[FakeDB, None]:
    raise NotImplementedError(
        "TODO 3: yield FakeDB() with finally close — same pattern as get_db()"
    )


# ════════════════════════════════════════════════════════════════════════════
# TODO 4 — Test helper: fake user dependency
# ════════════════════════════════════════════════════════════════════════════
"""
Define make_fake_user(user_id, email, role) → callable:

  Returns a callable (closure) that FastAPI can use as a dependency.
  The closure takes no arguments — it just returns the UserModel directly.

  Hint:
    def make_fake_user(user_id=42, email="test@test.com", role="user"):
        async def _fake_user():
            return UserModel(id=user_id, email=email, role=role)
        return _fake_user

  In tests:
    app.dependency_overrides[get_current_user] = make_fake_user(id=99, role="admin")
"""

def make_fake_user(user_id: int = 42, email: str = "test@test.com", role: str = "user"):
    raise NotImplementedError(
        "TODO 4: return async closure that returns UserModel(id=user_id, email=email, role=role)"
    )


# ════════════════════════════════════════════════════════════════════════════
# FIXTURES
# ════════════════════════════════════════════════════════════════════════════

@pytest_asyncio.fixture(autouse=True)
async def clear_overrides():
    """Restore dependency_overrides after EVERY test — isolation guarantee."""
    yield
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        yield c


# ════════════════════════════════════════════════════════════════════════════
# TESTS
# ════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_me_with_valid_token(client: AsyncClient):
    """Real get_current_user: valid token returns user data."""
    resp = await client.get("/me", headers={"X-Auth-Token": "valid-token"})
    assert resp.status_code == 200, f"FAIL: Expected 200. Got {resp.status_code}: {resp.json()}"
    body = resp.json()
    assert body["email"] == "alice@test.com", f"FAIL: Wrong email. Got {body}"


@pytest.mark.asyncio
async def test_me_invalid_token_returns_401(client: AsyncClient):
    """Real get_current_user: bad token → 401."""
    resp = await client.get("/me", headers={"X-Auth-Token": "wrong"})
    assert resp.status_code == 401, f"FAIL: Expected 401. Got {resp.status_code}"


@pytest.mark.asyncio
async def test_me_no_token_returns_401(client: AsyncClient):
    """Real get_current_user: missing header → 401."""
    resp = await client.get("/me")
    assert resp.status_code == 401, f"FAIL: Expected 401. Got {resp.status_code}"


@pytest.mark.asyncio
async def test_me_with_overridden_user(client: AsyncClient):
    """Override get_current_user — no token needed, test sees fake user."""
    app.dependency_overrides[get_current_user] = make_fake_user(
        user_id=99, email="charlie@test.com", role="admin"
    )
    resp = await client.get("/me")
    assert resp.status_code == 200, f"FAIL: {resp.status_code}: {resp.json()}"
    body = resp.json()
    assert body["id"]    == 99,                "FAIL: id should be 99"
    assert body["email"] == "charlie@test.com","FAIL: email should be charlie@test.com"
    assert body["role"]  == "admin",           "FAIL: role should be admin"


@pytest.mark.asyncio
async def test_items_with_both_overrides(client: AsyncClient):
    """Override BOTH deps — no token, no real DB needed."""
    FakeDB.open_count  = 0
    FakeDB.close_count = 0

    app.dependency_overrides[get_current_user] = make_fake_user(user_id=42)
    app.dependency_overrides[get_db]           = get_fake_db

    resp = await client.get("/items/")
    assert resp.status_code == 200, f"FAIL: {resp.status_code}: {resp.json()}"
    items = resp.json()
    assert len(items) == 2, f"FAIL: user 42 owns 2 items. Got {len(items)}: {items}"
    assert all(item["owner_id"] == 42 for item in items), "FAIL: Items not filtered by owner"


@pytest.mark.asyncio
async def test_db_teardown_runs_after_request(client: AsyncClient):
    """get_fake_db's finally block must run — FakeDB.close_count should increment."""
    FakeDB.open_count  = 0
    FakeDB.close_count = 0

    app.dependency_overrides[get_current_user] = make_fake_user(user_id=42)
    app.dependency_overrides[get_db]           = get_fake_db

    await client.get("/items/")

    assert FakeDB.open_count  == 1, f"FAIL: DB should have been opened once. Got {FakeDB.open_count}"
    assert FakeDB.close_count == 1, (
        f"FAIL: DB should have been closed once (finally block). Got {FakeDB.close_count}"
    )


@pytest.mark.asyncio
async def test_overrides_cleared_between_tests(client: AsyncClient):
    """
    Verify autouse clear_overrides fixture works — this test runs AFTER the
    override tests but should NOT have any overrides active.
    Without valid token: 401 (real dependency in play again).
    """
    resp = await client.get("/me")
    assert resp.status_code == 401, (
        f"FAIL: Overrides should be cleared between tests. Got {resp.status_code}"
    )


@pytest.mark.asyncio
async def test_different_users_see_different_items(client: AsyncClient):
    """Override with user_id=99 — should see only Thingus (owner_id=99)."""
    app.dependency_overrides[get_current_user] = make_fake_user(user_id=99)
    app.dependency_overrides[get_db]           = get_fake_db

    resp = await client.get("/items/")
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) == 1, f"FAIL: user 99 owns 1 item. Got {len(items)}: {items}"
    assert items[0]["name"] == "Thingus", f"FAIL: Expected 'Thingus'. Got {items[0]['name']}"


# ════════════════════════════════════════════════════════════════════════════
# SOCH (Answer ALOUD before moving to Lab 09)
# ════════════════════════════════════════════════════════════════════════════
"""
SOCH:

Q1: app.dependency_overrides kya karta hai exactly?
    Test mein override karne ke baad clear karna kyon zaroori hai?

Q2: httpx.AsyncClient + ASGITransport vs TestClient — kya fark hai?
    Kab AsyncClient prefer karoge?

Q3: Agar real DB test karna ho (not fake), dependency_overrides se kya karoge?
    (Override with a test DB session factory pointing to test_db)

Q4: make_fake_user() ek closure return karta hai — kyon direct UserModel return
    nahi karte? FastAPI dependency mein callable kyon chahiye?

Q5: autouse=True fixture ka kya matlab hai?
    clear_overrides kyon autouse hai? Kya hoga agar autouse=False karo?
"""
