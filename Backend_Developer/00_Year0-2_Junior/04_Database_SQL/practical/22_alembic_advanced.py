"""
Alembic Advanced — Production Migration Patterns
=================================================
Covers the patterns that most tutorials skip:

  - Migration file anatomy (upgrade / downgrade lifecycle)
  - Auto-generate pitfalls and when to write migrations by hand
  - Data migrations: raw SQL vs. ORM (why raw SQL wins)
  - Large-table batch updates to avoid lock escalation
  - Renaming tables and columns safely
  - SQLite batch mode for ALTER TABLE limitations
  - Postgres ENUM creation and extension in autocommit
  - CONCURRENTLY index creation without table locks
  - Reversible migrations and the NotImplementedError pattern
  - Stamping an existing production database
  - Environment-specific include_object filtering
  - Advisory locks to prevent concurrent migration races
  - env.py patterns for multi-tenant / multi-schema deployments
  - CI/CD integration checklist

This is an illustrative module.  Individual sections can be dropped into
real Alembic migration files (alembic/versions/*.py) or env.py with minimal
modification.  No database connection is required to study the patterns.

pip install alembic sqlalchemy
"""

from __future__ import annotations

import os
import textwrap
from typing import Generator

# Alembic public API — imported for type-annotation purposes so the module
# documents real symbols even when alembic is available in the environment.
# pip install alembic sqlalchemy
import sqlalchemy as sa
from alembic import op
from sqlalchemy.sql import column, table
from sqlalchemy import text


# ==========================================================================
# 1. MIGRATION FILE ANATOMY
# ==========================================================================

# Every Alembic migration is a Python module with four module-level variables
# and two required functions.  Below is the canonical template.

MIGRATION_TEMPLATE = textwrap.dedent("""
    \"\"\"add users table

    Revision ID: a1b2c3d4
    Revises: previous_revision_id
    Create Date: 2024-01-01 12:00:00.000000
    \"\"\"
    from alembic import op
    import sqlalchemy as sa

    revision     = 'a1b2c3d4'
    down_revision = 'previous_revision_id'   # None for the very first migration
    branch_labels = None
    depends_on    = None


    def upgrade() -> None:
        op.create_table(
            'users',
            sa.Column('id',         sa.Integer(),               nullable=False,
                      primary_key=True),
            sa.Column('email',      sa.String(255),             nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True),
                      server_default=sa.func.now()),
        )
        # Always create indexes explicitly — autogenerate sometimes misses them.
        op.create_index('ix_users_email', 'users', ['email'], unique=True)


    def downgrade() -> None:
        op.drop_index('ix_users_email', table_name='users')
        op.drop_table('users')
""")


# ==========================================================================
# 2. AUTO-GENERATE PITFALLS
# ==========================================================================

# env.py snippet that wires auto-generate to application models:
ENV_PY_AUTOGENERATE = textwrap.dedent("""
    # alembic/env.py
    from myapp.models import Base          # import ALL model modules here
    target_metadata = Base.metadata

    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,                 # detect column type changes
        compare_server_default=True,       # detect server_default changes
        render_as_batch=True,              # required for SQLite (section 5)
    )
""")

# Known auto-generate blind spots:
AUTOGENERATE_BLIND_SPOTS = [
    "Server-side defaults vs Python-side defaults — autogenerate ignores Python defaults.",
    "Renamed columns/tables — seen as DROP + ADD (data loss!). Always rename manually.",
    "PostgreSQL ENUM modifications — adding values requires autocommit.",
    "Some constraint changes (check, exclusion constraints).",
    "Anything in a schema that is not reflected (e.g., views, materialized views).",
]


def print_autogenerate_warnings() -> None:
    """Print production reminders about auto-generate limitations."""
    print("Auto-generate blind spots — always review generated migrations:")
    for i, warning in enumerate(AUTOGENERATE_BLIND_SPOTS, 1):
        print(f"  {i}. {warning}")


# ==========================================================================
# 3. DATA MIGRATIONS — RAW SQL PATTERN
# ==========================================================================

# ------------------------------------------------------------------
# BAD: Using ORM models inside a migration.
# The model may drift from the migration over time, causing failures
# when the migration is replayed from scratch (e.g., on a fresh DB).
# ------------------------------------------------------------------

def _data_migration_bad_example_do_not_use() -> None:
    """
    Anti-pattern — importing ORM models into a migration.
    Left here as documentation of what NOT to do.
    """
    # DO NOT do this:
    #   from myapp.models import User
    #   session = Session(bind=op.get_bind())
    #   for user in session.query(User).all():
    #       user.full_name = user.first_name + " " + user.last_name
    #   session.commit()
    pass


# ------------------------------------------------------------------
# GOOD: Self-contained table reflection (no ORM dependency).
# This migration will still run correctly years from now even if the
# User model has been renamed, moved, or deleted.
# ------------------------------------------------------------------

# Define a "shadow" table that represents only the columns this migration needs.
_users_shadow = table(
    "users",
    column("id",         sa.Integer),
    column("first_name", sa.String),
    column("last_name",  sa.String),
    column("full_name",  sa.String),
)


def upgrade_backfill_full_name() -> None:
    """
    Data migration: populate users.full_name from first_name + last_name.

    Drop this function body into the upgrade() of the relevant revision file.
    The shadow table above must be copied into that file too so the migration
    is fully self-contained.
    """
    connection = op.get_bind()
    rows = connection.execute(_users_shadow.select()).fetchall()
    for row in rows:
        connection.execute(
            _users_shadow.update()
            .where(_users_shadow.c.id == row.id)
            .values(full_name=f"{row.first_name} {row.last_name}")
        )


def downgrade_backfill_full_name() -> None:
    """Reverse: clear the full_name column (data is not recoverable)."""
    connection = op.get_bind()
    connection.execute(
        _users_shadow.update().values(full_name=None)
    )


# ------------------------------------------------------------------
# ALTERNATIVE GOOD: Single raw-SQL UPDATE (fastest for small tables)
# ------------------------------------------------------------------

def upgrade_backfill_full_name_raw_sql() -> None:
    """
    Same backfill using a single SQL statement — preferred for small tables.
    """
    op.execute(
        text("""
            UPDATE users
            SET    full_name = first_name || ' ' || last_name
            WHERE  full_name IS NULL
        """)
    )


# ==========================================================================
# 4. LARGE-TABLE BATCH DATA MIGRATIONS
# ==========================================================================

def upgrade_backfill_batch(batch_size: int = 10_000) -> None:
    """
    Batch-update a large table to avoid holding a long-lived lock and
    generating excessive WAL / undo log.

    Pattern:
      1. Add column with NULL default (instant on most engines).
      2. Backfill in batches of ``batch_size`` rows.
      3. (Later migration) Set NOT NULL / add default.

    This function represents the body of step 2's upgrade().
    """
    conn = op.get_bind()
    while True:
        result = conn.execute(
            text("""
                UPDATE users
                SET    full_name = first_name || ' ' || last_name
                WHERE  id IN (
                    SELECT id
                    FROM   users
                    WHERE  full_name IS NULL
                    LIMIT  :batch_size
                )
            """),
            {"batch_size": batch_size},
        )
        # rowcount == 0 means there are no remaining NULL rows.
        if result.rowcount == 0:
            break


# Why batch updates matter:
BATCH_MIGRATION_RATIONALE = [
    "A single UPDATE on 50M rows holds a table lock for minutes.",
    "Large transactions bloat Write-Ahead Log (WAL) on Postgres and undo log on MySQL.",
    "If the migration is killed mid-run, batching preserves partial progress.",
    "Batching allows the DB autovacuum to keep pace with dead tuple accumulation.",
]


# ==========================================================================
# 5. RENAMING TABLES AND COLUMNS
# ==========================================================================

def upgrade_rename_table_and_column() -> None:
    """
    Rename the 'user' table to 'users' and rename the 'email_addr' column
    to 'email'.

    Auto-generate treats renames as DROP + ADD (data loss!).
    Always write renames by hand and review carefully.
    """
    op.rename_table("user", "users")
    op.alter_column("users", "email_addr", new_column_name="email")


def downgrade_rename_table_and_column() -> None:
    op.alter_column("users", "email", new_column_name="email_addr")
    op.rename_table("users", "user")


# ==========================================================================
# 6. SQLITE BATCH MODE
# ==========================================================================

# SQLite does not support many ALTER TABLE variants (e.g., DROP COLUMN before
# 3.35, TYPE changes, renaming with FK references).  Alembic's batch_alter_table
# works around this by:
#   1. Creating a new table with the desired schema.
#   2. Copying data from the old table.
#   3. Dropping the old table and renaming the new one.

def upgrade_sqlite_batch_alter() -> None:
    """
    Example: rename a column and add a new column on SQLite.
    Use render_as_batch=True in env.py so autogenerate emits this syntax.
    """
    with op.batch_alter_table("users") as batch_op:
        batch_op.alter_column("name", new_column_name="full_name")
        batch_op.add_column(sa.Column("phone", sa.String(20), nullable=True))


def downgrade_sqlite_batch_alter() -> None:
    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_column("phone")
        batch_op.alter_column("full_name", new_column_name="name")


# ==========================================================================
# 7. POSTGRES ENUM MANAGEMENT
# ==========================================================================

def upgrade_create_enum() -> None:
    """
    Create a Postgres ENUM type and a column that uses it.
    Must manually drop the type in downgrade — SQLAlchemy does not do this
    automatically when the column is dropped.
    """
    op.execute("CREATE TYPE order_status AS ENUM ('pending', 'paid', 'cancelled')")
    op.add_column(
        "orders",
        sa.Column(
            "status",
            sa.Enum("pending", "paid", "cancelled", name="order_status"),
            nullable=False,
            server_default="pending",
        ),
    )


def downgrade_create_enum() -> None:
    op.drop_column("orders", "status")
    op.execute("DROP TYPE order_status")


def upgrade_extend_enum() -> None:
    """
    Add a new value to an existing Postgres ENUM.

    'ALTER TYPE ... ADD VALUE' cannot run inside a transaction on Postgres < 12.
    Use autocommit_block() to commit the enclosing transaction first, then
    execute the DDL outside any transaction.
    """
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE order_status ADD VALUE 'refunded'")


# Note: there is no safe downgrade for removing an ENUM value in Postgres.
# The only option is to recreate the type (risky if rows reference the value).
def downgrade_extend_enum() -> None:
    raise NotImplementedError(
        "Removing a Postgres ENUM value requires recreating the type. "
        "Ensure no rows reference 'refunded' before attempting manually."
    )


# ==========================================================================
# 8. CONCURRENTLY INDEXES (Postgres)
# ==========================================================================

# Regular CREATE INDEX acquires a ShareLock that blocks writes for its duration.
# CREATE INDEX CONCURRENTLY avoids the write lock but cannot run inside a
# transaction.  Alembic wraps every migration in a transaction by default, so
# we must opt out via autocommit_block().

def upgrade_concurrent_index() -> None:
    """
    Create an index without locking the table — safe for production traffic.
    """
    with op.get_context().autocommit_block():
        op.create_index(
            "ix_users_email",
            "users",
            ["email"],
            unique=True,
            postgresql_concurrently=True,
        )


def downgrade_concurrent_index() -> None:
    with op.get_context().autocommit_block():
        op.drop_index(
            "ix_users_email",
            table_name="users",
            postgresql_concurrently=True,
        )


# ==========================================================================
# 9. REVERSIBLE MIGRATIONS — BEST PRACTICES
# ==========================================================================

def upgrade_add_audit_table() -> None:
    op.create_table(
        "audit_log",
        sa.Column("id",         sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("table_name", sa.String(100),  nullable=False),
        sa.Column("row_id",     sa.Integer(),    nullable=False),
        sa.Column("action",     sa.String(10),   nullable=False),
        sa.Column("changed_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column("changed_by", sa.String(255),  nullable=True),
    )
    op.create_index("ix_audit_log_table_row", "audit_log",
                    ["table_name", "row_id"])


def downgrade_add_audit_table() -> None:
    """
    Dropping audit_log permanently destroys the audit history.
    Raise here to force a deliberate override rather than silently losing data.
    """
    raise NotImplementedError(
        "Dropping audit_log would permanently destroy audit history. "
        "Archive the table manually, then set down_revision to skip this step."
    )


# ==========================================================================
# 10. STAMPING AN EXISTING DATABASE
# ==========================================================================

STAMPING_GUIDE = textwrap.dedent("""
    Stamping tells Alembic "the DB is already at this revision" without running
    any migration SQL.  Use when:
      - Adopting Alembic in a project that already has a live schema.
      - Recovering from a failed migration that partially applied.

    Commands:
        alembic stamp head           # Mark as fully migrated
        alembic stamp <revision_id>  # Mark as at a specific revision
        alembic stamp base           # Mark as having no migrations applied

    After stamping, normal upgrade/downgrade commands work as expected.
""")


# ==========================================================================
# 11. ENVIRONMENT-SPECIFIC FILTERING (env.py)
# ==========================================================================

def include_object(
    object,   # noqa: A002  (shadows builtin — matches Alembic's signature)
    name: str,
    type_: str,
    reflected: bool,
    compare_to,
) -> bool:
    """
    Alembic include_object hook — controls which DB objects are compared
    during auto-generate.

    Pass to context.configure(include_object=include_object) in env.py.

    Example policy:
      - Skip the 'audit_log' table in the test environment (kept small).
      - Skip all tables whose names start with 'tmp_'.
    """
    env = os.getenv("APP_ENV", "production")

    if type_ == "table":
        if env == "test" and name == "audit_log":
            return False          # Exclude audit_log from test migrations
        if name.startswith("tmp_"):
            return False          # Never migrate temporary scratch tables

    return True


ENV_PY_WITH_FILTERING = textwrap.dedent("""
    # alembic/env.py  (online migration section)
    from myapp.migrations.helpers import include_object

    def run_migrations_online():
        connectable = engine_from_config(config.get_section(config.config_ini_section))
        with connectable.connect() as connection:
            context.configure(
                connection=connection,
                target_metadata=target_metadata,
                compare_type=True,
                compare_server_default=True,
                include_object=include_object,
            )
            with context.begin_transaction():
                context.run_migrations()
""")


# ==========================================================================
# 12. ADVISORY LOCKS — PREVENT CONCURRENT MIGRATION RACES
# ==========================================================================

# When many application instances start simultaneously (e.g., rolling deploy),
# each may try to run `alembic upgrade head`.  Without coordination, you get
# races, duplicate DDL, and corrupted migration history.

ADVISORY_LOCK_MIGRATION = textwrap.dedent("""
    # Place inside a migration's upgrade() to serialise concurrent executions.
    # Better approach: run migrations as a pre-deploy job, not at app startup.

    MIGRATION_LOCK_ID = 12345678   # pick a stable arbitrary integer for this project

    def upgrade() -> None:
        op.execute(f"SELECT pg_advisory_lock({MIGRATION_LOCK_ID})")
        try:
            # --- actual migration work ---
            op.add_column('users', sa.Column('verified', sa.Boolean(),
                          server_default='false', nullable=False))
        finally:
            op.execute(f"SELECT pg_advisory_unlock({MIGRATION_LOCK_ID})")
""")

ADVISORY_LOCK_NOTES = [
    "pg_advisory_lock() blocks until the lock is available — safe across concurrent instances.",
    "The lock is released automatically if the session drops, preventing deadlock.",
    "Prefer running migrations as a separate pre-deploy step (k8s Job, GitHub Actions step).",
    "Never acquire advisory locks inside a long transaction that holds table locks too.",
]


# ==========================================================================
# 13. MULTI-TENANT / SCHEMA-PER-TENANT MIGRATIONS
# ==========================================================================

ENV_PY_MULTI_TENANT = textwrap.dedent("""
    # alembic/env.py — apply the same migration to every tenant schema.

    def get_all_tenant_ids():
        # Query a control DB or a config file for the list of tenant schemas.
        return ['acme', 'globex', 'initech']

    def run_migrations_online():
        connectable = engine_from_config(...)
        with connectable.connect() as connection:
            for tenant_id in get_all_tenant_ids():
                # Switch the search_path to the tenant's schema.
                connection.execute(
                    text(f'SET search_path = tenant_{tenant_id}')
                )
                context.configure(
                    connection=connection,
                    target_metadata=target_metadata,
                )
                with context.begin_transaction():
                    context.run_migrations()
""")


# ==========================================================================
# 14. BRANCHES AND MERGING
# ==========================================================================

BRANCHING_GUIDE = textwrap.dedent("""
    Scenario: two developers both created a migration from the same base revision.

        base_rev (abc)
          ├── dev_a_rev (def)   [PR #1]
          └── dev_b_rev (ghi)   [PR #2]

    After both PRs merge, Alembic sees two heads.  Create a merge commit:

        alembic merge def ghi -m "merge branch A and branch B"

    This generates a migration with:
        down_revision = ('def', 'ghi')

    Running `alembic upgrade head` then applies both paths and the merge point.

    Named branches (less common):
        # In the revision file:
        branch_labels = 'payments_branch'

        # Apply only the payments branch:
        alembic upgrade payments_branch@head

    Recommendation: avoid branches unless you have independently deployable
    modules (e.g., a plugin system).  Linear history is far easier to reason about.
""")


# ==========================================================================
# 15. CI/CD INTEGRATION CHECKLIST
# ==========================================================================

CICD_CHECKLIST = textwrap.dedent("""
    GitHub Actions example (runs on every PR that touches migrations):

        - name: Set up Python
          uses: actions/setup-python@v4
          with:
            python-version: '3.11'

        - name: Install dependencies
          run: pip install -r requirements.txt

        - name: Start test database
          run: docker compose up -d postgres
             # or: use a GitHub-hosted Postgres service container

        - name: Apply migrations (upgrade)
          run: alembic upgrade head
          env:
            DATABASE_URL: postgresql://postgres:postgres@localhost:5432/testdb

        - name: Verify downgrade
          run: alembic downgrade -1

        - name: Re-apply to confirm idempotency
          run: alembic upgrade head

    Key rules:
      1. Run `alembic upgrade head` BEFORE deploying new code
         (the new code assumes the new schema already exists).
      2. Always test both upgrade and downgrade in CI — downgrade is
         your emergency rollback lever.
      3. Generate SQL for review:
           alembic upgrade --sql head > migration.sql
      4. Stamp staging from the latest prod backup before testing
         a migration that touches production data.
""")


# ==========================================================================
# 16. COMMON PITFALLS REFERENCE
# ==========================================================================

COMMON_PITFALLS: dict[str, str] = {
    "1. Auto-generate misses models": (
        "Ensure every model module is imported before target_metadata is read in env.py."
    ),
    "2. Migration passes locally, fails in production": (
        "DB state diverges.  Restore a prod backup to staging and migrate that first."
    ),
    "3. Long migration kills rolling deploy": (
        "Move heavy data operations to a background worker or a separate backfill script."
    ),
    "4. Dropping a column still referenced by old code": (
        "Use zero-downtime patterns: deploy code that ignores the column first, then drop."
    ),
    "5. ENUM extension outside transaction": (
        "Use autocommit_block() for ALTER TYPE ... ADD VALUE on Postgres."
    ),
    "6. Inconsistent default sources": (
        "Pick either a Python-side default (ORM) or a DB server_default — not both."
    ),
    "7. Missing index after create_table": (
        "op.create_index() must be called explicitly; autogenerate can miss FK indexes."
    ),
    "8. Concurrent migrations at startup": (
        "Use advisory locks or, better, run migrations as a pre-deploy Job."
    ),
}


def print_pitfalls() -> None:
    """Print the common pitfalls table."""
    print("Common Alembic pitfalls:\n")
    for title, detail in COMMON_PITFALLS.items():
        print(f"  {title}")
        print(f"    -> {detail}\n")


# ==========================================================================
# 17. PRODUCTION WORKFLOW SUMMARY
# ==========================================================================

PRODUCTION_WORKFLOW = textwrap.dedent("""
    Production migration lifecycle
    ──────────────────────────────
    1.  Developer writes or tweaks ORM models locally.
    2.  alembic revision --autogenerate -m "<description>"
    3.  REVIEW the generated file — fix renames, data ops, ENUM changes.
    4.  Test locally:
          alembic upgrade head
          alembic downgrade -1
          alembic upgrade head
    5.  Include the migration file in the PR (committed alongside model changes).
    6.  CI runs upgrade + downgrade against a fresh test DB (see section 15).
    7.  PR merges to main.
    8.  Deploy pipeline:
          a. alembic upgrade head   (against prod DB, before new code goes live)
          b. Deploy new application code that expects the updated schema.
    9.  Monitor DB metrics and application errors for 10–30 minutes.

    For high-risk migrations (large renames, big data backfills):
      - Feature-flag the new code path.
      - Run the backfill as an out-of-band script that can be paused and resumed.
      - Add the NOT NULL constraint or drop the old column in a follow-up deploy.
""")


# ==========================================================================
# DEMO (no external DB required)
# ==========================================================================

if __name__ == "__main__":
    print("=" * 70)
    print("Alembic Advanced — Pattern Reference")
    print("=" * 70)

    print("\n--- Auto-generate warnings ---")
    print_autogenerate_warnings()

    print("\n--- Common pitfalls ---")
    print_pitfalls()

    print("\n--- Stamping guide ---")
    print(STAMPING_GUIDE)

    print("\n--- Branching guide ---")
    print(BRANCHING_GUIDE)

    print("\n--- Production workflow ---")
    print(PRODUCTION_WORKFLOW)

    print("\n--- CI/CD checklist ---")
    print(CICD_CHECKLIST)

    print("\n--- Batch migration rationale ---")
    for point in BATCH_MIGRATION_RATIONALE:
        print(f"  * {point}")

    print("\n--- Advisory lock notes ---")
    for note in ADVISORY_LOCK_NOTES:
        print(f"  * {note}")

    print("\nAll pattern functions defined in this module:")
    functions = [
        "upgrade_backfill_full_name()         — data migration via shadow table",
        "upgrade_backfill_full_name_raw_sql()  — data migration via raw SQL",
        "upgrade_backfill_batch()              — large-table batch updates",
        "upgrade_rename_table_and_column()     — safe rename DDL",
        "upgrade_sqlite_batch_alter()          — SQLite batch_alter_table",
        "upgrade_create_enum()                 — Postgres ENUM creation",
        "upgrade_extend_enum()                 — Postgres ENUM extension (autocommit)",
        "upgrade_concurrent_index()            — CONCURRENTLY index (no table lock)",
        "upgrade_add_audit_table()             — reversible migration example",
        "include_object()                      — env.py filtering hook",
    ]
    for fn in functions:
        print(f"  {fn}")
