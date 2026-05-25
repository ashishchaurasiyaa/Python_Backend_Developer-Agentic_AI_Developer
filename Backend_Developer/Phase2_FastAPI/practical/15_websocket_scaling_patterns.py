"""
============================================================
WEBSOCKET SCALING PATTERNS — Practical
============================================================
Multi-server WebSocket broadcast using Redis Pub/Sub.

Install:
    pip install fastapi uvicorn redis websockets

Run multiple servers:
    uvicorn 15_websocket_scaling_patterns:app --port 8001
    uvicorn 15_websocket_scaling_patterns:app --port 8002

Connect clients:
    # Browser console:
    const ws = new WebSocket("ws://localhost:8001/ws/general?token=abc");
    ws.onmessage = (e) => console.log(e.data);
    ws.send(JSON.stringify({type: "message", text: "hi"}));

    # Other tab:
    const ws = new WebSocket("ws://localhost:8002/ws/general?token=def");
    # Should receive messages from port 8001 — cross-server broadcast!
"""
import asyncio
import json
import time
import os
import uuid
from typing import Dict, Set


# ============================================================
# 1. CONNECTION MANAGER (per-server)
# ============================================================
class ConnectionManager:
    """Tracks local WebSocket connections grouped by room."""
    def __init__(self):
        # room_id -> set of (ws, user_id, connection_id)
        self.rooms: Dict[str, Set] = {}
        # connection_id -> metadata
        self.connections: Dict[str, dict] = {}

    async def connect(self, websocket, room_id: str, user_id: str) -> str:
        conn_id = str(uuid.uuid4())
        if room_id not in self.rooms:
            self.rooms[room_id] = set()
        self.rooms[room_id].add((websocket, user_id, conn_id))
        self.connections[conn_id] = {
            "room_id": room_id,
            "user_id": user_id,
            "ws": websocket,
            "connected_at": time.time(),
            "last_seen": time.time(),
        }
        return conn_id

    def disconnect(self, conn_id: str):
        meta = self.connections.pop(conn_id, None)
        if meta:
            room_id = meta["room_id"]
            if room_id in self.rooms:
                self.rooms[room_id] = {
                    t for t in self.rooms[room_id] if t[2] != conn_id
                }
                if not self.rooms[room_id]:
                    del self.rooms[room_id]

    async def broadcast_local(self, room_id: str, message: str):
        """Send to clients ON THIS SERVER only."""
        dead = []
        for ws, user_id, conn_id in self.rooms.get(room_id, set()):
            try:
                await asyncio.wait_for(ws.send_text(message), timeout=5)
            except Exception:
                dead.append(conn_id)
        for conn_id in dead:
            self.disconnect(conn_id)

    def stats(self) -> dict:
        return {
            "total_connections": len(self.connections),
            "rooms": {r: len(s) for r, s in self.rooms.items()},
            "uptime_seconds": time.time() - SERVER_START,
        }


SERVER_START = time.time()
manager = ConnectionManager()
SERVER_ID = os.getenv("HOSTNAME", str(uuid.uuid4())[:8])


# ============================================================
# 2. REDIS PUB/SUB BRIDGE (cross-server broadcast)
# ============================================================
class RedisBridge:
    """Subscribes to Redis pub/sub, forwards messages to local clients."""
    def __init__(self, redis_url: str, manager: ConnectionManager):
        self.redis_url = redis_url
        self.manager = manager
        self.redis = None
        self.pubsub = None
        self._task = None

    async def start(self):
        try:
            import redis.asyncio as redis_lib
        except ImportError:
            print("  ⚠️  Install: pip install redis")
            return
        self.redis = redis_lib.from_url(self.redis_url, decode_responses=True)
        self.pubsub = self.redis.pubsub()
        await self.pubsub.psubscribe("room:*")
        self._task = asyncio.create_task(self._listen())
        print(f"  ✅ Redis bridge connected ({SERVER_ID})")

    async def _listen(self):
        async for message in self.pubsub.listen():
            if message["type"] != "pmessage":
                continue
            channel = message["channel"]    # "room:general"
            room_id = channel.split(":", 1)[1]
            data = message["data"]
            # Parse — skip if originated from this server (avoid echo)
            payload = json.loads(data)
            if payload.get("origin_server") == SERVER_ID:
                continue
            await self.manager.broadcast_local(room_id, data)

    async def publish(self, room_id: str, payload: dict):
        if not self.redis:
            # No Redis = single-server mode, just local broadcast
            await self.manager.broadcast_local(room_id, json.dumps(payload))
            return
        payload["origin_server"] = SERVER_ID
        data = json.dumps(payload)
        # 1. Send locally (avoid waiting for Redis round-trip)
        await self.manager.broadcast_local(room_id, data)
        # 2. Publish to Redis so OTHER servers get it
        await self.redis.publish(f"room:{room_id}", data)

    async def stop(self):
        if self._task:
            self._task.cancel()
        if self.pubsub:
            await self.pubsub.close()
        if self.redis:
            await self.redis.close()


bridge = RedisBridge(
    redis_url=os.getenv("REDIS_URL", "redis://localhost:6379/0"),
    manager=manager,
)


# ============================================================
# 3. AUTH (simple token verification)
# ============================================================
def verify_token(token: str) -> str | None:
    """In production: verify JWT, check DB. Here: any non-empty token = user."""
    if not token or len(token) < 3:
        return None
    return f"user_{token[:6]}"


# ============================================================
# 4. FASTAPI APP — endpoints
# ============================================================
try:
    from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query, HTTPException
    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def lifespan(app):
        await bridge.start()
        # Background heartbeat
        hb_task = asyncio.create_task(heartbeat_loop())
        yield
        hb_task.cancel()
        await bridge.stop()

    app = FastAPI(lifespan=lifespan)

    @app.get("/")
    async def index():
        return {
            "server_id": SERVER_ID,
            "info": "WebSocket scaling demo",
            "ws_url": "/ws/{room_id}?token=...",
            "stats": manager.stats(),
        }

    @app.get("/stats")
    async def stats():
        return {**manager.stats(), "server_id": SERVER_ID}

    @app.websocket("/ws/{room_id}")
    async def websocket_endpoint(
        websocket: WebSocket,
        room_id: str,
        token: str = Query(...),
    ):
        # Auth BEFORE accepting (don't waste resources on bad clients)
        user_id = verify_token(token)
        if not user_id:
            await websocket.close(code=1008, reason="Unauthorized")
            return

        await websocket.accept()
        conn_id = await manager.connect(websocket, room_id, user_id)
        await websocket.send_json({
            "type": "joined",
            "room_id": room_id,
            "user_id": user_id,
            "server_id": SERVER_ID,
        })

        # Notify others
        await bridge.publish(room_id, {
            "type": "user_joined",
            "user_id": user_id,
        })

        try:
            while True:
                data = await websocket.receive_json()
                msg_type = data.get("type", "message")
                if msg_type == "message":
                    await bridge.publish(room_id, {
                        "type": "message",
                        "user_id": user_id,
                        "text": data.get("text", ""),
                        "ts": time.time(),
                    })
                elif msg_type == "pong":
                    manager.connections[conn_id]["last_seen"] = time.time()
        except WebSocketDisconnect:
            pass
        except Exception as e:
            print(f"  WS error: {e}")
        finally:
            manager.disconnect(conn_id)
            await bridge.publish(room_id, {
                "type": "user_left",
                "user_id": user_id,
            })

except ImportError:
    print("FastAPI not installed — run: pip install fastapi uvicorn redis")


# ============================================================
# 5. HEARTBEAT — detect dead connections
# ============================================================
async def heartbeat_loop():
    """Send pings every 30s, drop stale connections."""
    while True:
        await asyncio.sleep(30)
        now = time.time()
        for conn_id, meta in list(manager.connections.items()):
            try:
                # Send ping
                await asyncio.wait_for(
                    meta["ws"].send_json({"type": "ping"}),
                    timeout=2,
                )
                # Check stale (no pong in 90s)
                if now - meta["last_seen"] > 90:
                    print(f"  Dropping stale connection: {conn_id}")
                    await meta["ws"].close()
                    manager.disconnect(conn_id)
            except Exception:
                manager.disconnect(conn_id)


# ============================================================
# 6. NGINX CONFIG FOR PRODUCTION
# ============================================================
NGINX_CONFIG = """
# /etc/nginx/conf.d/ws.conf
upstream ws_backend {
    ip_hash;                    # sticky sessions for WS
    server app1:8000;
    server app2:8000;
    server app3:8000;
}

server {
    listen 443 ssl;
    server_name api.example.com;

    location /ws/ {
        proxy_pass http://ws_backend;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "Upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;

        # Long-lived WS connections
        proxy_read_timeout 86400;     # 24h
        proxy_send_timeout 86400;
        proxy_connect_timeout 60;
    }
}
"""


# ============================================================
# 7. CLIENT JS REFERENCE
# ============================================================
CLIENT_JS = """
const ws = new WebSocket("ws://localhost:8001/ws/general?token=mytoken");

ws.onopen = () => {
    console.log("Connected!");
    ws.send(JSON.stringify({type: "message", text: "Hello"}));
};

ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    if (data.type === "ping") {
        ws.send(JSON.stringify({type: "pong"}));   // heartbeat
    } else {
        console.log("Received:", data);
    }
};

ws.onclose = (event) => {
    console.log("Disconnected:", event.code);
    // Reconnect with exponential backoff
    setTimeout(connectWS, Math.min(30000, 1000 * Math.pow(2, retries++)));
};
"""


# ============================================================
# 8. STANDALONE TEST (without FastAPI)
# ============================================================
async def standalone_demo():
    """Test ConnectionManager without server setup."""
    print("=" * 60)
    print("WebSocket Manager — Standalone Demo")
    print("=" * 60)

    class FakeWS:
        def __init__(self, name):
            self.name = name
            self.messages = []
        async def send_text(self, msg):
            self.messages.append(msg)
            print(f"  [{self.name}] received: {msg[:60]}")

    mgr = ConnectionManager()
    a = FakeWS("alice")
    b = FakeWS("bob")
    c = FakeWS("carol")

    await mgr.connect(a, "general", "alice")
    await mgr.connect(b, "general", "bob")
    await mgr.connect(c, "private", "carol")

    print(f"\n  Stats: {mgr.stats()}")

    print("\n  Broadcasting to 'general' room:")
    await mgr.broadcast_local("general", '{"text":"Hi general"}')
    print("\n  Carol (private) should NOT receive ↑")


if __name__ == "__main__":
    print("=" * 60)
    print("WebSocket Scaling Patterns")
    print("=" * 60)
    print("\nProduction run:")
    print("  uvicorn 15_websocket_scaling_patterns:app --port 8001")
    print("  uvicorn 15_websocket_scaling_patterns:app --port 8002")
    print("\nClient JS:")
    print(CLIENT_JS)
    print("\nNginx config:")
    print(NGINX_CONFIG)
    print("\n--- Running standalone manager demo ---")
    asyncio.run(standalone_demo())
