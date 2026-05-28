"""
============================================================
LONG-RUNNING TASKS + CANCELLATION — Practical
============================================================
Patterns:
1. revoke() basic
2. Soft/hard time limits
3. Cooperative cancellation flag
4. Progress reporting + resume
5. acks_late for crash resilience
6. SIGTERM graceful shutdown
"""


# ============================================================
# 1. BASIC REVOKE PATTERNS
# ============================================================
BASIC_REVOKE = '''
from celery.result import AsyncResult
from celery import Celery

app = Celery("myapp")

@app.task
def my_task(x):
    return x * 2

# Submit
result = my_task.delay(42)
print(result.id)

# REVOKE — works only if task hasn't started
result.revoke()

# Force terminate running task (USE CAREFULLY in prefork pool!)
result.revoke(terminate=True, signal="SIGTERM")

# Revoke + don't reach worker if queued
result.revoke()    # task_id added to revoked list
# Worker checks list before each task; if revoked, skips

# Limitations:
# - revoke requires broker that supports remote control (NOT SQS)
# - terminate=True can kill sibling tasks in prefork pool
# - Doesn't work if worker offline
'''


# ============================================================
# 2. TIME LIMITS
# ============================================================
TIME_LIMITS = '''
from celery.exceptions import SoftTimeLimitExceeded
from celery import shared_task

# SOFT + HARD limits
@shared_task(
    soft_time_limit=300,    # 5 min — SIGUSR1, task can clean up
    time_limit=360,          # 6 min — SIGTERM, killed
)
def long_task():
    try:
        for i in range(10000):
            process_chunk(i)
    except SoftTimeLimitExceeded:
        # 5 min mark hit — graceful cleanup
        save_partial_state()
        raise   # re-raise so task is marked as failed

# Global defaults
app.conf.update(
    task_soft_time_limit=300,
    task_time_limit=600,
)

# Override per task or per call
my_task.apply_async(args=[1], time_limit=1200, soft_time_limit=1080)
'''


# ============================================================
# 3. COOPERATIVE CANCELLATION (recommended)
# ============================================================
COOPERATIVE_CANCEL = '''
import redis
from celery import shared_task

r = redis.Redis()

def is_cancelled(task_id: str) -> bool:
    return bool(r.get(f"cancel:{task_id}"))

def cancel_task(task_id: str):
    r.set(f"cancel:{task_id}", "1", ex=3600)


@shared_task(bind=True)
def encode_video(self, video_id):
    chunks = list(get_chunks(video_id))
    completed = 0

    for i, chunk in enumerate(chunks):
        # CHECK CANCELLATION
        if is_cancelled(self.request.id):
            cleanup_partial(video_id)
            return {
                "status": "cancelled",
                "completed_chunks": completed,
                "total_chunks": len(chunks),
            }

        encode_chunk(chunk)
        completed += 1

        # Update progress for client polling
        self.update_state(
            state="PROGRESS",
            meta={"current": completed, "total": len(chunks)}
        )

    return {"status": "completed", "video_id": video_id}


# FastAPI endpoint to cancel
@app.post("/api/tasks/{task_id}/cancel")
async def cancel_endpoint(task_id: str):
    # 1. Mark cancellation flag (running tasks pick this up)
    cancel_task(task_id)

    # 2. Also revoke from queue (for not-yet-started)
    from celery.result import AsyncResult
    AsyncResult(task_id).revoke()

    return {"cancelled": task_id}


# Polling progress from API
@app.get("/api/tasks/{task_id}")
async def get_progress(task_id: str):
    result = AsyncResult(task_id)
    if result.state == "PROGRESS":
        return result.info       # {"current": 50, "total": 100}
    if result.state == "SUCCESS":
        return {"result": result.result}
    return {"state": result.state}
'''


# ============================================================
# 4. PROGRESS PERSISTENCE + RESUME
# ============================================================
RESUMABLE_TASK = '''
import redis
r = redis.Redis()


@shared_task(bind=True, acks_late=True)
def resumable_video_encode(self, video_id, start_chunk=0):
    """Can be cancelled and resumed from middle."""
    chunks = list(get_chunks(video_id))

    # Read persisted progress
    progress_key = f"progress:{video_id}"
    actual_start = max(start_chunk, int(r.get(progress_key) or 0))

    print(f"Starting from chunk {actual_start}/{len(chunks)}")

    for i in range(actual_start, len(chunks)):
        # Cancellation
        if is_cancelled(self.request.id):
            return {"status": "cancelled", "resume_from": i}

        # Process
        encode_chunk(chunks[i])

        # Persist progress
        r.set(progress_key, str(i + 1), ex=86400)

        self.update_state(
            state="PROGRESS",
            meta={"current": i + 1, "total": len(chunks)},
        )

    # Cleanup progress marker
    r.delete(progress_key)
    return {"status": "completed"}


# Resume API
@app.post("/api/videos/{video_id}/resume")
async def resume_encoding(video_id: int):
    progress = int(r.get(f"progress:{video_id}") or 0)
    task = resumable_video_encode.delay(video_id, start_chunk=progress)
    return {"task_id": task.id, "resume_from": progress}
'''


# ============================================================
# 5. ACKS_LATE FOR CRASH RESILIENCE
# ============================================================
ACKS_LATE = '''
@shared_task(
    bind=True,
    acks_late=True,                    # ack only after completion
    reject_on_worker_lost=True,         # requeue if worker dies
    autoretry_for=(Exception,),
    max_retries=3,
)
def critical_task(self, data):
    """Idempotent task that survives worker crashes."""
    # IMPORTANT: Idempotency check
    job_id = data["id"]
    if already_processed(job_id):
        return get_cached_result(job_id)

    result = do_critical_work(data)
    mark_processed(job_id, result)
    return result

# Behavior:
# Normal:        broker sends → worker processes → ack → done
# With acks_late: broker sends → worker processes → success → ack
#                                              → failure → no ack → broker retries
# If worker crashes mid-execution → no ack → broker redelivers → idempotency check catches dup
'''


# ============================================================
# 6. ASYNC TASK WITH CANCELLATION
# ============================================================
ASYNC_TASK = '''
import asyncio
from celery import shared_task


@shared_task(bind=True)
def async_long_task(self):
    return asyncio.run(_impl(self.request.id))


async def _impl(task_id: str):
    chunks = await fetch_chunks()

    for i, chunk in enumerate(chunks):
        if is_cancelled(task_id):
            return {"status": "cancelled"}

        # Async I/O with timeout — important!
        try:
            await asyncio.wait_for(process_chunk(chunk), timeout=30)
        except asyncio.TimeoutError:
            print(f"Chunk {i} timed out, skipping")
            continue

    return {"status": "completed"}
'''


# ============================================================
# 7. GRACEFUL WORKER SHUTDOWN
# ============================================================
GRACEFUL_SHUTDOWN = '''
from celery.signals import worker_shutting_down, worker_shutdown
import signal
import logging

@worker_shutting_down.connect
def on_shutdown_initiated(**kwargs):
    """Called when SIGTERM received — start graceful shutdown."""
    logging.info("Worker shutdown initiated")
    # Stop accepting new tasks
    # In-flight tasks have time_limit to complete

@worker_shutdown.connect
def on_shutdown_complete(**kwargs):
    """Worker fully shut down."""
    logging.info("Worker shutdown complete")
    # Cleanup: close DB connections, flush metrics, etc.


# Run worker with shutdown grace
# celery -A myapp worker \\
#     --time-limit=3600 \\          # hard limit
#     --soft-time-limit=3300 \\     # soft (5 min before hard)
#     --worker-shutdown-timeout=300  # wait 5 min for in-flight

# Kubernetes: configure preStop + terminationGracePeriodSeconds
# preStop: send SIGTERM to celery
# terminationGracePeriod: 300 (5 min to drain)
'''


# ============================================================
# 8. PROGRESS REPORTING + WEBSOCKET PUSH
# ============================================================
PROGRESS_WEBSOCKET = '''
# Real-time progress via WebSocket (FastAPI)

from celery.signals import task_postrun

@app.websocket("/ws/task/{task_id}")
async def task_progress_ws(websocket: WebSocket, task_id: str):
    await websocket.accept()
    pubsub = redis.pubsub()
    await pubsub.subscribe(f"progress:{task_id}")

    while True:
        message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1)
        if message:
            await websocket.send_json(json.loads(message["data"]))


# Inside Celery task
@shared_task(bind=True)
def long_task_with_progress(self):
    for i in range(100):
        # Publish progress to Redis
        redis.publish(f"progress:{self.request.id}", json.dumps({
            "current": i,
            "total": 100,
            "percent": i,
        }))
        do_work(i)
'''


# ============================================================
# 9. PRODUCTION VIDEO ENCODER (all patterns combined)
# ============================================================
PRODUCTION_VIDEO_ENCODER = '''
@shared_task(
    bind=True,
    acks_late=True,                    # crash resilience
    reject_on_worker_lost=True,
    time_limit=7200,                    # 2h hard limit
    soft_time_limit=6900,               # 5min before hard
    autoretry_for=(IOError, ConnectionError),
    max_retries=3,
)
def encode_video_production(self, video_id, format_options):
    task_id = self.request.id

    # Resume from persisted progress
    progress = int(r.get(f"video_progress:{video_id}") or 0)
    chunks = get_chunks(video_id)

    try:
        for i in range(progress, len(chunks)):
            # 1. Cancellation check
            if is_cancelled(task_id):
                cleanup_partial(video_id)
                return {"status": "cancelled", "completed": i}

            # 2. Process with timeout
            try:
                encode_chunk(chunks[i], format_options, timeout=300)
            except TimeoutError:
                # Retry from this chunk
                raise self.retry(
                    kwargs={"start_chunk": i},
                    countdown=60,
                )

            # 3. Persist progress (idempotent)
            r.set(f"video_progress:{video_id}", str(i + 1), ex=86400)

            # 4. Update state
            self.update_state(
                state="PROGRESS",
                meta={"current": i + 1, "total": len(chunks)},
            )

            # 5. Publish for WebSocket clients
            r.publish(f"task_progress:{task_id}", json.dumps({
                "current": i + 1, "total": len(chunks),
            }))

        # Finalize
        merge_chunks(video_id)
        r.delete(f"video_progress:{video_id}")
        return {"status": "completed", "video_id": video_id}

    except SoftTimeLimitExceeded:
        # 5 min before hard limit — save state
        save_partial(video_id)
        raise

    except Exception as e:
        # Cleanup partial on unrecoverable error
        save_partial(video_id)
        raise
'''


# ============================================================
# 10. CHECKLIST FOR LONG-RUNNING TASKS
# ============================================================
CHECKLIST = """
================================================================
LONG-RUNNING TASK PRODUCTION CHECKLIST
================================================================

✅ Cancellation check at each iteration
✅ Progress persistence (Redis) — resumable
✅ update_state(PROGRESS, meta={}) for client polling
✅ acks_late=True for crash resilience
✅ Idempotency check (avoid double-processing)
✅ Soft + hard time limits (graceful + safety net)
✅ Timeout on external calls (HTTP, DB)
✅ Cleanup on exception (try/finally)
✅ Chunked processing (natural cancellation points)
✅ Avoid terminate=True (risky in prefork)
✅ Distributed lock if shared resource
✅ SIGTERM handler for graceful shutdown
✅ Monitoring: task duration p99, cancellation rate
✅ Documented runbook for stuck tasks
================================================================
"""


# ============================================================
# MAIN
# ============================================================
if __name__ == "__main__":
    print("=" * 60)
    print("LONG-RUNNING TASKS + CANCELLATION — Practical")
    print("=" * 60)

    print("\n--- 1. BASIC REVOKE ---")
    print(BASIC_REVOKE)
    print("\n--- 2. TIME LIMITS ---")
    print(TIME_LIMITS)
    print("\n--- 3. COOPERATIVE CANCEL (RECOMMENDED) ---")
    print(COOPERATIVE_CANCEL)
    print("\n--- 4. RESUMABLE TASK ---")
    print(RESUMABLE_TASK)
    print("\n--- 5. ACKS_LATE FOR CRASH RESILIENCE ---")
    print(ACKS_LATE)
    print("\n--- 6. ASYNC TASK ---")
    print(ASYNC_TASK)
    print("\n--- 7. GRACEFUL SHUTDOWN ---")
    print(GRACEFUL_SHUTDOWN)
    print("\n--- 8. WEBSOCKET PROGRESS ---")
    print(PROGRESS_WEBSOCKET)
    print("\n--- 9. PRODUCTION VIDEO ENCODER ---")
    print(PRODUCTION_VIDEO_ENCODER)
    print(CHECKLIST)
