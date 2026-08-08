"""
FastAPI Lab 03 — Async SQLAlchemy CRUD
=========================================
OBJECTIVE: implement real async `create_user` / `get_user` functions against
SQLAlchemy 2.0's async engine, verified with real pytest asserts.

TASK:
  1. TODO 1: implement `create_user()` — build a `UserORM`, add it to the
     session, commit, refresh, return it.
  2. TODO 2: implement `get_user()` — fetch a user by id with `session.get()`.
  3. Run: pytest 03_async_sqlalchemy_crud.py -v

Prereq: pip install sqlalchemy aiosqlite pytest pytest-asyncio

Note: uses aiosqlite (in-memory) instead of Postgres so this lab runs with
zero external services — no docker-compose needed here. If you want Postgres
parity with the rest of the repo's labs, swap DATABASE_URL for
`postgresql+asyncpg://lab:lab@localhost:5432/lab` and nothing else changes;
SQLAlchemy's async API is driver-agnostic.
"""

from __future__ import annotations

from typing import Optional

import pytest
import pytest_asyncio
from sqlalchemy import String
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class UserORM(Base):
    __tablename__ = "lab03_users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True)
    name: Mapped[str] = mapped_column(String(100))


# ─────────────────────────────────────────────────────────────
# TODO 1: create a UserORM row and persist it.
#   Hint:
#       user = UserORM(email=email, name=name)
#       session.add(user)
#       await session.commit()
#       await session.refresh(user)
#       return user
async def create_user(session: AsyncSession, email: str, name: str) -> UserORM:
    raise NotImplementedError("TODO 1: implement create_user()")
# ─────────────────────────────────────────────────────────────


# ─────────────────────────────────────────────────────────────
# TODO 2: fetch a user by primary key.
#   Hint: return await session.get(UserORM, user_id)
async def get_user(session: AsyncSession, user_id: int) -> Optional[UserORM]:
    raise NotImplementedError("TODO 2: implement get_user()")
# ─────────────────────────────────────────────────────────────


# ═══════════════════════════════════════════════════════
# pytest fixtures — fresh in-memory SQLite engine per test
# ═══════════════════════════════════════════════════════

DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture
async def session():
    engine = create_async_engine(DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    Session = async_sessionmaker(engine, expire_on_commit=False)
    async with Session() as s:
        yield s

    await engine.dispose()


# ═══════════════════════════════════════════════════════
# Tests — real behavioral asserts, not "did it run"
# ═══════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_create_user_assigns_id(session: AsyncSession):
    user = await create_user(session, "ada@example.com", "Ada Lovelace")
    assert user.id is not None
    assert user.email == "ada@example.com"


@pytest.mark.asyncio
async def test_get_user_returns_correct_row(session: AsyncSession):
    created = await create_user(session, "turing@example.com", "Alan Turing")
    fetched = await get_user(session, created.id)
    assert fetched is not None
    assert fetched.email == "turing@example.com"
    assert fetched.name == "Alan Turing"


@pytest.mark.asyncio
async def test_get_user_missing_returns_none(session: AsyncSession):
    fetched = await get_user(session, 9999)
    assert fetched is None


@pytest.mark.asyncio
async def test_duplicate_email_violates_unique_constraint(session: AsyncSession):
    await create_user(session, "dup@example.com", "First")
    with pytest.raises(IntegrityError):
        await create_user(session, "dup@example.com", "Second")


# ═══════════════════════════════════════════════════════
# Standalone runner — lets you `python 03_...py` for a quick smoke check
# in addition to the real pytest run.
# ═══════════════════════════════════════════════════════

async def _smoke() -> None:
    import asyncio

    engine = create_async_engine(DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    Session = async_sessionmaker(engine, expire_on_commit=False)

    try:
        async with Session() as s:
            user = await create_user(s, "smoke@example.com", "Smoke Test")
            fetched = await get_user(s, user.id)
            missing = await get_user(s, 9999)

        ok = (
            user.id is not None
            and fetched is not None
            and fetched.email == "smoke@example.com"
            and missing is None
        )
        print("\n" + "─" * 55)
        if ok:
            print("✅ PASS — create_user + get_user behave correctly")
        else:
            print("❌ FAIL — check TODO 1 (create_user) and TODO 2 (get_user)")
    except NotImplementedError as e:
        print(f"\n❌ {e}")
        print("   Run `pytest 03_async_sqlalchemy_crud.py -v` for the full picture.")
    finally:
        await engine.dispose()

    print("""
THINK (answer out loud):
  1. Why call `await session.refresh(user)` after `commit()`? What would be
     missing on `user` without it (hint: server-generated defaults)?
  2. `expire_on_commit=False` is set on the sessionmaker here — what would
     break in `test_get_user_returns_correct_row` if it were True/default?
  3. `session.get()` vs `select(UserORM).where(...)` — when does `.get()`
     stop being the right tool (composite lookups, extra filters)?
  4. This lab uses aiosqlite. What SQLAlchemy-level changes (if any) would
     be needed to point the same code at Postgres via asyncpg?
""")


if __name__ == "__main__":
    import asyncio

    asyncio.run(_smoke())
