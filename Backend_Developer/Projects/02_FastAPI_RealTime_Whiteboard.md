# Project 2: Real-Time Collaborative Whiteboard / Editor

**Stack:** FastAPI + WebSocket + Y.js (CRDT) + Redis + Postgres + S3 + Cloudflare
**Build Time:** 3-4 weeks
**Difficulty:** ⭐⭐⭐⭐⭐ (Distributed systems heavy)
**Resume Strength:** ⭐⭐⭐⭐⭐ (Wow factor + showcases real-time architecture)

---

## 1. Project Overview & Business Problem

### What it is
A Google Docs / Figma / Miro-style collaborative editor backend. Multiple users edit the same document simultaneously and see each other's changes in real-time with sub-100ms latency.

### Why build this
- **Real-time architecture showcase:** WebSocket scaling, pub/sub backplane, conflict resolution.
- **CRDT (Conflict-free Replicated Data Type):** The hard problem of distributed systems made approachable.
- **Best demo:** Open two browser tabs → both edit → both update. Magic in interviews.
- **Modern stack:** Y.js, WebRTC adjacency, edge networking.

### Real-world analogues
- Google Docs
- Figma
- Miro
- Notion (partial — has CRDT)
- Linear
- Excalidraw
- Replit's collaborative coding

---

## 2. Requirements

### Functional
- **Document creation:** Users create text docs, whiteboards, mind maps.
- **Real-time sync:** All edits propagate to other connected users instantly.
- **Conflict resolution:** Concurrent edits merge deterministically without server arbitration.
- **Presence:** See who's currently viewing/editing the doc.
- **Cursors:** See where other users' cursors are.
- **Offline support:** Edit while offline; sync when reconnected.
- **Version history:** View past versions; restore.
- **Sharing:** Public/private/password-protected.
- **Comments:** Threaded comments on parts of the doc.
- **Authentication:** Both logged-in and anonymous users.

### Non-Functional
- 100K+ concurrent users globally.
- 1M+ documents stored.
- Sub-100ms sync latency in same region; < 300ms global.
- 99.95% availability.
- Document size up to 10MB per doc.
- Offline sync with conflict resolution.

---

## 3. Scale Estimation

| Metric | Number |
|---|---|
| Total users | 10M |
| Daily active users | 1M |
| Concurrent WebSocket connections | 100K |
| Documents stored | 1M |
| Avg document size | 100KB (text); 5MB (whiteboards with images) |
| Total storage | 1M × 1MB avg = 1TB |
| Events/sec at peak | 50K (10K active editors × 5 ops/sec) |
| WS message broadcast/sec | 500K (1 op fan-out 10×) |

---

## 4. CRDT — The Core Concept

### Why not Operational Transformation (OT)?
- OT (Google Docs): central server arbitrates; complex algorithm; brittle offline.
- CRDT: decentralized; operations commute; offline-first; provably correct.

### What is CRDT?
Data structures designed so concurrent operations produce the same result regardless of order:

```
User A inserts "X" at position 5
User B inserts "Y" at position 5 (simultaneously)

CRDT outcome: both characters preserved; deterministic ordering (e.g., by user ID).
Final state: same on all replicas after sync.
```

### Y.js — the library we'll use
Y.js is the production-grade CRDT for collaborative editing.

```python
# Server doesn't need to interpret CRDT.
# It just stores + broadcasts the binary updates.
```

Server's job:
1. Receive binary CRDT updates from clients.
2. Broadcast to all other connected clients.
3. Persist for late-joiners.

### Why this is brilliant
Server logic is dumb (just broker). Clients merge updates via CRDT math. **Scales beautifully.**

---

## 5. High-Level Architecture

```
                       Browser Clients (Y.js)
                              │
                              │ WebSocket
                              ▼
                       ┌──────────────┐
                       │ Cloudflare    │ (TLS, geo-routing)
                       └──────┬───────┘
                              │
                       ┌──────▼───────┐
                       │  Load        │
                       │  Balancer    │
                       └──────┬───────┘
                              │ sticky sessions
              ┌───────────────┼────────────────┐
              │               │                │
        ┌─────▼──────┐   ┌────▼──────┐   ┌────▼──────┐
        │  WS        │   │  WS        │   │  WS        │
        │  Gateway 1 │   │  Gateway 2 │   │  Gateway N │
        └─────┬──────┘   └────┬──────┘   └────┬──────┘
              │               │                │
              └───────────────┼────────────────┘
                              │
                       ┌──────▼───────┐
                       │   Redis      │ Pub/Sub
                       │   Cluster    │ (cross-server broadcast)
                       └──────────────┘
                              │
                       ┌──────▼───────┐
                       │   Postgres   │ (doc metadata)
                       │              │
                       │   S3         │ (CRDT snapshots)
                       └──────────────┘
```

---

## 6. The Data Flow (Critical)

### User A makes an edit
```
1. Client A: insert "hello" at position 0.
2. Y.js generates a binary CRDT update.
3. Client A sends update via WebSocket → Server A.
4. Server A:
   a. Persists update (append to update log).
   b. Publishes to Redis: "doc:abc:updates" with the binary blob.
5. All servers (1, 2, ..., N) subscribed to "doc:abc:updates" receive it.
6. Each server broadcasts to its locally-connected clients editing doc abc.
7. Client B receives update → applies via Y.js → UI updates.
```

End-to-end latency: typically < 50ms in same region.

### Late-joining client
```
1. Client connects to /ws/doc/abc.
2. Server sends current full state (snapshot + recent updates).
3. Client's Y.js initializes with this state.
4. Client subscribes to future updates.
```

### Sync after offline period
```
1. Client comes back online with local Y.js state.
2. Client sends "state vector" (what it has).
3. Server computes diff: updates it has but client doesn't.
4. Server sends those updates.
5. Client merges → catches up.
```

---

## 7. Data Model

```sql
-- Documents
CREATE TABLE documents (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    owner_id        UUID REFERENCES users(id),
    title           TEXT NOT NULL,
    type            TEXT NOT NULL,    -- 'text', 'whiteboard', 'mindmap'
    visibility      TEXT NOT NULL,    -- 'private', 'shared', 'public'
    password_hash   TEXT,              -- optional, for password-protected
    snapshot_url    TEXT,              -- S3 key of latest full snapshot
    state_vector    BYTEA,             -- Y.js state vector at last snapshot
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at      TIMESTAMPTZ
);
CREATE INDEX idx_documents_owner ON documents(owner_id);

-- Updates log (incremental CRDT updates)
CREATE TABLE document_updates (
    id              BIGSERIAL PRIMARY KEY,
    document_id     UUID NOT NULL REFERENCES documents(id),
    update_data     BYTEA NOT NULL,    -- binary CRDT update
    user_id         UUID,               -- who applied (can be null for anon)
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_doc_updates_doc_id ON document_updates(document_id, id);

-- Snapshots (periodic full state)
CREATE TABLE document_snapshots (
    id              BIGSERIAL PRIMARY KEY,
    document_id     UUID NOT NULL,
    s3_key          TEXT NOT NULL,
    size_bytes      INT,
    update_count_at_snapshot BIGINT,    -- so we know which updates to garbage collect
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Sharing
CREATE TABLE document_collaborators (
    document_id     UUID,
    user_id         UUID,
    permission      TEXT NOT NULL,    -- 'view', 'edit', 'admin'
    added_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (document_id, user_id)
);

CREATE TABLE document_share_links (
    id              UUID PRIMARY KEY,
    document_id     UUID,
    token           TEXT UNIQUE NOT NULL,
    permission      TEXT NOT NULL,
    expires_at      TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Comments
CREATE TABLE comments (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id     UUID NOT NULL,
    user_id         UUID NOT NULL,
    parent_id       UUID,              -- threaded replies
    anchor          JSONB,              -- {"node_id": "...", "offset": 5}
    text            TEXT NOT NULL,
    resolved        BOOL NOT NULL DEFAULT false,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Presence (ephemeral; in Redis, not DB)
-- Stored in Redis: "presence:doc:{doc_id}" → set of {user_id: cursor_info}
```

---

## 8. WebSocket Endpoint

### Protocol

```
WS /ws/doc/{document_id}?token={jwt or share_token}

Messages (binary frames):
  ─────────────────────────────
  Client → Server:
    type=0:  SYNC_STEP_1 (state vector)
    type=1:  SYNC_STEP_2 (initial state)
    type=2:  UPDATE (incremental CRDT update)
    type=3:  AWARENESS (presence: cursor pos, user info)

  Server → Client:
    type=0:  SYNC_STEP_1 (server's state vector)
    type=1:  SYNC_STEP_2 (server's diff)
    type=2:  UPDATE (others' updates)
    type=3:  AWARENESS (others' presence)
    type=4:  ERROR (auth, doc not found, etc.)
```

This matches the y-websocket protocol used in production.

### FastAPI implementation

```python
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends
import asyncio
import redis.asyncio as redis

app = FastAPI()
r = redis.from_url("redis://localhost")

# Local state: doc_id → set of (websocket, user_info)
local_connections: dict[str, set] = {}

@app.websocket("/ws/doc/{document_id}")
async def doc_ws(websocket: WebSocket, document_id: str):
    # 1. Authenticate
    token = websocket.query_params.get("token")
    user = await authenticate(token)  # or anon
    doc = await get_doc_with_access_check(document_id, user)
    if not doc:
        await websocket.close(4404, "Not found / no access")
        return

    await websocket.accept()

    # 2. Send initial state (snapshot + recent updates)
    snapshot, updates = await load_doc_state(document_id)
    await websocket.send_bytes(encode_initial_state(snapshot, updates))

    # 3. Add to local connections
    if document_id not in local_connections:
        local_connections[document_id] = set()
        asyncio.create_task(subscribe_doc_channel(document_id))
    local_connections[document_id].add((websocket, user))

    try:
        while True:
            msg = await websocket.receive_bytes()
            # Parse message type
            msg_type = msg[0]
            payload = msg[1:]

            if msg_type == 2:  # UPDATE
                # Persist update
                await db.execute(
                    "INSERT INTO document_updates (document_id, update_data, user_id) "
                    "VALUES ($1, $2, $3)",
                    document_id, payload, user.id if user else None
                )
                # Broadcast via Redis
                await r.publish(f"doc:{document_id}:updates", msg)

            elif msg_type == 3:  # AWARENESS
                # Don't persist; just broadcast
                await r.publish(f"doc:{document_id}:awareness", msg)
                # Update Redis presence map
                await update_presence(document_id, user, payload)

    except WebSocketDisconnect:
        pass
    finally:
        local_connections[document_id].discard((websocket, user))
        if not local_connections[document_id]:
            del local_connections[document_id]
            # No need to unsubscribe Redis — let it linger; will be GC'd
        await remove_presence(document_id, user)


async def subscribe_doc_channel(doc_id):
    """Subscribe to Redis pub/sub for a document; forward to local clients."""
    pubsub = r.pubsub()
    await pubsub.subscribe(f"doc:{doc_id}:updates", f"doc:{doc_id}:awareness")
    try:
        async for msg in pubsub.listen():
            if msg["type"] != "message": continue
            data = msg["data"]
            # Broadcast to all local clients for this doc
            for ws, user in list(local_connections.get(doc_id, [])):
                try:
                    await ws.send_bytes(data)
                except Exception:
                    pass
    except Exception as e:
        logger.error(f"PubSub error for {doc_id}: {e}")
    finally:
        await pubsub.unsubscribe()
        await pubsub.close()
```

### Loading initial state efficiently

```python
async def load_doc_state(doc_id: str) -> tuple[bytes, list[bytes]]:
    """Returns (snapshot_bytes, list_of_recent_updates)."""
    doc = await db.fetch_one("SELECT * FROM documents WHERE id = $1", doc_id)

    snapshot = b""
    if doc.snapshot_url:
        snapshot = await s3.get_object(Bucket=BUCKET, Key=doc.snapshot_url)

    # Only fetch updates since last snapshot
    updates = await db.fetch(
        "SELECT update_data FROM document_updates "
        "WHERE document_id = $1 AND id > $2 "
        "ORDER BY id",
        doc_id, doc.last_snapshot_update_id or 0
    )
    return snapshot, [u.update_data for u in updates]
```

---

## 9. Snapshot Strategy

Updates accumulate. Loading 1000s of updates per new connection = slow.

### Snapshot every N updates or M minutes

```python
@celery.task
def snapshot_doc(doc_id: str):
    """Build full state from all updates; upload to S3."""
    doc = get_doc(doc_id)

    # Fetch all updates
    updates = db.fetch(
        "SELECT update_data FROM document_updates WHERE document_id = $1 ORDER BY id",
        doc_id
    )

    # Apply updates via Y.js (Python port: y-py)
    import y_py as Y
    ydoc = Y.YDoc()
    for u in updates:
        Y.apply_update(ydoc, u.update_data)

    # Get full state
    full_state = Y.encode_state_as_update(ydoc)

    # Upload to S3
    s3_key = f"snapshots/{doc_id}/{int(time.time())}.bin"
    s3.put_object(Bucket=BUCKET, Key=s3_key, Body=full_state)

    # Update doc record
    last_update_id = updates[-1].id
    db.execute(
        "UPDATE documents SET snapshot_url = $1, last_snapshot_update_id = $2 WHERE id = $3",
        s3_key, last_update_id, doc_id
    )

    # Optionally GC: delete old updates that are in snapshot
    # (Be careful: old clients reconnecting might need them)
    db.execute(
        "DELETE FROM document_updates WHERE document_id = $1 AND id <= $2 - 1000",
        doc_id, last_update_id
    )
```

### When to snapshot
- After 500 updates accumulate.
- Every 5 minutes of activity.
- When doc becomes inactive (no users for 10 min).

Trigger from:
- Periodic Celery beat.
- Or on every Nth update.

---

## 10. Presence System

```python
async def update_presence(doc_id, user, awareness_payload):
    """Store user's current cursor/selection in Redis."""
    await r.hset(
        f"presence:doc:{doc_id}",
        user.id,
        json.dumps({
            "name": user.full_name,
            "color": user.cursor_color,
            "data": awareness_payload.hex(),  # or base64
            "last_seen": time.time()
        })
    )
    await r.expire(f"presence:doc:{doc_id}", 300)

async def remove_presence(doc_id, user):
    await r.hdel(f"presence:doc:{doc_id}", user.id)

async def get_presence(doc_id):
    return await r.hgetall(f"presence:doc:{doc_id}")
```

Periodic cleanup:
```python
@celery.task
def cleanup_stale_presence():
    for key in r.scan_iter("presence:doc:*"):
        for user_id, data in r.hgetall(key).items():
            if time.time() - data.last_seen > 60:
                r.hdel(key, user_id)
```

---

## 11. Scaling WebSocket

### Connection counts per server

- Pure Python + asyncio: ~10K WS per process.
- With 8 processes × 10 servers = 800K capacity.
- For 1M+: dedicated tier (Go/Rust) or Centrifugo.

### Sticky sessions

Without sticky sessions: client reconnects to different server → fresh state needed.

```nginx
upstream ws_backend {
    ip_hash;  # sticky by client IP
    server ws1:8000;
    server ws2:8000;
}
```

Or via Cloudflare: enabled by default for WS upgrades.

### Backpressure

```python
class ConnectionManager:
    def __init__(self):
        self.send_queues: dict[WebSocket, asyncio.Queue] = {}

    async def send(self, ws, data):
        q = self.send_queues[ws]
        try:
            q.put_nowait(data)
        except asyncio.QueueFull:
            # Slow client; close connection
            await ws.close(1008, "Backpressure")

    async def send_loop(self, ws):
        q = self.send_queues[ws]
        while True:
            data = await q.get()
            await ws.send_bytes(data)
```

Bounded queue per connection prevents memory blowup from slow clients.

---

## 12. Authorization

### Document access matrix

| Document visibility | Auth required | Who can view | Who can edit |
|---|---|---|---|
| Private | Yes | Owner + invited collaborators | Same |
| Shared | Yes | Owner + share-link holders | Per permission |
| Public | No | Anyone | Edit only if logged in |
| Password-protected | Password | Anyone with password | Same |

```python
async def get_doc_with_access_check(doc_id, user, share_token=None, password=None):
    doc = await db.fetch_one("SELECT * FROM documents WHERE id = $1", doc_id)
    if not doc: return None

    if doc.visibility == "public": return doc

    if doc.visibility == "password" and password:
        if bcrypt.checkpw(password, doc.password_hash): return doc
        return None

    if doc.owner_id == user.id: return doc

    # Check collaborators
    collab = await db.fetch_one(
        "SELECT permission FROM document_collaborators WHERE document_id = $1 AND user_id = $2",
        doc_id, user.id
    )
    if collab: return doc

    # Check share link
    if share_token:
        link = await db.fetch_one(
            "SELECT * FROM document_share_links WHERE token = $1 AND document_id = $2",
            share_token, doc_id
        )
        if link and (not link.expires_at or link.expires_at > now()):
            return doc

    return None
```

---

## 13. Caching Strategy

| Cache | TTL | Purpose |
|---|---|---|
| Doc metadata | 5 min | Reduce DB hits on every WS connect |
| Snapshot URL | 1 hour | Avoid re-fetching from S3 |
| User session | 30 min | Standard JWT auth cache |
| Presence | 30 sec | Live, ephemeral |
| Permissions | 5 min | Cache collaborator list |

---

## 14. API Endpoints (Beyond WebSocket)

```
POST   /docs                          (create doc)
GET    /docs                          (list user's docs)
GET    /docs/{id}                     (metadata)
PATCH  /docs/{id}                     (update title, visibility)
DELETE /docs/{id}                     (soft delete)

POST   /docs/{id}/collaborators       (add)
DELETE /docs/{id}/collaborators/{uid} (remove)
PATCH  /docs/{id}/collaborators/{uid} (change permission)

POST   /docs/{id}/share-links         (create)
DELETE /docs/{id}/share-links/{tid}   (revoke)

GET    /docs/{id}/snapshots           (list versions)
POST   /docs/{id}/snapshots/{sid}/restore (revert)

POST   /docs/{id}/comments            (add comment)
PATCH  /docs/{id}/comments/{cid}      (edit/resolve)
DELETE /docs/{id}/comments/{cid}

GET    /docs/{id}/export?format=pdf   (export)

WS     /ws/doc/{id}?token=...         (real-time sync)
```

---

## 15. Deployment Architecture

### Local development

```yaml
# docker-compose.yml
services:
  api:
    build: .
    ports: ["8000:8000"]
    environment:
      DATABASE_URL: postgres://...
      REDIS_URL: redis://redis:6379

  redis:
    image: redis:7-alpine
    command: redis-server --maxmemory 1gb

  postgres:
    image: postgres:16
```

### Production (AWS)

```
                    ┌──────────────────┐
                    │   Cloudflare     │  (DDoS + edge cache)
                    └────────┬─────────┘
                             │
                    ┌────────▼─────────┐
                    │   AWS ALB        │  (WS support)
                    └────────┬─────────┘
                             │
        ┌────────────────────┼────────────────────┐
        ▼                    ▼                    ▼
   ┌──────────┐         ┌──────────┐         ┌──────────┐
   │  ECS     │   ...   │  ECS     │         │  ECS     │
   │ WS Pod   │         │ WS Pod   │         │ API Pod  │
   └────┬─────┘         └────┬─────┘         └────┬─────┘
        └──────────┬─────────┘                    │
                   ▼                              │
            ┌──────────────┐                      │
            │ElastiCache   │◄─────────────────────┘
            │   Redis      │
            └──────┬───────┘
                   │
            ┌──────▼───────┐
            │  RDS         │
            │  Postgres    │
            └──────────────┘
                   │
                   ▼
              ┌────────┐
              │   S3   │  (snapshots)
              └────────┘
```

### Connection limits per container

```yaml
resources:
  limits:
    memory: 1Gi
    cpu: 1000m
env:
  WORKERS_PER_CORE: 1
  MAX_CONNECTIONS: 5000
```

---

## 16. Senior-Level Showcases

### A. CRDT-based conflict resolution
"No server arbitration; clients merge mathematically. Server is dumb pub/sub broker."

### B. Sticky sessions + Redis pub/sub backplane
"100K concurrent users → distributed across many WS servers. Redis routes events to the right server hosting that client."

### C. Snapshot + incremental updates
"Storage efficient. New clients get snapshot + small diff, not full history replay."

### D. Backpressure handling
"Bounded send queue per connection; slow clients get disconnected, not OOM the server."

### E. State vector sync
"Y.js sync protocol: clients exchange state vectors → only send diff. Bandwidth-efficient."

### F. Offline-first
"Y.js works offline; reconcile on reconnect via CRDT merge."

### G. Geo-distributed via Cloudflare
"Anycast routing puts clients on nearest edge; reduces sync latency globally."

### H. Soft real-time presence
"Cursor positions broadcast at 30 FPS but throttled per-client to 5 Hz to reduce server load."

### I. Document versioning via snapshots
"Each snapshot is a recoverable version. Time-travel by loading older snapshot."

### J. Graceful WebSocket shutdown
"On SIGTERM: stop accepting new connections; existing ones drain over 30s before kill."

---

## 17. Implementation Roadmap

### Week 1: Core sync
- [ ] FastAPI app + WS endpoint scaffold.
- [ ] Y.js integration on client side (small JS demo).
- [ ] Document CRUD (create, list, get).
- [ ] Basic WS protocol (no auth yet).
- [ ] Single-server sync working.

### Week 2: Persistence + scaling
- [ ] Store updates to Postgres.
- [ ] Snapshot via Celery task.
- [ ] Multi-server via Redis pub/sub.
- [ ] Auth via JWT in query param.
- [ ] Presence + cursors via awareness messages.

### Week 3: Polish + features
- [ ] Sharing (links, collaborators).
- [ ] Comments + threads.
- [ ] Version history UI.
- [ ] Anonymous user support.
- [ ] Password-protected docs.

### Week 4: Production
- [ ] Backpressure + connection limits.
- [ ] Graceful shutdown.
- [ ] Sticky sessions via ALB / Cloudflare.
- [ ] Monitoring (WS connection count, message rate).
- [ ] Load test: 10K concurrent WS.
- [ ] Deploy to AWS ECS or similar.

---

## 18. Common Pitfalls & Solutions

### Pitfall 1: Cross-server message loss
**Symptom:** User on Server A sends update; User on Server B never receives.
**Solution:** Redis pub/sub correctly subscribed at each server.

### Pitfall 2: Memory leak from disconnected WS
**Symptom:** WS process memory keeps growing.
**Solution:** Cleanup local_connections + cancel send tasks on disconnect.

### Pitfall 3: Slow clients backing up server
**Symptom:** One slow client blocks broadcasts.
**Solution:** Per-connection bounded queue + drop or close on full.

### Pitfall 4: Storage explosion (millions of updates)
**Symptom:** DB table grows unbounded.
**Solution:** Periodic snapshot + GC old updates after snapshot covers them.

### Pitfall 5: CRDT bugs
**Symptom:** Concurrent updates produce different state on different replicas.
**Solution:** Use Y.js / Automerge — battle-tested. Don't roll your own.

### Pitfall 6: Reconnect storms
**Symptom:** Server restart → 10K clients reconnect simultaneously → CPU spike.
**Solution:** Client-side reconnect with jittered exponential backoff.

### Pitfall 7: WS ping/pong missed
**Symptom:** Dead connections accumulate.
**Solution:** Configure ping interval (20s) + close on missed pongs.

---

## 19. Performance Targets

| Metric | Target |
|---|---|
| WS connection time | < 200ms |
| First sync (initial state) | < 500ms |
| Edit propagation (same region) | < 100ms |
| Edit propagation (cross region) | < 300ms |
| Concurrent connections per pod | 5K |
| Total concurrent | 100K |
| Updates/sec broadcast | 50K |
| Memory per WS conn | ~30KB |

---

## 20. Load Testing

```python
# Use websockets library for load test
import asyncio
import websockets
import json

async def simulate_user(doc_id, n_edits=10):
    async with websockets.connect(f"ws://api.example.com/ws/doc/{doc_id}?token=...") as ws:
        # Wait for initial state
        await ws.recv()

        for _ in range(n_edits):
            # Simulate Y.js update (binary)
            update = b'\x02' + os.urandom(50)
            await ws.send(update)
            await asyncio.sleep(1)

async def main():
    tasks = [simulate_user(f"doc-{i % 100}") for i in range(10000)]
    await asyncio.gather(*tasks)

asyncio.run(main())
```

Run on multiple machines → 10K+ concurrent connections to validate sync.

---

## 21. Resume Bullets

- Built a real-time collaborative editor in FastAPI supporting 100K+ concurrent users with sub-100ms sync latency, CRDT-based conflict resolution via Y.js, and Redis pub/sub backplane across multiple WS servers.
- Designed snapshot + incremental update storage in Postgres + S3, with periodic compaction via Celery; achieved 99.95% uptime SLO.
- Implemented offline-first sync, presence indicators with throttled broadcasts (5Hz), and graceful WebSocket shutdown supporting SIGTERM drain.

---

## 22. Interview Talking Points

- **"How does Google Docs work?"** → OT historically; modern apps use CRDT.
- **"Why CRDT over OT?"** → Decentralized, offline-friendly, server is simpler.
- **"WebSocket scaling to 100K?"** → Multiple servers + sticky sessions + Redis pub/sub.
- **"Handling network partition?"** → CRDT merges on reconnect. Y.js state vector → diff sync.
- **"Storage strategy for forever-growing docs?"** → Periodic snapshots; GC old incremental updates.
- **"Presence at scale?"** → Redis hash with TTL; throttled broadcast; ephemeral state.

---

## 23. Stretch Goals

- **End-to-end encryption (E2EE):** Server stores opaque bytes; only collaborators can decrypt.
- **Voice + video on doc (Figma-style):** WebRTC integration.
- **Plugin system:** Custom widgets on whiteboard.
- **Export to PDF/PNG/Markdown:** Server-side rendering of doc state.
- **AI integration:** "Summarize this doc", "Generate slides" via LLM.
- **Image upload + embedding:** Direct upload to S3 + reference in doc.
- **Comments with replies + reactions.**
- **Granular permissions:** Per-block read/write.
- **WebRTC for peer-to-peer sync:** Reduce server load for small groups.

---

## 24. Tech Stack Summary

| Layer | Choice | Why |
|---|---|---|
| **Backend framework** | FastAPI | Async, WS support, type hints |
| **CRDT lib** | Y.js (client), y-py (server) | Most mature, fast, battle-tested |
| **Message broker** | Redis Pub/Sub | Fast fan-out, low overhead |
| **DB** | Postgres | Relational metadata, BYTEA for updates |
| **Snapshots** | S3 | Cheap binary storage |
| **CDN** | Cloudflare | WS support, edge routing |
| **LB** | AWS ALB | WS-aware sticky sessions |
| **Auth** | JWT + share tokens | Stateless |
| **Task queue** | Celery | Snapshot generation |
| **Monitoring** | Prometheus + Grafana | WS connection count, broadcast rate |

---

## TL;DR

- Real-time collaborative editor in FastAPI + Y.js CRDT.
- WebSocket scaling via Redis pub/sub backplane.
- 100K concurrent, sub-100ms sync.
- Snapshot + incremental updates for efficient storage.
- Offline-first via Y.js merge math.
- **Wow factor:** open two tabs → both edit → live sync. Best demo in interviews.
- 3-4 weeks build time.
