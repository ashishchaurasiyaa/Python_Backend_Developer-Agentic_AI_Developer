"""
Modern Topics — Doc 13: Gemini Live API (PRACTICAL)
=======================================================
`google-genai` isn't required to understand the session/streaming mechanics
— this builds a mock async session with the same shape (connect, send,
receive-as-stream, tool_call handling) so the CONCEPTS run without a real
WebSocket connection or API key.

Topics covered:
  1. The session lifecycle — connect, send turns, receive a stream
  2. Turn-taking / VAD concept, simulated with an interruption scenario
  3. Function calling inside a live session
  4. Gemini Live vs OpenAI Realtime — a real comparison function, not just a table

Install (optional, real SDK): pip install google-genai
Run: python 13_gemini_live_api_practical.py
"""

import asyncio


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 1: The Session Lifecycle — Mock, Same Shape as the Real SDK
# ─────────────────────────────────────────────────────────────────────────────

print("=" * 70)
print("SECTION 1: Session Lifecycle")
print("=" * 70)


class MockLiveResponse:
    def __init__(self, text: str = None, tool_call=None):
        self.text = text
        self.data = None  # would be raw PCM bytes in a real AUDIO-modality session
        self.tool_call = tool_call


class MockLiveSession:
    """Same call shape as google-genai's `client.aio.live.connect()` session:
    send_client_content() to send a turn, receive() as an async stream of
    responses. No real WebSocket — this is entirely in-process."""

    def __init__(self, config: dict):
        self.config = config
        self._pending_turns = []

    async def send_client_content(self, turns: dict, turn_complete: bool = True):
        self._pending_turns.append(turns)

    async def receive(self):
        # Simulates the server streaming a response back token by token —
        # a real session would yield this from the actual model's output.
        last_turn = self._pending_turns[-1] if self._pending_turns else {}
        user_text = last_turn.get("parts", [{}])[0].get("text", "")
        canned_reply = f"[mock reply to: '{user_text}'] Quantum computing uses qubits, which can be 0 and 1 at once."
        for chunk in canned_reply.split(" "):
            yield MockLiveResponse(text=chunk + " ")
            await asyncio.sleep(0)  # yield control, mirrors real async streaming


async def basic_session():
    config = {"response_modalities": ["TEXT"]}
    session = MockLiveSession(config)
    await session.send_client_content(turns={"role": "user", "parts": [{"text": "Explain quantum computing in 2 lines"}]}, turn_complete=True)
    print()
    async for response in session.receive():
        if response.text:
            print(response.text, end="", flush=True)
    print()


asyncio.run(basic_session())
print("\n  Real code (google-genai installed): identical shape —")
print("""
    async with client.aio.live.connect(model=MODEL, config=config) as session:
        await session.send_client_content(turns={...}, turn_complete=True)
        async for response in session.receive():
            if response.text: print(response.text, end="", flush=True)
""")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 2: Turn-Taking / VAD — Simulating an Interruption
# ─────────────────────────────────────────────────────────────────────────────

print("=" * 70)
print("SECTION 2: Barge-In (Interruption) Concept")
print("=" * 70)


async def simulate_barge_in():
    """The doc's point: server-side VAD detects when the user starts talking
    WHILE the model is still producing output, and cancels the in-flight
    response. This simulates that cancellation with an asyncio.Event."""
    user_interrupted = asyncio.Event()

    async def model_speaking():
        words = ["The", "answer", "to", "your", "question", "is", "quite", "long", "and", "detailed..."]
        for w in words:
            if user_interrupted.is_set():
                print(f"\n  [MODEL OUTPUT CANCELLED — barge-in detected]")
                return
            print(w, end=" ", flush=True)
            await asyncio.sleep(0.05)

    async def user_barges_in():
        await asyncio.sleep(0.15)  # user starts talking partway through the model's response
        user_interrupted.set()

    print()
    await asyncio.gather(model_speaking(), user_barges_in())


asyncio.run(simulate_barge_in())
print("\n  In a real session, this is entirely server-managed — you don't write")
print("  the VAD logic yourself, but your CLIENT code must handle a response")
print("  stream that can be truncated mid-turn, exactly like the cancellation above.")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 3: Function Calling in a Live Session
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("SECTION 3: Function Calling — Same Session, Now With Tools")
print("=" * 70)


class MockFunctionCall:
    def __init__(self, id: str, name: str, args: dict):
        self.id, self.name, self.args = id, name, args


class MockToolCall:
    def __init__(self, function_calls):
        self.function_calls = function_calls


def get_weather(city: str) -> dict:
    return {"temp_c": 34}


async def function_calling_session():
    config = {
        "response_modalities": ["TEXT"],
        "tools": [{"function_declarations": [{"name": "get_weather", "description": "city weather", "parameters": {"type": "object", "properties": {"city": {"type": "string"}}}}]}],
    }
    session = MockLiveSession(config)
    await session.send_client_content(turns={"role": "user", "parts": [{"text": "What's the weather in Delhi?"}]}, turn_complete=True)

    # Simulate the server deciding to call the tool instead of answering directly
    fake_response = MockLiveResponse(tool_call=MockToolCall([MockFunctionCall(id="call_1", name="get_weather", args={"city": "Delhi"})]))
    if fake_response.tool_call:
        for fc in fake_response.tool_call.function_calls:
            result = get_weather(**fc.args)
            print(f"\n  Model requested: {fc.name}({fc.args})")
            print(f"  Sending back via session.send_tool_response(...): {result}")


asyncio.run(function_calling_session())


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 4: Gemini Live vs OpenAI Realtime — a Real Decision Function
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("SECTION 4: Which Live API for Your Use Case?")
print("=" * 70)


def pick_live_api(needs_video_input: bool, needs_google_search_grounding: bool, primarily_voice_only: bool) -> str:
    if needs_video_input:
        return "Gemini Live — native video/screen frame streaming, OpenAI Realtime is audio+text-focused"
    if needs_google_search_grounding:
        return "Gemini Live — built-in Google Search grounding as a live-session tool"
    if primarily_voice_only:
        return "Either works — OpenAI Realtime if already in the OpenAI ecosystem, Gemini Live otherwise"
    return "Gemini Live for multimodal (voice+vision), OpenAI Realtime for voice-first"


for case in [(True, False, False), (False, True, False), (False, False, True)]:
    print(f"\n  needs_video={case[0]}, needs_search_grounding={case[1]}, voice_only={case[2]}")
    print(f"    -> {pick_live_api(*case)}")

print("\n  Note: Anthropic has no direct real-time bidi audio API yet — Claude")
print("  voice is typically an STT -> Claude -> TTS pipeline (see 01_voice_agents.md),")
print("  which is a real, relevant trade-off if Claude is your primary model elsewhere.")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 5: Exercises
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("SECTION 5: EXERCISES")
print("=" * 70)
print("""
EASY:
1. Change MockLiveSession's canned reply logic to actually vary based on
   the user_text content (simple keyword matching is fine).

MEDIUM:
2. Add an AUDIO response_modality path to MockLiveSession — response.data
   should contain fake PCM bytes instead of text, mirroring Section 5 of
   the theory doc.

HARD:
3. If you have `google-genai` installed and an API key: run Section 1's
   REAL version against `gemini-2.0-flash-live-001` and compare the actual
   streaming cadence to this mock's simulated one.

PRO:
4. Extend simulate_barge_in() so the model, upon cancellation, generates a
   SHORT acknowledgment ("Sorry, go ahead") before yielding to the user —
   this is closer to what a real voice agent needs to feel natural, not
   just abrupt silence.
""")

if __name__ == "__main__":
    print("\nDone. Next: 18_model_training_internals_practical.py")
