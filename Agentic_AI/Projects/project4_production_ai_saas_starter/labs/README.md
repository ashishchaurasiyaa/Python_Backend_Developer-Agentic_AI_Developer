# Labs — deploying the triage agent (trimmed MVP)

This is the build plan for turning `project4_production_ai_saas_starter` from
a CLI-only agent into a real, internet-reachable, deployed service. Everything
in `app/agent/`, `app/guardrails.py`, `app/observability/`, and `app/evals/`
already works and stays untouched — these labs only add a way to reach it.

**Scope decision:** this is the trimmed deploy-first MVP, not the full mini-SaaS
described in `../../04_project4_production_ai_saas.md`. Multi-tenant Postgres,
Stripe billing, Redis semantic cache, and the LiteLLM multi-provider router are
all deliberately deferred — see "Out of scope" at the bottom. The goal here is
"this agent is measured and guarded in production," not "this is a billing
platform."

**Format:** each lab has a Goal, a Task (what you write), a Verify step that is
genuinely self-checking (pass/fail, not "looks right"), and SOCH (reasoning)
questions to answer before moving on — same template as `07_Kafka/labs/`,
`09_Celery/labs/`, `08_Redis/labs/` elsewhere in this repo. Labs are sequential.

## Checklist

- [ ] Lab 0 — Baseline (confirm existing eval/reliability/mutation all green)
- [ ] Lab 1 — FastAPI HTTP surface (`/healthz`, `/v1/triage`)
- [ ] Lab 2 — API-key auth + rate limiting
- [ ] Lab 3 — Live evals + cost endpoint (`/v1/evals`, `/v1/stats`)
- [ ] Lab 4 — Containerize (Dockerfile + docker-compose)
- [ ] Lab 5 — Deploy to Fly.io (public HTTPS URL)
- [ ] Lab 6 — Gate the deploy on the existing quality bar

---

## Lab 0 — Baseline (no new code)

**Goal:** Confirm what already works before adding anything, so a later bug is
provably new, not pre-existing.

**Task:** none — just run, from `project4_production_ai_saas_starter/`:
```bash
pip install anthropic pydantic pytest fastapi "uvicorn[standard]"
python main.py --provider stub eval
python main.py --provider stub reliability --runs 8
python main.py mutation
```

**Verify:** `eval` reports 16/16 cases, `reliability` reports 8/8 all-pass
rounds, `mutation` reports 0 unexplained survivors. If any of these don't hold
on your machine right now, fix that first — every lab after this assumes a
green baseline.

**SOCH:** Why does the stub backend exist at all — what would break about
"reproducible eval numbers in CI" if every eval run cost real API money?

---

## Lab 1 — FastAPI HTTP surface

**Goal:** Turn the CLI-only agent into something reachable over HTTP, with
zero changes to the agent/eval/guardrail code underneath.

**New file:** `app/api/http.py`
- `POST /v1/triage` — body `{"ticket": str}`, calls the existing `triage()`
  from `app/agent/triage.py`, returns
  `{"result": TriageResult, "trace_id", "cost_usd", "latency_ms", "violations": [...]}`
  on success.
- `GET /healthz` — returns `{"status": "ok", "provider": <backend name>}`.
  This becomes the Fly.io health-check target in Lab 5.
- Reuse `get_backend()` from `app.llm` exactly as `main.py` does — the HTTP
  layer must stay as provider-agnostic as the CLI is.

**Task (TODO — fill this in):**
1. Map `InputRejected`-shaped failures (`run.error` starting with
   `"input_rejected"`) to HTTP 400, `AgentError`-shaped failures
   (`max_steps_exceeded`, `unparseable_output`, `model_refusal`) to HTTP 502,
   anything else to 500.
2. Add a pydantic request model that caps ticket length on the read side too
   (defense in depth — `guard_input` already caps it, this just fails fast
   with a clean 422 instead of running the agent first).

**Also:** create `app/api/__init__.py` (empty, matching `app/agent/__init__.py`),
and add a "Run the HTTP server" line to the project README's "Run it" section.

**Verify:**
```bash
uvicorn app.api.http:app --port 8000 &
curl -s localhost:8000/healthz | python -m json.tool
curl -s -X POST localhost:8000/v1/triage -H 'content-type: application/json' \
  -d '{"ticket": "Where is my order A1002?"}' | python -m json.tool
curl -s -X POST localhost:8000/v1/triage -d '{"ticket": ""}' -w '\n%{http_code}\n'
```
PASS = healthz returns 200, a real ticket returns a category/priority/draft_reply,
an empty ticket returns a 4xx (not a 500, not a hang).

**SOCH:**
- Why does `InputRejected` deserve a 400, not a 500 — what's the difference in
  what each status code promises to a caller?
- The agent loop can take several seconds (multiple model calls). What does
  that mean for `uvicorn`'s worker model if two tickets arrive at once — do
  you need `async def` here, and if not yet, when would you?

---

## Lab 2 — API-key auth + rate limiting (deliberately simple, not multi-tenant)

**Goal:** Nobody should be able to spend your API budget by finding the URL.
Scope is intentionally NOT the spec's Postgres-backed multi-tenant system —
one shared list of valid keys is enough to prove the pattern.

**New file:** `app/api/auth.py`
- Read a comma-separated list of valid keys from env var `API_KEYS`
  (e.g. `API_KEYS=devkey1,devkey2`).
- A FastAPI dependency `require_api_key(x_api_key: str = Header(...))` that
  401s on a missing/invalid key.
- A simple **in-memory fixed-window rate limiter** keyed by API key: N
  requests per 60s (a small `dict[str, list[float]]` of timestamps — no
  Redis, that's deferred scope). 429 with a `Retry-After` header when
  exceeded.

**Task (TODO — fill this in):** the rate-limit check function itself — given
a key and a window, decide allow/deny and prune old timestamps. Wire it as a
second dependency on `/v1/triage` (not on `/healthz` — Fly's health checks
must never be rate-limited).

**Verify:**
```bash
for i in $(seq 1 12); do
  curl -s -o /dev/null -w "%{http_code} " -X POST localhost:8000/v1/triage \
    -H 'x-api-key: devkey1' -d '{"ticket":"test"}'
done
```
PASS = the first N (your configured limit) return 200/4xx-from-agent, the rest
return 429. Also verify a request with no `x-api-key` header returns 401, and
one with a wrong key also returns 401.

**SOCH:**
- Why does this rate limiter silently stop working correctly the moment you
  run two `uvicorn` processes (or two Fly machines)? What's the one-line fix
  if this had to scale — and where does that fix already exist elsewhere in
  your repo? *(hint: `08_Redis/labs/04_sliding_window_rate_limiter`)*
- Why 401 for a bad key but 429 for too many requests, not the other way round?

---

## Lab 3 — Live evals + cost endpoint

**Goal:** Make the eval/reliability numbers and running cost visible over
HTTP, not just in a local Markdown report — this is what turns "I built an
agent" into "here's a live URL that proves it's measured."

**New file:** `app/api/dashboard.py`
- `GET /v1/evals` — runs `run_eval()` from `app.evals.runner` on demand
  against the current backend, returns the JSON summary
  (`cases_passed/cases_total`, `cost_per_case`, `p50_ms`/`p95_ms`). Gate this
  behind the same `require_api_key` dependency — it spends real money against
  a real backend.
- `GET /v1/stats` — reads `traces/traces.jsonl` (written by every
  `/v1/triage` call already, via `Trace.write()` — no new instrumentation
  needed), and aggregates: total requests, total cost, error rate, over the
  last N lines. No new database — the trace file already IS the data source.

**Task (TODO — fill this in):** the aggregation function for `/v1/stats` —
read the JSONL, compute
`{"requests": n, "total_cost_usd": ..., "error_rate": ..., "avg_latency_ms": ...}`.

**Verify:**
```bash
curl -s localhost:8000/v1/evals -H 'x-api-key: devkey1' | python -m json.tool
curl -s -X POST localhost:8000/v1/triage -H 'x-api-key: devkey1' -d '{"ticket":"Where is A1001?"}'
curl -s localhost:8000/v1/stats -H 'x-api-key: devkey1' | python -m json.tool
```
PASS = `/v1/evals` reports `cases_passed == cases_total` on stub, `/v1/stats`
shows the request count went up and `total_cost_usd > 0` after the triage call.

**SOCH:** Why read `/v1/stats` straight from the existing trace JSONL instead
of adding a database table for it right now? At what point (what usage
volume, or what query you'd want to run) would that stop being good enough —
and which of the spec's deferred milestones is the actual fix?

---

## Lab 4 — Containerize

**Goal:** Package the MVP as one image, small, with exactly the dependencies
this trimmed scope actually needs — not the full spec's `requirements.txt`.

**New file:** `requirements-mvp.txt` — trimmed to `anthropic`, `pydantic`,
`fastapi`, `uvicorn[standard]`. (`requirements.txt` stays as-is, documenting
the full-spec deps for whenever those milestones get built later — add a
one-line comment at its top pointing at `requirements-mvp.txt` for what's
actually running today.)

**New file:** `Dockerfile` — `python:3.12-slim` base, `COPY` + `pip install -r
requirements-mvp.txt`, `CMD ["uvicorn", "app.api.http:app", "--host",
"0.0.0.0", "--port", "8080"]`.

**New file:** `docker-compose.yml` — one service, `env_file: .env` (for
`ANTHROPIC_API_KEY` and `API_KEYS`), port `8080:8080`. For local verification
before touching Fly at all.

**Verify:**
```bash
docker compose up --build -d
curl -s localhost:8080/healthz
docker compose logs --tail 20
docker compose down
```
PASS = the containerized service answers `/healthz` identically to the bare-
`uvicorn` run in Lab 1, with no import errors in the logs.

**SOCH:** What's in `requirements.txt` that you deliberately left out of the
image, and why would including it (litellm, sqlalchemy, asyncpg, stripe,
openai) make the image bigger for zero benefit *right now*?

---

## Lab 5 — Deploy to Fly.io

**Goal:** A public HTTPS URL that anyone (an interviewer included) can hit,
live.

**New file:** `fly.toml` (generated by `fly launch --no-deploy`, then edit:
health check path `/healthz`, internal port `8080`).

**Task:**
1. `fly secrets set ANTHROPIC_API_KEY=... API_KEYS=...` — never in `fly.toml`
   or the image itself.
2. `fly deploy`.
3. Confirm the free-tier machine's `auto_stop_machines`/`auto_start_machines`
   behavior (it will sleep on idle) — decide, and note here, whether that's
   acceptable for a demo link or worth a `min_machines_running = 1`.

**Verify (from your own machine, not localhost):**
```bash
curl -s https://<your-app>.fly.dev/healthz
curl -s -X POST https://<your-app>.fly.dev/v1/triage -H 'x-api-key: ...' -d '{"ticket":"Where is A1001?"}'
```
PASS = both work from the public internet, with `--provider anthropic` active
(real model, real cost — check `/v1/stats` shows a non-zero `total_cost_usd`
after this).

**SOCH:** Your eval report already measured p50/p95 latency under the stub.
On a scaled-to-zero Fly machine, what does the *first* request after idle
look like compared to that number — and why does that matter if this URL is
what an interviewer clicks?

---

## Lab 6 — Gate the deploy on the existing quality bar

**Goal:** Close the loop — the project README already says "a number you
cannot break is not a measurement" (that's what the mutation suite proved).
Make that bar a condition of shipping, not just a thing that's true in a
local terminal.

**New file:** `scripts/predeploy_check.sh`
```bash
#!/usr/bin/env bash
set -euo pipefail
python main.py --provider stub eval
python main.py --provider stub reliability --runs 8
python main.py mutation
echo "All quality gates passed — safe to fly deploy."
```

**Task:** run this script before every `fly deploy` by hand for now;
optionally wire it as a GitHub Actions workflow
(`.github/workflows/predeploy.yml`) that runs on push, as a stretch goal —
not required to call this project deployed.

**Verify:** deliberately break something (e.g. comment out the
`get_refund_policy` call requirement in `guard_output`) and confirm
`predeploy_check.sh` exits non-zero and says which case/assertion failed —
the mutation-suite discipline applied to the deploy gate itself.

**SOCH:** This script would have caught the exact bug the mutation suite
found earlier (output-side PII redaction never exercised) *before* it
reached the deployed URL. What's the cost difference between catching that
locally vs. an interviewer hitting it on the live link?

---

## Out of scope (deliberately deferred)

Do not build in this pass, even though `../../04_project4_production_ai_saas.md`
describes them: multi-tenant Postgres + `Tenant` model, Stripe subscriptions
and webhooks, Redis-backed rate limiting/token budgets, semantic cache,
LiteLLM multi-provider router, admin revenue dashboard. These stay on the
project README's "Not built yet" list as *future* milestones on top of a
project that is already deployed — not blockers to calling it deployed.

## End-to-end verification (after all 6 labs)

1. Every lab's checkbox above is ticked.
2. `python main.py --provider stub eval|reliability|mutation` all still pass
   (nothing in `app/agent`, `app/guardrails.py`, `app/evals`,
   `app/observability` was modified).
3. `docker compose up` serves `/healthz` locally.
4. The public Fly.io URL answers `/healthz` and `/v1/triage` with a real
   Anthropic-backed response.
5. `/v1/stats` on the live URL shows non-zero real cost after a few real
   requests — this is the artifact worth linking in a resume/interview, not
   the code alone.
