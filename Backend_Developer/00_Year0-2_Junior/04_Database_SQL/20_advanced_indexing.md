# Advanced Indexing — Covering, Partial, Expression

## Why It Matters

Basic single-column index = beginner. Senior 5 YOE knows:
- **Covering indexes** → eliminate table lookup
- **Partial indexes** → smaller, faster, targeted
- **Expression indexes** → index computed values
- **Multi-column order** → wrong order = unused index
- **Index types** → B-tree, GIN, GiST, BRIN, Hash — when each

Senior interview: "Query slow despite index. Why?" → wrong index type, wrong column order, predicate not sargable, index bloat.

---

## Core Concepts

### Covering Index (INCLUDE clause)

```sql
-- Without INCLUDE — index lookup + table fetch
CREATE INDEX idx_users_email ON users (email);
SELECT name, email FROM users WHERE email = 'x@y.com';
-- Plan: Index Scan + Heap Lookup (need 'name')


-- With INCLUDE — fully covered (Index Only Scan)
CREATE INDEX idx_users_email_inc ON users (email) INCLUDE (name);
SELECT name, email FROM users WHERE email = 'x@y.com';
-- Plan: Index Only Scan — no table fetch
```

**Benefit:** Saves random I/O. Critical for high-frequency lookup-then-read patterns.

### Partial Index

```sql
-- Index only rows matching condition
CREATE INDEX idx_orders_unpaid
    ON orders (created_at)
    WHERE status = 'pending';
```

**Use cases:**
- Job queue (only pending jobs)
- Soft delete (only `deleted_at IS NULL`)
- Active users (only `is_active = true`)
- Hot data (recent month)

**Benefit:** Smaller index → faster scan + write. May fit fully in memory.

### Expression Index

```sql
-- Without — full scan needed
CREATE INDEX idx_users_email ON users (email);
SELECT * FROM users WHERE LOWER(email) = 'foo@bar.com';
-- Index NOT used (function applied to column)


-- With — index used
CREATE INDEX idx_users_email_lower ON users (LOWER(email));
SELECT * FROM users WHERE LOWER(email) = 'foo@bar.com';


-- Other examples
CREATE INDEX idx_users_year ON users (EXTRACT(YEAR FROM created_at));
CREATE INDEX idx_articles_json_status ON articles ((meta->>'status'));
```

### Multi-Column Index Order

```sql
CREATE INDEX idx_orders_user_status_date ON orders (user_id, status, created_at);

-- Used:
WHERE user_id = X                          -- yes
WHERE user_id = X AND status = 'paid'      -- yes
WHERE user_id = X AND status = 'paid' AND created_at > 'X'  -- yes

-- NOT used:
WHERE status = 'paid'                      -- no (skips leading column)
WHERE created_at > 'X'                     -- no
```

**Rule:** Leftmost-prefix. Order by selectivity descending (more selective columns first).

### Index Types

| Type | Best For | Example |
|---|---|---|
| **B-tree** | Equality, range, sorting (default) | `WHERE id = X`, `ORDER BY` |
| **Hash** | Equality only | `WHERE name = 'x'` (rarely needed) |
| **GIN** | Multi-value (arrays, JSON, full-text) | `tags @> ARRAY['x']` |
| **GiST** | Geometric, ranges, full-text | PostGIS spatial |
| **BRIN** | Huge sequential tables (logs) | Date-partitioned data |

```sql
CREATE INDEX idx_articles_tags ON articles USING GIN (tags);          -- array
CREATE INDEX idx_events_location ON events USING GIST (location);     -- geom
CREATE INDEX idx_logs_time ON logs USING BRIN (timestamp);            -- huge log table
CREATE INDEX idx_articles_search ON articles USING GIN (to_tsvector('english', body));
```

### Index-Only Scan Conditions

PostgreSQL uses index-only scan when:
1. All columns needed are in index (or INCLUDE)
2. Visibility map says all pages all-visible (recent VACUUM)

```sql
-- Force vacuum to update visibility map
VACUUM ANALYZE users;
```

### CONCURRENT Index Creation

```sql
-- Normal — locks table during build (BAD for prod)
CREATE INDEX idx_x ON huge_table (col);

-- Concurrent — no lock, takes longer (use in prod)
CREATE INDEX CONCURRENTLY idx_x ON huge_table (col);

-- If fails, leftover invalid index
SELECT indexrelid::regclass FROM pg_index WHERE NOT indisvalid;
DROP INDEX CONCURRENTLY idx_x;
-- Retry
```

### Index Bloat

After many UPDATEs/DELETEs, index has dead entries. Rebuild:

```sql
REINDEX INDEX CONCURRENTLY idx_x;          -- Postgres 12+
REINDEX TABLE CONCURRENTLY users;
```

Monitor:

```sql
SELECT
    schemaname, tablename, indexname,
    pg_size_pretty(pg_relation_size(indexrelid)) as size,
    idx_scan, idx_tup_read, idx_tup_fetch
FROM pg_stat_user_indexes
ORDER BY pg_relation_size(indexrelid) DESC;
```

### Unused Index Detection

```sql
SELECT indexrelid::regclass, indrelid::regclass, idx_scan
FROM pg_stat_user_indexes
WHERE idx_scan = 0
  AND NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conindid = indexrelid);
```

Drop unused indexes — they cost write performance.

### Index for ORDER BY

```sql
SELECT * FROM articles ORDER BY created_at DESC LIMIT 10;

-- Index helps if matches order
CREATE INDEX idx_articles_created ON articles (created_at DESC);
```

### Sargable Predicates

```sql
-- Non-sargable (function on column) — index NOT used
WHERE LOWER(email) = 'x@y.com'
WHERE email LIKE '%foo'              -- leading wildcard
WHERE EXTRACT(YEAR FROM dt) = 2026


-- Sargable — index used
WHERE email = 'x@y.com'
WHERE email LIKE 'foo%'              -- prefix match OK
WHERE dt >= '2026-01-01' AND dt < '2027-01-01'
```

Or create expression indexes for non-sargable patterns.

---

## How It Works Internally

### B-Tree Structure

```
        [Root]
       /  |  \
   [Page] [Page] [Page]
   /  \    / \    / \
  ...      ...     ...
[Leaf pages with row IDs]
```

O(log n) lookup. Sorted leaves → range queries fast.

### Index-Only Scan + Visibility Map

```
Postgres MVCC: row may be deleted but tuple still in index until vacuumed.
Visibility map (per page): "all rows visible to all txns".
Index-only scan checks visibility map — if page all-visible, skip table.
```

VACUUM updates visibility map. Run regularly (auto-vacuum).

### GIN vs GiST

- **GIN**: inverted index, fast lookup, slow insert. Best for static-ish data.
- **GiST**: generalized search tree, slower lookup, faster insert. Best for high-update workloads.

---

## Common Pitfalls

### 1. Too Many Indexes

Each INSERT/UPDATE updates ALL indexes on the table. 20 indexes on `users` = slow writes.

### 2. Index Not Used Despite Existence

Check `EXPLAIN`. Common reasons:
- Wrong column order in multi-column
- Function applied to column (non-sargable)
- Statistics outdated (run `ANALYZE table`)
- Index marked invalid
- Type cast issues (`WHERE id = '5'` on int column)

### 3. Forgetting to ANALYZE After Bulk Load

```sql
COPY users FROM '...';   -- query planner has stale stats
ANALYZE users;            -- update statistics
```

### 4. Multi-Column Index Order Wrong

```sql
CREATE INDEX idx_orders ON orders (status, user_id);  -- bad order

SELECT * FROM orders WHERE user_id = 5;  -- index NOT used (skips 'status')
```

Order by selectivity: high cardinality first.

### 5. Index on Low-Cardinality Column

```sql
CREATE INDEX idx_users_gender ON users (gender);  -- only 2-3 values
```

Postgres planner ignores (table scan faster). Use partial index instead:

```sql
CREATE INDEX idx_users_admin ON users (id) WHERE gender = 'admin';
```

### 6. Index Bloat Ignored

Long-running queries + many updates → bloat. Periodic `REINDEX CONCURRENTLY`.

### 7. JSON Indexes Missed

```sql
-- Slow
WHERE data->>'status' = 'paid'


-- With expression index
CREATE INDEX idx_data_status ON orders ((data->>'status'));


-- For multiple keys: GIN index
CREATE INDEX idx_data_gin ON orders USING GIN (data);
-- Supports @>, ?, ?&, ?| operators
```

---

## Exclusion Constraints — "overlap allowed hi nahi" (GiST ka killer use case)

UNIQUE bolta hai "equal values nahi"; **EXCLUDE** bolta hai "koi bhi do rows jinke beech yeh operator true ho, nahi" — booking-overlap problem ka database-level solution:

```sql
CREATE EXTENSION IF NOT EXISTS btree_gist;

CREATE TABLE bookings (
    room_id  int,
    duration tstzrange,        -- [check_in, check_out)
    EXCLUDE USING GIST (
        room_id  WITH =,        -- same room...
        duration WITH &&        -- ...overlapping time range → REJECT
    )
);

INSERT INTO bookings VALUES (101, '[2026-08-10, 2026-08-12)');   -- ✅
INSERT INTO bookings VALUES (101, '[2026-08-11, 2026-08-13)');   -- ❌ conflict!
INSERT INTO bookings VALUES (102, '[2026-08-11, 2026-08-13)');   -- ✅ different room
```

**Yeh kyun important hai:** application-level check (`SELECT ... FOR UPDATE` + overlap query) race conditions me leak karta hai jab tak serializable isolation ya explicit locking na ho — EXCLUDE constraint index-level pe atomically enforce karta hai, concurrency bugs impossible. Meeting rooms, hotel bookings, shift scheduling, IP-range allocation — sab yahi pattern. (BookMyShow/Airbnb HLD discussion me yeh bolna strong signal hai — "seat/room overlap ko main DB-level exclusion constraint se guarantee karta hoon, app-level check sirf UX ke liye.")

---

## Interview Q&A

**Q1:** Multi-column index ka order kaise decide karoge?
**A:** Three rules: (1) Most selective (high cardinality) column first. (2) Match common WHERE patterns. (3) Equality columns before range columns. Example: `(user_id, created_at)` not `(created_at, user_id)` — queries usually filter user then date range.

**Q2:** Partial index kab use karoge?
**A:** When you only query a subset. Examples: `WHERE status = 'pending'` (queue), `WHERE deleted_at IS NULL` (soft delete), `WHERE is_active = true`. Index 1% of rows instead of 100% → 100x smaller. Cheaper writes too.

**Q3:** Covering index ka benefit?
**A:** Index-only scan — no table fetch needed. Saves random I/O (which dominates query time for non-cached data). `CREATE INDEX X ON t (a) INCLUDE (b, c)` — query selecting only a, b, c uses index without touching heap.

**Q4:** GIN vs B-tree?
**A:** B-tree: scalar values, equality + range + sort. GIN: composite values (arrays, JSON, tsvector). GIN supports `@>`, `?`, full-text search. Trade-off: GIN slow to update (every keyword indexed), fast to search.

**Q5:** Index slow likhne par bhi use nahi ho rha — debug kaise?
**A:** `EXPLAIN (ANALYZE, BUFFERS) <query>`. Look for `Seq Scan` vs `Index Scan`. Reasons: (1) statistics stale → ANALYZE. (2) function on column → expression index. (3) wrong column order. (4) planner thinks seq scan cheaper (few rows, low selectivity). (5) type mismatch.

**Q6:** CREATE INDEX CONCURRENTLY ka use?
**A:** Production-safe — no AccessExclusiveLock on table. Allows writes during creation. Trade-off: 2-3x slower than non-concurrent, may leave invalid index on failure. Always use in prod.

**Q7:** Index bloat detect aur fix?
**A:** Detect via pg_stat_user_indexes — compare `pg_relation_size` to expected. Fix: `REINDEX INDEX CONCURRENTLY name`. For tables: `REINDEX TABLE CONCURRENTLY name`. Schedule periodic during low-traffic window.

**Q8:** Index on JSONB how?
**A:** Two options: (1) **Expression index** on specific key: `CREATE INDEX ON t ((data->>'status'))` — fast for that one key. (2) **GIN index** on whole JSONB: `CREATE INDEX ON t USING GIN (data)` — supports any key + `@>` containment. GIN larger but flexible.

---

## Real-World Use Cases

### 1. Job Queue (Partial Index)

```sql
CREATE INDEX idx_jobs_pending
    ON jobs (priority DESC, created_at)
    WHERE status = 'pending';

-- Query: 1M jobs total, 100 pending → scans only those 100
SELECT * FROM jobs
WHERE status = 'pending'
ORDER BY priority DESC, created_at
LIMIT 1
FOR UPDATE SKIP LOCKED;
```

### 2. Soft Delete (Partial Unique)

```sql
-- Unique only among non-deleted
CREATE UNIQUE INDEX idx_users_email_active
    ON users (email)
    WHERE deleted_at IS NULL;

-- Allows re-using email after delete
```

### 3. Multi-Tenant (Composite + Covering)

```sql
CREATE INDEX idx_orders_tenant_status
    ON orders (tenant_id, status, created_at DESC)
    INCLUDE (amount, customer_id);

-- All common queries: WHERE tenant_id = X AND status = ... ORDER BY created_at DESC
-- Plus SELECT amount, customer_id — covered, no heap access
```

---

## References

- [PostgreSQL Indexes](https://www.postgresql.org/docs/current/indexes.html)
- [Index types](https://www.postgresql.org/docs/current/indexes-types.html)
- [pgexperts blog on indexes](https://www.pgexperts.com/blog/)
- Markus Winand: Use The Index, Luke!
