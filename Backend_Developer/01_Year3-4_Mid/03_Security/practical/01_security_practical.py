"""
Phase3_Security — Complete Security Practical
==============================================
Topics covered:
  1. JWT: create/decode/blacklist/rotation
  2. JWT alg:none attack + fix demo
  3. Brute Force protection (Redis-based lockout)
  4. CSRF: double-submit cookie pattern
  5. TOTP 2FA with pyotp
  6. RBAC: role-based permission system
  7. OWASP: input validation, SQL injection prevention
  8. Audit logging (structured JSON)
  9. Security headers middleware
  10. Secrets config with pydantic-settings

Run:
  pip install fastapi uvicorn python-jose[cryptography] passlib[bcrypt]
              redis pyotp qrcode[pil] pydantic-settings python-multipart
  uvicorn 01_security_practical:app --reload

Note: Redis required for sections 3, 4, JWT blacklist.
      Start Redis: docker run -d -p 6379:6379 redis
"""

# ─── Imports ─────────────────────────────────────────────────────────────────
import asyncio
import hashlib
import io
import json
import logging
import os
import re
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Annotated

import pyotp
import qrcode
import base64

from fastapi import (
    Cookie,
    Depends,
    FastAPI,
    Header,
    HTTPException,
    Request,
    Response,
    status,
)
from fastapi.responses import JSONResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from jose import jwt, JWTError, ExpiredSignatureError
from passlib.context import CryptContext
from pydantic import BaseModel, EmailStr, field_validator, SecretStr
from pydantic_settings import BaseSettings

# ─────────────────────────────────────────────────────────────────────────────
# SECTION 0: Config with pydantic-settings
# ─────────────────────────────────────────────────────────────────────────────

class Settings(BaseSettings):
    jwt_secret_key:   str = secrets.token_hex(32)   # Generated at runtime (dev)
    jwt_algorithm:    str = "HS256"
    access_token_exp: int = 15    # minutes
    refresh_token_exp: int = 7    # days
    debug:            bool = False
    environment:      str = "development"
    redis_url:        str = "redis://localhost:6379"

    model_config = {"env_file": ".env", "case_sensitive": False}


settings = Settings()

print(f"\n{'='*60}")
print(f"JWT Secret (first 8 chars): {settings.jwt_secret_key[:8]}...")
print(f"Algorithm: {settings.jwt_algorithm}")
print(f"{'='*60}\n")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 1: JWT — Create, Decode, Blacklist
# ─────────────────────────────────────────────────────────────────────────────

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security    = HTTPBearer(auto_error=False)

# In-memory blacklist for demo (use Redis in production)
TOKEN_BLACKLIST: set[str] = set()

# Fake user store
FAKE_USERS = {
    "alice@example.com": {
        "id": 1,
        "email": "alice@example.com",
        "hashed_password": pwd_context.hash("Password123!"),
        "role": "admin",
        "totp_enabled": False,
        "totp_secret": None,
    },
    "bob@example.com": {
        "id": 2,
        "email": "bob@example.com",
        "hashed_password": pwd_context.hash("SecurePass456!"),
        "role": "user",
        "totp_enabled": False,
        "totp_secret": None,
    },
}


def create_access_token(data: dict, expires_minutes: int | None = None) -> str:
    """Create JWT access token with JTI for blacklisting."""
    exp = expires_minutes or settings.access_token_exp
    payload = {
        **data,
        "exp": datetime.now(timezone.utc) + timedelta(minutes=exp),
        "iat": datetime.now(timezone.utc),
        "jti": str(uuid.uuid4()),    # Unique ID for blacklisting
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> dict:
    """
    Decode JWT — SAFE version.
    INTERVIEW: Always pass algorithms= list to prevent alg:none attack!
    """
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],   # ← CRITICAL: explicit list
        )
        return payload
    except ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except JWTError as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {e}")


def get_token_jti(token: str) -> str | None:
    """Get JTI without signature verification (for blacklisting)."""
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
            options={"verify_exp": False},
        )
        return payload.get("jti")
    except JWTError:
        return None


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> dict:
    """JWT dependency — checks blacklist + decodes."""
    if not credentials:
        raise HTTPException(401, "Not authenticated")

    token = credentials.credentials

    # Check blacklist
    jti = get_token_jti(token)
    if jti and jti in TOKEN_BLACKLIST:
        raise HTTPException(401, "Token has been revoked")

    payload = decode_token(token)
    user_id = payload.get("sub")

    # Find user
    for user in FAKE_USERS.values():
        if str(user["id"]) == str(user_id):
            return user

    raise HTTPException(401, "User not found")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 2: RBAC — Role-Based Access Control
# ─────────────────────────────────────────────────────────────────────────────

class Role(str, Enum):
    ADMIN     = "admin"
    MODERATOR = "moderator"
    USER      = "user"


ROLE_PERMISSIONS: dict[Role, set[str]] = {
    Role.USER:      {"posts:read", "posts:create", "profile:read", "profile:update"},
    Role.MODERATOR: {"posts:read", "posts:create", "posts:delete", "profile:read",
                     "users:list"},
    Role.ADMIN:     {"posts:read", "posts:create", "posts:delete", "posts:update",
                     "users:list", "users:create", "users:delete", "admin:dashboard",
                     "profile:read", "profile:update"},
}


def require_permission(permission: str):
    """Factory dependency for permission-based auth."""
    async def _check(current_user: dict = Depends(get_current_user)) -> dict:
        role = Role(current_user.get("role", "user"))
        allowed = ROLE_PERMISSIONS.get(role, set())
        if permission not in allowed:
            raise HTTPException(
                status_code=403,
                detail=f"Permission '{permission}' required. Your role '{role}' is insufficient."
            )
        return current_user
    return _check


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 3: Brute Force Protection
# ─────────────────────────────────────────────────────────────────────────────

# In-memory store for demo (use Redis in production)
ATTEMPT_STORE: dict[str, int]   = {}
LOCKOUT_STORE: dict[str, float] = {}

MAX_ATTEMPTS = 5
LOCKOUT_SECONDS = 300   # 5 minutes


def get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "127.0.0.1"


def check_brute_force(identifier: str) -> None:
    """Check if identifier (email:ip) is locked out."""
    lockout_key  = f"lockout:{identifier}"
    attempts_key = f"attempts:{identifier}"

    # Check lockout
    if lockout_key in LOCKOUT_STORE:
        locked_until = LOCKOUT_STORE[lockout_key]
        remaining    = locked_until - datetime.now(timezone.utc).timestamp()
        if remaining > 0:
            raise HTTPException(
                status_code=429,
                detail=f"Too many failed attempts. Try again in {int(remaining)} seconds.",
                headers={"Retry-After": str(int(remaining))},
            )
        else:
            # Lockout expired
            del LOCKOUT_STORE[lockout_key]
            del ATTEMPT_STORE[attempts_key]


def record_failed_attempt(identifier: str) -> None:
    """Record a failed login attempt and lock if threshold reached."""
    attempts_key = f"attempts:{identifier}"
    lockout_key  = f"lockout:{identifier}"

    current = ATTEMPT_STORE.get(attempts_key, 0) + 1
    ATTEMPT_STORE[attempts_key] = current

    print(f"[BruteForce] {identifier}: {current}/{MAX_ATTEMPTS} failed attempts")

    if current >= MAX_ATTEMPTS:
        LOCKOUT_STORE[lockout_key] = (
            datetime.now(timezone.utc).timestamp() + LOCKOUT_SECONDS
        )
        print(f"[BruteForce] LOCKED: {identifier} for {LOCKOUT_SECONDS}s")


def clear_failed_attempts(identifier: str) -> None:
    """Clear attempts after successful login."""
    ATTEMPT_STORE.pop(f"attempts:{identifier}", None)
    LOCKOUT_STORE.pop(f"lockout:{identifier}", None)


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 4: CSRF Protection
# ─────────────────────────────────────────────────────────────────────────────

# CSRF token store: session_id → csrf_token
CSRF_TOKENS: dict[str, str] = {}


def generate_csrf_token() -> str:
    return secrets.token_urlsafe(32)


def set_csrf_cookie(response: Response, session_id: str) -> str:
    """Generate CSRF token and set in cookie (non-httpOnly so JS can read it)."""
    csrf_token = generate_csrf_token()
    CSRF_TOKENS[session_id] = csrf_token

    # Non-httpOnly: JS reads this → sends in X-CSRF-Token header
    response.set_cookie(
        key="csrf_token",
        value=csrf_token,
        httponly=False,     # ← JS must be able to read it
        samesite="strict",
        secure=False,       # True in production (HTTPS)
        max_age=3600,
    )
    return csrf_token


def require_csrf(
    x_csrf_token: str | None = Header(None, alias="X-CSRF-Token"),
    csrf_token: str | None = Cookie(None),
    session_id: str | None = Cookie(None),
) -> None:
    """
    CSRF protection — double submit cookie pattern.
    Header value must match cookie value.
    """
    if not x_csrf_token or not csrf_token:
        raise HTTPException(403, "CSRF token missing")

    if not secrets.compare_digest(x_csrf_token, csrf_token):
        raise HTTPException(403, "CSRF token mismatch")

    # Additional: verify token is in our store
    if session_id and CSRF_TOKENS.get(session_id) != csrf_token:
        raise HTTPException(403, "CSRF token invalid (not issued by server)")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 5: TOTP 2FA
# ─────────────────────────────────────────────────────────────────────────────

# Pending 2FA secrets (user_id → secret) — use Redis with TTL in production
PENDING_TOTP: dict[int, str] = {}

# Temp tokens for 2FA step
TEMP_TOKENS: dict[str, int] = {}   # token → user_id


def generate_totp_secret() -> str:
    return pyotp.random_base32()


def generate_qr_code_base64(secret: str, email: str, issuer: str = "MyApp") -> str:
    """Generate QR code PNG as base64 string."""
    totp = pyotp.TOTP(secret)
    uri  = totp.provisioning_uri(name=email, issuer_name=issuer)

    img = qrcode.make(uri)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


def verify_totp_code(secret: str, code: str) -> bool:
    """Verify TOTP code with ±1 window for clock skew."""
    totp = pyotp.TOTP(secret)
    return totp.verify(code, valid_window=1)


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 6: Audit Logging
# ─────────────────────────────────────────────────────────────────────────────

class AuditAction(str, Enum):
    LOGIN_SUCCESS    = "auth.login.success"
    LOGIN_FAILED     = "auth.login.failed"
    LOGIN_LOCKED     = "auth.login.locked"
    LOGOUT           = "auth.logout"
    TOKEN_REVOKED    = "auth.token.revoked"
    TWO_FA_SETUP     = "auth.2fa.setup"
    TWO_FA_ENABLED   = "auth.2fa.enabled"
    TWO_FA_SUCCESS   = "auth.2fa.success"
    TWO_FA_FAILED    = "auth.2fa.failed"
    DATA_CREATED     = "data.created"
    DATA_READ        = "data.read"
    DATA_DELETED     = "data.deleted"
    PERMISSION_DENIED = "security.permission_denied"
    RATE_LIMIT_HIT   = "security.rate_limit"


class AuditLogger:
    SENSITIVE_KEYS = {"password", "secret", "token", "api_key", "pin", "cvv"}
    JWT_PATTERN    = re.compile(r"eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+")

    def __init__(self):
        self.logger = logging.getLogger("audit")
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            handler.setFormatter(logging.Formatter("%(message)s"))
            self.logger.addHandler(handler)
        self.logger.setLevel(logging.INFO)
        self.logger.propagate = False

    def log(
        self,
        action:      AuditAction,
        user_id:     int | str | None,
        request:     Request | None = None,
        resource:    str | None = None,
        resource_id: str | None = None,
        details:     dict[str, Any] | None = None,
        success:     bool = True,
    ) -> None:
        event: dict[str, Any] = {
            "event_id":    str(uuid.uuid4())[:8],
            "timestamp":   datetime.now(timezone.utc).isoformat(),
            "action":      action.value,
            "user_id":     user_id,
            "success":     success,
        }
        if resource:
            event["resource"]    = resource
        if resource_id:
            event["resource_id"] = resource_id

        if request:
            event["ip"]     = self._get_ip(request)
            event["method"] = request.method
            event["path"]   = str(request.url.path)

        if details:
            event["details"] = self._sanitize(details)

        self.logger.info(f"[AUDIT] {json.dumps(event)}")

    def _get_ip(self, request: Request) -> str:
        fwd = request.headers.get("x-forwarded-for")
        return fwd.split(",")[0].strip() if fwd else (
            request.client.host if request.client else "unknown"
        )

    def _sanitize(self, data: dict) -> dict:
        sanitized = {}
        for k, v in data.items():
            if any(s in k.lower() for s in self.SENSITIVE_KEYS):
                sanitized[k] = "[REDACTED]"
            elif isinstance(v, str):
                # Remove JWT tokens from values
                sanitized[k] = self.JWT_PATTERN.sub("[REDACTED_TOKEN]", v)
            else:
                sanitized[k] = v
        return sanitized


audit = AuditLogger()


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 7: Security Headers Middleware
# ─────────────────────────────────────────────────────────────────────────────

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)

        response.headers["X-Content-Type-Options"]      = "nosniff"
        response.headers["X-Frame-Options"]             = "DENY"
        response.headers["Strict-Transport-Security"]   = "max-age=31536000; includeSubDomains"
        response.headers["Referrer-Policy"]             = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"]          = "geolocation=(), camera=(), microphone=()"
        response.headers["Cross-Origin-Opener-Policy"]  = "same-origin"
        response.headers.pop("server", None)

        # No cache for auth endpoints
        if any(p in request.url.path for p in ["/auth", "/login"]):
            response.headers["Cache-Control"] = "no-store"
            response.headers["Pragma"]        = "no-cache"

        return response


# ─────────────────────────────────────────────────────────────────────────────
# FastAPI App Setup
# ─────────────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="Security Practical",
    description="JWT, 2FA, RBAC, CSRF, Audit Logging demo",
    version="1.0.0",
)

app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─────────────────────────────────────────────────────────────────────────────
# Pydantic Models
# ─────────────────────────────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    email: str
    password: str


class LoginResponse(BaseModel):
    access_token:  str
    token_type:    str = "bearer"
    requires_2fa:  bool = False
    temp_token:    str | None = None


class TOTPSetupResponse(BaseModel):
    secret:   str
    qr_code:  str
    message:  str


class TOTPVerifyRequest(BaseModel):
    code: str


class TOTPLoginRequest(BaseModel):
    temp_token: str
    code: str


class UserResponse(BaseModel):
    id:    int
    email: str
    role:  str


# ─────────────────────────────────────────────────────────────────────────────
# ENDPOINTS
# ─────────────────────────────────────────────────────────────────────────────


# ── Section 1: Basic Login / Logout ──────────────────────────────────────────

@app.post("/auth/login", response_model=LoginResponse, tags=["1. JWT Auth"])
async def login(body: LoginRequest, request: Request):
    """
    Login with brute force protection.
    Identifier = email + IP (dual-factor lockout).
    """
    ip          = get_client_ip(request)
    identifier  = f"{body.email}:{ip}"

    # 1. Brute force check
    check_brute_force(identifier)

    # 2. Find user
    user = FAKE_USERS.get(body.email)
    dummy_hash = pwd_context.hash("dummy")   # Timing attack prevention

    if not user:
        # STILL verify password (timing attack prevention)
        pwd_context.verify(body.password, dummy_hash)
        record_failed_attempt(identifier)
        audit.log(AuditAction.LOGIN_FAILED, None, request,
                  details={"email": body.email, "reason": "user_not_found"}, success=False)
        raise HTTPException(401, "Invalid email or password")

    if not pwd_context.verify(body.password, user["hashed_password"]):
        record_failed_attempt(identifier)
        audit.log(AuditAction.LOGIN_FAILED, user["id"], request,
                  details={"email": body.email, "reason": "wrong_password"}, success=False)
        raise HTTPException(401, "Invalid email or password")

    # 3. Successful password — clear failed attempts
    clear_failed_attempts(identifier)

    # 4. Check if 2FA enabled
    if user.get("totp_enabled") and user.get("totp_secret"):
        temp_token = create_access_token(
            {"sub": str(user["id"]), "scope": "2fa_pending"},
            expires_minutes=5
        )
        TEMP_TOKENS[temp_token] = user["id"]
        audit.log(AuditAction.LOGIN_SUCCESS, user["id"], request,
                  details={"email": body.email, "2fa_required": True})
        return LoginResponse(
            access_token="",   # Empty — not fully logged in yet
            requires_2fa=True,
            temp_token=temp_token,
        )

    # 5. Issue access token
    access_token = create_access_token({"sub": str(user["id"]), "role": user["role"]})
    audit.log(AuditAction.LOGIN_SUCCESS, user["id"], request,
              details={"email": body.email})
    return LoginResponse(access_token=access_token)


@app.post("/auth/logout", tags=["1. JWT Auth"])
async def logout(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    current_user: dict = Depends(get_current_user),
    request: Request = None,
):
    """
    Logout — blacklist the token.
    INTERVIEW: Stateless JWT ko revoke karne ka yahi tarika hai.
    """
    token = credentials.credentials
    jti   = get_token_jti(token)
    if jti:
        TOKEN_BLACKLIST.add(jti)

    audit.log(AuditAction.LOGOUT, current_user["id"], request)
    return {"message": "Logged out successfully"}


@app.get("/auth/me", response_model=UserResponse, tags=["1. JWT Auth"])
async def me(current_user: dict = Depends(get_current_user)):
    """Get current user from JWT."""
    return UserResponse(
        id=current_user["id"],
        email=current_user["email"],
        role=current_user["role"],
    )


# ── Section 2: JWT Attack Demo ────────────────────────────────────────────────

@app.get("/demo/jwt-attacks", tags=["2. JWT Attack Demo"])
async def jwt_attacks_demo():
    """
    INTERVIEW DEMO: Show alg:none attack and fix.
    """
    import jwt as pyjwt   # raw PyJWT for demo

    # 1. Create a valid token
    payload = {"sub": "1", "role": "user", "exp": 9999999999}
    valid_token = pyjwt.encode(payload, settings.jwt_secret_key, algorithm="HS256")

    # 2. Craft alg:none attack token (no signature)
    import base64 as b64
    header  = b64.urlsafe_b64encode(b'{"alg":"none","typ":"JWT"}').rstrip(b"=").decode()
    body_   = b64.urlsafe_b64encode(
        json.dumps({"sub": "1", "role": "admin", "exp": 9999999999}).encode()
    ).rstrip(b"=").decode()
    attack_token = f"{header}.{body_}."

    # 3. Show what BAD code would do (accept alg:none)
    try:
        bad_result = pyjwt.decode(
            attack_token,
            settings.jwt_secret_key,
            algorithms=["HS256", "none"],   # ← VULNERABLE
            options={"verify_signature": False}
        )
        attack_success = True
        attack_payload = bad_result
    except Exception as e:
        attack_success = False
        attack_payload = str(e)

    # 4. Show what GOOD code does (reject alg:none)
    try:
        good_result = pyjwt.decode(
            attack_token,
            settings.jwt_secret_key,
            algorithms=["HS256"],   # ← SECURE: only HS256
        )
        fixed_success = False
    except Exception as e:
        fixed_success = True   # Attack BLOCKED

    return {
        "demo": "JWT alg:none attack",
        "valid_token_preview": valid_token[:50] + "...",
        "attack_token":        attack_token[:80] + "...",
        "bad_code_accepts_attack": attack_success,
        "good_code_blocks_attack": fixed_success,
        "lesson": "Always pass algorithms=['HS256'] — never omit or include 'none'",
    }


# ── Section 3: Brute Force Demo ───────────────────────────────────────────────

@app.post("/demo/brute-force-test", tags=["3. Brute Force"])
async def brute_force_test(body: LoginRequest, request: Request):
    """
    INTERVIEW DEMO: Try wrong password 5 times → locked out.
    Use email: 'brutetest@example.com', password: anything wrong
    """
    ip         = get_client_ip(request)
    identifier = f"{body.email}:{ip}"

    check_brute_force(identifier)

    attempts = ATTEMPT_STORE.get(f"attempts:{identifier}", 0)
    record_failed_attempt(identifier)

    return {
        "result":       "failed",
        "attempt":      attempts + 1,
        "max_attempts": MAX_ATTEMPTS,
        "warning":      f"Locked after {MAX_ATTEMPTS} failed attempts",
    }


@app.get("/demo/brute-force-status", tags=["3. Brute Force"])
async def brute_force_status(email: str, request: Request):
    """Check lockout status for an identifier."""
    ip         = get_client_ip(request)
    identifier = f"{email}:{ip}"
    lockout_key = f"lockout:{identifier}"
    attempts_key = f"attempts:{identifier}"

    locked_until = LOCKOUT_STORE.get(lockout_key)
    remaining = 0
    if locked_until:
        remaining = max(0, locked_until - datetime.now(timezone.utc).timestamp())

    return {
        "identifier":  identifier,
        "attempts":    ATTEMPT_STORE.get(attempts_key, 0),
        "is_locked":   remaining > 0,
        "locked_seconds_remaining": int(remaining),
    }


# ── Section 4: CSRF Demo ──────────────────────────────────────────────────────

@app.get("/csrf/token", tags=["4. CSRF"])
async def get_csrf_token(response: Response):
    """
    Step 1: Get CSRF token — sets it in cookie.
    Browser automatically sends cookie on subsequent requests.
    """
    session_id = secrets.token_urlsafe(16)
    csrf_token = set_csrf_cookie(response, session_id)

    # Also set session cookie
    response.set_cookie("session_id", session_id, httponly=True, samesite="strict")

    return {
        "message":    "CSRF token set in cookie",
        "csrf_token": csrf_token,   # Frontend includes this in X-CSRF-Token header
        "session_id": session_id,
        "usage":      "Include as header: X-CSRF-Token: <token>",
    }


@app.post("/csrf/protected-action", tags=["4. CSRF"])
async def csrf_protected_action(
    _csrf: None = Depends(require_csrf),
    body: dict = None,
):
    """
    Step 2: Protected endpoint — requires valid CSRF token.
    INTERVIEW: Double submit cookie pattern kaise kaam karta hai.
    """
    return {
        "message": "CSRF check passed!",
        "action":  "Sensitive state change executed",
        "body":    body,
    }


# ── Section 5: 2FA / TOTP ─────────────────────────────────────────────────────

@app.post("/auth/2fa/setup", response_model=TOTPSetupResponse, tags=["5. 2FA TOTP"])
async def setup_2fa(current_user: dict = Depends(get_current_user)):
    """
    Generate TOTP secret + QR code.
    User scans QR in Google Authenticator / Authy.
    """
    user_id = current_user["id"]

    # Generate new secret
    secret = generate_totp_secret()

    # Store pending (not yet confirmed)
    PENDING_TOTP[user_id] = secret

    # Generate QR code
    qr_b64 = generate_qr_code_base64(secret, current_user["email"])

    audit.log(AuditAction.TWO_FA_SETUP, user_id,
              details={"email": current_user["email"]})

    return TOTPSetupResponse(
        secret  = secret,
        qr_code = f"data:image/png;base64,{qr_b64}",
        message = "Scan QR code in authenticator app, then verify with /auth/2fa/verify-setup",
    )


@app.post("/auth/2fa/verify-setup", tags=["5. 2FA TOTP"])
async def verify_2fa_setup(
    body: TOTPVerifyRequest,
    current_user: dict = Depends(get_current_user),
):
    """
    Confirm 2FA setup by verifying a TOTP code from the app.
    """
    user_id = current_user["id"]
    pending_secret = PENDING_TOTP.get(user_id)

    if not pending_secret:
        raise HTTPException(400, "No pending 2FA setup. Call /auth/2fa/setup first.")

    if not verify_totp_code(pending_secret, body.code):
        audit.log(AuditAction.TWO_FA_FAILED, user_id,
                  details={"email": current_user["email"], "stage": "setup_verify"}, success=False)
        raise HTTPException(400, "Invalid TOTP code. Check your authenticator app.")

    # Enable 2FA for user
    FAKE_USERS[current_user["email"]]["totp_enabled"] = True
    FAKE_USERS[current_user["email"]]["totp_secret"]  = pending_secret
    del PENDING_TOTP[user_id]

    audit.log(AuditAction.TWO_FA_ENABLED, user_id,
              details={"email": current_user["email"]})

    return {"message": "2FA enabled successfully!"}


@app.post("/auth/2fa/login", tags=["5. 2FA TOTP"])
async def complete_2fa_login(body: TOTPLoginRequest, request: Request):
    """
    Complete login by providing TOTP code after password verification.
    """
    # Validate temp token
    try:
        payload = decode_token(body.temp_token)
    except HTTPException:
        raise HTTPException(401, "Invalid or expired temp token")

    if payload.get("scope") != "2fa_pending":
        raise HTTPException(401, "Invalid token scope")

    user_id = int(payload["sub"])

    # Find user
    user = None
    for u in FAKE_USERS.values():
        if u["id"] == user_id:
            user = u
            break

    if not user or not user.get("totp_secret"):
        raise HTTPException(401, "2FA not configured for this user")

    if not verify_totp_code(user["totp_secret"], body.code):
        audit.log(AuditAction.TWO_FA_FAILED, user_id, request,
                  details={"email": user["email"]}, success=False)
        raise HTTPException(401, "Invalid 2FA code")

    # Issue full access token
    access_token = create_access_token({"sub": str(user["id"]), "role": user["role"]})

    audit.log(AuditAction.TWO_FA_SUCCESS, user_id, request,
              details={"email": user["email"]})

    return {"access_token": access_token, "token_type": "bearer"}


# ── Section 6: RBAC Demo ──────────────────────────────────────────────────────

@app.get("/admin/dashboard", tags=["6. RBAC"])
async def admin_dashboard(
    current_user: dict = Depends(require_permission("admin:dashboard")),
    request: Request = None,
):
    """Requires 'admin:dashboard' permission (admin role only)."""
    audit.log(AuditAction.DATA_READ, current_user["id"], request,
              resource="admin_dashboard")
    return {
        "message":   "Welcome to Admin Dashboard",
        "user":      current_user["email"],
        "role":      current_user["role"],
        "data":      {"total_users": len(FAKE_USERS), "active_sessions": 42},
    }


@app.get("/users", tags=["6. RBAC"])
async def list_users(
    current_user: dict = Depends(require_permission("users:list")),
):
    """Requires 'users:list' permission (admin or moderator)."""
    return {
        "users": [
            {"id": u["id"], "email": u["email"], "role": u["role"]}
            for u in FAKE_USERS.values()
        ]
    }


@app.get("/posts", tags=["6. RBAC"])
async def list_posts(
    current_user: dict = Depends(require_permission("posts:read")),
):
    """Requires 'posts:read' (all roles)."""
    return {
        "posts": [
            {"id": 1, "title": "Hello World", "author": "alice@example.com"},
            {"id": 2, "title": "Security Basics", "author": "bob@example.com"},
        ],
        "reader": current_user["email"],
    }


# ── Section 7: Input Validation (OWASP A03) ───────────────────────────────────

class CreatePostRequest(BaseModel):
    title:   str
    content: str
    tags:    list[str] = []

    @field_validator("title")
    @classmethod
    def validate_title(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 3:
            raise ValueError("Title must be at least 3 characters")
        if len(v) > 200:
            raise ValueError("Title too long (max 200)")
        # Allow letters, numbers, spaces, basic punctuation only
        if re.search(r'[<>"\';`]', v):
            raise ValueError("Title contains invalid characters")
        return v

    @field_validator("content")
    @classmethod
    def sanitize_content(cls, v: str) -> str:
        # Strip HTML tags (simple version — use bleach in production)
        v = re.sub(r'<[^>]+>', '', v)
        if len(v) > 10000:
            raise ValueError("Content too long (max 10000)")
        return v.strip()

    @field_validator("tags")
    @classmethod
    def validate_tags(cls, v: list[str]) -> list[str]:
        if len(v) > 10:
            raise ValueError("Max 10 tags allowed")
        return [tag.lower().strip()[:50] for tag in v if tag.strip()]


@app.post("/posts", tags=["7. Input Validation"])
async def create_post(
    body: CreatePostRequest,
    current_user: dict = Depends(require_permission("posts:create")),
    request: Request = None,
):
    """
    Input validated post creation.
    Pydantic validators: strip HTML, validate lengths, reject special chars.
    """
    # Safe: parameterized query would be used in real DB (no f-string SQL!)
    # BAD: f"INSERT INTO posts WHERE title='{body.title}'"
    # GOOD: session.execute(text("INSERT INTO posts ..."), {"title": body.title})

    audit.log(
        AuditAction.DATA_CREATED,
        current_user["id"],
        request,
        resource="post",
        details={"title": body.title, "tags": body.tags},
    )

    return {
        "message":  "Post created",
        "title":    body.title,
        "content":  body.content[:100] + "..." if len(body.content) > 100 else body.content,
        "tags":     body.tags,
        "author":   current_user["email"],
    }


# ── Section 8: Security Health Check ─────────────────────────────────────────

@app.get("/security/config-check", tags=["8. Security Check"])
async def security_config_check():
    """
    Quick security configuration audit.
    INTERVIEW: What to check before deploying.
    """
    checks = {
        "jwt_secret_strong":     len(settings.jwt_secret_key) >= 32,
        "debug_disabled":        not settings.debug,
        "algorithm_not_none":    settings.jwt_algorithm != "none",
        "algorithm_is_hmac_or_rsa": settings.jwt_algorithm in ("HS256", "RS256", "ES256"),
        "short_access_token_expiry": settings.access_token_expiry_minutes <= 60,
    }
    score   = sum(checks.values())
    total   = len(checks)
    rating  = "✅ Secure" if score == total else f"⚠️  {total - score} issues found"

    return {
        "rating":     rating,
        "score":      f"{score}/{total}",
        "checks":     checks,
        "algorithm":  settings.jwt_algorithm,
        "token_expiry_minutes": settings.access_token_expiry_minutes,
    }


# ─────────────────────────────────────────────────────────────────────────────
# DEMO / TEST CLIENT
# ─────────────────────────────────────────────────────────────────────────────

async def run_tests():
    """
    Demonstration client — runs through all security features.
    """
    from httpx import AsyncClient

    base = "http://localhost:8000"
    print("\n" + "="*60)
    print("SECURITY PRACTICAL — TEST DEMO")
    print("="*60)

    async with AsyncClient(base_url=base) as client:

        # ── Test 1: Security config check ──
        print("\n[1] Security Config Check")
        r = await client.get("/security/config-check")
        data = r.json()
        print(f"   Rating: {data['rating']}")
        print(f"   Score:  {data['score']}")

        # ── Test 2: Login ──
        print("\n[2] Login — alice@example.com")
        r = await client.post("/auth/login",
                              json={"email": "alice@example.com", "password": "Password123!"})
        print(f"   Status: {r.status_code}")
        login_data = r.json()
        alice_token = login_data.get("access_token", "")
        print(f"   Token: {alice_token[:30]}...")
        headers = {"Authorization": f"Bearer {alice_token}"}

        # ── Test 3: Get current user ──
        print("\n[3] GET /auth/me")
        r = await client.get("/auth/me", headers=headers)
        print(f"   Status: {r.status_code}")
        print(f"   User:   {r.json()}")

        # ── Test 4: JWT attacks demo ──
        print("\n[4] JWT alg:none Attack Demo")
        r = await client.get("/demo/jwt-attacks")
        d = r.json()
        print(f"   Attack succeeds on bad code: {d['bad_code_accepts_attack']}")
        print(f"   Good code blocks attack:     {d['good_code_blocks_attack']}")
        print(f"   Lesson: {d['lesson']}")

        # ── Test 5: Brute force demo ──
        print("\n[5] Brute Force — 3 failed attempts")
        for i in range(3):
            r = await client.post("/demo/brute-force-test",
                                  json={"email": "brutetest@example.com",
                                        "password": "wrongpassword"})
            print(f"   Attempt {i+1}: {r.status_code} — {r.json()}")
            if r.status_code == 429:
                print("   → LOCKED OUT!")
                break

        # ── Test 6: RBAC — admin tries admin dashboard ──
        print("\n[6a] RBAC — Admin accesses admin dashboard")
        r = await client.get("/admin/dashboard", headers=headers)
        print(f"   Status: {r.status_code} (admin should get 200)")

        # Login as bob (user role)
        r = await client.post("/auth/login",
                              json={"email": "bob@example.com", "password": "SecurePass456!"})
        bob_token = r.json().get("access_token", "")
        bob_headers = {"Authorization": f"Bearer {bob_token}"}

        print("\n[6b] RBAC — User (bob) tries admin dashboard")
        r = await client.get("/admin/dashboard", headers=bob_headers)
        print(f"   Status: {r.status_code} (user should get 403)")
        if r.status_code == 403:
            print(f"   Detail: {r.json()['detail']}")

        # ── Test 7: CSRF demo ──
        print("\n[7] CSRF Protection")
        r = await client.get("/csrf/token")
        csrf_data = r.json()
        csrf_token = csrf_data["csrf_token"]
        print(f"   Got CSRF token: {csrf_token[:20]}...")

        # Request WITH correct CSRF token
        r = await client.post(
            "/csrf/protected-action",
            json={"action": "transfer_funds"},
            headers={
                "X-CSRF-Token": csrf_token,
                "Cookie": f"csrf_token={csrf_token}",
            }
        )
        print(f"   With CSRF token: {r.status_code} (should be 200)")

        # Request WITHOUT CSRF token (CSRF attack scenario)
        r = await client.post(
            "/csrf/protected-action",
            json={"action": "transfer_funds"},
        )
        print(f"   Without CSRF token: {r.status_code} (should be 403)")

        # ── Test 8: Input validation ──
        print("\n[8] Input Validation")
        r = await client.post("/posts",
                              json={"title": "<script>alert('xss')</script>",
                                    "content": "Hello World", "tags": []},
                              headers=headers)
        print(f"   XSS in title: {r.status_code} (should be 422)")

        r = await client.post("/posts",
                              json={"title": "Safe Post Title",
                                    "content": "<b>Bold</b> text here", "tags": ["python"]},
                              headers=headers)
        print(f"   Valid post: {r.status_code}")
        if r.status_code == 200:
            print(f"   HTML stripped: '{r.json()['content']}'")  # Should be without <b>

        # ── Test 9: Logout (token blacklist) ──
        print("\n[9] Logout (Token Blacklist)")
        r = await client.post("/auth/logout", headers=headers)
        print(f"   Logout: {r.status_code} — {r.json()}")

        # Try using blacklisted token
        r = await client.get("/auth/me", headers=headers)
        print(f"   Reuse blacklisted token: {r.status_code} (should be 401)")

        # ── Test 10: TOTP Setup (manual verification needed) ──
        print("\n[10] 2FA Setup")
        # Login fresh token
        r = await client.post("/auth/login",
                              json={"email": "alice@example.com", "password": "Password123!"})
        fresh_headers = {"Authorization": f"Bearer {r.json()['access_token']}"}

        r = await client.post("/auth/2fa/setup", headers=fresh_headers)
        print(f"   Setup: {r.status_code}")
        if r.status_code == 200:
            setup = r.json()
            print(f"   Secret: {setup['secret']}")
            print(f"   QR Code: data:image/png;base64,...[{len(setup['qr_code'])} chars]")
            print(f"   Message: {setup['message']}")

            # Demo manual verification (code changes every 30 seconds)
            totp = pyotp.TOTP(setup["secret"])
            current_code = totp.now()
            print(f"\n   Current TOTP code (demo): {current_code}")

            r = await client.post(
                "/auth/2fa/verify-setup",
                json={"code": current_code},
                headers=fresh_headers,
            )
            print(f"   Verify setup: {r.status_code} — {r.json()}")

    print("\n" + "="*60)
    print("DEMO COMPLETE")
    print("="*60)


if __name__ == "__main__":
    import uvicorn
    import threading

    def run_server():
        uvicorn.run(app, host="0.0.0.0", port=8000, log_level="warning")

    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()

    import time
    time.sleep(1.5)

    asyncio.run(run_tests())
