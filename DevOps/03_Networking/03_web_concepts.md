# Web Infrastructure Concepts — Proxies, CDN, Load Balancing, API Gateway

**DevOps Track · Phase 3: Networking**

## Quick Concepts

| Concept | One-line definition |
|---------------------|----------------------------------------------------------------------|
| **Forward proxy** | Sits in front of CLIENTS — hides/represents them to the outside world |
| **Reverse proxy** | Sits in front of SERVERS — hides/represents backends from clients |
| **CDN** | Geographically distributed cache serving content close to the user |
| **Load balancer** | Distributes traffic across multiple backend instances |
| **L4 vs L7** | Routing decision at transport layer (IP/port) vs application layer (HTTP content) |
| **API Gateway** | Managed entry point handling routing, auth, rate limiting for backend APIs |
| **WebSocket** | Long-lived full-duplex connection upgraded from HTTP — stays open indefinitely |

---

## Why This Matters for Backend/DevOps Work

```
This is the vocabulary of "how traffic actually reaches your app."
Every production backend sits behind SOME combination of these.
You will configure Nginx as a reverse proxy, put an ALB in front of
an ECS service, and put CloudFront in front of static assets.
Knowing which piece does what is the difference between debugging
in minutes vs hours.
```

---

## Forward Proxy vs Reverse Proxy

| | Forward Proxy | Reverse Proxy |
|--|--------------|--------------|
| **Sits in front of** | Clients (users) | Servers (backends) |
| **Who configured it** | The client explicitly | The server operator |
| **Hides identity of** | The client, from the destination | The backend server(s), from the client |
| **Typical use** | Corporate filtering, egress control, debugging | Load balancing, TLS termination, routing |
| **Real examples** | Squid, mitmproxy, corporate outbound filter | Nginx, HAProxy, ALB, Cloudflare |

```
Forward proxy:
   [Many clients] ──▶ [Forward Proxy] ──▶ Internet ──▶ [Destination]
   The destination sees the PROXY'S IP, not the real client IP.

Reverse proxy:
   Internet ──▶ [Reverse Proxy] ──▶ [Many backend servers]
   The client sees the PROXY'S IP/hostname, not the real backend IP.

One-line test to tell them apart:
  "Who configured it — the client or the server operator?"
  Client configured it → forward proxy
  Server operator configured it → reverse proxy
```

### Forward Proxy — How It Actually Works

```
The client must be explicitly configured to use a forward proxy:
  export http_proxy=http://proxy.corp.com:3128
  export https_proxy=http://proxy.corp.com:3128

For HTTP:
  Client sends full URL to proxy:  GET http://example.com/page HTTP/1.1
  Proxy makes the request, returns the response.
  Destination sees: proxy's IP as source.

For HTTPS (CONNECT method):
  Client sends:  CONNECT example.com:443 HTTP/1.1
  Proxy opens a TCP tunnel to example.com:443, replies: 200 Connection Established
  Client does TLS handshake directly through the tunnel.
  Proxy CAN'T see the encrypted content — only the destination hostname.

Use cases:
  1. Corporate web filtering: all outbound traffic through a proxy
     that blocks distracting sites and logs requests for compliance.
  2. Egress control in a locked-down VPC: private subnets only reach
     the internet via a Squid proxy that whitelists allowed destinations.
     Without an allowlist, a compromised instance can exfiltrate data to
     any endpoint — the proxy is the chokepoint.
  3. Developer debugging: mitmproxy, Charles Proxy — intercept and
     inspect HTTPS traffic from mobile apps by being the forward proxy
     with a trusted self-signed cert.
```

### Reverse Proxy — What It Does Before Your App Sees a Request

```
Benefits of running Nginx in front of your app:

1. TLS termination:
   Nginx handles cert management, TLS handshake, and cipher negotiation.
   Your backend app receives plain HTTP on an internal port.
   The app never needs to know about certs.

2. One external IP → many internal services:
   api.example.com/api/orders  → orders service :8001
   api.example.com/api/users   → users service  :8002
   api.example.com/static/     → served directly from disk

3. X-Forwarded-For — preserving real client IPs:
   Without this header: backend sees src IP = 127.0.0.1 (Nginx itself)
   With this header:    backend reads X-Real-IP: 203.0.113.45
   Your logs, rate limits, and geo-blocking all need the real client IP.

4. Buffering slow clients:
   Nginx buffers the entire request from slow clients before forwarding.
   Your Python/Node backend never blocks waiting for a slow upload —
   Nginx handles the slow client, forwards a complete request instantly.

5. Static file serving:
   Nginx serves /static/ directly from disk (kernel sendfile — zero copy).
   These requests never hit your app process at all.
```

---

## CDN (Content Delivery Network)

### How CDN Caching Actually Works

```
A CDN is a global network of edge servers ("Points of Presence" / PoPs).
Edges cache copies of your content so requests don't travel to your origin.

User in Mumbai → nearest CDN edge (Mumbai PoP):

  Cache HIT:
    Edge has a fresh copy → serves it in 5–20ms
    Origin server never receives the request

  Cache MISS:
    Edge fetches from origin (e.g. ALB in us-east-1) → ~200ms round trip
    Edge caches the response according to Cache-Control headers
    All subsequent Mumbai requests → cache hit

What to put behind a CDN:
  ✓ Static assets (JS, CSS, images, fonts) — cache for 1 year
  ✓ API responses that are not user-specific (product catalogue, public config)
  ✓ Video / large file delivery
  ✗ User-specific responses (shopping cart, account data) — never cache
  ✗ Auth tokens, session cookies — never cache
```

### Cache-Control Headers — The Full Picture

```
Cache-Control: public, max-age=31536000, immutable
  public     = CDN edges may cache this (not just the browser)
  max-age    = cache for 1 year (seconds)
  immutable  = content will NEVER change at this URL — skip revalidation
  Use for:   versioned static assets  (app.a1b2c3d4.js)

Cache-Control: no-store
  Never cache anywhere — not in CDN, not in browser
  Use for:   auth tokens, user-specific API responses

Cache-Control: public, max-age=300, stale-while-revalidate=60
  Serve cached for 5 minutes.
  After 5 minutes: still serve stale while triggering a background refresh.
  User sees no latency spike while the cache refreshes.
  Use for:   slowly changing API responses (product listings, public data)

Cache-Control: private, max-age=0
  Browser may cache (for back button), but CDN edges must not.
  Use for:   pages with user-specific content (logged-in dashboard)
```

### Cache Invalidation Strategies

```
1. Versioned filenames (best practice — no invalidation needed):
   app.js             → bad: same URL, CDN serves stale content
   app.a1b2c3d4.js    → good: new hash = new URL = CDN fetches fresh

   In your Webpack/Vite/build config:
   output: { filename: '[name].[contenthash].js' }

2. Manual CDN invalidation:
   CloudFront: CreateInvalidation API call → takes ~30s to propagate
   Free for first 1000 paths/month, then charged.
   Acceptable for emergency hotfixes, not ideal for routine deploys.

3. Short TTL during deploys:
   Normally: max-age=3600 (1 hour)
   During deploy: reduce to max-age=60 temporarily
   After deploy: raise TTL back
   Tradeoff: more origin requests during the low-TTL window

Rule: versioned filenames + long TTL > short TTL + manual invalidation.
Design for immutable assets from day one.
```

### CDN as DDoS Absorption

```
Without CDN:
  100,000 req/s of attack traffic hits your origin directly.
  EC2s saturate, DB connections exhaust, site goes down.

With CDN (high cache hit rate):
  99,000 req/s served from CDN edges — origin never sees them.
  1,000 req/s reach origin — manageable.
  CDN adds: rate limiting by IP at the edge (WAF rules).
  Volumetric DDoS absorbed by CDN's distributed capacity (petabits/s).

This is why CloudFront + AWS WAF is the standard first-line DDoS defence.
The attack traffic never reaches your VPC — it dies at the edge.
```

---

## Load Balancer — L4 vs L7

| | Layer 4 (Transport) | Layer 7 (Application) |
|--|--------------------|-----------------------|
| **Routes based on** | IP address + port only | Full HTTP: path, headers, host, cookies |
| **Protocol awareness** | None — forwards raw TCP/UDP | Understands HTTP/gRPC/WebSocket |
| **Performance** | Faster, minimal overhead | Slightly more overhead (parses HTTP) |
| **Path-based routing** | No | Yes — `/api/` → service A, `/static/` → service B |
| **TLS termination** | Passthrough or basic | Yes — terminates and re-encrypts internally |
| **AWS equivalent** | NLB (Network Load Balancer) | ALB (Application Load Balancer) |
| **Use when** | Raw TCP, extreme low latency, non-HTTP | Web APIs, microservices, HTTP routing |

```
Rule of thumb:
  "I need to spread raw TCP connections fast with no HTTP awareness" → NLB
  "I need to route /orders to one service and /users to another"     → ALB
  "I need to inspect headers, cookies, or terminate TLS"              → ALB
  "I need a static IP for the load balancer" (NLBs support Elastic IPs) → NLB
```

### Load Balancing Algorithms

```
Round Robin:
  Request 1 → Server A, Request 2 → Server B, Request 3 → Server C, repeat
  Simple equal distribution.
  Problem: if requests vary in processing time, one server gets overloaded
           while others sit idle (500ms requests vs 5ms requests).
  Use when: request processing time is roughly uniform.

Least Connections:
  Always forward to the backend with the fewest active connections.
  Better for variable request durations.
  ALB default algorithm (weighted variant).
  Use when: request durations vary significantly (mixed fast/slow endpoints).

Weighted Round Robin:
  Server A gets 70% of requests, Server B gets 30%.
  Use when: backends have different capacities (different instance types).
  Canary deployments: 5% weight to new version, 95% to old version.

IP Hash (Sticky by IP):
  Same client IP always goes to same backend.
  Problem: a corporate proxy sends 30% of traffic from one IP
           → one backend gets overloaded.
  Use only when you can't use cookie-based stickiness.

Cookie-based Session Stickiness (ALB: AWSALB cookie):
  ALB sets a cookie on first response.
  Subsequent requests with that cookie go to the same target.
  Use when: app stores session state in memory (avoid if possible —
            fix the statefulness instead, use Redis for sessions).
  Required for: WebSocket connections (by design).
```

### Health Checks — The Real Mechanics

```
An unhealthy backend silently breaks user requests without health checks.

TCP health check (NLB default):
  "Can I open a TCP connection to this port?"
  ✓ Verifies: process is running and listening
  ✗ Does NOT verify: app logic works, DB connection alive

HTTP health check (ALB default):
  "Do I get HTTP 200 from GET /health?"
  ✓ Verifies: process running + app logic + DB accessible

A GOOD /health endpoint:
  @app.get("/health")
  def health():
      db.execute("SELECT 1")   # verify DB is reachable
      cache.ping()              # verify Redis is reachable
      return {"status": "ok"}
  → Returns 500 if any critical dependency is down
  → ALB stops routing traffic to this backend until it recovers

A BAD /health endpoint:
  @app.get("/health")
  def health():
      return {"status": "ok"}   # always 200 even if DB is dead
  → ALB keeps routing traffic to a broken backend

ALB health check settings:
  Interval            30s (how often to check)
  Healthy threshold   2 (2 consecutive 200s → healthy)
  Unhealthy threshold 2 (2 consecutive failures → removed from rotation)
  Timeout             5s (how long to wait for response)
```

### Connection Draining (Deregistration Delay)

```
Without connection draining:
  Rolling deploy removes instance from ALB immediately.
  All in-flight requests to that instance get dropped → 502 errors.
  WebSocket connections severed with no warning.

With connection draining (ALB default: 300s):
  1. ALB stops sending NEW requests to the deregistering instance.
  2. Allows EXISTING in-flight requests to complete.
  3. After the drain timeout: forcibly closes remaining connections.
  4. Instance safely terminates.

In your deploy pipeline:
  1. Deregister instance from target group → new traffic stops
  2. Wait for drain (or poll active connections = 0)
  3. Deploy new code
  4. Re-register instance → ALB resumes routing

For ECS: set deregistration_delay on the target group.
For Kubernetes:
  preStop:
    exec:
      command: ["sleep", "15"]   # give LB time to stop routing
  terminationGracePeriodSeconds: 60
```

---

## WebSockets Behind a Load Balancer

### The Upgrade Handshake

```
Client                                    Server
  │  GET /chat HTTP/1.1                     │
  │  Upgrade: websocket                     │
  │  Connection: Upgrade                    │
  │  Sec-WebSocket-Key: dGhlIHNhbXBsZ...    │
  │ ──────────────────────────────────────▶ │
  │                                          │
  │  HTTP/1.1 101 Switching Protocols        │
  │  Upgrade: websocket                      │
  │  Connection: Upgrade                     │
  │ ◀────────────────────────────────────── │
  │                                          │
  │  ══ full-duplex TCP pipe from here on ══ │
  │  ══ NOT ordinary HTTP request/response ══│
  │  ══ connection stays open indefinitely ══│
```

### Why WebSockets Break Naive Load Balancer Assumptions

```
Ordinary HTTP: every request can land on a DIFFERENT backend.
Statelessness makes this fine — the whole horizontal scaling model
depends on it.

WebSocket: once established, PINNED to ONE backend for its entire
lifetime. That backend holds the actual socket + per-connection state
("which chat room is this connection subscribed to?").

Consequences:

1. Idle timeout (most common production issue):
   ALB default idle timeout = 60 seconds.
   A WebSocket sitting silently open between messages gets killed
   silently — no error on either side. Client just notices it disconnected.
   Fix: raise idle timeout on the WebSocket route to match your max
   message gap, AND have the app send periodic ping/pong frames
   (WebSocket ping/pong keeps the connection "active" from the LB's view).

2. Load skew:
   Round-robin sends NEW WebSocket connections evenly, but OLD connections
   stay pinned. An overloaded instance keeps its 1000 existing WebSocket
   connections while the LB sends new ones elsewhere.
   Monitoring: track active connections per backend, not just RPS.

3. Rolling deploys:
   SIGTERM to an instance drops ALL its WebSocket connections instantly.
   Users see disconnects with no graceful reconnect signal.
   Fix: before SIGTERM, the app should send WebSocket close frames with
   a reconnect hint, and the client should handle reconnect on close.

4. Horizontal scaling needs a pub/sub backplane:
   User A's connection is on Backend 1.
   User B's connection is on Backend 2.
   User A sends a message to User B.
   The message arrives at Backend 1 — but User B's socket is on Backend 2.
   Backend 1 can't send directly.
   Fix: Redis Pub/Sub — Backend 1 publishes to Redis, Backend 2 subscribes
   and delivers to User B's socket.
   Without this: horizontal scaling is impossible for real-time features.
```

```
AWS specifics:
  ALB supports WebSocket natively — detects the Upgrade header,
  holds the connection open, routes to one target for the connection lifetime.
  NLB also works — L4 TCP passthrough naturally stays pinned to one target.
```

---

## API Gateway

### What It Does Beyond a Plain Reverse Proxy

```
A plain Nginx reverse proxy: routes requests to backends.

An API Gateway does all that PLUS:
  - Authentication / JWT validation (before the request reaches any backend)
  - API key management (issue, revoke, track usage per key)
  - Rate limiting / throttling per client/API key/endpoint
  - Request/response transformation (header injection, path rewriting)
  - Centralized logging and metrics for all API traffic
  - Canary routing / version routing (/v1, /v2, /v3)
  - Request validation (schema checks before hitting the backend)
```

### Rate Limiting — Token Bucket Algorithm

```
Each client gets a "bucket" with a token capacity:
  Capacity:    1000 tokens
  Refill rate: 100 tokens/second

Each request consumes 1 token.
When bucket is empty → 429 Too Many Requests.
Bucket refills at 100 tokens/second even while empty.

Why token bucket is better than fixed window:
  Fixed window: 1000 requests/minute
    Problem: 1000 requests in the last second of minute 1, then 1000 in the
    first second of minute 2 = 2000 requests in 2 seconds.
    Fixed window allows burst at the boundary.

  Token bucket: smooth rate + controlled burst.
  A client can use their full 1000-token burst, then is limited to 100 req/s.
  No boundary artifact. More accurate rate control.

In AWS API Gateway:
  throttle: rateLimit: 100   # requests per second (token bucket refill rate)
            burstLimit: 200  # max burst size (token bucket capacity)
  Returns 429 with Retry-After header when exceeded.
```

### Auth at the Gateway Layer

```
JWT validation:
  Gateway validates token signature + expiry before routing.
  Backend receives pre-validated claims in headers (X-User-ID, X-Role).
  Backend doesn't need the JWT secret — gateway is the trust boundary.

API key:
  Gateway looks up the key in a DB/config.
  Adds customer context headers (X-Customer-ID, X-Plan) to the request.
  Backend trusts these headers — no key lookup needed in app code.

OAuth2 / OIDC:
  Gateway handles the token exchange flow.
  Can also do token introspection (validate against auth server on each request).

mTLS (mutual TLS):
  Both client and gateway present certificates.
  Used for service-to-service auth in zero-trust architectures.

AWS API Gateway options:
  IAM auth:   AWS Signature v4 — for internal AWS services/Lambda
  Cognito:    JWT from Cognito user pool
  Lambda auth: custom authorizer function — run any auth logic
  API keys:   per-usage-plan throttling and quotas
```

### AWS API Gateway: REST API vs HTTP API

```
HTTP API (newer):
  Cheaper (~$1/million requests vs ~$3.5/million)
  Lower latency (~10ms added vs ~60ms)
  Fewer features: no usage plans, no per-method throttling, no WAF
  Use for: simple HTTP proxy to Lambda or HTTP backends

REST API (older, full-featured):
  Per-method throttling, usage plans, API keys
  WAF integration
  Request/response transformation (Velocity templates)
  SDK generation
  Use for: external-facing APIs needing full rate limiting/key management

WebSocket API:
  Manages WebSocket connections and routes messages to Lambda
  Great for: serverless real-time features (chat, notifications)
```

---

## A Realistic Request Path — With Latency Numbers

```
User in Mumbai → api.example.com/api/users/42 (dynamic, authenticated)

Step 1: DNS resolution
  OS cache hit:        < 1ms
  Recursive DNS:       ~5ms (cached at ISP resolver)
  Cold DNS lookup:     ~100ms (root → TLD → authoritative)

Step 2: CDN edge (Mumbai PoP)
  Cache HIT  (static assets):  5–20ms → served, done
  Cache MISS (dynamic API):    continue to step 3

Step 3: CDN → ALB (us-east-1)
  Mumbai → us-east-1 RTT:  ~180ms
  TCP handshake:            ~180ms (1 RTT)
  TLS 1.3 handshake:        ~180ms (1 RTT)

Step 4: ALB processing
  Rule matching + target selection:  < 1ms
  Security group check:              < 1ms

Step 5: Backend app (private subnet, ECS task)
  App logic:                  10–50ms
  DB query (indexed):         5–20ms
  DB query (table scan/lock): 100ms–10s → this is your p99 problem

Step 6: Response path (reverse of above)

Total latency:
  Cache HIT (static):    5–20ms    ← CDN served it
  Cache MISS (dynamic):  ~600ms    ← cross-continental round trip
  Cached on fast region: ~30ms     ← if your users are near your AWS region

Why this matters:
  A 200ms API = feels instant.
  A 600ms API = feels sluggish.
  A 2000ms API = users abandon.
  CDN + caching collapses the geography tax from 600ms to 20ms.
```

---

## Nginx as Reverse Proxy — Full Production Config

```nginx
# /etc/nginx/conf.d/myapp.conf

upstream myapp_backend {
    least_conn;                         # send to backend with fewest connections
    server 10.0.10.5:8000 weight=2;     # gets 2x traffic (more powerful instance)
    server 10.0.10.6:8000 weight=1;
    keepalive 32;                        # maintain 32 idle connections to backends
                                         # avoids TCP handshake on every request
}

server {
    listen 443 ssl http2;
    server_name api.example.com;

    ssl_certificate     /etc/letsencrypt/live/api.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/api.example.com/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;

    # Pass real client IP to backend (REQUIRED for accurate logs/rate limiting)
    proxy_set_header X-Real-IP          $remote_addr;
    proxy_set_header X-Forwarded-For    $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto  $scheme;
    proxy_set_header Host               $host;

    # Timeouts
    proxy_connect_timeout  5s;    # time to establish connection to backend
    proxy_send_timeout    60s;    # time between writes to backend
    proxy_read_timeout    60s;    # time waiting for backend response

    # Regular HTTP API
    location /api/ {
        proxy_pass http://myapp_backend;
    }

    # WebSocket — must set Upgrade headers and long read timeout
    location /ws/ {
        proxy_pass http://myapp_backend;
        proxy_http_version 1.1;
        proxy_set_header Upgrade    $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_read_timeout 3600s;   # WebSocket connections can be open for hours
    }

    # Static files served directly from disk — never hits app process
    location /static/ {
        alias /opt/myapp/static/;
        expires 1y;
        add_header Cache-Control "public, immutable";
        gzip_static on;             # serve pre-compressed .gz files if they exist
    }
}

# HTTP → HTTPS redirect
server {
    listen 80;
    server_name api.example.com;
    return 301 https://$host$request_uri;
}
```

---

## Senior Tips

```
1. "Which side configured it?" instantly identifies forward vs reverse proxy.
   Client configured it = forward proxy.
   Server operator configured it = reverse proxy.

2. CDN + versioned asset filenames beats manual cache invalidation.
   app.[contenthash].js with max-age=31536000 means you never
   invalidate cache — the URL changes with the content.

3. A reverse proxy, load balancer, and API gateway can be the SAME
   physical component (Nginx configured to do all three) — the terms
   describe ROLES, not separate boxes.

4. Your /health endpoint must check ALL critical dependencies.
   A /health that always returns 200 is worse than no health check —
   it tells the ALB a broken backend is healthy.

5. WebSocket idle timeout is the most common "mysterious disconnect" bug.
   Default ALB idle timeout = 60s. Raise it for WebSocket routes.
   Always implement client-side reconnect logic — WebSocket disconnects
   are inevitable in production.

6. X-Forwarded-For can be spoofed by clients if not validated.
   Trust it ONLY from known proxy IPs (your own Nginx, your ALB).
   In AWS: ALB always overwrites X-Forwarded-For, so it's safe.
   Behind Nginx: set real_ip_header and trusted_proxies in config.
```

---

## Interview Angle

**Q: Reverse proxy vs forward proxy — one-line test to tell them apart.**

```
"Who configured it?"
  Client configured it → forward proxy (hides the client)
  Server operator configured it → reverse proxy (hides the backend)

Forward proxy: Squid, corporate outbound filter, mitmproxy
Reverse proxy: Nginx, HAProxy, ALB, Cloudflare
```

**Q: When would you choose NLB over ALB?**

```
NLB when:
  - Non-HTTP protocol (raw TCP/UDP — game servers, custom protocols)
  - You need a static Elastic IP per AZ (NLB supports it, ALB doesn't)
  - Extreme low latency (<1ms overhead vs ALB's ~1–5ms)
  - Very high throughput (millions of connections/sec)

ALB when:
  - Path-based routing (/api vs /static vs /admin)
  - Host-based routing (api.example.com vs app.example.com)
  - WAF integration, header inspection, TLS termination
  - HTTP → HTTPS redirect
  - WebSocket support (ALB handles the Upgrade header)
```

**Q: What does an API Gateway give you that plain Nginx doesn't?**

```
First-class features out of the box:
  - Per-client rate limiting by API key (token bucket, burst limits)
  - Usage plans (client A gets 1000 req/day, client B gets 10000/day)
  - API key issuance, rotation, revocation — managed, with a UI
  - Request/response transformation without Lua/JS modules
  - Built-in auth: Cognito, Lambda authorizer, IAM

Nginx CAN approximate these with modules (rate_limit, auth_request,
Lua scripts), but you're hand-rolling what API Gateway gives managed.
The distinction: API Gateway treats these as first-class features;
Nginx treats them as configuration challenges.
```

**Q: How does a CDN help during a DDoS attack?**

```
For cacheable content:
  Attack traffic hits CDN edges, which have petabits/sec of capacity.
  The edges serve cached responses — origin never receives the traffic.
  A volumetric DDoS effectively never reaches your infrastructure.

For dynamic content:
  CDN WAF rules rate-limit attack IPs at the edge.
  Only legitimate-looking traffic passes through to origin.

The key: CDN absorbs the attack at the edge, closest to where it
originates, before it traverses expensive internet bandwidth to your VPC.
```

**Q: WebSocket connections drop after 60s of inactivity — what's the cause and fix?**

```
Cause: ALB's default idle timeout is 60 seconds. A WebSocket with no
messages for >60s looks "idle" to the LB — it closes the TCP connection
silently. Neither the client nor the server logs an error.

Fix 1 (LB config): Raise the idle timeout on the ALB for the WebSocket
target group to match your max expected message gap (e.g. 3600s).

Fix 2 (application): Implement WebSocket ping/pong keepalive frames.
Every 30 seconds, the server sends a ping frame — client replies with
pong. The LB sees traffic and resets its idle timer.
Client also sees pong → knows connection is alive.

Both together: raise timeout AND implement keepalive. LB config alone
fails if timeout must be very long; keepalive alone fails if someone
forgets to update the LB config.
```

**Q: How do you scale WebSocket horizontally without losing messages?**

```
Problem: User A's socket is on Backend 1. User B's socket is on Backend 2.
User A sends a message to User B. Message arrives at Backend 1.
Backend 1 can't reach User B's socket directly.

Solution: Redis Pub/Sub backplane.
  Backend 1: publish message to Redis channel "user:B"
  Backend 2: subscribed to "user:B" channel, receives the message
  Backend 2: sends the message to User B's open socket

Each backend subscribes to channels for all connected users.
When a user connects → subscribe to their channel.
When a user disconnects → unsubscribe.

This is the standard pattern for: chat apps, collaborative editing,
live notifications, real-time dashboards.
```

---

## Related

- [`02_protocols.md`](02_protocols.md) — HTTP mechanics, TCP vs UDP, TLS handshake
- [`../07_Cloud_AWS/03_networking_dns_lb.md`](../07_Cloud_AWS/03_networking_dns_lb.md) — ALB/NLB config specifics, Security Groups
- [`../20_Best_Practices/01_deployment_dr_incident_cost.md`](../20_Best_Practices/01_deployment_dr_incident_cost.md) — connection draining in rolling deploys
- [`../17_Caching/01_caching.md`](../17_Caching/01_caching.md) — Redis Pub/Sub as the WebSocket backplane pattern