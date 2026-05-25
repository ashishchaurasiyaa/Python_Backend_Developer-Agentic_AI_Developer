# PostgreSQL Advanced — Indexes, EXPLAIN ANALYZE, Query Optimization

## Quick Concepts
- **Index** = fast lookup ke liye data structure (B-Tree, GIN, GiST, BRIN)
- **EXPLAIN ANALYZE** = query execution plan + actual timing dikhata hai
- **Partial index** = sirf certain rows ka index
- **Composite index** = multiple columns ka index
- **pgBouncer** = connection pooling — PostgreSQL max connections manage karo

---

## Interview Questions & Answers

### Q1: PostgreSQL mein indexes kaise kaam karte hain? Kab kaunsa use karo?
**Answer:**
```sql
-- B-Tree (default) — equality, range queries
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_orders_created ON orders(created_at DESC);

-- Composite index — multi-column filter
CREATE INDEX idx_orders_user_status ON orders(user_id, status);
-- Query: WHERE user_id = 5 AND status = 'pending'  → uses composite index
-- Query: WHERE user_id = 5                          → uses composite index (leftmost)
-- Query: WHERE status = 'pending'                   → DOES NOT use (user_id not first)

-- Partial index — sirf specific rows
CREATE INDEX idx_active_users ON users(email) WHERE is_active = TRUE;
-- Size bahut kam hota hai + faster

-- GIN index — JSONB, full-text search, arrays
CREATE INDEX idx_products_tags ON products USING GIN(tags);
CREATE INDEX idx_docs_content ON documents USING GIN(to_tsvector('english', content));

-- BRIN index — time-series data (append-only large tables)
CREATE INDEX idx_logs_created ON logs USING BRIN(created_at);

-- Covering index — index mein hi extra columns (table access avoid)
CREATE INDEX idx_orders_user_covering ON orders(user_id) INCLUDE (amount, status);

-- Unique index
CREATE UNIQUE INDEX idx_users_email_unique ON users(email);

-- Expression index
CREATE INDEX idx_users_lower_email ON users(LOWER(email));
-- Query: WHERE LOWER(email) = 'ashish@test.com'  → uses index
```

---

### Q2: EXPLAIN ANALYZE kaise padhte hain?
**Answer:**
```sql
EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT)
SELECT u.name, COUNT(o.id) as order_count
FROM users u
LEFT JOIN orders o ON o.user_id = u.id
WHERE u.is_active = TRUE
GROUP BY u.id
ORDER BY order_count DESC
LIMIT 10;

-- Output example:
-- Limit  (cost=450.23..450.25 rows=10) (actual time=12.4..12.5 rows=10)
--   -> Sort  (cost=450.23..455.23 rows=2000) (actual time=12.3..12.4 rows=10)
--     -> HashAggregate  (cost=320.00..340.00 rows=2000) (actual time=11.2..11.9)
--       -> Hash Left Join  (cost=100..280 rows=20000) (actual time=2.1..9.8)
--           Hash Cond: (o.user_id = u.id)
--           -> Seq Scan on orders  (actual time=0.01..4.2 rows=50000) ← BAD!
--           -> Hash  -> Index Scan on users (actual time=0.01..0.8 rows=1000)
-- Planning Time: 0.5 ms
-- Execution Time: 12.8 ms

-- Kya dekhna hai:
-- Seq Scan = full table scan → index missing ho sakta hai
-- cost=100..450 = estimated cost (units arbitrary)
-- actual time=12.4ms = real execution time
-- rows=50000 vs rows=10 = estimate vs actual (stats outdated?)
-- Buffers: hit=1200 miss=50 = cache hit rate

-- Stats update karo agar estimates wrong hain
ANALYZE users;
VACUUM ANALYZE orders;
```

---

### Q3: Slow queries optimize karne ke common techniques?
**Answer:**
```sql
-- 1. Index add karo
-- Query: SELECT * FROM orders WHERE user_id = 5 AND status = 'pending'
CREATE INDEX idx_orders_user_status ON orders(user_id, status);

-- 2. SELECT * avoid karo — sirf zaruri columns
-- BAD:
SELECT * FROM users JOIN profiles ON users.id = profiles.user_id;
-- GOOD:
SELECT users.id, users.name, profiles.bio FROM users JOIN profiles...;

-- 3. LIMIT use karo
SELECT * FROM orders ORDER BY created_at DESC LIMIT 20;

-- 4. Subquery → JOIN convert karo (often faster)
-- BAD:
SELECT * FROM users WHERE id IN (SELECT user_id FROM orders WHERE amount > 1000);
-- GOOD:
SELECT DISTINCT u.* FROM users u JOIN orders o ON o.user_id = u.id WHERE o.amount > 1000;

-- 5. COUNT(*) vs COUNT(column)
SELECT COUNT(*) FROM users;         -- faster (no null check)
SELECT COUNT(email) FROM users;     -- null skip karta hai

-- 6. Window functions — GROUP BY se better
SELECT
    user_id,
    amount,
    SUM(amount) OVER (PARTITION BY user_id) as user_total,
    ROW_NUMBER() OVER (PARTITION BY user_id ORDER BY created_at DESC) as rn
FROM orders;

-- 7. CTE (Common Table Expression)
WITH monthly_stats AS (
    SELECT
        DATE_TRUNC('month', created_at) as month,
        SUM(amount) as revenue
    FROM orders
    WHERE status = 'completed'
    GROUP BY 1
)
SELECT * FROM monthly_stats WHERE revenue > 100000;

-- 8. pg_stat_statements — slow queries identify karo
SELECT query, total_exec_time, calls, mean_exec_time
FROM pg_stat_statements
ORDER BY mean_exec_time DESC
LIMIT 10;
```

---

### Q4: pgBouncer kya hai? Connection pooling kyu zaroori hai?
**Answer:**
PostgreSQL har connection ke liye ek process fork karta hai — expensive! 1000 connections = 1000 processes.

**pgBouncer** ek connection pool manager hai:
- App → pgBouncer (many connections) → PostgreSQL (few connections)

```ini
# pgbouncer.ini
[databases]
myapp = host=localhost dbname=myapp

[pgbouncer]
listen_addr = 0.0.0.0
listen_port = 6432
auth_type = md5
auth_file = /etc/pgbouncer/userlist.txt
pool_mode = transaction    # transaction level pooling (best performance)
max_client_conn = 1000     # app se max connections
default_pool_size = 20     # PostgreSQL ko max 20 connections
min_pool_size = 5
reserve_pool_size = 5
log_connections = 0
log_disconnections = 0

# Pool modes:
# session    = client ka session end hone tak connection hold karo
# transaction = transaction end hone par release (RECOMMENDED)
# statement  = har statement ke baad release (most aggressive)
```

```python
# SQLAlchemy connection string pgBouncer ke liye
# Port 6432 (pgBouncer) instead of 5432 (PostgreSQL direct)
DATABASE_URL = "postgresql+asyncpg://user:pass@localhost:6432/myapp"

# pgBouncer ke saath prepared statements off karo
engine = create_async_engine(
    DATABASE_URL,
    connect_args={"prepared_statement_cache_size": 0},  # pgBouncer ke saath issue
)
```

---

### Q5: PostgreSQL JSONB kaise use karte hain?
**Answer:**
```sql
-- Table
CREATE TABLE products (
    id SERIAL PRIMARY KEY,
    name VARCHAR(200),
    metadata JSONB          -- JSONB = binary, indexed, fast; JSON = text stored
);

-- Insert
INSERT INTO products (name, metadata)
VALUES ('Laptop', '{"brand": "Dell", "specs": {"ram": 16, "ssd": 512}, "tags": ["gaming", "work"]}');

-- Query
SELECT * FROM products WHERE metadata->>'brand' = 'Dell';
SELECT * FROM products WHERE (metadata->'specs'->>'ram')::int > 8;
SELECT * FROM products WHERE metadata @> '{"tags": ["gaming"]}';  -- contains

-- Index on JSONB
CREATE INDEX idx_products_metadata ON products USING GIN(metadata);
CREATE INDEX idx_products_brand ON products((metadata->>'brand'));

-- Update JSONB
UPDATE products
SET metadata = jsonb_set(metadata, '{specs,ram}', '32')
WHERE id = 1;

-- Python (asyncpg)
import json
product = await conn.fetchrow(
    "SELECT * FROM products WHERE metadata @> $1",
    json.dumps({"brand": "Dell"})
)
```
