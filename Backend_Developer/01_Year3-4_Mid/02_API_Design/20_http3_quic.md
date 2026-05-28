# API Design — HTTP/3 + QUIC (Modern Transport for Python APIs)
**API Design · Year 3-4 | Senior Backend + Agentic AI**

## Quick Concepts
- **HTTP/3** = HTTP over QUIC (not TCP) — 2022 standardized
- **QUIC** = transport protocol over UDP — built-in TLS 1.3, multiplexed streams
- **vs HTTP/2** = same HTTP semantics, different transport (QUIC, not TCP)
- **Benefits** = 0-RTT connection, no head-of-line blocking, connection migration
- **Use case** = mobile clients, lossy networks, low-latency APIs
- **TLS** = mandatory (encryption built-in)
- **Adoption** = 95%+ browsers, Cloudflare/Google/Meta widely use, Python ecosystem catching up

---

## Why HTTP/3 Matters

```
HTTP/1.1: 1 request per connection (or keep-alive sequential)
HTTP/2:   multiplexed streams over 1 TCP connection
HTTP/3:   multiplexed streams over QUIC (UDP)

Problem with HTTP/2:
TCP head-of-line blocking — if 1 packet drops, ALL streams pause until retransmit

HTTP/3 solution:
QUIC has per-stream flow control — 1 dropped packet only affects 1 stream
```

**Real-world impact:**
- Mobile users on flaky 4G/5G → 20-50% faster page loads
- Users behind NAT → seamless network switch (Wi-Fi → cellular)
- API clients → connection migration without re-handshake

---

## When to Adopt HTTP/3

| Use HTTP/3 | Skip HTTP/3 |
|---|---|
| Mobile-heavy clients | Internal backend-to-backend |
| Global users (high RTT) | Datacenter-local only |
| Real-time apps (gaming, video) | Batch workloads |
| Streaming APIs (LLM, SSE) | Simple CRUD APIs |
| Want 0-RTT for return users | TCP HTTP/2 fast enough |
| CDN already supports it | Behind legacy load balancer |

---

## Interview Questions & Answers

### Q1: HTTP/3 Python server kaise run karte hain (Hypercorn)?

**Answer:** Hypercorn supports HTTP/3 natively (via `aioquic`).

```bash
pip install hypercorn[h3]
pip install fastapi uvicorn
```

**FastAPI app:**
```python
# main.py
from fastapi import FastAPI

app = FastAPI()

@app.get("/")
async def root():
    return {"message": "Hello from HTTP/3!"}

@app.get("/health")
async def health():
    return {"status": "ok"}
```

**Run with Hypercorn:**
```bash
# Generate self-signed cert for testing
openssl req -x509 -newkey rsa:4096 -keyout key.pem -out cert.pem \
  -days 365 -nodes -subj "/CN=localhost"

# Run HTTP/1.1 + HTTP/2 + HTTP/3 simultaneously
hypercorn main:app \
  --bind 0.0.0.0:443 \
  --quic-bind 0.0.0.0:443 \
  --certfile cert.pem \
  --keyfile key.pem \
  --alt-svc 'h3=":443"'
```

**Test with curl:**
```bash
# HTTP/3 (requires curl with HTTP/3 support — built with quiche)
curl --http3 https://localhost:443/

# Or use Cloudflare's curl image
docker run -it --net=host ghcr.io/cloudflare/curl:latest \
  curl --http3 -k https://localhost:443/

# Browser: Chrome shows "h3" in DevTools Network → Protocol column
```

---

### Q2: aioquic — direct QUIC programming?

**Answer:** Low-level control when needed (custom protocols).

```python
import asyncio
from aioquic.asyncio import serve
from aioquic.asyncio.protocol import QuicConnectionProtocol
from aioquic.quic.configuration import QuicConfiguration
from aioquic.quic.events import StreamDataReceived

class EchoServerProtocol(QuicConnectionProtocol):
    def quic_event_received(self, event):
        if isinstance(event, StreamDataReceived):
            data = event.data
            self._quic.send_stream_data(event.stream_id, b"Echo: " + data)

async def main():
    config = QuicConfiguration(
        is_client=False,
        alpn_protocols=["echo"],
    )
    config.load_cert_chain(certfile="cert.pem", keyfile="key.pem")

    await serve(
        host="0.0.0.0",
        port=4433,
        configuration=config,
        create_protocol=EchoServerProtocol,
    )

    await asyncio.Event().wait()  # run forever

asyncio.run(main())
```

**Use case:** Custom non-HTTP protocols (gaming, telemetry, custom RPC).

---

### Q3: Caddy as HTTP/3 reverse proxy (recommended production)?

**Answer:** Caddy enables HTTP/3 by default — easiest production setup.

```caddyfile
# Caddyfile
api.acme.com {
    reverse_proxy fastapi:8000

    # HTTP/3 enabled by default
    # TLS automatic via Let's Encrypt

    # Custom logging
    log {
        output stdout
        format json
    }

    # Headers
    header {
        Strict-Transport-Security "max-age=31536000;"
        X-Content-Type-Options "nosniff"
    }
}
```

```bash
docker run -p 80:80 -p 443:443 -p 443:443/udp \
  -v $PWD/Caddyfile:/etc/caddy/Caddyfile \
  -v caddy_data:/data \
  caddy:2.8
```

**Caddy advantages:**
- HTTP/3 + TLS auto-renewal in 4 lines
- Open source, no vendor lock-in
- HTTP/3 alpn negotiation works out-of-box

---

### Q4: Nginx + HTTP/3 (most common production)?

**Answer:** Nginx 1.25+ supports HTTP/3 (experimental in 1.25, stable 1.27+).

```nginx
# /etc/nginx/sites-enabled/api
server {
    listen 443 ssl;
    listen 443 quic reuseport;          # HTTP/3 on same port
    listen [::]:443 quic reuseport;

    server_name api.acme.com;

    ssl_certificate /etc/ssl/cert.pem;
    ssl_certificate_key /etc/ssl/key.pem;
    ssl_protocols TLSv1.3;               # HTTP/3 requires TLS 1.3

    # Advertise HTTP/3 support
    add_header Alt-Svc 'h3=":443"; ma=86400';

    # HTTP/3-specific
    quic_retry on;                       # mitigate DDoS
    quic_gso on;                         # generic segmentation offload (better perf)

    location / {
        proxy_pass http://fastapi:8000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-Proto https;
        proxy_set_header X-Forwarded-Protocol $http_x_forwarded_protocol;
    }
}
```

**Firewall (UDP for QUIC):**
```bash
# UDP 443 for HTTP/3
sudo ufw allow 443/udp
sudo ufw allow 443/tcp
```

**Verify:**
```bash
curl --http3 -I https://api.acme.com
# HTTP/3 200
# alt-svc: h3=":443"; ma=86400
```

---

### Q5: Cloudflare HTTP/3 (zero-effort upgrade)?

**Answer:** Enable in dashboard — Cloudflare handles HTTP/3 to origin in TCP.

```
Cloudflare Dashboard:
Network → HTTP/3 (with QUIC) → ON
Network → 0-RTT Connection Resumption → ON
Network → gRPC → ON (if using)
```

Architecture:
```
Client ─[HTTP/3]─→ Cloudflare ─[HTTP/2 or HTTP/1.1]─→ Origin (FastAPI)
```

**Benefits:**
- HTTP/3 at edge globally
- Origin stays HTTP/2 (simpler)
- 0-RTT for return visitors
- DDoS protection included

**For LLM streaming over HTTP/3:**
```python
# Important: Cloudflare buffers SSE on lower tiers
# Set explicit headers
@app.post("/chat/stream")
async def stream(req: ChatRequest):
    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "CF-Edge-Disable-Buffering": "1",   # Cloudflare Enterprise
        },
    )
```

---

### Q6: Client side — Python httpx with HTTP/3?

**Answer:** Use `httpx-async-resolver` + `aioquic` (still maturing).

```bash
pip install 'httpx[http2,http3]'
# Or use aiohttp + aiohttp-quic-transport
```

```python
import httpx

# httpx supports HTTP/2; HTTP/3 still beta in 2026
async def fetch():
    async with httpx.AsyncClient(http2=True) as client:
        response = await client.get("https://api.acme.com/")
        print(response.http_version)        # "HTTP/2"
        print(response.json())

# For HTTP/3 specifically, use aiohttp + experimental backend
import aiohttp
from aiohttp_quic_transport import QuicTransport

async def fetch_h3():
    connector = QuicTransport()
    async with aiohttp.ClientSession(connector=connector) as session:
        async with session.get("https://api.acme.com/") as response:
            print(response.version)
            print(await response.text())
```

**Reality check:** Most Python clients use HTTP/2 for now. HTTP/3 client support improving.

---

### Q7: Performance benchmarking HTTP/3 vs HTTP/2?

**Answer:** Use realistic conditions (latency, packet loss).

```bash
# Tool: h2load (from nghttp2-utils) — supports HTTP/2 + HTTP/3
sudo apt install nghttp2-client

# Benchmark HTTP/2
h2load -n 10000 -c 100 -m 10 https://api.acme.com/test

# Benchmark HTTP/3
h2load -n 10000 -c 100 -m 10 --alpn h3 https://api.acme.com/test
```

**Simulate network conditions:**
```bash
# Add 100ms latency + 1% loss (Linux)
sudo tc qdisc add dev eth0 root netem delay 100ms loss 1%

# Run benchmark — HTTP/3 should outperform HTTP/2 significantly

# Cleanup
sudo tc qdisc del dev eth0 root
```

**Typical results (50ms RTT, 0.5% loss):**

| Metric | HTTP/2 | HTTP/3 | Improvement |
|---|---|---|---|
| Page load (10 req) | 850ms | 480ms | 43% |
| TTFB | 150ms | 90ms | 40% |
| API throughput | 8000 req/s | 12000 req/s | 50% |
| Connection migration | None | Seamless | — |

---

### Q8: Common HTTP/3 issues + debugging?

**Answer:** UDP is often blocked; here's how to diagnose.

**Issue 1: UDP 443 blocked by firewall**
```bash
# Test if UDP reaches server
nc -u -z api.acme.com 443

# Use HTTPS upgrade fallback
# Chrome: chrome://flags/#enable-quic
# Force fallback: ?disable_h3 query param

# Check ALPN
openssl s_client -connect api.acme.com:443 -alpn h3,h2,http/1.1
```

**Issue 2: Alt-Svc not set**
```bash
# Server MUST advertise HTTP/3 via Alt-Svc header on first HTTP/2 response
curl -I https://api.acme.com/
# Look for: alt-svc: h3=":443"; ma=86400

# If missing → client never tries HTTP/3
```

**Issue 3: TLS 1.3 not enabled**
```bash
# Verify TLS 1.3 (HTTP/3 requires it)
openssl s_client -connect api.acme.com:443 -tls1_3

# If TLS 1.2 only → HTTP/3 won't negotiate
```

**Issue 4: Load balancer not UDP-aware**
- AWS ALB: only HTTP/2 (HTTP/3 still in preview as of 2026)
- AWS NLB: needs UDP target group + sticky sessions
- GCP Load Balancer: HTTP/3 GA
- Cloudflare: HTTP/3 default

---

## Migration Plan (Existing Service)

```
Phase 1 (Week 1): Enable on CDN
- Cloudflare/Fastly HTTP/3 toggle
- Monitor browser-side metrics

Phase 2 (Week 2-3): Origin support
- Upgrade Nginx to 1.27+ or switch to Caddy
- Listen on UDP 443
- Set Alt-Svc header

Phase 3 (Week 4-5): Mobile clients
- Update iOS/Android HTTP libraries
- A/B test traffic split

Phase 4 (Month 2+): Internal services
- Service mesh that supports HTTP/3 (Cilium has it)
- Backend-to-backend (lower priority)
```

---

## Production Gotchas

| Gotcha | Fix |
|---|---|
| UDP 443 blocked by enterprise firewall | Always have HTTP/2 fallback |
| Cert renewal issues | Use Caddy (auto) or cert-manager |
| Logs missing HTTP/3 requests | Update log format to capture protocol |
| Load balancer drops UDP | Use UDP-aware LB or direct exposure |
| Metrics confuse HTTP/2 + HTTP/3 | Label by protocol in Prometheus |
| Old clients break | Always serve HTTP/1.1 alongside |
| Compression CPU spike | QUIC has built-in stream encryption — no extra |
| Buffer bloat in middleboxes | Test with realistic network conditions |
| 0-RTT replay attacks | Disable for non-idempotent endpoints |
| Connection ID rotation breaks logs | Track session via auth token instead |

---

## Senior-level Checklist

- [ ] HTTP/3 support analysis done (do clients/CDN support it?)
- [ ] Origin server upgraded (Hypercorn, Caddy, or Nginx 1.27+)
- [ ] UDP 443 open in firewalls + LBs
- [ ] TLS 1.3 enabled (mandatory)
- [ ] Alt-Svc header set
- [ ] HTTP/2 fallback works (UDP blocked → still functional)
- [ ] 0-RTT enabled only for safe (idempotent) endpoints
- [ ] Metrics labeled by HTTP version
- [ ] Logs capture HTTP/3 protocol
- [ ] Load balancer is UDP-aware
- [ ] Mobile clients tested
- [ ] Performance benchmarked under packet loss
- [ ] Cert rotation works (TLS 1.3 only)

---

## Related Docs
- `01_rest_best_practices.md` — REST fundamentals
- `17_api_versioning_streaming.md` — streaming patterns
- `00_Year0-2_Junior/06_FastAPI/26_sse_deep.md` — SSE (works over HTTP/3)
- `01_Year3-4_Mid/04_DevOps/02_nginx_deep.md` — Nginx config
- `01_Year3-4_Mid/03_Security/06_cryptography_basics.md` — TLS 1.3

## External References
- HTTP/3 RFC 9114: https://datatracker.ietf.org/doc/html/rfc9114
- QUIC RFC 9000: https://datatracker.ietf.org/doc/html/rfc9000
- aioquic: https://github.com/aiortc/aioquic
- Hypercorn: https://hypercorn.readthedocs.io
- Caddy HTTP/3: https://caddyserver.com/docs/quick-starts/https
- Cloudflare HTTP/3: https://blog.cloudflare.com/http3-the-past-present-and-future
