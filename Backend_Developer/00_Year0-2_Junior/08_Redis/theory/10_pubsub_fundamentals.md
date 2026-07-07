# Redis Pub/Sub Fundamentals

## Why It Matters (Senior 5 YOE Context)

You already know Redis Streams (durable, replayable, consumer-group-based —
`05_streams_consumer_groups.md`). Pub/Sub is the OLDER, simpler mechanism it
was largely introduced to fix the shortcomings of — knowing exactly what
Pub/Sub can't do is what makes Streams' design make sense, and it's a
natural interview follow-up the moment Streams comes up.

Senior interview: "Why does Redis have both Pub/Sub AND Streams — aren't
they the same thing?" → Pub/Sub is fire-and-forget with zero persistence;
Streams exists specifically because Pub/Sub loses messages for anyone not
actively listening at the moment of publish.

---

## Core Concept

```
PUBLISH channel_name "message"
        │
        ▼
   Redis broadcasts to EVERY client currently SUBSCRIBED to that channel,
   RIGHT NOW, at this instant.

   Zero persistence. Zero delivery guarantee. If nobody is subscribed
   when PUBLISH happens, the message is GONE FOREVER — not queued,
   not stored, not replayable.
```

```bash
# Terminal 1 — subscriber
SUBSCRIBE notifications

# Terminal 2 — publisher
PUBLISH notifications "New order #123 created"

# Terminal 1 immediately receives:
# 1) "message"
# 2) "notifications"
# 3) "New order #123 created"
```

### Python (redis-py)

```python
import redis

r = redis.Redis(host="localhost", port=6379)

# Publisher
r.publish("notifications", "New order #123 created")

# Subscriber (blocking loop)
pubsub = r.pubsub()
pubsub.subscribe("notifications")

for message in pubsub.listen():
    if message["type"] == "message":
        print(f"Received: {message['data']}")
```

### Async version (FastAPI/asyncio — the pattern behind your WebSocket scaling coverage)

```python
import redis.asyncio as redis

r = redis.Redis(host="localhost", port=6379)
pubsub = r.pubsub()

async def listen():
    await pubsub.subscribe("notifications")
    async for message in pubsub.listen():
        if message["type"] == "message":
            await broadcast_to_websocket_clients(message["data"])
```

This is exactly the mechanism your `03_scaling_with_redis_pubsub.md` (in
`13_WebSocket_SSE/`) uses to fan out WebSocket messages across multiple
FastAPI server instances — Pub/Sub's fire-and-forget nature is actually
FINE there, because WebSocket connections are themselves ephemeral/live-only
— there's no need to replay a chat message to someone who wasn't connected
when it was sent.

---

## Pattern subscriptions — `PSUBSCRIBE`

```bash
# Subscribe to all channels matching a glob pattern
PSUBSCRIBE user.*.notifications

# Now receives messages published to:
# user.123.notifications, user.456.notifications, etc.
# without subscribing to each user's channel individually
```

```python
pubsub.psubscribe("user.*.notifications")
async for message in pubsub.listen():
    if message["type"] == "pmessage":
        channel = message["channel"]
        # extract user_id from channel name if needed
```

---

## Pub/Sub vs Streams — the actual interview comparison

| | **Pub/Sub** | **Streams** |
|---|---|---|
| Persistence | None — message exists only during `PUBLISH` | Persistent log, survives restarts (with AOF/RDB) |
| Delivery guarantee | None — offline subscribers get nothing | At-least-once, with consumer-group ACKs |
| Replay old messages | Impossible | Yes — `XRANGE`, re-read by ID |
| Multiple independent consumers of the SAME message | Yes, all subscribers get every message (broadcast) | Yes, but via consumer GROUPS — within a group, each message goes to only ONE consumer (load-balanced), not all |
| Overhead | Extremely low — no storage, no ID tracking | Higher — every message is stored and tracked until trimmed |
| Right for | Real-time broadcast where missing a message if you weren't listening is acceptable (live chat fan-out, cache invalidation signals, WebSocket scaling) | Anything needing durability/replay (task queues, event sourcing, audit logs) |

**The one-line answer to memorize:** "Pub/Sub is fire-and-forget broadcast
with zero persistence — fine for ephemeral real-time signals. Streams adds
persistence and consumer groups on top, at the cost of storage overhead —
use it when you can't afford to lose a message just because nobody was
listening at that exact moment."

---

## Common production gotcha — Pub/Sub during a Redis restart/failover

```
Redis Sentinel failover triggers a NEW master promotion.
Any Pub/Sub subscribers connected to the OLD master lose their subscription
entirely — Pub/Sub state is NOT replicated/failed-over, unlike data keys.
Clients must detect the disconnect and RE-SUBSCRIBE after reconnecting
to the new master.
```

This ties directly into your existing `07_sentinel_ha.md` coverage — worth
calling out explicitly since it's the kind of detail that causes silent
message loss in production if the client's reconnect logic doesn't also
re-issue the `SUBSCRIBE` commands.

---

## Interview Q&A

**Q: A subscriber was offline for 5 seconds during a network blip — do they get the messages published during that gap?**
A: No — Pub/Sub has zero persistence. Messages published while nobody
(or a temporarily-disconnected client) was subscribed are gone permanently.
If that's unacceptable, use Streams instead, where messages persist and can
be re-read by ID after reconnecting.

**Q: Can multiple consumers "share" the workload of processing Pub/Sub messages, like a queue?**
A: No — every subscriber to a channel gets EVERY message (it's a broadcast,
not a work queue). If you want load-balanced processing across multiple
workers, use Streams with a consumer group, where each message in the group
goes to exactly one consumer.

**Q: Why would you ever use Pub/Sub instead of Streams, given Streams is strictly more capable?**
A: Lower overhead (no storage/tracking per message) and simpler mental
model, for cases where losing a message due to nobody listening is
genuinely fine — real-time signals like WebSocket fan-out or cache
invalidation notifications, where the "message" is really just a live
trigger, not data you need to guarantee delivery of.

---

Related: `05_streams_consumer_groups.md` (the durable alternative this
compares against), `07_sentinel_ha.md` (the failover gotcha for active
subscriptions), [../../01_Year3-4_Mid/13_WebSocket_SSE/03_scaling_with_redis_pubsub.md](../../../01_Year3-4_Mid/13_WebSocket_SSE/03_scaling_with_redis_pubsub.md)
(Pub/Sub applied to WebSocket fan-out across server instances).
