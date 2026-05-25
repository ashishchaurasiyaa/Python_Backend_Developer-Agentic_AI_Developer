"""
Optimistic vs Pessimistic Locking — Production Patterns
"""

import time
import random
from contextlib import contextmanager


# ==========================================================================
# 1. PESSIMISTIC — SELECT FOR UPDATE (Django ORM)
# ==========================================================================

"""
from django.db import transaction
from blog.models import Product, Order
from blog.exceptions import OutOfStock


@transaction.atomic
def buy_item_pessimistic(user, product_id):
    # Acquires row-level exclusive lock until COMMIT
    product = Product.objects.select_for_update().get(pk=product_id)

    if product.stock <= 0:
        raise OutOfStock()

    product.stock -= 1
    product.save()

    return Order.objects.create(user=user, product=product)
"""


# ==========================================================================
# 2. NOWAIT — fail fast on lock contention
# ==========================================================================

"""
from django.db import DatabaseError, transaction


def try_buy_nowait(user, product_id):
    try:
        with transaction.atomic():
            product = (
                Product.objects
                .select_for_update(nowait=True)
                .get(pk=product_id)
            )
            product.stock -= 1
            product.save()
            return Order.objects.create(user=user, product=product)
    except DatabaseError as e:
        if 'could not obtain lock' in str(e).lower():
            return {'status': 'busy, try again'}
        raise
"""


# ==========================================================================
# 3. SKIP LOCKED — concurrent worker pattern (job queue)
# ==========================================================================

"""
@transaction.atomic
def claim_next_job(worker_id):
    job = (
        Job.objects
        .select_for_update(skip_locked=True)
        .filter(status='pending')
        .order_by('priority', 'created_at')   # determinism
        .first()
    )
    if job is None:
        return None
    job.status = 'processing'
    job.claimed_by = worker_id
    job.claimed_at = timezone.now()
    job.save()
    return job


# Multiple Celery workers run this — each gets different job
# Without SKIP LOCKED: they'd serialize through same row
"""


# ==========================================================================
# 4. OPTIMISTIC — Version column + retry
# ==========================================================================

"""
# Model
class Product(models.Model):
    name = models.CharField(max_length=200)
    stock = models.IntegerField()
    version = models.IntegerField(default=0)


def buy_item_optimistic(product_id, max_retries=5):
    for attempt in range(max_retries):
        product = Product.objects.get(pk=product_id)  # no lock

        if product.stock <= 0:
            raise OutOfStock()

        # Atomic conditional update
        updated = Product.objects.filter(
            pk=product_id,
            version=product.version,
        ).update(
            stock=product.stock - 1,
            version=product.version + 1,
        )

        if updated == 1:
            return product
        # Lost — someone else updated. Retry with backoff.
        sleep_time = 0.05 * (2 ** attempt) + random.random() * 0.05
        time.sleep(sleep_time)

    raise ConcurrencyError(f"Too many concurrent updates for product {product_id}")
"""


# ==========================================================================
# 5. ATOMIC UPDATE (single SQL — no transaction needed)
# ==========================================================================

"""
def buy_item_atomic(product_id):
    # Single UPDATE with condition — atomic, no race
    updated = Product.objects.filter(
        pk=product_id,
        stock__gt=0,
    ).update(stock=F('stock') - 1)

    if updated == 0:
        raise OutOfStock()
    # Now safe to create Order
"""


# ==========================================================================
# 6. SQLALCHEMY ASYNC — with_for_update
# ==========================================================================

"""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


async def buy_item_sqlalchemy_async(session: AsyncSession, product_id: int):
    async with session.begin():
        stmt = select(Product).where(Product.id == product_id).with_for_update()
        result = await session.execute(stmt)
        product = result.scalar_one()

        if product.stock <= 0:
            raise OutOfStock()
        product.stock -= 1
        # auto-commit on context exit
"""


# ==========================================================================
# 7. SQLALCHEMY VERSION COUNTER (auto-managed)
# ==========================================================================

"""
from sqlalchemy import Column, Integer, String


class Product(Base):
    __tablename__ = 'products'
    __mapper_args__ = {
        'version_id_col': version_column,
    }
    id = Column(Integer, primary_key=True)
    name = Column(String(200))
    stock = Column(Integer)
    version_column = Column(Integer, nullable=False)


# SQLAlchemy auto-adds: WHERE version_column = X to every UPDATE
# Raises StaleDataError if version doesn't match (someone else updated)
"""


# ==========================================================================
# 8. ACCOUNT TRANSFER (deadlock prevention via ordered locks)
# ==========================================================================

"""
@transaction.atomic
def transfer(from_id: int, to_id: int, amount: float):
    if from_id == to_id:
        raise ValueError("Cannot transfer to self")

    # CRITICAL: lock in deterministic order (PK ascending)
    # Otherwise two concurrent transfers (A→B and B→A) deadlock
    first_id, second_id = sorted([from_id, to_id])

    locked = list(
        Account.objects
        .select_for_update()
        .filter(pk__in=[first_id, second_id])
        .order_by('pk')
    )
    by_id = {a.pk: a for a in locked}
    from_acc = by_id[from_id]
    to_acc = by_id[to_id]

    if from_acc.balance < amount:
        raise InsufficientFunds()

    from_acc.balance -= amount
    to_acc.balance += amount
    from_acc.save()
    to_acc.save()

    Transaction.objects.create(
        from_account=from_acc,
        to_account=to_acc,
        amount=amount,
    )
"""


# ==========================================================================
# 9. DEADLOCK RETRY WRAPPER
# ==========================================================================

"""
from django.db import OperationalError
from functools import wraps


def retry_on_deadlock(max_retries=3):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except OperationalError as e:
                    msg = str(e).lower()
                    if 'deadlock' in msg or 'lock wait timeout' in msg:
                        if attempt < max_retries - 1:
                            time.sleep(0.05 * (2 ** attempt) + random.random() * 0.05)
                            continue
                    raise
            raise OperationalError('Max deadlock retries exceeded')
        return wrapper
    return decorator


@retry_on_deadlock(max_retries=5)
def transfer_safe(from_id, to_id, amount):
    return transfer(from_id, to_id, amount)
"""


# ==========================================================================
# 10. REDIS DISTRIBUTED LOCK (across services/DBs)
# ==========================================================================

import redis
from redis.lock import Lock as RedisLock


r = redis.Redis(host='localhost', port=6379)


@contextmanager
def distributed_lock(key: str, timeout: int = 10, blocking_timeout: int = 5):
    lock = RedisLock(r, key, timeout=timeout, blocking_timeout=blocking_timeout)
    acquired = lock.acquire()
    if not acquired:
        raise Exception(f"Could not acquire lock {key}")
    try:
        yield lock
    finally:
        try:
            lock.release()
        except redis.exceptions.LockError:
            pass


# Usage
def update_external_resource(resource_id, data):
    with distributed_lock(f'resource:{resource_id}', timeout=30):
        # Critical section — exclusive access across all processes
        ...


# ==========================================================================
# 11. RAW SQL EXAMPLES
# ==========================================================================

"""
-- PostgreSQL: SELECT FOR UPDATE
BEGIN;
SELECT * FROM products WHERE id = 5 FOR UPDATE;
UPDATE products SET stock = stock - 1 WHERE id = 5;
COMMIT;

-- SKIP LOCKED for job queue
BEGIN;
SELECT * FROM jobs
WHERE status = 'pending'
ORDER BY priority, created_at
LIMIT 1
FOR UPDATE SKIP LOCKED;

-- Lock timeout
SET lock_timeout = '5s';

-- Atomic single-statement update (no SELECT FOR UPDATE needed)
UPDATE products
SET stock = stock - 1
WHERE id = 5 AND stock > 0;

-- Check affected rows = 1 means success
"""


# ==========================================================================
# 12. DEBUGGING LOCKS (PostgreSQL)
# ==========================================================================

"""
-- Currently held locks
SELECT pid, locktype, relation::regclass, mode, granted
FROM pg_locks
WHERE NOT granted;

-- Who's blocking whom
SELECT
    blocked_locks.pid AS blocked_pid,
    blocked_activity.query AS blocked_query,
    blocking_activity.pid AS blocking_pid,
    blocking_activity.query AS blocking_query,
    EXTRACT(EPOCH FROM (now() - blocking_activity.query_start)) AS blocking_duration_sec
FROM pg_catalog.pg_locks blocked_locks
JOIN pg_catalog.pg_stat_activity blocked_activity ON blocked_activity.pid = blocked_locks.pid
JOIN pg_catalog.pg_locks blocking_locks
    ON blocking_locks.locktype = blocked_locks.locktype
    AND blocking_locks.relation = blocked_locks.relation
    AND blocking_locks.pid != blocked_locks.pid
JOIN pg_catalog.pg_stat_activity blocking_activity ON blocking_activity.pid = blocking_locks.pid
WHERE NOT blocked_locks.granted AND blocking_locks.granted;

-- Long-running idle transactions (holding locks!)
SELECT pid, now() - xact_start AS duration, state, query
FROM pg_stat_activity
WHERE state IN ('idle in transaction', 'idle in transaction (aborted)')
ORDER BY duration DESC;
"""


# ==========================================================================
# 13. PERFORMANCE COMPARISON
# ==========================================================================

"""
Pessimistic locking:
+ Simple — no retry logic
+ Strong guarantee — no lost updates
- Reduces throughput (serial)
- Risk of deadlock
- Long-held lock blocks others

Optimistic locking:
+ High throughput (no waiting)
+ No deadlock
- Wasted work on conflict (retry)
- Complex retry logic
- Bad for high-contention rows

Rule of thumb:
- Conflict rate < 1%  → optimistic
- Conflict rate > 10% → pessimistic
- Mixed/uncertain     → atomic single-statement updates if possible
"""
