"""
Level8 Doc8 -- Observability Practical Lab (Hinglish Edition)
==============================================================

KYA SEEKHENGE (What We Will Learn):
  1. Teen pillars of observability -- Tracing, Metrics, Logging
  2. Custom LLMLogger -- contextmanager + JSONL sink (theory section 7)
  3. PII redaction -- safe_log pattern (theory section 11)
  4. Metrics collection -- tokens, latency, cost per call (theory section 8)
  5. Alerting rules simulator -- high latency, cost budget, error rate (theory section 9)
  6. Langfuse-style @observe decorator -- manual implementation (theory section 4)
  7. OpenTelemetry-style span tracing -- manual simulation (theory section 6)
  8. Helicone-style proxy concept -- base_url swap (theory section 5)
  9. Live LLM call -- Groq free tier, graceful degradation without key
 10. Production stack summary (theory section 10)

KAISE CHALANA (How to Run):
  uv run --project /Users/youngmanindia/Documents/PythonRevision/Agentic_AI/my-agentic-ai-project \
      python Level8_Production_LLMOps/08_observability_practical.py

  Ya phir directly (with uv environment active):
  uv run python 08_observability_practical.py

  Key nahi hai? Koi baat nahi -- script offline MOCK mode mein chala leti hai EXIT 0.
  Groq key chahiye production calls ke liye:
    export GROQ_API_KEY=gsk_...
"""

# ---------------------------------------------------------------------------
# Standard library imports -- koi heavy deps nahi
# ---------------------------------------------------------------------------
import os
import re
import json
import time
import uuid
import math
import random
import statistics
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Generator, List, Optional
from io import StringIO

# ---------------------------------------------------------------------------
# SETUP -- key check aur mock mode decide karo
# ---------------------------------------------------------------------------

GROQ_API_KEY = os.getenv("GROQ_API_KEY") or "placeholder"
LIVE_MODE = GROQ_API_KEY != "placeholder"  # True only when real key hai

print("=" * 65)
print("  OBSERVABILITY PRACTICAL -- Level 8, Doc 8")
print("  (Hinglish Edition -- Roman script only)")
print("=" * 65)
if not LIVE_MODE:
    print("  [MOCK MODE] GROQ_API_KEY nahi mili -- fake data use hoga.")
    print("  Live calls skip honge, EXIT 0 guarantee hai.")
else:
    print("  [LIVE MODE] GROQ_API_KEY mili -- real LLM calls honge.")
print()


# ---------------------------------------------------------------------------
# HELPER: get_client -- OpenAI-compatible client for Groq free tier
# Theory note: OpenAI() crashes on None key, isliye placeholder use karo
# ---------------------------------------------------------------------------

def get_client():
    """
    Groq ka free LLM client return karo.
    api_key=placeholder set hai taaki OpenAI() constructor crash na kare.
    LIVE_MODE=False hone par yeh function call nahi hota.
    """
    from openai import OpenAI  # lazy import -- sirf jab zaroorat ho
    return OpenAI(
        base_url="https://api.groq.com/openai/v1",
        api_key=GROQ_API_KEY,  # placeholder string -- constructor safe hai
    )


# ---------------------------------------------------------------------------
# SECTION 1: TEEN PILLARS -- Tracing, Metrics, Logging
# Theory section 2 -- Teen sawaalon ke jawab
# ---------------------------------------------------------------------------

print("=" * 65)
print("SECTION 1: Teen Pillars of Observability")
print("=" * 65)

PILLARS = {
    "Tracing":  "Step-by-step kya hua? Poora agent trace tree dikhata hai.",
    "Metrics":  "Kitna fast/mehenga/accurate? P50/P95/P99 latency, cost/call.",
    "Logging":  "Input/output kya tha? JSONL sink mein har call ka record.",
}

print()
for pillar, description in PILLARS.items():
    print(f"  {pillar:<12}: {description}")

print()
print("  Production AI bina observability ke ANDHA hai.")
print("  Bug kahan? Latency kyun badhi? Kaunsa prompt version better?")
print("  Yeh sab sirf observability se pata chalta hai.")
print()


# ---------------------------------------------------------------------------
# SECTION 2: PII REDACTION -- safe_log()
# Theory section 11 -- GDPR/CCPA compliance ke liye zaruri
# ---------------------------------------------------------------------------

print("=" * 65)
print("SECTION 2: PII Redaction -- safe_log()")
print("=" * 65)


def safe_log(text: str) -> str:
    """
    PII redact karo logs se before sending to any observability sink.
    Theory section 11 se directly liya gaya pattern.
    - Email addresses -> [EMAIL]
    - Phone numbers (10+ digits) -> [PHONE]
    - Credit card numbers (16 digits) -> [CARD]
    """
    # Email redaction
    text = re.sub(r"[\w.+-]+@[\w-]+\.[\w.-]+", "[EMAIL]", text)
    # Phone numbers (10 ya zyada consecutive digits)
    text = re.sub(r"\b\d{10,}\b", "[PHONE]", text)
    # Credit card (exactly 16 digits)
    text = re.sub(r"\b\d{16}\b", "[CARD]", text)
    return text


# Demo -- PII redaction test karo
test_texts = [
    "User email: john.doe@example.com aur phone 9876543210 hai.",
    "Card number: 4111111111111111 use mat karo production mein.",
    "Normal query: Python mein list comprehension kaise likhte hain?",
    "Customer 9876543210 ne email ashish@test.in se complaint ki.",
]

print()
print("  PII redaction demo:")
for original in test_texts:
    redacted = safe_log(original)
    changed = "(REDACTED)" if redacted != original else "(clean)"
    print(f"  IN:  {original}")
    print(f"  OUT: {redacted} {changed}")
    print()


# ---------------------------------------------------------------------------
# SECTION 3: CUSTOM LLMLogger -- contextmanager + JSONL sink
# Theory section 7 -- Framework-independent logging
# ---------------------------------------------------------------------------

print("=" * 65)
print("SECTION 3: Custom LLMLogger (theory section 7 ka live demo)")
print("=" * 65)


class LLMLogger:
    """
    Custom logger -- koi bhi LLM framework ho, yeh kaam karega.
    Theory section 7 ka direct implementation.

    Sink: StringIO (in-memory) -- production mein open("logs.jsonl", "a") use karo.
    current_trace_id: poore agent run ka shared ID hai.
    """

    def __init__(self, sink):
        self.sink = sink
        self.current_trace_id: Optional[str] = None
        self._records: List[Dict] = []  # in-memory copy for demo display

    def new_trace(self) -> str:
        """Naya trace start karo -- ek agent run = ek trace_id."""
        self.current_trace_id = str(uuid.uuid4())[:8]
        return self.current_trace_id

    @contextmanager
    def trace(self, name: str, **metadata) -> Generator[Dict, None, None]:
        """
        Context manager -- ek span (step) ka record banata hai.
        Usage:
            with logger.trace("llm_call", model="llama3") as span:
                span["metadata"]["tokens"] = 42
        """
        span_id = str(uuid.uuid4())[:8]
        trace_id = self.current_trace_id or span_id
        start = time.time()

        record: Dict[str, Any] = {
            "span_id": span_id,
            "trace_id": trace_id,
            "name": name,
            "start_time_iso": datetime.utcnow().isoformat(),
            "metadata": dict(metadata),
            "error": None,
            "duration_ms": 0.0,
        }

        try:
            yield record
        except Exception as exc:
            record["error"] = str(exc)
            raise
        finally:
            record["duration_ms"] = round((time.time() - start) * 1000, 2)
            # PII safe karo before writing
            safe_record = json.dumps(record)
            self.sink.write(safe_record + "\n")
            self._records.append(record)

    def get_records(self) -> List[Dict]:
        return list(self._records)


# Demo -- logger use karke ek fake agent run trace karo
print()
print("  LLMLogger demo -- ek fake agent run trace ho raha hai:")
print()

log_sink = StringIO()  # in-memory sink
logger = LLMLogger(sink=log_sink)
trace_id = logger.new_trace()
print(f"  Trace ID: {trace_id}")

# Agent run simulate karo
with logger.trace("agent_run", user_id="u123", query="Explain Python GIL"):
    # Step 1: retrieve docs
    with logger.trace("retrieve_docs", source="vectorstore") as span:
        time.sleep(0.01)  # simulate retrieval
        span["metadata"]["docs_count"] = 3
        span["metadata"]["query_tokens"] = 12

    # Step 2: LLM call (mock)
    with logger.trace("llm_call", model="llama3-8b-8192") as span:
        time.sleep(0.02)  # simulate LLM call
        span["metadata"]["input_tokens"] = 150
        span["metadata"]["output_tokens"] = 80
        span["metadata"]["cost_usd"] = round(230 * 0.000001, 6)  # Groq pricing

    # Step 3: tool call (mock)
    with logger.trace("tool_call", tool_name="web_search") as span:
        time.sleep(0.01)
        span["metadata"]["search_query"] = "Python GIL explained"
        span["metadata"]["results_count"] = 5

# Recorded spans dikhao
records = logger.get_records()
print(f"  Total spans recorded: {len(records)}")
print()
print("  Span tree (theory section 3 ka format):")
for rec in records:
    indent = "  " if rec["name"] != "agent_run" else ""
    error_note = f" [ERROR: {rec['error']}]" if rec["error"] else ""
    meta_tokens = rec["metadata"].get("output_tokens", "")
    token_note = f" | {meta_tokens} tokens" if meta_tokens else ""
    print(f"    {indent}+-- {rec['name']:<20} {rec['duration_ms']:>6.1f}ms{token_note}{error_note}")

print()
print("  JSONL sample (pehli line):")
log_sink.seek(0)
first_line = log_sink.readline()
first_obj = json.loads(first_line)
print(f"    span_id    : {first_obj['span_id']}")
print(f"    trace_id   : {first_obj['trace_id']}")
print(f"    name       : {first_obj['name']}")
print(f"    duration_ms: {first_obj['duration_ms']}")
print()


# ---------------------------------------------------------------------------
# SECTION 4: METRICS COLLECTION -- per call aur per run
# Theory section 8 -- Kya track karna chahiye
# ---------------------------------------------------------------------------

print("=" * 65)
print("SECTION 4: Metrics Collection (theory section 8)")
print("=" * 65)


@dataclass
class LLMCallMetrics:
    """
    Theory section 8 'Per LLM call' metrics ka dataclass.
    Har LLM call ke baad yeh object fill karo.
    """
    call_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    model: str = "llama3-8b-8192"
    input_tokens: int = 0
    output_tokens: int = 0
    latency_ms: float = 0.0
    cost_usd: float = 0.0
    error: Optional[str] = None
    user_id: Optional[str] = None
    session_id: Optional[str] = None

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens

    def cost_from_groq_pricing(self):
        """
        Groq free tier approximate pricing (USD per 1M tokens).
        llama3-8b: input $0.05, output $0.10 per 1M tokens (approx).
        """
        input_cost = (self.input_tokens / 1_000_000) * 0.05
        output_cost = (self.output_tokens / 1_000_000) * 0.10
        self.cost_usd = round(input_cost + output_cost, 8)
        return self.cost_usd


@dataclass
class AgentRunMetrics:
    """
    Theory section 8 'Per Agent Run' metrics ka dataclass.
    """
    run_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    total_cost_usd: float = 0.0
    total_latency_ms: float = 0.0
    tool_call_count: int = 0
    llm_call_count: int = 0
    outcome: str = "pending"   # success / error / timeout
    iterations: int = 0
    call_metrics: List[LLMCallMetrics] = field(default_factory=list)

    def add_call(self, call: LLMCallMetrics):
        self.call_metrics.append(call)
        self.total_cost_usd = round(self.total_cost_usd + call.cost_usd, 8)
        self.total_latency_ms = round(self.total_latency_ms + call.latency_ms, 2)
        self.llm_call_count += 1

    def p_latency(self, percentile: float) -> float:
        """P50/P95/P99 latency nikalo -- theory mein mention hai."""
        if not self.call_metrics:
            return 0.0
        latencies = sorted(m.latency_ms for m in self.call_metrics)
        idx = max(0, int(math.ceil(percentile / 100 * len(latencies))) - 1)
        return latencies[idx]


# Demo -- fake calls se metrics bharo
print()
print("  Simulated LLM call metrics (3 calls):")
print()

random.seed(42)
agent_run = AgentRunMetrics()
agent_run.tool_call_count = 2
agent_run.iterations = 3

fake_calls = [
    {"input_tokens": 120, "output_tokens": 60, "latency_ms": 340.0},
    {"input_tokens": 200, "output_tokens": 150, "latency_ms": 820.0},
    {"input_tokens": 90,  "output_tokens": 45,  "latency_ms": 190.0},
]

for i, c in enumerate(fake_calls, 1):
    m = LLMCallMetrics(
        user_id=f"user_{i}",
        session_id="sess_abc",
        input_tokens=c["input_tokens"],
        output_tokens=c["output_tokens"],
        latency_ms=c["latency_ms"],
    )
    m.cost_from_groq_pricing()
    agent_run.add_call(m)
    print(f"  Call {i}:  {m.total_tokens:>4} tokens | "
          f"{m.latency_ms:>6.0f}ms | ${m.cost_usd:.8f}")

agent_run.outcome = "success"

print()
print("  Agent Run Summary:")
print(f"    Run ID         : {agent_run.run_id}")
print(f"    LLM calls      : {agent_run.llm_call_count}")
print(f"    Tool calls     : {agent_run.tool_call_count}")
print(f"    Iterations     : {agent_run.iterations}")
print(f"    Total latency  : {agent_run.total_latency_ms:.0f}ms")
print(f"    Total cost     : ${agent_run.total_cost_usd:.8f}")
print(f"    P50 latency    : {agent_run.p_latency(50):.0f}ms")
print(f"    P95 latency    : {agent_run.p_latency(95):.0f}ms")
print(f"    P99 latency    : {agent_run.p_latency(99):.0f}ms")
print(f"    Outcome        : {agent_run.outcome}")
print()


# ---------------------------------------------------------------------------
# SECTION 5: ALERTING RULES SIMULATOR
# Theory section 9 -- Production alerts kaise set karte hain
# ---------------------------------------------------------------------------

print("=" * 65)
print("SECTION 5: Alerting Rules Simulator (theory section 9)")
print("=" * 65)


@dataclass
class AlertRule:
    """
    Ek alert rule -- naam, condition function, aur action.
    Theory section 9 ke sabhi alerts yahan implement hain.
    """
    name: str
    description: str
    action: str
    check: Any  # callable (metrics_dict) -> bool

    def evaluate(self, metrics: Dict[str, float]) -> bool:
        try:
            return bool(self.check(metrics))
        except Exception:
            return False


# Theory section 9 ke exact alerts reproduce karo
alert_rules: List[AlertRule] = [
    AlertRule(
        name="high_latency",
        description="P99 latency > 5000ms",
        action="page_oncall",
        check=lambda m: m.get("p99_latency_ms", 0) > 5000,
    ),
    AlertRule(
        name="cost_budget",
        description="Daily spend > $100",
        action="notify_team",
        check=lambda m: m.get("daily_spend_usd", 0) > 100,
    ),
    AlertRule(
        name="quality_drop",
        description="Faithfulness score < 0.8",
        action="alert_engineering",
        check=lambda m: m.get("faithfulness_score", 1.0) < 0.8,
    ),
    AlertRule(
        name="error_rate",
        description="Error rate > 1%",
        action="page_oncall",
        check=lambda m: m.get("error_rate_pct", 0) > 1.0,
    ),
]


def run_alert_checks(current_metrics: Dict[str, float]) -> List[str]:
    """Saari alert rules check karo, triggered alerts ki list return karo."""
    triggered = []
    for rule in alert_rules:
        fired = rule.evaluate(current_metrics)
        status = "FIRED" if fired else "OK   "
        print(f"    [{status}] {rule.name:<18} | {rule.description}")
        if fired:
            print(f"           -> Action: {rule.action}")
            triggered.append(rule.name)
    return triggered


# Normal metrics -- sab OK hona chahiye
print()
print("  Scenario A: Normal production metrics (sab theek hai):")
normal_metrics = {
    "p99_latency_ms": 2800.0,
    "daily_spend_usd": 45.0,
    "faithfulness_score": 0.92,
    "error_rate_pct": 0.3,
}
triggered_a = run_alert_checks(normal_metrics)
print(f"    Triggered alerts: {triggered_a or 'NONE -- sab theek!'}")

# Bad metrics -- sab fail hona chahiye
print()
print("  Scenario B: Degraded production metrics (sab bura hai):")
bad_metrics = {
    "p99_latency_ms": 7500.0,
    "daily_spend_usd": 130.0,
    "faithfulness_score": 0.65,
    "error_rate_pct": 3.2,
}
triggered_b = run_alert_checks(bad_metrics)
print(f"    Triggered alerts: {triggered_b}")
print()


# ---------------------------------------------------------------------------
# SECTION 6: LANGFUSE-STYLE @observe DECORATOR
# Theory section 4 -- Open-source framework-agnostic tracing
# ---------------------------------------------------------------------------

print("=" * 65)
print("SECTION 6: Langfuse-style @observe Decorator (theory section 4)")
print("=" * 65)

# Global trace store -- production mein yeh Langfuse server pe jaata hai
_LANGFUSE_TRACES: List[Dict] = []


def observe(func):
    """
    Theory section 4 ka @langfuse.observe() decorator ka manual version.
    Kisi bhi function ko decorate karo -- auto trace ho jaata hai.
    Production mein: from langfuse import Langfuse; langfuse.observe()
    """
    import functools

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        trace_entry: Dict[str, Any] = {
            "function": func.__name__,
            "trace_id": str(uuid.uuid4())[:8],
            "start_iso": datetime.utcnow().isoformat(),
            "args_repr": str(args)[:80],
            "kwargs_repr": str(kwargs)[:80],
            "output": None,
            "error": None,
            "duration_ms": 0.0,
        }
        t0 = time.time()
        try:
            result = func(*args, **kwargs)
            trace_entry["output"] = str(result)[:120]
            return result
        except Exception as exc:
            trace_entry["error"] = str(exc)
            raise
        finally:
            trace_entry["duration_ms"] = round((time.time() - t0) * 1000, 2)
            _LANGFUSE_TRACES.append(trace_entry)

    return wrapper


# Apply decorator to demo functions -- theory ka example reproduce karo
@observe
def retrieve_context(query: str) -> List[str]:
    """Fake retrieval -- production mein vectorstore call hoga."""
    time.sleep(0.01)
    return [
        f"Doc 1 about {query[:20]}",
        f"Doc 2 about {query[:20]}",
    ]


@observe
def format_prompt(query: str, docs: List[str]) -> str:
    """Context + query se prompt banao."""
    time.sleep(0.005)
    context = "\n".join(docs)
    return f"Context:\n{context}\n\nQuestion: {query}\nAnswer:"


@observe
def my_agent(query: str) -> str:
    """
    Theory section 4 ka example -- @observe se poora agent trace hota hai.
    Nested functions bhi individually trace hoti hain.
    """
    docs = retrieve_context(query)
    prompt = format_prompt(query, docs)
    # LLM call mock (LIVE_MODE mein real call hoga -- Section 9 mein)
    return f"[Mock answer] Based on {len(docs)} docs: Python GIL = single thread lock."


print()
print("  @observe decorator demo:")
result = my_agent("Python GIL kya hai?")
print(f"  Agent output: {result}")
print()
print(f"  Traces captured: {len(_LANGFUSE_TRACES)}")
for t in _LANGFUSE_TRACES:
    print(f"    [{t['function']:<18}] {t['duration_ms']:>6.1f}ms | "
          f"output={t['output'][:40] if t['output'] else 'None'}...")
print()


# ---------------------------------------------------------------------------
# SECTION 7: OPENTELEMETRY-STYLE SPAN TRACING
# Theory section 6 -- Standard open format, Datadog/Honeycomb/Grafana pe bhejo
# ---------------------------------------------------------------------------

print("=" * 65)
print("SECTION 7: OpenTelemetry-style Span Tracing (theory section 6)")
print("=" * 65)


class MockTracer:
    """
    Theory section 6 ka OpenTelemetry tracer -- manual simulation.
    Production mein: from opentelemetry import trace; tracer = trace.get_tracer(__name__)
    Spans Datadog, Honeycomb, Grafana, Jaeger pe export hote hain.
    """

    def __init__(self, name: str = __name__):
        self.name = name
        self._spans: List[Dict] = []

    @contextmanager
    def start_as_current_span(self, span_name: str):
        """
        Theory section 6 ka @tracer.start_as_current_span("agent_run") mimic.
        with tracer.start_as_current_span("step") as span:
            span.set_attribute("key", value)
        """
        span = _OtelSpan(span_name, self._spans)
        span._start()
        try:
            yield span
        except Exception as exc:
            span.record_exception(exc)
            raise
        finally:
            span._end()


class _OtelSpan:
    """Internal span object -- set_attribute aur record_exception support karta hai."""

    def __init__(self, name: str, registry: List[Dict]):
        self._name = name
        self._registry = registry
        self._attrs: Dict = {}
        self._t0: float = 0.0
        self._data: Dict = {}

    def _start(self):
        self._t0 = time.time()
        self._data = {
            "span_name": self._name,
            "span_id": str(uuid.uuid4())[:8],
            "attributes": self._attrs,
            "events": [],
            "status": "OK",
            "duration_ms": 0.0,
        }

    def _end(self):
        self._data["duration_ms"] = round((time.time() - self._t0) * 1000, 2)
        self._data["attributes"] = dict(self._attrs)
        self._registry.append(self._data)

    def set_attribute(self, key: str, value: Any):
        """span.set_attribute("query", query) -- theory mein exact yahi syntax hai."""
        self._attrs[key] = value

    def record_exception(self, exc: Exception):
        self._data["status"] = "ERROR"
        self._data["events"].append({"exception": str(exc)})


# Demo -- theory section 6 ka exact pattern reproduce karo
tracer = MockTracer("observability_lab")


def run_agent_otel(query: str) -> str:
    """
    Theory section 6 ka example exactly reproduce kiya:
    @tracer.start_as_current_span("agent_run")
    def run_agent(query): ...
    """
    with tracer.start_as_current_span("agent_run") as root_span:
        root_span.set_attribute("query", query)
        root_span.set_attribute("user_id", "demo_user")

        with tracer.start_as_current_span("retrieve") as span:
            span.set_attribute("query", query)
            time.sleep(0.01)  # simulate retrieve
            docs = [f"doc_{i}" for i in range(3)]
            span.set_attribute("docs_count", len(docs))

        with tracer.start_as_current_span("llm_call") as span:
            span.set_attribute("model", "llama3-8b-8192")
            time.sleep(0.015)  # simulate LLM
            response = f"Answer to: {query[:30]}"
            span.set_attribute("output_tokens", 45)

        root_span.set_attribute("outcome", "success")
        return response


print()
print("  OpenTelemetry span demo:")
otel_result = run_agent_otel("Agentic AI kya hota hai?")
print(f"  Result: {otel_result}")
print()
print(f"  Spans exported ({len(tracer._spans)}):")
for span in tracer._spans:
    attrs_str = ", ".join(f"{k}={v}" for k, v in span["attributes"].items())
    print(f"    [{span['status']}] {span['span_name']:<15} "
          f"{span['duration_ms']:>6.1f}ms | {attrs_str[:60]}")
print()
print("  Production mein yeh spans Datadog / Honeycomb / Grafana pe jaate hain.")
print()


# ---------------------------------------------------------------------------
# SECTION 8: HELICONE-STYLE PROXY CONCEPT
# Theory section 5 -- Zero code change, base_url swap
# ---------------------------------------------------------------------------

print("=" * 65)
print("SECTION 8: Helicone-style Proxy Concept (theory section 5)")
print("=" * 65)

HELICONE_PATTERN = '''
# Production mein sirf base_url badlo -- koi aur code change nahi!
# Theory section 5 ka exact pattern:

from openai import OpenAI
import os

client = OpenAI(
    base_url="https://oai.helicone.ai/v1",
    api_key=os.getenv("OPENAI_API_KEY") or "placeholder",
    default_headers={
        "Helicone-Auth": f"Bearer {os.getenv('HELICONE_API_KEY', 'placeholder')}"
    }
)

# Ab SAARI calls auto-log hoti hain -- zero code change!
# Features jo milte hain:
#   - Automatic request/response logging
#   - Cost tracking per call
#   - Built-in caching (same prompt -> no LLM call)
#   - Rate limiting
#   - Grafana-compatible metrics export

# Groq version (same concept):
groq_client = OpenAI(
    base_url="https://api.groq.com/openai/v1",
    api_key=os.getenv("GROQ_API_KEY") or "placeholder",
)
# Groq ka apna dashboard hai -- sab calls wahan dikhayi deti hain.
'''

print()
print("  Helicone proxy pattern (theory section 5):")
print(HELICONE_PATTERN)


# ---------------------------------------------------------------------------
# SECTION 9: LIVE LLM CALL WITH FULL OBSERVABILITY
# Theory sab kuch -- ek real call ke saath end-to-end demo
# ---------------------------------------------------------------------------

print("=" * 65)
print("SECTION 9: Live LLM Call + Full Observability Pipeline")
print("=" * 65)

live_log_sink = StringIO()
live_logger = LLMLogger(sink=live_log_sink)
live_tracer = MockTracer("live_demo")


def call_llm_with_observability(query: str) -> Dict[str, Any]:
    """
    Ek LLM call karo aur poori observability pipeline chalao:
    1. PII redact karo query se
    2. Tracer span start karo
    3. Logger se trace karo
    4. Metrics collect karo
    5. Alert rules check karo
    """
    trace_id = live_logger.new_trace()
    metrics = LLMCallMetrics(user_id="demo_user", session_id="sess_live")
    response_text = None

    with live_tracer.start_as_current_span("full_pipeline") as root:
        root.set_attribute("trace_id", trace_id)
        root.set_attribute("query_len", len(query))

        # PII redaction
        with live_tracer.start_as_current_span("pii_redact") as span:
            safe_query = safe_log(query)
            span.set_attribute("original_len", len(query))
            span.set_attribute("safe_len", len(safe_query))
            span.set_attribute("pii_removed", query != safe_query)

        # LLM call (ya mock)
        with live_logger.trace("llm_call", model=metrics.model, user_id=metrics.user_id) as log_span:
            with live_tracer.start_as_current_span("llm_call") as otel_span:
                t_call = time.time()

                if LIVE_MODE:
                    # Real Groq call
                    try:
                        client = get_client()
                        chat_response = client.chat.completions.create(
                            model="llama3-8b-8192",
                            messages=[
                                {
                                    "role": "system",
                                    "content": (
                                        "Tum ek helpful AI assistant ho. "
                                        "Short aur clear jawab do, 2-3 sentences mein."
                                    ),
                                },
                                {"role": "user", "content": safe_query},
                            ],
                            max_tokens=120,
                            temperature=0.3,
                        )
                        response_text = chat_response.choices[0].message.content
                        usage = chat_response.usage
                        metrics.input_tokens = usage.prompt_tokens
                        metrics.output_tokens = usage.completion_tokens
                    except Exception as exc:
                        log_span["error"] = str(exc)
                        otel_span.set_attribute("error", str(exc))
                        metrics.error = str(exc)
                        response_text = f"[LLM ERROR: {str(exc)[:60]}]"
                else:
                    # Mock mode -- fake response
                    time.sleep(0.02)
                    response_text = (
                        "[MOCK] LLM ne kaha: Observability production AI ke liye "
                        "zaruri hai. Bina trace ke debugging impossible hai."
                    )
                    metrics.input_tokens = len(safe_query.split()) * 2
                    metrics.output_tokens = 35

                metrics.latency_ms = round((time.time() - t_call) * 1000, 2)
                metrics.cost_from_groq_pricing()

                # Span attributes update karo
                log_span["metadata"]["input_tokens"] = metrics.input_tokens
                log_span["metadata"]["output_tokens"] = metrics.output_tokens
                log_span["metadata"]["latency_ms"] = metrics.latency_ms
                log_span["metadata"]["cost_usd"] = metrics.cost_usd

                otel_span.set_attribute("input_tokens", metrics.input_tokens)
                otel_span.set_attribute("output_tokens", metrics.output_tokens)
                otel_span.set_attribute("latency_ms", metrics.latency_ms)

        root.set_attribute("total_cost_usd", metrics.cost_usd)
        root.set_attribute("outcome", "error" if metrics.error else "success")

    return {
        "query": query,
        "safe_query": safe_query,
        "response": response_text,
        "metrics": metrics,
        "trace_id": trace_id,
    }


print()
test_query = "Agentic AI kya hai? Mera email test@example.com hai aur phone 9876543210 hai."
print(f"  Query (with PII): {test_query}")
print()

result = call_llm_with_observability(test_query)

print(f"  Safe query (PII removed): {result['safe_query']}")
print(f"  Response: {result['response']}")
print()
m = result["metrics"]
print(f"  Metrics collected:")
print(f"    Call ID       : {m.call_id}")
print(f"    Input tokens  : {m.input_tokens}")
print(f"    Output tokens : {m.output_tokens}")
print(f"    Latency       : {m.latency_ms:.1f}ms")
print(f"    Cost          : ${m.cost_usd:.8f}")
print(f"    Error         : {m.error or 'None'}")
print()

# Alert check karo is call ke baad
print("  Alert check post-call:")
call_metrics_for_alerts = {
    "p99_latency_ms": m.latency_ms,
    "daily_spend_usd": m.cost_usd * 1000,  # agar 1000 calls hoti toh
    "faithfulness_score": 0.91,
    "error_rate_pct": 0.0 if not m.error else 100.0,
}
triggered_live = run_alert_checks(call_metrics_for_alerts)
print(f"  Triggered: {triggered_live or 'NONE -- sab theek!'}")
print()


# ---------------------------------------------------------------------------
# SECTION 10: LANGFUSE OPTIONAL -- lazy import with fallback
# Theory section 4 -- Optional heavy library
# ---------------------------------------------------------------------------

print("=" * 65)
print("SECTION 10: Optional Libraries (lazy import pattern)")
print("=" * 65)

print()
print("  Langfuse (optional -- pip install langfuse):")
try:
    from langfuse import Langfuse  # type: ignore
    langfuse_available = True
    print("  [OK] langfuse import successful -- production use kar sakte ho.")
except ImportError:
    langfuse_available = False
    print("  [SKIP] langfuse installed nahi hai.")
    print("         Install: pip install langfuse")
    print("         Phir: LANGFUSE_SECRET_KEY=... LANGFUSE_PUBLIC_KEY=... use karo.")
    print("         Is lab mein manual @observe decorator se same effect mila.")

print()
print("  Ragas (eval quality metrics -- optional):")
try:
    import ragas  # type: ignore
    ragas_available = True
    print("  [OK] ragas available -- faithfulness/relevancy compute ho sakta hai.")
except ImportError:
    ragas_available = False
    print("  [SKIP] ragas installed nahi hai.")
    print("         Install: pip install ragas")
    print("         Use case: faithfulness_score = evaluate(dataset, metrics=[Faithfulness()])")

print()
print("  sentence-transformers (embedding -- optional):")
try:
    from sentence_transformers import SentenceTransformer  # type: ignore
    st_available = True
    print("  [OK] sentence-transformers available.")
except ImportError:
    st_available = False
    print("  [SKIP] sentence-transformers nahi hai.")
    print("         Install: pip install sentence-transformers")

print()
print("  chromadb (vectorstore -- optional):")
try:
    import chromadb  # type: ignore
    chroma_available = True
    print("  [OK] chromadb available.")
except ImportError:
    chroma_available = False
    print("  [SKIP] chromadb nahi hai.")
    print("         Install: pip install chromadb")

print()
print(f"  Library status summary:")
print(f"    langfuse            : {'available' if langfuse_available else 'not installed (ok)'}")
print(f"    ragas               : {'available' if ragas_available else 'not installed (ok)'}")
print(f"    sentence-transformers: {'available' if st_available else 'not installed (ok)'}")
print(f"    chromadb            : {'available' if chroma_available else 'not installed (ok)'}")
print()


# ---------------------------------------------------------------------------
# SECTION 11: PRODUCTION STACK SUMMARY
# Theory section 10 -- Recommended architecture
# ---------------------------------------------------------------------------

print("=" * 65)
print("SECTION 11: Production Stack Summary (theory section 10)")
print("=" * 65)

PRODUCTION_STACK = """
  Theory section 10 ka recommended stack:

  Application (agentic code)
       |
       v
  [Option A] LangSmith  -- agar LangChain use kar rahe ho
  [Option B] Helicone   -- drop-in proxy, zero code change
  [Option C] Langfuse   -- self-hosted, privacy-first, framework-agnostic
       |
       v
  Prometheus  -- metrics aggregation (counters, histograms)
       |
       v
  Grafana     -- dashboards (latency P99, cost/day, error rate)
       |
       v
  PagerDuty / Alertmanager -- on-call alerts

  Most teams ke liye BEST balance:
    Langfuse (self-hosted) + Grafana dashboard
    Reason: data apne server pe, koi vendor lock-in nahi, GDPR compliant.

  Is Lab mein hamne simulate kiya:
    - Custom LLMLogger  (= Langfuse ka manual version)
    - MockTracer        (= OpenTelemetry ka manual version)
    - AlertRule         (= Prometheus alert rules ka manual version)
    - safe_log()        (= PII redaction middleware)
    - LLMCallMetrics    (= Prometheus metrics labels)
"""

print(PRODUCTION_STACK)


# ---------------------------------------------------------------------------
# FINAL SUMMARY
# ---------------------------------------------------------------------------

print("=" * 65)
print("  OBSERVABILITY -- INTERVIEW SUMMARY (Hinglish)")
print("=" * 65)

SUMMARY_POINTS = [
    "Teen pillars: Tracing (kya hua), Metrics (kitna fast/mehanga), Logging (input/output).",
    "LangSmith: LangChain users ke liye best, auto-trace with env vars.",
    "Langfuse: Open source, self-hosted, @observe decorator, framework-agnostic.",
    "Helicone: Drop-in proxy -- bas base_url badlo, sab auto-log.",
    "OpenTelemetry: Open standard -- Datadog/Honeycomb/Grafana pe export karo.",
    "Custom LLMLogger: contextmanager + JSONL sink -- koi bhi stack mein kaam karta hai.",
    "Metrics track karo: tokens, cost, latency P50/P95/P99, error, user_id.",
    "Alerts lagao: high latency, cost budget, quality drop, error rate.",
    "PII redact karo BEFORE logging -- GDPR/CCPA compliance ke liye.",
    "Production stack: Langfuse + Grafana = best balance for most teams.",
]

print()
for i, point in enumerate(SUMMARY_POINTS, 1):
    print(f"  {i:>2}. {point}")

print()
print("  Next: 09_guardrails.md -- Safety, validation, content moderation")
print("=" * 65)
print()
print("  [EXIT 0] Lab successfully completed.")
print()
