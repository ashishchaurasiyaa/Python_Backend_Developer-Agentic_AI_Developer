"""
MongoDB Transactions — Production Patterns

Run: python 05_transactions_deep.py
Prereq: docker compose up -d   (see docker-compose.yml in this folder —
        single-node REPLICA SET, transactions/change streams ka isके bina
        matlab hi nahi banta, standalone mongod pe ye chalte hi nahi)
"""

import os
import asyncio
from datetime import datetime

import pymongo
from pymongo import MongoClient, WriteConcern
from pymongo.read_concern import ReadConcern
from pymongo.errors import OperationFailure
from motor.motor_asyncio import AsyncIOMotorClient


# Replica set required for transactions.
# directConnection=true — single-node rs0 ka member host "mongo:27017" hai
# (docker network ke andar), jo host machine se resolve nahi hota. Direct
# connect kar ke replica-set topology auto-discovery skip karte hain — is
# node ko seedha target karte hain (yahi hamesha PRIMARY hai).
MONGO_URI = os.getenv("MONGO_LAB_URI", "mongodb://localhost:27018/?directConnection=true")
client = MongoClient(MONGO_URI)
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


# ==========================================================================
# 12. LAB DRIVER — prove atomicity for real (rollback vs corrupted write)
# ==========================================================================

def _reset_bank_lab() -> None:
    """Fresh lab accounts — purana lab data clear karo."""
    db.accounts.delete_many({'_id': {'$in': ['lab_A', 'lab_B']}})
    db.accounts.insert_many([
        {'_id': 'lab_A', 'balance': 1000},
        {'_id': 'lab_B', 'balance': 500},
    ])


def _get_balances() -> tuple:
    a = db.accounts.find_one({'_id': 'lab_A'})['balance']
    b = db.accounts.find_one({'_id': 'lab_B'})['balance']
    return a, b


def transfer_in_transaction(from_id: str, to_id: str, amount: int,
                             session, blow_up: bool = False) -> None:
    """
    Bank transfer — debit + credit ATOMIC hone chahiye: dono ho ya koi nahi.

    blow_up=True → debit ke turant baad, credit se PEHLE exception raise
    karta hai (simulate: mid-transfer crash / bug). Transaction sahi se
    wired ho to poora block rollback ho jayega — debit bhi undo hoga.
    Wire NA ho (jaisa abhi hai) to debit permanently apply ho jayega —
    paisa "gayab" ho gaya, atomicity toot gayi.
    """
    # ─────────────────────────────────────────────────────────────
    # TODO 1: neeche do updates ko ek TRANSACTION ke andar wrap karo.
    #   Abhi dono updates seedhe-seedhe (session ke saath, par bina
    #   transaction ke) chal rahe hain — matlab blow_up=True hone par debit
    #   ROLLBACK nahi hoga, sirf credit skip hoga. Real bank ke liye ye
    #   disaster hai.
    #   Hint: `with session.start_transaction(read_concern=ReadConcern('snapshot'),
    #                                          write_concern=WriteConcern('majority')):`
    #   — poore neeche wale 3 statements (debit, blow_up check, credit) ko
    #   isi `with` block ke andar indent kar do.
    db.accounts.update_one({'_id': from_id}, {'$inc': {'balance': -amount}}, session=session)
    if blow_up:
        raise RuntimeError("simulated crash mid-transfer (after debit, before credit)")
    db.accounts.update_one({'_id': to_id}, {'$inc': {'balance': amount}}, session=session)
    # ─────────────────────────────────────────────────────────────


def main() -> None:
    print("MongoDB Transactions Lab — atomic rollback vs corrupted partial write")

    print("\n[1] Connect + reset lab accounts")
    client.admin.command('ping')
    _reset_bank_lab()
    a0, b0 = _get_balances()
    print(f"    lab_A={a0}  lab_B={b0}")

    print("\n[2] Transfer 200 that CRASHES mid-transfer (blow_up=True)")
    with client.start_session() as session:
        try:
            transfer_in_transaction('lab_A', 'lab_B', 200, session, blow_up=True)
        except RuntimeError as e:
            print(f"    caught simulated crash: {e}")
    a1, b1 = _get_balances()
    print(f"    after crash: lab_A={a1}  lab_B={b1}")

    print("\n[3] Reset + successful transfer of 200 (no crash)")
    _reset_bank_lab()
    with client.start_session() as session:
        transfer_in_transaction('lab_A', 'lab_B', 200, session, blow_up=False)
    a2, b2 = _get_balances()
    print(f"    after transfer: lab_A={a2}  lab_B={b2}")

    print("\n" + "─" * 60)
    rollback_ok = (a1 == a0 and b1 == b0)
    commit_ok = (a2 == a0 - 200 and b2 == b0 + 200)

    if rollback_ok and commit_ok:
        print("✅ PASS — crash ne pura transfer rollback kiya (balances "
              "unchanged), aur successful transfer ne dono balances "
              "atomically update kiye.")
    elif not rollback_ok:
        print(f"❌ FAIL — crash ke baad balances badal gaye "
              f"(lab_A {a0}→{a1}, lab_B {b0}→{b1}). TODO 1 abhi bhi "
              "unfilled hai — updates transaction ke andar wrap nahi hain, "
              "isliye debit permanently apply ho gaya even though credit "
              "kabhi hua hi nahi. Fix: session.start_transaction() se wrap karo.")
    else:
        print(f"❌ FAIL — successful transfer ke baad balances galat hain "
              f"(expected lab_A={a0 - 200}, lab_B={b0 + 200}; "
              f"got lab_A={a2}, lab_B={b2}).")

    print(f"""
SOCH (bolke jawab do):
  1. blow_up=True wale case me agar transaction wrap na ho, to debit
     permanently apply ho jaata hai par credit kabhi nahi — real production
     me iska matlab paisa "gayab" ho gaya. Client retry kare to kya double-
     debit ho sakta hai?
  2. with_transaction() (auto-retry wrapper, upar section 2 dekho) vs manual
     session.start_transaction() (jo TODO 1 me use kiya) — kab kaunsa
     use karoge?
  3. write_concern='majority' kyun zaroori hai transaction commit ke liye?
     Agar w=1 use karte to primary failover pe kya risk hota?
  4. Single-node replica set me transactions test ho sakti hain, par
     multi-node cluster me ek extra failure mode hota hai jo yahan kabhi
     nahi dikhega — kya? (Hint: network partition during commit →
     TransientTransactionError, retry chahiye)
""")


if __name__ == "__main__":
    main()
