# Project 3: URL Shortener at Scale (Bitly-clone)

**Stack:** FastAPI + Postgres + Redis + Kafka + Clickhouse + Cloudflare + Docker + AWS
**Build Time:** 2-3 weeks
**Difficulty:** ⭐⭐⭐⭐ (Scaling challenges, not domain complexity)
**Resume Strength:** ⭐⭐⭐⭐ (Classic high-traffic project)

---

## 1. Project Overview & Business Problem

### What it is
Bitly / TinyURL clone — convert long URLs to short 7-character codes, redirect, track clicks, provide analytics.

### Why build this
- **Scaling showcase:** Read-heavy at 100:1 read-write ratio.
- **Distributed ID generation:** Snowflake / base62 encoding.
- **Caching strategy:** Aggressive Redis caching to handle 100K RPS.
- **Real-time analytics:** Kafka → Clickhouse for click events.
- **Classic interview project:** Often asked in system design rounds.

### Real-world analogues
- Bitly
- TinyURL
- t.co (Twitter)
- goo.gl (deprecated)
- rebrand.ly
- shorturl.at
- Slack's internal URL shortener

---

## 2. Requirements

### Functional
- Shorten any URL → 7-character code.
- Custom aliases (e.g., `/blog-2024`).
- Redirect from short URL to long.
- Click tracking (timestamp, geo, browser).
- Per-URL analytics (graph of clicks over time).
- User accounts (optional; anonymous OK).
- Expiring URLs (1h, 24h, 7d, 30d, never).
- Password-protected URLs.
- Custom domains (paid feature).
- API for programmatic shortening.
- QR code generation.

### Non-Functional
- 100K RPS sustained (peak 500K).
- Read p99 < 50ms (redirect must be fast).
- Write p99 < 200ms.
- 99.99% availability for redirects (your URLs in emails/SMS).
- 100B total URLs storage capacity.
- Real-time analytics (< 1 min delay).
- Globally distributed.

---

## 3. Scale Estimation

| Metric | Calculation | Number |
|---|---|---|
| New URLs/day | 10M | |
| Total URLs after 5 years | 10M × 365 × 5 | ~18B |
| Encoding: base62, 7 chars | 62^7 | ~3.5 trillion (room for growth) |
| Clicks/day | 1B (100:1 read:write) | |
| Reads/sec avg | 1B / 86400 | ~12K/sec |
| Reads/sec peak | 12K × 5 | ~60K/sec |
| Writes/sec | 10M / 86400 | ~120/sec |
| Storage per URL | ~200 bytes | |
| Total storage | 18B × 200 bytes | ~3.6 TB |
| Cache hot URLs | 1% × 18B × 200 | ~36 GB (Redis cluster) |
| Click events/sec | 60K (peak) | |
| Analytics storage | 5B × 100 bytes/event | ~500 GB |

---

## 4. High-Level Architecture

```
                       ┌─────────────────┐
                       │   Cloudflare    │  (CDN + edge cache)
                       └────────┬────────┘
                                │
                       ┌────────▼────────┐
                       │     ALB         │
                       └────────┬────────┘
                                │
       ┌────────────────────────┼────────────────────────┐
       │                        │                        │
   ┌───▼──────┐             ┌───▼──────┐            ┌───▼──────┐
   │ FastAPI  │             │ FastAPI  │            │ FastAPI  │
   │ Instance │             │ Instance │            │ Instance │
   └───┬──────┘             └───┬──────┘            └───┬──────┘
       │                        │                        │
       └────────────────────────┼────────────────────────┘
                                │
            ┌───────────────────┼───────────────────┐
            │                   │                   │
       ┌────▼─────┐       ┌─────▼─────┐       ┌────▼─────┐
       │  Redis   │       │ Postgres  │       │  Kafka   │
       │ Cluster  │       │+ Replicas │       │  Cluster │
       └──────────┘       └───────────┘       └────┬─────┘
                                                    │
                                              ┌─────▼─────┐
                                              │ Click     │
                                              │ Processor │
                                              └─────┬─────┘
                                                    │
                                              ┌─────▼─────┐
                                              │Clickhouse │
                                              │(Analytics)│
                                              └───────────┘
```

---

## 5. Short ID Generation

### Requirements
- 7 characters (base62 = a-z, A-Z, 0-9).
- 62^7 = 3.5 trillion possible IDs.
- Distributed (multiple servers generate without coordination).
- No predictability (don't expose total URL count).

### Approach: Snowflake-style + Base62 Encode

```python
import time
import base64

class SnowflakeID:
    """
    64-bit ID composition:
        1 bit  | reserved
        41 bits | timestamp_ms - EPOCH
        10 bits | worker_id (1024 workers max)
        12 bits | sequence (4096/ms/worker)
    """
    EPOCH = 1704067200000  # 2024-01-01

    def __init__(self, worker_id: int):
        self.worker_id = worker_id & 0x3FF
        self.sequence = 0
        self.last_ts = 0

    def next_id(self) -> int:
        ts = int(time.time() * 1000)
        if ts == self.last_ts:
            self.sequence = (self.sequence + 1) & 0xFFF
            if self.sequence == 0:
                while ts <= self.last_ts:
                    ts = int(time.time() * 1000)
        else:
            self.sequence = 0
        self.last_ts = ts

        return (
            ((ts - self.EPOCH) << 22)
            | (self.worker_id << 12)
            | self.sequence
        )


def to_base62(num: int) -> str:
    chars = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
    if num == 0: return chars[0]
    result = []
    while num > 0:
        result.append(chars[num % 62])
        num //= 62
    return "".join(reversed(result))


snowflake = SnowflakeID(worker_id=int(os.environ.get("WORKER_ID", 0)))

def gen_short_code() -> str:
    snowflake_id = snowflake.next_id()
    code = to_base62(snowflake_id)
    return code[-7:]   # take last 7 chars to keep length consistent
```

### Alternative: Counter + base62 (centralized)

```python
# Counter in Redis (single ID generator)
async def gen_id():
    n = await redis.incr("url_counter")
    return to_base62(n).zfill(7)
```

Simpler but Redis becomes bottleneck. Snowflake is preferred at scale.

### Custom alias (user-defined)

```python
@app.post("/shorten")
async def shorten(req: ShortenRequest, user=Depends(get_user)):
    if req.custom_alias:
        if not re.match(r"^[a-zA-Z0-9-]{3,20}$", req.custom_alias):
            raise HTTPException(400, "Invalid alias format")
        exists = await db.fetch_one("SELECT 1 FROM urls WHERE short_code = $1", req.custom_alias)
        if exists:
            raise HTTPException(409, "Alias taken")
        code = req.custom_alias
    else:
        code = gen_short_code()
    ...
```

---

## 6. Data Model

```sql
-- URLs
CREATE TABLE urls (
    id              BIGSERIAL PRIMARY KEY,
    short_code      TEXT UNIQUE NOT NULL,
    long_url        TEXT NOT NULL,
    user_id         BIGINT,                       -- null for anonymous
    custom_domain   TEXT,                          -- null = default domain
    expires_at      TIMESTAMPTZ,                   -- null = never
    password_hash   TEXT,                          -- null = no password
    metadata        JSONB DEFAULT '{}',
    click_count     BIGINT DEFAULT 0,             -- denormalized counter
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at      TIMESTAMPTZ
);
CREATE UNIQUE INDEX idx_urls_short_code ON urls(short_code) WHERE deleted_at IS NULL;
CREATE INDEX idx_urls_user_created ON urls(user_id, created_at DESC) WHERE user_id IS NOT NULL;
CREATE INDEX idx_urls_expires ON urls(expires_at) WHERE expires_at IS NOT NULL;

-- Users (optional)
CREATE TABLE users (
    id              BIGSERIAL PRIMARY KEY,
    email           TEXT UNIQUE NOT NULL,
    password_hash   TEXT NOT NULL,
    plan            TEXT DEFAULT 'free',           -- 'free', 'pro'
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Custom domains
CREATE TABLE custom_domains (
    domain          TEXT PRIMARY KEY,
    user_id         BIGINT NOT NULL REFERENCES users(id),
    verified        BOOL DEFAULT false,
    verification_token TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- API keys
CREATE TABLE api_keys (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         BIGINT NOT NULL REFERENCES users(id),
    key_hash        TEXT UNIQUE NOT NULL,
    name            TEXT,
    last_used_at    TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Click events (stored in Clickhouse, not Postgres at scale)
-- Schema in Clickhouse:
CREATE TABLE clicks (
    short_code      String,
    timestamp       DateTime,
    ip_hash         String,
    country         LowCardinality(String),
    browser         LowCardinality(String),
    os              LowCardinality(String),
    referer         String,
    is_unique       UInt8
) ENGINE = MergeTree()
PARTITION BY toYYYYMM(timestamp)
ORDER BY (short_code, timestamp);
```

---

## 7. The Redirect Endpoint (Hot Path)

This is the most-hit endpoint. Must be < 50ms.

```python
@app.get("/{short_code}")
async def redirect(short_code: str, request: Request):
    # 1. Check Redis cache first
    cached = await redis.get(f"url:{short_code}")
    if cached:
        url = json.loads(cached)
    else:
        # 2. Check Postgres
        url = await db.fetch_one(
            "SELECT long_url, expires_at, password_hash FROM urls "
            "WHERE short_code = $1 AND deleted_at IS NULL",
            short_code
        )
        if not url:
            raise HTTPException(404, "URL not found")

        # Cache for next 1 hour
        await redis.setex(
            f"url:{short_code}",
            3600,
            json.dumps({
                "long_url": url.long_url,
                "expires_at": url.expires_at.isoformat() if url.expires_at else None,
                "password_hash": url.password_hash
            })
        )

    # 3. Check expiry
    if url.get("expires_at") and datetime.fromisoformat(url["expires_at"]) < datetime.utcnow():
        raise HTTPException(410, "URL expired")

    # 4. Password protection
    if url.get("password_hash"):
        return HTMLResponse(render_password_prompt(short_code))

    # 5. Track click asynchronously (fire and forget to Kafka)
    asyncio.create_task(track_click(short_code, request))

    # 6. Redirect
    return RedirectResponse(url["long_url"], status_code=302)


async def track_click(short_code, request):
    event = {
        "short_code": short_code,
        "timestamp": datetime.utcnow().isoformat(),
        "ip_hash": hashlib.sha256(request.client.host.encode()).hexdigest()[:16],
        "user_agent": request.headers.get("user-agent", ""),
        "referer": request.headers.get("referer", ""),
        "country": await get_country(request.client.host)
    }
    await kafka_producer.send("clicks", event)
```

### Why so fast?
- 99% cache hit ratio → no DB hit.
- Click tracking async → doesn't block redirect.
- Cloudflare can cache redirects at edge (5-min TTL on response).

---

## 8. Caching Strategy

### Redis cluster (32 nodes typical for this scale)

```
url:{short_code} → JSON{long_url, expires_at, password_hash}   (TTL 1h)
hot_urls:zset    → ZADD score=click_count   (LRU eviction candidate)
```

### Cache warming
On URL creation: immediately populate Redis.
```python
await db.execute("INSERT INTO urls ...")
await redis.setex(f"url:{code}", 3600, json.dumps({...}))
```

### Cache invalidation
On URL edit/delete:
```python
await db.execute("UPDATE urls SET ... WHERE short_code = $1", code)
await redis.delete(f"url:{code}")
```

### Negative caching (URL doesn't exist)
404 responses cached in Redis for 60 seconds (lower TTL than positive cache).
```python
await redis.setex(f"url:{code}:notfound", 60, "1")
```
Reduces brute-force scanning load.

### Bloom filter pre-check
Before Postgres query, check Bloom filter "does this URL exist?".

```python
async def url_exists(short_code):
    if not await bloom.contains(short_code):
        return False   # definitely no
    return await db.fetch_one("SELECT 1 FROM urls WHERE short_code = $1", short_code)
```

For random scans (attacker enumerating), Bloom rejects 99% without DB hit.

---

## 9. Click Analytics Pipeline

### Producer (FastAPI fire-and-forget to Kafka)

```python
kafka_producer = AIOKafkaProducer(
    bootstrap_servers="kafka:9092",
    value_serializer=lambda v: json.dumps(v).encode(),
    compression_type="lz4",
    linger_ms=10,
    enable_idempotence=True
)
await kafka_producer.start()

async def track_click(short_code, request):
    await kafka_producer.send("clicks", {...})
```

### Consumer (separate service)

```python
# click_processor.py
import aiokafka

consumer = AIOKafkaConsumer("clicks", group_id="click-processor", ...)

async def process_clicks():
    await consumer.start()
    async for msg in consumer:
        event = json.loads(msg.value)

        # Enrich
        event["country"] = await ip_to_country(event["ip_hash"])
        event["browser"], event["os"] = parse_user_agent(event["user_agent"])
        event["is_unique"] = await is_unique_click(event["short_code"], event["ip_hash"])

        # Insert into Clickhouse (batched)
        await clickhouse_batch.append(event)
        if len(clickhouse_batch) >= 1000:
            await clickhouse.insert("clicks", clickhouse_batch)
            clickhouse_batch.clear()

        # Update counter in Redis (atomic increment)
        await redis.incr(f"clicks:{event['short_code']}")

        # Periodic flush to Postgres (denormalized counter)
        if msg.offset % 10000 == 0:
            await flush_click_counts_to_db()
```

### Why this pipeline?
- **Redirect endpoint never slows down.** Click tracking is async.
- **Kafka absorbs spikes.** Even at 500K clicks/sec, fine.
- **Clickhouse for analytics.** Massive aggregations in milliseconds.
- **Redis for live counters.** Real-time "X clicks total" without DB hit.

---

## 10. Analytics Queries

```sql
-- Top 10 URLs by click count (last 24h)
SELECT short_code, count() AS clicks
FROM clicks
WHERE timestamp > now() - INTERVAL 1 DAY
GROUP BY short_code
ORDER BY clicks DESC
LIMIT 10;

-- Click rate per minute for a specific URL
SELECT toStartOfMinute(timestamp) AS minute, count() AS clicks
FROM clicks
WHERE short_code = 'abc123' AND timestamp > now() - INTERVAL 1 HOUR
GROUP BY minute
ORDER BY minute;

-- Top countries for a URL
SELECT country, count() AS clicks, uniqExact(ip_hash) AS unique_visitors
FROM clicks
WHERE short_code = 'abc123' AND timestamp > now() - INTERVAL 7 DAY
GROUP BY country
ORDER BY clicks DESC
LIMIT 20;

-- Referer breakdown
SELECT referer, count() FROM clicks
WHERE short_code = 'abc123'
GROUP BY referer
ORDER BY count() DESC;

-- HOT path: did anyone in the last minute hit this URL?
-- (Used for "live" dashboards)
SELECT count() FROM clicks
WHERE short_code = 'abc123' AND timestamp > now() - INTERVAL 1 MINUTE;
```

Clickhouse responds in milliseconds even on billions of rows due to columnar storage + partition pruning.

---

## 11. API Design

```
# Public (no auth required)
GET    /{short_code}                    (redirect)
POST   /shorten                          (basic shorten — anon OK)

# Auth required (account features)
POST   /auth/signup
POST   /auth/login
GET    /me/urls                          (list user's URLs)
PATCH  /me/urls/{id}                     (edit)
DELETE /me/urls/{id}                     (delete)
GET    /me/urls/{id}/analytics           (per-URL stats)
GET    /me/urls/{id}/clicks?from=&to=    (raw clicks)
GET    /me/api-keys
POST   /me/api-keys
DELETE /me/api-keys/{id}

# Custom domains (paid)
POST   /me/domains                       (claim domain)
GET    /me/domains/{domain}/verify       (DNS verification)

# QR code
GET    /{short_code}/qr.png              (QR image)
```

### Shorten endpoint

```python
class ShortenRequest(BaseModel):
    long_url: HttpUrl
    custom_alias: str | None = None
    expires_in_hours: int | None = None
    password: str | None = None

@app.post("/shorten")
async def shorten(req: ShortenRequest, user=Depends(optional_auth)):
    # Validate long_url is safe (not malicious)
    if await is_url_blacklisted(req.long_url):
        raise HTTPException(403, "URL not allowed")

    # Generate or use custom code
    if req.custom_alias:
        if not user or user.plan == "free":
            raise HTTPException(402, "Custom alias requires paid plan")
        if await db.fetch_one("SELECT 1 FROM urls WHERE short_code = $1", req.custom_alias):
            raise HTTPException(409, "Alias taken")
        code = req.custom_alias
    else:
        for _ in range(10):
            code = gen_short_code()
            if not await db.fetch_one("SELECT 1 FROM urls WHERE short_code = $1", code):
                break
        else:
            raise HTTPException(500, "Could not generate unique code")

    # Hash password if set
    pwd_hash = None
    if req.password:
        if not user or user.plan == "free":
            raise HTTPException(402, "Password protection requires paid plan")
        pwd_hash = bcrypt.hashpw(req.password.encode(), bcrypt.gensalt()).decode()

    # Calculate expiry
    expires_at = None
    if req.expires_in_hours:
        expires_at = datetime.utcnow() + timedelta(hours=req.expires_in_hours)

    # Insert
    await db.execute(
        "INSERT INTO urls (short_code, long_url, user_id, password_hash, expires_at) "
        "VALUES ($1, $2, $3, $4, $5)",
        code, str(req.long_url), user.id if user else None, pwd_hash, expires_at
    )

    # Warm cache
    await redis.setex(
        f"url:{code}",
        3600,
        json.dumps({"long_url": str(req.long_url), "expires_at": ..., "password_hash": pwd_hash})
    )

    return {
        "short_url": f"https://shrt.ly/{code}",
        "code": code,
        "long_url": str(req.long_url),
        "expires_at": expires_at
    }
```

---

## 12. Rate Limiting

### Per IP (anonymous)
- 100 URLs/hour.
- 10K redirects/hour (prevent abuse).

### Per user
- Free: 1K URLs/month.
- Pro: 100K URLs/month.
- Enterprise: unlimited.

### Per API key
- Configurable per plan.

```python
async def rate_limit(key: str, limit: int, window_sec: int):
    redis_key = f"rl:{key}"
    count = await redis.incr(redis_key)
    if count == 1:
        await redis.expire(redis_key, window_sec)
    if count > limit:
        raise HTTPException(429, "Rate limit exceeded")
```

---

## 13. Security

### Malicious URL detection
```python
BLOCKLIST_PATTERNS = [
    r"\.exe$", r"\.dmg$", r"\.bat$",   # executables
    r"phishing-domains\.txt",          # known phishing
]

async def is_url_blacklisted(url: str) -> bool:
    # Check Google Safe Browsing API
    response = await httpx.post(
        "https://safebrowsing.googleapis.com/v4/threatMatches:find",
        json={"client": {...}, "threatInfo": {...}}
    )
    if response.json().get("matches"):
        return True

    # Check internal blocklist
    domain = urlparse(url).hostname
    if await redis.sismember("url_blocklist", domain):
        return True

    return False
```

### CAPTCHA for anonymous shortening
Prevent bot abuse:
```python
if not user:
    captcha_token = req.captcha_token
    if not await verify_captcha(captcha_token):
        raise HTTPException(400, "CAPTCHA required")
```

### URL preview
Show preview before redirect for un-trusted users:
```python
@app.get("/preview/{code}")
async def preview(code: str):
    url = await get_url(code)
    return {
        "long_url": url.long_url,
        "domain": urlparse(url.long_url).hostname,
        "is_suspicious": await is_suspicious(url.long_url),
        "created_at": url.created_at
    }
```

---

## 14. Custom Domains

For "yourcompany.co/abc123" branded short URLs:

### Setup flow
1. User claims domain: `POST /me/domains { domain: "myco.co" }`.
2. System generates DNS challenge: `TXT _shrtly-verify.myco.co = <token>`.
3. User adds DNS record.
4. System verifies: `dig TXT _shrtly-verify.myco.co`.
5. User CNAMEs `myco.co → shrt.ly`.
6. System serves `myco.co/abc` same as `shrt.ly/abc`.

### Wildcard SSL
Use Let's Encrypt with DNS-01 challenge or Cloudflare for SSL on custom domains.

```python
@app.get("/{short_code}")
async def redirect(short_code: str, request: Request):
    host = request.headers.get("host")
    if host != PRIMARY_DOMAIN:
        # Custom domain: verify it's claimed
        domain = await get_domain(host)
        if not domain or not domain.verified:
            raise HTTPException(404)
    # ... rest of redirect logic
```

---

## 15. QR Code Generation

```python
import qrcode
from io import BytesIO

@app.get("/{short_code}/qr.png")
async def qr_code(short_code: str, size: int = 200):
    url = f"https://shrt.ly/{short_code}"
    qr = qrcode.QRCode(version=1, box_size=10, border=4)
    qr.add_data(url)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")
    img = img.resize((size, size))

    buf = BytesIO()
    img.save(buf, "PNG")
    buf.seek(0)

    return StreamingResponse(buf, media_type="image/png", headers={
        "Cache-Control": "public, max-age=86400, immutable"
    })
```

CDN caches QR codes — generation only happens once per URL.

---

## 16. Deployment

### Docker Compose (Dev)

```yaml
services:
  api:
    build: .
    ports: ["8000:8000"]
    environment:
      DATABASE_URL: postgres://...
      REDIS_URL: redis://redis:6379
      KAFKA_BROKERS: kafka:9092

  click-processor:
    build: .
    command: python -m click_processor

  postgres:
    image: postgres:16

  redis:
    image: redis:7

  kafka:
    image: apache/kafka:3.7.0

  clickhouse:
    image: clickhouse/clickhouse-server:24
    ports: ["8123:8123"]
```

### Production (AWS)

```
                  ┌──────────────┐
                  │  Cloudflare  │
                  └──────┬───────┘
                         │
                  ┌──────▼───────┐
                  │      ALB     │
                  └──────┬───────┘
                         │
       ┌─────────────────┼─────────────────┐
       ▼                 ▼                 ▼
  ┌─────────┐       ┌─────────┐       ┌─────────┐
  │ECS Pod  │  ...  │ECS Pod  │       │ECS Pod  │
  │FastAPI  │       │FastAPI  │       │Click    │
  └────┬────┘       └────┬────┘       │Process  │
       └─────────────────┘             └────┬────┘
                │                            │
        ┌───────┼────────┐                   │
        ▼       ▼        ▼                   ▼
   ┌────────┐ ┌─────────┐ ┌────────┐   ┌──────────┐
   │RDS PG  │ │Elastic  │ │ MSK     │   │ClickHouse│
   │+Replica│ │Cache    │ │(Kafka)  │   │ Cloud    │
   └────────┘ └─────────┘ └─────────┘   └──────────┘
```

### Scaling
- API pods: 20-50 instances behind ALB.
- DB: 1 primary + 3-5 read replicas (for analytics queries).
- Redis: 6-node cluster (3 master + 3 replica).
- Kafka: 3 brokers, 12 partitions on `clicks` topic.

---

## 17. Senior-Level Showcases

### A. Snowflake-based distributed ID generation
"No central counter; each pod generates IDs independently. 4096 IDs/ms/pod."

### B. 99% cache hit ratio
"Redis cluster sized to hold hot URLs. Cache key pattern + TTL designed for redirect-heavy workload."

### C. Async click tracking via Kafka
"Redirect path NEVER blocks on analytics. Kafka absorbs spikes."

### D. Clickhouse for analytics
"Columnar OLAP for billion-row analytics queries in milliseconds."

### E. Edge caching via Cloudflare
"302 redirects cached at edge for 5 minutes. Reduces origin load 10x."

### F. Bloom filter pre-check
"Reject random URL scans without DB hit. Saves resources."

### G. Google Safe Browsing integration
"Prevent malicious URLs from being shortened — protects platform reputation."

### H. Custom domain with auto-SSL
"Customer brings own domain; we serve their branded short URLs with auto-renewed SSL."

### I. Time-series analytics with partition pruning
"Clickhouse partitioned by month; queries on recent data scan only relevant partitions."

### J. Graceful URL expiry
"Periodic cleanup job; expired URLs return 410 Gone (not 404)."

---

## 18. Implementation Roadmap

### Week 1: Core
- [ ] FastAPI scaffold + Postgres.
- [ ] Snowflake ID generator.
- [ ] Shorten + redirect endpoints.
- [ ] Redis caching.
- [ ] Basic dashboard for created URLs.

### Week 2: Analytics + Features
- [ ] Kafka click event pipeline.
- [ ] Clickhouse setup + click events.
- [ ] Click count denormalized in Postgres.
- [ ] Analytics API endpoints.
- [ ] Custom aliases.
- [ ] Expiring URLs.
- [ ] Password protection.

### Week 3: Production
- [ ] Authentication + user accounts.
- [ ] API keys.
- [ ] Rate limiting.
- [ ] QR code generation.
- [ ] Malicious URL detection.
- [ ] Custom domain support.
- [ ] Load test: 50K RPS sustained.
- [ ] Deploy to AWS.

---

## 19. Common Pitfalls & Solutions

### Pitfall 1: Hot key in Redis
**Symptom:** One URL (viral) gets 50K req/sec; Redis CPU spikes.
**Solution:** Cloudflare edge cache absorbs most; or split key (`url:abc:0`, `url:abc:1`).

### Pitfall 2: ID collision under load
**Symptom:** Same code generated twice.
**Solution:** Unique constraint on `short_code` + retry on collision.

### Pitfall 3: Click pipeline backpressure
**Symptom:** Kafka lag grows; clicks lost.
**Solution:** Auto-scale click processor; alert on lag.

### Pitfall 4: Long URL with malicious content
**Symptom:** User shortens phishing URL.
**Solution:** Google Safe Browsing check + community reports + auto-disable.

### Pitfall 5: Database growth
**Symptom:** `urls` table at 1B rows.
**Solution:** Partition by month (id range); cold storage for expired/deleted.

### Pitfall 6: Cache stampede
**Symptom:** Cache expires for hot URL → 100K requests hit DB simultaneously.
**Solution:** Probabilistic early refresh + lock-on-miss.

### Pitfall 7: Reload on expired URL
**Symptom:** Expired URL returns 404; user retries; same response.
**Solution:** Cache negative response (404/410) for 60s.

---

## 20. Performance Benchmarks

| Metric | Target |
|---|---|
| Redirect p50 | < 20ms |
| Redirect p99 | < 50ms |
| Shorten p99 | < 200ms |
| Cache hit ratio | > 95% |
| Sustained RPS | 60K |
| Peak RPS | 200K |
| Click pipeline lag | < 1 min |
| Analytics query (1B rows) | < 500ms |

---

## 21. Load Testing

```python
# Locust
from locust import HttpUser, task, between
import random

class URLUser(HttpUser):
    wait_time = between(0.1, 0.5)

    @task(95)   # 95% redirects
    def redirect(self):
        code = random.choice(["abc123", "xyz789", ...])   # 100 hot codes
        self.client.get(f"/{code}", allow_redirects=False)

    @task(5)    # 5% shortens
    def shorten(self):
        self.client.post("/shorten", json={
            "long_url": f"https://example.com/{random.randint(0, 10000)}"
        })
```

Target: 60K RPS sustained on cluster.

---

## 22. Resume Bullets

- Built a high-throughput URL shortener in FastAPI handling 60K RPS with Snowflake-based distributed ID generation and 99% Redis cache hit ratio.
- Designed async click analytics pipeline (Kafka → Clickhouse) processing 1B+ events/day with < 1 min freshness.
- Implemented edge-cached redirects via Cloudflare with custom-domain support (auto-SSL), achieving p99 redirect latency < 50ms.

---

## 23. Interview Talking Points

- **"How does base62 encoding work and why 7 chars?"** → 62^7 = 3.5T unique codes; short for UX.
- **"How do you avoid ID collisions across multiple servers?"** → Snowflake bits include worker ID.
- **"What if Redis goes down?"** → Fall back to Postgres; performance degrades but service alive.
- **"How do you handle hot URLs (viral)?"** → CDN edge caching; one URL can serve 1M+ RPS from edge.
- **"How do you scale analytics queries on billions of rows?"** → Clickhouse columnar + partition pruning.
- **"Custom domains?"** → DNS verification + automated SSL via Let's Encrypt or Cloudflare.

---

## 24. Stretch Goals

- **Link in bio:** Linktree-style multi-link landing page.
- **A/B testing:** Multiple destinations for one short URL.
- **Branded short URLs:** AI-suggested aliases based on long URL.
- **API rate limits with token bucket:** Per-API-key precise control.
- **Webhook on click:** Notify customer when URL is clicked.
- **GIF preview:** Show video/GIF in preview page.
- **Affiliate link rewriting:** Auto-add affiliate codes.
- **Geo-targeted redirects:** Different destinations by country.
- **Time-based redirects:** Different destinations by time of day.
- **UTM parameter auto-injection.**

---

## 25. Tech Stack Summary

| Layer | Choice | Why |
|---|---|---|
| **API framework** | FastAPI | Async, fast, type-safe |
| **DB** | Postgres | Relational metadata |
| **Cache** | Redis Cluster | 99% cache hit |
| **Queue** | Kafka | Async click events |
| **Analytics** | Clickhouse | Columnar, billions of rows |
| **CDN** | Cloudflare | Edge caching of redirects |
| **Load balancer** | AWS ALB | TLS termination |
| **Container** | Docker + ECS | Standard |
| **Monitoring** | Prometheus + Grafana | Metrics |
| **CI/CD** | GitHub Actions | Standard |

---

## TL;DR

- 7-character base62 short codes via Snowflake IDs.
- Cache-first reads (99% hit) for sub-50ms redirects.
- Async click tracking via Kafka → Clickhouse.
- Cloudflare edge caching multiplies effective throughput 10x.
- Custom domains, password URLs, expiring URLs as features.
- 60K RPS target, 99.99% uptime.
- 2-3 weeks build time.
- **Classic scaling project that demonstrates caching, distributed IDs, and analytics pipelines.**
