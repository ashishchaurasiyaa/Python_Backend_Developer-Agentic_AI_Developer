# 49 — TCP & UDP Deep

> The transport-layer protocols that underpin everything. Senior backend engineers should be fluent in TCP behavior and know when UDP is the right tool.

---

## TCP — Transmission Control Protocol

### What it provides
- **Reliable delivery** (retransmit on loss).
- **Ordered delivery** (bytes arrive in send order).
- **Flow control** (sender doesn't overwhelm receiver).
- **Congestion control** (sender slows down if network congested).
- **Connection-oriented** (handshake + state).

### TCP segment (simplified)
```
| Source Port (16) | Destination Port (16) |
| Sequence Number (32) |
| Acknowledgment Number (32) |
| Data Offset (4) | Reserved | Flags (SYN, ACK, FIN, RST, PSH, URG) | Window Size (16) |
| Checksum (16) | Urgent Pointer (16) |
| Options (variable) |
| Data (variable) |
```

### Connection lifecycle

```
SYN → SYN-ACK → ACK    (3-way handshake)
... data exchange ...
FIN → ACK → FIN → ACK  (4-way termination)
```

### Sequence numbers
Every byte numbered. Acks acknowledge "next expected byte".

```
Sender: SEQ=1000, DATA=100 bytes
Receiver: ACK=1100   (next byte I expect)

Sender: SEQ=1100, DATA=200 bytes
Receiver: ACK=1300
```

---

## TCP Reliability

### Retransmission
Sender holds copy of bytes until ack received. If no ack in timeout (RTO), retransmit.

### RTO (Retransmission Timeout)
- Initial estimate from SRTT (smoothed RTT).
- Doubles on each retransmit (exponential backoff).
- Capped at typically 60s.

### Selective Acknowledgments (SACK)
Modern TCP. Receiver tells sender which specific blocks it got, so sender doesn't retransmit unnecessarily.

### Fast retransmit
3 duplicate ACKs → packet probably lost → retransmit immediately (don't wait for timer).

---

## TCP Flow Control

Receiver advertises `Window Size` = how many bytes it can buffer.

```
Receiver: ACK=1100, Window=8192
        (I've received up to byte 1099; I can buffer 8192 more)

Sender: respects window — won't send more than 8192 bytes without new ACK.
```

If receiver slow, window shrinks. Sender stops. Receiver consumes, window grows, sender resumes.

### Window scaling
Original TCP: max 64KB window (16-bit). Modern: window scale factor → effective window MBs.

---

## TCP Congestion Control

Different from flow control:
- Flow control: don't overwhelm receiver.
- Congestion control: don't overwhelm network.

### Congestion window (cwnd)
Sender's internal state: how much can it send without ACK.

### Phases
1. **Slow start**: cwnd starts small, doubles each RTT until threshold.
2. **Congestion avoidance**: linear increase.
3. **Fast retransmit**: on 3 dup ACKs, retransmit + reduce cwnd.
4. **Recovery**: restore.

### Algorithms
- **Reno**: original.
- **Cubic**: Linux default. Better at high BDP (bandwidth-delay product).
- **BBR (Bottleneck Bandwidth and RTT)**: Google's. Models the path, doesn't rely on packet loss.

```bash
# Check Linux congestion control
sysctl net.ipv4.tcp_congestion_control
# bbr (or cubic on most systems)
```

---

## TCP Head-of-Line Blocking

If packet N is lost:
- Packets N+1, N+2... arrive at OS but TCP holds them.
- Application can't read them until N is retransmitted.
- HTTP/2 multiplexes streams over one TCP → one lost packet blocks all streams.
- HTTP/3 solves this by going over UDP/QUIC.

---

## Nagle's Algorithm vs TCP_NODELAY

Default: TCP coalesces small writes to send fewer packets.
- Good: efficient.
- Bad: latency in interactive apps (writes wait up to 200ms).

```python
import socket
sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
```

Disables Nagle. Used by SSH, telnet, HTTP/2, gRPC.

---

## TCP Keep-Alive

By default, idle TCP connection stays open forever (until OS shuts down).

Keep-alive: periodic probe to detect dead peer.

```python
sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPIDLE, 60)    # idle before probe
sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPINTVL, 10)   # interval
sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPCNT, 5)      # max probes
```

Common: long-lived connections (DB pools, gRPC) often layer application-level keepalive (PING frames) instead of TCP keep-alive.

---

## TIME_WAIT State

After active close, the closing side enters TIME_WAIT for 2*MSL (~60-240s).

**Purpose:** ensure delayed packets from old connection don't confuse new connection on same (source IP, source port, dest IP, dest port) tuple.

**Production issue:** thousands of short-lived connections (e.g., HTTP/1.0) → port exhaustion via accumulated TIME_WAIT.

```bash
# Count TIME_WAIT
netstat -an | grep TIME_WAIT | wc -l

# Tune (use with caution)
sysctl -w net.ipv4.tcp_tw_reuse=1
```

Better fix: use persistent connections / connection pooling.

---

## UDP — User Datagram Protocol

### What it provides
- Send datagrams to a destination.
- That's it.

### Doesn't provide
- Reliability.
- Ordering.
- Flow control.
- Congestion control.
- Connection state.

### UDP datagram
```
| Source Port (16) | Destination Port (16) |
| Length (16) | Checksum (16) |
| Data (variable) |
```

Header: 8 bytes. TCP header: 20+ bytes. UDP overhead minimal.

---

## When UDP

### Latency-sensitive, loss-tolerant
- VoIP (Zoom, Teams) — losing a few packets = brief audio glitch, retransmit would cause delay > usefulness.
- Video streaming (live) — same.
- Online games (FPS) — losing a position update isn't fatal; the next one supersedes it.

### One-shot small messages
- DNS queries.
- NTP.
- DHCP.

### Custom reliable protocols on top
- **QUIC** (HTTP/3) is UDP-based with its own reliability + congestion control.
- **RUDP** (Reliable UDP) for some games.

### Multicast
- Multicast is UDP-only (TCP is point-to-point).
- Used in financial market data, in-house pub/sub.

---

## TCP vs UDP Quick Decision

| Need | Pick |
|---|---|
| File transfer, web pages | TCP |
| API calls, DB queries | TCP |
| Live video / audio | UDP (custom RTP) |
| Online games (real-time) | UDP |
| DNS | UDP (TCP fallback for large responses) |
| Service discovery (mDNS) | UDP multicast |
| Modern web (HTTP/3) | UDP via QUIC |
| Bulk transfer between datacenters | TCP (or custom UDP for special cases) |

---

## Socket Programming Basics

### TCP server (Python)
```python
import socket

sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
sock.bind(("0.0.0.0", 8080))
sock.listen(128)   # backlog

while True:
    conn, addr = sock.accept()
    # Handle conn
```

### TCP client
```python
sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.connect(("example.com", 80))
sock.sendall(b"GET / HTTP/1.1\r\nHost: example.com\r\n\r\n")
data = sock.recv(4096)
```

### UDP server
```python
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind(("0.0.0.0", 8080))

while True:
    data, addr = sock.recvfrom(1024)
    sock.sendto(b"pong", addr)
```

---

## Performance Tuning

### TCP buffer sizes
```bash
sysctl -w net.core.rmem_max=16777216    # max receive buffer
sysctl -w net.core.wmem_max=16777216    # max send buffer
sysctl -w net.ipv4.tcp_rmem='4096 87380 16777216'   # auto-tuning min, default, max
sysctl -w net.ipv4.tcp_wmem='4096 65536 16777216'
```

Larger buffers help long-distance high-throughput (bigger BDP).

### Ephemeral port range
```bash
sysctl -w net.ipv4.ip_local_port_range='1024 65535'
```

If you make outbound connections, run out of ports.

### Max connections (listen backlog)
```python
sock.listen(2048)   # OS-level limit also matters
```

```bash
sysctl -w net.core.somaxconn=4096
```

### FIN handling
Tune to clean up TIME_WAIT faster (cautiously):
```bash
sysctl -w net.ipv4.tcp_fin_timeout=15
```

---

## Common Issues

### "Connection refused"
- Nothing listening on that port.
- Listening but firewall blocks.

### "Connection reset by peer"
- Peer crashed or aborted.
- Or middlebox (LB, firewall) killed the conn.

### "Connection timeout"
- No response to SYN.
- Possible: firewall dropping silently, peer overloaded.

### Slow connection establishment
- Synflood mitigation tuning (SYN cookies).
- Backlog too small → kernel rejects.

### "Too many open files"
- File descriptor limit. `ulimit -n 65535`.

### Packet loss diagnostics
```bash
netstat -s | grep -i retrans   # TCP retransmissions
ss -ti                          # Per-connection RTT, retransmit
mtr example.com                 # path latency + loss
```

---

## Bandwidth-Delay Product (BDP)

```
BDP = bandwidth × RTT
```

For 1 Gbps link at 100ms RTT:
BDP = 10^9 * 0.1 / 8 = 12.5 MB

You need window size > BDP to fully utilize the link.

If TCP window = 64KB and BDP = 12.5MB → only using 0.5% of bandwidth!

Solution: enable window scaling (default in modern OS).

---

## NIC Offload Features

Modern NICs offload TCP processing from CPU:
- **GSO/GRO** (Generic Segmentation/Receive Offload): batch packets.
- **TSO/LRO** (TCP-specific).
- **Checksum offload**: NIC computes checksums.
- **Steering** (RSS): distribute incoming flows across CPUs.

These massively improve throughput at scale (40+ Gbps).

---

## Kernel Bypass

For HFT / ultra-low latency:
- **DPDK** (Data Plane Development Kit): userspace networking, bypass kernel.
- **RDMA** (Remote Direct Memory Access): zero-copy, between machines.
- **eBPF/XDP**: programmable packet filtering before kernel processing.

Used by: trading systems, CDNs, large-scale load balancers (Cloudflare's Magic Transit).

---

## TCP Connection Pooling

For app-to-app communication (DB, internal services):
- Reuse connections.
- Avoid TIME_WAIT proliferation.
- Faster (no handshake).

```python
# requests library uses HTTPAdapter with pool
import requests
s = requests.Session()
adapter = HTTPAdapter(pool_connections=100, pool_maxsize=100)
s.mount("http://", adapter)
```

---

## Real-World Examples

### Why DNS uses UDP
- Small payloads (< 512 bytes typically).
- Latency critical.
- Fail fast / retry better than long TCP timeout.
- Fallback to TCP for large responses (DNSSEC, AXFR).

### Why HTTP traditionally uses TCP
- Need reliability + ordering for HTML/JS.
- Connection state for sessions.

### Why HTTP/3 switched
- Eliminate TCP HOL.
- Connection migration (mobile).
- Faster handshake.

### Why gRPC streams over HTTP/2
- Persistent connections, multiplexed streams.
- Built-in flow control.

### Why Redis (over TCP)
- Connection state matters.
- Ordered command/response.

### Why DNS query (over UDP usually)
- Stateless, idempotent retry.
- One round trip.

---

## TL;DR

**TCP:** reliable, ordered, congestion-controlled, connection-oriented. Default choice.

**UDP:** unreliable, unordered, no state. Use when latency > correctness or you implement reliability yourself (QUIC, RTP).

**Modern era:** UDP-based protocols (QUIC, WebRTC) are catching up to TCP for general use cases — kernel bypass and connection migration are big wins.

**Interview gold:** Be able to explain head-of-line blocking, congestion control, and why HTTP/3 went UDP.
