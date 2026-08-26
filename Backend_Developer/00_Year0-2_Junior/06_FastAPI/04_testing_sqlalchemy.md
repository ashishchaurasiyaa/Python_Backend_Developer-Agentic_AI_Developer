# FastAPI — Testing (pytest + httpx) + SQLAlchemy 2.0

## Quick Concepts
- **pytest** = Python ka standard testing framework
- **httpx** = async HTTP client — FastAPI testing ke liye
- **TestClient** = sync testing (httpx wrapper)
- **AsyncClient** = async tests ke liye
- **SQLAlchemy 2.0** = modern ORM — async support, typed queries
- **Repository pattern** = DB operations ko service logic se alag karo

---

## Andar kya hota hai — TestClient Asli Network Call NAHI Karta

### In-process ASGI call, koi socket nahi

```python
from fastapi.testclient import TestClient
client = TestClient(app)
response = client.get("/users/1")
```

Yeh koi real HTTP request bhej ke localhost pe listen nahi kar raha. `TestClient`
(aur naya `ASGITransport` + `httpx.AsyncClient` pattern) tumhare `app` callable ko
**seedha ek Python function ki tarah call** karta hai, ASGI protocol simulate
karke — ek `scope` dict banata hai (method, path, headers), `receive`/`send`
coroutines simulate karta hai. Koi TCP socket, koi real port bind, koi HTTP
parsing — sab **in-process**. Isiliye tests itni fast chalti hain.

### `dependency_overrides` — mocking library nahi chahiye, ek dict hai

```python
app.dependency_overrides[get_db] = get_test_db
```

FastAPI DI resolution (`02_dependency_injection.md`) ke andar, `get_db` ko call
karne se PEHLE ek check hota hai: "kya `app.dependency_overrides` dict mein iske
liye koi replacement hai?" Agar haan, ORIGINAL callable ke bajaye REPLACEMENT
call hota hai — poora resolution graph automatically test-version use karta hai,
kyunki override lookup HAR dependency-resolve step pe hota hai, sirf top-level pe
nahi. Isiliye `unittest.mock.patch` jaisi kisi library ki zaroorat nahi padti —
DI system khud hi swap-point hai.

---

## Interview Questions & Answers

### Q1: FastAPI testing kaise karte hain (pytest + httpx)?
**Answer:**
```python
# tests/conftest.py
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.main import app
from app.database import get_db, Base

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"

@pytest_asyncio.fixture(scope="session")
async def db_engine():
    engine = create_async_engine(TEST_DB_URL)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()

@pytest_asyncio.fixture
async def db_session(db_engine):
    TestSession = async_sessionmaker(db_engine, expire_on_commit=False)
    async with TestSession() as session:
        yield session
        await session.rollback()   # har test ke baad rollback

@pytest_asyncio.fixture
async def client(db_session: AsyncSession):
    async def override_db():
        yield db_session

    app.dependency_overrides[get_db] = override_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()

# tests/test_users.py
import pytest

@pytest.mark.asyncio
async def test_create_user(client: AsyncClient):
    response = await client.post("/users", json={
        "name": "Ashish",
        "email": "ashish@test.com",
        "age": 25
    })
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Ashish"
    assert data["email"] == "ashish@test.com"
    assert "id" in data

@pytest.mark.asyncio
async def test_get_user_not_found(client: AsyncClient):
    response = await client.get("/users/9999")
    assert response.status_code == 404
    assert response.json()["code"] == "NOT_FOUND"

@pytest.mark.asyncio
async def test_create_user_invalid_email(client: AsyncClient):
    response = await client.post("/users", json={
        "name": "Test",
        "email": "not-an-email",
        "age": 25
    })
    assert response.status_code == 422

@pytest.mark.asyncio
async def test_authenticated_endpoint(client: AsyncClient):
    # First create user and get token
    login_response = await client.post("/auth/login", json={
        "email": "ashish@test.com", "password": "password123"
    })
    token = login_response.json()["access_token"]

    # Use token
    response = await client.get(
        "/profile",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
```

---

### Q2: SQLAlchemy 2.0 models aur async queries kaise likhte hain?
**Answer:**
```python
from sqlalchemy import String, Integer, Boolean, DateTime, ForeignKey, Index, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime
from typing import Optional

class Base(DeclarativeBase):
    pass

class User(Base):
    __tablename__ = "users"

    # Typed columns (SQLAlchemy 2.0 style)
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(default=True)
    role: Mapped[str] = mapped_column(String(50), default="user")
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    # Relationship
    orders: Mapped[list["Order"]] = relationship(back_populates="user", lazy="selectin")

    __table_args__ = (
        Index("ix_users_email", "email"),
        Index("ix_users_role_active", "role", "is_active"),
    )

class Order(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    amount: Mapped[float]
    status: Mapped[str] = mapped_column(String(50), default="pending")
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    user: Mapped["User"] = relationship(back_populates="orders")
```

---

### Q3: SQLAlchemy 2.0 CRUD queries kaise likhte hain?
**Answer:**
```python
from sqlalchemy import select, update, delete, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload, joinedload

class UserRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    # CREATE
    async def create(self, name: str, email: str) -> User:
        user = User(name=name, email=email)
        self.db.add(user)
        await self.db.flush()   # ID generate karo (commit nahi)
        await self.db.refresh(user)
        return user

    # READ — single
    async def get_by_id(self, user_id: int) -> Optional[User]:
        return await self.db.get(User, user_id)

    async def get_by_email(self, email: str) -> Optional[User]:
        stmt = select(User).where(User.email == email)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    # READ — multiple with filters
    async def list_users(
        self,
        skip: int = 0,
        limit: int = 10,
        role: Optional[str] = None,
        search: Optional[str] = None,
    ) -> tuple[list[User], int]:
        stmt = select(User).where(User.is_active == True)

        if role:
            stmt = stmt.where(User.role == role)
        if search:
            stmt = stmt.where(
                or_(
                    User.name.ilike(f"%{search}%"),
                    User.email.ilike(f"%{search}%"),
                )
            )

        # Count total
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = await self.db.scalar(count_stmt)

        # Paginate
        stmt = stmt.offset(skip).limit(limit).order_by(User.created_at.desc())
        result = await self.db.execute(stmt)
        return result.scalars().all(), total

    # READ with eager loading
    async def get_with_orders(self, user_id: int) -> Optional[User]:
        stmt = (
            select(User)
            .options(selectinload(User.orders))  # N+1 problem avoid
            .where(User.id == user_id)
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    # UPDATE
    async def update(self, user_id: int, **kwargs) -> Optional[User]:
        stmt = (
            update(User)
            .where(User.id == user_id)
            .values(**kwargs)
            .returning(User)
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    # DELETE (soft delete)
    async def soft_delete(self, user_id: int) -> bool:
        result = await self.db.execute(
            update(User).where(User.id == user_id).values(is_active=False)
        )
        return result.rowcount > 0

    # Bulk insert
    async def bulk_create(self, users_data: list[dict]) -> list[User]:
        users = [User(**data) for data in users_data]
        self.db.add_all(users)
        await self.db.flush()
        return users
```

---

### Q4: Alembic migrations kaise karte hain?
**Answer:**
```bash
# Install + init
pip install alembic
alembic init alembic

# alembic/env.py mein models import karo
from app.models import Base
target_metadata = Base.metadata

# Migration create karo (auto-detect changes)
alembic revision --autogenerate -m "add users table"

# Apply karo
alembic upgrade head

# Ek step back
alembic downgrade -1

# History dekho
alembic history

# Current version
alembic current
```

```python
# alembic/versions/001_add_users.py
from alembic import op
import sqlalchemy as sa

def upgrade():
    op.create_table(
        "users",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("email", sa.String(255), unique=True, nullable=False),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_users_email", "users", ["email"])

def downgrade():
    op.drop_index("ix_users_email", "users")
    op.drop_table("users")
```

---

### Q5: Repository pattern FastAPI mein kaise use karte hain?
**Answer:**
```python
# Clean architecture — DB logic alag, route logic alag

# Service layer
class UserService:
    def __init__(self, repo: UserRepository):
        self.repo = repo

    async def register(self, email: str, name: str, password: str) -> User:
        existing = await self.repo.get_by_email(email)
        if existing:
            raise HTTPException(409, "Email already registered")
        hashed = hash_password(password)
        return await self.repo.create(name=name, email=email, hashed_password=hashed)

# Dependency
async def get_user_service(db: DbSession) -> UserService:
    return UserService(UserRepository(db))

UserServiceDep = Annotated[UserService, Depends(get_user_service)]

# Route — sirf HTTP logic, no DB code
@app.post("/register")
async def register(user: RegisterRequest, service: UserServiceDep):
    new_user = await service.register(user.email, user.name, user.password)
    return new_user
```
