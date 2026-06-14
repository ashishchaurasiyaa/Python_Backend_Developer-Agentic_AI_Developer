"""
Scaling WebSocket / SSE with Redis Pub/Sub — Production Patterns
=================================================================

Demonstrates how to break through the single-server WebSocket ceiling by
introducing Redis Pub/Sub as a backplane.  Every app server subscribes to
Redis channels for the users and rooms connected to it; publishing to Redis
from *any* server reaches the correct client regardless of which pod it lives on.

Topics covered
--------------
1.  Why multi-server WS breaks without a backplane.
2.  Redis Pub/Sub basics — publish / subscribe / pattern subscribe.
3.  Per-user channel pattern — ConnectionManager with lazy unsubscribe.
4.  Per-room channel pattern — group chat / live channels.
5.  Broadcast fan-out — system announcements, tenant notifications.
6.  Presence system — Redis sets + TTL heartbeat.
7.  Durability option A — Redis Streams (persistent, replay on reconnect).
8.  Durability option B — dual-write: Pub/Sub + DB for missed-event catch-up.
9.  Pattern subscriptions vs. explicit subscriptions — trade-offs.
10. Cluster considerations — sharded pub/sub (Redis 7+).
11. NATS alternative — brief illustrative snippet.
12. FastAPI integration — full runnable app wiring everything together.
13. Production monitoring checklist.

Quick start (local Redis required for full runtime behaviour)
-------------------------------------------------------------
    pip install fastapi uvicorn redis websockets
    docker run -d -p 6379:6379 redis:7

    # Run:
    uvicorn 03_scaling_with_redis_pubsub:app --host 0.0.0.0 --port 8000

Scaling numbers (real-world reference)
---------------------------------------
| Architecture                         | Concurrent connections |
|--------------------------------------|------------------------|
| Single Python server                 | 1 K – 10 K             |
| Multiple Python servers + Redis      | 100 K – 500 K          |
| Go/Rust servers + Redis              | 1 M+                   |
| Centrifugo (dedicated gateway)       | 10 M+                  |
| Phoenix Channels (Elixir)            | 2 M per server         |
"""

# pip install fastapi uvicorn redis websockets

import asyncio
import json
import logging
import time
from contextlib import asynccontextmanager
from typing import Optional

import redis.asyncio as aioredis
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

REDIS_URL = "redis://localhost:6379"

# ==========================================================================
# 1.  REDIS CLIENT — single shared async client per server process
#     Use a separate connection (or a separate Redis instance) for Pub/Sub
#     at high volume to avoid blocking the command pipeline.
# ==========================================================================

_redis_client: Optional[aioredis.Redis] = None


async def get_redis() -> aioredis.Redis:
    """Return the shared async Redis client, creating it on first call."""
    global _redis_client
    if _redis_client is None:
        _redis_client = aioredis.from_url(REDIS_URL, decode_responses=True)
    return _redis_client


# ==========================================================================
# 2.  REDIS PUB/SUB BASICS
#     Illustrative helpers that wrap the three core patterns.
# ==========================================================================

async def demo_pubsub_basics() -> None:
    """
    Illustrate the fundamental Redis Pub/Sub API.

    Key properties:
    - Fire-and-forget: no persistence; subscriber offline → message lost.
    - Fast: ~1 M msg/sec on a local Redis.
    - Pattern subscriptions: psubscribe("user:*").
    """
    r = await get_redis()

    # --- publisher ---
    subscribers = await r.publish("channel-demo", "Hello from publisher!")
    logger.info("Published to channel-demo; %d subscriber(s) received it.", subscribers)

    # --- subscriber (runs briefly then exits) ---
    pubsub = r.pubsub()
    await pubsub.subscribe("channel-demo")
    try:
        async for msg in pubsub.listen():
            if msg["type"] == "message":
                logger.info("Received from channel-demo: %s", msg["data"])
                break  # receive one message then stop for demo
    finally:
        await pubsub.unsubscribe("channel-demo")
        await pubsub.aclose()


# ==========================================================================
# 3.  PER-USER CHANNEL CONNECTION MANAGER
#
#  Architecture:
#
#       Load Balancer
#      /      |      \
#   Srv A   Srv B   Srv C          (each runs this ConnectionManager)
#     |       |       |
#     └───────┴───────┘
#              |
#           Redis  pub/sub
#
#  Each server maintains:
#    local_connections[user_id] → list of WebSocket objects
#    A single pubsub connection subscribing to the channels for users
#    currently connected to *this* server.
#
#  Lazy unsubscribe (30 s grace period):
#    When the last WS for a user disconnects, we keep the Redis subscription
#    for 30 seconds so a fast reconnect avoids the round-trip cost of
#    re-subscribing.
# ==========================================================================

UNSUBSCRIBE_GRACE_SECONDS = 30


class ConnectionManager:
    """
    Manages WebSocket connections and their Redis Pub/Sub subscriptions
    for a single server process.  Designed to be instantiated once at
    startup and shared across all request handlers.
    """

    def __init__(self, redis_client: aioredis.Redis) -> None:
        self.redis = redis_client
        # user_id → [WebSocket, ...]
        self.local_connections: dict[str, list[WebSocket]] = {}
        # user_id → asyncio.TimerHandle (pending unsubscribe after grace period)
        self._pending_unsub: dict[str, asyncio.TimerHandle] = {}
        self.pubsub = redis_client.pubsub()
        self._listener_task: Optional[asyncio.Task] = None

    async def start(self) -> None:
        """Launch the background Redis listener.  Call once at app startup."""
        self._listener_task = asyncio.create_task(self._listen(), name="redis-listener")
        logger.info("ConnectionManager started — Redis listener running.")

    async def stop(self) -> None:
        """Cancel the background listener and close the pubsub connection."""
        if self._listener_task:
            self._listener_task.cancel()
            try:
                await self._listener_task
            except asyncio.CancelledError:
                pass
        await self.pubsub.aclose()
        logger.info("ConnectionManager stopped.")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def connect(self, user_id: str, ws: WebSocket) -> None:
        """
        Accept the WebSocket and register it under user_id.
        Subscribe to the Redis channel user:{user_id} if this is the
        first connection for this user on this server.
        """
        await ws.accept()

        # Cancel any pending lazy-unsubscribe for this user.
        if user_id in self._pending_unsub:
            self._pending_unsub.pop(user_id).cancel()

        if user_id not in self.local_connections:
            self.local_connections[user_id] = []
            await self.pubsub.subscribe(f"user:{user_id}")
            logger.info("Subscribed to Redis channel user:%s", user_id)

        self.local_connections[user_id].append(ws)
        logger.info(
            "WebSocket connected for user %s (%d total connections for this user).",
            user_id,
            len(self.local_connections[user_id]),
        )

    async def disconnect(self, user_id: str, ws: WebSocket) -> None:
        """
        Remove the WebSocket from the registry.
        Schedule a lazy unsubscribe from Redis after the grace period so
        a rapid reconnect does not pay the subscribe round-trip cost.
        """
        connections = self.local_connections.get(user_id, [])
        if ws in connections:
            connections.remove(ws)

        if not connections:
            self.local_connections.pop(user_id, None)
            loop = asyncio.get_event_loop()
            handle = loop.call_later(
                UNSUBSCRIBE_GRACE_SECONDS,
                lambda: asyncio.ensure_future(self._lazy_unsubscribe(user_id)),
            )
            self._pending_unsub[user_id] = handle
            logger.info(
                "Last WS for user %s disconnected; will unsubscribe in %ds.",
                user_id,
                UNSUBSCRIBE_GRACE_SECONDS,
            )

    async def send_to_user(self, user_id: str, payload: dict) -> None:
        """
        Publish a JSON payload to user:{user_id} on Redis.

        Works whether the user is connected to this server or any other
        server in the fleet — Redis routes the message to the correct one.
        """
        await self.redis.publish(f"user:{user_id}", json.dumps(payload))

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _lazy_unsubscribe(self, user_id: str) -> None:
        """Unsubscribe from Redis after the grace period if no reconnect occurred."""
        self._pending_unsub.pop(user_id, None)
        if user_id not in self.local_connections:
            await self.pubsub.unsubscribe(f"user:{user_id}")
            logger.info("Unsubscribed from Redis channel user:%s (grace period expired).", user_id)

    async def _listen(self) -> None:
        """
        Background task: consume messages from the Redis pubsub connection
        and forward them to the appropriate local WebSocket clients.
        """
        logger.info("Redis listener task started.")
        try:
            async for msg in self.pubsub.listen():
                if msg["type"] != "message":
                    continue
                channel: str = msg["channel"]   # e.g. "user:123"
                data: str = msg["data"]

                if not channel.startswith("user:"):
                    continue

                user_id = channel.split(":", 1)[1]
                await self._forward(user_id, data)
        except asyncio.CancelledError:
            pass
        except Exception:
            logger.exception("Redis listener crashed — attempting restart.")

    async def _forward(self, user_id: str, text: str) -> None:
        """Send raw text to all local WebSocket connections for user_id."""
        sockets = list(self.local_connections.get(user_id, []))
        dead: list[WebSocket] = []
        for ws in sockets:
            try:
                await ws.send_text(text)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.local_connections.get(user_id, []).remove(ws)


# ==========================================================================
# 4.  PER-ROOM CHANNEL MANAGER (group chat / live rooms)
#
#  Extends the same pattern to rooms:
#    Redis channel: room:{room_id}
#    All servers with at least one member in room R subscribe to room:R.
# ==========================================================================

class RoomManager:
    """
    Manages room (group) subscriptions.  Tracks which WebSockets are in
    which room on this server and forwards inbound Redis messages accordingly.
    """

    def __init__(self, redis_client: aioredis.Redis) -> None:
        self.redis = redis_client
        # room_id → {WebSocket, ...}
        self.rooms: dict[str, set[WebSocket]] = {}
        self.pubsub = redis_client.pubsub()
        self._listener_task: Optional[asyncio.Task] = None

    async def start(self) -> None:
        self._listener_task = asyncio.create_task(self._listen(), name="room-redis-listener")

    async def stop(self) -> None:
        if self._listener_task:
            self._listener_task.cancel()
            try:
                await self._listener_task
            except asyncio.CancelledError:
                pass
        await self.pubsub.aclose()

    async def join(self, room_id: str, ws: WebSocket) -> None:
        """Subscribe to the room channel (if first member) and track the socket."""
        if room_id not in self.rooms:
            self.rooms[room_id] = set()
            await self.pubsub.subscribe(f"room:{room_id}")
            logger.info("Subscribed to Redis channel room:%s", room_id)
        self.rooms[room_id].add(ws)

    async def leave(self, room_id: str, ws: WebSocket) -> None:
        """Remove socket; unsubscribe from Redis when the room becomes empty."""
        members = self.rooms.get(room_id, set())
        members.discard(ws)
        if not members:
            self.rooms.pop(room_id, None)
            await self.pubsub.unsubscribe(f"room:{room_id}")
            logger.info("Unsubscribed from Redis channel room:%s (no members left).", room_id)

    async def publish(self, room_id: str, payload: dict) -> None:
        """Broadcast a message to all servers subscribed to this room."""
        await self.redis.publish(f"room:{room_id}", json.dumps(payload))

    async def _listen(self) -> None:
        try:
            async for msg in self.pubsub.listen():
                if msg["type"] != "message":
                    continue
                channel: str = msg["channel"]  # e.g. "room:general"
                data: str = msg["data"]

                if not channel.startswith("room:"):
                    continue

                room_id = channel.split(":", 1)[1]
                sockets = list(self.rooms.get(room_id, set()))
                for ws in sockets:
                    try:
                        await ws.send_text(data)
                    except Exception:
                        self.rooms.get(room_id, set()).discard(ws)
        except asyncio.CancelledError:
            pass
        except Exception:
            logger.exception("Room Redis listener crashed.")


# ==========================================================================
# 5.  BROADCAST FAN-OUT — system announcements / tenant notifications
#
#  Channels:
#    system:announcements  → all online users
#    tenant:{tid}:notify   → all users in a tenant
#
#  Subscribers register themselves; no routing table needed.
# ==========================================================================

async def broadcast_system_announcement(redis_client: aioredis.Redis, message: str) -> int:
    """
    Publish a system-wide announcement.
    Returns the number of server processes that received it.
    """
    payload = json.dumps({"type": "system_announcement", "message": message, "ts": time.time()})
    count = await redis_client.publish("system:announcements", payload)
    logger.info("Broadcast system announcement; %d server(s) received.", count)
    return count


async def broadcast_tenant_notification(
    redis_client: aioredis.Redis, tenant_id: str, payload: dict
) -> int:
    """Publish a notification to all users within a specific tenant."""
    data = json.dumps({"type": "tenant_notification", "tenant_id": tenant_id, **payload})
    return await redis_client.publish(f"tenant:{tenant_id}:notify", data)


# ==========================================================================
# 6.  PRESENCE SYSTEM — "who's online?" via Redis sets + TTL
#
#  On connect:
#    SADD online_users <user_id>
#    SET presence:<user_id> 1 EX 60
#
#  Heartbeat every 30 s:
#    EXPIRE presence:<user_id> 60   (reset TTL)
#
#  On disconnect:
#    SREM online_users <user_id>
#    DEL presence:<user_id>
#
#  Query:
#    SISMEMBER online_users <user_id>
#    SMEMBERS  online_users            (all online)
# ==========================================================================

PRESENCE_TTL_SECONDS = 60
HEARTBEAT_INTERVAL_SECONDS = 30


class PresenceManager:
    """
    Tracks online status using Redis sets and per-user TTL keys.
    A background heartbeat task keeps each connected user's presence key alive.
    """

    def __init__(self, redis_client: aioredis.Redis) -> None:
        self.redis = redis_client
        # user_id → heartbeat asyncio.Task
        self._heartbeats: dict[str, asyncio.Task] = {}

    async def mark_online(self, user_id: str) -> None:
        """Register a user as online and start their heartbeat."""
        pipe = self.redis.pipeline()
        pipe.sadd("online_users", user_id)
        pipe.set(f"presence:{user_id}", "1", ex=PRESENCE_TTL_SECONDS)
        await pipe.execute()

        if user_id not in self._heartbeats:
            task = asyncio.create_task(
                self._heartbeat_loop(user_id), name=f"presence-hb-{user_id}"
            )
            self._heartbeats[user_id] = task
        logger.info("User %s is now online.", user_id)

    async def mark_offline(self, user_id: str) -> None:
        """Remove the user from the online set and cancel their heartbeat."""
        task = self._heartbeats.pop(user_id, None)
        if task:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        pipe = self.redis.pipeline()
        pipe.srem("online_users", user_id)
        pipe.delete(f"presence:{user_id}")
        await pipe.execute()
        logger.info("User %s is now offline.", user_id)

    async def is_online(self, user_id: str) -> bool:
        return bool(await self.redis.sismember("online_users", user_id))

    async def all_online(self) -> set[str]:
        return await self.redis.smembers("online_users")

    async def _heartbeat_loop(self, user_id: str) -> None:
        """Refresh the presence TTL every HEARTBEAT_INTERVAL_SECONDS."""
        try:
            while True:
                await asyncio.sleep(HEARTBEAT_INTERVAL_SECONDS)
                await self.redis.expire(f"presence:{user_id}", PRESENCE_TTL_SECONDS)
        except asyncio.CancelledError:
            pass


# ==========================================================================
# 7.  DURABILITY — OPTION A: REDIS STREAMS
#
#  Redis 5+ persistent streams allow replay on reconnect.
#
#  Publish:
#    XADD stream:user:{user_id} * data <json>
#
#  Consume (new events only):
#    XREAD BLOCK 5000 STREAMS stream:user:{user_id} $
#
#  Catch-up after reconnect:
#    XREAD STREAMS stream:user:{user_id} <last_msg_id>
# ==========================================================================

async def stream_publish(redis_client: aioredis.Redis, user_id: str, payload: dict) -> str:
    """
    Write a message to the persistent Redis Stream for user_id.
    Returns the generated message ID which the client should track
    to request catch-up on reconnect.
    """
    msg_id = await redis_client.xadd(f"stream:user:{user_id}", {"data": json.dumps(payload)})
    return msg_id


async def stream_consume(
    redis_client: aioredis.Redis, user_id: str, ws: WebSocket, last_id: str = "$"
) -> None:
    """
    Forward Redis Stream messages to a WebSocket, starting from last_id.

    Pass last_id="$" for live-only delivery, or pass the client's last
    acknowledged message ID to replay missed events on reconnect.
    """
    while True:
        try:
            events = await redis_client.xread(
                {f"stream:user:{user_id}": last_id}, block=5000, count=100
            )
        except Exception:
            logger.exception("Stream read error for user %s.", user_id)
            await asyncio.sleep(1)
            continue

        for _stream, messages in events:
            for msg_id, fields in messages:
                try:
                    await ws.send_text(fields["data"])
                    last_id = msg_id  # advance cursor
                except Exception:
                    logger.warning("Failed to deliver stream msg %s to WS.", msg_id)
                    return


# ==========================================================================
# 8.  DURABILITY — OPTION B: DUAL-WRITE (Redis Pub/Sub + DB)
#
#  On send:
#    1. Persist to DB (so missed events can be queried later).
#    2. Publish to Redis Pub/Sub for live delivery.
#
#  On WS reconnect:
#    1. Fetch events from DB since last_event_id.
#    2. Flush them to the client.
#    3. Then subscribe to the live Redis channel.
#
#  The stub below shows the pattern without a real DB dependency.
# ==========================================================================

class DurableMessenger:
    """
    Illustrates the dual-write pattern.  Replace _db_insert / _db_fetch
    with your actual ORM or DB driver calls.
    """

    def __init__(self, redis_client: aioredis.Redis) -> None:
        self.redis = redis_client
        # In-process list simulates a DB table (replace with real persistence).
        self._db: list[dict] = []
        self._id_counter = 0

    async def send(self, user_id: str, msg: dict) -> int:
        """Persist the message and publish it on Redis for live delivery."""
        self._id_counter += 1
        event = {"id": self._id_counter, "user_id": user_id, "ts": time.time(), **msg}
        # --- step 1: persist ---
        self._db.append(event)
        # --- step 2: live broadcast ---
        await self.redis.publish(f"user:{user_id}", json.dumps(event))
        return event["id"]

    async def catchup(self, ws: WebSocket, user_id: str, last_event_id: int) -> None:
        """
        Replay any events the client missed while disconnected.
        Should be called immediately after WS accept, before subscribing
        to the live Redis channel.
        """
        missed = [e for e in self._db if e["user_id"] == user_id and e["id"] > last_event_id]
        for evt in missed:
            try:
                await ws.send_json(evt)
            except Exception:
                logger.warning("Failed to deliver catch-up event %d.", evt["id"])
                return
        logger.info("Sent %d catch-up event(s) to user %s.", len(missed), user_id)


# ==========================================================================
# 9.  PATTERN SUBSCRIPTIONS vs. EXPLICIT SUBSCRIPTIONS
#
#  psubscribe("user:*") matches ALL user channels:
#    - Simpler: no explicit subscribe/unsubscribe per user.
#    - Wasteful: receives messages for users NOT connected to this server;
#      requires filtering in the app layer.
#
#  Explicit subscribe per user (used above in ConnectionManager):
#    - Receives only relevant messages.
#    - Requires subscribe/unsubscribe lifecycle management.
#    - Preferred for medium-to-large fleets.
#
#  Pattern subscribe is acceptable for small deployments where the number
#  of distinct user channels is bounded and traffic is low.
# ==========================================================================

async def pattern_subscribe_demo(redis_client: aioredis.Redis, managed_users: set[str]) -> None:
    """
    Demonstrate psubscribe for "user:*".  In a real server this would run
    as a background task; it filters to only deliver for users that are
    actually connected here.
    """
    pubsub = redis_client.pubsub()
    await pubsub.psubscribe("user:*")
    try:
        async for msg in pubsub.listen():
            if msg["type"] != "pmessage":
                continue
            channel: str = msg["channel"]
            user_id = channel.split(":", 1)[1]
            if user_id not in managed_users:
                # Message is for a user on a different server — discard.
                continue
            logger.info("Pattern sub received for managed user %s: %s", user_id, msg["data"])
    finally:
        await pubsub.punsubscribe("user:*")
        await pubsub.aclose()


# ==========================================================================
# 10.  REDIS CLUSTER CONSIDERATIONS
#
#  Standard pub/sub does NOT propagate across Redis Cluster nodes:
#
#    Node 1: PUBLISH user:123 "hello"
#    Node 2: SUBSCRIBE user:123          ← will NOT receive the message
#
#  Solutions (in order of preference):
#
#  A. Redis 7+ Sharded Pub/Sub
#     Uses CRC16 to pin a channel to a specific node:
#
#       SPUBLISH  user:123 "hello"     (publish to shard)
#       SSUBSCRIBE user:123            (subscribe to shard)
#
#     redis-py: await r.spublish(...) / await pubsub.ssubscribe(...)
#
#  B. Single non-clustered Redis for pub/sub only
#     Use a separate standalone Redis for pub/sub, separate cluster for data.
#     Simple and scales to ~100 K subscribers.
#
#  C. NATS or Kafka
#     For architectures that exceed what Redis can handle or need built-in
#     persistence with consumer groups (Kafka) or low-latency subject routing
#     (NATS).
# ==========================================================================

REDIS_CLUSTER_NOTES = """
Sharded Pub/Sub (Redis 7+) example:

    import redis.asyncio.cluster as redis_cluster

    rc = redis_cluster.RedisCluster.from_url("redis://localhost:7000")

    # Publish (routes to the shard that owns "user:123")
    await rc.spublish("user:123", json.dumps(payload))

    # Subscribe (connect directly to the shard that owns the channel)
    pubsub = rc.pubsub()
    await pubsub.ssubscribe("user:123")
    async for msg in pubsub.listen():
        ...
"""


# ==========================================================================
# 11.  NATS ALTERNATIVE — brief illustrative snippet
#
#  NATS is purpose-built for messaging:
#  - Lower latency than Redis Pub/Sub.
#  - Pull-based subscribers for back-pressure control.
#  - Wildcard subject hierarchies.
#  - JetStream for durable streams (Kafka-like).
#
#  pip install nats-py
# ==========================================================================

NATS_EXAMPLE = """
import nats

# Connect
nc = await nats.connect("nats://localhost:4222")

# Publish
await nc.publish("user.123.msg", json.dumps(payload).encode())

# Subscribe with wildcard (user.> matches user.123.msg, user.456.alert, …)
async def handler(msg):
    data = json.loads(msg.data.decode())
    print("NATS received:", data)

sub = await nc.subscribe("user.>", cb=handler)

# JetStream (durable, persistent)
js = nc.jetstream()
await js.add_stream(name="USERS", subjects=["user.>"])
await js.publish("user.123.msg", json.dumps(payload).encode())
"""

BACKPLANE_SELECTION_GUIDE = """
Choosing the right backplane
-----------------------------
Concurrent users   Recommended backplane
-----------------  ------------------------------------------
< 10 K             Redis Pub/Sub (simple)
10 K – 500 K       Redis Pub/Sub + Streams for persistence
500 K – 1 M        NATS or Centrifugo
Need replay/dura.  Kafka or Redis Streams
> 1 M              Dedicated tier: Centrifugo, Go gateway, etc.
"""


# ==========================================================================
# 12.  FASTAPI APPLICATION — wires everything together
# ==========================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown lifecycle for the FastAPI app."""
    r = await get_redis()

    # Instantiate shared managers.
    app.state.conn_manager = ConnectionManager(r)
    app.state.room_manager = RoomManager(r)
    app.state.presence = PresenceManager(r)
    app.state.messenger = DurableMessenger(r)

    await app.state.conn_manager.start()
    await app.state.room_manager.start()
    logger.info("App startup complete — all managers running.")

    yield

    # Graceful shutdown.
    await app.state.conn_manager.stop()
    await app.state.room_manager.stop()
    if _redis_client:
        await _redis_client.aclose()
    logger.info("App shutdown complete.")


app = FastAPI(
    title="WebSocket Scaling — Redis Pub/Sub",
    description="Production patterns for multi-server real-time with Redis.",
    version="1.0.0",
    lifespan=lifespan,
)


# --------------------------------------------------------------------------
# Per-user WebSocket endpoint
# --------------------------------------------------------------------------

@app.websocket("/ws/user/{user_id}")
async def websocket_user(websocket: WebSocket, user_id: str) -> None:
    """
    Connect a client identified by user_id.

    Any server in the fleet can call send_to_user(user_id, ...) and the
    message will arrive here regardless of which pod the client is on.
    """
    manager: ConnectionManager = websocket.app.state.conn_manager
    presence: PresenceManager = websocket.app.state.presence

    await manager.connect(user_id, websocket)
    await presence.mark_online(user_id)
    try:
        while True:
            raw = await websocket.receive_text()
            # Echo inbound messages back through Redis so the full
            # pub/sub round-trip is exercised even in a local demo.
            payload = {"type": "echo", "from": user_id, "data": raw}
            await manager.send_to_user(user_id, payload)
    except WebSocketDisconnect:
        pass
    finally:
        await manager.disconnect(user_id, websocket)
        await presence.mark_offline(user_id)


# --------------------------------------------------------------------------
# Per-room WebSocket endpoint
# --------------------------------------------------------------------------

@app.websocket("/ws/room/{room_id}/{user_id}")
async def websocket_room(websocket: WebSocket, room_id: str, user_id: str) -> None:
    """
    Connect user_id to room room_id.
    Messages posted to the room are delivered to every member across all servers.
    """
    room_mgr: RoomManager = websocket.app.state.room_manager

    await websocket.accept()
    await room_mgr.join(room_id, websocket)
    try:
        while True:
            raw = await websocket.receive_text()
            payload = {"type": "chat", "room": room_id, "from": user_id, "text": raw}
            await room_mgr.publish(room_id, payload)
    except WebSocketDisconnect:
        pass
    finally:
        await room_mgr.leave(room_id, websocket)


# --------------------------------------------------------------------------
# REST endpoints — demonstrate fire-and-forget pub, presence queries, etc.
# --------------------------------------------------------------------------

@app.post("/publish/user/{user_id}")
async def publish_to_user(user_id: str, body: dict) -> JSONResponse:
    """
    Publish a message to a user from the server side.
    Works from any instance; Redis routes to whichever server the user is on.
    """
    r = await get_redis()
    await r.publish(f"user:{user_id}", json.dumps(body))
    return JSONResponse({"status": "published", "user_id": user_id})


@app.post("/publish/room/{room_id}")
async def publish_to_room(room_id: str, body: dict) -> JSONResponse:
    """Publish a message to an entire room."""
    room_mgr: RoomManager = app.state.room_manager
    await room_mgr.publish(room_id, body)
    return JSONResponse({"status": "published", "room_id": room_id})


@app.post("/announce")
async def announce(body: dict) -> JSONResponse:
    """Broadcast a system-wide announcement to all connected servers."""
    r = await get_redis()
    count = await broadcast_system_announcement(r, body.get("message", ""))
    return JSONResponse({"status": "broadcast", "servers_reached": count})


@app.get("/presence/{user_id}")
async def check_presence(user_id: str) -> JSONResponse:
    """Return online / offline status for a user."""
    presence: PresenceManager = app.state.presence
    online = await presence.is_online(user_id)
    return JSONResponse({"user_id": user_id, "online": online})


@app.get("/presence")
async def list_online() -> JSONResponse:
    """Return the set of all currently online user IDs."""
    presence: PresenceManager = app.state.presence
    users = list(await presence.all_online())
    return JSONResponse({"online": users, "count": len(users)})


@app.post("/send/durable/{user_id}")
async def send_durable(user_id: str, body: dict) -> JSONResponse:
    """
    Dual-write: persist the message AND publish on Redis.
    On reconnect the client can request catch-up since last_event_id.
    """
    messenger: DurableMessenger = app.state.messenger
    event_id = await messenger.send(user_id, body)
    return JSONResponse({"status": "sent", "event_id": event_id})


# --------------------------------------------------------------------------
# WebSocket endpoint that supports catch-up (durability option B)
# --------------------------------------------------------------------------

@app.websocket("/ws/durable/{user_id}")
async def websocket_durable(
    websocket: WebSocket, user_id: str, last_event_id: int = 0
) -> None:
    """
    WebSocket with catch-up on reconnect.

    Query param: last_event_id — the last event the client acknowledged.
    Server replays any missed events before switching to live delivery.
    """
    manager: ConnectionManager = websocket.app.state.conn_manager
    messenger: DurableMessenger = websocket.app.state.messenger

    await websocket.accept()
    # Step 1: flush missed events.
    await messenger.catchup(websocket, user_id, last_event_id)
    # Step 2: register for live delivery (without re-accepting).
    if user_id not in manager.local_connections:
        manager.local_connections[user_id] = []
        await manager.pubsub.subscribe(f"user:{user_id}")
    manager.local_connections[user_id].append(websocket)
    try:
        while True:
            raw = await websocket.receive_text()
            event_id = await messenger.send(user_id, {"type": "echo", "data": raw})
            logger.info("Durable send for user %s — event_id=%d", user_id, event_id)
    except WebSocketDisconnect:
        pass
    finally:
        await manager.disconnect(user_id, websocket)


# ==========================================================================
# 13.  PRODUCTION MONITORING CHECKLIST
# ==========================================================================

MONITORING_CHECKLIST = """
Metrics to track
----------------
- ws_connections_active       Per server; alert on sudden drop.
- redis_pubsub_messages_rate  Messages published per second.
- redis_stream_lag            Consumer group lag for Stream-based delivery.
- ws_message_delivery_failed  Increment on send_text exceptions.
- redis_resubscriptions       Track reconnect / subscription churn.

Key alerts
----------
- Connection count drops > 20% in 60 s     → possible crash or network partition.
- Redis pub/sub backlog growing             → Redis CPU saturation.
- Reconnect storm (spike in ws_connect/s)  → back-off + jitter on client side.

Recommended tooling
-------------------
- Prometheus + Grafana for time-series metrics.
- Redis INFO stats (connected_clients, pubsub_channels, pubsub_patterns).
- Sentry for WebSocket exception tracking.
- Structured JSON logging (structlog / python-json-logger) for log aggregation.

Common pitfalls — summary
--------------------------
1. pub/sub on Redis Cluster: broadcast does not cross nodes; use sharded or single.
2. Forgetting unsubscribe: memory leaks in the Redis server (pubsub_channels grows).
3. No heartbeat / ping: half-open TCP connections accumulate silently.
4. Using pub/sub for durable messaging: fire-and-forget, no replay.
5. Sharing Redis for cache + high-volume pub/sub: separate instances.
6. psubscribe("user:*") on large fleet: each server gets all traffic; filter overhead.
"""
