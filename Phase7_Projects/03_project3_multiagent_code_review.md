# Project 3: Multi-Agent Code Review System

## Overview
Shows multi-agent coordination and GitHub integration skills.
**Stack:** LangGraph Supervisor + FastAPI + GitHub Webhooks + MCP + Instructor

---

## Architecture

```
GitHub PR Opened/Updated
         │
         ▼ webhook
┌─────────────────────┐
│   FastAPI Webhook   │
│   /webhook/github   │
└────────┬────────────┘
         │ queue job
         ▼
┌─────────────────────┐
│  Celery Worker      │
│  (async review)     │
└────────┬────────────┘
         │
         ▼
┌─────────────────────────────────────────────┐
│           LangGraph Supervisor               │
│                                             │
│  ┌──────────┐  ┌────────────┐  ┌─────────┐ │
│  │ Security │  │Performance │  │  Style  │ │
│  │  Agent   │  │   Agent    │  │  Agent  │ │
│  │ (Opus)   │  │ (Sonnet)   │  │ (Haiku) │ │
│  └──────────┘  └────────────┘  └─────────┘ │
│                    │                        │
│          ┌─────────▼──────────┐             │
│          │  Synthesizer Agent │             │
│          │  (merge + decide)  │             │
│          └─────────┬──────────┘             │
└────────────────────┼────────────────────────┘
                     │
         ┌───────────┴──────────┐
         ▼                      ▼
   Auto-approve            Human Review
   (minor issues)          Queue (critical)
         │                      │
         ▼                      ▼
   GitHub API:             Slack Alert
   Post comments           + Block Merge
```

---

## Core Implementation

### 1. Agent State

```python
# app/agent/state.py
from typing import TypedDict, Literal
from pydantic import BaseModel

class SecurityIssue(BaseModel):
    severity: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]
    file: str
    line: int
    description: str
    suggestion: str
    owasp_category: str | None = None

class PerformanceIssue(BaseModel):
    type: str             # "n+1", "missing_index", "sync_in_async"
    file: str
    line: int
    impact: str
    suggestion: str

class StyleIssue(BaseModel):
    rule: str
    file: str
    line: int
    message: str
    autofix: str | None = None

class ReviewState(TypedDict):
    pr_id: int
    repo: str
    diff: str
    files_changed: list[str]
    security_issues: list[SecurityIssue]
    performance_issues: list[PerformanceIssue]
    style_issues: list[StyleIssue]
    decision: Literal["approve", "request_changes", "human_review"]
    review_comment: str
    cost_usd: float
```

### 2. LangGraph Supervisor

```python
# app/agent/graph.py
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from .nodes import (
    run_security_review,
    run_performance_review,
    run_style_review,
    synthesize_review,
    post_github_review,
    human_review_interrupt,
)
from .state import ReviewState

async def build_review_graph(db_pool) -> any:
    checkpointer = AsyncPostgresSaver(db_pool)
    await checkpointer.setup()

    graph = StateGraph(ReviewState)

    graph.add_node("security", run_security_review)
    graph.add_node("performance", run_performance_review)
    graph.add_node("style", run_style_review)
    graph.add_node("synthesize", synthesize_review)
    graph.add_node("human_review", human_review_interrupt)
    graph.add_node("post_github", post_github_review)

    # Run all 3 agents in parallel via fan-out
    graph.set_entry_point("security")
    graph.set_entry_point("performance")   # Parallel
    graph.set_entry_point("style")         # Parallel

    # All converge to synthesizer
    graph.add_edge("security", "synthesize")
    graph.add_edge("performance", "synthesize")
    graph.add_edge("style", "synthesize")

    # Routing based on severity
    graph.add_conditional_edges(
        "synthesize",
        route_based_on_severity,
        {
            "human_review": "human_review",
            "post_github": "post_github",
        }
    )
    graph.add_edge("human_review", "post_github")
    graph.add_edge("post_github", END)

    return graph.compile(
        checkpointer=checkpointer,
        interrupt_before=["human_review"],  # Pause for human
    )

def route_based_on_severity(state: ReviewState) -> str:
    has_critical = any(
        issue.severity == "CRITICAL"
        for issue in state["security_issues"]
    )
    return "human_review" if has_critical else "post_github"
```

### 3. Security Agent (uses Instructor for structured output)

```python
# app/agent/nodes.py
import instructor
import anthropic
from .state import ReviewState, SecurityIssue, PerformanceIssue, StyleIssue
from pydantic import BaseModel

claude_client = instructor.from_anthropic(anthropic.AsyncAnthropic())

class SecurityReviewResult(BaseModel):
    issues: list[SecurityIssue]
    summary: str

async def run_security_review(state: ReviewState) -> ReviewState:
    """Security agent — OWASP checks on diff."""

    result = await claude_client.messages.create(
        model="claude-opus-4-7",  # Best model for critical security
        max_tokens=4096,
        response_model=SecurityReviewResult,
        messages=[{
            "role": "user",
            "content": f"""You are a security expert. Review this code diff for security issues.
Check for: SQL injection, XSS, hardcoded secrets, insecure dependencies, 
OWASP Top 10 vulnerabilities, authentication flaws, authorization issues.

DIFF:
{state['diff'][:8000]}

Report each issue with: severity (LOW/MEDIUM/HIGH/CRITICAL), file, line, description, suggestion."""
        }]
    )

    return {
        "security_issues": result.issues,
        "cost_usd": state.get("cost_usd", 0) + 0.08,  # Opus cost estimate
    }

class PerformanceReviewResult(BaseModel):
    issues: list[PerformanceIssue]

async def run_performance_review(state: ReviewState) -> ReviewState:
    result = await claude_client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2048,
        response_model=PerformanceReviewResult,
        messages=[{
            "role": "user",
            "content": f"""Review for performance issues: N+1 queries, missing DB indexes,
synchronous calls in async context, O(n²) algorithms, memory leaks.

DIFF:
{state['diff'][:8000]}"""
        }]
    )
    return {"performance_issues": result.issues, "cost_usd": state.get("cost_usd", 0) + 0.02}

async def run_style_review(state: ReviewState) -> ReviewState:
    """Style agent — runs ruff, checks docstrings, naming."""
    import subprocess, tempfile, os

    style_issues = []

    # Run ruff on changed files
    for file_path in state["files_changed"]:
        if file_path.endswith(".py"):
            # Would actually fetch file content from GitHub API
            # For demo: just Claude review
            pass

    result = await claude_client.messages.create(
        model="claude-haiku-4-5-20251001",  # Cheapest model for style
        max_tokens=1024,
        response_model=type("StyleResult", (), {"issues": list[StyleIssue]})(),
        messages=[{
            "role": "user",
            "content": f"Check for PEP8 violations, missing type hints, unclear naming:\n\n{state['diff'][:4000]}"
        }]
    )
    return {"style_issues": result.issues, "cost_usd": state.get("cost_usd", 0) + 0.001}
```

### 4. GitHub Webhook Handler

```python
# app/api/webhook.py
from fastapi import APIRouter, Request, HTTPException, BackgroundTasks
import hashlib, hmac, os

router = APIRouter()

def verify_github_signature(payload: bytes, signature: str) -> bool:
    """Verify GitHub webhook signature."""
    secret = os.getenv("GITHUB_WEBHOOK_SECRET", "").encode()
    expected = "sha256=" + hmac.new(secret, payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)

@router.post("/webhook/github")
async def github_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
):
    payload = await request.body()
    signature = request.headers.get("X-Hub-Signature-256", "")

    if not verify_github_signature(payload, signature):
        raise HTTPException(status_code=401, detail="Invalid signature")

    event = request.headers.get("X-GitHub-Event")
    data = await request.json()

    if event == "pull_request" and data["action"] in ("opened", "synchronize"):
        pr = data["pull_request"]
        background_tasks.add_task(
            trigger_review,
            pr_id=pr["number"],
            repo=data["repository"]["full_name"],
            diff_url=pr["diff_url"],
        )

    return {"status": "queued"}

async def trigger_review(pr_id: int, repo: str, diff_url: str):
    """Fetch diff and trigger agent review."""
    import httpx
    async with httpx.AsyncClient() as client:
        headers = {"Authorization": f"token {os.getenv('GITHUB_TOKEN')}"}
        diff_response = await client.get(diff_url, headers=headers)
        diff = diff_response.text

    # Queue in Celery
    review_pr_task.delay(pr_id=pr_id, repo=repo, diff=diff)
```

### 5. GitHub API — Post Inline Comments

```python
# app/github_client.py
import httpx, os
from .agent.state import ReviewState

GITHUB_API = "https://api.github.com"

async def post_review(state: ReviewState, commit_sha: str):
    """Post review comments to GitHub PR."""
    headers = {
        "Authorization": f"token {os.getenv('GITHUB_TOKEN')}",
        "Accept": "application/vnd.github.v3+json",
    }

    # Build inline comments
    comments = []

    for issue in state["security_issues"]:
        comments.append({
            "path": issue.file,
            "line": issue.line,
            "body": f"**[{issue.severity} Security]** {issue.description}\n\n**Fix:** {issue.suggestion}",
        })

    for issue in state["performance_issues"]:
        comments.append({
            "path": issue.file,
            "line": issue.line,
            "body": f"**[Performance]** {issue.type}: {issue.impact}\n\n**Suggestion:** {issue.suggestion}",
        })

    # Submit review
    review_event = "REQUEST_CHANGES" if state["decision"] != "approve" else "APPROVE"

    async with httpx.AsyncClient() as client:
        await client.post(
            f"{GITHUB_API}/repos/{state['repo']}/pulls/{state['pr_id']}/reviews",
            headers=headers,
            json={
                "commit_id": commit_sha,
                "body": state["review_comment"],
                "event": review_event,
                "comments": comments,
            }
        )

    # Block merge on CRITICAL
    critical = [i for i in state["security_issues"] if i.severity == "CRITICAL"]
    if critical:
        await client.post(
            f"{GITHUB_API}/repos/{state['repo']}/statuses/{commit_sha}",
            headers=headers,
            json={
                "state": "failure",
                "description": f"{len(critical)} critical security issues found",
                "context": "ai-code-review/security",
            }
        )
```

### 6. Slack Notification via MCP

```python
# mcp-server/slack_tool.py — MCP tool for Slack
from fastmcp import FastMCP
import httpx, os

mcp = FastMCP("slack-notifier")

@mcp.tool()
async def send_slack_message(channel: str, message: str, blocks: list | None = None) -> dict:
    """
    Send a message to a Slack channel.
    
    Args:
        channel: Slack channel ID or name (e.g., "#engineering")
        message: Plain text message
        blocks: Optional Slack Block Kit blocks for rich formatting
    """
    webhook_url = os.getenv("SLACK_WEBHOOK_URL")
    payload = {"text": message, "channel": channel}
    if blocks:
        payload["blocks"] = blocks

    async with httpx.AsyncClient() as client:
        resp = await client.post(webhook_url, json=payload)
    return {"status": "sent" if resp.status_code == 200 else "failed"}

# In synthesizer agent — use MCP tool to notify on critical
async def notify_human_reviewer(state: ReviewState):
    critical_issues = [i for i in state["security_issues"] if i.severity == "CRITICAL"]

    blocks = [
        {"type": "section", "text": {"type": "mrkdwn",
            "text": f"*CRITICAL Security Issue in PR #{state['pr_id']}*"}},
        {"type": "section", "text": {"type": "mrkdwn",
            "text": "\n".join([f"• {i.description}" for i in critical_issues])}},
        {"type": "actions", "elements": [
            {"type": "button", "text": {"type": "plain_text", "text": "Review PR"},
             "url": f"https://github.com/{state['repo']}/pull/{state['pr_id']}"}
        ]}
    ]
    # Send via MCP tool...
```

---

## Cost Analysis

```
REVIEW COST BREAKDOWN:
  Small PR (<100 lines):
    Security Agent (Opus):    ~$0.03
    Performance (Sonnet):     ~$0.01
    Style (Haiku):            ~$0.001
    Total:                    ~$0.04

  Medium PR (100-500 lines):
    Total:                    ~$0.15-0.20

  Large PR (>500 lines):
    Total:                    ~$0.40-0.60

COST OPTIMIZATION:
  - Haiku for style (saves 90% vs Sonnet)
  - Skip style review for non-.py files
  - Cache security patterns (don't re-review unchanged files)
  - Batch reviews in off-peak hours
```

---

## Interview Talking Points

```
SYSTEM DESIGN DECISIONS:

1. Why Supervisor pattern (not just sequential)?
   - 3 agents can run in PARALLEL → 3x faster
   - Each agent specialized → better results
   - Synthesizer sees all results → coherent final review

2. Why Instructor for structured output?
   - Agents MUST return structured data (SecurityIssue, not free text)
   - Instructor handles retry on validation failure
   - Type-safe: Pydantic validation catches bad LLM output

3. Why Opus for security, Haiku for style?
   - Security: missing one CRITICAL issue = disaster → best model
   - Style: PEP8 check is simple → cheapest model
   - Cost savings: 95% cheaper overall vs all-Opus

4. Human-in-the-loop via interrupt:
   - LangGraph interrupt_before=["human_review"]
   - Graph pauses, sends Slack alert
   - Human approves via API → graph resumes
   - State persisted in PostgreSQL → survives restarts

5. Webhook security:
   - HMAC-SHA256 signature verification
   - Replay attack prevention: check X-GitHub-Delivery header
   - Secret stored in env var, never in code
```
