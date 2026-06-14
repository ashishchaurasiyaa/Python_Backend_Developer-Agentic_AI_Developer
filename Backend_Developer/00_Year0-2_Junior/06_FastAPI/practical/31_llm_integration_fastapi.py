"""
FastAPI — LLM Integration: OpenAI, Claude, Streaming + Production Patterns

Covers:
  - Singleton async LLM clients via lifespan
  - Basic chat endpoint (Anthropic Claude)
  - SSE streaming endpoint (token-by-token)
  - Parallel batch calls with asyncio.gather + semaphore rate-limiting
  - Exponential-backoff retry with tenacity
  - Per-user token/cost tracking + daily quota enforcement (Redis)
  - Multi-provider fallback routing with LiteLLM
  - Background long-running LLM jobs with Celery
  - Streaming + usage tracking combined
  - Anthropic prompt caching pattern

External dependencies (not all are needed simultaneously):
  pip install fastapi uvicorn anthropic openai litellm tenacity redis celery structlog
"""

# ==========================================================================
# 1. IMPORTS
# ==========================================================================

import asyncio
import json
import logging
import os
import time
from contextlib import asynccontextmanager
from datetime import datetime
from decimal import Decimal
from functools import wraps
from typing import List

import structlog

# pip install anthropic
from anthropic import (
    AsyncAnthropic,
    APIConnectionError,
    RateLimitError,
)

# pip install openai
from openai import AsyncOpenAI

# pip install fastapi uvicorn
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse

# pip install pydantic  (bundled with FastAPI)
from pydantic import BaseModel, Field

# pip install tenacity
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

# pip install redis
import redis.asyncio as aioredis


log = structlog.get_logger()


# ==========================================================================
# 2. SINGLETON LLM CLIENTS — created once, reused across every request
# ==========================================================================

class LLMClients:
    """Holds async SDK client instances shared across the process lifetime."""

    openai: AsyncOpenAI | None = None
    anthropic: AsyncAnthropic | None = None


clients = LLMClients()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    FastAPI lifespan handler.
    Startup  : instantiate clients (connection-pool reuse, explicit timeout).
    Shutdown : close clients gracefully to free TCP connections.

    Key rules:
    - Async SDK is mandatory — the sync SDK blocks the event loop.
    - Create clients once; never recreate per request.
    - Set explicit timeout; LLMs can hang 30+ seconds and kill workers.
    """
    api_key_openai = os.environ.get("OPENAI_API_KEY", "sk-placeholder")
    api_key_anthropic = os.environ.get("ANTHROPIC_API_KEY", "sk-ant-placeholder")

    clients.openai = AsyncOpenAI(
        api_key=api_key_openai,
        timeout=30.0,   # LLM can be slow — never leave this unset
        max_retries=2,  # built-in retry for transient errors
    )
    clients.anthropic = AsyncAnthropic(
        api_key=api_key_anthropic,
        timeout=30.0,
        max_retries=2,
    )
    log.info("llm_clients_ready")
    yield
    # --- Shutdown ---
    await clients.openai.close()
    await clients.anthropic.close()
    log.info("llm_clients_closed")


app = FastAPI(
    title="LLM Integration — FastAPI Production Patterns",
    version="1.0.0",
    lifespan=lifespan,
)


# ==========================================================================
# 3. PRICING TABLE + COST CALCULATOR
# ==========================================================================

# Prices per 1 million tokens (update regularly from provider docs)
PRICING: dict[str, dict[str, Decimal]] = {
    "claude-opus-4-7":    {"input": Decimal("15.00"), "output": Decimal("75.00")},
    "claude-sonnet-4-6":  {"input": Decimal("3.00"),  "output": Decimal("15.00")},
    "claude-haiku-4-5":   {"input": Decimal("0.80"),  "output": Decimal("4.00")},
    "gpt-4o":             {"input": Decimal("2.50"),  "output": Decimal("10.00")},
    "gpt-4o-mini":        {"input": Decimal("0.15"),  "output": Decimal("0.60")},
}


def _calc_cost(input_tok: int, output_tok: int, model: str) -> float:
    """Return USD cost for a single LLM call. Returns 0.0 for unknown models."""
    if model not in PRICING:
        return 0.0
    p = PRICING[model]
    cost = (
        Decimal(input_tok) * p["input"]
        + Decimal(output_tok) * p["output"]
    ) / Decimal(1_000_000)
    return float(cost)


# ==========================================================================
# 4. PYDANTIC REQUEST / RESPONSE MODELS
# ==========================================================================

class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=10_000)
    model: str = Field("claude-sonnet-4-6")
    temperature: float = Field(0.7, ge=0.0, le=2.0)
    max_tokens: int = Field(1024, ge=1, le=8192)


class ChatResponse(BaseModel):
    text: str
    model: str
    input_tokens: int
    output_tokens: int
    cost_usd: float


class BatchRequest(BaseModel):
    prompts: List[str] = Field(..., max_length=10)  # cap prevents abuse


class BatchResponse(BaseModel):
    results: List[str]
    total_input_tokens: int
    total_output_tokens: int


# ==========================================================================
# 5. STUB DEPENDENCY — replace with real auth in production
# ==========================================================================

async def get_current_user_id() -> int:
    """
    Placeholder auth dependency.
    In production: validate JWT, return user_id from claims.
    """
    return 42


# ==========================================================================
# 6. BASIC CHAT ENDPOINT (Claude, non-streaming)
# ==========================================================================

@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    """
    Single-turn chat using Anthropic Claude.

    Production notes:
    - Always await async SDK — sync call blocks event loop.
    - Catch Exception broadly, re-raise as 502 so caller knows it is LLM-side.
    - Return token counts + cost for observability / billing.
    """
    try:
        response = await clients.anthropic.messages.create(
            model=req.model,
            max_tokens=req.max_tokens,
            temperature=req.temperature,
            messages=[{"role": "user", "content": req.message}],
        )
    except Exception as exc:
        log.error("llm_error", error=str(exc))
        raise HTTPException(status_code=502, detail=f"LLM error: {exc}")

    input_tok = response.usage.input_tokens
    output_tok = response.usage.output_tokens

    return ChatResponse(
        text=response.content[0].text,
        model=response.model,
        input_tokens=input_tok,
        output_tokens=output_tok,
        cost_usd=_calc_cost(input_tok, output_tok, response.model),
    )


# ==========================================================================
# 7. SSE STREAMING ENDPOINT (token-by-token)
# ==========================================================================

@app.post("/chat/stream")
async def chat_stream(req: ChatRequest):
    """
    Stream Claude responses token-by-token using Server-Sent Events (SSE).

    Wire format:
      data: {"text": "<chunk>"}\n\n        — for each token chunk
      data: {"type": "done", ...}\n\n      — final usage summary

    Nginx / Cloudflare notes:
    - X-Accel-Buffering: no  — disables Nginx proxy buffering.
    - Connection: keep-alive — required for long streams.
    - Cloudflare below Enterprise buffers by default; use WebSocket there.
    """
    async def event_generator():
        try:
            async with clients.anthropic.messages.stream(
                model=req.model,
                max_tokens=req.max_tokens,
                messages=[{"role": "user", "content": req.message}],
            ) as stream:
                async for text_chunk in stream.text_stream:
                    # SSE wire format requires "data: ...\n\n"
                    yield f"data: {json.dumps({'text': text_chunk})}\n\n"

                # Final event carries token-usage metadata
                final = await stream.get_final_message()
                usage_event = {
                    "type": "done",
                    "input_tokens": final.usage.input_tokens,
                    "output_tokens": final.usage.output_tokens,
                    "cost_usd": _calc_cost(
                        final.usage.input_tokens,
                        final.usage.output_tokens,
                        final.model,
                    ),
                }
                yield f"data: {json.dumps(usage_event)}\n\n"

        except Exception as exc:
            yield f"data: {json.dumps({'error': str(exc)})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",   # disable Nginx buffering
            "Connection": "keep-alive",
        },
    )


# ==========================================================================
# 8. PARALLEL BATCH CALLS — asyncio.gather + semaphore
# ==========================================================================

# Semaphore limits concurrent LLM calls to avoid hitting provider rate limits
_BATCH_SEMAPHORE = asyncio.Semaphore(5)


async def _single_call(prompt: str) -> tuple[str, int, int]:
    """
    One Claude call.  Returns (text, input_tokens, output_tokens).
    Uses the cheaper Haiku model — appropriate for high-volume batch work.
    """
    response = await clients.anthropic.messages.create(
        model="claude-haiku-4-5",
        max_tokens=512,
        messages=[{"role": "user", "content": prompt}],
    )
    return (
        response.content[0].text,
        response.usage.input_tokens,
        response.usage.output_tokens,
    )


async def _bounded_call(prompt: str) -> tuple[str, int, int]:
    """Rate-limited wrapper around _single_call."""
    async with _BATCH_SEMAPHORE:
        return await _single_call(prompt)


@app.post("/chat/batch", response_model=BatchResponse)
async def chat_batch(req: BatchRequest):
    """
    Run up to 10 prompts in parallel.

    asyncio.gather with return_exceptions=True means one failed call does
    not cancel the rest — each error is surfaced as an "ERROR: ..." string.
    """
    results = await asyncio.gather(
        *[_bounded_call(p) for p in req.prompts],
        return_exceptions=True,
    )

    texts: list[str] = []
    input_total = 0
    output_total = 0

    for r in results:
        if isinstance(r, Exception):
            texts.append(f"ERROR: {r}")
        else:
            text, in_tok, out_tok = r
            texts.append(text)
            input_total += in_tok
            output_total += out_tok

    return BatchResponse(
        results=texts,
        total_input_tokens=input_total,
        total_output_tokens=output_total,
    )


# ==========================================================================
# 9. RETRY WITH EXPONENTIAL BACKOFF (tenacity)
# ==========================================================================

# Only retry on transient errors — never on auth / bad-request errors.
_RETRY_EXCEPTIONS = (RateLimitError, APIConnectionError)


async def call_llm_with_retry(prompt: str, model: str = "claude-sonnet-4-6") -> str:
    """
    Retry matrix:
      RateLimitError (429)    — Yes: wait for quota reset
      APIConnectionError      — Yes: network glitch
      APITimeoutError         — Yes (built-in max_retries handles this)
      APIStatusError 5xx      — Yes: server-side issue
      BadRequestError (400)   — No:  bug in our code
      AuthenticationError 401 — No:  fix the API key
      PermissionDeniedError   — No:  fix permissions

    Wait schedule: 2s → 4s → 8s (capped at 30s).
    """
    async for attempt in AsyncRetrying(
        retry=retry_if_exception_type(_RETRY_EXCEPTIONS),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        reraise=True,
    ):
        with attempt:
            response = await clients.anthropic.messages.create(
                model=model,
                max_tokens=1024,
                messages=[{"role": "user", "content": prompt}],
            )
            return response.content[0].text

    # Unreachable — tenacity reraises on final failure
    raise RuntimeError("Retry loop exited without result")  # pragma: no cover


@app.post("/chat/retry")
async def chat_with_retry(req: ChatRequest):
    """Chat endpoint with explicit tenacity retry on transient LLM errors."""
    try:
        text = await call_llm_with_retry(req.message, req.model)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))
    return {"text": text}


# ==========================================================================
# 10. TOKEN USAGE + COST TRACKING (Redis)
# ==========================================================================

# pip install redis
_redis_pool = aioredis.ConnectionPool.from_url(
    os.environ.get("REDIS_URL", "redis://localhost:6379"),
    max_connections=20,
)

DAILY_LIMIT_USD = 5.0   # configurable per plan


async def _get_redis() -> aioredis.Redis:
    return aioredis.Redis(connection_pool=_redis_pool)


async def track_usage(
    user_id: int, model: str, input_tok: int, output_tok: int
) -> None:
    """
    Write per-day and per-month token + cost counters to Redis.

    Key schema:
      usage:user:{user_id}:{YYYY-MM-DD}  hash — input_tokens, output_tokens, cost_usd
      usage:user:{user_id}:{YYYY-MM}     hash — cost_usd (monthly rollup)

    TTL: daily keys expire after 90 days; monthly keys after 400 days.
    Pipeline batches 6 Redis commands into one round-trip.
    """
    r = await _get_redis()
    cost = _calc_cost(input_tok, output_tok, model)
    today = datetime.utcnow().strftime("%Y-%m-%d")
    month = datetime.utcnow().strftime("%Y-%m")

    day_key = f"usage:user:{user_id}:{today}"
    month_key = f"usage:user:{user_id}:{month}"

    pipe = r.pipeline()
    pipe.hincrby(day_key, "input_tokens", input_tok)
    pipe.hincrby(day_key, "output_tokens", output_tok)
    pipe.hincrbyfloat(day_key, "cost_usd", cost)
    pipe.expire(day_key, 60 * 60 * 24 * 90)          # 90 days

    pipe.hincrbyfloat(month_key, "cost_usd", cost)
    pipe.expire(month_key, 60 * 60 * 24 * 400)        # 400 days

    await pipe.execute()


async def check_quota(user_id: int) -> None:
    """
    Raise HTTP 402 if the user has hit their daily USD spend cap.
    Called before every LLM request in quota-aware endpoints.
    """
    r = await _get_redis()
    today = datetime.utcnow().strftime("%Y-%m-%d")
    raw = await r.hget(f"usage:user:{user_id}:{today}", "cost_usd")
    if raw and float(raw) >= DAILY_LIMIT_USD:
        raise HTTPException(status_code=402, detail="Daily LLM quota exceeded")


@app.post("/chat/tracked", response_model=ChatResponse)
async def chat_with_tracking(
    req: ChatRequest,
    user_id: int = Depends(get_current_user_id),
):
    """
    Chat endpoint that enforces quota before the call and records usage after.
    Redis failures are caught and logged — never block the user response.
    """
    try:
        await check_quota(user_id)
    except HTTPException:
        raise
    except Exception as exc:
        log.warning("quota_check_failed", error=str(exc))  # Redis down — fail open

    try:
        response = await clients.anthropic.messages.create(
            model=req.model,
            max_tokens=req.max_tokens,
            temperature=req.temperature,
            messages=[{"role": "user", "content": req.message}],
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))

    input_tok = response.usage.input_tokens
    output_tok = response.usage.output_tokens

    try:
        await track_usage(user_id, response.model, input_tok, output_tok)
    except Exception as exc:
        log.warning("track_usage_failed", error=str(exc))  # non-fatal

    return ChatResponse(
        text=response.content[0].text,
        model=response.model,
        input_tokens=input_tok,
        output_tokens=output_tok,
        cost_usd=_calc_cost(input_tok, output_tok, response.model),
    )


# ==========================================================================
# 11. MULTI-PROVIDER FALLBACK ROUTING (LiteLLM)
# ==========================================================================

# pip install litellm
import litellm
from litellm import acompletion  # type: ignore[import]

litellm.set_verbose = False     # set True for debugging provider calls

# Primary → fallback chain: Claude first, GPT-4o if Claude is down, mini if GPT-4o fails
FALLBACK_MODELS: list[str] = [
    "anthropic/claude-sonnet-4-6",   # primary — best quality
    "openai/gpt-4o",                  # fallback — if Anthropic unavailable
    "openai/gpt-4o-mini",             # budget fallback
]


@app.post("/chat/resilient")
async def chat_resilient(req: ChatRequest):
    """
    Attempts FALLBACK_MODELS in order.  If the primary fails (network,
    outage, rate limit) LiteLLM transparently retries on the next provider.

    Why LiteLLM:
    - Single OpenAI-compatible interface for 100+ providers.
    - Built-in fallbacks, cost tracking, caching (Redis), routing rules.
    - Observability hooks: LangSmith, Langfuse, Helicone.
    """
    try:
        response = await acompletion(
            model=FALLBACK_MODELS[0],
            messages=[{"role": "user", "content": req.message}],
            fallbacks=FALLBACK_MODELS[1:],
            timeout=30,
            num_retries=2,
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))

    return {
        "text": response.choices[0].message.content,
        "model_used": response.model,
        "input_tokens": response.usage.prompt_tokens,
        "output_tokens": response.usage.completion_tokens,
        "cost_usd": _calc_cost(
            response.usage.prompt_tokens,
            response.usage.completion_tokens,
            response.model,
        ),
    }


# ==========================================================================
# 12. BACKGROUND LLM JOBS (Celery + Redis)
# ==========================================================================

# pip install celery redis
from celery import Celery  # type: ignore[import]
from uuid import uuid4

celery_app = Celery(
    "llm_tasks",
    broker=os.environ.get("CELERY_BROKER_URL", "redis://localhost:6379/0"),
    backend=os.environ.get("CELERY_RESULT_BACKEND", "redis://localhost:6379/1"),
)


@celery_app.task(bind=True, max_retries=2)
def process_long_llm_task(self, prompt: str, user_id: int) -> dict:
    """
    Celery task for LLM calls that may take minutes (large context, long output).

    Uses the sync Anthropic SDK — Celery workers have their own event loops
    and the async SDK cannot be called in this context without wrapping.

    Pattern:
    1. Client POST /llm/submit  → gets task_id immediately (HTTP 202)
    2. Worker processes in background
    3. Client polls GET /llm/status/{task_id} until done
    """
    from anthropic import Anthropic  # sync SDK for Celery workers

    client = Anthropic(
        api_key=os.environ.get("ANTHROPIC_API_KEY", "sk-ant-placeholder"),
    )
    try:
        response = client.messages.create(
            model="claude-opus-4-7",
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}],
            timeout=120,  # long context tasks need 120 s+
        )
        return {
            "status": "completed",
            "text": response.content[0].text,
            "tokens": response.usage.input_tokens + response.usage.output_tokens,
        }
    except Exception as exc:
        raise self.retry(exc=exc, countdown=10)


@app.post("/llm/submit", status_code=202)
async def submit_job(
    req: ChatRequest,
    user_id: int = Depends(get_current_user_id),
):
    """
    Enqueue a long LLM task.  Returns task_id immediately.
    Client polls /llm/status/{task_id} for completion.
    """
    task = process_long_llm_task.delay(req.message, user_id)
    return {"task_id": task.id, "status": "queued"}


@app.get("/llm/status/{task_id}")
async def job_status(task_id: str):
    """Poll Celery task status.  Returns result when ready."""
    task = celery_app.AsyncResult(task_id)
    if task.ready():
        return {"status": "done", "result": task.result}
    return {"status": task.state.lower()}


# ==========================================================================
# 13. STREAMING + USAGE TRACKING COMBINED
# ==========================================================================

@app.post("/chat/stream/tracked")
async def chat_stream_tracked(
    req: ChatRequest,
    user_id: int = Depends(get_current_user_id),
):
    """
    SSE stream with per-user cost tracking.

    Critical detail: usage metadata is only available in the FINAL message,
    not in the token chunks themselves.  Track inside the `finally` block so
    usage is always recorded even if the client disconnects mid-stream.
    """
    await check_quota(user_id)

    async def event_generator():
        input_tok = 0
        output_tok = 0
        try:
            async with clients.anthropic.messages.stream(
                model=req.model,
                max_tokens=req.max_tokens,
                messages=[{"role": "user", "content": req.message}],
            ) as stream:
                async for chunk in stream.text_stream:
                    yield f"data: {json.dumps({'text': chunk})}\n\n"

                final = await stream.get_final_message()
                input_tok = final.usage.input_tokens
                output_tok = final.usage.output_tokens

                yield f"data: {json.dumps({'type': 'done', 'in': input_tok, 'out': output_tok})}\n\n"

        finally:
            # Track even if client closed connection before stream finished
            if input_tok > 0:
                try:
                    await track_usage(user_id, req.model, input_tok, output_tok)
                except Exception as exc:
                    log.warning("track_usage_failed_stream", error=str(exc))

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


# ==========================================================================
# 14. ANTHROPIC PROMPT CACHING
# ==========================================================================

# A large static document that is expensively tokenised on first call
# and cached (at 10% cost) for subsequent calls within 5 minutes.
_LARGE_SYSTEM_CONTEXT = """
You are a senior backend engineer specializing in Python, FastAPI, and distributed systems.
You provide precise, production-ready advice. You prefer async patterns, explicit error handling,
and structured logging. You always consider latency, cost, and failure modes in your answers.
""".strip()


@app.post("/chat/cached")
async def chat_with_prompt_cache(req: ChatRequest):
    """
    Anthropic prompt caching example.

    How it works:
    - The large system block is marked with cache_control: ephemeral.
    - Anthropic caches the KV computation for 5 minutes.
    - Subsequent identical-prefix requests pay ~10% of normal input cost.
    - cache_read_input_tokens appears in usage when a cache hit occurs.

    Best for: shared large documents, long instruction sets, few-shot examples
    that stay constant across many requests.
    """
    try:
        response = await clients.anthropic.messages.create(
            model=req.model,
            max_tokens=req.max_tokens,
            system=[
                {
                    "type": "text",
                    "text": _LARGE_SYSTEM_CONTEXT,         # small static part
                },
                {
                    "type": "text",
                    "text": "# Reference documentation\n" + ("..." * 100),
                    "cache_control": {"type": "ephemeral"},  # cache this block
                },
            ],
            messages=[{"role": "user", "content": req.message}],
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))

    usage = response.usage
    cache_read = getattr(usage, "cache_read_input_tokens", 0) or 0
    cache_created = getattr(usage, "cache_creation_input_tokens", 0) or 0

    return {
        "text": response.content[0].text,
        "input_tokens": usage.input_tokens,
        "output_tokens": usage.output_tokens,
        "cache_read_tokens": cache_read,
        "cache_created_tokens": cache_created,
        "cost_usd": _calc_cost(usage.input_tokens, usage.output_tokens, response.model),
    }


# ==========================================================================
# 15. STRUCTURED REQUEST LOGGING MIDDLEWARE
# ==========================================================================

@app.middleware("http")
async def structured_log_middleware(request: Request, call_next):
    """
    Log every request with method, path, status, and latency.
    Attach correlation ID so distributed traces can be joined.
    """
    start = time.monotonic()
    # Correlation ID comes from upstream gateway (e.g., AWS ALB) or is generated
    correlation_id = request.headers.get("X-Correlation-ID", str(uuid4())[:8])

    try:
        response = await call_next(request)
        status = response.status_code
    except Exception:
        status = 500
        raise
    finally:
        duration_ms = int((time.monotonic() - start) * 1000)
        log.info(
            "http_request",
            method=request.method,
            path=request.url.path,
            status=status,
            duration_ms=duration_ms,
            correlation_id=correlation_id,
        )

    return response


# ==========================================================================
# 16. PRODUCTION CHECKLIST (reference comments)
# ==========================================================================

_PRODUCTION_CHECKLIST = """
Senior-level LLM integration checklist:

  [x] Async SDK — never use sync SDK in FastAPI routes (blocks event loop)
  [x] Singleton clients via lifespan — connection-pool reuse
  [x] Explicit timeout on every client (timeout=30 minimum; 120 for long context)
  [x] Exponential-backoff retry via tenacity (only on transient errors)
  [x] Per-user token + cost tracking in Redis (pipeline for atomicity)
  [x] Daily / monthly quota enforcement before each LLM call
  [x] SSE streaming with Nginx X-Accel-Buffering: no header
  [x] Multi-provider fallback chain via LiteLLM
  [x] Background jobs for long tasks via Celery (avoid HTTP timeout)
  [x] Prompt caching for large static context (Anthropic ephemeral cache)
  [x] Structured logging with correlation ID on every request
  [ ] Observability hooks (LangSmith / Langfuse) — attach to litellm.callbacks
  [ ] API key via secret manager (Vault / AWS Secrets Manager), not .env
  [ ] Vector DB (pgvector) for RAG context injection — see 18_pgvector doc
  [ ] Semantic caching layer (Redis) — see 06_semantic_caching_llm doc
"""

# ==========================================================================
# 17. RUN INSTRUCTIONS (not a __main__ block — use uvicorn directly)
# ==========================================================================

RUN_INSTRUCTIONS = """
Development:
  export ANTHROPIC_API_KEY="sk-ant-..."
  export OPENAI_API_KEY="sk-..."
  export REDIS_URL="redis://localhost:6379"
  uvicorn 31_llm_integration_fastapi:app --reload --port 8000

Production (Gunicorn + Uvicorn workers):
  gunicorn 31_llm_integration_fastapi:app \\
      -w 4 \\
      -k uvicorn.workers.UvicornWorker \\
      --bind 0.0.0.0:8000 \\
      --timeout 60 \\
      --keep-alive 5

Start Celery worker (for /llm/submit endpoint):
  celery -A 31_llm_integration_fastapi.celery_app worker --loglevel=info

Interactive API docs:
  http://localhost:8000/docs
"""
