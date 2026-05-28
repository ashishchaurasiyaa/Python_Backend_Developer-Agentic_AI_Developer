# Design Slack / Workplace Chat

---

## 1. Requirements

### Functional
- 1:1 messaging, group channels, threads.
- Real-time delivery (< 200ms typical, < 1s worst case).
- Presence (online / away / typing).
- Read receipts, message reactions.
- File sharing (images, docs, video).
- Search across messages.
- @mentions and notifications (in-app, mobile push, email).
- Workspace separation (each org is isolated).
- Message history (last 5 years).

### Non-Functional
- 50M DAU, 500K concurrent users per region.
- 1B messages/day.
- p99 message delivery < 1s.
- Message durability: zero loss after server ack.
- Search latency < 200ms.
- 99.95% availability.

---

## 2. Scale Estimation

| Metric | Calc | Number |
|---|---|---|
| Total messages/sec | 1B / 86400 | ~12K msg/s avg |
| Peak (3x) | 12K × 3 | ~36K msg/s |
| Avg message size | 200 bytes text + metadata | ~500 bytes |
| Storage daily | 1B × 500 bytes | ~500 GB/day |
| Storage 5 years | 500GB × 1825 | ~900 TB |
| Active WebSocket conns | 500K concurrent | × 10KB state = 5GB |
| Search index size | 30% of messages text | ~250 TB |

---

## 3. High-Level Architecture

```
                    ┌──────────────┐
                    │  Load Balancer│
                    └──────┬───────┘
                           │
        ┌──────────────────┼─────────────────────┐
        │                  │                     │
  ┌─────▼────┐      ┌──────▼──────┐       ┌──────▼──────┐
  │ HTTP API │      │ WebSocket    │       │  Push       │
  │ (REST)   │      │ Gateway      │       │  Service    │
  └─────┬────┘      └──────┬──────┘        └──────┬──────┘
        │                  │                       │
        │           ┌──────▼─────────────────┐    │
        │           │   Kafka (msg-bus)      │    │
        │           └──┬─────┬──────┬────────┘    │
        │              │     │      │             │
        │      ┌───────▼┐ ┌──▼───┐ ┌▼──────────┐  │
        │      │Persist │ │Index │ │Notification│  │
        │      │Worker  │ │Worker│ │  Worker    │  │
        │      └────────┘ └──────┘ └───────────┘  │
        │           │        │         │          │
  ┌─────▼──────┐ ┌─▼────┐  ┌─▼───┐ ┌──▼──────────▼┐
  │ Auth/User  │ │ Msg  │  │ ES  │ │ FCM / APNs    │
  │   DB       │ │  DB  │  │     │ │               │
  │ (Postgres) │ │(Cass)│  │     │ └───────────────┘
  └────────────┘ └──────┘  └─────┘
                                   ┌──────┐
                                   │  S3   │ (files)
                                   └──────┘
```

---

## 4. WebSocket Connection Layer

### Connection management
Each user maintains 1 WebSocket per device. Server maintains:
- `connection_id → user_id` map (in-memory).
- `user_id → list[connection_id]` (Redis hash, since user_id may have multiple devices).
- `connection_id → server_node` (for cross-node routing).

```python
class WSGateway:
    def __init__(self):
        self.local_conns: dict[str, WebSocket] = {}  # local map

    async def connect(self, user_id: str, ws: WebSocket):
        conn_id = f"{node_id}:{uuid4()}"
        self.local_conns[conn_id] = ws
        await redis.hset(f"user_conns:{user_id}", conn_id, node_id)
        await redis.expire(f"user_conns:{user_id}", 86400)

    async def disconnect(self, user_id: str, conn_id: str):
        del self.local_conns[conn_id]
        await redis.hdel(f"user_conns:{user_id}", conn_id)
```

### Server-to-server message routing
When a message lands on Server A for a user connected to Server B:
- Server A looks up user's node in Redis.
- Publishes to Kafka topic `direct.{node_b}` or per-node Redis Pub/Sub.
- Server B reads, forwards to local WebSocket.

---

## 5. Message Send Flow

```
1. Client → POST /messages or WebSocket send
2. API server validates auth, channel membership
3. API server generates msg_id (Snowflake)
4. API server writes to Kafka: topic=channel_events, key=channel_id
   (preserves ordering per channel via partition key)
5. API server returns 200 with msg_id (client sees confirmation)

6. Persist worker reads from Kafka → writes to Cassandra (messages table)
7. Index worker reads from Kafka → indexes in Elasticsearch
8. Fanout worker reads from Kafka → identifies recipients → publishes to WS gateways
9. Notification worker reads from Kafka → checks recipient preferences → sends push/email
```

**Key insight:** Client gets ack BEFORE persistence (after Kafka write). Kafka provides durability.

---

## 6. Data Model

### Cassandra (message store, write-heavy)

```sql
-- Optimized for "fetch last N messages in channel"
CREATE TABLE messages_by_channel (
    channel_id     UUID,
    msg_id         BIGINT,        -- Snowflake, time-ordered
    user_id        UUID,
    content        TEXT,
    thread_id      BIGINT,        -- null if not a thread reply
    created_at     TIMESTAMP,
    reactions      MAP<TEXT, SET<UUID>>,  -- emoji → set of user_ids
    PRIMARY KEY (channel_id, msg_id)
) WITH CLUSTERING ORDER BY (msg_id DESC);

-- Optimized for "fetch user's recent activity"
CREATE TABLE messages_by_user (
    user_id        UUID,
    msg_id         BIGINT,
    channel_id     UUID,
    PRIMARY KEY (user_id, msg_id)
) WITH CLUSTERING ORDER BY (msg_id DESC);
```

**Partition key:** `channel_id` → all messages of a channel co-located. Hot channels can be problematic (single Slack-wide announce); shard by `(channel_id, time_bucket)` if needed.

### Postgres (workspace metadata)

```sql
CREATE TABLE workspaces (id, name, plan, created_at);
CREATE TABLE users (id, workspace_id, email, name, status);
CREATE TABLE channels (id, workspace_id, name, is_private);
CREATE TABLE channel_members (channel_id, user_id, joined_at, last_read_msg_id);
```

### Redis (presence, ephemeral state)

```
presence:user:{user_id}   → {online|away|offline, last_seen}
typing:channel:{ch_id}    → set of currently typing user_ids (TTL 5s)
unread:user:{user_id}     → hash {channel_id: unread_count}
user_conns:{user_id}      → hash {conn_id: node_id}
```

---

## 7. Real-Time Delivery (Fanout)

For a channel with N members:
```
Message arrives → Kafka
Fanout worker:
  members = get_channel_members(channel_id)  // ~100s typically
  for each member:
    nodes = redis.hgetall(f"user_conns:{member}")
    for each (conn_id, node_id):
      publish to redis pubsub "ws_node:{node_id}" with {conn_id, message}

Each WS gateway subscribes to its own node channel.
On receive: lookup local conn → ws.send(message).
```

**Optimization for huge channels (Slack #general with 10K members):**
- Don't fanout to offline users — they'll fetch via REST on connect.
- Batch sends to same node.

---

## 8. Presence

### Naive: client sends heartbeat every 30s
Updates Redis with `EX 60`. Server expires inactivity → status = offline.

### Scaling presence
500K concurrent users × heartbeat every 30s = 16K writes/sec to Redis. Cheap.

For **online status broadcast** (showing "5 friends online"):
- Subscriber model: client subscribes to friends' presence updates.
- Use Redis Pub/Sub `presence:{user_id}`.

---

## 9. Message Search

### Indexing
- Index worker consumes Kafka → indexes in Elasticsearch.
- Document shape:
```json
{
  "msg_id": 123,
  "workspace_id": "ws1",
  "channel_id": "ch1",
  "user_id": "u1",
  "content": "hello world",
  "created_at": "2024-01-01T00:00:00Z"
}
```

### Search query
```python
GET /workspaces/{ws}/_search
{
  "query": {
    "bool": {
      "must": [
        {"match": {"content": "deploy bug"}},
        {"term": {"workspace_id": "ws1"}}
      ],
      "filter": [
        {"terms": {"channel_id": [user_accessible_channel_ids]}}
      ]
    }
  },
  "sort": [{"created_at": "desc"}]
}
```

**Access control:** Always filter by channel IDs the user is a member of. Done at query level, not post-filter (faster).

### Index strategy
- Hot index: current month (daily).
- Warm: last 6 months (weekly).
- Cold: archived, restored on demand.

---

## 10. Notifications

### Decision tree
```
Message lands → who gets notified?
  - Channel mention (@channel, @here)
  - User mention (@alice)
  - DM recipient
  - User with channel notifications enabled

For each notified user:
  - In-app badge → update Redis unread:user:{uid}, send WS push
  - Push notification → check preferences, send via FCM/APNs
  - Email → only if user offline > 30 min, batch into digest
```

### Push notification design
- Send only when user not actively connected (no WS).
- De-duplicate (same msg → don't send to user already received via WS).
- Quiet hours respected.
- Batch via "you have 5 new messages" if rapid.

---

## 11. Threads

Threads = messages with `thread_id`. Treated as a child collection.

```python
# Reply to msg 123 → message has thread_id=123
# Fetch thread → SELECT * FROM messages WHERE thread_id = 123 ORDER BY msg_id
```

**Counts:** Maintain `thread_reply_count` denormalized on parent message; increment on each reply (eventually consistent via Kafka).

---

## 12. File Uploads

Direct-to-S3 via presigned URLs.

```
1. Client: POST /files/init   { name, size, mime }
2. Server: returns presigned S3 PUT URL + file_id
3. Client: uploads directly to S3
4. Client: POST /messages   { content, file_id }
5. Message stored with file reference
6. CDN serves files via signed URLs
```

**Why not proxy through server:** would saturate API bandwidth. S3 handles parallel multi-part natively.

**Security:** Signed URLs expire in 1h. File access checked via channel membership before signing.

---

## 13. Edit / Delete

```sql
UPDATE messages_by_channel
SET content = ?, edited_at = now()
WHERE channel_id = ? AND msg_id = ?;
```

Then publish `message.edited` event → fanout to all subscribers → they update UI.

Delete = soft delete (`deleted_at` set). Search reindex removes the entry.

---

## 14. Edge Cases & Production Concerns

### Out-of-order messages
With Kafka partition by `channel_id`, within a channel messages are ordered. But what if Server A's clock is ahead?
- Use server-assigned Snowflake IDs, not client timestamps.
- Client UI may show momentarily out-of-order but converges.

### Hot channel (10K users in #general)
- Fanout becomes expensive.
- Use **read-fanout** instead of write-fanout: store the message once, each client polls/subscribes lazily.
- Slack uses hybrid: small channels = write-fanout, big = read-fanout.

### User on poor network
- WebSocket disconnects → reconnect with last_msg_id → server pushes missed messages.
- Client persists unsent messages locally.

### Workspace isolation
- Every query filtered by `workspace_id`.
- DB row-level security as defense in depth.
- ES indices per workspace for largest workspaces.

### Encryption
- At rest: KMS-encrypted Cassandra and ES storage.
- In transit: TLS everywhere.
- End-to-end: optional, hard to do well with search (search requires plaintext).

---

## 15. APIs (sample)

```
POST   /channels/{ch_id}/messages
GET    /channels/{ch_id}/messages?before=<msg_id>&limit=50
PATCH  /messages/{msg_id}          # edit
DELETE /messages/{msg_id}
POST   /messages/{msg_id}/reactions { emoji }
GET    /search?q=...&channel_id=...
POST   /files/init                  # presigned URL
GET    /channels/{ch_id}/members
GET    /presence?user_ids=[...]

WS:    /ws?token=...
       events: message.new, message.edit, presence.update, typing
```

---

## 16. Trade-offs

| Decision | Trade-off |
|---|---|
| Kafka in send path | Adds 5-10ms latency, but gives durability + decoupling |
| Cassandra over Postgres | Write-heavy workload, eventually consistent reads acceptable |
| WS for delivery | Stateful → harder to scale, but low latency |
| Server-assigned IDs | Eliminates client clock skew, requires server round-trip |
| Write-fanout default | Simpler client, but doesn't scale to huge channels |
| Soft delete | Audit + recovery, but search reindex needed |

---

## 17. Follow-up questions to anticipate

- **"How does Slack do end-to-end encryption?"** → They don't, except enterprise. E2E breaks search.
- **"How would you handle a channel with 1M members?"** → Read-fanout, hierarchical broadcast tree.
- **"How to handle clock skew?"** → Server Snowflake IDs, vector clocks for collaborative edit.
- **"What about huddles / voice/video?"** → Separate service via WebRTC, SFU (Selective Forwarding Unit) for multi-party.
- **"Push notif at 3am — handle?"** → User preferences for quiet hours, server applies before sending.
