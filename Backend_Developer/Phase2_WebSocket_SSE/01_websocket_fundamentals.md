# 01 — WebSocket Fundamentals

> Persistent bidirectional connection between client and server over a single TCP connection. The standard for real-time web apps.

---

## Why WebSocket Exists

HTTP is request-response. To push data to clients without a request, options are:
- **Polling**: client asks "anything new?" every N seconds → wasteful.
- **Long polling**: server holds request until event → heavy connection turnover.
- **SSE**: server → client one-way → no bidirectional.
- **WebSocket**: full duplex, low overhead, modern.

---

## The Protocol

### Handshake
Starts as HTTP request:
```http
GET /chat HTTP/1.1
Host: example.com
Upgrade: websocket
Connection: Upgrade
Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==
Sec-WebSocket-Version: 13
```

Server responds:
```http
HTTP/1.1 101 Switching Protocols
Upgrade: websocket
Connection: Upgrade
Sec-WebSocket-Accept: s3pPLMBiTxaQ9kYGzzhZRbK+xOo=
```

After this, the TCP connection is upgraded; HTTP framing is replaced with WebSocket framing.

### URL scheme
- `ws://` (plain)
- `wss://` (TLS — production standard)

### After handshake
Both sides can send messages at any time. Bidirectional.

---

## Frame Structure

```
 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
+-+-+-+-+-------+-+-------------+-------------------------------+
|F|R|R|R| opcode|M| Payload len |    Extended payload length    |
|I|S|S|S|  (4)  |A|     (7)     |             (16/64)           |
|N|V|V|V|       |S|             |   (if payload len==126/127)   |
| |1|2|3|       |K|             |                               |
+-+-+-+-+-------+-+-------------+ - - - - - - - - - - - - - - - +
|     Extended payload length continued, if payload len == 127  |
+ - - - - - - - - - - - - - - - +-------------------------------+
|                               |Masking-key, if MASK set to 1  |
+-------------------------------+-------------------------------+
| Masking-key (continued)       |          Payload Data         |
+-------------------------------+ - - - - - - - - - - - - - - - +
:                     Payload Data continued ...                :
+ - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - +
|                     Payload Data continued ...                |
+---------------------------------------------------------------+
```

Key fields:
- `FIN`: last frame of message? (for fragmentation)
- `Opcode`: 1=text, 2=binary, 8=close, 9=ping, 10=pong
- `MASK`: client-to-server frames must be masked
- `Payload length`: 7 bits, or 16/64 bit extended

---

## Frame Types

| Opcode | Type | Meaning |
|---|---|---|
| 0x0 | Continuation | Part of fragmented message |
| 0x1 | Text | UTF-8 text |
| 0x2 | Binary | Arbitrary binary |
| 0x8 | Close | Connection close (with reason code) |
| 0x9 | Ping | Heartbeat request |
| 0xA | Pong | Heartbeat response |

---

## Python WebSocket Server

### Using `websockets` library (standalone)
```python
import asyncio
import websockets

async def echo(websocket):
    async for message in websocket:
        await websocket.send(f"Echo: {message}")

async def main():
    async with websockets.serve(echo, "localhost", 8765):
        await asyncio.Future()  # run forever

asyncio.run(main())
```

### Client
```python
import asyncio
import websockets

async def hello():
    async with websockets.connect("ws://localhost:8765") as ws:
        await ws.send("Hello!")
        response = await ws.recv()
        print(response)

asyncio.run(hello())
```

---

## FastAPI WebSocket

```python
from fastapi import FastAPI, WebSocket, WebSocketDisconnect

app = FastAPI()

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_text()
            await websocket.send_text(f"Echo: {data}")
    except WebSocketDisconnect:
        print("Client disconnected")
```

---

## Connection Lifecycle

```
1. Client opens WS connection
2. Server accepts handshake
3. Both exchange messages
4. Either side initiates close (Close frame)
5. Other side acks
6. TCP closed
```

### Close codes
- 1000: normal close
- 1001: going away
- 1006: abnormal close (no Close frame, network broke)
- 1008: policy violation
- 1011: internal error
- 4000-4999: application-defined

```python
await websocket.close(code=4001, reason="Auth failed")
```

---

## Heartbeat / Keep-Alive

Detects dead connections that didn't FIN properly.

```python
# Server pings every 20s
while True:
    try:
        await asyncio.wait_for(websocket.ping(), timeout=10)
        await asyncio.sleep(20)
    except asyncio.TimeoutError:
        await websocket.close(1006)
        break
```

`websockets` lib has built-in `ping_interval` parameter.

---

## Authentication

WebSocket doesn't have a "header" phase for auth like HTTP after handshake. Three options:

### 1. Token in query string
```
ws://example.com/ws?token=abc...
```
Easy but token in URL = visible in server logs.

### 2. Token in subprotocol
```javascript
const ws = new WebSocket("wss://example.com/ws", ["jwt", "abc..."]);
```
Server reads `Sec-WebSocket-Protocol` header.

### 3. First message after connect
```python
@app.websocket("/ws")
async def ws(websocket: WebSocket):
    await websocket.accept()
    auth_msg = await websocket.receive_json()
    user = await verify(auth_msg["token"])
    if not user:
        await websocket.close(4001, "Unauthorized")
        return
    # proceed
```

### 4. Cookie-based
Same as HTTP cookie — works for browser clients. CSRF defense needed.

**Production:** subprotocol or first-message auth. Avoid query strings.

---

## Message Framing in App Logic

WebSocket sends raw messages. You typically wrap them in a message format:

```python
import json

# Send
await ws.send_text(json.dumps({"type": "chat", "data": "hello"}))

# Receive
msg = json.loads(await ws.receive_text())
match msg["type"]:
    case "chat": handle_chat(msg["data"])
    case "typing": handle_typing(msg["data"])
```

### Binary messages
Use msgpack/protobuf for performance:
```python
import msgpack

await ws.send_bytes(msgpack.packb({"type": "chat", "data": "hello"}))
msg = msgpack.unpackb(await ws.receive_bytes())
```

---

## Backpressure

If you send faster than client receives, server's send queue grows.

Solutions:
1. **Drop messages**: skip when queue full.
2. **Apply flow control**: ask client to ACK every N msgs.
3. **Close slow clients**: protect server resources.

```python
# websockets lib config
async with websockets.serve(
    handler,
    write_limit=64 * 1024,  # bytes buffered before backpressure
    ping_interval=20,
    ping_timeout=10
):
    ...
```

---

## Max Message Size

Limit incoming message size:
```python
async with websockets.serve(handler, max_size=1024 * 1024):  # 1MB
    ...
```

Otherwise: a malicious client sends 1GB message → server OOMs.

---

## Browser-Side

```javascript
const ws = new WebSocket("wss://example.com/ws");

ws.onopen = () => {
    ws.send(JSON.stringify({ type: "subscribe", channel: "chat-1" }));
};

ws.onmessage = (event) => {
    const msg = JSON.parse(event.data);
    handleMessage(msg);
};

ws.onerror = (err) => console.error(err);
ws.onclose = (event) => console.log("Closed", event.code);

// Send periodically
setInterval(() => ws.send(JSON.stringify({type:"ping"})), 30000);
```

### Reconnect logic
```javascript
function connect() {
    const ws = new WebSocket(url);
    ws.onclose = () => {
        setTimeout(connect, Math.random() * 5000); // backoff with jitter
    };
}
```

Always implement client-side reconnect with backoff.

---

## WebSocket Across Proxies / LBs

### NGINX
```nginx
location /ws {
    proxy_pass http://backend;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "Upgrade";
    proxy_set_header Host $host;
    proxy_read_timeout 86400;     # WS connections can be long
}
```

### AWS ALB
Supports WebSocket out of the box. Set idle timeout > 60s.

### Cloudflare
Supports WS. Enterprise plan recommended for stability.

---

## Sticky Sessions

For multi-instance servers: ensure same client returns to same server.

LB modes:
- **IP hash**: same client IP → same server.
- **Cookie**: session affinity cookie.
- **None**: rely on pub/sub backplane (see file 03).

Without sticky sessions: client connects to server A; another client connects to server B. They can't see each other's events without a shared pub/sub.

---

## Common Issues

### 1. "Connection upgrade failed"
Usually proxy/LB not configured for WS. Check Upgrade headers.

### 2. Client disconnects after 60s
LB idle timeout. Configure ping interval shorter than timeout.

### 3. CORS / origin check
```python
@app.websocket("/ws")
async def ws(websocket: WebSocket):
    origin = websocket.headers.get("origin")
    if origin not in ALLOWED_ORIGINS:
        await websocket.close(1008)
        return
    await websocket.accept()
```

### 4. Memory leak with many clients
Track connections, close idle ones, set max connections per process.

### 5. 1006 abnormal close
Network blip; client should reconnect.

---

## Comparison with Alternatives

| | WebSocket | SSE | HTTP Long Poll | gRPC Streaming |
|---|---|---|---|---|
| Direction | Bidirectional | Server→Client | Client→Server | Bidirectional |
| Protocol | TCP upgrade | HTTP | HTTP | HTTP/2 |
| Binary | Yes | No | Yes (base64) | Yes |
| Reconnect | Manual | Auto | Manual | Manual |
| Browser | Yes | Yes | Yes | gRPC-Web only |
| Use case | Chat, games | Live feeds | Legacy | Internal services |

---

## When NOT to Use WebSocket

- Simple notifications (use SSE).
- Push to mobile (use APNs/FCM directly).
- Reading large data once (use HTTP).
- Internal service comms (use gRPC).

---

## TL;DR

- WebSocket = bi-directional persistent connection.
- Upgrade from HTTP via handshake.
- Frame-based protocol; text + binary.
- Heartbeat to detect dead connections.
- Auth via subprotocol / first-message / cookie.
- Reconnect logic client-side mandatory.
- Backpressure handling for slow clients.
- Sticky sessions or pub/sub backplane for multi-server.
