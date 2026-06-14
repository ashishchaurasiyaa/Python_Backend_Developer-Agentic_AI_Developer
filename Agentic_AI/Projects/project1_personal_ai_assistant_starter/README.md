# Project 1 Starter — Personal AI Assistant with MCP

Spec file: [../01_project1_personal_ai_assistant.md](../01_project1_personal_ai_assistant.md)

## How to Run

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Set env vars (optional — runs in placeholder mode without them)
export ANTHROPIC_API_KEY=sk-ant-...
export POSTGRES_URL=postgresql+asyncpg://...
export REDIS_URL=redis://localhost:6379

# 3. Run the skeleton
python main.py
```

## Milestones

| # | Milestone | Key Files |
|---|-----------|-----------|
| 1 | LangGraph state + graph scaffold | `app/agent/state.py`, `app/agent/graph.py` |
| 2 | FastAPI streaming (SSE) `/chat` endpoint | `app/api/chat.py` |
| 3 | MCP tools server (file, web_search, DB) | `mcp_server/server.py` |
| 4 | RAG ingestion + pgvector retriever | `app/rag/ingestor.py`, `app/rag/retriever.py` |
| 5 | React frontend with SSE hook | `frontend/src/hooks/useSSE.ts` |
| 6 | Docker Compose (postgres+pgvector, redis, backend, mcp) | `docker-compose.yml` |
| 7 | GitHub Actions CI/CD → EC2 deploy | `.github/workflows/deploy.yml` |

## Stack

FastAPI + LangGraph + MCP (FastMCP) + RAG + pgvector + Redis + React + Docker + AWS EC2
