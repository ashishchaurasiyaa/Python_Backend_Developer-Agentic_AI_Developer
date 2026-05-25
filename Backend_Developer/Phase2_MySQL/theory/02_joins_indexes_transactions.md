# MySQL — JOINs, Indexes & Transactions
**Intermediate Level | What, Why, How**

---

## Quick Concepts
- **JOIN** = Do ya zyada tables ke rows ko ek saath laana — ON condition se match karke
- **Index** = Book ke table of contents jaisi cheez — O(N) full scan se O(log N) tak
- **Transaction** = Ek se zyada operations ko ek unit mein bandho — ya sab hoga ya kuch nahi
- **ACID** = Atomicity, Consistency, Isolation, Durability — transactions ki guarantee
- **EXPLAIN** = Query ka execution plan dekho — index use ho raha hai ya nahi
- **Covering Index** = Query ke sabhi columns sirf index se mil jayein — table lookup zero
- **Deadlock** = Do transactions ek doosre ka lock wait kar rahe hain — infinite wait

---

## Sample Schema (Sabhi Examples Isi Se)

```sql
CREATE TABLE users (
    id    INT PRIMARY KEY AUTO_INCREMENT,
    name  VARCHAR(100) NOT NULL,
    email VARCHAR(200) UNIQUE,
    city  VARCHAR(50)
);

CREATE TABLE orders (
    id           INT PRIMARY KEY AUTO_INCREMENT,
    user_id      INT,                          -- NULL ho sakta hai (orphan orders)
    total_amount DECIMAL(10,2),
    status       ENUM('pending','paid','shipped','delivered','cancelled'),
    created_at   DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
);

CREATE TABLE products (
    id       INT PRIMARY KEY AUTO_INCREMENT,
    name     VARCHAR(200),
    price    DECIMAL(10,2),
    category VARCHAR(50),
    is_active BOOLEAN DEFAULT TRUE
);

CREATE TABLE order_items (
    id         INT PRIMARY KEY AUTO_INCREMENT,
    order_id   INT NOT NULL,
    product_id INT NOT NULL,
    quantity   INT NOT NULL,
    unit_price DECIMAL(10,2),
    FOREIGN KEY (order_id)   REFERENCES orders(id)   ON DELETE CASCADE,
    FOREIGN KEY (product_id) REFERENCES products(id)
);
```

---

## Interview Questions & Answers

---

### Q1: INNER JOIN vs LEFT JOIN — kab kya use karo?

**Answer:**
```
INNER JOIN:
  Sirf woh rows return karta hai jo DONO tables mein match karein
  "Intersection" jaisa hai
  Use karo jab: aapko sirf matched data chahiye
  Example: Sirf un users ki list jo orders place kar chuke hain

LEFT JOIN (LEFT OUTER JOIN):
  Left table ki SAARI rows return karta hai
  Right table mein match na ho toh NULL aata hai
  Use karo jab: aapko left table ka poora data chahiye, chahe match ho ya na ho
  Example: Sabhi users ki list — order kiya ho ya na kiya ho

Rule of thumb:
  INNER JOIN  → "sirf jo dono mein hain"
  LEFT JOIN   → "left ka sab, right ka jo mila"
  RIGHT JOIN  → LEFT JOIN ka ulta (rarely used, LEFT JOIN prefer karo)
```

```sql
-- INNER JOIN: Users jo orders place kar chuke hain
SELECT u.name, u.email,
       COUNT(o.id)           AS order_count,
       SUM(o.total_amount)   AS total_spent
FROM users u
INNER JOIN orders o ON u.id = o.user_id
GROUP BY u.id, u.name, u.email
ORDER BY total_spent DESC;

-- LEFT JOIN: Sabhi users — order kiya ho ya na kiya ho
SELECT u.name, u.email,
       COUNT(o.id)                       AS order_count,
       COALESCE(SUM(o.total_amount), 0)  AS total_spent
FROM users u
LEFT JOIN orders o ON u.id = o.user_id
GROUP BY u.id, u.name, u.email
ORDER BY total_spent DESC;

-- Anti-join trick: Users jo KABHI kuch nahi kharide
-- (LEFT JOIN + IS NULL — IN/NOT IN se zyada efficient)
SELECT u.name, u.email
FROM users u
LEFT JOIN orders o ON u.id = o.user_id
WHERE o.id IS NULL;
```

**Interview Tip:**
```
Agar pucha: "INNER JOIN vs WHERE with comma?"
  SELECT * FROM a, b WHERE a.id = b.a_id  →  INNER JOIN hi hai, purana syntax
  Modern SQL mein explicit JOIN prefer karo — readable + optimizer-friendly
```

---

### Q2: Composite Index mein column order matter karta hai kya? (Left Prefix Rule)

**Answer:**
```
Haan! Bahut zyada matter karta hai — Left Prefix Rule ke wajah se.

Composite index (a, b, c) create karo toh MySQL ye queries use kar sakta hai:
  ✅ WHERE a = ?
  ✅ WHERE a = ? AND b = ?
  ✅ WHERE a = ? AND b = ? AND c = ?
  ✅ WHERE a = ? AND b BETWEEN ? AND ?
  ❌ WHERE b = ?           (a skip hua — index use nahi hoga)
  ❌ WHERE c = ?           (a aur b skip hue)
  ❌ WHERE b = ? AND c = ? (a skip hua)

Real example:
```

```sql
-- Composite index: status pehle, created_at baad mein
CREATE INDEX idx_status_date ON orders(status, created_at);

-- ✅ Index use karega (left prefix: status)
EXPLAIN SELECT * FROM orders WHERE status = 'paid';

-- ✅ Index use karega (dono columns)
EXPLAIN SELECT * FROM orders
WHERE status = 'paid' AND created_at > '2024-01-01';

-- ❌ Index use NAHI karega (status skip, sirf created_at)
EXPLAIN SELECT * FROM orders WHERE created_at > '2024-01-01';
-- Full table scan hoga! Alag index banana padega.

-- Rule: Sabse selective column pehle rakho
-- (status mein 5 values, created_at mein millions — status pehle rakho)
```

```
Interview gold:
  "High cardinality column ko index mein pehle rakho"
  Cardinality = number of unique values (email: high, gender: low)
```

---

### Q3: EXPLAIN mein 'ALL' type dikhe toh kya matlab?

**Answer:**
```
EXPLAIN ke 'type' column mein ye values aati hain (worst se best):

ALL     → Full Table Scan — har ek row check ho rahi hai  ⚠️ (AVOID)
index   → Full Index Scan — index traverse kiya gaya
range   → Index se range scan (BETWEEN, >, <, IN)
ref     → Non-unique index use hua
eq_ref  → Unique index / PRIMARY KEY join mein
const   → PRIMARY KEY ya UNIQUE se exact match — fastest  ✅
system  → Table mein sirf ek row hai

'ALL' dikhe toh immediately check karo:
  1. WHERE clause column pe index hai?
  2. JOIN ON column pe index hai?
  3. Column data type mismatch toh nahi? (int = varchar — index skip hota hai)
  4. Function use toh nahi? (WHERE YEAR(created_at) = 2024 — index miss!)
```

```sql
-- BAD: Function se index miss
EXPLAIN SELECT * FROM orders WHERE YEAR(created_at) = 2024;
-- type: ALL  ❌

-- GOOD: Range condition — index hit
EXPLAIN SELECT * FROM orders
WHERE created_at BETWEEN '2024-01-01' AND '2024-12-31';
-- type: range  ✅

-- BAD: Implicit type conversion
EXPLAIN SELECT * FROM users WHERE id = '5';  -- id is INT, '5' is string
-- Sometimes still works but can cause index skip on joins

-- EXPLAIN ka poora output samajhna:
-- key      → NULL mane koi index use nahi hua
-- rows     → estimated rows scanned (kam = better)
-- filtered → % rows jo WHERE condition pass karenge
-- Extra    → "Using filesort" (bad) / "Using index" (covering index, good)

EXPLAIN FORMAT=JSON
SELECT u.name, COUNT(o.id) AS orders
FROM users u
LEFT JOIN orders o ON u.id = o.user_id
GROUP BY u.id;
```

---

### Q4: Covering Index kya hai? Kab useful hai?

**Answer:**
```
Covering Index = Ek aisa index jisme query ke saare columns maujood hain
                 MySQL ko actual table row fetch karne ki zaroorat nahi padti
                 "Index-only scan" bhi kehte hain

Normal query flow:
  1. Index traverse karo → row ka pointer milta hai
  2. Pointer se actual table row fetch karo (random I/O!)
  Total: 2 operations

Covering Index flow:
  1. Index traverse karo → sabhi needed columns directly mile
  No step 2!  → Bahut fast, especially large tables pe
```

```sql
-- EXAMPLE: Orders table pe ye query frequent hai
SELECT user_id, status, total_amount
FROM orders
WHERE user_id = 5;

-- Regular index (sirf user_id pe)
CREATE INDEX idx_user ON orders(user_id);
-- Index se user_id = 5 ke rows milenge, phir table fetch hoga

-- Covering index (query ke sabhi 3 columns include karo)
CREATE INDEX idx_covering ON orders(user_id, status, total_amount);
-- Ab sirf index se query satisfy ho sakti hai!

EXPLAIN SELECT user_id, status, total_amount
FROM orders WHERE user_id = 5;
-- Extra: "Using index"  ← covering index ka sign ✅

-- Kab use karo:
--   Hot queries jo frequently run hoti hain
--   SELECT mein limited columns (SELECT * pe covering index ineffective)
--   Large tables jahan random I/O costly hai

-- Kab avoid karo:
--   Bahut zyada columns → index size = table size ke barabar
--   Heavy INSERT/UPDATE tables → index maintenance overhead
```

---

### Q5: MySQL ka default isolation level kya hai? Kyu?

**Answer:**
```
MySQL InnoDB ka default: REPEATABLE READ

Kyu REPEATABLE READ?
  - Ek transaction mein agar ek hi query do baar chalao
    toh dono baar same result milega
  - Dusre transaction ne beech mein kuch commit kiya toh bhi
    aapki existing transaction ko farak nahi padta
  - Most applications ke liye ye balance sahi hai:
    Performance acchi + data consistency bhi

Chaaron isolation levels:

READ UNCOMMITTED  →  Dirty reads possible (dusre ka uncommitted data dekh sakte ho)
                     Fastest, but data incorrect ho sakta hai ⚠️

READ COMMITTED    →  Dirty reads nahi, but non-repeatable reads possible
                     Default PostgreSQL. Each query fresh snapshot deti hai.

REPEATABLE READ   →  Non-repeatable reads nahi.
                     Default MySQL InnoDB. Transaction shuru mein snapshot fix.
                     Phantom reads bhi handle karta hai InnoDB (MVCC se)

SERIALIZABLE      →  Strictest — transactions ek ke baad ek execute
                     No concurrency issues but very slow ⚠️
```

```sql
-- Current isolation level check karo
SELECT @@transaction_isolation;
-- Output: REPEATABLE-READ

-- Isolation level change karna (session level)
SET SESSION TRANSACTION ISOLATION LEVEL READ COMMITTED;

-- Ek transaction ke liye
SET TRANSACTION ISOLATION LEVEL SERIALIZABLE;
START TRANSACTION;
-- ... your queries ...
COMMIT;

-- Global change (restart ke baad bhi persist)
SET GLOBAL TRANSACTION ISOLATION LEVEL READ COMMITTED;
```

---

### Q6: Deadlock kab hota hai MySQL mein? Kaise avoid karo?

**Answer:**
```
Deadlock = Do transactions ek doosre ke locks ka wait kar rahe hain

Classic scenario:
  T1: locks row A, wait kar raha hai row B ke liye
  T2: locks row B, wait kar raha hai row A ke liye
  → Dono infinite wait!

MySQL automatically detect karta hai deadlock aur ek transaction
automatically rollback kar deta hai (victim choose karta hai)
```

```sql
-- Deadlock kaise hota hai (simulation)

-- Transaction 1 (Session 1)
START TRANSACTION;
SELECT * FROM accounts WHERE id = 1 FOR UPDATE;  -- Lock row 1
-- Ab T2 lock row 2 kar leta hai...
SELECT * FROM accounts WHERE id = 2 FOR UPDATE;  -- Wait! T2 ne lock kiya hai
-- DEADLOCK!

-- Transaction 2 (Session 2)
START TRANSACTION;
SELECT * FROM accounts WHERE id = 2 FOR UPDATE;  -- Lock row 2
SELECT * FROM accounts WHERE id = 1 FOR UPDATE;  -- Wait! T1 ne lock kiya hai
-- DEADLOCK!
```

```
Deadlock avoid karne ke tips:

1. CONSISTENT ORDER: Har transaction mein rows same order mein lock karo
   T1 aur T2 dono pehle row 1 lock karein, phir row 2
   → Deadlock impossible!

2. SHORT TRANSACTIONS: Transaction chhota rakho — jaldi lock lo, jaldi release karo
   Transaction mein user input mat wait karo!

3. INDEX USE KARO: Without index = full table lock (zyada conflict)
   With index = sirf specific rows lock

4. RETRY LOGIC: Application mein deadlock catch karo aur retry karo
   MySQL error code 1213 = ER_LOCK_DEADLOCK
```

```python
import mysql.connector
import time

def execute_with_retry(conn, operations, max_retries=3):
    """Deadlock pe automatically retry karo"""
    for attempt in range(max_retries):
        try:
            cursor = conn.cursor()
            conn.start_transaction()
            for op in operations:
                cursor.execute(op['sql'], op.get('params', ()))
            conn.commit()
            cursor.close()
            return True
        except mysql.connector.errors.DatabaseError as e:
            conn.rollback()
            if e.errno == 1213 and attempt < max_retries - 1:  # Deadlock
                wait = (2 ** attempt) * 0.1  # Exponential backoff
                print(f"Deadlock detected, retry {attempt+1} in {wait:.1f}s...")
                time.sleep(wait)
            else:
                raise
    return False
```

---

### Q7: Subquery vs JOIN — kab kya better?

**Answer:**
```
General rule:
  JOIN     → Better performance, optimizer can work with it better
  Subquery → Better readability sometimes, necessary for some cases

Kab JOIN prefer karo:
  - Simple lookups (user ka naam + order details)
  - Multiple tables combine karna
  - GROUP BY + aggregation with related tables

Kab Subquery zaroor hai:
  - EXISTS / NOT EXISTS checks
  - Derived tables (GROUP BY result pe filter karna)
  - Correlated subqueries (outer query ka reference chahiye)
  - Scalar value return karna (ek column, ek row)
```

```sql
-- SAME result, two approaches:

-- Subquery approach
SELECT name FROM users
WHERE id IN (
    SELECT DISTINCT user_id FROM orders WHERE status = 'cancelled'
);

-- JOIN approach (generally faster for large datasets)
SELECT DISTINCT u.name
FROM users u
INNER JOIN orders o ON u.id = o.user_id AND o.status = 'cancelled';

-- EXISTS (large subquery pe IN se better):
SELECT name FROM users u
WHERE EXISTS (
    SELECT 1 FROM orders o
    WHERE o.user_id = u.id AND o.total_amount > 10000
);
-- EXISTS short-circuits — pehla match mila toh ruk jaata hai
-- IN saari values load karta hai pehle

-- Derived table — subquery mein GROUP BY, phir filter:
SELECT category, avg_price
FROM (
    SELECT category, AVG(price) AS avg_price
    FROM products
    GROUP BY category
) AS category_stats
WHERE avg_price > 5000;
-- GROUP BY result pe directly WHERE nahi laga sakte, isliye derived table

-- Correlated subquery — outer query reference
SELECT p.name, p.price,
    (SELECT COUNT(*) FROM order_items oi
     JOIN orders o ON oi.order_id = o.id
     WHERE oi.product_id = p.id AND o.status = 'delivered'
    ) AS times_sold
FROM products p
ORDER BY times_sold DESC;
-- Ye har product ke liye ek subquery run karta hai — slow for large tables
-- Better: LEFT JOIN + GROUP BY
```

---

### Q8: SAVEPOINT kab use karte hain?

**Answer:**
```
SAVEPOINT = Transaction ke andar ek "checkpoint" — wahan tak rollback kar sako
            Puri transaction rollback nahi karni, sirf kuch hissa

Use case: Complex multi-step operations jahan partial success valid ho
  - Order create karo (SAVEPOINT)
  - Order items add karo — fail ho sakte hain (invalid product etc.)
  - Items rollback, but order reh sake
```

```sql
-- E-commerce example: Order create + items add
START TRANSACTION;

-- Step 1: Order create karo
INSERT INTO orders (user_id, total_amount, status)
VALUES (1, 0, 'pending');

SET @order_id = LAST_INSERT_ID();
SAVEPOINT order_created;  -- Checkpoint!

-- Step 2: Items add karo
INSERT INTO order_items (order_id, product_id, quantity, unit_price)
VALUES (@order_id, 101, 2, 999.00);  -- Product 101 exist karta hai

SAVEPOINT item1_added;

INSERT INTO order_items (order_id, product_id, quantity, unit_price)
VALUES (@order_id, 999, 1, 500.00);  -- Product 999 nahi hai! FK violation
-- Error aaya...

ROLLBACK TO SAVEPOINT item1_added;  -- Sirf failed item rollback, order safe

-- Order total update karo with just item1
UPDATE orders SET total_amount = 1998.00 WHERE id = @order_id;

COMMIT;  -- Order + 1 item commit ho gaya
-- Partial success ✅

-- RELEASE SAVEPOINT — agar checkpoint ki zaroorat nahi rahi
RELEASE SAVEPOINT order_created;
```

---

## Section A — All Types of JOINs (Reference)

```sql
-- RIGHT JOIN: Orders jo bina user ke hain (orphan orders)
SELECT o.id, o.total_amount, u.name
FROM users u
RIGHT JOIN orders o ON u.id = o.user_id
WHERE u.id IS NULL;

-- FULL OUTER JOIN: MySQL mein direct support nahi, UNION se banate hain
SELECT u.name, o.id AS order_id
FROM users u LEFT JOIN orders o ON u.id = o.user_id
UNION
SELECT u.name, o.id AS order_id
FROM users u RIGHT JOIN orders o ON u.id = o.user_id;

-- SELF JOIN: Employee + Manager (same table se)
CREATE TABLE employees (
    id         INT PRIMARY KEY,
    name       VARCHAR(100),
    manager_id INT,
    FOREIGN KEY (manager_id) REFERENCES employees(id)
);

SELECT e.name AS employee, m.name AS manager
FROM employees e
LEFT JOIN employees m ON e.manager_id = m.id;

-- CROSS JOIN: Cartesian product (har combination)
SELECT s.size_name, c.color_name
FROM sizes s CROSS JOIN colors c;
-- 4 sizes x 6 colors = 24 rows

-- Multi-table JOIN (4 tables):
SELECT
    u.name         AS customer,
    o.id           AS order_id,
    o.status,
    p.name         AS product,
    oi.quantity,
    oi.unit_price,
    (oi.quantity * oi.unit_price) AS line_total
FROM users u
JOIN orders      o  ON u.id          = o.user_id
JOIN order_items oi ON o.id          = oi.order_id
JOIN products    p  ON oi.product_id = p.id
WHERE o.status = 'delivered'
ORDER BY o.id, p.name;
```

---

## Section B — Index Types (Reference)

```sql
-- PRIMARY KEY → Automatically clustered B-Tree index
CREATE TABLE t (id INT PRIMARY KEY);

-- UNIQUE Index
CREATE UNIQUE INDEX idx_email ON users(email);

-- Regular B-Tree Index
CREATE INDEX idx_category ON products(category);

-- Composite Index
CREATE INDEX idx_status_date ON orders(status, created_at);

-- FULLTEXT Index (text search ke liye)
CREATE FULLTEXT INDEX idx_search ON products(name);
SELECT * FROM products
WHERE MATCH(name) AGAINST ('laptop gaming' IN BOOLEAN MODE);

-- Index management
SHOW INDEX FROM orders;
DROP INDEX idx_category ON products;
ANALYZE TABLE products;  -- Index statistics refresh karo
```

---

## Section C — Views, Stored Procedures & Triggers (Reference)

```sql
-- VIEW — Virtual table, reusable query
CREATE OR REPLACE VIEW active_product_summary AS
SELECT
    p.id, p.name, p.price, p.category,
    COUNT(oi.id)        AS times_ordered,
    SUM(oi.quantity)    AS total_units_sold
FROM products p
LEFT JOIN order_items oi ON p.id = oi.product_id
WHERE p.is_active = TRUE
GROUP BY p.id, p.name, p.price, p.category;

SELECT * FROM active_product_summary WHERE category = 'electronics';

-- STORED PROCEDURE
DELIMITER $$
CREATE PROCEDURE get_user_stats(
    IN  p_user_id     INT,
    OUT p_order_count INT,
    OUT p_total_spent DECIMAL(12,2)
)
BEGIN
    SELECT COUNT(*), COALESCE(SUM(total_amount), 0)
    INTO   p_order_count, p_total_spent
    FROM   orders
    WHERE  user_id = p_user_id AND status != 'cancelled';
END$$
DELIMITER ;

CALL get_user_stats(1, @cnt, @total);
SELECT @cnt AS order_count, @total AS total_spent;

-- TRIGGER (audit trail)
DELIMITER $$
CREATE TRIGGER before_order_delete
BEFORE DELETE ON orders
FOR EACH ROW
BEGIN
    INSERT INTO order_audit (order_id, action, old_status, deleted_at)
    VALUES (OLD.id, 'DELETE', OLD.status, NOW());
END$$
DELIMITER ;
```

---

## Python Transactions Pattern

```python
import mysql.connector
from contextlib import contextmanager

@contextmanager
def transaction(conn):
    """Transaction context manager — commit ya rollback automatically"""
    try:
        yield conn
        conn.commit()
        print("Transaction committed")
    except Exception as e:
        conn.rollback()
        print(f"Transaction rolled back: {e}")
        raise


def transfer_money(conn, from_id: int, to_id: int, amount: float):
    """Atomic money transfer — ya dono update honge, ya koi nahi"""
    with transaction(conn):
        cursor = conn.cursor(dictionary=True)

        # SELECT FOR UPDATE — dono rows lock karo (concurrent change prevent)
        cursor.execute(
            "SELECT id, balance FROM accounts WHERE id IN (%s, %s) FOR UPDATE",
            (from_id, to_id)
        )
        accounts = {row['id']: row for row in cursor.fetchall()}

        if accounts[from_id]['balance'] < amount:
            raise ValueError(
                f"Insufficient balance: {accounts[from_id]['balance']:.2f}"
            )

        cursor.execute(
            "UPDATE accounts SET balance = balance - %s WHERE id = %s",
            (amount, from_id)
        )
        cursor.execute(
            "UPDATE accounts SET balance = balance + %s WHERE id = %s",
            (amount, to_id)
        )
        cursor.close()
        print(f"Transferred Rs.{amount:.2f} from account {from_id} to {to_id}")
```

---

## Summary Table

| Topic | Key Point | Interview Tip |
|---|---|---|
| INNER JOIN | Sirf matched rows | Default JOIN — most common |
| LEFT JOIN | Left table sab rows | Anti-join: `WHERE right.id IS NULL` |
| FULL OUTER JOIN | MySQL mein UNION se | Direct support nahi MySQL mein |
| SELF JOIN | Same table ko alias se join | Employee-Manager hierarchy |
| CROSS JOIN | Cartesian product | Careful — N*M rows ban sakte hain |
| Index B-Tree | O(log N) search | Default index type in MySQL |
| Composite Index | Left prefix rule | Column order matters! |
| Covering Index | No table lookup | `Extra: Using index` in EXPLAIN |
| EXPLAIN type:ALL | Full table scan | Immediately add index |
| EXPLAIN type:const | Best case (PK match) | 1 row guaranteed |
| Isolation Default | REPEATABLE READ | MySQL InnoDB default |
| Deadlock | Consistent lock order | Retry with exponential backoff |
| SAVEPOINT | Partial rollback | Complex multi-step transactions |
| EXISTS vs IN | EXISTS short-circuits | Large subquery pe EXISTS prefer karo |
| SELECT FOR UPDATE | Row-level exclusive lock | Money transfer, inventory deduct |

---

*Next: 03_window_functions_cte_optimization.md*
