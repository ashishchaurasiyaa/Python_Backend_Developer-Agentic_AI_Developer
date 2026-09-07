# Company Research & HR Round Playbook

> This is not another STAR-story bank — that's [`10_behavioral_backend.md`](10_behavioral_backend.md). And it's not salary negotiation — that's [`12_negotiation_offer.md`](12_negotiation_offer.md). This file is the round that sits **before or between** the technical rounds: the recruiter screen and the HR round — company research method, the specific questions that round asks, the logistics questions companies actually check, red flags to watch for from the other side of the table, and the questions you should be asking them.

---

## SECTION 1 — WHY THIS ROUND IS SCORED DIFFERENTLY THAN A TECHNICAL ROUND

A technical round scores whether you can do the job. The HR round scores **fit and risk**: will you accept the offer if made, will you stay past the first year, will you represent the company well to clients/teammates, and is there anything in your story that needs clarifying before an offer is extended. It's shorter, less adversarial, but a bad answer here can sink an otherwise-strong technical performance — recruiters routinely veto candidates over vague answers to "why are you leaving" or unrealistic salary expectations stated too early.

**The single biggest mistake:** treating this round as low-stakes small talk and under-preparing for it relative to the DSA/system-design rounds. It's shorter, not lower-signal.

---

## SECTION 2 — COMPANY RESEARCH: A 30-MINUTE FRAMEWORK

Do this before every onsite/final round, not just once per job search. 30 minutes, four sources:

| Source | What to extract | Time |
|---|---|---|
| **Company site + product** | What do they actually sell? Who's the customer? Sign up for the product if it's self-serve — use it for 5 minutes. | 10 min |
| **Engineering blog / GitHub org** | What's their stack? Any public post about an architecture decision, incident, or migration you can reference in conversation? | 10 min |
| **Recent news** (funding round, layoffs, leadership change, product launch) | Anything that changes the risk calculus or gives you a genuine question to ask | 5 min |
| **Glassdoor / LinkedIn / Blind** (read skeptically — both directions) | Interview process length, common complaints, but weight recent reviews over old ones and discount extreme outliers in both directions | 5 min |

**What this buys you:** the ability to answer "why do you want to join us" with something specific instead of generic flattery, and to ask a question in Section 5 that proves you actually looked.

---

## SECTION 3 — THE CORE HR-ROUND QUESTIONS

### Q1. "Tell me about yourself."

Not a request for your resume read aloud. Structure: **current role in one line → the arc that got you here (2–3 sentences) → why you're looking now → why this role specifically.** 60–90 seconds, not 5 minutes.

**Weak:** "I'm a backend engineer with 4 years of experience in Python, I've worked at X and Y, I know Django and FastAPI, I'm looking for new opportunities."

**Stronger:** "I've spent the last 4 years building backend systems for [domain] — started on a small team shipping fast, and over time moved into owning the [specific system]. I'm looking to move now because I want more ownership over system design decisions, which is what drew me to this role specifically — [company]'s engineering blog post about [specific thing] is exactly the kind of problem I want to be working on."

Full 4-minute deep-dive version of this (for when the round goes longer): [`11_resume_walkthrough_prep.md`](11_resume_walkthrough_prep.md).

---

### Q2. "Why are you looking to leave your current company?"

**Never say:** anything that badmouths the current employer, even if true and even if the interviewer seems sympathetic. It reads as a risk signal — "will they talk about us like this in a year?"

**Frame around growth, not escape**, even when escape is the real reason:
- Weak: "My manager is difficult and there's no growth."
- Better: "I've grown as much as I can in my current scope — I'm looking for a role with more ownership over [specific thing], which is what drew me to this opening."

If the real reason is compensation, org instability, or a bad manager — it's fine to be honest at a factual, non-emotional level ("the team's direction changed after a reorg") without editorializing or venting.

---

### Q3. "What are your strengths and weaknesses?"

**Strengths:** pick one that's relevant to *this specific role*, not a generic list. Back it with one concrete example, not just an adjective.

**Weaknesses — the trap to avoid:** a fake weakness ("I work too hard," "I'm a perfector") reads as evasive and is a well-known cliché that recruiters specifically probe past. Give something **real but not disqualifying**, paired with what you're actively doing about it:

> "I used to under-communicate progress on long-running tasks — I'd go heads-down and surface only when done, which meant stakeholders were sometimes surprised by delays. I've since built a habit of a short async update every 2–3 days on anything longer than a week, even when there's no real news yet."

---

### Q4. "Where do you see yourself in 3–5 years?"

The recruiter is checking: does your trajectory match what this role can actually offer? Don't claim a specific title (especially not the interviewer's own role, or something the company can't realistically offer at this level) — describe a **direction of growth** that this role plausibly enables.

> "I want to keep deepening on the backend/systems side — moving from building features to owning the architecture of a domain, and eventually mentoring more junior engineers on it. This role's scope is exactly the kind of ownership that gets me there."

---

### Q5. "Do you have any offers in hand / are you interviewing elsewhere?"

Be honest but concise — you don't owe a full list. If you have competing offers, this is useful leverage information *for later* (negotiation), not something to volunteer unprompted this early unless directly asked.

> "I'm in process with a couple of other companies, at varying stages — nothing finalized yet. This role is a strong match for what I'm looking for, which is why I wanted to move quickly through your process too."

**What NOT to do:** naming specific competing companies unprompted, or bluffing offers you don't have — recruiters in the same city/industry often know each other, and a bluff that gets checked is a worse outcome than honesty.

---

## SECTION 4 — LOGISTICS QUESTIONS (WHERE PROCESSES ACTUALLY STALL)

These aren't "soft" — a mismatch here kills offers after everything else has gone well, and Indian product/service company HR teams check them methodically.

| Question | What to prepare |
|---|---|
| **Notice period** | Know your exact number, and whether you can negotiate a buyout with your current employer if the new company wants faster. Say the real number — a mismatched notice period surfaces at the offer stage and wastes everyone's time if disclosed late. |
| **Current CTC / expected CTC** | For expected CTC: research the band first ([`12_negotiation_offer.md`](12_negotiation_offer.md) has India market bands by company tier) and give a **range**, not a single number, anchored slightly above your target. Deflecting entirely ("what's your budget for this role?") is also valid and often better — see that file's Section 6. |
| **Relocation / hybrid / remote** | Confirm you actually know the company's policy before the round — "flexible" companies sometimes mean "3 days in office," not fully remote. Don't discover this mismatch after accepting. |
| **Reason for gaps in employment** | Be factual and brief — health, caregiving, upskilling, a startup that shut down are all normal. Don't over-explain or apologize; state it once, move on. |
| **Reference checks / background verification** | Standard for product companies in India — have 2 professional references ready (former manager preferred) who know they may be contacted, and make sure your resume dates match what your previous employer's HR will confirm. |
| **Multiple offers / decision timeline** | If you're juggling processes, communicate your timeline honestly early rather than letting a company find out late that you accepted elsewhere — burns the relationship for future roles at the same company. |

---

## SECTION 5 — QUESTIONS TO ASK THEM (THIS IS ALSO BEING SCORED)

Asking no questions, or only asking about perks/WFH policy, reads as low engagement. Asking research-backed questions does the opposite work of Section 2 — signals genuine interest, not desperation.

**Good questions by category:**

- **Team/role specific:** "What does success look like in this role at the 6-month mark?" · "What's the biggest technical challenge the team is dealing with right now?"
- **Engineering culture:** "How does the team decide between building something in-house vs buying/using a managed service?" · "What's the on-call rotation like, and how is incident response handled?"
- **Growth:** "What does the path from this level to the next typically look like here?"
- **Company-research-backed (from Section 2):** "I saw the engineering blog post about [specific migration/incident] — is that pattern still evolving, or is that considered settled now?"

**Avoid asking (saves it for later, or looks bad this early):** detailed compensation/benefits questions before an offer exists, "how many vacation days" as an opening question, or anything answerable with two minutes on the company website.

---

## SECTION 6 — RED FLAGS TO WATCH FOR (THE INTERVIEW GOES BOTH WAYS)

An HR/recruiter round is also your chance to evaluate them. Some signals worth noting, not necessarily disqualifying alone, but worth weighing together:

- **Vague answers about team size, tech stack, or reporting structure** — a well-run engineering org can answer these crisply.
- **Excessive urgency to close ("we need an answer by tomorrow")** without a clear reason — can indicate high attrition backfill pressure.
- **Every question about growth gets deflected to "depends on performance"** with no concrete examples of anyone who's actually grown through the levels.
- **Recruiter can't or won't connect you with the hiring manager or a future teammate** before an offer, when reasonably requested.
- **Consistently negative recent Glassdoor/Blind reviews specifically about the team you'd join**, not just generic company-wide noise (weight recency and specificity higher than volume).

None of these alone should tank a decision — they're data points to weigh alongside everything else (comp, role scope, company trajectory), the same way a technical interviewer weighs one weak answer against an otherwise-strong round.

---

## SECTION 7 — SERVICE COMPANY vs PRODUCT COMPANY vs STARTUP: HOW THIS ROUND DIFFERS

| | Service companies (TCS/Infosys/Wipro-tier) | Product companies | Startups |
|---|---|---|---|
| **Round length** | Short, often scripted questions | 30–45 min, more conversational | Often folded into a founder/hiring-manager chat, less formal |
| **What's actually scored** | Communication basics, availability/notice period, willingness to relocate to client location | Culture fit, growth trajectory match, comp band fit | Founder chemistry, comfort with ambiguity, genuine interest in the mission (not just comp) |
| **Comp discussion** | Often fixed bands by experience, less room to negotiate here | Range-based, negotiable | Equity is part of the conversation — understand vesting/strike price basics before this round |
| **Biggest risk if underprepared** | Sounding disengaged or unclear about availability | Vague "why us" answer with no company-specific research | Not being able to speak to why THIS problem/mission, not just "it's a startup so it sounds exciting" |

Condensed rapid-revision version for a short-notice service-company screen: [`INFOSYS_QUICK_REVISION.md`](INFOSYS_QUICK_REVISION.md).

---

**Related:** STAR-format behavioral stories for the technical-adjacent rounds — [`10_behavioral_backend.md`](10_behavioral_backend.md). Salary bands and negotiation mechanics once an offer exists — [`12_negotiation_offer.md`](12_negotiation_offer.md). Narrating your resume and past projects — [`11_resume_walkthrough_prep.md`](11_resume_walkthrough_prep.md).
