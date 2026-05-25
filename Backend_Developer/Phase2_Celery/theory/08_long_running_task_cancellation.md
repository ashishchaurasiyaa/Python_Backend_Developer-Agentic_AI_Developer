# Long-Running Tasks + Cancellation

> **Interview angle:** "1 hour ka video encoding task — user 'cancel' button daba diya. Worker kya kare? Process kill? Resources leak hone wala."

---

## 1. Why Cancellation is Hard

Celery isn't designed for long-running tasks. By default:
- Worker holds task → can't yield
- `revoke()` doesn't always work
- Kill -9 = work lost + resources leaked
- Result: orphaned files, half-uploaded data, stuck transactions

---

## 2. Four Cancellation Strategies

### Strategy 1: `revoke()` — works for queued tasks only
### Strategy 2: Soft Time Limit — task receives signal
### Strategy 3: Hard Time Limit — worker killed
### Strategy 4: Cooperative Cancellation — task checks flag

---

## 3. Strategy 1: `revoke()`

### Cancel queued task (not yet started)
```python
from celery.result import AsyncResult

result = my_task.delay(arg)
print(result.id)

# Cancel — works IF task hasn't been picked up yet
result.revoke()
```

### Force terminate running task
```python
result.revoke(terminate=True, signal="SIGTERM")
# Sends signal to worker process
# - SIGTERM: graceful (worker can clean up)
# - SIGKILL: immediate kill (resource leaks!)
```

### Limitations
- `revoke()` requires broker that supports remote control (NOT SQS)
- `terminate=True` may kill **other tasks** on same worker (prefork pool)
- Worker may finish current task before checking revoke list

---

## 4. Strategy 2: Soft Time Limit (gentle timeout)

```python
@app.task(soft_time_limit=300, time_limit=360)
def long_task():
    try:
        do_work()
    except SoftTimeLimitExceeded:
        # Task got 300s warning — clean up gracefully
        cleanup_partial_work()
        raise
```

- `soft_time_limit=300` → after 300s, raises `SoftTimeLimitExceeded` inside task
- `time_limit=360` → hard kill at 360s if task didn't honor soft
- Soft signal = `SIGUSR1` on Unix
- Doesn't work on Windows

### Global defaults
```python
app.conf.task_soft_time_limit = 300
app.conf.task_time_limit = 360
```

---

## 5. Strategy 3: Hard Time Limit

```python
@app.task(time_limit=600)
def task():
    # Killed via SIGTERM after 600s, no chance to cleanup
    pass
```

- Use as safety net
- Combine with soft limit for graceful path

---

## 6. Strategy 4: Cooperative Cancellation (Recommended)

Task periodically checks a flag. If set, exits gracefully.

```python
import redis

r = redis.Redis()

def is_cancelled(task_id):
    return bool(r.get(f"cancel:{task_id}"))

def cancel(task_id):
    r.set(f"cancel:{task_id}", "1", ex=3600)


@app.task(bind=True)
def encode_video(self, video_id):
    chunks = get_chunks(video_id)
    for i, chunk in enumerate(chunks):
        if is_cancelled(self.request.id):
            cleanup_partial(video_id)
            return {"status": "cancelled", "progress": i / len(chunks)}

        encode_chunk(chunk)
        self.update_state(state="PROGRESS", meta={"current": i, "total": len(chunks)})

    return {"status": "completed"}


# API endpoint
@app.post("/api/tasks/{task_id}/cancel")
async def cancel_task(task_id: str):
    cancel(task_id)
    return {"cancelled": task_id}
```

### Pros
- Works with any broker (including SQS)
- Clean shutdown (resources released)
- Can save partial progress

### Cons
- Each task must implement check
- Polling overhead (~1ms per check)

---

## 7. Async Tasks with Cancellation

```python
import asyncio

@app.task(bind=True)
def async_work(self):
    return asyncio.run(_async_impl(self.request.id))

async def _async_impl(task_id):
    chunks = get_chunks()
    for i, chunk in enumerate(chunks):
        # Check at each iteration
        if is_cancelled(task_id):
            return {"status": "cancelled"}

        # Async I/O with timeout
        try:
            await asyncio.wait_for(process_chunk(chunk), timeout=10)
        except asyncio.TimeoutError:
            continue
```

---

## 8. Progress Updates (UX during long tasks)

```python
@app.task(bind=True)
def slow_task(self):
    total = 100
    for i in range(total):
        do_step(i)
        self.update_state(
            state="PROGRESS",
            meta={"current": i, "total": total, "percent": i/total*100},
        )
    return "done"

# Client polls progress
result = AsyncResult(task_id)
while not result.ready():
    info = result.info     # {"current": 50, "total": 100, ...}
    await asyncio.sleep(1)
```

For real-time push: WebSocket or SSE relayed via Redis.

---

## 9. Handling Worker Crashes Mid-Task

```python
@app.task(
    bind=True,
    acks_late=True,                    # ack only after task done
    reject_on_worker_lost=True,         # requeue if worker dies
)
def critical_task(self, data):
    do_work(data)
```

### `acks_late=True`
- Default: task ack'd to broker BEFORE execution starts
- If worker crashes → task LOST
- With `acks_late=True`: ack only after success → broker redelivers on crash

### `reject_on_worker_lost=True`
- If worker connection lost, message rejected (not ack'd)
- Broker requeues

⚠️ **Side effect:** Idempotency MUST be guaranteed. Task may run twice.

---

## 10. Chunking + Resumable Tasks

For very long tasks, break into resumable chunks.

```python
@app.task(bind=True)
def encode_video_chunked(self, video_id, start_chunk=0):
    """Resumable — can restart from middle."""
    chunks = get_chunks(video_id)
    for i in range(start_chunk, len(chunks)):
        if is_cancelled(self.request.id):
            return {"status": "cancelled", "resume_from": i}

        try:
            encode_chunk(chunks[i])
        except Exception as e:
            # Schedule restart from this chunk
            encode_video_chunked.apply_async(
                args=[video_id],
                kwargs={"start_chunk": i},
                countdown=60,
            )
            raise

        # Persist progress
        r.set(f"progress:{self.request.id}", str(i), ex=86400)

    return {"status": "completed"}
```

---

## 11. Distributed Lock + Cancellation

For tasks holding shared resources:

```python
import redis

r = redis.Redis()

@app.task(bind=True)
def update_resource(self, resource_id):
    lock_key = f"lock:resource:{resource_id}"
    lock_id = self.request.id

    if not r.set(lock_key, lock_id, nx=True, ex=600):
        return {"error": "resource busy"}

    try:
        for i in range(100):
            if is_cancelled(self.request.id):
                return {"status": "cancelled"}
            do_work(i)
    finally:
        # Release lock only if WE own it
        lua = """
        if redis.call("GET", KEYS[1]) == ARGV[1] then
            return redis.call("DEL", KEYS[1])
        end
        """
        r.eval(lua, 1, lock_key, lock_id)
```

---

## 12. SIGTERM Handling (graceful shutdown)

When worker receives SIGTERM (k8s eviction, deploy):

```python
from celery.signals import worker_shutdown
import signal

@worker_shutdown.connect
def on_shutdown(**kwargs):
    """Worker is shutting down — graceful cleanup."""
    # Mark all in-flight tasks as needing resumption
    for task in inspect.active():
        mark_for_retry(task["id"])
```

### Configure shutdown grace
```bash
celery -A myapp worker --time-limit=3600 --soft-time-limit=3300

# Or
worker_shutdown_timeout = 300   # 5 min to finish current tasks
```

---

## 13. Real-World Pattern: Video Encoder

```python
@app.task(bind=True, acks_late=True, time_limit=7200)
def encode_video(self, video_id, format_options):
    """Long-running with all cancellation patterns."""
    task_id = self.request.id

    # Resume support
    progress = int(r.get(f"progress:{task_id}") or 0)
    chunks = get_chunks(video_id)

    try:
        for i in range(progress, len(chunks)):
            # Cancellation check
            if is_cancelled(task_id):
                cleanup_partial(video_id, completed_chunks=i)
                return {"status": "cancelled", "completed": i}

            # Process with timeout
            try:
                encode_chunk(chunks[i], format_options, timeout=300)
            except TimeoutError:
                # Skip this chunk? Retry whole task?
                raise self.retry(countdown=60, kwargs={"start_chunk": i})

            # Persist progress
            r.set(f"progress:{task_id}", str(i + 1), ex=86400)

            # Update state for client polling
            self.update_state(state="PROGRESS",
                              meta={"current": i + 1, "total": len(chunks)})

        # Finalize
        merge_chunks(video_id)
        return {"status": "completed", "video_id": video_id}

    except SoftTimeLimitExceeded:
        # Got SIGUSR1 — clean shutdown
        save_partial(video_id, progress)
        raise

    except Exception:
        # Will be retried by acks_late + reject_on_worker_lost
        save_partial(video_id, progress)
        raise


@app.post("/api/videos/{video_id}/cancel/{task_id}")
async def cancel_encoding(task_id: str):
    cancel(task_id)
    # Also revoke from queue if not started yet
    AsyncResult(task_id).revoke()
    return {"cancelled": task_id}
```

---

## 14. Common Pitfalls

### Pitfall 1: Using `revoke(terminate=True)` carelessly
Kills entire worker process in prefork pool → all sibling tasks die too.

### Pitfall 2: No idempotency with `acks_late`
Worker dies → task re-runs → side effects executed twice (double charges, double emails).

### Pitfall 3: No progress persistence
Crash mid-way → restart from zero. Always persist progress.

### Pitfall 4: Cancellation check too infrequent
User clicks cancel → task takes 30 more seconds because check is at end of each big step.

### Pitfall 5: No timeout on external calls
HTTP call hangs → task hangs → no cancellation possible. Always wrap in `asyncio.wait_for` or `requests timeout=`.

---

## 15. Interview Questions

**Q1: Long task cancel kaise?**
1. `revoke()` for queued
2. `revoke(terminate=True)` for running (risky)
3. **Cooperative pattern**: task checks Redis flag periodically

**Q2: Soft vs hard time limit?**
Soft = SIGUSR1 to task → exception → cleanup chance. Hard = SIGTERM → kill.

**Q3: Worker crash mid-task?**
`acks_late=True` + `reject_on_worker_lost=True` → broker redelivers. Idempotency required.

**Q4: How to track progress?**
`self.update_state(state="PROGRESS", meta={...})` + client polls AsyncResult. Or push via WebSocket.

**Q5: Resumable tasks?**
Persist progress in Redis. Task reads progress on start, resumes from there.

**Q6: terminate=True risk?**
Prefork pool: kills whole process → sibling tasks die. Use cooperative cancellation instead.

**Q7: SQS doesn't support revoke?**
Right. Use cooperative cancellation (flag check) only.

---

## 16. Best Practices

1. **Cooperative cancellation pattern** — flag check in loop
2. **Persist progress** — Redis with TTL
3. **Soft + hard time limits** — soft for graceful, hard as safety net
4. **acks_late + idempotency** — survive worker crashes
5. **Chunk long tasks** — natural cancellation points
6. **`update_state`** for client visibility
7. **Timeout on external calls**
8. **SIGTERM handler** for graceful worker shutdown
9. **Avoid `terminate=True`** in prefork pool
10. **Test cancellation in load tests**

---

## Related
- [[02_celery_advanced]]
- [[03_celery_advanced_patterns]]
- [[09_celery_canvas_workflows]]
