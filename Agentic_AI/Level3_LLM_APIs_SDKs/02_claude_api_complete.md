# Anthropic Claude API — Messages, Tool Use, Streaming, Prompt Caching, Batch

## Quick Concepts
- **Messages API** = Claude ka primary API — stateless conversation
- **Tool use** = Claude functions call kar sakta hai (function calling)
- **Prompt caching** = repeated context 90% cheaper — `cache_control` blocks
- **Extended thinking** = complex reasoning — model apna "thought process" dikhata hai
- **Batch API** = async bulk processing — 50% cheaper, 24h processing

---

## Andar kya hota hai — Named SSE Events + Cache Kaise Match Hoti Hai

### Streaming — OpenAI se structurally alag hai

OpenAI ka stream sirf "delta chunks" ka flat sequence hai. Claude ka stream
**named events** hain — har event ka apna type + payload:

```
event: message_start        → {message: {id, model, ...}}
event: content_block_start  → {index: 0, content_block: {type: "text"}}
event: content_block_delta  → {index: 0, delta: {text: "Hello"}}
event: content_block_delta  → {index: 0, delta: {text: " world"}}
event: content_block_stop   → {index: 0}
event: message_delta        → {delta: {stop_reason: "end_turn"}, usage: {...}}
event: message_stop
```

Client ko `event:` NAME pe dispatch karna hai, na ki sab kuch ek generic
"delta" maan lena. `thinking` aur `tool_use` content blocks bhi isi
start/delta/stop triplet pattern se aate hain — sirf `content_block.type`
alag hoga — matlab ek response mein MULTIPLE blocks stream ho sakte hain
(pehle `thinking`, phir `text`), har ek apna independent start/stop pair.

### Prompt caching — PREFIX-exact match hai, semantic-similarity NAHI

```python
messages=[
    {"role": "user", "content": [
        {"type": "text", "text": huge_context, "cache_control": {"type": "ephemeral"}},
        {"type": "text", "text": actual_question}
    ]}
]
```

`cache_control` marker jahan lagaya, Anthropic us POINT TAK ke poore prefix
(token sequence) ko cache karta hai — internally ek hash us exact token
sequence ka. Agle request ka prefix EXACTLY wahi (same breakpoint tak) ho to
cache-HIT (90% cheaper, faster TTFT) — ek bhi token pehle change hua (system
prompt me typo fix bhi) to poora cache-MISS, koi partial-credit nahi milta.
Cache ~5 min TTL rakhta hai, har cache-hit pe TTL refresh hota hai — isiliye
high-frequency reuse pattern (chatbot with long system prompt) mein genuinely
kaam karta hai, one-off calls mein nahi.

### Extended thinking — ek ALAG content block hai, hidden magic nahi

`thinking` block normal content block ki tarah hi stream hota hai (apna
start/delta/stop) — final answer se PEHLE aata hai, alag block index pe.
Thinking tokens BILL hote hain aur context budget mein count hote hain — yeh
free-hidden-reasoning nahi hai, ek visible+billed extra generation step hai.

---

## Interview Questions & Answers

### Q1: Claude Messages API basic usage aur model selection?
**Answer:**
```python
import anthropic

client = anthropic.Anthropic()  # ANTHROPIC_API_KEY env var se

# Model selection guide:
# claude-haiku-4-5-20251001  → fastest, cheapest — simple tasks, high volume
# claude-sonnet-4-6          → balanced — most tasks (RECOMMENDED default)
# claude-opus-4-7            → most capable — complex reasoning, research

# Basic call
response = client.messages.create(
    model="claude-sonnet-4-6",
    max_tokens=1024,
    system="You are a helpful Python expert.",
    messages=[
        {"role": "user", "content": "Explain async/await in 3 sentences."}
    ]
)

print(response.content[0].text)
print(f"Input tokens: {response.usage.input_tokens}")
print(f"Output tokens: {response.usage.output_tokens}")
print(f"Stop reason: {response.stop_reason}")  # end_turn, max_tokens, tool_use

# Multi-turn conversation
messages = []

def chat(user_message: str) -> str:
    messages.append({"role": "user", "content": user_message})

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        system="You are a Python tutor.",
        messages=messages
    )

    assistant_reply = response.content[0].text
    messages.append({"role": "assistant", "content": assistant_reply})
    return assistant_reply

# Async version
import anthropic

async_client = anthropic.AsyncAnthropic()

async def async_chat(message: str) -> str:
    response = await async_client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        messages=[{"role": "user", "content": message}]
    )
    return response.content[0].text
```

---

### Q2: Tool Use (Function Calling) kaise kaam karta hai?
**Answer:**
```python
import anthropic
import json

client = anthropic.Anthropic()

# Tool definitions
tools = [
    {
        "name": "get_weather",
        "description": "Get current weather for a city",
        "input_schema": {
            "type": "object",
            "properties": {
                "city": {
                    "type": "string",
                    "description": "City name, e.g. 'Mumbai'"
                },
                "unit": {
                    "type": "string",
                    "enum": ["celsius", "fahrenheit"],
                    "description": "Temperature unit"
                }
            },
            "required": ["city"]
        }
    },
    {
        "name": "search_database",
        "description": "Search for user records in the database",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "limit": {"type": "integer", "default": 10}
            },
            "required": ["query"]
        }
    }
]

# Tool implementations
def get_weather(city: str, unit: str = "celsius") -> dict:
    # Real implementation mein weather API call karo
    return {"city": city, "temp": 28, "unit": unit, "condition": "Sunny"}

def search_database(query: str, limit: int = 10) -> list:
    # Real implementation mein DB query karo
    return [{"id": 1, "name": "Ashish", "email": "ashish@test.com"}]

# Agentic loop — Claude tool call kare toh execute karo
def run_with_tools(user_message: str) -> str:
    messages = [{"role": "user", "content": user_message}]

    while True:
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1024,
            tools=tools,
            messages=messages,
        )

        # Tool use nahi — final answer
        if response.stop_reason == "end_turn":
            for block in response.content:
                if hasattr(block, "text"):
                    return block.text

        # Tool use requested
        if response.stop_reason == "tool_use":
            # Assistant message add karo
            messages.append({"role": "assistant", "content": response.content})

            # Tools execute karo
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    tool_name = block.name
                    tool_input = block.input

                    # Execute the tool
                    if tool_name == "get_weather":
                        result = get_weather(**tool_input)
                    elif tool_name == "search_database":
                        result = search_database(**tool_input)
                    else:
                        result = {"error": f"Unknown tool: {tool_name}"}

                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": json.dumps(result)
                    })

            # Tool results Claude ko bhejo
            messages.append({"role": "user", "content": tool_results})

# Usage
answer = run_with_tools("What's the weather in Mumbai? Also find users named Ashish.")
print(answer)
```

---

### Q3: Streaming kaise implement karte hain FastAPI mein?
**Answer:**
```python
import anthropic
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
import json

app = FastAPI()
client = anthropic.AsyncAnthropic()

@app.post("/chat")
async def chat_stream(message: str, system: str = "You are a helpful assistant."):
    async def generate():
        async with client.messages.stream(
            model="claude-sonnet-4-6",
            max_tokens=1024,
            system=system,
            messages=[{"role": "user", "content": message}],
        ) as stream:
            async for text in stream.text_stream:
                yield f"data: {json.dumps({'text': text})}\n\n"

            # Final message stats
            final = await stream.get_final_message()
            yield f"data: {json.dumps({'done': True, 'usage': {'input': final.usage.input_tokens, 'output': final.usage.output_tokens}})}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
    )

# Streaming with tool use
@app.post("/chat/tools")
async def chat_with_tools_stream(message: str):
    async def generate():
        async with client.messages.stream(
            model="claude-sonnet-4-6",
            max_tokens=2048,
            tools=tools,
            messages=[{"role": "user", "content": message}],
        ) as stream:
            async for event in stream:
                if event.type == "content_block_delta":
                    if hasattr(event.delta, "text"):
                        yield f"data: {json.dumps({'type': 'text', 'content': event.delta.text})}\n\n"
                    elif hasattr(event.delta, "partial_json"):
                        yield f"data: {json.dumps({'type': 'tool_input', 'content': event.delta.partial_json})}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")
```

---

### Q4: Prompt Caching — cost 90% kaise bachate hain?
**Answer:**
```python
import anthropic

client = anthropic.Anthropic()

# Requirements:
# - Min 1024 tokens (Sonnet/Opus) ya 2048 tokens (Haiku) cached block mein
# - cache_control: {"type": "ephemeral"} add karo
# - Cache TTL = 5 minutes (same content repeat karo iss time mein)
# - Savings: cache_read = 10% of normal price

# Pattern 1: Long system prompt cache karo
LONG_CONTEXT = """
[Insert 1000+ token document/context here]
You are an expert analyzing this codebase...
[Long code examples, documentation, etc.]
"""

def analyze_with_caching(user_question: str) -> str:
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        system=[
            {
                "type": "text",
                "text": LONG_CONTEXT,
                "cache_control": {"type": "ephemeral"}  # CACHE THIS BLOCK
            }
        ],
        messages=[{"role": "user", "content": user_question}]
    )

    # Log cache usage
    usage = response.usage
    print(f"Cache write: {usage.cache_creation_input_tokens}")  # first call
    print(f"Cache read:  {usage.cache_read_input_tokens}")       # subsequent calls
    print(f"Normal:      {usage.input_tokens}")

    return response.content[0].text

# Pattern 2: RAG documents cache karo
def rag_with_caching(documents: list[str], question: str) -> str:
    doc_content = "\n\n".join(f"Document {i+1}:\n{doc}" for i, doc in enumerate(documents))

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": f"Here are the reference documents:\n\n{doc_content}",
                        "cache_control": {"type": "ephemeral"}  # documents cache
                    },
                    {
                        "type": "text",
                        "text": f"\nQuestion: {question}"
                    }
                ]
            }
        ]
    )
    return response.content[0].text

# Multiple cache breakpoints (multi-turn ke liye)
def multi_turn_with_cache(conversation_history: list, new_message: str) -> str:
    # History cache karo, sirf new message non-cached
    cached_messages = []
    for i, msg in enumerate(conversation_history):
        if i == len(conversation_history) - 1:
            # Last history message par cache breakpoint
            cached_messages.append({
                "role": msg["role"],
                "content": [
                    {"type": "text", "text": msg["content"],
                     "cache_control": {"type": "ephemeral"}}
                ]
            })
        else:
            cached_messages.append(msg)

    cached_messages.append({"role": "user", "content": new_message})

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        messages=cached_messages,
    )
    return response.content[0].text
```

---

### Q5: Batch API — bulk processing 50% cheaper
**Answer:**
```python
import anthropic
import time

client = anthropic.Anthropic()

# Batch API:
# - 50% cheaper than real-time
# - Up to 24 hours processing time
# - Up to 10,000 requests per batch
# - Best for: bulk data processing, nightly jobs, evaluations

def process_batch(items: list[dict]) -> list[dict]:
    # Requests create karo
    requests = [
        {
            "custom_id": f"item-{i}",  # track karne ke liye
            "params": {
                "model": "claude-haiku-4-5-20251001",
                "max_tokens": 200,
                "messages": [{
                    "role": "user",
                    "content": f"Classify this review sentiment (POSITIVE/NEGATIVE/NEUTRAL): {item['text']}"
                }]
            }
        }
        for i, item in enumerate(items)
    ]

    # Batch submit karo
    batch = client.messages.batches.create(requests=requests)
    print(f"Batch ID: {batch.id}")
    print(f"Status: {batch.processing_status}")

    # Poll for completion
    while batch.processing_status == "in_progress":
        time.sleep(60)  # 1 minute wait
        batch = client.messages.batches.retrieve(batch.id)
        print(f"Status: {batch.processing_status} - "
              f"Succeeded: {batch.request_counts.succeeded}/"
              f"{batch.request_counts.processing}")

    # Results collect karo
    results = []
    for result in client.messages.batches.results(batch.id):
        if result.result.type == "succeeded":
            results.append({
                "id": result.custom_id,
                "sentiment": result.result.message.content[0].text.strip()
            })
        else:
            results.append({
                "id": result.custom_id,
                "error": result.result.error.type
            })

    return results

# Async batch monitoring
async def monitor_batch(batch_id: str):
    async_client = anthropic.AsyncAnthropic()

    while True:
        batch = await async_client.messages.batches.retrieve(batch_id)
        if batch.processing_status != "in_progress":
            break
        await asyncio.sleep(30)

    return batch
```

---

### Q6: Claude vs GPT-4 — key differences?
**Answer:**
```
CLAUDE strengths:
  ✓ Longer context (200K tokens Sonnet/Opus)
  ✓ Better instruction following
  ✓ More nuanced, less hallucination in long context
  ✓ Better code quality (especially Python)
  ✓ Extended thinking for complex reasoning
  ✓ Prompt caching (90% savings on cached tokens)
  ✓ Computer Use API
  ✓ Better at refusing harmful requests gracefully

GPT-4 strengths:
  ✓ Wider ecosystem (plugins, assistants API)
  ✓ Better for structured outputs (JSON mode built-in)
  ✓ Fine-tuning available (GPT-4o-mini)
  ✓ More familiar to developers
  ✓ DALL-E integration
  ✓ Better multilingual (some languages)

BOTH good at:
  - Code generation
  - RAG
  - Tool/function calling
  - Vision
  - Streaming

Practical choice:
  Production API + RAG → Claude Sonnet (cost + quality)
  Simple/fast tasks → Claude Haiku or GPT-4o-mini
  Complex reasoning → Claude Opus or GPT-o1
  Fine-tuning needed → GPT-4o-mini
```
