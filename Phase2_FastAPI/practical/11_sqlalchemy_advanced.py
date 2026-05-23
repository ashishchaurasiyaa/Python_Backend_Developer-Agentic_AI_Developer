"""
PHASE 2 FastAPI — Practical 11: SQLAlchemy Advanced
Run: uvicorn 11_sqlalchemy_advanced:app --reload
Docs: http://127.0.0.1:8000/docs

Install: pip install sqlalchemy aiosqlite fastapi uvicorn

Topics:
  - N+1 problem — what it is + how to fix
  - selectinload vs joinedload vs subqueryload
  - Explicit transactions — session.begin(), savepoints
  - Bulk insert / bulk update (batch performance)
  - Soft delete pattern — deleted_at + auto-filter mixin
  - SQLAlchemy events — @event.listens_for
  - Raw SQL with text() when ORM is not enough
  - Upsert pattern — insert or update
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Optional, Sequence

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from sqlalchemy import (
    Boolean, DateTime, ForeignKey, Integer, String, Text,
    delete, event, func, insert, select, text, update,
)
from sqlalchemy.ext.asyncio import (
    AsyncSession, async_sessionmaker, create_async_engine,
)
from sqlalchemy.orm import (
    DeclarativeBase, Mapped, MappedColumn,
    mapped_column, relationship,
    joinedload, selectinload, subqueryload,
)

DATABASE_URL = "sqlite+aiosqlite:///./sqlalchemy_advanced.db"

engine = create_async_engine(DATABASE_URL, echo=True, future=True)
AsyncSessionFactory = async_sessionmaker(engine, expire_on_commit=False)


# ═══════════════════════════════════════════════════════
# SECTION 1: Models — with Soft Delete Mixin
# ═══════════════════════════════════════════════════════

class Base(DeclarativeBase):
    pass


class TimestampMixin:
    """Adds created_at + updated_at to every model."""
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class SoftDeleteMixin:
    """
    Soft delete — never actually DELETE rows.
    Set deleted_at timestamp instead.
    Filter with .where(Model.deleted_at.is_(None))
    """
    deleted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None, index=True
    )
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, index=True)

    def soft_delete(self):
        self.deleted_at = datetime.now(timezone.utc)
        self.is_deleted = True

    def restore(self):
        self.deleted_at = None
        self.is_deleted = False


class Author(Base, TimestampMixin):
    __tablename__ = "authors"

    id:    Mapped[int] = mapped_column(Integer, primary_key=True)
    name:  Mapped[str] = mapped_column(String(100))
    email: Mapped[str] = mapped_column(String(255), unique=True)
    bio:   Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # One author → many books
    books: Mapped[list["Book"]] = relationship("Book", back_populates="author", lazy="noload")
    # noload = never auto-load — we control loading explicitly


class Book(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "books"

    id:        Mapped[int] = mapped_column(Integer, primary_key=True)
    title:     Mapped[str] = mapped_column(String(200))
    price:     Mapped[float] = mapped_column(default=0.0)
    published: Mapped[bool] = mapped_column(Boolean, default=False)
    author_id: Mapped[int] = mapped_column(ForeignKey("authors.id"), index=True)

    author: Mapped["Author"] = relationship("Author", back_populates="books", lazy="noload")
    tags:   Mapped[list["Tag"]] = relationship("Tag", secondary="book_tags", lazy="noload")


class Tag(Base):
    __tablename__ = "tags"
    id:   Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(50), unique=True)


# Association table (many-to-many)
from sqlalchemy import Table, Column
book_tags = Table(
    "book_tags", Base.metadata,
    Column("book_id", ForeignKey("books.id"), primary_key=True),
    Column("tag_id",  ForeignKey("tags.id"),  primary_key=True),
)


# ═══════════════════════════════════════════════════════
# SECTION 2: N+1 Problem — Diagnosis + Fix
# ═══════════════════════════════════════════════════════

async def n_plus_1_bad(session: AsyncSession) -> list[dict]:
    """
    BAD — N+1 problem.
    1 query for authors → then 1 query PER author for books.
    10 authors = 11 queries. 1000 authors = 1001 queries!
    """
    authors = (await session.execute(select(Author))).scalars().all()
    result = []
    for author in authors:
        # This triggers a NEW query for each author!
        books = (await session.execute(
            select(Book).where(Book.author_id == author.id)
        )).scalars().all()
        result.append({"author": author.name, "book_count": len(books)})
    return result


async def n_plus_1_fixed_selectinload(session: AsyncSession) -> list[dict]:
    """
    GOOD — selectinload.
    2 queries total regardless of author count:
      Query 1: SELECT * FROM authors
      Query 2: SELECT * FROM books WHERE author_id IN (1, 2, 3, ...)

    Use when: loading collections (one-to-many)
    """
    authors = (await session.execute(
        select(Author).options(selectinload(Author.books))
    )).scalars().all()

    return [
        {"author": a.name, "books": [b.title for b in a.books]}
        for a in authors
    ]


async def n_plus_1_fixed_joinedload(session: AsyncSession) -> list[dict]:
    """
    GOOD — joinedload.
    1 query with LEFT OUTER JOIN:
      SELECT authors.*, books.* FROM authors
      LEFT OUTER JOIN books ON books.author_id = authors.id

    Use when: loading single related object (many-to-one)
    WARNING: Can cause duplicate rows for collections — use selectinload instead.
    """
    books = (await session.execute(
        select(Book)
        .options(joinedload(Book.author))   # load author WITH book in 1 query
        .where(Book.is_deleted.is_(False))
    )).unique().scalars().all()

    return [
        {"book": b.title, "author": b.author.name if b.author else None}
        for b in books
    ]


async def load_with_multiple_relations(session: AsyncSession) -> list[dict]:
    """
    Load books WITH author AND tags simultaneously.
    Still just 3 queries total.
    """
    books = (await session.execute(
        select(Book)
        .options(
            joinedload(Book.author),        # JOIN for single object
            selectinload(Book.tags),        # IN for collection
        )
        .where(Book.is_deleted.is_(False))
    )).unique().scalars().all()

    return [
        {
            "book": b.title,
            "author": b.author.name if b.author else None,
            "tags": [t.name for t in b.tags],
        }
        for b in books
    ]


# ═══════════════════════════════════════════════════════
# SECTION 3: Explicit Transactions
# ═══════════════════════════════════════════════════════

async def transfer_with_transaction(
    session: AsyncSession,
    from_author_id: int,
    to_author_id: int,
    book_id: int,
) -> dict:
    """
    Explicit transaction: move a book from one author to another.
    If ANY step fails, entire transaction rolls back.
    """
    async with session.begin():  # BEGIN TRANSACTION
        # Step 1: verify book exists and belongs to from_author
        book = await session.get(Book, book_id)
        if not book or book.author_id != from_author_id:
            raise ValueError(f"Book {book_id} not found for author {from_author_id}")

        # Step 2: verify target author exists
        to_author = await session.get(Author, to_author_id)
        if not to_author:
            raise ValueError(f"Target author {to_author_id} not found")

        # Step 3: transfer
        book.author_id = to_author_id
        # If exception raised here → session.begin() auto-rolls back

    # Committed here
    return {"book_id": book_id, "new_author_id": to_author_id, "status": "transferred"}


async def bulk_operation_with_savepoint(session: AsyncSession) -> dict:
    """
    Nested transactions using SAVEPOINT.
    Partial rollback without losing outer transaction.
    """
    async with session.begin():  # outer transaction
        # Do some work
        await session.execute(
            update(Author).where(Author.id == 1).values(bio="Updated")
        )

        # Nested savepoint — can rollback just this part
        async with session.begin_nested():  # SAVEPOINT sp1
            try:
                await session.execute(
                    update(Book).where(Book.id == 99999).values(price=999.0)
                )
                # Simulate failure
                # raise ValueError("Something went wrong")
            except Exception:
                pass  # rollback to savepoint sp1, outer tx still active

    return {"status": "outer transaction committed, savepoint may have rolled back"}


# ═══════════════════════════════════════════════════════
# SECTION 4: Bulk Operations (Performance)
# ═══════════════════════════════════════════════════════

async def bulk_insert_books(session: AsyncSession, author_id: int, count: int = 100) -> int:
    """
    Bulk insert — single INSERT with multiple values.
    100x faster than individual session.add() in a loop.
    """
    books_data = [
        {
            "title": f"Book {i}",
            "price": float(i * 10),
            "published": i % 2 == 0,
            "author_id": author_id,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        }
        for i in range(1, count + 1)
    ]

    # Single INSERT ... VALUES (row1), (row2), ... (rowN)
    await session.execute(insert(Book), books_data)
    await session.commit()
    return count


async def bulk_update_prices(session: AsyncSession, author_id: int, discount: float) -> int:
    """
    Bulk UPDATE — single UPDATE statement with WHERE.
    """
    result = await session.execute(
        update(Book)
        .where(Book.author_id == author_id)
        .where(Book.is_deleted.is_(False))
        .values(price=Book.price * (1 - discount))
        .returning(Book.id)  # get updated IDs back
    )
    await session.commit()
    updated_ids = result.scalars().all()
    return len(updated_ids)


async def bulk_delete_soft(session: AsyncSession, author_id: int) -> int:
    """
    Bulk soft delete — mark all books of an author as deleted.
    """
    now = datetime.now(timezone.utc)
    result = await session.execute(
        update(Book)
        .where(Book.author_id == author_id)
        .where(Book.is_deleted.is_(False))
        .values(is_deleted=True, deleted_at=now)
        .returning(Book.id)
    )
    await session.commit()
    return len(result.scalars().all())


# ═══════════════════════════════════════════════════════
# SECTION 5: Soft Delete Pattern
# ═══════════════════════════════════════════════════════

async def get_active_books(session: AsyncSession) -> Sequence[Book]:
    """Always filter out soft-deleted rows."""
    result = await session.execute(
        select(Book)
        .where(Book.is_deleted.is_(False))   # ← always add this!
        .options(joinedload(Book.author))
        .order_by(Book.id)
    )
    return result.unique().scalars().all()


async def soft_delete_book(session: AsyncSession, book_id: int) -> bool:
    """Soft delete a single book."""
    book = await session.get(Book, book_id)
    if not book or book.is_deleted:
        return False
    book.soft_delete()   # uses SoftDeleteMixin method
    await session.commit()
    return True


async def restore_book(session: AsyncSession, book_id: int) -> bool:
    """Restore a soft-deleted book."""
    result = await session.execute(
        select(Book).where(Book.id == book_id)  # no is_deleted filter!
    )
    book = result.scalar_one_or_none()
    if not book or not book.is_deleted:
        return False
    book.restore()
    await session.commit()
    return True


async def list_deleted_books(session: AsyncSession) -> Sequence[Book]:
    """List soft-deleted books (admin view)."""
    result = await session.execute(
        select(Book)
        .where(Book.is_deleted.is_(True))
        .order_by(Book.deleted_at.desc())
    )
    return result.scalars().all()


# ═══════════════════════════════════════════════════════
# SECTION 6: Upsert Pattern
# ═══════════════════════════════════════════════════════

async def upsert_tag(session: AsyncSession, tag_name: str) -> Tag:
    """
    INSERT OR UPDATE — get or create pattern.
    """
    # Try to get existing
    result = await session.execute(select(Tag).where(Tag.name == tag_name))
    tag = result.scalar_one_or_none()

    if not tag:
        tag = Tag(name=tag_name)
        session.add(tag)
        await session.commit()
        await session.refresh(tag)

    return tag


async def upsert_author(session: AsyncSession, email: str, name: str, bio: str = "") -> Author:
    """INSERT if not exists, UPDATE if exists."""
    result = await session.execute(select(Author).where(Author.email == email))
    author = result.scalar_one_or_none()

    if author:
        author.name = name
        author.bio  = bio
    else:
        author = Author(email=email, name=name, bio=bio)
        session.add(author)

    await session.commit()
    await session.refresh(author)
    return author


# ═══════════════════════════════════════════════════════
# SECTION 7: Raw SQL with text()
# ═══════════════════════════════════════════════════════

async def raw_sql_stats(session: AsyncSession) -> dict:
    """
    Use raw SQL when ORM is too complex.
    - Complex aggregations
    - Window functions
    - Database-specific features (EXPLAIN ANALYZE)
    """
    # Aggregate: book count and avg price per author
    result = await session.execute(text("""
        SELECT
            a.name as author_name,
            COUNT(b.id) as book_count,
            ROUND(AVG(b.price), 2) as avg_price,
            SUM(CASE WHEN b.published = 1 THEN 1 ELSE 0 END) as published_count
        FROM authors a
        LEFT JOIN books b ON b.author_id = a.id AND b.is_deleted = 0
        GROUP BY a.id, a.name
        ORDER BY book_count DESC
    """))
    rows = result.mappings().all()
    return {"stats": [dict(r) for r in rows]}


async def explain_query(session: AsyncSession) -> str:
    """Run EXPLAIN ANALYZE to check query performance."""
    result = await session.execute(text(
        "EXPLAIN SELECT * FROM books WHERE author_id = 1 AND is_deleted = 0"
    ))
    return "\n".join(str(row[0]) for row in result.fetchall())


# ═══════════════════════════════════════════════════════
# SECTION 8: FastAPI App
# ═══════════════════════════════════════════════════════

async def get_session():
    async with AsyncSessionFactory() as session:
        yield session


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Seed data
    async with AsyncSessionFactory() as session:
        # Create authors
        for i in range(1, 4):
            existing = (await session.execute(
                select(Author).where(Author.email == f"author{i}@test.com")
            )).scalar_one_or_none()
            if not existing:
                author = Author(name=f"Author {i}", email=f"author{i}@test.com")
                session.add(author)
        await session.commit()

        # Create books
        authors = (await session.execute(select(Author))).scalars().all()
        for author in authors:
            book_count = (await session.execute(
                select(func.count()).where(Book.author_id == author.id)
            )).scalar_one()
            if book_count == 0:
                for j in range(1, 4):
                    session.add(Book(
                        title=f"{author.name}'s Book {j}",
                        price=float(j * 100),
                        published=(j % 2 == 0),
                        author_id=author.id,
                    ))
        await session.commit()
    print("✅ Seed data ready")
    yield
    await engine.dispose()


app = FastAPI(
    title="SQLAlchemy Advanced Practical",
    description="N+1, Eager Loading, Transactions, Bulk Ops, Soft Delete",
    version="1.0.0",
    lifespan=lifespan,
)


@app.get("/demo/n-plus-1/bad", tags=["N+1 Problem"])
async def demo_n_plus_1_bad():
    """BAD: Triggers N+1 — watch SQL logs (echo=True)."""
    async with AsyncSessionFactory() as session:
        return await n_plus_1_bad(session)


@app.get("/demo/n-plus-1/selectinload", tags=["N+1 Problem"])
async def demo_selectinload():
    """GOOD: selectinload — 2 queries for all authors+books."""
    async with AsyncSessionFactory() as session:
        return await n_plus_1_fixed_selectinload(session)


@app.get("/demo/n-plus-1/joinedload", tags=["N+1 Problem"])
async def demo_joinedload():
    """GOOD: joinedload — 1 JOIN query for books+authors."""
    async with AsyncSessionFactory() as session:
        return await n_plus_1_fixed_joinedload(session)


@app.get("/demo/multi-relation-load", tags=["N+1 Problem"])
async def demo_multi_load():
    """Load books WITH author AND tags — still just 3 queries."""
    async with AsyncSessionFactory() as session:
        return await load_with_multiple_relations(session)


@app.post("/demo/bulk-insert/{author_id}", tags=["Bulk Operations"])
async def demo_bulk_insert(author_id: int, count: int = 50):
    """Bulk insert N books in a single query."""
    async with AsyncSessionFactory() as session:
        inserted = await bulk_insert_books(session, author_id, count)
        return {"inserted": inserted, "author_id": author_id}


@app.patch("/demo/bulk-discount/{author_id}", tags=["Bulk Operations"])
async def demo_bulk_update(author_id: int, discount: float = 0.1):
    """Bulk update all book prices for an author."""
    async with AsyncSessionFactory() as session:
        updated = await bulk_update_prices(session, author_id, discount)
        return {"updated_books": updated, "discount_applied": f"{discount*100}%"}


@app.get("/books/active", tags=["Soft Delete"])
async def get_active(limit: int = 20):
    """Only non-deleted books."""
    async with AsyncSessionFactory() as session:
        books = await get_active_books(session)
        return [{"id": b.id, "title": b.title, "price": b.price} for b in books[:limit]]


@app.delete("/books/{book_id}/soft", tags=["Soft Delete"])
async def soft_delete(book_id: int):
    """Soft delete — sets is_deleted=True, deleted_at=now."""
    async with AsyncSessionFactory() as session:
        success = await soft_delete_book(session, book_id)
        if not success:
            raise HTTPException(404, "Book not found or already deleted")
        return {"deleted": book_id, "type": "soft_delete"}


@app.post("/books/{book_id}/restore", tags=["Soft Delete"])
async def restore(book_id: int):
    """Restore a soft-deleted book."""
    async with AsyncSessionFactory() as session:
        success = await restore_book(session, book_id)
        if not success:
            raise HTTPException(404, "Book not found or not deleted")
        return {"restored": book_id}


@app.get("/books/deleted", tags=["Soft Delete"])
async def get_deleted():
    """Admin: list all soft-deleted books."""
    async with AsyncSessionFactory() as session:
        books = await list_deleted_books(session)
        return [{"id": b.id, "title": b.title, "deleted_at": str(b.deleted_at)} for b in books]


@app.get("/stats/raw-sql", tags=["Raw SQL"])
async def raw_stats():
    """Complex aggregation via raw SQL."""
    async with AsyncSessionFactory() as session:
        return await raw_sql_stats(session)


@app.get("/", tags=["Root"])
async def root():
    return {
        "message": "SQLAlchemy Advanced Practical",
        "tip": "echo=True in engine — watch SQL queries in terminal!",
        "demos": {
            "n_plus_1_bad":   "GET /demo/n-plus-1/bad",
            "selectinload":   "GET /demo/n-plus-1/selectinload",
            "joinedload":     "GET /demo/n-plus-1/joinedload",
            "bulk_insert":    "POST /demo/bulk-insert/1?count=50",
            "bulk_discount":  "PATCH /demo/bulk-discount/1?discount=0.2",
            "soft_delete":    "DELETE /books/1/soft",
            "restore":        "POST /books/1/restore",
            "deleted_list":   "GET /books/deleted",
            "raw_stats":      "GET /stats/raw-sql",
        }
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("11_sqlalchemy_advanced:app", host="0.0.0.0", port=8010, reload=True)
