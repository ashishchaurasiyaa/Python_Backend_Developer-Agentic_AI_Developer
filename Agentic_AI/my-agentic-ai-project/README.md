# my-agentic-ai-project

> **Backend Developer (4.3 YOE) → Agentic AI Engineer** ka hands-on build repo. Sab kuch yahan
> `uv run` se offline/local chalta hai — koi cloud key mandatory nahi, jab tak "real AWS deploy"
> na karo.

Agar poochha jaaye **"kuch build kiya hai jo dikha sako?"** — jawaab **ALEX** hai, neeche.

---

## The flagship project — ALEX (Agentic Learning Equities eXplainer)

Ek **multi-agent financial planner**: user apni holdings deta hai, 4 specialized agents
collaborate karke ek concentration-risk + rebalancing recommendation banate hain.

```
                    ┌──────────────────┐
   FinancialProfile │  PlannerAgent    │  goal + light profile-summary
   (holdings, age,  │  (decides what   │  ──────────────► analysis sub-tasks
    risk appetite)  │  to analyze)     │
                    └────────┬─────────┘
                             │ typed PlannerOutput
                 ┌───────────┴────────────┐
                 ▼                        ▼
        ┌─────────────────┐      ┌─────────────────┐
        │ PortfolioAnalyst │      │   RiskAgent      │
        │ (full holdings + │      │ (full holdings + │
        │  plan → alloc %) │      │  analyst output)  │
        └────────┬─────────┘      └────────┬─────────┘
                  │ AnalystOutput           │ RiskOutput
                  └───────────┬─────────────┘
                               ▼
                     ┌───────────────────┐
                     │ SynthesizerAgent   │  merges all upstream
                     │ (final rebalance   │  structured outputs
                     │  recommendation)   │
                     └───────────────────┘
```

**Where the code lives:**
[`Udemy_EdDonner_ProductionTrack/Week4_MultiAgent_Observability_AgentCore/Practical/`](Udemy_EdDonner_ProductionTrack/Week4_MultiAgent_Observability_AgentCore/Practical/)
— 6 labs, ~4,700 lines, each independently `uv run`-able and exit-0 with zero cloud creds.

| Lab | What it actually builds |
|---|---|
| `lab1_alex_multiagent_financial_planner.py` | The core orchestration above — 4 agents, typed Pydantic handoffs, in-process `Tracer` |
| `lab2_aurora_data_layer.py` | `ProfileRepository` abstraction — Aurora Serverless v2 (RDS Data API) in prod, stdlib `sqlite3` locally, same interface either way |
| `lab3_package_deploy_agent_lambda.py` | The planner wrapped as a real `lambda_handler(event, context)`, packaged for API Gateway v2 proxy integration, Terraform-provisioned |
| `lab4_observability_tracing_judge.py` | Span-based tracing (Langfuse in prod, structured-JSON `LocalTracer` offline) + an LLM-as-a-Judge quality eval |
| `lab5_security_guardrails_prompt_injection.py` | `guarded_agent()` — INPUT guardrail (prompt-injection/jailbreak detection + PII redaction) → LLM call → OUTPUT guardrail |
| `lab6_agentcore_loop_agent.py` | A ReAct-style think→tool→observe loop, runnable standalone or on Bedrock AgentCore's managed runtime |

### Why this shape (the design decisions, not just the components)

- **Multi-agent, not one long prompt** — split happens only where a sub-task's quality needs to
  be measured and improved independently (risk assessment vs allocation math are genuinely
  different skills). Golden rule followed: start with one call, measure, split only when a
  metric says to — not by default.
- **Typed Pydantic handoffs, not free-text between agents** — Synthesizer needs Analyst's
  `top_holding_pct` as a `float` it can threshold against, not a paragraph to re-parse. This is
  the same "structured output = production trust" argument as
  [`Level7_Frameworks/08_pydantic_ai.md`](../Level7_Frameworks/08_pydantic_ai.md)'s validate-and-retry
  loop, applied at the agent-to-agent boundary instead of the model-output boundary.
- **Context engineering per agent, deliberately** — Planner gets a light summary (decide what to
  analyze), Analyst/Risk get full holdings (need the numbers), Synthesizer gets everyone's
  structured output (needs to merge). Nobody gets more context than their task requires.
- **Repository pattern for the data layer** (`ProfileRepository` in lab2, `PortfolioRepository`
  in lab3) — same interface, swappable backend (`AuroraDataApiBackend` vs stdlib `sqlite3`). This
  is deliberately the same pattern taught in
  [`Backend_Developer/.../15_Design_Patterns_SOLID`](../../Backend_Developer/01_Year3-4_Mid/15_Design_Patterns_SOLID/),
  applied to an agent's data access instead of a Django/FastAPI app's.
- **Offline-first, graceful degrade everywhere** — every heavy dependency (`boto3`, `langfuse`,
  the LLM client itself) is a lazy import wrapped in try/except. No key → deterministic templated
  stub output, same typed shape, `exit 0`. This is why every lab runs free and the orchestration
  *shape* stays visible to inspect even with zero cloud access.

### Deployed shape (when it's not running local/offline)

```
Client → API Gateway v2 (HTTP API, POST /plan, throttled burst 20 / rate 10)
            → Lambda (planner_exec role, aws_lambda_function.planner)
                → runs the lab1 agent graph (Bedrock via LiteLLM in prod)
                → reads/writes via Aurora Serverless v2 (RDS Data API, lab2)
                → every agent call traced to Langfuse (spans + LLM-as-Judge, lab4)
                → wrapped in the guardrail layer (lab5) before touching the user
        (lab6 variant: same agent loop, running on Bedrock AgentCore's managed runtime instead)
```

Provisioned via Terraform in
[`Practical/terraform/`](Udemy_EdDonner_ProductionTrack/Week4_MultiAgent_Observability_AgentCore/Practical/terraform/)
— IAM role + policy, CloudWatch log group, the Lambda function, and the full API Gateway v2
integration/route/stage chain.

**Cost discipline is part of the design, not an afterthought:** Aurora Serverless v2 bills
per-ACU-hour *even at minimum capacity, even idle* (~$43/mo for a forgotten 0.5-ACU cluster) —
the runbook below treats "delete/pause the cluster same-day" as a hard rule, not a suggestion.
That's a real production instinct worth stating out loud in an interview, not just a cost table.

### Run it

```bash
# Everything below is $0 — no LLM key needed, no AWS, no langfuse. Deterministic stubs, exit 0.
uv run Udemy_EdDonner_ProductionTrack/Week4_MultiAgent_Observability_AgentCore/Practical/lab1_alex_multiagent_financial_planner.py
```

Full walkthrough, real-AWS deploy steps, and the per-service cost/teardown table:
[`Practical/PRACTICAL_RUNBOOK.md`](Udemy_EdDonner_ProductionTrack/Week4_MultiAgent_Observability_AgentCore/Practical/PRACTICAL_RUNBOOK.md).

---

## Everything else in this repo

ALEX is the thing to lead with in an interview; everything below is the course-work it grew out
of — useful as supporting depth, not the headline.

| Folder | What it is |
|---|---|
| [`Udemy_EdDonner_Course/`](Udemy_EdDonner_Course/) | Weeks 1–6 foundations: OpenAI Agents SDK, CrewAI, LangGraph, AutoGen, MCP |
| [`Udemy_EdDonner_ProductionTrack/`](Udemy_EdDonner_ProductionTrack/) | Weeks 1–4 production skills — Vercel/AWS/Docker, Serverless+Terraform+CI/CD, multi-cloud/SageMaker, and Week 4 = ALEX above |
| [`generativeai/langchain/`](generativeai/langchain/), [`generativeai/rag/`](generativeai/rag/) | Smaller standalone LangChain + RAG practice scripts (01–08, incl. a PDF chatbot and a research assistant) |
| [`KrishNaik_AgenticAI_NewTopics/`](KrishNaik_AgenticAI_NewTopics/) | Notes on newer 2026 topics — LangChain v1, vectorless RAG, deep agents, LLM gateways |
| `NOTES.md`, `COMPLETE_SEQUENCE.md`, `4_DAY_PRACTICE_PLAN.md` | Personal learning log / course sequencing — process notes, not project docs |
