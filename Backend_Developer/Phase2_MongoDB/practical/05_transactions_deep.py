"""
MongoDB Transactions — Production Patterns
"""

import asyncio
from datetime import datetime

import pymongo
from pymongo import MongoClient, WriteConcern, ReadConcern
from pymongo.errors import OperationFailure
from motor.motor_asyncio import AsyncIOMotorClient


# Replica set required for transactions
client = MongoClient("mongodb://localhost:27017/?replicaSet=rs0")
db = client.bank


# ==========================================================================
# 1. SIMPLE TRANSACTION (manual)
# ==========================================================================

def transfer_manual(from_id, to_id, amount):
    with client.start_session() as session:
        with session.start_transaction(
            read_concern=ReadConcern('snapshot'),
            write_concern=WriteConcern('majority', wtimeout=10000),
        ):
            from_acc = db.accounts.find_one(
                {'_id': from_id},
                session=session,
            )
            if from_acc['balance'] < amount:
                raise ValueError("Insufficient funds")

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
            # Auto-commits on context exit


# ==========================================================================
# 2. with_transaction() — auto-retry (RECOMMENDED)
# ==========================================================================

def transfer_auto_retry(from_id, to_id, amount):
    def callback(session):
        # Atomic check + debit (single op)
        result = db.accounts.update_one(
            {'_id': from_id, 'balance': {'$gte': amount}},
            {'$inc': {'balance': -amount}},
            session=session,
        )
        if result.matched_count == 0:
            raise ValueError("Insufficient funds or account not found")

        # Credit recipient
        db.accounts.update_one(
            {'_id': to_id},
            {'$inc': {'balance': amount}},
            session=session,
        )

        # Audit log
        db.transactions.insert_one(
            {
                'from_id': from_id,
                'to_id': to_id,
                'amount': amount,
                'created_at': datetime.utcnow(),
            },
            session=session,
        )

    with client.start_session() as session:
        session.with_transaction(
            callback,
            read_concern=ReadConcern('snapshot'),
            write_concern=WriteConcern('majority'),
        )


# ==========================================================================
# 3. ASYNC TRANSACTION (motor)
# ==========================================================================

async_client = AsyncIOMotorClient("mongodb://localhost:27017/?replicaSet=rs0")
async_db = async_client.bank


async def transfer_async(from_id, to_id, amount):
    async def callback(session):
        result = await async_db.accounts.update_one(
            {'_id': from_id, 'balance': {'$gte': amount}},
            {'$inc': {'balance': -amount}},
            session=session,
        )
        if result.matched_count == 0:
            raise ValueError("Insufficient funds")

        await async_db.accounts.update_one(
            {'_id': to_id},
            {'$inc': {'balance': amount}},
            session=session,
        )

        await async_db.transactions.insert_one(
            {
                'from_id': from_id,
                'to_id': to_id,
                'amount': amount,
                'created_at': datetime.utcnow(),
            },
            session=session,
        )

    async with await async_client.start_session() as session:
        await session.with_transaction(
            callback,
            read_concern=ReadConcern('snapshot'),
            write_concern=WriteConcern('majority'),
        )


# ==========================================================================
# 4. INVENTORY RESERVATION
# ==========================================================================

def reserve_items(cart_id: str, items: list[dict]):
    """items = [{'product_id': X, 'qty': N}, ...]"""

    def callback(session):
        # Reserve each item
        for item in items:
            result = db.products.update_one(
                {'_id': item['product_id'], 'stock': {'$gte': item['qty']}},
                {
                    '$inc': {'stock': -item['qty']},
                    '$push': {'reservations': {
                        'cart_id': cart_id,
                        'qty': item['qty'],
                        'at': datetime.utcnow(),
                    }},
                },
                session=session,
            )
            if result.matched_count == 0:
                # Triggers rollback
                raise ValueError(f"Out of stock: {item['product_id']}")

        # Record reservation
        db.cart_reservations.insert_one(
            {
                'cart_id': cart_id,
                'items': items,
                'status': 'reserved',
                'expires_at': datetime.utcnow().replace(microsecond=0),
                'created_at': datetime.utcnow(),
            },
            session=session,
        )

    with client.start_session() as session:
        session.with_transaction(callback)


# ==========================================================================
# 5. RETRY ON TRANSIENT ERROR (manual)
# ==========================================================================

def run_with_retry(func, *args, max_retries=5, **kwargs):
    """Wrap any transaction function with TransientTransactionError retry."""
    for attempt in range(max_retries):
        try:
            return func(*args, **kwargs)
        except OperationFailure as e:
            if e.has_error_label('TransientTransactionError'):
                if attempt < max_retries - 1:
                    continue
            raise
    raise RuntimeError("Max retries exceeded")


# ==========================================================================
# 6. SINGLE-DOC ATOMIC (when transaction overkill)
# ==========================================================================

# Atomic increment + check in ONE operation
def decrement_stock_atomic(product_id, qty):
    """No transaction needed — single-doc op is atomic."""
    result = db.products.update_one(
        {'_id': product_id, 'stock': {'$gte': qty}},
        {'$inc': {'stock': -qty}},
    )
    return result.matched_count == 1


# Atomic upsert
def set_user_field(user_id, field, value):
    db.users.update_one(
        {'_id': user_id},
        {'$set': {field: value, 'updated_at': datetime.utcnow()}},
        upsert=True,
    )


# Find-and-modify atomically
def claim_next_job():
    """Atomically grab + mark as processing."""
    return db.jobs.find_one_and_update(
        {'status': 'pending'},
        {'$set': {'status': 'processing', 'claimed_at': datetime.utcnow()}},
        sort=[('priority', -1), ('created_at', 1)],
        return_document=pymongo.ReturnDocument.AFTER,
    )


# ==========================================================================
# 7. SAGA PATTERN (when transaction not possible)
# ==========================================================================

class SagaStep:
    def __init__(self, do_func, undo_func):
        self.do = do_func
        self.undo = undo_func


def run_saga(steps: list[SagaStep]):
    """Execute steps; rollback on failure."""
    completed = []
    try:
        for step in steps:
            step.do()
            completed.append(step)
    except Exception:
        # Compensate in reverse order
        for step in reversed(completed):
            try:
                step.undo()
            except Exception as undo_err:
                print(f"WARNING: undo failed: {undo_err}")
        raise


# Example
# steps = [
#     SagaStep(
#         do=lambda: db.accounts.update_one({'_id': 'A'}, {'$inc': {'balance': -100}}),
#         undo=lambda: db.accounts.update_one({'_id': 'A'}, {'$inc': {'balance': 100}}),
#     ),
#     SagaStep(
#         do=lambda: call_external_payment_api(),
#         undo=lambda: reverse_external_payment(),
#     ),
# ]
# run_saga(steps)


# ==========================================================================
# 8. EMBEDDED DOC PATTERN (avoid transactions)
# ==========================================================================

# Instead of separate collections, embed related data
def add_order_to_user_atomic(user_id: str, order: dict):
    """Single-doc update — atomic without transaction."""
    db.users.update_one(
        {'_id': user_id},
        {
            '$push': {'orders': order},
            '$inc': {'total_spend': order['amount']},
            '$set': {'last_order_at': datetime.utcnow()},
        },
    )


# ==========================================================================
# 9. SETUP CHECKLIST
# ==========================================================================

SETUP_CHECKLIST = """
# Replica set setup (required for transactions)
mongod --replSet rs0 --port 27017 --dbpath /data/rs0 &
mongod --replSet rs0 --port 27018 --dbpath /data/rs1 &
mongod --replSet rs0 --port 27019 --dbpath /data/rs2 &

# Initialize
mongosh --port 27017
> rs.initiate({
    _id: "rs0",
    members: [
      { _id: 0, host: "localhost:27017" },
      { _id: 1, host: "localhost:27018" },
      { _id: 2, host: "localhost:27019" }
    ]
})

# Verify
> rs.status()

# Connection string
mongodb://localhost:27017,localhost:27018,localhost:27019/?replicaSet=rs0

# Tune transaction timeout (default 60s)
> db.adminCommand({setParameter: 1, transactionLifetimeLimitSeconds: 120})
"""


# ==========================================================================
# 10. MONITORING TRANSACTIONS
# ==========================================================================

def transaction_metrics():
    stats = db.command('serverStatus')['transactions']
    print(f"Currently active: {stats['currentActive']}")
    print(f"Currently inactive: {stats['currentInactive']}")
    print(f"Total started: {stats['totalStarted']}")
    print(f"Total aborted: {stats['totalAborted']}")
    print(f"Total committed: {stats['totalCommitted']}")
    abort_rate = stats['totalAborted'] / max(stats['totalStarted'], 1) * 100
    print(f"Abort rate: {abort_rate:.1f}%")
    if abort_rate > 10:
        print("ALERT: high abort rate — investigate conflicts")


# ==========================================================================
# 11. WHEN TO USE EACH PATTERN
# ==========================================================================

DECISION_TREE = """
Single doc update?
    → Use single-doc atomic ($inc, $set, find_one_and_update)
    → NO transaction needed

Multi-doc, same collection, can embed?
    → Embed into one doc, update atomically
    → NO transaction needed

Multi-doc, different collections, on same MongoDB?
    → Use transaction with majority write concern
    → with_transaction() for auto-retry

Multi-service / external API call?
    → Saga pattern with compensating actions
    → Or 2PC if all services support
    → MongoDB transactions can't span external systems

High throughput, low conflict?
    → Optimistic concurrency: version field + retry
    → Faster than transactions

Read-heavy with rare writes?
    → ReadConcern('majority') for consistent reads
    → No transaction needed
"""
