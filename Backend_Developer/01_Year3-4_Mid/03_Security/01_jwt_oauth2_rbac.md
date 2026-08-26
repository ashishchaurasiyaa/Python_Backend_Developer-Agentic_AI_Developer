# Security — JWT, OAuth2, RBAC, API Key Management, Input Validation

## Quick Concepts
- **JWT** = JSON Web Token — stateless auth token (header.payload.signature)
- **OAuth2** = authorization framework — Google/GitHub se login
- **RBAC** = Role-Based Access Control — role se permissions define karo
- **API Key** = server-to-server auth ke liye
- **Input validation** = SQL injection, XSS, command injection rokna

---

## Andar kya hota hai — JWT Signature Verify Kaise Hoti Hai, aur `alg: none` Attack

### Verify — recompute karke COMPARE karna hai, decrypt nahi

```
JWT = base64url(header) + "." + base64url(payload) + "." + signature

Verify process:
  1. header + payload ko base64url-decode karo (yeh PLAIN TEXT hain,
     "encrypted" nahi — koi bhi JWT ko decode karke padh sakta hai,
     ENCODED hai, ENCRYPTED nahi)
  2. header ka "alg" field padho (jaise "HS256" ya "RS256")
  3. USI algorithm se signature RECOMPUTE karo (header.payload string pe)
  4. recomputed signature == token ka signature? MATCH → valid; MISMATCH → reject
```

**`alg: none` attack** — agar server BLINDLY token ke apne "alg" header pe
trust karta hai (bina EXPECTED algorithm enforce kiye), attacker signature
hata ke header mein `"alg": "none"` likh sakta hai — kuch libraries yeh
accept kar leti thin (galat implementation). Fix: server hamesha EXPECTED
algorithm hardcode karke verify kare (`jwt.decode(token, key, algorithms=["HS256"])`),
token ke apne "alg" field pe kabhi decide na kare.

### RBAC — kis POINT pe enforce hota hai

Role check route HANDLER ke andar nahi, ek DEPENDENCY/MIDDLEWARE mein hona
chahiye jo handler chalne se PEHLE token ke role-claim ko required-role ke
against verify kare — yehi pattern `06_security_jwt_rbac.md` (FastAPI) mein
`Depends(require_role(...))` ki tarah already dikhaya gaya hai. Handler ke
ANDAR check karna galti-prone hai — ek naya route add karte waqt check
bhoolna easy hai.

---

## Interview Questions & Answers

### Q1: JWT kaise kaam karta hai? Access + Refresh token pattern?
**Answer:**
```
JWT Structure: base64(header).base64(payload).signature

Header: {"alg": "HS256", "typ": "JWT"}
Payload: {"sub": "123", "role": "admin", "exp": 1700000000}
Signature: HMAC_SHA256(header + "." + payload, SECRET_KEY)

ACCESS TOKEN: short-lived (15-30 min) — har request mein bhejo
REFRESH TOKEN: long-lived (7-30 days) — sirf new access token lene ke liye
```

```python
from datetime import datetime, timedelta
import jwt
from passlib.context import CryptContext

SECRET_KEY = "your-super-secret-key-min-32-chars"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE = timedelta(minutes=30)
REFRESH_TOKEN_EXPIRE = timedelta(days=7)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)

def create_access_token(user_id: int, role: str, extra: dict = {}) -> str:
    payload = {
        "sub": str(user_id),
        "role": role,
        "type": "access",
        "iat": datetime.utcnow(),
        "exp": datetime.utcnow() + ACCESS_TOKEN_EXPIRE,
        **extra,
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

def create_refresh_token(user_id: int) -> str:
    payload = {
        "sub": str(user_id),
        "type": "refresh",
        "iat": datetime.utcnow(),
        "exp": datetime.utcnow() + REFRESH_TOKEN_EXPIRE,
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(401, "Invalid token")

# Login endpoint
@app.post("/auth/login")
async def login(credentials: LoginRequest, db: DbSession):
    user = await db.scalar(select(User).where(User.email == credentials.email))
    if not user or not verify_password(credentials.password, user.hashed_password):
        raise HTTPException(401, "Invalid credentials")

    access_token = create_access_token(user.id, user.role)
    refresh_token = create_refresh_token(user.id)

    # Refresh token DB mein store karo (invalidate karne ke liye)
    await store_refresh_token(user.id, refresh_token)

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "expires_in": int(ACCESS_TOKEN_EXPIRE.total_seconds()),
    }

# Token refresh
@app.post("/auth/refresh")
async def refresh_token(refresh_token: str, db: DbSession):
    payload = decode_token(refresh_token)
    if payload.get("type") != "refresh":
        raise HTTPException(401, "Invalid token type")

    # DB mein check karo — revoked to nahi
    if not await is_refresh_token_valid(payload["sub"], refresh_token):
        raise HTTPException(401, "Refresh token revoked")

    user = await db.get(User, int(payload["sub"]))
    new_access = create_access_token(user.id, user.role)
    return {"access_token": new_access, "token_type": "bearer"}

# Logout — refresh token invalidate karo
@app.post("/auth/logout")
async def logout(current_user: CurrentUser, refresh_token: str):
    await revoke_refresh_token(current_user.id, refresh_token)
    return {"message": "Logged out"}
```

---

### Q2: OAuth2 flow kaise kaam karta hai? Google login implement karo
**Answer:**
```
AUTHORIZATION CODE FLOW:
1. User → "Login with Google" click karo
2. App → Google ko redirect karo (client_id, scope, redirect_uri, state)
3. User → Google mein login karo + permission do
4. Google → app ko code bhejta hai (redirect_uri + code)
5. App → Google ko code bhejta hai → ACCESS TOKEN milta hai
6. App → Google User API call karta hai → user info milti hai
7. App → apna JWT banata hai
```

```python
# pip install authlib httpx
from authlib.integrations.starlette_client import OAuth
from starlette.config import Config

config = Config(".env")
oauth = OAuth(config)

oauth.register(
    name="google",
    client_id=config("GOOGLE_CLIENT_ID"),
    client_secret=config("GOOGLE_CLIENT_SECRET"),
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_kwargs={"scope": "openid email profile"},
)

@app.get("/auth/google")
async def google_login(request: Request):
    redirect_uri = "https://myapp.com/auth/google/callback"
    return await oauth.google.authorize_redirect(request, redirect_uri)

@app.get("/auth/google/callback")
async def google_callback(request: Request, db: DbSession):
    token = await oauth.google.authorize_access_token(request)
    user_info = token["userinfo"]

    # User create ya fetch karo
    user = await db.scalar(select(User).where(User.email == user_info["email"]))
    if not user:
        user = User(
            email=user_info["email"],
            name=user_info["name"],
            google_id=user_info["sub"],
            is_verified=True,
        )
        db.add(user)
        await db.commit()

    access_token = create_access_token(user.id, user.role)
    refresh_token = create_refresh_token(user.id)

    # Frontend ko redirect karo token ke saath
    return RedirectResponse(
        f"https://myapp.com/auth/success?token={access_token}&refresh={refresh_token}"
    )
```

---

### Q3: RBAC kaise implement karte hain?
**Answer:**
```python
from enum import Enum
from typing import set

class Role(str, Enum):
    GUEST = "guest"
    USER = "user"
    MODERATOR = "moderator"
    ADMIN = "admin"
    SUPER_ADMIN = "super_admin"

class Permission(str, Enum):
    # Users
    READ_USERS = "users:read"
    CREATE_USERS = "users:create"
    UPDATE_USERS = "users:update"
    DELETE_USERS = "users:delete"
    # Orders
    READ_OWN_ORDERS = "orders:read:own"
    READ_ALL_ORDERS = "orders:read:all"
    # Admin
    ACCESS_DASHBOARD = "admin:dashboard"
    MANAGE_SETTINGS = "admin:settings"

# Role → Permissions mapping
ROLE_PERMISSIONS: dict[Role, set[Permission]] = {
    Role.GUEST: {Permission.READ_USERS},
    Role.USER: {
        Permission.READ_USERS,
        Permission.READ_OWN_ORDERS,
    },
    Role.MODERATOR: {
        Permission.READ_USERS,
        Permission.UPDATE_USERS,
        Permission.READ_ALL_ORDERS,
    },
    Role.ADMIN: {
        *ROLE_PERMISSIONS[Role.MODERATOR],
        Permission.CREATE_USERS,
        Permission.DELETE_USERS,
        Permission.ACCESS_DASHBOARD,
    },
    Role.SUPER_ADMIN: set(Permission),   # sabhi permissions
}

def has_permission(role: Role, permission: Permission) -> bool:
    return permission in ROLE_PERMISSIONS.get(role, set())

# Dependency factory
def require_permission(permission: Permission):
    async def check(current_user: CurrentUser) -> User:
        if not has_permission(Role(current_user.role), permission):
            raise HTTPException(
                status_code=403,
                detail=f"Permission '{permission}' required"
            )
        return current_user
    return Depends(check)

# Usage
@app.get("/admin/users", dependencies=[require_permission(Permission.READ_USERS)])
async def admin_list_users(db: DbSession): ...

@app.delete("/users/{id}")
async def delete_user(
    id: int,
    _: User = require_permission(Permission.DELETE_USERS),
    db: DbSession = Depends(get_db),
): ...
```

---

### Q4: API Key management kaise karte hain?
**Answer:**
```python
import secrets
import hashlib

class APIKeyService:
    @staticmethod
    def generate() -> tuple[str, str]:
        """Returns (raw_key, hashed_key) — raw key sirf ek baar dikhao"""
        raw_key = f"sk_{secrets.token_urlsafe(32)}"
        hashed = hashlib.sha256(raw_key.encode()).hexdigest()
        return raw_key, hashed

    @staticmethod
    def hash(raw_key: str) -> str:
        return hashlib.sha256(raw_key.encode()).hexdigest()

# Model
class APIKey(Base):
    __tablename__ = "api_keys"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    name: Mapped[str]                         # "Production Key", "Mobile App"
    key_hash: Mapped[str] = mapped_column(unique=True)  # stored hash
    prefix: Mapped[str]                       # "sk_abc123..." first 8 chars for display
    scopes: Mapped[str] = mapped_column(default="read")
    last_used_at: Mapped[Optional[datetime]]
    expires_at: Mapped[Optional[datetime]]
    is_active: Mapped[bool] = mapped_column(default=True)

# Create API key
@app.post("/api-keys")
async def create_api_key(name: str, scopes: str, current_user: CurrentUser, db: DbSession):
    raw_key, hashed = APIKeyService.generate()

    api_key = APIKey(
        user_id=current_user.id,
        name=name,
        key_hash=hashed,
        prefix=raw_key[:12],   # display ke liye
        scopes=scopes,
    )
    db.add(api_key)
    await db.commit()

    return {
        "key": raw_key,   # SIRF ABHI DIKHAO — store mat karo
        "prefix": api_key.prefix,
        "message": "Save this key securely — it won't be shown again"
    }

# Authenticate via API key
from fastapi.security import APIKeyHeader

api_key_header = APIKeyHeader(name="X-API-Key")

async def get_user_from_api_key(
    api_key: str = Depends(api_key_header),
    db: DbSession = Depends(get_db),
    redis: RedisDep = Depends(get_redis),
) -> User:
    # Cache mein check karo (performance)
    cache_key = f"apikey:{APIKeyService.hash(api_key)}"
    cached_user_id = await redis.get(cache_key)

    if not cached_user_id:
        key_record = await db.scalar(
            select(APIKey).where(
                APIKey.key_hash == APIKeyService.hash(api_key),
                APIKey.is_active == True,
                or_(APIKey.expires_at.is_(None), APIKey.expires_at > datetime.utcnow())
            )
        )
        if not key_record:
            raise HTTPException(401, "Invalid API key")

        await redis.setex(cache_key, 300, str(key_record.user_id))
        # Update last_used_at (background task se)
        cached_user_id = key_record.user_id

    return await db.get(User, int(cached_user_id))
```

---

### Q5: Input Validation — SQL Injection, XSS, Command Injection rokna
**Answer:**
```python
from pydantic import BaseModel, validator, field_validator
import bleach
import re

# 1. ALWAYS Pydantic use karo — raw dict nahi
class UserInput(BaseModel):
    username: str
    email: str
    age: int
    bio: str

    @field_validator("username")
    @classmethod
    def validate_username(cls, v: str) -> str:
        if not re.match(r"^[a-zA-Z0-9_-]{3,30}$", v):
            raise ValueError("Username: only alphanumeric, _, - allowed (3-30 chars)")
        return v

    @field_validator("bio")
    @classmethod
    def sanitize_bio(cls, v: str) -> str:
        # XSS: HTML tags strip karo
        return bleach.clean(v, tags=[], strip=True)

# 2. SQL Injection — NEVER string format karo
# BAD — SQL Injection possible!
query = f"SELECT * FROM users WHERE email = '{email}'"

# GOOD — parameterized queries
result = await db.execute(
    select(User).where(User.email == email)   # SQLAlchemy handles escaping
)
# Ya raw SQL mein:
result = await conn.fetch("SELECT * FROM users WHERE email = $1", email)

# 3. Command Injection — subprocess avoid karo
# BAD
import subprocess
subprocess.run(f"ffmpeg -i {filename}", shell=True)  # NEVER shell=True with user input

# GOOD
import shlex
safe_filename = shlex.quote(filename)
subprocess.run(["ffmpeg", "-i", safe_filename], shell=False)

# 4. Path Traversal
import os
from pathlib import Path

def safe_file_path(base_dir: str, filename: str) -> Path:
    base = Path(base_dir).resolve()
    full_path = (base / filename).resolve()
    if not str(full_path).startswith(str(base)):
        raise ValueError("Path traversal attempt detected")
    return full_path

# 5. Security Headers (FastAPI middleware)
@app.middleware("http")
async def security_headers(request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["Content-Security-Policy"] = "default-src 'self'"
    return response

# 6. HTTPS + CORS already configured (see middleware file)

# 7. Secrets management — NEVER hardcode
# BAD
DATABASE_URL = "postgresql://user:password@host/db"

# GOOD — environment variables ya AWS Secrets Manager
import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    database_url: str
    secret_key: str
    aws_access_key_id: str = ""   # IAM role se milta hai EC2 par

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
```
