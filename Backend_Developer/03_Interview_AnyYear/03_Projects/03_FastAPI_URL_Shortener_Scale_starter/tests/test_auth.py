import pytest

pytestmark = pytest.mark.asyncio


async def test_signup_returns_token(client, unique_email):
    resp = await client.post("/auth/signup", json={"email": unique_email, "password": "hunter22"})
    assert resp.status_code == 201
    body = resp.json()
    assert "access_token" in body
    assert body["token_type"] == "bearer"


async def test_signup_duplicate_email_rejected(client, unique_email):
    await client.post("/auth/signup", json={"email": unique_email, "password": "hunter22"})
    resp = await client.post("/auth/signup", json={"email": unique_email, "password": "different"})
    assert resp.status_code == 409


async def test_login_success(client, unique_email):
    await client.post("/auth/signup", json={"email": unique_email, "password": "hunter22"})
    resp = await client.post("/auth/login", json={"email": unique_email, "password": "hunter22"})
    assert resp.status_code == 200
    assert "access_token" in resp.json()


async def test_login_wrong_password_rejected(client, unique_email):
    await client.post("/auth/signup", json={"email": unique_email, "password": "hunter22"})
    resp = await client.post("/auth/login", json={"email": unique_email, "password": "wrong-password"})
    assert resp.status_code == 401


async def test_login_unknown_email_rejected(client, unique_email):
    resp = await client.post("/auth/login", json={"email": unique_email, "password": "whatever"})
    assert resp.status_code == 401
