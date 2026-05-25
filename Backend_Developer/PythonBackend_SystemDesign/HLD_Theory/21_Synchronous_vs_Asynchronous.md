# Synchronous vs Asynchronous Communication

## Quick Reference Card
```
Synchronous  → Request-Response — caller WAITS for result — REST API, DB query
Asynchronous → Fire and Forget — caller DOESN'T WAIT — Celery tasks, events
Blocking     → Thread stuck waiting — holds thread resource
Non-blocking → Thread free to do other work while waiting
Use sync     → When you need immediate result (payment status, data validation)
Use async    → When task is slow (email, SAP push) or decoupled (notifications)
Interview hook → "SAP invoice push: sync = 500ms wait | async Celery = 10ms response"
```

---

## PART 1: HINGLISH — Samjhne ke liye

### 1.1 Synchronous vs Asynchronous — Core Concept

**Analogy: Restaurant order karna**

**Synchronous (Counter service):**
- Tum counter pe khade ho
- Order diya: "1 samosa"
- Wait karo (thread blocked!)
- Samosa ready → tum le lo → sit down
- Doosra kaam tab tak band

**Asynchronous (Table service):**
- Seat le lo, waiter ko order diya
- Waiter chal gaya kitchen mein
- Tum newspaper padh rahe ho, kisi se baat kar rahe ho
- Waiter aata hai — "Sir samosa ready hai"
- Tum doosra kaam bhi karte rahe!

```
SYNCHRONOUS:
  Client          Server
    │                │
    │──── Request ───►│
    │                │ (processing...)
    │                │ wait... wait...
    │◄─── Response ──│
    │                │
  (Client blocked until response)

ASYNCHRONOUS:
  Client          Queue        Worker
    │                │            │
    │──── Enqueue ──►│            │
    │◄─── "Queued" ──│            │
    │  (free!)       │──Dequeue──►│
    │                │            │ (processing...)
    │  (doing other  │            │
    │   stuff)        │◄──Done────│
    │                │(result in  │
    │                │ DB/Redis)  │
```

---

### 1.2 Blocking vs Non-Blocking

```
BLOCKING (Synchronous traditional):
  Thread assigned to request → stuck waiting for DB/API/network
  
  Thread 1: Handle Request 1 → Wait DB (50ms) → Wait SAP (200ms) → Respond
            [████████████████ BLOCKED 250ms ████████████████]
  
  If 100 concurrent requests → 100 threads needed, all blocked!
  Django Gunicorn workers: default 5 workers
  → Only 5 requests handled simultaneously
  → 6th request WAITS for a worker to free up

NON-BLOCKING (Async I/O or Threading workarounds):
  Thread 1: Handle Request → Start DB query (non-blocking) → Handle Request 2
            → DB result comes in → Resume Request 1 → Respond
  
  Single thread can handle many requests because:
  It doesn't WAIT — it registers callbacks and handles other work
  
  Python async:
  async def handle_request():
      data = await db.query(...)  # Non-blocking! Other coroutines run
      result = await external_api.call(...)  # Non-blocking!
      return result
  
  FastAPI/Django Async Views: Use ASGI server (Uvicorn)
  vs
  Django Sync Views: Use WSGI server (Gunicorn) — one thread per request
```

---

### 1.3 When to Use Synchronous

```
USE SYNCHRONOUS WHEN:
  ✓ Caller needs result immediately
  ✓ Subsequent steps depend on this result
  ✓ Error handling must be immediate
  ✓ Simple, fast operations

EXAMPLES:
  
  1. User authentication:
     Login → Check credentials → NEED RESULT NOW (is password correct?)
     Can't say: "I'll check password later, log you in now"
  
  2. Payment status:
     User clicks Pay → Need to know SUCCESS or FAILURE now
     Can't say: "Payment pending, please wait" (bad UX for card payment)
  
  3. Booking creation:
     Create booking → Need booking ID to show confirmation page
     Can't say: "Booking will be created later"
  
  4. Form validation:
     User submits form → Check if email already exists → Need result now
  
  5. Database reads:
     API request for package list → Read from DB → Return response
     Synchronous is fine (fast query, result needed immediately)

CODE EXAMPLE:
  def login(request):
      email = request.data['email']
      password = request.data['password']
      
      # Synchronous — result needed NOW
      user = authenticate(request, email=email, password=password)
      
      if user:
          token = create_jwt_token(user)
          return Response({'token': token})  # Immediate response
      else:
          return Response({'error': 'Invalid credentials'}, status=401)
```

---

### 1.4 When to Use Asynchronous

```
USE ASYNCHRONOUS WHEN:
  ✓ Task is slow (>100ms) and doesn't need immediate result
  ✓ Task can be decoupled (notification, log, sync)
  ✓ Reliability matters (retry on failure)
  ✓ Background processing acceptable

EXAMPLES:

  1. Email sending:
     User registers → Send welcome email
     Don't wait for email server! Just queue it.
     "Email sent or not doesn't affect registration success"
  
  2. SAP/ERP sync:
     Invoice created → Push to SAP HANA (200-500ms)
     User doesn't need to wait for SAP push
     Queue the sync, respond immediately
  
  3. PDF generation:
     User requests certificate → Generate PDF (2-3 sec)
     "We'll generate your certificate, here's your booking ID"
     Poll or webhook when done
  
  4. Search index update:
     Package created → Update Typesense index
     User's package is in DB (authoritative)
     Search index will update in next 5 seconds (ok)
  
  5. Notifications:
     Booking confirmed → Send WhatsApp + Email to customer + Sales team
     Multiple notifications, don't slow down booking API

CELERY EXAMPLE:
  # booking/views.py
  def create_booking(request):
      # Synchronous — needs result immediately
      with transaction.atomic():
          booking = Booking.objects.create(**data)
          payment = Payment.objects.create(booking=booking, ...)
      
      # Asynchronous — doesn't need to complete before response
      send_booking_confirmation_email.delay(booking.id)    # Fast return
      push_booking_to_sap.delay(booking.id)                 # Fast return
      update_search_index.delay(booking.id)                 # Fast return
      
      # Response is immediate — user sees confirmation
      return Response(BookingSerializer(booking).data)
  
  # tasks.py
  @shared_task(bind=True, max_retries=3)
  def send_booking_confirmation_email(self, booking_id):
      booking = Booking.objects.get(id=booking_id)
      # This runs in background worker
      send_email(booking.user.email, ...)
```

---

### 1.5 Synchronous vs Asynchronous Patterns

#### Pattern 1: Request-Reply (Synchronous)
```
Client → API → DB → Response
Simple, direct, blocks until done
Use for: All standard REST API calls
```

#### Pattern 2: Fire-and-Forget (Async, no result needed)
```
Client → API → Queue task → "Received!" response → Worker processes later
Use for: Emails, logging, analytics, notifications
No callback needed — just confirm task was queued
```

#### Pattern 3: Callback (Async with result)
```
Client → API → Queue task → Task ID response
...time passes...
Worker completes → Notifies client via webhook
Use for: PDF generation, long-running reports
```

#### Pattern 4: Polling (Async with polling)
```
Client → API → Queue task → Job ID response
Client polls GET /job/{id}/status every 2 seconds
Worker completes → Status = "done" → Client fetches result
Use for: Certificate generation, data export
```

#### Pattern 5: WebSocket (Bidirectional real-time)
```
Client ←WebSocket→ Server
Server can push updates to client without client polling
Use for: Live booking status, chat, real-time dashboards
```

---

### 1.6 Celery + Django — Async Implementation

```python
# Complete async setup

# celery.py
from celery import Celery

app = Celery('youngman')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()

# settings.py
CELERY_BROKER_URL = 'redis://localhost:6379/1'  # RabbitMQ or Redis
CELERY_RESULT_BACKEND = 'redis://localhost:6379/2'
CELERY_TASK_SERIALIZER = 'json'
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_ACKS_LATE = True          # Acknowledge after completion (not on pickup)
CELERY_TASK_REJECT_ON_WORKER_LOST = True  # Requeue if worker crashes

# tasks.py
from celery import shared_task
from celery.exceptions import MaxRetriesExceededError

@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def push_invoice_to_sap(self, invoice_id):
    """
    Asynchronous SAP push — runs in background worker.
    Retries up to 3 times if SAP is temporarily unavailable.
    """
    try:
        invoice = Invoice.objects.get(id=invoice_id)
        sap_client.push_invoice(invoice)
        
        invoice.sap_synced = True
        invoice.sap_sync_at = timezone.now()
        invoice.save(update_fields=['sap_synced', 'sap_sync_at'])
        
    except SAPConnectionError as exc:
        # SAP unavailable → retry with exponential backoff
        raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))
    
    except MaxRetriesExceededError:
        # All retries failed → Dead Letter Queue
        FailedSAPSync.objects.create(invoice_id=invoice_id, error=str(exc))
        notify_ops_team.delay(f"SAP sync failed for invoice {invoice_id}")

# views.py
def create_invoice(request):
    invoice = Invoice.objects.create(**request.data)
    
    # Asynchronous — fires immediately, doesn't wait
    push_invoice_to_sap.delay(invoice.id)
    generate_invoice_pdf.delay(invoice.id)
    send_invoice_email.delay(invoice.id)
    
    # Response in ~10ms (no waiting for SAP/PDF/email)
    return Response({'id': invoice.id, 'status': 'created'})

# With task result tracking (polling pattern):
def export_report(request):
    task = generate_monthly_report.delay(request.user.id)
    return Response({'task_id': task.id})

def check_report_status(request, task_id):
    task = AsyncResult(task_id)
    if task.ready():
        return Response({'status': 'done', 'result': task.result})
    return Response({'status': 'pending'})
```

---

### 1.7 Django Async Views (ASGI)

```python
# Async views — non-blocking I/O

# settings.py
# Use uvicorn (ASGI) instead of gunicorn (WSGI):
# uvicorn myproject.asgi:application --workers 4

# views.py
import asyncio
import aiohttp

class AsyncInvoiceView(APIView):
    
    async def get(self, request, invoice_id):
        # Multiple async calls simultaneously!
        invoice, sap_status = await asyncio.gather(
            self.get_invoice(invoice_id),
            self.get_sap_status(invoice_id)
        )
        
        return Response({'invoice': invoice, 'sap_status': sap_status})
    
    async def get_invoice(self, invoice_id):
        # Django ORM supports async since 4.1
        return await Invoice.objects.aget(id=invoice_id)
    
    async def get_sap_status(self, invoice_id):
        async with aiohttp.ClientSession() as session:
            async with session.get(f'{SAP_API}/invoice/{invoice_id}/status') as r:
                return await r.json()
    
    # With sync views + threads: 200ms + 200ms = 400ms total
    # With async views: max(200ms, 200ms) = 200ms (parallel!)

# Django 4.1+ supports async ORM:
# await Model.objects.aget(id=pk)          # async get
# await Model.objects.acreate(**data)       # async create
# async for item in Model.objects.all():    # async iteration
```

---

### 1.8 Ashish ke projects mein

```
SYNCHRONOUS operations in Youngman/Niroskos:
  ✓ User login/auth — token needed immediately
  ✓ Booking creation — booking_id needed for confirmation page
  ✓ Payment initiation — need payment link/status immediately
  ✓ All GET requests — read data, respond immediately
  ✓ Form validation — check availability synchronously

ASYNCHRONOUS operations:
  ✓ SAP invoice push — 200-500ms, user doesn't wait (Celery)
  ✓ Invoice PDF generation — 2-3 sec (Celery)
  ✓ Email sending — SMTP can be slow (Celery)
  ✓ WhatsApp notifications — Exotel/Twilio API (Celery)
  ✓ Typesense index update — 5-10 sec lag acceptable (signal + Celery)
  ✓ Account receivable checks — batch job (Celery Beat)
  
  Async results:
    Invoice creation API: 500ms → 10ms (moved SAP push to async)
    Booking confirmation: immediate (notifications in background)
    Monthly invoice batch: runs overnight (no user waiting)

KEY DECISION FRAMEWORK:
  Q: "Does the user need this result to continue?"
  YES → Synchronous
  NO → Asynchronous (Celery task)
  
  Q: "Is this operation slow (>100ms)?"
  YES → Consider async even if result needed (queue + poll)
  NO → Synchronous is fine
```

---

## PART 2: ENGLISH — Interviewer ko bolne ke liye

### 2.1 Definitions

> **Synchronous Communication**: The caller sends a request and blocks (waits) until a response is received. Simple, direct, immediately consistent. Scales poorly for slow operations as threads/processes are held during wait.

> **Asynchronous Communication**: The caller sends a request and immediately proceeds without waiting for the result. The result is delivered later via callback, polling, or event. Better throughput for slow operations but adds complexity (message queues, retry logic, eventual consistency).

---

### 2.2 Synchronous vs Asynchronous Comparison

| Dimension | Synchronous | Asynchronous |
|-----------|-------------|--------------|
| Caller behavior | Blocks until response | Returns immediately |
| Coupling | Tight (both parties must be available) | Loose (sender/receiver independent) |
| Consistency | Immediate | Eventual |
| Error handling | Direct (exception propagates) | Requires retry/DLQ strategy |
| Scalability | Limited by slowest operation | Better for slow I/O |
| Complexity | Low | Higher (queue, worker, monitoring) |
| Use case | User-facing reads/writes | Background processing |
| Examples | REST API, DB query | Celery, Kafka consumer |

---

### 2.3 Async Patterns

```
1. FIRE AND FORGET:
   task.delay(data)
   No need for result
   Use: notifications, logging, analytics
   
2. CALLBACK (webhook):
   POST /process → task_id
   Worker completes → POST /callback/client
   Use: Payment processing, third-party integrations

3. POLLING:
   POST /export → task_id
   GET /export/task_id → {status: pending/done, result: ...}
   Use: Report generation, batch processing

4. EVENT-DRIVEN:
   Producer → Event → Queue/Topic → Consumer processes
   Loose coupling — consumer doesn't need to be running when event fires
   Use: Microservices communication, real-time pipelines
```

---

### 2.4 Real Project Answer

> "In Youngman's invoice creation flow, we made a conscious decision about sync vs async for each step. The core invoice creation — database transaction — is synchronous: we need the invoice_id for the response. Everything else is asynchronous via Celery: SAP push (300ms), PDF generation (2 seconds), and email notification (variable). This reduced invoice creation API response time from ~500ms to ~15ms. The key question we ask is: 'Does the user or the next step in the flow need this result immediately?' SAP sync doesn't affect the user — they just need the invoice created. The Celery task retries up to 3 times with exponential backoff, and failed syncs go to a dead letter queue for ops review."

---

### 2.5 Common Follow-up Q&A

**Q1: What happens if an async task fails?**
> "Celery handles this with retry policies. We configure `max_retries=3` and `default_retry_delay=60` — on failure, the task retries up to 3 times with increasing delays. If all retries fail, it hits the Dead Letter Queue — a separate queue where failed tasks are stored for manual inspection. We also have a monitoring setup: Celery Flower shows task success/failure rates, and a daily management command checks for unprocessed items (SAP sync not attempted for invoices older than 1 hour). This ensures eventual consistency — even if the Celery task fails multiple times, a recovery job will catch it."

**Q2: How do you decide the number of Celery workers?**
> "It depends on task type: CPU-bound tasks (PDF generation, data processing): `workers = CPU count`. I/O-bound tasks (SAP API calls, emails): more workers can help since workers spend time waiting for I/O. We run 3 Celery workers on our EC2 t3.medium (2 vCPUs) for I/O-bound SAP push tasks. Each worker can handle 1 task at a time by default. With `--concurrency=4` per worker, you can run 4 concurrent tasks per worker via threading/eventlet, useful for I/O-bound workloads. Monitor queue depth — if it grows, add workers."

**Q3: What is the difference between message queue and task queue?**
> "A task queue (Celery + Redis/RabbitMQ) is designed for running Python functions asynchronously. You pass function name + arguments, the worker imports and executes the function. High-level abstraction. A message queue (Kafka, RabbitMQ, SQS) is more general — it routes messages between producers and consumers. Consumers decide what to do with messages. Lower-level, more flexible, supports multiple consumers per message (Kafka). Celery uses a message queue (RabbitMQ or Redis) as its broker internally — the message queue handles delivery, Celery handles the execution logic."

---

## Interview Cheat Sheet

```
Synchronous:
  Caller waits for result
  Use when: Immediate result needed, next step depends on it
  Examples: Login, booking creation, payment, DB reads
  Problem: Slow operations block threads

Asynchronous:
  Caller fires and continues
  Use when: Slow operation, user doesn't need to wait
  Examples: Email, SAP push, PDF generation, notifications
  Benefit: Fast API response, better throughput

Patterns:
  Fire-and-forget: task.delay(data) — no result needed
  Polling: task_id → client polls status endpoint
  Callback/webhook: worker pushes result to client URL
  Event-driven: producer → queue → consumer

Django + Celery (most common):
  @shared_task(bind=True, max_retries=3)
  def my_task(self, data):
      try: do_work(data)
      except Error as exc: raise self.retry(exc=exc)
  
  # In view:
  my_task.delay(data)  # Returns immediately

Django Async Views (ASGI):
  async def view(request):
      result = await Model.objects.aget(id=pk)
  # Non-blocking DB call — thread handles other requests while waiting

My project:
  Sync: login, booking create, payment init
  Async: SAP push, PDF gen, emails, notifications
  Result: Invoice API 500ms → 15ms
  Worker setup: 3 Celery workers, I/O-bound tasks
```
