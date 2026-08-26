"""
Celery Labs — shared app + tasks
=================================
Saare labs isi app ko use karte hain. Worker alag terminal me chalao:

    celery -A tasks worker --loglevel=info --concurrency=2

Queues wale lab (03) ke liye:
    celery -A tasks worker -Q high,default --loglevel=info

Prereq: docker compose up -d   |   pip install "celery[redis]"
"""

import time
import random
from celery import Celery

app = Celery(
    "labs",
    broker="redis://localhost:6379/0",
    backend="redis://localhost:6379/1",
)

app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="Asia/Kolkata",
    # Lab 04 me isse khelenge — abhi default (worker prefetch)
    worker_prefetch_multiplier=4,
    task_acks_late=False,
    task_default_queue="default",
    task_routes={
        "tasks.urgent_task": {"queue": "high"},
    },
)


# ══════════════════════════════════════════
# Lab 01 — basics
# ══════════════════════════════════════════
@app.task
def add(x: int, y: int) -> int:
    time.sleep(0.5)                      # thoda kaam simulate
    return x + y


@app.task
def slow_task(seconds: float) -> str:
    time.sleep(seconds)
    return f"slept {seconds}s"


# ══════════════════════════════════════════
# Lab 02 — retries
# ══════════════════════════════════════════
@app.task(bind=True, max_retries=3, default_retry_delay=1)
def flaky_api_call(self, fail_times: int = 2) -> str:
    """
    Pehle `fail_times` attempts fail honge, phir succeed.
    self.request.retries = ab tak kitne retries ho chuke.
    """
    if self.request.retries < fail_times:
        print(f"  attempt {self.request.retries + 1} → failing")
        # Lab 02 me TODO: yahan retry trigger karna hai
        raise ConnectionError("upstream 503")
    return f"succeeded after {self.request.retries} retries"


@app.task(
    bind=True,
    autoretry_for=(ConnectionError,),
    retry_backoff=True,                  # 1s, 2s, 4s...
    retry_jitter=True,                   # thundering herd se bachao
    max_retries=4,
)
def auto_retry_task(self, fail_times: int = 2) -> str:
    """Same cheez, par declarative — production me yeh form prefer karo."""
    if self.request.retries < fail_times:
        raise ConnectionError("upstream 503")
    return f"succeeded after {self.request.retries} retries"


# ══════════════════════════════════════════
# Lab 03 — routing / priority queues
# ══════════════════════════════════════════
@app.task
def urgent_task(order_id: str) -> str:
    time.sleep(0.2)
    return f"URGENT handled {order_id}"


@app.task
def bulk_task(batch_id: int) -> str:
    time.sleep(1.0)
    return f"bulk {batch_id} done"


# ══════════════════════════════════════════
# Lab 04 — canvas workflows
# ══════════════════════════════════════════
@app.task
def fetch_price(item: str) -> float:
    time.sleep(random.uniform(0.2, 0.6))
    return round(random.uniform(100, 500), 2)


@app.task
def apply_tax(price: float, rate: float = 0.18) -> float:
    return round(price * (1 + rate), 2)


@app.task
def summarize(prices: list) -> dict:
    return {"count": len(prices), "total": round(sum(prices), 2)}


# ══════════════════════════════════════════
# Lab 05 — idempotency
# ══════════════════════════════════════════
@app.task
def process_payment_naive(order_id: int, amount: float) -> dict:
    """NOT idempotent — har call pe naya tx_id banta hai."""
    time.sleep(0.3)
    tx_id = random.randint(10000, 99999)
    return {"order_id": order_id, "charged": amount, "tx_id": tx_id}


@app.task(bind=True, max_retries=5)
def process_payment_idempotent(self, order_id: int, amount: float, idempotency_key: str) -> dict:
    """
    Idempotent payment — Redis mein result cache karo.
    Same idempotency_key pe dobara call → cached result wapas.

    Lab 05 TODOs yahan hain:
      TODO A: existing result check karo (r.get)
      TODO B: result store karo with 24h TTL (r.setex)
    """
    import redis as _redis
    r = _redis.Redis(host="localhost", port=6379, db=2, decode_responses=True)
    cache_key = f"payment_idem:{idempotency_key}"

    # ── TODO A: check if already processed ────────────────────────────────
    # existing = r.get(cache_key)
    # if existing:
    #     return {"order_id": order_id, "tx_id": existing, "idempotent": True,
    #             "status": "ALREADY_PROCESSED"}
    existing = None   # ← TODO A: isse badlo
    # ──────────────────────────────────────────────────────────────────────

    if existing:
        return {"order_id": order_id, "tx_id": existing, "idempotent": True,
                "status": "ALREADY_PROCESSED"}

    time.sleep(0.3)                        # external payment API simulate
    tx_id = str(random.randint(10000, 99999))

    # ── TODO B: result store karo ─────────────────────────────────────────
    # r.setex(cache_key, 86400, tx_id)     # 24h TTL
    pass                                   # ← TODO B: isse badlo
    # ──────────────────────────────────────────────────────────────────────

    return {"order_id": order_id, "charged": amount, "tx_id": tx_id,
            "idempotent": False, "status": "CHARGED"}


# ══════════════════════════════════════════
# Lab 07 — chunking / parallel processing
# ══════════════════════════════════════════
@app.task
def process_batch(batch: list) -> dict:
    """Ek batch of record IDs ko process karo."""
    time.sleep(0.05 * len(batch))          # simulate real work
    return {
        "count": len(batch),
        "batch_sum": sum(batch),
        "min": min(batch),
        "max": max(batch),
    }


@app.task
def aggregate_results(results: list) -> dict:
    """Chord callback — saare batch results merge karo."""
    total = sum(r["batch_sum"] for r in results)
    count = sum(r["count"] for r in results)
    return {
        "total_records": count,
        "grand_sum": total,
        "batches_processed": len(results),
    }
