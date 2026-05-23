"""
Day45 — SQLAlchemy 2.0 + Alembic Deep Dive
============================================
Level: Intermediate → Advanced
Target: 5 YOE Python Backend Developer Interview

Topics Covered:
  1.  Core vs ORM — when to use each
  2.  Declarative Base — Base, Column types, relationships
  3.  Models — User, Post, Tag with ManyToMany, __repr__, __tablename__
  4.  Relationships — relationship(), back_populates, lazy vs eager loading
  5.  Session — Session, sessionmaker, context manager pattern
  6.  Queries — legacy query() vs modern 2.0 select()
  7.  Filters — filter(), filter_by(), or_(), and_(), in_(), like()
  8.  Async SQLAlchemy — create_async_engine, AsyncSession
  9.  Alembic — init, env.py, autogenerate, upgrade/downgrade (as comments)
 10.  Patterns — Repository pattern, Unit of Work
 11.  Performance — N+1 problem, eager loading fix, bulk insert
 12.  Transactions — nested transactions, savepoints, rollback on error
"""

# ============================================================
# IMPORTS
# ============================================================
from __future__ import annotations

import logging
from collections.abc import AsyncGenerator, Generator
from contextlib import asynccontextmanager, contextmanager
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Table,
    Text,
    and_,
    create_engine,
    event,
    func,
    or_,
    select,
    text,
)
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    Session,
    joinedload,
    mapped_column,
    relationship,
    selectinload,
    sessionmaker,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ============================================================
# SECTION 1: CORE vs ORM
# ============================================================
"""
SQLAlchemy has two layers:

CORE (lower level):
  - Works with Table objects and raw SQL constructs (select(), insert(), etc.)
  - Returns Row objects (like named tuples)
  - Use when: maximum control, bulk operations, complex raw SQL, performance-
    critical paths, or when you don't need ORM features (relationships, etc.)

ORM (higher level):
  - Works with Python classes mapped to tables
  - Returns full model instances with relationships
  - Use when: you need object-graph navigation, relationship management,
    identity map (same row = same Python object), or event hooks

SQLAlchemy 2.0 unified both layers: you can use select() with both.
"""

# ============================================================
# SECTION 2 & 3: DECLARATIVE BASE + MODELS
# ============================================================

# Modern 2.0 style: use DeclarativeBase class
class Base(DeclarativeBase):
    """All models inherit from this. Provides metadata and registry."""
    pass


# ManyToMany association table (pure Core — no ORM class needed)
post_tags = Table(
    "post_tags",
    Base.metadata,
    Column("post_id", Integer, ForeignKey("posts.id", ondelete="CASCADE"), primary_key=True),
    Column("tag_id", Integer, ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True),
)


class TimestampMixin:
    """Reusable mixin for created_at/updated_at columns."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )


class User(TimestampMixin, Base):
    """
    ORM model for the 'users' table.
    Uses Mapped[] + mapped_column() (SQLAlchemy 2.0 style).
    The older Column() style still works but Mapped[] provides type safety.
    """

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    bio: Mapped[str | None] = mapped_column(Text, nullable=True)

    # One-to-many: one User has many Posts
    posts: Mapped[list[Post]] = relationship(
        "Post",
        back_populates="author",
        cascade="all, delete-orphan",  # deleting user deletes their posts
        lazy="select",  # default: load posts only when accessed (lazy)
    )

    def __repr__(self) -> str:
        return f"<User id={self.id} email={self.email!r}>"

    def __str__(self) -> str:
        return self.name


class Post(TimestampMixin, Base):
    __tablename__ = "posts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    is_published: Mapped[bool] = mapped_column(Boolean, default=False)

    # ForeignKey to users table
    author_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )

    # Many-to-one: Post belongs to User
    author: Mapped[User] = relationship("User", back_populates="posts", lazy="select")

    # Many-to-many: Post has many Tags (via post_tags association table)
    tags: Mapped[list[Tag]] = relationship(
        "Tag",
        secondary=post_tags,
        back_populates="posts",
        lazy="select",
    )

    def __repr__(self) -> str:
        return f"<Post id={self.id} title={self.title!r}>"


class Tag(Base):
    __tablename__ = "tags"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    slug: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)

    # Many-to-many back-reference
    posts: Mapped[list[Post]] = relationship(
        "Post",
        secondary=post_tags,
        back_populates="tags",
        lazy="select",
    )

    def __repr__(self) -> str:
        return f"<Tag name={self.name!r}>"


# ============================================================
# SECTION 4: RELATIONSHIPS — Lazy vs Eager Loading
# ============================================================
"""
LAZY LOADING (lazy="select"):
  - Default. Loads related objects on first access (fires a new SQL query).
  - Simple but causes N+1 problem in loops.

EAGER LOADING:
  - joinedload():   Uses SQL JOIN. Good for Many-to-one (author on Post).
  - selectinload(): Uses a second IN() query. Good for one-to-many (posts on User).
  - subqueryload(): Uses a correlated subquery. Usually worse than selectinload.

RULE OF THUMB:
  - Use joinedload for *-to-one (avoids N+1 with single JOIN).
  - Use selectinload for *-to-many (avoids cartesian explosion from JOINs).
"""

# ============================================================
# SECTION 5: SESSION — sessionmaker, context manager
# ============================================================

# Sync engine (SQLite for demo; swap for postgresql+psycopg2:// in production)
SYNC_DATABASE_URL = "sqlite:///./demo.db"

engine = create_engine(
    SYNC_DATABASE_URL,
    echo=False,          # Set True to log all SQL
    pool_size=10,        # (not applicable to SQLite, but important for Postgres)
    max_overflow=20,
    pool_pre_ping=True,  # Reconnect if connection is stale
)

SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,   # Always use explicit transactions
    autoflush=False,    # Don't flush before every query (control it yourself)
    expire_on_commit=True,  # Attributes expire after commit (safe default)
)


@contextmanager
def get_db_session() -> Generator[Session, None, None]:
    """
    Context manager for sync sessions.
    Guarantees commit on success, rollback on error, and close always.
    """
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def create_all_tables() -> None:
    """Create all tables defined in Base.metadata."""
    Base.metadata.create_all(bind=engine)


def drop_all_tables() -> None:
    """Drop all tables (useful in tests)."""
    Base.metadata.drop_all(bind=engine)


# ============================================================
# SECTION 6 & 7: QUERIES — Legacy vs Modern 2.0 + Filters
# ============================================================

def demo_queries(session: Session) -> None:
    """Demonstrates various query patterns."""

    # --- Modern 2.0 style (preferred) ---

    # SELECT * FROM users WHERE is_active = true
    stmt = select(User).where(User.is_active == True)  # noqa: E712
    users = session.scalars(stmt).all()

    # SELECT * FROM users WHERE email LIKE '%@example.com' ORDER BY name
    stmt = (
        select(User)
        .where(User.email.like("%@example.com"))
        .order_by(User.name)
    )
    users = session.scalars(stmt).all()

    # Filters: or_(), and_(), in_()
    stmt = select(User).where(
        or_(
            User.name == "Alice",
            and_(User.age > 25, User.is_active == True),  # noqa: E712
        )
    )

    stmt = select(User).where(User.id.in_([1, 2, 3]))

    # COUNT
    total = session.scalar(select(func.count()).select_from(User))

    # JOIN: Posts with their authors (eager)
    stmt = (
        select(Post)
        .options(joinedload(Post.author))   # JOIN users ON posts.author_id = users.id
        .where(Post.is_published == True)   # noqa: E712
        .limit(10)
    )
    posts = session.scalars(stmt).unique().all()

    # Aggregation: count posts per user
    stmt = (
        select(User.name, func.count(Post.id).label("post_count"))
        .join(Post, Post.author_id == User.id, isouter=True)
        .group_by(User.id)
        .order_by(func.count(Post.id).desc())
    )
    rows = session.execute(stmt).all()

    # --- Legacy style (still valid but discouraged) ---
    # users = session.query(User).filter(User.is_active == True).all()
    # user = session.query(User).filter_by(email="alice@example.com").first()

    return users


# ============================================================
# SECTION 8: ASYNC SQLALCHEMY
# ============================================================

ASYNC_DATABASE_URL = "sqlite+aiosqlite:///./demo_async.db"
# For PostgreSQL: "postgresql+asyncpg://user:password@localhost/dbname"

async_engine = create_async_engine(
    ASYNC_DATABASE_URL,
    echo=False,
    pool_pre_ping=True,
)

AsyncSessionLocal = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,  # Important for async: don't expire after commit
)


@asynccontextmanager
async def get_async_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Async context manager for database sessions."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def async_create_user(name: str, email: str, hashed_password: str) -> User:
    """Example of async DB operation."""
    async with get_async_db_session() as session:
        user = User(name=name, email=email, hashed_password=hashed_password)
        session.add(user)
        await session.flush()   # Get the auto-generated ID without committing
        await session.refresh(user)  # Reload from DB (populates defaults)
        return user


async def async_get_users_with_posts() -> list[User]:
    """Async query with eager loading using selectinload."""
    async with get_async_db_session() as session:
        stmt = (
            select(User)
            .options(selectinload(User.posts).selectinload(Post.tags))
            .where(User.is_active == True)  # noqa: E712
        )
        result = await session.execute(stmt)
        return result.scalars().unique().all()


async def create_async_tables() -> None:
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


# ============================================================
# SECTION 9: ALEMBIC — Commands and env.py Setup
# ============================================================

"""
=== ALEMBIC WORKFLOW ===

1. INITIALIZE (run once per project):
   $ alembic init alembic
   Creates: alembic/ directory with env.py, script.py.mako, versions/

2. CONFIGURE env.py:
   In alembic/env.py, replace the target_metadata line:

       # Import your models and Base
       from app.models import Base          # <-- your models file
       from app.config import DATABASE_URL  # <-- your sync DB URL

       config.set_main_option("sqlalchemy.url", DATABASE_URL)
       target_metadata = Base.metadata     # <-- tells Alembic what to compare

3. GENERATE MIGRATION (autogenerate):
   $ alembic revision --autogenerate -m "create users posts tags tables"
   Alembic compares current DB schema vs Base.metadata and generates a file
   in alembic/versions/ with upgrade() and downgrade() functions.

4. APPLY MIGRATION:
   $ alembic upgrade head        # Apply all pending migrations
   $ alembic upgrade +1          # Apply next 1 migration
   $ alembic downgrade -1        # Rollback 1 migration
   $ alembic downgrade base      # Rollback all (back to empty DB)

5. CHECK CURRENT STATE:
   $ alembic current             # Show current revision in DB
   $ alembic history             # Show all revisions
   $ alembic show <revision_id>  # Show specific revision

EXAMPLE GENERATED MIGRATION FILE:
---------------------------------
# alembic/versions/abc123_create_users_table.py

from alembic import op
import sqlalchemy as sa

revision = 'abc123'
down_revision = None  # None = first migration
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table(
        'users',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('email', sa.String(255), nullable=False, unique=True),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_users_email', 'users', ['email'])

def downgrade() -> None:
    op.drop_index('ix_users_email', table_name='users')
    op.drop_table('users')

ADDING A COLUMN MIGRATION:
--------------------------
def upgrade() -> None:
    op.add_column('users', sa.Column('bio', sa.Text(), nullable=True))

def downgrade() -> None:
    op.drop_column('users', 'bio')

TIPS:
- Always review autogenerated migrations before running them.
- Autogenerate misses: custom types, stored procedures, partial indexes.
- Use --sql flag for dry run: alembic upgrade head --sql
- In CI: run alembic upgrade head on every deploy.
"""

# ============================================================
# SECTION 10: PATTERNS — Repository + Unit of Work
# ============================================================

class UserRepository:
    """
    Repository pattern: abstracts all User DB operations.
    Dependencies injected (session), making it testable without real DB.
    """

    def __init__(self, session: Session) -> None:
        self.session = session

    def get_by_id(self, user_id: int) -> User | None:
        return self.session.get(User, user_id)

    def get_by_email(self, email: str) -> User | None:
        stmt = select(User).where(User.email == email)
        return self.session.scalar(stmt)

    def list_active(self, limit: int = 50, offset: int = 0) -> list[User]:
        stmt = (
            select(User)
            .where(User.is_active == True)  # noqa: E712
            .order_by(User.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(self.session.scalars(stmt).all())

    def create(self, name: str, email: str, hashed_password: str) -> User:
        user = User(name=name, email=email, hashed_password=hashed_password)
        self.session.add(user)
        self.session.flush()  # Get ID without full commit
        return user

    def deactivate(self, user_id: int) -> bool:
        user = self.get_by_id(user_id)
        if not user:
            return False
        user.is_active = False
        return True

    def delete(self, user_id: int) -> bool:
        user = self.get_by_id(user_id)
        if not user:
            return False
        self.session.delete(user)
        return True


class PostRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_published_posts(self, limit: int = 20) -> list[Post]:
        stmt = (
            select(Post)
            .options(joinedload(Post.author), selectinload(Post.tags))
            .where(Post.is_published == True)  # noqa: E712
            .limit(limit)
        )
        return list(self.session.scalars(stmt).unique().all())

    def create(self, title: str, body: str, author_id: int, tag_names: list[str] | None = None) -> Post:
        post = Post(title=title, body=body, author_id=author_id)
        if tag_names:
            for name in tag_names:
                slug = name.lower().replace(" ", "-")
                # Get or create tag
                stmt = select(Tag).where(Tag.slug == slug)
                tag = self.session.scalar(stmt)
                if not tag:
                    tag = Tag(name=name, slug=slug)
                    self.session.add(tag)
                post.tags.append(tag)
        self.session.add(post)
        self.session.flush()
        return post


class UnitOfWork:
    """
    Unit of Work pattern: groups multiple repository operations into one
    atomic transaction. If any step fails, all changes are rolled back.

    Usage:
        with UnitOfWork() as uow:
            user = uow.users.create("Alice", "alice@example.com", "hash")
            uow.posts.create("Hello", "World", author_id=user.id)
            uow.commit()
    """

    def __init__(self) -> None:
        self.session = SessionLocal()
        self.users = UserRepository(self.session)
        self.posts = PostRepository(self.session)

    def __enter__(self) -> UnitOfWork:
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        if exc_type:
            self.rollback()
        self.session.close()

    def commit(self) -> None:
        self.session.commit()

    def rollback(self) -> None:
        self.session.rollback()


def demo_unit_of_work() -> None:
    """Demo: create user + post in a single atomic transaction."""
    with UnitOfWork() as uow:
        try:
            user = uow.users.create(
                name="Bob",
                email="bob@example.com",
                hashed_password="$2b$12$fakehash",
            )
            post = uow.posts.create(
                title="My First Post",
                body="Hello, world!",
                author_id=user.id,
                tag_names=["Python", "SQLAlchemy"],
            )
            uow.commit()
            logger.info("Created user %r and post %r", user, post)
        except Exception as exc:
            logger.error("Transaction failed: %s", exc)
            raise


# ============================================================
# SECTION 11: PERFORMANCE — N+1 Problem + Bulk Insert
# ============================================================

def demo_n_plus_one_problem(session: Session) -> None:
    """
    N+1 PROBLEM: Loading N posts and then accessing author for each
    fires N additional SELECT queries (1 for posts + N for authors).
    """
    # BAD: N+1 queries
    posts = session.scalars(select(Post)).all()
    for post in posts:
        # Each access to post.author fires a new SELECT!
        logger.info("Author: %s", post.author.name)


def demo_eager_loading_fix(session: Session) -> None:
    """
    FIX: Use joinedload (single SQL JOIN) or selectinload (one extra query).
    Both load all data upfront — no N+1.
    """
    # GOOD: joinedload = single JOIN query
    stmt = select(Post).options(joinedload(Post.author))
    posts = session.scalars(stmt).unique().all()
    for post in posts:
        logger.info("Author: %s", post.author.name)  # No extra query

    # GOOD: selectinload for collections (one-to-many)
    stmt = select(User).options(selectinload(User.posts))
    users = session.scalars(stmt).all()
    for user in users:
        logger.info("Post count: %d", len(user.posts))  # No extra query


def demo_bulk_insert(session: Session) -> None:
    """
    BULK INSERT: add_all() is faster than individual add() in a loop,
    but it's still one INSERT per row. For true bulk, use:
      - session.execute(insert(User), [dict1, dict2, ...])
      - engine.execute() with Core insert()
    """
    # Method 1: add_all() — still uses ORM overhead
    users = [
        User(
            name=f"User{i}",
            email=f"user{i}@example.com",
            hashed_password="$2b$12$fakehash",
        )
        for i in range(1000)
    ]
    session.add_all(users)
    session.commit()
    logger.info("Inserted %d users via add_all()", len(users))

    # Method 2: Core bulk insert (fastest — bypasses ORM)
    from sqlalchemy import insert  # noqa: PLC0415

    rows = [
        {
            "name": f"BulkUser{i}",
            "email": f"bulk{i}@example.com",
            "hashed_password": "$2b$12$fakehash",
            "is_active": True,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        }
        for i in range(5000)
    ]
    session.execute(insert(User), rows)
    session.commit()
    logger.info("Bulk inserted %d users via Core insert()", len(rows))


# ============================================================
# SECTION 12: TRANSACTIONS — Nested, Savepoints, Rollback
# ============================================================

def demo_nested_transaction(session: Session) -> None:
    """
    Savepoints (SAVEPOINT SQL statement) allow partial rollback within a
    transaction. Useful when you want to try something and undo just that
    part if it fails, without rolling back everything.

    SQLAlchemy uses begin_nested() to create a SAVEPOINT.
    """
    with get_db_session() as session:
        user = User(name="Charlie", email="charlie@example.com", hashed_password="hash")
        session.add(user)
        session.flush()

        # Attempt to create a post; if it fails, rollback just the post
        try:
            with session.begin_nested():  # SAVEPOINT
                post = Post(title="Draft", body="...", author_id=user.id)
                session.add(post)
                session.flush()
                # Simulate error
                raise ValueError("Something went wrong with the post")
        except ValueError:
            logger.warning("Post creation failed — rolled back to savepoint")
            # User is still in the transaction, post is not

        # Outer transaction: user will still be committed
        logger.info("User %r will be committed despite post failure", user)


def demo_transaction_rollback(session: Session) -> None:
    """
    Demonstrates explicit rollback on business logic failure.
    Always use try/except/finally or a context manager.
    """
    session = SessionLocal()
    try:
        user = User(name="Dave", email="dave@example.com", hashed_password="hash")
        session.add(user)
        session.flush()

        # Some validation
        if "@" not in user.email:
            raise ValueError("Invalid email")

        session.commit()
        logger.info("User created: %r", user)
    except Exception as exc:
        session.rollback()  # Undo everything since last commit
        logger.error("Rolled back due to: %s", exc)
        raise
    finally:
        session.close()


# ============================================================
# SQLAlchemy EVENTS
# ============================================================

@event.listens_for(User, "before_insert")
def set_timestamps_on_insert(mapper: Any, connection: Any, target: User) -> None:
    """SQLAlchemy event hook: runs before every User INSERT."""
    now = datetime.now(timezone.utc)
    if not target.created_at:
        target.created_at = now
    target.updated_at = now


@event.listens_for(User, "before_update")
def update_timestamp_on_update(mapper: Any, connection: Any, target: User) -> None:
    """SQLAlchemy event hook: auto-update updated_at before every UPDATE."""
    target.updated_at = datetime.now(timezone.utc)


# ============================================================
# DEMO RUNNER
# ============================================================

def run_sync_demo() -> None:
    """Run all sync demo operations."""
    create_all_tables()

    with get_db_session() as session:
        # Create a user
        user = User(
            name="Alice",
            email="alice@example.com",
            hashed_password="$2b$12$fakehash",
        )
        session.add(user)
        session.flush()
        logger.info("Created: %r (id=%d)", user, user.id)

        # Create a post with tags
        tag_python = Tag(name="Python", slug="python")
        tag_sql = Tag(name="SQLAlchemy", slug="sqlalchemy")
        session.add_all([tag_python, tag_sql])
        session.flush()

        post = Post(
            title="Mastering SQLAlchemy",
            body="SQLAlchemy is powerful...",
            author_id=user.id,
            is_published=True,
        )
        post.tags = [tag_python, tag_sql]
        session.add(post)

    # Query with eager loading
    with get_db_session() as session:
        stmt = (
            select(Post)
            .options(joinedload(Post.author), selectinload(Post.tags))
            .where(Post.is_published == True)  # noqa: E712
        )
        posts = session.scalars(stmt).unique().all()
        for p in posts:
            logger.info("Post: %r | Author: %s | Tags: %s", p, p.author.name, [t.name for t in p.tags])


if __name__ == "__main__":
    run_sync_demo()


# ============================================================
# INTERVIEW Q&A (15 Questions)
# ============================================================

"""
=== SQLAlchemy + Alembic Interview Q&A — Senior Level ===

Q1. What is the difference between SQLAlchemy Core and ORM?
A1. Core is a SQL abstraction layer — you work with Table objects and
    SQL expression language (select(), insert()). ORM maps Python classes
    to tables and gives you relationships, identity map, and events.
    ORM is built on top of Core. Use Core for bulk operations or when you
    don't need object-graph navigation; use ORM for domain-driven code.

Q2. What is the N+1 problem and how do you fix it in SQLAlchemy?
A2. N+1: loading 10 posts and accessing post.author fires 10 extra queries
    (one per post). Fix with eager loading:
    - joinedload(Post.author): single JOIN — best for *-to-one
    - selectinload(User.posts): one extra IN() query — best for *-to-many
    Avoid lazy="subquery" (deprecated) and never use lazy loading in loops.

Q3. What is the identity map in SQLAlchemy?
A3. The Session maintains an identity map: a dict of {(type, primary_key): object}.
    If you query the same row twice in the same session, you get the exact
    same Python object (not a copy). This prevents duplicate objects and
    enables change tracking (dirty checking before commit).

Q4. What does expire_on_commit=True do?
A4. After session.commit(), all loaded objects are "expired": their attributes
    are cleared. Next access triggers a fresh SELECT. This prevents serving
    stale data. Set expire_on_commit=False in async code to avoid lazy-load
    errors after the session is closed.

Q5. When would you use session.flush() vs session.commit()?
A5. flush() writes pending changes to the DB in the current transaction
    (so you can get auto-generated IDs) but does NOT commit — the transaction
    is still open. commit() makes changes permanent and releases the transaction.
    Use flush() when you need an ID mid-transaction before the overall commit.

Q6. How do you handle database migrations in production with Alembic?
A6. (1) Generate: alembic revision --autogenerate -m "description"
    (2) Review the generated file for correctness
    (3) Test: alembic upgrade head --sql | review SQL
    (4) Deploy: run alembic upgrade head in CI/CD before starting the app
    (5) On rollback: alembic downgrade -1
    Always keep migration files in version control.

Q7. What is the difference between relationship cascade="all" and "all, delete-orphan"?
A7. cascade="all" propagates save/merge/delete/refresh actions from parent to child.
    "delete-orphan" additionally deletes a child when it's removed from the
    parent's collection (disassociated). Use "all, delete-orphan" for
    owned/contained relationships (e.g., user's addresses).

Q8. How do you implement a many-to-many relationship in SQLAlchemy?
A8. Create an association Table (not class) with two ForeignKey columns and
    pass it to relationship(secondary=...). SQLAlchemy manages the JOIN table
    automatically on add/remove. If you need extra columns on the join table
    (e.g., created_at), use an association object (a full mapped class).

Q9. What is the purpose of back_populates vs backref?
A9. Both set up the reverse side of a relationship. back_populates requires
    explicit declaration on both sides (preferred in 2.0 for clarity).
    backref auto-creates the reverse relationship as a string shorthand.
    Use back_populates for explicitness and type-checker support.

Q10. How does async SQLAlchemy differ from sync?
A10. Use create_async_engine, AsyncSession, async_sessionmaker.
     All DB calls require await: await session.execute(), await session.commit().
     Set expire_on_commit=False (expired attributes would require lazy load,
     which can't be awaited after session closes).
     Use selectinload instead of joinedload for collections (avoids sync joins).

Q11. What is a savepoint and when would you use it?
A11. A savepoint (SAVEPOINT SQL) is a marker within a transaction. You can
     roll back to it without aborting the entire transaction. In SQLAlchemy:
     session.begin_nested(). Use when you want to attempt a risky sub-operation
     and undo just that part on failure (e.g., try sending an email record,
     rollback the email but keep the user creation).

Q12. How does Alembic's autogenerate work?
A12. Alembic compares the current DB schema (inspected via INFORMATION_SCHEMA)
     against Base.metadata (your Python models). It generates a revision file
     with upgrade() and downgrade() functions. It detects new tables, columns,
     indexes, and constraints — but misses stored procedures, custom types,
     and some constraints. Always review before applying.

Q13. What are the pros and cons of using ORM vs raw SQL?
A13. ORM pros: type safety, relationships, auto-escaping (no SQL injection),
     migrations via Alembic, database agnostic, pythonic interface.
     ORM cons: N+1 risk, magic (hard to debug), can generate suboptimal SQL,
     overhead for bulk ops.
     Raw SQL pros: full control, optimal queries, transparent.
     Raw SQL cons: injection risk if not parameterized, maintenance burden.
     Best practice: ORM for CRUD, Core/raw for complex analytics.

Q14. How do you handle connection pooling in SQLAlchemy?
A14. SQLAlchemy has a built-in connection pool (QueuePool by default).
     Key settings: pool_size (base connections), max_overflow (burst),
     pool_timeout (wait before error), pool_recycle (max conn age),
     pool_pre_ping=True (test conn before use — handles stale connections).
     For async, use AsyncAdaptedQueuePool (default with async engines).

Q15. How do you test code that uses SQLAlchemy sessions?
A15. Three approaches:
     (a) In-memory SQLite: create_engine("sqlite:///:memory:"), fast but
         doesn't support all Postgres features.
     (b) Test transaction rollback: wrap each test in a transaction and
         rollback at the end — DB is never modified.
     (c) Mock the session: mock session.scalar(), session.execute(), etc.
         for pure unit tests without any DB.
     For integration tests, use a real Postgres with a separate test database
     and alembic upgrade head before tests.
"""
