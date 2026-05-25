# Level 8 — Doc 8: Observability (LangSmith / Langfuse / Helicone) ⭐

> **Goal:** Production AI = visibility into every LLM call. Trace, debug, monitor, alert.

---

## 1. Why Observability Matters

LLM apps are **black boxes** by default:
- Why did agent give wrong answer?
- Where did latency spike?
- Which prompt version performs best?
- Are we within cost budget?

Without observability, debugging is impossible.

---

## 2. Three Pillars

| Pillar | Question Answered |
|---|---|
| **Tracing** | Step-by-step what happened |
| **Metrics** | How fast/expensive/accurate? |
| **Logging** | What was input/output? |

---

## 3. LangSmith (LangChain's)

**Best for:** LangChain/LangGraph users

### Setup
```bash
pip install langsmith
export LANGCHAIN_API_KEY=ls__...
export LANGCHAIN_TRACING_V2=true
export LANGCHAIN_PROJECT=my-agent
```

That's it. Any LangChain code now auto-traces.

### What you see
```
Agent Run #abc123
├── retrieve_docs (200ms, $0.0001)
├── llm_call (1500ms, $0.001)
│   ├── system: "You are..."
│   ├── user: "What is..."
│   └── output: "..."
├── tool_call: search (500ms)
└── llm_call (800ms, $0.0005)

Total: 3.0s, $0.0016
```

### Features
- Full trace tree
- Cost per step
- Inputs/outputs visible
- Compare runs side-by-side
- Add to eval datasets
- Online + offline evaluation

---

## 4. Langfuse (Open Source)

**Best for:** Self-hosting, privacy, framework-agnostic

```python
from langfuse import Langfuse
langfuse = Langfuse()

@langfuse.observe()
def my_agent(query):
    # Decorate functions — auto-traces
    response = llm.call(query)
    return response
```

### Features
- Self-hosted (data stays internal)
- Works with any LLM provider
- Cost tracking
- Prompt management
- Eval framework built-in
- Score user feedback

---

## 5. Helicone

**Best for:** Drop-in proxy, no code changes

```python
# Just change base URL
from openai import OpenAI
client = OpenAI(
    base_url="https://oai.helicone.ai/v1",
    default_headers={"Helicone-Auth": f"Bearer {os.getenv('HELICONE_API_KEY')}"}
)

# Now all calls auto-logged
```

### Features
- Zero code changes
- Logs all OpenAI/Anthropic calls
- Cost tracking
- Caching (built-in)
- Rate limiting

---

## 6. OpenTelemetry (Open Standard)

Most production stacks use OpenTelemetry:

```python
from opentelemetry import trace
tracer = trace.get_tracer(__name__)

@tracer.start_as_current_span("agent_run")
def run_agent(query):
    with tracer.start_as_current_span("retrieve") as span:
        span.set_attribute("query", query)
        docs = retrieve(query)
        span.set_attribute("docs_count", len(docs))
    
    with tracer.start_as_current_span("llm_call"):
        response = llm.call(query, docs)
    
    return response
```

Send to: Datadog, Honeycomb, Grafana, Jaeger.

---

## 7. Custom Logging Pattern

If you don't use frameworks:

```python
import json
import time
import uuid
from contextlib import contextmanager

class LLMLogger:
    def __init__(self, sink):
        self.sink = sink  # JSON file, database, etc.
    
    @contextmanager
    def trace(self, name: str, **metadata):
        span_id = str(uuid.uuid4())
        start = time.time()
        record = {
            "span_id": span_id,
            "trace_id": getattr(self, "current_trace", span_id),
            "name": name,
            "start_time": start,
            "metadata": metadata
        }
        try:
            yield record
        except Exception as e:
            record["error"] = str(e)
            raise
        finally:
            record["duration_ms"] = (time.time() - start) * 1000
            self.sink.write(json.dumps(record) + "\n")

# Usage
logger = LLMLogger(sink=open("logs.jsonl", "a"))

with logger.trace("agent_run", user_id="u123"):
    with logger.trace("retrieve") as r:
        docs = retrieve(query)
        r["metadata"]["docs_count"] = len(docs)
    
    with logger.trace("llm_call") as r:
        response = llm.call(query)
        r["metadata"]["tokens"] = response.usage.total_tokens
```

---

## 8. Metrics to Track

### Per LLM call
- Model used
- Input tokens, output tokens
- Cost
- Latency (P50, P95, P99)
- Error type (if any)
- User ID / Session ID

### Per Agent Run
- Total cost
- Total latency
- Number of tool calls
- Final outcome (success/error/timeout)
- Number of iterations

### Quality (from eval)
- Faithfulness
- Answer relevancy
- User thumbs up/down

---

## 9. Alerting

```python
# Use Prometheus + Grafana, or proprietary
alerts = [
    {
        "name": "high_latency",
        "condition": "p99_latency > 5s for 5 min",
        "action": "page_oncall"
    },
    {
        "name": "cost_budget",
        "condition": "daily_spend > $100",
        "action": "notify_team"
    },
    {
        "name": "quality_drop",
        "condition": "faithfulness < 0.8",
        "action": "alert_engineering"
    },
    {
        "name": "error_rate",
        "condition": "error_rate > 1%",
        "action": "page_oncall"
    },
]
```

---

## 10. Production Stack (Recommended)

```
Application
   ↓
LangSmith (if using LangChain) — automatic
OR
Helicone (drop-in) + custom OpenTelemetry
   ↓
Prometheus (metrics aggregation)
Grafana (dashboards)
PagerDuty (alerts)
```

For most teams: **Langfuse self-hosted** + **Grafana dashboard** is great balance.

---

## 11. Privacy Considerations

Logging user data has implications:
- GDPR / CCPA compliance
- PII redaction before logging
- Retention policies (delete after 30 days?)
- User opt-in for "improve service"

```python
def safe_log(text):
    # Redact emails, phones, etc.
    text = re.sub(r'[\w.+-]+@[\w-]+\.[\w.-]+', '[EMAIL]', text)
    text = re.sub(r'\b\d{10,}\b', '[PHONE]', text)
    text = re.sub(r'\b\d{16}\b', '[CARD]', text)
    return text
```

---

## 12. Key Takeaways

✅ Observability is **non-negotiable** for production AI
✅ LangSmith (best for LangChain), Langfuse (open source), Helicone (drop-in)
✅ Trace: full step-by-step. Metrics: aggregates. Logs: details.
✅ Track: tokens, cost, latency, quality, errors
✅ Set alerts on critical metrics
✅ Redact PII before logging
✅ Most teams: Langfuse + Grafana stack works well

**Next:** [09_guardrails.md](09_guardrails.md) — Safety, validation, content moderation
