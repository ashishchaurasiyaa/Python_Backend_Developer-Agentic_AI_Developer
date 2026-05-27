# 05 — Load Balancing

## What a load balancer does

A load balancer (LB) is a reverse proxy that distributes incoming requests across multiple backend servers. It provides:

1. **Horizontal scaling** — fan out traffic to N servers
2. **High availability** — route around failed backends
3. **Performance** — minimize latency by picking the right server
4. **Security / TLS termination** — single TLS endpoint, simpler cert management
5. **Observability** — centralized request logging and metrics

Without an LB, you can't scale beyond one machine for a public-facing service.

## L4 (Transport) vs L7 (Application)

| | **L4** | **L7** |
|---|--------|--------|
| **Layer** | TCP/UDP | HTTP/HTTPS, gRPC, WebSocket |
| **Inspection** | IP + port only | Headers, path, cookies, body |
| **Decisions** | Connection routing | Content-aware routing |
| **Performance** | Very fast (no parse) | Slower (parses each request) |
| **TLS** | Pass-through or terminate | Almost always terminates |
| **Examples** | AWS NLB, IPVS, HAProxy (L4 mode), F5 | AWS ALB, nginx, Envoy, HAProxy (L7 mode), Traefik |
| **Use** | Generic TCP services, very high throughput | Modern HTTP APIs, microservices |

**Modern default:** L7 for web/API traffic, L4 in front for ultra-high QPS or non-HTTP protocols.

## Load balancing algorithms

| Algorithm | How | When to use |
|-----------|-----|-------------|
| **Round Robin** | Cycle through servers in order | Uniform servers, similar request cost |
| **Weighted Round Robin** | Round robin with per-server weights | Heterogeneous server capacity |
| **Least Connections** | Send to server with fewest active conns | Variable request durations |
| **Weighted Least Connections** | Same, weighted | Mixed capacity + variable durations |
| **Least Response Time** | Combine connections + recent latency | Best general default if available |
| **IP Hash** | hash(client_ip) % N → server | Stateful (sticky) sessions without cookies |
| **URL Hash** | hash(path) % N → server | Cache locality (same URL → same cache) |
| **Consistent Hashing** | Map keys + servers to a ring | Cache-friendly + minimal churn on scale |
| **Random** | Pick random server | Surprisingly competitive; easy to reason |
| **Power of Two Choices** | Pick 2 random, send to less loaded | Near-optimal with O(1) work |

**Power of two choices** is a great default — randomized, fair, simple, and provably close to "least connections" in performance.

## Consistent hashing (deep dive)

A hash ring where both servers and keys map to positions on a circle. Each key is served by the next server clockwise.

```
Servers: hash("A")=10, hash("B")=40, hash("C")=80   (on ring 0-99)
Keys:    "user:1" → hash=15 → served by B
         "user:2" → hash=85 → served by A (wraps around)
```

**Adding/removing a server moves only ~K/N keys**, vs `hash % N` which moves nearly all keys.

**Virtual nodes (vnodes):** to avoid uneven distribution, each physical server gets many positions on the ring (e.g., 100-200 vnodes). Smooths load and isolates failure impact.

Used in: Cassandra, DynamoDB, memcached clients (ketama), some CDNs.

## Health checks

The LB must know which backends are alive.

**Active health checks:**
- LB pings backends on a schedule (e.g., `GET /health` every 5s)
- Considered unhealthy after N consecutive failures
- Reintroduced after M consecutive successes

**Passive health checks:**
- LB observes traffic; mark backend unhealthy on error rate / timeout spike
- Faster detection but noisier

**Best practice:** use *both*. Active for cold detection, passive for fast-fail.

**Health check anti-patterns:**
- `/health` returns 200 even when DB is down → LB sends traffic to broken backend
- Health check that does too much (full DB query) → expensive, false positives
- No timeout on the check → stuck checks hide failures

**Levels of health:**
- *Liveness* — process is up
- *Readiness* — ready to serve real traffic (DB connection pool warmed, cache primed)
- *Deep* — downstream dependencies OK

## Sticky sessions

Tie a user to one backend, usually for in-memory session state.

**Mechanisms:**
- Cookie-based (LB sets a cookie identifying the backend)
- IP hash (deterministic from source IP)

**Tradeoffs:**
- *Pro:* lets you keep session state in memory
- *Con:* unbalanced load; lose state on backend death; harder rolling deploys

**Better:** make backends stateless, store session in Redis. Stickiness is a band-aid.

## TLS termination

LB decrypts TLS, sends plaintext to backends (faster) — common for L7 LBs.

**Alternatives:**
- **TLS pass-through:** LB doesn't decrypt; useful when end-to-end encryption required (PCI, healthcare).
- **TLS re-encrypt:** LB decrypts, then re-encrypts to backend. Compromise of inspection + security.

**Cert management:** centralize at the LB. Use ACME (Let's Encrypt) for auto-renewal.

## DNS load balancing & GSLB

For multi-region traffic.

- **Round-robin DNS:** return multiple A records; client picks one.
- **GeoDNS:** return the closest region's IP based on client geo.
- **Latency-based routing (LBR):** return the region with lowest measured latency from client.
- **Weighted DNS:** split traffic by weights for canary deploys.
- **Health-based DNS:** remove unhealthy regions.

Used in: Route 53 (AWS), Cloudflare DNS, Akamai.

**Caveat:** DNS caching by clients can delay failover by minutes (TTL). Use very short TTL (30-60s) for HA.

## Anycast

Same IP advertised from multiple locations; client routes to nearest via BGP.

Used by: Cloudflare, Google DNS (8.8.8.8), CDNs. Sub-second failover, simple to use.

## Layer 7 routing capabilities

Beyond load balancing, modern L7 LBs do:

- **Path-based routing** — `/api/* → api-service`, `/admin/* → admin-service`
- **Host-based routing** — `api.example.com → api`, `web.example.com → web`
- **Header-based routing** — `X-Beta: true → beta-cluster`
- **Canary / blue-green** — 5% traffic to new version
- **Rate limiting** — per-IP, per-API-key
- **Authentication** — JWT validation, OAuth
- **Compression** — gzip, brotli
- **Caching** — small response cache
- **WAF** — block injection, XSS, bots

## Service Mesh (Istio, Linkerd, Consul)

A network of sidecar proxies (usually Envoy) handling inter-service traffic. Provides L7 LB *between microservices* with:
- mTLS everywhere
- Per-call retries, circuit breakers, timeouts
- Traffic splitting (canary)
- Distributed tracing
- Policy enforcement

Tradeoff: significant operational complexity. Use only if you have many microservices and feel the pain.

## Reverse proxies in the wild

| Product | Niche |
|---------|-------|
| **nginx** | Battle-tested L7, static files, simple config |
| **HAProxy** | Best-in-class L4 and L7, extreme perf |
| **Envoy** | Service-mesh data plane, dynamic config, modern observability |
| **Traefik** | Kubernetes-native auto-config |
| **Caddy** | Auto HTTPS, simple config |
| **AWS ALB** | Managed L7, integrates with AWS |
| **AWS NLB** | Managed L4, millions of conns, static IP |
| **Cloudflare LB** | Global anycast + health checks |

## Failover patterns

**Active-Passive:** primary serves traffic; standby idle. Failover when primary dies.
- VRRP / keepalived for IP takeover
- Common for stateful systems (DB, LB itself)

**Active-Active:** all nodes serve traffic. Most modern systems.

**Multi-region:**
- *Active-passive:* one region serves; failover via DNS/Route53.
- *Active-active:* multiple regions; geo-route users; cross-region replication for data.

## Capacity planning the LB

Sometimes the LB itself becomes the bottleneck:

- Connection limit (each conn = some memory)
- CPU for TLS handshakes (offload to NIC if needed)
- Bandwidth (10-100 Gbps NICs available)
- Concurrent in-flight requests (`Little's Law` again)

Solution: scale the LB tier itself — multiple LB instances behind DNS round-robin or anycast.

## Interview Q&A

**Q1: When would you choose L4 over L7?**
*A:* When you need raw throughput (millions of conns/sec), don't need content-aware routing (e.g., generic TCP service, gRPC streaming), want to minimize processing latency, or need to pass-through TLS for compliance. AWS NLB is L4; ALB is L7.

**Q2: A backend is slow but not failing. How does the LB handle it?**
*A:* Active health checks may pass (the server's not "down"). Use *least response time* or *least connections* algorithm so slow backends naturally receive less traffic. Add per-backend latency monitoring; eject backends with anomalous p99. Implement *outlier detection* (Envoy/Istio feature).

**Q3: You have 10 backends, each a hot cache. Which LB algorithm?**
*A:* Consistent hashing (URL or key-based), so the same cache key always hits the same backend — preserves cache locality. Use virtual nodes for even distribution. Round robin would mean 10× cache misses initially as each request might hit a different backend's cold cache.

**Q4: Health check passes, but users see errors. What's wrong?**
*A:* The health check is too superficial. It returns 200 even when a downstream (DB, dependency) is broken, or the backend is in a degraded state (high latency but not failed). Improve: include downstream checks in `/health/deep`, add SLO-based circuit breaking, look at error rate not just availability.

**Q5: Walk through what happens when you `curl example.com`.**
*A:* DNS resolves example.com → IP (possibly geo-routed via GSLB). TCP handshake to that IP, which is actually the LB's anycast IP. TLS handshake (LB terminates). LB picks an L7 routing rule based on host/path. LB picks a backend by algorithm. Forwards HTTP request. Backend processes, returns response. LB possibly compresses, returns to client. Client closes connection (or HTTP keep-alive reuses).

**Q6: Sticky sessions are causing imbalance — 80% of traffic on 2/10 backends. Options?**
*A:* (1) Move state out of memory into Redis so sticky isn't needed. (2) Use cookie-based stickiness with shorter TTL. (3) Cap concurrent sessions per backend. (4) Use *consistent hashing* with vnodes so even if some users stay long, distribution stays uniform. (5) Best fix: make the app stateless.

## Further reading

- HAProxy & nginx docs (they teach the concepts well)
- "The Tail at Scale" — Dean & Barroso
- Existing notes: `../*_LoadBalanc*.md` if present
- *Designing Data-Intensive Applications* — Ch 8 (Trouble with Distributed Systems)
