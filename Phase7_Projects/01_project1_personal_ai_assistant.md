# Project 1: Personal AI Assistant with MCP

## Overview
Main flagship project — covers the entire stack end-to-end.
**Stack:** FastAPI + LangGraph + MCP + RAG + React + Docker + AWS EC2

---

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                  React Frontend                      │
│         (Streaming SSE, Chat UI, File Upload)        │
└────────────────────────┬────────────────────────────┘
                         │ HTTP/SSE
┌────────────────────────▼────────────────────────────┐
│              FastAPI Backend                         │
│   /chat (SSE)  /upload  /conversations  /health     │
└──────────┬──────────────────────────────────────────┘
           │
┌──────────▼──────────┐    ┌──────────────────────┐
│   LangGraph Agent    │    │   MCP Tools Server   │
│                     │◄──►│                      │
│  StateGraph:        │    │  - file_system tool  │
│  → route_intent     │    │  - web_search tool   │
│  → search_docs      │    │  - database tool     │
│  → web_search       │    │  - calendar tool     │
│  → generate         │    └──────────────────────┘
└─────────┬───────────┘
          │
┌─────────▼───────────────────────────────────────────┐
│  Data Layer                                          │
│  PostgreSQL (pgvector) │ Redis (sessions, cache)    │
└─────────────────────────────────────────────────────┘
```

---

## Project Structure

```
personal-ai-assistant/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI app, lifespan
│   │   ├── api/
│   │   │   ├── chat.py          # SSE streaming endpoint
│   │   │   ├── documents.py     # File upload + indexing
│   │   │   └── conversations.py # History management
│   │   ├── agent/
│   │   │   ├── graph.py         # LangGraph StateGraph
│   │   │   ├── nodes.py         # Agent nodes
│   │   │   ├── state.py         # TypedDict state
│   │   │   └── tools.py         # Tool definitions
│   │   ├── mcp/
│   │   │   └── server.py        # FastMCP server
│   │   ├── rag/
│   │   │   ├── ingestor.py      # Document ingestion
│   │   │   ├── retriever.py     # Hybrid search
│   │   │   └── chunker.py       # Chunking strategies
│   │   └── db/
│   │       ├── models.py        # SQLAlchemy models
│   │       └── session.py       # Async session factory
│   ├── tests/
│   ├── alembic/
│   ├── Dockerfile
│   └── pyproject.toml
├── mcp-server/
│   ├── server.py                # Standalone MCP server
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── App.tsx
│   │   ├── components/
│   │   │   ├── ChatWindow.tsx
│   │   │   ├── MessageBubble.tsx
│   │   │   └── FileUpload.tsx
│   │   └── hooks/
│   │       └── useSSE.ts
│   └── package.json
├── docker-compose.yml
├── .github/workflows/
│   └── deploy.yml
└── README.md
```

---

## Core Implementation

### 1. Agent State + Graph

```python
# backend/app/agent/state.py
from typing import TypedDict, Annotated
from langchain_core.messages import BaseMessage
import operator

class AssistantState(TypedDict):
    messages: Annotated[list[BaseMessage], operator.add]
    user_id: str
    intent: str                    # "search_docs", "web_search", "general"
    retrieved_docs: list[dict]
    tool_results: list[dict]
    final_answer: str
```

```python
# backend/app/agent/graph.py
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langchain_anthropic import ChatAnthropic
from .state import AssistantState
from .nodes import route_intent, search_documents, web_search, generate_response

async def build_graph(db_pool) -> any:
    checkpointer = AsyncPostgresSaver(db_pool)
    await checkpointer.setup()

    llm = ChatAnthropic(model="claude-sonnet-4-6")

    graph = StateGraph(AssistantState)

    graph.add_node("route_intent", route_intent)
    graph.add_node("search_documents", search_documents)
    graph.add_node("web_search", web_search)
    graph.add_node("generate", generate_response)

    graph.set_entry_point("route_intent")

    graph.add_conditional_edges(
        "route_intent",
        lambda state: state["intent"],
        {
            "search_docs": "search_documents",
            "web_search": "web_search",
            "general": "generate",
        }
    )

    graph.add_edge("search_documents", "generate")
    graph.add_edge("web_search", "generate")
    graph.add_edge("generate", END)

    return graph.compile(checkpointer=checkpointer)
```

### 2. Streaming Chat Endpoint

```python
# backend/app/api/chat.py
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from langchain_core.messages import HumanMessage
import json, asyncio

router = APIRouter()

@router.post("/chat")
async def chat_stream(
    request: ChatRequest,
    graph = Depends(get_agent_graph),
    db = Depends(get_db_session),
):
    async def generate():
        config = {
            "configurable": {
                "thread_id": request.conversation_id,
                "user_id": request.user_id,
            }
        }

        async for event in graph.astream_events(
            {"messages": [HumanMessage(content=request.message)]},
            config=config,
            version="v2",
        ):
            if event["event"] == "on_chat_model_stream":
                chunk = event["data"]["chunk"]
                if chunk.content:
                    yield f"data: {json.dumps({'type': 'token', 'content': chunk.content})}\n\n"

            elif event["event"] == "on_chain_end" and event["name"] == "generate":
                yield f"data: {json.dumps({'type': 'done'})}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        }
    )
```

### 3. MCP Server

```python
# mcp-server/server.py
from fastmcp import FastMCP
from tavily import TavilyClient
import httpx, os

mcp = FastMCP("personal-assistant-tools")
tavily = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))

@mcp.tool()
async def web_search(query: str, max_results: int = 5) -> dict:
    """Search the web for current information."""
    result = tavily.search(query, max_results=max_results, include_answer=True)
    return {"answer": result.get("answer", ""), "sources": result.get("results", [])}

@mcp.tool()
async def read_file(file_path: str) -> str:
    """Read content from a local file."""
    allowed_dirs = ["/home/user/documents", "/tmp/uploads"]
    if not any(file_path.startswith(d) for d in allowed_dirs):
        return "Error: Access denied — path not in allowed directories"
    with open(file_path) as f:
        return f.read()

@mcp.tool()
async def query_database(sql: str) -> list[dict]:
    """
    Run a read-only SQL query against the user's data.
    Only SELECT statements allowed.
    """
    if not sql.strip().upper().startswith("SELECT"):
        return [{"error": "Only SELECT queries allowed"}]
    # Execute against DB...
    return []

if __name__ == "__main__":
    mcp.run(transport="stdio")
```

### 4. RAG Ingestion

```python
# backend/app/rag/ingestor.py
from langchain_community.document_loaders import PyPDFLoader, UnstructuredWordDocumentLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
from sqlalchemy.ext.asyncio import AsyncSession
import numpy as np

async def ingest_document(
    file_path: str,
    user_id: str,
    db: AsyncSession,
) -> int:
    """Ingest document into vector store. Returns chunk count."""

    # Load
    if file_path.endswith(".pdf"):
        loader = PyPDFLoader(file_path)
    else:
        loader = UnstructuredWordDocumentLoader(file_path)
    docs = loader.load()

    # Chunk
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    chunks = splitter.split_documents(docs)

    # Embed
    embedder = OpenAIEmbeddings(model="text-embedding-3-small")
    texts = [c.page_content for c in chunks]
    embeddings = await embedder.aembed_documents(texts)

    # Store in pgvector
    for chunk, embedding in zip(chunks, embeddings):
        await db.execute(
            """INSERT INTO document_chunks (user_id, content, embedding, metadata)
               VALUES (:user_id, :content, :embedding, :metadata)""",
            {
                "user_id": user_id,
                "content": chunk.page_content,
                "embedding": embedding,
                "metadata": chunk.metadata,
            }
        )
    await db.commit()
    return len(chunks)
```

### 5. Docker Compose

```yaml
# docker-compose.yml
version: "3.9"

services:
  backend:
    build: ./backend
    ports:
      - "8000:8000"
    env_file: .env
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy

  mcp-server:
    build: ./mcp-server
    env_file: .env

  frontend:
    build: ./frontend
    ports:
      - "3000:80"

  postgres:
    image: pgvector/pgvector:pg16
    environment:
      POSTGRES_DB: assistant_db
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD", "pg_isready", "-U", "postgres"]
      interval: 10s

  redis:
    image: redis:7-alpine
    command: redis-server --requirepass ${REDIS_PASSWORD}
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s

  prometheus:
    image: prom/prometheus
    ports:
      - "9090:9090"
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml

  grafana:
    image: grafana/grafana
    ports:
      - "3001:3000"

volumes:
  pgdata:
```

---

## Database Schema

```sql
-- Documents table
CREATE TABLE documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    filename VARCHAR(255) NOT NULL,
    file_type VARCHAR(50),
    uploaded_at TIMESTAMPTZ DEFAULT NOW()
);

-- Document chunks with vectors
CREATE TABLE document_chunks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    document_id UUID REFERENCES documents(id),
    content TEXT NOT NULL,
    embedding vector(1536),            -- pgvector
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- HNSW index for fast similarity search
CREATE INDEX ON document_chunks USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);

-- Conversation history (LangGraph checkpoints)
-- Auto-managed by LangGraph AsyncPostgresSaver

-- Usage tracking
CREATE TABLE usage_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    conversation_id VARCHAR(255),
    prompt_tokens INT,
    completion_tokens INT,
    cost_usd DECIMAL(10, 6),
    model VARCHAR(100),
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

---

## GitHub Actions Deploy

```yaml
# .github/workflows/deploy.yml
name: Deploy to EC2

on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    environment: production

    steps:
      - uses: actions/checkout@v4

      - name: Run tests
        run: |
          pip install uv && uv sync --group dev
          uv run pytest tests/ -x

      - name: Build and push to ECR
        env:
          AWS_ACCESS_KEY_ID: ${{ secrets.AWS_ACCESS_KEY_ID }}
          AWS_SECRET_ACCESS_KEY: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
        run: |
          aws ecr get-login-password --region us-east-1 | \
            docker login --username AWS --password-stdin ${{ secrets.ECR_REGISTRY }}
          docker compose build
          docker compose push

      - name: Deploy to EC2
        uses: appleboy/ssh-action@v1
        with:
          host: ${{ secrets.EC2_HOST }}
          username: ubuntu
          key: ${{ secrets.EC2_PRIVATE_KEY }}
          script: |
            cd ~/personal-ai-assistant
            git pull
            docker compose pull
            docker compose up -d --force-recreate
            sleep 15
            curl -f http://localhost:8000/health || exit 1
```

---

## Interview Talking Points

```
THIS PROJECT DEMONSTRATES:
  ✓ Full-stack: FastAPI + React + Docker + AWS
  ✓ Agentic AI: LangGraph with conditional routing
  ✓ RAG: Document ingestion + hybrid search + pgvector
  ✓ MCP: Custom tools server (file, web, DB)
  ✓ Production: SSE streaming, auth, monitoring
  ✓ DevOps: GitHub Actions → EC2 auto-deploy

SYSTEM DESIGN DECISIONS:
  - LangGraph checkpointing → multi-turn conversation memory
  - SSE instead of WebSocket → simpler, works with load balancers
  - pgvector inside PostgreSQL → no extra infra for MVP
  - MCP separate service → tools can be reused by other agents
  - Redis for sessions → horizontal scaling of FastAPI pods

TRADEOFFS DISCUSSED:
  - pgvector vs Qdrant: chose pgvector (simpler, existing DB)
  - WebSocket vs SSE: chose SSE (simpler, HTTP/2 compatible)
  - Monolith vs microservices: started modular monolith
```
