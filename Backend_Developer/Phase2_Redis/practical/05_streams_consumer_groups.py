"""
Redis Streams + Consumer Groups — Production Patterns
"""

import asyncio
import json
import time
import uuid

import redis
import redis.asyncio as aioredis


r = redis.Redis(host='localhost', port=6379, decode_responses=True)


# ==========================================================================
# 1. PRODUCER — XADD
# ==========================================================================

def publish_event(stream: str, event: dict, maxlen: int = 100000):
    """Cap stream size to prevent unbounded growth."""
    msg_id = r.xadd(
        stream,
        event,
        maxlen=maxlen,
        approximate=True,  # ~ — faster, slight overflow OK
    )
    return msg_id


# Example
# publish_event('events:orders', {'order_id': '1', 'amount': '99.99'})
# publish_event('events:logins', {'user_id': '42', 'ip': '1.2.3.4'})


# ==========================================================================
# 2. SIMPLE READ (no groups) — fan-out to all readers
# ==========================================================================

def tail_stream(stream: str, last_id: str = '$'):
    """Read new messages forever. $ = only new; 0 = from beginning."""
    while True:
        messages = r.xread({stream: last_id}, count=10, block=5000)
        for _, entries in messages:
            for msg_id, fields in entries:
                yield msg_id, fields
                last_id = msg_id


# ==========================================================================
# 3. CONSUMER GROUP — Load distribution
# ==========================================================================

def setup_group(stream: str, group: str, start_from: str = '$'):
    """Create group idempotently. start_from='$' = new msgs only, '0' = from beginning."""
    try:
        r.xgroup_create(stream, group, id=start_from, mkstream=True)
        print(f"Created group {group} on {stream}")
    except redis.ResponseError as e:
        if 'BUSYGROUP' in str(e):
            print(f"Group {group} already exists")
        else:
            raise


def consume_group(
    stream: str,
    group: str,
    consumer_name: str,
    handler,
    batch_size: int = 10,
    block_ms: int = 5000,
):
    """Consumer worker loop."""
    setup_group(stream, group)

    while True:
        try:
            messages = r.xreadgroup(
                group,
                consumer_name,
                {stream: '>'},   # > = only undelivered
                count=batch_size,
                block=block_ms,
            )
        except redis.ConnectionError:
            time.sleep(1)
            continue

        for _stream, entries in messages:
            for msg_id, fields in entries:
                try:
                    handler(msg_id, fields)
                    # ACK after successful processing
                    r.xack(stream, group, msg_id)
                except Exception as e:
                    # Don't ACK — message remains in PEL for retry
                    print(f"Failed to process {msg_id}: {e}")


# Example handler
def process_order(msg_id, fields):
    print(f"Processing order {msg_id}: {fields}")
    # ... DB write, external API call


# Run consumer
# consume_group('events:orders', 'order-processors', 'worker-1', process_order)


# ==========================================================================
# 4. XAUTOCLAIM — recover crashed consumer's messages
# ==========================================================================

def auto_claim_stuck_messages(
    stream: str,
    group: str,
    new_consumer: str,
    idle_ms: int = 30000,
):
    """Periodic task: claim messages idle > N ms (consumer crashed)."""
    cursor = '0'
    while True:
        cursor, claimed = r.xautoclaim(
            stream,
            group,
            new_consumer,
            min_idle_time=idle_ms,
            start_id=cursor,
            count=100,
        )
        if claimed:
            print(f"Claimed {len(claimed)} stuck messages")
            for msg_id, fields in claimed:
                # Re-process
                try:
                    process_order(msg_id, fields)
                    r.xack(stream, group, msg_id)
                except Exception as e:
                    print(f"Re-process failed for {msg_id}: {e}")

        if cursor == '0-0':
            break


# Schedule via cron or Celery beat
# auto_claim_stuck_messages('events:orders', 'order-processors', 'recovery-worker', 60000)


# ==========================================================================
# 5. PENDING ENTRIES (PEL) MONITORING
# ==========================================================================

def check_pending(stream: str, group: str):
    """View pending messages for group — alert if too many."""
    summary = r.xpending(stream, group)
    # Returns: {'pending': N, 'min': '...', 'max': '...', 'consumers': [...]}

    print(f"Stream {stream} group {group}: {summary['pending']} pending")
    if summary['pending'] > 1000:
        print("ALERT: PEL growing — slow consumers?")

    # Detail per message
    details = r.xpending_range(
        name=stream,
        groupname=group,
        min='-',
        max='+',
        count=10,
    )
    for d in details:
        # d = {'message_id': ..., 'consumer': ..., 'time_since_delivered': ms, 'times_delivered': N}
        if d['times_delivered'] > 5:
            print(f"POISON: {d['message_id']} delivered {d['times_delivered']} times")


# ==========================================================================
# 6. STREAM TRIMMING (retention)
# ==========================================================================

def trim_stream_by_size(stream: str, max_length: int = 100000):
    """Keep last N messages."""
    r.xtrim(stream, maxlen=max_length, approximate=True)


def trim_stream_by_time(stream: str, max_age_hours: int = 168):
    """Keep messages newer than N hours."""
    cutoff_ms = int((time.time() - max_age_hours * 3600) * 1000)
    cutoff_id = f'{cutoff_ms}-0'
    r.xtrim(stream, minid=cutoff_id)


# ==========================================================================
# 7. ASYNC CONSUMER (high concurrency)
# ==========================================================================

async def async_consume(
    stream: str,
    group: str,
    consumer_name: str,
    handler,
):
    r_async = aioredis.from_url('redis://localhost:6379', decode_responses=True)

    # Setup group
    try:
        await r_async.xgroup_create(stream, group, id='$', mkstream=True)
    except aioredis.ResponseError as e:
        if 'BUSYGROUP' not in str(e):
            raise

    try:
        while True:
            messages = await r_async.xreadgroup(
                group,
                consumer_name,
                {stream: '>'},
                count=10,
                block=5000,
            )
            for _stream, entries in messages:
                tasks = []
                for msg_id, fields in entries:
                    tasks.append(
                        process_and_ack(r_async, stream, group, msg_id, fields, handler)
                    )
                await asyncio.gather(*tasks, return_exceptions=True)
    finally:
        await r_async.aclose()


async def process_and_ack(r, stream, group, msg_id, fields, handler):
    try:
        await handler(msg_id, fields)
        await r.xack(stream, group, msg_id)
    except Exception as e:
        print(f"Process failed {msg_id}: {e}")


# ==========================================================================
# 8. AI TASK QUEUE EXAMPLE
# ==========================================================================

# Producer (API endpoint)
def queue_ai_task(prompt: str, user_id: int, model: str = 'claude-sonnet-4-6'):
    task_id = str(uuid.uuid4())
    r.xadd(
        'ai:tasks',
        {
            'task_id': task_id,
            'prompt': prompt,
            'user_id': str(user_id),
            'model': model,
            'queued_at': str(time.time()),
        },
        maxlen=100000,
    )
    return task_id


# Worker
async def ai_worker(consumer_name: str):
    r_async = aioredis.from_url('redis://localhost:6379', decode_responses=True)

    try:
        await r_async.xgroup_create('ai:tasks', 'ai-workers', id='$', mkstream=True)
    except aioredis.ResponseError:
        pass

    while True:
        messages = await r_async.xreadgroup(
            'ai-workers',
            consumer_name,
            {'ai:tasks': '>'},
            count=1,
            block=5000,
        )

        for _, entries in messages:
            for msg_id, fields in entries:
                task_id = fields['task_id']
                try:
                    # Call LLM
                    # result = await call_llm(fields['prompt'], fields['model'])
                    result = 'mock result'

                    # Store result
                    await r_async.hset(
                        f'ai:result:{task_id}',
                        mapping={'status': 'done', 'result': result},
                    )
                    await r_async.expire(f'ai:result:{task_id}', 3600)

                    await r_async.xack('ai:tasks', 'ai-workers', msg_id)
                except Exception as e:
                    print(f"Task {task_id} failed: {e}")


# ==========================================================================
# 9. PROD CONFIG
# ==========================================================================

PRODUCTION_CONFIG = """
# Persistence — for streams as durable queue
appendonly yes
appendfsync everysec   # ~1s data loss worst case

# Memory
maxmemory 4gb
maxmemory-policy noeviction   # don't evict streams!

# Monitor with:
redis-cli XINFO STREAM events:orders
redis-cli XINFO GROUPS events:orders
redis-cli XLEN events:orders


# Alert metrics:
# - XLEN > expected (slow consumers?)
# - XPENDING count > N
# - XPENDING max idle > Y
# - Group lag (newest_id - last_delivered_id)
"""


# ==========================================================================
# 10. EXACTLY-ONCE PROCESSING (via dedup)
# ==========================================================================

def process_with_dedup(msg_id: str, fields: dict):
    """Idempotent processing — skip if already processed."""
    dedup_key = f'processed:{msg_id}'

    # SETNX with TTL
    if not r.set(dedup_key, '1', ex=86400, nx=True):
        # Already processed
        return

    try:
        # Actual work
        do_work(fields)
    except Exception:
        # Allow retry
        r.delete(dedup_key)
        raise


def do_work(fields):
    pass  # placeholder
