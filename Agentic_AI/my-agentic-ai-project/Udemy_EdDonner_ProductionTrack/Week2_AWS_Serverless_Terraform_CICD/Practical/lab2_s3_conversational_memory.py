"""
LAB 2 — S3 conversational memory for STATELESS Lambda
=====================================================
Title: Lambda stateless hai (har invocation ek fresh, throwaway container) — isliye
       chat history ko BAHAR (external storage) rakhna padta hai. Yahan ek MemoryStore
       banate hain ek PLUGGABLE backend ke saath: local file (offline) ya S3 (boto3),
       aur ek REAL deployable Lambda `handler` jo poora "stateless + external memory"
       loop dikhata hai.

KYA SEEKHENGE (what concepts):
- WHY serverless ko EXTERNAL state chahiye: Lambda har request par fresh container me
  chal sakta hai (ya purana kill ho chuka hota hai). Process memory / local disk par
  jo kuch rakha wo agle invocation me GUM ho sakta hai. Isliye "session state" hamesha
  bahar — S3 / DynamoDB / Redis — me rehna chahiye. (L38, L39)
- LOCAL -> S3 MIGRATION STORY: Day 1 me memory ek local `memory/<uuid>.json` thi; Day 2
  par wahi exact pattern S3 object (`s3://$S3_BUCKET/sessions/<id>.json`) ban jaata hai.
  Interface SAME rehta hai (load_history / save_message), sirf backend swap hota hai —
  classic repository/adapter pattern. (L40)
- S3 OBJECT-PER-SESSION pattern: har session = ek JSON object, key = `sessions/<id>.json`.
  S3 ek flat key-value object store hai (file-system "jaisa" dikhta hai par hai nahi). (L40, L42)
- API GATEWAY + CLOUDFRONT + CORS ka note: browser CloudFront se static frontend leta hai,
  aur `fetch()` se API Gateway -> Lambda ko hit karta hai. Do alag origins => CORS allow
  headers chahiye, warna browser block kar deta hai. (L43, L44, L45)
- REAL Lambda handler(event, context): API-Gateway-proxy contract padhta hai
  (httpMethod / path / body) aur {statusCode, headers, body} return karta hai — wahi
  handler jo deploy hota hai. Self-demo isi handler ko mock events se invoke karta hai.

KAISE CHALANA (how to run) — CWD = repo root:
    # Default: built-in self-demo (LOCAL backend, fully offline, no AWS, no key) => EXIT 0
    uv run Udemy_EdDonner_ProductionTrack/Week2_AWS_Serverless_Terraform_CICD/Practical/lab2_s3_conversational_memory.py

Setup (optional, sab OPTIONAL — bina inke bhi self-demo chalta hai):
- S3_BUCKET set + boto3 installed + AWS creds available  => S3Backend use hoga.
  inme se kuch bhi missing? => clear Hinglish note print karke LocalFileBackend par
  auto-fall-back. (NEVER crash, NEVER hang.)
- GROQ_API_KEY set => handler ka /chat LIVE LLM reply dega; warna ek deterministic
  "echo" reply de ke shape dikha deta hai (gracefully degrade), phir bhi EXIT 0.

LECTURE MAPPING: Ed Donner "AI Engineer Production Track", Week 2 · Day 1 -> Day 2.
  L38 = Conversational memory (stateless app -> stateful via per-session JSON; client
        session_id rakhta hai, server stateless rehta hai => horizontal scaling possible).
  L39 = Production AI agents on Lambda + S3 (serverless architecture).
  L40 = Migrate chat local -> S3 + Lambda (USE_S3 toggle; get_object/put_object;
        Mangum se FastAPI ko Lambda handler banana).
  L42 = Lambda + S3 memory config (timeout, S3 bucket globally-unique naam, execution role).
  L43 = S3 buckets + API Gateway (routes incl. POST /chat, OPTIONS preflight, CORS).
  L44 = CloudFront (static frontend S3 par; browser fetch ab real API Gateway endpoint par).
  L45 = Live test + CORS origin ko `*` se specific CloudFront URL par restrict.

COST: Is lab ko LOCALLY chalana = $0. Default backend local filesystem (`./_s3_memory/`)
  hai => koi AWS, koi network, koi key nahi. Real AWS deploy (runbook me) ka cost:
  S3 storage ~$0.023/GB-month (conversation JSONs KB me => effectively free), S3
  requests ~$0.005 per 1000 PUT / $0.0004 per 1000 GET (idle par $0), Lambda free-tier
  1M requests + 400k GB-sec/month (chhoti app => $0). API Gateway HTTP API $1.00 per
  million requests. CloudFront free-tier 1 TB/month out. Net: Ed ka pura course estimate
  ~$5-$10, zyaadatar free-tier ke andar — assuming end me resources cleanup kar do (L63).
"""

import json
import os
import sys
import uuid
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

# .env load. override=True => agar shell me purani value set hai to .env wali jeet
# jayegi (Ed Donner isi convention ko follow karta hai).
load_dotenv(override=True)


# ---------------------------------------------------------------------------
# get_client: provider ke hisaab se (client, model_name) return karta hai.
# Groq aur Gemini OpenAI-compatible hain — bas base_url alag. Isiliye ek hi
# `openai` library teeno providers ko call kar leti hai. File ko SELF-CONTAINED
# rakhne ke liye helper yahin inline rakha hai (Week-1 convention).
# ---------------------------------------------------------------------------
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


# Default provider ek hi jagah define — taaki handler consistent rahe. Production me
# yeh config (env var) se aata; abhi clarity ke liye hardcoded.
PROVIDER = "groq"


# ===========================================================================
# ###############  WHY SERVERLESS NEEDS EXTERNAL STATE  #####################
# ===========================================================================
# Yeh block sirf comment hai par is poore lab ka DIL hai (L38/L39 ka core lesson).
#
# 1) LAMBDA STATELESS HAI. Ek normal long-running server (uvicorn) process memory me
#    cheezein rakh sakta hai kyunki wahi process baar-baar requests serve karta hai.
#    Lambda ALAG hai: har request par AWS ek "execution environment" (chhota container)
#    use karta hai jo:
#       - cold start par BILKUL fresh hota hai (sab kuch khaali),
#       - idle hone par AWS isse KILL kar deta hai,
#       - aur 2 concurrent requests do ALAG containers me chal sakti hain.
#    Matlab tum process-level dict (e.g. `SESSIONS = {}`) par BHAROSA nahi kar sakte —
#    wo agle invocation me gayab ho sakta hai, ya kisi aur container me hoga hi nahi.
#
# 2) HENCE: SESSION STATE BAHAR. Chat history ko ek EXTERNAL durable store me rakho:
#       - S3            -> object-per-session JSON (yeh lab; Ed ka course choice)
#       - DynamoDB      -> key-value, low-latency, auto-scaling
#       - Redis/Elasticache -> fast, ephemeral-friendly
#    Server PURELY stateless ho jaata hai => koi bhi container koi bhi request handle
#    kar sakta hai => HORIZONTAL SCALING free milti hai. (L38 ka backend-dev note.)
#
# 3) CLIENT SESSION_ID HOLD KARTA HAI. State bahar hai, par "kaun-si conversation" yeh
#    client batata hai: request me ek `session_id` aata hai (na ho to server naya UUID
#    banata hai aur wapas deta hai). Yeh classic "stateless HTTP + external session
#    store" pattern hai jo har backend dev jaanta hai.
#
# 4) LOCAL -> S3 MIGRATION (L40). Day 1 me yeh memory `memory/<uuid>.json` LOCAL thi.
#    Day 2 par wahi exact pattern S3 object ban gaya: `open()` ki jagah
#    `s3.get_object()` / `s3.put_object()`. Interface (load/save) same, backend swap.
#    Isiliye neeche MemoryStore ek PLUGGABLE backend leta hai — yeh repository/adapter
#    pattern hai (12-factor "backing services": storage env-flag ke peeche).
# ===========================================================================


# ===========================================================================
# BACKEND 1 — LocalFileBackend (default, fully offline)
# ===========================================================================
# Day 1 wala behaviour: har session ek local JSON file. Yahan ek dir `./_s3_memory/`
# use karte hain jisme keys `sessions/<id>.json` ke roop me rehti hain — bilkul wahi
# layout jo S3 me hoga, taaki migration "mental model" 1:1 match kare.
class LocalFileBackend:
    """Per-session JSON ko local `_s3_memory/` dir me rakhta hai. No network, no AWS.

    Yeh S3Backend ke saath SAME interface implement karta hai: get(key) -> bytes|None,
    put(key, body_bytes). Isiliye MemoryStore inme se kisi ek ko bhi 'plug' kar sakta hai.
    """

    def __init__(self, root: str = "_s3_memory"):
        # root dir banao agar nahi hai. parents=True => nested bhi ban jaye; exist_ok
        # => dobara chalane par crash na ho.
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        # key "sessions/<id>.json" hai — isme '/' ho sakta hai, isliye local par bhi
        # nested folder banate hain taaki S3 ke "folder-jaisa" layout se match kare.
        p = self.root / key
        p.parent.mkdir(parents=True, exist_ok=True)
        return p

    def get(self, key: str):
        """Object bytes return karo, ya None agar 'NoSuchKey' (file hi nahi)."""
        p = self._path(key)
        if p.exists():
            return p.read_bytes()
        return None  # S3 ke NoSuchKey ke equivalent — nayi conversation

    def put(self, key: str, body: bytes) -> None:
        """Object bytes likho (overwrite). S3 put_object ka local equivalent."""
        self._path(key).write_bytes(body)

    def describe(self) -> str:
        # Self-demo me dikhane ke liye: yeh backend actually kahan likh raha hai.
        return f"LocalFileBackend(dir={self.root.resolve()})"


# ===========================================================================
# BACKEND 2 — S3Backend (boto3, LAZY import; only when fully available)
# ===========================================================================
# CRITICAL: boto3 is environment me INSTALLED NAHI hai aur AWS creds bhi NAHI hain.
# Isliye boto3 ko sirf is class ke andar LAZILY import karte hain (try/except) —
# module top-level par import karte to bina boto3 wale env me poori file hi crash
# kar jaati. MemoryStore neeche decide karta hai ki yeh backend banana bhi hai ya nahi.
class S3Backend:
    """boto3 se s3://<bucket>/<key> par get/put. Constructor me boto3 ko LAZY import
    karta hai; ImportError par ya creds missing par MemoryStore isse use hi nahi karega
    (LocalFileBackend par fall back hota hai)."""

    def __init__(self, bucket: str):
        self.bucket = bucket
        # LAZY import: agar boto3 nahi hai to yeh ImportError MemoryStore tak propagate
        # hoga, jise wo catch karke local fallback kar dega. Top-level import NAHI.
        import boto3  # noqa: WPS433 (intentional local import)
        # NOTE: client banana sasta hai (network call nahi), par GET/PUT par creds chahiye.
        self._s3 = boto3.client("s3")

    def get(self, key: str):
        """S3 se object laao. NoSuchKey => None (nayi conversation). Baaki errors raise."""
        try:
            resp = self._s3.get_object(Bucket=self.bucket, Key=key)
            return resp["Body"].read()
        # boto3 client ke exceptions runtime me attach hote hain; isliye class name se
        # match karte hain taaki bina boto3-types ke bhi kaam kare.
        except self._s3.exceptions.NoSuchKey:
            return None

    def put(self, key: str, body: bytes) -> None:
        """S3 me object likho. Yeh wahi put_object hai jo L40 me dekha."""
        self._s3.put_object(Bucket=self.bucket, Key=key, Body=body)

    def describe(self) -> str:
        return f"S3Backend(bucket={self.bucket})"


# ===========================================================================
# MemoryStore — pluggable backend ke upar conversation API
# ===========================================================================
# Yahi wo "session store abstraction" hai. Backend choose karne ki LOGIC select_backend()
# me hai (factory). MemoryStore khud backend-agnostic hai: bas get/put bytes janta hai.
def _key_for(session_id: str) -> str:
    # S3 OBJECT-PER-SESSION pattern: ek prefix `sessions/` + `<id>.json`.
    # S3 me "folder" sirf naam ka illusion hai (key me '/' bas ek character hai), par
    # yeh prefix listing/cleanup/lifecycle-rules (TTL) ke liye useful hota hai.
    return f"sessions/{session_id}.json"


def select_backend():
    """Decide karo kaun-sa backend use karna hai, aur kyun — ek (backend, note) tuple.

    Rule (task spec): S3Backend SIRF tab jab S3_BUCKET env set HO *AND* boto3 + creds
    available hon. Inme se kuch bhi missing => LocalFileBackend par auto-fall-back, ek
    clear Hinglish note ke saath. NEVER crash, NEVER hang.
    """
    bucket = os.getenv("S3_BUCKET")

    # (a) Bucket hi configured nahi => seedha local. Yeh default/offline path hai.
    if not bucket:
        return (
            LocalFileBackend(),
            "S3_BUCKET env set nahi => LOCAL backend (offline). Yeh Day-1 wala "
            "`memory/<uuid>.json` pattern hai; deploy par S3_BUCKET set hoga (L40/L42).",
        )

    # (b) Bucket set hai, par AWS creds available hain? Hum boto3 ko thaka kar bina
    #     network HANG kiye check karte hain. Sabse pratical signal: standard AWS env
    #     vars. Inke bina S3Backend ka get/put runtime par AccessDenied/credential-error
    #     dega (ya credential-chain network par hang kar sakta hai) — isliye PEHLE check.
    has_creds = bool(
        os.getenv("AWS_ACCESS_KEY_ID")
        or os.getenv("AWS_PROFILE")
        # ECS/Lambda role-based creds: container credentials endpoint set hota hai.
        or os.getenv("AWS_CONTAINER_CREDENTIALS_RELATIVE_URI")
    )
    if not has_creds:
        return (
            LocalFileBackend(),
            f"S3_BUCKET={bucket} mila par AWS creds nahi (AWS_ACCESS_KEY_ID/AWS_PROFILE "
            "/role) => LOCAL fallback. AWS not configured -> local fallback.",
        )

    # (c) Bucket + creds dono hain => S3Backend try karo. boto3 missing ho sakta hai
    #     (jaise is repo me) => ImportError catch karke local fallback.
    try:
        return (
            S3Backend(bucket),
            f"S3_BUCKET={bucket} + boto3 + creds available => S3Backend "
            "(s3://{bucket}/sessions/<id>.json).".replace("{bucket}", bucket),
        )
    except ImportError:
        return (
            LocalFileBackend(),
            "boto3 INSTALLED nahi (pip/uv add boto3) => LOCAL fallback. "
            "AWS not configured -> local fallback.",
        )
    except Exception as exc:  # noqa: BLE001 — koi bhi boto3 init error => safe fallback
        # NEVER crash: kisi bhi unexpected boto3/creds error par bhi local par jaao.
        return (
            LocalFileBackend(),
            f"S3Backend init fail ({type(exc).__name__}) => LOCAL fallback. "
            "AWS not configured -> local fallback.",
        )


class MemoryStore:
    """Conversation memory API. Backend pluggable (LocalFileBackend ya S3Backend).

    Public API (jo handler use karta hai):
      - save_message(session_id, role, content)  -> ek turn append karke persist
      - load_history(session_id) -> list[dict]    -> poori prior history wapas
    Dono backend-agnostic hain: andar bas JSON bytes get/put hota hai.
    """

    def __init__(self, backend=None):
        # Backend inject kar sakte ho (testing/demo me handy); na do to select_backend().
        if backend is None:
            backend, note = select_backend()
            self._note = note
        else:
            self._note = f"explicit backend => {backend.describe()}"
        self.backend = backend

    @property
    def note(self) -> str:
        # select_backend ne jo decide kiya (S3 vs local + kyun) — UI/log ke liye.
        return self._note

    def load_history(self, session_id: str) -> list:
        """Is session ki poori prior conversation (list of {role, content}). Nayi ho to []."""
        raw = self.backend.get(_key_for(session_id))
        if raw is None:
            return []  # nayi conversation — koi object/file nahi mila
        # Defensive: corrupt/empty JSON par crash mat karo — fresh history se start.
        try:
            data = json.loads(raw)
            return data if isinstance(data, list) else []
        except (json.JSONDecodeError, ValueError):
            return []

    def save_message(self, session_id: str, role: str, content: str) -> list:
        """Ek turn ({role, content}) load->append->persist karta hai. Updated history return.

        NOTE: yeh read-modify-write hai. Flat-file/S3 par concurrent writes RACE kar
        sakte hain (do parallel requests ek doosre ko overwrite). Learning ke liye theek;
        production me DynamoDB conditional-writes ya optimistic-locking chahiye (L38 note).
        """
        history = self.load_history(session_id)
        history.append({"role": role, "content": content})
        # JSON ko bytes me serialize karke backend ko de do — dono backends bytes lete hain.
        self.backend.put(_key_for(session_id), json.dumps(history).encode("utf-8"))
        return history


# ===========================================================================
# LLM reply — graceful degrade (key na ho to deterministic echo)
# ===========================================================================
def generate_reply(history: list) -> tuple[str, str]:
    """(reply_text, mode). History (system+turns) ko LLM ko bhejta hai. GROQ_API_KEY na
    ho to LIVE call skip karke ek deterministic 'echo' reply deta hai — shape same rehti
    hai, crash/hang nahi (graceful degrade). Returns (reply, "live"|"degraded")."""
    last_user = next((m["content"] for m in reversed(history) if m["role"] == "user"), "")

    if not os.getenv("GROQ_API_KEY"):
        # DEGRADED: bina key ke bhi loop chalna chahiye taaki memory-persistence demo ho.
        # Deterministic reply => self-demo reproducible rehta hai.
        return (f"(degraded, no GROQ_API_KEY) Echo: tumne kaha -> '{last_user}'", "degraded")

    # LIVE: system prompt + prior history + latest message — wahi L38 wala messages shape.
    client, model = get_client(PROVIDER)
    messages = [{"role": "system", "content": "You are a concise, friendly assistant."}]
    messages.extend(history)
    try:
        resp = client.chat.completions.create(model=model, messages=messages, max_tokens=128)
        return (resp.choices[0].message.content, "live")
    except Exception as exc:  # noqa: BLE001 — network/auth fail par bhi handler 200 de
        # NEVER crash the request: live call fail hua to degraded message do.
        return (f"(live call failed: {type(exc).__name__}) Echo: '{last_user}'", "degraded")


# ===========================================================================
# REAL DEPLOYABLE LAMBDA HANDLER — API-Gateway-proxy contract
# ===========================================================================
# Yeh WAHI handler hai jo AWS Lambda par deploy hota hai. (Course me Mangum FastAPI ko
# wrap karke yeh banata hai; yahan hum raw handler likh rahe hain taaki contract saaf
# dikhe — koi web framework dependency nahi.)
#
# API Gateway "proxy integration" event Lambda ko aise deta hai:
#   event["httpMethod"]  -> "POST" / "GET" / "OPTIONS"   (HTTP API v2 me requestContext.http.method)
#   event["path"]        -> "/chat"
#   event["body"]        -> JSON string (POST body), ya None
# Aur Lambda ko aisa return karna hota hai:
#   {"statusCode": int, "headers": {...}, "body": json.dumps(...)}
# API Gateway is dict ko real HTTP response me convert kar deta hai.
def _cors_headers() -> dict:
    """CORS allow headers. L43/L45: browser (CloudFront origin) -> API Gateway (alag
    origin) cross-origin call karta hai, isliye server ko explicitly allow karna padta
    hai warna browser block kar dega. `CORS_ORIGINS` env se origin aata hai (Day-2 ke
    end me ise `*` se specific CloudFront URL par restrict karte hain — L45)."""
    origin = os.getenv("CORS_ORIGINS", "*")
    return {
        "Content-Type": "application/json",
        "Access-Control-Allow-Origin": origin,
        "Access-Control-Allow-Headers": "*",
        "Access-Control-Allow-Methods": "*",
    }


def _response(status: int, body: dict) -> dict:
    """API-Gateway-proxy shape banao: statusCode + headers + JSON-string body."""
    return {"statusCode": status, "headers": _cors_headers(), "body": json.dumps(body)}


def handler(event, context):
    """AWS Lambda + API-Gateway-proxy entrypoint. POST /chat ka poora stateless loop:
    history load -> user msg append -> (LLM) reply -> reply save -> JSON return.
    Bina key/AWS ke bhi gracefully chalta hai (degraded reply, local memory)."""
    event = event or {}

    # --- method/path nikaalo (REST API v1 aur HTTP API v2 dono shapes support) ---
    method = (
        event.get("httpMethod")  # REST API (v1)
        or event.get("requestContext", {}).get("http", {}).get("method")  # HTTP API (v2)
        or "GET"
    )
    path = (
        event.get("path")
        or event.get("rawPath")
        or event.get("requestContext", {}).get("http", {}).get("path")
        or "/"
    )

    # --- OPTIONS preflight (L43): browser CORS negotiation. Empty 200 + CORS headers. ---
    # Ise handle na karo to browser se chat kaam hi nahi karega.
    if method == "OPTIONS":
        return _response(200, {"ok": True})

    # --- GET /health (L42/L43): no key, no AWS needed. Liveness + config visibility. ---
    if method == "GET" and path.rstrip("/") in ("", "/health"):
        store = MemoryStore()
        return _response(200, {
            "status": "healthy",
            "backend": store.backend.describe(),
            "use_s3": store.backend.__class__.__name__ == "S3Backend",
            "llm_configured": bool(os.getenv("GROQ_API_KEY")),
        })

    # --- POST /chat (L43: "the one we really care most about") ------------------
    if method == "POST" and path.rstrip("/") == "/chat":
        # body ek JSON STRING hai (API Gateway proxy). Parse karo, garbage par 400 do.
        try:
            payload = json.loads(event.get("body") or "{}")
        except (json.JSONDecodeError, ValueError):
            return _response(400, {"error": "body must be valid JSON"})

        message = payload.get("message")
        if not message:
            return _response(400, {"error": "field 'message' required"})

        # session_id client se aata hai; na ho to naya UUID (L38). Client ise hold karega.
        session_id = payload.get("session_id") or str(uuid.uuid4())

        # ---- POORA STATELESS-WITH-EXTERNAL-MEMORY LOOP ----
        store = MemoryStore()                      # fresh store (jaise har Lambda invocation)
        store.save_message(session_id, "user", message)   # 1) user msg persist
        history = store.load_history(session_id)           # 2) poori history (external se)
        reply, mode = generate_reply(history)              # 3) LLM (ya degraded echo)
        store.save_message(session_id, "assistant", reply) # 4) reply persist

        return _response(200, {
            "session_id": session_id,   # client ise yaad rakhega (stateless server)
            "reply": reply,
            "mode": mode,               # "live" ya "degraded"
            "turns": len(history) + 1,  # +1 = abhi-save kiya assistant turn
        })

    # --- koi aur route => 404 (proxy ke ANY/{proxy+} catch-all me yahi aata) ---
    return _response(404, {"error": f"no route for {method} {path}"})


# ===========================================================================
# SELF-DEMO — `uv run <file>` (no args) yahan aata hai. No AWS, no key => EXIT 0.
# ===========================================================================
def _mock_event(method: str, path: str, body: dict | None = None) -> dict:
    """API-Gateway-proxy event dict hand-build karo (jaisa API Gateway bhejta hai)."""
    return {
        "httpMethod": method,
        "path": path,
        "headers": {"content-type": "application/json"},
        "body": json.dumps(body) if body is not None else None,
        # HTTP API v2 fields bhi daal dete hain taaki handler ka v2-path bhi exercise ho.
        "rawPath": path,
        "requestContext": {"http": {"method": method, "path": path}},
    }


def _pp(label: str, resp: dict) -> None:
    """Lambda response ko padhne-layak print karo (body JSON-string ko bhi expand)."""
    print(f"\n>>> {label}")
    print(f"    statusCode = {resp['statusCode']}")
    print(f"    headers.Access-Control-Allow-Origin = "
          f"{resp['headers'].get('Access-Control-Allow-Origin')}")
    print("    body       = " + json.dumps(json.loads(resp["body"]), indent=2, ensure_ascii=False)
          .replace("\n", "\n    "))


def run_self_demo() -> None:
    """Local backend par do turns ek session par chalao, phir ek 'fresh' store me reload
    karke prove karo ki memory PERSIST hui (yeh stateless-Lambda ka asli point hai)."""
    print("\n" + "#" * 74)
    print("#  LAB 2 SELF-DEMO — S3 conversational memory for stateless Lambda")
    print("#  (LOCAL backend, fully offline — no AWS, no boto3, no API key needed)")
    print("#" * 74)

    # Konsa backend chuna gaya aur KYUN — yeh fallback story explicitly dikhata hai.
    store = MemoryStore()
    print(f"\nBackend decision: {store.note}")
    print(f"Active backend  : {store.backend.describe()}")

    # ---- 1) /health (no key, no AWS) ----
    print("\n" + "=" * 74)
    print("STEP 1 — GET /health  (mock API-Gateway event; no key/AWS needed)")
    print("=" * 74)
    _pp("handler(GET /health)", handler(_mock_event("GET", "/health"), None))

    # ---- 2) OPTIONS preflight (CORS) ----
    print("\n" + "=" * 74)
    print("STEP 2 — OPTIONS /chat  (CORS preflight — L43; browser ise pehle bhejta hai)")
    print("=" * 74)
    _pp("handler(OPTIONS /chat)", handler(_mock_event("OPTIONS", "/chat"), None))

    # ---- 3) POST /chat turn 1 (naya session) ----
    print("\n" + "=" * 74)
    print("STEP 3 — POST /chat turn 1  (naya session; server UUID banata hai)")
    print("=" * 74)
    r1 = handler(_mock_event("POST", "/chat", {"message": "Hi there. My name's Alex."}), None)
    _pp("handler(POST /chat) #1", r1)
    session_id = json.loads(r1["body"])["session_id"]
    print(f"\n    [client ne session_id yaad rakha] => {session_id}")

    # ---- 4) POST /chat turn 2 (same session — memory test) ----
    print("\n" + "=" * 74)
    print("STEP 4 — POST /chat turn 2  (SAME session_id => prior history load hoti hai)")
    print("=" * 74)
    r2 = handler(_mock_event("POST", "/chat",
                             {"message": "What's my name again?", "session_id": session_id}), None)
    _pp("handler(POST /chat) #2", r2)

    # ---- 5) PROOF: fresh store (jaise naya Lambda container) reload kare history ----
    print("\n" + "=" * 74)
    print("STEP 5 — PERSISTENCE PROOF — ek FRESH MemoryStore (naya Lambda container jaisa)")
    print("         banao aur usse SAME session_id ki history reload karo. Agar memory")
    print("         sach me EXTERNAL hai, to do turns (4 messages) yahan bhi dikhne chahiye.")
    print("=" * 74)
    fresh_store = MemoryStore()  # bilkul naya object — process-memory me kuch shared nahi
    reloaded = fresh_store.load_history(session_id)
    print(f"\n    fresh_store.load_history('{session_id[:8]}...') => {len(reloaded)} messages:")
    for i, m in enumerate(reloaded, 1):
        print(f"      {i}. [{m['role']:9}] {m['content']}")

    # Hard assertion-style check (par crash nahi karte — sirf clear PASS/FAIL print).
    ok = len(reloaded) == 4 and reloaded[0]["role"] == "user"
    print(f"\n    PERSISTENCE: {'PASS ✅' if ok else 'CHECK ❌'} "
          "(memory bahar thi, isliye fresh container me bhi mili — yahi stateless+S3 point)")

    # ---- 6) where it lives + AWS deploy note ----
    print("\n" + "=" * 74)
    print("STEP 6 — Memory kahan likhi? + AWS deploy story")
    print("=" * 74)
    print(f"    LOCAL : {Path('_s3_memory').resolve()}/sessions/{session_id}.json")
    print("    S3    : s3://$S3_BUCKET/sessions/<id>.json  (S3_BUCKET set + boto3 + creds => S3Backend)")
    print("    FLOW  : Browser -> CloudFront (static frontend, S3) ; "
          "Browser fetch() -> API Gateway -> Lambda(handler) -> S3 memory")
    print("    CORS  : CloudFront origin != API Gateway origin => OPTIONS preflight + "
          "Access-Control-Allow-Origin (L45: prod me `*` ko CloudFront URL par restrict)")

    print("\n" + "#" * 74)
    print("#  LAB 2 complete. Pattern: stateless handler + EXTERNAL per-session memory.")
    print("#  Local <-> S3 backend swap = same interface (repository/adapter pattern).")
    print("#" * 74 + "\n")

    # Hamesha clean exit 0 — chaahe key/AWS ho ya na ho.
    raise SystemExit(0)


# ===========================================================================
# MAIN
# ===========================================================================
if __name__ == "__main__":
    # is lab me sirf ek mode hai: self-demo (Lambda handler ko mock events se invoke).
    # (sys import upar hai taaki future flags add karna easy ho.)
    _ = sys
    run_self_demo()
