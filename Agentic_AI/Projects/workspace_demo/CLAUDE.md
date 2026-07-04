# Workspace Demo — AI Chat Assistant

Project memory for Claude Code. Loaded automatically every session. Keep it
short (< 200 lines) — push step-by-step procedures into `.claude/skills/`.

## Overview
A tiny end-to-end web app that demonstrates how a Claude Code **workspace** is
laid out: a Python backend, a plain HTML/CSS/JS frontend, and a full `.claude/`
configuration layer (agents, skills, settings, MCP). Used as a teaching demo.

## Architecture
- `backend/`  — FastAPI app.
  - `main.py`   serves the frontend and the `/api/chat` + `/api/health` routes.
  - `llm.py`    wraps the Anthropic SDK; placeholder-safe when no key is set.
  - `config.py` loads env via python-dotenv; holds non-secret settings.
- `frontend/` — static `index.html` + `style.css` + `app.js` (no framework).
- Frontend calls `POST /api/chat` with `{ message, history }` → `{ reply }`.

## Tech stack
- Backend: Python 3.11+, FastAPI, Uvicorn, Anthropic SDK.
- Frontend: vanilla HTML / CSS / JavaScript (no build step).
- Model: `claude-opus-4-8` by default (override with `CLAUDE_MODEL`).

## Commands
- Install:  `pip install -r requirements.txt`
- Run:      `uvicorn backend.main:app --reload`  → http://127.0.0.1:8000
- Health:   `curl localhost:8000/api/health`

## Conventions
- 4-space indentation in Python; type hints on function signatures.
- Keep secrets in `.env` (gitignored). Never hardcode `ANTHROPIC_API_KEY`.
- The SDK reads `ANTHROPIC_API_KEY` from the environment — don't pass it explicitly.
- Read response text with `[b.text for b in resp.content if b.type == "text"]`.
- Frontend talks to the backend only through `/api/*` — no direct API calls.

## Capabilities available to Claude here
- Tools: file read/write, bash (run uvicorn, pip, curl), grep/glob.
- MCP servers (see `.mcp.json`): `filesystem`, `fetch`.
- Subagents (see `.claude/agents/`): `code-reviewer`, `api-tester`.
- Skills (see `.claude/skills/`): `add-endpoint`, `run-app`.

## Lessons learned
- Mount `StaticFiles` at "/" AFTER the `/api/*` routes, or it swallows them.
- Keep the app placeholder-safe so demos run without a key.
