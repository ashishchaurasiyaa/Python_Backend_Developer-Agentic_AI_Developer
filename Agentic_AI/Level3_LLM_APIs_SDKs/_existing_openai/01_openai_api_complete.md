# OpenAI API — Chat Completions, Embeddings, Batch, Fine-tuning, Rate Limits

## Quick Concepts
- **Chat Completions** = primary API — GPT-4o, o1, etc.
- **Embeddings** = text → vector (numbers) — semantic search ke liye
- **Batch API** = async, 50% cheaper, 24h SLA
- **Fine-tuning** = apna data se model customize karo
- **TPM/RPM** = Tokens Per Minute / Requests Per Minute — rate limits

---

## Interview Questions & Answers

### Q1: OpenAI Chat Completions API advanced usage?
**Answer:**
```python
import openai
from openai import AsyncOpenAI

client = openai.OpenAI()
async_client = AsyncOpenAI()

# Basic call with all params
response = client.chat.completions.create(
    model="gpt-4o",
    messages=[
        {"role": "system", "content": "You are a Python expert."},
        {"role": "user", "content": "Explain generators."},
        {"role": "assistant", "content": "Generators are..."},   # multi-turn
        {"role": "user", "content": "Give me an example."},
    ],
    max_tokens=1000,
    temperature=0.7,
    top_p=1.0,
    n=1,                    # kitne completions chahiye
    stream=False,
    presence_penalty=0.0,
    frequency_penalty=0.0,
    logprobs=True,          # token probabilities (debugging ke liye)
    top_logprobs=3,
    seed=42,               # reproducibility
    user="user-123",       # rate limit tracking
)

print(response.choices[0].message.content)
print(f"Finish reason: {response.choices[0].finish_reason}")  # stop, length, tool_calls
print(f"Total tokens: {response.usage.total_tokens}")

# Function calling (OpenAI style)
functions = [
    {
        "name": "get_stock_price",
        "description": "Get current stock price",
        "parameters": {
            "type": "object",
            "properties": {
                "symbol": {"type": "string", "description": "Stock symbol like RELIANCE.NS"},
                "exchange": {"type": "string", "enum": ["NSE", "BSE"]}
            },
            "required": ["symbol"]
        }
    }
]

response = client.chat.completions.create(
    model="gpt-4o",
    messages=[{"role": "user", "content": "What is Reliance stock price on NSE?"}],
    tools=[{"type": "function", "function": f} for f in functions],
    tool_choice="auto",  # auto, none, ya specific tool
)

if response.choices[0].finish_reason == "tool_calls":
    tool_call = response.choices[0].message.tool_calls[0]
    func_name = tool_call.function.name
    func_args = json.loads(tool_call.function.arguments)
    # Execute function...
```

---

### Q2: Embeddings API — semantic search kaise karte hain?
**Answer:**
```python
import numpy as np
from openai import OpenAI

client = OpenAI()

def get_embedding(text: str, model: str = "text-embedding-3-small") -> list[float]:
    """
    Models:
    text-embedding-3-small: 1536 dims, $0.02/1M tokens (RECOMMENDED)
    text-embedding-3-large: 3072 dims, $0.13/1M tokens (better quality)
    text-embedding-ada-002: 1536 dims (old, avoid)
    """
    text = text.replace("\n", " ")  # newlines remove karo
    response = client.embeddings.create(input=text, model=model)
    return response.data[0].embedding

def cosine_similarity(v1: list[float], v2: list[float]) -> float:
    a, b = np.array(v1), np.array(v2)
    return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))

# Simple semantic search
class SemanticSearchEngine:
    def __init__(self):
        self.documents: list[str] = []
        self.embeddings: list[list[float]] = []

    def add_document(self, text: str):
        embedding = get_embedding(text)
        self.documents.append(text)
        self.embeddings.append(embedding)

    def search(self, query: str, top_k: int = 5) -> list[tuple[str, float]]:
        query_embedding = get_embedding(query)
        similarities = [
            cosine_similarity(query_embedding, emb)
            for emb in self.embeddings
        ]
        # Top-k results
        top_indices = np.argsort(similarities)[-top_k:][::-1]
        return [(self.documents[i], similarities[i]) for i in top_indices]

# Bulk embeddings (efficient)
def get_embeddings_batch(texts: list[str]) -> list[list[float]]:
    # OpenAI ek call mein 2048 texts tak handle karta hai
    response = client.embeddings.create(
        input=texts,
        model="text-embedding-3-small"
    )
    return [item.embedding for item in sorted(response.data, key=lambda x: x.index)]

# With pgvector (PostgreSQL)
import asyncpg

async def store_embeddings(conn, documents: list[dict]):
    embeddings = get_embeddings_batch([d["text"] for d in documents])
    await conn.executemany(
        "INSERT INTO documents (content, embedding) VALUES ($1, $2::vector)",
        [(doc["text"], embedding) for doc, embedding in zip(documents, embeddings)]
    )

async def semantic_search_db(conn, query: str, limit: int = 5):
    query_embedding = get_embedding(query)
    return await conn.fetch(
        """
        SELECT content, 1 - (embedding <=> $1::vector) as similarity
        FROM documents
        ORDER BY embedding <=> $1::vector
        LIMIT $2
        """,
        query_embedding, limit
    )
```

---

### Q3: Rate Limiting handle kaise karo? Exponential backoff?
**Answer:**
```python
import asyncio
import time
from tenacity import (
    retry, stop_after_attempt, wait_exponential,
    retry_if_exception_type, before_sleep_log
)
import logging
import openai

logger = logging.getLogger(__name__)

# Tenacity se automatic retry
@retry(
    stop=stop_after_attempt(6),
    wait=wait_exponential(multiplier=1, min=1, max=60),
    retry=retry_if_exception_type(openai.RateLimitError),
    before_sleep=before_sleep_log(logger, logging.WARNING),
)
async def call_with_retry(messages: list, model: str = "gpt-4o") -> str:
    response = await async_client.chat.completions.create(
        model=model,
        messages=messages,
        max_tokens=1000,
    )
    return response.choices[0].message.content

# Manual rate limiting with token bucket
class OpenAIRateLimiter:
    def __init__(self, rpm: int = 500, tpm: int = 150000):
        self.rpm = rpm
        self.tpm = tpm
        self._request_times = []
        self._token_times = []

    async def wait_if_needed(self, estimated_tokens: int = 1000):
        now = time.time()
        minute_ago = now - 60

        # Clean old entries
        self._request_times = [t for t in self._request_times if t > minute_ago]
        self._token_times = [t for t in self._token_times if t[0] > minute_ago]

        # Check limits
        if len(self._request_times) >= self.rpm:
            wait = 60 - (now - self._request_times[0])
            if wait > 0:
                await asyncio.sleep(wait)

        tokens_used = sum(t[1] for t in self._token_times)
        if tokens_used + estimated_tokens >= self.tpm:
            wait = 60 - (now - self._token_times[0][0])
            if wait > 0:
                await asyncio.sleep(wait)

        self._request_times.append(now)
        self._token_times.append((now, estimated_tokens))

rate_limiter = OpenAIRateLimiter(rpm=500, tpm=150000)

async def rate_limited_call(messages: list) -> str:
    await rate_limiter.wait_if_needed()
    return await call_with_retry(messages)
```

---

### Q4: OpenAI Batch API kaise use karte hain?
**Answer:**
```python
import json
import io
from openai import OpenAI

client = OpenAI()

def submit_batch(prompts: list[dict]) -> str:
    """
    Batch API:
    - 50% cheaper
    - Up to 24 hours
    - Up to 50,000 requests per batch
    """
    # JSONL file banao
    batch_content = ""
    for i, prompt in enumerate(prompts):
        request = {
            "custom_id": f"req-{i}",
            "method": "POST",
            "url": "/v1/chat/completions",
            "body": {
                "model": "gpt-4o-mini",
                "messages": prompt["messages"],
                "max_tokens": prompt.get("max_tokens", 500),
            }
        }
        batch_content += json.dumps(request) + "\n"

    # File upload
    file_obj = io.BytesIO(batch_content.encode())
    batch_file = client.files.create(file=("batch.jsonl", file_obj), purpose="batch")

    # Batch create
    batch = client.batches.create(
        input_file_id=batch_file.id,
        endpoint="/v1/chat/completions",
        completion_window="24h",
    )

    print(f"Batch ID: {batch.id}")
    return batch.id

def get_batch_results(batch_id: str) -> list[dict]:
    batch = client.batches.retrieve(batch_id)

    if batch.status != "completed":
        print(f"Status: {batch.status}")
        return []

    # Results download
    result_file = client.files.content(batch.output_file_id)
    results = []

    for line in result_file.text.strip().split("\n"):
        data = json.loads(line)
        if data["response"]["status_code"] == 200:
            results.append({
                "id": data["custom_id"],
                "content": data["response"]["body"]["choices"][0]["message"]["content"]
            })

    return results
```

---

### Q5: Fine-tuning kab kare? Kaise karte hain?
**Answer:**
```python
# WHEN TO FINE-TUNE:
# ✓ Consistent format/style chahiye (always JSON, always Hindi)
# ✓ Domain-specific knowledge jis par model weak hai
# ✓ Prompt engineering insufficient hai
# ✓ Cost reduce karna hai (smaller fine-tuned model)
# ✗ RAG better option hai (knowledge retrieval ke liye)
# ✗ Reasoning improve nahi hota fine-tuning se

import json

# Training data prepare karo (JSONL format)
training_examples = [
    {
        "messages": [
            {"role": "system", "content": "Extract order info as JSON"},
            {"role": "user", "content": "Order 2 laptops worth 1500 USD each"},
            {"role": "assistant", "content": '{"items": "laptops", "qty": 2, "price": 1500, "total": 3000}'}
        ]
    },
    # ... minimum 10 examples, recommended 50-100
]

# Save JSONL
with open("training_data.jsonl", "w") as f:
    for example in training_examples:
        f.write(json.dumps(example) + "\n")

# Upload + fine-tune
def start_fine_tune():
    # Upload file
    with open("training_data.jsonl", "rb") as f:
        file = client.files.create(file=f, purpose="fine-tune")

    # Start job
    job = client.fine_tuning.jobs.create(
        training_file=file.id,
        model="gpt-4o-mini",   # cheapest to fine-tune
        hyperparameters={
            "n_epochs": 3,
            "learning_rate_multiplier": 0.1,
        }
    )

    print(f"Fine-tune job: {job.id}")
    return job.id

# Check status
def check_fine_tune(job_id: str):
    job = client.fine_tuning.jobs.retrieve(job_id)
    print(f"Status: {job.status}")
    print(f"Model: {job.fine_tuned_model}")   # ft:gpt-4o-mini:org:name:id

# Use fine-tuned model
response = client.chat.completions.create(
    model="ft:gpt-4o-mini:myorg:order-extractor:abc123",
    messages=[{"role": "user", "content": "Order 3 phones for 800 USD"}]
)
```

---

### Q6: Cost optimization strategies?
**Answer:**
```python
# 1. CACHING — same request ke liye cache use karo
import hashlib
import redis

redis_client = redis.Redis()

def cached_completion(messages: list, model: str = "gpt-4o-mini") -> str:
    cache_key = hashlib.md5(json.dumps(messages).encode()).hexdigest()
    cached = redis_client.get(f"llm_cache:{cache_key}")
    if cached:
        return cached.decode()

    response = client.chat.completions.create(model=model, messages=messages)
    result = response.choices[0].message.content

    redis_client.setex(f"llm_cache:{cache_key}", 3600, result)
    return result

# 2. MODEL ROUTING — complexity ke hisab se model choose karo
def smart_model_select(prompt_length: int, task: str) -> str:
    if task in ["classify", "extract"] or prompt_length < 500:
        return "gpt-4o-mini"  # 30x cheaper than gpt-4o
    elif task in ["summarize", "translate"]:
        return "gpt-4o-mini"
    else:
        return "gpt-4o"

# 3. BATCH INSTEAD OF REAL-TIME (when latency ok)
# Real-time: $5/1M tokens
# Batch:     $2.5/1M tokens (50% off)

# 4. PROMPT COMPRESSION — unnecessary text remove karo
def compress_prompt(text: str) -> str:
    # LLMLingua ya manual compression
    # Remove redundant whitespace, examples, verbose instructions
    import re
    return re.sub(r'\s+', ' ', text).strip()

# 5. MAX TOKENS SET KARO — infinite billing nahi
# Always max_tokens set karo based on expected output
```
