# PostgreSQL — Expand-Contract Migrations + Ghost Tables (Zero-Downtime DDL)
**Phase 2 Database | Senior Backend + Agentic AI**

## Quick Concepts
- **Expand-Contract** = 6-step pattern for zero-downtime schema changes
- **Ghost table** = MySQL pattern (gh-ost, pt-online-schema-change) — copy table, swap atomically
- **Why** = blocking DDL on 50M-row table = 30+ min downtime
- **PostgreSQL locks** = ACCESS EXCLUSIVE blocks reads + writes; ACCESS SHARE allows reads
- **Online vs offline** = online = no lock; offline = brief lock acceptable
- **Backward compat** = old code + new schema must coexist during migration window

---

## The Pattern (6 Steps)

```
DEPLOY ┌────────────────────────────────────────────────────────┐
       │                                                          │
   v1  │  Old code (reads/writes old schema)                      │
       │                                                          │
       │            ▼ Migration 1: EXPAND                         │
       │  Schema = old + new (additive only)                      │
       │                                                          │
   v2  │  Old code (still works)                                  │
       │                                                          │
       │            ▼ Migration 2: BACKFILL                       │
       │  Old data copied to new structure                        │
       │                                                          │
       │            ▼ Migration 3: DUAL-WRITE                     │
       │  New code writes to both old + new                       │
       │                                                          │
   v3  │  New code (reads new, writes both)                       │
       │                                                          │
       │            ▼ Migration 4: MIGRATE READS                  │
       │  New code reads from new only                            │
       │                                                          │
   v4  │  New code (reads new, writes new only)                   │
       │                                                          │
       │            ▼ Migration 5: STOP DUAL-WRITE                │
       │  Drop old code paths                                     │
       │                                                          │
       │            ▼ Migration 6: CONTRACT                       │
       │  Drop old column / table / index                         │
       │                                                          │
   v5  │  Clean state                                             │
       └────────────────────────────────────────────────────────┘
```

---

## What Locks What (PostgreSQL)

| DDL operation | Lock | Impact |
|---|---|---|
| `ADD COLUMN` (no default) | ACCESS EXCLUSIVE (instant) | Brief blip |
| `ADD COLUMN` with non-volatile default | ACCESS EXCLUSIVE (instant, PG 11+) | Brief blip |
| `ADD COLUMN` with volatile default | ACCESS EXCLUSIVE + rewrites table | **OUTAGE** |
| `DROP COLUMN` | ACCESS EXCLUSIVE (instant) | Brief blip; data NOT freed |
| `ALTER COLUMN TYPE` | ACCESS EXCLUSIVE + may rewrite | Often **OUTAGE** |
| `ADD CONSTRAINT NOT NULL` | ACCESS EXCLUSIVE + full scan | **OUTAGE on big table** |
| `ADD CHECK CONSTRAINT NOT VALID` | ACCESS EXCLUSIVE (instant) | Brief blip |
| `VALIDATE CONSTRAINT` | SHARE UPDATE EXCLUSIVE | Allows reads + writes |
| `CREATE INDEX` | SHARE | Blocks writes |
| `CREATE INDEX CONCURRENTLY` | SHARE UPDATE EXCLUSIVE | Allows everything |
| `DROP INDEX` | ACCESS EXCLUSIVE | Brief blip |
| `DROP INDEX CONCURRENTLY` | SHARE UPDATE EXCLUSIVE | Allows everything |
| `RENAME COLUMN` | ACCESS EXCLUSIVE (instant) | Brief blip; breaks app |
| `RENAME TABLE` | ACCESS EXCLUSIVE (instant) | Brief blip; breaks app |

**Rule:** Anything that says "ACCESS EXCLUSIVE + rewrites" = avoid on tables > 1M rows.

---

## Interview Questions & Answers

### Q1: Adding a NOT NULL column safely?

**Answer:** Naive approach takes the table offline. Use expand-contract.

```sql
-- ❌ BAD: blocks for minutes on big table
ALTER TABLE orders ADD COLUMN status_code TEXT NOT NULL DEFAULT 'pending';
-- This rewrites EVERY row → ACCESS EXCLUSIVE for duration

-- ✅ GOOD: expand-contract pattern
```

**Step 1 (EXPAND):** Add nullable column
```sql
-- Instant, brief lock
ALTER TABLE orders ADD COLUMN status_code TEXT;
```

**Step 2 (BACKFILL):** Populate in batches (separate migration)
```python
async def backfill_status_codes():
    """Run as one-off job — no transaction; many small batches."""
    while True:
        updated = await db.execute("""
            UPDATE orders
            SET status_code = CASE
                WHEN status = 'new' THEN 'pending'
                WHEN status = 'paid' THEN 'paid'
                WHEN status = 'shipped' THEN 'fulfilled'
                ELSE 'unknown'
            END
            WHERE status_code IS NULL
              AND id IN (
                  SELECT id FROM orders
                  WHERE status_code IS NULL
                  LIMIT 10000
              )
        """)
        if updated.rowcount == 0:
            break
        await asyncio.sleep(0.1)  # let other queries through
```

**Step 3 (DUAL-WRITE):** App writes both old + new
```python
class OrderService:
    async def create_order(self, status: str):
        status_code = map_status(status)
        await db.execute(
            "INSERT INTO orders (status, status_code) VALUES (:s, :sc)",
            {"s": status, "sc": status_code},
        )
```

**Step 4 (VERIFY):**
```sql
-- All rows have value?
SELECT COUNT(*) FROM orders WHERE status_code IS NULL;
-- Should be 0
```

**Step 5 (ADD CONSTRAINT):**
```sql
-- Two-phase: validate without lock
ALTER TABLE orders ADD CONSTRAINT status_code_not_null
  CHECK (status_code IS NOT NULL) NOT VALID;

-- Then validate in background (no table lock)
ALTER TABLE orders VALIDATE CONSTRAINT status_code_not_null;

-- Finally convert to proper NOT NULL (PG 12+)
ALTER TABLE orders ALTER COLUMN status_code SET NOT NULL;
-- This is fast now because constraint already validated
```

**Step 6 (CONTRACT):** Drop old column (next deploy)
```sql
ALTER TABLE orders DROP COLUMN status;
```

---

### Q2: Renaming a column without downtime?

**Answer:** Direct rename breaks all running code. Use copy-then-drop.

```python
# Bad approach
ALTER TABLE users RENAME COLUMN email TO email_address;
# → All running app servers crash because they query 'email'
```

**Safe approach:**

**Migration 1 (EXPAND):**
```sql
ALTER TABLE users ADD COLUMN email_address TEXT;
```

**Migration 2 (BACKFILL):**
```python
# Background job
await db.execute("UPDATE users SET email_address = email WHERE email_address IS NULL")
```

**Deploy v2:**
```python
# Code reads old, writes both
class UserService:
    async def get(self, id):
        user = await db.fetch_one("SELECT * FROM users WHERE id = :id", {"id": id})
        return user.email_address or user.email   # prefer new, fallback to old

    async def update(self, id, email):
        await db.execute(
            "UPDATE users SET email = :e, email_address = :e WHERE id = :id",
            {"e": email, "id": id},
        )
```

**Migration 3 (TRIGGER for safety):**
```sql
-- Keep old + new in sync via trigger (until v2 deployed everywhere)
CREATE OR REPLACE FUNCTION sync_email() RETURNS TRIGGER AS $$
BEGIN
    IF NEW.email IS NOT NULL AND NEW.email_address IS NULL THEN
        NEW.email_address := NEW.email;
    ELSIF NEW.email_address IS NOT NULL AND NEW.email IS NULL THEN
        NEW.email := NEW.email_address;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER sync_email_trigger
    BEFORE INSERT OR UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION sync_email();
```

**Deploy v3:**
```python
# Code reads new only
async def get(self, id):
    user = await db.fetch_one(...)
    return user.email_address
```

**Migration 4 (CONTRACT):**
```sql
DROP TRIGGER sync_email_trigger ON users;
DROP FUNCTION sync_email();
ALTER TABLE users DROP COLUMN email;
```

---

### Q3: Changing column type safely?

**Answer:** Most type changes rewrite the table. Use new column.

```sql
-- ❌ BAD on big table
ALTER TABLE products ALTER COLUMN price TYPE NUMERIC(10, 2);
-- Rewrites entire table

-- ✅ GOOD
-- Step 1
ALTER TABLE products ADD COLUMN price_v2 NUMERIC(10, 2);

-- Step 2 (backfill in batches)
UPDATE products SET price_v2 = price::NUMERIC(10, 2)
WHERE id IN (SELECT id FROM products WHERE price_v2 IS NULL LIMIT 10000);

-- Step 3-5: dual-write, migrate reads, etc.

-- Final
ALTER TABLE products DROP COLUMN price;
ALTER TABLE products RENAME COLUMN price_v2 TO price;  -- brief lock
```

**Types that DON'T require rewrite (PG 12+):**
- `VARCHAR(100)` → `VARCHAR(200)` (widening)
- `TEXT` → `VARCHAR` (no length issues)
- `TIMESTAMP` → `TIMESTAMPTZ` (no actual rewrite)

---

### Q4: Adding a foreign key safely?

**Answer:** Two-phase — add invalid, then validate.

```sql
-- ❌ Blocks for full table scan
ALTER TABLE orders ADD CONSTRAINT fk_user
    FOREIGN KEY (user_id) REFERENCES users(id);

-- ✅ Two-phase
ALTER TABLE orders ADD CONSTRAINT fk_user
    FOREIGN KEY (user_id) REFERENCES users(id)
    NOT VALID;   -- Doesn't validate existing rows; just future inserts

-- Then validate in background (allows reads + writes)
ALTER TABLE orders VALIDATE CONSTRAINT fk_user;
```

---

### Q5: Creating indexes without blocking writes?

**Answer:** `CREATE INDEX CONCURRENTLY` — always use this in prod.

```sql
-- ❌ Blocks ALL writes during index build
CREATE INDEX idx_orders_created ON orders(created_at);

-- ✅ Allows writes during build
CREATE INDEX CONCURRENTLY idx_orders_created ON orders(created_at);

-- Caveat: cannot be in a transaction
-- (Alembic migrations need autocommit mode)
```

**Alembic with concurrent indexes:**
```python
# alembic/versions/abc_add_orders_index.py
from alembic import op

# Each migration runs in transaction by default — must override
def upgrade():
    op.execute("COMMIT")  # exit transaction
    op.execute("CREATE INDEX CONCURRENTLY idx_orders_created ON orders(created_at)")
    op.execute("BEGIN")    # re-enter for any more ops

def downgrade():
    op.execute("COMMIT")
    op.execute("DROP INDEX CONCURRENTLY IF EXISTS idx_orders_created")
    op.execute("BEGIN")

# Better: use explicit autocommit
revision = "abc"
down_revision = "xyz"
branch_labels = None
depends_on = None

# Mark as non-transactional
def upgrade():
    pass  # see below

# Run with:
# alembic upgrade head --sql > migration.sql
# psql -f migration.sql      # outside transaction
```

**Or use `pg-osc` or similar for full automation.**

---

### Q6: gh-ost / pt-online-schema-change for MySQL?

**Answer:** Copy-table approach when PG-style DDL not possible.

**How gh-ost works:**
```
1. Create _table_gho (ghost copy) with new schema
2. Hook into binlog → replicate writes from original → ghost
3. Copy existing rows in batches
4. Once caught up, swap tables atomically (rename)
5. Drop old table
```

```bash
# Install gh-ost
brew install gh-ost   # or download binary

# Run migration
gh-ost \
  --user="dba" --password="secret" \
  --host="db.acme.com" --database="prod" --table="orders" \
  --alter="ADD COLUMN status_code VARCHAR(50)" \
  --execute \
  --max-load=Threads_running=25 \
  --critical-load=Threads_running=100 \
  --chunk-size=1000 \
  --max-lag-millis=1500 \
  --throttle-control-replicas="replica1.acme.com,replica2.acme.com"
```

**pt-online-schema-change (Percona):**
```bash
pt-online-schema-change \
  --alter "ADD COLUMN status_code VARCHAR(50)" \
  D=prod,t=orders \
  --execute
```

**For PostgreSQL: pg_repack, pg-osc, supabase/pg-online-schema-change** offer similar:
```bash
# pg_repack (most popular)
pg_repack --table orders --jobs 4
# Rebuilds table without locking; reclaims dead space
```

---

### Q7: Migration order matters — coordinate with deploy?

**Answer:** Schema migrations and code deploys are sequenced.

**Typical sequence:**
```
1. Run ADDITIVE migration (expand)
   Schema: old + new fields/tables
   Code: still using old

2. Deploy CODE v2 (dual-write)
   Schema: same
   Code: writes both, reads old

3. Run BACKFILL job
   Schema: same
   Data: new fields populated for all rows

4. Deploy CODE v3 (read new)
   Schema: same
   Code: writes both, reads new

5. Deploy CODE v4 (stop writing old)
   Schema: same
   Code: writes new only

6. Run DESTRUCTIVE migration (contract)
   Schema: old fields removed
   Code: doesn't touch removed fields
```

**Rule:** Never combine code change + destructive migration in one deploy.

---

### Q8: Migration monitoring + safety checks?

**Answer:** Pre/post checks + auto-rollback.

```python
# Check before migration
async def pre_migration_check():
    # 1. Replication lag
    lag = await db.fetch_val("""
        SELECT EXTRACT(EPOCH FROM (now() - pg_last_xact_replay_timestamp()))
        FROM pg_stat_replication
        WHERE state = 'streaming'
    """)
    if lag and lag > 5:
        raise RuntimeError(f"Replication lag too high: {lag}s")

    # 2. Long-running queries
    long_queries = await db.fetch_val("""
        SELECT COUNT(*) FROM pg_stat_activity
        WHERE state = 'active' AND now() - query_start > INTERVAL '30 seconds'
    """)
    if long_queries > 5:
        raise RuntimeError(f"{long_queries} long-running queries — wait")

    # 3. Lock conflicts
    blocked = await db.fetch_val("""
        SELECT COUNT(*) FROM pg_locks WHERE granted = FALSE
    """)
    if blocked > 0:
        raise RuntimeError(f"{blocked} blocked queries — investigate")

# Lock timeout for safety
async def safe_migrate():
    await db.execute("SET lock_timeout = '5s'")     # bail if lock not acquired in 5s
    await db.execute("SET statement_timeout = '30s'")
    try:
        await db.execute("ALTER TABLE ...")
    except asyncpg.QueryCanceledError:
        # Lock timed out — abort + alert
        await alert("Migration failed due to lock timeout")
        raise
```

**Alembic monitoring wrapper:**
```python
# alembic/env.py
from sqlalchemy import event

@event.listens_for(connection, "before_cursor_execute")
def slow_query_warn(conn, cursor, statement, params, context, executemany):
    if "ALTER TABLE" in statement.upper():
        # Send alert about DDL execution
        notify_oncall(f"DDL executing: {statement[:200]}")
```

---

## Migration Patterns Cheatsheet

| Change | Safe Approach |
|---|---|
| Add nullable column | Direct `ALTER` (instant) |
| Add NOT NULL column | Expand-contract |
| Drop column | Direct (instant — wait one deploy first) |
| Rename column | Expand-contract with trigger |
| Change type (compatible) | Direct (PG 12+) |
| Change type (incompatible) | Expand-contract via new column |
| Add index | `CREATE INDEX CONCURRENTLY` |
| Drop index | `DROP INDEX CONCURRENTLY` |
| Add FK | `ADD CONSTRAINT ... NOT VALID` + `VALIDATE` |
| Add CHECK | Same as FK pattern |
| Rename table | New table + dual-write + cutover |
| Split table | Expand-contract; very long |
| Merge tables | Trigger-based dual-write |
| Partition existing big table | `pg_partman` or manual; multi-step |

---

## Tooling Comparison

| Tool | DB | Notes |
|---|---|---|
| Alembic | PG, MySQL, SQLite | Python-friendly; manual safety |
| **pg_repack** | PG | Reclaim dead space; rebuild |
| **pg-osc** | PG | Online schema change |
| gh-ost | MySQL | GitHub-built; very mature |
| pt-online-schema-change | MySQL | Percona; old reliable |
| Liquibase | All | XML/YAML migrations |
| Flyway | All | SQL-first migrations |
| Atlas | PG, MySQL | New, declarative |
| Squawk | PG | Linter for unsafe migrations |
| **Strong Migrations** | Rails (PG) | Catches risky DDL pre-deploy |

---

## Pre-Deploy Migration Linting

```bash
# Squawk — PG linter
pip install pg-osc squawk
squawk migrations/abc_add_column.sql
# Warns: adding NOT NULL column without default; running CREATE INDEX (not CONCURRENTLY); etc.
```

```yaml
# .github/workflows/migration-safety.yml
- name: Check migrations
  run: |
    for f in alembic/versions/new_*.py; do
      squawk "$f" --pg-version 16
    done
```

---

## Production Gotchas

| Gotcha | Fix |
|---|---|
| Foreign key validation locks table | Use `NOT VALID` then `VALIDATE` |
| Long migration blocks replicas | Throttle; check replica lag |
| `DROP COLUMN` keeps space | Run `VACUUM FULL` or `pg_repack` |
| Index build fails partway | `DROP INDEX CONCURRENTLY IF EXISTS` first |
| Migration in transaction with `CONCURRENTLY` | Auto-commit; separate migration |
| Trigger lag during backfill | Reduce batch size + sleep |
| Constraint validation OOM | Split into smaller checks |
| Migration order out of sync | Use deployment freeze during migration |
| Two-deploy gap forgotten | Make checklist; track in JIRA |
| Rollback impossible | Always test rollback path |

---

## Senior-level Checklist

- [ ] Squawk / Strong Migrations in CI
- [ ] `lock_timeout` set in migration scripts
- [ ] `statement_timeout` set
- [ ] `CREATE INDEX CONCURRENTLY` for all index builds
- [ ] `NOT VALID` for new constraints, then validate
- [ ] Backfill in batches with sleep
- [ ] Replication lag monitoring during migration
- [ ] Pre-migration health check (long queries, locks)
- [ ] Rollback plan documented + tested
- [ ] Code + schema deploys sequenced (never combined for destructive)
- [ ] pg_repack scheduled monthly for space reclamation
- [ ] Migration playbooks for common patterns
- [ ] On-call alerted before any DDL in prod
- [ ] Game day migrations rehearsed in staging

---

## Related Docs
- `09_postgresql_ha_read_replicas.md` — replication
- `10_postgresql_partitioning_sharding.md` — partitioning
- `21_isolation_levels_anomalies.md` — transaction semantics
- `22_alembic_advanced.md` — Alembic patterns
- `24_zero_downtime_migrations.md` — earlier patterns
- `25_cdc_debezium_postgresql.md` — CDC for sync

## External References
- Strong Migrations: https://github.com/ankane/strong_migrations
- Squawk: https://squawkhq.com
- pg_repack: https://reorg.github.io/pg_repack
- gh-ost: https://github.com/github/gh-ost
- pt-online-schema-change: https://www.percona.com/doc/percona-toolkit
- Braintree's zero-downtime PG migrations: https://www.braintreepayments.com/blog/safe-operations-for-high-volume-postgresql/
