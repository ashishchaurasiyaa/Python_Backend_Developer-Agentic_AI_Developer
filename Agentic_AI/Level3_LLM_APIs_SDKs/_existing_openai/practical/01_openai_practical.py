"""
Phase4_OpenAI — Complete Practical
=====================================
Topics covered:
  1. Chat Completions (GPT-4o) — basic, multi-turn, JSON mode
  2. Streaming responses
  3. Function calling / Tool use
  4. Embeddings (text-embedding-3-small)
  5. Vision (GPT-4o with image)
  6. Rate limit handling with exponential backoff
  7. Batch API (async, 50% cheaper)
  8. Async client

Install: pip install openai
Env var: OPENAI_API_KEY=sk-...

Run: python 01_openai_practical.py
"""

import asyncio
import base64
import json
import os
import time
import random

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
MOCK_MODE = not OPENAI_API_KEY

if MOCK_MODE:
    print("⚠  MOCK MODE — set OPENAI_API_KEY env var to run real API calls\n")

try:
    import openai
    from openai import OpenAI, AsyncOpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    print("openai not installed: pip install openai\n")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 1: Chat Completions
# ─────────────────────────────────────────────────────────────────────────────

print("=" * 60)
print("SECTION 1: OpenAI Chat Completions")
print("=" * 60)

OPENAI_MODELS = {
    "gpt-4o":         "Multimodal, text+vision, fast, good quality",
    "gpt-4o-mini":    "Cheap + fast — for high volume tasks",
    "gpt-4-turbo":    "Long context (128k), reliable",
    "o1-preview":     "Deep reasoning (slower, expensive)",
    "o3-mini":        "Fast reasoning model",
}
print("\n  Models:")
for m, d in OPENAI_MODELS.items():
    print(f"  {m:<16}: {d}")

def basic_openai_call():
    if MOCK_MODE or not OPENAI_AVAILABLE:
        print("\n  [Mock] Chat completion: 'Generators are lazy iterators...'")
        return

    client = OpenAI()
    response = client.chat.completions.create(
        model       = "gpt-4o-mini",
        max_tokens  = 200,
        temperature = 0.7,
        messages    = [
            {"role": "system", "content": "You are a concise Python expert."},
            {"role": "user",   "content": "Explain Python generators in 2 sentences."},
        ],
    )
    msg = response.choices[0].message
    print(f"\n  Response: {msg.content[:100]}...")
    print(f"  Tokens: {response.usage.prompt_tokens} in, {response.usage.completion_tokens} out")
    print(f"  Finish reason: {response.choices[0].finish_reason}")

basic_openai_call()

# JSON mode
JSON_MODE_CODE = '''\
# INTERVIEW: JSON mode = guaranteed valid JSON output
response = client.chat.completions.create(
    model="gpt-4o-mini",
    response_format={"type": "json_object"},   # ← enable JSON mode
    messages=[
        {"role": "system", "content": "Output valid JSON only."},
        {"role": "user",   "content": "Return user info as JSON with name, age, email fields."},
    ],
)
data = json.loads(response.choices[0].message.content)
print(data)  # {"name": "Alice", "age": 30, "email": "alice@example.com"}
'''
print("\n  JSON mode pattern:", JSON_MODE_CODE[:150])


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 2: Function Calling
# INTERVIEW: Model decides when and which function to call
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 60)
print("SECTION 2: Function Calling / Tool Use")
print("=" * 60)

TOOLS_DEFINITION = [
    {
        "type": "function",
        "function": {
            "name":        "search_database",
            "description": "Search users database by email or name",
            "parameters": {
                "type":       "object",
                "properties": {
                    "query":       {"type": "string", "description": "Search term"},
                    "field":       {"type": "string", "enum": ["email", "name", "id"]},
                    "limit":       {"type": "integer", "default": 10},
                },
                "required": ["query", "field"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "send_email",
            "description": "Send an email to a user",
            "parameters": {
                "type":       "object",
                "properties": {
                    "to":      {"type": "string"},
                    "subject": {"type": "string"},
                    "body":    {"type": "string"},
                },
                "required": ["to", "subject", "body"],
            },
        },
    },
]


def handle_tool_call(name: str, args: dict) -> str:
    """Execute tool and return JSON result."""
    if name == "search_database":
        return json.dumps([
            {"id": 1, "name": "Alice Johnson", "email": "alice@example.com"},
            {"id": 2, "name": "Alice Smith",   "email": "alice.s@example.com"},
        ])
    elif name == "send_email":
        print(f"    [Email sent to {args['to']}: {args['subject']}]")
        return json.dumps({"success": True, "message_id": "msg_123"})
    return json.dumps({"error": "Unknown tool"})


def openai_with_tools(user_message: str):
    """
    INTERVIEW: OpenAI tool use flow (same as Claude):
    1. Send tools + message
    2. model returns tool_calls (finish_reason = "tool_calls")
    3. Execute tools
    4. Send tool results as "tool" role messages
    5. Model returns final text
    """
    if MOCK_MODE or not OPENAI_AVAILABLE:
        print(f"  [Mock] User: {user_message}")
        print(f"  [Mock] Tool call: search_database(query='Alice', field='name')")
        print(f"  [Mock] Final: Found 2 users named Alice.")
        return

    client   = OpenAI()
    messages = [{"role": "user", "content": user_message}]

    response = client.chat.completions.create(
        model    = "gpt-4o-mini",
        tools    = TOOLS_DEFINITION,
        messages = messages,
    )

    while response.choices[0].finish_reason == "tool_calls":
        msg = response.choices[0].message
        messages.append(msg)

        for tool_call in msg.tool_calls:
            args   = json.loads(tool_call.function.arguments)
            result = handle_tool_call(tool_call.function.name, args)
            print(f"  Tool: {tool_call.function.name}({args})")

            messages.append({
                "role":         "tool",
                "tool_call_id": tool_call.id,
                "content":      result,
            })

        response = client.chat.completions.create(
            model    = "gpt-4o-mini",
            tools    = TOOLS_DEFINITION,
            messages = messages,
        )

    print(f"  Answer: {response.choices[0].message.content[:100]}...")


print("\n  Tool use demo:")
openai_with_tools("Find all users named Alice and send them a welcome email.")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 3: Embeddings
# INTERVIEW: Text → vector for semantic search, RAG, clustering
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 60)
print("SECTION 3: Embeddings")
print("=" * 60)

import math

def cosine_similarity(v1: list, v2: list) -> float:
    """Calculate cosine similarity between two vectors."""
    dot   = sum(a * b for a, b in zip(v1, v2))
    norm1 = math.sqrt(sum(a * a for a in v1))
    norm2 = math.sqrt(sum(b * b for b in v2))
    return dot / (norm1 * norm2) if norm1 and norm2 else 0.0


def demo_embeddings():
    if MOCK_MODE or not OPENAI_AVAILABLE:
        # Simulate embeddings with random vectors
        print("  [Mock] Embedding demo with simulated vectors:")
        import random
        random.seed(42)
        docs = [
            "Python is a programming language",
            "FastAPI is a web framework for Python",
            "The cat sat on the mat",
        ]
        query     = "Python web development"
        query_vec = [random.gauss(0, 1) for _ in range(1536)]
        doc_vecs  = [[random.gauss(0, 1) for _ in range(1536)] for _ in docs]

        # Normalize
        def normalize(v): n = math.sqrt(sum(x*x for x in v)); return [x/n for x in v]
        query_vec = normalize(query_vec)
        doc_vecs  = [normalize(v) for v in doc_vecs]

        similarities = [(cosine_similarity(query_vec, dv), doc) for dv, doc in zip(doc_vecs, docs)]
        similarities.sort(reverse=True)
        print(f"  Query: '{query}'")
        for sim, doc in similarities:
            print(f"    {sim:.3f}: {doc}")
        return

    client = OpenAI()
    docs = [
        "Python is a programming language",
        "FastAPI is a web framework for Python",
        "The cat sat on the mat",
    ]
    query = "Python web development"

    # Batch embed docs + query
    all_texts = [query] + docs
    response  = client.embeddings.create(model="text-embedding-3-small", input=all_texts)
    vectors   = [e.embedding for e in response.data]

    query_vec = vectors[0]
    doc_vecs  = vectors[1:]

    similarities = [(cosine_similarity(query_vec, dv), doc) for dv, doc in zip(doc_vecs, docs)]
    similarities.sort(reverse=True)

    print(f"  Query: '{query}'")
    print(f"  Embedding size: {len(query_vec)} dimensions")
    for sim, doc in similarities:
        print(f"    {sim:.3f}: {doc}")


demo_embeddings()

print("\n  Embedding Models:")
embed_models = {
    "text-embedding-3-small": "1536 dims, cheapest ($0.02/1M tokens)",
    "text-embedding-3-large": "3072 dims, more accurate ($0.13/1M tokens)",
    "text-embedding-ada-002": "Legacy — use 3-small instead",
}
for m, d in embed_models.items():
    print(f"  {m:<30}: {d}")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 4: Rate Limit Handling
# INTERVIEW: 429 handling with exponential backoff
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 60)
print("SECTION 4: Rate Limit Handling")
print("=" * 60)

RATE_LIMIT_CODE = '''\
from openai import RateLimitError, APITimeoutError, APIConnectionError
import time, random

def call_with_retry(func, *args, max_retries=5, **kwargs):
    """Exponential backoff for OpenAI rate limits."""
    for attempt in range(max_retries):
        try:
            return func(*args, **kwargs)
        except RateLimitError as e:
            # INTERVIEW: Respect Retry-After header if present
            retry_after = getattr(e, "retry_after", None)
            wait = retry_after or min(2 ** attempt + random.uniform(0, 1), 60)
            print(f"Rate limited. Waiting {wait:.1f}s (attempt {attempt+1})")
            time.sleep(wait)
        except APITimeoutError:
            time.sleep(2 ** attempt)   # timeout → backoff
        except APIConnectionError:
            time.sleep(5)  # connection error → wait longer
    raise RuntimeError("Max retries exceeded")

# Usage
response = call_with_retry(
    client.chat.completions.create,
    model="gpt-4o-mini",
    messages=[{"role": "user", "content": "Hello"}]
)
'''
print(RATE_LIMIT_CODE[:500])

print("\n  Rate Limit Tips:")
tips = {
    "TPM/RPM":          "Track tokens/requests per minute — stay under limits",
    "Retry-After":      "OpenAI sends header with wait time — respect it",
    "Jitter":           "Add random(0, 1) to backoff — prevent thundering herd",
    "Parallel requests": "Use asyncio.gather() for concurrent requests (stay under RPM)",
    "Batch API":        "For non-real-time: 50% cheaper, no rate limits",
}
for k, v in tips.items():
    print(f"  {k:<20}: {v}")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 5: Async Client
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 60)
print("SECTION 5: Async Client + Parallel Calls")
print("=" * 60)

ASYNC_CODE = '''\
import asyncio
from openai import AsyncOpenAI

async_client = AsyncOpenAI()

async def get_analysis(text: str, analysis_type: str) -> str:
    response = await async_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": f"Perform {analysis_type} analysis."},
            {"role": "user",   "content": text},
        ],
        max_tokens=200,
    )
    return response.choices[0].message.content

async def parallel_analysis(text: str):
    """INTERVIEW: asyncio.gather = run multiple LLM calls concurrently."""
    sentiment, keywords, summary = await asyncio.gather(
        get_analysis(text, "sentiment"),
        get_analysis(text, "keyword extraction"),
        get_analysis(text, "summarization"),
    )
    return {"sentiment": sentiment, "keywords": keywords, "summary": summary}

# Run it:
results = asyncio.run(parallel_analysis("FastAPI is an excellent Python web framework..."))
'''
print(ASYNC_CODE)

print("\n" + "=" * 60)
print("OPENAI API INTERVIEW SUMMARY:")
print("  Chat Completions: temperature, max_tokens, response_format=json_object")
print("  Tool use: finish_reason='tool_calls' → execute → send as role='tool'")
print("  Embeddings: text-embedding-3-small, cosine similarity for search")
print("  Rate limits: exponential backoff + jitter, Batch API for bulk")
print("  Async: AsyncOpenAI + asyncio.gather for parallel calls")
print("=" * 60)
