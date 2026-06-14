# WhatsApp-Lite Chat Backend — Starter

Spec: [../04_FastAPI_WhatsApp_Lite_Chat.md](../04_FastAPI_WhatsApp_Lite_Chat.md)

## What to build

Scalable messaging backend: 1:1 and group chat, real-time WebSocket delivery, read receipts, typing indicators, presence, push notifications for offline users, media upload to S3.  Target: 1M concurrent WS connections, 200K messages/sec, p99 < 200ms.

## How to run

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Infrastructure
docker run -d --name pg -e POSTGRES_PASSWORD=dev -p 5432:5432 postgres:16
docker run -d --name redis -p 6379:6379 redis:7
docker run -d --name kafka -p 9092:9092 apache/kafka:3.7.0
# Cassandra (for message storage at scale):
docker run -d --name cassandra -p 9042:9042 cassandra:4.1

uvicorn main:app --reload
```

Connect via WebSocket: `ws://localhost:8000/ws?token=<jwt>`

## Milestones (from spec)

- **Week 1** — Phone OTP auth, 1:1 chat via REST, basic message storage (Postgres to start)
- **Week 2** — WebSocket gateway pod, real-time delivery, presence (Redis heartbeat), multi-device
- **Week 3** — Cassandra schemas, Kafka send path (durability before ack), persistence + fanout workers, Redis pub/sub backplane
- **Week 4** — Group chat, read receipts (3 levels), typing indicators, media upload (S3 presigned URLs)
- **Week 5** — FCM/APNs push (with 5s batch debounce), offline queue, Elasticsearch search, load test 100K concurrent

## Key patterns to implement

1. Kafka in the send path: producer acks Kafka (5ms) → client gets ack → persistence worker writes Cassandra → fanout worker delivers.
2. Cross-server routing: `Redis HGETALL user_conns:{user_id}` → publish to `gateway:{node_id}` channel → local WS delivery.
3. Cassandra partition key = `chat_id`; clustering key = `msg_id` (Snowflake, time-ordered).
4. Online presence: `Redis SET presence:{user_id} 1 EX 60`; heartbeat every 30s; broadcast to contacts on change.
5. Push notification batching: Redis INCR counter with 5s debounce; send 1 aggregated push if count > 1.
