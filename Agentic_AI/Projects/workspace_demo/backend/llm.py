"""
Claude client wrapper.

Placeholder-safe: if ANTHROPIC_API_KEY is not set, the app still runs and
returns a friendly demo reply instead of crashing. This makes it safe to
launch live during a presentation without a key.
"""
import os

from .config import settings

SYSTEM_PROMPT = (
    "You are a helpful, concise AI assistant embedded in a demo web app. "
    "Answer in a few short sentences unless asked for detail."
)


def _client():
    """Return an Anthropic client, or None if no API key is configured."""
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return None
    import anthropic  # lazy import — app starts without the key
    return anthropic.Anthropic()


def generate_reply(message: str, history: list[dict]) -> str:
    """Send the conversation to Claude and return the assistant's text reply."""
    client = _client()

    if client is None:
        return (
            "[demo mode] No ANTHROPIC_API_KEY is set, so I'm echoing instead of "
            f'calling Claude. You said: "{message}". '
            "Add your key to .env and restart to chat for real."
        )

    # The API is stateless — send the full history each turn.
    messages = [{"role": m["role"], "content": m["content"]} for m in history]
    messages.append({"role": "user", "content": message})

    response = client.messages.create(
        model=settings.model,
        max_tokens=1024,
        system=SYSTEM_PROMPT,
        messages=messages,
    )

    return "".join(block.text for block in response.content if block.type == "text")
