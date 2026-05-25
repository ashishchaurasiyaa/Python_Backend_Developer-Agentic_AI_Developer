"""
API Security Hardening — Production Patterns
"""

import hashlib
import hmac
import ipaddress
import os
import secrets
import socket
import time
import uuid
from urllib.parse import urlparse

import jwt
from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, EmailStr, Field, field_validator


app = FastAPI()


# ==========================================================================
# 1. JWT VALIDATION (strict)
# ==========================================================================

JWT_SECRET = os.environ.get('JWT_SECRET', '')
if not JWT_SECRET or len(JWT_SECRET) < 32:
    raise RuntimeError('JWT_SECRET must be at least 32 chars')

JWT_ALGORITHM = 'HS256'


def create_jwt(user_id: int, scopes: list[str] = None, ttl_minutes: int = 15):
    payload = {
        'sub': str(user_id),
        'scopes': scopes or [],
        'iat': int(time.time()),
        'exp': int(time.time() + ttl_minutes * 60),
        'jti': str(uuid.uuid4()),   # unique token ID for blacklist
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_jwt(token: str):
    try:
        return jwt.decode(
            token,
            JWT_SECRET,
            algorithms=[JWT_ALGORITHM],   # explicit — no 'none'
            options={
                'verify_signature': True,
                'verify_exp': True,
                'verify_iat': True,
                'require': ['exp', 'iat', 'sub'],
            },
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, 'Token expired')
    except jwt.InvalidTokenError as e:
        raise HTTPException(401, f'Invalid token: {e}')


# ==========================================================================
# 2. AUTH DEPENDENCY
# ==========================================================================

class CurrentUser(BaseModel):
    id: int
    email: str
    role: str = 'user'
    is_admin: bool = False
    tier: str = 'free'
    scopes: list[str] = []
    tenant_id: int | None = None


async def get_current_user(authorization: str = Header(...)) -> CurrentUser:
    if not authorization.startswith('Bearer '):
        raise HTTPException(401, 'Missing Bearer token')

    token = authorization[7:]
    payload = decode_jwt(token)

    # Check blacklist (Redis)
    # if redis_client.sismember('jwt:blacklist', payload['jti']):
    #     raise HTTPException(401, 'Revoked')

    return CurrentUser(
        id=int(payload['sub']),
        email=payload.get('email', ''),
        role=payload.get('role', 'user'),
        is_admin=payload.get('is_admin', False),
        tier=payload.get('tier', 'free'),
        scopes=payload.get('scopes', []),
        tenant_id=payload.get('tenant_id'),
    )


def require_admin(user: CurrentUser = Depends(get_current_user)):
    if not user.is_admin:
        raise HTTPException(403, 'Admin required')
    return user


def require_scope(scope: str):
    def dep(user: CurrentUser = Depends(get_current_user)):
        if scope not in user.scopes:
            raise HTTPException(403, f'Missing scope: {scope}')
        return user
    return dep


# ==========================================================================
# 3. BOLA PREVENTION (Object-Level Authorization)
# ==========================================================================

orders_db = {
    1: {'id': 1, 'user_id': 1, 'amount': 100},
    2: {'id': 2, 'user_id': 2, 'amount': 200},
}


@app.get('/orders/{order_id}')
def get_order(order_id: int, user: CurrentUser = Depends(get_current_user)):
    order = orders_db.get(order_id)

    # Always check ownership
    if order is None or (order['user_id'] != user.id and not user.is_admin):
        # 404 not 403 — don't leak existence
        raise HTTPException(404, 'Order not found')

    return order


# ==========================================================================
# 4. MASS ASSIGNMENT PREVENTION
# ==========================================================================

class UserSelfUpdate(BaseModel):
    """ONLY user-editable fields. No is_admin, is_staff, password_hash."""

    name: str | None = Field(None, max_length=100)
    bio: str | None = Field(None, max_length=500)
    avatar_url: str | None = None


class AdminUserUpdate(BaseModel):
    """Admin can edit more, but still NO password_hash."""

    name: str | None = None
    email: EmailStr | None = None
    is_admin: bool | None = None
    is_active: bool | None = None
    tier: str | None = None


@app.patch('/users/me')
def update_self(payload: UserSelfUpdate, user: CurrentUser = Depends(get_current_user)):
    # Whitelist enforced by Pydantic model
    updates = payload.model_dump(exclude_unset=True)
    # ... db.update_user(user.id, **updates)
    return {'updated': list(updates.keys())}


@app.patch('/admin/users/{user_id}', dependencies=[Depends(require_admin)])
def admin_update(user_id: int, payload: AdminUserUpdate):
    updates = payload.model_dump(exclude_unset=True)
    return {'updated': list(updates.keys())}


# ==========================================================================
# 5. RESOURCE CONSUMPTION LIMITS
# ==========================================================================

from fastapi import Query, File, UploadFile


@app.get('/items')
def list_items(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),   # MAX 100
):
    return [{'id': i} for i in range(skip, skip + limit)]


@app.post('/upload')
async def upload(file: UploadFile = File(...)):
    MAX_SIZE = 10 * 1024 * 1024

    size = 0
    chunks = []
    while True:
        chunk = await file.read(1024 * 64)
        if not chunk:
            break
        size += len(chunk)
        if size > MAX_SIZE:
            raise HTTPException(413, 'File too large')
        chunks.append(chunk)
    return {'size': size}


# ==========================================================================
# 6. SSRF PREVENTION
# ==========================================================================

BLOCKED_NETS = [
    ipaddress.ip_network('127.0.0.0/8'),
    ipaddress.ip_network('10.0.0.0/8'),
    ipaddress.ip_network('172.16.0.0/12'),
    ipaddress.ip_network('192.168.0.0/16'),
    ipaddress.ip_network('169.254.0.0/16'),  # AWS metadata!
    ipaddress.ip_network('::1/128'),
    ipaddress.ip_network('fc00::/7'),
]


def validate_url(url: str):
    parsed = urlparse(url)
    if parsed.scheme not in {'http', 'https'}:
        raise HTTPException(400, 'Only http/https')

    hostname = parsed.hostname
    if not hostname:
        raise HTTPException(400, 'Missing hostname')

    try:
        infos = socket.getaddrinfo(hostname, None)
    except socket.gaierror:
        raise HTTPException(400, 'DNS resolution failed')

    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        for net in BLOCKED_NETS:
            if ip in net:
                raise HTTPException(400, f'Blocked IP range: {ip}')


@app.post('/fetch-url')
async def fetch_url(url: str, user: CurrentUser = Depends(get_current_user)):
    import httpx

    validate_url(url)

    async with httpx.AsyncClient(
        timeout=5.0,
        follow_redirects=False,
    ) as client:
        resp = await client.get(url)

    # Validate response size
    if int(resp.headers.get('content-length', 0)) > 1_000_000:
        raise HTTPException(502, 'Response too large')

    return {'status': resp.status_code}


# ==========================================================================
# 7. SECURITY HEADERS MIDDLEWARE
# ==========================================================================

SECURITY_HEADERS = {
    'Strict-Transport-Security': 'max-age=31536000; includeSubDomains; preload',
    'X-Content-Type-Options': 'nosniff',
    'X-Frame-Options': 'DENY',
    'Referrer-Policy': 'no-referrer',
    'Permissions-Policy': 'geolocation=(), camera=(), microphone=()',
    'Content-Security-Policy': "default-src 'none'; script-src 'self'",
}


@app.middleware('http')
async def security_headers_middleware(request: Request, call_next):
    response = await call_next(request)
    for k, v in SECURITY_HEADERS.items():
        response.headers[k] = v
    return response


# ==========================================================================
# 8. CORS (strict)
# ==========================================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=['https://app.example.com'],   # NEVER ['*'] with credentials
    allow_credentials=True,
    allow_methods=['GET', 'POST', 'PUT', 'PATCH', 'DELETE'],
    allow_headers=['Authorization', 'Content-Type', 'X-CSRF-Token'],
    expose_headers=['X-Trace-Id', 'X-RateLimit-Remaining'],
    max_age=3600,
)


# ==========================================================================
# 9. API KEY AUTH (machine-to-machine)
# ==========================================================================

# api_keys table:
#   id, user_id, key_hash, name, scopes, last_used_at, expires_at, revoked_at

api_keys_db = {
    'hashed_key_abc123': {
        'user_id': 1,
        'name': 'CI Deploy Key',
        'scopes': ['deploy', 'logs:read'],
        'active': True,
    },
}


def hash_api_key(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


def generate_api_key() -> tuple[str, str]:
    """Returns (raw_key, hashed_key)."""
    raw = f'sk_live_{secrets.token_urlsafe(32)}'
    return raw, hash_api_key(raw)


async def authenticate_api_key(x_api_key: str = Header(...)) -> dict:
    if not x_api_key.startswith('sk_'):
        raise HTTPException(401, 'Invalid key format')

    hashed = hash_api_key(x_api_key)
    key_record = api_keys_db.get(hashed)

    if not key_record or not key_record.get('active'):
        raise HTTPException(401, 'Invalid or revoked API key')

    # Update last_used_at (async, don't block response)
    # await update_last_used(hashed)

    return key_record


@app.get('/api/keyed-endpoint')
async def keyed(key=Depends(authenticate_api_key)):
    return {'user_id': key['user_id'], 'scopes': key['scopes']}


# ==========================================================================
# 10. HMAC SIGNATURE VERIFICATION (webhooks)
# ==========================================================================

WEBHOOK_SECRET = os.environ.get('WEBHOOK_SECRET', '').encode()


def verify_hmac_signature(body: bytes, signature: str, timestamp: int) -> bool:
    """Verify with constant-time compare + timestamp window."""
    # Replay protection — reject old requests
    if abs(time.time() - timestamp) > 300:   # 5 min window
        return False

    payload = f'{timestamp}.'.encode() + body
    expected = hmac.new(WEBHOOK_SECRET, payload, hashlib.sha256).hexdigest()

    return hmac.compare_digest(expected, signature)


@app.post('/webhook/incoming')
async def webhook(
    request: Request,
    x_signature: str = Header(...),
    x_timestamp: int = Header(...),
    x_event_id: str = Header(...),
):
    body = await request.body()

    sig = x_signature.removeprefix('sha256=')
    if not verify_hmac_signature(body, sig, x_timestamp):
        raise HTTPException(401, 'Invalid signature')

    # Idempotency — Redis SETNX
    # if not redis_client.set(f'webhook:{x_event_id}', '1', ex=86400, nx=True):
    #     return {'status': 'duplicate'}

    # ... process
    return {'received': True}


# ==========================================================================
# 11. INPUT VALIDATION (Pydantic)
# ==========================================================================

class UserCreateIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=12, max_length=128)
    name: str = Field(min_length=1, max_length=100, pattern=r'^[\w\s.\-\']+$')
    age: int | None = Field(None, ge=13, le=150)

    @field_validator('password')
    @classmethod
    def password_strength(cls, v):
        if not any(c.isupper() for c in v):
            raise ValueError('Password needs uppercase')
        if not any(c.islower() for c in v):
            raise ValueError('Password needs lowercase')
        if not any(c.isdigit() for c in v):
            raise ValueError('Password needs digit')
        if not any(c in '!@#$%^&*()_+-=[]{}|;:,.<>?' for c in v):
            raise ValueError('Password needs special character')
        return v

    @field_validator('email')
    @classmethod
    def reject_disposable(cls, v):
        DISPOSABLE = {'mailinator.com', 'tempmail.com', '10minutemail.com'}
        domain = v.split('@')[1].lower()
        if domain in DISPOSABLE:
            raise ValueError(f'Disposable email not allowed: {domain}')
        return v


@app.post('/users')
def create_user(payload: UserCreateIn):
    # All validation done by Pydantic
    return {'created': True}


# ==========================================================================
# 12. RESPONSE MODEL (whitelist output fields)
# ==========================================================================

class UserOut(BaseModel):
    """Whitelist — no password_hash, no internal_notes."""

    id: int
    email: EmailStr
    name: str
    role: str
    created_at: str


@app.get('/users/{user_id}', response_model=UserOut)
def get_user(user_id: int):
    # Even if DB returns more fields, response only includes UserOut fields
    return {
        'id': user_id,
        'email': 'u@example.com',
        'name': 'Alice',
        'role': 'user',
        'created_at': '2026-01-01',
        'password_hash': 'should-not-leak',   # excluded by response_model
        'internal_notes': 'should-not-leak',
    }


# ==========================================================================
# 13. AUDIT LOGGING
# ==========================================================================

import logging


audit_log = logging.getLogger('audit')


def log_security_event(event_type: str, user_id: int | None, **details):
    audit_log.info(
        event_type,
        extra={
            'event_type': event_type,
            'user_id': user_id,
            'timestamp': time.time(),
            **details,
        },
    )


@app.post('/login')
async def login(payload: dict, request: Request):
    # ... validate password ...
    success = False

    if not success:
        log_security_event(
            'login_failed',
            user_id=None,
            email=payload.get('email'),
            ip=request.client.host,
            user_agent=request.headers.get('user-agent', ''),
        )
        raise HTTPException(401, 'Invalid credentials')

    log_security_event('login_success', user_id=1, ip=request.client.host)
    return {'token': '...'}


# ==========================================================================
# 14. GENERIC EXCEPTION HANDLER (no info leak)
# ==========================================================================

@app.exception_handler(Exception)
async def unhandled_exception(request: Request, exc: Exception):
    trace_id = str(uuid.uuid4())

    log = logging.getLogger(__name__)
    log.exception(
        f'Unhandled exception trace_id={trace_id}',
        exc_info=exc,
        extra={'trace_id': trace_id, 'path': request.url.path},
    )

    return JSONResponse(
        {
            'error': 'Internal server error',
            'detail': 'An unexpected error occurred. Contact support with trace_id.',
            'trace_id': trace_id,
        },
        status_code=500,
        headers={'X-Trace-Id': trace_id},
    )


# ==========================================================================
# 15. STARTUP CHECKS (fail fast on misconfig)
# ==========================================================================

@app.on_event('startup')
async def startup_security_checks():
    required_env = [
        'JWT_SECRET',
        'DATABASE_URL',
        'REDIS_URL',
    ]
    for var in required_env:
        if not os.environ.get(var):
            raise RuntimeError(f'Missing required env: {var}')

    if len(os.environ.get('JWT_SECRET', '')) < 32:
        raise RuntimeError('JWT_SECRET too weak (min 32 chars)')

    if os.environ.get('DEBUG', '').lower() == 'true' and os.environ.get('ENV') == 'production':
        raise RuntimeError('DEBUG=True in production — refusing to start')


# ==========================================================================
# 16. SECURITY CHECKLIST
# ==========================================================================

SECURITY_CHECKLIST = """
Pre-deploy:

[ ] Secrets in env vars (never in code)
[ ] JWT_SECRET >= 32 chars
[ ] DEBUG=False in production
[ ] TLS / HTTPS everywhere (HSTS header set)
[ ] CORS — specific origins, not '*'
[ ] Rate limiting at edge + app
[ ] Authentication on every endpoint (default deny)
[ ] Object-level auth checks (BOLA prevention)
[ ] Mass assignment prevention (whitelist Pydantic models)
[ ] Input validation (size, format, range)
[ ] Output filtering (response_model whitelist)
[ ] SSRF protection (URL validation, no redirects)
[ ] SQL injection (ORM, no string formatting)
[ ] XSS escaped in any HTML responses
[ ] Logging: failed logins, admin actions, perm changes
[ ] No stack traces in 500 responses
[ ] Dependencies audited (pip-audit, safety)
[ ] Penetration tested before major launches
"""
