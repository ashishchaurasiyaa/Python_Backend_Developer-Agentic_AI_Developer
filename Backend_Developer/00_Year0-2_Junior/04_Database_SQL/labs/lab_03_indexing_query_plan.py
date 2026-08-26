"""
Lab 03 — Indexing & Query Plans
════════════════════════════════════════════════════════════════════════════════

ARCHITECTURE — What an Index Does:

    WITHOUT index:           WITH index (B-Tree on email):
    ┌──────────────────┐     ┌───────────────────────────┐
    │ Sequential Scan  │     │ Index Scan                │
    │ Read ALL 1M rows │     │ B-Tree: O(log N) lookup   │
    │ Check each email │     │ → leaf node → table row   │
    │ Cost: O(N)       │     │ Cost: O(log N)            │
    └──────────────────┘     └───────────────────────────┘

INDEX TYPES:
  B-Tree (default) — range queries, equality, ORDER BY, <, >, BETWEEN
  Hash             — equality only (=), no range queries
  GIN              — arrays, JSONB, full-text search
  GiST             — geometric types, full-text search

COMPOSITE INDEX — column ORDER matters:
  CREATE INDEX idx ON orders(status, created_at)
  ✅ WHERE status = 'shipped'
  ✅ WHERE status = 'shipped' AND created_at > '2026-01-01'
  ❌ WHERE created_at > '2026-01-01'  ← leftmost column not in filter → full scan

COVERING INDEX:
  All columns needed are in the index → no table heap access needed
  CREATE INDEX idx ON orders(status, created_at) INCLUDE (total_amount)
  SELECT total_amount WHERE status='x' AND created_at>'y' → index-only scan

PARTIAL INDEX:
  Index only a subset of rows — smaller, faster
  CREATE INDEX idx ON orders(created_at) WHERE status = 'pending'

INTERVIEW ANSWER:
  "Composite index mein leftmost column ka filter hona zaroori hai — warna
   index use nahi hoga (full scan). (status, created_at) ka index sirf tab
   kaam karta hai jab status filter ho. EXPLAIN ANALYZE se check karte hain
   ki index scan ho raha hai ya sequential scan."

TASK:
  1. TODO 1: Create a composite index on orders(status, created_at)
  2. TODO 2: Create a partial index only for 'pending' orders
  3. TODO 3: Write a query that uses the composite index (verify with EXPLAIN QUERY PLAN)
  4. TODO 4: Write a query that CANNOT use the composite index (no leftmost column)
  5. TODO 5: Create a covering index that avoids table access entirely

RUN: python lab_03_indexing_query_plan.py

Prereq: none — uses Python's built-in sqlite3
Note: SQLite uses "EXPLAIN QUERY PLAN" (not PostgreSQL's EXPLAIN ANALYZE).
      The principles are identical; the output format differs.
      In production: EXPLAIN (ANALYZE, BUFFERS) SELECT ... in PostgreSQL.
"""

import sqlite3

# ════════════════════════════════════════════════════════════════════════════
# SCHEMA + SEED DATA
# ════════════════════════════════════════════════════════════════════════════

def setup_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row

    conn.executescript("""
        CREATE TABLE orders (
            id           INTEGER PRIMARY KEY,
            user_id      INTEGER NOT NULL,
            status       TEXT NOT NULL,    -- 'pending','shipped','delivered','cancelled'
            total_amount REAL NOT NULL,
            created_at   TEXT NOT NULL     -- ISO date string 'YYYY-MM-DD'
        );

        -- Insert 1000 sample orders
        WITH RECURSIVE cnt(i) AS (
            SELECT 1
            UNION ALL SELECT i+1 FROM cnt WHERE i < 1000
        )
        INSERT INTO orders(user_id, status, total_amount, created_at)
        SELECT
            (i % 50) + 1,
            CASE i % 4
                WHEN 0 THEN 'pending'
                WHEN 1 THEN 'shipped'
                WHEN 2 THEN 'delivered'
                ELSE 'cancelled'
            END,
            ROUND(10.0 + (i * 7.3) % 990, 2),
            DATE('2026-01-01', '+' || (i % 180) || ' days')
        FROM cnt;
    """)
    conn.commit()
    return conn


def get_query_plan(conn: sqlite3.Connection, sql: str, params: tuple = ()) -> str:
    """
    Run EXPLAIN QUERY PLAN and return plan text joined.
    In SQLite: 'USING INDEX' or 'SCAN' appear in the detail column.
    In PostgreSQL: use EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT).
    """
    cur = conn.execute(f"EXPLAIN QUERY PLAN {sql}", params)
    rows = cur.fetchall()
    return " | ".join(str(dict(r)) for r in rows)


# ════════════════════════════════════════════════════════════════════════════
# TODO 1 — Create composite index on orders(status, created_at)
# ════════════════════════════════════════════════════════════════════════════
"""
Create a composite B-Tree index named `idx_orders_status_created`
on the `orders` table for columns (status, created_at).

Hint:
  conn.execute("CREATE INDEX idx_orders_status_created ON orders(status, created_at)")

This index can satisfy queries that filter on:
  ✅ status alone
  ✅ status + created_at
  ❌ created_at alone (leftmost column missing from filter)
"""

def create_composite_index(conn: sqlite3.Connection) -> None:
    raise NotImplementedError(
        "TODO 1: CREATE INDEX idx_orders_status_created ON orders(status, created_at)"
    )


# ════════════════════════════════════════════════════════════════════════════
# TODO 2 — Create partial index for pending orders only
# ════════════════════════════════════════════════════════════════════════════
"""
Create a partial index `idx_orders_pending_created` on `orders(created_at)`
WHERE status = 'pending'.

Benefit: ~250 rows indexed instead of 1000 — smaller, faster for pending queries.

Hint:
  conn.execute(
      "CREATE INDEX idx_orders_pending_created ON orders(created_at) "
      "WHERE status = 'pending'"
  )
"""

def create_partial_index(conn: sqlite3.Connection) -> None:
    raise NotImplementedError(
        "TODO 2: CREATE INDEX ... ON orders(created_at) WHERE status = 'pending'"
    )


# ════════════════════════════════════════════════════════════════════════════
# TODO 3 — Query that USES the composite index
# ════════════════════════════════════════════════════════════════════════════
"""
Write a query that filters on BOTH status AND created_at.
This should use `idx_orders_status_created`.

Hint:
  SELECT id, status, created_at, total_amount
  FROM orders
  WHERE status = 'shipped'
    AND created_at >= '2026-03-01'
  ORDER BY created_at;

Return the list of result dicts.
"""

def query_using_composite_index(conn: sqlite3.Connection) -> list:
    raise NotImplementedError(
        "TODO 3: SELECT WHERE status='shipped' AND created_at >= '2026-03-01'"
    )


# ════════════════════════════════════════════════════════════════════════════
# TODO 4 — Query that CANNOT use composite index (no leftmost column)
# ════════════════════════════════════════════════════════════════════════════
"""
Write a query that filters ONLY on created_at (no status filter).
The composite index idx_orders_status_created CANNOT be used here —
`status` is the leftmost column and it's absent.

Hint:
  SELECT id, status, created_at, total_amount
  FROM orders
  WHERE created_at >= '2026-06-01'
  ORDER BY created_at;

Return the list of result dicts.

Note: SQLite may still use a scan. The important concept is: in PostgreSQL,
EXPLAIN ANALYZE would show a "Seq Scan" or "Bitmap Heap Scan" bypassing
the composite index.
"""

def query_without_index(conn: sqlite3.Connection) -> list:
    raise NotImplementedError(
        "TODO 4: SELECT WHERE created_at >= '2026-06-01' (no status — index not useful)"
    )


# ════════════════════════════════════════════════════════════════════════════
# TODO 5 — Covering index: avoid heap table access
# ════════════════════════════════════════════════════════════════════════════
"""
Create a covering index that includes total_amount so the DB can satisfy
certain queries from the index alone (no table heap access needed).

In PostgreSQL:
  CREATE INDEX idx_covering ON orders(status, created_at) INCLUDE (total_amount);

In SQLite, INCLUDE is not supported — put total_amount as a regular index column:
  CREATE INDEX idx_orders_covering ON orders(status, created_at, total_amount);

Then write a query that only needs status, created_at, and total_amount:
  SELECT status, created_at, total_amount FROM orders WHERE status = 'delivered';

This query can be answered entirely from the index — no table rows needed.

Hint:
  def create_covering_index(conn):
      conn.execute("CREATE INDEX idx_orders_covering ON orders(status, created_at, total_amount)")

  def query_covering_index(conn):
      return [dict(r) for r in conn.execute(
          "SELECT status, created_at, total_amount FROM orders WHERE status = 'delivered'"
      )]
"""

def create_covering_index(conn: sqlite3.Connection) -> None:
    raise NotImplementedError(
        "TODO 5a: CREATE INDEX idx_orders_covering ON orders(status, created_at, total_amount)"
    )

def query_covering_index(conn: sqlite3.Connection) -> list:
    raise NotImplementedError(
        "TODO 5b: SELECT status, created_at, total_amount FROM orders WHERE status='delivered'"
    )


# ════════════════════════════════════════════════════════════════════════════
# TESTS
# ════════════════════════════════════════════════════════════════════════════

def run_tests():
    conn = setup_db()
    passed = 0
    failed = 0

    def check(label, condition, msg=""):
        nonlocal passed, failed
        if condition:
            print(f"✅ {label}")
            passed += 1
        else:
            print(f"❌ {label} — FAIL: {msg}")
            failed += 1

    # ── TODO 1 ──────────────────────────────────────────────────────────────
    print("\n── TODO 1: Create composite index ──")
    create_composite_index(conn)
    indexes = [r[1] for r in conn.execute("PRAGMA index_list('orders')").fetchall()]
    check("1a. idx_orders_status_created exists",
          "idx_orders_status_created" in indexes, f"Indexes found: {indexes}")

    # Verify column order in index
    idx_info = conn.execute("PRAGMA index_info('idx_orders_status_created')").fetchall()
    idx_cols = [r[2] for r in idx_info]
    check("1b. First column is 'status'",
          idx_cols and idx_cols[0] == "status", f"Index columns: {idx_cols}")
    check("1c. Second column is 'created_at'",
          len(idx_cols) > 1 and idx_cols[1] == "created_at", f"Index columns: {idx_cols}")

    # ── TODO 2 ──────────────────────────────────────────────────────────────
    print("\n── TODO 2: Create partial index ──")
    create_partial_index(conn)
    indexes = [r[1] for r in conn.execute("PRAGMA index_list('orders')").fetchall()]
    check("2a. idx_orders_pending_created exists",
          "idx_orders_pending_created" in indexes, f"Indexes: {indexes}")

    # ── TODO 3 ──────────────────────────────────────────────────────────────
    print("\n── TODO 3: Query using composite index ──")
    rows3 = query_using_composite_index(conn)
    check("3a. Returns rows (shipped orders from Mar 2026+)",
          len(rows3) > 0, "Expected some rows — check date range and status filter")
    check("3b. All rows have status='shipped'",
          all(r["status"] == "shipped" for r in rows3),
          f"Non-shipped row found: {[r['status'] for r in rows3 if r['status'] != 'shipped']}")
    check("3c. All rows have created_at >= '2026-03-01'",
          all(r["created_at"] >= "2026-03-01" for r in rows3),
          "Row with created_at before 2026-03-01 found")

    # Show query plan (informational)
    plan3 = get_query_plan(conn,
        "SELECT id, status, created_at FROM orders WHERE status='shipped' AND created_at >= '2026-03-01'")
    print(f"   [QUERY PLAN] {plan3[:120]}")

    # ── TODO 4 ──────────────────────────────────────────────────────────────
    print("\n── TODO 4: Query without leftmost index column ──")
    rows4 = query_without_index(conn)
    check("4a. Returns rows (orders from Jun 2026+)",
          len(rows4) > 0, "Expected rows for created_at >= '2026-06-01'")
    check("4b. All rows have created_at >= '2026-06-01'",
          all(r["created_at"] >= "2026-06-01" for r in rows4),
          "Row before '2026-06-01' found")

    # Show query plan (informational — shows index NOT used for composite)
    plan4 = get_query_plan(conn,
        "SELECT id, status, created_at FROM orders WHERE created_at >= '2026-06-01'")
    print(f"   [QUERY PLAN] {plan4[:120]}")
    print("   ↑ Note: in PostgreSQL this would show Seq Scan (composite index bypassed)")

    # ── TODO 5 ──────────────────────────────────────────────────────────────
    print("\n── TODO 5: Covering index ──")
    create_covering_index(conn)
    indexes = [r[1] for r in conn.execute("PRAGMA index_list('orders')").fetchall()]
    check("5a. idx_orders_covering exists",
          "idx_orders_covering" in indexes, f"Indexes: {indexes}")

    rows5 = query_covering_index(conn)
    check("5b. Returns delivered orders",
          len(rows5) > 0, "Expected some delivered orders")
    check("5c. All rows have status='delivered'",
          all(r["status"] == "delivered" for r in rows5),
          f"Non-delivered row found")
    check("5d. total_amount column present in result",
          rows5 and "total_amount" in rows5[0].keys(),
          f"Columns: {list(rows5[0].keys()) if rows5 else 'empty'}")

    # Covering index query plan
    plan5 = get_query_plan(conn,
        "SELECT status, created_at, total_amount FROM orders WHERE status='delivered'")
    print(f"   [QUERY PLAN] {plan5[:120]}")
    print("   ↑ In PostgreSQL: 'Index Only Scan' = covering index hit (no heap access)")

    print(f"\n{'═'*50}")
    print(f"  {passed} passed  |  {failed} failed")
    if failed == 0:
        print("  ✅ ALL PASS — Lab 03 complete!")
    else:
        print("  ❌ Fix the failing TODOs above and rerun.")
    print('═'*50)
    conn.close()


# ════════════════════════════════════════════════════════════════════════════
# SOCH (Answer ALOUD)
# ════════════════════════════════════════════════════════════════════════════
"""
Q1: Composite index mein column order kyon matter karta hai?
    (status, created_at) vs (created_at, status) — kya fark padta hai?

Q2: Partial index kab use karo?
    "Pending orders ki query 90% queries hain" — partial index kyon helpful hai?

Q3: Covering index kya hai aur "Index Only Scan" kab hota hai?
    (All SELECT columns are in the index — no table heap access needed)

Q4: Production mein ek query slow ho gayi — step-by-step kya karoge?
    (Capture SQL → EXPLAIN ANALYZE → check Seq Scan vs Index Scan →
     check index exists → check index selectivity → check statistics)

Q5: Bahut zyada indexes bad kyon hai?
    (Write overhead: INSERT/UPDATE/DELETE har index ko update karta hai.
     Storage cost. Optimizer confusion. Maintenance overhead.)
"""

if __name__ == "__main__":
    run_tests()
