"""
============================================================
ASGI INTERNALS + UVICORN TUNING — Practical
============================================================

Run different demos:
  python 13_asgi_internals_uvicorn_tuning.py minimal
  python 13_asgi_internals_uvicorn_tuning.py middleware
  python 13_asgi_internals_uvicorn_tuning.py lifespan
"""
import asyncio
import sys
import time
import os
from typing import Callable, Awaitable


# ============================================================
# 1. MINIMAL ASGI APP — pure, no framework
# ============================================================
async def minimal_asgi_app(scope, receive, send):
    """The bare-minimum ASGI app — what FastAPI is built on."""
    assert scope["type"] == "http"

    # Read request body (may come in chunks)
    body = b""
    more_body = True
    while more_body:
        msg = await receive()
        body += msg.get("body", b"")
        more_body = msg.get("more_body", False)

    # Send response
    response_body = f"Hello!\nPath: {scope['path']}\nBody: {body.decode()}\n".encode()
    await send({
        "type": "http.response.start",
        "status": 200,
        "headers": [
            (b"content-type", b"text/plain"),
            (b"content-length", str(len(response_body)).encode()),
        ],
    })
    await send({
        "type": "http.response.body",
        "body": response_body,
    })


# ============================================================
# 2. ASGI MIDDLEWARE — wraps the app
# ============================================================
class TimingMiddleware:
    """Logs request duration. Pure ASGI middleware."""
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        start = time.perf_counter()
        path = scope["path"]

        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                duration = (time.perf_counter() - start) * 1000
                print(f"  [Timing] {scope['method']} {path} → {message['status']} {duration:.2f}ms")
                # Add custom header
                headers = list(message.get("headers", []))
                headers.append((b"x-process-time", f"{duration:.2f}".encode()))
                message["headers"] = headers
            await send(message)

        await self.app(scope, receive, send_wrapper)


# ============================================================
# 3. LIFESPAN-AWARE APP
# ============================================================
class AppWithLifespan:
    def __init__(self):
        self.db_pool = None    # would be real DB pool in prod
        self.cache = None

    async def __call__(self, scope, receive, send):
        if scope["type"] == "lifespan":
            await self._lifespan(receive, send)
        elif scope["type"] == "http":
            await self._http(scope, receive, send)

    async def _lifespan(self, receive, send):
        while True:
            message = await receive()
            if message["type"] == "lifespan.startup":
                print("  [Lifespan] STARTUP — connecting to DB, loading models...")
                self.db_pool = "fake_pool"
                await send({"type": "lifespan.startup.complete"})
            elif message["type"] == "lifespan.shutdown":
                print("  [Lifespan] SHUTDOWN — closing connections...")
                self.db_pool = None
                await send({"type": "lifespan.shutdown.complete"})
                return

    async def _http(self, scope, receive, send):
        body = f"DB pool ready: {self.db_pool is not None}".encode()
        await send({"type": "http.response.start", "status": 200,
                    "headers": [(b"content-type", b"text/plain")]})
        await send({"type": "http.response.body", "body": body})


# ============================================================
# 4. ROUTING MIDDLEWARE — multiple endpoints
# ============================================================
async def route_users(scope, receive, send):
    await send({"type": "http.response.start", "status": 200,
                "headers": [(b"content-type", b"application/json")]})
    await send({"type": "http.response.body", "body": b'{"users": []}'})


async def route_health(scope, receive, send):
    await send({"type": "http.response.start", "status": 200,
                "headers": [(b"content-type", b"application/json")]})
    await send({"type": "http.response.body", "body": b'{"status": "ok"}'})


async def not_found(scope, receive, send):
    await send({"type": "http.response.start", "status": 404,
                "headers": [(b"content-type", b"text/plain")]})
    await send({"type": "http.response.body", "body": b"Not Found"})


async def router_app(scope, receive, send):
    """Simple ASGI router."""
    if scope["type"] != "http":
        return
    path = scope["path"]
    if path == "/users":
        await route_users(scope, receive, send)
    elif path == "/health":
        await route_health(scope, receive, send)
    else:
        await not_found(scope, receive, send)


# ============================================================
# 5. WSGI vs ASGI COMPARISON (in comments)
# ============================================================
WSGI_EXAMPLE = """
# WSGI — synchronous, no WebSocket support
def wsgi_app(environ, start_response):
    status = '200 OK'
    headers = [('Content-Type', 'text/plain')]
    start_response(status, headers)
    return [b'Hello WSGI']
"""

ASGI_EXAMPLE = """
# ASGI — async, supports HTTP + WebSocket + lifespan
async def asgi_app(scope, receive, send):
    if scope['type'] == 'http':
        await send({'type': 'http.response.start', 'status': 200,
                    'headers': [(b'content-type', b'text/plain')]})
        await send({'type': 'http.response.body', 'body': b'Hello ASGI'})
"""


# ============================================================
# 6. GUNICORN/UVICORN CONFIG TEMPLATE
# ============================================================
GUNICORN_CONFIG = """
# gunicorn_conf.py — production config

bind = "0.0.0.0:8000"
workers = int(os.getenv("WORKERS", os.cpu_count() * 2 + 1))
worker_class = "uvicorn.workers.UvicornWorker"
worker_connections = 1000           # max concurrent connections per worker
keepalive = 5                        # close idle keep-alive after 5s
timeout = 60                         # kill worker if unresponsive
graceful_timeout = 30                # SIGTERM grace period

# Memory management
max_requests = 50000                 # restart worker after N reqs
max_requests_jitter = 5000           # randomize to avoid all-at-once

# Logging
accesslog = "-"
errorlog = "-"
loglevel = "info"

# Performance
preload_app = True                   # share read-only memory
backlog = 2048                       # TCP listen backlog

# Hooks
def post_fork(server, worker):
    server.log.info(f"Worker spawned (pid: {worker.pid})")

def worker_int(worker):
    worker.log.info(f"Worker SIGINT (pid: {worker.pid})")
"""

UVICORN_PROD = """
# Run with:
# uvicorn app:app \\
#   --host 0.0.0.0 \\
#   --port 8000 \\
#   --workers 4 \\
#   --loop uvloop \\
#   --http httptools \\
#   --backlog 2048 \\
#   --limit-concurrency 1000 \\
#   --limit-max-requests 50000 \\
#   --timeout-keep-alive 5 \\
#   --proxy-headers \\
#   --forwarded-allow-ips '*' \\
#   --no-server-header

# OR via gunicorn:
# gunicorn app:app -c gunicorn_conf.py
"""


# ============================================================
# 7. GRACEFUL SHUTDOWN PATTERN
# ============================================================
GRACEFUL_SHUTDOWN = """
import signal
import asyncio

shutdown_event = asyncio.Event()

@app.on_event("startup")
async def startup():
    loop = asyncio.get_event_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, lambda: shutdown_event.set())

@app.middleware("http")
async def reject_during_shutdown(request, call_next):
    if shutdown_event.is_set():
        return JSONResponse({"error": "shutting down"}, status_code=503)
    return await call_next(request)

# Inside long-running endpoint, check shutdown_event periodically
"""


# ============================================================
# 8. SLOW REQUEST LOGGER MIDDLEWARE
# ============================================================
class SlowRequestMiddleware:
    def __init__(self, app, threshold_ms=500):
        self.app = app
        self.threshold = threshold_ms / 1000

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        start = time.perf_counter()

        await self.app(scope, receive, send)

        elapsed = time.perf_counter() - start
        if elapsed > self.threshold:
            print(f"  [SLOW] {scope['method']} {scope['path']} took {elapsed*1000:.0f}ms")


# ============================================================
# 9. RUN STANDALONE WITH BUILT-IN ASGI SERVER (asyncio)
# ============================================================
async def run_simple_server(host="127.0.0.1", port=8765):
    """Demo: serve minimal ASGI app without uvicorn."""

    # Wrap with timing middleware
    app = TimingMiddleware(router_app)

    async def handle_client(reader, writer):
        # VERY simplified HTTP parsing — production use httptools
        try:
            request_line = (await reader.readline()).decode().strip()
            if not request_line:
                return
            method, path, _ = request_line.split(" ", 2)

            # Skip headers
            while True:
                line = await reader.readline()
                if line in (b"\r\n", b""):
                    break

            scope = {
                "type": "http",
                "method": method,
                "path": path,
                "headers": [],
                "query_string": b"",
            }

            response_parts = []

            async def receive():
                return {"type": "http.request", "body": b"", "more_body": False}

            async def send(message):
                if message["type"] == "http.response.start":
                    status = message["status"]
                    headers = "\r\n".join(
                        f"{k.decode()}: {v.decode()}"
                        for k, v in message["headers"]
                    )
                    response_parts.append(f"HTTP/1.1 {status} OK\r\n{headers}\r\n\r\n".encode())
                elif message["type"] == "http.response.body":
                    response_parts.append(message["body"])

            await app(scope, receive, send)
            for part in response_parts:
                writer.write(part)
            await writer.drain()
        finally:
            writer.close()

    server = await asyncio.start_server(handle_client, host, port)
    print(f"  Listening on http://{host}:{port}")
    print(f"  Try: curl http://{host}:{port}/users")
    print(f"  Try: curl http://{host}:{port}/health")
    print("  Press Ctrl+C to stop\n")
    async with server:
        await server.serve_forever()


# ============================================================
# 10. WORKER COUNT CALCULATOR
# ============================================================
def suggest_workers():
    cpus = os.cpu_count() or 1
    print(f"  CPU cores         : {cpus}")
    print(f"  I/O-bound app     : {cpus} workers (asyncio handles concurrency)")
    print(f"  CPU-bound app     : {2*cpus + 1} workers (2N+1 rule)")
    print(f"  Memory-heavy (ML) : {max(1, cpus // 2)} workers (avoid model duplication)")


# ============================================================
# MAIN
# ============================================================
def show_configs():
    print("=" * 60)
    print("GUNICORN CONFIG TEMPLATE")
    print("=" * 60)
    print(GUNICORN_CONFIG)
    print("\n" + "=" * 60)
    print("UVICORN PRODUCTION COMMAND")
    print("=" * 60)
    print(UVICORN_PROD)
    print("=" * 60)
    print("GRACEFUL SHUTDOWN PATTERN")
    print("=" * 60)
    print(GRACEFUL_SHUTDOWN)


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "info"

    if mode == "minimal":
        print("Run: uvicorn 13_asgi_internals_uvicorn_tuning:minimal_asgi_app")
    elif mode == "server":
        try:
            asyncio.run(run_simple_server())
        except KeyboardInterrupt:
            print("\n  Stopped")
    elif mode == "workers":
        suggest_workers()
    elif mode == "configs":
        show_configs()
    else:
        print("=" * 60)
        print("ASGI INTERNALS — Demo modes")
        print("=" * 60)
        print("  python 13_asgi_internals_uvicorn_tuning.py minimal")
        print("    → Show how to mount minimal ASGI app")
        print("  python 13_asgi_internals_uvicorn_tuning.py server")
        print("    → Run a tiny HTTP server using ASGI app")
        print("  python 13_asgi_internals_uvicorn_tuning.py workers")
        print("    → Suggest worker counts for this machine")
        print("  python 13_asgi_internals_uvicorn_tuning.py configs")
        print("    → Print Gunicorn + Uvicorn production config")
        print()
        suggest_workers()
