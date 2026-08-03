# Databases — MySQL & PostgreSQL Operations

**DevOps Track · Phase 15: Databases**

> Complementary to the app-level coverage in Backend_Developer/ — this covers the infra/ops angle: hardening, deployment, and operating these systems.

## Quick Concepts

- **Replication** = copying data from a primary DB to one or more replicas, for HA and read scaling
- **Async replication** = primary doesn't wait for replica ack before confirming a write — fast, but replica can lag and lose the most recent writes on primary failure
- **Semi-sync replication** = primary waits for at least one replica to acknowledge receipt (not apply) before confirming the write — a middle ground
- **Streaming replication (Postgres)** = replica continuously receives and replays WAL (Write-Ahead Log) segments from the primary
- **Replication lag** = how far behind a replica is from the primary, measured in time or bytes/LSN — the #1 metric to watch on any replicated DB
- **Logical backup** = SQL statements or a portable dump that reconstructs data (`mysqldump`, `pg_dump`) — slow to restore, portable across versions
- **Physical backup** = raw copy of data files/WAL (`pg_basebackup`, Percona XtraBackup) — fast restore, tied to DB version/architecture
- **PITR (Point-in-Time Recovery)** = restoring a DB to an exact timestamp by replaying WAL/binlog after a base backup
- **Connection pooling** = reusing a fixed set of DB connections across many app requests instead of opening one per request — PgBouncer is the standard tool for Postgres
- **Slow query log** = DB-level log of queries exceeding a duration threshold — the first place to look when a DB is under load
- **`EXPLAIN ANALYZE`** = runs a query and reports the actual execution plan and timings — the tool that tells you WHY a query is slow, not just that it is
- **VACUUM** = reclaims space from dead row versions PostgreSQL's MVCC model leaves behind on UPDATE/DELETE — `autovacuum` does this automatically unless something blocks it

---

## Why This Matters for Ops

```
App-level SQL work (writing efficient queries, ORM usage,
indexing for a specific query pattern) lives in Backend_Developer/.

The ops job is different:
   - Will this DB survive the primary dying at 3am?
   - Can we restore from backup to an exact point in time after
     a bad migration wiped data?
   - Is the connection count from 50 app pods about to exhaust
     max_connections and take the whole DB down?
   - Is a replica silently 20 minutes behind, serving stale reads
     to users without anyone noticing?

These are infra questions. Getting them wrong doesn't show up as
a slow query — it shows up as a full outage or permanent data loss.
```

---

## MySQL vs PostgreSQL — Replication Models

### MySQL: Async vs Semi-Sync

```
Async (default):
Primary ---write---> commits locally ---> confirms to client
                  \\--(async)--> replica applies later

   Fast. Replica can be behind. On primary crash, any writes not
   yet shipped to the replica are LOST if you fail over to it.

Semi-sync (rpl_semi_sync):
Primary ---write---> waits for >=1 replica ACK (received, not applied)
                  ---> commits ---> confirms to client

   Slower (extra round trip). Guarantees at least one replica has
   the write in its relay log before the primary confirms — much
   lower (not zero) risk of data loss on failover.
```

```sql
-- MySQL: check replication status on a replica
SHOW REPLICA STATUS\G
-- key fields: Seconds_Behind_Source, Replica_IO_Running, Replica_SQL_Running

-- Enable semi-sync (both sides need the plugin)
INSTALL PLUGIN rpl_semi_sync_source SONAME 'semisync_source.so';
SET GLOBAL rpl_semi_sync_source_enabled = 1;
SET GLOBAL rpl_semi_sync_source_timeout = 1000;  -- ms, falls back to async after
```

### PostgreSQL: Streaming Replication

```
Primary continuously ships WAL (Write-Ahead Log) segments to
replicas, which replay them to stay in sync.

synchronous_commit = off       → async, fastest, same lag risk as MySQL async
synchronous_commit = on        → primary waits for WAL flush on primary only
synchronous_commit = remote_write → waits for replica to receive + write (not fsync)
synchronous_commit = remote_apply → waits for replica to APPLY — strongest guarantee, slowest
```

```ini
# postgresql.conf — primary
wal_level = replica
max_wal_senders = 5
synchronous_standby_names = 'replica1'   # makes it synchronous
synchronous_commit = remote_apply
```

```sql
-- Check replication lag on primary (bytes behind)
SELECT client_addr, state, sent_lsn, replay_lsn,
       pg_wal_lsn_diff(sent_lsn, replay_lsn) AS lag_bytes
FROM pg_stat_replication;

-- Check lag on replica (time behind)
SELECT now() - pg_last_xact_replay_timestamp() AS replication_lag;
```

### Comparison

| | MySQL | PostgreSQL |
|---|---|---|
| Default replication | Async | Async (streaming) |
| Strong-consistency option | Semi-sync (plugin) | Synchronous (`remote_apply`) |
| Failover tooling | Orchestrator, MHA, Group Replication | Patroni, repmgr |
| Multi-primary option | Group Replication, Galera | BDR (extension), less common |
| Logical replication | Yes (binlog-based, row/statement) | Yes (native since PG 10) |

---

## Backup Strategies

### Logical vs Physical

```
Logical (mysqldump / pg_dump):
   + Portable across versions/architectures
   + Human-readable-ish, selective restore (single table)
   - Slow on large DBs (full table scan + reconstruct via SQL)
   - Restore is slow (replaying SQL, rebuilding indexes)

Physical (Percona XtraBackup / pg_basebackup):
   + Fast backup and restore — copies raw data files
   + Supports PITR when combined with binlog/WAL archiving
   - Tied to the exact DB version and often OS/architecture
   - Not selectively restorable at the table level (without extra tooling)
```

```bash
# MySQL logical backup
mysqldump -h localhost -u root -p --single-transaction \
    --routines --triggers mydb > backup.sql
gzip backup.sql

# MySQL physical backup (Percona XtraBackup — hot backup, no downtime)
xtrabackup --backup --target-dir=/backup/full --user=root --password=...
xtrabackup --prepare --target-dir=/backup/full

# Postgres logical backup
pg_dump -h localhost -U postgres -Fc mydb > backup.dump   # custom format
pg_restore -d mydb backup.dump

# Postgres physical backup (base backup for streaming replication setup)
pg_basebackup -h primary_host -D /var/lib/postgresql/backup -U replicator -Fp -Xs -P
```

### Point-in-Time Recovery (PITR)

```
Base backup (nightly, physical) + continuous WAL/binlog archiving
   = restore to ANY second between the base backup and now.

Real use case: a bad migration or "DELETE FROM orders" without a
WHERE clause runs at 14:32. PITR lets you restore to 14:31:59 —
one second before the mistake — instead of losing everything since
last night's backup.
```

```ini
# postgresql.conf — enable WAL archiving for PITR
archive_mode = on
archive_command = 'cp %p /archive/wal/%f'
```

```bash
# Restore to a specific point in time
# 1. Restore the base backup
# 2. Create recovery.signal + set recovery_target_time in postgresql.conf
echo "recovery_target_time = '2026-07-25 14:31:59'" >> postgresql.conf
touch /var/lib/postgresql/data/recovery.signal
pg_ctl start   # replays WAL up to that exact timestamp, then stops
```

```bash
# MySQL PITR: base backup + binlog replay
mysqlbinlog --start-datetime="2026-07-25 00:00:00" \
            --stop-datetime="2026-07-25 14:31:59" \
            mysql-bin.000123 | mysql -u root -p mydb
```

### Backup Retention Pattern

```bash
#!/usr/bin/env bash
set -euo pipefail
# nightly cron: full logical backup, 7-day retention, off-box copy
DATE=$(date +%Y%m%d)
pg_dump -Fc mydb > /backup/mydb-$DATE.dump
aws s3 cp /backup/mydb-$DATE.dump s3://backups-bucket/postgres/
find /backup -name "mydb-*.dump" -mtime +7 -delete
```

---

## Connection Pooling at the Infra Level — PgBouncer

```
Problem: Postgres forks a full OS process per connection. Each app
pod might hold 10-20 idle connections "just in case." Scale to 50
pods and you're at 500-1000 connections against a DB with
max_connections=200 — the DB falls over from connection overhead
alone, independent of actual query load.

Fix: PgBouncer sits between apps and Postgres, multiplexing many
client connections onto a small pool of real DB connections.
```

```ini
# pgbouncer.ini
[databases]
mydb = host=127.0.0.1 port=5432 dbname=mydb

[pgbouncer]
listen_port = 6432
auth_type = md5
pool_mode = transaction     # release connection back to pool after each transaction
                             # (vs session — held for the client's whole session)
default_pool_size = 20      # real DB connections per database
max_client_conn = 1000      # client-facing connections PgBouncer accepts
```

```bash
# App connects to PgBouncer's port, not Postgres directly
DATABASE_URL=postgres://user:pass@pgbouncer-host:6432/mydb

# Inspect pool state
psql -h pgbouncer-host -p 6432 pgbouncer -c "SHOW POOLS;"
psql -h pgbouncer-host -p 6432 pgbouncer -c "SHOW STATS;"
```

```
pool_mode = transaction is the standard choice for stateless web apps —
it lets far more app connections share far fewer real DB connections
since each is only held for the duration of a transaction, not the
whole client session.

Gotcha: transaction mode breaks session-level features — prepared
statements across transactions, SET commands meant to persist,
LISTEN/NOTIFY. Know what your ORM relies on before switching modes.
```

---

## User & Permission Management

Every DB in this file assumes credentials already exist — here's how they actually get created, and why "just use the superuser everywhere" is the ops equivalent of the AWS `s3:*` wildcard anti-pattern from Phase 7.

```sql
-- PostgreSQL
CREATE ROLE app_user WITH LOGIN PASSWORD 'change-me';
GRANT CONNECT ON DATABASE mydb TO app_user;
GRANT USAGE ON SCHEMA public TO app_user;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO app_user;

-- A read-only role for reporting/analytics — same idea as an IAM
-- least-privilege role, applied at the database level
CREATE ROLE readonly_user WITH LOGIN PASSWORD 'change-me';
GRANT CONNECT ON DATABASE mydb TO readonly_user;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO readonly_user;

-- Revoke, when a role should no longer have access
REVOKE ALL PRIVILEGES ON ALL TABLES IN SCHEMA public FROM app_user;

-- See who can do what
\du                                    -- list roles (psql meta-command)
SELECT grantee, privilege_type, table_name
FROM information_schema.role_table_grants
WHERE grantee = 'app_user';
```

```sql
-- MySQL — same idea, different syntax
CREATE USER 'app_user'@'%' IDENTIFIED BY 'change-me';
GRANT SELECT, INSERT, UPDATE, DELETE ON mydb.* TO 'app_user'@'%';

CREATE USER 'readonly_user'@'%' IDENTIFIED BY 'change-me';
GRANT SELECT ON mydb.* TO 'readonly_user'@'%';

REVOKE ALL PRIVILEGES ON mydb.* FROM 'app_user'@'%';
FLUSH PRIVILEGES;    -- MySQL needs this after direct grant table edits (not needed
                        -- after GRANT/REVOKE statements themselves, but a common
                        -- habit/safety net when troubleshooting permission issues)

SHOW GRANTS FOR 'app_user'@'%';
```

```
Real ops discipline: the app connects as app_user (scoped to exactly
the CRUD it needs), a SEPARATE readonly_user backs any BI/reporting
tool, and the actual superuser/postgres/root account is used ONLY for
schema migrations and emergency access — never as the app's everyday
connection string. Same least-privilege principle as IAM (Phase 7),
just enforced at the database layer instead of the cloud provider layer.
```

---

## VACUUM — Preventing PostgreSQL Table Bloat

PostgreSQL never overwrites a row in place on `UPDATE`/`DELETE` — it writes a new row version and marks the old one dead (MVCC — Multi-Version Concurrency Control, what lets concurrent readers never block on a writer). Dead rows accumulate as **bloat** until something reclaims that space.

```sql
VACUUM orders;              -- reclaim space from dead rows, make it
                               -- available for REUSE by future writes to
                               -- THIS table (does NOT shrink the file on disk)
VACUUM ANALYZE orders;         -- also updates the query planner's statistics —
                                 -- run this after a large bulk load/delete,
                                 -- stale statistics cause the planner to pick
                                 -- genuinely bad query plans
VACUUM FULL orders;              -- ACTUALLY shrinks the file on disk — but
                                    -- takes an EXCLUSIVE lock for the duration,
                                    -- blocking all reads/writes to the table.
                                    -- Rarely run on a live production table
                                    -- without a real maintenance window.
```

```bash
# Check autovacuum activity and table bloat
psql -c "SELECT relname, n_dead_tup, n_live_tup, last_autovacuum
          FROM pg_stat_user_tables ORDER BY n_dead_tup DESC LIMIT 10;"
```

```
autovacuum runs automatically in the background by default — most of
the time you never think about VACUUM at all. It becomes an ops
problem specifically when:
  - A high-write-volume table's autovacuum can't keep up with the
    dead-row generation rate (n_dead_tup keeps climbing) — tune
    autovacuum_vacuum_scale_factor/cost_limit more aggressively for
    that specific table
  - A long-running transaction (an idle connection holding an open
    transaction, a stuck migration) prevents VACUUM from reclaiming
    anything at all, because MVCC must keep old row versions visible
    to that still-open transaction — "why isn't autovacuum reclaiming
    space" often traces back to exactly this
  - Transaction ID wraparound — Postgres's internal transaction
    counter is finite; if autovacuum genuinely can't keep up for an
    extended period, Postgres will eventually refuse new writes
    entirely to protect data integrity. Rare, but the single most
    severe VACUUM-related failure mode, and why monitoring
    n_dead_tup/autovacuum lag matters at all in a healthy system.
```

**Interview framing:** "why does a PostgreSQL table on-disk size keep growing even though row count is stable" is almost always dead tuples from UPDATE/DELETE churn outpacing autovacuum — the fix is tuning autovacuum aggressiveness for that table (or finding and killing the long-running transaction blocking it), not `VACUUM FULL` as a routine maintenance habit.

---

## Monitoring Key Metrics

| Metric | MySQL | PostgreSQL | Why it matters |
|---|---|---|---|
| Replication lag | `Seconds_Behind_Source` | `pg_last_xact_replay_timestamp()` diff | Stale reads on replicas, failover data-loss risk |
| Connection count | `SHOW STATUS LIKE 'Threads_connected'` | `SELECT count(*) FROM pg_stat_activity` | Approaching `max_connections` = imminent outage |
| Slow queries | `slow_query_log` + `long_query_time` | `log_min_duration_statement` | First place to look when latency spikes |
| Lock waits | `SHOW ENGINE INNODB STATUS` | `pg_locks` join `pg_stat_activity` | Diagnoses blocking/deadlock incidents |
| Disk usage / WAL growth | `information_schema.tables` | `pg_database_size()`, `pg_wal` dir size | Unbounded WAL growth = disk full = DB down |
| Cache hit ratio | InnoDB buffer pool hit rate | `pg_stat_database` blks_hit/blks_read | Low ratio = undersized memory for working set |

```sql
-- Postgres: enable + inspect slow query log
-- postgresql.conf: log_min_duration_statement = 500   (ms)
SELECT query, calls, mean_exec_time, total_exec_time
FROM pg_stat_statements
ORDER BY total_exec_time DESC LIMIT 10;

-- MySQL: enable slow query log
SET GLOBAL slow_query_log = 'ON';
SET GLOBAL long_query_time = 0.5;
-- tail: /var/log/mysql/mysql-slow.log
```

### `EXPLAIN` — What the Slow Query Log Points You Toward Next

The slow query log tells you WHICH query is slow. `EXPLAIN` tells you WHY.

```sql
-- Postgres — ANALYZE actually RUNS the query and reports real timings,
-- not just the planner's estimate (plain EXPLAIN only estimates, never executes)
EXPLAIN ANALYZE
SELECT * FROM orders WHERE customer_id = 42 AND status = 'pending';
```

```
Seq Scan on orders  (cost=0.00..18334.00 rows=1 width=120)
                    (actual time=45.201..120.442 rows=3 loops=1)
  Filter: (customer_id = 42 AND status = 'pending')
  Rows Removed by Filter: 999997
Planning Time: 0.112 ms
Execution Time: 120.501 ms
```

```
Seq Scan (sequential/full table scan) on a million-row table, filtering
OUT 999,997 rows to find 3 — this is the single most common thing
EXPLAIN ANALYZE reveals: a missing index. The fix:

CREATE INDEX idx_orders_customer_status ON orders(customer_id, status);

-- Re-run EXPLAIN ANALYZE afterward — the plan should now show:
Index Scan using idx_orders_customer_status on orders
                    (actual time=0.045..0.089 rows=3 loops=1)
```

```sql
-- MySQL equivalent
EXPLAIN ANALYZE SELECT * FROM orders WHERE customer_id = 42 AND status = 'pending';
-- or, older MySQL versions without ANALYZE support:
EXPLAIN SELECT * FROM orders WHERE customer_id = 42;
-- look for type: ALL (full table scan, bad) vs type: ref/range (index used, good)
```

```
Senior habit: NEVER add an index blind because "it might help" — every
index speeds up reads but slows down every WRITE to that table (the
index itself must be updated) and takes disk space. Confirm the actual
problem with EXPLAIN ANALYZE first, add the index, then EXPLAIN ANALYZE
again to confirm the plan actually changed and execution time actually
dropped — don't assume, verify both ends of the fix.
```

---

## Senior Tip

```
Replication lag and connection count are the two metrics that turn
"degraded" into "down" fastest, and both are silent until they aren't
— a replica can lag for hours with zero errors logged anywhere, until
someone reads stale data and files a confused bug report. Alert on
both proactively (lag > 10s, connections > 80% of max), don't wait
to discover them during an incident.
```

## Interview Angle

**Q: Why would you choose semi-sync/synchronous replication over async, given the latency cost?**
When data loss on failover is unacceptable (financial transactions,
order records) — async replication can lose the last few seconds of
writes if the primary dies before shipping them. Semi-sync/sync
trades write latency for a durability guarantee at failover time.

**Q: What's the practical difference between logical and physical backups for a 500GB database?**
Physical backup (XtraBackup/pg_basebackup) copies raw files — minutes
to hours depending on I/O, and restore is comparably fast. Logical
backup (mysqldump/pg_dump) has to read and reconstruct every row via
SQL — can take much longer on both backup and restore, but is portable
across DB versions and lets you restore just one table if needed.

**Q: How does PgBouncer's `transaction` pool mode change what the app can rely on?**
The underlying DB connection is returned to the pool as soon as a
transaction commits, not when the client disconnects — so a different
app connection may reuse that DB connection for the next transaction.
Session-scoped state (prepared statements, `SET` variables meant to
persist, advisory locks held across transactions) breaks under this
mode because there's no guarantee of the same physical connection.

**Q: A query flagged by the slow query log is doing a full table scan on a million-row table. How do you confirm that, and what's the fix?**
`EXPLAIN ANALYZE` on the query — a `Seq Scan` with a high `Rows Removed by Filter` count confirms it's scanning far more rows than it returns. The fix is usually a composite index on the columns in the `WHERE` clause, then re-running `EXPLAIN ANALYZE` to confirm the plan switched to an `Index Scan` and execution time actually dropped — never add an index on assumption alone, since every index also slows down writes to that table.

**Q: A PostgreSQL table's on-disk size keeps growing even though its row count has been stable for weeks. What's the likely cause?**
Table bloat from dead row versions — PostgreSQL's MVCC model writes a new row version on every UPDATE and marks the old one dead rather than overwriting in place, and if `autovacuum` can't keep up with that churn (or a long-running transaction is preventing it from reclaiming anything), dead tuples accumulate as bloat. Check `pg_stat_user_tables` for a high `n_dead_tup` and a stale `last_autovacuum`, then either tune autovacuum more aggressively for that table or find and end the long-running transaction blocking it.

---

## Related

- [02_nosql_mongodb_redis.md](02_nosql_mongodb_redis.md) — MongoDB and Redis ops
- [../../Backend_Developer/00_Year0-2_Junior/07_Django_DRF/01_orm_deep_dive.md](../../Backend_Developer/00_Year0-2_Junior/07_Django_DRF/01_orm_deep_dive.md) — app-level ORM/query patterns
