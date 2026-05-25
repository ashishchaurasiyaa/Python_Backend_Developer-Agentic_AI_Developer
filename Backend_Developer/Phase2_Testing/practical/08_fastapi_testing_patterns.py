"""
============================================================
FASTAPI TESTING PATTERNS — Practical
============================================================
Install:
    pip install fastapi pytest pytest-asyncio httpx pytest-mock respx

Includes:
1. Sync + async test patterns
2. conftest.py shared fixtures
3. DB fixtures (transactional rollback)
4. Auth fixtures
5. External API mocking
6. WebSocket tests
7. Dependency overrides
"""


# ============================================================
# 1. SAMPLE FASTAPI APP (for testing)
# ============================================================
SAMPLE_APP = '''
# myapp/main.py

from fastapi import FastAPI, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

app = FastAPI()

# Schemas
class UserCreate(BaseModel):
    name: str
    email: str

class UserOut(BaseModel):
    id: int
    name: str
    email: str

# DB dependency
async def get_db() -> AsyncSession:
    async with AsyncSession(engine) as session:
        yield session

# Auth dependency
async def get_current_user(token: str = Header(None), db = Depends(get_db)):
    if not token:
        raise HTTPException(401)
    user = await db.get_user_by_token(token)
    if not user:
        raise HTTPException(401)
    return user

# Endpoints
@app.get("/users/{user_id}", response_model=UserOut)
async def get_user(user_id: int, db = Depends(get_db)):
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(404)
    return user

@app.post("/users", response_model=UserOut, status_code=201)
async def create_user(data: UserCreate, db = Depends(get_db),
                      background: BackgroundTasks = None):
    user = User(**data.dict())
    db.add(user)
    await db.commit()
    background.add_task(send_welcome_email, user.id)
    return user

@app.get("/api/me", response_model=UserOut)
async def get_me(current_user = Depends(get_current_user)):
    return current_user
'''


# ============================================================
# 2. CONFTEST.PY (shared fixtures)
# ============================================================
CONFTEST = '''
# tests/conftest.py

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from myapp.main import app
from myapp.db import Base, get_db

DATABASE_URL = "postgresql+asyncpg://test:test@localhost:5432/test_db"


@pytest_asyncio.fixture(scope="session")
async def engine():
    """Session-scoped engine (created once)."""
    engine = create_async_engine(DATABASE_URL, pool_pre_ping=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(engine):
    """Per-test transaction, rolled back at end."""
    async with engine.connect() as conn:
        trans = await conn.begin()
        Session = sessionmaker(bind=conn, class_=AsyncSession, expire_on_commit=False)
        async with Session() as session:
            yield session
        await trans.rollback()


@pytest_asyncio.fixture
async def client(db_session):
    """Async HTTP client with DB override."""
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest.fixture
def sync_client():
    """Sync TestClient (simpler but blocks event loop)."""
    return TestClient(app)


@pytest_asyncio.fixture
async def authed_client(client, db_session):
    """Authenticated client."""
    user = User(email="test@example.com", password_hash="...")
    db_session.add(user)
    await db_session.commit()

    response = await client.post("/auth/login", json={
        "email": "test@example.com",
        "password": "test123",
    })
    token = response.json()["access_token"]
    client.headers["Authorization"] = f"Bearer {token}"
    yield client


@pytest.fixture
def mock_redis(mocker):
    """Mock Redis client."""
    return mocker.MagicMock()
'''


# ============================================================
# 3. SYNC TEST PATTERNS
# ============================================================
SYNC_TESTS = '''
# tests/test_users_sync.py
# Using sync TestClient — simpler, but blocks event loop

from fastapi.testclient import TestClient

def test_root(sync_client: TestClient):
    response = sync_client.get("/")
    assert response.status_code == 200


def test_get_user(sync_client):
    response = sync_client.get("/users/1")
    assert response.status_code == 200
    data = response.json()
    assert "id" in data
    assert "name" in data


def test_create_user(sync_client):
    response = sync_client.post("/users", json={
        "name": "Alice",
        "email": "alice@example.com",
    })
    assert response.status_code == 201
    assert response.json()["email"] == "alice@example.com"


@pytest.mark.parametrize("user_id,expected", [
    (1, 200),
    (999, 404),
    (-1, 422),
    ("abc", 422),
])
def test_user_statuses(sync_client, user_id, expected):
    response = sync_client.get(f"/users/{user_id}")
    assert response.status_code == expected
'''


# ============================================================
# 4. ASYNC TEST PATTERNS
# ============================================================
ASYNC_TESTS = '''
# tests/test_users_async.py
# Using AsyncClient — async-native

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_root_async(client: AsyncClient):
    response = await client.get("/")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_create_user(client: AsyncClient, db_session):
    response = await client.post("/users", json={
        "name": "Bob",
        "email": "bob@example.com",
    })
    assert response.status_code == 201

    # Check DB
    user = await db_session.execute(select(User).where(User.email == "bob@example.com"))
    assert user.scalar_one_or_none() is not None


@pytest.mark.asyncio
async def test_concurrent_requests(client):
    """Run multiple requests in parallel."""
    import asyncio
    responses = await asyncio.gather(*[
        client.get(f"/users/{i}") for i in range(1, 11)
    ])
    assert all(r.status_code in (200, 404) for r in responses)
'''


# ============================================================
# 5. DEPENDENCY OVERRIDES
# ============================================================
DEPENDENCY_OVERRIDES = '''
# Override specific dependency for a test

@pytest.mark.asyncio
async def test_with_custom_auth(client, db_session):
    """Override auth to return specific user."""
    from myapp.main import app, get_current_user

    async def fake_user():
        return User(id=42, email="fake@test.com", role="admin")

    app.dependency_overrides[get_current_user] = fake_user

    response = await client.get("/api/me")
    assert response.json()["id"] == 42

    # Cleanup happens automatically via fixture


# Override Redis
@pytest.mark.asyncio
async def test_caching(client, mocker):
    mock_redis = mocker.MagicMock()
    mock_redis.get = mocker.AsyncMock(return_value="cached")

    async def get_redis_override():
        return mock_redis

    app.dependency_overrides[get_redis] = get_redis_override

    response = await client.get("/cached-endpoint")
    mock_redis.get.assert_called_once()
'''


# ============================================================
# 6. MOCKING EXTERNAL APIS WITH RESPX
# ============================================================
MOCK_EXTERNAL = '''
# pip install respx

import respx
import httpx
import pytest


@respx.mock
@pytest.mark.asyncio
async def test_proxy_endpoint(client):
    """Mock external API call."""
    # Set up mock response
    respx.get("https://api.external.com/users/1").respond(
        200, json={"id": 1, "name": "External User"}
    )

    # Endpoint calls external API internally
    response = await client.get("/proxy/users/1")
    assert response.json()["name"] == "External User"


# pytest-httpx alternative
def test_with_pytest_httpx(client, httpx_mock):
    httpx_mock.add_response(
        method="GET",
        url="https://api.external.com/data",
        json={"key": "value"},
    )
    response = client.get("/external-data")
    assert response.json()["key"] == "value"
'''


# ============================================================
# 7. WEBSOCKET TESTING
# ============================================================
WEBSOCKET_TESTS = '''
# Sync (TestClient)
def test_websocket_basic(sync_client):
    with sync_client.websocket_connect("/ws") as ws:
        ws.send_text("hello")
        response = ws.receive_text()
        assert response == "hello back"


def test_websocket_json(sync_client):
    with sync_client.websocket_connect("/ws/chat") as ws:
        ws.send_json({"type": "message", "text": "hi"})
        msg = ws.receive_json()
        assert msg["type"] == "ack"


def test_websocket_disconnect(sync_client):
    with sync_client.websocket_connect("/ws") as ws:
        ws.send_text("disconnect_now")
        # Server closes connection
    # Outside with block — disconnected gracefully


# Async (httpx-ws)
@pytest.mark.asyncio
async def test_ws_async(client):
    from httpx_ws import aconnect_ws
    async with aconnect_ws("ws://test/ws", client) as ws:
        await ws.send_text("hello")
        msg = await ws.receive_text()
        assert msg == "hello back"
'''


# ============================================================
# 8. BACKGROUND TASKS
# ============================================================
BACKGROUND_TASKS = '''
@pytest.mark.asyncio
async def test_signup_triggers_background_task(client, mocker):
    """Verify background task is enqueued."""
    mock_send = mocker.patch("myapp.background.send_welcome_email")

    response = await client.post("/users", json={
        "name": "Alice",
        "email": "alice@example.com",
    })
    assert response.status_code == 201

    # FastAPI runs background tasks after response
    # In tests, they execute immediately after response

    mock_send.assert_called_once()


# For Celery tasks (mock .delay())
@pytest.mark.asyncio
async def test_celery_task_enqueued(client, mocker):
    mock_task = mocker.patch("myapp.tasks.process_signup.delay")

    response = await client.post("/users", json={...})

    mock_task.assert_called_once_with(user_id=response.json()["id"])
'''


# ============================================================
# 9. FILE UPLOAD
# ============================================================
FILE_UPLOAD = '''
def test_upload_csv(sync_client):
    csv_content = b"name,email\\nAlice,a@x.com\\nBob,b@x.com"
    response = sync_client.post(
        "/upload",
        files={"file": ("users.csv", csv_content, "text/csv")},
    )
    assert response.status_code == 200
    assert response.json()["rows"] == 2


@pytest.mark.asyncio
async def test_upload_image(client):
    with open("tests/fixtures/test.png", "rb") as f:
        files = {"file": ("test.png", f.read(), "image/png")}
        response = await client.post("/upload-image", files=files)
    assert response.status_code == 200


def test_upload_invalid_type(sync_client):
    response = sync_client.post(
        "/upload",
        files={"file": ("malicious.exe", b"binary", "application/octet-stream")},
    )
    assert response.status_code == 400
'''


# ============================================================
# 10. SSE STREAMING
# ============================================================
SSE_TESTS = '''
def test_sse_stream(sync_client):
    """Test Server-Sent Events stream."""
    with sync_client.stream("GET", "/sse/notifications") as response:
        chunks = []
        for line in response.iter_lines():
            if line.startswith("data:"):
                data = line[5:].strip()
                chunks.append(data)
            if len(chunks) >= 3:
                break
    assert len(chunks) == 3
    assert all(c for c in chunks)


@pytest.mark.asyncio
async def test_ndjson_stream(client):
    """Streaming NDJSON response."""
    async with client.stream("GET", "/export/users.ndjson") as response:
        users = []
        async for line in response.aiter_lines():
            if line:
                users.append(json.loads(line))
    assert len(users) > 0
'''


# ============================================================
# 11. VALIDATION ERRORS
# ============================================================
VALIDATION_TESTS = '''
def test_missing_required_field(sync_client):
    response = sync_client.post("/users", json={"name": "Alice"})  # no email
    assert response.status_code == 422
    error = response.json()
    locations = [tuple(e["loc"]) for e in error["detail"]]
    assert ("body", "email") in locations


def test_invalid_type(sync_client):
    response = sync_client.post("/users", json={
        "name": "Alice",
        "email": 12345,    # should be string
    })
    assert response.status_code == 422


def test_validation_error_shape(sync_client, snapshot):
    """Snapshot the error response format."""
    response = sync_client.post("/users", json={})
    assert response.status_code == 422
    assert response.json() == snapshot
'''


# ============================================================
# 12. PYTEST.INI / PYPROJECT.TOML
# ============================================================
PYTEST_CONFIG = '''
# pyproject.toml

[tool.pytest.ini_options]
asyncio_mode = "auto"      # auto-detect @pytest.mark.asyncio
addopts = "--strict-markers --tb=short -ra"
testpaths = ["tests"]
markers = [
    "slow: marks slow tests",
    "integration: integration tests",
    "e2e: end-to-end tests",
    "smoke: smoke tests",
]

[tool.coverage.run]
source = ["myapp"]
branch = true
omit = ["*/migrations/*", "*/conftest.py"]

[tool.coverage.report]
exclude_lines = [
    "pragma: no cover",
    "if TYPE_CHECKING:",
    "raise NotImplementedError",
]
fail_under = 80
'''


# ============================================================
# 13. COMPLETE TEST EXAMPLE
# ============================================================
COMPLETE_TEST = '''
# tests/test_user_journey.py
"""End-to-end user journey test."""

import pytest
import respx
from httpx import AsyncClient

@pytest.mark.e2e
@pytest.mark.asyncio
@respx.mock
async def test_complete_signup_flow(client: AsyncClient, db_session):
    """Test: signup → verify email → login → access profile."""

    # Mock external email service
    respx.post("https://api.sendgrid.com/v3/mail/send").respond(202)

    # 1. Signup
    signup = await client.post("/auth/signup", json={
        "name": "Alice",
        "email": "alice@example.com",
        "password": "Test@1234",
    })
    assert signup.status_code == 201
    user_id = signup.json()["id"]

    # Verify user in DB
    from myapp.models import User
    user = await db_session.get(User, user_id)
    assert user.email == "alice@example.com"
    assert not user.is_verified

    # 2. Email verification
    verify = await client.get(f"/auth/verify?token={user.verification_token}")
    assert verify.status_code == 200

    await db_session.refresh(user)
    assert user.is_verified

    # 3. Login
    login = await client.post("/auth/login", json={
        "email": "alice@example.com",
        "password": "Test@1234",
    })
    assert login.status_code == 200
    token = login.json()["access_token"]

    # 4. Access profile
    client.headers["Authorization"] = f"Bearer {token}"
    profile = await client.get("/api/me")
    assert profile.status_code == 200
    assert profile.json()["email"] == "alice@example.com"
'''


# ============================================================
# MAIN
# ============================================================
if __name__ == "__main__":
    print("=" * 60)
    print("FASTAPI TESTING PATTERNS")
    print("=" * 60)

    print("\n--- SAMPLE APP ---")
    print(SAMPLE_APP)
    print("\n--- CONFTEST ---")
    print(CONFTEST)
    print("\n--- SYNC TESTS ---")
    print(SYNC_TESTS)
    print("\n--- ASYNC TESTS ---")
    print(ASYNC_TESTS)
    print("\n--- DEPENDENCY OVERRIDES ---")
    print(DEPENDENCY_OVERRIDES)
    print("\n--- MOCK EXTERNAL APIs ---")
    print(MOCK_EXTERNAL)
    print("\n--- WEBSOCKET TESTS ---")
    print(WEBSOCKET_TESTS)
    print("\n--- BACKGROUND TASKS ---")
    print(BACKGROUND_TASKS)
    print("\n--- FILE UPLOAD ---")
    print(FILE_UPLOAD)
    print("\n--- SSE STREAMING ---")
    print(SSE_TESTS)
    print("\n--- VALIDATION ---")
    print(VALIDATION_TESTS)
    print("\n--- PYTEST CONFIG ---")
    print(PYTEST_CONFIG)
    print("\n--- COMPLETE E2E TEST ---")
    print(COMPLETE_TEST)
