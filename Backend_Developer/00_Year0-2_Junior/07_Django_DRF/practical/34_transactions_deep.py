"""
Django Transactions Deep — Production Patterns
"""

import time
import random
import logging
from functools import wraps

from django.db import transaction, connection, OperationalError, IntegrityError


log = logging.getLogger(__name__)


# ==========================================================================
# 1. BASIC ATOMIC PATTERNS
# ==========================================================================

"""
from blog.models import Order, Payment, Account


# Decorator
@transaction.atomic
def transfer(from_id, to_id, amount):
    from_acc = Account.objects.select_for_update().get(pk=from_id)
    to_acc = Account.objects.select_for_update().get(pk=to_id)

    if from_acc.balance < amount:
        raise ValueError('Insufficient funds')

    from_acc.balance -= amount
    to_acc.balance += amount
    from_acc.save()
    to_acc.save()
    # Auto-commit on success; auto-rollback on exception


# Context manager
def create_order(user, cart):
    with transaction.atomic():
        order = Order.objects.create(user=user, total=cart.total)
        for item in cart.items.all():
            OrderItem.objects.create(order=order, product=item.product, qty=item.qty)
        cart.delete()
    # Commit happens at end of `with` block
    return order
"""


# ==========================================================================
# 2. NESTED ATOMIC (SAVEPOINTS)
# ==========================================================================

"""
@transaction.atomic
def complex_order(user, cart):
    order = Order.objects.create(user=user)

    successful_items = 0
    for item in cart.items.all():
        try:
            with transaction.atomic():    # SAVEPOINT
                Inventory.objects.select_for_update().filter(
                    product=item.product, stock__gte=item.qty
                ).update(stock=F('stock') - item.qty)
                OrderItem.objects.create(order=order, **item)
                successful_items += 1
        except OutOfStock:
            # Savepoint rolled back; outer txn continues
            log.warning(f'Out of stock for {item.product_id}')

    if successful_items == 0:
        raise ValueError('No items available')

    order.item_count = successful_items
    order.save()
    # All successful items committed
"""


# ==========================================================================
# 3. on_commit HOOK
# ==========================================================================

"""
from blog.tasks import send_welcome_email, notify_admins


@transaction.atomic
def signup(email, password):
    user = User.objects.create_user(email=email, password=password)
    profile = Profile.objects.create(user=user)

    # WRONG: dispatch may run before COMMIT, task receives unknown user_id
    # send_welcome_email.delay(user.id)

    # RIGHT: only fires after successful commit
    transaction.on_commit(lambda: send_welcome_email.delay(user.id))

    # Multiple hooks OK
    transaction.on_commit(lambda: notify_admins.delay(f'New signup: {email}'))

    return user


# If on_commit handler raises, doesn't roll back (commit already done)
# Wrap in try/except + alerting
"""


# ==========================================================================
# 4. SELECT FOR UPDATE PATTERNS
# ==========================================================================

"""
@transaction.atomic
def reserve_seat(seat_id, user):
    seat = Seat.objects.select_for_update().get(pk=seat_id)
    if seat.status != 'available':
        raise SeatTaken()
    seat.status = 'reserved'
    seat.reserved_by = user
    seat.save()
    return seat


# NOWAIT — fail fast
@transaction.atomic
def try_reserve(seat_id, user):
    try:
        seat = Seat.objects.select_for_update(nowait=True).get(pk=seat_id)
    except DatabaseError:
        return None  # Someone else has it
    # ... proceed


# SKIP LOCKED — job queue pattern
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
        job.claimed_by = worker_id
        job.save()
    return job


# Lock only some tables in JOIN
@transaction.atomic
def update_order_with_user_join(order_id):
    order = (
        Order.objects
        .select_related('user')
        .select_for_update(of=('self',))   # only lock order, not user
        .get(pk=order_id)
    )
"""


# ==========================================================================
# 5. SET_ROLLBACK (mark for rollback without exception)
# ==========================================================================

"""
@transaction.atomic
def process_with_validation(request):
    Order.objects.create(...)

    if some_check_fails:
        transaction.set_rollback(True)
        return Response({'error': 'Validation failed'}, status=400)

    # If no rollback marked, commit happens normally
    return Response({'status': 'ok'})
"""


# ==========================================================================
# 6. DEADLOCK RETRY DECORATOR
# ==========================================================================

def retry_on_deadlock(max_retries=3, base_delay=0.05):
    """Decorator: retry on PostgreSQL deadlock detection."""

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exc = None
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except OperationalError as e:
                    msg = str(e).lower()
                    if 'deadlock' in msg or 'lock wait timeout' in msg:
                        last_exc = e
                        if attempt < max_retries - 1:
                            delay = base_delay * (2 ** attempt) + random.random() * 0.05
                            time.sleep(delay)
                            continue
                    raise
            raise last_exc

        return wrapper
    return decorator


# Usage
"""
@retry_on_deadlock(max_retries=5)
@transaction.atomic
def transfer(from_id, to_id, amount):
    # Lock in consistent order to MINIMIZE deadlocks
    ids = sorted([from_id, to_id])
    accs = list(Account.objects.select_for_update().filter(pk__in=ids).order_by('pk'))
    # ...
"""


# ==========================================================================
# 7. ATOMIC PER DATABASE (multi-DB)
# ==========================================================================

"""
# Multi-DB writes — separate transactions per DB
def cross_db_op():
    with transaction.atomic(using='default'):
        Order.objects.using('default').create(...)

    with transaction.atomic(using='analytics'):
        AnalyticsEvent.objects.using('analytics').create(...)
    # NOT cross-DB atomic — both run independently

# For cross-DB consistency, use Saga or eventual consistency
"""


# ==========================================================================
# 8. NON-ATOMIC VIEWS (with ATOMIC_REQUESTS=True globally)
# ==========================================================================

"""
# settings.py
DATABASES = {
    'default': {
        ...
        'ATOMIC_REQUESTS': True,
    },
}


# But specific view should NOT be atomic (e.g., long-running, no DB writes)
from django.db.transaction import non_atomic_requests


@non_atomic_requests
def long_running_export(request):
    # No transaction held
    return StreamingHttpResponse(generate_csv())
"""


# ==========================================================================
# 9. CONNECTION-LEVEL SETTINGS
# ==========================================================================

"""
# Inside atomic block, set per-transaction config

@transaction.atomic
def critical_update():
    with connection.cursor() as c:
        c.execute("SET LOCAL statement_timeout = '5s'")
        c.execute("SET LOCAL lock_timeout = '2s'")
        c.execute("SET LOCAL idle_in_transaction_session_timeout = '30s'")

    # Now operations within this txn use these timeouts
    Order.objects.filter(...).update(...)


# Per-database global setting
DATABASES = {
    'default': {
        ...
        'OPTIONS': {
            'options': '-c statement_timeout=30000 -c lock_timeout=10000',
        },
    },
}
"""


# ==========================================================================
# 10. ASYNC TRANSACTIONS (Django 5.1+)
# ==========================================================================

"""
import asyncio
from django.db import transaction


async def async_transfer(from_id, to_id, amount):
    async with transaction.atomic():
        from_acc = await Account.objects.aget(pk=from_id)
        to_acc = await Account.objects.aget(pk=to_id)

        if from_acc.balance < amount:
            raise ValueError('Insufficient')

        from_acc.balance -= amount
        to_acc.balance += amount
        await from_acc.asave()
        await to_acc.asave()


# Older Django: wrap sync in sync_to_async
from asgiref.sync import sync_to_async

async def async_transfer_old(from_id, to_id, amount):
    @sync_to_async
    def _do():
        with transaction.atomic():
            # sync code
            pass
    return await _do()
"""


# ==========================================================================
# 11. TESTING TRANSACTIONS
# ==========================================================================

"""
from django.test import TransactionTestCase, TestCase


# TestCase wraps each test in transaction + rollback (fast, but on_commit doesn't fire!)
class FastTests(TestCase):
    def test_no_on_commit(self):
        with self.captureOnCommitCallbacks(execute=True):
            create_order(...)
            # on_commit callbacks captured and executed



# TransactionTestCase actually commits (slow, but realistic)
class RealTransactionTests(TransactionTestCase):
    def test_with_real_commit(self):
        create_order(...)
        # on_commit fires for real


# captureOnCommitCallbacks in TestCase (Django 4+)
class HookTests(TestCase):
    def test_on_commit_executed(self):
        with self.captureOnCommitCallbacks(execute=True) as callbacks:
            with transaction.atomic():
                transaction.on_commit(lambda: print('committed'))

        self.assertEqual(len(callbacks), 1)
"""


# ==========================================================================
# 12. MONITORING LONG TRANSACTIONS
# ==========================================================================

LONG_TXN_QUERIES = """
-- PostgreSQL: find long-running transactions
SELECT
    pid,
    usename,
    state,
    now() - xact_start AS duration,
    query
FROM pg_stat_activity
WHERE state IN ('idle in transaction', 'idle in transaction (aborted)')
  AND now() - xact_start > interval '5 minutes'
ORDER BY duration DESC;


-- Kill stuck transactions
SELECT pg_terminate_backend(pid)
FROM pg_stat_activity
WHERE state = 'idle in transaction'
  AND now() - xact_start > interval '30 minutes';


-- Auto-kill via DB config
ALTER ROLE myapp SET idle_in_transaction_session_timeout = '5min';


-- Currently held locks
SELECT
    locktype,
    relation::regclass,
    mode,
    granted,
    pid
FROM pg_locks
WHERE NOT granted;
"""


# ==========================================================================
# 13. PATTERN: COMMIT-OR-ROLLBACK + EMAIL
# ==========================================================================

"""
@transaction.atomic
def register_user(email, password, name):
    # All DB work inside atomic
    user = User.objects.create_user(email=email, password=password)
    Profile.objects.create(user=user, name=name)
    UserSettings.objects.create(user=user)

    # Side effects after commit ONLY
    def post_commit_actions():
        send_welcome_email.delay(user.id)
        track_signup.delay(user.id, source='web')
        invalidate_cache('signup_count')

    transaction.on_commit(post_commit_actions)

    return user


# If any DB op fails, atomic rolls back AND post_commit_actions never run
"""


# ==========================================================================
# 14. SAGA PATTERN (cross-service / cross-DB)
# ==========================================================================

class SagaStep:
    def __init__(self, action, compensation):
        self.action = action
        self.compensation = compensation


def run_saga(steps):
    """Execute steps; compensate (reverse) on failure."""
    completed = []
    try:
        for step in steps:
            step.action()
            completed.append(step)
    except Exception as e:
        log.error(f'Saga failed: {e}, compensating...')
        for step in reversed(completed):
            try:
                step.compensation()
            except Exception as comp_err:
                log.exception(f'Compensation failed: {comp_err}')
        raise


# Example
"""
def signup_with_external_services(email):
    user_holder = {}

    def create_user():
        user_holder['user'] = User.objects.create(email=email)

    def delete_user():
        User.objects.filter(pk=user_holder['user'].pk).delete()

    def create_stripe_customer():
        cust = stripe.Customer.create(email=email)
        user_holder['user'].stripe_id = cust.id
        user_holder['user'].save()

    def delete_stripe_customer():
        stripe.Customer.delete(user_holder['user'].stripe_id)

    def send_welcome_email():
        # ... send

    def revoke_welcome_email():
        pass  # can't unsend

    run_saga([
        SagaStep(create_user, delete_user),
        SagaStep(create_stripe_customer, delete_stripe_customer),
        SagaStep(send_welcome_email, revoke_welcome_email),
    ])
"""
