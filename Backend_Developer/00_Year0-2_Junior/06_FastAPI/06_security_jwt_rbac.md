# FastAPI — Security: JWT Refresh Tokens + RBAC + OAuth2
**FastAPI · Year 0-2 | Senior Backend + Agentic AI**

## Quick Concepts
- **Access token** = short-lived (15 min) — API calls ke liye
- **Refresh token** = long-lived (7 days) — new access token generate karne ke liye
- **RBAC** = Role-Based Access Control — user ka role decide karta hai kya kar sakta hai
- **OAuth2 Password Flow** = username+password → token (internal APIs ke liye)
- **API Key** = service-to-service auth (agents, webhooks)
- **HTTPBearer** = Authorization: Bearer <token> header

---

## Interview Questions & Answers

### Q1: JWT access + refresh token system kaise banate hain?
**Answer:**
```python
import secrets
from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel
import redis.asyncio as aioredis

# ─── Config ───
SECRET_KEY = "your-256-bit-secret-key-store-in-env"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 15
REFRESH_TOKEN_EXPIRE_DAYS = 7

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
bearer_scheme = HTTPBearer()

# ─── Models ───
class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = ACCESS_TOKEN_EXPIRE_MINUTES * 60  # seconds

class RefreshRequest(BaseModel):
    refresh_token: str

class TokenData(BaseModel):
    user_id: int
    email: str
    role: str
    token_type: str  # "access" or "refresh"

# ─── Token Creation ───
def create_access_token(user_id: int, email: str, role: str) -> str:
    payload = {
        "sub": str(user_id),
        "email": email,
        "role": role,
        "type": "access",
        "exp": datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

def create_refresh_token(user_id: int) -> str:
    payload = {
        "sub": str(user_id),
        "type": "refresh",
        "jti": secrets.token_hex(16),  # unique ID — for revocation
        "exp": datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

def create_token_pair(user_id: int, email: str, role: str) -> TokenPair:
    return TokenPair(
        access_token=create_access_token(user_id, email, role),
        refresh_token=create_refresh_token(user_id),
    )

# ─── Token Verification ───
def decode_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

# ─── Current User Dependency ───
async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(bearer_scheme)],
    redis: aioredis.Redis = Depends(get_redis),  # check revocation
) -> TokenData:
    payload = decode_token(credentials.credentials)

    # Reject refresh tokens in API endpoints
    if payload.get("type") != "access":
        raise HTTPException(status_code=401, detail="Access token required")

    # Check if token is revoked (logout blacklist in Redis)
    jti = payload.get("jti")
    if jti and await redis.exists(f"revoked:{jti}"):
        raise HTTPException(status_code=401, detail="Token has been revoked")

    return TokenData(
        user_id=int(payload["sub"]),
        email=payload["email"],
        role=payload["role"],
        token_type=payload["type"],
    )

CurrentUser = Annotated[TokenData, Depends(get_current_user)]

# ─── Auth Routes ───
router = APIRouter(prefix="/auth", tags=["auth"])

@router.post("/login", response_model=TokenPair)
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    # Verify user from DB
    user = await user_repo.get_by_email(form_data.username)
    if not user or not pwd_context.verify(form_data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    return create_token_pair(user.id, user.email, user.role)

@router.post("/refresh", response_model=TokenPair)
async def refresh_tokens(body: RefreshRequest, db=Depends(get_db)):
    payload = decode_token(body.refresh_token)

    if payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Refresh token required")

    user = await user_repo.get_by_id(int(payload["sub"]), db)
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found or inactive")

    return create_token_pair(user.id, user.email, user.role)

@router.post("/logout")
async def logout(
    current_user: CurrentUser,
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    redis: aioredis.Redis = Depends(get_redis),
):
    """Revoke access token — add to Redis blacklist until expiry."""
    payload = decode_token(credentials.credentials)
    jti = payload.get("jti", credentials.credentials[-8:])  # fallback
    exp = payload.get("exp", 0)
    ttl = max(0, exp - int(datetime.now(timezone.utc).timestamp()))

    await redis.setex(f"revoked:{jti}", ttl, "1")
    return {"message": "Logged out successfully"}
```

---

### Q2: RBAC (Role-Based Access Control) kaise implement karte hain?
**Answer:**
```python
from enum import Enum
from typing import Callable

class UserRole(str, Enum):
    ADMIN = "admin"
    MANAGER = "manager"
    USER = "user"
    VIEWER = "viewer"

# Role hierarchy: ADMIN > MANAGER > USER > VIEWER
ROLE_HIERARCHY = {
    UserRole.ADMIN:   4,
    UserRole.MANAGER: 3,
    UserRole.USER:    2,
    UserRole.VIEWER:  1,
}

# ─── Permission-based (fine-grained) ───
ROLE_PERMISSIONS: dict[UserRole, set[str]] = {
    UserRole.ADMIN:   {"read", "write", "delete", "manage_users", "view_billing"},
    UserRole.MANAGER: {"read", "write", "delete", "view_billing"},
    UserRole.USER:    {"read", "write"},
    UserRole.VIEWER:  {"read"},
}

def require_role(*allowed_roles: UserRole):
    """Dependency factory — enforce role check."""
    def dependency(current_user: CurrentUser):
        if current_user.role not in [r.value for r in allowed_roles]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{current_user.role}' not allowed. Required: {[r.value for r in allowed_roles]}"
            )
        return current_user
    return Depends(dependency)


def require_permission(permission: str):
    """Dependency factory — enforce permission check."""
    def dependency(current_user: CurrentUser):
        role = UserRole(current_user.role)
        if permission not in ROLE_PERMISSIONS.get(role, set()):
            raise HTTPException(
                status_code=403,
                detail=f"Permission '{permission}' required"
            )
        return current_user
    return Depends(dependency)


def require_min_role(min_role: UserRole):
    """Dependency — require at least a certain role level."""
    def dependency(current_user: CurrentUser):
        user_level = ROLE_HIERARCHY.get(UserRole(current_user.role), 0)
        required_level = ROLE_HIERARCHY[min_role]
        if user_level < required_level:
            raise HTTPException(status_code=403, detail="Insufficient role")
        return current_user
    return Depends(dependency)


# ─── Usage in routes ───
admin_router = APIRouter(prefix="/admin", tags=["admin"])
user_router  = APIRouter(prefix="/users", tags=["users"])

# Admin only
@admin_router.delete("/users/{user_id}")
async def delete_user(
    user_id: int,
    current_user: CurrentUser = require_role(UserRole.ADMIN),
):
    return {"deleted": user_id}

# Admin or Manager
@admin_router.get("/reports")
async def get_reports(
    current_user: CurrentUser = require_role(UserRole.ADMIN, UserRole.MANAGER),
):
    return {"reports": []}

# Permission-based
@user_router.post("/documents")
async def create_document(
    current_user: CurrentUser = require_permission("write"),
):
    return {"created": True}

# Resource ownership check — user can only access own data
@user_router.get("/profile/{user_id}")
async def get_profile(user_id: int, current_user: CurrentUser):
    if current_user.role not in ["admin", "manager"] and current_user.user_id != user_id:
        raise HTTPException(status_code=403, detail="Cannot access another user's profile")
    return {"user_id": user_id}
```

---

### Q3: API Key authentication (service-to-service) kaise karte hain?
**Answer:**
```python
from fastapi import Security
from fastapi.security import APIKeyHeader, APIKeyQuery

# Header-based API key (recommended)
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

# Query-based (for webhooks, simple integrations)
api_key_query = APIKeyQuery(name="api_key", auto_error=False)

async def get_api_key(
    header_key: str | None = Security(api_key_header),
    query_key:  str | None = Security(api_key_query),
    db = Depends(get_db),
) -> dict:
    """Accept API key from header OR query param."""
    api_key = header_key or query_key

    if not api_key:
        raise HTTPException(status_code=403, detail="API key required")

    # Look up in DB (hashed keys)
    import hashlib
    key_hash = hashlib.sha256(api_key.encode()).hexdigest()
    key_record = await api_key_repo.get_by_hash(key_hash, db)

    if not key_record or not key_record.is_active:
        raise HTTPException(status_code=403, detail="Invalid API key")

    # Rate limit check per API key
    await check_api_key_rate_limit(key_record.id)

    return {"service": key_record.service_name, "key_id": key_record.id}

# Usage:
@app.post("/webhooks/ingest")
async def ingest_data(
    payload: dict,
    api_client: dict = Depends(get_api_key),
):
    return {"received": True, "service": api_client["service"]}

# Generate API key (admin endpoint)
@admin_router.post("/api-keys")
async def create_api_key(service_name: str, current_user: CurrentUser = require_role(UserRole.ADMIN)):
    import hashlib, secrets
    raw_key = f"sk_{secrets.token_urlsafe(32)}"
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
    # Save key_hash to DB (never save raw_key)
    # ...
    return {"api_key": raw_key, "note": "Save this — shown only once"}
```

---

### Q4: OAuth2 Password Flow complete implementation?
**Answer:**
```python
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token")

# Token endpoint — OAuth2 standard
@router.post("/token", response_model=TokenPair)
async def oauth2_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db = Depends(get_db),
):
    """
    OAuth2 Password Grant.
    form_data.username = email
    form_data.password = password
    form_data.scopes = requested scopes (optional)
    """
    user = await user_repo.get_by_email(form_data.username, db)
    if not user or not pwd_context.verify(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=400,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Validate requested scopes
    allowed_scopes = {"read", "write"} if user.role == "user" else {"read", "write", "admin"}
    granted_scopes = set(form_data.scopes) & allowed_scopes

    return create_token_pair(user.id, user.email, user.role)

# Current user from OAuth2 bearer token
async def get_current_user_oauth2(
    token: str = Depends(oauth2_scheme),
) -> TokenData:
    payload = decode_token(token)
    return TokenData(
        user_id=int(payload["sub"]),
        email=payload["email"],
        role=payload["role"],
        token_type="access",
    )
```

---

### Q5: Password hashing + security best practices?
**Answer:**
```python
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

class PasswordService:
    @staticmethod
    def hash(password: str) -> str:
        return pwd_context.hash(password)

    @staticmethod
    def verify(plain: str, hashed: str) -> bool:
        return pwd_context.verify(plain, hashed)

    @staticmethod
    def is_strong(password: str) -> bool:
        """Enforce password policy."""
        return (
            len(password) >= 8 and
            any(c.isupper() for c in password) and
            any(c.isdigit() for c in password)
        )

# ─── Security Best Practices Checklist ───
# ✓ Store bcrypt hashed passwords (never plaintext)
# ✓ Access tokens short-lived (15 min)
# ✓ Refresh tokens long-lived, stored in HttpOnly cookie or secure storage
# ✓ Refresh tokens rotated on each use (one-time use)
# ✓ Token revocation via Redis blacklist (logout support)
# ✓ HTTPS only in production
# ✓ Rate limit /login endpoint (prevent brute force)
# ✓ Store API keys as SHA-256 hashes
# ✓ Include 'type' claim in JWT to prevent refresh tokens used as access
# ✓ Use 'jti' (JWT ID) for revocation granularity
# ✓ CORS restricted to known origins
```

---

## Summary Table

| Scenario | Use |
|---|---|
| User login → tokens | OAuth2 Password Flow |
| Short-lived API access | Access token (15 min) |
| Get new access token | Refresh token (7 days) |
| Logout | Redis blacklist + token jti |
| Role-based routes | `require_role(UserRole.ADMIN)` |
| Fine-grained permissions | `require_permission("delete")` |
| Service-to-service | API key (hashed in DB) |
| Swagger auth in docs | `OAuth2PasswordBearer(tokenUrl=...)` |
