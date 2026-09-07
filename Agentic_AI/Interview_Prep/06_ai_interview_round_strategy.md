# AI/GenAI Interview Round Strategy — the Meta-Game

> This isn't another question list — [`01_system_design_ai_questions.md`](01_system_design_ai_questions.md) and [`02_coding_patterns.md`](02_coding_patterns.md) are that. This is **how the round is actually run and scored**: the formats specific to AI/GenAI roles, what's being evaluated underneath the code, and the failure modes that sink otherwise-strong candidates in this specific kind of interview.

---

## 1. AI/GenAI rounds don't look like plain backend rounds

A generic backend DSA/system-design loop and an AI-role loop overlap, but AI roles add formats that don't exist elsewhere:

| Format | What it actually is | What's different from a plain backend round |
|---|---|---|
| **Live RAG/agent build** | 45–60 min: build a small retrieval or tool-calling pipeline live, usually with a starter repo | You're evaluated on prompt/context design choices, not just code correctness — a working-but-badly-prompted solution scores lower than a well-reasoned one |
| **Take-home eval build** | Given a dataset + a task, build an eval harness and report metrics | Interviewers read your **eval design**, not just your model/pipeline — "how do you know it's working" is the real question |
| **Whiteboard AI system design** | Design a RAG chatbot / agent platform / LLM cost-monitoring system | Same estimation skills as backend HLD, plus token/cost math, latency-vs-quality trade-offs, and hallucination mitigation — see [`01_system_design_ai_questions.md`](01_system_design_ai_questions.md) for worked examples |
| **Prompt/context review** | You're shown a system prompt or agent harness and asked to find the bug | Tests whether you can read prompts like code — spot ambiguous instructions, missing constraints, or context-window mismanagement |

**Ask the recruiter which of these you'll get** — it's a completely reasonable question, and pacing a take-home-eval mindset into a 45-minute live-build round (or vice versa) wastes the time you have.

---

## 2. What's actually being scored in a live RAG/agent build

The same four-axis rubric as a plain coding round applies (problem-solving, code quality, communication, verification — see the Backend track's [`03_dsa_round_strategy.md`](../../Backend_Developer/03_Interview_AnyYear/02_Interview_Prep/03_dsa_round_strategy.md) §4 for the general version), but AI rounds add a fifth axis:

**5. AI-systems judgment** — did you make deliberate, defensible choices about:
- Chunking strategy (and can you explain why, not just that you picked one)
- What goes in the system prompt vs. what's retrieved vs. what's a tool call
- How you'd know the thing is actually working (eval, not vibes)
- Where hallucination/failure is likely, and what you'd do about it — "the model might just get this wrong sometimes" is a **weak** answer; "I'd add a citation-grounding check and flag low-confidence retrievals" is what a senior candidate says

**The failure mode this axis catches:** a candidate who builds a working RAG pipeline but never once mentions evaluation, cost, or failure modes unprompted. Interviewers specifically watch for whether you raise these yourself — waiting to be asked reads as inexperience with production AI systems, not just an oversight.

---

## 3. Take-home eval builds — what the reviewer actually reads

When the task is "build an eval for X," the deliverable isn't the pipeline — it's whether your eval would actually **catch a regression**. Concretely, a strong take-home:

- Has a **fixed, versioned test set** (not test cases you wrote by looking at what your own solution outputs — that's testing to the answer, and experienced reviewers can tell)
- Reports metrics that map to the actual task (faithfulness/relevancy for RAG, task success rate for agents — not just "it ran without errors")
- Includes **at least one adversarial or edge case** you expect to fail, with your own honest note about why
- States a **pass/fail threshold** and justifies it, even loosely — "correctness > 90% on this test set" is a real engineering decision, "it looked good" isn't

**The tell reviewers watch for:** eval code that only tests the happy path. A senior AI engineer's instinct is "how would this silently break in production," not "does the demo work."

---

## 4. Reading a system prompt or agent harness under time pressure

When shown someone else's prompt/harness and asked to find the issue, work top-down, not randomly:

```
1. IDENTITY & SCOPE — does the prompt clearly say what the agent is and isn't for?
2. TOOL DESCRIPTIONS — are they unambiguous? (most tool-calling bugs are bad
   descriptions, not bad code — see Level7's semantic_kernel practical for why)
3. CONFLICTING INSTRUCTIONS — does anything in the prompt contradict something
   else in it, or contradict what a tool's description implies?
4. MISSING GUARDRAILS — is there anything the agent could be tricked into
   doing that isn't explicitly disallowed?
5. CONTEXT BUDGET — is anything being sent that the model won't use this turn?
   (Level6 Doc 13's context-budget framework applies directly here)
```

Narrate this checklist out loud as you go through it — the interviewer is scoring your process, not just whether you spot the bug.

---

## 5. Common failure modes specific to AI rounds

1. **Treating hallucination as an unsolvable given.** "LLMs just hallucinate sometimes" with no follow-up is a dead end. Always pair it with a mitigation (grounding, citations, confidence thresholds, human-in-the-loop for high-stakes outputs).
2. **No cost/latency awareness.** Proposing GPT-4-class models for every step of a high-volume pipeline without mentioning cheaper-tier routing (see Backend's [`02_django_fastapi_framework_qa.md`](../../Backend_Developer/03_Interview_AnyYear/02_Interview_Prep/02_django_fastapi_framework_qa.md) for the general model-routing pattern) signals you haven't shipped this in production.
3. **Confusing prompt engineering with context engineering.** If asked about a long-running agent's reliability and you only talk about wording the system prompt better, that's a scope miss — see Level6 Doc 13 for the distinction and why it matters at the systems level.
4. **No eval story at all.** "I tested it manually and it looked right" for anything beyond a toy example is the single most common gap that separates mid from senior in this loop.
5. **Not knowing your own repo's numbers.** If you claim RAG experience, be ready for "what was your retrieval failure rate, and how did you measure it?" — a vague answer here is worse than admitting you haven't measured it and explaining how you would.

---

## 6. Preparation checklist, mapped to this repo

| Round type | Practice here |
|---|---|
| Live RAG/agent build | [`Level5_RAG_Vector_Databases/`](../Level5_RAG_Vector_Databases/) practicals, [`Level6_Agent_Patterns/`](../Level6_Agent_Patterns/) practicals — run them, don't just read |
| Eval design | [`Level6_Agent_Patterns/10_agent_evaluation_practical.py`](../Level6_Agent_Patterns/10_agent_evaluation_practical.py), [`Level5_RAG_Vector_Databases/09_ragas_evaluation_practical.py`](../Level5_RAG_Vector_Databases/09_ragas_evaluation_practical.py) |
| Whiteboard AI system design | [`01_system_design_ai_questions.md`](01_system_design_ai_questions.md), timed |
| Prompt/harness review | [`Level6_Agent_Patterns/12_agent_harness_engineering_practical.py`](../Level6_Agent_Patterns/12_agent_harness_engineering_practical.py), [`13_context_engineering_practical.py`](../Level6_Agent_Patterns/13_context_engineering_practical.py) |
| Cost/latency trade-offs | [`Level3_LLM_APIs_SDKs/`](../Level3_LLM_APIs_SDKs/) — model routing, caching |

---

**Related:** [`02_coding_patterns.md`](02_coding_patterns.md) for the algorithmic-coding half of a mixed loop · [`04_key_technical_concepts.md`](04_key_technical_concepts.md) for a fast pre-interview refresh.
