# Project 4: WhatsApp-lite Chat Backend

**Stack:** FastAPI + WebSocket + Cassandra + Redis + Kafka + FCM/APNs + S3
**Build Time:** 4-5 weeks
**Difficulty:** ⭐⭐⭐⭐⭐ (Massive distributed system)
**Resume Strength:** ⭐⭐⭐⭐⭐ (Real-time + messaging + scale)

---

## 1. Project Overview & Business Problem

### What it is
A scalable messaging backend supporting 1:1 chat, group chat, media sharing, read receipts, typing indicators, and offline delivery — like WhatsApp / Telegram / Signal.

### Why build this
- **Most comprehensive real-time project:** covers WebSocket, Cassandra, push notifications, media.
- **Industry-standard scaling challenges:** 1M+ concurrent connections, billions of messages.
- **Career-relevant:** Slack, Discord, WhatsApp, Telegram all use similar architecture.

### Real-world analogues
- WhatsApp
- Telegram
- Signal
- Slack (DMs)
- Discord
- Messenger
- Microsoft Teams

---

## 2. Requirements

### Functional
- **1:1 chat**: Send text, images, videos, files between users.
- **Group chat**: Up to 1000 members per group.
- **Real-time delivery**: < 200ms in-region.
- **Read receipts**: Sent ✓, Delivered ✓✓, Read ✓✓ (blue).
- **Typing indicators**.
- **Online presence**.
- **Last seen timestamps**.
- **Message history**: Searchable, paginated.
- **Push notifications**: When user offline.
- **Multi-device sync**: Phone, desktop, web all show same state.
- **Voice messages + media** (images, videos, docs).
- **Reply to specific message**.
- **Message reactions** (emojis).
- **Delete for everyone** / Delete for me.
- **End-to-end encryption** (optional bonus).
- **Block / report users**.

### Non-Functional
- 1M+ concurrent WebSocket connections.
- 5B messages/day → 60K/sec avg, 200K/sec peak.
- p99 delivery latency < 200ms.
- 99.99% availability for messaging.
- Zero message loss after server ack.
- 5-year message retention.
- Multi-region for global users.

---

## 3. Scale Estimation

| Metric | Calculation | Number |
|---|---|---|
| Total users | 100M | |
| Active users (DAU) | 30M | |
| Concurrent WS connections | 1M peak | |
| Messages/day | 5B | |
| Messages/sec avg | 5B / 86400 | ~60K |
| Messages/sec peak | × 3 | ~200K |
| Avg message size | 500 bytes (text) / 2MB (media) | |
| Daily storage | 5B × 500 bytes (text only) | ~2.5 TB/day |
| Yearly storage | × 365 | ~900 TB |
| Media storage | 1B/day × 1MB | ~1 PB/year |
| Push notifications/day | 2B (offline users) | |

---

## 4. High-Level Architecture

```
                       ┌────────────────┐
                       │  Cloudflare    │  (TLS termination, DDoS)
                       └────────┬───────┘
                                │
                       ┌────────▼───────┐
                       │   Load Balancer │
                       └────────┬───────┘
                                │
       ┌────────────────────────┼──────────────────────┐
       │                        │                      │
   ┌───▼──────┐         ┌───────▼─────┐         ┌──────▼───────┐
   │ WS       │         │  HTTP API   │         │  Push        │
   │ Gateway  │         │  (REST)     │         │  Service     │
   │ Pods     │         │  Pods       │         │  Workers     │
   └───┬──────┘         └───────┬─────┘         └──────┬───────┘
       │                        │                      │
       │              ┌─────────▼─────────────┐        │
       │              │     Kafka (msg bus)    │        │
       │              └─────────┬─────────────┘        │
       │                        │                      │
   ┌───▼─────────┬──────────────┼─────────────┐        │
   │             │              │             │        │
┌──▼───────┐ ┌───▼─────┐ ┌──────▼────┐  ┌─────▼──┐ ┌───▼──────┐
│ Cassandra│ │ Redis   │ │Persistence│  │Fanout  │ │FCM/APNs   │
│(messages)│ │(presence│ │Worker     │  │Worker  │ │           │
│          │ │ + state)│ │           │  │        │ │           │
└──────────┘ └─────────┘ └───────────┘  └────────┘ └───────────┘
                                                 │
                                          ┌──────▼──────┐
                                          │     S3      │  (media)
                                          └─────────────┘
```

---

## 5. WebSocket Gateway Layer

### Connection management

Each user maintains 1 WebSocket per device.

```python
# In-memory map per WS gateway process
local_connections: dict[str, dict[str, WebSocket]] = {
    # user_id → {device_id → ws}
}

# In Redis: user_id → device_id → gateway_node_id
# (for routing messages to the right gateway server)
```

```python
@app.websocket("/ws")
async def ws_endpoint(websocket: WebSocket, token: str = Query(...)):
    user = await verify_jwt(token)
    if not user:
        await websocket.close(4001)
        return

    device_id = generate_device_id()
    await websocket.accept()

    # Register in local + Redis
    local_connections.setdefault(user.id, {})[device_id] = websocket
    await redis.hset(f"user_conns:{user.id}", device_id, GATEWAY_NODE_ID)
    await redis.expire(f"user_conns:{user.id}", 86400)

    # Subscribe to user's pub/sub channel
    pubsub_task = asyncio.create_task(subscribe_user_channel(user.id, device_id))

    # Send any pending messages
    await deliver_pending(user, device_id, websocket)

    try:
        while True:
            msg = await websocket.receive_json()
            await handle_client_message(user, device_id, msg)
    except WebSocketDisconnect:
        pass
    finally:
        pubsub_task.cancel()
        local_connections[user.id].pop(device_id, None)
        if not local_connections[user.id]:
            del local_connections[user.id]
        await redis.hdel(f"user_conns:{user.id}", device_id)
```

### Routing messages to right gateway

```python
async def deliver_to_user(target_user_id: str, message: dict):
    """Find which gateway node hosts the user; publish there."""
    # All devices the user has connected
    conns = await redis.hgetall(f"user_conns:{target_user_id}")
    if not conns:
        # User offline: queue + send push
        await queue_offline_message(target_user_id, message)
        await send_push_notification(target_user_id, message)
        return

    # Publish to each gateway node
    for device_id, gateway_node in conns.items():
        await redis.publish(f"gateway:{gateway_node}", json.dumps({
            "to_user": target_user_id,
            "to_device": device_id,
            "message": message
        }))


async def subscribe_user_channel(user_id, device_id):
    """Each gateway subscribes to its own channel."""
    pubsub = redis.pubsub()
    await pubsub.subscribe(f"gateway:{GATEWAY_NODE_ID}")
    try:
        async for msg in pubsub.listen():
            if msg["type"] != "message": continue
            data = json.loads(msg["data"])
            if data["to_user"] == user_id and data["to_device"] == device_id:
                ws = local_connections.get(user_id, {}).get(device_id)
                if ws:
                    await ws.send_json(data["message"])
    finally:
        await pubsub.unsubscribe()
```

---

## 6. Message Flow (Critical Path)

### Sending a message

```
1. Sender's client: POST /messages or WS send
   {chat_id, type: "text", content: "Hello"}

2. API server:
   a. Validate sender is in chat
   b. Generate msg_id (Snowflake → time-ordered)
   c. Publish to Kafka topic: chat_events
      key=chat_id (preserves per-chat ordering)
   d. Return 200 + msg_id immediately (client sees ack)

3. Persistence worker (Kafka consumer):
   a. Reads msg → writes to Cassandra (messages_by_chat)
   b. Marks msg as "persisted" → publishes to Kafka topic: persisted_messages

4. Fanout worker:
   a. Reads from persisted_messages
   b. Lookup chat members
   c. For each member's connected device:
      - Publish to that device's gateway via Redis
   d. For offline members:
      - Queue in Cassandra (offline_messages)
      - Trigger push notification

5. Receiver's WS gateway:
   a. Gets event from Redis pub/sub
   b. Forwards to local WS connection
   c. Receiver client renders msg
```

### Why this design?
- **Kafka in middle:** durability + decoupling. If persistence worker dies, no data lost.
- **Single partition per chat:** ordering preserved within a chat.
- **Async fanout:** sender doesn't wait for fanout to all receivers.
- **Per-device delivery:** multi-device users get all updates.

### Latency budget
| Step | Time |
|---|---|
| Client → API | 30ms |
| API → Kafka write | 5ms |
| Kafka → Persistence worker | 10ms |
| Persist to Cassandra | 20ms |
| Persistence → Fanout | 10ms |
| Redis pub/sub fanout | 5ms |
| Gateway → Receiver | 30ms |
| **Total p50** | **~100ms** |

---

## 7. Data Model

### Cassandra schemas

```sql
-- Messages partitioned by chat for "fetch chat history" queries
CREATE TABLE messages_by_chat (
    chat_id        UUID,
    msg_id         BIGINT,     -- Snowflake, time-ordered
    sender_id      UUID,
    type           TEXT,        -- 'text', 'image', 'video', 'voice', 'file'
    content        TEXT,         -- text body OR media URL
    media_meta     TEXT,         -- JSON: {size, mime_type, thumbnail_url}
    reply_to       BIGINT,       -- msg_id of replied-to msg, null otherwise
    reactions      MAP<TEXT, SET<UUID>>,  -- emoji → set of user_ids
    sent_at        TIMESTAMP,
    edited_at      TIMESTAMP,
    deleted_at     TIMESTAMP,
    PRIMARY KEY (chat_id, msg_id)
) WITH CLUSTERING ORDER BY (msg_id DESC);

-- For "fetch user's recent activity"
CREATE TABLE messages_by_user (
    user_id     UUID,
    msg_id      BIGINT,
    chat_id     UUID,
    PRIMARY KEY (user_id, msg_id)
) WITH CLUSTERING ORDER BY (msg_id DESC);

-- Offline message queue (per user)
CREATE TABLE offline_messages (
    user_id     UUID,
    msg_id      BIGINT,
    chat_id     UUID,
    sender_id   UUID,
    content     TEXT,
    sent_at     TIMESTAMP,
    PRIMARY KEY (user_id, msg_id)
) WITH CLUSTERING ORDER BY (msg_id DESC) AND DEFAULT_TIME_TO_LIVE = 2592000;  -- 30 days

-- Read receipts (per message, per user)
CREATE TABLE message_read_status (
    chat_id     UUID,
    msg_id      BIGINT,
    user_id     UUID,
    read_at     TIMESTAMP,
    PRIMARY KEY ((chat_id, msg_id), user_id)
);
```

### Postgres schemas (relational metadata)

```sql
-- Users
CREATE TABLE users (
    id              UUID PRIMARY KEY,
    phone_number    TEXT UNIQUE NOT NULL,
    display_name    TEXT,
    profile_pic_url TEXT,
    about           TEXT,
    last_seen_at    TIMESTAMPTZ,
    is_online       BOOL DEFAULT false,
    created_at      TIMESTAMPTZ DEFAULT now()
);

-- Chats (both 1:1 and group)
CREATE TABLE chats (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    type            TEXT NOT NULL,    -- 'one_to_one', 'group'
    name            TEXT,              -- null for 1:1
    avatar_url      TEXT,
    created_by      UUID,
    created_at      TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE chat_members (
    chat_id         UUID NOT NULL REFERENCES chats(id),
    user_id         UUID NOT NULL REFERENCES users(id),
    role            TEXT DEFAULT 'member',  -- 'admin', 'member'
    joined_at       TIMESTAMPTZ DEFAULT now(),
    last_read_msg_id BIGINT,   -- for unread count
    notification_pref TEXT DEFAULT 'all',  -- 'all', 'mentions', 'none'
    PRIMARY KEY (chat_id, user_id)
);
CREATE INDEX idx_chat_members_user ON chat_members(user_id);

-- Devices (multi-device support)
CREATE TABLE devices (
    id              UUID PRIMARY KEY,
    user_id         UUID NOT NULL,
    type            TEXT,    -- 'android', 'ios', 'web', 'desktop'
    push_token      TEXT,
    last_active_at  TIMESTAMPTZ,
    created_at      TIMESTAMPTZ DEFAULT now()
);

-- Contacts / friends
CREATE TABLE contacts (
    user_id         UUID,
    contact_id      UUID,
    nickname        TEXT,
    added_at        TIMESTAMPTZ DEFAULT now(),
    PRIMARY KEY (user_id, contact_id)
);

-- Blocked users
CREATE TABLE blocked_users (
    user_id         UUID,
    blocked_user_id UUID,
    blocked_at      TIMESTAMPTZ DEFAULT now(),
    PRIMARY KEY (user_id, blocked_user_id)
);
```

---

## 8. Online Presence

```python
# When user connects WS
async def on_connect(user_id):
    await redis.set(f"presence:{user_id}", "online", ex=60)
    # Publish event to user's contacts
    contacts = await get_user_contacts(user_id)
    for c in contacts:
        await redis.publish(f"presence:contacts:{c}", json.dumps({
            "user_id": user_id, "status": "online"
        }))

# Periodic heartbeat extends TTL
async def heartbeat_loop(user_id):
    while True:
        await redis.expire(f"presence:{user_id}", 60)
        await asyncio.sleep(30)

# On disconnect
async def on_disconnect(user_id):
    last_seen = datetime.utcnow()
    await redis.delete(f"presence:{user_id}")
    await db.execute("UPDATE users SET last_seen_at = $1, is_online = false WHERE id = $2",
                    last_seen, user_id)
    # Publish offline event
    contacts = await get_user_contacts(user_id)
    for c in contacts:
        await redis.publish(f"presence:contacts:{c}", json.dumps({
            "user_id": user_id, "status": "offline", "last_seen": last_seen.isoformat()
        }))

# Check status
async def get_presence(user_id):
    status = await redis.get(f"presence:{user_id}")
    if status:
        return {"status": "online"}
    last_seen = await db.fetch_val("SELECT last_seen_at FROM users WHERE id = $1", user_id)
    return {"status": "offline", "last_seen": last_seen}
```

### Typing indicators

```python
async def set_typing(chat_id, user_id):
    await redis.set(f"typing:{chat_id}:{user_id}", "1", ex=5)
    # Broadcast to chat members
    members = await get_chat_members(chat_id, exclude=user_id)
    for m in members:
        await deliver_to_user(m, {"type": "typing", "chat_id": chat_id, "user_id": user_id})

async def stop_typing(chat_id, user_id):
    await redis.delete(f"typing:{chat_id}:{user_id}")
    # Broadcast
```

Typing auto-expires after 5s if user stops sending updates.

---

## 9. Read Receipts (3 levels)

### Sent ✓
Server received message, before persisted.

### Delivered ✓✓ (gray)
Receiver's device received the message.

### Read ✓✓ (blue)
Receiver opened the chat with this message visible.

```python
# Receiver client → POST /messages/read with msg_ids
@app.post("/messages/read")
async def mark_read(req: ReadRequest, user=Depends(get_user)):
    for msg_id in req.msg_ids:
        await cassandra.execute(
            "INSERT INTO message_read_status (chat_id, msg_id, user_id, read_at) "
            "VALUES (?, ?, ?, ?)",
            req.chat_id, msg_id, user.id, datetime.utcnow()
        )

    # Update user's last_read_msg_id
    max_msg_id = max(req.msg_ids)
    await db.execute(
        "UPDATE chat_members SET last_read_msg_id = $1 "
        "WHERE chat_id = $2 AND user_id = $3 AND last_read_msg_id < $1",
        max_msg_id, req.chat_id, user.id
    )

    # Notify sender(s)
    senders = await get_msg_senders(req.chat_id, req.msg_ids)
    for sender_id in senders:
        if sender_id != user.id:
            await deliver_to_user(sender_id, {
                "type": "read_receipt",
                "chat_id": req.chat_id,
                "reader_id": user.id,
                "msg_ids": req.msg_ids
            })

    return {"ok": True}
```

### Unread count

```python
@app.get("/chats/{chat_id}/unread_count")
async def unread_count(chat_id: UUID, user=Depends(get_user)):
    member = await db.fetch_one(
        "SELECT last_read_msg_id FROM chat_members WHERE chat_id = $1 AND user_id = $2",
        chat_id, user.id
    )
    count = await cassandra.fetch_val(
        "SELECT count(*) FROM messages_by_chat WHERE chat_id = ? AND msg_id > ?",
        chat_id, member.last_read_msg_id or 0
    )
    return {"unread": count}
```

---

## 10. Media Handling

Images, videos, files.

### Upload flow
```
1. Client → POST /media/upload-init {filename, size, mime_type}
2. Server validates, returns presigned S3 PUT URL + media_id
3. Client uploads directly to S3
4. Client → POST /messages {chat_id, type: "image", media_id}
5. Server includes media URL in message
6. Receivers fetch via signed GET URL (TTL 24h)
```

### Image processing pipeline
```
S3 upload → S3 event → Lambda → 
  - Generate thumbnail (200x200)
  - Compress original
  - Strip EXIF (privacy)
  - Upload to S3
  - Update DB with derived URLs
```

```python
# Pseudo-Lambda
def process_media(event):
    s3_key = event["s3"]["object"]["key"]
    media_id = parse_media_id(s3_key)

    img = download_from_s3(s3_key)
    img = strip_exif(img)

    thumb = img.thumbnail((200, 200))
    upload_to_s3(f"thumbnails/{media_id}.webp", thumb)

    compressed = compress(img, quality=85)
    upload_to_s3(f"compressed/{media_id}.webp", compressed)

    update_media_record(media_id, status="ready",
                       thumb_url=..., compressed_url=...)
```

### Video transcoding
- Convert to HLS for adaptive streaming.
- Use AWS MediaConvert or FFmpeg in Lambda.
- Generate thumbnail from first frame.
- 480p / 720p / 1080p variants.

---

## 11. Push Notifications

Receiver offline → push.

```python
async def send_push_notification(user_id, message):
    # Skip if user disabled notifications for this chat
    member = await get_chat_member(message["chat_id"], user_id)
    if member.notification_pref == "none":
        return

    # Get all devices for user
    devices = await db.fetch(
        "SELECT type, push_token FROM devices WHERE user_id = $1 AND push_token IS NOT NULL",
        user_id
    )

    sender = await get_user(message["sender_id"])
    chat = await get_chat(message["chat_id"])

    title = sender.display_name if chat.type == "one_to_one" else chat.name
    body = format_preview(message)

    for device in devices:
        if device.type in ("android", "ios"):
            await fcm_send(device.push_token, title, body, data={"chat_id": str(chat.id)})
        elif device.type == "web":
            await web_push_send(device.push_token, title, body)
```

### Batching for efficiency
If user offline → 50 messages arrive → batch into 1 notification ("50 new messages from X").

```python
async def maybe_batch_push(user_id, message):
    pending_key = f"push_batch:{user_id}"
    pending = await redis.incr(pending_key)
    if pending == 1:
        await redis.expire(pending_key, 10)
        # Schedule batch flush in 5s
        asyncio.create_task(flush_batch(user_id, delay=5))
    return pending

async def flush_batch(user_id, delay):
    await asyncio.sleep(delay)
    count = await redis.get(f"push_batch:{user_id}")
    await redis.delete(f"push_batch:{user_id}")

    if int(count) == 1:
        # Send original detailed notification
        ...
    else:
        await send_aggregated_push(user_id, f"{count} new messages")
```

---

## 12. Group Chat Fanout

### For small groups (≤ 50 members)
Direct fanout works. Same as 1:1, just send to N people.

### For large groups (1000 members)
Fanout in batch:
```python
async def fanout_group_message(chat_id, message):
    members = await get_chat_members(chat_id)

    # Split into batches of 100
    for i in range(0, len(members), 100):
        batch = members[i:i+100]
        asyncio.create_task(deliver_batch(batch, message))

async def deliver_batch(user_ids, message):
    # Parallel deliveries
    await asyncio.gather(*[deliver_to_user(uid, message) for uid in user_ids])
```

### For huge groups (broadcast channels — Telegram-style)
Different model: read-fanout instead of write-fanout.
- Message stored once.
- Subscribers poll / are notified to fetch.
- No per-member push.
- Used for Channels (read-only broadcast).

---

## 13. End-to-End Encryption (Stretch)

For privacy-focused chat (Signal protocol).

### Key exchange
- Each user has long-term identity key (Curve25519).
- Each device has signed prekey + one-time prekeys uploaded to server.
- Diffie-Hellman key exchange → session key.

### Encryption
- Client encrypts message with session key (AES-256-GCM).
- Sends ciphertext to server.
- Server stores + forwards opaque bytes.
- Receiver decrypts with shared session key.

### Server's role
- Distributes prekeys.
- Stores ciphertext (can't read).
- Can't generate metadata about message contents.

### Trade-offs
- ✗ No server-side search.
- ✗ No "view messages in web" without device sync.
- ✓ True privacy.

Most apps offer optional E2EE per-chat.

---

## 14. Searching Messages

### Per-user index in Elasticsearch
```
{
  "user_id": "abc",
  "chat_id": "xyz",
  "msg_id": 12345,
  "content": "Hello World",
  "sender_id": "def",
  "sent_at": "..."
}
```

User searches "where did Alice send me the recipe?":
```python
es.search(body={
    "query": {
        "bool": {
            "must": [
                {"term": {"user_id": current_user.id}},
                {"match": {"content": "recipe"}},
            ],
            "filter": [
                {"term": {"sender_id": alice.id}}
            ]
        }
    }
})
```

User-scoped index ensures privacy + scalability.

---

## 15. Multi-Device Sync

Same user on phone + desktop + web.

### Strategy
- Each device gets its own WS connection.
- All messages delivered to all devices simultaneously.
- Read receipts shared (one device reads → all show as read).
- Typing indicator unique per device.

```python
# Deliver to all devices
async def deliver_to_user(user_id, message):
    conns = await redis.hgetall(f"user_conns:{user_id}")
    for device_id, gateway in conns.items():
        await deliver_to_device(user_id, device_id, gateway, message)
```

### Device-specific delivery state
"Did Phone deliver this message?" tracked separately from desktop.

---

## 16. APIs

```
# Auth (phone OTP)
POST /auth/send-otp        { phone_number }
POST /auth/verify-otp      { phone_number, otp }
POST /auth/refresh         { refresh_token }

# Profile
GET    /me
PATCH  /me                                  { display_name, about }
POST   /me/avatar                           (upload picture)

# Chats
GET    /chats                              (list with last message preview)
POST   /chats                              { type, members }    (create)
GET    /chats/{id}
DELETE /chats/{id}                          (leave/delete for me)
PATCH  /chats/{id}                         (rename group, etc.)

# Members
POST   /chats/{id}/members                  (add member, admin only)
DELETE /chats/{id}/members/{user_id}        (remove)

# Messages
GET    /chats/{id}/messages?before=<msg_id>&limit=50
POST   /chats/{id}/messages                 { type, content, reply_to? }
DELETE /messages/{msg_id}                  ?for=me|everyone
PATCH  /messages/{msg_id}                  (edit text)
POST   /messages/{msg_id}/reactions        { emoji }
DELETE /messages/{msg_id}/reactions        { emoji }
POST   /messages/read                       { chat_id, msg_ids }

# Media
POST   /media/upload-init                   { filename, size, mime_type }
GET    /media/{id}                          (signed download URL)

# Contacts
GET    /contacts
POST   /contacts                            { phone_number }
DELETE /contacts/{id}

# Block
POST   /users/{id}/block
DELETE /users/{id}/block

# Presence
GET    /users/{id}/presence

# WebSocket
WS    /ws?token=<jwt>
```

---

## 17. Caching Strategy

| Cache | Key | TTL |
|---|---|---|
| User profile | `user:{id}` | 5 min |
| Chat metadata | `chat:{id}` | 5 min |
| Chat members | `chat:{id}:members` | 1 min |
| User's chats list | `user:{id}:chats` | 30 sec |
| Online presence | `presence:{user_id}` | 60s (heartbeat) |
| Typing indicator | `typing:{chat_id}:{user_id}` | 5s |
| Unread count | `unread:{user_id}:{chat_id}` | live (incremented) |
| Recent messages | `chat:{id}:recent` | 5 min |
| WS connection map | `user_conns:{user_id}` | 24h |

---

## 18. Deployment Architecture

### Production scale stack

```
1M concurrent WS users:
  - 100 WS gateway pods (10K conn each)
  - 50 API pods (REST)
  - 10 fanout worker pods
  - 5 persistence worker pods
  - 5 push notification workers

Cassandra: 12-node cluster (3 racks × 4 nodes)
Kafka: 5 brokers, 60 partitions per topic
Redis: 12-node cluster (6 masters + 6 replicas)
Postgres: 3 read replicas + 1 primary
S3: standard for media
```

### Regional deployment
- Multi-region (us-east, us-west, eu-west, ap-south).
- Each region has full stack.
- Cross-region replication via Kafka MirrorMaker.
- User connects to nearest region.
- Cassandra multi-DC replication.

---

## 19. Senior-Level Showcases

### A. WebSocket gateway tier separate from API
Gateways are simple, stateful (per-connection). API is stateless REST. Different scaling.

### B. Kafka in the send path
Producer waits for Kafka ack (5ms), not final delivery. Massive throughput.

### C. Cassandra partition strategy
Partition by `chat_id` → all messages of a chat co-located. Fast `SELECT ORDER BY msg_id LIMIT 50`.

### D. Snowflake IDs for message ordering
Time-ordered IDs → DB indexes happy + chronological without separate timestamp column.

### E. Multi-device delivery via per-device tracking
Each device has its own delivery state. Doesn't break if one device offline.

### F. Push notification batching
50 messages → 1 push notification. Avoids spam.

### G. Online/last-seen via Redis with heartbeat
Lightweight; auto-expires; broadcasts only to contacts.

### H. Read receipts via Cassandra writes
Idempotent; eventually consistent; fast.

### I. Media via S3 + Lambda processing
Avoids API bandwidth bottleneck.

### J. Multi-region Cassandra
Tunable consistency (LOCAL_QUORUM for fast reads, QUORUM for cross-region).

---

## 20. Implementation Roadmap

### Week 1: Core auth + chat
- [ ] Phone OTP auth.
- [ ] Chat creation (1:1).
- [ ] Send/receive messages via REST.
- [ ] Basic message storage.

### Week 2: WebSocket
- [ ] WS gateway pod.
- [ ] Real-time message delivery.
- [ ] Online presence.
- [ ] Multi-device basic support.

### Week 3: Persistence + scale
- [ ] Cassandra schemas + adapter.
- [ ] Kafka in send path.
- [ ] Persistence worker.
- [ ] Fanout worker.
- [ ] Redis pub/sub backplane.

### Week 4: Features
- [ ] Group chat.
- [ ] Read receipts.
- [ ] Typing indicators.
- [ ] Media upload (S3 presigned).
- [ ] Image thumbnails (Lambda).

### Week 5: Production
- [ ] Push notifications (FCM/APNs).
- [ ] Offline message queue.
- [ ] Search via Elasticsearch.
- [ ] Multi-region deployment.
- [ ] Load test: 100K concurrent.
- [ ] Monitoring + alerts.

---

## 21. Common Pitfalls & Solutions

### Pitfall 1: Lost messages on server crash
**Symptom:** Messages sent during crash never delivered.
**Solution:** Kafka in send path; durability before client ack.

### Pitfall 2: Out-of-order messages
**Symptom:** Messages appear scrambled.
**Solution:** Snowflake IDs + partition key on chat_id; Cassandra orders by clustering key.

### Pitfall 3: Push notification storm
**Symptom:** 100 messages → 100 notifications → uninstall.
**Solution:** Batch notifications with 5s debounce.

### Pitfall 4: Hot chat partition
**Symptom:** Celebrity / viral group → single Cassandra partition overwhelmed.
**Solution:** Compound partition key `(chat_id, time_bucket)`.

### Pitfall 5: WS reconnect storm
**Symptom:** Gateway restart → all clients reconnect at once.
**Solution:** Jittered exponential backoff on client; staggered restarts on server.

### Pitfall 6: Multi-device read receipt confusion
**Symptom:** Phone reads → desktop still shows unread.
**Solution:** Server-side last_read_msg_id; all devices fetch from this.

### Pitfall 7: Cassandra tombstones building up
**Symptom:** Delete operations slow over time.
**Solution:** TTL-based deletion (auto-cleanup) rather than DELETE statements.

---

## 22. Performance Benchmarks

| Metric | Target |
|---|---|
| Message send → receive (same region) | < 200ms p99 |
| Cross-region delivery | < 500ms p99 |
| WS connection time | < 200ms |
| Concurrent WS per pod | 10K |
| Message throughput | 200K/sec |
| Push delivery latency | < 5s |
| Media upload (signed URL) | < 100ms (URL gen) |
| Search query | < 200ms |

---

## 23. Load Testing

```python
# Simulate 100K concurrent users
import asyncio, websockets, random

async def user_session(user_id):
    async with websockets.connect(f"ws://api.example.com/ws?token=...") as ws:
        while True:
            # Random behavior
            action = random.choice(["send", "send", "type", "read", "idle"])
            if action == "send":
                await ws.send(json.dumps({
                    "type": "message",
                    "chat_id": random.choice(user_chats[user_id]),
                    "content": f"Hello from {user_id}"
                }))
            elif action == "idle":
                await asyncio.sleep(10)

async def main():
    tasks = [user_session(uid) for uid in range(100000)]
    await asyncio.gather(*tasks)
```

Run on 10 machines × 10K connections each.

---

## 24. Resume Bullets

- Built a high-scale messaging backend in FastAPI supporting 1M+ concurrent WebSocket connections and 200K messages/sec with Kafka-backed durability and Cassandra storage.
- Designed multi-device sync, read receipts, and push notifications (FCM/APNs) with notification batching, achieving p99 delivery < 200ms.
- Implemented Redis pub/sub-based gateway routing for cross-server WS message broadcasting in a multi-region active-active architecture.

---

## 25. Interview Talking Points

- **"How would you design WhatsApp?"** → This entire doc is the answer.
- **"Why Cassandra over Postgres for messages?"** → Write-heavy, time-series-like, predictable partition.
- **"How do messages stay ordered in a chat?"** → Snowflake IDs + Cassandra clustering key.
- **"What if Cassandra is slow?"** → Tunable consistency (QUORUM vs ONE); local DC reads.
- **"How do you scale WebSocket to 1M?"** → Gateway tier + Redis pub/sub + sticky sessions.
- **"Multi-device sync — how?"** → Per-device WS; centralized state in Cassandra.
- **"Push notifications at scale?"** → Async worker reading from Kafka; batched delivery.

---

## 26. Stretch Goals

- **End-to-end encryption (Signal protocol).**
- **Voice & video calls (WebRTC + SFU like mediasoup).**
- **Stickers & GIFs.**
- **Status / Stories (24h).**
- **Disappearing messages.**
- **Polls in chat.**
- **Voice messages with transcription (Whisper).**
- **Smart replies (AI suggestions).**
- **Message translation (per-user language).**
- **Bots / API (like Telegram bots).**

---

## 27. Tech Stack Summary

| Layer | Choice | Why |
|---|---|---|
| **API + WS** | FastAPI | Async, WS native |
| **Message DB** | Cassandra | Write-heavy, partitionable |
| **Metadata DB** | Postgres | Relational, multi-table |
| **Cache** | Redis Cluster | Presence, pub/sub backplane |
| **Queue** | Kafka | Durability, decoupling |
| **Media** | S3 + Lambda | Cheap, scalable |
| **Push** | FCM + APNs | Native push delivery |
| **Search** | Elasticsearch | Full-text |
| **CDN** | Cloudflare | Edge TLS, DDoS |
| **Container** | Docker + K8s | Scaling |
| **Monitoring** | Prometheus + Grafana + Sentry | Observability |

---

## TL;DR

- 1M+ concurrent WebSocket connections.
- 200K messages/sec via Kafka pipeline.
- Cassandra for write-heavy message storage.
- Redis pub/sub for cross-server delivery.
- Multi-device sync; push notifications when offline.
- Read receipts, typing, presence, media uploads.
- 4-5 weeks build time.
- **Most comprehensive real-time messaging project; covers nearly every system design pattern.**
