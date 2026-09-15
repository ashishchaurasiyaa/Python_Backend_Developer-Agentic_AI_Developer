"""
DAY 50 — contextvars: ContextVar for Async-Safe Context
Architecture Level: Senior Python Backend + Agentic AI

WHY THIS MATTERS:
- FastAPI uses contextvars internally for request state
- SQLAlchemy async sessions use it for session scoping
- Agents use it to pass trace_id / user_id through call chains
- threading.local() breaks in async code — ContextVar fixes this
"""

import asyncio
import contextvars
import uuid
from typing import Optional


# ═══════════════════════════════════════════════════════
# PART A: The Problem — threading.local vs ContextVar
# ═══════════════════════════════════════════════════════

# ─────────────────────────────────────────────
# 1. WHY threading.local() FAILS in async code
# ─────────────────────────────────────────────

# threading.local stores data per-THREAD.
# In async code, multiple coroutines run on the SAME thread.
# So threading.local is SHARED across all coroutines → data leaks.

import threading

thread_local = threading.local()

async def bad_handler(request_id: str):
    thread_local.request_id = request_id   # DANGER: shared across coroutines!
    await asyncio.sleep(0.01)              # another coroutine can overwrite it here
    return thread_local.request_id         # may return wrong request_id!


# ─────────────────────────────────────────────
# 2. ContextVar — the correct async-safe solution
# ─────────────────────────────────────────────

# ContextVar is isolated per asyncio Task (coroutine execution context)
# Each Task gets its own copy — no leakage between requests

request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar(
    "request_id",
    default="no-request"
)

async def correct_handler(request_id: str):
    request_id_var.set(request_id)         # safe: isolated to THIS task
    await asyncio.sleep(0.01)
    return request_id_var.get()            # always returns THIS task's value


async def demo_isolation():
    print("\n=== ContextVar Isolation Demo ===")
    # Run two handlers concurrently — they should NOT interfere
    results = await asyncio.gather(
        correct_handler("REQ-001"),
        correct_handler("REQ-002"),
        correct_handler("REQ-003"),
    )
    print(f"Results: {results}")
    # Output: ['REQ-001', 'REQ-002', 'REQ-003'] — always correct


asyncio.run(demo_isolation())


# ═══════════════════════════════════════════════════════
# PART B: ContextVar API
# ═══════════════════════════════════════════════════════

# ─────────────────────────────────────────────
# 1. Basic API: set / get / reset
# ─────────────────────────────────────────────

user_id_var: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "user_id", default=None
)

# set() returns a Token — use it to RESET back to previous value
token = user_id_var.set("user-123")
print(f"\nuser_id = {user_id_var.get()}")   # user-123

# Reset to previous value (None)
user_id_var.reset(token)
print(f"after reset: {user_id_var.get()}")  # None


# ─────────────────────────────────────────────
# 2. get() with default
# ─────────────────────────────────────────────

trace_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("trace_id")

# get(default) — safe fallback when not set
trace = trace_id_var.get("auto-" + uuid.uuid4().hex[:8])
print(f"trace_id fallback: {trace}")


# ═══════════════════════════════════════════════════════
# PART C: Real-World Pattern — FastAPI Request Context
# ═══════════════════════════════════════════════════════

# ─────────────────────────────────────────────
# 1. Middleware sets context, handlers read it
# ─────────────────────────────────────────────

# In FastAPI, middleware runs before each request handler:
#
# app = FastAPI()
#
# @app.middleware("http")
# async def request_context_middleware(request: Request, call_next):
#     request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
#     user_id = request.state.user_id  # set by auth middleware
#
#     # Set context for this request's task
#     token_rid = request_id_var.set(request_id)
#     token_uid = user_id_var.set(user_id)
#     try:
#         response = await call_next(request)
#         return response
#     finally:
#         request_id_var.reset(token_rid)
#         user_id_var.reset(token_uid)
#
#
# @app.get("/orders")
# async def get_orders():
#     # No need to pass request_id — just read from context
#     rid = request_id_var.get()
#     uid = user_id_var.get()
#     logger.info(f"[{rid}] Fetching orders for user {uid}")
#     orders = await order_service.get_for_user(uid)
#     return orders


# ─────────────────────────────────────────────
# 2. Structured logging with ContextVar
# ─────────────────────────────────────────────

import logging

class ContextFilter(logging.Filter):
    """Inject request_id and user_id into every log record automatically."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get("no-request")
        record.user_id    = user_id_var.get("anonymous")
        return True


def setup_context_logger() -> logging.Logger:
    logger = logging.getLogger("app")
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter(
        "[%(request_id)s] [%(user_id)s] %(levelname)s: %(message)s"
    ))
    logger.addFilter(ContextFilter())
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)
    return logger


logger = setup_context_logger()

async def handle_request(req_id: str, uid: str):
    token1 = request_id_var.set(req_id)
    token2 = user_id_var.set(uid)
    try:
        logger.info("Processing request")
        await asyncio.sleep(0.001)
        logger.info("Request complete")
    finally:
        request_id_var.reset(token1)
        user_id_var.reset(token2)

asyncio.run(handle_request("req-abc", "user-42"))


# ═══════════════════════════════════════════════════════
# PART D: Agentic AI Pattern — Trace Propagation
# ═══════════════════════════════════════════════════════

# ─────────────────────────────────────────────
# 1. Pass trace_id through entire agent call chain
# ─────────────────────────────────────────────

trace_id_ctx: contextvars.ContextVar[str] = contextvars.ContextVar(
    "trace_id", default="no-trace"
)
agent_name_ctx: contextvars.ContextVar[str] = contextvars.ContextVar(
    "agent_name", default="unknown"
)


async def call_llm(prompt: str) -> str:
    """Simulated LLM call — reads trace context automatically."""
    trace = trace_id_ctx.get()
    agent = agent_name_ctx.get()
    print(f"  [LLM] trace={trace} agent={agent} prompt='{prompt[:30]}...'")
    await asyncio.sleep(0.01)
    return f"Response to: {prompt}"


async def search_tool(query: str) -> list[str]:
    """Simulated tool call — same context propagates."""
    trace = trace_id_ctx.get()
    print(f"  [TOOL:search] trace={trace} query='{query}'")
    await asyncio.sleep(0.005)
    return [f"Result 1 for {query}", f"Result 2 for {query}"]


async def research_agent(task: str) -> str:
    token = agent_name_ctx.set("research_agent")
    try:
        results = await search_tool(task)
        summary = await call_llm(f"Summarize: {results}")
        return summary
    finally:
        agent_name_ctx.reset(token)


async def orchestrator(user_query: str):
    """Top-level agent that sets trace_id and dispatches sub-agents."""
    trace_id = f"trace-{uuid.uuid4().hex[:8]}"
    token = trace_id_ctx.set(trace_id)
    try:
        print(f"\n[ORCHESTRATOR] Starting trace: {trace_id}")
        result = await research_agent(user_query)
        print(f"[ORCHESTRATOR] Done: {result[:50]}")
    finally:
        trace_id_ctx.reset(token)


asyncio.run(orchestrator("Python async patterns"))


# ═══════════════════════════════════════════════════════
# PART E: contextvars.copy_context() — snapshot and run
# ═══════════════════════════════════════════════════════

# ─────────────────────────────────────────────
# 1. copy_context() — run code with current context in a new thread
# ─────────────────────────────────────────────

import concurrent.futures

request_id_var.set("req-snapshot-999")

ctx = contextvars.copy_context()  # snapshot current context

def sync_task():
    """This sync function runs in a thread but inherits async context."""
    rid = request_id_var.get()
    print(f"\n[THREAD] inherited request_id = {rid}")
    return f"processed in thread with {rid}"

with concurrent.futures.ThreadPoolExecutor() as pool:
    # Run sync_task in thread pool WITH current context
    future = pool.submit(ctx.run, sync_task)
    result = future.result()
    print(f"Thread result: {result}")

# FastAPI uses this internally when calling sync route handlers:
# loop.run_in_executor(None, ctx.run, sync_handler)


# ═══════════════════════════════════════════════════════
# PART F: Interview Questions
# ═══════════════════════════════════════════════════════

"""
Q1: Why does threading.local() fail in async code?
    threading.local is per-thread. Async coroutines share a thread, so
    all coroutines see the same local — data leaks between requests.

Q2: What is ContextVar and when do you use it?
    ContextVar stores data per asyncio Task (coroutine context).
    Use it when you need request-scoped data (request_id, user_id, trace_id)
    that must propagate through async call chains without explicit passing.

Q3: What does set() return and why does it matter?
    set() returns a Token. Use token to reset() back to the previous value —
    essential in middleware/finally blocks to avoid context leaks.

Q4: How do you pass ContextVar values to a thread pool?
    Use contextvars.copy_context() to snapshot current context,
    then pool.submit(ctx.run, fn) — FastAPI does this internally.

Q5: How does FastAPI use ContextVar internally?
    Request middleware sets request-scoped vars. FastAPI also uses
    ContextVar for its dependency injection scoping per request.
"""
