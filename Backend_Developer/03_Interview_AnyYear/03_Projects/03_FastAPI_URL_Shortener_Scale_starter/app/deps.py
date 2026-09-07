"""Shared FastAPI dependencies — auth (required + optional) and rate limiting."""

import time

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import get_session
from app.models import User
from app.redis_client import get_redis
from app.security import decode_access_token

settings = get_settings()

_bearer = HTTPBearer(auto_error=False)


async def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
    session: AsyncSession = Depends(get_session),
) -> User:
    """Required auth — 401 if missing/invalid token."""
    user = await _resolve_user(creds, session)
    if user is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user


async def get_optional_user(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
    session: AsyncSession = Depends(get_session),
) -> User | None:
    """Optional auth — anonymous shortening is allowed (spec functional
    requirements), but authenticated users unlock custom alias + higher
    rate limits, so most write endpoints want to KNOW who's calling
    without forcing a login."""
    return await _resolve_user(creds, session)


async def _resolve_user(creds: HTTPAuthorizationCredentials | None, session: AsyncSession) -> User | None:
    if creds is None:
        return None
    user_id = decode_access_token(creds.credentials)
    if user_id is None:
        return None
    result = await session.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()


async def rate_limit(request: Request, user: User | None = Depends(get_optional_user)) -> None:
    """Sliding-window rate limiter (Redis sorted set) — same pattern as the
    Backend_Developer interview-prep FastAPI rate-limiting doc. Anonymous
    callers get a tighter limit than authenticated ones, matching the spec's
    per-IP vs per-user tiers (section 12)."""
    redis = get_redis()
    if user is not None:
        key = f"ratelimit:user:{user.id}"
        limit = settings.auth_shorten_per_minute
    else:
        client_ip = request.client.host if request.client else "unknown"
        key = f"ratelimit:ip:{client_ip}"
        limit = settings.anon_shorten_per_minute

    now = time.time()
    window = 60
    pipe = redis.pipeline()
    pipe.zremrangebyscore(key, 0, now - window)
    pipe.zadd(key, {str(now): now})
    pipe.zcard(key)
    pipe.expire(key, window)
    _, _, count, _ = await pipe.execute()

    if count > limit:
        raise HTTPException(status_code=429, detail=f"Rate limit exceeded ({limit}/min). Sign in for a higher limit.")
