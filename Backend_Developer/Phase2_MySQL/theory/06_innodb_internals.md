# InnoDB Internals

## Why It Matters

InnoDB = MySQL's default storage engine. Understanding internals critical for:
- **Performance tuning** (buffer pool, redo log size)
- **Lock troubleshooting** (next-key locks, deadlocks)
- **Crash recovery understanding**
- **Query plan optimization** (clustered vs secondary indexes)

Senior interview: "Why do MySQL queries slow down after many updates?" → understand MVCC + undo log + purge.

---

## Architecture

```
┌──────────────────────────────────────────┐
│           InnoDB Storage Engine          │
├──────────────────────────────────────────┤
│  Buffer Pool (in-memory cache)           │
│  ├─ LRU list (with midpoint insertion)   │
│  └─ Flush list (dirty pages)             │
├──────────────────────────────────────────┤
│  Redo Log (WAL — write-ahead log)        │
│  Undo Log (MVCC + rollback)              │
│  Doublewrite Buffer (atomic writes)      │
│  Change Buffer (deferred index updates)  │
├──────────────────────────────────────────┤
│  Files: ibdata1, ib_logfile0/1, *.ibd    │
└──────────────────────────────────────────┘
```

## Buffer Pool

Memory-resident cache of disk pages (16KB each).

```sql
SHOW VARIABLES LIKE 'innodb_buffer_pool_size';
-- Default 128MB. Production: 50-70% of RAM.

SET GLOBAL innodb_buffer_pool_size = 17179869184;  -- 16GB
```

**LRU with midpoint insertion:**

```
[ Young (5/8) ──────── | ─ Old (3/8) ]
                       ↑
                  new pages inserted here
```

Prevents one-time scans from evicting hot pages. New pages → midpoint. Only promoted to young after second access.

**Tune:**

```sql
SET GLOBAL innodb_old_blocks_pct = 37;       -- % of buffer pool in old sublist
SET GLOBAL innodb_old_blocks_time = 1000;    -- ms before promotion to young
```

## Redo Log (Write-Ahead Log)

```sql
SHOW VARIABLES LIKE 'innodb_log_file_size';
```

Two files (default 48MB each). Cycle between them. Every change logged BEFORE data file write.

**Recovery:** On crash, replay redo log to bring data files up-to-date. Larger redo = longer between checkpoints = better write throughput, slower recovery.

**Tune:**

```ini
[mysqld]
innodb_log_file_size = 2G        # large for write-heavy
innodb_log_files_in_group = 2
innodb_log_buffer_size = 64M
innodb_flush_log_at_trx_commit = 1   # 1=fsync each commit (ACID), 2=fsync per sec
```

## Undo Log

Stores old versions of rows for:
1. **Rollback** — UNDO a transaction
2. **MVCC** — read versions visible per snapshot
3. **Purge** — clean up deleted rows after no transaction needs them

Lives in `ibdata1` (pre-5.7) or undo tablespaces (5.7+).

**Why MySQL slows after deletes:** undo log grows. Purge thread can't keep up if active long-running txns block purge.

```sql
SHOW ENGINE INNODB STATUS\G
-- Look for History list length
```

History > 1M = purge falling behind. Kill long-running txns.

## Doublewrite Buffer

Writes pages to separate buffer first, then to actual data file. Protects against torn pages (partial page writes during crash).

```sql
SHOW VARIABLES LIKE 'innodb_doublewrite';
```

Default ON. Disable only on filesystems with atomic writes (ZFS, etc).

## Change Buffer

Defers secondary index updates for non-unique indexes when target page not in buffer pool. Merges later when page loaded.

```sql
SHOW VARIABLES LIKE 'innodb_change_buffering';
-- 'all' (default), 'inserts', 'deletes', 'purges', 'changes', 'none'

SHOW VARIABLES LIKE 'innodb_change_buffer_max_size';  -- % of buffer pool, default 25
```

**Trade-off:** Faster writes, slightly slower reads (until merge). Mostly invisible.

## Adaptive Hash Index

In-memory hash index for frequently-accessed pages. Auto-built.

```sql
SHOW VARIABLES LIKE 'innodb_adaptive_hash_index';
```

For random access patterns, can hurt — try disabling.

## Clustered vs Secondary Indexes

**Clustered Index = primary key** stored with row data. One per table.

```
Primary Key (id) → leaf node = ENTIRE ROW
```

**Secondary Index** stores indexed columns + primary key (not data):

```
Secondary index on (email) → leaf = (email, id)
SELECT * FROM users WHERE email = 'x' →
  1. lookup email in secondary index → get id
  2. lookup id in clustered index → get row
```

**Implications:**
- Primary key should be sequential (INT AUTO_INCREMENT, not UUID — UUID causes B+ tree fragmentation)
- Secondary index lookups = 2 B+ tree walks unless covered
- Cover queries via include columns: `INDEX(email) INCLUDE (name)`

## Row Formats

```sql
SHOW TABLE STATUS WHERE Name = 'users';

ALTER TABLE users ROW_FORMAT=DYNAMIC;
```

| Format | Use Case |
|---|---|
| REDUNDANT | Legacy, avoid |
| COMPACT | Default pre-5.7 |
| DYNAMIC | Default 5.7+, off-page storage |
| COMPRESSED | Smaller but slower (CPU cost) |

For tables with BLOB/TEXT: DYNAMIC stores off-page.

## Page Structure (16KB Default)

```
[ Header ][ Records ... ][ Free ][ Page Trailer ]
```

Each page stores ~7 indexed rows on average. Smaller pages (4K, 8K) for SSD with smaller IO; larger (32K, 64K) for HDD.

## Lock Types

- **Record lock** — single row index entry
- **Gap lock** — gap between index records (prevents phantom inserts)
- **Next-key lock** = record + gap (default at REPEATABLE READ)
- **Intention lock** — table-level "I plan to lock rows" (compatibility)

```sql
SELECT * FROM users WHERE id = 5 FOR UPDATE;
-- Locks row 5 + small gap around it

SELECT * FROM users WHERE id > 10 FOR UPDATE;
-- Locks all matching rows + gaps (prevents phantom inserts)
```

## Deadlock Detection

InnoDB auto-detects (cycle in wait-for graph), aborts one txn:

```sql
SHOW ENGINE INNODB STATUS\G
-- "LATEST DETECTED DEADLOCK" section shows last deadlock
```

To minimize deadlocks: lock in consistent order (by PK ascending).

## MVCC Implementation

Each row has hidden columns:
- `DB_TRX_ID` — transaction that created/modified this row version
- `DB_ROLL_PTR` — pointer to undo log entry (older version)
- `DB_ROW_ID` — used if no primary key (synthetic)

```
Row R history (via undo log):
  Current: { name: 'C', trx_id: 100 }
  Undo: { name: 'B', trx_id: 95 }
  Undo: { name: 'A', trx_id: 90 }

Transaction 92 reads R:
  See { name: 'A' } (its snapshot includes 90 but not 95)
```

---

## Common Pitfalls

### 1. UUID Primary Key

UUID = random → inserts go to random B+ tree positions → page splits → fragmentation. Use AUTO_INCREMENT INT or UUIDv7 (time-ordered).

### 2. Buffer Pool Too Small

```sql
SELECT (1 - Innodb_buffer_pool_reads / Innodb_buffer_pool_read_requests) * 100 AS hit_ratio
FROM information_schema.global_status
WHERE variable_name IN ('Innodb_buffer_pool_reads', 'Innodb_buffer_pool_read_requests');
```

< 95% hit rate → buffer pool too small. Increase up to 70% RAM.

### 3. Long-Running Transactions Block Purge

```sql
SELECT * FROM information_schema.innodb_trx
ORDER BY trx_started ASC;
```

Old transactions hold undo log → can't be purged → tablespace grows.

### 4. Redo Log Too Small

Frequent checkpoints → poor write throughput. Resize:

```ini
innodb_log_file_size = 2G  # or larger for write-heavy
```

Restart required. Larger = longer crash recovery but better throughput.

### 5. `innodb_flush_log_at_trx_commit = 2`

Faster but loses up to 1 second of transactions on crash. OK for non-critical. For ACID: keep at 1.

### 6. Wrong Row Format for BLOBs

`COMPACT` stores BLOBs inline (slow). Use `DYNAMIC` (default 5.7+) — BLOBs off-page.

---

## Interview Q&A

**Q1:** InnoDB buffer pool kaise size karoge?
**A:** 50-70% of RAM (leave room for OS, other processes, sort buffers). Monitor hit ratio (Innodb_buffer_pool_reads / read_requests) — want > 95%. Larger = fewer disk reads. Tune `innodb_buffer_pool_instances` for concurrency (8-16 instances on big pools).

**Q2:** Redo log size impact?
**A:** Larger redo log = longer between checkpoints = more sequential writes (better throughput). Trade-off: longer crash recovery time. Production write-heavy: 2-4 GB. innodb_flush_log_at_trx_commit=1 for ACID (fsync per commit), =2 for ~1s data loss tolerance.

**Q3:** MVCC kaise kaam karta hai InnoDB mein?
**A:** Hidden columns DB_TRX_ID, DB_ROLL_PTR per row. Updates create new version + chain to old in undo log. Read view = snapshot of TRX_IDs visible at start. Reads filter row versions by visibility. No reader locks. Purge thread cleans up after no active txn needs the old version.

**Q4:** Long-running transactions ka bad effect?
**A:** Old txn keeps undo log entries alive → purge can't clean up → undo grows → reads slow (must traverse longer undo chain). Also: read view stays "old", may miss recent commits. Monitor `History list length` in SHOW ENGINE INNODB STATUS. Kill old txns.

**Q5:** Next-key lock vs record lock?
**A:** Record lock = single index entry. Next-key = record + gap before it (prevents phantom inserts at REPEATABLE READ). For `WHERE id = 5 FOR UPDATE`, MySQL takes next-key (locks 5 + gap to next existing key). At READ COMMITTED, no gap locks (only record).

**Q6:** Clustered index UUID ke saath problem?
**A:** UUIDv4 is random — every insert goes to random B+ tree position → page splits → fragmentation → bigger index → slower. Solutions: (1) AUTO_INCREMENT INT. (2) UUIDv7 (time-ordered). (3) ULID (time-prefixed). For sharded systems where UUID needed, snowflake-style IDs work too.

**Q7:** Doublewrite buffer ka purpose?
**A:** Protects against torn pages — partial page write during crash (16KB write not atomic at OS level). Doublewrite: write to buffer first, then to data file. If crash during 2nd write, recover from buffer. Performance cost ~5-10%. Disable only on filesystems with atomic writes (ZFS).

**Q8:** Deadlock production mein kaise kam karein?
**A:** (1) Lock in consistent order (by PK ASC). (2) Short transactions (release locks fast). (3) Lower isolation (READ COMMITTED has no gap locks). (4) `innodb_lock_wait_timeout` smaller (50s default — fail fast). (5) Monitor deadlock count, app-level retry on 1213 errors.

---

## Real-World Use Cases

### 1. Write-Heavy OLTP Tuning

```ini
innodb_buffer_pool_size = 32G
innodb_log_file_size = 4G
innodb_log_buffer_size = 128M
innodb_flush_log_at_trx_commit = 1
innodb_doublewrite = ON
innodb_io_capacity = 2000           # for SSD
innodb_io_capacity_max = 4000
innodb_flush_neighbors = 0           # disable for SSD
```

### 2. Read-Heavy Reporting

```ini
innodb_buffer_pool_size = 60% RAM  # max caching
innodb_adaptive_hash_index = ON
innodb_change_buffer_max_size = 50
```

### 3. Large Tables (Time-Series)

Use partitioning to scale. Older partitions less frequently accessed → less buffer pool pressure.

---

## References

- [InnoDB Architecture](https://dev.mysql.com/doc/refman/8.0/en/innodb-architecture.html)
- [Buffer Pool](https://dev.mysql.com/doc/refman/8.0/en/innodb-buffer-pool.html)
- [InnoDB Locking](https://dev.mysql.com/doc/refman/8.0/en/innodb-locking.html)
- "High Performance MySQL" 4th edition
- Mark Callaghan's MySQL blog
