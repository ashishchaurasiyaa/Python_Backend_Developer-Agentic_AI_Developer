# Celery Canvas — Advanced Workflows

> **Interview angle:** "Image upload → 5 parallel resizes → after all done, generate thumbnail collage → notify user. Kaise design karoge?"

---

## 1. Canvas Primitives

Celery Canvas = composable building blocks for workflows.

| Primitive | Purpose | Example |
|---|---|---|
| **signature** | Task call template | `add.s(1, 2)` |
| **chain** | Sequential A → B → C | `chain(a.s(), b.s(), c.s())` |
| **group** | Parallel A, B, C | `group(a.s(), b.s(), c.s())` |
| **chord** | Group + callback | `chord([a, b, c], summary.s())` |
| **map** | Apply task to each element | `task.map([1,2,3])` |
| **starmap** | Map with multi-args | `task.starmap([(1,2),(3,4)])` |
| **chunks** | Batch large iterables | `task.chunks(items, 10)` |

---

## 2. `signature` — Task Call Template

```python
from celery import signature

# Create signature (delayed execution)
sig = add.s(1, 2)            # immutable args: 1+2
sig = add.signature(args=(1, 2), kwargs={}, options={"queue": "default"})

# Call later
result = sig.delay()
result = sig.apply_async()

# Partial application
sig = add.s(1)               # partial — second arg supplied later
result = sig.delay(10)        # → add(1, 10)
```

### Immutable signatures
```python
# When chained, previous result is passed as first arg by default
sig = task.s()              # mutable — accepts prev result
sig = task.si()             # immutable — ignores prev result
sig = task.s().set(immutable=True)
```

---

## 3. `chain` — Sequential Pipeline

```python
from celery import chain

# Result of A becomes first arg of B
workflow = chain(
    fetch.s("user-42"),         # fetch user-42 → {data}
    transform.s(),               # transform({data}) → cleaned
    save.s(),                    # save(cleaned) → saved_id
)
workflow.delay()

# Using | operator
workflow = fetch.s("user-42") | transform.s() | save.s()
workflow.delay()
```

### Get result
```python
result = workflow.apply_async()
final = result.get()         # value from last task in chain
```

### Failure behavior
- If A fails → B and C don't run
- Whole chain marked FAILED

---

## 4. `group` — Parallel Execution

```python
from celery import group

# Run 100 tasks in parallel
job = group(send_email.s(user_id) for user_id in range(100))
result = job.apply_async()

# Get all results
results = result.get()       # list of 100 results

# Check progress
print(result.completed_count())   # how many done
print(result.ready())               # all complete?
```

---

## 5. `chord` — Group + Callback

Run group in parallel. When ALL done, run callback with combined results.

```python
from celery import chord

# Process N items in parallel, then aggregate
workflow = chord(
    (process_chunk.s(i) for i in range(10)),    # group
    aggregate.s(),                                # callback
)
result = workflow.apply_async()
# callback receives: [chunk_0_result, chunk_1_result, ..., chunk_9_result]
```

### Important
- Chord requires **result backend** (NOT just broker)
- Order of results = order in group
- If any task in group fails, callback isn't called by default

---

## 6. Real-World Example: Image Pipeline

```python
from celery import chain, group, chord

@app.task
def upload_to_storage(image_id):
    # Upload original
    return {"image_id": image_id, "url": "..."}

@app.task
def resize(data, size):
    # Resize to specified dimensions
    return {**data, f"size_{size}": "..."}

@app.task
def generate_collage(sized_images):
    # All sizes ready — make collage
    return {"collage_url": "..."}

@app.task
def notify_user(result):
    send_notification(result)


# Pipeline:
# 1. Upload original
# 2. Parallel: resize to small, medium, large, thumbnail
# 3. After all sizes done: generate collage
# 4. Notify user
workflow = chain(
    upload_to_storage.s(image_id),
    chord(
        [
            resize.s(size=200),
            resize.s(size=500),
            resize.s(size=1000),
            resize.s(size=2000),
        ],
        generate_collage.s(),
    ),
    notify_user.s(),
)
workflow.delay()
```

---

## 7. `map` and `starmap`

```python
# Map — same arg structure
add.map([(1,2), (3,4), (5,6)])
# Actually iterates as add((1,2)) — pass tuple as first arg

# starmap — unpacks tuple as args
add.starmap([(1,2), (3,4), (5,6)])
# add(1,2), add(3,4), add(5,6)

# Difference: starmap = star-unpack
```

---

## 8. `chunks` — Batch Processing

```python
# Process 1M items in chunks of 1000
process_item.chunks(items_iterable, 1000).apply_async()
# Creates ~1000 tasks, each processes 1000 items
```

Faster than 1M individual tasks (less broker overhead).

---

## 9. Conditional Branching

Celery has no native if/else, but you can:

### Pattern: branching via task return
```python
@app.task
def check_user(user_id):
    user = get_user(user_id)
    if user.premium:
        return ("premium_path", user_id)
    return ("free_path", user_id)


@app.task
def route_decision(data):
    path, user_id = data
    if path == "premium_path":
        return premium_workflow.apply_async(args=[user_id])
    return free_workflow.apply_async(args=[user_id])


chain(check_user.s(42), route_decision.s()).delay()
```

### Pattern: callback chooses next task
```python
@app.task(bind=True)
def main_task(self, data):
    result = process(data)
    if result["needs_review"]:
        review_task.apply_async(args=[result], queue="review")
    else:
        complete_task.apply_async(args=[result])
```

---

## 10. Error Handling in Workflows

### `link_error` callback
```python
@app.task
def on_error(request, exc, traceback):
    logger.error(f"Task {request.id} failed: {exc}")

# Attach error handler
task = my_task.s(1).set(link_error=on_error.s())
task.delay()
```

### Chord errback
```python
chord(
    (process.s(i) for i in range(10)),
    aggregate.s(),
).apply_async(link_error=on_error.s())
```

### Allow partial failures (chord with `propagate=False`)
```python
result = workflow.apply_async()
result.get(propagate=False)   # don't raise on failure
```

---

## 11. Complex Workflow: DAG-style

For complex graphs, use chord nesting:

```python
# Step 1: parallel A, B, C
# Step 2: when all done, parallel D, E
# Step 3: when D, E done, F

step_1 = group(a.s(), b.s(), c.s())
step_2_then_3 = chord(
    [d.s(), e.s()],
    f.s(),
)
workflow = chord(step_1, step_2_then_3)
```

For very complex DAGs: consider **Apache Airflow** or **Temporal**.

---

## 12. Replay / Retry Whole Chain

Chain failures can be retried by reapplying:

```python
result = workflow.apply_async()
if result.failed():
    # Retry from start
    workflow.apply_async()

# Or retry from specific step
remaining_chain = chain(transform.s(), save.s())
remaining_chain.delay(initial_data)
```

---

## 13. Result Backend Requirements

| Operation | Requires Result Backend |
|---|---|
| Simple `delay()` | No |
| `.get()` result | Yes |
| `chord` | Yes (mandatory!) |
| `group` + `.get()` | Yes |

Common result backends:
- Redis (most common)
- RabbitMQ (limited features)
- DynamoDB (AWS-native)
- PostgreSQL (durable)

---

## 14. Performance Considerations

### Chord overhead
- Every chord task writes to result backend
- 1000 chord = 1000 writes
- For high throughput: avoid huge chords

### Group result fetching
```python
# Bad — sequential get
results = [r.get() for r in group_result]

# Good — group.get() is parallel
results = group_result.get()
```

### Chunks vs individual tasks
```python
# 100K individual tasks = 100K broker round trips
my_task.delay(i) for i in range(100000)

# 100 chunked tasks = 100 broker round trips
my_task.chunks(range(100000), 1000).apply_async()
# But: chunks limited — each task must accept list
```

---

## 15. Real-World: ETL Pipeline

```python
@app.task
def extract_partition(partition_id):
    return read_data_partition(partition_id)

@app.task
def transform_partition(data):
    return clean_and_enrich(data)

@app.task
def load_partitions(transformed_partitions):
    # Receives list of transformed partitions
    return write_to_warehouse(transformed_partitions)

@app.task
def notify_completion(load_result):
    send_slack(f"ETL complete: {load_result}")


# Pipeline
partitions = list_partitions()    # e.g., 100 partitions

etl_workflow = chord(
    # Extract + Transform each partition in parallel
    [
        chain(
            extract_partition.s(p_id),
            transform_partition.s(),
        )
        for p_id in partitions
    ],
    # Load all + notify
    chain(load_partitions.s(), notify_completion.s()),
)
etl_workflow.apply_async()
```

---

## 16. Workflow Inspection

```python
result = workflow.apply_async()
print(result.id)
print(result.parent)            # previous task in chain
print(result.children)           # tasks spawned

# Group result
gr = group_signature.apply_async()
print(gr.completed_count())      # X out of N done
print(gr.successful())           # all succeeded?
print(gr.ready())                # all done (success or fail)?
print(gr.failed())               # any failed?

# Chord — query callback result
chord_result.get()                # callback's result
```

---

## 17. Common Pitfalls

### Pitfall 1: Chord without result backend
```python
# Default broker_url only — chord FAILS silently
app.conf.result_backend = "redis://..."  # mandatory!
```

### Pitfall 2: Huge chord = memory bloat
1M tasks in a chord → 1M results in memory.

### Pitfall 3: Mutable signature when expecting immutable
```python
# Bad — result of A becomes first arg of B unexpectedly
chain(notify.s(), cleanup.s())   # cleanup gets notify's return!

# Fix
chain(notify.si(), cleanup.si())   # immutable
```

### Pitfall 4: Hardcoded queue routes break chains
Different parts of chain end up on different queues with different workers.

### Pitfall 5: Group with no result backend → can't `.get()`
Group can run, but `.get()` fails without backend.

---

## 18. Interview Questions

**Q1: Canvas primitives?**
- signature: task call template
- chain: sequential
- group: parallel
- chord: group + callback when all done
- map/starmap: apply to iterable

**Q2: chord vs group?**
Group = parallel only. Chord = group + callback that receives all results.

**Q3: Chord requirement?**
Result backend mandatory. Stores intermediate results.

**Q4: Sequence + parallel example?**
```python
chain(
    setup.s(),
    chord([a.s(), b.s()], merge.s()),
    finalize.s(),
)
```

**Q5: Mutable vs immutable signature?**
Mutable (`.s()`): in chain, receives prev result. Immutable (`.si()`): ignores prev.

**Q6: Error in chord?**
By default, errors in group tasks don't run callback. Use `propagate=False` or error callback.

**Q7: Replace Airflow with Celery Canvas?**
Sometimes. Canvas good for moderate DAGs. Airflow better for very complex DAGs, scheduling, UI, observability.

---

## 19. Best Practices

1. **Use chains for sequential pipelines**
2. **Use chords for fan-out + aggregate**
3. **Set immutable signatures (`.si()`)** when prev result not needed
4. **Configure result backend** if using chords/groups with results
5. **Don't nest too deeply** — flatten when possible
6. **Error handlers via `link_error`**
7. **Inspect workflow state** during dev
8. **Chunks for very large iterables** to reduce broker load
9. **Monitor workflow latency end-to-end**
10. **Document workflow DAG** in code comments

---

## Related
- [[01_celery_basics]]
- [[02_celery_advanced]]
- [[03_celery_advanced_patterns]]
- [[08_long_running_task_cancellation]]
