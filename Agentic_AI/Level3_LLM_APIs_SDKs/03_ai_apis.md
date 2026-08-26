# AI APIs — Gemini, HuggingFace Inference, Groq, Ollama

## Quick Concepts
- **Gemini** = Google ka LLM — 1M token context, multimodal, Flash (fast/cheap) vs Pro (powerful)
- **HuggingFace Inference API** = 1000s of open models cloud pe — hosted inference
- **Groq** = blazing fast inference hardware — LPU chip — llama/mixtral ultra-fast
- **Ollama** = local LLM run karo — privacy, no API costs, offline use

---

## Andar kya hota hai — Yeh Chaaro ARCHITECTURALLY Alag Hain, Sirf "Alag API" Nahi

### Groq — GPU nahi, LPU (deterministic dataflow), isiliye itna fast

GPUs dynamically schedule karte hain — batching, memory-access patterns
runtime pe decide hote hain, isse latency VARIANCE aati hai. Groq ka LPU
(Language Processing Unit) chip compile-time pe hi POORA dataflow schedule
kar deta hai — kaunsa compute kab hoga, yeh FIXED hai execution se pehle hi.
Koi runtime scheduling overhead nahi, koi batching-induced jitter nahi — yehi
architectural farak hai jo Groq ki speed explain karta hai, "better hardware"
jaisa vague reason nahi.

### Ollama — local serving, llama.cpp ke upar

```
Model file (GGUF format, quantized — 4-bit/8-bit weights)
  → memory-mapped (mmap) load hota hai, poora RAM mein copy nahi
  → layers CPU/GPU ke beech split ho sakte hain (partial GPU offload)
  → inference llama.cpp ke optimized C++ kernels se chalta hai
```

Quantization (GGUF) hi wajah hai ki ek 7B-parameter model tumhare laptop pe
chal jaata hai — weights ki precision (16-bit → 4-bit) kam karke size/memory
drastically ghatate hain, thoda accuracy trade-off ke saath.

### HuggingFace Inference API — cold-start behavior samjho

Har model ka apna hamesha-warm server NAHI hota. Kam-used model pe pehla
request "cold" hota hai — model us waqt pod pe LOAD hota hai (seconds se
minutes lag sakte), phir kuch der warm pool mein rehta hai agle requests
fast serve karne ke liye. Production mein isliye "first call slow, phir
fast" pattern normal hai — retry-with-backoff isi cold-start ko handle
karne ke liye zaroori hai, error nahi samjhna chahiye.

### Gemini — 1M context ka matlab kya hai practically

Bada context window ka matlab yeh NAHI ki poora context free/fast process
hota hai — prefill (poore input ko process karna response start karne se
pehle) context-length ke saath LINEARLY (ya usse zyada) badhta hai. 1M
tokens ka context bhejna = seconds ka prefill latency + proportionally
zyada cost, chahe output chhota ho.

---

## Interview Questions & Answers

### Q1: Gemini API — Google ka LLM kaise use karte hain?

> ⚠️ **PADHNE SE PEHLE:** neeche wala code **legacy SDK** (`google-generativeai`) hai.
> Google ne ise **deprecate** kar diya hai — naya unified SDK **`google-genai`** hai
> (`from google import genai`). Legacy padhna abhi bhi useful hai kyunki purane
> codebases aur tutorials isi me hain, par **interview me aur naye code me Q1b wala
> pattern use karo.** Agar interviewer purana SDK likhe dekhe to yeh bolna —
> *"yeh legacy SDK hai, naya `google-genai` unified client hai jo Gemini Developer API
> aur Vertex AI dono ko same interface se handle karta hai"* — yeh currency dikhata hai.

**Answer (legacy SDK — recognition ke liye):**
```python
# pip install google-generativeai   # <-- DEPRECATED, Q1b dekho

import google.generativeai as genai
import os

genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))

# ===== MODEL SELECTION =====
# gemini-2.0-flash-exp  → fastest, cheapest, 1M context
# gemini-1.5-pro        → most capable, 2M context
# gemini-1.5-flash      → balanced speed/quality

# ===== BASIC USAGE =====
model = genai.GenerativeModel("gemini-2.0-flash-exp")

response = model.generate_content("Explain Python async/await")
print(response.text)
print(f"Usage: {response.usage_metadata}")

# ===== CHAT (Multi-turn) =====
chat = model.start_chat(history=[])

response1 = chat.send_message("My name is Ashish. I'm learning Python.")
response2 = chat.send_message("What's my name?")  # Remembers context
print(response2.text)

# ===== SYSTEM INSTRUCTION =====
model_with_system = genai.GenerativeModel(
    model_name="gemini-2.0-flash-exp",
    system_instruction="You are a senior Python developer. Always provide production-ready code with type hints.",
)

# ===== STREAMING =====
for chunk in model.generate_content("Write a FastAPI hello world", stream=True):
    print(chunk.text, end="", flush=True)

# ===== MULTIMODAL — Image + Text =====
import PIL.Image

image = PIL.Image.open("diagram.png")

response = model.generate_content([
    "What does this architecture diagram show?",
    image,
])
print(response.text)

# From URL
import httpx
image_bytes = httpx.get("https://example.com/image.jpg").content

response = model.generate_content([
    "Describe this image",
    {"mime_type": "image/jpeg", "data": image_bytes},
])

# ===== STRUCTURED OUTPUT =====
from pydantic import BaseModel

class CodeReview(BaseModel):
    issues: list[str]
    severity: str
    fixed_code: str

import json

response = model.generate_content(
    f"""Review this Python code and return JSON:
{{"issues": [...], "severity": "LOW/MEDIUM/HIGH/CRITICAL", "fixed_code": "..."}}

Code:
def get_user(id):
    conn = sqlite3.connect('db.sqlite')
    cursor = conn.execute(f"SELECT * FROM users WHERE id={id}")
    return cursor.fetchone()
""",
    generation_config=genai.GenerationConfig(
        response_mime_type="application/json",
        response_schema=CodeReview,  # Pydantic schema enforce
    )
)

review = CodeReview.model_validate_json(response.text)
print(f"Issues: {review.issues}")

# ===== LONG DOCUMENT (1M token context!) =====
with open("large_codebase.py", "r") as f:
    code = f.read()

response = model.generate_content(
    f"Analyze this entire codebase for security vulnerabilities:\n\n{code}"
)

# ===== ASYNC =====
import asyncio

async def async_gemini():
    model = genai.GenerativeModel("gemini-2.0-flash-exp")
    response = await model.generate_content_async("Hello!")
    return response.text
```

---

### Q1b: Gemini — **current** SDK (`google-genai`) — yeh likhna interview me

**Answer:**
```python
# pip install google-genai

from google import genai
from google.genai import types
import os

# ===== CLIENT (do modes — yehi naye SDK ka asli fayda hai) =====
# Mode 1: Gemini Developer API (API key)
client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))

# Mode 2: Vertex AI (enterprise — GCP project, IAM auth, data residency)
client = genai.Client(
    vertexai=True,
    project=os.getenv("GCP_PROJECT"),
    location="us-central1",
)
# INTERVIEW: SAME code dono me chalta hai, sirf client init badalta hai.
# Yeh bilkul wahi pattern hai jo OpenAI -> AzureOpenAI me hai:
#   consumer API vs enterprise (IAM/VPC/residency) — client swap, business logic same.

# ===== BASIC =====
resp = client.models.generate_content(
    model="gemini-2.5-flash",              # flash = fast/sasta, pro = reasoning-heavy
    contents="Explain Python async/await",
)
print(resp.text)
print(resp.usage_metadata)

# ===== SYSTEM INSTRUCTION + SAMPLING (ab config object me) =====
resp = client.models.generate_content(
    model="gemini-2.5-flash",
    contents="Review this function",
    config=types.GenerateContentConfig(
        system_instruction="You are a senior Python developer. Return production-ready code.",
        temperature=0.2,
        max_output_tokens=1024,
    ),
)

# ===== CHAT (multi-turn, history managed) =====
chat = client.chats.create(model="gemini-2.5-flash")
chat.send_message("My name is Ashish.")
print(chat.send_message("What's my name?").text)

# ===== STREAMING =====
for chunk in client.models.generate_content_stream(
    model="gemini-2.5-flash", contents="Write a FastAPI hello world"
):
    print(chunk.text, end="", flush=True)

# ===== STRUCTURED OUTPUT (Pydantic schema — enforced, parse nahi karna padta) =====
from pydantic import BaseModel

class CodeReview(BaseModel):
    issues: list[str]
    severity: str
    fixed_code: str

resp = client.models.generate_content(
    model="gemini-2.5-flash",
    contents="Review this code: def get_user(id): ...",
    config=types.GenerateContentConfig(
        response_mime_type="application/json",
        response_schema=CodeReview,
    ),
)
review: CodeReview = resp.parsed          # <-- already-parsed object milta hai

# ===== TOOL / FUNCTION CALLING =====
def get_weather(city: str) -> str:
    """Get current weather for a city."""
    return f"{city}: 31C, humid"

resp = client.models.generate_content(
    model="gemini-2.5-flash",
    contents="Kolkata ka mausam kaisa hai?",
    config=types.GenerateContentConfig(
        tools=[get_weather],              # plain Python function -> schema auto
    ),
)
# INTERVIEW: docstring + type hints se schema banta hai — bilkul Semantic Kernel ke
# @kernel_function aur LangChain ke @tool jaisa. Har SDK me same idea hai.

# ===== THINKING BUDGET (2.5 series ka naya knob) =====
resp = client.models.generate_content(
    model="gemini-2.5-flash",
    contents="Solve this step by step: ...",
    config=types.GenerateContentConfig(
        thinking_config=types.ThinkingConfig(thinking_budget=0),   # 0 = thinking off (sasta/fast)
    ),
)
# INTERVIEW: reasoning models me thinking tokens BILL hote hain. Simple tasks pe
# budget 0 karke cost bacha sakte ho — yeh cost-optimization ka concrete example hai.

# ===== MULTIMODAL =====
from pathlib import Path
resp = client.models.generate_content(
    model="gemini-2.5-flash",
    contents=[
        types.Part.from_bytes(data=Path("diagram.png").read_bytes(),
                              mime_type="image/png"),
        "What does this architecture diagram show?",
    ],
)

# ===== FILES API (bade PDF/video ke liye — inline bytes limit se bacho) =====
f = client.files.upload(file="large_report.pdf")
resp = client.models.generate_content(
    model="gemini-2.5-pro", contents=[f, "Summarize the key risks"])

# ===== ASYNC =====
import asyncio
async def main():
    r = await client.aio.models.generate_content(
        model="gemini-2.5-flash", contents="Hello!")
    return r.text

# ===== EMBEDDINGS =====
emb = client.models.embed_content(
    model="text-embedding-004",
    contents=["chunk one", "chunk two"],
)
```

**Legacy → current migration cheat sheet:**

| Legacy (`google-generativeai`) | Current (`google-genai`) |
|---|---|
| `genai.configure(api_key=...)` | `client = genai.Client(api_key=...)` |
| `genai.GenerativeModel("m")` | model ek **parameter** hai, object nahi |
| `model.generate_content(x)` | `client.models.generate_content(model="m", contents=x)` |
| `model.start_chat()` | `client.chats.create(model="m")` |
| `genai.GenerationConfig(...)` | `types.GenerateContentConfig(...)` |
| `system_instruction=` model pe | `config.system_instruction` |
| `generate_content_async` | `client.aio.models.generate_content` |
| Vertex AI ke liye alag SDK | same client, `vertexai=True` |

**Interview points:**
- Naye SDK me **model stateless parameter** hai — matlab ek client se multiple models
  switch karna trivial hai (routing/fallback pattern ke liye ideal)
- **Gemini Developer API vs Vertex AI** = consumer vs enterprise. Vertex me IAM,
  VPC-SC, data residency, CMEK milte hain — bilkul **OpenAI vs Azure OpenAI** wali
  hi story. Yeh parallel bolna, dono cloud samajhna dikhta hai.
- **Thinking budget** = reasoning models ka cost knob. Simple task pe 0 karo.
- Gemini ka USP: **long context (1M+)** aur native multimodal — isliye "poora contract
  PDF daal do" wale use-case me RAG se pehle long-context try karna valid option hai
  (trade-off: cost per call zyada, latency zyada, par pipeline simple)

---

### Q2: HuggingFace Inference API — open source models kaise use karte hain?
**Answer:**
```python
# pip install huggingface_hub transformers

from huggingface_hub import InferenceClient
import os

client = InferenceClient(token=os.getenv("HF_TOKEN"))

# ===== TEXT GENERATION =====
# Free tier: slow (shared), Pro: faster, Enterprise: dedicated

# Chat completion (OpenAI-compatible)
response = client.chat_completion(
    model="meta-llama/Meta-Llama-3.1-8B-Instruct",
    messages=[
        {"role": "system", "content": "You are a Python expert."},
        {"role": "user", "content": "What is a decorator?"}
    ],
    max_tokens=500,
    temperature=0.7,
)
print(response.choices[0].message.content)

# ===== STREAMING =====
for token in client.chat_completion(
    model="mistralai/Mistral-7B-Instruct-v0.2",
    messages=[{"role": "user", "content": "Write a haiku about Python"}],
    stream=True,
    max_tokens=100,
):
    if token.choices[0].delta.content:
        print(token.choices[0].delta.content, end="")

# ===== EMBEDDINGS =====
embedding = client.feature_extraction(
    text="Python is a programming language",
    model="sentence-transformers/all-MiniLM-L6-v2",  # free, fast
)
print(f"Embedding dim: {len(embedding[0])}")  # 384 dims

# Batch embeddings
texts = ["Python generators", "JavaScript promises", "Go goroutines"]
embeddings = [
    client.feature_extraction(text=t, model="sentence-transformers/all-MiniLM-L6-v2")
    for t in texts
]

# ===== CLASSIFICATION =====
result = client.text_classification(
    "This product is amazing! Best purchase ever.",
    model="distilbert-base-uncased-finetuned-sst-2-english",
)
print(result)  # [{'label': 'POSITIVE', 'score': 0.999}]

# ===== ZERO-SHOT CLASSIFICATION =====
result = client.zero_shot_classification(
    "FastAPI is a web framework for building APIs",
    candidate_labels=["technology", "sports", "politics", "entertainment"],
    model="facebook/bart-large-mnli",
)
print(result)  # labels sorted by score

# ===== IMAGE CLASSIFICATION =====
with open("cat.jpg", "rb") as f:
    result = client.image_classification(f, model="google/vit-base-patch16-224")
print(result)  # [{'label': 'tabby cat', 'score': 0.95}]

# ===== DEDICATED ENDPOINT (production) =====
dedicated_client = InferenceClient(
    model="https://xyz.endpoints.huggingface.cloud",  # your dedicated endpoint
    token=os.getenv("HF_TOKEN"),
)

# ===== LOCAL TRANSFORMERS (no API needed) =====
from transformers import pipeline

# CPU inference (dev)
classifier = pipeline(
    "text-classification",
    model="distilbert-base-uncased-finetuned-sst-2-english",
    device=-1,  # CPU
)
result = classifier("This is great!")
print(result)

# GPU inference
generator = pipeline(
    "text-generation",
    model="microsoft/phi-2",
    device=0,  # GPU 0
    torch_dtype="auto",
)
result = generator("Python is", max_new_tokens=50)
print(result[0]["generated_text"])
```

---

### Q3: Groq — ultra-fast LLM inference kaise use karte hain?
**Answer:**
```python
# pip install groq

from groq import Groq, AsyncGroq
import os

client = Groq(api_key=os.getenv("GROQ_API_KEY"))
async_client = AsyncGroq(api_key=os.getenv("GROQ_API_KEY"))

# Available models (2025):
# llama-3.3-70b-versatile     → best quality (70B params)
# llama-3.1-8b-instant        → fastest (8B params)
# mixtral-8x7b-32768          → large context (32K tokens)
# gemma2-9b-it                → Google Gemma

# ===== BASIC USAGE =====
response = client.chat.completions.create(
    model="llama-3.3-70b-versatile",
    messages=[
        {"role": "system", "content": "You are a Python expert."},
        {"role": "user", "content": "Explain list comprehensions."}
    ],
    max_tokens=500,
    temperature=0.7,
)

print(response.choices[0].message.content)
print(f"Tokens per second: {response.usage.total_tokens / response.usage.total_time:.0f}")
# Groq is 10-20x faster than typical API providers!

# ===== STREAMING =====
stream = client.chat.completions.create(
    model="llama-3.1-8b-instant",
    messages=[{"role": "user", "content": "Write a quicksort in Python"}],
    stream=True,
)

for chunk in stream:
    if chunk.choices[0].delta.content:
        print(chunk.choices[0].delta.content, end="")

# ===== ASYNC =====
async def groq_async(messages: list) -> str:
    response = await async_client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=messages,
    )
    return response.choices[0].message.content

# ===== WITH LITELLM (unified interface) =====
from litellm import completion

response = completion(
    model="groq/llama-3.3-70b-versatile",
    messages=[{"role": "user", "content": "Hello"}],
)

# ===== USE CASES FOR GROQ =====
# - Real-time chat (low latency)
# - Batch processing (high throughput)
# - Code generation (fast iteration)
# - Pre-processing steps in pipeline (quick classify/route)

# SPEED COMPARISON (tokens/second, approximate):
# Groq LPU:   ~300-800 tok/s
# OpenAI GPT-4o:  ~50-100 tok/s
# Claude Haiku:   ~100-200 tok/s
```

---

### Q4: Ollama — local LLM kaise run karte hain?
**Answer:**
```python
# Install Ollama: curl -fsSL https://ollama.com/install.sh | sh
# Pull model: ollama pull llama3.2
# Run server: ollama serve (auto-starts)

import httpx
from openai import OpenAI
import asyncio

# ===== OLLAMA REST API (direct) =====
def ollama_generate(prompt: str, model: str = "llama3.2") -> str:
    response = httpx.post(
        "http://localhost:11434/api/generate",
        json={
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0.7,
                "num_predict": 500,
            }
        },
        timeout=120,
    )
    return response.json()["response"]

# Chat format
def ollama_chat(messages: list, model: str = "llama3.2") -> str:
    response = httpx.post(
        "http://localhost:11434/api/chat",
        json={
            "model": model,
            "messages": messages,
            "stream": False,
        },
        timeout=120,
    )
    return response.json()["message"]["content"]

# ===== OPENAI-COMPATIBLE API =====
ollama_client = OpenAI(
    base_url="http://localhost:11434/v1",
    api_key="ollama",  # required but ignored
)

response = ollama_client.chat.completions.create(
    model="llama3.2",
    messages=[{"role": "user", "content": "Explain Python decorators"}],
)
print(response.choices[0].message.content)

# ===== WITH LANGCHAIN =====
from langchain_community.llms import Ollama
from langchain_community.chat_models import ChatOllama
from langchain_community.embeddings import OllamaEmbeddings

# Chat model
llm = ChatOllama(model="llama3.2", temperature=0.7)
result = llm.invoke("What is FastAPI?")
print(result.content)

# Embeddings (free, local!)
embeddings = OllamaEmbeddings(model="nomic-embed-text")
vector = embeddings.embed_query("Python generators")
print(f"Embedding dim: {len(vector)}")  # 768

# ===== AVAILABLE MODELS =====
# ollama pull llama3.2          → Meta Llama 3.2 (3B, fast on CPU)
# ollama pull llama3.1:8b       → Llama 3.1 8B (balanced)
# ollama pull mistral           → Mistral 7B
# ollama pull codellama         → Code-specialized
# ollama pull nomic-embed-text  → Embeddings model
# ollama pull phi3              → Microsoft Phi-3 (small but capable)

# ===== CUSTOM MODELFILE =====
MODELFILE = """
FROM llama3.2

SYSTEM "You are a Python expert. Always use type hints and async code."

PARAMETER temperature 0.3
PARAMETER num_predict 1000
"""
# ollama create python-expert -f Modelfile
# ollama run python-expert "Write a FastAPI endpoint"

# ===== DOCKER =====
DOCKER_COMPOSE = """
services:
  ollama:
    image: ollama/ollama:latest
    ports:
      - "11434:11434"
    volumes:
      - ollama_data:/root/.ollama
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: all
              capabilities: [gpu]   # GPU ke liye
volumes:
  ollama_data:
"""
```

---

### Q5: Provider comparison — kab kaun sa choose karo?
**Answer:**
```
PROVIDER DECISION MATRIX (2025):

Provider      | Speed    | Cost     | Context | Best For
─────────────────────────────────────────────────────────
Claude Sonnet | Medium   | Medium   | 200K    | Production, RAG, complex tasks
Claude Haiku  | Fast     | Cheap    | 200K    | High-volume, simple tasks
GPT-4o        | Medium   | Medium   | 128K    | General purpose, function calling
GPT-4o-mini   | Fast     | Cheapest | 128K    | Cost optimization, simple tasks
Gemini Flash  | Very Fast| Cheap    | 1M      | Long documents, multimodal
Gemini Pro    | Medium   | Medium   | 2M      | Very long context
Groq Llama 70B| Blazing  | Cheap    | 128K    | Real-time chat, low latency
Groq Llama 8B | Ultra    | Free     | 8K      | Quick tasks, high throughput
HuggingFace   | Variable | Variable | Variable| Custom/fine-tuned models
Ollama Local  | Depends  | FREE     | Varies  | Privacy, offline, dev/testing

COMMON INTERVIEW SCENARIOS:

Q: Customer support chatbot — kaun sa model?
A: Claude Haiku (cheap, fast) ya GPT-4o-mini
   With LiteLLM fallback to Groq for cost optimization

Q: Long legal document analysis?
A: Gemini 1.5 Pro (2M context) ya Claude Opus (200K)

Q: Real-time coding assistant?
A: Groq Llama 70B (fastest), fallback to Claude Sonnet

Q: Privacy-sensitive enterprise?
A: Ollama self-hosted + open-source model
   OR Azure OpenAI / Bedrock (data stays in your cloud)

Q: Multi-modal (image + text)?
A: GPT-4o (best vision), Gemini Pro, Claude Sonnet

Q: Cost optimization strategy?
1. Route simple tasks → cheapest model (Haiku/GPT-4o-mini)
2. Complex tasks → better model (Sonnet/GPT-4o)
3. Batch non-urgent → Batch API (50% discount)
4. Semantic caching → reduce repeat calls
5. LiteLLM fallbacks → uptime + cost
```
