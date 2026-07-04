---
name: run-app
description: Use this skill to install dependencies and run this project. Handles virtual environment, .env setup, and launches the server or skeleton.
---

# Run the App

## Steps

1. **Virtual environment**
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Environment variables**
   - Check if `.env` exists: `ls .env`
   - If not: `cp .env.example .env` then tell user to fill in real values

4. **Run**
   - Skeleton (no API key needed):
     ```bash
     python main.py
     ```
   - Full app (needs ANTHROPIC_API_KEY + GITHUB_TOKEN + GITHUB_WEBHOOK_SECRET):
     ```bash
     uvicorn app.api.webhook:app --reload --port 8000
     ```

5. **Health check** (if running full app):
   ```bash
   curl http://127.0.0.1:8000/health
   ```

See `scripts/start.sh` for a one-command launcher.
