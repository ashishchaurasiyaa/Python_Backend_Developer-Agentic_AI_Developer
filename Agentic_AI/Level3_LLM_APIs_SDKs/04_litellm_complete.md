# LiteLLM — Universal LLM Interface, Provider Fallbacks, Cost Tracking, Proxy

## Quick Concepts
- **LiteLLM** = ek API se sab LLM providers call karo (OpenAI, Claude, Gemini, etc.)
- **Provider fallback** = ek fail hote hi doosra try karo automatically
- **Cost tracking** = har call ka cost track karo
- **LiteLLM Proxy** = ek central server — team ke liye unified gateway
- **Load balancing** = multiple API keys mein traffic distribute karo

---

## Andar kya hota hai — "Unified Interface" Ek Translation Layer Hai, Magic Nahi

### Request/response TRANSFORM hota hai, har provider ke liye

```python
response = litellm.completion(model="claude-3-5-sonnet", messages=[...])
# yeh OpenAI-format messages/response use karta hai — Claude ka NATIVE
# format nahi. LiteLLM ANDAR yeh karta hai:
#
# 1. Tumhara OpenAI-shape request leta hai
# 2. model="claude-..." dekh ke Anthropic ka ADAPTER function chalata hai
# 3. Adapter OpenAI-shape ko Anthropic ke ACTUAL wire format mein transform
#    karta hai (messages array → Anthropic ka system+messages split,
#    max_tokens required field jo OpenAI mein optional tha, etc.)
# 4. Real Anthropic API ko call karta hai
# 5. Anthropic ka response (named-events ya JSON) WAPAS OpenAI-shape
#    response object mein transform karta hai
```

Har supported provider ke liye LiteLLM ke paas apna DEDICATED
transform-in/transform-out adapter hai — "universal interface" ka matlab
hai LiteLLM ne yeh translation kaam pehle se kar rakha hai, koi provider
khud OpenAI-compatible nahi ban gaya.

### Fallback — exception TYPE dekh ke decide hota hai, blind retry nahi

```python
litellm.completion(model="gpt-4o", fallbacks=["claude-3-5-sonnet"], messages=[...])
```

`Router` internally specific EXCEPTION TYPES catch karta hai — rate limit
(`RateLimitError`), timeout, 5xx server error — aur INHI cases mein next
provider try karta hai. Ek genuine `400 Bad Request` (galat input tumhara)
pe fallback NAHI chalega — woh error tumhara hai, doosra provider bhi wahi
reject karega, retry karne ka fayda nahi.

### Load balancing — per-deployment usage TRACK hota hai

Router har deployment (ek hi model, multiple API keys/regions ho sakte)
ka rolling-window mein tokens/requests usage track karta hai — naya call
aane par LEAST-LOADED (ya weighted-random, config ke hisaab se) deployment
choose karta hai. Yeh ek simple round-robin nahi hai — actual load-aware
routing decision hai, current usage state ke against.

---

## Interview Questions & Answers

### Q1: LiteLLM kya hai? Kyu use karte hain?
**Answer:**
```python
# pip install litellm

import litellm
from litellm import completion, acompletion

# SAME CODE — different providers
# OpenAI
response = completion(
    model="gpt-4o",
    messages=[{"role": "user", "content": "Hello"}]
)

# Claude (same code!)
response = completion(
    model="claude-sonnet-4-6",
    messages=[{"role": "user", "content": "Hello"}]
)

# Gemini (same code!)
response = completion(
    model="gemini/gemini-1.5-pro",
    messages=[{"role": "user", "content": "Hello"}]
)

# Groq (same code!)
response = completion(
    model="groq/llama-3.1-8b-instant",
    messages=[{"role": "user", "content": "Hello"}]
)

# Ollama local (same code!)
response = completion(
    model="ollama/llama3.2",
    messages=[{"role": "user", "content": "Hello"}]
)

# Response format SAME for all providers
print(response.choices[0].message.content)
print(response.usage.total_tokens)

# WHY LITELLM:
# ✓ Vendor lock-in nahi
# ✓ Easy provider switch
# ✓ Automatic retries + fallbacks
# ✓ Cost tracking built-in
# ✓ Consistent error handling
```

---

### Q2: Provider Fallbacks kaise karte hain?
**Answer:**
```python
import litellm

# FALLBACK SETUP
# Primary fail → backup try karo
response = litellm.completion_with_fallbacks(
    model="claude-sonnet-4-6",
    messages=[{"role": "user", "content": "Write a poem"}],
    fallbacks=["gpt-4o", "gemini/gemini-1.5-pro"],  # order mein try
    context_window_fallbacks=[
        {"claude-opus-4-7": ["claude-sonnet-4-6"]},  # context limit pe fallback
    ]
)

# Async version
async def resilient_completion(prompt: str) -> str:
    response = await litellm.acompletion_with_fallbacks(
        model="claude-sonnet-4-6",
        messages=[{"role": "user", "content": prompt}],
        fallbacks=["gpt-4o", "groq/llama-3.1-70b-versatile"],
        num_retries=2,
    )
    return response.choices[0].message.content

# Router-based fallback (production recommended)
from litellm import Router

router = Router(
    model_list=[
        {
            "model_name": "fast-model",
            "litellm_params": {
                "model": "claude-haiku-4-5-20251001",
                "api_key": "sk-ant-...",
            },
            "tpm": 100000,
            "rpm": 100,
        },
        {
            "model_name": "fast-model",  # same alias — load balancing
            "litellm_params": {
                "model": "gpt-4o-mini",
                "api_key": "sk-openai-...",
            },
            "tpm": 200000,
            "rpm": 200,
        },
        {
            "model_name": "smart-model",
            "litellm_params": {
                "model": "claude-sonnet-4-6",
                "api_key": "sk-ant-...",
            }
        },
        {
            "model_name": "smart-model",  # fallback for smart-model
            "litellm_params": {
                "model": "gpt-4o",
                "api_key": "sk-openai-...",
            }
        }
    ],
    routing_strategy="least-busy",   # load balancing strategy
    fallbacks=[{"smart-model": ["fast-model"]}],
    allowed_fails=2,       # 2 failures ke baad fallback trigger
    retry_after=5,         # 5s baad retry
)

# Use router
response = await router.acompletion(
    model="smart-model",
    messages=[{"role": "user", "content": "Explain recursion"}]
)
```

---

### Q3: Cost Tracking kaise karte hain?
**Answer:**
```python
import litellm
from litellm import completion

# Enable cost tracking
litellm.success_callback = ["langfuse"]  # ya custom callback

# Custom cost callback
def track_cost(kwargs, completion_response, start_time, end_time):
    cost = litellm.completion_cost(
        completion_response=completion_response,
        model=kwargs["model"],
    )
    duration = (end_time - start_time).total_seconds()

    # DB ya analytics mein save karo
    print(f"Model: {kwargs['model']}")
    print(f"Cost: ${cost:.6f}")
    print(f"Duration: {duration:.2f}s")
    print(f"Tokens: {completion_response.usage.total_tokens}")

litellm.success_callback = [track_cost]

# Per-request cost calculate karo
response = completion(
    model="claude-sonnet-4-6",
    messages=[{"role": "user", "content": "Hello"}]
)

cost = litellm.completion_cost(completion_response=response)
print(f"This call cost: ${cost:.6f}")

# Cost estimate before calling (input tokens ke liye)
estimated_cost = litellm.cost_per_token(
    model="claude-sonnet-4-6",
    prompt_tokens=1000,
    completion_tokens=500,
)
print(f"Estimated: ${sum(estimated_cost.values()):.6f}")

# Usage tracking with user IDs (per-user billing ke liye)
response = completion(
    model="gpt-4o",
    messages=[{"role": "user", "content": "Hello"}],
    user="user-123",       # track kar sakte ho per user
    metadata={
        "user_id": "user-123",
        "feature": "chat",
        "session_id": "sess-456"
    }
)
```

---

### Q4: LiteLLM Proxy Server kaise setup karte hain?
**Answer:**
```yaml
# config.yaml — LiteLLM proxy config
model_list:
  - model_name: gpt-4o
    litellm_params:
      model: gpt-4o
      api_key: os.environ/OPENAI_API_KEY

  - model_name: claude-sonnet
    litellm_params:
      model: claude-sonnet-4-6
      api_key: os.environ/ANTHROPIC_API_KEY

  - model_name: fast
    litellm_params:
      model: claude-haiku-4-5-20251001
      api_key: os.environ/ANTHROPIC_API_KEY

  - model_name: fast
    litellm_params:
      model: gpt-4o-mini
      api_key: os.environ/OPENAI_API_KEY

router_settings:
  routing_strategy: least-busy
  allowed_fails: 2

general_settings:
  master_key: sk-my-master-key    # team ka shared key
  database_url: postgresql://...  # usage logs store karo
  alerting: ["slack"]

litellm_settings:
  success_callback: ["langfuse"]
  failure_callback: ["slack"]
  max_budget: 100                 # $100/day limit
  budget_duration: 1d
```

```bash
# Start proxy
pip install 'litellm[proxy]'
litellm --config config.yaml --port 4000 --debug

# Docker Compose mein
services:
  litellm-proxy:
    image: ghcr.io/berriai/litellm:main-latest
    ports:
      - "4000:4000"
    volumes:
      - ./litellm_config.yaml:/app/config.yaml
    environment:
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
    command: --config /app/config.yaml --port 4000
```

```python
# Team members sirf proxy URL use karein — real API keys nahi
import openai

# OpenAI SDK se LiteLLM proxy use karo
proxy_client = openai.OpenAI(
    api_key="sk-my-master-key",
    base_url="http://litellm-proxy:4000"
)

response = proxy_client.chat.completions.create(
    model="claude-sonnet",   # proxy ke model name
    messages=[{"role": "user", "content": "Hello"}]
)
```

---

### Q5: Observability — LangSmith/Langfuse integration?
**Answer:**
```python
import litellm
import os

# Langfuse integration
os.environ["LANGFUSE_PUBLIC_KEY"] = "pk-..."
os.environ["LANGFUSE_SECRET_KEY"] = "sk-..."
os.environ["LANGFUSE_HOST"] = "https://cloud.langfuse.com"

litellm.success_callback = ["langfuse"]
litellm.failure_callback = ["langfuse"]

# Har call automatically Langfuse mein log hoga:
# - Model used
# - Input/output
# - Tokens + cost
# - Latency
# - User ID
# - Custom metadata

response = litellm.completion(
    model="claude-sonnet-4-6",
    messages=[{"role": "user", "content": "Hello"}],
    metadata={
        "generation_name": "chat-response",
        "session_id": "sess-123",
        "user_id": "user-456",
        "tags": ["production", "chat"],
    }
)

# LangSmith
os.environ["LANGCHAIN_API_KEY"] = "ls__..."
os.environ["LANGCHAIN_TRACING_V2"] = "true"
litellm.success_callback = ["langsmith"]
```
