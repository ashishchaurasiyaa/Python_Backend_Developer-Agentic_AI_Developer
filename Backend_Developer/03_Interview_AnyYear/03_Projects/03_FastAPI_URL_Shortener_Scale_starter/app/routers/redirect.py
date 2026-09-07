"""GET /{short_code} — the hot path (spec section 7). Redis cache-aside first,
Postgres fallback, async click tracking that never blocks the redirect.

NOT implemented here (documented scope decision, see README): the Kafka ->
Clickhouse click pipeline. Click tracking below increments a denormalized
counter directly on the row instead — correct at this project's scale,
would need to move to the async pipeline before real production traffic.
"""

import asyncio
import hashlib
import json
from datetime import datetime, timezone
from io import BytesIO

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import AsyncSessionLocal, get_session
from app.models import URL
from app.redis_client import get_redis

router = APIRouter(tags=["redirect"])
settings = get_settings()


def _cache_key(short_code: str) -> str:
    return f"url:{short_code}"


@router.get("/{short_code}")
async def redirect(short_code: str, request: Request, session: AsyncSession = Depends(get_session)):
    redis = get_redis()
    cache_key = _cache_key(short_code)

    cached = await redis.get(cache_key)
    if cached:
        url_data = json.loads(cached)
    else:
        result = await session.execute(select(URL).where(URL.short_code == short_code, URL.deleted_at.is_(None)))
        url_row = result.scalar_one_or_none()
        if url_row is None:
            raise HTTPException(status_code=404, detail="URL not found")

        url_data = {
            "long_url": url_row.long_url,
            "expires_at": url_row.expires_at.isoformat() if url_row.expires_at else None,
            "password_hash": url_row.password_hash,
        }
        await redis.set(cache_key, json.dumps(url_data), ex=settings.redirect_cache_ttl_seconds)

    if url_data["expires_at"]:
        expires_at = datetime.fromisoformat(url_data["expires_at"])
        if expires_at < datetime.now(timezone.utc):
            raise HTTPException(status_code=410, detail="URL has expired")

    if url_data["password_hash"]:
        return HTMLResponse(_password_prompt_html(short_code))

    asyncio.create_task(_track_click(short_code, request))
    return RedirectResponse(url_data["long_url"], status_code=302)


async def _track_click(short_code: str, request: Request) -> None:
    """Fire-and-forget — the redirect above never awaits this. Uses its own
    DB session since the request's session may already be closed by the
    time this task actually runs."""
    ip = request.client.host if request.client else "unknown"
    ip_hash = hashlib.sha256(ip.encode()).hexdigest()[:16]  # never store raw IPs
    _ = {
        "short_code": short_code,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "ip_hash": ip_hash,
        "user_agent": request.headers.get("user-agent", ""),
        "referer": request.headers.get("referer", ""),
    }
    # Real deploy: await kafka_producer.send("clicks", event) -> Clickhouse consumer.
    # This project's scope: increment the denormalized counter directly.
    try:
        async with AsyncSessionLocal() as click_session:
            await click_session.execute(update(URL).where(URL.short_code == short_code).values(click_count=URL.click_count + 1))
            await click_session.commit()
    except Exception:
        pass  # click tracking must never take down the redirect path


def _password_prompt_html(short_code: str) -> str:
    return f"""<!doctype html><html><body>
<form method="post" action="/{short_code}/unlock">
  <p>This link is password-protected.</p>
  <input type="password" name="password" placeholder="Password" required>
  <button type="submit">Continue</button>
</form>
</body></html>"""


@router.get("/{short_code}/qr.png")
async def qr_code(short_code: str, size: int = 200, session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(URL).where(URL.short_code == short_code, URL.deleted_at.is_(None)))
    if result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="URL not found")

    import qrcode

    url = f"https://{settings.base_domain}/{short_code}"
    qr = qrcode.QRCode(version=1, box_size=10, border=4)
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white").resize((size, size))
    buf = BytesIO()
    img.save(buf, "PNG")
    buf.seek(0)
    return StreamingResponse(buf, media_type="image/png", headers={"Cache-Control": "public, max-age=86400, immutable"})
