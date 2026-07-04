# Workspace Demo — AI Chat Assistant

A tiny end-to-end app that shows how a **Claude Code workspace** is structured:
a Python backend + plain HTML/CSS/JS frontend, wrapped in a complete `.claude/`
configuration layer (agents, skills, settings, MCP).

Built as a teaching demo for the **Workspace** topic. For the full walkthrough
of every file and "how do I add X", read **[WORKSPACE_GUIDE.md](WORKSPACE_GUIDE.md)**.

## Quick start

```bash
# 1. (optional) create a virtualenv
python3 -m venv .venv && source .venv/bin/activate

# 2. install deps
pip install -r requirements.txt

# 3. (optional) add your key — without it, the app runs in demo mode
cp .env.example .env        # then edit .env and paste your ANTHROPIC_API_KEY

# 4. run
uvicorn backend.main:app --reload
```

Open **http://127.0.0.1:8000** and chat.

## Folder structure

```
workspace_demo/
├── .claude/                  # ← the Claude Code config layer (committed)
│   ├── settings.json         #   permissions, env (shared with the team)
│   ├── settings.local.json.example  # template for personal overrides (gitignored)
│   ├── agents/               #   subagents — one .md per agent
│   │   ├── code-reviewer.md
│   │   └── api-tester.md
│   ├── skills/               #   reusable workflows — a folder per skill
│   │   ├── add-endpoint/SKILL.md
│   │   └── run-app/SKILL.md (+ scripts/)
│   └── commands/             #   slash commands
│       └── ship-check.md
├── backend/                  # FastAPI app (Python)
│   ├── main.py · llm.py · config.py
├── frontend/                 # vanilla HTML / CSS / JS
│   ├── index.html · style.css · app.js
├── CLAUDE.md                 # project memory, loaded every session
├── .mcp.json                 # MCP servers for this project
├── .gitignore                # what stays out of git (incl. .env, local settings)
├── .env.example              # env template (copy to .env)
└── requirements.txt
```

## Tech stack
- **Backend:** Python, FastAPI, Uvicorn, Anthropic SDK
- **Frontend:** HTML + CSS + JavaScript (no framework, no build step)
- **Model:** `claude-opus-4-8` (override via `CLAUDE_MODEL` in `.env`)
