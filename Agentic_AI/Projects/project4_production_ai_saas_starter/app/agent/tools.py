"""Tools the triage agent may call.

Two things matter here beyond the implementations:

1. Every tool is read-only. Nothing the agent can call on its own changes state.
   Issuing an actual refund is a human action, gated by `needs_human`.
2. Tool descriptions state *when* to call, not only what the tool does. Recent
   Claude models reach for tools conservatively; a trigger condition in the
   description is what raises the should-call rate.
"""

from typing import Any

# Stand-in for the orders service. A real deployment swaps this for a repository
# call; the tool signature and the eval suite stay unchanged.
_ORDERS: dict[str, dict[str, Any]] = {
    "A1001": {"status": "delivered", "amount_usd": 42.50, "region": "US", "days_since_delivery": 3},
    "A1002": {"status": "in_transit", "amount_usd": 189.00, "region": "EU", "days_since_delivery": None},
    "A1003": {"status": "delivered", "amount_usd": 640.00, "region": "US", "days_since_delivery": 45},
    "A1004": {"status": "cancelled", "amount_usd": 15.00, "region": "IN", "days_since_delivery": None},
    "A1005": {"status": "delivered", "amount_usd": 95.00, "region": "EU", "days_since_delivery": 12},
}

_REFUND_POLICY: dict[str, dict[str, Any]] = {
    "US": {"window_days": 30, "max_auto_refund_usd": 100.0},
    "EU": {"window_days": 14, "max_auto_refund_usd": 100.0},
    "IN": {"window_days": 7, "max_auto_refund_usd": 50.0},
}


def lookup_order(order_id: str) -> dict[str, Any]:
    """Return order status, amount and region for an order id."""
    order = _ORDERS.get(order_id.strip().upper())
    if order is None:
        return {"found": False, "order_id": order_id}
    return {"found": True, "order_id": order_id.strip().upper(), **order}


def get_refund_policy(region: str) -> dict[str, Any]:
    """Return the refund window and auto-approval ceiling for a region."""
    policy = _REFUND_POLICY.get(region.strip().upper())
    if policy is None:
        return {"found": False, "region": region}
    return {"found": True, "region": region.strip().upper(), **policy}


TOOL_IMPLS = {
    "lookup_order": lookup_order,
    "get_refund_policy": get_refund_policy,
}

TOOL_DEFS = [
    {
        "name": "lookup_order",
        "description": (
            "Look up an order's status, amount and region. Call this whenever the "
            "ticket mentions an order id, a delivery, or a specific purchase — do "
            "not assume order details from the ticket text alone."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "order_id": {
                    "type": "string",
                    "description": "Order id, e.g. A1001.",
                }
            },
            "required": ["order_id"],
            "additionalProperties": False,
        },
        "strict": True,
    },
    {
        "name": "get_refund_policy",
        "description": (
            "Return the refund window and the maximum amount that may be refunded "
            "without human approval, for one region. Call this before saying "
            "anything to the customer about whether a refund is possible."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "region": {
                    "type": "string",
                    "description": "Two-letter region code: US, EU or IN.",
                }
            },
            "required": ["region"],
            "additionalProperties": False,
        },
        "strict": True,
    },
]


def run_tool(name: str, tool_input: dict[str, Any]) -> dict[str, Any]:
    """Execute a tool by name. Unknown tools return an error result rather than
    raising, so the model can recover instead of the loop dying."""
    impl = TOOL_IMPLS.get(name)
    if impl is None:
        return {"error": f"unknown tool: {name}"}
    try:
        return impl(**tool_input)
    except TypeError as exc:
        return {"error": f"bad arguments for {name}: {exc}"}
