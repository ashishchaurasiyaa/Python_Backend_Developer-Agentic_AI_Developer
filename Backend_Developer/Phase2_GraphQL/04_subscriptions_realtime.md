# 04 — GraphQL Subscriptions & Real-Time

> Server pushes data to clients over a long-lived connection. Built on WebSocket (or SSE).

---

## When to use Subscriptions

- Chat applications.
- Live dashboards (real-time metrics).
- Collaborative editing notifications.
- Order/payment status updates.
- Real-time game events.
- Stock prices, sports scores.

**Don't use for:**
- Simple polling-suffices cases (notifications every 5 min).
- One-off events (use webhook to server).
- File downloads.

---

## Schema

```graphql
type Subscription {
  newMessage(channelId: ID!): Message!
  orderStatus(orderId: ID!): OrderStatus!
  liveMetrics: Metric!
}
```

Subscription resolvers return an `AsyncGenerator` — yields values over time.

---

## Strawberry Subscription Implementation

```python
import strawberry
from typing import AsyncGenerator
import asyncio

@strawberry.type
class Message:
    id: strawberry.ID
    text: str
    author: str

@strawberry.type
class Subscription:
    @strawberry.subscription
    async def new_message(
        self,
        channel_id: strawberry.ID,
        info
    ) -> AsyncGenerator[Message, None]:
        # Subscribe to internal pub/sub channel
        async for msg in pubsub.subscribe(f"channel:{channel_id}"):
            yield Message(id=msg.id, text=msg.text, author=msg.author)

schema = strawberry.Schema(
    query=Query,
    mutation=Mutation,
    subscription=Subscription,
)
```

---

## Transport Protocols

### WebSocket (graphql-ws / graphql-transport-ws)
- Bi-directional.
- Industry standard for subscriptions.
- Server-side state per connection.

### Server-Sent Events (SSE)
- Server → Client only.
- Reconnects automatically.
- Simpler than WS.
- Strawberry supports via experimental transport.

### HTTP/2 Streaming
- Less common.

**Default:** Use `graphql-transport-ws` (modern WS protocol).

---

## FastAPI WebSocket Wire-up

```python
from strawberry.fastapi import GraphQLRouter
from fastapi import FastAPI

graphql_app = GraphQLRouter(
    schema,
    subscription_protocols=[
        "graphql-transport-ws",
        "graphql-ws",  # legacy support
    ]
)

app = FastAPI()
app.include_router(graphql_app, prefix="/graphql")
# WS automatically at /graphql with ws:// protocol upgrade
```

---

## Client-Side (JavaScript)

```javascript
import { createClient } from 'graphql-ws';

const client = createClient({
  url: 'ws://localhost:8000/graphql',
  connectionParams: { authToken: 'jwt-...' }
});

const unsubscribe = client.subscribe(
  {
    query: `subscription($id: ID!) { newMessage(channelId: $id) { id text } }`,
    variables: { id: 'chat-1' }
  },
  {
    next: (data) => console.log('new msg', data),
    error: (err) => console.error(err),
    complete: () => console.log('done'),
  }
);
```

---

## Pub/Sub Backplane

For single-process apps, in-memory pub/sub works:

```python
# Simple in-memory pub/sub (single process only)
from collections import defaultdict
import asyncio

class PubSub:
    def __init__(self):
        self.subscribers: dict[str, list[asyncio.Queue]] = defaultdict(list)

    async def subscribe(self, channel: str):
        q = asyncio.Queue()
        self.subscribers[channel].append(q)
        try:
            while True:
                yield await q.get()
        finally:
            self.subscribers[channel].remove(q)

    async def publish(self, channel: str, msg):
        for q in self.subscribers[channel]:
            await q.put(msg)

pubsub = PubSub()
```

**Production:** Use Redis pub/sub, NATS, or Kafka so multiple server instances share state.

### Redis-backed pub/sub

```python
import redis.asyncio as redis
import json

class RedisPubSub:
    def __init__(self, redis_url):
        self.redis = redis.from_url(redis_url, decode_responses=True)

    async def subscribe(self, channel: str):
        pubsub = self.redis.pubsub()
        await pubsub.subscribe(channel)
        try:
            async for msg in pubsub.listen():
                if msg["type"] == "message":
                    yield json.loads(msg["data"])
        finally:
            await pubsub.unsubscribe(channel)
            await pubsub.close()

    async def publish(self, channel: str, msg):
        await self.redis.publish(channel, json.dumps(msg))

pubsub = RedisPubSub("redis://localhost")
```

In subscription resolver:
```python
@strawberry.subscription
async def new_message(self, channel_id: ID, info):
    async for msg in pubsub.subscribe(f"chan:{channel_id}"):
        yield Message(**msg)
```

In mutation:
```python
@strawberry.mutation
async def send_message(self, channel_id: ID, text: str) -> Message:
    msg = await db.insert_message(channel_id, text)
    await pubsub.publish(f"chan:{channel_id}", {
        "id": msg.id, "text": msg.text, "author": msg.author
    })
    return msg
```

---

## Scaling Subscriptions

### Single-process
Easy. In-memory pub/sub works.

### Multi-process / Multi-server
Need a shared pub/sub: Redis / NATS / Kafka.

Each app server subscribes to Redis channel; pushes to all WS clients connected to that server.

### High-scale (millions of concurrent WS)
- Sharded pub/sub by channel.
- Dedicated WS gateway tier (e.g., centrifugo).
- GraphQL subscription server separate from API server.

---

## Authentication

WebSocket auth via `connectionParams`:

```python
async def get_context_ws(connection_init_payload):
    token = connection_init_payload.get("authToken")
    user = await verify_jwt(token)
    if not user:
        raise ConnectionError("Unauthorized")
    return {"user": user}

graphql_app = GraphQLRouter(
    schema,
    context_getter=get_context,
    websocket_context_getter=get_context_ws,
)
```

Per-subscription auth:
```python
@strawberry.subscription
async def admin_metrics(self, info) -> AsyncGenerator[Metric, None]:
    if info.context["user"].role != "admin":
        raise PermissionError("Admin only")
    async for m in metrics_stream():
        yield m
```

---

## Connection Lifecycle

```
1. Client opens WS → server accepts
2. Client sends connection_init { authToken: ... }
3. Server validates, sends connection_ack
4. Client sends subscribe { id, query, variables }
5. Server begins streaming next messages
6. Client sends complete → server stops that subscription
7. Client closes WS → server cleans up
```

---

## Heartbeat / Keep-Alive

Detect dead connections. graphql-transport-ws supports `ping/pong` frames.

Server config:
```python
GraphQLRouter(
    schema,
    keep_alive=True,
    keep_alive_interval=30  # seconds
)
```

Browsers/clients respond automatically.

---

## Resource Limits

Each WS = a long-lived connection eating server resources.

**Limit per server:**
- Max WS connections (e.g., 10K per process).
- Max subscriptions per connection (e.g., 50).
- Idle timeout (close after N minutes no activity).

```python
async def new_message(self, info, channel_id):
    user = info.context["user"]
    if subscription_count(user.id) > 50:
        raise GraphQLError("Subscription limit exceeded")
    ...
```

---

## Filtering in Subscriptions

Don't push every event to every subscriber.

```python
@strawberry.subscription
async def new_message(
    self,
    channel_id: ID,
    only_mentions: bool = False,
    info
) -> AsyncGenerator[Message, None]:
    user = info.context["user"]
    async for msg in pubsub.subscribe(f"chan:{channel_id}"):
        if only_mentions and user.id not in msg.mentioned_user_ids:
            continue
        yield Message(**msg)
```

Better: pre-filter at pub/sub level if possible.

---

## Subscriptions vs Polling

| | Subscription | Polling |
|---|---|---|
| Latency | Real-time | Poll interval |
| Server load | Connection per client | Periodic requests |
| Complexity | High (pub/sub, WS) | Low |
| Resilience | Need reconnect logic | Stateless retry |
| Best for | Push-required (chat) | Eventually-consistent (notif) |

**Polling can be smarter:** SWR / React Query patterns auto-poll on focus with backoff.

---

## Subscriptions vs Webhooks

| | Subscription | Webhook |
|---|---|---|
| Direction | Server → Client (WS) | Server → Server (HTTP) |
| Use case | UI updates | Third-party integrations |
| Stateful | Yes | No |

Webhooks are for B2B (Stripe → your server). Subscriptions are for UX (your server → user's browser).

---

## Production Considerations

### Backpressure
Slow client = queue fills up.

```python
@strawberry.subscription
async def stream(self, info):
    queue = asyncio.Queue(maxsize=100)   # bounded
    async def producer():
        async for msg in source:
            try:
                queue.put_nowait(msg)
            except asyncio.QueueFull:
                pass  # drop or close subscription
    asyncio.create_task(producer())
    while True:
        yield await queue.get()
```

### Resumability
Client reconnects: how to catch up on missed events?

- Track last event ID per subscription.
- Re-fetch from DB between last seen and now on reconnect.
- Or accept lossy semantics.

### Schema validation
Subscriptions are part of the schema. Document carefully — clients have to handle reconnection, ordering.

---

## Testing

```python
@pytest.mark.asyncio
async def test_subscription():
    async def gen_messages():
        await pubsub.publish("chan:1", {"id": "1", "text": "hi"})
        await asyncio.sleep(0.01)
        await pubsub.publish("chan:1", {"id": "2", "text": "bye"})

    async with schema.subscribe(
        "subscription($id: ID!) { newMessage(channelId: $id) { id text } }",
        variable_values={"id": "1"},
        context_value=ctx
    ) as gen:
        asyncio.create_task(gen_messages())
        msgs = []
        async for r in gen:
            msgs.append(r.data["newMessage"])
            if len(msgs) == 2: break
        assert msgs == [{"id": "1", "text": "hi"}, {"id": "2", "text": "bye"}]
```

---

## TL;DR

- Subscription = `AsyncGenerator` yielding values over time.
- WebSocket transport via graphql-transport-ws protocol.
- Single-process: in-memory pub/sub.
- Multi-process: Redis/NATS/Kafka backplane.
- Auth via connectionParams + connection_init.
- Limit subs per connection; bounded queues for backpressure.
- For pure server→client, SSE is simpler than WS.
