# WebSocket Scaling Patterns

> **Interview angle:** "Chat app design karo jo 1 million concurrent users handle kare. WebSocket scale kaise karoge?"

---

## 1. The Scaling Problem

Single FastAPI instance:
- ~10,000 concurrent WebSocket connections per process (1 CPU)
- Memory: ~10 KB per connection
- Hard ceiling around 50K-100K with tuning

**Above this** → horizontal scaling needed. **But WebSockets are stateful.**

### Core Challenge
```
User A connected to → Server 1
User B connected to → Server 2

User A sends message in room "general"
→ Server 1 has the message
→ Server 2's User B doesn't receive it
```

**Solution:** broadcast via shared message bus.

---

## 2. Architecture Patterns

### Pattern 1: Single Server (vertical scaling)
```
Browser ↔ Server (in-memory connection map)
```
- Works up to ~10-50K connections
- Single point of failure
- Use only for small apps

### Pattern 2: Multiple Servers + Pub/Sub
```
Browser ─ LB ─ Server 1 ─┐
                          │
Browser ─ LB ─ Server 2 ──├── Redis Pub/Sub
                          │
Browser ─ LB ─ Server 3 ─┘
```
- Each server subscribes to relevant channels
- When server publishes, all servers receive
- Each server forwards to its connected clients

### Pattern 3: Dedicated WebSocket Tier
```
Browser ─ LB ─ WS Tier (stateless) ─ Kafka/Redis ─ Worker Tier
                                                    │
                                                    └─ DB / Business Logic
```
- WS servers only handle connections
- Business logic in separate workers
- Best for huge scale (Slack, Discord)

### Pattern 4: Pure Pub/Sub Services
- Use Pusher, Ably, AWS API Gateway WebSocket
- Outsource WS handling, focus on business logic

---

## 3. Sticky Sessions vs Stateless

### Sticky Sessions (default needed for WS)
Load balancer routes same client to same server.
- Required because WS is a long-lived TCP connection
- Configure on Nginx/ALB/HAProxy
- Downside: uneven distribution if some servers have heavy users

### Stateless (with Redis state)
Store session state in Redis → any server can handle any message.
- More resilient (server crash = reconnect anywhere)
- Higher latency (Redis lookup per message)
- Used by large-scale chat apps

---

## 4. Redis Pub/Sub Pattern (Most Common)

```python
# Each server subscribes to "room:*" channels
# When user joins room → server subscribes to "room:general"
# When user sends message → server PUBLISH to "room:general"
# All servers subscribed → forward to their connected clients
```

### Code Structure
```python
class ConnectionManager:
    def __init__(self):
        self.local_connections = {}    # room_id → set of websockets ON THIS SERVER

    async def subscribe_to_redis(self, redis):
        pubsub = redis.pubsub()
        async for message in pubsub.listen():
            # Got message from another server — forward to local clients
            await self.broadcast_local(message["channel"], message["data"])

    async def publish(self, room_id, message):
        await redis.publish(f"room:{room_id}", message)

    async def broadcast_local(self, channel, data):
        room_id = channel.replace("room:", "")
        for ws in self.local_connections.get(room_id, []):
            await ws.send_text(data)
```

---

## 5. Kafka for Persistent Streaming

When you need:
- Replay history
- Multiple consumer groups (e.g., audit + analytics)
- Strict ordering per partition
- Long-term storage of events

```python
# Producer (in WS handler)
await producer.send("chat-events", key=room_id, value=message)

# Consumer (separate workers)
async for msg in consumer:
    await ws_manager.broadcast(msg.value)
```

Use Kafka for chat history, Redis Pub/Sub for ephemeral broadcasts.

---

## 6. Connection Lifecycle

```python
@app.websocket("/ws/{room_id}")
async def websocket_endpoint(websocket: WebSocket, room_id: str):
    await websocket.accept()
    await manager.connect(websocket, room_id)
    try:
        while True:
            data = await websocket.receive_text()
            await manager.broadcast(room_id, data)
    except WebSocketDisconnect:
        manager.disconnect(websocket, room_id)
    except Exception:
        manager.disconnect(websocket, room_id)
        raise
```

### Heartbeat / Ping-Pong
```python
async def send_pings():
    while True:
        await asyncio.sleep(30)
        for ws in connections:
            try:
                await ws.send_text("ping")
            except:
                disconnect(ws)
```

Why: NATs/proxies kill idle TCP connections after 60-120s.

---

## 7. Authentication

WebSocket doesn't natively support `Authorization` header in browsers. Options:

### Option 1: Token in query param
```
ws://api/ws?token=jwt_xxx
```
⚠️ Token logged in access logs.

### Option 2: First message after connect
```python
async def ws_endpoint(websocket):
    await websocket.accept()
    auth_msg = await websocket.receive_json()
    if not verify_token(auth_msg["token"]):
        await websocket.close(code=1008)
        return
```

### Option 3: Cookie-based (HTTP-only, same-site)
Works automatically if WS on same domain. Most secure.

### Option 4: Subprotocol header
```
new WebSocket(url, ["bearer", "jwt_token"])
```

---

## 8. Backpressure Handling

**Problem:** Slow client → server's send buffer fills → blocks event loop.

**Solutions:**
```python
async def safe_send(ws, message):
    try:
        await asyncio.wait_for(ws.send_text(message), timeout=5)
    except (asyncio.TimeoutError, WebSocketDisconnect):
        manager.disconnect(ws)
```

For high-throughput: per-connection queue with max size, drop on overflow.

---

## 9. Load Balancer Configuration

### Nginx
```nginx
upstream ws_backend {
    ip_hash;   # sticky sessions
    server app1:8000;
    server app2:8000;
    server app3:8000;
}

server {
    location /ws/ {
        proxy_pass http://ws_backend;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "Upgrade";
        proxy_set_header Host $host;
        proxy_read_timeout 86400;       # 24h — don't kill idle
        proxy_send_timeout 86400;
    }
}
```

### AWS ALB
- Listener: HTTP/HTTPS
- Target group: enable **stickiness** with cookie
- Timeout: increase idle timeout to 4000s

---

## 10. Real-World Examples

### Slack architecture
- WebSocket connections terminate at "flannel" service
- Flannel subscribes to Redis pub/sub
- Backend services publish via Redis
- Kafka for persistence + replay

### Discord
- Custom Rust-based gateway service
- ~5M concurrent connections per node
- Erlang for orchestration

### Twitch Chat (IRC over WebSocket)
- Each shard handles 10-15K viewers per channel
- Redis cluster for cross-shard

---

## 11. Monitoring Metrics

| Metric | Why |
|---|---|
| `ws_connected_total` | Total active connections |
| `ws_messages_sent_per_sec` | Broadcast load |
| `ws_messages_received_per_sec` | Client send rate |
| `ws_connection_duration_p50/p99` | How long users stay connected |
| `ws_send_failures_total` | Slow client / disconnects |
| `redis_pubsub_lag_ms` | Cross-server propagation delay |
| `memory_per_connection_kb` | Capacity planning |

---

## 12. FastAPI-Specific Tips

### Workers + WebSocket
- Each worker has independent connection set
- Need Redis/Kafka for cross-worker pub/sub
- Don't use `--workers > 1` without external state

### Async DB ops
- Don't use sync DB driver — blocks event loop = breaks WS

### Graceful shutdown
```python
@app.on_event("shutdown")
async def shutdown():
    for ws in active_connections:
        await ws.close(code=1001, reason="Server shutting down")
```

---

## 13. Interview Questions

**Q1: WebSocket scaling kaise karoge?**
1. Multiple servers + sticky sessions
2. Redis Pub/Sub for cross-server broadcasts
3. Kafka if persistence needed
4. Dedicated WS tier (Slack model)

**Q2: Sticky sessions kyu chahiye?**
WebSocket = long-lived TCP. Same client must reach same server for connection. Without sticky → reconnect every load-balanced request.

**Q3: 1M concurrent users design?**
- ~100 WS servers × 10K connections each
- Redis Cluster for state + pub/sub
- Kafka for events
- Geo-distributed clusters (multi-region)

**Q4: WS authentication?**
- Token in subprotocol or first-message
- Cookie if same-origin
- Validate before `await websocket.accept()`

**Q5: Slow client handle?**
Send with timeout. Drop if buffer fills. Use per-connection bounded queue.

**Q6: Heartbeat kyu zaroori?**
Detect dead connections (NAT timeouts, network drops). Without ping, server thinks client connected, wastes resources.

**Q7: Pub/Sub vs Kafka for WS?**
- Pub/Sub: ephemeral, fast, no replay
- Kafka: persistent, durable, can replay

---

## 14. Best Practices

1. **Stateless WS server + Redis state** for true scalability
2. **Sticky sessions** on LB for connection affinity
3. **Heartbeat** every 30s
4. **Auth before accept** — don't waste resources
5. **Bounded send queues** — prevent runaway memory
6. **Graceful shutdown** — close connections cleanly
7. **Monitoring** — track per-connection memory, broadcast lag
8. **Separate connection limits** per user (prevent abuse)
9. **Reconnect strategy** on client — exponential backoff
10. **Use HTTPS/WSS** — proxies often break plain WS

---

## Related
- [[13_asgi_internals_uvicorn_tuning]]
- [[../Phase2_Redis/]] — Redis Pub/Sub patterns
- [[../Phase3_DevOps/02_nginx]] — Nginx WS config
