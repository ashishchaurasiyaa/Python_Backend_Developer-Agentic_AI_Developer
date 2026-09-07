"""Application factory + entry point."""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import get_settings
from app.redis_client import close_redis
from app.routers import auth, health, redirect, shorten, urls

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    from app.db import engine, init_models

    # create_all() is idempotent (checkfirst=True by default) — safe to run
    # on every startup. Fine for this project's scope; see db.py's docstring
    # for why a real deployment would use Alembic instead.
    await init_models()
    yield
    await close_redis()
    await engine.dispose()


def create_app() -> FastAPI:
    app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)

    # IMPORTANT: registration order matters. redirect.router owns the
    # catch-all `/{short_code}` path — every other single-segment route
    # (/health, /shorten) MUST be registered before it, or FastAPI/Starlette
    # matches routes in declaration order and `/{short_code}` would swallow
    # them (e.g. GET /health would be interpreted as short_code="health").
    app.include_router(health.router)
    app.include_router(auth.router)
    app.include_router(urls.router)
    app.include_router(shorten.router)
    app.include_router(redirect.router)  # last, on purpose

    return app


app = create_app()
