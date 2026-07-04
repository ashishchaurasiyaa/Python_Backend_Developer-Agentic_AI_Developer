"""
FastAPI app: serves the static frontend and a /api/chat endpoint.

Run with:  uvicorn backend.main:app --reload
Then open: http://127.0.0.1:8000
"""
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .config import settings
from .llm import generate_reply

app = FastAPI(title="Workspace Demo — AI Chat Assistant")

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"


class ChatRequest(BaseModel):
    message: str
    history: list[dict] = []


@app.get("/api/health")
async def health() -> dict:
    """Lightweight status check — also reports whether a key is configured."""
    return {"ok": True, "model": settings.model, "live": settings.has_api_key}


@app.post("/api/chat")
async def chat(req: ChatRequest) -> dict:
    """Take a user message + history, return Claude's reply."""
    reply = generate_reply(req.message, req.history)
    return {"reply": reply}


# Serve the frontend (index.html at "/") AFTER the API routes so /api/* wins.
app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
