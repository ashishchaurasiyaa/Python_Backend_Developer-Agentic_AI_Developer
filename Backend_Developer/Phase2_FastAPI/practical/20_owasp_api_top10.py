"""
OWASP API Top 10 — FastAPI Mitigations

Practical defense patterns for each item.
"""

import hmac
import hashlib
import ipaddress
import secrets
import socket
from urllib.parse import urlparse

import httpx
import jwt
from fastapi import FastAPI, Depends, HTTPException, Header, Query, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded


app = FastAPI(
    title="Hardened API",
    debug=False,   # NEVER True in prod
    # Optional: hide /docs in prod
    # docs_url=None,
    # redoc_url=None,
    # openapi_url=None,
)


# ==========================================================================
# 1. RATE LIMITING (slowapi)
# ==========================================================================

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


# ==========================================================================
# 2. CORS (no wildcards in prod)
# ==========================================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://app.example.com"],  # explicit list
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type", "X-CSRF-Token"],
    max_age=3600,
)


# ==========================================================================
# 3. CURRENT USER (with scopes)
# ==========================================================================

JWT_SECRET = "your-jwt-secret"


class CurrentUser(BaseModel):
    id: int
    email: str
    is_admin: bool = False
    scopes: list[str] = []


async def get_current_user(authorization: str = Header(...)) -> CurrentUser:
    if not authorization.startswith("Bearer "):
        raise HTTPException(401, "Invalid auth header")
    token = authorization[7:]
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])  # explicit alg list
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(401, "Invalid token")
    return CurrentUser(**payload)


def require_admin(user: CurrentUser = Depends(get_current_user)):
    if not user.is_admin:
        raise HTTPException(403, "Admin required")
    return user


# ==========================================================================
# 4. BOLA PREVENTION (Object-Level Authorization)
# ==========================================================================

# Mock DB
orders_db = {
    1: {"id": 1, "user_id": 1, "amount": 100},
    2: {"id": 2, "user_id": 2, "amount": 200},
}


@app.get("/orders/{order_id}")
def get_order(order_id: int, user: CurrentUser = Depends(get_current_user)):
    order = orders_db.get(order_id)
    if order is None:
        raise HTTPException(404)
    # Owner OR admin
    if order["user_id"] != user.id and not user.is_admin:
        # 404 not 403 → avoid existence leak
        raise HTTPException(404)
    return order


# ==========================================================================
# 5. MASS ASSIGNMENT PREVENTION
# ==========================================================================

class UserSelfUpdate(BaseModel):
    """Only user-editable fields. NO is_admin, NO email_verified."""

    name: str | None = Field(None, max_length=100)
    bio: str | None = Field(None, max_length=500)


class AdminUserUpdate(BaseModel):
    """Admin-only edits."""

    name: str | None = None
    email: str | None = None
    is_admin: bool | None = None
    email_verified: bool | None = None


@app.patch("/users/me")
def update_self(
    payload: UserSelfUpdate,
    user: CurrentUser = Depends(get_current_user),
):
    # Only writable fields exposed
    updates = payload.model_dump(exclude_unset=True)
    # ... db.update_user(user.id, **updates)
    return {"updated": list(updates.keys())}


@app.patch("/admin/users/{user_id}", dependencies=[Depends(require_admin)])
def admin_update_user(user_id: int, payload: AdminUserUpdate):
    updates = payload.model_dump(exclude_unset=True)
    # ... db.update_user(user_id, **updates)
    return {"updated": list(updates.keys())}


# ==========================================================================
# 6. RESOURCE CONSUMPTION LIMITS
# ==========================================================================

@app.get("/articles/")
def list_articles(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),  # MAX 100 — prevents huge pages
):
    return [{"id": i, "title": f"Article {i}"} for i in range(skip, skip + limit)]


# File upload size limit
from fastapi import File, UploadFile


@app.post("/upload")
async def upload(file: UploadFile = File(...)):
    MAX_SIZE = 10 * 1024 * 1024  # 10 MB

    # Read in chunks; reject if too large
    size = 0
    chunks = []
    while True:
        chunk = await file.read(1024 * 64)
        if not chunk:
            break
        size += len(chunk)
        if size > MAX_SIZE:
            raise HTTPException(413, "File too large")
        chunks.append(chunk)
    return {"size": size}


# ==========================================================================
# 7. LOGIN — rate limit + uniform error message
# ==========================================================================

class LoginIn(BaseModel):
    email: str
    password: str


@app.post("/login")
@limiter.limit("5/minute")
async def login(request: Request, payload: LoginIn):
    # Lookup user
    # user = db.find_user(payload.email)

    # Uniform error to prevent enumeration
    # if not user or not bcrypt.checkpw(payload.password, user.password_hash):
    #     raise HTTPException(401, "Invalid credentials")  # NOT "user not found"

    # ... issue JWT
    return {"token": "..."}


# ==========================================================================
# 8. SSRF PREVENTION
# ==========================================================================

BLOCKED_NETWORKS = [
    ipaddress.ip_network('127.0.0.0/8'),
    ipaddress.ip_network('10.0.0.0/8'),
    ipaddress.ip_network('172.16.0.0/12'),
    ipaddress.ip_network('192.168.0.0/16'),
    ipaddress.ip_network('169.254.0.0/16'),  # AWS metadata
    ipaddress.ip_network('0.0.0.0/8'),
    ipaddress.ip_network('::1/128'),
    ipaddress.ip_network('fe80::/10'),
    ipaddress.ip_network('fc00::/7'),
]


class UnsafeUrl(Exception):
    pass


def validate_outbound_url(url: str):
    parsed = urlparse(url)
    if parsed.scheme not in {'http', 'https'}:
        raise UnsafeUrl("Only http/https allowed")

    hostname = parsed.hostname
    if not hostname:
        raise UnsafeUrl("Missing hostname")

    try:
        infos = socket.getaddrinfo(hostname, None)
    except socket.gaierror:
        raise UnsafeUrl("DNS resolution failed")

    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        for net in BLOCKED_NETWORKS:
            if ip in net:
                raise UnsafeUrl(f"Blocked private network: {ip}")


@app.post("/webhook-test")
async def webhook_test(url: str):
    try:
        validate_outbound_url(url)
    except UnsafeUrl as e:
        raise HTTPException(400, str(e))

    async with httpx.AsyncClient(timeout=5.0, follow_redirects=False) as c:
        resp = await c.get(url)
    return {"status": resp.status_code}


# ==========================================================================
# 9. SECURITY HEADERS MIDDLEWARE
# ==========================================================================

@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains; preload"
    response.headers["Referrer-Policy"] = "same-origin"
    response.headers["Permissions-Policy"] = "geolocation=(), camera=(), microphone=()"
    return response


# ==========================================================================
# 10. GENERIC EXCEPTION HANDLER (no stack trace leak)
# ==========================================================================

@app.exception_handler(Exception)
async def all_exception_handler(request: Request, exc: Exception):
    # Log full details server-side
    import logging
    logging.exception("Unhandled exception", exc_info=exc)
    # Return generic error
    return JSONResponse({"error": "Internal server error"}, status_code=500)


# ==========================================================================
# 11. WEBHOOK HMAC VERIFICATION + REPLAY PROTECTION
# ==========================================================================

WEBHOOK_SECRET = b"webhook-secret"
# In real app: Redis-backed
processed_events: set[str] = set()


@app.post("/webhook/incoming")
async def webhook(
    request: Request,
    x_signature: str = Header(...),
    x_event_id: str = Header(...),
    x_timestamp: int = Header(...),
):
    body = await request.body()

    # Timestamp window (5 min) — prevents old request replay
    import time
    if abs(time.time() - x_timestamp) > 300:
        raise HTTPException(400, "Timestamp out of window")

    # HMAC verify
    payload = f'{x_timestamp}.{body.decode()}'
    expected = hmac.new(WEBHOOK_SECRET, payload.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(x_signature, expected):
        raise HTTPException(401, "Invalid signature")

    # Idempotency / replay
    if x_event_id in processed_events:
        return {"status": "duplicate, ignored"}
    processed_events.add(x_event_id)

    # ... process event
    return {"status": "processed"}


# ==========================================================================
# 12. UNSAFE 3rd-PARTY API CONSUMPTION
# ==========================================================================

class ExternalProduct(BaseModel):
    """Validated shape — enforce schema on external response."""

    id: int
    name: str = Field(max_length=200)
    price_cents: int = Field(ge=0, le=10_000_000)  # sanity bounds


@app.get("/external-product/{product_id}")
async def get_external_product(product_id: int):
    async with httpx.AsyncClient(
        timeout=5.0,
        follow_redirects=False,
    ) as c:
        try:
            resp = await c.get(f'https://api.partner.example.com/products/{product_id}')
            resp.raise_for_status()
        except httpx.RequestError:
            raise HTTPException(502, "Upstream unavailable")
        except httpx.HTTPStatusError:
            raise HTTPException(502, "Upstream error")

        # Limit response size
        if int(resp.headers.get('content-length', 0)) > 1_000_000:
            raise HTTPException(502, "Response too large")

    try:
        product = ExternalProduct.model_validate(resp.json())
    except Exception:
        raise HTTPException(502, "Invalid upstream response")

    return product


# ==========================================================================
# 13. PASSWORD STRENGTH (avoid common passwords)
# ==========================================================================

def check_password_strength(password: str) -> bool:
    if len(password) < 12:
        return False
    if password.lower() in COMMON_PASSWORDS:
        return False
    # Etc — HaveIBeenPwned check, complexity
    return True


# Stub
COMMON_PASSWORDS = {"password123", "qwerty", "admin"}


# ==========================================================================
# 14. STARTUP CHECKS (fail fast on misconfig)
# ==========================================================================

@app.on_event("startup")
async def startup_checks():
    # Verify required env vars
    import os
    for var in ["JWT_SECRET", "DATABASE_URL"]:
        if not os.environ.get(var):
            raise RuntimeError(f"Missing required env: {var}")

    # Verify JWT_SECRET strong
    if len(os.environ.get("JWT_SECRET", "")) < 32:
        raise RuntimeError("JWT_SECRET too short — min 32 chars")
