"""
Real-Time Collaborative Whiteboard / Editor — skeleton entry point.
Spec: ../02_FastAPI_RealTime_Whiteboard.md

Run:
    uvicorn main:app --reload
"""

import asyncio
import json
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query
from fastapi.responses import JSONResponse

app = FastAPI(title="Real-Time Collaborative Whiteboard", version="0.1.0")

# In-memory map: doc_id -> set of (WebSocket, user_info)
# In production this is per-pod; cross-pod fan-out uses Redis pub/sub.
local_connections: dict[str, set] = {}


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

@app.get("/health")
async def health():
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Document REST endpoints  (Week 1 milestone)
# ---------------------------------------------------------------------------
# TODO: POST   /docs                  — create document
# TODO: GET    /docs                  — list user's documents
# TODO: GET    /docs/{id}             — metadata
# TODO: PATCH  /docs/{id}             — update title / visibility
# TODO: DELETE /docs/{id}             — soft delete

@app.post("/docs")
async def create_doc(request_data: dict = None):
    # TODO: validate input (title, type: text|whiteboard|mindmap, visibility)
    # TODO: insert into documents table
    # TODO: return doc metadata
    return {"detail": "TODO: create_doc not yet implemented"}


@app.get("/docs")
async def list_docs():
    # TODO: list documents owned by current user (JWT)
    return {"items": [], "detail": "TODO"}


@app.get("/docs/{doc_id}")
async def get_doc(doc_id: str):
    # TODO: check access (owner / collaborator / share link / public)
    return {"detail": "TODO"}


# ---------------------------------------------------------------------------
# Sharing  (Week 3 milestone)
# ---------------------------------------------------------------------------
# TODO: POST   /docs/{id}/collaborators
# TODO: DELETE /docs/{id}/collaborators/{uid}
# TODO: POST   /docs/{id}/share-links
# TODO: DELETE /docs/{id}/share-links/{tid}

# ---------------------------------------------------------------------------
# Snapshots / version history  (Week 3 milestone)
# ---------------------------------------------------------------------------
# TODO: GET  /docs/{id}/snapshots
# TODO: POST /docs/{id}/snapshots/{sid}/restore

# ---------------------------------------------------------------------------
# Comments  (Week 3 milestone)
# ---------------------------------------------------------------------------
# TODO: POST   /docs/{id}/comments
# TODO: PATCH  /docs/{id}/comments/{cid}
# TODO: DELETE /docs/{id}/comments/{cid}

# ---------------------------------------------------------------------------
# WebSocket sync endpoint  (Week 1-2 milestone)
# ---------------------------------------------------------------------------

@app.websocket("/ws/doc/{document_id}")
async def doc_ws(
    websocket: WebSocket,
    document_id: str,
    token: str = Query(default=None),
):
    """
    y-websocket compatible endpoint.

    Message types (client -> server):
      type=0  SYNC_STEP_1  (state vector)
      type=1  SYNC_STEP_2  (initial state)
      type=2  UPDATE       (incremental CRDT update) — persisted + broadcast
      type=3  AWARENESS    (cursor / presence)       — broadcast only

    Message types (server -> client):
      type=0  SYNC_STEP_1  (server state vector)
      type=1  SYNC_STEP_2  (server diff)
      type=2  UPDATE       (others' updates)
      type=3  AWARENESS    (others' presence)
    """
    # TODO: authenticate via token (JWT or share_token)
    # TODO: load document; check access via get_doc_with_access_check()
    # TODO: send initial state (snapshot bytes + recent incremental updates)

    await websocket.accept()

    if document_id not in local_connections:
        local_connections[document_id] = set()
        # TODO: start Redis pub/sub subscribe task for this doc
        # asyncio.create_task(subscribe_doc_channel(document_id))

    local_connections[document_id].add(websocket)

    try:
        while True:
            msg = await websocket.receive_bytes()
            msg_type = msg[0] if msg else None
            payload = msg[1:]

            if msg_type == 2:  # UPDATE
                # TODO: persist update to document_updates table
                # TODO: publish to Redis: "doc:{document_id}:updates"
                # Broadcast locally (cross-pod goes via Redis subscriber)
                for ws in list(local_connections.get(document_id, set())):
                    if ws is not websocket:
                        try:
                            await ws.send_bytes(msg)
                        except Exception:
                            pass

            elif msg_type == 3:  # AWARENESS
                # TODO: update Redis presence map with TTL 300s
                for ws in list(local_connections.get(document_id, set())):
                    if ws is not websocket:
                        try:
                            await ws.send_bytes(msg)
                        except Exception:
                            pass

    except WebSocketDisconnect:
        pass
    finally:
        local_connections.get(document_id, set()).discard(websocket)
        if not local_connections.get(document_id):
            local_connections.pop(document_id, None)
        # TODO: remove_presence(document_id, user)


# ---------------------------------------------------------------------------
# Celery tasks to wire up (in tasks.py)
# ---------------------------------------------------------------------------
# TODO: snapshot_doc(doc_id)       — merge all updates, upload to S3
# TODO: cleanup_stale_presence()   — periodic Redis cleanup
# Trigger snapshot after 500 updates or every 5 min of activity
