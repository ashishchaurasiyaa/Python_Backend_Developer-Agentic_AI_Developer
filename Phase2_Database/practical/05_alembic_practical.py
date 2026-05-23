"""
Alembic Migrations — Practical Guide
═══════════════════════════════════════════════════════════════
Run: python 05_alembic_practical.py
Install: pip install alembic sqlalchemy[asyncio] asyncpg

NOTE: This file demonstrates Alembic concepts with RUNNABLE code
      showing the patterns. Real Alembic runs via CLI:
        alembic init migrations
        alembic revision --autogenerate -m "add users table"
        alembic upgrade head
        alembic downgrade -1

Topics:
  - Alembic project setup (env.py for async)
  - Auto-generate migrations from models
  - Manual migration (complex changes auto-generate can't do)
  - Data migration (backfill within schema migration)
  - Zero-downtime migration patterns
  - Rollback strategy
  - Common migration patterns

INTERVIEW QUICK REFERENCE at bottom.
"""

import asyncio
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import text, inspect
from sqlalchemy.ext.asyncio import create_async_engine, AsyncConnection

DB_URL = "postgresql+asyncpg://postgres:postgres@localhost:5432/alembic_demo"

engine = create_async_engine(DB_URL, echo=False)


# ═══════════════════════════════════════════════════════════
# SECTION 1: Alembic Project Structure (Reference)
# ═══════════════════════════════════════════════════════════

ALEMBIC_PROJECT_STRUCTURE = """
myapp/
├── alembic.ini              ← Alembic config
├── migrations/
│   ├── env.py               ← Migration environment (async setup here)
│   ├── script.py.mako       ← Migration template
│   └── versions/
│       ├── 001_create_users.py
│       ├── 002_add_email_index.py
│       └── 003_add_posts_table.py
└── app/
    └── models.py            ← SQLAlchemy models
"""

ALEMBIC_INI_CONTENT = """
# alembic.ini
[alembic]
script_location = migrations
sqlalchemy.url = postgresql+asyncpg://postgres:postgres@localhost/myapp

[loggers]
keys = root,sqlalchemy,alembic
"""

# ─── env.py for ASYNC (critical — default env.py is sync!) ───
ENV_PY_ASYNC = '''
# migrations/env.py — ASYNC version
import asyncio
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context
from app.models import Base  # import your models

config = context.config
fileConfig(config.config_file_name)
target_metadata = Base.metadata


def run_migrations_offline():
    """Run migrations without DB connection (generates SQL)."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection):
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online():
    """Run migrations with actual DB connection (async)."""
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,  # NullPool for migrations — no pooling needed
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
'''


# ═══════════════════════════════════════════════════════════
# SECTION 2: Migration File Examples
# ═══════════════════════════════════════════════════════════

def show_migration_examples():
    print("\n--- MIGRATION FILE EXAMPLES ---")

    # ─── Simple auto-generated migration ───
    migration_001 = '''
# migrations/versions/001_create_users_table.py
"""create users table

Revision ID: a1b2c3d4e5f6
Revises:
Create Date: 2024-01-15 10:30:00
"""
from alembic import op
import sqlalchemy as sa

revision = "a1b2c3d4e5f6"
down_revision = None          # first migration — no parent
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        "users",
        sa.Column("id",         sa.Integer,     primary_key=True),
        sa.Column("email",      sa.String(255), nullable=False, unique=True),
        sa.Column("name",       sa.String(100), nullable=False),
        sa.Column("plan",       sa.String(20),  nullable=False, server_default="free"),
        sa.Column("credits",    sa.Integer,     nullable=False, server_default="0"),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_users_email",      "users", ["email"])
    op.create_index("idx_users_plan",       "users", ["plan"])
    op.create_index("idx_users_deleted_at", "users", ["deleted_at"])

def downgrade():
    op.drop_table("users")
    # indexes are dropped automatically with table
'''

    # ─── Zero-downtime migration — add nullable column first ───
    migration_002 = '''
# migrations/versions/002_add_metadata_to_users.py
"""add metadata column to users (zero-downtime)

Revision ID: b2c3d4e5f6a1
Revises: a1b2c3d4e5f6
"""
from alembic import op
import sqlalchemy as sa

revision = "b2c3d4e5f6a1"
down_revision = "a1b2c3d4e5f6"

def upgrade():
    # STEP 1: Add nullable column (instant — no lock, no backfill)
    op.add_column("users", sa.Column("metadata", sa.JSON, nullable=True))
    # Deploy app code that handles null metadata
    # STEP 2: Backfill → done in a separate data migration (see migration 003)
    # STEP 3: NOT NULL constraint → done after backfill in migration 004

def downgrade():
    op.drop_column("users", "metadata")
'''

    # ─── Data migration (backfill) ───
    migration_003 = '''
# migrations/versions/003_backfill_user_metadata.py
"""backfill metadata for existing users

Revision ID: c3d4e5f6a1b2
Revises: b2c3d4e5f6a1
"""
from alembic import op
import sqlalchemy as sa

revision = "c3d4e5f6a1b2"
down_revision = "b2c3d4e5f6a1"

def upgrade():
    # INTERVIEW: Data migration kaise karte hain safely?
    # batch update in small chunks — don't lock entire table
    connection = op.get_bind()

    batch_size = 10000
    while True:
        result = connection.execute(
            sa.text("""
                UPDATE users
                SET metadata = \'{}\'::json
                WHERE metadata IS NULL
                AND id IN (
                    SELECT id FROM users
                    WHERE metadata IS NULL
                    LIMIT :batch_size
                )
            """),
            {"batch_size": batch_size}
        )
        if result.rowcount == 0:
            break

def downgrade():
    pass  # data migration — no meaningful downgrade
'''

    # ─── Add NOT NULL after backfill complete ───
    migration_004 = '''
# migrations/versions/004_set_metadata_not_null.py
"""set metadata NOT NULL after backfill

Revision ID: d4e5f6a1b2c3
Revises: c3d4e5f6a1b2
"""
from alembic import op
import sqlalchemy as sa

revision = "d4e5f6a1b2c3"
down_revision = "c3d4e5f6a1b2"

def upgrade():
    # STEP 3: Now safe to add NOT NULL (all rows have value)
    op.alter_column("users", "metadata",
        nullable=False,
        server_default=sa.text("'{}'::json"),
    )

def downgrade():
    op.alter_column("users", "metadata", nullable=True, server_default=None)
'''

    # ─── Concurrent index creation ───
    migration_005 = '''
# migrations/versions/005_add_gin_index_metadata.py
"""add GIN index on metadata (CONCURRENTLY — no lock)

Revision ID: e5f6a1b2c3d4
Revises: d4e5f6a1b2c3
"""
from alembic import op
import sqlalchemy as sa

revision = "e5f6a1b2c3d4"
down_revision = "d4e5f6a1b2c3"

def upgrade():
    # CRITICAL: CREATE INDEX CONCURRENTLY cannot run in transaction
    # Alembic wraps migrations in transaction by default → disable it
    op.execute("COMMIT")   # close alembic's transaction
    op.execute("""
        CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_users_metadata_gin
        ON users USING gin(metadata)
    """)
    # Note: no explicit BEGIN needed — alembic handles it

def downgrade():
    op.execute("COMMIT")
    op.execute("DROP INDEX CONCURRENTLY IF EXISTS idx_users_metadata_gin")
'''

    print(migration_001[:400] + "\n  ...[truncated]")
    print("\n  ✓ migration_001: create_users_table")
    print("  ✓ migration_002: add nullable metadata (step 1 of 3)")
    print("  ✓ migration_003: backfill metadata data (step 2 of 3)")
    print("  ✓ migration_004: set NOT NULL (step 3 of 3)")
    print("  ✓ migration_005: CREATE INDEX CONCURRENTLY (no lock)")


# ═══════════════════════════════════════════════════════════
# SECTION 3: Common Alembic Operations (CLI Reference)
# ═══════════════════════════════════════════════════════════

def show_cli_reference():
    print("\n--- ALEMBIC CLI REFERENCE ---")
    cli_commands = """
  # Init
  alembic init migrations                          # create migrations/ folder
  alembic init -t async migrations                 # async template (py3.10+)

  # Create migration
  alembic revision --autogenerate -m "add users"   # auto from model changes
  alembic revision -m "manual change"              # empty migration file

  # Apply
  alembic upgrade head                             # apply all pending
  alembic upgrade +1                               # apply next 1
  alembic upgrade a1b2c3d4                         # apply specific revision

  # Rollback
  alembic downgrade -1                             # rollback 1 migration
  alembic downgrade base                           # rollback ALL
  alembic downgrade a1b2c3d4                       # downgrade to specific

  # Status
  alembic current                                  # current revision applied
  alembic history --verbose                        # all migrations
  alembic heads                                    # latest revisions

  # SQL output (dry run)
  alembic upgrade head --sql                       # print SQL without running
  alembic upgrade head --sql > migration.sql       # save SQL to file
"""
    print(cli_commands)


# ═══════════════════════════════════════════════════════════
# SECTION 4: Live Demo — Run Migrations Programmatically
# ═══════════════════════════════════════════════════════════

async def demo_migration_tracking(conn: AsyncConnection):
    """
    Demonstrate what Alembic's alembic_version table looks like.
    Shows how Alembic tracks applied migrations.
    """
    print("\n--- MIGRATION TRACKING (alembic_version table) ---")

    # Simulate creating alembic_version table (what alembic does internally)
    await conn.execute(text("DROP TABLE IF EXISTS alembic_version_demo"))
    await conn.execute(text("""
        CREATE TABLE alembic_version_demo (
            version_num VARCHAR(32) NOT NULL PRIMARY KEY
        )
    """))

    # Simulate applying migrations
    migrations = [
        ("a1b2c3d4e5f6", "create users table"),
        ("b2c3d4e5f6a1", "add metadata column"),
        ("c3d4e5f6a1b2", "backfill metadata"),
    ]

    for rev_id, description in migrations:
        await conn.execute(
            text("INSERT INTO alembic_version_demo VALUES (:rev)"),
            {"rev": rev_id}
        )
        print(f"  ✓ Applied: {rev_id} — {description}")

    # Show current state (what `alembic current` shows)
    result = await conn.execute(text("SELECT version_num FROM alembic_version_demo"))
    current = result.scalar()
    print(f"\n  Current revision: {current}")
    print(f"  (alembic current → reads this table)")

    await conn.execute(text("DROP TABLE alembic_version_demo"))


async def demo_zero_downtime_pattern(conn: AsyncConnection):
    """Demonstrate zero-downtime migration in actual SQL."""
    print("\n--- ZERO-DOWNTIME MIGRATION PATTERN (Live) ---")

    # Setup
    await conn.execute(text("DROP TABLE IF EXISTS demo_users"))
    await conn.execute(text("""
        CREATE TABLE demo_users (
            id    SERIAL PRIMARY KEY,
            email VARCHAR(255) UNIQUE NOT NULL,
            name  VARCHAR(100) NOT NULL
        )
    """))
    # Seed data
    await conn.execute(text("""
        INSERT INTO demo_users (email, name) VALUES
        ('alice@test.com', 'Alice'),
        ('bob@test.com', 'Bob'),
        ('charlie@test.com', 'Charlie')
    """))

    # ─── STEP 1: Add column nullable (instant, no lock) ───
    print("  Step 1: ALTER TABLE ADD COLUMN nullable (no lock)...")
    await conn.execute(text(
        "ALTER TABLE demo_users ADD COLUMN bio TEXT"
    ))
    print("  ✓ Column added (nullable) — app deployed, handles NULL bio")

    # ─── STEP 2: Backfill in batches ───
    print("  Step 2: Backfill existing rows in batches...")
    batch = 0
    while True:
        result = await conn.execute(text("""
            UPDATE demo_users
            SET bio = 'No bio yet'
            WHERE bio IS NULL
            AND id IN (SELECT id FROM demo_users WHERE bio IS NULL LIMIT 2)
        """))
        if result.rowcount == 0:
            break
        batch += 1
        print(f"    Batch {batch}: updated {result.rowcount} rows")

    # ─── STEP 3: Add NOT NULL (after all rows have value) ───
    print("  Step 3: ALTER COLUMN SET NOT NULL (now safe)...")
    await conn.execute(text(
        "ALTER TABLE demo_users ALTER COLUMN bio SET NOT NULL"
    ))
    print("  ✓ NOT NULL constraint applied")

    # Verify
    result = await conn.execute(text("SELECT id, name, bio FROM demo_users"))
    rows = result.all()
    print(f"  Final state ({len(rows)} rows):")
    for row in rows:
        print(f"    {row.name}: bio='{row.bio}'")

    await conn.execute(text("DROP TABLE demo_users"))


async def demo_rename_column_pattern(conn: AsyncConnection):
    """Safe column rename — never use ALTER COLUMN RENAME in production directly."""
    print("\n--- SAFE COLUMN RENAME (Zero-downtime) ---")

    await conn.execute(text("DROP TABLE IF EXISTS demo_posts"))
    await conn.execute(text("""
        CREATE TABLE demo_posts (
            id         SERIAL PRIMARY KEY,
            title      VARCHAR(200),
            first_name VARCHAR(100),  -- we want to rename this to author_name
            last_name  VARCHAR(100)
        )
    """))
    await conn.execute(text("""
        INSERT INTO demo_posts (title, first_name, last_name) VALUES
        ('Post 1', 'Alice', 'Smith'),
        ('Post 2', 'Bob', 'Jones')
    """))

    steps = [
        ("Migration 1", "ADD COLUMN author_name VARCHAR(200)",
         "ALTER TABLE demo_posts ADD COLUMN author_name VARCHAR(200)"),

        ("Migration 2 (backfill)", "UPDATE SET author_name = first_name || last_name",
         "UPDATE demo_posts SET author_name = first_name || ' ' || last_name"),

        ("Migration 3 (cleanup)", "DROP old columns after app reads from author_name",
         "ALTER TABLE demo_posts DROP COLUMN first_name, DROP COLUMN last_name"),
    ]

    for step_name, description, sql in steps:
        await conn.execute(text(sql))
        print(f"  ✓ {step_name}: {description}")

    result = await conn.execute(text("SELECT title, author_name FROM demo_posts"))
    for row in result.all():
        print(f"    '{row.title}' by {row.author_name}")

    await conn.execute(text("DROP TABLE demo_posts"))


# ═══════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════

async def main():
    print("Alembic Migration Patterns — Practical Guide")
    print("=" * 50)

    print(ALEMBIC_PROJECT_STRUCTURE)

    show_migration_examples()
    show_cli_reference()

    print("\nConnecting to PostgreSQL...")
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
            print("✓ Connected — running live migration pattern demos\n")

            await demo_migration_tracking(conn)
            await demo_zero_downtime_pattern(conn)
            await demo_rename_column_pattern(conn)
            await conn.commit()

    except Exception as e:
        print(f"DB connection failed: {e}")
        print("Running code/reference demos only (no live DB needed)")

    finally:
        await engine.dispose()

    print("\n✓ All Alembic demos complete!")


# ═══════════════════════════════════════════════════════════
# INTERVIEW QUICK REFERENCE
# ═══════════════════════════════════════════════════════════
"""
Q: Alembic kya hai?
A: SQLAlchemy ke liye database migration tool
   Models change → alembic revision --autogenerate → migration file
   Migration file: upgrade() + downgrade() functions
   alembic upgrade head → apply all pending migrations

Q: env.py async kyu change karna padta hai?
A: Default env.py sync (DBAPI) use karta hai
   Async SQLAlchemy ke liye: async_engine_from_config + asyncio.run()
   NullPool use karo migrations ke liye (no connection pooling needed)

Q: Zero-downtime migration 3 steps?
A: Step 1: ADD COLUMN nullable (instant, no lock)
   Step 2: Backfill in batches (no lock, throttled)
   Step 3: SET NOT NULL (after backfill complete)

Q: CREATE INDEX safely?
A: CREATE INDEX CONCURRENTLY — no table lock, slow build
   Alembic mein: op.execute("COMMIT") pehle (CONCURRENTLY needs no transaction)

Q: Column rename safely?
A: 1. Add new column
   2. Deploy app writing to BOTH old + new
   3. Backfill new column from old
   4. Deploy app reading from new column only
   5. Drop old column

Q: Rollback strategy?
A: alembic downgrade -1 (one step back)
   Every migration should have working downgrade() function
   Data migrations: downgrade = NOP (can't un-backfill easily)
   Test downgrade in staging before production!

Q: Multiple migration branches?
A: alembic merge heads → creates merge migration
   Happens when 2 devs create migrations from same base
   alembic heads shows multiple → alembic merge + commit

Q: alembic --sql kya karta hai?
A: Dry run — prints SQL without executing
   Use in CI: alembic upgrade head --sql > migration.sql
   Review SQL before applying to production
"""

if __name__ == "__main__":
    asyncio.run(main())
