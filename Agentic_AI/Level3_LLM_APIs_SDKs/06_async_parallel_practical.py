"""
Level3.6 — Async & Parallel LLM Calls: Complete Practical
==========================================================
KYA SEEKHENGE (What we will learn):
  1. asyncio basics — event loop, coroutine, await ka matlab
  2. AsyncOpenAI client se single async LLM call
  3. asyncio.gather se parallel fan-out (N calls ek saath)
  4. Semaphore se rate-limit protection (concurrent cap)
  5. Fan-out + Fan-in pattern (multi-perspective synthesis)
  6. return_exceptions=True — partial failure graceful handling
  7. Progress tracking — asyncio.as_completed se live counter
  8. Pipeline pattern — stage-by-stage parallel processing
  9. Sync vs Async comparison table
  10. Common pitfalls aur senior mantras

KAISE CHALANA (How to run):
  uv run /Users/youngmanindia/Documents/PythonRevision/Agentic_AI/Level3_LLM_APIs_SDKs/06_async_parallel_practical.py

  Ya /tmp se:
  cd /tmp && uv run --project /Users/youngmanindia/Documents/PythonRevision/Agentic_AI/my-agentic-ai-project python "/Users/youngmanindia/Documents/PythonRevision/Agentic_AI/Level3_LLM_APIs_SDKs/06_async_parallel_practical.py"

  Live LLM ke liye:
  GROQ_API_KEY=gsk_xxx uv run <file>

  Key nahi hai? No problem — script MOCK MODE mein chalega aur EXIT 0 karega.
"""

import asyncio
import os
import time
from typing import Optional

# ---------------------------------------------------------------------------
# CLIENT SETUP
# Groq free tier use karo by default (OpenAI ke barabar API, free mein!)
# GROQ_API_KEY nahi mila → placeholder lagao → MOCK_MODE on
# ---------------------------------------------------------------------------

# openai package AsyncOpenAI use karenge — Groq bhi same OpenAI-compatible API deta hai
try:
    from openai import AsyncOpenAI
    OPENAI_PKG_AVAILABLE = True
except ImportError:
    OPENAI_PKG_AVAILABLE = False


def get_client() -> Optional["AsyncOpenAI"]:
    """
    Groq ka free endpoint use karta hai by default.
    GROQ_API_KEY nahi mila → 'placeholder' dalo — client banao
    lekin asli call crash karega (MOCK_MODE pakad lega).

    INTERVIEW: Sync OpenAI() ko None key dene pe construction pe crash hota hai.
    Isliye placeholder string dete hain — graceful degrade ke liye.
    """
    if not OPENAI_PKG_AVAILABLE:
        return None

    api_key = os.getenv("GROQ_API_KEY") or "placeholder"
    base_url = "https://api.groq.com/openai/v1"

    return AsyncOpenAI(api_key=api_key, base_url=base_url)


# MOCK_MODE: koi real API key nahi mili → fake responses use karo
MOCK_MODE = not bool(os.getenv("GROQ_API_KEY"))

# Default model — Groq pe fast aur free
DEFAULT_MODEL = "llama3-8b-8192"


# ---------------------------------------------------------------------------
# HELPER: Async LLM call (real ya mock)
# ---------------------------------------------------------------------------

async def ask(
    prompt: str,
    client: Optional["AsyncOpenAI"] = None,
    model: str = DEFAULT_MODEL,
    max_tokens: int = 80,
) -> str:
    """
    Single async LLM call — yahi building block hai baaki sab patterns ka.

    MOCK_MODE mein: seedha fake response return karo — no network needed.
    Real mode mein: await karo Groq API ka.

    INTERVIEW pitfall: await bhool gaye? Coroutine object milega, response nahi!
      Wrong:  result = ask("Hi")   # sirf coroutine object
      Right:  result = await ask("Hi")  # actual string
    """
    if MOCK_MODE or client is None:
        # Thoda simulate karo async delay — jaise real network hoti hai
        await asyncio.sleep(0.05)
        # Prompt ke pehle 40 chars use karo mock response mein
        snippet = prompt[:40].replace("\n", " ")
        return f"[MOCK] Response for: '{snippet}...'"

    response = await client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=max_tokens,
    )
    return response.choices[0].message.content


# ---------------------------------------------------------------------------
# SECTION 1: asyncio Fundamentals — Theory + Demo
# ---------------------------------------------------------------------------

print("=" * 65)
print("SECTION 1: asyncio Fundamentals — Event Loop, Coroutine, Await")
print("=" * 65)

ASYNCIO_CONCEPTS = {
    "async def":        "Coroutine function banata hai — immediately execute nahi hoti",
    "await":            "Coroutine ko run karo aur result ka wait karo",
    "Event Loop":       "Ek thread mein N coroutines manage karta hai (asyncio.run se start)",
    "asyncio.gather":   "N coroutines ek saath chalao, saari complete hone pe list return",
    "asyncio.Semaphore":"Max concurrent limit lagao — rate limit se bachao",
    "asyncio.sleep":    "Non-blocking sleep — time.sleep use karna event loop block karta hai!",
    "asyncio.as_completed": "Jo pehle complete ho uska result pehle milega (progress tracking)",
    "return_exceptions":"gather mein — ek failure puri batch nahi rokti",
}

print()
for concept, explanation in ASYNCIO_CONCEPTS.items():
    print(f"  {concept:<25}: {explanation}")

print("""
  BLOCKING vs NON-BLOCKING:
    time.sleep(2)           -- event loop RUKA. Koi aur coroutine nahi chal sakta.
    await asyncio.sleep(2)  -- event loop FREE. Doosri coroutines chalti rehti hain.

  SEQUENTIAL vs PARALLEL (Real numbers):
    Sequential: 10 LLM calls x 2 sec = 20 seconds total
    Parallel:   10 LLM calls ek saath = ~2 seconds total  (10x speedup!)
""")


# ---------------------------------------------------------------------------
# SECTION 2: Single Async Call
# ---------------------------------------------------------------------------

print("=" * 65)
print("SECTION 2: Single Async LLM Call — Basic Pattern")
print("=" * 65)

SINGLE_CALL_CODE = '''\
from openai import AsyncOpenAI
import asyncio

# Groq ke liye base_url change karo, baaki same
client = AsyncOpenAI(
    api_key  = os.getenv("GROQ_API_KEY") or "placeholder",
    base_url = "https://api.groq.com/openai/v1",
)

async def ask(prompt: str) -> str:
    response = await client.chat.completions.create(
        model    = "llama3-8b-8192",   # Groq free model
        messages = [{"role": "user", "content": prompt}],
        max_tokens = 100,
    )
    return response.choices[0].message.content

async def main():
    # Single call
    answer = await ask("Python mein async kya hota hai?")
    print(answer)

asyncio.run(main())   # <-- Entry point: event loop start karo
'''
print(SINGLE_CALL_CODE)
print("  Note: asyncio.run() ek NAYA event loop banata hai.")
print("  FastAPI ke andar asyncio.run() mat karo — wahan already loop chal rahi hoti hai.")


# ---------------------------------------------------------------------------
# SECTION 3: Parallel Calls — asyncio.gather
# ---------------------------------------------------------------------------

print("\n" + "=" * 65)
print("SECTION 3: Parallel Fan-Out — asyncio.gather")
print("=" * 65)

GATHER_CODE = '''\
async def parallel_questions(client):
    questions = [
        "Python mein async kya hota hai?",
        "await keyword ka kya matlab hai?",
        "Event loop kaise kaam karta hai?",
        "Coroutine aur thread mein farak kya hai?",
    ]

    # STEP 1: Saare tasks ek list mein banao (abhi kuch nahi chala)
    tasks = [ask(q, client) for q in questions]

    # STEP 2: Sab ek saath launch karo, saare complete hone ka wait karo
    # INTERVIEW: asyncio.gather = fan-out pattern
    answers = await asyncio.gather(*tasks)

    for q, a in zip(questions, answers):
        print(f"  Q: {q}")
        print(f"  A: {a[:80]}")
        print()
'''
print(GATHER_CODE)


async def demo_parallel_gather():
    """Section 3 ka live demo — timing bhi dikhata hai."""
    client = get_client()

    prompts = [
        "Python mein async kya hota hai? 1 line mein batao.",
        "await keyword kab use karte hain? 1 line mein.",
        "Event loop kya hota hai? 1 line mein.",
        "asyncio.gather ka kya kaam hai? 1 line mein.",
    ]

    print(f"  {len(prompts)} questions parallel mein bhej rahe hain...")
    start = time.perf_counter()

    # Fan-out — saare tasks ek saath chalte hain
    tasks = [ask(p, client) for p in prompts]
    answers = await asyncio.gather(*tasks)

    elapsed = time.perf_counter() - start
    print(f"  Saari calls complete — {elapsed:.2f}s mein (parallel!)\n")

    for i, (q, a) in enumerate(zip(prompts, answers), 1):
        print(f"  [{i}] Q: {q[:50]}")
        print(f"      A: {a[:70]}")
    print()


asyncio.run(demo_parallel_gather())


# ---------------------------------------------------------------------------
# SECTION 4: Rate Limit Protection — Semaphore
# ---------------------------------------------------------------------------

print("=" * 65)
print("SECTION 4: Semaphore se Rate Limit Protection")
print("=" * 65)

SEMAPHORE_CODE = '''\
# Problem: 100 calls ek saath bhejo → provider rate limit hit!
# Solution: Semaphore lagao — maximum N calls hi ek waqt mein

CONCURRENT_LIMIT = 5  # ek waqt mein sirf 5 calls in-flight

async def rate_limited_ask(prompt: str, semaphore: asyncio.Semaphore, client) -> str:
    async with semaphore:          # <-- agar 5 already chal rahe to yahan RUKO
        return await ask(prompt, client)

async def batch_with_semaphore(prompts: list[str], client) -> list[str]:
    semaphore = asyncio.Semaphore(CONCURRENT_LIMIT)
    # Sab tasks banao — semaphore automatically throttle karega
    tasks = [rate_limited_ask(p, semaphore, client) for p in prompts]
    return await asyncio.gather(*tasks)

# Result: 100 calls → 5 at a time → no rate limit hits!
# Throughput: 100 / 5 = 20 rounds (sequential within each round)
'''
print(SEMAPHORE_CODE)

print("  INTERVIEW Q: 1000 LLM requests ko rate limit se bachate hue kaise process karoge?")
print("  A: asyncio.Semaphore(10) → sirf 10 concurrent, baki wait karenge.")
print("     Plus: 429 response pe exponential backoff (Section 7 mein dekho).")
print()


async def demo_semaphore():
    """Semaphore demo — limit=3, 8 tasks."""
    client = get_client()
    LIMIT = 3
    semaphore = asyncio.Semaphore(LIMIT)

    in_flight = [0]  # mutable counter for closure

    async def tracked_ask(prompt: str, idx: int) -> str:
        async with semaphore:
            in_flight[0] += 1
            # Real mode mein: print karo agar concurrency check karni hai
            result = await ask(prompt, client)
            in_flight[0] -= 1
            return result

    prompts = [f"Question {i}: Python topic {i} samjhao briefly." for i in range(8)]
    print(f"  {len(prompts)} tasks, concurrent limit={LIMIT}...")
    start = time.perf_counter()

    tasks = [tracked_ask(p, i) for i, p in enumerate(prompts)]
    results = await asyncio.gather(*tasks)

    elapsed = time.perf_counter() - start
    print(f"  {len(results)} results mila, {elapsed:.2f}s mein.")
    print(f"  Pehla result: {results[0][:60]}")
    print()


asyncio.run(demo_semaphore())


# ---------------------------------------------------------------------------
# SECTION 5: Fan-Out + Fan-In Pattern
# ---------------------------------------------------------------------------

print("=" * 65)
print("SECTION 5: Fan-Out + Fan-In — Multi-Perspective Synthesis")
print("=" * 65)

FAN_OUT_CODE = '''\
async def multi_perspective_answer(question: str, client) -> str:
    """
    PATTERN: Fan-Out → 3 parallel views → Fan-In synthesis
    Use case: Research, complex QnA, A/B comparison

    Fan-Out:
      Prompt 1: "briefly explain: {question}"
      Prompt 2: "explain with examples: {question}"
      Prompt 3: "critically evaluate: {question}"
      (sab parallel mein chalte hain)

    Fan-In:
      Synthesis call: "Teeno views ko ek mein merge karo"
    """
    prompts = [
        f"Briefly explain in 2 lines: {question}",
        f"Give 1 real-world example for: {question}",
        f"One limitation or tradeoff of: {question}",
    ]

    # Fan-Out — 3 parallel calls
    views = await asyncio.gather(*[ask(p, client) for p in prompts])

    # Fan-In — ek synthesis call
    synthesis_prompt = (
        f"Question: {question}\\n\\n"
        f"View 1 (brief): {views[0]}\\n"
        f"View 2 (example): {views[1]}\\n"
        f"View 3 (limitation): {views[2]}\\n\\n"
        f"Inhe ek coherent 3-line answer mein merge karo."
    )
    final = await ask(synthesis_prompt, client)
    return final
'''
print(FAN_OUT_CODE)


async def demo_fan_out_fan_in():
    """Fan-Out + Fan-In live demo."""
    client = get_client()
    question = "Python mein asyncio.gather kya karta hai?"

    print(f"  Question: {question}")
    print("  Fan-Out: 3 parallel views bhej rahe hain...")
    start = time.perf_counter()

    prompts = [
        f"Briefly explain in 2 lines: {question}",
        f"Give 1 real-world example for: {question}",
        f"One limitation or tradeoff of: {question}",
    ]

    views = await asyncio.gather(*[ask(p, client) for p in prompts])
    fan_out_time = time.perf_counter() - start
    print(f"  Fan-Out complete in {fan_out_time:.2f}s")
    for i, v in enumerate(views, 1):
        print(f"    View {i}: {v[:70]}")

    # Fan-In
    synthesis_prompt = (
        f"Question: {question}\n\n"
        f"View 1 (brief): {views[0]}\n"
        f"View 2 (example): {views[1]}\n"
        f"View 3 (tradeoff): {views[2]}\n\n"
        "Inhe ek coherent 3-line answer mein merge karo."
    )
    print("\n  Fan-In: synthesis call...")
    final = await ask(synthesis_prompt, client)
    total_time = time.perf_counter() - start
    print(f"  Final synthesized answer ({total_time:.2f}s total):")
    print(f"    {final[:120]}")
    print()


asyncio.run(demo_fan_out_fan_in())


# ---------------------------------------------------------------------------
# SECTION 6: Partial Failure Handling — return_exceptions=True
# ---------------------------------------------------------------------------

print("=" * 65)
print("SECTION 6: Partial Failure — return_exceptions=True")
print("=" * 65)

EXCEPTIONS_CODE = '''\
async def best_effort_batch(prompts: list[str], client) -> tuple:
    """
    INTERVIEW: asyncio.gather default behavior —
      agar ek task fail hua → sari gather fail ho jaati hai!

    return_exceptions=True lagao:
      Failed tasks Exception objects return karte hain (crash nahi karte).
      Baaki tasks normally complete hote hain.
    """
    tasks = [ask(p, client) for p in prompts]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    successful = []
    failed = []
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            failed.append((prompts[i], str(result)))
        else:
            successful.append((prompts[i], result))

    print(f"  Success: {len(successful)}, Failed: {len(failed)}")
    return successful, failed
'''
print(EXCEPTIONS_CODE)


async def demo_partial_failure():
    """Partial failure demo — kuch tasks fail honge (intentionally)."""
    client = get_client()

    async def ask_maybe_fail(prompt: str, should_fail: bool) -> str:
        """Mock mein manually fail karate hain kuch tasks."""
        if should_fail:
            raise ValueError(f"Simulated failure for: '{prompt[:30]}'")
        return await ask(prompt, client)

    prompts_and_flags = [
        ("Python kya hai?", False),
        ("asyncio samjhao", False),
        ("FAIL karo isko", True),   # ye fail hoga
        ("Groq kya hai?", False),
        ("YAAR FAIL!", True),       # ye bhi fail hoga
    ]

    tasks = [ask_maybe_fail(p, f) for p, f in prompts_and_flags]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    successful = [(prompts_and_flags[i][0], r) for i, r in enumerate(results) if not isinstance(r, Exception)]
    failed     = [(prompts_and_flags[i][0], r) for i, r in enumerate(results) if isinstance(r, Exception)]

    print(f"  Total tasks: {len(results)}")
    print(f"  Success: {len(successful)} | Failed: {len(failed)}")
    for p, r in successful:
        print(f"    OK   : {p} → {str(r)[:50]}")
    for p, e in failed:
        print(f"    FAIL : {p} → {e}")
    print()


asyncio.run(demo_partial_failure())


# ---------------------------------------------------------------------------
# SECTION 7: Progress Tracking — asyncio.as_completed
# ---------------------------------------------------------------------------

print("=" * 65)
print("SECTION 7: Progress Tracking — asyncio.as_completed")
print("=" * 65)

PROGRESS_CODE = '''\
async def batch_with_progress(prompts: list[str], client) -> list[str]:
    """
    asyncio.as_completed — jo task pehle complete ho, uska result pehle milega.
    asyncio.gather ke ULTa — gather sab complete hone ka wait karta hai.

    Use case: UI mein live progress bar dikhana — tqdm ya custom counter.
    """
    tasks = [ask(p, client) for p in prompts]
    total = len(tasks)
    results = []

    # Jo bhi pehle complete ho, usse process karo
    for i, future in enumerate(asyncio.as_completed(tasks), 1):
        result = await future
        results.append(result)
        percent = int(i / total * 100)
        # UI mein yahan websocket event bhejo ya tqdm update karo
        print(f"  Progress: [{i}/{total}] {percent}% | {str(result)[:50]}")

    return results

# Note: as_completed se ORDER guarantee nahi hoti!
# Gather se order guarantee hoti hai (input ke same order mein output).
'''
print(PROGRESS_CODE)


async def demo_progress_tracking():
    """Progress tracking live demo."""
    client = get_client()
    prompts = [f"Topic {i}: batao 1 line mein kya hai ye Python concept {i}" for i in range(1, 7)]

    print(f"  {len(prompts)} tasks — progress dekhte hain jab bhi koi complete ho:\n")
    tasks = [ask(p, client) for p in prompts]
    completed = 0

    for future in asyncio.as_completed(tasks):
        result = await future
        completed += 1
        bar = "#" * completed + "-" * (len(prompts) - completed)
        print(f"  [{bar}] {completed}/{len(prompts)} | {str(result)[:55]}")

    print()


asyncio.run(demo_progress_tracking())


# ---------------------------------------------------------------------------
# SECTION 8: Pipeline Pattern — Stage-by-Stage Parallel Processing
# ---------------------------------------------------------------------------

print("=" * 65)
print("SECTION 8: Pipeline Pattern — Stage 1 → Stage 2 Parallel")
print("=" * 65)

PIPELINE_CODE = '''\
async def doc_pipeline(documents: list[str], client) -> list[tuple]:
    """
    Pipeline = multiple sequential stages, each stage parallel.

    Stage 1: Summarize (5 concurrent max)
    Stage 2: Extract key topics (5 concurrent max)

    INTERVIEW: Ye pattern multi-doc RAG indexing mein common hai.
    Stage ke beech mein dependency hoti hai (Stage 2 ko Stage 1 ka output chahiye).
    Stage ke andar independent hain (parallel chalte hain).
    """
    sem = asyncio.Semaphore(5)   # dono stages mein same semaphore use kar sakte hain

    # Stage 1: Summarize
    async def summarize(doc: str) -> str:
        async with sem:
            return await ask(f"Summarize in 1 sentence: {doc[:300]}", client)

    summaries = await asyncio.gather(*[summarize(d) for d in documents])
    print(f"  Stage 1 done: {len(summaries)} summaries")

    # Stage 2: Extract key topic
    async def extract_topic(summary: str) -> str:
        async with sem:
            return await ask(f"Key topic in 3 words: {summary}", client)

    topics = await asyncio.gather(*[extract_topic(s) for s in summaries])
    print(f"  Stage 2 done: {len(topics)} topics extracted")

    return list(zip(summaries, topics))
'''
print(PIPELINE_CODE)


async def demo_pipeline():
    """Pipeline demo — 2 stages, 4 documents."""
    client = get_client()
    documents = [
        "Python asyncio module allows writing concurrent code using the async/await syntax.",
        "Groq is an AI inference company offering fast LLM APIs using custom LPU hardware.",
        "FastAPI is a modern Python web framework built on top of Starlette and Pydantic.",
        "Semaphore is a concurrency primitive that limits the number of simultaneous operations.",
    ]

    print(f"  {len(documents)} documents ko pipeline se process kar rahe hain...\n")
    sem = asyncio.Semaphore(3)

    async def summarize(doc: str) -> str:
        async with sem:
            return await ask(f"1 sentence mein summarize karo: {doc}", client)

    async def extract_topic(summary: str) -> str:
        async with sem:
            return await ask(f"3 words mein key topic batao: {summary}", client)

    # Stage 1
    summaries = await asyncio.gather(*[summarize(d) for d in documents])
    print("  Stage 1 (Summarize) complete:")
    for i, s in enumerate(summaries, 1):
        print(f"    Doc {i}: {s[:70]}")

    # Stage 2
    topics = await asyncio.gather(*[extract_topic(s) for s in summaries])
    print("\n  Stage 2 (Topics) complete:")
    for i, t in enumerate(topics, 1):
        print(f"    Doc {i} topic: {t[:50]}")
    print()


asyncio.run(demo_pipeline())


# ---------------------------------------------------------------------------
# SECTION 9: Timing Comparison — Sequential vs Parallel
# ---------------------------------------------------------------------------

print("=" * 65)
print("SECTION 9: Sequential vs Parallel — Timing Demo")
print("=" * 65)


async def demo_timing_comparison():
    """Sequential aur parallel ka actual time compare karo."""
    client = get_client()
    N = 6
    prompts = [f"Question {i}: asyncio concept {i} briefly batao." for i in range(N)]

    # --- Sequential (ek ke baad ek) ---
    print(f"  Sequential: {N} calls ek ke baad ek...")
    start = time.perf_counter()
    sequential_results = []
    for p in prompts:
        r = await ask(p, client)
        sequential_results.append(r)
    seq_time = time.perf_counter() - start
    print(f"  Sequential time: {seq_time:.3f}s")

    # --- Parallel (sab ek saath) ---
    print(f"\n  Parallel: {N} calls ek saath (asyncio.gather)...")
    start = time.perf_counter()
    parallel_results = await asyncio.gather(*[ask(p, client) for p in prompts])
    par_time = time.perf_counter() - start
    print(f"  Parallel time: {par_time:.3f}s")

    if par_time > 0:
        speedup = seq_time / par_time
        print(f"\n  Speedup: {speedup:.1f}x faster (parallel)")
        if MOCK_MODE:
            print("  (MOCK MODE mein difference chhota dikhega — real API pe 5-10x hoga)")
    print()


asyncio.run(demo_timing_comparison())


# ---------------------------------------------------------------------------
# SECTION 10: Sync vs Async — When to Use What
# ---------------------------------------------------------------------------

print("=" * 65)
print("SECTION 10: Sync vs Async — Kab Kya Use Karein")
print("=" * 65)

SYNC_VS_ASYNC = {
    "FastAPI / Starlette backend":      ("Async", "Ek request mein multiple LLM calls"),
    "Jupyter Notebook (quick test)":    ("Sync",  "Simple hai, loop already running hoti hai"),
    "CLI automation script":            ("Sync",  "Ek kaam, koi concurrency nahi"),
    "Multi-doc summarization":          ("Async", "Har doc = 1 parallel call — 10x faster"),
    "Streaming responses to browser":   ("Async", "SSE / WebSocket = async required"),
    "Batch embedding 1000 texts":       ("Async", "1 API call (batch) ya parallel calls"),
    "Agent loop (tool calling)":        ("Async", "Parallel tool execution — 3-5x faster"),
    "Simple one-shot prompt":           ("Sync",  "Async overkill hai yahan"),
}

print(f"\n  {'Use Case':<40} {'Sync/Async':<12} Reason")
print("  " + "-" * 70)
for use_case, (kind, reason) in SYNC_VS_ASYNC.items():
    tag = f"[{kind}]"
    print(f"  {use_case:<40} {tag:<12} {reason}")

print("""
  RULE: Agar N independent LLM calls hain → ASYNC use karo.
        Agar ek call ki output agla call ka input hai → SEQUENTIAL (still async).
        FastAPI ke andar → KABHI asyncio.run() mat karo (loop already chal rahi hai).
""")


# ---------------------------------------------------------------------------
# SECTION 11: Common Pitfalls
# ---------------------------------------------------------------------------

print("=" * 65)
print("SECTION 11: Common Pitfalls — Ye Galti Mat Karna")
print("=" * 65)

PITFALLS = [
    (
        "await bhool gaye",
        "coro = ask('Hi')  # coroutine object mila, result nahi!",
        "result = await ask('Hi')",
    ),
    (
        "Semaphore nahi lagaya",
        "asyncio.gather(*[ask(p) for p in 1000_prompts])  # rate limit blast!",
        "asyncio.Semaphore(10) use karo",
    ),
    (
        "time.sleep in async function",
        "async def foo():\n    time.sleep(2)  # EVENT LOOP BLOCK! Baki coroutines freeze",
        "await asyncio.sleep(2)  # non-blocking",
    ),
    (
        "Sync OpenAI client in async context",
        "client = OpenAI()  # sync client, await nahi kar sakte",
        "client = AsyncOpenAI()  # async version use karo",
    ),
    (
        "return_exceptions bhool gaye",
        "results = await asyncio.gather(*tasks)  # 1 fail = sab fail",
        "results = await asyncio.gather(*tasks, return_exceptions=True)",
    ),
    (
        "asyncio.run() in FastAPI",
        "@app.get('/') async def route():\n    asyncio.run(some_coro())  # CRASH — nested loop",
        "result = await some_coro()  # seedha await karo",
    ),
    (
        "1000 tasks bina limit ke",
        "asyncio.gather(*[ask(p) for p in 1000_items])  # socket exhaustion",
        "Semaphore(20) + chunked batching",
    ),
]

print()
for i, (name, wrong, right) in enumerate(PITFALLS, 1):
    print(f"  Pitfall {i}: {name}")
    print(f"    WRONG : {wrong}")
    print(f"    RIGHT : {right}")
    print()


# ---------------------------------------------------------------------------
# SECTION 12: Interview Q&A
# ---------------------------------------------------------------------------

print("=" * 65)
print("SECTION 12: Interview Questions & Answers")
print("=" * 65)

QNA = [
    (
        "Q1: 1000 LLM requests respecting rate limits kaise process karo?",
        "asyncio.Semaphore(10) → sirf 10 concurrent. Chunked batching bhi karo\n"
        "     (chunks of 100, 60s interval). 429 response pe exponential backoff.",
    ),
    (
        "Q2: Parallel vs Sequential — kab kaunsa?",
        "Parallel: calls independent hain (multi-doc, A/B test, embedding batch).\n"
        "     Sequential: ek call ka output agla call ka input (agent reasoning chain).",
    ),
    (
        "Q3: Ek failed call parallel batch mein kaise handle karein?",
        "asyncio.gather(*tasks, return_exceptions=True) — failure Exception object\n"
        "     return karta hai, string nahi. Loop mein isinstance(r, Exception) check karo.",
    ),
    (
        "Q4: Async se cost kaise bachai ja sakti hai?",
        "1. Cancellation: user disconnect detect karo, in-flight call abort karo.\n"
        "     2. Higher throughput per worker → fewer servers needed.\n"
        "     3. Embedding batching: 100 separate calls ki jagah 1 batch call.",
    ),
    (
        "Q5: requests.get() async function ke andar kyon galat hai?",
        "Blocking call hai — event loop ruk jaata hai. Koi aur coroutine nahi\n"
        "     chal sakta jab tak ye complete na ho. httpx.AsyncClient ya AsyncOpenAI use karo.",
    ),
    (
        "Q6: asyncio.gather vs asyncio.as_completed mein farak?",
        "gather: sabke complete hone ka wait karta hai, ORDER maintain karta hai.\n"
        "     as_completed: jo pehle done ho uska result pehle milta hai (progress tracking).",
    ),
]

print()
for q, a in QNA:
    print(f"  {q}")
    print(f"     {a}")
    print()


# ---------------------------------------------------------------------------
# SECTION 13: Senior Mantras (Theory Doc se)
# ---------------------------------------------------------------------------

print("=" * 65)
print("SECTION 13: Senior Mantras — Yaad Rakhna")
print("=" * 65)

MANTRAS = [
    "AsyncOpenAI production mein use karo. Sync sirf simple scripts ke liye.",
    "Semaphore lagao har fan-out pe. Rate limits zaroor aayenge.",
    "Embedding batch karo. 1 API call 100 separate se behtar hai.",
    "return_exceptions=True — best-effort batch ke liye must-have.",
    "Ek httpx client reuse karo. Connection pool matter karta hai.",
    "Agent loops mein parallel tool calls karo. 5x speedup milta hai.",
    "1000+ concurrent mat karo. Chunk + Semaphore se control mein raho.",
    "Concurrent count track karo — cost forecasting ke liye useful.",
    "User disconnect pe cancel karo. Paise bachte hain.",
    "async def + await = cheap. Liberally use karo.",
]

print()
for i, mantra in enumerate(MANTRAS, 1):
    print(f"  {i:>2}. {mantra}")

print()


# ---------------------------------------------------------------------------
# FINAL SUMMARY
# ---------------------------------------------------------------------------

print("=" * 65)
print("ASYNC PARALLEL LLM CALLS — FINAL SUMMARY")
print("=" * 65)
print("""
  Core pattern:
    async def ask(prompt, client) -> str:          # building block
        return await client.chat.completions.create(...)

  Fan-Out (N parallel):
    results = await asyncio.gather(*[ask(p) for p in prompts])

  Rate Limit Protection:
    sem = asyncio.Semaphore(10)
    async with sem:
        return await ask(prompt, client)

  Partial Failure:
    results = await asyncio.gather(*tasks, return_exceptions=True)

  Progress:
    for future in asyncio.as_completed(tasks):
        result = await future   # jo pehle done wo pehle milega

  Pipeline:
    stage1 = await asyncio.gather(*[step1(x) for x in inputs])
    stage2 = await asyncio.gather(*[step2(x) for x in stage1])

  Golden Rule:
    Independent calls → PARALLEL (asyncio.gather)
    Dependent calls  → SEQUENTIAL (await ek ke baad ek)
    Always           → Semaphore lagao fan-out pe
""")

if MOCK_MODE:
    print("  [MOCK MODE] Real calls ke liye GROQ_API_KEY set karo (free at console.groq.com)")
else:
    print("  [LIVE MODE] Groq API use ho rahi hai.")

print("=" * 65)
print("  Script complete. EXIT 0.")
print("=" * 65)
