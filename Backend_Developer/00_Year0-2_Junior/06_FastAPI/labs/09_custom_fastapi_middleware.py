"""
FastAPI Lab 09 — Custom Middleware
====================================
ARCHITECTURE — Middleware Execution Order:

    REQUEST ARRIVES
         │
         ▼
    Middleware 1 (outermost — added last)
      before_code()
      │
      ▼
    Middleware 2
      before_code()
      │
      ▼
    Middleware 3 (innermost — added first)
      before_code()
      │
      ▼
    ENDPOINT executes
      │
      ▼
    Middleware 3 — after_code()
      │
      ▼
    Middleware 2 — after_code()
      │
      ▼
    Middleware 1 — after_code()
      │
      ▼
    RESPONSE SENT

PATTERNS in this lab:

  CorrelationIDMiddleware:
    - Read X-Correlation-ID from request header
    - If missing: generate a new UUID
    - Store in request.state.correlation_id
    - Add to response headers: X-Correlation-ID: <uuid>
    - Purpose: trace a single request across services in distributed system

  TimingMiddleware:
    - Record start time BEFORE calling next
    - After response: add X-Process-Time: <float>ms header
    - Purpose: latency monitoring without touching endpoint code

  BlockedIPMiddleware:
    - Check request.client.host against BLOCKED_IPS set
    - If blocked: return 403 JSON response IMMEDIATELY (short-circuit)
    - Never calls next — endpoint is never reached
    - Purpose: IP-level ban without auth layer

  MaintenanceModeMiddleware:
    - Read MAINTENANCE_MODE flag
    - If True: return 503 JSON immediately with Retry-After header
    - Short-circuit same as BlockedIP
    - If /health path: always pass through (liveness check must work)

INTERVIEW ANSWER:
  "FastAPI middleware BaseHTTPMiddleware mein __init__ aur dispatch() implement
   karte hain. dispatch() mein `await call_next(request)` endpoint ko call karta
   hai — isse pehle ka code 'before', baad ka code 'after' request handler hai.
   Short-circuit ke liye Response() seedha return kar do, call_next mat bulao."

TASK:
  1. TODO 1: CorrelationIDMiddleware — read/generate X-Correlation-ID, add to response
  2. TODO 2: TimingMiddleware — measure + add X-Process-Time header (ms)
  3. TODO 3: BlockedIPMiddleware — return 403 JSON for IPs in BLOCKED_IPS
  4. TODO 4: MaintenanceModeMiddleware — return 503 JSON (pass /health through)
  5. Run: python 09_custom_fastapi_middleware.py

Prereq: pip install fastapi httpx
"""

from __future__ import annotations

import asyncio
import time
import uuid

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from httpx import ASGITransport, AsyncClient
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

app = FastAPI(title="Lab 09 — Custom Middleware")

BLOCKED_IPS     = {"10.0.0.1", "192.168.1.100"}
MAINTENANCE_MODE = False  # toggle in tests via monkeypatch or direct assignment


# ════════════════════════════════════════════════════════════════════════════
# TODO 1 — CorrelationIDMiddleware
# ════════════════════════════════════════════════════════════════════════════
"""
Implement CorrelationIDMiddleware(BaseHTTPMiddleware):

  dispatch(request: Request, call_next) -> Response:
    1. correlation_id = request.headers.get("X-Correlation-ID") or str(uuid.uuid4())
    2. request.state.correlation_id = correlation_id  ← available to endpoint
    3. response = await call_next(request)
    4. response.headers["X-Correlation-ID"] = correlation_id
    5. return response

  Hint:
    class CorrelationIDMiddleware(BaseHTTPMiddleware):
        async def dispatch(self, request: Request, call_next) -> Response:
            correlation_id = request.headers.get("X-Correlation-ID") or str(uuid.uuid4())
            request.state.correlation_id = correlation_id
            response = await call_next(request)
            response.headers["X-Correlation-ID"] = correlation_id
            return response
"""

class CorrelationIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        raise NotImplementedError(
            "TODO 1: read/generate X-Correlation-ID, set on request.state, add to response headers"
        )


# ════════════════════════════════════════════════════════════════════════════
# TODO 2 — TimingMiddleware
# ════════════════════════════════════════════════════════════════════════════
"""
Implement TimingMiddleware(BaseHTTPMiddleware):

  dispatch(request: Request, call_next) -> Response:
    1. start = time.perf_counter()
    2. response = await call_next(request)
    3. duration_ms = (time.perf_counter() - start) * 1000
    4. response.headers["X-Process-Time"] = f"{duration_ms:.2f}ms"
    5. return response
"""

class TimingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        raise NotImplementedError(
            "TODO 2: record start time, call_next, add X-Process-Time header"
        )


# ════════════════════════════════════════════════════════════════════════════
# TODO 3 — BlockedIPMiddleware
# ════════════════════════════════════════════════════════════════════════════
"""
Implement BlockedIPMiddleware(BaseHTTPMiddleware):

  dispatch(request: Request, call_next) -> Response:
    1. client_ip = request.client.host if request.client else "unknown"
    2. If client_ip in BLOCKED_IPS:
         return JSONResponse(
             {"detail": "Access denied", "ip": client_ip},
             status_code=403
         )
    3. return await call_next(request)

  Note: short-circuit means call_next is NEVER called for blocked IPs.
        The endpoint is never reached.
"""

class BlockedIPMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        raise NotImplementedError(
            "TODO 3: check request.client.host against BLOCKED_IPS, return 403 or call_next"
        )


# ════════════════════════════════════════════════════════════════════════════
# TODO 4 — MaintenanceModeMiddleware
# ════════════════════════════════════════════════════════════════════════════
"""
Implement MaintenanceModeMiddleware(BaseHTTPMiddleware):

  dispatch(request: Request, call_next) -> Response:
    1. If MAINTENANCE_MODE is True AND request.url.path != "/health":
         return JSONResponse(
             {"detail": "Service under maintenance. Try again later."},
             status_code=503,
             headers={"Retry-After": "300"}
         )
    2. return await call_next(request)

  Note: /health must ALWAYS pass through so load balancers know the process is alive.
"""

class MaintenanceModeMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        raise NotImplementedError(
            "TODO 4: return 503 if MAINTENANCE_MODE, always pass /health"
        )


# ════════════════════════════════════════════════════════════════════════════
# MIDDLEWARE REGISTRATION (order matters — last added = outermost)
# ════════════════════════════════════════════════════════════════════════════

app.add_middleware(CorrelationIDMiddleware)
app.add_middleware(TimingMiddleware)
app.add_middleware(BlockedIPMiddleware)
app.add_middleware(MaintenanceModeMiddleware)


# ════════════════════════════════════════════════════════════════════════════
# ENDPOINTS
# ════════════════════════════════════════════════════════════════════════════

@app.get("/ping")
async def ping(request: Request):
    return {
        "message": "pong",
        "correlation_id": getattr(request.state, "correlation_id", None),
    }


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/slow")
async def slow_endpoint():
    await asyncio.sleep(0.05)
    return {"done": True}


# ════════════════════════════════════════════════════════════════════════════
# TESTS
# ════════════════════════════════════════════════════════════════════════════

async def run_tests():
    import importlib
    import sys

    # Reset maintenance mode to False before tests
    current_module = sys.modules[__name__]

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        passed = 0
        failed = 0

        # ── TODO 1: CorrelationID ─────────────────────────────────────────

        print("\n── TODO 1: CorrelationIDMiddleware ──")

        # 1a. Provided header echoed back
        cid = "my-trace-12345"
        resp = await client.get("/ping", headers={"X-Correlation-ID": cid})
        if resp.headers.get("X-Correlation-ID") == cid:
            print(f"✅ 1a. Provided X-Correlation-ID echoed: {cid}")
            passed += 1
        else:
            print(f"❌ 1a. FAIL: Expected '{cid}'. Got: {resp.headers.get('X-Correlation-ID')}")
            failed += 1

        # 1b. Missing header → generated UUID
        resp = await client.get("/ping")
        hdr = resp.headers.get("X-Correlation-ID", "")
        try:
            uuid.UUID(hdr)
            print(f"✅ 1b. Missing header → generated UUID: {hdr}")
            passed += 1
        except ValueError:
            print(f"❌ 1b. FAIL: Expected UUID. Got: '{hdr}'")
            failed += 1

        # 1c. correlation_id available in endpoint via request.state
        resp = await client.get("/ping", headers={"X-Correlation-ID": "trace-abc"})
        body = resp.json()
        if body.get("correlation_id") == "trace-abc":
            print("✅ 1c. request.state.correlation_id visible in endpoint")
            passed += 1
        else:
            print(f"❌ 1c. FAIL: endpoint sees correlation_id={body.get('correlation_id')!r}, expected 'trace-abc'")
            failed += 1

        # ── TODO 2: Timing ────────────────────────────────────────────────

        print("\n── TODO 2: TimingMiddleware ──")

        # 2a. X-Process-Time header present and ends with 'ms'
        resp = await client.get("/ping")
        pt = resp.headers.get("X-Process-Time", "")
        if pt.endswith("ms"):
            print(f"✅ 2a. X-Process-Time present: {pt}")
            passed += 1
        else:
            print(f"❌ 2a. FAIL: X-Process-Time should end with 'ms'. Got: '{pt}'")
            failed += 1

        # 2b. Slow endpoint shows higher time
        resp_slow  = await client.get("/slow")
        resp_fast  = await client.get("/ping")
        slow_ms    = float(resp_slow.headers.get("X-Process-Time", "0ms").replace("ms", ""))
        fast_ms    = float(resp_fast.headers.get("X-Process-Time", "0ms").replace("ms", ""))
        if slow_ms > fast_ms:
            print(f"✅ 2b. /slow ({slow_ms:.1f}ms) > /ping ({fast_ms:.1f}ms)")
            passed += 1
        else:
            print(f"❌ 2b. FAIL: /slow ({slow_ms:.1f}ms) should be > /ping ({fast_ms:.1f}ms)")
            failed += 1

        # ── TODO 3: BlockedIP ─────────────────────────────────────────────

        print("\n── TODO 3: BlockedIPMiddleware ──")

        # 3a. Normal request (127.0.0.1) — not blocked
        resp = await client.get("/ping")
        if resp.status_code == 200:
            print("✅ 3a. 127.0.0.1 not blocked (normal request OK)")
            passed += 1
        else:
            print(f"❌ 3a. FAIL: Normal request should be 200. Got {resp.status_code}")
            failed += 1

        # 3b. Blocked IP test — simulate by adding test IP to BLOCKED_IPS temporarily
        import sys as _sys
        mod = _sys.modules[__name__]
        mod.BLOCKED_IPS.add("127.0.0.1")
        resp = await client.get("/ping")
        mod.BLOCKED_IPS.discard("127.0.0.1")
        if resp.status_code == 403:
            print("✅ 3b. Blocked IP returns 403")
            passed += 1
        else:
            print(f"❌ 3b. FAIL: Blocked IP should return 403. Got {resp.status_code}: {resp.json()}")
            failed += 1

        # 3c. Response body has 'detail' key
        mod.BLOCKED_IPS.add("127.0.0.1")
        resp = await client.get("/ping")
        mod.BLOCKED_IPS.discard("127.0.0.1")
        if "detail" in resp.json():
            print("✅ 3c. 403 response body has 'detail' key")
            passed += 1
        else:
            print(f"❌ 3c. FAIL: 403 body should have 'detail'. Got: {resp.json()}")
            failed += 1

        # ── TODO 4: MaintenanceMode ───────────────────────────────────────

        print("\n── TODO 4: MaintenanceModeMiddleware ──")

        # 4a. Maintenance off — normal request works
        resp = await client.get("/ping")
        if resp.status_code == 200:
            print("✅ 4a. Maintenance OFF → /ping returns 200")
            passed += 1
        else:
            print(f"❌ 4a. FAIL: Maintenance OFF, /ping should be 200. Got {resp.status_code}")
            failed += 1

        # 4b. Maintenance ON — /ping blocked
        mod.MAINTENANCE_MODE = True
        resp = await client.get("/ping")
        mod.MAINTENANCE_MODE = False
        if resp.status_code == 503:
            print("✅ 4b. Maintenance ON → /ping returns 503")
            passed += 1
        else:
            print(f"❌ 4b. FAIL: Maintenance ON, /ping should be 503. Got {resp.status_code}")
            failed += 1

        # 4c. Maintenance ON — /health still works
        mod.MAINTENANCE_MODE = True
        resp = await client.get("/health")
        mod.MAINTENANCE_MODE = False
        if resp.status_code == 200:
            print("✅ 4c. Maintenance ON → /health still returns 200 (pass-through)")
            passed += 1
        else:
            print(f"❌ 4c. FAIL: /health should bypass maintenance. Got {resp.status_code}")
            failed += 1

        # 4d. 503 has Retry-After header
        mod.MAINTENANCE_MODE = True
        resp = await client.get("/ping")
        mod.MAINTENANCE_MODE = False
        if "retry-after" in {k.lower() for k in resp.headers}:
            print("✅ 4d. 503 response has Retry-After header")
            passed += 1
        else:
            print(f"❌ 4d. FAIL: 503 should have Retry-After. Headers: {dict(resp.headers)}")
            failed += 1

        # ── Summary ───────────────────────────────────────────────────────
        print(f"\n{'═'*50}")
        print(f"  {passed} passed  |  {failed} failed")
        if failed == 0:
            print("  ✅ ALL PASS — Lab 09 complete!")
        else:
            print("  ❌ Fix the failing TODOs above and rerun.")
        print('═'*50)


# ════════════════════════════════════════════════════════════════════════════
# SOCH (Answer ALOUD before moving to Lab 10)
# ════════════════════════════════════════════════════════════════════════════
"""
SOCH:

Q1: FastAPI mein middleware execution order kya hota hai?
    Last added middleware outermost kyon hoti hai?

Q2: Short-circuit middleware kaise kaam karta hai?
    `call_next` kabhi nahi call hota — kya endpoint ke side effects hote hain?

Q3: CorrelationID ka kya use hai distributed systems mein?
    Bina correlation ID ke debugging kion mushkil hoti hai?

Q4: Timing middleware production mein kyon useful hai?
    (Monitoring, SLA tracking, p99 latency without touching endpoint code)

Q5: BaseHTTPMiddleware ki performance limitation kya hai? (Advanced)
    (Starlette's BaseHTTPMiddleware buffers streaming responses — use pure
     ASGI middleware for streaming; BaseHTTPMiddleware fine for most cases)
"""

if __name__ == "__main__":
    asyncio.run(run_tests())
