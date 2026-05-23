"""
GraphQL + SSE + WebSocket + File Upload + Content Negotiation
═══════════════════════════════════════════════════════════════
Run:
  pip install fastapi uvicorn strawberry-graphql[fastapi] websockets aiofiles httpx redis

  Terminal 1 (server):
    uvicorn 02_graphql_sse_websocket_practical:app --reload --port 8001

  Terminal 2 (tests):
    python 02_graphql_sse_websocket_practical.py

Prerequisites:
  docker run -d -p 6379:6379 redis   (for SSE pub/sub demo)

Sections:
  1. GraphQL — Schema, Query, Mutation, Subscription, DataLoader (N+1 fix)
  2. SSE — LLM-style token streaming, job progress
  3. WebSocket — Chat room (bidirectional)
  4. File Upload + Streaming Download
  5. Content Negotiation (JSON / CSV / XML)
  6. CORS headers verification

INTERVIEW QUICK REFERENCE at bottom.
"""

import asyncio
import csv
import io
import json
import os
import time
import uuid
from datetime import datetime, timezone
from typing import AsyncGenerator, Optional

import aiofiles
import httpx
import strawberry
from fastapi import (
    FastAPI, Request, Response, WebSocket, WebSocketDisconnect,
    UploadFile, File, Depends, Header,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse, FileResponse
from strawberry.fastapi import GraphQLRouter
from strawberry.dataloader import DataLoader
from strawberry.types import Info


# ═══════════════════════════════════════════════════════════
# IN-MEMORY FAKE DATABASE
# ═══════════════════════════════════════════════════════════

USERS_DB: dict[int, dict] = {
    1: {"id": 1, "name": "Alice",   "email": "alice@test.com",   "plan": "premium"},
    2: {"id": 2, "name": "Bob",     "email": "bob@test.com",     "plan": "free"},
    3: {"id": 3, "name": "Charlie", "email": "charlie@test.com", "plan": "free"},
}

POSTS_DB: dict[int, dict] = {
    1: {"id": 1, "title": "FastAPI Deep Dive",   "author_id": 1, "status": "published", "tags": ["python", "api"]},
    2: {"id": 2, "title": "Redis Patterns",      "author_id": 1, "status": "published", "tags": ["redis"]},
    3: {"id": 3, "title": "GraphQL vs REST",     "author_id": 2, "status": "published", "tags": ["graphql", "api"]},
    4: {"id": 4, "title": "Draft Post",          "author_id": 2, "status": "draft",     "tags": []},
    5: {"id": 5, "title": "Async Python Guide",  "author_id": 3, "status": "published", "tags": ["python", "async"]},
}

UPLOAD_DIR = "/tmp/api_uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)


# ═══════════════════════════════════════════════════════════
# SECTION 1: GraphQL — Strawberry
# ═══════════════════════════════════════════════════════════

# ─── Types ───
@strawberry.type
class User:
    id:    strawberry.ID
    name:  str
    email: str
    plan:  str

    @strawberry.field
    async def posts(self, info: Info) -> list["Post"]:
        """
        INTERVIEW: DataLoader kyu?
        Bina DataLoader: 1 user query per post (N+1 problem)
        DataLoader ke saath: ek batch query for all users → O(1) queries
        """
        loader: DataLoader = info.context["loaders"]["posts_by_author"]
        return await loader.load(int(self.id))


@strawberry.type
class Post:
    id:        strawberry.ID
    title:     str
    status:    str
    tags:      list[str]

    @strawberry.field
    async def author(self, info: Info) -> User:
        loader: DataLoader = info.context["loaders"]["user_by_id"]
        return await loader.load(int(self.id))


@strawberry.input
class CreatePostInput:
    title:  str
    tags:   list[str] = strawberry.field(default_factory=list)


# ─── DataLoader functions (batch loading) ───
async def batch_load_users(user_ids: list[int]) -> list[Optional[User]]:
    """
    Called ONCE with all collected user IDs.
    1 DB query instead of N queries.
    """
    result = {uid: USERS_DB.get(uid) for uid in user_ids}
    return [
        User(id=str(u["id"]), name=u["name"], email=u["email"], plan=u["plan"])
        if (u := result.get(uid)) else None
        for uid in user_ids
    ]


async def batch_load_posts_by_author(author_ids: list[int]) -> list[list[Post]]:
    """Batch load posts grouped by author_id."""
    grouped: dict[int, list[Post]] = {aid: [] for aid in author_ids}
    for post in POSTS_DB.values():
        if post["author_id"] in grouped and post["status"] == "published":
            grouped[post["author_id"]].append(
                Post(id=str(post["id"]), title=post["title"],
                     status=post["status"], tags=post["tags"])
            )
    return [grouped[aid] for aid in author_ids]


# ─── Context factory ───
async def get_graphql_context() -> dict:
    return {
        "loaders": {
            "user_by_id":       DataLoader(load_fn=batch_load_users),
            "posts_by_author":  DataLoader(load_fn=batch_load_posts_by_author),
        }
    }


# ─── Query ───
@strawberry.type
class Query:
    @strawberry.field
    async def user(self, id: strawberry.ID) -> Optional[User]:
        u = USERS_DB.get(int(id))
        if not u:
            return None
        return User(id=str(u["id"]), name=u["name"], email=u["email"], plan=u["plan"])

    @strawberry.field
    async def users(self) -> list[User]:
        return [
            User(id=str(u["id"]), name=u["name"], email=u["email"], plan=u["plan"])
            for u in USERS_DB.values()
        ]

    @strawberry.field
    async def posts(self, status: Optional[str] = None) -> list[Post]:
        posts = POSTS_DB.values()
        if status:
            posts = [p for p in posts if p["status"] == status]
        return [
            Post(id=str(p["id"]), title=p["title"], status=p["status"], tags=p["tags"])
            for p in posts
        ]


# ─── Mutation ───
@strawberry.type
class Mutation:
    @strawberry.mutation
    async def create_post(self, input: CreatePostInput) -> Post:
        new_id = max(POSTS_DB.keys()) + 1
        post   = {
            "id": new_id, "title": input.title,
            "author_id": 1, "status": "draft", "tags": input.tags,
        }
        POSTS_DB[new_id] = post

        # Publish to SSE stream (for Subscription demo)
        _post_events.append(post)

        return Post(id=str(new_id), title=post["title"],
                    status=post["status"], tags=post["tags"])

    @strawberry.mutation
    async def publish_post(self, id: strawberry.ID) -> Optional[Post]:
        post = POSTS_DB.get(int(id))
        if not post:
            return None
        post["status"] = "published"
        return Post(id=str(post["id"]), title=post["title"],
                    status=post["status"], tags=post["tags"])


# ─── Subscription (real-time via async generator) ───
_post_events: list[dict] = []


@strawberry.type
class Subscription:
    @strawberry.subscription
    async def post_created(self) -> AsyncGenerator[Post, None]:
        """
        INTERVIEW: GraphQL Subscription kaise kaam karta hai?
        WebSocket connection maintain hoti hai.
        Server events async generator se yield karta hai.
        Production mein: Redis Pub/Sub se events broadcast karo.
        """
        seen = len(_post_events)
        while True:
            await asyncio.sleep(0.5)
            if len(_post_events) > seen:
                for post in _post_events[seen:]:
                    yield Post(id=str(post["id"]), title=post["title"],
                               status=post["status"], tags=post["tags"])
                seen = len(_post_events)


# ─── Schema + Router ───
schema = strawberry.Schema(
    query=Query,
    mutation=Mutation,
    subscription=Subscription,
)

graphql_router = GraphQLRouter(
    schema,
    context_getter=get_graphql_context,
    graphiql=True,   # GraphiQL playground at /graphql
)


# ═══════════════════════════════════════════════════════════
# SECTION 2: SSE — Server-Sent Events
# ═══════════════════════════════════════════════════════════

async def token_stream_generator(text: str) -> AsyncGenerator[str, None]:
    """
    Simulate LLM token-by-token streaming.
    INTERVIEW: SSE format?
      data: <payload>\n\n          → simple message
      event: <name>\n              → named event
      data: <payload>\n\n
      id: <id>\n                   → for reconnect (Last-Event-ID)
      : keepalive\n\n              → comment (ping)
    """
    words = text.split()
    for i, word in enumerate(words):
        await asyncio.sleep(0.08)   # simulate token generation delay
        payload = json.dumps({"token": word + " ", "index": i})
        yield f"data: {payload}\n\n"

    # Final event with metadata
    yield f"event: done\ndata: {json.dumps({'total_tokens': len(words)})}\n\n"
    yield "data: [DONE]\n\n"


async def job_progress_generator(job_id: str) -> AsyncGenerator[str, None]:
    """Simulate background job progress via SSE."""
    steps = [
        (10,  "Initializing..."),
        (25,  "Loading data..."),
        (50,  "Processing..."),
        (75,  "Generating output..."),
        (90,  "Finalizing..."),
        (100, "Complete!"),
    ]
    for progress, message in steps:
        await asyncio.sleep(0.5)
        payload = json.dumps({"job_id": job_id, "progress": progress, "message": message})
        yield f"id: {progress}\nevent: progress\ndata: {payload}\n\n"

    # Keepalive example
    yield ": keepalive\n\n"


# ═══════════════════════════════════════════════════════════
# SECTION 3: WebSocket — Chat Room
# ═══════════════════════════════════════════════════════════

class ChatRoomManager:
    def __init__(self):
        self.rooms: dict[str, list[WebSocket]] = {}
        self.history: dict[str, list[dict]]    = {}

    async def connect(self, room: str, ws: WebSocket, username: str):
        await ws.accept()
        self.rooms.setdefault(room, []).append(ws)
        self.history.setdefault(room, [])
        # Send history to new joiner
        for msg in self.history[room][-10:]:
            await ws.send_json(msg)
        # Announce join
        await self.broadcast(room, {
            "type":    "system",
            "message": f"{username} joined the room",
            "time":    datetime.utcnow().isoformat(),
        }, exclude=ws)

    def disconnect(self, room: str, ws: WebSocket):
        if room in self.rooms:
            self.rooms[room].remove(ws)

    async def broadcast(self, room: str, data: dict, exclude: WebSocket = None):
        self.history[room].append(data)
        for ws in self.rooms.get(room, []):
            if ws is not exclude:
                try:
                    await ws.send_json(data)
                except Exception:
                    pass

    def active_users(self, room: str) -> int:
        return len(self.rooms.get(room, []))


chat_manager = ChatRoomManager()


# ═══════════════════════════════════════════════════════════
# FASTAPI APP + ROUTES
# ═══════════════════════════════════════════════════════════

app = FastAPI(title="GraphQL + SSE + WebSocket Demo", version="1.0.0")

# ─── CORS middleware ───
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID", "X-RateLimit-Remaining"],
    max_age=86400,
)

# ─── Mount GraphQL ───
app.include_router(graphql_router, prefix="/graphql")


# ─── SSE: LLM-style streaming ───
@app.post("/stream/llm")
async def stream_llm_response(payload: dict):
    """
    Simulates LLM token streaming (ChatGPT-style).
    INTERVIEW: Why SSE for LLM?
    - HTTP compatible (works through proxies)
    - Auto-reconnect built-in
    - One-way push — perfect for LLM output
    - No WebSocket overhead for one-way use case
    """
    prompt   = payload.get("prompt", "Hello World from the streaming API response")
    response = f"You asked: '{prompt}'. Here is a detailed answer about Python async programming and FastAPI best practices for building production APIs."

    return StreamingResponse(
        token_stream_generator(response),
        media_type="text/event-stream",
        headers={
            "Cache-Control":     "no-cache",
            "X-Accel-Buffering": "no",   # Nginx buffering disable
        },
    )


# ─── SSE: Job progress ───
@app.post("/stream/job")
async def start_job_stream(payload: dict):
    job_id = str(uuid.uuid4())
    return StreamingResponse(
        job_progress_generator(job_id),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache"},
    )


# ─── SSE: Live notifications feed ───
@app.get("/stream/notifications")
async def notification_stream(
    request: Request,
    last_event_id: Optional[str] = Header(None, alias="Last-Event-ID"),
):
    """
    INTERVIEW: Last-Event-ID kyu?
    Browser disconnect hone ke baad reconnect pe ye header bhejta hai.
    Server missed events replay karta hai from that ID.
    """
    SAMPLE_NOTIFICATIONS = [
        {"type": "like",    "message": "Alice liked your post"},
        {"type": "comment", "message": "Bob commented: 'Great article!'"},
        {"type": "follow",  "message": "Charlie started following you"},
    ]

    async def generate():
        for i, notif in enumerate(SAMPLE_NOTIFICATIONS):
            if last_event_id and i <= int(last_event_id):
                continue   # Skip already-seen events
            await asyncio.sleep(0.3)
            yield f"id: {i}\nevent: notification\ndata: {json.dumps(notif)}\n\n"

        # Keepalive
        while True:
            if await request.is_disconnected():
                break
            yield ": keepalive\n\n"
            await asyncio.sleep(15)

    return StreamingResponse(generate(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache"})


# ─── WebSocket: Chat Room ───
@app.websocket("/ws/chat/{room_id}")
async def chat_websocket(
    websocket: WebSocket,
    room_id:   str,
    username:  str = "Anonymous",
):
    """
    INTERVIEW: WebSocket lifecycle?
    1. HTTP GET /ws/chat/room1 + Upgrade: websocket
    2. 101 Switching Protocols
    3. Full-duplex WS connection
    4. receive_json() blocks until message arrives
    5. Either side sends CLOSE frame to disconnect
    """
    await chat_manager.connect(room_id, websocket, username)
    try:
        while True:
            data = await websocket.receive_json()
            await chat_manager.broadcast(room_id, {
                "type":    "message",
                "user":    username,
                "message": data.get("message", ""),
                "time":    datetime.utcnow().isoformat(),
                "room":    room_id,
                "users":   chat_manager.active_users(room_id),
            })
    except WebSocketDisconnect:
        chat_manager.disconnect(room_id, websocket)
        await chat_manager.broadcast(room_id, {
            "type":    "system",
            "message": f"{username} left the room",
            "time":    datetime.utcnow().isoformat(),
        })


# ─── File Upload ───
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB

@app.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    """
    INTERVIEW: Large file upload kaise handle karo?
    file.read() → memory mein load → bad for large files
    Stream in chunks → memory efficient
    """
    # Validate content type
    allowed = {"image/jpeg", "image/png", "image/gif", "application/pdf", "text/plain"}
    if file.content_type not in allowed:
        return JSONResponse(
            status_code=415,
            content={"error": f"Unsupported type: {file.content_type}. Allowed: {allowed}"},
        )

    # Stream to disk
    file_id   = str(uuid.uuid4())
    file_path = os.path.join(UPLOAD_DIR, f"{file_id}_{file.filename}")
    size      = 0

    async with aiofiles.open(file_path, "wb") as f:
        while chunk := await file.read(8192):   # 8KB chunks
            size += len(chunk)
            if size > MAX_FILE_SIZE:
                os.remove(file_path)
                return JSONResponse(
                    status_code=413,
                    content={"error": f"File too large. Max: {MAX_FILE_SIZE // 1024 // 1024}MB"},
                )
            await f.write(chunk)

    return {
        "file_id":      file_id,
        "filename":     file.filename,
        "content_type": file.content_type,
        "size_bytes":   size,
        "download_url": f"/download/{file_id}",
    }


# ─── Streaming File Download ───
@app.get("/download/{file_id}")
async def download_file(file_id: str):
    """
    INTERVIEW: FileResponse vs StreamingResponse?
    FileResponse:      entire file loaded → small files only
    StreamingResponse: chunked → large files, memory efficient
    """
    matches = [f for f in os.listdir(UPLOAD_DIR) if f.startswith(file_id)]
    if not matches:
        return JSONResponse(status_code=404, content={"error": "File not found"})

    file_path = os.path.join(UPLOAD_DIR, matches[0])
    filename  = matches[0][len(file_id) + 1:]   # strip uuid_ prefix
    file_size = os.path.getsize(file_path)

    async def stream_file():
        async with aiofiles.open(file_path, "rb") as f:
            while chunk := await f.read(65536):   # 64KB chunks
                yield chunk

    return StreamingResponse(
        stream_file(),
        media_type="application/octet-stream",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Length":      str(file_size),
            "Accept-Ranges":       "bytes",
        },
    )


# ─── Content Negotiation ───
@app.get("/export/users")
async def export_users(request: Request):
    """
    INTERVIEW: Content negotiation kaise karte hain?
    Accept: application/json → JSON
    Accept: text/csv         → CSV download
    Accept: application/xml  → XML

    Client batata hai kya chahiye → server appropriate format return karta hai
    """
    accept = request.headers.get("accept", "application/json")
    users  = list(USERS_DB.values())

    # CSV
    if "text/csv" in accept:
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=["id", "name", "email", "plan"])
        writer.writeheader()
        writer.writerows(users)
        return Response(
            content=output.getvalue(),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=users.csv"},
        )

    # XML
    if "application/xml" in accept:
        xml_rows = "".join(
            f"<user><id>{u['id']}</id><name>{u['name']}</name>"
            f"<email>{u['email']}</email><plan>{u['plan']}</plan></user>"
            for u in users
        )
        return Response(
            content=f'<?xml version="1.0"?><users>{xml_rows}</users>',
            media_type="application/xml",
        )

    # Default JSON
    return JSONResponse({"users": users, "total": len(users)})


# ─── CORS headers demo endpoint ───
@app.get("/cors-demo")
async def cors_demo(response: Response):
    """Check response headers to verify CORS is configured."""
    return {
        "message": "CORS demo endpoint",
        "cors_configured": True,
        "note": "Check browser DevTools → Network → Response Headers for CORS headers",
    }


# ═══════════════════════════════════════════════════════════
# TEST CLIENT
# ═══════════════════════════════════════════════════════════

async def run_tests():
    base = "http://localhost:8001"

    async with httpx.AsyncClient(base_url=base, timeout=30.0) as client:
        print("\n" + "=" * 60)
        print("GRAPHQL + SSE + WEBSOCKET + FILE — LIVE TESTS")
        print("=" * 60)

        # ─── 1. GraphQL Queries ───
        print("\n[1] GraphQL — Queries")
        gql_query = {
            "query": """
                query {
                    users {
                        id name plan
                        posts { id title tags }
                    }
                }
            """
        }
        r = await client.post("/graphql", json=gql_query)
        data = r.json()
        if "data" in data and data["data"]:
            users = data["data"].get("users", [])
            print(f"  users query → {len(users)} users")
            for u in users[:2]:
                print(f"    {u['name']} ({u['plan']}) → {len(u.get('posts', []))} posts")
        else:
            print(f"  Response: {data}")

        # ─── 2. GraphQL N+1 Demo (DataLoader) ───
        print("\n[2] GraphQL — Posts with authors (DataLoader prevents N+1)")
        r = await client.post("/graphql", json={
            "query": "{ posts(status: \"published\") { id title author { name } } }"
        })
        data = r.json()
        if "data" in data and data["data"]:
            posts = data["data"].get("posts", [])
            print(f"  {len(posts)} posts loaded with authors — 2 queries total (DataLoader batched)")
            for p in posts[:3]:
                print(f"    '{p['title']}' by {p.get('author', {}).get('name', '?')}")

        # ─── 3. GraphQL Mutation ───
        print("\n[3] GraphQL — Mutation (createPost)")
        r = await client.post("/graphql", json={
            "query": """
                mutation {
                    createPost(input: { title: "New Test Post", tags: ["test", "graphql"] }) {
                        id title status tags
                    }
                }
            """
        })
        data = r.json()
        if "data" in data and data["data"]:
            post = data["data"].get("createPost", {})
            print(f"  Created: id={post.get('id')} title='{post.get('title')}' status={post.get('status')}")

        # ─── 4. SSE — LLM Streaming ───
        print("\n[4] SSE — LLM Token Streaming")
        tokens_received = []
        async with client.stream("POST", "/stream/llm",
                                  json={"prompt": "Explain Python async"}) as response:
            async for line in response.aiter_lines():
                if line.startswith("data: ") and "[DONE]" not in line:
                    raw = line[6:]
                    if not raw.startswith("{"):
                        continue
                    try:
                        d = json.loads(raw)
                        if "token" in d:
                            tokens_received.append(d["token"])
                    except json.JSONDecodeError:
                        pass
                elif line.startswith("event: done"):
                    pass
        print(f"  Received {len(tokens_received)} tokens via SSE")
        print(f"  Assembled: {''.join(tokens_received[:8])}...")

        # ─── 5. SSE — Job Progress ───
        print("\n[5] SSE — Job Progress Streaming")
        progress_events = []
        async with client.stream("POST", "/stream/job", json={}) as response:
            async for line in response.aiter_lines():
                if line.startswith("data:") and "progress" in line:
                    try:
                        d = json.loads(line.split("data:", 1)[1].strip())
                        progress_events.append(d)
                        print(f"  Progress: {d.get('progress')}% — {d.get('message')}")
                    except Exception:
                        pass
        print(f"  Total events: {len(progress_events)}")

        # ─── 6. File Upload + Download ───
        print("\n[6] File Upload + Streaming Download")
        test_content = b"Hello World! This is a test file for upload/download demo.\n" * 100
        files = {"file": ("test_upload.txt", test_content, "text/plain")}
        r = await client.post("/upload", files=files)
        upload_result = r.json()
        print(f"  Upload: {r.status_code} — {upload_result.get('filename')} "
              f"({upload_result.get('size_bytes')} bytes)")

        file_id = upload_result.get("file_id")
        if file_id:
            r = await client.get(f"/download/{file_id}")
            downloaded = await r.aread()
            print(f"  Download: {r.status_code} — {len(downloaded)} bytes "
                  f"(match: {downloaded == test_content})")
            print(f"  Content-Disposition: {r.headers.get('content-disposition')}")

        # ─── 7. Content Negotiation ───
        print("\n[7] Content Negotiation")
        # JSON
        r = await client.get("/export/users",
                              headers={"Accept": "application/json"})
        print(f"  JSON: {r.status_code}, content-type={r.headers.get('content-type')}")
        print(f"    data preview: total={r.json().get('total')} users")

        # CSV
        r = await client.get("/export/users", headers={"Accept": "text/csv"})
        print(f"  CSV:  {r.status_code}, content-type={r.headers.get('content-type')}")
        lines = r.text.strip().split("\n")
        print(f"    rows: {len(lines)} (header + {len(lines)-1} users)")

        # XML
        r = await client.get("/export/users", headers={"Accept": "application/xml"})
        print(f"  XML:  {r.status_code}, content-type={r.headers.get('content-type')}")
        print(f"    preview: {r.text[:80]}...")

        # ─── 8. CORS headers ───
        print("\n[8] CORS Headers")
        r = await client.options("/cors-demo",
                                  headers={"Origin": "http://localhost:3000",
                                           "Access-Control-Request-Method": "GET"})
        cors_headers = {
            k: v for k, v in r.headers.items()
            if k.lower().startswith("access-control")
        }
        for k, v in cors_headers.items():
            print(f"  {k}: {v}")

        print("\n✓ All tests complete!")
        print(f"\nGraphQL Playground: http://localhost:8001/graphql")


if __name__ == "__main__":
    print("Starting tests...")
    print("Ensure server is running: uvicorn 02_graphql_sse_websocket_practical:app --port 8001")
    asyncio.run(run_tests())


# ═══════════════════════════════════════════════════════════
# INTERVIEW QUICK REFERENCE
# ═══════════════════════════════════════════════════════════
"""
Q: GraphQL N+1 problem solve kaise karte hain?
A: DataLoader — batch load karo.
   Bina DataLoader: 1 query for posts + N queries for each post's author
   DataLoader ke saath: 1 query for posts + 1 batch query (WHERE id IN (...))
   DataLoader per-request instantiate karo (not global — stale data risk)

Q: GraphQL vs REST kab choose karo?
A: GraphQL: multiple clients (mobile/web), complex nested data, over-fetching problem
   REST:    simple CRUD, file upload, caching critical, team unfamiliar with GQL

Q: SSE vs WebSocket kab?
A: SSE:       server → client only (LLM streaming, notifications, progress)
              HTTP, auto-reconnect, simpler
   WebSocket: bidirectional (chat, games, live collaboration)
              lower latency, binary support

Q: SSE format kya hai?
A: data: <payload>\n\n           (simple message)
   event: <name>\ndata: ...\n\n  (named event)
   id: <n>\ndata: ...\n\n        (with ID for reconnect)
   : keepalive\n\n               (comment/ping)

Q: Content negotiation kaise kaam karta hai?
A: Client: Accept: text/csv
   Server: response mein Content-Type: text/csv + CSV body
   Same URL → different format based on Accept header

Q: File upload stream kaise karo?
A: UploadFile.read(chunk_size) in while loop
   Sabse important: await file.read(8192) → 8KB at a time
   Poora file.read() → memory overflow on large files

Q: CORS allow_origins=["*"] with allow_credentials=True?
A: INVALID! Browser reject karta hai.
   Credentials ke saath: specific origins list karo
   Vary: Origin header bhi add karo (CDN ke liye)

Q: Strawberry subscription production mein kaise scale karo?
A: Single server: async generator kaam karta hai
   Multi-server: Redis Pub/Sub use karo
   - Publisher: redis.publish("channel", data)
   - Subscriber: pubsub.subscribe("channel") → async generator yield
   - Sab WebSocket connections same Redis channel se sunti hain
"""
