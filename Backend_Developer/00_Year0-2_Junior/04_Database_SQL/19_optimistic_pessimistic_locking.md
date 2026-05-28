# Optimistic vs Pessimistic Locking

## Why It Matters (Senior 5 YOE Context)

Concurrent writes to same row → **race conditions**:
- Two users buy last unit of inventory → both succeed, oversold
- Concurrent balance update → one's update lost
- Double-spending in financial transfers

Locking strategies prevent these. Choice depends on contention:
- **Pessimistic**: lock row before reading. Best when high contention.
- **Optimistic**: read, compute, write with check. Best when low contention.

Senior interview: "Two users click 'buy last item' at same time — how do you prevent overselling?" → SELECT FOR UPDATE or version column.

---

## Core Concepts

### Pessimistic Locking — `SELECT FOR UPDATE`

```sql
BEGIN;
SELECT * FROM products WHERE id = 5 FOR UPDATE;   -- locks row
-- Other transactions wait here
UPDATE products SET stock = stock - 1 WHERE id = 5;
COMMIT;  -- releases lock
```

**Variants:**
- `FOR UPDATE` — exclusive lock, blocks reads with `FOR UPDATE`
- `FOR NO KEY UPDATE` — weaker (allows FK references)
- `FOR SHARE` — shared lock (others can read but not write)
- `FOR UPDATE NOWAIT` — fail immediately if locked
- `FOR UPDATE SKIP LOCKED` — skip locked rows (job queue pattern)

### Django ORM — `select_for_update()`

```python
from django.db import transaction


@transaction.atomic
def buy_item(user, product_id):
    product = (
        Product.objects
        .select_for_update()   # adds FOR UPDATE
        .get(pk=product_id)
    )
    if product.stock <= 0:
        raise OutOfStock()
    product.stock -= 1
    product.save()
    Order.objects.create(user=user, product=product)
```

Other concurrent calls to `buy_item` for same product → block until first transaction commits.

### `select_for_update(nowait=True)` and `skip_locked=True`

```python
# NOWAIT — fail immediately
try:
    Product.objects.select_for_update(nowait=True).get(pk=5)
except DatabaseError:
    return "Try again"


# SKIP LOCKED — useful for job queues
@transaction.atomic
def claim_job():
    job = (
        Job.objects
        .select_for_update(skip_locked=True)
        .filter(status='pending')
        .first()
    )
    if job:
        job.status = 'processing'
        job.save()
    return job
```

`SKIP LOCKED` = essential for concurrent workers (Celery-like patterns).

### SQLAlchemy — `with_for_update()`

```python
from sqlalchemy import select

with Session() as session:
    with session.begin():
        stmt = select(Product).where(Product.id == 5).with_for_update()
        product = session.execute(stmt).scalar_one()
        product.stock -= 1


# Async
async with AsyncSession() as session:
    async with session.begin():
        stmt = select(Product).where(Product.id == 5).with_for_update()
        result = await session.execute(stmt)
        product = result.scalar_one()
        product.stock -= 1
```

### Optimistic Locking — Version Column

```python
class Product(models.Model):
    name = models.CharField(max_length=200)
    stock = models.IntegerField()
    version = models.IntegerField(default=0)
```

```python
def buy_item_optimistic(product_id):
    for attempt in range(5):
        product = Product.objects.get(pk=product_id)
        if product.stock <= 0:
            raise OutOfStock()

        # Atomic UPDATE with version check
        updated = Product.objects.filter(
            pk=product_id,
            version=product.version,
        ).update(
            stock=product.stock - 1,
            version=product.version + 1,
        )

        if updated == 1:
            return  # success
        # Else: someone else updated, retry
        time.sleep(0.05 * (2 ** attempt))  # exponential backoff

    raise ConcurrencyError("Too many concurrent updates")
```

### SQLAlchemy ORM Version Counter

```python
class Product(Base):
    __tablename__ = 'products'
    __mapper_args__ = {'version_id_col': version}

    id = Column(Integer, primary_key=True)
    stock = Column(Integer)
    version = Column(Integer, nullable=False)


# Automatically adds WHERE version = X to UPDATE
# Raises StaleDataError on mismatch
```

### Combining — Pessimistic + Retry on Deadlock

```python
from django.db import OperationalError


def buy_item_robust(product_id):
    for attempt in range(3):
        try:
            with transaction.atomic():
                product = Product.objects.select_for_update().get(pk=product_id)
                product.stock -= 1
                product.save()
                return
        except OperationalError as e:
            if 'deadlock' in str(e).lower():
                time.sleep(0.1 * (2 ** attempt))
                continue
            raise
    raise Exception("Max retries")
```

### Locking Range (Gap Locks)

```sql
-- Lock all rows matching condition + gaps (prevents INSERT)
SELECT * FROM orders WHERE created_at > '2026-01-01' FOR UPDATE;
```

MySQL InnoDB uses next-key locks (row + gap) at REPEATABLE READ. Prevents phantom reads.

### Distributed Locks (Redis)

For locking across multiple DBs or non-DB resources:

```python
from redis.lock import Lock

with Lock(redis_client, 'inventory:5', timeout=10) as lock:
    # Critical section
    ...
```

Redlock algorithm for multi-Redis HA setups.

---

## How It Works Internally

### PostgreSQL Lock Modes

```
AccessShareLock        — SELECT (no lock conflict with each other)
RowShareLock           — SELECT FOR SHARE
RowExclusiveLock       — INSERT/UPDATE/DELETE
ShareLock              — index creation (concurrent CREATE INDEX uses ShareUpdateExclusive)
ShareRowExclusiveLock  — explicit LOCK TABLE
ExclusiveLock          — refreshing materialized view
AccessExclusiveLock    — ALTER TABLE, DROP TABLE
```

`pg_locks` view shows current locks.

### Deadlock Detection

PostgreSQL detects deadlocks automatically (default 1s). One transaction is aborted with `40P01` SQLSTATE.

```sql
-- Configure threshold
SET deadlock_timeout = '1s';
```

### Lock Wait

```sql
-- Postgres: wait forever
SET lock_timeout = '5s';   -- abort after 5s

-- MySQL: innodb_lock_wait_timeout = 50s default
```

---

## Common Pitfalls

### 1. Forgetting `transaction.atomic()`

```python
# WRONG — select_for_update outside transaction = ProgrammingError
Product.objects.select_for_update().get(pk=5)


# RIGHT
with transaction.atomic():
    Product.objects.select_for_update().get(pk=5)
```

### 2. Locking Too Wide (Table Lock)

```sql
LOCK TABLE products IN EXCLUSIVE MODE;   -- blocks everything
```

Avoid table locks. Use row-level always.

### 3. Long-Held Lock = Cascading Wait

```python
@transaction.atomic
def slow():
    product = Product.objects.select_for_update().get(pk=5)
    # ... external API call (5 seconds!) ...
    # ... all other requests wait
```

**Fix:** Minimize critical section. External calls outside transaction.

### 4. Optimistic Retry Without Backoff

```python
while True:
    # ... try update ...
    if updated: break
    # busy loop = CPU melt
```

Add `time.sleep` with exponential backoff.

### 5. Deadlock on Same Two Rows in Different Order

```python
# Transaction A: lock row 1 then row 2
# Transaction B: lock row 2 then row 1
# → Deadlock
```

**Fix:** Always lock in same order (by primary key).

### 6. SKIP LOCKED Without ORDER BY

```python
# Race condition: workers grab different rows but not deterministic
Job.objects.select_for_update(skip_locked=True).filter(status='pending').first()
```

Add `.order_by('priority', 'created_at')` for determinism.

### 7. Version Column Not on Index

```python
Product.objects.filter(pk=X, version=Y).update(...)
```

Without index on `(pk, version)` — full row check. Usually fine since pk is indexed.

---

## Interview Q&A

**Q1:** Pessimistic vs Optimistic — kab kya?
**A:** Pessimistic (`SELECT FOR UPDATE`): high write contention — lock prevents conflict at cost of throughput. Optimistic (version column + retry): low contention — most updates succeed first try, retry rare. For inventory/payments (rare conflicts but critical): optimistic with version. For workflows with frequent overlap: pessimistic.

**Q2:** SELECT FOR UPDATE SKIP LOCKED ka use case?
**A:** Job queue — multiple workers each grab next pending job without waiting. Without SKIP LOCKED, workers serialize through same row. With it: parallel claim. Pattern: `SELECT ... WHERE status='pending' FOR UPDATE SKIP LOCKED LIMIT 1`.

**Q3:** Deadlock kaise prevent karoge?
**A:** (1) Always acquire locks in same order (e.g., by primary key ascending). (2) Keep transactions short. (3) `lock_timeout` so long waits fail fast. (4) Retry on deadlock detection (PostgreSQL aborts one txn). (5) Use lower isolation level when possible (Read Committed vs Serializable).

**Q4:** Inventory decrement safe kaise karoge?
**A:** Option 1 (pessimistic): `SELECT ... FOR UPDATE` + check stock + update inside transaction. Option 2 (optimistic): version column + retry. Option 3 (atomic): `UPDATE products SET stock = stock - 1 WHERE id = X AND stock > 0` (single statement, atomic) + check affected rows.

**Q5:** Long-running transaction holding lock — debug?
**A:** PostgreSQL: `pg_stat_activity` shows current queries. `pg_locks` shows held locks. `SELECT pg_blocking_pids(pid)` for blockers. MySQL: `SHOW PROCESSLIST`, `information_schema.innodb_lock_waits`. Set `statement_timeout` / `idle_in_transaction_session_timeout`.

**Q6:** Distributed lock when DB-level not enough?
**A:** Redis Redlock or single-Redis `SET key value NX EX ttl`. Use when: locking across multiple DBs, locking non-DB resources (files, external APIs), or when DB pool exhaustion is concern. Watch out: split-brain risk in single-Redis (use Redlock for production).

**Q7:** Phantom reads aur SELECT FOR UPDATE ka connection?
**A:** Phantom = same query returns different row count due to concurrent INSERTs. Postgres serializable isolation prevents. MySQL InnoDB uses next-key locks at REPEATABLE READ. `SELECT ... WHERE x=5 FOR UPDATE` locks gaps too — prevents new rows matching condition.

**Q8:** Retry-on-conflict pattern with exponential backoff — implementation?
**A:**
```python
for attempt in range(5):
    try:
        # ... try update with version check
        if updated == 1: return
    except IntegrityError:
        pass
    sleep_time = min(0.05 * (2 ** attempt) + random.random() * 0.05, 5)
    time.sleep(sleep_time)
raise MaxRetriesExceeded()
```
Jitter prevents thundering herd.

---

## Real-World Use Cases

### 1. Ticket Booking

```python
@transaction.atomic
def book_seat(seat_id, user):
    seat = Seat.objects.select_for_update().get(pk=seat_id)
    if seat.status != 'available':
        raise SeatUnavailable()
    seat.status = 'booked'
    seat.booked_by = user
    seat.save()
```

### 2. Account Transfer

```python
@transaction.atomic
def transfer(from_id, to_id, amount):
    # Lock in PK order to prevent deadlock
    ids = sorted([from_id, to_id])
    accounts = (
        Account.objects
        .select_for_update()
        .filter(pk__in=ids)
        .order_by('pk')
    )
    from_acc = accounts.get(pk=from_id)
    to_acc = accounts.get(pk=to_id)
    if from_acc.balance < amount:
        raise InsufficientFunds()
    from_acc.balance -= amount
    to_acc.balance += amount
    from_acc.save()
    to_acc.save()
```

### 3. Distributed Job Queue

```python
@transaction.atomic
def claim_next_job(worker_id):
    job = (
        Job.objects
        .select_for_update(skip_locked=True)
        .filter(status='pending')
        .order_by('priority', 'created_at')
        .first()
    )
    if job:
        job.status = 'processing'
        job.worker_id = worker_id
        job.save()
    return job
```

---

## References

- [PostgreSQL Explicit Locking](https://www.postgresql.org/docs/current/explicit-locking.html)
- [InnoDB Locking](https://dev.mysql.com/doc/refman/8.0/en/innodb-locking.html)
- [Django select_for_update](https://docs.djangoproject.com/en/5.0/ref/models/querysets/#select-for-update)
- [SQLAlchemy version_id_col](https://docs.sqlalchemy.org/en/20/orm/versioning.html)
- Designing Data-Intensive Applications — Ch. 7 (Transactions)
