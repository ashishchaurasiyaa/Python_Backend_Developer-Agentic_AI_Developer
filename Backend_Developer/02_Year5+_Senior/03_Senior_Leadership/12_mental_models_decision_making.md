# 🧠 Mental Models for Senior Engineering Decision-Making

> **Target:** 5+ YOE | **Goal:** Structured thinking tools senior engineers use to make good decisions FAST, under uncertainty, without re-deriving everything from scratch each time.

---

## Part 1: WHAT — Mental Models, and Why Seniors Need Them

### Definition

> A **mental model** is a reusable framework for thinking through a problem —
> not a fact to memorize, but a LENS to look through. Senior engineers are
> distinguished less by knowing more facts than by having a bigger toolkit
> of mental models to reach for when a new, unfamiliar problem shows up.

**Real-Life Analogy 🧰**

A junior engineer facing a new problem often starts from zero — re-deriving
an approach from scratch. A senior engineer pattern-matches: "this smells
like a producer-consumer problem," "this is a classic build-vs-buy
tradeoff," "this needs first-principles thinking because there's no
existing precedent." Mental models are the pattern library that makes that
fast.

Senior interview: this whole file is really answering the follow-up
question behind EVERY system-design interview — not "do you know sharding,"
but "HOW do you decide what to reach for when the problem in front of you
doesn't map cleanly to anything you've memorized."

---

## Part 2: The Core Mental Models

### 1. First-Principles Thinking

```
Instead of reasoning by ANALOGY ("we'll do it the way Netflix does it"),
break the problem down to its FUNDAMENTAL, undeniable truths, and
reason UP from there.

Example: "Should we use microservices?"
  Analogy-based: "Netflix/Amazon use microservices, so should we"
  First-principles: "What's our ACTUAL problem? Team of 4, one product,
  no scaling pain yet → the fundamental truths (small team, low complexity)
  point AWAY from microservices, regardless of what Netflix does."
```

**When to use it:** whenever you catch yourself reasoning "X company does
it this way" as the ENTIRE justification — that's a signal to stop and ask
what the underlying constraints actually are for YOUR situation specifically.

### 2. Inversion (Charlie Munger's "invert, always invert")

```
Instead of asking "how do we succeed at X," ask "what would GUARANTEE
we fail at X, and how do we avoid that."

Example: "How do we ensure this migration goes smoothly?"
  Forward: brainstorm everything that could go right (often vague, aspirational)
  Inverted: "What would make this migration a DISASTER?" →
    - No rollback plan
    - No feature flag to cut traffic gradually
    - Migrating on a Friday
    - No monitoring on the new path before cutover
  → Now you have a concrete checklist of things to explicitly NOT do.
```

**Why this works better than forward-planning alone:** it's often
psychologically easier to spot failure modes than to imagine every path to
success — inversion surfaces concrete risks that "let's just plan carefully"
tends to miss.

### 3. Second-Order Thinking

```
FIRST-order: what happens immediately as a direct result of this decision?
SECOND-order: what happens AS A RESULT of that first effect, and the
              effect after that?

Example: "Let's add a cache to speed up this endpoint."
  1st order: endpoint gets faster ✅
  2nd order: now there's a cache invalidation problem — stale data risk
  3rd order: team adds complexity to handle invalidation correctly,
             on-call burden increases, debugging "why is this data stale"
             becomes a recurring incident category
```

Directly relevant to your existing System Design coverage — most system
design tradeoffs (caching, denormalization, async processing) are exactly
this: attractive first-order benefits, real second/third-order costs that
interviewers specifically probe for ("what's the DOWNSIDE of this
approach") to see if you're only thinking one step ahead.

### 4. Occam's Razor (in an engineering context)

```
Among explanations/solutions that fit the evidence equally well,
prefer the SIMPLER one.

Debugging example: a service is slow. Two hypotheses:
  A) A rare race condition in custom connection-pooling code
  B) The connection pool size is just misconfigured too low
Occam's razor: check B first — it's simpler, faster to verify, and
statistically far more common than exotic concurrency bugs.
```

**Engineering-specific version:** "it's probably not a compiler bug" — the
more mundane, boring explanation is usually correct; reach for exotic
explanations only after ruling out the boring ones.

### 5. Systems Thinking

```
Instead of analyzing a component in ISOLATION, understand it as part of
a system of interacting parts with FEEDBACK LOOPS.

Example: "Why did adding more servers make the outage WORSE?"
  Component view: "more servers = more capacity = should help"
  Systems view: more servers → more connections opened to the shared
  database → database connection pool EXHAUSTED → database becomes the
  new bottleneck → the "fix" made total system throughput WORSE, because
  the real constraint was never compute capacity in the first place.
```

Ties directly to your existing distributed-systems coverage — this is
exactly the reasoning behind identifying the ACTUAL bottleneck (via
profiling/monitoring, `05_prometheus_grafana.md`) before reaching for a fix,
rather than assuming the obvious-looking constraint is the real one.

### 6. The Map Is Not the Territory

```
Your architecture diagram, your mental model of "how the system works,"
your documentation — these are all SIMPLIFICATIONS (maps) of the real,
messier system (the territory). They will eventually diverge from reality
as the system evolves.

Practical implication: when debugging a production issue, TRUST what
the system is actually doing (logs, traces, metrics — the territory)
over what the architecture diagram/your mental model SAYS it should be
doing (the map). "That's not supposed to be possible" is a signal your
map is outdated, not that the observation is wrong.
```

### 7. Reversible vs Irreversible Decisions (Bezos's "Type 1 vs Type 2")

```
Type 1 (irreversible, "one-way door"): choosing a database engine for a
  core system, a public API contract, a company-wide auth strategy —
  deserves slow, careful, heavily-analyzed decision-making

Type 2 (reversible, "two-way door"): which library to use for a small
  internal tool, a feature flag's default value, a config parameter —
  should be decided FAST, by whoever's closest to the problem, and
  fixed later if wrong
```

**Why this matters for senior engineers specifically:** a common failure
mode is applying Type-1-level analysis paralysis to Type-2 decisions
(bikeshedding a reversible choice for weeks) while sometimes rushing genuine
Type-1 decisions. Explicitly categorizing which type a decision is BEFORE
debating it is the actual skill — this is the same judgment underlying
[Pattern_Selection_Framework](../02_Architecture_Patterns/Section_09_Architectural_Decision_Making/03_Pattern_Selection_Framework.md)'s
architecture-choice guidance and `11_rfc_adr_writing.md`'s "when do you
actually need an RFC" judgment call.

### 8. Chesterton's Fence

```
Before removing something that seems useless/wrong ("why is this weird
retry-with-3-second-sleep here, that's obviously bad code"), find out
WHY it was put there in the first place.

The "obviously bad" code often exists because of a specific incident
or edge case the current reader doesn't have context on — removing it
without understanding reintroduces the original bug.
```

Directly applicable to legacy-code work — the instinct to "clean up" code
you don't immediately understand is exactly where this model earns its
keep; git blame + the original PR/commit message is your Chesterton's-Fence
investigation tool.

---

## Part 3: Combining Models — A Worked Example

```
Scenario: "Should we rewrite this legacy monolith as microservices?"

1. First-principles: what's the ACTUAL pain? (not "microservices are
   modern") — is it deploy velocity? team scaling? specific bottlenecks?
2. Inversion: what would make this rewrite a disaster? (underestimated
   scope, no incremental migration path, team doesn't have distributed-
   systems experience yet) → these become explicit risks to mitigate
3. Second-order: rewriting fixes deploy velocity (1st order) but adds
   distributed-systems failure modes — network partitions, eventual
   consistency bugs (2nd order) — is the team ready for THAT operational
   burden?
4. Reversible vs irreversible: is this a one-way door? (Often yes — hard
   to un-migrate once data is split across services) → deserves the
   slow, careful analysis, not a quick call
5. Chesterton's Fence: WHY is the current monolith built the way it is?
   Some of its "bad" design might be load-bearing for a reason the team
   doesn't remember
```

This is the actual thought process a strong "should we do X" system-design
answer demonstrates — not a memorized verdict, but visible use of multiple
models layered together.

---

## Interview Q&A

**Q: How do you decide between two roughly-equal technical approaches when you don't have data yet?**
A: Classify the decision as reversible or irreversible first. If reversible,
decide fast and cheaply, gather real data from the outcome, adjust later.
If irreversible, invest more analysis upfront — but even then, first-principles
thinking (what's our ACTUAL constraint, not what other companies do) narrows
it faster than open-ended debate.

**Q: A junior engineer wants to delete some confusing legacy code that "doesn't seem to do anything." How do you respond?**
A: Chesterton's Fence — investigate why it's there (git blame, related
incident tickets, the original PR discussion) before removing it. Confusing
code is often load-bearing for a reason that isn't visible from the code
alone.

**Q: How do you avoid only thinking one step ahead when evaluating a proposed fix?**
A: Explicitly reason through second and third-order effects, not just the
immediate benefit — ask "and then what happens as a RESULT of that" at
least twice. This is the same discipline good system-design tradeoff
analysis already requires (e.g., a cache's second-order invalidation cost).

---

Related: [Pattern_Selection_Framework](../02_Architecture_Patterns/Section_09_Architectural_Decision_Making/03_Pattern_Selection_Framework.md)
(applies these models to architecture choice specifically), `11_rfc_adr_writing.md`
(reversible vs irreversible decisions map directly to "does this need an RFC"),
[Architecture_AntiPatterns](../02_Architecture_Patterns/Section_09_Architectural_Decision_Making/04_Architecture_AntiPatterns.md)
(many anti-patterns are exactly what happens when these models AREN'T applied).
