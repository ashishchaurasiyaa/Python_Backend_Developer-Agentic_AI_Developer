# Git Workflows — Advanced Recap Q&A (Interview Deep Dive)

> Self-test recap of [04_git_workflows.md](04_git_workflows.md), Round 4b (branching strategies, PR workflow, bisect, tags, blame, pre-commit hooks). Format: analogy → concept → live proof (real git commands run in scratch repos).

---

## Q1. GitHub Flow vs Git Flow vs Trunk-Based Development

**Analogy:** Three restaurant kitchen workflows.

**GitHub Flow** — one long-running branch (`main`), feature branches off it, PR back into it, `main` deploys continuously.
```
main ─────●─────●─────●─────●─────●─────●─────
              │       │           │
              └───────●           │
              feature (PR merged)  │
                                   ●─── hotfix
```
Pros: simple, fast, modern. Cons: needs strong CI + feature flags (unfinished work merged to `main` must be hidden behind flags).

**Git Flow** — `main` = production only, `develop` = next release integration branch, plus `release/*`/`hotfix/*`/`feature/*` branches.
```
main      ●─────●─────●  (production releases only)
develop   ●─●─●─●─●─●    (integration branch)
```
Pros: clear production-vs-next-release separation, good for versioned releases (libraries, mobile apps, on-prem software). Cons: heavyweight, slower for small teams.

**Trunk-Based Development** — everyone commits to `main` (or hours/days-long branches), pioneered by Google/Facebook.
```
main ─●─●─●─●─●─●─●─●─●─●─●─●─
        │ │     │     │
        └─┘ short-lived feature branches (hours-days)
```
Pros: no merge hell, purest continuous integration. Cons: requires high trust + strong automated testing + feature flags — unsafe without them.

### Senior recommendation

| Scenario | Pick |
|---|---|
| Small team (<10 devs), most SaaS | GitHub Flow (default for most companies) |
| Mature CI/CD + feature flags | Trunk-Based |
| Versioned releases (libraries, mobile, on-prem) | Git Flow |

**Interview one-liner:** "GitHub Flow trades formality for speed. Git Flow trades speed for control when releases are versioned. Trunk-based is the extreme speed end, needing feature flags and strong CI discipline."

---

## Q2. Small PRs Pattern

**Analogy:** Reviewing one chapter carefully vs skimming a 500-page book in one sitting — attention and bug-catching quality degrades sharply with size.

**Reviewer-perspective problems with large PRs:**
1. **Cognitive overload** — context spread across hundreds of lines forces constant scrolling; leads to superficial "LGTM" rubber-stamp approvals.
2. **Review effectiveness drops with size** — a 50-line PR gets a much higher issue-catch rate than a 500-line one, purely from reviewer fatigue.
3. **Merge conflicts compound** — the longer a big PR stays open, the further `main` drifts, the worse the eventual conflict.
4. **Debugging nightmare** — if a bug ships from a 500-line PR, isolating the exact change responsible is far harder than from a small, focused PR (also makes `git bisect`, Q3, much less precise).
5. **Slow feedback loop** — large PRs get deprioritized by reviewers ("I'll look later"); small PRs get reviewed and merged fast, unblocking the author sooner.

**Guideline:** ~200-400 lines of diff; split a big feature into independently reviewable/revertable PRs (e.g. migration+model → API endpoint → frontend integration).

---

## Q3. `git bisect`

**Analogy:** Finding a word in a dictionary via binary search — open the middle, narrow the half, repeat. Same algorithm, applied to commit history.

### Live Proof — Real Bug Found in 3 Steps Out of 9 Commits

```
9 commits (C0 good ... C8 bad, bug secretly introduced at C4: `a + b` became `a - b`)

git bisect start
git bisect bad HEAD
git bisect good <C0-hash>
git bisect run python3 test_add.py     # test script: exit 0 = good, exit 1 = bad

Step 1: tested C4 (midpoint) -> BAD
Step 2: tested C2 -> GOOD
Step 3: tested C3 -> GOOD
Result: "b5fc00e is the first bad commit -- C4: refactor add() (introduces a silent bug)"
```
Exactly correct, in **3 comparisons instead of checking all 9 commits** — **O(log n)** instead of **O(n)**. With 1000 commits between a known-good and known-bad point, bisect needs only ~10 steps (log₂(1000) ≈ 10).

**`git bisect run <script>`** automates the whole search — any command exiting `0`=good / non-zero=bad — no manual testing needed at each step.

**Real-world use case:** "Bug appeared sometime in the last 2 weeks, ~200 commits, no idea which one" — a reproducing test script turns a hopeless manual hunt into an ~8-step guided search.

---

## Q4. `git tag` — Annotated vs Lightweight

**Analogy:** Lightweight tag = a bookmark (just a page number, no metadata). Annotated tag = a notarized certificate (signature, date, message) — its own real Git object.

### Live Proof — Different Git Object Types, Confirmed

```
Lightweight tag (v1.0.0-lite):
  git cat-file -t  -> "commit"   (just a direct pointer, no metadata stored)

Annotated tag (v1.0.0, created with -a -m):
  git cat-file -t  -> "tag"      (its own distinct object type)
  content:
    object a73c915...
    type commit
    tag v1.0.0
    tagger Demo <demo@example.com> ...
    Release 1.0.0: first stable release
```

**Always use annotated tags for releases** (`git tag -a v1.2.0 -m "..."`):
- Records who tagged it, when, and why (audit trail)
- `git describe` (used in build scripts for version strings) needs annotated tags to work reliably
- GitHub Releases and most tooling expect them

Lightweight tags are fine only for personal, throwaway bookmarks. **Note:** tags don't push automatically with plain `git push` — need `git push origin <tag>` or `--tags`.

---

## Q5. `git blame`

**Analogy:** Every line of a shared document showing "last edited by X on date Y."

### Live Proof — Multi-Author File, Line-Level Attribution

```
git blame config.py:
e31a784d (Alice 2026-09-10 ...) TIMEOUT = 5  # reduced after incident #4521
^e00b8de (Alice 2026-09-10 ...) RETRIES = 3
fd86a9ed (Bob   2026-09-10 ...) MAX_CONNECTIONS = 100
```
Every line carries its own commit hash, author, and timestamp — confirmed across two different authors on the same file.

**`git blame -L 10,20 file.py`** restricts output to just lines 10-20 — useful for a large file when only a specific section is suspicious.

**Real workflow:** spot a weird value (`TIMEOUT = 5`) → `git blame` shows who changed it and a hint why (commit message referencing an incident) → `git show <hash>` for the full commit context — get the answer without asking anyone directly.

---

## Q6. Pre-Commit Hooks

**Analogy:** A security guard checking bags before letting anyone into a building — `.git/hooks/pre-commit` runs automatically before a commit is created; a non-zero exit code cancels the commit entirely.

### Live Proof — Real Hook Blocking a Hardcoded Secret

```
Pattern: AKIA[0-9A-Z]{16}  (real AWS access key ID format)

Attempt 1: AWS_KEY = "AKIAABCDEFGHIJKLMNOP" hardcoded
  -> "BLOCKED: possible secret detected in settings.py" -- exit code: 1, commit never created

Attempt 2: AWS_KEY = os.environ["AWS_KEY"]  (loaded from env instead)
  -> commit succeeded -- exit code: 0
```

**Why this matters:** this is exactly the kind of gate that prevents a hardcoded production secret from ever entering git history — once committed and pushed, a secret is in history permanently unless history is rewritten (`git filter-repo`/BFG — painful and risky on a shared repo). Directly relevant given the Toofan repo secrets incident noted in project memory — a pre-commit secret scanner is the concrete fix that would have caught it before the commit, not after.

**In practice, don't hand-roll regex** — use the `pre-commit` framework (`.pre-commit-config.yaml`, installed via `pre-commit install`) with tools like:
- `detect-secrets` / `gitleaks` — scan for AWS/GitHub/Stripe keys, private keys, etc.
- `black` / `ruff` — auto-format/lint before commit
- `trailing-whitespace`, `end-of-file-fixer` — hygiene checks

---

## Round 4b Scorecard

All 6 topics were unknown going in ("nahi pta") and taught fresh with live proof:
- Branching strategies (GitHub Flow / Git Flow / Trunk-Based) and when to pick each
- Small PRs — the reviewer-fatigue argument, not just "keep it short"
- `git bisect` — binary search over commit history, O(log n), automatable with `bisect run`
- Annotated vs lightweight tags — genuinely different Git object types, use annotated for releases
- `git blame` — line-level attribution, `-L` range restriction, pairs with `git show`
- Pre-commit hooks — real secret-blocking hook built and verified live; ties directly to the Toofan secrets-in-git incident from project history

**Action item:** All 6 were cold-start gaps — worth a full re-read of [04_git_workflows.md](04_git_workflows.md) before an interview, not just this summary.
