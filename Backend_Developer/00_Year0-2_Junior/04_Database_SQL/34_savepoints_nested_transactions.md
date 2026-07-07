# Savepoints & Nested Transactions

## Why It Matters

You already know `BEGIN`/`COMMIT`/`ROLLBACK` — savepoints are the detail
that comes up the moment one step in a multi-step transaction can fail
without wanting to throw away everything before it. It's a small topic but a
real gap: "can you partially roll back a transaction?" is a fair follow-up
after any transactions/locking discussion.

Senior interview: "You're processing a batch of 100 orders in one
transaction. Order #47 fails validation — do you roll back all 100?" →
savepoint before each order, `ROLLBACK TO SAVEPOINT` on failure, continue
the rest, single final `COMMIT`.

---

## Core Concept

```sql
BEGIN;

INSERT INTO orders (id, total) VALUES (1, 100);

SAVEPOINT before_order_2;
INSERT INTO orders (id, total) VALUES (2, -50);   -- fails a CHECK constraint

ROLLBACK TO SAVEPOINT before_order_2;   -- undoes ONLY order 2's insert
                                          -- order 1's insert is still staged

INSERT INTO orders (id, total) VALUES (3, 200);

COMMIT;   -- orders 1 and 3 are saved; order 2 never happened
```

Without the savepoint, a failed statement (constraint violation) would abort
the **entire transaction** — Postgres refuses further commands until you
`ROLLBACK` everything.

---

## Django / SQLAlchemy equivalents (the part you'll actually use)

```python
# Django — atomic() blocks nest as savepoints automatically
from django.db import transaction

with transaction.atomic():
    order1.save()
    try:
        with transaction.atomic():   # inner atomic() = savepoint
            order2.save()  # raises IntegrityError
    except IntegrityError:
        pass  # inner block rolled back to its savepoint; outer continues
    order3.save()
# order1 and order3 committed; order2 never happened
```

```python
# SQLAlchemy — explicit nested transaction (savepoint)
with session.begin():
    session.add(order1)
    try:
        with session.begin_nested():   # SAVEPOINT
            session.add(order2)
            session.flush()  # triggers the constraint check
    except IntegrityError:
        pass  # rolled back to the SAVEPOINT only
    session.add(order3)
```

This is exactly the pattern for **batch processing with partial failure
tolerance** — process what you can, skip what fails, without an all-or-nothing
transaction wrapping the whole batch.

---

## What "nested transactions" really means in Postgres

```
Postgres has NO true nested transactions — BEGIN inside BEGIN is a no-op
warning, not a real nested transaction. What Django/SQLAlchemy call
"nested transactions" are actually SAVEPOINTs under the hood — same
mechanism, friendlier API.
```

```sql
-- What Django's inner atomic() actually generates:
SAVEPOINT s1;
-- ... your inner block's statements ...
RELEASE SAVEPOINT s1;      -- success path (like an inner COMMIT)
-- or
ROLLBACK TO SAVEPOINT s1;  -- failure path (like an inner ROLLBACK)
```

---

## Interview Q&A

**Q: Can you roll back part of a transaction without losing everything?**
A: Yes — `SAVEPOINT name`, then `ROLLBACK TO SAVEPOINT name` undoes only the
work since that savepoint; the transaction is still open and can continue.

**Q: How does Django's `atomic()` relate to savepoints?**
A: The outermost `atomic()` opens a real transaction (`BEGIN`); any
`atomic()` nested inside an already-open transaction becomes a `SAVEPOINT`
instead — this is why nested `atomic()` blocks let you catch and recover
from a failure in just the inner block.

**Q: Performance cost of savepoints?**
A: Cheap for a handful, but each savepoint holds resources — creating
thousands of savepoints in a tight loop (e.g., one per row in a 10k-row
batch) adds meaningful overhead. For large batches, prefer batching failures
into a validation pass before the transaction, or chunk into smaller
transactions instead of one-savepoint-per-row.

---

Related: [19_optimistic_pessimistic_locking.md](19_optimistic_pessimistic_locking.md),
[21_isolation_levels_anomalies.md](21_isolation_levels_anomalies.md).
