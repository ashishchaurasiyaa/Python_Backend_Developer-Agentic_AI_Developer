"""
PHASE 2 FastAPI — Practical 07: SQLAlchemy 2.0 Async + Repository Pattern + Testing
Run app:   uvicorn 07_testing_sqlalchemy:app --reload
Run tests: pytest 07_testing_sqlalchemy.py -v  (requires pytest-asyncio, httpx, aiosqlite)

Install: pip install fastapi uvicorn sqlalchemy aiosqlite alembic pytest pytest-asyncio httpx

Topics:
  - SQLAlchemy 2.0 async models
  - Async session factory
  - CRUD with select(), insert(), update(), delete()
  - Relationships (lazy vs eager loading)
  - Repository pattern
  - Service layer
  - Dependency override for testing
  - pytest + httpx AsyncClient tests
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import Annotated, AsyncGenerator, Optional, Sequence

import pytest
import pytest_asyncio
from fastapi import Depends, FastAPI, HTTPException, status
from httpx import ASGITransport, AsyncClient
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import ForeignKey, String, Text, func, select
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


# ═══════════════════════════════════════════════════════
# SECTION 1: SQLAlchemy 2.0 Models
# ═══════════════════════════════════════════════════════

class Base(DeclarativeBase):
    pass


class UserORM(Base):
    __tablename__ = "users"

    id:    Mapped[int]          = mapped_column(primary_key=True, index=True)
    name:  Mapped[str]          = mapped_column(String(100))
    email: Mapped[str]          = mapped_column(String(255), unique=True, index=True)
    role:  Mapped[str]          = mapped_column(String(20), default="user")
    is_active: Mapped[bool]     = mapped_column(default=True)

    # Relationship: one user → many posts
    posts: Mapped[list["PostORM"]] = relationship("PostORM", back_populates="author", lazy="select")

    def __repr__(self) -> str:
        return f"<User id={self.id} email={self.email}>"


class PostORM(Base):
    __tablename__ = "posts"

    id:        Mapped[int]          = mapped_column(primary_key=True, index=True)
    title:     Mapped[str]          = mapped_column(String(200))
    body:      Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    author_id: Mapped[int]          = mapped_column(ForeignKey("users.id"), index=True)
    published: Mapped[bool]         = mapped_column(default=False)

    author: Mapped["UserORM"] = relationship("UserORM", back_populates="posts")


# ═══════════════════════════════════════════════════════
# SECTION 2: Database Setup
# ═══════════════════════════════════════════════════════

# SQLite async (development). Production: postgresql+asyncpg://
DATABASE_URL = "sqlite+aiosqlite:///./fastapi_practical.db"

engine = create_async_engine(
    DATABASE_URL,
    echo=False,          # True = log all SQL queries
    future=True,
)

AsyncSessionFactory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,   # objects usable after commit
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency: yields DB session, auto-closes after request."""
    async with AsyncSessionFactory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise


DB = Annotated[AsyncSession, Depends(get_db)]


# ═══════════════════════════════════════════════════════
# SECTION 3: Repository Pattern
# ═══════════════════════════════════════════════════════

class UserRepository:
    """Data access layer — all DB queries for users here, no business logic."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, user_id: int) -> Optional[UserORM]:
        return await self.db.get(UserORM, user_id)

    async def get_by_email(self, email: str) -> Optional[UserORM]:
        result = await self.db.execute(select(UserORM).where(UserORM.email == email))
        return result.scalar_one_or_none()

    async def list(
        self,
        skip: int = 0,
        limit: int = 10,
        role: Optional[str] = None,
        active_only: bool = True,
    ) -> tuple[Sequence[UserORM], int]:
        q = select(UserORM)
        if role:
            q = q.where(UserORM.role == role)
        if active_only:
            q = q.where(UserORM.is_active.is_(True))

        # Total count
        count_q  = select(func.count()).select_from(q.subquery())
        total    = (await self.db.execute(count_q)).scalar_one()

        # Paginated results
        result   = await self.db.execute(q.offset(skip).limit(limit))
        users    = result.scalars().all()

        return users, total

    async def create(self, name: str, email: str, role: str = "user") -> UserORM:
        user = UserORM(name=name, email=email, role=role)
        self.db.add(user)
        await self.db.commit()
        await self.db.refresh(user)
        return user

    async def update(self, user: UserORM, **kwargs) -> UserORM:
        for k, v in kwargs.items():
            setattr(user, k, v)
        await self.db.commit()
        await self.db.refresh(user)
        return user

    async def delete(self, user: UserORM) -> None:
        await self.db.delete(user)
        await self.db.commit()

    async def exists_by_email(self, email: str) -> bool:
        result = await self.db.execute(
            select(func.count()).where(UserORM.email == email)
        )
        return (result.scalar_one() or 0) > 0


class PostRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, post_id: int) -> Optional[PostORM]:
        return await self.db.get(PostORM, post_id)

    async def list_by_author(self, author_id: int, published_only: bool = False) -> Sequence[PostORM]:
        q = select(PostORM).where(PostORM.author_id == author_id)
        if published_only:
            q = q.where(PostORM.published.is_(True))
        result = await self.db.execute(q.order_by(PostORM.id.desc()))
        return result.scalars().all()

    async def create(self, title: str, body: Optional[str], author_id: int) -> PostORM:
        post = PostORM(title=title, body=body, author_id=author_id)
        self.db.add(post)
        await self.db.commit()
        await self.db.refresh(post)
        return post

    async def publish(self, post: PostORM) -> PostORM:
        post.published = True
        await self.db.commit()
        await self.db.refresh(post)
        return post


# ═══════════════════════════════════════════════════════
# SECTION 4: Service Layer
# ═══════════════════════════════════════════════════════

class UserService:
    """Business logic — uses UserRepository, raises domain errors."""

    def __init__(self, user_repo: UserRepository):
        self.user_repo = user_repo

    async def register(self, name: str, email: str, role: str = "user") -> UserORM:
        if await self.user_repo.exists_by_email(email):
            raise HTTPException(status_code=409, detail=f"Email '{email}' already registered")
        return await self.user_repo.create(name=name, email=email, role=role)

    async def get_or_404(self, user_id: int) -> UserORM:
        user = await self.user_repo.get_by_id(user_id)
        if not user:
            raise HTTPException(status_code=404, detail=f"User {user_id} not found")
        return user

    async def deactivate(self, user_id: int) -> UserORM:
        user = await self.get_or_404(user_id)
        return await self.user_repo.update(user, is_active=False)


# ─── Dependency helpers ───
def get_user_repo(db: DB) -> UserRepository:
    return UserRepository(db)

def get_post_repo(db: DB) -> PostRepository:
    return PostRepository(db)

def get_user_service(repo: Annotated[UserRepository, Depends(get_user_repo)]) -> UserService:
    return UserService(repo)

UserRepo    = Annotated[UserRepository, Depends(get_user_repo)]
PostRepo    = Annotated[PostRepository, Depends(get_post_repo)]
UserSvc     = Annotated[UserService,    Depends(get_user_service)]


# ═══════════════════════════════════════════════════════
# SECTION 5: Pydantic Schemas
# ═══════════════════════════════════════════════════════

class UserCreate(BaseModel):
    name:  str = Field(..., min_length=2)
    email: EmailStr
    role:  str = "user"


class UserOut(BaseModel):
    id:       int
    name:     str
    email:    str
    role:     str
    is_active: bool

    model_config = {"from_attributes": True}


class PostCreate(BaseModel):
    title: str = Field(..., min_length=3)
    body:  Optional[str] = None


class PostOut(BaseModel):
    id:        int
    title:     str
    body:      Optional[str]
    author_id: int
    published: bool

    model_config = {"from_attributes": True}


# ═══════════════════════════════════════════════════════
# SECTION 6: FastAPI App + Routes
# ═══════════════════════════════════════════════════════

@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("✅ DB tables created")
    yield
    await engine.dispose()
    print("✅ DB engine disposed")


app = FastAPI(
    title="FastAPI SQLAlchemy + Repository + Testing",
    version="1.0.0",
    lifespan=lifespan,
)


@app.get("/", tags=["Root"])
async def root():
    return {"message": "SQLAlchemy + Repository Pattern — visit /docs"}


# ─── User routes ───
@app.get("/users", response_model=list[UserOut], tags=["Users"])
async def list_users(
    skip: int = 0,
    limit: int = 10,
    role: Optional[str] = None,
    repo: UserRepo = ...,
):
    users, total = await repo.list(skip=skip, limit=limit, role=role)
    return users


@app.get("/users/{user_id}", response_model=UserOut, tags=["Users"])
async def get_user(user_id: int, svc: UserSvc):
    return await svc.get_or_404(user_id)


@app.post("/users", response_model=UserOut, status_code=201, tags=["Users"])
async def create_user(body: UserCreate, svc: UserSvc):
    return await svc.register(body.name, body.email, body.role)


@app.delete("/users/{user_id}", status_code=204, tags=["Users"])
async def deactivate_user(user_id: int, svc: UserSvc):
    await svc.deactivate(user_id)


# ─── Post routes ───
@app.get("/users/{user_id}/posts", response_model=list[PostOut], tags=["Posts"])
async def get_user_posts(
    user_id: int,
    published_only: bool = False,
    svc: UserSvc = ...,
    repo: PostRepo = ...,
):
    await svc.get_or_404(user_id)  # verify user exists
    posts = await repo.list_by_author(user_id, published_only=published_only)
    return posts


@app.post("/users/{user_id}/posts", response_model=PostOut, status_code=201, tags=["Posts"])
async def create_post(user_id: int, body: PostCreate, svc: UserSvc, repo: PostRepo):
    await svc.get_or_404(user_id)
    return await repo.create(title=body.title, body=body.body, author_id=user_id)


@app.patch("/posts/{post_id}/publish", response_model=PostOut, tags=["Posts"])
async def publish_post(post_id: int, repo: PostRepo):
    post = await repo.get_by_id(post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    return await repo.publish(post)


# ═══════════════════════════════════════════════════════
# SECTION 7: Tests (pytest + httpx AsyncClient)
# ═══════════════════════════════════════════════════════

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"

@pytest_asyncio.fixture(scope="session")
async def test_engine():
    eng = create_async_engine(TEST_DB_URL, echo=False, future=True)
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await eng.dispose()


@pytest_asyncio.fixture
async def db_session(test_engine):
    """Fresh session for each test — rolls back after test."""
    TestSession = async_sessionmaker(test_engine, expire_on_commit=False)
    async with TestSession() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def client(test_engine):
    """AsyncClient with DB overridden to use test SQLite."""
    TestSession = async_sessionmaker(test_engine, expire_on_commit=False)

    async def override_get_db():
        async with TestSession() as session:
            try:
                yield session
            except Exception:
                await session.rollback()
                raise

    # Override the DB dependency
    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac

    app.dependency_overrides.clear()


# ─── Tests ───

@pytest.mark.asyncio
async def test_create_user(client: AsyncClient):
    resp = await client.post("/users", json={
        "name": "Test User",
        "email": "test@example.com",
        "role": "user",
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["email"] == "test@example.com"
    assert data["is_active"] is True


@pytest.mark.asyncio
async def test_duplicate_email(client: AsyncClient):
    payload = {"name": "Alice", "email": "alice@test.com", "role": "user"}
    await client.post("/users", json=payload)

    resp = await client.post("/users", json=payload)
    assert resp.status_code == 409
    assert "already registered" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_get_user_not_found(client: AsyncClient):
    resp = await client.get("/users/9999")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_user_posts_flow(client: AsyncClient):
    # Create user
    user_resp = await client.post("/users", json={
        "name": "PostUser", "email": "postuser@test.com", "role": "user"
    })
    user_id = user_resp.json()["id"]

    # Create post
    post_resp = await client.post(f"/users/{user_id}/posts", json={
        "title": "My First Post",
        "body": "Hello world",
    })
    assert post_resp.status_code == 201
    post_id = post_resp.json()["id"]
    assert post_resp.json()["published"] is False

    # Publish
    pub_resp = await client.patch(f"/posts/{post_id}/publish")
    assert pub_resp.status_code == 200
    assert pub_resp.json()["published"] is True

    # List published posts only
    list_resp = await client.get(f"/users/{user_id}/posts?published_only=true")
    posts = list_resp.json()
    assert len(posts) == 1
    assert posts[0]["id"] == post_id


@pytest.mark.asyncio
async def test_repository_directly(db_session: AsyncSession):
    """Test repository without going through HTTP layer."""
    repo = UserRepository(db_session)

    user = await repo.create("Direct User", "direct@test.com")
    assert user.id is not None
    assert user.email == "direct@test.com"

    fetched = await repo.get_by_id(user.id)
    assert fetched is not None
    assert fetched.name == "Direct User"

    exists = await repo.exists_by_email("direct@test.com")
    assert exists is True

    not_exists = await repo.exists_by_email("nobody@test.com")
    assert not_exists is False


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("07_testing_sqlalchemy:app", host="0.0.0.0", port=8006, reload=True)
