"""
LAB 6 — Scheduled agent workflows with EventBridge (managed cron -> Lambda)
===========================================================================
Title: Ek RECURRING research/ingest job ko AWS EventBridge SCHEDULE se autonomous
       banao. EventBridge har N minute/ghante "wake up" karke ek Lambda ko fire
       karta hai; us Lambda ka `handler(event, context)` ek chhota job chalata hai
       (run log karta, research/ingest pipeline ko "would-call" karta) aur ek
       summary return karta hai. Yeh wahi "Alex Scheduler" pattern hai (L87) —
       managed cron, koi always-on box nahi.

KYA SEEKHENGE (what concepts):
- CRON vs RATE schedule expressions: EventBridge do tareeke se "kab chalana hai"
  bolne deta hai —
    * rate(2 hours)            -> simple fixed interval ("har 2 ghante")
    * cron(0 9 * * ? *)        -> exact wall-clock ("har din 09:00 UTC")
  Hum dono parse/explain karenge aur ek chhota validator dikhayenge.
- PUSH vs PULL scheduling: traditional cron = PULL (ek always-on box har minute
  jaagke "kuch chalana hai?" check karta — server tumhara, patch tumhare, idle bhi
  paisa). EventBridge = PUSH (AWS ke paas managed scheduler hai, time aane par WO
  tumhare Lambda ko INVOKE/push karta — koi server nahi, idle = $0). Yeh shift
  serverless cron ka asli faayda hai (L87 "managed cron, no crontab box").
- IDEMPOTENCY for scheduled jobs: scheduler "at-least-once" deliver kar sakta hai
  (retry, clock-skew, overlap) — yaani ek hi schedule tick par handler do baar
  chal sakta hai. Isliye job ko IDEMPOTENT banao: har run ko ek deterministic
  RUN-KEY (schedule time se derive) do, aur "already processed?" check karke
  duplicate kaam skip karo. Warna har retry pe research dobara chalega = double
  cost + duplicate vectors. Hum ek in-memory idempotency store se yeh dikhayenge.
- EVENTBRIDGE -> LAMBDA EVENT SHAPE: scheduled invocation API-Gateway-proxy se
  BILKUL alag dict hai. Hum exact shape match karenge:
    event = {
      "version": "0", "id": "<uuid>", "detail-type": "Scheduled Event",
      "source": "aws.events", "account": "...", "time": "2026-06-13T09:00:00Z",
      "region": "us-east-1",
      "resources": ["arn:aws:events:...:rule/alex-research-schedule"],
      "detail": {}                      # scheduled events me detail aksar khaali
    }
  Handler is shape ko pehchaan ke (source=="aws.events", detail-type=="Scheduled
  Event") job chalata hai. Galat/unknown event aaye to clean skip — crash nahi.
- LAZY boto3 + GRACEFUL DEGRADE: is env me boto3, AWS creds, koi LLM key — kuch
  nahi. Isliye "would-call research pipeline" wala AWS code-path boto3 ko sirf
  try/except ke andar LAZILY import karta hai; missing ho to saaf Hinglish note
  ("boto3/AWS not available -> local fallback") print karke ek LOCAL mock run
  chalata hai. NA crash, NA hang, NA network/model download.
- DEPLOY (Terraform): saath wali deploy/eventbridge_schedule.tf me yahi wiring HCL
  me hai — aws_cloudwatch_event_rule (schedule_expression) -> event_target (->
  yeh Lambda) -> aws_lambda_permission (events ko invoke karne ki ijaazat).

KAISE CHALANA (how to run) — CWD = repo root:
    # Default: self-demo (no AWS / no boto3 / no key bhi chalega, EXIT 0)
    uv run Udemy_EdDonner_ProductionTrack/Week3_MultiCloud_SageMaker_Pipelines/Practical/lab6_eventbridge_scheduled_agent.py

    # Sirf ek scheduled tick simulate karke summary dekhni ho:
    uv run Udemy_EdDonner_ProductionTrack/Week3_MultiCloud_SageMaker_Pipelines/Practical/lab6_eventbridge_scheduled_agent.py --one

LECTURE MAPPING: Ed Donner "AI Engineer Production Track", Week 3 · Day 5.
  L87 = Automating AI Agent Workflows with AWS EventBridge Scheduling
        (EventBridge Scheduler = managed cron; rate(2 hours); chhota "Alex
        Scheduler" Lambda jo research_auto kick karta = fire-and-forget dispatcher;
        Terraform conditional resource `count = var.scheduler_enabled ? 1 : 0`;
        do-layer observability: App Runner CloudWatch logs + OpenAI traces).
  L88 = Week 3 wrap-up + assignment (resilience: SQS retries -> yahan idempotency
        ka rationale; cost discipline: scheduler_enabled=false / terraform destroy).
  NOTE: Ed ne lecture me NAYA `aws_scheduler_schedule` (EventBridge Scheduler)
  resource use kiya. Yeh lab CLASSIC `aws_cloudwatch_event_rule` + target +
  lambda_permission triple dikhata hai (task ne yeh explicitly maanga, aur yahi
  Lambda-invoke ki wiring ko sabse saaf dikhata hai) — dono real AWS scheduling
  hain. Difference ek note me niche samjhaaya hai.

COST: Is lab ko LOCALLY chalana = $0. boto3/AWS creds na ho to "research call"
  ek LOCAL mock run karta hai (no network); LLM key bhi na ho to summary planning
  text SKIP karke sirf run-shape + structured log dikhta hai — phir bhi EXIT 0,
  zero cost, zero crash.
  REAL AWS deploy (runbook): EventBridge rule/schedule khud lagbhag free (first
  ~14M custom events/month free tier ke andar). Asli kharcha har TICK par hota
  hai jo wo trigger karta hai: Lambda invocation (chhota) + downstream research
  run (App Runner agent loop + Bedrock tokens + SageMaker embed + S3 vectors,
  L77-L82). rate(2 hours) => din me 12 runs => agar each run ~Nova-Pro 3/10
  cent + chhota App Runner/Lambda compute, to monthly ~$ few dollars. Cadence
  badhao (rate(2 hours) -> rate(20 hours)) ya scheduler_enabled=false karke
  cost neeche rakho (L87/L88 cost discipline).
"""

import hashlib
import json
import os
import sys
import time

from dotenv import load_dotenv
from openai import OpenAI

# .env load. override=True => .env value shell ki purani value ko jeet jaaye
# (Ed Donner ki convention). GROQ_API_KEY etc. yahin se uth jaayega (agar ho).
load_dotenv(override=True)


# ===========================================================================
# get_client — optional LLM (sirf "run plan" sentence generate karne ke liye).
# EXACT helper (placeholder fix ke saath). Key na ho to live call SKIP — exit 0.
# ===========================================================================
# Groq/Gemini OpenAI-compatible hain — sirf base_url alag. Scheduled job ko LLM ki
# zaroorat NAHI hai; hum sirf demo me dikhate hain ki agar research agent ke liye
# ek chhota "aaj kya research karna hai" plan banana ho to provider yahin se aata.
def get_client(provider: str = "groq"):
    """(client, model). Default groq => free. NOTE `or "placeholder"`: OpenAI() None key par
    CONSTRUCTION time hi crash karta hai, isliye placeholder."""
    if provider == "groq":
        return OpenAI(base_url="https://api.groq.com/openai/v1",
                      api_key=os.getenv("GROQ_API_KEY") or "placeholder"), "llama-3.3-70b-versatile"
    if provider == "gemini":
        return OpenAI(base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
                      api_key=os.getenv("GOOGLE_API_KEY") or "placeholder"), "gemini-2.5-flash"
    raise ValueError(f"Unknown provider: {provider}")


# ===========================================================================
# ##########  SCHEDULE EXPRESSIONS — cron vs rate (teaching helper)  #########
# ===========================================================================
# EventBridge do flavours deta hai "kab chalana" bolne ke:
#   1) rate(<value> <unit>)   e.g. rate(2 hours), rate(10 minutes), rate(1 day)
#      -> "create hone ke baad har <value> <unit>". Simple FIXED INTERVAL. Yahi
#         Ed ne L87 me use kiya (rate(2 hours)).
#   2) cron(min hour day-of-month month day-of-week year)  -> 6 fields, EXACT
#      wall-clock. AWS cron classic Unix cron se thoda alag hai: 6 fields (year
#      extra), aur day-of-month / day-of-week dono * NAHI ho sakte — ek ko `?`
#      (no-specific-value) rakhna padta. e.g. cron(0 9 * * ? *) = roz 09:00 UTC.
# IMPORTANT: EventBridge ka time ZONE hamesha UTC hota hai (rule-based). Local
# time chahiye to naya "EventBridge Scheduler" timezone support deta hai — par
# classic rule UTC-only. (Yeh ek bada gotcha hai: "9am" likha, prod me 9am UTC
# chala, India me 2:30pm — schedule hamesha UTC me socho.)
def explain_schedule(expr: str) -> dict:
    """Ek schedule_expression string ko parse/validate karke human-readable
    explanation deta hai. Sirf STRING parsing — koi AWS call nahi. (Teaching +
    Terraform me likhi expr ko sanity-check karne ke kaam aata hai.)"""
    expr = (expr or "").strip()
    info = {"expr": expr, "kind": None, "human": None, "valid": False, "note": None}

    # --- rate(...) ---------------------------------------------------------
    if expr.startswith("rate(") and expr.endswith(")"):
        inner = expr[len("rate("):-1].strip()        # e.g. "2 hours"
        parts = inner.split()
        info["kind"] = "rate"
        # rate ke do tokens hote hain: ek number + ek unit (minute/hour/day,
        # singular tabhi jab value==1, warna plural). AWS yeh strictly check karta.
        if len(parts) == 2 and parts[0].isdigit():
            value, unit = int(parts[0]), parts[1]
            ok_units = {"minute", "minutes", "hour", "hours", "day", "days"}
            if unit in ok_units and value >= 1:
                # singular/plural rule: value==1 => singular, warna plural.
                expect = unit.rstrip("s") + ("" if value == 1 else "s")
                if unit == expect:
                    info["valid"] = True
                    info["human"] = f"har {value} {unit} (fixed interval, create ke baad se)"
                else:
                    info["note"] = (f"value={value} ke saath unit '{expect}' hona chahiye "
                                    f"(AWS singular/plural strict hai)")
            else:
                info["note"] = f"unit '{unit}' invalid (minute(s)/hour(s)/day(s) allowed)"
        else:
            info["note"] = "rate(<positive-int> <unit>) shape expected, e.g. rate(2 hours)"
        return info

    # --- cron(...) ---------------------------------------------------------
    if expr.startswith("cron(") and expr.endswith(")"):
        inner = expr[len("cron("):-1].strip()
        fields = inner.split()
        info["kind"] = "cron"
        # AWS cron = 6 fields: minutes hours day-of-month month day-of-week year.
        # (Unix cron = 5 fields; AWS ka extra 'year' + ? convention yaad rakho.)
        if len(fields) == 6:
            mn, hr, dom, mon, dow, yr = fields
            info["valid"] = True
            info["human"] = (f"minute={mn} hour={hr} day-of-month={dom} month={mon} "
                             f"day-of-week={dow} year={yr}  (UTC, 6-field AWS cron)")
            # classic gotcha: dom aur dow dono '*' nahi ho sakte (ek '?' chahiye).
            if dom == "*" and dow == "*":
                info["valid"] = False
                info["note"] = ("AWS cron me day-of-month aur day-of-week dono '*' nahi ho "
                                "sakte — ek ko '?' (no-specific-value) karo")
        else:
            info["note"] = (f"AWS cron me 6 fields chahiye (mila {len(fields)}): "
                            "min hour day-of-month month day-of-week year")
        return info

    info["note"] = "expr 'rate(...)' ya 'cron(...)' se shuru hona chahiye"
    return info


# ===========================================================================
# IDEMPOTENCY — scheduled jobs at-least-once chal sakte hain, isliye dedupe.
# ===========================================================================
# WHY: EventBridge -> Lambda invocation "at-least-once" hai. Retry, transient
# error, ya overlapping schedule tick ki wajah se ek hi LOGICAL run ka handler
# do baar chal sakta hai. Agar handler har baar research+ingest blindly chalaye
# to: (a) double cost (Bedrock tokens + SageMaker embed dobara), (b) duplicate
# vectors S3 me (data corruption). Solution: har run ko ek DETERMINISTIC RUN-KEY
# do (schedule TIME + rule se derive — retry par bhi WAHI key banegi), aur ek
# durable store me "yeh key process ho chuki?" check karo. Pehli baar => run +
# mark. Dobara aaye => skip (idempotent).
#
# Production me yeh store = DynamoDB (conditional PutItem with attribute_not_exists
# => atomic "claim") ya S3 object existence. Yahan demo ke liye ek in-memory set;
# concept same hai. (L88 ka resilience/retry sabak yahin connect hota.)
_PROCESSED_RUN_KEYS: set[str] = set()


def make_run_key(event: dict) -> str:
    """Scheduled event se ek DETERMINISTIC run-key banao. Retry par SAME event
    (same id/time/resources) => SAME key => duplicate detect ho jaata hai.
    Hum event['time'] (schedule tick ka UTC timestamp) + rule ARN ko hash karte
    hain — yeh dono retry ke beech constant rehte hain (event['id'] kabhi-kabhi
    badal sakta, isliye time+rule zyada reliable idempotency anchor hai)."""
    when = (event or {}).get("time", "")                       # "2026-06-13T09:00:00Z"
    resources = (event or {}).get("resources", []) or []
    rule = resources[0] if resources else "unknown-rule"
    raw = f"{rule}|{when}"
    # short stable hash — readable + collision-safe enough for a run-key.
    return "run-" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def already_processed(run_key: str) -> bool:
    """Idempotency check. Production: DynamoDB conditional write / S3 head-object."""
    return run_key in _PROCESSED_RUN_KEYS


def mark_processed(run_key: str) -> None:
    """Run-key ko 'done' mark karo taaki agla retry skip ho jaaye."""
    _PROCESSED_RUN_KEYS.add(run_key)


# ===========================================================================
# THE JOB — chhota research/ingest "kick". L87 ka Alex Scheduler = fire-and-forget.
# ===========================================================================
# Ed ka real Alex Scheduler Lambda ka EKMAATRA kaam: App Runner ke research_auto
# endpoint ko call karna (research run kick karna). Wo job khud nahi karta — sirf
# downstream service ko POKE karta (dispatcher pattern = decoupling). Hum yahi
# emulate karte hain: try karo "research kick" boto3/HTTP se; available na ho to
# ek LOCAL mock run chala do. Dono case me ek run summary banta hai.
def kick_research_run(run_key: str, topic: str) -> dict:
    """Research/ingest pipeline ko 'kick' karo (fire-and-forget). REAL deploy me
    yeh App Runner ke /research_auto ko HTTP se call karta (ya Lambda ko boto3 se
    invoke). Yahan boto3 LAZILY try; missing/no-creds => LOCAL mock run. NEVER
    crash, NEVER network/download."""
    # --- AWS path: boto3 se downstream Lambda invoke (ya App Runner HTTP) -------
    # boto3 ko LAZILY import karte hain — module top par NAHI. Kyun? (1) is env me
    # boto3 install hi nahi; top-level import poori file crash kar deta. (2) Lambda
    # runtime me boto3 built-in hota hai par local dev me nahi — lazy dono jagah
    # safe. Import/creds fail => clean Hinglish note + local fallback.
    try:
        import boto3  # noqa: F401  (lazy on purpose)

        target = os.getenv("RESEARCH_LAMBDA_NAME")  # downstream researcher Lambda
        if not target:
            # boto3 to hai, par hum config nahi diya ki KISKO kick karna — local mock.
            raise RuntimeError("RESEARCH_LAMBDA_NAME set nahi => kis Lambda ko kick karna pata nahi")

        # NOTE: yeh asli invoke shape hai jo deploy par chalta. InvocationType
        # "Event" = ASYNC fire-and-forget (scheduler ko response ka wait nahi
        # karna — wahi "kick aur bhool jao" pattern, L87). Yahan tak pahunchna
        # is env me hoga hi nahi (boto3 missing), isliye yeh teaching reference hai.
        region = os.getenv("AWS_REGION", "us-east-1")
        client = boto3.client("lambda", region_name=region)
        payload = json.dumps({"run_key": run_key, "topic": topic})
        client.invoke(FunctionName=target, InvocationType="Event", Payload=payload)
        return {"mode": "aws", "target": target, "dispatched": True,
                "note": f"async kick bheja Lambda '{target}' ko (InvocationType=Event)"}
    except ImportError:
        print("[INFO] boto3 missing => AWS research-kick nahi ho sakta. "
              "AWS not configured -> local mock run.")
    except Exception as e:
        # BotoCoreError/ClientError (no creds, AccessDenied, region) + humara
        # RuntimeError sab yahan. Crash mat karo — degrade karo (L87/L88 spirit).
        print(f"[INFO] AWS research-kick unavailable ({e}) -> local mock run.")

    # --- LOCAL fallback: ek mock research run "chalaya" (no network) -----------
    # Real run App Runner par chalta; yahan hum sirf yeh dikhate hain ki scheduled
    # handler ne kaam DISPATCH kiya — ek deterministic mock result banake.
    fake_docs = max(1, (sum(ord(c) for c in run_key) % 3) + 1)  # 1..3, deterministic
    return {"mode": "local-mock", "target": None, "dispatched": True,
            "docs_would_ingest": fake_docs,
            "note": "boto3/AWS na hone par local mock research run (no network, $0)"}


def plan_research_topic() -> str:
    """OPTIONAL: agar LLM key ho to ek chhota 'aaj kya research karna hai' line
    generate karo (context engineering ka chhota swaad, L88). Key na ho to ek
    fixed default topic — LIVE call SKIP, exit 0. Scheduled job ko LLM ki zaroorat
    NAHI; yeh sirf demo ki garnish hai."""
    default = "latest financial market & macro updates for the knowledge base"
    key = os.getenv("GROQ_API_KEY")
    if not key:
        # Graceful skip — koi live call nahi, koi cost nahi.
        return default + "  [LLM SKIPPED: GROQ_API_KEY missing => $0]"
    try:
        client, model = get_client("groq")
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "user",
                       "content": "In 12 words, suggest one finance research topic to "
                                  "ingest into a vector knowledge base today."}],
            max_tokens=40,
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        # Network/key/rate-limit kuch bhi fail ho — degrade, crash nahi.
        return default + f"  [LLM call failed: {e}]"


# ===========================================================================
# STRUCTURED LOG — Lambda stdout -> CloudWatch Logs. JSON => metrics/alarms (L49/L87).
# ===========================================================================
def _emit_log(record: dict) -> None:
    """Ek STRUCTURED JSON log line stdout par. Lambda me stdout seedha CloudWatch
    Logs me jaata hai; JSON hone se CloudWatch metric filters in fields ko parse
    karke METRICS/ALARMS bana lete hain (L87 do-layer observability ka infra layer)."""
    print(json.dumps(record, ensure_ascii=False))


# ===========================================================================
# AWS LAMBDA HANDLER — REAL deployable. EventBridge SCHEDULED-event contract.
# ===========================================================================
# Yeh WAHI function hai jo EventBridge rule trigger karta (L87 ka Alex Scheduler).
# API-Gateway-proxy se ALAG: yahan event me httpMethod/path/body NAHI hota. Iske
# bajaye:
#   event["source"]      == "aws.events"
#   event["detail-type"] == "Scheduled Event"
#   event["time"]        == us tick ka UTC timestamp
#   event["resources"]   == [rule ARN jisne fire kiya]
# Handler:
#   1) Verify karta hai ki yeh sach me scheduled event hai (warna clean skip).
#   2) Idempotency: run-key banake check — duplicate tick? to skip.
#   3) Research run "kick" karta (fire-and-forget) + ek summary banata.
#   4) Ek structured JSON log emit karta + summary dict return karta.
# Async invoke (InvocationType=Event) me return value kahin nahi jaata — par hum
# phir bhi summary return karte hain (sync test / step-functions / CloudWatch ke
# liye useful, aur self-demo isse print karta hai).
def handler(event, context):
    """EventBridge scheduled event -> ek research/ingest run kick karo + summary do.
    Bina AWS/boto3/key ke bhi chalta hai (local mock) — kabhi unhandled crash nahi."""
    event = event or {}
    source = event.get("source")
    detail_type = event.get("detail-type")

    # --- 0) Yeh sach me scheduled event hai? (defensive contract check) --------
    # EventBridge ek hi Lambda par alag-alag event bhej sakta hai. Hum sirf apna
    # scheduled-tick handle karte hain; baaki ko clean skip (status="ignored")
    # — taaki galat trigger par bhi crash na ho.
    is_scheduled = (source == "aws.events" and detail_type == "Scheduled Event")
    if not is_scheduled:
        _emit_log({"event": "scheduled_run", "status": "ignored",
                   "reason": f"not a scheduled event (source={source}, detail-type={detail_type})"})
        return {"status": "ignored",
                "reason": "expected source='aws.events' & detail-type='Scheduled Event'"}

    # context (Lambda runtime object) se request id — logs/traces correlate karne ko.
    # Local self-demo me hum ek chhota mock context bhejte hain (niche dekho).
    aws_request_id = getattr(context, "aws_request_id", None) if context else None

    # --- 1) Idempotency: is tick ka deterministic run-key + dedupe -------------
    run_key = make_run_key(event)
    if already_processed(run_key):
        # At-least-once delivery ka duplicate. Skip => no double cost / dup vectors.
        _emit_log({"event": "scheduled_run", "status": "skipped_duplicate",
                   "run_key": run_key, "schedule_time": event.get("time"),
                   "aws_request_id": aws_request_id})
        return {"status": "skipped_duplicate", "run_key": run_key,
                "schedule_time": event.get("time")}

    # --- 2) Asli kaam: research topic plan + downstream research run kick -------
    start = time.time()
    topic = plan_research_topic()                 # optional LLM (key na ho to skip)
    kick = kick_research_run(run_key, topic)       # boto3 try -> local mock fallback

    # Idempotency mark SUCCESS ke baad. (Production me yeh atomic "claim" pehle
    # hota hai — par concept ke liye yahan run ke baad mark kar rahe; agar tum
    # at-most-once chahte ho to claim-before-work karo.)
    mark_processed(run_key)
    latency_ms = int((time.time() - start) * 1000)

    # --- 3) Structured log (CloudWatch food) + summary -------------------------
    summary = {
        "status": "ok",
        "run_key": run_key,                       # idempotency anchor
        "schedule_time": event.get("time"),        # kis tick par chala (UTC)
        "rule_arn": (event.get("resources") or [None])[0],
        "research_topic": topic,
        "kick": kick,                             # aws ya local-mock dispatch result
        "latency_ms": latency_ms,
        "aws_request_id": aws_request_id,
    }
    _emit_log({"event": "scheduled_run", **{k: summary[k] for k in
               ("status", "run_key", "schedule_time", "latency_ms")},
               "kick_mode": kick.get("mode")})
    return summary


# ===========================================================================
# SELF-DEMO — `uv run <file>` (no args) yahan aata hai. No AWS/boto3/key => exit 0.
# ===========================================================================
# Handler ko hand-built MOCK EventBridge scheduled-event dicts se invoke karte
# hain — bilkul wahi shape jo deployed Lambda ko EventBridge bhejta. Saath me cron/
# rate explain karte hain, push-vs-pull samjhaate hain, aur idempotency ko ek
# DUPLICATE tick bhej ke prove karte hain (dusri baar skip hona chahiye).
class _MockLambdaContext:
    """Lambda runtime `context` object ka minimal mock. Asli context me
    aws_request_id, function_name, get_remaining_time_in_millis() hote hain;
    hum bas itna dete hain jitna handler chhuta hai."""
    def __init__(self, request_id="mock-req-id-0001"):
        self.aws_request_id = request_id
        self.function_name = "alex-scheduler"
        self.memory_limit_in_mb = 128

    def get_remaining_time_in_millis(self):
        return 60000


def _mock_scheduled_event(rule_name="alex-research-schedule",
                          when="2026-06-13T09:00:00Z",
                          event_id="11111111-2222-3333-4444-555555555555"):
    """Ek minimal EventBridge SCHEDULED event dict — jaisa AWS bhejta hai.
    detail aksar khaali ({}) hota hai scheduled events me (koi business payload
    nahi — sirf "time aa gaya, chalo")."""
    return {
        "version": "0",
        "id": event_id,
        "detail-type": "Scheduled Event",
        "source": "aws.events",
        "account": "123456789012",
        "time": when,
        "region": "us-east-1",
        "resources": [f"arn:aws:events:us-east-1:123456789012:rule/{rule_name}"],
        "detail": {},
    }


def _print_schedule_lessons():
    """cron vs rate, push vs pull — teaching block. Sirf print + local parse."""
    print("=" * 72)
    print("SCHEDULE EXPRESSIONS — rate(...) vs cron(...)   [EventBridge, UTC]")
    print("=" * 72)
    for expr in ["rate(2 hours)", "rate(10 minutes)", "cron(0 9 * * ? *)",
                 "rate(1 hours)", "cron(0 9 * * * *)", "rate(5 bananas)"]:
        info = explain_schedule(expr)
        flag = "OK " if info["valid"] else "BAD"
        human = info["human"] or info["note"]
        print(f"  [{flag}] {expr:20s} -> {human}")
    print()
    print("PUSH vs PULL scheduling:")
    print("  PULL (classic cron): ek always-on box har minute jaagke poochta")
    print("       'kuch chalana hai?'. Server tumhara, patching tumhari, idle bhi paisa.")
    print("  PUSH (EventBridge) : AWS ka managed scheduler time aane par TUMHARE Lambda")
    print("       ko INVOKE/push karta. Koi server nahi, idle = $0. (L87: managed cron)")
    print()


def run_self_demo():
    """Schedule lessons, ek scheduled tick handle, phir DUPLICATE tick se
    idempotency prove — phir exit 0 (chahe AWS/boto3/key ho ya na ho)."""
    print("\n" + "#" * 72)
    print("#  LAB 6 SELF-DEMO — EventBridge scheduled agent  (no AWS/boto3/key bhi OK)")
    print("#" * 72 + "\n")

    # --- 1) cron/rate + push-vs-pull (teaching) ----------------------------
    _print_schedule_lessons()

    # --- 2) ek scheduled tick handle karo (mock EventBridge event) ---------
    print("=" * 72)
    print("HANDLER: scheduled tick #1   (rate(2 hours) ka ek wake-up, L87 Alex Scheduler)")
    print("=" * 72)
    ev = _mock_scheduled_event(when="2026-06-13T09:00:00Z")
    ctx = _MockLambdaContext("mock-req-id-0001")
    print("INPUT event (EventBridge scheduled shape):")
    print(json.dumps(ev, indent=2, ensure_ascii=False))
    print("\n--- structured log line(s) below = exactly Lambda -> CloudWatch Logs ---")
    summary1 = handler(ev, ctx)
    print("--- end logs ---\n")
    print("RUN SUMMARY:")
    print(json.dumps(summary1, indent=2, ensure_ascii=False))
    print()

    # --- 3) IDEMPOTENCY proof: WAHI tick dobara (retry) => skip ------------
    print("=" * 72)
    print("HANDLER: SAME tick dobara (at-least-once retry simulate) => idempotent skip")
    print("=" * 72)
    print("Note: same event['time'] + same rule => SAME run_key => duplicate detect.")
    print("\n--- structured log line(s) ---")
    summary2 = handler(ev, _MockLambdaContext("mock-req-id-0002"))  # naya request id, same tick
    print("--- end logs ---\n")
    print("RUN SUMMARY (dobara):")
    print(json.dumps(summary2, indent=2, ensure_ascii=False))
    assert summary2["status"] == "skipped_duplicate", "idempotency fail!"
    print("\n>> IDEMPOTENT: dusri baar status='skipped_duplicate' — research dobara NAHI chala")
    print("   (warna double cost + duplicate vectors). Yahi at-least-once ka guard. (L88)")
    print()

    # --- 4) AGLA tick (alag time) => naya run, normal chalega --------------
    print("=" * 72)
    print("HANDLER: scheduled tick #2   (2 ghante baad ka NAYA tick => naya run_key)")
    print("=" * 72)
    ev2 = _mock_scheduled_event(when="2026-06-13T11:00:00Z")  # alag time => alag key
    print("\n--- structured log line(s) ---")
    summary3 = handler(ev2, _MockLambdaContext("mock-req-id-0003"))
    print("--- end logs ---\n")
    print("RUN SUMMARY (naya tick):")
    print(json.dumps(summary3, indent=2, ensure_ascii=False))
    assert summary3["status"] == "ok", "new tick should run!"
    print()

    # --- 5) Non-scheduled event => clean ignore (contract safety) ----------
    print("=" * 72)
    print("HANDLER: galat event (S3 event, scheduled nahi) => clean ignore, no crash")
    print("=" * 72)
    bogus = {"source": "aws.s3", "detail-type": "Object Created"}
    print("\n--- structured log line(s) ---")
    summary4 = handler(bogus, _MockLambdaContext())
    print("--- end logs ---\n")
    print("RUN SUMMARY:")
    print(json.dumps(summary4, indent=2, ensure_ascii=False))
    assert summary4["status"] == "ignored", "non-scheduled should be ignored!"
    print()

    # --- 6) Wiring + cost explainer ----------------------------------------
    print("=" * 72)
    print("EVENTBRIDGE -> LAMBDA WIRING  (deploy/eventbridge_schedule.tf)")
    print("=" * 72)
    print("3 resources milke yeh kaam karte hain (Terraform file me detail):")
    print("  1) aws_cloudwatch_event_rule   : schedule_expression = rate(2 hours)")
    print("                                    (kab fire karna — managed cron)")
    print("  2) aws_cloudwatch_event_target : rule -> is Lambda ko point karta")
    print("                                    (kya invoke karna)")
    print("  3) aws_lambda_permission       : EventBridge ko is Lambda ko INVOKE")
    print("                                    karne ki ijaazat (warna AccessDenied)")
    print(">> Bina permission ke rule fire to hoga par Lambda invoke 'silently' fail")
    print("   (yeh #1 EventBridge gotcha hai). source_arn se rule tak scope karo.")
    print()
    print("COST DISCIPLINE (L87/L88): rate(2 hours) => din me 12 runs. Mehnga lage to")
    print("  scheduler_enabled=false + terraform apply (rule delete), ya cadence badhao")
    print("  (rate(20 hours)). Rule khud lagbhag free; kharcha har tick ke downstream")
    print("  research run (Bedrock+SageMaker+S3) par.")
    print()

    print("#" * 72)
    print("#  LAB 6 complete. handler() = EventBridge scheduled-event shape; idempotent")
    print("#  (at-least-once safe); boto3/AWS na ho to local mock; har run ek JSON log.")
    print("#" * 72 + "\n")

    raise SystemExit(0)


# ===========================================================================
# MAIN — default self-demo; --one => sirf ek scheduled tick + summary.
# ===========================================================================
if __name__ == "__main__":
    if "--one" in sys.argv:
        # Minimal: ek scheduled tick handle karke summary print.
        ev = _mock_scheduled_event()
        result = handler(ev, _MockLambdaContext())
        print(json.dumps(result, indent=2, ensure_ascii=False))
        raise SystemExit(0)
    else:
        run_self_demo()
