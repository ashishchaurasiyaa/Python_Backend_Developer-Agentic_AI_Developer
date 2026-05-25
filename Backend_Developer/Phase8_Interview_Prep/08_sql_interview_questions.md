# SQL Interview Questions — Backend Engineer Edition

> Senior backend roles need solid SQL. This pack covers the actual queries asked in interviews + production patterns.

**Reference schema** used throughout:
```sql
CREATE TABLE users (
    id           BIGSERIAL PRIMARY KEY,
    name         TEXT,
    email        TEXT UNIQUE,
    created_at   TIMESTAMPTZ DEFAULT now(),
    country      TEXT
);

CREATE TABLE orders (
    id           BIGSERIAL PRIMARY KEY,
    user_id      BIGINT REFERENCES users(id),
    amount       NUMERIC(10,2),
    status       TEXT,                  -- 'pending', 'paid', 'cancelled'
    created_at   TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE products (
    id           BIGSERIAL PRIMARY KEY,
    name         TEXT,
    price        NUMERIC(10,2),
    category_id  BIGINT
);

CREATE TABLE order_items (
    order_id     BIGINT REFERENCES orders(id),
    product_id   BIGINT REFERENCES products(id),
    quantity     INT,
    unit_price   NUMERIC(10,2),
    PRIMARY KEY (order_id, product_id)
);
```

---

## SECTION 1 — JOIN MASTERY

### Q1. Difference between INNER, LEFT, RIGHT, FULL?

```sql
-- INNER: only rows matching in BOTH tables
SELECT u.name, o.amount
FROM users u
INNER JOIN orders o ON o.user_id = u.id;

-- LEFT: all from users; NULL where no order
SELECT u.name, o.amount
FROM users u
LEFT JOIN orders o ON o.user_id = u.id;

-- RIGHT: mirror of LEFT (rarely used; swap tables instead)

-- FULL: union of LEFT + RIGHT
SELECT u.name, o.amount
FROM users u
FULL JOIN orders o ON o.user_id = u.id;
```

**Mental model:**
```
LEFT JOIN:    [A's all] + matched B (NULL else)
INNER JOIN:   intersection of A and B
FULL JOIN:    union (NULL where no match either side)
```

---

### Q2. Find users with NO orders (anti-join)

```sql
-- LEFT JOIN + NULL filter (classic)
SELECT u.*
FROM users u
LEFT JOIN orders o ON o.user_id = u.id
WHERE o.id IS NULL;

-- NOT EXISTS (often faster, planner-friendlier)
SELECT u.*
FROM users u
WHERE NOT EXISTS (
    SELECT 1 FROM orders o WHERE o.user_id = u.id
);

-- NOT IN (PITFALL: if subquery returns NULL, NOT IN returns no rows!)
SELECT u.*
FROM users u
WHERE u.id NOT IN (SELECT user_id FROM orders);  -- broken if user_id has NULL
```

**Performance:** `NOT EXISTS` ≈ `LEFT JOIN ... IS NULL` ≈ `EXCEPT`. Avoid `NOT IN` with nullable columns.

---

### Q3. Self-join — employees and managers

```sql
CREATE TABLE employees (
    id INT PRIMARY KEY,
    name TEXT,
    manager_id INT REFERENCES employees(id)
);

-- Each employee's manager name
SELECT e.name AS employee, m.name AS manager
FROM employees e
LEFT JOIN employees m ON e.manager_id = m.id;
```

---

### Q4. Find duplicate emails

```sql
SELECT email, COUNT(*) AS n
FROM users
GROUP BY email
HAVING COUNT(*) > 1;

-- With row details
SELECT *
FROM users
WHERE email IN (
    SELECT email FROM users GROUP BY email HAVING COUNT(*) > 1
);
```

---

### Q5. Second highest salary (LeetCode classic)

```sql
-- Method 1: subquery
SELECT MAX(salary) AS second_highest
FROM employees
WHERE salary < (SELECT MAX(salary) FROM employees);

-- Method 2: window function (handles ties cleanly)
SELECT DISTINCT salary
FROM (
    SELECT salary, DENSE_RANK() OVER (ORDER BY salary DESC) AS rk
    FROM employees
) t
WHERE rk = 2;

-- Method 3: OFFSET (cleanest in PG)
SELECT salary FROM employees
ORDER BY salary DESC
LIMIT 1 OFFSET 1;
```

---

## SECTION 2 — WINDOW FUNCTIONS

### Q6. ROW_NUMBER vs RANK vs DENSE_RANK

```sql
-- Salaries: 100, 100, 90, 80
-- ROW_NUMBER:  1, 2, 3, 4   (always unique)
-- RANK:        1, 1, 3, 4   (gaps after ties)
-- DENSE_RANK:  1, 1, 2, 3   (no gaps)

SELECT name, salary,
    ROW_NUMBER() OVER (ORDER BY salary DESC) AS rn,
    RANK()       OVER (ORDER BY salary DESC) AS rk,
    DENSE_RANK() OVER (ORDER BY salary DESC) AS drk
FROM employees;
```

---

### Q7. Top-N per group (extremely common)

```sql
-- Top 3 highest-paid employees per department
SELECT *
FROM (
    SELECT e.*,
        ROW_NUMBER() OVER (
            PARTITION BY department_id
            ORDER BY salary DESC
        ) AS rn
    FROM employees e
) t
WHERE rn <= 3;
```

**Variants:**
- Top earner only per dept: `WHERE rn = 1`.
- Use `RANK()` if you want ties.

---

### Q8. Running total / cumulative sum

```sql
SELECT order_date, amount,
    SUM(amount) OVER (
        ORDER BY order_date
        ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
    ) AS running_total
FROM orders;

-- Per user
SELECT order_date, amount,
    SUM(amount) OVER (
        PARTITION BY user_id
        ORDER BY order_date
    ) AS user_running_total
FROM orders;
```

---

### Q9. LAG and LEAD — month-over-month change

```sql
WITH monthly AS (
    SELECT date_trunc('month', created_at) AS m, SUM(amount) AS revenue
    FROM orders
    GROUP BY m
)
SELECT m, revenue,
    LAG(revenue) OVER (ORDER BY m) AS prev_month,
    revenue - LAG(revenue) OVER (ORDER BY m) AS delta,
    100.0 * (revenue - LAG(revenue) OVER (ORDER BY m))
        / NULLIF(LAG(revenue) OVER (ORDER BY m), 0) AS pct_change
FROM monthly
ORDER BY m;
```

---

### Q10. Median in SQL

```sql
-- Postgres has built-in
SELECT percentile_cont(0.5) WITHIN GROUP (ORDER BY salary) AS median
FROM employees;

-- Generic SQL (no PERCENTILE_CONT)
SELECT AVG(salary) AS median
FROM (
    SELECT salary,
        ROW_NUMBER() OVER (ORDER BY salary) AS rn,
        COUNT(*) OVER () AS total
    FROM employees
) t
WHERE rn IN ((total+1)/2, (total+2)/2);
```

---

### Q11. Sessionization (consecutive events within 30min)

```sql
WITH events_marked AS (
    SELECT user_id, event_time,
        CASE
            WHEN event_time - LAG(event_time) OVER (PARTITION BY user_id ORDER BY event_time)
                 > interval '30 minutes' THEN 1
            ELSE 0
        END AS new_session
    FROM events
),
sessions AS (
    SELECT *, SUM(new_session) OVER (PARTITION BY user_id ORDER BY event_time) AS session_id
    FROM events_marked
)
SELECT user_id, session_id, MIN(event_time) AS start, MAX(event_time) AS end_t,
       COUNT(*) AS events_count
FROM sessions
GROUP BY user_id, session_id;
```

**This pattern shows up in:** analytics, fraud detection, behavior tracking.

---

## SECTION 3 — AGGREGATION TRICKS

### Q12. WHERE vs HAVING

```sql
-- WHERE filters rows BEFORE aggregation
-- HAVING filters AFTER aggregation

SELECT country, COUNT(*) AS n_users
FROM users
WHERE created_at > '2024-01-01'   -- per-row filter
GROUP BY country
HAVING COUNT(*) > 100;              -- group-level filter
```

---

### Q13. Conditional aggregation (pivot-lite)

```sql
SELECT
    user_id,
    COUNT(*) FILTER (WHERE status = 'paid')      AS paid_count,
    COUNT(*) FILTER (WHERE status = 'cancelled') AS cancelled_count,
    SUM(amount) FILTER (WHERE status = 'paid')   AS paid_revenue
FROM orders
GROUP BY user_id;

-- Pre-Postgres SQL: use CASE
SELECT
    user_id,
    SUM(CASE WHEN status = 'paid'      THEN 1 ELSE 0 END) AS paid_count,
    SUM(CASE WHEN status = 'cancelled' THEN 1 ELSE 0 END) AS cancelled_count
FROM orders
GROUP BY user_id;
```

---

### Q14. GROUPING SETS / ROLLUP / CUBE

```sql
-- Multiple levels of aggregation in one query
SELECT country, status, COUNT(*) AS n
FROM users u
JOIN orders o ON o.user_id = u.id
GROUP BY GROUPING SETS (
    (country, status),
    (country),
    (status),
    ()                -- grand total
);

-- ROLLUP: hierarchical (country → all)
GROUP BY ROLLUP (country, status);

-- CUBE: all combinations
GROUP BY CUBE (country, status);
```

---

### Q15. Average without NULLs (gotcha)

```sql
SELECT AVG(score) FROM students;  -- AVG ignores NULL automatically
SELECT AVG(COALESCE(score, 0)) FROM students;  -- treats NULL as 0
-- These give DIFFERENT answers!
```

---

## SECTION 4 — INDEXING & PERFORMANCE

### Q16. When does an index get used?

Will use index:
```sql
WHERE id = 123                -- equality
WHERE id > 100                -- range
WHERE name LIKE 'alice%'      -- prefix LIKE
WHERE email IN ('a', 'b')     -- IN list
ORDER BY id LIMIT 10          -- ordered access
```

Will NOT use index:
```sql
WHERE LOWER(email) = 'alice@x.com'   -- function on column
WHERE id + 1 = 124                   -- expression on column
WHERE email LIKE '%alice%'           -- leading wildcard
WHERE name <> 'alice'                -- negation
```

**Fix function-on-column:** Functional index.
```sql
CREATE INDEX idx_users_email_lower ON users (LOWER(email));
```

---

### Q17. Composite index — column order matters

```sql
CREATE INDEX idx_orders_user_date ON orders (user_id, created_at);

-- Uses index (left prefix)
WHERE user_id = 1;
WHERE user_id = 1 AND created_at > '2024-01-01';

-- Does NOT use index (skipping leftmost)
WHERE created_at > '2024-01-01';
```

**Rule:** Multi-column index = "phone book sorted by last name, then first name". You can't find "all people named John" without knowing the last name first.

---

### Q18. Covering index (include columns)

```sql
-- Postgres
CREATE INDEX idx_orders_user_date_amount
    ON orders (user_id, created_at)
    INCLUDE (amount, status);

-- Query can be answered entirely from index (no heap lookup)
SELECT amount, status FROM orders
WHERE user_id = 1 AND created_at > '2024-01-01';
```

**Why:** Cuts random disk IO. Trade-off: bigger index, slower writes.

---

### Q19. EXPLAIN ANALYZE — read the output

```sql
EXPLAIN ANALYZE
SELECT * FROM orders WHERE user_id = 1;
```

```
Seq Scan on orders  (cost=0.00..123.45 rows=10 width=64) (actual time=0.5..15.2 rows=8 loops=1)
  Filter: (user_id = 1)
  Rows Removed by Filter: 99992
Planning Time: 0.123 ms
Execution Time: 15.4 ms
```

**Red flags:**
- `Seq Scan` on big table when index expected.
- `actual rows` ≫ `rows` estimate → run `ANALYZE`.
- Nested Loop with many outer rows → likely missing index.

---

### Q20. N+1 query problem — diagnose and fix

```python
# ❌ N+1 — Django
for order in Order.objects.all():
    print(order.user.name)  # extra query per order

# ✓ select_related (JOIN) for FK
for order in Order.objects.select_related('user'):
    print(order.user.name)

# ✓ prefetch_related (separate query, joined in Python) for M2M / reverse
for user in User.objects.prefetch_related('orders'):
    for o in user.orders.all():
        ...
```

In SQLAlchemy: `joinedload`, `selectinload`.

**Detect:** `django-debug-toolbar`, `pyinstrument`, query count assertions in tests.

---

## SECTION 5 — TRANSACTIONS & LOCKING

### Q21. ACID properties — examples

```
A (Atomic):     Transaction all-or-nothing.
                 BEGIN; UPDATE A; UPDATE B; COMMIT;
                 If B fails, A is rolled back.

C (Consistent): Constraints upheld (FK, UNIQUE, CHECK).

I (Isolated):   Concurrent txns don't interfere (depends on isolation level).

D (Durable):    Committed = on disk = survives crash.
```

---

### Q22. Isolation levels

| Level | Dirty Read | Non-Repeatable | Phantom | Default in |
|---|---|---|---|---|
| Read Uncommitted | ✓ possible | ✓ | ✓ | (rare) |
| Read Committed | ✗ | ✓ possible | ✓ | Postgres, Oracle |
| Repeatable Read | ✗ | ✗ | ✓ in standard, ✗ in PG | MySQL InnoDB |
| Serializable | ✗ | ✗ | ✗ | (slow) |

**Anomalies:**
- Dirty read: see uncommitted data.
- Non-repeatable: same row, two different values within a txn.
- Phantom: same query, different number of rows.

---

### Q23. SELECT ... FOR UPDATE

```sql
BEGIN;
SELECT * FROM accounts WHERE id = 1 FOR UPDATE;   -- lock row
UPDATE accounts SET balance = balance - 100 WHERE id = 1;
COMMIT;
```

**Other variants:**
- `FOR NO KEY UPDATE` — weaker, allows concurrent reads.
- `FOR SHARE` — shared lock, blocks `FOR UPDATE`.
- `SKIP LOCKED` — for queue patterns, picks the next available row.
- `NOWAIT` — fail fast instead of blocking.

---

### Q24. Deadlock — recognize and resolve

```sql
-- Session A
BEGIN; UPDATE a SET x=1 WHERE id=1;   -- locks row 1
       UPDATE a SET x=1 WHERE id=2;   -- wait for B
-- Session B
BEGIN; UPDATE a SET x=2 WHERE id=2;   -- locks row 2
       UPDATE a SET x=2 WHERE id=1;   -- wait for A → DEADLOCK
```

**DB detects, kills one. Postgres returns error 40P01.**

**Prevent:** Always lock rows in the same order. Use shorter txns. `FOR UPDATE SKIP LOCKED` for queues.

---

### Q25. Optimistic locking (without FOR UPDATE)

```sql
-- Add version column
ALTER TABLE accounts ADD COLUMN version INT DEFAULT 0;

-- Read
SELECT id, balance, version FROM accounts WHERE id = 1;
-- (got balance=100, version=5)

-- Conditional update
UPDATE accounts
SET balance = 90, version = version + 1
WHERE id = 1 AND version = 5;
-- If 0 rows updated → someone else changed it. Retry.
```

**Use:** Low-contention reads, high write conflict. Avoids locking.

---

## SECTION 6 — CTEs & RECURSIVE

### Q26. CTE vs subquery vs temp table

```sql
-- CTE (Common Table Expression)
WITH active_users AS (
    SELECT * FROM users WHERE deleted_at IS NULL
)
SELECT * FROM active_users WHERE country = 'IN';
```

**When CTE:**
- Recursive queries.
- Readability (avoid 3-level nested subqueries).
- Reuse in same query.

**Postgres 12+:** CTE no longer always materialized → planner inlines unless `MATERIALIZED` keyword.

---

### Q27. Recursive CTE — org hierarchy

```sql
WITH RECURSIVE reports AS (
    -- Anchor: top manager
    SELECT id, name, manager_id, 1 AS level
    FROM employees
    WHERE manager_id IS NULL

    UNION ALL

    -- Recursive: people who report up
    SELECT e.id, e.name, e.manager_id, r.level + 1
    FROM employees e
    JOIN reports r ON e.manager_id = r.id
)
SELECT * FROM reports ORDER BY level, name;
```

**Other uses:** Tree traversal, graph reachability, generating series.

---

### Q28. Generate series of dates (Postgres)

```sql
SELECT date_trunc('day', dd)::date AS d
FROM generate_series('2024-01-01'::date, '2024-12-31'::date, '1 day') AS dd;

-- Use for time-series gap filling
WITH all_days AS (
    SELECT generate_series('2024-01-01'::date, current_date, '1 day') AS d
)
SELECT d.d, COALESCE(o.cnt, 0) AS orders_count
FROM all_days d
LEFT JOIN (
    SELECT date_trunc('day', created_at)::date AS d, COUNT(*) AS cnt
    FROM orders
    GROUP BY 1
) o ON o.d = d.d
ORDER BY d.d;
```

---

## SECTION 7 — UPSERT & MERGE

### Q29. UPSERT in Postgres

```sql
INSERT INTO users (id, name, email)
VALUES (1, 'Alice', 'alice@x.com')
ON CONFLICT (id)
DO UPDATE SET name = EXCLUDED.name, email = EXCLUDED.email;

-- Only update if value changed (avoid unnecessary writes)
ON CONFLICT (id) DO UPDATE
    SET name = EXCLUDED.name
    WHERE users.name IS DISTINCT FROM EXCLUDED.name;

-- Do nothing if exists (idempotent insert)
ON CONFLICT (id) DO NOTHING;
```

---

### Q30. MySQL UPSERT

```sql
INSERT INTO users (id, name) VALUES (1, 'Alice')
ON DUPLICATE KEY UPDATE name = VALUES(name);
```

---

### Q31. MERGE (Postgres 15+, SQL Server, Oracle)

```sql
MERGE INTO target t
USING source s ON t.id = s.id
WHEN MATCHED THEN
    UPDATE SET t.name = s.name
WHEN NOT MATCHED THEN
    INSERT (id, name) VALUES (s.id, s.name);
```

**Watch out:** Standard MERGE doesn't have INSERT ... ON CONFLICT atomicity. Concurrent MERGEs can fail. Use `INSERT ... ON CONFLICT` in Postgres if you can.

---

## SECTION 8 — POSTGRES SPECIFIC

### Q32. JSONB operations

```sql
-- Stored: {"name": "alice", "address": {"city": "Pune"}, "tags": ["vip"]}

-- Access
SELECT data->>'name' FROM users;          -- "alice" (text)
SELECT data->'address'->>'city' FROM users; -- "Pune"

-- Containment
SELECT * FROM users WHERE data @> '{"tags": ["vip"]}';

-- Index for containment queries
CREATE INDEX ON users USING GIN (data jsonb_path_ops);

-- Update key
UPDATE users SET data = jsonb_set(data, '{address,city}', '"Mumbai"');

-- Delete key
UPDATE users SET data = data - 'address';
```

---

### Q33. Array operations

```sql
-- Column type: tags TEXT[]

SELECT * FROM users WHERE 'vip' = ANY(tags);
SELECT * FROM users WHERE tags @> ARRAY['vip', 'paid'];   -- contains both
SELECT * FROM users WHERE tags && ARRAY['vip', 'free'];   -- any overlap

-- Aggregate
SELECT array_agg(name ORDER BY created_at) FROM users WHERE country = 'IN';

-- Unnest
SELECT unnest(tags) FROM users;
```

---

### Q34. Distinct ON

```sql
-- Most recent order per user
SELECT DISTINCT ON (user_id)
    user_id, created_at, amount
FROM orders
ORDER BY user_id, created_at DESC;
```

Postgres-specific shortcut. ORDER BY must start with the DISTINCT columns.

---

### Q35. Partitioning

```sql
-- Range partition by month
CREATE TABLE orders (
    id BIGSERIAL,
    created_at TIMESTAMPTZ NOT NULL,
    ...
) PARTITION BY RANGE (created_at);

CREATE TABLE orders_2024_01 PARTITION OF orders
    FOR VALUES FROM ('2024-01-01') TO ('2024-02-01');

CREATE TABLE orders_2024_02 PARTITION OF orders
    FOR VALUES FROM ('2024-02-01') TO ('2024-03-01');
```

**When:** Tables >100M rows, time-based access patterns. Partition pruning massively speeds up queries.

---

## SECTION 9 — REAL INTERVIEW PUZZLES

### Q36. Consecutive 3+ days revenue > 100

```sql
WITH daily AS (
    SELECT date_trunc('day', created_at)::date AS d, SUM(amount) AS rev
    FROM orders
    GROUP BY 1
),
above_100 AS (
    SELECT d, rev,
        d - (ROW_NUMBER() OVER (ORDER BY d))::int AS grp
    FROM daily
    WHERE rev > 100
)
SELECT MIN(d) AS start_d, MAX(d) AS end_d, COUNT(*) AS consec_days
FROM above_100
GROUP BY grp
HAVING COUNT(*) >= 3;
```

**Trick:** Subtract row number from date → consecutive dates share same `grp`.

---

### Q37. Find seats together (3 consecutive empty)

```sql
-- Cinema seats: id (1-100), is_empty boolean
WITH e AS (
    SELECT id, is_empty,
        id - ROW_NUMBER() OVER (PARTITION BY is_empty ORDER BY id) AS grp
    FROM seats
)
SELECT MIN(id) AS start, MAX(id) AS end
FROM e
WHERE is_empty = TRUE
GROUP BY grp
HAVING COUNT(*) >= 3;
```

---

### Q38. Rolling 7-day average

```sql
SELECT day, daily_revenue,
    AVG(daily_revenue) OVER (
        ORDER BY day
        ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
    ) AS rolling_7d
FROM (
    SELECT date_trunc('day', created_at)::date AS day, SUM(amount) AS daily_revenue
    FROM orders
    GROUP BY 1
) t
ORDER BY day;
```

---

### Q39. Department with highest avg salary (not employees, but dept)

```sql
SELECT department_id
FROM employees
GROUP BY department_id
ORDER BY AVG(salary) DESC
LIMIT 1;

-- With ties
WITH dept_avg AS (
    SELECT department_id, AVG(salary) AS avg_sal
    FROM employees
    GROUP BY department_id
)
SELECT department_id FROM dept_avg
WHERE avg_sal = (SELECT MAX(avg_sal) FROM dept_avg);
```

---

### Q40. Customer who placed orders every month in 2024

```sql
SELECT user_id
FROM orders
WHERE created_at >= '2024-01-01' AND created_at < '2025-01-01'
GROUP BY user_id
HAVING COUNT(DISTINCT date_trunc('month', created_at)) = 12;
```

---

### Q41. Find gaps in a sequence

```sql
-- IDs in invoices: 1, 2, 3, 5, 6, 9
-- Missing: 4, 7, 8

WITH all_ids AS (
    SELECT generate_series(MIN(id), MAX(id))::int AS id FROM invoices
)
SELECT a.id AS missing
FROM all_ids a
LEFT JOIN invoices i ON i.id = a.id
WHERE i.id IS NULL;

-- Or: find gap ranges
SELECT id + 1 AS gap_start,
    next_id - 1 AS gap_end
FROM (
    SELECT id, LEAD(id) OVER (ORDER BY id) AS next_id
    FROM invoices
) t
WHERE next_id > id + 1;
```

---

### Q42. Largest island of 1's in a grid stored as rows

```sql
-- grid: x, y, val (0/1) — find largest connected component of 1's
-- This is graph algorithm; SQL is painful but possible with recursive CTE
-- Honest answer: "I'd do this in app code, but I can sketch the recursive approach..."
```

If asked, sketch CTE approach but flag it's not idiomatic SQL.

---

### Q43. Group sessions by 5-minute gaps

(Already covered in Q11 — sessionization.)

---

### Q44. Max consecutive wins per player

```sql
WITH marked AS (
    SELECT player_id, game_date, result,
        ROW_NUMBER() OVER (PARTITION BY player_id ORDER BY game_date) -
        ROW_NUMBER() OVER (PARTITION BY player_id, result ORDER BY game_date)
        AS streak_grp
    FROM games
)
SELECT player_id, MAX(streak_len) AS longest_win_streak
FROM (
    SELECT player_id, streak_grp, COUNT(*) AS streak_len
    FROM marked
    WHERE result = 'win'
    GROUP BY player_id, streak_grp
) t
GROUP BY player_id;
```

---

## SECTION 10 — PRODUCTION SQL GOTCHAS

### Q45. Why is COUNT(*) slow on big tables?

Postgres counts via row scan (MVCC — visibility check per row).

Workarounds:
- `pg_class.reltuples` — approximate, fast.
- Materialized view with periodic refresh.
- Trigger-maintained counter table.

```sql
-- Approximate
SELECT reltuples::bigint FROM pg_class WHERE relname = 'orders';
```

---

### Q46. SELECT * — why it's bad

- Network bandwidth: ship unused columns.
- App parses unneeded data.
- Schema changes silently break consumers.
- Index-only scan impossible if you need columns not in index.

Always list columns explicitly.

---

### Q47. Why are dates with timezone preferred?

```sql
-- TIMESTAMP: no TZ info, ambiguous
-- TIMESTAMPTZ: stored as UTC, displayed in session TZ

CREATE TABLE events (
    happened_at TIMESTAMPTZ DEFAULT now()
);
```

**Always use TIMESTAMPTZ.** TIMESTAMP without TZ is a footgun unless you guarantee all sources are same TZ (you can't).

---

### Q48. UUID vs BIGINT primary key

| | UUID | BIGINT |
|---|---|---|
| Size | 16 bytes | 8 bytes |
| Generate | Distributed safe | Needs sequence/snowflake |
| Index locality | Random (bad) — UUID v4 | Sequential (good) |
| URL friendly | ✓ | ✗ (enumerable) |

**Modern choice:** UUID v7 (time-ordered) — best of both.

---

### Q49. SELECT ... FOR UPDATE SKIP LOCKED (job queue)

```sql
-- Worker grabs next available job
BEGIN;
SELECT * FROM jobs
WHERE status = 'pending'
ORDER BY priority DESC, created_at
LIMIT 1
FOR UPDATE SKIP LOCKED;

-- Update to 'running', commit
UPDATE jobs SET status = 'running', worker_id = 'w1' WHERE id = ?;
COMMIT;
```

This is the secret behind Postgres-as-queue patterns (e.g., `pgmq`, `pg-boss`).

---

### Q50. Pagination — keyset (cursor) vs OFFSET

```sql
-- OFFSET — bad at scale, scans skipped rows
SELECT * FROM orders ORDER BY id LIMIT 20 OFFSET 100000;

-- Keyset — uses index, constant time
SELECT * FROM orders WHERE id > $last_seen_id ORDER BY id LIMIT 20;
```

**Always prefer keyset** for infinite scroll / API pagination.

---

## SQL REVIEW CHECKLIST

Before submitting any non-trivial query, ask:

- [ ] Is there an index on the WHERE column?
- [ ] Is there a function wrapping the WHERE column (kills index)?
- [ ] Does my JOIN return more rows than expected (cartesian risk)?
- [ ] Is COUNT(*) inside a subquery (slow)?
- [ ] Are NULLs handled (`IS NULL`, `COALESCE`)?
- [ ] Have I run EXPLAIN ANALYZE on production-sized data?
- [ ] Is this query in a transaction with the right isolation level?
- [ ] What happens if 100 workers run this concurrently (locking, races)?

**Senior signal:** Answer "what's the EXPLAIN plan?" before they ask.
