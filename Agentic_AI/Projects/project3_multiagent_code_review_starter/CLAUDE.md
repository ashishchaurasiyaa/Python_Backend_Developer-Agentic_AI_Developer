# Multi-Agent Code Review System

## What this project is
A LangGraph supervisor that automatically reviews GitHub PRs using 3 specialist agents running in parallel, then posts inline comments back to GitHub.

## Architecture

```
GitHub Webhook (PR opened/updated)
         |
    FastAPI handler  (app/api/webhook.py)
         |
    LangGraph Supervisor  (app/agent/graph.py)
    /          |          \
Security     Perf         Style       ← parallel fan-out
(Opus)     (Sonnet)      (Haiku)
    \          |          /
         Synthesizer  (app/agent/nodes.py)
              |
    CRITICAL? ──yes──▶ Human-in-the-loop interrupt
              |no
       GitHub Review  (app/github_client.py)
              +
       Slack alert if CRITICAL  (mcp_server/slack_tool.py)
```

## Stack
- LangGraph >= 0.2 (StateGraph, interrupt_before)
- FastAPI + Uvicorn
- Anthropic SDK + Instructor (structured output)
- SQLAlchemy + asyncpg (LangGraph checkpointing)
- Celery + Redis (webhook task queue)
- FastMCP (Slack tool)
- httpx (GitHub API)

## File map
```
main.py                   ← skeleton entry point (run to smoke-test)
app/
  api/webhook.py          ← POST /webhook/github (Milestone 6)
  agent/
    state.py              ← ReviewState TypedDict + Pydantic models (Milestone 1)
    graph.py              ← LangGraph supervisor graph (Milestone 2)
    nodes.py              ← security / perf / style / synthesize nodes (Milestones 3-5)
  github_client.py        ← GitHub API — post inline PR comments (Milestone 7)
mcp_server/
  slack_tool.py           ← FastMCP Slack notifier (Milestone 8)
```

## Run commands
```bash
# Install
pip install -r requirements.txt

# Env (copy once, then fill in real values)
cp .env.example .env

# Run skeleton (no API key needed)
python main.py

# Run full app (needs all env vars)
uvicorn app.api.webhook:app --reload --port 8000
```

## Milestones
1. `state.py` — ReviewState + SecurityIssue / PerformanceIssue / StyleIssue models
2. `graph.py` — LangGraph parallel fan-out (security + perf + style → synthesize)
3. `nodes.py` — Security agent (Instructor + Opus, structured output)
4. `nodes.py` — Perf (Sonnet) + Style (Haiku) agents
5. `nodes.py` — Synthesizer + human-in-the-loop interrupt
6. `webhook.py` — FastAPI POST /webhook/github + HMAC verification
7. `github_client.py` — post inline review comments, block merge on CRITICAL
8. `slack_tool.py` — FastMCP tool for CRITICAL Slack alerts

## Models by agent
| Agent    | Model             | Why                                    |
|----------|-------------------|----------------------------------------|
| Security | claude-opus-4-8   | Never miss a critical vulnerability    |
| Perf     | claude-sonnet-4-6 | Balanced — N+1, missing index, sync    |
| Style    | claude-haiku-4-5  | Cheapest — PEP8, type hints, naming    |

## Conventions
- All agents return **Pydantic models via Instructor** (never raw strings)
- LangGraph state: always TypedDict, all list fields default to `[]`
- Secrets: only in `.env` — never hardcode; never commit `.env`
- Async everywhere — `async def` for all nodes and API handlers
- Cost field (`cost_usd: float`) accumulates across all nodes in ReviewState
