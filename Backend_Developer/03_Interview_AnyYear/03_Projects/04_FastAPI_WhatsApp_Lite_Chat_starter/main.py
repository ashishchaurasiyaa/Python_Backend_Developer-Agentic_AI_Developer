"""
WhatsApp-Lite Chat Backend — skeleton entry point.
Spec: ../04_FastAPI_WhatsApp_Lite_Chat.md

Run:
    uvicorn main:app --reload
"""

import asyncio
import json
import time
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

app = FastAPI(title="WhatsApp-Lite Chat Backend", version="0.1.0")

# Gateway node ID (set per pod via env in production).
GATEWAY_NODE_ID = "node-1"

# local_connections: user_id -> {device_id -> WebSocket}
local_connections: dict[str, dict[str, WebSocket]] = {}


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

@app.get("/health")
async def health():
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Auth (phone OTP)  (Week 1 milestone)
# ---------------------------------------------------------------------------
# TODO: POST /auth/send-otp     { phone_number }
# TODO: POST /auth/verify-otp   { phone_number, otp } -> { access, refresh }
# TODO: POST /auth/refresh       { refresh_token }

@app.post("/auth/send-otp")
async def send_otp(body: dict):
    # TODO: validate phone_number format
    # TODO: generate 6-digit OTP, store in Redis with TTL 300s
    # TODO: send via SMS gateway (e.g., Twilio / MSG91)
    return {"detail": "TODO: OTP sending not implemented"}


@app.post("/auth/verify-otp")
async def verify_otp(body: dict):
    # TODO: compare OTP from Redis
    # TODO: create or fetch user record
    # TODO: issue JWT access + refresh tokens
    return {"detail": "TODO: OTP verification not implemented"}


# ---------------------------------------------------------------------------
# WebSocket gateway  (Week 2 milestone)
# ---------------------------------------------------------------------------

@app.websocket("/ws")
async def ws_endpoint(websocket: WebSocket, token: str = Query(...)):
    """
    Per-device WebSocket connection.

    Inbound JSON message types (client -> server):
      {"type": "message", "chat_id": "...", "content": "...", "msg_type": "text"}
      {"type": "typing",  "chat_id": "..."}
      {"type": "read",    "chat_id": "...", "msg_ids": [...]}

    Outbound JSON message types (server -> client):
      {"type": "new_message", ...}
      {"type": "typing",       "chat_id": ..., "user_id": ...}
      {"type": "read_receipt", "chat_id": ..., "reader_id": ..., "msg_ids": [...]}
      {"type": "presence",     "user_id": ..., "status": "online"|"offline"}
    """
    # TODO: verify_jwt(token) — 401 close on failure
    # TODO: assign device_id
    await websocket.accept()

    user_id = "placeholder-user-id"  # TODO: from JWT
    device_id = f"device-{int(time.time())}"  # TODO: stable device ID

    # Register connection locally and in Redis
    local_connections.setdefault(user_id, {})[device_id] = websocket
    # TODO: redis.hset(f"user_conns:{user_id}", device_id, GATEWAY_NODE_ID)
    # TODO: redis.expire(f"user_conns:{user_id}", 86400)

    # TODO: subscribe_user_channel(user_id, device_id) as background task
    # TODO: deliver_pending(user, device_id, websocket)
    # TODO: on_connect(user_id) — update presence, notify contacts

    try:
        while True:
            msg = await websocket.receive_json()
            await handle_client_message(user_id, device_id, msg)
    except WebSocketDisconnect:
        pass
    finally:
        local_connections.get(user_id, {}).pop(device_id, None)
        if not local_connections.get(user_id):
            local_connections.pop(user_id, None)
        # TODO: redis.hdel(f"user_conns:{user_id}", device_id)
        # TODO: on_disconnect(user_id)


async def handle_client_message(user_id: str, device_id: str, msg: dict) -> None:
    msg_type = msg.get("type")

    if msg_type == "message":
        # TODO: validate sender is in chat
        # TODO: generate Snowflake message ID
        # TODO: publish to Kafka topic "chat_events" (key=chat_id for ordering)
        # TODO: return ack with msg_id immediately
        pass

    elif msg_type == "typing":
        # TODO: set Redis key typing:{chat_id}:{user_id} with TTL 5s
        # TODO: broadcast typing event to other chat members
        pass

    elif msg_type == "read":
        # TODO: INSERT into Cassandra message_read_status
        # TODO: UPDATE chat_members.last_read_msg_id
        # TODO: deliver read_receipt to senders
        pass


# ---------------------------------------------------------------------------
# REST API  (Week 1-4 milestones)
# ---------------------------------------------------------------------------

@app.get("/chats")
async def list_chats():
    # TODO: auth, return list of chats with last message preview
    return {"items": [], "detail": "TODO"}


@app.post("/chats")
async def create_chat(body: dict):
    # TODO: create 1:1 or group chat (type, members)
    return {"detail": "TODO"}


@app.get("/chats/{chat_id}/messages")
async def get_messages(chat_id: str, before: int = None, limit: int = 50):
    # TODO: SELECT from Cassandra messages_by_chat WHERE chat_id = ? AND msg_id < before LIMIT limit
    return {"items": [], "detail": "TODO"}


@app.post("/chats/{chat_id}/messages")
async def send_message_rest(chat_id: str, body: dict):
    # TODO: same as WS path but via REST (useful for bots / integrations)
    return {"detail": "TODO"}


@app.post("/media/upload-init")
async def media_upload_init(body: dict):
    """Return a presigned S3 PUT URL so the client uploads directly."""
    # TODO: validate filename, size, mime_type
    # TODO: generate media_id
    # TODO: return { media_id, upload_url, expires_in }
    return {"detail": "TODO: presigned URL generation not implemented"}


# ---------------------------------------------------------------------------
# Celery / Kafka workers to implement (separate workers/)
# ---------------------------------------------------------------------------
# TODO: persistence_worker  — Kafka consumer, writes to Cassandra
# TODO: fanout_worker       — reads from persisted_messages, delivers to all devices
# TODO: push_worker         — FCM/APNs for offline users, with batch debounce (5s)
