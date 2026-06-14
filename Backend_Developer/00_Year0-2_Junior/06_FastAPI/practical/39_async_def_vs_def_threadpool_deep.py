"""
FastAPI — `async def` vs `def`: Event Loop vs Threadpool (Deep Dive)
=====================================================================

Core truth:
    Writing `async def` does NOT make your code faster.
    Putting a blocking call inside `async def` FREEZES the entire event loop.

FastAPI (Starlette) inspects every endpoint with `inspect.iscoroutinefunction()`:
  - `async def`  → runs directly on the event loop (main thread).
                   Concurrency comes from `await` (cooperative switching).
  - `def`        → offloaded to anyio worker threadpool (default: 40 threads).
                   Concurrency comes from OS threads.

Execution paths:
  async def path                        def (sync) path
  ──────────────                        ──────────────────────────────
  Request arrives                       Request arrives
    │                                     │
  Event loop schedules coroutine        Starlette: run_in_threadpool(endpoint)
    │                                     │
  Code runs until first `await`         anyio pool picks one thread
    │                                     │
  `await` → loop switches to next req   Thread runs sync code
    │                                   (block here = only THIS thread stalls)
  I/O done → coroutine resumes            │
    │                                   Thread finishes → result returned
  Response                              Response

Run:
    pip install fastapi uvicorn[standard] httpx anyio starlette
    uvicorn 39_async_def_vs_def_threadpool_deep:app --reload
"""

import asyncio
import inspect
import logging
import time
from concurrent.futures import ProcessPoolExecutor
from contextlib import asynccontextmanager
from functools import partial, wraps
from typing import Any

import anyio.to_thread
from fastapi import Depends, FastAPI, Request
from starlette.concurrency import run_in_threadpool

# pip install httpx
import httpx

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)


# ==========================================================================
# 1. APPLICATION LIFESPAN — shared resources + threadpool tuning
# ==========================================================================

# A single shared ProcessPoolExecutor for CPU-bound tasks (created once at startup).
# Creating it per-request would spawn/kill processes on every call — very expensive.
_process_pool: ProcessPoolExecutor | None = None


@asynccontextmanager
async def lifespan(application: FastAPI):
    """
    Startup / shutdown lifecycle manager.

    Three things happen here:
      1. The anyio threadpool limit is raised from the default 40 to 80.
         This is appropriate when many `def` endpoints make short, I/O-bound
         blocking calls and the default ceiling is too low.
         WARNING: raise this only after measuring — higher limit × DB connections
         can exceed postgres max_connections.
      2. A shared httpx.AsyncClient is created for async HTTP calls.
         One client per application, not one per request (avoids repeated
         TCP/TLS handshakes).
      3. A ProcessPoolExecutor is started for CPU-bound work that must complete
         inside a request-response cycle.
    """
    global _process_pool

    # --- Tune anyio threadpool (default = 40 tokens) ---
    limiter = anyio.to_thread.current_default_thread_limiter()
    limiter.total_tokens = 80
    log.info("anyio threadpool limit set to %d", limiter.total_tokens)

    # --- Shared async HTTP client ---
    application.state.http = httpx.AsyncClient(timeout=10.0)
    log.info("Shared httpx.AsyncClient created")

    # --- CPU process pool (4 workers) ---
    _process_pool = ProcessPoolExecutor(max_workers=4)
    log.info("ProcessPoolExecutor started with 4 workers")

    yield  # application runs

    # --- Teardown ---
    await application.state.http.aclose()
    _process_pool.shutdown(wait=False)
    log.info("Resources cleaned up")


app = FastAPI(
    title="async def vs def — Deep Dive",
    description="Illustrative module covering the event-loop vs threadpool execution model.",
    lifespan=lifespan,
)


# ==========================================================================
# 2. THE TRAP — async def + blocking call = event loop frozen
# ==========================================================================

@app.get(
    "/disaster",
    summary="DISASTER: async def + blocking sleep",
    tags=["Trap Demonstration"],
)
async def disaster():
    """
    Anti-pattern: blocking call inside async def.

    `time.sleep` holds the event loop thread for 3 seconds.
    During this time NO other request — not even `/health` — can be processed.
    With 10 concurrent requests this endpoint takes ~30 sec total (serial!).

    Symptoms in production:
      - p99 latency spike across ALL endpoints simultaneously
      - Health checks timeout → Kubernetes pod restart → cascading failure
      - CPU near 0% but everything is slow (loop is blocked, not busy)
    """
    log.warning("DISASTER endpoint called — event loop will be blocked for 3s")
    time.sleep(3)          # blocks the single event-loop thread
    return {"endpoint": "/disaster", "note": "event loop was frozen for 3s"}


@app.get(
    "/safe-sync",
    summary="SAFE: sync def + blocking call → threadpool",
    tags=["Correct Patterns"],
)
def safe_sync():
    """
    Correct pattern when using blocking libraries (requests, sync SQLAlchemy, boto3).

    FastAPI detects this is a plain `def` and offloads it to anyio threadpool.
    `time.sleep` blocks only one thread — the other 79 remain available.
    With 10 concurrent requests this endpoint takes ~3 sec total (parallel).
    """
    log.info("safe_sync called — threadpool thread blocked, event loop free")
    time.sleep(3)
    return {"endpoint": "/safe-sync", "note": "only 1 threadpool thread was blocked"}


@app.get(
    "/best-async",
    summary="BEST: async def + await-able I/O",
    tags=["Correct Patterns"],
)
async def best_async():
    """
    Ideal pattern when using async-native libraries (httpx, asyncpg, aioredis, motor).

    `await asyncio.sleep` yields control back to the event loop.
    The loop can interleave thousands of concurrent coroutines — no threads needed.
    With 10 concurrent requests this endpoint takes ~3 sec total (parallel),
    using zero threadpool slots.
    """
    await asyncio.sleep(3)
    return {"endpoint": "/best-async", "note": "event loop was free during the entire wait"}


# ==========================================================================
# 3. ESCAPE HATCHES — safely calling blocking code from async context
# ==========================================================================

def _legacy_generate_report(user_id: int) -> dict[str, Any]:
    """
    Simulates a legacy synchronous function (e.g., PDF generation, a sync DB call,
    a boto3 S3 upload) that cannot be made async without a rewrite.
    """
    time.sleep(0.5)        # simulate ~500ms I/O
    return {"report": f"report_for_user_{user_id}", "size_bytes": 12_345}


# --- 3.1: run_in_threadpool (Starlette / FastAPI recommended) ---

@app.get(
    "/report/threadpool/{user_id}",
    summary="run_in_threadpool — recommended FastAPI escape hatch",
    tags=["Escape Hatches"],
)
async def report_via_threadpool(user_id: int):
    """
    `run_in_threadpool` is the FastAPI/Starlette-recommended way to call a
    blocking function from inside an `async def` endpoint.

    It uses the SAME anyio pool that `def` endpoints use, so your capacity
    planning (total_tokens) covers both automatically.
    """
    report = await run_in_threadpool(_legacy_generate_report, user_id)
    return {"source": "run_in_threadpool", **report}


# --- 3.2: asyncio.to_thread (stdlib, Python 3.9+) ---

@app.get(
    "/report/to-thread/{user_id}",
    summary="asyncio.to_thread — stdlib alternative",
    tags=["Escape Hatches"],
)
async def report_via_to_thread(user_id: int):
    """
    `asyncio.to_thread` uses asyncio's default executor (NOT the anyio-managed
    pool that FastAPI uses for `def` endpoints).  It is functionally identical
    but draws from a separate pool — factor this into capacity math.

    Advantage over run_in_threadpool: supports keyword arguments directly.
    """
    result = await asyncio.to_thread(_legacy_generate_report, user_id=user_id)
    return {"source": "asyncio.to_thread", **result}


# ==========================================================================
# 4. CPU-BOUND WORK — ProcessPoolExecutor (not threadpool!)
# ==========================================================================

def _crunch_numbers(n: int) -> int:
    """
    Pure CPU-bound computation.

    Sending this to the threadpool does NOT help — the GIL ensures Python
    threads cannot execute bytecode in parallel.  This function must go to a
    separate OS process where it gets its own GIL.

    The function and its arguments must be picklable (no lambdas, no closures
    that capture local state) because ProcessPoolExecutor uses pickle to
    transfer data across process boundaries.
    """
    return sum(i * i for i in range(n))


@app.get(
    "/cpu-crunch/{n}",
    summary="CPU-bound work via ProcessPoolExecutor",
    tags=["Escape Hatches"],
)
async def cpu_crunch(n: int = 10_000_000):
    """
    For CPU-bound work that must complete inside the request-response cycle,
    use `loop.run_in_executor` with a `ProcessPoolExecutor`.

    Common mistake: `run_in_executor(None, fn)` uses the DEFAULT thread executor
    (not a process pool) — GIL contention still applies.  Always pass an
    explicit ProcessPoolExecutor for CPU work.

    For tasks that can tolerate being asynchronous (>1–2 sec), offloading to
    Celery / arq / RQ is a better architecture choice.
    """
    if _process_pool is None:
        return {"error": "process pool not initialised — did lifespan run?"}

    loop = asyncio.get_running_loop()
    result = await loop.run_in_executor(_process_pool, _crunch_numbers, n)
    return {"n": n, "result": result, "executor": "ProcessPoolExecutor"}


# ==========================================================================
# 5. ASYNC HTTP PROXY — shared AsyncClient (avoid per-request creation)
# ==========================================================================

@app.get(
    "/proxy",
    summary="Async HTTP proxy using shared httpx.AsyncClient",
    tags=["Correct Patterns"],
)
async def async_proxy(request: Request):
    """
    Anti-pattern: creating a new `httpx.AsyncClient()` per request.
      Each call incurs a fresh TCP + TLS handshake — adds 50–300 ms.

    Correct pattern: one shared client stored in `app.state` during lifespan.
      Connection pool is reused across requests for the same host.

    Even more important: NEVER use `requests.get(...)` inside `async def` —
    that is a sync HTTP call that blocks the event loop thread entirely.
    """
    client: httpx.AsyncClient = request.app.state.http
    # Using httpbin as a stable public echo service
    response = await client.get("https://httpbin.org/get", params={"source": "shared-client"})
    return {"status": response.status_code, "data": response.json()}


# ==========================================================================
# 6. SYNC DEPENDENCY vs ASYNC DEPENDENCY — threadpool consumption
# ==========================================================================

def get_db_session_sync():
    """
    Sync dependency — FastAPI runs this in the SAME threadpool that `def`
    endpoints use.  Each request using this dependency consumes one threadpool
    slot while the dependency runs.

    This is the correct pattern for sync SQLAlchemy (Session-based) at
    moderate scale (<500 RPS with fast queries).
    """
    # In real code: yield Session(); try: yield db; finally: db.close()
    log.debug("sync DB session dependency called (threadpool thread)")
    return {"driver": "sync_sqlalchemy", "session_id": id(object())}


async def get_db_session_async():
    """
    Async dependency — runs on the event loop, no threadpool slot consumed.

    This is the correct pattern for async SQLAlchemy 2.0 + asyncpg.
    Lazy-loading relationships will raise `MissingGreenlet` — use explicit
    `selectinload` / `joinedload` instead.
    """
    log.debug("async DB session dependency called (event loop coroutine)")
    # In real code: async with AsyncSession(engine) as session: yield session
    return {"driver": "asyncpg", "session_id": id(object())}


@app.get(
    "/users/{user_id}/sync-db",
    summary="def endpoint + sync SQLAlchemy dependency",
    tags=["Database Patterns"],
)
def get_user_sync(user_id: int, db=Depends(get_db_session_sync)):
    """
    Both the dependency and the endpoint run in the threadpool.
    Safe for blocking calls; valid at moderate scale.
    """
    return {"user_id": user_id, "db": db, "endpoint_type": "def (threadpool)"}


@app.get(
    "/users/{user_id}/async-db",
    summary="async def endpoint + async SQLAlchemy dependency",
    tags=["Database Patterns"],
)
async def get_user_async(user_id: int, db=Depends(get_db_session_async)):
    """
    Both the dependency and the endpoint run on the event loop.
    Scales to thousands of concurrent waits; use explicit eager-loading.
    """
    return {"user_id": user_id, "db": db, "endpoint_type": "async def (event loop)"}


# ==========================================================================
# 7. THREADPOOL EXHAUSTION — demonstrating the 40-thread ceiling
# ==========================================================================

@app.get(
    "/slow-report",
    summary="Slow sync endpoint — demonstrates threadpool saturation",
    tags=["Trap Demonstration"],
)
def slow_report():
    """
    Simulates a slow blocking DB query (10 sec) inside a `def` endpoint.

    With the default 40-thread limit:
      - 5 requests/sec × 10 sec/request = 50 threads needed at steady state
      - Only 40 available → 41st request queues, waiting for a free thread
      - Even `/fast-def` gets queued (same pool) → latency cliff for ALL sync endpoints

    Distinction (important for interviews):
      Event loop block  → ALL endpoints freeze instantly (async + sync)
      Threadpool exhaustion → only sync (`def`) endpoints queue; async endpoints
                              continue processing normally (different code path)
    """
    time.sleep(10)
    return {"endpoint": "/slow-report", "note": "exhausts threadpool at >4 concurrent callers"}


@app.get(
    "/fast-def",
    summary="Fast sync endpoint — victim of threadpool exhaustion from /slow-report",
    tags=["Trap Demonstration"],
)
def fast_def():
    """
    Takes <1 ms on its own, but gets queued behind /slow-report calls when the
    40-thread pool is saturated.  This is threadpool exhaustion, not event loop
    block — `/best-async` would still respond immediately.
    """
    return {"endpoint": "/fast-def", "note": "normally <1ms, but queued when pool is full"}


# ==========================================================================
# 8. ASYNCIO DEBUG MODE — detecting blocking callbacks at development time
# ==========================================================================

@app.get(
    "/debug-mode-info",
    summary="How to enable asyncio debug mode",
    tags=["Debugging"],
)
async def debug_mode_info():
    """
    In development, enable asyncio debug mode to catch accidental blocking calls.

    Any coroutine that holds the event loop for longer than
    `slow_callback_duration` (default 100 ms) generates a WARNING log entry.

    Enable via:
      PYTHONASYNCIODEBUG=1 uvicorn app:app

    Or programmatically (shown below — not applied here to avoid side-effects).
    """
    loop = asyncio.get_running_loop()
    return {
        "debug_mode_active": loop.get_debug(),
        "slow_callback_duration_sec": loop.slow_callback_duration,
        "how_to_enable": [
            "PYTHONASYNCIODEBUG=1 uvicorn app:app",
            "loop.set_debug(True) + loop.slow_callback_duration = 0.1",
        ],
    }


# ==========================================================================
# 9. INTROSPECTION HELPER — verify FastAPI's routing decision at runtime
# ==========================================================================

@app.get(
    "/routing-decision",
    summary="Introspect how FastAPI dispatches each endpoint",
    tags=["Debugging"],
)
async def routing_decision():
    """
    FastAPI uses `inspect.iscoroutinefunction()` to decide the execution path.
    This endpoint exposes that decision for each registered route so you can
    verify your application behaves as intended.
    """
    decisions = []
    for route in app.routes:
        endpoint = getattr(route, "endpoint", None)
        if endpoint is not None:
            decisions.append(
                {
                    "path": route.path,  # type: ignore[attr-defined]
                    "name": endpoint.__name__,
                    "is_coroutine": inspect.iscoroutinefunction(endpoint),
                    "execution_path": (
                        "event loop (async def)"
                        if inspect.iscoroutinefunction(endpoint)
                        else "anyio threadpool (def)"
                    ),
                }
            )
    return {"routes": decisions}


# ==========================================================================
# 10. DECISION REFERENCE — embedded as an API endpoint for quick recall
# ==========================================================================

@app.get(
    "/decision-table",
    summary="async def vs def decision table",
    tags=["Reference"],
)
async def decision_table():
    """
    The decision table to memorise for interviews and code reviews.
    """
    return {
        "combinations": [
            {
                "pattern": "async def + await-able I/O (httpx, asyncpg, aioredis, motor)",
                "verdict": "BEST",
                "why": "Event loop interleaves thousands of concurrent waits, zero thread overhead",
            },
            {
                "pattern": "def + blocking libs (requests, sync SQLAlchemy, boto3, pymongo)",
                "verdict": "OKAY",
                "why": "Threadpool absorbs up to ~80 concurrent blocking ops (tuned limit)",
            },
            {
                "pattern": "async def + blocking lib (requests, time.sleep, sync DB)",
                "verdict": "DISASTER",
                "why": "Event loop frozen — entire application serialises, all endpoints slow",
            },
            {
                "pattern": "CPU-bound work anywhere (def or async def)",
                "verdict": "USE ProcessPool",
                "why": "GIL prevents parallel bytecode; threads do not help. ProcessPool or Celery.",
            },
        ],
        "escape_hatches": [
            {
                "tool": "run_in_threadpool (starlette)",
                "use_when": "Blocking I/O inside async def — uses FastAPI's shared anyio limiter",
            },
            {
                "tool": "asyncio.to_thread (stdlib, 3.9+)",
                "use_when": "Generic asyncio code, supports kwargs, separate executor pool",
            },
            {
                "tool": "loop.run_in_executor(ProcessPoolExecutor, fn)",
                "use_when": "CPU-bound work that must complete inside the request/response cycle",
            },
            {
                "tool": "Celery / arq / RQ",
                "use_when": "CPU or long-running work that can be decoupled from the HTTP response",
            },
        ],
        "threadpool_tuning": {
            "default_tokens": 40,
            "how_to_tune": "anyio.to_thread.current_default_thread_limiter().total_tokens = N  (in lifespan)",
            "raise_when": "Short I/O-bound blocking calls, concurrency > 40, RAM allows, DB pool allows",
            "do_not_raise_when": [
                "Calls are long (>5s) — fix root cause or use Celery",
                "CPU-bound work in threadpool — GIL contention gets worse, use ProcessPool",
                "DB connections per thread would exceed postgres max_connections",
            ],
        },
        "capacity_math": {
            "blocking_path": "uvicorn_workers × anyio_threads = max concurrent blocking ops",
            "async_path": "uvicorn_workers × (practically: memory/FD/downstream limits)",
            "db_connection_warning": "workers × threads can demand more DB connections than max_connections — measure first",
        },
    }


# ==========================================================================
# 11. HEALTH CHECK — must be async to remain responsive even under load
# ==========================================================================

@app.get(
    "/health",
    summary="Liveness probe",
    tags=["Ops"],
)
async def health():
    """
    Keep health checks as `async def` with no blocking calls.
    If `/health` is a `def` endpoint and the threadpool is exhausted, the
    Kubernetes liveness probe will time out → pod restart → cascading failure.
    If `/health` is `async def` but calls a blocking library, it joins the same
    frozen event loop → same failure.

    Correct: `async def` + no I/O (or only await-able I/O).
    """
    return {"status": "ok"}


# ==========================================================================
# 12. CAPACITY MATH DEMO (standalone — no server required)
# ==========================================================================

def _print_capacity_math() -> None:
    """
    Illustrates the workers × threads capacity ceiling for blocking endpoints.
    Run as a standalone script: `python 39_async_def_vs_def_threadpool_deep.py`
    """
    print("\n" + "=" * 60)
    print("CAPACITY MATH — def endpoints (blocking I/O)")
    print("=" * 60)

    scenarios = [
        (4, 40, 0.1),    # 4 workers, 40 threads, 100ms per op
        (4, 80, 0.1),    # tuned pool
        (4, 40, 2.0),    # slow queries (2 sec each)
        (4, 40, 10.0),   # very slow queries (10 sec each)
    ]

    for workers, threads, op_time_s in scenarios:
        concurrent_capacity = workers * threads
        rps_ceiling = concurrent_capacity / op_time_s
        print(
            f"  {workers} workers × {threads:3d} threads,  op={op_time_s:.1f}s "
            f" → {concurrent_capacity:4d} concurrent blocking ops "
            f" → {rps_ceiling:6.0f} RPS ceiling"
        )

    print()
    print("Async path (proper async def with await-able I/O):")
    print("  1 worker can interleave thousands of concurrent waits.")
    print("  Ceiling is memory / file descriptors / downstream service, NOT threads.")
    print()
    print("DB connection warning:")
    print("  4 workers × 80 threads = 320 potential DB connections.")
    print("  PostgreSQL default max_connections = 100.  Math first, tune second.")
    print("=" * 60)

    # Demonstrate that inspect.iscoroutinefunction correctly identifies async
    async def _sample_async():
        await asyncio.sleep(0)

    def _sample_sync():
        time.sleep(0)

    print("\nFastAPI routing decisions (inspect.iscoroutinefunction):")
    for fn in [_sample_async, _sample_sync]:
        path = "event loop" if inspect.iscoroutinefunction(fn) else "anyio threadpool"
        print(f"  {fn.__name__}: is_coroutine={inspect.iscoroutinefunction(fn)} → {path}")
    print()


if __name__ == "__main__":
    _print_capacity_math()
    print("To run the FastAPI server:")
    print("  uvicorn 39_async_def_vs_def_threadpool_deep:app --reload")
    print()
    print("Key endpoints to explore:")
    print("  GET /disaster           — async def + blocking: event loop frozen")
    print("  GET /safe-sync          — def: only one threadpool thread blocked")
    print("  GET /best-async         — async def + await: loop stays free")
    print("  GET /report/threadpool/1  — run_in_threadpool escape hatch")
    print("  GET /report/to-thread/1   — asyncio.to_thread escape hatch")
    print("  GET /cpu-crunch/1000000   — ProcessPoolExecutor for CPU work")
    print("  GET /routing-decision   — see FastAPI's per-route dispatch decision")
    print("  GET /decision-table     — full async/sync decision reference")
