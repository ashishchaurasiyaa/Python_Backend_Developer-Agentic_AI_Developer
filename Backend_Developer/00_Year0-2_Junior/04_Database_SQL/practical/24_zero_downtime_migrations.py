"""
Zero-Downtime Database Migrations — Production Patterns
========================================================

Covers the expand-contract pattern and every sub-pattern a backend engineer
encounters in production: column rename, NOT NULL addition, column drop,
type change, concurrent index creation, NOT VALID foreign keys, table rename,
batched backfill with crash recovery, feature-flag gating, and the production
migration checklist.

External infra (PostgreSQL, asyncpg) is referenced but not required for the
module to import.  The `__main__` block runs a fully self-contained simulation
using an in-memory SQLite database so you can execute this file without any
external dependencies and see all concepts exercised.

Usage
-----
    python 24_zero_downtime_migrations.py           # run the demo
    python -m py_compile 24_zero_downtime_migrations.py && echo OK  # syntax only
"""

# pip install asyncpg sqlalchemy[asyncio] aiosqlite

from __future__ import annotations

import asyncio
import logging
import time
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

log = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s | %(name)s | %(message)s",
)


# ==========================================================================
# 1. EXPAND-CONTRACT PATTERN — OVERVIEW
# ==========================================================================
#
# Rule: each migration phase must leave the database in a state that is
# simultaneously compatible with the old code (currently in production) AND
# the new code (about to be deployed).
#
# Phase sequence for a column rename  email_addr → email:
#
#   Phase 1  EXPAND    Add `email` column alongside `email_addr`  (migration)
#   Phase 2  DUAL-WRITE Deploy app that writes to both columns   (app deploy)
#   Phase 3  BACKFILL  Copy email_addr → email for existing rows (background job)
#   Phase 4  CUTOVER   Deploy app that reads only `email`        (app deploy)
#   Phase 5  CLEANUP   Remove dual-write; single write to `email` only
#   Phase 6  CONTRACT  Drop `email_addr` column                  (migration)
#
# Each phase is independently deployable.  The old and new app versions can
# coexist during rolling deploy without any pod crashing.


class MigrationPhase(str, Enum):
    EXPAND = "expand"
    DUAL_WRITE = "dual_write"
    BACKFILL = "backfill"
    CUTOVER = "cutover"
    CLEANUP = "cleanup"
    CONTRACT = "contract"


# ==========================================================================
# 2. SQL STATEMENT LIBRARY — RAW DDL TEMPLATES
# ==========================================================================
#
# These are the exact SQL statements you would run in each pattern.
# Written as module-level strings so a migration framework (Alembic, Flyway)
# can embed them.  Never run DDL statements inside a transaction on large
# tables in production — Postgres holds a lock for the full duration.

class DDL:
    """Ready-to-use SQL statement fragments for zero-downtime schema changes."""

    # --- Pattern A: Rename column -------------------------------------------

    RENAME_EXPAND = """
        -- Phase 1: Add NEW column (does not touch existing data)
        ALTER TABLE users ADD COLUMN email TEXT;
        -- Index concurrently so writers are not blocked
        CREATE INDEX CONCURRENTLY ix_users_email ON users(email);
    """

    RENAME_CONTRACT = """
        -- Phase 6: Drop OLD column after all pods read only email
        ALTER TABLE users DROP COLUMN email_addr;
        DROP INDEX IF EXISTS ix_users_email_addr;
    """

    # --- Pattern B: Add NOT NULL column -------------------------------------

    # WRONG — locks table while default is applied to every row
    ADD_NOT_NULL_NAIVE = """
        -- DO NOT USE on large tables: full table lock until default applied
        ALTER TABLE users ADD COLUMN phone TEXT NOT NULL DEFAULT '';
    """

    # RIGHT — three steps, each instant or batched
    ADD_NOT_NULL_STEP1 = """
        -- Step 1: Add nullable — instant, no lock beyond metadata
        ALTER TABLE users ADD COLUMN phone TEXT;
    """
    # Step 2: backfill in application (see backfill() below)
    ADD_NOT_NULL_STEP3 = """
        -- Step 3: Enforce NOT NULL after every row is populated
        -- Postgres 12+: fast because the planner sees the default is constant
        ALTER TABLE users ALTER COLUMN phone SET NOT NULL;
    """

    # --- Pattern C: Drop column ---------------------------------------------
    # Order: stop writing → stop reading → drop column (three separate deploys)

    DROP_COLUMN_SAFE = """
        -- Final step only after ALL app pods no longer reference the column
        ALTER TABLE products DROP COLUMN legacy_field;
    """

    # --- Pattern D: Change column type --------------------------------------

    CHANGE_TYPE_NAIVE = """
        -- DO NOT USE on large tables: rewrites every row, holds table lock
        ALTER TABLE products ALTER COLUMN price TYPE NUMERIC(10,2)
            USING price::numeric;
    """

    CHANGE_TYPE_EXPAND = """
        -- Phase 1: Add new typed column
        ALTER TABLE products ADD COLUMN price_v2 NUMERIC(10, 2);
        -- Phase 2: Backfill (in application batches)
        -- Phase 3: Trigger or dual-write to keep columns in sync
        -- Phase 4: Switch reads → price_v2
        -- Phase 5: Drop price column
    """

    # --- Pattern E: Index creation ------------------------------------------

    CREATE_INDEX_NAIVE = """
        -- DO NOT USE on busy tables: blocks writes until complete
        CREATE INDEX ix_orders_user_id ON orders(user_id);
    """

    CREATE_INDEX_CONCURRENT = """
        -- Correct: does not hold write lock; two passes through table
        -- Can fail if unique constraint violated → leaves INVALID index
        CREATE INDEX CONCURRENTLY ix_orders_user_id ON orders(user_id);

        -- Verify afterwards; drop and retry if pg_stat_user_indexes shows invalid=true
        SELECT indexrelname, idx_scan, idx_tup_read
        FROM pg_stat_user_indexes
        WHERE indexrelname = 'ix_orders_user_id';
    """

    # --- Pattern F: Add foreign key -----------------------------------------

    ADD_FK_NAIVE = """
        -- Locks table while it scans all rows to validate constraint
        ALTER TABLE orders
            ADD CONSTRAINT fk_user
            FOREIGN KEY (user_id) REFERENCES users(id);
    """

    ADD_FK_ZERO_DOWNTIME = """
        -- Step 1: Mark NOT VALID → constraint added without full-table scan
        ALTER TABLE orders
            ADD CONSTRAINT fk_user
            FOREIGN KEY (user_id) REFERENCES users(id) NOT VALID;

        -- Step 2: Validate separately — scans rows but takes ShareUpdateExclusiveLock,
        --         which does NOT block reads or writes
        ALTER TABLE orders VALIDATE CONSTRAINT fk_user;
    """

    # --- Pattern G: Rename table --------------------------------------------

    RENAME_TABLE_EXPAND = """
        -- Phase 1: Create new table with same schema
        CREATE TABLE users_new (LIKE users INCLUDING ALL);

        -- Phase 2: Mirror writes via trigger
        CREATE TRIGGER mirror_to_users_new
        AFTER INSERT OR UPDATE OR DELETE ON users
        FOR EACH ROW EXECUTE FUNCTION mirror_users_fn();

        -- Phase 3: Backfill historical rows
        INSERT INTO users_new
        SELECT * FROM users
        WHERE id NOT IN (SELECT id FROM users_new);

        -- Phase 4: Switch app reads to users_new
        -- Phase 5: Drop old table and rename new table
        DROP TABLE users;
        ALTER TABLE users_new RENAME TO users;
    """

    # --- Add unique constraint via concurrent index -------------------------

    ADD_UNIQUE_CONSTRAINT = """
        -- DO NOT USE: scans + locks
        ALTER TABLE users ADD CONSTRAINT uq_users_email UNIQUE (email);

        -- CORRECT: build the index without locks, then attach it
        CREATE UNIQUE INDEX CONCURRENTLY ix_uq_users_email ON users(email);
        ALTER TABLE users ADD CONSTRAINT uq_users_email
            UNIQUE USING INDEX ix_uq_users_email;
    """


# ==========================================================================
# 3. DUAL-WRITE MODEL — PATTERN A (COLUMN RENAME)
# ==========================================================================

class UserModel:
    """
    ORM model fragment illustrating dual-write during a column rename.

    During Phase 2 / Phase 3 the model writes to both columns so that any
    old-code pod still reading email_addr keeps working, and any new-code pod
    reading email also gets the value.
    """

    def __init__(self, email_addr: str) -> None:
        # Legacy column — populated from DB
        self.email_addr: str = email_addr
        # New column — starts populated from legacy value
        self._email: Optional[str] = None

    # -----------------------------------------------------------------------
    # Phase 2-3: Dual-write property
    # -----------------------------------------------------------------------
    @property
    def email(self) -> str:
        """Read from new column; fall back to legacy column if not yet backfilled."""
        return self._email or self.email_addr

    @email.setter
    def email(self, value: str) -> None:
        """Write to both columns during the transition window."""
        self._email = value
        self.email_addr = value  # keeps legacy column in sync

    # -----------------------------------------------------------------------
    # Phase 5: Single-write (after all pods on new code)
    # -----------------------------------------------------------------------
    # class UserModelV2:
    #     email = Column("email", Text)
    #     # email_addr no longer referenced; column still in DB until Phase 6


# ==========================================================================
# 4. BATCHED IDEMPOTENT BACKFILL
# ==========================================================================

class BackfillConfig:
    """Tuning knobs for large-table backfill jobs."""

    def __init__(
        self,
        batch_size: int = 1_000,
        sleep_between_batches: float = 0.1,
        progress_table: str = "migration_progress",
    ) -> None:
        self.batch_size = batch_size                    # rows per UPDATE statement
        self.sleep_between_batches = sleep_between_batches  # seconds between batches
        self.progress_table = progress_table


async def backfill_email_column(
    db,                            # asyncpg Connection or compatible
    config: Optional[BackfillConfig] = None,
) -> int:
    """
    Phase 3: Backfill email_addr → email for all NULL rows.

    Idempotent: safe to re-run.  Chunked: processes `batch_size` rows per
    statement so lock duration stays short.  Throttled: sleeps between batches
    to keep replication lag low.

    Returns total rows updated.
    """
    if config is None:
        config = BackfillConfig()

    total_updated = 0

    while True:
        rows = await db.fetch(
            """
            SELECT id, email_addr
            FROM users
            WHERE email IS NULL
            LIMIT $1
            """,
            config.batch_size,
        )
        if not rows:
            break

        ids = [r["id"] for r in rows]
        updated = await db.execute(
            "UPDATE users SET email = email_addr WHERE id = ANY($1::bigint[])",
            ids,
        )
        count = int(updated.split()[-1])  # "UPDATE N"
        total_updated += count
        log.info("backfill_email: updated %d rows (total so far: %d)", count, total_updated)

        await asyncio.sleep(config.sleep_between_batches)

    log.info("backfill_email: complete — %d rows updated", total_updated)
    return total_updated


async def backfill_phone_column(
    db,
    config: Optional[BackfillConfig] = None,
) -> int:
    """
    Pattern B: Backfill phone = '' for rows where phone IS NULL.
    Must complete before the NOT NULL constraint is added.
    """
    if config is None:
        config = BackfillConfig()

    total_updated = 0
    last_id = 0

    while True:
        rows = await db.fetch(
            """
            SELECT id FROM users
            WHERE phone IS NULL AND id > $1
            ORDER BY id
            LIMIT $2
            """,
            last_id,
            config.batch_size,
        )
        if not rows:
            break

        ids = [r["id"] for r in rows]
        await db.execute(
            "UPDATE users SET phone = '' WHERE id = ANY($1::bigint[])",
            ids,
        )
        last_id = ids[-1]
        total_updated += len(ids)
        log.info("backfill_phone: processed up to id=%d (%d total)", last_id, total_updated)

        await asyncio.sleep(config.sleep_between_batches)

    return total_updated


# ==========================================================================
# 5. CRASH-RECOVERY PROGRESS TRACKING
# ==========================================================================
#
# For tables with 100 M+ rows the backfill can run for hours.
# Storing progress lets the worker resume from where it crashed.

CREATE_PROGRESS_TABLE = """
CREATE TABLE IF NOT EXISTS migration_progress (
    migration_name TEXT PRIMARY KEY,
    last_id_processed BIGINT NOT NULL DEFAULT 0,
    rows_processed    BIGINT NOT NULL DEFAULT 0,
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
"""


async def get_progress(db, migration_name: str) -> int:
    """Return last_id_processed for this migration, or 0 if not started."""
    row = await db.fetchrow(
        "SELECT last_id_processed FROM migration_progress WHERE migration_name = $1",
        migration_name,
    )
    return row["last_id_processed"] if row else 0


async def save_progress(db, migration_name: str, last_id: int, rows_processed: int) -> None:
    """Upsert progress record — safe to call after every batch."""
    await db.execute(
        """
        INSERT INTO migration_progress (migration_name, last_id_processed, rows_processed, updated_at)
        VALUES ($1, $2, $3, NOW())
        ON CONFLICT (migration_name) DO UPDATE
            SET last_id_processed = EXCLUDED.last_id_processed,
                rows_processed    = migration_progress.rows_processed + EXCLUDED.rows_processed,
                updated_at        = NOW()
        """,
        migration_name,
        last_id,
        rows_processed,
    )


async def resumable_backfill(
    db,
    migration_name: str,
    config: Optional[BackfillConfig] = None,
) -> int:
    """
    Resumable backfill for Pattern B (phone column).

    Reads last_id_processed from migration_progress and starts from there.
    After each batch, writes the new checkpoint.  If the process crashes and
    restarts it picks up exactly where it left off — at most one batch of
    redundant work.
    """
    if config is None:
        config = BackfillConfig()

    last_id = await get_progress(db, migration_name)
    total_updated = 0
    log.info("%s: resuming from id=%d", migration_name, last_id)

    while True:
        rows = await db.fetch(
            """
            SELECT id FROM users
            WHERE phone IS NULL AND id > $1
            ORDER BY id
            LIMIT $2
            """,
            last_id,
            config.batch_size,
        )
        if not rows:
            break

        ids = [r["id"] for r in rows]
        await db.execute(
            "UPDATE users SET phone = '' WHERE id = ANY($1::bigint[])",
            ids,
        )
        last_id = ids[-1]
        batch_count = len(ids)
        total_updated += batch_count

        await save_progress(db, migration_name, last_id, batch_count)
        log.info("%s: checkpoint id=%d (%d rows this session)", migration_name, last_id, total_updated)

        await asyncio.sleep(config.sleep_between_batches)

    return total_updated


# ==========================================================================
# 6. FEATURE-FLAG GATING
# ==========================================================================
#
# Combine schema migration phases with feature flags so you can roll out
# the new code path to 1 % → 10 % → 50 % → 100 % and roll back instantly.

class FeatureFlagService:
    """
    Minimal in-memory feature-flag registry.
    In production back this with LaunchDarkly, Unleash, or a DB table.
    """

    def __init__(self) -> None:
        self._flags: Dict[str, float] = {}  # flag → rollout fraction [0.0, 1.0]

    def set_rollout(self, flag: str, percent: float) -> None:
        """percent: 0.0 (off) to 1.0 (fully on)."""
        if not 0.0 <= percent <= 1.0:
            raise ValueError(f"percent must be in [0, 1], got {percent}")
        self._flags[flag] = percent
        log.info("feature_flag: %s → %.0f%%", flag, percent * 100)

    def is_enabled(self, flag: str, user_id: int) -> bool:
        """Stable per-user bucketing: same user always gets the same result."""
        rollout = self._flags.get(flag, 0.0)
        if rollout == 0.0:
            return False
        if rollout == 1.0:
            return True
        # Deterministic bucket: hash(flag + user_id) mod 100
        bucket = hash(f"{flag}:{user_id}") % 100
        return bucket < int(rollout * 100)


flags = FeatureFlagService()


def write_user_email(user: UserModel, new_email: str, user_id: int) -> None:
    """
    Example of feature-flag gated cutover.

    Phase 2-3: Both code paths write to the model; the property handles
    dual-write to both DB columns.

    Phase 4+:  Once flag reaches 100 %, the old path can be deleted.
    """
    if flags.is_enabled("use_new_email_field", user_id):
        # New code path: write to the new `email` column via the property
        user.email = new_email
    else:
        # Legacy code path: write only to `email_addr`
        user.email_addr = new_email


# ==========================================================================
# 7. MIGRATION SAFETY ANALYZER
# ==========================================================================
#
# A lightweight linter that mirrors what the Ruby `strong_migrations` gem
# does — it inspects a DDL statement and flags patterns that are dangerous
# on large production tables.

class SafetyWarning:
    """Holds a single safety finding from the migration analyzer."""

    def __init__(self, severity: str, message: str, suggestion: str) -> None:
        self.severity = severity      # "ERROR" | "WARNING"
        self.message = message
        self.suggestion = suggestion


def analyze_migration_safety(sql: str) -> List[SafetyWarning]:
    """
    Inspect raw SQL for anti-patterns known to cause downtime.

    Returns a list of SafetyWarning objects.  An empty list means no issues
    were detected (not a guarantee of safety).
    """
    warnings: List[SafetyWarning] = []
    sql_upper = sql.upper().strip()

    # Rule 1: plain RENAME COLUMN
    if "RENAME COLUMN" in sql_upper:
        warnings.append(SafetyWarning(
            severity="ERROR",
            message="RENAME COLUMN breaks any query that references the old name.",
            suggestion=(
                "Use expand-contract: ADD COLUMN new_name, dual-write, backfill, "
                "switch reads, then DROP COLUMN old_name."
            ),
        ))

    # Rule 2: ADD COLUMN ... NOT NULL DEFAULT without Postgres 11+ optimization
    if "ADD COLUMN" in sql_upper and "NOT NULL" in sql_upper and "DEFAULT" in sql_upper:
        warnings.append(SafetyWarning(
            severity="WARNING",
            message=(
                "ADD COLUMN NOT NULL DEFAULT rewrites every row in Postgres < 11; "
                "even in Postgres 11+ with a volatile default it locks."
            ),
            suggestion=(
                "Add the column as nullable, backfill in batches, then "
                "ALTER COLUMN SET NOT NULL."
            ),
        ))

    # Rule 3: CREATE INDEX without CONCURRENTLY
    if "CREATE INDEX" in sql_upper and "CONCURRENTLY" not in sql_upper:
        warnings.append(SafetyWarning(
            severity="ERROR",
            message="CREATE INDEX without CONCURRENTLY blocks all writes until complete.",
            suggestion="Use CREATE INDEX CONCURRENTLY instead.",
        ))

    # Rule 4: ADD CONSTRAINT FOREIGN KEY without NOT VALID
    if "ADD CONSTRAINT" in sql_upper and "FOREIGN KEY" in sql_upper and "NOT VALID" not in sql_upper:
        warnings.append(SafetyWarning(
            severity="ERROR",
            message=(
                "ADD CONSTRAINT ... FOREIGN KEY validates all existing rows, "
                "holding a lock for the full scan."
            ),
            suggestion=(
                "Add constraint with NOT VALID, then run VALIDATE CONSTRAINT separately "
                "(takes ShareUpdateExclusiveLock — does not block reads/writes)."
            ),
        ))

    # Rule 5: DROP COLUMN is usually safe, but warn about CASCADE
    if "DROP COLUMN" in sql_upper and "CASCADE" in sql_upper:
        warnings.append(SafetyWarning(
            severity="WARNING",
            message="DROP COLUMN CASCADE may silently drop dependent views or constraints.",
            suggestion="Audit all dependent objects before using CASCADE.",
        ))

    # Rule 6: ALTER TABLE ... ALTER COLUMN ... TYPE
    if "ALTER COLUMN" in sql_upper and " TYPE " in sql_upper:
        warnings.append(SafetyWarning(
            severity="ERROR",
            message=(
                "ALTER COLUMN TYPE rewrites every row, holding an AccessExclusiveLock "
                "for the full duration."
            ),
            suggestion=(
                "Use expand-contract: add a new typed column, backfill via app or trigger, "
                "switch reads, then drop the old column."
            ),
        ))

    return warnings


def print_safety_report(label: str, sql: str) -> None:
    """Run analyzer and pretty-print results."""
    issues = analyze_migration_safety(sql)
    status = "PASS" if not issues else f"{len(issues)} ISSUE(S)"
    print(f"\n[Safety Check] {label} — {status}")
    for w in issues:
        print(f"  [{w.severity}] {w.message}")
        print(f"          Suggestion: {w.suggestion}")


# ==========================================================================
# 8. REPLICATION LAG MONITOR (illustrative)
# ==========================================================================

async def check_replication_lag(db) -> List[Dict[str, Any]]:
    """
    Query pg_stat_replication to see how far replicas lag behind primary.
    Call this during and after a heavy migration; pause if lag exceeds threshold.

    Requires: connected to primary; user has pg_monitor privilege.
    """
    rows = await db.fetch(
        """
        SELECT
            client_addr,
            state,
            write_lag,
            flush_lag,
            replay_lag
        FROM pg_stat_replication
        ORDER BY replay_lag DESC NULLS LAST
        """
    )
    return [dict(r) for r in rows]


async def wait_for_replication_catchup(
    db,
    max_lag_seconds: float = 30.0,
    poll_interval: float = 5.0,
) -> None:
    """
    Block until the most-lagged replica is within max_lag_seconds of the primary.
    Insert between migration phases on systems with physical replication.
    """
    while True:
        stats = await check_replication_lag(db)
        if not stats:
            log.info("wait_replication: no replicas detected, proceeding")
            return

        max_replay = max(
            (r["replay_lag"].total_seconds() if r["replay_lag"] else 0.0)
            for r in stats
        )
        if max_replay <= max_lag_seconds:
            log.info("wait_replication: lag %.1fs — OK to continue", max_replay)
            return

        log.warning(
            "wait_replication: lag %.1fs > %.1fs threshold — sleeping %.1fs",
            max_replay, max_lag_seconds, poll_interval,
        )
        await asyncio.sleep(poll_interval)


# ==========================================================================
# 9. PRODUCTION MIGRATION CHECKLIST
# ==========================================================================

PRODUCTION_CHECKLIST = """
PRODUCTION MIGRATION CHECKLIST
===============================
Before running ANY schema migration in production:

  [ ] Tested on staging with production-sized data (same row counts, same indexes).
  [ ] Estimated lock duration: seconds OK, minutes are a red flag.
  [ ] No ADD COLUMN NOT NULL DEFAULT on a table > 100k rows (Postgres < 11).
  [ ] All new indexes use CREATE INDEX CONCURRENTLY.
  [ ] Foreign key constraints added with NOT VALID first, validated separately.
  [ ] CASCADE effects audited; no unintended cascaded deletes.
  [ ] Down migration (rollback) tested and documented.
  [ ] Data backfill split from schema-change migration into separate deployment.
  [ ] Application code is backward-compatible with both old and new schema.
  [ ] Replication lag monitored during migration; alert threshold set.
  [ ] Error rate / latency dashboards open during and after deploy.
  [ ] Rollback plan documented and rehearsed.
  [ ] Migration scheduled for low-traffic window.
  [ ] On-call engineer available for full migration + 30-minute soak window.

If any box is unchecked, do not proceed.
"""


# ==========================================================================
# 10. SELF-CONTAINED DEMO (SQLite via aiosqlite)
# ==========================================================================
#
# Demonstrates: dual-write model, safety analyzer, feature-flag gating,
# and a simulated batched backfill using an in-memory SQLite database.
# No external PostgreSQL connection required.

async def _sqlite_demo() -> None:
    """
    Run a simulated zero-downtime migration workflow on an in-memory SQLite DB.

    SQLite does not support all PostgreSQL DDL features (e.g., CONCURRENTLY,
    NOT VALID, ALTER COLUMN TYPE), so we simulate the logic at the Python
    layer and show the DDL that would be executed against a real PostgreSQL
    instance.
    """
    # pip install aiosqlite
    import aiosqlite  # type: ignore

    print("\n" + "=" * 70)
    print("ZERO-DOWNTIME MIGRATIONS — DEMO (in-memory SQLite)")
    print("=" * 70)

    # -----------------------------------------------------------------------
    # Section A — Safety Analyzer
    # -----------------------------------------------------------------------
    print("\n--- SECTION A: Safety Analyzer ---")

    print_safety_report(
        "RENAME COLUMN (direct)",
        "ALTER TABLE users RENAME COLUMN email_addr TO email;",
    )
    print_safety_report(
        "CREATE INDEX (non-concurrent)",
        "CREATE INDEX ix_users_email ON users(email);",
    )
    print_safety_report(
        "ADD FK (without NOT VALID)",
        "ALTER TABLE orders ADD CONSTRAINT fk_user FOREIGN KEY (user_id) REFERENCES users(id);",
    )
    print_safety_report(
        "ADD COLUMN NOT NULL DEFAULT",
        "ALTER TABLE users ADD COLUMN phone TEXT NOT NULL DEFAULT '';",
    )
    print_safety_report(
        "ALTER COLUMN TYPE",
        "ALTER TABLE products ALTER COLUMN price TYPE NUMERIC(10,2) USING price::numeric;",
    )
    print_safety_report(
        "CREATE INDEX CONCURRENTLY (correct)",
        "CREATE INDEX CONCURRENTLY ix_users_email ON users(email);",
    )
    print_safety_report(
        "ADD FK NOT VALID (correct)",
        "ALTER TABLE orders ADD CONSTRAINT fk_user FOREIGN KEY (user_id) REFERENCES users(id) NOT VALID;",
    )

    # -----------------------------------------------------------------------
    # Section B — Dual-write model
    # -----------------------------------------------------------------------
    print("\n--- SECTION B: Dual-Write Model (Pattern A — Column Rename) ---")

    user = UserModel(email_addr="alice@example.com")
    print(f"  Initial email_addr : {user.email_addr}")
    print(f"  Initial email (via property) : {user.email}")

    # Phase 2: New code writes through the dual-write property
    user.email = "alice.new@example.com"
    print(f"\n  After dual-write:")
    print(f"    email_addr (old column) : {user.email_addr}")
    print(f"    email      (new column) : {user.email}")

    # -----------------------------------------------------------------------
    # Section C — Feature-flag gating
    # -----------------------------------------------------------------------
    print("\n--- SECTION C: Feature-Flag Gated Cutover ---")

    flags.set_rollout("use_new_email_field", 0.0)
    user2 = UserModel(email_addr="bob@example.com")
    write_user_email(user2, "bob.updated@example.com", user_id=42)
    print(f"  [0% rollout] email_addr={user2.email_addr}, _email={user2._email}")

    flags.set_rollout("use_new_email_field", 1.0)
    user3 = UserModel(email_addr="carol@example.com")
    write_user_email(user3, "carol.updated@example.com", user_id=99)
    print(f"  [100% rollout] email_addr={user3.email_addr}, _email={user3._email}")

    # -----------------------------------------------------------------------
    # Section D — Simulated batched backfill via SQLite
    # -----------------------------------------------------------------------
    print("\n--- SECTION D: Batched Backfill Simulation (SQLite) ---")

    async with aiosqlite.connect(":memory:") as db:
        db.row_factory = aiosqlite.Row

        # Phase 0: Original table (only email_addr, no email column yet)
        await db.execute(
            "CREATE TABLE users (id INTEGER PRIMARY KEY, email_addr TEXT, email TEXT)"
        )
        # Seed 25 rows with email IS NULL (simulating rows before Phase 3)
        await db.executemany(
            "INSERT INTO users (email_addr, email) VALUES (?, NULL)",
            [(f"user{i}@old.example.com",) for i in range(1, 26)],
        )
        await db.commit()

        count_before = (await (await db.execute("SELECT COUNT(*) FROM users WHERE email IS NULL")).fetchone())[0]
        print(f"  Rows with email IS NULL before backfill: {count_before}")

        # Batched backfill: process 10 rows at a time
        BATCH = 10
        total_updated = 0
        while True:
            async with db.execute(
                "SELECT id, email_addr FROM users WHERE email IS NULL LIMIT ?", (BATCH,)
            ) as cursor:
                rows = await cursor.fetchall()

            if not rows:
                break

            ids = [r["id"] for r in rows]
            placeholders = ",".join("?" for _ in ids)
            await db.execute(
                f"UPDATE users SET email = email_addr WHERE id IN ({placeholders})",
                ids,
            )
            await db.commit()
            total_updated += len(ids)
            log.info("  backfill batch: updated %d rows (total: %d)", len(ids), total_updated)
            # No real sleep in demo — would be asyncio.sleep(0.1) in production

        count_after = (await (await db.execute("SELECT COUNT(*) FROM users WHERE email IS NULL")).fetchone())[0]
        print(f"  Rows with email IS NULL after backfill: {count_after}")
        print(f"  Total rows backfilled: {total_updated}")

        # Sample verification
        async with db.execute("SELECT id, email_addr, email FROM users LIMIT 3") as cur:
            sample = await cur.fetchall()
        print("  Sample rows after backfill:")
        for row in sample:
            print(f"    id={row['id']} email_addr={row['email_addr']} email={row['email']}")

    # -----------------------------------------------------------------------
    # Section E — Migration checklist
    # -----------------------------------------------------------------------
    print("\n--- SECTION E: Production Migration Checklist ---")
    print(PRODUCTION_CHECKLIST)

    print("=" * 70)
    print("DEMO COMPLETE")
    print("=" * 70)


# ==========================================================================
# 11. QUICK-REFERENCE DDL REFERENCE CARD
# ==========================================================================
#
# Keep this comment block as a cheat-sheet when writing Alembic migration files.

_REFERENCE_CARD = {
    "Add nullable column":          "ALTER TABLE t ADD COLUMN col TEXT;  -- instant",
    "Add NOT NULL column":          "Add nullable → backfill → SET NOT NULL",
    "Drop column":                  "Stop writing → stop reading → DROP COLUMN",
    "Rename column":                "Expand → dual-write → backfill → cutover → contract",
    "Change column type":           "Expand → dual-write → backfill → cutover → contract",
    "Add index":                    "CREATE INDEX CONCURRENTLY ...",
    "Add FK":                       "ADD CONSTRAINT ... NOT VALID → VALIDATE CONSTRAINT",
    "Add unique constraint":        "CREATE UNIQUE INDEX CONCURRENTLY → ADD CONSTRAINT USING INDEX",
    "Rename table":                 "Create new → trigger mirror → backfill → switch → drop old",
}


if __name__ == "__main__":
    asyncio.run(_sqlite_demo())
