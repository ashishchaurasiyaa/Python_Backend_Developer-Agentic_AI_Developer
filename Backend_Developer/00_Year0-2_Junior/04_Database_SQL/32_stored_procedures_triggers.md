# Stored Procedures & Triggers

## Why It Matters

Less central for a Python backend dev than for a DBA role — most business
logic today lives in the application layer (Django/FastAPI), not the
database. But it still comes up as a conceptual tradeoff question ("why not
just put this logic in a trigger?"), and triggers specifically underpin CDC
pipelines you likely already know about (Debezium). Enough depth to discuss
the tradeoffs confidently is the goal here, not deep DBA-level mastery.

Senior interview: "You need to auto-update an `updated_at` column on every
row change, and audit every delete. Trigger or application code?" → trigger
for both (guarantees it happens regardless of which app/service writes), but
know the cost.

---

## Core Concepts

### Stored Procedure — logic that lives in the database

```sql
-- PostgreSQL: PL/pgSQL stored procedure
CREATE OR REPLACE PROCEDURE transfer_funds(
    sender_id INT, receiver_id INT, amount NUMERIC
)
LANGUAGE plpgsql
AS $$
BEGIN
    UPDATE accounts SET balance = balance - amount WHERE id = sender_id;
    UPDATE accounts SET balance = balance + amount WHERE id = receiver_id;

    IF (SELECT balance FROM accounts WHERE id = sender_id) < 0 THEN
        RAISE EXCEPTION 'Insufficient funds';
    END IF;
END;
$$;

-- Call it
CALL transfer_funds(1, 2, 500);
```

Difference from a **function**: a function returns a value and can be used in
a `SELECT`; a procedure performs an action (can run transactions, doesn't have
to return anything).

```sql
-- Function version (returns a value, usable in SELECT)
CREATE OR REPLACE FUNCTION get_account_balance(acc_id INT)
RETURNS NUMERIC AS $$
    SELECT balance FROM accounts WHERE id = acc_id;
$$ LANGUAGE sql;

SELECT get_account_balance(1);
```

### Why teams AVOID heavy stored-procedure logic (the actual interview point)

| Downside | Why it matters |
|---|---|
| **Version control** | SQL logic living in the DB is harder to code-review, diff, and roll back than application code in Git |
| **Testing** | Harder to unit-test than Python functions; needs a real DB connection |
| **Portability** | PL/pgSQL/T-SQL are vendor-specific — locks you into one database engine |
| **Team skill split** | Most backend teams are stronger in Python/application code than in DB-side procedural SQL |
| **Scaling reads** | Logic in the DB runs ON the DB server — can't scale it independently like you would stateless app servers |

**When they're still the right call:** extremely performance-critical bulk
operations where round-tripping rows to the app and back is the bottleneck
(e.g., end-of-day batch financial reconciliation touching millions of rows).

---

### Triggers — automatic logic fired on data changes

```sql
-- Auto-update `updated_at` on every row change
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_set_updated_at
BEFORE UPDATE ON orders
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();
```

```sql
-- Audit log trigger — capture every delete before it happens
CREATE OR REPLACE FUNCTION log_deleted_order()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO orders_audit_log (order_id, deleted_at, deleted_data)
    VALUES (OLD.id, NOW(), row_to_json(OLD));
    RETURN OLD;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_audit_delete
BEFORE DELETE ON orders
FOR EACH ROW
EXECUTE FUNCTION log_deleted_order();
```

### Trigger types

| Type | Fires |
|---|---|
| `BEFORE INSERT/UPDATE/DELETE` | Before the change — can modify `NEW`, or cancel the operation |
| `AFTER INSERT/UPDATE/DELETE` | After the change — for logging/side-effects, can't modify the row anymore |
| `INSTEAD OF` | On views — lets you make an otherwise-non-updatable view updatable |
| `FOR EACH ROW` vs `FOR EACH STATEMENT` | Per-row (most common) vs once per SQL statement regardless of row count |

### How this connects to CDC (this repo's existing coverage)

```
Application writes to DB
        ↓
Postgres logical replication / WAL (not a manual trigger)
        ↓
Debezium reads the WAL → publishes change events to Kafka
        ↓
Downstream consumers react (search index update, cache invalidation, etc.)
```

Modern CDC (see [25_cdc_debezium_postgresql.md](25_cdc_debezium_postgresql.md))
has mostly replaced **manual** "trigger writes to an outbox table" patterns —
but the outbox-table-via-trigger approach is still valid where you don't want
a full CDC pipeline (Debezium/Kafka) running, just a lightweight guarantee.

---

## Interview Q&A

**Q: Application-layer logic vs database trigger — how do you decide?**
A: Trigger when the invariant must hold **no matter which system writes to
the table** (multiple services, ad-hoc admin scripts, migrations all touching
the same table) — e.g., `updated_at`, audit logging. Application layer for
anything with business logic that changes often, needs testing, or needs
version control alongside the rest of the codebase.

**Q: What's a risk with triggers specifically?**
A: Hidden behavior — a developer runs a normal-looking `UPDATE` and doesn't
realize a trigger cascaded into 3 other tables. Debugging becomes harder
because the logic isn't visible at the call site. Document triggers clearly.

**Q: Stored procedure vs ORM method — which wins for a bulk update of 1M rows?**
A: Stored procedure / raw SQL usually wins — avoids pulling 1M rows into
Python memory and round-tripping them back. This is the one scenario where
DB-side logic is the pragmatic choice even in an ORM-first codebase.

---

Related: [25_cdc_debezium_postgresql.md](25_cdc_debezium_postgresql.md) (WAL-based
CDC as the modern alternative to manual outbox triggers),
[31_normalization_denormalization.md](31_normalization_denormalization.md).
