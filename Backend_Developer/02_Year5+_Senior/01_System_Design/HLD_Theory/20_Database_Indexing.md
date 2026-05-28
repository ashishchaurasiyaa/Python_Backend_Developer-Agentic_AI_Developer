# Database Indexing — B-Tree, Hash, Composite Indexes, SQL Query Optimization

## Quick Reference Card
```
Index        → Separate data structure that speeds up queries — like book ka index
B-Tree       → Default index — range queries, ORDER BY, equality — O(log n)
Hash         → Equality only — WHERE id = 5 — O(1) — not for range
Composite    → Multiple columns — (user_id, created_at) — column order matters!
Covering     → Index has all columns query needs — no table access needed
EXPLAIN      → PostgreSQL plan analyzer — use this to debug slow queries
Interview hook → "Booking query 500ms → 20ms after composite index (user_id, created_at)"
```

---

## PART 1: HINGLISH — Samjhne ke liye

### 1.1 Index Kya Hai?

**Analogy: Dictionary / Phonebook**

Dictionary mein 10,000 words hain. "Xerography" dhundhna hai.
- **Without index**: Page 1 se start karo, har page padho... 500 pages tak (table scan!)
- **With index (alphabetical order)**: X section seedha jao → page 450 → 2 seconds!

Database mein index ek alag data structure hai jo:
- Query fast karta hai
- Extra storage leta hai
- Write operations thoda slow karta hai (index bhi update karna hota hai)

```
WITHOUT INDEX:
  SELECT * FROM bookings WHERE user_id = 123;
  
  → Full table scan: Check EVERY row
  → 1 million rows: 1 million comparisons
  → Slow: O(n)

WITH INDEX on user_id:
  → B-Tree traversal: ~20 comparisons for 1 million rows
  → Fast: O(log n)

  Index structure (simplified):
  user_id | row_pointer
  --------+-----------
  1       → row at disk page 42
  5       → row at disk page 71
  123     → row at disk page 891  ← Found! Jump directly
  789     → row at disk page 234
```

---

### 1.2 B-Tree Index — Default PostgreSQL Index

```
B-TREE (Balanced Tree):
  Self-balancing tree where leaf nodes contain actual key values + row pointers
  
  Structure:
                    [50, 100]
                   /    |    \
            [10,20]  [60,80]  [120,180]
           /  |  \  ...
          [5][15][25]...
  
  All leaf nodes at same depth → O(log n) always
  
  SUPPORTS:
  ✓ Equality:       WHERE id = 5
  ✓ Range:          WHERE price BETWEEN 1000 AND 5000
  ✓ Greater/Less:   WHERE created_at > '2024-01-01'
  ✓ LIKE prefix:    WHERE name LIKE 'Ashish%' (prefix, not %Ashish%)
  ✓ ORDER BY:       Can use index for sort, avoiding full sort
  ✓ NULL checks:    WHERE field IS NULL / IS NOT NULL
  
  NOT EFFICIENT FOR:
  ✗ LIKE suffix:    WHERE name LIKE '%Kumar' (can't use B-Tree)
  ✗ Full-text:      WHERE description LIKE '%backwater%' (use tsvector/GIN)
  ✗ Function:       WHERE LOWER(email) = 'ashish@...' (unless functional index)

CREATE INDEX idx_bookings_user ON bookings(user_id);
CREATE INDEX idx_bookings_date ON bookings(created_at);
CREATE INDEX idx_packages_price ON packages(price);
```

---

### 1.3 Hash Index

```
HASH INDEX:
  Key → hash function → bucket → row pointer
  
  "user_id = 123" → hash(123) = 47 → bucket 47 → row pointer
  
  SUPPORTS:
  ✓ Equality ONLY: WHERE session_token = 'abc123'
  
  NOT SUPPORTED:
  ✗ Range:     WHERE id > 100 (no ordering in hash)
  ✗ ORDER BY:  Can't sort using hash
  ✗ LIKE:      Can't do prefix match

  O(1) for equality lookups (faster than B-Tree's O(log n)!)

WHEN TO USE HASH INDEX:
  - Session tokens, API keys (random strings, equality only)
  - UUIDs (equality lookup only)
  - No range queries ever needed on this column
  
  In practice: B-Tree is usually better because it handles both equality AND range
  Hash index saved space historically (less so in modern PostgreSQL)
  
  PostgreSQL (before 10): Hash indexes NOT crash-safe
  PostgreSQL 10+: Hash indexes are WAL-logged, safe to use

CREATE INDEX idx_sessions_token ON sessions USING HASH (token);
```

---

### 1.4 Composite Index — Multiple Columns

```
COMPOSITE INDEX: Index on (col1, col2, col3...)

KEY RULE: LEFTMOST PREFIX RULE
  Index: (user_id, created_at, status)
  
  CAN USE INDEX:
  ✓ WHERE user_id = 5                          (first column used)
  ✓ WHERE user_id = 5 AND created_at > 'date'  (first two columns)
  ✓ WHERE user_id = 5 AND created_at > 'date' AND status = 'active'  (all three)
  ✓ ORDER BY user_id, created_at               (in order)
  
  CANNOT USE INDEX:
  ✗ WHERE created_at > 'date'      (skipped user_id — leftmost missing!)
  ✗ WHERE status = 'active'        (skipped both user_id and created_at)
  ✗ WHERE user_id = 5 AND status = 'active'  (only user_id used, status skipped)

COLUMN ORDER MATTERS:
  Most selective column first? Or most frequently filtered first?
  
  RULE 1: Put equality columns BEFORE range columns
  Index: (user_id, status, created_at)
  ✓ WHERE user_id = 5 AND status = 'active' AND created_at > 'date'
  ✗ Index: (created_at, user_id, status)  — bad order
  
  RULE 2: High cardinality columns first
  user_id (millions of users) BEFORE status ('active'/'inactive' — only 2 values)
  
EXAMPLE:
  Booking table — common query:
  SELECT * FROM bookings WHERE user_id = ? AND status = 'confirmed' ORDER BY created_at DESC
  
  Best index: (user_id, status, created_at)
  - user_id equality first (high cardinality, always in query)
  - status equality second (limits results significantly)
  - created_at for ORDER BY (no extra sort needed!)
  
  CREATE INDEX idx_bookings_user_status_date 
  ON bookings(user_id, status, created_at DESC);
```

---

### 1.5 Covering Index

```
COVERING INDEX: Index contains ALL columns the query needs
  Query can be answered from index alone — no need to hit the actual table!
  
  Query: SELECT user_id, status, amount FROM bookings WHERE user_id = 5
  
  Without covering index:
  1. B-Tree index: Find rows with user_id = 5
  2. For each row found: Fetch actual row from table (extra disk I/O!)
  
  With covering index (user_id, status, amount):
  1. B-Tree index: Find rows with user_id = 5
  2. Read status + amount directly from index (no table access!)
  → Much faster!

PostgreSQL: INCLUDE clause for covering index
  
  CREATE INDEX idx_bookings_covering
  ON bookings(user_id)
  INCLUDE (status, amount, created_at);
  -- user_id = search key, status/amount/created_at = included for covering
  
  -- Query that uses this covering index:
  SELECT status, amount, created_at
  FROM bookings
  WHERE user_id = 5
  ORDER BY created_at;
  -- Answered ENTIRELY from index!

MySQL: Covering index achieved by including all query columns in index definition
  CREATE INDEX idx ON bookings(user_id, status, amount, created_at);
```

---

### 1.6 Functional / Expression Index

```
FUNCTIONAL INDEX: Index on expression/function result

Problem:
  SELECT * FROM users WHERE LOWER(email) = 'ashish@youngman.com'
  Regular index on email: won't help (case mismatch)
  
  Solution:
  CREATE INDEX idx_users_email_lower ON users(LOWER(email));
  -- Now LOWER(email) query uses index!

Other examples:
  -- Date extraction
  CREATE INDEX idx_bookings_month ON bookings(EXTRACT(MONTH FROM created_at));
  -- Query: WHERE EXTRACT(MONTH FROM created_at) = 1
  
  -- JSON field
  CREATE INDEX idx_meta_source ON events((metadata->>'source'));
  -- Query: WHERE metadata->>'source' = 'web'
  
  -- Partial expression
  CREATE INDEX idx_active_premium ON users(email)
  WHERE is_active = true AND plan = 'premium';
  -- Only indexes active premium users (smaller, faster!)
  
  -- URL path prefix
  CREATE INDEX idx_url_prefix ON requests(LEFT(url, 50));
```

---

### 1.7 EXPLAIN ANALYZE — Debugging Slow Queries

```sql
-- Add EXPLAIN ANALYZE before any query to see execution plan

EXPLAIN ANALYZE
SELECT b.*, u.name FROM bookings b
JOIN users u ON b.user_id = u.id
WHERE b.status = 'confirmed'
AND b.created_at > '2024-01-01'
ORDER BY b.created_at DESC
LIMIT 50;

-- Output:
Limit  (cost=0.00..892.43 rows=50)  (actual time=0.143..45.231 rows=50)
  -> Sort  (cost=892.43..901.72 rows=3714)  (actual time=44.912..45.132 rows=50)
       Sort Key: b.created_at DESC
       Sort Method: top-N heapsort  Memory: 36kB
       -> Hash Join  (cost=234.50..780.12 rows=3714)  (actual time=15.231..43.891 rows=3714)
            Hash Cond: (b.user_id = u.id)
            -> Seq Scan on bookings b  (cost=0.00..542.12 rows=3714)
                   ← PROBLEM! "Seq Scan" = no index used!
                   Filter: ((status='confirmed') AND (created_at>'2024-01-01'))
                   Rows Removed by Filter: 46286
            -> Hash  (cost=145.00..145.00 rows=5000)
                   -> Seq Scan on users u

-- Interpretation:
-- "Seq Scan on bookings" → Full table scan! Index missing
-- "Rows Removed by Filter: 46286" → Scanning 50000 rows, returning 3714

-- FIX: Add composite index
CREATE INDEX idx_bookings_status_date ON bookings(status, created_at DESC);

-- After index, EXPLAIN shows:
-- Index Scan using idx_bookings_status_date on bookings
-- → Much faster!

-- Key things to look for in EXPLAIN:
-- "Seq Scan" → No index (usually bad on large tables)
-- "Index Scan" → Using index ✓
-- "Index Only Scan" → Covering index ✓✓ (no table access)
-- "Hash Join" → Join method (sometimes slow on large tables)
-- "Nested Loop" → Join method (fast when outer side is small)
-- High "actual time" → This node is slow
-- "cost=" numbers → Optimizer's estimate (not actual)
-- "actual time=" → Real execution time
```

---

### 1.8 Index Design for Common Queries

```python
# Django model with proper indexes

class Booking(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, db_index=True)
    package = models.ForeignKey(Package, on_delete=models.CASCADE, db_index=True)
    status = models.CharField(max_length=20)
    created_at = models.DateTimeField(auto_now_add=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    
    class Meta:
        indexes = [
            # Most common query: user's bookings
            models.Index(fields=['user', 'status', '-created_at'],
                        name='idx_booking_user_status_date'),
            
            # Admin dashboard: all confirmed bookings by date
            models.Index(fields=['status', '-created_at'],
                        name='idx_booking_status_date'),
            
            # Financial report: bookings in date range
            models.Index(fields=['-created_at'],
                        name='idx_booking_date'),
        ]

class Invoice(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE)
    status = models.CharField(max_length=20)
    due_date = models.DateField()
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    
    class Meta:
        indexes = [
            # "Company X ke overdue invoices"
            models.Index(fields=['company', 'status', 'due_date'],
                        name='idx_invoice_company_status_due'),
            
            # "All unpaid invoices overdue"
            models.Index(fields=['status', 'due_date'],
                        name='idx_invoice_status_due'),
        ]

# EXPLAIN the query to verify index is used:
from django.db import connection

def explain_query():
    qs = Booking.objects.filter(
        user_id=5,
        status='confirmed'
    ).order_by('-created_at')
    
    print(qs.explain(verbose=True, analyze=True))
    # Shows PostgreSQL execution plan
```

---

### 1.9 Common Index Anti-Patterns

```
1. INDEX ON EVERY COLUMN (over-indexing):
   ✗ Each insert/update must maintain ALL indexes
   ✗ 10 indexes on a write-heavy table = 10x write overhead
   ✓ Index only what's queried frequently
   Rule: Start with zero indexes, add only when EXPLAIN shows Seq Scan on large tables

2. NOT USING INDEX DUE TO FUNCTION:
   ✗ WHERE YEAR(created_at) = 2024   (function on indexed column → ignores index!)
   ✓ WHERE created_at BETWEEN '2024-01-01' AND '2024-12-31'
   ✓ OR create functional index: CREATE INDEX ON t (YEAR(created_at))

3. LIKE % prefix (wildcard at start):
   ✗ WHERE name LIKE '%Kumar'  (can't use B-Tree for this)
   ✓ WHERE name LIKE 'Kumar%' (prefix match works!)
   ✓ For contains: Use full-text index (GIN with tsvector)

4. WRONG COLUMN ORDER in composite:
   ✗ (status, user_id) when queries always have user_id
   ✓ (user_id, status) — more selective column first

5. INDEX ON LOW CARDINALITY COLUMN:
   ✗ CREATE INDEX ON bookings(status)
      (status has only 3-4 values — 25% rows per value = table scan faster!)
   ✓ Use as SECOND column in composite with high-cardinality first
   ✓ Or use partial index:
      CREATE INDEX ON bookings(created_at) WHERE status = 'pending'
      (Only indexes pending bookings — small, fast)
```

---

### 1.10 Ashish ke projects mein

```
Youngman — Invoice query optimization:

BEFORE:
  # Invoice list for admin (1000+ invoices)
  Invoice.objects.filter(status='unpaid').order_by('-due_date')
  # EXPLAIN: Seq Scan on invoices (500ms!)

AFTER:
  # Added composite index
  models.Index(fields=['status', '-due_date'], name='idx_invoice_status_due')
  
  # Django generates:
  CREATE INDEX idx_invoice_status_due ON invoices(status, due_date DESC);
  
  # EXPLAIN after: Index Scan (20ms!)

Niroskos — Booking queries:
  # Most frequent query: "User X ke sab bookings"
  Booking.objects.filter(user_id=user_id).order_by('-created_at')
  
  # Composite index:
  models.Index(fields=['user', '-created_at'], name='idx_booking_user_date')
  
  # Even better: Covering index (amount bhi select karte hain)
  # Raw SQL index:
  # CREATE INDEX idx_booking_user_date_covering
  # ON bookings(user_id, created_at DESC) INCLUDE (status, amount);

N+1 query fix (not indexing but related):
  # BEFORE: 1 query for bookings + N queries for each user
  bookings = Booking.objects.all()
  for b in bookings:
      print(b.user.name)  # Each access = new query!
  
  # AFTER: 2 queries total
  bookings = Booking.objects.select_related('user').all()
  for b in bookings:
      print(b.user.name)  # No extra query — pre-fetched!
```

---

## PART 2: ENGLISH — Interviewer ko bolne ke liye

### 2.1 Definitions

> **Database Index**: An auxiliary data structure that provides fast lookup of rows based on indexed column values. Trades write overhead and storage for read performance. Default index in PostgreSQL and MySQL is B-Tree.

> **B-Tree Index**: A self-balancing tree structure that maintains sorted order of keys. Supports equality, range, and prefix queries in O(log n) time. The default and most versatile index type.

> **Composite Index**: An index on multiple columns. Follows the leftmost prefix rule — queries must use the indexed columns from left to right to benefit from the index.

---

### 2.2 Index Types Comparison

| Type | Data Structure | Query Support | Best For |
|------|---------------|---------------|----------|
| B-Tree | Balanced tree | Equality, range, prefix LIKE, IS NULL, ORDER BY | General purpose (default) |
| Hash | Hash table | Equality only (=) | Random string lookups |
| GIN | Inverted index | Array contains, full-text, JSONB | Full-text search, arrays, JSON |
| GiST | Generalized search tree | Geographic, range types, nearest neighbor | PostGIS, geometric data |
| BRIN | Block range | Min/max of sequential data | Very large tables, timestamp columns |
| Partial | B-Tree on subset | Equality, range (on filtered rows) | Sparse conditions (WHERE status='active') |

---

### 2.3 Index and Query Optimizer

```
PostgreSQL query planner decides whether to use index:
  
  FACTORS:
  1. Selectivity: How many rows does the WHERE clause select?
     - High selectivity (few rows) → Index Scan
     - Low selectivity (many rows, e.g. 80%) → Seq Scan may be faster
     (Sequential table scan = faster for 80% of table due to prefetch)
  
  2. Table size: Small tables → Seq Scan always (index overhead not worth it)
  
  3. Index statistics: pg_statistics tracks column data distribution
     ANALYZE table updates statistics
     Stale statistics → Planner makes bad decisions!
  
  4. VACUUM state: Bloated tables → inaccurate row counts

  Force index use (for testing):
  SET enable_seqscan = off;
  EXPLAIN SELECT ...; -- Now forced to use index
  SET enable_seqscan = on; -- Reset
  
  Update statistics:
  ANALYZE bookings; -- Update for specific table
  VACUUM ANALYZE bookings; -- Reclaim space + update stats
```

---

### 2.4 Real Project Answer

> "In Youngman's invoicing system, I identified slow queries using Django's `connection.queries` debug output and PostgreSQL's `pg_stat_statements` extension. The invoice listing was doing a sequential scan on a table of 50,000+ rows. I used `EXPLAIN ANALYZE` to confirm — it showed `Seq Scan on invoices, Rows Removed by Filter: 49500`. Adding a composite index `(company_id, status, due_date DESC)` brought that query from 500ms to 20ms. The key insight was column order: `company_id` first (highest cardinality, always in WHERE clause), then `status` (narrows to unpaid), then `due_date` (used for ORDER BY, so the index provides sort order without an extra sort step)."

---

### 2.5 Common Follow-up Q&A

**Q1: How do you identify which queries need indexes?**
> "Three tools: (1) `pg_stat_statements` extension — tracks all queries with execution time. Sort by `total_time DESC` to find the slowest queries. (2) PostgreSQL slow query log — set `log_min_duration_statement = 200ms` to log any query over 200ms. (3) Django Debug Toolbar in development — shows all queries per request with timing. Once slow queries are identified, run `EXPLAIN ANALYZE` on them to see the execution plan. 'Seq Scan' on large tables is the primary indicator that an index would help."

**Q2: What is the impact of indexes on write performance?**
> "Every index on a table adds overhead to INSERT, UPDATE, and DELETE operations because the index must be updated alongside the table. For INSERT: each index tree must be traversed to find the right position and updated — O(log n) per index. For UPDATE: if the indexed column changes, the old entry must be removed and new one inserted. For DELETE: old entries must be removed from all indexes. Rule of thumb: 5-10 indexes on a write-heavy table can increase write time by 2-5x. Solution: index only what's needed, use partial indexes (smaller), batch index creation with `CREATE INDEX CONCURRENTLY` (non-blocking)."

**Q3: What is a covering index and when is it beneficial?**
> "A covering index includes all columns referenced in a query — both in WHERE, JOIN conditions, and SELECT columns. The query can be answered entirely from the index without accessing the main table ('heap'). This is called an 'Index Only Scan' in PostgreSQL's EXPLAIN output. Benefit: eliminates the extra disk I/O of fetching actual rows — particularly valuable when the table is large and rows are scattered across many disk pages. PostgreSQL's INCLUDE clause adds non-searchable columns to the index: `CREATE INDEX ON bookings(user_id) INCLUDE (status, amount)`. The INCLUDE columns don't affect index ordering but allow covering index scans."

---

## Interview Cheat Sheet

```
B-Tree Index (default):
  O(log n), supports equality + range + ORDER BY
  CREATE INDEX idx_name ON table(column);

Hash Index:
  O(1) equality only, no range/sort
  CREATE INDEX idx USING HASH ON table(column);

Composite Index:
  (user_id, status, created_at)
  Leftmost prefix rule: query must use from left
  Equality columns first, range/sort last
  CREATE INDEX ON table(col1, col2, col3);

Covering Index:
  Include all SELECT columns → Index Only Scan
  CREATE INDEX ON table(search_col) INCLUDE (col1, col2);

EXPLAIN ANALYZE:
  Look for: Seq Scan (bad) vs Index Scan / Index Only Scan (good)
  Sort Method: "heapsort" bad → index sort good
  "Rows Removed by Filter" → selectivity indicator

Anti-patterns:
  Function on indexed column (YEAR(col) → no index use)
  LIKE '%suffix' (use full-text instead)
  Low cardinality column alone (status = only 3 values)
  Over-indexing (10+ indexes → slow writes)

Django:
  class Meta:
      indexes = [models.Index(fields=['user', '-created_at'])]
  
  qs.explain(analyze=True)  # See execution plan

My project:
  invoice (company, status, due_date): 500ms → 20ms
  booking (user, -created_at): fast user booking list
  N+1 fix: select_related/prefetch_related
```
