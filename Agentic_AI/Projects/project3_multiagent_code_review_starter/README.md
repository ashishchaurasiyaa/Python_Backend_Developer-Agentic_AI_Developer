# Project 3 Starter — Multi-Agent Code Review System

Spec file: [../03_project3_multiagent_code_review.md](../03_project3_multiagent_code_review.md)

## How to Run

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Set env vars (optional — runs in placeholder mode without them)
export ANTHROPIC_API_KEY=sk-ant-...
export GITHUB_TOKEN=ghp_...
export GITHUB_WEBHOOK_SECRET=...
export SLACK_WEBHOOK_URL=https://hooks.slack.com/...

# 3. Run the skeleton
python main.py
```

## Milestones

| # | Milestone | Key Files |
|---|-----------|-----------|
| 1 | ReviewState TypedDict + Pydantic issue models | `app/agent/state.py` |
| 2 | LangGraph supervisor: parallel Security+Perf+Style fan-out | `app/agent/graph.py` |
| 3 | Security agent (Instructor + Anthropic, structured output) | `app/agent/nodes.py` |
| 4 | Performance + Style agents (Sonnet + Haiku) | `app/agent/nodes.py` |
| 5 | Synthesizer + human-in-the-loop interrupt | `app/agent/nodes.py` |
| 6 | GitHub webhook handler + HMAC verification | `app/api/webhook.py` |
| 7 | GitHub API: post inline PR comments + block merge | `app/github_client.py` |
| 8 | Slack MCP tool for CRITICAL alerts | `mcp_server/slack_tool.py` |

## Stack

LangGraph Supervisor + FastAPI + GitHub Webhooks + MCP + Instructor + Anthropic (Opus/Sonnet/Haiku)
