# FastAPI — Dependency Injection System

## Quick Concepts
- **Depends()** = FastAPI ka DI system — shared logic inject karo
- Dependencies automatically resolve hoti hain — chain ho sakti hain
- `yield` wali dependencies cleanup karte hain (DB sessions ke liye perfect)
- Request-scoped: ek request mein ek hi baar create hoti hai
- Testing mein easily mock/override kar sakte hain

---

## Interview Questions & Answers

### Q1: Dependency Injection kya hai? FastAPI mein kaise kaam karta hai?
**Answer:**
```python
from fastapi import FastAPI, Depends, HTTPException
from typing import Annotated

app = FastAPI()

# Simple dependency
def get_query_params(skip: int = 0, limit: int = 10):
    return {"skip": skip, "limit": limit}

@app.get("/items")
async def list_items(params: dict = Depends(get_query_params)):
    return params

# Annotated style (recommended FastAPI 0.95+)
PaginationDep = Annotated[dict, Depends(get_query_params)]

@app.get("/users")
async def list_users(pagination: PaginationDep):
    return pagination
```

---

### Q2: Database session dependency kaise banate hain?
**Answer:**
```python
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from fastapi import Depends
from typing import AsyncGenerator

engine = create_async_engine(DATABASE_URL, echo=False)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)

# yield dependency — request ke baad session close ho jaata hai
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        # finally: session automatically close hoga context manager se

DbSession = Annotated[AsyncSession, Depends(get_db)]

# Use karo
@app.get("/users/{user_id}")
async def get_user(user_id: int, db: DbSession):
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(404, "User not found")
    return user

@app.post("/users")
async def create_user(user_data: UserCreate, db: DbSession):
    user = User(**user_data.model_dump())
    db.add(user)
    # commit get_db mein hoga yield ke baad
    return user
```

---

### Q3: Authentication dependency kaise banate hain? JWT token verify karo
**Answer:**
```python
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt

security = HTTPBearer()

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db)
) -> User:
    token = credentials.credentials
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        user_id = payload.get("sub")
        if not user_id:
            raise ValueError("Invalid token")
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

    user = await db.get(User, int(user_id))
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found or inactive")
    return user

# Role-based dependency
def require_role(role: str):
    async def check_role(current_user: User = Depends(get_current_user)):
        if current_user.role != role:
            raise HTTPException(403, f"Role '{role}' required")
        return current_user
    return check_role

CurrentUser = Annotated[User, Depends(get_current_user)]
AdminUser = Annotated[User, Depends(require_role("admin"))]

# Routes
@app.get("/profile")
async def get_profile(user: CurrentUser):
    return user

@app.delete("/users/{user_id}")
async def delete_user(user_id: int, admin: AdminUser, db: DbSession):
    user = await db.get(User, user_id)
    await db.delete(user)
    return {"deleted": True}
```

---

### Q4: Dependency chain (nested dependencies) kaise kaam karta hai?
**Answer:**
```python
# Chain: get_settings → get_db → get_current_user → get_current_active_user

from functools import lru_cache
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    database_url: str
    secret_key: str
    redis_url: str

    class Config:
        env_file = ".env"

@lru_cache
def get_settings() -> Settings:
    return Settings()

SettingsDep = Annotated[Settings, Depends(get_settings)]

# Settings DB URL se engine banao
async def get_db(settings: SettingsDep) -> AsyncGenerator[AsyncSession, None]:
    engine = create_async_engine(settings.database_url)
    async with AsyncSessionLocal() as session:
        yield session

# User dependency DB use karta hai
async def get_current_user(db: DbSession) -> User:
    ...

# Final dependency
async def get_active_premium_user(
    user: Annotated[User, Depends(get_current_user)]
) -> User:
    if not user.is_active:
        raise HTTPException(400, "Inactive user")
    if user.plan != "premium":
        raise HTTPException(402, "Premium plan required")
    return user

# FastAPI automatically resolves the whole chain
@app.get("/premium-feature")
async def premium_endpoint(user: Annotated[User, Depends(get_active_premium_user)]):
    return {"message": f"Welcome premium user {user.name}"}
```

---

### Q5: Testing mein dependency override kaise karte hain?
**Answer:**
```python
# tests/conftest.py
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from app.main import app
from app.database import get_db

# Test DB (SQLite in-memory)
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"
test_engine = create_async_engine(TEST_DATABASE_URL)
TestSessionLocal = async_sessionmaker(test_engine)

async def override_get_db():
    async with TestSessionLocal() as session:
        yield session

# Override current user (authenticated)
async def override_get_current_user():
    return User(id=1, name="Test User", role="admin", is_active=True)

@pytest.fixture
def client():
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()

# Test
def test_get_profile(client):
    response = client.get("/profile")
    assert response.status_code == 200
    assert response.json()["name"] == "Test User"
```

---

### Q6: Redis/Cache dependency kaise banate hain?
**Answer:**
```python
import redis.asyncio as aioredis
from fastapi import Depends
import json

redis_client: aioredis.Redis = None

async def get_redis() -> aioredis.Redis:
    return redis_client   # lifespan mein initialized

RedisDep = Annotated[aioredis.Redis, Depends(get_redis)]

# Cache decorator as dependency
def cached(key_prefix: str, ttl: int = 300):
    async def cache_dep(redis: RedisDep) -> dict:
        return {"redis": redis, "key_prefix": key_prefix, "ttl": ttl}
    return Depends(cache_dep)

@app.get("/products/{product_id}")
async def get_product(
    product_id: int,
    db: DbSession,
    redis: RedisDep,
):
    cache_key = f"product:{product_id}"
    cached = await redis.get(cache_key)
    if cached:
        return json.loads(cached)

    product = await db.get(Product, product_id)
    if not product:
        raise HTTPException(404, "Product not found")

    await redis.setex(cache_key, 300, json.dumps(product.to_dict()))
    return product
```
