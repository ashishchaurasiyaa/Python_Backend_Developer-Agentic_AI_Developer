"""
Async database engine + session dependency (SQLAlchemy 2.0 style).

The engine is created lazily at import but does NOT connect until a session is
first used, so the app boots even before Postgres is up (health check stays green).
Models + Alembic migrations arrive on Day 2.
"""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.config import get_settings

settings = get_settings()

engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
    pool_pre_ping=True,   # drop dead connections instead of erroring mid-request
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    """Declarative base for all ORM models (populated Day 2)."""


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency — one session per request, always closed."""
    async with AsyncSessionLocal() as session:
        yield session
