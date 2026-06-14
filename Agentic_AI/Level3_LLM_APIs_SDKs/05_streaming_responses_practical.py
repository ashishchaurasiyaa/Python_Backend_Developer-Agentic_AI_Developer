"""
============================================================
Level 3.5 — Streaming LLM Responses : Complete Practical Lab
============================================================

KYA SEEKHENGE (What we will learn):
  1. Streaming kya hota hai aur kyun zaroori hai production mein
  2. Sync streaming — token-by-token print karna (OpenAI-compat via Groq)
  3. TTFT (Time To First Token) measure karna
  4. Fake / simulated streaming — bina key ke bhi demo chalana
  5. SSE (Server-Sent Events) format — browser ke liye token packaging
  6. Backpressure concept — bounded buffer pattern
  7. Tool-calls streaming — chunks accumulate karke final call banana
  8. Token counting during stream — real-time cost estimate
  9. Async streaming pattern — asyncio ke saath
 10. Production pitfalls — nginx, cancellation, keepalive

KAISE CHALANA (How to run):
  # Bina key ke (offline demo, EXIT 0 guarantee):
  uv run /Users/youngmanindia/Documents/PythonRevision/Agentic_AI/Level3_LLM_APIs_SDKs/05_streaming_responses_practical.py

  # Groq key ke saath (real streaming):
  GROQ_API_KEY=gsk_... uv run <same file>

THEORY REFERENCE:
  ../Level3_LLM_APIs_SDKs/05_streaming_responses.md
============================================================
"""

import asyncio
import json
import os
import sys
import time
from collections import deque
from typing import Generator, Iterator

# ─────────────────────────────────────────────────────────────────────────────
# GROQ_API_KEY check — graceful degradation
# OpenAI() bina key ke None dene se crash karta hai, isliye "placeholder" dete hain
# ─────────────────────────────────────────────────────────────────────────────
GROQ_API_KEY = os.getenv("GROQ_API_KEY") or "placeholder"
LIVE_MODE = os.getenv("GROQ_API_KEY") is not None

if not LIVE_MODE:
    print("[INFO] GROQ_API_KEY nahi mili — OFFLINE/DEMO mode chalega. EXIT 0 milega.")
    print("[INFO] Real streaming ke liye: export GROQ_API_KEY=gsk_...\n")


# ─────────────────────────────────────────────────────────────────────────────
# get_client() — Groq ko OpenAI-compatible endpoint se use karte hain
# Theory: "Multi-Provider Abstraction" section
# ─────────────────────────────────────────────────────────────────────────────
def get_client():
    """
    Groq ka free tier use karta hai via OpenAI-compatible API.
    api_key=None se OpenAI() crash karta hai, isliye 'placeholder' fallback hai.
    Offline mode mein client banta hai but koi API call nahi hoti.
    """
    from openai import OpenAI  # openai package project env mein available hai

    client = OpenAI(
        base_url="https://api.groq.com/openai/v1",
        api_key=GROQ_API_KEY,  # "placeholder" if no key
    )
    return client


# Default model for Groq free tier
GROQ_MODEL = "llama-3.1-8b-instant"

# ─────────────────────────────────────────────────────────────────────────────
# SECTION 1: Streaming kya hai — concept demo
# Theory: "Why Streaming Is Non-Negotiable"
# ─────────────────────────────────────────────────────────────────────────────

print("=" * 62)
print("SECTION 1: Streaming vs Non-Streaming — Concept")
print("=" * 62)

# Without streaming: pura response aane ka wait karo
WITHOUT_STREAMING = """
Without Streaming (Blocking):
  User  → "Generate karo"
  App   → 8-15 seconds wait (LLM poora response banata hai)
  User  → blank screen dekh ke bore ho gaya → page band kiya

With Streaming (Non-Blocking):
  User  → "Generate karo"
  App   → pehla token 300ms mein → tokens flow karte hain
  User  → response banta dekh raha hai → engaged → ruka

Result:
  3-5x kam perceived latency
  Users abandon nahi karte
  Early cancel se cost bachti hai
  "Magical" UX — ye LLM standard hai
"""
print(WITHOUT_STREAMING)

# Key metrics jo production mein track karte hain
STREAMING_METRICS = {
    "TTFT":       "Time To First Token — user-visible metric, < 500ms target",
    "Throughput": "Tokens per second — stream rate",
    "P99 TTC":    "99th percentile Time-To-Completion",
    "Error Rate":  "Stream failures / total requests",
}
print("  Production Metrics:")
for k, v in STREAMING_METRICS.items():
    print(f"    {k:<14}: {v}")

# ─────────────────────────────────────────────────────────────────────────────
# SECTION 2: Fake streaming — key nahi hai toh bhi demo chalega
# Theory basis: chunk-by-chunk delivery simulate karna
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 62)
print("SECTION 2: Simulated Streaming (Offline Demo)")
print("=" * 62)


def fake_stream(text: str, chunk_size: int = 3, delay: float = 0.03) -> Generator[str, None, None]:
    """
    OFFLINE DEMO ke liye fake token stream.
    Real streaming mein LLM server se chunks aate hain,
    yahan hum khud text ko chunks mein todke yield karte hain.

    Theory: "Chunk = a small piece of the response (1-N tokens)"
    chunk_size: kitne chars ek chunk mein (real LLM = 1-4 tokens typically)
    delay: simulate karta hai network latency
    """
    words = text.split()
    buffer = ""
    for word in words:
        buffer += word + " "
        if len(buffer) >= chunk_size:
            yield buffer
            buffer = ""
            time.sleep(delay)  # network latency simulate kar raha hai
    if buffer:
        yield buffer  # remaining text


def print_stream(stream: Iterator[str], label: str = "LLM") -> str:
    """
    Stream ko print karta hai — end="" flush=True pattern.
    Theory: "print(delta, end='', flush=True)" — yahi production pattern hai.
    Returns: complete accumulated text
    """
    print(f"\n  [{label}] Streaming...")
    print("  ", end="")
    full_text = ""
    start = time.perf_counter()
    first_token_time = None

    for chunk in stream:
        if first_token_time is None:
            first_token_time = time.perf_counter() - start  # TTFT measure kiya!
        print(chunk, end="", flush=True)
        full_text += chunk

    elapsed = time.perf_counter() - start
    print()  # newline after stream
    print(f"  [TTFT: {first_token_time*1000:.0f}ms | Total: {elapsed*1000:.0f}ms]")
    return full_text


# Fake stream demo
DEMO_TEXT = (
    "Streaming LLM responses mein server tokens ek-ek karke bhejta hai. "
    "Pehla token bahut jaldi aata hai — yahi TTFT hai. "
    "User ko blank screen nahi dekhna padta — response banta dikh ta hai. "
    "Ye production LLM ka standard UX pattern hai."
)

result = print_stream(fake_stream(DEMO_TEXT), label="Fake-Stream")
print(f"  [Total chars received: {len(result)}]")

# ─────────────────────────────────────────────────────────────────────────────
# SECTION 3: Real sync streaming via Groq (OpenAI-compatible)
# Theory: "OpenAI" section — stream=True pattern
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 62)
print("SECTION 3: Real Sync Streaming (Groq / OpenAI-compat)")
print("=" * 62)

SYNC_STREAM_CODE = '''\
# OpenAI-compatible streaming — Groq ke liye same pattern
client = get_client()

stream = client.chat.completions.create(
    model=GROQ_MODEL,
    messages=[{"role": "user", "content": "Python mein async kya hai?"}],
    stream=True,                         # <-- yahi streaming ON karta hai
)

# Chunk-by-chunk iterate karo
for chunk in stream:
    delta = chunk.choices[0].delta.content   # ek chunk ka text
    if delta:                                  # empty chunks ko skip karo
        print(delta, end="", flush=True)      # flush=True — buffer mat rakho!
'''
print("  Code pattern:")
print(SYNC_STREAM_CODE)

if LIVE_MODE:
    print("  [LIVE] Real Groq streaming chal raha hai...")
    try:
        client = get_client()
        stream = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[{"role": "user", "content": "Python streaming kya hai? 2 line mein batao."}],
            stream=True,
            max_tokens=80,
        )
        print("\n  ", end="")
        start_t = time.perf_counter()
        ttft = None
        full = ""
        for chunk in stream:
            delta = chunk.choices[0].delta.content
            if delta:
                if ttft is None:
                    ttft = time.perf_counter() - start_t
                print(delta, end="", flush=True)
                full += delta
        elapsed_t = time.perf_counter() - start_t
        print()
        print(f"  [TTFT: {ttft*1000:.0f}ms | Total: {elapsed_t*1000:.0f}ms | Chars: {len(full)}]")
    except Exception as e:
        print(f"  [ERROR] Groq API call fail hua: {e}")
        print("  [FALLBACK] Fake stream se continue karte hain...")
        print_stream(fake_stream("Python streaming mein server tokens ek-ek karke bhejta hai."), "Fallback")
else:
    print("  [SKIP] GROQ_API_KEY nahi hai — fake stream se demo:")
    print_stream(
        fake_stream("Python streaming mein OpenAI client ka stream=True flag use hota hai."),
        "Demo",
    )

# ─────────────────────────────────────────────────────────────────────────────
# SECTION 4: SSE (Server-Sent Events) Format
# Theory: "SSE format: data: <json>\n\n"
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 62)
print("SECTION 4: SSE Format — Browser ke Liye Token Packaging")
print("=" * 62)

SSE_EXPLANATION = """
SSE vs WebSocket — interview question:
  SSE  = HTTP-based, unidirectional (server → client), auto-reconnect,
         standard fetch() API, proxy-friendly — LLM streaming ke liye PERFECT
  WS   = bidirectional, heavier — LLM streaming ke liye overkill hai

SSE Format (har chunk aisa dikhta hai):
  data: {"token": "Python "}\\n\\n
  data: {"token": "mein "}\\n\\n
  data: {"done": true}\\n\\n
"""
print(SSE_EXPLANATION)


def token_to_sse(token: str) -> str:
    """
    Ek token ko SSE format mein convert karta hai.
    Theory: 'data: {json}\\n\\n' — yahi FastAPI StreamingResponse ko yield karta hai.
    """
    return f"data: {json.dumps({'token': token})}\n\n"


def stream_done_sse() -> str:
    """Stream khatam hone ka SSE signal."""
    return f"data: {json.dumps({'done': True})}\n\n"


def stream_error_sse(err: str) -> str:
    """Error ko SSE mein wrap karna — client ko pata chale."""
    return f"data: {json.dumps({'error': str(err)})}\n\n"


# Demo: fake stream ko SSE format mein convert karo
print("  SSE Packet Demo (fake stream → SSE format):")
demo_tokens = ["Python ", "streaming ", "bahut ", "fast ", "hoti ", "hai!"]
for tok in demo_tokens[:4]:  # pehle 4 tokens hi print karenge
    sse_packet = token_to_sse(tok)
    print(f"    {repr(sse_packet)}")
print(f"    {repr(stream_done_sse())}")

# FastAPI pattern ka code show karo
FASTAPI_CODE = '''\
# FastAPI Production Pattern (code reference):
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse
from openai import AsyncOpenAI
import json

app = FastAPI()
client = AsyncOpenAI()

async def stream_llm(prompt: str, request: Request):
    """Tokens SSE format mein yield karta hai. Disconnection bhi handle karta hai."""
    try:
        stream = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            stream=True,
        )
        async for chunk in stream:
            if await request.is_disconnected():   # user ne tab band kiya!
                await stream.close()               # billing band karo!
                break
            delta = chunk.choices[0].delta.content
            if delta:
                yield f"data: {json.dumps({"token": delta})}\\n\\n"
        yield f"data: {json.dumps({"done": True})}\\n\\n"
    except Exception as e:
        yield f"data: {json.dumps({"error": str(e)})}\\n\\n"

@app.post("/api/chat/stream")
async def chat_stream(payload: dict, request: Request):
    return StreamingResponse(
        stream_llm(payload["prompt"], request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # nginx buffering band karo!
        },
    )
'''
print("\n  FastAPI streaming endpoint reference:")
print(FASTAPI_CODE)

# ─────────────────────────────────────────────────────────────────────────────
# SECTION 5: TTFT Measurement
# Theory: "TTFT = Time To First Token (perceived latency, the metric that matters)"
# ─────────────────────────────────────────────────────────────────────────────

print("=" * 62)
print("SECTION 5: TTFT — Time To First Token Measurement")
print("=" * 62)


def measure_ttft_stream(stream: Iterator[str]) -> dict:
    """
    Stream karte waqt TTFT measure karta hai.
    TTFT = start se pehle non-empty chunk aane tak ka time.
    Theory: "TTFT is the user-visible metric — keep < 500ms for good UX."
    """
    start = time.perf_counter()
    ttft_ms = None
    tokens = []
    token_count = 0

    for chunk in stream:
        if ttft_ms is None and chunk.strip():
            ttft_ms = (time.perf_counter() - start) * 1000  # milliseconds
        tokens.append(chunk)
        token_count += 1  # rough token count (chars/4 ~ tokens)
        print(chunk, end="", flush=True)

    total_ms = (time.perf_counter() - start) * 1000
    full_text = "".join(tokens)

    print()
    return {
        "ttft_ms": round(ttft_ms or 0, 1),
        "total_ms": round(total_ms, 1),
        "total_chars": len(full_text),
        "approx_tokens": len(full_text) // 4,  # rough estimate
        "ttft_ok": (ttft_ms or 9999) < 500,   # < 500ms = good UX
    }


print("  Measuring TTFT on simulated stream:")
print("  ", end="")
# Simulated stream with different delay to demo TTFT
metrics = measure_ttft_stream(
    fake_stream("TTFT measurement example streaming tokens one by one.", delay=0.02)
)
print(f"\n  TTFT Metrics: {metrics}")
status = "GOOD (< 500ms)" if metrics["ttft_ok"] else "SLOW (> 500ms)"
print(f"  TTFT Status: {status}")

# ─────────────────────────────────────────────────────────────────────────────
# SECTION 6: Backpressure — Bounded Buffer Pattern
# Theory: "Backpressure = client can't keep up with stream rate"
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 62)
print("SECTION 6: Backpressure — Bounded Buffer Pattern")
print("=" * 62)

BACKPRESSURE_EXPLANATION = """
Problem: Producer (LLM server) fast hai, consumer (UI/DB write) slow hai
  → Buffer badh jaata hai → Memory leak!

Solution: deque(maxlen=N) — bounded buffer
  → Jab buffer full ho jaaye → purane tokens drop ho jaate hain
  → Producer rok nahi sakta consumer ko, but memory bounded rehti hai

Theory pattern:
  class BoundedStream:
      buffer = deque(maxlen=100)  # max 100 chunks buffer
      → Slow consumer ke liye safe
      → Producer kabhi block nahi hota
"""
print(BACKPRESSURE_EXPLANATION)


class BoundedStreamDemo:
    """
    Bounded buffer pattern ka synchronous demo.
    Theory mein async version hai — yahan concept same hai sync mein.
    deque(maxlen=N) = automatic bounded buffer, thread-safe read/write.
    """

    def __init__(self, max_buffer: int = 5):
        # maxlen se automatically purana data drop hota hai jab full ho
        self.buffer: deque = deque(maxlen=max_buffer)
        self.max_buffer = max_buffer
        self.dropped = 0

    def produce(self, chunk: str) -> bool:
        """
        Producer: naya chunk buffer mein daalo.
        Agar buffer full hai toh deque automatically oldest drop karta hai.
        Returns True if buffer was at capacity (drop happened).
        """
        was_full = len(self.buffer) == self.max_buffer
        self.buffer.append(chunk)
        if was_full:
            self.dropped += 1
        return was_full

    def consume(self) -> str | None:
        """Consumer: buffer se ek chunk nikalo."""
        if self.buffer:
            return self.buffer.popleft()
        return None

    def stats(self) -> dict:
        return {
            "buffer_size": len(self.buffer),
            "max_buffer": self.max_buffer,
            "dropped_chunks": self.dropped,
        }


# Demo: fast producer, slow consumer
print("  Bounded Buffer Demo (maxlen=5, 12 chunks produce karenge):")
bsd = BoundedStreamDemo(max_buffer=5)

# Produce 12 chunks — buffer 5 se zyada nahi rakhega
tokens_to_produce = ["tok1", "tok2", "tok3", "tok4", "tok5",
                     "tok6", "tok7", "tok8", "tok9", "tok10", "tok11", "tok12"]

for tok in tokens_to_produce:
    dropped = bsd.produce(tok)
    status_flag = " [DROP oldest]" if dropped else ""
    print(f"    Produced: {tok:<6} | Buffer: {list(bsd.buffer)}{status_flag}")

print(f"\n  Final stats: {bsd.stats()}")
print("  Note: buffer kabhi 5 se zyada nahi hua — memory safe rahi!")

# ─────────────────────────────────────────────────────────────────────────────
# SECTION 7: Tool Calls Streaming — Chunks Accumulate Karte Hain
# Theory: "Tool calls arrive in chunks too — must accumulate"
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 62)
print("SECTION 7: Tool Calls in Streaming — Accumulation Pattern")
print("=" * 62)

TOOL_CALL_EXPLANATION = """
Problem: Tool calls bhi chunks mein aate hain — ek chunk mein poora JSON nahi hota!
  chunk 1: {"name": "get_we"}
  chunk 2: {"name": "ather", "args": '{"ci'}
  chunk 3: {"args": 'ty": "Mumb'}
  chunk 4: {"args": 'ai"}'}

Solution: Dictionary mein accumulate karo, stream khatam hone ke baad parse karo.
  tool_calls_buffer[idx]["name"] += chunk.function.name
  tool_calls_buffer[idx]["arguments"] += chunk.function.arguments
"""
print(TOOL_CALL_EXPLANATION)

# Simulate chunked tool call arrival
TOOL_CALL_CHUNKS = [
    # (index, id, name_chunk, args_chunk)
    (0, "call_abc123", "get_weather", ""),
    (0, "",            "",            '{"city": "Mum'),
    (0, "",            "",            'bai", "unit":'),
    (0, "",            "",            ' "celsius"}'),
    (1, "call_def456", "search_",    ""),
    (1, "",            "web",         '{"query": "Python str'),
    (1, "",            "",            'eaming"}'),
]


def accumulate_tool_calls(chunks: list) -> dict:
    """
    Streaming tool call chunks ko accumulate karta hai.
    Theory: "Streaming with Tool Calls" section ka direct implementation.
    """
    tool_calls_buffer: dict = {}

    for idx, tc_id, name_chunk, args_chunk in chunks:
        if idx not in tool_calls_buffer:
            tool_calls_buffer[idx] = {"id": "", "name": "", "arguments": ""}

        if tc_id:
            tool_calls_buffer[idx]["id"] += tc_id
        if name_chunk:
            tool_calls_buffer[idx]["name"] += name_chunk
        if args_chunk:
            tool_calls_buffer[idx]["arguments"] += args_chunk

    return tool_calls_buffer


accumulated = accumulate_tool_calls(TOOL_CALL_CHUNKS)

print("  Accumulation result:")
for idx, tc in accumulated.items():
    try:
        parsed_args = json.loads(tc["arguments"])
    except json.JSONDecodeError:
        parsed_args = f"[JSON incomplete: {tc['arguments']!r}]"
    print(f"    Tool {idx}: id={tc['id']}, name={tc['name']}, args={parsed_args}")

TOOL_CALL_CODE = '''\
# Production tool call accumulation:
tool_calls_buffer = {}

for chunk in stream:
    if chunk.choices[0].delta.tool_calls:
        for tc in chunk.choices[0].delta.tool_calls:
            idx = tc.index
            if idx not in tool_calls_buffer:
                tool_calls_buffer[idx] = {"id": "", "name": "", "arguments": ""}
            if tc.function.name:
                tool_calls_buffer[idx]["name"] += tc.function.name
            if tc.function.arguments:
                tool_calls_buffer[idx]["arguments"] += tc.function.arguments

# Stream khatam hone ke baad parse karo
for idx, tc in tool_calls_buffer.items():
    args = json.loads(tc["arguments"])
    result = execute_tool(tc["name"], args)
'''
print(f"\n  Code Reference:\n{TOOL_CALL_CODE}")

# ─────────────────────────────────────────────────────────────────────────────
# SECTION 8: Token Counting During Stream — Real-Time Cost View
# Theory: "Token Counting + Cost During Stream"
# ─────────────────────────────────────────────────────────────────────────────

print("=" * 62)
print("SECTION 8: Token Counting During Stream")
print("=" * 62)

TOKEN_COUNT_EXPLANATION = """
Problem: OpenAI/Groq usage stats stream ke baad aate hain — real-time nahi
Solution 1: stream_options={"include_usage": True} — final chunk mein usage aata hai
Solution 2: Rough estimate — chars / 4 ~ tokens (English ke liye)
            Accurate ke liye: tiktoken library use karo

Cost formula:
  Input cost  = prompt_tokens  * (price_per_million / 1_000_000)
  Output cost = output_tokens  * (price_per_million / 1_000_000)
"""
print(TOKEN_COUNT_EXPLANATION)


def rough_token_count(text: str) -> int:
    """
    Rough token estimate — chars / 4 ~ tokens (English ke liye).
    Theory: "estimate while streaming" pattern.
    Accurate ke liye tiktoken use karo jo is project mein installed nahi hai.
    """
    return max(1, len(text) // 4)


def stream_with_cost_tracking(
    stream: Iterator[str],
    input_tokens: int = 20,  # prompt tokens (known before streaming)
    price_per_million_input: float = 0.10,   # Groq llama3 ~ $0.10/M
    price_per_million_output: float = 0.10,  # Groq llama3 ~ $0.10/M
) -> dict:
    """
    Stream karte waqt real-time token count aur cost estimate karta hai.
    Theory: "Token counting in stream = real-time cost view" — Senior Mantra #8
    """
    output_chars = 0
    full_text = ""

    print("  Streaming with cost tracking:")
    print("  ", end="")

    for chunk in stream:
        print(chunk, end="", flush=True)
        full_text += chunk
        output_chars += len(chunk)

    print()

    output_tokens = rough_token_count(full_text)
    input_cost = input_tokens * price_per_million_input / 1_000_000
    output_cost = output_tokens * price_per_million_output / 1_000_000

    return {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "input_cost_usd": round(input_cost, 8),
        "output_cost_usd": round(output_cost, 8),
        "total_cost_usd": round(input_cost + output_cost, 8),
    }


# Demo with fake stream
cost_demo_text = (
    "Token counting streaming mein bahut important hai. "
    "Real-time cost tracking se budget control hota hai. "
    "Tiktoken se accurate count milta hai."
)

cost_info = stream_with_cost_tracking(
    fake_stream(cost_demo_text, delay=0.01),
    input_tokens=15,
)
print(f"\n  Cost Breakdown: {cost_info}")
print(f"  Total cost: ${cost_info['total_cost_usd']:.8f} USD")

# If live, also try real usage tracking
if LIVE_MODE:
    print("\n  [LIVE] stream_options usage tracking:")
    try:
        client = get_client()
        # Note: Groq might not support stream_options, so we handle gracefully
        stream = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[{"role": "user", "content": "1+1 kya hai?"}],
            stream=True,
            max_tokens=20,
        )
        print("  ", end="")
        last_usage = None
        for chunk in stream:
            delta = chunk.choices[0].delta.content
            if delta:
                print(delta, end="", flush=True)
            # Some providers send usage in last chunk
            if hasattr(chunk, "usage") and chunk.usage:
                last_usage = chunk.usage
        print()
        if last_usage:
            print(f"  [Usage from API] prompt={last_usage.prompt_tokens}, "
                  f"completion={last_usage.completion_tokens}")
        else:
            print("  [Note] Usage chunk nahi mila — provider-dependent feature hai")
    except Exception as e:
        print(f"  [SKIP] Usage tracking error: {e}")

# ─────────────────────────────────────────────────────────────────────────────
# SECTION 9: Async Streaming Pattern
# Theory: "Async Variants" section
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 62)
print("SECTION 9: Async Streaming Pattern")
print("=" * 62)

ASYNC_CODE = '''\
# Async streaming — multiple concurrent streams ke liye
from openai import AsyncOpenAI
import asyncio

async def stream_async(prompt: str):
    """
    Async generator — multiple prompts concurrently stream kar sakte hain.
    asyncio.gather() se parallel streams possible hain.
    """
    client = AsyncOpenAI(
        base_url="https://api.groq.com/openai/v1",
        api_key=os.getenv("GROQ_API_KEY") or "placeholder",
    )
    stream = await client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[{"role": "user", "content": prompt}],
        stream=True,
    )
    async for chunk in stream:
        delta = chunk.choices[0].delta.content
        if delta:
            yield delta   # async generator — "async for" se consume karo

async def main():
    async for token in stream_async("Python async kya hai?"):
        print(token, end="", flush=True)
    print()

asyncio.run(main())
'''
print("  Async Streaming Code Reference:")
print(ASYNC_CODE)


# Runnable async demo (fake stream for offline safety)
async def fake_async_stream(text: str, delay: float = 0.02):
    """Async fake stream — asyncio-compatible generator."""
    words = text.split()
    for i, word in enumerate(words):
        await asyncio.sleep(delay)  # simulate async I/O wait
        yield word + " "


async def async_demo():
    """
    Async streaming demo chalata hai.
    Theory: async for chunk in stream — yahi production pattern hai.
    """
    print("  Async stream demo:")
    print("  ", end="")
    text = "Async streaming mein multiple requests parallel chal sakte hain."
    full = ""
    async for chunk in fake_async_stream(text, delay=0.015):
        print(chunk, end="", flush=True)
        full += chunk
    print()
    print(f"  [Async demo complete, chars={len(full)}]")


# Run async demo
asyncio.run(async_demo())

# ─────────────────────────────────────────────────────────────────────────────
# SECTION 10: Production Pitfalls
# Theory: "Edge Cases + Production Pitfalls" section
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 62)
print("SECTION 10: Production Pitfalls — Interview Ke Liye Yaad Karo")
print("=" * 62)

PITFALLS = [
    (
        "Nginx buffer karta hai by default",
        "X-Accel-Buffering: no header lagao ya nginx config mein: proxy_buffering off;",
    ),
    (
        "Browser fetch buffer karta hai bina Content-Type ke",
        'media_type="text/event-stream" set karo — browser real-time update karega',
    ),
    (
        "User disconnect kare toh server generate karta rehta hai",
        "request.is_disconnected() check karo loop mein, stream.close() call karo",
    ),
    (
        "Empty chunks UI crash karte hain",
        "if delta: check lagao — None/empty chunks filter karo",
    ),
    (
        "Long streams proxy timeout se toot jaati hain",
        "Keepalive: yield ': keepalive\\n\\n' every 30s — SSE comment format",
    ),
    (
        "Mobile networks streams drop karte hain",
        "Client-side reconnect implement karo last-event-id ke saath",
    ),
    (
        "Token counting bina tiktoken ke galat cost reports",
        "Tiktoken ya provider usage chunks use karo accurate counting ke liye",
    ),
    (
        "Tool call JSON ek chunk mein nahi aata",
        "tool_calls_buffer mein accumulate karo, stream khatam hone ke baad parse karo",
    ),
]

for i, (problem, solution) in enumerate(PITFALLS, 1):
    print(f"\n  {i}. PROBLEM: {problem}")
    print(f"     SOLUTION: {solution}")

# ─────────────────────────────────────────────────────────────────────────────
# SECTION 11: Interview Q&A
# Theory: "Interview Questions" section
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 62)
print("SECTION 11: Interview Q&A — Key Questions")
print("=" * 62)

QA = [
    (
        "Q: SSE vs WebSocket — LLM streaming ke liye kaunsa better hai?",
        "A: SSE! HTTP-based hai (proxy-friendly), unidirectional (server→client "
        "= LLM use case), auto-reconnect, standard fetch() API. WebSocket "
        "bidirectional + heavy — LLM ke liye overkill hai.",
    ),
    (
        "Q: Streaming quality kaise measure karte hain?",
        "A: TTFT (Time To First Token) — user-visible metric, < 500ms target. "
        "Token throughput (tokens/sec). P99 TTC (time-to-completion). "
        "Error rate. TTFT sabse important hai.",
    ),
    (
        "Q: User mid-stream disconnect kare toh kya hoga?",
        "A: Server generate karta rehega — paise waste! Solution: "
        "request.is_disconnected() check karo loop mein, stream.close() "
        "call karo. Billing stop hogi.",
    ),
    (
        "Q: Streaming aur non-streaming dono support kaise karein?",
        "A: Single endpoint with ?stream=true param. Non-streaming: "
        "saare chunks collect karo, JSON return karo. "
        "Streaming: StreamingResponse return karo.",
    ),
    (
        "Q: Concurrent streams efficiently kaise handle karein?",
        "A: AsyncOpenAI + asyncio ke saath shared httpx connection pool. "
        "asyncio.gather() se multiple parallel streams. "
        "High concurrency ke liye provider batch APIs.",
    ),
]

for q, a in QA:
    print(f"\n  {q}")
    print(f"  {a}")

# ─────────────────────────────────────────────────────────────────────────────
# SECTION 12: Senior Mantras — Production Ke 10 Rules
# Theory: "Senior Mantras" section
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 62)
print("SECTION 12: Senior Mantras — Production Rules")
print("=" * 62)

MANTRAS = [
    "HAMESHA stream karo user-facing LLM responses. Kabhi block mat karo.",
    "Disconnects handle karo — tumhara wallet depend karta hai iss par.",
    "SSE > WebSocket — one-way streaming ke liye.",
    "Proxy buffering disable karo (Nginx, Cloudflare).",
    "TTFT religiously track karo. Ye THE UX metric hai.",
    "tool_calls ko chunks mein accumulate karo — piecemeal aate hain.",
    "Keepalive heartbeat every 30s — long streams ke liye.",
    "Token counting stream mein = real-time cost view.",
    "Buffer bound rakho. Slow consumers producer ko crash nahi karte.",
    "Slow networks par test karo. 3G par streaming UX baith jaata hai.",
]

for i, mantra in enumerate(MANTRAS, 1):
    print(f"  {i:>2}. {mantra}")

# ─────────────────────────────────────────────────────────────────────────────
# SUMMARY
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 62)
print("SUMMARY — Kya Sikha:")
print("=" * 62)

SUMMARY_POINTS = {
    "Streaming":      "Token-by-token delivery — perceived latency 3-5x kam",
    "TTFT":           "Time To First Token — < 500ms = good UX",
    "SSE":            "HTTP-based, unidirectional, browser-friendly format",
    "Chunk pattern":  "for chunk in stream: if delta: print(delta, end='', flush=True)",
    "Backpressure":   "deque(maxlen=N) — slow consumer ke liye safe bounded buffer",
    "Tool calls":     "Chunks accumulate karo, end mein json.loads() karo",
    "Cost tracking":  "chars//4 rough estimate ya tiktoken ya provider usage",
    "Async":          "AsyncOpenAI + async for — concurrent streams possible",
    "Cancellation":   "is_disconnected() check karo, stream.close() pe billing ruk ti",
    "Nginx":          "X-Accel-Buffering: no — buffering disable karo",
}

for concept, explanation in SUMMARY_POINTS.items():
    print(f"  {concept:<18}: {explanation}")

print("\n" + "=" * 62)
print("Lab complete! Ab theory file padho:")
print("  05_streaming_responses.md")
print("=" * 62)

# Explicit EXIT 0 — offline mode mein bhi guaranteed
sys.exit(0)
