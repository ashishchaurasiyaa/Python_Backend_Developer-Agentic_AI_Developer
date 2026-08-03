# PostgreSQL — Window Functions, CTEs, Full-Text Search

## Quick Concepts
- **Window Function** = aggregate function jo rows DELETE nahi karta — har row ka result alag
- **`PARTITION BY`** = window ke andar groups banao
- **`ORDER BY` in window** = order define karo (ROW_NUMBER, RANK ke liye)
- **Frame clause** = `ROWS BETWEEN` — window ki boundary define karo
- **CTE (`WITH`)** = temporary named result set — complex query ko readable banao
- **Recursive CTE** = tree/hierarchy traverse karo (categories, org chart)
- **Full-Text Search** = `tsvector` (indexed document) + `tsquery` (search query)

---

## Interview Questions & Answers

### Q1: Window Functions kya hain? GROUP BY se kaise alag hain?

**Answer:**
```sql
-- GROUP BY — rows collapse ho jaati hain (1 row per group)
SELECT department, AVG(salary)
FROM employees
GROUP BY department;
-- Result: 3 rows (one per dept)

-- Window Function — rows remain, aggregate ADD hota hai
SELECT
    name,
    department,
    salary,
    AVG(salary) OVER (PARTITION BY department) AS dept_avg,
    salary - AVG(salary) OVER (PARTITION BY department)  AS diff_from_avg
FROM employees;
-- Result: ALL rows, har row ke saath dept_avg column

-- INTERVIEW: Window function ka syntax?
-- function() OVER (
--   [PARTITION BY column]  -- groups (optional)
--   [ORDER BY column]      -- ordering within window
--   [frame_clause]         -- ROWS/RANGE BETWEEN
-- )
```

---

### Q2: ROW_NUMBER, RANK, DENSE_RANK, NTILE kab use karte hain?

**Answer:**
```sql
-- ─── ROW_NUMBER — always unique sequential number ───
SELECT
    name,
    department,
    salary,
    ROW_NUMBER() OVER (PARTITION BY department ORDER BY salary DESC) AS rn
FROM employees;
-- Each dept mein: 1, 2, 3, 4... (ties ke baad bhi unique)

-- ─── RANK — ties ke baad gap ───
SELECT
    name, salary,
    RANK() OVER (ORDER BY salary DESC) AS rank
FROM employees;
-- Ties: 1, 1, 3, 4 (gap after tie)

-- ─── DENSE_RANK — ties ke baad no gap ───
SELECT
    name, salary,
    DENSE_RANK() OVER (ORDER BY salary DESC) AS dense_rank
FROM employees;
-- Ties: 1, 1, 2, 3 (no gap)

-- ─── NTILE — n buckets mein divide karo ───
SELECT
    name, salary,
    NTILE(4) OVER (ORDER BY salary DESC) AS quartile
FROM employees;
-- 1=top 25%, 2=next 25%, etc.

-- ─── Real use case: Top 3 posts per category ───
SELECT * FROM (
    SELECT
        p.id, p.title, p.views_count,
        c.name AS category,
        ROW_NUMBER() OVER (
            PARTITION BY p.category_id
            ORDER BY p.views_count DESC
        ) AS rn
    FROM posts p
    JOIN categories c ON c.id = p.category_id
    WHERE p.status = 'published'
) ranked
WHERE rn <= 3;  -- sirf top 3 per category
```

---

### Q3: LAG, LEAD, FIRST_VALUE, LAST_VALUE — time-series analysis?

**Answer:**
```sql
-- ─── LAG — previous row ki value ───
-- Use: month-over-month comparison, delta calculation

SELECT
    order_date,
    revenue,
    LAG(revenue, 1, 0) OVER (ORDER BY order_date) AS prev_month_revenue,
    revenue - LAG(revenue, 1, 0) OVER (ORDER BY order_date) AS mom_change,
    ROUND(
        (revenue - LAG(revenue, 1, 0) OVER (ORDER BY order_date))::numeric
        / NULLIF(LAG(revenue, 1, 0) OVER (ORDER BY order_date), 0) * 100, 2
    ) AS mom_pct_change
FROM monthly_revenue
ORDER BY order_date;

-- ─── LEAD — next row ki value ───
SELECT
    user_id,
    event_type,
    event_time,
    LEAD(event_type) OVER (PARTITION BY user_id ORDER BY event_time) AS next_event,
    LEAD(event_time) OVER (PARTITION BY user_id ORDER BY event_time) AS next_event_time
FROM user_events;

-- ─── Running total (cumulative sum) ───
SELECT
    order_date,
    amount,
    SUM(amount) OVER (ORDER BY order_date ROWS UNBOUNDED PRECEDING) AS running_total,
    SUM(amount) OVER (
        ORDER BY order_date
        ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
    ) AS rolling_7day_total
FROM orders;

-- ─── FIRST_VALUE / LAST_VALUE ───
SELECT
    name, department, salary,
    FIRST_VALUE(name) OVER (PARTITION BY department ORDER BY salary DESC) AS highest_earner,
    LAST_VALUE(name)  OVER (
        PARTITION BY department ORDER BY salary DESC
        ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING
    ) AS lowest_earner
FROM employees;
-- Note: LAST_VALUE ke liye ROWS BETWEEN ... UNBOUNDED FOLLOWING jaruri hai
```

---

### Q4: CTEs (`WITH` clause) kab use karte hain?

**Answer:**
```sql
-- ─── Basic CTE — complex query readable banao ───
WITH
active_users AS (
    SELECT id, email, created_at
    FROM users
    WHERE is_active = TRUE AND deleted_at IS NULL
),
user_post_counts AS (
    SELECT user_id, COUNT(*) AS post_count
    FROM posts
    WHERE status = 'published'
    GROUP BY user_id
),
user_stats AS (
    SELECT
        u.id, u.email,
        COALESCE(pc.post_count, 0) AS posts,
        u.created_at
    FROM active_users u
    LEFT JOIN user_post_counts pc ON pc.user_id = u.id
)
SELECT *
FROM user_stats
WHERE posts > 5
ORDER BY posts DESC;

-- ─── CTE vs Subquery — kab kya? ───
-- Subquery: once use karna ho
-- CTE: same result multiple baar use karna ho
--      recursive query
--      readability improve karna ho

-- ─── Recursive CTE — tree/hierarchy ───
-- Use: category tree, org chart, file system, social follows
WITH RECURSIVE category_tree AS (
    -- Base case: root categories (no parent)
    SELECT id, name, parent_id, 0 AS depth, name::TEXT AS path
    FROM categories
    WHERE parent_id IS NULL

    UNION ALL

    -- Recursive case: children
    SELECT
        c.id, c.name, c.parent_id,
        ct.depth + 1,
        (ct.path || ' > ' || c.name)::TEXT
    FROM categories c
    JOIN category_tree ct ON ct.id = c.parent_id
    WHERE ct.depth < 10  -- prevent infinite loop
)
SELECT * FROM category_tree ORDER BY path;

-- ─── CTE for UPDATE/DELETE ───
WITH posts_to_archive AS (
    SELECT id FROM posts
    WHERE status = 'published'
      AND published_at < NOW() - INTERVAL '2 years'
)
UPDATE posts
SET status = 'archived'
WHERE id IN (SELECT id FROM posts_to_archive);
```

---

### Q5: PostgreSQL Full-Text Search kaise karte hain?

**Answer:**
```sql
-- ─── Basic FTS ───
-- tsvector = preprocessed document (stems, stop words removed)
-- tsquery  = search query

SELECT title, content
FROM posts
WHERE to_tsvector('english', title || ' ' || content)
   @@ to_tsquery('english', 'django & orm & optimization')
ORDER BY ts_rank(
    to_tsvector('english', title || ' ' || content),
    to_tsquery('english', 'django & orm & optimization')
) DESC;

-- ─── Performance: Stored tsvector column + GIN index ───
ALTER TABLE posts ADD COLUMN search_vector tsvector;

-- Auto-update search_vector trigger
CREATE OR REPLACE FUNCTION update_search_vector()
RETURNS TRIGGER AS $$
BEGIN
    NEW.search_vector := to_tsvector(
        'english',
        COALESCE(NEW.title, '') || ' ' ||
        COALESCE(NEW.excerpt, '') || ' ' ||
        COALESCE(NEW.content, '')
    );
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER posts_search_vector_update
    BEFORE INSERT OR UPDATE ON posts
    FOR EACH ROW EXECUTE FUNCTION update_search_vector();

-- GIN index on tsvector
CREATE INDEX idx_posts_search ON posts USING gin(search_vector);

-- Fast search with index
SELECT id, title,
    ts_rank(search_vector, query) AS rank,
    ts_headline('english', title, query, 'MaxWords=15, MinWords=10') AS snippet
FROM posts, to_tsquery('english', 'django:* | fastapi:*') AS query
WHERE search_vector @@ query
ORDER BY rank DESC
LIMIT 20;

-- ─── pg_trgm — fuzzy/partial search ───
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE INDEX idx_posts_title_trgm ON posts USING gin(title gin_trgm_ops);

-- Similarity search (typos, partial match)
SELECT title, similarity(title, 'dajngo') AS sim
FROM posts
WHERE title % 'dajngo'  -- similarity threshold (default 0.3)
ORDER BY sim DESC;

-- LIKE with index (pg_trgm makes LIKE fast)
SELECT * FROM posts WHERE title ILIKE '%django orm%';
-- With gin_trgm_ops index, this is fast!

-- ─── Python (asyncpg / SQLAlchemy) ───
from sqlalchemy import text

async def search_posts(session, query: str):
    result = await session.execute(
        text("""
            SELECT id, title,
                   ts_rank(search_vector, plainto_tsquery('english', :q)) AS rank,
                   ts_headline('english', excerpt,
                       plainto_tsquery('english', :q)) AS snippet
            FROM posts
            WHERE search_vector @@ plainto_tsquery('english', :q)
            ORDER BY rank DESC
            LIMIT 20
        """),
        {"q": query}
    )
    return result.mappings().all()
```

---

### Q6: Table Partitioning kab use karte hain?

**Answer:**
```sql
-- INTERVIEW: Partitioning kyu?
-- Large tables (100M+ rows) mein queries slow hoti hain
-- Partition pruning = sirf relevant partition scan karo
-- Old data archive/drop karna easy

-- ─── RANGE Partitioning (time-based — most common) ───
CREATE TABLE events (
    id         BIGSERIAL,
    event_type VARCHAR(50),
    user_id    INT,
    created_at TIMESTAMPTZ NOT NULL
) PARTITION BY RANGE (created_at);

-- Monthly partitions
CREATE TABLE events_2024_01 PARTITION OF events
    FOR VALUES FROM ('2024-01-01') TO ('2024-02-01');
CREATE TABLE events_2024_02 PARTITION OF events
    FOR VALUES FROM ('2024-02-01') TO ('2024-03-01');

-- pg_partman extension se automatic partition creation
-- SELECT partman.create_parent('public.events', 'created_at', 'native', 'monthly');

-- ─── LIST Partitioning (category-based) ───
CREATE TABLE orders (
    id     BIGSERIAL,
    status VARCHAR(20) NOT NULL,
    amount DECIMAL(10,2)
) PARTITION BY LIST (status);

CREATE TABLE orders_pending   PARTITION OF orders FOR VALUES IN ('pending');
CREATE TABLE orders_completed PARTITION OF orders FOR VALUES IN ('completed', 'shipped');
CREATE TABLE orders_cancelled PARTITION OF orders FOR VALUES IN ('cancelled', 'refunded');

-- ─── HASH Partitioning (distribute evenly) ───
CREATE TABLE user_sessions (
    id      BIGSERIAL,
    user_id INT NOT NULL,
    data    JSONB
) PARTITION BY HASH (user_id);

CREATE TABLE user_sessions_0 PARTITION OF user_sessions
    FOR VALUES WITH (MODULUS 4, REMAINDER 0);
CREATE TABLE user_sessions_1 PARTITION OF user_sessions
    FOR VALUES WITH (MODULUS 4, REMAINDER 1);
-- ... etc

-- INTERVIEW: Partition pruning kaise verify karo?
EXPLAIN (ANALYZE, BUFFERS)
SELECT * FROM events WHERE created_at >= '2024-01-01' AND created_at < '2024-02-01';
-- Output should show: "Partitions scanned: 1" (only events_2024_01)
```

---

## Bonus 1: GROUPING SETS / ROLLUP / CUBE — multi-level aggregation ek query me

"Region-wise total, product-wise total, AUR grand total — teeno ek saath" — teen alag GROUP BY + UNION ALL ki jagah:

```sql
-- GROUPING SETS: exactly jo combinations chahiye
SELECT region, product, SUM(amount) AS total
FROM sales
GROUP BY GROUPING SETS ((region), (product), ());   -- () = grand total row

-- ROLLUP: hierarchy ke saare levels — (region, product) → (region) → ()
SELECT region, product, SUM(amount)
FROM sales GROUP BY ROLLUP (region, product);
-- Report: har region ke andar product totals + region subtotal + grand total

-- CUBE: SAB combinations (2^n) — cross-tab analysis
SELECT region, product, SUM(amount)
FROM sales GROUP BY CUBE (region, product);

-- Subtotal rows me dono NULL dikhte hain — asli NULL se differentiate:
SELECT region, product, SUM(amount),
       GROUPING(region) AS is_region_subtotal    -- 1 = yeh subtotal row hai
FROM sales GROUP BY ROLLUP (region, product);
```

**Interview line:** *"ROLLUP hierarchical subtotals ke liye (region→product report), CUBE har combination ke liye, GROUPING SETS jab custom combinations chahiye. Ek hi scan me saare levels — UNION ALL wale version se N-times faster, aur `GROUPING()` se subtotal rows identify hoti hain."* (MySQL 8 me sirf `WITH ROLLUP` syntax hai; GROUPING SETS/CUBE PostgreSQL/standard.)

---

## Bonus 2: LATERAL Join — "har row ke liye correlated subquery, FROM me"

Classic problem: **"har customer ke last 3 orders"** — window function se ho jata hai, par LATERAL zyada natural aur often faster hai:

```sql
SELECT c.name, o.*
FROM customers c
CROSS JOIN LATERAL (
    SELECT id, amount, created_at
    FROM orders
    WHERE orders.customer_id = c.id      -- ← bahar wali table ko reference! yehi LATERAL hai
    ORDER BY created_at DESC
    LIMIT 3
) o;
-- Without LATERAL yeh subquery c.id ko dekh hi nahi sakti thi

-- LEFT JOIN LATERAL ... ON true  → jinke orders nahi unko bhi rakho
SELECT c.name, o.amount
FROM customers c
LEFT JOIN LATERAL (
    SELECT amount FROM orders WHERE customer_id = c.id
    ORDER BY created_at DESC LIMIT 1
) o ON true;
```

**Kab LATERAL vs window function:** top-N-per-group me agar N chhota hai aur `(customer_id, created_at)` pe index hai to LATERAL har customer ke liye index se seedha N rows uthata hai (nested loop); window function poori table scan karke ROW_NUMBER assign karta hai. Chhota N + selective outer = LATERAL jeeta; poore dataset ka ranking chahiye = window function.

---

## Summary

| Function | Use Case |
|---------|---------|
| `ROW_NUMBER()` | Pagination, deduplication, top-N per group |
| `RANK()` / `DENSE_RANK()` | Rankings with tie handling |
| `LAG()` / `LEAD()` | Period-over-period comparison |
| `SUM() OVER (ORDER BY...)` | Running totals, moving averages |
| Recursive CTE | Tree traversal, org charts, category hierarchy |
| `tsvector` + `tsquery` | Full-text search with relevance ranking |
| `pg_trgm` | Fuzzy search, LIKE with index |
| Partitioning | 100M+ row tables, time-series, archival |
