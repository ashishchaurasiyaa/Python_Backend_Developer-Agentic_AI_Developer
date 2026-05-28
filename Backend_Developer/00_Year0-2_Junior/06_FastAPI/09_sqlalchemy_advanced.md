# FastAPI — SQLAlchemy Advanced

## Quick Concepts
- **N+1 Problem** = 1 query list ke liye + N queries har item ke relation ke liye
- **`selectinload`** = 2nd SELECT...WHERE IN (...) query — best for collections
- **`joinedload`** = LEFT OUTER JOIN — best for single object relations
- **`lazy="noload"`** = relation access karne pe error — force explicit loading
- **Soft Delete** = `deleted_at` set karo, physically delete mat karo
- **`session.begin()`** = explicit transaction block
- **Savepoint** = nested transaction — partial rollback
- **Bulk insert** = `insert(Model)` statement — 10-100x faster than loop

---

## Interview Questions & Answers

### Q1: N+1 problem kya hai? SQLAlchemy mein kaise fix karte hain?

**Answer:**
```python
from sqlalchemy.orm import selectinload, joinedload

# ─── BAD — N+1 problem ───
users = await session.execute(select(User))
for user in users.scalars():
    # EACH user ke liye alag query! 100 users = 101 queries
    posts = await session.execute(select(Post).where(Post.user_id == user.id))

# ─── GOOD — selectinload (2 queries total) ───
# Query 1: SELECT * FROM users
# Query 2: SELECT * FROM posts WHERE user_id IN (1, 2, 3, ...)
result = await session.execute(
    select(User).options(selectinload(User.posts))
)
users = result.scalars().all()
for user in users:
    print(user.posts)  # no extra query — already loaded

# ─── GOOD — joinedload (1 query with LEFT JOIN) ───
# Use for ForeignKey/ManyToOne (single related object)
# Use for: post.author, comment.post (not collections)
result = await session.execute(
    select(Post).options(joinedload(Post.author))
)
posts = result.scalars().unique().all()  # unique() needed with joinedload

# ─── INTERVIEW: selectinload vs joinedload kab use karo? ───
# selectinload → One-to-many, Many-to-many (collections)
#   user.posts, post.tags, order.items
# joinedload   → Many-to-one, One-to-one (single object)
#   post.author, comment.user, order.shipping_address

# ─── Nested eager loading ───
result = await session.execute(
    select(User).options(
        selectinload(User.posts).selectinload(Post.tags),  # nested
        selectinload(User.posts).joinedload(Post.category),
    )
)
```

---

### Q2: Soft Delete kaise implement karte hain SQLAlchemy mein?

**Answer:**
```python
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import DateTime, event
from datetime import datetime, timezone

class SoftDeleteMixin:
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None, index=True
    )

    def soft_delete(self):
        self.deleted_at = datetime.now(timezone.utc)

    def restore(self):
        self.deleted_at = None

    @property
    def is_deleted(self) -> bool:
        return self.deleted_at is not None

class Post(SoftDeleteMixin, Base):
    __tablename__ = "posts"
    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str]

# ─── Repository — always filter deleted ───
class PostRepository:
    async def get_active(self, session: AsyncSession) -> list[Post]:
        result = await session.execute(
            select(Post).where(Post.deleted_at.is_(None))  # NOT NULL check
        )
        return result.scalars().all()

    async def delete(self, session: AsyncSession, post_id: int):
        post = await session.get(Post, post_id)
        if post:
            post.soft_delete()
            await session.flush()  # write to DB (still in transaction)

    async def get_including_deleted(self, session):
        result = await session.execute(select(Post))  # no filter
        return result.scalars().all()

# ─── INTERVIEW: Soft delete ke cons? ───
# 1. DB rows grow forever → need archival/cleanup job
# 2. UNIQUE constraints break (email reuse after delete)
#    Fix: partial unique index WHERE deleted_at IS NULL
# 3. All queries must filter — easy to forget
#    Fix: SQLAlchemy event listener (filter_by_default)
```

---

### Q3: Transactions — `session.begin()` aur savepoints kaise use karte hain?

**Answer:**
```python
from sqlalchemy.ext.asyncio import AsyncSession

# ─── Explicit transaction ───
async def transfer_credits(session: AsyncSession, from_id: int, to_id: int, amount: float):
    async with session.begin():  # commits on exit, rollbacks on exception
        sender   = await session.get(User, from_id)
        receiver = await session.get(User, to_id)

        if sender.credits < amount:
            raise ValueError("Insufficient credits")

        sender.credits   -= amount
        receiver.credits += amount
        # auto-commit when `async with session.begin()` exits normally

# ─── Savepoint (nested transaction) ───
async def create_order_with_optional_log(session, user, items):
    async with session.begin():
        order = Order(user_id=user.id)
        session.add(order)
        await session.flush()  # get order.id without committing

        try:
            async with session.begin_nested():  # SAVEPOINT
                log_entry = AuditLog(action="order_created", user_id=user.id)
                session.add(log_entry)
                # If logging fails → only savepoint rolls back
                # Main transaction (order) still proceeds
        except Exception:
            pass  # log fail → ok, order still saves

        await session.commit()

# ─── INTERVIEW: session.flush() vs session.commit()? ───
# flush():  SQL write karo DB ko, but transaction still open
#   → get auto-generated IDs (like order.id)
#   → can still rollback
# commit(): transaction close karo, permanent change
```

---

### Q4: Bulk operations — `bulk_create`, `bulk_update` kaise karte hain?

**Answer:**
```python
from sqlalchemy import insert, update, select
from sqlalchemy.dialects.postgresql import insert as pg_insert

# ─── Bulk Insert (10-100x faster than loop) ───
async def bulk_insert_users(session: AsyncSession, users_data: list[dict]):
    # BAD — loop (N INSERT statements)
    # for data in users_data:
    #     session.add(User(**data))

    # GOOD — single INSERT with multiple VALUES
    await session.execute(
        insert(User),
        users_data  # list of dicts
    )
    await session.commit()

# ─── Bulk Update ───
async def bulk_update_prices(session: AsyncSession, updates: list[dict]):
    # updates = [{"id": 1, "price": 99.99}, {"id": 2, "price": 149.99}]
    await session.execute(
        update(Product),
        updates  # SQLAlchemy maps to UPDATE...WHERE id = :id
    )
    await session.commit()

# ─── Upsert (INSERT ... ON CONFLICT DO UPDATE) ───
async def upsert_user(session: AsyncSession, email: str, name: str):
    stmt = pg_insert(User).values(email=email, name=name)
    stmt = stmt.on_conflict_do_update(
        index_elements=["email"],           # UNIQUE column
        set_={"name": stmt.excluded.name}   # update on conflict
    )
    await session.execute(stmt)
    await session.commit()

# ─── Bulk Insert with RETURNING (get inserted IDs) ───
async def bulk_insert_return_ids(session, items_data):
    result = await session.execute(
        insert(Item).returning(Item.id, Item.created_at),
        items_data,
    )
    return result.fetchall()  # [(id, created_at), ...]
```

---

### Q5: SQLAlchemy relationship types — `Mapped` with FK?

**Answer:**
```python
from sqlalchemy.orm import relationship, Mapped, mapped_column
from sqlalchemy import ForeignKey
from typing import Optional

class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str]

    # One-to-Many: user has many posts
    posts: Mapped[list["Post"]] = relationship(
        back_populates="author",
        lazy="noload",  # never auto-load — must use selectinload
        cascade="all, delete-orphan",  # delete posts when user deleted
    )

class Post(Base):
    __tablename__ = "posts"
    id:        Mapped[int] = mapped_column(primary_key=True)
    title:     Mapped[str]
    user_id:   Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)

    # Many-to-One: post belongs to one user
    author: Mapped["User"] = relationship(back_populates="posts", lazy="noload")

    # Many-to-Many: post has many tags
    tags: Mapped[list["Tag"]] = relationship(
        secondary="post_tags",  # association table
        lazy="noload",
    )

# Association table (Many-to-Many)
post_tags = Table(
    "post_tags",
    Base.metadata,
    Column("post_id", ForeignKey("posts.id"), primary_key=True),
    Column("tag_id",  ForeignKey("tags.id"),  primary_key=True),
)

# INTERVIEW: lazy="noload" kyu use karte hain?
# Default lazy="select" → accessing post.author triggers implicit query
# In async context ye fail hota hai (MissingGreenlet error)
# lazy="noload" → force explicit loading via options(selectinload/joinedload)
# lazy="raise"  → raise error if accidentally accessed without eager loading
```

---

### Q6: Raw SQL aur `text()` kab use karte hain?

**Answer:**
```python
from sqlalchemy import text

# ─── text() — parameterized raw SQL ───
async def get_post_stats(session: AsyncSession, min_views: int):
    result = await session.execute(
        text("""
            SELECT
                p.id,
                p.title,
                COUNT(c.id) AS comment_count,
                SUM(c.is_approved::int) AS approved_count
            FROM posts p
            LEFT JOIN comments c ON c.post_id = p.id
            WHERE p.views_count >= :min_views
              AND p.deleted_at IS NULL
            GROUP BY p.id
            ORDER BY comment_count DESC
            LIMIT 20
        """),
        {"min_views": min_views},  # ALWAYS parameterize — never f-string!
    )
    return result.mappings().all()  # list of dict-like rows

# ─── INTERVIEW: text() kab use karo? ───
# - Complex SQL (window functions, CTEs, EXPLAIN ANALYZE)
# - DB-specific functions (PostgreSQL full-text, JSON ops, array ops)
# - Performance-critical queries after ORM fails to optimize
# - NEVER: f"WHERE id = {user_id}" → SQL injection!
```

---

## Summary: Eager Loading Decision Tree

```
Relationship type?
├── ForeignKey / ManyToOne (single object: post.author)
│   └── joinedload()  → 1 query with LEFT JOIN
│
└── OneToMany / ManyToMany (collection: user.posts, post.tags)
    └── selectinload() → 2 queries (SELECT...IN)

Need nested?
  .options(selectinload(User.posts).selectinload(Post.tags))

Lazy loading default?
  lazy="noload"   → always explicit (recommended async)
  lazy="select"   → implicit query (sync only, avoid in async)
  lazy="raise"    → error if not explicitly loaded (strictest)
```
