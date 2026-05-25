"""
MySQL Practical 03 — Window Functions, CTEs, Query Optimization
================================================================
Topics: Window Functions, CTEs (Basic/Multiple/Recursive),
        EXPLAIN analysis, Query optimization patterns,
        Performance tips (bulk insert, connection pool)

Run:
    python 03_advanced_optimization.py window
    python 03_advanced_optimization.py cte
    python 03_advanced_optimization.py explain
    python 03_advanced_optimization.py optimization
    python 03_advanced_optimization.py partition
    python 03_advanced_optimization.py all

Prerequisites:
    pip install mysql-connector-python
    MySQL 8.0+ running locally
    DB: practice_db (ya apna config neeche update karo)
"""

import sys
import time
import random
import json
from datetime import datetime, timedelta

import mysql.connector
from mysql.connector import pooling

# ─── DB Config ───────────────────────────────────────────────────────────────
DB_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "",        # apna password yahan
    "database": "practice_db",
    "port": 3306,
}

CATEGORIES = [
    (1, "Electronics", None),
    (2, "Laptops", 1),
    (3, "Gaming Laptops", 2),
    (4, "Ultrabooks", 2),
    (5, "Mobiles", 1),
    (6, "Android Phones", 5),
    (7, "Clothing", None),
    (8, "Men", 7),
    (9, "Women", 7),
    (10, "Sports", None),
]

PRODUCTS = [
    ("Lenovo Legion 5", 2, 85000),
    ("ASUS ROG Strix", 3, 110000),
    ("Acer Predator", 3, 95000),
    ("Dell XPS 13", 4, 98000),
    ("MacBook Air M2", 4, 115000),
    ("HP Spectre x360", 4, 105000),
    ("Samsung Galaxy S23", 6, 74999),
    ("OnePlus 11", 6, 56999),
    ("Redmi Note 12", 6, 18999),
    ("Oppo Reno 8", 6, 28999),
    ("Men's T-Shirt", 8, 599),
    ("Men's Jeans", 8, 1499),
    ("Men's Jacket", 8, 2999),
    ("Women's Kurti", 9, 799),
    ("Women's Saree", 9, 2499),
    ("Women's Dress", 9, 1899),
    ("Running Shoes", 10, 3499),
    ("Cricket Kit", 10, 8999),
    ("Gym Gloves", 10, 499),
    ("Yoga Mat", 10, 999),
]

STATUSES = ["pending", "paid", "shipped", "delivered", "cancelled", "refunded"]
STATUS_WEIGHTS = [5, 15, 10, 50, 15, 5]   # delivered most common

CITIES = ["Mumbai", "Delhi", "Bengaluru", "Hyderabad", "Chennai", "Pune", "Kolkata"]

# ─── Helpers ─────────────────────────────────────────────────────────────────

def get_connection():
    return mysql.connector.connect(**DB_CONFIG)


def separator(title: str, char: str = "=", width: int = 70):
    print(f"\n{char * width}")
    print(f"  {title}")
    print(f"{char * width}")


def print_rows(rows, headers=None, max_col_width=20):
    """Simple tabular print."""
    if not rows:
        print("  (no rows)")
        return
    if headers is None and isinstance(rows[0], dict):
        headers = list(rows[0].keys())
    if headers:
        col_w = [min(max_col_width, max(len(str(h)), max(len(str(r[h] if isinstance(r, dict) else r[i])) for r in rows)))
                 for i, h in enumerate(headers)]
        row_fmt = "  " + "  ".join(f"{{:<{w}}}" for w in col_w)
        print(row_fmt.format(*headers))
        print("  " + "  ".join("-" * w for w in col_w))
        for r in rows:
            vals = [r[h] if isinstance(r, dict) else r[i] for i, h in enumerate(headers)]
            vals = [str(v)[:max_col_width] if v is not None else "NULL" for v in vals]
            print(row_fmt.format(*vals))
    else:
        for r in rows:
            print(" ", r)


# ─── Setup ───────────────────────────────────────────────────────────────────

def setup_analytics_data():
    """
    Demo tables create karo aur realistic seed data insert karo.
    Tables: users, categories, products, orders
    Data: 10 users, 20 products, 5 categories, 300+ orders (12 months)
    """
    separator("SETUP — Creating tables and seeding data")
    conn = get_connection()
    cur = conn.cursor()

    # Drop & recreate
    cur.execute("DROP TABLE IF EXISTS orders")
    cur.execute("DROP TABLE IF EXISTS products")
    cur.execute("DROP TABLE IF EXISTS users")
    cur.execute("DROP TABLE IF EXISTS categories")

    cur.execute("""
        CREATE TABLE categories (
            id INT PRIMARY KEY,
            name VARCHAR(100) NOT NULL,
            parent_id INT,
            FOREIGN KEY (parent_id) REFERENCES categories(id)
        )
    """)

    cur.execute("""
        CREATE TABLE users (
            id INT AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(100) NOT NULL,
            email VARCHAR(150) UNIQUE NOT NULL,
            city VARCHAR(50),
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cur.execute("""
        CREATE TABLE products (
            id INT AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(200) NOT NULL,
            category_id INT,
            price DECIMAL(10,2) NOT NULL,
            stock INT DEFAULT 100,
            FOREIGN KEY (category_id) REFERENCES categories(id)
        )
    """)

    cur.execute("""
        CREATE TABLE orders (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT NOT NULL,
            product_id INT NOT NULL,
            quantity INT DEFAULT 1,
            total_amount DECIMAL(10,2) NOT NULL,
            status VARCHAR(20) NOT NULL,
            created_at DATETIME NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id),
            FOREIGN KEY (product_id) REFERENCES products(id)
        )
    """)

    # Insert categories (self-referential — parent first)
    for cat in CATEGORIES:
        cur.execute("INSERT INTO categories (id, name, parent_id) VALUES (%s, %s, %s)", cat)

    # Insert 10 users
    names = ["Aarav Sharma", "Priya Verma", "Rohit Gupta", "Sneha Patel",
             "Arjun Singh", "Kavya Reddy", "Nikhil Joshi", "Pooja Nair",
             "Raj Kumar", "Ananya Iyer"]
    for i, name in enumerate(names, 1):
        fname = name.split()[0].lower()
        city = random.choice(CITIES)
        cur.execute(
            "INSERT INTO users (name, email, city) VALUES (%s, %s, %s)",
            (name, f"{fname}{i}@example.com", city)
        )

    # Insert 20 products
    for pname, cat_id, price in PRODUCTS:
        cur.execute(
            "INSERT INTO products (name, category_id, price) VALUES (%s, %s, %s)",
            (pname, cat_id, price)
        )

    # Seed 360 orders — 12 months of data
    base_date = datetime(2024, 1, 1)
    orders = []
    product_ids = list(range(1, 21))
    for day in range(365):
        order_date = base_date + timedelta(days=day)
        num_orders = random.randint(0, 3)
        for _ in range(num_orders):
            uid = random.randint(1, 10)
            pid = random.choice(product_ids)
            price = PRODUCTS[pid - 1][2]
            qty = random.randint(1, 3)
            total = round(price * qty * random.uniform(0.9, 1.0), 2)
            status = random.choices(STATUSES, weights=STATUS_WEIGHTS)[0]
            jitter = timedelta(hours=random.randint(0, 20), minutes=random.randint(0, 59))
            orders.append((uid, pid, qty, total, status, order_date + jitter))

    cur.executemany(
        "INSERT INTO orders (user_id, product_id, quantity, total_amount, status, created_at) "
        "VALUES (%s, %s, %s, %s, %s, %s)",
        orders
    )

    conn.commit()
    print(f"  Categories inserted : {len(CATEGORIES)}")
    print(f"  Users inserted      : 10")
    print(f"  Products inserted   : {len(PRODUCTS)}")
    print(f"  Orders inserted     : {len(orders)}")
    cur.close()
    conn.close()
    print("  Setup complete!")


# ─── Section A: Window Functions ─────────────────────────────────────────────

def demo_window_functions():
    separator("DEMO A — Window Functions (MySQL 8.0+)")
    conn = get_connection()
    cur = conn.cursor(dictionary=True)

    # 1. ROW_NUMBER per category — top products by price
    print("\n[1] ROW_NUMBER — Top 2 products per category (by price desc)")
    cur.execute("""
        SELECT * FROM (
            SELECT
                p.name AS product,
                c.name AS category,
                p.price,
                ROW_NUMBER() OVER (PARTITION BY p.category_id ORDER BY p.price DESC) AS rn
            FROM products p
            JOIN categories c ON p.category_id = c.id
        ) ranked
        WHERE rn <= 2
        ORDER BY category, rn
    """)
    rows = cur.fetchall()
    print_rows(rows, headers=["product", "category", "price", "rn"])

    # 2. RANK vs DENSE_RANK
    print("\n[2] RANK vs DENSE_RANK — ties mein difference")
    cur.execute("""
        SELECT name, price,
            RANK()       OVER (ORDER BY price DESC) AS `rank`,
            DENSE_RANK() OVER (ORDER BY price DESC) AS dense_rank
        FROM products
        ORDER BY price DESC
        LIMIT 8
    """)
    rows = cur.fetchall()
    print_rows(rows, headers=["name", "price", "rank", "dense_rank"])
    print("  NOTE: RANK mein gaps hote hain (1,1,3), DENSE_RANK mein nahi (1,1,2)")

    # 3. Running total
    print("\n[3] Running total — cumulative revenue by month")
    cur.execute("""
        WITH monthly AS (
            SELECT
                DATE_FORMAT(created_at, '%Y-%m') AS month,
                ROUND(SUM(total_amount), 2) AS revenue
            FROM orders
            WHERE status = 'delivered'
            GROUP BY DATE_FORMAT(created_at, '%Y-%m')
        )
        SELECT month, revenue,
            ROUND(SUM(revenue) OVER (ORDER BY month), 2) AS running_total
        FROM monthly
        ORDER BY month
    """)
    rows = cur.fetchall()
    print_rows(rows, headers=["month", "revenue", "running_total"])

    # 4. LAG — day-over-day revenue change
    print("\n[4] LAG — Day-over-day revenue change (last 10 days with data)")
    cur.execute("""
        WITH daily AS (
            SELECT
                DATE(created_at) AS sale_date,
                ROUND(SUM(total_amount), 2) AS daily_revenue
            FROM orders
            WHERE status IN ('paid', 'delivered', 'shipped')
            GROUP BY DATE(created_at)
        )
        SELECT sale_date, daily_revenue,
            LAG(daily_revenue, 1) OVER (ORDER BY sale_date) AS prev_day,
            ROUND(
                daily_revenue - LAG(daily_revenue, 1) OVER (ORDER BY sale_date),
                2
            ) AS day_change
        FROM daily
        ORDER BY sale_date DESC
        LIMIT 10
    """)
    rows = cur.fetchall()
    print_rows(rows, headers=["sale_date", "daily_revenue", "prev_day", "day_change"])

    # 5. NTILE — price quartiles
    print("\n[5] NTILE(4) — products price quartile mein distribute karo")
    cur.execute("""
        SELECT name, price,
            NTILE(4) OVER (ORDER BY price) AS price_quartile
        FROM products
        ORDER BY price
    """)
    rows = cur.fetchall()
    print_rows(rows, headers=["name", "price", "price_quartile"])
    print("  Q1=cheapest 25%, Q4=most expensive 25%")

    cur.close()
    conn.close()


# ─── Section B: CTEs ─────────────────────────────────────────────────────────

def demo_ctes():
    separator("DEMO B — CTEs (Common Table Expressions)")
    conn = get_connection()
    cur = conn.cursor(dictionary=True)

    # 1. Basic CTE — Monthly revenue with % contribution
    print("\n[1] Basic CTE — Monthly revenue + % contribution")
    cur.execute("""
        WITH monthly_revenue AS (
            SELECT
                DATE_FORMAT(created_at, '%Y-%m') AS month,
                ROUND(SUM(total_amount), 2) AS revenue,
                COUNT(*) AS order_count
            FROM orders
            WHERE status = 'delivered'
            GROUP BY DATE_FORMAT(created_at, '%Y-%m')
        )
        SELECT month, revenue, order_count,
            ROUND(revenue / order_count, 2) AS avg_order_value,
            ROUND(revenue / SUM(revenue) OVER () * 100, 1) AS revenue_pct
        FROM monthly_revenue
        ORDER BY month
    """)
    rows = cur.fetchall()
    print_rows(rows, headers=["month", "revenue", "order_count", "avg_order_value", "revenue_pct"])

    # 2. Multiple CTEs — top customers + their details
    print("\n[2] Multiple CTEs — Top 5 customers with spending details")
    cur.execute("""
        WITH
        top_customers AS (
            SELECT user_id,
                   ROUND(SUM(total_amount), 2) AS total_spent,
                   COUNT(*) AS num_orders
            FROM orders
            WHERE status != 'cancelled'
            GROUP BY user_id
            ORDER BY total_spent DESC
            LIMIT 5
        ),
        customer_details AS (
            SELECT u.id, u.name, u.email, u.city
            FROM users u
            JOIN top_customers tc ON u.id = tc.user_id
        )
        SELECT cd.name, cd.city, tc.total_spent, tc.num_orders,
               ROUND(tc.total_spent / tc.num_orders, 2) AS avg_per_order
        FROM customer_details cd
        JOIN top_customers tc ON cd.id = tc.user_id
        ORDER BY tc.total_spent DESC
    """)
    rows = cur.fetchall()
    print_rows(rows, headers=["name", "city", "total_spent", "num_orders", "avg_per_order"])

    # 3. Recursive CTE — category hierarchy tree
    print("\n[3] Recursive CTE — Category hierarchy tree")
    cur.execute("""
        WITH RECURSIVE category_tree AS (
            -- Base case: root categories (no parent)
            SELECT id, name, parent_id, 0 AS level, name AS path
            FROM categories
            WHERE parent_id IS NULL

            UNION ALL

            -- Recursive case: child categories
            SELECT c.id, c.name, c.parent_id,
                   ct.level + 1,
                   CONCAT(ct.path, ' > ', c.name)
            FROM categories c
            JOIN category_tree ct ON c.parent_id = ct.id
        )
        SELECT id, level, path
        FROM category_tree
        ORDER BY path
    """)
    rows = cur.fetchall()
    print("\n  Category Tree:")
    for row in rows:
        indent = "  " + ("    " * row["level"])
        level_marker = "├─" if row["level"] > 0 else "◆"
        print(f"{indent}{level_marker} {row['path'].split(' > ')[-1]}  (id={row['id']}, level={row['level']})")

    print("\n  Full paths:")
    for row in rows:
        print(f"  {row['path']}")

    cur.close()
    conn.close()


# ─── Section C: EXPLAIN Analysis ─────────────────────────────────────────────

def demo_explain_analysis():
    separator("DEMO C — EXPLAIN Analysis")
    conn = get_connection()
    cur = conn.cursor(dictionary=True)

    print("""
  EXPLAIN key columns:
  ┌────────────┬──────────────────────────────────────────────────────┐
  │ type       │ ALL→index→range→ref→eq_ref→const  (ALL = worst)     │
  │ key        │ NULL = no index used! (problem)                       │
  │ rows       │ Estimated rows scanned (lower = better)              │
  │ Extra      │ Using filesort = bad, Using index = great            │
  └────────────┴──────────────────────────────────────────────────────┘
    """)

    queries_to_analyze = [
        ("Full table scan (no index)",
         "SELECT * FROM orders WHERE total_amount > 50000"),
        ("Primary key lookup (fastest)",
         "SELECT * FROM orders WHERE id = 100"),
        ("JOIN without extra index",
         "SELECT o.id, u.name FROM orders o JOIN users u ON o.user_id = u.id LIMIT 10"),
        ("ORDER BY without index",
         "SELECT * FROM orders ORDER BY total_amount DESC LIMIT 10"),
        ("Subquery",
         "SELECT * FROM users WHERE id IN (SELECT DISTINCT user_id FROM orders WHERE status='delivered')"),
    ]

    for name, sql in queries_to_analyze:
        print(f"\n  Query: {name}")
        print(f"  SQL  : {sql[:80]}{'...' if len(sql) > 80 else ''}")
        try:
            cur.execute(f"EXPLAIN FORMAT=JSON {sql}")
            result = cur.fetchone()
            # result is a dict with key 'EXPLAIN'
            key = list(result.keys())[0]
            plan = json.loads(result[key])
            table_info = plan.get("query_block", {}).get("table", {})
            nested = plan.get("query_block", {}).get("nested_loop", [])

            if table_info:
                tables = [table_info]
            elif nested:
                tables = [n.get("table", {}) for n in nested]
            else:
                tables = []

            for t in tables:
                print(f"    table         : {t.get('table_name', '?')}")
                print(f"    access_type   : {t.get('access_type', '?')}  ← type in EXPLAIN")
                idx = t.get('key', t.get('possible_keys', 'NULL'))
                print(f"    key used      : {idx}")
                print(f"    rows_examined : {t.get('rows_examined_per_scan', '?')}")
                used_cols = t.get('used_columns', [])
                if used_cols:
                    print(f"    used_columns  : {used_cols[:5]}{'...' if len(used_cols) > 5 else ''}")
                attached_cond = t.get('attached_condition', '')
                if attached_cond:
                    print(f"    condition     : {str(attached_cond)[:60]}")

        except Exception as e:
            # Fallback to regular EXPLAIN
            cur.execute(f"EXPLAIN {sql}")
            rows = cur.fetchall()
            for r in rows:
                print(f"    table={r.get('table')}  type={r.get('type')}  "
                      f"key={r.get('key') or 'NULL'}  rows={r.get('rows')}  "
                      f"Extra={r.get('Extra') or ''}")

    # Add an index and show difference
    print("\n  --- Adding index on orders.total_amount ---")
    try:
        cur.execute("CREATE INDEX idx_orders_total ON orders(total_amount)")
        print("  Index created: idx_orders_total")
    except mysql.connector.errors.ProgrammingError:
        print("  Index already exists — skipping")

    print("\n  Re-running query after index:")
    cur.execute("EXPLAIN SELECT * FROM orders WHERE total_amount > 50000")
    rows = cur.fetchall()
    for r in rows:
        print(f"    type={r.get('type')}  key={r.get('key') or 'NULL'}  "
              f"rows={r.get('rows')}  Extra={r.get('Extra') or ''}")
    print("  NOTE: type should now be 'range' instead of 'ALL'")

    cur.close()
    conn.close()


# ─── Section D: Query Optimization ───────────────────────────────────────────

def demo_query_optimization():
    separator("DEMO D — Query Optimization: Bad vs Good patterns")
    conn = get_connection()
    cur = conn.cursor(dictionary=True)

    # Helper: time a query
    def time_query(label, sql, params=None):
        start = time.perf_counter()
        if params:
            cur.execute(sql, params)
        else:
            cur.execute(sql)
        rows = cur.fetchall()
        elapsed = (time.perf_counter() - start) * 1000
        print(f"  [{label:30s}] {elapsed:7.2f} ms  | rows={len(rows)}")
        return rows

    # ── 1. SELECT * vs SELECT columns ──────────────────────────────────────
    print("\n[1] SELECT * vs SELECT specific columns")
    time_query("SELECT *", "SELECT * FROM orders WHERE status = 'delivered'")
    time_query("SELECT specific cols", "SELECT id, user_id, total_amount, created_at FROM orders WHERE status = 'delivered'")
    print("  NOTE: Difference badi tables pe aur zyada saaf dikhta hai.")

    # ── 2. Function on indexed column ──────────────────────────────────────
    print("\n[2] Function on indexed column vs range query")
    # Make sure index on created_at exists
    try:
        cur.execute("CREATE INDEX idx_orders_created ON orders(created_at)")
    except mysql.connector.errors.ProgrammingError:
        pass

    time_query("YEAR() — breaks index", "SELECT * FROM orders WHERE YEAR(created_at) = 2024")
    time_query("BETWEEN — uses index", "SELECT * FROM orders WHERE created_at BETWEEN '2024-01-01' AND '2024-12-31 23:59:59'")

    # ── 3. LIKE patterns ──────────────────────────────────────────────────
    print("\n[3] LIKE — leading wildcard vs prefix match")
    time_query("LIKE '%shirt%' (full scan)", "SELECT * FROM products WHERE name LIKE '%shirt%'")
    time_query("LIKE 'Men%'  (prefix)", "SELECT * FROM products WHERE name LIKE 'Men%'")

    # ── 4. NOT IN vs NOT EXISTS ───────────────────────────────────────────
    print("\n[4] NOT IN vs NOT EXISTS")
    time_query("NOT IN subquery", "SELECT id, name FROM users WHERE id NOT IN (SELECT DISTINCT user_id FROM orders)")
    time_query("NOT EXISTS", "SELECT id, name FROM users u WHERE NOT EXISTS (SELECT 1 FROM orders o WHERE o.user_id = u.id)")

    # ── 5. Loop insert vs executemany (bulk) ──────────────────────────────
    print("\n[5] Loop INSERT vs executemany (bulk insert)")
    cur.execute("DROP TABLE IF EXISTS bulk_test")
    cur.execute("""
        CREATE TABLE bulk_test (
            id INT AUTO_INCREMENT PRIMARY KEY,
            val INT,
            txt VARCHAR(50)
        )
    """)

    # Bad: Loop
    start = time.perf_counter()
    conn.autocommit = False
    for i in range(200):
        cur.execute("INSERT INTO bulk_test (val, txt) VALUES (%s, %s)", (i, f"row_{i}"))
    conn.commit()
    loop_ms = (time.perf_counter() - start) * 1000
    print(f"  [Loop INSERT — 200 rows       ] {loop_ms:7.2f} ms")

    # Truncate
    cur.execute("TRUNCATE TABLE bulk_test")

    # Good: executemany
    start = time.perf_counter()
    data = [(i, f"row_{i}") for i in range(200)]
    cur.executemany("INSERT INTO bulk_test (val, txt) VALUES (%s, %s)", data)
    conn.commit()
    bulk_ms = (time.perf_counter() - start) * 1000
    print(f"  [executemany — 200 rows       ] {bulk_ms:7.2f} ms")

    speedup = loop_ms / bulk_ms if bulk_ms > 0 else 0
    print(f"  Speedup: {speedup:.1f}x faster with executemany!")

    cur.execute("DROP TABLE IF EXISTS bulk_test")
    conn.commit()
    conn.autocommit = True

    cur.close()
    conn.close()


# ─── Section E: Performance Tips ─────────────────────────────────────────────

def demo_performance_tips():
    separator("DEMO E — Performance Tips & Connection Pool")

    # ── 1. Connection Pool demo ────────────────────────────────────────────
    print("\n[1] Connection Pool vs Single Connection")

    pool_config = {**DB_CONFIG, "pool_name": "mypool", "pool_size": 5}

    # Single connection benchmark
    start = time.perf_counter()
    for _ in range(10):
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT 1")
        cur.fetchone()
        cur.close()
        conn.close()
    single_ms = (time.perf_counter() - start) * 1000
    print(f"  [10x new connections (single)] {single_ms:7.2f} ms")

    # Pool benchmark
    try:
        pool = pooling.MySQLConnectionPool(**pool_config)
        start = time.perf_counter()
        for _ in range(10):
            conn = pool.get_connection()
            cur = conn.cursor()
            cur.execute("SELECT 1")
            cur.fetchone()
            cur.close()
            conn.close()  # Returns to pool, doesn't actually close
        pool_ms = (time.perf_counter() - start) * 1000
        print(f"  [10x pool connections        ] {pool_ms:7.2f} ms")
        speedup = single_ms / pool_ms if pool_ms > 0 else 0
        print(f"  Pool is ~{speedup:.1f}x faster — no TCP handshake overhead!")
    except Exception as e:
        print(f"  Pool demo error: {e}")

    # ── 2. Index impact demo ──────────────────────────────────────────────
    print("\n[2] Index impact — add/drop index and compare")
    conn = get_connection()
    cur = conn.cursor(dictionary=True)

    # Drop status index if exists
    try:
        cur.execute("DROP INDEX idx_orders_status ON orders")
        conn.commit()
    except Exception:
        pass

    def run_status_query():
        start = time.perf_counter()
        cur.execute("SELECT COUNT(*) AS cnt FROM orders WHERE status = 'delivered'")
        cur.fetchone()
        return (time.perf_counter() - start) * 1000

    ms_no_index = run_status_query()
    print(f"  Without index on status: {ms_no_index:.2f} ms")

    cur.execute("CREATE INDEX idx_orders_status ON orders(status)")
    conn.commit()

    ms_with_index = run_status_query()
    print(f"  With index on status   : {ms_with_index:.2f} ms")
    print(f"  Improvement            : {ms_no_index - ms_with_index:.2f} ms")

    # ── 3. Covering Index demo ─────────────────────────────────────────────
    print("\n[3] Covering Index — Using index (no table lookup)")
    # Composite index covering the query
    try:
        cur.execute("CREATE INDEX idx_cover ON orders(status, total_amount, created_at)")
        conn.commit()
    except Exception:
        pass

    cur.execute("EXPLAIN SELECT status, total_amount, created_at FROM orders WHERE status = 'delivered'")
    rows = cur.fetchall()
    for r in rows:
        extra = r.get('Extra', '')
        key = r.get('key', 'NULL')
        print(f"  key={key}  Extra={extra}")
        if 'Using index' in (extra or ''):
            print("  'Using index' = COVERING INDEX! Table rows touch nahi hue.")

    # ── 4. Useful monitoring queries ──────────────────────────────────────
    print("\n[4] Monitoring — useful status queries")
    monitoring = [
        ("Threads connected", "SHOW STATUS LIKE 'Threads_connected'"),
        ("Max used connections", "SHOW STATUS LIKE 'Max_used_connections'"),
        ("InnoDB buffer pool reads", "SHOW STATUS LIKE 'Innodb_buffer_pool_reads'"),
        ("InnoDB buffer pool read requests", "SHOW STATUS LIKE 'Innodb_buffer_pool_read_requests'"),
        ("Slow queries", "SHOW STATUS LIKE 'Slow_queries'"),
    ]
    for label, sql in monitoring:
        cur.execute(sql)
        row = cur.fetchone()
        if row:
            val = row.get("Value", "?")
            print(f"  {label:40s}: {val}")

    # ── 5. Show indexes on orders ──────────────────────────────────────────
    print("\n[5] All indexes on orders table")
    cur.execute("SHOW INDEX FROM orders")
    rows = cur.fetchall()
    seen = set()
    for r in rows:
        key_name = r.get("Key_name")
        col = r.get("Column_name")
        idx_type = r.get("Index_type")
        if key_name not in seen:
            print(f"  {key_name:30s}  column={col:20s}  type={idx_type}")
            seen.add(key_name)

    cur.close()
    conn.close()


# ─── Section F: Partition Demo ────────────────────────────────────────────────

def demo_partitioning():
    separator("DEMO F — Partitioning (RANGE by year)")
    conn = get_connection()
    cur = conn.cursor(dictionary=True)

    # Create partitioned table
    cur.execute("DROP TABLE IF EXISTS orders_partitioned")
    cur.execute("""
        CREATE TABLE orders_partitioned (
            id INT NOT NULL AUTO_INCREMENT,
            user_id INT NOT NULL,
            total_amount DECIMAL(10,2),
            status VARCHAR(20),
            created_at DATETIME NOT NULL,
            PRIMARY KEY (id, created_at)
        )
        PARTITION BY RANGE (YEAR(created_at)) (
            PARTITION p2022 VALUES LESS THAN (2023),
            PARTITION p2023 VALUES LESS THAN (2024),
            PARTITION p2024 VALUES LESS THAN (2025),
            PARTITION p_future VALUES LESS THAN MAXVALUE
        )
    """)
    print("  Partitioned table created with 4 partitions (2022, 2023, 2024, future)")

    # Insert data across years
    data = []
    for year in [2022, 2023, 2024, 2025]:
        for _ in range(50):
            data.append((
                random.randint(1, 10),
                round(random.uniform(500, 100000), 2),
                random.choice(STATUSES),
                datetime(year, random.randint(1, 12), random.randint(1, 28),
                         random.randint(0, 23))
            ))
    cur.executemany(
        "INSERT INTO orders_partitioned (user_id, total_amount, status, created_at) VALUES (%s, %s, %s, %s)",
        data
    )
    conn.commit()
    print(f"  Inserted {len(data)} rows across 2022-2025")

    # Show partition info
    print("\n  Partition row counts:")
    cur.execute("""
        SELECT PARTITION_NAME, TABLE_ROWS
        FROM information_schema.PARTITIONS
        WHERE TABLE_SCHEMA = %s AND TABLE_NAME = 'orders_partitioned'
        ORDER BY PARTITION_NAME
    """, (DB_CONFIG["database"],))
    rows = cur.fetchall()
    for r in rows:
        print(f"    {r['PARTITION_NAME']:15s}: {r['TABLE_ROWS']} rows (approximate)")

    # EXPLAIN to show partition pruning
    print("\n  Partition pruning demo (EXPLAIN):")
    cur.execute("EXPLAIN SELECT * FROM orders_partitioned WHERE YEAR(created_at) = 2024")
    rows = cur.fetchall()
    for r in rows:
        partitions = r.get("partitions", "N/A")
        type_val = r.get("type", "N/A")
        print(f"    type={type_val}  partitions={partitions}")
        print(f"    Only 'p2024' scanned — others pruned!")

    # Cleanup
    cur.execute("DROP TABLE IF EXISTS orders_partitioned")
    conn.commit()
    print("\n  Partitioned table dropped (cleanup)")

    cur.close()
    conn.close()


# ─── Main Dispatcher ──────────────────────────────────────────────────────────

def main():
    args = sys.argv[1:]
    mode = args[0].lower() if args else "all"

    print("=" * 70)
    print("  MySQL Practical 03 — Window Functions, CTEs, Optimization")
    print("=" * 70)

    # Always setup data first
    try:
        setup_analytics_data()
    except mysql.connector.Error as e:
        print(f"\n  ERROR: Could not connect to MySQL — {e}")
        print(f"  Check DB_CONFIG at top of file (host, user, password, database)")
        sys.exit(1)

    demos = {
        "window":       demo_window_functions,
        "cte":          demo_ctes,
        "explain":      demo_explain_analysis,
        "optimization": demo_query_optimization,
        "partition":    demo_partitioning,
        "perf":         demo_performance_tips,
    }

    if mode == "all":
        for fn in demos.values():
            fn()
    elif mode in demos:
        demos[mode]()
    else:
        print(f"\n  Unknown mode: '{mode}'")
        print(f"  Available: {', '.join(demos.keys())}, all")
        sys.exit(1)

    separator("All demos complete!", char="-")


if __name__ == "__main__":
    main()
