import uuid

import pytest

from app.config import get_settings

pytestmark = pytest.mark.asyncio


async def test_anonymous_rate_limit_enforced(client):
    settings = get_settings()
    limit = settings.anon_shorten_per_minute

    statuses = []
    for _ in range(limit + 2):
        resp = await client.post("/shorten", json={"long_url": f"https://example.com/{uuid.uuid4().hex}"})
        statuses.append(resp.status_code)

    assert statuses.count(200) == limit, f"expected exactly {limit} successes, got {statuses.count(200)}: {statuses}"
    assert statuses[-1] == 429
    assert statuses[-2] == 429


async def test_authenticated_users_get_higher_limit(client, unique_email):
    settings = get_settings()
    signup = await client.post("/auth/signup", json={"email": unique_email, "password": "hunter22"})
    token = signup.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Authenticated limit is much higher than anonymous — confirm we can
    # exceed the ANONYMOUS limit without hitting 429 while authenticated.
    anon_limit = settings.anon_shorten_per_minute
    for i in range(anon_limit + 3):
        resp = await client.post("/shorten", json={"long_url": f"https://example.com/{uuid.uuid4().hex}"}, headers=headers)
        assert resp.status_code == 200, f"request {i+1} unexpectedly rate-limited while authenticated"
