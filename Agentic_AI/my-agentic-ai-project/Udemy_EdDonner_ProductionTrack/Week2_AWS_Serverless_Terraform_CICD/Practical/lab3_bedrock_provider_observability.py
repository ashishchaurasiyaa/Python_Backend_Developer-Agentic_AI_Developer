"""
LAB 3 — Bedrock provider + OpenAI->Bedrock migration + CloudWatch-style observability
=====================================================================================
Title: Ek PROVIDER-AGNOSTIC `call_llm(prompt)` banao jo OpenAI <-> Bedrock ke beech
       ek-line config change se swap ho jaaye, aur har call ko CloudWatch-style
       STRUCTURED JSON log se wrap karo — taaki wahi log aage metrics/alarms ban sake.

KYA SEEKHENGE (what concepts):
- PROVIDER ABSTRACTION: `call_llm(prompt)` ko ek thin interface ke peeche rakho. Caller
  (Lambda handler) ko pata hi nahi ki andar Bedrock hai ya groq fallback. Yahi pattern
  (L47 ka core sabak) provider switch ko poore codebase ka change nahi, ek-line config
  change bana deta hai.
- BEDROCK invoke_model API SHAPE: boto3 `bedrock-runtime` ka `invoke_model` OpenAI ke
  `chat.completions.create` se BILKUL alag hai. Hum DONO shapes side-by-side dikhayenge:
    * OpenAI : client.chat.completions.create(model=, messages=[{role,content}])
               -> response.choices[0].message.content   (pydantic object)
    * Bedrock: client.invoke_model(modelId=, body=json.dumps({...provider-specific...}))
               -> json.loads(response["body"].read())    (raw bytes -> dict)
  Aur dhyan: har Bedrock model family ka request/response body ALAG hota hai
  (Anthropic Claude vs Amazon Nova/Titan) — hum dono ka exact JSON banayenge/parse karenge.
- LAZY boto3 + GRACEFUL DEGRADE: is env me boto3 aur AWS creds dono NAHI hain. Isliye
  boto3 ko sirf AWS code-path ke andar try/except me import karte hain; missing ho to
  saaf Hinglish note ("AWS not configured -> local fallback") print karke groq fallback
  par chale jaate hain. NA crash, NA hang.
- OBSERVABILITY: har call ke aas-paas ek STRUCTURED JSON log line stdout par chhapti hai:
  {"event":"llm_call","provider":..,"model":..,"latency_ms":..,"prompt_tokens":..,
   "completion_tokens":..,"ok":..}. Lambda ka stdout seedha CloudWatch Logs me jaata
   hai; structured (JSON) hone se CloudWatch in fields ko metrics/alarms me convert
   kar leta hai (L49: metrics, logs, alarms — "proof via metrics, not faith").
- LAMBDA HANDLER: ek REAL deployable `handler(event, context)` jo API-Gateway-proxy
  contract follow karta hai (event["httpMethod"]/["path"]/["body"] -> statusCode/body).
  Self-demo isi handler ko hand-built mock event dicts se invoke karta hai.

KAISE CHALANA (how to run) — CWD = repo root:
    # Default: self-demo (no AWS / no key bhi chalega, exit 0)
    uv run Udemy_EdDonner_ProductionTrack/Week2_AWS_Serverless_Terraform_CICD/Practical/lab3_bedrock_provider_observability.py

    # Sirf provider selection + ek structured log line dekhni ho:
    uv run Udemy_EdDonner_ProductionTrack/Week2_AWS_Serverless_Terraform_CICD/Practical/lab3_bedrock_provider_observability.py --one

LECTURE MAPPING: Ed Donner "AI Engineer Production Track", Week 2 · Day 3.
  L46 = Setting Up Amazon Bedrock (IAM: AmazonBedrockFullAccess + CloudWatchFullAccess;
        per-model access; Nova micro/lite/pro; Bedrock = AWS managed LLM gateway, no API keys).
  L47 = Migrating OpenAI -> Bedrock (boto3 bedrock-runtime client; OpenAI format se Bedrock
        format me translate; response = plain dict; provider abstraction = ek-file change).
  L48 = Deploying Bedrock LLMs to Lambda (zip upload; health check confirms model=Nova;
        paid model bina API key — IAM execution role authorize karta hai, bill AWS account par).
  L49 = Monitoring with CloudWatch + Bedrock Metrics (invocations, input/output token count,
        invocation latency; structured logs -> metrics -> dashboards -> alarms).
  NOTE: Ed ne lecture me high-level `bedrock.converse(...)` API use ki. Yeh lab task ke
  hisaab se LOWER-LEVEL `invoke_model(...)` ko PRIMARY rakhta hai (kyunki wahi har model
  family ka exact request/response JSON expose karta hai = real learning), aur `converse`
  ko ek note me dikhaata hai — dono real Bedrock APIs hain.

COST: Is lab ko LOCALLY chalana = $0. boto3/AWS creds na ho to groq free-tier fallback
  (llama-3.3-70b) use hota hai; LLM key bhi na ho to live call SKIP karke sirf request/
  response SHAPE dikhta hai + structured logs — phir bhi EXIT 0, zero cost, zero crash.
  REAL AWS deploy (runbook): Bedrock Nova per-1000-tokens bill (L47) — Nova Micro ek
  conversation "radar par bhi nahi", Nova Pro ~3/10 cent/conversation; AWS account par
  billed (koi API key/upfront nahi). Lambda invocation + CloudWatch logs/metrics ka
  chhota charge — Ed ka pura course estimate ~$5-$10 (zyaadatar free-tier ke andar).
"""

import json
import os
import sys
import time

from dotenv import load_dotenv
from openai import OpenAI

# .env load. override=True => .env value shell ki purani value ko jeet jaaye
# (Ed Donner ki convention). Yeh GROQ_API_KEY / BEDROCK_MODEL_ID dono uthaa lega.
load_dotenv(override=True)


# ===========================================================================
# get_client — fallback (local) LLM ke liye. EXACT helper (placeholder fix ke saath).
# ===========================================================================
# Groq/Gemini OpenAI-compatible hain — sirf base_url alag. Isliye wahi ek `openai`
# library teeno providers ko call kar leti hai. Yeh helper FallbackProvider ke andar
# use hota hai jab Bedrock available na ho (no boto3 / no AWS creds).
def get_client(provider: str = "groq"):
    """(client, model). Default groq => free, OpenAI-compatible. NOTE the `or "placeholder"`:
    OpenAI() None api_key par CONSTRUCTION time hi crash karta hai, isliye placeholder."""
    if provider == "groq":
        return OpenAI(base_url="https://api.groq.com/openai/v1",
                      api_key=os.getenv("GROQ_API_KEY") or "placeholder"), "llama-3.3-70b-versatile"
    if provider == "gemini":
        return OpenAI(base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
                      api_key=os.getenv("GOOGLE_API_KEY") or "placeholder"), "gemini-2.5-flash"
    raise ValueError(f"Unknown provider: {provider}")


# ===========================================================================
# ############  WHY AN ABSTRACTION? (L47 ka DIL — ek-line swap)  #############
# ===========================================================================
# OpenAI aur Bedrock ka API shape alag hai. Agar har jagah seedhe SDK call likho,
# to provider badalne par poore codebase ke 50 jagah change karne padenge.
#
# Solution: ek THIN PROTOCOL define karo — `generate(prompt) -> ProviderResult`.
# Har provider us protocol ka ek implementation hai. Caller (Lambda handler) sirf
# `call_llm(prompt)` bulata hai; usse pata hi nahi andar kaun hai. Provider switch
# ab ek CONFIG decision hai (BEDROCK_MODEL_ID env set hai? to Bedrock; warna fallback)
# — code ka ek-line change, na ki har caller ko chhedna.
#
# Yeh sirf "saaf code" nahi — yeh PORTABILITY + testability hai: local me free groq
# par develop karo, prod me Bedrock par chalao, exactly same handler code.
# ===========================================================================


class ProviderResult:
    """Provider-neutral result. Har provider isi shape me normalize karta hai taaki
    caller ko OpenAI vs Bedrock ke alag-alag response dicts handle na karne padein."""
    def __init__(self, text, model, prompt_tokens=0, completion_tokens=0):
        self.text = text                          # generated string
        self.model = model                        # jo model use hua
        self.prompt_tokens = prompt_tokens or 0   # input tokens (cost + CloudWatch metric)
        self.completion_tokens = completion_tokens or 0  # output tokens


# ---------------------------------------------------------------------------
# BedrockProvider — boto3 bedrock-runtime invoke_model. (L46/L47/L48)
# ---------------------------------------------------------------------------
# DESIGN: boto3 ko LAZILY (call ke time) import karte hain, module top par NAHI.
# Kyun? (1) is env me boto3 install hi nahi — top-level import poori file ko crash
# kar deta. (2) Lambda runtime me boto3 built-in aata hai, par local dev me nahi —
# lazy import dono jagah safe. Agar import ya creds fail ho, hum exception raise karte
# hain jise call_llm() catch karke fallback par bhej deta hai.
# ---------------------------------------------------------------------------
class BedrockProvider:
    def __init__(self, model_id, region=None):
        self.model_id = model_id
        # AWS_REGION Lambda runtime me auto-set hota hai; local me default us-east-1.
        self.region = region or os.getenv("AWS_REGION", "us-east-1")
        self.name = "bedrock"

    # --- request body builder: har model FAMILY ka body ALAG hai ----------
    # Yahi invoke_model ka asli "gotcha" hai (vs OpenAI ka ek hi shape). Hum
    # model_id prefix dekh ke sahi JSON body banate hain.
    def _build_body(self, prompt):
        if self.model_id.startswith("anthropic."):
            # Anthropic Claude (Bedrock par) — "Messages API" body shape:
            #   anthropic_version REQUIRED hai, messages me content STRING ya blocks.
            return json.dumps({
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 256,                         # output cap = cost brake
                "messages": [{"role": "user", "content": prompt}],
            })
        # Amazon Nova / Titan family — content ek LIST of {"text": ...} blocks hota hai
        # (L47 ka "janky" format), aur inference config alag key me jaata hai.
        # (Nova: amazon.nova-micro-v1:0 / nova-lite-v1:0 / nova-pro-v1:0)
        return json.dumps({
            "messages": [{"role": "user", "content": [{"text": prompt}]}],
            "inferenceConfig": {"maxTokens": 256},
        })

    # --- response parser: family ke hisaab se text/tokens nikaalo -----------
    # OpenAI pydantic deta hai (response.choices[0].message.content). Bedrock raw
    # bytes deta hai -> json.loads -> nested dict. Yahi parsing 90% migration bugs
    # ka source hai (L47), isliye defensive .get() use karte hain.
    def _parse(self, payload):
        if self.model_id.startswith("anthropic."):
            # Anthropic: {"content":[{"type":"text","text":...}], "usage":{...}}
            text = ""
            for block in payload.get("content", []):
                if block.get("type") == "text":
                    text += block.get("text", "")
            usage = payload.get("usage", {})
            return text, usage.get("input_tokens", 0), usage.get("output_tokens", 0)
        # Nova/Titan: {"output":{"message":{"content":[{"text":...}]}}, "usage":{...}}
        # Note: yahi nested path L47 me dikha tha (converse ke saath); invoke_model bhi
        # similar nesting deta hai. Defensive: koi bhi level missing ho to "" mil jaaye.
        msg = payload.get("output", {}).get("message", {})
        blocks = msg.get("content", [])
        text = blocks[0].get("text", "") if blocks else ""
        usage = payload.get("usage", {})
        return text, usage.get("inputTokens", 0), usage.get("outputTokens", 0)

    def generate(self, prompt):
        # LAZY import — yahi line decide karti hai Bedrock chalega ya fallback.
        # boto3 missing => ImportError => call_llm() fallback par bhej dega.
        try:
            import boto3                       # noqa: F401  (lazy on purpose)
        except ImportError as e:
            # Saaf Hinglish: kya missing hai + kya hoga. RuntimeError raise karte hain
            # taaki call_llm() ek hi jagah pakad ke fallback par switch kare.
            raise RuntimeError(
                "boto3 missing => Bedrock use nahi ho sakta. AWS not configured "
                f"-> local fallback. (detail: {e})"
            )

        # boto3 client banao. region galat/creds missing ho sakte hain — koi network
        # call abhi nahi hoti (client construction lazy hai), error invoke par aayega.
        client = boto3.client("bedrock-runtime", region_name=self.region)

        body = self._build_body(prompt)
        try:
            # *** YAHI hai invoke_model ki ASLI SHAPE (vs OpenAI chat.completions) ***
            #   - modelId      : kaunsa model (e.g. amazon.nova-lite-v1:0)
            #   - body         : JSON STRING (provider-specific), bytes me jaata hai
            #   - contentType  : application/json
            resp = client.invoke_model(
                modelId=self.model_id,
                body=body,
                contentType="application/json",
                accept="application/json",
            )
            # Response ka "body" ek STREAM hai — .read() karke bytes, phir json.loads.
            # (OpenAI me yeh ready-made pydantic object hota; yahan manual parse.)
            payload = json.loads(resp["body"].read())
        except Exception as e:
            # Broad except JAAN-BOOJH KE: yahan boto3 ke BotoCoreError/ClientError
            # (creds missing, AccessDenied, region galat) + KeyError (response shape)
            # sab aate hain. call_llm() ise pakad ke fallback par bhej dega. (L47:
            # "locally chal raha tha, Lambda me break" wala AccessDeniedException
            # bhi yahin land karta — degrade karo, crash mat karo.)
            raise RuntimeError(f"Bedrock invoke fail: {e}")

        text, in_tok, out_tok = self._parse(payload)
        return ProviderResult(text=text, model=self.model_id,
                              prompt_tokens=in_tok, completion_tokens=out_tok)


# ---------------------------------------------------------------------------
# FallbackProvider — groq free get_client (local dev / no-AWS). (L47 abstraction)
# ---------------------------------------------------------------------------
# Jab Bedrock available nahi (no boto3 / no creds / invoke fail), hum yahan girte
# hain. Same `generate(prompt) -> ProviderResult` interface — caller ko farak nahi
# padta. Yeh OpenAI-compatible chat.completions use karta hai (OpenAI shape ka demo).
# ---------------------------------------------------------------------------
class FallbackProvider:
    def __init__(self, provider="groq"):
        self.provider = provider
        self.name = f"fallback:{provider}"
        _, self.model = get_client(provider)   # sirf model name ke liye (no network)

    def generate(self, prompt):
        # Agar key hi nahi, to LIVE call mat karo — graceful degrade. ProviderResult
        # me ek placeholder text + zero tokens, taaki shape dikhe aur exit 0 ho.
        key = os.getenv("GROQ_API_KEY")
        if not key:
            return ProviderResult(
                text="[SKIPPED live call: GROQ_API_KEY missing => local cost $0. "
                     "Key set karo to yahan real groq output aayega.]",
                model=self.model,
            )
        # *** OpenAI-style chat.completions.create (Bedrock invoke_model se ULTA) ***
        client, model = get_client(self.provider)
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],  # content = STRING
            max_tokens=256,                                    # output cap
        )
        usage = getattr(resp, "usage", None)
        return ProviderResult(
            text=resp.choices[0].message.content,              # pydantic path
            model=model,
            prompt_tokens=getattr(usage, "prompt_tokens", 0),
            completion_tokens=getattr(usage, "completion_tokens", 0),
        )


# ===========================================================================
# select_provider — CONFIG decide karta hai kaun chalega. (ek-line swap point)
# ===========================================================================
# Rule (L47/L48): BEDROCK_MODEL_ID env set hai => Bedrock try karo (prod path).
# Warna fallback groq (local path). Bedrock try kiya par boto3/creds missing ho to
# call_llm() runtime par fallback par switch kar dega (graceful). Yeh function sirf
# INTENT chunta hai; actual availability call ke time pata chalti hai.
def select_provider():
    model_id = os.getenv("BEDROCK_MODEL_ID")
    if model_id:
        return BedrockProvider(model_id)
    return FallbackProvider("groq")


# ===========================================================================
# call_llm — PUBLIC API. provider abstraction + CloudWatch-style structured log.
# ===========================================================================
# Yeh wahi ek function hai jo poora codebase use karta hai. Andar:
#   1) provider select (config se)
#   2) generate() try karo; Bedrock fail (no boto3/creds) ho to fallback par switch
#   3) HAR call ke aas-paas ek STRUCTURED JSON log line stdout par (CloudWatch food)
def _emit_log(record: dict):
    """STRUCTURED JSON log line stdout par. Lambda me stdout -> CloudWatch Logs.
    JSON hone se CloudWatch Logs Insights / metric filters in fields ko parse karke
    METRICS aur ALARMS bana lete hain (L49). Plain-text print se yeh nahi hota —
    isliye production me hamesha structured (JSON) logging."""
    # print() = stdout. ensure_ascii=False taaki koi unicode bhi readable rahe.
    print(json.dumps(record, ensure_ascii=False))


def call_llm(prompt: str) -> ProviderResult:
    """Prompt -> ProviderResult. Provider-agnostic + har call ek JSON log line emit.
    NA crash karta hai (Bedrock fail => fallback), NA hang."""
    provider = select_provider()

    # Bedrock chosen tha par available nahi (boto3/creds) — graceful switch.
    # Hum try karte hain; RuntimeError aaya to ek "fallback" note log karke fallback.
    if isinstance(provider, BedrockProvider):
        try:
            return _timed_generate(provider, prompt)
        except RuntimeError as e:
            # AWS not configured -> local fallback (saaf Hinglish, L48 ka concept).
            print(f"[INFO] {e}")
            print("[INFO] Bedrock unavailable => FallbackProvider (groq) par switch.")
            provider = FallbackProvider("groq")

    return _timed_generate(provider, prompt)


def _timed_generate(provider, prompt: str) -> ProviderResult:
    """generate() ko time karke ek CloudWatch-style structured log emit karta hai.
    Kisi bhi exception par ok=false log karke exception aage raise (BedrockProvider
    ke RuntimeError ko call_llm fallback ke liye pakadta hai)."""
    start = time.time()
    ok = False
    result = None
    try:
        result = provider.generate(prompt)
        ok = True
        return result
    finally:
        # finally => success ho ya fail, log HAMESHA emit hota hai (observability ka
        # asli point: failures bhi metric/alarm me dikhne chahiye, L49).
        latency_ms = int((time.time() - start) * 1000)
        record = {
            "event": "llm_call",                 # CloudWatch metric filter isi par match karega
            "provider": provider.name,
            "model": getattr(result, "model", None)
                     or getattr(provider, "model", None)
                     or getattr(provider, "model_id", None),
            "latency_ms": latency_ms,            # -> p50/p99 latency metric
            "prompt_tokens": getattr(result, "prompt_tokens", 0) if result else 0,
            "completion_tokens": getattr(result, "completion_tokens", 0) if result else 0,
            "ok": ok,                            # ok=false par ALARM (Errors > 0, L49)
        }
        _emit_log(record)


# ===========================================================================
# AWS LAMBDA HANDLER — REAL deployable. API-Gateway-proxy contract.
# ===========================================================================
# Yeh WAHI function hai jo deploy hota (L48). API Gateway "proxy integration" me:
#   event = {"httpMethod": "POST", "path": "/generate", "body": "<json string>", ...}
#   return = {"statusCode": int, "headers": {...}, "body": json.dumps(...)}
# body ek STRING hota hai (JSON nahi) — isliye json.loads/json.dumps khud karna padta.
def handler(event, context):
    """POST /generate -> call_llm(prompt). GET / -> health (model dikhata, L48 jaisa).
    Bina AWS/key ke bhi 200 deta hai (graceful) — kabhi unhandled 500 nahi."""
    method = (event or {}).get("httpMethod", "GET")
    path = (event or {}).get("path", "/")

    # CORS headers — frontend (CloudFront) se call ke liye (Week 1/2 ka CORS sabak).
    headers = {"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"}

    # --- GET / -> health check (L48: deploy ke baad smoke test, model confirm) ----
    if method == "GET" and path == "/":
        provider = select_provider()
        return {
            "statusCode": 200,
            "headers": headers,
            "body": json.dumps({
                "status": "ok",
                # konsa path live hai — Bedrock (prod) ya fallback (local). Yeh wahi
                # field hai jisse L48 me "model = Nova" confirm hota tha.
                "provider": provider.name,
                "model": getattr(provider, "model_id", None) or getattr(provider, "model", None),
                "bedrock_configured": bool(os.getenv("BEDROCK_MODEL_ID")),
            }),
        }

    # --- POST /generate -> asli LLM call (provider abstraction ke peeche) ---------
    if method == "POST" and path == "/generate":
        # body string ho sakta hai (API Gateway) ya already-dict (kuch test harness).
        raw = (event or {}).get("body") or "{}"
        try:
            data = raw if isinstance(raw, dict) else json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            # Garbage-in => 400, crash nahi (production input validation).
            return {"statusCode": 400, "headers": headers,
                    "body": json.dumps({"error": "invalid JSON body"})}

        prompt = (data or {}).get("prompt")
        if not prompt:
            return {"statusCode": 400, "headers": headers,
                    "body": json.dumps({"error": "missing 'prompt'"})}

        # call_llm graceful hai — Bedrock fail/key missing par bhi result deta hai.
        result = call_llm(prompt)
        return {
            "statusCode": 200,
            "headers": headers,
            "body": json.dumps({
                "output": result.text,
                "model": result.model,
                "usage": {
                    "prompt_tokens": result.prompt_tokens,
                    "completion_tokens": result.completion_tokens,
                    "total_tokens": result.prompt_tokens + result.completion_tokens,
                },
            }),
        }

    # --- Anything else -> 404 (clean contract, no crash) -------------------------
    return {"statusCode": 404, "headers": headers,
            "body": json.dumps({"error": f"no route for {method} {path}"})}


# ===========================================================================
# SELF-DEMO — `uv run <file>` (no args) yahan aata hai. No AWS / no key => exit 0.
# ===========================================================================
# Handler ko hand-built MOCK API-Gateway-proxy events se invoke karte hain — bilkul
# wahi jo deployed Lambda ko milta. Saath me OpenAI vs Bedrock SHAPE side-by-side
# print karte hain (teaching), aur structured log lines dikhte hain (CloudWatch food).
def _mock_event(method, path, body=None):
    """Ek minimal API-Gateway-proxy event dict — jaisa AWS bhejta hai."""
    return {"httpMethod": method, "path": path,
            "body": json.dumps(body) if body is not None else None}


def _print_api_shapes():
    """OpenAI vs Bedrock invoke_model ka request/response SHAPE side-by-side — yahi
    L47 ka core 'shapes alag hote hain' sabak hai. Sirf print, koi network call nahi."""
    print("=" * 72)
    print("API SHAPE COMPARE — OpenAI chat.completions  vs  Bedrock invoke_model")
    print("=" * 72)
    print("OpenAI (FallbackProvider):")
    print("  REQ : client.chat.completions.create(model=..,")
    print("            messages=[{'role':'user','content': '<string>'}])")
    print("  RES : response.choices[0].message.content   # pydantic object")
    print()
    print("Bedrock Nova/Titan (invoke_model):")
    print("  REQ : client.invoke_model(modelId='amazon.nova-lite-v1:0',")
    print("            body=json.dumps({")
    print("              'messages':[{'role':'user','content':[{'text':'<string>'}]}],")
    print("              'inferenceConfig':{'maxTokens':256}}))")
    print("  RES : json.loads(resp['body'].read())"
          "['output']['message']['content'][0]['text']")
    print()
    print("Bedrock Anthropic Claude (invoke_model):")
    print("  REQ : body=json.dumps({'anthropic_version':'bedrock-2023-05-31',")
    print("            'max_tokens':256,")
    print("            'messages':[{'role':'user','content':'<string>'}]})")
    print("  RES : json.loads(resp['body'].read())['content'][0]['text']")
    print()
    print("Bedrock Converse API (L47 me Ed ne yeh use ki — higher level, family-agnostic):")
    print("  REQ : client.converse(modelId=.., messages=[{'role':..,'content':[{'text':..}]}])")
    print("  RES : response['output']['message']['content'][0]['text']")
    print()
    print(">> WHY ABSTRACTION: in dono ke beech swap = call_llm() ke andar ek-line config")
    print("   change (BEDROCK_MODEL_ID env), na ki har caller ko chhedna. (L47)")
    print()


def run_self_demo():
    """Provider select dikhao, API shapes compare karo, mock events se handler invoke
    karo, structured logs + sample dikhao — phir exit 0 (chahe AWS/key ho ya na ho)."""
    print("\n" + "#" * 72)
    print("#  LAB 3 SELF-DEMO — Bedrock provider + observability  (no AWS/key bhi OK)")
    print("#" * 72 + "\n")

    # --- 1) Konsa provider select hua aur kyun -----------------------------
    provider = select_provider()
    print("=" * 72)
    print("PROVIDER SELECTION  (config-driven, ek-line swap)")
    print("=" * 72)
    print(f"BEDROCK_MODEL_ID set?  = {bool(os.getenv('BEDROCK_MODEL_ID'))}")
    print(f"selected provider      = {provider.name}")
    if isinstance(provider, FallbackProvider):
        print("note                   = BEDROCK_MODEL_ID nahi mila => FallbackProvider "
              "(groq free). Yeh local/no-AWS path hai.")
    else:
        print("note                   = BEDROCK_MODEL_ID mila => Bedrock try hoga; boto3/"
              "creds missing ho to call_llm() runtime par fallback par switch karega.")
    print()

    # --- 2) OpenAI vs Bedrock invoke_model shapes (teaching) ---------------
    _print_api_shapes()

    # --- 3) GET / health (mock API-Gateway event) --------------------------
    print("=" * 72)
    print("HANDLER: GET /   (health — L48 smoke test, model confirm)")
    print("=" * 72)
    resp = handler(_mock_event("GET", "/"), None)
    print(f"statusCode = {resp['statusCode']}")
    print("body       = " + json.dumps(json.loads(resp["body"]), indent=2, ensure_ascii=False))
    print()

    # --- 4) POST /generate (mock event) — yahan structured log line aayega -
    print("=" * 72)
    print("HANDLER: POST /generate   (provider abstraction + CloudWatch-style JSON log)")
    print("=" * 72)
    sample_body = {"prompt": "In one short sentence, what is Amazon Bedrock?"}
    print(f"REQUEST event body = {sample_body}")
    print("\n--- structured log line(s) below = exactly what Lambda writes to "
          "CloudWatch Logs ---")
    resp = handler(_mock_event("POST", "/generate", sample_body), None)
    print("--- end logs ---\n")
    print(f"statusCode = {resp['statusCode']}")
    print("RESPONSE   = " + json.dumps(json.loads(resp["body"]), indent=2, ensure_ascii=False))
    print()

    # --- 5) Observability explainer ----------------------------------------
    print("=" * 72)
    print("OBSERVABILITY  (L49: structured logs -> metrics -> alarms)")
    print("=" * 72)
    print("Upar wali JSON log line ({event:'llm_call', provider, model, latency_ms,")
    print("prompt_tokens, completion_tokens, ok}) Lambda ke stdout se CloudWatch Logs")
    print("me jaati hai. JSON hone se CloudWatch:")
    print("  - metric filter se latency_ms / *_tokens ko METRIC bana leta hai (L49)")
    print("  - ok=false count par ALARM laga sakte ho (Errors > 0)")
    print("  - *_tokens par alarm = cost-runaway ka sabse sasta detector")
    print("Plain-text print se yeh kuch nahi hota — isliye STRUCTURED (JSON) logging.")
    print()

    print("#" * 72)
    print("#  LAB 3 complete. call_llm() = provider-agnostic; Bedrock<->groq ek-line swap;")
    print("#  har call ek JSON log line = CloudWatch metrics/alarms ka raw material.")
    print("#" * 72 + "\n")

    raise SystemExit(0)


# ===========================================================================
# MAIN — default self-demo; --one => sirf ek call_llm + structured log line.
# ===========================================================================
if __name__ == "__main__":
    if "--one" in sys.argv:
        # Minimal: ek call_llm, dekho kaun select hua + ek JSON log line.
        print(f"[selected provider] {select_provider().name}")
        r = call_llm("Say hi in 3 words.")
        print(f"[result text] {r.text}")
        raise SystemExit(0)
    else:
        run_self_demo()
