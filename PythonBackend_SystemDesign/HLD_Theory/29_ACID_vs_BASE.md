# ACID vs BASE — Database Consistency Models

## WHAT

**ACID** and **BASE** are two opposite philosophies for how a database handles transactions and consistency.

| Property | ACID | BASE |
|---|---|---|
| Full form | Atomicity, Consistency, Isolation, Durability | Basically Available, Soft-state, Eventually consistent |
| Used in | RDBMS (PostgreSQL, MySQL) | NoSQL (Cassandra, DynamoDB, MongoDB) |
| Focus | Correctness | Availability + Performance |

---

## ACID — Deep Dive

### A — Atomicity
All operations in a transaction succeed **or all fail**. No partial updates.

```sql
-- Transfer ₹500: both ops succeed or both fail
BEGIN;
  UPDATE accounts SET balance = balance - 500 WHERE id = 1;
  UPDATE accounts SET balance = balance + 500 WHERE id = 2;
COMMIT;
-- If second UPDATE fails → entire transaction rolls back
```

### C — Consistency
Database always moves from one **valid state** to another. All constraints are satisfied.

```sql
-- Constraint: balance >= 0
-- Transfer ₹500 when balance = ₹200 → REJECTED
-- DB stays in valid state
```

### I — Isolation
Concurrent transactions behave as if they run **serially**. No dirty reads.

**Isolation Levels (weakest → strongest):**
```
READ UNCOMMITTED  → can read uncommitted data (dirty read)
READ COMMITTED    → reads only committed data (PostgreSQL default)
REPEATABLE READ   → same query returns same result within txn
SERIALIZABLE      → strictest, transactions fully isolated
```

### D — Durability
Once committed, data **survives crashes**. Written to disk (WAL — Write-Ahead Log).

---

## BASE — Deep Dive

### BA — Basically Available
System **always responds**, even if some nodes are down or data is stale.
(vs ACID which might block waiting for consistency)

### S — Soft State
State may **change over time** even without new input (as replicas sync).

### E — Eventually Consistent
All replicas will **converge** to the same state — but not immediately.

```
User writes: name = "Alice" → goes to replica-1
             replica-2 still has name = "Bob"  (stale for ~100ms)
             replica-2 syncs → name = "Alice"  (eventually consistent)
```

---

## REAL LIFE ANALOGY

**ACID** = Bank transaction  
You transfer ₹500 to a friend. Either the money leaves your account AND enters theirs — or neither happens. No middle ground.

**BASE** = WhatsApp message  
You send a message. It shows ✓ on your phone (basically available). Your friend might see it 2 seconds later (eventually consistent). The system doesn't wait for perfect sync before responding.

---

## WHEN TO USE WHAT

| Scenario | Model | Why |
|---|---|---|
| Banking / payments | ACID | Money cannot be duplicated or lost |
| Order inventory | ACID | Stock count must be exact |
| User sessions / cache | BASE | Slight staleness is acceptable |
| Social media likes/views | BASE | ±100 views doesn't matter |
| Product catalog reads | BASE | Read speed > perfect accuracy |
| Shopping cart | BASE | Eventual sync is fine |

---

## Python Backend Example

```python
# ACID — SQLAlchemy transaction
from sqlalchemy.orm import Session

def transfer_money(session: Session, from_id: int, to_id: int, amount: float):
    try:
        sender   = session.query(Account).filter_by(id=from_id).with_for_update().one()
        receiver = session.query(Account).filter_by(id=to_id).with_for_update().one()
        
        if sender.balance < amount:
            raise ValueError("Insufficient funds")
        
        sender.balance   -= amount
        receiver.balance += amount
        session.commit()        # atomic: both changes or none
    except Exception:
        session.rollback()      # durability: nothing changes
        raise

# BASE — Redis eventually consistent counter
import redis
r = redis.Redis()

def increment_view_count(post_id: str):
    # Fast, available — but may lag behind real count by seconds
    r.incr(f"views:{post_id}")

def get_view_count(post_id: str) -> int:
    return int(r.get(f"views:{post_id}") or 0)
```

---

## CAP Connection

| Theorem | ACID | BASE |
|---|---|---|
| CAP choice | CP (Consistency + Partition tolerance) | AP (Availability + Partition tolerance) |
| On network partition | Wait for consistency | Return stale data |

---

## Interview Q&A

**Q: Can a NoSQL database be ACID?**
A: Yes. MongoDB 4.0+ supports multi-document ACID transactions. CockroachDB (distributed SQL) is ACID + horizontally scalable.

**Q: What is a dirty read?**
A: Reading data that another transaction has modified but NOT yet committed. If that transaction rolls back, you read invalid data. Prevented by READ COMMITTED isolation level.

**Q: What does "eventually consistent" mean in practice?**
A: Replicas will agree on the same value within milliseconds to seconds after the last write. No guarantee on exact time — but they WILL converge.

**Q: How does DynamoDB achieve eventual consistency?**
A: Uses vector clocks and last-write-wins (LWW). Reads can request strongly consistent (1 read unit) or eventually consistent (0.5 read unit = cheaper).
