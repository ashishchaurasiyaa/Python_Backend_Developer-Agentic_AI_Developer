"""
============================================================
CELERY CANVAS — Workflow Patterns Practical
============================================================
Working examples of:
1. signature primitives
2. chain (sequential)
3. group (parallel)
4. chord (group + callback)
5. map / starmap / chunks
6. Conditional branching
7. Error handling
8. Real ETL pipeline
"""


# ============================================================
# 1. SIGNATURE PATTERNS
# ============================================================
SIGNATURE_PATTERNS = '''
from celery import signature, shared_task

@shared_task
def add(x, y):
    return x + y

@shared_task
def multiply(x, y):
    return x * y

# Various ways to create signature
sig = add.s(2, 3)                     # short form
sig = add.signature(args=(2, 3))       # explicit
sig = signature("myapp.tasks.add", args=(2, 3))  # by name (string)

# Partial application (currying)
add_to_2 = add.s(2)                    # add(2, ?)
result = add_to_2.delay(5)              # add(2, 5) = 7

# Immutable vs Mutable
sig_mutable = add.s(2)                 # in chain, prev result becomes 2nd arg
sig_immutable = add.si(2, 3)           # ignores prev result

# Options on signature
sig = add.s(2, 3).set(queue="priority", countdown=10, expires=60)
result = sig.delay()
'''


# ============================================================
# 2. CHAIN (Sequential Pipeline)
# ============================================================
CHAIN_EXAMPLES = '''
from celery import chain

# Method 1: chain() function
workflow = chain(
    fetch_data.s("user-42"),
    clean_data.s(),
    save_data.s(),
)
result = workflow.apply_async()
final = result.get()    # value from save_data

# Method 2: pipe operator
workflow = fetch_data.s("user-42") | clean_data.s() | save_data.s()
result = workflow()    # same as apply_async()

# Mixing immutable signatures
workflow = chain(
    notify_admin.si("user signup"),      # immutable — ignores prev
    log_event.s(),                        # mutable — receives prev result
)

# Chain failure: subsequent tasks skipped
# Inspect chain result
result = workflow.apply_async()
print(result.parent)                      # previous task result
print(result.parent.parent)                # earlier task
'''


# ============================================================
# 3. GROUP (Parallel)
# ============================================================
GROUP_EXAMPLES = '''
from celery import group

# Submit 100 emails in parallel
job = group(send_email.s(user_id) for user_id in range(100))
result = job.apply_async()

# Wait for all to finish
results = result.get()                    # list of 100 results
print(f"Sent {len(results)} emails")

# Monitor progress
import time
while not result.ready():
    print(f"{result.completed_count()}/{len(result)} done")
    time.sleep(1)

# Group with kwargs
group_result = group(
    send_email.s(user_id, template="welcome")
    for user_id in user_ids
).apply_async()
'''


# ============================================================
# 4. CHORD (Group + Callback)
# ============================================================
CHORD_EXAMPLES = '''
from celery import chord

# Process partitions in parallel, then aggregate

@shared_task
def process_partition(partition_id):
    return {"partition": partition_id, "count": 100}

@shared_task
def aggregate_results(results):
    """Receives LIST of all partition results."""
    total = sum(r["count"] for r in results)
    return {"total": total, "partitions": len(results)}

# Chord
workflow = chord(
    (process_partition.s(p) for p in range(10)),    # group
    aggregate_results.s(),                            # callback
)
result = workflow.apply_async()
print(result.get())    # aggregate's return

# IMPORTANT: chord REQUIRES result backend
# app.conf.result_backend = "redis://localhost:6379/0"


# Chord with error handling
chord_workflow = chord(
    (process_partition.s(p) for p in range(10)),
    aggregate_results.s(),
).on_error(handle_chord_failure.s())
'''


# ============================================================
# 5. MAP / STARMAP / CHUNKS
# ============================================================
MAP_STARMAP_CHUNKS = '''
# map — applies task to each element (element passed as first arg)
result = add.map([(1, 2), (3, 4), (5, 6)])
# Each call: add((1,2)), add((3,4)), add((5,6))

# starmap — unpacks tuple as args
result = add.starmap([(1, 2), (3, 4), (5, 6)])
# Each call: add(1,2), add(3,4), add(5,6)

# chunks — group items in batches
process_user.chunks(user_ids, 1000)
# Creates ~ceil(len/1000) tasks, each processes 1000 items
# Less broker traffic than 100K individual tasks

# Best for high-volume:
# 1M users → 1000 chunks of 1000 → 1000 tasks vs 1M tasks
'''


# ============================================================
# 6. REAL-WORLD: IMAGE PROCESSING PIPELINE
# ============================================================
IMAGE_PIPELINE = '''
@shared_task
def upload_original(image_data):
    """Upload original image, return reference."""
    return {"original_url": store_in_s3(image_data)}

@shared_task
def resize(data, size):
    """Resize to specified width."""
    url = resize_and_upload(data["original_url"], size)
    return {**data, f"size_{size}": url}

@shared_task
def generate_thumbnail_collage(sized_images):
    """All sizes uploaded — make collage of them."""
    return {"collage_url": create_collage(sized_images)}

@shared_task
def update_db(result):
    """Persist final URLs to DB."""
    db.update_image(result)
    return result

@shared_task
def notify_user(result):
    """Send notification."""
    push_notify(result.get("user_id"))


# Pipeline:
# 1. Upload original
# 2. Parallel: 4 resize tasks
# 3. After all done: generate collage
# 4. Update DB
# 5. Notify user
pipeline = chain(
    upload_original.s(image_data),
    chord(
        [
            resize.s(size=200),
            resize.s(size=500),
            resize.s(size=1000),
            resize.s(size=2000),
        ],
        generate_thumbnail_collage.s(),
    ),
    update_db.s(),
    notify_user.s(),
)
pipeline.apply_async()
'''


# ============================================================
# 7. ETL PIPELINE
# ============================================================
ETL_PIPELINE = '''
@shared_task
def extract_partition(partition_id, source_table):
    """Read partition from source."""
    rows = read_from_source(source_table, partition_id)
    return {"partition": partition_id, "rows": rows}

@shared_task
def transform_partition(data):
    """Clean and enrich."""
    transformed = []
    for row in data["rows"]:
        transformed.append(clean_and_enrich(row))
    return {"partition": data["partition"], "rows": transformed}

@shared_task
def load_all_partitions(transformed_partitions):
    """Batch insert all transformed data."""
    total = 0
    for p in transformed_partitions:
        load_to_warehouse(p["rows"])
        total += len(p["rows"])
    return {"total_rows": total}

@shared_task
def notify_etl_complete(load_result):
    send_slack(f"ETL complete: {load_result['total_rows']} rows")
    return load_result


def run_etl(source_table):
    partitions = list_partitions(source_table)

    workflow = chord(
        # Extract + Transform each partition in parallel
        [
            chain(
                extract_partition.s(p_id, source_table),
                transform_partition.s(),
            )
            for p_id in partitions
        ],
        # When all done, load + notify
        chain(load_all_partitions.s(), notify_etl_complete.s()),
    )
    return workflow.apply_async()
'''


# ============================================================
# 8. CONDITIONAL BRANCHING
# ============================================================
CONDITIONAL_BRANCH = '''
@shared_task
def check_user_tier(user_id):
    user = User.objects.get(id=user_id)
    return {"user_id": user_id, "tier": user.tier}


@shared_task
def premium_workflow(data):
    # Premium-specific processing
    return enhance_premium_user(data["user_id"])


@shared_task
def standard_workflow(data):
    return standard_processing(data["user_id"])


@shared_task
def branch(data):
    """Decide which path to take."""
    if data["tier"] == "premium":
        return premium_workflow.apply_async(args=[data]).get()
    return standard_workflow.apply_async(args=[data]).get()


# Usage
chain(check_user_tier.s(42), branch.s()).apply_async()


# Alternative: nested signatures
@shared_task(bind=True)
def smart_router(self, data):
    if data["tier"] == "premium":
        return self.replace(premium_workflow.si(data))
    return self.replace(standard_workflow.si(data))
'''


# ============================================================
# 9. ERROR HANDLING
# ============================================================
ERROR_HANDLING = '''
from celery import chain, group, chord

# link_error — runs only on failure
@shared_task
def handle_failure(request, exc, traceback):
    logger.error(f"Task {request.id} failed: {exc}")
    alert_oncall(request.id, str(exc))


# Attach to single task
task_sig = my_task.s(1).on_error(handle_failure.s())

# Attach to chain
workflow = chain(a.s(), b.s(), c.s())
workflow.link_error(handle_failure.s())
workflow.apply_async()

# Chord-specific error handler
chord_workflow = chord(
    (process.s(i) for i in range(10)),
    aggregate.s(),
).on_error(handle_chord_failure.s())


# Allow partial failures (don't propagate)
result = workflow.apply_async()
try:
    final = result.get(propagate=False)    # don't raise
except Exception:
    pass

# Check status without raising
if result.failed():
    print(f"Workflow failed at {result.parent}")
'''


# ============================================================
# 10. INSPECTING WORKFLOW STATE
# ============================================================
INSPECT_WORKFLOW = '''
result = workflow.apply_async()

# Chain — get each step
print(result.id)              # last task
print(result.parent)          # previous task in chain
print(result.parent.parent)   # earlier

# Group
group_result = group_workflow.apply_async()
print(group_result.completed_count())   # X / total
print(group_result.successful())         # all OK?
print(group_result.failed())              # any failed?
print(group_result.ready())               # all done?

# Iterate results
for r in group_result.results:
    print(f"Task {r.id}: {r.state}")

# Chord — get callback result
chord_result = chord_workflow.apply_async()
final = chord_result.get()   # callback's return value
'''


# ============================================================
# 11. ADVANCED: REPLAY / RESUME
# ============================================================
REPLAY_PATTERNS = '''
# Replay whole chain
def replay_workflow(workflow_id):
    # Lookup original args from DB
    workflow_data = get_workflow_record(workflow_id)
    workflow = chain(*[
        task_class.s(**step["kwargs"])
        for step in workflow_data["steps"]
    ])
    return workflow.apply_async()


# Resume from specific step
def resume_from_step(workflow_id, step_index):
    workflow_data = get_workflow_record(workflow_id)
    intermediate = workflow_data["intermediate_results"][step_index - 1]
    remaining = chain(*[
        task_class.s(**step["kwargs"])
        for step in workflow_data["steps"][step_index:]
    ])
    return remaining.apply_async(args=[intermediate])
'''


# ============================================================
# 12. PERFORMANCE COMPARISON
# ============================================================
PERFORMANCE = '''
# 100K tasks individually
for i in range(100000):
    my_task.delay(i)
# = 100K broker round trips, ~10 seconds to enqueue

# Same with group
group(my_task.s(i) for i in range(100000)).apply_async()
# = 1 broker call (group serialized as single op), much faster

# Same with chunks (recommended for very large iterables)
my_task.chunks(range(100000), 1000).apply_async()
# = 100 tasks, each processes 1000 items
# Less broker overhead, less result storage

# Trade-offs:
# - Individual: max parallelism, max overhead
# - Group: parallel but huge result set
# - Chunks: less parallelism but less overhead
'''


# ============================================================
# MAIN
# ============================================================
if __name__ == "__main__":
    print("=" * 60)
    print("CELERY CANVAS — Workflow Patterns")
    print("=" * 60)

    print("\n--- 1. SIGNATURES ---")
    print(SIGNATURE_PATTERNS)
    print("\n--- 2. CHAIN ---")
    print(CHAIN_EXAMPLES)
    print("\n--- 3. GROUP ---")
    print(GROUP_EXAMPLES)
    print("\n--- 4. CHORD ---")
    print(CHORD_EXAMPLES)
    print("\n--- 5. MAP / STARMAP / CHUNKS ---")
    print(MAP_STARMAP_CHUNKS)
    print("\n--- 6. IMAGE PIPELINE ---")
    print(IMAGE_PIPELINE)
    print("\n--- 7. ETL PIPELINE ---")
    print(ETL_PIPELINE)
    print("\n--- 8. CONDITIONAL BRANCHING ---")
    print(CONDITIONAL_BRANCH)
    print("\n--- 9. ERROR HANDLING ---")
    print(ERROR_HANDLING)
    print("\n--- 10. INSPECTING WORKFLOWS ---")
    print(INSPECT_WORKFLOW)
    print("\n--- 11. REPLAY PATTERNS ---")
    print(REPLAY_PATTERNS)
    print("\n--- 12. PERFORMANCE ---")
    print(PERFORMANCE)

    print("\n" + "=" * 60)
    print("CHEAT SHEET")
    print("=" * 60)
    print("""
chain     A → B → C        sequential
group     [A, B, C]        parallel
chord     [A, B, C] → D    parallel then callback
map       task.map(iter)   one task per item
starmap   star-unpack args same as map but tuples
chunks    batch items      reduce broker overhead

| or chain()       sequential
group()             parallel
chord(g, cb)        parallel + cb when all done

.s() = mutable    .si() = immutable
""")
