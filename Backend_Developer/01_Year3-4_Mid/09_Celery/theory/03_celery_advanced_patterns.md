# Celery Advanced Patterns — Interview Prep (40 LPA)
# Theory in Hinglish | English Code/Terms

> **Target:** Python Backend Developer roles at 40 LPA+  
> **Level:** Advanced  
> **Series:** Celery (Year 3-4)  
> **File:** 03_celery_advanced_patterns.md

---

## Table of Contents

1. Canvas — Celery Workflow Primitives
2. Task Signatures and Calling
3. Task Routing
4. Retry Strategies
5. Task Chaining (chain)
6. Groups (Parallel Execution)
7. Chord (Map-Reduce)
8. Celery Beat — Periodic Tasks
9. Task States and Monitoring
10. Flower — Monitoring Dashboard
11. Concurrency and Pool
12. Priority Queues
13. Soft vs Hard Time Limits
14. Production Configuration
15. 10 Interview Q&As

---

## 1. Canvas — Celery Workflow Primitives

### Canvas kya hai?

Canvas Celery ka **workflow composition system** hai. Jab aapko sirf ek task nahi, balki multiple tasks ko ek saath ya sequence mein run karna ho, tab Canvas primitives use karte hain.

Socho production mein order processing pipeline:
- User ne order diya → payment validate karo → inventory update karo → email bhejo → analytics record karo

Yeh sab kaam sequentially ya parallel hone chahiye. Canvas yahi karta hai.

### 1.1 chain() — Sequential Execution

**Concept:** Ek task ka output, next task ka input ban jaata hai.

```python
from celery import chain

# Syntax
result = chain(task1.s(args), task2.s(), task3.s())()

# Real example — data pipeline
pipeline = chain(
    fetch_user_data.s(user_id),      # Step 1: DB se data fetch karo
    enrich_with_crm.s(),              # Step 2: CRM data add karo (prev result milega)
    calculate_score.s(),              # Step 3: Score calculate karo
    update_user_record.s()            # Step 4: DB update karo
)
result = pipeline.apply_async()
final = result.get(timeout=60)
```

**Important:** `|` operator bhi chain banata hai:

```python
# Yeh dono equivalent hain:
pipeline = fetch_data.s(url) | process.s() | save.s()
pipeline = chain(fetch_data.s(url), process.s(), save.s())
```

**Kab use karein:**
- ETL pipelines
- Multi-step order processing
- Sequential API calls jahan ek ka result doosre ko chahiye

### 1.2 group() — Parallel Execution

**Concept:** Multiple tasks simultaneously run hoti hain, saari complete hone ka wait karo.

```python
from celery import group

# Syntax
result = group(task.s(arg) for arg in items)()

# Real example — bulk notifications
notification_tasks = group(
    send_push.s(user_id, message),
    send_email.s(user_id, message),
    send_sms.s(user_id, message)
)
result = notification_tasks.apply_async()
results = result.get(timeout=30)  # list of results from all 3
```

**Key points:**
- Saari tasks **independently** run hoti hain — ek fail ho to doosri continue karti hain
- `result.get()` list return karta hai (order preserved)
- `result.successful()` — check if all tasks passed
- `result.failed()` — check if any task failed

### 1.3 chord() — Parallel → Callback (Map-Reduce)

**Concept:** Pehle group mein sab tasks parallel run hoti hain, phir ek **callback** unke results leke chalta hai.

```python
from celery import chord

# Syntax
chord(group_of_tasks)(callback_task)

# Real example — price comparison
scraping_tasks = group(
    scrape_amazon.s(product_id),
    scrape_flipkart.s(product_id),
    scrape_myntra.s(product_id)
)
result = chord(scraping_tasks)(find_best_price.s())
best = result.get(timeout=60)  # callback ka result
```

**Behind the scenes:**
1. `chord_unlock` task periodically check karta hai kya saare group tasks done hain
2. Jab sab complete ho jaayein, callback ko list of results pass karta hai
3. **Result backend required** — Redis ya DB mein results store hote hain

### 1.4 starmap() — Tuple Unpacking ke saath Map

```python
from celery import starmap

# Agar task multiple args leta ho
# add(2, 3), add(4, 5), add(6, 7) — tuple list se
result = add.starmap([(2, 3), (4, 5), (6, 7)]).apply_async()
# Equivalent to: [add(2,3), add(4,5), add(6,7)]
```

### 1.5 chunks() — Iterable ko Chunks mein Split karo

```python
# Agar 1000 items hain, 100-100 ke batches mein process karo
result = process_item.chunks(zip(range(1000)), 100).apply_async()
# Yeh 10 groups of 100 banata hai
```

**Use case:** Large datasets ko manageable batches mein process karna — heavy DB imports, bulk file processing.

### 1.6 map() — Apply Task to Iterable

```python
# Simple map — ek task ko list ke har element pe apply karo
result = process_item.map([1, 2, 3, 4, 5]).apply_async()
```

### 1.7 Complex Workflows — Chain of Groups, Nested Chords

**Real-world pattern — E-commerce order fulfillment:**

```python
from celery import chain, group, chord

order_workflow = chain(
    validate_order.s(order_id),                    # Step 1: validate
    chord(                                          # Step 2: parallel processing
        group(
            charge_payment.s(),
            reserve_inventory.s(),
            notify_warehouse.s()
        )
    )(fulfillment_confirmed.s()),                  # Step 3: callback after all 3 done
    chain(
        generate_invoice.s(),                      # Step 4: invoice
        send_confirmation_email.s()                # Step 5: email
    )
)
result = order_workflow.apply_async()
```

### 1.8 Immutable Signatures — `.si()` vs `.s()`

**Yeh ek bahut important distinction hai:**

```python
# .s() — MUTABLE signature
# Parent task ka result next task ko argument ke roop mein milta hai
chain(task_a.s(), task_b.s())()
# task_b ko task_a ka result milega as first argument

# .si() — IMMUTABLE signature  
# Parent ka result IGNORE ho jaata hai
chain(send_email.s(user_id), log_event.si("email_sent"))()
# log_event ko "email_sent" hi milega, send_email ka result nahi
```

**Kab `.si()` use karein:**
- Jab task chain mein hai, lekin pichle task ke result se koi matlab nahi
- Side effects ke liye (logging, auditing, cleanup)
- Jab task apne arguments khud se lete hain

```python
# Pattern: main pipeline + side effects
pipeline = chain(
    process_payment.s(order_id),
    group(
        update_order_status.s(),           # .s() — payment result chahiye
        send_receipt.si(user_id),          # .si() — bas user_id chahiye, result nahi
        log_transaction.si(order_id)       # .si() — audit log, result se koi matlab nahi
    )
)
```

---

## 2. Task Signatures and Calling

### 2.1 Teen Tarike — `.delay()` vs `.apply_async()` vs `.apply()`

```python
# 1. .delay() — simplest, shorthand for apply_async
task.delay(arg1, arg2, kwarg=value)
# Equivalent to:
task.apply_async(args=[arg1, arg2], kwargs={'kwarg': value})

# 2. .apply_async() — full control
task.apply_async(
    args=[arg1, arg2],
    kwargs={'key': 'value'},
    countdown=60,           # 60 seconds baad run karo
    eta=datetime(2024, 1, 1, 8, 0),  # specific time pe run karo
    expires=3600,           # 1 hour baad expire kar do
    queue='high_priority',  # specific queue pe bhejo
    priority=9,             # highest priority
    task_id='my-custom-id'  # custom ID
)

# 3. .apply() — SYNCHRONOUS, broker ko bypass karta hai
# Testing ke liye use karo, production mein mat use karo
result = task.apply(args=[arg1])
value = result.get()  # immediately available
```

**Interview tip:** `.apply()` testing ke liye perfect hai — broker chahiye nahi, aur task synchronously execute hota hai. Production mein kabhi mat use karo.

### 2.2 countdown= — Delay in Seconds

```python
# 5 minutes baad run karo
send_reminder.apply_async(args=[user_id], countdown=300)

# Use case: payment retry after 1 hour
process_payment.apply_async(args=[order_id], countdown=3600)
```

### 2.3 eta= — Execute at Datetime

```python
from datetime import datetime, timezone

# Monday 9 AM UTC pe run karo
next_monday = datetime(2024, 1, 8, 9, 0, tzinfo=timezone.utc)
send_weekly_report.apply_async(eta=next_monday)
```

**Difference:** `countdown` relative hai (X seconds baad), `eta` absolute hai (specific datetime).

### 2.4 expires= — Task Deadline

```python
# Agar task 5 minutes mein start nahi hua to discard kar do
send_flash_sale_notification.apply_async(
    args=[sale_id],
    expires=300  # seconds
)

# Ya datetime se:
from datetime import datetime, timedelta
deadline = datetime.utcnow() + timedelta(hours=2)
task.apply_async(expires=deadline)
```

**Use case:** Flash sale notifications, OTP sends — stale hone ke baad useless hain.

### 2.5 queue= — Route to Specific Queue

```python
# High priority task ko dedicated queue pe bhejo
send_payment_alert.apply_async(args=[user_id], queue='high_priority')

# Email tasks ko email queue pe
send_newsletter.apply_async(args=[campaign_id], queue='email')

# Analytics ko alag queue pe — main pipeline affect nahi hogi
track_event.apply_async(args=[event_data], queue='analytics')
```

### 2.6 priority= — 0-9

```python
# RabbitMQ ke saath kaam karta hai
# 9 = highest priority, 0 = lowest
urgent_task.apply_async(priority=9)
normal_task.apply_async(priority=5)
batch_job.apply_async(priority=1)
```

**Note:** Redis ke saath priority limited support hai — multiple queues use karo.

### 2.7 soft_time_limit vs time_limit

```python
@app.task(
    soft_time_limit=55,  # 55 seconds baad SoftTimeLimitExceeded raise hoga
    time_limit=60        # 60 seconds baad SIGKILL (immediate death)
)
def long_task():
    try:
        # ... kaam karo
        pass
    except SoftTimeLimitExceeded:
        # Graceful cleanup
        save_progress()
        cleanup_temp_files()
        raise  # re-raise so task fails properly
```

### 2.8 task_id= — Custom Task ID

```python
import uuid

# Custom ID assign karo taaki baad mein track kar sako
order_id = "ORD-12345"
task_id = f"process-order-{order_id}"

result = process_order.apply_async(
    args=[order_id],
    task_id=task_id
)

# Later kisi bhi jagah se check karo:
from celery.result import AsyncResult
status = AsyncResult(task_id).state  # "PENDING", "SUCCESS", etc.
```

---

## 3. Task Routing

### 3.1 Multiple Queues — CELERY_TASK_ROUTES

Ek hi queue mein sab tasks daalna — galat practice hai production mein. Socho:
- Payment task queue jam ho gayi critical newsletter task ki wajah se — disaster!

```python
# celeryconfig.py
CELERY_TASK_ROUTES = {
    'myapp.tasks.send_email': {'queue': 'email'},
    'myapp.tasks.process_payment': {'queue': 'high_priority'},
    'myapp.tasks.generate_report': {'queue': 'reports'},
    'myapp.tasks.track_analytics': {'queue': 'analytics'},
    'myapp.tasks.*': {'queue': 'default'},  # wildcard — baaki sab default mein
}
```

### 3.2 task_queues with Exchange and Queue

```python
from kombu import Exchange, Queue

# RabbitMQ ke liye proper setup
CELERY_TASK_QUEUES = (
    Queue('default', Exchange('default'), routing_key='default'),
    Queue('high_priority', Exchange('high_priority'), routing_key='high_priority'),
    Queue('email', Exchange('email'), routing_key='email'),
    Queue('analytics', Exchange('analytics'), routing_key='analytics'),
)

CELERY_DEFAULT_QUEUE = 'default'
CELERY_DEFAULT_EXCHANGE = 'default'
CELERY_DEFAULT_ROUTING_KEY = 'default'
```

### 3.3 Direct Routing — Queues ka Architecture

```
┌─────────────────────────────────────────────────┐
│                   Producer                       │
│          (FastAPI / Django views)                │
└──────────┬──────────┬──────────┬────────────────┘
           │          │          │
           ▼          ▼          ▼
    ┌──────────┐ ┌──────────┐ ┌──────────┐
    │ default  │ │  email   │ │analytics │
    │  queue   │ │  queue   │ │  queue   │
    └────┬─────┘ └────┬─────┘ └────┬─────┘
         │             │             │
         ▼             ▼             ▼
    ┌──────────┐ ┌──────────┐ ┌──────────┐
    │ Worker 1 │ │ Worker 2 │ │ Worker 3 │
    │ Worker 2 │ │          │ │          │
    │ Worker 3 │ │          │ │          │
    └──────────┘ └──────────┘ └──────────┘
```

### 3.4 @app.task(queue='email') — Default Queue for Task

```python
@app.task(queue='email')
def send_welcome_email(user_id: str):
    """Yeh task automatically 'email' queue mein jaayegi"""
    pass

@app.task(queue='high_priority')
def process_refund(order_id: str):
    """Critical task — dedicated queue"""
    pass
```

### 3.5 Workers Consuming Specific Queues

```bash
# 3 workers on default + high_priority
celery -A myapp worker -Q default,high_priority --concurrency=4

# Dedicated email worker
celery -A myapp worker -Q email --concurrency=2 -n email_worker@%h

# Analytics worker — low priority, kan bulk handle kare
celery -A myapp worker -Q analytics --concurrency=8 -n analytics@%h
```

### 3.6 Dead Letter Queue (DLQ) Pattern

**Concept:** Baar baar fail hone wali tasks ko ek alag "dead" queue mein daal do, taaki unhe manually inspect kar sako.

```python
# RabbitMQ ke saath
from kombu import Exchange, Queue

# DLQ setup
dead_letter_exchange = Exchange('dead_letter', type='direct')
CELERY_TASK_QUEUES = (
    Queue(
        'default',
        Exchange('default'),
        routing_key='default',
        queue_arguments={
            'x-dead-letter-exchange': 'dead_letter',
            'x-dead-letter-routing-key': 'dead'
        }
    ),
    Queue('dead_letter', dead_letter_exchange, routing_key='dead'),
)

# Task max retries exhaust hone ke baad DLQ mein chali jaayegi
@app.task(max_retries=3, acks_late=True)
def risky_task(data):
    try:
        process(data)
    except Exception as exc:
        raise self.retry(exc=exc)
```

---

## 4. Retry Strategies

### 4.1 Basic Retry

```python
@app.task(bind=True, max_retries=3)
def send_notification(self, user_id: str, message: str):
    try:
        result = notification_api.send(user_id, message)
        return result
    except (ConnectionError, TimeoutError) as exc:
        # 60 seconds baad retry karo
        raise self.retry(exc=exc, countdown=60)
```

**`bind=True` kyon?** Taaki `self` available ho — `self.retry()`, `self.request.retries` access kar sako.

### 4.2 Exponential Backoff (Manual)

```python
@app.task(bind=True, max_retries=5)
def call_external_api(self, payload: dict):
    try:
        return requests.post("https://api.third-party.com/data", json=payload, timeout=10)
    except requests.RequestException as exc:
        # 2^0=1s, 2^1=2s, 2^2=4s, 2^3=8s, 2^4=16s
        backoff = 2 ** self.request.retries
        raise self.retry(exc=exc, countdown=backoff)
```

**Kyon exponential backoff?**
- Agar server overloaded hai, immediately retry karna aur load badh jaata hai
- Exponential backoff server ko "breathe" karne ka time deta hai

### 4.3 autoretry_for — Automatic Retry on Exceptions

```python
@app.task(
    autoretry_for=(ConnectionError, TimeoutError, requests.RequestException),
    max_retries=3,
    retry_backoff=True,          # automatic exponential backoff
    retry_backoff_max=600,       # max 10 minutes wait
    retry_jitter=True            # randomness add karo
)
def fetch_data(url: str):
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    return response.json()
```

### 4.4 retry_jitter — Thundering Herd Problem Solve karo

**Problem:** 100 tasks fail hoti hain, sab exact same time pe retry karti hain → server crash!

**Solution:** Jitter (randomness) add karo taaki retries spread out ho jaayein.

```python
@app.task(
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_jitter=True   # Adds random offset to backoff time
)
def task_with_jitter(data):
    pass
```

### 4.5 on_failure Callback

```python
def on_task_failure(exc, task_id, args, kwargs, einfo):
    """Jab task permanently fail ho jaaye"""
    logger.error(f"Task {task_id} permanently failed: {exc}")
    # Alert bhejo, Slack notification, PagerDuty, etc.
    send_alert_to_oncall(f"Critical task failed: {task_id}")

@app.task(
    bind=True,
    max_retries=3,
    on_failure=on_task_failure
)
def critical_task(self, data):
    pass
```

---

## 5. Task Chaining (chain) — Deep Dive

### 5.1 Result Passing

```python
# Har step previous step ka result receive karta hai

@app.task
def fetch_data(url: str) -> dict:
    return requests.get(url).json()  # {'users': [...], 'count': 100}

@app.task
def filter_active(data: dict) -> list:
    # 'data' = fetch_data ka result
    return [u for u in data['users'] if u['active']]

@app.task
def send_emails(users: list) -> dict:
    # 'users' = filter_active ka result
    sent = 0
    for user in users:
        email_service.send(user['email'])
        sent += 1
    return {'sent': sent}

# Chain execute karo
pipeline = chain(
    fetch_data.s("https://api.example.com/users"),
    filter_active.s(),
    send_emails.s()
)
result = pipeline.apply_async()
final = result.get(timeout=120)  # {'sent': 75}
```

### 5.2 Error in Chain

```python
# Agar koi ek task fail ho, baaki skip ho jaati hain

pipeline = chain(
    step1.s(),   # ✓ success
    step2.s(),   # ✗ FAIL — exception raise karta hai
    step3.s(),   # ✗ SKIPPED — never runs
    step4.s()    # ✗ SKIPPED — never runs
)

try:
    result = pipeline.apply_async()
    final = result.get(timeout=60)
except Exception as e:
    print(f"Chain failed at some step: {e}")
```

### 5.3 .on_error() — Handle Chain Failure

```python
@app.task
def handle_pipeline_error(uuid):
    """Jab chain mein koi task fail ho"""
    result = AsyncResult(uuid)
    logger.error(f"Pipeline failed: {result.traceback}")
    notify_admin(f"Data pipeline failed: {uuid}")

pipeline = chain(
    fetch_data.s(url),
    process_data.s(),
    save_results.s()
).on_error(handle_pipeline_error.s())

result = pipeline.apply_async()
```

### 5.4 Immutable Chain Pattern

```python
# Yeh ek common pattern hai — pipeline + audit logging

@app.task
def process_payment(order_id: str) -> dict:
    return {"order_id": order_id, "amount": 1000, "status": "charged"}

@app.task
def update_order_db(payment_result: dict) -> dict:
    # payment_result ka use karke DB update karo
    db.update_order(payment_result)
    return payment_result

@app.task
def send_receipt(payment_result: dict):
    # payment_result se email info extract karo
    email_service.send_receipt(payment_result)

@app.task
def log_to_audit(order_id: str):
    # Yeh task .si() ke saath use hogi — result ignore karega
    audit_log.record(order_id, "payment_processed", timestamp=now())

# Chain with immutable side effects
pipeline = chain(
    process_payment.s(order_id),
    update_order_db.s(),
    send_receipt.s(),
    log_to_audit.si(order_id)   # .si() — audit ke liye original order_id chahiye
)
```

---

## 6. Groups (Parallel Execution) — Deep Dive

### 6.1 Basic Group

```python
from celery import group

@app.task
def process_image(image_id: str, format: str) -> dict:
    """Single image ko ek format mein convert karo"""
    converted = image_converter.convert(image_id, format)
    return {"image_id": image_id, "format": format, "url": converted.url}

# Ek image ko multiple formats mein parallel convert karo
image_id = "img_12345"
conversion_group = group(
    process_image.s(image_id, "webp"),
    process_image.s(image_id, "jpg"),
    process_image.s(image_id, "thumb_jpg"),
    process_image.s(image_id, "mobile_webp")
)

group_result = conversion_group.apply_async()
results = group_result.get(timeout=60)
# results = [
#   {"image_id": "img_12345", "format": "webp", "url": "..."},
#   {"image_id": "img_12345", "format": "jpg", "url": "..."},
#   ...
# ]
```

### 6.2 AsyncResult for Group

```python
group_result = my_group.apply_async()

# Sab complete hone ka wait karo
results = group_result.get(timeout=120)

# Status check (blocking nahi)
print(group_result.successful())   # True agar sab pass
print(group_result.failed())       # True agar koi fail
print(group_result.ready())        # True agar sab done (success ya fail)
print(group_result.waiting())      # True agar koi pending hai

# Individual results
for async_result in group_result.results:
    print(async_result.state, async_result.result)
```

### 6.3 Error Handling in Groups

```python
# Group mein ek task fail ho to baaki continue karti hain (chain se alag!)

group_result = my_group.apply_async()
results = []

# Individual results check karo
for async_result in group_result.results:
    try:
        result = async_result.get(timeout=30)
        results.append(result)
    except Exception as e:
        logger.error(f"Task {async_result.id} failed: {e}")
        results.append(None)  # ya error object

successful = [r for r in results if r is not None]
print(f"Completed: {len(successful)}/{len(group_result.results)}")
```

### 6.4 Dynamic Groups

```python
# Runtime pe group create karo

def bulk_process_orders(order_ids: list):
    """Large list of orders ko parallel process karo"""
    task_group = group(
        process_single_order.s(order_id)
        for order_id in order_ids
    )
    result = task_group.apply_async()
    return result.id  # Frontend ko ye ID return karo tracking ke liye
```

---

## 7. Chord (Map-Reduce) — Deep Dive

### 7.1 Anatomy of a Chord

```python
from celery import chord, group

# Chord = group + callback
# Callback ko group ke SARE results ek list mein milte hain

@app.task
def analyze_sentiment(review_text: str) -> dict:
    """Single review ka sentiment analyze karo"""
    score = ml_model.predict(review_text)
    return {"text": review_text[:50], "score": score}

@app.task
def aggregate_sentiment(results: list) -> dict:
    """Callback: sare reviews ka aggregate"""
    scores = [r["score"] for r in results]
    return {
        "total_reviews": len(scores),
        "avg_sentiment": sum(scores) / len(scores),
        "positive": sum(1 for s in scores if s > 0.5),
        "negative": sum(1 for s in scores if s <= 0.5)
    }

# Chord execute karo
reviews = get_product_reviews(product_id)  # 500 reviews

analysis = chord(
    group(analyze_sentiment.s(review) for review in reviews)
)(aggregate_sentiment.s())

final_report = analysis.get(timeout=300)
```

### 7.2 chord_unlock — Internal Mechanism

```
Chord kaise kaam karta hai:

1. Group ki saari tasks queue mein jaati hain
2. chord_unlock task periodically check karta hai (every 1 second by default)
3. Jab sari tasks complete ho jaayein:
   - Callback ko results ki list pass ki jaati hai
   - chord_unlock khud terminate ho jaata hai
4. Callback task execute hoti hai
```

```python
# chord_unlock interval configure karo
app.conf.CELERY_CHORD_UNLOCK_MAX_RETRIES = 1000  # max 1000 checks
# Default interval 1 second, chord timeout ke liye use karo:
result = chord(tasks)(callback.s()).apply_async()
callback_result = result.get(timeout=600)  # max 10 minutes
```

### 7.3 Result Backend Required

```python
# WRONG — chord ka result backend ke bina kaam nahi karta
app = Celery('tasks', broker='redis://localhost:6379/0')
# ^ Result backend set nahi kiya — chord fail hogi!

# CORRECT
app = Celery(
    'tasks',
    broker='redis://localhost:6379/0',
    backend='redis://localhost:6379/1'  # Result backend REQUIRED for chord
)
```

### 7.4 Real Use Case — Parallel API Calls → Aggregate

```python
@app.task(
    autoretry_for=(requests.RequestException,),
    retry_backoff=True,
    max_retries=3
)
def fetch_exchange_rate(currency_pair: str) -> dict:
    """Single currency pair ka exchange rate fetch karo"""
    response = requests.get(
        f"https://api.exchangerates.io/latest?base={currency_pair[:3]}&symbols={currency_pair[3:]}",
        timeout=10
    )
    data = response.json()
    return {
        "pair": currency_pair,
        "rate": data["rates"][currency_pair[3:]],
        "timestamp": data["date"]
    }

@app.task
def build_forex_dashboard(rates: list) -> dict:
    """Callback: saare rates se dashboard data build karo"""
    return {
        pair: {"rate": rate, "timestamp": ts}
        for item in rates
        for pair, rate, ts in [(item["pair"], item["rate"], item["timestamp"])]
    }

# 20 currency pairs parallel fetch karo
currency_pairs = ["USDINR", "EURINR", "GBPINR", "JPYINR", "AUDINR",
                  "CADINR", "CHFINR", "CNHINR", "SGDINR", "HKDINR"]

dashboard = chord(
    group(fetch_exchange_rate.s(pair) for pair in currency_pairs)
)(build_forex_dashboard.s())

forex_data = dashboard.get(timeout=60)
```

---

## 8. Celery Beat — Periodic Tasks

### 8.1 beat_schedule Configuration

```python
# celeryconfig.py
from celery.schedules import crontab
from datetime import timedelta

app.conf.beat_schedule = {
    # 1. Har 30 second mein
    'heartbeat': {
        'task': 'tasks.system_heartbeat',
        'schedule': timedelta(seconds=30),
    },

    # 2. Har 5 minute mein
    'sync-cache': {
        'task': 'tasks.refresh_cache',
        'schedule': crontab(minute='*/5'),
        'args': ('product_catalog',),
    },

    # 3. Daily 8 AM pe
    'daily-report': {
        'task': 'tasks.send_daily_report',
        'schedule': crontab(hour=8, minute=0),
        'kwargs': {'report_type': 'summary'},
    },

    # 4. Every Monday 9 AM
    'weekly-digest': {
        'task': 'tasks.send_weekly_digest',
        'schedule': crontab(hour=9, minute=0, day_of_week='monday'),
    },

    # 5. Month ka pehla din midnight pe
    'monthly-billing': {
        'task': 'tasks.process_monthly_billing',
        'schedule': crontab(day_of_month=1, hour=0, minute=0),
    },
}

app.conf.timezone = 'Asia/Kolkata'  # IST timezone
```

### 8.2 crontab() — All Options

```python
from celery.schedules import crontab

# Minute expressions
crontab(minute=0)           # har ghante ki 0th minute
crontab(minute='*/15')      # har 15 minute
crontab(minute='0,30')      # minute 0 aur 30

# Hour expressions
crontab(hour=9)             # 9 AM
crontab(hour='9-17')        # 9 AM se 5 PM tak
crontab(hour='*/2')         # har 2 ghante

# Day of week (0=Sunday, 1=Monday, ..., 6=Saturday)
crontab(day_of_week='monday')
crontab(day_of_week='1,3,5')  # Mon, Wed, Fri
crontab(day_of_week='1-5')    # Weekdays

# Day of month
crontab(day_of_month=1)       # Month ka pehla din
crontab(day_of_month='1,15')  # 1st aur 15th

# Month
crontab(month_of_year=3)      # March
crontab(month_of_year='3,6,9,12')  # Quarterly

# Complex
crontab(
    hour=9,
    minute=30,
    day_of_week='monday-friday',
    month_of_year='*'
)  # Weekdays 9:30 AM
```

### 8.3 django-celery-beat — DB-Stored Schedules

**Problem:** `beat_schedule` file mein hardcoded hai — change karne ke liye code redeploy karna padega.

**Solution:** `django-celery-beat` — schedules DB mein store hote hain, Django admin se change kar sako.

```bash
pip install django-celery-beat
```

```python
# settings.py
INSTALLED_APPS = [
    ...
    'django_celery_beat',
]

# celery.py
app.conf.beat_scheduler = 'django_celery_beat.schedulers:DatabaseScheduler'
```

```bash
python manage.py migrate  # Creates periodic_tasks table
celery -A myapp beat -l info --scheduler django_celery_beat.schedulers:DatabaseScheduler
```

Ab Django admin se `/admin/django_celery_beat/periodictask/` pe jaao aur tasks manage karo.

### 8.4 Beat Worker Run karna

```bash
# Beat aur worker alag processes mein run honi chahiye!

# Terminal 1: Worker
celery -A myapp worker -l info

# Terminal 2: Beat scheduler
celery -A myapp beat -l info

# Ya combined (development only):
celery -A myapp worker --beat -l info
```

**Production mein NEVER combined run karo** — agar worker crash ho to beat bhi band ho jaayegi.

### 8.5 Timezone Handling

```python
# celeryconfig.py
CELERY_TIMEZONE = 'Asia/Kolkata'      # IST
CELERY_ENABLE_UTC = True              # Internal storage UTC mein, display IST mein

# Verify:
from celery.utils.time import timezone
print(timezone.get_timezone('Asia/Kolkata'))
```

---

## 9. Task States and Monitoring

### 9.1 Task Lifecycle

```
PENDING → STARTED → SUCCESS
                  → FAILURE
                  → RETRY → STARTED → ...
         → REVOKED
```

| State    | Matlab                                         |
|----------|------------------------------------------------|
| PENDING  | Task queue mein wait kar rahi hai              |
| STARTED  | Worker ne task uthaa li, execute ho rahi hai   |
| SUCCESS  | Task successfully complete                     |
| FAILURE  | Task fail ho gayi (exception raise hua)        |
| RETRY    | Task retry hone wali hai                       |
| REVOKED  | Task cancel kar di gayi                        |

### 9.2 Custom States — Progress Tracking

```python
@app.task(bind=True)
def import_csv(self, file_path: str):
    """CSV import karo aur progress track karo"""
    rows = read_csv(file_path)
    total = len(rows)

    for i, row in enumerate(rows):
        process_row(row)

        # Har 10% pe update karo
        if i % (total // 10) == 0:
            self.update_state(
                state='PROGRESS',
                meta={
                    'current': i,
                    'total': total,
                    'percent': int(i / total * 100),
                    'status': f'Processing row {i}/{total}'
                }
            )

    return {'imported': total, 'status': 'complete'}

# Frontend polling (FastAPI example)
@router.get("/import-status/{task_id}")
def get_import_status(task_id: str):
    result = AsyncResult(task_id)

    if result.state == 'PENDING':
        return {"status": "waiting", "percent": 0}
    elif result.state == 'PROGRESS':
        return {
            "status": "processing",
            "percent": result.info.get('percent', 0),
            "current": result.info.get('current', 0),
            "total": result.info.get('total', 0)
        }
    elif result.state == 'SUCCESS':
        return {"status": "complete", "percent": 100, "result": result.result}
    elif result.state == 'FAILURE':
        return {"status": "failed", "error": str(result.result)}
```

### 9.3 AsyncResult — Full API

```python
from celery.result import AsyncResult

task_id = "some-task-uuid"
result = AsyncResult(task_id)

# State
print(result.state)        # 'PENDING', 'SUCCESS', etc.
print(result.status)       # Same as state

# Result (raises exception if task failed)
print(result.result)       # Task ka return value (ya exception object)

# Blocking get
try:
    value = result.get(timeout=30)    # Timeout seconds
except TimeoutError:
    print("Task ne 30 seconds mein complete nahi kiya")
except Exception as e:
    print(f"Task failed: {e}")

# Non-blocking
if result.ready():          # Done? (success ya failure)
    if result.successful(): # Success?
        value = result.result
    else:                   # Failure
        tb = result.traceback

# Revoke — cancel a pending task
result.revoke()                        # Soft revoke (agar start nahi hua)
result.revoke(terminate=True)          # Hard kill (agar chal raha hai)
result.revoke(terminate=True, signal='SIGKILL')  # Immediate kill

# Forget — result backend se delete karo
result.forget()
```

### 9.4 CELERY_TASK_TRACK_STARTED

```python
# By default STARTED state set nahi hoti
# Yeh enable karo agar aapko pata karna ho kab task shuru hua

app.conf.task_track_started = True  # CELERY_TASK_TRACK_STARTED

# Ab result.state 'STARTED' return karega jab worker task run kar raha ho
```

---

## 10. Flower — Monitoring Dashboard

### 10.1 Installation and Start

```bash
pip install flower

# Basic start
celery -A myapp flower --port=5555

# With authentication
celery -A myapp flower --port=5555 --basic_auth=admin:secret

# With broker URL explicitly
celery -A myapp flower --broker=redis://localhost:6379/0 --port=5555
```

### 10.2 Flower Features

Flower `http://localhost:5555` pe available hota hai:

- **Dashboard:** Real-time task count, worker status
- **Workers tab:** Kaunsa worker active hai, kitni tasks run ho rahi hain
- **Tasks tab:** Recent tasks, unka state, execution time
- **Broker tab:** Queue sizes, message counts

### 10.3 Flower REST API

```bash
# All tasks
curl http://localhost:5555/api/tasks

# Specific task
curl http://localhost:5555/api/task/info/TASK-UUID

# All workers
curl http://localhost:5555/api/workers

# Revoke task via API
curl -X POST http://localhost:5555/api/task/revoke/TASK-UUID?terminate=true

# Worker pool info
curl http://localhost:5555/api/workers?refresh=true
```

```python
# Python mein Flower API use karo
import requests

flower_url = "http://localhost:5555"

def get_active_tasks():
    resp = requests.get(f"{flower_url}/api/tasks?state=STARTED")
    return resp.json()

def revoke_task(task_id: str):
    resp = requests.post(f"{flower_url}/api/task/revoke/{task_id}?terminate=true")
    return resp.json()
```

---

## 11. Concurrency and Pool

### 11.1 --concurrency

```bash
# 4 parallel worker processes
celery -A myapp worker --concurrency=4

# Rule of thumb:
# CPU-bound tasks: CPU cores ke barabar ya thoda kam
# I/O-bound tasks (DB, API calls): CPU cores se zyada
```

### 11.2 Pool Types

**Prefork (Default) — Multiprocessing:**
```bash
celery -A myapp worker --pool=prefork --concurrency=4
```
- Har worker ek **alag process** hai (Python GIL se free)
- CPU-bound tasks ke liye best: data processing, ML inference, image processing
- High memory overhead — 4 workers = 4 Python processes

**Eventlet/Gevent — Coroutines:**
```bash
pip install eventlet  # ya gevent
celery -A myapp worker --pool=eventlet --concurrency=1000
```
- Single process mein thousands of concurrent tasks
- I/O-bound tasks ke liye best: API calls, DB queries, file reads
- Tasks ko blocking I/O pe pause karna aur doosri task run karna
- **Monkey patching** required — third-party libraries ka blocking I/O replace hota hai

```python
# Eventlet ke saath celery.py mein add karo:
import eventlet
eventlet.monkey_patch()
```

**Solo Pool — Single-Threaded:**
```bash
celery -A myapp worker --pool=solo
```
- Single process, single thread
- Debugging ke liye useful (pdb, breakpoints work karte hain)
- Production mein mat use karo

### 11.3 --autoscale

```bash
# Workers ko demand ke hisaab se scale karo
celery -A myapp worker --autoscale=10,3
# min 3 workers, max 10 workers
# Load increase pe auto-scale up, decrease pe scale down

# Useful configuration:
celery -A myapp worker \
    --autoscale=20,2 \
    --concurrency=4 \
    --pool=prefork \
    -Q default,high_priority
```

---

## 12. Priority Queues

### 12.1 RabbitMQ Priority

```python
from kombu import Exchange, Queue

# RabbitMQ x-max-priority argument
CELERY_TASK_QUEUES = [
    Queue(
        'tasks',
        Exchange('tasks'),
        routing_key='tasks',
        queue_arguments={'x-max-priority': 10}  # 0-10 priority range
    )
]

# High priority task
urgent_task.apply_async(priority=9, queue='tasks')

# Normal task
normal_task.apply_async(priority=5, queue='tasks')

# Background task
background_task.apply_async(priority=1, queue='tasks')
```

### 12.2 Redis — Multiple Queues as Priority

Redis mein native priority nahi hai. Pattern: alag queues, alag workers.

```python
# 3 priority levels = 3 separate queues
PRIORITY_QUEUES = {
    'high': 'tasks:high',
    'normal': 'tasks:normal',
    'low': 'tasks:low'
}

# Worker assignments
# bash:
# celery -A myapp worker -Q tasks:high -c 4 -n high_worker@%h
# celery -A myapp worker -Q tasks:normal -c 4 -n normal_worker@%h
# celery -A myapp worker -Q tasks:high,tasks:normal,tasks:low -c 2 -n general_worker@%h
```

### 12.3 Production Priority Pattern

```
Priority Setup (3 machines example):
- Machine 1: 3 workers on high_priority + 1 on default
- Machine 2: 3 workers on default + 1 on email
- Machine 3: 2 workers on analytics + 1 on reports + 1 on default
```

```python
@app.task(queue='high_priority')
def process_payment(order_id: str):
    """Critical — dedicated workers"""
    pass

@app.task(queue='default')
def generate_thumbnail(image_id: str):
    """Normal priority"""
    pass

@app.task(queue='analytics')
def track_page_view(page_data: dict):
    """Low priority — analytics can wait"""
    pass
```

---

## 13. Soft vs Hard Time Limits

### 13.1 Soft Time Limit — Graceful Shutdown

```python
from celery.exceptions import SoftTimeLimitExceeded

@app.task(soft_time_limit=55, time_limit=60)
def process_large_file(file_id: str):
    temp_files = []
    connection = None

    try:
        connection = db.get_connection()
        data = read_large_file(file_id)
        temp_files = create_temp_files(data)

        result = heavy_processing(data)
        save_result(result)
        return {"processed": True, "file_id": file_id}

    except SoftTimeLimitExceeded:
        # 55 seconds pe yahan aao — cleanup time hai!
        logger.warning(f"Soft time limit hit for file {file_id}")

        # Cleanup karo gracefully
        for temp in temp_files:
            os.remove(temp)
        if connection:
            connection.close()

        # Partial progress save karo (optional)
        save_partial_progress(file_id)

        raise  # Exception re-raise karo taaki task FAILED mark ho

    finally:
        # Finally block ALWAYS run karta hai
        if connection:
            connection.close()
```

### 13.2 Hard Time Limit — Nuclear Option

```
soft_time_limit: Python exception raise karta hai → catchable → cleanup possible
time_limit:      SIGKILL bhejta hai → immediate process termination → no cleanup!
```

```python
# Production best practice:
# soft_time_limit = expected_time * 1.5
# time_limit = expected_time * 2

# Agar task 30 seconds mein complete hona chahiye:
@app.task(soft_time_limit=45, time_limit=60)
def expected_30_second_task():
    pass
```

---

## 14. Production Configuration

### 14.1 Complete Production Config

```python
# celeryconfig.py — Production Ready

# Broker and Backend
CELERY_BROKER_URL = 'redis://redis:6379/0'
CELERY_RESULT_BACKEND = 'redis://redis:6379/1'

# Serialization — JSON is safe and readable
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_ACCEPT_CONTENT = ['json']

# Task Acknowledgment
CELERY_TASK_ACKS_LATE = True        # Task complete hone ke baad ack karo (not on receive)
CELERY_WORKER_PREFETCH_MULTIPLIER = 1  # Fair distribution — ek kaam pura karo phir naya lo
CELERY_TASK_REJECT_ON_WORKER_LOST = True  # Worker crash pe task reject karo (re-queue hogi)

# Retry defaults
CELERY_TASK_MAX_RETRIES = 3
CELERY_TASK_DEFAULT_RETRY_DELAY = 60  # 60 second between retries

# Time limits
CELERY_TASK_SOFT_TIME_LIMIT = 300   # 5 minutes default soft limit
CELERY_TASK_TIME_LIMIT = 360        # 6 minutes hard limit

# Result expiry
CELERY_RESULT_EXPIRES = 3600        # Results 1 hour baad delete ho jaayein

# Connection
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True
CELERY_BROKER_CONNECTION_MAX_RETRIES = 10

# Monitoring
CELERY_TASK_TRACK_STARTED = True
CELERY_SEND_TASK_ERROR_EMAILS = False  # Use Sentry instead

# Worker
CELERYD_LOG_FORMAT = '[%(asctime)s: %(levelname)s/%(processName)s] %(message)s'
CELERYD_TASK_LOG_FORMAT = '[%(asctime)s: %(levelname)s/%(processName)s][%(task_name)s(%(task_id)s)] %(message)s'
```

### 14.2 Why ACKS_LATE?

**Default behavior (`acks_late=False`):**
1. Worker task receive karta hai
2. IMMEDIATELY broker ko ack karta hai (task queue se remove ho gayi)
3. Phir task execute karta hai
4. Agar worker crash ho jaaye → task LOST! (broker ko laga task complete ho gayi)

**`acks_late=True` behavior:**
1. Worker task receive karta hai
2. Task execute karta hai
3. SUCCESS ke baad broker ko ack karta hai
4. Agar worker crash ho jaaye → task re-queued hoti hai (broker ko laga task incomplete)

**Side effect:** `acks_late=True` ke saath task twice execute ho sakti hai (at-least-once delivery). **Tasks idempotent honi chahiye!**

### 14.3 Why PREFETCH_MULTIPLIER=1?

**Default `prefetch_multiplier=4`:**
Worker 4 tasks ek baar mein uthaa leta hai. Problem:
- Worker A: 4 heavy tasks (5 min each = 20 min)
- Worker B: idle (queue empty lagti hai usse)
- Result: Load imbalance!

**`prefetch_multiplier=1`:**
Har worker ek kaam complete kare, phir naya uthaye. Fair distribution.

```python
# celeryconfig.py
CELERY_WORKER_PREFETCH_MULTIPLIER = 1  # Fair distribution

# Exception: agar tasks bahut short hain (<1 second), prefetch=4 rakhna theek hai
# Network overhead kam karne ke liye
```

---

## 15. Interview Q&As — 40 LPA Level

---

**Q1: chord vs group mein kya difference hai?**

**Answer:**

`group` ke results koi aggregate nahi karta — sab tasks independently run hoti hain aur aapko individually results check karne padte hain.

`chord = group + callback` — group ki saari tasks parallel run hoti hain, complete hone ke baad ek **callback** task unke results ki list receive karta hai.

```python
# group — no aggregation
g = group(task.s(i) for i in items)
results = g.apply_async().get()  # list of results, manually process karo

# chord — built-in aggregation
c = chord(group(task.s(i) for i in items))(aggregate.s())
# aggregate task ko [result1, result2, ...] milega automatically
```

`chord` ke liye result backend (Redis/DB) **mandatory** hai.

---

**Q2: Chain mein immutable signature `.si()` ka kya use hai?**

**Answer:**

Chain mein normally har task pichle task ka result receive karta hai as first argument. Lekin kabhi kabhi ek task chain mein daalni hai jo:
- Apne khud ke arguments se kaam karti hai
- Parent result se kuch matlab nahi

`.si()` (immutable signature) parent result ko **ignore** karta hai.

```python
# Problem: log_audit ko payment_result pass ho raha hai (galat!)
chain(process_payment.s(order_id), log_audit.s(order_id))

# Solution: .si() se sirf order_id milega, payment result nahi
chain(process_payment.s(order_id), log_audit.si(order_id))
```

Yeh logging, notifications, aur side effects ke liye perfect hai.

---

**Q3: `CELERY_TASK_ACKS_LATE = True` kyon set karte hain production mein?**

**Answer:**

Default (`acks_late=False`) mein task receive hone pe immediately ack hoti hai. Agar worker crash ho task execution ke beech mein, task **permanently lost** ho jaati hai.

`acks_late=True` mein ack sirf **successful completion** ke baad hoti hai. Worker crash pe task broker mein wapas aati hai aur doosra worker uthaa leta hai.

**Tradeoff:** Tasks twice execute ho sakti hain (at-least-once). Isliye tasks **idempotent** honi chahiye — same task baar baar run karo to same result.

```python
@app.task(acks_late=True)
def process_order(order_id: str):
    # Idempotent: agar order already processed hai to skip karo
    if Order.objects.filter(id=order_id, status='processed').exists():
        return {"already_processed": True}
    # ... process
```

---

**Q4: `CELERY_WORKER_PREFETCH_MULTIPLIER = 1` kyon recommended hai?**

**Answer:**

Default value 4 hai — worker 4 tasks ek saath prefetch karta hai. Yeh "hoarding" karti hai tasks:

- Worker A bahut slow tasks le gaya (4 x 10min = 40min ho gaya)
- Worker B ke paas kuch nahi, idle baith raha hai
- New short tasks Worker B ko nahi mil rahi (Worker A ne reserve kar rakha hai)

`multiplier=1` = ek task lo, complete karo, phir naya lo. **Fair distribution**.

**Exception:** Agar tasks bahut short hain (< 1 second), multiplier=4 rakhna theek hai — network overhead optimize hota hai.

---

**Q5: Chord bina result backend ke kyon fail hoti hai?**

**Answer:**

Chord ko pata karna hota hai kab group ki **saari tasks complete** ho gayi hain. Yeh information kahan store hogi? **Result backend mein**.

`chord_unlock` task periodically result backend ko poll karta hai:
- "Kya task-1 done hai?" → Backend mein check karo
- "Kya task-2 done hai?" → Backend mein check karo
- Jab sab done → callback trigger karo

Bina result backend ke yeh state store nahi ho sakti → chord indefinitely hang karti hai ya fail.

```python
# WRONG
app = Celery(broker='redis://...')  # No backend!

# CORRECT
app = Celery(broker='redis://.../0', backend='redis://.../1')
```

---

**Q6: Exponential backoff kaise implement karte hain Celery mein?**

**Answer:**

Do tarike:

**Manual:**
```python
@app.task(bind=True, max_retries=5)
def my_task(self, data):
    try:
        call_api(data)
    except Exception as exc:
        countdown = 2 ** self.request.retries  # 1, 2, 4, 8, 16 seconds
        raise self.retry(exc=exc, countdown=countdown)
```

**Built-in (Recommended):**
```python
@app.task(
    autoretry_for=(Exception,),
    retry_backoff=True,       # Automatic exponential backoff
    retry_backoff_max=600,    # Max 10 minutes
    retry_jitter=True         # Random offset (thundering herd se bachao)
)
def my_task(data):
    call_api(data)
```

Jitter important hai — agar 1000 tasks same time pe fail hoti hain aur sab exact same time pe retry karti hain, server phir se crash ho sakta hai.

---

**Q7: Soft time limit vs hard time limit mein kya difference hai?**

**Answer:**

| | Soft Time Limit | Hard Time Limit |
|---|---|---|
| Signal | `SoftTimeLimitExceeded` exception | `SIGKILL` |
| Catchable? | Haan — `try/except` se catch karo | Nahi — immediate death |
| Cleanup? | Possible — DB connections close, temp files delete | Impossible |
| Task state | FAILURE (gracefully) | FAILURE (abruptly) |

**Pattern:**
```python
@app.task(soft_time_limit=55, time_limit=60)
def long_task():
    try:
        do_work()
    except SoftTimeLimitExceeded:
        save_progress()   # Cleanup
        cleanup_files()
        raise             # Task ko fail mark karo
```

Soft limit pe cleanup karo, hard limit is "emergency brake" hai.

---

**Q8: Celery Beat vs system cron (crontab) — kab kya use karein?**

**Answer:**

| | Celery Beat | System Cron |
|---|---|---|
| Distribution | Multiple workers pe distribute ho sakta hai | Single machine pe run |
| Scheduling | DB mein store kar sako (django-celery-beat) | File mein hardcoded |
| Monitoring | Flower, task history | System logs only |
| Task chaining | Beat + Celery tasks chain/chord kar sakte hain | Nahi |
| Dependencies | Celery infrastructure chahiye | OS level |

**Use Celery Beat when:**
- Tasks already Celery workers pe run hoti hain
- Runtime pe schedule change karna ho (django-celery-beat)
- Complex workflows (beat triggers chain/chord)
- Distributed environment mein consistent scheduling chahiye

**Use System Cron when:**
- Simple scripts (DB backup, log rotation)
- Celery infrastructure nahi hai
- OS-level operations

---

**Q9: Task routing ka purpose kya hai? Ek ek queue mein sab kyon nahi daalte?**

**Answer:**

Single queue ka problem:

1. **Priority mixing:** Low priority bulk email tasks → high priority payment tasks ko block kar sakti hain
2. **Resource competition:** Analytics (CPU heavy) + Notifications (I/O heavy) ek saath → inefficient
3. **Scaling:** Email surge aaya → sirf email workers scale karo, payment workers ko touch mat karo
4. **Isolation:** Email queue jam ho gayi → payments unaffected

Routing se:
- `high_priority` queue → 3 dedicated workers (payments, refunds, OTPs)
- `email` queue → 2 workers
- `analytics` queue → 1 worker (can lag, that's ok)

```python
CELERY_TASK_ROUTES = {
    'tasks.process_payment': {'queue': 'high_priority'},
    'tasks.send_otp': {'queue': 'high_priority'},
    'tasks.send_newsletter': {'queue': 'email'},
    'tasks.track_event': {'queue': 'analytics'},
}
```

---

**Q10: Celery worker concurrency models kya hain? Kab kaunsa use karein?**

**Answer:**

**Prefork (default):**
- Multiple OS processes
- Har process ka apna Python interpreter (GIL nahi!)
- CPU-bound tasks ke liye: data processing, ML inference, PDF generation
- Memory heavy — `n` workers = `n` Python processes
- `--concurrency=4` (number of CPU cores)

**Eventlet/Gevent:**
- Single process, cooperative multitasking (coroutines)
- Thousands of concurrent tasks in one process
- I/O-bound tasks ke liye: HTTP calls, DB queries, file reads
- Memory efficient
- Requires monkey patching
- `--concurrency=1000 --pool=eventlet`

**Solo:**
- Single process, single thread
- Only for debugging
- `--pool=solo`

**Rule of thumb:**
```
API calls / DB queries → Eventlet (--pool=eventlet --concurrency=500)
Data processing / ML  → Prefork  (--pool=prefork --concurrency=4)
Mixed workload        → Prefork + separate Eventlet worker on different queue
```

---

## Summary — Key Points Yaad Rakhein

```
Canvas Primitives:
  chain()  = sequential  (A → B → C)
  group()  = parallel    (A + B + C)
  chord()  = parallel + callback (A+B+C → D)

.s() = mutable (parent result pass hoga)
.si() = immutable (parent result ignore)

Retry:
  autoretry_for + retry_backoff + retry_jitter = production-ready

Queues:
  Alag queues = isolation + scaling + priority

Production Must-Haves:
  acks_late = True          (no task loss on crash)
  prefetch_multiplier = 1   (fair distribution)
  task_serializer = 'json'  (security + readability)
  result_backend = redis    (chord + state tracking)

Time Limits:
  soft_time_limit → cleanup possible
  time_limit → immediate kill
```

---

*End of 03_celery_advanced_patterns.md*  
*Next: 04_celery_django_integration.md*
