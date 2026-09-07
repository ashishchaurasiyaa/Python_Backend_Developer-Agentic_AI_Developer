"""Async database engine + session dependency (SQLAlchemy 2.0 style)."""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import get_settings

settings = get_settings()

engine = create_async_engine(settings.database_url, echo=settings.debug, pool_pre_ping=True)

AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session


async def init_models() -> None:
    """Create tables from metadata. Fine for this project's scope — a real
    production deployment would use Alembic migrations instead so schema
    changes are versioned and reviewable, not just re-derived from models."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
