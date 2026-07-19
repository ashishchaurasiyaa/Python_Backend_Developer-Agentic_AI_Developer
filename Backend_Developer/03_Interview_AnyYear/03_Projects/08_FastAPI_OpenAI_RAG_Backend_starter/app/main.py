"""
Application factory + entry point.

`create_app()` wires config, lifespan, and routers together. The module-level
`app` is what uvicorn serves (`uvicorn app.main:app` or the root shim
`uvicorn main:app`).
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import get_settings
from app.routers import documents, health, query

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: (Day 2+) verify DB/Redis connectivity, warm caches, run checks.
    yield
    # Shutdown: release the connection pool cleanly.
    from app.db import engine

    await engine.dispose()


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        lifespan=lifespan,
    )
    app.include_router(health.router)
    app.include_router(documents.router)
    app.include_router(query.router)
    return app


app = create_app()
