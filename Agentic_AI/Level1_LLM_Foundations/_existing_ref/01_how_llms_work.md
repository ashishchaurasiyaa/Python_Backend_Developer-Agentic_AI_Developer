# How LLMs Work — Tokens, Context Window, Temperature, Streaming

## Quick Concepts
- **LLM** = Large Language Model — next token predict karta hai probability se
- **Token** ≈ 4 characters ya ~¾ word — billing aur context limit tokens mein hoti hai
- **Context window** = max tokens model ek baar mein dekh sakta hai (input + output)
- **Temperature** = randomness control — 0 = deterministic, 1+ = creative
- **Top-p (nucleus sampling)** = cumulative probability threshold
- **Streaming** = tokens ek ek karke aate hain — perceived speed fast

---

## Interview Questions & Answers

### Q1: LLM kaise kaam karta hai? Tokens kya hain?
**Answer:**
```
LLM = Transformer architecture
Input text → tokenize → embedding vectors → attention layers → output token probabilities → sample next token

Token ≠ word:
  "Hello world" = 2 tokens
  "Ashish" = 2 tokens (Ash + ish)
  " " (space) = usually part of next token
  Code, numbers = more tokens

Token counting:
  English: ~1 token per 4 chars / ~¾ words per token
  Hindi/Unicode: more tokens per character (2-4x)
  Code: variable

tiktoken se count karo (OpenAI):
```

```python
import tiktoken

def count_tokens(text: str, model: str = "gpt-4o") -> int:
    enc = tiktoken.encoding_for_model(model)
    return len(enc.encode(text))

def estimate_cost(text: str, model: str = "gpt-4o") -> dict:
    tokens = count_tokens(text, model)
    # GPT-4o pricing (approximate)
    input_cost_per_1k = 0.005
    return {
        "tokens": tokens,
        "estimated_cost_usd": (tokens / 1000) * input_cost_per_1k
    }

# Anthropic ke liye
import anthropic
client = anthropic.Anthropic()

def count_tokens_claude(messages: list, model: str = "claude-sonnet-4-6") -> int:
    response = client.messages.count_tokens(
        model=model,
        messages=messages,
    )
    return response.input_tokens
```

---

### Q2: Temperature, Top-p, Max Tokens — kya effect padta hai?
**Answer:**
```python
import openai

client = openai.OpenAI()

# TEMPERATURE
# 0.0 = deterministic (same input → same output) — code generation, factual
# 0.3-0.7 = balanced — general chat
# 0.8-1.0 = creative — stories, brainstorming
# > 1.0 = very random (usually avoid)

# TOP-P (nucleus sampling)
# 0.1 = top 10% probability tokens only (focused)
# 0.9 = top 90% probability tokens (diverse)
# 1.0 = all tokens eligible
# Note: Temperature ya top-p — dono ek saath nahi change karte usually

# Use temperature OR top-p, not both
response = client.chat.completions.create(
    model="gpt-4o",
    messages=[{"role": "user", "content": "Write a poem"}],
    temperature=0.9,      # creative
    top_p=1.0,
    max_tokens=500,        # output limit
    presence_penalty=0.5,  # naye topics encourage karo (0 to 2)
    frequency_penalty=0.3, # repetition reduce karo (0 to 2)
)

# WHEN TO USE WHAT:
# Code generation:     temperature=0, top_p=0.1
# Factual Q&A:         temperature=0.1
# Chat assistant:      temperature=0.7
# Creative writing:    temperature=0.9, top_p=0.95
# Data extraction:     temperature=0, top_p=0.1
```

---

### Q3: Context Window management kaise karte hain? Sliding window?
**Answer:**
```python
from typing import TypedDict

class Message(TypedDict):
    role: str  # "system", "user", "assistant"
    content: str

class ContextWindowManager:
    def __init__(self, max_tokens: int = 100_000, reserve_output: int = 2000):
        self.max_tokens = max_tokens - reserve_output  # output ke liye reserve
        self.messages: list[Message] = []
        self.system_prompt: str = ""

    def set_system(self, prompt: str):
        self.system_prompt = prompt

    def add_message(self, role: str, content: str):
        self.messages.append({"role": role, "content": content})
        self._trim_if_needed()

    def _estimate_tokens(self, text: str) -> int:
        return len(text) // 4  # rough estimate

    def _trim_if_needed(self):
        """Context limit exceed ho toh purane messages hataao"""
        while self._total_tokens() > self.max_tokens and len(self.messages) > 2:
            # Pehla user message hataao (system ke baad)
            self.messages.pop(0)

    def _total_tokens(self) -> int:
        total = self._estimate_tokens(self.system_prompt)
        for msg in self.messages:
            total += self._estimate_tokens(msg["content"])
        return total

    def get_messages(self) -> list[Message]:
        return self.messages

# Summarization strategy (better than trimming)
async def summarize_old_messages(
    messages: list[Message],
    client: openai.AsyncOpenAI,
    keep_last: int = 10
) -> list[Message]:
    if len(messages) <= keep_last:
        return messages

    to_summarize = messages[:-keep_last]
    recent = messages[-keep_last:]

    summary_prompt = f"""Summarize this conversation history concisely:

{chr(10).join(f'{m["role"]}: {m["content"]}' for m in to_summarize)}

Summary:"""

    response = await client.chat.completions.create(
        model="gpt-4o-mini",  # cheap model for summarization
        messages=[{"role": "user", "content": summary_prompt}],
        max_tokens=300,
        temperature=0.1,
    )
    summary = response.choices[0].message.content

    return [
        {"role": "system", "content": f"[Previous conversation summary: {summary}]"},
        *recent
    ]
```

---

### Q4: Streaming responses kaise implement karte hain?
**Answer:**
```python
import asyncio
import openai

client = openai.AsyncOpenAI()

# STREAMING — tokens as they arrive
async def stream_response(prompt: str):
    async with client.chat.completions.stream(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=1000,
    ) as stream:
        async for text in stream.text_stream:
            print(text, end="", flush=True)

# FastAPI SSE (Server-Sent Events) endpoint
from fastapi import FastAPI
from fastapi.responses import StreamingResponse

app = FastAPI()

@app.post("/chat/stream")
async def chat_stream(message: str):
    async def generate():
        async with client.chat.completions.stream(
            model="gpt-4o",
            messages=[{"role": "user", "content": message}],
        ) as stream:
            async for chunk in stream:
                if chunk.choices[0].delta.content:
                    text = chunk.choices[0].delta.content
                    yield f"data: {json.dumps({'text': text})}\n\n"
            yield "data: [DONE]\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        }
    )

# Frontend (JavaScript) mein receive karo:
# const eventSource = new EventSource('/chat/stream?message=...')
# eventSource.onmessage = (e) => {
#   if (e.data === '[DONE]') return
#   const { text } = JSON.parse(e.data)
#   document.getElementById('response').innerHTML += text
# }
```

---

### Q5: Model routing — kab kaunsa model use karo?
**Answer:**
```python
from enum import Enum

class TaskComplexity(Enum):
    SIMPLE = "simple"      # keyword extraction, classification
    MEDIUM = "medium"      # Q&A, summarization, translation
    COMPLEX = "complex"    # reasoning, code generation, analysis

def route_model(task: TaskComplexity, needs_speed: bool = False) -> str:
    """Cost-effective model routing"""

    routing_table = {
        # (complexity, speed_priority): model
        (TaskComplexity.SIMPLE, True):    "gpt-4o-mini",          # cheapest + fast
        (TaskComplexity.SIMPLE, False):   "gpt-4o-mini",
        (TaskComplexity.MEDIUM, True):    "claude-haiku-4-5-20251001",  # fast + capable
        (TaskComplexity.MEDIUM, False):   "claude-sonnet-4-6",    # balanced
        (TaskComplexity.COMPLEX, True):   "claude-sonnet-4-6",    # fast powerful
        (TaskComplexity.COMPLEX, False):  "claude-opus-4-7",      # most capable
    }

    return routing_table[(task, needs_speed)]

# Practical routing
async def smart_complete(prompt: str, task_type: str) -> str:
    complexity_map = {
        "classify": TaskComplexity.SIMPLE,
        "extract": TaskComplexity.SIMPLE,
        "summarize": TaskComplexity.MEDIUM,
        "answer": TaskComplexity.MEDIUM,
        "reason": TaskComplexity.COMPLEX,
        "code": TaskComplexity.COMPLEX,
    }

    complexity = complexity_map.get(task_type, TaskComplexity.MEDIUM)
    model = route_model(complexity)

    # Cost ~10x cheaper for simple tasks using mini models
    ...

# Cost comparison (approximate, May 2025):
# GPT-4o-mini:      $0.15/$0.60  per 1M input/output tokens
# Claude Haiku:     $0.25/$1.25  per 1M tokens
# GPT-4o:           $5/$15       per 1M tokens
# Claude Sonnet:    $3/$15       per 1M tokens
# Claude Opus:      $15/$75      per 1M tokens
```

---

### Q6: Prompt Caching kya hai? Cost kaise bachate hain?
**Answer:**
```
Prompt Caching = repeated system prompt / context ko cache karo
→ cached tokens = 90% cheaper (Anthropic) / 50% cheaper (OpenAI)

USE WHEN:
- Long system prompt (>1024 tokens Anthropic, >128 OpenAI)
- Same documents/context baar baar bhejte ho (RAG)
- Few-shot examples bade hain

HOW IT WORKS:
- Pehli call: full tokens charge hote hain + cache fill hota hai (5 min TTL)
- Agle calls (5 min mein): cached part = deep discount
```

```python
# Anthropic cache_control (next file mein detail)
import anthropic

client = anthropic.Anthropic()

LONG_SYSTEM_PROMPT = """You are an expert Python backend developer...
[1000+ words of context/instructions]
"""  # This gets cached

response = client.messages.create(
    model="claude-sonnet-4-6",
    max_tokens=1024,
    system=[
        {
            "type": "text",
            "text": LONG_SYSTEM_PROMPT,
            "cache_control": {"type": "ephemeral"}  # CACHE THIS
        }
    ],
    messages=[{"role": "user", "content": "What is FastAPI?"}]
)

# Check cache hit
print(response.usage.cache_read_input_tokens)    # cached tokens (cheap)
print(response.usage.cache_creation_input_tokens) # first time cache fill
print(response.usage.input_tokens)               # non-cached tokens
```
