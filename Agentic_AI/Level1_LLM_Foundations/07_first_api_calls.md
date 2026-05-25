# Level 1 — Doc 7: Your First API Calls

> **Goal:** Working code. OpenAI + Claude + Gemini. Token counting, errors, basics. Yahaan se tum coder bante ho.

---

## 1. Setup Reminder

Confirm `.env` has keys (from Doc 6):
```bash
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
```

Install:
```bash
uv add openai anthropic litellm tiktoken python-dotenv
```

---

## 2. Simplest OpenAI Call

```python
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

client = OpenAI()  # Reads OPENAI_API_KEY from env

response = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[
        {"role": "user", "content": "What is Python?"}
    ]
)

print(response.choices[0].message.content)
print(f"\nTokens used: {response.usage.total_tokens}")
print(f"Cost: ${response.usage.prompt_tokens * 0.15 / 1_000_000 + response.usage.completion_tokens * 0.60 / 1_000_000:.6f}")
```

---

## 3. Simplest Claude Call

```python
from anthropic import Anthropic

client = Anthropic()

response = client.messages.create(
    model="claude-3-5-sonnet-20241022",
    max_tokens=512,
    messages=[
        {"role": "user", "content": "What is Python?"}
    ]
)

print(response.content[0].text)
print(f"\nTokens: {response.usage.input_tokens} in, {response.usage.output_tokens} out")
```

**Note differences:**
- Claude requires `max_tokens`
- Claude returns content as a LIST of blocks
- Token info is structured differently

---

## 4. With System Prompt

```python
# OpenAI
response = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[
        {"role": "system", "content": "You are a Python tutor. Explain like I'm 5."},
        {"role": "user", "content": "What is a list comprehension?"}
    ]
)

# Anthropic
response = anthropic_client.messages.create(
    model="claude-3-5-sonnet-20241022",
    max_tokens=512,
    system="You are a Python tutor. Explain like I'm 5.",  # ← Separate param!
    messages=[
        {"role": "user", "content": "What is a list comprehension?"}
    ]
)
```

---

## 5. Streaming Responses

For real-time UI:

### OpenAI streaming
```python
stream = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[{"role": "user", "content": "Count from 1 to 10 slowly"}],
    stream=True
)

for chunk in stream:
    if chunk.choices[0].delta.content:
        print(chunk.choices[0].delta.content, end="", flush=True)
```

### Anthropic streaming
```python
with client.messages.stream(
    model="claude-3-5-sonnet-20241022",
    max_tokens=512,
    messages=[{"role": "user", "content": "Count from 1 to 10 slowly"}]
) as stream:
    for text in stream.text_stream:
        print(text, end="", flush=True)
```

---

## 6. Multi-Turn Conversation

```python
conversation_history = [
    {"role": "system", "content": "You are a helpful assistant."}
]

def chat(user_message: str) -> str:
    conversation_history.append({"role": "user", "content": user_message})
    
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=conversation_history
    )
    
    assistant_msg = response.choices[0].message.content
    conversation_history.append({"role": "assistant", "content": assistant_msg})
    return assistant_msg

print(chat("My name is Ashish"))
print(chat("What's my name?"))  # Remembers
```

---

## 7. Token Counting (Before Calling)

```python
import tiktoken

enc = tiktoken.encoding_for_model("gpt-4o")

text = "Hello, world! This is a token counting demo."
tokens = enc.encode(text)
print(f"Tokens: {len(tokens)}")
print(f"Token IDs: {tokens}")
print(f"Decoded: {enc.decode(tokens)}")
```

**Why count?**
- Check before sending (avoid context overflow)
- Estimate cost
- Truncate long inputs

---

## 8. Cost Estimator

```python
PRICING = {
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "gpt-4o": {"input": 2.50, "output": 10.00},
    "claude-3-5-sonnet-20241022": {"input": 3.00, "output": 15.00},
    "claude-3-5-haiku-20241022": {"input": 0.25, "output": 1.25},
}

def estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    p = PRICING[model]
    return (input_tokens * p["input"] + output_tokens * p["output"]) / 1_000_000

# Estimate
input_tokens = 500
output_tokens = 200

for model in PRICING:
    cost = estimate_cost(model, input_tokens, output_tokens)
    print(f"{model:35s} ${cost:.6f}")
```

---

## 9. Error Handling

```python
from openai import OpenAI, RateLimitError, APIError
import time

def safe_llm_call(messages, model="gpt-4o-mini", max_retries=3):
    for attempt in range(max_retries):
        try:
            response = client.chat.completions.create(
                model=model,
                messages=messages
            )
            return response.choices[0].message.content
        
        except RateLimitError as e:
            wait = 2 ** attempt
            print(f"Rate limit. Waiting {wait}s...")
            time.sleep(wait)
        
        except APIError as e:
            print(f"API error: {e}")
            return None
    
    return None  # All retries failed
```

---

## 10. With Tenacity (Production Retry Library)

```python
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from openai import RateLimitError, APITimeoutError

@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, min=2, max=60),
    retry=retry_if_exception_type((RateLimitError, APITimeoutError))
)
def robust_llm_call(messages, model="gpt-4o-mini"):
    response = client.chat.completions.create(
        model=model,
        messages=messages,
        timeout=30
    )
    return response.choices[0].message.content
```

---

## 11. LiteLLM (Unified Interface)

One library, all providers:

```python
from litellm import completion

# OpenAI
resp = completion(model="gpt-4o-mini", messages=[{"role": "user", "content": "hi"}])

# Claude  
resp = completion(model="claude-3-5-sonnet-20241022", messages=[...])

# Gemini
resp = completion(model="gemini/gemini-2.0-flash", messages=[...])

# Llama via Ollama (local)
resp = completion(model="ollama/llama3.1", messages=[...])

# All return same structure!
print(resp.choices[0].message.content)
```

**LiteLLM benefits:**
- Same code, swap providers
- Built-in retries
- Cost tracking
- Fallback chains

---

## 12. Async Calls (For Parallel Speed)

```python
import asyncio
from openai import AsyncOpenAI

async_client = AsyncOpenAI()

async def parallel_translate(texts):
    tasks = []
    for text in texts:
        task = async_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": f"Translate to French: {text}"}]
        )
        tasks.append(task)
    
    responses = await asyncio.gather(*tasks)
    return [r.choices[0].message.content for r in responses]

texts = ["Hello", "Good morning", "Thank you", "Goodbye"]
results = asyncio.run(parallel_translate(texts))
for orig, trans in zip(texts, results):
    print(f"{orig} → {trans}")
```

5 sequential calls (each 1s) = 5s. Parallel = ~1s.

---

## 13. Temperature & Sampling

```python
# Deterministic — same input always → same output
response = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[{"role": "user", "content": "Pick a number 1-100"}],
    temperature=0  # Deterministic
)

# Creative — varied outputs
response = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[{"role": "user", "content": "Write a haiku about coding"}],
    temperature=1.0  # More creative
)
```

**Rule:**
- `temperature=0` for classification, extraction, code
- `temperature=0.3-0.7` for general chat
- `temperature=1.0+` for creative writing

---

## 14. Other Important Params

```python
response = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[...],
    
    # Stop sequences
    stop=["\n\n", "END"],  # Stop generating at these
    
    # Max tokens to generate
    max_tokens=500,
    
    # Penalty (reduce repetition)
    frequency_penalty=0.5,  # 0-2
    
    # Encourage new topics
    presence_penalty=0.5,
    
    # Reproducible (when temp > 0)
    seed=42
)
```

---

## 15. Putting It All Together — Mini Chatbot

```python
# chatbot.py
from openai import OpenAI
from dotenv import load_dotenv
import tiktoken

load_dotenv()
client = OpenAI()
enc = tiktoken.encoding_for_model("gpt-4o")

SYSTEM = "You are a friendly Python tutor."
history = [{"role": "system", "content": SYSTEM}]
total_cost = 0

def chat(message: str):
    global total_cost
    history.append({"role": "user", "content": message})
    
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=history,
        temperature=0.3
    )
    
    reply = response.choices[0].message.content
    history.append({"role": "assistant", "content": reply})
    
    # Cost tracking
    cost = (response.usage.prompt_tokens * 0.15 + 
            response.usage.completion_tokens * 0.60) / 1_000_000
    total_cost += cost
    
    return reply, response.usage.total_tokens, cost


if __name__ == "__main__":
    print("Chatbot ready. Type 'quit' to exit.\n")
    while True:
        msg = input("You: ").strip()
        if msg.lower() == "quit":
            print(f"Session total cost: ${total_cost:.6f}")
            break
        reply, tokens, cost = chat(msg)
        print(f"Bot: {reply}")
        print(f"  ({tokens} tokens, ${cost:.6f})\n")
```

Run: `python chatbot.py`

---

## 16. Common First-Day Errors

### Error: "API key not set"
```python
# Fix: ensure .env loaded
from dotenv import load_dotenv
load_dotenv()  # ← Don't forget this!
```

### Error: "Model not found"
```python
# Wrong
model="gpt4-mini"  # Typo
# Right
model="gpt-4o-mini"
```

### Error: "Rate limit exceeded"
- Free tier has low limits
- Use retry with backoff
- Or upgrade tier

### Error: "Context length exceeded"
- Input too long
- Count tokens, truncate

---

## 17. Key Takeaways

✅ OpenAI + Claude code patterns: similar but key differences (max_tokens, system param, content format)
✅ Always handle errors (retry on 429)
✅ Count tokens before calling
✅ Track cost — `response.usage`
✅ Use `temperature=0` for consistent outputs
✅ Stream for UX, async for parallelism
✅ LiteLLM for provider-agnostic code
✅ Save your first working chatbot — refer back to it

**Level 1 Complete!** 🎉 Next: [Level 2 — Prompt Engineering](../Level2_Prompt_Engineering/01_anatomy_of_prompt.md)
