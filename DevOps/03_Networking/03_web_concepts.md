# Web Infrastructure Concepts — Proxies, CDN, Load Balancing, API Gateway

**DevOps Track · Phase 3: Networking**

## Quick Concepts

- **Forward proxy** = sits in front of CLIENTS, hides/represents them to the outside world
- **Reverse proxy** = sits in front of SERVERS, hides/represents them from the outside world
- **CDN** = geographically distributed cache serving content close to the user
- **Load balancer** = distributes traffic across multiple backend instances
- **L4 vs L7** = load balancing decision made at the transport layer (IP/port) vs application layer (HTTP content)
- **API Gateway** = a managed entry point handling routing, auth, rate limiting, and more for a set of backend APIs/services
- **WebSocket** = a long-lived, full-duplex connection upgraded from an initial HTTP request — unlike ordinary HTTP, the connection stays open indefinitely for both sides to send messages anytime

---

## Why This Matters for Backend/DevOps Work

```
This is the vocabulary of "how traffic actually reaches your app" —
every production backend sits behind SOME combination of these. You
will configure Nginx as a reverse proxy, put an ALB in front of an
ECS service, and put CloudFront in front of static assets. Knowing
which piece does what is the difference between debugging in minutes
vs hours.
```

---

## Forward Proxy vs Reverse Proxy

| | Forward Proxy | Reverse Proxy |
|---|---|---|
| **Sits in front of** | Clients (users) | Servers (backends) |
| **Who knows it exists** | The client explicitly configures it | The client usually doesn't know — looks like the origin server |
| **Hides identity of** | The client, from the destination server | The backend server(s), from the client |
| **Typical use case** | Corporate internet filtering, bypassing geo-restrictions, client anonymization (VPN-like) | Load balancing, TLS termination, caching, routing to multiple backend services |
| **Real examples** | Squid proxy, a corporate outbound web proxy, a VPN | Nginx, HAProxy, AWS ALB, Cloudflare |

```
Forward proxy:
   [Many clients] --> [Forward Proxy] --> Internet --> [Destination server]
   The SERVER sees the proxy's IP, not the real client's.

Reverse proxy:
   Internet --> [Reverse Proxy] --> [Many backend servers]
   The CLIENT sees the proxy's IP/hostname, not the real backend's.
```

### Senior framing

```
"Which side configured it?" is the fastest way to tell them apart.
Client configured it → forward proxy. Server operator configured it
→ reverse proxy. As a backend/DevOps engineer, you'll work with
reverse proxies constantly (Nginx in front of your app) and forward
proxies occasionally (egress filtering in a locked-down VPC).
```

---

## CDN (Content Delivery Network)

```
A CDN is a global network of edge caching servers ("points of
presence" / PoPs) that store copies of your content physically close
to end users, so requests don't have to round-trip to your origin
server every time.

Client (Mumbai) --> nearest CDN edge (Mumbai PoP)
   ├── cache HIT  → served instantly from edge, origin never touched
   └── cache MISS → edge fetches from origin, caches it, serves it,
                     future requests from that region hit the cache

What you'd put behind a CDN:
   - Static assets (JS/CSS/images) — huge win, rarely change
   - API responses that are cacheable and not user-specific
   - Video/large file delivery

AWS equivalent: CloudFront
Others: Cloudflare, Akamai, Fastly
```

```
DevOps concerns with a CDN:
   - Cache invalidation ("cache busting") after a deploy — versioned
     filenames (app.a1b2c3.js) sidestep needing manual invalidation
   - Cache-Control / TTL headers control how long edges hold content
   - CDN also gives you free DDoS absorption at the edge (huge distributed
     capacity soaks up volumetric attacks before they reach origin)
```

---

## Load Balancer — L4 vs L7

| | Layer 4 (Transport) | Layer 7 (Application) |
|---|---|---|
| **Decides routing based on** | IP address + port only | Full HTTP request — path, headers, host, cookies |
| **Protocol awareness** | None — just forwards TCP/UDP packets | Understands HTTP, can inspect/modify requests |
| **Performance** | Faster, lower overhead | Slightly more overhead (has to parse the request) |
| **Can it do path-based routing?** (e.g. `/api` → service A, `/static` → service B) | No | Yes |
| **Can it terminate TLS?** | Passes through encrypted, or basic passthrough | Yes — commonly terminates TLS and re-encrypts or forwards plain internally |
| **AWS equivalent** | NLB (Network Load Balancer) | ALB (Application Load Balancer) |
| **Typical use case** | Raw TCP services, extreme low-latency needs, non-HTTP protocols | Web APIs, microservices needing content-based routing |

```
Rule of thumb:
   - "I just need to spread TCP connections across servers, fast" → L4 (NLB)
   - "I need to route /orders to service A and /users to service B,
      or inspect headers/cookies" → L7 (ALB)
```

---

## WebSockets Behind a Load Balancer — Why They're Different

Every load balancing concept above implicitly assumes short-lived HTTP request/response pairs. A WebSocket connection breaks that assumption on purpose — and that mismatch is a genuinely common real-world "why do connections keep dropping" incident.

### The Upgrade Handshake

```
Client                                    Server
  │  GET /chat HTTP/1.1                     │
  │  Upgrade: websocket                     │
  │  Connection: Upgrade                    │
  │  Sec-WebSocket-Key: dGhlIHNhbXBsZ...     │
  │ ────────────────────────────────────>   │
  │                                          │
  │  HTTP/1.1 101 Switching Protocols        │
  │  Upgrade: websocket                      │
  │  Connection: Upgrade                     │
  │ <────────────────────────────────────    │
  │                                          │
  │  <== now a full-duplex TCP connection,   │
  │      NOT ordinary HTTP request/response  │
  │      anymore, stays open indefinitely => │
```

The connection starts as a normal HTTP request, then the `101 Switching Protocols` response upgrades that SAME TCP connection to a raw, bidirectional pipe — it never closes and reopens per message the way HTTP does.

### Why This Breaks Naive Load Balancer Assumptions

```
Ordinary HTTP behind a load balancer: every request can, in principle,
land on a DIFFERENT backend instance — statelessness is what makes
this fine, and it's exactly the assumption the whole rest of this
file (and the "session/state handled externally" rule from Phase 20)
is built on.

A WebSocket connection is the OPPOSITE — once established, it's
pinned to ONE specific backend instance for its entire lifetime
(that instance holds the actual open socket and any per-connection
state, like "which chat room this connection is subscribed to").
```

```
Consequences for real infrastructure:

1. Idle timeout — a plain HTTP-tuned load balancer often has a short
   idle timeout (ALB default: 60s). A WebSocket can sit silently open
   for MINUTES between messages — the LB silently kills it as "idle,"
   the app sees a mysterious disconnect with no error on either side.
   Fix: raise the LB's idle timeout specifically for the WebSocket
   route, or have the app send periodic ping/pong keepalive frames.

2. Load balancing algorithm — round-robin or least-connections is
   fine for short HTTP requests, but for WebSockets it determines
   which backend gets the LONG-LIVED connection, which then STAYS
   there. An LB that keeps sending new WebSocket connections to an
   already-overloaded instance (because it doesn't know the OLD
   connections are still open and consuming resources there) can
   create lopsided load that a simple health check won't catch.

3. Deployment/rolling updates — the zero-downtime checklist from
   Phase 20 (drain connections before killing a pod/instance) matters
   MORE here: a rolling update that just SIGTERMs an instance instantly
   drops every open WebSocket connection on it at once, with no
   graceful reconnect signal to affected clients unless the app
   explicitly sends one before shutting down.

4. Horizontal scaling needs a backplane — if a message needs to reach
   a user whose WebSocket connection is pinned to a DIFFERENT backend
   instance than the one that received the triggering event, that
   instance can't just "send it" — the instances need a shared pub/sub
   layer (Redis Pub/Sub, a message queue) to relay the message to
   whichever instance actually holds that user's connection.
```

```
AWS specifics: an ALB (L7) supports WebSocket natively — it detects
the Upgrade header and holds the connection open for its configured
idle timeout, same "sticky to one target" behavior described above.
An NLB (L4) works too, since it's not HTTP-aware at all and simply
forwards the raw TCP stream — connection pinning happens naturally
because L4 doesn't do per-request routing in the first place.
```

**Senior framing:** WebSockets aren't just "HTTP but it stays open" from an infrastructure standpoint — they invalidate the statelessness assumption almost everything else in this phase relies on, which is why idle timeouts, LB algorithm choice, graceful shutdown, and horizontal scaling all need separate, deliberate handling for them.

---

## API Gateway

```
An API Gateway is a managed reverse proxy specialized for APIs — it
sits in front of one or many backend services and typically handles:

   - Request routing to the correct backend/microservice
   - Authentication / API key validation
   - Rate limiting / throttling per client
   - Request/response transformation
   - Centralized logging and metrics for all API traffic
   - Sometimes: caching, request validation, canary/version routing

Client --> API Gateway --> [routes to] --> Orders Service
                        --> [routes to] --> Users Service
                        --> [routes to] --> Payments Service

AWS equivalent: Amazon API Gateway
Others: Kong, Nginx (configured as a gateway), Apigee
```

```
API Gateway vs plain reverse proxy (Nginx):
   A reverse proxy CAN do some of this (routing, TLS termination),
   but "API Gateway" implies a higher-level feature set purpose-built
   for API traffic: per-client rate limiting, API key/auth management,
   usage plans, and often a management UI/API for defining routes
   without touching config files directly.
```

---

## Tying It Together — A Realistic Request Path

```
User's browser
    │
    ▼
CDN (CloudFront) ──── cache hit? serve static asset directly, done.
    │ cache miss / dynamic request
    ▼
API Gateway / L7 Load Balancer (ALB) ──── TLS termination, auth check,
    │                                     rate limiting, path routing
    ▼
Reverse Proxy (Nginx, sometimes same as above) ──── routes to the
    │                                                correct upstream
    ▼
Backend app servers (multiple instances, behind the LB for HA)
    │
    ▼
Database / cache layer
```

---

## Senior Tip

```
1. In interviews, always anchor the L4/L7 answer to a concrete example:
   "NLB for a raw TCP game server needing ultra-low latency, ALB for
   an HTTP API that needs to route /v1 and /v2 differently."
2. CDN + versioned asset filenames > manual cache invalidation —
   design for it from day one, don't bolt it on later.
3. A reverse proxy, a load balancer, and an API gateway can all be the
   SAME physical component (e.g. Nginx configured to do all three) —
   the terms describe roles/responsibilities, not always separate boxes.
4. Forward proxies are rare in typical backend work but show up in
   locked-down corporate/VPC egress setups — know the concept even if
   you rarely configure one yourself.
```

## Interview Angle

**Q: Explain reverse proxy vs forward proxy with a one-line test to tell them apart.**
Ask "who configured it, the client or the server operator?" A forward proxy is configured by/for the client to reach the outside world (hides the client). A reverse proxy is configured by the server operator to sit in front of backends (hides the backend). Nginx in front of your API is a reverse proxy; a corporate outbound web filter is a forward proxy.

**Q: When would you choose an NLB over an ALB?**
When you need raw TCP/UDP forwarding with minimal latency and don't need HTTP-aware routing — e.g. a non-HTTP protocol, extremely high throughput requirements, or when you need a static IP for the load balancer (NLBs support Elastic IPs per AZ, ALBs don't).

**Q: What does an API Gateway give you that a plain Nginx reverse proxy doesn't, out of the box?**
Built-in per-client rate limiting/throttling, API key/usage-plan management, and often request/response transformation and usage analytics — without you hand-rolling that logic into proxy config. Nginx CAN be configured to approximate parts of this (rate-limiting modules exist), but "API Gateway" as a term implies that feature set is first-class and managed.

**Q: How does a CDN help during a traffic spike or DDoS attempt, beyond just performance?**
The CDN's distributed edge capacity absorbs and serves cached content close to users without hitting your origin at all — for cacheable content, a volumetric spike largely never reaches your actual infrastructure, which is why CDNs are also a standard first line of DDoS defense.

**Q: Users report their WebSocket connections randomly drop after a minute or two of inactivity, with no error on either side. What's the likely cause?**
The load balancer's idle timeout is shorter than the gap between WebSocket messages — a default ALB idle timeout of 60s will silently close a connection that's been quiet for a bit longer than that, and neither the client nor the server logs an "error" because from the LB's point of view it's just cleaning up an idle connection, not failing anything. Fix: raise the idle timeout on the WebSocket route specifically, and/or have the application send periodic ping/pong keepalive frames so the connection never looks idle to the LB.

---

## Related

- [`02_protocols.md`](02_protocols.md) — the underlying HTTP/TCP mechanics WebSockets upgrade from
- [`../07_Cloud_AWS/03_networking_dns_lb.md`](../07_Cloud_AWS/03_networking_dns_lb.md) — ALB/NLB configuration specifics, including WebSocket support
- [`../20_Best_Practices/01_deployment_dr_incident_cost.md`](../20_Best_Practices/01_deployment_dr_incident_cost.md) — the zero-downtime/connection-draining checklist that matters even more for long-lived WebSocket connections
- [`../17_Caching/01_caching.md`](../17_Caching/01_caching.md) — Redis Pub/Sub as the backplane pattern for relaying messages across WebSocket-holding instances
