# Foundations — Networking Fundamentals for Backend Devs
**Foundations · Year 0-2 | Zero → Senior**

## Quick Concepts

- **IP address** = network address of a host (IPv4: `192.168.1.1`, IPv6: `2001:db8::1`)
- **Port** = number identifying a service on a host (e.g., 80=HTTP, 443=HTTPS, 5432=Postgres)
- **MAC address** = hardware identifier of network card
- **Subnet** = group of IP addresses (e.g., `10.0.0.0/24` = 256 IPs)
- **TCP** = reliable, ordered, connection-based protocol
- **UDP** = fast, unreliable, connectionless
- **HTTP/HTTPS** = application protocols built on TCP
- **DNS** = name → IP resolution
- **Socket** = endpoint for sending/receiving data over network
- **Latency** = time for one packet round-trip
- **Bandwidth** = data per unit time (Mbps/Gbps)
- **MTU** = max packet size (typically 1500 bytes)

---

## Why Backend Devs Need This

```
Daily backend = network communication.

You can't debug:
   ✗ "Why is my API slow?" (without knowing TCP RTT)
   ✗ "Why connection refused?" (without knowing TCP handshake)
   ✗ "Why my DNS is flaky?" (without knowing resolution chain)
   ✗ "Why CORS error?" (without HTTP basics)
   ✗ "Why are we hitting connection limits?" (without TCP states)

These are every-week problems.
```

---

## OSI Model (7 Layers) — Mental Map

```
Layer 7 — Application      HTTP, HTTPS, gRPC, DNS, FTP, SMTP
Layer 6 — Presentation     TLS encryption, encoding
Layer 5 — Session          Connection management
Layer 4 — Transport        TCP, UDP, QUIC
Layer 3 — Network          IP (IPv4, IPv6), routing
Layer 2 — Data Link        Ethernet, Wi-Fi (MAC addresses)
Layer 1 — Physical         Cables, radio waves
```

### TCP/IP Stack (Pragmatic 4-layer view)

```
   Application       (HTTP, gRPC, DNS, …)
   Transport         (TCP, UDP)
   Network           (IP)
   Link              (Ethernet, Wi-Fi)
```

### What This Means in Practice

```
When you call api.example.com/users:

Layer 7  HTTP request "GET /users HTTP/1.1\r\nHost: api.example.com\r\n"
                            │
Layer 6  TLS encrypts it      │
                            │
Layer 4  TCP wraps in segments with port 443 + checksums
                            │
Layer 3  IP wraps each segment with src + dst IP addresses
                            │
Layer 2  Ethernet wraps with MAC addresses (router hops)
                            │
Layer 1  Bits sent over fiber / Wi-Fi

Server reverses the process to read your request.
```

---

## IP Addresses

### IPv4

```
Format: 4 octets, each 0-255
   192.168.1.1
   10.0.0.50

Total: ~4.3 billion addresses (exhausted)
Notation: dotted-decimal
```

### IPv6

```
Format: 8 groups of 4 hex digits
   2001:0db8:85a3:0000:0000:8a2e:0370:7334
   Short:  2001:db8:85a3::8a2e:370:7334

Total: 2¹²⁸ addresses (basically unlimited)
Adoption: ~40% of internet in 2026
```

### Special Ranges

```
Private (not routable on internet):
   10.0.0.0/8        — 16.7M addresses (used in AWS VPC)
   172.16.0.0/12     — Docker default
   192.168.0.0/16    — Home networks

Loopback:
   127.0.0.0/8       — localhost (127.0.0.1)

Link-local:
   169.254.0.0/16    — auto-configured (no DHCP)

Broadcast:
   255.255.255.255   — all hosts on subnet
```

### CIDR Notation

```
10.0.0.0/24    →  10.0.0.0 — 10.0.0.255       (256 IPs)
10.0.0.0/16    →  10.0.0.0 — 10.0.255.255     (65,536 IPs)
10.0.0.0/8     →  10.0.0.0 — 10.255.255.255   (16M IPs)
10.0.0.0/32    →  single host

/N means "first N bits are network, rest is host"
```

---

## Ports

### Port Ranges

```
0-1023      → Well-known (HTTP=80, HTTPS=443, SSH=22, DNS=53)
1024-49151  → Registered (Postgres=5432, Redis=6379, MongoDB=27017)
49152-65535 → Ephemeral (client outbound ports)
```

### Common Backend Ports

```
80      HTTP
443     HTTPS
22      SSH
21      FTP
53      DNS
25      SMTP
587     SMTP (TLS)
3306    MySQL
5432    PostgreSQL
6379    Redis
27017   MongoDB
9092    Kafka
5672    RabbitMQ
8000    Common dev port (FastAPI default)
3000    Common dev port (React/Node)
8080    Common alt-HTTP
9200    Elasticsearch
```

### Check What's Listening

```bash
ss -tlnp                    # all TCP listeners + process
ss -tlnp | grep :8000       # who has port 8000

# Older alternative
netstat -tlnp

# Mac
lsof -i :8000
```

---

## TCP (Transmission Control Protocol)

### Properties

```
✓ Reliable    — guaranteed delivery (retransmit lost packets)
✓ Ordered     — packets reassembled in order
✓ Connection-based — establish before sending
✓ Flow control — receiver tells sender to slow down
✓ Congestion control — backs off if network congested

✗ Slower than UDP (more overhead)
✗ Head-of-line blocking (one lost packet stalls others)
```

### Three-Way Handshake

```
   Client                          Server
     │                               │
     │  ─── SYN, seq=x ────────────► │
     │                               │
     │  ◄── SYN+ACK, seq=y, ack=x+1│
     │                               │
     │  ─── ACK, ack=y+1 ──────────► │
     │                               │
     │  ◄══════ connection ════════► │
     │       established
```

Cost: 1 RTT (round-trip time) before any data sent.

### Connection Termination (4-Way Handshake)

```
   Client                          Server
     │  ─── FIN ────────────────►  │
     │  ◄── ACK ─────────────────  │
     │                              │
     │   (server finishes work)     │
     │                              │
     │  ◄── FIN ──────────────────  │
     │  ─── ACK ────────────────► │

State after: TIME_WAIT (60-120 sec, prevents stale packets)
```

### TCP States You'll See

```
LISTEN        — server waiting for connections
ESTABLISHED   — connection active
TIME_WAIT     — recently closed, waiting before fully releasing
CLOSE_WAIT    — remote closed, local hasn't yet (your bug!)
SYN_SENT      — client sent SYN
SYN_RECV      — server received SYN, waiting for ACK
FIN_WAIT_1/2  — local sent FIN
```

```bash
ss -tn    # all TCP in tabular form
ss -tn state established
ss -tn state time-wait | wc -l   # how many in TIME_WAIT
```

### Senior Pattern: TIME_WAIT Exhaustion

```
Problem: many short-lived connections → 30k+ in TIME_WAIT
→ run out of ephemeral ports → "Cannot assign requested address"

Solutions:
   ✓ Use connection pooling (keep TCP alive, reuse)
   ✓ net.ipv4.tcp_tw_reuse=1 (Linux kernel param)
   ✓ Don't open new connection per request
```

---

## UDP (User Datagram Protocol)

### Properties

```
✓ Fast      — no handshake, no reliability overhead
✓ Stateless — no connection
✓ Multicast — one-to-many

✗ Unreliable — packets may be lost/duplicated/reordered
✗ Application must handle delivery if it cares
```

### Use Cases

```
✓ DNS queries (1 packet up + 1 down)
✓ Video / audio streaming (lose a frame, keep going)
✓ Gaming (low latency > reliability)
✓ Logs (statsd, syslog)
✓ QUIC (modern UDP-based replacement for TCP)
```

### TCP vs UDP — At a Glance

```
                  TCP         UDP
                  ──────────  ──────────
   Connection    Yes         No
   Reliability   Yes         No (DIY)
   Order         Yes         No (DIY)
   Speed         Slower      Faster
   Overhead      20+ bytes/pkt   8 bytes/pkt
   Use cases     HTTP, DB, SSH   DNS, video, gaming
```

---

## HTTP (Application Layer)

### Request Structure

```
GET /api/users/42 HTTP/1.1\r\n
Host: api.example.com\r\n
Authorization: Bearer eyJ...\r\n
Content-Type: application/json\r\n
\r\n
<body if POST/PUT>
```

### Response Structure

```
HTTP/1.1 200 OK\r\n
Content-Type: application/json\r\n
Content-Length: 45\r\n
\r\n
{"id": 42, "name": "alice"}
```

### Methods (Verbs)

```
GET      — read (idempotent, safe)
POST     — create (NOT idempotent)
PUT      — replace (idempotent)
PATCH    — partial update
DELETE   — remove (idempotent)
HEAD     — like GET but no body
OPTIONS  — what methods are allowed (CORS preflight)
```

### Status Codes (Categories)

```
1xx Informational    100 Continue, 101 Switching Protocols
2xx Success          200 OK, 201 Created, 204 No Content
3xx Redirect         301 Moved (permanent), 302 Found, 304 Not Modified
4xx Client Error     400, 401, 403, 404, 405, 409, 422, 429
5xx Server Error     500, 502 Bad Gateway, 503 Unavailable, 504 Timeout
```

### Versions

```
HTTP/1.0  — one request per TCP connection
HTTP/1.1  — keep-alive, pipelining (rarely used)
HTTP/2    — multiplexed streams, binary, server push, header compression
HTTP/3    — over QUIC (UDP), no head-of-line blocking
```

### Why HTTP/2 Matters

```
HTTP/1.1:
   ✗ One request at a time per connection
   ✗ Need 6+ TCP connections per origin

HTTP/2:
   ✓ Multiplexed streams (many in parallel) on ONE connection
   ✓ Binary framing (faster parsing)
   ✓ HPACK header compression
   ✗ Still head-of-line blocking at TCP layer

HTTP/3 (QUIC):
   ✓ Multiplexing without TCP HoL blocking
   ✓ 0-RTT reconnect (faster)
   ✓ Better mobile (connection migration)
   → See 01_Year3-4_Mid/02_API_Design/20_http3_quic.md for deep dive
```

### Headers Backend Devs Care About

```
Authorization: Bearer <token>
Cookie: session=abc123
Content-Type: application/json
Accept: application/json
User-Agent: Mozilla/...
X-Forwarded-For: 1.2.3.4         # client IP behind proxy
X-Request-ID: uuid                # tracing
Cache-Control: max-age=3600
ETag: "abc123"
If-None-Match: "abc123"           # conditional GET
Idempotency-Key: uuid             # safe retries
```

---

## TLS / HTTPS

### Why TLS

```
Without TLS (plain HTTP):
   ✗ Anyone on network can read your data
   ✗ Anyone can modify it (MITM)
   ✗ You can't verify the server's identity

With TLS:
   ✓ Encrypted (confidentiality)
   ✓ Integrity (tampering detected)
   ✓ Authenticated (certificates verify identity)
```

### TLS Handshake (Simplified — TLS 1.3)

```
   Client                          Server
     │                                │
     │  ClientHello (ciphers, key)  │
     │  ─────────────────────────► │
     │                                │
     │  ServerHello + Certificate    │
     │  ◄─────────────────────────  │
     │                                │
     │   (verify cert against CA)    │
     │                                │
     │  ─── Finished ────────────►   │
     │  ◄── Finished ───────────     │
     │                                │
     │  ═══ Encrypted traffic ═══   │
```

TLS 1.3: 1-RTT handshake (vs 2-RTT in TLS 1.2). With session resumption: 0-RTT.

### Certificates

```
A certificate = public key + identity + signature

Chain of trust:
   Your site cert
      ↑ signed by
   Intermediate CA
      ↑ signed by
   Root CA (trusted by browser/OS)
```

### Senior Tools

```bash
# View cert details
openssl s_client -connect example.com:443 -showcerts

# Check expiry
echo | openssl s_client -connect example.com:443 2>/dev/null \
   | openssl x509 -noout -dates

# Test TLS config
curl -v https://example.com
nmap --script ssl-enum-ciphers -p 443 example.com
```

---

## DNS (Domain Name System)

### Resolution Flow

```
You type api.example.com:
   1. Browser cache (in-memory)
   2. OS cache (`/etc/hosts` first)
   3. Local resolver (router / ISP)
   4. Recursive resolver (8.8.8.8, 1.1.1.1)
   5. Root server (.)         — knows .com server
   6. TLD server (com.)        — knows example.com server
   7. Authoritative server     — knows api.example.com → IP

Result is cached at each level with TTL.
```

### Record Types

```
A       IPv4 address       (api.example.com → 1.2.3.4)
AAAA    IPv6 address
CNAME   alias              (www.example.com → example.com)
MX      mail server
TXT     text (SPF, DKIM, ownership proofs)
NS      nameservers
SOA     start of authority
SRV     service location
CAA     certificate authority allowed to issue
PTR     reverse lookup (IP → name)
```

### Tools

```bash
dig example.com                 # full DNS query
dig +short example.com          # just the answer
dig MX example.com              # mail records
dig @8.8.8.8 example.com        # specific resolver

nslookup example.com            # alternative
host example.com                # simpler

# Reverse DNS
dig -x 1.2.3.4
```

### TTL & Caching

```
TTL = how long answer is cached.

Short TTL (60s):
   ✓ Faster propagation on changes
   ✗ More DNS queries
   ✓ For failover / rolling deploys

Long TTL (24h):
   ✓ Less DNS load
   ✗ Changes take a day to propagate

Senior pattern:
   - Use short TTL (60-300s) for app records
   - Long TTL for static infra (NS, MX)
```

### DNS Failures Backend Devs Hit

```
1. "Host not found"
   → DNS misconfigured
   ✓ Check /etc/resolv.conf
   ✓ dig from app server

2. Slow first-request
   → Cold DNS cache
   ✓ Pre-resolve on startup
   ✓ Set short timeout

3. "Connection refused" after deploy
   → DNS TTL not expired, hitting old IP
   ✓ Lower TTL BEFORE migrations

4. AWS RDS / ElastiCache endpoints change
   → DNS-based failover; app caches the old IP
   ✓ Don't cache resolved IPs; trust DNS each call
```

---

## Network Diagnostic Tools

### Connectivity

```bash
ping -c 4 example.com          # ICMP reachable + latency
traceroute example.com         # path through routers
mtr example.com                # ping + traceroute combined
```

### Port testing

```bash
nc -zv host 5432               # is port open?
telnet host 5432               # connect interactively
nmap -p 80,443,8080 host       # scan

# Self-test
nc -l 9000                     # listen on 9000 (one side)
nc remote 9000                 # connect (other side)
```

### HTTP debugging

```bash
curl -v https://api.example.com/users
curl -I https://example.com    # headers only
curl -w "Time: %{time_total}s\n" -o /dev/null -s URL

# Time breakdown
curl -w "DNS: %{time_namelookup}s\n\
Connect: %{time_connect}s\n\
SSL: %{time_appconnect}s\n\
TTFB: %{time_starttransfer}s\n\
Total: %{time_total}s\n" -o /dev/null -s https://api.example.com
```

### Packet capture

```bash
# All packets on interface
sudo tcpdump -i eth0

# Only port 80
sudo tcpdump -i any port 80

# Save for Wireshark
sudo tcpdump -i any -w capture.pcap

# Just headers, no payload
sudo tcpdump -nn -i any port 5432

# Inspect specific host
sudo tcpdump -i any host 1.2.3.4
```

---

## Sockets (Programmer's View)

### Python TCP Server

```python
import socket

server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
server.bind(("0.0.0.0", 8000))
server.listen(128)

while True:
    conn, addr = server.accept()
    data = conn.recv(1024)
    conn.send(b"Hello\n")
    conn.close()
```

### Python TCP Client

```python
import socket

with socket.create_connection(("example.com", 80)) as sock:
    sock.sendall(b"GET / HTTP/1.1\r\nHost: example.com\r\n\r\n")
    response = sock.recv(4096)
    print(response.decode())
```

### What's Happening at OS Level

```
socket()  — create file descriptor
bind()    — attach FD to (IP, port)
listen()  — kernel queues incoming connections
accept()  — pop from queue, return new FD for connection
recv()    — read bytes
send()    — write bytes
close()   — release FD
```

### Why It Matters for Backend

```
✓ Each accepted connection = 1 FD
✓ FastAPI / Uvicorn manage this via asyncio under the hood
✓ Tune kernel: net.core.somaxconn for accept queue size
✓ Tune ulimit -n for max FDs
```

---

## Common Senior Issues & Fixes

### "Connection Refused"

```
Cause:
   ✓ Server not listening on that port
   ✓ Firewall blocking
   ✓ Wrong IP/host

Diagnose:
   ss -tlnp | grep :8000     # is something listening?
   curl -v target            # what error
   telnet target 8000        # raw TCP test
```

### "Connection Timed Out"

```
Cause:
   ✓ Network unreachable (routing)
   ✓ Server overloaded (queue full)
   ✓ Firewall silently dropping

Diagnose:
   ping target               # any reachability?
   traceroute target         # where does it stop?
   sudo iptables -L          # check firewall (Linux)
```

### "Too Many Open Files"

```
Cause:
   ✓ ulimit -n too low
   ✓ Not closing connections (leak)
   ✓ Connection pool too big

Fix:
   ulimit -n 65536
   Check: lsof -p $PID | wc -l
   Use context managers / connection pools
```

### "Address Already in Use"

```
Cause:
   ✓ Previous process still in TIME_WAIT
   ✓ Another process using port

Fix:
   setsockopt SO_REUSEADDR
   ss -tlnp | grep :PORT
   pkill old_process
```

### Slow API but server CPU low

```
Cause:
   ✓ DNS resolution slow
   ✓ TLS handshake (no session reuse)
   ✓ TCP packet loss
   ✓ Database query slow
   ✓ External API call slow

Diagnose:
   curl -w timing breakdown
   strace on production process
   APM tools (OpenTelemetry)
```

---

## NAT, Proxies, Load Balancers

### NAT (Network Address Translation)

```
Your home router does NAT:
   - Inside: 192.168.1.x (private)
   - Outside: 73.45.6.7 (public)
   - Maps connections via port

You can't initiate to inside without port forwarding.
This is why "behind NAT" is a problem for P2P.
```

### Forward Proxy

```
You → Proxy → Internet

Use: corporate firewall, privacy, caching
You configure the proxy.
```

### Reverse Proxy

```
Internet → Reverse Proxy → Your servers

Use: load balancing, SSL termination, caching, security
Server is "hidden" behind proxy.
Examples: Nginx, HAProxy, Envoy, CloudFront, Cloudflare.
```

### Load Balancer

```
Internet → LB → [Server 1, 2, 3, ...]

Algorithms: round-robin, least-connection, hash, weighted
Layer 4 (TCP): cheap, no app awareness
Layer 7 (HTTP): can route by URL, headers
```

### Real Stack

```
Internet
   ↓
DNS (Route53)
   ↓
ALB / NLB (AWS) or Nginx
   ↓
Kubernetes Ingress
   ↓
Service (load balances across pods)
   ↓
Your FastAPI pod
```

---

## CORS (Cross-Origin Resource Sharing)

### Why It Exists

```
Browser security: by default, JS from origin A
can't fetch from origin B.

Origin = scheme + host + port
   https://app.example.com   ≠   https://api.example.com
   http://localhost:3000     ≠   http://localhost:8000
```

### How It Works

```
1. Browser makes preflight OPTIONS request:
   OPTIONS /users HTTP/1.1
   Origin: https://app.example.com
   Access-Control-Request-Method: POST

2. Server responds:
   Access-Control-Allow-Origin: https://app.example.com
   Access-Control-Allow-Methods: GET, POST
   Access-Control-Allow-Headers: Content-Type, Authorization
   Access-Control-Max-Age: 86400

3. Browser then sends actual request.
```

### FastAPI Setup

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://app.example.com"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### Senior Gotchas

```
✗ allow_origins=["*"] + allow_credentials=True → browsers reject
✗ Forgetting OPTIONS in your reverse proxy → preflight fails
✗ CORS error in console — server is fine, browser blocks
✗ Server-to-server doesn't have CORS (only browsers)
```

---

## Backend Networking Cheatsheet

```bash
# Discover services
ss -tlnp                  # what's listening locally
nmap host                 # what's listening remotely

# Test HTTP
curl -v URL
curl -w timing URL

# Test TCP
nc -zv host port

# Trace network path
traceroute target
mtr target

# DNS
dig domain
dig +short domain

# Live packets
sudo tcpdump -i any port 80

# Connections
ss -tn state established | wc -l
ss -tn 'state established sport = :8000' # connections to my port
ss -tn state time-wait | wc -l            # TIME_WAITs
```

---

## Interview Questions

### Q1: Explain the TCP 3-way handshake

Client sends SYN with sequence x. Server replies SYN-ACK (its sequence y + ack=x+1). Client sends ACK (ack=y+1). Connection established. Costs 1 RTT — that's why connection reuse / keep-alive matters.

### Q2: TCP vs UDP — when to use each?

TCP for reliable, ordered, connection-oriented (HTTP, DB, SSH). UDP for low-latency, fire-and-forget (DNS, video, gaming, statsd). TCP has more overhead per packet and a handshake; UDP has neither.

### Q3: What happens when you type `api.example.com` in code?

1. DNS resolution (cache → resolver → root → TLD → auth)
2. TCP handshake to resolved IP on port 443
3. TLS handshake (cert validation + key exchange)
4. HTTP request sent
5. HTTP response received
6. TCP close (or keep-alive for reuse)

### Q4: What's HTTP/2 multiplexing?

In HTTP/1.1, you need a separate TCP connection (or wait) per request. HTTP/2 sends many requests in parallel over ONE TCP connection via "streams." Reduces connection overhead and head-of-line blocking at the HTTP layer (but not TCP — that's what HTTP/3 fixes).

### Q5: What's the difference between forward and reverse proxy?

Forward proxy sits between YOU and the internet (corporate firewall, anonymizer). Reverse proxy sits between the internet and YOUR servers (Nginx, ALB). Forward proxy you configure; reverse proxy you're served by.

### Q6: Why does CORS exist?

Browser security feature preventing JS on origin A from reading data from origin B without explicit permission. Server-side calls don't have this restriction. Implemented via preflight OPTIONS + Access-Control-* headers.

### Q7: What's a TCP TIME_WAIT and why does it matter?

After closing, the side that initiated close stays in TIME_WAIT (~2× MSL = 60-120s) to absorb stale packets. Many short-lived connections → many TIME_WAITs → ephemeral port exhaustion → can't open new connections. Solutions: connection pooling, SO_REUSEADDR, kernel tuning.

### Q8: What's a CIDR notation?

`10.0.0.0/24` = first 24 bits are network, last 8 are host = 256 IPs. The smaller the /N, the bigger the range.

### Q9: Why is DNS often the slowest part of a request?

First request must traverse the resolver chain (potentially round-trips). After that it's cached. Mitigations: short TTL for changeability, but pre-resolve at app startup or use connection pools so resolution happens once per connection lifecycle.

### Q10: Difference between A and CNAME records?

`A` maps a name to an IPv4 address directly. `CNAME` aliases a name to another name (which then resolves). CNAME can't be on the root domain (apex). Many providers use "ALIAS" or "ANAME" as workaround.

---

## Senior Mantras

```
1. Every API call = DNS + TCP + TLS + HTTP. Optimize each.

2. Reuse connections. Keep-alive + pooling.

3. Set short DNS TTL before migrations, long after.

4. ss > netstat (faster, newer).

5. tcpdump is your friend when logs lie.

6. Containers behind LBs: trust X-Forwarded-For carefully (spoofable).

7. HTTPS is the default. Plain HTTP only in localhost dev.

8. Browser CORS errors are CLIENT-side, server is fine.

9. Connection limits matter: ulimit + somaxconn + connection pool.

10. Network latency dominates wall-clock time. Optimize round trips.
```

---

## Related

- [01_linux_bash_essentials.md](01_linux_bash_essentials.md) — commands used
- [02_os_concepts.md](02_os_concepts.md) — sockets at OS level
- [04_git_workflows.md](04_git_workflows.md) — version control
- [../02_Year5+_Senior/01_System_Design/HLD_Theory/](../../02_Year5+_Senior/01_System_Design/HLD_Theory) — for HLD context
- [../01_Year3-4_Mid/02_API_Design/](../../01_Year3-4_Mid/02_API_Design) — HTTP deep dives
