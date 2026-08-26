"""
FastAPI Lab 07 — Async SQLAlchemy Transactions & Race Conditions
=================================================================
ARCHITECTURE — Transaction Lifecycle:

    async with session.begin():          ← BEGIN
        result = await session.execute(
            select(Account)
            .where(Account.id == aid)
            .with_for_update()           ← SELECT ... FOR UPDATE (row lock)
        )
        account = result.scalar_one()
        account.balance -= amount
    # EXIT → COMMIT (or ROLLBACK if exception)

WHY select_for_update()?
  Without it: two concurrent transfers of 500 from a 1000-balance account
  both read balance=1000, both subtract 500, both write 500 → balance = 500
  (should be 0). Race condition / "lost update".

  With it: second transaction blocks until first commits → reads 500,
  subtracts 500, result = 0. Correct.

WHY session.begin() context manager?
  COMMIT on __aexit__ (no exception), ROLLBACK on __aexit__ (exception).
  No manual commit/rollback needed. Cleaner than try/except/finally.

ISOLATION LEVELS (brief):
  READ COMMITTED  — sees only committed rows. Default in Postgres.
  REPEATABLE READ — snapshot frozen at tx start; phantom reads possible.
  SERIALIZABLE    — full isolation; slowest; use for financial ledgers.

INTERVIEW ANSWER:
  "FastAPI async SQLAlchemy mein race condition rokne ke liye
   select_for_update() use karte hain — ye SELECT...FOR UPDATE SQL generate
   karta hai jo row-level lock leta hai. Dusri transaction tab tak wait karti
   hai jab tak pehli commit ya rollback na kare. async with session.begin()
   context manager auto-commit/rollback handle karta hai."

TASK:
  1. TODO 1: implement transfer() — begin tx, select_for_update, debit + credit
  2. TODO 2: implement get_balance() — plain async read (no lock needed)
  3. TODO 3: implement concurrent_transfers() — run two transfers with
             asyncio.gather to trigger the race condition with/without FOR UPDATE
  4. Run: pytest 07_async_sqlalchemy_transactions.py -v  (or -v -p no:odoo)

Prereq: pip install sqlalchemy aiosqlite pytest pytest-asyncio
"""

from __future__ import annotations

import asyncio
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from sqlalchemy import String, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


# ════════════════════════════════════════════════════════════════════════════
# SCHEMA
# ════════════════════════════════════════════════════════════════════════════

class Base(DeclarativeBase):
    pass


class Account(Base):
    __tablename__ = "lab07_accounts"
    id:      Mapped[int]   = mapped_column(primary_key=True)
    owner:   Mapped[str]   = mapped_column(String(100))
    balance: Mapped[float]


# ════════════════════════════════════════════════════════════════════════════
# ENGINE + SESSION FACTORY (in-memory SQLite — no Docker needed)
# ════════════════════════════════════════════════════════════════════════════

DATABASE_URL = "sqlite+aiosqlite:///:memory:"
engine = create_async_engine(DATABASE_URL, echo=False)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


# ════════════════════════════════════════════════════════════════════════════
# TODO 1 — transfer(from_id, to_id, amount, session)
# ════════════════════════════════════════════════════════════════════════════
"""
Implement transfer(from_id: int, to_id: int, amount: float, session: AsyncSession) -> None

  Steps inside a transaction:
    1. Select from_account with WITH FOR UPDATE (row lock).
       Use: select(Account).where(Account.id == from_id).with_for_update()
    2. Execute: result = await session.execute(stmt)
    3. from_acc = result.scalar_one()
    4. Check from_acc.balance >= amount; raise ValueError("Insufficient funds") if not
    5. Fetch to_account (also with_for_update — prevents deadlocks via consistent ordering)
    6. from_acc.balance -= amount
    7. to_acc.balance  += amount
    (Transaction commits automatically when caller's `async with session.begin()` exits)

  Signature:
    async def transfer(
        from_id: int, to_id: int, amount: float, session: AsyncSession
    ) -> None:

  Hint:
    stmt = select(Account).where(Account.id == from_id).with_for_update()
    result = await session.execute(stmt)
    from_acc = result.scalar_one()
"""

async def transfer(from_id: int, to_id: int, amount: float, session: AsyncSession) -> None:
    raise NotImplementedError(
        "TODO 1: select_for_update both accounts, check balance, debit + credit"
    )


# ════════════════════════════════════════════════════════════════════════════
# TODO 2 — get_balance(account_id, session) → float
# ════════════════════════════════════════════════════════════════════════════
"""
Implement get_balance(account_id: int, session: AsyncSession) -> float

  Plain read — no FOR UPDATE needed (we're just reading, not writing).
  Use: await session.get(Account, account_id)
  Return account.balance. Raise ValueError if account not found.

  Hint:
    account = await session.get(Account, account_id)
    if account is None:
        raise ValueError(f"Account {account_id} not found")
    return account.balance
"""

async def get_balance(account_id: int, session: AsyncSession) -> float:
    raise NotImplementedError(
        "TODO 2: await session.get(Account, account_id); return account.balance"
    )


# ════════════════════════════════════════════════════════════════════════════
# TODO 3 — safe_transfer_with_begin(from_id, to_id, amount) → None
# ════════════════════════════════════════════════════════════════════════════
"""
Implement safe_transfer_with_begin(from_id: int, to_id: int, amount: float) -> None

  This is the CALLER — it opens the session + begins the transaction,
  then delegates the business logic to transfer().

  Pattern:
    async with AsyncSessionLocal() as session:
        async with session.begin():
            await transfer(from_id, to_id, amount, session)

  The double context manager is the canonical SQLAlchemy 2.0 async pattern:
    - AsyncSessionLocal() → opens session (connection)
    - session.begin()     → BEGIN; COMMIT on success, ROLLBACK on exception

  Hint:
    async def safe_transfer_with_begin(from_id, to_id, amount):
        async with AsyncSessionLocal() as session:
            async with session.begin():
                await transfer(from_id, to_id, amount, session)
"""

async def safe_transfer_with_begin(from_id: int, to_id: int, amount: float) -> None:
    raise NotImplementedError(
        "TODO 3: async with AsyncSessionLocal() as session: async with session.begin(): await transfer(...)"
    )


# ════════════════════════════════════════════════════════════════════════════
# FIXTURES
# ════════════════════════════════════════════════════════════════════════════

@pytest_asyncio.fixture(scope="function")
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Create tables, yield a fresh session, drop tables after test."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture(scope="function")
async def seeded_accounts(db_session: AsyncSession):
    """Insert Alice (1000) and Bob (500) and commit."""
    alice = Account(id=1, owner="Alice", balance=1000.0)
    bob   = Account(id=2, owner="Bob",   balance=500.0)
    db_session.add_all([alice, bob])
    await db_session.commit()
    return alice, bob


# ════════════════════════════════════════════════════════════════════════════
# TESTS
# ════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_simple_transfer(db_session: AsyncSession, seeded_accounts):
    """Alice sends 200 to Bob — balances must update atomically."""
    async with db_session.begin():
        await transfer(1, 2, 200.0, db_session)

    alice_bal = await get_balance(1, db_session)
    bob_bal   = await get_balance(2, db_session)

    assert alice_bal == 800.0, f"FAIL: Alice balance should be 800. Got {alice_bal}"
    assert bob_bal   == 700.0, f"FAIL: Bob balance should be 700. Got {bob_bal}"


@pytest.mark.asyncio
async def test_insufficient_funds_raises(db_session: AsyncSession, seeded_accounts):
    """Transfer more than balance → ValueError, balances unchanged."""
    with pytest.raises(ValueError, match="Insufficient"):
        async with db_session.begin():
            await transfer(2, 1, 9999.0, db_session)

    alice_bal = await get_balance(1, db_session)
    bob_bal   = await get_balance(2, db_session)

    assert alice_bal == 1000.0, f"FAIL: Alice balance should be unchanged (1000). Got {alice_bal}"
    assert bob_bal   ==  500.0, f"FAIL: Bob balance should be unchanged (500). Got {bob_bal}"


@pytest.mark.asyncio
async def test_get_balance_not_found():
    """get_balance for non-existent account → ValueError."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as session:
        with pytest.raises(ValueError, match="not found"):
            await get_balance(9999, session)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.mark.asyncio
async def test_safe_transfer_with_begin_commits():
    """safe_transfer_with_begin opens own session + commits — test via separate read."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as setup_session:
        setup_session.add_all([
            Account(id=10, owner="Charlie", balance=300.0),
            Account(id=11, owner="Diana",   balance=100.0),
        ])
        await setup_session.commit()

    await safe_transfer_with_begin(10, 11, 150.0)

    async with AsyncSessionLocal() as verify_session:
        charlie = await get_balance(10, verify_session)
        diana   = await get_balance(11, verify_session)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    assert charlie == 150.0, f"FAIL: Charlie should have 150. Got {charlie}"
    assert diana   == 250.0, f"FAIL: Diana should have 250. Got {diana}"


@pytest.mark.asyncio
async def test_rollback_on_exception(db_session: AsyncSession, seeded_accounts):
    """
    If transfer raises mid-way, the transaction rolls back.
    Balances stay at starting values.
    """
    class BoomError(Exception):
        pass

    class BoomTransfer:
        """Debit Alice but then crash — simulates mid-tx failure."""
        @staticmethod
        async def boom(from_id, to_id, amount, session):
            stmt = select(Account).where(Account.id == from_id).with_for_update()
            result = await session.execute(stmt)
            acc = result.scalar_one()
            acc.balance -= amount
            raise BoomError("boom mid-tx")

    try:
        async with db_session.begin():
            await BoomTransfer.boom(1, 2, 300.0, db_session)
    except BoomError:
        pass  # expected

    alice_bal = await get_balance(1, db_session)
    assert alice_bal == 1000.0, (
        f"FAIL: Rollback should restore Alice's balance to 1000. Got {alice_bal}"
    )


# ════════════════════════════════════════════════════════════════════════════
# SOCH (Answer ALOUD before moving to Lab 08)
# ════════════════════════════════════════════════════════════════════════════
"""
SOCH:

Q1: select_for_update() kyon zaroori hai concurrent transfers mein?
    Bina uske kya race condition hogi? Example deke explain karo.

Q2: `async with session.begin()` ka kya matlab hai?
    Exception aane pe kya automatically hota hai?

Q3: "Lost update" problem kya hota hai? Kab hota hai?
    select_for_update use karne ke baad kyon fix hota hai?

Q4: SQLite mein select_for_update ka actual effect kya hai?
    (SQLite file-level lock; Postgres mein row-level lock — different behavior)

Q5: Deadlock kab hota hai transactions mein? Prevent karne ke liye kya karte hain?
    (Always acquire locks in same ORDER: lower id first)
"""
