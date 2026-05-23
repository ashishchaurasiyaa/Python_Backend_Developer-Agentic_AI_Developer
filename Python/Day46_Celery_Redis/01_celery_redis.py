"""
Day46 — Celery + Redis Deep Dive
==================================
Level: Intermediate → Advanced
Target: 5 YOE Python Backend Developer Interview

Topics Covered:
  1.  Setup — Celery app, broker=Redis, result_backend=Redis
  2.  Basic Tasks — @app.task, delay(), apply_async(), task states
  3.  Task Options — bind=True, max_retries, countdown, eta, expires
  4.  Retry Pattern — self.retry(), exponential backoff, autoretry_for
  5.  Task Routing — task_routes, queues (high/default/low priority)
  6.  Canvas — chain(), group(), chord(), map()
  7.  Beat Scheduler — beat_schedule, crontab(), periodic tasks
  8.  Monitoring — task signals, custom base class with logging
  9.  Redis Patterns — cache-aside, pub/sub, rate limiting, dist. lock, leaderboard
 10.  Testing — CELERY_TASK_ALWAYS_EAGER, mock for async tasks
"""

# ============================================================
# IMPORTS
# ============================================================
from __future__ import annotations

import json
import logging
import time
import uuid
from datetime import datetime, timedelta, timezone
from functools import wraps
from typing import Any
from unittest.mock import MagicMock, patch

import redis
from celery import Celery, Task, chord, group, chain
from celery.result import AsyncResult
from celery.schedules import crontab
from celery.signals import task_failure, task_postrun, task_prerun, task_retry
from celery.utils.log import get_task_logger

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
task_logger = get_task_logger(__name__)

# ============================================================
# SECTION 1: SETUP — Celery App Configuration
# ============================================================

# Create the Celery application
app = Celery(
    "day46_tasks",                           # App name (used in logs/monitoring)
    broker="redis://localhost:6379/0",       # Broker: Redis DB 0
    backend="redis://localhost:6379/1",      # Result backend: Redis DB 1
    include=["day46_tasks"],                 # Modules to auto-discover tasks from
)

# Full configuration via app.conf.update()
app.conf.update(
    # Serialization
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],

    # Timezone
    timezone="Asia/Kolkata",
    enable_utc=True,

    # Task behavior
    task_track_started=True,       # STARTED state is reported (useful for monitoring)
    task_acks_late=True,           # ACK only after task completes (safer, prevents loss)
    task_reject_on_worker_lost=True,  # Re-queue task if worker dies mid-execution
    worker_prefetch_multiplier=1,  # One task per worker at a time (fair scheduling)

    # Result expiry
    result_expires=3600,           # Results expire after 1 hour

    # Retry defaults
    task_soft_time_limit=300,      # SIGTERM after 5 min (SoftTimeLimitExceeded)
    task_time_limit=360,           # SIGKILL after 6 min (TimeoutError)

    # Beat schedule (defined in Section 7)
    beat_schedule={},              # Populated in Section 7
)

# Direct Redis client for Section 9 patterns
redis_client = redis.Redis(host="localhost", port=6379, db=2, decode_responses=True)

# ============================================================
# SECTION 8: CUSTOM TASK BASE CLASS (define before tasks)
# ============================================================

class LoggedTask(Task):
    """
    Custom base class for all tasks.
    Adds structured logging, timing, and error reporting.
    Inherit via: @app.task(base=LoggedTask)
    """

    abstract = True  # Tell Celery this is a base class, not a runnable task

    def on_success(self, retval: Any, task_id: str, args: tuple, kwargs: dict) -> None:
        task_logger.info(
            "Task SUCCESS | id=%s | task=%s | result=%r",
            task_id, self.name, retval,
        )

    def on_failure(self, exc: Exception, task_id: str, args: tuple, kwargs: dict, einfo: Any) -> None:
        task_logger.error(
            "Task FAILURE | id=%s | task=%s | error=%s: %s",
            task_id, self.name, type(exc).__name__, exc,
        )
        # In production: send alert to Sentry, PagerDuty, Slack, etc.
        # sentry_sdk.capture_exception(exc)

    def on_retry(self, exc: Exception, task_id: str, args: tuple, kwargs: dict, einfo: Any) -> None:
        task_logger.warning(
            "Task RETRY | id=%s | task=%s | attempt=%d | error=%s",
            task_id, self.name, self.request.retries, exc,
        )

    def before_start(self, task_id: str, args: tuple, kwargs: dict) -> None:
        """Called just before task execution begins."""
        self._start_time = time.monotonic()
        task_logger.info("Task STARTED | id=%s | task=%s", task_id, self.name)

    def after_return(self, status: str, retval: Any, task_id: str, args: tuple, kwargs: dict, einfo: Any) -> None:
        """Called after task returns, regardless of success/failure."""
        duration = time.monotonic() - getattr(self, "_start_time", time.monotonic())
        task_logger.info(
            "Task DONE | id=%s | status=%s | duration=%.3fs",
            task_id, status, duration,
        )


# ============================================================
# SECTION 2: BASIC TASKS
# ============================================================

@app.task(base=LoggedTask, bind=True, name="tasks.send_welcome_email")
def send_welcome_email(self: LoggedTask, user_id: int, email: str, name: str) -> dict:
    """
    Basic task: Send welcome email to a new user.
    bind=True gives access to self (the task instance).

    Task States:
      PENDING  — Task queued but not yet picked up
      STARTED  — Worker has picked up the task (requires task_track_started=True)
      SUCCESS  — Task completed successfully
      FAILURE  — Task raised an unhandled exception
      RETRY    — Task is being retried
      REVOKED  — Task was cancelled
    """
    task_logger.info("Sending welcome email to %s <%s>", name, email)
    time.sleep(1)  # Simulate SMTP latency

    # Simulate occasional failure
    import random  # noqa: PLC0415
    if random.random() < 0.1:
        raise ConnectionError("SMTP server unreachable")

    result = {
        "user_id": user_id,
        "email": email,
        "sent_at": datetime.now(timezone.utc).isoformat(),
        "message_id": str(uuid.uuid4()),
    }
    task_logger.info("Welcome email sent: %s", result["message_id"])
    return result


@app.task(name="tasks.process_image")
def process_image(image_path: str, operations: list[str]) -> dict:
    """
    Task: Resize, watermark, or compress an image.
    Demonstrates a CPU-bound background task.
    """
    task_logger.info("Processing image: %s with ops: %s", image_path, operations)
    time.sleep(3)  # Simulate image processing

    return {
        "input": image_path,
        "output": image_path.replace(".", "_processed."),
        "operations_applied": operations,
        "size_kb": 245,
    }


@app.task(name="tasks.generate_report")
def generate_report(report_type: str, user_id: int, date_range: dict) -> dict:
    """
    Task: Generate PDF/CSV report (heavy computation).
    """
    task_logger.info("Generating %s report for user %d", report_type, user_id)
    time.sleep(5)  # Simulate report generation

    return {
        "report_type": report_type,
        "user_id": user_id,
        "file_path": f"/reports/{user_id}/{report_type}_{uuid.uuid4().hex[:8]}.pdf",
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


# --- HOW TO INVOKE TASKS ---

def demo_task_invocation() -> None:
    """Different ways to call Celery tasks."""

    # 1. delay() — shorthand for apply_async() with positional args
    result = send_welcome_email.delay(
        user_id=42,
        email="alice@example.com",
        name="Alice",
    )
    print(f"Task ID: {result.id}")

    # 2. apply_async() — full control
    result = send_welcome_email.apply_async(
        args=[42, "alice@example.com", "Alice"],
        countdown=30,           # Wait 30 seconds before executing
        expires=3600,           # Discard task if not picked up within 1 hour
        queue="high_priority",  # Route to specific queue
        retry=True,
    )

    # 3. Inspect task state
    async_result = AsyncResult(result.id, app=app)
    print(f"State: {async_result.state}")          # PENDING / STARTED / SUCCESS / FAILURE
    print(f"Result: {async_result.result}")        # Return value (if SUCCESS)
    print(f"Info: {async_result.info}")            # Exception (if FAILURE)

    # Check readiness
    if async_result.ready():
        print(f"Done! Result: {async_result.get(timeout=10)}")

    # 4. Revoke (cancel) a task
    async_result.revoke(terminate=True)  # terminate=True sends SIGTERM to worker


# ============================================================
# SECTION 3 & 4: TASK OPTIONS — Retry with Exponential Backoff
# ============================================================

@app.task(
    base=LoggedTask,
    bind=True,
    name="tasks.send_sms",
    max_retries=5,
    default_retry_delay=60,  # Wait 60 seconds before first retry
)
def send_sms(self: LoggedTask, phone: str, message: str) -> dict:
    """
    Manual retry with exponential backoff.
    Backoff: 2^retry_count * base_delay (60, 120, 240, 480, 960 seconds)
    """
    try:
        task_logger.info("Sending SMS to %s: %s", phone, message)
        time.sleep(0.5)

        # Simulate flaky SMS gateway
        import random  # noqa: PLC0415
        if random.random() < 0.4:
            raise IOError("SMS gateway timeout")

        return {"phone": phone, "status": "sent", "retries_used": self.request.retries}

    except IOError as exc:
        retry_count = self.request.retries
        backoff_delay = (2 ** retry_count) * 60  # Exponential backoff
        task_logger.warning(
            "SMS failed (attempt %d/%d). Retrying in %ds",
            retry_count + 1, self.max_retries + 1, backoff_delay,
        )
        raise self.retry(exc=exc, countdown=backoff_delay)


@app.task(
    bind=True,
    name="tasks.call_payment_api",
    autoretry_for=(ConnectionError, TimeoutError),  # Auto-retry on these exceptions
    retry_kwargs={"max_retries": 3, "countdown": 5},
    retry_backoff=True,       # Enable exponential backoff automatically
    retry_backoff_max=600,    # Cap backoff at 10 minutes
    retry_jitter=True,        # Add random jitter to avoid thundering herd
)
def call_payment_api(self: Task, amount: float, user_id: int, idempotency_key: str) -> dict:
    """
    autoretry_for: Celery 4.3+ feature — automatically retries on specified exceptions.
    retry_backoff: Celery 5+ feature — doubles delay on each retry.
    retry_jitter: Adds randomness to prevent multiple workers retrying simultaneously.
    """
    task_logger.info("Calling payment API: user=%d amount=%.2f", user_id, amount)

    # Simulate API call
    time.sleep(0.3)
    return {
        "transaction_id": str(uuid.uuid4()),
        "user_id": user_id,
        "amount": amount,
        "idempotency_key": idempotency_key,
        "status": "charged",
    }


# ============================================================
# SECTION 5: TASK ROUTING
# ============================================================

# Configure named queues and route tasks to them
app.conf.task_routes = {
    "tasks.send_welcome_email": {"queue": "high_priority"},
    "tasks.send_sms": {"queue": "high_priority"},
    "tasks.call_payment_api": {"queue": "high_priority"},
    "tasks.process_image": {"queue": "default"},
    "tasks.generate_report": {"queue": "low_priority"},
}

# To start workers for specific queues:
# $ celery -A day46_tasks worker -Q high_priority --concurrency=4
# $ celery -A day46_tasks worker -Q default --concurrency=8
# $ celery -A day46_tasks worker -Q low_priority --concurrency=2

# Queue declarations (for clarity — Celery creates them automatically)
app.conf.task_queues = {
    "high_priority": {"exchange": "high_priority", "routing_key": "high"},
    "default": {"exchange": "default", "routing_key": "default"},
    "low_priority": {"exchange": "low_priority", "routing_key": "low"},
}

app.conf.task_default_queue = "default"


# ============================================================
# SECTION 6: CANVAS — Workflow Primitives
# ============================================================

@app.task(name="tasks.resize_image")
def resize_image(image_path: str, size: tuple[int, int]) -> str:
    task_logger.info("Resizing %s to %s", image_path, size)
    time.sleep(1)
    return f"{image_path}_resized_{size[0]}x{size[1]}.jpg"


@app.task(name="tasks.add_watermark")
def add_watermark(image_path: str, text: str = "© MyApp") -> str:
    task_logger.info("Adding watermark to %s", image_path)
    time.sleep(0.5)
    return f"{image_path}_watermarked.jpg"


@app.task(name="tasks.upload_to_s3")
def upload_to_s3(image_path: str) -> dict:
    task_logger.info("Uploading %s to S3", image_path)
    time.sleep(2)
    return {"s3_url": f"https://bucket.s3.amazonaws.com/{image_path}", "image_path": image_path}


@app.task(name="tasks.notify_user")
def notify_user(upload_results: list[dict], user_id: int) -> None:
    """Callback for chord — receives list of results from group."""
    task_logger.info("Notifying user %d about %d uploads", user_id, len(upload_results))
    urls = [r["s3_url"] for r in upload_results if isinstance(r, dict)]
    task_logger.info("Uploaded URLs: %s", urls)


@app.task(name="tasks.cleanup_temp")
def cleanup_temp(user_id: int) -> dict:
    task_logger.info("Cleaning up temp files for user %d", user_id)
    return {"status": "cleaned", "user_id": user_id}


@app.task(name="tasks.send_report_email")
def send_report_email(report_path: str, email: str) -> dict:
    task_logger.info("Sending report %s to %s", report_path, email)
    return {"sent": True, "to": email}


def demo_canvas_workflows() -> None:
    """
    Canvas: Celery's workflow composition primitives.
    Think of it as async function composition.
    """
    image_path = "/tmp/photo.jpg"
    user_id = 42

    # -------------------------------------------------------
    # CHAIN: Sequential execution (output of step N → input of step N+1)
    # -------------------------------------------------------
    # resize → watermark → upload (each step receives the output of the previous)
    pipeline = chain(
        resize_image.s(image_path, (800, 600)),   # .s() = signature
        add_watermark.s(),                         # receives resized path
        upload_to_s3.s(),                          # receives watermarked path
    )
    result = pipeline.delay()
    # result.get() → final upload result dict
    print("Chain task ID:", result.id)

    # -------------------------------------------------------
    # GROUP: Parallel execution (same input, multiple workers)
    # -------------------------------------------------------
    # Upload multiple sizes in parallel
    image_sizes = [(1920, 1080), (800, 600), (400, 300), (150, 150)]
    parallel_uploads = group(
        chain(
            resize_image.s(image_path, size),
            upload_to_s3.s(),
        )
        for size in image_sizes
    )
    group_result = parallel_uploads.delay()
    results = group_result.get()  # waits for ALL to complete
    print("Group results:", results)

    # -------------------------------------------------------
    # CHORD: Parallel + Callback (group finishes → callback with all results)
    # -------------------------------------------------------
    # Resize all sizes in parallel, then notify user once ALL are done
    upload_tasks = group(
        chain(
            resize_image.s(image_path, size),
            add_watermark.s(),
            upload_to_s3.s(),
        )
        for size in image_sizes
    )
    # notify_user receives a list of all group results as its first argument
    notification = notify_user.s(user_id)
    workflow = chord(upload_tasks, notification)
    chord_result = workflow.delay()
    print("Chord started:", chord_result.id)

    # -------------------------------------------------------
    # CHAIN + CHORD combined (common real-world pattern)
    # -------------------------------------------------------
    full_pipeline = chain(
        # Step 1: Generate report
        generate_report.s("monthly_sales", user_id, {"start": "2026-01-01", "end": "2026-01-31"}),
        # Step 2: Send report via email (receives report dict from Step 1)
        send_report_email.s("alice@example.com"),
        # Step 3: Cleanup temp files
        cleanup_temp.s(user_id),
    )
    full_pipeline.delay()

    # -------------------------------------------------------
    # MAP: Apply same task to a list of arguments
    # -------------------------------------------------------
    emails = ["a@x.com", "b@x.com", "c@x.com"]
    # task.map() = group of the same task applied to each item
    send_welcome_email.map(
        [(i, email, f"User{i}") for i, email in enumerate(emails, 1)]
    ).delay()


# ============================================================
# SECTION 7: BEAT SCHEDULER — Periodic Tasks
# ============================================================

app.conf.beat_schedule = {
    # Run every day at midnight
    "daily-cleanup": {
        "task": "tasks.cleanup_temp",
        "schedule": crontab(hour=0, minute=0),  # midnight
        "args": (0,),  # user_id=0 = system cleanup
    },

    # Run every Monday at 9 AM
    "weekly-report": {
        "task": "tasks.generate_report",
        "schedule": crontab(hour=9, minute=0, day_of_week=1),  # 1 = Monday
        "kwargs": {
            "report_type": "weekly_summary",
            "user_id": 0,  # 0 = system-wide report
            "date_range": {"start": "auto", "end": "auto"},
        },
    },

    # Run every 5 minutes
    "health-check": {
        "task": "tasks.send_sms",
        "schedule": timedelta(minutes=5),
        "args": ("+910000000000", "Health check ping"),
    },

    # Run every hour at :30
    "hourly-sync": {
        "task": "tasks.process_image",
        "schedule": crontab(minute=30),
        "args": ("/tmp/placeholder.jpg", ["optimize"]),
    },
}

# To start the beat scheduler:
# $ celery -A day46_tasks beat --loglevel=info
# $ celery -A day46_tasks beat -S django_celery_beat.schedulers:DatabaseScheduler  (for DB-backed schedule)

# To start worker + beat together (development only):
# $ celery -A day46_tasks worker --beat --loglevel=info


# ============================================================
# SECTION 8 (continued): MONITORING — Task Signals
# ============================================================

@task_prerun.connect
def on_task_prerun(task_id: str, task: Task, args: tuple, kwargs: dict, **extras: Any) -> None:
    """Fired just before a task starts executing on the worker."""
    task_logger.debug("PRE-RUN | task=%s | id=%s", task.name, task_id)


@task_postrun.connect
def on_task_postrun(
    task_id: str,
    task: Task,
    args: tuple,
    kwargs: dict,
    retval: Any,
    state: str,
    **extras: Any,
) -> None:
    """Fired after a task completes (success or failure)."""
    task_logger.debug("POST-RUN | task=%s | id=%s | state=%s", task.name, task_id, state)


@task_failure.connect
def on_task_failure(
    task_id: str,
    exception: Exception,
    traceback: Any,
    einfo: Any,
    **extras: Any,
) -> None:
    """Fired when a task raises an unhandled exception."""
    task_logger.error(
        "FAILURE SIGNAL | id=%s | error=%s: %s",
        task_id, type(exception).__name__, exception,
    )
    # Integrate with Sentry: sentry_sdk.capture_exception(exception)


@task_retry.connect
def on_task_retry(request: Any, reason: Exception, einfo: Any, **extras: Any) -> None:
    """Fired when a task is about to be retried."""
    task_logger.warning("RETRY SIGNAL | task=%s | reason=%s", request.task, reason)


# ============================================================
# SECTION 9: REDIS PATTERNS (beyond Celery)
# ============================================================

# --- 9a. Cache-Aside Pattern ---

def cache_aside(key: str, ttl: int = 300):
    """
    Decorator implementing Cache-Aside (Lazy Loading) pattern.
    1. Check cache → return if hit
    2. If miss → call function → store in cache → return
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            cached = redis_client.get(key)
            if cached is not None:
                logger.info("Cache HIT for key: %s", key)
                return json.loads(cached)

            logger.info("Cache MISS for key: %s — fetching from DB", key)
            result = func(*args, **kwargs)
            redis_client.setex(key, ttl, json.dumps(result))
            return result
        return wrapper
    return decorator


@cache_aside("user:profile:42", ttl=600)
def get_user_profile(user_id: int) -> dict:
    """Simulate a slow DB call that gets cached."""
    time.sleep(0.5)  # Simulate DB query latency
    return {"id": user_id, "name": "Alice", "email": "alice@example.com"}


def invalidate_cache(pattern: str) -> int:
    """Delete all cache keys matching a pattern."""
    keys = redis_client.keys(pattern)
    if keys:
        return redis_client.delete(*keys)
    return 0


# --- 9b. Pub/Sub --- (async messaging between services)

def redis_publisher(channel: str, message: dict) -> None:
    """Publish an event to a Redis channel."""
    payload = json.dumps(message)
    subscriber_count = redis_client.publish(channel, payload)
    logger.info("Published to %s (%d subscribers): %s", channel, subscriber_count, payload)


def redis_subscriber(channel: str) -> None:
    """
    Subscribe and listen for messages. This is blocking — run in a thread/process.

    Usage:
        Thread(target=redis_subscriber, args=("user.events",), daemon=True).start()
    """
    pubsub = redis_client.pubsub()
    pubsub.subscribe(channel)
    logger.info("Subscribed to channel: %s", channel)

    for message in pubsub.listen():
        if message["type"] == "message":
            data = json.loads(message["data"])
            logger.info("Received on %s: %s", channel, data)
            # Handle the event
            if data.get("event") == "user.registered":
                send_welcome_email.delay(
                    user_id=data["user_id"],
                    email=data["email"],
                    name=data["name"],
                )


def demo_pubsub() -> None:
    """Demo: publish a user registration event."""
    redis_publisher("user.events", {
        "event": "user.registered",
        "user_id": 123,
        "email": "new@example.com",
        "name": "New User",
    })


# --- 9c. Rate Limiting — Sliding Window ---

class SlidingWindowRateLimiter:
    """
    Redis-based sliding window rate limiter.
    Uses sorted sets: key = identifier, score = timestamp, member = unique request ID.

    Allows max_requests per window_seconds.
    """

    def __init__(self, redis_conn: redis.Redis, max_requests: int, window_seconds: int) -> None:
        self.redis = redis_conn
        self.max_requests = max_requests
        self.window_seconds = window_seconds

    def is_allowed(self, identifier: str) -> tuple[bool, int]:
        """
        Returns (is_allowed, remaining_requests).
        Uses MULTI/EXEC pipeline for atomicity.
        """
        key = f"rate_limit:{identifier}"
        now = time.time()
        window_start = now - self.window_seconds

        with self.redis.pipeline() as pipe:
            pipe.zremrangebyscore(key, "-inf", window_start)  # Remove expired entries
            pipe.zadd(key, {str(uuid.uuid4()): now})          # Add current request
            pipe.zcard(key)                                    # Count requests in window
            pipe.expire(key, self.window_seconds)
            results = pipe.execute()

        request_count = results[2]
        remaining = max(0, self.max_requests - request_count)
        allowed = request_count <= self.max_requests

        if not allowed:
            # Undo the zadd — we don't want to count rejected requests
            self.redis.zpopmax(key, 1)

        return allowed, remaining


def rate_limit_demo() -> None:
    limiter = SlidingWindowRateLimiter(redis_client, max_requests=5, window_seconds=60)

    for i in range(8):
        allowed, remaining = limiter.is_allowed("user:42")
        status = "ALLOWED" if allowed else "BLOCKED"
        logger.info("Request %d: %s (remaining: %d)", i + 1, status, remaining)


# --- 9d. Distributed Lock (SET NX PX) ---

class RedisDistributedLock:
    """
    Distributed lock using Redis SET NX PX.
    Prevents multiple workers from executing the same critical section.

    NX = only SET if key does Not eXist
    PX = expiry in milliseconds (prevents deadlock if worker crashes)
    """

    def __init__(self, redis_conn: redis.Redis, lock_key: str, ttl_ms: int = 30_000) -> None:
        self.redis = redis_conn
        self.lock_key = lock_key
        self.ttl_ms = ttl_ms
        self.lock_value = str(uuid.uuid4())  # Unique value to verify ownership

    def acquire(self) -> bool:
        """Returns True if lock acquired, False if already locked."""
        result = self.redis.set(
            self.lock_key,
            self.lock_value,
            nx=True,     # SET only if Not eXists
            px=self.ttl_ms,  # TTL in milliseconds
        )
        return result is True

    def release(self) -> bool:
        """
        Release lock only if we own it (compare-and-delete using Lua script).
        Using a Lua script ensures atomicity — prevents race condition between
        GET (verify ownership) and DEL (release).
        """
        lua_script = """
        if redis.call('GET', KEYS[1]) == ARGV[1] then
            return redis.call('DEL', KEYS[1])
        else
            return 0
        end
        """
        result = self.redis.eval(lua_script, 1, self.lock_key, self.lock_value)
        return result == 1

    def __enter__(self) -> RedisDistributedLock:
        if not self.acquire():
            raise RuntimeError(f"Could not acquire lock: {self.lock_key}")
        return self

    def __exit__(self, *args: Any) -> None:
        self.release()


@app.task(name="tasks.process_monthly_invoice")
def process_monthly_invoice(user_id: int) -> dict:
    """
    Critical section: only one worker should process this at a time per user.
    Uses distributed lock to prevent duplicate processing.
    """
    lock_key = f"lock:invoice:{user_id}"

    try:
        with RedisDistributedLock(redis_client, lock_key, ttl_ms=60_000):
            task_logger.info("Processing invoice for user %d (lock acquired)", user_id)
            time.sleep(2)  # Simulate invoice processing
            return {"user_id": user_id, "invoice_id": str(uuid.uuid4()), "status": "processed"}
    except RuntimeError:
        task_logger.warning("Invoice already being processed for user %d", user_id)
        return {"user_id": user_id, "status": "skipped", "reason": "lock_not_acquired"}


# --- 9e. Leaderboard with Sorted Sets ---

class RedisLeaderboard:
    """
    Real-time leaderboard using Redis Sorted Sets (ZSET).
    ZADD: O(log N)
    ZRANK/ZREVRANK: O(log N)
    ZRANGE/ZREVRANGE: O(log N + M) where M = returned elements
    """

    def __init__(self, redis_conn: redis.Redis, board_name: str) -> None:
        self.redis = redis_conn
        self.key = f"leaderboard:{board_name}"

    def add_score(self, player: str, score: float) -> None:
        """Add or update player's score."""
        self.redis.zadd(self.key, {player: score})

    def increment_score(self, player: str, delta: float) -> float:
        """Increment player score by delta."""
        return self.redis.zincrby(self.key, delta, player)

    def get_rank(self, player: str) -> int | None:
        """Get player's rank (0-indexed, 0 = highest score)."""
        rank = self.redis.zrevrank(self.key, player)
        return rank + 1 if rank is not None else None  # 1-indexed

    def get_top_n(self, n: int = 10) -> list[dict]:
        """Get top N players with scores."""
        results = self.redis.zrevrange(self.key, 0, n - 1, withscores=True)
        return [
            {"rank": i + 1, "player": player, "score": score}
            for i, (player, score) in enumerate(results)
        ]

    def get_around_player(self, player: str, radius: int = 2) -> list[dict]:
        """Get players around a specific player (e.g., 2 above, 2 below)."""
        rank = self.redis.zrevrank(self.key, player)
        if rank is None:
            return []
        start = max(0, rank - radius)
        end = rank + radius
        results = self.redis.zrevrange(self.key, start, end, withscores=True)
        return [
            {"rank": start + i + 1, "player": p, "score": s}
            for i, (p, s) in enumerate(results)
        ]


def demo_leaderboard() -> None:
    board = RedisLeaderboard(redis_client, "monthly_sales")

    # Add scores
    players = [
        ("Alice", 9500.0),
        ("Bob", 12000.0),
        ("Charlie", 8750.0),
        ("Diana", 15000.0),
        ("Eve", 11200.0),
    ]
    for player, score in players:
        board.add_score(player, score)

    # Diana scores a bonus sale
    board.increment_score("Diana", 2500.0)

    # Get top 3
    top_3 = board.get_top_n(3)
    for entry in top_3:
        logger.info("#%d %s: %.0f", entry["rank"], entry["player"], entry["score"])

    # Check Alice's rank
    alice_rank = board.get_rank("Alice")
    logger.info("Alice's rank: #%d", alice_rank)

    # Leaderboard around Alice
    around_alice = board.get_around_player("Alice", radius=2)
    logger.info("Players around Alice: %s", around_alice)


# ============================================================
# SECTION 10: TESTING
# ============================================================

# --- Method 1: CELERY_TASK_ALWAYS_EAGER ---
# With always_eager=True, tasks run synchronously in the same process.
# No broker/worker needed. Good for unit tests.

def get_test_app() -> Celery:
    """Create a Celery app configured for testing."""
    test_app = Celery("test")
    test_app.conf.update(
        task_always_eager=True,      # Run tasks synchronously
        task_eager_propagates=True,  # Propagate exceptions (don't swallow them)
        broker_url="memory://",      # In-memory broker
        result_backend="cache+memory://",
    )
    return test_app


def test_send_welcome_email_task() -> None:
    """Test that the task runs correctly."""
    # Temporarily configure for eager execution
    app.conf.task_always_eager = True
    app.conf.task_eager_propagates = True

    try:
        result = send_welcome_email.delay(
            user_id=1,
            email="test@example.com",
            name="Test User",
        )
        # With always_eager, result is immediately available
        assert result.successful()
        value = result.get()
        assert value["email"] == "test@example.com"
        assert "message_id" in value
        print("test_send_welcome_email_task: PASSED")
    except AssertionError as e:
        print(f"test_send_welcome_email_task: FAILED — {e}")
    finally:
        app.conf.task_always_eager = False


# --- Method 2: Mock the task for fast unit tests ---

def service_that_sends_email(user_id: int, email: str, name: str) -> str:
    """Business logic that triggers an email task."""
    result = send_welcome_email.delay(user_id=user_id, email=email, name=name)
    return result.id


def test_service_calls_task_with_correct_args() -> None:
    """Mock the task to verify it's called with correct arguments."""
    with patch("__main__.send_welcome_email") as mock_task:
        mock_result = MagicMock()
        mock_result.id = "fake-task-id-123"
        mock_task.delay.return_value = mock_result

        task_id = service_that_sends_email(42, "alice@example.com", "Alice")

        mock_task.delay.assert_called_once_with(
            user_id=42,
            email="alice@example.com",
            name="Alice",
        )
        assert task_id == "fake-task-id-123"
        print("test_service_calls_task_with_correct_args: PASSED")


# --- Method 3: Test Redis patterns with fakeredis ---

def test_rate_limiter_with_fakeredis() -> None:
    """Test rate limiter using fakeredis (no real Redis needed)."""
    try:
        import fakeredis  # noqa: PLC0415
        fake_redis = fakeredis.FakeRedis(decode_responses=True)
        limiter = SlidingWindowRateLimiter(fake_redis, max_requests=3, window_seconds=60)

        # First 3 requests should be allowed
        for i in range(3):
            allowed, remaining = limiter.is_allowed("test_user")
            assert allowed, f"Request {i+1} should be allowed"

        # 4th request should be blocked
        allowed, remaining = limiter.is_allowed("test_user")
        assert not allowed, "4th request should be blocked"
        print("test_rate_limiter_with_fakeredis: PASSED")
    except ImportError:
        print("test_rate_limiter_with_fakeredis: SKIPPED (fakeredis not installed)")


def test_distributed_lock() -> None:
    """Test distributed lock acquire/release."""
    try:
        import fakeredis  # noqa: PLC0415
        fake_redis = fakeredis.FakeRedis(decode_responses=True)

        lock1 = RedisDistributedLock(fake_redis, "test:lock", ttl_ms=5000)
        lock2 = RedisDistributedLock(fake_redis, "test:lock", ttl_ms=5000)

        # Lock 1 should acquire
        assert lock1.acquire() is True, "Lock 1 should acquire"
        # Lock 2 should fail (lock is held by lock1)
        assert lock2.acquire() is False, "Lock 2 should fail"
        # Lock 1 releases
        assert lock1.release() is True, "Lock 1 should release"
        # Now lock 2 should acquire
        assert lock2.acquire() is True, "Lock 2 should now acquire"
        lock2.release()
        print("test_distributed_lock: PASSED")
    except ImportError:
        print("test_distributed_lock: SKIPPED (fakeredis not installed)")


# ============================================================
# DEMO RUNNER
# ============================================================

def run_all_demos() -> None:
    """Run all non-Celery demos (Redis patterns, tests)."""
    logger.info("=== Running Redis Demos ===")

    # Rate limiting demo (needs Redis)
    try:
        rate_limit_demo()
    except redis.ConnectionError:
        logger.warning("Redis not running — skipping rate limit demo")

    # Leaderboard demo (needs Redis)
    try:
        demo_leaderboard()
    except redis.ConnectionError:
        logger.warning("Redis not running — skipping leaderboard demo")

    # Tests
    logger.info("=== Running Tests ===")
    test_send_welcome_email_task()
    test_service_calls_task_with_correct_args()
    test_rate_limiter_with_fakeredis()
    test_distributed_lock()


if __name__ == "__main__":
    run_all_demos()

    # To actually run Celery:
    # Start Redis: docker run -p 6379:6379 redis:alpine
    # Start worker: celery -A 01_celery_redis worker --loglevel=info
    # Start beat: celery -A 01_celery_redis beat --loglevel=info
    # Monitor: celery -A 01_celery_redis flower (install: pip install flower)


# ============================================================
# INTERVIEW Q&A (15 Questions)
# ============================================================

"""
=== Celery + Redis Interview Q&A — Senior Level ===

Q1. What is Celery and why is it used instead of Python threads for background jobs?
A1. Celery is a distributed task queue. Unlike threads, tasks run in separate
    worker processes (or machines), are persisted to a broker (Redis/RabbitMQ)
    so they survive app restarts, support retry logic, scheduling, monitoring,
    and horizontal scaling. Threads are in-process, ephemeral, and blocked by
    the GIL for CPU-bound work.

Q2. What is the difference between a broker and a result backend in Celery?
A2. Broker: Message queue (Redis/RabbitMQ) where tasks are enqueued. Workers
    pull from the broker. Required.
    Result backend: Storage (Redis/DB) for task return values and state.
    Optional — only needed if you call result.get() or check task state.
    Use different Redis DBs to avoid mixing messages and results.

Q3. What does task_acks_late=True do and when should you use it?
A3. By default (acks_late=False), the task is acknowledged (removed from queue)
    when the worker receives it. With acks_late=True, it's acknowledged AFTER
    completion. If the worker crashes mid-task, the task goes back to the queue.
    Use for tasks where you can't afford to lose a job (payments, critical emails).
    Risk: If the task is non-idempotent, it may execute twice on crash recovery.

Q4. Explain Celery Canvas: chain, group, and chord.
A4. chain(t1, t2, t3): Sequential — output of t1 is input of t2, etc.
    Think Unix pipe: t1 | t2 | t3.
    group(t1, t2, t3): Parallel — all tasks execute concurrently.
    Result is a GroupResult with all individual results.
    chord(group(...), callback): Parallel + barrier — runs the callback
    once ALL group tasks complete, passing all results as a list.
    Used for fan-out/fan-in patterns (e.g., resize 5 images, then notify).

Q5. How does exponential backoff work in Celery retries?
A5. On each retry, the delay doubles: countdown = base_delay * (2 ^ retry_count).
    Adding jitter (random delta) prevents thundering herd — all workers retrying
    simultaneously overwhelming the downstream service.
    Celery 5+ supports this natively with retry_backoff=True, retry_jitter=True.
    Manually: raise self.retry(exc=exc, countdown=2**self.request.retries * 60)

Q6. What is the N+1 problem in Celery and how do you avoid it?
A6. Not directly an ORM concept here, but a parallel: spawning N individual tasks
    for N items when one bulk task would suffice. Example: calling user.delay()
    in a loop for 1000 users creates 1000 task messages.
    Fix: Use group() for parallel execution, or pass a list to one task that
    handles the batch internally. Reduces broker overhead dramatically.

Q7. How do you monitor Celery tasks in production?
A7. (a) Flower: web UI for real-time monitoring (pip install flower,
        celery flower).
    (b) Celery signals: task_prerun, task_postrun, task_failure — integrate
        with Sentry, Datadog, CloudWatch.
    (c) Custom base Task class with on_success/on_failure hooks.
    (d) Redis Pub/Sub or database for custom dashboards.
    (e) celery inspect active — CLI to see running tasks.

Q8. Explain the Redis Distributed Lock pattern and why a plain SET/GET is unsafe.
A8. A plain GET (check) → DEL (if owned) is a TOCTOU race: between GET and DEL,
    another worker may have acquired the lock. The safe pattern:
    SET key value NX PX ttl — atomic, creates key only if absent, auto-expires.
    Release: Lua script atomically verifies ownership and deletes.
    The TTL prevents deadlock if the lock holder crashes.

Q9. What is the Cache-Aside pattern and what are its trade-offs?
A9. Read: check cache → if miss, read from DB → store in cache → return.
    Write: write to DB → invalidate/update cache.
    Pros: simple, cache only what's read (no wasted memory).
    Cons: cache miss on first access (cold start), potential stale data if
    invalidation is missed, thundering herd on cache expiry under high traffic.
    Mitigation: probabilistic early expiration, request coalescing (single-flight).

Q10. What is the difference between Celery beat and a cron job?
A10. Cron runs on a single machine at OS level — no monitoring, no retry, no
     distributed coordination. Celery beat generates tasks and puts them in the
     broker, where any worker can pick them up. Supports dynamic scheduling
     (DB-backed with django-celery-beat), multiple timezones, and integrates
     with Celery monitoring tools. Beat is still a SPOF — run only one beat
     instance (or use Redbeat for HA).

Q11. How do you implement idempotency in Celery tasks?
A11. Use a unique idempotency_key (from the caller) stored in Redis.
     At task start: check if key exists → if yes, return cached result.
     On success: store result in Redis with TTL. This prevents duplicate
     side effects (double charge, duplicate email) when a task is retried.
     Also ensure your task logic is idempotent at DB level (upsert vs insert).

Q12. What is the worker_prefetch_multiplier and why set it to 1?
A12. Controls how many tasks a worker prefetches from the broker.
     Default is 4 — worker reserves 4 tasks at once. This improves throughput
     but hurts fairness: one slow task blocks 3 others in the buffer.
     Set to 1 for long-running tasks to ensure fair distribution across workers.
     For fast tasks (< 1s), higher values reduce broker round-trip overhead.

Q13. How do you implement a priority queue in Celery?
A13. Define multiple queues (high_priority, default, low_priority) and route
     tasks via task_routes config. Start workers listening to specific queues:
     celery worker -Q high_priority --concurrency=4
     celery worker -Q default --concurrency=8
     celery worker -Q low_priority --concurrency=2
     High priority queue has more dedicated workers — better throughput.
     Not true priority ordering within a queue (use RabbitMQ for that).

Q14. Explain Redis Sorted Sets and their time complexity.
A14. Sorted Sets (ZSET): key → {member: float_score}.
     ZADD: O(log N) — adds/updates member with score.
     ZRANGE/ZREVRANGE: O(log N + M) — get range by rank.
     ZRANGEBYSCORE: O(log N + M) — get members by score range.
     ZRANK/ZREVRANK: O(log N) — get rank of a member.
     Use cases: leaderboards, rate limiting (score=timestamp), task priority
     queues, time-series (score=epoch), autocomplete.

Q15. How do you gracefully shut down Celery workers?
A15. Send SIGTERM: celery multi stop worker1 or kill -TERM <pid>.
     Worker finishes the current task, then exits. No tasks are lost.
     SIGKILL (-9) immediately terminates — current task is lost (re-queued
     if acks_late=True). In Kubernetes: set terminationGracePeriodSeconds
     to a value longer than your longest task, configure preStop hook to
     run celery worker --stop. Always use graceful shutdown in production.
"""
