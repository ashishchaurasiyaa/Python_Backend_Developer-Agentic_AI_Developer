"""
URL Shortener at Scale (Bitly-clone) — skeleton entry point.
Spec: ../03_FastAPI_URL_Shortener_Scale.md

Run:
    uvicorn main:app --reload
"""

import os
import time
import hashlib
import asyncio
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import RedirectResponse, StreamingResponse, JSONResponse
from pydantic import BaseModel, HttpUrl

app = FastAPI(title="URL Shortener at Scale", version="0.1.0")

# Worker ID for Snowflake ID generation (set via env in production)
WORKER_ID = int(os.environ.get("WORKER_ID", 0))

# ---------------------------------------------------------------------------
# Snowflake-based short code generator
# ---------------------------------------------------------------------------

class SnowflakeID:
    """
    64-bit ID:  1 reserved | 41 timestamp_ms | 10 worker_id | 12 sequence
    See spec section 5 for full detail.
    """
    EPOCH = 1704067200000  # 2024-01-01

    def __init__(self, worker_id: int):
        self.worker_id = worker_id & 0x3FF
        self.sequence = 0
        self.last_ts = 0

    def next_id(self) -> int:
        ts = int(time.time() * 1000)
        if ts == self.last_ts:
            self.sequence = (self.sequence + 1) & 0xFFF
            if self.sequence == 0:
                while ts <= self.last_ts:
                    ts = int(time.time() * 1000)
        else:
            self.sequence = 0
        self.last_ts = ts
        return ((ts - self.EPOCH) << 22) | (self.worker_id << 12) | self.sequence


_snowflake = SnowflakeID(WORKER_ID)
_B62_CHARS = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"


def to_base62(num: int) -> str:
    if num == 0:
        return _B62_CHARS[0]
    result = []
    while num > 0:
        result.append(_B62_CHARS[num % 62])
        num //= 62
    return "".join(reversed(result))


def gen_short_code() -> str:
    return to_base62(_snowflake.next_id())[-7:]


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

@app.get("/health")
async def health():
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Shorten endpoint  (Week 1 milestone)
# ---------------------------------------------------------------------------

class ShortenRequest(BaseModel):
    long_url: HttpUrl
    custom_alias: str | None = None
    expires_in_hours: int | None = None
    password: str | None = None


@app.post("/shorten")
async def shorten(req: ShortenRequest):
    """
    Create a short URL.  Authenticated users may add custom alias / password.
    """
    # TODO: optional_auth() — check JWT or API key in header
    # TODO: is_url_blacklisted(req.long_url) — Google Safe Browsing API
    # TODO: custom alias validation (paid feature)
    # TODO: generate code via gen_short_code() with collision retry
    # TODO: hash password if provided (bcrypt)
    # TODO: insert into urls table
    # TODO: warm Redis cache: SETEX url:{code} 3600 <json>
    code = gen_short_code()
    return {
        "short_url": f"https://shrt.ly/{code}",
        "code": code,
        "long_url": str(req.long_url),
        "expires_at": None,
        "detail": "TODO: DB persistence not yet implemented",
    }


# ---------------------------------------------------------------------------
# Redirect endpoint — HOT PATH  (Week 1 milestone)
# ---------------------------------------------------------------------------

@app.get("/{short_code}")
async def redirect(short_code: str, request: Request):
    """
    Redirect short_code -> long_url.  Redis cache first, DB fallback.
    Click tracking is fire-and-forget (async Kafka producer).
    """
    # TODO: check Redis cache: GET url:{short_code}
    # TODO: if cache miss: SELECT from urls WHERE short_code = $1 AND deleted_at IS NULL
    # TODO: if not found: raise 404
    # TODO: check expiry; return 410 Gone if expired
    # TODO: check password protection; return HTML password form if needed
    # TODO: asyncio.create_task(track_click(short_code, request))
    # TODO: return RedirectResponse(long_url, status_code=302)

    # Placeholder — replace with real lookup
    raise HTTPException(status_code=404, detail="URL not found (TODO: implement lookup)")


# ---------------------------------------------------------------------------
# QR code  (Week 2 milestone)
# ---------------------------------------------------------------------------

@app.get("/{short_code}/qr.png")
async def qr_code(short_code: str, size: int = 200):
    """Generate and return QR code image for a short URL."""
    # TODO: verify short_code exists
    # TODO: generate QR via qrcode library
    # TODO: cache-control: public, max-age=86400, immutable
    import qrcode
    from io import BytesIO
    url = f"https://shrt.ly/{short_code}"
    qr = qrcode.QRCode(version=1, box_size=10, border=4)
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white").resize((size, size))
    buf = BytesIO()
    img.save(buf, "PNG")
    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="image/png",
        headers={"Cache-Control": "public, max-age=86400, immutable"},
    )


# ---------------------------------------------------------------------------
# Analytics endpoints  (Week 2 milestone)
# ---------------------------------------------------------------------------
# TODO: GET /me/urls                          — list user's URLs
# TODO: GET /me/urls/{id}/analytics           — per-URL stats (Clickhouse query)
# TODO: GET /me/urls/{id}/clicks?from=&to=    — raw click events

# ---------------------------------------------------------------------------
# Auth / API keys  (Week 2 milestone)
# ---------------------------------------------------------------------------
# TODO: POST /auth/signup
# TODO: POST /auth/login
# TODO: GET  /me/api-keys
# TODO: POST /me/api-keys
# TODO: DELETE /me/api-keys/{id}

# ---------------------------------------------------------------------------
# Click tracking (background task)
# ---------------------------------------------------------------------------
async def track_click(short_code: str, request: Request) -> None:
    """
    Fire-and-forget.  Publish event to Kafka; Kafka consumer writes to Clickhouse.
    """
    # TODO: build event dict (short_code, timestamp, ip_hash, user_agent, referer, country)
    # TODO: await kafka_producer.send("clicks", event)
    pass
