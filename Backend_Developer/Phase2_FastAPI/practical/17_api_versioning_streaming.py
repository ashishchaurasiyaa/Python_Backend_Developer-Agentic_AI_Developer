"""
============================================================
API VERSIONING + STREAMING RESPONSES — Practical
============================================================
Run:
    uvicorn 17_api_versioning_streaming:app --reload

Try:
    curl http://localhost:8000/v1/users/1
    curl http://localhost:8000/v2/users/1
    curl -H "X-API-Version: v1" http://localhost:8000/users/1
    curl http://localhost:8000/export/users.csv
    curl http://localhost:8000/export/users.ndjson
    curl http://localhost:8000/sse/progress
"""
import asyncio
import json
import time
from dataclasses import dataclass


# ============================================================
# 1. SHARED MODELS / DATA
# ============================================================
@dataclass
class User:
    id: int
    first_name: str
    last_name: str
    email: str


USERS = [
    User(1, "Ashish", "Chaurasiya", "ashish@example.com"),
    User(2, "Bob", "Smith", "bob@example.com"),
    User(3, "Carol", "Davis", "carol@example.com"),
]


# ============================================================
# 2. URL-PATH VERSIONING
# ============================================================
try:
    from fastapi import FastAPI, APIRouter, Request, Response, Header, HTTPException
    from fastapi.responses import StreamingResponse, JSONResponse
    from datetime import datetime, date
    from typing import Annotated, AsyncIterator

    app = FastAPI(title="Versioning + Streaming Demo")

    # --- V1 Router ---
    v1 = APIRouter(prefix="/v1", tags=["v1"])

    @v1.get("/users/{user_id}")
    async def get_user_v1(user_id: int, response: Response):
        user = next((u for u in USERS if u.id == user_id), None)
        if not user:
            raise HTTPException(404)
        # V1 = old flat shape
        response.headers["Deprecation"] = "true"
        response.headers["Sunset"] = "Wed, 31 Dec 2025 23:59:59 GMT"
        response.headers["Link"] = '</v2/users>; rel="successor-version"'
        return {
            "id": user.id,
            "name": f"{user.first_name} {user.last_name}",   # combined
            "email": user.email,
        }

    # --- V2 Router ---
    v2 = APIRouter(prefix="/v2", tags=["v2"])

    @v2.get("/users/{user_id}")
    async def get_user_v2(user_id: int):
        user = next((u for u in USERS if u.id == user_id), None)
        if not user:
            raise HTTPException(404)
        # V2 = structured profile + HATEOAS links
        return {
            "id": user.id,
            "profile": {
                "first_name": user.first_name,
                "last_name": user.last_name,
            },
            "email": user.email,
            "_links": {
                "self": {"href": f"/v2/users/{user.id}"},
                "delete": {"href": f"/v2/users/{user.id}", "method": "DELETE"},
            },
        }

    app.include_router(v1)
    app.include_router(v2)

    # ============================================================
    # 3. HEADER-BASED VERSIONING
    # ============================================================
    @app.get("/users/{user_id}")
    async def get_user_versioned(
        user_id: int,
        api_version: Annotated[str, Header(alias="X-API-Version")] = "v2",
    ):
        user = next((u for u in USERS if u.id == user_id), None)
        if not user:
            raise HTTPException(404)
        if api_version == "v1":
            return {"id": user.id, "name": f"{user.first_name} {user.last_name}"}
        elif api_version == "v2":
            return {"id": user.id, "profile": {"first_name": user.first_name}}
        raise HTTPException(400, f"Unsupported version: {api_version}")

    # ============================================================
    # 4. DATE-BASED VERSIONING (Stripe style)
    # ============================================================
    @app.get("/charges")
    async def list_charges(
        stripe_version: Annotated[str | None, Header(alias="Stripe-Version")] = None,
    ):
        if stripe_version:
            try:
                v_date = datetime.strptime(stripe_version, "%Y-%m-%d").date()
            except ValueError:
                raise HTTPException(400, "Invalid Stripe-Version format")
        else:
            v_date = date.today()

        if v_date < date(2023, 1, 1):
            return {"charges": [{"amount": 1000}]}   # old: amount in cents
        elif v_date < date(2024, 4, 10):
            return {"charges": [{"amount": 10, "currency": "USD"}]}
        else:
            return {
                "charges": [{"amount": {"value": 10, "currency": "USD"}, "id": "ch_1"}],
            }

    # ============================================================
    # 5. STREAMING: CSV EXPORT
    # ============================================================
    @app.get("/export/users.csv")
    async def export_csv():
        async def csv_generator():
            yield "id,first_name,last_name,email\n"
            for u in USERS:
                await asyncio.sleep(0.01)
                yield f"{u.id},{u.first_name},{u.last_name},{u.email}\n"

        return StreamingResponse(
            csv_generator(),
            media_type="text/csv",
            headers={
                "Content-Disposition": 'attachment; filename="users.csv"',
                "X-Accel-Buffering": "no",   # for Nginx
            },
        )

    # ============================================================
    # 6. STREAMING: NDJSON
    # ============================================================
    @app.get("/export/users.ndjson")
    async def export_ndjson():
        async def ndjson_generator():
            for u in USERS:
                await asyncio.sleep(0.01)
                yield json.dumps({
                    "id": u.id,
                    "first_name": u.first_name,
                    "email": u.email,
                }) + "\n"

        return StreamingResponse(
            ndjson_generator(),
            media_type="application/x-ndjson",
        )

    # ============================================================
    # 7. STREAMING: SERVER-SENT EVENTS (SSE)
    # ============================================================
    @app.get("/sse/progress")
    async def sse_progress():
        async def event_stream():
            for i in range(20):
                payload = {"step": i, "total": 20, "ts": time.time()}
                yield f"event: progress\ndata: {json.dumps(payload)}\n\n"
                await asyncio.sleep(0.3)
            yield 'event: done\ndata: {"status":"complete"}\n\n'

        return StreamingResponse(
            event_stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    # ============================================================
    # 8. STREAMING: LLM TOKEN-BY-TOKEN (simulated)
    # ============================================================
    @app.post("/chat/stream")
    async def chat_stream():
        response_tokens = ["Hello", ",", " I", " am", " an", " AI", " assistant", "."]

        async def llm_stream():
            for token in response_tokens:
                payload = {"token": token}
                yield f"data: {json.dumps(payload)}\n\n"
                await asyncio.sleep(0.2)
            yield "data: [DONE]\n\n"

        return StreamingResponse(llm_stream(), media_type="text/event-stream")

    # ============================================================
    # 9. STREAMING: LARGE FILE / CHUNKED
    # ============================================================
    @app.get("/stream/random-bytes")
    async def random_bytes(size_mb: int = 10):
        import os

        async def byte_stream():
            chunks = size_mb * 1024 // 8   # 8KB chunks
            for _ in range(chunks):
                yield os.urandom(8192)

        return StreamingResponse(
            byte_stream(),
            media_type="application/octet-stream",
            headers={"Content-Disposition": f'attachment; filename="random_{size_mb}mb.bin"'},
        )

    # ============================================================
    # 10. STREAMING WITH HEARTBEAT (keep-alive)
    # ============================================================
    @app.get("/sse/notifications")
    async def sse_notifications():
        async def stream():
            last_heartbeat = time.monotonic()
            for i in range(5):
                # Send actual event
                yield f"event: notification\ndata: Message {i}\n\n"
                # Heartbeat every 30s in real apps (here: between messages)
                if time.monotonic() - last_heartbeat > 5:
                    yield ": heartbeat\n\n"      # SSE comment line
                    last_heartbeat = time.monotonic()
                await asyncio.sleep(2)

        return StreamingResponse(stream(), media_type="text/event-stream")

    # ============================================================
    # 11. HOMEPAGE WITH USAGE
    # ============================================================
    @app.get("/", include_in_schema=False)
    async def home():
        return {
            "versioning_endpoints": {
                "URL path v1"  : "GET /v1/users/1",
                "URL path v2"  : "GET /v2/users/1",
                "Header version": "GET /users/1 with header X-API-Version: v1 or v2",
                "Date-based"   : "GET /charges with header Stripe-Version: 2023-06-01",
            },
            "streaming_endpoints": {
                "CSV export"     : "GET /export/users.csv",
                "NDJSON export"  : "GET /export/users.ndjson",
                "SSE progress"   : "GET /sse/progress",
                "LLM token stream": "POST /chat/stream",
                "Random bytes"   : "GET /stream/random-bytes?size_mb=10",
                "SSE w/heartbeat": "GET /sse/notifications",
            },
        }

except ImportError:
    print("Install: pip install fastapi uvicorn")
    app = None


# ============================================================
# 12. CLIENT EXAMPLES (Reference)
# ============================================================
CURL_TESTS = """
# URL Versioning
curl http://localhost:8000/v1/users/1
curl http://localhost:8000/v2/users/1

# Header Versioning
curl -H "X-API-Version: v1" http://localhost:8000/users/1
curl -H "X-API-Version: v2" http://localhost:8000/users/1

# Date Versioning (Stripe-style)
curl -H "Stripe-Version: 2022-01-01" http://localhost:8000/charges
curl -H "Stripe-Version: 2024-06-01" http://localhost:8000/charges

# Streaming CSV (constant memory regardless of size)
curl http://localhost:8000/export/users.csv

# NDJSON (line-by-line JSON)
curl http://localhost:8000/export/users.ndjson | jq .

# Server-Sent Events
curl -N http://localhost:8000/sse/progress

# LLM streaming
curl -N -X POST http://localhost:8000/chat/stream
"""

BROWSER_EXAMPLES = """
// SSE in browser
const events = new EventSource("/sse/progress");
events.addEventListener("progress", (e) => {
    const data = JSON.parse(e.data);
    console.log("Progress:", data);
});
events.addEventListener("done", () => events.close());

// Process NDJSON streaming
const response = await fetch("/export/users.ndjson");
const reader = response.body.getReader();
const decoder = new TextDecoder();
let buffer = "";
while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\\n");
    buffer = lines.pop();   // last (possibly incomplete) line
    for (const line of lines) {
        if (line) console.log(JSON.parse(line));
    }
}
"""

NGINX_STREAMING_CONFIG = """
# Nginx config for streaming endpoints
location ~* /(sse|stream|export)/ {
    proxy_pass http://app;
    proxy_buffering off;          # don't buffer
    proxy_cache off;
    proxy_http_version 1.1;
    proxy_set_header Connection "";
    chunked_transfer_encoding on;
}
"""


if __name__ == "__main__":
    print("=" * 60)
    print("API Versioning + Streaming Demo")
    print("=" * 60)
    print("\nRun:  uvicorn 17_api_versioning_streaming:app --reload")
    print("\n--- curl tests ---")
    print(CURL_TESTS)
    print("\n--- Browser JS ---")
    print(BROWSER_EXAMPLES)
    print("\n--- Nginx config ---")
    print(NGINX_STREAMING_CONFIG)
