# FastAPI — LLM Integration: OpenAI, Claude, Streaming + Production Patterns
**Phase 2 FastAPI | Senior Backend + Agentic AI**

## Quick Concepts
- **LLM API** = HTTP call to OpenAI/Anthropic — high latency (1-30s), token-priced, stateless
- **Streaming** = Server-Sent Events (SSE) — token-by-token response, better UX
- **Async SDK** = `AsyncOpenAI`, `AsyncAnthropic` — non-blocking calls (mandatory for FastAPI)
- **Token usage** = `prompt_tokens + completion_tokens` — track for cost
- **Retries** = exponential backoff for transient errors (429, 503, network)
- **Timeouts** = LLM can take 30+ seconds — set explicit timeouts
- **LiteLLM** = unified SDK for 100+ providers (OpenAI, Claude, Gemini, local models)

---

## Interview Questions & Answers

### Q1: FastAPI mein OpenAI/Claude integrate kaise karte hain (production-ready)?

**Answer:**
```python
import os
from contextlib import asynccontextmanager
from typing import Annotated

from anthropic import AsyncAnthropic
from fastapi import Depends, FastAPI, HTTPException
from openai import AsyncOpenAI
from pydantic import BaseModel, Field

# ─── Singleton Clients (reused across requests) ───
class LLMClients:
    openai: AsyncOpenAI | None = None
    anthropic: AsyncAnthropic | None = None

clients = LLMClients()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: create clients once
    clients.openai = AsyncOpenAI(
        api_key=os.environ["OPENAI_API_KEY"],
        timeout=30.0,  # explicit timeout
        max_retries=2,
    )
    clients.anthropic = AsyncAnthropic(
        api_key=os.environ["ANTHROPIC_API_KEY"],
        timeout=30.0,
        max_retries=2,
    )
    yield
    # Shutdown: close clients
    await clients.openai.close()
    await clients.anthropic.close()

app = FastAPI(lifespan=lifespan)

# ─── Models ───
class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=10_000)
    model: str = "claude-opus-4-7"
    temperature: float = Field(0.7, ge=0.0, le=2.0)
    max_tokens: int = Field(1024, ge=1, le=8192)

class ChatResponse(BaseModel):
    text: str
    model: str
    input_tokens: int
    output_tokens: int
    cost_usd: float

# ─── Endpoint ───
@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    try:
        response = await clients.anthropic.messages.create(
            model=req.model,
            max_tokens=req.max_tokens,
            temperature=req.temperature,
            messages=[{"role": "user", "content": req.message}],
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"LLM error: {e}")

    return ChatResponse(
        text=response.content[0].text,
        model=response.model,
        input_tokens=response.usage.input_tokens,
        output_tokens=response.usage.output_tokens,
        cost_usd=_calc_cost(response.usage.input_tokens, response.usage.output_tokens, req.model),
    )
```

**Key points:**
- Async SDK **mandatory** — sync SDK blocks FastAPI event loop
- Singleton client in `lifespan` — connection pool reuse
- Explicit `timeout` — LLMs hang, can kill workers
- `max_retries=2` — built-in retry for transient errors

---

### Q2: Token-by-token streaming kaise implement karte hain (SSE)?

**Answer:** Server-Sent Events use karo. Real-time UX for chat apps.

```python
from fastapi.responses import StreamingResponse
import json

@app.post("/chat/stream")
async def chat_stream(req: ChatRequest):
    async def event_generator():
        try:
            async with clients.anthropic.messages.stream(
                model=req.model,
                max_tokens=req.max_tokens,
                messages=[{"role": "user", "content": req.message}],
            ) as stream:
                async for text_chunk in stream.text_stream:
                    # SSE format: "data: {json}\n\n"
                    yield f"data: {json.dumps({'text': text_chunk})}\n\n"

                # Final message with usage info
                final = await stream.get_final_message()
                usage = {
                    "type": "done",
                    "input_tokens": final.usage.input_tokens,
                    "output_tokens": final.usage.output_tokens,
                }
                yield f"data: {json.dumps(usage)}\n\n"

        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # disable Nginx buffering
            "Connection": "keep-alive",
        },
    )
```

**Frontend consumes:**
```javascript
const response = await fetch('/chat/stream', {
    method: 'POST',
    body: JSON.stringify({message: "Hello"}),
});
const reader = response.body.getReader();
const decoder = new TextDecoder();

while (true) {
    const {done, value} = await reader.read();
    if (done) break;
    const chunk = decoder.decode(value);
    // Parse "data: {...}\n\n" lines
    chunk.split('\n\n').forEach(line => {
        if (line.startsWith('data: ')) {
            const data = JSON.parse(line.slice(6));
            console.log(data.text);
        }
    });
}
```

**Gotchas:**
- ⚠️ Nginx default buffers responses → set `X-Accel-Buffering: no`
- ⚠️ Cloudflare buffers below Enterprise tier → use WebSocket alternative
- ⚠️ `Connection: keep-alive` required for long streams

---

### Q3: Async parallel LLM calls (multiple prompts at once)?

**Answer:** `asyncio.gather` use karo. CPU-bound nahi hai, isliye true parallelism milta hai.

```python
import asyncio
from typing import List

class BatchRequest(BaseModel):
    prompts: List[str] = Field(..., max_length=10)  # cap to prevent abuse

class BatchResponse(BaseModel):
    results: List[str]
    total_input_tokens: int
    total_output_tokens: int

async def _single_call(prompt: str) -> tuple[str, int, int]:
    response = await clients.anthropic.messages.create(
        model="claude-haiku-4-5",  # cheaper for batch
        max_tokens=512,
        messages=[{"role": "user", "content": prompt}],
    )
    return (
        response.content[0].text,
        response.usage.input_tokens,
        response.usage.output_tokens,
    )

@app.post("/chat/batch", response_model=BatchResponse)
async def chat_batch(req: BatchRequest):
    # Parallel execution
    results = await asyncio.gather(
        *[_single_call(p) for p in req.prompts],
        return_exceptions=True,  # one failure doesn't kill batch
    )

    texts, input_total, output_total = [], 0, 0
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
```

**Concurrency limit pattern** (avoid rate limits):
```python
SEMAPHORE = asyncio.Semaphore(5)  # max 5 concurrent calls

async def _bounded_call(prompt: str):
    async with SEMAPHORE:
        return await _single_call(prompt)
```

---

### Q4: Retry logic with exponential backoff?

**Answer:** Use `tenacity` library — production standard.

```python
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)
from anthropic import APIConnectionError, APIStatusError, RateLimitError

RETRY_EXCEPTIONS = (RateLimitError, APIConnectionError)

async def call_llm_with_retry(prompt: str) -> str:
    async for attempt in AsyncRetrying(
        retry=retry_if_exception_type(RETRY_EXCEPTIONS),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),  # 2s, 4s, 8s...
        reraise=True,
    ):
        with attempt:
            response = await clients.anthropic.messages.create(
                model="claude-opus-4-7",
                max_tokens=1024,
                messages=[{"role": "user", "content": prompt}],
            )
            return response.content[0].text
```

**Retry decision matrix:**
| Error | Retry? | Reason |
|---|---|---|
| `RateLimitError` (429) | ✅ Yes, longer wait | Will succeed after quota resets |
| `APIConnectionError` | ✅ Yes | Network glitch |
| `APITimeoutError` | ✅ Yes (max 2x) | Could be transient |
| `APIStatusError` (500-503) | ✅ Yes | Server issue |
| `BadRequestError` (400) | ❌ No | Bug in your code |
| `AuthenticationError` (401) | ❌ No | Wrong API key |
| `PermissionDeniedError` (403) | ❌ No | Need to fix permissions |

---

### Q5: Token usage + cost tracking middleware?

**Answer:** Per-user cost tracking is **critical** for SaaS. Redis-based counter pattern.

```python
import redis.asyncio as aioredis
from datetime import datetime
from decimal import Decimal

# Pricing per 1M tokens (update from provider docs)
PRICING = {
    "claude-opus-4-7": {"input": Decimal("15.00"), "output": Decimal("75.00")},
    "claude-sonnet-4-6": {"input": Decimal("3.00"), "output": Decimal("15.00")},
    "claude-haiku-4-5": {"input": Decimal("0.80"), "output": Decimal("4.00")},
    "gpt-4o": {"input": Decimal("2.50"), "output": Decimal("10.00")},
    "gpt-4o-mini": {"input": Decimal("0.15"), "output": Decimal("0.60")},
}

def _calc_cost(input_tok: int, output_tok: int, model: str) -> float:
    if model not in PRICING:
        return 0.0
    p = PRICING[model]
    cost = (Decimal(input_tok) * p["input"] + Decimal(output_tok) * p["output"]) / Decimal(1_000_000)
    return float(cost)

# ─── Redis tracking ───
redis_pool = aioredis.ConnectionPool.from_url("redis://localhost:6379")

async def track_usage(user_id: int, model: str, input_tok: int, output_tok: int):
    r = aioredis.Redis(connection_pool=redis_pool)
    cost = _calc_cost(input_tok, output_tok, model)
    today = datetime.utcnow().strftime("%Y-%m-%d")
    month = datetime.utcnow().strftime("%Y-%m")

    pipe = r.pipeline()
    pipe.hincrby(f"usage:user:{user_id}:{today}", "input_tokens", input_tok)
    pipe.hincrby(f"usage:user:{user_id}:{today}", "output_tokens", output_tok)
    pipe.hincrbyfloat(f"usage:user:{user_id}:{today}", "cost_usd", cost)
    pipe.expire(f"usage:user:{user_id}:{today}", 60 * 60 * 24 * 90)  # 90 days

    # Monthly aggregate
    pipe.hincrbyfloat(f"usage:user:{user_id}:{month}", "cost_usd", cost)
    pipe.expire(f"usage:user:{user_id}:{month}", 60 * 60 * 24 * 400)

    await pipe.execute()

# ─── Quota enforcement ───
DAILY_LIMIT_USD = 5.0

async def check_quota(user_id: int):
    r = aioredis.Redis(connection_pool=redis_pool)
    today = datetime.utcnow().strftime("%Y-%m-%d")
    spent = await r.hget(f"usage:user:{user_id}:{today}", "cost_usd")
    if spent and float(spent) >= DAILY_LIMIT_USD:
        raise HTTPException(status_code=402, detail="Daily LLM quota exceeded")

@app.post("/chat/v2")
async def chat_with_tracking(req: ChatRequest, user_id: int = Depends(get_current_user_id)):
    await check_quota(user_id)
    response = await clients.anthropic.messages.create(
        model=req.model,
        max_tokens=req.max_tokens,
        messages=[{"role": "user", "content": req.message}],
    )
    await track_usage(
        user_id, req.model,
        response.usage.input_tokens,
        response.usage.output_tokens,
    )
    return {"text": response.content[0].text}
```

---

### Q6: LiteLLM se multi-provider routing kaise karte hain?

**Answer:** Single SDK, fallback chain — production resilience.

```python
import litellm
from litellm import acompletion

litellm.set_verbose = False
litellm.success_callback = ["langsmith"]  # observability

# ─── Provider fallback chain ───
FALLBACK_MODELS = [
    "anthropic/claude-opus-4-7",      # primary
    "openai/gpt-4o",                   # if Claude fails
    "openai/gpt-4o-mini",              # cheap fallback
]

@app.post("/chat/resilient")
async def chat_resilient(req: ChatRequest):
    response = await acompletion(
        model=FALLBACK_MODELS[0],
        messages=[{"role": "user", "content": req.message}],
        fallbacks=FALLBACK_MODELS[1:],  # auto-fallback
        timeout=30,
        num_retries=2,
    )
    return {
        "text": response.choices[0].message.content,
        "model_used": response.model,
        "input_tokens": response.usage.prompt_tokens,
        "output_tokens": response.usage.completion_tokens,
    }
```

**Why LiteLLM:**
- ✅ Same interface for OpenAI, Claude, Gemini, Mistral, Ollama
- ✅ Automatic fallbacks
- ✅ Cost tracking built-in
- ✅ Caching support (Redis)
- ✅ Routing rules (cheap vs smart models)

---

### Q7: Background LLM jobs (long-running tasks) kaise handle karte hain?

**Answer:** Celery + Redis. LLM call >5 min ho sakti hai — HTTP timeout problem.

```python
from celery import Celery
from uuid import uuid4

celery_app = Celery("llm_tasks", broker="redis://localhost:6379/0", backend="redis://localhost:6379/1")

@celery_app.task(bind=True, max_retries=2)
def process_long_llm_task(self, prompt: str, user_id: int):
    """Sync version for Celery worker — uses sync SDK."""
    from anthropic import Anthropic
    client = Anthropic()

    try:
        response = client.messages.create(
            model="claude-opus-4-7",
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}],
            timeout=120,
        )
        return {
            "status": "completed",
            "text": response.content[0].text,
            "tokens": response.usage.input_tokens + response.usage.output_tokens,
        }
    except Exception as e:
        raise self.retry(exc=e, countdown=10)

# ─── FastAPI endpoints ───
@app.post("/llm/submit")
async def submit_job(req: ChatRequest, user_id: int = Depends(get_current_user_id)):
    task = process_long_llm_task.delay(req.message, user_id)
    return {"task_id": task.id, "status": "queued"}

@app.get("/llm/status/{task_id}")
async def job_status(task_id: str):
    task = celery_app.AsyncResult(task_id)
    if task.ready():
        return {"status": "done", "result": task.result}
    return {"status": task.state.lower()}
```

---

### Q8: Streaming + tracking ko combine kaise karte hain?

**Answer:** Stream me end pe usage info aati hai — final callback me track karo.

```python
@app.post("/chat/stream/tracked")
async def chat_stream_tracked(
    req: ChatRequest,
    user_id: int = Depends(get_current_user_id),
):
    await check_quota(user_id)

    async def event_generator():
        input_tok, output_tok = 0, 0
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

                yield f"data: {json.dumps({'type':'done', 'in': input_tok, 'out': output_tok})}\n\n"
        finally:
            # Track usage even if client disconnects mid-stream
            if input_tok > 0:
                await track_usage(user_id, req.model, input_tok, output_tok)

    return StreamingResponse(event_generator(), media_type="text/event-stream")
```

---

## Production Gotchas

| Gotcha | Fix |
|---|---|
| Sync SDK in async route | Always use `AsyncOpenAI`/`AsyncAnthropic` |
| No timeout set | `timeout=30` minimum, 120 for long context |
| API key in code | Use env vars + `python-dotenv` + secret manager (Vault/AWS) |
| Client recreated per request | Use `lifespan` for singleton |
| Streaming hangs in Nginx | `X-Accel-Buffering: no` header |
| Token usage not tracked | Implement `track_usage()` middleware on every call |
| No rate limit on user | Add quota check before each call |
| Long context blows memory | Stream input from disk; use Files API |
| Prompts not cached | Anthropic prompt caching = 90% cost saving |

---

## Anthropic Prompt Caching (huge cost saver)

```python
# Cache system prompt + large context — pay 10% on cache hits
response = await clients.anthropic.messages.create(
    model="claude-opus-4-7",
    max_tokens=1024,
    system=[
        {
            "type": "text",
            "text": "You are a senior backend engineer...",  # static
        },
        {
            "type": "text",
            "text": LARGE_DOCUMENTATION,  # 50K tokens
            "cache_control": {"type": "ephemeral"},  # 5-min TTL
        },
    ],
    messages=[{"role": "user", "content": req.message}],
)
# First call: full price
# Subsequent calls within 5 min: ~10% of input price
```

---

## Senior-level Checklist

- [ ] Async SDK used (never sync in FastAPI route)
- [ ] Singleton client via `lifespan`
- [ ] Explicit timeout per call
- [ ] Retry with exponential backoff (tenacity)
- [ ] Per-user token + cost tracking in Redis
- [ ] Daily/monthly quota enforcement
- [ ] Streaming with SSE + Nginx buffering disabled
- [ ] Multi-provider fallback (LiteLLM)
- [ ] Background jobs for long tasks (Celery)
- [ ] Prompt caching enabled
- [ ] Structured logging (input/output/tokens/latency)
- [ ] Observability hook (LangSmith/Langfuse)

---

## Related Docs
- `26_sse_deep.md` — SSE fundamentals
- `Phase2_Caching/06_semantic_caching_llm.md` — semantic cache layer
- `Phase2_Database/18_pgvector_ai_workloads.md` — vector DB for context
- `32_function_calling_endpoints.md` — next: tool use
- `33_prompt_injection_security.md` — security layer
