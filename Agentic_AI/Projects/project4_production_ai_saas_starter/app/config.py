"""Configuration for the triage agent.

Comments in this package are English on purpose: this project is meant to be
read by interviewers, not only by me.
"""

import os

# Claude Opus 5. Thinking is ON by default on this model — do not disable it,
# because a disabled-thinking Opus 5 can emit a tool call as plain text (the
# call silently never runs). Cost is controlled with `effort` instead.
MODEL = "claude-opus-5"
EFFORT = os.getenv("AGENT_EFFORT", "low")

# max_tokens caps thinking + response text together, so leave headroom.
MAX_TOKENS = 8192

# USD per million tokens (Claude Opus 5).
PRICE_IN_PER_MTOK = 5.00
PRICE_OUT_PER_MTOK = 25.00

# Agent loop safety rails.
MAX_STEPS = 6

# Guardrail limits.
MAX_TICKET_CHARS = 4000
# Above this amount a refund may not be auto-approved by the agent.
REFUND_HUMAN_APPROVAL_THRESHOLD = 100.00

TRACE_DIR = os.getenv("TRACE_DIR", "traces")
REPORT_DIR = os.getenv("REPORT_DIR", "reports")


def cost_usd(input_tokens: int, output_tokens: int) -> float:
    """Cost of one model call in USD."""
    return (
        input_tokens / 1_000_000 * PRICE_IN_PER_MTOK
        + output_tokens / 1_000_000 * PRICE_OUT_PER_MTOK
    )
