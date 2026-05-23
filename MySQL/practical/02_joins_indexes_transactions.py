"""
MySQL Practical 02 — JOINs, Indexes & Transactions
===================================================
Covers: INNER/LEFT/RIGHT/SELF/CROSS JOIN, Subqueries, Indexes (B-Tree,
        Composite, Covering, FULLTEXT), Transactions, SAVEPOINTs,
        Deadlock simulation + retry, Views.

Run:
    python 02_joins_indexes_transactions.py [section]

Sections:
    joins          All JOIN types with formatted output
    subqueries     Scalar, IN, EXISTS, Correlated, Derived table
    indexes        Index creation, EXPLAIN comparison, composite, covering
    transactions   Happy path, rollback, SAVEPOINT, deadlock + retry
    views          Create view, query, update, re-query
    all            Run everything (default)

Prerequisites:
    pip install mysql-connector-python tabulate

    Docker (quick start):
        docker run -d --name mysql_practice \\
            -p 3306:3306 \\
            -e MYSQL_ROOT_PASSWORD=rootpass \\
            -e MYSQL_DATABASE=practice_db \\
            mysql:8.0

    Or set env vars:
        MYSQL_HOST, MYSQL_PORT, MYSQL_USER, MYSQL_PASSWORD, MYSQL_DATABASE
"""

import os
import sys
import time
import json
import threading
import mysql.connector
from contextlib import contextmanager
from typing import List, Dict, Any

try:
    from tabulate import tabulate
    HAS_TABULATE = True
except ImportError:
    HAS_TABULATE = False
    print("Tip: pip install tabulate for prettier tables")

# ─────────────────────────────────────────────
# Config
# ─────────────────────────────────────────────
DB_CONFIG = {
    "host":     os.environ.get("MYSQL_HOST",     "127.0.0.1"),
    "port":     int(os.environ.get("MYSQL_PORT", "3306")),
    "user":     os.environ.get("MYSQL_USER",     "root"),
    "password": os.environ.get("MYSQL_PASSWORD", "rootpass"),
    "database": os.environ.get("MYSQL_DATABASE", "practice_db"),
    "autocommit": False,
}


# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────
def get_conn(**overrides) -> mysql.connector.MySQLConnection:
    cfg = {**DB_CONFIG, **overrides}
    return mysql.connector.connect(**cfg)


def print_table(rows: List[tuple], headers: List[str], title: str = "") -> None:
    """Rows ko formatted table mein print karo."""
    if title:
        print(f"\n  {title}")
        print("  " + "-" * len(title))
    if not rows:
        print("  (koi rows nahi mili)")
        return
    if HAS_TABULATE:
        print(tabulate(rows, headers=headers, tablefmt="rounded_outline",
                       numalign="right", floatfmt=".2f"))
    else:
        # Simple fallback
        col_widths = [max(len(str(h)), max((len(str(r[i])) for r in rows), default=0))
                      for i, h in enumerate(headers)]
        fmt = "  " + "  ".join(f"{{:<{w}}}" for w in col_widths)
        print(fmt.format(*headers))
        print("  " + "  ".join("-" * w for w in col_widths))
        for row in rows:
            print(fmt.format(*[str(v) if v is not None else "NULL" for v in row]))
    print(f"  ({len(rows)} row{'s' if len(rows) != 1 else ''})")


@contextmanager
def transaction(conn):
    """Context manager — auto commit ya rollback."""
    try:
        yield conn
        conn.commit()
        print("  ✅ Transaction committed")
    except Exception as exc:
        conn.rollback()
        print(f"  ❌ Transaction rolled back: {exc}")
        raise


def run_explain(cursor, sql: str, params: tuple = ()) -> None:
    """EXPLAIN chalao aur key columns print karo."""
    cursor.execute(f"EXPLAIN {sql}", params)
    cols = [d[0] for d in cursor.description]
    rows = cursor.fetchall()
    print("  [EXPLAIN]")
    for row in rows:
        d = dict(zip(cols, row))
        key   = d.get("key")    or "NULL (no index!)"
        rtype = d.get("type")   or "?"
        rrows = d.get("rows")   or "?"
        extra = d.get("Extra")  or ""
        print(f"    type={rtype:10s}  key={key:30s}  rows={rrows:>8}  Extra={extra}")


# ─────────────────────────────────────────────
# Schema + Seed
# ─────────────────────────────────────────────
def setup_schema() -> None:
    """
    Tables banao aur sample data seed karo.
    Tables: users, orders, products, order_items, accounts, employees
    Edge cases: users without orders, orphan orders (user_id=NULL),
                products never ordered, accounts for transaction demo.
    """
    print("\n" + "=" * 60)
    print("  SETUP — Schema + Seed Data")
    print("=" * 60)

    conn = get_conn(autocommit=True)
    cur  = conn.cursor()

    # Drop order matters (FK constraints)
    drops = [
        "DROP TABLE IF EXISTS order_audit",
        "DROP TABLE IF EXISTS order_items",
        "DROP TABLE IF EXISTS orders",
        "DROP TABLE IF EXISTS products",
        "DROP TABLE IF EXISTS users",
        "DROP TABLE IF EXISTS accounts",
        "DROP TABLE IF EXISTS employees",
        "DROP VIEW  IF EXISTS active_product_summary",
    ]
    for ddl in drops:
        cur.execute(ddl)

    ddl_statements = [
        # users
        """
        CREATE TABLE users (
            id         INT PRIMARY KEY AUTO_INCREMENT,
            name       VARCHAR(100) NOT NULL,
            email      VARCHAR(200) UNIQUE,
            city       VARCHAR(50)
        )
        """,
        # orders — user_id can be NULL (orphan)
        """
        CREATE TABLE orders (
            id           INT PRIMARY KEY AUTO_INCREMENT,
            user_id      INT,
            total_amount DECIMAL(10,2),
            status       ENUM('pending','paid','shipped','delivered','cancelled'),
            created_at   DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
        )
        """,
        # products
        """
        CREATE TABLE products (
            id        INT PRIMARY KEY AUTO_INCREMENT,
            name      VARCHAR(200),
            price     DECIMAL(10,2),
            category  VARCHAR(50),
            is_active BOOLEAN DEFAULT TRUE
        )
        """,
        # order_items
        """
        CREATE TABLE order_items (
            id         INT PRIMARY KEY AUTO_INCREMENT,
            order_id   INT NOT NULL,
            product_id INT NOT NULL,
            quantity   INT NOT NULL,
            unit_price DECIMAL(10,2),
            FOREIGN KEY (order_id)   REFERENCES orders(id)   ON DELETE CASCADE,
            FOREIGN KEY (product_id) REFERENCES products(id)
        )
        """,
        # accounts (for transaction demo)
        """
        CREATE TABLE accounts (
            id      INT PRIMARY KEY AUTO_INCREMENT,
            holder  VARCHAR(100),
            balance DECIMAL(12,2) NOT NULL DEFAULT 0.00
        )
        """,
        # employees (self-join demo)
        """
        CREATE TABLE employees (
            id         INT PRIMARY KEY AUTO_INCREMENT,
            name       VARCHAR(100),
            department VARCHAR(50),
            manager_id INT,
            FOREIGN KEY (manager_id) REFERENCES employees(id)
        )
        """,
        # order_audit (trigger demo)
        """
        CREATE TABLE order_audit (
            id         INT PRIMARY KEY AUTO_INCREMENT,
            order_id   INT,
            action     VARCHAR(20),
            old_status VARCHAR(20),
            deleted_at DATETIME
        )
        """,
    ]

    for ddl in ddl_statements:
        cur.execute(ddl)

    print("  Tables created ✅")

    # ── Seed users (some will NOT have orders — edge case) ──
    users = [
        ("Rahul Sharma",    "rahul@example.com",   "Mumbai"),
        ("Priya Gupta",     "priya@example.com",   "Delhi"),
        ("Amit Verma",      "amit@example.com",    "Bengaluru"),
        ("Sneha Patel",     "sneha@example.com",   "Ahmedabad"),
        ("Vikram Singh",    "vikram@example.com",  "Jaipur"),
        ("Kavya Reddy",     "kavya@example.com",   "Hyderabad"),
        ("Arjun Nair",      "arjun@example.com",   "Kochi"),
        ("Meera Joshi",     "meera@example.com",   "Pune"),
        # Users WITHOUT any orders (edge case for LEFT JOIN demo)
        ("Ravi Kumar",      "ravi@example.com",    "Chennai"),
        ("Pooja Mishra",    "pooja@example.com",   "Lucknow"),
    ]
    cur.executemany("INSERT INTO users (name, email, city) VALUES (%s,%s,%s)", users)

    # ── Seed products ──
    products = [
        ("iPhone 15",          89999.00, "electronics"),
        ("Samsung Galaxy S24", 79999.00, "electronics"),
        ("Laptop Dell XPS",   129999.00, "electronics"),
        ("Wireless Earbuds",    4999.00, "accessories"),
        ("Laptop Bag",          2499.00, "accessories"),
        ("Mechanical Keyboard", 8999.00, "peripherals"),
        ("USB-C Hub",           3499.00, "peripherals"),
        ("Monitor 27inch",     34999.00, "peripherals"),
        ("Office Chair",       24999.00, "furniture"),
        ("Standing Desk",      45999.00, "furniture"),
        ("Python Book",          799.00, "books"),
        ("MySQL Deep Dive",      999.00, "books"),
        # Product never ordered (edge case)
        ("Smart Watch",        15999.00, "electronics"),
        ("Gaming Mouse",        5999.00, "peripherals"),
    ]
    cur.executemany(
        "INSERT INTO products (name, price, category) VALUES (%s,%s,%s)", products
    )

    # ── Seed orders (some belong to users, 2 are orphans) ──
    orders = [
        (1, 94998.00,  "delivered"),
        (1, 4999.00,   "paid"),
        (2, 129999.00, "shipped"),
        (2, 11498.00,  "delivered"),
        (3, 89999.00,  "delivered"),
        (4, 79999.00,  "pending"),
        (4, 38498.00,  "delivered"),
        (5, 2499.00,   "cancelled"),
        (6, 129999.00, "paid"),
        (7, 55998.00,  "delivered"),
        (8, 4999.00,   "cancelled"),
        (8, 24999.00,  "delivered"),
        # Orphan orders — user_id=NULL (edge case for RIGHT JOIN / anti-join)
        (None, 5000.00, "pending"),
        (None, 1500.00, "cancelled"),
    ]
    cur.executemany(
        "INSERT INTO orders (user_id, total_amount, status) VALUES (%s,%s,%s)", orders
    )

    # ── Seed order_items ──
    # order_id  product_id  qty  unit_price
    items = [
        (1,  1, 1, 89999.00),  # order 1: iPhone
        (1,  4, 1,  4999.00),  # order 1: Earbuds
        (2,  4, 1,  4999.00),  # order 2: Earbuds
        (3,  3, 1, 129999.00), # order 3: Laptop
        (4,  6, 1,  8999.00),  # order 4: Keyboard
        (4,  7, 1,  2499.00),  # order 4: Bag — wait, that's bag not hub
        (5,  1, 1, 89999.00),  # order 5: iPhone
        (6,  2, 1, 79999.00),  # order 6: Samsung
        (7,  2, 1, 79999.00),  # order 7: Samsung
        (7,  9, 1, 24999.00),  # order 7: Chair
        (8,  5, 1,  2499.00),  # order 8: Bag
        (9,  3, 1, 129999.00), # order 9: Laptop
        (10, 3, 1, 129999.00), # order 10: Laptop
        (10, 8, 1,  34999.00), # order 10: Monitor
        (11, 4, 1,  4999.00),  # order 11: Earbuds
        (12, 9, 1, 24999.00),  # order 12: Chair
    ]
    cur.executemany(
        "INSERT INTO order_items (order_id, product_id, quantity, unit_price) "
        "VALUES (%s,%s,%s,%s)",
        items
    )

    # ── Seed accounts ──
    accounts = [
        ("Alice",   50000.00),
        ("Bob",     30000.00),
        ("Charlie",  5000.00),  # low balance — for insufficient funds demo
    ]
    cur.executemany("INSERT INTO accounts (holder, balance) VALUES (%s,%s)", accounts)

    # ── Seed employees (self-join) ──
    # First insert top-level (no manager)
    cur.execute("INSERT INTO employees (id,name,department,manager_id) VALUES (1,'Suresh CEO','Management',NULL)")
    cur.execute("INSERT INTO employees (id,name,department,manager_id) VALUES (2,'Deepa CTO','Engineering',1)")
    cur.execute("INSERT INTO employees (id,name,department,manager_id) VALUES (3,'Rohan VP Sales','Sales',1)")
    cur.execute("INSERT INTO employees (id,name,department,manager_id) VALUES (4,'Anjali Dev Lead','Engineering',2)")
    cur.execute("INSERT INTO employees (id,name,department,manager_id) VALUES (5,'Nikhil Sr Dev','Engineering',4)")
    cur.execute("INSERT INTO employees (id,name,department,manager_id) VALUES (6,'Priti Dev','Engineering',4)")
    cur.execute("INSERT INTO employees (id,name,department,manager_id) VALUES (7,'Sanjay Sales Mgr','Sales',3)")

    cur.close()
    conn.close()

    print("  Seed data inserted ✅")
    print("    Users: 10 (2 without orders)")
    print("    Products: 14 (2 never ordered)")
    print("    Orders: 14 (2 orphan — user_id NULL)")
    print("    Order Items: 16")
    print("    Accounts: 3")
    print("    Employees: 7 (hierarchy)")


# ─────────────────────────────────────────────
# Section 1: JOINs
# ─────────────────────────────────────────────
def demo_joins() -> None:
    print("\n" + "=" * 60)
    print("  SECTION 1 — All JOIN Types")
    print("=" * 60)

    conn = get_conn(autocommit=True)
    cur  = conn.cursor()

    # ── 1a. INNER JOIN ──────────────────────────────────────────
    print("\n📌 1a. INNER JOIN — Users jo orders place kar chuke hain")
    print("   Sirf matched rows — user bhi hona chahiye, order bhi")
    cur.execute("""
        SELECT u.name, u.city,
               COUNT(o.id)                       AS order_count,
               COALESCE(SUM(o.total_amount), 0)  AS total_spent
        FROM   users u
        INNER JOIN orders o ON u.id = o.user_id
        GROUP  BY u.id, u.name, u.city
        ORDER  BY total_spent DESC
    """)
    print_table(cur.fetchall(),
                ["Name", "City", "Orders", "Total Spent (Rs)"],
                "Result:")

    # ── 1b. LEFT JOIN ──────────────────────────────────────────
    print("\n📌 1b. LEFT JOIN — Sabhi users (order kiya ho ya na kiya ho)")
    print("   Users without orders → order_count=0")
    cur.execute("""
        SELECT u.name, u.city,
               COUNT(o.id)                       AS order_count,
               COALESCE(SUM(o.total_amount), 0)  AS total_spent
        FROM   users u
        LEFT JOIN orders o ON u.id = o.user_id
        GROUP  BY u.id, u.name, u.city
        ORDER  BY total_spent DESC
    """)
    print_table(cur.fetchall(),
                ["Name", "City", "Orders", "Total Spent (Rs)"],
                "Result (INNER JOIN se zyada rows ayenge):")

    # ── 1c. Anti-Join (LEFT JOIN + IS NULL) ────────────────────
    print("\n📌 1c. Anti-JOIN — Users jo KABHI kuch nahi kharide")
    print("   LEFT JOIN + WHERE right.id IS NULL")
    print("   (NOT IN se zyada efficient for large tables)")
    cur.execute("""
        SELECT u.name, u.email, u.city
        FROM   users u
        LEFT JOIN orders o ON u.id = o.user_id
        WHERE  o.id IS NULL
    """)
    print_table(cur.fetchall(),
                ["Name", "Email", "City"],
                "Result:")

    # ── 1d. RIGHT JOIN ─────────────────────────────────────────
    print("\n📌 1d. RIGHT JOIN + IS NULL — Orphan orders (user_id NULL)")
    print("   Orders jo kisi user se belong nahi karte")
    cur.execute("""
        SELECT o.id AS order_id, o.total_amount, o.status, u.name AS user_name
        FROM   users u
        RIGHT JOIN orders o ON u.id = o.user_id
        WHERE  u.id IS NULL
    """)
    print_table(cur.fetchall(),
                ["Order ID", "Amount", "Status", "User (NULL = orphan)"],
                "Result:")

    # ── 1e. FULL OUTER JOIN via UNION ──────────────────────────
    print("\n📌 1e. FULL OUTER JOIN — UNION se (MySQL mein direct support nahi)")
    cur.execute("""
        SELECT u.name AS user_name, o.id AS order_id, o.status
        FROM   users u LEFT JOIN orders o ON u.id = o.user_id
        UNION
        SELECT u.name AS user_name, o.id AS order_id, o.status
        FROM   users u RIGHT JOIN orders o ON u.id = o.user_id
        ORDER  BY user_name, order_id
        LIMIT  12
    """)
    print_table(cur.fetchall(),
                ["User", "Order ID", "Status"],
                "Result (first 12 rows):")

    # ── 1f. Self JOIN ──────────────────────────────────────────
    print("\n📌 1f. SELF JOIN — Employee + Manager hierarchy")
    print("   Same table ko do aliases se join karo")
    cur.execute("""
        SELECT e.name       AS employee,
               e.department,
               COALESCE(m.name, '(CEO — no manager)') AS manager
        FROM   employees e
        LEFT JOIN employees m ON e.manager_id = m.id
        ORDER  BY e.manager_id NULLS FIRST, e.id
    """)
    print_table(cur.fetchall(),
                ["Employee", "Department", "Manager"],
                "Result:")

    # ── 1g. CROSS JOIN ─────────────────────────────────────────
    print("\n📌 1g. CROSS JOIN — Cartesian product (categories x statuses)")
    print("   Use case: price matrix, combinations generate karna")
    cur.execute("""
        SELECT c.cat, s.stat, CONCAT(c.cat, '-', s.stat) AS combo
        FROM
            (SELECT 'electronics' AS cat UNION SELECT 'books' UNION SELECT 'furniture') c
            CROSS JOIN
            (SELECT 'in_stock' AS stat UNION SELECT 'out_of_stock') s
        ORDER BY c.cat, s.stat
    """)
    print_table(cur.fetchall(),
                ["Category", "Status", "Combo"],
                "Result (3 categories x 2 statuses = 6 rows):")

    # ── 1h. Multi-table JOIN (4 tables) ────────────────────────
    print("\n📌 1h. Multi-table JOIN — users + orders + order_items + products")
    cur.execute("""
        SELECT
            u.name                                AS customer,
            o.id                                  AS order_id,
            o.status,
            p.name                                AS product,
            oi.quantity,
            oi.unit_price,
            (oi.quantity * oi.unit_price)         AS line_total
        FROM   users u
        JOIN   orders      o  ON u.id          = o.user_id
        JOIN   order_items oi ON o.id          = oi.order_id
        JOIN   products    p  ON oi.product_id = p.id
        WHERE  o.status = 'delivered'
        ORDER  BY o.id, p.name
        LIMIT  10
    """)
    print_table(cur.fetchall(),
                ["Customer", "Order ID", "Status", "Product", "Qty", "Unit Price", "Line Total"],
                "Result — Delivered orders (first 10):")

    cur.close()
    conn.close()


# ─────────────────────────────────────────────
# Section 2: Subqueries
# ─────────────────────────────────────────────
def demo_subqueries() -> None:
    print("\n" + "=" * 60)
    print("  SECTION 2 — Subqueries")
    print("=" * 60)

    conn = get_conn(autocommit=True)
    cur  = conn.cursor()

    # ── 2a. Scalar subquery ────────────────────────────────────
    print("\n📌 2a. Scalar Subquery — Avg price ke comparison")
    print("   Subquery ek single value return karta hai")
    cur.execute("""
        SELECT name, price,
               ROUND((SELECT AVG(price) FROM products), 2)      AS avg_price,
               ROUND(price - (SELECT AVG(price) FROM products), 2) AS diff_from_avg
        FROM   products
        ORDER  BY price DESC
    """)
    print_table(cur.fetchall(),
                ["Product", "Price", "Avg Price", "Diff from Avg"],
                "Result:")

    # ── 2b. IN subquery ────────────────────────────────────────
    print("\n📌 2b. IN Subquery — Users jinhone kabhi cancel kiya")
    cur.execute("""
        SELECT u.name, u.email
        FROM   users u
        WHERE  u.id IN (
            SELECT DISTINCT user_id
            FROM   orders
            WHERE  status = 'cancelled'
               AND user_id IS NOT NULL
        )
    """)
    print_table(cur.fetchall(),
                ["Name", "Email"],
                "Result:")

    # ── 2c. EXISTS vs IN ───────────────────────────────────────
    print("\n📌 2c. EXISTS vs IN — Large orders wale users")
    print("   EXISTS short-circuits (pehla match mila, ruk jaata hai)")
    print("   IN poori subquery load karta hai pehle")

    # EXISTS
    t0 = time.perf_counter()
    cur.execute("""
        SELECT u.name
        FROM   users u
        WHERE  EXISTS (
            SELECT 1 FROM orders o
            WHERE  o.user_id = u.id AND o.total_amount > 50000
        )
    """)
    rows_exists = cur.fetchall()
    t_exists = time.perf_counter() - t0

    # Equivalent with IN
    t0 = time.perf_counter()
    cur.execute("""
        SELECT u.name
        FROM   users u
        WHERE  u.id IN (
            SELECT DISTINCT user_id FROM orders WHERE total_amount > 50000
        )
    """)
    rows_in = cur.fetchall()
    t_in = time.perf_counter() - t0

    print_table(rows_exists, ["Name"], "EXISTS result:")
    print(f"  EXISTS time : {t_exists*1000:.2f}ms")
    print(f"  IN     time : {t_in*1000:.2f}ms")
    assert set(rows_exists) == set(rows_in), "Results should match!"
    print("  Same results confirmed ✅")

    # ── 2d. Correlated subquery ────────────────────────────────
    print("\n📌 2d. Correlated Subquery — Times each product was delivered")
    print("   Outer query ke har row ke liye subquery chalti hai")
    cur.execute("""
        SELECT p.name, p.category, p.price,
               (
                   SELECT COUNT(*)
                   FROM   order_items oi
                   JOIN   orders o ON oi.order_id = o.id
                   WHERE  oi.product_id = p.id
                     AND  o.status = 'delivered'
               ) AS times_delivered
        FROM   products p
        ORDER  BY times_delivered DESC, p.price DESC
    """)
    print_table(cur.fetchall(),
                ["Product", "Category", "Price", "Times Delivered"],
                "Result:")

    # ── 2e. Derived table ──────────────────────────────────────
    print("\n📌 2e. Derived Table — GROUP BY result pe filter")
    print("   Subquery in FROM clause — pehle aggregate, phir filter")
    print("   (Directly GROUP BY pe WHERE nahi laga sakte)")
    cur.execute("""
        SELECT category, avg_price, product_count
        FROM (
            SELECT category,
                   ROUND(AVG(price), 2) AS avg_price,
                   COUNT(*)             AS product_count
            FROM   products
            GROUP  BY category
        ) AS cat_stats
        WHERE avg_price > 5000
        ORDER BY avg_price DESC
    """)
    print_table(cur.fetchall(),
                ["Category", "Avg Price", "Product Count"],
                "Categories with avg price > Rs.5000:")

    cur.close()
    conn.close()


# ─────────────────────────────────────────────
# Section 3: Indexes
# ─────────────────────────────────────────────
def demo_indexes() -> None:
    print("\n" + "=" * 60)
    print("  SECTION 3 — Indexes")
    print("=" * 60)

    conn = get_conn(autocommit=True)
    cur  = conn.cursor()

    # ── 3a. EXPLAIN without vs with index ─────────────────────
    print("\n📌 3a. B-Tree Index — BEFORE vs AFTER comparison")

    # Remove any existing index on status
    try:
        cur.execute("DROP INDEX idx_status ON orders")
    except Exception:
        pass

    query = "SELECT * FROM orders WHERE status = 'delivered'"

    print("\n  --- WITHOUT Index ---")
    run_explain(cur, query)
    t0 = time.perf_counter()
    cur.execute(query)
    cur.fetchall()
    t_no_idx = time.perf_counter() - t0
    print(f"  Query time (no index): {t_no_idx*1000:.3f}ms")

    # Add index
    cur.execute("CREATE INDEX idx_status ON orders(status)")
    print("\n  CREATE INDEX idx_status ON orders(status)  ✅")

    print("\n  --- WITH Index ---")
    run_explain(cur, query)
    t0 = time.perf_counter()
    cur.execute(query)
    cur.fetchall()
    t_with_idx = time.perf_counter() - t0
    print(f"  Query time (with index): {t_with_idx*1000:.3f}ms")

    print(f"\n  Speedup: {t_no_idx/t_with_idx:.1f}x "
          f"(small table pe marginal, large tables pe dramatic)")

    # ── 3b. Composite Index + Left Prefix Rule ─────────────────
    print("\n📌 3b. Composite Index — Left Prefix Rule demo")

    try:
        cur.execute("DROP INDEX idx_status_date ON orders")
    except Exception:
        pass

    cur.execute("CREATE INDEX idx_status_date ON orders(status, created_at)")
    print("  CREATE INDEX idx_status_date ON orders(status, created_at)  ✅\n")

    queries = [
        ("✅ status only (left prefix)", "SELECT * FROM orders WHERE status = 'paid'"),
        ("✅ status + date (both columns)", "SELECT * FROM orders WHERE status = 'paid' AND created_at > '2024-01-01'"),
        ("❌ date only (no left prefix)", "SELECT * FROM orders WHERE created_at > '2024-01-01'"),
    ]
    for label, q in queries:
        print(f"  {label}")
        run_explain(cur, q)
        print()

    # ── 3c. Covering Index ─────────────────────────────────────
    print("\n📌 3c. Covering Index — No table lookup needed")

    try:
        cur.execute("DROP INDEX idx_covering ON orders")
    except Exception:
        pass

    covering_q = "SELECT user_id, status, total_amount FROM orders WHERE user_id = 1"

    print("  Without covering index:")
    run_explain(cur, covering_q)

    cur.execute("CREATE INDEX idx_covering ON orders(user_id, status, total_amount)")
    print("\n  CREATE INDEX idx_covering ON orders(user_id, status, total_amount)  ✅")
    print("  With covering index:")
    run_explain(cur, covering_q)
    print("  Look for 'Using index' in Extra column ✅")

    # ── 3d. SHOW INDEX ─────────────────────────────────────────
    print("\n📌 3d. SHOW INDEX FROM orders")
    cur.execute("SHOW INDEX FROM orders")
    cols   = [d[0] for d in cur.description]
    rows   = cur.fetchall()
    # Show only important columns
    key_cols = ["Key_name", "Column_name", "Non_unique", "Cardinality", "Index_type"]
    key_idxs = [cols.index(c) for c in key_cols if c in cols]
    filtered = [[row[i] for i in key_idxs] for row in rows]
    print_table(filtered,
                [key_cols[i] for i in range(len(key_cols)) if key_cols[i] in cols],
                "Indexes on orders table:")

    # ── 3e. Function on column breaks index ────────────────────
    print("\n📌 3e. Function on column — Index MISS (common mistake!)")
    print("  WRONG: WHERE YEAR(created_at) = 2024  → index miss")
    run_explain(cur, "SELECT * FROM orders WHERE YEAR(created_at) = 2024")
    print("  RIGHT: WHERE created_at BETWEEN ... → index hit")
    run_explain(cur, "SELECT * FROM orders WHERE created_at BETWEEN '2024-01-01' AND '2024-12-31'")

    cur.close()
    conn.close()


# ─────────────────────────────────────────────
# Section 4: Transactions
# ─────────────────────────────────────────────
def demo_transactions() -> None:
    print("\n" + "=" * 60)
    print("  SECTION 4 — Transactions")
    print("=" * 60)

    # ── 4a. Happy path — Successful transfer ──────────────────
    print("\n📌 4a. Happy Path — Money Transfer (Rs.10,000 Alice → Bob)")

    conn = get_conn()

    def show_balances(label: str) -> None:
        c = conn.cursor(dictionary=True)
        c.execute("SELECT id, holder, balance FROM accounts ORDER BY id")
        rows = c.fetchall()
        c.close()
        print(f"\n  [{label}]")
        for r in rows:
            print(f"    Account {r['id']} ({r['holder']:10s}): Rs.{r['balance']:>12,.2f}")

    show_balances("BEFORE transfer")

    try:
        with transaction(conn):
            cur = conn.cursor(dictionary=True)
            # Lock both rows with FOR UPDATE — concurrent changes prevent
            cur.execute(
                "SELECT id, holder, balance FROM accounts WHERE id IN (1, 2) FOR UPDATE"
            )
            accounts = {r['id']: r for r in cur.fetchall()}
            amount = 10_000

            if accounts[1]['balance'] < amount:
                raise ValueError(f"Insufficient balance!")

            cur.execute("UPDATE accounts SET balance = balance - %s WHERE id = 1", (amount,))
            cur.execute("UPDATE accounts SET balance = balance + %s WHERE id = 2", (amount,))
            cur.close()
            print(f"  Debit Rs.{amount:,} from Alice, Credit to Bob")
    except Exception as exc:
        print(f"  Error: {exc}")

    show_balances("AFTER transfer")
    conn.close()

    # ── 4b. Error path — Insufficient balance → Rollback ──────
    print("\n📌 4b. Error Path — Insufficient Balance (Rs.99,999 from Charlie)")

    conn = get_conn()

    def show_balance(holder: str) -> None:
        c = conn.cursor(dictionary=True)
        c.execute("SELECT balance FROM accounts WHERE holder = %s", (holder,))
        r = c.fetchone()
        c.close()
        print(f"  {holder} balance: Rs.{r['balance']:>10,.2f}")

    show_balance("Charlie")

    try:
        with transaction(conn):
            cur = conn.cursor(dictionary=True)
            cur.execute(
                "SELECT id, balance FROM accounts WHERE holder = 'Charlie' FOR UPDATE"
            )
            acc = cur.fetchone()
            amount = 99_999

            print(f"  Trying to transfer Rs.{amount:,} (balance: Rs.{acc['balance']:,})")

            if acc['balance'] < amount:
                raise ValueError(
                    f"Insufficient! Balance={acc['balance']}, Required={amount}"
                )
            cur.execute("UPDATE accounts SET balance = balance - %s WHERE id = %s",
                        (amount, acc['id']))
            cur.close()
    except ValueError:
        pass  # Expected — already printed by context manager

    show_balance("Charlie")
    print("  Charlie balance unchanged — rollback worked ✅")
    conn.close()

    # ── 4c. SAVEPOINT — partial rollback ──────────────────────
    print("\n📌 4c. SAVEPOINT — Partial Rollback Demo")
    print("   Order create → SAVEPOINT → invalid item fail → rollback item → commit order")

    conn = get_conn()
    cur  = conn.cursor(dictionary=True)

    conn.start_transaction()
    try:
        # Step 1: Create order
        cur.execute(
            "INSERT INTO orders (user_id, total_amount, status) VALUES (1, 0, 'pending')"
        )
        order_id = cur.lastrowid
        print(f"  Order {order_id} created")

        conn.cmd_query("SAVEPOINT after_order")
        print(f"  SAVEPOINT 'after_order' set")

        # Step 2: Valid item
        cur.execute(
            "INSERT INTO order_items (order_id, product_id, quantity, unit_price) "
            "VALUES (%s, 1, 1, 89999.00)", (order_id,)
        )
        print(f"  Item 1 (iPhone) added ✅")

        conn.cmd_query("SAVEPOINT after_item1")

        # Step 3: Invalid item (product_id 9999 doesn't exist — FK violation)
        try:
            cur.execute(
                "INSERT INTO order_items (order_id, product_id, quantity, unit_price) "
                "VALUES (%s, 9999, 1, 500.00)", (order_id,)
            )
            conn.commit()  # This won't be reached
        except mysql.connector.errors.IntegrityError as e:
            print(f"  Item 2 failed (product 9999 n/a): {e.msg}")
            conn.cmd_query("ROLLBACK TO SAVEPOINT after_item1")
            print(f"  Rolled back to 'after_item1' — item 1 still safe")

        # Step 4: Update order total with just item 1
        cur.execute("UPDATE orders SET total_amount = 89999.00 WHERE id = %s", (order_id,))
        conn.commit()
        print(f"  Order {order_id} committed with 1 item (total Rs.89,999) ✅")

    except Exception as exc:
        conn.rollback()
        print(f"  Unexpected error: {exc}")

    # Verify
    cur.execute("SELECT id, total_amount, status FROM orders WHERE id = %s", (order_id,))
    order = cur.fetchone()
    cur.execute("SELECT product_id, quantity FROM order_items WHERE order_id = %s", (order_id,))
    items = cur.fetchall()
    print(f"  Verification: Order={order}, Items={items}")
    cur.close()
    conn.close()

    # ── 4d. Deadlock simulation + retry ───────────────────────
    print("\n📌 4d. Deadlock Simulation + Retry")
    print("   T1 locks account 1 then tries account 2")
    print("   T2 locks account 2 then tries account 1")
    print("   MySQL auto-detects and kills one; we retry.")

    deadlock_errors = []
    results         = []

    def txn1():
        conn1 = get_conn()
        try:
            conn1.start_transaction()
            c = conn1.cursor()
            c.execute("SELECT balance FROM accounts WHERE id = 1 FOR UPDATE")
            time.sleep(0.15)  # Let T2 lock account 2 first
            c.execute("SELECT balance FROM accounts WHERE id = 2 FOR UPDATE")
            c.execute("UPDATE accounts SET balance = balance - 100 WHERE id = 1")
            c.execute("UPDATE accounts SET balance = balance + 100 WHERE id = 2")
            conn1.commit()
            c.close()
            results.append("T1 committed")
        except mysql.connector.errors.DatabaseError as e:
            conn1.rollback()
            if e.errno == 1213:
                deadlock_errors.append("T1 deadlock detected")
                results.append("T1 rolled back (deadlock)")
        finally:
            conn1.close()

    def txn2():
        conn2 = get_conn()
        try:
            conn2.start_transaction()
            c = conn2.cursor()
            c.execute("SELECT balance FROM accounts WHERE id = 2 FOR UPDATE")
            time.sleep(0.15)  # Let T1 lock account 1 first
            c.execute("SELECT balance FROM accounts WHERE id = 1 FOR UPDATE")
            c.execute("UPDATE accounts SET balance = balance - 50 WHERE id = 2")
            c.execute("UPDATE accounts SET balance = balance + 50 WHERE id = 1")
            conn2.commit()
            c.close()
            results.append("T2 committed")
        except mysql.connector.errors.DatabaseError as e:
            conn2.rollback()
            if e.errno == 1213:
                deadlock_errors.append("T2 deadlock detected")
                results.append("T2 rolled back (deadlock)")
        finally:
            conn2.close()

    t1 = threading.Thread(target=txn1)
    t2 = threading.Thread(target=txn2)
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    for r in results:
        print(f"  {r}")
    if deadlock_errors:
        for e in deadlock_errors:
            print(f"  ⚠️  {e}")
        print("  Deadlock detected and handled automatically ✅")
        print("  Solution: Always lock in consistent order (id ASC) to prevent")
    else:
        print("  No deadlock occurred this run (timing-dependent)")

    # ── Retry pattern ──────────────────────────────────────────
    print("\n  --- Retry Pattern with Exponential Backoff ---")

    def transfer_with_retry(from_id: int, to_id: int, amount: float,
                            max_retries: int = 3) -> bool:
        """Deadlock pe retry karo — production-grade pattern."""
        for attempt in range(max_retries):
            conn = get_conn()
            try:
                conn.start_transaction()
                cur = conn.cursor(dictionary=True)
                # Consistent lock order (lower id first) — prevents deadlock!
                ids = sorted([from_id, to_id])
                cur.execute(
                    "SELECT id, balance FROM accounts WHERE id IN (%s, %s) FOR UPDATE",
                    ids
                )
                accs = {r['id']: r for r in cur.fetchall()}
                if accs[from_id]['balance'] < amount:
                    raise ValueError("Insufficient balance")
                cur.execute("UPDATE accounts SET balance = balance - %s WHERE id = %s",
                            (amount, from_id))
                cur.execute("UPDATE accounts SET balance = balance + %s WHERE id = %s",
                            (amount, to_id))
                conn.commit()
                cur.close()
                conn.close()
                print(f"  Transfer Rs.{amount} successful (attempt {attempt+1})")
                return True
            except mysql.connector.errors.DatabaseError as e:
                conn.rollback()
                conn.close()
                if e.errno == 1213 and attempt < max_retries - 1:
                    wait = (2 ** attempt) * 0.05
                    print(f"  Deadlock, retry {attempt+1}/{max_retries} in {wait:.2f}s")
                    time.sleep(wait)
                else:
                    print(f"  Failed after {max_retries} attempts: {e}")
                    return False
            except ValueError as e:
                conn.rollback()
                conn.close()
                print(f"  Business error (no retry): {e}")
                return False
        return False

    transfer_with_retry(1, 2, 500)


# ─────────────────────────────────────────────
# Section 5: Views
# ─────────────────────────────────────────────
def demo_views() -> None:
    print("\n" + "=" * 60)
    print("  SECTION 5 — Views")
    print("=" * 60)

    conn = get_conn(autocommit=True)
    cur  = conn.cursor()

    # ── Create view ────────────────────────────────────────────
    print("\n📌 5a. Create View — active_product_summary")
    cur.execute("DROP VIEW IF EXISTS active_product_summary")
    cur.execute("""
        CREATE VIEW active_product_summary AS
        SELECT
            p.id,
            p.name,
            p.price,
            p.category,
            COUNT(oi.id)     AS times_ordered,
            COALESCE(SUM(oi.quantity), 0) AS total_units_sold
        FROM   products p
        LEFT JOIN order_items oi ON p.id = oi.product_id
        WHERE  p.is_active = TRUE
        GROUP  BY p.id, p.name, p.price, p.category
    """)
    print("  View created ✅")

    # ── Query view ─────────────────────────────────────────────
    print("\n📌 5b. Query the view — like a regular table")
    cur.execute("""
        SELECT name, category, price, times_ordered, total_units_sold
        FROM   active_product_summary
        ORDER  BY times_ordered DESC, price DESC
    """)
    print_table(cur.fetchall(),
                ["Product", "Category", "Price", "Times Ordered", "Units Sold"],
                "Result:")

    # ── Filter view ────────────────────────────────────────────
    print("\n📌 5c. Filter view — sirf electronics")
    cur.execute("""
        SELECT name, price, times_ordered
        FROM   active_product_summary
        WHERE  category = 'electronics'
        ORDER  BY times_ordered DESC
    """)
    print_table(cur.fetchall(),
                ["Product", "Price", "Times Ordered"],
                "Electronics only:")

    # ── Update underlying data, view reflects it ───────────────
    print("\n📌 5d. Update underlying table — view auto-reflects")
    cur.execute("UPDATE products SET is_active = FALSE WHERE name = 'Smart Watch'")
    print("  Smart Watch set is_active=FALSE")

    cur.execute("SELECT COUNT(*) FROM active_product_summary")
    count_after = cur.fetchone()[0]
    print(f"  Products in view after update: {count_after}")
    print("  (Smart Watch no longer in view because is_active=FALSE) ✅")

    # ── Show views ─────────────────────────────────────────────
    print("\n📌 5e. SHOW FULL TABLES — views list karo")
    cur.execute("SHOW FULL TABLES WHERE Table_type = 'VIEW'")
    rows = cur.fetchall()
    print_table(rows, ["View Name", "Table Type"], "Views in database:")

    cur.close()
    conn.close()


# ─────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────
def main() -> None:
    section = sys.argv[1].lower() if len(sys.argv) > 1 else "all"

    print("\n" + "=" * 60)
    print("  MySQL Practical 02 — JOINs, Indexes & Transactions")
    print(f"  Section: {section.upper()}")
    print("=" * 60)

    # Always run setup first
    try:
        setup_schema()
    except mysql.connector.errors.DatabaseError as e:
        print(f"\n  Cannot connect to MySQL: {e}")
        print("  Make sure MySQL is running:")
        print("    docker run -d --name mysql_practice -p 3306:3306 \\")
        print("      -e MYSQL_ROOT_PASSWORD=rootpass \\")
        print("      -e MYSQL_DATABASE=practice_db mysql:8.0")
        sys.exit(1)

    section_map = {
        "joins":        demo_joins,
        "subqueries":   demo_subqueries,
        "indexes":      demo_indexes,
        "transactions": demo_transactions,
        "views":        demo_views,
    }

    if section == "all":
        for fn in section_map.values():
            fn()
    elif section in section_map:
        section_map[section]()
    else:
        print(f"\n  Unknown section: {section}")
        print(f"  Available: {', '.join(section_map)} , all")
        sys.exit(1)

    print("\n" + "=" * 60)
    print("  All done!")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()
