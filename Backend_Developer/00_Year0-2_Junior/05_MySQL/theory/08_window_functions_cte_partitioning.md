# MySQL Window Functions, CTEs & Partitioning

## Why It Matters

MySQL only got these three features properly in **8.0** (2018) — before that,
teams wrote painful self-joins and correlated subqueries to fake ranking or
running totals. If you've mostly worked with older MySQL or came from
Postgres (which had these for years earlier), it's worth confirming you can
write them idiomatically in MySQL 8 syntax specifically, since minor syntax
differences from Postgres trip people up mid-interview.

Senior interview: "Get each customer's top 3 orders by amount, in one
query." → `ROW_NUMBER() OVER (PARTITION BY customer_id ORDER BY amount DESC)`.

---

## Window Functions (MySQL 8.0+)

```sql
-- Rank each employee's salary within their department
SELECT
    name, department, salary,
    RANK() OVER (PARTITION BY department ORDER BY salary DESC) AS dept_rank,
    ROW_NUMBER() OVER (PARTITION BY department ORDER BY salary DESC) AS row_num,
    AVG(salary) OVER (PARTITION BY department) AS dept_avg
FROM employees;
```

| Function | Behavior |
|---|---|
| `ROW_NUMBER()` | Unique sequential number, no ties (1,2,3,4) |
| `RANK()` | Ties share rank, next rank skips (1,2,2,4) |
| `DENSE_RANK()` | Ties share rank, no skip (1,2,2,3) |
| `LAG()` / `LEAD()` | Access previous/next row's value without a self-join |
| `SUM()`/`AVG()` OVER | Running total / moving average, without collapsing rows like `GROUP BY` does |

```sql
-- Top-3-per-group pattern (the classic interview question)
SELECT * FROM (
    SELECT *, ROW_NUMBER() OVER (PARTITION BY customer_id ORDER BY total DESC) AS rn
    FROM orders
) ranked
WHERE rn <= 3;
```

```sql
-- Running total (LAG for month-over-month comparison)
SELECT
    month, revenue,
    LAG(revenue) OVER (ORDER BY month) AS prev_month_revenue,
    revenue - LAG(revenue) OVER (ORDER BY month) AS mom_change
FROM monthly_revenue;
```

---

## CTEs (Common Table Expressions, MySQL 8.0+)

```sql
-- Non-recursive CTE — readability over a nested subquery
WITH high_value_customers AS (
    SELECT customer_id, SUM(total) AS lifetime_value
    FROM orders
    GROUP BY customer_id
    HAVING SUM(total) > 10000
)
SELECT c.name, h.lifetime_value
FROM high_value_customers h
JOIN customers c ON c.id = h.customer_id
ORDER BY h.lifetime_value DESC;
```

```sql
-- Recursive CTE — the interview-favorite: org chart / category tree traversal
WITH RECURSIVE org_chart AS (
    -- anchor: top-level (no manager)
    SELECT id, name, manager_id, 1 AS level
    FROM employees
    WHERE manager_id IS NULL

    UNION ALL

    -- recursive: each level joins back to the previous level's result
    SELECT e.id, e.name, e.manager_id, oc.level + 1
    FROM employees e
    JOIN org_chart oc ON e.manager_id = oc.id
)
SELECT * FROM org_chart ORDER BY level;
```

This is the standard way to query hierarchical data (category trees,
org charts, threaded comments) without a fixed-depth chain of self-joins.

---

## Partitioning (physical table partitioning, distinct from window `PARTITION BY`)

**Important distinction to say out loud in an interview:** window function
`PARTITION BY` is a query-time grouping concept; table **partitioning** below
is a physical storage concept — don't conflate the two, interviewers listen
for this.

```sql
-- RANGE partitioning — common for time-series data (partition by year)
CREATE TABLE orders (
    id INT NOT NULL,
    order_date DATE NOT NULL,
    total DECIMAL(10,2),
    PRIMARY KEY (id, order_date)
)
PARTITION BY RANGE (YEAR(order_date)) (
    PARTITION p2023 VALUES LESS THAN (2024),
    PARTITION p2024 VALUES LESS THAN (2025),
    PARTITION p2025 VALUES LESS THAN (2026),
    PARTITION p_future VALUES LESS THAN MAXVALUE
);
```

```sql
-- HASH partitioning — spread rows evenly across N partitions (no natural range key)
CREATE TABLE user_sessions (
    id INT NOT NULL,
    user_id INT NOT NULL,
    PRIMARY KEY (id, user_id)
)
PARTITION BY HASH(user_id)
PARTITIONS 8;
```

**Why partition:** queries filtering on the partition key (e.g.,
`WHERE order_date >= '2025-01-01'`) only scan matching partitions
("partition pruning") instead of the whole table — huge win on
time-series tables that grow indefinitely. Also makes dropping old data
cheap (`DROP PARTITION` vs a slow `DELETE`).

---

## Interview Q&A

**Q: `RANK()` vs `DENSE_RANK()` — when does it matter?**
A: Only when there are ties. Two employees tied for rank 1: `RANK()` gives
next employee rank 3 (skips 2); `DENSE_RANK()` gives rank 2 (no skip).
Matters for "top N" queries where skipped ranks could exclude a row you
wanted.

**Q: Why use a CTE instead of a subquery?**
A: Readability (name the intermediate result, reference it multiple times in
the outer query) and recursive CTEs enable tree/hierarchy traversal that
plain subqueries can't express at all.

**Q: Does MySQL partitioning improve JOIN performance?**
A: Only indirectly, via partition pruning reducing rows scanned before the
join — MySQL does not parallelize a single query across partitions like some
other engines. The main win is on filtered scans and fast bulk-delete of old
partitions, not JOIN speed itself.

---

Related: [04_window_functions_cte.md](../../04_Database_SQL/04_window_functions_cte.md)
(same concepts in PostgreSQL syntax — compare the two), `03_advanced_optimization.md`.
