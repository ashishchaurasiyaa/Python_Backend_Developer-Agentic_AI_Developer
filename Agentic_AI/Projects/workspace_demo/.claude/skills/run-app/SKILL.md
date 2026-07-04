---
name: Run the app
description: Install dependencies, start the FastAPI backend, and open the chat UI. Use when asked to run, start, launch, or preview the app.
allowed-tools: Bash(pip install:*) Bash(uvicorn:*) Bash(python:*)
---

# Run the app

1. Install dependencies (first time only):
   ```bash
   pip install -r requirements.txt
   ```
2. Start the server with autoreload:
   ```bash
   uvicorn backend.main:app --reload
   ```
3. Open http://127.0.0.1:8000 in a browser.

Without `ANTHROPIC_API_KEY` set, the app runs in **demo mode** (it echoes your
message). Add the key to `.env` and restart to chat with Claude for real.

A one-shot launcher is bundled at `scripts/start.sh`:
```bash
bash .claude/skills/run-app/scripts/start.sh
```
