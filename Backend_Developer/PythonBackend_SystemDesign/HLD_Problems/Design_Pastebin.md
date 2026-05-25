# Design Pastebin / Code Sharing Service

---

## 1. Requirements

### Functional
- User can paste text content, get a shareable short URL.
- Anyone with URL can read.
- Optional expiration (10 min, 1 hour, 1 day, 1 week, 1 month, never).
- Optional privacy (public/unlisted/private with password).
- Syntax highlighting (Python, JS, JSON, ...).
- View count tracking.
- User accounts (optional) — list of pastes.
- Raw view (plain text).
- Diff view between two pastes.

### Non-Functional
- 10M pastes/day, 100M reads/day.
- Read-to-write ratio: 10:1.
- Read p99 < 100ms.
- Write p99 < 300ms.
- Content size: 10 KB avg, 10 MB max.
- 99.9% availability.

---

## 2. Scale Estimation

| Metric | Calc | Number |
|---|---|---|
| Writes/sec | 10M / 86400 | ~120 |
| Reads/sec | 100M / 86400 | ~1200 |
| Peak (5x) | | 6K reads/sec |
| Storage/day | 10M × 10 KB | 100 GB |
| Storage 5yr | 100GB × 1825 | 180 TB |
| URL char space | base62 (a-zA-Z0-9) = 62 chars | |
| 7-char URL space | 62^7 | 3.5 trillion |
| ID space needed (lifetime) | 10M/day × 5yr × 365 | ~18B → 6-char enough, use 7 for buffer |

---

## 3. High-Level Architecture

```
                ┌────────────┐
                │    CDN      │  (caches raw views)
                └─────┬──────┘
                      │
                ┌─────▼──────┐
                │ Load Balancer│
                └─────┬──────┘
                      │
              ┌───────▼────────┐
              │  API Service    │
              └───┬───────┬────┘
                  │       │
        ┌─────────▼─┐  ┌──▼──────┐
        │ ID Service│  │ Storage  │
        │ (KGS)     │  │ Layer    │
        └───────────┘  └────┬─────┘
                            │
                  ┌─────────┼──────────┬────────┐
                  │         │          │        │
              ┌───▼──┐  ┌───▼──┐   ┌───▼───┐  ┌─▼────┐
              │ Redis │  │ Cassandra│ │  S3   │  │Postgres│
              │ (hot) │  │(metadata)│ │(content)│ │(users) │
              └───────┘  └─────────┘ └────────┘  └────────┘
```

---

## 4. ID Generation (Key Generation Service)

### Approach A: Hash-based
```python
import hashlib
def gen_id(content: str, salt: str) -> str:
    h = hashlib.sha256((content + salt).encode()).digest()
    return base62_encode(h[:6])  # 6 bytes → 8 chars
```
**Problem:** Collisions possible. Two same contents → same URL (might be desired or not).

### Approach B: Snowflake → encode

```python
class SnowflakeKGS:
    EPOCH = 1704067200000  # 2024-01-01
    def __init__(self, worker_id: int):
        self.worker_id = worker_id & 0x3FF
        self.seq = 0
        self.last_ts = 0
        self.lock = Lock()

    def next_id(self) -> str:
        with self.lock:
            ts = int(time.time() * 1000)
            if ts == self.last_ts:
                self.seq = (self.seq + 1) & 0xFFF
                if self.seq == 0:
                    while ts <= self.last_ts:
                        ts = int(time.time() * 1000)
            else:
                self.seq = 0
            self.last_ts = ts
            raw = ((ts - self.EPOCH) << 22) | (self.worker_id << 12) | self.seq
            return base62_encode(raw)[-7:]
```

### Approach C: Pre-generated pool (recommended at scale)
- Offline batch generates 1B unique 7-char IDs.
- Stored in DB table `available_ids`.
- API service pulls IDs from this pool (LPOP from Redis queue).

```python
async def get_id():
    return await redis.lpop("id_pool")  # O(1)

# Refilled by a background job when pool < threshold
```

**Pros:** Fast (no compute), guaranteed unique.
**Cons:** Operational overhead, pool can run dry if not monitored.

---

## 5. Data Model

### Postgres (metadata)
```sql
CREATE TABLE pastes (
    id            TEXT PRIMARY KEY,         -- 7-char base62
    user_id       BIGINT NULL,              -- null for anonymous
    title         TEXT,
    language      TEXT,                      -- 'python', 'json', ...
    expires_at    TIMESTAMPTZ NULL,         -- null = never expires
    privacy       TEXT,                      -- 'public', 'unlisted', 'private'
    password_hash TEXT NULL,                  -- bcrypt hash if pwd-protected
    view_count    BIGINT DEFAULT 0,
    size_bytes    INT,
    content_url   TEXT,                       -- S3 URL
    created_at    TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX ON pastes(user_id, created_at DESC);
CREATE INDEX ON pastes(expires_at) WHERE expires_at IS NOT NULL;
```

### S3 (content storage)
```
s3://pastes-content/{prefix-2}/{paste_id}.txt
```
Prefix by first 2 chars to avoid S3 hot partitions (e.g., `s3://pastes/ab/abc1234.txt`).

### Redis (hot cache)
```
paste:{id}        → JSON-encoded metadata + content (TTL 1h)
views:{id}        → counter (flushed to DB periodically)
```

---

## 6. Write Flow

```python
@app.post("/pastes")
async def create_paste(req: CreatePaste, user: User = None):
    # 1. Validate size, language
    if len(req.content) > 10 * 1024 * 1024:
        raise HTTPException(400, "Too large")

    # 2. Get unique ID
    paste_id = await redis.lpop("id_pool")
    if not paste_id:
        paste_id = await fallback_id_generator()

    # 3. Upload content to S3
    s3_key = f"{paste_id[:2]}/{paste_id}.txt"
    await s3.put_object(Bucket="pastes-content", Key=s3_key, Body=req.content)

    # 4. Calculate expires_at
    expires_at = None
    if req.expiry:
        expires_at = now + req.expiry

    # 5. Hash password if set
    pwd_hash = bcrypt.hashpw(req.password.encode(), bcrypt.gensalt()) if req.password else None

    # 6. Persist metadata
    await db.execute("""
        INSERT INTO pastes (id, user_id, title, language, expires_at, privacy,
                           password_hash, size_bytes, content_url)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
    """, paste_id, user.id if user else None, req.title, req.language,
        expires_at, req.privacy, pwd_hash, len(req.content),
        f"s3://pastes-content/{s3_key}")

    return {"id": paste_id, "url": f"https://pastebin.com/{paste_id}"}
```

---

## 7. Read Flow

```python
@app.get("/pastes/{id}")
async def read_paste(id: str, password: str = None):
    # 1. Check Redis cache
    cached = await redis.get(f"paste:{id}")
    if cached:
        paste = json.loads(cached)
    else:
        # 2. Load metadata from DB
        paste = await db.fetch_one("SELECT * FROM pastes WHERE id = %s", id)
        if not paste:
            raise HTTPException(404)

        # 3. Load content from S3
        content = await s3.get_object(Key=paste.content_url)
        paste["content"] = content

        # 4. Cache for next reads
        await redis.set(f"paste:{id}", json.dumps(paste), ex=3600)

    # 5. Auth check
    if paste["expires_at"] and paste["expires_at"] < now:
        raise HTTPException(404)
    if paste["privacy"] == "private" and not verify_pwd(password, paste["password_hash"]):
        raise HTTPException(401)

    # 6. Increment views (async, buffered)
    await redis.incr(f"views:{id}")

    return paste
```

---

## 8. CDN Strategy

Pastes are immutable after creation. Perfect for CDN caching.

```
Headers:
  Cache-Control: public, max-age=86400, immutable
  ETag: <paste_id>
```

CDN keeps raw views cached for 24h. Origin only hit if cache miss or expired.

**Cache invalidation:** Pastes immutable → no invalidation needed. If user deletes, purge by tag.

---

## 9. Expiration / Cleanup

### Lazy expiration (preferred)
On read, check `expires_at`. If expired, return 404 + delete async.

### Background cleanup
```python
async def cleanup_expired_pastes():
    while True:
        expired_ids = await db.fetch("""
            SELECT id, content_url FROM pastes
            WHERE expires_at IS NOT NULL AND expires_at < now()
            LIMIT 1000
        """)
        for row in expired_ids:
            await s3.delete_object(Key=parse_s3_key(row.content_url))
            await db.execute("DELETE FROM pastes WHERE id = %s", row.id)
            await redis.delete(f"paste:{row.id}")
        await asyncio.sleep(60)
```

Use Postgres index on `expires_at WHERE expires_at IS NOT NULL` for efficient sweep.

---

## 10. Syntax Highlighting

### Server-side (preferred for SEO)
Use Pygments or Prism on server:
```python
from pygments import highlight
from pygments.lexers import get_lexer_by_name
from pygments.formatters import HtmlFormatter

def render_paste(content, lang):
    lexer = get_lexer_by_name(lang)
    return highlight(content, lexer, HtmlFormatter())
```

Cache the rendered HTML in Redis to avoid re-highlighting.

### Client-side (preferred for interactivity)
Send raw text + language; client uses highlight.js. Lower server CPU.

**Hybrid:** Server-render once, cache, serve HTML for first paint.

---

## 11. Search

Optional feature; useful for user's own pastes.

```python
# Elasticsearch index
PUT /pastes/_doc/{id}
{
  "title": "...",
  "content": "...",      # full text indexed
  "language": "python",
  "user_id": 42,
  "created_at": "..."
}
```

For public/private separation, filter by user_id at query time.

---

## 12. Anonymous vs Authenticated

### Anonymous
- IP-rate-limited (10 pastes/hour).
- No user dashboard.
- Can set expiration but max 30 days.

### Authenticated
- 100 pastes/hour.
- Dashboard with paste history.
- Permanent pastes allowed.
- Private + password-protected.
- Can edit/delete own pastes.

### Rate limiting
```python
async def rate_limit_check(identifier: str, limit: int = 10, window: int = 3600):
    key = f"rl:paste:{identifier}"
    count = await redis.incr(key)
    if count == 1:
        await redis.expire(key, window)
    if count > limit:
        raise HTTPException(429, "Rate limit exceeded")
```

---

## 13. Security & Abuse

### Content moderation
- Scan for: malware code, doxxing PII (emails, phone numbers, credit cards).
- ML classifier for offensive content.
- DMCA reporting endpoint.

### Anti-spam
- CAPTCHA for anonymous users.
- IP reputation check.
- Honeypot fields.

### Privacy / Encryption
- Optional end-to-end (client-side AES encryption before upload).
- Password decryption client-side.

### Abuse signals
- Same content uploaded 100x → likely spam.
- Velocity check.

---

## 14. View Count

Naive: `UPDATE pastes SET view_count = view_count + 1 WHERE id = ?` per view.
Problem: contention on popular pastes.

### Solution
- Increment Redis counter (`INCR views:{id}`).
- Periodic job flushes to DB every 60s.

```python
async def flush_view_counts():
    keys = await redis.keys("views:*")
    pipe = redis.pipeline()
    for key in keys:
        pipe.get(key)
        pipe.delete(key)
    results = await pipe.execute()
    # batch update DB
    for key, count in zip(keys[::2], results[::2]):
        paste_id = key.split(":")[1]
        await db.execute("UPDATE pastes SET view_count = view_count + %s WHERE id = %s", count, paste_id)
```

---

## 15. Diff View

User-provided two paste IDs → return unified diff.

```python
import difflib
async def diff_pastes(id1, id2):
    a = await fetch_content(id1)
    b = await fetch_content(id2)
    return list(difflib.unified_diff(a.splitlines(), b.splitlines()))
```

Cache result (immutable inputs).

---

## 16. APIs

```
POST   /pastes                    # create
GET    /pastes/{id}               # read (with optional password)
GET    /pastes/{id}/raw           # raw text only
DELETE /pastes/{id}               # owner only
GET    /users/me/pastes           # list
GET    /pastes/{a}/diff/{b}       # diff
```

---

## 17. Trade-offs

| Decision | Trade-off |
|---|---|
| ID pool vs gen-on-write | Pool: faster but needs ops; Gen: simpler but lock contention |
| S3 for content | Cheap, scalable; slight read latency vs DB |
| CDN cache | Drastically reduces origin load; cold reads slow |
| Lazy expiration | No background process; expired pastes linger till read |
| Async view counts | Eventual; cleaner DB writes |
| 7-char IDs | Trillions of pastes possible; longer URLs |

---

## 18. Follow-up Questions

- **"What if 2 pastes get the same content?"** → Optional dedup via content hash → reuse existing paste (storage savings, but loses per-paste analytics).
- **"How to handle 10 MB pastes?"** → Stream upload to S3, chunked GET on read, gzip-encoded transfer.
- **"How to prevent paste enumeration (scrape all pastes)?"** → 7-char base62 space is large enough (3.5T); but use private flag for sensitive content, password protection for very sensitive.
- **"Custom URLs (vanity)?"** → Reserve namespace, charge premium. Store in separate `vanity_urls` table with unique constraint.
- **"Sharing via QR code?"** → API returns QR-encoded URL on demand.
- **"What if S3 outage?"** → Multi-region replication; failover to backup region. Or write to multiple buckets at insert.
