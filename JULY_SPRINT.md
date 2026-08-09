# 🚀 JULY SPRINT — Senior Backend + Agentic AI (28 June → 31 July 2026)

> # 📦 CLOSED / EXPIRED — archive only
> **Sprint window:** 28 Jun → 31 Jul 2026 · **Closed on:** 2026-08-08 · **Outcome:** 0/10 items checked
>
> **Retro (ek line):** plan theek tha, execution nahi hua — poore sprint me content likha gaya, labs nahi kiye.
> Yahi RCA [`MY_PROGRESS.md`](MY_PROGRESS.md) me note hai: *"audit loop comfortable hai, labs karna uncomfortable hai."*
> Isi wajah se naya driver [`ROADMAP.md`](ROADMAP.md) **lab-first** hai (theory tab kholo jab lab me atko).
>
> **Aaj ka kaam → [`ROADMAP.md`](ROADMAP.md).** Yeh file sirf reference ke liye rakhi hai —
> priority order (English → DSA → System Design → Backend) aaj bhi sahi hai, dates nahi.

---

> **Ek hi maqsad:** 31 July tak interview-ready hona.
>
> **Priority order (yahi follow karo, is order me):**
> 1. 🗣️ **English** — asli gap yahi hai, pehle aata hai
> 2. 💻 **DSA** — coding round ka pehla filter
> 3. 🏛️ **System Design** — senior role ka 40%
> 4. 📚 **Backend Topics** — depth refresh (Python, APIs, Microservices etc.)
>
> **Time budget (realistic):** ~3–4 hrs/day · 5 days/week · 4.5 weeks = **~65–70 study hours**
>
> Yeh plan `STUDY_PLAN.md` ka calendar layer hai — wahan items hain, yahan **schedule + deadlines**.

---

## 📅 WEEK 1 (28 June – 4 July) — FOUNDATION LOCK

**Theme:** English start + Python depth + DSA warm-up + Agentic refresh

| Day | Slot | Time | Kya karna hai |
|-----|------|------|---------------|
| Sat 28 | 🗣️ English | 30m | Basic scripts: self-intro + "tell me about your experience" → [english_speaking/](english_speaking/README.md) |
| Sat 28 | 💻 DSA | 1h | Pattern 1: Two Pointers — 2 problems (`01_DSA`) |
| Sat 28 | 📚 Backend | 1.5h | Python Advanced — GIL, async internals, descriptors, metaclasses (`01_Python_Advanced`) |
| Sun 29 | 🗣️ English | 30m | "Why are you looking for a change?" + "What are your strengths?" — loud practice |
| Sun 29 | 💻 DSA | 1h | Pattern 2: Sliding Window — 2 problems |
| Sun 29 | 📚 Backend | 1.5h | API Design — REST maturity, versioning, idempotency, webhooks (`02_API_Design`) |
| Mon 30 | 🗣️ English | 30m | "Describe a challenging project" — STAR format loud |
| Mon 30 | 💻 DSA | 1h | Pattern 3: Stack/Monotonic Stack — 2 problems |
| Mon 30 | 📚 Backend | 1.5h | Security — JWT/OAuth2/RBAC, OWASP Top 10 (`03_Security`) |
| Tue 1 | 🗣️ English | 30m | Technical vocabulary: "scalability", "trade-off", "bottleneck", "throughput" |
| Tue 1 | 💻 DSA | 1h | Pattern 4: Hashing — 2 problems |
| Tue 1 | 📚 Backend | 1.5h | Microservices — CQRS, event sourcing, outbox, saga (`05_Microservices`) |
| Wed 2 | 🗣️ English | 30m | "Walk me through your architecture at Niroskos" — bolke practice |
| Wed 2 | 💻 DSA | 1h | Pattern 5: Trees BFS/DFS — 2 problems |
| Wed 2 | 📚 Backend | 1.5h | Design Patterns + SOLID — GoF in Python (`15_Design_Patterns_SOLID`) |
| Thu 3 | 🗣️ English | 30m | "What is your biggest weakness?" + "Where do you see yourself in 5 years?" |
| Thu 3 | 💻 DSA | 1h | Pattern 6: Graphs — 2 problems |
| Thu 3 | 📚 Backend | 1.5h | DevOps refresh — Docker, CI/CD, Prometheus/Grafana (`04_DevOps`) |
| Fri 4 | 🗣️ English | 30m | Week 1 English review — record karke suno, weak spots note karo |
| Fri 4 | 💻 DSA | 45m | Weak problem revisit — jo galat hua tha |
| Fri 4 | 📚 Backend | 45m | Week 1 Backend gaps cover karo |

**Week 1 Deliverable:** Python + API + Security + Microservices = mentally refreshed. DSA Pattern 1–3 done.

---

## 📅 WEEK 2 (5 July – 11 July) — SYSTEM DESIGN CORE

**Theme:** HLD Theory (foundations) + DSA patterns continue + Agentic Tool Use / RAG

| Day | Block | Kya karna hai |
|-----|-------|---------------|
| Sat 5 | SD (2h) | HLD Theory 01–10: architecture basics, latency/throughput, CAP theorem, caching (`HLD_Theory`) |
| Sat 5 | DSA (1h) | Pattern 4: Hashing — 2 problems |
| Sun 6 | SD (2h) | HLD Theory 11–20: DB sharding/replication, auth, load balancing, CDN, SLA |
| Sun 6 | Agentic (1h) | Level 4: Tool Use / Function Calling — yahi se "agentic" shuru |
| Mon 7 | SD (2h) | HLD Theory 21–31: message queues, event-driven, observability, rate limiting |
| Mon 7 | DSA (1h) | Pattern 5: Trees BFS/DFS — 2 problems |
| Tue 8 | SD (2h) | HLD Theory 32–42: advanced sharding, circuit breaker, consistent hashing |
| Tue 8 | Agentic (1h) | Level 5: RAG & Vector DBs — chunking, embeddings, hybrid search |
| Wed 9 | SD (2h) | HLD Theory 43–58: CRDTs, idempotency, serverless, final batch |
| Wed 9 | DSA (1h) | Pattern 6: Graphs (BFS/DFS) — 2 problems |
| Thu 10 | HLD Problems (2h) | **Classics aloud:** URL Shortener, Rate Limiter, Notification System — **bolke design karo** |
| Thu 10 | Agentic (1h) | Level 5 continued: reranking, RAGAS eval |
| Fri 11 | REVIEW (2h) | HLD Theory gaps. DSA 1 problem. English: System Design vocabulary practice (30 min) |

**Week 2 Deliverable:** HLD Theory 01–58 done. DSA Pattern 4–6 done. RAG concepts clear.

---

## 📅 WEEK 3 (12 July – 18 July) — HLD PROBLEMS + AGENT PATTERNS

**Theme:** Classic + Product HLD problems (design karo, mat sirf padho) + Agent Patterns deep

| Day | Block | Kya karna hai |
|-----|-------|---------------|
| Sat 12 | HLD Problems (2h) | Payment System, Pastebin — bolke design karo, whiteboard style |
| Sat 12 | DSA (1h) | Pattern 7: Heaps / Priority Queue — 2 problems |
| Sun 13 | HLD Problems (2h) | YouTube / Netflix — scale, CDN, recommendation, storage |
| Sun 13 | Agentic (1h) | Level 6: Agent Patterns — ReAct, Plan-Execute, Reflection |
| Mon 14 | HLD Problems (2h) | Instagram Feed, Twitter Timeline — fan-out, timeline aggregation |
| Mon 14 | DSA (1h) | Pattern 8: DP (1D) — 2 problems |
| Tue 15 | HLD Problems (2h) | AI/Modern: ChatGPT Backend, RAG System — queue + streaming + token budget |
| Tue 15 | Agentic (1h) | Level 6: Multi-agent supervisor, Routing, Human-in-loop, Swarm |
| Wed 16 | LLD Theory (1.5h) | OOP + SOLID, GoF patterns (`LLD_Theory`) |
| Wed 16 | DSA (1h) | Pattern 9: DP (2D) — 2 problems |
| Thu 17 | LLD Problems (2h) | LRU Cache, Rate Limiter, URL Shortener — code live |
| Thu 17 | Agentic (1h) | Level 7: LangGraph + MCP — yeh must hai, CrewAI/LlamaIndex/PydanticAI |
| Fri 18 | REVIEW (2h) | HLD weak spots revisit. DSA 1 problem. English: "Design karo" mock answer practice |

**Week 3 Deliverable:** 10+ HLD problems bolke done. LLD basics done. Agent Patterns + LangGraph clear.

---

## 📅 WEEK 4 (19 July – 25 July) — HANDS-ON + INTERVIEW PREP

**Theme:** Production LLMOps + Kafka/gRPC skim + Backend Interview Prep + Project build

| Day | Block | Kya karna hai |
|-----|-------|---------------|
| Sat 19 | Agentic (2h) | Level 8: Production LLMOps — observability, guardrails, cost, fine-tuning |
| Sat 19 | DSA (1h) | Pattern 10: Binary Search — 2 problems |
| Sun 20 | Backend (1.5h) | Kafka — topics, partitions, exactly-once (`07_Kafka`) — JD-specific skim |
| Sun 20 | Agentic (1h) | AI Interview Prep (`Interview_Prep`) — agent orchestration Qs, RAG optimization |
| Mon 21 | Backend Interview (2h) | Python tricky Qs — GIL, mutable defaults, descriptors, async (`02_Interview_Prep`) |
| Mon 21 | DSA (1h) | Pattern 11: Greedy — 2 problems |
| Tue 22 | Backend Interview (2h) | System Design 50 Qs mock (`02_Interview_Prep`) — loud answers |
| Tue 22 | Agentic (1h) | MCP Advanced + AI Security — MCP server banana, OWASP LLM Top 10 |
| Wed 23 | PROJECT (3h) | **Capstone start:** RAG Document Q&A *ya* Multi-Agent Code Review — scaffold + README |
| Thu 24 | PROJECT (3h) | **Capstone build:** core feature working end-to-end |
| Fri 25 | REVIEW (2h) | DSA weak patterns revisit. English: "Tell me about your project" script polish |

**Week 4 Deliverable:** LLMOps done. Backend interview Qs done. Capstone project 60% ready.

---

## 📅 WEEK 5 (26 July – 31 July) — FINAL POLISH + MOCK INTERVIEWS

**Theme:** Consolidate, mock interviews, project finish, resume + English final polish

| Day | Block | Kya karna hai |
|-----|-------|---------------|
| Sat 26 | PROJECT (3h) | Capstone finish + GitHub push + README polish |
| Sat 26 | DSA (1h) | Pattern 12: Backtracking — 2 problems |
| Sun 27 | MOCK (2h) | Full mock System Design round: "Design WhatsApp" — bolke, 45 min |
| Sun 27 | English (1h) | Interview intro + project walkthrough script — record karke suno |
| Mon 28 | MOCK (2h) | Full mock DSA round: 2 medium problems timed (30 min each) |
| Mon 28 | Backend (1h) | Behavioral (STAR) + Resume walkthrough (`02_Interview_Prep`) |
| Tue 29 | MOCK (2h) | Agentic mock: "Design a RAG system for enterprise" — bolke |
| Tue 29 | DSA (1h) | Weak pattern revisit — jo bhi galat hua tha |
| Wed 30 | FINAL REVIEW (3h) | HLD weak spots, Python gotchas, English answers — last polish |
| Thu 31 | 🎯 READY DAY | Sab review. Resume update. Apply karo. |

**Week 5 Deliverable:** 3 full mocks done. Project on GitHub. Resume updated. Interview-ready.

---

## 📊 PRIORITY MATRIX — kya kabhi skip nahi karna

| Rank | Priority | Topic | Reason |
|------|----------|-------|--------|
| 1 | 🔴 MUST | **English speaking (daily)** | Asli gap yahi hai — sab kuch aata hai par bol nahi pate |
| 2 | 🔴 MUST | **DSA Patterns 1–12** | Pehla filter, coding round = nahi hua to sab bekar |
| 3 | 🔴 MUST | **HLD Theory 01–58** | Senior interview ka 40% — bolke answer karo |
| 4 | 🔴 MUST | **HLD Problems (10+)** | Bolke practice — sirf padhna kafi nahi |
| 5 | 🔴 MUST | **Python Advanced (GIL/async)** | "Senior Python" = yeh zaroor poochha jayega |
| 6 | 🔴 MUST | **LLD Problems (5+)** | Code karo live |
| 7 | 🟡 SHOULD | Level 6 Agent Patterns | Agentic roles ke liye |
| 8 | 🟡 SHOULD | Level 7 LangGraph + MCP | Real agentic frameworks |
| 9 | 🟡 SHOULD | Capstone Project | Resume proof |
| 10 | ⚪ SKIM | Kafka / gRPC / GraphQL | JD me ho to 1 day, warna skip |
| 11 | ⚪ SKIP | L1/L2 Agentic deep dive | Already done on Udemy |

---

## ⚡ DAILY STRUCTURE (roz follow karo — PRIORITY ORDER ME)

```
SLOT 1 — 🗣️ English (30–45 min)   ← PEHLE, kabhi skip nahi
  Morning ya commute pe:
  - Week 1–2: Basic → Intermediate scripts (english_speaking/README.md)
  - Week 3–4: Interview English — "Tell me about yourself", "Design X"
  - Week 5:   Record karke suno, polish karo

SLOT 2 — 💻 DSA (1.5–2 hrs)        ← ROZ, no excuse
  5 problems/day — Easy→Medium→Hard order
  Easy (1–2): 15 min each
  Medium (2): 25 min each
  Hard (1): 30 min — skip if time short
  Stuck? 15 min baad hint, 25 min baad solution. Pattern > solve.

SLOT 3 — 🏛️ System Design (1–1.5h) ← BOLKE practice karo, mat sirf padho
  HLD Theory → HLD Problems (Week 2–3 me heavy)
  LLD Problems (Week 3 me)

SLOT 4 — 📚 Backend Topics (45–60 min) ← Depth refresh
  Python Advanced → API Design → Microservices → DevOps (Week 1 me)
  Agentic AI L4–L8 (Week 2–4 me rotate karke)
  
SLOT 5 — 📝 Log (5 min)
  MY_PROGRESS.md — 3 lines: kya padha / kya code / kal kya
```

**Chhota din rule:** Bas **English 20 min + DSA 1 problem**. Streak > perfection.
**Sabse chhota din bhi:** English pehle, baki baad.

---

## 🎯 31 JULY CHECKLIST — Interview Ready Hoon Agar:

- [ ] HLD Theory 01–58 done ✅
- [ ] 10+ HLD problems bolke design kiye ✅
- [ ] 5+ LLD problems live code kiye ✅
- [ ] DSA Patterns 1–12 done, 2–3 per pattern ✅
- [ ] Python Advanced (async, GIL, decorators, metaclasses) confident ✅
- [ ] Agentic Level 4–8 done (RAG + Agent Patterns + LangGraph + LLMOps) ✅
- [ ] 1 capstone project on GitHub ✅
- [ ] 3 full mock interview rounds done ✅
- [ ] English: "Tell me about yourself" + "Design X" + "Project walkthrough" scripts polished ✅
- [ ] Resume updated with project + skill lines ✅

---

> **Yaad rakh:** Content already hai repos me — ab execution ka game hai. Bolke practice karo, code karo, aur roz thoda English. 31 July ka target real hai agar roz 3–4 ghante dete ho.
>
> Daily entry point: [`STUDY_PLAN.md`](STUDY_PLAN.md) · Progress log: [`MY_PROGRESS.md`](MY_PROGRESS.md)
