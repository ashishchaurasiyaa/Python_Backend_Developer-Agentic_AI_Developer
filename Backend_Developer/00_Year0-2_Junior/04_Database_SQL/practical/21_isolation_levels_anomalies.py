"""
Isolation Levels & Anomalies — Production Patterns
"""

import time
import random
import threading
import psycopg
from psycopg import sql
from psycopg.errors import SerializationFailure, DeadlockDetected


DB_DSN = "postgresql://user:pass@localhost:5432/mydb"


# ==========================================================================
# 1. DEMONSTRATING LOST UPDATE (READ COMMITTED — default)
# ==========================================================================

def demo_lost_update():
    """Two threads both add to same balance — one update lost."""

    def add_to_balance(amount):
        with psycopg.connect(DB_DSN) as conn:
            conn.autocommit = False
            with conn.cursor() as cur:
                # Read
                cur.execute("SELECT balance FROM accounts WHERE id = 1")
                balance = cur.fetchone()[0]
                # Simulate processing delay
                time.sleep(0.1)
                # Write
                cur.execute(
                    "UPDATE accounts SET balance = %s WHERE id = 1",
                    [balance + amount],
                )
                conn.commit()

    t1 = threading.Thread(target=add_to_balance, args=(50,))
    t2 = threading.Thread(target=add_to_balance, args=(30,))
    t1.start(); t2.start()
    t1.join(); t2.join()

    # Expected: 80 total added; Actual: only 50 OR 30 added (lost update)


# ==========================================================================
# 2. FIX 1 — SELECT FOR UPDATE
# ==========================================================================

def add_with_select_for_update(amount):
    with psycopg.connect(DB_DSN) as conn:
        conn.autocommit = False
        with conn.cursor() as cur:
            cur.execute("SELECT balance FROM accounts WHERE id = 1 FOR UPDATE")
            balance = cur.fetchone()[0]
            cur.execute(
                "UPDATE accounts SET balance = %s WHERE id = 1",
                [balance + amount],
            )
            conn.commit()


# ==========================================================================
# 3. FIX 2 — ATOMIC UPDATE (no isolation tricks)
# ==========================================================================

def atomic_add(amount):
    with psycopg.connect(DB_DSN) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE accounts SET balance = balance + %s WHERE id = 1",
                [amount],
            )
        conn.commit()
    # Single statement atomic — no race condition


# ==========================================================================
# 4. FIX 3 — SERIALIZABLE + retry
# ==========================================================================

def add_serializable_with_retry(amount, max_retries=5):
    for attempt in range(max_retries):
        try:
            with psycopg.connect(DB_DSN) as conn:
                conn.autocommit = False
                with conn.cursor() as cur:
                    cur.execute("SET TRANSACTION ISOLATION LEVEL SERIALIZABLE")
                    cur.execute("SELECT balance FROM accounts WHERE id = 1")
                    balance = cur.fetchone()[0]
                    time.sleep(0.05)
                    cur.execute(
                        "UPDATE accounts SET balance = %s WHERE id = 1",
                        [balance + amount],
                    )
                    conn.commit()
            return
        except SerializationFailure:
            if attempt < max_retries - 1:
                # Exponential backoff with jitter
                delay = 0.05 * (2 ** attempt) + random.random() * 0.05
                time.sleep(delay)
                continue
            raise
    raise Exception("Max retries exceeded")


# ==========================================================================
# 5. WRITE SKEW DEMO
# ==========================================================================

def demo_write_skew():
    """
    Constraint: at least 1 doctor on-call.

    Two doctors are on-call: A and B.
    Both decide to go off-call at the same time.
    Each checks "are there other on-call doctors?" sees 2 → goes off-call.
    Result: 0 on-call doctors — constraint violated.
    """

    def go_off_call(doctor_id):
        with psycopg.connect(DB_DSN) as conn:
            conn.autocommit = False
            with conn.cursor() as cur:
                cur.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ")

                # Check on-call count
                cur.execute("SELECT COUNT(*) FROM doctors WHERE on_call = true")
                count = cur.fetchone()[0]

                if count >= 2:
                    # Safe to go off-call (so we think)
                    cur.execute(
                        "UPDATE doctors SET on_call = false WHERE id = %s",
                        [doctor_id],
                    )
                conn.commit()
        # REPEATABLE READ does NOT prevent this!
        # SERIALIZABLE would abort one of the two


# ==========================================================================
# 6. ANOMALY DEMOS BY ISOLATION LEVEL
# ==========================================================================

ANOMALY_TABLE = """
┌──────────────────────┬───────────────┬───────────────┬───────────────┬───────────────┐
│ Anomaly              │ READ UNCOMM   │ READ COMMITTED│ REP READ      │ SERIALIZABLE  │
├──────────────────────┼───────────────┼───────────────┼───────────────┼───────────────┤
│ Dirty read           │ Possible      │ NO            │ NO            │ NO            │
│ Non-repeatable read  │ Possible      │ Possible      │ NO            │ NO            │
│ Phantom read         │ Possible      │ Possible      │ NO (PG) /     │ NO            │
│                      │               │               │ Possible (std)│               │
│ Lost update          │ Possible      │ Possible      │ Possible*     │ NO            │
│ Write skew           │ Possible      │ Possible      │ Possible      │ NO            │
└──────────────────────┴───────────────┴───────────────┴───────────────┴───────────────┘

* Lost update prevention varies by DB — PG REPEATABLE READ catches via abort
* PostgreSQL doesn't implement READ UNCOMMITTED (treats as READ COMMITTED)
* MySQL InnoDB REPEATABLE READ prevents phantoms via next-key locks
"""


# ==========================================================================
# 7. SQLALCHEMY ISOLATION LEVEL SETUP
# ==========================================================================

"""
from sqlalchemy import create_engine

# Per-engine default
engine = create_engine(URL, isolation_level="REPEATABLE READ")

# Per-connection
with engine.connect().execution_options(isolation_level="SERIALIZABLE") as conn:
    # ...
    pass

# Async
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession

engine = create_async_engine(URL, isolation_level="REPEATABLE READ")

async with engine.connect() as conn:
    await conn.execution_options(isolation_level="SERIALIZABLE")
"""


# ==========================================================================
# 8. DJANGO ISOLATION LEVEL
# ==========================================================================

"""
# settings.py — global default
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        # ...
        'OPTIONS': {
            'isolation_level': psycopg.IsolationLevel.REPEATABLE_READ,
        },
    },
}


# Per-transaction
from django.db import connection, transaction


@transaction.atomic
def report_with_consistent_view():
    with connection.cursor() as c:
        c.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ")
    # All queries see same snapshot
    total = Order.objects.aggregate(Sum('amount'))
    count = Order.objects.count()


# Auto-retry decorator for SERIALIZABLE
from django.db import OperationalError
from functools import wraps


def serializable_retry(max_retries=5):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(max_retries):
                try:
                    with transaction.atomic():
                        with connection.cursor() as c:
                            c.execute("SET TRANSACTION ISOLATION LEVEL SERIALIZABLE")
                        return func(*args, **kwargs)
                except OperationalError as e:
                    if 'serialize' in str(e).lower():
                        if attempt < max_retries - 1:
                            time.sleep(0.05 * 2 ** attempt + random.random() * 0.05)
                            continue
                    raise
            raise OperationalError("Max retries")
        return wrapper
    return decorator
"""


# ==========================================================================
# 9. CHECKING SNAPSHOT STATE (PostgreSQL)
# ==========================================================================

SNAPSHOT_QUERIES = """
-- Current transaction state
SELECT pid, xact_start, state, query
FROM pg_stat_activity
WHERE state LIKE 'idle%';


-- Active transaction's snapshot
SELECT txid_current(), txid_current_snapshot();


-- Find long-running idle transactions (cause bloat)
SELECT pid, now() - xact_start AS duration, state, query
FROM pg_stat_activity
WHERE state IN ('idle in transaction', 'idle in transaction (aborted)')
ORDER BY duration DESC;


-- Kill stuck transaction
SELECT pg_terminate_backend(pid)
FROM pg_stat_activity
WHERE state = 'idle in transaction'
  AND now() - xact_start > interval '10 minutes';


-- Set idle timeout (auto-abort)
SET idle_in_transaction_session_timeout = '5min';
"""


# ==========================================================================
# 10. RECOMMENDED PATTERNS PER USE CASE
# ==========================================================================

PATTERNS = """
Banking transfer:
    SERIALIZABLE + retry on conflict
    OR FOR UPDATE in deterministic order + READ COMMITTED

Inventory decrement:
    Atomic UPDATE — `UPDATE ... SET stock = stock - 1 WHERE stock > 0`
    Single statement = no isolation needed

Multi-step report (consistent snapshot):
    REPEATABLE READ — all queries see same snapshot

Read-modify-write on unique constraint:
    SERIALIZABLE + retry
    OR INSERT ... ON CONFLICT DO UPDATE (UPSERT)

Job queue (concurrent claim):
    SELECT FOR UPDATE SKIP LOCKED
    READ COMMITTED is fine

Counters (high contention):
    UPDATE with WHERE — atomic
    OR Redis INCR — DB-free
"""
