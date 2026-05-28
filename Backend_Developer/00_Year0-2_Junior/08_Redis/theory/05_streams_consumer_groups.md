# Redis Streams + Consumer Groups

## Why It Matters (Senior 5 YOE Context)

Redis Streams = **Kafka-lite for Redis users**:
- **Persistent event log** (vs Pub/Sub which loses messages)
- **Consumer groups** for load distribution
- **At-least-once delivery** with ACK
- **Reprocessing** old messages by ID

Use cases: event sourcing, AI task queue, audit log, real-time analytics, microservice events.

Senior interview: "Need a durable queue but don't want Kafka complexity" → Redis Streams.

---

## Core Concepts

### Stream Basics

```bash
# Add event to stream (XADD)
XADD events:user-signups * email alice@example.com source web
# → "1709123456789-0" (auto-generated ID: timestamp-sequence)

# Read latest events
XRANGE events:user-signups - +     # all events
XRANGE events:user-signups - + COUNT 10
XREVRANGE events:user-signups + -  # reverse

# Read new events (blocking)
XREAD BLOCK 5000 STREAMS events:user-signups $    # $ = only new
XREAD COUNT 10 STREAMS events:user-signups 0      # 0 = from start
```

### Consumer Groups (Load Distribution)

```bash
# Create group
XGROUP CREATE events:user-signups workers $ MKSTREAM
# $ = start from newest; 0 = from beginning

# Consumer reads
XREADGROUP GROUP workers consumer-1 COUNT 10 BLOCK 5000 STREAMS events:user-signups >
# > = only undelivered

# Acknowledge
XACK events:user-signups workers 1709123456789-0
```

`>` symbol = "give me undelivered messages". Each message delivered to ONE consumer in the group.

### Python Implementation (redis-py)

```python
import redis


r = redis.Redis(decode_responses=True)


# Producer
def publish_event(stream, event):
    r.xadd(stream, event, maxlen=10000)  # cap stream size


publish_event('events:orders', {'order_id': 1, 'amount': 100})


# Consumer (group)
def setup_group(stream, group):
    try:
        r.xgroup_create(stream, group, id='$', mkstream=True)
    except redis.ResponseError as e:
        if 'BUSYGROUP' not in str(e):
            raise


def consume(stream, group, consumer_name):
    setup_group(stream, group)
    while True:
        messages = r.xreadgroup(
            group,
            consumer_name,
            {stream: '>'},
            count=10,
            block=5000,
        )
        for _stream, entries in messages:
            for msg_id, fields in entries:
                try:
                    process(fields)
                    r.xack(stream, group, msg_id)
                except Exception:
                    # Not ACK'd → reappears via XCLAIM
                    pass
```

### Pending Entries List (PEL) + XCLAIM

If consumer crashes after read but before ACK, message stays in PEL:

```bash
# View pending
XPENDING events:user-signups workers
# Summary: 5 pending

XPENDING events:user-signups workers - + 10
# Detail: msg_id, consumer, idle_ms, deliveries


# Claim stuck messages (idle > 30s)
XCLAIM events:user-signups workers consumer-2 30000 1709123456789-0
# Now consumer-2 owns it


# Auto-claim (Redis 6.2+)
XAUTOCLAIM events:user-signups workers consumer-2 30000 0 COUNT 10
```

Production pattern: periodic task that XAUTOCLAIM old pending messages → reprocess.

### Trimming (Capping Stream Size)

```bash
# Approximate trim (fast, allows slight overflow)
XADD events:logs MAXLEN ~ 100000 * msg "..."

# Exact trim
XADD events:logs MAXLEN = 100000 * msg "..."

# Trim by min ID
XTRIM events:logs MINID 1709000000000-0
```

`~` = approximate (rounded to whole macro-nodes for efficiency).

### Reading Multiple Streams

```python
r.xread(
    {'stream1': '$', 'stream2': '$'},
    block=5000,
)
```

### Resume Pattern (Last Seen ID)

```python
last_id = '0'   # or load from persistent store
while True:
    messages = r.xread({stream: last_id}, count=100, block=5000)
    for stream, entries in messages:
        for msg_id, fields in entries:
            process(fields)
            last_id = msg_id
            save_last_id_somewhere(last_id)
```

For at-least-once, store last_id durably.

### vs Pub/Sub vs Kafka

| Feature | Pub/Sub | Streams | Kafka |
|---|---|---|---|
| Persistence | No | Yes (configurable) | Yes (mandatory) |
| Consumer groups | No | Yes | Yes |
| Replay | No | Yes | Yes |
| Multi-consumer | All get all | One per group | One per group |
| Throughput | Very high | High | Very high |
| Operational complexity | Trivial | Low | High |

---

## How It Works Internally

### Radix Tree Storage

Streams stored as macro-nodes in radix tree. Compact (delta encoding). Range queries fast.

### IDs

Format: `<unix-ms>-<sequence>`. Monotonically increasing per stream. Can specify own ID with `XADD key id ...`.

### PEL Memory

Each pending entry held in memory until ACK. Don't let PEL grow unbounded — monitor + claim stuck messages.

---

## Common Pitfalls

### 1. Forgetting MAXLEN

```python
r.xadd('logs', {...})  # stream grows forever → memory blowup
```

Always cap. `MAXLEN ~ 1000000` keeps recent 1M.

### 2. No Consumer Group Reads = All Same Data

`XREAD` (without GROUP) — all consumers get all messages. Use `XREADGROUP` for load distribution.

### 3. Slow Consumer = PEL Grows

If consumer doesn't ACK, messages accumulate. Set alerts on XPENDING summary.

### 4. Forgetting XACK

```python
messages = r.xreadgroup(...)
process(...)
# Forgot r.xack(...) — message stays pending forever
```

Always ACK after success. Set up XAUTOCLAIM for crashed consumers.

### 5. ID Conflicts

```python
r.xadd('s', {...}, id='1234-0')  # MUST be greater than last
```

If new ID ≤ existing → error. Use `*` for auto-generation.

### 6. Stream Per Customer = Too Many Keys

For multi-tenant: one stream per tenant might be too many. Use single stream + tenant filter in consumer:

```python
r.xadd('global-events', {'tenant_id': 5, ...})
```

Or shard by tenant ID modulo N.

---

## Interview Q&A

**Q1:** Redis Streams vs Kafka — kab kya use karoge?
**A:** Streams: simpler ops, already using Redis, throughput < ~1M msg/sec, retention < 1 week (memory). Kafka: > 1M msg/sec, multi-day retention, multi-DC replication, mature ecosystem (Connect, Streams API). For most apps: Streams if Redis already in stack; Kafka for high-scale dedicated streaming.

**Q2:** Consumer group fail kar gaya — message kaise recover hota hai?
**A:** Crashed consumer's messages stuck in PEL (Pending Entries List). Two options: (1) Manual XCLAIM by another consumer. (2) XAUTOCLAIM (Redis 6.2+) — periodic task scans PEL for idle > X seconds, claims to new consumer. Idempotency required since message may be processed twice.

**Q3:** XADD MAXLEN ~ vs = — difference?
**A:** `=` exact length, slightly slower. `~` approximate (rounded to whole radix-tree macro-nodes), faster. Use `~` for non-strict caps. For exact retention by time, use MINID-based trim instead.

**Q4:** Streams persistent kaise hain?
**A:** Same as other Redis data — controlled by AOF/RDB. Default: RDB snapshots (data loss on crash within snapshot window). AOF + fsync everysec = ~1s data loss worst case. AOF + fsync always = no loss but slow. Configure per durability requirement.

**Q5:** Exactly-once vs at-least-once?
**A:** Streams = at-least-once by default. If consumer crashes after process before ACK, next consumer reprocesses. For exactly-once: idempotent processing (dedupe by msg_id in Redis SET / DB unique constraint). True exactly-once impossible in distributed systems.

**Q6:** Replay messages kaise karein?
**A:** Streams retain by MAXLEN — replay anything still in stream. `XREAD STREAMS stream 0` from beginning. Or create new consumer group with `id=0` instead of `$`. Or use XREVRANGE to walk backward.

**Q7:** Hot consumer scenario kya hai?
**A:** Single stream + single consumer = bottleneck. Fix: multiple consumers in same group (load distributes). For ordered processing per key (e.g., per user), shard by key into N streams; each stream handled by one consumer.

**Q8:** XPENDING monitoring kya batata hai?
**A:** Summary: total pending count, min/max IDs, consumers and pending counts. Detail: per-message idle time, deliveries count, owner consumer. Alert on: PEL > N, idle > Xs, deliveries > 5 (poison pill).

---

## Real-World Use Cases

### 1. AI Task Queue

```python
# Producer (API)
r.xadd('ai:tasks', {'prompt': '...', 'user_id': 1, 'model': 'claude'})


# Worker
async def worker(consumer_name):
    while True:
        msgs = r.xreadgroup('ai-workers', consumer_name, {'ai:tasks': '>'},
                             count=1, block=5000)
        for _, entries in msgs:
            for msg_id, fields in entries:
                try:
                    result = await call_llm(fields)
                    await store_result(msg_id, result)
                    r.xack('ai:tasks', 'ai-workers', msg_id)
                except Exception:
                    # Don't ACK — will retry via XAUTOCLAIM
                    pass
```

### 2. Event Sourcing

Each domain event → stream. Replay from `id=0` to rebuild state.

### 3. Audit Log

```python
r.xadd('audit', {
    'user_id': 1,
    'action': 'login',
    'ip': '...',
    'ts': time.time(),
}, maxlen=1000000)
```

Compliance: stream backed up daily to S3.

---

## References

- [Redis Streams Intro](https://redis.io/docs/data-types/streams/)
- [Streams Tutorial](https://redis.io/docs/data-types/streams-tutorial/)
- [XADD command](https://redis.io/commands/xadd/)
- "Redis Stack" book by Brian Sam-Bodden
