"""
Real-Time AI Chat App (ChatGPT-style) — skeleton entry point.
Spec: ../09_Realtime_AI_Chat_App.md

Run:
    uvicorn main:app --reload
"""

import asyncio
import json
import uuid
from typing import AsyncGenerator
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

app = FastAPI(title="Real-Time AI Chat App", version="0.1.0")

# In-memory per-pod state.  Cross-pod sync via Redis pub/sub.
# user_id -> set[WebSocket]
_connections: dict[str, set[WebSocket]] = {}

# message_id -> asyncio.Event  (for stop-generation support)
_active_streams: dict[str, asyncio.Event] = {}


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

@app.get("/health")
async def health():
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Auth  (Phase 1 milestone)
# ---------------------------------------------------------------------------
# TODO: POST /auth/signup  { email, password }
# TODO: POST /auth/login   { email, password } -> { access_token, refresh_token }
# TODO: POST /auth/google  (OAuth callback)
# TODO: POST /auth/refresh { refresh_token }

@app.post("/auth/signup")
async def signup(body: dict):
    # TODO: hash password (bcrypt), insert user, send verification email
    return {"detail": "TODO"}


@app.post("/auth/login")
async def login(body: dict):
    # TODO: verify credentials, issue JWT
    return {"detail": "TODO"}


# ---------------------------------------------------------------------------
# Conversation REST  (Phase 1 milestone)
# ---------------------------------------------------------------------------

@app.post("/conversations")
async def create_conversation(body: dict):
    # TODO: auth, insert conversation (owner_user_id, title, model_default)
    return {"conversation_id": str(uuid.uuid4()), "detail": "TODO"}


@app.get("/conversations")
async def list_conversations():
    # TODO: list conversations for current user, ordered by updated_at DESC
    return {"items": [], "detail": "TODO"}


@app.get("/conversations/{conv_id}/messages")
async def get_messages(conv_id: str, limit: int = 50, before: str = None):
    # TODO: paginate messages; respect is_active_branch for branching
    return {"items": [], "detail": "TODO"}


# ---------------------------------------------------------------------------
# WebSocket (Phase 2 milestone)
# ---------------------------------------------------------------------------

@app.websocket("/ws/chat")
async def chat_ws(websocket: WebSocket, token: str = Query(...)):
    """
    Bidirectional WebSocket for real-time AI chat.

    Inbound JSON events:
      {"type": "send_message", "conversation_id": "...", "content": "..."}
      {"type": "stop",          "message_id": "..."}
      {"type": "ping"}

    Outbound JSON events:
      {"type": "message_added",  "message_id": "...", "role": "user", "content": "..."}
      {"type": "token",           "message_id": "...", "delta": "..."}
      {"type": "complete",        "message_id": "..."}
      {"type": "error",           "message_id": "...", "detail": "..."}
      {"type": "pong"}
    """
    # TODO: authenticate via token (JWT); 4001 close on failure
    user_id = "placeholder"  # TODO: from JWT

    await websocket.accept()
    _connections.setdefault(user_id, set()).add(websocket)

    # TODO: redis.set(f"online:{user_id}", "1", ex=60)
    # TODO: drain pending messages from Redis queue for this user

    try:
        while True:
            data = await websocket.receive_json()

            if data.get("type") == "send_message":
                await _handle_send_message(user_id, data)

            elif data.get("type") == "stop":
                msg_id = data.get("message_id", "")
                if msg_id in _active_streams:
                    _active_streams[msg_id].set()

            elif data.get("type") == "ping":
                await websocket.send_json({"type": "pong"})

    except WebSocketDisconnect:
        pass
    finally:
        _connections.get(user_id, set()).discard(websocket)
        if not _connections.get(user_id):
            _connections.pop(user_id, None)


async def _broadcast_to_user(user_id: str, message: dict) -> None:
    """Send to all of this user's local WebSocket connections."""
    for ws in list(_connections.get(user_id, set())):
        try:
            await ws.send_json(message)
        except Exception:
            _connections.get(user_id, set()).discard(ws)
    # TODO: also publish to Redis pub/sub channel "user:{user_id}" for other pods


async def _handle_send_message(user_id: str, data: dict) -> None:
    conv_id = data.get("conversation_id")
    content = data.get("content", "")

    # TODO: validate user owns / is member of conversation
    # TODO: save user message to DB
    user_msg_id = str(uuid.uuid4())
    await _broadcast_to_user(user_id, {
        "type": "message_added",
        "message_id": user_msg_id,
        "role": "user",
        "content": content,
    })

    # Begin AI response stream
    asst_msg_id = str(uuid.uuid4())
    stop_event = asyncio.Event()
    _active_streams[asst_msg_id] = stop_event

    asyncio.create_task(_stream_llm(user_id, conv_id, asst_msg_id, content, stop_event))


async def _stream_llm(
    user_id: str,
    conv_id: str,
    msg_id: str,
    prompt: str,
    stop_event: asyncio.Event,
) -> None:
    """Stream tokens from LLM to user's WebSocket connections."""
    try:
        # TODO: import anthropic; load conversation history from DB
        # TODO: async with anthropic.messages.stream(...) as stream:
        #           async for token in stream.text_stream:
        #               if stop_event.is_set(): break
        #               await _broadcast_to_user(user_id, {"type": "token", "message_id": msg_id, "delta": token})
        # TODO: save complete assistant message to DB
        # TODO: track tokens_in, tokens_out, cost_usd

        # Placeholder token stream
        for token in ["TODO", " —", " LLM", " stream", " not", " implemented"]:
            if stop_event.is_set():
                break
            await _broadcast_to_user(user_id, {"type": "token", "message_id": msg_id, "delta": token})
            await asyncio.sleep(0.05)

        await _broadcast_to_user(user_id, {"type": "complete", "message_id": msg_id})
    except Exception as exc:
        await _broadcast_to_user(user_id, {"type": "error", "message_id": msg_id, "detail": str(exc)})
    finally:
        _active_streams.pop(msg_id, None)


# ---------------------------------------------------------------------------
# Conversation sharing  (Phase 4 milestone)
# ---------------------------------------------------------------------------
# TODO: POST /conversations/{id}/share   — generate share_token
# TODO: GET  /share/{token}              — read-only public view

# ---------------------------------------------------------------------------
# Collaboration  (Phase 4 milestone)
# ---------------------------------------------------------------------------
# TODO: POST /conversations/{id}/members { user_id, role }
# TODO: Presence indicators via Redis SET online:{user_id} with heartbeat

# ---------------------------------------------------------------------------
# Stripe billing  (Phase 5 milestone)
# ---------------------------------------------------------------------------
# TODO: GET  /billing/tier
# TODO: POST /billing/subscribe { price_id }
# TODO: POST /billing/webhook   (Stripe events)
