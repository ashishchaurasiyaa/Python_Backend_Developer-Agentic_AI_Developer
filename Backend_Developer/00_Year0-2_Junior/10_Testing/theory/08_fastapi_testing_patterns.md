# FastAPI Testing Patterns

> **Interview angle:** "FastAPI app test karna hai — sync, async, DB, external APIs. Best practices?"

---

## 1. FastAPI Test Stack

```bash
pip install pytest pytest-asyncio httpx pytest-cov pytest-mock
```

- **pytest** — test runner
- **httpx** — async HTTP client (recommended over `TestClient`)
- **pytest-asyncio** — async test support
- **pytest-mock** — mocking helpers

---

## 2. Sync TestClient (simpler, blocking)

```python
from fastapi.testclient import TestClient
from myapp.main import app

client = TestClient(app)

def test_root():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"message": "Hello"}
```

`TestClient` uses requests internally. **Blocks the event loop** in async tests. OK for most cases.

---

## 3. Async AsyncClient (recommended)

```python
import pytest
from httpx import AsyncClient, ASGITransport
from myapp.main import app

@pytest.mark.asyncio
async def test_root():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get("/")
        assert response.status_code == 200
```

**Why async?** If your endpoint does `await something()`, sync TestClient can be slow.

---

## 4. Dependency Overrides (mocking)

Override FastAPI dependencies for tests.

```python
# main.py
async def get_db():
    async with AsyncSession() as session:
        yield session

@app.get("/users/{id}")
async def get_user(id: int, db: AsyncSession = Depends(get_db)):
    return await db.get(User, id)
```

```python
# test_users.py
from main import app, get_db

async def override_get_db():
    """Return a test DB session."""
    async with TestSession() as session:
        yield session

app.dependency_overrides[get_db] = override_get_db

# After test
app.dependency_overrides.clear()
```

### Fixture pattern
```python
@pytest.fixture
def override_dependency():
    app.dependency_overrides[get_db] = override_get_db
    yield
    app.dependency_overrides.clear()
```

---

## 5. Test DB Setup

### Per-test transactional rollback
```python
@pytest.fixture
async def db_session():
    """New transaction per test, rolled back."""
    async with engine.connect() as connection:
        trans = await connection.begin()
        session = AsyncSession(bind=connection)
        yield session
        await session.close()
        await trans.rollback()
        await connection.close()
```

### Per-test fresh DB
```python
@pytest.fixture(scope="function", autouse=True)
async def setup_db():
    """Drop + recreate schema before each test."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield
```

### Session-scoped DB (faster, but tests must clean up)
```python
@pytest.fixture(scope="session")
async def db_engine():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()
```

---

## 6. Authentication in Tests

### Test with JWT
```python
@pytest.fixture
def authed_client(client):
    response = client.post("/auth/login", json={
        "username": "test", "password": "pass",
    })
    token = response.json()["access_token"]
    client.headers["Authorization"] = f"Bearer {token}"
    return client

def test_protected_endpoint(authed_client):
    response = authed_client.get("/api/me")
    assert response.status_code == 200
```

### Bypass auth via override
```python
async def fake_current_user():
    return User(id=1, email="test@example.com", role="admin")

app.dependency_overrides[get_current_user] = fake_current_user
```

---

## 7. Mocking External APIs

```python
def test_endpoint_calls_external(client, mocker):
    """Mock external HTTP calls."""
    mock_get = mocker.patch("myapp.services.httpx.AsyncClient.get")
    mock_get.return_value.json.return_value = {"data": "mocked"}

    response = client.get("/api/external-data")
    assert response.json()["data"] == "mocked"
```

### `respx` for httpx mocking
```python
import respx
import httpx

@respx.mock
def test_external_api():
    respx.get("https://api.external.com/users").respond(
        200, json={"id": 1, "name": "Test"}
    )

    response = client.get("/proxy/users/1")
    assert response.json()["name"] == "Test"
```

### `pytest-httpx`
```python
def test_with_pytest_httpx(httpx_mock):
    httpx_mock.add_response(
        method="GET",
        url="https://api.example.com/data",
        json={"key": "value"},
    )
    response = client.get("/proxy/data")
```

---

## 8. WebSocket Testing

```python
def test_websocket():
    with client.websocket_connect("/ws") as websocket:
        websocket.send_text("hello")
        data = websocket.receive_text()
        assert data == "hello back"
```

```python
@pytest.mark.asyncio
async def test_websocket_async():
    from httpx_ws import aconnect_ws
    async with aconnect_ws("ws://test/ws", client) as ws:
        await ws.send_text("hello")
        response = await ws.receive_text()
        assert response == "hello back"
```

---

## 9. Parametrize Test Cases

```python
@pytest.mark.parametrize("user_id,expected_status", [
    (1, 200),       # valid
    (999, 404),     # not found
    (-1, 422),      # invalid
    ("abc", 422),   # wrong type
])
def test_get_user_statuses(client, user_id, expected_status):
    response = client.get(f"/users/{user_id}")
    assert response.status_code == expected_status
```

---

## 10. Lifespan Events

```python
@pytest.fixture(scope="session")
async def app_with_lifespan():
    async with LifespanManager(app):
        yield app

@pytest.mark.asyncio
async def test_with_startup(app_with_lifespan):
    transport = ASGITransport(app=app_with_lifespan)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get("/")
        assert response.status_code == 200
```

---

## 11. Test File Organization

```
tests/
├── conftest.py                 # shared fixtures
├── unit/
│   ├── test_models.py
│   └── test_services.py
├── integration/
│   ├── test_endpoints.py
│   └── test_db.py
├── e2e/
│   └── test_full_flow.py
└── fixtures/
    └── data.json
```

---

## 12. conftest.py — Shared Fixtures

```python
# tests/conftest.py
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from myapp.main import app
from myapp.db import Base, get_db


# Session-scoped engine (created once)
@pytest_asyncio.fixture(scope="session")
async def engine():
    engine = create_async_engine(
        "postgresql+asyncpg://localhost/test_db",
        echo=False,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


# Per-test session with rollback
@pytest_asyncio.fixture
async def db_session(engine):
    async with engine.connect() as connection:
        trans = await connection.begin()
        async with AsyncSession(bind=connection) as session:
            yield session
        await trans.rollback()


# Override app's DB dependency
@pytest_asyncio.fixture
async def client(db_session):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


# Authenticated client
@pytest_asyncio.fixture
async def authed_client(client, db_session):
    # Create test user
    user = User(email="test@example.com", password_hash="...")
    db_session.add(user)
    await db_session.commit()

    response = await client.post("/auth/login", json={
        "email": "test@example.com",
        "password": "test123",
    })
    token = response.json()["access_token"]
    client.headers["Authorization"] = f"Bearer {token}"
    return client
```

---

## 13. Background Tasks Testing

```python
# Test that endpoint enqueues task
def test_endpoint_enqueues_task(client, mocker):
    mock_task = mocker.patch("myapp.tasks.send_email.delay")
    response = client.post("/signup", json={"email": "a@x.com"})
    assert response.status_code == 201
    mock_task.assert_called_once_with("a@x.com")
```

For BackgroundTasks (FastAPI built-in):
```python
def test_background_task_runs(client, mocker):
    mock_func = mocker.patch("myapp.background.do_work")
    response = client.post("/trigger-task")
    assert mock_func.called
```

---

## 14. File Upload Testing

```python
def test_upload_file(client):
    files = {"file": ("test.csv", b"col1,col2\n1,2\n", "text/csv")}
    response = client.post("/upload", files=files)
    assert response.status_code == 200
    assert response.json()["rows"] == 1
```

---

## 15. SSE / Streaming Testing

```python
def test_sse_stream(client):
    with client.stream("GET", "/sse/progress") as response:
        chunks = []
        for line in response.iter_lines():
            if line.startswith("data:"):
                chunks.append(line)
            if len(chunks) >= 5:
                break
    assert len(chunks) == 5
```

---

## 16. Validation / Error Responses

```python
def test_validation_error(client):
    response = client.post("/users", json={
        "name": "Alice",
        # missing required "email"
    })
    assert response.status_code == 422
    error = response.json()
    assert error["detail"][0]["loc"] == ["body", "email"]
    assert error["detail"][0]["type"] == "missing"
```

---

## 17. Snapshot Testing API Responses

```python
def test_user_response_shape(client, snapshot):
    response = client.get("/users/1").json()
    assert response == snapshot(exclude=props("created_at", "updated_at"))
```

---

## 18. Performance / Timing Tests

```python
import time

def test_endpoint_fast(client):
    start = time.perf_counter()
    response = client.get("/api/data")
    elapsed = time.perf_counter() - start
    assert response.status_code == 200
    assert elapsed < 0.1   # < 100ms SLA
```

For real load: use Locust (see `06_performance_testing_locust.md`).

---

## 19. Pytest Markers

```python
# pyproject.toml
[tool.pytest.ini_options]
markers = [
    "slow: marks tests as slow",
    "integration: integration tests",
    "e2e: end-to-end tests",
]

# Usage
@pytest.mark.slow
@pytest.mark.integration
async def test_full_workflow():
    pass

# Run only fast tests
pytest -m "not slow"

# Run E2E only
pytest -m e2e
```

---

## 20. Common Pitfalls

### Pitfall 1: Forgetting `app.dependency_overrides.clear()`
Tests leak overrides into each other.

### Pitfall 2: Module-level TestClient
```python
# ❌ created once, holds connection
client = TestClient(app)

# ✅ use fixture
@pytest.fixture
def client():
    return TestClient(app)
```

### Pitfall 3: Not handling async correctly
```python
# ❌ sync test calling async function
def test_x():
    result = await my_async_fn()    # SyntaxError

# ✅
@pytest.mark.asyncio
async def test_x():
    result = await my_async_fn()
```

### Pitfall 4: SQLite differences from Postgres
JSONB, full-text search, GIN indexes — SQLite doesn't support. Use real Postgres in tests.

### Pitfall 5: Mocking what you shouldn't
Mock external dependencies, not your own code. Excessive mocking → meaningless tests.

---

## 21. Interview Questions

**Q1: TestClient vs AsyncClient?**
TestClient = sync, simpler, sufficient for most. AsyncClient (httpx) = async-native, faster for async-heavy endpoints.

**Q2: Dependency override?**
`app.dependency_overrides[real_dep] = fake_dep`. Replaces in tests, clear after.

**Q3: Test DB strategy?**
- Transactional rollback: fast, single DB
- Per-test schema: safer, isolated
- SQLite memory: very fast but feature gap
- Real Postgres: most accurate

**Q4: Auth mocking?**
Override `get_current_user` dependency to return test user, OR generate test JWT.

**Q5: External APIs mocking?**
respx, pytest-httpx, or unittest.mock.patch the HTTP client. NEVER hit real external API in tests.

**Q6: WebSocket test?**
`client.websocket_connect()` context manager. Test both send + receive.

**Q7: How to test FastAPI background tasks?**
Mock the task function or call it directly. Don't rely on actual background scheduling.

---

## 22. Best Practices

1. **AsyncClient over TestClient** for async apps
2. **Fixture for client** — don't create at module level
3. **Dependency overrides** for mocking
4. **Transactional rollback** for fast tests
5. **Real Postgres** for integration tests
6. **Mock external APIs** (respx, pytest-httpx)
7. **Parametrize** for many scenarios
8. **Per-test cleanup** — clear overrides
9. **Markers** to organize (slow, integration, e2e)
10. **Coverage targets** — > 80% for core logic

---

## Related
- [[01_pytest_advanced]]
- [[02_snapshot_testing]]
- [[05_test_parallelization]]
- [[../../00_Year0-2_Junior/06_FastAPI/13_asgi_internals_uvicorn_tuning]]
