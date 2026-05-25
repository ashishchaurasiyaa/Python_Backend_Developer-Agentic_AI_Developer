# Isolation Levels & Anomalies — Transaction Deep Dive

## Why It Matters

Wrong isolation level → bugs that pass tests, fail in production at scale:
- **Lost updates** → two transfers, one disappears
- **Phantom reads** → report count differs from sum
- **Write skew** → constraint violated despite check
- **Dirty reads** → reads uncommitted (rolled-back) data

Senior interview: "How does PostgreSQL achieve REPEATABLE READ without locking everything?" → MVCC.

---

## Core Concepts

### SQL Standard Isolation Levels

| Level | Dirty Read | Non-Repeatable Read | Phantom Read |
|---|---|---|---|
| READ UNCOMMITTED | Possible | Possible | Possible |
| READ COMMITTED | No | Possible | Possible |
| REPEATABLE READ | No | No | Possible (per standard) |
| SERIALIZABLE | No | No | No |

**Note:** PostgreSQL defaults to READ COMMITTED. Its REPEATABLE READ also prevents phantoms (snapshot isolation).

### Anomaly Definitions

**Dirty Read:** Read uncommitted data from another txn (which may roll back).

```
T1: UPDATE balance = 100 (not committed)
T2: SELECT balance → reads 100
T1: ROLLBACK
T2: now sees ghost data
```

**Non-Repeatable Read:** Same SELECT in same txn returns different values.

```
T1: SELECT price → 100
T2: UPDATE price = 200, COMMIT
T1: SELECT price → 200 (changed within same txn)
```

**Phantom Read:** Same query returns different ROW SETS.

```
T1: SELECT COUNT(*) WHERE status='paid' → 5
T2: INSERT (status='paid'), COMMIT
T1: SELECT COUNT(*) WHERE status='paid' → 6
```

**Lost Update:** Two txns both read + update; one's update lost.

```
T1: SELECT balance → 100
T2: SELECT balance → 100
T1: UPDATE balance = 100 + 50, COMMIT → 150
T2: UPDATE balance = 100 + 30, COMMIT → 130 (T1's update lost!)
```

**Write Skew:** Two txns read overlapping data, write to different rows, both pass their own constraints but together violate.

```
Constraint: at least 1 doctor on-call
T1: SELECT count of on-call doctors → 2; UPDATE doctor=A on_call=false; COMMIT
T2: SELECT count → 2; UPDATE doctor=B on_call=false; COMMIT
Result: 0 on-call doctors — constraint broken
```

### PostgreSQL Implementation (MVCC)

PostgreSQL uses Multi-Version Concurrency Control:
- Each row has `xmin` (created by txn ID), `xmax` (deleted/updated by txn ID)
- Each txn has a snapshot (set of visible txn IDs)
- Reads see version visible per snapshot — no locks needed for reading
- Writes create new row version

```
READ COMMITTED:
  Snapshot taken per query
  Reads always see latest committed data


REPEATABLE READ (= snapshot isolation in PG):
  Snapshot taken at transaction start
  Same data throughout transaction


SERIALIZABLE (SSI in PG):
  Snapshot + tracks read/write dependencies
  Detects + aborts conflicts (serialization failures)
```

### Setting Isolation Level

```sql
BEGIN ISOLATION LEVEL REPEATABLE READ;
-- or
BEGIN;
SET TRANSACTION ISOLATION LEVEL SERIALIZABLE;
```

Python (psycopg):

```python
import psycopg
from psycopg.rows import dict_row


with psycopg.connect("...", row_factory=dict_row) as conn:
    conn.isolation_level = psycopg.IsolationLevel.SERIALIZABLE
    with conn.transaction():
        # work
        pass
```

Django:

```python
from django.db import transaction


@transaction.atomic
def transfer():
    cursor = connection.cursor()
    cursor.execute("SET TRANSACTION ISOLATION LEVEL SERIALIZABLE")
    # ... work
```

Or via DATABASES setting:

```python
DATABASES = {
    'default': {
        # ...
        'OPTIONS': {
            'isolation_level': psycopg.IsolationLevel.REPEATABLE_READ,
        },
    },
}
```

### SQLAlchemy Isolation Level

```python
# Per engine
engine = create_engine(URL, isolation_level="REPEATABLE READ")

# Per connection
with engine.connect().execution_options(isolation_level="SERIALIZABLE") as conn:
    ...

# Per session (begin)
with Session(engine) as session:
    session.connection().execution_options(isolation_level="SERIALIZABLE")
```

### Serialization Failures + Retry

SERIALIZABLE may abort transactions:

```python
from psycopg.errors import SerializationFailure


def serializable_with_retry(func, max_retries=3):
    for attempt in range(max_retries):
        try:
            return func()
        except SerializationFailure:
            if attempt < max_retries - 1:
                time.sleep(0.05 * 2 ** attempt)
                continue
            raise
```

### MySQL InnoDB Specifics

```sql
-- MySQL default: REPEATABLE READ (different from Postgres!)
-- Uses MVCC + next-key locks (row + gap)

SET GLOBAL transaction_isolation = 'READ-COMMITTED';
SET SESSION transaction_isolation = 'READ-COMMITTED';
```

InnoDB REPEATABLE READ prevents phantom reads via gap locks (different from spec).

---

## How It Works Internally

### Snapshot Isolation in PostgreSQL

```
Transaction T1 starts at time t1
  → Snapshot S1 = set of committed txns at t1

T1 reads row R:
  → Find version of R where xmin ∈ S1 and (xmax ∉ S1 or xmax = NULL)

If T2 updates R after t1:
  → T2 creates new version with xmin = T2
  → T1 still sees old version (not in T1's snapshot)
```

### Serializable Snapshot Isolation (SSI)

PG uses SSI for SERIALIZABLE. Tracks read-write conflicts between txns. If detected, aborts one with `40001` (`serialization_failure`).

Cost: bookkeeping overhead. Use only when needed.

### Lock Modes (in addition to MVCC)

```
SELECT FOR UPDATE → exclusive row lock
SELECT FOR SHARE → shared row lock
UPDATE/DELETE → exclusive row lock acquired automatically
INSERT → exclusive lock on new row + index entry locks (gap locks in MySQL)
```

---

## Common Pitfalls

### 1. Read-Modify-Write Race

```python
# Pseudo-code
@transaction.atomic
def add_to_balance(account_id, amount):
    acc = Account.objects.get(pk=account_id)        # READ
    acc.balance += amount                            # MODIFY
    acc.save()                                       # WRITE
```

Two concurrent calls = lost update at READ COMMITTED. Fix:
- Use SELECT FOR UPDATE
- Or atomic UPDATE: `UPDATE ... SET balance = balance + 50 WHERE id = X`
- Or REPEATABLE READ + retry on conflict

### 2. Snapshot Isolation Doesn't Prevent Write Skew

Write skew passes REPEATABLE READ:

```
T1, T2 both SELECT (count on-call doctors) → both see count >= 2
T1 sets doctor A off-call, T2 sets doctor B off-call
Both commit → 0 doctors on call
```

Fix: SERIALIZABLE, or explicit SELECT FOR UPDATE on relevant rows.

### 3. Long-Running Snapshot

REPEATABLE READ txn that runs 1 hour blocks autovacuum from cleaning dead tuples → bloat. Avoid long-running txns; or set `idle_in_transaction_session_timeout`.

### 4. Mixed Isolation Levels

Different connections use different levels — confusing bugs. Centralize via settings or `connection.execution_options`.

### 5. SQL Standard != Implementation

Postgres REPEATABLE READ ≠ MySQL REPEATABLE READ ≠ standard. Read your DB's docs.

### 6. Retry Logic Missing for SERIALIZABLE

App-level retries required on `40001` (`could not serialize access due to ...`). Without retries, users see errors.

---

## Interview Q&A

**Q1:** READ COMMITTED vs REPEATABLE READ?
**A:** READ COMMITTED: each SELECT sees fresh snapshot of committed data (default in PG). REPEATABLE READ: txn-start snapshot, all reads consistent within txn (snapshot isolation in PG). Prevents non-repeatable reads. Doesn't prevent write skew (need SERIALIZABLE).

**Q2:** PostgreSQL MVCC kaise kaam karta hai?
**A:** Each row has xmin, xmax, ctid. Updates create new row version (don't modify in place). Snapshots = set of visible txn IDs. Reads filter rows by snapshot. No reader locks. Tradeoff: bloat from old versions → vacuum required.

**Q3:** Write skew kya hai aur kaise prevent karoge?
**A:** Two concurrent txns read overlapping data, write disjoint rows, individually consistent but jointly violate constraint. SERIALIZABLE prevents via SSI (tracks read-write conflicts). Or use SELECT FOR UPDATE on relevant rows (forces serialization manually).

**Q4:** SERIALIZABLE ki cost?
**A:** PG uses SSI — minimal overhead during normal operation, but aborts conflicting txns (returns `serialization_failure`). App must retry. Performance acceptable in low contention; degrades sharply with high contention. Use only when needed (financial txns, sensitive constraints).

**Q5:** MySQL vs PostgreSQL isolation defaults?
**A:** PostgreSQL: READ COMMITTED (default). MySQL: REPEATABLE READ (default). MySQL InnoDB REPEATABLE READ uses gap locks → prevents phantoms (stronger than SQL standard). Different "REPEATABLE READ" semantics — easy bug source.

**Q6:** Lost update kab hota hai?
**A:** Read-modify-write at READ COMMITTED without locking. Both txns read old value, modify, write new — second overwrite the first's update. Fix: (1) SELECT FOR UPDATE. (2) Atomic UPDATE (`balance = balance + X`). (3) REPEATABLE READ + retry on conflict. (4) Optimistic with version column.

**Q7:** Snapshot kab take hota hai REPEATABLE READ mein?
**A:** PostgreSQL: at first SELECT or DML statement in the txn (not at BEGIN). Subsequent reads see same snapshot. New writes can occur but other txns' new commits invisible to this txn until commit/rollback.

**Q8:** Dirty read kaise possible hai?
**A:** Only at READ UNCOMMITTED isolation level. PostgreSQL doesn't even implement READ UNCOMMITTED (treats as READ COMMITTED). MySQL InnoDB allows but rarely used. Modern apps avoid READ UNCOMMITTED — risk far outweighs minimal perf gain.

---

## Real-World Use Cases

### 1. Banking Transfer (SERIALIZABLE + retry)

```python
def transfer(from_id, to_id, amount):
    for attempt in range(5):
        try:
            with connection.cursor() as c:
                c.execute("SET TRANSACTION ISOLATION LEVEL SERIALIZABLE")
            with transaction.atomic():
                from_acc = Account.objects.get(pk=from_id)
                to_acc = Account.objects.get(pk=to_id)
                if from_acc.balance < amount:
                    raise InsufficientFunds()
                from_acc.balance -= amount
                to_acc.balance += amount
                from_acc.save()
                to_acc.save()
            return
        except OperationalError as e:
            if 'could not serialize' in str(e):
                time.sleep(0.05 * 2 ** attempt)
                continue
            raise
    raise Exception("Max retries")
```

### 2. Atomic Counter (no isolation tricks needed)

```python
# Single statement is atomic — no isolation issue
Product.objects.filter(pk=5).update(stock=F('stock') - 1)
```

### 3. Reports — REPEATABLE READ

```python
# Multi-query report needs consistent view
with connection.cursor() as c:
    c.execute("BEGIN ISOLATION LEVEL REPEATABLE READ")
    # All queries see same snapshot — totals match
    total = Order.objects.filter(...).aggregate(Sum('amount'))
    count = Order.objects.filter(...).count()
    # total / count = correct
```

---

## References

- [PostgreSQL Transaction Isolation](https://www.postgresql.org/docs/current/transaction-iso.html)
- [MySQL InnoDB Transactions](https://dev.mysql.com/doc/refman/8.0/en/innodb-consistent-read.html)
- "Designing Data-Intensive Applications" Ch. 7
- [Adya thesis on isolation](https://www.microsoft.com/en-us/research/publication/weak-consistency-a-generalized-theory-and-optimistic-implementations-for-distributed-transactions/)
