# 24 — Zero-Downtime DB Migrations

> The expand-contract pattern. The art of evolving schema while production keeps serving traffic.

---

## The Problem

Old code expects column `email_addr`. New code expects `email`.

Single deploy with column rename:
```sql
ALTER TABLE users RENAME COLUMN email_addr TO email;
```

Time T0: migration starts. Old code (still in some pods) → boom, AttributeError.

---

## The Expand-Contract Pattern

Four phases, each backward-compatible.

```
Phase 1 EXPAND:    Add new alongside old.
Phase 2 MIGRATE:   Backfill data old → new.
Phase 3 CUTOVER:   Switch code to read/write new only.
Phase 4 CONTRACT:  Remove old.
```

Each phase deployed independently. No single deploy breaks old or new.

---

## Pattern A — Rename Column

### Phase 1: Add new column (deploy migration only)
```sql
ALTER TABLE users ADD COLUMN email TEXT;
CREATE INDEX CONCURRENTLY ix_users_email ON users(email);
```

Old code still reads/writes `email_addr`. New code doesn't exist yet.

### Phase 2: Dual-write (deploy code)
```python
class User:
    @property
    def email(self):
        return self._email or self.email_addr

    @email.setter
    def email(self, value):
        self._email = value
        self.email_addr = value   # write to both during transition
```

Both columns kept in sync.

### Phase 3: Backfill old → new
```python
# Backfill script (idempotent, batched)
async def backfill():
    while True:
        rows = await db.fetch(
            "SELECT id, email_addr FROM users WHERE email IS NULL LIMIT 1000"
        )
        if not rows: break
        ids = [r.id for r in rows]
        await db.execute(
            "UPDATE users SET email = email_addr WHERE id = ANY($1)",
            ids
        )
```

Run as background job. Can take days for big tables.

### Phase 4: Switch reads to new
Deploy code that reads only `email`:
```python
class User:
    email = Column("email", Text)
    # email_addr deprecated; not read
```

Writes still go to both for safety. Old code (rolling deploy) still alive in some pods reading `email_addr`, so don't drop yet.

### Phase 5: Drop dual-write
Once all pods on new code, drop dual-write:
```python
class User:
    email = Column("email", Text)
```

### Phase 6: Drop old column
Final migration:
```sql
ALTER TABLE users DROP COLUMN email_addr;
DROP INDEX ix_users_email_addr;
```

**Total: 6 deploys over weeks.** Painful, but zero downtime.

---

## Pattern B — Add NOT NULL Column

### Naive (downtime)
```sql
ALTER TABLE users ADD COLUMN phone TEXT NOT NULL DEFAULT '';
```

Locks table while default applied. 1M rows = minutes of lock.

### Zero-downtime
```sql
-- Step 1: nullable
ALTER TABLE users ADD COLUMN phone TEXT;
```
Instant.

```python
# Step 2: backfill batched
UPDATE users SET phone = '' WHERE phone IS NULL AND id BETWEEN 0 AND 10000;
-- repeat in batches
```

```sql
-- Step 3: add NOT NULL constraint
-- In Postgres 12+, use NOT VALID first, then validate
ALTER TABLE users ALTER COLUMN phone SET NOT NULL;
```

In Postgres 11 and earlier, this scans the table. In 12+, it's fast IF default isn't volatile.

---

## Pattern C — Drop Column

### Issue
Old code still has the column in queries.

```python
class User(Model):
    legacy_field = CharField()  # to remove
```

If we drop it before removing from code:
```
SQL: SELECT id, email, legacy_field FROM users → error: column doesn't exist
```

### Zero-downtime
```
Phase 1: Stop writing to it (deploy code change). Migration table column unchanged.
Phase 2: Stop reading from it (deploy code change). Column still in DB.
Phase 3: Drop column (migration). All code already past the read.
```

In Django: mark field as removed before dropping:
```python
class Meta:
    managed = False  # tell Django not to manage this field
```

Then drop in migration.

---

## Pattern D — Change Column Type

```sql
ALTER COLUMN price TYPE NUMERIC(10, 2) USING price::numeric;
```

This rewrites the column → table lock for large tables.

### Zero-downtime
```
Phase 1: Add new column with target type.
  ALTER TABLE products ADD COLUMN price_v2 NUMERIC(10, 2);
Phase 2: Backfill.
  UPDATE products SET price_v2 = price::numeric;   (in batches)
Phase 3: Triggers to keep in sync.
  Or dual-write in app.
Phase 4: Switch reads.
Phase 5: Drop old column.
```

Same as rename, basically.

---

## Pattern E — Index Creation

Default `CREATE INDEX` locks table for writes.

```sql
-- Zero-downtime:
CREATE INDEX CONCURRENTLY ix_users_email ON users(email);
```

CONCURRENTLY:
- Doesn't block reads/writes.
- Takes 2x time.
- Multiple passes through table.
- Can fail (e.g., unique constraint violations) → leaves invalid index.

Validate after:
```sql
SELECT * FROM pg_stat_user_indexes WHERE indexrelname = 'ix_users_email';
```

If invalid: drop and retry.

---

## Pattern F — Adding a Foreign Key

```sql
-- Naive (locks table while validating)
ALTER TABLE orders ADD CONSTRAINT fk_user FOREIGN KEY (user_id) REFERENCES users(id);
```

### Zero-downtime
```sql
-- Step 1: add as NOT VALID (no scan)
ALTER TABLE orders ADD CONSTRAINT fk_user
  FOREIGN KEY (user_id) REFERENCES users(id) NOT VALID;

-- Step 2: validate (scans but doesn't lock)
ALTER TABLE orders VALIDATE CONSTRAINT fk_user;
```

---

## Pattern G — Renaming Table

Same expand-contract:
```sql
-- Phase 1: create new with same schema
CREATE TABLE users_new (LIKE users INCLUDING ALL);

-- Phase 2: dual-write (via trigger or app)
CREATE TRIGGER mirror_to_new
AFTER INSERT OR UPDATE OR DELETE ON users
FOR EACH ROW EXECUTE FUNCTION mirror_users();

-- Phase 3: backfill historical
INSERT INTO users_new SELECT * FROM users WHERE NOT EXISTS (...);

-- Phase 4: switch app to read new
-- Phase 5: drop old
DROP TABLE users;
ALTER TABLE users_new RENAME TO users;
```

Or use views as indirection layer.

---

## Patterns Cheat Sheet

| Operation | Direct | Zero-downtime |
|---|---|---|
| Add column nullable | Fast | OK |
| Add column NOT NULL with default | Slow (locks) | Add nullable → backfill → NOT NULL |
| Drop column | OK in DB; breaks queries | Drop usage → wait → drop column |
| Rename column | Breaks queries | Add new → dual-write → backfill → drop old |
| Change type | Slow (locks) | Add new → backfill → drop old |
| Add index | Slow (locks writes) | CONCURRENTLY |
| Add FK | Slow (validates) | NOT VALID → VALIDATE separately |
| Add unique constraint | Slow + may fail | CREATE UNIQUE INDEX CONCURRENTLY → ADD CONSTRAINT USING INDEX |

---

## Feature Flags + Migrations

Combine with feature flags for safety:

```python
if feature_enabled("use_new_email_field", user):
    user.email = "..."  # new code path
else:
    user.email_addr = "..."  # old code path
```

Roll out to 1% → 10% → 50% → 100%. Easy rollback.

---

## Backfill at Scale

For tables with 100M+ rows:

### Idempotent
```sql
UPDATE users SET phone = '' WHERE phone IS NULL AND id BETWEEN $1 AND $2;
```

Can re-run safely.

### Chunked
Process 10K rows at a time. Sleep between batches to give DB breathing room.

### Resume on crash
Store progress in a table:
```sql
CREATE TABLE migration_progress (
    migration_name TEXT PRIMARY KEY,
    last_id_processed BIGINT,
    updated_at TIMESTAMPTZ
);
```

Worker resumes from `last_id_processed`.

### Throttle
```python
async def backfill_with_throttle():
    while True:
        await process_batch()
        await asyncio.sleep(1)   # 1 sec between batches
```

Monitor DB load; back off if WAL backup or replica lag grows.

---

## Database Replication Considerations

### Lag during migrations
Heavy migration on primary → WAL accumulates → replica lags.

Mitigate:
- Run migration during low traffic.
- Throttle so primary's WAL drain rate exceeds generation.
- Add temporary replicas with more compute.

### Schema migrations replicate
Postgres logical replication replicates DDL only in newer versions. Plan accordingly.

---

## Tools

### gh-ost (GitHub's MySQL tool)
Online schema migration without downtime by creating shadow table, copying data, swapping.

### pt-online-schema-change (Percona MySQL)
Similar pattern.

### pg_repack
Reclaims wasted space; rebuilds tables online for Postgres.

### Strong_migrations (Ruby gem; Python equivalents exist)
Lints migrations for production safety.

---

## Migration Checklist (Production)

Before deploying any migration:
- [ ] Tested on staging with prod-sized data.
- [ ] Estimated lock duration (seconds OK, minutes risky).
- [ ] No NOT NULL without default for large tables.
- [ ] CONCURRENTLY for any new index.
- [ ] CASCADE thought through (won't cascade-delete millions of rows).
- [ ] Reversible (down migration tested).
- [ ] Data backfill separate from schema change.
- [ ] App code backward + forward compatible.
- [ ] Monitoring in place (replication lag, errors).
- [ ] Rollback plan documented.

---

## Real-World Story

**The "RENAME COLUMN at 5pm Friday" disaster.**

Team renamed a column on a 50M-row table via single migration. Lock acquired immediately. App threads piled up waiting. Within 30 seconds, every API request was timing out. Site down for 18 minutes during checkout peak.

Lessons:
- Never schema-migrate during peak.
- Never single-deploy a column rename.
- Always estimate lock duration first.

After: team adopted expand-contract pattern. Every migration goes through schema-only PR + data PR + cutover PR + cleanup PR pipeline.

---

## TL;DR

- **Expand-Contract**: add new alongside old → migrate → cutover → drop.
- Multiple deploys, each backward-compatible.
- CONCURRENTLY indexes, NOT VALID FKs.
- Backfills: batched, idempotent, throttled.
- Feature flags for risky changes.
- Test on staging with realistic data.
- Never single-deploy a rename / type change / required column.
- Monitor replication lag during migrations.
- Track progress in a table for crash recovery.

**Mantra:** "Each phase keeps both old and new code working. If only one direction works, you have downtime risk."
