# Web Servers — Apache Basics
**DevOps Track · Phase 13: Web Servers**

## Quick Concepts

- **Apache HTTP Server (httpd)** = process/thread-based web server, the historical default before Nginx's rise — still common in shared hosting, legacy enterprise, and some PHP-heavy stacks
- **mod_php** = Apache module that embeds the PHP interpreter directly inside each Apache worker process
- **mod_wsgi** = Apache module that embeds a Python WSGI application directly inside Apache worker processes (Django/Flask equivalent of mod_php)
- **mod_proxy / mod_proxy_http** = Apache modules that let Apache act as a reverse proxy, forwarding requests to an app server (like Gunicorn) instead of running the app in-process
- **VirtualHost** = Apache's block for configuring one domain/site, analogous to Nginx's `server {}` block
- **.htaccess** = a per-directory config file Apache reads at request time, allowing config overrides without editing the main config or restarting the server
- **MPM (Multi-Processing Module)** = Apache's concurrency model — `prefork` (process-per-connection), `worker` (threads within processes), `event` (like `worker`, but non-blocking for keep-alive connections)

---

## Why This Matters

```
You will rarely choose Apache greenfield for a new Python service —
Nginx dominates there. But you WILL encounter Apache:
   - legacy enterprise deployments (PHP-heavy orgs, older Java shops)
   - shared hosting environments
   - some CI/CD or on-prem setups where Apache is the org standard
   - interview questions testing whether you understand WHY Nginx
     won the reverse-proxy space (this requires understanding what
     Apache does differently, not just "Nginx is faster")

Knowing Apache's process/thread model vs Nginx's event-driven model
is the actual substance behind "why Nginx for reverse-proxying
Python services" — memorizing that Nginx is "faster" without knowing
why is a shallow answer in an interview.
```

---

## mod_php vs mod_wsgi/mod_proxy for Python Apps

### mod_php (PHP's classic Apache integration)

```apache
LoadModule php_module modules/libphp.so

<FilesMatch \.php$>
    SetHandler application/x-httpd-php
</FilesMatch>
```
Every Apache worker process that handles a PHP request has the PHP interpreter loaded in-process — request comes in, PHP runs inline, response goes out. Simple, but ties PHP's lifecycle tightly to Apache's process model (heavier workers, less flexible scaling of the app layer independent of the web server).

### mod_wsgi — Python's Equivalent, Embedded Mode

```apache
LoadModule wsgi_module modules/mod_wsgi.so

<VirtualHost *:80>
    ServerName api.example.com
    WSGIDaemonProcess myapp python-path=/opt/myapp:/opt/myapp/venv/lib/python3.12/site-packages
    WSGIProcessGroup myapp
    WSGIScriptAlias / /opt/myapp/wsgi.py

    <Directory /opt/myapp>
        Require all granted
    </Directory>
</VirtualHost>
```
`WSGIDaemonProcess` runs the Python app in its own daemon process pool (separate from Apache's own worker processes) — this "daemon mode" is what most production mod_wsgi deployments use, rather than fully embedding Python inside Apache workers, precisely to avoid coupling Python's lifecycle/memory to Apache's.

### mod_proxy — The Nginx-Style Approach (Recommended for Modern Python)

```apache
LoadModule proxy_module modules/mod_proxy.so
LoadModule proxy_http_module modules/mod_proxy_http.so

<VirtualHost *:80>
    ServerName api.example.com

    ProxyPreserveHost On
    ProxyPass        / http://127.0.0.1:8000/
    ProxyPassReverse / http://127.0.0.1:8000/

    RequestHeader set X-Forwarded-Proto "http"
</VirtualHost>
```
Here Apache does exactly what Nginx does in the reverse-proxy examples: the actual Python app runs independently (Gunicorn/Uvicorn), Apache just forwards HTTP to it. This decouples the app's process model entirely from Apache's — **this is the pattern to know**, since it's the only one that shows up in modern deployments still using Apache.

**Practical takeaway**: mod_wsgi embedded/daemon mode was common with older Django deployments; virtually all current Python deployments (regardless of front-end web server) run the app as its own process (Gunicorn/Uvicorn workers) and put a reverse proxy in front — Apache with `mod_proxy` or Nginx with `proxy_pass` are functionally equivalent choices at that point, and Nginx usually wins on resource efficiency and configuration ergonomics.

---

## .htaccess vs Main Config

| | `.htaccess` (per-directory) | Main config (`httpd.conf` / `sites-available/*.conf`) |
|---|---|---|
| Where it lives | Inside the web-served directory itself | Central config files, outside the web root |
| Who can edit it | Anyone with filesystem write access to that directory (e.g., a shared-hosting tenant) | Only server admins |
| Reload required? | No — Apache re-reads it on every request in that directory | Yes — requires `apachectl graceful`/restart |
| Performance cost | Apache checks for `.htaccess` files on every request path component — real overhead at scale | None (parsed once at startup) |
| Typical use | Shared hosting (control without server access), quick per-app URL rewrites | Everything else — VirtualHosts, modules, global tuning |

```apache
# .htaccess example — common in shared PHP hosting or legacy Django/WSGI setups
RewriteEngine On
RewriteCond %{HTTPS} off
RewriteRule ^(.*)$ https://%{HTTP_HOST}%{REQUEST_URI} [L,R=301]

<Files "wsgi.py">
    Require all granted
</Files>
```

**Rule of thumb**: if you control the whole server (which is the norm for backend/DevOps engineers deploying their own services), put everything in the main config with `AllowOverride None` and disable `.htaccess` lookups entirely — it's pure overhead you don't need, and it's a well-known Apache performance footgun at directory depth.

---

## VirtualHost Example — Full Site Config

```apache
<VirtualHost *:80>
    ServerName api.example.com
    ServerAlias www.api.example.com
    DocumentRoot /var/www/api

    ProxyPreserveHost On
    ProxyPass        /static/ !
    ProxyPass        / http://127.0.0.1:8000/
    ProxyPassReverse / http://127.0.0.1:8000/

    Alias /static/ /opt/myapp/static/
    <Directory /opt/myapp/static>
        Require all granted
    </Directory>

    ErrorLog  ${APACHE_LOG_DIR}/api-error.log
    CustomLog ${APACHE_LOG_DIR}/api-access.log combined
</VirtualHost>

<VirtualHost *:443>
    ServerName api.example.com
    DocumentRoot /var/www/api

    SSLEngine on
    SSLCertificateFile      /etc/letsencrypt/live/api.example.com/fullchain.pem
    SSLCertificateKeyFile   /etc/letsencrypt/live/api.example.com/privkey.pem

    ProxyPreserveHost On
    ProxyPass        / http://127.0.0.1:8000/
    ProxyPassReverse / http://127.0.0.1:8000/
    RequestHeader set X-Forwarded-Proto "https"

    ErrorLog  ${APACHE_LOG_DIR}/api-ssl-error.log
    CustomLog ${APACHE_LOG_DIR}/api-ssl-access.log combined
</VirtualHost>
```

```bash
sudo a2ensite api.conf         # enable the site (Debian/Ubuntu)
sudo a2enmod proxy proxy_http ssl headers rewrite
sudo apachectl configtest      # like `nginx -t`
sudo systemctl reload apache2  # graceful reload
```

---

## Apache vs Nginx — Concurrency Model

This is the core "why Nginx dominates for reverse-proxying" answer.

| | Apache (prefork/worker MPM) | Nginx |
|---|---|---|
| Model | Process-per-connection (`prefork`) or thread-per-connection (`worker`) | Event-driven, single-threaded event loop per worker process |
| Concurrency mechanism | OS spawns a process/thread per connection; blocking I/O per connection | `epoll`/`kqueue` — one worker process handles thousands of connections via non-blocking I/O, no thread-per-connection overhead |
| Memory per connection | Higher — each process/thread carries its own stack/overhead (MB-scale per worker) | Very low — connections are just event-loop state (KB-scale) |
| Behavior under high concurrency (C10K) | Degrades — thousands of processes/threads exhausts memory and causes context-switch thrashing | Scales gracefully — this is precisely the problem Nginx was built to solve |
| Best fit | Environments needing per-request process isolation (mod_php's model), `.htaccess`-heavy shared hosting | Reverse proxy, load balancer, static file serving, TLS termination, high-concurrency APIs |
| Newer MPM (`event`) | Apache's `event` MPM narrows this gap for keep-alive connections, but the module ecosystem (mod_php etc.) still assumes blocking-per-request in many deployments | N/A — event-driven from the ground up |

**Why this matters for Python services specifically**: a Python backend behind a reverse proxy needs the proxy to hold open many slow/idle client connections (mobile clients, keep-alive, slow networks) cheaply while a small pool of Gunicorn/Uvicorn workers does the actual CPU work. Nginx's event loop is purpose-built for "hold open 10,000 mostly-idle connections cheaply, forward the active ones to a small backend pool" — exactly the reverse-proxy shape of the problem. Apache's traditional process/thread-per-connection model spends real memory/CPU on every idle connection, which is wasted overhead in this specific role, even though it's a non-issue when Apache is just running mod_php/mod_wsgi directly for lower-concurrency, CPU-bound-per-request workloads.

---

## Senior Tip

```
1. If you inherit an Apache + mod_wsgi deployment, don't rewrite it
   to Nginx on day one just because "Nginx is better." Understand
   whether it's actually a bottleneck first — for many internal or
   low-traffic services, Apache is perfectly adequate.

2. `.htaccess` files are checked on every request for every directory
   in the path — in a directory tree with many `.htaccess` files this
   is real, measurable latency. `AllowOverride None` + main config is
   the performance-conscious choice when you control the server.

3. mod_security (Apache's WAF module) still shows up in enterprise
   environments as a compliance requirement — know that it exists as
   a request-filtering layer, distinct from mod_proxy/mod_wsgi.

4. When migrating Apache -> Nginx, the reverse-proxy config translates
   almost 1:1 in concept (ProxyPass ~= proxy_pass, VirtualHost ~=
   server{}) — the real work is usually in .htaccess rewrite rules,
   which have no direct Nginx equivalent and must be rewritten as
   explicit `location`/`rewrite` blocks.
```

## Interview Angle

**Q: "Why does Nginx handle more concurrent connections than Apache with the same hardware?"**
Nginx uses a single event-driven loop per worker process with non-blocking I/O (`epoll`/`kqueue`) — one worker can juggle thousands of connections because idle/slow connections cost almost nothing (just event-loop bookkeeping). Apache's traditional prefork/worker MPM allocates a process or thread per connection, so memory and context-switching overhead scale linearly with concurrent connections, which becomes the bottleneck at high scale (the classic "C10K problem").

**Q: "You're deploying a new Django app — Apache+mod_wsgi or Nginx+Gunicorn? Why?"**
Nginx+Gunicorn — it decouples the web server (Nginx: TLS, static files, reverse proxy, rate limiting) from the app server (Gunicorn: runs Django in independent worker processes you can scale/restart separately). This is the modern default; mod_wsgi embeds the app in Apache's own process model, which is less flexible for independent scaling and rolling restarts of the app layer.
