# ⚖️ Load Balancing — System Design Deep Dive

> **Target:** 3-5 YOE | **Goal:** Load balancer kya, kaise kaam karta, kaunse algorithms, kab kya use.

---

## Part 1: WHAT — Load Balancer Kya Hai?

### Definition

> **Load Balancer** = traffic distribute karne wala component **multiple servers ke beech**. Single point pe load aata, multiple servers pe distribute hota.

### Real-Life Analogy 🛒

Soch tu **supermarket me cashier counter** dekh raha hai:
- 1 cashier = long line, slow
- 5 cashiers + manager directing = parallel, fast

**Manager = Load Balancer**
**Cashiers = Servers**

---

## Part 2: WHY — Load Balancing Critical?

### Reason 1: Scalability

Single server handles ~10k requests/sec.
Need 100k? Add 10 servers.
LB distributes load.

### Reason 2: Reliability

Server down? LB routes around.
No single point of failure.

### Reason 3: Performance

Distribute load → faster responses.
No server overwhelmed.

### Reason 4: Maintenance

Take server down for updates.
LB sends traffic elsewhere.
Zero downtime deploys.

### Reason 5: SSL Termination

LB handles SSL.
Servers focus on application.

---

## Part 3: HOW — Load Balancer Architecture

### Basic Flow

```
USERS
  │
  ▼
┌─────────────────────┐
│  LOAD BALANCER      │
│  - Receives request │
│  - Picks server     │
│  - Forwards         │
└──────────┬──────────┘
           │
   ┌───────┼───────┐
   ▼       ▼       ▼
Server  Server  Server
  1       2       3
```

### Components

#### 1. VIP (Virtual IP)
Public-facing IP.
Users see this.

#### 2. Health Checks
Periodically check servers.
Skip unhealthy ones.

#### 3. Algorithm
Decides which server gets request.

#### 4. Sticky Sessions
Same user → same server (sometimes).

---

## Part 4: TYPES OF LOAD BALANCERS

### Type 1: Hardware Load Balancers

> **Physical devices.**

Examples:
- F5 BIG-IP
- Citrix NetScaler

#### Pros
- Very fast
- Reliable
- Feature-rich

#### Cons
- Expensive ($$$$$)
- Hard to scale
- Vendor lock-in

### Type 2: Software Load Balancers

> **Software running on commodity hardware.**

Examples:
- Nginx
- HAProxy
- Traefik
- Envoy

#### Pros
- Flexible
- Cheap (free!)
- Scalable

#### Cons
- Need to manage
- Configuration complexity

### Type 3: Cloud Load Balancers

> **Managed by cloud provider.**

Examples:
- AWS ELB (Classic, ALB, NLB)
- GCP Cloud Load Balancing
- Azure Load Balancer

#### Pros
- Managed (no ops)
- Integrated with services
- Auto-scaling

#### Cons
- Vendor lock-in
- Cost
- Limited customization

---

## Part 5: LOAD BALANCER LAYERS

### Layer 4 (Transport)

> **Routes based on TCP/UDP.**

Sees:
- IP addresses
- Ports
- Not application data

#### Pros
- Fast (less processing)
- Protocol-agnostic
- Simple

#### Cons
- Can't make smart decisions
- No URL-based routing

### Layer 7 (Application)

> **Routes based on HTTP.**

Sees:
- URL paths
- Headers
- Cookies
- Body

#### Pros
- Smart routing
- Content-based decisions
- SSL termination

#### Cons
- Slower (more processing)
- HTTP only
- More complex

### Choosing

#### L4 If
- TCP/UDP based
- Maximum performance needed
- Simple routing

#### L7 If
- HTTP-based
- Content-aware routing needed
- SSL termination wanted

---

## Part 6: LOAD BALANCING ALGORITHMS

### Algorithm 1: Round Robin

> **Sequential distribution.**

```
Request 1 → Server 1
Request 2 → Server 2
Request 3 → Server 3
Request 4 → Server 1 (back to start)
```

#### Pros
- Simple
- Fair distribution
- No state needed

#### Cons
- Doesn't consider load
- All servers treated equal

#### Use When
- Servers identical
- Stateless workloads
- Simple needs

### Algorithm 2: Least Connections

> **Server with fewest active connections gets request.**

```
Server 1: 5 connections
Server 2: 3 connections ← gets request
Server 3: 8 connections
```

#### Pros
- Better for varied workloads
- Adapts to load

#### Cons
- Doesn't consider connection cost

#### Use When
- Long-lived connections
- Variable request times

### Algorithm 3: Weighted Round Robin

> **Some servers get more traffic.**

```
Server 1 (weight 3): gets 3 out of every 6
Server 2 (weight 2): gets 2 out of every 6
Server 3 (weight 1): gets 1 out of every 6
```

#### Use When
- Heterogeneous servers
- Some more powerful

### Algorithm 4: IP Hash

> **Same IP → same server (sticky).**

```
hash(client_ip) % num_servers = server_index
```

#### Pros
- Sticky sessions
- No external state

#### Cons
- Uneven distribution if IPs cluster

#### Use When
- Session affinity needed
- No shared state

### Algorithm 5: Least Response Time

> **Server with fastest current response.**

#### Pros
- Best UX
- Adapts to performance

#### Cons
- Complex to measure
- Health check overhead

### Algorithm 6: Random

> **Random server picked.**

#### Pros
- Simple
- No state

#### Cons
- Not predictable

### Algorithm 7: Consistent Hashing

> **Minimize re-routing when servers added/removed.**

Concept:
```
Servers on a "ring"
Hash request to ring position
Use clockwise nearest server
```

#### Pros
- Stable mapping
- Server changes minimal disruption
- Used by Cassandra, DynamoDB

#### Cons
- Complex to implement

---

## Part 7: HEALTH CHECKS

### Why Health Checks

> **Don't send traffic to dead servers.**

### Types

#### TCP Check
> "Server accepting connections?"

Simple, fast.

#### HTTP Check
> "Server responding to /health?"

```
GET /health
↓
200 OK = healthy
500 or timeout = unhealthy
```

#### Application-Level
> Custom logic:
- Database connection OK?
- Cache accessible?
- Critical services up?

### Frequency

- Every 5-30 seconds typical
- Configurable
- Trade-off: speed vs load

### Failure Handling

```
3 consecutive failures = mark unhealthy
Don't route here
Continue checking
2 consecutive successes = mark healthy
Resume routing
```

---

## Part 8: SESSION PERSISTENCE (STICKY SESSIONS)

### What It Is

> **Same user → same server.**

### Why Needed

#### Stateful Apps
Session data on specific server.
Need to stick.

#### Performance
- Cached data
- Connection reuse

### Implementation

#### Cookie-Based
```
First request → Server 1
LB sets cookie: server=1
Next request with cookie → Server 1
```

#### IP-Based
```
hash(client_ip) → same server
```

### Drawbacks

- Uneven load
- Server failure = session lost
- Limits scaling

### Better Alternative

> Stateless apps + external session store (Redis).

---

## Part 9: SSL/TLS TERMINATION

### What It Means

> **LB handles SSL encryption/decryption.** Servers see plain HTTP.

### Why

- Centralized cert management
- Less load on servers
- Better SSL features (HTTP/2, etc.)

### Architecture

```
USER (HTTPS) ─→ LB (decrypt) ─→ SERVERS (HTTP)

Between LB and servers:
- HTTP (private network)
- Or HTTPS (re-encrypt) for security
```

---

## Part 10: GLOBAL LOAD BALANCING

### Single Region

```
Users in India → Mumbai DC
Users in US → US DC
Users in EU → EU DC
```

### Geo-DNS

> DNS returns different IP based on user location.

### Anycast

> Same IP advertised from multiple locations.
> User reaches nearest naturally.

### CDN

> Content delivery network at edge.
> Static content from nearest POP.

---

## Part 11: LOAD BALANCER HIGH AVAILABILITY

### Problem

LB itself = single point of failure.

### Solutions

#### Active-Passive
```
LB 1 (active)
LB 2 (standby)

If LB 1 fails, LB 2 takes over.
Floating IP moves.
```

#### Active-Active
```
LB 1 + LB 2 both active
DNS round-robin between them
Each handles half traffic
```

#### DNS Failover
```
Multiple LB IPs in DNS
Client retries on failure
```

---

## Part 12: AWS ELB OPTIONS

### Classic Load Balancer (ELB)

Old generation.
L4 + L7 mixed.
Avoid for new.

### Application Load Balancer (ALB)

> **L7, HTTP/HTTPS, modern.**

Features:
- Path-based routing
- Host-based routing
- WebSocket support
- HTTP/2

Use: Web apps

### Network Load Balancer (NLB)

> **L4, ultra-fast, TCP/UDP.**

Features:
- Static IP
- Million+ connections
- Low latency

Use: Gaming, IoT, custom protocols

### Gateway Load Balancer (GLB)

> **Specialty for security appliances.**

Use: Firewalls, IDS, packet inspection

---

## Part 13: NGINX AS LOAD BALANCER

### Configuration Concepts

```
Backend servers defined.
LB algorithm chosen.
Routes configured.
Health checks set.
```

### Use Cases

- Reverse proxy
- API gateway
- Static file serving
- SSL termination

### Why Popular

- Free
- Fast
- Flexible
- Wide support

---

## Part 14: COMMON ARCHITECTURE PATTERNS

### Pattern 1: Single Region

```
USER
 ↓
DNS → LB → SERVERS
```

Simple. Limited HA.

### Pattern 2: Multi-AZ

```
USER
 ↓
DNS → LB
       ↓        ↓
    AZ-1      AZ-2
    Servers   Servers
```

HA within region.

### Pattern 3: Multi-Region

```
USER
 ↓
DNS (geo-routing)
 ↓         ↓
Region 1  Region 2
LB         LB
Servers    Servers
```

Global, complex, expensive.

### Pattern 4: API Gateway

```
USER
 ↓
API GATEWAY (auth, rate limit, routing)
 ↓
LBs for each service
 ↓
Microservices
```

Microservices standard.

---

## Part 15: PERFORMANCE CONSIDERATIONS

### Throughput

- HW LBs: millions of req/s
- Cloud LBs: 100k-1M req/s
- Software LBs: 50k-500k req/s

### Latency

- LB adds 1-10ms typically
- Layer 7 slower than Layer 4

### Connection Limits

- Each LB has max connections
- Plan for growth

---

## Part 16: SECURITY

### DDoS Protection

> Absorb attacks before reaching servers.

- AWS Shield (auto)
- Cloudflare
- Custom rules

### WAF (Web Application Firewall)

> Block malicious requests.

- SQL injection
- XSS
- Common attacks

### Rate Limiting

> Throttle abusive clients.

Per IP, per user, per API key.

### Access Control

> IP whitelisting.
> Country blocking.
> Authentication.

---

## Part 17: MONITORING

### Key Metrics

#### Request Metrics
- Requests per second
- Latency (p50, p95, p99)
- Errors

#### Backend Metrics
- Healthy hosts
- Unhealthy hosts
- Backend response time

#### Connection Metrics
- Active connections
- New connections/sec
- Rejected connections

### Alerts

```
- All backends down → critical
- High error rate → warning
- High latency → warning
- Backend failing health → warning
```

---

## Part 18: COMMON ISSUES

### Issue 1: Uneven Load

Cause: Sticky sessions, IP hash with clustered IPs.
Fix: Better algorithm, stateless apps.

### Issue 2: Connection Limits Hit

Cause: Too many connections.
Fix: Scale up LB, multiple LBs.

### Issue 3: Health Check Storm

Cause: Too many checks too often.
Fix: Reduce frequency, optimize endpoint.

### Issue 4: SSL Issues

Cause: Cert expired, wrong chain.
Fix: Automated renewal, monitoring.

### Issue 5: Timeouts

Cause: Slow backend.
Fix: Investigate backend, adjust timeouts.

---

## Part 19: CHOOSING A LOAD BALANCER

### Decision Tree

```
Cloud provider?
├─ Yes → Use cloud LB (ALB/NLB/etc.)
└─ No → On-prem or hybrid

What protocol?
├─ HTTP → ALB or Nginx
├─ TCP → NLB or HAProxy
├─ gRPC → ALB or Envoy

Scale?
├─ Small → Nginx
├─ Medium → HAProxy
├─ Large → Envoy or cloud
```

---

## Part 20: ADVANCED PATTERNS

### Service Mesh

> Each service has sidecar proxy.
> Internal LB via mesh.

Examples: Istio, Linkerd

### Canary Deployments

```
LB sends 5% traffic to new version
95% to old
Monitor errors
Gradually increase
```

### Blue-Green

```
Blue (current) gets 100%
Deploy Green (new)
Switch LB to Green
Blue becomes standby
```

### A/B Testing

```
50% to version A
50% to version B
Compare metrics
```

---

## Part 21: REAL-WORLD EXAMPLE

### Netflix Architecture

```
Users worldwide
 ↓
DNS routing (Route 53)
 ↓
Regional ELBs
 ↓
Zuul (custom LB/Gateway)
 ↓
Microservices (Eureka discovery)
```

### Key Decisions
- Multi-region for HA
- Custom edge for video
- Service mesh internally
- Aggressive caching

---

## Part 22: Q&A

### Q: When to add load balancer?
**A**: When you have 2+ servers.

### Q: HW vs SW LB?
**A**: SW for most. HW only for extreme requirements.

### Q: Single LB enough?
**A**: No, need at least 2 for HA.

### Q: Sticky sessions OK?
**A**: Try to avoid. Stateless better.

### Q: Algorithm to use?
**A**: Round robin default. Least connections for varied.

### Q: Layer 4 vs 7?
**A**: L7 for HTTP apps. L4 for performance/non-HTTP.

### Q: How to handle DDoS?
**A**: CDN + WAF + rate limiting + cloud DDoS protection.

---

## 🎯 Bhai's Final Words

> **Load balancer = backend ka traffic controller. Without it, single server bottleneck. With it, unlimited scale possible.**

3 Mantras:
1. **At least 2 LBs** (HA)
2. **Health checks matter** (skip dead servers)
3. **Right algorithm** (round robin default)

Senior engineer LB ko deeply samajhta hai. Architecture decisions me central. 🚀
