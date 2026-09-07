# AI Company & Role Research — Is This a Real AI Role?

> [`03_behavioral_questions.md`](03_behavioral_questions.md) already covers generic "questions to ask the interviewer" and STAR-format answers — this file is narrower and AI-specific: **how to tell whether an "AI/GenAI" role is genuinely building production AI systems or is a thin wrapper role**, what due-diligence questions actually reveal that, and what to weigh once you know.

---

## 1. Why this matters more for AI roles than most

"AI Engineer" and "GenAI Developer" are currently some of the most inflated titles in the job market — the same title can mean anything from "owns evals, guardrails, and a real agent platform serving millions of requests" to "wrote a few prompts and called the OpenAI API from a Flask app once." The gap between these two roles in skill development, resume value, and actual work is enormous, and JDs rarely make the difference obvious. Spending 20 minutes of research before an onsite is the highest-leverage thing you can do to avoid taking (or wasting interview time pursuing) the wrong one.

---

## 2. The research framework — where to actually look

| Source | What to check | What it tells you |
|---|---|---|
| **Engineering blog / GitHub** | Any post about eval methodology, guardrails, an incident involving the AI system, or model routing? | Real production AI work generates real production AI problems — if none are ever discussed publicly, that's not disqualifying alone, but worth asking about directly |
| **The actual product** | Use it. Does the AI feature feel genuinely useful, or bolted on? Does it fail gracefully, or hallucinate visibly? | A company that ships a rough-but-honest AI feature is often further along than one with a polished demo and no real usage |
| **Job posting itself, read literally** | Does it list specific tools (LangGraph, evals, vector DBs, specific model providers) or only buzzwords ("AI-powered," "cutting-edge")? | Specific tooling mentions usually mean someone who actually does the work wrote the JD |
| **LinkedIn of the team you'd join** | Do current members have hands-on AI/ML backgrounds, or did the team get relabeled "AI team" during a recent pivot? | A team that pivoted overnight from "backend team" to "AI team" isn't automatically bad, but changes what you're actually walking into |
| **Funding/press context** | Is "AI" central to the company's actual business model, or a feature bolted onto an unrelated product for a funding narrative? | Shapes how much real investment and roadmap priority the AI work will realistically get |

---

## 3. Due-diligence questions that actually reveal the answer

Generic "tell me about your AI stack" invites a rehearsed, impressive-sounding non-answer. These are harder to fake convincingly:

- **"How do you know your AI feature is actually working well — what do you measure, and how often does it regress?"** A real answer names a specific metric and a specific incident. A vague answer ("we monitor it") is a signal, not a disqualifier — but worth noting.
- **"Walk me through what happens when the model gets something wrong in production — how do you find out, and what's the fix path?"** Tests whether there's an actual observability/eval loop, not just a demo that worked once.
- **"What's your model-routing or cost-control strategy?"** At any real scale, cost becomes a first-class engineering concern — no answer at all suggests low volume or no real production traffic yet, which isn't automatically bad but is useful context for what you'd actually be doing day to day.
- **"How much of the team's day-to-day is prompt/context iteration vs. traditional backend work?"** Calibrates expectations directly — useful either way, since some candidates want more AI-specific depth and some want AI as one part of a broader backend role.
- **"What happens when the underlying model provider ships a breaking change or deprecates a model version?"** A team that's hit this before will have a real story. A team that hasn't thought about it yet is either very new to production AI or has been lucky so far.

---

## 4. Red flags worth weighing (not automatic disqualifiers)

- The JD is AI-buzzword-dense but the interviewer can't describe a single specific technical challenge the team has actually faced
- "We're pivoting to AI" said about a company whose core product has nothing to do with AI, with no concrete roadmap beyond the phrase itself
- No one on the team can name what model/provider they use, or says "we're still deciding" for a role that's supposedly hands-on with it today
- The interview process itself never touches on evals, safety, or failure handling at all — for a genuinely AI-native team, this usually comes up somewhere in the loop unprompted

**None of these should be read as absolute rules** — an early-stage team that's honest about "we're still figuring this out" can be a genuinely good, high-growth opportunity; the point is to walk in with eyes open about which kind of role it actually is, not to filter companies out mechanically.

---

## 5. Comp and market context — India, GenAI-specific (2026)

The AI-role premium is real but uneven, and skews toward companies with actual production AI workloads over ones just adding the title:

- **Product companies with real AI platforms** (Series B+, or established product companies building AI features) generally pay a premium over an equivalent non-AI backend role at the same company tier — the premium reflects genuine scarcity of engineers with hands-on eval/agent/RAG production experience, not just LLM API familiarity.
- **"AI" roles at traditional service companies** often pay close to standard backend bands despite the title, since the work is frequently thinner than the title implies — verify with the due-diligence questions above before assuming the title alone justifies a premium ask.
- **Startups building AI-native products** vary hugely — equity matters more here than at an established company, and the due-diligence questions in §3 matter more too, since you're betting more of your near-term skill development on the team's actual maturity.

For the full India salary-band breakdown by company tier and negotiation mechanics once an offer exists, see the Backend track's [`12_negotiation_offer.md`](../../Backend_Developer/03_Interview_AnyYear/02_Interview_Prep/12_negotiation_offer.md) — those bands apply here too; this file only adds the AI-specific premium/discount judgment on top.

---

**Related:** [`05_genai_developer_azure_role_prep.md`](05_genai_developer_azure_role_prep.md) for a worked example of mapping one specific JD to prep · [`06_ai_interview_round_strategy.md`](06_ai_interview_round_strategy.md) for what happens once you're in the loop · Backend's [`04_company_research_hr_round.md`](../../Backend_Developer/03_Interview_AnyYear/02_Interview_Prep/04_company_research_hr_round.md) for the general (non-AI-specific) company-research framework and HR-round logistics.
