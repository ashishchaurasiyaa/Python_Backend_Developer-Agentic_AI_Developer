"""
Server-Sent Events — Production Patterns
"""

import asyncio
import json
import time
from typing import AsyncGenerator

from fastapi import FastAPI, Request, Header, Depends
from sse_starlette.sse import EventSourceResponse
import httpx
import redis.asyncio as aioredis


app = FastAPI()


# ==========================================================================
# 1. BASIC SSE — counter
# ==========================================================================

@app.get("/stream/counter")
async def stream_counter(request: Request):
    async def gen():
        for i in range(1, 1001):
            if await request.is_disconnected():
                print(f"Client disconnected at {i}")
                break
            yield {
                "event": "tick",
                "id": str(i),
                "data": json.dumps({"count": i, "timestamp": time.time()}),
            }
            await asyncio.sleep(0.5)

    return EventSourceResponse(gen(), ping=15)


# ==========================================================================
# 2. LLM TOKEN STREAMING (Anthropic Claude example)
# ==========================================================================

@app.post("/chat/stream")
async def chat_stream(message: str):
    async def stream_claude():
        # Anthropic streaming
        async with httpx.AsyncClient(timeout=60.0) as client:
            async with client.stream(
                'POST',
                'https://api.anthropic.com/v1/messages',
                json={
                    'model': 'claude-sonnet-4-6',
                    'max_tokens': 1024,
                    'messages': [{'role': 'user', 'content': message}],
                    'stream': True,
                },
                headers={
                    'x-api-key': 'YOUR_KEY',
                    'anthropic-version': '2023-06-01',
                    'content-type': 'application/json',
                },
            ) as response:
                async for line in response.aiter_lines():
                    if not line.startswith('data: '):
                        continue
                    data_str = line[6:]
                    if data_str == '[DONE]':
                        break
                    try:
                        chunk = json.loads(data_str)
                        if chunk.get('type') == 'content_block_delta':
                            delta_text = chunk.get('delta', {}).get('text', '')
                            if delta_text:
                                yield {'event': 'token', 'data': delta_text}
                        elif chunk.get('type') == 'message_stop':
                            yield {'event': 'done', 'data': '[DONE]'}
                    except json.JSONDecodeError:
                        continue

    return EventSourceResponse(stream_claude(), ping=10)


# ==========================================================================
# 3. PROGRESS UPDATES for long-running job
# ==========================================================================

@app.get("/jobs/{job_id}/follow")
async def follow_job(job_id: str, request: Request):
    """Poll DB + stream status to client."""

    async def gen():
        last_progress = -1
        while True:
            if await request.is_disconnected():
                return

            # Mock — fetch from DB / Redis
            job = await get_job_status(job_id)

            if job['progress'] != last_progress:
                last_progress = job['progress']
                yield {
                    'event': 'progress',
                    'data': json.dumps(job),
                }

            if job['status'] in ('completed', 'failed', 'cancelled'):
                yield {'event': 'final', 'data': json.dumps(job)}
                return

            await asyncio.sleep(2)

    return EventSourceResponse(gen(), ping=15)


async def get_job_status(job_id: str) -> dict:
    # Placeholder — replace with real DB lookup
    return {'id': job_id, 'status': 'running', 'progress': 50}


# ==========================================================================
# 4. RESUMABLE STREAM (Last-Event-ID support)
# ==========================================================================

# In-memory event store for demo. Use Redis Streams in prod.
_event_log: list[tuple[int, str]] = []


@app.get("/stream/resumable")
async def resumable_stream(
    request: Request,
    last_event_id: str | None = Header(None),
):
    start_from = int(last_event_id or '0') + 1

    async def gen():
        # First send any past events (catch-up)
        for evt_id, data in _event_log:
            if evt_id >= start_from:
                yield {'id': str(evt_id), 'data': data}

        # Then live events
        # ... in real app, subscribe to Redis pub/sub here
        current_id = _event_log[-1][0] if _event_log else 0
        while True:
            if await request.is_disconnected():
                return
            current_id += 1
            data = json.dumps({'tick': current_id, 'ts': time.time()})
            _event_log.append((current_id, data))
            # Trim old (keep last 1000)
            if len(_event_log) > 1000:
                _event_log[:] = _event_log[-1000:]
            yield {'id': str(current_id), 'data': data}
            await asyncio.sleep(1)

    return EventSourceResponse(gen())


# ==========================================================================
# 5. REDIS PUB/SUB FAN-OUT
# ==========================================================================

REDIS_URL = "redis://localhost:6379/0"


@app.get("/notifications/{user_id}")
async def notifications(user_id: str, request: Request):
    """Per-user notification stream backed by Redis pub/sub."""
    r = aioredis.from_url(REDIS_URL)
    pubsub = r.pubsub()
    await pubsub.subscribe(f'user:{user_id}:notifications')

    async def gen():
        try:
            while True:
                if await request.is_disconnected():
                    break

                msg = await pubsub.get_message(
                    ignore_subscribe_messages=True,
                    timeout=15.0,
                )
                if msg is None:
                    # Timeout — heartbeat handled by sse_starlette ping=
                    continue
                if msg['type'] != 'message':
                    continue

                yield {
                    'event': 'notification',
                    'data': msg['data'].decode('utf-8'),
                }
        finally:
            await pubsub.unsubscribe()
            await pubsub.aclose()
            await r.aclose()

    return EventSourceResponse(gen(), ping=15)


# Producer (call from anywhere)
async def publish_notification(user_id: str, payload: dict):
    r = aioredis.from_url(REDIS_URL)
    try:
        await r.publish(
            f'user:{user_id}:notifications',
            json.dumps(payload),
        )
    finally:
        await r.aclose()


# ==========================================================================
# 6. REDIS STREAMS (with consumer groups — durable)
# ==========================================================================

@app.get("/stream/durable/{user_id}")
async def durable_stream(user_id: str, request: Request):
    """Backed by Redis Streams — replayable, durable."""
    r = aioredis.from_url(REDIS_URL)
    stream_key = f'events:{user_id}'
    last_id = '0'  # start from beginning; or '$' for only new

    async def gen():
        nonlocal last_id
        try:
            while True:
                if await request.is_disconnected():
                    return

                # XREAD blocks for up to 10s
                messages = await r.xread(
                    streams={stream_key: last_id},
                    count=10,
                    block=10_000,
                )
                if not messages:
                    continue

                for _, entries in messages:
                    for msg_id, fields in entries:
                        last_id = msg_id.decode()
                        data = {k.decode(): v.decode() for k, v in fields.items()}
                        yield {
                            'id': last_id,
                            'data': json.dumps(data),
                        }
        finally:
            await r.aclose()

    return EventSourceResponse(gen(), ping=15)


# Producer
async def publish_to_stream(user_id: str, data: dict):
    r = aioredis.from_url(REDIS_URL)
    try:
        await r.xadd(
            f'events:{user_id}',
            data,
            maxlen=10000,    # cap stream size
        )
    finally:
        await r.aclose()


# ==========================================================================
# 7. HEARTBEAT / CUSTOM RETRY
# ==========================================================================

@app.get("/stream/with-retry")
async def with_retry(request: Request):
    async def gen():
        # First message can set retry delay
        yield {'retry': 5000, 'data': 'connected'}

        while not await request.is_disconnected():
            yield {'data': f'tick {time.time()}'}
            await asyncio.sleep(2)

    return EventSourceResponse(gen())


# ==========================================================================
# 8. CLIENT JS EXAMPLE
# ==========================================================================
"""
// Browser client

const evt = new EventSource('/stream/counter');

evt.addEventListener('tick', (e) => {
    const data = JSON.parse(e.data);
    document.getElementById('count').textContent = data.count;
});

evt.addEventListener('token', (e) => {
    // LLM streaming
    document.getElementById('output').textContent += e.data;
});

evt.onerror = (e) => {
    // EventSource auto-reconnects; just log
    console.log('SSE error, reconnecting...');
};

// Close
// evt.close();
"""


# ==========================================================================
# 9. NGINX CONFIG (disable buffering)
# ==========================================================================
"""
location /stream/ {
    proxy_pass http://backend;
    proxy_http_version 1.1;
    proxy_buffering off;
    proxy_cache off;
    proxy_set_header Connection '';
    chunked_transfer_encoding off;
    proxy_read_timeout 24h;
    proxy_send_timeout 24h;
}
"""


# ==========================================================================
# 10. RESPONSE HEADERS (for clarity)
# ==========================================================================

# sse_starlette already sets:
# Content-Type: text/event-stream
# Cache-Control: no-cache
# Connection: keep-alive
# X-Accel-Buffering: no   (for nginx)
