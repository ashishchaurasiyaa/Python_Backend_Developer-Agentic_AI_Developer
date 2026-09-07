import uuid

import pytest

pytestmark = pytest.mark.asyncio


async def _signup_and_get_token(client, unique_email) -> str:
    resp = await client.post("/auth/signup", json={"email": unique_email, "password": "hunter22"})
    return resp.json()["access_token"]


async def test_anonymous_shorten_succeeds(client, unique_url):
    resp = await client.post("/shorten", json={"long_url": unique_url})
    assert resp.status_code == 200
    body = resp.json()
    assert body["long_url"] == unique_url
    assert len(body["code"]) > 0
    assert body["short_url"].endswith(body["code"])


async def test_anonymous_custom_alias_rejected(client, unique_url):
    resp = await client.post("/shorten", json={"long_url": unique_url, "custom_alias": "should-fail-anon"})
    assert resp.status_code == 403


async def test_authenticated_custom_alias_succeeds(client, unique_email, unique_url):
    token = await _signup_and_get_token(client, unique_email)
    alias = f"alias-{uuid.uuid4().hex[:8]}"
    resp = await client.post(
        "/shorten",
        json={"long_url": unique_url, "custom_alias": alias},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["code"] == alias


async def test_duplicate_custom_alias_conflicts(client, unique_email, unique_url):
    token = await _signup_and_get_token(client, unique_email)
    alias = f"alias-{uuid.uuid4().hex[:8]}"
    headers = {"Authorization": f"Bearer {token}"}

    first = await client.post("/shorten", json={"long_url": unique_url, "custom_alias": alias}, headers=headers)
    assert first.status_code == 200

    second = await client.post("/shorten", json={"long_url": "https://different.example.com", "custom_alias": alias}, headers=headers)
    assert second.status_code == 409


async def test_invalid_alias_format_rejected(client, unique_email, unique_url):
    token = await _signup_and_get_token(client, unique_email)
    resp = await client.post(
        "/shorten",
        json={"long_url": unique_url, "custom_alias": "a"},  # too short, min 3 chars
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 422  # pydantic validation error


async def test_generated_codes_are_unique(client):
    codes = set()
    for _ in range(5):
        resp = await client.post("/shorten", json={"long_url": f"https://example.com/{uuid.uuid4().hex}"})
        codes.add(resp.json()["code"])
    assert len(codes) == 5
