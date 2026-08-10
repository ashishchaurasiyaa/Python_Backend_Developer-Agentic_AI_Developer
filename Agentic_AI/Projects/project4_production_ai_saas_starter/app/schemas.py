"""The agent's output contract.

Two representations of the same thing:
  - TriageResult  : Pydantic model, used to validate what came back.
  - TRIAGE_SCHEMA : JSON Schema, sent to the API as output_config.format so the
                    model is constrained to produce it in the first place.

Validating on both sides is deliberate. The schema stops most malformed output;
the Pydantic model is what proves it, and what the eval harness asserts against.
"""

from typing import Literal, Optional

from pydantic import BaseModel, Field

Category = Literal["billing", "shipping", "technical", "refund", "account", "other"]
Priority = Literal["low", "medium", "high", "urgent"]


class TriageResult(BaseModel):
    category: Category
    priority: Priority
    order_id: Optional[str] = Field(
        default=None, description="Order id referenced by the ticket, if any."
    )
    needs_human: bool = Field(
        description="True when a human must review before the reply is sent."
    )
    draft_reply: str = Field(description="Reply drafted for the customer.")


# Hand-written rather than generated from the model: structured outputs require
# additionalProperties=false and an explicit `required` list, and nullable
# fields must be expressed as anyOf.
TRIAGE_SCHEMA = {
    "type": "object",
    "properties": {
        "category": {
            "type": "string",
            "enum": ["billing", "shipping", "technical", "refund", "account", "other"],
        },
        "priority": {
            "type": "string",
            "enum": ["low", "medium", "high", "urgent"],
        },
        "order_id": {
            "anyOf": [{"type": "string"}, {"type": "null"}],
            "description": "Order id referenced by the ticket, or null.",
        },
        "needs_human": {"type": "boolean"},
        "draft_reply": {"type": "string"},
    },
    "required": ["category", "priority", "order_id", "needs_human", "draft_reply"],
    "additionalProperties": False,
}
