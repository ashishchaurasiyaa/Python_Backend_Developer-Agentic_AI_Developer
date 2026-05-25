# 03 — Scaling WebSocket/SSE with Redis Pub/Sub

> The single-server real-time architecture breaks at the second server. You need a backplane. Redis Pub/Sub is the most common one.

---

## The Problem at Scale

```
Single server:
  Alice connects → Server A
  Bob connects   → Server A
  Alice sends message → Server A → broadcasts to Bob ✓

Two servers:
  Alice connects → Server A
  Bob connects   → Server B   ← different server!
  Alice sends message → Server A → Bob never receives ✗
```

Servers don't know about each other's connected clients.

---

## Solution Patterns

### 1. Redis Pub/Sub (most common)
### 2. Kafka (when you also need persistence/replay)
### 3. NATS (lightweight, modern)
### 4. PostgreSQL LISTEN/NOTIFY (simple, low-volume)
### 5. Centrifugo (dedicated real-time gateway)

We'll cover Redis Pub/Sub in depth here.

---

## Redis Pub/Sub Basics

```python
import redis.asyncio as redis

r = redis.from_url("redis://localhost", decode_responses=True)

# Publisher
await r.publish("channel-1", "Hello!")

# Subscriber
async def subscribe():
    pubsub = r.pubsub()
    await pubsub.subscribe("channel-1")
    async for msg in pubsub.listen():
        if msg["type"] == "message":
            print(f"Got: {msg['data']}")
```

**Key properties:**
- Fire-and-forget: no persistence; if subscriber offline, message lost.
- Fast: ~1M msg/sec.
- Pattern subscriptions: `pubsub.psubscribe("user:*")`.

---

## Architecture for WebSocket + Redis

```
                       ┌──────────────┐
                       │ Load Balancer│ (sticky sessions optional)
                       └──────┬───────┘
              ┌───────────────┼───────────────┐
              ▼               ▼               ▼
        ┌─────────┐     ┌─────────┐     ┌─────────┐
        │ Server A│     │ Server B│     │ Server C│
        │ Alice   │     │ Bob     │     │ Carol   │
        └────┬────┘     └────┬────┘     └────┬────┘
             │               │                │
             └───────┬───────┴────────────────┘
                     ▼
                ┌─────────┐
                │  Redis  │ pub/sub
                └─────────┘
```

Each app server subscribes to relevant Redis channels and forwards events to its local WS clients.

---

## Pattern: Per-User Channel

Each user has their own Redis channel. When event for user U arrives, publish to `user:U`. Whichever server holds user U's WS subscribes and forwards.

```python
class ConnectionManager:
    def __init__(self, redis_client):
        self.local_connections: dict[str, list[WebSocket]] = {}
        self.redis = redis_client
        self.pubsub = redis_client.pubsub()
        asyncio.create_task(self._listen())

    async def connect(self, user_id: str, ws: WebSocket):
        await ws.accept()
        if user_id not in self.local_connections:
            self.local_connections[user_id] = []
            await self.pubsub.subscribe(f"user:{user_id}")
        self.local_connections[user_id].append(ws)

    async def disconnect(self, user_id: str, ws: WebSocket):
        self.local_connections[user_id].remove(ws)
        if not self.local_connections[user_id]:
            del self.local_connections[user_id]
            await self.pubsub.unsubscribe(f"user:{user_id}")

    async def _listen(self):
        async for msg in self.pubsub.listen():
            if msg["type"] != "message": continue
            channel = msg["channel"]  # e.g., "user:123"
            user_id = channel.split(":")[1]
            data = msg["data"]

            # Forward to all connected WS for this user
            for ws in self.local_connections.get(user_id, []):
                try:
                    await ws.send_text(data)
                except Exception:
                    pass

manager = ConnectionManager(r)
```

### To send to a user from anywhere:
```python
await r.publish(f"user:123", json.dumps({"type": "new_message", "data": "..."}))
```

Works whether user is on Server A, B, or C — Redis routes to the right one.

---

## Pattern: Channel/Room Subscriptions

For group chat / live channels:

```python
# When user joins room
await pubsub.subscribe(f"room:{room_id}")

# When user posts message
await r.publish(f"room:{room_id}", json.dumps(message))
```

All servers with at least one user in that room subscribe to the Redis channel.

---

## Pattern: Channel Fan-Out

Sometimes you want broadcast to many:
- `system:announcements` → all online users.
- `tenant:{tid}:notifications` → all users in a tenant.

Subscribers self-register.

---

## Optimizations

### 1. Connection pooling
Each Server should keep a single pubsub connection, not per-user:
```python
pubsub = r.pubsub()
# subscribe to many channels via this one
```

### 2. Pattern subscriptions (psubscribe)
Subscribe to `user:*` if you want to listen for all users this server has:
```python
await pubsub.psubscribe("user:*")
```
But: matches ALL channels, even users not connected here → filter in app.

Better: explicit subscribe per actual user.

### 3. Lazy unsubscribe
Don't unsubscribe immediately when last user disconnects — they may reconnect quickly. Keep subscription for ~30s.

---

## Redis Cluster Considerations

Redis Pub/Sub doesn't propagate across cluster nodes by default!

```
Cluster:
  Node 1: publishes "user:123"
  Node 2: subscribed to "user:123"   ← won't get message
```

### Solutions:
1. **Redis 7+ sharded pub/sub** (`spublish`/`ssubscribe`) — uses CRC16 to keep channel pinned to one node.
2. **Run pub/sub on single Redis (not clustered)** — simple, scales to ~100K subs.
3. **Use NATS / Kafka** for huge scale.

---

## Persistence Concern

Redis Pub/Sub is fire-and-forget. If subscriber down for 5 seconds, those messages are lost.

### Options if you need durability:

#### Option A: Redis Streams (preferred)
Redis 5+ has persistent streams.

```python
# Publish
await r.xadd("stream:user:123", {"data": json.dumps(message)})

# Consume
last_id = "$"
while True:
    events = await r.xread({"stream:user:123": last_id}, block=5000)
    for stream, msgs in events:
        for msg_id, data in msgs:
            await ws.send_text(data["data"])
            last_id = msg_id
```

On reconnect, replay from `last_id`. No data loss.

#### Option B: Combine with DB
- Publish to Redis Pub/Sub for live delivery.
- Also persist to DB.
- On WS reconnect, fetch missed events from DB since `last_event_id`.

```python
# Send
await db.insert_event(user_id, msg)        # persist
await r.publish(f"user:{user_id}", json.dumps(msg))   # broadcast

# On WS connect with last_event_id
missed = await db.fetch_events_since(user_id, last_event_id)
for evt in missed:
    await ws.send_json(evt)
# Then subscribe to live channel...
```

#### Option C: Kafka
For high-throughput durable streams, use Kafka instead of Redis.

---

## Scaling Numbers (Real-World)

| Architecture | Concurrent connections |
|---|---|
| Single Python server | 1K-10K |
| Multiple Python servers + Redis | 100K-500K |
| Go/Rust servers + Redis | 1M+ |
| Centrifugo (dedicated) | 10M+ |
| Phoenix Channels (Elixir) | 2M per server |

For 1M+ concurrent: consider dedicated tier (Go server, Centrifugo, or custom).

---

## Centrifugo (Real-Time as a Service)

If you don't want to build this yourself:

```
App server → publishes to Centrifugo → Centrifugo → clients

Centrifugo handles:
  - WebSocket/SSE/HTTP-streaming
  - Auth via JWT
  - Sticky sessions
  - Pub/Sub with Redis backend
  - Presence
  - History
```

Open source, written in Go, scales massively.

Other options: Soketi (Pusher-compatible), Ably (managed), PubNub (managed).

---

## Presence System

"Who's online?" feature requires tracking active connections.

### Pattern: Redis sets

```python
# On connect
await r.sadd("online_users", user_id)
await r.expire(f"presence:{user_id}", 60)  # TTL

# Heartbeat every 30s
async def heartbeat(user_id):
    while ws_alive:
        await r.expire(f"presence:{user_id}", 60)
        await asyncio.sleep(30)

# On disconnect
await r.srem("online_users", user_id)

# Query
is_online = await r.sismember("online_users", user_id)
all_online = await r.smembers("online_users")
```

For "show online status to friends":
- Use Redis sorted set of last-active timestamps.
- Subscribe to `presence:{user_id}` channel for live updates.

---

## NATS — Alternative to Redis Pub/Sub

NATS is purpose-built for messaging:
- Lower latency.
- Pull-based subscribers (better backpressure).
- Subject hierarchies with wildcards.
- JetStream for persistence (like Kafka).

```python
import nats

nc = await nats.connect("nats://localhost:4222")
await nc.publish("user.123.msg", b"hello")

async def message_handler(msg):
    print(msg.data)

await nc.subscribe("user.>", cb=message_handler)
```

Use when:
- Redis Pub/Sub at scale insufficient.
- You want lighter-weight than Kafka.

---

## Choosing the Right Backplane

| Use case | Backplane |
|---|---|
| < 10K concurrent | Redis Pub/Sub (simple) |
| 10K-500K concurrent | Redis Pub/Sub + Streams for persistence |
| 500K-1M concurrent | NATS or Centrifugo |
| Need replay/durability | Kafka or Redis Streams |
| Massive scale (1M+) | Dedicated tier (Centrifugo, Go gateway) |

---

## Common Pitfalls

### 1. Pub/Sub on Redis Cluster
Doesn't broadcast across nodes. Use sharded or single-node.

### 2. Forgetting to unsubscribe
Memory leak in server.

### 3. No heartbeat
Half-open connections accumulate.

### 4. Pub/Sub for durable messaging
Lost messages on disconnect. Use Streams.

### 5. Same Redis for cache + pubsub at scale
Pub/Sub at high volume can stall command queue. Separate instances.

### 6. Routing via wildcards
`psubscribe("user:*")` matches all → unused traffic on each server.

---

## Production Monitoring

- WS connection count per server.
- Redis Pub/Sub message rate.
- Subscriber lag (for streams).
- Failed message deliveries.
- Re-subscriptions / churn rate.

Alerts:
- Connection count drops sharply.
- Redis pub/sub backlog growing.
- Reconnect storm.

---

## Real-World Examples

### Slack
Redis Pub/Sub + WebSocket gateway tier (Go). Persistent message store in Cassandra.

### Discord
Custom Elixir gateway servers (Phoenix Channels). Distributed via consistent hashing.

### Twitter (X)
Custom real-time backend; Redis Pub/Sub for some flows.

### Linear / Notion
WebSocket + Pub/Sub for collaborative editing CRDT messages.

---

## TL;DR

- Single server WS → multi-server requires a backplane.
- Redis Pub/Sub is the most common choice.
- One channel per user (or per room).
- Each server subscribes to channels for users connected to it.
- Redis Cluster: use sharded pub/sub or single Redis.
- For durability: combine with DB or use Redis Streams.
- For scale beyond 500K: NATS, Centrifugo, Kafka, or custom.
- Presence: Redis sets + TTL.
