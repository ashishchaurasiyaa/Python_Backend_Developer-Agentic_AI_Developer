"""
Structured Logging — Production Patterns
"""

import logging
import sys
import time
import uuid
from contextvars import ContextVar
from typing import Any

import structlog
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware


# ==========================================================================
# 1. CONTEXT VARS for request-scoped values
# ==========================================================================

request_id_var: ContextVar[str] = ContextVar('request_id', default='-')
user_id_var: ContextVar[str | None] = ContextVar('user_id', default=None)
trace_id_var: ContextVar[str] = ContextVar('trace_id', default='-')


# ==========================================================================
# 2. STRUCTLOG CONFIGURATION
# ==========================================================================

def configure_logging(
    log_level: str = "INFO",
    json_format: bool = True,
):
    timestamper = structlog.processors.TimeStamper(fmt="iso", utc=True)

    shared_processors = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        timestamper,
        structlog.processors.StackInfoRenderer(),
        sanitize_sensitive,
        censor_long_strings,
    ]

    if json_format:
        processors = shared_processors + [
            structlog.processors.dict_tracebacks,
            structlog.processors.JSONRenderer(),
        ]
    else:
        processors = shared_processors + [structlog.dev.ConsoleRenderer(colors=True)]

    structlog.configure(
        processors=processors,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, log_level.upper()),
    )

    # Silence noisy libs
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)


# ==========================================================================
# 3. CUSTOM PROCESSORS (sanitization)
# ==========================================================================

SENSITIVE_KEY_PATTERNS = (
    'password', 'passwd', 'token', 'secret', 'authorization',
    'api_key', 'apikey', 'private_key', 'cookie', 'session',
    'credit_card', 'cvv', 'ssn',
)


def sanitize_sensitive(_, __, event_dict: dict) -> dict:
    """Replace sensitive values with ***."""
    for key in list(event_dict.keys()):
        key_lower = key.lower()
        if any(s in key_lower for s in SENSITIVE_KEY_PATTERNS):
            event_dict[key] = '***'
    return event_dict


def censor_long_strings(_, __, event_dict: dict, max_len: int = 1000) -> dict:
    """Truncate huge log values."""
    for k, v in event_dict.items():
        if isinstance(v, str) and len(v) > max_len:
            event_dict[k] = v[:max_len] + f'...[truncated {len(v) - max_len}]'
    return event_dict


# ==========================================================================
# 4. INITIALIZE + GET LOGGER
# ==========================================================================

import os

configure_logging(
    log_level=os.environ.get('LOG_LEVEL', 'INFO'),
    json_format=os.environ.get('LOG_FORMAT', 'json') == 'json',
)

log = structlog.get_logger()


# ==========================================================================
# 5. CORRELATION ID + ACCESS LOG MIDDLEWARE
# ==========================================================================

app = FastAPI()


@app.middleware("http")
async def correlation_and_access_log(request: Request, call_next):
    # Resolve / generate request ID
    request_id = request.headers.get('x-request-id') or str(uuid.uuid4())
    token_req = request_id_var.set(request_id)

    # Resolve W3C trace context
    traceparent = request.headers.get('traceparent', '')
    if traceparent and len(traceparent.split('-')) >= 2:
        trace_id = traceparent.split('-')[1]
    else:
        trace_id = uuid.uuid4().hex

    token_trace = trace_id_var.set(trace_id)

    # Bind to structlog context
    structlog.contextvars.bind_contextvars(
        request_id=request_id,
        trace_id=trace_id,
        method=request.method,
        path=request.url.path,
        client_ip=request.client.host if request.client else '-',
    )

    start = time.monotonic()
    log.info("request_started")

    try:
        response = await call_next(request)
    except Exception as e:
        duration_ms = int((time.monotonic() - start) * 1000)
        log.exception(
            "request_failed",
            duration_ms=duration_ms,
            error_type=type(e).__name__,
        )
        raise

    duration_ms = int((time.monotonic() - start) * 1000)
    log.info(
        "request_completed",
        status_code=response.status_code,
        duration_ms=duration_ms,
    )

    response.headers['X-Request-ID'] = request_id
    response.headers['traceparent'] = f'00-{trace_id}-{uuid.uuid4().hex[:16]}-01'

    structlog.contextvars.clear_contextvars()
    request_id_var.reset(token_req)
    trace_id_var.reset(token_trace)

    return response


# ==========================================================================
# 6. USER CONTEXT INJECTION (after auth)
# ==========================================================================

from fastapi import Depends, Header, HTTPException


async def get_current_user(authorization: str = Header(...)):
    # ... validate token, get user
    user_id = 'user-123'  # mock

    user_id_var.set(user_id)
    structlog.contextvars.bind_contextvars(user_id=user_id)

    return {'id': user_id}


# ==========================================================================
# 7. ENDPOINT WITH STRUCTURED LOGS
# ==========================================================================

@app.get("/items/{item_id}")
async def get_item(item_id: int, user=Depends(get_current_user)):
    log.info("fetching_item", item_id=item_id)

    # Simulate work
    try:
        if item_id < 0:
            raise ValueError("negative id")
        item = {'id': item_id, 'name': f'Item {item_id}'}
        log.info("item_fetched", item_id=item_id, found=True)
        return item
    except ValueError as e:
        log.warning("invalid_item_id", item_id=item_id, error=str(e))
        raise HTTPException(400, "Invalid ID")


# ==========================================================================
# 8. STARLETTE LOGGING — disable default access log
# ==========================================================================

# Uvicorn access log is plain text — disable in favor of our middleware
# Run: uvicorn app:app --no-access-log

# Or in code:
# uvicorn.run(app, log_config=None, access_log=False)


# ==========================================================================
# 9. CELERY TASK CONTEXT PROPAGATION
# ==========================================================================

"""
# tasks.py
from celery import Celery
import structlog


celery_app = Celery(__name__)


@celery_app.task(bind=True)
def my_task(self, item_id, request_id=None, user_id=None):
    # Restore context from task headers
    if request_id:
        structlog.contextvars.bind_contextvars(request_id=request_id)
    if user_id:
        structlog.contextvars.bind_contextvars(user_id=user_id)

    log.info("task_started", task_id=self.request.id, item_id=item_id)
    try:
        # ... work
        log.info("task_completed", task_id=self.request.id)
    except Exception as e:
        log.exception("task_failed", task_id=self.request.id)
        raise


# From FastAPI view:
@app.post("/items/{item_id}/process")
async def queue_processing(item_id: int, user=Depends(get_current_user)):
    my_task.delay(
        item_id,
        request_id=request_id_var.get(),
        user_id=user['id'],
    )
    return {'queued': True}
"""


# ==========================================================================
# 10. EXTERNAL HTTP CLIENT WITH TRACE PROPAGATION
# ==========================================================================

import httpx


async def call_downstream(url: str):
    """Forward trace context to downstream service."""
    headers = {
        'X-Request-ID': request_id_var.get(),
        'traceparent': f'00-{trace_id_var.get()}-{uuid.uuid4().hex[:16]}-01',
    }
    async with httpx.AsyncClient(timeout=10.0) as client:
        log.info("downstream_call_started", url=url)
        try:
            resp = await client.get(url, headers=headers)
            log.info("downstream_call_completed", url=url, status=resp.status_code)
            return resp
        except httpx.RequestError as e:
            log.error("downstream_call_failed", url=url, error=str(e))
            raise


# ==========================================================================
# 11. LOG SAMPLING (avoid hot-loop blowups)
# ==========================================================================

import random


class SamplingLogger:
    def __init__(self, logger, sample_rate: float = 0.01):
        self.logger = logger
        self.sample_rate = sample_rate

    def info(self, event, **kw):
        if random.random() < self.sample_rate:
            self.logger.info(event, sampled=True, **kw)


sampled = SamplingLogger(log, sample_rate=0.01)
# Use in hot loops
# for row in million_rows:
#     sampled.info("processing", row_id=row.id)


# ==========================================================================
# 12. ALTERNATIVE: LOGURU SETUP
# ==========================================================================

"""
# pip install loguru
from loguru import logger
import sys


logger.remove()
logger.add(
    sys.stdout,
    level="INFO",
    serialize=True,    # JSON output
    backtrace=True,
    diagnose=False,    # don't dump local vars (security)
)


# Use
logger.bind(user_id=123, request_id='abc').info("login")
"""
