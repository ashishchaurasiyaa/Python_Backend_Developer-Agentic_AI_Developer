# System Design Practice Drills — Timed, Self-Graded

> `HLD_Problems/` me 36 walkthroughs hain — wo **padhne** ke liye hain. Yeh file **bolne/likhne** ke liye hai: timer, structure, rubric. System design akela practice karne ka sabse bada problem yeh hai ki "padh liya" aur "bol sakta hoon" me 10x gap hota hai, aur woh gap sirf timed attempt + honest self-grading se pata chalta hai.

## Kaise use karo

```
1. Ek drill uthao (neeche 12 hain, difficulty order me)
2. TIMER: 45 minutes. Blank page/whiteboard. Notes band.
3. Bolke karo — literally out loud, ya voice memo record karo.
   (Bonus: spoken English practice bhi ho jaati hai — do birds, one stone)
4. Time khatam → rubric se KHUD grade karo (neeche)
5. Phir HLD_Problems/ ka corresponding file kholo aur compare karo
6. Jo miss hua wo "Gap log" me likho. 1 week baad wahi drill dobara.
```

---

## The 45-minute structure (yehi interview ka actual flow hai)

```
0-5 min    REQUIREMENTS
           Functional: 3-5 core features (scope cut karo — "v1 me yeh nahi")
           Non-functional: scale, latency target, consistency needs, availability
           Clarifying questions POOCHO — interviewer expect karta hai

5-10 min   ESTIMATION (back-of-envelope)
           DAU → QPS (peak = avg × 3-5) → storage/day → bandwidth
           Ek number bolo, assumption bolo. Perfect math nahi chahiye.

10-15 min  API + DATA MODEL
           3-4 endpoints (ya events). Core tables/collections + key indexes.
           Yahi wo hissa hai jo backend devs sabse achha karte hain — use it.

15-30 min  HIGH-LEVEL DESIGN
           Boxes + arrows: client → LB → service(s) → cache → DB → queue → workers
           Har box ke liye ek line: kyun hai, kya karta hai

30-40 min  DEEP DIVE (interviewer ka favourite hissa)
           Bottleneck identify karo aur solve karo:
           hot key? sharding key? read-heavy → replica/cache?
           write-heavy → queue/batch? consistency? failure mode?

40-45 min  TRADE-OFFS + WRAP
           "SQL chuna kyunki X; agar Y hota to NoSQL"
           Failure modes, monitoring, kya v2 me karoge
```

---

## Self-grading rubric (100 points)

| Area | Points | Full marks tab jab... |
|---|---|---|
| **Requirements & scope** | 15 | Functional + non-functional dono; scope cut kiya; clarifying Qs poochhe |
| **Estimation** | 10 | QPS + storage numbers with stated assumptions; numbers design ko drive karte hain |
| **API & data model** | 15 | Concrete endpoints/schema; indexes; partition/shard key named |
| **High-level architecture** | 20 | Har component justified; koi magic box nahi; data flow clear |
| **Deep dive** | 20 | Kam se kam 2 bottlenecks identify + solve kiye; numbers se justify |
| **Trade-offs** | 15 | "X chuna kyunki…, cost yeh hai" — dono side bole |
| **Communication** | 5 | Structured, timeboxed, interviewer ko saath le kar chale |

```
Scoring:
  < 50   → concept gaps hain; us topic ka HLD_Theory doc dobara padho
  50-70  → knowledge hai, structure weak; format pe drill karo
  70-85  → interview-ready for most companies
  85+    → strong hire signal; ab sirf breadth badhao
```

**Honest grading ka rule:** jo tumne **bola nahi**, wo count nahi hota — chahe tumhe pata ho. Interview me bhi yahi hota hai.

---

## Drill list (difficulty order — top se shuru karo)

### Tier 1 — Warm-ups (pehle yeh 4, har ek 2 baar)
| # | Drill | Focus | Reference |
|---|---|---|---|
| 1 | URL Shortener | Hashing, ID generation, read-heavy caching | [URL_Shortener](HLD_Problems/URL_Shortener.md) |
| 2 | Pastebin | Storage, TTL/expiry, CDN | [Design_Pastebin](HLD_Problems/Design_Pastebin.md) |
| 3 | Rate Limiter (service-level) | Algorithms, distributed counters, Redis | [Rate_Limiter](LLD_Problems/Rate_Limiter.md) |
| 4 | Gaming Leaderboard | Redis ZSET, rank queries, sharding by score | [Design_Gaming_Leaderboard](HLD_Problems/Design_Gaming_Leaderboard.md) |

### Tier 2 — Core (interview me sabse zyada aate hain)
| # | Drill | Focus | Reference |
|---|---|---|---|
| 5 | Twitter/X Feed | Fan-out on write vs read, celebrity problem | [Design_Twitter_X](HLD_Problems/Design_Twitter_X.md) |
| 6 | WhatsApp Chat | WebSocket at scale, delivery/ordering, offline | [Design_WhatsApp_Chat](HLD_Problems/Design_WhatsApp_Chat.md) |
| 7 | Uber/Ride Matching | Geospatial index, real-time matching, state machine | [Design_Uber_Maps](HLD_Problems/Design_Uber_Maps.md) |
| 8 | BookMyShow (seat booking) | Concurrency, locking, exactly-once payment | [Design_BookMyShow](HLD_Problems/Design_BookMyShow.md) |

### Tier 3 — Senior differentiators
| # | Drill | Focus | Reference |
|---|---|---|---|
| 9 | Distributed Message Queue | Log storage, replication/ISR, consumer groups | [Design_Distributed_Message_Queue](HLD_Problems/Design_Distributed_Message_Queue.md) |
| 10 | Google Docs (collaborative) | OT vs CRDT, conflict resolution | [Design_Google_Docs](HLD_Problems/Design_Google_Docs.md) |
| 11 | Multi-Tenant SaaS | Isolation models, noisy neighbour, per-tenant limits | [Design_Multi_Tenant_SaaS](HLD_Problems/Design_Multi_Tenant_SaaS.md) |
| 12 | RAG / LLM Backend | Vector store, chunking, cost/latency, evals | [Design_RAG_System](HLD_Problems/Design_RAG_System.md) |

> Drill 12 tumhara **differentiator** hai — Backend + Agentic combo wali positioning yahi cash hoti hai. Ise 3 baar karo, dusron se zyada.

---

## Gap log (yeh table apne notes me maintain karo)

```
| Date | Drill | Score | Kya miss hua | Retry date |
|------|-------|-------|--------------|-----------|
| 08-05| URL Shortener | 62 | estimation skip kiya, cache eviction nahi bola | 08-12 |
```

Pattern dikhega 3-4 drills ke baad — zyadatar log ka **same** hissa miss hota hai (usually estimation ya trade-offs). Wahi tumhara asli gap hai, poora syllabus nahi.

---

## LLD drills (alag skill — coding round me aata hai)

45 min, par yahan **code likhna** hai (classes, interfaces, ek working flow):

| # | Drill | Focus |
|---|---|---|
| L1 | Parking Lot | Class design, enums, strategy for pricing |
| L2 | Elevator System | State machine, scheduling algorithm |
| L3 | Splitwise | Balance graph, settlement algorithm |
| L4 | Rate Limiter (in-process) | Token bucket, thread-safety |
| L5 | Notification System | Strategy + observer, retry/DLQ |

Rubric alag: SOLID adherence (25), extensibility — naya requirement add karna kitna aasan (25), working code (25), edge cases + concurrency (25). References: [LLD_Problems/](LLD_Problems/)

---

## 4-week plan

```
Week 1: Tier 1 ke 4 drills, har ek 2 baar (2nd attempt me score 15+ badhna chahiye)
Week 2: Tier 2 ke 4 drills, ek-ek baar + Week 1 ka lowest-score wala repeat
Week 3: Tier 3 ke 4 drills (RAG wala 2 baar)
Week 4: LLD ke 5 drills + gap log ke top-3 repeats
```

Ek din me ek hi drill. 45 min drill + 20 min comparison/grading = ~1 ghanta. Isse zyada karne se quality girti hai.

---

**Related:** [SYSTEM_DESIGN_CHECKLIST](SYSTEM_DESIGN_CHECKLIST.md) (theory coverage) · [HLD_Theory/](HLD_Theory/) (67 concepts) · [HLD_Problems/](HLD_Problems/) (36 walkthroughs) · [DSA practice harness](../../03_Interview_AnyYear/01_DSA/practice/)
