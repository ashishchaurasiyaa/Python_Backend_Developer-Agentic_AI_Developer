"""Input and output guardrails.

Input side: cap the size, strip PII before it ever reaches the model, and flag
prompt-injection attempts.

Output side: check the model's answer against rules the model is not trusted to
enforce on its own. Every violation is recorded on the trace and most are
*repaired* rather than blocked — a support reply routed to a human is a better
failure mode than no reply at all. The eval suite asserts on the repaired
output, so a regression in the model shows up as a spike in violations rather
than as silently worse answers.
"""

import re
from dataclasses import dataclass
from typing import Any, Optional

from app.config import MAX_TICKET_CHARS, REFUND_HUMAN_APPROVAL_THRESHOLD
from app.schemas import TriageResult

EMAIL_RE = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.]+\b")
CARD_RE = re.compile(r"\b(?:\d[ -]?){13,16}\b")
PHONE_RE = re.compile(r"\b(?:\+?\d{1,3}[ -]?)?(?:\d[ -]?){9,12}\b")

INJECTION_PATTERNS = [
    re.compile(p, re.IGNORECASE)
    for p in (
        r"ignore (all |any )?(previous|prior|above) instructions",
        r"disregard (the )?(system|previous) prompt",
        r"you are now\b",
        r"reveal (your )?(system )?prompt",
        r"print (your )?instructions",
        r"</?system>",
    )
]


class InputRejected(Exception):
    """Raised when a ticket must not reach the model at all."""


@dataclass
class Violation:
    code: str
    message: str


@dataclass
class GuardedInput:
    text: str
    redactions: int
    injection_detected: bool


def guard_input(ticket: str) -> GuardedInput:
    """Sanitise a ticket before it reaches the model."""
    if not ticket or not ticket.strip():
        raise InputRejected("empty ticket")
    if len(ticket) > MAX_TICKET_CHARS:
        raise InputRejected(
            f"ticket is {len(ticket)} chars, limit is {MAX_TICKET_CHARS}"
        )

    injection = any(p.search(ticket) for p in INJECTION_PATTERNS)

    redactions = 0
    text = ticket
    for pattern, token in ((EMAIL_RE, "[EMAIL]"), (CARD_RE, "[CARD]"), (PHONE_RE, "[PHONE]")):
        text, n = pattern.subn(token, text)
        redactions += n

    return GuardedInput(text=text, redactions=redactions, injection_detected=injection)


def guard_output(
    result: TriageResult,
    *,
    tools_called: list[str],
    order: Optional[dict[str, Any]],
    injection_detected: bool,
) -> tuple[TriageResult, list[Violation]]:
    """Check the model's answer and repair what can safely be repaired.

    Returns the (possibly repaired) result plus every violation found.
    """
    violations: list[Violation] = []
    data = result.model_dump()

    # 1. A reply may not discuss refunds unless the policy tool actually ran.
    mentions_refund = "refund" in data["draft_reply"].lower()
    if mentions_refund and "get_refund_policy" not in tools_called:
        violations.append(
            Violation(
                "refund_discussed_without_policy_check",
                "draft_reply mentions a refund but get_refund_policy was never called",
            )
        )
        data["needs_human"] = True

    # 2. A refund above the approval threshold is never auto-approved.
    amount = float((order or {}).get("amount_usd") or 0.0)
    if (
        data["category"] == "refund"
        and amount > REFUND_HUMAN_APPROVAL_THRESHOLD
        and not data["needs_human"]
    ):
        violations.append(
            Violation(
                "high_value_refund_auto_approved",
                f"refund of ${amount:.2f} exceeds "
                f"${REFUND_HUMAN_APPROVAL_THRESHOLD:.2f} but needs_human was false",
            )
        )
        data["needs_human"] = True

    # 3. Anything that looked like prompt injection goes to a human.
    if injection_detected and not data["needs_human"]:
        violations.append(
            Violation(
                "injection_not_escalated",
                "prompt-injection pattern in the ticket but needs_human was false",
            )
        )
        data["needs_human"] = True

    # 4. No raw PII may survive into the customer-facing reply.
    reply, leaked = _strip_pii(data["draft_reply"])
    if leaked:
        violations.append(
            Violation("pii_in_reply", f"{leaked} PII value(s) redacted from draft_reply")
        )
        data["draft_reply"] = reply
        data["needs_human"] = True

    return TriageResult(**data), violations


def _strip_pii(text: str) -> tuple[str, int]:
    total = 0
    for pattern, token in ((EMAIL_RE, "[EMAIL]"), (CARD_RE, "[CARD]")):
        text, n = pattern.subn(token, text)
        total += n
    return text, total
