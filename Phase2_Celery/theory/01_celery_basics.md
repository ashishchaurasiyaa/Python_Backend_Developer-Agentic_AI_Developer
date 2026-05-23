# Celery — Tasks, Chains, Chords, Groups + Celery Beat

## Quick Concepts
- **Celery** = distributed task queue — async background jobs ke liye
- **Worker** = tasks execute karne wala process
- **Broker** = message queue (Redis / RabbitMQ) — tasks store karta hai
- **Result Backend** = task result store karta hai (Redis / DB)
- **Chain** = tasks ek ke baad ek (output → next input)
- **Group** = tasks parallel mein
- **Chord** = group complete hone ke baad callback

---

## Interview Questions & Answers

### Q1: Celery setup kaise karte hain FastAPI/Django ke saath?
**Answer:**
```python
# celery_app.py
from celery import Celery
import os

# Broker = Redis (tasks queue)
# Backend = Redis (results store)
celery_app = Celery(
    "myapp",
    broker="redis://localhost:6379/0",
    backend="redis://localhost:6379/1",
    include=["app.tasks.email", "app.tasks.reports", "app.tasks.notifications"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="Asia/Kolkata",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,           # crash par re-queue
    worker_prefetch_multiplier=1,  # ek baar ek hi task lo (memory safe)
    result_expires=3600,           # results 1 hour baad expire
)

# Worker start karo:
# celery -A celery_app worker --loglevel=info --concurrency=4
```

---

### Q2: Tasks kaise define karte hain? Retry logic kaise add karte hain?
**Answer:**
```python
from celery import shared_task
from celery.utils.log import get_task_logger

logger = get_task_logger(__name__)

# Simple task
@shared_task
def add(x: int, y: int) -> int:
    return x + y

# Task with retry
@shared_task(
    bind=True,                  # self access karo (task instance)
    max_retries=3,
    default_retry_delay=60,     # 60 seconds baad retry
    autoretry_for=(Exception,), # automatically retry on any exception
    retry_backoff=True,         # exponential backoff
    retry_backoff_max=600,      # max 10 minutes wait
    retry_jitter=True,          # random jitter add karo
)
def send_email(self, to: str, subject: str, body: str):
    try:
        result = email_service.send(to=to, subject=subject, body=body)
        logger.info(f"Email sent to {to}")
        return result
    except email_service.TemporaryError as exc:
        raise self.retry(exc=exc)
    except email_service.PermanentError:
        logger.error(f"Permanent email error for {to}")
        # Retry mat karo
        raise

# Task with custom queue and priority
@shared_task(queue="high_priority", priority=9)
def process_payment(order_id: int):
    logger.info(f"Processing payment for order {order_id}")
    payment_gateway.charge(order_id)

# Usage
send_email.delay("user@test.com", "Welcome!", "Thank you for registering")
process_payment.apply_async(args=[order_id], countdown=5)  # 5s baad execute

# Task ID track karo
task = send_email.delay("user@test.com", "Hi", "Body")
print(f"Task ID: {task.id}")
result = task.get(timeout=10)   # block karke result lo
print(f"Status: {task.status}") # PENDING, STARTED, SUCCESS, FAILURE, RETRY
```

---

### Q3: Chains, Groups, Chords kaise kaam karte hain?
**Answer:**
```python
from celery import chain, group, chord, signature

# CHAIN — ek ke baad ek, output → next input
# resize → watermark → upload to S3
image_pipeline = chain(
    resize_image.s(image_id, width=800),
    add_watermark.s("MyApp"),
    upload_to_s3.s(bucket="my-bucket"),
)
result = image_pipeline.delay()

# GROUP — parallel execution
# 3 reports ek saath generate karo
report_group = group(
    generate_sales_report.s(month=1),
    generate_inventory_report.s(month=1),
    generate_user_report.s(month=1),
)
result = report_group.delay()
results = result.get()  # [sales_data, inventory_data, user_data]

# CHORD — group complete hone ke baad callback
# Sab reports generate ho jaayein, phir email bhejo
pipeline = chord(
    group(
        generate_sales_report.s(month=1),
        generate_inventory_report.s(month=1),
    ),
    send_monthly_email.s(to="boss@company.com")  # callback
)
pipeline.delay()
# send_monthly_email ko [sales_result, inventory_result] milega

# Complex pipeline
full_pipeline = chain(
    validate_order.s(order_id),
    group(
        charge_payment.s(),
        update_inventory.s(),
    ) | merge_results.s(),
    send_confirmation.s(),
)
full_pipeline.delay()
```

---

### Q4: Celery Beat — Periodic tasks kaise schedule karte hain?
**Answer:**
```python
# celery_app.py
from celery.schedules import crontab

celery_app.conf.beat_schedule = {
    # Har 5 minute mein
    "cleanup-expired-sessions": {
        "task": "app.tasks.cleanup_expired_sessions",
        "schedule": 300.0,   # seconds
    },

    # Roz saat baje
    "daily-report": {
        "task": "app.tasks.generate_daily_report",
        "schedule": crontab(hour=7, minute=0),
    },

    # Har Monday saat baje
    "weekly-digest": {
        "task": "app.tasks.send_weekly_digest",
        "schedule": crontab(hour=7, minute=0, day_of_week=1),
    },

    # Har mahine ki 1 tarikh
    "monthly-billing": {
        "task": "app.tasks.process_monthly_billing",
        "schedule": crontab(day_of_month=1, hour=0, minute=0),
    },

    # With arguments
    "sync-users-every-hour": {
        "task": "app.tasks.sync_users",
        "schedule": crontab(minute=0),    # har ghante
        "args": ("all",),
        "kwargs": {"notify": True},
    },
}

# Beat worker start karo:
# celery -A celery_app beat --loglevel=info
# Ya worker ke saath:
# celery -A celery_app worker --beat --loglevel=info
```

---

### Q5: Celery mein different queues kaise use karte hain?
**Answer:**
```python
# celery_app.py
from kombu import Queue

celery_app.conf.task_queues = (
    Queue("default", routing_key="default"),
    Queue("high_priority", routing_key="high"),
    Queue("emails", routing_key="email"),
    Queue("reports", routing_key="report"),
)

celery_app.conf.task_default_queue = "default"
celery_app.conf.task_routes = {
    "app.tasks.send_email": {"queue": "emails"},
    "app.tasks.send_sms": {"queue": "emails"},
    "app.tasks.process_payment": {"queue": "high_priority"},
    "app.tasks.generate_*": {"queue": "reports"},
}

# Dedicated workers per queue
# celery -A celery_app worker -Q emails --concurrency=2 --loglevel=info
# celery -A celery_app worker -Q high_priority --concurrency=4
# celery -A celery_app worker -Q reports --concurrency=1
# celery -A celery_app worker -Q default --concurrency=4
```

---

### Q6: Flower — Celery monitoring kaise karte hain?
**Answer:**
```bash
pip install flower

# Start karo
celery -A celery_app flower --port=5555

# Docker Compose mein
services:
  flower:
    image: mher/flower
    command: celery -A celery_app flower
    ports:
      - "5555:5555"
    environment:
      - CELERY_BROKER_URL=redis://redis:6379/0
      - FLOWER_BASIC_AUTH=admin:password  # basic auth
    depends_on:
      - redis
```

```python
# Programmatically task status check karo
from celery.result import AsyncResult

def get_task_status(task_id: str) -> dict:
    result = AsyncResult(task_id)
    return {
        "task_id": task_id,
        "status": result.status,
        "result": result.result if result.ready() else None,
        "traceback": result.traceback if result.failed() else None,
    }

# FastAPI endpoint
@app.get("/tasks/{task_id}")
async def check_task(task_id: str):
    return get_task_status(task_id)

@app.post("/generate-report")
async def generate_report(month: int):
    task = generate_monthly_report.delay(month)
    return {"task_id": task.id, "status": "queued"}
```

---

### Q7: RabbitMQ vs Redis as Celery broker?
**Answer:**
| Feature | Redis | RabbitMQ |
|---|---|---|
| Setup | Simple | Complex (exchange, bindings) |
| Performance | Fast (in-memory) | Slightly slower |
| Message persistence | Optional | Yes (durable queues) |
| Routing | Basic | Advanced (topic, fanout, direct) |
| Dead letter queue | Manual | Built-in |
| Memory | More (all in RAM) | Less |
| Use case | Simple, fast tasks | Complex routing, enterprise |
| **Recommendation** | **Most projects** | High reliability needed |

```python
# RabbitMQ broker URL
CELERY_BROKER_URL = "amqp://admin:password@rabbitmq:5672//"

# Redis broker URL (simpler)
CELERY_BROKER_URL = "redis://redis:6379/0"
```
