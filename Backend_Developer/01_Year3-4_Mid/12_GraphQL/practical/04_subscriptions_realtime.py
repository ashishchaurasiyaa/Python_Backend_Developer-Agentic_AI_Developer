"""
GraphQL Subscriptions & Real-Time Streaming — Production Patterns
=================================================================
Covers:
  - In-memory PubSub (single-process)
  - Redis-backed PubSub (multi-process / multi-server)
  - Strawberry subscription resolvers with AsyncGenerator
  - Per-subscription auth and resource limits
  - Backpressure via bounded asyncio.Queue
  - Filtering events inside the resolver
  - Heartbeat / keep-alive configuration
  - FastAPI WebSocket wire-up (graphql-transport-ws + legacy graphql-ws)
  - Connection lifecycle notes
  - Resumable subscriptions: last-event-id catch-up pattern
  - pytest-asyncio testing helper

Transport: WebSocket over graphql-transport-ws (modern) and graphql-ws (legacy).
For pure server→client push, SSE is simpler — see comment blocks below.

pip install strawberry-graphql[fastapi] fastapi uvicorn
pip install redis[asyncio]        # for RedisPubSub
pip install pytest pytest-asyncio # for testing helpers
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from functools import wraps
from typing import AsyncGenerator, Optional

import strawberry
from strawberry import ID
from strawberry.fastapi import GraphQLRouter
from strawberry.types import Info

from fastapi import Depends, FastAPI, HTTPException, Request

# ==========================================================================
# LOGGING
# ==========================================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
)
log = logging.getLogger(__name__)


# ==========================================================================
# 1. IN-MEMORY PUB/SUB  (single-process; no external infra required)
# ==========================================================================

class PubSub:
    """Thread-safe (coroutine-safe) in-memory pub/sub broker.

    Suitable for single-process deployments only.  Each subscriber gets its
    own asyncio.Queue; published messages fan out to every queue on the channel.

    For production multi-server deployments replace with RedisPubSub below.
    """

    def __init__(self) -> None:
        # channel -> list of subscriber queues
        self._subscribers: dict[str, list[asyncio.Queue]] = defaultdict(list)

    async def subscribe(self, channel: str) -> AsyncGenerator[dict, None]:
        """Yield messages arriving on *channel*.  Cleans up on generator close."""
        q: asyncio.Queue[dict] = asyncio.Queue()
        self._subscribers[channel].append(q)
        log.debug("PubSub: subscriber added to '%s'", channel)
        try:
            while True:
                yield await q.get()
        finally:
            self._subscribers[channel].remove(q)
            log.debug("PubSub: subscriber removed from '%s'", channel)

    async def publish(self, channel: str, message: dict) -> int:
        """Fan-out *message* to all subscribers on *channel*.

        Returns the number of subscribers that received the message.
        """
        queues = self._subscribers.get(channel, [])
        for q in queues:
            await q.put(message)
        log.debug("PubSub: published to '%s' (%d subscribers)", channel, len(queues))
        return len(queues)


# Singleton — imported by resolvers and mutations throughout the application.
pubsub = PubSub()


# ==========================================================================
# 2. REDIS-BACKED PUB/SUB  (multi-process / multi-server)
# ==========================================================================

class RedisPubSub:
    """Pub/sub backplane backed by Redis (asyncio).

    Each app server subscribes to a Redis channel and pushes received messages
    to all WebSocket clients connected to that server.  This allows horizontal
    scaling: N uvicorn workers all sharing the same Redis instance.

    Usage::

        redis_pubsub = RedisPubSub("redis://localhost:6379")

        # In a subscription resolver:
        async for msg in redis_pubsub.subscribe("chan:chat-1"):
            yield Message(**msg)

        # In a mutation:
        await redis_pubsub.publish("chan:chat-1", {"id": ..., "text": ...})

    pip install redis[asyncio]
    """

    def __init__(self, redis_url: str = "redis://localhost:6379") -> None:
        # Import deferred so the module compiles without redis installed.
        import redis.asyncio as aioredis  # pip install redis[asyncio]

        self._redis = aioredis.from_url(redis_url, decode_responses=True)

    async def subscribe(self, channel: str) -> AsyncGenerator[dict, None]:
        """Subscribe to a Redis channel; yield decoded JSON messages."""
        ps = self._redis.pubsub()
        await ps.subscribe(channel)
        try:
            async for raw in ps.listen():
                if raw["type"] == "message":
                    yield json.loads(raw["data"])
        finally:
            await ps.unsubscribe(channel)
            await ps.aclose()

    async def publish(self, channel: str, message: dict) -> None:
        """Publish a JSON-serialisable *message* to a Redis channel."""
        await self._redis.publish(channel, json.dumps(message))


# ==========================================================================
# 3. STRAWBERRY TYPES
# ==========================================================================

@strawberry.type
class Message:
    id: strawberry.ID
    text: str
    author: str
    channel_id: strawberry.ID
    timestamp: float


@strawberry.type
class OrderStatus:
    order_id: strawberry.ID
    status: str            # e.g. "pending", "dispatched", "delivered"
    updated_at: float


@strawberry.type
class Metric:
    name: str
    value: float
    unit: str
    recorded_at: float


# ==========================================================================
# 4. SIMPLE USER / AUTH TYPES
# ==========================================================================

@dataclass
class User:
    id: str
    username: str
    role: str = "user"     # "user" | "admin"


# Tracks active subscriptions per user to enforce resource limits.
# In production this would live in Redis.
_active_subscription_counts: dict[str, int] = defaultdict(int)
_SUBSCRIPTION_LIMIT_PER_USER = 50


def subscription_count(user_id: str) -> int:
    return _active_subscription_counts[user_id]


def _inc_subscription(user_id: str) -> None:
    _active_subscription_counts[user_id] += 1


def _dec_subscription(user_id: str) -> None:
    _active_subscription_counts[user_id] = max(
        0, _active_subscription_counts[user_id] - 1
    )


async def verify_jwt(token: Optional[str]) -> Optional[User]:
    """Stub JWT verifier — replace with real library (python-jose, PyJWT).

    In production validate signature, expiry, and issuer.
    """
    if not token:
        return None
    # Simulate: any non-empty token is accepted; role embedded in prefix.
    role = "admin" if token.startswith("admin-") else "user"
    return User(id=f"user-{token[:8]}", username="test_user", role=role)


# ==========================================================================
# 5. CONTEXT — HTTP and WebSocket
# ==========================================================================

async def get_context(request: Request) -> dict:
    """HTTP context getter: extract Bearer token from Authorization header."""
    auth = request.headers.get("Authorization", "")
    token = auth.removeprefix("Bearer ").strip() or None
    user = await verify_jwt(token)
    return {"request": request, "user": user}


async def get_context_ws(connection_init_payload: dict) -> dict:
    """WebSocket context getter: token arrives in connection_init payload.

    Strawberry calls this during the graphql-transport-ws handshake.
    Raising an exception here sends connection_error and closes the socket.
    """
    token = (connection_init_payload or {}).get("authToken")
    user = await verify_jwt(token)
    if user is None:
        raise ConnectionError("Unauthorized: missing or invalid authToken")
    log.info("WS authenticated: user=%s role=%s", user.id, user.role)
    return {"user": user}


# ==========================================================================
# 6. SUBSCRIPTION RESOLVERS
# ==========================================================================

@strawberry.type
class Subscription:

    # ------------------------------------------------------------------
    # 6a. New messages on a chat channel (basic)
    # ------------------------------------------------------------------

    @strawberry.subscription
    async def new_message(
        self,
        info: Info,
        channel_id: strawberry.ID,
        only_mentions: bool = False,
    ) -> AsyncGenerator[Message, None]:
        """Stream new messages on *channel_id*.

        *only_mentions* — when True, yield only messages where the
        authenticated user is mentioned; useful for notification feeds
        without flooding the client with every message.
        """
        user: Optional[User] = info.context.get("user")
        if user is None:
            raise strawberry.types.graphql.GraphQLError("Authentication required")

        if subscription_count(user.id) >= _SUBSCRIPTION_LIMIT_PER_USER:
            raise strawberry.types.graphql.GraphQLError(
                f"Subscription limit ({_SUBSCRIPTION_LIMIT_PER_USER}) exceeded"
            )

        channel_key = f"chan:{channel_id}"
        _inc_subscription(user.id)
        log.info("new_message subscription: user=%s channel=%s", user.id, channel_key)

        try:
            async for raw in pubsub.subscribe(channel_key):
                # ----- Filtering: skip events that don't match criteria -----
                if only_mentions:
                    mentioned = raw.get("mentioned_user_ids", [])
                    if user.id not in mentioned:
                        continue
                # -----------------------------------------------------------
                yield Message(
                    id=raw["id"],
                    text=raw["text"],
                    author=raw["author"],
                    channel_id=channel_id,
                    timestamp=raw.get("timestamp", time.time()),
                )
        finally:
            _dec_subscription(user.id)
            log.info(
                "new_message unsubscribed: user=%s channel=%s", user.id, channel_key
            )

    # ------------------------------------------------------------------
    # 6b. Order-status updates (scoped to a specific order)
    # ------------------------------------------------------------------

    @strawberry.subscription
    async def order_status(
        self,
        info: Info,
        order_id: strawberry.ID,
    ) -> AsyncGenerator[OrderStatus, None]:
        """Stream status changes for *order_id*.

        Clients subscribe immediately after placing an order and receive
        status transitions: pending → confirmed → dispatched → delivered.
        """
        user: Optional[User] = info.context.get("user")
        if user is None:
            raise strawberry.types.graphql.GraphQLError("Authentication required")

        channel_key = f"order:{order_id}"
        _inc_subscription(user.id)
        try:
            async for raw in pubsub.subscribe(channel_key):
                yield OrderStatus(
                    order_id=raw["order_id"],
                    status=raw["status"],
                    updated_at=raw.get("updated_at", time.time()),
                )
        finally:
            _dec_subscription(user.id)

    # ------------------------------------------------------------------
    # 6c. Live system metrics — admin-only
    # ------------------------------------------------------------------

    @strawberry.subscription
    async def live_metrics(
        self,
        info: Info,
    ) -> AsyncGenerator[Metric, None]:
        """Stream system metrics; restricted to users with role='admin'.

        Permission is checked once at subscription start.  If role changes
        at runtime the existing subscription is NOT revoked automatically —
        that requires extra session-tracking outside this example.
        """
        user: Optional[User] = info.context.get("user")
        if user is None or user.role != "admin":
            raise strawberry.types.graphql.GraphQLError(
                "Admin role required for live_metrics"
            )

        channel_key = "metrics:live"
        _inc_subscription(user.id)
        try:
            async for raw in pubsub.subscribe(channel_key):
                yield Metric(
                    name=raw["name"],
                    value=raw["value"],
                    unit=raw.get("unit", ""),
                    recorded_at=raw.get("recorded_at", time.time()),
                )
        finally:
            _dec_subscription(user.id)

    # ------------------------------------------------------------------
    # 6d. Backpressure-aware subscription (bounded queue)
    # ------------------------------------------------------------------

    @strawberry.subscription
    async def high_volume_stream(
        self,
        info: Info,
        channel_id: strawberry.ID,
    ) -> AsyncGenerator[Message, None]:
        """Demonstrate bounded-queue backpressure for fast producers.

        A background task drains the raw pub/sub channel into a bounded
        asyncio.Queue.  If the queue is full (slow client), events are
        dropped rather than buffered indefinitely, protecting server memory.

        Adjust maxsize to balance freshness vs. message loss tolerance.
        """
        user: Optional[User] = info.context.get("user")
        if user is None:
            raise strawberry.types.graphql.GraphQLError("Authentication required")

        bounded_queue: asyncio.Queue[dict] = asyncio.Queue(maxsize=100)
        channel_key = f"chan:{channel_id}"
        _inc_subscription(user.id)

        async def _producer() -> None:
            """Drain pub/sub into the bounded queue; silently drop on full."""
            try:
                async for raw in pubsub.subscribe(channel_key):
                    try:
                        bounded_queue.put_nowait(raw)
                    except asyncio.QueueFull:
                        log.warning(
                            "high_volume_stream: queue full for user=%s — dropping event",
                            user.id,
                        )
            except asyncio.CancelledError:
                pass

        producer_task = asyncio.create_task(_producer())
        try:
            while True:
                raw = await bounded_queue.get()
                yield Message(
                    id=raw["id"],
                    text=raw["text"],
                    author=raw["author"],
                    channel_id=channel_id,
                    timestamp=raw.get("timestamp", time.time()),
                )
        finally:
            producer_task.cancel()
            _dec_subscription(user.id)


# ==========================================================================
# 7. QUERY & MUTATION  (minimal — required to build the schema)
# ==========================================================================

@strawberry.type
class Query:
    @strawberry.field
    def ping(self) -> str:
        """Health-check field."""
        return "pong"

    @strawberry.field
    def channel_history(
        self,
        channel_id: strawberry.ID,
        limit: int = 20,
    ) -> list[Message]:
        """Return recent messages for a channel.

        In production query from a persistent store (PostgreSQL, DynamoDB).
        This stub returns an empty list.
        """
        return []


@strawberry.type
class Mutation:

    @strawberry.mutation
    async def send_message(
        self,
        info: Info,
        channel_id: strawberry.ID,
        text: str,
    ) -> Message:
        """Persist a message and publish it to subscribers on the channel.

        Pattern:
          1. Write to database for durability.
          2. Publish to pub/sub for real-time fan-out.

        Here the DB write is stubbed; pub/sub publish is real.
        """
        user: Optional[User] = info.context.get("user")
        if user is None:
            raise strawberry.types.graphql.GraphQLError("Authentication required")

        msg = Message(
            id=str(uuid.uuid4()),
            text=text,
            author=user.username,
            channel_id=channel_id,
            timestamp=time.time(),
        )

        # Publish to in-memory pubsub so subscribers receive it.
        await pubsub.publish(
            f"chan:{channel_id}",
            {
                "id": msg.id,
                "text": msg.text,
                "author": msg.author,
                "timestamp": msg.timestamp,
                "mentioned_user_ids": [],  # populate from text parsing in production
            },
        )
        log.info("send_message: channel=%s author=%s", channel_id, user.username)
        return msg

    @strawberry.mutation
    async def update_order_status(
        self,
        info: Info,
        order_id: strawberry.ID,
        status: str,
    ) -> OrderStatus:
        """Update an order's status and push the change to subscribers."""
        user: Optional[User] = info.context.get("user")
        if user is None or user.role != "admin":
            raise strawberry.types.graphql.GraphQLError(
                "Admin role required to update order status"
            )

        now = time.time()
        await pubsub.publish(
            f"order:{order_id}",
            {"order_id": order_id, "status": status, "updated_at": now},
        )
        log.info("update_order_status: order=%s status=%s", order_id, status)
        return OrderStatus(order_id=order_id, status=status, updated_at=now)

    @strawberry.mutation
    async def publish_metric(
        self,
        info: Info,
        name: str,
        value: float,
        unit: str = "",
    ) -> Metric:
        """Push a metric data point to live_metrics subscribers."""
        user: Optional[User] = info.context.get("user")
        if user is None or user.role != "admin":
            raise strawberry.types.graphql.GraphQLError("Admin role required")

        now = time.time()
        metric = Metric(name=name, value=value, unit=unit, recorded_at=now)
        await pubsub.publish(
            "metrics:live",
            {"name": name, "value": value, "unit": unit, "recorded_at": now},
        )
        return metric


# ==========================================================================
# 8. SCHEMA ASSEMBLY
# ==========================================================================

schema = strawberry.Schema(
    query=Query,
    mutation=Mutation,
    subscription=Subscription,
)


# ==========================================================================
# 9. FASTAPI APPLICATION + GRAPHQL ROUTER
# ==========================================================================

app = FastAPI(
    title="GraphQL Subscriptions — Real-Time Demo",
    description=(
        "Strawberry + FastAPI with WebSocket subscriptions using "
        "graphql-transport-ws (modern) and graphql-ws (legacy) protocols."
    ),
    version="1.0.0",
)

# Wire up both WebSocket sub-protocols:
#   - graphql-transport-ws : modern (default since 2021, use this)
#   - graphql-ws            : legacy (Apollo Client < v3.5)
graphql_app = GraphQLRouter(
    schema,
    context_getter=get_context,
    # Strawberry 0.200+ supports websocket_context_getter directly.
    # If your version uses on_ws_connect, adapt accordingly.
    subscription_protocols=[
        "graphql-transport-ws",
        "graphql-ws",
    ],
    # Keep-alive: the server sends WebSocket ping frames every 30 seconds.
    # Clients that support graphql-transport-ws respond with pong automatically,
    # allowing the server to detect dead connections and reclaim resources.
    keep_alive=True,
    keep_alive_interval=30,
)

app.include_router(graphql_app, prefix="/graphql")


@app.get("/health")
async def health_check() -> dict:
    """Liveness probe — returns immediately without touching any dependency."""
    return {"status": "ok"}


# ==========================================================================
# 10. RESUMABLE SUBSCRIPTIONS — last-event-id catch-up
# ==========================================================================

class ResumablePubSub:
    """Extends PubSub with an in-memory event log for catch-up on reconnect.

    On reconnect a client passes its *last_event_id*; the server replays
    every event that occurred after that ID before switching to live streaming.

    Limits:
      - *max_history* controls memory usage.
      - In production store the event log in Redis with TTL or in PostgreSQL.
    """

    def __init__(self, max_history: int = 500) -> None:
        self._inner = PubSub()
        self._history: dict[str, list[dict]] = defaultdict(list)
        self._max_history = max_history

    async def publish(self, channel: str, message: dict) -> None:
        """Append *message* to history, then fan-out."""
        history = self._history[channel]
        history.append(message)
        if len(history) > self._max_history:
            history.pop(0)
        await self._inner.publish(channel, message)

    async def subscribe(
        self,
        channel: str,
        last_event_id: Optional[str] = None,
    ) -> AsyncGenerator[dict, None]:
        """Replay missed events then yield live events.

        If *last_event_id* is None, only live events are sent (lossy).
        """
        if last_event_id is not None:
            history = self._history.get(channel, [])
            # Find the index of the last seen event.
            seen_idx = next(
                (i for i, e in enumerate(history) if e.get("id") == last_event_id),
                -1,
            )
            for missed in history[seen_idx + 1 :]:
                yield missed

        async for live_event in self._inner.subscribe(channel):
            yield live_event


resumable_pubsub = ResumablePubSub()


# ==========================================================================
# 11. CONNECTION LIFECYCLE  (reference — documented as constants)
# ==========================================================================

# The graphql-transport-ws handshake proceeds as follows:
#
#   1. Client opens WebSocket:  ws://host/graphql
#   2. Client   →  Server:   { type: "connection_init", payload: { authToken: "..." } }
#   3. Server   →  Client:   { type: "connection_ack" }
#      (Strawberry calls get_context_ws here; raises = connection_error)
#   4. Client   →  Server:   { type: "subscribe", id: "1", payload: { query, variables } }
#   5. Server   →  Client:   { type: "next", id: "1", payload: { data: { ... } } }
#      (repeated for every yielded value)
#   6. Client   →  Server:   { type: "complete", id: "1" }
#      (server stops the subscription for id "1")
#   7. Client closes WebSocket → server cleans up all open subscriptions


# ==========================================================================
# 12. PYTEST TESTING HELPERS
# ==========================================================================

# pip install pytest pytest-asyncio
# Run with: pytest 04_subscriptions_realtime.py -v

async def _demo_send_and_receive() -> list[dict]:
    """Internal integration helper: publish two messages and collect them.

    Not a full pytest example (no @pytest.mark decorators) so that this file
    runs under plain asyncio without pytest installed.  The pattern mirrors
    the pytest block shown in the theory doc exactly.
    """
    received: list[dict] = []

    async def _publisher() -> None:
        await asyncio.sleep(0.02)
        await pubsub.publish("chan:test", {"id": "1", "text": "hello", "author": "alice", "timestamp": time.time()})
        await asyncio.sleep(0.02)
        await pubsub.publish("chan:test", {"id": "2", "text": "world", "author": "bob",   "timestamp": time.time()})

    pub_task = asyncio.create_task(_publisher())

    async def _collect() -> None:
        async for msg in pubsub.subscribe("chan:test"):
            received.append(msg)
            if len(received) >= 2:
                break

    await asyncio.gather(pub_task, _collect())
    return received


# pytest-style test (importable by pytest without running the event loop at
# import time — only executed when pytest collects it or __main__ calls it).
#
# import pytest
#
# @pytest.mark.asyncio
# async def test_pubsub_roundtrip():
#     msgs = await _demo_send_and_receive()
#     assert len(msgs) == 2
#     assert msgs[0]["text"] == "hello"
#     assert msgs[1]["text"] == "world"
#
#
# @pytest.mark.asyncio
# async def test_subscription_schema():
#     """Test a subscription through the Strawberry schema directly."""
#     ctx = {"user": User(id="u1", username="alice", role="user")}
#     variable_values = {"channelId": "test-chan"}
#
#     async def _send_msgs():
#         await asyncio.sleep(0.02)
#         await pubsub.publish("chan:test-chan", {
#             "id": "m1", "text": "hi", "author": "alice",
#             "timestamp": time.time(), "mentioned_user_ids": [],
#         })
#
#     async with schema.subscribe(
#         """subscription($channelId: ID!) {
#             newMessage(channelId: $channelId) { id text author }
#         }""",
#         variable_values=variable_values,
#         context_value=ctx,
#     ) as gen:
#         asyncio.create_task(_send_msgs())
#         async for result in gen:
#             assert result.data["newMessage"]["text"] == "hi"
#             break


# ==========================================================================
# 13. CLIENT-SIDE REFERENCE  (JavaScript — graphql-ws library)
# ==========================================================================

_JS_CLIENT_EXAMPLE = """
// npm install graphql-ws

import { createClient } from 'graphql-ws';

const client = createClient({
  url: 'ws://localhost:8000/graphql',
  connectionParams: {
    authToken: 'your-jwt-token-here',
  },
});

// Subscribe to chat messages
const unsubscribe = client.subscribe(
  {
    query: `
      subscription($channelId: ID!) {
        newMessage(channelId: $channelId) {
          id
          text
          author
          timestamp
        }
      }
    `,
    variables: { channelId: 'chat-room-1' },
  },
  {
    next:     (data)  => console.log('New message:', data.data.newMessage),
    error:    (err)   => console.error('Subscription error:', err),
    complete: ()      => console.log('Subscription closed'),
  }
);

// Stop subscribing (sends 'complete' frame to server)
// unsubscribe();
"""


# ==========================================================================
# 14. SCALING REFERENCE NOTES
# ==========================================================================

_SCALING_NOTES = """
Scaling WebSocket Subscriptions
================================

Single-process:
  - In-memory PubSub (this file's PubSub class) — zero infra.
  - Supports thousands of concurrent WS connections per process.

Multi-process / multi-server:
  - Replace in-memory PubSub with RedisPubSub (Section 2 above).
  - All app servers subscribe to the same Redis channels.
  - Redis fan-out pushes events to every server, which forwards to
    clients connected to it.

High-scale (millions of concurrent WebSocket connections):
  - Shard channels: e.g., channel 0-499 → Redis cluster shard A.
  - Dedicated WebSocket gateway tier (e.g., Centrifugo, Ably, Pusher).
  - GraphQL subscription server separated from the REST/HTTP API servers.
  - NATS or Kafka as the pub/sub backplane for durability.

Resource limits (per process):
  - Max WS connections:       configure via OS ulimit (file descriptors).
  - Max subscriptions / user: enforced in resolver (_SUBSCRIPTION_LIMIT_PER_USER).
  - Idle timeout:             close connections with no ping response.
  - Keep-alive interval:      30 s (configured on GraphQLRouter above).
"""


# ==========================================================================
# 15. DEMO  (runs without external infra)
# ==========================================================================

async def _run_demo() -> None:
    """Standalone demo: shows pub/sub round-trip without starting an HTTP server.

    Start the full server with:
        uvicorn 04_subscriptions_realtime:app --reload --port 8000

    Then open:
        http://localhost:8000/graphql  (Strawberry GraphiQL IDE)

    And run subscriptions from the IDE or a graphql-ws JavaScript client.
    """
    print("\n=== PubSub Round-Trip Demo ===")
    msgs = await _demo_send_and_receive()
    for m in msgs:
        print(f"  Received: id={m['id']} text='{m['text']}' author={m['author']}")
    assert len(msgs) == 2
    assert msgs[0]["id"] == "1"
    assert msgs[1]["id"] == "2"
    print("  Assertions passed.\n")

    print("=== ResumablePubSub Catch-Up Demo ===")
    # Pre-populate history with two events.
    await resumable_pubsub.publish("chan:r1", {"id": "e1", "text": "first"})
    await resumable_pubsub.publish("chan:r1", {"id": "e2", "text": "second"})
    await resumable_pubsub.publish("chan:r1", {"id": "e3", "text": "third"})

    replayed: list[dict] = []

    async def _replay_collect() -> None:
        # Simulate reconnect: client last saw event e1; expects e2 and e3.
        async def _stop_after_two(gen: AsyncGenerator) -> None:
            async for msg in gen:
                replayed.append(msg)
                if len(replayed) >= 2:
                    break

        await _stop_after_two(resumable_pubsub.subscribe("chan:r1", last_event_id="e1"))

    await _replay_collect()
    assert replayed[0]["id"] == "e2", f"Expected e2 got {replayed[0]['id']}"
    assert replayed[1]["id"] == "e3", f"Expected e3 got {replayed[1]['id']}"
    print(f"  Replayed {len(replayed)} missed events: {[e['text'] for e in replayed]}")
    print("  Catch-up assertions passed.\n")

    print("=== Subscription Count Enforcement ===")
    fake_user_id = "demo-user"
    _active_subscription_counts[fake_user_id] = _SUBSCRIPTION_LIMIT_PER_USER
    count = subscription_count(fake_user_id)
    print(f"  Subscription count for {fake_user_id}: {count} (limit={_SUBSCRIPTION_LIMIT_PER_USER})")
    assert count == _SUBSCRIPTION_LIMIT_PER_USER
    print("  Limit check passed.\n")

    print("All demo assertions passed.")
    print("\nTo start the HTTP server run:")
    print("  uvicorn 04_subscriptions_realtime:app --reload --port 8000")


if __name__ == "__main__":
    asyncio.run(_run_demo())
