# Level 3.6 — Async & Parallel LLM Calls
**Phase: LLM APIs & SDKs | Production-Critical**

## Quick Concepts

- **Async** = non-blocking I/O — one coroutine can wait on N LLM calls simultaneously
- **Parallel calls** = N LLM requests in flight at once (fan-out)
- **asyncio.gather** = await all N tasks, return list of results
- **Semaphore** = limit concurrent calls (avoid rate limits)
- **Batching** = group requests into one larger one (e.g., embedding batch)
- **Rate limit** = provider's max RPM/TPM per key
- **Fan-out / fan-in** = pattern: send N requests → collect N responses

---

## Why Async + Parallel Matters

```
Sequential (BLOCKING):
   10 LLM calls × 2 sec each = 20 seconds total
   User waits forever.

Parallel async:
   10 LLM calls in flight = 2 seconds total
   10x faster.

Common scenarios:
   ✓ Multi-document summarization (1 call per doc)
   ✓ Multi-tenant batch processing
   ✓ Multi-step agent chains (parallel branches)
   ✓ A/B comparing prompts/models
   ✓ Embedding batches for RAG indexing
```

---

## Basic Async LLM Call

```python
from openai import AsyncOpenAI
import asyncio

client = AsyncOpenAI()


async def ask(prompt: str) -> str:
    response = await client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
    )
    return response.choices[0].message.content


# Single call
async def main():
    answer = await ask("What is FastAPI?")
    print(answer)

asyncio.run(main())
```

---

## Parallel Calls — asyncio.gather

```python
async def parallel_questions():
    questions = [
        "Explain async in Python",
        "Explain await keyword",
        "Explain event loop",
        "Explain coroutine",
    ]

    # Fire all 4 at once, wait for all
    tasks = [ask(q) for q in questions]
    answers = await asyncio.gather(*tasks)

    for q, a in zip(questions, answers):
        print(f"Q: {q}\nA: {a[:100]}...\n")


asyncio.run(parallel_questions())
```

**Speedup:** 4 calls × 2s = 8s sequential → ~2s parallel.

---

## Rate Limit Protection — Semaphore

```python
# Provider rate limit: 60 RPM
# If you fan-out 100 calls, you'll hit limits

CONCURRENT_LIMIT = 10  # max in-flight requests

async def rate_limited_ask(prompt: str, semaphore: asyncio.Semaphore):
    async with semaphore:  # blocks if 10 already in-flight
        return await ask(prompt)


async def batch_with_limit():
    semaphore = asyncio.Semaphore(CONCURRENT_LIMIT)
    prompts = [f"Question {i}" for i in range(100)]
    
    tasks = [rate_limited_ask(p, semaphore) for p in prompts]
    results = await asyncio.gather(*tasks)
    return results
```

Result: 100 calls processed 10-at-a-time, no rate limit hits.

---

## Fan-Out + Aggregate Pattern

```python
async def multi_perspective_answer(question: str) -> str:
    """Ask 3 different models, synthesize answer."""
    
    prompts = [
        f"Answer briefly: {question}",
        f"Answer with examples: {question}",
        f"Answer critically: {question}",
    ]
    
    # Fan out — 3 parallel calls
    answers = await asyncio.gather(*[ask(p) for p in prompts])
    
    # Fan in — 1 synthesis call
    synthesis = await ask(
        f"Synthesize these into one answer:\n\n"
        f"View 1: {answers[0]}\n\n"
        f"View 2: {answers[1]}\n\n"
        f"View 3: {answers[2]}"
    )
    return synthesis
```

---

## Embedding Batch (Cost-Efficient)

```python
# Instead of N separate calls, batch them
texts = ["doc1 content", "doc2 content", ..., "doc100 content"]

# One API call, batch of 100
response = await client.embeddings.create(
    model="text-embedding-3-small",
    input=texts,  # list, not single string
)

embeddings = [d.embedding for d in response.data]
```

**Why this matters:**
- 100 separate calls: 100 × API overhead + 100 × billing entries
- 1 batch call: 1 round-trip + bulk pricing (often 50% cheaper)

---

## Handling Mixed Success/Failure (return_exceptions)

```python
async def best_effort_batch(prompts: list[str]):
    """Don't crash whole batch if 1 call fails."""
    
    tasks = [ask(p) for p in prompts]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    successful = []
    failed = []
    for i, r in enumerate(results):
        if isinstance(r, Exception):
            failed.append((prompts[i], r))
        else:
            successful.append((prompts[i], r))
    
    print(f"Success: {len(successful)}, Failed: {len(failed)}")
    return successful, failed
```

---

## Progress Tracking (Many Calls)

```python
from tqdm.asyncio import tqdm

async def batch_with_progress(prompts):
    tasks = [ask(p) for p in prompts]
    results = []
    
    for f in tqdm.as_completed(tasks):
        result = await f
        results.append(result)
    
    return results
```

For UI: yield progress events:

```python
async def streaming_batch_progress(prompts):
    total = len(prompts)
    completed = 0
    
    async def wrapped(p):
        nonlocal completed
        result = await ask(p)
        completed += 1
        return result, completed
    
    tasks = [wrapped(p) for p in prompts]
    for f in asyncio.as_completed(tasks):
        result, count = await f
        yield {"progress": count / total, "result": result}
```

---

## Pipelining (Stream + Process Concurrently)

```python
async def doc_pipeline(documents: list[str]):
    """Process docs through 3 stages, pipeline-style."""
    
    # Stage 1: summarize (parallel, 5 at a time)
    sem = asyncio.Semaphore(5)
    
    async def summarize(doc):
        async with sem:
            return await ask(f"Summarize: {doc[:2000]}")
    
    summaries = await asyncio.gather(*[summarize(d) for d in documents])
    
    # Stage 2: extract entities (in parallel)
    async def extract(summary):
        async with sem:
            return await ask(f"Extract entities: {summary}")
    
    entities = await asyncio.gather(*[extract(s) for s in summaries])
    
    return list(zip(summaries, entities))
```

---

## Connection Pool + httpx Tuning

```python
import httpx
from openai import AsyncOpenAI

# Shared httpx client with bigger pool
http_client = httpx.AsyncClient(
    limits=httpx.Limits(max_connections=100, max_keepalive_connections=20),
    timeout=httpx.Timeout(60.0, connect=5.0),
)

client = AsyncOpenAI(http_client=http_client)
```

Higher pool = more concurrent calls without socket creation overhead.

---

## When to Use Sync vs Async

```
Use Async:
   ✓ Web servers (FastAPI, Starlette)
   ✓ Multiple LLM calls in one request
   ✓ Streaming responses
   ✓ Concurrent users (every backend)

Use Sync:
   ✓ Single-script automation
   ✓ Notebooks (mostly)
   ✓ Simple CLI tools
   
Mix them carefully:
   ✗ asyncio.run() inside sync function repeatedly = leak
   ✓ Use ProcessPoolExecutor / ThreadPoolExecutor for bridge
```

---

## FastAPI Integration

```python
from fastapi import FastAPI, BackgroundTasks
import asyncio

app = FastAPI()


@app.post("/batch-analyze")
async def batch(documents: list[str]):
    """User submits 50 docs, get analysis for each."""
    
    semaphore = asyncio.Semaphore(10)
    
    async def analyze(doc):
        async with semaphore:
            return await ask(f"Analyze: {doc}")
    
    results = await asyncio.gather(*[analyze(d) for d in documents])
    return {"results": results}
```

For long-running batches (>30s), use background tasks + status endpoint instead of blocking the request.

---

## Async Tool Calling in Loops

```python
async def agent_loop(question: str, max_steps=5):
    messages = [{"role": "user", "content": question}]
    
    for step in range(max_steps):
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            tools=TOOLS,
        )
        
        msg = response.choices[0].message
        messages.append(msg)
        
        if not msg.tool_calls:
            return msg.content  # final answer
        
        # Execute tool calls IN PARALLEL
        async def run_tool(tc):
            args = json.loads(tc.function.arguments)
            result = await tools[tc.function.name](**args)
            return {
                "role": "tool",
                "tool_call_id": tc.id,
                "content": json.dumps(result),
            }
        
        tool_results = await asyncio.gather(
            *[run_tool(tc) for tc in msg.tool_calls]
        )
        messages.extend(tool_results)
    
    raise Exception("max steps reached")
```

→ Parallel tool execution often 3-5x faster than sequential.

---

## Common Pitfalls

```
1. ✗ Forgetting await — coroutine never runs
   coro = ask("Hi")  # returns coroutine object
   ✓ result = await ask("Hi")

2. ✗ asyncio.gather without limit → rate limited
   ✓ Use Semaphore

3. ✗ Mixing sync (OpenAI) + async (AsyncOpenAI) clients
   ✓ Pick one consistently

4. ✗ Blocking call inside async function
   ✗ time.sleep(1) — blocks event loop!
   ✓ await asyncio.sleep(1)

5. ✗ Not handling partial failures
   gather() throws on any failure by default
   ✓ return_exceptions=True

6. ✗ asyncio.run() inside FastAPI handler
   ✓ FastAPI already runs in event loop — just await

7. ✗ Single httpx client per request
   ✓ Reuse client (connection pool)

8. ✗ Large fan-out (1000+ concurrent)
   ✓ Bound with semaphore, batch into chunks
```

---

## Interview Questions

### Q1: How do you batch 1000 LLM requests respecting rate limits?

Semaphore for concurrent limit + chunked batching for total throughput. Example: max 10 concurrent + chunks of 100 every 60s = 6000 RPH. Track usage from response headers, back off on 429s.

### Q2: When to use parallel vs sequential LLM calls?

Parallel when calls are independent (multi-doc summarization, A/B test, embedding batch). Sequential when output of N feeds into N+1 (agent reasoning loop, prompt chain).

### Q3: How do you handle one failed call in a parallel batch?

`asyncio.gather(*tasks, return_exceptions=True)` — failures returned as Exception objects in result list, others succeed. Decide per-app whether to retry, skip, or fail entire batch.

### Q4: How does async help with cost?

Cancellation: detect user disconnect early, abort in-flight calls. Concurrent batches: better throughput per worker = fewer servers. Embedding batches: 1 API call vs N saves overhead + sometimes bulk discount.

### Q5: What's wrong with calling `requests.get()` in an async function?

Blocks the event loop. While that call waits, no other coroutine runs — defeats async entirely. Use `httpx.AsyncClient` or async OpenAI SDK.

---

## Senior Mantras

```
1. AsyncOpenAI for all production work. Sync only for scripts.

2. Semaphore your fan-outs. Rate limits will bite.

3. Batch embeddings. 1 call beats 100.

4. return_exceptions=True for best-effort batches.

5. Reuse one httpx client. Connection pools matter.

6. Parallel tool calls in agent loops. 5x speedup.

7. Don't asyncio.gather() 1000 things. Chunk + semaphore.

8. Track concurrent count for cost forecasting.

9. Cancel on user disconnect. Save money.

10. async def + await = cheap. Use them liberally.
```

---

## Related

- [05_streaming_responses.md](05_streaming_responses.md)
- [07_error_handling_retries.md](07_error_handling_retries.md)
- [10_cost_optimization.md](10_cost_optimization.md)
- [../../Backend_Developer/Phase1_Python_Daily/Day31_Asyncio_Advanced/](../../Backend_Developer/Phase1_Python_Daily/Day31_Asyncio_Advanced/) — asyncio fundamentals
