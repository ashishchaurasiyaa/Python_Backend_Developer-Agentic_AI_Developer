# Celery Advanced — Signals, Custom Tasks, Worker Modes, Django Integration

## Quick Concepts
- **Celery signals** = task lifecycle hooks (prerun, postrun, failure, success)
- **Custom base class** = shared logic for all tasks (logging, DB session, metrics)
- **Task locking** = prevent same task running twice simultaneously (Redis lock)
- **prefork** = default — multiprocessing (CPU-bound tasks)
- **eventlet/gevent** = cooperative threading (I/O-bound tasks, more concurrency)
- **transaction.on_commit** = Celery task dispatch AFTER transaction commits (critical!)
- **Dead Letter Queue** = failed tasks routed to separate queue for inspection
- **ETA / countdown** = delay task execution by time
- **Revocation** = cancel a pending/running task

---

## Interview Questions & Answers

### Q1: Celery signals kya hain? Kab use karte hain?

**Answer:**
```python
from celery.signals import (
    task_prerun,
    task_postrun,
    task_success,
    task_failure,
    task_retry,
    task_revoked,
    worker_ready,
    worker_shutdown,
)
import time
import logging

logger = logging.getLogger(__name__)

# ─── task_prerun — task start hone se pehle ───
@task_prerun.connect
def task_prerun_handler(task_id, task, args, kwargs, **extra):
    """Har task ke liye timer start karo."""
    task.start_time = time.time()
    logger.info(f"Task starting: {task.name}[{task_id}]")

# ─── task_postrun — task complete hone ke baad ───
@task_postrun.connect
def task_postrun_handler(task_id, task, args, kwargs, retval, state, **extra):
    """Task duration log karo."""
    duration = time.time() - getattr(task, "start_time", time.time())
    logger.info(f"Task done: {task.name}[{task_id}] state={state} duration={duration:.2f}s")

# ─── task_failure — task fail hone par ───
@task_failure.connect
def task_failure_handler(task_id, exception, args, kwargs, traceback, einfo, **extra):
    """Failed tasks ko Sentry/alerting mein report karo."""
    logger.error(f"Task FAILED: {task_id} | Exception: {exception}")
    # sentry_sdk.capture_exception(exception)
    # alert_on_call_team(task_id, str(exception))

# ─── task_success ───
@task_success.connect
def task_success_handler(sender, result, **extra):
    logger.debug(f"Task SUCCESS: {sender.name} result={result}")

# ─── task_retry ───
@task_retry.connect
def task_retry_handler(request, reason, einfo, **extra):
    logger.warning(f"Task RETRY: {request.id} reason={reason}")

# ─── worker_ready — worker start hone ke baad ───
@worker_ready.connect
def worker_ready_handler(sender, **extra):
    """DB connection warm karo, caches load karo."""
    logger.info(f"Worker ready: {sender}")

# ─── worker_shutdown — worker gracefully shutdown ───
@worker_shutdown.connect
def worker_shutdown_handler(sender, **extra):
    """Cleanup: close DB connections, flush metrics."""
    logger.info("Worker shutting down — cleaning up")

# ─── INTERVIEW: Signals kab use karte hain? ───
# task_prerun:    metrics/tracing start karo (timer, span)
# task_postrun:   duration metrics send karo (Prometheus)
# task_failure:   alert (Sentry, PagerDuty)
# worker_ready:   app state initialize karo
# worker_shutdown: graceful cleanup
```

---

### Q2: Custom Task base class kab banate hain?

**Answer:**
```python
from celery import Task
from celery.utils.log import get_task_logger
import time

logger = get_task_logger(__name__)

class BaseTask(Task):
    """
    INTERVIEW: Custom base class kyu?
    Common logic ek jagah — logging, metrics, error handling
    All tasks inherit automatically — DRY principle
    """
    abstract = True   # directly instantiate mat karo

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """Override — task fail hone par call hota hai."""
        logger.error(
            f"Task failed: {self.name}[{task_id}]",
            extra={"exception": str(exc), "args": args}
        )
        super().on_failure(exc, task_id, args, kwargs, einfo)

    def on_retry(self, exc, task_id, args, kwargs, einfo):
        logger.warning(f"Task retry: {self.name}[{task_id}] attempt={self.request.retries}")
        super().on_retry(exc, task_id, args, kwargs, einfo)

    def on_success(self, retval, task_id, args, kwargs):
        logger.info(f"Task success: {self.name}[{task_id}]")
        super().on_success(retval, task_id, args, kwargs)

    def __call__(self, *args, **kwargs):
        """Wrap task execution with timing."""
        start = time.time()
        try:
            result = super().__call__(*args, **kwargs)
            duration = time.time() - start
            # metrics.histogram("task.duration", duration, tags={"task": self.name})
            return result
        except Exception:
            duration = time.time() - start
            # metrics.increment("task.failure", tags={"task": self.name})
            raise


# ─── Database session injecting base task ───
class DatabaseTask(BaseTask):
    """Task with SQLAlchemy session lifecycle."""
    abstract = True
    _session = None

    @property
    def session(self):
        if self._session is None:
            from app.database import SessionLocal
            self._session = SessionLocal()
        return self._session

    def after_return(self, status, retval, task_id, args, kwargs, einfo):
        """Close session after task completes."""
        if self._session is not None:
            self._session.close()
            self._session = None
        super().after_return(status, retval, task_id, args, kwargs, einfo)


# ─── Usage ───
@celery_app.task(base=DatabaseTask, bind=True, max_retries=3)
def sync_user_data(self, user_id: int):
    user = self.session.query(User).get(user_id)
    # ... process
    self.session.commit()
```

---

### Q3: Task locking — duplicate task prevention kaise karte hain?

**Answer:**
```python
import redis
from functools import wraps
from celery import shared_task

redis_client = redis.Redis(host="localhost", port=6379, db=0)

def task_lock(timeout: int = 60 * 60):
    """
    INTERVIEW: Duplicate task problem kya hai?
    Celery Beat same task multiple baar dispatch kar sakta hai agar:
    - Worker crash ho → task re-queued → duplicate run
    - Beat scheduler restart → tasks re-fired

    Solution: distributed lock — Redis mein lock lo before execution
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Unique lock key for this task + args
            lock_key = f"celery_lock:{func.__name__}:{args}:{kwargs}"
            lock = redis_client.lock(lock_key, timeout=timeout)

            acquired = lock.acquire(blocking=False)
            if not acquired:
                # Already running — skip this execution
                import logging
                logging.getLogger(__name__).info(
                    f"Task {func.__name__} already running, skipping"
                )
                return None

            try:
                return func(*args, **kwargs)
            finally:
                try:
                    lock.release()
                except Exception:
                    pass  # lock may have expired

        return wrapper
    return decorator


# Usage
@shared_task
@task_lock(timeout=300)   # max 5 minutes
def generate_daily_report():
    """Only one instance runs at a time — even with multiple workers."""
    # ... expensive report generation
    pass


# ─── Alternative: task_lock as Celery base class ───
class SingletonTask(Task):
    """Task that only runs one instance at a time."""
    abstract = True

    def __call__(self, *args, **kwargs):
        key = f"singleton:{self.name}"
        acquired = redis_client.set(key, "1", nx=True, ex=self.timeout)
        if not acquired:
            return {"status": "skipped", "reason": "already_running"}
        try:
            return super().__call__(*args, **kwargs)
        finally:
            redis_client.delete(key)

    @property
    def timeout(self):
        return getattr(self, "_lock_timeout", 3600)


@celery_app.task(base=SingletonTask, _lock_timeout=600)
def expensive_sync():
    pass
```

---

### Q4: Worker concurrency modes — prefork vs eventlet vs gevent?

**Answer:**
```
─── prefork (default) ───
  Multiprocessing — each worker = OS process
  
  Best for: CPU-bound tasks
    Image processing, PDF generation, ML inference
    Tasks that use GIL (NumPy, pandas)
  
  Start:
    celery -A app worker --concurrency=4
    # 4 parallel processes
    # Memory: 4 × process_size (50-200MB each)

─── eventlet (greenlets) ───
  Cooperative threading — monkey-patching
  
  Best for: I/O-bound tasks
    HTTP requests, DB queries, Redis calls, S3 uploads
    100s of concurrent I/O operations with low memory
  
  Install: pip install eventlet
  Start:
    celery -A app worker --pool=eventlet --concurrency=100
    # 100 greenlets — very low memory overhead
  
  CRITICAL: monkey-patch karo BEFORE imports
    import eventlet
    eventlet.monkey_patch()
    from celery import Celery   # AFTER monkey_patch

─── gevent (greenlets) ───
  Similar to eventlet, often preferred
  
  Best for: same as eventlet — I/O bound
  
  Install: pip install gevent
  Start:
    celery -A app worker --pool=gevent --concurrency=100

─── solo (single process) ───
  No concurrency — 1 task at a time
  
  Best for: debugging, development, tasks that can't be parallel
  
  Start:
    celery -A app worker --pool=solo

─── INTERVIEW: Kab kaunsa? ───
  API calls / email sending / file upload → eventlet/gevent (100+ concurrent)
  Image processing / ML inference        → prefork (4-8 processes)
  Heavy CPU (video encoding)             → prefork + 1 worker per core
  Development / debug                    → solo

─── Production Docker Compose example ───
  services:
    worker-cpu:
      command: celery -A app worker -Q images,reports --concurrency=4
      # prefork default — CPU tasks

    worker-io:
      command: celery -A app worker -Q emails,webhooks --pool=gevent --concurrency=50
      # gevent — I/O tasks — 50 concurrent with low memory
```

---

### Q5: Django + Celery — transaction.on_commit kyu zaroori hai?

**Answer:**
```python
# ─── PROBLEM: task dispatch before commit ───
# BAD — classic mistake!
from django.db import transaction

def create_user(email: str):
    with transaction.atomic():
        user = User.objects.create(email=email)
        # WRONG: Task dispatched INSIDE transaction
        # If transaction rolls back → task already sent!
        # Worker runs task, tries to find user → NOT FOUND!
        send_welcome_email.delay(user.id)

# ─── SOLUTION: transaction.on_commit ───
def create_user_correct(email: str):
    with transaction.atomic():
        user = User.objects.create(email=email)
        # CORRECT: Task fires ONLY after transaction successfully commits
        transaction.on_commit(
            lambda: send_welcome_email.delay(user.id)
        )

# ─── Django signal mein ───
from django.db.models.signals import post_save
from django.dispatch import receiver

@receiver(post_save, sender=User)
def user_created_handler(sender, instance, created, **kwargs):
    if created:
        # WRONG (common mistake):
        # generate_profile_image.delay(instance.id)

        # CORRECT:
        transaction.on_commit(
            lambda: generate_profile_image.delay(instance.id)
        )

# ─── FastAPI / SQLAlchemy equivalent ───
# No ORM transaction.on_commit equivalent
# Pattern: dispatch task AFTER session.commit()

async def create_user_fastapi(session: AsyncSession, email: str):
    user = User(email=email)
    session.add(user)
    await session.commit()
    # Now safe to dispatch — user is in DB
    send_welcome_email.delay(user.id)
    return user

# ─── INTERVIEW: Celery task aur DB transaction sync kaise karo? ───
# 1. Django: transaction.on_commit(lambda: task.delay(id))
# 2. FastAPI: dispatch AFTER await session.commit()
# 3. Always pass DB ID (not object) — worker gets fresh DB state
```

---

### Q6: Dead Letter Queue — failed tasks handle kaise karte hain?

**Answer:**
```python
# ─── Dead Letter Queue (DLQ) pattern ───
# Tasks that exhausted all retries → special queue for inspection

# celery_app.py
from kombu import Queue, Exchange

dead_letter_exchange = Exchange("dead_letters", type="direct")

celery_app.conf.task_queues = (
    Queue("default"),
    Queue("emails"),
    Queue("dead_letters",
          exchange=dead_letter_exchange,
          routing_key="dead_letters"),
)

# ─── Task that sends to DLQ on final failure ───
from celery import shared_task, current_app

@shared_task(
    bind=True,
    max_retries=3,
    retry_backoff=True,
    acks_late=True,
)
def send_invoice(self, invoice_id: int):
    try:
        invoice_service.send(invoice_id)
    except Exception as exc:
        if self.request.retries >= self.max_retries - 1:
            # Last retry — send to DLQ with context
            current_app.send_task(
                "app.tasks.handle_dead_letter",
                args=[{
                    "task_name": self.name,
                    "args": [invoice_id],
                    "exception": str(exc),
                    "retries": self.request.retries,
                }],
                queue="dead_letters",
            )
        raise self.retry(exc=exc)


@shared_task(queue="dead_letters")
def handle_dead_letter(task_info: dict):
    """Process permanently failed tasks — alert, store, manual review."""
    import logging
    logger = logging.getLogger(__name__)
    logger.critical(
        f"DEAD LETTER: {task_info['task_name']} failed after {task_info['retries']} retries"
    )
    # Store in DB for manual review
    FailedTask.objects.create(
        task_name=task_info["task_name"],
        args=task_info["args"],
        exception=task_info["exception"],
    )
    # Alert operations team
    # send_pagerduty_alert(task_info)


# ─── RabbitMQ built-in DLQ ───
# RabbitMQ has native DLQ via x-dead-letter-exchange
# Queue("emails",
#       queue_arguments={
#           "x-dead-letter-exchange": "dead_letters",
#           "x-message-ttl": 86400000,  # 24 hours
#       })
```

---

### Q7: Task ETA, countdown, revocation?

**Answer:**
```python
from celery.result import AsyncResult

# ─── countdown — N seconds baad run karo ───
send_reminder.apply_async(args=[user_id], countdown=3600)  # 1 hour baad

# ─── ETA — specific time pe run karo ───
from datetime import datetime, timedelta, timezone

run_at = datetime(2024, 3, 1, 9, 0, tzinfo=timezone.utc)  # March 1 at 9 AM UTC
generate_monthly_report.apply_async(eta=run_at)

# ─── expires — deadline ke baad mat run karo ───
send_flash_sale_email.apply_async(
    args=[user_id],
    expires=datetime.now(timezone.utc) + timedelta(hours=2),  # 2 hour window
)

# ─── Revocation — pending task cancel karo ───
task = send_email.delay("user@test.com", "Hi", "Body")
task_id = task.id

# Cancel karo (if not yet started)
celery_app.control.revoke(task_id, terminate=False)

# Force terminate even if running
celery_app.control.revoke(task_id, terminate=True, signal="SIGTERM")

# Multiple tasks revoke
celery_app.control.revoke([task_id_1, task_id_2, task_id_3])

# ─── Check status ───
result = AsyncResult(task_id)
print(result.status)    # PENDING, STARTED, SUCCESS, FAILURE, REVOKED, RETRY
print(result.ready())   # True if done (success or failure)
print(result.successful())
print(result.failed())

if result.ready():
    print(result.get())  # actual return value

# ─── Forget result (free backend memory) ───
result.forget()
```

---

## Summary

| Pattern | When to Use |
|---------|-------------|
| Signals | Cross-cutting: metrics, logging, alerting |
| Custom base class | Shared behavior: DB session, error handling |
| Task locking | Prevent duplicate: Celery Beat tasks, cron jobs |
| prefork | CPU-bound: image/video/ML |
| gevent/eventlet | I/O-bound: emails, HTTP calls, file uploads |
| transaction.on_commit | Django: always dispatch AFTER transaction commits |
| Dead Letter Queue | Failed tasks: inspect, alert, manual recovery |
| countdown / ETA | Delayed execution: reminders, scheduled jobs |
| Revocation | Cancel pending: order cancellation, user logout |

| Worker command | Mode | Use Case |
|---------------|------|---------|
| `--pool=prefork --concurrency=4` | Multiprocess | CPU-bound |
| `--pool=gevent --concurrency=100` | Greenlets | I/O-bound |
| `--pool=solo` | Single | Debug |
| `-Q emails --concurrency=10` | Queue-specific | Separate scaling |
| `--beat` | + Scheduler | Beat in same process (dev only) |
