# DSA Round Strategy — How the Round Is Actually Run and Judged

> This is not a problem list — [`01_DSA/TOP_INTERVIEW_QUESTIONS.md`](../01_DSA/TOP_INTERVIEW_QUESTIONS.md) and [`00_Coding_Patterns_Index.md`](../01_DSA/00_Coding_Patterns_Index.md) are that. This is the **meta-game**: what the round actually looks like at different company tiers, what the interviewer is scoring underneath the code, the communication protocol that turns a correct solution into a strong signal, and what to do when you're stuck. Pair this with the timed practice loop in [`01_DSA/practice/`](../01_DSA/practice/) — reading this won't help until you run it live.

---

## 1. What the round actually looks like, by company tier

The format changes more than the difficulty does. Knowing which format you're walking into changes how you should pace yourself.

| Tier | Typical format | Problem count | What's actually being tested |
|---|---|---|---|
| **Big product / FAANG-adjacent** | 45 min, 1 problem (sometimes 2 related — a follow-up extension of the first) | 1–2 | Depth: can you optimize brute force → optimal live, handle the follow-up twist |
| **India product companies** (Flipkart, Swiggy, CRED, Razorpay, Zeta, Navi, PhonePe) | 45–60 min, 1–2 problems, often followed by a separate LLD round same day | 1–2 | Same as above, plus how you talk through trade-offs — these companies weight communication heavily |
| **Service companies** (TCS, Infosys, Wipro, Cognizant-tier) | Online assessment (HackerRank/HackerEarth) first, then a shorter verbal round | 2–4 in the OA, 1 verbal | Correctness under a hard timer in the OA; basic articulation in the verbal round — depth expectations are lower |
| **Startups (Series A–C)** | Often a take-home or a longer 90-min pairing session | 1–3, sometimes open-ended | Whether you can build something working under ambiguity, not just solve a canned pattern |

**Why this matters:** pacing a FAANG-style single-hard-problem round like a service-company OA (rushing to a brute force fast) reads as shallow. Pacing a service-company OA like a FAANG round (spending 15 minutes reasoning about one problem) means you don't finish. Ask the recruiter for the format in advance — it's a normal question, not a red flag to ask it.

---

## 2. The first two minutes decide the round more than the last twenty

Interviewers form a strong first impression from **how you receive the problem**, before you've written a line of code. This is the single most under-invested part of most candidates' prep.

**The clarifying-question checklist — run this every time, even when the problem seems obvious:**

- **Input constraints:** What's the size of `n`? (`n ≤ 20` hints at exponential/backtracking being fine; `n ≤ 10^5` rules out O(n²); `n ≤ 10^9` hints at O(log n) or O(1))
- **Value ranges:** Can numbers be negative? Zero? Duplicates allowed?
- **Edge cases out loud:** Empty input? Single element? What should happen — error, or a defined return value?
- **Output shape:** Exact format expected — sorted? Any valid answer among several? Indices or values?
- **Mutability:** Can you modify the input in place, or must it be preserved?

**Why this is scored, not just polite:** a candidate who asks "what's the range of `n`?" before coding is signaling they think about complexity *before* writing code, not after it TLEs. This single habit is one of the highest-leverage two minutes in the entire round.

---

## 3. The protocol — say the approach before you write a line

This is the exact protocol used in [`01_DSA/practice/README.md`](../01_DSA/practice/README.md)'s "yehi asli value hai" section, expanded for a live interview specifically:

```
1. RESTATE the problem in your own words (confirms you understood it correctly — catches
   misreadings before they cost you 15 minutes).
2. NAME the pattern out loud: "This looks like a sliding window because we need a contiguous
   subarray satisfying a condition." Silent pattern-matching in your head reads as guessing.
3. STATE the brute force AND its complexity, even if you're not going to code it:
   "Brute force is O(n²) — check every pair. We can do better with a hashmap for O(n)."
   This proves you can identify the naive solution and reason about why it's insufficient —
   skipping straight to the optimal solution without mentioning the brute force actually reads
   as WORSE, because the interviewer can't tell if you evaluated alternatives or got lucky.
4. WALK THROUGH the approach on a small example BEFORE coding — on paper/whiteboard/verbally.
   Catches logic errors when they cost 30 seconds instead of after 10 minutes of coding.
5. CODE, narrating major decisions ("using a deque here so I can pop from both ends in O(1)").
   Silent coding for 10+ minutes is the single most common complaint interviewers report —
   they can't score what they can't observe.
6. TEST against the example you walked through, then explicitly against edge cases
   (empty, single element, all-same-value) — out loud, before the interviewer has to ask.
7. STATE final time/space complexity unprompted.
```

**The failure mode this prevents:** a candidate who codes correctly in silence and gets the right answer often scores *lower* than one who talks through a slightly rockier path to the same answer — because the interviewer is scoring the demonstrated thought process, not just the final diff.

---

## 4. What's actually being scored (the rubric behind the rubric)

Most companies use some version of this four-axis rubric, even when they don't share it with you:

| Axis | What it means | How it's graded |
|---|---|---|
| **Problem solving** | Did you reach a correct, efficient approach, and how much hinting did it take? | Independent > needed one nudge > needed heavy guidance |
| **Coding** | Is the code clean, correctly handles edge cases, compiles/runs (mentally or actually)? | Syntax slips are usually forgiven if caught and fixed; logic bugs are not |
| **Communication** | Could someone else follow your reasoning without re-deriving it themselves? | This is the axis most candidates under-invest in relative to its weight |
| **Verification** | Did you test your own solution, or did the interviewer have to find the bug? | Self-caught bugs score *better* than "correct on the first try with no verification shown" |

**The counterintuitive part:** a candidate who writes buggy code but talks through it well, catches their own bug via testing, and fixes it — often outscores a silent candidate who happened to write bug-free code the first time. The interview is evaluating how you work, because that's what the job actually is.

---

## 5. When you're stuck — the recovery protocol

Getting stuck is normal and expected; how you recover is what's being watched.

```
STUCK for ~2 minutes with no progress →
  1. Re-read the problem. Say out loud what you know and don't know yet.
  2. Try a SMALLER example by hand — n=2 or n=3 — look for the pattern manually.
  3. Ask: "Can I trade space for time?" (hashmap/set for O(1) lookup)
       "Can I sort first?" (unlocks two-pointer/binary-search approaches)
       "Is there a brute force I can start coding while I think about the optimization?"
  4. If truly stuck after ~5 more minutes: ASK for a hint. "I'm considering two approaches —
     could you point me toward whether one of these is more promising?"
     This is not a failure. Interviewers expect it, and candidates who ask for a
     well-framed hint (showing what they've already tried) score better than
     candidates who silently spiral for ten minutes.
```

**What actually hurts your score:** going silent for an extended stretch, restarting from scratch repeatedly without converging, or bluffing a wrong complexity claim rather than saying "let me think about that."

---

## 6. The follow-up question — the part FAANG-tier rounds are actually testing

The first solution is often table stakes; the follow-up is where the round is decided.

- *"Can you do it in O(1) space?"*
- *"What if the input doesn't fit in memory?"*
- *"What if this needs to run on a stream, not a static array?"*
- *"How would this change if there could be duplicates / negative numbers / it needed to be thread-safe?"*

**Prep implication:** for your strongest 15–20 practiced problems, deliberately think through one plausible follow-up for each — not to memorize an answer, but to build the reflex of treating the first solution as a starting point, not the finish line.

---

## 7. Common failure modes (in order of how often they actually sink candidates)

1. **Jumping to code before clarifying anything.** Reads as impulsive, and often means re-deriving mid-code when a misunderstanding surfaces.
2. **Going silent for 5+ minutes.** The interviewer has nothing to score and starts assuming the worst.
3. **Claiming a complexity without deriving it.** "This is O(n log n)" without being able to explain why, when pressed, is worse than not stating a complexity at all.
4. **Not testing your own code.** Handing a solution to the interviewer and waiting for them to find the bug is a wasted opportunity — self-testing is free credibility.
5. **Over-engineering a simple problem.** Building a generic, heavily abstracted solution for a problem that needed 10 direct lines signals poor judgment about when abstraction is warranted, not skill.
6. **Freezing on the follow-up.** Treating the first correct answer as "done" and being visibly thrown when asked to extend it.

---

## 8. Preparation cadence that actually works

Cramming problems the week before does not fix weak fundamentals — it produces pattern-recognition that collapses under a slightly-varied problem. The cadence below, cross-referenced with the repo's own tools:

| Phase | What | Where |
|---|---|---|
| **Weeks 1–2** | Build pattern recognition — one problem per major pattern, verified, not just read | [`01_DSA/practice/`](../01_DSA/practice/) — 35 problems, self-checking harness |
| **Weeks 3–6** | Volume — company-tagged problems at your target companies | [`2_Month_DSA_5_Problems_Per_Day_WITH_LINKS_AND_COMPANY_TAGS.docx`](../01_DSA/2_Month_DSA_5_Problems_Per_Day_WITH_LINKS_AND_COMPANY_TAGS.docx) |
| **Weeks 5–8 (parallel)** | Timed, narrated mock attempts — practicing the protocol in Section 3, not just the algorithm | Pair with a friend, or record yourself narrating a solve out loud — the narration habit doesn't form silently |
| **Ongoing** | Spaced repetition — the same problem 3 days later, from a blank file | [`01_DSA/practice/README.md`](../01_DSA/practice/README.md)'s protocol, step 6 |

**The mistake this table is designed to prevent:** doing 150 problems silently and alone, then discovering in the actual interview that narrating your thought process live, under time pressure, in front of someone watching, is a different skill than solving in a quiet room — and that skill only builds by practicing it out loud beforehand, not during the interview itself.

---

**Related:** pattern reference — [`00_Coding_Patterns_Index.md`](../01_DSA/00_Coding_Patterns_Index.md). Decision trees for picking an approach — [`00_Approach_Flowcharts.md`](../01_DSA/00_Approach_Flowcharts.md). Backend-specific coding-round recipes (schema design under a timer, not pure algorithms) — [`06_backend_coding_round_patterns.md`](06_backend_coding_round_patterns.md). Timed system-design drills with the same self-graded-rubric philosophy — [`02_Year5+_Senior/01_System_Design/PRACTICE_DRILLS.md`](../../02_Year5+_Senior/01_System_Design/PRACTICE_DRILLS.md).
