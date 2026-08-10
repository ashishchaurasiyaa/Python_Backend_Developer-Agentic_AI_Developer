"""Model backends behind one interface.

`AnthropicBackend` is the real thing. `StubBackend` is a deterministic
rule-based model that speaks the same wire shape (tool_use blocks, tool_result
blocks, a final JSON body).

The stub exists for one reason: the eval harness must be runnable and
reproducible without an API key and without spending money. Numbers produced
under the stub are labelled as stub numbers in every report — they measure the
harness, not the model.
"""

import json
import os
import re
from dataclasses import dataclass, field
from typing import Any, Optional

from app.config import EFFORT, MAX_TOKENS, MODEL


@dataclass
class ToolCall:
    id: str
    name: str
    input: dict[str, Any]


@dataclass
class LLMResponse:
    text: str
    tool_calls: list[ToolCall] = field(default_factory=list)
    assistant_content: Any = None  # appended verbatim as the assistant turn
    input_tokens: int = 0
    output_tokens: int = 0
    stop_reason: Optional[str] = None


class Backend:
    name = "base"

    def complete(
        self,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        output_schema: Optional[dict[str, Any]] = None,
    ) -> LLMResponse:
        raise NotImplementedError


# --------------------------------------------------------------------------
# Real backend
# --------------------------------------------------------------------------


class AnthropicBackend(Backend):
    name = "anthropic"

    def __init__(self, model: str = MODEL, effort: str = EFFORT) -> None:
        import anthropic  # imported lazily so the stub path needs no SDK

        self.model = model
        self.effort = effort
        self.client = anthropic.Anthropic()

    def complete(
        self,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        output_schema: Optional[dict[str, Any]] = None,
    ) -> LLMResponse:
        output_config: dict[str, Any] = {"effort": self.effort}
        if output_schema is not None:
            output_config["format"] = {"type": "json_schema", "schema": output_schema}

        # Thinking is left at its default (adaptive) on Opus 5. Disabling it is
        # what makes a model emit tool calls as plain text; `effort` is the cost
        # lever instead.
        response = self.client.messages.create(
            model=self.model,
            max_tokens=MAX_TOKENS,
            system=system,
            tools=tools,
            output_config=output_config,
            messages=messages,
        )

        if response.stop_reason == "refusal":
            return LLMResponse(
                text="",
                assistant_content=response.content,
                input_tokens=response.usage.input_tokens,
                output_tokens=response.usage.output_tokens,
                stop_reason="refusal",
            )

        text = "".join(b.text for b in response.content if b.type == "text")
        calls = [
            ToolCall(id=b.id, name=b.name, input=dict(b.input))
            for b in response.content
            if b.type == "tool_use"
        ]
        return LLMResponse(
            text=text,
            tool_calls=calls,
            assistant_content=response.content,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            stop_reason=response.stop_reason,
        )


# --------------------------------------------------------------------------
# Deterministic stub backend
# --------------------------------------------------------------------------

_ORDER_RE = re.compile(r"\bA\d{4}\b", re.IGNORECASE)

_REFUND_WORDS = ("refund", "money back", "return it", "reimburse")
_SHIPPING_WORDS = ("where is", "delivery", "shipping", "arrive", "tracking", "not delivered")
_BILLING_WORDS = ("charged", "invoice", "billing", "payment", "double charge", "card")
_ACCOUNT_WORDS = ("password", "log in", "login", "sign in", "account locked", "2fa")
_TECH_WORDS = ("error", "crash", "bug", "not working", "broken", "fails")
_URGENT_WORDS = ("urgent", "asap", "immediately", "legal", "chargeback", "lawyer")
_ANGRY_WORDS = ("angry", "furious", "unacceptable", "terrible", "worst")


class StubBackend(Backend):
    """Rule-based stand-in. Same wire shape as the real backend, no network."""

    name = "stub"

    def complete(
        self,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        output_schema: Optional[dict[str, Any]] = None,
    ) -> LLMResponse:
        ticket = _first_user_text(messages)
        results = _tool_results_so_far(messages)
        low = ticket.lower()
        order_id = _ORDER_RE.search(ticket)
        order_id = order_id.group(0).upper() if order_id else None

        # Step 1 — look the order up before saying anything about it.
        if order_id and "lookup_order" not in results:
            return self._tool_call("lookup_order", {"order_id": order_id}, "call_1")

        order = results.get("lookup_order")

        # Step 2 — check policy before mentioning a refund.
        wants_refund = any(w in low for w in _REFUND_WORDS)
        if wants_refund and "get_refund_policy" not in results:
            region = (order or {}).get("region", "US")
            return self._tool_call("get_refund_policy", {"region": region}, "call_2")

        # Step 3 — final answer.
        payload = _decide(ticket, order, results.get("get_refund_policy"))
        body = json.dumps(payload)
        return LLMResponse(
            text=body,
            assistant_content=[{"type": "text", "text": body}],
            input_tokens=_approx_tokens(system) + _approx_tokens(json.dumps(messages, default=str)),
            output_tokens=_approx_tokens(body),
            stop_reason="end_turn",
        )

    def _tool_call(self, name: str, args: dict[str, Any], call_id: str) -> LLMResponse:
        return LLMResponse(
            text="",
            tool_calls=[ToolCall(id=call_id, name=name, input=args)],
            assistant_content=[
                {"type": "tool_use", "id": call_id, "name": name, "input": args}
            ],
            input_tokens=120,
            output_tokens=40,
            stop_reason="tool_use",
        )


def _decide(
    ticket: str,
    order: Optional[dict[str, Any]],
    policy: Optional[dict[str, Any]],
) -> dict[str, Any]:
    low = ticket.lower()

    if any(w in low for w in _REFUND_WORDS):
        category = "refund"
    elif any(w in low for w in _SHIPPING_WORDS):
        category = "shipping"
    elif any(w in low for w in _BILLING_WORDS):
        category = "billing"
    elif any(w in low for w in _ACCOUNT_WORDS):
        category = "account"
    elif any(w in low for w in _TECH_WORDS):
        category = "technical"
    else:
        category = "other"

    amount = float((order or {}).get("amount_usd") or 0.0)
    if any(w in low for w in _URGENT_WORDS):
        priority = "urgent"
    elif amount >= 500 or any(w in low for w in _ANGRY_WORDS):
        priority = "high"
    elif order is not None:
        priority = "medium"
    else:
        priority = "low"

    needs_human = priority == "urgent"
    reply_parts: list[str] = ["Thanks for reaching out — I've looked into this."]

    if category == "refund":
        ceiling = float((policy or {}).get("max_auto_refund_usd") or 0.0)
        window = int((policy or {}).get("window_days") or 0)
        days = (order or {}).get("days_since_delivery")
        out_of_window = days is not None and window and days > window

        if amount > ceiling or out_of_window:
            needs_human = True
            reply_parts.append(
                "A refund on this order needs a review by our team before it can "
                "be approved, so I've passed it on and someone will confirm shortly."
            )
        else:
            reply_parts.append(
                f"This order is inside our {window}-day window, so the refund can "
                "go ahead and you'll see it back on your original payment method."
            )
    elif category == "shipping":
        status = (order or {}).get("status", "unknown")
        reply_parts.append(f"Your order is currently marked as {status}.")
    else:
        reply_parts.append("I've raised this with the right team and we'll follow up.")

    return {
        "category": category,
        "priority": priority,
        "order_id": (order or {}).get("order_id"),
        "needs_human": needs_human,
        "draft_reply": " ".join(reply_parts),
    }


def _first_user_text(messages: list[dict[str, Any]]) -> str:
    for msg in messages:
        if msg.get("role") != "user":
            continue
        content = msg.get("content")
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            for block in content:
                if isinstance(block, dict) and block.get("type") == "text":
                    return str(block.get("text", ""))
    return ""


def _tool_results_so_far(messages: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Map tool name -> its most recent result, by pairing tool_use ids with
    the tool_result blocks that answered them."""
    id_to_name: dict[str, str] = {}
    out: dict[str, dict[str, Any]] = {}
    for msg in messages:
        content = msg.get("content")
        if not isinstance(content, list):
            continue
        for block in content:
            block = block if isinstance(block, dict) else getattr(block, "__dict__", {})
            if block.get("type") == "tool_use":
                id_to_name[str(block.get("id"))] = str(block.get("name"))
            elif block.get("type") == "tool_result":
                name = id_to_name.get(str(block.get("tool_use_id")))
                if not name:
                    continue
                try:
                    out[name] = json.loads(block.get("content") or "{}")
                except (json.JSONDecodeError, TypeError):
                    out[name] = {}
    return out


def _approx_tokens(text: str) -> int:
    """Rough token estimate for the stub only. Real counts come from the API's
    usage block; never use this for billing."""
    return max(1, len(text) // 4)


def get_backend(name: Optional[str] = None) -> Backend:
    """Pick a backend. Defaults to the real one when a credential is present."""
    name = name or os.getenv("AGENT_PROVIDER") or (
        "anthropic" if os.getenv("ANTHROPIC_API_KEY") else "stub"
    )
    if name == "anthropic":
        return AnthropicBackend()
    if name == "stub":
        return StubBackend()
    raise ValueError(f"unknown backend: {name}")
