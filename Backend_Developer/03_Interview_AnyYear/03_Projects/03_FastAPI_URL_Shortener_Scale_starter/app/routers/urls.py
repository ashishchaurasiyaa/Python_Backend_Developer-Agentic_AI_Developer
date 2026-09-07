"""GET /me/urls — spec section 11 analytics-lite endpoint (Clickhouse-backed
per-click analytics are out of scope, see README; click_count is the
denormalized counter tracked directly on each row)."""

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import get_session
from app.deps import get_current_user
from app.models import URL, User

router = APIRouter(prefix="/me", tags=["urls"])
settings = get_settings()


class URLSummary(BaseModel):
    code: str
    short_url: str
    long_url: str
    click_count: int
    created_at: str
    expires_at: str | None


@router.get("/urls", response_model=list[URLSummary])
async def list_my_urls(
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
    limit: int = 50,
):
    result = await session.execute(
        select(URL)
        .where(URL.user_id == user.id, URL.deleted_at.is_(None))
        .order_by(URL.created_at.desc())
        .limit(min(limit, 200))
    )
    rows = result.scalars().all()
    return [
        URLSummary(
            code=r.short_code,
            short_url=f"https://{settings.base_domain}/{r.short_code}",
            long_url=r.long_url,
            click_count=r.click_count,
            created_at=r.created_at.isoformat(),
            expires_at=r.expires_at.isoformat() if r.expires_at else None,
        )
        for r in rows
    ]
