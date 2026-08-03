# MySQL Advanced Optimization — Theory Notes
**Format:** Hinglish | Interview Q&A Style  
**Topic:** Window Functions, CTEs, Query Optimization, Partitioning, InnoDB Internals

---

## Section A — Window Functions (MySQL 8.0+)

> MySQL 8.0 se available hain. Pehle ye sab subqueries se karna padta tha.  
> Window function = aggregate function ki tarah kaam karta hai, **but rows reduce nahi hoti**.

```sql
-- ROW_NUMBER — unique rank (no ties)
SELECT 
    name, category, price,
    ROW_NUMBER() OVER (PARTITION BY category ORDER BY price DESC) AS rank_in_category
FROM products;
```
- `PARTITION BY category` → har category ka apna window
- `ORDER BY price DESC` → window ke andar price se sort
- Result: Electronics row 1,2,3... Clothing row 1,2,3... alag alag

```sql
-- RANK vs DENSE_RANK (ties handle karna)
SELECT name, price,
    RANK() OVER (ORDER BY price DESC) AS rank,            -- gaps hote hain (1,1,3)
    DENSE_RANK() OVER (ORDER BY price DESC) AS dense_rank -- no gaps (1,1,2)
FROM products;
```
| name    | price | RANK | DENSE_RANK |
|---------|-------|------|------------|
| A       | 1000  | 1    | 1          |
| B       | 1000  | 1    | 1          |
| C       | 800   | 3    | 2          |

```sql
-- Top-N per group (top 3 products per category)
SELECT * FROM (
    SELECT name, category, price,
        ROW_NUMBER() OVER (PARTITION BY category ORDER BY price DESC) AS rn
    FROM products
) ranked
WHERE rn <= 3;
```
> Classic interview question! Subquery mein window function, outer mein filter.

```sql
-- Running total aur 7-day moving average
SELECT 
    created_at, total_amount,
    SUM(total_amount) OVER (ORDER BY created_at) AS running_total,
    AVG(total_amount) OVER (ORDER BY created_at ROWS BETWEEN 6 PRECEDING AND CURRENT ROW) AS avg_7day
FROM orders;
```
- `ROWS BETWEEN 6 PRECEDING AND CURRENT ROW` → current row + pichle 6 rows = 7 rows window

```sql
-- LAG / LEAD (previous/next row access)
SELECT 
    DATE(created_at) AS sale_date,
    SUM(total_amount) AS daily_revenue,
    LAG(SUM(total_amount), 1) OVER (ORDER BY DATE(created_at)) AS prev_day,
    SUM(total_amount) - LAG(SUM(total_amount), 1) OVER (ORDER BY DATE(created_at)) AS day_change
FROM orders
GROUP BY DATE(created_at);
```
- `LAG(col, n)` → n rows pehle ki value
- `LEAD(col, n)` → n rows baad ki value
- Day-over-day change nikalne ka best way

```sql
-- NTILE — rows ko equal buckets mein divide karo
SELECT name, price,
    NTILE(4) OVER (ORDER BY price) AS price_quartile  -- Q1, Q2, Q3, Q4
FROM products;
```
- 100 rows + NTILE(4) → 25-25-25-25 rows per quartile

---

## Section B — CTEs (Common Table Expressions)

> `WITH` clause se define hoti hai. Temporary named result set.  
> Readability badhata hai. Subquery replace karta hai.

```sql
-- Basic CTE: Monthly revenue analysis
WITH monthly_revenue AS (
    SELECT 
        DATE_FORMAT(created_at, '%Y-%m') AS month,
        SUM(total_amount) AS revenue,
        COUNT(*) AS order_count
    FROM orders
    WHERE status = 'delivered'
    GROUP BY DATE_FORMAT(created_at, '%Y-%m')
)
SELECT month, revenue, order_count,
    revenue / order_count AS avg_order_value,
    revenue / SUM(revenue) OVER () * 100 AS revenue_pct
FROM monthly_revenue
ORDER BY month;
```
- `SUM(revenue) OVER ()` → window function for total across all months
- `revenue_pct` → % contribution of each month

```sql
-- Multiple CTEs (comma se separate)
WITH 
top_customers AS (
    SELECT user_id, SUM(total_amount) AS total_spent
    FROM orders WHERE status != 'cancelled'
    GROUP BY user_id
    ORDER BY total_spent DESC
    LIMIT 10
),
customer_details AS (
    SELECT u.id, u.name, u.email, u.city
    FROM users u
    JOIN top_customers tc ON u.id = tc.user_id
)
SELECT cd.*, tc.total_spent
FROM customer_details cd
JOIN top_customers tc ON cd.id = tc.user_id;
```
> Multiple CTEs ek chain banate hain. Baad wala pehle wale ko reference kar sakta hai.

```sql
-- Recursive CTE (category hierarchy, org chart)
WITH RECURSIVE category_tree AS (
    -- Base case: root categories (koi parent nahi)
    SELECT id, name, parent_id, 0 AS level, name AS path
    FROM categories WHERE parent_id IS NULL
    
    UNION ALL
    
    -- Recursive case: child categories
    SELECT c.id, c.name, c.parent_id, ct.level + 1, 
           CONCAT(ct.path, ' > ', c.name)
    FROM categories c
    JOIN category_tree ct ON c.parent_id = ct.id
)
SELECT * FROM category_tree ORDER BY path;
```
**Output:**
```
Electronics
Electronics > Laptops
Electronics > Laptops > Gaming Laptops
Electronics > Mobiles
Clothing
Clothing > Men
```
- `RECURSIVE` keyword zaroori hai
- Base case + UNION ALL + Recursive case
- Termination: jab koi aur rows match na karein

---

## Section C — Query Optimization (CRITICAL for Interviews)

### EXPLAIN Output Padhna

```sql
EXPLAIN SELECT o.*, u.name FROM orders o 
JOIN users u ON o.user_id = u.id WHERE o.status = 'paid';
```

**Key Columns:**
| Column | What to Look For |
|--------|-----------------|
| `type` | `ALL` (worst) → `index` → `ref` → `eq_ref` → `const` (best) |
| `key` | `NULL` = koi index use nahi hua! Problem hai. |
| `rows` | Estimated rows scanned — jitna kam utna achha |
| `Extra` | `Using filesort` = bad, `Using temporary` = bad, `Using index` = great |

**Extra field meanings:**
- `Using filesort` → ORDER BY ke liye index nahi → disk sort hoti hai → **SLOW**
- `Using temporary` → Temporary table create hui → GROUP BY/DISTINCT mein → **SLOW**
- `Using index` → Covering index! Data index se hi mila, table touch nahi hua → **FAST**
- `Using where` → WHERE filter rows fetch ke baad apply hua → normal

### 6 Common Optimization Patterns

**1. SELECT * avoid karo**
```sql
-- Bad: Unnecessary columns fetch, more I/O, no covering index possible
SELECT * FROM orders WHERE user_id = 1;

-- Good: Sirf zaroori columns
SELECT id, status, total_amount, created_at FROM orders WHERE user_id = 1;
```

**2. Indexed column pe function mat lagao**
```sql
-- Bad: YEAR() function index tod deta hai — full table scan!
SELECT * FROM orders WHERE YEAR(created_at) = 2024;

-- Good: Range use karo, index kaam karega
SELECT * FROM orders WHERE created_at BETWEEN '2024-01-01' AND '2024-12-31 23:59:59';
```
> Rule: Indexed column ko function ke andar wrap mat karo.

**3. Leading wildcard avoid karo**
```sql
-- Bad: Full table scan, index useless
SELECT * FROM products WHERE name LIKE '%laptop%';

-- Better: Index use hoga (prefix match)
SELECT * FROM products WHERE name LIKE 'laptop%';

-- Best: Full-text search ke liye FULLTEXT index
SELECT * FROM products WHERE MATCH(name) AGAINST('laptop' IN BOOLEAN MODE);
```

**4. ORDER BY + LIMIT ke liye index**
```sql
-- Ye query fast tabhi hogi jab created_at pe index ho
SELECT * FROM orders ORDER BY created_at DESC LIMIT 10;

-- Index banao:
CREATE INDEX idx_orders_created ON orders(created_at);
```

**5. NOT IN → NOT EXISTS se replace karo**
```sql
-- Slow: NOT IN NULL values ke saath unpredictable behave karta hai
SELECT * FROM users WHERE id NOT IN (SELECT user_id FROM orders);

-- Faster: NOT EXISTS subquery short-circuit karta hai
SELECT * FROM users u 
WHERE NOT EXISTS (SELECT 1 FROM orders o WHERE o.user_id = u.id);
```

**6. N+1 Problem (ORMs mein bahut common)**
```python
# Bad — N+1: Har user ke liye alag query!
users = get_all_users()        # 1 query
for user in users:
    orders = get_orders(user.id)  # N queries! (100 users = 101 total queries)

# Good — Single JOIN query
SELECT u.*, o.id AS order_id, o.total_amount
FROM users u
LEFT JOIN orders o ON u.id = o.user_id;
# = 1 query, much faster
```

---

## Section D — Partitioning

> Badi tables ko physically alag alag parts mein divide karo.  
> Query sirf relevant partition scan karti hai → **Partition Pruning**.

### RANGE Partitioning (Date-based — Most Common)
```sql
CREATE TABLE orders_partitioned (
    id INT NOT NULL AUTO_INCREMENT,
    user_id INT,
    total_amount DECIMAL(10,2),
    created_at DATETIME NOT NULL,
    PRIMARY KEY (id, created_at)  -- Partition key PRIMARY KEY mein hona chahiye
) PARTITION BY RANGE (YEAR(created_at)) (
    PARTITION p2022 VALUES LESS THAN (2023),
    PARTITION p2023 VALUES LESS THAN (2024),
    PARTITION p2024 VALUES LESS THAN (2025),
    PARTITION p_future VALUES LESS THAN MAXVALUE
);

-- Partition pruning verify karo
EXPLAIN SELECT * FROM orders_partitioned WHERE YEAR(created_at) = 2024;
-- partitions column mein sirf 'p2024' dikhega — rest skip!
```

### LIST Partitioning (Fixed Values)
```sql
PARTITION BY LIST COLUMNS (status) (
    PARTITION p_active   VALUES IN ('pending', 'paid', 'shipped'),
    PARTITION p_inactive VALUES IN ('delivered', 'cancelled', 'refunded')
);
```

### HASH Partitioning (Even Distribution)
```sql
PARTITION BY HASH (user_id) PARTITIONS 8;  -- user_id % 8 se partition decide hota hai
```

### Partition Management
```sql
-- New partition add karo (yearly rotation)
ALTER TABLE orders_partitioned ADD PARTITION (
    PARTITION p2025 VALUES LESS THAN (2026)
);

-- Old data purge — DROP PARTITION = DELETE se 100x fast!
ALTER TABLE orders_partitioned DROP PARTITION p2022;
```
> `DROP PARTITION` ka advantage: Rows individually delete nahi karti, poora file delete hota hai.

### Partitioning Kab Use Karein?
- Table > 100 million rows ho
- Date-range queries common ho (logs, orders, events)
- Old data archiving/deletion zaroori ho
- Single partition operations sufficient ho

---

## Section E — InnoDB Storage Engine Internals

### B-Tree Clustered Index

```
Primary Key = Clustered Index
  → Data physically PRIMARY KEY ORDER mein stored hota hai (disk pe)
  → Table = B-Tree jiska leaf node = actual data row

Secondary Index (e.g., index on email):
  → Leaf node mein Primary Key stored hota hai (data nahi)
  → Lookup: Secondary B-Tree → Primary Key → Clustered B-Tree → Data
  → 2 B-tree traversals hote hain (double lookup)
```

> Isliye Primary Key choose carefully karo. INT AUTO_INCREMENT best hai. UUID bad hai (random inserts → B-tree fragmentation).

### Buffer Pool

```
Default size: 128MB  ← Production ke liye bahut kam!
Recommended:  70-80% of total RAM

SET GLOBAL innodb_buffer_pool_size = 4 * 1024 * 1024 * 1024;  -- 4GB

Kaise kaam karta hai:
  Hot data  → Buffer Pool mein cache (RAM) → Fast reads
  Cold data → Disk se read (I/O) → Slow
  
  LRU (Least Recently Used) algorithm → old data evict hota hai
```

### InnoDB Row Formats

| Format | Use Case |
|--------|----------|
| `DYNAMIC` | Default (MySQL 8) — variable-length columns best handled |
| `COMPACT` | Older, compatible |
| `COMPRESSED` | Disk space save, but slower |

### MVCC (Multi-Version Concurrency Control)

```
Problem: Read aur Write ek saath kaise ho bina lock ke?

Solution — MVCC:
  Each row ke multiple versions stored hain (undo log mein)
  
  Transaction T1 starts (snapshot at time X):
    → T1 sirf X ke pehle ki committed data dekhta hai
    → T2 write kare tab bhi T1 ko nahi dikhega (T1 ka snapshot purana hai)
  
  Reader writers ko block nahi karta
  Writer readers ko block nahi karta
  → High concurrency!
```

### Redo Log vs Undo Log

```
Redo Log (Write-Ahead Log):
  → COMMIT ke baad data durability guarantee
  → Crash recovery: incomplete transactions redo log se recover hoti hain
  → innodb_log_file_size se control hota hai

Undo Log:
  → ROLLBACK ke liye old data versions store karta hai
  → MVCC ke liye old snapshots
  → Large transactions = large undo log
```

---

## Section F — Replication Basics

### Master-Slave Architecture

```
                    Binary Log
  [ Master DB ] ─────────────► [ Slave DB 1 ]
                                [ Slave DB 2 ]
                                [ Slave DB 3 ]

Master: All WRITEs (INSERT, UPDATE, DELETE)
Slave:  All READs (SELECT)
```

### Read Scaling Pattern

```
Application → MySQL Router / ProxySQL
                    │
         ┌──────────┴──────────┐
         ▼                     ▼
    WRITE → Master        READ → Replica(s)
```

### Python with Read Replica

```python
import mysql.connector

# Separate connections for read and write
write_conn = mysql.connector.connect(
    host="master-db.internal",
    user="app_user", password="secret",
    database="myapp"
)
read_conn = mysql.connector.connect(
    host="replica-db.internal",  # Replica host
    user="app_user", password="secret",
    database="myapp"
)

def get_product(product_id):
    """Read from replica — fast, non-blocking"""
    with read_conn.cursor(dictionary=True) as cursor:
        cursor.execute("SELECT * FROM products WHERE id = %s", (product_id,))
        return cursor.fetchone()

def update_product(product_id, data):
    """Write to master — consistent"""
    with write_conn.cursor() as cursor:
        cursor.execute(
            "UPDATE products SET price = %s WHERE id = %s",
            (data['price'], product_id)
        )
        write_conn.commit()
```

> **Replication Lag:** Write master pe hota hai, replica slightly behind ho sakta hai.  
> Critical reads (e.g., payment confirmation) → Master se karo.  
> Analytics, listings → Replica se karo.

---

## Section G — Performance Tuning

### Slow Query Log

```sql
-- Enable slow query log
SET GLOBAL slow_query_log = 'ON';
SET GLOBAL long_query_time = 1;          -- 1 second se zyada = slow
SET GLOBAL slow_query_log_file = '/var/log/mysql/slow.log';

-- Verify settings
SHOW VARIABLES LIKE 'slow_query%';
SHOW VARIABLES LIKE 'long_query_time';
```

### Important System Variables

```sql
-- Buffer pool size check
SHOW VARIABLES LIKE 'innodb_buffer_pool_size';

-- Max connections
SHOW VARIABLES LIKE 'max_connections';  -- Default: 151

-- Query cache (MySQL 8 mein REMOVED — Redis use karo)
SHOW VARIABLES LIKE 'query_cache%';
```

### Connection Pooling

```sql
-- Current connections
SHOW STATUS LIKE 'Threads_connected';

-- Peak connections ever
SHOW STATUS LIKE 'Max_used_connections';

-- Connection errors
SHOW STATUS LIKE 'Connection_errors%';
```

> **Never** create new DB connection per HTTP request!  
> Use connection pool: `mysql-connector-python` pool, SQLAlchemy pool, PgBouncer equivalent.

### Live Monitoring Queries

```sql
-- Running queries dekho
SHOW PROCESSLIST;

-- Long-running queries kill karo
KILL QUERY <process_id>;

-- InnoDB engine full status
SHOW ENGINE INNODB STATUS\G

-- Active transactions
SELECT * FROM information_schema.INNODB_TRX;

-- Current locks (deadlock debug)
SELECT * FROM information_schema.INNODB_LOCKS;

-- Lock waits
SELECT * FROM information_schema.INNODB_LOCK_WAITS;
```

### Index Analysis

```sql
-- Table ke indexes dekho
SHOW INDEX FROM orders;

-- Unused indexes find karo (MySQL sys schema)
SELECT * FROM sys.schema_unused_indexes;

-- Redundant indexes
SELECT * FROM sys.schema_redundant_indexes;

-- Index stats
SELECT * FROM information_schema.STATISTICS 
WHERE table_schema = 'mydb' AND table_name = 'orders';
```

---

## Section H — MySQL 8 Index Features: Invisible & Descending Indexes

### Invisible indexes — "index hatane se pehle test karo"

Production me index DROP karna scary hai — kya koi query use kar rahi thi? Invisible = optimizer ke liye गायब, par maintained:

```sql
ALTER TABLE orders ALTER INDEX idx_customer_date INVISIBLE;
-- Index ab bhi update hota hai har write pe, par optimizer USE nahi karta

-- 24-48 ghante monitor karo: slow query log / performance_schema me regression?
--   Regression aayi  → ALTER INDEX ... VISIBLE;   (instant rollback, rebuild nahi)
--   Sab theek        → DROP INDEX ...;             (ab confidently)
```

**Interview line:** *"Index drop karne se pehle main use INVISIBLE karta hoon — writes pe maintain hota rehta hai isliye rollback instant hai, aur agar koi hidden query regress kare to VISIBLE wapas ek metadata flip hai, multi-hour index rebuild nahi."* (PostgreSQL me direct equivalent nahi — wahan `hypopg` hypothetical indexes ulta direction test karte hain.)

### Descending indexes — mixed-order ORDER BY ka fix

MySQL 8 se pehle `INDEX (a ASC, b DESC)` me DESC **parse hota tha par ignore** hota tha — mixed-direction sorts filesort karate the:

```sql
-- Feed query: naye posts pehle, same-time pe author A-Z
SELECT * FROM posts ORDER BY created_at DESC, author ASC LIMIT 20;

-- MySQL 8: ab genuinely descending store hota hai
CREATE INDEX idx_feed ON posts (created_at DESC, author ASC);
-- EXPLAIN: "Using index" — no filesort ✅
-- (Single-column DESC scan to pehle bhi backward-scan se ho jata tha;
--  yeh MIXED directions ke liye matter karta hai)
```

---

## Interview Q&A — Advanced Optimization

**Q1: Window functions MySQL mein kab available hue?**

> MySQL 8.0 se (2018 mein). Pehle ye sab subqueries ya application-level code se karna padta tha.  
> ROW_NUMBER, RANK, DENSE_RANK, LAG, LEAD, NTILE, FIRST_VALUE, LAST_VALUE, SUM/AVG OVER() — sab 8.0+ mein.

---

**Q2: EXPLAIN mein "Using filesort" kya problem hai? Kaise fix karein?**

> Matlab ORDER BY ke liye koi index available nahi tha — MySQL ne sab rows fetch ki, phir sort ki.  
> Badi tables pe bahut slow hota hai.  
>
> **Fix:**  
> 1. ORDER BY columns pe composite index banao  
> 2. Index column order = ORDER BY column order hona chahiye  
> `CREATE INDEX idx_orders_status_date ON orders(status, created_at DESC);`  
> `SELECT * FROM orders WHERE status='paid' ORDER BY created_at DESC;` — ab filesort nahi

---

**Q3: Partitioning kab use karo? Partition pruning kya hai?**

> **Use karo jab:**  
> - Table > 50-100M rows ho  
> - Date-range queries dominant ho (logs, transactions)  
> - Old data regularly delete karna ho  
>
> **Partition Pruning:**  
> WHERE clause se MySQL decide karta hai ki kaunsa partition scan karna hai, baaki skip.  
> `WHERE YEAR(created_at) = 2024` → sirf p2024 partition scan, p2022/p2023 completely skip.  
> EXPLAIN mein `partitions` column mein visible hota hai.

---

**Q4: InnoDB Buffer Pool kya hai? Production mein kitna set karo?**

> RAM mein data aur index pages ka cache.  
> Hot data buffer pool mein rehta hai → disk I/O nahi hoti → fast queries.  
>
> **Production:**  
> - Dedicated DB server → 70-80% of RAM  
> - 32GB RAM server → 24-25GB buffer pool  
> - `SET GLOBAL innodb_buffer_pool_size = 25769803776;`  
> - my.cnf mein: `innodb_buffer_pool_size = 25G`  
>
> `SHOW STATUS LIKE 'Innodb_buffer_pool_read_requests';`  
> `SHOW STATUS LIKE 'Innodb_buffer_pool_reads';`  
> Hit ratio = (read_requests - reads) / read_requests → 99%+ target karo.

---

**Q5: Read Replica setup kyu karte hain? Consistency guarantee hai kya?**

> **Kyu:**  
> - Read traffic master se hata ke replicas pe distribute karo  
> - Master sirf writes handle kare → faster writes  
> - Analytics queries replicas pe run karo → master ko load na do  
> - Geographic distribution (users ke nazdik replica)  
>
> **Consistency:**  
> - Async replication → Replication LAG exist karta hai (usually milliseconds)  
> - Master pe write karo, turant replica pe read karo → purana data mil sakta hai  
> - Strongly consistent reads → Master se karo (payment, inventory check)  
> - Eventually consistent reads → Replica se karo (product listings, reports)

---

**Q6: SELECT * avoid kyu karein?**

> 4 reasons:
> 1. **Extra I/O:** Unnecessary columns bhi disk se read hoti hain
> 2. **Covering index impossible:** SELECT * ke saath index-only scan nahi hoti — table rows fetch karne padte hain
> 3. **Network overhead:** App server tak zyada data travel karta hai
> 4. **Schema change fragile:** New column add hone pe application code break ho sakta hai  
>
> Sirf zaroori columns explicitly list karo. Indexes bhi better utilize hote hain.

---

**Q7: MVCC kya hai? InnoDB mein kaise kaam karta hai?**

> **MVCC = Multi-Version Concurrency Control**  
> Problem solve karta hai: Readers aur Writers ek saath kaise kaam karein bina lock ke?  
>
> **Mechanism:**  
> - Har row ke saath hidden columns: `DB_TRX_ID` (transaction ID) aur `DB_ROLL_PTR` (undo log pointer)  
> - Transaction start pe snapshot liya jata hai (read view)  
> - Read: Transaction apne snapshot ke according hi rows dekhta hai  
> - Write: Nayi version create hoti hai, old version undo log mein  
> - Commit: Version visible hoti hai future transactions ke liye  
> - Rollback: Undo log se old version restore  
>
> **Benefit:** `SELECT` never `INSERT/UPDATE` ko block karta, vice versa bhi.  
> `READ COMMITTED` vs `REPEATABLE READ` → MVCC snapshot timing mein difference hai.
