"""
Server-Sent Events (SSE) — Production Patterns with FastAPI
============================================================

SSE is a one-way, server-to-client streaming protocol built on plain HTTP.
The server keeps a long-lived response open and pushes formatted text events
as they occur.  Browsers have a native EventSource API that reconnects
automatically and resumes from the last received event ID.

When to use SSE:
- Live notifications, order/payment updates
- Real-time dashboard metrics
- Long-running task progress reporting
- LLM token-by-token streaming (OpenAI's API uses SSE)
- Chat receive channel (paired with a separate POST for sending)

When to use WebSocket instead:
- Bidirectional communication (games, collaborative editing)
- Binary data transport

Install:
    pip install fastapi uvicorn[standard] sse-starlette

Run (development):
    uvicorn 02_sse_server_sent_events:app --reload --port 8000

Run (production — HTTP/2 via hypercorn):
    pip install hypercorn
    hypercorn 02_sse_server_sent_events:app --bind 0.0.0.0:8000
"""

import asyncio
import json
import logging
import time
from collections import deque
from dataclasses import dataclass, field
from typing import AsyncGenerator, Optional

from fastapi import FastAPI, Header, HTTPException, Query, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

# pip install sse-starlette
from sse_starlette.sse import EventSourceResponse

log = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

app = FastAPI(title="SSE Demo", description="Server-Sent Events production patterns")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==========================================================================
# 1. SSE EVENT FORMAT HELPERS
# ==========================================================================

def format_sse(
    data: str,
    event: Optional[str] = None,
    event_id: Optional[str] = None,
    retry_ms: Optional[int] = None,
) -> str:
    """
    Serialise a single SSE event into the wire format.

    Format::

        event: <type>\\n          (optional; default = "message")
        id: <id>\\n               (optional; enables Last-Event-ID resume)
        retry: <milliseconds>\\n  (optional; reconnect hint)
        data: <line>\\n
        data: <line>\\n           (multi-line data supported)
        \\n                       <- empty line terminates the event

    Common mistake: using only one trailing newline.  The event is not
    dispatched to the client until the *double* newline is written.
    """
    parts: list[str] = []
    if event:
        parts.append(f"event: {event}")
    if event_id is not None:
        parts.append(f"id: {event_id}")
    if retry_ms is not None:
        parts.append(f"retry: {retry_ms}")
    # Multi-line data: each line prefixed with "data: "
    for line in data.splitlines():
        parts.append(f"data: {line}")
    parts.append("")   # trailing empty string → "\n\n" after join
    return "\n".join(parts) + "\n"


def format_heartbeat() -> str:
    """
    SSE comment line.  Clients ignore comments; proxies see activity and
    reset their idle timeout.  Send every ~15 s to survive 60 s proxy
    timeouts (NGINX default).
    """
    return ": heartbeat\n\n"


# ==========================================================================
# 2. IN-MEMORY EVENT STORE  (replace with a real DB / Redis in production)
# ==========================================================================

@dataclass
class StoredEvent:
    id: int
    event_type: str
    payload: dict


class EventStore:
    """
    Bounded ring-buffer of recent events that supports:
    - Publish: fanout to all connected SSE queues.
    - Replay: return events since a given ID for Last-Event-ID resume.
    """

    MAX_HISTORY = 1_000

    def __init__(self) -> None:
        self._counter: int = 0
        self._history: deque[StoredEvent] = deque(maxlen=self.MAX_HISTORY)
        # Each connected client gets its own asyncio.Queue.
        self._subscribers: set[asyncio.Queue] = set()

    async def publish(self, event_type: str, payload: dict) -> StoredEvent:
        """Store a new event and push it to every connected subscriber."""
        self._counter += 1
        evt = StoredEvent(id=self._counter, event_type=event_type, payload=payload)
        self._history.append(evt)
        dead: list[asyncio.Queue] = []
        for q in self._subscribers:
            try:
                q.put_nowait(evt)
            except asyncio.QueueFull:
                # Client is too slow; mark for removal to avoid unbounded growth.
                dead.append(q)
                log.warning("SSE subscriber queue full — dropping slow client")
        for q in dead:
            self._subscribers.discard(q)
        log.info("Published event id=%s type=%s", evt.id, evt.event_type)
        return evt

    def events_since(self, last_id: int) -> list[StoredEvent]:
        """Return all stored events with id > last_id (for replay on reconnect)."""
        return [e for e in self._history if e.id > last_id]

    def subscribe(self) -> asyncio.Queue:
        """Register a new subscriber queue and return it."""
        q: asyncio.Queue = asyncio.Queue(maxsize=200)
        self._subscribers.add(q)
        return q

    def unsubscribe(self, q: asyncio.Queue) -> None:
        """Remove a subscriber queue (called when client disconnects)."""
        self._subscribers.discard(q)


store = EventStore()


# ==========================================================================
# 3. MANUAL SSE — StreamingResponse (no third-party library)
# ==========================================================================

async def _manual_generator(request: Request) -> AsyncGenerator[str, None]:
    """
    Minimal SSE generator using only FastAPI / Starlette primitives.

    Pattern:
    1. Replay missed events from Last-Event-ID header.
    2. Subscribe to the live fanout queue.
    3. Yield events; interleave heartbeats to keep the connection alive.
    4. Detect client disconnect via request.is_disconnected() and clean up.
    """
    last_id_header = request.headers.get("Last-Event-ID", "0")
    last_id = int(last_id_header) if last_id_header.isdigit() else 0

    # --- Replay missed events ---
    missed = store.events_since(last_id)
    for evt in missed:
        yield format_sse(
            data=json.dumps(evt.payload),
            event=evt.event_type,
            event_id=str(evt.id),
        )

    # --- Subscribe to live stream ---
    q = store.subscribe()
    try:
        while True:
            if await request.is_disconnected():
                log.info("SSE client disconnected (manual endpoint)")
                break

            try:
                evt = await asyncio.wait_for(q.get(), timeout=15.0)
                yield format_sse(
                    data=json.dumps(evt.payload),
                    event=evt.event_type,
                    event_id=str(evt.id),
                )
            except asyncio.TimeoutError:
                # 15 s elapsed with no events — send heartbeat to prevent
                # proxy idle-timeout disconnection.
                yield format_heartbeat()
    finally:
        store.unsubscribe(q)


@app.get(
    "/events/manual",
    summary="SSE stream (manual StreamingResponse)",
    tags=["SSE"],
)
async def events_manual(request: Request):
    """
    Manual SSE endpoint using StreamingResponse.

    Headers set here are required:
    - ``Content-Type: text/event-stream`` — tells the browser to parse as SSE.
    - ``Cache-Control: no-cache`` — prevents intermediary caching.
    - ``X-Accel-Buffering: no`` — NGINX-specific: disables proxy_buffering so
      events are forwarded to the client immediately, not held in a buffer.
    """
    return StreamingResponse(
        _manual_generator(request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",   # disable NGINX proxy buffering
            "Connection": "keep-alive",
        },
    )


# ==========================================================================
# 4. SSE WITH sse-starlette  (recommended for production)
# ==========================================================================
#
# EventSourceResponse from sse-starlette handles:
#   - Correct Content-Type and headers.
#   - Automatic ping events (configurable interval).
#   - Disconnect detection.
#   - Dict-based event format: {"event": ..., "id": ..., "data": ...}
#
# pip install sse-starlette

async def _starlette_generator(
    request: Request,
    last_id: int,
) -> AsyncGenerator[dict, None]:
    """
    SSE generator that yields dict objects consumed by EventSourceResponse.

    Keys recognised by EventSourceResponse:
      - "event"  → SSE event type field
      - "id"     → SSE id field (for Last-Event-ID resume)
      - "data"   → SSE data field (string)
      - "retry"  → SSE retry field (reconnect delay in ms)
    """
    # --- Replay missed events ---
    for evt in store.events_since(last_id):
        yield {
            "event": evt.event_type,
            "id":    str(evt.id),
            "data":  json.dumps(evt.payload),
        }

    # --- Live stream ---
    q = store.subscribe()
    try:
        while True:
            if await request.is_disconnected():
                log.info("SSE client disconnected (sse-starlette endpoint)")
                break
            try:
                evt = await asyncio.wait_for(q.get(), timeout=20.0)
                yield {
                    "event": evt.event_type,
                    "id":    str(evt.id),
                    "data":  json.dumps(evt.payload),
                }
            except asyncio.TimeoutError:
                # EventSourceResponse sends its own ping if ping= is set;
                # this branch is a safety valve if ping is not configured.
                continue
    finally:
        store.unsubscribe(q)


@app.get(
    "/events",
    summary="SSE stream (sse-starlette — recommended)",
    tags=["SSE"],
)
async def events(
    request: Request,
    last_event_id: Optional[str] = Header(default=None, alias="Last-Event-ID"),
):
    """
    Production SSE endpoint using EventSourceResponse.

    ``ping=15`` instructs sse-starlette to send a comment (`: ping`) every
    15 seconds automatically — no manual heartbeat logic required.

    The ``Last-Event-ID`` header is sent by the browser on every automatic
    reconnect, enabling seamless resume from where the client left off.

    curl example::

        curl -N http://localhost:8000/events
    """
    last_id = int(last_event_id) if last_event_id and last_event_id.isdigit() else 0
    return EventSourceResponse(
        _starlette_generator(request, last_id),
        ping=15,              # send `: ping` comment every 15 seconds
    )


# ==========================================================================
# 5. TASK PROGRESS STREAM (long-running job pattern)
# ==========================================================================

async def _progress_generator(
    request: Request,
    task_id: str,
) -> AsyncGenerator[dict, None]:
    """
    Simulate a multi-step background task and stream progress events.

    Pattern used for: file processing, ML inference, data imports.

    Client listens on GET /tasks/{task_id}/progress and displays a progress
    bar.  Task result is embedded in the final "done" event payload.
    """
    steps = [
        ("validating",   10),
        ("processing",   40),
        ("transforming", 70),
        ("persisting",   90),
        ("done",        100),
    ]
    for step_name, progress in steps:
        if await request.is_disconnected():
            log.info("Client disconnected during task %s at step %s", task_id, step_name)
            break

        payload = {"task_id": task_id, "step": step_name, "progress": progress}
        if step_name == "done":
            payload["result"] = {"status": "success", "records_processed": 42}

        yield {
            "event": "progress",
            "data":  json.dumps(payload),
        }
        # Simulate work — remove in real implementation
        await asyncio.sleep(0.8)


@app.get(
    "/tasks/{task_id}/progress",
    summary="Task progress stream",
    tags=["SSE"],
)
async def task_progress(request: Request, task_id: str):
    """
    Stream progress for a long-running task.

    Browser-side::

        const es = new EventSource(`/tasks/${taskId}/progress`);
        es.addEventListener("progress", (e) => {
            const {step, progress} = JSON.parse(e.data);
            progressBar.value = progress;
            if (step === "done") es.close();
        });
    """
    return EventSourceResponse(
        _progress_generator(request, task_id),
        ping=10,
    )


# ==========================================================================
# 6. LLM TOKEN STREAMING PATTERN
# ==========================================================================

async def _llm_stream_generator(
    request: Request,
    prompt: str,
) -> AsyncGenerator[dict, None]:
    """
    Mock LLM token-by-token streaming response (OpenAI-style SSE).

    In production, replace the simulated tokens with real SDK calls::

        async with client.stream("POST", "/chat/completions", json={...}) as resp:
            async for line in resp.aiter_lines():
                if line.startswith("data: "):
                    chunk = json.loads(line[6:])
                    token = chunk["choices"][0]["delta"].get("content", "")
                    if token:
                        yield {"event": "token", "data": token}

    The `done` event signals the client to stop appending tokens.
    """
    simulated_tokens = ["The", " quick", " brown", " fox", " jumps", " over",
                        " the", " lazy", " dog", "."]

    for token in simulated_tokens:
        if await request.is_disconnected():
            break
        yield {"event": "token", "data": token}
        await asyncio.sleep(0.1)   # simulate per-token latency

    yield {"event": "done", "data": ""}


@app.get(
    "/llm/stream",
    summary="LLM token streaming (mock)",
    tags=["SSE"],
)
async def llm_stream(
    request: Request,
    prompt: str = Query(default="Tell me about SSE", description="Prompt to send to LLM"),
):
    """
    Stream LLM tokens one-by-one as SSE events.

    OpenAI's API uses this exact pattern.  Client accumulates tokens
    and appends them to a <pre> or textarea element in real time.

    Browser-side::

        const es = new EventSource(`/llm/stream?prompt=...`);
        es.addEventListener("token",  (e) => output.textContent += e.data);
        es.addEventListener("done",   ()  => es.close());
    """
    return EventSourceResponse(
        _llm_stream_generator(request, prompt),
        ping=30,
    )


# ==========================================================================
# 7. PUBLISH ENDPOINT — push events into the store
# ==========================================================================

@app.post(
    "/publish",
    summary="Publish an event to all SSE subscribers",
    tags=["Admin"],
    status_code=status.HTTP_202_ACCEPTED,
)
async def publish_event(body: dict):
    """
    Publish an event so all connected SSE clients receive it.

    Example payload::

        {"type": "order_paid", "data": {"order_id": 42, "amount": 99.99}}

    In production this endpoint would be internal-only (protected by an API
    key or network policy), called by background workers or webhooks.
    """
    event_type = body.get("type", "message")
    payload = body.get("data", {})
    if not isinstance(payload, dict):
        raise HTTPException(status_code=422, detail="'data' must be a JSON object")
    evt = await store.publish(event_type=event_type, payload=payload)
    return {"published": True, "event_id": evt.id, "event_type": evt.event_type}


# ==========================================================================
# 8. BACKPRESSURE-AWARE GENERATOR
# ==========================================================================

async def _backpressure_generator(
    request: Request,
) -> AsyncGenerator[str, None]:
    """
    Illustrate the backpressure pattern for a high-throughput event source.

    When events arrive faster than the client can consume them (slow TCP
    window), the bounded queue fills up.  ``put_nowait`` + ``QueueFull``
    drops excess events rather than blocking the producer, preventing
    memory growth.

    This generator is used when we have a separate fast event source (e.g.,
    Kafka consumer) decoupled from the per-client SSE send loop.
    """
    queue: asyncio.Queue = asyncio.Queue(maxsize=100)

    async def producer() -> None:
        """Simulate a fast event source (Kafka, Redis Streams, etc.)."""
        counter = 0
        while True:
            counter += 1
            event_data = json.dumps({"seq": counter, "ts": time.time()})
            try:
                queue.put_nowait(event_data)
            except asyncio.QueueFull:
                log.warning("Backpressure: queue full, dropping event seq=%d", counter)
            await asyncio.sleep(0.05)   # 20 events/s from source

    producer_task = asyncio.create_task(producer())
    try:
        while True:
            if await request.is_disconnected():
                break
            try:
                data = await asyncio.wait_for(queue.get(), timeout=15.0)
                yield format_sse(data=data, event="metric")
            except asyncio.TimeoutError:
                yield format_heartbeat()
    finally:
        producer_task.cancel()


@app.get(
    "/events/backpressure",
    summary="Backpressure-aware high-throughput SSE",
    tags=["SSE"],
)
async def events_backpressure(request: Request):
    """
    High-throughput SSE with bounded per-client queue.

    The producer runs at 20 events/s; if the client's TCP window is full,
    events are dropped rather than buffering unboundedly in memory.
    """
    return StreamingResponse(
        _backpressure_generator(request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


# ==========================================================================
# 9. HEALTH / INFO ENDPOINTS
# ==========================================================================

@app.get("/health", tags=["Ops"])
async def health():
    """Liveness probe — returns subscriber count for observability."""
    return {
        "status": "ok",
        "event_store": {
            "total_events_published": store._counter,
            "history_size":           len(store._history),
            "active_subscribers":     len(store._subscribers),
        },
    }


# ==========================================================================
# 10. NGINX / PROXY CONFIGURATION REFERENCE
# ==========================================================================

NGINX_SSE_CONFIG = """
# NGINX configuration for SSE endpoints
# The single most important setting is `proxy_buffering off`.
# Without it, events are held in the buffer until the response ends (never).

location /events {
    proxy_pass         http://backend;
    proxy_buffering    off;           # CRITICAL — disable response buffering
    proxy_cache        off;
    proxy_set_header   Connection '';
    proxy_http_version 1.1;
    proxy_read_timeout 24h;           # keep connection open for up to 24 hours
    # Disable gzip — streaming gzip can cause buffering issues
    gzip               off;

    # Headers the app sets (documented here for ops reference):
    #   Cache-Control: no-cache
    #   X-Accel-Buffering: no     ← NGINX also honours this per-response header
    #   Content-Type: text/event-stream
}
"""


# ==========================================================================
# 11. BROWSER-SIDE JAVASCRIPT REFERENCE
# ==========================================================================

BROWSER_JS_REFERENCE = """
// --- Basic usage ---
const es = new EventSource("/events");

// Default "message" event (no event: field in SSE)
es.onmessage = (e) => console.log("message:", e.data);

// Named event types
es.addEventListener("order_paid",    (e) => handleOrder(JSON.parse(e.data)));
es.addEventListener("status_update", (e) => updateUI(JSON.parse(e.data)));
es.addEventListener("token",         (e) => appendToken(e.data));
es.addEventListener("done",          ()  => es.close());

// Error / reconnect
es.onerror = (err) => {
    // Browser reconnects automatically after ~3 s (or retry: field value)
    console.error("SSE error — browser will retry automatically", err);
};

// Manual close
es.close();


// --- Last-Event-ID ---
// Browser sends this header automatically on every reconnect.
// Server replays events since that ID — zero client code needed.


// --- Auth workaround (EventSource has no headers API) ---
// Option A: Cookie-based auth (works natively)
// Option B: Token in query param (avoid — visible in logs)
// Option C: event-source-polyfill (supports custom headers)

import { EventSourcePolyfill } from "event-source-polyfill";   // npm install event-source-polyfill

const esAuth = new EventSourcePolyfill("/events", {
    headers: { "Authorization": `Bearer ${localStorage.getItem("token")}` },
    heartbeatTimeout: 60_000,
});
"""


# ==========================================================================
# 12. PRODUCTION SCALING NOTES
# ==========================================================================

SCALING_NOTES = """
HTTP/1.1 limitation
-------------------
Browsers limit ~6 open connections per origin.  With HTTP/1.1 SSE, a user
with 6 browser tabs exhausts the connection pool and the 7th tab cannot
connect.  HTTP/2 multiplexes all SSE streams over a single TCP connection —
no browser limit.

Always serve SSE over HTTP/2 (or HTTP/3) in production:
    hypercorn app:app --bind 0.0.0.0:443 --certfile cert.pem --keyfile key.pem

Multi-server fanout (backplane pattern)
---------------------------------------
When you scale horizontally, an event published on server A must reach
clients connected to servers B and C.  Standard solution: Redis Pub/Sub.

    Event published by worker
          ↓
    PUBLISH redis channel "events:global"
          ↓
    Each app server has an SUBSCRIBE loop
          ↓
    Server pushes received message into its local subscriber queues
          ↓
    Each connected SSE client receives the event

See 03_sse_backplane.py for a full Redis Pub/Sub implementation.

Connection counts
-----------------
Each open SSE connection holds one async task (or thread in sync servers).
With asyncio, a single uvicorn process can hold tens of thousands of
concurrent SSE connections comfortably (no per-connection thread overhead).
"""


# ==========================================================================
# 13. STARTUP / SHUTDOWN LIFECYCLE
# ==========================================================================

@app.on_event("startup")
async def on_startup() -> None:
    log.info("SSE demo server started.  Endpoints:")
    log.info("  GET  /events                  — main SSE stream (sse-starlette)")
    log.info("  GET  /events/manual           — SSE stream (raw StreamingResponse)")
    log.info("  GET  /events/backpressure     — bounded-queue high-throughput SSE")
    log.info("  GET  /tasks/{task_id}/progress — task progress stream")
    log.info("  GET  /llm/stream?prompt=...   — mock LLM token streaming")
    log.info("  POST /publish                  — publish event to all subscribers")
    log.info("  GET  /health                   — liveness + subscriber count")


@app.on_event("shutdown")
async def on_shutdown() -> None:
    log.info("SSE demo server shutting down.  Active subscribers: %d",
             len(store._subscribers))


# ==========================================================================
# 14. __main__ DEMO — demonstrates the format_sse helper standalone
# ==========================================================================

if __name__ == "__main__":
    # Demonstrates the wire format produced by format_sse() without starting
    # the web server.  Useful for understanding the SSE protocol.

    print("=== SSE Wire Format Demo ===\n")

    # Simple data-only event
    print(repr(format_sse(data="hello world")))

    # Named event with ID
    print(repr(format_sse(
        data=json.dumps({"order_id": 42, "amount": 99.99}),
        event="order_paid",
        event_id="42",
    )))

    # Multi-line data (each line prefixed with "data: ")
    print(repr(format_sse(
        data="line one\nline two\nline three",
        event="multiline",
        event_id="43",
        retry_ms=3000,
    )))

    # Heartbeat comment
    print(repr(format_heartbeat()))

    print("\n=== To run the full SSE server ===")
    print("  uvicorn 02_sse_server_sent_events:app --reload --port 8000")
    print("\n=== Quick test with curl ===")
    print("  curl -N http://localhost:8000/events")
    print("  curl -N http://localhost:8000/tasks/job-123/progress")
    print("  curl -N http://localhost:8000/llm/stream?prompt=Hello")
    print("\n=== Publish a test event ===")
    print("  curl -X POST http://localhost:8000/publish \\")
    print('       -H "Content-Type: application/json" \\')
    print('       -d \'{"type": "order_paid", "data": {"order_id": 42}}\'')
