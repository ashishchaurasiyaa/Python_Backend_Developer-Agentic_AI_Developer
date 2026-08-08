# Azure OpenAI — AzureOpenAI Client, Entra ID Auth, Deployments, Quota/TPM, PTU, Content Filters

> **Interview context:** Yeh doc specifically Azure GenAI Developer roles ke liye hai —
> `Interview_Prep/05_genai_developer_azure_role_prep.md` §4 ka full expansion.
> Level8 mein high-level coverage already hai (`Level8_Production_LLMOps/04_enterprise_ai_platforms.md` Q3-Q4)
> — woh "kab use karein" batata hai, yeh doc "kaise use karein + kya alag hai" deep mein jaata hai.

## Quick Concepts
- **Azure OpenAI** = OpenAI ke models (GPT-4o, o-series, embeddings, DALL-E, Whisper) **tumhare Azure subscription ke andar** — data residency + compliance + Azure IAM ke saath
- **Deployment name ≠ model name** = Azure mein pehle model *deploy* karte ho apne naam se, phir code mein us deployment name se call karte ho
- **`api_version`** = classic Azure endpoints pe mandatory query param — breaking changes versioned hote hain (naya **v1 API** yeh khatam kar raha hai)
- **Entra ID auth** = API key ki jagah Azure AD tokens / managed identity — enterprise security review ka favourite topic
- **Quota (TPM)** = tokens-per-minute pool per model per region per subscription — deployments is pool se TPM allocate karte hain
- **Content filters** = resource-level built-in filtering (hate/sexual/violence/self-harm + prompt shields) — dono prompt AUR completion pe chalta hai
- **PTU** = Provisioned Throughput Units — reserved capacity, predictable latency; pay-as-you-go = shared capacity, variable latency
- **Deployment types** = Global Standard / Data Zone / Regional Standard (+ inke Provisioned variants) — data processing kahan hoga yeh decide karta hai

---

## Interview Questions & Answers

### Q1: Azure OpenAI vs direct OpenAI — code mein exactly kya badalta hai?
**Answer:**
```python
# pip install openai   (SAME SDK — alag package nahi hai!)

import os

# ===== VANILLA OPENAI =====
from openai import OpenAI

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

response = client.chat.completions.create(
    model="gpt-4o",                       # OpenAI ka model name
    messages=[{"role": "user", "content": "Hello"}],
)

# ===== AZURE OPENAI — 3 cheezein badalti hain =====
from openai import AzureOpenAI

client = AzureOpenAI(
    api_key=os.getenv("AZURE_OPENAI_API_KEY"),
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
    # e.g. https://mycompany-openai.openai.azure.com/
    api_version="2024-10-21",             # GA version — MANDATORY on classic endpoint
)

response = client.chat.completions.create(
    model="my-gpt4o-deployment",          # ⚠ DEPLOYMENT name, not model name!
    messages=[{"role": "user", "content": "Hello"}],
)

# Response object BILKUL SAME hai — choices, usage, finish_reason sab identical
print(response.choices[0].message.content)
print(response.usage.total_tokens)

# DIFF SUMMARY (interview mein yeh 3 points bolo):
# 1. Client class: OpenAI → AzureOpenAI (endpoint + api_version required)
# 2. model= param: model name → YOUR deployment name
# 3. Auth: api-key header OR Entra ID token (vanilla OpenAI sirf Bearer key)
# Baaki calling code (messages, tools, streaming, structured outputs) unchanged.
```

**Senior tip:** Interview mein bolo — "the *calling* code is identical, only client
construction and routing change — which is exactly why abstractions like LiteLLM
(`04_litellm_complete.md`, `model="azure/<deployment>"`) make multi-provider trivial."

---

### Q2: Deployment name vs model name — yeh confusion kyu hai, aur deployment hota kya hai?
**Answer:**
```python
# MENTAL MODEL:
#
# OpenAI direct:   tum OpenAI ke SHARED model instance ko naam se call karte ho
#                  model="gpt-4o"  → unka infra, unka naam
#
# Azure OpenAI:    tum PEHLE apne resource mein model DEPLOY karte ho:
#                  Azure AI Foundry portal (ya CLI/Bicep/Terraform) mein:
#                    - model:            gpt-4o
#                    - model version:    2024-08-06 (pin ya auto-update policy)
#                    - deployment name:  "chat-prod"  ← TUMHARA naam
#                    - deployment type:  Global Standard / Regional / PTU
#                    - TPM allocation:   e.g. 100K TPM is deployment ko
#                  Phir code mein: model="chat-prod"

# ISKA FAYDA KYA (yeh senior answer hai):
# 1. VERSION CONTROL — "chat-prod" ke peeche model version pin kar sakte ho.
#    OpenAI direct pe model alias silently upgrade ho sakta hai;
#    Azure pe upgrade policy TUM control karte ho (auto-update vs pinned).
# 2. BLUE/GREEN for models — "chat-prod-v2" deploy karo naye model version pe,
#    traffic shift karo, code sirf deployment name change karta hai (ya env var).
# 3. CAPACITY ISOLATION — har deployment apna TPM allocation rakhta hai.
#    Batch jobs ka deployment alag, user-facing chat ka alag → noisy neighbour nahi.

# CLI se deployment banana (interview mein bolna impressive hai):
# az cognitiveservices account deployment create \
#   --name my-openai-resource \
#   --resource-group my-rg \
#   --deployment-name chat-prod \
#   --model-name gpt-4o \
#   --model-version "2024-08-06" \
#   --model-format OpenAI \
#   --sku-name "GlobalStandard" \
#   --sku-capacity 100          # 100 = 100K TPM
```

---

### Q3: `api_version` kya hai, aur naya "v1 API" isko kaise replace kar raha hai?
**Answer:**
```python
# ===== CLASSIC (abhi bhi sabse common in prod) =====
# Har request pe ?api-version=... query param jaata hai.
# Azure API surface ko version karta hai (SDK version se alag cheez hai!).

client = AzureOpenAI(
    azure_endpoint="https://myres.openai.azure.com/",
    api_key="...",
    api_version="2024-10-21",        # GA — stable, production default
    # api_version="2025-04-01-preview",  # preview — naye features pehle yahan aate hain
)

# GA vs preview:
# - GA versions (e.g. 2024-10-21): stable, breaking changes nahi
# - Preview versions: naye features (naye models ke params, naye endpoints),
#   but Azure retire kar sakta hai — prod mein GA pin karo

# ===== NAYA v1 API (GA in 2025) — api-version churn khatam =====
# Endpoint: https://<resource>.openai.azure.com/openai/v1/
# Ab PLAIN OpenAI client bhi use kar sakte ho — sirf base_url point karo:

from openai import OpenAI

client = OpenAI(
    base_url="https://myres.openai.azure.com/openai/v1/",
    api_key=os.getenv("AZURE_OPENAI_API_KEY"),
)
response = client.chat.completions.create(
    model="chat-prod",               # deployment name ab bhi — yeh nahi badla
    messages=[{"role": "user", "content": "Hello"}],
)

# v1 API ka point:
# - OpenAI-compatible surface — ongoing api-version bumping ki zaroorat nahi
# - Code OpenAI ↔ Azure ke beech portable (sirf base_url + key switch)
# - Responses API isi v1 surface pe naturally milta hai (Q9 dekho)
```

**Interview angle:** "api_version SDK version nahi hai — yeh Azure ke REST contract
ka version hai. Prod mein GA version pin karte hain; preview sirf tab jab koi naya
feature chahiye. Naya v1 endpoint yeh churn hata deta hai aur OpenAI client se
directly compatible hai." — itna bol diya to yeh question khatam.

---

### Q4: Entra ID (Azure AD) auth vs api-key — enterprise kaise auth karta hai?
**Answer:**
```python
# pip install azure-identity

# ===== OPTION 1: API KEY (simple, but enterprise mein discouraged) =====
# - 2 static keys per resource (key1/key2 for rotation)
# - Problem: shared secret — leak ho sakta hai, per-user attribution nahi,
#   rotation manual, security review mein red flag

client = AzureOpenAI(
    api_key=os.getenv("AZURE_OPENAI_API_KEY"),
    azure_endpoint=endpoint, api_version="2024-10-21",
)

# ===== OPTION 2: ENTRA ID / MANAGED IDENTITY (enterprise default) =====
from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from openai import AzureOpenAI

token_provider = get_bearer_token_provider(
    DefaultAzureCredential(),
    "https://cognitiveservices.azure.com/.default",   # scope — yaad rakho
)

client = AzureOpenAI(
    azure_endpoint=endpoint,
    azure_ad_token_provider=token_provider,   # ⚠ api_key ki jagah — no secrets!
    api_version="2024-10-21",
)
# SDK har call pe fresh token le lega (provider callable hai) — expiry handled.

# DefaultAzureCredential ki chain (order mein try karta hai):
#   1. Environment vars (service principal: AZURE_CLIENT_ID/SECRET/TENANT_ID)
#   2. Managed Identity (App Service / AKS / VM / Container Apps pe ZERO secrets)
#   3. Azure CLI login (local dev — `az login` kiya hua)
# → SAME CODE local dev se prod tak. Yeh line interview mein bolo.

# RBAC roles (kaun sa role chahiye — yeh poocha jaata hai):
#   "Cognitive Services OpenAI User"        → inference calls (chat, embeddings)
#   "Cognitive Services OpenAI Contributor" → + deployments manage karna
# Role assignment resource/RG/subscription scope pe hota hai.

# az role assignment create \
#   --assignee <principal-id> \
#   --role "Cognitive Services OpenAI User" \
#   --scope /subscriptions/<sub>/resourceGroups/<rg>/providers/Microsoft.CognitiveServices/accounts/<res>

# ENTERPRISE WIN (Q9-of-JD "responsible AI/governance" se tie karo):
# - No secrets in code/env → nothing to leak or rotate
# - Per-identity audit trail (kaun se app/user ne call kiya)
# - Conditional access policies apply hoti hain
# - Key-based auth ko resource pe DISABLE bhi kar sakte ho (disableLocalAuth=true)
```

---

### Q5: Quota, TPM/RPM kaise kaam karta hai? 429 aaye to kya karoge?
**Answer:**
```python
# QUOTA MODEL (3-level socho):
#
# Subscription + Region + Model  →  TPM QUOTA POOL   (e.g. gpt-4o in eastus2: 1M TPM)
#         └── Deployment A: 300K TPM  ┐
#         └── Deployment B: 500K TPM  ├─ pool se allocate — sum ≤ quota
#         └── (200K TPM free)         ┘
#
# - TPM = tokens per minute (input + estimated output dono count hote hain)
# - RPM bhi milta hai TPM ke proportion mein (rule of thumb: ~6 RPM per 1K TPM)
# - Quota badhana: Azure portal se request (approval lagta hai for big jumps)
# - Rate limit ENFORCEMENT short windows mein hota hai (per-second/10s buckets),
#   isliye burst traffic 429 de sakta hai even under minute-level TPM

# ===== 429 HANDLING (production pattern) =====
from openai import AzureOpenAI, RateLimitError, APIStatusError
import time, random

def chat_with_retry(client, deployment: str, messages: list, max_retries: int = 5):
    for attempt in range(max_retries):
        try:
            return client.chat.completions.create(model=deployment, messages=messages)
        except RateLimitError as e:
            # Azure Retry-After header bhejta hai — RESPECT it, guess mat karo
            retry_after = None
            if e.response is not None:
                retry_after = e.response.headers.get("Retry-After")
            wait = float(retry_after) if retry_after else min(2 ** attempt, 60)
            wait += random.uniform(0, 1)          # jitter — thundering herd avoid
            time.sleep(wait)
    raise RuntimeError("Rate limited after all retries")

# 429 KE BAAKI FIXES (retry se pehle yeh bolo — architecture answer):
# 1. TPM allocation badhao us deployment ka (quota pool mein space ho to instant)
# 2. Workloads ko alag deployments mein split karo (batch vs interactive)
# 3. Global Standard deployment type use karo (global capacity pool — kam 429s)
# 4. max_tokens realistic rakho — quota estimation max_tokens ko count karta hai!
#    max_tokens=4096 by-default rakhoge to quota 4x jaldi "khatam" dikhega
# 5. Sustained high load → PTU (Q7)
# 6. Non-urgent bulk work → Batch API (50% discount, 24h window, alag quota)
```

**Senior tip:** "max_tokens quota ko inflate karta hai" — yeh detail 90% candidates
nahi jaante. Azure rate limiter available-quota check karta hai
`prompt_tokens + max_tokens` se, actual output se nahi.

---

### Q6: Content filters — kya hai, kaise handle karte ho, kab configure karte ho?
**Answer:**
```python
# Azure OpenAI mein content filtering RESOURCE LEVEL pe built-in hai —
# OpenAI direct se yeh BADA difference hai (wahan sirf policy + optional
# moderation endpoint hai; yahan filter pipeline MANDATORY by default).

# CATEGORIES (dono prompt AND completion pe):
#   hate, sexual, violence, self_harm     — severity: safe/low/medium/high
#   Default: medium+high BLOCK hota hai har category mein
# PLUS additional models:
#   - Prompt Shields: jailbreak attempts + indirect/injected attacks (documents mein)
#   - Protected material: copyrighted text / code detection
#   - Groundedness detection (RAG ke liye — response sources se grounded hai ya nahi)

# ===== KYA HOTA HAI JAB FILTER TRIGGER HOTA HAI =====

# CASE 1: PROMPT filtered → API call hi FAIL hoti hai
from openai import BadRequestError

try:
    response = client.chat.completions.create(model="chat-prod", messages=messages)
except BadRequestError as e:
    if e.body and e.body.get("code") == "content_filter":
        # HTTP 400, code="content_filter" — user ko graceful message do,
        # LOG karo (audit), retry MAT karo (deterministic block hai)
        handle_blocked_prompt(e.body.get("innererror", {}))

# CASE 2: COMPLETION filtered → response aati hai but truncated/empty
choice = response.choices[0]
if choice.finish_reason == "content_filter":
    # Output block hua — "stop" nahi mila
    log_filtered_completion(response)

# Per-response filter details bhi milti hain (Azure-only fields):
# response.choices[0].content_filter_results  → per-category severity+filtered
# response.prompt_filter_results              → prompt side ka verdict

# ===== CONFIGURABILITY =====
# - Azure AI Foundry portal → custom content filter policy banao
#   (per-category thresholds adjust; deployment pe attach hota hai)
# - Severity thresholds RAISE/LOWER kar sakte ho; filters fully OFF karna
#   restricted hai — approved use cases ke liye Microsoft form bharna padta hai
#   (e.g. abuse-detection products jo khud harmful content process karte hain)
# - STREAMING: default mode chunks ko filter-buffer karta hai (thoda latency);
#   "asynchronous filter" mode instant streaming deta hai but filter verdict
#   baad mein aata hai — UI ko potentially content retract karna pad sakta hai

# INTERVIEW TIE-IN: JD ka "responsible AI" yahan se answer karo —
# "Azure pe content safety infra-level pe milta hai: default filters, prompt
# shields for injection, configurable per-deployment policies, plus filter
# results API response mein aate hain jo hum audit-log karte hain."
```

---

### Q7: PTU vs pay-as-you-go — kab kya use karoge?
**Answer:**
```python
# ===== PAY-AS-YOU-GO ("Standard") =====
# - Per-token billing, shared capacity pool
# - Latency VARIABLE (noisy neighbours, capacity pressure)
# - 429s possible under regional capacity crunch
# - Zero commitment — dev/test aur spiky/low-volume prod ke liye perfect

# ===== PTU (Provisioned Throughput Units) =====
# - RESERVED model-processing capacity — hourly billing per PTU,
#   monthly/yearly Azure Reservations pe BADA discount (~70-85% vs hourly)
# - PREDICTABLE latency + throughput (isolated capacity, latency SLA-backed)
# - Min PTU per model hota hai (e.g. gpt-4o Global Provisioned min ~15 PTU)
# - Capacity calculator se estimate karte ho: peak TPM → required PTUs

# DECISION FRAMEWORK (yeh table interview answer hai):
#
# | Workload                              | Choice                            |
# |---------------------------------------|-----------------------------------|
# | Dev/test, POCs                         | Pay-as-you-go (Global Standard)   |
# | Spiky, unpredictable traffic           | Pay-as-you-go                     |
# | High sustained volume, latency-strict  | PTU                               |
# | Baseline + spikes                      | PTU base + SPILLOVER to standard  |
# | Overnight bulk / evals / backfills     | Batch API (50% cheaper, 24h SLA)  |
#
# SPILLOVER (senior detail): PTU deployment pe traffic overflow ho to Azure
# automatically excess ko paired standard deployment pe route kar sakta hai —
# best of both: guaranteed baseline + elastic burst.

# ===== DEPLOYMENT TYPES (data processing location axis) =====
# Standard (pay-as-you-go) flavours:
#   Global Standard    → processing GLOBAL capacity pool mein kahin bhi
#                        (best availability/throughput; data AT REST resource
#                         region mein hi rehta hai)
#   Data Zone Standard → processing EU-zone ya US-zone ke andar bounded
#   Regional Standard  → processing SIRF resource region mein
# PTU flavours: Global / Data Zone / Regional Provisioned — same axis.
#
# COMPLIANCE MAPPING: strict data-processing-residency requirement
# (e.g. "inference EU ke bahar nahi jaa sakta") → Data Zone ya Regional.
# Sirf data-at-rest concern hai → Global Standard chalega (rest resource region mein).
```

---

### Q8: Regional availability — kya dhyan rakhna hota hai?
**Answer:**
```python
# 1. MODEL × REGION MATRIX: har model har region mein NAHI hota.
#    Naye models pehle limited regions mein aate hain (typically East US 2,
#    Sweden Central jaise regions pehle paate hain), phir rollout hota hai.
#    → Architecture decision: resource region choose karne se pehle
#      model availability table check karo (Microsoft Learn pe "model summary
#      table and region availability" page).
#
# 2. QUOTA PER REGION: TPM quota subscription+region+model combo pe hai.
#    Ek region mein quota khatam → doosre region mein resource banao,
#    LiteLLM Router / apna router dono ke beech load-balance kare
#    (04_litellm_complete.md ka Router pattern — yahan directly apply hota hai).
#
# 3. DATA RESIDENCY vs AVAILABILITY TRADEOFF:
#    Global Standard   = best model availability + highest default quotas
#    Regional Standard = strictest residency, but limited models + capacity
#    Data Zone         = middle ground (EU/US zone)
#
# 4. DR / MULTI-REGION PATTERN (system design round ke liye):
#    - 2+ regions mein same deployment name se deploy karo ("chat-prod")
#    - Client-side failover ya API Management / LiteLLM proxy ke through route
#    - Deployment name same rakhne se failover = sirf endpoint swap
```

---

### Q9: Responses API Azure pe — kya hai aur Chat Completions se kab prefer karoge?
**Answer:**
```python
# Responses API = OpenAI ka newer unified API (chat completions + tools +
# stateful conversation ek surface pe). Azure pe yeh v1 API surface ke saath aata hai.

from openai import OpenAI

# v1 endpoint use karo (Q3 wala) — Responses API isi pe hai
client = OpenAI(
    base_url="https://myres.openai.azure.com/openai/v1/",
    api_key=os.getenv("AZURE_OPENAI_API_KEY"),
)

response = client.responses.create(
    model="chat-prod",                     # deployment name — Azure rule yahan bhi
    input="Explain HNSW indexes in two lines",
)
print(response.output_text)                # convenience accessor

# STATEFUL CHAINING (Responses API ka killer feature):
follow_up = client.responses.create(
    model="chat-prod",
    previous_response_id=response.id,      # server-side conversation state!
    input="Now compare with IVFFlat",
)
# → Har turn pe pura history resend karne ki zaroorat nahi (token savings + simpler code)

# TOOLS: web_search / file_search / code_interpreter / function calling —
# built-in tool types Responses API pe first-class hain.

# CHAT COMPLETIONS vs RESPONSES — interview answer:
# - Chat Completions: industry-standard, har framework support karta hai, stateless
# - Responses: stateful (previous_response_id), built-in tools, naya default for
#   agentic patterns; Azure pe availability API-version/region dependent hai
# - Prod advice: existing systems Chat Completions pe chalte rehte hain;
#   naye agentic builds Responses pe consider karo — but check Azure region support first
```

---

### Q10: "Azure OpenAI vs direct OpenAI — enterprise kyu Azure choose karta hai?" (THE compliance answer)
**Answer:**
```
YEH QUESTION 2026-08-11 WALE INTERVIEW MEIN AANA ALMOST GUARANTEED HAI.
Structure: Compliance → Security → Enterprise ops → Honest tradeoffs.

1. DATA RESIDENCY & PROCESSING BOUNDARIES
   - Prompts/completions tumhare Azure tenant ke boundary mein process hote hain
   - Data Zone / Regional deployments se PROCESSING location bhi pin hota hai
   - Training pe use NAHI hota (direct OpenAI API bhi ab yeh promise karta hai,
     but Azure pe yeh Microsoft ke enterprise DPA + compliance framework ke
     under contractually covered hota hai — auditor ko yeh sunna hota hai)

2. COMPLIANCE CERTIFICATIONS INHERIT HOTI HAIN
   - Azure ka compliance portfolio (SOC 2, ISO 27001, HIPAA BAA, GDPR DPA,
     regional certifications) Azure OpenAI pe extend hota hai
   - Regulated industries (BFSI, healthcare, gov) ke liye procurement
     Microsoft ke saath already approved hota hai — NEW VENDOR ONBOARDING SKIP

3. IDENTITY & NETWORK SECURITY
   - Entra ID / managed identity auth (Q4) — no API keys at all
   - Private Endpoints / VNet integration — traffic public internet touch nahi karta
   - Key-based auth disable kar sakte ho; RBAC + conditional access + audit logs

4. RESPONSIBLE AI INFRA BUILT-IN
   - Content filters + prompt shields resource level pe (Q6) — DIY nahi karna

5. ENTERPRISE OPS
   - Billing existing Azure agreement (EA/MCA) mein — no new procurement
   - SLA + Microsoft support contract; PTU se latency guarantees (Q7)
   - Azure Monitor / diagnostic logs existing observability mein feed hote hain

HONEST TRADEOFFS (yeh bolne se answer senior lagta hai):
   - Naye OpenAI models/features pehle openai.com pe aate hain, Azure pe
     thoda lag ke saath (gap ab kaafi chhota hai, but exists)
   - Quota management + deployment overhead — direct API zyada simple hai
   - Model breadth: sirf OpenAI(+few) models — Claude chahiye to AWS Bedrock ya
     Foundry Models catalog dekho (Level8 doc 04 ka selection guide)

ONE-LINER CLOSER:
   "Capability same hai — enterprise Azure isliye choose karta hai kyunki
    AI unke EXISTING security, compliance aur billing perimeter ke andar
    aa jaata hai, bajaye ek naya vendor perimeter banane ke."
```

---

## Quick-Reference Card

| Cheez | OpenAI direct | Azure OpenAI |
|---|---|---|
| Client | `OpenAI(api_key=...)` | `AzureOpenAI(azure_endpoint, api_version, api_key/azure_ad_token_provider)` |
| `model=` | Model name (`gpt-4o`) | **Deployment name** (tumhara) |
| API versioning | Nahi (SDK hi contract) | `api_version` pin (ya naya v1 endpoint) |
| Auth | API key only | API key **ya Entra ID/managed identity** |
| Rate limits | Org-level tiers | TPM quota per sub+region+model, deployment-allocated |
| Content filter | Policy + optional moderation API | **Built-in mandatory pipeline**, configurable per deployment |
| Reserved capacity | — | **PTU** (+ spillover to standard) |
| Data processing location | OpenAI infra | Global / Data Zone / Regional — TUM choose karte ho |
| Batch discount | 50% | 50% (Global Batch) |
| Networking | Public API | Private Endpoints / VNet possible |

---

## Interview Q&A (rapid fire)

**Q: Same SDK hai to `AzureOpenAI` alag class kyu hai?**
A: URL construction (`{endpoint}/openai/deployments/{name}/...` + `api-version` param)
aur auth header (`api-key` / Entra bearer token) alag hote hain — class yeh handle
karti hai. v1 endpoint pe plain `OpenAI` client bhi chal jaata hai `base_url` ke saath.

**Q: Deployment name galat diya to kya error aata hai?**
A: 404 `DeploymentNotFound` — yeh Azure ka classic first-day error hai. Model name
(`gpt-4o`) daal dena jabki deployment ka naam kuch aur hai = sabse common mistake.

**Q: TPM quota aur deployment capacity mein kya farak?**
A: Quota = region+model ka pool (ceiling); deployment capacity = us pool se ek
deployment ko diya gaya slice. Pool se zyada allocate nahi kar sakte.

**Q: Content filter false positive pe user experience kaise bachate ho?**
A: Prompt-block (400) pe graceful "rephrase" message; completion-block
(`finish_reason=content_filter`) pe retry-with-rewording ya human handoff; filter
results ko audit-log; aur agar legit use case consistently block ho raha hai to
deployment pe custom filter policy (raised thresholds) apply karte hain.

**Q: PTU kab justify hota hai?**
A: Jab sustained throughput itna high ho ki hourly-reserved capacity per-token
billing se sasti pad jaaye (calculator se break-even nikalta hai), YA jab latency
predictability contractual/UX requirement ho — sirf cost nahi, consistency bhi.

**Q: Managed identity local dev pe kaise chalti hai jab wahan identity nahi hoti?**
A: `DefaultAzureCredential` chain — local pe Azure CLI credential (`az login`) pick
hota hai, prod pe managed identity. Code identical rehta hai.

---

Related: `Level8_Production_LLMOps/04_enterprise_ai_platforms.md` (Q3 basic Azure client,
Q4 enterprise-platform rationale, selection guide — yeh doc usko deep karta hai),
`04_litellm_complete.md` (`azure/<deployment>` routing + multi-region Router),
`07_error_handling_retries.md` (retry patterns jo Q5 ke 429 handling ke neeche hain),
`Level5_RAG_Vector_Databases/11_azure_ai_search.md` (Azure-native RAG ka retrieval side),
`Interview_Prep/05_genai_developer_azure_role_prep.md` (§4 cheat sheet + interview plan).
Practical: `11_azure_openai_practical.py`.
