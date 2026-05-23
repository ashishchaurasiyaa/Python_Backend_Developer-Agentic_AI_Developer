# Task Queue / Job Scheduler — LLD
> **Difficulty:** Hard | **Frequency:** ★★★★★ | **Your Strength:** Celery in Niroskos (crypto scanner, reminders, SAP sync)

---

## What is a Task Queue?

```
Web request → heavy kaam → user wait karega? NO.
Solution: task queue mein daalo → background worker process kare.

Web Process (fast)          Worker Process (async)
──────────────────         ──────────────────────
Request aaya               Queue se task uthao
Task queue mein daalo  →   Execute karo
Response do (instant)      Retry on failure
                           Dead letter on max retry
```

---

## Celery Architecture (Niroskos Production)

```
┌─────────────────────────────────────────────────────────────┐
│                    CELERY ARCHITECTURE                       │
├──────────────────┬──────────────────┬───────────────────────┤
│   PRODUCER       │   BROKER         │   CONSUMER            │
│   (Django app)   │   (Redis)        │   (Celery Worker)     │
│                  │                  │                        │
│  task.delay()    │  Queue:          │  Worker Pool:          │
│  task.apply_     │  ├─ critical     │  ├─ prefork (CPU)     │
│    async()       │  ├─ default      │  ├─ gevent (I/O)      │
│                  │  ├─ celery       │  └─ solo (debug)      │
│  .delay()        │  └─ blockchain   │                        │
│  = shorthand     │                  │  Concurrency: 4-8     │
│  for             │  Each queue =    │  workers per process  │
│  .apply_async()  │  Redis LIST      │                        │
│  with no args    │  LPUSH/BRPOP     │  Beat Scheduler:      │
│                  │                  │  ├─ crontab('*/1 * ')  │
│                  │  Result Backend: │  └─ timedelta(min=10) │
│                  │  Redis HSET      │                        │
└──────────────────┴──────────────────┴───────────────────────┘

Niroskos stack:
  Broker:  Redis (same Redis as cache + rate limiter)
  Backend: Redis (task results stored here)
  Workers: 3 Celery worker processes (Docker containers)
  Beat:    1 Celery beat process (periodic tasks)
```

---

## Full Implementation

```python
from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional
import threading
import uuid
import time
import queue
import heapq


# ═══════════════════════════════════════════════════════════════
# ENUMS & DOMAIN OBJECTS
# ═══════════════════════════════════════════════════════════════

class TaskStatus(Enum):
    PENDING   = "pending"     # Queued, not yet picked up
    STARTED   = "started"     # Worker running it
    SUCCESS   = "success"     # Done
    FAILURE   = "failure"     # Failed, may retry
    RETRY     = "retry"       # Scheduled for retry
    REVOKED   = "revoked"     # Cancelled
    DEAD      = "dead"        # Max retries exceeded → DLQ


class TaskPriority(Enum):
    CRITICAL = 0    # OTP, payment webhooks — process immediately
    HIGH     = 1    # Booking confirmation emails
    NORMAL   = 5    # Reminders, cache refreshes
    LOW      = 10   # Reports, bulk exports


@dataclass
class TaskResult:
    task_id:      str
    status:       TaskStatus
    result:       Any   = None
    error:        str   = ""
    traceback:    str   = ""
    started_at:   Optional[datetime] = None
    completed_at: Optional[datetime] = None
    attempt:      int   = 1

    @property
    def duration_ms(self) -> Optional[float]:
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds() * 1000
        return None


@dataclass
class TaskMessage:
    """
    What goes onto the queue (serialized to JSON in Celery).
    Celery message format: task name + args + kwargs + options.
    """
    task_id:          str   = field(default_factory=lambda: str(uuid.uuid4()))
    task_name:        str   = ""
    args:             list  = field(default_factory=list)
    kwargs:           dict  = field(default_factory=dict)
    priority:         TaskPriority = TaskPriority.NORMAL
    queue_name:       str   = "default"
    max_retries:      int   = 3
    retry_countdown:  float = 60.0     # seconds before next retry
    retry_backoff:    bool  = True     # exponential backoff
    eta:              Optional[datetime] = None   # run not before this time
    expires:          Optional[datetime] = None   # discard after this time
    attempt:          int   = 1
    enqueued_at:      datetime = field(default_factory=datetime.now)
    idempotency_key:  str   = ""       # prevent duplicate execution


# ═══════════════════════════════════════════════════════════════
# TASK BASE CLASS
# ═══════════════════════════════════════════════════════════════

class BaseTask(ABC):
    """
    Celery mein: @shared_task decorator se yeh kaam hota hai.
    Yahan: explicit class — same concept.

    Niroskos tasks:
      BlockchainScanTask     — crypto payment confirm karna (self-rescheduling)
      BookingReminderTask    — 48h pehle customer ko email
      SAPSyncTask            — booking data SAP HANA mein push karna
      ExotelSMSTask          — rate-limited SMS send
      CacheRefreshTask       — stale booking cache refresh
    """
    name:        str = ""
    max_retries: int = 3
    queue:       str = "default"
    priority:    TaskPriority = TaskPriority.NORMAL

    @abstractmethod
    def run(self, *args, **kwargs) -> Any:
        """Business logic — override karo"""
        pass

    def on_success(self, result: Any, task_id: str, args, kwargs) -> None:
        """Success ke baad — override optional"""
        pass

    def on_failure(self, exc: Exception, task_id: str, args, kwargs, einfo) -> None:
        """Final failure (DLQ jane se pehle) — override optional"""
        pass

    def on_retry(self, exc: Exception, task_id: str, args, kwargs, einfo) -> None:
        """Har retry pe — override optional"""
        pass


# ═══════════════════════════════════════════════════════════════
# RETRY POLICY
# ═══════════════════════════════════════════════════════════════

@dataclass
class RetryPolicy:
    """
    Celery equivalent:
      @shared_task(bind=True, max_retries=3, default_retry_delay=60)
      def my_task(self, ...):
          try:
              ...
          except SomeError as exc:
              raise self.retry(exc=exc, countdown=backoff_delay)
    """
    max_retries:     int   = 3
    base_delay:      float = 60.0    # seconds
    backoff_factor:  float = 2.0     # exponential multiplier
    max_delay:       float = 3600.0  # cap at 1 hour
    jitter:          bool  = True    # add random ±10% — prevents thundering herd

    # Which exceptions trigger retry vs immediate DLQ
    retryable_exceptions: tuple = (ConnectionError, TimeoutError, OSError)
    fatal_exceptions:     tuple = (ValueError, TypeError, KeyError)

    def delay_for_attempt(self, attempt: int) -> float:
        """
        attempt 1 → 60s
        attempt 2 → 120s
        attempt 3 → 240s (capped at max_delay)

        Celery: raise self.retry(countdown=delay)
        """
        delay = self.base_delay * (self.backoff_factor ** (attempt - 1))
        delay = min(delay, self.max_delay)
        if self.jitter:
            import random
            delay *= (0.9 + random.random() * 0.2)   # ±10%
        return delay

    def should_retry(self, exc: Exception, attempt: int) -> bool:
        if attempt >= self.max_retries:
            return False
        if isinstance(exc, self.fatal_exceptions):
            return False    # Programming error — retry won't help
        return True         # Transient error — retry


# ═══════════════════════════════════════════════════════════════
# PRIORITY QUEUE (In-Memory Broker Simulation)
# ═══════════════════════════════════════════════════════════════

class PriorityTaskQueue:
    """
    In Celery: different queues per priority (critical, default, low).
    Workers consume critical first, then default, then low.

    Here: single priority queue using heapq.
    Item: (priority_value, enqueue_time, TaskMessage)
    Tie-break on enqueue_time → FIFO within same priority.
    """

    def __init__(self):
        self._heap: list = []
        self._lock = threading.Lock()
        self._not_empty = threading.Condition(self._lock)

    def enqueue(self, message: TaskMessage) -> None:
        with self._not_empty:
            # (priority_int, timestamp, message) — heap sorts by first element
            item = (
                message.priority.value,
                message.enqueued_at.timestamp(),
                message
            )
            heapq.heappush(self._heap, item)
            self._not_empty.notify()   # Wake a waiting worker
        print(f"[QUEUE] Enqueued: {message.task_name} | priority={message.priority.name} "
              f"| id={message.task_id[:8]}")

    def dequeue(self, timeout: float = 5.0) -> Optional[TaskMessage]:
        """Block until a task is available (like Redis BRPOP)"""
        with self._not_empty:
            deadline = time.time() + timeout
            while not self._heap:
                remaining = deadline - time.time()
                if remaining <= 0:
                    return None
                self._not_empty.wait(timeout=remaining)

            _, _, message = heapq.heappop(self._heap)

            # ETA check — not ready yet? Re-enqueue
            if message.eta and datetime.now() < message.eta:
                heapq.heappush(self._heap, (
                    message.priority.value,
                    message.enqueued_at.timestamp(),
                    message
                ))
                return None  # Nothing ready yet

            # Expiry check
            if message.expires and datetime.now() > message.expires:
                print(f"[QUEUE] Expired, discarding: {message.task_id[:8]}")
                return None

            return message

    def __len__(self) -> int:
        with self._lock:
            return len(self._heap)


# ═══════════════════════════════════════════════════════════════
# DEAD LETTER QUEUE
# ═══════════════════════════════════════════════════════════════

class DeadLetterQueue:
    """
    Max retries exceeded → task lands here.
    Ops team can:
      1. Inspect why it failed
      2. Fix the bug
      3. Re-queue manually
      4. Discard

    Celery equivalent: task_acks_late + task_reject_on_worker_lost
    Or: custom on_failure() that publishes to a 'dead_letter' queue.

    Niroskos: Failed SAP sync tasks → DLQ → ops team gets Slack alert
              Failed crypto scans   → DLQ → manual payment verification
    """

    def __init__(self):
        self._messages: List[dict] = []
        self._lock = threading.Lock()
        self._observers: list = []   # Slack alert, email to ops

    def add(self, message: TaskMessage, error: str, traceback: str = "") -> None:
        entry = {
            "task_id":     message.task_id,
            "task_name":   message.task_name,
            "args":        message.args,
            "kwargs":      message.kwargs,
            "attempts":    message.attempt,
            "error":       error,
            "traceback":   traceback,
            "failed_at":   datetime.now().isoformat(),
            "original_message": message
        }
        with self._lock:
            self._messages.append(entry)

        print(f"[DLQ] ☠ Task dead: {message.task_name} | "
              f"attempts={message.attempt} | error={error[:60]}")

        # Alert ops team
        for observer in self._observers:
            observer(entry)

    def subscribe_alert(self, callback: Callable) -> None:
        """E.g.: lambda entry: slack.send('#ops', f'DLQ: {entry[task_name]}'"""
        self._observers.append(callback)

    def replay(self, task_id: str, task_queue: PriorityTaskQueue) -> bool:
        """Re-queue a failed task after ops team fixes the issue"""
        with self._lock:
            for i, entry in enumerate(self._messages):
                if entry["task_id"] == task_id:
                    original: TaskMessage = entry["original_message"]
                    # Reset attempt count for fresh start
                    original.attempt = 1
                    task_queue.enqueue(original)
                    self._messages.pop(i)
                    print(f"[DLQ] Replayed: {original.task_name}")
                    return True
        return False

    def list_failed(self) -> List[dict]:
        with self._lock:
            return [
                {"task_id": e["task_id"], "task_name": e["task_name"],
                 "attempts": e["attempts"], "error": e["error"][:80],
                 "failed_at": e["failed_at"]}
                for e in self._messages
            ]

    def __len__(self) -> int:
        with self._lock:
            return len(self._messages)


# ═══════════════════════════════════════════════════════════════
# WORKER
# ═══════════════════════════════════════════════════════════════

class Worker:
    """
    Celery worker = this class running in a separate process.
    Pulls tasks from queue, executes, handles retry/DLQ.

    Celery internals:
      BRPOP  → blocking pop from Redis list
      Prefetch: worker takes N tasks at once (prefetch_multiplier)
      Acks:  task acknowledged AFTER success (task_acks_late=True recommended)
    """

    def __init__(
        self,
        worker_id:    str,
        task_queue:   PriorityTaskQueue,
        dlq:          DeadLetterQueue,
        retry_policy: RetryPolicy,
        task_registry: Dict[str, BaseTask]
    ):
        self.worker_id     = worker_id
        self._queue        = task_queue
        self._dlq          = dlq
        self._retry_policy = retry_policy
        self._registry     = task_registry
        self._results:     Dict[str, TaskResult] = {}
        self._running      = False
        self._thread:      Optional[threading.Thread] = None
        self._tasks_done   = 0
        self._tasks_failed = 0

    def start(self) -> None:
        self._running = True
        self._thread  = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        print(f"[WORKER {self.worker_id}] Started")

    def stop(self) -> None:
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
        print(f"[WORKER {self.worker_id}] Stopped | done={self._tasks_done} failed={self._tasks_failed}")

    def _run_loop(self) -> None:
        """Main loop — BRPOP equivalent"""
        while self._running:
            message = self._queue.dequeue(timeout=1.0)
            if message:
                self._execute(message)

    def _execute(self, message: TaskMessage) -> None:
        task = self._registry.get(message.task_name)
        if not task:
            print(f"[WORKER {self.worker_id}] Unknown task: {message.task_name}")
            return

        result = TaskResult(
            task_id    = message.task_id,
            status     = TaskStatus.STARTED,
            attempt    = message.attempt,
            started_at = datetime.now()
        )
        self._results[message.task_id] = result

        print(f"[WORKER {self.worker_id}] Running: {message.task_name} "
              f"| attempt={message.attempt} | id={message.task_id[:8]}")

        try:
            output = task.run(*message.args, **message.kwargs)
            result.status       = TaskStatus.SUCCESS
            result.result       = output
            result.completed_at = datetime.now()
            self._tasks_done   += 1
            print(f"[WORKER {self.worker_id}] ✓ {message.task_name} "
                  f"({result.duration_ms:.0f}ms)")
            task.on_success(output, message.task_id, message.args, message.kwargs)

        except Exception as exc:
            result.error        = str(exc)
            result.completed_at = datetime.now()
            self._tasks_failed += 1

            if self._retry_policy.should_retry(exc, message.attempt):
                delay = self._retry_policy.delay_for_attempt(message.attempt)
                result.status = TaskStatus.RETRY

                # Re-enqueue with incremented attempt + ETA
                retry_message = TaskMessage(
                    task_id         = message.task_id,   # Same ID — traceable
                    task_name       = message.task_name,
                    args            = message.args,
                    kwargs          = message.kwargs,
                    priority        = message.priority,
                    queue_name      = message.queue_name,
                    max_retries     = message.max_retries,
                    retry_countdown = message.retry_countdown,
                    attempt         = message.attempt + 1,
                    eta             = datetime.now() + timedelta(seconds=delay),
                    idempotency_key = message.idempotency_key
                )
                self._queue.enqueue(retry_message)
                print(f"[WORKER {self.worker_id}] ↻ Retry scheduled: "
                      f"{message.task_name} in {delay:.0f}s "
                      f"(attempt {message.attempt + 1}/{message.max_retries})")
                task.on_retry(exc, message.task_id, message.args, message.kwargs, str(exc))

            else:
                # Max retries or fatal error → DLQ
                result.status = TaskStatus.DEAD
                self._dlq.add(message, str(exc))
                task.on_failure(exc, message.task_id, message.args, message.kwargs, str(exc))

    def get_result(self, task_id: str) -> Optional[TaskResult]:
        return self._results.get(task_id)


# ═══════════════════════════════════════════════════════════════
# BEAT SCHEDULER (Periodic Tasks)
# ═══════════════════════════════════════════════════════════════

@dataclass
class PeriodicTask:
    """
    Celery Beat equivalent.
    crontab(minute='*/5') → every 5 minutes
    timedelta(hours=1)    → every hour
    """
    name:        str
    task_name:   str
    interval:    timedelta
    args:        list  = field(default_factory=list)
    kwargs:      dict  = field(default_factory=dict)
    last_run:    Optional[datetime] = None
    enabled:     bool  = True

    def is_due(self) -> bool:
        if not self.enabled:
            return False
        if self.last_run is None:
            return True
        return datetime.now() >= self.last_run + self.interval


class BeatScheduler:
    """
    Celery Beat: separate process that enqueues periodic tasks.
    Checks every second which tasks are due → enqueues them.

    Niroskos periodic tasks:
      booking_reminders   → every 1 hour  (48h before safari)
      blockchain_scanner  → every 10 sec  (crypto payment confirm)
      sap_sync_bootstrap  → every 5 min   (sync any missed items)
      cache_cleanup       → every midnight (clear expired entries)
    """

    def __init__(self, task_queue: PriorityTaskQueue):
        self._queue    = task_queue
        self._schedule: List[PeriodicTask] = []
        self._running  = False
        self._thread:  Optional[threading.Thread] = None

    def register(self, periodic_task: PeriodicTask) -> None:
        self._schedule.append(periodic_task)
        print(f"[BEAT] Registered: {periodic_task.name} every {periodic_task.interval}")

    def start(self) -> None:
        self._running = True
        self._thread  = threading.Thread(target=self._tick, daemon=True)
        self._thread.start()
        print("[BEAT] Scheduler started")

    def stop(self) -> None:
        self._running = False

    def _tick(self) -> None:
        """Check every second — like Celery Beat's main loop"""
        while self._running:
            for task in self._schedule:
                if task.is_due():
                    self._enqueue_periodic(task)
                    task.last_run = datetime.now()
            time.sleep(1)

    def _enqueue_periodic(self, task: PeriodicTask) -> None:
        message = TaskMessage(
            task_name       = task.task_name,
            args            = task.args,
            kwargs          = task.kwargs,
            priority        = TaskPriority.NORMAL,
            idempotency_key = f"{task.task_name}_{datetime.now().strftime('%Y%m%d%H%M')}"
        )
        self._queue.enqueue(message)


# ═══════════════════════════════════════════════════════════════
# TASK PRODUCER (Application side)
# ═══════════════════════════════════════════════════════════════

class TaskProducer:
    """
    Django app → TaskProducer → Queue.
    Celery equivalent: task.delay() or task.apply_async()
    """

    def __init__(self, task_queue: PriorityTaskQueue):
        self._queue            = task_queue
        self._dedup_store: Dict[str, str] = {}   # idempotency_key → task_id

    def send(
        self,
        task_name:        str,
        args:             list  = None,
        kwargs:           dict  = None,
        priority:         TaskPriority = TaskPriority.NORMAL,
        queue_name:       str   = "default",
        countdown:        float = 0,         # delay in seconds
        eta:              Optional[datetime] = None,
        max_retries:      int   = 3,
        idempotency_key:  str   = "",
    ) -> str:
        """
        Returns task_id — caller can poll for result.

        Celery equivalent:
          send_email.apply_async(
              args=[booking_id],
              countdown=60,
              queue='high',
              max_retries=3
          )
        """
        # Idempotency — same key? Return existing task_id
        if idempotency_key and idempotency_key in self._dedup_store:
            existing_id = self._dedup_store[idempotency_key]
            print(f"[PRODUCER] Duplicate task skipped: {idempotency_key} → {existing_id[:8]}")
            return existing_id

        message = TaskMessage(
            task_name       = task_name,
            args            = args or [],
            kwargs          = kwargs or {},
            priority        = priority,
            queue_name      = queue_name,
            max_retries     = max_retries,
            eta             = eta or (datetime.now() + timedelta(seconds=countdown) if countdown else None),
            idempotency_key = idempotency_key,
        )

        if idempotency_key:
            self._dedup_store[idempotency_key] = message.task_id

        self._queue.enqueue(message)
        return message.task_id


# ═══════════════════════════════════════════════════════════════
# CONCRETE TASKS (Niroskos Real Tasks)
# ═══════════════════════════════════════════════════════════════

class BlockchainScanTask(BaseTask):
    """
    Niroskos: Crypto payment confirmation.
    Self-rescheduling: scans blockchain → not confirmed yet → re-enqueue after 10s.
    Max 360 attempts (1 hour of 10-second intervals).

    Celery pattern:
      @shared_task(bind=True, max_retries=360)
      def scan_blockchain(self, payment_id):
          payment = Payment.objects.get(id=payment_id)
          tx = web3.eth.get_transaction(payment.tx_hash)
          if tx and tx.blockNumber and web3.eth.block_number - tx.blockNumber >= 12:
              payment.status = 'COMPLETED'
              payment.save()
          else:
              raise self.retry(countdown=10)   ← self-reschedule
    """
    name        = "blockchain_scan"
    max_retries = 360   # 1 hour
    queue       = "blockchain"
    priority    = TaskPriority.HIGH

    def __init__(self, producer: TaskProducer):
        self._producer = producer

    def run(self, payment_id: str, tx_hash: str, attempt: int = 1) -> dict:
        print(f"[BLOCKCHAIN] Scanning tx {tx_hash[:16]}... | attempt={attempt}")

        # Simulate: confirmed after attempt 3
        if attempt < 3:
            # Not confirmed — re-schedule after 10 seconds
            self._producer.send(
                task_name = self.name,
                kwargs    = {"payment_id": payment_id, "tx_hash": tx_hash, "attempt": attempt + 1},
                countdown = 10,
                priority  = TaskPriority.HIGH,
                idempotency_key = f"blockchain_{payment_id}_attempt_{attempt + 1}"
            )
            return {"status": "pending", "attempt": attempt}

        # Confirmed!
        print(f"[BLOCKCHAIN] ✓ Payment {payment_id} confirmed on blockchain!")
        return {"status": "confirmed", "payment_id": payment_id}

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        payment_id = kwargs.get("payment_id", "unknown")
        print(f"[BLOCKCHAIN] FAILED: payment {payment_id} → manual verification needed")


class BookingReminderTask(BaseTask):
    """48-hour reminder email before safari"""
    name     = "booking_reminder"
    queue    = "default"
    priority = TaskPriority.NORMAL

    def run(self, booking_id: str) -> dict:
        print(f"[REMINDER] Sending 48h reminder for booking {booking_id}")
        # notification_service.send(NotificationContext(event=BOOKING_REMINDER, ...))
        return {"status": "sent", "booking_id": booking_id}


class SAPSyncTask(BaseTask):
    """
    Push booking/invoice to SAP HANA.
    Retryable: SAP can be temporarily unavailable.
    Fatal: if booking doesn't exist → ValueError → DLQ immediately.
    """
    name        = "sap_sync"
    max_retries = 5
    queue       = "default"
    priority    = TaskPriority.NORMAL

    def run(self, booking_id: str, sync_type: str) -> dict:
        print(f"[SAP SYNC] Syncing booking {booking_id} to SAP ({sync_type})")
        # sap_connector.sync_booking(booking_id, sync_type)
        # → SAP HANA DocumentLines format
        return {"status": "synced", "booking_id": booking_id}

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        booking_id = kwargs.get("booking_id", args[0] if args else "unknown")
        print(f"[SAP SYNC] DEAD: booking {booking_id} → ops team notified via Slack")


class ExotelSMSTask(BaseTask):
    """
    Rate-limited SMS send (200/min via Exotel).
    RateLimitError → retry after retry_after seconds.
    """
    name        = "exotel_sms"
    max_retries = 3
    queue       = "default"
    priority    = TaskPriority.HIGH

    def run(self, phone: str, message: str) -> dict:
        print(f"[SMS TASK] → {phone}: {message[:40]}")
        # exotel_service.send_sms(phone, message)
        return {"status": "sent", "to": phone}


class CacheRefreshTask(BaseTask):
    """Booking payment cache refresh"""
    name     = "cache_refresh"
    queue    = "default"
    priority = TaskPriority.LOW

    def run(self, booking_id: str) -> dict:
        print(f"[CACHE] Refreshing payment cache for booking {booking_id}")
        # booking.refresh_payment_cache()
        return {"status": "refreshed", "booking_id": booking_id}
```

---

## Demo

```python
# ─── Setup ───────────────────────────────────────────────────
task_queue = PriorityTaskQueue()
dlq        = DeadLetterQueue()
policy     = RetryPolicy(max_retries=3, base_delay=0.1, max_delay=1.0)  # fast for demo
producer   = TaskProducer(task_queue)

# DLQ alert → Slack (simulated)
dlq.subscribe_alert(lambda e: print(f"  [SLACK #ops] ☠ DLQ: {e['task_name']} — {e['error'][:50]}"))

# Register tasks
blockchain_task = BlockchainScanTask(producer)
registry = {
    "blockchain_scan":   blockchain_task,
    "booking_reminder":  BookingReminderTask(),
    "sap_sync":          SAPSyncTask(),
    "exotel_sms":        ExotelSMSTask(),
    "cache_refresh":     CacheRefreshTask(),
}

# Start 2 workers
workers = [
    Worker(f"w{i}", task_queue, dlq, policy, registry)
    for i in range(1, 3)
]
for w in workers: w.start()


# ─── Flow 1: Priority Queue ───────────────────────────────────
print("=" * 55)
print("FLOW 1: Priority — critical beats low")
print("=" * 55)

# Enqueue low priority first
producer.send("cache_refresh", kwargs={"booking_id": "BKG-001"},
              priority=TaskPriority.LOW)
producer.send("booking_reminder", kwargs={"booking_id": "BKG-002"},
              priority=TaskPriority.NORMAL)
# Critical goes last but processed first
producer.send("exotel_sms",
              kwargs={"phone": "+254712345678", "message": "Your OTP is 847291"},
              priority=TaskPriority.CRITICAL)

time.sleep(1)


# ─── Flow 2: Blockchain Self-Rescheduling ─────────────────────
print("\n" + "=" * 55)
print("FLOW 2: Blockchain scan (self-rescheduling)")
print("=" * 55)

producer.send(
    "blockchain_scan",
    kwargs={"payment_id": "PAY-001", "tx_hash": "0xabc123def456", "attempt": 1},
    priority=TaskPriority.HIGH,
    idempotency_key="blockchain_PAY001_attempt_1"
)
time.sleep(2)


# ─── Flow 3: Retry + DLQ ─────────────────────────────────────
print("\n" + "=" * 55)
print("FLOW 3: Retry → DLQ (SAP temporarily down)")
print("=" * 55)

# Patch SAP task to fail
original_run = SAPSyncTask.run
fail_count   = [0]

def failing_sap_run(self, booking_id, sync_type="invoice"):
    fail_count[0] += 1
    if fail_count[0] <= 3:
        raise ConnectionError(f"SAP HANA connection timeout (attempt {fail_count[0]})")
    return {"status": "synced"}

SAPSyncTask.run = failing_sap_run

producer.send("sap_sync",
              kwargs={"booking_id": "BKG-003", "sync_type": "invoice"},
              priority=TaskPriority.NORMAL)

time.sleep(2)
print(f"\nDLQ contents: {dlq.list_failed()}")

# Replay from DLQ after fix
SAPSyncTask.run = original_run   # "Fix" the bug
if dlq.list_failed():
    failed_id = dlq.list_failed()[0]["task_id"]
    print(f"\nReplaying from DLQ: {failed_id[:8]}")
    dlq.replay(failed_id, task_queue)
    time.sleep(1)


# ─── Flow 4: Idempotency ─────────────────────────────────────
print("\n" + "=" * 55)
print("FLOW 4: Idempotent task (same key = skip)")
print("=" * 55)

key = "reminder_BKG004_48h"
id1 = producer.send("booking_reminder", kwargs={"booking_id": "BKG-004"},
                    idempotency_key=key)
id2 = producer.send("booking_reminder", kwargs={"booking_id": "BKG-004"},
                    idempotency_key=key)  # Duplicate!
print(f"Same task_id returned: {id1 == id2}")


# ─── Beat Scheduler ──────────────────────────────────────────
print("\n" + "=" * 55)
print("BEAT SCHEDULER: Periodic tasks")
print("=" * 55)

beat = BeatScheduler(task_queue)
beat.register(PeriodicTask(
    name="hourly_reminders", task_name="booking_reminder",
    interval=timedelta(seconds=3), kwargs={"booking_id": "SCHEDULED"}
))
beat.start()
time.sleep(4)   # Should fire once
beat.stop()

for w in workers: w.stop()
```

---

## Celery vs Custom — Mapping

```
Custom Class           | Celery Equivalent
───────────────────────────────────────────────────────────────
TaskMessage            | celery.app.task.Task (serialized as JSON)
PriorityTaskQueue      | Redis LIST (LPUSH/BRPOP)
Worker._run_loop()     | celery.worker.consumer.Consumer
Worker._execute()      | celery.app.trace.build_tracer
RetryPolicy            | @shared_task(max_retries=3, default_retry_delay=60)
  .should_retry()      | raise self.retry(exc=exc, countdown=N)
DeadLetterQueue        | task_routes + custom on_failure() → 'dead_letter' queue
BeatScheduler          | celery beat + CELERYBEAT_SCHEDULE
TaskProducer.send()    | task.apply_async(args, kwargs, countdown, eta, queue)
  countdown=N          | eta=now+timedelta(seconds=N)
TaskPriority.CRITICAL  | queue='critical' + CELERY_ROUTES
idempotency_key        | task_id= param in apply_async (custom dedup needed)
```

---

## Celery Config (Niroskos production settings)

```python
# settings/celery.py

CELERY_BROKER_URL    = 'redis://redis:6379/0'
CELERY_RESULT_BACKEND = 'redis://redis:6379/0'

# Queues with priorities
CELERY_TASK_QUEUES = {
    'critical':   {'exchange': 'critical',   'routing_key': 'critical'},
    'default':    {'exchange': 'default',    'routing_key': 'default'},
    'blockchain': {'exchange': 'blockchain', 'routing_key': 'blockchain'},
    'low':        {'exchange': 'low',        'routing_key': 'low'},
}
CELERY_DEFAULT_QUEUE = 'default'

# Route tasks to queues
CELERY_TASK_ROUTES = {
    'apps.payments.tasks.scan_blockchain':       {'queue': 'blockchain'},
    'apps.communications.tasks.send_sms':        {'queue': 'critical'},
    'apps.communications.tasks.send_otp':        {'queue': 'critical'},
    'apps.bookings.tasks.send_reminder':         {'queue': 'default'},
    'apps.integrations.tasks.sap_sync':          {'queue': 'default'},
    'apps.reports.tasks.generate_report':        {'queue': 'low'},
}

# Worker settings
CELERY_WORKER_PREFETCH_MULTIPLIER = 1      # Don't hoard tasks (fair distribution)
CELERY_TASK_ACKS_LATE             = True   # Ack AFTER completion (not on pickup)
CELERY_TASK_REJECT_ON_WORKER_LOST = True   # Re-queue if worker dies mid-task
CELERY_TASK_SERIALIZER            = 'json'
CELERY_RESULT_EXPIRES             = 3600   # Result TTL in Redis

# Beat schedule
from celery.schedules import crontab
CELERYBEAT_SCHEDULE = {
    'send-booking-reminders': {
        'task':     'apps.bookings.tasks.send_booking_reminders',
        'schedule': crontab(minute=0),    # Every hour
    },
    'sap-sync-bootstrap': {
        'task':     'apps.integrations.tasks.sap_sync_bootstrap',
        'schedule': crontab(minute='*/5'),
    },
    'cleanup-expired-drafts': {
        'task':     'apps.bookings.tasks.cleanup_expired_drafts',
        'schedule': crontab(minute='*/10'),
    },
}
```

---

## Interview Q&A

**Q: "Celery ka architecture explain karo — Niroskos mein kaise use kiya?"**
> "Celery teen components hai: Producer, Broker, Consumer. Django app Producer hai — task.apply_async() call karta hai jo message Redis (Broker) ke ek LIST mein LPUSH kar deta hai. Worker processes BRPOP karte hain — blocking pop — jab message aata hai immediately uthate hain. Niroskos mein teen types ke tasks the: blockchain scanner (crypto payment confirm, self-rescheduling every 10s), booking reminders (Celery Beat se hourly trigger), aur SAP HANA sync (booking data push karna). Different queues — critical, default, blockchain — different workers consume different queues, blockchain tasks normal tasks ko block na kar sakein."

**Q: "Retry mechanism kaise kaam karta hai?"**
> "Celery task mein bind=True karo → self milta hai. Exception aane pe raise self.retry(exc=exc, countdown=N) karo. Yeh current task fail mark karta hai aur ek nayi message queue mein daalta hai with eta=now+N. Exponential backoff ke liye: countdown = base_delay × (2 ^ attempt_number). Max retries exceed hone pe Celery on_failure() call karta hai — wahan hum DLQ mein push karte hain aur Slack pe ops alert jaata hai. Important: task_acks_late=True — task complete hone ke baad acknowledge karo, pehle nahi. Agar worker crash ho gaya mid-execution, Redis pe message wapas aa jaata hai."

**Q: "Dead Letter Queue — kya hai, kaise handle kiya?"**
> "Max retries exceed hone ke baad task execution stop ho jaata hai — message discard ho jaata hai by default. DLQ mein hum in failed tasks ko preserve karte hain ek separate queue/table mein. Niroskos mein: on_failure() mein failed task ka payload, error, traceback, aur attempt count ek FailedTask model mein save karte the. Slack #ops-alerts pe notification jaati thi. Ops team inspect karta, bug fix karta, phir admin interface se replay karta — same task dobara enqueue hota fresh attempt count ke saath. SAP HANA sync failures mostly transient network issues the — replay ke baad success ho jaata tha."

**Q: "Blockchain scanner task kaise kaam karta tha?"**
> "Self-rescheduling Celery task. User USDT bhejta tha — hum deposit_address generate karte the. Task start hota — blockchain scan karo, 12 confirmations chahiye. Agar less than 12: raise self.retry(countdown=10, max_retries=360) — 10 second baad dobara check. 360 attempts = 1 hour window. 12 confirmations hone pe payment COMPLETED mark karo, PaymentAllocation create karo, Django Signal fire karo — booking cache refresh. Agar 1 hour mein confirm nahi hua — DLQ mein daalo, customer ko email karo manual verification ke liye."

**Q: "Task idempotency — kaise ensure kiya?"**
> "Two approaches. First: idempotency_key as task ID — apply_async(task_id=f'reminder_{booking_id}_48h') — Celery deduplicates by task_id in result backend. Agar same ID ka task already exists, naya enqueue nahi hota. Second: task ke andar check karo — task start hone pe DB mein check karo kya yeh operation already complete hai. For booking reminders: reminder_sent flag on Booking model — task shuru hone pe check karo, agar True already → early return. Yeh important hai kyunki Beat scheduler + signal + webhook teeno ek hi task enqueue kar sakte hain concurrently."

---

*Last Updated: April 2026 | SDE-2 Interview Prep — Niroskos Celery Architecture*
