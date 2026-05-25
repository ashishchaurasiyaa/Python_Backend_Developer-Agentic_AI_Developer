# Web Server

## Quick Reference Card
```
Web Server    → Static content serve karta hai (HTML, CSS, images) — Nginx, Apache
App Server    → Dynamic content — business logic execute karta hai — Gunicorn, uWSGI
Reverse Proxy → Client ke aage Nginx baith ke requests forward karta hai
Worker model  → Gunicorn: pre-fork workers — har request ek worker process handle karta hai
Interview hook → "Nginx + Gunicorn + Django DRF — production stack at Youngman/Niroskos"
```

---

## PART 1: HINGLISH — Samjhne ke liye

### 1.1 Kya hai?

**Web Server = Ek darwaaza wala**

Socho ek hospital:
- **Web Server (Nginx)** = Security guard at entrance. Har aane wale ko check karta hai, sahi jagah bhejta hai.
  - Simple requests (X-ray report PDF, photo) → khud de deta hai (static files)
  - Doctor se milna hai → andar bhejta hai (forward to app server)

- **App Server (Gunicorn)** = Doctor. Actual kaam karta hai — diagnose karta hai, treatment decide karta hai.
  - Database se data laata hai
  - Business logic chalata hai
  - Response generate karta hai

```
Browser
  │
  ▼
Nginx (Web Server / Reverse Proxy)
  │── Static files (CSS, images, media) → directly serve
  │── Dynamic requests (API calls) ──────┐
                                          ▼
                                   Gunicorn (App Server)
                                     │── Worker 1
                                     │── Worker 2
                                     │── Worker 3
                                          │
                                          ▼
                                   Django Application
                                          │
                                          ▼
                                   PostgreSQL / Redis
```

---

### 1.2 Web Server vs Application Server

| Feature | Web Server (Nginx) | App Server (Gunicorn) |
|---------|-------------------|----------------------|
| Kya karta hai | Static files serve, proxy | Business logic execute |
| Performance | Very fast (C, event-loop) | Depends on code complexity |
| Scaling | Horizontal + CDN | Horizontal (more workers) |
| Protocol | HTTP/1.1, HTTP/2 | WSGI/ASGI |
| Examples | Nginx, Apache, Caddy | Gunicorn, uWSGI, Uvicorn |

---

### 1.3 Nginx — Ek Web Server ka kaam

**Nginx ke 5 main jobs:**

```
1. Static File Server
   GET /media/profile.jpg → Nginx directly serves from /var/www/media/
   (No Django involved — very fast)

2. Reverse Proxy
   GET /api/bookings/ → Forward to Gunicorn:8000

3. Load Balancer
   Requests distribute karo between multiple Gunicorn instances

4. SSL Termination
   HTTPS connection Nginx handle karta hai
   Gunicorn ko plain HTTP forward hota hai

5. Rate Limiting / Security
   Too many requests from one IP → reject
   DDoS protection
```

**Nginx config (simplified):**
```nginx
# Static files — Nginx directly serve karta hai
location /static/ {
    alias /var/www/staticfiles/;
    expires 30d;                    # Cache for 30 days
}

location /media/ {
    alias /var/www/media/;
}

# API requests — Gunicorn ko forward karo
location /api/ {
    proxy_pass http://127.0.0.1:8000;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
}

# SSL
listen 443 ssl;
ssl_certificate /etc/ssl/cert.pem;
ssl_certificate_key /etc/ssl/key.pem;
```

---

### 1.4 Gunicorn — Application Server

**WSGI = Web Server Gateway Interface**
- Python app server ke liye standard interface
- Django likhta hai WSGI, Gunicorn use karta hai WSGI

**Pre-fork Worker Model:**
```
Gunicorn Master Process
    ├── Worker 1 (PID: 1234) — request handle kar raha hai
    ├── Worker 2 (PID: 1235) — idle
    ├── Worker 3 (PID: 1236) — request handle kar raha hai
    └── Worker 4 (PID: 1237) — idle

Master process workers ko spawn karta hai
Agar worker crash kare → master new worker spawn karta hai
```

**Workers ka number:**
```bash
# Formula: (2 × CPU cores) + 1
# 4-core machine → 9 workers
gunicorn --workers 9 --bind 0.0.0.0:8000 niroskos.wsgi:application
```

**Sync vs Async Workers:**
```
Sync worker (default):
  - Ek request at a time per worker
  - CPU-bound tasks ke liye good
  - Django ORM calls blocking hain → sync theek hai

Async worker (Uvicorn/Gunicorn with eventlet):
  - Multiple concurrent connections per worker
  - I/O-bound tasks ke liye good
  - WebSocket, SSE ke liye needed
  
Production stack:
  - Django (sync) → Gunicorn sync workers
  - FastAPI/async Django → Uvicorn workers
```

---

### 1.5 WSGI vs ASGI

```
WSGI (Synchronous):
  Request → Worker process → Django view → Response
  One request at a time per worker
  Django + DRF default
  
ASGI (Asynchronous):
  Request → Event loop → Django async view → Response
  Multiple concurrent requests per worker
  Django Channels, FastAPI
  
Youngman/Niroskos: WSGI (Gunicorn) — standard Django DRF
Celery handles async — not ASGI
```

---

### 1.6 Ashish ke projects mein

**Youngman Beta stack:**
```
EC2 (AWS)
  └── Nginx (port 80/443)
        └── Gunicorn (port 8000) — 4 workers
              └── Django DRF
                    └── PostgreSQL (RDS) + Redis (ElastiCache)
              
Static files → AWS S3 + CloudFront CDN
Media files → AWS S3 (presigned URLs)
```

**Niroskos stack:**
```
AWS EC2
  └── Nginx (SSL termination + subdomain routing)
        └── Gunicorn + Django 5.2
              └── PostgreSQL + Redis + Typesense
        
Celery workers → separate EC2 instances
Beat scheduler → separate process
```

---

## PART 2: ENGLISH — Interviewer ko bolne ke liye

### 2.1 Definition

> A **Web Server** is software (or hardware) that accepts HTTP requests and responds with static content (HTML, images, CSS) or forwards dynamic requests to an application server. A web server like Nginx acts as a reverse proxy, SSL terminator, and static file server, sitting between clients and the application layer.

> An **Application Server** (like Gunicorn) runs the actual application code — executing business logic, querying databases, and generating dynamic responses. It implements WSGI/ASGI to interface with Python web frameworks.

---

### 2.2 Request Lifecycle

```
1. Browser → DNS lookup → IP address resolved
2. TCP connection established (3-way handshake)
3. TLS handshake (HTTPS) — Nginx terminates SSL
4. HTTP request sent to Nginx
5. Nginx checks:
   - Static file? → Serve directly (no app involved)
   - API request? → Forward to Gunicorn via reverse proxy
6. Gunicorn worker receives request
7. WSGI callable invoked → Django processes request
8. Middleware stack executed (auth, CORS, rate limit)
9. URL router → View function
10. ORM query → PostgreSQL
11. Response built → JSON serialized
12. Response travels back: Gunicorn → Nginx → Browser
```

---

### 2.3 Nginx vs Apache

| Feature | Nginx | Apache |
|---------|-------|--------|
| Architecture | Event-driven (async) | Process/thread per request |
| Concurrency | High (10k+ connections) | Lower under heavy load |
| Static files | Very fast | Good |
| Dynamic content | Via reverse proxy | mod_wsgi/mod_php built-in |
| Memory usage | Low | Higher |
| Config style | Blocks | Directives |
| Use case | High-traffic, microservices | Traditional PHP hosting |

**Why Nginx for Python apps:** Python apps use WSGI/ASGI servers (Gunicorn), not Apache's mod_wsgi typically. Nginx's event-driven model handles thousands of concurrent connections efficiently.

---

### 2.4 Worker Sizing

```python
# Production formula
import multiprocessing
workers = (multiprocessing.cpu_count() * 2) + 1

# Additional considerations:
# - Memory per worker: ~50-100MB for Django
# - EC2 t3.medium (2 vCPU, 4GB RAM): 5 workers × 100MB = 500MB used
# - Keep headroom for spikes

# Timeout
gunicorn_timeout = 30  # seconds — kill worker if request takes > 30s
keepalive = 2          # seconds — persistent connections

# Command
# gunicorn --workers=5 --timeout=30 --bind=0.0.0.0:8000 app.wsgi:application
```

---

### 2.5 Real Project Answer

> "At Youngman and Niroskos, our standard stack is Nginx + Gunicorn + Django DRF deployed on AWS EC2. Nginx handles SSL termination — certificates from Let's Encrypt — and serves all static files directly from disk, bypassing Django entirely. This is a significant performance optimization since Django doesn't process static file requests. For API calls, Nginx forwards to Gunicorn running with (2×CPU+1) sync workers. For Niroskos' multi-tenant setup, Nginx handles subdomain-based routing — each tenant's subdomain routes to the same Gunicorn process but with the tenant context extracted from the Host header."

---

### 2.6 Common Follow-up Q&A

**Q1: Why not serve static files from Django directly?**
> "Django's static file serving is intentionally simple and not production-grade. It goes through the entire middleware stack for every image and CSS file. Nginx serves static files directly from disk using sendfile syscall — orders of magnitude faster. In production, we use WhiteNoise or S3/CloudFront for even better performance."

**Q2: What happens when a Gunicorn worker dies?**
> "The Gunicorn master process monitors workers via heartbeat. A worker that doesn't respond within the timeout (--timeout=30) is killed with SIGKILL and a new worker is spawned. Requests in-flight on the dead worker are lost — the client gets a 502/504. This is why we use pre-fork workers (resilient) and Nginx retry logic for critical endpoints."

**Q3: How do you handle WebSocket connections?**
> "Standard Gunicorn sync workers can't handle WebSockets (long-lived connections). Options: (1) Use Gunicorn with eventlet/gevent workers for async — but complex. (2) Use Django Channels + Daphne/Uvicorn (ASGI) for WebSocket-specific routes. (3) Separate WebSocket service (Node.js, Go) that's more efficient for stateful connections. In Niroskos, we use polling for live order tracking rather than WebSockets to keep the stack simple."

---

## Interview Cheat Sheet

```
Web Server (Nginx):
- Static files serve (fast, no Django)
- Reverse proxy to Gunicorn
- SSL termination
- Load balancing
- Rate limiting / DDoS protection

App Server (Gunicorn):
- Runs Django/Python code
- Pre-fork workers: (2×CPU)+1
- WSGI interface
- Each worker = separate process

Request path:
Browser → Nginx (SSL, static) → Gunicorn workers → Django → DB → back

WSGI vs ASGI:
WSGI = sync, one request per worker (Django default)
ASGI = async, concurrent requests (Django Channels, FastAPI)

My stack: Nginx + Gunicorn + Django DRF on AWS EC2
Static/media → S3 + CloudFront
```
