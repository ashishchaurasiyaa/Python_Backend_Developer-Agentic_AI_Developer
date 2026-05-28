# Django Transactions Deep

## Why It Matters

DB transactions = atomicity guarantee. Django wrappers:
- `transaction.atomic` — block-level
- `ATOMIC_REQUESTS` — per-request
- `on_commit` — hooks after commit
- `set_rollback` — manual rollback
- `select_for_update` — pessimistic lock

Senior interview: "Email send karna hai DB write ke baad — atomic kaise?" → `transaction.on_commit(lambda: ...)`.

---

## Core Concepts

### `transaction.atomic` Decorator / Context Manager

```python
from django.db import transaction


@transaction.atomic
def transfer(from_id, to_id, amount):
    from_acc = Account.objects.select_for_update().get(pk=from_id)
    to_acc = Account.objects.select_for_update().get(pk=to_id)

    from_acc.balance -= amount
    to_acc.balance += amount
    from_acc.save()
    to_acc.save()
    # Auto-commits on return; rollback on exception


# Context manager
def view(request):
    with transaction.atomic():
        # Critical section
        order = Order.objects.create(...)
        Payment.objects.create(order=order)
        # Both committed or both rolled back
```

### Nested Atomic (Savepoints)

```python
@transaction.atomic
def outer():
    Order.objects.create(...)

    try:
        with transaction.atomic():    # creates SAVEPOINT
            Inventory.deduct(...)     # may raise
    except OutOfStock:
        # Savepoint rolled back, outer txn continues
        log_failure()

    # Outer commits Order even if Inventory rolled back
```

Without inner atomic, OutOfStock would roll back Order too.

### Per-Request Transactions

```python
# settings.py
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        # ...
        'ATOMIC_REQUESTS': True,   # wrap every request in transaction
    },
}
```

Pros: views auto-atomic, no need to remember `@atomic`.
Cons: long-running views = long transactions = lock contention.

**Mixed:** `ATOMIC_REQUESTS = False` + manual `@atomic` on specific views.

### `on_commit` Hook

```python
@transaction.atomic
def signup(request):
    user = User.objects.create(...)

    # If we send email here, it fires before commit
    # If transaction rolls back, email was already sent — orphan!

    transaction.on_commit(
        lambda: send_welcome_email.delay(user.id)
    )
    # Lambda only called AFTER successful commit
```

**Critical for:** Celery tasks (don't dispatch tasks referring to data not yet committed), webhooks, side effects.

### `set_rollback`

Mark transaction for rollback without raising:

```python
@transaction.atomic
def process(request):
    if some_condition:
        transaction.set_rollback(True)
        return HttpResponse('Cancelled', status=200)
    # Otherwise, commit happens normally
```

### `select_for_update` (Pessimistic Lock)

```python
@transaction.atomic
def buy_item(user, product_id):
    product = Product.objects.select_for_update().get(pk=product_id)
    # Row locked until transaction commits

    if product.stock <= 0:
        raise OutOfStock()

    product.stock -= 1
    product.save()


# Options
Product.objects.select_for_update(nowait=True)            # fail if locked
Product.objects.select_for_update(skip_locked=True)        # skip locked (queue pattern)
Product.objects.select_for_update(of=('self',))            # lock only this table in JOIN
```

### Isolation Levels per Transaction

```python
from django.db import connection


@transaction.atomic
def serializable_op():
    with connection.cursor() as c:
        c.execute("SET TRANSACTION ISOLATION LEVEL SERIALIZABLE")
    # ... your code
```

Or via DATABASES setting:

```python
DATABASES = {
    'default': {
        'OPTIONS': {
            'isolation_level': psycopg.IsolationLevel.REPEATABLE_READ,
        },
    },
}
```

### Atomic Block Methods

```python
# Inside atomic:
transaction.get_connection().in_atomic_block   # True
transaction.set_rollback(True)                  # mark for rollback
transaction.set_autocommit(False)               # manual control
transaction.on_commit(callback)                  # post-commit hook
transaction.savepoint()                          # explicit savepoint
transaction.savepoint_commit(sid)
transaction.savepoint_rollback(sid)
```

### Async Transactions (Django 5.1+)

```python
async def async_transfer():
    async with transaction.atomic():
        from_acc = await Account.objects.aget(pk=1)
        to_acc = await Account.objects.aget(pk=2)
        # ...
        await from_acc.asave()
        await to_acc.asave()
```

### Database-Specific Behavior

**PostgreSQL:**
- Auto-rollback on any error inside transaction → can't continue using same connection
- Need explicit `try/except` + `set_rollback` to keep using

**MySQL:**
- Some DDL implicitly commits (creates new index, etc.)
- Avoid mixing DDL + transaction.

### Retry on Deadlock

```python
from django.db import OperationalError
import time


def retry_on_deadlock(func, max_retries=3):
    for attempt in range(max_retries):
        try:
            with transaction.atomic():
                return func()
        except OperationalError as e:
            if 'deadlock' in str(e).lower():
                time.sleep(0.05 * 2 ** attempt)
                continue
            raise
    raise OperationalError('Max retries')


def transfer():
    return retry_on_deadlock(_transfer_inner)
```

---

## Common Pitfalls

### 1. Sending Email Inside Transaction

```python
@transaction.atomic
def signup(request):
    user = User.objects.create(...)
    send_mail(...)    # if user.save() fails AFTER → email sent for nothing
```

Use `on_commit`:

```python
transaction.on_commit(lambda: send_mail(...))
```

### 2. Long Transaction Holding Locks

```python
@transaction.atomic
def slow():
    obj = Model.objects.select_for_update().get(pk=1)
    requests.get('https://external.api/...')   # 30s wait → 30s lock
```

External calls outside transaction.

### 3. ATOMIC_REQUESTS + Long Views

Every view = transaction → if any view is slow, all DB connections held → starvation.

```python
# settings — disable ATOMIC_REQUESTS for slow views
ATOMIC_REQUESTS = False
# Use @atomic explicitly on fast critical views
```

Or per-view:

```python
@transaction.non_atomic_requests
def slow_view(request):
    ...
```

### 4. Bulk Operations in Atomic — Memory Spike

```python
@transaction.atomic
def import_all():
    objects = [Model(...) for _ in range(10_000_000)]
    Model.objects.bulk_create(objects)    # huge memory + huge transaction
```

Chunk + separate transactions.

### 5. Forgetting on_commit for Celery

```python
@transaction.atomic
def view():
    obj = Model.objects.create(...)
    my_task.delay(obj.id)   # task may run before commit → obj not in DB
```

Use `on_commit`:

```python
transaction.on_commit(lambda: my_task.delay(obj.id))
```

### 6. Mixing Database Operations on Multiple DBs

`@atomic` is per-database. For multi-DB writes, separate atomic blocks per DB.

```python
@transaction.atomic(using='default')
@transaction.atomic(using='analytics')
def cross_db():
    Model.objects.using('default').create(...)
    Analytics.objects.using('analytics').create(...)
```

These are SEPARATE transactions — no cross-DB atomicity. Use Saga pattern.

### 7. select_for_update on Replica

```python
Model.objects.using('replica').select_for_update()   # ERROR — replicas read-only
```

Always use primary for locking.

### 8. Atomic Decorator on Async View

Django 5.1+ supports `async with transaction.atomic()`. Before that, use sync wrapper.

---

## Interview Q&A

**Q1:** transaction.atomic kaise kaam karta hai?
**A:** Wraps block in DB transaction. Begin → execute → commit on success / rollback on exception. Nested atomic = savepoints. Decorator + context manager forms. Per-request via ATOMIC_REQUESTS. Per-database for multi-DB.

**Q2:** on_commit kab use karte ho?
**A:** Side effects that should only happen IF transaction commits successfully. Examples: Celery tasks (avoid task referring to uncommitted data), webhook calls, cache invalidations, email sends. Without on_commit: side effect happens before commit → if rollback, orphan effect.

**Q3:** select_for_update vs F-expressions?
**A:** select_for_update: pessimistic, locks rows for entire transaction. Other readers wait. Use for multi-step read-modify-write. F-expression update: atomic SQL UPDATE, no separate read. Use for simple atomic ops (counter). F faster but less flexible.

**Q4:** Deadlock retry pattern?
**A:**
```python
for attempt in range(3):
    try:
        with transaction.atomic():
            # work
        return
    except OperationalError as e:
        if 'deadlock' in str(e).lower():
            time.sleep(0.05 * 2 ** attempt)
            continue
        raise
```

**Q5:** ATOMIC_REQUESTS pros/cons?
**A:** Pros: auto-atomic per view, simpler code, hard to forget. Cons: long views = long transactions = lock contention, DB connection held for entire request. Recommendation: False globally, `@atomic` explicitly. Or True with strict timeout.

**Q6:** Cross-DB atomicity Django mein possible?
**A:** No — Django's `atomic` is per-DB. Multi-DB writes need Saga pattern (compensating actions). Or 2PC if DBs support (rare in OLTP). Best: design schema to keep related data on same DB.

**Q7:** Nested atomic — savepoint behavior?
**A:** Inner `atomic` creates SAVEPOINT. If inner raises caught exception, savepoint rolls back but outer continues. If outer raises, both roll back. Allows partial rollback. Common: try inner ops, fall back to alternative on failure.

**Q8:** Long-running transaction problem?
**A:** Holds DB locks → other queries wait. PostgreSQL: prevents VACUUM → bloat. Connection consumed. Strategy: keep transactions short, do external calls outside, batch heavy work. Use `idle_in_transaction_session_timeout` to auto-kill.

---

## Real-World Use Cases

### 1. Order Creation with Email

```python
@transaction.atomic
def create_order(user, cart):
    order = Order.objects.create(user=user, total=cart.total)
    for item in cart.items.all():
        OrderItem.objects.create(order=order, **item)
    cart.delete()

    transaction.on_commit(
        lambda: send_confirmation_email.delay(order.id)
    )

    return order
```

### 2. Inventory Atomic Reservation

```python
@transaction.atomic
def reserve(product_id, qty):
    product = Product.objects.select_for_update().get(pk=product_id)
    if product.stock < qty:
        raise OutOfStock()
    product.stock -= qty
    product.save()
    return Reservation.objects.create(product=product, qty=qty)
```

### 3. Cross-Service Saga (Email + Profile)

```python
def signup(email, name):
    user = User.objects.create(email=email)
    try:
        Profile.objects.create(user=user, name=name)
        SubscriptionService.create_subscription(user.id)   # external
    except Exception:
        # Compensate
        SubscriptionService.cancel_subscription(user.id)
        Profile.objects.filter(user=user).delete()
        user.delete()
        raise
```

---

## References

- [Django Transactions](https://docs.djangoproject.com/en/5.0/topics/db/transactions/)
- [transaction.on_commit](https://docs.djangoproject.com/en/5.0/topics/db/transactions/#django.db.transaction.on_commit)
- [select_for_update](https://docs.djangoproject.com/en/5.0/ref/models/querysets/#select-for-update)
- "Designing Data-Intensive Applications" — Ch 7 (Transactions)
