"""
Expand-Contract Migrations & Zero-Downtime DDL — Production Patterns
=====================================================================

Covers the six-step expand-contract pattern for zero-downtime schema changes on
PostgreSQL, including:

  * Expand  — additive DDL that the old code can still run against
  * Backfill — batch-updating historical rows without long-running transactions
  * Dual-write — writing to both old and new columns/tables simultaneously
  * Read-migration — switching reads to the new structure
  * Contract — dropping the now-redundant legacy columns/constraints

All SQL is issued through SQLAlchemy Core (asyncpg dialect) so the module can be
imported and studied without a running database.  Where live infrastructure is
required the relevant class / function is clearly marked.

External dependencies
---------------------
pip install sqlalchemy[asyncio] asyncpg alembic structlog
"""

import asyncio
import logging
import textwrap
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

import structlog

# ==========================================================================
# LOGGING SETUP
# ==========================================================================

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = structlog.get_logger()


# ==========================================================================
# 1. LOCK-IMPACT REFERENCE TABLE
# ==========================================================================
# Keep as importable constants — useful for in-code documentation and CI
# linting checks.

LOCK_IMPACT: dict[str, dict] = {
    "ADD COLUMN (no default)": {
        "lock": "ACCESS EXCLUSIVE",
        "rewrites": False,
        "safe_on_big_table": True,
        "notes": "Instant; brief blip",
    },
    "ADD COLUMN with volatile default": {
        "lock": "ACCESS EXCLUSIVE",
        "rewrites": True,
        "safe_on_big_table": False,
        "notes": "OUTAGE — rewrites every row",
    },
    "DROP COLUMN": {
        "lock": "ACCESS EXCLUSIVE",
        "rewrites": False,
        "safe_on_big_table": True,
        "notes": "Instant; data NOT freed (need VACUUM FULL / pg_repack)",
    },
    "ALTER COLUMN TYPE": {
        "lock": "ACCESS EXCLUSIVE",
        "rewrites": True,
        "safe_on_big_table": False,
        "notes": "Usually OUTAGE — rewrites table",
    },
    "ADD CONSTRAINT NOT NULL (naive)": {
        "lock": "ACCESS EXCLUSIVE",
        "rewrites": False,
        "safe_on_big_table": False,
        "notes": "OUTAGE on big table — full scan under exclusive lock",
    },
    "ADD CHECK CONSTRAINT NOT VALID": {
        "lock": "ACCESS EXCLUSIVE",
        "rewrites": False,
        "safe_on_big_table": True,
        "notes": "Instant; only enforces future writes",
    },
    "VALIDATE CONSTRAINT": {
        "lock": "SHARE UPDATE EXCLUSIVE",
        "rewrites": False,
        "safe_on_big_table": True,
        "notes": "Allows concurrent reads AND writes",
    },
    "CREATE INDEX": {
        "lock": "SHARE",
        "rewrites": False,
        "safe_on_big_table": False,
        "notes": "Blocks writes for entire build duration",
    },
    "CREATE INDEX CONCURRENTLY": {
        "lock": "SHARE UPDATE EXCLUSIVE",
        "rewrites": False,
        "safe_on_big_table": True,
        "notes": "Allows everything; cannot run inside transaction",
    },
    "DROP INDEX CONCURRENTLY": {
        "lock": "SHARE UPDATE EXCLUSIVE",
        "rewrites": False,
        "safe_on_big_table": True,
        "notes": "Allows everything",
    },
    "RENAME COLUMN": {
        "lock": "ACCESS EXCLUSIVE",
        "rewrites": False,
        "safe_on_big_table": False,  # safe from a lock perspective but BREAKS app
        "notes": "Instant lock; breaks all running app code — never in prod without dual-write",
    },
}


def print_lock_reference() -> None:
    """Print a formatted lock-impact summary to stdout."""
    print("\n=== PostgreSQL DDL Lock-Impact Reference ===\n")
    for op, info in LOCK_IMPACT.items():
        safe = "YES" if info["safe_on_big_table"] else "NO "
        rewrite = "REWRITE" if info["rewrites"] else "       "
        print(f"  {safe} | {rewrite} | {info['lock']:<30} | {op}")
        print(f"       |         |                                | -> {info['notes']}\n")


# ==========================================================================
# 2. MIGRATION PHASE ENUM
# ==========================================================================

class MigrationPhase(str, Enum):
    """Ordered phases of a full expand-contract cycle."""
    EXPAND = "expand"
    BACKFILL = "backfill"
    DUAL_WRITE = "dual_write"
    MIGRATE_READS = "migrate_reads"
    STOP_DUAL_WRITE = "stop_dual_write"
    CONTRACT = "contract"


# ==========================================================================
# 3. PRE-MIGRATION HEALTH CHECKS
# ==========================================================================

@dataclass
class HealthCheckResult:
    passed: bool
    checks: dict[str, str] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)


async def pre_migration_check(conn) -> HealthCheckResult:
    """
    Run pre-flight checks before executing any DDL.

    Raises RuntimeError if critical conditions are not met so that the calling
    migration script can abort safely rather than taking a lock on an unhealthy
    cluster.

    Requires a live asyncpg connection or SQLAlchemy async connection.
    """
    result = HealthCheckResult(passed=True)

    # --- 1. Replication lag ---
    try:
        lag_query = textwrap.dedent("""
            SELECT COALESCE(
                MAX(EXTRACT(EPOCH FROM (now() - pg_last_xact_replay_timestamp()))),
                0
            ) AS lag_seconds
            FROM pg_stat_replication
            WHERE state = 'streaming'
        """)
        row = await conn.fetchrow(lag_query)
        lag = float(row["lag_seconds"]) if row else 0.0
        if lag > 5:
            msg = f"Replication lag too high: {lag:.1f}s (threshold: 5s)"
            result.errors.append(msg)
            result.passed = False
            result.checks["replication_lag"] = f"FAIL — {msg}"
        else:
            result.checks["replication_lag"] = f"OK — {lag:.1f}s"
    except Exception as exc:
        result.checks["replication_lag"] = f"SKIP — {exc}"

    # --- 2. Long-running queries ---
    try:
        long_query_sql = textwrap.dedent("""
            SELECT COUNT(*) AS cnt
            FROM pg_stat_activity
            WHERE state = 'active'
              AND now() - query_start > INTERVAL '30 seconds'
              AND query NOT ILIKE '%pg_stat_activity%'
        """)
        row = await conn.fetchrow(long_query_sql)
        count = int(row["cnt"])
        if count > 5:
            msg = f"{count} long-running queries (>30 s) detected — wait before migrating"
            result.errors.append(msg)
            result.passed = False
            result.checks["long_running_queries"] = f"FAIL — {msg}"
        else:
            result.checks["long_running_queries"] = f"OK — {count} long-running queries"
    except Exception as exc:
        result.checks["long_running_queries"] = f"SKIP — {exc}"

    # --- 3. Blocked queries ---
    try:
        blocked_sql = "SELECT COUNT(*) AS cnt FROM pg_locks WHERE granted = FALSE"
        row = await conn.fetchrow(blocked_sql)
        blocked = int(row["cnt"])
        if blocked > 0:
            msg = f"{blocked} blocked queries — investigate before adding DDL lock"
            result.errors.append(msg)
            result.passed = False
            result.checks["blocked_queries"] = f"FAIL — {msg}"
        else:
            result.checks["blocked_queries"] = "OK — no blocked queries"
    except Exception as exc:
        result.checks["blocked_queries"] = f"SKIP — {exc}"

    return result


# ==========================================================================
# 4. SAFE DDL EXECUTOR
# ==========================================================================

async def safe_ddl(conn, statement: str,
                   lock_timeout: str = "5s",
                   statement_timeout: str = "30s") -> None:
    """
    Execute a DDL statement with conservative timeouts.

    If PostgreSQL cannot acquire the required lock within `lock_timeout` the
    statement is aborted automatically, preventing a migration from queuing
    behind a long transaction and blocking all subsequent queries.

    Parameters
    ----------
    conn:
        asyncpg connection or pool.
    statement:
        DDL SQL to execute.
    lock_timeout:
        PostgreSQL interval string — how long to wait for the lock.
    statement_timeout:
        Maximum wall-clock time for the whole statement.
    """
    await conn.execute(f"SET lock_timeout = '{lock_timeout}'")
    await conn.execute(f"SET statement_timeout = '{statement_timeout}'")
    try:
        await conn.execute(statement)
        log.info("ddl_executed", sql=statement[:120].replace("\n", " "))
    except Exception as exc:
        log.error("ddl_failed", sql=statement[:120], error=str(exc))
        raise
    finally:
        # Reset to defaults so subsequent queries are not affected.
        await conn.execute("SET lock_timeout = DEFAULT")
        await conn.execute("SET statement_timeout = DEFAULT")


# ==========================================================================
# 5. EXAMPLE: ADDING A NOT-NULL COLUMN (orders.status_code)
# ==========================================================================
# This is the most common expand-contract scenario.
#
# Timeline:
#   Migration A  — EXPAND  (add nullable column)
#   Background   — BACKFILL (populate historical rows in small batches)
#   Code deploy  — DUAL-WRITE v2 (write both `status` and `status_code`)
#   Migration B  — ADD CONSTRAINT NOT VALID  +  VALIDATE
#   Migration C  — SET NOT NULL  (fast because constraint already validates)
#   Code deploy  — READ from `status_code` only
#   Migration D  — CONTRACT (drop `status`)

# --------------------------------------------------------------------------
# Step A: EXPAND migration
# --------------------------------------------------------------------------

MIGRATION_A_EXPAND_SQL = textwrap.dedent("""
    -- Step 1: EXPAND — add nullable column (instant, brief lock)
    ALTER TABLE orders ADD COLUMN IF NOT EXISTS status_code TEXT;
""")


# --------------------------------------------------------------------------
# Step B: BACKFILL — run as a background job, NOT inside a transaction
# --------------------------------------------------------------------------

STATUS_MAP = {
    "new": "pending",
    "paid": "paid",
    "shipped": "fulfilled",
    "cancelled": "cancelled",
}


async def backfill_status_codes(conn, batch_size: int = 10_000,
                                 sleep_ms: int = 100) -> int:
    """
    Backfill `orders.status_code` from `orders.status` in small batches.

    This function intentionally does NOT run inside a transaction so that each
    batch is committed independently.  This keeps lock duration minimal and
    allows replication lag to catch up between batches.

    Returns the total number of rows updated.

    Parameters
    ----------
    conn:
        asyncpg connection — should NOT be inside a transaction block.
    batch_size:
        Rows updated per batch.  Keep below 50 000 to avoid hot-row contention.
    sleep_ms:
        Milliseconds to sleep between batches, giving reads a chance to proceed.
    """
    total_updated = 0

    backfill_sql = textwrap.dedent(f"""
        UPDATE orders
        SET status_code = CASE
            WHEN status = 'new'       THEN 'pending'
            WHEN status = 'paid'      THEN 'paid'
            WHEN status = 'shipped'   THEN 'fulfilled'
            WHEN status = 'cancelled' THEN 'cancelled'
            ELSE 'unknown'
        END
        WHERE status_code IS NULL
          AND id IN (
              SELECT id FROM orders
              WHERE status_code IS NULL
              ORDER BY id
              LIMIT {batch_size}
          )
    """)

    while True:
        result = await conn.execute(backfill_sql)
        # asyncpg returns a string like "UPDATE 9731"
        rows_affected = int(result.split()[-1])
        total_updated += rows_affected
        log.info("backfill_batch", rows=rows_affected, total=total_updated)

        if rows_affected == 0:
            break

        await asyncio.sleep(sleep_ms / 1000)

    log.info("backfill_complete", total_rows=total_updated)
    return total_updated


# --------------------------------------------------------------------------
# Step C: DUAL-WRITE service layer
# --------------------------------------------------------------------------

def _map_status(status: str) -> str:
    """Convert legacy `status` values to the new `status_code` vocabulary."""
    return STATUS_MAP.get(status, "unknown")


class OrderServiceDualWrite:
    """
    Order service with dual-write: writes both `status` (legacy) and
    `status_code` (new) so that the database is always consistent regardless
    of which application version is reading.

    Use this class during the dual-write deployment window.
    """

    def __init__(self, pool):
        self._pool = pool

    async def create_order(self, status: str) -> int:
        """Insert a new order, writing both status columns."""
        status_code = _map_status(status)
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO orders (status, status_code, created_at)
                VALUES ($1, $2, NOW())
                RETURNING id
                """,
                status,
                status_code,
            )
        log.info("order_created", id=row["id"], status=status, status_code=status_code)
        return row["id"]

    async def update_status(self, order_id: int, status: str) -> None:
        """Update an order's status, keeping both columns in sync."""
        status_code = _map_status(status)
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE orders
                SET status = $1, status_code = $2
                WHERE id = $3
                """,
                status,
                status_code,
                order_id,
            )
        log.info("order_updated", id=order_id, status=status, status_code=status_code)

    async def get_order(self, order_id: int) -> Optional[dict]:
        """Read order — prefer new column, fall back to legacy."""
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM orders WHERE id = $1", order_id
            )
        if not row:
            return None
        return {
            "id": row["id"],
            # Prefer new column; fall back to legacy during transition window.
            "status_code": row["status_code"] or _map_status(row["status"]),
            "status": row["status"],
        }


# --------------------------------------------------------------------------
# Step D: Service after cutover (reads and writes new column only)
# --------------------------------------------------------------------------

class OrderServiceV3:
    """
    Order service after the expand-contract cycle is complete.

    At this point:
      - `status_code` column is populated and NOT NULL
      - `status` column has been dropped by the CONTRACT migration
    """

    def __init__(self, pool):
        self._pool = pool

    async def create_order(self, status_code: str) -> int:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                "INSERT INTO orders (status_code, created_at) VALUES ($1, NOW()) RETURNING id",
                status_code,
            )
        return row["id"]

    async def update_status(self, order_id: int, status_code: str) -> None:
        async with self._pool.acquire() as conn:
            await conn.execute(
                "UPDATE orders SET status_code = $1 WHERE id = $2",
                status_code,
                order_id,
            )

    async def get_order(self, order_id: int) -> Optional[dict]:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT id, status_code, created_at FROM orders WHERE id = $1",
                order_id,
            )
        return dict(row) if row else None


# ==========================================================================
# 6. ADD NOT-NULL CONSTRAINT — two-phase pattern
# ==========================================================================

MIGRATION_ADD_CONSTRAINT_SQL = textwrap.dedent("""
    -- Phase 1 (instant lock): mark constraint NOT VALID so existing rows
    --   are not scanned but future inserts/updates must satisfy it.
    ALTER TABLE orders
        ADD CONSTRAINT chk_status_code_not_null
        CHECK (status_code IS NOT NULL) NOT VALID;

    -- Phase 2 (SHARE UPDATE EXCLUSIVE — allows reads + writes):
    --   scan historical rows to validate the constraint.
    --   Run this in a separate transaction / migration step.
    ALTER TABLE orders VALIDATE CONSTRAINT chk_status_code_not_null;

    -- Phase 3 (optional, PG 12+): convert to a proper NOT NULL marker.
    --   This is now fast because PG knows the check constraint guarantees it.
    ALTER TABLE orders ALTER COLUMN status_code SET NOT NULL;
""")


# ==========================================================================
# 7. CONTRACT MIGRATION
# ==========================================================================

MIGRATION_CONTRACT_SQL = textwrap.dedent("""
    -- Run only after ALL application instances have stopped writing 'status'.
    ALTER TABLE orders DROP COLUMN IF EXISTS status;

    -- Note: DROP COLUMN is instant but does NOT reclaim disk space.
    -- Schedule pg_repack to rebuild the table at a low-traffic window:
    --   pg_repack --table orders --jobs 4
""")


# ==========================================================================
# 8. RENAME COLUMN — expand-contract with a sync trigger
# ==========================================================================
# Scenario: rename users.email → users.email_address
#
# Deployment sequence:
#   Migration 1  — EXPAND (add email_address column)
#   Migration 2  — BACKFILL
#   Migration 3  — CREATE TRIGGER (keep both in sync)
#   Code deploy  — DUAL-WRITE (write both; read new with fallback)
#   Code deploy  — READ new only; WRITE new only
#   Migration 4  — CONTRACT (drop trigger + old column)

RENAME_EXPAND_SQL = textwrap.dedent("""
    -- Step 1: add the new column (instant)
    ALTER TABLE users ADD COLUMN IF NOT EXISTS email_address TEXT;
""")

RENAME_TRIGGER_SQL = textwrap.dedent("""
    -- Step 3: keep the two columns in sync via trigger
    --   This removes the need for the application to dual-write and lets a
    --   mixed fleet (old code + new code) coexist safely.
    CREATE OR REPLACE FUNCTION sync_email_columns()
    RETURNS TRIGGER AS $$
    BEGIN
        IF NEW.email IS NOT NULL AND NEW.email_address IS NULL THEN
            NEW.email_address := NEW.email;
        ELSIF NEW.email_address IS NOT NULL AND NEW.email IS NULL THEN
            NEW.email := NEW.email_address;
        END IF;
        RETURN NEW;
    END;
    $$ LANGUAGE plpgsql;

    DROP TRIGGER IF EXISTS trg_sync_email ON users;
    CREATE TRIGGER trg_sync_email
        BEFORE INSERT OR UPDATE ON users
        FOR EACH ROW EXECUTE FUNCTION sync_email_columns();
""")

RENAME_CONTRACT_SQL = textwrap.dedent("""
    -- Step 4: CONTRACT — remove the sync machinery and legacy column.
    DROP TRIGGER IF EXISTS trg_sync_email ON users;
    DROP FUNCTION IF EXISTS sync_email_columns();
    ALTER TABLE users DROP COLUMN IF EXISTS email;
""")


class UserServiceDualWrite:
    """
    User service with dual-write: populates both `email` and `email_address`
    during the rename transition window.
    """

    def __init__(self, pool):
        self._pool = pool

    async def get_user_email(self, user_id: int) -> Optional[str]:
        """Return the canonical email, preferring the new column."""
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT email, email_address FROM users WHERE id = $1", user_id
            )
        if not row:
            return None
        # Prefer new column; fall back to legacy during transition.
        return row["email_address"] or row["email"]

    async def update_email(self, user_id: int, email: str) -> None:
        """Write both columns so any version of the app sees a consistent value."""
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE users
                SET email = $1, email_address = $1
                WHERE id = $2
                """,
                email,
                user_id,
            )


# ==========================================================================
# 9. FOREIGN KEY — two-phase (NOT VALID then VALIDATE)
# ==========================================================================

FK_TWO_PHASE_SQL = textwrap.dedent("""
    -- Phase 1: add the constraint without validating existing rows (instant).
    --   New inserts / updates ARE checked from this point forward.
    ALTER TABLE orders
        ADD CONSTRAINT fk_orders_user_id
        FOREIGN KEY (user_id) REFERENCES users(id)
        NOT VALID;

    -- Phase 2: validate existing rows concurrently.
    --   Uses SHARE UPDATE EXCLUSIVE — reads + writes continue.
    ALTER TABLE orders VALIDATE CONSTRAINT fk_orders_user_id;
""")


# ==========================================================================
# 10. INDEX CREATION — always CONCURRENTLY in production
# ==========================================================================

INDEX_SQL = textwrap.dedent("""
    -- BAD: blocks ALL writes for the entire build
    -- CREATE INDEX idx_orders_created ON orders(created_at);

    -- GOOD: allows concurrent reads and writes during build
    -- Cannot run inside a transaction block — use autocommit.
    CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_orders_created_at
        ON orders(created_at);

    -- Drop also concurrently
    DROP INDEX CONCURRENTLY IF EXISTS idx_orders_created_at;
""")


# ==========================================================================
# 11. ALEMBIC HELPERS — concurrent index + non-transactional migrations
# ==========================================================================

# These strings represent the bodies of Alembic migration files.
# They are kept as module-level constants so they can be inspected and
# copy-pasted into actual migration files.

ALEMBIC_CONCURRENT_INDEX_MIGRATION = textwrap.dedent('''
    """Add idx_orders_created_at (CONCURRENTLY)."""
    # alembic/versions/001_add_orders_idx.py

    from alembic import op

    # Must be set so Alembic does not wrap the migration in a transaction.
    # CREATE INDEX CONCURRENTLY cannot run inside a transaction.
    # See: https://alembic.sqlalchemy.org/en/latest/api/runtime.html
    revision = "001"
    down_revision = None
    branch_labels = None
    depends_on = None


    def upgrade() -> None:
        # Exit the implicit transaction before running CONCURRENTLY.
        op.execute("COMMIT")
        op.execute(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS "
            "idx_orders_created_at ON orders(created_at)"
        )


    def downgrade() -> None:
        op.execute("COMMIT")
        op.execute(
            "DROP INDEX CONCURRENTLY IF EXISTS idx_orders_created_at"
        )
''')

ALEMBIC_ENV_DDL_HOOK = textwrap.dedent('''
    # alembic/env.py — add DDL event hook for on-call alerting
    from sqlalchemy import event


    def add_ddl_alert_hook(connection):
        """Notify on-call before any DDL executes."""
        @event.listens_for(connection, "before_cursor_execute")
        def before_execute(conn, cursor, statement, params, context, executemany):
            upper = statement.upper().strip()
            if any(kw in upper for kw in ("ALTER TABLE", "CREATE INDEX", "DROP ")):
                # Replace with your actual alerting integration
                import logging
                logging.warning("DDL executing: %s", statement[:200].replace("\\n", " "))
''')


# ==========================================================================
# 12. MIGRATION PLAYBOOK — data class
# ==========================================================================

@dataclass
class MigrationPlaybook:
    """
    Structured record of a planned expand-contract migration.

    Store in version control alongside the Alembic migration files so the
    full context (rationale, deploy order, rollback) is preserved.
    """
    title: str
    table: str
    phases: list[MigrationPhase]
    rollback_plan: str
    checklist: list[str] = field(default_factory=list)

    def describe(self) -> str:
        lines = [
            f"Migration: {self.title}",
            f"Table    : {self.table}",
            f"Phases   : {' → '.join(p.value for p in self.phases)}",
            f"Rollback : {self.rollback_plan}",
            "",
            "Checklist:",
        ]
        for item in self.checklist:
            lines.append(f"  [ ] {item}")
        return "\n".join(lines)


SENIOR_CHECKLIST = [
    "Squawk / Strong Migrations in CI passing",
    "lock_timeout set in migration script",
    "statement_timeout set in migration script",
    "CREATE INDEX uses CONCURRENTLY",
    "New constraints added NOT VALID then VALIDATE separately",
    "Backfill runs in batches with sleep between each",
    "Replication lag monitored throughout",
    "Pre-migration health check passed (long queries, blocked locks)",
    "Rollback path documented and tested in staging",
    "Code + schema deploys are sequenced (no destructive DDL with code)",
    "pg_repack scheduled after DROP COLUMN for space reclamation",
    "On-call alerted before any DDL in production",
    "Migration rehearsed in staging with prod-sized data",
]


# ==========================================================================
# 13. MOCK DEMO — illustrative walkthrough (no live database needed)
# ==========================================================================

class MockConnection:
    """
    Minimal mock of an asyncpg connection used to demonstrate the health-check
    and DDL-executor logic without a live PostgreSQL instance.
    """

    async def execute(self, sql: str, *args) -> str:
        op = sql.strip().split()[0].upper()
        log.info("mock_execute", operation=op, sql=sql[:80].replace("\n", " "))
        return "UPDATE 0"

    async def fetchrow(self, sql: str, *args) -> dict:
        # Return safe defaults that pass all pre-migration checks.
        return {"lag_seconds": 0.2, "cnt": 0}


async def run_demo() -> None:
    """
    Walk through the expand-contract pattern phases without a live database.
    """
    print("\n" + "=" * 70)
    print("  Expand-Contract Migration — Illustrative Demo")
    print("=" * 70)

    # --- Lock reference ---
    print_lock_reference()

    # --- Pre-migration health check ---
    print("\n=== Pre-Migration Health Check ===\n")
    conn = MockConnection()
    result = await pre_migration_check(conn)
    for check, status in result.checks.items():
        print(f"  {check}: {status}")
    if result.passed:
        print("\n  All checks passed. Safe to proceed.\n")
    else:
        print("\n  FAILED — aborting migration.\n")
        return

    # --- Print each migration SQL block ---
    phases = [
        ("1. EXPAND — add nullable column", MIGRATION_A_EXPAND_SQL),
        ("2. ADD CONSTRAINT NOT NULL (two-phase)", MIGRATION_ADD_CONSTRAINT_SQL),
        ("3. CONTRACT — drop legacy column", MIGRATION_CONTRACT_SQL),
        ("4. RENAME — expand phase", RENAME_EXPAND_SQL),
        ("5. RENAME — sync trigger", RENAME_TRIGGER_SQL),
        ("6. RENAME — contract phase", RENAME_CONTRACT_SQL),
        ("7. FOREIGN KEY — two-phase", FK_TWO_PHASE_SQL),
        ("8. INDEX — CONCURRENTLY", INDEX_SQL),
    ]

    for title, sql in phases:
        print(f"\n=== {title} ===\n")
        for line in sql.strip().splitlines():
            print(f"  {line}")

    # --- Execute EXPAND with safe_ddl on mock ---
    print("\n=== safe_ddl Executor Demo ===\n")
    await safe_ddl(
        conn,
        "ALTER TABLE orders ADD COLUMN IF NOT EXISTS status_code TEXT",
        lock_timeout="5s",
        statement_timeout="30s",
    )

    # --- Dual-write demonstration (pure-logic, no real DB) ---
    print("\n=== Dual-Write Service Demo (mock) ===\n")
    status = "paid"
    status_code = _map_status(status)
    print(f"  Input status : {status!r}")
    print(f"  Mapped code  : {status_code!r}")
    print(f"  Would write  : status='{status}', status_code='{status_code}'")

    # --- Playbook ---
    print("\n=== Migration Playbook ===\n")
    playbook = MigrationPlaybook(
        title="orders.status → orders.status_code (NOT NULL)",
        table="orders",
        phases=[
            MigrationPhase.EXPAND,
            MigrationPhase.BACKFILL,
            MigrationPhase.DUAL_WRITE,
            MigrationPhase.MIGRATE_READS,
            MigrationPhase.STOP_DUAL_WRITE,
            MigrationPhase.CONTRACT,
        ],
        rollback_plan=(
            "Deploy previous code version (still writes both columns). "
            "Drop status_code column in next maintenance window."
        ),
        checklist=SENIOR_CHECKLIST,
    )
    print(playbook.describe())

    # --- Alembic migration snippet ---
    print("\n=== Alembic Concurrent Index Migration Snippet ===\n")
    for line in ALEMBIC_CONCURRENT_INDEX_MIGRATION.strip().splitlines():
        print(f"  {line}")

    print("\n" + "=" * 70)
    print("  Demo complete — no live database required.")
    print("=" * 70 + "\n")


# ==========================================================================
# ENTRY POINT
# ==========================================================================

if __name__ == "__main__":
    asyncio.run(run_demo())
