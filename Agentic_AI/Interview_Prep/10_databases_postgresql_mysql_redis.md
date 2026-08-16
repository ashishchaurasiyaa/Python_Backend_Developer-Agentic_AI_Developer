# Databases Deep Guide — PostgreSQL · MySQL · Redis
### Resume Skills: PostgreSQL, MySQL, Redis, Query Optimization, Indexing
### PwC Interview Ready · 3-4 baar padho

> **Reading plan:**
> - Pass 1: Poora padho — architecture samjho
> - Pass 2: Interview Answer sections loud bolke practice karo
> - Pass 3: Architecture diagrams haath se draw karo
> - Pass 4: Quick Recall Card only

---

## TABLE OF CONTENTS

| # | Topic | Tera Resume Project |
|---|---|---|
| 1 | PostgreSQL — Architecture + Internals | Youngman Beta, Niroskos, ALL projects |
| 2 | Indexing Deep Dive | 60% latency reduction ka basis |
| 3 | Transactions + Isolation Levels | SAP HANA idempotent ops |
| 4 | Query Optimization | p95 latency reduction |
| 5 | MySQL — vs PostgreSQL | YES Platform, NFC Tracker |
| 6 | Redis — Architecture + Data Structures | Niroskos, Toofan |
| 7 | Redis Use Cases | Caching, Sessions, Rate Limiting, Pub/Sub |
| 8 | Interview Q&A — 20 Questions | PwC specific |
| 9 | Quick Recall Card | 1 ghanta pehle |

---

## TOPIC 1: POSTGRESQL — ARCHITECTURE + INTERNALS

### Definition
```
PostgreSQL = Open-source RDBMS (Relational Database Management System).
"Most advanced open source database" — ACID compliant, extensible.
1996 se available — battle-tested, enterprise-ready.
Tera primary DB har production project mein.
```

### Simple Example (analogy)
```
PostgreSQL = Swiss Army knife of databases

MySQL  = Specialized chef knife (fast, focused, web apps)
MongoDB = Bucket (dump anything, no structure)
PostgreSQL = Swiss Army knife:
  ✅ Relational data (tables, JOINs)
  ✅ JSON/JSONB (document store)
  ✅ Full-text search (like Elasticsearch, lighter)
  ✅ Vector search (pgvector — RAG ke liye)
  ✅ Time-series (partitioned tables)
  ✅ GIS data (PostGIS extension)
  ✅ Advanced indexing (B-tree, GIN, GiST, BRIN)
```

### PostgreSQL Architecture — internals

```
POSTGRESQL PROCESS ARCHITECTURE
────────────────────────────────────────────────────────

CLIENT (Python / Django / psycopg2)
    │
    │  TCP connection (port 5432)
    ▼
POSTMASTER (master process)
    │  Spawns one backend per connection
    │
    ├── BACKEND PROCESS 1 (tera connection)
    │   ├── Parse SQL → Parse Tree
    │   ├── Rewrite rules
    │   ├── Plan (query optimizer → execution plan)
    │   └── Execute → results
    │
    ├── BACKEND PROCESS 2 (doosra connection)
    │
    ├── WAL WRITER     ← Write-Ahead Log (crash recovery)
    ├── CHECKPOINTER   ← Flush dirty pages to disk
    ├── AUTOVACUUM     ← Dead tuple cleanup
    ├── BGWRITER       ← Background buffer flusher
    └── STATS COLLECTOR← pg_stat_* views ka data

MEMORY STRUCTURE:
┌─────────────────────────────────────────────────────┐
│  SHARED MEMORY (sabhi backends share karte hain)    │
│                                                      │
│  ┌──────────────────┐  ┌──────────────────────────┐ │
│  │  SHARED BUFFERS  │  │  WAL BUFFERS             │ │
│  │  (cache: 25% RAM)│  │  (write-ahead log buffer)│ │
│  │                  │  │                          │ │
│  │  8KB pages       │  │  Written before data     │ │
│  │  Hot data here   │  │  for crash recovery      │ │
│  └──────────────────┘  └──────────────────────────┘ │
│                                                      │
│  ┌──────────────────┐  ┌──────────────────────────┐ │
│  │  LOCK TABLE      │  │  PROC ARRAY              │ │
│  │  (row/table      │  │  (active transactions)   │ │
│  │   level locks)   │  │                          │ │
│  └──────────────────┘  └──────────────────────────┘ │
└─────────────────────────────────────────────────────┘

DISK STRUCTURE:
├── pg_data/
│   ├── base/          ← actual table/index files (8KB pages)
│   ├── pg_wal/        ← Write-Ahead Log files
│   ├── pg_tblspc/     ← tablespaces
│   └── global/        ← pg_database, pg_authid catalog
```

### MVCC — Multi-Version Concurrency Control

```
MVCC = Multiple versions of same row exist simultaneously.
No read-write locks — readers don't block writers.

HOW IT WORKS:
───────────────────────────────────────────────────────

ORIGINAL ROW:
┌─────────────────────────────────────────────────────┐
│  id=1  │  amount=1000  │  xmin=100  │  xmax=null   │
│  (xmin = transaction that created this version)     │
│  (xmax = transaction that deleted/updated this)     │
└─────────────────────────────────────────────────────┘

Transaction 200 updates amount to 2000:
┌─────────────────────────────────────────────────────┐
│  id=1  │  amount=1000  │  xmin=100  │  xmax=200    │ ← OLD (dead)
├─────────────────────────────────────────────────────┤
│  id=1  │  amount=2000  │  xmin=200  │  xmax=null   │ ← NEW (live)
└─────────────────────────────────────────────────────┘

Transaction 150 (started BEFORE 200):
→ sees amount=1000 (xmin=100 ≤ 150, xmax=200 > 150)

Transaction 300 (started AFTER 200):
→ sees amount=2000 (xmin=200 ≤ 300, xmax=null)

BENEFIT: Readers never wait for writers, writers never wait for readers.
COST:    Dead tuples accumulate → VACUUM karta hai cleanup.
```

### VACUUM — dead tuple cleanup

```
AUTOVACUUM (automatic, runs in background):
────────────────────────────────────────────
- Dead tuples clean karta hai (old MVCC versions)
- Table stats update karta hai (query planner ke liye)
- Visibility map update (index-only scans ke liye)

WHEN NEEDED:
- High UPDATE/DELETE tables (invoices, orders)
- Table bloat hoti hai without vacuum
- Table bloat → slow full table scans

TUNING (high-write tables):
autovacuum_vacuum_scale_factor = 0.01  # 1% change pe trigger (default 20%)
autovacuum_analyze_scale_factor = 0.005

MANUAL (emergency):
VACUUM ANALYZE invoices;         -- vacuum + update stats
VACUUM FULL invoices;            -- aggressive, table lock! (avoid on prod)

CHECK BLOAT:
SELECT schemaname, tablename,
       n_dead_tup, n_live_tup,
       round(n_dead_tup::numeric/n_live_tup * 100, 2) AS dead_pct
FROM pg_stat_user_tables
WHERE n_live_tup > 0
ORDER BY dead_pct DESC;
```

---

## TOPIC 2: INDEXING DEEP DIVE

### Index types — kab kya

```
INDEX TYPE    OPERATOR         USE CASE
───────────   ──────────────   ────────────────────────────────
B-TREE        =, <, >, BETWEEN Default. Most queries. Range scans.
              LIKE 'abc%'      Sorted access.
              ORDER BY         ← tera 60% latency fix yahan tha

GIN           @>, ?            JSONB queries, full-text search,
              to_tsvector      Array containment
              ANY, ALL

GiST          &&, @>           Geometric/geographic data (PostGIS)
              <->              Nearest neighbor (pgvector!)
              OVERLAPS

BRIN          Range queries    Very large tables (time-series)
              on sequential    Tiny index size
              data             Append-only data (logs, events)

HASH          =                Exact equality only, rarely needed
```

### Index creation — production safe

```sql
-- ═══════════════════════════════════════════════════
-- BASIC INDEX
-- ═══════════════════════════════════════════════════
CREATE INDEX idx_invoice_status
ON invoicing_invoice (status);

-- COMPOSITE INDEX (column order matters!)
CREATE INDEX idx_invoice_company_status
ON invoicing_invoice (company_id, status);
-- Use: WHERE company_id=X AND status=Y ✅
-- Use: WHERE company_id=X              ✅ (leading column)
-- Use: WHERE status=Y                  ❌ (non-leading — index skipped)

-- PARTIAL INDEX (subset of rows — smaller, faster)
CREATE INDEX idx_invoice_pending
ON invoicing_invoice (created_at)
WHERE status = 'pending';
-- Only pending invoices indexed — much smaller

-- CONCURRENT INDEX (zero downtime — production pe yahi karo)
CREATE INDEX CONCURRENTLY idx_invoice_amount
ON invoicing_invoice (amount);
-- No table lock! Build in background.
-- Takes longer but prod traffic unaffected.

-- COVERING INDEX (index-only scan)
CREATE INDEX idx_invoice_cover
ON invoicing_invoice (status, company_id)
INCLUDE (amount, created_at);
-- Query: SELECT amount FROM invoices WHERE status='paid' AND company_id=5
-- Never touches actual table — answered from index alone!

-- ═══════════════════════════════════════════════════
-- CHECK INDEX USAGE
-- ═══════════════════════════════════════════════════
SELECT indexname, idx_scan, idx_tup_read
FROM pg_stat_user_indexes
WHERE relname = 'invoicing_invoice'
ORDER BY idx_scan DESC;
-- idx_scan = 0 → index never used → DROP it!

-- FIND MISSING INDEXES
SELECT relname, seq_scan, seq_tup_read,
       idx_scan, seq_tup_read / seq_scan AS avg_seq_read
FROM pg_stat_user_tables
WHERE seq_scan > 0
ORDER BY seq_tup_read DESC;
-- High seq_tup_read with low idx_scan → needs index!
```

### EXPLAIN ANALYZE — query profiling (tera 60% fix ka tool)

```sql
-- ═══════════════════════════════════════════════════
-- EXPLAIN ANALYZE — actual execution plan
-- ═══════════════════════════════════════════════════
EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT)
SELECT i.invoice_number, i.amount, c.name
FROM invoicing_invoice i
JOIN companies c ON i.company_id = c.id
WHERE i.status = 'pending'
  AND i.created_at > NOW() - INTERVAL '30 days'
ORDER BY i.amount DESC;

-- OUTPUT READING:
-- Seq Scan      → full table scan (BAD for large tables)
-- Index Scan    → index used (GOOD)
-- Index Only    → covering index (BEST — no heap access)
-- Hash Join     → in-memory join (good for large sets)
-- Nested Loop   → good for small inner sets
-- Sort          → ORDER BY needs sort (add index if slow)

-- KEY NUMBERS:
-- actual time=X..Y → Y is total time for node
-- rows=N → actual rows returned
-- Buffers: hit=X → from cache (fast), read=Y → from disk (slow)

-- RED FLAGS:
-- Seq Scan on large table
-- rows estimate vs actual very different (stale stats → ANALYZE)
-- Sort Method: external merge → not enough work_mem

-- FIX STALE STATS:
ANALYZE invoicing_invoice;
```

### Index on Django project — real example

```python
# models.py — tera 60% latency fix ka basis
class Invoice(models.Model):
    status     = models.CharField(max_length=20, db_index=True)  # single
    company    = models.ForeignKey(Company, ...)  # FK auto-creates index
    created_at = models.DateTimeField(auto_now_add=True)
    amount     = models.DecimalField(...)

    class Meta:
        indexes = [
            # Composite: most common query pattern
            models.Index(
                fields=["company", "status"],
                name="idx_invoice_company_status"
            ),
            # Partial: only pending (subset index)
            models.Index(
                fields=["created_at"],
                condition=Q(status="pending"),
                name="idx_invoice_pending_date"
            ),
        ]

# BEFORE (slow):
# SELECT * FROM invoice WHERE company_id=5 AND status='pending'
# → Seq Scan, checked 50,000 rows

# AFTER (index_scan):
# → Index Scan using idx_invoice_company_status
# → checked 45 rows
# p95: 800ms → 320ms (60% improvement)
```

---

## TOPIC 3: TRANSACTIONS + ISOLATION LEVELS

### ACID properties

```
A = ATOMICITY    → All or nothing. Invoice create + SAP sync → both or neither.
C = CONSISTENCY  → DB always valid state. FK constraints, CHECK constraints.
I = ISOLATION    → Concurrent transactions don't interfere.
D = DURABILITY   → Committed data survives crash. WAL guarantee.
```

### Isolation levels — kya kya problems hote hain

```
PROBLEM 1: DIRTY READ
─────────────────────
Tx A writes amount=2000 (not committed)
Tx B reads amount=2000
Tx A ROLLBACK → amount never was 2000
Tx B used wrong data!

PROBLEM 2: NON-REPEATABLE READ
────────────────────────────────
Tx A reads amount=1000
Tx B updates amount=2000, commits
Tx A reads SAME row → amount=2000 (different!)

PROBLEM 3: PHANTOM READ
────────────────────────
Tx A: SELECT COUNT(*) FROM invoices WHERE status='pending' → 10
Tx B: INSERT new pending invoice, commits
Tx A: SELECT COUNT(*) WHERE status='pending' → 11 (phantom row!)

ISOLATION LEVELS (and what they prevent):
──────────────────────────────────────────────────────────
Level                  Dirty   Non-rep  Phantom  Notes
─────────────────────  ──────  ───────  ───────  ────────────────────
READ UNCOMMITTED       ❌No    ❌No     ❌No     Dirty reads allowed
READ COMMITTED         ✅Yes   ❌No     ❌No     PG DEFAULT
REPEATABLE READ        ✅Yes   ✅Yes    ✅Yes*   *PG prevents phantoms too
SERIALIZABLE           ✅Yes   ✅Yes    ✅Yes    Full isolation, slowest
```

### Transactions in Python — Django + psycopg2

```python
# ═══════════════════════════════════════════════════
# DJANGO TRANSACTIONS
# ═══════════════════════════════════════════════════
from django.db import transaction

# Method 1: atomic() decorator
@transaction.atomic
def create_invoice_and_sync(data):
    invoice = Invoice.objects.create(**data)
    sap_log = SAPLog.objects.create(invoice=invoice, status="pending")
    push_to_sap(invoice)   # if this fails → both rollback
    return invoice

# Method 2: atomic() context manager
def process_payment(invoice_id, amount):
    with transaction.atomic():
        invoice = Invoice.objects.select_for_update().get(id=invoice_id)
        # select_for_update() → ROW LOCK
        # No other transaction can update this row until we commit
        if invoice.status != "pending":
            raise ValueError("Not pending")
        invoice.amount_paid += amount
        invoice.status = "paid" if invoice.amount_paid >= invoice.amount else "partial"
        invoice.save()

# Method 3: SAVEPOINT (nested transaction)
with transaction.atomic():
    invoice = Invoice.objects.create(...)
    try:
        with transaction.atomic():   # savepoint
            risky_operation()
    except Exception:
        pass   # inner rolled back, outer continues

# ═══════════════════════════════════════════════════
# ISOLATION LEVEL CHANGE
# ═══════════════════════════════════════════════════
from django.db import connection

with transaction.atomic():
    connection.cursor().execute(
        "SET TRANSACTION ISOLATION LEVEL SERIALIZABLE"
    )
    # now serializable isolation
    critical_operation()

# ═══════════════════════════════════════════════════
# ON COMMIT HOOKS (signal after commit, not before)
# ═══════════════════════════════════════════════════
from django.db import transaction

def notify_after_commit(invoice):
    transaction.on_commit(
        lambda: send_notification.delay(invoice.id)
    )
    # Celery task triggers ONLY after DB commit confirmed
    # If transaction rolls back → task NOT triggered
    # Prevents: "task ran but DB not committed" race condition
```

### Deadlocks — kya hai aur kaise avoid karo

```
DEADLOCK SCENARIO:
──────────────────
Tx A: LOCK row 1 → wants row 2
Tx B: LOCK row 2 → wants row 1
Both wait forever → PostgreSQL detects + kills one

PREVENTION:
───────────
1. Always lock rows in SAME ORDER:
   # BAD: Tx A locks invoice, then company
   #      Tx B locks company, then invoice → deadlock
   # GOOD: Always lock invoice FIRST, then company

2. select_for_update(of=("self",))  # lock only specific tables
   with transaction.atomic():
       invoice = Invoice.objects.select_for_update().get(id=1)
       company = Company.objects.select_for_update().get(id=invoice.company_id)

3. NOWAIT: fail immediately instead of waiting
   Invoice.objects.select_for_update(nowait=True).get(id=1)
   # Raises DatabaseError if locked → retry logic lagao

4. SKIP LOCKED: skip locked rows (queue processing)
   Invoice.objects.select_for_update(skip_locked=True).filter(status="pending")[:10]
   # Multiple workers pe — each gets different rows!
```

---

## TOPIC 4: QUERY OPTIMIZATION (Tera 60% Latency Fix)

### Step-by-step optimization process

```
STEP 1: IDENTIFY slow queries
───────────────────────────────────────────────────
# PostgreSQL slow query log (postgresql.conf):
log_min_duration_statement = 200   # log queries > 200ms

# pg_stat_statements extension:
SELECT query, calls, mean_exec_time, total_exec_time
FROM pg_stat_statements
ORDER BY mean_exec_time DESC
LIMIT 10;

STEP 2: EXPLAIN ANALYZE the slow query
───────────────────────────────────────────────────
EXPLAIN (ANALYZE, BUFFERS) <your slow query>;
Look for: Seq Scan, Sort, Hash, high actual rows

STEP 3: FIX
───────────────────────────────────────────────────
Fix 1: Add missing index
Fix 2: Rewrite query (eliminate subquery, use CTE)
Fix 3: select_related / prefetch_related (N+1)
Fix 4: Increase work_mem (sort spills to disk)
Fix 5: ANALYZE table (stale statistics)
Fix 6: Denormalize if needed (read-heavy)

STEP 4: VERIFY
───────────────────────────────────────────────────
Before: p95 latency = 800ms (log se)
After:  p95 latency = 320ms (60% reduction)
```

### Common query patterns — optimized versions

```sql
-- ═══════════════════════════════════════════════════
-- PAGINATION (efficient cursor-based)
-- ═══════════════════════════════════════════════════

-- BAD: OFFSET (gets slower as offset grows)
SELECT * FROM invoices ORDER BY id LIMIT 20 OFFSET 10000;
-- PostgreSQL reads 10020 rows, discards 10000 → slow!

-- GOOD: Cursor pagination (constant time)
SELECT * FROM invoices
WHERE id > :last_seen_id       -- last page ka last id
ORDER BY id
LIMIT 20;
-- Direct index seek → always fast regardless of page

-- ═══════════════════════════════════════════════════
-- UPSERT (insert or update atomically)
-- ═══════════════════════════════════════════════════
INSERT INTO invoice_sync_log (invoice_id, sap_status, synced_at)
VALUES (123, 'success', NOW())
ON CONFLICT (invoice_id)       -- unique constraint pe conflict
DO UPDATE SET
    sap_status = EXCLUDED.sap_status,
    synced_at  = EXCLUDED.synced_at;
-- Atomic — no race condition between check + insert

-- ═══════════════════════════════════════════════════
-- WINDOW FUNCTIONS (analytics without subquery)
-- ═══════════════════════════════════════════════════
SELECT
    invoice_number,
    amount,
    company_id,
    SUM(amount) OVER (PARTITION BY company_id) AS company_total,
    RANK() OVER (PARTITION BY company_id ORDER BY amount DESC) AS rank_in_company,
    LAG(amount) OVER (ORDER BY created_at) AS prev_invoice_amount
FROM invoicing_invoice
WHERE status = 'paid';

-- ═══════════════════════════════════════════════════
-- CTE (Common Table Expression — readable complex queries)
-- ═══════════════════════════════════════════════════
WITH pending_invoices AS (
    SELECT id, amount, company_id
    FROM invoicing_invoice
    WHERE status = 'pending'
      AND created_at < NOW() - INTERVAL '30 days'
),
company_totals AS (
    SELECT company_id, SUM(amount) AS overdue_amount
    FROM pending_invoices
    GROUP BY company_id
)
SELECT c.name, ct.overdue_amount
FROM company_totals ct
JOIN companies c ON ct.company_id = c.id
WHERE ct.overdue_amount > 100000
ORDER BY ct.overdue_amount DESC;

-- ═══════════════════════════════════════════════════
-- JSONB queries (PostgreSQL strength)
-- ═══════════════════════════════════════════════════
-- Store SAP response as JSONB
CREATE TABLE sap_responses (
    id SERIAL PRIMARY KEY,
    invoice_id INT,
    response JSONB,
    created_at TIMESTAMP
);

-- Query JSONB
SELECT id, response->>'status' AS sap_status
FROM sap_responses
WHERE response @> '{"error_code": null}'    -- containment
  AND response->>'status' = 'success';

-- GIN index on JSONB
CREATE INDEX idx_sap_response_gin ON sap_responses USING GIN (response);
```

---

## TOPIC 5: MYSQL

### Definition + when to use

```
MySQL = Oldest, most widely deployed RDBMS.
LAMP stack ka "M" — Linux, Apache, MySQL, PHP.
Web hosting, WordPress, simple CRUD apps mein dominant.
```

### PostgreSQL vs MySQL — honest comparison

```
FEATURE                     POSTGRESQL            MYSQL
──────────────────────      ─────────────         ────────────────────
ACID compliance             ✅ Full               ✅ Full (InnoDB)
JSON support                ✅ JSONB (better)     ⚠️ JSON (limited ops)
Full-text search            ✅ Built-in           ✅ Built-in
Indexing                    ✅ B-tree/GIN/GiST    ✅ B-tree (limited)
Window functions            ✅ Full               ✅ MySQL 8+
CTEs                        ✅ Full               ✅ MySQL 8+
Partitioning                ✅ Declarative        ⚠️ More complex
Extensions                  ✅ pgvector, PostGIS  ❌ Limited
MVCC                        ✅ Row-level          ✅ Row-level (InnoDB)
Replication                 ✅ Streaming WAL      ✅ Binlog
Performance (read)          ✅ Great              ✅ Slightly faster
                                                  for simple queries
Performance (complex)       ✅ Better             ⚠️ Optimizer weaker
DEFAULT                     ⭐ My recommendation  Legacy projects
```

### MySQL-specific concepts

```sql
-- ═══════════════════════════════════════════════════
-- STORAGE ENGINES
-- ═══════════════════════════════════════════════════
-- InnoDB (default, always use this):
-- ACID compliant, row-level locking, FK support, MVCC
CREATE TABLE invoices (...) ENGINE=InnoDB;

-- MyISAM (legacy, avoid):
-- No transactions, table-level locks, faster reads
-- NOT crash-safe

-- ═══════════════════════════════════════════════════
-- AUTO_INCREMENT vs PostgreSQL SERIAL
-- ═══════════════════════════════════════════════════
-- MySQL:
CREATE TABLE t (id INT AUTO_INCREMENT PRIMARY KEY, ...);
-- PostgreSQL:
CREATE TABLE t (id SERIAL PRIMARY KEY, ...);
-- Or modern:
CREATE TABLE t (id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY, ...);

-- ═══════════════════════════════════════════════════
-- EXPLAIN FORMAT
-- ═══════════════════════════════════════════════════
EXPLAIN FORMAT=JSON SELECT * FROM invoices WHERE status='pending';
-- type column: ALL=full scan, ref=index, const=single row
-- key: index used
-- rows: estimated rows scanned
-- Extra: "Using index" = covering index

-- ═══════════════════════════════════════════════════
-- SPECIFIC TO YES PLATFORM (tera project)
-- ═══════════════════════════════════════════════════
-- Certificate table (1000+/month, sub-200ms p95)
CREATE TABLE certificates (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    cert_number VARCHAR(50) UNIQUE NOT NULL,
    holder_name VARCHAR(255) NOT NULL,
    qr_code     VARCHAR(500),
    status      ENUM('active', 'revoked', 'expired') DEFAULT 'active',
    issued_at   DATETIME DEFAULT CURRENT_TIMESTAMP,
    expires_at  DATETIME,
    INDEX idx_cert_status_issued (status, issued_at),  -- composite
    INDEX idx_cert_expires (expires_at)                -- expiry queries
) ENGINE=InnoDB;
```

### Interview Answer

> **Q: "PostgreSQL vs MySQL — kaunsa prefer karte ho aur kyun?"**
>
> *"PostgreSQL prefer karta hoon new projects mein — mainly 3 reasons.
> First, JSONB support — Youngman Beta mein SAP HANA response JSONB mein
> store kiya, GIN index pe fast query kar sakte hain. MySQL ka JSON
> limited hai. Second, extensions — pgvector Niroskos mein use kiya
> semantic search ke liye, MySQL pe yeh possible nahi tha. Third, query
> optimizer — complex JOINs aur window functions PostgreSQL better handle
> karta hai. MySQL use kiya YES Platform mein — already legacy stack tha,
> migration cost nahi tha worth karna. New project? PostgreSQL."*

---

## TOPIC 6: REDIS — ARCHITECTURE + DATA STRUCTURES

### Definition
```
Redis = Remote Dictionary Server.
In-memory key-value store.
Disk persistence optional hai.
Single-threaded (atomicity guarantee), event-loop based.
10x faster than PostgreSQL for appropriate use cases.
```

### Simple Example (analogy)
```
PostgreSQL = Library (permanent, organized, searchable)
Redis      = Whiteboard (fast, temporary, in front of you)

Use whiteboard for:
- Things you need RIGHT NOW (session data, cache)
- Things that change fast (real-time counters, leaderboards)
- Temporary notes (rate limiting windows, OTP codes)
- Pub/sub (shout something, who's listening hears it)

Never use whiteboard for:
- Permanent records (invoices, user data → use PostgreSQL)
- Data larger than whiteboard (Redis = RAM size limit)
```

### Redis Architecture

```
REDIS ARCHITECTURE
────────────────────────────────────────────────────────

CLIENT (Python / redis-py)
    │  TCP connection (port 6379)
    │  RESP protocol (Redis Serialization Protocol)
    ▼
┌─────────────────────────────────────────────────────┐
│                  REDIS SERVER                        │
│                                                      │
│  SINGLE THREAD (event loop)                          │
│  ┌──────────────────────────────────────────────┐   │
│  │  Event Loop                                  │   │
│  │  ├── Accept connections                      │   │
│  │  ├── Read commands                           │   │
│  │  ├── Execute command (in-memory)             │   │
│  │  └── Write response                          │   │
│  └──────────────────────────────────────────────┘   │
│                                                      │
│  IN-MEMORY DATA STORE                               │
│  ┌──────────────────────────────────────────────┐   │
│  │  Key-Value pairs                             │   │
│  │  "session:abc" → {user_id: 1, ...}           │   │
│  │  "rate:user:1" → 45 (counter)                │   │
│  │  "cache:inv:123" → "{...json...}"            │   │
│  └──────────────────────────────────────────────┘   │
│                                                      │
│  PERSISTENCE (optional):                            │
│  ├── RDB (snapshot): every N seconds               │
│  └── AOF (append-only file): every command logged  │
└─────────────────────────────────────────────────────┘
```

### 6 Data Structures — kab kya

```
DATA STRUCTURE     COMMANDS              USE CASE
────────────────   ─────────────────     ────────────────────────────
STRING             GET, SET, INCR        Cache, sessions, counters,
                   SETEX, SETNX          OTP codes, feature flags

LIST               LPUSH, RPUSH          Task queue (Celery broker!)
                   LPOP, BRPOP           Notification feed
                   LRANGE                Activity log (latest N)

HASH               HSET, HGET            User session (multiple fields)
                   HMSET, HGETALL        Object cache (no serialization)
                   HINCRBY               Shopping cart

SET                SADD, SMEMBERS        Unique visitors, tags
                   SINTER, SUNION        Common friends
                   SISMEMBER             Membership check (O(1))

SORTED SET         ZADD, ZRANGE          Leaderboard, priority queue
(ZSET)             ZRANGEBYSCORE         Rate limiting (sliding window)
                   ZRANK                 Scheduled tasks (score=timestamp)

STREAM             XADD, XREAD           Event log, message queue
                   XGROUP                Consumer groups (like Kafka lite)
```

### Code — all 6 data structures

```python
import redis
from datetime import timedelta

r = redis.Redis(host="localhost", port=6379, db=0, decode_responses=True)

# ═══════════════════════════════════════════════════
# 1. STRING — Cache + OTP
# ═══════════════════════════════════════════════════
# Simple cache
r.setex("cache:invoice:123",
        timedelta(minutes=5),
        json.dumps(invoice_data))

cached = r.get("cache:invoice:123")
if cached:
    return json.loads(cached)

# OTP (one-time password)
otp = "847291"
r.setex(f"otp:{phone}", timedelta(minutes=10), otp)

def verify_otp(phone, entered_otp):
    stored = r.get(f"otp:{phone}")
    if stored and stored == entered_otp:
        r.delete(f"otp:{phone}")   # single use!
        return True
    return False

# Counter (atomic)
r.incr("stats:api_calls_today")        # atomic increment
r.incrby("stats:tokens_used", 1500)   # increment by N

# ═══════════════════════════════════════════════════
# 2. LIST — Task Queue (Celery uses this!)
# ═══════════════════════════════════════════════════
# Producer
r.lpush("queue:email", json.dumps({"to": "user@example.com", "subject": "Invoice"}))
r.lpush("queue:email", json.dumps({"to": "user2@example.com", "subject": "Payment"}))

# Consumer (blocking pop — waits for items)
while True:
    _, task = r.brpop("queue:email", timeout=5)  # wait 5s
    if task:
        process_email_task(json.loads(task))

# Recent activity log (capped list)
r.lpush("activity:user:1", json.dumps({"action": "login", "time": "..."}))
r.ltrim("activity:user:1", 0, 99)   # keep only last 100
activities = r.lrange("activity:user:1", 0, -1)

# ═══════════════════════════════════════════════════
# 3. HASH — Session Storage
# ═══════════════════════════════════════════════════
session_id = "sess_abc123"
r.hset(f"session:{session_id}", mapping={
    "user_id": "42",
    "email": "ashish@example.com",
    "role": "admin",
    "login_time": "2026-08-15T10:30:00"
})
r.expire(f"session:{session_id}", 3600)   # 1 hour

# Read specific field
user_id = r.hget(f"session:{session_id}", "user_id")

# Read all fields
session_data = r.hgetall(f"session:{session_id}")

# ═══════════════════════════════════════════════════
# 4. SET — Unique Tracking
# ═══════════════════════════════════════════════════
# Daily unique visitors (no duplicates)
today = datetime.now().strftime("%Y-%m-%d")
r.sadd(f"visitors:{today}", user_id)
unique_count = r.scard(f"visitors:{today}")

# Feature flags (which users have access)
r.sadd("feature:new_dashboard", "user:42", "user:100", "user:200")
has_access = r.sismember("feature:new_dashboard", f"user:{user_id}")

# ═══════════════════════════════════════════════════
# 5. SORTED SET — Rate Limiting (sliding window)
# ═══════════════════════════════════════════════════
import time

def is_rate_limited(user_id: str, limit: int = 100, window_seconds: int = 3600) -> bool:
    key = f"rate:{user_id}"
    now = time.time()
    window_start = now - window_seconds

    pipe = r.pipeline()
    pipe.zremrangebyscore(key, 0, window_start)   # remove old entries
    pipe.zadd(key, {str(now): now})               # add current request
    pipe.zcard(key)                               # count in window
    pipe.expire(key, window_seconds)
    results = pipe.execute()

    request_count = results[2]
    return request_count > limit

# Leaderboard
r.zadd("leaderboard:weekly", {"user:42": 1500, "user:100": 2300, "user:200": 800})
top_3 = r.zrevrange("leaderboard:weekly", 0, 2, withscores=True)

# ═══════════════════════════════════════════════════
# 6. PIPELINE — batch commands (reduce round trips)
# ═══════════════════════════════════════════════════
# WITHOUT pipeline: 100 round trips
for i in range(100):
    r.set(f"key:{i}", i)

# WITH pipeline: 1 round trip
pipe = r.pipeline()
for i in range(100):
    pipe.set(f"key:{i}", i)
pipe.execute()   # sends all at once

# ═══════════════════════════════════════════════════
# REDIS TRANSACTIONS (MULTI/EXEC)
# ═══════════════════════════════════════════════════
with r.pipeline() as pipe:
    while True:
        try:
            pipe.watch("balance:user:42")   # watch for changes
            balance = int(pipe.get("balance:user:42") or 0)
            if balance < 100:
                raise ValueError("Insufficient balance")
            pipe.multi()                    # start transaction
            pipe.decrby("balance:user:42", 100)
            pipe.incrby("balance:merchant:1", 100)
            pipe.execute()                  # atomic execute
            break
        except redis.WatchError:
            continue   # someone changed balance → retry
```

---

## TOPIC 7: REDIS USE CASES — Real Production Patterns

### Pattern 1: Caching (tera SAP HANA token)

```
CACHE-ASIDE PATTERN:
────────────────────────────────────────────────────────

APP                    REDIS                 DATABASE
 │                       │                      │
 │──── GET cache:inv:1 ──►│                      │
 │◄─── MISS ─────────────│                      │
 │                       │                      │
 │──────────────────────────────── SELECT ──────►│
 │◄──────────────────────────────── data ────────│
 │                       │                      │
 │──── SET cache:inv:1 ──►│                      │
 │     (TTL: 5 min)       │                      │
 │◄─── OK ───────────────│                      │
 │                       │                      │
 │ (next request)        │                      │
 │──── GET cache:inv:1 ──►│                      │
 │◄─── HIT: data ────────│  (no DB call!)       │

TERA REAL USE (Youngman Beta):
SAP HANA auth token cache:
token = cache.get("sap_token")
if not token:
    token = sap_auth()   # expensive HTTP call
    cache.set("sap_token", token, timeout=3500)  # token valid 3600s
```

### Pattern 2: Celery Task Queue (Niroskos mein)

```
CELERY + REDIS ARCHITECTURE:
────────────────────────────────────────────────────────

DJANGO APP (producer)              CELERY WORKER (consumer)
      │                                   │
      │  .delay()                         │
      │──────────────────►  REDIS         │
      │                   (LIST queue)    │
      │                        │          │
      │                        │──────────►
      │                        │  BRPOP (blocking)
      │                        │          │
      │                        │          │ Execute task
      │                        │          │
      │                        │◄─────────│ RESULT
      │                   (RESULT backend)│

# settings.py
CELERY_BROKER_URL = "redis://localhost:6379/0"
CELERY_RESULT_BACKEND = "redis://localhost:6379/1"

# Different queues for priority
CELERY_TASK_ROUTES = {
    "send_invoice_email": {"queue": "high_priority"},
    "generate_report":    {"queue": "low_priority"},
}
# celery -A config worker -Q high_priority --concurrency=4
# celery -A config worker -Q low_priority --concurrency=2
```

### Pattern 3: Rate Limiting (Toofan AI gateway)

```python
# SLIDING WINDOW RATE LIMITER (Toofan mein)
class RateLimiter:
    def __init__(self, redis_client, limit: int, window: int):
        self.r = redis_client
        self.limit = limit        # max requests
        self.window = window      # window in seconds

    async def is_allowed(self, key: str) -> tuple[bool, dict]:
        now = time.time()
        window_start = now - self.window

        pipe = self.r.pipeline()
        pipe.zremrangebyscore(key, 0, window_start)
        pipe.zadd(key, {str(now): now})
        pipe.zcard(key)
        pipe.expire(key, self.window)
        _, _, count, _ = pipe.execute()

        remaining = max(0, self.limit - count)
        reset_time = int(now) + self.window

        return count <= self.limit, {
            "limit": self.limit,
            "remaining": remaining,
            "reset": reset_time,
        }

# FastAPI middleware
limiter = RateLimiter(redis_client, limit=100, window=3600)

@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    key = f"rate:{request.client.host}"
    allowed, info = await limiter.is_allowed(key)
    if not allowed:
        return JSONResponse(
            status_code=429,
            content={"error": "Rate limit exceeded"},
            headers={
                "X-RateLimit-Limit": str(info["limit"]),
                "X-RateLimit-Remaining": "0",
                "Retry-After": str(info["reset"]),
            }
        )
    response = await call_next(request)
    response.headers["X-RateLimit-Remaining"] = str(info["remaining"])
    return response
```

### Pattern 4: Pub/Sub (real-time notifications)

```python
# PUBLISHER (Django signal ya Celery task)
def notify_invoice_paid(invoice_id):
    r.publish(
        f"channel:company:{invoice.company_id}",
        json.dumps({"event": "invoice_paid", "invoice_id": invoice_id})
    )

# SUBSCRIBER (separate process ya WebSocket handler)
pubsub = r.pubsub()
pubsub.subscribe(f"channel:company:{company_id}")

for message in pubsub.listen():
    if message["type"] == "message":
        data = json.loads(message["data"])
        # Send to WebSocket clients
        await websocket_manager.broadcast(company_id, data)

# PATTERN subscribe (wildcard)
pubsub.psubscribe("channel:company:*")   # all companies
```

### Pattern 5: Distributed Lock (idempotent operations)

```python
# REDLOCK — distributed lock (tera SAP HANA idempotency ka basis)
import uuid

def acquire_lock(key: str, timeout: int = 30) -> str | None:
    """Try to acquire distributed lock. Returns lock_id or None."""
    lock_id = str(uuid.uuid4())
    acquired = r.set(
        f"lock:{key}",
        lock_id,
        nx=True,      # SET only if Not eXists
        ex=timeout    # expire after N seconds (safety)
    )
    return lock_id if acquired else None

def release_lock(key: str, lock_id: str) -> bool:
    """Release lock only if we own it (compare-and-delete)."""
    lua_script = """
    if redis.call("get", KEYS[1]) == ARGV[1] then
        return redis.call("del", KEYS[1])
    else
        return 0
    end
    """
    return r.eval(lua_script, 1, f"lock:{key}", lock_id)

# USAGE (SAP HANA invoice push — idempotent):
def push_invoice_to_sap(invoice_id: int):
    lock_key = f"sap_sync:{invoice_id}"
    lock_id = acquire_lock(lock_key, timeout=60)
    if not lock_id:
        logger.warning(f"Invoice {invoice_id} already being synced")
        return   # another worker is processing

    try:
        sap_client.push_invoice(invoice_id)
    finally:
        release_lock(lock_key, lock_id)
```

---

## TOPIC 8: INTERVIEW Q&A — 20 Questions

---

**Q1. Tune 60% latency kaise reduce ki — exact steps?**

```
ANSWER (STAR format):

SITUATION:
Invoice list page pe p95 latency 800ms thi.
Django Debug Toolbar mein dekha: 101 queries per request.

ROOT CAUSE:
Invoice.objects.filter(status="pending")
→ 100 invoices return hue
→ for invoice in invoices: invoice.company.name
→ 100 extra queries (N+1 problem!)

ACTION (3 changes):
1. select_related("company", "created_by") add kiya
   → 101 queries → 1 JOIN query
   → 800ms → 520ms

2. Composite index add kiya (company_id, status)
   → Django Meta.indexes
   → Seq Scan → Index Scan
   → 520ms → 380ms

3. Partial index for pending status
   → Only pending rows indexed → smaller, faster
   → 380ms → 320ms

RESULT:
p95: 800ms → 320ms (60% reduction)
Verified via Django Debug Toolbar + pg_stat_statements

LESSON:
Always check query count first (Debug Toolbar).
Then EXPLAIN ANALYZE.
Then index design.
Measure before and after.
```

---

**Q2. ACID kya hai — real example se?**

```
ATOMIC:
Invoice create + SAP sync log → dono hote hain ya dono nahi.
Agar SAP fail hoga → invoice bhi rollback. Half-state nahi.

CONSISTENT:
Invoice amount negative nahi ho sakta (CHECK constraint).
FK constraint: invoice ke company_id wala company exist karna chahiye.

ISOLATED:
Tx A invoice amount update kar raha hai.
Tx B invoice padh raha hai.
READ COMMITTED (default): Tx B committed value padh raha hai.
Dirty read nahi hoga.

DURABLE:
Invoice paid mark hua → WAL log pe likh gaya.
Server crash ho jaaye → postgres restart pe recover ho jaayega.
"COMMIT;" ka matlab permanently saved.
```

---

**Q3. Redis aur PostgreSQL mein kab kya choose karte ho?**

```
POSTGRESQL:
✅ Permanent data (invoices, users, orders)
✅ Complex queries (JOINs, aggregations, window functions)
✅ ACID transactions (payment processing)
✅ Referential integrity (FK constraints)
✅ Data > RAM (disk-based)

REDIS:
✅ Speed critical (sub-millisecond) → cache, sessions
✅ Temporary data (OTP: 10 min, rate limit window: 1 hr)
✅ Counter/leaderboard (INCR, ZADD — atomic)
✅ Task queue (Celery broker)
✅ Pub/Sub (real-time notifications)
✅ Data fits in RAM

RULE: PostgreSQL = source of truth. Redis = performance layer on top.
Never store data ONLY in Redis that you can't afford to lose
(unless persistence configured).
```

---

**Q4. Redis persistence kaise configure kiya production mein?**

```
TWO MECHANISMS:
1. RDB (Redis Database Backup):
   Periodic snapshot to disk.
   save 900 1     → if 1 change in 900 sec, save
   save 300 10    → if 10 changes in 300 sec, save
   FAST restore, but data loss possible between snapshots.

2. AOF (Append Only File):
   Every write command logged to file.
   appendfsync everysec  → flush every second (recommended)
   appendfsync always    → flush every write (slowest, safest)
   Slower, but near-zero data loss.

MY APPROACH (Niroskos/Toofan):
- Cache data: RDB only (losing cache = minor, DB is source of truth)
- Session data: AOF (losing sessions = users logged out, bad UX)
- Celery queue: AOF + manual backup (losing tasks = missed processing)

redis.conf:
save 900 1
save 300 10
appendonly yes
appendfsync everysec
```

---

**Q5. PostgreSQL MVCC aur locks ka relation?**

```
MVCC = Multi-Version Concurrency Control.
Readers don't block writers, writers don't block readers.

HOW:
Each row has xmin (created by) and xmax (deleted by).
Reader sees snapshot at transaction start time.
Writer creates new row version.
No read-write lock needed.

WHEN LOCKS NEEDED (MVCC nahi enough):
SELECT FOR UPDATE: explicit row lock
  Invoice.objects.select_for_update().get(id=1)
  → Prevents concurrent updates to same invoice

Table-level lock:
  LOCK TABLE invoices IN SHARE MODE;
  → Rare, usually index + row lock enough

DEADLOCK:
If Tx A locks row 1, wants row 2
And Tx B locks row 2, wants row 1
PostgreSQL detects → kills one transaction
Prevention: consistent lock order in application code.
```

---

**Q6. SAP HANA sync mein idempotency kaise ensure kiya?**

```
PROBLEM:
Invoice push to SAP HANA → network timeout after send.
Retry kiya → duplicate invoice SAP mein?

SOLUTION (3-layer idempotency):

Layer 1: Idempotency key
  POST /sap/invoices
  Idempotency-Key: invoice-{invoice_id}-{hash}
  SAP returns same response for duplicate key (if already processed)

Layer 2: Status check before push
  if SAPLog.objects.filter(invoice=invoice, status="success").exists():
      return  # already synced

Layer 3: Database upsert (atomic)
  INSERT INTO sap_sync_log (invoice_id, status)
  ON CONFLICT (invoice_id) DO UPDATE SET status=EXCLUDED.status

Layer 4: Distributed lock (Redis)
  acquire_lock(f"sap_sync:{invoice_id}")
  → Only one worker processes same invoice at once

RESULT: 99% success on 10,000+ invoices/month with retries.
```

---

**Q7. Index kab nahi lagana chahiye?**

```
DON'T INDEX:
❌ Small tables (<1000 rows) → Seq Scan faster than index lookup
❌ Low-cardinality columns → status=pending/paid (only 4 values)
   Better: partial index (WHERE status='pending')
❌ Columns rarely used in WHERE/JOIN/ORDER BY
❌ Tables with very high write rate → every INSERT/UPDATE/DELETE
   updates ALL indexes → write slowdown

EXTRA COST OF INDEX:
Every INSERT → update all indexes on that table
Every UPDATE → update indexes for changed columns
Every DELETE → update all indexes
Extra storage space

CHECK UNUSED INDEXES:
SELECT indexname, idx_scan
FROM pg_stat_user_indexes
WHERE idx_scan = 0        -- never used!
  AND indisunique = FALSE -- not unique constraint
ORDER BY pg_relation_size(indexrelid) DESC;

DROP unused indexes → faster writes!
```

---

**Q8. Redis cache invalidation strategy kya use karte ho?**

```
PROBLEM: Cache stale ho gaya (DB updated but cache old data hai)

STRATEGY 1: TTL (Time-To-Live) — simplest
r.setex("cache:invoice:123", 300, data)  # expires in 5 min
Tradeoff: 5 min stale data acceptable karo

STRATEGY 2: Cache-aside with explicit invalidation
On update:
def update_invoice(id, data):
    Invoice.objects.filter(id=id).update(**data)
    r.delete(f"cache:invoice:{id}")   # immediately invalid
On read:
    cached = r.get(f"cache:invoice:{id}")
    if not cached:
        data = Invoice.objects.get(id=id)
        r.setex(f"cache:invoice:{id}", 300, json.dumps(data))

STRATEGY 3: Write-through
On every write, update cache + DB together.

WHICH WHEN:
Read-heavy, slightly stale OK → TTL
Strict consistency needed → explicit invalidation
High write rate → skip cache for that entity

MY APPROACH (Niroskos):
Product listings: 5-min TTL (changes rarely)
Booking details: explicit invalidation on update
User sessions: write-through (always fresh)
```

---

**Q9. PostgreSQL connection pooling kaise kiya?**

```
PROBLEM:
Django per-request DB connection → 100 requests = 100 connections
PostgreSQL max_connections = 100 (default)
→ Connection refused errors at scale!

SOLUTION: PgBouncer (connection pooler)

WITHOUT POOLER:
Django App → 100 connections → PostgreSQL
                              (max 100, each costs ~5MB RAM)

WITH PGBOUNCER:
Django App → 100 connections → PgBouncer → 10 connections → PostgreSQL
                               (pool: reuse connections efficiently)

PgBouncer MODES:
Session pooling:    1 connection per session (least savings)
Transaction pooling: 1 connection per transaction (RECOMMENDED)
Statement pooling:   1 connection per statement (risky)

DJANGO SETTINGS:
DATABASES = {
    "default": {
        "HOST": "pgbouncer_host",  # point to pgbouncer
        "PORT": 6432,               # pgbouncer port
        "CONN_MAX_AGE": 0,          # disable Django's own pooling
                                    # pgbouncer handles it
    }
}

RESULT: 100 app connections → 10 actual PostgreSQL connections
        App scales without PostgreSQL overload.
```

---

**Q10. Redis Celery setup mein kya gotchas hain?**

```
GOTCHA 1: Task acknowledgment
Default: task acked when received (not when done)
If worker crashes mid-task → task lost!
FIX:
CELERY_TASK_ACKS_LATE = True          # ack after completion
CELERY_WORKER_PREFETCH_MULTIPLIER = 1  # one task at a time

GOTCHA 2: Result backend memory
CELERY_RESULT_BACKEND = "redis://..."
Results stored in Redis indefinitely → memory leak!
FIX:
CELERY_RESULT_EXPIRES = 3600   # expire results after 1 hour

GOTCHA 3: Connection pool exhaustion
Many Celery workers → each needs Redis connections
FIX:
CELERY_BROKER_POOL_LIMIT = 10   # per-worker connection pool

GOTCHA 4: Task retries with Redis
If Redis goes down → all queued tasks lost (RDB snapshot gap)
FIX: AOF persistence + sentinel/cluster for HA

MY SETUP (Niroskos):
CELERY_BROKER_URL = "redis://localhost:6379/0"
CELERY_RESULT_BACKEND = "redis://localhost:6379/1"
CELERY_TASK_ACKS_LATE = True
CELERY_WORKER_PREFETCH_MULTIPLIER = 1
CELERY_RESULT_EXPIRES = 3600
```

---

**Q11. PostgreSQL partition kab use karte ho?**

```
PARTITIONING = Large table ko smaller pieces mein split karo.

WHEN:
- Table > 100M rows → queries slow even with indexes
- Old data archive karna hai (drop old partition → instant)
- Data naturally time-based (logs, events, transactions)

TYPES:
Range: date range (invoices by month)
List:  discrete values (orders by region)
Hash:  hash of key (even distribution)

EXAMPLE (Youngman Beta invoices):
CREATE TABLE invoicing_invoice (
    id         BIGSERIAL,
    created_at TIMESTAMP NOT NULL,
    amount     DECIMAL,
    status     VARCHAR(20)
) PARTITION BY RANGE (created_at);

-- Monthly partitions
CREATE TABLE invoicing_invoice_2026_01
    PARTITION OF invoicing_invoice
    FOR VALUES FROM ('2026-01-01') TO ('2026-02-01');

CREATE TABLE invoicing_invoice_2026_02
    PARTITION OF invoicing_invoice
    FOR VALUES FROM ('2026-02-01') TO ('2026-03-01');

-- Query: WHERE created_at = '2026-01-15'
-- → Only scans 2026_01 partition (partition pruning)

DROP TABLE invoicing_invoice_2024_01;  -- instant! old data gone
```

---

**Q12. JSONB vs JSON in PostgreSQL?**

```
JSON:
- Stores exact text (whitespace, key order preserved)
- Parsed on every query → slower
- Size: slightly larger

JSONB (Binary JSON):
- Stored in decomposed binary format
- Parsed once on insert → faster queries
- Supports GIN index → fast key/value search
- Key order NOT preserved, duplicate keys removed
- Size: similar or smaller

WHEN:
Always use JSONB unless exact text preservation needed.

MERI USE CASE (Youngman Beta):
SAP HANA response JSONB mein store kiya:
response JSONB default '{}'

-- GIN index for fast queries:
CREATE INDEX idx_sap_resp ON sap_logs USING GIN (response);

-- Query:
SELECT * FROM sap_logs WHERE response @> '{"status": "error"}';
-- @ = "contains" operator → uses GIN index → fast!
```

---

**Q13. Redis Sorted Set se rate limiting — sliding window?**

```
FIXED WINDOW (simple, less accurate):
Hour 1 (12:00-1:00): 100 requests OK
Hour 2 (1:00-2:00):  100 requests OK
Problem: 100 requests at 12:59 + 100 at 1:01 = 200 in 2 min!

SLIDING WINDOW (accurate):
Always look back exactly 60 min from NOW.
Never allows burst at boundary.

IMPLEMENTATION (Sorted Set):
Key: "rate:user:42"
Score: timestamp
Value: unique request ID

ZADD rate:user:42 1691234567.123 "req_uuid_1"
ZADD rate:user:42 1691234567.456 "req_uuid_2"

On each request:
1. Remove old entries: ZREMRANGEBYSCORE key 0 (now - window)
2. Add current: ZADD key now uuid
3. Count: ZCARD key
4. If count > limit → rate limited

ATOMIC via pipeline:
pipe.zremrangebyscore(key, 0, now - window)
pipe.zadd(key, {uuid: now})
pipe.zcard(key)
pipe.expire(key, window)
results = pipe.execute()
```

---

**Q14. Database migration strategy — zero downtime?**

```
PROBLEM: Production pe running app ke saath migration karna.
Table lock → app hangs → downtime!

SAFE MIGRATION STEPS:

Step 1: Add nullable column (no lock)
ALTER TABLE invoices ADD COLUMN gst_number VARCHAR(20);
-- No data to populate → instant, no lock

Step 2: Backfill in batches (background)
UPDATE invoices SET gst_number = compute_gst(id)
WHERE id BETWEEN 1 AND 1000;   -- small batches
-- Run during off-hours, app still running

Step 3: Add NOT NULL constraint (check first)
ALTER TABLE invoices ALTER COLUMN gst_number SET NOT NULL;
-- Only after all rows filled

Step 4: Add index (CONCURRENT)
CREATE INDEX CONCURRENTLY idx_gst_number ON invoices (gst_number);

NEVER:
❌ ALTER TABLE ADD COLUMN NOT NULL without default (full table rewrite!)
❌ Regular CREATE INDEX (table lock!)
❌ Rename column (Django sees delete + add → data loss!)

TOOLS:
django-pg-zero-downtime → safe migrations
squashmigrations → merge many migrations
```

---

**Q15. PostgreSQL full-text search kab use karo vs Elasticsearch?**

```
POSTGRESQL FTS:
✅ Data already in PostgreSQL → no extra service
✅ Transactional consistency (search results = DB state)
✅ Simpler ops (no extra service to manage)
⚠️ Performance: OK for < 1M docs, slower after
❌ No fuzzy search, synonym handling limited
❌ No relevance tuning

ELASTICSEARCH:
✅ Optimized for full-text search at any scale
✅ Fuzzy matching, synonyms, analyzers
✅ Distributed (horizontal scale)
✅ Real-time relevance tuning
❌ Extra service to manage
❌ Eventual consistency with primary DB

MY APPROACH:
Niroskos: PostgreSQL FTS for tour package search
  to_tsvector('english', title || ' ' || description)
  Good enough for 10,000 packages, no extra service

YES Platform certificates: PostgreSQL FTS
  Quick cert number + name search, small dataset

Hypothetical: 10M+ products, complex relevance → Elasticsearch
(also used in Youngman Beta for product catalog,
 but stayed on PostgreSQL for simplicity given dataset size)
```

---

## QUICK RECALL CARD

```
╔════════════════════════════════════════════════════════════════╗
║         POSTGRESQL + MYSQL + REDIS RECALL CARD                ║
╠════════════════════════════════════════════════════════════════╣
║                                                                ║
║  POSTGRESQL                                                    ║
║  MVCC    = Multi-version concurrency (no read-write locks)    ║
║  VACUUM  = Dead tuple cleanup (auto runs in background)        ║
║  WAL     = Write-Ahead Log (crash recovery)                   ║
║  N+1 fix = select_related (FK) / prefetch_related (M2M)       ║
║  Indexes = B-tree(default) / GIN(JSONB,FTS) / GiST(geo)      ║
║  CONCURRENT = CREATE INDEX CONCURRENTLY (no lock!)            ║
║  EXPLAIN = EXPLAIN (ANALYZE, BUFFERS) <query>                 ║
║  Isolation= READ COMMITTED (default PG)                       ║
║  Upsert  = INSERT ... ON CONFLICT DO UPDATE                   ║
║  JSONB   = Binary JSON, GIN indexed, fast queries             ║
║  FTS     = to_tsvector + GIN index                            ║
║                                                                ║
║  60% LATENCY FIX:                                             ║
║  N+1 → select_related: 101 queries → 1                        ║
║  Composite index: company_id + status                         ║
║  Partial index: WHERE status='pending'                         ║
║  p95: 800ms → 320ms                                           ║
║                                                                ║
║  MYSQL                                                         ║
║  Engine = InnoDB (always), not MyISAM                         ║
║  AUTO_INCREMENT vs PostgreSQL SERIAL                          ║
║  EXPLAIN: type=ALL(bad), ref(index), const(best)              ║
║  Used in: YES Platform, NFC Tracker                           ║
║  PostgreSQL preferred for new projects                        ║
║                                                                ║
║  REDIS                                                         ║
║  STRING  = Cache, OTP, counters, feature flags                ║
║  LIST    = Task queue (Celery!), activity feed                ║
║  HASH    = Session storage (multiple fields per key)          ║
║  SET     = Unique visitors, membership check O(1)             ║
║  ZSET    = Rate limiting (sliding window), leaderboard        ║
║  STREAM  = Event log, consumer groups                         ║
║                                                                ║
║  REDIS PATTERNS:                                               ║
║  Cache-aside    = GET → miss → DB → SET                       ║
║  Distributed lock = SET NX EX + Lua delete                    ║
║  Rate limit     = ZREMRANGE + ZADD + ZCARD (pipeline)        ║
║  Celery broker  = LIST (LPUSH/BRPOP)                          ║
║  Pub/Sub        = PUBLISH / SUBSCRIBE                         ║
║                                                                ║
║  PERSISTENCE:                                                  ║
║  RDB = snapshot (fast restore, some data loss)                ║
║  AOF = append log (near-zero loss, slower)                    ║
║  Cache → RDB. Sessions/queue → AOF.                           ║
╚════════════════════════════════════════════════════════════════╝
```

---

*Last updated: 2026-08-15 · PwC Interview 2026-08-18*
*Resume skills: PostgreSQL · MySQL · Redis · Query Optimization · Indexing*