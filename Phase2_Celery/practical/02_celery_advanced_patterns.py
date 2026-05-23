"""
Celery Advanced Patterns — Production-Quality Demo
====================================================
File: 02_celery_advanced_patterns.py
Series: Phase 2 — Celery | 40 LPA Interview Prep

Run Modes:
----------
1. Demo (no Redis needed — pure Python simulation):
   python 02_celery_advanced_patterns.py
   python 02_celery_advanced_patterns.py chain
   python 02_celery_advanced_patterns.py group
   python 02_celery_advanced_patterns.py chord
   python 02_celery_advanced_patterns.py retry
   python 02_celery_advanced_patterns.py beat
   python 02_celery_advanced_patterns.py monitor
   python 02_celery_advanced_patterns.py priority
   python 02_celery_advanced_patterns.py routing
   python 02_celery_advanced_patterns.py all

2. Real Celery worker (Redis required):
   export REDIS_URL=redis://localhost:6379/0
   celery -A 02_celery_advanced_patterns worker -l info -Q default,high_priority,email,analytics

3. Real Celery with Beat:
   celery -A 02_celery_advanced_patterns beat -l info

4. Flower monitoring:
   celery -A 02_celery_advanced_patterns flower --port=5555

Design:
-------
- REDIS_AVAILABLE = False → all demos run as pure Python (no Celery install needed)
- REDIS_AVAILABLE = True  → actual Celery tasks defined and available for real workers
- Each section mirrors real Celery patterns exactly
"""

import os
import sys
import time
import random
import logging
import threading
import heapq
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Callable, Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from functools import wraps

# ─── Logging Setup ────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# ─── Redis / Celery Detection ─────────────────────────────────────────────────
REDIS_URL = os.environ.get("REDIS_URL", "")
REDIS_AVAILABLE = bool(REDIS_URL)

# Real Celery app — only created when Redis is available
celery_app = None

if REDIS_AVAILABLE:
    try:
        from celery import Celery, chain, group, chord
        from celery.schedules import crontab
        from celery.exceptions import SoftTimeLimitExceeded
        from celery.result import AsyncResult

        celery_app = Celery(
            "advanced_patterns",
            broker=REDIS_URL,
            backend=REDIS_URL.replace("/0", "/1") if REDIS_URL.endswith("/0") else REDIS_URL + "_results",
        )
        celery_app.conf.update(
            task_serializer="json",
            result_serializer="json",
            accept_content=["json"],
            task_acks_late=True,
            worker_prefetch_multiplier=1,
            task_reject_on_worker_lost=True,
            task_track_started=True,
            result_expires=3600,
            broker_connection_retry_on_startup=True,
            task_routes={
                "02_celery_advanced_patterns.fetch_page": {"queue": "default"},
                "02_celery_advanced_patterns.send_email_task": {"queue": "email"},
                "02_celery_advanced_patterns.track_event": {"queue": "analytics"},
                "02_celery_advanced_patterns.process_payment_task": {"queue": "high_priority"},
            },
            beat_schedule={
                "demo-heartbeat": {
                    "task": "02_celery_advanced_patterns.heartbeat_task",
                    "schedule": timedelta(seconds=30),
                },
                "demo-daily-report": {
                    "task": "02_celery_advanced_patterns.daily_report_task",
                    "schedule": crontab(hour=8, minute=0),
                },
            },
        )
        print(f"[Celery] Connected to broker: {REDIS_URL}")
    except ImportError:
        REDIS_AVAILABLE = False
        print("[Warning] Celery/Redis not available — running in Demo mode")


# =============================================================================
# SECTION 1: TASK CHAIN (SEQUENTIAL PIPELINE)
# =============================================================================

def simulate_chain() -> None:
    """
    Chain pattern: each step receives the previous step's output.
    Real-world use: ETL pipeline, order processing, data enrichment.
    """
    print("\n" + "=" * 60)
    print("SECTION 1: Chain — Sequential Data Pipeline")
    print("=" * 60)
    print("Concept: fetch → clean → transform → save")
    print("Each step receives the previous step's result.\n")

    # ── Step functions (mirror Celery task bodies) ────────────────────────────

    def fetch_data(url: str) -> Dict:
        """Step 1: Remote source se raw data fetch karo."""
        logger.info(f"[1/4] Fetching data from {url} ...")
        time.sleep(0.08)
        raw_records = [
            {"id": i, "value": random.randint(1, 100), "category": random.choice(["A", "B", "C"])}
            for i in range(1, 21)
        ]
        logger.info(f"      Fetched {len(raw_records)} raw records.")
        return {"records": raw_records, "source": url, "fetched_at": datetime.utcnow().isoformat()}

    def validate_and_clean(data: Dict) -> Dict:
        """Step 2: Invalid records filter karo."""
        logger.info("[2/4] Validating and cleaning records ...")
        time.sleep(0.05)
        valid = [r for r in data["records"] if r["value"] > 10]  # filter low-value
        removed = len(data["records"]) - len(valid)
        logger.info(f"      Kept {len(valid)} records, removed {removed} invalid.")
        return {"records": valid, "source": data["source"], "removed_count": removed}

    def enrich_data(data: Dict) -> Dict:
        """Step 3: Extra metadata add karo."""
        logger.info("[3/4] Enriching records with metadata ...")
        time.sleep(0.06)
        enriched = []
        for r in data["records"]:
            r["grade"] = "High" if r["value"] > 70 else "Medium" if r["value"] > 40 else "Low"
            r["processed_at"] = datetime.utcnow().isoformat()
            enriched.append(r)
        return {**data, "records": enriched, "enriched": True}

    def save_to_db(data: Dict) -> Dict:
        """Step 4: Processed data DB mein save karo."""
        logger.info(f"[4/4] Saving {len(data['records'])} records to database ...")
        time.sleep(0.04)
        # Simulate DB insert
        saved_ids = [r["id"] for r in data["records"]]
        return {
            "status": "success",
            "saved_count": len(saved_ids),
            "removed_count": data.get("removed_count", 0),
            "source": data["source"],
        }

    # ── Execute as sequential chain ───────────────────────────────────────────
    start = time.time()
    result = save_to_db(
        enrich_data(
            validate_and_clean(
                fetch_data("https://api.example.com/products")
            )
        )
    )
    elapsed = time.time() - start

    print(f"\n  Chain Result: {result}")
    print(f"  Total time:  {elapsed:.3f}s")

    # ── Real Celery equivalent ────────────────────────────────────────────────
    print("""
  ┌─ Real Celery Chain ────────────────────────────────────────┐
  │                                                             │
  │  from celery import chain                                   │
  │                                                             │
  │  pipeline = chain(                                          │
  │      fetch_data.s("https://api.example.com/products"),     │
  │      validate_and_clean.s(),   # receives fetch result     │
  │      enrich_data.s(),          # receives clean result     │
  │      save_to_db.s()            # receives enrich result    │
  │  )                                                          │
  │                                                             │
  │  # Async execution                                          │
  │  result = pipeline.apply_async()                            │
  │  final = result.get(timeout=60)                            │
  │                                                             │
  │  # Shorthand with | operator                               │
  │  pipeline = (                                               │
  │      fetch_data.s(url) | validate_and_clean.s()           │
  │      | enrich_data.s() | save_to_db.s()                   │
  │  )                                                          │
  │                                                             │
  │  # Immutable step (ignore parent result):                  │
  │  chain(..., log_audit.si(user_id))  # .si() not .s()      │
  └─────────────────────────────────────────────────────────────┘
""")


# =============================================================================
# SECTION 2: GROUP (PARALLEL EXECUTION)
# =============================================================================

def simulate_group() -> None:
    """
    Group pattern: multiple independent tasks run in parallel.
    Real-world use: bulk notifications, parallel API calls, batch processing.
    """
    print("\n" + "=" * 60)
    print("SECTION 2: Group — Parallel Execution")
    print("=" * 60)
    print("Concept: Send emails to 20 users — parallel vs sequential.\n")

    def send_email(recipient: str, subject: str, template: str = "default") -> Dict:
        """Simulate sending a single email via external API."""
        latency = random.uniform(0.05, 0.25)  # 50-250ms per email API call
        time.sleep(latency)
        success = random.random() > 0.08  # 92% success rate
        return {
            "recipient": recipient,
            "subject": subject,
            "sent": success,
            "latency_ms": round(latency * 1000),
            "error": None if success else "SMTP connection timeout",
        }

    recipients = [f"user{i:02d}@example.com" for i in range(1, 21)]
    subject = "Your weekly product digest"

    # ── Sequential baseline ───────────────────────────────────────────────────
    logger.info("Running SEQUENTIAL email send ...")
    start = time.time()
    seq_results = [send_email(r, subject) for r in recipients]
    t_seq = time.time() - start
    seq_sent = sum(1 for r in seq_results if r["sent"])

    # ── Parallel with ThreadPoolExecutor (simulates Celery group) ─────────────
    logger.info("Running PARALLEL email send (ThreadPool — simulates Celery group) ...")
    start = time.time()
    par_results = []
    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = {pool.submit(send_email, r, subject): r for r in recipients}
        for future in as_completed(futures):
            try:
                par_results.append(future.result())
            except Exception as exc:
                par_results.append({"recipient": futures[future], "sent": False, "error": str(exc)})
    t_par = time.time() - start
    par_sent = sum(1 for r in par_results if r["sent"])

    # ── Results ───────────────────────────────────────────────────────────────
    speedup = t_seq / t_par if t_par > 0 else 0
    print(f"\n  Sequential:  {t_seq:.3f}s  — sent {seq_sent}/{len(recipients)}")
    print(f"  Parallel:    {t_par:.3f}s  — sent {par_sent}/{len(recipients)}")
    print(f"  Speedup:     {speedup:.1f}x faster")

    failed = [r for r in par_results if not r["sent"]]
    if failed:
        print(f"  Failed:      {[r['recipient'] for r in failed]}")

    print("""
  ┌─ Real Celery Group ─────────────────────────────────────────┐
  │                                                             │
  │  from celery import group                                   │
  │                                                             │
  │  # Static group                                             │
  │  email_group = group(                                       │
  │      send_email.s(r, subject)                              │
  │      for r in recipients                                    │
  │  )                                                          │
  │  group_result = email_group.apply_async()                   │
  │  results = group_result.get(timeout=60)                    │
  │                                                             │
  │  # Check status                                             │
  │  group_result.successful()   # All passed?                 │
  │  group_result.failed()       # Any failed?                 │
  │  group_result.ready()        # All done (pass or fail)?    │
  │                                                             │
  │  # Individual results with error handling                  │
  │  for ar in group_result.results:                            │
  │      try:                                                   │
  │          val = ar.get(timeout=10)                          │
  │      except Exception as e:                                 │
  │          print(f"Task {ar.id} failed: {e}")                │
  └─────────────────────────────────────────────────────────────┘
""")


# =============================================================================
# SECTION 3: CHORD (MAP-REDUCE / PARALLEL → CALLBACK)
# =============================================================================

def simulate_chord() -> None:
    """
    Chord pattern: parallel tasks → single callback with all results.
    Real-world use: web scraping + aggregation, parallel reports → summary.
    """
    print("\n" + "=" * 60)
    print("SECTION 3: Chord — Parallel Scrape → Aggregate")
    print("=" * 60)
    print("Concept: Scrape 10 pages in parallel, then aggregate all results.\n")

    def scrape_product_page(page_id: int) -> Dict:
        """Single page ko scrape karo."""
        latency = random.uniform(0.05, 0.2)
        time.sleep(latency)
        products = [
            {
                "id": page_id * 100 + i,
                "name": f"Product {page_id}-{i}",
                "price": round(random.uniform(99, 9999), 2),
                "in_stock": random.random() > 0.2,
                "rating": round(random.uniform(1.0, 5.0), 1),
            }
            for i in range(1, random.randint(5, 15))
        ]
        return {
            "page_id": page_id,
            "products": products,
            "scraped_at": datetime.utcnow().isoformat(),
        }

    def aggregate_catalog(page_results: List[Dict]) -> Dict:
        """
        Chord callback: saare pages ke results ek saath milte hain.
        Yeh exactly wahi hai jo Celery callback ko milta hai.
        """
        all_products = []
        for page in page_results:
            all_products.extend(page["products"])

        in_stock = [p for p in all_products if p["in_stock"]]
        prices = [p["price"] for p in all_products]
        ratings = [p["rating"] for p in all_products]

        return {
            "total_pages": len(page_results),
            "total_products": len(all_products),
            "in_stock_count": len(in_stock),
            "out_of_stock_count": len(all_products) - len(in_stock),
            "avg_price": round(sum(prices) / len(prices), 2),
            "min_price": min(prices),
            "max_price": max(prices),
            "avg_rating": round(sum(ratings) / len(ratings), 2),
            "top_rated": max(all_products, key=lambda p: p["rating"])["name"],
        }

    page_ids = list(range(1, 11))  # 10 pages

    # ── Parallel scraping (group phase) ───────────────────────────────────────
    logger.info(f"Scraping {len(page_ids)} pages in parallel ...")
    start = time.time()
    with ThreadPoolExecutor(max_workers=5) as pool:
        page_results = list(pool.map(scrape_product_page, page_ids))
    t_parallel = time.time() - start

    # ── Aggregate (callback phase) ────────────────────────────────────────────
    logger.info("Running aggregate callback ...")
    summary = aggregate_catalog(page_results)
    t_total = time.time() - start

    print(f"\n  Pages scraped: {len(page_ids)}  (parallel in {t_parallel:.3f}s)")
    print(f"  Total time:    {t_total:.3f}s")
    print(f"  Summary:")
    for k, v in summary.items():
        print(f"    {k}: {v}")

    print("""
  ┌─ Real Celery Chord ─────────────────────────────────────────┐
  │                                                             │
  │  from celery import chord, group                            │
  │                                                             │
  │  # REQUIRES result backend (Redis/DB)                      │
  │  result = chord(                                            │
  │      group(scrape_product_page.s(pid) for pid in page_ids) │
  │  )(aggregate_catalog.s())                                   │
  │                                                             │
  │  # Wait for chord to finish                                 │
  │  summary = result.get(timeout=300)                         │
  │                                                             │
  │  # Without result backend → chord WILL HANG!               │
  │  # app = Celery(backend='redis://...')  ← REQUIRED         │
  └─────────────────────────────────────────────────────────────┘
""")


# =============================================================================
# SECTION 4: RETRY WITH EXPONENTIAL BACKOFF
# =============================================================================

def simulate_retry_backoff() -> None:
    """
    Retry strategy with exponential backoff + jitter.
    Real-world use: external API calls, payment gateways, email services.
    """
    print("\n" + "=" * 60)
    print("SECTION 4: Retry — Exponential Backoff + Jitter")
    print("=" * 60)
    print("Concept: Flaky API — retry with increasing delays.\n")

    class FlakyAPIClient:
        """Simulate an unreliable third-party API."""

        def __init__(self, success_after_attempt: int = 4):
            self.attempt = 0
            self.success_after = success_after_attempt

        def call(self, payload: Dict) -> Dict:
            self.attempt += 1
            if self.attempt < self.success_after:
                if self.attempt == 1:
                    raise ConnectionError("Connection refused")
                elif self.attempt == 2:
                    raise TimeoutError("Request timed out after 30s")
                else:
                    raise OSError(f"Server error 503 (attempt {self.attempt})")
            return {"status": "success", "data": payload, "attempt": self.attempt}

    def with_exponential_backoff(
        fn: Callable,
        max_retries: int = 5,
        base_delay: float = 0.05,  # small for demo
        max_delay: float = 0.5,
        jitter: bool = True,
    ) -> Any:
        """
        Generic exponential backoff wrapper.
        Mirrors Celery's retry_backoff + retry_jitter behavior.
        """
        last_exc = None
        for attempt in range(max_retries + 1):
            try:
                result = fn()
                logger.info(f"  [Retry] SUCCESS on attempt {attempt + 1}")
                return result
            except Exception as exc:
                last_exc = exc
                if attempt == max_retries:
                    logger.error(f"  [Retry] EXHAUSTED after {max_retries} retries: {exc}")
                    raise

                # Exponential: 2^0=1, 2^1=2, 2^2=4, ...  (scaled by base_delay)
                exp_delay = base_delay * (2 ** attempt)
                # Jitter: add up to 20% randomness → prevents thundering herd
                jitter_offset = random.uniform(0, exp_delay * 0.2) if jitter else 0
                delay = min(exp_delay + jitter_offset, max_delay)

                logger.warning(
                    f"  [Retry] Attempt {attempt + 1} FAILED: {exc!r} "
                    f"— retrying in {delay:.3f}s ..."
                )
                time.sleep(delay)

        raise last_exc  # Should never reach here

    # ── Run demos ─────────────────────────────────────────────────────────────
    print("  [Demo 1] API succeeds on attempt 4:")
    api = FlakyAPIClient(success_after_attempt=4)
    result = with_exponential_backoff(lambda: api.call({"user_id": "u123"}))
    print(f"  Result: {result}\n")

    print("  [Demo 2] API always fails (exhaust retries):")
    api_broken = FlakyAPIClient(success_after_attempt=999)
    try:
        with_exponential_backoff(
            lambda: api_broken.call({"user_id": "u456"}),
            max_retries=3,
        )
    except Exception as exc:
        print(f"  Final failure: {type(exc).__name__}: {exc}\n")

    print("""
  ┌─ Real Celery Retry ─────────────────────────────────────────┐
  │                                                             │
  │  # Manual exponential backoff                               │
  │  @app.task(bind=True, max_retries=5)                       │
  │  def call_payment_api(self, order_id):                      │
  │      try:                                                   │
  │          return payment_gateway.charge(order_id)            │
  │      except (ConnectionError, TimeoutError) as exc:         │
  │          countdown = 2 ** self.request.retries              │
  │          raise self.retry(exc=exc, countdown=countdown)    │
  │                                                             │
  │  # Built-in (recommended for production)                   │
  │  @app.task(                                                  │
  │      autoretry_for=(ConnectionError, TimeoutError),        │
  │      retry_backoff=True,      # auto exponential           │
  │      retry_backoff_max=600,   # cap at 10 minutes          │
  │      retry_jitter=True,       # thundering herd prevention │
  │      max_retries=5,                                         │
  │  )                                                          │
  │  def call_payment_api(order_id):                            │
  │      return payment_gateway.charge(order_id)                │
  └─────────────────────────────────────────────────────────────┘
""")


# =============================================================================
# SECTION 5: CELERY BEAT — PERIODIC TASK SCHEDULE (DEMO)
# =============================================================================

def simulate_beat_schedule() -> None:
    """
    Demonstrate Beat schedule configuration and simulate periodic execution.
    """
    print("\n" + "=" * 60)
    print("SECTION 5: Celery Beat — Periodic Tasks")
    print("=" * 60)
    print("Concept: Schedule recurring tasks (like cron, but Celery-native).\n")

    # ── Show configuration ────────────────────────────────────────────────────
    BEAT_SCHEDULE_EXAMPLE = """
  # celeryconfig.py — Beat Schedule Configuration
  from celery.schedules import crontab
  from datetime import timedelta

  app.conf.beat_schedule = {
      # Every 30 seconds
      'system-heartbeat': {
          'task': 'tasks.heartbeat',
          'schedule': timedelta(seconds=30),
      },
      # Every 5 minutes
      'refresh-product-cache': {
          'task': 'tasks.refresh_cache',
          'schedule': crontab(minute='*/5'),
          'args': ('products',),
      },
      # Daily at 8:00 AM IST
      'daily-sales-report': {
          'task': 'tasks.send_daily_report',
          'schedule': crontab(hour=8, minute=0),
          'kwargs': {'report_type': 'sales'},
      },
      # Every Monday 9:30 AM
      'weekly-digest': {
          'task': 'tasks.send_weekly_digest',
          'schedule': crontab(hour=9, minute=30, day_of_week='monday'),
      },
      # 1st of every month, midnight
      'monthly-billing': {
          'task': 'tasks.process_billing',
          'schedule': crontab(day_of_month=1, hour=0, minute=0),
      },
  }
  app.conf.timezone = 'Asia/Kolkata'
"""
    print(BEAT_SCHEDULE_EXAMPLE)

    # ── Simulate scheduled execution ──────────────────────────────────────────
    @dataclass(order=True)
    class ScheduledTask:
        next_run: float = field(compare=True)
        name: str = field(compare=False)
        interval_seconds: float = field(compare=False)
        fn: Callable = field(compare=False)
        run_count: int = field(default=0, compare=False)

    # Simulated task functions
    executed_log = []

    def heartbeat():
        executed_log.append(("heartbeat", datetime.utcnow()))
        return "ALIVE"

    def refresh_cache(key: str):
        executed_log.append(("refresh_cache", datetime.utcnow()))
        return f"Cache '{key}' refreshed"

    def cleanup_sessions():
        executed_log.append(("cleanup_sessions", datetime.utcnow()))
        return "Sessions cleaned"

    # Build a minimal scheduler (priority queue)
    now = time.time()
    schedule_heap: List[ScheduledTask] = [
        ScheduledTask(now + 0.1, "heartbeat", 0.5, heartbeat),
        ScheduledTask(now + 0.2, "refresh_cache", 0.8, lambda: refresh_cache("products")),
        ScheduledTask(now + 0.3, "cleanup_sessions", 1.2, cleanup_sessions),
    ]
    heapq.heapify(schedule_heap)

    logger.info("  [Beat] Simulating 3 seconds of scheduled execution ...")
    simulation_end = time.time() + 3.0

    while time.time() < simulation_end and schedule_heap:
        task = heapq.heappop(schedule_heap)

        wait = task.next_run - time.time()
        if wait > 0:
            time.sleep(wait)

        if time.time() > simulation_end:
            break

        result = task.fn()
        task.run_count += 1
        logger.info(f"  [Beat] Executed '{task.name}' → {result!r} (run #{task.run_count})")

        # Re-schedule
        task.next_run = time.time() + task.interval_seconds
        heapq.heappush(schedule_heap, task)

    print(f"\n  Executed {len(executed_log)} tasks in simulation:")
    from collections import Counter
    counts = Counter(name for name, _ in executed_log)
    for task_name, count in sorted(counts.items()):
        print(f"    {task_name}: {count} times")

    print("""
  ┌─ Beat Run Commands ─────────────────────────────────────────┐
  │                                                             │
  │  # Start beat scheduler (separate process!)                │
  │  celery -A myapp beat -l info                              │
  │                                                             │
  │  # Start worker (separate process!)                        │
  │  celery -A myapp worker -l info                            │
  │                                                             │
  │  # django-celery-beat (DB-stored schedules)                │
  │  pip install django-celery-beat                             │
  │  # Add 'django_celery_beat' to INSTALLED_APPS              │
  │  # python manage.py migrate                                 │
  │  celery -A myapp beat -l info \\                            │
  │      --scheduler django_celery_beat.schedulers:DatabaseScheduler
  └─────────────────────────────────────────────────────────────┘
""")


# =============================================================================
# SECTION 6: TASK PROGRESS MONITORING
# =============================================================================

def simulate_progress_tracking() -> None:
    """
    Long-running task with real-time progress updates.
    Real-world use: CSV imports, report generation, video processing.
    """
    print("\n" + "=" * 60)
    print("SECTION 6: Task Progress Monitoring")
    print("=" * 60)
    print("Concept: Long task updates its state — frontend can poll for progress.\n")

    # ── Mock AsyncResult (mirrors Celery's AsyncResult API) ───────────────────
    class MockAsyncResult:
        def __init__(self, task_id: str):
            self.id = task_id
            self._state = "PENDING"
            self._meta: Dict = {}
            self._lock = threading.Lock()

        def update_state(self, state: str, meta: Dict) -> None:
            with self._lock:
                self._state = state
                self._meta = meta

        @property
        def state(self) -> str:
            with self._lock:
                return self._state

        @property
        def info(self) -> Dict:
            with self._lock:
                return self._meta.copy()

        def get_status_response(self) -> Dict:
            """Simulates what a REST endpoint would return."""
            state = self.state
            info = self.info
            if state == "PENDING":
                return {"status": "waiting", "percent": 0}
            elif state == "STARTED":
                return {"status": "started", "percent": 0}
            elif state == "PROGRESS":
                return {
                    "status": "in_progress",
                    "percent": info.get("percent", 0),
                    "current": info.get("current", 0),
                    "total": info.get("total", 0),
                    "message": info.get("message", ""),
                }
            elif state == "SUCCESS":
                return {"status": "complete", "percent": 100, "result": info.get("result")}
            else:
                return {"status": "failed", "error": str(info)}

    # ── Simulate long-running task (runs in background thread) ────────────────
    def long_import_task(total_rows: int, result_obj: MockAsyncResult) -> None:
        """CSV import karo — progress updates ke saath."""
        result_obj.update_state("STARTED", {"total": total_rows, "percent": 0})

        errors = []
        processed = 0
        skipped = 0

        for i in range(total_rows):
            time.sleep(0.005)  # Simulate row processing time

            # Occasionally encounter errors (5% rate)
            if random.random() < 0.05:
                errors.append({"row": i + 1, "error": "Invalid format"})
                skipped += 1
            else:
                processed += 1

            # Update progress every 10%
            if (i + 1) % max(1, total_rows // 10) == 0:
                percent = round((i + 1) / total_rows * 100)
                result_obj.update_state("PROGRESS", {
                    "percent": percent,
                    "current": i + 1,
                    "total": total_rows,
                    "processed": processed,
                    "skipped": skipped,
                    "errors": len(errors),
                    "message": f"Importing row {i + 1}/{total_rows}",
                })

        result_obj.update_state("SUCCESS", {
            "percent": 100,
            "result": {
                "total": total_rows,
                "processed": processed,
                "skipped": skipped,
                "errors": errors[:5],  # first 5 errors
            },
        })

    # ── Polling loop (simulates frontend polling) ─────────────────────────────
    task_id = "import-task-abc123"
    async_result = MockAsyncResult(task_id)

    logger.info(f"  Starting long task (task_id={task_id}) ...")

    # Run task in background thread
    worker_thread = threading.Thread(
        target=long_import_task, args=(100, async_result), daemon=True
    )
    worker_thread.start()

    print(f"  Polling task status (task_id={task_id}):\n")

    last_percent = -1
    while True:
        status = async_result.get_status_response()

        # Only print when progress changes
        if status.get("percent", -1) != last_percent:
            last_percent = status.get("percent", -1)
            if status["status"] in ("in_progress", "started", "waiting"):
                pct = status.get("percent", 0)
                bar = "█" * (pct // 5) + "░" * (20 - pct // 5)
                print(f"  [{bar}] {pct:3d}%  {status.get('message', '')}")

        if status["status"] in ("complete", "failed"):
            print(f"\n  Final status: {status}")
            break

        time.sleep(0.1)

    worker_thread.join(timeout=10)

    print("""
  ┌─ Real Celery Progress Tracking ────────────────────────────┐
  │                                                             │
  │  @app.task(bind=True)                                       │
  │  def import_csv(self, file_path):                           │
  │      rows = read_csv(file_path)                            │
  │      total = len(rows)                                      │
  │                                                             │
  │      for i, row in enumerate(rows):                        │
  │          process_row(row)                                   │
  │          if i % (total // 10) == 0:                        │
  │              self.update_state(                             │
  │                  state='PROGRESS',                          │
  │                  meta={'percent': i*100//total,            │
  │                        'current': i, 'total': total}       │
  │              )                                              │
  │      return {'imported': total}                            │
  │                                                             │
  │  # FastAPI polling endpoint                                 │
  │  @router.get("/status/{task_id}")                          │
  │  def get_status(task_id: str):                              │
  │      result = AsyncResult(task_id)                         │
  │      if result.state == 'PROGRESS':                        │
  │          return result.info  # {'percent': 50, ...}        │
  └─────────────────────────────────────────────────────────────┘
""")


# =============================================================================
# SECTION 7: PRIORITY QUEUES (ROUTING)
# =============================================================================

def simulate_priority_and_routing() -> None:
    """
    Priority queues and task routing demonstration.
    Real-world use: isolate critical tasks, prevent queue starvation.
    """
    print("\n" + "=" * 60)
    print("SECTION 7: Priority Queues & Task Routing")
    print("=" * 60)
    print("Concept: Route tasks to different queues based on priority.\n")

    # ── Task queue simulator ───────────────────────────────────────────────────
    from queue import PriorityQueue
    import uuid

    @dataclass(order=True)
    class QueuedTask:
        priority: int         # Lower number = higher priority (0=urgent)
        task_id: str = field(compare=False, default_factory=lambda: str(uuid.uuid4())[:8])
        task_name: str = field(compare=False, default="")
        payload: Dict = field(compare=False, default_factory=dict)
        queued_at: float = field(compare=False, default_factory=time.time)

    # Simulated queue processor
    class SimpleWorker:
        def __init__(self, name: str, queues: List[str], concurrency: int = 2):
            self.name = name
            self.queues = queues
            self.concurrency = concurrency
            self.processed: List[Dict] = []

        def process(self, task: QueuedTask, processing_time: float = 0.02) -> Dict:
            time.sleep(processing_time)
            result = {
                "worker": self.name,
                "task_id": task.task_id,
                "task_name": task.task_name,
                "priority": task.priority,
                "latency_ms": round((time.time() - task.queued_at) * 1000),
            }
            self.processed.append(result)
            return result

    # ── Enqueue tasks with different priorities ───────────────────────────────
    task_definitions = [
        # (priority, queue, name, count)
        (0, "high_priority", "process_payment", 3),
        (0, "high_priority", "send_otp", 5),
        (1, "default", "generate_thumbnail", 8),
        (1, "default", "update_user_profile", 6),
        (2, "email", "send_newsletter", 4),
        (2, "email", "send_welcome_email", 3),
        (3, "analytics", "track_page_view", 12),
        (3, "analytics", "log_event", 10),
    ]

    # Separate queues
    queues: Dict[str, List[QueuedTask]] = {
        "high_priority": [],
        "default": [],
        "email": [],
        "analytics": [],
    }

    total_enqueued = 0
    for priority, queue_name, task_name, count in task_definitions:
        for _ in range(count):
            task = QueuedTask(
                priority=priority,
                task_name=task_name,
                payload={"timestamp": datetime.utcnow().isoformat()},
            )
            queues[queue_name].append(task)
            total_enqueued += 1

    # ── Process with workers ───────────────────────────────────────────────────
    workers = {
        "high_priority": SimpleWorker("w-hp", ["high_priority"], concurrency=4),
        "default": SimpleWorker("w-default", ["default"], concurrency=4),
        "email": SimpleWorker("w-email", ["email"], concurrency=2),
        "analytics": SimpleWorker("w-analytics", ["analytics"], concurrency=2),
    }

    start = time.time()
    all_results = []

    def process_queue(queue_name: str) -> None:
        worker = workers[queue_name]
        with ThreadPoolExecutor(max_workers=worker.concurrency) as pool:
            futures = [
                pool.submit(worker.process, task, 0.01)
                for task in queues[queue_name]
            ]
            for f in as_completed(futures):
                all_results.append(f.result())

    # Process all queues in parallel
    with ThreadPoolExecutor(max_workers=4) as outer_pool:
        outer_futures = [
            outer_pool.submit(process_queue, qname)
            for qname in queues.keys()
        ]
        for f in as_completed(outer_futures):
            f.result()

    elapsed = time.time() - start

    # ── Report ────────────────────────────────────────────────────────────────
    print(f"  Total tasks enqueued: {total_enqueued}")
    print(f"  Total processed:      {len(all_results)}")
    print(f"  Total time:           {elapsed:.3f}s\n")

    from collections import defaultdict
    by_queue = defaultdict(list)
    for r in all_results:
        by_queue[r["worker"]].append(r["latency_ms"])

    print("  Queue Performance:")
    print(f"  {'Worker':<15} {'Tasks':>6} {'Avg Latency (ms)':>20}")
    print(f"  {'-'*15} {'-'*6} {'-'*20}")
    for worker_name, latencies in sorted(by_queue.items()):
        avg_lat = sum(latencies) / len(latencies)
        print(f"  {worker_name:<15} {len(latencies):>6} {avg_lat:>20.1f}")

    print("""
  ┌─ Real Celery Routing Config ────────────────────────────────┐
  │                                                             │
  │  # celeryconfig.py                                          │
  │  CELERY_TASK_ROUTES = {                                     │
  │      'tasks.process_payment':  {'queue': 'high_priority'}, │
  │      'tasks.send_otp':         {'queue': 'high_priority'}, │
  │      'tasks.send_email':       {'queue': 'email'},         │
  │      'tasks.track_analytics':  {'queue': 'analytics'},     │
  │      'tasks.*':                {'queue': 'default'},        │
  │  }                                                          │
  │                                                             │
  │  # Start workers for each queue:                           │
  │  # celery -A myapp worker -Q high_priority -c 4 -n hp@%h  │
  │  # celery -A myapp worker -Q default -c 4 -n def@%h       │
  │  # celery -A myapp worker -Q email -c 2 -n email@%h       │
  │  # celery -A myapp worker -Q analytics -c 8 -n ana@%h     │
  └─────────────────────────────────────────────────────────────┘
""")


# =============================================================================
# SECTION 8: SOFT vs HARD TIME LIMIT
# =============================================================================

def simulate_time_limits() -> None:
    """
    Soft time limit → graceful cleanup.
    Hard time limit → immediate kill.
    """
    print("\n" + "=" * 60)
    print("SECTION 8: Soft vs Hard Time Limits")
    print("=" * 60)
    print("Concept: Soft limit allows cleanup; hard limit = instant kill.\n")

    class SoftTimeLimitExceededDemo(Exception):
        pass

    def run_with_soft_time_limit(
        fn: Callable,
        soft_limit: float,
        hard_limit: float,
        *args,
        **kwargs,
    ) -> Any:
        """
        Simulate Celery's soft/hard time limit behavior using threading.
        """
        result_holder = {"result": None, "exception": None, "cleanup_done": False}
        soft_exceeded = threading.Event()
        hard_exceeded = threading.Event()

        def target():
            try:
                result_holder["result"] = fn(soft_exceeded, *args, **kwargs)
            except SoftTimeLimitExceededDemo:
                logger.warning("  [TimeLimit] SoftTimeLimitExceeded caught — running cleanup ...")
                result_holder["cleanup_done"] = True
                result_holder["exception"] = SoftTimeLimitExceededDemo("Task exceeded soft limit")
            except Exception as exc:
                result_holder["exception"] = exc

        thread = threading.Thread(target=target, daemon=True)

        # Soft limit timer
        def trigger_soft():
            time.sleep(soft_limit)
            soft_exceeded.set()

        # Hard limit timer (terminate thread — simulated)
        def trigger_hard():
            time.sleep(hard_limit)
            hard_exceeded.set()

        soft_timer = threading.Thread(target=trigger_soft, daemon=True)
        hard_timer = threading.Thread(target=trigger_hard, daemon=True)

        start = time.time()
        thread.start()
        soft_timer.start()
        hard_timer.start()

        thread.join(timeout=hard_limit + 0.2)

        elapsed = time.time() - start
        return result_holder, elapsed

    # ── Demo Task: processes items until soft limit ────────────────────────────
    def long_processing_task(soft_signal: threading.Event, total_items: int = 200) -> Dict:
        """Process items — stops gracefully when soft limit hits."""
        temp_connections = ["conn_1", "conn_2"]  # resources to clean up
        processed = []

        for i in range(total_items):
            if soft_signal.is_set():
                raise SoftTimeLimitExceededDemo()

            time.sleep(0.01)  # simulate per-item processing
            processed.append(i)

        return {"processed": len(processed), "status": "complete"}

    # Run with soft limit that will trigger
    logger.info("  Running task with tight soft limit (will trigger) ...")
    holder, elapsed = run_with_soft_time_limit(
        long_processing_task, soft_limit=0.3, hard_limit=1.0, total_items=200
    )

    print(f"\n  Elapsed: {elapsed:.3f}s")
    print(f"  Cleanup done: {holder['cleanup_done']}")
    print(f"  Exception: {type(holder['exception']).__name__}")

    # Run with generous limit (will complete)
    logger.info("  Running task with generous limit (will complete normally) ...")
    holder2, elapsed2 = run_with_soft_time_limit(
        long_processing_task, soft_limit=5.0, hard_limit=10.0, total_items=20
    )
    print(f"\n  Elapsed: {elapsed2:.3f}s")
    print(f"  Result: {holder2['result']}")
    print(f"  Cleanup needed: {holder2['cleanup_done']}")

    print("""
  ┌─ Real Celery Time Limits ───────────────────────────────────┐
  │                                                             │
  │  from celery.exceptions import SoftTimeLimitExceeded       │
  │                                                             │
  │  @app.task(soft_time_limit=55, time_limit=60)              │
  │  def process_large_file(file_id: str):                      │
  │      resources = []                                         │
  │      try:                                                   │
  │          resources = acquire_resources()                    │
  │          return do_heavy_processing(file_id)                │
  │      except SoftTimeLimitExceeded:                         │
  │          # 5 seconds left — cleanup!                       │
  │          for r in resources: r.close()                     │
  │          save_partial_progress(file_id)                    │
  │          raise  # Mark task as FAILED                      │
  │      finally:                                               │
  │          # Always runs (even on hard limit? No — SIGKILL!) │
  │          pass                                               │
  │                                                             │
  │  Soft: Python exception → catchable → 5s cleanup window   │
  │  Hard: SIGKILL → no cleanup → process dies immediately     │
  └─────────────────────────────────────────────────────────────┘
""")


# =============================================================================
# REAL CELERY TASKS (only defined when Redis available)
# =============================================================================

if REDIS_AVAILABLE and celery_app:
    from celery import chain, group, chord
    from celery.exceptions import SoftTimeLimitExceeded

    @celery_app.task(
        bind=True,
        name="02_celery_advanced_patterns.heartbeat_task",
        queue="default",
    )
    def heartbeat_task(self) -> Dict:
        return {"worker": self.request.hostname, "timestamp": datetime.utcnow().isoformat()}

    @celery_app.task(
        name="02_celery_advanced_patterns.daily_report_task",
        queue="default",
    )
    def daily_report_task(report_type: str = "summary") -> Dict:
        logger.info(f"Generating daily {report_type} report ...")
        return {"report_type": report_type, "generated_at": datetime.utcnow().isoformat()}

    @celery_app.task(
        bind=True,
        name="02_celery_advanced_patterns.fetch_page",
        queue="default",
        autoretry_for=(ConnectionError, TimeoutError),
        retry_backoff=True,
        retry_backoff_max=300,
        retry_jitter=True,
        max_retries=3,
    )
    def fetch_page(self, page_id: int) -> Dict:
        """Fetch a product page — retries on network errors."""
        import random
        time.sleep(random.uniform(0.05, 0.15))
        products = [
            {"id": page_id * 100 + i, "price": round(random.uniform(99, 9999), 2)}
            for i in range(random.randint(5, 15))
        ]
        return {"page_id": page_id, "products": products}

    @celery_app.task(
        name="02_celery_advanced_patterns.aggregate_pages",
        queue="default",
    )
    def aggregate_pages(page_results: List[Dict]) -> Dict:
        """Chord callback — receives list of all page results."""
        all_products = [p for page in page_results for p in page["products"]]
        prices = [p["price"] for p in all_products]
        return {
            "total_pages": len(page_results),
            "total_products": len(all_products),
            "avg_price": round(sum(prices) / len(prices), 2) if prices else 0,
        }

    @celery_app.task(
        bind=True,
        name="02_celery_advanced_patterns.process_payment_task",
        queue="high_priority",
        acks_late=True,
        soft_time_limit=55,
        time_limit=60,
    )
    def process_payment_task(self, order_id: str, amount: float) -> Dict:
        """Process payment — critical task on high_priority queue."""
        try:
            logger.info(f"Processing payment for order {order_id}, amount={amount}")
            time.sleep(0.1)  # Simulate payment gateway call
            return {"order_id": order_id, "amount": amount, "status": "charged"}
        except SoftTimeLimitExceeded:
            logger.error(f"Payment timeout for order {order_id}")
            raise

    @celery_app.task(
        name="02_celery_advanced_patterns.send_email_task",
        queue="email",
    )
    def send_email_task(recipient: str, subject: str, body: str) -> Dict:
        """Send email — routed to email queue."""
        time.sleep(0.05)
        return {"recipient": recipient, "sent": True}

    @celery_app.task(
        name="02_celery_advanced_patterns.track_event",
        queue="analytics",
    )
    def track_event(event_name: str, properties: Dict) -> Dict:
        """Track analytics event — low priority queue."""
        return {"event": event_name, "tracked": True}

    @celery_app.task(
        bind=True,
        name="02_celery_advanced_patterns.import_data_task",
        queue="default",
        acks_late=True,
        soft_time_limit=280,
        time_limit=300,
    )
    def import_data_task(self, file_path: str, total_rows: int) -> Dict:
        """Long-running import with progress tracking."""
        try:
            for i in range(total_rows):
                time.sleep(0.01)
                if i % (total_rows // 10) == 0:
                    self.update_state(
                        state="PROGRESS",
                        meta={
                            "percent": i * 100 // total_rows,
                            "current": i,
                            "total": total_rows,
                            "message": f"Importing row {i}/{total_rows}",
                        },
                    )
            return {"imported": total_rows, "status": "complete"}
        except SoftTimeLimitExceeded:
            logger.warning("Import task soft limit — saving progress ...")
            raise

    def run_real_celery_demo():
        """Execute real Celery workflows when Redis is available."""
        print("\n" + "=" * 60)
        print("REAL CELERY MODE (Redis connected)")
        print("=" * 60)

        # 1. Chain
        print("\n[1] Submitting chain workflow ...")
        result = (
            fetch_page.s(1)
            | aggregate_pages.s()
        ).apply_async()
        print(f"    Chain task ID: {result.id}")

        # 2. Group (parallel page fetches)
        print("\n[2] Submitting group (10 parallel page fetches) ...")
        g = group(fetch_page.s(i) for i in range(1, 11))
        group_result = g.apply_async()
        print(f"    Group ID: {group_result.id}")

        # 3. Chord (parallel → aggregate)
        print("\n[3] Submitting chord (parallel fetch → aggregate) ...")
        c = chord(
            group(fetch_page.s(i) for i in range(1, 6))
        )(aggregate_pages.s())
        print(f"    Chord callback ID: {c.id}")

        # 4. Priority routing
        print("\n[4] Submitting tasks to different queues ...")
        process_payment_task.apply_async(
            args=["ORD-001", 1499.0], queue="high_priority", priority=9
        )
        send_email_task.apply_async(
            args=["user@example.com", "Welcome!", "Hello!"], queue="email"
        )
        track_event.apply_async(
            args=["page_view", {"page": "/home"}], queue="analytics", priority=1
        )
        print("    Tasks submitted to high_priority, email, analytics queues.")

        print("""
    ┌─ Check Results ─────────────────────────────────────────────┐
    │                                                             │
    │  from celery.result import AsyncResult                     │
    │                                                             │
    │  r = AsyncResult("TASK-ID-HERE")                           │
    │  print(r.state)    # PENDING, STARTED, SUCCESS, FAILURE    │
    │  print(r.result)   # Return value (if SUCCESS)             │
    │  print(r.get(timeout=30))  # Block until done              │
    │                                                             │
    │  # Flower UI: http://localhost:5555                        │
    │  # celery -A 02_celery_advanced_patterns flower            │
    └─────────────────────────────────────────────────────────────┘
""")


# =============================================================================
# SECTION 9: PRODUCTION CONFIGURATION SUMMARY
# =============================================================================

def show_production_config() -> None:
    """Print the canonical production Celery configuration."""
    print("\n" + "=" * 60)
    print("SECTION 9: Production Configuration Cheatsheet")
    print("=" * 60)

    config = """
  # ── celeryconfig.py — Production Ready ───────────────────────

  # Broker and Backend
  CELERY_BROKER_URL = 'redis://redis:6379/0'
  CELERY_RESULT_BACKEND = 'redis://redis:6379/1'  # Separate DB for results

  # Serialization (NEVER use pickle in prod!)
  CELERY_TASK_SERIALIZER = 'json'
  CELERY_RESULT_SERIALIZER = 'json'
  CELERY_ACCEPT_CONTENT = ['json']

  # Reliability
  CELERY_TASK_ACKS_LATE = True               # Ack after completion, not receive
  CELERY_WORKER_PREFETCH_MULTIPLIER = 1      # Fair distribution (no hoarding)
  CELERY_TASK_REJECT_ON_WORKER_LOST = True   # Re-queue on worker crash

  # Task limits
  CELERY_TASK_SOFT_TIME_LIMIT = 300          # 5 min default soft limit
  CELERY_TASK_TIME_LIMIT = 360               # 6 min hard limit
  CELERY_TASK_MAX_RETRIES = 3

  # Result management
  CELERY_RESULT_EXPIRES = 3600               # Clean up results after 1 hour

  # Connection
  CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True
  CELERY_BROKER_CONNECTION_MAX_RETRIES = 10

  # Monitoring
  CELERY_TASK_TRACK_STARTED = True           # Enable STARTED state

  # Timezone (important for beat)
  CELERY_TIMEZONE = 'Asia/Kolkata'
  CELERY_ENABLE_UTC = True

  # ── Why each setting? ─────────────────────────────────────────
  #
  # acks_late=True:
  #   Without: task acked on receive → worker crash = task LOST
  #   With:    task acked on success → worker crash = task RE-QUEUED
  #   Trade-off: tasks must be IDEMPOTENT (safe to run twice)
  #
  # prefetch_multiplier=1:
  #   Without: worker hoards 4 tasks → load imbalance
  #   With:    take 1, finish it, take next → fair distribution
  #
  # reject_on_worker_lost=True:
  #   Without: unacked task stays in "unacked" state forever
  #   With:    task re-queued for another worker → no lost work
  #
  # task_track_started=True:
  #   Without: state jumps PENDING → SUCCESS (no STARTED)
  #   With:    can tell if task is actually running vs just queued
"""
    print(config)


# =============================================================================
# MAIN — Demo Runner
# =============================================================================

DEMO_MAP = {
    "chain": ("Chain — Sequential Pipeline", simulate_chain),
    "group": ("Group — Parallel Execution", simulate_group),
    "chord": ("Chord — Map-Reduce", simulate_chord),
    "retry": ("Retry — Exponential Backoff", simulate_retry_backoff),
    "beat": ("Beat — Periodic Tasks", simulate_beat_schedule),
    "monitor": ("Monitor — Progress Tracking", simulate_progress_tracking),
    "priority": ("Priority — Queue Routing", simulate_priority_and_routing),
    "timelimit": ("Time Limits — Soft vs Hard", simulate_time_limits),
    "config": ("Production Configuration", show_production_config),
}


def print_banner() -> None:
    print("""
╔══════════════════════════════════════════════════════════════╗
║   Celery Advanced Patterns — Interview Prep (40 LPA)        ║
║   Phase 2 | 02_celery_advanced_patterns.py                  ║
╠══════════════════════════════════════════════════════════════╣
║  Mode: {}                                      ║
╚══════════════════════════════════════════════════════════════╝
""".format("REAL CELERY (Redis)" if REDIS_AVAILABLE else "DEMO (Pure Python — no broker needed)"))


def main() -> None:
    print_banner()

    args = sys.argv[1:]

    if REDIS_AVAILABLE and celery_app:
        # Real Celery mode — just define tasks (worker picks them up)
        if "demo" in args or not args:
            # Still run demos alongside real Celery
            pass
        if "realcell" in args:
            run_real_celery_demo()
            return

    if not args or "all" in args:
        sections = list(DEMO_MAP.keys())
    else:
        sections = [a for a in args if a in DEMO_MAP]
        if not sections:
            print(f"Unknown section(s): {args}")
            print(f"Available: {', '.join(DEMO_MAP.keys())}, all")
            sys.exit(1)

    for section_key in sections:
        title, fn = DEMO_MAP[section_key]
        fn()

    print("\n" + "=" * 60)
    print("All demos complete.")
    if not REDIS_AVAILABLE:
        print("\nTo run with real Celery + Redis:")
        print("  export REDIS_URL=redis://localhost:6379/0")
        print("  celery -A 02_celery_advanced_patterns worker -l info \\")
        print("         -Q default,high_priority,email,analytics")
        print("  celery -A 02_celery_advanced_patterns beat -l info")
        print("  celery -A 02_celery_advanced_patterns flower --port=5555")
    print("=" * 60)


if __name__ == "__main__":
    main()
