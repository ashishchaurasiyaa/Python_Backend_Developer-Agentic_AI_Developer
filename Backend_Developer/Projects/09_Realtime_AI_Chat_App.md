# Project 9: Real-Time AI Chat App (ChatGPT-style)

**Stack:** FastAPI + WebSocket/SSE + PostgreSQL + Redis + Anthropic + OpenAI + Stripe + Docker + AWS
**Build Time:** 2-3 weeks
**Difficulty:** ⭐⭐⭐⭐ (AI + real-time + multi-tenant)
**Resume Strength:** ⭐⭐⭐⭐⭐ (Showcases AI + WebSocket + scaling)

---

## 1. Project Overview & Business Problem

### What it is
A real-time, multi-user AI chat application — like ChatGPT but with **WebSocket-based streaming**, **multi-device sync**, **shared conversations**, **collaborative AI sessions**, and **voice mode**. Like ChatGPT + Slack hybrid.

### Why build this
- **Demonstrates real-time + AI** — most candidates only know request-response
- **WebSocket scaling** — pub/sub, sticky sessions, backpressure
- **Multi-device challenges** — sync across web/mobile
- **Hottest product category** in 2026

### Real-world analogues
- ChatGPT (web)
- Claude.ai
- Poe.com
- Perplexity
- Pi.ai
- Notion AI chat

---

## 2. Requirements

### Functional
- **Auth**: Email/password + Google OAuth + 2FA
- **Chat**: Real-time AI conversations
- **Streaming**: Token-by-token via WebSocket/SSE
- **Multi-device sync**: Messages appear instantly on all devices
- **Conversation history**: Forever, searchable
- **Multi-model**: GPT, Claude, Gemini (user picks)
- **Conversation sharing**: Public/private share links
- **Collaborative chat**: Multiple users in one conversation (chat with friends + AI)
- **File uploads**: Documents, images, code
- **Voice mode**: Voice input + voice output (V2)
- **Custom GPTs**: User-defined personas (V2)
- **Code execution**: Sandboxed Python (V2)
- **Mobile-first UI**: PWA + native apps
- **Stop generation**: Mid-stream cancel
- **Regenerate**: Re-roll last response
- **Edit + branch**: Edit a message, see alternate timeline

### Non-Functional
- 1M MAU, 100K DAU
- 50K concurrent WebSocket connections
- TTFT < 1s (P95)
- Streaming throughput: 30+ tokens/sec/user
- 99.95% uptime
- Multi-region (US, EU, India)
- GDPR + India DPDP compliant
- Cost < $0.30/active user/month

---

## 3. Scale Estimation

| Metric | Number |
|---|---|
| Total users | 1M |
| DAU | 100K |
| Messages/user/day | 20 |
| Messages/day | 2M |
| Concurrent connections (peak) | 50K |
| LLM tokens/day | 2M × 1K avg = 2B |
| LLM cost (Sonnet) | $10K/day = $3.6M/yr |
| With Anthropic prompt caching | $3K/day = $1.1M/yr |
| Postgres writes/sec | ~50 |
| Redis ops/sec | ~10K (sessions, pubsub) |

---

## 4. Architecture

```
                    ┌─────────────────────┐
   Web/iOS/Android ─→│ Cloudflare (WAF/CDN)│
                    └──────────┬──────────┘
                               │
                ┌──────────────┴───────────────┐
                │                              │
        ┌───────▼──────┐              ┌────────▼────────┐
        │ REST API     │              │ WebSocket Hub    │
        │ (FastAPI)    │              │ (FastAPI + uvicorn)│
        │ - auth        │              │ - chat streaming │
        │ - history    │              │ - presence       │
        │ - search     │              │ - typing         │
        └───────┬──────┘              └────────┬────────┘
                │                              │
                └──────────────┬───────────────┘
                               │
                ┌──────────────┴──────────────┐
                │                              │
        ┌───────▼──────┐              ┌────────▼────────┐
        │ PostgreSQL   │              │ Redis Cluster    │
        │ - users      │              │ - WS sessions    │
        │ - convos     │              │ - pub/sub        │
        │ - messages   │              │ - quotas         │
        │ - sharing    │              │ - rate limits    │
        └──────────────┘              └─────────────────┘

                ┌──────────────────────┐
                │ LLM Router (LiteLLM) │
                ├─────────┬────────────┤
                │ Claude  │ OpenAI    │
                └─────────┴────────────┘

External:
- Stripe (Pro tier billing)
- Twilio (SMS for 2FA)
- AWS S3 (file uploads)
- Datadog (observability)
- Cloudflare (DDoS, edge)
```

---

## 5. WebSocket vs SSE Decision

| Aspect | WebSocket | SSE |
|---|---|---|
| Bidirectional | ✅ | ❌ (server → client only) |
| Reconnect | Manual | Auto (browser native) |
| Multiplexing | Yes | No |
| Browser support | All | All |
| Through corporate firewall | Issues | Better (HTTP) |
| Best for | Multi-user chat + presence | Single-stream AI response |

**Decision:** **WebSocket** for chat (presence, multi-user). Use SSE inside WebSocket for token streaming if simpler.

---

## 6. Implementation Phases

### Phase 1: Auth + Basic Chat (Week 1)
- [ ] FastAPI skeleton with auth (JWT)
- [ ] Postgres schema: users, conversations, messages
- [ ] Basic REST endpoints: create conversation, send message
- [ ] OpenAI non-streaming integration
- [ ] React/Next.js frontend (minimal)

### Phase 2: WebSocket + Streaming (Week 1-2)
- [ ] WebSocket endpoint with auth handshake
- [ ] Redis pub/sub for fan-out
- [ ] Anthropic streaming integration
- [ ] Token-by-token forward via WebSocket
- [ ] Stop generation support
- [ ] Multi-device sync (same user → multiple devices)

### Phase 3: Conversation Features (Week 2)
- [ ] Conversation history + search
- [ ] Edit + branch (alternate timelines)
- [ ] Regenerate response
- [ ] Auto-titling via Haiku
- [ ] Multi-model support (Claude/GPT/Gemini)
- [ ] System prompts / personas

### Phase 4: Collaboration (Week 2-3)
- [ ] Conversation sharing (public links)
- [ ] Multi-user conversations (real-time)
- [ ] Presence indicators
- [ ] Typing indicators
- [ ] @-mentions to invoke AI

### Phase 5: Scale + Production (Week 3)
- [ ] Sticky WebSocket sessions (Redis-aware load balancer)
- [ ] Horizontal scaling (multiple WebSocket pods)
- [ ] Rate limiting (per-user, per-tier)
- [ ] Stripe Pro tier
- [ ] Observability (Datadog, Sentry)
- [ ] Load testing (k6 with WebSocket)

### Phase 6: Polish + Mobile (Week 3-4)
- [ ] PWA configuration
- [ ] React Native mobile app
- [ ] Push notifications (FCM/APNs)
- [ ] Voice mode (OpenAI Realtime API)
- [ ] File uploads (S3 presigned URLs)

---

## 7. Key Code Patterns

### WebSocket connection manager with multi-device sync

```python
from fastapi import WebSocket
from typing import Set
import redis.asyncio as aioredis

class ConnectionManager:
    """Per-pod state — coordinates via Redis pub/sub for multi-pod."""

    def __init__(self):
        self.connections: dict[str, set[WebSocket]] = {}  # user_id → ws
        self.redis = aioredis.from_url("redis://redis-cluster")
        self.pubsub = self.redis.pubsub()

    async def start(self):
        # Subscribe to user broadcasts from other pods
        await self.pubsub.psubscribe("user:*")
        asyncio.create_task(self._listen_pubsub())

    async def connect(self, user_id: str, ws: WebSocket):
        await ws.accept()
        self.connections.setdefault(user_id, set()).add(ws)

        # Announce presence
        await self.redis.set(f"online:{user_id}", "1", ex=60)

        # Send any pending messages from offline period
        pending = await self.redis.lrange(f"queue:{user_id}", 0, -1)
        for msg in pending:
            await ws.send_text(msg)
        await self.redis.delete(f"queue:{user_id}")

    async def send_to_user(self, user_id: str, message: dict):
        """Send to all of user's devices, even across pods."""
        # Local devices
        if user_id in self.connections:
            for ws in self.connections[user_id]:
                try:
                    await ws.send_text(json.dumps(message))
                except Exception:
                    self.connections[user_id].discard(ws)

        # Other pods via Redis pub/sub
        await self.redis.publish(f"user:{user_id}", json.dumps(message))

    async def _listen_pubsub(self):
        """Receive messages for users connected to THIS pod from other pods."""
        async for msg in self.pubsub.listen():
            if msg["type"] == "pmessage":
                channel = msg["channel"].decode()
                user_id = channel.split(":")[1]
                data = msg["data"].decode()
                # Send to local connections only
                if user_id in self.connections:
                    for ws in self.connections[user_id]:
                        await ws.send_text(data)

    async def disconnect(self, user_id: str, ws: WebSocket):
        if user_id in self.connections:
            self.connections[user_id].discard(ws)

manager = ConnectionManager()

@app.websocket("/ws/chat")
async def chat_ws(ws: WebSocket):
    user_id = await authenticate_ws(ws)
    await manager.connect(user_id, ws)

    try:
        while True:
            data = await ws.receive_json()
            if data["type"] == "send_message":
                await handle_message(user_id, data)
            elif data["type"] == "stop":
                await handle_stop(data["conversation_id"])
    except WebSocketDisconnect:
        await manager.disconnect(user_id, ws)
```

### LLM streaming with stop support

```python
async def handle_message(user_id: str, data: dict):
    conv_id = data["conversation_id"]
    message = data["content"]

    # Save user message
    user_msg_id = await save_message(conv_id, "user", message)

    # Send back to all user's devices
    await manager.send_to_user(user_id, {
        "type": "message_added",
        "message_id": user_msg_id,
        "role": "user",
        "content": message,
    })

    # Begin AI response
    asst_msg_id = uuid4()
    stop_signal = asyncio.Event()

    # Store stop signal for cancellation
    active_streams[asst_msg_id] = stop_signal

    full_response = []

    try:
        async with anthropic.messages.stream(
            model="claude-opus-4-7",
            system=get_system_prompt(conv_id),
            messages=await load_history(conv_id),
            max_tokens=4096,
        ) as stream:
            async for token in stream.text_stream:
                if stop_signal.is_set():
                    break
                full_response.append(token)
                await manager.send_to_user(user_id, {
                    "type": "token",
                    "message_id": str(asst_msg_id),
                    "delta": token,
                })

        final = await stream.get_final_message()
        await save_message(
            conv_id, "assistant",
            "".join(full_response),
            model="claude-opus-4-7",
            tokens_in=final.usage.input_tokens,
            tokens_out=final.usage.output_tokens,
        )
        await manager.send_to_user(user_id, {
            "type": "complete",
            "message_id": str(asst_msg_id),
        })
    finally:
        del active_streams[asst_msg_id]

async def handle_stop(message_id: str):
    if message_id in active_streams:
        active_streams[message_id].set()
```

---

## 8. Database Schema (Highlights)

```sql
CREATE TABLE users (
    id UUID PRIMARY KEY,
    email TEXT UNIQUE NOT NULL,
    tier TEXT DEFAULT 'free',  -- free, pro, team
    region TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE conversations (
    id UUID PRIMARY KEY,
    owner_user_id UUID REFERENCES users(id),
    title TEXT,
    is_shared BOOLEAN DEFAULT FALSE,
    share_token TEXT UNIQUE,
    model_default TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE conversation_members (
    conversation_id UUID REFERENCES conversations(id),
    user_id UUID REFERENCES users(id),
    role TEXT,  -- 'owner', 'collaborator', 'viewer'
    joined_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (conversation_id, user_id)
);

CREATE TABLE messages (
    id UUID PRIMARY KEY,
    conversation_id UUID REFERENCES conversations(id) ON DELETE CASCADE,
    parent_message_id UUID REFERENCES messages(id),  -- for branching
    role TEXT NOT NULL,
    content TEXT,
    model TEXT,
    tokens_in INT,
    tokens_out INT,
    cost_usd NUMERIC(10, 6),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    user_id UUID,  -- for collaborator messages
    is_active_branch BOOLEAN DEFAULT TRUE
) PARTITION BY RANGE (created_at);  -- monthly partitions

CREATE TABLE attachments (
    id UUID PRIMARY KEY,
    message_id UUID REFERENCES messages(id),
    s3_key TEXT,
    filename TEXT,
    mime_type TEXT,
    size_bytes BIGINT
);
```

---

## 9. Frontend Architecture

```
Next.js app (PWA-enabled)
├── /chat/[conversationId]
│   ├── MessageList (virtualized for long convos)
│   ├── StreamingMessage (token animations)
│   ├── ComposerBar (input + file upload)
│   └── PresenceBar (online users)
├── /share/[token]   (public conversation view)
└── /workspace        (sidebar with all conversations)

State management: Zustand
Real-time: Native WebSocket API
Offline: Service Worker + IndexedDB cache
```

---

## 10. Testing Strategy

```python
# WebSocket integration tests
async def test_streaming_message():
    async with httpx_ws.connect("ws://localhost:8000/ws/chat", headers=auth) as ws:
        await ws.send_json({"type": "send_message", "content": "Hi", "conversation_id": "abc"})

        tokens_received = []
        async for msg in ws:
            data = json.loads(msg)
            if data["type"] == "token":
                tokens_received.append(data["delta"])
            elif data["type"] == "complete":
                break

        assert len(tokens_received) > 0
        full = "".join(tokens_received)
        assert "Hi" in full or "Hello" in full  # AI responded

# Multi-device sync test
async def test_multi_device_sync():
    async with httpx_ws.connect(...) as ws1, httpx_ws.connect(...) as ws2:
        # Send from device 1
        await ws1.send_json({"type": "send_message", "content": "test"})
        # Device 2 should receive
        msg = await asyncio.wait_for(ws2.receive_json(), timeout=2.0)
        assert msg["content"] == "test"

# Load test (k6 with WebSocket)
# 50K concurrent WebSockets, 1 message per minute
# Assert p95 message delivery < 500ms
```

---

## 11. Production Optimizations

| Concern | Solution |
|---|---|
| WebSocket scaling | Sticky sessions; Redis pub/sub for fan-out |
| Memory per WS connection | ~25KB; 100K conns = 2.5GB per pod |
| Reconnection storms | Exponential backoff; randomize |
| Slow message persists | Async; commit before LLM streams |
| LLM cost spike | Tier-based model routing |
| Hot conversation | Cap members; archive old messages |
| Search performance | Postgres FTS + Elasticsearch for big tenants |
| Mobile network drop | Queue messages in Redis; replay on reconnect |

---

## 12. Cost Analysis (per 100K DAU)

| Component | Monthly Cost |
|---|---|
| LLM (mixed models) | $100K (without cache) |
| LLM (with Anthropic cache + smart routing) | $30K |
| Postgres (RDS) | $5K |
| Redis cluster | $2K |
| WebSocket pods (50K conns) | $4K |
| S3 + CDN | $2K |
| Misc (Sentry, Datadog, etc) | $3K |
| **Total** | **~$46K/month** |

**Per active user:** $0.46/month (achievable with caching strategy)

---

## 13. Stretch Goals

- [ ] Voice mode (Whisper + Realtime API + ElevenLabs)
- [ ] Code interpreter (sandbox via E2B)
- [ ] Image generation (DALL-E, Stable Diffusion)
- [ ] Custom personas / GPTs
- [ ] Plugin/MCP marketplace
- [ ] Memory across conversations (long-term per-user memory)
- [ ] Browser extension (highlight → ask AI)
- [ ] Team/organization features (Slack-style workspaces)

---

## 14. Resume Bullets

- Built **real-time AI chat platform** supporting 50K concurrent WebSocket connections
- Implemented **multi-device sync** via Redis pub/sub fan-out across multiple pods
- Designed **streaming pipeline** with stop/regenerate, achieving < 1s TTFT (P95)
- Built **branching conversation model** (edit + alternate timelines like ChatGPT)
- Engineered **multi-model LLM router** (Claude/GPT/Gemini) with cost-aware tier routing
- Reduced LLM costs **65% via Anthropic prompt caching + semantic cache**
- Deployed on **K8s with sticky sessions** for WebSocket scaling
- Handled **mobile reconnection scenarios** with message queueing

---

## 15. Related Resources
- `Phase2_FastAPI/31_llm_integration_fastapi.md` — LLM patterns
- `Phase2_FastAPI/37_voice_agent_backend.md` — voice mode
- `Phase2_WebSocket_SSE/` — WebSocket fundamentals
- `PythonBackend_SystemDesign/HLD_Problems/Design_ChatGPT_Backend.md` — HLD reference
- `Phase2_Redis/` — pub/sub patterns
- `Projects/04_FastAPI_WhatsApp_Lite_Chat.md` — non-AI chat patterns
