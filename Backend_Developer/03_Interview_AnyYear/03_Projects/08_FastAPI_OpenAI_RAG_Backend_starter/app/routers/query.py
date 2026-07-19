"""
RAG query endpoints (stubs — implemented Week 2).

`/query`        — non-streaming, returns answer + citations
`/query/stream` — SSE token-by-token, then a final citations event
"""

import json
from collections.abc import AsyncGenerator

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.config import get_settings

router = APIRouter(tags=["query"])


class QueryRequest(BaseModel):
    question: str
    session_id: str | None = None
    model: str | None = None  # defaults to settings.llm_model when None
    top_k: int = 5


@router.post("/query")
async def query(req: QueryRequest):
    """
    Non-streaming RAG query. Pipeline (Week 2):
      1. check semantic cache (cosine >= 0.97) -> return cached
      2. embed question (settings.embedding_model)
      3. hybrid_search(tenant_id, embedding, question, top_k):
         pgvector cosine + BM25 tsvector -> RRF merge -> Cohere rerank
      4. build grounded prompt (context + "cite sources") -> LLM
      5. persist message + cost (tokens_in/out), save to semantic cache
    """
    settings = get_settings()
    return {
        "answer": "TODO: RAG pipeline lands Week 2",
        "citations": [],
        "session_id": req.session_id,
        "model": req.model or settings.llm_model,
    }


@router.post("/query/stream")
async def query_stream(req: QueryRequest):
    """Streaming SSE RAG query. Yields tokens, then citations, then [DONE]."""

    async def _generate() -> AsyncGenerator[str, None]:
        # TODO(Week 2): retrieval pipeline (same as /query), then
        # stream tokens from the LLM and emit a final citations event.
        yield f"data: {json.dumps({'token': 'TODO'})}\n\n"
        yield f"data: {json.dumps({'type': 'citations', 'sources': []})}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        _generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
