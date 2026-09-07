# URL Shortener at Scale (Bitly-clone)

Spec: [../03_FastAPI_URL_Shortener_Scale.md](../03_FastAPI_URL_Shortener_Scale.md)

## Status — verified, not assumed

The original file here was a TODO scaffold (a bare `main.py`, no models, no
tests). It's now a working core implementation — built, containerized, and
checked live against a real Postgres + Redis, not just "should work."

| Area | What's real | Verified how |
|---|---|---|
| Snowflake IDs → base62 | 64-bit `timestamp\|worker_id\|sequence` packing ([`app/shortcode.py`](app/shortcode.py)) | Standalone script: 5 rapid `next_id()` calls all unique, full base62 round-trip correct |
| Auth | Signup/login, JWT (`python-jose`), `bcrypt` password hashing ([`app/routers/auth.py`](app/routers/auth.py)) | `pytest tests/test_auth.py` — 5/5 passing against live Postgres |
| Shorten | Anonymous + authenticated, custom alias (auth-gated), collision-retry on generated codes ([`app/routers/shorten.py`](app/routers/shorten.py)) | `pytest tests/test_shorten.py` — 6/6 passing |
| Redirect (hot path) | Redis cache-aside, Postgres fallback, expiry (410), password-protected URLs, fire-and-forget click tracking, real QR PNG ([`app/routers/redirect.py`](app/routers/redirect.py)) | `pytest tests/test_redirect.py` — 7/7 passing, incl. checking real PNG magic bytes |
| Rate limiting | Redis sorted-set sliding window, differentiated anon (5/min) vs authenticated (60/min) ([`app/deps.py`](app/deps.py)) | `pytest tests/test_rate_limit.py` — 2/2 passing, confirms exact cutoff (5th request 200, 6th/7th 429) |
| Docker | Multi-stage build, non-root user, healthcheck, docker-compose with dependent healthchecks | `docker compose up -d --build` → all 3 services report `healthy`; manually curled every endpoint above against the live stack before writing tests |

**20/20 tests passing.** Run them yourself:

```bash
docker compose up -d
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m pytest tests/ -v
```

## What's deliberately deferred (stretch goals, not gaps)

The full spec targets 60K RPS / 99.99% availability at Bitly's scale. This
starter builds the part that demonstrates the architecture decisions — it
does not chase the scale numbers. Left out on purpose:

- **Kafka click-event pipeline + Clickhouse analytics** — click tracking here
  is a fire-and-forget denormalized counter (`URL.click_count`) written via
  its own DB session, not a streamed event. Real analytics (clicks by
  geo/referrer/time-bucket) would sit on top of a Kafka→Clickhouse pipeline;
  `requirements.txt` deliberately drops `aiokafka` with a comment explaining
  why.
- **Custom domains + SSL** — `custom_domain` exists as a nullable column on
  `URL` but there's no domain-verification or cert-provisioning flow.
- **CAPTCHA / bot detection on shorten** — anonymous rate limiting is the
  only anti-abuse control; no CAPTCHA challenge.
- **Malicious URL detection (Google Safe Browsing)** — not integrated; a
  malicious long_url is accepted and shortened like any other.
- **Edge caching / Cloudflare** — the Redis cache-aside layer is the only
  cache; no CDN/edge tier.
- **Alembic migrations** — schema is created via `Base.metadata.create_all`
  at startup (see the docstring in [`app/db.py`](app/db.py)). Fine for a
  single-instance starter; a real deployment needs real migrations.

## Architecture notes worth knowing for an interview

- **Route registration order matters.** `redirect.router` owns the catch-all
  `GET /{short_code}` and is registered *last* in
  [`app/main.py`](app/main.py) — Starlette matches routes in declaration
  order, so a dynamic single-segment route registered earlier would swallow
  `/health`, `/auth/*`, etc.
- **No code truncation.** The original scaffold's `main.py` truncated the
  base62 Snowflake ID to its last 7 characters. That throws away the
  high-order (timestamp) bits and shrinks effective uniqueness to ~42 bits —
  a latent collision bug that gets worse over time, not better. This build
  keeps the full ~10-11 char code and adds a collision-retry loop as a
  defensive backstop, not a crutch.
- **Partial unique index, not a plain unique constraint.** `short_code` is
  unique only where `deleted_at IS NULL`
  ([`app/models.py`](app/models.py)) — a soft-deleted URL's code can be
  reissued without a hard delete.
- **Click tracking uses its own DB session.** The request's session may
  already be closing by the time the fire-and-forget `asyncio.create_task`
  runs; using a fresh `AsyncSessionLocal()` avoids a "session already
  closed" race.

## How to run

```bash
docker compose up -d --build
open http://localhost:8002/docs
```

Ports are offset from this repo's other dockerized project
(`08_FastAPI_OpenAI_RAG_Backend_starter`, which uses 8001/5432/6379) so both
stacks can run at once: app→**8002**, Postgres→**5433**, Redis→**6380**.

```bash
# quick manual check
curl -s -X POST localhost:8002/shorten -H 'content-type: application/json' \
  -d '{"long_url": "https://anthropic.com/"}'
curl -s -o /dev/null -D - localhost:8002/<code-from-above>   # 302 → long_url
```

## Milestones (from spec) — what's done

- **Week 1** — Snowflake ID generator, shorten + redirect endpoints, Redis caching → **done**
- **Week 2** — custom aliases, expiring URLs, password protection → **done**; Kafka pipeline + Clickhouse → **deferred** (see above)
- **Week 3** — Auth + user accounts, rate limiting, QR codes → **done**; malicious URL detection, custom domains → **deferred**
