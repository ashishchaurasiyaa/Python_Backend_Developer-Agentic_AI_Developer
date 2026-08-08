"""
Azure OpenAI — Complete Practical
==================================
Topics:
  1. AzureOpenAI client vs OpenAI client (endpoint, api_version, deployment names)
  2. Entra ID / managed identity auth (vs api-key)
  3. Chat call + Azure-only response fields (content filter results)
  4. 429 / quota handling with Retry-After
  5. Embeddings on Azure
  6. v1 endpoint + Responses API
  7. Deployment types + PTU vs pay-as-you-go decision table

Install: pip install openai azure-identity
Env (for live mode):
  AZURE_OPENAI_ENDPOINT      = https://<resource>.openai.azure.com/
  AZURE_OPENAI_API_KEY       = <key>            (or use az login + Entra section)
  AZURE_OPENAI_DEPLOYMENT    = <chat deployment name, e.g. gpt-4o>  [optional]
  AZURE_OPENAI_EMBED_DEPLOYMENT = <embedding deployment name>       [optional]
Run: python 11_azure_openai_practical.py
"""

import os, time, random

AZURE_ENDPOINT   = os.getenv("AZURE_OPENAI_ENDPOINT", "")
AZURE_API_KEY    = os.getenv("AZURE_OPENAI_API_KEY", "")
CHAT_DEPLOYMENT  = os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4o")
EMBED_DEPLOYMENT = os.getenv("AZURE_OPENAI_EMBED_DEPLOYMENT", "text-embedding-3-small")

MOCK_MODE = not (AZURE_ENDPOINT and AZURE_API_KEY)
if MOCK_MODE:
    print("⚠  MOCK MODE — set AZURE_OPENAI_ENDPOINT + AZURE_OPENAI_API_KEY for live calls\n")

try:
    from openai import AzureOpenAI, OpenAI, RateLimitError, BadRequestError
    OPENAI_SDK_AVAILABLE = True
except ImportError:
    OPENAI_SDK_AVAILABLE = False
    print("openai not installed: pip install openai\n")

# ─────────────────────────────────────────────────────────────────────────────
# SECTION 1: Client setup — the 3-line diff vs vanilla OpenAI
# INTERVIEW: same SDK, same .chat.completions.create() — only client + routing change
# ─────────────────────────────────────────────────────────────────────────────

print("=" * 60)
print("SECTION 1: AzureOpenAI client vs OpenAI client")
print("=" * 60)

CLIENT_DIFF = """\
# Vanilla OpenAI                          # Azure OpenAI
from openai import OpenAI                 from openai import AzureOpenAI
client = OpenAI(                          client = AzureOpenAI(
    api_key="sk-...",                         api_key=os.environ["AZURE_OPENAI_API_KEY"],
)                                             azure_endpoint="https://myres.openai.azure.com/",
                                              api_version="2024-10-21",   # Azure REST contract version
                                          )
client.chat.completions.create(           client.chat.completions.create(
    model="gpt-4o",   # MODEL name            model="chat-prod",  # DEPLOYMENT name (yours!)
    messages=[...],                           messages=[...],
)                                         )
"""
print(CLIENT_DIFF)

def make_client():
    """INTERVIEW: AzureOpenAI = endpoint + api_version + deployment-name routing."""
    return AzureOpenAI(
        api_key=AZURE_API_KEY,
        azure_endpoint=AZURE_ENDPOINT,
        api_version="2024-10-21",         # GA version — pin in prod
    )

def azure_chat(prompt: str) -> str:
    if MOCK_MODE or not OPENAI_SDK_AVAILABLE:
        return f"[Mock Azure response via deployment '{CHAT_DEPLOYMENT}']: Hello!"
    client = make_client()
    response = client.chat.completions.create(
        model=CHAT_DEPLOYMENT,            # NOT "gpt-4o" — YOUR deployment name
        messages=[{"role": "user", "content": prompt}],
        max_tokens=100,
    )
    return response.choices[0].message.content

print("  Chat call →", azure_chat("Say hello in 5 words"))

# Common first-day error (worth knowing the shape of):
#   openai.NotFoundError: Error code: 404 - {'error': {'code': 'DeploymentNotFound', ...}}
#   → you passed a MODEL name where Azure wanted your DEPLOYMENT name


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 2: Entra ID auth (enterprise default — no API keys at all)
# INTERVIEW: DefaultAzureCredential chain → same code local (az login) and prod (MI)
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 60)
print("SECTION 2: Entra ID / Managed Identity auth")
print("=" * 60)

ENTRA_CODE = '''\
# pip install azure-identity
from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from openai import AzureOpenAI

token_provider = get_bearer_token_provider(
    DefaultAzureCredential(),
    "https://cognitiveservices.azure.com/.default",   # the scope — memorize it
)

client = AzureOpenAI(
    azure_endpoint="https://myres.openai.azure.com/",
    azure_ad_token_provider=token_provider,   # instead of api_key — zero secrets
    api_version="2024-10-21",
)

# DefaultAzureCredential tries in order:
#   1. env service principal  2. Managed Identity (prod)  3. Azure CLI (local dev)
# RBAC role needed: "Cognitive Services OpenAI User"
# Hardening: set disableLocalAuth=true on the resource → key auth fully off
'''
print(ENTRA_CODE)

# Live attempt only if azure-identity present AND user has a logged-in credential
if not MOCK_MODE and OPENAI_SDK_AVAILABLE:
    try:
        from azure.identity import DefaultAzureCredential, get_bearer_token_provider
        provider = get_bearer_token_provider(
            DefaultAzureCredential(), "https://cognitiveservices.azure.com/.default"
        )
        entra_client = AzureOpenAI(
            azure_endpoint=AZURE_ENDPOINT,
            azure_ad_token_provider=provider,
            api_version="2024-10-21",
        )
        r = entra_client.chat.completions.create(
            model=CHAT_DEPLOYMENT,
            messages=[{"role": "user", "content": "ping"}],
            max_tokens=5,
        )
        print("  Entra ID auth call OK →", r.choices[0].message.content)
    except ImportError:
        print("  (azure-identity not installed — skipping live Entra call)")
    except Exception as e:
        print(f"  (Entra call skipped: {type(e).__name__} — needs az login + RBAC role)")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 3: Content filter results — Azure-only response fields
# INTERVIEW: prompt block = 400 code:"content_filter"; output block = finish_reason
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 60)
print("SECTION 3: Content filter handling")
print("=" * 60)

FILTER_CODE = '''\
# CASE 1 — prompt blocked: the CALL fails (HTTP 400)
try:
    r = client.chat.completions.create(model="chat-prod", messages=msgs)
except BadRequestError as e:
    if e.body and e.body.get("code") == "content_filter":
        # deterministic block — do NOT retry; log + show graceful message
        ...

# CASE 2 — completion blocked: call succeeds, output truncated
if r.choices[0].finish_reason == "content_filter":
    ...

# Azure-only inspection fields on every response:
#   r.choices[0].content_filter_results  → {hate: {filtered, severity}, sexual: ..., ...}
#   r.prompt_filter_results              → prompt-side verdicts
# Categories: hate / sexual / violence / self_harm (safe|low|medium|high)
# Plus: Prompt Shields (jailbreak + indirect injection), protected material
'''
print(FILTER_CODE)

if not MOCK_MODE and OPENAI_SDK_AVAILABLE:
    client = make_client()
    r = client.chat.completions.create(
        model=CHAT_DEPLOYMENT,
        messages=[{"role": "user", "content": "What is 2+2?"}],
        max_tokens=10,
    )
    cfr = getattr(r.choices[0], "content_filter_results", None)
    print("  finish_reason:", r.choices[0].finish_reason)
    print("  content_filter_results present:", bool(cfr))
else:
    print("  [Mock] finish_reason: stop | content_filter_results: all categories safe")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 4: 429 / quota handling
# INTERVIEW: TPM quota = per subscription+region+model pool, sliced per deployment.
# Rate limiter counts prompt_tokens + max_tokens — keep max_tokens realistic!
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 60)
print("SECTION 4: 429 handling with Retry-After")
print("=" * 60)

def chat_with_retry(prompt: str, max_retries: int = 5) -> str:
    """Respect Azure's Retry-After header; exponential backoff + jitter as fallback."""
    if MOCK_MODE or not OPENAI_SDK_AVAILABLE:
        return "[Mock] would retry on RateLimitError honoring Retry-After header"
    client = make_client()
    for attempt in range(max_retries):
        try:
            r = client.chat.completions.create(
                model=CHAT_DEPLOYMENT,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=50,             # realistic max_tokens → quota not inflated
            )
            return r.choices[0].message.content
        except RateLimitError as e:
            retry_after = None
            if e.response is not None:
                retry_after = e.response.headers.get("Retry-After")
            wait = float(retry_after) if retry_after else min(2 ** attempt, 60)
            wait += random.uniform(0, 1)   # jitter
            print(f"  429 → waiting {wait:.1f}s (attempt {attempt + 1})")
            time.sleep(wait)
    raise RuntimeError("rate limited after retries")

print("  ", chat_with_retry("one word: ok"))

print("""
  Beyond retries (say this FIRST in interviews — architecture before duct tape):
    1. raise deployment TPM allocation (if quota pool has headroom)
    2. split workloads across deployments (batch vs interactive isolation)
    3. Global Standard deployment type → global capacity pool, fewer 429s
    4. Batch API for bulk jobs (50% cheaper, separate quota)
    5. sustained load → PTU (Section 6)""")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 5: Embeddings on Azure (RAG ka ingredient — Level5 doc 11 se pairs)
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 60)
print("SECTION 5: Embeddings on Azure")
print("=" * 60)

def azure_embed(texts):
    """Same embeddings.create() — model= is your EMBEDDING deployment name."""
    if MOCK_MODE or not OPENAI_SDK_AVAILABLE:
        return [[0.0] * 8 for _ in texts]   # fake 8-dim vectors
    client = make_client()
    r = client.embeddings.create(model=EMBED_DEPLOYMENT, input=texts)
    return [item.embedding for item in r.data]

vecs = azure_embed(["Azure AI Search stores these", "in a vector field"])
print(f"  embedded {len(vecs)} texts, dims={len(vecs[0])}"
      + ("  (mock)" if MOCK_MODE else ""))


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 6: v1 endpoint + Responses API
# INTERVIEW: v1 = OpenAI-compatible surface, no api-version churn;
# Responses API = stateful (previous_response_id) + built-in tools
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 60)
print("SECTION 6: v1 endpoint + Responses API")
print("=" * 60)

V1_CODE = '''\
from openai import OpenAI   # PLAIN client — that's the point of v1

client = OpenAI(
    base_url="https://myres.openai.azure.com/openai/v1/",
    api_key=os.environ["AZURE_OPENAI_API_KEY"],
)

r1 = client.responses.create(model="chat-prod", input="Explain HNSW in 2 lines")
print(r1.output_text)

r2 = client.responses.create(
    model="chat-prod",
    previous_response_id=r1.id,       # server-side conversation state
    input="Now compare with IVFFlat",
)
# No resending full history each turn → token savings + simpler code
'''
print(V1_CODE)

if not MOCK_MODE and OPENAI_SDK_AVAILABLE:
    try:
        v1_client = OpenAI(
            base_url=AZURE_ENDPOINT.rstrip("/") + "/openai/v1/",
            api_key=AZURE_API_KEY,
        )
        r = v1_client.responses.create(model=CHAT_DEPLOYMENT, input="Say ok")
        print("  Responses API live →", r.output_text[:60])
    except Exception as e:
        print(f"  (Responses API not available on this resource/region: {type(e).__name__})")
else:
    print("  [Mock] Responses API: output_text='ok', then chained via previous_response_id")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 7: Deployment types + PTU vs pay-as-you-go (pure Python — always runs)
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 60)
print("SECTION 7: Deployment types + PTU decision table")
print("=" * 60)

DEPLOYMENT_TYPES = [
    # (type, processing location, when)
    ("Global Standard",    "anywhere (global pool)",  "default: best availability + quota"),
    ("Data Zone Standard", "EU zone or US zone",      "zone-bounded processing requirement"),
    ("Regional Standard",  "resource region only",    "strict in-region processing"),
    ("Global Provisioned", "global pool, reserved",   "PTU: sustained load, latency SLA"),
    ("Regional Provisioned","in-region, reserved",    "PTU + residency together"),
]
print(f"  {'Type':<20} {'Processing':<26} When")
for t, loc, when in DEPLOYMENT_TYPES:
    print(f"  {t:<20} {loc:<26} {when}")

WORKLOAD_CHOICE = [
    ("Dev/test, POC",                 "Pay-as-you-go (Global Standard)"),
    ("Spiky unpredictable traffic",   "Pay-as-you-go"),
    ("High sustained + latency SLA",  "PTU (reserved capacity)"),
    ("Baseline + occasional bursts",  "PTU base + spillover to standard"),
    ("Overnight bulk / evals",        "Batch API (50% discount, 24h window)"),
]
print("\n  Workload → billing choice:")
for w, c in WORKLOAD_CHOICE:
    print(f"  {w:<32}: {c}")

print("\n" + "=" * 60)
print("AZURE OPENAI INTERVIEW SUMMARY:")
print("  Client: AzureOpenAI(endpoint, api_version) — or plain OpenAI on /openai/v1/")
print("  model= takes YOUR deployment name, never the raw model name")
print("  Auth: api-key OR Entra ID token provider (enterprise: keys disabled)")
print("  Quota: TPM pool per sub+region+model → sliced across deployments")
print("  Content filters: built-in, both directions, results on every response")
print("  PTU = reserved capacity + predictable latency; PAYG = shared + variable")
print("  Why Azure: data boundary + compliance + identity — not capability")
print("=" * 60)
