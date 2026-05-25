# PostgreSQL Internals — VACUUM, Deadlocks, WAL, Replication

## Quick Concepts
- **MVCC** = Multi-Version Concurrency Control — readers don't block writers
- **Dead tuples** = old row versions (after UPDATE/DELETE) — still on disk until VACUUMed
- **VACUUM** = reclaims dead tuple space, updates statistics
- **autovacuum** = background VACUUM daemon — automatic, configurable
- **Table bloat** = unused space from dead tuples — slows queries, wastes disk
- **WAL** = Write-Ahead Log — every change logged before data file write
- **Checkpoint** = WAL flushed to data files — crash recovery point
- **Deadlock** = two transactions each waiting for the other's lock
- **Streaming replication** = WAL shipped to standby in real-time
- **Logical replication** = replicate specific tables, supports cross-version

---

## Interview Questions & Answers

### Q1: VACUUM kya hai? autovacuum kab fail karta hai?

**Answer:**
```sql
-- ─── WHY VACUUM? ───
-- PostgreSQL MVCC: UPDATE = old row marked dead + new row inserted
-- DELETE = row marked dead (not physically removed)
-- Dead tuples accumulate → table bloat → slow seq scans
-- VACUUM reclaims dead tuple space + updates pg_statistic (for planner)

-- ─── Check table bloat ───
SELECT
    schemaname,
    tablename,
    n_live_tup,
    n_dead_tup,
    ROUND(n_dead_tup::numeric / NULLIF(n_live_tup + n_dead_tup, 0) * 100, 2) AS dead_pct,
    last_vacuum,
    last_autovacuum,
    last_analyze,
    last_autoanalyze
FROM pg_stat_user_tables
ORDER BY n_dead_tup DESC
LIMIT 20;

-- ─── Manual VACUUM ───
VACUUM posts;                   -- reclaim dead tuples
VACUUM ANALYZE posts;           -- reclaim + update statistics
VACUUM FULL posts;              -- rewrite table — compact but locks table! Use rarely
VACUUM VERBOSE posts;           -- detailed output

-- ─── autovacuum triggers (default settings) ───
-- autovacuum_vacuum_threshold = 50   (min 50 dead tuples before trigger)
-- autovacuum_vacuum_scale_factor = 0.2  (trigger when 20% of rows are dead)
-- Formula: n_dead_tup > threshold + scale_factor * n_live_tup
-- Example: 10,000 row table → vacuum when 50 + 0.2 * 10000 = 2050 dead tuples

-- ─── autovacuum failing? Common causes ───
-- 1. Long-running transactions: hold oldest XID → VACUUM can't clean up
SELECT
    pid, usename,
    now() - xact_start AS txn_age,
    query
FROM pg_stat_activity
WHERE xact_start IS NOT NULL
ORDER BY xact_age DESC
LIMIT 5;

-- 2. Table too busy: autovacuum gets throttled by cost settings
-- autovacuum_vacuum_cost_delay = 20ms (pause between work chunks)
-- autovacuum_vacuum_cost_limit = 200 (cost units per chunk)

-- Fix: per-table override for high-churn tables
ALTER TABLE order_events SET (
    autovacuum_vacuum_scale_factor = 0.01,  -- trigger at 1% dead
    autovacuum_vacuum_cost_delay = 5        -- less throttling
);

-- ─── FREEZE — XID wraparound prevention ───
-- PostgreSQL transaction IDs (XID) are 32-bit → wrap after ~2 billion
-- VACUUM FREEZE marks old rows as "frozen" (no XID) → safe from wraparound
-- autovacuum_freeze_max_age = 200 million (trigger freeze before wraparound)

-- Check tables at risk of XID wraparound
SELECT
    schemaname, tablename,
    age(relfrozenxid) AS xid_age,
    pg_size_pretty(pg_total_relation_size(oid)) AS size
FROM pg_class
WHERE relkind = 'r'
ORDER BY age(relfrozenxid) DESC
LIMIT 10;
-- WARNING: if age > 1.5 billion → urgent! Run VACUUM FREEZE immediately
```

```
INTERVIEW: VACUUM FULL vs VACUUM?
VACUUM:      marks dead space as reusable (no lock, online)
VACUUM FULL: rewrites table compactly (table lock, offline) — use rarely

INTERVIEW: ANALYZE kab zaroori hai?
Table stats update hoti hain → query planner better plans banata hai
After bulk INSERT/DELETE/UPDATE — ANALYZE manually run karo
autovacuum_analyze_scale_factor = 0.1 (default: analyze at 10% row change)

INTERVIEW: autovacuum disable karna kabhi sahi hai?
Almost never! Disabling causes XID wraparound → database shutdown
Only disable during bulk loads, re-enable immediately after
```

---

### Q2: Deadlocks — kaise hote hain? Prevention?

**Answer:**
```sql
-- ─── DEADLOCK EXAMPLE ───
-- Transaction A:
BEGIN;
UPDATE accounts SET balance = balance - 100 WHERE id = 1;  -- locks row 1
-- (waiting for row 2 lock held by B)
UPDATE accounts SET balance = balance + 100 WHERE id = 2;

-- Transaction B (simultaneously):
BEGIN;
UPDATE accounts SET balance = balance - 100 WHERE id = 2;  -- locks row 2
-- (waiting for row 1 lock held by A) → DEADLOCK!
UPDATE accounts SET balance = balance + 100 WHERE id = 1;

-- PostgreSQL detects cycle → kills one transaction (deadlock victim)
-- ERROR: deadlock detected
-- DETAIL: Process 1234 waits for ShareLock on transaction 5678;
--         blocked by process 5678

-- ─── Find blocking queries ───
SELECT
    blocked.pid     AS blocked_pid,
    blocked.query   AS blocked_query,
    blocking.pid    AS blocking_pid,
    blocking.query  AS blocking_query,
    blocked.wait_event_type,
    blocked.wait_event
FROM pg_stat_activity AS blocked
JOIN pg_stat_activity AS blocking
    ON blocking.pid = ANY(pg_blocking_pids(blocked.pid))
WHERE NOT blocked.query LIKE '%pg_stat_activity%';

-- ─── PREVENTION strategies ───

-- 1. Consistent lock ordering (most important!)
-- Always lock rows in same order (id ASC) across all transactions
-- Bad:  Tx1: lock(1) then lock(2), Tx2: lock(2) then lock(1) → deadlock
-- Good: Both Tx lock in ascending id order → no cycle possible

-- 2. lock_timeout — fail fast instead of waiting forever
SET lock_timeout = '5s';   -- fail if can't acquire lock in 5 seconds
-- statement_timeout is harder deadline on any statement
SET statement_timeout = '30s';

-- 3. SELECT FOR UPDATE to pre-declare intent
BEGIN;
SELECT * FROM accounts WHERE id IN (1, 2) ORDER BY id  -- order matters!
FOR UPDATE;  -- grab both locks upfront → no mid-transaction deadlock
UPDATE accounts SET balance = balance - 100 WHERE id = 1;
UPDATE accounts SET balance = balance + 100 WHERE id = 2;
COMMIT;

-- 4. FOR UPDATE SKIP LOCKED — queue processing pattern
-- Each worker grabs available rows without blocking each other
SELECT * FROM tasks
WHERE status = 'pending'
ORDER BY created_at
LIMIT 10
FOR UPDATE SKIP LOCKED;
-- Workers run concurrently — no lock contention, no deadlock
```

```python
# ─── Python: handle deadlock with retry ───
import asyncio
from sqlalchemy.exc import OperationalError

async def transfer_with_retry(session, from_id: int, to_id: int, amount: float, max_retries: int = 3):
    """
    INTERVIEW: Application level deadlock handling?
    Catch OperationalError (deadlock) → retry with backoff
    Always lock rows in consistent ORDER (min id first) to minimize deadlocks
    """
    for attempt in range(max_retries):
        try:
            async with session.begin():
                # Lock in consistent order (min id first)
                ids = sorted([from_id, to_id])
                result = await session.execute(
                    text("SELECT * FROM accounts WHERE id = ANY(:ids) ORDER BY id FOR UPDATE"),
                    {"ids": ids}
                )
                accounts = {row.id: row for row in result.mappings()}

                from_acc = accounts[from_id]
                to_acc   = accounts[to_id]

                if from_acc["balance"] < amount:
                    raise ValueError("Insufficient balance")

                await session.execute(
                    text("UPDATE accounts SET balance = balance - :amt WHERE id = :id"),
                    {"amt": amount, "id": from_id}
                )
                await session.execute(
                    text("UPDATE accounts SET balance = balance + :amt WHERE id = :id"),
                    {"amt": amount, "id": to_id}
                )
                return True

        except OperationalError as e:
            if "deadlock" in str(e).lower() and attempt < max_retries - 1:
                wait = 0.1 * (2 ** attempt)  # exponential backoff
                await asyncio.sleep(wait)
                await session.rollback()
                continue
            raise
```

---

### Q3: WAL (Write-Ahead Log) — kya hai? Crash recovery kaise?

**Answer:**
```
─── WAL (Write-Ahead Log) — Core PostgreSQL mechanism ───

How it works:
  1. Every change (INSERT/UPDATE/DELETE) written to WAL first
  2. WAL flushed to disk (fsync)
  3. Actual data files updated later (at checkpoint)

Why WAL?
  - Crash recovery: WAL replay karo from last checkpoint → full recovery
  - Durability guarantee: even if crash, no committed data lost
  - Streaming replication: WAL ship karo standby ko → real-time copy

─── WAL file location ───
$PGDATA/pg_wal/
  000000010000000000000001   ← WAL segment (16MB default)
  000000010000000000000002
  ...

─── Checkpoint ───
  - WAL changes → data files sync
  - After checkpoint: WAL segments before it can be recycled
  - checkpoint_completion_target = 0.9 (spread over 90% of checkpoint interval)
  - checkpoint_timeout = 5min (default)
  - max_wal_size = 1GB (trigger checkpoint if WAL grows beyond this)

─── Point-in-Time Recovery (PITR) ───
  Base backup + WAL archives → restore to any point in time
  pg_basebackup → full snapshot
  archive_command = 'cp %p /wal_archive/%f'  → WAL archiving
  restore_command = 'cp /wal_archive/%f %p'  → recovery

─── WAL settings for performance ───
  synchronous_commit = on     → wait for WAL fsync (safest, slower)
  synchronous_commit = off    → no fsync wait (faster, ~400ms data loss risk)
  wal_compression = on        → compress WAL segments (save disk/bandwidth)
  wal_level = replica         → needed for streaming replication
  wal_level = logical         → needed for logical replication

─── wal_level options ───
  minimal:  minimal WAL — no replication possible
  replica:  streaming replication + PITR
  logical:  logical replication (table-level, cross-version)
```

```sql
-- Check WAL stats
SELECT * FROM pg_stat_bgwriter;          -- checkpoint frequency, buffers written
SELECT * FROM pg_stat_replication;       -- connected standbys
SELECT pg_current_wal_lsn();             -- current WAL position
SELECT pg_wal_lsn_diff(
    pg_current_wal_lsn(),
    sent_lsn                             -- replication lag in bytes
) FROM pg_stat_replication;
```

---

### Q4: Replication — Streaming vs Logical kab?

**Answer:**
```
─── Streaming Replication (Physical) ───
  WAL stream copy → exact byte-for-byte copy of primary
  
  Primary (pg_hba.conf):
    host  replication  replicator  standby_ip/32  md5

  Primary (postgresql.conf):
    wal_level = replica
    max_wal_senders = 5
    wal_keep_size = 1GB    # keep WAL for slow standbys

  Standby (recovery.conf / postgresql.conf):
    primary_conninfo = 'host=primary_ip user=replicator password=...'
    hot_standby = on        # allow read queries on standby
    recovery_target_timeline = 'latest'

  Use:
    + Read replicas (read-heavy load distribution)
    + High availability (failover)
    + Full replica — same PostgreSQL version
  
  Limitations:
    - Same major version required
    - All databases replicated (no table-level)

─── Logical Replication ───
  Replicates individual tables at SQL level (not byte-for-byte)
  
  Publisher (primary):
    CREATE PUBLICATION my_pub FOR TABLE orders, users;
    wal_level = logical

  Subscriber (standby):
    CREATE SUBSCRIPTION my_sub
    CONNECTION 'host=primary dbname=mydb user=replicator'
    PUBLICATION my_pub;

  Use:
    + Cross-version migration (upgrade PostgreSQL with zero downtime)
    + Selective table replication
    + Data transformation / filtering
    + Multi-master setups (bi-directional with pglogical)
  
  Limitations:
    - DDL not replicated (CREATE TABLE etc — must run manually)
    - Sequences not replicated

─── INTERVIEW: Read replica kaise load balance karte hain? ───
  1. PgBouncer / HAProxy → route SELECT to replica
  2. SQLAlchemy: separate engine for reads
     read_engine  = create_async_engine("postgresql+asyncpg://replica/db")
     write_engine = create_async_engine("postgresql+asyncpg://primary/db")
  3. Django: DATABASE_ROUTERS with DatabaseRouter
     reads → 'replica', writes → 'default'

─── Replication lag monitoring ───
  -- On primary:
  SELECT client_addr, state, sent_lsn, write_lsn, flush_lsn, replay_lsn,
         pg_wal_lsn_diff(sent_lsn, replay_lsn) AS lag_bytes
  FROM pg_stat_replication;

  Alert if lag_bytes > 50MB (configurable per use case)
```

---

### Q5: Connection Pooling — pgBouncer deep dive?

**Answer:**
```
─── Why connection pooling? ───
  PostgreSQL: each connection = OS process (~5-10MB RAM)
  100 connections = 500MB-1GB RAM just for processes
  pgBouncer: lightweight proxy — maintains small pool, reuses connections

─── pgBouncer modes ───

  Session pooling (default):
    Client connected → server connection assigned until client disconnects
    Same as no pooling (almost)
    Use: when app uses session-level features (temp tables, SET)

  Transaction pooling (recommended for web apps):
    Server connection returned to pool AFTER each transaction
    100 app connections → 10 real PostgreSQL connections!
    CANNOT use: LISTEN, named prepared statements, advisory locks, SET
    Use: stateless apps (Django/FastAPI with ORM)

  Statement pooling:
    Connection returned after each statement
    Rarely used — most apps have multi-statement transactions

─── pgBouncer config (/etc/pgbouncer/pgbouncer.ini) ───

  [databases]
  myapp = host=127.0.0.1 port=5432 dbname=myapp

  [pgbouncer]
  listen_addr = 0.0.0.0
  listen_port = 6432
  auth_type = md5
  auth_file = /etc/pgbouncer/userlist.txt

  pool_mode = transaction          # recommended
  max_client_conn = 1000           # max app connections
  default_pool_size = 20           # real PostgreSQL connections
  min_pool_size = 5                # keep warm connections
  reserve_pool_size = 5            # emergency connections
  reserve_pool_timeout = 5         # wait before using reserve

  server_idle_timeout = 600        # close idle server connections
  client_idle_timeout = 0          # don't close idle clients
  server_lifetime = 3600           # recycle connections hourly

─── Monitoring pgBouncer ───
  SHOW POOLS;       -- active, idle, waiting connections
  SHOW STATS;       -- requests/sec, avg query time
  SHOW CLIENTS;     -- connected clients
  SHOW SERVERS;     -- real PostgreSQL connections

─── SQLAlchemy pool settings (when NOT using pgBouncer) ───
  create_async_engine(
      url,
      pool_size=10,          # persistent connections
      max_overflow=5,        # temporary extra connections
      pool_timeout=30,       # wait 30s for available connection
      pool_recycle=1800,     # recycle connections every 30min (avoid stale)
      pool_pre_ping=True,    # test connection before use
  )
```

---

## Summary

| Concept | When to Act |
|---------|-------------|
| VACUUM | n_dead_tup > 20% of live rows |
| VACUUM FULL | table bloat >50%, during maintenance window |
| VACUUM FREEZE | age(relfrozenxid) > 1.5 billion XID |
| Deadlock prevention | Consistent lock order + lock_timeout + FOR UPDATE |
| WAL level | `replica` for HA, `logical` for cross-version migration |
| Streaming replication | Same version, full DB copy, HA/read replicas |
| Logical replication | Table-level, cross-version, selective sync |
| pgBouncer mode | `transaction` for web apps, `session` for stateful |

| pg_stat view | Shows |
|-------------|-------|
| `pg_stat_user_tables` | n_dead_tup, last_vacuum, seq_scan vs idx_scan |
| `pg_stat_activity` | Active queries, long transactions, blocking |
| `pg_stat_replication` | Standby lag, WAL sent/received |
| `pg_stat_bgwriter` | Checkpoint frequency, buffers written |
| `pg_locks` | Active locks, waiting locks |
