# Load Balancer

## Quick Reference Card
```
Load Balancer → Incoming traffic ko multiple servers mein distribute karta hai
Round Robin   → 1→2→3→1→2→3 (equal rotation)
Weighted RR   → 1(3x)→2(1x) — powerful server zyada requests le
Least Conn    → Server with fewest active connections chosen
IP Hash       → Same client → always same server (sticky sessions)
Health Check  → Unhealthy server ko rotation se hata deta hai
Interview hook → "Nginx + AWS ALB — Round Robin with health checks for Django app"
```

---

## PART 1: HINGLISH — Samjhne ke liye

### 1.1 Kya hai Load Balancer?

**Analogy: Bank ka token system**

Bank mein 5 counters hain. Ek security guard sabko numbers deta hai — "Counter 1 pe jao", "Counter 3 pe jao". Ye guard dhyan rakhta hai ki koi ek counter pe bheed na ho, aur agar counter 4 band hai to wahan kisi ko na bheje.

Ye guard = Load Balancer.

```
Without Load Balancer:
  1000 users → Server 1 (OVERLOADED!)
               Server 2 (idle)
               Server 3 (idle)

With Load Balancer:
  1000 users → Load Balancer → Server 1 (~333)
                              → Server 2 (~333)
                              → Server 3 (~333)
```

---

### 1.2 Load Balancer kya karta hai?

```
4 main functions:

1. TRAFFIC DISTRIBUTION
   Client requests → LB → Backend servers
   No single server overloaded

2. HEALTH CHECKING
   Every 30 seconds: LB pings each server
   "GET /health → 200 OK?" → Healthy, keep in rotation
   "Timeout / 500 error?" → Remove from rotation
   Server recovers → Auto-add back

3. SSL TERMINATION
   Client → HTTPS → Load Balancer (decrypts SSL)
   LB → HTTP → Backend servers (plain text, faster)
   Backend servers don't need SSL certificates
   Centralized SSL management

4. SESSION PERSISTENCE (Sticky Sessions)
   Same user → always same server
   Useful when session is server-side
   (Ideally: use Redis sessions instead — then not needed)
```

---

### 1.3 Load Balancing Algorithms

#### Algorithm 1: Round Robin

```
ROUND ROBIN — Equal rotation

Request 1 → Server A
Request 2 → Server B
Request 3 → Server C
Request 4 → Server A (back to start)
Request 5 → Server B
...

Pros:
  Simple, works well when all requests similar size
  Even distribution over time

Cons:
  Doesn't account for server capacity differences
  Doesn't account for request complexity
  Server A gets heavy DB query, Server B gets simple ping → uneven load

Best for:
  Homogeneous servers (all same spec)
  Homogeneous requests (all similar processing time)
  Stateless apps (each request independent)
```

#### Algorithm 2: Weighted Round Robin

```
WEIGHTED ROUND ROBIN — Powerful servers get more traffic

Server A: weight=3 (c5.xlarge — 4 vCPU)
Server B: weight=1 (t3.medium — 2 vCPU)

Distribution:
Request 1 → Server A
Request 2 → Server A
Request 3 → Server A
Request 4 → Server B
Request 5 → Server A (starts again)
...

3:1 ratio = Server A gets 3x traffic of Server B

Use case:
  Mixed fleet (some powerful, some small instances)
  Gradual traffic migration (new version on Server B with weight=5,
  old version on Server A with weight=95 → 5% canary)
```

#### Algorithm 3: Least Connections

```
LEAST CONNECTIONS — Server with fewest active connections

  Current connections:
  Server A: 50 active connections
  Server B: 30 active connections  ← Least!
  Server C: 80 active connections
  
  Next request → Server B (fewest connections)

Pros:
  Better for long-lived connections (WebSockets, file uploads)
  Dynamic — adapts to varying request duration
  
Cons:
  More complex tracking
  Connection count ≠ server load (1 heavy query vs 100 light queries)

Best for:
  WebSocket connections
  File upload/download
  Long-running API calls
  Variable request duration

Variant: Least Response Time
  Routes to server with lowest avg response time
  More accurate than connection count
```

#### Algorithm 4: IP Hash (Sticky Sessions)

```
IP HASH — Same client → same server

  Client IP: 192.168.1.1
  Hash: SHA1(192.168.1.1) % 3 = 2 → Server C (always!)
  
  Next request from same IP → hash → Server C (same!)

Pros:
  Session consistency without shared session store
  Good for non-sticky-but-predictable routing
  
Cons:
  Uneven distribution if many users behind same NAT
  (Office with 1000 users all appear as 1 IP → all go to same server)
  Server failure → those users' sessions lost

Use case:
  Legacy apps that can't externalize session
  Gaming servers (state per connection)

Better alternative: Redis sessions + Round Robin
  (Don't need IP Hash if app is truly stateless)
```

#### Algorithm 5: Resource Based / Adaptive

```
RESOURCE BASED — Server mein actual load dekho

  Server A: CPU 90% → Don't send here
  Server B: CPU 20% → Send here!
  Server C: CPU 60% → Maybe

  LB agent runs on each server, reports metrics
  LB uses real-time CPU/Memory to decide routing

Pros:
  Most accurate — actually adapts to server condition
  
Cons:
  Requires monitoring agent on each server
  More complex setup
  Slight delay (metrics polling interval)

Used by: HAProxy, Nginx+ (paid), advanced ALB configurations
```

---

### 1.4 Layer 4 vs Layer 7 Load Balancing

```
LAYER 4 (Transport Layer — TCP/UDP):
  Operates on IP + Port only
  Cannot see HTTP headers, cookies, URL
  Fast (minimal processing)
  
  Routing decision: "This is TCP port 443 → Server A"
  No content inspection
  
  Example: AWS Network Load Balancer (NLB)
  Use: When speed > intelligence (DNS, streaming, games)

LAYER 7 (Application Layer — HTTP/HTTPS):
  Can read HTTP headers, URL path, cookies, body
  Content-based routing possible
  Slightly slower (more processing)
  
  Routing decisions:
  /api/* → API Server cluster
  /static/* → CDN or static server cluster
  Cookie: user_id=123 → specific server (sticky)
  Header: X-Tenant: kenya → Kenya app server
  
  Example: AWS Application Load Balancer (ALB)
  Use: Web apps, microservices routing, A/B testing

EXAMPLE L7 ROUTING (Nginx):
  upstream api_servers {
      server api1.internal:8000;
      server api2.internal:8000;
  }
  
  upstream static_servers {
      server static1.internal:80;
  }
  
  location /api/ {
      proxy_pass http://api_servers;
  }
  
  location /static/ {
      proxy_pass http://static_servers;
  }
```

---

### 1.5 Health Checks

```
ACTIVE HEALTH CHECKS (LB probes servers):
  Every 30 seconds: GET /health HTTP/1.1
  Timeout: 5 seconds
  Unhealthy threshold: 2 failures → Remove from rotation
  Healthy threshold: 3 successes → Add back to rotation

Good /health endpoint:
  - HTTP 200 = all good
  - HTTP 500 = unhealthy
  - Check DB connectivity, Redis connectivity, disk space
  - Response time < 200ms (if slow → server is struggling)

Django health check:
  # pip install django-health-check
  
  urlpatterns = [
      path('health/', include('health_check.urls')),
  ]
  
  INSTALLED_APPS = [
      'health_check',
      'health_check.db',           # DB connectivity
      'health_check.cache',        # Redis/cache
      'health_check.storage',      # File storage
      'health_check.contrib.celery', # Celery
  ]
  
  # GET /health/ → 200 OK if all checks pass
  #             → 500 if any check fails
  # LB removes server from rotation on 500

PASSIVE HEALTH CHECKS:
  LB monitors actual request success/failure
  5 failures in 10 seconds → mark server unhealthy
  No dedicated probe — uses real traffic
  
  Nginx: proxy_next_upstream error timeout http_500;
```

---

### 1.6 Global Server Load Balancing (GSLB)

```
DNS-BASED GLOBAL LOAD BALANCING:
  User in Mumbai → DNS resolve "api.youngman.com"
                → Route to Mumbai server (closest)
  User in London → DNS resolve "api.youngman.com"
                → Route to London server (closest)

  Implementation:
  Route 53 routing policies:
  - Latency-based: Route to lowest latency region
  - Geolocation: Route by user's country/region
  - Failover: Primary region healthy → use primary
              Primary unhealthy → Route to DR region
  - Weighted: 90% primary, 10% new region (canary rollout)

  ┌──────────────┐
  │    Route 53  │
  │    (DNS)     │
  └──────┬───────┘
         │
    ┌────┴────┐
    ▼         ▼
Mumbai     London
  ALB        ALB
   │          │
EC2s        EC2s
```

---

### 1.7 Nginx Load Balancer Config — Ashish ke projects

```nginx
# /etc/nginx/nginx.conf — Youngman production config

upstream django_app {
    # Algorithm: Round Robin (default)
    server 10.0.1.10:8000 weight=1;   # App Server 1
    server 10.0.1.11:8000 weight=1;   # App Server 2
    server 10.0.1.12:8000 weight=2;   # App Server 3 (more powerful)
    
    # Health check (Nginx+ only — commercial):
    # health_check interval=30s fails=2 passes=3;
    
    # keepalive connections to upstream
    keepalive 32;
}

upstream celery_flower {
    server 10.0.1.10:5555;  # Only 1 flower instance (monitoring)
}

server {
    listen 443 ssl;
    server_name api.youngman.com;
    
    ssl_certificate     /etc/ssl/youngman.crt;
    ssl_certificate_key /etc/ssl/youngman.key;
    
    # Static files → S3 CloudFront (not to Django)
    location /static/ {
        proxy_pass https://d1234.cloudfront.net/static/;
    }
    
    # API requests → Django app servers
    location / {
        proxy_pass http://django_app;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto https;
        
        # Timeouts
        proxy_connect_timeout 10s;
        proxy_read_timeout 60s;
        proxy_send_timeout 60s;
    }
    
    # Health check endpoint
    location /health/ {
        proxy_pass http://django_app;
        access_log off;  # Don't pollute logs with health checks
    }
}
```

**AWS ALB routing:**
```
ALB Rules (evaluated top to bottom):
  Rule 1: Path /api/v1/payments/* → Target Group: payments-service
  Rule 2: Path /api/v1/bookings/* → Target Group: bookings-service
  Rule 3: Path /static/*          → Target Group: static-server (or S3)
  Default Rule:                   → Target Group: django-main

ALB Health Check:
  Protocol: HTTP
  Path: /health/
  Healthy threshold: 3
  Unhealthy threshold: 2
  Interval: 30 seconds
  Timeout: 5 seconds
```

---

## PART 2: ENGLISH — Interviewer ko bolne ke liye

### 2.1 Definition

> **Load Balancer**: A component that distributes incoming network traffic across multiple backend servers to ensure no single server is overwhelmed. Provides horizontal scalability, high availability through health checks, SSL termination, and optionally session persistence. Operates at Layer 4 (TCP/UDP) or Layer 7 (HTTP/HTTPS application layer).

---

### 2.2 Load Balancing Algorithm Comparison

| Algorithm | Routing Logic | Best For | Limitation |
|-----------|--------------|----------|------------|
| Round Robin | Equal rotation | Homogeneous servers/requests | Ignores server capacity |
| Weighted RR | Rotation by weight | Mixed-spec fleets, canary | Static weights |
| Least Connections | Fewest active conns | Long-lived connections | Conn count ≠ actual load |
| IP Hash | Hash(client IP) → server | Sticky without shared state | NAT flattens multiple users |
| Least Response Time | Lowest avg latency | Latency-sensitive APIs | Requires measurement overhead |
| Resource Based | CPU/memory metrics | Variable workloads | Requires monitoring agent |

---

### 2.3 Layer 4 vs Layer 7

| Feature | L4 (Network LB) | L7 (Application LB) |
|---------|----------------|---------------------|
| OSI Layer | Transport (TCP/UDP) | Application (HTTP) |
| Routing basis | IP + Port | URL, headers, cookies, body |
| SSL termination | No (passthrough) | Yes |
| Content-based routing | No | Yes |
| Speed | Faster | Slightly slower |
| Use case | DNS, gaming, TCP services | Web apps, microservices |
| AWS example | Network LB (NLB) | Application LB (ALB) |

---

### 2.4 High Availability of the Load Balancer Itself

```
SPOF Problem: What if the Load Balancer fails?

Solutions:
1. Active-Passive LB pair:
   Primary LB → Virtual IP (VIP) → traffic
   Secondary LB → standby
   Keepalived/VRRP: if primary fails → secondary takes VIP

2. DNS round robin to multiple LBs:
   api.example.com → [LB1_IP, LB2_IP]
   DNS rotates → traffic splits

3. Cloud managed LBs (AWS ALB):
   AWS runs multiple LB nodes internally
   Not a single server — distributed, automatically HA
   You never worry about LB availability with AWS ALB

4. Anycast routing:
   Multiple LBs globally, same IP
   BGP routing sends user to nearest one
   (Used by Cloudflare, Google DNS 8.8.8.8)
```

---

### 2.5 Real Project Answer

> "In Youngman, we use a two-tier load balancing setup. AWS Application Load Balancer handles external traffic — it terminates SSL, performs L7 routing, and distributes to Django instances using Round Robin with health checks on `/health/`. The ALB is managed by AWS so we don't worry about its availability. Within the EC2 instances, Nginx acts as a local load balancer between Gunicorn worker processes. The health check endpoint queries DB connectivity and cache availability — if either is degraded, the server returns 500 and the ALB removes it from rotation within ~60 seconds. For Celery, multiple workers process from the same RabbitMQ queue — that's implicit load balancing at the queue level."

---

### 2.6 Common Follow-up Q&A

**Q1: How does a load balancer handle sticky sessions?**
> "Two approaches: IP Hash routing (same IP always goes to same server) or cookie-based affinity. With IP Hash, the LB computes a hash of the client IP and maps it to a server consistently. With cookie-based, the LB inserts a cookie (e.g., `AWSALB=abc123`) into the response; subsequent requests with that cookie go to the same server. Both have failure scenarios — if that server dies, the session is lost. The better solution is to externalize session state to Redis so any server can handle any request, making sticky sessions unnecessary."

**Q2: What is the difference between load balancing and reverse proxy?**
> "Every load balancer is a reverse proxy, but not every reverse proxy is a load balancer. A reverse proxy sits in front of one or more servers and handles requests on their behalf — it can cache, compress, terminate SSL, and add security headers. When the reverse proxy distributes across multiple backends, it becomes a load balancer. Nginx in our setup does both: it's a reverse proxy (SSL termination, header manipulation) and a load balancer (distributing to Gunicorn workers via `upstream` blocks)."

**Q3: What happens during a rolling deployment with a load balancer?**
> "Rolling deployment: take one server out of rotation, deploy new code, health check passes, add back, repeat for next server. The LB health check is what makes this zero-downtime. With AWS ALB and Auto Scaling, the process is: create new launch template with new AMI → update ASG to use new template → ASG terminates old instances one by one, launching new ones → ALB only sends traffic to instances that pass health checks. At no point is all capacity taken offline simultaneously. ECS and Kubernetes deployments work similarly with readiness probes."

---

## Interview Cheat Sheet

```
Load Balancer = Traffic distributor + health monitor + SSL terminator

Algorithms:
  Round Robin: Equal rotation — simple, works for homogeneous setup
  Weighted RR: weight=3 gets 3x requests — mixed fleets, canary deploys
  Least Connections: Fewest active conns wins — long-lived connections
  IP Hash: Same IP → same server — sticky without shared state

Layer 4 vs 7:
  L4 (NLB): TCP-level, fast, no content inspection
  L7 (ALB): HTTP-level, URL/header routing, SSL termination

Health Checks:
  GET /health/ every 30s
  2 failures → remove from rotation
  3 successes → add back
  
  Health endpoint checks: DB, Redis, Celery — not just HTTP 200

High Availability:
  AWS ALB: internally distributed (managed HA)
  Self-hosted: Active-Passive pair with keepalived/VRRP

My setup:
  AWS ALB → Round Robin → Django EC2 instances
  Health check: /health/ (checks DB + Redis)
  SSL terminated at ALB
  Local: Nginx → Gunicorn workers (5 per EC2)

Sticky sessions:
  IP Hash or cookie-based — but prefer Redis sessions (stateless is better)
```
