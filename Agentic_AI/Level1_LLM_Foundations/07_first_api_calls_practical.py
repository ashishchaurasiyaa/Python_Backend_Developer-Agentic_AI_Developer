"""
Level 1 — Doc 7: First API Calls (PRACTICAL)
==============================================
Topics covered:
  1. Hello World — OpenAI + Claude
  2. System prompts comparison
  3. Streaming responses
  4. Multi-turn conversation
  5. Token counting + cost estimation
  6. Error handling + retry
  7. LiteLLM unified interface
  8. Async parallel calls
  9. Mini chatbot end-to-end

Install:
  pip install openai anthropic litellm tiktoken tenacity python-dotenv

Run: python 07_first_api_calls_practical.py
"""

import os
import asyncio
import time
from typing import Optional
from dotenv import load_dotenv

load_dotenv()


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 1: Env Validation
# ─────────────────────────────────────────────────────────────────────────────

print("=" * 70)
print("SECTION 1: Environment Validation")
print("=" * 70)

REQUIRED_KEYS = ["OPENAI_API_KEY", "ANTHROPIC_API_KEY"]
OPTIONAL_KEYS = ["GEMINI_API_KEY", "TAVILY_API_KEY", "LANGCHAIN_API_KEY"]

for key in REQUIRED_KEYS:
    status = "✓" if os.getenv(key) else "✗ MISSING"
    print(f"  {key}: {status}")

print("\nOptional:")
for key in OPTIONAL_KEYS:
    status = "✓" if os.getenv(key) else "○ not set"
    print(f"  {key}: {status}")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 2: Hello World
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("SECTION 2: Hello World — OpenAI + Claude")
print("=" * 70)


def openai_hello():
    if not os.getenv("OPENAI_API_KEY"):
        return "[NO_API_KEY]"
    try:
        from openai import OpenAI
        client = OpenAI()
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": "Say 'OpenAI working' in 3 words"}]
        )
        return resp.choices[0].message.content
    except Exception as e:
        return f"[Error: {e}]"


def anthropic_hello():
    if not os.getenv("ANTHROPIC_API_KEY"):
        return "[NO_API_KEY]"
    try:
        from anthropic import Anthropic
        client = Anthropic()
        resp = client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=50,
            messages=[{"role": "user", "content": "Say 'Claude working' in 3 words"}]
        )
        return resp.content[0].text
    except Exception as e:
        return f"[Error: {e}]"


print(f"  OpenAI:    {openai_hello()}")
print(f"  Anthropic: {anthropic_hello()}")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 3: System Prompts (OpenAI vs Anthropic)
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("SECTION 3: System Prompts")
print("=" * 70)

SYSTEM = "You are a Python tutor. Explain like teaching a 10-year-old. Use 2 sentences."
QUERY = "What is a list comprehension?"


def openai_with_system():
    if not os.getenv("OPENAI_API_KEY"):
        return "[NO_API_KEY]"
    from openai import OpenAI
    client = OpenAI()
    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": SYSTEM},  # In messages
            {"role": "user", "content": QUERY}
        ],
        max_tokens=150
    )
    return resp.choices[0].message.content


def anthropic_with_system():
    if not os.getenv("ANTHROPIC_API_KEY"):
        return "[NO_API_KEY]"
    from anthropic import Anthropic
    client = Anthropic()
    resp = client.messages.create(
        model="claude-3-5-sonnet-20241022",
        max_tokens=150,
        system=SYSTEM,  # Separate parameter!
        messages=[{"role": "user", "content": QUERY}]
    )
    return resp.content[0].text


print(f"\n[OpenAI response]\n{openai_with_system()}")
print(f"\n[Claude response]\n{anthropic_with_system()}")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 4: Streaming
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("SECTION 4: Streaming Responses")
print("=" * 70)


def openai_stream():
    if not os.getenv("OPENAI_API_KEY"):
        return
    from openai import OpenAI
    client = OpenAI()
    print("OpenAI streaming: ", end="", flush=True)
    stream = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": "Count 1 to 5"}],
        stream=True
    )
    for chunk in stream:
        if chunk.choices[0].delta.content:
            print(chunk.choices[0].delta.content, end="", flush=True)
    print()


openai_stream()


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 5: Multi-Turn Conversation
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("SECTION 5: Multi-Turn Conversation")
print("=" * 70)


class ConversationBot:
    def __init__(self, system: str = "You are a helpful assistant."):
        self.history = [{"role": "system", "content": system}]
        try:
            from openai import OpenAI
            self.client = OpenAI()
        except Exception:
            self.client = None

    def chat(self, message: str) -> Optional[str]:
        if not self.client or not os.getenv("OPENAI_API_KEY"):
            return None
        self.history.append({"role": "user", "content": message})
        resp = self.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=self.history,
            max_tokens=200
        )
        reply = resp.choices[0].message.content
        self.history.append({"role": "assistant", "content": reply})
        return reply


bot = ConversationBot("You are a memory-test assistant. Be concise.")
turns = [
    "My name is Ashish and I love Python",
    "What's my name?",
    "What's my favorite language?",
]
for msg in turns:
    print(f"USER: {msg}")
    print(f"BOT:  {bot.chat(msg)}\n")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 6: Token Counting + Cost
# ─────────────────────────────────────────────────────────────────────────────

print("=" * 70)
print("SECTION 6: Token Counting + Cost Estimation")
print("=" * 70)

PRICING = {
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "gpt-4o": {"input": 2.50, "output": 10.00},
    "claude-3-5-sonnet-20241022": {"input": 3.00, "output": 15.00},
    "claude-3-5-haiku-20241022": {"input": 0.25, "output": 1.25},
}


def count_tokens(text: str, model: str = "gpt-4o-mini") -> int:
    try:
        import tiktoken
        enc = tiktoken.encoding_for_model("gpt-4o")
        return len(enc.encode(text))
    except ImportError:
        return len(text) // 4  # Rough estimate


def estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    p = PRICING.get(model, {"input": 0, "output": 0})
    return (input_tokens * p["input"] + output_tokens * p["output"]) / 1_000_000


sample = "The quick brown fox jumps over the lazy dog. " * 20
tokens = count_tokens(sample)
print(f"\nSample text: {sample[:60]}...")
print(f"Tokens: {tokens}")
print(f"\nCost for {tokens} input + 200 output tokens:")
for model in PRICING:
    cost = estimate_cost(model, tokens, 200)
    print(f"  {model:35s} ${cost:.6f}")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 7: Retry with Tenacity
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("SECTION 7: Robust Retry with Tenacity")
print("=" * 70)


def robust_llm_call(messages, model="gpt-4o-mini"):
    if not os.getenv("OPENAI_API_KEY"):
        return "[NO_API_KEY]"
    try:
        from tenacity import retry, stop_after_attempt, wait_exponential
        from openai import OpenAI, RateLimitError, APITimeoutError, APIConnectionError

        @retry(
            stop=stop_after_attempt(3),
            wait=wait_exponential(multiplier=1, min=2, max=10),
        )
        def _call():
            client = OpenAI(timeout=10)
            resp = client.chat.completions.create(model=model, messages=messages, max_tokens=100)
            return resp.choices[0].message.content

        return _call()
    except ImportError:
        return "Install: pip install tenacity"
    except Exception as e:
        return f"Failed after retries: {e}"


print(robust_llm_call([{"role": "user", "content": "Say hello briefly"}]))


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 8: LiteLLM Unified Interface
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("SECTION 8: LiteLLM — Unified Interface")
print("=" * 70)


def litellm_demo():
    try:
        from litellm import completion
    except ImportError:
        print("Install: pip install litellm")
        return

    messages = [{"role": "user", "content": "Say 'hi' in 2 words"}]

    # Try different providers
    providers = [
        ("openai", "gpt-4o-mini"),
        ("anthropic", "claude-3-5-sonnet-20241022"),
    ]

    for name, model in providers:
        env_key = f"{name.upper()}_API_KEY"
        if not os.getenv(env_key):
            print(f"  {name}: skipped (no {env_key})")
            continue
        try:
            resp = completion(model=model, messages=messages, max_tokens=20)
            print(f"  {name}: {resp.choices[0].message.content}")
        except Exception as e:
            print(f"  {name}: error - {e}")


litellm_demo()


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 9: Async Parallel Calls
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("SECTION 9: Async Parallel Calls")
print("=" * 70)


async def parallel_translate(texts: list[str]) -> list[str]:
    if not os.getenv("OPENAI_API_KEY"):
        return ["[NO_API_KEY]"] * len(texts)
    try:
        from openai import AsyncOpenAI
        client = AsyncOpenAI()

        async def translate_one(text: str):
            resp = await client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": f"Translate to French: '{text}'. Output only the French."}],
                max_tokens=30
            )
            return resp.choices[0].message.content

        return await asyncio.gather(*[translate_one(t) for t in texts])
    except Exception as e:
        return [f"[Error: {e}]"] * len(texts)


texts = ["Hello", "Good morning", "Thank you"]
t1 = time.time()
results = asyncio.run(parallel_translate(texts))
elapsed = time.time() - t1

print(f"Parallel translations ({elapsed:.2f}s for {len(texts)}):")
for orig, trans in zip(texts, results):
    print(f"  {orig} → {trans}")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 10: Compare Models — Same Query
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("SECTION 10: Compare Models — Same Query")
print("=" * 70)


def compare_models(query: str):
    try:
        from litellm import completion
    except ImportError:
        return
    models = ["gpt-4o-mini", "claude-3-5-haiku-20241022"]
    for model in models:
        env_var = "OPENAI_API_KEY" if "gpt" in model else "ANTHROPIC_API_KEY"
        if not os.getenv(env_var):
            print(f"  {model}: skipped")
            continue
        try:
            t = time.time()
            resp = completion(model=model, messages=[{"role": "user", "content": query}], max_tokens=100)
            elapsed = time.time() - t
            content = resp.choices[0].message.content
            usage = getattr(resp, "usage", None)
            cost = 0
            if usage:
                cost = estimate_cost(model, usage.prompt_tokens, usage.completion_tokens)
            print(f"\n  [{model}] ({elapsed:.2f}s, ${cost:.6f})")
            print(f"  {content[:200]}")
        except Exception as e:
            print(f"  {model}: error - {e}")


compare_models("Explain quantum computing in 2 sentences")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 11: Exercises
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("SECTION 11: EXERCISES")
print("=" * 70)
print("""
EASY:
1. Modify the chatbot to track total cost. Print cost after each turn.
2. Stream a response to a 200-word essay. Observe how it streams.

MEDIUM:
3. Build a translation pipeline: 10 sentences → French via parallel async calls. Time it.
4. Add retry logic to the multi-turn bot. Inject errors and verify it recovers.

HARD:
5. Compare gpt-4o-mini vs Claude Haiku on 20 questions. Track accuracy + cost.
6. Build a cost dashboard — track per-query cost across a session, plot histogram.

PRO:
7. Build a "Smart Router":
   - Easy queries (1 turn, < 100 tokens) → Gemini Flash (cheapest)
   - Medium → GPT-4o-mini
   - Hard / code → Claude Sonnet
   Measure total cost vs single-model baseline.
""")

if __name__ == "__main__":
    print("\n✅ Level 1 complete! All foundational pieces in place.")
    print("👉 Next: Level 2 (Prompt Engineering) → Level 3 (APIs) → Level 4 (Tool Use)")
