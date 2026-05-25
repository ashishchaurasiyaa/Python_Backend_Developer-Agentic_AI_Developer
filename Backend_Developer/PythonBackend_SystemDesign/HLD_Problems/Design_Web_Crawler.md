# Design Web Crawler (Distributed)

---

## 1. Requirements

### Functional
- Crawl the web starting from seed URLs
- Download HTML content of discovered pages
- Extract new URLs from pages and add to crawl queue
- Respect robots.txt (politeness policy)
- Avoid re-crawling the same URL (deduplication)
- Handle crawl freshness (re-crawl pages periodically)
- Crawl at scale: billions of pages

### Non-Functional
- 1 billion pages crawled per month (~400 pages/sec)
- Store ~500 TB of raw HTML
- URL frontier: 10 billion known URLs
- Politeness: max 1 request/domain/sec
- Fault-tolerant: workers crash, queue survives
- Scalable: add workers dynamically

---

## 2. Scale Estimation

| Metric | Calculation | Result |
|--------|-------------|--------|
| Pages/sec | 1B pages ÷ 30 days ÷ 86400 | ~400 pages/sec |
| Average page size | 100 KB HTML + assets | ~100 KB |
| HTML storage | 400 req/s × 100 KB × 86400 × 30 | ~100 TB/month |
| URLs in frontier | 10B unique URLs × 100 bytes | ~1 TB URL frontier |
| DNS lookups | 400 req/s × new domains | ~10 lookups/sec avg |

---

## 3. Architecture

```
Seed URLs
    │
    ▼
┌──────────────┐    ┌─────────────────────────────────────────────────┐
│  URL         │    │              Crawler Workers (100s)              │
│  Frontier    │───▶│  1. Fetch URL from frontier (per-domain bucket) │
│  (Redis/Kafka│    │  2. Check robots.txt + rate limit               │
│   + priority │    │  3. Download HTML                               │
│   queue)     │    │  4. Parse + extract links                       │
└──────────────┘    │  5. Store HTML to S3                            │
        ▲           │  6. Push new URLs to dedup + frontier           │
        │           └─────────────────────────────────────────────────┘
        │                           │
┌───────┴──────┐         ┌──────────▼──────────┐
│  URL Dedup   │         │   Content Store      │
│  (Bloom      │         │   S3 (raw HTML)      │
│   Filter +   │         │   + Elasticsearch    │
│   Redis SET) │         │   (indexed content)  │
└──────────────┘         └─────────────────────┘
```

---

## 4. URL Frontier (Priority Queue)

```python
"""
URL Frontier: manages which URLs to crawl next.
Two-layer structure:
  1. Front queues: priority-based (high-priority domains crawled more often)
  2. Back queues:  per-domain queues (ensures politeness — 1 req/domain/sec)

Politeness: one back queue per domain, with delay between fetches.
Priority: based on PageRank, importance, freshness.
"""

import heapq
import time
from collections import defaultdict
from dataclasses import dataclass, field

@dataclass(order=True)
class URLEntry:
    priority: float        # lower = higher priority
    next_fetch_at: float   # earliest time to fetch (politeness)
    url: str = field(compare=False)
    depth: int = field(compare=False, default=0)


class URLFrontier:
    """
    Per-domain queues with politeness enforcement.
    Global priority ordering across domains.
    """

    POLITENESS_DELAY_SEC = 1.0    # min delay between requests to same domain
    MAX_DEPTH = 10                 # don't crawl deeper than this
    DEFAULT_PRIORITY = 5.0        # higher number = lower priority

    def __init__(self, redis_client):
        self.redis = redis_client
        self.domain_last_fetch: dict[str, float] = {}
        self.priority_queue: list[URLEntry] = []

    def add_url(self, url: str, priority: float = None, depth: int = 0):
        """Add URL to frontier with priority score."""
        if depth > self.MAX_DEPTH:
            return

        domain = self._extract_domain(url)
        if priority is None:
            priority = self._compute_priority(url)

        # Next allowed fetch time (politeness)
        last_fetch = self.domain_last_fetch.get(domain, 0)
        next_fetch = max(time.time(), last_fetch + self.POLITENESS_DELAY_SEC)

        entry = URLEntry(
            priority=priority,
            next_fetch_at=next_fetch,
            url=url,
            depth=depth
        )
        heapq.heappush(self.priority_queue, entry)

        # Also persist to Redis for durability
        self.redis.zadd(f"frontier:{domain}", {url: next_fetch})

    def get_next_url(self) -> URLEntry | None:
        """
        Get highest-priority URL that is ready to be fetched (politeness respected).
        Returns None if no URL is ready yet.
        """
        now = time.time()
        while self.priority_queue:
            entry = self.priority_queue[0]
            if entry.next_fetch_at <= now:
                heapq.heappop(self.priority_queue)
                domain = self._extract_domain(entry.url)
                self.domain_last_fetch[domain] = now
                return entry
            break   # next URL not ready yet (politeness delay)
        return None

    def _extract_domain(self, url: str) -> str:
        from urllib.parse import urlparse
        return urlparse(url).netloc.lower()

    def _compute_priority(self, url: str) -> float:
        """
        Priority based on:
        - Short URLs (root pages): high priority
        - Deep paths: lower priority
        - Known important domains: high priority
        """
        from urllib.parse import urlparse
        parsed = urlparse(url)
        path_depth = len([p for p in parsed.path.split("/") if p])

        HIGH_PRIORITY_DOMAINS = {"wikipedia.org", "bbc.com", "nytimes.com"}
        domain = parsed.netloc.lower()

        if any(hpd in domain for hpd in HIGH_PRIORITY_DOMAINS):
            return 1.0 + path_depth * 0.1
        return 5.0 + path_depth * 0.5
```

---

## 5. URL Deduplication

```python
"""
Problem: Web has ~4.5B indexed pages, and many more URLs.
Links are duplicates (with/without trailing slash, http vs https, etc.)

Two-layer deduplication:
1. Bloom Filter: fast approximate check (no false negatives, small false positive rate)
2. Redis SET / Hash: exact check before adding to frontier

URL normalization before dedup:
- Lowercase scheme + host
- Remove default port (:80, :443)
- Sort query parameters
- Remove fragment (#section)
- Resolve relative URLs
"""

import hashlib
from bitarray import bitarray

class BloomFilter:
    """
    Space-efficient probabilistic dedup structure.
    False positive rate: ~1% with m=10*n bits and k=7 hash functions.
    For 10B URLs: ~12.5 GB memory (vs 800 GB for exact set).
    """

    def __init__(self, capacity: int = 10_000_000, error_rate: float = 0.01):
        import math
        # Calculate optimal m and k
        m = int(-capacity * math.log(error_rate) / (math.log(2) ** 2))
        k = int(m / capacity * math.log(2))
        self.size = m
        self.k = k
        self.bits = bitarray(m)
        self.bits.setall(0)

    def _hashes(self, item: str) -> list[int]:
        hashes = []
        for i in range(self.k):
            h = hashlib.md5(f"{i}:{item}".encode()).hexdigest()
            hashes.append(int(h, 16) % self.size)
        return hashes

    def add(self, item: str):
        for idx in self._hashes(item):
            self.bits[idx] = 1

    def contains(self, item: str) -> bool:
        return all(self.bits[idx] for idx in self._hashes(item))


class URLDeduplicator:
    """Two-layer dedup: Bloom Filter (fast) + Redis (exact)."""

    def __init__(self, redis_client):
        self.redis = redis_client
        self.bloom = BloomFilter(capacity=10_000_000_000, error_rate=0.01)

    def normalize_url(self, url: str) -> str:
        """Canonical form for dedup comparison."""
        from urllib.parse import urlparse, urlunparse, urlencode, parse_qsl
        parsed = urlparse(url.lower().strip())
        # Remove fragment, sort query params
        query = urlencode(sorted(parse_qsl(parsed.query)))
        normalized = urlunparse((
            parsed.scheme,
            parsed.netloc.rstrip(":80").rstrip(":443"),
            parsed.path.rstrip("/") or "/",
            "", query, ""
        ))
        return normalized

    async def is_seen(self, url: str) -> bool:
        """Check if URL has been crawled before."""
        normalized = self.normalize_url(url)

        # Fast check: bloom filter (might have false positives)
        if not self.bloom.contains(normalized):
            return False

        # Exact check: Redis
        url_hash = hashlib.sha256(normalized.encode()).hexdigest()[:16]
        return bool(await self.redis.sismember("crawled_urls", url_hash))

    async def mark_seen(self, url: str):
        """Mark URL as crawled."""
        normalized = self.normalize_url(url)
        self.bloom.add(normalized)
        url_hash = hashlib.sha256(normalized.encode()).hexdigest()[:16]
        await self.redis.sadd("crawled_urls", url_hash)
```

---

## 6. Crawler Worker

```python
"""
Worker: fetches URLs, parses HTML, extracts links, stores content.
Many workers run in parallel (100s to 1000s).
Each worker handles one URL at a time.
"""

import asyncio
import aiohttp
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import time

class RobotsCache:
    """Cache parsed robots.txt per domain."""

    def __init__(self, redis_client):
        self.redis = redis_client

    async def is_allowed(self, url: str, user_agent: str = "MyBot") -> bool:
        from urllib.robotparser import RobotFileParser
        domain = urlparse(url).netloc
        cache_key = f"robots:{domain}"

        cached = await self.redis.get(cache_key)
        if cached:
            robots_text = cached.decode()
        else:
            robots_url = f"https://{domain}/robots.txt"
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(robots_url, timeout=aiohttp.ClientTimeout(total=5)) as r:
                        robots_text = await r.text() if r.status == 200 else ""
            except Exception:
                robots_text = ""
            await self.redis.setex(cache_key, 86400, robots_text)  # 24h cache

        parser = RobotFileParser()
        parser.parse(robots_text.splitlines())
        return parser.can_fetch(user_agent, url)


class CrawlerWorker:
    """
    Async crawler worker — one instance per worker process.
    """

    USER_AGENT = "MyBot/1.0 (+https://mybotinfo.example.com)"
    REQUEST_TIMEOUT = 30
    MAX_CONTENT_LENGTH = 5 * 1024 * 1024   # 5 MB max page size

    def __init__(self, frontier: URLFrontier, dedup: URLDeduplicator,
                 robots: RobotsCache, s3_client, kafka_client):
        self.frontier = frontier
        self.dedup    = dedup
        self.robots   = robots
        self.s3       = s3_client
        self.kafka    = kafka_client

    async def run(self):
        """Main crawl loop — runs indefinitely."""
        async with aiohttp.ClientSession(
            headers={"User-Agent": self.USER_AGENT},
            connector=aiohttp.TCPConnector(limit=100)
        ) as session:
            while True:
                entry = self.frontier.get_next_url()
                if not entry:
                    await asyncio.sleep(0.1)
                    continue

                try:
                    await self.crawl_url(session, entry)
                except Exception as e:
                    await self._log_error(entry.url, str(e))

    async def crawl_url(self, session: aiohttp.ClientSession,
                         entry: URLEntry):
        url = entry.url

        # 1. Check robots.txt
        if not await self.robots.is_allowed(url):
            return

        # 2. Fetch page
        try:
            async with session.get(
                url,
                timeout=aiohttp.ClientTimeout(total=self.REQUEST_TIMEOUT),
                allow_redirects=True,
                max_redirects=5
            ) as response:
                # Only process HTML pages
                content_type = response.headers.get("Content-Type", "")
                if "text/html" not in content_type:
                    return

                content_length = int(response.headers.get("Content-Length", 0))
                if content_length > self.MAX_CONTENT_LENGTH:
                    return

                html = await response.read()
                if len(html) > self.MAX_CONTENT_LENGTH:
                    html = html[:self.MAX_CONTENT_LENGTH]

                final_url = str(response.url)   # after redirects
                status_code = response.status

        except asyncio.TimeoutError:
            await self._log_error(url, "Timeout")
            return
        except aiohttp.ClientError as e:
            await self._log_error(url, str(e))
            return

        # 3. Store HTML to S3
        page_key = self._url_to_s3_key(final_url)
        await self.s3.put_object(
            Bucket="crawler-pages",
            Key=page_key,
            Body=html,
            ContentType="text/html",
            Metadata={
                "url": final_url,
                "crawled_at": str(time.time()),
                "status_code": str(status_code)
            }
        )

        # 4. Parse HTML + extract links
        new_urls = self._extract_links(html.decode("utf-8", errors="ignore"),
                                        final_url)

        # 5. Dedup + add to frontier
        new_count = 0
        for new_url in new_urls:
            if not await self.dedup.is_seen(new_url):
                self.frontier.add_url(new_url, depth=entry.depth + 1)
                await self.dedup.mark_seen(new_url)
                new_count += 1

        # 6. Emit crawl event for downstream processing (indexer)
        await self.kafka.send("crawled_pages", {
            "url":        final_url,
            "s3_key":     page_key,
            "depth":      entry.depth,
            "crawled_at": time.time(),
            "new_urls":   new_count,
            "status":     status_code
        })

    def _extract_links(self, html: str, base_url: str) -> list[str]:
        """Parse all <a href> links from HTML."""
        soup = BeautifulSoup(html, "html.parser")
        links = []
        for tag in soup.find_all("a", href=True):
            href = tag["href"].strip()
            if not href or href.startswith(("#", "javascript:", "mailto:", "tel:")):
                continue
            absolute = urljoin(base_url, href)
            parsed = urlparse(absolute)
            if parsed.scheme in ("http", "https"):
                links.append(absolute)
        return links[:200]   # limit links per page

    def _url_to_s3_key(self, url: str) -> str:
        """Generate S3 key from URL."""
        url_hash = hashlib.sha256(url.encode()).hexdigest()
        return f"pages/{url_hash[:2]}/{url_hash[2:4]}/{url_hash}.html"

    async def _log_error(self, url: str, error: str):
        await self.kafka.send("crawl_errors", {"url": url, "error": error,
                                                "ts": time.time()})
```

---

## 7. Distributed Coordinator

```python
"""
Problem: With 100s of workers and billions of URLs, we need distributed coordination:
1. Partition URL frontier across workers (each worker handles certain domains)
2. Consistent hashing to assign domains to workers
3. Kafka for durable URL queue (survives worker crashes)
"""

import hashlib
import bisect

class CrawlCoordinator:
    """
    Distributes crawl work across workers using consistent hashing on domain.
    """

    def __init__(self, worker_ids: list[str]):
        self.ring: dict[int, str] = {}
        self.sorted_keys: list[int] = []
        for worker_id in worker_ids:
            self.add_worker(worker_id)

    def add_worker(self, worker_id: str, replicas: int = 100):
        for i in range(replicas):
            key = int(hashlib.md5(f"{worker_id}:{i}".encode()).hexdigest(), 16)
            self.ring[key] = worker_id
            bisect.insort(self.sorted_keys, key)

    def remove_worker(self, worker_id: str, replicas: int = 100):
        for i in range(replicas):
            key = int(hashlib.md5(f"{worker_id}:{i}".encode()).hexdigest(), 16)
            del self.ring[key]
            self.sorted_keys.remove(key)

    def get_worker(self, domain: str) -> str:
        """Get responsible worker for a domain."""
        if not self.ring:
            raise RuntimeError("No workers registered")
        key = int(hashlib.md5(domain.encode()).hexdigest(), 16)
        idx = bisect.bisect(self.sorted_keys, key) % len(self.sorted_keys)
        return self.ring[self.sorted_keys[idx]]

    def assign_url(self, url: str) -> str:
        """Assign URL to a worker based on its domain."""
        from urllib.parse import urlparse
        domain = urlparse(url).netloc.lower()
        return self.get_worker(domain)


# Kafka-based URL distribution (production approach)
class KafkaCrawlQueue:
    """
    Use Kafka as the durable URL frontier.
    Partitioned by domain hash → same domain always goes to same worker partition.
    Workers are Kafka consumer group members.
    """

    async def publish_url(self, url: str, priority: int = 5):
        from urllib.parse import urlparse
        domain = urlparse(url).netloc.lower()
        partition_key = hashlib.md5(domain.encode()).hexdigest()

        await self.kafka.send(
            "url_frontier",
            key=partition_key.encode(),   # same domain → same partition
            value={"url": url, "priority": priority, "ts": time.time()}
        )

    async def consume_urls(self, worker_id: str):
        """Worker consumes from its assigned partitions."""
        consumer = self.kafka.consumer("url_frontier",
                                        group_id="crawler_workers")
        async for message in consumer:
            url_data = message.value
            yield url_data["url"], url_data["priority"]
```

---

## 8. Politeness & Rate Limiting

```python
"""
Politeness rules:
1. robots.txt: respect Crawl-delay directive
2. 1 request per domain per second (configurable)
3. Exponential backoff on errors (4xx, 5xx, timeouts)
4. Don't crawl the same domain from multiple workers
"""

class PolitenessPolicy:
    """Per-domain crawl rate control."""

    def __init__(self, redis_client):
        self.redis = redis_client
        self.default_delay = 1.0   # seconds between requests to same domain

    async def can_fetch(self, domain: str) -> bool:
        """Redis-based rate limiter per domain."""
        key = f"rate:{domain}"
        result = await self.redis.set(key, "1",
                                       ex=int(self.default_delay),
                                       nx=True)   # NX = only set if not exists
        return bool(result)

    async def wait_for_domain(self, domain: str):
        """Wait until domain can be fetched (blocking version)."""
        while not await self.can_fetch(domain):
            await asyncio.sleep(0.1)

    async def get_crawl_delay(self, domain: str) -> float:
        """Get crawl delay from robots.txt or default."""
        cached = await self.redis.get(f"crawl_delay:{domain}")
        if cached:
            return float(cached)
        return self.default_delay

    async def handle_error(self, domain: str, status_code: int):
        """Exponential backoff on server errors."""
        if status_code in (429, 503, 504):
            # Back off this domain
            backoff = min(3600, 2 ** await self._get_error_count(domain))
            await self.redis.set(f"backoff:{domain}", "1", ex=backoff)

    async def _get_error_count(self, domain: str) -> int:
        count = await self.redis.get(f"error_count:{domain}")
        return int(count or 0)
```

---

## 9. Failure Scenarios

| Scenario | Solution |
|----------|----------|
| Worker crashes mid-crawl | Kafka offset commit only after successful crawl → auto-retry |
| Domain blocks crawler | Detect via 403/429 → exponential backoff → rotate IP/UA |
| Crawler trap (infinite URLs) | Max depth limit + domain-level URL count cap |
| Duplicate content (mirrors) | Content hash dedup + SimHash for near-duplicate detection |
| DNS poisoning / slow DNS | Local DNS cache + async DNS resolution with timeout |
| Bloom filter false positives | Two-layer dedup (bloom + exact Redis check) |
| S3 write failures | Retry with exponential backoff, dead-letter queue for failed writes |

---

## 10. Interview Questions

**Q1: How to avoid crawling the same page twice?**
> Two-layer dedup: (1) Bloom filter (3-layer hash, 12.5 GB for 10B URLs, 1% false positive rate) for fast in-memory check. (2) Redis SET with SHA-256 URL hash for exact verification. Also: URL normalization (lowercase, sort query params, remove fragment) before dedup. Content hash (SimHash) to detect near-duplicate pages.

**Q2: How to respect politeness without slowing crawl to a crawl?**
> Domain-level queues: each domain has its own queue with a timestamp of when it can next be fetched. Workers pull from "ready" domains only. Consistent hashing ensures one domain is assigned to one worker (no coordination needed for rate limiting). Redis NX key for distributed rate limiting across workers.

**Q3: How does distributed crawling partition work?**
> Consistent hashing by domain: each domain maps to a specific Kafka partition. Workers are consumer group members, each consuming specific partitions. Adding workers: rebalance Kafka partitions. Domains stay on their partition until rebalance. This ensures same domain always goes to same worker → no distributed state for politeness.

**Q4: What is a crawler trap and how to prevent it?**
> Infinite URL generation: calendars (/calendar/2024/01/ → /2024/02/ ...), session IDs (?session=abc123), filter combinations. Prevention: (1) Max depth (e.g., 10 hops from seed). (2) Per-domain URL cap (e.g., max 1M URLs per domain). (3) Detect query parameter patterns and canonicalize. (4) Path normalization to collapse infinite paths.

**Q5: How to prioritize which URLs to crawl?**
> Priority queue with score based on: (1) PageRank of source page (link from high-PR page → high priority). (2) Domain importance (news sites, Wikipedia → high). (3) Freshness (recently modified → re-crawl sooner). (4) Depth (shallower pages → higher priority). Priority queue pre-populated with seed URLs; new discovered URLs get priority based on source page rank.

**Q6: How to handle dynamic content (JavaScript-rendered pages)?**
> Headless browser rendering (Puppeteer/Playwright) for JS-heavy pages. But expensive: 10x slower than simple HTTP fetch. Strategy: two-tier crawl — (1) Fast HTTP crawler for most pages. (2) JS rendering queue for pages detected as needing JS (empty body without JS). Detection: simple HTTP response has < 100 chars of visible text, or known patterns (React root div with no content).
