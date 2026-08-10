# Project 4 — Production AI SaaS

A support-ticket triage agent, built to the standard the market actually hires
for: not "it works in the demo", but **it is measured, guarded, traced, and it
still works on run number eight**.

Spec file: [../04_project4_production_ai_saas.md](../04_project4_production_ai_saas.md)

---

## Why this shape

Independent 2026 research puts the failure rate for agentic AI initiatives
between 77% and 95%; roughly 88% of agent proofs-of-concept never reach broad
production. The cause is almost never the model. It is missing evaluation
criteria, unscoped permissions, no monitoring, and demos that hide degradation
— a system at ~60% single-run success drops to ~25% measured over eight
consecutive runs at production load.

So the scarce work is not the SaaS plumbing. It is the four things below, and
they are what got built first.

| Concern | Where it lives |
|---|---|
| Evaluation | [`app/evals/dataset.py`](app/evals/dataset.py), [`runner.py`](app/evals/runner.py) |
| Consecutive-run reliability | [`app/evals/reliability.py`](app/evals/reliability.py) |
| Guardrails (input + output) | [`app/guardrails.py`](app/guardrails.py) |
| Tracing, tokens, cost, latency | [`app/observability/trace.py`](app/observability/trace.py) |
| Does the eval suite actually work? | [`app/evals/mutation.py`](app/evals/mutation.py) |

---

## Run it

No API key needed — the eval suite runs against a deterministic stub backend so
it is reproducible in CI and costs nothing.

```bash
pip install anthropic pydantic pytest
```

```bash
python main.py --provider stub eval
```

```bash
python main.py --provider stub reliability --runs 8
```

```bash
python main.py mutation
```

```bash
python main.py demo "Please refund order A1003, I want my money back."
```

With `ANTHROPIC_API_KEY` set, every command runs against Claude Opus 5 instead
— same harness, same assertions, real numbers.

---

## Current numbers

Produced by `python main.py --provider stub eval` and
`reliability --runs 8`. Full reports in [`reports/`](reports/).

| Metric | Value |
|---|---|
| Cases passed | 16/16 |
| Assertions passed | 55/55 |
| Consecutive all-pass rounds | 8/8 |
| Cases passing every single run | 16/16 |
| Non-deterministic outputs | 0 |
| Unit tests | 11 passed |
| Mutants caught by the eval suite | 4/6, 2 covered by unit tests, **0 unexplained survivors** |

**Read these honestly.** They are stub-backend numbers: they measure the
harness, the guardrails, and the agent's control flow — not model quality.
Cost and latency under the stub are synthetic and labelled as such in the
report. Model-quality numbers require an API key and a paid run; the harness
that produces them is the deliverable here.

---

## The agent

Support ticket in → classification, priority, order id, escalation flag, and a
drafted customer reply out, validated against a JSON schema on both sides of
the wire.

```
ticket
  → guard_input        size cap · PII redaction · injection detection
  → agent loop         Claude Opus 5 + tools, max 6 steps, one repair retry
      ├─ lookup_order        (read-only)
      └─ get_refund_policy   (read-only)
  → guard_output       schema · refund rules · PII · escalation
  → TriageResult + Trace
```

Two design decisions worth defending in an interview:

**Every tool is read-only.** The agent can look things up; it cannot move
money. Issuing a refund is a human action gated by `needs_human`, and the
output guard forces that flag on whenever the model tries to skip it.

**Guardrails repair rather than block.** A support reply routed to a human is a
better failure mode than no reply. Every repair is recorded as a violation on
the trace, so a model regression shows up as a spike in a counter instead of as
silently worse answers.

---

## Why there is a mutation suite

An eval suite reporting 100% is worthless until you know it can report
something else. `python main.py mutation` breaks the agent on purpose — one
defect at a time — and asserts the suite notices.

The first run of it found a genuine hole: **output-side PII redaction was never
exercised**, because the input guard strips emails before the model ever sees
them. That path is now covered by
[`tests/test_guardrails.py`](tests/test_guardrails.py), and the mutant is
recorded as an expected survivor pointing at the test that covers it.

That finding is the point. A number you cannot break is not a measurement.

---

## Not built yet

Deliberately deferred, because it is the part that proves the least — standard
backend work rather than agent work:

| # | Milestone | Status |
|---|---|---|
| 1 | Multi-tenant DB model + API key hashing | todo |
| 2 | Auth middleware: API key → Tenant (Redis cache) | todo |
| 3 | Rate limiting per tier (sliding window, Redis INCR) | todo |
| 4 | Token budget enforcement before the LLM call | todo |
| 5 | LiteLLM router with provider fallback | todo |
| 6 | Semantic cache (Redis + cosine similarity) | todo |
| 7 | FastAPI surface over the triage agent | todo |
| 8 | Stripe subscription + webhook handler | todo |
| 9 | Admin dashboard API (MRR, usage, top spenders) | todo |
