# 📅 90-DAY DAY-BY-DAY PLAN (12 weeks × 6 study days, Mon–Sat, Sunday rest)

> # ⚠️ YEH DAILY DRIVER NAHI HAI — dates ignore karo
> **Superseded for day-to-day use on 2026-08-08 by [`ROADMAP.md`](ROADMAP.md).**
> Is file ki calendar dates (Week 5 = Aug 05–11, etc.) ab ROADMAP se **match nahi karti** —
> ROADMAP 2026-08-08 ko Day 1 se shuru karta hai (lab-first), yeh file Day 28 dikhata hai.
> **Do calendars follow mat karo.** Roz ka kaam sirf [`ROADMAP.md`](ROADMAP.md) se lo.
>
> **Yeh file kis liye ab bhi useful hai:**
> - 🎯 **Job-hunt track** (resume → apply → project) — wo ab bhi valid hai, dates ke bina → [neeche dekho](#-job-hunt-track-runs-in-parallel-with-the-study-weeks--read-this-first)
> - 🏢 **Office-theory vs personal-practice** split ka idea (kaam ke beech kya padha ja sakta hai)
> - Long-range 12-week map, agar ROADMAP ke 8 hafte khatam ho jayein
>
> Applications track karne ke liye: [`JOB_TRACKER.md`](JOB_TRACKER.md)

---

> Derived from [00_START_HERE.md](00_START_HERE.md) PATH A (10-week sprint) + 2 buffer weeks + daily English.
> **Restarted from Day 1 on 2026-07-08** (no `MY_PROGRESS.md` entries existed yet, so this is a clean start — dates below are real calendar dates, Sunday = rest/catch-up, not listed).
>
> **Time split (theory vs practice):**
> - 🏢 **Office (9–6)** → **theory only** — reading/watching docs, no hands-on coding. This column is what to read during office hours.
> - 🌙 **Personal time (before/after office)** → **practice** — DSA coding, English speaking drills, project building. Anything hands-on goes here, not in office hours.
> - Items marked 🛠 are hands-on even though listed under Office Theory's topic — do the *design/reading* part at office, save the actual *coding* for personal time.
>
> Tick `- [ ]` → `- [x]` as you go (or just track via `MY_PROGRESS.md`). If you fall behind, don't skip English or DSA — compress the office theory reading instead (skim vs deep-read).
>
> **Updated 2026-07-08:** restructured into Office-Theory / Personal-Practice columns per user's request; dates re-anchored to start today. Content/order unchanged from the 2026-07-07 gap-fill pass (see [🆕 GAP-FILL ADDITIONS](#-gap-fill-additions-slot-these-into-the-days-above) at the bottom).

---

## 🎯 JOB-HUNT TRACK (runs in PARALLEL with the study weeks — read this first)

> **Added 2026-07-15.** The weekly tables below build SKILL. This track lands the JOB. An employed switcher must apply *while* prepping — the apply→rounds→offer→notice pipeline is itself 6–10 weeks, so applications start in Week 5, not at the end. Do these on weekends + in the gaps; they don't need dedicated weekdays.
>
> **Honesty guardrail (from resume audit):** frame studied topics as "studied/lab"; reserve "production/built/shipped" for the SaaS proof-project + your real Niroskos / SAP / Exotel work. Never claim prod Kafka/gRPC/Mongo/K8s until an artifact exists.

| Weeks | Stream A — Resume & Profile | Stream B — Proof-Project (weekends) | Stream C — Applications & Network |
|---|---|---|---|
| **W1–W3** (now→Jul 28) | Rewrite resume: move studied wins onto paper honestly (observability vocab, mypy/ruff, RFC7807, API versioning/pagination, testing, IaC). Rewrite LinkedIn headline → "Python Backend + Agentic AI". Turn on "Open to work" (recruiters-only). | **Start now, don't wait for W10.** Harden [01_FastAPI_Multi_Tenant_SaaS_starter](Backend_Developer/03_Interview_AnyYear/03_Projects/01_FastAPI_Multi_Tenant_SaaS_starter): thin vertical slice → add pytest+coverage. | Build a target list: 30–40 product companies (India) hiring Python backend / AI. Note who you know at each (referral map). |
| **W4–W6** (Jul 29→Aug 18) | Get resume reviewed (me + 1 senior dev). Write 3 STAR behavioral stories from real work + the project. | Add ONE concurrency fix (transaction lock / race) → red→green → **1-page ADR = interview story**. Then add basic OTel/Prometheus/Sentry. | **Start applying ~5/day (W5).** Referrals first. DM ex-colleagues in English (use interview_english). Track every app in `JOB_TRACKER.md`. |
| **W7–W9** (Aug 19→Sep 8) | Tailor resume per JD (keyword-match to each). Portfolio README polished. | Bolt ONE Agentic feature onto the SaaS (LangGraph/PydanticAI agent endpoint) → you're now genuinely "Backend + Agentic", one story. | Ramp to 8–10 apps/day. Chase referrals hard. Take recruiter screens (out loud, English). |
| **W10–W12** (Sep 9→29) | Iterate resume on what's responding. Prep negotiation. | **Deploy public** (Railway/Render/Fly) → live URL on resume + LinkedIn. | Interview rounds in full swing. Weekly mock w/ me. Convert → offer → give notice. |

**Job-hunt done right = the study plan feeds it, not replaces it.** Every DSA pattern learned → more screens you can pass. Every project milestone → a stronger resume line. Every English mock → a smoother recruiter call.

---

## WEEK 1 (Jul 08 – Jul 14) — Backend Core + DSA Start + English Basics
| Day | Date | 🏢 Office Theory (9–6) | 🌙 Personal — DSA + English |
|---|---|---|---|
| 1 | Jul 08 (Wed) | [01_Python_Advanced](Backend_Developer/01_Year3-4_Mid/01_Python_Advanced) start | DSA: [01_Arrays_Hashing](Backend_Developer/03_Interview_AnyYear/01_DSA/01_Arrays_Hashing) · Eng: [01_sentence_structure](english_speaking/01_Basics/01_sentence_structure.md) |
| 2 | Jul 09 (Thu) | 01_Python_Advanced finish | DSA: 01_Arrays_Hashing cont. · Eng: [02_grammar_basics](english_speaking/01_Basics/02_grammar_basics.md) |
| 3 | Jul 10 (Fri) | [07_Django_DRF](Backend_Developer/00_Year0-2_Junior/07_Django_DRF) — start with [00_django_basics_definition.md](Backend_Developer/00_Year0-2_Junior/07_Django_DRF/00_django_basics_definition.md) 🎯, then skim ORM/ViewSets | DSA: 01_Arrays_Hashing finish · Eng: [03_pronouns](english_speaking/01_Basics/03_pronouns.md) |
| 4 | Jul 11 (Sat) | [06_FastAPI](Backend_Developer/00_Year0-2_Junior/06_FastAPI) start | DSA: [02_Strings](Backend_Developer/03_Interview_AnyYear/01_DSA/02_Strings) · Eng: [04_basic_vocabulary](english_speaking/01_Basics/04_basic_vocabulary.md) |
| 5 | Jul 13 (Mon) | 06_FastAPI cont. | DSA: 02_Strings finish · Eng: [05_basic_speaking_drills](english_speaking/01_Basics/05_basic_speaking_drills.md) |
| 6 | Jul 14 (Tue) | 06_FastAPI cont. | DSA: [03_Linked_List](Backend_Developer/03_Interview_AnyYear/01_DSA/03_Linked_List) · Eng: review — record 2-min voice note, re-listen |

## WEEK 2 (Jul 15 – Jul 21) — Backend Core cont. + English Intermediate start
| Day | Date | 🏢 Office Theory (9–6) | 🌙 Personal — DSA + English |
|---|---|---|---|
| 7 | Jul 15 (Wed) | 06_FastAPI finish | DSA: [04_Stack_Queue](Backend_Developer/03_Interview_AnyYear/01_DSA/04_Stack_Queue) · Eng: [Int-01_tenses_complete](english_speaking/02_Intermediate/01_tenses_complete.md) |
| 8 | Jul 16 (Thu) | [04_Database_SQL](Backend_Developer/00_Year0-2_Junior/04_Database_SQL) start | DSA: 04_Stack_Queue finish · Eng: 01_tenses_complete cont. |
| 9 | Jul 17 (Fri) | 04_Database_SQL cont. | DSA: [05_Binary_Search](Backend_Developer/03_Interview_AnyYear/01_DSA/05_Binary_Search) · Eng: [Int-02_grammar_intermediate](english_speaking/02_Intermediate/02_grammar_intermediate.md) |
| 10 | Jul 18 (Sat) | 04_Database_SQL cont. | DSA: 05_Binary_Search finish · Eng: 02_grammar_intermediate cont. |
| 11 | Jul 20 (Mon) | [08_Redis](Backend_Developer/00_Year0-2_Junior/08_Redis) + [09_Caching](Backend_Developer/00_Year0-2_Junior/09_Caching) | DSA: [06_Two_Pointers_Sliding_Window](Backend_Developer/03_Interview_AnyYear/01_DSA/06_Two_Pointers_Sliding_Window) · Eng: [Int-03_sentence_building](english_speaking/02_Intermediate/03_sentence_building.md) |
| 12 | Jul 21 (Tue) | [10_Testing](Backend_Developer/00_Year0-2_Junior/10_Testing) — theory only, read testing patterns | DSA: 06_Two_Pointers cont. · Eng: 03_sentence_building cont. · 🛠 **build mini-CRUD project** in personal time this week |

## WEEK 3 (Jul 22 – Jul 28) — DSA ramps up + Security/DevOps + English Intermediate
| Day | Date | 🏢 Office Theory (9–6) | 🌙 Personal — DSA + English |
|---|---|---|---|
| 13 | Jul 22 (Wed) | [03_Security](Backend_Developer/01_Year3-4_Mid/03_Security) | DSA: [07_Recursion_Backtracking](Backend_Developer/03_Interview_AnyYear/01_DSA/07_Recursion_Backtracking) · Eng: [Int-04_idioms](english_speaking/02_Intermediate/04_idioms.md) |
| 14 | Jul 23 (Thu) | 03_Security cont. | DSA: 07_Recursion cont. · Eng: [Int-05_phrasal_verbs](english_speaking/02_Intermediate/05_phrasal_verbs.md) |
| 15 | Jul 24 (Fri) | [04_DevOps](Backend_Developer/01_Year3-4_Mid/04_DevOps) | DSA: [08_Sorting_Algorithms](Backend_Developer/03_Interview_AnyYear/01_DSA/08_Sorting_Algorithms) · Eng: [Int-06_intermediate_vocabulary](english_speaking/02_Intermediate/06_intermediate_vocabulary.md) |
| 16 | Jul 25 (Sat) | 04_DevOps cont. | DSA: [09_Trees](Backend_Developer/03_Interview_AnyYear/01_DSA/09_Trees) · Eng: [Int-07_conversation_practice](english_speaking/02_Intermediate/07_conversation_practice.md) |
| 17 | Jul 27 (Mon) | [05_Microservices](Backend_Developer/01_Year3-4_Mid/05_Microservices) | DSA: 09_Trees cont. · Eng: 07_conversation_practice cont. |
| 18 | Jul 28 (Tue) | 05_Microservices cont. | DSA: 09_Trees cont. · Eng: [Adv-01_advanced_grammar](english_speaking/03_Advanced/01_advanced_grammar.md) start |

## WEEK 4 (Jul 29 – Aug 04) — DSA Trees/Heaps/Graphs + Design Patterns + English Advanced
| Day | Date | 🏢 Office Theory (9–6) | 🌙 Personal — DSA + English |
|---|---|---|---|
| 19 | Jul 29 (Wed) | [15_Design_Patterns_SOLID](Backend_Developer/01_Year3-4_Mid/15_Design_Patterns_SOLID) | DSA: 09_Trees finish · Eng: 01_advanced_grammar cont. |
| 20 | Jul 30 (Thu) | 15_Design_Patterns_SOLID cont. | DSA: [10_Heaps_Priority_Queue](Backend_Developer/03_Interview_AnyYear/01_DSA/10_Heaps_Priority_Queue) · Eng: [Adv-02_advanced_vocabulary](english_speaking/03_Advanced/02_advanced_vocabulary.md) |
| 21 | Jul 31 (Fri) | 15_Design_Patterns_SOLID finish | DSA: 10_Heaps finish · Eng: 02_advanced_vocabulary cont. |
| 22 | Aug 01 (Sat) | [HLD_Theory](Backend_Developer/02_Year5+_Senior/01_System_Design/HLD_Theory) 01–08 | DSA: [11_Graphs_BFS_DFS](Backend_Developer/03_Interview_AnyYear/01_DSA/11_Graphs_BFS_DFS) · Eng: [Adv-03_advanced_idioms_phrasal](english_speaking/03_Advanced/03_advanced_idioms_phrasal.md) |
| 23 | Aug 03 (Mon) | HLD_Theory 09–15 | DSA: 11_Graphs cont. · Eng: 03_advanced_idioms_phrasal cont. |
| 24 | Aug 04 (Tue) | HLD_Theory 16–20 | DSA: 11_Graphs cont. · Eng: [Adv-04_pronunciation](english_speaking/03_Advanced/04_pronunciation.md) |

## WEEK 5 (Aug 05 – Aug 11) — Graphs/DP + HLD Theory core + Pronunciation
| Day | Date | 🏢 Office Theory (9–6) | 🌙 Personal — DSA + English |
|---|---|---|---|
| 25 | Aug 05 (Wed) | HLD_Theory 21–26 | DSA: 11_Graphs finish · Eng: 04_pronunciation cont. |
| 26 | Aug 06 (Thu) | HLD_Theory 27–32 | DSA: [12_Dynamic_Programming](Backend_Developer/03_Interview_AnyYear/01_DSA/12_Dynamic_Programming) · Eng: [Adv-05_public_speaking](english_speaking/03_Advanced/05_public_speaking.md) |
| 27 | Aug 07 (Fri) | HLD_Theory 33–38 | DSA: 12_DP cont. · Eng: 05_public_speaking cont. |
| 28 | Aug 08 (Sat) | HLD_Theory 39–44 | DSA: 12_DP cont. · Eng: [Adv-06_interview_english](english_speaking/03_Advanced/06_interview_english.md) start — self-intro |
| 29 | Aug 10 (Mon) | HLD_Theory 45–50 | DSA: 12_DP cont. · Eng: 06_interview_english — project walkthrough |
| 30 | Aug 11 (Tue) | HLD_Theory 51–58 | DSA: 12_DP finish · Eng: 06_interview_english — practice out loud + **1st weekly mock w/ me (English)** 🎤 |

## WEEK 6 (Aug 12 – Aug 18) — Greedy/Trie + HLD Theory finish + LLD + Interview English
| Day | Date | 🏢 Office Theory (9–6) | 🌙 Personal — DSA + English |
|---|---|---|---|
| 31 | Aug 12 (Wed) | HLD_Theory 59–65 (finish) | DSA: [13_Greedy](Backend_Developer/03_Interview_AnyYear/01_DSA/13_Greedy) · Eng: interview_english — system-design narration practice |
| 32 | Aug 13 (Thu) | [LLD_Theory](Backend_Developer/02_Year5+_Senior/01_System_Design/LLD_Theory) SOLID + patterns 1–5 | DSA: 13_Greedy finish · Eng: same, out loud |
| 33 | Aug 14 (Fri) | LLD_Theory patterns 6–12 | DSA: [14_Trie](Backend_Developer/03_Interview_AnyYear/01_DSA/14_Trie) · Eng: HR-round Qs practice |
| 34 | Aug 15 (Sat) | LLD_Theory patterns 13–19 | DSA: [15_Advanced_Graphs](Backend_Developer/03_Interview_AnyYear/01_DSA/15_Advanced_Graphs) · Eng: HR-round Qs cont. |
| 35 | Aug 17 (Mon) | LLD_Theory patterns 20–28 (finish) | DSA: 15_Advanced_Graphs cont. · Eng: record + review voice notes |
| 36 | Aug 18 (Tue) | [LLD_Problems](Backend_Developer/02_Year5+_Senior/01_System_Design/LLD_Problems) — LRU Cache, Parking Lot (read the design, code it in personal time 🛠) | DSA: 15_Advanced_Graphs finish · Eng: **2nd weekly mock** 🎤 |

## WEEK 7 (Aug 19 – Aug 25) — Bit Manip/Intervals + LLD Problems + HLD Problems start
| Day | Date | 🏢 Office Theory (9–6) | 🌙 Personal — DSA + English |
|---|---|---|---|
| 37 | Aug 19 (Wed) | LLD_Problems — Rate Limiter, URL Shortener (design read 🛠) | DSA: [16_Bit_Manipulation](Backend_Developer/03_Interview_AnyYear/01_DSA/16_Bit_Manipulation) · Eng: self-intro polish |
| 38 | Aug 20 (Thu) | [HLD_Problems](Backend_Developer/02_Year5+_Senior/01_System_Design/HLD_Problems)/URL_Shortener.md | DSA: [17_Intervals](Backend_Developer/03_Interview_AnyYear/01_DSA/17_Intervals) · Eng: project walkthrough polish |
| 39 | Aug 21 (Fri) | HLD_Problems/Design_Distributed_Cache.md (Rate Limiter concepts) | DSA: 17_Intervals finish · Eng: mock Q&A |
| 40 | Aug 22 (Sat) | HLD_Problems/Design_API_Gateway.md | DSA: [18_Segment_Tree_Fenwick](Backend_Developer/03_Interview_AnyYear/01_DSA/18_Segment_Tree_Fenwick) · Eng: mock Q&A |
| 41 | Aug 24 (Mon) | HLD_Problems/Design_Twitter_X.md | DSA: 18_Segment_Tree finish · Eng: pronunciation drill |
| 42 | Aug 25 (Tue) | HLD_Problems/Design_YouTube.md | DSA: [19_Math_Number_Theory](Backend_Developer/03_Interview_AnyYear/01_DSA/19_Math_Number_Theory) · Eng: **3rd weekly mock** 🎤 |

## WEEK 8 (Aug 26 – Sep 01) — Matrix/String DP + HLD Problems (products) + AI L1–4 kickoff
| Day | Date | 🏢 Office Theory (9–6) | 🌙 Personal — DSA + English |
|---|---|---|---|
| 43 | Aug 26 (Wed) | HLD_Problems/Design_Instagram_NewsFeed.md | DSA: [20_Matrix_Grid](Backend_Developer/03_Interview_AnyYear/01_DSA/20_Matrix_Grid) · Eng: interview_english review |
| 44 | Aug 27 (Thu) | HLD_Problems/Design_Netflix.md | DSA: [21_String_DP](Backend_Developer/03_Interview_AnyYear/01_DSA/21_String_DP) · Eng: interview_english review |
| 45 | Aug 28 (Fri) | HLD_Problems/Design_WhatsApp_Chat.md | DSA: 21_String_DP finish · Eng: mock Q&A |
| 46 | Aug 29 (Sat) | [Agentic_AI Level1-2](Agentic_AI/Level1_LLM_Foundations) refresh | DSA: [22_Monotonic_Queue](Backend_Developer/03_Interview_AnyYear/01_DSA/22_Monotonic_Queue) · Eng: mock Q&A |
| 47 | Aug 31 (Mon) | [Level3_LLM_APIs_SDKs](Agentic_AI/Level3_LLM_APIs_SDKs) | DSA: [23_Game_Theory_Randomized](Backend_Developer/03_Interview_AnyYear/01_DSA/23_Game_Theory_Randomized) · Eng: pronunciation drill |
| 48 | Sep 01 (Tue) | [Level4_Tool_Use_Function_Calling](Agentic_AI/Level4_Tool_Use_Function_Calling) | DSA: [24_Concurrency_Threading](Backend_Developer/03_Interview_AnyYear/01_DSA/24_Concurrency_Threading) · Eng: **4th weekly mock** 🎤 |

## WEEK 9 (Sep 02 – Sep 08) — DSA niche finish + AI RAG/Agent Patterns
| Day | Date | 🏢 Office Theory (9–6) | 🌙 Personal — DSA + English |
|---|---|---|---|
| 49 | Sep 02 (Wed) | [Level5_RAG_Vector_Databases](Agentic_AI/Level5_RAG_Vector_Databases) start | DSA: [25_Sparse_Table_RMQ](Backend_Developer/03_Interview_AnyYear/01_DSA/25_Sparse_Table_RMQ) · Eng: tech-answer-in-English drill |
| 50 | Sep 03 (Thu) | Level5 RAG cont. | DSA: [26_Suffix_Structures](Backend_Developer/03_Interview_AnyYear/01_DSA/26_Suffix_Structures) · Eng: same |
| 51 | Sep 04 (Fri) | Level5 RAG finish | DSA: [27_Digit_DP](Backend_Developer/03_Interview_AnyYear/01_DSA/27_Digit_DP) · Eng: same |
| 52 | Sep 05 (Sat) | [Level6_Agent_Patterns](Agentic_AI/Level6_Agent_Patterns) start | DSA: [28_Bitmask_DP](Backend_Developer/03_Interview_AnyYear/01_DSA/28_Bitmask_DP) (all patterns done ✅) · Eng: same |
| 53 | Sep 07 (Mon) | Level6 cont. | DSA: Timed mock (2 problems) 🛠 · Eng: same |
| 54 | Sep 08 (Tue) | Level6 finish | DSA: Timed mock (2 problems) 🛠 · Eng: **5th weekly mock** 🎤 |

## WEEK 10 (Sep 09 – Sep 15) — AI Frameworks + Project start + DSA mocks
| Day | Date | 🏢 Office Theory (9–6) | 🌙 Personal — DSA + English |
|---|---|---|---|
| 55 | Sep 09 (Wed) | [Level7_Frameworks](Agentic_AI/Level7_Frameworks) — LangGraph | DSA: Timed mock + weak-pattern revision 🛠 · Eng: pronunciation + self-intro polish |
| 56 | Sep 10 (Thu) | Level7 — MCP | DSA: Timed mock 🛠 · Eng: same |
| 57 | Sep 11 (Fri) | Level7 — LlamaIndex/PydanticAI (skim) | DSA: Timed mock 🛠 · Eng: same |
| 58 | Sep 12 (Sat) | [Level8_Production_LLMOps](Agentic_AI/Level8_Production_LLMOps) — observability, guardrails | DSA: Timed mock 🛠 · Eng: same |
| 59 | Sep 14 (Mon) | Read project spec — [Agentic_AI/Projects](Agentic_AI/Projects) or [Backend Projects](Backend_Developer/03_Interview_AnyYear/03_Projects) | DSA: Timed mock 🛠 · Eng: same · 🛠 **start portfolio project build** in personal time |
| 60 | Sep 15 (Tue) | Project design notes cont. | DSA: Timed mock 🛠 · Eng: **6th weekly mock** 🎤 · 🛠 project build cont. |

## WEEK 11 (Sep 16 – Sep 22) — Project build + Mock interviews (SD + DSA)
| Day | Date | 🏢 Office Theory (9–6) | 🌙 Personal — DSA + English |
|---|---|---|---|
| 61 | Sep 16 (Wed) | re-read relevant HLD/LLD theory for project design | DSA: Timed mock (2 problems) 🛠 · Eng: mock SD explained in English · 🛠 project build cont. |
| 62 | Sep 17 (Thu) | same | DSA: Timed mock 🛠 · Eng: mock SD in English · 🛠 project build cont. |
| 63 | Sep 18 (Fri) | same | DSA: Timed mock 🛠 · Eng: mock SD in English · 🛠 project build cont. |
| 64 | Sep 19 (Sat) | same | DSA: Timed mock 🛠 · Eng: mock behavioral Q in English · 🛠 project build cont. |
| 65 | Sep 21 (Mon) | same | DSA: Timed mock 🛠 · Eng: mock behavioral Q in English · 🛠 project — polish + README |
| 66 | Sep 22 (Tue) | same | DSA: Timed mock 🛠 · Eng: **7th weekly mock** 🎤 · 🛠 **deploy project** 🎯 |

## WEEK 12 (Sep 23 – Sep 29) — Final Polish (Interview Prep + Resume + Full Mocks)
| Day | Date | 🏢 Office Theory (9–6) | 🌙 Personal — DSA + English |
|---|---|---|---|
| 67 | Sep 23 (Wed) | [02_Interview_Prep](Backend_Developer/03_Interview_AnyYear/02_Interview_Prep) — 50 SD Qs | DSA: Timed mock 🛠 · Eng: interview_english final polish |
| 68 | Sep 24 (Thu) | 02_Interview_Prep — SQL Qs + Python tricky Qs | DSA: Timed mock 🛠 · Eng: same |
| 69 | Sep 25 (Fri) | 02_Interview_Prep — behavioral + resume | DSA: Timed mock 🛠 · Eng: same |
| 70 | Sep 26 (Sat) | 02_Interview_Prep — negotiation | DSA: Timed mock 🛠 · Eng: same |
| 71 | Sep 28 (Mon) | [Agentic_AI/Interview_Prep](Agentic_AI/Interview_Prep) | DSA: Timed mock 🛠 · Eng: full mock interview (English) |
| 72 | Sep 29 (Tue) | Resume final check | DSA: **Full mock: 2 DSA + 1 SD + 1 behavioral, timed** 🛠 · Eng: **Final mock w/ me** 🎤 |

---

## 📝 Daily discipline
- Log 3 lines in `MY_PROGRESS.md` every day (what you studied at office / what you coded in personal time / tomorrow's plan).
- Never skip DSA or the 30-min English block — everything else can flex.
- Office hours = reading only. If you only get through half the day's theory item, carry the rest to tomorrow rather than starting DSA/coding at office.
- Weekly mock (marked 🎤) = tell me the answer **out loud in English**, I'll correct like a teacher, then we move on.
- Sundays are rest/catch-up — not listed above, use them to repeat any day you fell behind on.

Master reference: [00_START_HERE.md](00_START_HERE.md) · [STUDY_PLAN.md](STUDY_PLAN.md) · [english_speaking/README.md](english_speaking/README.md)

---

## 🆕 GAP-FILL ADDITIONS (slot these into the days above — all office-theory reads)

> A full gap-analysis pass (2026-07) found real, missing topics across both repos and added ~30 new files. Everything below is genuinely new — none of it existed when this plan was first built. Read each on the day/week noted, during office theory time; they slot into existing topic blocks, they don't need extra days.

### 🔴 Read this one regardless of where you are in the plan
- **[00_django_basics_definition.md](Backend_Developer/00_Year0-2_Junior/07_Django_DRF/00_django_basics_definition.md)** — the plain-English "what is Django" answer + MVT + practice drill. This is the exact gap that started this whole plan. Read it TODAY if you haven't yet, don't wait for Day 3.

### Week 2 (Day 8–12 — Database_SQL / Redis block)
- [31_normalization_denormalization.md](Backend_Developer/00_Year0-2_Junior/04_Database_SQL/31_normalization_denormalization.md) — 1NF/2NF/3NF, another "basics you forget under pressure" topic
- [32_stored_procedures_triggers.md](Backend_Developer/00_Year0-2_Junior/04_Database_SQL/32_stored_procedures_triggers.md)
- [33_foreign_data_wrappers.md](Backend_Developer/00_Year0-2_Junior/04_Database_SQL/33_foreign_data_wrappers.md)
- [34_savepoints_nested_transactions.md](Backend_Developer/00_Year0-2_Junior/04_Database_SQL/34_savepoints_nested_transactions.md)
- [05_MySQL/theory/08_window_functions_cte_partitioning.md](Backend_Developer/00_Year0-2_Junior/05_MySQL/theory/08_window_functions_cte_partitioning.md), [09_galera_ndb_clustering.md](Backend_Developer/00_Year0-2_Junior/05_MySQL/theory/09_galera_ndb_clustering.md), [10_charset_collation.md](Backend_Developer/00_Year0-2_Junior/05_MySQL/theory/10_charset_collation.md) — MySQL, if a JD needs it
- [08_Redis/theory/10_pubsub_fundamentals.md](Backend_Developer/00_Year0-2_Junior/08_Redis/theory/10_pubsub_fundamentals.md)

### Week 1 (Day 4–6 — FastAPI block)
- [41_fastapi_rate_limiting.md](Backend_Developer/00_Year0-2_Junior/06_FastAPI/41_fastapi_rate_limiting.md)
- [42_fastapi_staticfiles_mount.md](Backend_Developer/00_Year0-2_Junior/06_FastAPI/42_fastapi_staticfiles_mount.md)
- [43_drf_content_negotiation.md](Backend_Developer/00_Year0-2_Junior/07_Django_DRF/43_drf_content_negotiation.md) — DRF, same block as Day 3's Django basics

### Week 3 (Day 13–18 — Security/DevOps/Microservices block)
- [21_container_image_security.md](Backend_Developer/01_Year3-4_Mid/03_Security/21_container_image_security.md)
- [20_blue_green_deployment.md](Backend_Developer/01_Year3-4_Mid/04_DevOps/20_blue_green_deployment.md), [21_ingress_controller.md](Backend_Developer/01_Year3-4_Mid/04_DevOps/21_ingress_controller.md)
- [03_github_actions_cicd.md](Backend_Developer/01_Year3-4_Mid/04_DevOps/03_github_actions_cicd.md) Q8–Q10 (artifacts, self-hosted runners, monorepo CI) — extended, not new file
- [02_Year5+_Senior/03_Senior_Leadership/12_mental_models_decision_making.md](Backend_Developer/02_Year5+_Senior/03_Senior_Leadership/12_mental_models_decision_making.md) — first-principles/inversion/second-order thinking, great for system-design interview reasoning

### Week 6–7 (Day 31–42 — JD-specific "should/skim" topics, only if relevant)
- [06_gRPC/13_grpc_client_side_load_balancing.md](Backend_Developer/01_Year3-4_Mid/06_gRPC/13_grpc_client_side_load_balancing.md)
- [07_Kafka/08_ordering_guarantees.md](Backend_Developer/01_Year3-4_Mid/07_Kafka/08_ordering_guarantees.md), [09_consumer_lag_monitoring.md](Backend_Developer/01_Year3-4_Mid/07_Kafka/09_consumer_lag_monitoring.md)
- [08_RabbitMQ/theory/08_clustering_delayed_alternate_exchange.md](Backend_Developer/01_Year3-4_Mid/08_RabbitMQ/theory/08_clustering_delayed_alternate_exchange.md)
- [09_Celery/theory/10_testing_idempotency.md](Backend_Developer/01_Year3-4_Mid/09_Celery/theory/10_testing_idempotency.md)
- [10_MongoDB/theory/09_gridfs.md](Backend_Developer/01_Year3-4_Mid/10_MongoDB/theory/09_gridfs.md)
- [11_Elasticsearch/theory/10_nested_object_percolator.md](Backend_Developer/01_Year3-4_Mid/11_Elasticsearch/theory/10_nested_object_percolator.md)
- [12_GraphQL/08_error_handling_conventions.md](Backend_Developer/01_Year3-4_Mid/12_GraphQL/08_error_handling_conventions.md)
- [13_WebSocket_SSE/05_socketio_stomp_alternative_protocols.md](Backend_Developer/01_Year3-4_Mid/13_WebSocket_SSE/05_socketio_stomp_alternative_protocols.md)
- [02_Architecture_Patterns/Section_03_Distributed_Systems/06_Sidecar_Ambassador_Patterns.md](Backend_Developer/02_Year5+_Senior/02_Architecture_Patterns/Section_03_Distributed_Systems/06_Sidecar_Ambassador_Patterns.md)

### Week 5 (Day 25–30 — HLD Theory block)
- [HLD_Theory/66_Dynamo_Style_Consistency.md](Backend_Developer/02_Year5+_Senior/01_System_Design/HLD_Theory/66_Dynamo_Style_Consistency.md) — gossip protocol, quorum reads/writes, hinted handoff, anti-entropy (read alongside file 62 Raft/Paxos)

### Week 8–10 (Day 43–60 — Agentic AI block)
- [Level1_LLM_Foundations/08_world_models_theory_of_mind.md](Agentic_AI/Level1_LLM_Foundations/08_world_models_theory_of_mind.md)
- [Level5_RAG_Vector_Databases/10_contextual_retrieval.md](Agentic_AI/Level5_RAG_Vector_Databases/10_contextual_retrieval.md) — Anthropic's technique, read alongside hybrid search/reranking
- [Level6_Agent_Patterns/12_agent_harness_engineering.md](Agentic_AI/Level6_Agent_Patterns/12_agent_harness_engineering.md) ⭐ — very current, read this one for sure
- [Level7_Frameworks/10_a2a_protocol.md](Agentic_AI/Level7_Frameworks/10_a2a_protocol.md), [11_haystack.md](Agentic_AI/Level7_Frameworks/11_haystack.md)
- [Modern_Topics/11_coding_agent_harness_deep_dive.md](Agentic_AI/Modern_Topics/11_coding_agent_harness_deep_dive.md) ⭐ — pairs with Level6 Doc 12 above, directly explains how the tool you're using right now (Claude Code) works

MASTER_INDEX.md for Agentic_AI is already updated with all these — cross-check there if a link above ever goes stale.
