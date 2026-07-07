# Database Normalization (1NF/2NF/3NF) & Denormalization

## Why It Matters

This is the classic "explain database design from scratch" interview opener —
the same category as "what is Django?" It's foundational, so it's exactly the
kind of question that gets forgotten under pressure despite being simple once
you say it out loud. Every schema-design discussion (and most senior "design
a database for X" questions) starts here.

Senior interview: "Walk me through how you'd design a normalized schema for an
e-commerce orders table, and when would you deliberately break normalization?"

---

## 🎤 The one-line answer (memorize this)

> **"Normalization is organizing a database into tables to reduce data
> redundancy and prevent update/insert/delete anomalies, by progressively
> applying rules called normal forms — 1NF, 2NF, 3NF being the ones used in
> practice. Denormalization is deliberately reversing some of that for read
> performance, once you understand the tradeoff."**

---

## Core Concepts

### The problem normalization solves (anomalies)

```
Unnormalized table:

| order_id | customer_name | customer_email     | product      | product_price |
|----------|---------------|---------------------|---------------|----------------|
| 1        | Ashish        | ashish@x.com        | Laptop        | 50000          |
| 2        | Ashish        | ashish@x.com        | Mouse         | 500            |

Problems:
- Update anomaly: customer changes email → must update EVERY row with that customer
- Insert anomaly: can't add a customer with no order yet (no order_id to hang it on)
- Delete anomaly: delete the only order → customer's email is lost entirely
```

### 1NF — First Normal Form

**Rule:** Each column holds a single atomic value; no repeating groups/arrays in a cell.

```sql
-- VIOLATES 1NF — comma-separated values in one column
CREATE TABLE orders (
    id INT,
    products VARCHAR(255)   -- 'Laptop,Mouse,Keyboard'  ❌
);

-- 1NF FIX — one row per product
CREATE TABLE order_items (
    order_id INT,
    product VARCHAR(255)
);
```

### 2NF — Second Normal Form

**Rule:** Must already be in 1NF, AND every non-key column depends on the
**entire** primary key (only matters when you have a composite key).

```sql
-- Composite key (order_id, product_id). VIOLATES 2NF:
-- product_name depends only on product_id, not on the full (order_id, product_id) key
CREATE TABLE order_items (
    order_id INT,
    product_id INT,
    product_name VARCHAR(255),   -- partial dependency ❌
    quantity INT,
    PRIMARY KEY (order_id, product_id)
);

-- 2NF FIX — split product_name into its own table
CREATE TABLE order_items (
    order_id INT,
    product_id INT,
    quantity INT,
    PRIMARY KEY (order_id, product_id)
);
CREATE TABLE products (
    product_id INT PRIMARY KEY,
    product_name VARCHAR(255)
);
```

### 3NF — Third Normal Form

**Rule:** Must already be in 2NF, AND no **transitive dependency** (non-key
column depending on another non-key column, not on the primary key directly).

```sql
-- VIOLATES 3NF — zip_code determines city, so city is transitively
-- dependent on customer_id through zip_code, not directly.
CREATE TABLE customers (
    customer_id INT PRIMARY KEY,
    zip_code VARCHAR(10),
    city VARCHAR(100)     -- transitive dependency ❌
);

-- 3NF FIX
CREATE TABLE customers (
    customer_id INT PRIMARY KEY,
    zip_code VARCHAR(10)
);
CREATE TABLE zip_codes (
    zip_code VARCHAR(10) PRIMARY KEY,
    city VARCHAR(100)
);
```

**Interview shortcut to say out loud:**
> "1NF = atomic columns. 2NF = no partial key dependency. 3NF = no transitive
> dependency. Beyond 3NF (BCNF, 4NF, 5NF) exists but is rarely applied in
> real systems — 3NF is the practical target."

---

## Denormalization — when and why to break the rules

```
Fully normalized e-commerce schema for an order summary page needs:
orders JOIN customers JOIN order_items JOIN products JOIN categories
                    ↓
5-table JOIN on every page load = slow at scale
                    ↓
Denormalize: store customer_name + product_name directly on order_items
             at write-time, accept some redundancy, skip the JOINs on read
```

| Approach | When to use |
|---|---|
| **Fully normalized** | Write-heavy systems, data integrity is critical (financial ledgers, inventory) |
| **Denormalized (redundant columns)** | Read-heavy systems where JOIN cost dominates (reporting dashboards, order history pages) |
| **Materialized views** | Middle ground — keep normalized source tables, precompute a denormalized view, refresh periodically |
| **CQRS (write model normalized, read model denormalized)** | Senior/microservices pattern — separate write DB (normalized) from read DB (denormalized, eventually consistent) |

**This repo's existing coverage this connects to:**
[16_jsonb_queries_indexes.md](16_jsonb_queries_indexes.md) — JSONB columns are a common denormalization tool in Postgres (embed related data instead of joining).
[10_postgresql_partitioning_sharding.md](10_postgresql_partitioning_sharding.md) — sharding decisions often follow from denormalization choices.

---

## Interview Q&A

**Q: Why would you deliberately denormalize a table?**
A: Read performance — avoiding expensive JOINs at query time when the system
is read-heavy and eventual consistency of the redundant copy is acceptable.
Tradeoff: more complex writes (update N places) and risk of data drift.

**Q: What's the difference between 2NF and 3NF in one sentence?**
A: 2NF removes dependencies on *part* of a composite key; 3NF removes
dependencies on *other non-key columns* (transitive dependencies).

**Q: Is a fully normalized schema always the right choice?**
A: No — it's the right *starting point*. Production systems denormalize
selectively once you've measured that JOINs are the bottleneck, not before.

---

Related: [19_optimistic_pessimistic_locking.md](19_optimistic_pessimistic_locking.md)
(normalized schemas increase JOIN/lock surface under concurrent writes),
[32_stored_procedures_triggers.md](32_stored_procedures_triggers.md).
