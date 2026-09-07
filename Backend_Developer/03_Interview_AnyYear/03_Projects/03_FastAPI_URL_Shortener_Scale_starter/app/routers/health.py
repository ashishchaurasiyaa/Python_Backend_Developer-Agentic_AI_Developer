"""Liveness / readiness endpoints."""

from fastapi import APIRouter

from app.config import get_settings

router = APIRouter(tags=["health"])


@router.get("/health")
async def health():
    """Liveness — boots without any datastore, so this stays green even if
    Postgres/Redis are briefly unreachable (matches the RAG backend's convention)."""
    s = get_settings()
    return {"status": "ok", "app": s.app_name, "env": s.environment}
