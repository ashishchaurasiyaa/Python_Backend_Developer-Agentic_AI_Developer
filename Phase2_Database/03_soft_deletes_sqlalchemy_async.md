# Soft Deletes, Optimistic Locking, SQLAlchemy 2.0 Async Sessions

## Quick Concepts
- **Soft delete** = `deleted_at` column set karo, actually delete mat karo
- **Read replica** = read queries alag server par, write master par
- **TimescaleDB** = PostgreSQL extension for time-series data
- **SQLAlchemy 2.0** = `select()` style, mapped_column, async sessions

---

## Interview Questions & Answers

### Q1: Soft delete pattern SQLAlchemy mein kaise implement karte hain?
**Answer:**
```python
from sqlalchemy import DateTime, event
from sqlalchemy.orm import Mapped, mapped_column, Session
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime
from typing import Optional

# Mixin approach — sab models mein reuse karo
class SoftDeleteMixin:
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, index=True)

    @property
    def is_deleted(self) -> bool:
        return self.deleted_at is not None

class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        default=datetime.utcnow,
        onupdate=datetime.utcnow
    )

class User(Base, SoftDeleteMixin, TimestampMixin):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    email: Mapped[str] = mapped_column(String(255), unique=True)

# Repository with soft delete
class UserRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_active(self, user_id: int) -> Optional[User]:
        stmt = select(User).where(
            User.id == user_id,
            User.deleted_at.is_(None)   # soft delete filter
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def list_active(self, skip: int = 0, limit: int = 20) -> list[User]:
        stmt = (
            select(User)
            .where(User.deleted_at.is_(None))
            .offset(skip).limit(limit)
        )
        result = await self.db.execute(stmt)
        return result.scalars().all()

    async def soft_delete(self, user_id: int) -> bool:
        result = await self.db.execute(
            update(User)
            .where(User.id == user_id, User.deleted_at.is_(None))
            .values(deleted_at=datetime.utcnow())
        )
        return result.rowcount > 0

    async def restore(self, user_id: int) -> bool:
        result = await self.db.execute(
            update(User)
            .where(User.id == user_id, User.deleted_at.isnot(None))
            .values(deleted_at=None)
        )
        return result.rowcount > 0

    async def hard_delete(self, user_id: int) -> bool:
        result = await self.db.execute(
            delete(User).where(User.id == user_id)
        )
        return result.rowcount > 0

    # Include deleted records
    async def get_with_deleted(self, user_id: int) -> Optional[User]:
        return await self.db.get(User, user_id)
```

---

### Q2: SQLAlchemy 2.0 async — multiple queries efficiently kaise karte hain?
**Answer:**
```python
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload, contains_eager, aliased
from sqlalchemy.ext.asyncio import AsyncSession

# 1. Eager loading — N+1 avoid karo
async def get_user_with_orders(user_id: int, db: AsyncSession) -> Optional[User]:
    stmt = (
        select(User)
        .options(
            selectinload(User.orders).selectinload(Order.items),  # nested eager load
            selectinload(User.profile),
        )
        .where(User.id == user_id, User.deleted_at.is_(None))
    )
    result = await db.execute(stmt)
    return result.unique().scalar_one_or_none()

# 2. Pagination with total count — ek trip mein
async def paginate_users(skip: int, limit: int, db: AsyncSession):
    base_query = select(User).where(User.deleted_at.is_(None))

    # Total count
    count_stmt = select(func.count()).select_from(base_query.subquery())
    total = await db.scalar(count_stmt)

    # Data
    data_stmt = base_query.offset(skip).limit(limit).order_by(User.created_at.desc())
    result = await db.execute(data_stmt)
    users = result.scalars().all()

    return users, total

# 3. Bulk operations
async def bulk_create_users(users_data: list[dict], db: AsyncSession) -> list[User]:
    users = [User(**data) for data in users_data]
    db.add_all(users)
    await db.flush()  # IDs generate karo bina commit ke
    for user in users:
        await db.refresh(user)
    return users

# 4. Upsert (INSERT ... ON CONFLICT)
from sqlalchemy.dialects.postgresql import insert

async def upsert_user(email: str, name: str, db: AsyncSession) -> User:
    stmt = insert(User).values(email=email, name=name)
    stmt = stmt.on_conflict_do_update(
        index_elements=["email"],
        set_={"name": name, "updated_at": datetime.utcnow()}
    ).returning(User)
    result = await db.execute(stmt)
    return result.scalar_one()

# 5. Raw SQL when needed
async def get_user_stats(db: AsyncSession) -> dict:
    result = await db.execute(
        text("""
            SELECT
                COUNT(*) as total,
                COUNT(*) FILTER (WHERE is_active) as active,
                AVG(EXTRACT(YEAR FROM AGE(NOW(), created_at))) as avg_age_years
            FROM users
            WHERE deleted_at IS NULL
        """)
    )
    row = result.fetchone()
    return {"total": row.total, "active": row.active, "avg_age_years": float(row.avg_age_years)}
```

---

### Q3: Read replicas setup kaise karte hain?
**Answer:**
```python
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
import random

# Master (writes)
master_engine = create_async_engine(
    "postgresql+asyncpg://user:pass@master-host:5432/mydb",
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
)

# Replicas (reads) — multiple
replica_engines = [
    create_async_engine(
        f"postgresql+asyncpg://user:pass@replica{i}-host:5432/mydb",
        pool_size=10,
    )
    for i in range(1, 3)   # 2 replicas
]

MasterSession = async_sessionmaker(master_engine, expire_on_commit=False)
ReplicaSession = async_sessionmaker(
    random.choice(replica_engines),   # load balance
    expire_on_commit=False
)

# FastAPI dependencies
async def get_write_db():
    async with MasterSession() as session:
        try:
            yield session
            await session.commit()
        except:
            await session.rollback()
            raise

async def get_read_db():
    async with ReplicaSession() as session:
        yield session

WriteDb = Annotated[AsyncSession, Depends(get_write_db)]
ReadDb = Annotated[AsyncSession, Depends(get_read_db)]

# Usage
@app.get("/users")
async def list_users(db: ReadDb):     # replica se read
    ...

@app.post("/users")
async def create_user(user: UserCreate, db: WriteDb):   # master pe write
    ...
```

---

### Q4: TimescaleDB — time-series data kaise handle karte hain?
**Answer:**
```sql
-- TimescaleDB = PostgreSQL extension
-- Automatic partitioning by time = faster queries

-- Enable extension
CREATE EXTENSION IF NOT EXISTS timescaledb;

-- Regular table banao
CREATE TABLE api_logs (
    id BIGSERIAL,
    timestamp TIMESTAMPTZ NOT NULL,
    endpoint VARCHAR(200),
    method VARCHAR(10),
    status_code INT,
    duration_ms FLOAT,
    user_id INT
);

-- Hypertable banao (time partitioned)
SELECT create_hypertable('api_logs', 'timestamp');

-- Compression enable karo (space save)
ALTER TABLE api_logs SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'endpoint'
);

-- Auto compress 30 days purana data
SELECT add_compression_policy('api_logs', INTERVAL '30 days');

-- Queries automatically fast hain
SELECT
    time_bucket('1 hour', timestamp) as hour,
    endpoint,
    COUNT(*) as requests,
    AVG(duration_ms) as avg_ms,
    PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY duration_ms) as p95_ms
FROM api_logs
WHERE timestamp > NOW() - INTERVAL '24 hours'
GROUP BY 1, 2
ORDER BY 1 DESC;
```

```python
# Python mein insert (asyncpg)
async def log_api_call(endpoint: str, method: str, status: int, duration: float, user_id: int):
    await conn.execute(
        """
        INSERT INTO api_logs (timestamp, endpoint, method, status_code, duration_ms, user_id)
        VALUES (NOW(), $1, $2, $3, $4, $5)
        """,
        endpoint, method, status, duration, user_id
    )
```
