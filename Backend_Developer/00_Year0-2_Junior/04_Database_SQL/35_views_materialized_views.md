# Views & Materialized Views — PostgreSQL

## 1. What is a View?

A **view** is a named SQL query stored in the database. It looks and behaves like a table but contains no data of its own — every query against it re-executes the underlying SQL.

```sql
CREATE VIEW active_users AS
SELECT id, email, created_at
FROM users
WHERE deleted_at IS NULL;

-- Use it like a table
SELECT * FROM active_users WHERE created_at > '2026-01-01';
```

Why:
- **Abstraction** — hide complex joins from application code
- **Security** — expose only certain columns/rows to a role
- **Consistency** — one place to change the definition

---

## 2. Updatable Views

PostgreSQL automatically makes a view updatable if it maps 1:1 to one base table (no JOINs, no aggregates, no DISTINCT, no LIMIT).

```sql
CREATE VIEW user_profiles AS
SELECT id, email, bio FROM users;

-- This works on an updatable view:
UPDATE user_profiles SET bio = 'New bio' WHERE id = 5;
-- PostgreSQL rewrites this to: UPDATE users SET bio = 'New bio' WHERE id = 5
```

### WITH CHECK OPTION

Prevents INSERTs/UPDATEs that would make the row disappear from the view:

```sql
CREATE VIEW active_users AS
SELECT * FROM users WHERE deleted_at IS NULL
WITH CHECK OPTION;

-- This FAILS — the row wouldn't appear in active_users after insert
UPDATE active_users SET deleted_at = NOW() WHERE id = 5;
-- ERROR: new row violates check option for view "active_users"
```

### Non-updatable views need INSTEAD OF triggers

```sql
-- View with JOIN — not auto-updatable
CREATE VIEW user_orders AS
SELECT u.email, o.total FROM users u JOIN orders o ON o.user_id = u.id;

CREATE TRIGGER update_user_orders
INSTEAD OF UPDATE ON user_orders
FOR EACH ROW EXECUTE FUNCTION handle_user_order_update();
```

---

## 3. Materialized Views

A **materialized view** stores the query result physically on disk. Query is fast (no re-computation) but data can become stale.

```sql
CREATE MATERIALIZED VIEW monthly_revenue AS
SELECT
    DATE_TRUNC('month', created_at) AS month,
    SUM(total_amount)               AS revenue,
    COUNT(*)                        AS order_count
FROM orders
GROUP BY 1
ORDER BY 1;

-- Query hits stored data — instant even on 100M rows
SELECT * FROM monthly_revenue WHERE month >= '2026-01-01';
```

### REFRESH MATERIALIZED VIEW

```sql
-- Blocks all reads during refresh (table-level lock)
REFRESH MATERIALIZED VIEW monthly_revenue;

-- Non-blocking: allows reads during refresh
-- Requires a UNIQUE index on the materialized view
REFRESH MATERIALIZED VIEW CONCURRENTLY monthly_revenue;
```

### Adding UNIQUE index for CONCURRENTLY

```sql
CREATE UNIQUE INDEX ON monthly_revenue (month);
-- Now CONCURRENTLY works
REFRESH MATERIALIZED VIEW CONCURRENTLY monthly_revenue;
```

### Automate refresh with pg_cron

```sql
-- Refresh every day at 3am (requires pg_cron extension)
SELECT cron.schedule('0 3 * * *', 'REFRESH MATERIALIZED VIEW CONCURRENTLY monthly_revenue');
```

---

## 4. View vs Materialized View — Decision Table

| Criterion | View | Materialized View |
|-----------|------|--------------------|
| Data freshness | Always current | Stale until refreshed |
| Query speed | Depends on underlying query | Fast (pre-computed) |
| Storage | None | Disk space for result set |
| Can be indexed | No | Yes |
| Good for | Auth filters, column masking | Reports, dashboards, analytics |
| Refresh needed | No | Yes (manual or scheduled) |
| Blocking | — | REFRESH blocks (use CONCURRENTLY) |

---

## 5. Security Use Case — Row-Level Visibility

```sql
-- Expose only the requesting tenant's rows
CREATE VIEW my_orders AS
SELECT * FROM orders
WHERE tenant_id = current_setting('app.tenant_id')::int;

-- Grant SELECT to app role (not on orders table directly)
GRANT SELECT ON my_orders TO app_role;
```

---

## 6. Performance Gotchas

### Views are not automatically optimized in older engines

```sql
-- This might not push the WHERE clause into the view's subquery efficiently
-- in all cases — use EXPLAIN ANALYZE to verify
SELECT * FROM expensive_view WHERE user_id = 5;

-- vs materialized view with index — always fast:
CREATE INDEX ON mv_user_stats(user_id);
SELECT * FROM mv_user_stats WHERE user_id = 5;
```

### Nesting views can hide performance problems

Each layer of views adds complexity to the query plan. Three levels of view nesting can produce a plan that's impossible to read. Materialize at the expensive join point.

---

## 7. Practical Patterns

### Pattern 1: Reporting layer (Materialized View)

```sql
CREATE MATERIALIZED VIEW dashboard_kpis AS
SELECT
    DATE_TRUNC('day', o.created_at)  AS day,
    COUNT(DISTINCT o.id)             AS orders,
    COUNT(DISTINCT o.user_id)        AS unique_customers,
    SUM(o.total_amount)              AS revenue,
    AVG(o.total_amount)              AS avg_order_value
FROM orders o
WHERE o.status = 'completed'
GROUP BY 1;

CREATE UNIQUE INDEX ON dashboard_kpis (day);
-- Refresh nightly; dashboard reads are instant
```

### Pattern 2: Multi-tenant data isolation (View)

```sql
CREATE VIEW tenant_users AS
SELECT * FROM users
WHERE organisation_id = current_setting('rls.org_id')::int;

-- Application sets it per-request:
-- SET LOCAL rls.org_id = 42;
```

### Pattern 3: Column-masking (View)

```sql
CREATE VIEW users_public AS
SELECT id, username, created_at  -- no email, no password_hash
FROM users;

GRANT SELECT ON users_public TO readonly_role;
```

---

## 8. Interview Questions

**Q: View aur Materialized View mein kya fark hai?**
View ek stored query hai — har baar execute hoti hai. Materialized view result disk pe store karta hai — fast hai lekin stale ho sakta hai jab tak REFRESH na karo.

**Q: REFRESH MATERIALIZED VIEW CONCURRENTLY kab kaam karta hai?**
Sirf tab jab materialized view pe ek UNIQUE index ho. Bina index ke CONCURRENTLY fail ho jaata hai.

**Q: Kab materialized view use karo aur kab regular view?**
Real-time data chahiye → regular view. Expensive aggregations jinhein har query pe compute karna slow ho → materialized view with scheduled refresh.

**Q: View se security kaise milti hai?**
Table pe direct GRANT mat do. View banao jo sirf allowed rows/columns expose kare, phir view pe GRANT do. Application code table ka structure nahi dekhti.

**Q: Updatable view kab hoti hai?**
Jab underlying query mein: ek hi base table ho, koi JOIN/GROUP BY/DISTINCT/LIMIT/aggregate na ho. PostgreSQL automatically UPDATE/INSERT/DELETE rewrite karta hai base table pe.
