# Level 4 — Doc 6: Parallel Tool Calls

> **Goal:** Multiple tools simultaneously execute karna. Latency 5x kam, throughput up.

---

## 1. Why Parallel?

If LLM needs 5 pieces of info:
- **Sequential:** 5 × 500ms = 2.5 seconds
- **Parallel:** max(500ms) = 500ms

Both OpenAI and Claude **request** multiple tools at once. YOU execute them in parallel.

---

## 2. When LLM Calls Tools in Parallel

LLM picks parallel when:
- Independent data needed (e.g., weather in 3 cities)
- No dependency between calls
- Same tool with different args

LLM picks **sequential** when:
- One tool's output feeds another (chain)
- Dependent operations

### Examples:
```
"Weather in Mumbai, Delhi, Bangalore" → parallel (3 weather calls)
"Search Tesla, then email me summary" → sequential (search → summarize → email)
"Cancel my order and refund payment" → sequential (cancel first)
```

---

## 3. Parallel Execution Pattern

```python
from concurrent.futures import ThreadPoolExecutor

def execute_tool_calls_parallel(tool_calls, tool_functions):
    """Execute all tool calls in parallel."""
    
    def run_one(tc):
        name = tc.function.name
        args = json.loads(tc.function.arguments)
        try:
            return tc.id, tool_functions[name](**args)
        except Exception as e:
            return tc.id, {"error": str(e)}
    
    with ThreadPoolExecutor(max_workers=10) as executor:
        results = dict(executor.map(run_one, tool_calls))
    
    return results
```

---

## 4. Async/Await Pattern (Better for I/O Tools)

For network-bound tools, async is more efficient than threads:

```python
import asyncio
import aiohttp

async def async_search(query: str):
    async with aiohttp.ClientSession() as session:
        async with session.get(f"https://api.search?q={query}") as resp:
            return await resp.json()

async def execute_parallel_async(tool_calls):
    """Execute all tool calls asynchronously."""
    
    async def run_one(tc):
        name = tc.function.name
        args = json.loads(tc.function.arguments)
        result = await ASYNC_TOOL_FUNCTIONS[name](**args)
        return tc.id, result
    
    tasks = [run_one(tc) for tc in tool_calls]
    results = await asyncio.gather(*tasks)
    return dict(results)
```

---

## 5. With Timeouts

```python
from concurrent.futures import ThreadPoolExecutor, TimeoutError

def execute_with_timeout(tool_calls, tool_functions, per_tool_timeout=10):
    results = {}
    with ThreadPoolExecutor(max_workers=10) as executor:
        future_to_tc = {
            executor.submit(_run_one, tc, tool_functions): tc
            for tc in tool_calls
        }
        for future in future_to_tc:
            tc = future_to_tc[future]
            try:
                results[tc.id] = future.result(timeout=per_tool_timeout)
            except TimeoutError:
                results[tc.id] = {"error": f"timeout after {per_tool_timeout}s"}
    return results
```

---

## 6. Mixed Sync + Async Tools

Real systems have both. Use `asyncio.run_in_executor` for sync tools:

```python
async def execute_mixed(tool_calls, sync_tools, async_tools):
    loop = asyncio.get_event_loop()
    
    async def run_one(tc):
        name = tc.function.name
        args = json.loads(tc.function.arguments)
        if name in async_tools:
            result = await async_tools[name](**args)
        else:
            # Run sync tool in thread pool.
            # NOTE: run_in_executor kwargs accept NAHI karta (signature: executor, func, *args).
            # **args seedha bhejoge to TypeError — functools.partial se kwargs bind karo:
            result = await loop.run_in_executor(
                None, functools.partial(sync_tools[name], **args)
            )
        return tc.id, result
    
    return dict(await asyncio.gather(*[run_one(tc) for tc in tool_calls]))
```

---

## 7. Production Considerations

### Limit concurrency
Don't run 1000 parallel calls — overwhelms APIs.
```python
ThreadPoolExecutor(max_workers=10)  # Limit
# Or: asyncio.Semaphore(10)
```

### Cost monitoring
Parallel = more requests in short time = harder to monitor.

```python
@track_cost
async def tool_call(...): ...
```

### Rate limits
External APIs (search, weather) have rate limits.
```python
# Bucket-style rate limiter
from asyncio import Semaphore
api_limit = Semaphore(50)  # Max 50 concurrent calls

async def rate_limited_call(...):
    async with api_limit:
        return await actual_call(...)
```

### Partial failures
If 4 of 5 tools succeed, return what you have:
```python
results = await asyncio.gather(*tasks, return_exceptions=True)
# Each result might be an exception — handle individually
```

---

## 8. Anthropic Claude — Parallel by Default

Claude often picks parallel naturally:
```python
# Multiple tool_use blocks in one response
[
    ToolUseBlock(name="get_weather", input={"city": "Mumbai"}),
    ToolUseBlock(name="get_weather", input={"city": "Delhi"}),
    ToolUseBlock(name="get_stock", input={"symbol": "AAPL"}),
]
```

You execute them parallel, send all results back in one user message.

### Disable parallel (force one at a time):
```python
tool_choice={"type": "auto", "disable_parallel_tool_use": True}
```

---

## 9. Common Pitfalls

### Pitfall 1: Shared state issues
```python
# Bad — shared mutable state
results = []
def tool_func(x):
    results.append(x)  # ← Race condition!

# Good — return value, don't mutate
def tool_func(x):
    return {"value": x}
```

### Pitfall 2: Database connections
```python
# Bad — single connection used by N threads
conn = create_connection()

def db_tool(query):
    return conn.execute(query)  # Thread-unsafe!

# Good — connection pool
pool = create_pool()

def db_tool(query):
    with pool.acquire() as conn:
        return conn.execute(query)
```

### Pitfall 3: Long-tail latency
If 1 of 10 tools is slow, total = slow tool's time.
Use timeouts + partial results.

---

## 10. Measuring Parallel Speedup

```python
import time

def measure(func, *args, **kwargs):
    start = time.time()
    result = func(*args, **kwargs)
    elapsed = time.time() - start
    return result, elapsed

# Sequential
_, t_seq = measure(execute_sequential, tool_calls)
# Parallel
_, t_par = measure(execute_parallel, tool_calls)

print(f"Sequential: {t_seq:.2f}s")
print(f"Parallel:   {t_par:.2f}s")
print(f"Speedup:    {t_seq / t_par:.1f}x")
```

---

## 11. Interview Questions

1. **Q: When does LLM call tools in parallel?**
   - When tools are independent (no data dependencies)

2. **Q: ThreadPool vs asyncio?**
   - Threads: CPU work or sync libraries. Async: network/IO heavy.

3. **Q: How to handle partial failures?**
   - Return exceptions from gather, handle each result individually

4. **Q: How to prevent overwhelming an API?**
   - Limit max_workers, use semaphores, respect rate limits

---

## 12. Key Takeaways

✅ Parallel = N tools in time of slowest one
✅ Use ThreadPoolExecutor for sync tools, asyncio for async I/O
✅ Add timeouts per tool
✅ Limit max concurrency (prevent API overload)
✅ Handle partial failures gracefully
✅ Claude does parallel by default; OpenAI via `parallel_tool_calls=True`

**Next:** [07_tool_use_loop.md](07_tool_use_loop.md) — Deeper into the agent loop
