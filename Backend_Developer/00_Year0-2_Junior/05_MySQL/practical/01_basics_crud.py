"""
MySQL Practical 01 — Basics, Installation & CRUD
=================================================
Run: python 01_basics_crud.py [connection|ddl|crud|bulk|datatypes|all]

Prerequisites:
  pip install mysql-connector-python pymysql

  Docker se MySQL run karo:
  docker run -d --name mysql -p 3306:3306 \\
    -e MYSQL_ROOT_PASSWORD=rootpass \\
    -e MYSQL_DATABASE=practice_db \\
    -e MYSQL_USER=myuser \\
    -e MYSQL_PASSWORD=mypass \\
    mysql:8.0

  Verify running:
  docker ps | grep mysql
  mysql -h 127.0.0.1 -P 3306 -u myuser -pmypass practice_db
"""

import sys
import time
from contextlib import contextmanager
from typing import Any, Dict, List, Optional

# ─── Try importing MySQL clients ───
try:
    import mysql.connector
    from mysql.connector import Error as MySQLError
    CONNECTOR = "mysql-connector-python"
except ImportError:
    try:
        import pymysql
        import pymysql.cursors
        mysql = None
        CONNECTOR = "pymysql"
    except ImportError:
        print("❌ No MySQL client found!")
        print("   Install: pip install mysql-connector-python")
        sys.exit(1)

# ─── Connection config ───
DB_CONFIG = {
    "host": "127.0.0.1",
    "port": 3306,
    "user": "myuser",
    "password": "mypass",
    "database": "practice_db",
    "charset": "utf8mb4",
    "autocommit": False,
}

DIVIDER = "═" * 60


# ══════════════════════════════════════════════════════════
# HELPER: Context Manager for DB connection
# ══════════════════════════════════════════════════════════

@contextmanager
def get_db(dictionary: bool = True):
    """
    Context manager — auto commit/rollback/close karta hai.

    Usage:
        with get_db() as (cursor, conn):
            cursor.execute("SELECT ...")
            rows = cursor.fetchall()
    """
    conn = None
    cursor = None
    try:
        if mysql is not None:
            conn = mysql.connector.connect(**DB_CONFIG)
            cursor = conn.cursor(dictionary=dictionary)
        else:
            import pymysql
            conn = pymysql.connect(
                **DB_CONFIG,
                cursorclass=pymysql.cursors.DictCursor if dictionary else pymysql.cursors.Cursor
            )
            cursor = conn.cursor()

        yield cursor, conn
        conn.commit()

    except Exception as e:
        if conn:
            conn.rollback()
        raise
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


def check_mysql_running():
    """MySQL running hai ya nahi check karo"""
    try:
        with get_db() as (cursor, conn):
            cursor.execute("SELECT 1")
        return True
    except Exception as e:
        print(f"\n❌ MySQL se connect nahi ho pa raha!")
        print(f"   Error: {e}")
        print(f"\n   Docker se start karo:")
        print(f"   docker run -d --name mysql -p 3306:3306 \\")
        print(f"     -e MYSQL_ROOT_PASSWORD=rootpass \\")
        print(f"     -e MYSQL_DATABASE=practice_db \\")
        print(f"     -e MYSQL_USER=myuser \\")
        print(f"     -e MYSQL_PASSWORD=mypass \\")
        print(f"     mysql:8.0")
        print(f"\n   Ya agar container already hai:")
        print(f"   docker start mysql")
        return False


# ══════════════════════════════════════════════════════════
# SECTION 1: CONNECTION TEST
# ══════════════════════════════════════════════════════════

def demo_connection():
    """
    MySQL connection test karo — version, databases, charset info.
    """
    print(f"\n{DIVIDER}")
    print("🔌 SECTION 1: CONNECTION & SERVER INFO")
    print(DIVIDER)

    with get_db() as (cursor, conn):

        # ─── MySQL Version ───
        cursor.execute("SELECT VERSION() AS version")
        row = cursor.fetchone()
        print(f"\n✅ Connected to MySQL!")
        print(f"   Server Version : {row['version']}")
        print(f"   Client Library : {CONNECTOR}")

        # ─── Current Database & User ───
        cursor.execute("SELECT DATABASE() AS db, USER() AS user_name")
        row = cursor.fetchone()
        print(f"   Database       : {row['db']}")
        print(f"   User           : {row['user_name']}")

        # ─── Character Set ───
        cursor.execute("SHOW VARIABLES LIKE 'character_set_database'")
        row = cursor.fetchone()
        if row:
            print(f"   Charset        : {row.get('Value', row)}")

        cursor.execute("SHOW VARIABLES LIKE 'collation_database'")
        row = cursor.fetchone()
        if row:
            print(f"   Collation      : {row.get('Value', row)}")

        # ─── List all databases ───
        cursor.execute("SHOW DATABASES")
        dbs = cursor.fetchall()
        print(f"\n📂 Available Databases:")
        for db in dbs:
            name = db.get('Database', list(db.values())[0])
            print(f"   - {name}")

        # ─── Connection variables ───
        cursor.execute("SHOW VARIABLES LIKE 'max_connections'")
        row = cursor.fetchone()
        if row:
            print(f"\n⚙️  Max Connections : {row.get('Value', '?')}")

        cursor.execute("SHOW STATUS LIKE 'Threads_connected'")
        row = cursor.fetchone()
        if row:
            print(f"   Current Threads: {row.get('Value', '?')}")

    print(f"\n✅ Connection demo complete!\n")


# ══════════════════════════════════════════════════════════
# SECTION 2: DDL — CREATE, ALTER, DROP
# ══════════════════════════════════════════════════════════

def demo_ddl():
    """
    DDL operations — CREATE TABLE, ALTER, SHOW commands, DROP.
    """
    print(f"\n{DIVIDER}")
    print("🏗️  SECTION 2: DDL — CREATE / ALTER / DROP")
    print(DIVIDER)

    with get_db() as (cursor, conn):

        # ─── Drop if exists (fresh start) ───
        cursor.execute("DROP TABLE IF EXISTS order_items")
        cursor.execute("DROP TABLE IF EXISTS orders")
        cursor.execute("DROP TABLE IF EXISTS products")
        cursor.execute("DROP TABLE IF EXISTS categories")
        print("\n🗑️  Old tables dropped (if existed)")

        # ─── Create categories table ───
        cursor.execute("""
            CREATE TABLE categories (
                id          INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
                name        VARCHAR(100) NOT NULL UNIQUE,
                slug        VARCHAR(100) NOT NULL UNIQUE,
                description TEXT,
                is_active   BOOLEAN NOT NULL DEFAULT TRUE,
                created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """)
        print("✅ Table 'categories' created")

        # ─── Create products table (main table with all data types) ───
        cursor.execute("""
            CREATE TABLE products (
                id           INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
                sku          VARCHAR(50)  NOT NULL UNIQUE,
                name         VARCHAR(200) NOT NULL,
                description  TEXT,
                price        DECIMAL(10, 2) NOT NULL DEFAULT 0.00,
                cost_price   DECIMAL(10, 2),
                stock        INT NOT NULL DEFAULT 0,
                category     ENUM('electronics','clothing','books','sports','home') NOT NULL,
                brand        VARCHAR(100),
                is_active    BOOLEAN NOT NULL DEFAULT TRUE,
                is_featured  BOOLEAN NOT NULL DEFAULT FALSE,
                tags         JSON,
                weight_kg    FLOAT,
                rating       DECIMAL(3, 2) DEFAULT 0.00,
                review_count INT UNSIGNED DEFAULT 0,
                image_url    VARCHAR(500),
                created_at   DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at   DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

                INDEX idx_category   (category),
                INDEX idx_price      (price),
                INDEX idx_brand      (brand),
                INDEX idx_active_cat (is_active, category),
                INDEX idx_featured   (is_featured, is_active)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """)
        print("✅ Table 'products' created")

        # ─── Create orders table (Foreign Key demo) ───
        cursor.execute("""
            CREATE TABLE orders (
                id           INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
                order_number VARCHAR(20) NOT NULL UNIQUE,
                customer_name VARCHAR(200) NOT NULL,
                customer_email VARCHAR(255) NOT NULL,
                total_amount DECIMAL(12, 2) NOT NULL DEFAULT 0.00,
                status       ENUM('pending','confirmed','shipped','delivered','cancelled')
                             NOT NULL DEFAULT 'pending',
                notes        TEXT,
                created_at   DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at   DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

                INDEX idx_email  (customer_email),
                INDEX idx_status (status)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """)
        print("✅ Table 'orders' created")

        # ─── ALTER TABLE examples ───
        print("\n🔧 ALTER TABLE operations:")

        # ADD COLUMN
        cursor.execute("""
            ALTER TABLE products
            ADD COLUMN discount_pct DECIMAL(5, 2) DEFAULT 0.00 AFTER price
        """)
        print("   ✅ Column 'discount_pct' added")

        # MODIFY COLUMN
        cursor.execute("""
            ALTER TABLE products
            MODIFY COLUMN description MEDIUMTEXT
        """)
        print("   ✅ Column 'description' modified to MEDIUMTEXT")

        # ADD INDEX
        cursor.execute("""
            ALTER TABLE products
            ADD INDEX idx_rating (rating)
        """)
        print("   ✅ Index 'idx_rating' added")

        # DROP COLUMN
        cursor.execute("ALTER TABLE products DROP COLUMN weight_kg")
        print("   ✅ Column 'weight_kg' dropped")

        # ─── SHOW commands ───
        print("\n📋 SHOW commands:")

        cursor.execute("SHOW TABLES")
        tables = cursor.fetchall()
        print(f"   Tables in DB: {[list(t.values())[0] for t in tables]}")

        cursor.execute("DESCRIBE products")
        cols = cursor.fetchall()
        print(f"\n   DESCRIBE products ({len(cols)} columns):")
        for col in cols[:5]:  # First 5 only
            field = col.get('Field', col)
            col_type = col.get('Type', '')
            null = col.get('Null', '')
            key = col.get('Key', '')
            key_str = f" [{key}]" if key else ""
            print(f"      {field:<20} {col_type:<25} NULL={null}{key_str}")
        print(f"      ... aur {len(cols) - 5} aur columns")

        cursor.execute("SHOW INDEX FROM products")
        indexes = cursor.fetchall()
        unique_indexes = {i.get('Key_name', '') for i in indexes}
        print(f"\n   Indexes on 'products': {unique_indexes}")

    print(f"\n✅ DDL demo complete!\n")


# ══════════════════════════════════════════════════════════
# SECTION 3: INSERT — Single, Bulk, IGNORE, UPSERT
# ══════════════════════════════════════════════════════════

SEED_PRODUCTS = [
    ("LAPTOP-001", "MacBook Pro 14",         125000.00, 50,  "electronics", "Apple",    True,  True,  4.8, 342),
    ("LAPTOP-002", "Dell XPS 15",             89000.00, 30,  "electronics", "Dell",     True,  False, 4.5, 156),
    ("LAPTOP-003", "Lenovo ThinkPad X1",      95000.00, 25,  "electronics", "Lenovo",   True,  False, 4.6, 210),
    ("PHONE-001",  "iPhone 15 Pro",           79000.00, 100, "electronics", "Apple",    True,  True,  4.7, 892),
    ("PHONE-002",  "Samsung Galaxy S24",      65000.00, 150, "electronics", "Samsung",  True,  True,  4.5, 645),
    ("PHONE-003",  "OnePlus 12",              49000.00, 80,  "electronics", "OnePlus",  True,  False, 4.4, 312),
    ("PHONE-004",  "Pixel 8 Pro",             72000.00, 40,  "electronics", "Google",   True,  False, 4.6, 178),
    ("BOOK-001",   "Clean Code",                499.00, 200, "books",       "OReilly",  True,  True,  4.9, 2341),
    ("BOOK-002",   "Design Patterns",           599.00, 180, "books",       "GoF",      True,  False, 4.8, 1892),
    ("BOOK-003",   "The Pragmatic Programmer",  549.00, 160, "books",       "OReilly",  True,  True,  4.9, 1567),
    ("BOOK-004",   "System Design Interview",   699.00, 220, "books",       "ByteByByte",True, False, 4.7, 943),
    ("SHIRT-001",  "Levi's Classic Tee",       1299.00, 300, "clothing",    "Levis",    True,  False, 4.3, 432),
    ("SHIRT-002",  "Nike Dri-FIT",             1999.00, 250, "clothing",    "Nike",     True,  True,  4.5, 678),
    ("SPORT-001",  "Adidas Running Shoes",     6999.00, 75,  "sports",      "Adidas",   True,  True,  4.6, 234),
    ("SPORT-002",  "Yoga Mat Premium",          899.00, 120, "sports",      "LifeFit",  True,  False, 4.4, 189),
    ("HOME-001",   "Philips Air Purifier",    15000.00, 35,  "home",        "Philips",  True,  False, 4.5, 156),
    ("HOME-002",   "Dyson V11 Vacuum",        35000.00, 20,  "home",        "Dyson",    True,  True,  4.7, 289),
    ("LAPTOP-OLD", "Refurb Dell Laptop",      25000.00, 0,   "electronics", "Dell",     False, False, 3.2, 45),
]


def demo_insert():
    """
    INSERT operations — single, bulk, INSERT IGNORE, ON DUPLICATE KEY.
    """
    print(f"\n{DIVIDER}")
    print("➕ SECTION 3: INSERT — Single, Bulk, IGNORE, UPSERT")
    print(DIVIDER)

    with get_db() as (cursor, conn):

        # ─── Single INSERT ───
        print("\n1️⃣  Single INSERT:")
        cursor.execute("""
            INSERT INTO products (sku, name, price, stock, category, brand, rating)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, ("TEST-001", "Test Product", 999.00, 10, "books", "TestBrand", 4.0))
        print(f"   Inserted 1 row — lastrowid = {cursor.lastrowid}")

        # ─── Bulk INSERT (executemany — much faster!) ───
        print("\n2️⃣  Bulk INSERT (executemany):")
        sql = """
            INSERT INTO products
                (sku, name, price, stock, category, brand, is_active, is_featured, rating, review_count)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        start = time.time()
        cursor.executemany(sql, SEED_PRODUCTS)
        elapsed = (time.time() - start) * 1000
        print(f"   Inserted {cursor.rowcount} rows in {elapsed:.2f}ms")
        print(f"   (executemany = 1 round trip for all rows! ✅)")

        # ─── INSERT IGNORE (duplicate skip) ───
        print("\n3️⃣  INSERT IGNORE (duplicate pe skip):")
        cursor.execute("""
            INSERT IGNORE INTO products (sku, name, price, stock, category)
            VALUES (%s, %s, %s, %s, %s)
        """, ("LAPTOP-001", "Duplicate MacBook", 100.00, 5, "electronics"))
        print(f"   rowcount = {cursor.rowcount}")
        print(f"   (0 = duplicate skip hua, error nahi aaya ✅)")

        # ─── ON DUPLICATE KEY UPDATE (UPSERT) ───
        print("\n4️⃣  ON DUPLICATE KEY UPDATE (UPSERT):")
        new_price = 129000.00
        cursor.execute("""
            INSERT INTO products (sku, name, price, stock, category)
            VALUES (%s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                price  = VALUES(price),
                stock  = VALUES(stock),
                updated_at = CURRENT_TIMESTAMP
        """, ("LAPTOP-001", "MacBook Pro 14 Updated", new_price, 45, "electronics"))
        print(f"   rowcount = {cursor.rowcount}")
        print(f"   (1 = insert, 2 = update, 0 = no change)")

        # Verify upsert
        cursor.execute("SELECT sku, name, price FROM products WHERE sku = %s", ("LAPTOP-001",))
        row = cursor.fetchone()
        print(f"   After upsert: price = ₹{row['price']:,.2f} (was 125000, now {new_price})")

        # ─── INSERT with JSON column ───
        print("\n5️⃣  INSERT with JSON column:")
        import json
        cursor.execute("""
            UPDATE products
            SET tags = %s
            WHERE sku = 'LAPTOP-001'
        """, (json.dumps(["bestseller", "apple", "premium", "m3chip"]),))
        print(f"   JSON tags set for LAPTOP-001")

        # ─── Count total rows ───
        cursor.execute("SELECT COUNT(*) AS total FROM products")
        row = cursor.fetchone()
        print(f"\n📊 Total products in table: {row['total']}")

    print(f"\n✅ INSERT demo complete!\n")


# ══════════════════════════════════════════════════════════
# SECTION 4: SELECT — Filtering, Sorting, Pagination, GROUP BY
# ══════════════════════════════════════════════════════════

def demo_select():
    """
    SELECT operations — WHERE, BETWEEN, IN, LIKE, NULL, ORDER BY, LIMIT, GROUP BY/HAVING.
    """
    print(f"\n{DIVIDER}")
    print("🔍 SECTION 4: SELECT — Filter, Sort, Paginate, Aggregate")
    print(DIVIDER)

    with get_db() as (cursor, conn):

        # ─── Basic SELECT ───
        print("\n1️⃣  Basic SELECT:")
        cursor.execute("SELECT id, sku, name, price, category FROM products LIMIT 3")
        rows = cursor.fetchall()
        for r in rows:
            print(f"   [{r['id']}] {r['sku']:<15} {r['name']:<30} ₹{r['price']:>10,.2f}  ({r['category']})")

        # ─── WHERE conditions ───
        print("\n2️⃣  WHERE — category + price filter:")
        cursor.execute("""
            SELECT sku, name, price
            FROM products
            WHERE category = %s AND price < %s AND is_active = TRUE
            ORDER BY price DESC
        """, ("electronics", 100000))
        rows = cursor.fetchall()
        print(f"   Electronics under ₹1L: {len(rows)} products")
        for r in rows[:3]:
            print(f"   {r['sku']:<15} {r['name']:<30} ₹{r['price']:,.2f}")

        # ─── BETWEEN ───
        print("\n3️⃣  BETWEEN — price range:")
        cursor.execute("""
            SELECT sku, name, price FROM products
            WHERE price BETWEEN %s AND %s
            ORDER BY price
        """, (1000, 10000))
        rows = cursor.fetchall()
        print(f"   Products ₹1K-₹10K: {len(rows)}")
        for r in rows:
            print(f"   {r['sku']:<15} ₹{r['price']:,.2f}")

        # ─── IN clause ───
        print("\n4️⃣  IN clause:")
        categories = ["books", "sports"]
        placeholders = ", ".join(["%s"] * len(categories))
        cursor.execute(f"""
            SELECT sku, name, category FROM products
            WHERE category IN ({placeholders})
            ORDER BY category, name
        """, categories)
        rows = cursor.fetchall()
        print(f"   Books + Sports products: {len(rows)}")
        for r in rows:
            print(f"   [{r['category']:<12}] {r['sku']:<15} {r['name']}")

        # ─── LIKE (wildcard search) ───
        print("\n5️⃣  LIKE — wildcard search:")
        cursor.execute("""
            SELECT sku, name FROM products WHERE name LIKE %s
        """, ("%Pro%",))
        rows = cursor.fetchall()
        print(f"   Products with 'Pro' in name: {len(rows)}")
        for r in rows:
            print(f"   {r['sku']:<15} {r['name']}")

        # ─── NULL check ───
        print("\n6️⃣  NULL check (IS NULL / IS NOT NULL):")
        cursor.execute("SELECT COUNT(*) AS cnt FROM products WHERE tags IS NOT NULL")
        row = cursor.fetchone()
        print(f"   Products with tags (IS NOT NULL): {row['cnt']}")

        cursor.execute("SELECT COUNT(*) AS cnt FROM products WHERE description IS NULL")
        row = cursor.fetchone()
        print(f"   Products without description (IS NULL): {row['cnt']}")

        # ─── JSON_CONTAINS ───
        print("\n7️⃣  JSON_CONTAINS — JSON column search:")
        cursor.execute("""
            SELECT sku, name, tags FROM products
            WHERE JSON_CONTAINS(tags, %s)
        """, ('"bestseller"',))
        rows = cursor.fetchall()
        print(f"   Bestseller tagged products: {len(rows)}")
        for r in rows:
            print(f"   {r['sku']:<15} tags={r['tags']}")

        # ─── ORDER BY multi-column ───
        print("\n8️⃣  ORDER BY — multi-column sort:")
        cursor.execute("""
            SELECT category, name, price, rating
            FROM products
            WHERE is_active = TRUE
            ORDER BY category ASC, price DESC
            LIMIT 6
        """)
        rows = cursor.fetchall()
        print(f"   Sorted by category ASC, price DESC:")
        for r in rows:
            print(f"   [{r['category']:<12}] {r['name']:<35} ₹{r['price']:>10,.2f} ⭐{r['rating']}")

        # ─── LIMIT / OFFSET (Pagination) ───
        print("\n9️⃣  LIMIT/OFFSET — Pagination:")
        page_size = 3
        for page in range(1, 3):
            offset = (page - 1) * page_size
            cursor.execute("""
                SELECT id, name, price FROM products
                WHERE is_active = TRUE
                ORDER BY id
                LIMIT %s OFFSET %s
            """, (page_size, offset))
            rows = cursor.fetchall()
            print(f"   Page {page} (LIMIT {page_size} OFFSET {offset}):")
            for r in rows:
                print(f"     [{r['id']}] {r['name']:<35} ₹{r['price']:,.2f}")

        # ─── Aggregate Functions ───
        print("\n🔟 Aggregate Functions:")
        cursor.execute("""
            SELECT
                COUNT(*)        AS total_products,
                AVG(price)      AS avg_price,
                MAX(price)      AS max_price,
                MIN(price)      AS min_price,
                SUM(stock)      AS total_stock
            FROM products
            WHERE is_active = TRUE
        """)
        row = cursor.fetchone()
        print(f"   Total Products : {row['total_products']}")
        print(f"   Avg Price      : ₹{float(row['avg_price']):,.2f}")
        print(f"   Max Price      : ₹{float(row['max_price']):,.2f}")
        print(f"   Min Price      : ₹{float(row['min_price']):,.2f}")
        print(f"   Total Stock    : {row['total_stock']} units")

        # ─── GROUP BY + HAVING ───
        print("\n1️⃣1️⃣ GROUP BY + HAVING:")
        cursor.execute("""
            SELECT
                category,
                COUNT(*)            AS product_count,
                ROUND(AVG(price),2) AS avg_price,
                SUM(stock)          AS total_stock,
                ROUND(AVG(rating),2) AS avg_rating
            FROM products
            WHERE is_active = TRUE
            GROUP BY category
            HAVING COUNT(*) >= 2
            ORDER BY avg_price DESC
        """)
        rows = cursor.fetchall()
        print(f"   Categories with 2+ products:")
        print(f"   {'Category':<15} {'Count':>6} {'Avg Price':>12} {'Stock':>8} {'Rating':>8}")
        print(f"   {'-'*55}")
        for r in rows:
            print(f"   {r['category']:<15} {r['product_count']:>6} "
                  f"₹{float(r['avg_price']):>10,.2f} {r['total_stock']:>8} "
                  f"⭐{float(r['avg_rating']):>6.2f}")

        # ─── DISTINCT ───
        print("\n1️⃣2️⃣ DISTINCT:")
        cursor.execute("SELECT DISTINCT brand FROM products WHERE brand IS NOT NULL ORDER BY brand")
        brands = [r['brand'] for r in cursor.fetchall()]
        print(f"   Unique brands ({len(brands)}): {', '.join(brands)}")

    print(f"\n✅ SELECT demo complete!\n")


# ══════════════════════════════════════════════════════════
# SECTION 5: UPDATE — Single, Bulk, Calculated
# ══════════════════════════════════════════════════════════

def demo_update():
    """
    UPDATE operations — single row, bulk, calculated updates.
    """
    print(f"\n{DIVIDER}")
    print("✏️  SECTION 5: UPDATE — Single, Bulk, Calculated")
    print(DIVIDER)

    with get_db() as (cursor, conn):

        # ─── Single row UPDATE ───
        print("\n1️⃣  Single row UPDATE:")
        cursor.execute("SELECT price, stock FROM products WHERE sku = %s", ("PHONE-001",))
        before = cursor.fetchone()
        print(f"   Before: price=₹{before['price']:,.2f}, stock={before['stock']}")

        cursor.execute("""
            UPDATE products
            SET price = %s, stock = %s, updated_at = CURRENT_TIMESTAMP
            WHERE sku = %s
        """, (82000.00, 95, "PHONE-001"))
        print(f"   rowcount (rows affected) = {cursor.rowcount}")

        cursor.execute("SELECT price, stock FROM products WHERE sku = %s", ("PHONE-001",))
        after = cursor.fetchone()
        print(f"   After : price=₹{after['price']:,.2f}, stock={after['stock']}")

        # ─── Bulk UPDATE (multiple rows matching condition) ───
        print("\n2️⃣  Bulk UPDATE — mark out-of-stock as inactive:")
        cursor.execute("SELECT COUNT(*) AS cnt FROM products WHERE stock = 0")
        before_cnt = cursor.fetchone()['cnt']
        print(f"   Out-of-stock products: {before_cnt}")

        cursor.execute("""
            UPDATE products
            SET is_active = FALSE
            WHERE stock = 0 AND is_active = TRUE
        """)
        print(f"   Updated {cursor.rowcount} products → is_active = FALSE")

        # ─── Calculated UPDATE (price +10% for electronics) ───
        print("\n3️⃣  Calculated UPDATE — electronics price +10%:")
        cursor.execute("""
            SELECT sku, name, price FROM products
            WHERE category = 'electronics' AND is_active = TRUE
            LIMIT 3
        """)
        rows_before = cursor.fetchall()
        print(f"   Before (sample):")
        for r in rows_before:
            print(f"   {r['sku']:<15} ₹{r['price']:,.2f}")

        cursor.execute("""
            UPDATE products
            SET price = ROUND(price * 1.10, 2)
            WHERE category = %s AND is_active = TRUE
        """, ("electronics",))
        print(f"   Updated {cursor.rowcount} electronics products (+10%)")

        cursor.execute("""
            SELECT sku, name, price FROM products
            WHERE category = 'electronics' AND is_active = TRUE
            LIMIT 3
        """)
        rows_after = cursor.fetchall()
        print(f"   After (same sample):")
        for r in rows_after:
            print(f"   {r['sku']:<15} ₹{r['price']:,.2f}")

        # ─── UPDATE with CASE (different update per row) ───
        print("\n4️⃣  UPDATE with CASE expression (category-specific discount):")
        cursor.execute("""
            UPDATE products
            SET discount_pct = CASE category
                WHEN 'electronics' THEN 5.00
                WHEN 'books'       THEN 15.00
                WHEN 'clothing'    THEN 20.00
                WHEN 'sports'      THEN 10.00
                ELSE 0.00
            END
            WHERE is_active = TRUE
        """)
        print(f"   Updated discounts for {cursor.rowcount} products")

        # Verify
        cursor.execute("""
            SELECT category, AVG(discount_pct) AS avg_discount
            FROM products
            WHERE is_active = TRUE
            GROUP BY category
        """)
        rows = cursor.fetchall()
        print(f"   Discount by category:")
        for r in rows:
            print(f"   [{r['category']:<12}] avg discount = {float(r['avg_discount']):.1f}%")

    print(f"\n✅ UPDATE demo complete!\n")


# ══════════════════════════════════════════════════════════
# SECTION 6: DELETE — With WHERE, Verify, TRUNCATE warning
# ══════════════════════════════════════════════════════════

def demo_delete():
    """
    DELETE operations — targeted delete, verify, TRUNCATE warning.
    """
    print(f"\n{DIVIDER}")
    print("🗑️  SECTION 6: DELETE — WHERE, Verify, TRUNCATE")
    print(DIVIDER)

    with get_db() as (cursor, conn):

        # ─── Count before delete ───
        cursor.execute("SELECT COUNT(*) AS cnt FROM products")
        before = cursor.fetchone()['cnt']
        print(f"\n📊 Before delete: {before} products total")

        # ─── Step 1: SELECT pehle dekho (safe delete practice) ───
        print("\n1️⃣  Safe delete practice — pehle SELECT se verify karo:")
        cursor.execute("""
            SELECT id, sku, name, is_active, stock
            FROM products
            WHERE is_active = FALSE
        """)
        to_delete = cursor.fetchall()
        print(f"   Inactive products (candidates for delete): {len(to_delete)}")
        for r in to_delete:
            print(f"   [ID:{r['id']}] {r['sku']:<15} {r['name']} (stock={r['stock']})")

        # ─── Step 2: DELETE with WHERE ───
        print("\n2️⃣  DELETE with WHERE:")
        cursor.execute("""
            DELETE FROM products
            WHERE is_active = FALSE
        """)
        deleted = cursor.rowcount
        print(f"   Deleted {deleted} inactive products")

        # ─── Verify ───
        cursor.execute("SELECT COUNT(*) AS cnt FROM products")
        after = cursor.fetchone()['cnt']
        print(f"   After delete: {after} products (was {before}, removed {before - after})")

        # ─── DELETE specific ID ───
        print("\n3️⃣  DELETE by specific ID:")
        cursor.execute("SELECT id, name FROM products WHERE sku = %s", ("TEST-001",))
        row = cursor.fetchone()
        if row:
            cursor.execute("DELETE FROM products WHERE id = %s", (row['id'],))
            print(f"   Deleted: [{row['id']}] {row['name']}")
        else:
            print(f"   TEST-001 already gone")

        # ─── Final count ───
        cursor.execute("SELECT COUNT(*) AS cnt FROM products")
        final = cursor.fetchone()['cnt']
        print(f"\n📊 Final product count: {final}")

    # ─── TRUNCATE warning (separate connection — DDL auto-commits) ───
    print("\n4️⃣  ⚠️  TRUNCATE vs DELETE comparison:")
    print("""
   TRUNCATE TABLE temp_table;  ← DDL
   ┌─────────────────────────────────────────────────────┐
   │  DELETE                    TRUNCATE                 │
   │  ─────────────────────     ────────────────────     │
   │  DML command               DDL command              │
   │  WHERE clause support ✅   No WHERE clause ❌       │
   │  Triggers fire ✅          Triggers DON'T fire ❌   │
   │  ROLLBACK possible ✅      ROLLBACK nahi hota ❌    │
   │  Row-by-row (slow) ❌      Page-level (fast) ✅     │
   │  AUTO_INCREMENT intact ✅  AUTO_INCREMENT reset ✅  │
   └─────────────────────────────────────────────────────┘

   Use TRUNCATE sirf temp/staging tables ke liye.
   Production data ke liye hamesha DELETE with WHERE.
    """)

    print(f"✅ DELETE demo complete!\n")


# ══════════════════════════════════════════════════════════
# SECTION 7: PYTHON PATTERNS
# ══════════════════════════════════════════════════════════

def demo_python_patterns():
    """
    Python best practices — context manager, executemany performance,
    parameterized queries (SQL injection prevention).
    """
    print(f"\n{DIVIDER}")
    print("🐍 SECTION 7: PYTHON PATTERNS")
    print(DIVIDER)

    # ─── Pattern 1: Context Manager ───
    print("\n1️⃣  Context Manager pattern (auto commit/rollback/close):")
    print("""
   @contextmanager
   def get_db():
       conn = mysql.connector.connect(**config)
       cursor = conn.cursor(dictionary=True)
       try:
           yield cursor, conn
           conn.commit()       # Success → commit
       except Exception:
           conn.rollback()     # Error → rollback (data safe!)
           raise
       finally:
           cursor.close()
           conn.close()        # Always close (connection leak nahi)

   # Usage:
   with get_db() as (cursor, conn):
       cursor.execute("INSERT INTO ...")
   # conn auto-close ho gayi ✅
    """)

    # ─── Pattern 2: executemany performance comparison ───
    print("\n2️⃣  executemany vs loop — performance comparison:")
    N = 500

    # Create temp table
    with get_db() as (cursor, conn):
        cursor.execute("DROP TABLE IF EXISTS perf_test")
        cursor.execute("""
            CREATE TABLE perf_test (
                id    INT AUTO_INCREMENT PRIMARY KEY,
                val   VARCHAR(50),
                num   INT
            ) ENGINE=InnoDB
        """)

    # Method A: Loop (slow — N round trips)
    start = time.time()
    with get_db() as (cursor, conn):
        for i in range(N):
            cursor.execute(
                "INSERT INTO perf_test (val, num) VALUES (%s, %s)",
                (f"item_{i}", i)
            )
    loop_time = (time.time() - start) * 1000

    # Clear
    with get_db() as (cursor, conn):
        cursor.execute("TRUNCATE TABLE perf_test")

    # Method B: executemany (fast — 1 round trip)
    data = [(f"item_{i}", i) for i in range(N)]
    start = time.time()
    with get_db() as (cursor, conn):
        cursor.executemany(
            "INSERT INTO perf_test (val, num) VALUES (%s, %s)",
            data
        )
    bulk_time = (time.time() - start) * 1000

    speedup = loop_time / bulk_time if bulk_time > 0 else 0
    print(f"   Inserting {N} rows:")
    print(f"   Loop (N round trips)    : {loop_time:.2f}ms")
    print(f"   executemany (1 trip)    : {bulk_time:.2f}ms")
    print(f"   Speedup                 : {speedup:.1f}x faster ✅")
    print(f"   → 100+ rows hoon toh ALWAYS use executemany!")

    # Cleanup
    with get_db() as (cursor, conn):
        cursor.execute("DROP TABLE IF EXISTS perf_test")

    # ─── Pattern 3: SQL Injection Prevention ───
    print("\n3️⃣  SQL Injection Prevention — Parameterized Queries:")
    print("""
   # ❌ WRONG — SQL Injection vulnerable:
   user_input = "'; DROP TABLE products; --"
   query = f"SELECT * FROM products WHERE name = '{user_input}'"
   # Actual SQL: SELECT * FROM products WHERE name = ''; DROP TABLE products; --'
   # TABLE DELETE HO SAKTI HAI! 😱

   # ✅ CORRECT — Parameterized (MySQL uses %s placeholder):
   cursor.execute(
       "SELECT * FROM products WHERE name = %s",
       (user_input,)    # Tuple! (comma at end important for single value)
   )
   # MySQL driver automatically escapes → safe ✅

   # ✅ Multiple params:
   cursor.execute(
       "SELECT * FROM products WHERE category = %s AND price < %s",
       (category, max_price)
   )

   # ✅ IN clause ke saath:
   cats = ['electronics', 'books']
   placeholders = ', '.join(['%s'] * len(cats))
   cursor.execute(
       f"SELECT * FROM products WHERE category IN ({placeholders})",
       cats      # list bhi chalta hai
   )

   # Note: PyMySQL aur mysql-connector dono %s use karte hain
   # SQLite %s nahi, ? use karta hai — dhyan rakhna!
    """)

    # ─── Pattern 4: Reusable DB class ───
    print("\n4️⃣  Reusable DB helper class:")
    print("""
   class MySQLDB:
       def __init__(self, **kwargs):
           self.config = kwargs

       @contextmanager
       def cursor(self):
           conn = mysql.connector.connect(**self.config)
           cur = conn.cursor(dictionary=True)
           try:
               yield cur, conn
               conn.commit()
           except:
               conn.rollback()
               raise
           finally:
               cur.close()
               conn.close()

       def fetchall(self, sql, params=()):
           with self.cursor() as (cur, _):
               cur.execute(sql, params)
               return cur.fetchall()

       def fetchone(self, sql, params=()):
           with self.cursor() as (cur, _):
               cur.execute(sql, params)
               return cur.fetchone()

       def execute(self, sql, params=()):
           with self.cursor() as (cur, _):
               cur.execute(sql, params)
               return cur.rowcount

       def executemany(self, sql, data):
           with self.cursor() as (cur, _):
               cur.executemany(sql, data)
               return cur.rowcount
    """)

    # ─── Pattern 5: dictionary=True vs tuple cursor ───
    print("\n5️⃣  dictionary=True cursor (recommended):")
    with get_db(dictionary=True) as (cursor, conn):
        cursor.execute("SELECT id, name, price FROM products LIMIT 2")
        rows_dict = cursor.fetchall()
        print(f"   dictionary=True  : {rows_dict[0]}")

    with get_db(dictionary=False) as (cursor, conn):
        cursor.execute("SELECT id, name, price FROM products LIMIT 2")
        rows_tuple = cursor.fetchall()
        print(f"   dictionary=False : {rows_tuple[0]}")

    print("""
   Dict cursor: row['name'] — readable, no index guessing ✅
   Tuple cursor: row[1]     — fragile, breaks on schema change ❌
    """)

    print(f"✅ Python patterns demo complete!\n")


# ══════════════════════════════════════════════════════════
# MAIN — Dispatcher
# ══════════════════════════════════════════════════════════

def print_usage():
    print("""
Usage: python 01_basics_crud.py [section]

Available sections:
  connection   → MySQL version, charset, databases list
  ddl          → CREATE TABLE, ALTER, SHOW commands, DROP
  insert       → Single insert, bulk, INSERT IGNORE, UPSERT
  select       → WHERE, BETWEEN, IN, LIKE, NULL, GROUP BY, pagination
  update       → Single, bulk, calculated, CASE update
  delete       → DELETE with WHERE, verify, TRUNCATE comparison
  patterns     → Context manager, executemany perf, SQL injection
  all          → Run all sections (default)

Example:
  python 01_basics_crud.py connection
  python 01_basics_crud.py all
    """)


def main():
    arg = sys.argv[1].lower() if len(sys.argv) > 1 else "all"

    if arg in ("help", "--help", "-h"):
        print_usage()
        return

    print(f"\n{'═' * 60}")
    print("🐬 MySQL Practical 01 — Basics, Installation & CRUD")
    print(f"{'═' * 60}")
    print(f"   Section  : {arg}")
    print(f"   Client   : {CONNECTOR}")
    print(f"   Host     : {DB_CONFIG['host']}:{DB_CONFIG['port']}")
    print(f"   Database : {DB_CONFIG['database']}")

    if not check_mysql_running():
        sys.exit(1)

    section_map = {
        "connection": demo_connection,
        "ddl":        demo_ddl,
        "insert":     demo_insert,
        "crud":       lambda: (demo_insert(), demo_select(), demo_update(), demo_delete()),
        "select":     demo_select,
        "update":     demo_update,
        "delete":     demo_delete,
        "patterns":   demo_python_patterns,
        "bulk":       demo_insert,
    }

    if arg == "all":
        # Full sequence — setup se teardown tak
        demo_connection()
        demo_ddl()
        demo_insert()
        demo_select()
        demo_update()
        demo_delete()
        demo_python_patterns()

        print(f"\n{'═' * 60}")
        print("🎉 All sections complete!")
        print("   Theory file padhne ke liye:")
        print("   theory/01_basics_installation_crud.md")
        print(f"{'═' * 60}\n")

    elif arg in section_map:
        # DDL pehle run karo agar sirf ek section run kar rahe ho
        if arg not in ("connection", "ddl", "patterns"):
            print("\n⚙️  Setting up tables first...")
            try:
                demo_ddl()
                demo_insert()
            except Exception as e:
                print(f"   Setup error: {e}")

        fn = section_map[arg]
        fn()
    else:
        print(f"\n❌ Unknown section: '{arg}'")
        print_usage()
        sys.exit(1)


if __name__ == "__main__":
    main()
