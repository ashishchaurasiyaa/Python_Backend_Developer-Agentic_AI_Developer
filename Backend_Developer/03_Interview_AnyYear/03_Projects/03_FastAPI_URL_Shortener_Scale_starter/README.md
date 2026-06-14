# URL Shortener at Scale (Bitly-clone) — Starter

Spec: [../03_FastAPI_URL_Shortener_Scale.md](../03_FastAPI_URL_Shortener_Scale.md)

## What to build

Bitly / TinyURL clone: shorten URLs to 7-char base62 codes, redirect with < 50ms p99 latency via aggressive Redis caching, track clicks async via Kafka → Clickhouse analytics pipeline.  Target: 60K RPS redirects, 99.99% availability.

## How to run

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Infrastructure
docker run -d --name pg -e POSTGRES_PASSWORD=dev -p 5432:5432 postgres:16
docker run -d --name redis -p 6379:6379 redis:7
docker run -d --name kafka -p 9092:9092 apache/kafka:3.7.0
docker run -d --name clickhouse -p 8123:8123 clickhouse/clickhouse-server:24

WORKER_ID=0 uvicorn main:app --reload
```

Open http://localhost:8000/docs.  The `/{short_code}` route is the hot path.

## Milestones (from spec)

- **Week 1** — Snowflake ID generator, shorten + redirect endpoints, Redis caching
- **Week 2** — Kafka click event pipeline, Clickhouse schema, analytics API, custom aliases, expiring URLs, password protection
- **Week 3** — Auth + user accounts, API keys, rate limiting, QR codes, malicious URL detection, custom domains

## Key patterns to implement

1. Snowflake ID generation: 41-bit timestamp | 10-bit worker_id | 12-bit sequence → base62 → last 7 chars.
2. Redirect is cache-first: `GET url:{short_code}` from Redis; DB only on miss; warm cache on miss.
3. Click tracking is fire-and-forget (`asyncio.create_task`); never blocks the redirect response.
4. Negative caching: 404 responses cached 60s in Redis to block enumeration attacks.
5. Bloom filter pre-check: reject random short-code scans without hitting DB.
