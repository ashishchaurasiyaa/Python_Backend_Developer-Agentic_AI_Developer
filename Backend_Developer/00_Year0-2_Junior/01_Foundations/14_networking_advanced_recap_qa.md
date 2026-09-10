# Networking — Advanced Recap Q&A (Interview Deep Dive)

> Self-test recap of [03_networking_fundamentals.md](03_networking_fundamentals.md), Round 3c (senior debugging, NAT/proxies/load balancing, CORS, connection pooling). Format: analogy → concept → live proof (real output from this machine).

---

## Topic 1. Connection Refused vs Connection Timeout

**Analogy:** Connection Refused = you reached the right address, but no one opened the door (nothing listening on that port) — the OS immediately replies with a rejection (RST). Connection Timeout = you never even found the address (unreachable network, silently-dropping firewall, wrong IP) — you wait the full timeout duration before giving up.

### Live Proof (see [connection_refused_vs_timeout_demo.py](connection_refused_vs_timeout_demo.py))

```
Connection REFUSED (nothing listening on that port): 0.000s -- instant, Errno 61
Connection TIMED OUT (unroutable address, 10.255.255.1): 3.001s -- waited full timeout
```

**Debugging table:**
| Symptom | Likely cause |
|---|---|
| Instant "Connection Refused" | Service down/crashed, wrong port, or firewall actively rejecting (sends RST) |
| Slow timeout | Wrong IP/hostname, broken network route, or firewall silently dropping packets |

Refused = application-level problem. Timeout = network/infra-level problem. Diagnose which one you're seeing before guessing at a fix.

---

## Topic 2. NAT + Forward Proxy vs Reverse Proxy

**NAT recap:** router rewrites private-IP traffic to its single public IP on the way out, tracks which internal device gets each response — lets private IP ranges be reused across every home/office network worldwide.

**Forward Proxy** = sits in front of the **client**. Target server never sees the real client, only the proxy's identity. Use cases: corporate content filtering, anonymity, shared caching.
```
You (client) --> Forward Proxy --> Internet (target server sees the PROXY, not you)
```

**Reverse Proxy** = sits in front of the **server**. Client never sees the real backend, only the proxy's identity.
```
Internet (client) --> Reverse Proxy --> Backend (hidden; client sees the PROXY, not the backend)
```
**Memory trick:** Forward proxy hides the client. Reverse proxy hides the server.

### Live Proof (see [reverse_proxy_forwarded_headers_demo.py](reverse_proxy_forwarded_headers_demo.py))

```
Backend listening on 127.0.0.1:63474 (never exposed to real client)
Reverse proxy listening on 127.0.0.1:63475 (client hits this)

[PROXY] real client connected from: 127.0.0.1:63476
[PROXY] injecting headers: X-Forwarded-For: 127.0.0.1, X-Forwarded-Proto: http, X-Forwarded-Host: api.example.com
[BACKEND] connection peer (proxy's IP, not real client): 127.0.0.1:63477
[BACKEND] X-Forwarded-For header: 127.0.0.1
```
Backend's TCP-level peer is the **proxy**, not the real client — the proxy must explicitly inject `X-Forwarded-For` so the backend can know the real client IP for logging/rate-limiting/geo-blocking.

**Senior gotcha:** if the backend trusts `X-Forwarded-For` blindly (not just from a trusted proxy hop), a client can spoof it — always validate via a trusted-proxy middleware (e.g. Starlette's `ProxyHeadersMiddleware`), not a raw header read.

---

## Topic 3. Load Balancer

**Analogy:** A restaurant manager assigning customers to waiters round-robin, while also tracking which waiters are "out sick" (health checks) and skipping them.

### Live Proof (see [load_balancer_round_robin_demo.py](load_balancer_round_robin_demo.py))

```
Health checks: Backend-1 HEALTHY, Backend-2 UNHEALTHY (removed from rotation), Backend-3 HEALTHY

Round-robin dispatch of 6 requests across the 2 healthy backends:
  1->Backend-1, 2->Backend-3, 3->Backend-1, 4->Backend-3, 5->Backend-1, 6->Backend-3
```
Confirms both round-robin distribution AND health-check-aware exclusion — the unhealthy backend received zero requests despite round-robin normally including it.

### Algorithms

| Algorithm | Decision basis | Best for |
|---|---|---|
| Round Robin | Strict rotation | Backends with roughly equal capacity |
| Least Connections | Fewest active connections right now | Variable-duration requests |
| Weighted Round Robin | Configured traffic share per backend | Heterogeneous hardware |
| IP Hash | Same client IP -> same backend | Sticky sessions |

**Senior gotcha — sticky sessions:** if a backend keeps session state in local memory (not a shared store), round-robin can route a user's next request to a different backend that doesn't know their session -> random "logged out" bugs. Fix: sticky sessions (IP hash) OR (preferred, more scalable) move session state to a shared store (Redis) so any backend can serve any request statelessly.

---

## Topic 4. CORS (Cross-Origin Resource Sharing)

**Analogy:** A building security guard who only checks outside visitors (browser JS), never internal staff (server-to-server calls) — CORS is enforced entirely by the **browser**, not the network or the server's own logic.

**Origin** = `scheme + host + port`, all three must match:
```
https://app.example.com  !=  https://api.example.com   (different host)
http://localhost:3000    !=  http://localhost:8000       (different port)
```

### Live Proof — Real Browser CORS Error, Then Real Fix (see [cors_demo_backend.py](cors_demo_backend.py) + [cors_demo_frontend.html](cors_demo_frontend.html))

**Backend WITHOUT CORS header** — real Chrome DevTools console error triggered in the actual browser pane:
```
Access to fetch at 'http://127.0.0.1:8091/data' from origin 'http://127.0.0.1:8092'
has been blocked by CORS policy: No 'Access-Control-Allow-Origin' header is present
on the requested resource.
```
Page showed: `FETCH FAILED: TypeError: Failed to fetch`

**Same backend restarted with `--with-cors` flag** (adds `Access-Control-Allow-Origin: http://127.0.0.1:8092`), page reloaded:
```
SUCCESS: {"message":"hello from API on port 8091"}
```
**Nothing else changed** — same data, same network path, only one response header added. Proves CORS is purely a browser-side gate on whether JS may *read* a response, not a network-level restriction.

### How it works (preflight)

```
1. Browser sends preflight: OPTIONS /users, Origin: https://app.example.com,
                             Access-Control-Request-Method: POST
2. Server responds: Access-Control-Allow-Origin / -Methods / -Headers
3. Only then does the browser send the actual request.
```

### Senior gotchas

- `allow_origins=["*"]` + `allow_credentials=True` together -> browsers **reject this combination outright**.
- Forgetting to let `OPTIONS` through a reverse proxy/API gateway -> preflight itself fails.
- A CORS error in the console almost always means the server responded fine — the browser is blocking JS from reading it. Check server logs before touching backend logic.
- **Server-to-server calls have zero CORS restriction** — it only exists for JS running on a webpage.

---

## Topic 5. Connection Pool Exhaustion

**Analogy:** A petrol pump with only 3 nozzles but 5 cars arrive — the first 3 get served immediately, the other 2 queue and wait for a nozzle to free up. No one is rejected (if there's a wait queue), but wait time increases.

### Live Proof (see [connection_pool_exhaustion_demo.py](connection_pool_exhaustion_demo.py))

```
Pool of 3 connections, 5 concurrent workers:
  worker 0,1,2 -> got a connection immediately (0.00s wait)
  worker 3,4   -> waited 1.34s for one to free up
```
Wait time for the queued workers (~1.34s) roughly matches how long the earlier workers held their connections (1.5s) — exactly the expected queuing behavior.

### Why this matters in production

- DB connection pool = 20, traffic spikes to 50 concurrent requests -> first 20 fast, remaining 30 **queue for a connection**, response time balloons — even though the DB itself isn't slow.
- Classic misleading symptom: "DB CPU is low, but the API is slow" — the bottleneck is the **application's own pool**, not the database.

**Fixes:**
- Tune pool size to real traffic patterns (too large can overwhelm the DB's own connection limit across all services combined)
- Set a connection-acquisition timeout so requests fail fast instead of hanging indefinitely
- Monitor pool utilization (active / idle / waiting count) as a first-class production metric
- Prefer async/non-blocking DB drivers (asyncpg, motor) — one connection can serve more concurrent in-flight queries than a sync blocking driver

---

## Round 3c Scorecard

Taught fresh with live proof for all 5 topics. Revisit before interviews:
- Connection Refused (app-level) vs Timeout (infra-level) — different debugging paths
- Forward proxy hides the client, reverse proxy hides the server; `X-Forwarded-For` trust boundary
- Sticky sessions vs stateless backend design tradeoff
- CORS is browser-enforced only — never a server or network restriction; server-to-server is exempt
- Connection pool exhaustion as a hidden cause of "slow API, but DB/CPU looks fine"
