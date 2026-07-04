"""Milestone 6 — FastAPI webhook handler + HMAC verification."""
import hashlib
import hmac
import os

from fastapi import FastAPI, Request, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse

from app.agent.graph import review_graph
from app.agent.state import ReviewState

app = FastAPI(title="Multi-Agent Code Review", version="1.0.0")


# ---------------------------------------------------------------------------
# HMAC verification
# ---------------------------------------------------------------------------

def _verify_github_signature(payload: bytes, signature_header: str | None) -> bool:
    secret = os.getenv("GITHUB_WEBHOOK_SECRET", "")
    if not secret or not signature_header:
        return False
    expected = "sha256=" + hmac.new(
        secret.encode(), payload, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature_header)


# ---------------------------------------------------------------------------
# Background task — run the review graph
# ---------------------------------------------------------------------------

async def _run_review(pr_id: int, repo: str, diff: str, files: list[str]):
    initial_state: ReviewState = {
        "pr_id": pr_id,
        "repo": repo,
        "diff": diff,
        "files_changed": files,
        "security_issues": [],
        "performance_issues": [],
        "style_issues": [],
        "decision": "approve",
        "review_comment": "",
        "cost_usd": 0.0,
    }
    config = {"configurable": {"thread_id": f"pr-{repo}-{pr_id}"}}
    await review_graph.ainvoke(initial_state, config=config)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/webhook/github")
async def github_webhook(request: Request, background_tasks: BackgroundTasks):
    payload = await request.body()
    sig = request.headers.get("X-Hub-Signature-256")

    if os.getenv("GITHUB_WEBHOOK_SECRET") and not _verify_github_signature(payload, sig):
        raise HTTPException(status_code=401, detail="Invalid signature")

    event = request.headers.get("X-GitHub-Event", "")
    if event != "pull_request":
        return JSONResponse({"skipped": True, "event": event})

    data = await request.json()
    action = data.get("action", "")
    if action not in ("opened", "synchronize", "reopened"):
        return JSONResponse({"skipped": True, "action": action})

    pr = data["pull_request"]
    pr_id = pr["number"]
    repo = data["repository"]["full_name"]

    # In production: fetch the real diff via GitHub API
    # For now, use the body as a stub diff
    diff = pr.get("body", "") or "# no diff provided"
    files = [f["filename"] for f in data.get("files", [])]

    background_tasks.add_task(_run_review, pr_id, repo, diff, files)
    return JSONResponse({"queued": True, "pr": pr_id, "repo": repo})
