# MySQL — Basics, Installation & CRUD
**Basic Level | What, Why, How**

---

## Quick Concepts
- **MySQL** = World's most popular open-source RDBMS — structured data ko tables mein store karta hai
- **RDBMS** = Relational Database Management System — tables, rows, columns aur relationships
- **InnoDB** = MySQL ka default storage engine — ACID transactions support karta hai (production standard)
- **Primary Key** = Har row ka unique identifier — NULL nahi ho sakta, duplicate nahi ho sakta
- **Foreign Key** = Dusri table ka reference — referential integrity enforce karta hai
- **NULL** = Value absent hai — zero ya empty string se alag concept hai
- **NOT NULL** = Column mein value mandatory hai — NULL allowed nahi
- **AUTO_INCREMENT** = Automatic ID generation — insert pe khud badh jaata hai
- **mysql-connector-python** = Oracle ka official Python client for MySQL
- **PyMySQL** = Pure Python lightweight client — mysql-connector ka drop-in replacement
- **DDL** = Data Definition Language — CREATE, ALTER, DROP (schema changes)
- **DML** = Data Manipulation Language — INSERT, UPDATE, DELETE, SELECT (data changes)
- **DCL** = Data Control Language — GRANT, REVOKE (permissions)
- **TCL** = Transaction Control Language — COMMIT, ROLLBACK, SAVEPOINT
- **utf8mb4** = Full Unicode charset — emojis aur special chars bhi store kar sakta hai
- **ACID** = Atomicity, Consistency, Isolation, Durability — transaction ki 4 guarantees

---

## What is MySQL? Why use it?

```
Without a database:
  Data → Files (CSV/JSON) → Search karo → O(n) slow, no relationships ❌

With MySQL:
  Data → Tables (indexed) → SQL Query → Milliseconds ✅

MySQL ke main use cases:
  1. Web Applications  → WordPress, Django, Flask backends
  2. E-commerce        → Products, orders, customers, inventory
  3. Analytics         → Reports, aggregations, GROUP BY queries
  4. Finance           → Transactions, ledgers (ACID guarantees)
  5. CMS               → Content management systems
  6. SaaS Products     → Multi-tenant applications

MySQL vs alternatives:
  MySQL     → Web apps, read-heavy, simple setup, huge community
  PostgreSQL → Complex queries, JSON, full-text, enterprise features
  SQLite    → Local/embedded, single user, no server needed
  MongoDB   → Unstructured/flexible schema, document storage
```

---

## Interview Questions & Answers

---

### Q1: MySQL kaise install karo? Docker se kaise run karo?

**Answer:**
```bash
# ─── Docker (recommended) ───
docker run -d \
  --name mysql \
  -p 3306:3306 \
  -e MYSQL_ROOT_PASSWORD=rootpass \
  -e MYSQL_DATABASE=mydb \
  -e MYSQL_USER=myuser \
  -e MYSQL_PASSWORD=mypass \
  mysql:8.0

# Data persist karne ke liye (volume mount)
docker run -d \
  --name mysql \
  -p 3306:3306 \
  -e MYSQL_ROOT_PASSWORD=rootpass \
  -e MYSQL_DATABASE=mydb \
  -e MYSQL_USER=myuser \
  -e MYSQL_PASSWORD=mypass \
  -v mysql_data:/var/lib/mysql \
  mysql:8.0

# Container mein ghuso
docker exec -it mysql bash

# ─── MySQL CLI connect ───
mysql -h 127.0.0.1 -P 3306 -u myuser -pmypass mydb

# Root se connect
mysql -h 127.0.0.1 -P 3306 -u root -prootpass

# ─── Mac (Homebrew) ───
brew install mysql
brew services start mysql

# ─── Python clients install ───
pip install mysql-connector-python   # Official Oracle client
pip install PyMySQL                  # Pure Python, lightweight
pip install cryptography             # SSL support ke liye
```

---

### Q2: Python se MySQL kaise connect karo? Connection patterns kya hain?

**Answer:**
```python
# ─── mysql-connector-python ───
import mysql.connector
from mysql.connector import Error

conn = mysql.connector.connect(
    host="localhost",
    port=3306,
    user="myuser",
    password="mypass",
    database="mydb",
    autocommit=False,       # Explicit transaction control
    connection_timeout=30,
    charset='utf8mb4',      # Full Unicode (emojis bhi support)
)

cursor = conn.cursor(dictionary=True)   # dict instead of tuple — recommended!
cursor.execute("SELECT VERSION()")
row = cursor.fetchone()
print(row)   # {'VERSION()': '8.0.33'}
cursor.close()
conn.close()

# ─── PyMySQL (drop-in replacement) ───
import pymysql

conn = pymysql.connect(
    host="localhost",
    port=3306,
    user="myuser",
    password="mypass",
    database="mydb",
    cursorclass=pymysql.cursors.DictCursor   # Always dict
)

# ─── Context Manager pattern (best practice) ───
from contextlib import contextmanager

@contextmanager
def get_db():
    conn = mysql.connector.connect(
        host="localhost", user="myuser",
        password="mypass", database="mydb",
        charset='utf8mb4', autocommit=False,
    )
    cursor = conn.cursor(dictionary=True)
    try:
        yield cursor, conn
        conn.commit()           # Success → commit
    except Exception:
        conn.rollback()         # Error → rollback
        raise
    finally:
        cursor.close()
        conn.close()

# Usage:
with get_db() as (cursor, conn):
    cursor.execute("SELECT * FROM products WHERE id = %s", (1,))
    product = cursor.fetchone()
```

---

### Q3: Database aur Table kaise banate hain? DDL commands kya hain?

**Answer:**
```sql
-- ─── Database Operations ───
CREATE DATABASE IF NOT EXISTS ecommerce
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

USE ecommerce;
SHOW DATABASES;
DROP DATABASE IF EXISTS ecommerce;

-- ─── Table with all common data types ───
CREATE TABLE products (
    id          INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    sku         VARCHAR(50)  NOT NULL UNIQUE,
    name        VARCHAR(200) NOT NULL,
    description TEXT,
    price       DECIMAL(10, 2) NOT NULL DEFAULT 0.00,
    stock       INT NOT NULL DEFAULT 0,
    category    ENUM('electronics','clothing','books','sports') NOT NULL,
    is_active   BOOLEAN NOT NULL DEFAULT TRUE,
    tags        JSON,                           -- JSON column (MySQL 5.7+)
    image_url   VARCHAR(500),
    weight_kg   FLOAT,
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at  DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    INDEX idx_category (category),             -- Single column index
    INDEX idx_price (price),
    INDEX idx_active_category (is_active, category)  -- Composite index
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ─── ALTER TABLE ───
ALTER TABLE products ADD COLUMN brand VARCHAR(100) AFTER name;
ALTER TABLE products MODIFY COLUMN price DECIMAL(12, 2) NOT NULL;
ALTER TABLE products DROP COLUMN weight_kg;
ALTER TABLE products ADD INDEX idx_brand (brand);
ALTER TABLE products RENAME TO items;           -- Table rename

-- ─── SHOW Commands ───
SHOW TABLES;
DESCRIBE products;               -- Column info
SHOW CREATE TABLE products;      -- Full CREATE statement
SHOW INDEX FROM products;        -- Index info
SHOW TABLE STATUS LIKE 'prod%';  -- Engine, rows, size info
```

---

### Q4: INSERT kaise karte hain? Upsert kya hota hai?

**Answer:**
```sql
-- ─── Single Row INSERT ───
INSERT INTO products (sku, name, price, stock, category)
VALUES ('LAPTOP-001', 'MacBook Pro', 125000.00, 50, 'electronics');

-- ─── Multiple Rows (Bulk Insert — ek hi trip mein, much faster!) ───
INSERT INTO products (sku, name, price, stock, category) VALUES
    ('PHONE-001', 'iPhone 15',    79000.00, 100, 'electronics'),
    ('PHONE-002', 'Samsung S24',  65000.00, 150, 'electronics'),
    ('BOOK-001',  'Clean Code',     499.00, 200, 'books'),
    ('BOOK-002',  'Design Patterns',599.00, 180, 'books');

-- ─── INSERT IGNORE — Duplicate pe silently skip (no error) ───
INSERT IGNORE INTO products (sku, name, price, category)
VALUES ('LAPTOP-001', 'Duplicate Laptop', 100, 'electronics');
-- sku already exists → row skip, no exception thrown

-- ─── ON DUPLICATE KEY UPDATE (UPSERT pattern) ───
-- "Agar exist kare → update karo, nahi kare → insert karo"
INSERT INTO products (sku, name, price, stock, category)
VALUES ('LAPTOP-001', 'MacBook Pro M3', 135000.00, 45, 'electronics')
ON DUPLICATE KEY UPDATE
    name  = VALUES(name),
    price = VALUES(price),
    stock = VALUES(stock);

-- ─── lastrowid — naya insert hua ID kaise milta hai ───
-- Python mein:
cursor.execute("INSERT INTO products (...) VALUES (...)", (...))
new_id = cursor.lastrowid   # Auto-increment ID
print(f"New product ID: {new_id}")
```

---

### Q5: SELECT query kaise likhte hain? Filtering, Sorting, Pagination?

**Answer:**
```sql
-- ─── Basic SELECT ───
SELECT * FROM products;
SELECT id, name, price FROM products;
SELECT name, price * 0.9 AS discounted_price FROM products;   -- Calculated column

-- ─── WHERE conditions ───
SELECT * FROM products WHERE category = 'electronics' AND price < 100000;
SELECT * FROM products WHERE price BETWEEN 1000 AND 50000;
SELECT * FROM products WHERE category IN ('electronics', 'books');
SELECT * FROM products WHERE name LIKE '%iPhone%';    -- Wildcard (contains)
SELECT * FROM products WHERE name LIKE 'Mac%';        -- Starts with
SELECT * FROM products WHERE name LIKE '%Pro';        -- Ends with
SELECT * FROM products WHERE description IS NOT NULL;
SELECT * FROM products WHERE description IS NULL;
SELECT * FROM products WHERE JSON_CONTAINS(tags, '"bestseller"');

-- ─── ORDER BY ───
SELECT * FROM products ORDER BY price DESC;
SELECT * FROM products ORDER BY category ASC, price DESC;   -- Multi-column sort

-- ─── LIMIT / OFFSET (Pagination ke liye) ───
SELECT * FROM products LIMIT 10;              -- First 10 rows
SELECT * FROM products LIMIT 10 OFFSET 20;   -- Page 3 (skip 20, take 10)
SELECT * FROM products LIMIT 20, 10;          -- MySQL shorthand: LIMIT offset, count

-- Page formula: OFFSET = (page_number - 1) * page_size

-- ─── DISTINCT ───
SELECT DISTINCT category FROM products;   -- Unique categories

-- ─── Aggregate Functions ───
SELECT COUNT(*) AS total FROM products;
SELECT
    COUNT(*)     AS total_products,
    AVG(price)   AS avg_price,
    MAX(price)   AS max_price,
    MIN(price)   AS min_price,
    SUM(stock)   AS total_stock
FROM products WHERE is_active = TRUE;

-- ─── GROUP BY + HAVING ───
SELECT
    category,
    COUNT(*)   AS product_count,
    AVG(price) AS avg_price,
    SUM(stock) AS total_stock
FROM products
WHERE is_active = TRUE
GROUP BY category
HAVING COUNT(*) > 5         -- GROUP BY ke baad filter (WHERE nahi!)
ORDER BY product_count DESC;

-- WHERE vs HAVING:
-- WHERE  → GROUP BY se PEHLE filter (individual rows pe)
-- HAVING → GROUP BY ke BAAD filter (groups pe)
```

---

### Q6: UPDATE aur DELETE kaise karte hain? Kya dhyan rakhein?

**Answer:**
```sql
-- ─── UPDATE ───
-- Single row update
UPDATE products SET price = 119000, stock = 45 WHERE id = 1;

-- Multiple rows update
UPDATE products SET is_active = FALSE WHERE stock = 0;

-- Calculated update (price 10% badhao)
UPDATE products SET price = price * 1.10 WHERE category = 'electronics';

-- Multi-table UPDATE (JOIN ke saath)
UPDATE products p
JOIN categories c ON p.category_id = c.id
SET p.is_featured = TRUE
WHERE c.name = 'electronics' AND p.price > 50000;

-- ⚠️ DANGER: WHERE clause bhool gaye? Saari rows update ho jaayengi!
-- UPDATE products SET price = 0;   ← NEVER DO THIS without WHERE

-- ─── DELETE ───
DELETE FROM products WHERE id = 5;
DELETE FROM products WHERE is_active = FALSE AND stock = 0;

-- DELETE ke pehle SELECT se verify karo:
SELECT * FROM products WHERE is_active = FALSE AND stock = 0;  -- pehle dekho
DELETE FROM products WHERE is_active = FALSE AND stock = 0;    -- phir delete

-- ─── TRUNCATE (Fast delete all rows) ───
TRUNCATE TABLE temp_data;
-- DDL command hai — undo nahi ho sakta!
-- AUTO_INCREMENT counter bhi reset ho jaata hai
-- Triggers fire nahi hote
```

---

### Q7: MySQL vs PostgreSQL — kab kya choose karo?

**Answer:**
```
MySQL choose karo jab:
  ✅ Web applications (WordPress, Drupal, Laravel)
  ✅ Read-heavy workloads
  ✅ Simple schema, straightforward queries
  ✅ Team already MySQL jaanta hai
  ✅ Hosting/managed services (PlanetScale, AWS RDS MySQL)
  ✅ Speed priority (simple queries mein faster)

PostgreSQL choose karo jab:
  ✅ Complex queries (CTEs, window functions, lateral joins)
  ✅ Advanced JSON operations (JSONB indexing)
  ✅ Full-text search (tsvector/tsquery)
  ✅ Geospatial data (PostGIS)
  ✅ Custom data types, extensions chahiye
  ✅ ACID compliance with complex transactions
  ✅ Django/FastAPI backends (PostgreSQL preferred)

Real answer in interviews:
  "MySQL simple web apps ke liye great hai, PostgreSQL enterprise
   features aur complex queries ke liye better choice hai.
   Main dono use kar sakta hoon — project requirements pe depend karta hai."
```

---

### Q8: InnoDB vs MyISAM — kya fark hai?

**Answer:**
```
Feature           InnoDB              MyISAM
─────────────────────────────────────────────────────
Transactions      ✅ Yes (ACID)       ❌ No
Foreign Keys      ✅ Yes              ❌ No
Row-level Lock    ✅ Yes (concurrent)  ❌ Table-level lock
Crash Recovery    ✅ Yes (redo log)    ❌ No
Full-text Index   ✅ Yes (MySQL 5.6+) ✅ Yes (older)
Read Speed        Good                Slightly faster (simple reads)
Write Speed       Good                Fast (no transaction overhead)
Default Engine    ✅ MySQL 5.5+       Was default before 5.5

Conclusion: InnoDB hamesha use karo (production mein).
  MyISAM sirf legacy code mein milta hai — naya code mein avoid karo.

ENGINE=InnoDB — CREATE TABLE mein specify karo (though default hai).
```

---

### Q9: VARCHAR vs CHAR — kab kya use karo?

**Answer:**
```sql
-- CHAR(n): Fixed length — hamesha n characters store karta hai (spaces se pad karta hai)
-- VARCHAR(n): Variable length — actual length + 1-2 bytes overhead

-- CHAR example:
-- CHAR(10) mein "Hi" store karo → "Hi        " (8 spaces pad)
-- Storage: always 10 bytes

-- VARCHAR example:
-- VARCHAR(10) mein "Hi" store karo → "Hi"
-- Storage: 2 bytes (actual) + 1 byte (length) = 3 bytes

-- Kab CHAR use karo:
CREATE TABLE countries (
    code CHAR(2) NOT NULL,    -- Always 2 chars: "IN", "US", "UK"
    name VARCHAR(100)
);
-- CHAR ke liye:
--   ✅ Fixed-length codes: country codes, status flags, hash digests
--   ✅ Frequently updated columns (variable-length update slow hota hai)
--   ✅ Mostly full-length data

-- Kab VARCHAR use karo:
CREATE TABLE users (
    username  VARCHAR(50),    -- Length vary karta hai
    email     VARCHAR(255),
    bio       VARCHAR(500)
);
-- VARCHAR ke liye:
--   ✅ Most text fields (names, emails, descriptions)
--   ✅ Length variable hogi (better space efficiency)
--   ✅ Max length uncertain ho toh bhi safe
```

---

### Q10: INSERT IGNORE vs ON DUPLICATE KEY UPDATE — kab kya?

**Answer:**
```sql
-- INSERT IGNORE: Duplicate pe SILENTLY SKIP karo
-- Use case: "Agar nahi hai toh insert, warna kuch mat karo"
INSERT IGNORE INTO user_preferences (user_id, pref_key, pref_value)
VALUES (101, 'theme', 'dark');
-- user_id=101, pref_key='theme' already exists → silently skip
-- ⚠️ WARNING: Aur bhi errors ignore ho jaate hain (data truncation etc.)

-- ON DUPLICATE KEY UPDATE: Duplicate pe UPDATE karo
-- Use case: "Agar nahi hai toh insert, warna update karo" (true UPSERT)
INSERT INTO product_inventory (sku, quantity, last_updated)
VALUES ('PHONE-001', 10, NOW())
ON DUPLICATE KEY UPDATE
    quantity     = quantity + VALUES(quantity),   -- Add to existing
    last_updated = VALUES(last_updated);

-- VALUES(col) → naya value jo INSERT mein diya tha

-- Summary:
-- INSERT IGNORE    → duplicate pe skip, no update
-- ON DUPLICATE KEY → duplicate pe specific update
-- REPLACE INTO     → duplicate pe DELETE + INSERT (avoid! — FKs break ho sakte hain)
```

---

### Q11: DELETE vs TRUNCATE vs DROP — kya fark hai?

**Answer:**
```sql
-- DELETE: DML command — rows remove karo (selective ya all)
DELETE FROM logs WHERE created_at < '2024-01-01';  -- Specific rows
DELETE FROM temp_table;                             -- All rows (slow!)
-- ✅ WHERE clause support
-- ✅ Triggers fire hote hain
-- ✅ ROLLBACK possible (transaction mein ho toh)
-- ✅ Row-by-row delete — log karta hai
-- ❌ Slow for large tables
-- AUTO_INCREMENT reset NAHI hota

-- TRUNCATE: DDL command — saari rows fast remove karo
TRUNCATE TABLE logs;
-- ❌ No WHERE clause
-- ❌ Triggers fire NAHI hote
-- ❌ ROLLBACK possible NAHI (DDL hai)
-- ✅ Very fast (page-level operation)
-- ✅ AUTO_INCREMENT counter reset ho jaata hai
-- ❌ Foreign key referenced table pe TRUNCATE fail hoga

-- DROP: DDL command — poori table ya database delete karo
DROP TABLE IF EXISTS logs;
DROP DATABASE IF EXISTS old_db;
-- ❌ No WHERE clause
-- ❌ Not reversible
-- ✅ Table structure + data + indexes sab gone
-- Schema bhi chala jaata hai

-- Quick comparison:
-- DELETE   → kuch rows ya saari rows remove, reversible, slow
-- TRUNCATE → saari rows remove, fast, irreversible, AUTO_INCREMENT reset
-- DROP     → table/DB hi khatam, schema bhi gone
```

---

### Q12: NULL vs Empty String — kya fark hai?

**Answer:**
```sql
-- NULL = Value absent/unknown hai — "pata nahi" ka concept
-- '' (Empty String) = Value present hai, lekin blank hai — "pata hai, khaali hai"

-- NULL examples:
INSERT INTO users (name, phone) VALUES ('Ram', NULL);
-- phone field mein value hai hi nahi (optional tha)

-- Empty string examples:
INSERT INTO users (name, phone) VALUES ('Shyam', '');
-- phone diya gaya — lekin blank (data entry error?)

-- NULL ke saath comparison:
SELECT * FROM users WHERE phone = NULL;    -- ❌ WRONG — always returns 0 rows!
SELECT * FROM users WHERE phone IS NULL;   -- ✅ CORRECT
SELECT * FROM users WHERE phone IS NOT NULL;  -- ✅ CORRECT

-- NULL arithmetic:
SELECT NULL + 5;      -- NULL (NULL kisi bhi operation mein propagate hota hai)
SELECT NULL = NULL;   -- NULL (not TRUE!)
SELECT NULL != NULL;  -- NULL

-- COALESCE — NULL handle karne ka standard way:
SELECT COALESCE(phone, 'N/A') FROM users;   -- NULL → 'N/A'
SELECT COALESCE(price, 0) FROM products;    -- NULL → 0

-- IFNULL (MySQL specific):
SELECT IFNULL(phone, 'No phone') FROM users;

-- Best practice:
-- Optional fields → allow NULL
-- Required fields → NOT NULL constraint
-- Never use '' as substitute for NULL in optional fields
```

---

### Q13: DECIMAL vs FLOAT — money ke liye kaunsa use karo?

**Answer:**
```sql
-- FLOAT / DOUBLE: Approximate values (binary floating point)
-- Scientific notation mein store hota hai → precision issues!

SELECT 0.1 + 0.2;           -- 0.30000000000000004 (surprise! ❌)
CREATE TABLE bad_finance (
    amount FLOAT   -- NEVER for money!
);
INSERT INTO bad_finance VALUES (9999.99);
SELECT amount * 100 FROM bad_finance;  -- 999998.9999... (wrong!)

-- DECIMAL(M, D): EXACT numeric values
-- M = total digits, D = digits after decimal point
CREATE TABLE good_finance (
    amount DECIMAL(15, 2)  -- Up to 9,999,999,999,999.99
);
INSERT INTO good_finance VALUES (9999.99);
SELECT amount * 100 FROM good_finance;  -- 999999.00 ✅ EXACT

-- Rule of thumb:
-- Money, prices, quantities → DECIMAL
-- Scientific measurements, ML features → FLOAT/DOUBLE (approximation okay)
-- Storage: DECIMAL uses more space but gives exact results

-- Common patterns:
price        DECIMAL(10, 2)   -- Up to 99,999,999.99
tax_rate     DECIMAL(5, 4)    -- Up to 9.9999 (e.g., 0.1800 = 18%)
salary       DECIMAL(12, 2)   -- Up to 9,999,999,999.99
percentage   DECIMAL(5, 2)    -- Up to 999.99%
```

---

### Q14: SQL Injection kaise rokein? Parameterized queries kya hain?

**Answer:**
```python
# SQL Injection: Attacker malicious SQL code input mein inject karta hai

# ❌ WRONG — SQL Injection vulnerable:
user_input = "'; DROP TABLE users; --"
query = f"SELECT * FROM users WHERE name = '{user_input}'"
# Actual SQL ban jaata hai:
# SELECT * FROM users WHERE name = ''; DROP TABLE users; --'
cursor.execute(query)   # DANGER! Table delete ho sakti hai!

# ❌ Also WRONG:
username = request.form['username']
cursor.execute("SELECT * FROM users WHERE username = '" + username + "'")

# ✅ CORRECT — Parameterized queries (always use this!):
cursor.execute(
    "SELECT * FROM users WHERE username = %s AND password = %s",
    (username, password)    # Tuple of values
)

# ✅ Multiple parameters:
cursor.execute(
    "INSERT INTO products (sku, name, price) VALUES (%s, %s, %s)",
    (sku, name, price)
)

# ✅ IN clause ke saath:
categories = ['electronics', 'books', 'sports']
placeholders = ', '.join(['%s'] * len(categories))  # '%s, %s, %s'
cursor.execute(
    f"SELECT * FROM products WHERE category IN ({placeholders})",
    categories
)

# MySQL mein placeholder = %s (not ? like SQLite)
# PyMySQL mein bhi %s use hota hai

# Additional security:
# 1. Least privilege — user ko sirf zaroori permissions do
# 2. Input validation — type/length check karo
# 3. Error messages expose mat karo (debug info production mein off)
# 4. ORM use karo (SQLAlchemy, Django ORM) — auto-parameterized
```

---

## MySQL Data Types — Complete Reference

```sql
-- ─── Numeric Types ───
TINYINT              -- -128 to 127 (or 0-255 UNSIGNED) — boolean ke liye
SMALLINT             -- ±32,767
MEDIUMINT            -- ±8,388,607
INT / INTEGER        -- ±2,147,483,647 (most common for IDs)
BIGINT               -- ±9.2 * 10^18 (large IDs, timestamps in ms)
FLOAT(M,D)           -- Approximate decimal (~7 digits precision)
DOUBLE(M,D)          -- Approximate decimal (~15 digits precision)
DECIMAL(M,D)         -- EXACT decimal — money ke liye ALWAYS use this!

-- ─── String Types ───
CHAR(n)              -- Fixed length (1-255 chars, padded with spaces)
VARCHAR(n)           -- Variable length (1-65535 chars, saves space)
TINYTEXT             -- Up to 255 bytes
TEXT                 -- Up to 65,535 bytes (~64KB)
MEDIUMTEXT           -- Up to 16,777,215 bytes (~16MB)
LONGTEXT             -- Up to 4,294,967,295 bytes (~4GB)
ENUM('a','b','c')    -- Predefined list, 1-2 bytes storage, fast
SET('a','b','c')     -- Multiple values from predefined list

-- ─── Date and Time ───
DATE                 -- 'YYYY-MM-DD' only
TIME                 -- 'HH:MM:SS' only
DATETIME             -- 'YYYY-MM-DD HH:MM:SS' (no timezone, up to 9999)
TIMESTAMP            -- UTC stored, auto timezone convert (up to 2038!)
YEAR                 -- 4-digit year (2155 tak)

-- ─── Special Types ───
BOOLEAN / BOOL       -- Alias for TINYINT(1): 0=FALSE, 1=TRUE
JSON                 -- Structured JSON (MySQL 5.7+, indexed bhi ho sakta)
BINARY(n)            -- Fixed-length binary data
VARBINARY(n)         -- Variable-length binary data
BLOB                 -- Binary large object (up to 65KB)
MEDIUMBLOB           -- Up to 16MB
LONGBLOB             -- Up to 4GB (images/files — DB mein avoid karo!)

-- ─── VARCHAR vs CHAR quick rule ───
-- CHAR  → Fixed-length data: country codes (IN,US), status (Y/N), hash values
-- VARCHAR → Variable-length data: names, emails, descriptions (almost everything)

-- ─── DATETIME vs TIMESTAMP ───
-- DATETIME  → Timezone-independent, '1000-01-01' to '9999-12-31', no auto-convert
-- TIMESTAMP → UTC mein store, app timezone pe auto-convert, only up to '2038-01-19'
-- created_at/updated_at ke liye DATETIME recommended (no 2038 problem)
```

---

## Python CRUD — Complete Class with Error Handling

```python
import mysql.connector
from mysql.connector import Error
from contextlib import contextmanager
from typing import Optional, List, Dict, Any

class MySQLDB:
    """
    MySQL wrapper class — context manager pattern ke saath
    Production-ready: error handling, parameterized queries, bulk ops
    """
    def __init__(self, host: str, user: str, password: str,
                 database: str, port: int = 3306):
        self.config = dict(
            host=host, port=port, user=user,
            password=password, database=database,
            charset='utf8mb4', autocommit=False,
        )

    @contextmanager
    def get_cursor(self, dictionary: bool = True):
        """Context manager — auto commit/rollback/close"""
        conn = mysql.connector.connect(**self.config)
        cursor = conn.cursor(dictionary=dictionary)
        try:
            yield cursor, conn
            conn.commit()
        except Error as e:
            conn.rollback()
            raise
        finally:
            cursor.close()
            conn.close()

    def insert(self, table: str, data: Dict[str, Any]) -> int:
        """Single row insert — returns lastrowid"""
        cols = ", ".join(data.keys())
        placeholders = ", ".join(["%s"] * len(data))
        sql = f"INSERT INTO {table} ({cols}) VALUES ({placeholders})"
        with self.get_cursor() as (cursor, conn):
            cursor.execute(sql, list(data.values()))
            return cursor.lastrowid

    def bulk_insert(self, table: str, rows: List[Dict[str, Any]]) -> int:
        """Bulk insert with executemany — much faster than loop!"""
        if not rows:
            return 0
        cols = ", ".join(rows[0].keys())
        placeholders = ", ".join(["%s"] * len(rows[0]))
        sql = f"INSERT INTO {table} ({cols}) VALUES ({placeholders})"
        values = [list(r.values()) for r in rows]
        with self.get_cursor() as (cursor, conn):
            cursor.executemany(sql, values)
            return cursor.rowcount

    def select(self, table: str, where: str = "",
               params: tuple = (), limit: int = 100) -> List[Dict]:
        """SELECT with optional WHERE clause"""
        sql = f"SELECT * FROM {table}"
        if where:
            sql += f" WHERE {where}"
        sql += f" LIMIT {limit}"
        with self.get_cursor() as (cursor, conn):
            cursor.execute(sql, params)
            return cursor.fetchall()

    def execute(self, sql: str, params: tuple = ()) -> int:
        """Raw SQL execute — for UPDATE/DELETE"""
        with self.get_cursor() as (cursor, conn):
            cursor.execute(sql, params)
            return cursor.rowcount

    def query(self, sql: str, params: tuple = ()) -> List[Dict]:
        """Raw SQL query — for complex SELECT"""
        with self.get_cursor() as (cursor, conn):
            cursor.execute(sql, params)
            return cursor.fetchall()


# Usage example:
db = MySQLDB("localhost", "myuser", "mypass", "mydb")

# Insert
new_id = db.insert("products", {
    "sku": "LAPTOP-001",
    "name": "MacBook Pro",
    "price": 125000.00,
    "category": "electronics"
})

# Bulk insert (1000 rows ek trip mein)
products = [
    {"sku": f"ITEM-{i}", "name": f"Product {i}", "price": i * 100, "category": "books"}
    for i in range(1, 1001)
]
count = db.bulk_insert("products", products)

# Select
rows = db.select("products", "category = %s AND price < %s",
                 ("electronics", 100000), limit=20)

# Update
affected = db.execute(
    "UPDATE products SET price = price * %s WHERE category = %s",
    (1.1, "electronics")
)
```

---

## Summary Table

| Concept | Kya hai | Kab use karo |
|---|---|---|
| **InnoDB** | Default storage engine, ACID support | Hamesha (production) |
| **AUTO_INCREMENT** | Automatic ID generation | Primary keys ke liye |
| **PRIMARY KEY** | Unique row identifier | Har table mein ek hona chahiye |
| **FOREIGN KEY** | Dusri table ka reference | Relationships enforce karne ke liye |
| **VARCHAR(n)** | Variable-length string | Most text fields |
| **CHAR(n)** | Fixed-length string | Country codes, fixed codes |
| **DECIMAL(M,D)** | Exact decimal | Prices, money (NEVER use FLOAT) |
| **DATETIME** | Date + Time (no timezone) | created_at, updated_at |
| **TIMESTAMP** | UTC datetime (timezone aware) | Avoid (2038 problem) |
| **JSON** | JSON column | Flexible/optional attributes |
| **NOT NULL** | Value mandatory | Required fields |
| **NULL** | Value absent | Optional fields |
| **INDEX** | Fast lookup | WHERE/ORDER BY columns pe |
| **INSERT IGNORE** | Duplicate skip karo | Idempotent inserts |
| **ON DUPLICATE KEY** | Upsert pattern | Insert or update |
| **DELETE** | Rows remove (DML) | Selective deletion, rollback-able |
| **TRUNCATE** | Fast clear all (DDL) | Temp tables clear karna |
| **%s placeholder** | Parameterized query | ALWAYS — SQL injection rokta hai |
| **executemany()** | Bulk insert/update | 100+ rows insert karne ke liye |
| **dictionary=True** | Dict cursor | Tuple se better — key names milte hain |
| **DDL** | CREATE, ALTER, DROP | Schema changes |
| **DML** | INSERT, UPDATE, DELETE | Data changes |
| **TCL** | COMMIT, ROLLBACK | Transaction control |
| **HAVING** | GROUP BY ke baad filter | Aggregated results filter karna |
| **COALESCE** | NULL → default value | NULL handle karna |
