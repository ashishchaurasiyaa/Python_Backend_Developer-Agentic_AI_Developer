# 48 — HTTP Versions Deep — 0.9 / 1.0 / 1.1 / 2 / 3

> Understanding the evolution of HTTP is essential for senior interviews. Why HTTP/2 changed things. Why HTTP/3 matters.

---

## Timeline

| Version | Year | Transport | Key change |
|---|---|---|---|
| HTTP/0.9 | 1991 | TCP | Just `GET /path`, returns HTML. No headers. |
| HTTP/1.0 | 1996 | TCP | Headers, status codes, methods (POST, HEAD). One req/conn. |
| HTTP/1.1 | 1997 | TCP | Persistent conn, chunked encoding, Host header. |
| HTTP/2 | 2015 | TCP+TLS | Multiplexing, binary frames, server push, HPACK. |
| HTTP/3 | 2022 | UDP (QUIC) | Eliminates head-of-line blocking, faster handshake. |

---

## HTTP/1.0 — The Bottleneck

### How it works
```
TCP handshake (3-way)
TLS handshake (if HTTPS)
GET /index.html
← response
TCP close

# For next request, repeat everything.
```

### Problems
- New TCP connection per request → ~3 RTT overhead per request.
- For a page with 50 images: 50 sequential roundtrips.

---

## HTTP/1.1 — Persistent Connections

### Keep-Alive
Default: connection stays open after a request.
```
GET /img1.jpg HTTP/1.1
Connection: keep-alive
← response
GET /img2.jpg          ← reuses same TCP connection
← response
```

### Pipelining (mostly broken in practice)
Theoretically: send multiple requests on one connection without waiting for responses.

```
client: GET /a → GET /b → GET /c
server: response a → response b → response c   (must be in order)
```

**Problem:** Head-of-line (HOL) blocking. Slow `a` blocks `b` and `c`.
Most browsers and proxies disabled pipelining due to broken intermediaries.

### Browser workaround: parallel connections
Browsers open 6-8 connections per origin to fetch in parallel.

### Chunked transfer encoding
Server doesn't need `Content-Length` upfront. Stream response in chunks.

```
HTTP/1.1 200 OK
Transfer-Encoding: chunked

7\r\n
Mozilla\r\n
9\r\n
Developer\r\n
0\r\n     ← end marker
```

### Host header
Multiple sites on one IP. Required in HTTP/1.1.

---

## HTTP/2 — The Game Changer

### Goals
- Eliminate HOL blocking at HTTP layer.
- Reduce latency.
- Less bandwidth.

### Key features

#### 1. Binary framing
Not text anymore. Binary frames:
```
Frame type: HEADERS, DATA, SETTINGS, PUSH_PROMISE, ...
Stream ID: which logical "request" this belongs to
Payload
```

#### 2. Multiplexing
Multiple "streams" on one TCP connection. Each request/response = a stream.

```
Connection:
  Stream 1: GET /a
  Stream 3: GET /b      ← can be in flight simultaneously
  Stream 5: GET /c
```

Browser opens 1 connection (not 6). Multiplexes all requests over it.

**HOL blocking?** Still possible at TCP layer (if one packet lost, all streams stall until retransmit). Solved by HTTP/3.

#### 3. Server push
Server can preemptively send resources before client requests.
```
Client: GET /index.html
Server: HTML + (pushes /style.css and /app.js, anticipating need)
```

In practice: poorly used; mostly deprecated in browsers. Replaced by `<link rel="preload">`.

#### 4. Header compression (HPACK)
Headers repeated across requests. HPACK uses Huffman coding + dynamic table.

Initial cookie header (50 bytes) sent once; subsequent references = 1 byte.

#### 5. Stream prioritization
Client can declare: "this stream more important than that stream."

#### 6. Mandatory TLS
HTTP/2 in browsers always uses TLS (h2 over TLS). HTTP/2 cleartext (h2c) exists but rarely used.

---

## HTTP/2 Performance Wins

| Scenario | HTTP/1.1 | HTTP/2 |
|---|---|---|
| 50 small files, slow network | 3-5s | 1-1.5s |
| Large file download | Same | Same |
| API calls (many small) | Multiple connections | Single connection multiplexed |
| TLS handshake | Once per origin | Once per origin (still) |

---

## HTTP/3 — Goodbye TCP

### Why TCP is the problem

HTTP/2 multiplexes streams over TCP. But:
- TCP sees ONE stream of bytes.
- If one packet is lost, TCP waits + retransmits.
- ALL streams stall during this — even those with no lost packets.

This is the **TCP-level HOL blocking** problem.

### Solution: QUIC (UDP-based)

QUIC = Quick UDP Internet Connections (Google, now IETF standard).

```
HTTP/3 over QUIC over UDP

QUIC has streams natively (not over a single byte stream).
Lost packet only stalls its own stream.
```

### Key features

#### 1. 0-RTT handshake
After first connection (which is 1-RTT for crypto), subsequent connections to same server: 0-RTT possible. Data sent in first packet.

#### 2. Connection migration
TCP conn dies if your IP changes (WiFi → cellular). QUIC connections survive — identified by connection ID, not IP.

#### 3. Encryption built-in
TLS 1.3 integrated into QUIC. No separate handshake.

#### 4. Better congestion control
Per-stream congestion control, faster recovery from packet loss.

### Adoption (2026)
- 25%+ of web traffic over HTTP/3.
- Used by Google, Facebook, Cloudflare, Akamai.
- Most modern browsers support.

---

## HTTP/3 Limitations

### UDP middleboxes
Some firewalls/middleboxes block or rate-limit UDP. HTTP/3 falls back to HTTP/2.

### Server load
QUIC implementation in userspace; more CPU than TCP (which is in kernel).
- Kernel offload (Linux 6.x has improvements).

### Debugging
TCP has decades of tooling. QUIC packet inspection requires special tools (qlog, qvis).

### Library maturity
Less mature than HTTP/2 stacks. Improving rapidly.

---

## Practical Implications

### For API design
- HTTP/2 → smaller cost per call → reasonable to make many small calls.
- HTTP/1.1 era practice: batch requests to reduce overhead.

### For frontend
- HTTP/2: bundle less aggressively (multiplexed loads are cheap).
- HTTP/1.1: bundle hard, use sprite sheets.

### For mobile apps
- HTTP/3: massive win on lossy networks.
- Connection migration: seamless WiFi→cellular handoff.

---

## Side Quest — Server-Sent Events vs WebSocket vs HTTP/2 Push

| Feature | SSE | WebSocket | HTTP/2 push |
|---|---|---|---|
| Direction | Server → Client | Bidirectional | Server → Client |
| Protocol | HTTP | Upgraded HTTP | HTTP/2 |
| Reconnect | Built-in | Manual | N/A |
| Binary | Text only | Yes | Yes |
| Use case | Live feeds | Chat, games | Preload assets |

---

## Inspect HTTP Version

### Browser DevTools
Network tab → Headers → Protocol column shows `h2`, `h3`, `http/1.1`.

### curl
```bash
curl --http2 -v https://example.com
curl --http3 -v https://example.com
```

### nghttp (HTTP/2 client)
```bash
nghttp -v https://example.com
```

### Wireshark
QUIC has its own dissector now.

---

## Server Setup

### Nginx HTTP/2
```nginx
server {
    listen 443 ssl http2;
    ssl_certificate ...;
}
```

### Nginx HTTP/3 (1.25+)
```nginx
server {
    listen 443 ssl http2;
    listen 443 quic reuseport;
    add_header Alt-Svc 'h3=":443"; ma=86400';
    ssl_certificate ...;
}
```

### Cloudflare
HTTP/3 enabled by default for all sites since 2020.

---

## Headers Worth Knowing

```
:method, :scheme, :authority, :path  ← pseudo-headers (HTTP/2+)
Alt-Svc: h3=":443"                    ← advertises HTTP/3 availability
Server-Timing: db;dur=53, app;dur=47  ← performance hints
Early-Data: 1                          ← 0-RTT data marker
```

---

## Quick Comparison Cheat Sheet

| Feature | 1.1 | 2 | 3 |
|---|---|---|---|
| Transport | TCP | TCP | UDP (QUIC) |
| Multiplex | No | Yes (TCP HOL) | Yes (no HOL) |
| Header compress | No | HPACK | QPACK |
| Server push | No | Yes (deprecated) | No |
| Binary | No | Yes | Yes |
| TLS | Optional | Required (browsers) | Built-in |
| Handshake | 3 (TCP + TLS) | 3 (TCP + TLS) | 1 (0-RTT possible) |

---

## Interview Tips

**Common question:** *"Why is HTTP/3 better than HTTP/2?"*

**Answer arc:**
1. HTTP/2 solved HOL at app layer with multiplexing.
2. But still uses TCP → TCP itself has HOL (packet loss stalls all streams).
3. HTTP/3 uses QUIC over UDP, which has stream-level packet retransmission.
4. Net: lossy networks (mobile) see big wins. Reliable LANs see smaller wins.
5. Bonus: 0-RTT, connection migration.

**Common gotcha:** "HTTP/2 server push?" → Mostly deprecated. Use `<link rel="preload">` instead.

---

## TL;DR

- **HTTP/1.1:** One req/conn (with pipelining broken in practice). Browser opens 6+ connections per origin.
- **HTTP/2:** Multiplexing over one TCP connection. TCP HOL still an issue.
- **HTTP/3:** QUIC over UDP, streams independent. Mobile network win.

**For backend interviews:** know the HOL blocking story top-to-bottom. It explains why every protocol layer has evolved.
