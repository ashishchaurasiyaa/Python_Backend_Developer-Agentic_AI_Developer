"""
FastAPI Performance Profiling — Production Patterns
"""

import asyncio
import cProfile
import logging
import pstats
import time
from functools import wraps
from io import StringIO

from fastapi import FastAPI, Request, Response
from fastapi.responses import HTMLResponse, ORJSONResponse


# ==========================================================================
# 1. ORJSON for fastest JSON serialization
# ==========================================================================

app = FastAPI(default_response_class=ORJSONResponse)


# ==========================================================================
# 2. PYINSTRUMENT MIDDLEWARE (on-demand profiling)
# ==========================================================================

# pip install pyinstrument
from pyinstrument import Profiler


@app.middleware("http")
async def profile_middleware(request: Request, call_next):
    """Add ?_profile=1 to URL to see flame graph."""
    if request.query_params.get('_profile') == '1':
        profiler = Profiler(async_mode='enabled', interval=0.001)
        profiler.start()
        try:
            response = await call_next(request)
        finally:
            profiler.stop()
        return HTMLResponse(profiler.output_html())
    return await call_next(request)


# ==========================================================================
# 3. CPROFILE DECORATOR (per-endpoint deterministic profiling)
# ==========================================================================

def cprofile_endpoint(func):
    @wraps(func)
    async def wrapper(*args, **kwargs):
        profiler = cProfile.Profile()
        profiler.enable()
        try:
            return await func(*args, **kwargs)
        finally:
            profiler.disable()
            s = StringIO()
            ps = pstats.Stats(profiler, stream=s).sort_stats('cumulative')
            ps.print_stats(30)
            print(s.getvalue())
    return wrapper


@app.get("/expensive-cprofile")
@cprofile_endpoint
async def expensive_cprofile():
    # Some work
    total = sum(i ** 2 for i in range(100_000))
    await asyncio.sleep(0.05)
    return {"total": total}


# ==========================================================================
# 4. PROMETHEUS METRICS
# ==========================================================================

# pip install prometheus-client
from prometheus_client import (
    Counter, Histogram, Gauge,
    make_asgi_app,
    CollectorRegistry, generate_latest, CONTENT_TYPE_LATEST,
)


REQUEST_DURATION = Histogram(
    'http_request_duration_seconds',
    'HTTP request latency',
    labelnames=['method', 'endpoint', 'status'],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)

REQUEST_COUNT = Counter(
    'http_requests_total',
    'Total HTTP requests',
    labelnames=['method', 'endpoint', 'status'],
)

ACTIVE_REQUESTS = Gauge(
    'http_requests_active',
    'Currently in-flight requests',
    labelnames=['method', 'endpoint'],
)


@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    method = request.method
    path = request.url.path

    ACTIVE_REQUESTS.labels(method, path).inc()
    start = time.monotonic()

    try:
        response = await call_next(request)
        status = str(response.status_code)
    except Exception:
        status = "500"
        raise
    finally:
        duration = time.monotonic() - start
        REQUEST_DURATION.labels(method, path, status).observe(duration)
        REQUEST_COUNT.labels(method, path, status).inc()
        ACTIVE_REQUESTS.labels(method, path).dec()

    return response


# Mount /metrics endpoint
metrics_app = make_asgi_app()
app.mount("/metrics", metrics_app)


# ==========================================================================
# 5. SLOW QUERY LOGGING (SQLAlchemy)
# ==========================================================================

"""
from sqlalchemy import event
from sqlalchemy.engine import Engine
import time

@event.listens_for(Engine, "before_cursor_execute")
def before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    conn.info.setdefault('query_start_time', []).append(time.monotonic())


@event.listens_for(Engine, "after_cursor_execute")
def after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    total = time.monotonic() - conn.info['query_start_time'].pop(-1)
    if total > 0.5:  # > 500ms
        logging.warning(
            "Slow query (%.2fs): %s",
            total,
            statement[:200].replace('\\n', ' '),
        )
"""


# ==========================================================================
# 6. ASYNC BLOCKING DETECTION
# ==========================================================================

import warnings


def detect_blocking_in_async(threshold_ms: int = 100):
    """Wrap an async function to detect long blocking work."""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            loop = asyncio.get_event_loop()
            start = loop.time()
            # Schedule a check
            handle = loop.call_later(threshold_ms / 1000, lambda: warnings.warn(
                f"{func.__name__} may be blocking event loop"
            ))
            try:
                return await func(*args, **kwargs)
            finally:
                handle.cancel()
        return wrapper
    return decorator


@app.get("/potentially-blocking")
@detect_blocking_in_async(threshold_ms=200)
async def maybe_blocks():
    await asyncio.sleep(0.05)
    return {}


# ==========================================================================
# 7. LOCUST LOAD TEST FILE
# ==========================================================================

LOCUST_FILE = """
# locustfile.py
from locust import HttpUser, task, between
import random


class APIUser(HttpUser):
    wait_time = between(1, 3)
    host = "http://localhost:8000"

    def on_start(self):
        # Login
        resp = self.client.post(
            "/login",
            json={"email": "test@example.com", "password": "secret"},
        )
        self.token = resp.json().get("token", "fake-token")
        self.client.headers["Authorization"] = f"Bearer {self.token}"

    @task(5)
    def list_articles(self):
        self.client.get("/articles?limit=20", name="/articles")

    @task(2)
    def get_article(self):
        article_id = random.randint(1, 100)
        self.client.get(f"/articles/{article_id}", name="/articles/[id]")

    @task(1)
    def create_article(self):
        self.client.post(
            "/articles",
            json={"title": "Locust test", "body": "..."},
            name="/articles [POST]",
        )

# Run:
# locust -f locustfile.py --headless -u 100 -r 10 -t 60s --host http://localhost:8000
# Or web UI: locust -f locustfile.py
"""


# ==========================================================================
# 8. STARTUP CHECKS — verify no obvious perf issues
# ==========================================================================

@app.on_event("startup")
async def startup_perf_checks():
    # Verify uvloop installed (faster than default loop)
    try:
        import uvloop
        print("uvloop available — use --loop uvloop")
    except ImportError:
        print("WARNING: uvloop not installed; will use default asyncio loop (~2x slower)")

    # Verify orjson
    try:
        import orjson
    except ImportError:
        print("WARNING: orjson not installed; using stdlib json (~3x slower)")


# ==========================================================================
# 9. PROFILING HELPER COMMANDS
# ==========================================================================

PROFILING_COMMANDS = """
# 1. py-spy live top (find current PID)
py-spy top --pid <PID>

# 2. py-spy record flame graph (30 seconds)
py-spy record -o profile.svg --pid <PID> --duration 30
py-spy record -o profile.svg --pid <PID> --duration 30 --native  # include C

# 3. Scalene
scalene --html --outfile profile.html app.py

# 4. cProfile entire app
python -m cProfile -o profile.pstats -m uvicorn app:app
python -c "import pstats; p = pstats.Stats('profile.pstats'); p.sort_stats('cumulative').print_stats(30)"

# 5. asyncio debug mode (warnings for blocking)
PYTHONASYNCIODEBUG=1 uvicorn app:app

# 6. uvicorn with uvloop
pip install uvloop httptools
uvicorn app:app --loop uvloop --http httptools --workers 4
"""


# ==========================================================================
# 10. PROD DEPLOY — GUNICORN + UVICORN WORKERS
# ==========================================================================

GUNICORN_CMD = """
# Recommended for production
gunicorn app:app \\
    -w 4 \\
    -k uvicorn.workers.UvicornWorker \\
    --bind 0.0.0.0:8000 \\
    --timeout 30 \\
    --keep-alive 5 \\
    --access-logfile - \\
    --error-logfile -

# Workers = 2 * CPU + 1 (rough rule)
# Each worker has its own event loop — N concurrent connections per worker
"""


# ==========================================================================
# 11. PER-ENDPOINT TIMING DECORATOR (lightweight)
# ==========================================================================

import structlog

log = structlog.get_logger()


def time_endpoint(func):
    @wraps(func)
    async def wrapper(*args, **kwargs):
        start = time.monotonic()
        try:
            result = await func(*args, **kwargs)
            duration_ms = int((time.monotonic() - start) * 1000)
            log.info(
                "endpoint_timing",
                func=func.__name__,
                duration_ms=duration_ms,
            )
            return result
        except Exception:
            duration_ms = int((time.monotonic() - start) * 1000)
            log.error(
                "endpoint_failed",
                func=func.__name__,
                duration_ms=duration_ms,
            )
            raise
    return wrapper


@app.get("/timed")
@time_endpoint
async def timed_endpoint():
    await asyncio.sleep(0.1)
    return {"ok": True}
