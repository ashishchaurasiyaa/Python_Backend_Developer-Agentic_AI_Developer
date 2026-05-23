"""
Phase4_Anthropic_Claude — Complete Practical
=============================================
Topics covered:
  1. Messages API: basic call, system prompt, multi-turn
  2. Streaming responses (async + sync)
  3. Tool use (function calling)
  4. Prompt caching (cache_control blocks)
  5. Extended thinking
  6. Batch API (async bulk)
  7. Cost estimation
  8. Error handling (rate limits, timeouts)
  9. Vision (image input)

Install: pip install anthropic
Env var: ANTHROPIC_API_KEY=sk-ant-...

Run:
  python 01_claude_practical.py
  → Works in MOCK MODE if API key not set
"""

import asyncio
import base64
import json
import os
import time
from typing import AsyncGenerator

# ─────────────────────────────────────────────────────────────────────────────
# Setup — Mock mode if no API key
# ─────────────────────────────────────────────────────────────────────────────

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
MOCK_MODE = not ANTHROPIC_API_KEY

if MOCK_MODE:
    print("⚠  MOCK MODE — set ANTHROPIC_API_KEY env var to run real API calls\n")

try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False
    print("anthropic not installed: pip install anthropic\n")


def mock_response(content: str, input_tokens: int = 100, output_tokens: int = 50):
    """Simulated Claude response for demo."""
    class MockUsage:
        def __init__(self): self.input_tokens = input_tokens; self.output_tokens = output_tokens
    class MockContent:
        def __init__(self, text): self.type = "text"; self.text = text
    class MockResponse:
        def __init__(self, text):
            self.content = [MockContent(text)]
            self.usage = MockUsage()
            self.stop_reason = "end_turn"
            self.model = "claude-sonnet-4-6"
    return MockResponse(content)


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 1: Basic Messages API
# INTERVIEW: model selection, system prompt, max_tokens
# ─────────────────────────────────────────────────────────────────────────────

print("=" * 60)
print("SECTION 1: Claude Messages API")
print("=" * 60)

# Model selection guide
MODELS = {
    "claude-haiku-4-5":    "Fastest, cheapest — simple tasks, high volume, classification",
    "claude-sonnet-4-6":   "RECOMMENDED — balanced speed/quality for most tasks",
    "claude-opus-4-7":     "Most capable — complex reasoning, research, analysis",
}
print("\n  Model Selection Guide:")
for model, desc in MODELS.items():
    print(f"  {model:<28}: {desc}")

def basic_claude_call():
    if MOCK_MODE or not ANTHROPIC_AVAILABLE:
        response = mock_response(
            "Async/await allows non-blocking I/O. "
            "async def defines a coroutine. "
            "await suspends coroutine until result is ready."
        )
    else:
        client = anthropic.Anthropic()
        response = client.messages.create(
            model      = "claude-sonnet-4-6",
            max_tokens = 256,
            system     = "You are a Python expert. Be concise.",
            messages   = [{"role": "user", "content": "Explain async/await in 3 sentences."}],
        )

    print(f"\n  Response: {response.content[0].text[:100]}...")
    print(f"  Tokens used: {response.usage.input_tokens} in, {response.usage.output_tokens} out")
    print(f"  Stop reason: {response.stop_reason}")
    return response

basic_claude_call()


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 2: Multi-turn Conversation
# INTERVIEW: messages array builds conversation history
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 60)
print("SECTION 2: Multi-turn Conversation")
print("=" * 60)

class ClaudeConversation:
    """
    INTERVIEW: Claude is STATELESS — no server-side memory.
    You must send full conversation history each time.
    Memory management: truncate old messages when context window fills.
    """

    def __init__(self, system: str = "", model: str = "claude-sonnet-4-6"):
        self.system   = system
        self.model    = model
        self.messages = []
        self.client   = anthropic.Anthropic() if ANTHROPIC_AVAILABLE else None

    def chat(self, user_message: str) -> str:
        self.messages.append({"role": "user", "content": user_message})

        if MOCK_MODE or not ANTHROPIC_AVAILABLE:
            reply = f"[Mock] Response to: '{user_message[:30]}...'"
        else:
            response = self.client.messages.create(
                model    = self.model,
                max_tokens = 512,
                system   = self.system,
                messages = self.messages,
            )
            reply = response.content[0].text

        self.messages.append({"role": "assistant", "content": reply})
        return reply

    def truncate_history(self, keep_last_n: int = 10):
        """INTERVIEW: Keep context window manageable — truncate old messages."""
        if len(self.messages) > keep_last_n * 2:
            self.messages = self.messages[-(keep_last_n * 2):]


conv = ClaudeConversation(system="You are a helpful Python tutor.")
print("\n  Conversation demo:")
for msg in ["What is a generator?", "Give me a simple example."]:
    reply = conv.chat(msg)
    print(f"  User: {msg}")
    print(f"  Claude: {reply[:80]}...")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 3: Streaming
# INTERVIEW: Token-by-token streaming for better UX
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 60)
print("SECTION 3: Streaming Response")
print("=" * 60)

STREAMING_CODE = '''\
# Sync streaming
with client.messages.stream(
    model="claude-sonnet-4-6",
    max_tokens=512,
    messages=[{"role": "user", "content": "Write a Python fibonacci function."}],
) as stream:
    for text in stream.text_stream:
        print(text, end="", flush=True)  # print each token as it arrives
    print()  # newline at end

    final = stream.get_final_message()
    print(f"Total tokens: {final.usage.input_tokens + final.usage.output_tokens}")

# Async streaming (FastAPI SSE)
async def stream_to_client(prompt: str) -> AsyncGenerator[str, None]:
    async with client.messages.stream(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    ) as stream:
        async for text in stream.text_stream:
            yield f"data: {text}\\n\\n"  # SSE format
        yield "data: [DONE]\\n\\n"

# FastAPI SSE endpoint
@app.get("/stream")
async def stream_endpoint(prompt: str):
    return StreamingResponse(
        stream_to_client(prompt),
        media_type="text/event-stream"
    )
'''
print("  Streaming code pattern:")
print(STREAMING_CODE[:400])

if not MOCK_MODE and ANTHROPIC_AVAILABLE:
    client = anthropic.Anthropic()
    print("\n  Live streaming demo:")
    with client.messages.stream(
        model="claude-sonnet-4-6",
        max_tokens=50,
        messages=[{"role": "user", "content": "Count to 5."}],
    ) as stream:
        print("  ", end="")
        for text in stream.text_stream:
            print(text, end="", flush=True)
        print()
else:
    print("\n  [Mock] Streaming: 1... 2... 3... 4... 5...")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 4: Tool Use (Function Calling)
# INTERVIEW: Claude decides when to call tools, you execute them
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 60)
print("SECTION 4: Tool Use (Function Calling)")
print("=" * 60)

TOOLS = [
    {
        "name": "get_weather",
        "description": "Get current weather for a city",
        "input_schema": {
            "type": "object",
            "properties": {
                "city":    {"type": "string", "description": "City name"},
                "units":   {"type": "string", "enum": ["celsius", "fahrenheit"]},
            },
            "required": ["city"],
        },
    },
    {
        "name": "calculate",
        "description": "Perform mathematical calculations",
        "input_schema": {
            "type": "object",
            "properties": {
                "expression": {"type": "string", "description": "Math expression"},
            },
            "required": ["expression"],
        },
    },
]


def execute_tool(tool_name: str, tool_input: dict) -> str:
    """Execute tool and return result."""
    if tool_name == "get_weather":
        city  = tool_input["city"]
        units = tool_input.get("units", "celsius")
        temp  = 22 if units == "celsius" else 72
        return json.dumps({"city": city, "temperature": temp, "condition": "sunny", "units": units})

    elif tool_name == "calculate":
        try:
            result = eval(tool_input["expression"], {"__builtins__": {}})
            return json.dumps({"result": result})
        except Exception as e:
            return json.dumps({"error": str(e)})

    return json.dumps({"error": f"Unknown tool: {tool_name}"})


def claude_with_tools(user_message: str) -> str:
    """
    INTERVIEW: Tool use flow:
    1. Send request with tools list
    2. Claude returns tool_use block (stop_reason = "tool_use")
    3. Execute the tool
    4. Send tool_result back to Claude
    5. Claude returns final text answer
    """
    if MOCK_MODE or not ANTHROPIC_AVAILABLE:
        print(f"  [Mock Tool] User: {user_message}")
        print(f"  [Mock Tool] Claude calls: get_weather(city='Mumbai')")
        print(f"  [Mock Tool] Tool result: temp=22°C, sunny")
        return "[Mock] It's currently 22°C and sunny in Mumbai."

    client   = anthropic.Anthropic()
    messages = [{"role": "user", "content": user_message}]

    # Step 1: Initial request
    response = client.messages.create(
        model      = "claude-sonnet-4-6",
        max_tokens = 1024,
        tools      = TOOLS,
        messages   = messages,
    )

    # Step 2: Handle tool calls
    while response.stop_reason == "tool_use":
        tool_results = []
        messages.append({"role": "assistant", "content": response.content})

        for block in response.content:
            if block.type == "tool_use":
                print(f"  Tool called: {block.name}({block.input})")
                result = execute_tool(block.name, block.input)
                tool_results.append({
                    "type":        "tool_result",
                    "tool_use_id": block.id,
                    "content":     result,
                })

        messages.append({"role": "user", "content": tool_results})

        # Step 3: Get final answer
        response = client.messages.create(
            model      = "claude-sonnet-4-6",
            max_tokens = 1024,
            tools      = TOOLS,
            messages   = messages,
        )

    return response.content[0].text


print("\n  Tool use demo:")
result = claude_with_tools("What's the weather in Mumbai? Also calculate 15 * 8 + 32.")
print(f"  Final answer: {result[:100]}...")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 5: Prompt Caching
# INTERVIEW: 90% cost reduction for repeated context (system prompts, docs)
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 60)
print("SECTION 5: Prompt Caching")
print("=" * 60)

PROMPT_CACHING_CODE = """\
# INTERVIEW: Prompt caching = cache large context blocks
# First call: full price (cache MISS)
# Subsequent calls: ~10% price for cached portion (cache HIT)
# Use for: long system prompts, reference docs, few-shot examples

response = client.messages.create(
    model="claude-sonnet-4-6",
    max_tokens=512,
    system=[
        {
            "type": "text",
            "text": "You are an expert Python developer...",
        },
        {
            "type": "text",
            "text": open("docs/api_reference.txt").read(),  # large doc
            "cache_control": {"type": "ephemeral"},   # ← CACHE THIS BLOCK
        },
    ],
    messages=[{"role": "user", "content": "How do I use the auth endpoint?"}],
)

# First call: cache_creation_input_tokens = full doc tokens (charged at 1.25x)
# Next calls: cache_read_input_tokens = same doc (charged at 0.1x = 90% cheaper!)
print(response.usage.cache_creation_input_tokens)  # tokens cached
print(response.usage.cache_read_input_tokens)       # tokens read from cache
"""
print(PROMPT_CACHING_CODE)

print("\n  Prompt Caching Benefits:")
benefits = {
    "Cost":     "90% reduction for cached tokens (cache_read = 0.1x price)",
    "Latency":  "Faster — cached tokens don't need re-encoding",
    "Use for":  "System prompts, docs, few-shot examples (min 1024 tokens to cache)",
    "TTL":      "5 minutes (ephemeral) — refresh before expiry for long sessions",
}
for k, v in benefits.items():
    print(f"  {k:<10}: {v}")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 6: Cost Estimation
# INTERVIEW: Pricing model, optimization strategies
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 60)
print("SECTION 6: Cost Estimation")
print("=" * 60)

# Approximate pricing (always check official docs for latest)
PRICING = {
    "claude-haiku-4-5":  {"input": 0.80,  "output": 4.00},   # per 1M tokens
    "claude-sonnet-4-6": {"input": 3.00,  "output": 15.00},
    "claude-opus-4-7":   {"input": 15.00, "output": 75.00},
}


def estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    pricing = PRICING.get(model, PRICING["claude-sonnet-4-6"])
    cost    = (input_tokens * pricing["input"] + output_tokens * pricing["output"]) / 1_000_000
    return cost


print("\n  Cost for 1000 API calls (500 in tokens, 200 out tokens each):")
for model in PRICING:
    cost = estimate_cost(model, 500 * 1000, 200 * 1000)
    print(f"  {model:<28}: ${cost:.2f}")

print("\n  Cost Optimization:")
tips = {
    "Use Haiku":            "For simple tasks (classification, routing) — 10x cheaper",
    "Prompt caching":       "90% reduction on cached system prompts",
    "Batch API":            "50% cheaper, async processing",
    "Shorter prompts":      "Every token costs — remove redundant instructions",
    "max_tokens":           "Set tight limit — don't request 4096 if you need 100",
}
for k, v in tips.items():
    print(f"  {k:<24}: {v}")

print("\n" + "=" * 60)
print("INTERVIEW SUMMARY:")
print("  Claude API = stateless (send full history each time)")
print("  tool_use stop_reason → execute tool → send tool_result → final answer")
print("  Prompt caching → cache_control: ephemeral → 90% cheaper repeated context")
print("  Streaming → stream.text_stream (sync) / async for text in stream.text_stream")
print("=" * 60)
