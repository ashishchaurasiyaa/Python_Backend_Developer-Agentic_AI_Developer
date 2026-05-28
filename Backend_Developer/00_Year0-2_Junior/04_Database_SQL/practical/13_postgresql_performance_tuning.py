"""
============================================================
POSTGRESQL PERFORMANCE TUNING — Practical
============================================================
Diagnostic queries + Python tools for finding slow queries,
bloat, missing indexes, and unused indexes.
"""
import asyncio
from dataclasses import dataclass


# ============================================================
# 1. POSTGRESQL.CONF — production template (32GB RAM, 8 cores)
# ============================================================
POSTGRES_CONF = """
# ===== MEMORY =====
shared_buffers = 8GB                       # 25% of RAM
effective_cache_size = 24GB                # 75% of RAM (hint)
work_mem = 16MB                            # per-query op (multiply by conns × ops!)
maintenance_work_mem = 2GB                 # for VACUUM, CREATE INDEX
huge_pages = try                           # Linux huge pages reduce TLB miss

# ===== WAL / CHECKPOINTS =====
wal_level = replica                        # or 'logical'
wal_buffers = 64MB
max_wal_size = 4GB                         # less frequent checkpoints
min_wal_size = 1GB
checkpoint_timeout = 15min
checkpoint_completion_target = 0.9
wal_compression = on                        # Postgres 14+

# ===== PARALLELISM =====
max_worker_processes = 8                   # CPU count
max_parallel_workers = 8
max_parallel_workers_per_gather = 4
max_parallel_maintenance_workers = 4

# ===== DISK =====
random_page_cost = 1.1                     # SSD
effective_io_concurrency = 200             # SSD
seq_page_cost = 1.0

# ===== CONNECTIONS =====
max_connections = 200                      # use PgBouncer beyond this

# ===== AUTOVACUUM =====
autovacuum = on
autovacuum_max_workers = 4
autovacuum_naptime = 30
autovacuum_vacuum_scale_factor = 0.05      # 5% (default 20%)
autovacuum_analyze_scale_factor = 0.02
autovacuum_vacuum_cost_limit = 1000

# ===== STATISTICS =====
default_statistics_target = 100            # per-column samples
track_io_timing = on
track_activities = on

# ===== LOGGING =====
log_min_duration_statement = 1000          # log queries > 1s
log_lock_waits = on
log_temp_files = 10MB                      # log temp files > 10MB
log_checkpoints = on
log_autovacuum_min_duration = 1000
log_line_prefix = '%t [%p]: user=%u,db=%d,app=%a '

# ===== EXTENSIONS (preload) =====
shared_preload_libraries = 'pg_stat_statements,auto_explain'

# ===== pg_stat_statements =====
pg_stat_statements.max = 10000
pg_stat_statements.track = all

# ===== auto_explain =====
auto_explain.log_min_duration = 1000       # auto-EXPLAIN slow queries
auto_explain.log_analyze = on
auto_explain.log_buffers = on
auto_explain.log_format = json
"""


# ============================================================
# 2. DIAGNOSTIC QUERIES (run periodically)
# ============================================================
SLOW_QUERIES = """
-- Top 20 slowest queries (cumulative time)
SELECT
    query,
    calls,
    round(total_exec_time::numeric, 2) AS total_ms,
    round(mean_exec_time::numeric, 2) AS avg_ms,
    round(max_exec_time::numeric, 2) AS max_ms,
    round((100 * total_exec_time / sum(total_exec_time) OVER ())::numeric, 2) AS pct,
    rows,
    round(rows::numeric / NULLIF(calls, 0), 2) AS avg_rows
FROM pg_stat_statements
WHERE query NOT LIKE '%pg_stat_statements%'
ORDER BY total_exec_time DESC
LIMIT 20;
"""

CURRENT_RUNNING_QUERIES = """
-- Queries currently running > 1s
SELECT
    pid,
    usename,
    application_name,
    state,
    now() - query_start AS duration,
    wait_event_type, wait_event,
    query
FROM pg_stat_activity
WHERE state != 'idle'
  AND (now() - query_start) > interval '1 second'
ORDER BY duration DESC;

-- Kill stuck query
-- SELECT pg_cancel_backend(12345);   -- soft (returns false if not cancellable)
-- SELECT pg_terminate_backend(12345); -- hard
"""

TABLE_BLOAT = """
-- Tables with dead tuple bloat
SELECT
    schemaname || '.' || relname AS table,
    n_live_tup, n_dead_tup,
    round(n_dead_tup::numeric / NULLIF(n_live_tup, 0) * 100, 2) AS dead_pct,
    last_vacuum, last_autovacuum,
    pg_size_pretty(pg_total_relation_size(relid)) AS total_size
FROM pg_stat_user_tables
WHERE n_dead_tup > 1000
ORDER BY n_dead_tup DESC
LIMIT 20;
"""

MISSING_INDEXES = """
-- Tables with many sequential scans (indicating missing index)
SELECT
    schemaname || '.' || relname AS table,
    seq_scan,
    seq_tup_read,
    idx_scan,
    seq_tup_read / NULLIF(seq_scan, 0) AS avg_rows_per_scan,
    pg_size_pretty(pg_relation_size(relid)) AS size
FROM pg_stat_user_tables
WHERE seq_scan > 1000
  AND seq_tup_read / NULLIF(seq_scan, 0) > 100   -- big scans
ORDER BY seq_tup_read DESC
LIMIT 20;
"""

UNUSED_INDEXES = """
-- Indexes that are never used (waste space + slow writes)
SELECT
    schemaname || '.' || indexrelname AS index,
    schemaname || '.' || relname AS table,
    idx_scan,
    idx_tup_read,
    idx_tup_fetch,
    pg_size_pretty(pg_relation_size(indexrelid)) AS size
FROM pg_stat_user_indexes
WHERE idx_scan < 50
  AND indexrelname NOT LIKE '%_pkey'
ORDER BY pg_relation_size(indexrelid) DESC
LIMIT 20;
"""

DUPLICATE_INDEXES = """
-- Duplicate/redundant indexes
SELECT
    a.indexrelname || ' overlaps ' || b.indexrelname AS conflict,
    a.tablename,
    pg_size_pretty(pg_relation_size(a.indexrelid)) AS a_size,
    pg_size_pretty(pg_relation_size(b.indexrelid)) AS b_size
FROM pg_indexes a
JOIN pg_indexes b ON a.tablename = b.tablename
    AND a.indexdef < b.indexdef
WHERE a.indexdef LIKE b.indexdef || '%';  -- simplified
"""

CACHE_HIT_RATIO = """
-- Cache hit ratio (target > 99%)
SELECT
    sum(heap_blks_read) AS disk_reads,
    sum(heap_blks_hit) AS cache_hits,
    round(sum(heap_blks_hit) * 100.0 / NULLIF(sum(heap_blks_hit) + sum(heap_blks_read), 0), 2) AS cache_hit_pct
FROM pg_statio_user_tables;

-- Index cache hit ratio
SELECT
    round(sum(idx_blks_hit) * 100.0 / NULLIF(sum(idx_blks_hit) + sum(idx_blks_read), 0), 2) AS index_cache_pct
FROM pg_statio_user_indexes;
"""

LOCK_MONITORING = """
-- Blocked queries
SELECT
    blocked_locks.pid AS blocked_pid,
    blocked_activity.usename AS blocked_user,
    blocking_locks.pid AS blocking_pid,
    blocking_activity.usename AS blocking_user,
    blocked_activity.query AS blocked_query,
    blocking_activity.query AS blocking_query
FROM pg_catalog.pg_locks blocked_locks
JOIN pg_catalog.pg_stat_activity blocked_activity ON blocked_activity.pid = blocked_locks.pid
JOIN pg_catalog.pg_locks blocking_locks
    ON blocking_locks.locktype = blocked_locks.locktype
    AND blocking_locks.database IS NOT DISTINCT FROM blocked_locks.database
    AND blocking_locks.relation IS NOT DISTINCT FROM blocked_locks.relation
    AND blocking_locks.pid != blocked_locks.pid
JOIN pg_catalog.pg_stat_activity blocking_activity ON blocking_activity.pid = blocking_locks.pid
WHERE NOT blocked_locks.granted;
"""

CONNECTION_STATS = """
-- Connection breakdown
SELECT
    state,
    count(*),
    max(now() - state_change) AS longest_in_state
FROM pg_stat_activity
GROUP BY state;

-- Connections by application
SELECT application_name, count(*)
FROM pg_stat_activity
GROUP BY application_name
ORDER BY count(*) DESC;
"""


# ============================================================
# 3. PYTHON SCRIPT — Run diagnostics
# ============================================================
RUN_DIAGNOSTICS = """
import asyncpg
import asyncio

async def diagnose(conn_url):
    conn = await asyncpg.connect(conn_url)

    print("=== TOP SLOW QUERIES ===")
    rows = await conn.fetch(SLOW_QUERIES_SQL)
    for r in rows:
        print(f"  {r['avg_ms']:8.2f}ms × {r['calls']:6d} = {r['total_ms']:10.2f}ms")
        print(f"    {r['query'][:100]}")

    print("\\n=== BLOATED TABLES ===")
    rows = await conn.fetch(TABLE_BLOAT_SQL)
    for r in rows:
        print(f"  {r['table']:30s} {r['dead_pct']:5.1f}% dead")

    print("\\n=== CACHE HIT RATIO ===")
    row = await conn.fetchrow(CACHE_HIT_SQL)
    if row['cache_hit_pct'] < 99:
        print(f"  ⚠️  Cache hit only {row['cache_hit_pct']}% — increase shared_buffers")

    await conn.close()

asyncio.run(diagnose("postgresql://..."))
"""


# ============================================================
# 4. VACUUM / REINDEX HELPERS
# ============================================================
VACUUM_OPS = """
-- Standard vacuum (doesn't lock)
VACUUM (VERBOSE, ANALYZE) users;

-- Aggressive vacuum (longer lock, reclaims space)
VACUUM FULL users;    -- exclusive lock, rewrites table!

-- Rebuild index (online in Postgres 12+)
REINDEX INDEX CONCURRENTLY idx_users_email;
REINDEX TABLE CONCURRENTLY users;

-- Per-table aggressive autovacuum
ALTER TABLE events SET (
    autovacuum_vacuum_scale_factor = 0.01,
    autovacuum_analyze_scale_factor = 0.005,
    autovacuum_vacuum_cost_limit = 2000
);

-- Update statistics for one column
ALTER TABLE events ALTER COLUMN user_id SET STATISTICS 1000;
ANALYZE events;
"""


# ============================================================
# 5. KEYSET PAGINATION (vs OFFSET)
# ============================================================
KEYSET_PAGINATION = """
# BAD — gets slower as page increases
SELECT * FROM events
ORDER BY id DESC
LIMIT 50 OFFSET 100000;    -- scans 100050 rows!

# GOOD — constant time regardless of position
SELECT * FROM events
WHERE id < :last_id
ORDER BY id DESC
LIMIT 50;

# Python helper
async def paginated_events(conn, cursor=None, limit=50):
    if cursor is None:
        sql = "SELECT * FROM events ORDER BY id DESC LIMIT $1"
        rows = await conn.fetch(sql, limit)
    else:
        sql = "SELECT * FROM events WHERE id < $1 ORDER BY id DESC LIMIT $2"
        rows = await conn.fetch(sql, cursor, limit)

    next_cursor = rows[-1]['id'] if rows else None
    return rows, next_cursor
"""


# ============================================================
# 6. EXPLAIN ANALYZE INTERPRETATION
# ============================================================
EXPLAIN_GUIDE = """
SAMPLE OUTPUT:
QUERY PLAN
--------------------------------------------------------
Seq Scan on users  (cost=0.00..1234.00 rows=10000 width=64)
                   (actual time=0.012..15.234 rows=9852 loops=1)
  Filter: (active = true)
  Rows Removed by Filter: 148
  Buffers: shared hit=512 read=300
Planning Time: 0.234 ms
Execution Time: 16.123 ms

KEY THINGS TO CHECK:
1. "Seq Scan" vs "Index Scan"
   - Seq Scan on big table + filter = missing index
2. "cost=" estimates vs "actual time="
   - Big difference = run ANALYZE
3. "rows=" estimate vs actual
   - Off by >10x = bad stats, run ANALYZE / increase statistics target
4. "loops=" > 1
   - Nested loop — may need different join strategy
5. "buffers shared read=" (not hit)
   - Cache miss = either cache too small or first query
6. "Sort Method: external merge Disk"
   - work_mem too small for this sort

RED FLAGS:
- Seq Scan on >10K row table without LIMIT
- Hash Join with batches > 1 (spilling)
- "Materialize" appearing (often optimizer giving up)
- Rows actual >> estimate (stale stats)
"""


# ============================================================
# 7. BULK LOAD OPTIMIZATION
# ============================================================
BULK_LOAD = """
# 1. Use COPY (10x faster than INSERT)
async with conn.copy_to_table("users", columns=["name", "email"]) as copy:
    for row in big_data:
        await copy.write_row(row)

# 2. Drop indexes before bulk load, recreate after
DROP INDEX idx_email;
COPY users FROM '/tmp/users.csv';
CREATE INDEX CONCURRENTLY idx_email ON users(email);

# 3. Disable autovacuum during load
ALTER TABLE users SET (autovacuum_enabled = false);
-- ... bulk load ...
VACUUM ANALYZE users;
ALTER TABLE users SET (autovacuum_enabled = true);

# 4. Increase maintenance_work_mem
SET maintenance_work_mem = '4GB';

# 5. Use UNLOGGED for temp staging (no WAL!)
CREATE UNLOGGED TABLE staging_users (LIKE users INCLUDING ALL);
COPY staging_users FROM ...;
ALTER TABLE staging_users SET LOGGED;   -- promote when done
"""


# ============================================================
# 8. PGTUNE EQUIVALENT (Python calculator)
# ============================================================
@dataclass
class TuningRecommendation:
    shared_buffers_mb: int
    effective_cache_size_mb: int
    work_mem_mb: int
    maintenance_work_mem_mb: int
    max_connections: int
    max_wal_size_mb: int
    config: str


def recommend_config(
    total_ram_gb: int,
    cpu_cores: int,
    workload: str = "oltp",     # oltp, dw (data warehouse), mixed
    storage: str = "ssd",       # ssd, hdd, nvme
) -> TuningRecommendation:
    """Generate PostgreSQL config recommendation."""
    ram_mb = total_ram_gb * 1024

    # Memory
    shared_buffers = min(ram_mb // 4, 8192)
    effective_cache = ram_mb * 3 // 4
    maint_work_mem = min(ram_mb // 16, 2048)

    # Work mem depends on workload + connections
    max_conns = 200 if workload == "oltp" else 40
    work_mem = (ram_mb - shared_buffers) // (max_conns * 4)
    work_mem = max(min(work_mem, 64), 4)

    # WAL
    max_wal = 16384 if workload == "dw" else 4096

    # I/O for storage type
    random_page_cost = {"nvme": 1.0, "ssd": 1.1, "hdd": 4.0}[storage]
    io_concurrency = {"nvme": 1000, "ssd": 200, "hdd": 1}[storage]

    config = f"""
shared_buffers = {shared_buffers}MB
effective_cache_size = {effective_cache}MB
work_mem = {work_mem}MB
maintenance_work_mem = {maint_work_mem}MB
max_connections = {max_conns}
max_wal_size = {max_wal}MB
random_page_cost = {random_page_cost}
effective_io_concurrency = {io_concurrency}
max_worker_processes = {cpu_cores}
max_parallel_workers_per_gather = {cpu_cores // 2}
max_parallel_workers = {cpu_cores}
checkpoint_completion_target = 0.9
"""
    return TuningRecommendation(
        shared_buffers, effective_cache, work_mem, maint_work_mem,
        max_conns, max_wal, config,
    )


def demo_recommendation():
    print("=" * 60)
    print("TUNING RECOMMENDATION FOR 32GB RAM, 8 CPU, OLTP, SSD")
    print("=" * 60)
    rec = recommend_config(32, 8, "oltp", "ssd")
    print(rec.config)


# ============================================================
# MAIN
# ============================================================
if __name__ == "__main__":
    demo_recommendation()

    print("\n" + "=" * 60)
    print("POSTGRESQL.CONF TEMPLATE")
    print("=" * 60)
    print(POSTGRES_CONF)

    print("\n--- DIAGNOSTIC QUERIES ---")
    print(SLOW_QUERIES)
    print(CURRENT_RUNNING_QUERIES)
    print(TABLE_BLOAT)
    print(MISSING_INDEXES)
    print(UNUSED_INDEXES)
    print(CACHE_HIT_RATIO)
    print(LOCK_MONITORING)
    print(CONNECTION_STATS)

    print("\n--- VACUUM OPS ---")
    print(VACUUM_OPS)
    print("\n--- KEYSET PAGINATION ---")
    print(KEYSET_PAGINATION)
    print("\n--- EXPLAIN GUIDE ---")
    print(EXPLAIN_GUIDE)
    print("\n--- BULK LOAD ---")
    print(BULK_LOAD)
