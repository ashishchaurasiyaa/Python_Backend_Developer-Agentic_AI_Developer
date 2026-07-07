# Celery Task Testing & Idempotency

> **Interview angle:** "How do you unit-test code that calls `.delay()`, without spinning up a real Redis/RabbitMQ broker in CI?" — and the follow-up almost every interviewer asks next: "What happens if that task runs twice?"

---

## 1. Testing Celery Tasks

### The core problem

```python
# Application code
@app.task
def send_welcome_email(user_id):
    user = User.objects.get(id=user_id)
    email_client.send(user.email, template="welcome")
    return {"sent": True}

# In a test, .delay() by default tries to actually publish to a REAL broker
send_welcome_email.delay(user.id)
# In CI with no broker running → connection error, test fails for the
# wrong reason (infra, not logic)
```

### Fix 1 — `task_always_eager` (run synchronously, no broker needed)

```python
# settings.py / test settings
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True   # let exceptions raise instead of swallowing

# Now .delay() runs the task body IMMEDIATELY, in-process, synchronously —
# no broker connection needed at all
```

```python
import pytest
from myapp.tasks import send_welcome_email

@pytest.fixture(autouse=True)
def celery_eager(settings):
    settings.CELERY_TASK_ALWAYS_EAGER = True
    settings.CELERY_TASK_EAGER_PROPAGATES = True

def test_send_welcome_email(user):
    result = send_welcome_email.delay(user.id)
    assert result.get()["sent"] is True
```

**Tradeoff to know:** `task_always_eager` runs the task in the SAME process
synchronously — it does NOT exercise real serialization (pickle/JSON
round-trip), real retry/backoff timing, or real worker concurrency behavior.
It tests your task's **logic**, not the Celery **plumbing** around it. Good
for unit tests; not a substitute for integration tests against a real broker.

### Fix 2 — mock `.delay()`/`.apply_async()` entirely (pure unit test)

```python
from unittest.mock import patch

def test_view_triggers_email_task():
    with patch("myapp.tasks.send_welcome_email.delay") as mock_delay:
        register_user(email="a@b.com")
        mock_delay.assert_called_once_with(user_id=1)
    # Verifies the TASK WAS CALLED with correct args —
    # doesn't execute the task body at all. Use this when testing the
    # CALLER's behavior, not the task's own logic.
```

### Fix 3 — real integration test (pytest-celery / a real worker in CI)

```python
# pytest-celery spins up an actual worker + broker (often via Docker) for
# tests that need to verify REAL async behavior — retry timing, task routing,
# actual serialization. Reserve this tier for the handful of tests that
# specifically need it; it's slower and more infra-dependent than the above.

@pytest.mark.celery(broker="redis://localhost:6379/0")
def test_real_async_execution(celery_worker):
    result = send_welcome_email.delay(1)
    assert result.get(timeout=10)["sent"] is True
```

### The three-tier testing strategy (say this in an interview)

| Tier | Tool | Tests |
|---|---|---|
| Task logic (fast, most tests) | `task_always_eager` | The task body's correctness |
| Caller behavior | `patch(".delay")` mock | That the right task gets triggered with right args |
| Real async plumbing (few, slow) | `pytest-celery` + real broker | Retry timing, routing, actual serialization |

---

## 2. Idempotency — what happens if the task runs twice?

### Why "at-least-once" delivery makes this unavoidable

```
Celery/most brokers guarantee AT-LEAST-ONCE delivery, not exactly-once:

Worker picks up task → starts processing → crashes before ack →
broker redelivers the SAME task to another worker → processed AGAIN

This is normal, expected broker behavior — not a bug to "fix" at the
broker level. Your TASK must tolerate running twice.
```

Same fundamental problem as [Kafka's exactly-once discussion](../../07_Kafka/05_exactly_once_transactions.md)
— the fix pattern is the same idea, applied to Celery tasks instead of stream processing.

### The naive, non-idempotent version

```python
@app.task
def charge_customer(order_id, amount):
    # DANGEROUS — if this task runs twice (retry, redelivery, duplicate
    # trigger from application code), the customer is charged TWICE
    stripe.charges.create(amount=amount, customer=get_customer(order_id))
```

### Fix — idempotency key pattern

```python
@app.task(bind=True, max_retries=3)
def charge_customer(self, order_id, amount, idempotency_key):
    # Stripe (and most payment APIs) natively support idempotency keys —
    # the SAME key sent twice returns the ORIGINAL result, doesn't re-charge
    stripe.charges.create(
        amount=amount,
        customer=get_customer(order_id),
        idempotency_key=idempotency_key,   # e.g., f"order-{order_id}-charge"
    )
```

```python
# For operations without native idempotency-key support (most internal
# DB writes) — check-then-act using a unique constraint as the guard
@app.task
def process_order(order_id):
    # unique constraint on (order_id) in a "processed_orders" table
    # makes a duplicate INSERT fail loudly instead of double-processing
    try:
        ProcessedOrder.objects.create(order_id=order_id)
    except IntegrityError:
        return  # already processed — safe no-op, not an error
    do_the_actual_processing(order_id)
```

```python
# Idempotent-by-design alternative: make the OPERATION itself safe to repeat,
# rather than guarding against repetition
@app.task
def set_user_status_active(user_id):
    # UPDATE ... SET status = 'active' is naturally idempotent —
    # running it twice produces the same end state as running it once.
    # Compare to `balance += amount`, which is NOT naturally idempotent.
    User.objects.filter(id=user_id).update(status="active")
```

### Idempotency vs `acks_late` (a common confusion)

```python
# task_acks_late=True → worker acks the broker AFTER task completes, not
# before starting. This REDUCES lost tasks on worker crash, but INCREASES
# duplicate execution risk (crash after finishing but before ack = redelivery
# of an already-completed task). It does NOT replace the need for
# idempotency — it actually makes duplicate execution MORE likely, trading
# "lost work" risk for "duplicate work" risk.
app.conf.task_acks_late = True
```

**Interview-correct framing:** `acks_late` and idempotency solve
**complementary** problems, not the same one — `acks_late` reduces the
chance of losing a task's work entirely; idempotency makes it SAFE for that
task to occasionally run more than once. Production systems that care about
correctness need both, not either/or.

---

## Interview Q&A

**Q: How do you unit-test a Django view that triggers a Celery task, without a real broker?**
A: `CELERY_TASK_ALWAYS_EAGER = True` in test settings runs `.delay()`
synchronously in-process — no broker needed. For testing just that the view
*triggers* the task correctly (not the task's own logic), mock
`.delay`/`.apply_async` directly instead.

**Q: Why can't you rely on the broker to guarantee exactly-once execution?**
A: Brokers (Redis, RabbitMQ, SQS) guarantee at-least-once delivery as the
practical default — a worker crash after picking up a task but before
acknowledging it causes redelivery. Building on top of at-least-once with an
idempotency key or unique-constraint guard is the standard fix, not fighting
the broker's delivery semantics.

**Q: Does `task_acks_late=True` fix the duplicate-execution problem?**
A: No — it actually makes duplicates MORE likely (ack happens after
completion, so a crash between finishing and acking causes redelivery of
already-done work). It trades lost-work risk for duplicate-work risk;
idempotency is still required regardless.

---

Related: `08_long_running_task_cancellation.md` (cooperative cancellation
also needs idempotent cleanup logic), [../../07_Kafka/05_exactly_once_transactions.md](../../07_Kafka/05_exactly_once_transactions.md)
(same at-least-once-delivery problem, different transport).
