# N04 — LLM Gateways (LiteLLM + LangChain): Ek Unified Door Saare Providers Ke Aage

> **Source:** Krish Naik — "Complete Agentic AI Course In 10 Hours" · chapter **10:30:25 (LLM Gateways)** · notebook: `KrishNaik_AgenticAI/LLM_Gateway_LiteLLM.ipynb` (KRISHAI Technologies) · YouTube: https://youtube.com/watch?v=rV3HJ4LEZ7k

---

## 🎯 TL;DR

LLM Gateway ek **middleware layer** hai jo tumhari app aur 100+ LLM providers (OpenAI, Anthropic, Gemini, Groq, Bedrock) ke beech baithta hai aur **ek hi unified API** deta hai — saath mein fallbacks, retries, caching, cost tracking, load-balancing, rate-limit handling aur observability free mein. Krish notebook mein yeh sab **LiteLLM** se banata hai (`completion()` aur `Router`), aur phir usko LangChain ke `ChatLiteLLM` se plug karta hai. Jo cheez tum apne labs mein **manually `get_client()` provider-swap + hand-rolled fallback ladder** se kar rahe the — gateway usko ek line mein productionize kar deta hai.

---

## 🗣️ Hinglish Explanation

### Sabse pehle: problem kya hai (WHY before WHAT)

Tum already jaante ho ki har provider ka SDK alag hota hai. OpenAI ka `openai` client, Anthropic ka `anthropic` client, Gemini ka `google-generativeai`, Bedrock ka `boto3`. Har ek ka request shape, response shape, error types, retry semantics alag. Apne labs mein tumne yeh dard khud feel kiya hoga jab ek `get_client(provider)` function likha tha jo provider ke hisaab se alag-alag client return karta tha, aur uske upar ek fallback ladder (pehle yeh try karo, fail ho to woh) likhi thi.

Yeh manual approach kaam to karta hai, par production mein 5 problems aati hain:

1. **Naya provider add karna = naya glue code** — har provider ke liye client init, message format conversion, response parsing.
2. **Fallback logic har jagah duplicate** — ek try/except ladder ek file mein, dusri kahin aur.
3. **Cost track karna manual** — har provider ka pricing alag, token counting alag.
4. **Caching, rate-limit handling, observability — sab tumhe khud banana padta hai.**
5. **Model swap karna = code rewrite**, kyunki model name client se hardcoded ghuse hote hain.

LLM Gateway exactly inhi 5 problems ko solve karta hai. Architecture ka mental model notebook se:

```
        Your App (Chatbot / RAG / Agent)
                    |
                    v
        ┌──────────────────────────┐
        │       LLM GATEWAY        │
        │  • Routing               │
        │  • Fallbacks             │
        │  • Caching               │
        │  • Rate limiting         │
        │  • Cost tracking         │
        │  • Observability         │
        └───┬─────┬─────┬─────┬────┘
            v     v     v     v
         OpenAI Claude Gemini Groq
```

Krish notebook mein **LiteLLM** use karta hai — open-source gateway jo 100+ providers support karta hai. (Alternatives: Portkey, Helicone, OpenRouter, Cloudflare AI Gateway, Kong AI Gateway — comparison table neeche hai.) LiteLLM isliye chuna kyunki self-host ho jaata hai, full control, kahin bhi chalta hai.

### Setup

```python
# Install
!pip install -q litellm langchain langchain-community langchain-openai python-dotenv

import warnings, logging
warnings.filterwarnings("ignore")
logging.getLogger("LiteLLM").setLevel(logging.ERROR)

import litellm
litellm.suppress_debug_info = True

import os
from dotenv import load_dotenv
load_dotenv()
# .env mein: OPENAI_API_KEY, ANTHROPIC_API_KEY, GROQ_API_KEY, GEMINI_API_KEY
```

LiteLLM keys ko **environment se khud uthata hai** — tumhe har provider ke liye alag client banane ki zaroorat nahi. Yeh pehla bada relief hai vs tumhara manual `get_client()`.

### Part 1 — The unified API: ek `completion()`, saare providers

Yeh gateway ka dil hai. OpenAI-compatible signature, lekin `model` string mein provider prefix dene se woh kahin bhi route ho jaata hai:

```python
from litellm import completion

# Same code, alag provider — sirf `model` string badlo!
response_openai = completion(
    model="gpt-4o-mini",
    messages=[{"role": "user", "content": "Explain RAG in one sentence."}]
)

response_groq = completion(
    model="groq/llama-3.3-70b-versatile",   # 👈 provider prefix: groq/
    messages=[{"role": "user", "content": "Explain RAG in one sentence."}]
)
```

Ek hi loop se 4 providers maar do — yahi cheez tum apne `get_client()` se manually karte the, ab declarative ho gayi:

```python
providers = [
    ("🔵 OpenAI",     "gpt-4o-mini"),
    ("🟢 Groq",       "groq/llama-3.3-70b-versatile"),
    ("🟣 Anthropic",  "claude-3-5-haiku-20241022"),
    ("🟡 Gemini",     "gemini/gemini-1.5-flash"),
]

for label, model in providers:
    try:
        r = completion(model=model, messages=[{"role": "user", "content": prompt}])
        print(f"{label:<15}: {r.choices[0].message.content[:80]}")
    except Exception as e:
        print(f"{label:<15}: ❌ {type(e).__name__}")
```

**Key insight:** response shape **hamesha OpenAI-style** hota hai — `r.choices[0].message.content`, `r.usage.prompt_tokens` — chahe Claude ho ya Gemini. LiteLLM andar-andar har provider ka response normalize kar deta hai. Tumhari app ko bas ek shape pata hai. Yeh wahi normalization hai jo tum apne **Bedrock provider abstraction** mein hand-likhte the (boto3 ka response shape alag tha, usko common dict mein convert karna padta tha). Gateway yeh free deta hai.

### Part 2 — Automatic fallbacks (tumhari fallback ladder, ek argument mein)

Yeh **#1 reason** hai jisse teams gateway adopt karti hain. Tumhare manual lab mein ek loop tha: "pehle GPT, fail ho to Claude, fail ho to Groq." LiteLLM mein woh poori ladder ek `fallbacks=[...]` argument hai:

```python
from litellm import completion

response = completion(
    model="gemini/gemini-1.5-flash",     # primary
    messages=[{"role": "user", "content": "What is an LLM Gateway?"}],
    fallbacks=[
        "gpt-4o-mini",                    # 1st backup
        "groq/llama-3.3-70b-versatile"    # 2nd backup
    ]
)
print("Which model actually answered?", response.model)  # response.model batata hai kaun jeeta
```

Primary ko jaan-bujhke fail karke dekho — fallback chain bachata hai:

```python
response = completion(
    model="openai/fake-nonexistent-model-9999",   # 👈 intentionally fail
    messages=[{"role": "user", "content": "What is an LLM Gateway?"}],
    fallbacks=["gpt-4o-mini", "groq/llama-3.3-70b-versatile"]
)
print("✅ App still got a response, even though the primary failed!")
print(f"🤖 Model that actually answered: {response.model}")
```

Agar `gpt-4o-mini` rate-limited ya down hai, LiteLLM transparently Claude, phir Groq retry karta hai. **Tumhari app ko failure dikhta hi nahi.** Compare karo apne manual try/except ladder se — wahan tumhe har exception type khud catch karni padti thi (OpenAI ka `RateLimitError` vs Anthropic ka alag), aur retry/backoff khud likhna padta tha. Gateway yeh sab andar handle karta hai.

### Part 3 — Cost tracking (jo manually impossible-sa tha)

LiteLLM ke paas built-in pricing DB hai — har call ka exact USD cost nikaal ke deta hai:

```python
from litellm import completion, completion_cost

response = completion(
    model="gpt-4o-mini",
    messages=[{"role": "user", "content": "Write a haiku about AI."}]
)

cost = completion_cost(completion_response=response)
print("Input tokens: ", response.usage.prompt_tokens)
print("Output tokens:", response.usage.completion_tokens)
print(f"Cost:         ${cost:.8f}")
```

Hazaar calls/din, team ya project ke hisaab se tag karke — turant pata chal jaata hai budget kaun jala raha hai. Manual setup mein tumhe har provider ka pricing table khud maintain karna padta.

### Part 4 — Caching (ek line mein, do baar paise mat do)

Agar 100 users "What is RAG?" poochte hain, LLM ko 100 baar call karne ki zaroorat nahi. In-memory cache ek line mein:

```python
import litellm, time
from litellm import completion
from litellm.caching import Cache

litellm.cache = Cache(type="local")   # production mein type="redis"

prompt = "What does LLM stand for? Answer in one line."

# Pehli call — actually OpenAI hit karti hai
start = time.time()
r1 = completion(model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                caching=True)
t1 = time.time() - start

# Doosri call — cache se, near-instant, ZERO cost
start = time.time()
r2 = completion(model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                caching=True)
t2 = time.time() - start
print(f"🚀 Speedup: {t1/t2:.1f}x faster, and ZERO cost on the second call!")
```

Yeh prompt-level **exact-match** cache hai — embedding-based semantic cache se alag (jo tum RAG mein dekh chuke ho). Yahan key prompt ka hash hai, semantic similarity nahi. Production mein `type="redis"` use karna (restart ke baad survive karта hai, multiple replicas share karte hain).

### Part 5 — Smart Routing: `Router` aur model aliases

Ab tak `completion()` ek-ek call ke liye tha. Production mein tum **`Router`** use karoge — jo ek config (`model_list`) leta hai aur **abstract aliases** ke peeche real deployments ko chhupata hai:

```python
import os
from litellm import Router

model_list = [
    {
        "model_name": "fast-cheap",                          # 👈 alias
        "litellm_params": {"model": "groq/llama-3.3-70b-versatile",
                           "api_key": os.getenv("GROQ_API_KEY")}
    },
    {
        "model_name": "smart-coding",                        # 👈 alias
        "litellm_params": {"model": "gpt-4o",                # mapped to OpenAI
                           "api_key": os.getenv("OPENAI_API_KEY")}
    },
    {
        "model_name": "balanced",
        "litellm_params": {"model": "gpt-4o-mini",
                           "api_key": os.getenv("OPENAI_API_KEY")}
    },
]

router = Router(model_list=model_list)

fast_response = router.completion(
    model="fast-cheap",                                       # app sirf alias jaanti hai
    messages=[{"role": "user", "content": "Summarize: AI is changing software."}]
)
code_response = router.completion(
    model="smart-coding",
    messages=[{"role": "user", "content": "Write a Python function to reverse a string."}]
)
```

**Key insight:** tumhari app `"fast-cheap"` ya `"smart-coding"` bolti hai — **abstract naam**. Router decide karta hai kaunsa provider actually use ho. Kal ko Groq ko sasta provider se replace karna ho — **zero code change**, sirf `model_list` config badlo. Yeh exactly tumhari `get_client()` indirection hai, par config-driven aur productionized.

### Part 6 — Load balancing: ek alias ke peeche kai deployments

OpenAI key par rate-limit hit kar rahe ho? Same alias ke neeche kai deployments daal do — Router automatically load-balance karta hai. Note: same `model_name` ("gpt-pool") do baar, alag providers ke saath:

```python
from litellm import Router
import os

model_list = [
    {"model_name": "gpt-pool",
     "litellm_params": {"model": "gpt-4o", "api_key": os.getenv("OPENAI_API_KEY")},
     "model_info": {"id": "openai-gpt4o"}},
    {"model_name": "gpt-pool",
     "litellm_params": {"model": "groq/llama-3.3-70b-versatile", "api_key": os.getenv("GROQ_API_KEY")},
     "model_info": {"id": "groq-llama-70b"}},
]

router = Router(model_list=model_list, routing_strategy="simple-shuffle")

for i in range(6):
    r = router.completion(model="gpt-pool",
                          messages=[{"role": "user", "content": f"Say hello, request {i+1}"}])
    deployment_id = r._hidden_params.get("model_id", "unknown")  # kaun serve kiya
    print(f"#{i+1} → {deployment_id}  ({r._response_ms:.0f} ms)")
```

`r._hidden_params.get("model_id")` se pata chalta hai kaunsa deployment serve hua. Routing strategies jo notebook demo karta hai:

- **`simple-shuffle`** — random/round-robin distribution.
- **`least-busy`** — supermarket mein chhoti line pakadne jaisa; jis deployment par sabse kam requests in-flight hain, usko bhejo.
- **`latency-based-routing`** — jo deployment recent calls mein sabse fast raha, usko prefer karo (pehli 2-3 calls exploratory, phir woh consistently fastest par lock kar lega — usually Groq).

```python
router = Router(model_list=model_list, routing_strategy="least-busy")
# ya
router = Router(model_list=model_list, routing_strategy="latency-based-routing")
```

### Part 7 — Observability: har call log karo (callbacks)

Production mein tumhe **har** call log karni hai — prompt, response, latency, cost, user_id. LiteLLM `success_callback` / `failure_callback` hooks deta hai:

```python
import litellm, json
from litellm import completion

call_logs = []

def log_success(kwargs, completion_response, start_time, end_time):
    """Har successful call ke baad auto-call hota hai."""
    call_logs.append({
        "model": kwargs.get("model"),
        "prompt": kwargs["messages"][-1]["content"][:60],
        "input_tokens": completion_response.usage.prompt_tokens,
        "output_tokens": completion_response.usage.completion_tokens,
        "latency_sec": round((end_time - start_time).total_seconds(), 2),
        "cost_usd": kwargs.get("response_cost", 0),
        "user": kwargs.get("user", "anonymous"),
    })

def log_failure(kwargs, completion_response, start_time, end_time):
    print("❌ Call failed:", kwargs.get("exception"))

litellm.success_callback = [log_success]
litellm.failure_callback = [log_failure]

for q, user in [("What is RAG?", "krish"), ("Explain transformers.", "student_42")]:
    completion(model="gpt-4o-mini",
               messages=[{"role": "user", "content": q}],
               user=user)   # call ko user se tag karo (attribution)

print(json.dumps(call_logs, indent=2, default=str))
```

Ab tumhare paas **per-user, per-call audit trail** hai — chargebacks, debugging, security review ke liye. Production mein in callbacks ko Langfuse / Helicone / Arize jaise backend par bhej dete hain.

### Part 8 — Guardrails as callbacks (input_callback) — tumhare guardrails knowledge se direct connect

Tumne guardrails alag se study kiye hain (output validators, structured checks). Notebook dikhata hai ki gateway level par guardrails **callbacks** ki tarah lagte hain — `litellm.input_callback` jo LLM call se **pehle** chalta hai. Pure Python, koi external library nahi:

```python
import re, litellm
from litellm import completion

PII_PATTERNS = {
    "EMAIL":   r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",
    "PHONE_IN":r"(\+91[\-\s]?)?[6-9]\d{9}",          # Indian mobile
    "AADHAAR": r"\b\d{4}\s?\d{4}\s?\d{4}\b",          # Indian Aadhaar
    "PAN":     r"\b[A-Z]{5}\d{4}[A-Z]\b",            # Indian PAN
}

def redact_pii(text):
    detected, clean = [], text
    for label, pattern in PII_PATTERNS.items():
        if re.findall(pattern, clean):
            detected.append(label)
            clean = re.sub(pattern, f"<{label}_REDACTED>", clean)
    return clean, detected

def pii_input_guardrail(kwargs):
    """Pre-call hook: user messages se PII scrub karo."""
    for msg in kwargs.get("messages", []):
        if msg.get("role") == "user":
            clean, detected = redact_pii(msg["content"])
            if detected:
                print(f"🚨 PII REDACTED: {detected}")
                msg["content"] = clean

litellm.input_callback = [pii_input_guardrail]
```

LLM ko real PAN/Aadhaar/email kabhi dikhta hi nahi — prompt machine chhodne se pehle redact ho jaata hai. Isi pattern se notebook **prompt-injection blocking** (regex patterns like `ignore (previous) instructions`, `you are now DAN`) aur **forbidden-topic blocking** (keyword match → `raise GuardrailViolation`) bhi dikhata hai. Yeh tumhare guardrails ka **centralized, gateway-level** version hai — har provider ke har call par automatically apply hota hai, ek jagah se.

### Part 9 — LangChain integration: `ChatLiteLLM`

Yeh production GenAI apps ke liye click hota hai. LangChain orchestration (chains, agents, RAG) + LiteLLM unified backend. LangChain ka built-in `ChatLiteLLM` wrapper kisi bhi chat model ki tarah drop-in hota hai:

```python
!pip install -q langchain-litellm

from langchain_litellm import ChatLiteLLM
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

llm = ChatLiteLLM(model="gpt-4o-mini", temperature=0.3)

prompt = ChatPromptTemplate.from_messages([
    ("system", "You are a helpful AI tutor named KrishGPT. Be concise."),
    ("user", "{question}")
])

chain = prompt | llm | StrOutputParser()      # same LCEL syntax
print(chain.invoke({"question": "What is an LLM Gateway in 3 bullets?"}))
```

**Magic:** `model="gpt-4o-mini"` ko `"claude-3-5-sonnet-20241022"` ya `"groq/llama-3.3-70b-versatile"` se replace karo — **poora chain** ab dusre provider par chalega, baaki kuch change nahi.

Aur LangChain ka apna `.with_fallbacks()` LiteLLM ke fallbacks ke saath stack ho jaata hai:

```python
from langchain_litellm import ChatLiteLLM
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

primary    = ChatLiteLLM(model="gpt-x")                              # jaan-bujhke galat
fallback_1 = ChatLiteLLM(model="gpt-4o-mini", temperature=0.2)
fallback_2 = ChatLiteLLM(model="groq/llama-3.3-70b-versatile", temperature=0.2)

robust_llm = primary.with_fallbacks([fallback_1, fallback_2])

prompt = ChatPromptTemplate.from_messages([
    ("system", 'Always reply in JSON: {{"answer": ...}}'),
    ("user", "{question}")
])
chain = prompt | robust_llm | StrOutputParser()
print(chain.invoke({"question": "Top 3 benefits of an LLM Gateway?"}))
```

### Part 10 — Capstone: task-aware smart chatbot (sab cheezein ek saath)

Notebook end mein ek mini chatbot banata hai jo: (1) query classify karta hai cheap fast model se, (2) task ke hisaab se sahi model par route karta hai, (3) fail ho to fallback, (4) cost+latency log karta hai. Yeh **router + fallback + cost tracking** ka real combination hai:

```python
import time
from litellm import completion, completion_cost

def classify_task(user_query: str) -> str:
    """Cheap classifier — fastest model se routing decide."""
    cls = completion(
        model="groq/llama-3.3-70b-versatile",
        messages=[{"role": "user", "content":
            f"Classify into EXACTLY one word: 'code', 'summary', or 'general'. "
            f"Query: {user_query}\n\nAnswer:"}],
        max_tokens=5)
    return cls.choices[0].message.content.strip().lower()

def call_with_fallbacks(model_chain, messages):
    """Order mein try karo; pehla jo succeed kare wahi return."""
    last_error = None
    for model in model_chain:
        try:
            return completion(model=model, messages=messages)
        except Exception as e:
            print(f"   ⚠️  {model} failed ({type(e).__name__}), trying next...")
            last_error = e
    raise last_error

def smart_chat(user_query: str):
    task = classify_task(user_query)
    routing = {
        "code":    ["gpt-4o", "gpt-4o-mini", "groq/llama-3.3-70b-versatile"],
        "summary": ["gpt-4o-mini", "groq/llama-3.3-70b-versatile"],
        "general": ["groq/llama-3.3-70b-versatile", "gpt-4o-mini"],
    }
    model_chain = routing.get(task, routing["general"])

    start = time.time()
    response = call_with_fallbacks(model_chain, [{"role": "user", "content": user_query}])
    latency = time.time() - start

    try:    cost_str = f"${completion_cost(completion_response=response):.6f}"
    except: cost_str = "n/a"

    return {"detected_task": task, "model_used": response.model,
            "answer": response.choices[0].message.content,
            "latency_sec": round(latency, 2), "cost_usd": cost_str}
```

Dekho `call_with_fallbacks` — yeh **bilkul wahi manual ladder hai jo tum apne labs mein likhte the**. Notebook deliberately yeh manual version dikhata hai _aur_ LiteLLM ka built-in `fallbacks=[...]` dono — taaki tum samjho gateway ne kya abstract kiya. Production mein tum manual loop ko `Router`/`fallbacks` se replace kar doge.

---

## 🆚 Aapke Existing Knowledge Se Connect

**Vs tumhare manual `get_client(provider)` + fallback ladder (jo labs mein khud likha tha):**
Yeh note ka core connection hai. Tumhare lab mein:
- `get_client(provider)` → provider ke hisaab se alag SDK client banata tha. **Gateway:** `model="provider/name"` string — koi client init nahi.
- Manual `for model in chain: try/except` ladder → **Gateway:** `fallbacks=[...]` ek argument, ya `Router(routing_strategy=...)`.
- Bedrock provider abstraction (boto3 response ko common shape mein convert karna) → **Gateway:** LiteLLM har response ko OpenAI-shape mein normalize karta hai, including Bedrock (`bedrock/...`). Tumhara hand-written normalizer ab built-in hai.
- Ek line summary: **gateway = tumhari provider-abstraction layer, productionized aur battle-tested.**

**Vs LangGraph (jo tum 23 lectures se jaante ho):**
LangGraph **orchestration** hai — nodes, edges, state, loops, conditional routing _between steps_ of an agent. LLM Gateway **infrastructure** hai — single LLM call ko kaunsa provider serve kare. Yeh orthogonal hain, competing nahi. LangGraph ka koi bhi node andar-andar gateway ke through LLM call kar sakta hai. Confuse mat karo: LangGraph routing = "agent ke kaunse step pe jaana hai"; gateway routing = "yeh ek call kaunse provider/model pe jaaye".

**Vs classic embedding-based RAG cache:**
RAG mein semantic cache embedding similarity se match karta hai ("kya yeh question pehle kisi similar question jaisa hai?"). Gateway ka `Cache(type="local")` **exact prompt-hash match** hai — fast aur sasta, par sirf bilkul same prompt par hit hota hai. Dono complementary; gateway cache LLM-call layer pe, RAG semantic cache retrieval layer pe.

**Vs guardrails (jo tum study kar chuke ho):**
Tumne guardrails ko app-level validators ki tarah dekha. Gateway unhe `input_callback`/`success_callback` ke through **centralize** karta hai — ek jagah PII redaction / injection blocking / topic filtering, jo har provider ke har call par automatically lagta hai. Same concept, better placement.

**Genuinely naya kya hai:** provider-agnostic unified API + config-driven routing/load-balancing strategies (`least-busy`, `latency-based`) + built-in per-call cost computation. Yeh teen cheezein tumne manually approximate ki thi; gateway inhe first-class banata hai.

---

## 📋 Key Concepts

| Concept | Matlab |
|---|---|
| **LLM Gateway** | App aur saare LLM providers ke beech middleware — ek unified door |
| **LiteLLM** | Open-source gateway, 100+ providers, `completion()` + `Router` |
| **`completion(model=...)`** | Unified call; `model` string mein provider prefix (`groq/`, `gemini/`, `bedrock/`) |
| **Response normalization** | Har provider ka output OpenAI-shape mein (`choices[0].message.content`) |
| **`fallbacks=[...]`** | Primary fail to auto-retry next model — tumhari manual ladder, ek arg |
| **`completion_cost()`** | Built-in pricing DB se exact USD cost per call |
| **`Cache(type="local"/"redis")`** | Exact prompt-hash caching; double-billing se bachao |
| **`Router` + `model_list`** | Abstract aliases (`fast-cheap`) → real deployments; config-driven swap |
| **Routing strategies** | `simple-shuffle`, `least-busy`, `latency-based-routing` |
| **Load balancing** | Same alias ke peeche kai deployments/keys → rate-limit handling |
| **`success_callback` / `failure_callback`** | Har call log — observability, audit trail, cost attribution |
| **`input_callback`** | Pre-call hook — gateway-level guardrails (PII redact, injection block) |
| **`ChatLiteLLM`** | LangChain wrapper — LCEL chain ke andar gateway plug-in |
| **`.with_fallbacks()`** | LangChain-native fallback stacking on top of gateway |

---

## 💼 Backend Dev Ke Liye Note

Backend engineer ke liye gateway concept **bilkul ek API gateway / service mesh jaisa** hai — bas LLM providers ke liye. Production patterns jo notebook ki best-practices table se directly tumhare backend instincts se match karte hain:

- **Standalone proxy mode** — LiteLLM ko sirf library ki tarah mat use karo; production mein ise **standalone proxy** ki tarah `config.yaml` ke saath chalao (K8s pod + HPA). Tumhari saari apps usko ek OpenAI-compatible endpoint ki tarah hit karti hain. Yeh tumhare microservices ke aage ek API gateway lagane jaisa hi mental model hai.
- **Config as code** — `config.yaml` (model_list, routing, fallbacks) ko Git mein version karo. Model swap = config PR, code deploy nahi.
- **Master key + virtual keys per team** — har team ko alag virtual key do; audit trail aur chargeback milta hai. Yeh API-key management ka classic backend pattern hai.
- **Redis caching, not in-memory** — `type="local"` sirf demo ke liye. Multi-replica setup mein `type="redis"` taaki cache shared + restart-safe ho.
- **Timeouts + `num_retries`** — hamesha set karo, warna hung call user thread block kar dega — wahi discipline jo tum HTTP clients pe lagate ho.
- **Pin model versions** — `claude-3-5-sonnet-20241022` (date-pinned) use karo, na ki floating alias — silent provider-side regression se bachne ke liye.
- **Observability backend** — callbacks ko Langfuse/Helicone/Arize pe bhejo, ya apni DB mein. Yeh tumhare existing logging/tracing stack (OpenTelemetry-style) ka LLM-specific extension hai.
- **Bedrock angle** — agar AWS pe ho, `bedrock/anthropic.claude-...` model strings se Bedrock route hota hai bina boto3 likhe — tumhari manual Bedrock abstraction ka direct replacement.

---

## ✅ Takeaway

- **LLM Gateway = tumhari manual provider-abstraction (`get_client` + fallback ladder + Bedrock normalizer) ka productionized, config-driven version** — ek unified `completion()` API, response normalization free.
- **Fallbacks, retries, caching, cost tracking, load-balancing, observability, guardrails** — sab gateway level pe ek-ek argument / callback, har provider ke har call par automatically.
- **`Router` + aliases** = code se model decouple; provider swap ek config change, zero code rewrite. Routing strategies (`least-busy`, `latency-based`) tumhare manual round-robin se kahin smarter.
- **LangChain `ChatLiteLLM`** se gateway kisi bhi LCEL chain / agent mein drop-in; LangGraph orchestration ke orthogonal — competing nahi.
- **Production mein standalone proxy** (config.yaml + K8s + Redis + virtual keys) ki tarah chalao — bilkul ek API gateway jaisa mental model.

---

## 🔗 Source & Code

- **Course:** Krish Naik — "Complete Agentic AI Course In 10 Hours" — https://youtube.com/watch?v=rV3HJ4LEZ7k
- **Chapter:** LLM Gateways @ **10:30:25**
- **Notebook:** `LLM_Gateway_LiteLLM.ipynb` (KRISHAI Technologies) — extracted source: `KrishNaik_AgenticAI_NewTopics/_sources/llm_gateways.txt`
- **Docs:** LiteLLM — https://docs.litellm.ai · LangChain — https://python.langchain.com
- **How to run:**
  1. `pip install -q litellm langchain langchain-community langchain-openai langchain-litellm python-dotenv`
  2. `.env` banao: `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GROQ_API_KEY`, `GEMINI_API_KEY`
  3. Cells top-to-bottom chalao. Caching demo se pehle `litellm.cache = None` aur callbacks reset karna (notebook ka cleanup cell) taaki pichhli state interfere na kare.
  4. Production: LiteLLM proxy mode — `litellm --config config.yaml` se standalone OpenAI-compatible endpoint chalao.
