"""
FastAPI Caching — Production Patterns
"""

import asyncio
import hashlib
import json
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from email.utils import format_datetime, parsedate_to_datetime

from fastapi import FastAPI, Request, Response, Depends, HTTPException
from fastapi_cache import FastAPICache
from fastapi_cache.backends.redis import RedisBackend
from fastapi_cache.decorator import cache
from redis import asyncio as aioredis


# ==========================================================================
# 1. SETUP — fastapi-cache2 + Redis
# ==========================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    redis_client = aioredis.from_url("redis://localhost:6379/0", decode_responses=True)
    FastAPICache.init(RedisBackend(redis_client), prefix="myapp-cache:")
    yield
    await redis_client.close()


app = FastAPI(lifespan=lifespan)


# ==========================================================================
# 2. BASIC CACHING (with @cache decorator)
# ==========================================================================

@app.get("/articles")
@cache(expire=60, namespace="articles")
async def list_articles():
    """Cached for 60 seconds."""
    # Pretend DB call
    return [{"id": 1, "title": "Sample"}]


@app.get("/articles/{article_id}")
@cache(expire=300, namespace="articles")
async def get_article(article_id: int):
    return {"id": article_id, "title": "Cached article"}


# ==========================================================================
# 3. PER-USER CACHE KEY
# ==========================================================================

def user_key_builder(
    func,
    namespace: str = "",
    request: Request = None,
    response: Response = None,
    *args,
    **kwargs,
) -> str:
    user_id = 'anon'
    if request and hasattr(request.state, 'user_id'):
        user_id = request.state.user_id
    return f'{namespace}:{func.__module__}.{func.__name__}:user:{user_id}'


@app.get("/my-dashboard")
@cache(expire=60, key_builder=user_key_builder, namespace="dashboard")
async def my_dashboard(request: Request):
    user_id = getattr(request.state, 'user_id', 'anon')
    return {
        'user_id': user_id,
        'cached_at': datetime.utcnow().isoformat(),
    }


# ==========================================================================
# 4. INVALIDATION ON MUTATION
# ==========================================================================

from pydantic import BaseModel


class ArticleIn(BaseModel):
    title: str
    body: str


@app.post("/articles")
async def create_article(payload: ArticleIn):
    # ... save to DB
    # Clear list cache
    await FastAPICache.clear(namespace="articles")
    return {"id": 999, **payload.model_dump()}


@app.put("/articles/{article_id}")
async def update_article(article_id: int, payload: ArticleIn):
    # ... update DB
    await FastAPICache.clear(namespace="articles")
    return {"id": article_id, **payload.model_dump()}


# ==========================================================================
# 5. ETAG + CONDITIONAL GET
# ==========================================================================

@app.get("/articles-with-etag/{article_id}")
async def article_with_etag(
    article_id: int,
    request: Request,
    response: Response,
):
    # Fetch from DB (or cache)
    article = {"id": article_id, "title": "X", "updated_at": datetime.utcnow().isoformat()}

    # Compute ETag — cheap (id + updated_at)
    etag_source = f'{article["id"]}-{article["updated_at"]}'
    etag = hashlib.md5(etag_source.encode()).hexdigest()

    if_none_match = request.headers.get('if-none-match', '')
    if if_none_match == f'"{etag}"' or if_none_match == etag:
        return Response(status_code=304)

    response.headers['ETag'] = f'"{etag}"'
    response.headers['Cache-Control'] = 'private, max-age=300, must-revalidate'
    return article


# ==========================================================================
# 6. LAST-MODIFIED
# ==========================================================================

@app.get("/articles-with-lm/{article_id}")
async def article_with_last_modified(
    article_id: int,
    request: Request,
    response: Response,
):
    article_updated_at = datetime.utcnow().replace(microsecond=0, tzinfo=timezone.utc)

    if_modified_since = request.headers.get('if-modified-since')
    if if_modified_since:
        try:
            client_time = parsedate_to_datetime(if_modified_since)
            if article_updated_at <= client_time:
                return Response(status_code=304)
        except (TypeError, ValueError):
            pass

    response.headers['Last-Modified'] = format_datetime(article_updated_at, usegmt=True)
    response.headers['Cache-Control'] = 'private, max-age=300'
    return {"id": article_id}


# ==========================================================================
# 7. CACHE-CONTROL DIRECTIVES
# ==========================================================================

@app.get("/public-content")
async def public_content(response: Response):
    """Cached at CDN edge."""
    response.headers['Cache-Control'] = 'public, max-age=3600, s-maxage=86400'
    return {"data": "anyone can cache"}


@app.get("/user-content")
async def user_content(response: Response):
    """Per-user, browser-only cache."""
    response.headers['Cache-Control'] = 'private, max-age=300'
    response.headers['Vary'] = 'Authorization'
    return {"data": "your data"}


@app.get("/sensitive")
async def sensitive(response: Response):
    """Never cache."""
    response.headers['Cache-Control'] = 'no-store'
    response.headers['Pragma'] = 'no-cache'
    return {"secret": "..."}


@app.get("/stale-while-revalidate")
async def swr(response: Response):
    """Fresh 60s, serve stale 5 min while async refresh."""
    response.headers['Cache-Control'] = 'public, max-age=60, stale-while-revalidate=300'
    return {"data": "..."}


# ==========================================================================
# 8. STAMPEDE PREVENTION (single-flight)
# ==========================================================================

_in_flight: dict[str, asyncio.Future] = {}


@asynccontextmanager
async def single_flight(key: str):
    """Only one coroutine computes per key — others await result."""
    if key in _in_flight:
        # Wait for in-progress computation
        try:
            result = await _in_flight[key]
            yield result
            return
        except Exception:
            # Fall through to recompute
            pass

    future = asyncio.Future()
    _in_flight[key] = future
    try:
        yield None  # signal caller to compute
    finally:
        # Clean up
        _in_flight.pop(key, None)


_r: aioredis.Redis = None


async def get_redis():
    global _r
    if _r is None:
        _r = aioredis.from_url("redis://localhost:6379/0", decode_responses=True)
    return _r


@app.get("/expensive-stampede-safe")
async def expensive_stampede_safe():
    r = await get_redis()
    key = 'expensive_query'

    cached = await r.get(key)
    if cached:
        return json.loads(cached)

    # Single-flight via Redis SETNX
    lock_key = f'{key}:lock'
    acquired = await r.set(lock_key, '1', ex=30, nx=True)

    if acquired:
        try:
            # Compute (only this caller does)
            result = await asyncio.sleep(0)
            result = {'data': 'computed', 'at': datetime.utcnow().isoformat()}
            await r.set(key, json.dumps(result), ex=300)
            return result
        finally:
            await r.delete(lock_key)
    else:
        # Wait briefly + retry
        for _ in range(20):
            await asyncio.sleep(0.1)
            cached = await r.get(key)
            if cached:
                return json.loads(cached)
        # Fallback: compute anyway
        return {'data': 'fallback'}


# ==========================================================================
# 9. CACHE WITH FALLBACK ON REDIS ERROR
# ==========================================================================

async def cache_get_safe(key: str, default=None):
    try:
        r = await get_redis()
        return await r.get(key)
    except Exception as e:
        import logging
        logging.warning(f"Cache get failed for {key}: {e}")
        return default


async def cache_set_safe(key: str, value: str, ex: int = 300):
    try:
        r = await get_redis()
        await r.set(key, value, ex=ex)
    except Exception as e:
        import logging
        logging.warning(f"Cache set failed for {key}: {e}")


@app.get("/resilient-cached/{item_id}")
async def resilient(item_id: int):
    """Falls back to DB if cache is down."""
    cached = await cache_get_safe(f'item:{item_id}')
    if cached:
        return json.loads(cached)

    # DB fetch (mock)
    item = {'id': item_id, 'name': f'Item {item_id}'}

    await cache_set_safe(f'item:{item_id}', json.dumps(item), ex=300)
    return item


# ==========================================================================
# 10. MULTI-TIER CACHE (in-memory L1 + Redis L2)
# ==========================================================================

from functools import lru_cache


_local_cache: dict[str, tuple[Any, float]] = {}
LOCAL_TTL = 30  # seconds


import time
from typing import Any


async def multi_tier_get(key: str):
    now = time.time()

    # L1: in-memory
    if key in _local_cache:
        val, expires = _local_cache[key]
        if expires > now:
            return val
        del _local_cache[key]

    # L2: Redis
    val = await cache_get_safe(key)
    if val:
        parsed = json.loads(val)
        _local_cache[key] = (parsed, now + LOCAL_TTL)
        return parsed
    return None


async def multi_tier_set(key: str, value: Any, redis_ttl: int = 300):
    _local_cache[key] = (value, time.time() + LOCAL_TTL)
    await cache_set_safe(key, json.dumps(value), ex=redis_ttl)
