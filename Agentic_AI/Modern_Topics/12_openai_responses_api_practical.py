"""
Modern Topics — Doc 12: OpenAI Responses API (PRACTICAL)
============================================================
Topics covered:
  1. Basic call — input= and output_text (vs Chat Completions' messages=/choices)
  2. Stateful conversation — previous_response_id, no re-sending history
  3. Custom function calling — the function_call_output item shape
  4. Structured outputs — client.responses.parse() with a Pydantic model

Install: pip install openai pydantic python-dotenv
Run: python 12_openai_responses_api_practical.py
"""

import json
import os
from dotenv import load_dotenv

load_dotenv()
HAS_KEY = bool(os.getenv("OPENAI_API_KEY"))


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 1: Basic Call — input= and output_text
# ─────────────────────────────────────────────────────────────────────────────

print("=" * 70)
print("SECTION 1: Basic Call")
print("=" * 70)

if not HAS_KEY:
    print("\n  [NO_API_KEY — set OPENAI_API_KEY to run this live. Showing the shape:]")
    print("""
    resp = client.responses.create(model="gpt-4.1", input="Explain idempotency in REST APIs in 2 lines.")
    print(resp.output_text)   # convenience: all text as one string
    # resp.output -> list of output items (messages, tool_calls, reasoning, etc.)
    """)
else:
    from openai import OpenAI
    client = OpenAI()
    resp = client.responses.create(model="gpt-4.1", input="Explain idempotency in REST APIs in 2 lines.")
    print(f"\n  {resp.output_text}")
    print(f"\n  resp.output has {len(resp.output)} item(s), types: {[item.type for item in resp.output]}")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 2: Stateful Conversation — previous_response_id
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("SECTION 2: Stateful Conversation (the killer feature)")
print("=" * 70)

if HAS_KEY:
    r1 = client.responses.create(model="gpt-4.1", input="My name is Ashish.")
    r2 = client.responses.create(model="gpt-4.1", input="What's my name?", previous_response_id=r1.id)
    print(f"\n  Turn 1: {r1.output_text}")
    print(f"  Turn 2 (chained via previous_response_id, no history resent): {r2.output_text}")
    print("\n  Notice: turn 2's INPUT was only 'What's my name?' — the server")
    print("  remembers turn 1 via previous_response_id, unlike Chat Completions")
    print("  where you'd have to resend the whole message list every call.")
else:
    print("""
    r1 = client.responses.create(model="gpt-4.1", input="My name is Ashish.")
    r2 = client.responses.create(model="gpt-4.1", input="What's my name?",
                                   previous_response_id=r1.id)   # <- server-side chain
    print(r2.output_text)   # "Ashish" — no history resent
    """)
    print("  [NO_API_KEY — this is the single biggest structural difference from")
    print("   Chat Completions worth remembering for an interview: state lives")
    print("   server-side, addressed by response ID, not resent every call.]")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 3: Custom Function Calling — function_call_output Shape
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("SECTION 3: Custom Function Calling")
print("=" * 70)

TOOLS = [{
    "type": "function",
    "name": "get_weather",
    "description": "Get current weather for a city",
    "parameters": {"type": "object", "properties": {"city": {"type": "string"}}, "required": ["city"]},
}]


def get_weather(city: str) -> dict:
    return {"temp_c": 32, "sky": "humid"}  # stand-in for a real weather API call


if HAS_KEY:
    resp = client.responses.create(model="gpt-4.1", input="What's the weather in Mumbai?", tools=TOOLS)
    for item in resp.output:
        if item.type == "function_call":
            args = json.loads(item.arguments)
            result = get_weather(**args)
            print(f"\n  Model requested: get_weather({args})")
            print(f"  Real function returned: {result}")

            # Send the result back, chained via previous_response_id — note the
            # NEW item type: "function_call_output" (replaces Chat Completions'
            # role: "tool" message).
            final = client.responses.create(
                model="gpt-4.1",
                previous_response_id=resp.id,
                input=[{"type": "function_call_output", "call_id": item.call_id, "output": json.dumps(result)}],
            )
            print(f"  Final answer: {final.output_text}")
            break
    else:
        print(f"\n  Model answered directly without calling the tool: {resp.output_text}")
else:
    print("""
    for item in resp.output:
        if item.type == "function_call":
            args = json.loads(item.arguments)
            result = get_weather(**args)
            final = client.responses.create(
                model="gpt-4.1",
                previous_response_id=resp.id,
                input=[{"type": "function_call_output", "call_id": item.call_id,
                         "output": json.dumps(result)}],
            )
    """)
    print("  [NO_API_KEY — key difference from Chat Completions: the tool result")
    print("   goes back as a 'function_call_output' ITEM in a new input=[...] list,")
    print("   chained via previous_response_id, not appended to a growing messages array.]")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 4: Structured Outputs — responses.parse()
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("SECTION 4: Structured Outputs (schema-guaranteed)")
print("=" * 70)

from pydantic import BaseModel


class Ticket(BaseModel):
    priority: str
    summary: str


if HAS_KEY:
    resp = client.responses.parse(model="gpt-4.1", input="Server down in prod, all customers affected.", text_format=Ticket)
    ticket = resp.output_parsed
    print(f"\n  Parsed: priority={ticket.priority!r}, summary={ticket.summary!r}")
    print(f"  Type: {type(ticket).__name__} — a real Ticket instance, not a dict you have to trust")
else:
    print("""
    resp = client.responses.parse(model="gpt-4.1",
                                    input="Server down in prod, all customers affected.",
                                    text_format=Ticket)
    print(resp.output_parsed)   # Ticket(priority='high', summary='...') — a real instance
    """)
    print("  [NO_API_KEY — .parse() + text_format guarantees the response matches")
    print("   the Pydantic schema, or raises, rather than hoping the model's JSON parses.]")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 5: Exercises
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("SECTION 5: EXERCISES")
print("=" * 70)
print("""
EASY:
1. Chain 3 turns instead of 2 in Section 2 — confirm the model remembers
   facts from turn 1 by turn 3.

MEDIUM:
2. Add a second tool to TOOLS (e.g. get_time(timezone)) and have the model
   choose between them based on the user's question.

HARD:
3. Add `stream=True` to Section 1's call and iterate the stream, printing
   only `response.output_text.delta` events — compare against Chat
   Completions' raw delta-chunk streaming from Level3.

PRO:
4. Extend Ticket with a nested Pydantic model (e.g. `affected_systems: list[str]`)
   and confirm responses.parse() still returns a fully-typed nested object,
   not just top-level fields.
""")

if __name__ == "__main__":
    print("\nDone. Next: 13_gemini_live_api_practical.py")
