# URL Shortener System Design — TinyURL / Bitly

## Quick Reference Card
```
Core feature  → Long URL → short code → redirect to long URL
Scale         → 100M URLs, 10B redirects/day (read-heavy: 100:1 read:write)
Short code    → 6 chars from [a-zA-Z0-9] = 62^6 = ~56 billion combinations
Key choice    → Hash (MD5/SHA256 + truncate) vs Counter (Base62 encode ID)
DB choice     → NoSQL (DynamoDB/Redis) for key-value lookups — O(1)
Interview hook→ "Base62 counter approach — simple, no collision, predictable length"
```

---

## PART 1: HINGLISH — Samjhne ke liye

### 1.1 Problem Statement

**User story:**
- Input: `https://www.youtube.com/watch?v=dQw4w9WgXcQ&feature=youtu.be&t=0`
- Output: `https://tny.ly/aB3x9k`
- When someone visits `tny.ly/aB3x9k` → Redirect to original URL

**Scale Requirements:**
```
100 million URLs stored
10 billion redirects per day
  = 10B / 86400 seconds
  = ~115,000 redirects per second (115K RPS)

Write: ~100 new URLs per second (much lower)
Read:Write = 100:1 (extreme read heavy!)

Storage:
  1 URL entry = ~500 bytes (URL + metadata)
  100M × 500 bytes = 50GB total (manageable!)
```

---

### 1.2 Key Design Decisions

#### Decision 1: Short Code Generation

**Option A: Hash-based (MD5/SHA256 + truncate)**
```python
import hashlib

def generate_short_code_hash(long_url: str) -> str:
    hash_hex = hashlib.md5(long_url.encode()).hexdigest()  # 32 hex chars
    # Take first 6 chars, convert to base62
    return base62_encode(int(hash_hex[:8], 16))[:6]

PROS:
  Same URL always generates same code → deduplication automatic
  Deterministic — no state needed

CONS:
  Collision risk: Different URLs might generate same 6-char code
  Must handle collisions (check DB, try next 6 chars)
  hash("url1") might equal hash("url2")[:6] — rarely but possible
```

**Option B: Counter-based (Auto-increment ID + Base62 encode)** ← RECOMMENDED
```python
# DB auto-increment: 1, 2, 3, 4, ...
# Base62 encode: 1 → "0000001", 1000000 → "4c92"

BASE62_CHARS = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"

def base62_encode(num: int) -> str:
    if num == 0:
        return BASE62_CHARS[0]
    result = []
    while num > 0:
        result.append(BASE62_CHARS[num % 62])
        num //= 62
    return ''.join(reversed(result)).zfill(6)  # Pad to 6 chars

# ID=1 → "000001", ID=62 → "000010", ID=3844 → "001000"
# 62^6 = 56 billion — enough for 100M URLs with massive room to grow

PROS:
  No collision possible (each ID unique)
  Predictable length
  Simple implementation
  
CONS:
  Sequential codes (ID 1, 2, 3...) → Slightly predictable
  Need atomic counter (race condition if not careful)
  
FIX for predictability: Shuffle/scramble the ID
  scrambled_id = id * PRIME_NUMBER % (62^6)  # Pseudo-random but reversible
  Or: Just use random 6-char code with collision check
```

**Option C: Random 6 chars**
```python
import random, string

def generate_random_code() -> str:
    chars = string.ascii_letters + string.digits  # 62 characters
    return ''.join(random.choices(chars, k=6))
    
# Must check DB for collision
# P(collision) = current_codes / 62^6 = 100M / 56B ≈ 0.18%
# Acceptable but need retry logic
```

---

### 1.3 Data Model

```python
class ShortenedURL:
    """
    Core URL mapping — stored in NoSQL (DynamoDB) or Redis
    """
    short_code: str        # "aB3x9k" — PRIMARY KEY
    long_url: str          # "https://www.youtube.com/..."
    user_id: Optional[int] # Creator (None for anonymous)
    created_at: datetime
    expires_at: Optional[datetime]  # None = never expires
    is_active: bool        # Can be disabled
    click_count: int       # Approximate (eventually consistent)
    custom_alias: bool     # True if user chose the code

class URLClickEvent:
    """
    Analytics events — stored in time-series DB (Cassandra) or data warehouse
    """
    short_code: str
    clicked_at: datetime
    referrer: Optional[str]
    user_agent: str
    ip_hash: str           # Hashed for privacy (not raw IP)
    country: str           # GeoIP lookup
    device_type: str       # mobile/desktop/tablet
```

---

### 1.4 System Components

```
HIGH-LEVEL ARCHITECTURE:

  Client (Browser/App)
        │
        ▼
  Load Balancer (AWS ALB)
        │
   ┌────┴────────────────────────────────┐
   │                                      │
   ▼                                      ▼
URL Creation Service              URL Redirect Service
  (Write API)                       (Read API — HIGH RPS!)
   │                                      │
   ▼                                      ▼
Counter Service                    Redis Cache
(ID generator)                  (short_code → long_url)
   │                                      │
   ▼                              (miss)  ▼
PostgreSQL/DynamoDB ────────────────────► DynamoDB
(Persistent storage)                   (canonical store)
   │
   ▼
Analytics Queue (Kafka/SQS)
   │
   ▼
Analytics DB (Cassandra/BigQuery)

KEY INSIGHT:
  Redirect service is THE bottleneck — 115K RPS
  Solution: Redis cache in front of DB
  Cache hit rate: ~95%+ (popular URLs accessed repeatedly)
  Only 5% requests hit DynamoDB — ~5750 RPS → manageable
```

---

### 1.5 Python Implementation

```python
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional
import hashlib
import redis
import threading

BASE62_CHARS = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"

def base62_encode(num: int, length: int = 6) -> str:
    """Encode integer to base62 string of given length."""
    if num == 0:
        return BASE62_CHARS[0] * length
    result = []
    while num > 0:
        result.append(BASE62_CHARS[num % 62])
        num //= 62
    return ''.join(reversed(result)).zfill(length)

def base62_decode(code: str) -> int:
    """Decode base62 string to integer."""
    result = 0
    for char in code:
        result = result * 62 + BASE62_CHARS.index(char)
    return result


@dataclass
class URLRecord:
    short_code: str
    long_url: str
    user_id: Optional[int]
    created_at: datetime
    expires_at: Optional[datetime]
    is_active: bool
    click_count: int


class AtomicCounter:
    """
    Thread-safe counter for unique ID generation.
    In production: use Redis INCR (atomic, distributed).
    """
    
    def __init__(self, start: int = 1_000_000):
        # Start at 1M to ensure 6-char codes always
        self._value = start
        self._lock = threading.Lock()
        # Production: Use Redis or distributed ID service (Snowflake)
        self._redis = redis.Redis(host='redis', port=6379)
    
    def next(self) -> int:
        """Get next unique ID atomically."""
        # Redis INCR is atomic — safe for distributed systems
        return self._redis.incr('url_counter')


class URLRepository:
    """
    Database abstraction.
    In production: DynamoDB with short_code as partition key.
    """
    
    def __init__(self):
        self._store: dict[str, URLRecord] = {}  # In-memory for demo
        # Production: boto3 DynamoDB client
    
    def save(self, record: URLRecord) -> None:
        self._store[record.short_code] = record
    
    def find_by_code(self, short_code: str) -> Optional[URLRecord]:
        return self._store.get(short_code)
    
    def find_by_long_url(self, long_url: str) -> Optional[URLRecord]:
        """Check if URL already shortened (deduplication)."""
        for record in self._store.values():
            if record.long_url == long_url:
                return record
        return None
    
    def increment_click_count(self, short_code: str) -> None:
        """Update click count — can be async/batched."""
        if short_code in self._store:
            self._store[short_code].click_count += 1


class CacheService:
    """
    Redis cache for fast URL lookups.
    """
    
    def __init__(self):
        self._redis = redis.Redis(host='redis', port=6379, decode_responses=True)
        self.CACHE_TTL = 24 * 3600  # 24 hours
    
    def get(self, short_code: str) -> Optional[str]:
        """Returns long_url or None."""
        return self._redis.get(f"url:{short_code}")
    
    def set(self, short_code: str, long_url: str, ttl: Optional[int] = None) -> None:
        self._redis.setex(f"url:{short_code}", ttl or self.CACHE_TTL, long_url)
    
    def invalidate(self, short_code: str) -> None:
        self._redis.delete(f"url:{short_code}")
    
    def record_click(self, short_code: str) -> None:
        """Approximate click counting — batch flush to DB."""
        self._redis.incr(f"clicks:{short_code}")


class URLShortenerService:
    """
    Core business logic for URL shortening.
    """
    
    def __init__(self):
        self._counter = AtomicCounter()
        self._repo = URLRepository()
        self._cache = CacheService()
        self.BASE_URL = "https://tny.ly/"
    
    def shorten(
        self,
        long_url: str,
        user_id: Optional[int] = None,
        custom_alias: Optional[str] = None,
        ttl_days: Optional[int] = None
    ) -> str:
        """
        Shorten a URL. Returns the short code.
        
        Strategy:
        1. Validate URL
        2. Check for deduplication (same user, same URL → same code)
        3. Generate short code (custom or counter-based)
        4. Store in DB + Cache
        5. Return short URL
        """
        
        # 1. Validate URL
        long_url = self._validate_url(long_url)
        
        # 2. Deduplication — same URL already shortened by this user?
        if user_id:
            existing = self._repo.find_by_long_url(long_url)
            if existing and existing.user_id == user_id:
                return self.BASE_URL + existing.short_code
        
        # 3. Generate short code
        if custom_alias:
            short_code = self._reserve_custom_alias(custom_alias)
        else:
            short_code = self._generate_code()
        
        # 4. Create record
        expires_at = (
            datetime.utcnow() + timedelta(days=ttl_days)
            if ttl_days else None
        )
        
        record = URLRecord(
            short_code=short_code,
            long_url=long_url,
            user_id=user_id,
            created_at=datetime.utcnow(),
            expires_at=expires_at,
            is_active=True,
            click_count=0
        )
        
        # 5. Persist
        self._repo.save(record)
        
        # 6. Cache (warm cache immediately on creation)
        cache_ttl = ttl_days * 86400 if ttl_days else None
        self._cache.set(short_code, long_url, cache_ttl)
        
        return self.BASE_URL + short_code
    
    def redirect(self, short_code: str) -> Optional[str]:
        """
        Resolve short code to long URL.
        Returns None if not found, expired, or inactive.
        
        CRITICAL PATH — must be extremely fast!
        Redis → DB (only on miss)
        """
        
        # 1. Try cache first (fast path — 95% of requests)
        long_url = self._cache.get(short_code)
        if long_url:
            self._record_click_async(short_code)
            return long_url
        
        # 2. Cache miss → DB lookup (slow path — 5% of requests)
        record = self._repo.find_by_code(short_code)
        
        if not record:
            return None  # 404
        
        if not record.is_active:
            return None  # Disabled
        
        if record.expires_at and datetime.utcnow() > record.expires_at:
            self._cache.set(short_code, "EXPIRED", ttl=60)  # Negative cache
            return None  # Expired
        
        # 3. Populate cache (so next request is fast)
        remaining_ttl = None
        if record.expires_at:
            remaining_ttl = int((record.expires_at - datetime.utcnow()).total_seconds())
        
        self._cache.set(short_code, record.long_url, remaining_ttl)
        
        # 4. Record click
        self._record_click_async(short_code)
        
        return record.long_url
    
    def deactivate(self, short_code: str, user_id: int) -> bool:
        """Deactivate a URL. Only owner can deactivate."""
        record = self._repo.find_by_code(short_code)
        if not record or record.user_id != user_id:
            return False
        
        record.is_active = False
        self._repo.save(record)
        self._cache.invalidate(short_code)
        return True
    
    def get_analytics(self, short_code: str) -> dict:
        """Get click analytics for a short URL."""
        record = self._repo.find_by_code(short_code)
        if not record:
            return {}
        
        # Get from Redis (fast, approximate) + DB (accurate)
        redis_clicks = self._get_redis_click_count(short_code)
        
        return {
            "short_code": short_code,
            "long_url": record.long_url,
            "created_at": record.created_at.isoformat(),
            "total_clicks": record.click_count + redis_clicks,
            "is_active": record.is_active,
            "expires_at": record.expires_at.isoformat() if record.expires_at else None,
        }
    
    def _generate_code(self) -> str:
        """Generate unique short code using counter + base62."""
        unique_id = self._counter.next()
        return base62_encode(unique_id, length=6)
    
    def _reserve_custom_alias(self, alias: str) -> str:
        """Reserve custom alias, raise if taken."""
        if not self._is_valid_alias(alias):
            raise ValueError(f"Invalid alias: {alias}")
        
        existing = self._repo.find_by_code(alias)
        if existing:
            raise ValueError(f"Alias '{alias}' is already taken")
        
        return alias
    
    def _is_valid_alias(self, alias: str) -> bool:
        """Alias: 4-16 chars, alphanumeric + hyphens."""
        import re
        return bool(re.match(r'^[a-zA-Z0-9-]{4,16}$', alias))
    
    def _validate_url(self, url: str) -> str:
        """Basic URL validation."""
        from urllib.parse import urlparse
        parsed = urlparse(url)
        if not parsed.scheme in ('http', 'https'):
            raise ValueError(f"Invalid URL scheme: {url}")
        if not parsed.netloc:
            raise ValueError(f"Invalid URL (no domain): {url}")
        
        # Prevent shortening our own short URLs (infinite redirect)
        if 'tny.ly' in parsed.netloc:
            raise ValueError("Cannot shorten already-shortened URLs")
        
        return url
    
    def _record_click_async(self, short_code: str) -> None:
        """Record click asynchronously (don't block the redirect)."""
        # In production: send to Kafka/SQS, consumer updates DB
        # Simple: Redis counter (batch flush to DB hourly)
        self._cache.record_click(short_code)
    
    def _get_redis_click_count(self, short_code: str) -> int:
        """Get click count from Redis (unflushed to DB)."""
        count = self._cache._redis.get(f"clicks:{short_code}")
        return int(count) if count else 0


# Demo usage
if __name__ == "__main__":
    service = URLShortenerService()
    
    # Shorten a URL
    short = service.shorten(
        "https://www.youtube.com/watch?v=dQw4w9WgXcQ&feature=youtu.be",
        user_id=1
    )
    print(f"Shortened: {short}")  # https://tny.ly/000001
    
    # Custom alias
    short2 = service.shorten(
        "https://www.example.com/very/long/path",
        user_id=2,
        custom_alias="my-link"
    )
    print(f"Custom: {short2}")  # https://tny.ly/my-link
    
    # Redirect
    code = short.split("/")[-1]  # "000001"
    long_url = service.redirect(code)
    print(f"Redirects to: {long_url}")
    
    # Analytics
    analytics = service.get_analytics(code)
    print(f"Analytics: {analytics}")
    
    # Same URL → same code (deduplication for same user)
    short3 = service.shorten(
        "https://www.youtube.com/watch?v=dQw4w9WgXcQ&feature=youtu.be",
        user_id=1  # Same user, same URL
    )
    assert short == short3, "Same user + same URL should return same short URL"
    print(f"Dedup works: {short == short3}")
```

---

### 1.6 Scaling Considerations

```
READ SCALING (115K RPS):

1. Redis Cache (Primary optimization):
   - All redirects check Redis first
   - Hot URLs always in cache
   - Cache hit rate: ~95%
   - Redis: 1M+ RPS capable
   - Only 5% → DynamoDB: ~5750 RPS (manageable)

2. Horizontal scaling of redirect service:
   - Stateless — any server handles any redirect
   - AWS Auto Scaling: scale based on CPU/RPS
   - 10 EC2 instances × 12K RPS = 120K RPS total

3. CDN for redirect service?
   - Possible but complex (redirects are dynamic)
   - Popular short codes could be cached at CDN
   - CDN returns 301/302 redirect response

WRITE SCALING (100 URL creations/second):
   - Much lower volume — single DB handles
   - Counter service: Redis INCR (atomic, fast)
   - DynamoDB write: ~1ms latency

DATABASE CHOICE:
  DynamoDB (recommended for this scale):
    - Key-value access (short_code → URL record)
    - Single-digit millisecond reads
    - Auto-scales, managed
    - 40K+ read capacity units by default
  
  Redis (cache layer):
    - <1ms for hot URLs
    - LRU eviction (evict unpopular URLs naturally)
    - 95%+ hit rate
  
  Analytics (separate DB):
    - Click events → Kafka → Cassandra or BigQuery
    - Time-series queries: "clicks per hour for last 30 days"
    - Don't pollute main DB with analytics writes
```

---

### 1.7 Edge Cases

```python
# Edge Case 1: Custom alias conflict
try:
    service.shorten(long_url, custom_alias="popular")
except ValueError as e:
    print(f"Error: {e}")  # "Alias 'popular' is already taken"

# Edge Case 2: Expired URL
# TTL stored in record.expires_at
# Check on redirect: if expired → 410 Gone (not 404)
# 410 Gone = resource permanently unavailable (vs 404 = not found)

# Edge Case 3: URL already shortened
# Don't create duplicate for same user + same URL
# Different users → different codes (user isolation)

# Edge Case 4: Malicious URLs
# Integrate with Google Safe Browsing API
# Check URL on creation, not on redirect
import requests

def check_safe_browsing(url: str) -> bool:
    """Check if URL is safe using Google Safe Browsing API."""
    response = requests.post(
        "https://safebrowsing.googleapis.com/v4/threatMatches:find",
        params={"key": SAFE_BROWSING_API_KEY},
        json={
            "threatInfo": {
                "threatTypes": ["MALWARE", "SOCIAL_ENGINEERING", "PHISHING"],
                "platformTypes": ["ANY_PLATFORM"],
                "threatEntryTypes": ["URL"],
                "threatEntries": [{"url": url}]
            }
        }
    )
    data = response.json()
    return len(data.get('matches', [])) == 0  # True = safe

# Edge Case 5: Very long URLs
# URL max length: 2048 chars (browser limit)
# Store full URL in DB, truncate in logs

# Edge Case 6: Rate limiting
# Anonymous: 10 URLs per day per IP
# Registered: 1000 URLs per day per user
# Check Redis counter before creating
```

---

## PART 2: ENGLISH — Interviewer ko bolne ke liye

### 2.1 System Requirements Summary

```
Functional:
  - Shorten long URL → short code
  - Redirect short code → original URL
  - Custom aliases (optional)
  - URL expiration (optional)
  - Analytics (click count, geo, device)
  - Deactivate URLs

Non-Functional:
  - 100M URLs stored
  - 115K redirects/second
  - <10ms p99 redirect latency
  - 99.99% availability
  - Analytics eventual consistency OK
```

### 2.2 Design Choices and Trade-offs

| Decision | Choice | Reason |
|----------|--------|--------|
| Short code generation | Counter + Base62 | No collision, simple, predictable length |
| Primary storage | DynamoDB | Key-value, single-digit ms, auto-scale |
| Cache | Redis | <1ms lookup, LRU eviction, high hit rate |
| Analytics | Kafka + Cassandra | High-write time-series, separate from main |
| ID distribution | Redis INCR | Atomic, distributed counter |
| Deduplication | User + URL hash | Same user, same URL → same code |

---

### 2.3 Real Project Connection

> "While URL shortener is a classic interview problem I haven't built specifically, the design principles apply directly to systems I've built. The counter + Base62 approach mirrors our booking sequence numbers (monotonically incrementing, human-readable). The Redis cache-first pattern for redirects is identical to our SAP token caching and package listing cache. The 100:1 read-heavy access pattern is similar to our package listing API (many views, few updates). The analytics async write pattern (click events to Kafka, not blocking the redirect) mirrors our Celery async approach for SAP sync."

---

### 2.4 Follow-up Q&A

**Q1: How would you implement 301 vs 302 redirect?**
> "301 (Permanent Redirect): Browser caches the destination URL. Future visits to short URL → browser directly calls original URL (bypasses our server). Pro: No server load for repeat visits. Con: We lose click analytics, and if URL changes, browsers still have the old redirect cached. 302 (Temporary Redirect): Browser doesn't cache. Every visit goes through our server. Pro: We track all clicks, can change destination. Con: Extra server hop always. For analytics purposes, 302 is correct. For bandwidth optimization: 301. Our choice: 302 by default (analytics more valuable than bandwidth), with an option for users to choose 301 for 'set and forget' links."

**Q2: How would you handle the counter service at scale?**
> "Options: (1) Redis INCR — atomic O(1) operation, single Redis node can do 100K+ INCR/second. Suitable for our 100 URL/second write rate. (2) Range-based allocation — central service allocates ranges of IDs (1-1000, 1001-2000...) to URL creation nodes. Each node uses its range locally without Redis coordination. Better for multi-region. (3) Snowflake ID — Twitter's distributed ID generation: 41-bit timestamp + 10-bit machine ID + 12-bit sequence. Globally unique, roughly time-sortable, no central coordinator. For URL shortener at our scale, Redis INCR is simplest. At Twitter/TinyURL scale, Snowflake or ZooKeeper-based range allocation."

**Q3: How do you prevent abuse (spam URLs)?**
> "Multi-layer defense: (1) Rate limiting by IP: Redis counter, 10 free URL creations per day per IP, 429 if exceeded. (2) Google Safe Browsing API check on creation — reject malware/phishing URLs. (3) CAPTCHA for anonymous users after first few creates. (4) Account suspension for users repeatedly creating spam. (5) Hash-based deduplication — same malicious URL created by different accounts = same short code, easier to block. (6) URL blacklist: periodically check all active URLs against updated threat databases. (7) DMCA/legal takedown: ability to instantly deactivate specific short codes."

---

## Interview Cheat Sheet

```
URL Shortener — Key Numbers:
  62^6 = 56 billion possible codes
  6 chars = [a-zA-Z0-9]
  Read:Write = 100:1

Core algorithm:
  ID counter (Redis INCR) → Base62 encode → 6-char code
  
  base62_encode(1000000) = "4c92"  # 6 chars
  
Short code options:
  Counter + Base62: No collision, predictable
  Hash + truncate: Dedup by content, collision risk
  Random: Simple, need collision check

Storage:
  DynamoDB: short_code (PK) → URL record
  Redis: Cache for hot URLs (<1ms)
  Cassandra/BigQuery: Analytics events

Redirect flow:
  Request → Redis (hit 95%!) → 302 Redirect
                ↓ miss (5%)
           DynamoDB → populate Redis → 302 Redirect

Key edge cases:
  Custom aliases: Check availability, validate format
  Expiration: Check on redirect, return 410 Gone
  Malicious URLs: Google Safe Browsing API
  Dedup: Same user + URL → same code
  Prevent URL loops: Can't shorten own domain

Scaling for 115K RPS:
  Redis cache: 95% hit rate → 5750 actual DB calls
  Stateless redirect service → horizontal scale easily
  Analytics: Async (Kafka → batch write) → don't slow redirect

301 vs 302:
  301: Browser caches → No analytics, can't change target
  302: Every request hits server → Analytics, mutable
  Default: 302 (analytics important)
```
