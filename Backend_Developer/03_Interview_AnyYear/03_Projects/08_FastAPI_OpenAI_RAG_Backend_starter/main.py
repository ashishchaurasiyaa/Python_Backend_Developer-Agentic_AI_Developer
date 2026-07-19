"""
Entry-point shim so `uvicorn main:app` keeps working.

The real application factory lives in app/main.py. Prefer `uvicorn app.main:app`.
The former single-file skeleton has been refactored into the app/ package
(routers/, config, db) — all its TODOs/reference SQL are preserved there.
"""

from app.main import app  # noqa: F401
