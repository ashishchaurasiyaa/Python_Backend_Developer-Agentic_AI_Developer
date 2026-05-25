# PostgreSQL Performance Tuning

> **Interview angle:** "Postgres slow ho gaya — kahan se start karoge tuning?"

---

## 1. Tuning Hierarchy (priority order)

```
1. Schema / Query design     ← biggest impact
2. Indexes
3. Postgres config (memory, WAL)
4. Hardware (SSD, more RAM)
5. Architecture (replicas, sharding)
```

**Don't tune config first.** Most slowness is bad queries or missing indexes.

---

## 2. Critical Memory Parameters

### `shared_buffers`
- Postgres's own buffer cache
- **Rule:** 25% of RAM (max 8GB usually optimal)
- 16GB RAM → `shared_buffers = 4GB`
- Larger doesn't help (OS cache also active)

### `effective_cache_size`
- Hint to optimizer about OS cache + shared_buffers
- **Rule:** 50-75% of RAM
- 16GB RAM → `effective_cache_size = 12GB`
- Doesn't actually allocate, just informs planner

### `work_mem`
- Memory per query operation (sort, hash join)
- Per-connection × per-query-op (can multiply!)
- **Rule:** start at 4-16MB, increase if EXPLAIN shows "disk sort"
- Be careful: 100 conns × 4 sorts × 64MB = 25GB!

### `maintenance_work_mem`
- For VACUUM, CREATE INDEX, ALTER TABLE
- **Rule:** 256MB-2GB
- Higher = faster maintenance

### `wal_buffers`
- WAL buffer before fsync
- Auto-tuned to 1/32 of shared_buffers, max 16MB
- Usually leave default

### Example settings (32GB RAM, dedicated DB server)
```ini
shared_buffers = 8GB
effective_cache_size = 24GB
work_mem = 16MB
maintenance_work_mem = 1GB
wal_buffers = 64MB
```

---

## 3. WAL + Checkpoint Tuning

### `checkpoint_timeout`
- How often Postgres syncs dirty pages
- Default 5 min → bursty I/O
- **Increase to 15-30 min** for smoother I/O

### `max_wal_size`
- WAL space between checkpoints
- Larger = fewer checkpoints, better throughput, more recovery time
- **Default 1GB → increase to 4-16GB** for write-heavy

### `checkpoint_completion_target`
- Spread checkpoint over what fraction of timeout
- **Default 0.9** = good (spreads I/O)

### Example
```ini
max_wal_size = 4GB
min_wal_size = 1GB
checkpoint_timeout = 15min
checkpoint_completion_target = 0.9
wal_compression = on            # Postgres 14+ compresses full-page writes
```

---

## 4. Parallelism

### `max_parallel_workers_per_gather`
- Parallel workers per query
- Default 2 → **set to 4-8** for analytical queries

### `max_parallel_workers`
- Total across all queries
- **Set to CPU count - 1**

### Example
```ini
max_worker_processes = 8
max_parallel_workers_per_gather = 4
max_parallel_workers = 8
max_parallel_maintenance_workers = 4
```

Query benefits when:
- Large table scans
- Hash joins on big tables
- Aggregations on partitioned tables

---

## 5. Autovacuum Tuning

Autovacuum keeps tables healthy. **Don't disable it!**

### Default = too lazy for high-write tables
```ini
# Be MORE aggressive
autovacuum_vacuum_scale_factor = 0.05   # vacuum at 5% bloat (default 20%)
autovacuum_analyze_scale_factor = 0.02  # analyze at 2%
autovacuum_vacuum_cost_limit = 1000     # vacuum faster (default 200)
autovacuum_naptime = 30                 # check every 30s
autovacuum_max_workers = 6              # more parallel workers
```

### Per-table override (for hot tables)
```sql
ALTER TABLE events SET (
    autovacuum_vacuum_scale_factor = 0.01,
    autovacuum_vacuum_cost_limit = 2000,
    autovacuum_analyze_scale_factor = 0.005
);
```

### Monitor
```sql
SELECT schemaname, relname,
    n_live_tup, n_dead_tup,
    round(n_dead_tup::numeric / NULLIF(n_live_tup, 0) * 100, 2) AS dead_pct,
    last_vacuum, last_autovacuum
FROM pg_stat_user_tables
ORDER BY n_dead_tup DESC LIMIT 10;
```

---

## 6. Query Tuning Tools

### EXPLAIN ANALYZE
```sql
EXPLAIN (ANALYZE, BUFFERS, VERBOSE)
SELECT ... ;
```

Look for:
- **Seq Scan** on big table → missing index?
- **Sort: external merge Disk** → increase work_mem
- **Hash Join** with low memory → increase work_mem
- **Rows actual >> rows estimate** → run ANALYZE
- **buffers shared read** → not in cache, slow disk I/O

### pg_stat_statements
```sql
CREATE EXTENSION pg_stat_statements;

-- In postgresql.conf
shared_preload_libraries = 'pg_stat_statements'

-- Top slow queries
SELECT query, calls, total_exec_time,
    mean_exec_time, max_exec_time,
    rows
FROM pg_stat_statements
ORDER BY total_exec_time DESC
LIMIT 10;
```

### pg_stat_activity
```sql
-- Currently running queries
SELECT pid, now() - query_start AS duration, state, query
FROM pg_stat_activity
WHERE state != 'idle'
ORDER BY duration DESC;

-- Kill slow query
SELECT pg_cancel_backend(12345);   -- soft (try)
SELECT pg_terminate_backend(12345); -- hard
```

### auto_explain
Logs EXPLAIN of slow queries automatically:
```ini
session_preload_libraries = 'auto_explain'
auto_explain.log_min_duration = 1000    # log queries > 1s
auto_explain.log_analyze = on
auto_explain.log_buffers = on
```

---

## 7. Index Tuning

### Find missing indexes
```sql
SELECT schemaname, tablename, seq_scan, seq_tup_read,
    idx_scan, seq_tup_read / NULLIF(seq_scan, 0) AS avg_rows_per_seq_scan
FROM pg_stat_user_tables
WHERE seq_scan > 0
ORDER BY seq_tup_read DESC
LIMIT 20;
```

### Find unused indexes (waste space)
```sql
SELECT indexrelname, idx_scan, idx_tup_read,
    pg_size_pretty(pg_relation_size(indexrelid))
FROM pg_stat_user_indexes
WHERE idx_scan < 50
ORDER BY pg_relation_size(indexrelid) DESC
LIMIT 20;
```

### Index types and when to use

| Type | Use Case |
|---|---|
| **B-tree** | Default. Equality, range, ORDER BY |
| **Hash** | Exact equality only (rare) |
| **GIN** | JSONB, arrays, full-text |
| **GiST** | Geometric, geo, range types |
| **BRIN** | Very large tables with natural order (time-series) |
| **Bloom** | Multi-column equality (less precise but compact) |
| **Partial** | Index subset of rows (WHERE active=true) |
| **Expression** | Index function output (lower(email)) |

### Index gotchas
- Each INSERT/UPDATE touches all indexes → slow writes if too many
- Indexes need maintenance (REINDEX periodically)
- Large indexes don't fit cache → slower than expected
- B-tree on TEXT > 8KB doesn't work — use hash of value

---

## 8. Connection Tuning

```ini
max_connections = 200          # don't go crazy — use PgBouncer
superuser_reserved_connections = 5
```

**Rule:** Lower is better. 200 max + PgBouncer can serve 1000s of clients.

---

## 9. Disk I/O Tuning

### `effective_io_concurrency`
- How many concurrent disk I/O ops (for SSD)
- HDD: 1, SSD: 200, NVMe: 500-1000

### `random_page_cost`
- Cost of random vs sequential read
- HDD: 4 (default), SSD: 1.1, NVMe: 1.0

```ini
# Modern SSD setup
effective_io_concurrency = 200
random_page_cost = 1.1
seq_page_cost = 1.0
```

---

## 10. Logging for Diagnosis

```ini
# Log slow queries
log_min_duration_statement = 1000    # 1s+

# Log lock waits
log_lock_waits = on
deadlock_timeout = 1s

# Log connections (audit)
log_connections = on
log_disconnections = on

# Format
log_line_prefix = '%t [%p]: [%l-1] user=%u,db=%d,app=%a,client=%h '

# Statement-level
# log_statement = 'mod'   # log INSERT/UPDATE/DELETE
# Disable in production — verbose
```

---

## 11. JSONB Performance

```sql
-- Index JSONB field
CREATE INDEX idx_data_gin ON events USING GIN (data);
-- Index specific key
CREATE INDEX idx_status ON events ((data->>'status'));

-- Query patterns
SELECT * FROM events WHERE data @> '{"status": "active"}';     -- uses GIN
SELECT * FROM events WHERE data->>'status' = 'active';         -- uses expression index
```

JSONB > JSON: binary format, faster, supports indexing.

---

## 12. Bulk Operations

### COPY (fastest)
```python
async with conn.cursor() as cur:
    async with cur.copy("COPY users (name, email) FROM STDIN") as copy:
        async for row in rows:
            await copy.write_row(row)
```

10x+ faster than INSERT.

### Disable indexes during bulk load
```sql
-- Before
ALTER INDEX idx_email DISABLE;        -- actually drop + recreate
DROP INDEX idx_email;

-- After bulk load
CREATE INDEX CONCURRENTLY idx_email ON users(email);
```

### UNLOGGED tables (for temp staging)
```sql
CREATE UNLOGGED TABLE staging (...);
-- Don't write to WAL = 2-5x faster
-- Risk: lost on crash (OK for staging)
```

---

## 13. PostgreSQL Statistics

### Update statistics
```sql
-- Stale stats = bad query plans
ANALYZE users;            -- single table
ANALYZE;                  -- all tables
VACUUM ANALYZE users;     -- vacuum + analyze
```

### Stats target (more samples = better plans)
```sql
ALTER TABLE events ALTER COLUMN user_id SET STATISTICS 1000;
-- Default 100. Higher for columns with skewed distribution.
ANALYZE events;
```

### Extended statistics (correlated columns)
```sql
-- For correlated columns: ALWAYS query together
CREATE STATISTICS stats_zip_city (dependencies)
    ON zip_code, city FROM addresses;
ANALYZE addresses;
```

---

## 14. Common Performance Anti-Patterns

### Anti-pattern 1: SELECT *
Pulls unnecessary columns. Specify columns.

### Anti-pattern 2: N+1 queries
```python
# Bad: 1 + N queries
users = User.query.all()
for user in users:
    posts = Post.query.filter_by(user_id=user.id).all()   # N queries

# Good: JOIN or prefetch
users = User.query.options(joinedload(User.posts)).all()
```

### Anti-pattern 3: Indexing every column
Each index slows writes. Index based on actual query patterns.

### Anti-pattern 4: Long-running transactions
Hold locks → block others → bloat (autovacuum can't clean rows visible to long txns).

### Anti-pattern 5: SELECT FOR UPDATE on whole table
```sql
SELECT * FROM users FOR UPDATE;   -- locks entire table!
SELECT * FROM users WHERE id = 1 FOR UPDATE;   -- locks just one row
```

### Anti-pattern 6: Using OFFSET for pagination
```sql
SELECT * FROM events ORDER BY id LIMIT 50 OFFSET 100000;
-- Scans 100000 + 50 rows. SLOW.
```
Use keyset pagination:
```sql
SELECT * FROM events WHERE id > :last_id ORDER BY id LIMIT 50;
```

---

## 15. Tuning Workflow

1. **Baseline** — record current metrics
2. **Find slow queries** (pg_stat_statements)
3. **EXPLAIN ANALYZE** each
4. **Fix one at a time** — add index, rewrite, increase work_mem
5. **Measure improvement**
6. **Repeat**

---

## 16. PgTune (Easy Starting Point)

https://pgtune.leopard.in.ua/ — input RAM/CPU/disk, get config.

```ini
# Generated by PgTune for 32GB RAM, 8 cores, OLTP
shared_buffers = 8GB
effective_cache_size = 24GB
maintenance_work_mem = 2GB
checkpoint_completion_target = 0.9
wal_buffers = 16MB
default_statistics_target = 100
random_page_cost = 1.1
effective_io_concurrency = 200
work_mem = 16MB
huge_pages = try
min_wal_size = 1GB
max_wal_size = 4GB
max_worker_processes = 8
max_parallel_workers_per_gather = 4
max_parallel_workers = 8
max_parallel_maintenance_workers = 4
```

---

## 17. Interview Questions

**Q1: Tuning kahan se start karte?**
1. Slow queries (pg_stat_statements)
2. EXPLAIN ANALYZE
3. Add/fix indexes
4. Then config tuning

**Q2: shared_buffers default kyu kam hai?**
Conservative for small servers. Tune to 25% of RAM for dedicated DB.

**Q3: work_mem kab badhao?**
EXPLAIN shows "external merge Disk" → sort spilling. Increase to fit in memory.

**Q4: Autovacuum kab tune karo?**
High-write tables show n_dead_tup growing. Lower scale_factor + higher cost_limit.

**Q5: max_connections high kyu nahi?**
Each conn = ~10MB + process. Use PgBouncer for multiplexing.

**Q6: Random vs seq page cost?**
SSDs: random ≈ seq (set random=1.1). HDDs: random much slower (default 4).

**Q7: parallel query kab fast?**
Big sequential scans, hash joins. Set max_parallel_workers_per_gather = 4-8.

---

## 18. Best Practices Summary

1. **Profile first** with pg_stat_statements + EXPLAIN
2. **Indexes** > config tuning > hardware
3. **Tune autovacuum** for write-heavy tables
4. **PgBouncer** to multiplex connections
5. **work_mem carefully** — multiplies per conn × per op
6. **max_wal_size large** for write-heavy
7. **JSONB GIN indexes** for searchable fields
8. **COPY for bulk loads**
9. **Keyset pagination** not OFFSET
10. **Monitor + alert** on slow queries + bloat

---

## Related
- [[09_postgresql_ha_read_replicas]]
- [[11_pgbouncer_connection_pooling]]
- [[07_postgresql_internals]]
- [[01_postgresql_advanced]]
