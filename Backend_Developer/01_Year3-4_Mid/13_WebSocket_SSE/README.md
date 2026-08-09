# 🔌 WebSocket + SSE (realtime)

> **5 theory + 4 practical.** Chat, notifications, live dashboards, LLM token streaming — sab yahin se.
> Interview ka asli sawal WebSocket ka syntax nahi, **scaling** hai.

---

## 🔴 Pehle yeh 3

| # | Topic | Classic question |
|---|---|---|
| [03](03_scaling_with_redis_pubsub.md) | **Redis pub/sub se scaling** | 🔥 "3 servers hain, user A server-1 pe, user B server-2 pe — message kaise pahunchega?" |
| [02](02_sse_server_sent_events.md) | **SSE** | "WebSocket vs SSE — kab kya?" (LLM streaming ka jawab) |
| [01](01_websocket_fundamentals.md) | **Fundamentals** | Handshake, upgrade, frames, heartbeat/ping-pong |

---

## 📚 Poori list

| # | Topic | Practical |
|---|---|---|
| [01](01_websocket_fundamentals.md) 🔴 | Protocol internals, handshake, frames | [`01_...py`](practical/01_websocket_fundamentals.py) |
| [02](02_sse_server_sent_events.md) 🔴 | Server-Sent Events | [`02_...py`](practical/02_sse_server_sent_events.py) |
| [03](03_scaling_with_redis_pubsub.md) 🔴 | Scaling with Redis pub/sub, message ordering | [`03_...py`](practical/03_scaling_with_redis_pubsub.py) |
| [04](04_fastapi_websocket_deep.md) | FastAPI WebSocket deep dive | [`04_...py`](practical/04_fastapi_websocket_deep.py) |
| [05](05_socketio_stomp_alternative_protocols.md) | Socket.IO, STOMP, alternatives | — |

---

## ⚔️ WebSocket vs SSE vs Polling — yeh table yaad rakho

| | WebSocket | SSE | Long polling |
|---|---|---|---|
| Direction | **Bi-directional** | Server → client only | Client pulls |
| Protocol | `ws://` (upgrade) | Plain HTTP | Plain HTTP |
| Auto-reconnect | Khud likhna padta hai | **Built-in** (`Last-Event-ID`) | N/A |
| Proxy/firewall | Kabhi-kabhi block | HTTP hai, aasan | Sabse aasan |
| Best for | Chat, multiplayer, collab editing | **LLM token streaming**, notifications, live feeds | Fallback |

**Senior line:** *"Client ko sirf sunna hai to SSE — simpler hai, auto-reconnect free milta hai, HTTP/2 pe multiplex bhi. WebSocket tab jab dono taraf se baat karni ho."*
Isiliye ChatGPT-style token streaming **SSE** pe hoti hai, WebSocket pe nahi.

---

## 🎯 Scaling ka jawab (yeh poora bolo)

1. WebSocket **stateful** hai — connection ek hi server se bandha hai
2. Load balancer pe **sticky sessions** ya connection-aware routing
3. Cross-server delivery ke liye **Redis pub/sub** — server A publish kare, sab servers subscribe karein → [03](03_scaling_with_redis_pubsub.md)
4. **Ordering** ka dhyan — pub/sub guarantee nahi deta, sequence numbers chahiye
5. Presence tracking Redis me (TTL ke saath), heartbeat se refresh
6. Scale bahut bada ho to dedicated gateway layer (Centrifugo / API Gateway WebSocket)

**Related:** [Redis pub/sub](../../00_Year0-2_Junior/08_Redis/theory/10_pubsub_fundamentals.md) · [12_GraphQL subscriptions](../12_GraphQL/04_subscriptions_realtime.md) · [02_API_Design](../02_API_Design/README.md) · [LLM streaming](../../../Agentic_AI/Level3_LLM_APIs_SDKs/)
