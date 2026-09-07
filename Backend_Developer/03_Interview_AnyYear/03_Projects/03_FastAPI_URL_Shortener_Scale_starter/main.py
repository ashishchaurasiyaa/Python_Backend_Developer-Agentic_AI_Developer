"""
Entry-point shim so `uvicorn main:app` keeps working.

The real application factory lives in app/main.py. Prefer `uvicorn app.main:app`.
"""

from app.main import app  # noqa: F401
