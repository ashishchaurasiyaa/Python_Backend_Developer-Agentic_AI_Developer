"""Milestones 3-5 — Security, Performance, Style agents + Synthesizer + human review."""
import os
from .state import (
    ReviewState, SecurityIssue, PerformanceIssue, StyleIssue,
    SecurityReviewResult, PerformanceReviewResult, StyleReviewResult,
)

# ---------------------------------------------------------------------------
# Lazy client helpers — app starts without keys
# ---------------------------------------------------------------------------

def _instructor_client(model: str):
    """Return (instructor_client, model) or None if no API key."""
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return None, model
    import instructor
    import anthropic
    client = instructor.from_anthropic(anthropic.AsyncAnthropic())
    return client, model


# ---------------------------------------------------------------------------
# Milestone 3 — Security agent  (Opus — never miss a critical vuln)
# ---------------------------------------------------------------------------

SECURITY_PROMPT = """You are a senior application security engineer.
Review the following PR diff for OWASP Top 10 vulnerabilities, hardcoded secrets,
HMAC bypass, SQL injection, path traversal, and missing input validation.
Return structured findings only."""

async def run_security_review(state: ReviewState) -> dict:
    client, model = _instructor_client("claude-opus-4-8")

    if client is None:
        print("[security] No API key — returning empty stub")
        return {
            "security_issues": [],
            "cost_usd": state.get("cost_usd", 0.0),
        }

    result: SecurityReviewResult = await client.messages.create(
        model=model,
        max_tokens=2048,
        messages=[{
            "role": "user",
            "content": f"{SECURITY_PROMPT}\n\nDiff:\n{state['diff']}",
        }],
        response_model=SecurityReviewResult,
    )

    return {
        "security_issues": result.issues,
        "cost_usd": state.get("cost_usd", 0.0) + result.cost_usd + 0.08,
    }


# ---------------------------------------------------------------------------
# Milestone 4a — Performance agent  (Sonnet — N+1, sync-in-async)
# ---------------------------------------------------------------------------

PERF_PROMPT = """You are a backend performance engineer.
Find N+1 queries, sync calls inside async functions, missing DB indexes,
blocking I/O in async handlers, and unbounded loops.
Return structured findings only."""

async def run_performance_review(state: ReviewState) -> dict:
    client, model = _instructor_client("claude-sonnet-4-6")

    if client is None:
        print("[perf] No API key — returning empty stub")
        return {
            "performance_issues": [],
            "cost_usd": state.get("cost_usd", 0.0),
        }

    result: PerformanceReviewResult = await client.messages.create(
        model=model,
        max_tokens=1024,
        messages=[{
            "role": "user",
            "content": f"{PERF_PROMPT}\n\nDiff:\n{state['diff']}",
        }],
        response_model=PerformanceReviewResult,
    )

    return {
        "performance_issues": result.issues,
        "cost_usd": state.get("cost_usd", 0.0) + result.cost_usd + 0.02,
    }


# ---------------------------------------------------------------------------
# Milestone 4b — Style agent  (Haiku — cheapest, PEP8 + type hints)
# ---------------------------------------------------------------------------

STYLE_PROMPT = """You are a Python style reviewer.
Check for PEP 8 violations, missing type hints, unclear names,
missing docstrings on public functions, and mutable default arguments.
Return structured findings only."""

async def run_style_review(state: ReviewState) -> dict:
    client, model = _instructor_client("claude-haiku-4-5")

    if client is None:
        print("[style] No API key — returning empty stub")
        return {
            "style_issues": [],
            "cost_usd": state.get("cost_usd", 0.0),
        }

    result: StyleReviewResult = await client.messages.create(
        model=model,
        max_tokens=1024,
        messages=[{
            "role": "user",
            "content": f"{STYLE_PROMPT}\n\nDiff:\n{state['diff']}",
        }],
        response_model=StyleReviewResult,
    )

    return {
        "style_issues": result.issues,
        "cost_usd": state.get("cost_usd", 0.0) + result.cost_usd + 0.001,
    }


# ---------------------------------------------------------------------------
# Milestone 5 — Synthesizer
# ---------------------------------------------------------------------------

def synthesize_review(state: ReviewState) -> dict:
    """Merge all agent findings into a final decision + human-readable comment."""
    security = state.get("security_issues", [])
    perf = state.get("performance_issues", [])
    style = state.get("style_issues", [])

    has_critical = any(i.severity == "CRITICAL" for i in security)
    has_high = any(i.severity == "HIGH" for i in security)
    total = len(security) + len(perf) + len(style)

    if has_critical:
        decision = "human_review"
    elif has_high or total > 5:
        decision = "request_changes"
    elif total == 0:
        decision = "approve"
    else:
        decision = "request_changes"

    lines = ["## Automated Code Review\n"]

    if security:
        lines.append(f"### Security ({len(security)} issues)")
        for i in security:
            lines.append(f"- **[{i.severity}]** `{i.file}:{i.line}` — {i.description}")
            lines.append(f"  > {i.suggestion}")

    if perf:
        lines.append(f"\n### Performance ({len(perf)} issues)")
        for i in perf:
            lines.append(f"- **[{i.type}]** `{i.file}:{i.line}` — {i.impact}")
            lines.append(f"  > {i.suggestion}")

    if style:
        lines.append(f"\n### Style ({len(style)} issues)")
        for i in style:
            lines.append(f"- `{i.file}:{i.line}` [{i.rule}] — {i.message}")

    cost = state.get("cost_usd", 0.0)
    lines.append(f"\n---\n_Review cost: ${cost:.3f} | Decision: **{decision}**_")

    return {
        "decision": decision,
        "review_comment": "\n".join(lines),
    }


# ---------------------------------------------------------------------------
# Milestone 5 — Human-in-the-loop interrupt node
# ---------------------------------------------------------------------------

def human_review_interrupt(state: ReviewState) -> dict:
    """
    LangGraph pauses here (interrupt_before) when a CRITICAL issue is found.
    A human must resume with an approved or escalated decision.
    """
    print(f"[human_review] PR #{state['pr_id']} has CRITICAL issues — awaiting human decision.")
    return {}


# ---------------------------------------------------------------------------
# Routing function
# ---------------------------------------------------------------------------

def route_after_synthesize(state: ReviewState) -> str:
    return "human_review" if state["decision"] == "human_review" else "post_github"
