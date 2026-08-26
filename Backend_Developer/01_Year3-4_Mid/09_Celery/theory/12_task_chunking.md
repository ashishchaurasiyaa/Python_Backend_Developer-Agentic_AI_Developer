# Task Chunking — Processing Large Datasets with Celery

## 1. The Problem

```
Task: "Process 1 million user records for monthly report"

Naive approach (ONE task):
@app.task
def generate_report():
    users = User.objects.all()   # ← loads 1M objects into RAM
    for user in users:           # ← sequential, single worker
        process(user)
    # Runtime: hours. Memory: GBs. No parallelism.
```

Problems:
- Single worker → no parallelism
- All records in memory → OOM
- Task timeout (soft/hard limit) kills long-running task
- No progress visibility
- Retry reruns EVERYTHING from scratch

---

## 2. Chunking — Core Concept

Break the dataset into small batches. Each batch is an independent task. Process all batches in parallel.

```
1M records
    ↓
Split into 1000 batches × 1000 records
    ↓
1000 tasks → dispatched to workers
    ↓
10 workers → 100 batches each → parallel
    ↓
~10× faster than sequential
```

---

## 3. Basic Chunking — Python Level

```python
from celery import group

def chunk(iterable, size):
    """Split list into fixed-size chunks."""
    it = list(iterable)
    for i in range(0, len(it), size):
        yield it[i:i + size]


@app.task
def process_batch(record_ids: list) -> dict:
    """Process one batch of records."""
    results = []
    for rid in record_ids:
        user = User.objects.get(pk=rid)
        results.append(compute(user))
    return {"count": len(results), "success": len(results)}


def dispatch_chunked_report():
    record_ids = list(User.objects.values_list("id", flat=True))  # only IDs, not objects

    batches = list(chunk(record_ids, size=500))       # 1M → 2000 batches of 500
    job     = group(process_batch.s(batch) for batch in batches)
    result  = job.apply_async()
    return result
```

**Key rule:** Pass IDs to tasks, NOT ORM objects. Workers fetch fresh from DB.

---

## 4. Django ORM — Memory-Efficient Querying

```python
# ❌ WRONG: loads all 1M objects into RAM
users = User.objects.all()

# ✅ CORRECT: iterator() fetches in server-side cursor (no full load)
for user in User.objects.iterator(chunk_size=500):
    ...

# ✅ CORRECT: only fetch IDs (minimal memory)
id_list = User.objects.values_list("id", flat=True)

# ✅ CORRECT: pagination for very large tables
def get_record_ids_in_pages(page_size=1000):
    last_id = 0
    while True:
        ids = list(
            User.objects.filter(pk__gt=last_id).order_by("pk").values_list("pk", flat=True)[:page_size]
        )
        if not ids:
            break
        yield ids
        last_id = ids[-1]
```

---

## 5. Celery `chunks()` Method

Celery has a built-in `chunks()` that auto-splits a list of args.

```python
@app.task
def process_single(record_id: int) -> dict:
    user = User.objects.get(pk=record_id)
    return compute(user)

# chunks(args_list, n) → group of tasks, each with n items
record_ids = list(User.objects.values_list("id", flat=True))
job = process_single.chunks([(rid,) for rid in record_ids], n=500).group()
result = job.apply_async()
```

**Note:** `chunks()` creates individual tasks (one per item inside each chunk). `group()` creates tasks per chunk. For DB operations, prefer explicit batch tasks (fewer DB round trips).

---

## 6. chord() — Parallel + Automatic Aggregation

```
group() alone: parallel processing, results collected manually
chord()      : parallel processing + callback runs when ALL complete

chord(
    group(process_batch.s(batch) for batch in batches),  ← header (parallel)
    aggregate_results.s()                                 ← callback (runs after all)
)
```

```python
from celery import chord, group

@app.task
def process_batch(record_ids: list) -> dict:
    processed = [compute(rid) for rid in record_ids]
    return {"count": len(processed), "total": sum(processed)}

@app.task
def aggregate_results(batch_results: list) -> dict:
    """Called ONCE when all batches complete. Receives list of all batch results."""
    total_count = sum(r["count"] for r in batch_results)
    grand_total = sum(r["total"] for r in batch_results)
    return {"total_records": total_count, "grand_total": grand_total}


def dispatch_with_aggregation(record_ids: list, batch_size: int = 500) -> dict:
    batches  = [record_ids[i:i+batch_size] for i in range(0, len(record_ids), batch_size)]
    header   = group(process_batch.s(batch) for batch in batches)
    callback = aggregate_results.s()

    # chord returns an AsyncResult that resolves to callback's return value
    final_result = chord(header)(callback)
    return final_result.get(timeout=3600)   # wait max 1 hour
```

---

## 7. Chunking with Progress Tracking

```python
from celery import shared_task
import redis

r = redis.Redis()

@shared_task
def process_batch_with_progress(record_ids: list, job_id: str) -> dict:
    results = [compute(rid) for rid in record_ids]
    # Update progress in Redis
    r.incr(f"job:{job_id}:completed_batches")
    total = r.get(f"job:{job_id}:total_batches")
    done  = r.get(f"job:{job_id}:completed_batches")
    r.set(f"job:{job_id}:progress", f"{done}/{total}")
    return {"count": len(results)}


def dispatch_with_progress(record_ids: list, batch_size: int = 500) -> str:
    import uuid
    job_id  = str(uuid.uuid4())
    batches = [record_ids[i:i+batch_size] for i in range(0, len(record_ids), batch_size)]

    r.set(f"job:{job_id}:total_batches", len(batches))
    r.set(f"job:{job_id}:completed_batches", 0)
    r.expire(f"job:{job_id}:progress", 3600)

    group(process_batch_with_progress.s(batch, job_id) for batch in batches).apply_async()
    return job_id

# API endpoint to check progress:
# r.get(f"job:{job_id}:progress")  → b"45/100"
```

---

## 8. Memory Management Guidelines

```python
# Rule 1: Never pass ORM objects in task args
# ❌ BAD
@app.task
def process_user(user: User):       # User object not JSON-serializable + stale data
    ...

# ✅ GOOD
@app.task
def process_user(user_id: int):
    user = User.objects.get(pk=user_id)  # fresh fetch
    ...


# Rule 2: Batches should be IDs or simple dicts, not large payloads
# ❌ BAD: sends full serialized data through broker
@app.task
def process_batch(records: list):   # each record is a 5KB dict × 1000 = 5MB per task
    ...

# ✅ GOOD: send IDs only
@app.task
def process_batch(record_ids: list[int]):
    records = MyModel.objects.filter(pk__in=record_ids)
    ...


# Rule 3: Set max task size in config
app.conf.task_max_soft_time_limit = 3600   # 1 hour soft
app.conf.task_time_limit          = 3900   # 1 hour + 5 min hard
```

---

## 9. When to Use Which Pattern

| Scenario | Pattern |
|----------|---------|
| 10K records, no aggregation needed | `group()` |
| 10K records, need grand total | `chord()` |
| 1M records, unknown size | Generator + keyset pagination |
| Progress tracking needed | Custom Redis counter per batch |
| Each record independent | `chunks()` convenience method |
| Map-reduce workflow | `chord()` with complex callback |

---

## 10. Interview Questions

**Q: 1M records process karne hain. Sequential task se kya problem hai?**
Single worker, no parallelism. Memory explosion if all loaded at once. Task timeout. Retry reruns everything. Fix: chunk into 500-record batches, group() se parallel dispatch.

**Q: group() aur chord() mein kya fark hai?**
`group()`: parallel tasks, results manually collected via `GroupResult.get()`. `chord()`: parallel tasks (header) + callback (runs once when ALL complete) — built-in map-reduce.

**Q: Task mein ORM object kyun pass nahi karna chahiye?**
JSON-serializable nahi, pickle required (security risk). Worker pe stale data mil sakta hai (serialized at dispatch time, not at execution time). Sirf ID pass karo — worker fresh fetch karta hai.

**Q: Agar chord() ka ek batch fail ho jaaye to kya hota hai?**
Callback trigger nahi hota (by default). `chord_error_from_serialized_exception` ya custom error handler set karo. Partial results lost. Fix: batches ko retryable banao, dead-letter queue for persistent failures.
