"""Shared pytest fixtures.

Runs against the SAME Postgres/Redis docker-compose spins up for local dev
(exposed on host ports 5433/6380 — see docker-compose.yml) rather than
mocking the datastores. Every test uses a unique email/URL via uuid to
avoid colliding with other tests or manual testing you've done against the
same running stack.
"""

import os
import uuid

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://shortener:dev@localhost:5433/shortenerdb")
os.environ.setdefault("REDIS_URL", "redis://localhost:6380/0")
os.environ.setdefault("JWT_SECRET", "test-secret")

from app.db import engine, init_models  # noqa: E402
from app.main import app  # noqa: E402
from app.redis_client import get_redis  # noqa: E402


@pytest_asyncio.fixture(scope="session", autouse=True)
async def _init_db():
    await init_models()
    yield
    await engine.dispose()


@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
def unique_email() -> str:
    return f"test_{uuid.uuid4().hex[:12]}@example.com"


@pytest.fixture
def unique_url() -> str:
    return f"https://example.com/{uuid.uuid4().hex}"


@pytest_asyncio.fixture(autouse=True)
async def _isolate_rate_limits():
    """Rate limiting is keyed by IP/user and shared across tests in the same
    process — flush before each test so one test's requests don't eat into
    another's limit budget."""
    redis = get_redis()
    yield
    keys = await redis.keys("ratelimit:*")
    if keys:
        await redis.delete(*keys)
