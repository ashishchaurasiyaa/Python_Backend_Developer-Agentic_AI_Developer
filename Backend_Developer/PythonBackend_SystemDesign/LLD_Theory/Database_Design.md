# Database Design — LLD Interview Guide
> **Category:** Must Know | **Frequency:** ★★★★★ | **Mapped to:** Niroskos + Youngman real schemas

---

## What Interviewers Ask

```
1. "Design the DB schema for [Parking Lot / Booking / Payment / Rate Limiter]"
2. "Normalize this schema" → 1NF, 2NF, 3NF
3. "This query is slow — how do you fix it?" → Indexes
4. "What indexes would you add?" → B-Tree, Composite, Partial, Covering
5. "SQL vs NoSQL — when to use which?"
6. "How do you handle N+1 queries?" → select_related, prefetch_related
7. "Transactions and ACID — explain with example"
8. "How did you design [Niroskos/Youngman] DB?"
```

---

## PART 1: NORMALIZATION

### 1NF → 2NF → 3NF

```
Bad table (not normalized):
┌──────────┬──────────────┬──────────────────┬──────────────┬─────────────┐
│ booking_id│ customer_name│ customer_email   │ package_name │ package_price│
├──────────┼──────────────┼──────────────────┼──────────────┼─────────────┤
│ BKG-001  │ Rahul Sharma │ rahul@gmail.com  │ Masai Mara   │ 85000       │
│ BKG-002  │ Rahul Sharma │ rahul@gmail.com  │ Masai Mara   │ 85000       │ ← Rahul again!
│ BKG-003  │ James Mwangi │ james@gmail.com  │ Amboseli     │ 65000       │
└──────────┴──────────────┴──────────────────┴──────────────┴─────────────┘

Problems:
  Update anomaly: Rahul email change → 2 rows update karne honge
  Insert anomaly: Package add karo bina booking ke → NULL booking_id
  Delete anomaly: Last booking delete → customer info bhi chali jaaye
```

#### 1NF — Atomic values, no repeating groups

```sql
-- Rule: har column mein ek hi value, no arrays/lists
-- Violation example:
-- phone_numbers = "+91-9876, +91-8765"  ← NOT 1NF

-- Fix:
CREATE TABLE customer_phones (
    customer_id  INT,
    phone        VARCHAR(15),
    phone_type   VARCHAR(10),   -- mobile/home/work
    PRIMARY KEY (customer_id, phone)
);
```

#### 2NF — 1NF + No partial dependency (composite PK mein)

```sql
-- Violation: composite PK (booking_id, package_id)
-- package_name depends only on package_id, not on booking_id
-- → partial dependency

-- Bad:
CREATE TABLE booking_packages (
    booking_id   INT,
    package_id   INT,
    package_name VARCHAR(100),  -- ← depends only on package_id (partial dep)
    guests       INT,            -- ← depends on both (full dep) ✓
    PRIMARY KEY (booking_id, package_id)
);

-- Fix: separate table
CREATE TABLE packages (
    id   INT PRIMARY KEY,
    name VARCHAR(100)           -- fully dependent on id ✓
);
CREATE TABLE booking_packages (
    booking_id INT,
    package_id INT REFERENCES packages(id),
    guests     INT,
    PRIMARY KEY (booking_id, package_id)
);
```

#### 3NF — 2NF + No transitive dependency

```sql
-- Violation: booking → customer_id → customer_city
-- customer_city transitively depends on booking through customer_id

-- Bad:
CREATE TABLE bookings (
    id            INT PRIMARY KEY,
    customer_id   INT,
    customer_city VARCHAR(50),  -- ← transitive dep via customer_id
    amount        DECIMAL
);

-- Fix:
CREATE TABLE customers (
    id   INT PRIMARY KEY,
    city VARCHAR(50)            -- belongs here ✓
);
CREATE TABLE bookings (
    id          INT PRIMARY KEY,
    customer_id INT REFERENCES customers(id),
    amount      DECIMAL
);
```

---

## PART 2: INDEXES

### Types

```sql
-- B-TREE (default) — range queries, equality, ORDER BY
CREATE INDEX idx_bookings_travel_date ON bookings(travel_date);
-- Use: WHERE travel_date = '2026-05-15'
-- Use: WHERE travel_date BETWEEN '2026-05-01' AND '2026-05-31'
-- Use: ORDER BY travel_date

-- COMPOSITE — multi-column filter (order matters!)
CREATE INDEX idx_bookings_tenant_status ON bookings(tenant_id, status);
-- Use: WHERE tenant_id = 1 AND status = 'CONFIRMED'  ✓
-- Use: WHERE tenant_id = 1  ✓ (leftmost prefix)
-- NOT: WHERE status = 'CONFIRMED'  ✗ (not leftmost)

-- PARTIAL — subset of rows (WHERE condition)
CREATE INDEX idx_active_bookings ON bookings(customer_id)
WHERE status NOT IN ('CANCELLED', 'EXPIRED');
-- Smaller index — only active rows indexed
-- Niroskos: most queries on active bookings only

-- COVERING — all query columns in index (no table lookup)
CREATE INDEX idx_booking_list ON bookings(tenant_id, status, travel_date, ref_code);
-- Query: SELECT ref_code FROM bookings WHERE tenant_id=1 AND status='CONFIRMED'
-- → Index covers everything — no heap fetch needed

-- UNIQUE — constraint + implicit index
CREATE UNIQUE INDEX idx_transactions_event_id ON transactions(provider_event_id);
-- Niroskos: prevent duplicate webhook processing
-- This is also a DB-level idempotency guarantee
```

### When NOT to index

```sql
-- DON'T index low-cardinality columns (few distinct values)
-- Bad: CREATE INDEX ON payments(status)
-- status has 5 values — full table scan often faster
-- Exception: partial index on rare status

-- DON'T over-index write-heavy tables
-- Each INSERT/UPDATE must update all indexes
-- Payments table: keep indexes minimal, reads < writes

-- DO index: foreign keys (Django doesn't auto-index FKs!)
CREATE INDEX idx_bookings_customer_id ON bookings(customer_id);
CREATE INDEX idx_allocations_booking_id ON payment_allocations(booking_id);
```

---

## PART 3: NIROSKOS SCHEMA DESIGN

### Core Tables

```sql
-- ─── Multi-tenant ──────────────────────────────────────────

CREATE TABLE subsidiaries (
    id              SERIAL PRIMARY KEY,
    code            VARCHAR(10) UNIQUE NOT NULL,  -- 'niroskos_ke', 'niroskos_in'
    name            VARCHAR(100),
    country         VARCHAR(2),                   -- ISO: 'KE', 'IN'
    currency        VARCHAR(3),                   -- 'KES', 'INR'
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- ─── Customers ─────────────────────────────────────────────

CREATE TABLE customers (
    id              SERIAL PRIMARY KEY,
    subsidiary_id   INT NOT NULL REFERENCES subsidiaries(id),
    email           VARCHAR(255) NOT NULL,
    phone           VARCHAR(20),
    first_name      VARCHAR(100),
    last_name       VARCHAR(100),
    nationality     VARCHAR(2),
    odoo_partner_id INT,                          -- Sync with Odoo CRM
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (subsidiary_id, email)                 -- email unique per tenant
);

CREATE INDEX idx_customers_subsidiary ON customers(subsidiary_id);
CREATE INDEX idx_customers_odoo ON customers(odoo_partner_id) WHERE odoo_partner_id IS NOT NULL;

-- ─── Packages (Safari Products) ────────────────────────────

CREATE TABLE packages (
    id              SERIAL PRIMARY KEY,
    subsidiary_id   INT NOT NULL REFERENCES subsidiaries(id),
    name            VARCHAR(200) NOT NULL,
    package_type    VARCHAR(50),                  -- 'safari', 'transfer', 'accommodation'
    base_price      DECIMAL(12, 2) NOT NULL,
    capacity        INT NOT NULL,                 -- max guests per date
    duration_days   INT,
    meeting_point   TEXT,
    is_active       BOOLEAN DEFAULT TRUE,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_packages_subsidiary_active ON packages(subsidiary_id) WHERE is_active = TRUE;

-- ─── Bookings (State Machine) ──────────────────────────────

CREATE TABLE bookings (
    id                  SERIAL PRIMARY KEY,
    ref_code            VARCHAR(20) UNIQUE NOT NULL,          -- BKG-001
    subsidiary_id       INT NOT NULL REFERENCES subsidiaries(id),
    customer_id         INT NOT NULL REFERENCES customers(id),
    package_id          INT NOT NULL REFERENCES packages(id),

    -- State machine
    status              VARCHAR(20) NOT NULL DEFAULT 'DRAFT',
    -- CHECK constraint prevents invalid status at DB level
    CONSTRAINT chk_booking_status CHECK (
        status IN ('DRAFT','CONFIRMED','PAID','CANCELLED',
                   'RESCHEDULED','AMENDED','COMPLETED','EXPIRED',
                   'REFUND_PENDING','REFUNDED')
    ),

    -- Dates
    travel_date         DATE NOT NULL,
    amendment_deadline  DATE,                     -- travel_date - 3 days

    -- Guests & Pricing
    guests              INT NOT NULL DEFAULT 1,
    base_price          DECIMAL(12,2) NOT NULL,
    discount_amount     DECIMAL(12,2) DEFAULT 0,
    total_amount        DECIMAL(12,2) NOT NULL,
    currency            VARCHAR(3) NOT NULL,

    -- Payment cache (refreshed via Django Signal on PaymentAllocation)
    amount_paid         DECIMAL(12,2) DEFAULT 0,  -- cached sum of allocations
    balance_due         DECIMAL(12,2),            -- total_amount - amount_paid

    -- Draft expiry (BookingDraft pattern)
    draft_expires_at    TIMESTAMPTZ,

    -- Flags
    reminder_sent       BOOLEAN DEFAULT FALSE,

    -- Audit
    created_by_id       INT REFERENCES staff(id),
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    updated_at          TIMESTAMPTZ DEFAULT NOW(),
    deleted_at          TIMESTAMPTZ                           -- soft delete
);

CREATE INDEX idx_bookings_subsidiary_status ON bookings(subsidiary_id, status);
CREATE INDEX idx_bookings_customer ON bookings(customer_id);
CREATE INDEX idx_bookings_travel_date ON bookings(travel_date);
CREATE INDEX idx_bookings_active ON bookings(subsidiary_id, travel_date)
    WHERE status NOT IN ('CANCELLED', 'EXPIRED', 'REFUNDED');
-- Covering index for booking list view
CREATE INDEX idx_bookings_list ON bookings(subsidiary_id, status, travel_date, ref_code, amount_paid);

-- ─── Transactions (Payments) ───────────────────────────────

CREATE TABLE transactions (
    id                  SERIAL PRIMARY KEY,
    booking_id          INT NOT NULL REFERENCES bookings(id),
    payment_method      VARCHAR(20) NOT NULL,                 -- 'card','crypto','mpesa'
    status              VARCHAR(20) NOT NULL DEFAULT 'pending',
    amount              DECIMAL(12,2) NOT NULL,
    currency            VARCHAR(3) NOT NULL,
    idempotency_key     VARCHAR(255) UNIQUE NOT NULL,         -- client-provided
    provider_txn_id     VARCHAR(255),                        -- Stripe pi_xxx
    provider_event_id   VARCHAR(255) UNIQUE,                 -- Stripe evt_xxx (dedup webhook)
    gateway_response    JSONB,                               -- raw provider response
    attempt_count       INT DEFAULT 1,
    error_message       TEXT,
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    completed_at        TIMESTAMPTZ
);

CREATE INDEX idx_transactions_booking ON transactions(booking_id);
CREATE INDEX idx_transactions_status ON transactions(status) WHERE status = 'pending';

-- ─── Payment Allocations ───────────────────────────────────

CREATE TABLE payment_allocations (
    id              SERIAL PRIMARY KEY,
    booking_id      INT NOT NULL REFERENCES bookings(id),
    transaction_id  INT NOT NULL REFERENCES transactions(id),
    amount          DECIMAL(12,2) NOT NULL,
    allocation_type VARCHAR(20) DEFAULT 'standard',          -- advance/balance
    idempotency_key VARCHAR(255) UNIQUE NOT NULL,
    created_at      TIMESTAMPTZ DEFAULT NOW()
    -- post_save signal on this → booking.refresh_payment_cache()
);

CREATE INDEX idx_allocations_booking ON payment_allocations(booking_id);

-- ─── Staff + RBAC ──────────────────────────────────────────

CREATE TABLE staff (
    id              SERIAL PRIMARY KEY,
    user_id         INT NOT NULL REFERENCES auth_user(id),
    subsidiary_id   INT NOT NULL REFERENCES subsidiaries(id),
    role            VARCHAR(50) NOT NULL,
    -- 'admin','manager','guide','finance','reception'
    is_active       BOOLEAN DEFAULT TRUE,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE staff_extra_groups (
    staff_id        INT REFERENCES staff(id),
    group_id        INT REFERENCES auth_group(id),
    PRIMARY KEY (staff_id, group_id)
    -- m2m_changed signal → sync user.groups
);

-- ─── Audit Log ─────────────────────────────────────────────

CREATE TABLE audit_logs (
    id              BIGSERIAL PRIMARY KEY,              -- BIGSERIAL for high volume
    entity_type     VARCHAR(50) NOT NULL,               -- 'booking','payment','staff'
    entity_id       INT NOT NULL,
    action          VARCHAR(50) NOT NULL,               -- 'status_change','payment_received'
    old_value       JSONB,
    new_value       JSONB,
    performed_by_id INT REFERENCES staff(id),
    ip_address      INET,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- Partition by month (high volume table)
-- CREATE TABLE audit_logs_2026_04 PARTITION OF audit_logs
--     FOR VALUES FROM ('2026-04-01') TO ('2026-05-01');

CREATE INDEX idx_audit_entity ON audit_logs(entity_type, entity_id);
CREATE INDEX idx_audit_created ON audit_logs(created_at);
```

---

## PART 4: N+1 QUERY PROBLEM

```python
# ─── THE PROBLEM ────────────────────────────────────────────

# BAD: N+1 — 1 query for bookings + N queries for each customer
bookings = Booking.objects.filter(subsidiary_id=1, status='CONFIRMED')
for booking in bookings:
    print(booking.customer.email)   # ← Each iteration = 1 DB query!
    # 100 bookings = 101 queries

# ─── FIX 1: select_related (FK / OneToOne → JOIN) ──────────

bookings = Booking.objects.filter(
    subsidiary_id=1, status='CONFIRMED'
).select_related(
    'customer',           # JOIN customers
    'package',            # JOIN packages
    'created_by'          # JOIN staff
)
# 1 query with JOINs ✓
for booking in bookings:
    print(booking.customer.email)   # No extra query


# ─── FIX 2: prefetch_related (ManyToMany / reverse FK) ──────

bookings = Booking.objects.filter(
    subsidiary_id=1
).prefetch_related(
    'payment_allocations',            # Separate query, Python-side join
    'payment_allocations__transaction' # Nested prefetch
)
# 2 queries total ✓ (1 for bookings, 1 for all allocations)


# ─── FIX 3: values() / annotate() — avoid ORM object overhead

from django.db.models import Sum, Count, Q

# Payment summary without loading all objects
summary = Booking.objects.filter(
    subsidiary_id=1, status='CONFIRMED'
).annotate(
    total_paid=Sum('payment_allocations__amount'),
    payment_count=Count('payment_allocations')
).values('ref_code', 'total_amount', 'total_paid', 'payment_count')
# 1 query with GROUP BY ✓


# ─── FIX 4: Cached property (Niroskos refresh_payment_cache) ──

class Booking(models.Model):
    # Cached columns — updated via Django Signal
    amount_paid  = models.DecimalField(default=0)
    balance_due  = models.DecimalField(default=0)

    def refresh_payment_cache(self):
        """
        Called by PaymentAllocation post_save signal.
        Aggregates all allocations → stores in DB columns.
        Booking list reads from column (fast) — no JOIN needed.
        """
        from django.db.models import Sum
        total = self.payment_allocations.aggregate(
            total=Sum('amount')
        )['total'] or Decimal('0')

        Booking.objects.filter(id=self.id).update(
            amount_paid = total,
            balance_due = self.total_amount - total
        )
```

---

## PART 5: TRANSACTIONS & ACID

```python
# ─── ACID ───────────────────────────────────────────────────
# A — Atomicity:   All or nothing
# C — Consistency: DB rules always satisfied (constraints, FKs)
# I — Isolation:   Concurrent transactions don't see each other's partial work
# D — Durability:  Committed data survives crashes

# ─── Django @transaction.atomic ─────────────────────────────

from django.db import transaction

@transaction.atomic
def confirm_booking_and_allocate(booking_id, payment_id, amount):
    """
    Atomic: booking status update + payment allocation together.
    If allocation fails → booking status rollback hota hai.
    Niroskos mein: payment_service.py mein yeh pattern tha.
    """
    booking = Booking.objects.select_for_update().get(id=booking_id)
    # select_for_update() → row-level lock (prevents concurrent confirms)

    if booking.status != 'CONFIRMED':
        raise ValueError(f"Cannot allocate to {booking.status} booking")

    booking.status = 'PAID'
    booking.save()

    PaymentAllocation.objects.create(
        booking_id     = booking_id,
        transaction_id = payment_id,
        amount         = amount,
        idempotency_key = f"{booking_id}_{payment_id}"
    )
    # If this fails → booking.status rollback to previous ✓


# ─── Isolation Levels ───────────────────────────────────────

# READ COMMITTED (PostgreSQL default):
#   Sees only committed rows — no dirty reads
#   Problem: non-repeatable reads (same query = different results in same txn)

# REPEATABLE READ:
#   Snapshot at transaction start — consistent reads
#   Use for: booking availability check + reserve (prevent phantom reads)

# SERIALIZABLE:
#   Full isolation — as if serial execution
#   Slowest, but strictest
#   Use for: financial ledger, wallet balance updates


# ─── Optimistic vs Pessimistic Locking ──────────────────────

# PESSIMISTIC: select_for_update() — lock row immediately
# Use: short transactions, high contention (booking confirm)
booking = Booking.objects.select_for_update().get(id=booking_id)


# OPTIMISTIC: version field — check before update
# Use: long transactions, low contention (wallet balance)
rows_updated = Wallet.objects.filter(
    id=wallet_id,
    version=current_version    # ← If another transaction updated, this = 0 rows
).update(
    balance=new_balance,
    version=current_version + 1
)
if rows_updated == 0:
    raise ConcurrentUpdateError("Wallet modified by another transaction — retry")


# ─── Savepoints ─────────────────────────────────────────────

@transaction.atomic
def complex_booking_flow(booking_id):
    booking = Booking.objects.get(id=booking_id)

    with transaction.atomic():      # ← Nested = SAVEPOINT
        try:
            send_confirmation_email(booking)
        except EmailError:
            # Email failed — rollback only email part
            # Outer transaction still alive
            pass

    # Booking save still happens even if email failed
    booking.status = 'CONFIRMED'
    booking.save()
```

---

## PART 6: SQL QUERIES (Common Interview Questions)

```sql
-- ─── 1. Top 5 customers by booking value per subsidiary ─────

SELECT
    c.id,
    c.first_name || ' ' || c.last_name AS customer_name,
    COUNT(b.id)           AS total_bookings,
    SUM(b.total_amount)   AS total_value,
    RANK() OVER (
        PARTITION BY b.subsidiary_id
        ORDER BY SUM(b.total_amount) DESC
    ) AS rank_in_subsidiary
FROM bookings b
JOIN customers c ON c.id = b.customer_id
WHERE b.status NOT IN ('CANCELLED', 'EXPIRED')
GROUP BY c.id, c.first_name, c.last_name, b.subsidiary_id
HAVING RANK() OVER (...) <= 5;


-- ─── 2. Bookings with outstanding balance ───────────────────

SELECT
    b.ref_code,
    b.total_amount,
    b.amount_paid,
    b.balance_due,
    b.travel_date,
    c.email
FROM bookings b
JOIN customers c ON c.id = b.customer_id
WHERE b.status = 'CONFIRMED'
  AND b.balance_due > 0
  AND b.travel_date >= CURRENT_DATE
ORDER BY b.travel_date;


-- ─── 3. Monthly revenue per subsidiary ──────────────────────

SELECT
    s.code,
    DATE_TRUNC('month', t.completed_at) AS month,
    COUNT(DISTINCT b.id)                AS bookings,
    SUM(pa.amount)                      AS revenue
FROM payment_allocations pa
JOIN transactions t  ON t.id = pa.transaction_id AND t.status = 'completed'
JOIN bookings b      ON b.id = pa.booking_id
JOIN subsidiaries s  ON s.id = b.subsidiary_id
WHERE t.completed_at >= NOW() - INTERVAL '12 months'
GROUP BY s.code, DATE_TRUNC('month', t.completed_at)
ORDER BY s.code, month;


-- ─── 4. Packages with availability on a date ────────────────

SELECT
    p.id,
    p.name,
    p.capacity,
    COUNT(b.id)                    AS booked_guests,
    p.capacity - COUNT(b.id)       AS available_spots
FROM packages p
LEFT JOIN bookings b
    ON b.package_id = p.id
    AND b.travel_date = '2026-05-15'
    AND b.status NOT IN ('CANCELLED', 'EXPIRED', 'DRAFT')
WHERE p.subsidiary_id = 1
  AND p.is_active = TRUE
GROUP BY p.id, p.name, p.capacity
HAVING p.capacity - COUNT(b.id) > 0;


-- ─── 5. Find duplicate payments (same booking, same amount, same day) ──

SELECT
    booking_id,
    amount,
    DATE(created_at)   AS payment_date,
    COUNT(*)           AS duplicate_count
FROM transactions
WHERE status = 'completed'
GROUP BY booking_id, amount, DATE(created_at)
HAVING COUNT(*) > 1;


-- ─── 6. Window function: running total per booking ──────────

SELECT
    pa.booking_id,
    pa.created_at,
    pa.amount,
    SUM(pa.amount) OVER (
        PARTITION BY pa.booking_id
        ORDER BY pa.created_at
        ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
    ) AS running_total
FROM payment_allocations pa
WHERE pa.booking_id = 123;


-- ─── 7. Bookings approaching amendment deadline ─────────────

SELECT
    b.ref_code,
    b.travel_date,
    b.amendment_deadline,
    b.amendment_deadline - CURRENT_DATE AS days_until_locked,
    c.email
FROM bookings b
JOIN customers c ON c.id = b.customer_id
WHERE b.status = 'CONFIRMED'
  AND b.amendment_deadline BETWEEN CURRENT_DATE AND CURRENT_DATE + 3
ORDER BY b.amendment_deadline;
```

---

## PART 7: SQL vs NoSQL — When to Use

```
SQL (PostgreSQL):
  ✓ ACID transactions needed (payments, bookings)
  ✓ Complex joins (booking + customer + package + payment)
  ✓ Strong consistency required
  ✓ Schema is stable and known
  ✓ Reporting and analytics (GROUP BY, window functions)
  → Niroskos: ALL core data in PostgreSQL

NoSQL — Redis:
  ✓ Cache (SAP token, booking payment cache)
  ✓ Rate limiting (token bucket state)
  ✓ Session storage
  ✓ Task queue broker (Celery)
  ✓ Pub-Sub (real-time notifications)
  → Niroskos: Redis for cache + Celery broker

NoSQL — MongoDB:
  ✓ Flexible schema (logs, audit trails, config)
  ✓ Document-oriented (nested data without joins)
  ✗ Not for financial data (no ACID multi-document)

NoSQL — Cassandra:
  ✓ Time-series data (IoT, logs, metrics)
  ✓ High write throughput
  ✓ Geographically distributed
  ✗ No joins, no transactions

Elasticsearch:
  ✓ Full-text search (customer search, booking search)
  ✓ Log aggregation (ELK stack)
  → Niroskos: customer/booking search (if implemented)

Rule of thumb:
  Financial data      → PostgreSQL (ACID)
  Cache / sessions    → Redis
  Logs / events       → MongoDB or Elasticsearch
  Time-series metrics → InfluxDB / TimescaleDB
```

---

## PART 8: YOUNGMAN SCHEMA PATTERNS

```sql
-- ─── Challan + Delivery Pipeline ────────────────────────────

CREATE TABLE challans (
    id              SERIAL PRIMARY KEY,
    challan_no      VARCHAR(50) UNIQUE NOT NULL,
    customer_id     INT REFERENCES customers(id),
    status          VARCHAR(30) DEFAULT 'CREATED',
    -- CREATED → VEHICLE_LOADED → OUT_FOR_DELIVERY → DELIVERED → PICKUP_DONE
    total_amount    DECIMAL(12,2),
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE challan_items (
    id              SERIAL PRIMARY KEY,
    challan_id      INT NOT NULL REFERENCES challans(id),
    product_code    VARCHAR(50),
    quantity        INT,
    unit_price      DECIMAL(12,2),
    -- No total — computed: quantity * unit_price
    CONSTRAINT chk_positive_qty CHECK (quantity > 0)
);

-- Delivery stages (Observer pattern fires event on status change)
CREATE TABLE challan_stage_logs (
    id              SERIAL PRIMARY KEY,
    challan_id      INT NOT NULL REFERENCES challans(id),
    from_status     VARCHAR(30),
    to_status       VARCHAR(30),
    changed_by_id   INT REFERENCES users(id),
    notes           TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_stage_logs_challan ON challan_stage_logs(challan_id);

-- ─── EwayBill (GST) ─────────────────────────────────────────

CREATE TABLE eway_bills (
    id              SERIAL PRIMARY KEY,
    challan_id      INT REFERENCES challans(id),
    ewb_no          VARCHAR(20) UNIQUE,          -- Government EWB number
    ewb_type        VARCHAR(20),                 -- 'Delivery', 'Pickup'
    supply_type     VARCHAR(10),                 -- 'Outward', 'Inward'
    consignor_gstin VARCHAR(15),
    consignee_gstin VARCHAR(15),
    total_value     DECIMAL(12,2),
    status          VARCHAR(20) DEFAULT 'ACTIVE', -- ACTIVE/CANCELLED/EXTENDED
    generated_at    TIMESTAMPTZ DEFAULT NOW(),
    valid_till      TIMESTAMPTZ,
    api_response    JSONB                        -- MasterIndia raw response
);

-- ─── RBAC ────────────────────────────────────────────────────

CREATE TABLE roles (
    id          SERIAL PRIMARY KEY,
    name        VARCHAR(50) UNIQUE NOT NULL,
    permissions JSONB NOT NULL DEFAULT '{}'
    -- {'can_approve_challan': true, 'can_view_financials': false}
);

CREATE TABLE user_roles (
    user_id     INT REFERENCES users(id),
    role_id     INT REFERENCES roles(id),
    assigned_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (user_id, role_id)
);
```

---

## PART 9: INTERVIEW ANSWERS

**Q: "Booking system ka DB schema design karo"**
> "Core tables: customers, packages, bookings, transactions, payment_allocations. Bookings has a status column with a CHECK constraint for valid states. Amount_paid and balance_due are cached columns — updated via Django Signal on PaymentAllocation save — this prevents N+1 queries on booking list views. Transactions has provider_event_id with a UNIQUE constraint — this is the DB-level idempotency guarantee for webhook deduplication. Composite indexes on (subsidiary_id, status) and (subsidiary_id, travel_date) for the most common query patterns. Partial index on active bookings only — smaller, faster."

**Q: "N+1 query — explain and fix"**
> "N+1 is when you fetch N records and then execute N additional queries for related data. Classic example: list 100 bookings, then for each booking fetch customer.email — 101 queries. Fix in Django: select_related for FK/OneToOne (generates JOIN), prefetch_related for ManyToMany/reverse FK (2 queries, Python-side join). For aggregates — annotate() with Sum/Count instead of looping. In Niroskos: booking list showed amount_paid — we cached it in a DB column updated via Signal, so the list query needed no JOIN to payment_allocations."

**Q: "When would you denormalize?"**
> "When read performance matters more than write simplicity. Three cases: (1) Booking.amount_paid — a cached aggregate, updated via Signal. Avoids SUM join on every list view. (2) Booking.travel_date duplicated on booking_items — allows direct date queries without JOIN to bookings. (3) JSONB columns for flexible data — eway_bills.api_response stores raw provider response without schema migration. The rule: normalize first, denormalize only when you have a measured performance problem."

---

*Last Updated: April 2026 | SDE-2 Interview Prep — Niroskos + Youngman DB Design*
