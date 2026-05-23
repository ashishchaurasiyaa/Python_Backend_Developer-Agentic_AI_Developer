# Denormalization

## Quick Reference Card
```
Normalization    → Redundancy hatao, data integrity badhao (1NF, 2NF, 3NF)
Denormalization  → Intentionally redundancy add karo — reads faster karo
Read performance → JOINs hatao — single table se answer
Write trade-off  → Faster reads, slower writes, more storage
Use when         → Read-heavy, JOINs slow, reporting queries
Interview hook   → "Niroskos booking summary table — denormalized for fast dashboard queries"
```

---

## PART 1: HINGLISH — Samjhne ke liye

### 1.1 Normalization vs Denormalization

**Analogy: Student ka notebook**

**Normalized (DRY approach):**
- Teacher ka naam sirf ek jagah (teachers table)
- Subject sirf ek jagah (subjects table)
- Schedule table mein sirf IDs

Agar teacher ka naam change karna ho → sirf 1 jagah update

**Denormalized (copies for speed):**
- Schedule table mein directly teacher name aur subject name
- Read karo → sab kuch ek hi row mein
- Agar teacher ka naam change karna ho → schedule ke hazaron rows update

```
NORMALIZED:
  users   (id, name, email)
  packages (id, name, price, destination_id)
  destinations (id, city, country)
  bookings (id, user_id, package_id, date, status)

Query: "Show booking details with user name, package, destination"
  SELECT b.*, u.name, p.name, p.price, d.city
  FROM bookings b
  JOIN users u ON b.user_id = u.id
  JOIN packages p ON b.package_id = p.id  
  JOIN destinations d ON p.destination_id = d.id
  WHERE b.id = ?
  
  4-table JOIN → 4 index lookups → relatively slow at scale

DENORMALIZED (booking_summary table):
  booking_summary (
    booking_id, date, status,
    user_name, user_email,        ← copied from users
    package_name, package_price,  ← copied from packages
    destination_city, destination_country  ← copied from destinations
  )

Query: "Show booking details"
  SELECT * FROM booking_summary WHERE booking_id = ?
  
  1 table, 1 index lookup → fast!
```

---

### 1.2 When to Denormalize

```
GOOD CANDIDATES:

1. Dashboard / Reporting queries:
   Monthly invoice dashboard: JOIN invoices + companies + items + payments
   → Pre-compute denormalized invoice_report table
   → Dashboard loads instantly vs 2-3 second join

2. Read-heavy API responses:
   Package listing API: Called 1000x/day, rarely updated
   → Denormalize package + destination + hotel info
   → Or: Cache denormalized response in Redis

3. Audit logs / Event history:
   "What was the booking status at 3pm yesterday?"
   → Snapshot the full state at time of event
   → booking_events (booking_id, timestamp, status, user_name, amount)
   → Never need to JOIN to reconstruct historical state

4. Analytics / OLAP:
   "Revenue by destination by month"
   → OLAP star schema: fact_bookings + dim_destination + dim_date
   → No JOINs needed for aggregation queries

BAD CANDIDATES:

1. Frequently updated data:
   User email → used in 50 denormalized tables
   Email changes → 50 tables need update
   Risk: partial update failure → inconsistency

2. Many-to-many relationships:
   Package ↔ Activities (multiple per package)
   Denormalized: activities stored as JSON array in package row
   Works... but complex queries on activities

3. Small lookup tables:
   country_codes (id, code, name) — 200 rows
   These tables fit in memory / Redis cache
   JOIN cost negligible — don't denormalize
```

---

### 1.3 Denormalization Techniques

#### Technique 1: Materialized Views (DB-managed denormalization)

```sql
-- PostgreSQL Materialized View
CREATE MATERIALIZED VIEW booking_summary AS
SELECT 
    b.id AS booking_id,
    b.created_at,
    b.status,
    b.amount,
    u.name AS user_name,
    u.email AS user_email,
    p.name AS package_name,
    p.price AS package_price,
    d.city AS destination_city
FROM bookings b
JOIN users u ON b.user_id = u.id
JOIN packages p ON b.package_id = p.id
JOIN destinations d ON p.destination_id = d.id;

-- Index on materialized view
CREATE INDEX idx_booking_summary_user ON booking_summary(user_email);
CREATE INDEX idx_booking_summary_status ON booking_summary(status);

-- Fast query:
SELECT * FROM booking_summary WHERE status = 'confirmed' LIMIT 50;
-- No JOINs! Single table scan.

-- Refresh when data changes:
REFRESH MATERIALIZED VIEW CONCURRENTLY booking_summary;
-- CONCURRENTLY = no lock, can still query while refreshing
-- Schedule: hourly via pg_cron, or trigger via signal

-- Trade-off:
-- Query speed: 10x faster
-- Storage: Extra table (duplicated data)
-- Freshness: Stale until refreshed (can be 1 hour old for reports)
```

#### Technique 2: Stored Redundant Fields

```python
# Denormalized field in the model itself

class Booking(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    package = models.ForeignKey(Package, on_delete=models.CASCADE)
    
    # Denormalized fields — copied at creation time
    user_name = models.CharField(max_length=200)    # Copied from user
    user_email = models.EmailField()                # Copied from user
    package_name = models.CharField(max_length=200) # Copied from package
    package_price = models.DecimalField(max_digits=10, decimal_places=2)  # Copied
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    def save(self, *args, **kwargs):
        # Auto-populate denormalized fields on creation
        if not self.pk:  # Only on creation
            self.user_name = self.user.get_full_name()
            self.user_email = self.user.email
            self.package_name = self.package.name
            self.package_price = self.package.price
        super().save(*args, **kwargs)
    
    # Now booking history always has correct price/name at TIME OF BOOKING
    # Even if package price changes later — booking shows original price
    # This is actually CORRECT business behavior!
```

#### Technique 3: Embedded JSON (Document-like in RDBMS)

```python
# Store related data as JSON column (PostgreSQL JSONField)

class Package(models.Model):
    name = models.CharField(max_length=200)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    
    # Denormalized: itinerary as JSON instead of separate table
    itinerary = models.JSONField(default=list)
    # [
    #   {"day": 1, "location": "Mumbai", "activities": ["Sightseeing", "Museum"]},
    #   {"day": 2, "location": "Goa", "activities": ["Beach", "Cruise"]},
    # ]
    
    # Denormalized: hotels as JSON
    hotels = models.JSONField(default=list)
    # [{"name": "Taj", "stars": 5, "city": "Mumbai"}]

# Query (PostgreSQL JSON operators):
Package.objects.filter(itinerary__0__location='Mumbai')  # Django ORM
# SQL: WHERE itinerary->0->>'location' = 'Mumbai'

# Trade-off:
# Pro: Single row, no JOIN for itinerary
# Con: Can't easily query "all packages visiting Goa on day 3"
```

#### Technique 4: Separate Summary/Aggregate Tables

```python
# Pre-computed aggregates

class MonthlyRevenueSummary(models.Model):
    """Pre-computed monthly revenue by destination"""
    year = models.IntegerField()
    month = models.IntegerField()
    destination = models.CharField(max_length=100)
    total_bookings = models.IntegerField()
    total_revenue = models.DecimalField(max_digits=12, decimal_places=2)
    
    class Meta:
        unique_together = ('year', 'month', 'destination')

# Populate via management command (run nightly):
from django.db.models import Count, Sum

def compute_monthly_summary():
    data = Booking.objects.filter(
        status='confirmed'
    ).values(
        'created_at__year', 'created_at__month', 'package__destination__city'
    ).annotate(
        total_bookings=Count('id'),
        total_revenue=Sum('amount')
    )
    
    for row in data:
        MonthlyRevenueSummary.objects.update_or_create(
            year=row['created_at__year'],
            month=row['created_at__month'],
            destination=row['package__destination__city'],
            defaults={
                'total_bookings': row['total_bookings'],
                'total_revenue': row['total_revenue'],
            }
        )

# Dashboard query (instant — no JOINs, no aggregation):
report = MonthlyRevenueSummary.objects.filter(year=2024).order_by('-total_revenue')
```

---

### 1.4 Maintaining Data Consistency in Denormalized Schema

```python
# Challenge: User name changed → all denormalized copies need update

# Option 1: Event-driven update
@receiver(post_save, sender=User)
def update_denormalized_user_data(sender, instance, **kwargs):
    # Only update denormalized fields if relevant fields changed
    if instance.tracker.has_changed('name') or instance.tracker.has_changed('email'):
        # Update recent bookings (last 1 year)
        Booking.objects.filter(
            user=instance,
            created_at__gte=timezone.now() - timedelta(days=365)
        ).update(
            user_name=instance.get_full_name(),
            user_email=instance.email,
        )
        # Note: Old bookings intentionally keep old name (historical record)

# Option 2: Accept staleness
# Booking stores "name at time of booking" — correct for historical records!
# If user changes name, old bookings correctly show old name
# Invoice "John Smith" stays "John Smith" even after name change to "John Kumar"
# This is actually MORE correct for legal documents!

# Option 3: Always reference via FK for live data
# Denormalize only for historical snapshots / audit trails
# For "current" user name → always join with users table
```

---

### 1.5 Star Schema — Denormalization for Analytics

```
STAR SCHEMA (Data Warehouse pattern):

  fact_bookings (central table — events/transactions)
  ┌────────────────────────────────────────────────────┐
  │ booking_id, date_key, user_key, package_key,       │
  │ destination_key, amount, discount, duration_days   │
  └────────────────────────────────────────────────────┘
         │           │           │            │
         ▼           ▼           ▼            ▼
  dim_date     dim_user    dim_package  dim_destination
  (date attrs) (user attrs)(pkg attrs) (dest attrs)
  year, month, name, city, name, type,  city, country,
  quarter, dow email, tier price, dest  region, climate

Queries without JOINs needed:
  "Revenue by country by quarter"
  SELECT d.country, t.quarter, SUM(f.amount)
  FROM fact_bookings f
  JOIN dim_destination d ON f.destination_key = d.key
  JOIN dim_date t ON f.date_key = t.key
  GROUP BY d.country, t.quarter
  
  (Only 2 joins vs potentially 5+ in normalized schema)
  
  Can also pre-aggregate into OLAP cubes for instant queries

Tools: PostgreSQL, Redshift, BigQuery, Snowflake
```

---

### 1.6 Ashish ke projects mein

```
Youngman — Invoice system:
  Normalized: Invoice → InvoiceItems → Company → Package → Tax
  
  PROBLEM: Invoice listing page (100 invoices) → 400+ queries
  
  Solution: Denormalized invoice_list view / materialized view
  
  CREATE MATERIALIZED VIEW invoice_list AS
  SELECT 
      i.id, i.created_at, i.due_date, i.status,
      i.total_amount,
      c.name AS company_name, c.gst_number,
      COUNT(ii.id) AS item_count,
      SUM(ii.quantity * ii.unit_price) AS subtotal
  FROM invoices i
  JOIN companies c ON i.company_id = c.id
  LEFT JOIN invoice_items ii ON i.id = ii.invoice_id
  GROUP BY i.id, c.id;
  
  -- Invoice listing: instant query from materialized view
  -- Invoice detail: still uses normalized tables (fresh data)
  -- Refresh: REFRESH MATERIALIZED VIEW CONCURRENTLY invoice_list
  --          (scheduled every 5 minutes via Celery Beat)

Niroskos — Booking at time of creation (immutable snapshot):
  Booking stores: user_name, package_name, package_price_at_booking
  Reason: Package price changes often, but booking price must be immutable
  "You booked at ₹25,000" must never change even if package price → ₹30,000
  This is correct behavior, not a bug!
```

---

## PART 2: ENGLISH — Interviewer ko bolne ke liye

### 2.1 Definitions

> **Normalization**: The process of organizing relational data to reduce redundancy and improve integrity. Normal forms (1NF, 2NF, 3NF, BCNF) progressively eliminate various types of redundancy.

> **Denormalization**: The intentional introduction of redundancy into a database schema to improve read performance. Trade-off: faster reads, slower writes, increased storage, consistency management overhead.

---

### 2.2 Normalization Forms Quick Reference

```
1NF (First Normal Form):
  No repeating groups, each cell has atomic value
  ✗ tags: "travel,adventure,hiking" (comma-separated)
  ✓ package_tags (package_id, tag)

2NF (Second Normal Form):
  1NF + No partial dependency (non-key attributes depend on FULL key)
  ✗ (order_id, product_id) → product_name (product_name depends only on product_id)
  ✓ Move product_name to products table

3NF (Third Normal Form):
  2NF + No transitive dependency
  ✗ employee(emp_id, dept_id, dept_name) — dept_name depends on dept_id, not emp_id
  ✓ Move dept_name to departments table

BCNF (Boyce-Codd NF): Stronger 3NF — every determinant is a candidate key

In practice: Normalize to 3NF first, then selectively denormalize for performance
```

---

### 2.3 Techniques Comparison

| Technique | How | Best For | Refresh Strategy |
|-----------|-----|----------|-----------------|
| Materialized View | DB-managed denormalized view | Reporting, complex joins | REFRESH MATERIALIZED VIEW CONCURRENTLY (scheduled) |
| Redundant fields | Store copies in main table | Historical snapshots, fast reads | On-write + signals |
| JSON embedding | Related data as JSON column | Variable structure, read-heavy nested data | Update column on change |
| Summary tables | Pre-computed aggregates | Dashboards, analytics | Nightly/hourly batch |
| Star schema | Fact + dimension tables | OLAP, business intelligence | ETL pipeline |

---

### 2.4 Real Project Answer

> "In Youngman, our invoice listing dashboard was running a 4-table JOIN on every page load — joining invoices, companies, invoice items, and SAP sync status. When the list grew to thousands of invoices, this was noticeably slow. We created a PostgreSQL materialized view `invoice_list` that pre-computes all the joined data. The listing page now queries this single view with a simple indexed SELECT — response time went from ~800ms to ~50ms. We refresh the materialized view every 5 minutes via Celery Beat, which is acceptable for the dashboard. For real-time data (individual invoice detail), we still use the normalized tables. Additionally, when a booking is created in Niroskos, we snapshot the package price at that moment as a denormalized field — so if the package price changes later, historical bookings still show the correct price at time of booking, which is correct behavior for financial records."

---

### 2.5 Common Follow-up Q&A

**Q1: What are the risks of denormalization?**
> "Three main risks: (1) Update anomalies — if the same data exists in multiple places, an update must touch all copies. If any copy is missed (due to bug or crash), you have inconsistency. (2) Storage overhead — copying data increases storage requirements, which matters at scale. (3) False sense of simplicity — the query looks simple, but the application code maintaining consistency is complex. Mitigation: event-driven updates via signals, periodic reconciliation jobs, and being very deliberate about what to denormalize versus keep normalized."

**Q2: How is denormalization different from just using a cache?**
> "A cache (Redis) stores data in a separate system that can become stale and must be invalidated. Denormalization keeps data in the database itself — the denormalized copy is part of the persistent storage. Cache has TTL and LRU eviction; denormalized tables don't spontaneously lose data. Cache improves read latency by avoiding DB entirely; denormalization improves latency by avoiding joins within the DB. They're complementary: a materialized view (denormalization) + Redis cache (avoid DB entirely for hot data) = maximum read performance."

**Q3: When should you use a materialized view vs a summary table?**
> "Materialized views are maintained by the database — `REFRESH MATERIALIZED VIEW` updates them. They're defined by a SQL query and the DB computes the result. Simple to maintain but refresh is all-or-nothing (with CONCURRENTLY it's non-blocking but slower). Summary tables are managed by application code — you write a Celery task to recompute and update. More flexible: you can partially update (update_or_create specific rows), merge results from multiple sources, or apply business logic during computation. For pure SQL aggregations → materialized view. For complex computation involving non-SQL sources or business logic → summary table."

---

## Interview Cheat Sheet

```
Normalization: Remove redundancy → integrity
Denormalization: Add redundancy → read performance

When to denormalize:
  Read-heavy, rarely written data
  Complex JOINs on hot queries
  Reporting/analytics
  Historical snapshots (price at time of booking)

Techniques:
  Materialized View: DB-managed, REFRESH periodically
  Redundant fields: Copied columns in table
  JSON fields: Nested data in one column
  Summary tables: Pre-aggregated data (dashboards)
  Star schema: OLAP — fact + dimension tables

Consistency maintenance:
  Django signals → update copies on change
  Accept staleness (historical snapshots are correct as-is)
  Periodic reconciliation (catch missed updates)

Trade-offs:
  + Faster reads (no JOINs)
  + Simpler queries
  - Slower writes (multiple tables to update)
  - More storage
  - Consistency management

My project:
  invoice_list materialized view → 800ms → 50ms
  Booking stores price_at_booking → correct historical records
  Refresh: Celery Beat every 5 min (CONCURRENTLY — no lock)
```
