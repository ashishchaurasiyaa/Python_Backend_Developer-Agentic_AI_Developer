"""
Phase6_AI_APIs — Complete Practical
=====================================
Topics:
  1. FastAPI + LLM integration patterns
  2. Streaming responses (SSE)
  3. Background task processing
  4. Rate limiting + cost tracking per user
  5. Async LLM calls
  6. API versioning for AI endpoints
  7. Webhook patterns for async AI results

Install: pip install fastapi uvicorn langchain-openai anthropic
Run: python 01_ai_apis_practical.py
"""

import os, json, asyncio, time, hashlib
from typing import Optional, AsyncGenerator, Dict, Any
from dataclasses import dataclass, field
from datetime import datetime

MOCK_MODE = not os.getenv("OPENAI_API_KEY")
if MOCK_MODE:
    print("⚠  MOCK MODE — set OPENAI_API_KEY\n")

print("=" * 60)
print("AI API DESIGN PATTERNS")
print("=" * 60)

API_PATTERNS = {
    "Sync endpoint":       "POST /chat → wait for full LLM response → return JSON",
    "Streaming SSE":       "POST /chat/stream → Server-Sent Events, tokens as they arrive",
    "Background jobs":     "POST /analyze → job_id, GET /jobs/{id} → poll for result",
    "Webhook":             "POST /analyze with callback_url → POST result to callback_url",
    "Rate limiting":       "Per-user RPM/TPM limits via Redis sliding window",
    "Cost tracking":       "Log tokens per request, per user, per day",
    "Caching":             "Semantic cache: same/similar queries skip LLM",
    "Health check":        "GET /health checks LLM connectivity + DB + cache",
}
for k, v in API_PATTERNS.items():
    print(f"  {k:<22}: {v}")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 1: FastAPI + LLM Endpoint
# INTERVIEW: Sync vs streaming vs background
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 60)
print("SECTION 1: FastAPI + LLM Endpoints")
print("=" * 60)

FASTAPI_LLM_CODE = '''\
from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
import asyncio

app = FastAPI(title="AI API", version="1.0.0")

# ── Request/Response models ────────────────────────────────────
class ChatRequest(BaseModel):
    message:    str = Field(max_length=10000)
    session_id: str
    model:      str = "gpt-4o-mini"
    temperature:float = Field(default=0.7, ge=0, le=2)
    max_tokens: int = Field(default=1000, ge=1, le=4000)

class ChatResponse(BaseModel):
    response:    str
    session_id:  str
    model:       str
    usage:       dict    # {"prompt_tokens": ..., "completion_tokens": ...}
    cost_usd:    float
    latency_ms:  float

# ── Sync endpoint (simple) ─────────────────────────────────────
@app.post("/v1/chat", response_model=ChatResponse)
async def chat(request: ChatRequest, user=Depends(get_current_user)):
    start = time.time()
    # Rate limit check
    await rate_limiter.check(user.id)
    # Budget check
    await budget_tracker.check(user.id, estimated_tokens=request.max_tokens)

    llm = ChatOpenAI(model=request.model, temperature=request.temperature)
    msgs = await session_store.get_history(request.session_id)
    msgs.append(HumanMessage(content=request.message))

    response = await llm.ainvoke(msgs)
    await session_store.save(request.session_id, msgs + [response])

    usage   = response.usage_metadata
    cost    = estimate_cost(usage["input_tokens"], usage["output_tokens"], request.model)
    await budget_tracker.charge(user.id, cost)

    return ChatResponse(
        response   = response.content,
        session_id = request.session_id,
        model      = request.model,
        usage      = usage,
        cost_usd   = cost,
        latency_ms = (time.time() - start) * 1000,
    )

# ── Streaming endpoint ─────────────────────────────────────────
# INTERVIEW: StreamingResponse + async generator = SSE streaming
@app.post("/v1/chat/stream")
async def chat_stream(request: ChatRequest, user=Depends(get_current_user)):
    async def generate() -> AsyncGenerator[str, None]:
        llm = ChatOpenAI(model=request.model, streaming=True)
        async for chunk in llm.astream([HumanMessage(content=request.message)]):
            token = chunk.content
            if token:
                # SSE format: "data: {json}\\n\\n"
                yield f"data: {json.dumps({'token': token})}\\n\\n"
        yield f"data: {json.dumps({'done': True})}\\n\\n"

    return StreamingResponse(
        generate(),
        media_type = "text/event-stream",
        headers    = {
            "Cache-Control":   "no-cache",
            "X-Accel-Buffering":"no",    # disable Nginx buffering
        }
    )
'''
print(FASTAPI_LLM_CODE[:900])


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 2: Background Jobs (for long-running AI tasks)
# INTERVIEW: POST to submit, GET to poll, or webhook callback
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 60)
print("SECTION 2: Background Job Pattern")
print("=" * 60)

BACKGROUND_CODE = '''\
from fastapi import BackgroundTasks
from enum import Enum
import uuid

class JobStatus(str, Enum):
    PENDING   = "pending"
    RUNNING   = "running"
    COMPLETED = "completed"
    FAILED    = "failed"

# ── In-memory job store (use Redis in production) ──────────────
jobs: dict[str, dict] = {}

# ── Submit job ─────────────────────────────────────────────────
@app.post("/v1/analyze")
async def submit_analysis(
    request: AnalysisRequest,
    background_tasks: BackgroundTasks,
    user=Depends(get_current_user),
):
    job_id = str(uuid.uuid4())
    jobs[job_id] = {
        "id":         job_id,
        "status":     JobStatus.PENDING,
        "created_at": datetime.now().isoformat(),
        "user_id":    user.id,
        "result":     None,
        "error":      None,
    }
    # Add to background task queue
    background_tasks.add_task(run_analysis, job_id, request)
    return {"job_id": job_id, "status": "pending"}

async def run_analysis(job_id: str, request: AnalysisRequest):
    jobs[job_id]["status"] = JobStatus.RUNNING
    try:
        llm    = ChatOpenAI(model="gpt-4o")
        result = await llm.ainvoke(build_analysis_prompt(request))
        jobs[job_id].update({"status": JobStatus.COMPLETED, "result": result.content})
        # If webhook URL provided, POST result to it
        if request.callback_url:
            await post_webhook(request.callback_url, jobs[job_id])
    except Exception as e:
        jobs[job_id].update({"status": JobStatus.FAILED, "error": str(e)})

# ── Poll for result ────────────────────────────────────────────
@app.get("/v1/jobs/{job_id}")
async def get_job(job_id: str, user=Depends(get_current_user)):
    if job_id not in jobs:
        raise HTTPException(404, "Job not found")
    job = jobs[job_id]
    if job["user_id"] != user.id:
        raise HTTPException(403, "Access denied")
    return job

# ── Celery alternative (for production scale) ─────────────────
from celery import Celery
celery = Celery("tasks", broker="redis://localhost:6379")

@celery.task
def analyze_document_task(document: str, user_id: str) -> str:
    """Long-running analysis — runs in worker process."""
    llm = ChatOpenAI(model="gpt-4o")
    return llm.invoke(f"Analyze: {document}").content
'''
print(BACKGROUND_CODE[:700])


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 3: Rate Limiting + Cost Tracking
# INTERVIEW: Per-user controls to prevent abuse
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 60)
print("SECTION 3: Rate Limiting + Cost Tracking")
print("=" * 60)

RATE_COST_CODE = '''\
from fastapi import Request, HTTPException
from collections import defaultdict, deque
from datetime import datetime, timedelta

class AIRateLimiter:
    """
    INTERVIEW: Sliding window rate limiter.
    Track requests per user per minute.
    Different limits for free vs paid users.
    """
    LIMITS = {
        "free": {"rpm": 10,  "tpm": 50_000,  "daily_cost": 0.50},
        "paid": {"rpm": 100, "tpm": 500_000, "daily_cost": 50.0},
    }

    def __init__(self):
        self.requests = defaultdict(deque)   # user_id → deque of timestamps
        self.tokens   = defaultdict(list)    # user_id → [(timestamp, count)]
        self.costs    = defaultdict(float)   # user_id:date → daily cost

    async def check_and_track(
        self, user_id: str, tier: str, estimated_tokens: int
    ):
        limits = self.LIMITS[tier]
        now    = datetime.now()
        cutoff = now - timedelta(minutes=1)

        # Evict old requests
        reqs = self.requests[user_id]
        while reqs and reqs[0] < cutoff:
            reqs.popleft()

        # Check RPM
        if len(reqs) >= limits["rpm"]:
            retry_after = int(60 - (now - reqs[0]).seconds) + 1
            raise HTTPException(429, detail={
                "error":       "rate_limit_exceeded",
                "retry_after": retry_after,
                "message":     f"Rate limit: {limits['rpm']} requests/minute",
            })

        # Check TPM
        toks = [(ts, n) for ts, n in self.tokens[user_id] if ts >= cutoff]
        total_tokens = sum(n for _, n in toks)
        if total_tokens + estimated_tokens > limits["tpm"]:
            raise HTTPException(429, detail={"error": "token_limit_exceeded"})

        # Record
        reqs.append(now)
        self.tokens[user_id] = toks + [(now, estimated_tokens)]

    def record_cost(self, user_id: str, cost: float) -> float:
        date_key = f"{user_id}:{datetime.now().date()}"
        self.costs[date_key] += cost
        return self.costs[date_key]

    def get_daily_usage(self, user_id: str) -> dict:
        date_key = f"{user_id}:{datetime.now().date()}"
        return {
            "date":      datetime.now().date().isoformat(),
            "cost_usd":  self.costs.get(date_key, 0),
            "requests":  len(self.requests[user_id]),
        }
'''
print(RATE_COST_CODE[:700])


# Demo cost tracking
PRICING = {
    "gpt-4o":       {"input": 5.0,  "output": 15.0},    # per 1M tokens
    "gpt-4o-mini":  {"input": 0.15, "output": 0.60},
    "claude-sonnet":{"input": 3.0,  "output": 15.0},
}


def estimate_cost(input_tokens: int, output_tokens: int, model: str = "gpt-4o-mini") -> float:
    pricing = PRICING.get(model, PRICING["gpt-4o-mini"])
    return (input_tokens * pricing["input"] + output_tokens * pricing["output"]) / 1_000_000


print("\n  Cost estimation for typical requests:")
scenarios = [
    ("Simple chat (200in, 100out)", 200, 100),
    ("RAG query (2000in, 500out)",  2000, 500),
    ("Code review (4000in, 1000out)", 4000, 1000),
    ("1000 simple chats/day",       200_000, 100_000),
]
for desc, inp, out in scenarios:
    c_mini   = estimate_cost(inp, out, "gpt-4o-mini")
    c_4o     = estimate_cost(inp, out, "gpt-4o")
    print(f"  {desc:<40}: mini=${c_mini:.4f}  gpt-4o=${c_4o:.4f}")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 4: Complete FastAPI + AI Service
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 60)
print("SECTION 4: Production AI Service Template")
print("=" * 60)

COMPLETE_SERVICE = '''\
# main.py — Production-ready AI service

from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from contextlib import asynccontextmanager
import os, logging

logger = logging.getLogger(__name__)

# ── Lifecycle ──────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await db.connect()
    await redis.connect()
    logger.info("AI service started")
    yield
    # Shutdown
    await db.disconnect()
    await redis.disconnect()

app = FastAPI(
    title        = "AI Service API",
    version      = "1.0.0",
    lifespan     = lifespan,
    docs_url     = "/docs",
    redoc_url    = "/redoc",
)

# ── Middleware ─────────────────────────────────────────────────
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"])

# ── Router versioning ─────────────────────────────────────────
from fastapi import APIRouter

v1 = APIRouter(prefix="/v1", tags=["v1"])
v2 = APIRouter(prefix="/v2", tags=["v2"])

@v1.post("/chat")
async def chat_v1(req: ChatRequest, ...):
    # V1: returns string
    ...

@v2.post("/chat")
async def chat_v2(req: ChatRequestV2, ...):
    # V2: returns structured response with metadata
    ...

app.include_router(v1)
app.include_router(v2)

# ── Health check ──────────────────────────────────────────────
@app.get("/health")
async def health():
    checks = {
        "db":    await check_db(),
        "llm":   await check_llm_connectivity(),
        "cache": await check_redis(),
    }
    all_ok = all(v == "ok" for v in checks.values())
    return {"status": "healthy" if all_ok else "degraded", "checks": checks}

# ── Metrics ───────────────────────────────────────────────────
from prometheus_client import Counter, Histogram
requests = Counter("ai_requests_total", "Total AI requests", ["model", "endpoint"])
latency  = Histogram("ai_request_duration_seconds", "LLM latency", ["model"])
'''
print(COMPLETE_SERVICE[:700])


print("\n" + "=" * 60)
print("AI API DESIGN INTERVIEW SUMMARY:")
print("  Sync: POST /chat → await LLM → JSON (simple, blocks till done)")
print("  Streaming: StreamingResponse + AsyncGenerator → SSE tokens")
print("  Background: BackgroundTasks (small) or Celery+Redis (large scale)")
print("  Rate limit: sliding window RPM + TPM per user tier")
print("  Cost tracking: tokens × price per model, daily budgets per user")
print("  Versioning: APIRouter prefix /v1, /v2 for breaking changes")
print("  Health: check DB + LLM connectivity + cache in /health endpoint")
print("=" * 60)
