# Async & Queue Deep Guide — Celery · RabbitMQ · AWS SQS
### Resume Skills: Celery, RabbitMQ, AWS SQS, Async Processing
### PwC Interview Ready · 3-4 baar padho

> **Reading plan:**
> - Pass 1: Poora padho — architecture samjho
> - Pass 2: Interview answers loud bolke practice karo
> - Pass 3: Architecture diagrams haath se draw karo
> - Pass 4: Quick Recall Card only

---

## TABLE OF CONTENTS

| # | Topic | Tera Resume Project |
|---|---|---|
| 1 | Why Async — problem statement | All projects |
| 2 | Celery Architecture + Internals | Niroskos, Youngman Beta |
| 3 | Celery Code — tasks, routing, retry | Niroskos booking confirm |
| 4 | Celery Beat — periodic tasks | Report generation |
| 5 | RabbitMQ — AMQP internals | Production broker choice |
| 6 | RabbitMQ vs Redis as broker | Architecture decision |
| 7 | AWS SQS — cloud queue | AWS deployment |
| 8 | SQS Standard vs FIFO | Order-critical processing |
| 9 | Dead Letter Queue pattern | Fault tolerance |
| 10 | Interview Q&A — 18 Questions | PwC specific |
| 11 | Quick Recall Card | 1 ghanta pehle |

---

## TOPIC 1: WHY ASYNC — Problem Statement

### Synchronous problem

```
USER REQUEST → DJANGO VIEW → SEND EMAIL → RESPONSE
                              (3 seconds)
                              (user waits!)

If email server slow:
USER REQUEST → DJANGO VIEW → SEND EMAIL → TIMEOUT → 500 Error!
                              (30 seconds)

If 100 concurrent requests all send emails:
→ 100 threads blocked waiting for email server
→ Memory exhaustion → server crash
```

### Async solution

```
USER REQUEST → DJANGO VIEW → QUEUE TASK → RESPONSE (instant!)
                               ↓
                          CELERY WORKER (background)
                               ↓
                          SEND EMAIL (user already got response)

BENEFITS:
✅ Request returns immediately (fast UX)
✅ Worker retries on failure (resilient)
✅ Scale workers independently (horizontal scale)
✅ Different priority queues (VIP vs bulk)
✅ Scheduled tasks (cron-like but better)
```

### Real examples from tera resume

```
NIROSKOS (Tour booking platform):
──────────────────────────────────
Booking confirmed → SYNC would mean:
1. Save booking to DB
2. Send confirmation email (1-2s)
3. Send SMS to guide (1s)
4. Generate PDF invoice (2-3s)
5. Notify admin dashboard (0.5s)
Total: 5-6 seconds user waits!

WITH CELERY:
1. Save booking to DB
2. Queue tasks for steps 2-5
3. Return response in 200ms
Workers do rest in background.

YOUNGMAN BETA (SAP HANA sync):
────────────────────────────────
10,000+ invoices/month → SAP sync
Each sync = HTTP call to SAP (500ms-2s)
Sync all synchronously = hours blocked
WITH CELERY: Queue each invoice, workers process in parallel.
```

---

## TOPIC 2: CELERY ARCHITECTURE + INTERNALS

### High-level architecture

```
CELERY ARCHITECTURE
────────────────────────────────────────────────────────────────

DJANGO APP (Producer)                    CELERY WORKER (Consumer)
      │                                         │
      │ .delay() / .apply_async()               │
      │                                         │
      ▼                                         │
┌──────────────────────────────────────────┐    │
│              MESSAGE BROKER              │    │
│                                          │    │
│  Redis / RabbitMQ                        │    │
│                                          │    │
│  ┌─────────────────┐                    │    │
│  │  Queue: default │◄── push ───────────│────│── Django app
│  └────────────┬────┘                    │    │
│               │ pop                     │    │
│  ┌─────────────▼────┐                   │    │
│  │  Queue: high     │◄── push ─────────────── │
│  └─────────────┬────┘                   │    │
│               │ pop                     │    │
│  ┌─────────────▼────┐                   │    │
│  │  Queue: low      │                   │    │
│  └──────────────────┘                   │    │
└──────────────────────────────────────────┘    │
                │                               │
                │ BRPOP (blocking pop)          │
                ▼                               │
    ┌─────────────────────────────────────────┐ │
    │           CELERY WORKER PROCESS         │ │
    │                                         │ │
    │  ┌──────────────────────────────────┐   │ │
    │  │  Prefork Pool (default)          │   │ │
    │  │  ├── child process 1 (task A)    │   │ │
    │  │  ├── child process 2 (task B)    │   │ │
    │  │  ├── child process 3 (task C)    │   │ │
    │  │  └── child process 4 (idle)      │   │ │
    │  └──────────────────────────────────┘   │ │
    └─────────────────────────────────────────┘ │
                │                               │
                │ Store result                  │
                ▼                               │
    ┌─────────────────────────────────────────┐ │
    │         RESULT BACKEND                  │ │
    │         (Redis / DB / Memcached)        │ │
    │  task_id → {status, result, traceback}  │ │
    └─────────────────────────────────────────┘ │
                │                               │
                │ .get() / AsyncResult          │
                └───────────────────────────────┘
                  Django app can check results
```

### Worker pool types

```
POOL TYPE        USE CASE                     NOTES
──────────────   ──────────────────────────   ──────────────────────────
prefork          CPU-bound tasks              Separate OS processes
(default)        Image processing, reports    Full isolation, more memory

eventlet/gevent  I/O-bound tasks              Coroutines (green threads)
                 API calls, DB queries        High concurrency, single process
                 Thousands of tasks           pip install eventlet

threads          I/O-bound, simple setup      OS threads
                 Django ORM-heavy tasks       GIL limits CPU usage

solo             Debugging only               Single process, no pool
                 Development                  Tasks run sequentially

TERA CASE (Niroskos):
Email/SMS tasks → gevent (I/O bound, many concurrent)
PDF generation → prefork (CPU bound, needs isolation)

celery -A config worker -P gevent --concurrency 100    # I/O tasks
celery -A config worker -P prefork --concurrency 4     # CPU tasks
```

---

## TOPIC 3: CELERY CODE — TASKS, ROUTING, RETRY

### Setup + configuration

```python
# config/celery.py
import os
from celery import Celery
from kombu import Exchange, Queue

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

app = Celery("niroskos")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()  # finds tasks.py in each Django app

# settings.py
CELERY_BROKER_URL = "redis://localhost:6379/0"
CELERY_RESULT_BACKEND = "redis://localhost:6379/1"

# IMPORTANT production settings:
CELERY_TASK_ACKS_LATE = True           # ack after completion, not receipt
CELERY_WORKER_PREFETCH_MULTIPLIER = 1  # one task at a time (fair)
CELERY_TASK_REJECT_ON_WORKER_LOST = True  # requeue if worker dies mid-task
CELERY_RESULT_EXPIRES = 3600           # result expires in 1 hour
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"

# QUEUE ROUTING (priority)
CELERY_TASK_QUEUES = (
    Queue("high",    Exchange("high"),    routing_key="high"),
    Queue("default", Exchange("default"), routing_key="default"),
    Queue("low",     Exchange("low"),     routing_key="low"),
)
CELERY_TASK_DEFAULT_QUEUE = "default"
CELERY_TASK_DEFAULT_EXCHANGE = "default"
CELERY_TASK_DEFAULT_ROUTING_KEY = "default"

CELERY_TASK_ROUTES = {
    "bookings.tasks.send_booking_confirmation":   {"queue": "high"},
    "bookings.tasks.send_sms_to_guide":           {"queue": "high"},
    "reports.tasks.generate_monthly_report":      {"queue": "low"},
    "invoices.tasks.sync_to_sap":                 {"queue": "default"},
}
```

### Task definition — all patterns

```python
# bookings/tasks.py
from celery import shared_task, Task
from celery.utils.log import get_task_logger
from celery.exceptions import MaxRetriesExceededError
import requests

logger = get_task_logger(__name__)

# ═══════════════════════════════════════════════════
# BASIC TASK
# ═══════════════════════════════════════════════════
@shared_task
def send_welcome_email(user_id: int):
    from users.models import User
    user = User.objects.get(id=user_id)
    # send email
    logger.info(f"Sent welcome email to {user.email}")

# Call:
send_welcome_email.delay(user_id=42)

# ═══════════════════════════════════════════════════
# TASK WITH RETRY (Niroskos SAP sync ka pattern)
# ═══════════════════════════════════════════════════
@shared_task(
    bind=True,               # gives access to self (task instance)
    max_retries=3,           # max 3 retries
    default_retry_delay=60,  # wait 60s between retries
    autoretry_for=(          # auto retry on these exceptions
        requests.exceptions.Timeout,
        requests.exceptions.ConnectionError,
    ),
    retry_backoff=True,      # exponential: 60s, 120s, 240s
    retry_backoff_max=600,   # max 10 min wait
    retry_jitter=True,       # random jitter (prevent thundering herd)
    acks_late=True,
)
def sync_invoice_to_sap(self, invoice_id: int):
    from invoicing.models import Invoice, SAPLog
    try:
        invoice = Invoice.objects.get(id=invoice_id)

        # Idempotency check (prevents duplicate SAP entries)
        if SAPLog.objects.filter(invoice=invoice, status="success").exists():
            logger.info(f"Invoice {invoice_id} already synced, skipping")
            return {"status": "skipped", "reason": "already_synced"}

        # SAP API call
        response = sap_client.push_invoice(invoice)

        SAPLog.objects.update_or_create(
            invoice=invoice,
            defaults={"status": "success", "sap_ref": response["ref"]}
        )
        logger.info(f"Invoice {invoice_id} synced to SAP: {response['ref']}")
        return {"status": "success", "sap_ref": response["ref"]}

    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 422:
            # Validation error — no point retrying
            SAPLog.objects.update_or_create(
                invoice=invoice,
                defaults={"status": "failed", "error": str(e)}
            )
            raise   # don't retry

        # Other HTTP errors — retry
        logger.warning(f"SAP HTTP error for invoice {invoice_id}: {e}")
        raise self.retry(exc=e)

    except MaxRetriesExceededError:
        # All retries exhausted
        SAPLog.objects.update_or_create(
            invoice=invoice,
            defaults={"status": "failed", "error": "max_retries_exceeded"}
        )
        # Alert ops team
        send_ops_alert.delay(f"SAP sync failed after 3 retries: invoice {invoice_id}")

# ═══════════════════════════════════════════════════
# APPLY_ASYNC — fine-grained control
# ═══════════════════════════════════════════════════
# Basic delay
sync_invoice_to_sap.delay(invoice_id=123)

# With options
sync_invoice_to_sap.apply_async(
    args=[123],
    kwargs={},
    queue="high",                          # specific queue
    countdown=30,                          # wait 30s before executing
    eta=datetime(2026, 8, 15, 10, 0, 0), # execute at specific time
    expires=3600,                          # expire if not started in 1hr
    retry=True,
    retry_policy={"max_retries": 5},
)

# ═══════════════════════════════════════════════════
# CHAIN — sequential tasks (output of A → input of B)
# ═══════════════════════════════════════════════════
from celery import chain

# Booking confirmed → email → SMS → update dashboard
workflow = chain(
    send_booking_confirmation.s(booking_id=1),    # .s() = signature
    send_guide_sms.s(),                           # receives prev result
    update_booking_dashboard.s()
)
workflow.delay()

# ═══════════════════════════════════════════════════
# CHORD — parallel tasks then callback
# ═══════════════════════════════════════════════════
from celery import chord

# Process all invoices in parallel, then send summary
header = [sync_invoice_to_sap.s(id) for id in invoice_ids]
callback = send_sync_summary.s()

chord(header)(callback)
# All sync tasks run in parallel → when ALL done → send_sync_summary called

# ═══════════════════════════════════════════════════
# GROUP — parallel tasks, no callback
# ═══════════════════════════════════════════════════
from celery import group

# Send emails to all users in parallel
job = group(send_email.s(user_id) for user_id in user_ids)
result = job.delay()
results = result.get()  # wait for all

# ═══════════════════════════════════════════════════
# TASK STATES + MONITORING
# ═══════════════════════════════════════════════════
task_result = sync_invoice_to_sap.delay(123)
task_id = task_result.id

# Check status (from Django view or admin)
from celery.result import AsyncResult

result = AsyncResult(task_id)
print(result.state)   # PENDING / STARTED / SUCCESS / FAILURE / RETRY
print(result.result)  # return value or exception
print(result.traceback)  # if FAILURE

# Custom states (progress tracking)
@shared_task(bind=True)
def generate_report(self, report_id: int):
    total_pages = 100
    for i, page in enumerate(get_pages()):
        # Update progress
        self.update_state(
            state="PROGRESS",
            meta={"current": i, "total": total_pages, "percent": i * 100 // total_pages}
        )
        process_page(page)
    return {"status": "complete", "pages": total_pages}

# Poll from frontend (SSE or polling)
@app.get("/reports/{task_id}/status")
async def report_status(task_id: str):
    result = AsyncResult(task_id)
    if result.state == "PROGRESS":
        return result.info   # {"current": 45, "total": 100}
    elif result.state == "SUCCESS":
        return {"status": "done", "result": result.result}
    return {"status": result.state}
```

### Django signals + on_commit (prevent race condition)

```python
# signals.py — WRONG way
@receiver(post_save, sender=Booking)
def booking_created(sender, instance, created, **kwargs):
    if created:
        # BUG: Task might run BEFORE transaction commits!
        # Worker tries to fetch booking → not in DB yet → crash
        send_booking_confirmation.delay(instance.id)

# CORRECT way — on_commit hook
@receiver(post_save, sender=Booking)
def booking_created(sender, instance, created, **kwargs):
    if created:
        # Only queues task AFTER DB transaction commits
        transaction.on_commit(
            lambda: send_booking_confirmation.delay(instance.id)
        )
        # If transaction rolls back → task NOT queued ✅
```

---

## TOPIC 4: CELERY BEAT — PERIODIC TASKS

### Architecture

```
CELERY BEAT ARCHITECTURE
────────────────────────────────────────────────────────────────

CELERY BEAT (scheduler process — single instance!)
      │
      │  Every N seconds/minutes: "time hai task chalane ka"
      │
      ▼
   BROKER (Redis / RabbitMQ)
   ┌──────────────────────────────────────┐
   │  Queue: celery (default)             │
   │  Task: generate_daily_report         │
   └──────────────────────────────────────┘
      │
      ▼
   CELERY WORKER
   Executes generate_daily_report()

NOTE: Beat is SINGLE process. Never run multiple beat instances!
(duplicate tasks execute)
```

### Beat configuration — django-celery-beat (DB-backed)

```python
# pip install django-celery-beat
# INSTALLED_APPS: 'django_celery_beat'

# settings.py
CELERY_BEAT_SCHEDULER = "django_celery_beat.schedulers:DatabaseScheduler"
# Schedules stored in DB → change without restart!
# Admin panel se manage karo

# OR hardcoded in code:
from celery.schedules import crontab

CELERY_BEAT_SCHEDULE = {
    # Run every day at 6 AM
    "daily-sap-sync": {
        "task": "invoices.tasks.sync_all_pending_invoices",
        "schedule": crontab(hour=6, minute=0),
        "args": (),
    },

    # Every 30 minutes
    "check-booking-reminders": {
        "task": "bookings.tasks.send_upcoming_reminders",
        "schedule": crontab(minute="*/30"),
    },

    # Every Monday at 9 AM
    "weekly-report": {
        "task": "reports.tasks.generate_weekly_report",
        "schedule": crontab(hour=9, minute=0, day_of_week="monday"),
    },

    # Every 60 seconds (health check)
    "heartbeat": {
        "task": "core.tasks.system_heartbeat",
        "schedule": 60.0,   # seconds
    },

    # First day of every month
    "monthly-invoice-report": {
        "task": "reports.tasks.generate_monthly_invoice_report",
        "schedule": crontab(hour=7, minute=0, day_of_month=1),
    },
}
```

### Starting everything

```bash
# Start broker (Redis)
redis-server

# Start workers (separate terminal each)
celery -A config worker -Q high --concurrency=4 --loglevel=info
celery -A config worker -Q default --concurrency=2 --loglevel=info
celery -A config worker -Q low -P gevent --concurrency=20 --loglevel=info

# Start beat (one instance only!)
celery -A config beat --loglevel=info

# Monitor (Flower web UI)
pip install flower
celery -A config flower --port=5555
# http://localhost:5555 → tasks, workers, queues ka dashboard

# Production: supervisor / systemd se manage karo
```

---

## TOPIC 5: RABBITMQ — AMQP INTERNALS

### Definition

```
RabbitMQ = Enterprise message broker.
AMQP protocol (Advanced Message Queuing Protocol).
Written in Erlang → fault-tolerant by design.
Mature: 2007 se available.
Celery ka default broker (production recommendation).
```

### AMQP concepts — kya kya hai

```
AMQP CORE CONCEPTS:
────────────────────────────────────────────────────────────────

PRODUCER ──publish──► EXCHANGE ──route──► QUEUE ◄──consume── CONSUMER

1. PRODUCER:   Message publish karta hai
2. EXCHANGE:   Message routing karta hai (queue mein kahan jaaye)
3. BINDING:    Exchange aur Queue ko connect karta hai (routing rules)
4. QUEUE:      Messages store karta hai (durably)
5. CONSUMER:   Messages consume karta hai (Celery worker)
```

### Exchange types — kab kya

```
EXCHANGE TYPE    ROUTING          USE CASE
──────────────   ──────────────   ────────────────────────────────────
DIRECT           routing_key      Specific queue. Celery task routing.
                 exact match      high → high queue, default → default

FANOUT           none             Broadcast. All bound queues get copy.
                 (all queues)     Log aggregation, notifications to all

TOPIC            pattern match    Flexible routing. *.critical → all
                 * = one word     critical. logs.# → all logs.*
                 # = zero+words

HEADERS          header values    Route by message headers, not key.
                 (key-value)      Rare — complex, slow

YOUR CELERY:
Task routing = DIRECT exchange
"high" routing_key → high queue
"default" routing_key → default queue
```

### RabbitMQ architecture diagram

```
RABBITMQ ARCHITECTURE (Production Setup)
────────────────────────────────────────────────────────────────

DJANGO APP                RABBITMQ BROKER              CELERY WORKERS
    │                          │
    │  amqp://rabbit:5672      │
    │──────── connect ────────►│
    │                          │
    │  PUBLISH                 │  DIRECT EXCHANGE "celery"
    │  routing_key="high" ────►│
    │                          │  ┌─────────────────────────────────┐
    │                          │  │ Bindings:                        │
    │                          │  │ high    → Queue: high.tasks      │
    │                          │  │ default → Queue: default.tasks   │
    │                          │  │ low     → Queue: low.tasks       │
    │                          │  └─────────────────────────────────┘
    │                          │           │
    │                          │  ┌────────▼────────┐
    │                          │  │ Queue: high.tasks│ ──────► Worker 1
    │                          │  │ durable: true    │         (high)
    │                          │  │ msgs: 45         │
    │                          │  └──────────────────┘
    │                          │
    │                          │  ┌─────────────────────┐
    │                          │  │ Queue: default.tasks │ ──► Worker 2
    │                          │  │ durable: true        │    (default)
    │                          │  │ msgs: 120            │
    │                          │  └─────────────────────┘
    │                          │
    │  FANOUT for broadcast    │  FANOUT EXCHANGE "events"
    │  routing_key="" ────────►│  → ALL bound queues get copy
    │  (payment_processed evt) │  → audit_queue
    │                          │  → notification_queue
    │                          │  → analytics_queue

MANAGEMENT UI: http://rabbitmq:15672
(tera admin panel — queues, messages, consumers dekh)
```

### RabbitMQ key features

```
DURABILITY:
Queue durable=True + Message persistent → survives RabbitMQ restart
Non-durable → lost on restart (cache data ke liye OK)

ACKNOWLEDGMENT:
Consumer processes message → sends ACK
No ACK (crash) → message requeued automatically
manual_ack=True → you control when to ACK

PREFETCH:
channel.basic_qos(prefetch_count=1)
Worker ek time pe sirf 1 message lega
Fair dispatch — slow worker ko zyada nahi milega
Celery: CELERY_WORKER_PREFETCH_MULTIPLIER = 1

DEAD LETTER EXCHANGE (DLQ):
Message fails N times → DLQ mein jaata hai
Ops team inspect kar sake, manual fix, requeue
(Topic 9 mein detail hai)

CLUSTERING:
Multiple RabbitMQ nodes → HA
Queue mirroring → node fail hone pe data safe
Production pe minimum 3 nodes

MANAGEMENT PLUGIN:
rabbitmq-plugins enable rabbitmq_management
http://localhost:15672
Admin panel: queues, messages, consumers, rates
```

---

## TOPIC 6: RABBITMQ VS REDIS AS CELERY BROKER

### Comparison

```
FEATURE              REDIS BROKER          RABBITMQ BROKER
──────────────────   ──────────────────    ──────────────────────────
Protocol             Custom (RESP)         AMQP (standard)
Setup complexity     Simple               More complex
Durability           Optional (AOF/RDB)   Built-in (durable queues)
Message routing      Basic queues          Advanced (exchanges, topics)
Dead letter queue    Manual (custom)       Built-in (x-dead-letter)
Monitoring           Flower + Redis CLI    Management UI (15672)
Performance          Faster (in-memory)   Slightly slower
HA / Clustering      Redis Cluster         RabbitMQ Cluster + mirroring
Message TTL          Manual (EXPIRE)       Built-in
Priority queues      Sorted Set tricks     Built-in (x-max-priority)
AMQP compliance      ❌                    ✅
Use case             Small-medium apps     Enterprise, complex routing

WHEN I'D USE REDIS:
✅ Already using Redis (cache, sessions) → one less service
✅ Simple task queues, basic routing
✅ Small team, fast startup
✅ OK to lose some tasks on Redis crash (queue = cache-like)

WHEN I'D USE RABBITMQ:
✅ Complex routing (fanout events, topic filtering)
✅ Task durability critical (financial transactions)
✅ Enterprise compliance, AMQP required
✅ Multiple apps consuming same queue
✅ Need built-in DLQ, TTL, priority

MY RESUME:
Niroskos → Redis broker (simpler setup, faster iteration)
Would switch to RabbitMQ if:
- Task loss acceptable risk decreases (financial use case)
- Complex event routing needed
- Multiple services consuming tasks
```

---

## TOPIC 7: AWS SQS — CLOUD QUEUE

### Definition

```
AWS SQS = Simple Queue Service.
Managed cloud message queue — AWS runs it, you just use it.
Serverless: no server to manage, auto-scales.
Decouples microservices in AWS ecosystem.
```

### Architecture

```
AWS SQS ARCHITECTURE
────────────────────────────────────────────────────────────────

PRODUCER                   SQS SERVICE              CONSUMER
(Django / Lambda)              (AWS managed)         (Lambda / ECS / EC2)
     │                              │                      │
     │  SendMessage                 │                      │
     │─────────────────────────────►│                      │
     │                              │  ┌─────────────────┐ │
     │                              │  │ Queue           │ │
     │                              │  │ ┌─────────────┐ │ │
     │                              │  │ │ Message A   │ │ │
     │                              │  │ ├─────────────┤ │ │
     │                              │  │ │ Message B   │ │ │
     │                              │  │ ├─────────────┤ │ │
     │                              │  │ │ Message C   │ │ │
     │                              │  │ └─────────────┘ │ │
     │                              │  └────────┬────────┘ │
     │                              │           │           │
     │                              │  ReceiveMessage      │
     │                              │◄─────────────────────│
     │                              │           │           │
     │                              │  Message (invisible) │
     │                              │──────────────────────►│
     │                              │                       │
     │                              │  (processing...)      │
     │                              │                       │
     │                              │  DeleteMessage        │
     │                              │◄──────────────────────│
     │                              │  (ACK — remove msg)  │
     │                              │                       │

VISIBILITY TIMEOUT:
Consumer receives message → becomes INVISIBLE (not deleted)
If consumer crashes before DeleteMessage → timeout expires
Message becomes visible again → another consumer picks up!
```

### SQS code — boto3

```python
import boto3
import json
import logging
from typing import Any

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════
# SETUP
# ═══════════════════════════════════════════════════
sqs = boto3.client(
    "sqs",
    region_name="ap-south-1",
    # In production: use IAM role, not hardcoded keys!
    # aws_access_key_id=...,
    # aws_secret_access_key=...,
)

QUEUE_URL = "https://sqs.ap-south-1.amazonaws.com/123456789/niroskos-bookings"

# ═══════════════════════════════════════════════════
# PRODUCER — send message
# ═══════════════════════════════════════════════════
def send_booking_event(booking_id: int, event_type: str, data: dict):
    message = {
        "booking_id": booking_id,
        "event_type": event_type,
        "data": data,
    }
    response = sqs.send_message(
        QueueUrl=QUEUE_URL,
        MessageBody=json.dumps(message),
        MessageAttributes={
            "event_type": {
                "StringValue": event_type,
                "DataType": "String",
            }
        },
        DelaySeconds=0,   # immediate delivery (0-900s)
    )
    logger.info(f"Message sent: {response['MessageId']}")
    return response["MessageId"]

# Batch send (up to 10 messages, cheaper per-message)
def send_bulk_invoice_events(invoice_ids: list[int]):
    entries = [
        {
            "Id": str(invoice_id),
            "MessageBody": json.dumps({"invoice_id": invoice_id, "event": "sync"}),
        }
        for invoice_id in invoice_ids[:10]   # max 10 per batch
    ]
    response = sqs.send_message_batch(QueueUrl=QUEUE_URL, Entries=entries)
    failed = response.get("Failed", [])
    if failed:
        logger.error(f"Failed to send {len(failed)} messages")
    return response

# ═══════════════════════════════════════════════════
# CONSUMER — receive and process
# ═══════════════════════════════════════════════════
def process_queue_messages():
    while True:
        # Long polling (wait up to 20s for messages — cheaper!)
        response = sqs.receive_message(
            QueueUrl=QUEUE_URL,
            MaxNumberOfMessages=10,        # max 10 at once
            WaitTimeSeconds=20,            # long polling (vs short polling)
            VisibilityTimeout=30,          # 30s to process
            MessageAttributeNames=["All"],
        )

        messages = response.get("Messages", [])
        if not messages:
            logger.info("No messages, waiting...")
            continue

        for message in messages:
            receipt_handle = message["ReceiptHandle"]
            try:
                body = json.loads(message["Body"])
                process_booking_event(body)

                # SUCCESS → delete message (ACK)
                sqs.delete_message(
                    QueueUrl=QUEUE_URL,
                    ReceiptHandle=receipt_handle,
                )
                logger.info(f"Processed and deleted: {message['MessageId']}")

            except Exception as e:
                logger.error(f"Failed to process {message['MessageId']}: {e}")
                # DON'T delete → visibility timeout expires → retry!
                # Or change visibility timeout to retry sooner:
                sqs.change_message_visibility(
                    QueueUrl=QUEUE_URL,
                    ReceiptHandle=receipt_handle,
                    VisibilityTimeout=5,   # retry in 5 seconds
                )

# ═══════════════════════════════════════════════════
# CREATE QUEUE WITH DLQ
# ═══════════════════════════════════════════════════
def create_queue_with_dlq():
    # 1. Create Dead Letter Queue first
    dlq_response = sqs.create_queue(
        QueueName="niroskos-bookings-dlq",
        Attributes={
            "MessageRetentionPeriod": "1209600",  # 14 days
        }
    )
    dlq_url = dlq_response["QueueUrl"]
    dlq_attrs = sqs.get_queue_attributes(
        QueueUrl=dlq_url, AttributeNames=["QueueArn"]
    )
    dlq_arn = dlq_attrs["Attributes"]["QueueArn"]

    # 2. Create main queue with DLQ reference
    queue_response = sqs.create_queue(
        QueueName="niroskos-bookings",
        Attributes={
            "VisibilityTimeout": "30",
            "MessageRetentionPeriod": "86400",   # 1 day
            "RedrivePolicy": json.dumps({
                "deadLetterTargetArn": dlq_arn,
                "maxReceiveCount": "3",           # 3 failures → DLQ
            }),
        }
    )
    return queue_response["QueueUrl"]
```

---

## TOPIC 8: SQS STANDARD VS FIFO

### Comparison

```
STANDARD QUEUE:
────────────────────────────────────────────────────────────────
✅ Unlimited throughput (thousands/second)
✅ Best-effort ordering (mostly in order, not guaranteed)
⚠️ At-least-once delivery (can get DUPLICATES!)
   → Consumer must be IDEMPOTENT
✅ Cheaper
Use case: High-volume, idempotent tasks
          Email notifications, log processing, analytics

FIFO QUEUE:
────────────────────────────────────────────────────────────────
✅ Exactly-once processing (no duplicates!)
✅ FIFO order guaranteed within group
❌ 300 TPS limit (3000 with batching)
❌ More expensive
❌ Queue name must end with ".fifo"
Use case: Financial transactions, order processing
          Booking creation (can't duplicate a booking!)

MESSAGE GROUP ID (FIFO):
Messages with same MessageGroupId → processed in order
Different GroupIds → processed in parallel

# FIFO Example
sqs.send_message(
    QueueUrl="https://sqs.../niroskos-payments.fifo",
    MessageBody=json.dumps(payment_data),
    MessageGroupId=f"user-{user_id}",         # order per user
    MessageDeduplicationId=f"payment-{uuid}", # unique ID
)
```

---

## TOPIC 9: DEAD LETTER QUEUE — FAULT TOLERANCE

### What is DLQ

```
PROBLEM:
Message processing fails → retry → fail → retry → infinite loop
Queue blocked by bad message (poison pill)
Good messages behind bad message can't process!

SOLUTION: Dead Letter Queue

FLOW:
────────────────────────────────────────────────────────────────

Main Queue                       Dead Letter Queue
┌─────────────────────────┐      ┌──────────────────────────────┐
│ Message A (good)         │      │ Message B (failed 3 times)   │
│ Message B (poison pill) ─┼─────►│ → ops team investigates      │
│ Message C (good)         │      │ → manual fix + requeue       │
└─────────────────────────┘      └──────────────────────────────┘
    Workers skip B (in DLQ)
    A and C processed fine!

SETUP (SQS):
maxReceiveCount = 3    → after 3 failures → DLQ

SETUP (RabbitMQ):
x-dead-letter-exchange: "my-dlx"
x-dead-letter-routing-key: "dead"
x-message-ttl: 30000    → expires after 30s → DLQ

SETUP (Celery):
CELERY_TASK_MAX_RETRIES = 3    → after 3 → on_failure() called
```

### DLQ pattern in Celery

```python
# Celery "DLQ" equivalent — failed task handler
from celery import Task

class BaseTask(Task):
    abstract = True

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """Called after all retries exhausted."""
        logger.error(
            f"Task {self.name}[{task_id}] failed after all retries. "
            f"Args: {args}, Kwargs: {kwargs}, Exception: {exc}"
        )
        # Store in DB for ops team
        FailedTask.objects.create(
            task_id=task_id,
            task_name=self.name,
            args=str(args),
            kwargs=str(kwargs),
            error=str(exc),
            traceback=str(einfo),
        )
        # Alert ops
        send_slack_alert(
            f"🚨 Task {self.name} failed permanently: {exc}"
        )

    def on_retry(self, exc, task_id, args, kwargs, einfo):
        logger.warning(f"Task {self.name}[{task_id}] retrying: {exc}")


@shared_task(bind=True, base=BaseTask, max_retries=3)
def sync_invoice_to_sap(self, invoice_id: int):
    ...

# Requeue failed tasks (ops tool)
@app.post("/admin/retry-failed-tasks")
def retry_failed_tasks():
    failed = FailedTask.objects.filter(status="pending")
    for task in failed:
        # Requeue with original args
        sync_invoice_to_sap.apply_async(
            args=eval(task.args),
            kwargs=eval(task.kwargs),
        )
        task.status = "requeued"
        task.save()
    return {"requeued": failed.count()}
```

---

## TOPIC 10: INTERVIEW Q&A — 18 Questions

---

**Q1. Celery kya hai aur kyun use karte ho — ek real example se?**

```
ANSWER:
Celery ek distributed task queue hai. Django app se time-consuming
operations ko background mein move karne ke liye.

Real example (Niroskos):
User books a tour:
1. Booking DB mein save hoti hai
2. transaction.on_commit() pe 4 Celery tasks queue hote hain:
   - send_booking_confirmation.delay(booking_id) → high queue
   - send_guide_sms.delay(booking_id) → high queue
   - generate_invoice_pdf.delay(booking_id) → default queue
   - update_analytics.delay(booking_id) → low queue
3. User ko 200ms mein response milta hai

Workers background mein yeh sab karte hain.
Agar email fail hota hai → 3 retries with exponential backoff.
User experience unaffected.
```

---

**Q2. Celery retry strategy kya use karte ho?**

```
ANSWER:
Teen layers:

Layer 1: autoretry_for (automatic):
@shared_task(
    autoretry_for=(requests.Timeout, ConnectionError),
    retry_backoff=True,        # exponential: 60s, 120s, 240s
    retry_backoff_max=600,     # max 10 min
    retry_jitter=True,         # random jitter
    max_retries=3,
)

Layer 2: Manual retry (different errors, different strategy):
except HTTPError as e:
    if e.status_code == 422:
        raise   # no retry — validation error, won't fix itself
    raise self.retry(exc=e, countdown=60)

Layer 3: on_failure callback (exhausted):
Store in FailedTask DB → ops team alert → manual requeue option.

Youngman Beta SAP sync: 99% success rate on 10k+ invoices
using this 3-layer approach.
```

---

**Q3. CELERY_TASK_ACKS_LATE kya hai aur kyun zaroori hai?**

```
DEFAULT (acks_late=False):
Message received → immediately ACK'd (removed from queue)
Worker crashes mid-processing → message LOST!

ACKS_LATE=True:
Message received → stays in queue (invisible)
Worker processes → SUCCESS → then ACK'd (removed)
Worker crashes → visibility timeout → message requeued!

Tradeoff:
Possible duplicate execution if worker crashes AFTER processing
but BEFORE ACK.
Solution: Make tasks idempotent
  Check if already done before doing (idempotency key in DB)

MY SETUP:
CELERY_TASK_ACKS_LATE = True
CELERY_WORKER_PREFETCH_MULTIPLIER = 1   # one at a time = fair
CELERY_TASK_REJECT_ON_WORKER_LOST = True  # requeue on worker crash
```

---

**Q4. RabbitMQ aur Redis mein broker ke liye kya choose karoge?**

```
NIROSKOS mein Redis chose kiya:
- Already using Redis (cache, sessions) → one less service
- Simple task queues, basic routing
- Fast iteration, small team
- Acceptable: minor message loss risk (async tasks, not financial)

Production mein RabbitMQ prefer karunga jab:
1. Financial transactions → exactly-once delivery needed
   RabbitMQ durable queues + persistent messages = no loss on crash
2. Complex routing needed
   Fanout: payment event → billing + analytics + notification
   Topic: *.critical → monitoring queue
3. Multiple apps consuming same queue (AMQP standard)
4. Need built-in DLQ, message TTL, priority queues

Redis broker ka main risk:
AOF off hai → Redis restart → queued tasks lost!
FIX: appendonly yes in redis.conf
```

---

**Q5. SQS Standard vs FIFO — kab kya?**

```
STANDARD:
✅ Unlimited throughput
⚠️ At-least-once (duplicates possible)
→ Use when: idempotent tasks, high volume, order not critical
→ Example: Email notifications, log ingestion, analytics events

FIFO:
✅ Exactly-once, guaranteed order
❌ 300 TPS limit
→ Use when: financial transactions, order processing, booking creation
→ Example: Payment processing (can't charge twice!)

MY RULE:
Standard + idempotent consumer = works for most cases
FIFO for money/bookings where duplicate = real business problem

IDEMPOTENT CONSUMER EXAMPLE:
def process_payment(payment_id):
    if Payment.objects.filter(id=payment_id, status="processed").exists():
        return  # already done, skip (idempotent)
    process_and_charge(payment_id)
```

---

**Q6. Celery chain, chord, group — kab kya?**

```
CHAIN (sequential):
A result → B input → C input
booking_confirm → send_email → update_dashboard

chain(
    send_booking_confirmation.s(booking_id),
    send_guide_sms.s(),
    update_dashboard.s()
).delay()

GROUP (parallel, no callback):
Run N tasks in parallel, get all results
group(sync_invoice.s(id) for id in ids).delay()

CHORD (parallel → callback):
Run N tasks in parallel → when ALL done → callback
header = [sync_invoice.s(id) for id in ids]
chord(header)(send_sync_summary.s())

REAL USE (Youngman Beta):
Monthly billing run:
1. group → parallel SAP sync for all invoices
2. chord callback → generate summary report
3. chain → email summary → notify finance team
```

---

**Q7. SQS visibility timeout kya hai?**

```
Visibility Timeout = time given to consumer to process message

Consumer receives message → message becomes INVISIBLE to others
If processed + DeleteMessage called → permanently removed ✅
If consumer crashes → timeout expires → message VISIBLE again → retry ✅

DEFAULT: 30 seconds
If your task takes > 30s:
sqs.change_message_visibility(
    ReceiptHandle=receipt_handle,
    VisibilityTimeout=60,   # extend by 60s
)

BEST PRACTICE:
Set timeout = 2x expected processing time
Change visibility timeout periodically for long tasks
```

---

**Q8. Transaction pe Celery task queue kaise safely karte ho?**

```
PROBLEM:
@receiver(post_save, sender=Booking)
def on_booking_save(sender, instance, created, **kwargs):
    if created:
        send_confirmation.delay(instance.id)
        # Worker runs → DB.get(id) → NOT FOUND YET! (transaction not committed)
        # Race condition!

SOLUTION: transaction.on_commit()
@receiver(post_save, sender=Booking)
def on_booking_save(sender, instance, created, **kwargs):
    if created:
        transaction.on_commit(
            lambda: send_confirmation.delay(instance.id)
        )
        # Task queued ONLY after DB commit
        # Worker runs → DB.get(id) → found ✅
        # If transaction rolls back → task NOT queued ✅

This was one of the first bugs I fixed in Niroskos.
Saw "Booking matching query does not exist" in Celery logs.
Root cause: race condition between signal and worker.
Fix: on_commit wrapper.
```

---

**Q9. Long polling SQS mein kya hai?**

```
SHORT POLLING (bad):
ReceiveMessage called → immediately returns (even if empty)
100 empty calls per second → AWS charges per API call!
Wasteful + expensive.

LONG POLLING (good):
ReceiveMessage(WaitTimeSeconds=20) → waits up to 20s
If message arrives in 20s → returns immediately
If no message in 20s → returns empty
Fewer API calls → cheaper + more responsive

COST:
SQS: $0.40 per million requests
1000 short polls/min = 43M/month = $17.28
With long polling (20s wait): 3 polls/min = 1.3M/month = $0.52

Always use long polling in production.
WaitTimeSeconds=20 (max)
```

---

**Q10. Celery monitoring kaise karte ho production mein?**

```
TOOL 1: Flower (web UI)
pip install flower
celery -A config flower --port=5555 --basic-auth=admin:secret
http://localhost:5555
→ Active tasks, failed tasks, worker status, queue depths

TOOL 2: Celery events + custom logging
@app.task_prerun.connect
def task_started(task_id, task, args, kwargs, **extras):
    logger.info(f"TASK START: {task.name}[{task_id}]")

@app.task_postrun.connect
def task_ended(task_id, task, args, kwargs, retval, state, **extras):
    logger.info(f"TASK END: {task.name}[{task_id}] state={state}")

TOOL 3: pg_stat + Redis monitoring
Check queue depth:
python -c "import redis; r=redis.Redis(); print(r.llen('celery'))"

TOOL 4: Sentry (error tracking)
from sentry_sdk.integrations.celery import CeleryIntegration
sentry_sdk.init(dsn="...", integrations=[CeleryIntegration()])
→ All task failures → Sentry dashboard
```

---

**Q11. DLQ se kaise recover karte ho?**

```
SCENARIO:
Niroskos → SAP HANA API changes response format
100 sync tasks fail → all go to DLQ

RECOVERY PROCESS:
1. Alert milta hai (Sentry / Slack)
2. DLQ messages inspect karo:
   → Parse error: response['ref'] key → response['reference']
3. Code fix deploy karo
4. DLQ se messages requeue karo (SQS):

def requeue_dlq_messages(dlq_url, main_queue_url):
    while True:
        response = sqs.receive_message(
            QueueUrl=dlq_url,
            MaxNumberOfMessages=10
        )
        messages = response.get("Messages", [])
        if not messages:
            break
        for msg in messages:
            # Send to main queue
            sqs.send_message(
                QueueUrl=main_queue_url,
                MessageBody=msg["Body"]
            )
            # Delete from DLQ
            sqs.delete_message(
                QueueUrl=dlq_url,
                ReceiptHandle=msg["ReceiptHandle"]
            )
            print(f"Requeued: {msg['MessageId']}")

LESSON: DLQ = ops safety net. Never ignore DLQ alerts.
```

---

**Q12. Celery beat multiple instances ka issue?**

```
PROBLEM:
2 beat instances → same task scheduled twice
→ duplicate emails, duplicate SAP syncs, data corruption!

SOLUTION 1: Ensure single beat instance
systemd: ExecStart=celery beat (not autoscaling)

SOLUTION 2: Distributed lock (RedBeat)
pip install django-redbeat
CELERY_BEAT_SCHEDULER = "redbeat.RedBeatScheduler"
→ Uses Redis distributed lock
→ Multiple beat processes → only one active at a time
→ Failover: if active dies → another takes over
→ Production HA setup ke liye use karo

SOLUTION 3: Kubernetes (CronJob instead of Beat)
→ K8s manages scheduling
→ One-time job vs persistent beat process
```

---

## QUICK RECALL CARD

```
╔══════════════════════════════════════════════════════════════════╗
║         CELERY · RABBITMQ · SQS RECALL CARD                     ║
╠══════════════════════════════════════════════════════════════════╣
║                                                                  ║
║  CELERY                                                          ║
║  Architecture = Producer → Broker → Worker → Result Backend     ║
║  .delay()     = fire and forget                                  ║
║  .apply_async = with options (queue, eta, countdown)            ║
║  on_commit    = queue AFTER transaction commit (race fix!)       ║
║  ACKS_LATE    = True (process → THEN ack, no task loss)         ║
║  PREFETCH=1   = fair dispatch, one at a time                    ║
║  autoretry    = retry_backoff + retry_jitter (exponential)      ║
║  chain        = sequential (A→B→C)                              ║
║  group        = parallel (all at once)                          ║
║  chord        = parallel + callback (group + final step)        ║
║  Flower       = monitoring UI (port 5555)                       ║
║                                                                  ║
║  RABBITMQ                                                        ║
║  Protocol = AMQP                                                 ║
║  Producer → Exchange → (binding) → Queue → Consumer            ║
║  Exchange types: direct(routing key) / fanout(all) /            ║
║                  topic(pattern) / headers(key-value)            ║
║  Durable queue + persistent message = survives restart          ║
║  Prefetch = basic_qos(prefetch_count=1)                        ║
║  Redis vs RabbitMQ: Redis=simple, RabbitMQ=enterprise          ║
║                                                                  ║
║  SQS                                                             ║
║  Standard    = at-least-once, unlimited TPS, best-effort order  ║
║  FIFO        = exactly-once, 300 TPS, guaranteed order          ║
║  Visibility Timeout = time to process before requeue            ║
║  Long polling = WaitTimeSeconds=20 (cheaper, faster)            ║
║  DeleteMessage = ACK (remove after success)                     ║
║  DLQ = dead letter queue (max N failures → DLQ)                ║
║                                                                  ║
║  PATTERNS                                                        ║
║  Idempotent consumer = check before do (SQS duplicates safe)   ║
║  DLQ recovery = inspect → fix code → requeue                   ║
║  Retry: autoretry + backoff + jitter + on_failure DLQ          ║
║  Priority: separate queues (high/default/low + workers)        ║
║                                                                  ║
║  TERA RESUME:                                                    ║
║  Niroskos   → Celery + Redis broker, booking confirm workflow   ║
║  Youngman   → Celery for SAP HANA async invoice sync           ║
║  Both       → transaction.on_commit() pattern                   ║
╚══════════════════════════════════════════════════════════════════╝
```

---

*Last updated: 2026-08-15 · PwC Interview 2026-08-18*
*Resume skills: Celery · RabbitMQ · AWS SQS · Async Processing*