"""Liveness / readiness endpoints."""

from fastapi import APIRouter

from app.config import get_settings

router = APIRouter(tags=["health"])


@router.get("/health")
async def health():
    """Liveness — boots without any datastore (used by the Day 3 deploy check)."""
    s = get_settings()
    return {"status": "ok", "app": s.app_name, "env": s.environment}


@router.get("/health/ready")
async def readiness():
    """Readiness — Day 2 will actually ping Postgres + Redis here."""
    return {"status": "ok", "checks": {"db": "TODO", "redis": "TODO"}}
