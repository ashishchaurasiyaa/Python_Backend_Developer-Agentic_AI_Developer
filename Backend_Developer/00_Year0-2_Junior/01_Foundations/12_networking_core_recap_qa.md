# Networking — Core Basics Recap Q&A (Interview Deep Dive)

> Self-test recap of [03_networking_fundamentals.md](03_networking_fundamentals.md) and [03_networking_deepdive_hinglish.md](03_networking_deepdive_hinglish.md), Round 3a (core basics — OSI, IP, ports, TCP/UDP). Format: analogy → concept → live proof (real numbers from this machine).

---

## Topic 1. Encapsulation (OSI layers, headers)

**Analogy:** Sending a letter — you write the letter (app data), put it in an envelope with an address (TCP header), the post office puts it in a city-routed packet (IP header), the courier van has its own route label (Ethernet header). Each layer wraps the layer above without looking inside it. Receiving end unwraps in reverse.

### Live Proof (see [encapsulation_header_bytes_demo.py](encapsulation_header_bytes_demo.py))

```
Step 1: Application data (raw HTTP request)         = 46 bytes
Step 2: + TCP header (20 bytes)                     = 66 bytes
Step 3: + IP header (20 bytes)                      = 86 bytes
Step 4: + Ethernet header (14) + trailer/FCS (4)    = 104 bytes  (actual wire frame)
```
Decapsulating the raw 104-byte frame recovered the exact original data byte-for-byte, plus parsed metadata at every layer (`src_mac`/`dst_mac`, `src_ip=10.0.0.5`/`dst_ip=93.184.216.34`/`ttl=64`/`protocol=6`(TCP), `src_port=52134`/`dst_port=443`).

**Key number:** **58 bytes of header/trailer overhead** wrapped around just **46 bytes of real data** for a tiny request — overhead is more than half the wire size. This is exactly why HTTP/2 header compression (HPACK) and keep-alive connections matter at scale.

---

## Topic 2. Private/Public IP + Loopback vs 0.0.0.0

**Private IP ranges** (`10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`) exist because IPv4 has only ~4.3 billion addresses — private ranges can be **reused by every home/office network** because they're only meaningful inside that local network (like apartment numbers being reused across different buildings). **NAT** (Network Address Translation) is what makes this work: the router rewrites the source IP of outbound packets to its own single public IP, and tracks which internal device each response belongs to.

**Loopback (`127.0.0.1`) vs `0.0.0.0`:**

| Bind address | Meaning |
|---|---|
| `127.0.0.1` | Server accepts connections **only from the same machine** — no other device (even on the same LAN) can connect |
| `0.0.0.0` | Server accepts connections on **all network interfaces** — loopback AND LAN AND any other interface the machine has |

### Live Proof (see [bind_loopback_vs_lan_demo.py](bind_loopback_vs_lan_demo.py) — fixed during this session, see note below)

```
Bound to 127.0.0.1 (loopback only):
  Connecting via LAN IP (192.168.1.54)  -> FAILED (Connection refused)
  Connecting via 127.0.0.1              -> SUCCESS

Bound to 0.0.0.0 (all interfaces):
  Connecting via LAN IP (192.168.1.54)  -> SUCCESS
  Connecting via 127.0.0.1              -> SUCCESS
```

**Repo bug found + fixed during this session:** the original script used `listen(1)` with no `accept()` call, which caused the *second* connection attempt in each block to fail from **backlog queue exhaustion** (not a real networking restriction) — it looked like "0.0.0.0 doesn't accept loopback connections," which is false. Fixed by raising the backlog and adding `accept()`+`close()` per attempt so each connection is properly drained. Verified independently with a throwaway script (backlog=5, no draining) before applying the real fix — confirms `0.0.0.0` genuinely accepts loopback connections just fine.

**Common trap:** `0.0.0.0` is a wildcard bind address, not a real machine IP — you'd still browse to `http://localhost:8000` or `http://<LAN-IP>:8000`, never `http://0.0.0.0:8000`.

---

## Topic 3. Port + Socket + Ephemeral Port

**Port** = which "flat" inside the "building" (IP) — lets one IP host thousands of independent services (`:8000` app, `:5432` Postgres, `:6379` Redis).

**Socket** = not just an IP or a port — it's the full **5-tuple**: `(protocol, local IP, local port, remote IP, remote port)`. This is why one server on port 8000 can serve thousands of simultaneous clients — each client's `(remote IP, remote port)` is different even though the server's side is fixed.

### Live Proof (see [network_ip_port_mac_demo.py](network_ip_port_mac_demo.py))

```
Three services bound on same IP, different ports:
  127.0.0.1:61793, 127.0.0.1:61794, 127.0.0.1:61795

Server listening at 127.0.0.1:61796  (fixed, well-known port)
Client's OS-assigned ephemeral port: 61797  (client did NOT choose this)
Server sees incoming connection from: ('127.0.0.1', 61797)
```

**Ephemeral port:** when a client opens an outbound connection, the OS auto-assigns a temporary high-numbered port (typically 32768–60999 on Linux, 49152–65535 on macOS/Windows). Freed for reuse once the connection closes.

**Senior gotcha:** Ephemeral ports are a **limited pool** (~16,000–28,000 depending on OS). A service that opens a fresh outbound connection per request without pooling/reuse can exhaust this pool under load — see Topic 6 (TIME_WAIT) for the concrete mechanism.

---

## Topic 4. TCP 3-Way Handshake + 4-Way Termination

**Analogy:** Starting/ending a phone call.

**3-way handshake (starting):**
```
Client --SYN(seq=X)-------------> Server      "Hello, connect karna chahta hoon"
Client <--SYN-ACK(seq=Y,ack=X+1)-- Server      "Sunn raha hoon, mera bhi seq lo"
Client --ACK(ack=Y+1)-------------> Server     "Confirm, ab baat shuru"
                [ESTABLISHED]
```
Needs 3 messages because **both sides** must confirm readiness AND exchange sequence numbers **for both directions** (TCP is full-duplex).

**4-way termination (ending):**
```
Client --FIN--> Server     "Mera kehna khatam"
Client <--ACK-- Server     "Suna"
Client <--FIN-- Server     "Mera bhi khatam"
Client --ACK--> Server     "Confirm"
```
Needs 4 messages (2 independent pairs) because each direction of the full-duplex connection must be closed separately (half-close is possible — one side can stop sending while still receiving).

### Live Proof (see [tcp_states_demo.py](tcp_states_demo.py))

```
LISTEN:      127.0.0.1:61944 (LISTEN)
ESTABLISHED: shown on BOTH sides after real handshake —
             127.0.0.1:61945->127.0.0.1:61944 (ESTABLISHED)  [client]
             127.0.0.1:61944->127.0.0.1:61945 (ESTABLISHED)  [server]
After close(): 127.0.0.1.61945  127.0.0.1.61944  TIME_WAIT   [real kernel state, verified via netstat]
```

**Why TCP = "connection-oriented" and UDP isn't:** the handshake establishes shared state (both sides know they're "connected," sequence numbers tracked for ordering/retransmission). UDP has no handshake — a packet is just sent, no shared state exists to detect loss.

---

## Topic 5. TCP vs UDP

**Analogy:** TCP = registered post (tracked, acknowledged, automatically retransmitted, ordered — but slower/heavier). UDP = postcard (no tracking, no retransmission, possibly out of order — but fast/light).

### Live Proof (see [tcp_byte_stream_vs_udp_datagram_demo.py](tcp_byte_stream_vs_udp_datagram_demo.py)) — the real fundamental difference

```
TCP: ONE recv() call returned: b'HELLOWORLD'
     'HELLO' and 'WORLD' were TWO separate send() calls, arrived as ONE blob
     -> TCP has NO message boundaries, only an ordered byte stream

UDP: TWO separate recvfrom() calls returned: b'HELLO' and b'WORLD'
     -> each sendto() = exactly one recvfrom() -- UDP PRESERVES datagram boundaries
```
This is the detail most people miss — TCP doesn't preserve "messages," only a continuous byte stream. Application protocols must implement their own message framing (e.g. HTTP's `Content-Length` header or chunked encoding).

### Real backend use cases for UDP over TCP

| Use case | Why UDP wins |
|---|---|
| DNS queries | Tiny query+response, one round trip — TCP's handshake overhead > actual data |
| Live video/voice (WebRTC) | A lost/late frame should be dropped and skipped, not retransmitted and blocking the stream |
| Online multiplayer gaming | Stale position updates are useless even if delivered — retransmission just adds latency |
| DHCP | Device doesn't have an IP yet — no TCP connection concept applies |
| HTTP/3 (QUIC) | Built on UDP with its own reliability layer in user-space, avoiding TCP's head-of-line blocking (one lost packet blocks the whole connection in TCP; QUIC blocks only that one stream) |

**Interview one-liner:** TCP when correctness > speed (file transfer, API calls, DB queries). UDP when freshness > completeness (real-time media, gaming) or when overhead must be minimal (DNS).

---

## Topic 6. TIME_WAIT

**Analogy:** Restaurant table cleanup — after a customer leaves, the waiter doesn't seat a new one instantly; the table is held for a cleanup/safety buffer first.

**Why it exists:**
1. **Delayed/duplicate packet safety** — an old in-flight packet from the closed connection could otherwise be misread as belonging to a new connection if the port were reused instantly.
2. **Final ACK reliability** — if the last ACK of the 4-way termination is lost, the peer will resend its FIN; staying in TIME_WAIT lets you catch and re-ACK it correctly.

**Whoever sends the FIN first (the "active closer") is the side that enters TIME_WAIT** — not always the client, a common misconception.

### Live Proof (see [tcp_time_wait_exhaustion_demo.py](tcp_time_wait_exhaustion_demo.py) — built during this session)

20 rapid open-close connections, no pooling:
```
Total TIME_WAIT sockets: 29
  Client-side (client closed first, the usual case): 20   <- exactly matches N_CONNECTIONS
  Server-side (server raced ahead and closed first):  9   <- real timing race, confirms
                                                             "whoever FINs first" rule,
                                                             not "always the client"
```

### Production problem — TIME_WAIT exhaustion (senior-level gotcha)

```
Problem: high-churn short-lived connections, no pooling
         -> tens of thousands of sockets pile up in TIME_WAIT (~60s hold each, macOS/Linux default)
         -> ephemeral port pool (~16k-28k) gets exhausted
         -> new outbound connections fail: "Cannot assign requested address"
```

**Fixes:**
- **Connection pooling** — reuse existing TCP connections instead of opening a new one per request (addresses root cause)
- `net.ipv4.tcp_tw_reuse=1` (Linux kernel param) — allows safe reuse of a TIME_WAIT socket for new outgoing connections
- **HTTP keep-alive** — avoid closing connections between requests at all

---

## Repo fixes made during this recap session

1. **[bind_loopback_vs_lan_demo.py](bind_loopback_vs_lan_demo.py)** — fixed a `listen(1)`-with-no-`accept()` bug that made the demo falsely appear to show `0.0.0.0` rejecting loopback connections (it was backlog exhaustion, not a real networking restriction).
2. **[tcp_time_wait_exhaustion_demo.py](tcp_time_wait_exhaustion_demo.py)** — new demo added, proving TIME_WAIT pile-up under rapid connection churn with real, verified counts (including the client-vs-server race nuance).

## Round 3a Scorecard

User had not memorized these answers going in — this round was taught fresh, topic by topic, with live proof for each. Revisit before interviews:
- Encapsulation header overhead numbers
- Loopback vs 0.0.0.0 (and the fixed demo)
- Ephemeral ports + exhaustion risk
- 3-way/4-way handshake message counts and *why* each count
- TCP byte-stream vs UDP datagram boundary distinction
- TIME_WAIT: why it exists, who gets it, and the production exhaustion fix
