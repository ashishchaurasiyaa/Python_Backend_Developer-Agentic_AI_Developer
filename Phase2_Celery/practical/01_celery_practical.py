"""
Celery — Practical Examples (Complete Runnable Demo)
═══════════════════════════════════════════════════════════════
Install: pip install celery redis flower

Prerequisites:
  docker run -d -p 6379:6379 redis

HOW TO RUN:
  Terminal 1 — Start worker:
    celery -A 01_celery_practical worker --loglevel=info

  Terminal 2 — Run this script (producer):
    python 01_celery_practical.py

  Optional — Flower monitoring:
    celery -A 01_celery_practical flower --port=5555
    → open http://localhost:5555

Topics:
  - Celery app + task definitions
  - Basic task dispatch (delay / apply_async)
  - Retry with exponential backoff
  - Chain, Group, Chord (Canvas)
  - Task status tracking
  - Custom base task
  - Periodic tasks (Beat schedule)
  - Queue routing
  - Distributed lock (singleton task)
  - Rate limiting tasks

INTERVIEW QUICK REFERENCE at bottom.
"""

import time
import random
import logging
from datetime import datetime, timezone, timedelta
from celery import Celery, Task, chain, group, chord, shared_task
from celery.schedules import crontab
from celery.utils.log import get_task_logger

# ═══════════════════════════════════════════════════════════
# SECTION 1: App Setup
# ═══════════════════════════════════════════════════════════

app = Celery(
    "celery_demo",
    broker="redis://localhost:6379/0",
    backend="redis://localhost:6379/1",
)

app.conf.update(
    # Serialization
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],

    # Reliability
    task_acks_late=True,            # ack AFTER task completes (not before)
    worker_prefetch_multiplier=1,   # fetch 1 task at a time (memory safe)
    task_track_started=True,        # STARTED state visible in result backend

    # Result cleanup
    result_expires=3600,            # results expire in 1 hour

    # Timezone
    timezone="Asia/Kolkata",
    enable_utc=True,

    # Queues
    task_default_queue="default",
    task_queues={
        "default":       {"exchange": "default"},
        "emails":        {"exchange": "emails"},
        "high_priority": {"exchange": "high_priority"},
        "reports":       {"exchange": "reports"},
    },
    task_routes={
        "01_celery_practical.send_email":       {"queue": "emails"},
        "01_celery_practical.process_payment":  {"queue": "high_priority"},
        "01_celery_practical.generate_report":  {"queue": "reports"},
    },

    # Beat schedule (periodic tasks)
    beat_schedule={
        "cleanup-every-minute": {
            "task": "01_celery_practical.cleanup_expired_sessions",
            "schedule": 60.0,  # every 60 seconds
        },
        "daily-report-at-7am": {
            "task": "01_celery_practical.generate_report",
            "schedule": crontab(hour=7, minute=0),
            "args": ("daily",),
        },
    },
)

logger = get_task_logger(__name__)


# ═══════════════════════════════════════════════════════════
# SECTION 2: Basic Tasks
# ═══════════════════════════════════════════════════════════

@app.task(name="01_celery_practical.add")
def add(x: int, y: int) -> int:
    """Simple task — add two numbers."""
    logger.info(f"Adding {x} + {y}")
    time.sleep(0.1)  # simulate work
    return x + y


@app.task(
    name="01_celery_practical.send_email",
    bind=True,
    max_retries=3,
    autoretry_for=(ConnectionError,),
    retry_backoff=True,         # exponential: 1s, 2s, 4s, 8s...
    retry_backoff_max=60,       # max 60 seconds wait
    retry_jitter=True,          # random jitter
    queue="emails",
)
def send_email(self, to: str, subject: str, body: str) -> dict:
    """
    INTERVIEW: autoretry_for vs manual self.retry?
    autoretry_for:  automatic retry on specified exceptions
    self.retry():   manual control — conditional retry logic
    """
    logger.info(f"Sending email to {to}: {subject}")

    # Simulate occasional failure
    if random.random() < 0.2:  # 20% failure rate
        raise ConnectionError(f"Email server unavailable (attempt {self.request.retries + 1})")

    time.sleep(0.05)
    return {"status": "sent", "to": to, "subject": subject}


@app.task(
    name="01_celery_practical.process_payment",
    bind=True,
    max_retries=5,
    queue="high_priority",
)
def process_payment(self, order_id: int, amount: float) -> dict:
    logger.info(f"Processing payment: order={order_id} amount=${amount}")
    time.sleep(0.2)
    return {"status": "charged", "order_id": order_id, "amount": amount}


@app.task(name="01_celery_practical.generate_report")
def generate_report(report_type: str = "daily") -> dict:
    logger.info(f"Generating {report_type} report...")
    time.sleep(0.3)
    return {
        "type":       report_type,
        "records":    random.randint(100, 1000),
        "generated_at": datetime.now().isoformat(),
    }


@app.task(name="01_celery_practical.cleanup_expired_sessions")
def cleanup_expired_sessions() -> int:
    """Periodic task — cleans up expired sessions."""
    deleted = random.randint(0, 50)
    logger.info(f"Cleaned up {deleted} expired sessions")
    return deleted


# ═══════════════════════════════════════════════════════════
# SECTION 3: Canvas — Chain, Group, Chord
# ═══════════════════════════════════════════════════════════

@app.task(name="01_celery_practical.resize_image")
def resize_image(image_id: int, width: int = 800) -> dict:
    logger.info(f"Resizing image {image_id} to {width}px")
    time.sleep(0.1)
    return {"image_id": image_id, "width": width, "path": f"/tmp/img_{image_id}_{width}.jpg"}


@app.task(name="01_celery_practical.add_watermark")
def add_watermark(image_data: dict, text: str = "©MyApp") -> dict:
    logger.info(f"Adding watermark to {image_data['path']}")
    time.sleep(0.05)
    return {**image_data, "watermark": text, "path": image_data["path"].replace(".jpg", "_wm.jpg")}


@app.task(name="01_celery_practical.upload_to_s3")
def upload_to_s3(image_data: dict, bucket: str = "my-bucket") -> dict:
    logger.info(f"Uploading {image_data['path']} to s3://{bucket}")
    time.sleep(0.1)
    return {**image_data, "s3_url": f"s3://{bucket}/{image_data['path']}"}


@app.task(name="01_celery_practical.merge_report_results")
def merge_report_results(results: list) -> dict:
    """Chord callback — receives list of all group results."""
    logger.info(f"Merging {len(results)} report results")
    return {
        "merged":   True,
        "count":    len(results),
        "reports":  results,
        "total_records": sum(r.get("records", 0) for r in results if r),
    }


@app.task(name="01_celery_practical.send_report_email")
def send_report_email(merged_data: dict, to: str = "boss@company.com") -> dict:
    logger.info(f"Sending merged report ({merged_data.get('total_records')} records) to {to}")
    return {"sent": True, "to": to}


# ═══════════════════════════════════════════════════════════
# SECTION 4: Custom Base Task
# ═══════════════════════════════════════════════════════════

class TimedTask(Task):
    """
    INTERVIEW: Custom base class kyu?
    Cross-cutting concerns — timing, logging, metrics — ek jagah.
    All tasks inherit just by setting base=TimedTask.
    """
    abstract = True

    def __call__(self, *args, **kwargs):
        start = time.time()
        try:
            result = super().__call__(*args, **kwargs)
            duration = time.time() - start
            logger.info(f"[TIMED] {self.name} completed in {duration:.3f}s")
            return result
        except Exception as e:
            duration = time.time() - start
            logger.error(f"[TIMED] {self.name} FAILED after {duration:.3f}s: {e}")
            raise

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        logger.error(f"[BASE] Task failed: {self.name}[{task_id}] | {exc}")
        super().on_failure(exc, task_id, args, kwargs, einfo)


@app.task(base=TimedTask, name="01_celery_practical.heavy_computation")
def heavy_computation(n: int) -> int:
    """Uses custom base — gets automatic timing."""
    result = sum(i * i for i in range(n))
    return result


# ═══════════════════════════════════════════════════════════
# SECTION 5: Singleton Task (distributed lock)
# ═══════════════════════════════════════════════════════════

import redis as redis_lib

redis_client = redis_lib.Redis(host="localhost", port=6379, db=0, decode_responses=True)


class SingletonTask(Task):
    """
    INTERVIEW: Celery Beat mein duplicate task kaise rokein?
    Multiple workers ya Beat restart pe same task dobara run ho sakta hai.
    Solution: Redis lock — sirf ek instance at a time.
    """
    abstract = True
    lock_timeout = 300  # 5 minutes default

    def __call__(self, *args, **kwargs):
        lock_key = f"singleton_task:{self.name}"
        acquired = redis_client.set(lock_key, "1", nx=True, ex=self.lock_timeout)
        if not acquired:
            logger.info(f"[SINGLETON] {self.name} already running — skipping")
            return {"status": "skipped", "reason": "already_running"}
        try:
            return super().__call__(*args, **kwargs)
        finally:
            redis_client.delete(lock_key)


@app.task(base=SingletonTask, lock_timeout=600, name="01_celery_practical.sync_inventory")
def sync_inventory() -> dict:
    """Only one instance runs at a time across all workers."""
    logger.info("Syncing inventory (singleton)...")
    time.sleep(2)  # simulate long operation
    return {"synced": True, "items": random.randint(100, 500)}


# ═══════════════════════════════════════════════════════════
# SECTION 6: Rate-limited tasks
# ═══════════════════════════════════════════════════════════

@app.task(
    name="01_celery_practical.send_sms",
    rate_limit="10/m",   # max 10 per minute
    queue="emails",
)
def send_sms(phone: str, message: str) -> dict:
    """
    INTERVIEW: rate_limit kya karta hai?
    Worker-level throttle — is worker pe max N tasks/interval
    "10/m" = 10 per minute, "5/s" = 5 per second
    Good for: external API rate limits (SMS, email providers)
    """
    logger.info(f"SMS to {phone}: {message[:30]}...")
    return {"sent": True, "phone": phone}


# ═══════════════════════════════════════════════════════════
# PRODUCER — Run this section to dispatch tasks
# ═══════════════════════════════════════════════════════════

def demo_basic_tasks():
    print("\n--- BASIC TASK DISPATCH ---")

    # delay() — simplest, no options
    task1 = add.delay(10, 20)
    print(f"  add.delay(10, 20) → task_id={task1.id}")

    # apply_async() — full control
    task2 = send_email.apply_async(
        args=["alice@test.com", "Welcome!", "Thank you for joining"],
        countdown=2,          # run 2 seconds from now
        queue="emails",
    )
    print(f"  send_email (2s delay) → task_id={task2.id}")

    # With ETA
    run_at = datetime.now(timezone.utc) + timedelta(seconds=5)
    task3 = generate_report.apply_async(args=["monthly"], eta=run_at)
    print(f"  generate_report (5s ETA) → task_id={task3.id}")

    # Wait for result
    print("\n  Waiting for add result...")
    try:
        result = task1.get(timeout=10)
        print(f"  add(10, 20) = {result}")
        print(f"  Status: {task1.status}")
    except Exception as e:
        print(f"  Error (worker not running?): {e}")

    return task1, task2, task3


def demo_canvas():
    print("\n--- CANVAS: Chain, Group, Chord ---")

    # ─── Chain: sequential pipeline ───
    print("  Chain: resize → watermark → upload")
    image_pipeline = chain(
        resize_image.s(image_id=42, width=800),   # .s() = signature
        add_watermark.s("©MyApp"),
        upload_to_s3.s(bucket="prod-images"),
    )
    chain_task = image_pipeline.delay()
    print(f"  Chain dispatched: {chain_task.id}")

    try:
        result = chain_task.get(timeout=15, propagate=False)
        print(f"  Chain result: {result}")
    except Exception as e:
        print(f"  Chain result error (worker needed): {e}")

    # ─── Group: parallel execution ───
    print("\n  Group: 3 reports in parallel")
    report_group = group(
        generate_report.s("sales"),
        generate_report.s("inventory"),
        generate_report.s("users"),
    )
    group_task = report_group.delay()
    print(f"  Group dispatched: {group_task.id}")

    try:
        results = group_task.get(timeout=15)
        print(f"  Group results ({len(results)} items):")
        for r in results:
            print(f"    {r}")
    except Exception as e:
        print(f"  Group result error (worker needed): {e}")

    # ─── Chord: group + callback ───
    print("\n  Chord: parallel reports → merge → email")
    pipeline = chord(
        group(
            generate_report.s("sales"),
            generate_report.s("inventory"),
        ),
        merge_report_results.s()   # callback receives [result1, result2]
    )
    chord_task = pipeline.delay()
    print(f"  Chord dispatched: {chord_task.id}")

    try:
        merged = chord_task.get(timeout=20)
        print(f"  Chord merged result: {merged}")
    except Exception as e:
        print(f"  Chord result error (worker needed): {e}")


def demo_task_status():
    print("\n--- TASK STATUS TRACKING ---")
    from celery.result import AsyncResult

    task = heavy_computation.delay(10000)
    print(f"  Task dispatched: {task.id}")
    print(f"  Initial status: {task.status}")

    # Poll status
    for _ in range(5):
        time.sleep(0.5)
        status = task.status
        print(f"  Status: {status}")
        if status in ("SUCCESS", "FAILURE"):
            break

    try:
        if task.ready():
            result = task.get(timeout=5)
            print(f"  Result: {result}")
        else:
            print("  Task still pending (worker not running)")
    except Exception as e:
        print(f"  Status check: {e}")

    # Check via AsyncResult (from task_id string — e.g., from HTTP endpoint)
    task_id = task.id
    result = AsyncResult(task_id, app=app)
    info = {
        "task_id":    task_id,
        "status":     result.status,
        "ready":      result.ready(),
        "successful": result.successful() if result.ready() else None,
        "failed":     result.failed() if result.ready() else None,
    }
    print(f"  AsyncResult info: {info}")


def demo_revocation():
    print("\n--- TASK REVOCATION ---")

    # Dispatch with long countdown
    task = generate_report.apply_async(args=["weekly"], countdown=60)
    print(f"  Task dispatched (60s delay): {task.id}")
    print(f"  Status before revoke: {task.status}")

    # Revoke — cancel before it runs
    app.control.revoke(task.id, terminate=False)
    time.sleep(0.5)

    result = task.get(timeout=2, propagate=False)
    print(f"  Status after revoke: {task.status}")
    print(f"  Result: {result}")


def demo_singleton():
    print("\n--- SINGLETON TASK (distributed lock) ---")

    # First call — should run
    t1 = sync_inventory.delay()
    print(f"  First call dispatched: {t1.id}")

    # Second call immediately — should be skipped (lock held)
    time.sleep(0.1)
    t2 = sync_inventory.delay()
    print(f"  Second call dispatched: {t2.id}")

    try:
        r1 = t1.get(timeout=10, propagate=False)
        r2 = t2.get(timeout=5, propagate=False)
        print(f"  First result:  {r1}")
        print(f"  Second result: {r2}")
    except Exception as e:
        print(f"  Results (worker needed): {e}")


# ═══════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("Celery Practical Demo")
    print("=" * 50)
    print("NOTE: Start worker first:")
    print("  celery -A 01_celery_practical worker --loglevel=info")
    print("=" * 50)

    # Check Redis connection
    try:
        redis_client.ping()
        print("✓ Redis connected")
    except Exception as e:
        print(f"✗ Redis not available: {e}")
        print("  Start: docker run -d -p 6379:6379 redis")
        exit(1)

    demo_basic_tasks()
    demo_canvas()
    demo_task_status()
    demo_revocation()
    demo_singleton()

    print("\n✓ All producer demos complete!")
    print("\nCheck Flower for task details: http://localhost:5555")
    print("Start Flower: celery -A 01_celery_practical flower --port=5555")


# ═══════════════════════════════════════════════════════════
# INTERVIEW QUICK REFERENCE
# ═══════════════════════════════════════════════════════════
"""
Q: delay() vs apply_async()?
A: delay(*args, **kwargs)         → shortcut, no options
   apply_async(args, kwargs, ...) → full control:
     countdown=30         → 30 seconds baad
     eta=datetime(...)    → specific time pe
     expires=datetime(...)→ deadline ke baad cancel
     queue="high"         → specific queue
     priority=9           → queue priority

Q: task_acks_late=True kyu zaroori hai?
A: Default (False): task dequeue hote hi ack → worker crash = task lost
   acks_late=True: task COMPLETE hone ke baad ack → crash pe re-queue

Q: worker_prefetch_multiplier=1 kyu?
A: Default 4: worker 4 tasks prefetch karta hai
   Long tasks ke saath: worker busy, 3 tasks stuck in memory
   Set 1: ek task complete → next fetch → fair distribution

Q: Chain vs Group vs Chord?
A: Chain:  A → B → C (sequential, output flows)
   Group:  [A, B, C] parallel, independent
   Chord:  [A, B, C] parallel → callback(results) when all done

Q: .s() vs .si() vs .delay()?
A: .s()      = signature (immutable=False) — previous result pass hota hai
   .si()     = immutable signature — previous result ignore
   .delay()  = dispatch immediately

Q: task_track_started kya karta hai?
A: Default: PENDING → SUCCESS/FAILURE
   With track_started: PENDING → STARTED → SUCCESS/FAILURE
   Worker pe task start hote hi STARTED state set hota hai

Q: Rate limiting kab use karo?
A: External API limits follow karo: SMS → "10/m", email → "100/h"
   rate_limit per-worker hai, not global
   Global limit ke liye: Redis token bucket in task body

Q: Celery Beat vs cron kya choose karein?
A: Cron:         single machine — fails if machine down, no visibility
   Celery Beat:  distributed — workers handle execution, Flower mein visible
                 dynamic schedules DB mein store kar sakte ho
   Use Beat: jab task distributed workers pe run ho

Q: on_commit kyu use karna chahiye?
A: Task dispatch BEFORE transaction commit ho toh:
   - Transaction rollback → task already sent → worker tries to find data → 404
   transaction.on_commit(lambda: task.delay(id)) ensures:
   - Task fires ONLY if transaction successfully committed
"""
