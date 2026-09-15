# Celery + Django — Production Integration

## Why It Matters

Celery = Django's async task system. Critical for:
- **Email sending** (don't block request)
- **PDF/image processing**
- **Scheduled jobs** (Celery Beat)
- **External API calls**
- **Bulk operations** (chunked tasks)

Senior interview: "Long-running task in Django request — how to handle?" → Celery task + result polling/webhook.

---

## Core Concepts

### Setup

```python
# pip install celery[redis] django-celery-beat django-celery-results


# config/celery.py
import os
from celery import Celery


os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')


app = Celery('myapp')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()


@app.task(bind=True)
def debug_task(self):
    print(f'Request: {self.request!r}')
```

```python
# config/__init__.py
from .celery import app as celery_app


__all__ = ('celery_app',)
```

```python
# settings.py
CELERY_BROKER_URL = 'redis://redis:6379/1'
CELERY_RESULT_BACKEND = 'redis://redis:6379/2'

CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = 'UTC'

CELERY_TASK_ALWAYS_EAGER = False   # True in tests for sync execution

CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = 300   # 5 min hard
CELERY_TASK_SOFT_TIME_LIMIT = 240   # 4 min soft (catches SoftTimeLimitExceeded)

# For django-celery-beat
INSTALLED_APPS += ['django_celery_beat', 'django_celery_results']
CELERY_BEAT_SCHEDULER = 'django_celery_beat.schedulers:DatabaseScheduler'
```

### Defining Tasks

```python
# myapp/tasks.py
from celery import shared_task
from celery.exceptions import SoftTimeLimitExceeded


@shared_task
def send_welcome_email(user_id):
    from django.contrib.auth import get_user_model
    User = get_user_model()
    user = User.objects.get(pk=user_id)
    # ... send email
    return f'Email sent to {user.email}'


@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    retry_kwargs={'max_retries': 5, 'countdown': 60},
    retry_backoff=True,         # exponential
    retry_backoff_max=600,      # cap at 10 min
    retry_jitter=True,
)
def fetch_external_data(self, url):
    import httpx
    try:
        resp = httpx.get(url, timeout=10)
        resp.raise_for_status()
        return resp.json()
    except SoftTimeLimitExceeded:
        # Cleanup before hard kill
        raise
```

### Dispatching Tasks

```python
# views.py
from .tasks import send_welcome_email


def signup(request):
    user = User.objects.create(...)

    # Fire and forget
    send_welcome_email.delay(user.id)

    # Or with options
    send_welcome_email.apply_async(
        args=[user.id],
        countdown=60,         # delay 60s
        expires=300,          # expire after 5 min if not picked up
        priority=9,           # higher priority (broker-dependent)
        queue='emails',       # specific queue
    )

    return JsonResponse({'status': 'ok'})
```

### Returning Results

```python
# Wait for result (rarely good idea in views)
result = send_welcome_email.delay(user.id)
result.get(timeout=10)   # BLOCKS — bad in request


# Better: poll later
result.id   # task UUID
result.state   # PENDING, STARTED, SUCCESS, FAILURE
result.result  # actual return value


# Use django-celery-results for DB-stored results
from django_celery_results.models import TaskResult


task_result = TaskResult.objects.get(task_id=result.id)
```

### Periodic Tasks (Celery Beat)

```python
# Static schedule in settings (or via admin if using django-celery-beat)
from celery.schedules import crontab


CELERY_BEAT_SCHEDULE = {
    'daily-reports': {
        'task': 'reports.tasks.generate_daily_report',
        'schedule': crontab(hour=6, minute=0),   # daily 6 AM
    },
    'cleanup-sessions': {
        'task': 'core.tasks.cleanup_expired_sessions',
        'schedule': crontab(hour=3, minute=0, day_of_week=0),   # weekly Sun 3 AM
    },
    'fetch-stock-prices': {
        'task': 'market.tasks.fetch_prices',
        'schedule': 60.0,   # every 60s
    },
}
```

### Beat with Database Scheduler (admin-managed)

```python
# settings.py
CELERY_BEAT_SCHEDULER = 'django_celery_beat.schedulers:DatabaseScheduler'


# Migrations
python manage.py migrate django_celery_beat


# Now create/edit schedules in Django admin
# /admin/django_celery_beat/periodictask/
```

### Task Composition (Canvas)

```python
from celery import group, chain, chord


# Chain — sequential, output of one is input to next
chain(
    fetch_data.s(url),
    process_data.s(),
    save_result.s(),
).apply_async()


# Group — parallel
group(
    process_image.s(image_id)
    for image_id in image_ids
).apply_async()


# Chord — group then callback
chord(
    group(fetch_url.s(url) for url in urls),
    aggregate_results.s(),
).apply_async()
```

### Idempotent Tasks

```python
@shared_task
def charge_customer(order_id):
    from blog.models import Order

    order = Order.objects.select_for_update().get(pk=order_id)

    if order.status == 'paid':
        # Already processed — safe to ignore
        return 'already_paid'

    # Charge
    result = stripe.Charge.create(...)
    order.status = 'paid'
    order.stripe_charge_id = result.id
    order.save()
    return 'paid'
```

### Task Routing (Multiple Queues)

```python
# settings.py
CELERY_TASK_ROUTES = {
    'emails.tasks.*': {'queue': 'emails'},
    'reports.tasks.*': {'queue': 'reports'},
    'ai.tasks.*': {'queue': 'ai_heavy'},
    '*': {'queue': 'default'},
}


# Per-task
@shared_task(queue='priority_high')
def urgent_task():
    ...


# Worker for specific queue
# celery -A myapp worker -Q emails,reports -l info
# celery -A myapp worker -Q ai_heavy -c 2 -l info   # only 2 workers for heavy
```

### Worker Configuration

```bash
# Concurrency (number of parallel tasks per worker)
celery -A myapp worker -c 8

# Specific queue
celery -A myapp worker -Q emails -c 4

# With autoscale
celery -A myapp worker --autoscale=10,3   # min 3, max 10

# Prefork (default) vs gevent (for I/O bound)
celery -A myapp worker -P gevent -c 100

# Production with supervisor / systemd
```

### Monitoring (Flower)

```bash
pip install flower
celery -A myapp flower --port=5555


# Visit http://localhost:5555
# - Live worker status
# - Task history
# - Broker stats
```

### Sentry Integration

```python
# settings.py
import sentry_sdk
from sentry_sdk.integrations.celery import CeleryIntegration


sentry_sdk.init(
    dsn=os.environ['SENTRY_DSN'],
    integrations=[
        DjangoIntegration(),
        CeleryIntegration(),
    ],
)


# Task failures auto-reported to Sentry
```

### Testing

```python
# settings/test.py
CELERY_TASK_ALWAYS_EAGER = True   # synchronous execution
CELERY_TASK_EAGER_PROPAGATES = True


# Or use task_always_eager fixture in pytest
@pytest.fixture(autouse=True)
def celery_eager(settings):
    settings.CELERY_TASK_ALWAYS_EAGER = True
    settings.CELERY_TASK_EAGER_PROPAGATES = True


def test_signup_sends_email():
    user = User.objects.create(...)
    # send_welcome_email.delay() runs SYNCHRONOUSLY
    assert mail.outbox[0].to == [user.email]
```

---

## Common Pitfalls

### 1. Long Task in Request

```python
def view(request):
    send_emails_to_10000_users()   # 10 min — request times out
```

Always dispatch via Celery for > 1 second tasks.

### 2. Passing Django Objects to Task

```python
send_email.delay(user)   # user serialized as JSON — issues with FKs
```

Pass `user.id` (primitive). Task fetches fresh from DB.

### 3. No Retry Limit

```python
@shared_task(autoretry_for=(Exception,))   # retries FOREVER
def task():
    ...
```

Always set `max_retries`.

### 4. Forgetting `bind=True` for `self.retry`

```python
@shared_task
def task():
    self.retry()   # AttributeError
```

Must be `@shared_task(bind=True)` to use `self`.

### 5. Task Doing DB Reads with Stale Data

```python
@shared_task
def process(order_id):
    order = Order.objects.get(pk=order_id)
    # Task runs 5 min later — order state may have changed
```

Re-validate state, use `select_for_update` if needed.

### 6. ALWAYS_EAGER in Prod

```python
CELERY_TASK_ALWAYS_EAGER = True   # blocks request — defeats purpose
```

Only in tests.

### 7. Beat Schedule Not Loaded

```bash
celery -A myapp worker   # missing --beat
celery -A myapp beat     # separate process needed
```

Run beat separately. Or `--beat -B` to combine (only for single worker dev).

### 8. Result Backend Disk Bloat

`CELERY_RESULT_BACKEND` stores task results. Without cleanup → infinite growth.

```python
CELERY_RESULT_EXPIRES = 3600   # 1 hour
# Or use redis with maxmemory + LRU
```

---

## Interview Q&A

**Q1:** Celery in Django setup steps?
**A:** (1) Install celery + redis. (2) Create `config/celery.py` with Celery app. (3) Import in `__init__.py`. (4) Configure CELERY_* settings. (5) Create tasks with `@shared_task`. (6) Run worker: `celery -A config worker -l info`. (7) Beat for periodic: `celery -A config beat`. (8) Optional: Flower for monitoring.

**Q2:** Task retry strategy?
**A:** `autoretry_for=(SpecificException,)` + `retry_backoff=True` (exponential) + `retry_jitter=True` (randomize) + `max_retries=5`. Don't retry on bad input errors (ValueError) — only transient. Set `retry_backoff_max` cap to prevent absurd delays.

**Q3:** Idempotent task design?
**A:** Check current state before mutating. Example: `if order.status == 'paid': return` — second run no-op. Use unique constraint at DB level for true protection. Or store idempotency key in Redis: `SETNX task:idempotency:<key>` — skip if already set.

**Q4:** Multiple workers + queues organization?
**A:** Route tasks by criticality / resource needs. `emails` queue (lightweight, many workers), `ai_heavy` queue (few workers, GPU). `CELERY_TASK_ROUTES` maps task names to queues. Each worker subscribes to specific queues: `celery worker -Q queue1,queue2`.

**Q5:** Beat (periodic) vs cron?
**A:** Cron: OS-level, simple, single host. Beat: Celery-aware, in-app scheduling, retries via task system, observable in Flower, distributed (one beat instance + workers anywhere). For Django apps with tasks: Beat. For OS-level scripts: cron.

**Q6:** Task chain failure handling?
**A:** Chain stops at first failure. Use `link_error` callback. Or catch in task, raise specific error. For complex flows: workflows via `chord` with error callbacks. Sentry catches exceptions automatically.

**Q7:** Result backend kab use, kab nahi?
**A:** Use: when you need to track task status/result, retrieve return value, or chain results. Don't use: fire-and-forget tasks (waste of storage). Set `task.ignore_result = True` to skip storing.

**Q8:** Celery vs RQ vs Dramatiq vs Huey?
**A:** Celery: most mature, complex setup, scales massively. RQ: simpler, Redis-only, smaller. Dramatiq: middle ground, modern API. Huey: lightweight, SQLite/Redis. For Django at scale: Celery. For simple async: RQ or Huey.

---

## Real-World Use Cases

### 1. Email Sending Async

```python
@shared_task(retry_backoff=True, max_retries=5)
def send_email_async(to, subject, body):
    from django.core.mail import send_mail
    send_mail(subject, body, 'no-reply@example.com', [to])


# In signup view
send_email_async.delay(user.email, 'Welcome', 'Hi...')
```

### 2. Daily Report Generation

```python
@shared_task
def generate_daily_report():
    from django.utils import timezone
    today = timezone.now().date()
    report = Report.objects.create(date=today, status='generating')
    try:
        report.data = compute_report()
        report.status = 'ready'
    except Exception as e:
        report.status = 'failed'
        report.error = str(e)
    report.save()


# Beat schedule
CELERY_BEAT_SCHEDULE = {
    'daily-report': {
        'task': 'reports.tasks.generate_daily_report',
        'schedule': crontab(hour=6),
    },
}
```

### 3. Bulk Notification (Chunked)

```python
@shared_task
def send_bulk_notifications(user_ids):
    # Chunk to avoid mega-task
    chunk_size = 100
    for i in range(0, len(user_ids), chunk_size):
        chunk = user_ids[i:i + chunk_size]
        send_notification_chunk.delay(chunk)


@shared_task(autoretry_for=(Exception,), max_retries=3)
def send_notification_chunk(user_ids):
    for uid in user_ids:
        # ... send
```

---

## References

- [Celery docs](https://docs.celeryq.dev/)
- [Celery with Django](https://docs.celeryq.dev/en/stable/django/first-steps-with-django.html)
- [django-celery-beat](https://django-celery-beat.readthedocs.io/)
- [Flower](https://flower.readthedocs.io/)
