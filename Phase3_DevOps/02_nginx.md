# Nginx — Reverse Proxy, Load Balancing, SSL Termination

## Quick Concepts
- **Nginx** = high-performance web server + reverse proxy
- **Reverse proxy**: client ko nahi pata ki backend kahan hai — Nginx beech mein hota hai
- **Load balancing**: traffic ko multiple backend servers mein distribute karta hai
- **SSL termination**: Nginx HTTPS handle karta hai, backend HTTP se baat karta hai
- **Upstream** = backend servers ka group

---

## Interview Questions & Answers

### Q1: Nginx kya hai aur reverse proxy kaise kaam karta hai?
**Answer:**
Nginx ek web server hai jo:
- Static files serve karta hai (HTML, CSS, JS)
- **Reverse proxy** ke roop mein backend (FastAPI/Django) ke saamne khada hota hai
- **Load balancer** ban ke traffic distribute karta hai
- **SSL termination** karta hai

Reverse proxy flow:
```
Client → HTTPS:443 → Nginx → HTTP:8000 → FastAPI app
```
Client ko sirf Nginx ka IP/domain pata hota hai. Backend ports expose nahi hote.

```nginx
# /etc/nginx/nginx.conf ya /etc/nginx/conf.d/myapp.conf

server {
    listen 80;
    server_name myapp.com www.myapp.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

---

### Q2: Load balancing Nginx mein kaise karte hain?
**Answer:**
`upstream` block mein multiple backend servers define karo:

```nginx
upstream fastapi_backend {
    # Default: round-robin
    server 127.0.0.1:8001;
    server 127.0.0.1:8002;
    server 127.0.0.1:8003;
}

# Weighted (8001 ko zyada traffic)
upstream fastapi_weighted {
    server 127.0.0.1:8001 weight=3;
    server 127.0.0.1:8002 weight=1;
}

# IP Hash (same client → same server — session sticky)
upstream fastapi_sticky {
    ip_hash;
    server 127.0.0.1:8001;
    server 127.0.0.1:8002;
}

# Least connections
upstream fastapi_least {
    least_conn;
    server 127.0.0.1:8001;
    server 127.0.0.1:8002;
}

server {
    listen 80;
    location / {
        proxy_pass http://fastapi_backend;
    }
}
```

---

### Q3: SSL/HTTPS setup kaise karte hain Nginx mein?
**Answer:**
```nginx
# HTTP → HTTPS redirect
server {
    listen 80;
    server_name myapp.com;
    return 301 https://$host$request_uri;
}

# HTTPS server
server {
    listen 443 ssl http2;
    server_name myapp.com;

    ssl_certificate /etc/letsencrypt/live/myapp.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/myapp.com/privkey.pem;

    # Modern SSL settings
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;
    ssl_session_cache shared:SSL:10m;

    # Security headers
    add_header Strict-Transport-Security "max-age=31536000" always;
    add_header X-Frame-Options DENY;
    add_header X-Content-Type-Options nosniff;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-Proto https;
    }
}
```

**Let's Encrypt ke saath (free SSL):**
```bash
certbot --nginx -d myapp.com -d www.myapp.com
```

---

### Q4: Nginx se static files aur media files serve kaise karte hain?
**Answer:**
```nginx
server {
    listen 80;
    server_name myapp.com;

    # Django/FastAPI static files
    location /static/ {
        alias /var/www/myapp/staticfiles/;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }

    # Media/upload files
    location /media/ {
        alias /var/www/myapp/media/;
        expires 7d;
    }

    # API — backend ko bhejo
    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    # Frontend SPA (React/Vue)
    location / {
        root /var/www/myapp/frontend/build;
        try_files $uri $uri/ /index.html;  # SPA routing ke liye
    }
}
```

---

### Q5: WebSocket connections Nginx se kaise proxy karte hain?
**Answer:**
FastAPI/Django Channels ke WebSockets ke liye `Upgrade` headers forward karne padte hain:

```nginx
upstream ws_backend {
    server 127.0.0.1:8000;
}

server {
    listen 80;
    location /ws/ {
        proxy_pass http://ws_backend;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_read_timeout 86400;  # WebSocket timeout — 24 hours
    }
}
```

---

### Q6: Rate limiting Nginx mein kaise karte hain?
**Answer:**
```nginx
# http block mein define karo
http {
    # 10 requests per second per IP allow
    limit_req_zone $binary_remote_addr zone=api_limit:10m rate=10r/s;

    server {
        location /api/ {
            limit_req zone=api_limit burst=20 nodelay;
            limit_req_status 429;
            proxy_pass http://127.0.0.1:8000;
        }
    }
}
```

---

### Q7: Nginx Docker Compose mein kaise integrate karte hain?
**Answer:**
```yaml
# docker-compose.yml
services:
  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx/nginx.conf:/etc/nginx/conf.d/default.conf:ro
      - ./nginx/certs:/etc/nginx/certs:ro
      - static_files:/var/www/static:ro
    depends_on:
      - app

  app:
    build: .
    expose:
      - "8000"      # expose only to internal network, not host
    environment:
      - DATABASE_URL=postgresql://user:pass@db:5432/mydb
```

```nginx
# nginx/nginx.conf
upstream app {
    server app:8000;  # Docker DNS — service name as hostname
}

server {
    listen 80;
    location / {
        proxy_pass http://app;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

---

## Important Commands

```bash
nginx -t                    # config syntax check karo
nginx -s reload             # zero-downtime reload
systemctl status nginx
systemctl restart nginx

# Logs
tail -f /var/log/nginx/access.log
tail -f /var/log/nginx/error.log
```
