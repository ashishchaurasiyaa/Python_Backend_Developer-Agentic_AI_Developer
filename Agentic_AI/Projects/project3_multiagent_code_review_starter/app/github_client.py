"""Milestone 7 — GitHub API: post inline PR comments + request changes / approve."""
import os
import httpx

from app.agent.state import ReviewState

GITHUB_API = "https://api.github.com"


def _headers() -> dict:
    token = os.getenv("GITHUB_TOKEN", "")
    return {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


async def _get_pr_head_sha(repo: str, pr_id: int) -> str:
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{GITHUB_API}/repos/{repo}/pulls/{pr_id}",
            headers=_headers(),
        )
        resp.raise_for_status()
        return resp.json()["head"]["sha"]


async def post_review(state: ReviewState) -> None:
    """Post the synthesized review to GitHub as a PR review with inline comments."""
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        print(f"[github] No GITHUB_TOKEN — skipping review post for PR #{state['pr_id']}")
        return

    repo = state["repo"]
    pr_id = state["pr_id"]
    decision = state["decision"]

    try:
        commit_sha = await _get_pr_head_sha(repo, pr_id)
    except Exception as e:
        print(f"[github] Could not fetch PR head SHA: {e}")
        return

    # Build inline comments from security + perf issues
    inline_comments = []
    for issue in state.get("security_issues", []):
        inline_comments.append({
            "path": issue.file,
            "line": issue.line,
            "body": (
                f"**[{issue.severity} Security]** {issue.description}\n\n"
                f"**Suggestion:** {issue.suggestion}"
                + (f"\n\n_OWASP: {issue.owasp_category}_" if issue.owasp_category else "")
            ),
        })

    for issue in state.get("performance_issues", []):
        inline_comments.append({
            "path": issue.file,
            "line": issue.line,
            "body": f"**[Perf: {issue.type}]** {issue.impact}\n\n**Suggestion:** {issue.suggestion}",
        })

    # Map internal decision to GitHub event
    github_event_map = {
        "approve": "APPROVE",
        "request_changes": "REQUEST_CHANGES",
        "human_review": "COMMENT",  # escalated — don't block merge automatically
    }
    github_event = github_event_map.get(decision, "COMMENT")

    payload = {
        "commit_id": commit_sha,
        "body": state["review_comment"],
        "event": github_event,
        "comments": inline_comments,
    }

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{GITHUB_API}/repos/{repo}/pulls/{pr_id}/reviews",
            headers=_headers(),
            json=payload,
        )
        if resp.status_code not in (200, 201):
            print(f"[github] Review post failed: {resp.status_code} {resp.text}")
        else:
            print(f"[github] Review posted — PR #{pr_id} ({github_event})")
