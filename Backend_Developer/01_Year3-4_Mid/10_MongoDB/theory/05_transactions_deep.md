# MongoDB Transactions — Multi-Document ACID

## Why It Matters

Before 4.0, MongoDB had only single-document atomicity. 4.0+ added multi-document ACID transactions:
- **Financial operations** → debit + credit atomic
- **Inventory + order** → both update or neither
- **Multi-collection ops** → consistent across collections

But: transactions have overhead. Use only when single-doc atomicity won't work.

Senior interview: "Bank transfer — MongoDB ke saath kaise atomic?" → `with_transaction()` + write concern majority.

---

## Core Concepts

### Requirements

- MongoDB 4.0+ for single-doc transactions
- 4.0+ replica set required (no standalone)
- 4.2+ multi-document, multi-shard
- 5.0+ stable performance improvements

### Basic Transaction (Python)

```python
from pymongo import MongoClient


client = MongoClient("mongodb://localhost:27017/?replicaSet=rs0")


def transfer(from_id, to_id, amount):
    with client.start_session() as session:
        with session.start_transaction():
            db = client.bank

            from_acc = db.accounts.find_one(
                {'_id': from_id},
                session=session,
            )
            if from_acc['balance'] < amount:
                raise InsufficientFunds()

            db.accounts.update_one(
                {'_id': from_id},
                {'$inc': {'balance': -amount}},
                session=session,
            )
            db.accounts.update_one(
                {'_id': to_id},
                {'$inc': {'balance': amount}},
                session=session,
            )
            # Auto-commits on context exit; rollback on exception
```

### `with_transaction()` (Recommended — auto-retry)

```python
def callback(session):
    db = client.bank
    db.accounts.update_one(
        {'_id': from_id},
        {'$inc': {'balance': -amount}},
        session=session,
    )
    db.accounts.update_one(
        {'_id': to_id},
        {'$inc': {'balance': amount}},
        session=session,
    )


with client.start_session() as session:
    session.with_transaction(callback)
    # Auto-retries on TransientTransactionError
```

### Async (motor)

```python
from motor.motor_asyncio import AsyncIOMotorClient


client = AsyncIOMotorClient("mongodb://...")


async def transfer_async(from_id, to_id, amount):
    async with await client.start_session() as session:
        async with session.start_transaction():
            db = client.bank
            await db.accounts.update_one(
                {'_id': from_id},
                {'$inc': {'balance': -amount}},
                session=session,
            )
            await db.accounts.update_one(
                {'_id': to_id},
                {'$inc': {'balance': amount}},
                session=session,
            )
```

### Write Concerns

```python
from pymongo import WriteConcern, ReadConcern, ReadPreference


with session.start_transaction(
    read_concern=ReadConcern('snapshot'),
    write_concern=WriteConcern('majority', wtimeout=10000),
    read_preference=ReadPreference.PRIMARY,
):
    # ...
```

**Levels:**
- `WriteConcern(w=1)` — primary only (fast, less safe)
- `WriteConcern('majority')` — majority of replicas ack (recommended)
- `WriteConcern('all')` — all replicas

### Transaction Limits

- **Max duration:** 60 seconds default (`transactionLifetimeLimitSeconds`)
- **Max oplog size:** 16 MB total (writes + reads in txn)
- **No DDL ops** inside (no createCollection, createIndex)

Tune via:

```javascript
db.adminCommand({setParameter: 1, transactionLifetimeLimitSeconds: 120})
```

### Read Concerns

```python
ReadConcern('local')        # default — may read uncommitted from replicas
ReadConcern('majority')     # only majority-committed data
ReadConcern('snapshot')     # txn-start snapshot (REPEATABLE READ)
ReadConcern('linearizable') # strongest, most expensive
```

### Single-Document Atomicity (Default — Use When Possible)

```python
# These are AUTOMATIC atomic — no transaction needed:
db.accounts.update_one(
    {'_id': X, 'balance': {'$gte': amount}},
    {'$inc': {'balance': -amount}},
)
# Atomic check + update in one op
```

Transactions are slower. Single-doc atomic ops are preferred when possible.

### Retry on TransientTransactionError

```python
def safe_transaction(callback):
    while True:
        try:
            with client.start_session() as s:
                s.with_transaction(callback)
            return
        except pymongo.errors.OperationFailure as e:
            if e.has_error_label('TransientTransactionError'):
                continue  # retry
            raise
```

`with_transaction()` does this automatically.

---

## How It Works Internally

### Snapshot Isolation

Transaction reads at the snapshot of all-committed timestamp. Writes don't see other concurrent uncommitted writes. Like PostgreSQL REPEATABLE READ.

### Two-Phase Commit (Sharded)

For multi-shard txn (4.2+):
1. Coordinator selects one shard as transaction coordinator
2. All shards prepare (write but don't commit)
3. Coordinator votes commit
4. All shards commit
5. Confirms back to client

### Oplog Replication

Transaction operations grouped into single oplog entry (atomic for replication). Replicas apply atomically.

---

## Common Pitfalls

### 1. Transactions When Single-Doc Would Work

```python
# OVERKILL — single doc atomic update is atomic
with session.start_transaction():
    db.users.update_one(
        {'_id': user_id},
        {'$set': {'name': 'X'}},
        session=session,
    )
```

Use transactions only for multi-doc/multi-collection consistency.

### 2. Long Transactions

```python
with session.start_transaction():
    cursor = db.large_collection.find({}, session=session)
    for doc in cursor:  # iterates 10 minutes
        # transaction times out after 60s
```

Keep transactions short (< 60s default limit).

### 3. Forgetting `session=session`

```python
with session.start_transaction():
    db.col.update_one({}, {}, session=session)
    db.other.update_one({}, {})   # NOT in transaction!
```

Pass session to every operation.

### 4. Schema Migrations Inside Transaction

```python
with session.start_transaction():
    db.create_collection('x', session=session)  # ERROR
```

DDL not allowed.

### 5. Standalone Server (No RS)

```
TransientTransactionError: Standalone is not supported
```

Even single-node needs to be replica set: `--replSet rs0`.

### 6. Write Concern Mismatch

```python
# Transaction with majority but collection default is w=1
# → may report success but lost on failover
```

Always specify `WriteConcern('majority')` for txn writes.

---

## Interview Q&A

**Q1:** MongoDB transactions kab use karte ho?
**A:** Multi-document or multi-collection consistency required. Examples: bank transfer (debit + credit different docs), order + inventory (order doc + product doc both update). Don't use for single-doc updates (already atomic). Has overhead — only when needed.

**Q2:** Transaction limit 60s kyun hai?
**A:** Avoid long-held locks blocking other transactions. Configurable via `transactionLifetimeLimitSeconds`. If you need longer ops, redesign — batch into smaller transactions, or use single-doc atomic ops.

**Q3:** Write concern majority ka matlab?
**A:** Operation considered done only when majority of replica set members acknowledge. Prevents data loss on failover — promoted replica already has the write. Slower than w=1 but safer. Required for true durability.

**Q4:** Snapshot isolation vs PostgreSQL REPEATABLE READ?
**A:** Similar — txn sees consistent snapshot from start. Writes by other txns invisible. MongoDB uses `ReadConcern('snapshot')`. Doesn't prevent write skew — needs explicit conflict detection (or app-level locking).

**Q5:** TransientTransactionError kya hai?
**A:** Conflict or temporary issue → MongoDB suggests retry. `with_transaction()` auto-retries. Manual: check `e.has_error_label('TransientTransactionError')`. Causes: write conflicts, primary stepdown during txn, network blip.

**Q6:** Multi-shard transaction overhead?
**A:** Two-phase commit across shards = more network round-trips, longer duration. 5-10x slower than single-shard. Design schema to keep related data on same shard (shard key choice critical) to minimize cross-shard txns.

**Q7:** Read-after-write consistency in transaction?
**A:** Within same transaction: yes, reads see own writes. Across transactions: depends on read concern. `majority` waits for write to be majority-committed before others see. `local` may not.

**Q8:** Alternative to transactions for atomicity?
**A:** (1) Single-doc updates with `$inc`, `$set` — already atomic. (2) Optimistic concurrency: version field + retry. (3) Saga pattern: compensating transactions across services. (4) Document model: embed related data into one document (avoids multi-doc need).

---

## Real-World Use Cases

### 1. Bank Transfer

```python
def transfer(from_id, to_id, amount):
    def callback(session):
        db = client.bank

        # Atomic check + debit
        result = db.accounts.update_one(
            {'_id': from_id, 'balance': {'$gte': amount}},
            {'$inc': {'balance': -amount}},
            session=session,
        )
        if result.matched_count == 0:
            raise InsufficientFunds()

        db.accounts.update_one(
            {'_id': to_id},
            {'$inc': {'balance': amount}},
            session=session,
        )

        db.transactions.insert_one(
            {
                'from_id': from_id,
                'to_id': to_id,
                'amount': amount,
                'created_at': datetime.utcnow(),
            },
            session=session,
        )

    with client.start_session() as s:
        s.with_transaction(callback)
```

### 2. Inventory Reservation

```python
def reserve_items(cart_id, items):
    def callback(session):
        for item in items:
            result = db.products.update_one(
                {'_id': item['id'], 'stock': {'$gte': item['qty']}},
                {'$inc': {'stock': -item['qty']}},
                session=session,
            )
            if result.matched_count == 0:
                raise OutOfStock(item['id'])

        db.reservations.insert_one(
            {'cart_id': cart_id, 'items': items},
            session=session,
        )

    with client.start_session() as s:
        s.with_transaction(callback)
```

### 3. Avoid Transactions via Embedding

```python
# Instead of separate user + addresses + orders collections...
# Embed in single doc — atomic by default
{
    '_id': 'user_1',
    'name': 'Alice',
    'addresses': [{...}, {...}],
    'orders': [{...}, {...}],
}
db.users.update_one(
    {'_id': 'user_1'},
    {'$push': {'orders': new_order}, '$set': {'updated_at': now}},
)
# Single-doc — atomic
```

---

## References

- [MongoDB Transactions](https://www.mongodb.com/docs/manual/core/transactions/)
- [pymongo Transactions](https://pymongo.readthedocs.io/en/stable/api/pymongo/client_session.html)
- [Write Concerns](https://www.mongodb.com/docs/manual/reference/write-concern/)
- "MongoDB: The Definitive Guide" — Transactions chapter
