"""POST /shorten — spec section 11, "Shorten endpoint"."""

import re
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, HttpUrl, field_validator
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import get_session
from app.deps import get_optional_user, rate_limit
from app.models import URL, User
from app.security import hash_password
from app.shortcode import SnowflakeID, to_base62

router = APIRouter(tags=["shorten"])
settings = get_settings()

_snowflake = SnowflakeID(worker_id=settings.worker_id)
_ALIAS_PATTERN = re.compile(r"^[a-zA-Z0-9_-]{3,20}$")


class ShortenRequest(BaseModel):
    long_url: HttpUrl
    custom_alias: str | None = None
    expires_in_hours: int | None = None
    password: str | None = None

    @field_validator("custom_alias")
    @classmethod
    def validate_alias(cls, v: str | None) -> str | None:
        if v is not None and not _ALIAS_PATTERN.match(v):
            raise ValueError("custom_alias must be 3-20 chars, letters/digits/underscore/hyphen only")
        return v


class ShortenResponse(BaseModel):
    short_url: str
    code: str
    long_url: str
    expires_at: str | None


@router.post("/shorten", response_model=ShortenResponse, dependencies=[Depends(rate_limit)])
async def shorten(
    req: ShortenRequest,
    session: AsyncSession = Depends(get_session),
    user: User | None = Depends(get_optional_user),
):
    if req.custom_alias is not None and user is None:
        raise HTTPException(status_code=403, detail="Custom alias requires an account (spec: paid feature)")

    expires_at = None
    if req.expires_in_hours is not None:
        expires_at = datetime.now(timezone.utc) + timedelta(hours=req.expires_in_hours)

    password_hash = hash_password(req.password) if req.password else None

    if req.custom_alias:
        code = req.custom_alias
        url_row = URL(
            short_code=code, long_url=str(req.long_url), user_id=user.id if user else None,
            expires_at=expires_at, password_hash=password_hash,
        )
        session.add(url_row)
        try:
            await session.commit()
        except IntegrityError:
            await session.rollback()
            raise HTTPException(status_code=409, detail=f"Alias '{code}' is already taken")
    else:
        # Collision-retry loop (spec's own TODO) — astronomically unlikely with
        # a full-length Snowflake code, but this is the defensive pattern a
        # real system needs regardless of how the code is generated.
        for attempt in range(5):
            code = to_base62(_snowflake.next_id())
            url_row = URL(
                short_code=code, long_url=str(req.long_url), user_id=user.id if user else None,
                expires_at=expires_at, password_hash=password_hash,
            )
            session.add(url_row)
            try:
                await session.commit()
                break
            except IntegrityError:
                await session.rollback()
                if attempt == 4:
                    raise HTTPException(status_code=503, detail="Could not generate a unique code, try again")

    return ShortenResponse(
        short_url=f"https://{settings.base_domain}/{code}",
        code=code,
        long_url=str(req.long_url),
        expires_at=expires_at.isoformat() if expires_at else None,
    )
