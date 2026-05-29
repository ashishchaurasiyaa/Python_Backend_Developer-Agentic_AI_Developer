# AI APIs — Gemini, HuggingFace Inference, Groq, Ollama

## Quick Concepts
- **Gemini** = Google ka LLM — 1M token context, multimodal, Flash (fast/cheap) vs Pro (powerful)
- **HuggingFace Inference API** = 1000s of open models cloud pe — hosted inference
- **Groq** = blazing fast inference hardware — LPU chip — llama/mixtral ultra-fast
- **Ollama** = local LLM run karo — privacy, no API costs, offline use

---

## Interview Questions & Answers

### Q1: Gemini API — Google ka LLM kaise use karte hain?
**Answer:**
```python
# pip install google-generativeai

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
