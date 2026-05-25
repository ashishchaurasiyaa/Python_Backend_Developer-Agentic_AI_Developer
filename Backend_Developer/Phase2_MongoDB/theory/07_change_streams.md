# MongoDB Change Streams

## Why It Matters

Change Streams = real-time event listening on collection/database/cluster:
- **Cache invalidation** → invalidate Redis when MongoDB doc updates
- **Sync to other systems** → MongoDB → Elasticsearch
- **Real-time dashboards** → push UI updates
- **Event sourcing** → react to DB mutations
- **Audit log** → capture all changes

vs polling: real-time, lower overhead, exactly-once delivery.

Senior interview: "MongoDB → Elasticsearch sync — design?" → Change Streams listener forwarding to ES.

---

## Core Concepts

### Requirements

- Replica set or sharded cluster (no standalone)
- MongoDB 4.0+ for collection streams
- 4.0+ database/cluster streams

### Basic Watch

```python
from pymongo import MongoClient


client = MongoClient("mongodb://localhost:27017/?replicaSet=rs0")
db = client.mydb


# Watch a collection
with db.users.watch() as stream:
    for change in stream:
        print(change)
```

Each change document:

```json
{
  "_id": {"_data": "..."},
  "operationType": "insert",
  "clusterTime": Timestamp(...),
  "ns": {"db": "mydb", "coll": "users"},
  "documentKey": {"_id": ObjectId("...")},
  "fullDocument": {...}
}
```

### Operation Types

- `insert` — new doc
- `update` — existing doc updated
- `replace` — entire doc replaced
- `delete` — doc deleted
- `drop` — collection dropped
- `dropDatabase`
- `rename`
- `invalidate` — stream invalidated (collection dropped, etc.)

### Filter with Pipeline ($match)

```python
pipeline = [
    {'$match': {
        'operationType': {'$in': ['insert', 'update']},
        'fullDocument.status': 'paid',
    }}
]

with db.orders.watch(pipeline) as stream:
    for change in stream:
        process_paid_order(change['fullDocument'])
```

### fullDocument Option

```python
# Default: 'default' — fullDocument only for insert
# 'updateLookup' — also fetch current doc for update events

with db.users.watch(full_document='updateLookup') as stream:
    for change in stream:
        # change['fullDocument'] available even for update
        ...


# 'whenAvailable' (5.0+) — pre-image of updated doc
with db.users.watch(full_document_before_change='whenAvailable') as stream:
    for change in stream:
        before = change.get('fullDocumentBeforeChange')
        after = change.get('fullDocument')
```

### Resume Tokens (Resumability)

Each event has `_id` = resume token. Save it to resume from where you left off after restart/crash:

```python
import json


resume_token = None  # load from persistent store


while True:
    try:
        kwargs = {'resume_after': resume_token} if resume_token else {}
        with db.users.watch(**kwargs) as stream:
            for change in stream:
                process(change)
                resume_token = change['_id']
                save_resume_token(resume_token)  # persist
    except pymongo.errors.PyMongoError:
        time.sleep(1)
        # Loop re-opens with last resume_token
```

### Database / Cluster Streams

```python
# All collections in database
db.watch()


# Cluster-wide (all databases) — admin only
client.watch()
```

### Async (Motor)

```python
from motor.motor_asyncio import AsyncIOMotorClient


async def watch_users():
    client = AsyncIOMotorClient("mongodb://localhost:27017/?replicaSet=rs0")
    async with client.mydb.users.watch() as stream:
        async for change in stream:
            print(change)
```

### Pre-Image / Post-Image (Pre-Image Setup)

```javascript
db.runCommand({
    collMod: 'users',
    changeStreamPreAndPostImages: { enabled: true }
})


// Now use:
db.users.watch([], {fullDocumentBeforeChange: 'required'})
```

---

## How It Works Internally

### Built on Oplog

Change streams tail the oplog. Equivalent to running `db.oplog.rs.find()` but with structured events + filtering + resumability.

### At-Least-Once Delivery

If consumer crashes after read, restarts with `resume_after` → may get same event twice. Make handler idempotent.

### Timestamp Order

Events emit in cluster timestamp order. Same as oplog write order.

### Filter Pushdown

`$match` in pipeline pushed to server — fewer events sent over wire.

---

## Common Pitfalls

### 1. No Resume Token Persistence

```python
# If consumer crashes mid-loop, on restart starts from now → misses events
with col.watch() as stream:
    for change in stream:
        process(change)
```

Always persist resume token. Use Redis, DB, or Mongo itself.

### 2. Watch Closed After Long Idle

If no events for `maxAwaitTimeMS` (default 1s), driver may block. For long-running streams, set higher timeout or auto-reconnect on close.

### 3. Standalone Server

```
Error: $changeStream requires replica set or sharded cluster
```

Must run as replica set even single-node.

### 4. fullDocument Not Available for Updates

Default behavior. Use `full_document='updateLookup'`.

### 5. Heavy Handler Blocks Stream

```python
for change in stream:
    # 10s of work per event → backlog grows
    slow_process(change)
```

Decouple: stream pushes to queue, workers consume. Or async with semaphore.

### 6. Resume Token Expiry

If you fall too far behind, resume token may not be in oplog anymore → can't resume. Mitigation: larger oplog or restart from current.

### 7. Permissions

User needs `changeStream` privilege:

```javascript
db.grantRolesToUser('appuser', [{ role: 'readWrite', db: 'mydb' }, { role: 'read', db: 'local' }])
```

---

## Interview Q&A

**Q1:** Change Streams kab use karte ho?
**A:** Real-time reactions to data changes — cache invalidation, sync to search/analytics, push notifications, audit logs. Replaces polling. Pros: real-time, low overhead, exactly-once-able. Requires replica set, only works for live data (not historical).

**Q2:** Resume token kya hai?
**A:** Opaque ID for each event = position in oplog. On crash, restart with `resume_after=token` → continues from after that event. Critical for at-least-once delivery. Persist after every processed event.

**Q3:** fullDocument options explain karo.
**A:** `default` — fullDocument only for insert/replace. `updateLookup` — fetches current state for update events (one extra read). `required` — needed for $match on full doc fields. `whenAvailable` (with pre-image) — older state.

**Q4:** Change Stream vs Kafka Connect MongoDB?
**A:** Native streams: simple, no extra infra, good for medium scale. Kafka Connect: separate connector → Kafka → consumers, more buffering, better for high throughput + multiple consumers + replay. For < 10k events/sec: native streams sufficient.

**Q5:** Resumability after long downtime?
**A:** If oplog overwritten the resume token's position, can't resume — must restart from latest (skip missed events). Mitigation: larger oplog (rs.printReplicationInfo() shows window), or use Kafka Connect which has its own buffer.

**Q6:** Exactly-once with change streams?
**A:** Streams are at-least-once. For exactly-once: idempotent handlers (dedup by `_id` or operation ID in app DB/Redis). Use `clusterTime` + `_id` from change doc as unique key.

**Q7:** Stream filtering via pipeline?
**A:** `$match` on event fields — operationType, ns, fullDocument fields. Server-side filter — reduces network. Other stages: `$project` to limit fields, `$addFields` to enrich.

**Q8:** Multiple consumers same stream?
**A:** Open multiple `watch()` calls — each gets independent stream (own resume token). Or use Kafka Connect for true fan-out. Don't share resume tokens between consumers (one will fall behind).

---

## Real-World Use Cases

### 1. MongoDB → Elasticsearch Sync

```python
async def sync_to_es():
    es = AsyncElasticsearch()
    resume_token = await load_resume_token()

    while True:
        try:
            kwargs = {'full_document': 'updateLookup'}
            if resume_token:
                kwargs['resume_after'] = resume_token
            async with db.products.watch(**kwargs) as stream:
                async for change in stream:
                    if change['operationType'] in {'insert', 'update', 'replace'}:
                        doc = change['fullDocument']
                        await es.index(index='products', id=str(doc['_id']), document=doc)
                    elif change['operationType'] == 'delete':
                        await es.delete(index='products', id=str(change['documentKey']['_id']))

                    resume_token = change['_id']
                    await save_resume_token(resume_token)
        except Exception as e:
            print(f"Stream error: {e}, reconnecting...")
            await asyncio.sleep(2)
```

### 2. Cache Invalidation

```python
with db.users.watch(full_document='updateLookup') as stream:
    for change in stream:
        if change['operationType'] in {'update', 'replace', 'delete'}:
            user_id = str(change['documentKey']['_id'])
            redis_client.delete(f'user:{user_id}')
            print(f"Invalidated cache for user {user_id}")
```

### 3. Real-Time Notifications

```python
with db.orders.watch([{'$match': {'operationType': 'insert'}}]) as stream:
    for change in stream:
        order = change['fullDocument']
        await send_websocket_notification(
            user_id=order['user_id'],
            message=f"New order: {order['_id']}",
        )
```

---

## References

- [Change Streams docs](https://www.mongodb.com/docs/manual/changeStreams/)
- [pymongo Change Streams](https://pymongo.readthedocs.io/en/stable/api/pymongo/change_stream.html)
- MongoDB Kafka Connector
- Debezium MongoDB Connector
