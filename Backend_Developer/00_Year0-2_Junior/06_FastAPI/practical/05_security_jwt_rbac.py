"""
PHASE 2 FastAPI — Practical 05: Security — JWT Refresh Tokens + RBAC
Run: uvicorn 05_security_jwt_rbac:app --reload
Docs: http://127.0.0.1:8000/docs

Topics:
  - Access token (15 min) + Refresh token (7 days)
  - Token pair creation + verification
  - Logout with Redis blacklist (simulated)
  - RBAC — Role-Based Access Control
  - Permission-based access
  - API Key authentication
  - Password hashing (bcrypt)
"""

from __future__ import annotations

import hashlib
import secrets
import time
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Query, Request, Security, status
from fastapi.security import (
    APIKeyHeader,
    HTTPAuthorizationCredentials,
    HTTPBearer,
    OAuth2PasswordBearer,
    OAuth2PasswordRequestForm,
)
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel, EmailStr, Field


# ═══════════════════════════════════════════════════════
# SECTION 1: Config
# ═══════════════════════════════════════════════════════

SECRET_KEY = "learning-secret-key-256-bits-long-enough"
ALGORITHM  = "HS256"
ACCESS_EXPIRE_MINUTES  = 15
REFRESH_EXPIRE_DAYS    = 7

pwd_context    = CryptContext(schemes=["bcrypt"], deprecated="auto")
bearer_scheme  = HTTPBearer(auto_error=False)
oauth2_scheme  = OAuth2PasswordBearer(tokenUrl="/auth/token", auto_error=False)
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


# ═══════════════════════════════════════════════════════
# SECTION 2: Models
# ═══════════════════════════════════════════════════════

class UserRole(str, Enum):
    ADMIN   = "admin"
    MANAGER = "manager"
    USER    = "user"
    VIEWER  = "viewer"

ROLE_HIERARCHY = {
    UserRole.ADMIN:   4,
    UserRole.MANAGER: 3,
    UserRole.USER:    2,
    UserRole.VIEWER:  1,
}

ROLE_PERMISSIONS: dict[UserRole, set[str]] = {
    UserRole.ADMIN:   {"read", "write", "delete", "manage_users", "view_billing"},
    UserRole.MANAGER: {"read", "write", "delete", "view_billing"},
    UserRole.USER:    {"read", "write"},
    UserRole.VIEWER:  {"read"},
}


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = ACCESS_EXPIRE_MINUTES * 60


class RefreshRequest(BaseModel):
    refresh_token: str


class TokenData(BaseModel):
    user_id: int
    email: str
    role: str


class UserCreate(BaseModel):
    name: str
    email: EmailStr
    password: str = Field(..., min_length=8)
    role: UserRole = UserRole.USER


class UserOut(BaseModel):
    id: int
    name: str
    email: str
    role: str


# ─── Simulated user DB ───
USERS_DB: dict[str, dict] = {
    "alice@example.com": {
        "id": 1, "name": "Alice", "email": "alice@example.com",
        "hashed_password": pwd_context.hash("AdminPass1"),
        "role": "admin", "is_active": True,
    },
    "bob@example.com": {
        "id": 2, "name": "Bob", "email": "bob@example.com",
        "hashed_password": pwd_context.hash("UserPass1"),
        "role": "user", "is_active": True,
    },
    "viewer@example.com": {
        "id": 3, "name": "Viewer", "email": "viewer@example.com",
        "hashed_password": pwd_context.hash("ViewPass1"),
        "role": "viewer", "is_active": True,
    },
}

# Simulated Redis blacklist {jti: expires_at}
TOKEN_BLACKLIST: dict[str, float] = {}

# Simulated API keys {hash: service_name}
API_KEYS_DB: dict[str, str] = {
    hashlib.sha256("sk_test_learning_key_123".encode()).hexdigest(): "test_service",
}


# ═══════════════════════════════════════════════════════
# SECTION 3: Token Utilities
# ═══════════════════════════════════════════════════════

def create_access_token(user_id: int, email: str, role: str) -> str:
    jti = secrets.token_hex(8)
    payload = {
        "sub": str(user_id),
        "email": email,
        "role": role,
        "type": "access",
        "jti": jti,
        "exp": datetime.now(timezone.utc) + timedelta(minutes=ACCESS_EXPIRE_MINUTES),
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def create_refresh_token(user_id: int) -> str:
    jti = secrets.token_hex(16)
    payload = {
        "sub": str(user_id),
        "type": "refresh",
        "jti": jti,
        "exp": datetime.now(timezone.utc) + timedelta(days=REFRESH_EXPIRE_DAYS),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def make_token_pair(user_id: int, email: str, role: str) -> TokenPair:
    return TokenPair(
        access_token=create_access_token(user_id, email, role),
        refresh_token=create_refresh_token(user_id),
    )


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )


def is_token_revoked(jti: str, expires_at: float) -> bool:
    """Check Redis blacklist (simulated here)."""
    # Clean expired entries
    now = time.time()
    expired = [k for k, v in TOKEN_BLACKLIST.items() if v < now]
    for k in expired:
        del TOKEN_BLACKLIST[k]
    return jti in TOKEN_BLACKLIST


# ═══════════════════════════════════════════════════════
# SECTION 4: Auth Dependencies
# ═══════════════════════════════════════════════════════

async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
) -> TokenData:
    if not credentials:
        raise HTTPException(
            status_code=401,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    payload = decode_token(credentials.credentials)

    if payload.get("type") != "access":
        raise HTTPException(status_code=401, detail="Access token required (not refresh)")

    jti = payload.get("jti", "")
    exp = payload.get("exp", 0)
    if is_token_revoked(jti, exp):
        raise HTTPException(status_code=401, detail="Token has been revoked (logged out)")

    return TokenData(
        user_id=int(payload["sub"]),
        email=payload["email"],
        role=payload["role"],
    )


CurrentUser = Annotated[TokenData, Depends(get_current_user)]


# ─── Role-based dependency ───
def require_role(*roles: str):
    def checker(current_user: CurrentUser):
        if current_user.role not in roles:
            raise HTTPException(
                status_code=403,
                detail=f"Role '{current_user.role}' not allowed. Required: {list(roles)}",
            )
        return current_user
    return Depends(checker)


# ─── Permission-based dependency ───
def require_permission(permission: str):
    def checker(current_user: CurrentUser):
        role = UserRole(current_user.role)
        if permission not in ROLE_PERMISSIONS.get(role, set()):
            raise HTTPException(
                status_code=403,
                detail=f"Permission '{permission}' required. Your role: '{current_user.role}'",
            )
        return current_user
    return Depends(checker)


# ─── Minimum role level dependency ───
def require_min_role(min_role: UserRole):
    def checker(current_user: CurrentUser):
        user_level = ROLE_HIERARCHY.get(UserRole(current_user.role), 0)
        required   = ROLE_HIERARCHY[min_role]
        if user_level < required:
            raise HTTPException(
                status_code=403,
                detail=f"Requires at least '{min_role.value}' role. You have '{current_user.role}'",
            )
        return current_user
    return Depends(checker)


# ─── API Key dependency ───
async def get_api_client(
    api_key: Optional[str] = Security(api_key_header),
) -> str:
    if not api_key:
        raise HTTPException(status_code=403, detail="X-API-Key header required")

    key_hash = hashlib.sha256(api_key.encode()).hexdigest()
    service  = API_KEYS_DB.get(key_hash)
    if not service:
        raise HTTPException(status_code=403, detail="Invalid API key")

    return service


# ═══════════════════════════════════════════════════════
# SECTION 5: App + Routes
# ═══════════════════════════════════════════════════════

app = FastAPI(
    title="FastAPI Security — JWT + RBAC",
    description="Phase 2 — Access/Refresh tokens, Role-Based Access, API Keys",
    version="1.0.0",
)

auth_router   = APIRouter(prefix="/auth",   tags=["Auth"])
user_router   = APIRouter(prefix="/users",  tags=["Users"])
admin_router  = APIRouter(prefix="/admin",  tags=["Admin"])
api_router    = APIRouter(prefix="/api",    tags=["API Key Auth"])


# ─── Auth routes ───

@auth_router.post("/register", response_model=UserOut, status_code=201)
async def register(body: UserCreate):
    if body.email in USERS_DB:
        raise HTTPException(status_code=409, detail="Email already registered")

    new_id = max(u["id"] for u in USERS_DB.values()) + 1
    USERS_DB[body.email] = {
        "id": new_id,
        "name": body.name,
        "email": body.email,
        "hashed_password": pwd_context.hash(body.password),
        "role": body.role.value,
        "is_active": True,
    }
    return UserOut(**USERS_DB[body.email])


@auth_router.post("/login", response_model=TokenPair)
async def login(email: str = Query(...), password: str = Query(...)):
    """Quick login — use /auth/token for OAuth2 standard."""
    user = USERS_DB.get(email)
    if not user or not pwd_context.verify(password, user["hashed_password"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if not user["is_active"]:
        raise HTTPException(status_code=403, detail="Account is deactivated")
    return make_token_pair(user["id"], user["email"], user["role"])


@auth_router.post("/token", response_model=TokenPair, summary="OAuth2 Password Flow")
async def oauth2_token(form_data: OAuth2PasswordRequestForm = Depends()):
    """
    OAuth2 standard endpoint. Works with Swagger 'Authorize' button.
    Username = email. Test: alice@example.com / AdminPass1
    """
    user = USERS_DB.get(form_data.username)
    if not user or not pwd_context.verify(form_data.password, user["hashed_password"]):
        raise HTTPException(
            status_code=400,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return make_token_pair(user["id"], user["email"], user["role"])


@auth_router.post("/refresh", response_model=TokenPair)
async def refresh(body: RefreshRequest):
    """Use refresh token to get a new token pair."""
    payload = decode_token(body.refresh_token)
    if payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Refresh token required")

    user_id = int(payload["sub"])
    user = next((u for u in USERS_DB.values() if u["id"] == user_id), None)
    if not user or not user["is_active"]:
        raise HTTPException(status_code=401, detail="User not found or inactive")

    return make_token_pair(user["id"], user["email"], user["role"])


@auth_router.post("/logout")
async def logout(
    current_user: CurrentUser,
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
):
    """Revoke access token — blacklist it in Redis."""
    payload = decode_token(credentials.credentials)
    jti = payload.get("jti", "")
    exp = float(payload.get("exp", time.time() + 900))

    if jti:
        TOKEN_BLACKLIST[jti] = exp  # revoke until natural expiry
    return {"message": f"Logged out. Token for {current_user.email} revoked."}


# ─── User routes ───

@user_router.get("/me", response_model=UserOut)
async def get_me(current_user: CurrentUser):
    user = next((u for u in USERS_DB.values() if u["id"] == current_user.user_id), None)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return UserOut(**user)


@user_router.get("/{user_id}", response_model=UserOut)
async def get_user(user_id: int, current_user: CurrentUser):
    # Users can only see themselves; admin/manager can see anyone
    if current_user.role not in ("admin", "manager") and current_user.user_id != user_id:
        raise HTTPException(status_code=403, detail="Cannot access another user's profile")
    user = next((u for u in USERS_DB.values() if u["id"] == user_id), None)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return UserOut(**user)


# ─── Admin routes (role-based) ───

@admin_router.get("/users")
async def list_all_users(
    current_user: CurrentUser = require_role("admin", "manager"),
):
    """Admin + Manager only."""
    return [UserOut(**u) for u in USERS_DB.values()]


@admin_router.delete("/users/{user_id}", status_code=204)
async def delete_user(
    user_id: int,
    current_user: CurrentUser = require_role("admin"),  # Admin only
):
    user = next((u for u in USERS_DB.values() if u["id"] == user_id), None)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    del USERS_DB[user["email"]]


@admin_router.get("/billing")
async def view_billing(
    current_user: CurrentUser = require_permission("view_billing"),
):
    """Requires 'view_billing' permission — admin + manager."""
    return {"invoices": [], "total_revenue": 99999.0, "accessed_by": current_user.email}


@admin_router.get("/reports")
async def get_reports(
    current_user: CurrentUser = require_min_role(UserRole.MANAGER),
):
    """Requires at least MANAGER role."""
    return {"reports": ["sales", "users", "revenue"], "generated_for": current_user.role}


# ─── API Key routes ───

@api_router.post("/ingest")
async def ingest_data(
    payload: dict,
    service: str = Depends(get_api_client),
):
    """Service-to-service endpoint. Header: X-API-Key: sk_test_learning_key_123"""
    return {"received": True, "service": service, "keys": list(payload.keys())}


# ─── Permission showcase ───
@app.get("/permissions/my", tags=["Permissions"])
async def my_permissions(current_user: CurrentUser):
    """Show what permissions the current user has."""
    role  = UserRole(current_user.role)
    perms = ROLE_PERMISSIONS.get(role, set())
    level = ROLE_HIERARCHY.get(role, 0)
    return {
        "user": current_user.email,
        "role": current_user.role,
        "level": level,
        "permissions": sorted(perms),
    }


app.include_router(auth_router)
app.include_router(user_router)
app.include_router(admin_router)
app.include_router(api_router)


@app.get("/", tags=["Root"])
async def root():
    return {
        "message": "JWT + RBAC Practical",
        "test_users": {
            "admin":   "alice@example.com / AdminPass1",
            "user":    "bob@example.com / UserPass1",
            "viewer":  "viewer@example.com / ViewPass1",
        },
        "api_key": "sk_test_learning_key_123",
        "tip": "Use POST /auth/token to login, then click Authorize in Swagger",
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("05_security_jwt_rbac:app", host="0.0.0.0", port=8004, reload=True)
