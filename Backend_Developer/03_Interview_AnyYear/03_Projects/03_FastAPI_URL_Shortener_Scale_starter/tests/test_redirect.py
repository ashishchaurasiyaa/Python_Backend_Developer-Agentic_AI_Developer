import asyncio

import pytest

pytestmark = pytest.mark.asyncio


async def _shorten(client, long_url, **extra) -> str:
    resp = await client.post("/shorten", json={"long_url": long_url, **extra})
    return resp.json()["code"]


async def test_redirect_returns_302_to_long_url(client, unique_url):
    code = await _shorten(client, unique_url)
    resp = await client.get(f"/{code}", follow_redirects=False)
    assert resp.status_code == 302
    assert resp.headers["location"] == unique_url + ("" if unique_url.endswith("/") else "")


async def test_redirect_unknown_code_404s(client):
    resp = await client.get("/definitely-does-not-exist-xyz")
    assert resp.status_code == 404


async def test_redirect_expired_url_returns_410(client, unique_url):
    code = await _shorten(client, unique_url, expires_in_hours=-1)  # already expired
    resp = await client.get(f"/{code}", follow_redirects=False)
    assert resp.status_code == 410


async def test_password_protected_url_shows_prompt_not_redirect(client, unique_url):
    code = await _shorten(client, unique_url, password="secret123")
    resp = await client.get(f"/{code}", follow_redirects=False)
    assert resp.status_code == 200  # HTML prompt, not a redirect
    assert "password" in resp.text.lower()


async def test_click_count_increments_after_redirect(client, unique_email, unique_url):
    signup = await client.post("/auth/signup", json={"email": unique_email, "password": "hunter22"})
    token = signup.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    shorten_resp = await client.post("/shorten", json={"long_url": unique_url}, headers=headers)
    code = shorten_resp.json()["code"]

    await client.get(f"/{code}", follow_redirects=False)
    await asyncio.sleep(0.3)  # click tracking is fire-and-forget (asyncio.create_task), give it a beat

    urls = await client.get("/me/urls", headers=headers)
    match = next(u for u in urls.json() if u["code"] == code)
    assert match["click_count"] == 1


async def test_qr_code_returns_png(client, unique_url):
    code = await _shorten(client, unique_url)
    resp = await client.get(f"/{code}/qr.png")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "image/png"
    assert resp.content[:8] == b"\x89PNG\r\n\x1a\n"  # real PNG magic bytes, not a stub


async def test_qr_code_unknown_url_404s(client):
    resp = await client.get("/no-such-code/qr.png")
    assert resp.status_code == 404
