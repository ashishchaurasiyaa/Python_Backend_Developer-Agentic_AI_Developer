# Forward vs Reverse Proxy

## Quick Reference Card
```
Forward Proxy  → Client ke saamne — client ki taraf se request bhejta hai (VPN concept)
Reverse Proxy  → Server ke saamne — client ke liye server hide karta hai
Forward        → CLIENT side — Squid, VPN, corporate proxy
Reverse        → SERVER side — Nginx, HAProxy, AWS ALB, Cloudflare
Uses (Reverse) → Load balance, SSL terminate, cache, rate limit, serve static
Interview hook → "Nginx = reverse proxy for Django — SSL, static files, load balance"
```

---

## PART 1: HINGLISH — Samjhne ke liye

### 1.1 Forward Proxy Kya Hai?

**Analogy: Secretary jo tumhari taraf se calls karta hai**

Tu apne secretary ko bolta hai: "Google ko call karo aur information laao." Google jaanta hai ki call secretary ne ki — tumhara naam nahi. Secretary CLIENT ki taraf se act kar raha hai.

```
FORWARD PROXY:

CLIENT ──► FORWARD PROXY ──► INTERNET ──► SERVER

  Client: "Proxy ke through google.com access karo"
  Proxy: Request Google on behalf of client
  Google: Receives request from PROXY IP (not client's IP)
          → Client's actual IP hidden!
  
  Client ka actual IP: Hidden
  Proxy ki IP: Visible to destination server

USE CASES:
  1. Content filtering (school/office):
     Company → Forward proxy → Only allowed sites pass through
     Blocks: Facebook, YouTube → Blocked at proxy
  
  2. Bypass geo-restrictions (VPN-like):
     India mein banned site → Forward proxy in US → Access granted
     Site thinks request from US
  
  3. Caching (bandwidth saving):
     Office: 100 employees visit google.com
     Forward proxy caches google's homepage
     Only 1 request to Google, 100 served from cache
     (Squid proxy used for this historically)
  
  4. Anonymity:
     Client IP hidden from destination
     Privacy protection

EXAMPLES:
  Squid Proxy: Open source, corporate use
  Tor Network: Multiple forward proxies (onion routing)
  VPN: Client's traffic routes through VPN server (forward proxy concept)
  Corporate internet filter: IT department controls what employees can access
```

---

### 1.2 Reverse Proxy Kya Hai?

**Analogy: Company ka receptionist**

Tu company ke office aata hai, receptionist se milta hai — "I need to speak to the engineering team." Receptionist routes you to the right engineer. Tujhe pata nahi ki andar 10 engineers hain ya 1. Receptionist = reverse proxy.

```
REVERSE PROXY:

CLIENT ──► INTERNET ──► REVERSE PROXY ──► SERVER(s)

  Client: Request to api.youngman.com
  Reverse Proxy: Receives request, routes to appropriate backend server
  Backend server: Processes request
  
  Client ke saamne: Reverse proxy IP visible
  Backend servers: Hidden from client
  Client: Doesn't know if there's 1 server or 100 behind

USE CASES:
  1. Load Balancing:
     RP distributes requests → multiple backend servers
  
  2. SSL Termination:
     Client → HTTPS → RP (decrypts) → HTTP → Backend
     Backend doesn't need SSL certificate
  
  3. Static file serving:
     RP serves CSS/JS/images directly (fast!)
     Backend only handles dynamic requests
  
  4. Caching:
     RP caches responses → Reduces backend load
  
  5. Rate limiting:
     RP limits: 100 requests/minute per IP
     Backend protected from abuse
  
  6. Security (hide backend):
     Client never knows backend IPs
     Attacker can't directly attack backend servers
  
  7. Compression:
     RP compresses responses (gzip) → Less bandwidth
  
  8. A/B Testing / Canary:
     10% requests → New version server
     90% requests → Old version server

EXAMPLES:
  Nginx: Most popular reverse proxy (also web server)
  Apache httpd: Traditional reverse proxy
  HAProxy: High-performance TCP/HTTP load balancer
  AWS ALB: Managed reverse proxy + load balancer
  Cloudflare: CDN + reverse proxy (global)
  Traefik: Modern, dynamic (Kubernetes-friendly)
```

---

### 1.3 Forward vs Reverse — Key Difference

```
                FORWARD PROXY           REVERSE PROXY
                ──────────────────────────────────────
Position        Client side             Server side
Serves          CLIENT (hides client)   SERVER (hides server)
Configured by   Client                  Server admin
Client knows?   Yes (must configure)    NO (transparent)
Hides           Client's identity       Server's identity
Direction       Client → [FP] → Internet Internet → [RP] → Server
Who benefits    Clients                 Servers / Server owners

ANALOGY SUMMARY:
  Forward = Lawyer who speaks on your behalf (hides YOU)
  Reverse = Company receptionist (hides the COMPANY structure)
```

---

### 1.4 Nginx as Reverse Proxy — Complete Config

```nginx
# /etc/nginx/sites-available/youngman

# Upstream servers (backend Django app)
upstream django_backend {
    least_conn;  # Load balancing algorithm
    server 10.0.1.10:8000 weight=2;  # Primary app server
    server 10.0.1.11:8000 weight=1;  # Secondary app server
    keepalive 32;  # Keep 32 persistent connections to upstream
}

# Redirect HTTP → HTTPS
server {
    listen 80;
    server_name api.youngman.com;
    return 301 https://$server_name$request_uri;
}

# Main HTTPS server
server {
    listen 443 ssl http2;
    server_name api.youngman.com;

    # SSL termination (reverse proxy handles HTTPS)
    ssl_certificate     /etc/letsencrypt/live/youngman.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/youngman.com/privkey.pem;
    ssl_protocols       TLSv1.2 TLSv1.3;
    ssl_ciphers         ECDHE-RSA-AES256-GCM-SHA512:DHE-RSA-AES256-GCM-SHA512;
    ssl_session_cache   shared:SSL:10m;
    
    # Security headers
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header X-Content-Type-Options nosniff;
    add_header X-Frame-Options DENY;
    add_header Content-Security-Policy "default-src 'self'";
    
    # Gzip compression
    gzip on;
    gzip_types text/plain application/json application/javascript text/css;
    gzip_min_length 1024;
    
    # Rate limiting (forward proxy had none, reverse proxy enforces it)
    limit_req_zone $binary_remote_addr zone=api:10m rate=100r/m;
    limit_req zone=api burst=20 nodelay;
    
    # Static files — served directly by Nginx (never hits Django)
    location /static/ {
        alias /var/www/youngman/static/;
        expires 30d;  # Browser cache 30 days
        add_header Cache-Control "public, immutable";
        access_log off;  # Don't log static file hits
    }
    
    # Media files (user uploads) — check if using S3, redirect there
    location /media/ {
        # For S3: redirect to S3/CloudFront
        return 301 https://d1234.cloudfront.net/media/$1;
    }
    
    # Health check (don't log)
    location /health/ {
        proxy_pass http://django_backend;
        access_log off;
    }
    
    # API requests → Django (reverse proxy in action)
    location / {
        proxy_pass http://django_backend;
        
        # Pass original info to Django
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;       # Client's real IP
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;    # https
        
        # Timeouts
        proxy_connect_timeout 10s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
        
        # Buffering (helps with slow clients)
        proxy_buffering on;
        proxy_buffer_size 4k;
        proxy_buffers 8 4k;
    }
}
```

---

### 1.5 Django Settings for Reverse Proxy

```python
# settings.py — Tell Django it's behind a reverse proxy

# Trusted proxy IPs (Nginx's IP or LB's IP)
ALLOWED_HOSTS = ['api.youngman.com', 'youngman.com']

# Trust X-Forwarded-For header from trusted proxies
# (so request.META['REMOTE_ADDR'] gives client's real IP, not Nginx's)
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
USE_X_FORWARDED_HOST = True

# Django 4.0+ specific:
# List of trusted proxy IPs (must match Nginx/ALB IP range)
# TRUSTED_PROXIES is set via middleware

# For rate limiting — get real IP from X-Forwarded-For:
def get_client_ip(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        # First IP in chain is original client
        ip = x_forwarded_for.split(',')[0].strip()
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip

# Note: If behind ALB, ALB already strips to 1 IP in X-Forwarded-For
```

---

### 1.6 API Gateway vs Reverse Proxy

```
REVERSE PROXY (Nginx, HAProxy):
  Simple routing + load balancing + SSL termination
  Low-level, high performance
  Configured with config files
  Not aware of API semantics

API GATEWAY (Kong, AWS API Gateway, Apigee):
  Everything reverse proxy does + more:
  - Authentication/Authorization (JWT verification, API key management)
  - Rate limiting per API key / per user / per endpoint
  - API versioning (route /v1/ to old service, /v2/ to new)
  - Request/Response transformation
  - Circuit breaking
  - Analytics and monitoring
  - Developer portal
  
  More opinionated, API-aware
  Used in: Microservices, API monetization, multi-team APIs

WHEN TO USE WHAT:
  Single monolith Django app:
  → Nginx reverse proxy is fine (already does what you need)
  
  Microservices with multiple teams/APIs:
  → API Gateway (centralizes cross-cutting concerns)
  
  AWS architecture:
  → ALB (layer 7 LB) = reverse proxy
  → API Gateway (AWS service) = full API management
```

---

### 1.7 CDN as Reverse Proxy (Cloudflare, CloudFront)

```
CDN = Reverse proxy distributed globally

WITHOUT CDN:
  User in London → api.niroskos.com (resolves to Mumbai server)
  Network: London → Mumbai → London (600ms round trip)

WITH CLOUDFLARE (CDN as reverse proxy):
  User in London → Cloudflare London edge (DNS resolves to nearest edge)
  
  Cache hit: London edge has response → 10ms!
  Cache miss: London edge → Mumbai origin → caches at London
              Next request from London: Serve from cache!
  
  Cloudflare also provides:
  - DDoS protection (attacks absorbed at edge, not origin)
  - WAF (Web Application Firewall)
  - SSL termination at edge
  - Bot protection
  - Analytics

Youngman/Niroskos:
  S3 + CloudFront = CDN reverse proxy for static assets
  All requests: d1234.cloudfront.net
  CloudFront: Check cache → fetch from S3 if miss → cache → serve
  
  Origin: S3 bucket (hidden behind CloudFront)
  Client: Never talks directly to S3 origin
```

---

### 1.8 Ashish ke projects mein

```
Youngman Architecture:
  Internet
    │
    ▼
  AWS ALB (Managed reverse proxy)
    ├── HTTPS termination (ACM certificate)
    ├── Load balancing (Round Robin)
    ├── Health checks (/health/)
    │
    ▼
  EC2: Nginx (Reverse proxy within instance)
    ├── Static files → served directly
    ├── Rate limiting (100 req/min per IP)
    ├── Gzip compression
    │
    ▼
  Gunicorn (5 workers)
    │
    ▼
  Django app

  TWO REVERSE PROXIES:
  1. AWS ALB: External-facing, SSL, load balancing across EC2s
  2. Nginx: Internal to EC2, static files, rate limiting, Gunicorn management

  NO FORWARD PROXY:
  Users directly access our API
  SAP HANA outbound: Direct HTTPS (no proxy needed)
  
  CloudFront (CDN as reverse proxy):
  Users → CloudFront → S3 (static assets)
  CloudFront = reverse proxy that caches S3 content globally
```

---

## PART 2: ENGLISH — Interviewer ko bolne ke liye

### 2.1 Definitions

> **Forward Proxy**: A server that acts as intermediary on behalf of clients. Clients configure their systems to route requests through the proxy. The destination server sees the proxy's IP, not the client's. Provides client anonymity, content filtering, and caching.

> **Reverse Proxy**: A server that acts as intermediary on behalf of one or more backend servers. Clients send requests to the reverse proxy, which routes to appropriate backends. Clients don't know about backend server topology. Provides load balancing, SSL termination, caching, security, and serving static content.

---

### 2.2 Forward vs Reverse Proxy

| Dimension | Forward Proxy | Reverse Proxy |
|-----------|--------------|---------------|
| Placed before | Client | Server |
| Configured by | Client | Server admin |
| Client aware? | Yes (must configure) | No (transparent) |
| Hides | Client identity | Server topology |
| Purpose | Anonymity, filtering, caching (client) | LB, SSL, caching, security (server) |
| Examples | Squid, VPN, Tor | Nginx, HAProxy, ALB, Cloudflare |
| Who uses | Privacy-conscious users, enterprises | Every production web app |

---

### 2.3 Nginx Reverse Proxy Key Features

```
1. Load Balancing:
   upstream { server s1; server s2; }
   Algorithms: round_robin (default), least_conn, ip_hash, weighted

2. SSL Termination:
   listen 443 ssl http2;
   ssl_certificate + ssl_certificate_key

3. Static File Serving:
   location /static/ { alias /path/to/static/; }
   Much faster than Django serving static files

4. Rate Limiting:
   limit_req_zone $ip zone=api:10m rate=100r/m;
   limit_req zone=api burst=20;

5. Gzip Compression:
   gzip on; gzip_types application/json text/html;
   Reduces response size 60-80%

6. Header Manipulation:
   proxy_set_header X-Real-IP $remote_addr;
   Passes client IP to backend

7. Caching (Nginx proxy cache):
   proxy_cache_path /tmp/nginx_cache levels=1:2
   Caches backend responses at Nginx level
```

---

### 2.4 Real Project Answer

> "In Youngman's production setup, we have a two-tier reverse proxy architecture. AWS Application Load Balancer handles external traffic: SSL termination with ACM certificates, and distributing requests across our EC2 instances using Round Robin with health checks. Within each EC2, Nginx serves as an additional reverse proxy: it serves static files directly from the filesystem (bypassing Django entirely), applies rate limiting at 100 requests per minute per IP, handles gzip compression, and proxies API requests to the Gunicorn workers. This separation means Nginx handles the fast operations (static files, gzip) while Gunicorn handles Python execution. CloudFront acts as a CDN reverse proxy in front of S3, ensuring our static assets are served from the nearest edge location globally."

---

### 2.5 Common Follow-up Q&A

**Q1: Why use both AWS ALB and Nginx? Isn't one enough?**
> "They serve different roles. ALB handles cross-EC2 load balancing — distributing traffic across multiple instances and doing health checks — which Nginx on a single EC2 can't do. Nginx handles per-instance concerns: serving static files without hitting Python, rate limiting, compression, and managing Gunicorn processes. ALB can't serve static files from EC2's filesystem. You could replace Nginx with just Gunicorn and let ALB handle everything, but then Python handles static files (slower) and you lose fine-grained rate limiting. As the architecture grows, having Nginx also makes it easier to add per-server configurations independently of ALB rules."

**Q2: How does Nginx handle a million concurrent connections?**
> "Nginx uses an event-driven, asynchronous, non-blocking architecture — unlike Apache's process-per-connection model. A single Nginx worker process can handle tens of thousands of connections simultaneously using Linux's epoll/kqueue event notification. Events are processed in a loop: accept connection, read request, write to upstream or filesystem, send response — all without blocking. The number of workers is typically set to CPU count. Memory usage is low (~2MB per worker + small per-connection overhead). This is why Nginx is one of the most commonly cited examples of the C10K problem solution."

**Q3: What is the difference between Nginx as a web server vs as a reverse proxy?**
> "Same Nginx binary, different configuration blocks. As a web server: `location / { root /var/www/html; }` — Nginx reads files from the local filesystem and serves them directly. For static sites, documentation, landing pages. As a reverse proxy: `location / { proxy_pass http://backend; }` — Nginx forwards requests to another HTTP server (Django/Gunicorn/Node) and returns the response. In practice, a single Nginx instance often does both simultaneously: `location /static/ { root /var/www/; }` (web server for static) and `location / { proxy_pass http://django; }` (reverse proxy for dynamic content). This hybrid is the standard Django production configuration."

---

## Interview Cheat Sheet

```
Forward Proxy:
  Client side, hides CLIENT identity
  Client must configure to use it
  Use: VPN, corporate filtering, anonymity
  Examples: Squid, Tor, VPN services

Reverse Proxy:
  Server side, hides SERVER topology
  Transparent to client
  Use: Load balancing, SSL, static files, rate limiting
  Examples: Nginx, HAProxy, AWS ALB, Cloudflare

Nginx Reverse Proxy essentials:
  upstream { server s1:8000; server s2:8000; }
  location / { proxy_pass http://upstream_name; }
  
  Key features:
  - Static files: location /static/ { alias /path/; }
  - SSL: listen 443 ssl http2; ssl_certificate ...;
  - Gzip: gzip on; gzip_types ...;
  - Rate limit: limit_req_zone $ip zone=api:10m rate=100r/m;
  - Headers: proxy_set_header X-Real-IP $remote_addr;

API Gateway vs Reverse Proxy:
  Reverse Proxy: Routing, SSL, load balance
  API Gateway: + Auth, rate limit per user, analytics, versioning
  Use API Gateway for microservices/multiple teams

My setup:
  AWS ALB → EC2s (load balance, SSL termination)
  Nginx → Gunicorn (static files, gzip, rate limit)
  CloudFront → S3 (CDN as reverse proxy for static assets)
```
