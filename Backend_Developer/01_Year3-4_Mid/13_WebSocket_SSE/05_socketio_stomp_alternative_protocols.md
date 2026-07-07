# 05 — Socket.IO & STOMP (Alternative Real-Time Protocols)

> Raw WebSocket is a transport, not a protocol with conventions — Socket.IO and STOMP each add a layer of structure on top. Low-priority for a Python backend specifically, but worth recognizing when they come up.

---

## Why It Matters (and why it's lower priority for you specifically)

Raw WebSocket (already covered in `01_websocket_fundamentals.md`) gives you
bytes over a persistent connection — nothing more. No built-in reconnection,
no message routing/rooms, no fallback for environments that block WebSocket.
Socket.IO and STOMP are two different answers to "what do we build on top of
raw WebSocket to make it usable at application scale."

**Why this is lower priority for a Python backend role:** Socket.IO is
overwhelmingly a JS/Node-ecosystem convention (though a Python server library
exists); STOMP is more common in Java/Spring and enterprise message-broker
integrations (ActiveMQ/RabbitMQ STOMP plugin). A Python/FastAPI backend using
raw WebSocket + Redis pub/sub (your existing `03_scaling_with_redis_pubsub.md`
coverage) is the more idiomatic stack. This file exists so you can recognize
and discuss them if they come up, not because you'll likely build with them.

---

## Socket.IO

```
Socket.IO ≠ WebSocket. It's a library/protocol that:
1. Falls back to HTTP long-polling if WebSocket is blocked (corporate
   firewalls, old proxies) — auto-negotiates the best available transport
2. Adds "rooms" and "namespaces" — logical grouping of connections for
   broadcast (e.g., all clients in chat room #42)
3. Adds automatic reconnection with exponential backoff, built in
4. Adds acknowledgements — client can confirm receipt of a specific event
```

```python
# python-socketio — the Python server implementation
import socketio

sio = socketio.AsyncServer(async_mode="asgi", cors_allowed_origins="*")
app = socketio.ASGIApp(sio)

@sio.event
async def connect(sid, environ):
    print(f"Client {sid} connected")

@sio.event
async def join_room(sid, data):
    await sio.enter_room(sid, data["room"])

@sio.event
async def chat_message(sid, data):
    # Broadcast to everyone in the room EXCEPT the sender
    await sio.emit("chat_message", data, room=data["room"], skip_sid=sid)

@sio.event
async def disconnect(sid):
    print(f"Client {sid} disconnected")
```

```python
# Mounting alongside FastAPI (common integration pattern)
from fastapi import FastAPI

fastapi_app = FastAPI()
fastapi_app.mount("/socket.io", app)
```

**Key tradeoff:** Socket.IO requires the client to ALSO speak the Socket.IO
protocol (not plain WebSocket) — you can't connect to a Socket.IO server with
a browser's native `new WebSocket(url)`, you need the `socket.io-client`
library. This is the main reason teams skip it when both ends are under
their control and raw WebSocket is sufficient.

---

## STOMP (Simple/Streaming Text Oriented Messaging Protocol)

```
STOMP is a MESSAGING protocol (like AMQP, but simpler/text-based) that can
run OVER WebSocket as its transport — giving WebSocket clients pub/sub
semantics (SUBSCRIBE/SEND/ACK) similar to a message broker, instead of raw
bytes.

Client ──STOMP frames over WebSocket──► STOMP-capable broker (RabbitMQ
                                          STOMP plugin, ActiveMQ) ──► routes
                                          to subscribed topics/queues
```

```
STOMP frame format (text-based, human-readable — unlike AMQP's binary format):

SUBSCRIBE
id:sub-0
destination:/topic/orders

^@
```

```python
# Python client example (stomp.py library) — subscribing to a broker topic
import stomp

class OrderListener(stomp.ConnectionListener):
    def on_message(self, frame):
        print(f"Received: {frame.body}")

conn = stomp.Connection([("localhost", 61613)])
conn.set_listener("", OrderListener())
conn.connect(wait=True)
conn.subscribe(destination="/topic/orders", id=1, ack="auto")
```

**Where STOMP actually shows up:** enabling a browser client to subscribe
directly to a RabbitMQ/ActiveMQ topic over WebSocket, without a custom
backend layer translating between AMQP and WebSocket yourself. Common in
Java/Spring shops (Spring's WebSocket support has first-class STOMP
integration) — less common as a deliberate choice in a Python-first stack,
where you'd more likely just build a thin WebSocket→Redis-pub/sub bridge
instead (exactly what your existing `03_scaling_with_redis_pubsub.md` covers).

---

## Decision Table

| Need | Choice |
|---|---|
| Simple bidirectional messaging, both ends under your control | **Raw WebSocket** (your existing coverage) — simplest, no extra protocol |
| Need fallback for restrictive networks + rooms/reconnection built in, JS-heavy frontend | **Socket.IO** |
| Browser needs to subscribe directly to broker topics (RabbitMQ/ActiveMQ) without a custom bridge | **STOMP over WebSocket** |
| Python backend + Redis pub/sub already in your stack | **Raw WebSocket + Redis pub/sub** — the pattern this repo already teaches, and the more idiomatic choice here |

---

## Interview Q&A

**Q: Is Socket.IO the same as WebSocket?**
A: No — Socket.IO is a library/protocol built on top of WebSocket (with
long-polling fallback), requiring both client and server to speak the
Socket.IO protocol specifically. A plain browser `WebSocket` object cannot
connect to a Socket.IO server without the matching client library.

**Q: When would you reach for STOMP instead of just raw WebSocket + your own message routing?**
A: When you want browser clients to subscribe directly to existing broker
topics/queues (RabbitMQ, ActiveMQ) without writing a custom translation
layer yourself — STOMP gives WebSocket clients pub/sub semantics the broker
already understands natively.

**Q: Why might a Python/FastAPI shop avoid Socket.IO even though it solves real problems (reconnection, fallback)?**
A: It locks both ends into the Socket.IO protocol/client library — raw
WebSocket plus a Redis pub/sub layer (this repo's existing scaling pattern)
achieves reconnection/broadcast without that lock-in, and is more idiomatic
in a Python-first stack where the frontend isn't necessarily JS-only.

---

Related: `01_websocket_fundamentals.md` (the raw transport these build on),
`03_scaling_with_redis_pubsub.md` (the more idiomatic Python-stack
alternative to Socket.IO's rooms feature).
