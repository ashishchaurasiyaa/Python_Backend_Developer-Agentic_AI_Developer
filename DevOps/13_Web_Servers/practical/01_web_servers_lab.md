# Web Servers — Hands-On Lab
**DevOps Track · Phase 13 Practical**

## Prerequisites

- Nginx installed locally (`brew install nginx` on macOS, or run it via Docker — `docker run -p 80:80 nginx` — either works for this lab; examples below assume a locally installed nginx you can edit config files for and `reload`, but every config translates directly to a Docker bind-mount if you prefer containers)
- A simple backend to proxy to — Python's built-in server is enough for basic labs (`python3 -m http.server 8000`), but Labs 2-3 want something you can run multiple copies of; a tiny FastAPI/Flask app is ideal (`pip install fastapi uvicorn`)
- `openssl` (ships with macOS/Linux) for generating a self-signed cert — good enough for local TLS practice, no real domain or Let's Encrypt needed
- `curl` and optionally `hey`/`ab` for load-testing the rate limiter in Lab 3
- Root/sudo access to edit `/etc/nginx/` and reload the service (or, if using Docker, just restart the container — no sudo needed)

This lab is nginx-focused, matching the depth of `../01_nginx.md`. If you also want Apache practice, the `mod_proxy` VirtualHost example in `../02_apache_basics.md` is a near-1:1 translation of Lab 1 below — worth doing once you're comfortable with the nginx version, specifically to feel how similar the reverse-proxy concept is across both.

---

## Lab 1: Reverse Proxy — `proxy_pass` and Forwarded Headers

**Objective:** Get nginx correctly forwarding requests to a backend, with the headers a real backend needs to see the true client IP — the single most common nginx config you'll write in a real job.

**Task:**
1. Start a backend on port 8000 that logs/echoes the client IP it sees (a one-line FastAPI endpoint returning `request.client.host` works, or `python3 -m http.server 8000` combined with checking its access log).
2. Write an nginx `server` block listening on port 80, `proxy_pass`ing `/` to `http://127.0.0.1:8000`.
3. Add the four standard forwarding headers: `Host`, `X-Real-IP`, `X-Forwarded-For`, `X-Forwarded-Proto`.
4. Set explicit `proxy_connect_timeout`, `proxy_read_timeout`, `proxy_send_timeout`.
5. Test with `curl -v http://localhost/` and confirm you get the backend's response through nginx.
6. Temporarily REMOVE the `X-Real-IP`/`X-Forwarded-For` headers, hit the backend again, and confirm the backend now sees `127.0.0.1` (nginx itself) instead of your real client IP — reproduce the exact problem the lesson file warns about, then put the headers back and confirm it's fixed.

<details>
<summary>Solution / walkthrough</summary>

```python
# backend.py — minimal FastAPI backend that reveals what IP it actually sees
from fastapi import FastAPI, Request
app = FastAPI()

@app.get("/")
def root(request: Request):
    return {"client_ip_seen_by_backend": request.client.host}
```
```bash
pip install fastapi uvicorn
uvicorn backend:app --port 8000
```

```nginx
# /etc/nginx/conf.d/lab1.conf (or a docker bind-mounted equivalent)
server {
    listen 80;
    server_name localhost;

    location / {
        proxy_pass http://127.0.0.1:8000;

        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        proxy_connect_timeout 5s;
        proxy_read_timeout    60s;
        proxy_send_timeout    60s;
    }
}
```

```bash
sudo nginx -t && sudo nginx -s reload
curl -v http://localhost/
# {"client_ip_seen_by_backend":"127.0.0.1"}   <- still 127.0.0.1 because you're curling from localhost;
# the point of this lab is the HEADER being present, verify with -v and look for it round-tripping,
# or check the FastAPI request.headers directly to confirm X-Forwarded-For arrived correctly
```

To really see the difference, print `request.headers.get("x-forwarded-for")` in the backend instead of `request.client.host` (which nginx can't change, only headers can carry the real info):
```python
@app.get("/")
def root(request: Request):
    return {
        "direct_connection_ip": request.client.host,          # always nginx (127.0.0.1) once behind a proxy
        "x_forwarded_for_header": request.headers.get("x-forwarded-for"),  # the REAL client IP, if nginx sent it
    }
```
Remove the `proxy_set_header X-Forwarded-For ...` line, reload, and `x_forwarded_for_header` becomes `None` — this is the exact breakage (broken IP-based rate limiting, broken audit logs) the lesson file calls out as "not optional in a real deployment."
</details>

---

## Lab 2: Load Balancing — `upstream` with `least_conn`

**Objective:** Run two backend instances and prove nginx actually distributes load between them, then compare round-robin vs `least_conn` behavior under uneven request duration.

**Task:**
1. Run TWO copies of your backend, on ports 8000 and 8001, each printing its own port number in the response so you can tell them apart.
2. Write an `upstream backend_pool` block listing both, with `keepalive 32`.
3. Point a `location /` at `proxy_pass http://backend_pool` with `proxy_http_version 1.1` and `proxy_set_header Connection ""` (required for keepalive to the upstream).
4. Send 20 sequential requests with a loop and tally which backend answered each — confirm round-robin alternates roughly evenly.
5. Make one backend artificially slow (add `time.sleep(1)` to one instance's handler) and switch the upstream to `least_conn;`. Fire 10 CONCURRENT requests (not sequential — use `hey -c 10 -n 10` or background `curl &` calls) and confirm the fast backend receives more of them, because `least_conn` routes to whichever has fewer active connections, not blind round-robin.

<details>
<summary>Solution / walkthrough</summary>

```python
# backend.py — parameterize the port so you can tell instances apart
import sys, time
from fastapi import FastAPI
app = FastAPI()
PORT = sys.argv[1] if len(sys.argv) > 1 else "unknown"

@app.get("/")
def root():
    return {"served_by_port": PORT}
```
```bash
uvicorn backend:app --port 8000 --app-dir . &
uvicorn backend:app --port 8001 --app-dir . &
```

```nginx
upstream backend_pool {
    server 127.0.0.1:8000;
    server 127.0.0.1:8001;
    keepalive 32;
}

server {
    listen 80;
    server_name localhost;

    location / {
        proxy_pass http://backend_pool;
        proxy_http_version 1.1;
        proxy_set_header Connection "";
    }
}
```

```bash
for i in $(seq 1 20); do curl -s http://localhost/ | jq -r .served_by_port; done | sort | uniq -c
#   10 8000
#   10 8001
```

**Switching to `least_conn` with an artificially slow backend:**
```python
# backend on 8001 only — simulate a slow instance
import time
@app.get("/")
def root():
    time.sleep(1)
    return {"served_by_port": "8001-slow"}
```
```nginx
upstream backend_pool {
    least_conn;
    server 127.0.0.1:8000;
    server 127.0.0.1:8001;
    keepalive 32;
}
```
```bash
sudo nginx -s reload
hey -n 20 -c 10 http://localhost/ 2>&1 | tail -20
```
With `least_conn`, once the slow backend has an active in-flight request, nginx routes subsequent concurrent requests to the backend with fewer active connections (the fast one) instead of blindly alternating — you should see the fast backend (8000) handle a disproportionate share of the 20 requests versus a straight round-robin split. This is the exact scenario the lesson file describes: "requests with variable processing time" is where `least_conn` earns its keep over plain round-robin.
</details>

---

## Lab 3: Production-Style Combined Config — SSL + Rate Limiting + Reverse Proxy

**Objective:** Assemble everything from Labs 1-2 plus TLS termination and rate limiting into one realistic production-shaped config, and prove the rate limiter actually rejects excess traffic.

**Task:**
1. Generate a self-signed certificate for `localhost` with `openssl req -x509 ...` (no real domain/Let's Encrypt needed for local practice).
2. Write a `server` block on port 80 that redirects everything to HTTPS (`return 301 https://$host$request_uri`).
3. Write a `server` block on port 443 with `ssl_certificate`/`ssl_certificate_key`, `ssl_protocols TLSv1.2 TLSv1.3`, and HSTS via `add_header Strict-Transport-Security`.
4. Add a `limit_req_zone` at 5 requests/second per IP, applied to a `/login` location with `burst=10 nodelay` and `limit_req_status 429`.
5. Proxy everything else to your Lab 1/2 backend pool as normal.
6. Test SSL: `curl -vk https://localhost/` (the `-k` flag accepts the self-signed cert) and confirm the handshake completes and you see `TLSv1.3` (or 1.2) negotiated in the verbose output.
7. Test the rate limiter: fire 30 rapid requests at `/login` in under a second (`for i in $(seq 30); do curl -s -o /dev/null -w "%{http_code}\n" -k https://localhost/login & done; wait`) and confirm you see a mix of `200`s (within burst) and `429`s (rejected) rather than all 200s.

<details>
<summary>Solution / walkthrough</summary>

```bash
openssl req -x509 -newkey rsa:4096 -keyout /tmp/localhost-key.pem -out /tmp/localhost-cert.pem \
  -days 365 -nodes -subj "/CN=localhost"
```

```nginx
limit_req_zone $binary_remote_addr zone=login_limit:10m rate=5r/s;

upstream backend_pool {
    server 127.0.0.1:8000;
    server 127.0.0.1:8001;
    keepalive 32;
}

server {
    listen 80;
    server_name localhost;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl http2;
    server_name localhost;

    ssl_certificate     /tmp/localhost-cert.pem;
    ssl_certificate_key /tmp/localhost-key.pem;
    ssl_protocols       TLSv1.2 TLSv1.3;
    ssl_ciphers         HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;

    add_header Strict-Transport-Security "max-age=63072000" always;

    location /login {
        limit_req zone=login_limit burst=10 nodelay;
        limit_req_status 429;
        proxy_pass http://backend_pool;
        proxy_set_header X-Forwarded-Proto https;
    }

    location / {
        proxy_pass http://backend_pool;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

```bash
sudo nginx -t && sudo nginx -s reload

curl -vk https://localhost/ 2>&1 | grep -i "SSL connection\|TLS"
# * SSL connection using TLSv1.3 / ...

for i in $(seq 30); do curl -s -o /dev/null -w "%{http_code}\n" -k https://localhost/login & done; wait | sort | uniq -c
#      15 200
#      15 429
```

**Why you see a MIX of 200 and 429, not all-one-or-the-other**: `rate=5r/s` with `burst=10 nodelay` means nginx allows the first ~10 requests through immediately (the burst allowance) even though they arrive faster than 5/s, then starts rejecting with 429 once the burst bucket is empty and the sustained rate is exceeded. This is the token-bucket behavior described in the lesson file — `nodelay` means burst requests are served immediately rather than artificially queued/slowed to match the rate, which is why you get sharp 200→429 behavior instead of requests just getting progressively slower.

`curl -k` is required here only because the cert is self-signed and untrusted by your system's CA store — in real production with a Let's Encrypt cert this flag wouldn't be needed at all.
</details>

---

## Lab 4: Troubleshooting — Diagnosing a 502 Bad Gateway

**Objective:** Practice the actual debugging workflow for the most common nginx production error, rather than just knowing it exists.

**Task:**
1. Deliberately break your Lab 1 config: change `proxy_pass http://127.0.0.1:8000;` to point at a port nothing is listening on (`8999`).
2. Run `sudo nginx -t` — confirm it passes (a wrong upstream port is NOT a syntax error, so `-t` won't catch it).
3. Reload anyway and hit the endpoint with curl — observe the `502 Bad Gateway` response.
4. Check nginx's error log (`/var/log/nginx/error.log` or `docker logs <container>`) and find the specific line explaining WHY — it should mention "connection refused" to the upstream address.
5. Fix it (point back at the real backend port), reload, confirm 200 again.
6. Now reproduce a DIFFERENT 502 cause: start the real backend, but make it take 90 seconds to respond (`time.sleep(90)` in the handler) while `proxy_read_timeout` is set to `5s`. Hit it and observe nginx returns `504 Gateway Timeout` (not 502) — explain the difference between the two error codes based on what you just saw.

<details>
<summary>Solution / walkthrough</summary>

```nginx
location / {
    proxy_pass http://127.0.0.1:8999;   # nothing listens here — deliberately broken
    ...
}
```
```bash
sudo nginx -t
# nginx: configuration file /etc/nginx/nginx.conf test is successful
# (passes! -t only checks SYNTAX, not whether the upstream is reachable)

sudo nginx -s reload
curl -v http://localhost/
# < HTTP/1.1 502 Bad Gateway

tail -20 /var/log/nginx/error.log
# [error] ... connect() failed (61: Connection refused) while connecting to upstream,
# client: 127.0.0.1, server: localhost, request: "GET / HTTP/1.1",
# upstream: "http://127.0.0.1:8999/", host: "localhost"
```

The error log is unambiguous here: `connect() failed (61: Connection refused)` tells you immediately that nginx successfully tried to reach the upstream address and got actively rejected — nothing is listening on that port at all. This is the single most useful debugging step for ANY 502 and is worth checking before anything else, every time.

**Timeout vs refused connection — 504 instead of 502:**
```python
@app.get("/")
def root():
    time.sleep(90)
    return {"ok": True}
```
```nginx
location / {
    proxy_pass http://127.0.0.1:8000;
    proxy_read_timeout 5s;   # deliberately much shorter than the backend's 90s delay
}
```
```bash
curl -v http://localhost/
# < HTTP/1.1 504 Gateway Timeout   (after ~5 seconds, not 90)
```

**502 vs 504, the actual distinction**: 502 means nginx COULD NOT ESTABLISH a connection to the upstream at all (refused, DNS failure, upstream process not running) — nginx never got a chance to wait for a response because there was nothing to talk to. 504 means nginx DID connect successfully, sent the request, and then gave up waiting for a response after `proxy_read_timeout` elapsed — the upstream is alive but too slow. This distinction matters operationally: a spike in 502s points at "is my backend process even running/crashed," while a spike in 504s points at "my backend is up but something is making it slow" (a slow DB query, exhausted connection pool, etc.) — exactly the Senior Tip from the lesson file about setting `proxy_read_timeout` deliberately so a slow backend query surfaces as a clear, fast-failing signal instead of hanging silently.
</details>

---

## Self-Check Checklist

- [ ] Can you write a basic `proxy_pass` reverse-proxy `server` block with all four standard forwarding headers from memory?
- [ ] Can you explain what breaks in the backend if `X-Forwarded-For`/`X-Real-IP` are omitted?
- [ ] Can you write an `upstream` block with `least_conn` and explain when it's a better choice than default round-robin?
- [ ] Can you explain when `ip_hash` would actually backfire (hint: shared corporate NAT)?
- [ ] Can you configure SSL termination with modern `ssl_protocols`/HSTS, and explain what "termination" means for the backend?
- [ ] Can you configure `limit_req_zone` + `limit_req` with `burst` and `nodelay`, and explain what each does to the traffic shape?
- [ ] Can you explain the difference between `nginx -s reload` and a full restart, and why reload is preferred in production?
- [ ] Can you diagnose a 502 using the error log, and state the most likely root cause category (upstream down/unreachable)?
- [ ] Can you explain the difference between a 502 and a 504, and what each implies operationally?
- [ ] Can you explain, unprompted, why Nginx's event-driven model handles high concurrency better than Apache's prefork/worker model for a reverse-proxy role specifically?
