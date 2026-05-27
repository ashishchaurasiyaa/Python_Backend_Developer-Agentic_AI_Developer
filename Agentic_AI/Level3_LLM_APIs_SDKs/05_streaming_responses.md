# Level 3.5 — Streaming LLM Responses Deep
**Phase: LLM APIs & SDKs | Production-Critical**

## Quick Concepts

- **Streaming** = receive tokens one-by-one as the model generates, vs waiting for the full response
- **SSE (Server-Sent Events)** = HTTP protocol for server → client push streams
- **Chunk** = a small piece of the response (1-N tokens) delivered incrementally
- **TTFT** = Time To First Token (perceived latency, the metric that matters)
- **Token-by-token** vs **chunked** delivery — small batches reduce overhead
- **Backpressure** = client can't keep up with stream rate
- **Cancellation** = user closes tab → stop generating + stop billing

---

## Why Streaming Is Non-Negotiable

```
Without streaming:
   User: clicks "Generate"
   App: waits 8-15 seconds (LLM generates entire response)
   User: stares at blank screen → bounces

With streaming:
   User: clicks "Generate"
   App: first token in 300ms → tokens flow continuously
   User: sees response forming → engaged → stays

Result:
   ✓ 3-5x lower perceived latency
   ✓ Higher engagement (users don't abandon)
   ✓ Can cancel early (saves cost)
   ✓ Looks "magical" (LLM UX standard)
```

**Every production LLM endpoint streams. Period.**

---

## Streaming Across Major Providers

### OpenAI

```python
from openai import OpenAI

client = OpenAI()

stream = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[{"role": "user", "content": "Write a haiku about TCP"}],
    stream=True,
)

for chunk in stream:
    delta = chunk.choices[0].delta.content
    if delta:
        print(delta, end="", flush=True)
```

### Anthropic Claude

```python
from anthropic import Anthropic

client = Anthropic()

with client.messages.stream(
    max_tokens=1024,
    messages=[{"role": "user", "content": "Hello"}],
    model="claude-3-7-sonnet-latest",
) as stream:
    for text in stream.text_stream:
        print(text, end="", flush=True)
```

### Async Variants

```python
# OpenAI async
from openai import AsyncOpenAI

async def stream_async():
    client = AsyncOpenAI()
    stream = await client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": "Hi"}],
        stream=True,
    )
    async for chunk in stream:
        if chunk.choices[0].delta.content:
            yield chunk.choices[0].delta.content
```

---

## FastAPI Streaming Endpoint (Production Pattern)

```python
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse
from openai import AsyncOpenAI
import asyncio
import json

app = FastAPI()
client = AsyncOpenAI()


async def stream_llm(prompt: str, request: Request):
    """Yields tokens with SSE formatting. Handles cancellation."""
    try:
        stream = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            stream=True,
        )

        async for chunk in stream:
            # User closed connection — stop generating
            if await request.is_disconnected():
                await stream.close()
                break

            delta = chunk.choices[0].delta.content
            if delta:
                # SSE format: "data: <json>\n\n"
                yield f"data: {json.dumps({'token': delta})}\n\n"

        yield f"data: {json.dumps({'done': True})}\n\n"

    except Exception as e:
        yield f"data: {json.dumps({'error': str(e)})}\n\n"


@app.post("/api/chat/stream")
async def chat_stream(payload: dict, request: Request):
    return StreamingResponse(
        stream_llm(payload["prompt"], request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # disable nginx buffering
        },
    )
```

### Browser Consumer (JS)

```javascript
const response = await fetch('/api/chat/stream', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ prompt: 'Hello' }),
});

const reader = response.body.getReader();
const decoder = new TextDecoder();

while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    const text = decoder.decode(value);
    // Parse SSE: "data: {json}\n\n"
    const lines = text.split('\n\n');
    for (const line of lines) {
        if (line.startsWith('data: ')) {
            const data = JSON.parse(line.slice(6));
            if (data.token) appendToUI(data.token);
        }
    }
}
```

---

## Backpressure Handling

```python
# If consumer is slow, buffer can grow → memory leak
# Solution: bounded queue + drop or block

import asyncio
from collections import deque


class BoundedStream:
    def __init__(self, max_buffer=100):
        self.buffer = deque(maxlen=max_buffer)
        self.event = asyncio.Event()
        self.done = False

    async def producer(self, stream):
        async for chunk in stream:
            self.buffer.append(chunk)
            self.event.set()
        self.done = True
        self.event.set()

    async def consumer(self):
        while not (self.done and not self.buffer):
            await self.event.wait()
            self.event.clear()
            while self.buffer:
                yield self.buffer.popleft()
```

---

## Token Counting + Cost During Stream

```python
# OpenAI doesn't send usage in stream chunks by default
# Need to set stream_options

stream = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[...],
    stream=True,
    stream_options={"include_usage": True},  # final chunk has usage
)

usage = None
async for chunk in stream:
    if chunk.usage:  # final chunk
        usage = chunk.usage
        print(f"Tokens: in={usage.prompt_tokens}, out={usage.completion_tokens}")
```

Or estimate while streaming:

```python
import tiktoken

enc = tiktoken.encoding_for_model("gpt-4o-mini")
output_tokens = 0

async for chunk in stream:
    delta = chunk.choices[0].delta.content or ""
    output_tokens += len(enc.encode(delta))
    yield delta
```

---

## Multi-Provider Abstraction

```python
# Provider-agnostic streaming interface

class StreamingLLM:
    async def stream(self, prompt: str):
        raise NotImplementedError


class OpenAIStream(StreamingLLM):
    async def stream(self, prompt):
        s = await self.client.chat.completions.create(
            model=self.model, messages=[{"role": "user", "content": prompt}],
            stream=True,
        )
        async for chunk in s:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content


class ClaudeStream(StreamingLLM):
    async def stream(self, prompt):
        async with self.client.messages.stream(
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
            model=self.model,
        ) as s:
            async for text in s.text_stream:
                yield text


# Usage
llm: StreamingLLM = OpenAIStream() if use_openai else ClaudeStream()
async for token in llm.stream("Hello"):
    print(token, end="")
```

---

## Edge Cases + Production Pitfalls

```
1. ✗ Nginx buffers streams by default
   → Set: proxy_buffering off;
   → Or: X-Accel-Buffering: no header

2. ✗ Browser fetch buffers when no Content-Type
   → Set: media_type="text/event-stream"

3. ✗ Client disconnects but server keeps generating
   → Check request.is_disconnected() in loop
   → Call stream.close() on cancellation

4. ✗ Empty chunks crash UI
   → Filter: if chunk.choices[0].delta.content

5. ✗ JSON in middle of chunks (rare with structured output)
   → Use stream-json parser, not naive split

6. ✗ Long-running streams hit proxy timeouts
   → Heartbeat: yield ": keepalive\n\n" every 30s

7. ✗ Mobile networks drop streams more
   → Implement client-side reconnect with last-event-id

8. ✗ Counting tokens without tiktoken = wrong cost reports
   → Always use proper tokenizer
```

---

## Streaming with Tool Calls

Tool calls arrive in chunks too — must accumulate:

```python
tool_calls_buffer = {}

async for chunk in stream:
    if chunk.choices[0].delta.tool_calls:
        for tc in chunk.choices[0].delta.tool_calls:
            idx = tc.index
            if idx not in tool_calls_buffer:
                tool_calls_buffer[idx] = {
                    "id": tc.id or "",
                    "name": "",
                    "arguments": "",
                }
            if tc.function.name:
                tool_calls_buffer[idx]["name"] += tc.function.name
            if tc.function.arguments:
                tool_calls_buffer[idx]["arguments"] += tc.function.arguments

# After stream ends — parse final tool_calls
for idx, tc in tool_calls_buffer.items():
    args = json.loads(tc["arguments"])
    result = execute_tool(tc["name"], args)
```

---

## Interview Questions

### Q1: Why use SSE over WebSockets for LLM streaming?

SSE is HTTP-based (works through proxies, simpler firewall rules), unidirectional (server → client which is all we need), auto-reconnects in browsers, and uses standard `fetch` API. WebSockets are bidirectional + heavier — overkill for one-way streaming.

### Q2: How do you measure streaming quality?

TTFT (Time To First Token), token throughput (tokens/sec), 99th percentile time-to-completion, error rate. TTFT is the user-visible metric — keep < 500ms for good UX.

### Q3: What happens if user disconnects mid-stream?

Without handling: server keeps generating (wasting compute + your money). Solution: check `request.is_disconnected()` in the stream loop, close LLM stream on disconnect to stop billing.

### Q4: How do you support both streaming and non-streaming clients?

Single endpoint with `?stream=true` param. Non-streaming: collect all chunks, return JSON. Streaming: return `StreamingResponse`. Some APIs prefer separate `/chat` and `/chat/stream` endpoints.

### Q5: How do you batch multiple concurrent streams efficiently?

Use async with shared httpx client + connection pool. For very high concurrency, consider provider-batched APIs (OpenAI Batch). For cost: route fast/cheap models for first response, expensive for follow-ups.

---

## Senior Mantras

```
1. ALWAYS stream user-facing LLM responses. Never block.

2. Handle disconnects — your wallet depends on it.

3. SSE > WebSocket for one-way streaming.

4. Disable proxy buffering (Nginx, Cloudflare).

5. Track TTFT religiously. It's THE UX metric.

6. Accumulate tool_calls across chunks — they arrive piecemeal.

7. Heartbeat keepalives every 30s for long streams.

8. Token counting in stream = real-time cost view.

9. Bound your buffers. Slow consumers don't crash producer.

10. Test on slow networks. Streaming UX falls apart on 3G.
```

---

## Related

- [07_error_handling_retries.md](07_error_handling_retries.md) — what to do when stream fails
- [10_cost_optimization.md](10_cost_optimization.md) — cost tracking during streams
- [../Level1_LLM_Foundations/](../Level1_LLM_Foundations/) — tokenization basics
- [../../Backend_Developer/Phase2_FastAPI/26_sse_deep.md](../../Backend_Developer/Phase2_FastAPI/26_sse_deep.md) — SSE infrastructure deep dive
- [../../Backend_Developer/Phase2_FastAPI/31_llm_integration_fastapi.md](../../Backend_Developer/Phase2_FastAPI/31_llm_integration_fastapi.md) — full FastAPI integration
