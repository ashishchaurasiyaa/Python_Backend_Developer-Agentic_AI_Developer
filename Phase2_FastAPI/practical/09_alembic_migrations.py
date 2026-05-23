"""
PHASE 2 FastAPI — Practical 09: Alembic Migrations (Complete Setup)
Run app:   uvicorn 09_alembic_migrations:app --reload

Install: pip install alembic sqlalchemy asyncpg aiosqlite

FULL ALEMBIC SETUP GUIDE — every file you need:

  myproject/
  ├── alembic.ini               ← Alembic config (SECTION 2)
  ├── alembic/
  │   ├── env.py                ← Critical: async setup (SECTION 3)
  │   └── versions/
  │       ├── 001_initial.py    ← First migration (SECTION 4)
  │       └── 002_add_posts.py  ← Second migration (SECTION 5)
  ├── app/
  │   ├── models.py             ← SQLAlchemy models (SECTION 1)
  │   └── main.py               ← FastAPI app (SECTION 6)

Commands (SECTION 7)
"""

# ═══════════════════════════════════════════════════════
# SECTION 1: SQLAlchemy Models (app/models.py content)
# ═══════════════════════════════════════════════════════

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import (
    Boolean, DateTime, ForeignKey, Integer, String, Text, func
)
from sqlalchemy.ext.asyncio import AsyncAttrs, AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

DATABASE_URL = "sqlite+aiosqlite:///./alembic_demo.db"


class Base(AsyncAttrs, DeclarativeBase):
    """Base with async support + timestamp helpers."""

    # Every model gets created_at / updated_at automatically
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class UserModel(Base):
    """Migration 001 — initial table."""
    __tablename__ = "users"

    id:       Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name:     Mapped[str] = mapped_column(String(100), nullable=False)
    email:    Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    role:     Mapped[str] = mapped_column(String(20),  nullable=False, server_default="user")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="1")

    posts: Mapped[list["PostModel"]] = relationship("PostModel", back_populates="author")


class PostModel(Base):
    """Migration 002 — added later."""
    __tablename__ = "posts"

    id:        Mapped[int]          = mapped_column(Integer, primary_key=True, index=True)
    title:     Mapped[str]          = mapped_column(String(200), nullable=False)
    body:      Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    published: Mapped[bool]         = mapped_column(Boolean, server_default="0")
    author_id: Mapped[int]          = mapped_column(ForeignKey("users.id"), nullable=False, index=True)

    author: Mapped["UserModel"] = relationship("UserModel", back_populates="posts")


class TagModel(Base):
    """Migration 003 — tags system."""
    __tablename__ = "tags"

    id:   Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    slug: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)


# ═══════════════════════════════════════════════════════
# SECTION 2: alembic.ini content
# ═══════════════════════════════════════════════════════

ALEMBIC_INI = """
# alembic.ini — place in project root

[alembic]
# Path to migration scripts
script_location = alembic

# Template for migration filenames: YYYYMMDD_HH_mm_description.py
file_template = %%(year)d%%(month).2d%%(day).2d_%%(hour).2d%%(minute).2d_%%(slug)s

# SQLAlchemy URL — override in env.py for async
sqlalchemy.url = postgresql+asyncpg://user:pass@localhost/mydb

# Logging
[loggers]
keys = root,sqlalchemy,alembic

[handlers]
keys = console

[formatters]
keys = generic

[logger_root]
level = WARN
handlers = console
qualname =

[logger_sqlalchemy]
level = WARN
handlers =
qualname = sqlalchemy.engine

[logger_alembic]
level = INFO
handlers =
qualname = alembic

[handler_console]
class = StreamHandler
args = (sys.stderr,)
level = NOTSET
formatter = generic

[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s
datefmt = %H:%M:%S
"""


# ═══════════════════════════════════════════════════════
# SECTION 3: alembic/env.py — ASYNC setup (most important file)
# ═══════════════════════════════════════════════════════

ENV_PY_CONTENT = '''
# alembic/env.py — ASYNC version for SQLAlchemy 2.0 + FastAPI

import asyncio
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

# ─── Import your models so Alembic can detect them ───
# This is the MOST IMPORTANT part — all models must be imported!
from app.models import Base          # imports Base
import app.models                    # ensure all models are registered

# ─── Config ───
config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# MetaData for autogenerate
target_metadata = Base.metadata

# ─── Override URL from environment (12-factor app) ───
import os
db_url = os.getenv("DATABASE_URL", config.get_main_option("sqlalchemy.url"))
config.set_main_option("sqlalchemy.url", db_url)


def run_migrations_offline() -> None:
    """Run migrations without DB connection (generates SQL)."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,          # detect column type changes
        compare_server_default=True, # detect default value changes
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
        include_schemas=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Run migrations with async engine."""
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,    # no pooling for migrations
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Entry point for online migration mode."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
'''


# ═══════════════════════════════════════════════════════
# SECTION 4: Migration 001 — initial users table
# ═══════════════════════════════════════════════════════

MIGRATION_001 = '''
# alembic/versions/20240101_0000_initial_users.py
"""initial users table

Revision ID: abc123def456
Revises:
Create Date: 2024-01-01 00:00:00
"""

from alembic import op
import sqlalchemy as sa

revision = "abc123def456"
down_revision = None     # first migration — no parent
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id",        sa.Integer(),     nullable=False),
        sa.Column("name",      sa.String(100),   nullable=False),
        sa.Column("email",     sa.String(255),   nullable=False),
        sa.Column("role",      sa.String(20),    nullable=False, server_default="user"),
        sa.Column("is_active", sa.Boolean(),     nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_users_id",    "users", ["id"],    unique=False)
    op.create_index("ix_users_email", "users", ["email"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_users_email", table_name="users")
    op.drop_index("ix_users_id",    table_name="users")
    op.drop_table("users")
'''


# ═══════════════════════════════════════════════════════
# SECTION 5: Migration 002 — add posts table
# ═══════════════════════════════════════════════════════

MIGRATION_002 = '''
# alembic/versions/20240102_0000_add_posts.py
"""add posts table

Revision ID: def456ghi789
Revises: abc123def456
Create Date: 2024-01-02 00:00:00
"""

from alembic import op
import sqlalchemy as sa

revision = "def456ghi789"
down_revision = "abc123def456"   # points to previous migration
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create posts table
    op.create_table(
        "posts",
        sa.Column("id",        sa.Integer(), nullable=False),
        sa.Column("title",     sa.String(200), nullable=False),
        sa.Column("body",      sa.Text(),    nullable=True),
        sa.Column("published", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("author_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["author_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_posts_id",        "posts", ["id"],        unique=False)
    op.create_index("ix_posts_author_id", "posts", ["author_id"], unique=False)

    # Add column to existing table
    op.add_column("users", sa.Column("bio", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "bio")
    op.drop_index("ix_posts_author_id", table_name="posts")
    op.drop_index("ix_posts_id",        table_name="posts")
    op.drop_table("posts")
'''


# ═══════════════════════════════════════════════════════
# SECTION 6: Migration 003 — data migration (no schema change)
# ═══════════════════════════════════════════════════════

MIGRATION_003 = '''
# alembic/versions/20240103_0000_backfill_role.py
"""backfill default role for existing users

Revision ID: ghi789jkl012
Revises: def456ghi789
Create Date: 2024-01-03 00:00:00
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import table, column

revision = "ghi789jkl012"
down_revision = "def456ghi789"


def upgrade() -> None:
    # Data migration: update existing rows
    users_table = table("users",
        column("id",   sa.Integer),
        column("role", sa.String),
    )

    # Set role="user" for any NULL values
    op.execute(
        users_table.update()
        .where(users_table.c.role.is_(None))
        .values(role="user")
    )

    # Then make column non-nullable (safe after backfill)
    op.alter_column("users", "role", nullable=False, server_default="user")


def downgrade() -> None:
    op.alter_column("users", "role", nullable=True)
'''


# ═══════════════════════════════════════════════════════
# SECTION 7: Alembic CLI Commands
# ═══════════════════════════════════════════════════════

ALEMBIC_COMMANDS = """
# ─── SETUP (run once) ───
alembic init alembic                        # creates alembic/ folder + alembic.ini

# ─── CREATE MIGRATIONS ───
alembic revision --autogenerate -m "initial users table"   # auto-detect model changes
alembic revision -m "custom migration"                      # empty migration (manual)

# ─── RUN MIGRATIONS ───
alembic upgrade head                        # apply ALL pending migrations
alembic upgrade +1                          # apply next one migration
alembic upgrade abc123def456                # upgrade to specific revision

# ─── ROLLBACK ───
alembic downgrade -1                        # rollback ONE migration
alembic downgrade base                      # rollback ALL (empty DB)
alembic downgrade abc123def456              # rollback to specific revision

# ─── INSPECT ───
alembic current                             # current revision in DB
alembic history                             # all migrations in order
alembic history --verbose                   # with descriptions
alembic show abc123def456                   # show specific migration

# ─── GENERATE SQL (without running) ───
alembic upgrade head --sql                  # print SQL to stdout
alembic upgrade abc123:def456 --sql         # SQL for range of migrations

# ─── STAMP (mark migration as applied without running) ───
alembic stamp head                          # mark as at head (after manual schema create)
alembic stamp abc123def456                  # mark specific revision
"""


# ═══════════════════════════════════════════════════════
# SECTION 8: Run migrations in FastAPI lifespan
# ═══════════════════════════════════════════════════════

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.responses import JSONResponse


async def run_alembic_migrations():
    """
    Run pending migrations at app startup.
    Use in production — ensures DB is always up to date on deploy.
    """
    import subprocess
    result = subprocess.run(
        ["alembic", "upgrade", "head"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Migration failed:\n{result.stderr}")
    print(f"✅ Migrations: {result.stdout.strip() or 'already up to date'}")


async def get_alembic_current():
    """Get current migration revision."""
    import subprocess
    result = subprocess.run(
        ["alembic", "current"],
        capture_output=True, text=True,
    )
    return result.stdout.strip()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Run migrations on startup — safe for production."""
    print("🚀 Starting app...")

    # For SQLite demo: create tables directly
    engine = create_async_engine(DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await engine.dispose()
    print("✅ DB tables ready")

    # In real project with Alembic (uncomment):
    # await run_alembic_migrations()

    yield
    print("🛑 Shutting down...")


app = FastAPI(
    title="Alembic Migrations Guide",
    description="Complete Alembic setup for async FastAPI + SQLAlchemy 2.0",
    version="1.0.0",
    lifespan=lifespan,
)


@app.get("/", tags=["Root"])
async def root():
    return {
        "message": "Alembic Migrations Guide",
        "sections": {
            "1": "SQLAlchemy Models with timestamps",
            "2": "alembic.ini config",
            "3": "alembic/env.py (async setup)",
            "4": "Migration 001 — create users",
            "5": "Migration 002 — add posts + alter column",
            "6": "Migration 003 — data migration",
            "7": "CLI commands reference",
            "8": "Run migrations in FastAPI lifespan",
        }
    }


@app.get("/migrations/guide", tags=["Alembic"])
async def migration_guide():
    return JSONResponse({
        "alembic_ini": ALEMBIC_INI.strip(),
        "env_py": ENV_PY_CONTENT.strip(),
        "migration_001": MIGRATION_001.strip(),
        "migration_002": MIGRATION_002.strip(),
        "migration_003_data": MIGRATION_003.strip(),
        "commands": ALEMBIC_COMMANDS.strip(),
    })


@app.get("/migrations/tips", tags=["Alembic"])
async def migration_tips():
    return {
        "tips": [
            "Always review autogenerated migrations before running",
            "Never edit an already-applied migration — create a new one",
            "Data migrations: backfill first, then add constraints",
            "Use --sql flag to preview SQL before applying",
            "Stamp existing DBs with 'alembic stamp head' before using Alembic",
            "In production: run 'alembic upgrade head' in Dockerfile ENTRYPOINT or lifespan",
            "Use NullPool in env.py for migrations (no persistent connections)",
            "Import ALL models in env.py — autogenerate only detects imported tables",
        ],
        "common_mistakes": [
            "Forgetting to import models in env.py → autogenerate misses tables",
            "Using async engine directly in env.py without asyncio.run()",
            "Not setting compare_type=True → column type changes missed",
            "Editing applied migration → DB state diverges from history",
            "Running migrations without reviewing — autogenerate can be wrong",
        ]
    }


# ═══════════════════════════════════════════════════════
# SECTION 9: Interview Q&A
# ═══════════════════════════════════════════════════════

"""
Q1: Alembic kya hai? Kyun use karte hain?
    Alembic = SQLAlchemy ka official migration tool.
    Database schema changes ko version control karta hai.
    Team mein sab ka DB same state mein rehta hai.

Q2: autogenerate kaise kaam karta hai?
    Alembic current DB schema ko models se compare karta hai.
    Differences ke liye migration script auto-generate karta hai.
    IMPORTANT: env.py mein sare models import hone chahiye.

Q3: env.py mein async setup kyun chahiye?
    SQLAlchemy 2.0 ke async engine ke saath sync Alembic ka conflict.
    Solution: asyncio.run(run_async_migrations()) se async context mein chalao.
    NullPool use karo — migration ke liye persistent connection nahi chahiye.

Q4: Data migration (schema change nahi, sirf data) kaise karte hain?
    Alembic revision mein sa.table() + op.execute() use karo.
    Pattern: 1) backfill data, 2) then add NOT NULL constraint.
    Direct model import avoid karo — table() helper use karo.

Q5: Production mein migrations kaise run karte hain?
    Option 1: Dockerfile ENTRYPOINT mein 'alembic upgrade head'
    Option 2: FastAPI lifespan mein subprocess.run(['alembic', 'upgrade', 'head'])
    Option 3: K8s init container se migrations run karo.

Q6: Migration rollback kab karte hain?
    Development mein freely. Production mein carefully — data loss ho sakta hai.
    downgrade() mein dropped columns ka data wapis nahi aata.
    Critical data ke liye: soft delete prefer karo, hard delete nahi.
"""


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("09_alembic_migrations:app", host="0.0.0.0", port=8008, reload=True)
