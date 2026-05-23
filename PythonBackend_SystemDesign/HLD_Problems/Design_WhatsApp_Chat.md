# Design WhatsApp / Real-Time Chat System — HLD

## Requirements

### Functional
- 1-1 messaging and group chats (up to 256 members)
- Send text, images, voice notes
- Message delivery receipts (sent ✓, delivered ✓✓, read ✓✓ blue)
- Online presence (last seen)
- Push notifications for offline users
- End-to-end encryption (E2EE)

### Non-Functional
- 2 billion users, 100 billion messages/day
- Messages delivered in <100ms (same region)
- 99.99% availability
- Messages stored for 30 days (or until delivered)
- E2EE: server cannot read message content

---

## Back-of-Envelope Estimation

```
Users:          2B total, 500M DAU
Messages/day:   100B messages
QPS:            100B / 86,400 ≈ 1.16M messages/sec
Peak:           ~3-4M messages/sec

Storage per message:
  content(avg 100B) + metadata(50B) = 150 bytes
  100B × 150B = 15 TB/day (text only)
  Media (20%): 20B × avg 50KB = 1 PB/day → object storage

Active connections (WebSocket):
  500M DAU, avg 30% online = 150M concurrent connections
```

---

## High-Level Architecture

```
                        ┌─────────────────┐
                        │   Load Balancer  │
                        └────────┬────────┘
              ┌──────────────────┴──────────────────┐
              │                                     │
    ┌─────────▼───────────┐            ┌────────────▼──────────┐
    │  Chat Server Pool   │            │   Presence Service    │
    │  (WebSocket nodes)  │            │   (online/last seen)  │
    └─────────┬───────────┘            └────────────┬──────────┘
              │                                     │
    ┌─────────▼─────────────────────────────────────▼──────────┐
    │                     Message Queue (Kafka)                 │
    └──────────────────────────────┬────────────────────────────┘
                                   │
              ┌────────────────────┼────────────────────┐
              │                    │                    │
    ┌─────────▼────────┐  ┌────────▼────────┐  ┌───────▼──────────┐
    │  Message Store   │  │  Notification   │  │  Media Service   │
    │  (Cassandra)     │  │  Service (FCM)  │  │  (S3 + CDN)      │
    └──────────────────┘  └─────────────────┘  └──────────────────┘
```

---

## Component Deep-Dive

### 1. Connection Management (WebSocket)

```
Client opens WebSocket to Chat Server
Server assigns user → connection mapping
User goes offline → remove mapping, store last-seen

Challenge: 150M concurrent WebSocket connections
Solution:  Horizontal scaling of chat servers
           Connection metadata in Redis:
           user_id:123 → server_node:chat-12, conn_id:abc
```

### 2. Message Flow (1-1 Chat)

```
Alice sends message to Bob:

1. Alice → WebSocket → Chat Server A
2. Chat Server A:
   a. Save to Cassandra (status=sent)
   b. Publish to Kafka: topic="messages", key=bob_id
3. Chat Server routing (Bob's connection):
   a. Check Redis: bob connected to Chat Server B
   b. Push via inter-server channel OR
      Route through Kafka consumer on Server B
4. Chat Server B → WebSocket → Bob (delivered ✓✓)
5. Bob sends read receipt → Chat Server A → Alice (blue ✓✓)
6. If Bob offline → Push notification via FCM/APNs
```

### 3. Message Storage — Cassandra Schema

```sql
-- Why Cassandra?
-- Write-heavy, time-series data, no joins needed
-- Auto-partitions by conversation_id

CREATE TABLE messages (
    conversation_id  UUID,
    sent_at          TIMESTAMP,
    message_id       UUID,
    sender_id        UUID,
    content          TEXT,           -- encrypted blob
    content_type     TEXT,           -- 'text', 'image', 'audio'
    media_url        TEXT,           -- S3 URL for media
    status           TEXT,           -- 'sent','delivered','read'
    PRIMARY KEY ((conversation_id), sent_at, message_id)
) WITH CLUSTERING ORDER BY (sent_at DESC);

-- Load recent messages
SELECT * FROM messages
WHERE conversation_id = ?
  AND sent_at > ?
LIMIT 50;
```

### 4. Message Queue Design

```python
# Kafka topics:
# "chat.messages"        → all new messages
# "chat.receipts"        → delivery/read receipts
# "chat.notifications"   → offline user notifications
# "chat.presence"        → online/offline events

# Consumer group per chat server
# Each server only processes messages for users connected to IT
```

### 5. Presence Service

```python
import redis
from datetime import datetime, timezone

r = redis.Redis()

PRESENCE_TTL = 60  # seconds

def user_online(user_id: str, server_node: str):
    """Mark user online (heartbeat every 30s)."""
    r.setex(f"presence:{user_id}", PRESENCE_TTL, server_node)
    r.set(f"last_seen:{user_id}", datetime.now(tz=timezone.utc).isoformat())

def user_offline(user_id: str):
    r.delete(f"presence:{user_id}")
    r.set(f"last_seen:{user_id}", datetime.now(tz=timezone.utc).isoformat())

def get_user_server(user_id: str) -> str | None:
    """Returns which chat server the user is connected to."""
    return r.get(f"presence:{user_id}")

def get_last_seen(user_id: str) -> str:
    return r.get(f"last_seen:{user_id}") or "Long time ago"
```

### 6. Group Chat

```
Challenge: Sending to 256 members efficiently
Solution: Fanout strategy

1. Save message once to Cassandra
2. Kafka event: "group.message" → group_id=xyz
3. Group Consumer:
   a. Read member list from DB
   b. For each online member → route to their chat server
   c. For each offline member → push notification
   d. Fan-out in parallel (asyncio.gather)
```

### 7. End-to-End Encryption

```
WhatsApp uses Signal Protocol:
1. Each device generates a key pair (public + private)
2. Public keys uploaded to WhatsApp server
3. Alice encrypts message with Bob's PUBLIC key
4. Bob decrypts with his PRIVATE key
5. WhatsApp server only sees encrypted blob → cannot read

Implementation (simplified):
  Alice → encrypt(message, bob_public_key) → ciphertext → server → Bob
  Bob   → decrypt(ciphertext, bob_private_key) → plaintext
```

---

## Database Choices

| Data | DB | Reason |
|---|---|---|
| Messages | Cassandra | Write-heavy, time-series, sharding by conversation |
| User accounts | PostgreSQL | Strong consistency, relationships |
| User presence | Redis | Sub-ms reads, TTL auto-expiry |
| Media files | S3 + CloudFront CDN | Large objects, globally distributed |
| Notification tokens | DynamoDB | Key-value, high availability |

---

## Scaling Bottlenecks & Solutions

| Bottleneck | Solution |
|---|---|
| 150M WebSocket connections | Horizontal scaling of chat servers |
| 1M+ msg/sec writes | Cassandra write throughput, Kafka buffering |
| Group fanout (256 members) | Async parallel fanout via Kafka |
| Presence for 500M DAU | Redis Cluster, TTL-based expiry |
| Media storage (1 PB/day) | S3 + CDN + compression |

---

## Interview Talking Points

1. **Why WebSocket vs HTTP long-polling?**  
   WebSocket: bidirectional, persistent, low overhead. HTTP long-poll: simpler but more latency, more server connections.

2. **How to handle message ordering?**  
   Cassandra clustering by timestamp. For exact ordering use Lamport logical clocks or seq numbers per conversation.

3. **How does delivery receipt work?**  
   Server-to-client ACK when message is stored + delivered + read. Each receipt is a small event through Kafka.

4. **How do you scale to 2B users?**  
   - Chat servers: stateless, many instances, routed by user_id hash
   - Cassandra: sharded by conversation_id
   - Redis Cluster for presence
   - Separate Kafka clusters per region
