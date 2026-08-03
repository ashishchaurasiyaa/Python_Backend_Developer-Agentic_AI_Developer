# Web Servers — Nginx
**DevOps Track · Phase 13: Web Servers**

> Complementary to Backend_Developer/01_Year3-4_Mid/04_DevOps/ (app-deployment angle) — this covers the fuller tool/architecture picture.

## Quick Concepts

- **Nginx** = event-driven, asynchronous web server / reverse proxy / load balancer — handles thousands of concurrent connections per worker with a small memory footprint
- **Reverse Proxy** = Nginx sits in front of your app server(s), forwards client requests to them, returns their response to the client
- **Upstream** = a named group of backend servers Nginx can load-balance across
- **SSL/TLS Termination** = Nginx handles the HTTPS handshake/decryption, forwards plain HTTP to the backend (backend doesn't need certs)
- **proxy_cache** = Nginx stores upstream responses on disk/memory and serves repeat requests without hitting the backend
- **limit_req** = Nginx's token-bucket rate limiter, applied per client key (usually IP)
- **worker_process / worker_connections** = Nginx's concurrency model — N worker processes, each handling up to `worker_connections` concurrent connections via epoll/kqueue (non-blocking I/O)
- **`location` matching priority** = exact match → preferred prefix (`^~`) → regex (in file order) → longest plain prefix — NOT simply top-to-bottom
- **`try_files`** = tries a fallback chain of paths in order, the standard mechanism behind SPA routing (fall back to `index.html`)

---

## Why This Matters

```
Every production Python backend (Django, FastAPI, Flask) sits behind
Nginx or an equivalent (ALB, Envoy) — Gunicorn/Uvicorn are NOT meant
to face the internet directly. Nginx handles:
   - TLS termination (backend never touches cert private keys)
   - Load balancing across multiple app instances
   - Static file serving (way faster than Python serving files)
   - Rate limiting (before a bad request even reaches your app)
   - Caching (reduce backend load for repeat/expensive requests)

A DevOps/backend interview WILL ask you to sketch an nginx.conf from
memory — reverse proxy + upstream + SSL is the baseline expectation.
```

---

## Config Structure and Basic Operations

Before any directive below — where config actually lives, and how you control the running process.

```
/etc/nginx/
├── nginx.conf              # main config — events{}, http{} blocks, includes everything else
├── conf.d/                   # config files here are included automatically
│   └── backend.conf            # (the file the examples below assume)
├── sites-available/             # Debian/Ubuntu convention — every POSSIBLE site config
│   └── api.example.com
└── sites-enabled/                  # SYMLINKS into sites-available — only what's LINKED here
    └── api.example.com -> ../sites-available/api.example.com   # is actually active
```

```bash
sudo ln -s /etc/nginx/sites-available/api.example.com /etc/nginx/sites-enabled/
# enabling a site = symlinking it — disabling = removing the symlink,
# WITHOUT touching the actual config file in sites-available

sudo nginx -t                          # test config syntax — ALWAYS before reload
sudo systemctl reload nginx              # graceful reload — workers finish in-flight
                                            # requests, new workers pick up new config,
                                            # zero dropped connections
sudo nginx -s reload                       # equivalent, direct signal to the master process
sudo nginx -s stop                           # fast shutdown — drops in-flight connections
sudo nginx -s quit                             # graceful shutdown — finishes in-flight first

tail -f /var/log/nginx/access.log          # every request, by default
tail -f /var/log/nginx/error.log             # config errors, upstream failures, worker crashes —
                                                # the first place to look when something's broken
                                                # and access.log shows nothing unusual
```

```nginx
# conf.d/default.conf — catches requests that match NO server_name
server {
    listen 80 default_server;
    server_name _;
    return 444;   # nginx-specific: close connection with no response at all —
                    # the standard way to silently drop traffic from bots
                    # scanning by raw IP instead of a real hostname
}
```

---

## Reverse Proxy — `proxy_pass`

```nginx
# /etc/nginx/conf.d/backend.conf
server {
    listen 80;
    server_name api.example.com;

    location / {
        proxy_pass http://127.0.0.1:8000;

        # Forward real client info to the backend
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # Timeouts — tune for your app's expected response time
        proxy_connect_timeout 5s;
        proxy_read_timeout    60s;
        proxy_send_timeout    60s;
    }
}
```

Without `X-Forwarded-For`/`X-Real-IP`, your app sees every request as coming from `127.0.0.1` (Nginx itself) — this breaks IP-based rate limiting, geo logic, and audit logs in the app layer, so it's not optional in a real deployment.

---

## `location` Block Matching — A Genuinely Common Interview Question

Nginx doesn't evaluate `location` blocks top-to-bottom like a simple if/elif chain — it uses a specific PRIORITY order, regardless of the order they're written in the config file.

```nginx
location = /health {              # 1. EXACT match — highest priority, stops searching immediately
    return 200 "ok";
}

location ^~ /static/ {              # 2. PREFERRED prefix match — if this prefix matches, nginx
    alias /opt/myapp/static/;         # stops here WITHOUT checking any regex locations below,
}                                      # even if a regex would also match

location ~ \.php$ {                     # 3. Case-sensitive REGEX match (~), checked in the
    fastcgi_pass 127.0.0.1:9000;          # ORDER WRITTEN — first matching regex wins
}

location ~* \.(jpg|jpeg|png|gif)$ {        # 4. Case-INsensitive regex (~*)
    expires 30d;
}

location / {                                 # 5. Plain PREFIX match — longest matching
    proxy_pass http://backend_pool;            # prefix wins; this is the catch-all default
}
```

```
Priority order (NOT file order):
  1. Exact match           (location = /path)
  2. Preferred prefix       (location ^~ /path) — if it matches, regex
                              locations are SKIPPED entirely for this request
  3. Regex, in FILE ORDER    (location ~ or ~* ) — first one written that matches wins
  4. Plain prefix, LONGEST    (location /path) — longest matching prefix wins,
     match wins                 not file order

This is why a `location /static/` written ABOVE a `location ~* \.png$`
can still lose to the regex for a request like /static/logo.png — regex
locations (tier 3) outrank plain prefix locations (tier 4) regardless
of where either is written, UNLESS the prefix uses `^~` (tier 2, which
outranks regex entirely). This exact confusion — "I put my location
block first but it's not matching" — is one of the most common real
nginx debugging sessions.
```

### `try_files` — Fallback Chains for Static + SPA Serving

```nginx
location / {
    root /var/www/spa;
    try_files $uri $uri/ /index.html;
    # 1. try the exact URI as a file
    # 2. try it as a DIRECTORY (serves its index file if found)
    # 3. fall back to /index.html — the standard React/Vue/Angular
    #    SPA pattern: let the client-side router handle any path
    #    the server doesn't have a real file for, instead of a 404
}

location /uploads/ {
    root /var/www;
    try_files $uri =404;    # serve the file, or a real 404 if it genuinely doesn't exist
                              # (no fallback — appropriate for user-uploaded content,
                              # unlike the SPA catch-all above)
}
```

---

## Load Balancing — `upstream`

```nginx
upstream backend_pool {
    # Default: round-robin (requests distributed evenly, in order)
    server 10.0.1.10:8000;
    server 10.0.1.11:8000;
    server 10.0.1.12:8000 weight=2;   # gets ~2x the traffic of others
    server 10.0.1.13:8000 backup;     # only used if all above are down

    keepalive 32;   # keep 32 idle connections open to upstream (perf)
}

server {
    listen 80;
    server_name api.example.com;

    location / {
        proxy_pass http://backend_pool;
        proxy_http_version 1.1;
        proxy_set_header Connection "";   # needed for keepalive to upstream
    }
}
```

### Load Balancing Algorithms

| Directive | Behavior | Best for |
|---|---|---|
| (default, none) | Round-robin — requests cycle through servers in order | Stateless services, roughly equal server capacity |
| `least_conn;` | Sends the next request to whichever server has the fewest active connections | Requests with variable processing time (some slow, some fast) |
| `ip_hash;` | Same client IP always hits the same backend (session affinity) | Apps relying on in-memory session state (no shared session store) |
| `hash $request_uri consistent;` | Consistent hashing on a key (e.g., URI) | Cache-friendly routing — same resource always hits the same backend cache |

```nginx
upstream backend_pool {
    least_conn;
    server 10.0.1.10:8000;
    server 10.0.1.11:8000;
}
```

**Health checks**: open-source Nginx passively marks a server down after failed requests (`max_fails=3 fails_timeout=30s` on the `server` line); active health-check probing (hitting a `/health` endpoint proactively) requires Nginx Plus or an external tool — worth knowing this is a real open-source vs paid-tier distinction.

---

## SSL — Termination with Let's Encrypt

```nginx
server {
    listen 80;
    server_name api.example.com;
    # Redirect all HTTP to HTTPS
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl http2;
    server_name api.example.com;

    ssl_certificate     /etc/letsencrypt/live/api.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/api.example.com/privkey.pem;

    ssl_protocols       TLSv1.2 TLSv1.3;
    ssl_ciphers         HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;

    # Session cache — avoid full TLS handshake on every request
    ssl_session_cache   shared:SSL:10m;
    ssl_session_timeout 1h;

    # HSTS — tell browsers to always use HTTPS for this domain
    add_header Strict-Transport-Security "max-age=63072000" always;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header X-Forwarded-Proto https;
    }
}
```

Obtaining/renewing the cert with `certbot`:
```bash
sudo certbot --nginx -d api.example.com
# certbot edits the nginx config in place, sets up auto-renewal via
# a systemd timer / cron entry that runs 'certbot renew' twice daily
sudo certbot renew --dry-run   # verify auto-renewal works
```

This is **SSL termination** — the backend (Gunicorn/Uvicorn on port 8000) never sees TLS at all, it just gets plain HTTP from Nginx over localhost/private network. Simplifies cert management enormously: one place to rotate certs, not one per app instance.

---

## Caching — `proxy_cache`

```nginx
# In the http {} block — defines the cache zone
proxy_cache_path /var/cache/nginx/api_cache
    levels=1:2
    keys_zone=api_cache:10m
    max_size=1g
    inactive=60m
    use_temp_path=off;

server {
    listen 443 ssl;
    server_name api.example.com;

    location /api/products {
        proxy_pass http://backend_pool;
        proxy_cache api_cache;
        proxy_cache_valid 200 10m;      # cache 200 responses for 10 min
        proxy_cache_valid 404 1m;       # cache 404s briefly too
        proxy_cache_use_stale error timeout updating;  # serve stale on backend hiccup

        add_header X-Cache-Status $upstream_cache_status;  # HIT/MISS/BYPASS — great for debugging
    }

    location /api/checkout {
        proxy_pass http://backend_pool;
        proxy_cache off;   # never cache mutating/user-specific endpoints
    }
}
```

`keys_zone=api_cache:10m` reserves 10MB of shared memory for cache **keys/metadata** (not the actual cached bodies, which live on disk under `/var/cache/nginx/api_cache`). `X-Cache-Status` in the response header is the single most useful debugging tool when a cache "isn't working" — you can immediately see HIT vs MISS vs BYPASS vs EXPIRED per request.

Only cache safe, idempotent, non-personalized responses — anything with `Set-Cookie`, auth-dependent content, or side effects must bypass the cache (`proxy_cache off` or `proxy_cache_bypass`).

---

## Gzip Compression

```nginx
# In the http {} block — applies globally unless overridden per-server/location
gzip on;
gzip_types text/plain text/css application/json application/javascript
           text/xml application/xml application/xml+rss text/javascript;
gzip_min_length 1024;      # don't bother compressing tiny responses —
                              # the compression overhead isn't worth it below ~1KB
gzip_comp_level 5;             # 1 (fastest, least compression) to 9 (slowest, most) —
                                  # 5-6 is the common practical middle ground
gzip_vary on;                     # adds "Vary: Accept-Encoding" — tells caches/CDNs
                                     # a compressed and uncompressed version both exist
```

```
Why gzip_types matters: gzip is NOT enabled for every content type by
default even with `gzip on` — already-compressed formats (JPEG, PNG,
MP4, ZIP) get WORSE or negligible results from gzip and waste CPU
trying, so nginx doesn't compress them by default at all; explicitly
list the TEXT-based formats (JSON, JS, CSS, HTML, XML) that actually
benefit. A JSON API response can shrink 70-80%+ with gzip — genuinely
worth the small CPU cost on almost any real API.
```

```bash
curl -H "Accept-Encoding: gzip" -I https://api.example.com/api/products
# look for: Content-Encoding: gzip   in the response headers
```

---

## Rate Limiting — `limit_req`

```nginx
# In http {} block — defines the rate limit zone
# $binary_remote_addr = client IP (binary form, memory-efficient)
# 10m = 10MB zone, enough for ~160,000 tracked IPs
# rate=5r/s = 5 requests/second sustained rate per IP
limit_req_zone $binary_remote_addr zone=login_limit:10m rate=5r/s;
limit_req_zone $binary_remote_addr zone=api_limit:10m rate=20r/s;

server {
    listen 443 ssl;
    server_name api.example.com;

    # Protect a login endpoint from brute-force / credential stuffing
    location /api/auth/login {
        limit_req zone=login_limit burst=10 nodelay;
        limit_req_status 429;
        proxy_pass http://backend_pool;
    }

    # Looser limit for general API traffic
    location /api/ {
        limit_req zone=api_limit burst=40 nodelay;
        proxy_pass http://backend_pool;
    }
}
```

- `rate=5r/s` — sustained average allowed rate per IP
- `burst=10` — allow a burst of up to 10 requests beyond the rate before rejecting, queued/smoothed
- `nodelay` — serve burst requests immediately instead of artificially delaying them to match the rate (without `nodelay`, excess requests are queued and slowed down instead of processed immediately)
- `limit_req_status 429` — return proper `429 Too Many Requests` instead of Nginx's default `503`

This stops a credential-stuffing bot from hammering `/api/auth/login` before it ever reaches your Python app's connection pool — cheaper and faster than rate limiting in application code.

---

## Full Combined Example

```nginx
upstream backend_pool {
    least_conn;
    server 10.0.1.10:8000;
    server 10.0.1.11:8000;
    keepalive 32;
}

limit_req_zone $binary_remote_addr zone=api_limit:10m rate=20r/s;

proxy_cache_path /var/cache/nginx/api_cache levels=1:2
    keys_zone=api_cache:10m max_size=1g inactive=60m use_temp_path=off;

server {
    listen 80;
    server_name api.example.com;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl http2;
    server_name api.example.com;

    ssl_certificate     /etc/letsencrypt/live/api.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/api.example.com/privkey.pem;
    ssl_protocols       TLSv1.2 TLSv1.3;

    location /api/products {
        limit_req zone=api_limit burst=40 nodelay;
        proxy_cache api_cache;
        proxy_cache_valid 200 10m;
        add_header X-Cache-Status $upstream_cache_status;
        proxy_pass http://backend_pool;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    location /static/ {
        alias /opt/myapp/static/;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }
}
```

---

## Senior Tip

```
1. Always set proxy_read_timeout deliberately. The default (60s) can
   silently hide a slow backend query — either fix the query or set
   a timeout that fails fast and surfaces the problem.

2. worker_processes auto; and worker_connections 1024; (or higher)
   in the events {} block control raw concurrency capacity — check
   `ulimit -n` on the host, since worker_connections can't exceed
   the OS file-descriptor limit per process.

3. Never point Nginx directly at a Python dev server (django runserver,
   flask run) in production — those aren't built for concurrent
   connections. Always Nginx -> Gunicorn/Uvicorn -> app.

4. Use `nginx -t` to test config syntax before every reload:
       sudo nginx -t && sudo systemctl reload nginx
   `reload` (not `restart`) does a graceful worker replacement —
   zero dropped connections.

5. Rate limit BEFORE the app, not just in application middleware —
   it protects against connection-pool exhaustion at the app/DB
   layer, which app-level rate limiting can't prevent (the request
   already consumed a worker slot by the time app code runs).
```

## Interview Angle

**Q: "How do you achieve zero-downtime deploys with Nginx in front of multiple app instances?"**
Rolling restart the backend instances one at a time behind the `upstream` block — Nginx's health awareness (passive `max_fails`) routes around an instance that's restarting, or use a deployment orchestrator (K8s rolling update) that only removes a pod from the Service/endpoint list once it fails readiness, so Nginx/the LB never sends traffic to a instance mid-restart.

**Q: "least_conn vs ip_hash — when would ip_hash actually break something?"**
`ip_hash` breaks evenly-distributed load if a large fraction of your traffic comes from behind a single corporate NAT/proxy (many real users, one apparent IP) — all of them pin to one backend, causing hot-spotting. `least_conn` avoids that but sacrifices session affinity, so it requires the app to be stateless or use a shared session store (Redis) rather than in-memory sessions.

---

## Related

- [`02_apache_basics.md`](02_apache_basics.md) — Apache's concurrency model, and why Nginx's event loop wins for reverse-proxy workloads specifically
- [`../03_Networking/03_web_concepts.md`](../03_Networking/03_web_concepts.md) — reverse proxy/CDN/load-balancer concepts this file implements concretely
- [`../17_Caching/01_caching.md`](../17_Caching/01_caching.md) — caching strategy beyond `proxy_cache` (Redis, application-level caching)

**Q: "You wrote `location /static/` above `location ~* \.png$` in your config, expecting the prefix match to win for static PNG files — but the regex location is handling those requests instead. Why?"**
Nginx doesn't evaluate `location` blocks in file order — it uses a fixed priority: exact match, then preferred-prefix (`^~`), then regex matches (in the order written), then plain prefix matches by longest match. A plain prefix location (tier 4) always loses to a regex location (tier 3) regardless of which is written first in the file, unless the prefix is upgraded to `^~` (which jumps it to tier 2, above all regex locations).

**Q: "An API response body is 200KB of JSON, and clients on mobile networks are complaining about slow load times. What's a quick server-side fix that doesn't touch application code?"**
Enable gzip compression (`gzip on;` plus `gzip_types application/json ...;` in the `http{}` block) — a JSON payload typically compresses 70-80%+, since it's repetitive text. Nginx compresses on the fly per response; verify with `curl -H "Accept-Encoding: gzip" -I` and check for `Content-Encoding: gzip` in the response.
