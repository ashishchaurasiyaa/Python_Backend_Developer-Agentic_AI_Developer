"""
SQLAlchemy Async — Practical Examples
═══════════════════════════════════════════════════════════════
Run: python 04_sqlalchemy_async_practical.py
Install: pip install sqlalchemy[asyncio] asyncpg

Prerequisites:
  docker run -d -p 5432:5432 -e POSTGRES_PASSWORD=postgres postgres:16

Topics:
  - Async engine + session setup
  - Models with relationships
  - SoftDelete pattern
  - select_related equivalent (joinedload/selectinload)
  - N+1 prevention
  - Transactions (begin, begin_nested savepoints)
  - Bulk insert / upsert (ON CONFLICT)
  - Raw SQL with text()
  - Repository pattern

INTERVIEW QUICK REFERENCE at bottom.
"""

import asyncio
import random
import string
from datetime import datetime, timezone
from typing import Optional, List

from sqlalchemy import (
    Column, Integer, String, Text, Boolean, Decimal,
    DateTime, ForeignKey, Table, select, func, update, delete, insert, text,
)
from sqlalchemy.orm import (
    DeclarativeBase, Mapped, mapped_column, relationship,
    selectinload, joinedload, contains_eager,
)
from sqlalchemy.ext.asyncio import (
    create_async_engine, AsyncSession, async_sessionmaker,
)
from sqlalchemy.dialects.postgresql import insert as pg_insert

DB_URL = "postgresql+asyncpg://postgres:postgres@localhost:5432/sqlalchemy_demo"


# ═══════════════════════════════════════════════════════════
# MODELS
# ═══════════════════════════════════════════════════════════

class Base(DeclarativeBase):
    pass


# ─── Mixin for soft delete ───
class SoftDeleteMixin:
    """
    INTERVIEW: Soft delete kyu?
    Hard delete pe data gone — audit trail, recovery impossible.
    Soft delete: deleted_at timestamp → filter in queries.
    """
    deleted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )

    def soft_delete(self):
        self.deleted_at = datetime.now(timezone.utc)

    def restore(self):
        self.deleted_at = None

    @property
    def is_deleted(self) -> bool:
        return self.deleted_at is not None


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


# ─── Association table (M2M) ───
post_tags = Table(
    "post_tags",
    Base.metadata,
    Column("post_id", Integer, ForeignKey("posts.id"), primary_key=True),
    Column("tag_id",  Integer, ForeignKey("tags.id"),  primary_key=True),
)


class User(SoftDeleteMixin, TimestampMixin, Base):
    __tablename__ = "users"

    id      : Mapped[int]           = mapped_column(primary_key=True)
    email   : Mapped[str]           = mapped_column(String(255), unique=True, index=True)
    name    : Mapped[str]           = mapped_column(String(100))
    plan    : Mapped[str]           = mapped_column(String(20), default="free", index=True)
    credits : Mapped[int]           = mapped_column(default=0)

    posts   : Mapped[List["Post"]]  = relationship("Post", back_populates="author", lazy="noload")

    def __repr__(self):
        return f"<User {self.email}>"


class Tag(Base):
    __tablename__ = "tags"

    id   : Mapped[int] = mapped_column(primary_key=True)
    name : Mapped[str] = mapped_column(String(50), unique=True)

    posts: Mapped[List["Post"]] = relationship("Post", secondary=post_tags, back_populates="tags", lazy="noload")


class Post(SoftDeleteMixin, TimestampMixin, Base):
    __tablename__ = "posts"

    id          : Mapped[int]           = mapped_column(primary_key=True)
    title       : Mapped[str]           = mapped_column(String(200), index=True)
    content     : Mapped[str]           = mapped_column(Text)
    status      : Mapped[str]           = mapped_column(String(20), default="draft", index=True)
    views_count : Mapped[int]           = mapped_column(default=0)
    likes_count : Mapped[int]           = mapped_column(default=0)
    author_id   : Mapped[int]           = mapped_column(ForeignKey("users.id"), index=True)

    author  : Mapped["User"]        = relationship("User", back_populates="posts", lazy="noload")
    tags    : Mapped[List["Tag"]]   = relationship("Tag", secondary=post_tags, back_populates="posts", lazy="noload")
    comments: Mapped[List["Comment"]] = relationship("Comment", back_populates="post", lazy="noload")


class Comment(SoftDeleteMixin, TimestampMixin, Base):
    __tablename__ = "comments"

    id      : Mapped[int] = mapped_column(primary_key=True)
    content : Mapped[str] = mapped_column(Text)
    post_id : Mapped[int] = mapped_column(ForeignKey("posts.id"), index=True)
    user_id : Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)

    post : Mapped["Post"] = relationship("Post", back_populates="comments", lazy="noload")
    user : Mapped["User"] = relationship("User", lazy="noload")


# ═══════════════════════════════════════════════════════════
# ENGINE + SESSION SETUP
# ═══════════════════════════════════════════════════════════

def make_engine():
    """
    INTERVIEW: echo=True kya karta hai?
    SQL statements ko log karta hai — debug ke liye useful.
    Production mein echo=False.

    pool_pre_ping=True: stale connections detect karta hai.
    """
    return create_async_engine(
        DB_URL,
        echo=False,        # True = log all SQL
        pool_size=10,
        max_overflow=5,
        pool_pre_ping=True,
    )


engine = make_engine()

# session_maker factory — DI container mein register karo
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,   # INTERVIEW: expire_on_commit=False kyu?
    # Default True: commit ke baad attributes expire → lazy load triggers
    # False: committed objects ka data access karo without re-query
)


async def get_session():
    """Dependency / context manager for a single request."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


# ═══════════════════════════════════════════════════════════
# SECTION 1: CRUD Operations
# ═══════════════════════════════════════════════════════════

async def demo_crud(session: AsyncSession):
    print("\n--- CRUD OPERATIONS ---")

    # ─── Create ───
    user1 = User(email="alice@test.com", name="Alice", plan="premium", credits=500)
    user2 = User(email="bob@test.com",   name="Bob",   plan="free",    credits=100)
    session.add_all([user1, user2])
    await session.flush()  # assigns IDs without commit

    tag_py  = Tag(name="python")
    tag_api = Tag(name="api")
    session.add_all([tag_py, tag_api])
    await session.flush()

    post = Post(
        title="FastAPI Best Practices",
        content="Use dependency injection for clean code...",
        status="published",
        author_id=user1.id,
        tags=[tag_py, tag_api],
    )
    session.add(post)
    await session.commit()

    print(f"  Created: user={user1.id}, post={post.id}, tags={[t.name for t in [tag_py, tag_api]]}")

    # ─── Read ───
    stmt = select(User).where(User.email == "alice@test.com")
    result = await session.execute(stmt)
    alice = result.scalar_one()
    print(f"  Read: {alice.name} (plan={alice.plan}, credits={alice.credits})")

    # ─── Update ───
    alice.credits += 100
    await session.commit()
    print(f"  Updated credits: {alice.credits}")

    # ─── Soft Delete ───
    alice.soft_delete()
    await session.commit()
    print(f"  Soft deleted: deleted_at={alice.deleted_at}")

    # Active users only
    stmt = select(User).where(User.deleted_at.is_(None))
    result = await session.execute(stmt)
    active = result.scalars().all()
    print(f"  Active users (alice excluded): {[u.name for u in active]}")

    # ─── Restore ───
    alice.restore()
    await session.commit()
    print(f"  Restored: deleted_at={alice.deleted_at}")

    return user1, user2, post


# ═══════════════════════════════════════════════════════════
# SECTION 2: N+1 Prevention (selectinload vs joinedload)
# ═══════════════════════════════════════════════════════════

async def demo_eager_loading(session: AsyncSession):
    print("\n--- EAGER LOADING (selectinload vs joinedload) ---")
    """
    INTERVIEW: N+1 problem kya hai?
    1 query for posts + N queries for each post's author = N+1 total.
    Solution: eager load relationships.

    selectinload:  SELECT ... WHERE post_id IN (1,2,3,4,5) — 2 queries total
    joinedload:    LEFT OUTER JOIN — 1 query, duplicates in rows

    INTERVIEW: kab kaunsa?
    selectinload:  to-many (many rows in child) — avoids cartesian explosion
    joinedload:    to-one (author, category) — single JOIN is fine
    """

    # Create some posts for demo
    result = await session.execute(select(User).where(User.email == "alice@test.com"))
    alice = result.scalar_one_or_none()
    if not alice:
        return

    # Add more posts
    for i in range(3):
        p = Post(title=f"Post {i}", content=f"Content {i}", status="published", author_id=alice.id)
        session.add(p)
    await session.commit()

    # ─── BAD: N+1 — DON'T do this ───
    print("  [BAD] N+1 pattern — never do this:")
    result = await session.execute(select(Post).where(Post.deleted_at.is_(None)))
    posts = result.scalars().all()
    # This would trigger separate query per post:
    # for post in posts:
    #     author_name = post.author.name  ← lazy load = extra query!
    print(f"    Got {len(posts)} posts (accessing author would trigger N more queries)")

    # ─── GOOD: selectinload for to-many ───
    print("  [GOOD] selectinload (to-many — comments):")
    result = await session.execute(
        select(Post)
        .options(selectinload(Post.comments))  # 2 queries: posts + WHERE post_id IN (...)
        .options(joinedload(Post.author))      # JOIN for to-one author
        .where(Post.deleted_at.is_(None))
    )
    posts = result.unique().scalars().all()
    print(f"    Loaded {len(posts)} posts with author + comments (2 queries total)")

    # ─── GOOD: selectinload for M2M tags ───
    result = await session.execute(
        select(Post)
        .options(
            selectinload(Post.tags),
            selectinload(Post.author),
        )
        .where(Post.status == "published")
        .limit(3)
    )
    posts = result.unique().scalars().all()
    for post in posts:
        tag_names = [t.name for t in post.tags]
        print(f"    Post '{post.title[:30]}' by {post.author.name} — tags: {tag_names}")


# ═══════════════════════════════════════════════════════════
# SECTION 3: Transactions + Savepoints
# ═══════════════════════════════════════════════════════════

async def demo_transactions(session: AsyncSession):
    print("\n--- TRANSACTIONS + SAVEPOINTS ---")
    """
    INTERVIEW: Transaction kab use karte hain?
    Multiple related writes — all succeed or all rollback.
    e.g., credit transfer: debit one user + credit another = atomic.

    Savepoints (begin_nested):
    Partial rollback without killing whole transaction.
    e.g., try risky operation, rollback savepoint on fail, continue outer txn.
    """

    result = await session.execute(select(User).where(User.email.in_(["alice@test.com", "bob@test.com"])))
    users = {u.email: u for u in result.scalars().all()}
    alice = users.get("alice@test.com")
    bob   = users.get("bob@test.com")

    if not alice or not bob:
        print("  Users not found — run CRUD demo first")
        return

    print(f"  Before transfer: alice={alice.credits}, bob={bob.credits}")

    # ─── Atomic credit transfer ───
    try:
        async with session.begin_nested():  # savepoint
            if alice.credits < 50:
                raise ValueError("Insufficient credits")
            alice.credits -= 50
            bob.credits   += 50
            print(f"  Transfer 50 credits: alice → bob")

    except ValueError as e:
        print(f"  Transfer failed (savepoint rolled back): {e}")

    await session.commit()
    print(f"  After transfer: alice={alice.credits}, bob={bob.credits}")

    # ─── Savepoint demo — partial rollback ───
    print("\n  Savepoint demo (partial rollback):")
    async with session.begin_nested() as savepoint:  # outer savepoint
        alice.credits -= 10  # this should persist

        try:
            async with session.begin_nested():       # inner savepoint
                alice.credits -= 1000               # risky!
                raise Exception("Something failed")  # triggers inner rollback
        except Exception:
            print(f"    Inner operation failed, rolled back savepoint — alice still has {alice.credits}")

    await session.commit()

    # Refresh to get DB values
    await session.refresh(alice)
    print(f"  Final alice credits: {alice.credits} (outer -10 persisted, inner -1000 rolled back)")


# ═══════════════════════════════════════════════════════════
# SECTION 4: Bulk Insert + Upsert
# ═══════════════════════════════════════════════════════════

async def demo_bulk_operations(session: AsyncSession):
    print("\n--- BULK INSERT + UPSERT ---")
    """
    INTERVIEW: Bulk insert kaise karte hain?
    session.add() in loop = N queries → SLOW
    Better: insert() with executemany or bulk insert

    Upsert (ON CONFLICT):
    Insert if not exists, update if exists — atomic.
    Use case: sync external data, idempotent writes.
    """

    # ─── Bulk insert tags ───
    new_tags = [
        {"name": f"tag-{i}"}
        for i in range(5)
        if f"tag-{i}" not in ("python", "api")
    ]

    if new_tags:
        # Method 1: insert with ON CONFLICT DO NOTHING (PostgreSQL)
        stmt = pg_insert(Tag).values(new_tags).on_conflict_do_nothing(index_elements=["name"])
        await session.execute(stmt)
        await session.commit()
        print(f"  Bulk inserted {len(new_tags)} tags (with ON CONFLICT DO NOTHING)")

    # ─── Upsert — insert or update ───
    users_data = [
        {"email": "charlie@test.com", "name": "Charlie", "plan": "free",    "credits": 0},
        {"email": "diana@test.com",   "name": "Diana",   "plan": "premium", "credits": 200},
        {"email": "alice@test.com",   "name": "Alice Updated", "plan": "premium", "credits": 999},
    ]

    stmt = pg_insert(User).values(users_data)
    stmt = stmt.on_conflict_do_update(
        index_elements=["email"],
        set_={
            "name":    stmt.excluded.name,
            "plan":    stmt.excluded.plan,
            "credits": stmt.excluded.credits,
        }
    )
    await session.execute(stmt)
    await session.commit()
    print(f"  Upsert {len(users_data)} users (insert new + update existing alice)")

    # Verify
    result = await session.execute(
        select(User.email, User.name, User.credits)
        .where(User.email.in_(["alice@test.com", "charlie@test.com", "diana@test.com"]))
    )
    for row in result.all():
        print(f"    {row.email}: {row.name}, credits={row.credits}")

    # ─── Bulk update ───
    await session.execute(
        update(User)
        .where(User.plan == "free")
        .values(credits=func.coalesce(User.credits, 0) + 10)  # +10 credits to all free users
    )
    await session.commit()
    print("  Bulk update: +10 credits to all free users")

    # ─── Bulk delete (soft) ───
    await session.execute(
        update(Post)
        .where(Post.status == "draft")
        .values(deleted_at=datetime.now(timezone.utc))
    )
    await session.commit()
    print("  Bulk soft delete: all draft posts archived")


# ═══════════════════════════════════════════════════════════
# SECTION 5: Raw SQL with text()
# ═══════════════════════════════════════════════════════════

async def demo_raw_sql(session: AsyncSession):
    print("\n--- RAW SQL with text() ---")
    """
    INTERVIEW: Raw SQL kab use karte hain?
    Complex window functions, CTEs, EXPLAIN, custom PostgreSQL features
    that SQLAlchemy ORM doesn't support natively.

    IMPORTANT: always use :param binding — never f-string/format (SQL injection!)
    """

    # ─── Window function — top author by posts ───
    result = await session.execute(text("""
        SELECT
            u.name,
            u.email,
            COUNT(p.id) AS post_count,
            RANK() OVER (ORDER BY COUNT(p.id) DESC) AS author_rank
        FROM users u
        LEFT JOIN posts p ON p.author_id = u.id AND p.deleted_at IS NULL
        WHERE u.deleted_at IS NULL
        GROUP BY u.id, u.name, u.email
        ORDER BY post_count DESC
        LIMIT 5
    """))

    print("  Author rankings by post count:")
    for row in result.mappings().all():
        print(f"    #{row['author_rank']} {row['name']} ({row['post_count']} posts)")

    # ─── CTE ───
    result = await session.execute(text("""
        WITH user_stats AS (
            SELECT
                u.id,
                u.name,
                u.plan,
                u.credits,
                COUNT(p.id) AS total_posts
            FROM users u
            LEFT JOIN posts p ON p.author_id = u.id AND p.deleted_at IS NULL
            WHERE u.deleted_at IS NULL
            GROUP BY u.id, u.name, u.plan, u.credits
        )
        SELECT * FROM user_stats WHERE credits > :min_credits ORDER BY total_posts DESC
    """), {"min_credits": 0})

    print("\n  User stats CTE (credits > 0):")
    for row in result.mappings().all():
        print(f"    {row['name']} | plan={row['plan']} credits={row['credits']} posts={row['total_posts']}")

    # ─── EXPLAIN ANALYZE ───
    plan = await session.execute(text("""
        EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT)
        SELECT u.name, COUNT(p.id) as posts
        FROM users u
        LEFT JOIN posts p ON p.author_id = u.id
        WHERE u.deleted_at IS NULL
        GROUP BY u.id, u.name
    """))
    lines = [row[0] for row in plan.all()]
    print("\n  EXPLAIN ANALYZE (first 6 lines):")
    for line in lines[:6]:
        print(f"    {line}")


# ═══════════════════════════════════════════════════════════
# SECTION 6: Repository Pattern
# ═══════════════════════════════════════════════════════════

class UserRepository:
    """
    INTERVIEW: Repository pattern kyu?
    - Business logic aur database queries separate karo
    - Testing mein mock karna easy
    - Query logic ek jagah — reusable

    FastAPI mein: Depends(get_session) se session inject karo
    """

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, user_id: int) -> Optional[User]:
        result = await self.session.execute(
            select(User).where(User.id == user_id, User.deleted_at.is_(None))
        )
        return result.scalar_one_or_none()

    async def get_by_email(self, email: str) -> Optional[User]:
        result = await self.session.execute(
            select(User).where(User.email == email, User.deleted_at.is_(None))
        )
        return result.scalar_one_or_none()

    async def get_all_active(self, plan: Optional[str] = None) -> List[User]:
        stmt = select(User).where(User.deleted_at.is_(None))
        if plan:
            stmt = stmt.where(User.plan == plan)
        result = await self.session.execute(stmt.order_by(User.created_at.desc()))
        return list(result.scalars().all())

    async def create(self, email: str, name: str, plan: str = "free") -> User:
        user = User(email=email, name=name, plan=plan)
        self.session.add(user)
        await self.session.flush()
        return user

    async def update_credits(self, user_id: int, delta: int) -> Optional[User]:
        """Atomic credit update using UPDATE ... RETURNING."""
        result = await self.session.execute(
            update(User)
            .where(User.id == user_id, User.deleted_at.is_(None))
            .values(credits=User.credits + delta)
            .returning(User)
        )
        user = result.scalar_one_or_none()
        return user

    async def soft_delete(self, user_id: int) -> bool:
        result = await self.session.execute(
            update(User)
            .where(User.id == user_id, User.deleted_at.is_(None))
            .values(deleted_at=datetime.now(timezone.utc))
        )
        return result.rowcount > 0

    async def get_with_posts(self, user_id: int) -> Optional[User]:
        result = await self.session.execute(
            select(User)
            .options(selectinload(User.posts).selectinload(Post.tags))
            .where(User.id == user_id)
        )
        return result.scalar_one_or_none()

    async def count_by_plan(self) -> dict:
        result = await self.session.execute(
            select(User.plan, func.count(User.id).label("count"))
            .where(User.deleted_at.is_(None))
            .group_by(User.plan)
        )
        return {row.plan: row.count for row in result.all()}


async def demo_repository(session: AsyncSession):
    print("\n--- REPOSITORY PATTERN ---")

    repo = UserRepository(session)

    # get_all_active
    all_users = await repo.get_all_active()
    print(f"  All active users: {[u.name for u in all_users]}")

    # get by plan
    premium_users = await repo.get_all_active(plan="premium")
    print(f"  Premium users: {[u.name for u in premium_users]}")

    # count by plan
    plan_counts = await repo.count_by_plan()
    print(f"  Users by plan: {plan_counts}")

    # update credits
    if all_users:
        user = all_users[0]
        updated = await repo.update_credits(user.id, 50)
        if updated:
            print(f"  Updated {user.name}'s credits: +50")

    await session.commit()


# ═══════════════════════════════════════════════════════════
# SETUP
# ═══════════════════════════════════════════════════════════

async def setup_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    print("✓ Tables created")


# ═══════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════

async def main():
    print("Connecting to PostgreSQL (SQLAlchemy Async)...")
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception as e:
        print(f"Connection failed: {e}")
        print("Start with: docker run -d -p 5432:5432 -e POSTGRES_PASSWORD=postgres postgres:16")
        return

    print("✓ Connected")
    await setup_db()

    async with AsyncSessionLocal() as session:
        user1, user2, post = await demo_crud(session)
        await demo_eager_loading(session)
        await demo_transactions(session)
        await demo_bulk_operations(session)
        await demo_raw_sql(session)
        await demo_repository(session)

    await engine.dispose()
    print("\n✓ All SQLAlchemy async demos complete!")


# ═══════════════════════════════════════════════════════════
# INTERVIEW QUICK REFERENCE
# ═══════════════════════════════════════════════════════════
"""
Q: selectinload vs joinedload kab?
A: joinedload  → to-one (author, category) — single JOIN
   selectinload → to-many (posts, comments, tags) — separate IN query
   joinedload on to-many = cartesian explosion (rows multiply)

Q: lazy="noload" kyu use karo?
A: Async context mein lazy load kaam nahi karta (greenlet error)
   noload = explicitly no lazy load — force eager loading karo
   Default lazy="select" triggers sync lazy load which fails async

Q: expire_on_commit=False kyu?
A: Default True: commit ke baad ORM objects expire → attributes access karo
   to fresh query triggers (N+1 risk, lazy load error in async)
   False: committed values accessible without re-query — safer in async

Q: Soft delete implementation?
A: deleted_at column (nullable timestamp)
   Active: WHERE deleted_at IS NULL
   Soft delete: UPDATE SET deleted_at = NOW()
   Restore: UPDATE SET deleted_at = NULL

Q: Upsert kaise karte hain PostgreSQL mein?
A: pg_insert(Model).values(data)
   .on_conflict_do_update(index_elements=["email"], set_={...})

Q: Bulk insert vs session.add() loop?
A: Loop: N INSERT queries — slow
   Bulk: INSERT with executemany or pg_insert().values([...]) — fast

Q: Transaction vs Savepoint?
A: Transaction (begin):         commit/rollback karo whole thing
   Savepoint (begin_nested):    partial rollback — inner fails, outer continues
   Use savepoints: risky partial operations in larger transaction

Q: Repository pattern kyu?
A: Business logic + DB queries separate → testable, reusable
   Mock repository in tests — no real DB needed
   Single place for query changes
"""

if __name__ == "__main__":
    asyncio.run(main())
