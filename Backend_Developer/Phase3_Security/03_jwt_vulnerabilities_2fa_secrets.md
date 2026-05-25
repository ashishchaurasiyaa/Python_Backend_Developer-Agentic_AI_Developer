# JWT Vulnerabilities, 2FA/TOTP, Secrets Management & Audit Logging

---

# PART 1: JWT Security Vulnerabilities

## What are JWT Vulnerabilities?
- JWT (JSON Web Token) widely use hota hai auth mein — **but galat implementation = critical security holes**
- 5 major attack categories hain jo interviews mein frequently pooche jaate hain
- **Goal**: Attacks samjho + Python/FastAPI mein fix karo

---

## Vulnerability 1: Algorithm Confusion (alg:none Attack)

### What & Why it's Dangerous
```
JWT header: { "alg": "HS256", "typ": "JWT" }

Attack: Attacker header change karta hai:
{ "alg": "none", "typ": "JWT" }

Agar server "none" algorithm accept kare →
signature verify hi nahi hoti → attacker koi bhi payload bana sakta hai!

"none" algorithm = no signature = trust karna WRONG hai
```

### How to Fix
```python
import jwt  # PyJWT
from fastapi import HTTPException

# BAD: Algorithm not verified
def decode_token_bad(token: str) -> dict:
    # algorithms parameter missing → alg:none attack possible!
    return jwt.decode(token, SECRET_KEY, options={"verify_signature": False})


# GOOD: Explicit algorithm allowlist
SECRET_KEY = "super-secret-key-min-32-chars-long"
ALGORITHM  = "HS256"

def decode_token_safe(token: str) -> dict:
    try:
        payload = jwt.decode(
            token,
            SECRET_KEY,
            algorithms=["HS256"],          # ✓ Explicit allowlist — never ["none"]
            options={"require": ["exp", "iat", "sub"]},  # Required claims
        )
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "Token expired")
    except jwt.InvalidAlgorithmError:
        raise HTTPException(401, "Invalid algorithm")
    except jwt.InvalidTokenError:
        raise HTTPException(401, "Invalid token")


# INTERVIEW: RS256 vs HS256
# HS256 = HMAC + SHA256 (shared secret) → monolithic apps
# RS256 = RSA signature (private key sign, public key verify)
#       → microservices (each service has public key only)
#       → Algorithm confusion attack harder (private key secret)

# RS256 setup:
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

# Generate key pair (do once, store securely)
private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
public_key  = private_key.public_key()

# Sign with private key (auth server only)
token = jwt.encode({"sub": "user123", "exp": ...}, private_key, algorithm="RS256")

# Verify with public key (any service)
payload = jwt.decode(token, public_key, algorithms=["RS256"])
```

---

## Vulnerability 2: Weak Secret Brute Force

### What & Why
```
HS256 secret = password for HMAC
Weak secret = "secret", "password", "jwt_secret" → brute-forceable!

Tool: hashcat -a 0 -m 16500 token.txt wordlist.txt
      jwt_tool -t eyJ... -C -d rockyou.txt

If secret cracked → attacker forges ANY token with ANY user ID
```

### How to Fix
```python
import secrets
import os

# BAD secrets:
SECRET_KEY = "secret"           # ← brute-forceable
SECRET_KEY = "mysecretkey"      # ← in wordlist
SECRET_KEY = "jwt_secret_key"   # ← predictable

# GOOD: Cryptographically random, min 32 bytes (256 bits)
SECRET_KEY = secrets.token_hex(32)   # Generate once, store in env
# Example: "a3f8c2e1d4b7a6f9e8d3c2b1a0f9e8d7c6b5a4f3e2d1c0b9a8f7e6d5c4b3a2"

# In production: Load from environment variable
SECRET_KEY = os.getenv("JWT_SECRET_KEY")
if not SECRET_KEY or len(SECRET_KEY) < 32:
    raise RuntimeError("JWT_SECRET_KEY must be set and at least 32 chars")


# ─── Key Rotation ───
# Problem: Secret leaked → ALL tokens invalid karne padte hain
# Solution: Secret versioning

SECRETS = {
    "v2": os.getenv("JWT_SECRET_V2"),  # Current
    "v1": os.getenv("JWT_SECRET_V1"),  # Previous (for grace period)
}

def create_token(payload: dict) -> str:
    payload["kid"] = "v2"              # Key ID in token header
    return jwt.encode(payload, SECRETS["v2"], algorithm="HS256",
                      headers={"kid": "v2"})

def decode_token_with_rotation(token: str) -> dict:
    header = jwt.get_unverified_header(token)
    kid    = header.get("kid", "v2")

    if kid not in SECRETS:
        raise HTTPException(401, "Unknown key version")

    return jwt.decode(token, SECRETS[kid], algorithms=["HS256"])
```

---

## Vulnerability 3: Token Leakage

### What & Why
```
JWT tokens leak through:
1. URL query params → server logs mein forever: GET /api?token=eyJ...
2. Referer header → next site ko token mila
3. console.log(token) → frontend logs mein
4. Error responses → stack trace mein token printed
5. localStorage → XSS se accessible

Access log line:
2024-01-15 GET /api/data?token=eyJhbGciOiJIUzI1NiJ9... 200
→ Anyone with log access has the token!
```

### How to Fix
```python
from fastapi import Request, Header
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

# BAD: Token in URL
# GET /api/users?token=eyJ...
@app.get("/users")
async def get_users_bad(token: str = Query(None)):
    pass  # NEVER do this


# GOOD: Token in Authorization header only
security = HTTPBearer()

@app.get("/users")
async def get_users_good(
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    token = credentials.credentials  # From "Authorization: Bearer eyJ..."
    payload = decode_token_safe(token)
    ...


# ─── Logging: NEVER log tokens ───
import logging
import re

class TokenSanitizer(logging.Filter):
    """Remove JWT tokens from log messages."""
    JWT_PATTERN = re.compile(r'eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+')

    def filter(self, record):
        if isinstance(record.msg, str):
            record.msg = self.JWT_PATTERN.sub("[REDACTED_TOKEN]", record.msg)
        return True

# Apply to all loggers
logging.getLogger().addFilter(TokenSanitizer())


# ─── Storage: httpOnly cookie > localStorage ───
from fastapi.responses import JSONResponse

@app.post("/login")
async def login(response: JSONResponse, ...):
    token = create_access_token({"sub": user.id})
    response = JSONResponse({"message": "Login successful"})

    # httpOnly = JS cannot read it → XSS safe
    # Secure = HTTPS only
    # SameSite = CSRF protection
    response.set_cookie(
        key="access_token",
        value=f"Bearer {token}",
        httponly=True,          # ← XSS cannot steal
        secure=True,            # ← HTTPS only
        samesite="lax",         # ← CSRF protection
        max_age=900,            # 15 minutes
        path="/",
    )
    return response
```

---

## Vulnerability 4: JWT Token Blacklisting

### What & Why
```
Problem: JWT is STATELESS — logout karne ke baad bhi token valid hota hai!
User logout kare → token delete from browser
But agar koi ne token copy kar liya → woh still valid!

Solution: Blacklist (revocation list)
Logout pe token ko Redis mein store karo until its expiry
```

### How to Fix
```python
import redis.asyncio as aioredis
from datetime import datetime, timezone

redis_client = aioredis.from_url("redis://localhost:6379")

async def blacklist_token(token: str, exp: int) -> None:
    """Add token to blacklist until its natural expiry."""
    jti = get_token_jti(token)           # JWT ID (unique per token)
    ttl = exp - int(datetime.now(timezone.utc).timestamp())
    if ttl > 0:
        await redis_client.setex(f"blacklist:{jti}", ttl, "1")


async def is_token_blacklisted(token: str) -> bool:
    jti = get_token_jti(token)
    return await redis_client.exists(f"blacklist:{jti}") == 1


def get_token_jti(token: str) -> str:
    """Extract JTI claim from token without full verification."""
    payload = jwt.decode(token, options={"verify_signature": False})
    return payload.get("jti", token[:50])   # fallback to token prefix


# ─── Token creation with JTI ───
import uuid

def create_access_token(data: dict, expires_minutes: int = 15) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=expires_minutes)
    payload = {
        **data,
        "exp": expire,
        "iat": datetime.now(timezone.utc),
        "jti": str(uuid.uuid4()),   # ← Unique JWT ID
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


# ─── Dependency with blacklist check ───
async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> dict:
    token = credentials.credentials

    if await is_token_blacklisted(token):
        raise HTTPException(401, "Token has been revoked")

    return decode_token_safe(token)


# ─── Logout endpoint ───
@app.post("/auth/logout")
async def logout(
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    token   = credentials.credentials
    payload = decode_token_safe(token)
    await blacklist_token(token, payload["exp"])
    return {"message": "Logged out successfully"}
```

---

## Vulnerability 5: Token Expiry & Refresh Token Security

### What & Why
```
Access Token:  Short-lived (15 min) → minimize damage if leaked
Refresh Token: Long-lived (7 days)  → get new access token

Refresh Token vulnerabilities:
1. Stored in localStorage → XSS steal kar sakta hai
2. No rotation → one theft = forever access
3. No family tracking → replay attacks
```

### How to Fix — Refresh Token Rotation
```python
from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey

class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id         = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id    = Column(Integer, ForeignKey("users.id"))
    token_hash = Column(String, unique=True)   # Store hash only, not raw token
    family     = Column(String)                # Family ID for rotation detection
    is_revoked = Column(Boolean, default=False)
    expires_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), default=func.now())


import hashlib

def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


async def create_refresh_token(user_id: int, family: str = None) -> str:
    raw_token = secrets.token_urlsafe(32)
    family    = family or str(uuid.uuid4())

    db_token = RefreshToken(
        user_id    = user_id,
        token_hash = hash_token(raw_token),
        family     = family,
        expires_at = datetime.now(timezone.utc) + timedelta(days=7),
    )
    session.add(db_token)
    await session.commit()
    return raw_token   # Return raw (show once, never stored)


async def rotate_refresh_token(old_raw_token: str) -> tuple[str, str]:
    """Rotate refresh token — detect replay attacks via family."""
    token_hash = hash_token(old_raw_token)
    old_token  = await session.execute(
        select(RefreshToken)
        .where(RefreshToken.token_hash == token_hash)
    )
    old_token = old_token.scalar_one_or_none()

    if not old_token:
        raise HTTPException(401, "Invalid refresh token")

    # ─── Replay attack detection ───
    if old_token.is_revoked:
        # Someone used an already-rotated token → FULL family revocation!
        await session.execute(
            update(RefreshToken)
            .where(RefreshToken.family == old_token.family)
            .values(is_revoked=True)
        )
        await session.commit()
        raise HTTPException(401, "Token reuse detected — please login again")

    if old_token.expires_at < datetime.now(timezone.utc):
        raise HTTPException(401, "Refresh token expired")

    # Revoke old token
    old_token.is_revoked = True

    # Issue new token in same family
    new_raw = await create_refresh_token(old_token.user_id, family=old_token.family)
    new_access = create_access_token({"sub": str(old_token.user_id)})

    return new_access, new_raw
```

---

# PART 2: Two-Factor Authentication (2FA / TOTP)

## What is TOTP?
```
TOTP = Time-based One-Time Password (RFC 6238)
- Google Authenticator, Authy, Microsoft Authenticator use karte hain
- Shared secret + current time → 6-digit code (changes every 30 seconds)
- HMAC-SHA1(secret, floor(time/30))

Flow:
1. User enables 2FA → server generates secret
2. Secret shown as QR code → user scans in authenticator app
3. Login: password ✓ → then ask for 6-digit TOTP code
4. Server verifies code with same secret + current time window
```

### How to Implement TOTP
```python
# pip install pyotp qrcode[pil]

import pyotp
import qrcode
import io
import base64

# ─── Setup: Generate secret for user ───
def generate_totp_secret() -> str:
    return pyotp.random_base32()   # 32-char base32 secret

# ─── Generate QR code for authenticator app ───
def generate_qr_code(secret: str, email: str, issuer: str = "MyApp") -> str:
    """Returns base64-encoded PNG of QR code."""
    totp     = pyotp.TOTP(secret)
    uri      = totp.provisioning_uri(name=email, issuer_name=issuer)
    # URI format: otpauth://totp/MyApp:user@example.com?secret=BASE32SECRET&issuer=MyApp

    img = qrcode.make(uri)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


# ─── Verify TOTP code ───
def verify_totp(secret: str, code: str) -> bool:
    """
    valid_window=1 → accept 1 period before/after current
    Handles clock skew between server and user's phone
    """
    totp = pyotp.TOTP(secret)
    return totp.verify(code, valid_window=1)


# ─── FastAPI endpoints ───
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

router = APIRouter(prefix="/auth/2fa", tags=["2FA"])


class TOTPSetupResponse(BaseModel):
    secret:   str    # User backs this up
    qr_code:  str    # Base64 PNG
    backup_codes: list[str]


@router.post("/setup", response_model=TOTPSetupResponse)
async def setup_2fa(current_user = Depends(get_current_user)):
    """Step 1: Generate secret + QR code for user."""
    if current_user.totp_enabled:
        raise HTTPException(400, "2FA already enabled")

    secret = generate_totp_secret()

    # Store secret temporarily (not enabled until verified)
    await redis_client.setex(
        f"totp:pending:{current_user.id}",
        600,          # 10 min to complete setup
        secret
    )

    backup_codes = [secrets.token_hex(4).upper() for _ in range(10)]
    # Store hashed backup codes in DB
    hashed_backups = [hash_token(code) for code in backup_codes]
    await save_backup_codes(current_user.id, hashed_backups)

    return TOTPSetupResponse(
        secret   = secret,
        qr_code  = generate_qr_code(secret, current_user.email),
        backup_codes = backup_codes,   # Show ONCE, user saves them
    )


class TOTPVerifyRequest(BaseModel):
    code: str   # 6-digit code from authenticator


@router.post("/verify-setup")
async def verify_2fa_setup(
    body: TOTPVerifyRequest,
    current_user = Depends(get_current_user),
):
    """Step 2: Confirm user scanned QR by verifying a code."""
    pending_secret = await redis_client.get(f"totp:pending:{current_user.id}")
    if not pending_secret:
        raise HTTPException(400, "No pending 2FA setup (expired or not started)")

    secret = pending_secret.decode()
    if not verify_totp(secret, body.code):
        raise HTTPException(400, "Invalid TOTP code")

    # Now officially enable 2FA
    await db_update_user(current_user.id, totp_secret=secret, totp_enabled=True)
    await redis_client.delete(f"totp:pending:{current_user.id}")

    return {"message": "2FA enabled successfully"}


# ─── Login flow with 2FA ───
class LoginRequest(BaseModel):
    email: str
    password: str


class LoginResponse(BaseModel):
    requires_2fa: bool
    temp_token: str | None     # Valid 5 min — only for TOTP step
    access_token: str | None
    refresh_token: str | None


@router.post("/login", response_model=LoginResponse)
async def login_with_2fa(body: LoginRequest):
    user = await authenticate_user(body.email, body.password)
    if not user:
        raise HTTPException(401, "Invalid credentials")

    if user.totp_enabled:
        # Issue short-lived temp token for the 2FA step
        temp_token = create_access_token(
            {"sub": str(user.id), "scope": "2fa_pending"},
            expires_minutes=5
        )
        return LoginResponse(requires_2fa=True, temp_token=temp_token,
                             access_token=None, refresh_token=None)

    access  = create_access_token({"sub": str(user.id)})
    refresh = await create_refresh_token(user.id)
    return LoginResponse(requires_2fa=False, access_token=access,
                         refresh_token=refresh, temp_token=None)


class TOTPLoginRequest(BaseModel):
    temp_token: str
    code: str


@router.post("/login/2fa")
async def complete_2fa_login(body: TOTPLoginRequest):
    """Complete login by verifying TOTP code."""
    try:
        payload = decode_token_safe(body.temp_token)
    except HTTPException:
        raise HTTPException(401, "Invalid or expired temp token")

    if payload.get("scope") != "2fa_pending":
        raise HTTPException(401, "Invalid token scope")

    user_id = int(payload["sub"])
    user    = await get_user_by_id(user_id)

    # Check TOTP code
    if verify_totp(user.totp_secret, body.code):
        access  = create_access_token({"sub": str(user.id)})
        refresh = await create_refresh_token(user.id)
        return {"access_token": access, "refresh_token": refresh}

    # Check backup codes
    code_hash = hash_token(body.code.upper())
    if await use_backup_code(user_id, code_hash):
        access  = create_access_token({"sub": str(user.id)})
        refresh = await create_refresh_token(user.id)
        return {"access_token": access, "refresh_token": refresh,
                "warning": "Backup code used — please generate new ones"}

    raise HTTPException(401, "Invalid 2FA code")
```

---

# PART 3: Secrets Management

## What & Why
```
Secrets = API keys, DB passwords, JWT secrets, encryption keys
Problem:
  ✗ Hardcoded in code → version control mein
  ✗ .env file → committed by mistake, logged
  ✗ Environment variables → process listing mein visible

Solution: Dedicated secrets management
  ✓ HashiCorp Vault (self-hosted)
  ✓ AWS Secrets Manager (cloud)
  ✓ GCP Secret Manager
  ✓ Azure Key Vault
  ✓ Doppler, 1Password Secrets Automation
```

### How to Use HashiCorp Vault
```python
# pip install hvac

import hvac
import os

class VaultSecretsManager:
    """
    Production secrets ko Vault se load karo.
    Dynamic secrets: DB credentials jo automatically rotate hote hain.
    """

    def __init__(self):
        self.client = hvac.Client(
            url   = os.environ["VAULT_ADDR"],        # e.g., https://vault.company.com
            token = os.environ["VAULT_TOKEN"],        # App Role token (not root!)
        )
        if not self.client.is_authenticated():
            raise RuntimeError("Vault authentication failed")

    def get_secret(self, path: str, key: str) -> str:
        """Read secret from Vault KV v2."""
        response = self.client.secrets.kv.v2.read_secret_version(
            path=path,
            mount_point="secret",
        )
        return response["data"]["data"][key]

    def get_db_credentials(self) -> dict:
        """Dynamic DB credentials (auto-rotated by Vault)."""
        response = self.client.secrets.database.generate_credentials(
            name="my-postgres-role"
        )
        return {
            "username": response["data"]["username"],
            "password": response["data"]["password"],
            "lease_id": response["lease_id"],         # Track for renewal
        }

    def renew_lease(self, lease_id: str, increment: int = 3600) -> None:
        """Renew dynamic credential lease before it expires."""
        self.client.sys.renew_lease(lease_id=lease_id, increment=increment)


# ─── AWS Secrets Manager ───
import boto3
import json

def get_aws_secret(secret_name: str, region: str = "us-east-1") -> dict:
    """Load secrets from AWS Secrets Manager."""
    client = boto3.client("secretsmanager", region_name=region)

    response = client.get_secret_value(SecretId=secret_name)

    if "SecretString" in response:
        return json.loads(response["SecretString"])
    else:
        # Binary secret
        return json.loads(response["SecretBinary"].decode("utf-8"))


# Usage:
# secrets = get_aws_secret("prod/myapp/database")
# DB_PASSWORD = secrets["password"]


# ─── Secret Rotation Pattern ───
class SecretRotationManager:
    """
    Zero-downtime secret rotation:
    1. Generate new secret
    2. Update app to accept BOTH old + new (dual-read phase)
    3. Rotate all tokens to use new secret
    4. Remove old secret
    """

    def __init__(self):
        self._secrets: dict[str, str] = {}
        self._current_version: str = "v1"

    async def rotate_jwt_secret(self) -> None:
        new_version = f"v{int(self._current_version[1:]) + 1}"
        new_secret  = secrets.token_hex(32)

        # Phase 1: Add new secret (dual-accept)
        self._secrets[new_version] = new_secret
        self._current_version      = new_version

        # Phase 2: Old version remains for grace period (e.g., 15 min)
        await asyncio.sleep(15 * 60)

        # Phase 3: Remove old version
        old_versions = [v for v in self._secrets if v != new_version]
        for v in old_versions:
            del self._secrets[v]

    def get_current_secret(self) -> tuple[str, str]:
        return self._current_version, self._secrets[self._current_version]

    def get_all_secrets(self) -> dict[str, str]:
        return self._secrets.copy()   # For token verification
```

### Environment Variable Best Practices
```python
# ─── pydantic-settings: Type-safe config from env ───
# pip install pydantic-settings

from pydantic_settings import BaseSettings
from pydantic import SecretStr, field_validator

class Settings(BaseSettings):
    # SecretStr = stored as secret, not shown in repr/logs
    jwt_secret_key:  SecretStr
    db_password:     SecretStr
    redis_password:  SecretStr | None = None

    # Regular settings
    debug:           bool = False
    environment:     str  = "production"
    jwt_algorithm:   str  = "HS256"
    access_token_expiry_minutes: int = 15

    @field_validator("jwt_secret_key")
    @classmethod
    def validate_secret_strength(cls, v: SecretStr) -> SecretStr:
        if len(v.get_secret_value()) < 32:
            raise ValueError("JWT secret must be at least 32 characters")
        return v

    @field_validator("environment")
    @classmethod
    def validate_env(cls, v: str) -> str:
        if v not in ("development", "staging", "production"):
            raise ValueError(f"Invalid environment: {v}")
        return v

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": False,
    }


settings = Settings()

# Usage — never logs the actual value:
# repr(settings.jwt_secret_key) → SecretStr('**********')
raw_secret = settings.jwt_secret_key.get_secret_value()   # Explicit extraction


# ─── .env file — NEVER commit to git ───
# .env (not in git)
"""
JWT_SECRET_KEY=a3f8c2e1d4b7a6f9e8d3c2b1a0f9e8d7c6b5a4f3e2d1c0b9a8f7e6d5c4b3a2
DB_PASSWORD=super_secure_db_password_here
REDIS_PASSWORD=redis_password_here
DEBUG=false
ENVIRONMENT=production
"""

# .gitignore (always include these):
"""
.env
.env.local
.env.production
*.key
*.pem
secrets/
"""
```

---

# PART 4: Audit Logging

## What & Why
```
Audit Log = WHO did WHAT, WHEN, from WHERE
Required for:
  ✓ Security incident investigation ("who deleted this record?")
  ✓ Compliance (SOC2, GDPR, HIPAA, PCI-DSS)
  ✓ Debugging production issues
  ✓ Forensic analysis after breach

What to log:
  ✓ Authentication events (login/logout/failed/2FA)
  ✓ Authorization failures (403)
  ✓ Data access (read sensitive data)
  ✓ Data mutation (create/update/delete)
  ✓ Admin actions
  ✓ API key usage

What NOT to log:
  ✗ Passwords (even hashed)
  ✗ JWT tokens / API keys (full value)
  ✗ Credit card numbers, SSNs
  ✗ Personal health information (PHI)
```

### How to Implement Structured Audit Logging
```python
import logging
import json
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from fastapi import Request

class AuditAction(str, Enum):
    # Auth events
    LOGIN_SUCCESS    = "auth.login.success"
    LOGIN_FAILED     = "auth.login.failed"
    LOGIN_LOCKED     = "auth.login.locked"
    LOGOUT           = "auth.logout"
    TOKEN_REFRESHED  = "auth.token.refreshed"
    TOKEN_REVOKED    = "auth.token.revoked"
    TWO_FA_ENABLED   = "auth.2fa.enabled"
    TWO_FA_SUCCESS   = "auth.2fa.success"
    TWO_FA_FAILED    = "auth.2fa.failed"
    PASSWORD_CHANGED = "auth.password.changed"

    # Data events
    DATA_READ        = "data.read"
    DATA_CREATED     = "data.created"
    DATA_UPDATED     = "data.updated"
    DATA_DELETED     = "data.deleted"

    # Admin events
    ROLE_ASSIGNED    = "admin.role.assigned"
    USER_SUSPENDED   = "admin.user.suspended"
    CONFIG_CHANGED   = "admin.config.changed"

    # Security events
    PERMISSION_DENIED = "security.permission.denied"
    SUSPICIOUS_ACTIVITY = "security.suspicious"
    RATE_LIMIT_HIT   = "security.rate_limit"


class AuditLogger:
    """
    Structured JSON audit logger.
    Writes to separate audit log file AND database.
    """

    def __init__(self):
        self.logger = logging.getLogger("audit")
        handler = logging.FileHandler("/var/log/app/audit.log")
        handler.setFormatter(logging.Formatter("%(message)s"))  # Raw JSON
        self.logger.addHandler(handler)
        self.logger.setLevel(logging.INFO)
        self.logger.propagate = False   # Don't send to root logger


    def log(
        self,
        action:     AuditAction,
        user_id:    int | str | None,
        request:    Request | None = None,
        resource:   str | None = None,
        resource_id: str | None = None,
        details:    dict[str, Any] | None = None,
        success:    bool = True,
    ) -> None:
        event = {
            "event_id":   str(uuid.uuid4()),
            "timestamp":  datetime.now(timezone.utc).isoformat(),
            "action":     action.value,
            "user_id":    user_id,
            "success":    success,
            "resource":   resource,
            "resource_id": resource_id,
        }

        if request:
            event.update({
                "ip":         self._get_client_ip(request),
                "user_agent": request.headers.get("user-agent", "")[:200],
                "method":     request.method,
                "path":       str(request.url.path),
                "request_id": request.headers.get("x-request-id", ""),
            })

        if details:
            # Sanitize sensitive fields before logging
            sanitized = self._sanitize(details)
            event["details"] = sanitized

        self.logger.info(json.dumps(event))

        # Also write to DB for querying (async background task in real app)
        # asyncio.create_task(self._persist_to_db(event))


    def _get_client_ip(self, request: Request) -> str:
        """Get real IP behind proxy."""
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return request.client.host if request.client else "unknown"


    def _sanitize(self, data: dict) -> dict:
        """Remove/mask sensitive fields from log data."""
        SENSITIVE_KEYS = {
            "password", "secret", "token", "api_key", "credit_card",
            "ssn", "cvv", "pin", "private_key", "access_token"
        }
        sanitized = {}
        for k, v in data.items():
            if any(sensitive in k.lower() for sensitive in SENSITIVE_KEYS):
                sanitized[k] = "[REDACTED]"
            elif isinstance(v, str) and len(v) > 500:
                sanitized[k] = v[:200] + "...[TRUNCATED]"
            else:
                sanitized[k] = v
        return sanitized


audit = AuditLogger()


# ─── Usage in endpoints ───
@app.post("/auth/login")
async def login(request: Request, body: LoginRequest):
    user = await get_user_by_email(body.email)

    if not user or not verify_password(body.password, user.hashed_password):
        audit.log(
            action    = AuditAction.LOGIN_FAILED,
            user_id   = None,
            request   = request,
            details   = {"email": body.email, "reason": "invalid_credentials"},
            success   = False,
        )
        raise HTTPException(401, "Invalid credentials")

    audit.log(
        action      = AuditAction.LOGIN_SUCCESS,
        user_id     = user.id,
        request     = request,
        details     = {"email": user.email, "plan": user.plan},
    )
    ...


@app.delete("/users/{user_id}")
async def delete_user(
    user_id: int,
    current_user = Depends(get_current_user),
    request: Request = None,
):
    await perform_delete(user_id)

    audit.log(
        action       = AuditAction.DATA_DELETED,
        user_id      = current_user.id,
        request      = request,
        resource     = "user",
        resource_id  = str(user_id),
        details      = {"deleted_by": current_user.email, "reason": "admin_action"},
    )
    return {"message": "User deleted"}


# ─── FastAPI Middleware for automatic audit logging ───
from starlette.middleware.base import BaseHTTPMiddleware

class AuditMiddleware(BaseHTTPMiddleware):
    """Auto-log all API requests (optional, for compliance-heavy apps)."""

    SKIP_PATHS = {"/health", "/metrics", "/docs", "/openapi.json"}

    async def dispatch(self, request: Request, call_next):
        if request.url.path in self.SKIP_PATHS:
            return await call_next(request)

        start_time = datetime.now(timezone.utc)
        response   = await call_next(request)
        duration   = (datetime.now(timezone.utc) - start_time).total_seconds()

        # Only log non-GET requests (mutations) automatically
        # GET requests logged explicitly where sensitive
        if request.method in ("POST", "PUT", "PATCH", "DELETE"):
            user_id = getattr(request.state, "user_id", None)  # Set by auth middleware
            audit.log(
                action    = AuditAction.DATA_CREATED if request.method == "POST"
                           else AuditAction.DATA_UPDATED if request.method in ("PUT", "PATCH")
                           else AuditAction.DATA_DELETED,
                user_id   = user_id,
                request   = request,
                details   = {
                    "status_code": response.status_code,
                    "duration_ms": round(duration * 1000, 2),
                },
                success   = response.status_code < 400,
            )

        return response


# ─── Audit log format (JSON lines, queryable) ───
"""
{"event_id":"abc123","timestamp":"2024-01-15T10:30:00Z","action":"auth.login.success",
 "user_id":42,"success":true,"ip":"1.2.3.4","user_agent":"Mozilla/5.0...","method":"POST",
 "path":"/auth/login","details":{"email":"alice@example.com","plan":"premium"}}

{"event_id":"def456","timestamp":"2024-01-15T10:31:00Z","action":"data.deleted",
 "user_id":1,"success":true,"resource":"user","resource_id":"99","ip":"10.0.0.1",
 "details":{"deleted_by":"admin@example.com","reason":"admin_action"}}
"""

# ─── Query audit logs with jq ───
"""
# Logins in last hour:
grep '"action":"auth.login' audit.log | jq 'select(.timestamp > "2024-01-15T09:00:00Z")'

# Failed logins (potential brute force):
grep '"action":"auth.login.failed"' audit.log | jq '.ip' | sort | uniq -c | sort -rn

# All actions by user 42:
grep '"user_id":42' audit.log | jq '{action, timestamp, resource}'
"""
```

---

# PART 5: Security Headers & CSP

### Content Security Policy (CSP) for APIs
```python
class AdvancedSecurityMiddleware(BaseHTTPMiddleware):
    """Production-grade security headers."""

    async def dispatch(self, request, call_next):
        response = await call_next(request)

        # For API responses (JSON): strict CSP
        if "application/json" in response.headers.get("content-type", ""):
            response.headers["Content-Security-Policy"] = "default-src 'none'"
            response.headers["X-Content-Type-Options"]  = "nosniff"

        # HSTS: Force HTTPS for 1 year
        response.headers["Strict-Transport-Security"] = \
            "max-age=31536000; includeSubDomains; preload"

        # Prevent clickjacking
        response.headers["X-Frame-Options"] = "DENY"

        # Remove fingerprinting headers
        response.headers.pop("Server", None)
        response.headers.pop("X-Powered-By", None)

        # Permissions Policy: disable dangerous browser features
        response.headers["Permissions-Policy"] = \
            "geolocation=(), microphone=(), camera=(), usb=(), payment=()"

        # Referrer: Don't leak URL to external sites
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # Cross-Origin headers
        response.headers["Cross-Origin-Opener-Policy"]   = "same-origin"
        response.headers["Cross-Origin-Resource-Policy"] = "same-origin"
        response.headers["Cross-Origin-Embedder-Policy"] = "require-corp"

        return response
```

---

## Summary Table

| Vulnerability | Attack | Fix |
|---|---|---|
| alg:none | Forge tokens by disabling signature | `algorithms=["HS256"]` explicit list |
| Weak secret | Brute-force HMAC key with hashcat | `secrets.token_hex(32)` minimum |
| Token leakage | Steal from URL/logs/localStorage | httpOnly cookie, never in URL |
| Token reuse | Replay after logout | Redis blacklist with JTI |
| Refresh replay | Reuse rotated refresh token | Family tracking → full family revocation |
| No 2FA | Password leak = account takeover | TOTP with `pyotp`, backup codes |
| Hardcoded secrets | Git exposure | Vault/AWS Secrets Manager + pydantic-settings |
| No audit log | Invisible breaches | Structured JSON audit with AuditAction enum |

| 2FA Concept | Detail |
|---|---|
| TOTP algorithm | HMAC-SHA1(secret, floor(time/30)) |
| Valid window | `valid_window=1` = ±30s clock skew |
| Backup codes | 10 codes, single-use, stored hashed |
| Temp token | Short-lived (5 min), scope="2fa_pending" |
| QR code | `otpauth://totp/` URI format |

| Secret Management | When to Use |
|---|---|
| HashiCorp Vault | Self-hosted, dynamic DB credentials |
| AWS Secrets Manager | AWS-native, auto-rotation |
| pydantic-settings | Type-safe env loading, `SecretStr` |
| `.env` file | Development only, never in git |
