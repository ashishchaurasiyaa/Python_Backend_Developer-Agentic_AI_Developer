# Resume Walkthrough Prep — Make Your Past Sound Senior

> "Walk me through your resume" is the most-asked interview opener and the most under-prepared.
> Done well, it's a 4-minute pitch that frames every subsequent question. Done poorly, it sets a low ceiling.

---

## THE 4-MINUTE WALKTHROUGH STRUCTURE

```
0:00 → 0:30   Open with current role + signature accomplishment
0:30 → 2:00   Last 2 jobs in detail (impact-focused)
2:00 → 3:00   Earlier career as quick summary
3:00 → 3:30   Why you're looking now
3:30 → 4:00   What you're looking for + segue to "happy to dive into anything"
```

**Why this works:** Inverted pyramid — most recent and impressive first, fade detail as we go back.

---

## STAGE 1 — STRUCTURE FOR EACH ROLE

For your current + last role, prepare a structured pitch:

```
COMPANY (1 sentence — what it does, your scale)
ROLE (1 sentence — title, team, what you owned)
KEY ACHIEVEMENT 1 (specific, quantified)
KEY ACHIEVEMENT 2 (different dimension — e.g., technical vs leadership)
TECHNICAL STACK (1 line)
```

### Example narrative

> "I'm currently at **Razorpay**, India's largest payments platform — about 100K merchants, processing 10M+ transactions a day.
>
> I joined as a **senior backend engineer on the payments team**, owning our checkout API and webhook delivery system.
>
> My biggest project was **migrating our webhook delivery system from a polling cron to event-driven Kafka pipeline**. Reduced delivery latency from 30 seconds p95 to 200ms, and our merchant complaint volume on missed webhooks dropped 80%.
>
> Last quarter I **led the on-call rotation overhaul** — we'd been waking engineers up on 30 pages a week; I refactored alert routing and added auto-remediation, brought it to 6 actionable pages a week.
>
> Stack: **Python (FastAPI), Postgres, Kafka, Redis, Kubernetes on AWS.**"

**Time:** ~50 seconds for a current role. Don't go over 90.

---

## STAGE 2 — BUILD YOUR PITCH IN 5 PASSES

### Pass 1 — Brain dump (don't edit)
Write everything you did at each job. Forget brevity. Get raw material.

### Pass 2 — Rank by impact
For each job, identify the top 3 things that had **measurable business or technical impact**. Drop the rest.

### Pass 3 — Quantify
Every accomplishment needs a number.

| Vague | Quantified |
|---|---|
| Improved API performance | Reduced p99 from 2s to 200ms (10x improvement) |
| Migrated old system | Migrated 50M user records with zero downtime |
| Mentored juniors | Mentored 3 engineers, 2 promoted to mid-level |
| Built new service | Built notification service handling 5K req/sec |
| Fixed many bugs | Reduced production error rate from 2% to 0.1% |

**If you have no numbers — go find them.** Check old commits, PRs, Slack archives, metrics dashboards.

### Pass 4 — Connect to scope/seniority
Frame each accomplishment in terms of:
- **Scope:** team, multiple teams, org-wide.
- **Difficulty:** novel problem, well-trodden, brownfield.
- **Ownership:** solo IC, tech lead, IC + team enablement.

### Pass 5 — Rehearse out loud
Time yourself. Cut anything that doesn't land in 4 min total.

---

## STAGE 3 — THE FAMOUS PROJECT DEEP-DIVE

After your walkthrough, interviewer often picks ONE project and probes:
- "Tell me more about that webhook migration..."
- "What was the hardest part?"
- "What would you do differently?"

**Pre-prep this for 2-3 projects.** Each should have:

```
1. CONTEXT
   - Business problem (why was this needed?)
   - Existing solution and its limitations.
   - Constraints (timeline, team size, budget).

2. APPROACH
   - Architectural decisions (with trade-offs).
   - Why this approach vs alternatives.
   - Specific technical choices (e.g., "Why Kafka not RabbitMQ?").

3. EXECUTION
   - Your role: solo, lead, contributor.
   - Timeline + how it broke down.
   - Blockers and how you handled them.

4. OUTCOME
   - Metrics (latency, cost, errors, adoption).
   - Business impact.
   - Lessons learned.

5. REFLECTION
   - What would you do differently?
   - What surprised you?
```

### Sample deep dive

> **Q: "Walk me through the webhook migration in more detail."**
>
> **Context:** We had a cron job that polled a `pending_webhooks` table every 30 seconds and HTTP-POSTed to merchant URLs. As volume grew (3M webhooks/day), the cron ran longer than 30 seconds, creating queueing. Merchants complained about lag. Some webhooks were delivered with 5-min lag.
>
> **Approach:** Replaced with event-driven Kafka. Producer service writes events on payment status change → Kafka topic → consumer service delivers via HTTP. Chose Kafka over RabbitMQ for replay capability (we needed to replay 24h of failed deliveries occasionally) and our team already operated Kafka.
>
> **Execution:** 4 weeks, 2 engineers. Phase 1: build new path in parallel, dual-write to both systems (Kafka + old table). Phase 2: validate Kafka path with sampling. Phase 3: cut consumers to Kafka-only. Biggest blocker was idempotency — retries created duplicates. Solved via `delivery_id` UUID + DB unique constraint.
>
> **Outcome:** p95 delivery latency: 30s → 200ms. p99: 5min → 800ms. Merchant complaints dropped 80%. Operational cost roughly equal (Kafka added cost, dropped cron infra cost).
>
> **Reflection:** I'd add per-merchant rate limiting from day 1 — we had one merchant whose endpoint was so slow it would back up consumers. Added it in a follow-up sprint. Also: should've benchmarked downstream merchant tolerance first; some had 10-sec lambda timeouts that fired before our retry.

**Total time:** ~3 minutes. Detailed enough to demonstrate depth without dragging.

---

## STAGE 4 — CONNECTING THE DOTS

A great walkthrough has a **narrative arc** — your career has a direction, not random hops.

### Bad arc
> "I worked at A for 2 years doing payments. Then at B for 1 year doing notifications. Now at C for 6 months doing search."

(Sounds random. Why would they hire you?)

### Good arc
> "I started at A working on payments — that taught me distributed transactions and idempotency. At B I applied that to notifications — same problem class, different domain. At C I'm scaling it up to search infrastructure, where I'm learning Elasticsearch at production scale. The thread through all of it is data systems at scale."

(Now there's a story. They can predict your trajectory.)

### Frame domain changes positively
- "I deliberately switched from fintech to logistics to broaden my domain exposure."
- Not: "I left because the team was bad."

---

## STAGE 5 — RED FLAGS TO PRE-EMPT

Before they ask awkward questions, plan how to address gaps.

### Job hopping
> "I had three roles in 2 years, which I know looks scattered. The pattern: my first role was the wrong fit — startup with no engineering culture, I left after 8 months. Then a 14-month tenure at X. Now at Y for 14 months and stable. I'm looking for the next 4+ year run."

### Employment gap
> "I took 6 months off in 2024 to care for a family member. During that time I shipped a side project [X], rebuilt my Python knowledge with [Y], and read [Z]."

### No name-brand companies
> "Worked at small startups so far — gave me end-to-end ownership and exposure to the full stack. Now I want to learn from a larger team's engineering practices, which is why your scale appeals."

### Long tenure at one place
> "8 years at [X] sounds long, but in those 8 years I rotated through 4 different teams and got promoted twice. Each rotation was effectively a new job."

### Older roles (15+ years experience)
> "I'll spend more time on the last 5-7 years — earlier roles were valuable foundation but probably less relevant to this conversation. Happy to dive into anything specific."

---

## STAGE 6 — THE OPENING LINE

Your first sentence sets tone. Test 3-4 openings, pick what feels natural.

### Strong openings
- "I'm currently a senior backend engineer at X, where I've been for 3 years scaling our payments platform from 100 RPS to 10K."
- "I've been a backend engineer for 6 years, specializing in distributed systems at consumer-scale companies."
- "I started as a backend dev at a startup and have built up to leading payment infrastructure at scale."

### Weak openings
- "So, um, where do you want me to start?" (no agency)
- "My name is X, I have a degree from Y..." (irrelevant — they have your resume)
- "I'm currently at X, doing Java backend stuff" (vague)

---

## SAMPLE FULL 4-MIN WALKTHROUGHS

### Sample 1 — Senior Backend (5 years experience)

> "I'm currently a senior backend engineer at **Razorpay**, India's largest payments platform. I've been there 2 years, focused on our checkout API and webhook delivery system. My signature project was migrating webhook delivery from a polling cron to event-driven Kafka — brought p95 latency from 30 seconds to 200ms.
>
> Before that, I spent 3 years at **Zomato** on the food delivery platform. Worked on the order assignment system — that's where I learned distributed systems at real scale. Built the surge-pricing service from scratch, which handled 50K req/sec during peaks.
>
> Started my career at a 10-person startup called **CallHippo** in 2018 — that's where I learned to ship full-stack solo. Built voice-calling infrastructure on Twilio and Asterisk. Steep learning curve, lots of ownership.
>
> Why I'm looking: I've been at Razorpay for 2 years and the next obvious move is staff engineer, but the path isn't clear at my current team. I want to work on systems at the next order of magnitude or learn from staff/principal engineers above me. **Your team's work on [X] is exactly the kind of stretch I'm looking for.**
>
> I'm strongest in **Python, Postgres, Kafka, distributed systems**. Happy to dive into any project in more depth."

**~ 3:45 min spoken.**

### Sample 2 — Mid-level Backend (3 years experience)

> "I'm a backend engineer at **Swiggy** for the last 18 months on the discovery and search team. I work mostly in Python and Go — built the personalization service that powers the homepage feed, currently serving 60M users a day at p95 of 80ms.
>
> Before that, I spent 18 months at **Zerodha** on their backend platform, working on the trading-API. Smaller scale but tighter latency requirements — sub-10ms p99.
>
> First job out of college was a 2-year stint at **Practo**, on their backend team handling appointments and patient records. Steep learning curve — first exposure to production systems, on-call, and code reviews at scale.
>
> Looking now because at Swiggy I'm getting comfortable, and I want to stretch into systems I haven't touched yet — specifically distributed data systems and high-throughput streaming. Your team's recent post on the analytics pipeline rebuild caught my attention.
>
> Comfortable diving deeper into any of these. Where would you like to start?"

**~ 2:30 min spoken. Junior version, can be shorter.**

---

## STAGE 7 — PREPARE THE TIE-DOWNS

After your pitch, lead them where you want them to go.

**Closing phrases that work:**
- "Happy to go deeper on any of those — which one would you like to start with?"
- "I have a strong opinion on [X], if you want to dive there."
- "I think [project Y] is most relevant to the kind of work you're doing here — happy to walk through that."

**Avoid:**
- "...and yeah, that's pretty much it." (anti-climactic)
- "Did that answer your question?" (sounds insecure)
- Trailing off without a hand-off.

---

## STAGE 8 — REHEARSAL CHECKLIST

Before the actual interview:

- [ ] Recorded yourself doing the full walkthrough. Watched it back. Cut filler ("um", "like", "basically").
- [ ] Timed it. Under 4 minutes.
- [ ] Practiced with 2 people who give honest feedback.
- [ ] Have a 90-second version (for "give me a quick intro") and a 4-minute version (for "walk me through your resume").
- [ ] For each major role, have a deep-dive ready (3 min each).
- [ ] Pre-empt every gap or oddity in your resume.
- [ ] Have your "why looking" line nailed.
- [ ] Have your "what I'm looking for" line nailed.

---

## ANTI-PATTERNS

| Don't do | Do instead |
|---|---|
| List job titles + duties | Highlight 2-3 impacts per role |
| Talk for 8+ minutes | Cap at 4 min, invite follow-up |
| Use jargon they don't share | Plain language, then dive into specifics |
| Avoid talking about failures | Briefly own gaps proactively |
| Read your resume aloud | Tell a story |
| Stay in present tense the whole time | Past tense for past roles |
| Say "I helped with X" | "I owned X" (if true) |
| Trail off with "yeah, so..." | Land on a question/handoff |

---

## TONE & DELIVERY

- **Pace:** Slower than you think. Nervous people speed up.
- **Pauses:** Use them for emphasis after a key point.
- **Confidence:** Speak in declarative sentences. "I built X" not "I think I built X."
- **Energy:** Slightly higher than baseline. Bored interviewers tune out.
- **Eye contact** (in-person/video): Steady, not staring.
- **Smile** at the start. Sets the dynamic.

---

## FINAL TIP

**Your resume is not the constraint — your articulation is.**

Two candidates with identical experience often get vastly different outcomes because one **tells the story** and the other **lists facts.**

Do the prep. Rehearse. Time it. Show up sounding like you've already done this 50 times — because you have, in your bedroom mirror.
