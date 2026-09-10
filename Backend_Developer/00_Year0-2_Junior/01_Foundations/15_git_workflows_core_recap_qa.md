# Git Workflows — Core Recap Q&A (Interview Deep Dive)

> Self-test recap of [04_git_workflows.md](04_git_workflows.md), Round 4a (core model, rebase vs merge, conflicts, stash/cherry-pick, reset vs revert, reflog). Format: question → correct answer → live proof (real git commands run in a scratch repo).

---

## Q1. Working Directory → Staging Area → Local Repo → Remote — the 4-state model

**Common confusion to avoid:** Git's "staging area" (the index) is **not** the same thing as a team's "staging" deployment branch/environment — those are unrelated concepts that happen to share a name.

```
Working Directory  --git add-->  Staging Area (Index)  --git commit-->  Local Repo  --git push-->  Remote Repo
```

### Live proof

```
?? file.txt        <- untracked: exists ONLY in Working Directory
A  file.txt        <- staged (first column = staging area status: "Added, ready to commit")
136166f initial commit   <- committed: now in Local Repo, staging area clean again
 M file.txt         <- second column = modified in Working Directory, NOT yet staged
```
`git status --short`'s two columns: **first = staging area state, second = working directory state.**

---

## Q2. Rebase vs Merge — and the golden rule

### Live proof

```
BEFORE (diverged):
* ef9425f C2: change on feature-A
| * 772a556 C1: change on main
|/
* 977755b C0: base commit

AFTER MERGE:
*   90249e0 Merge branch 'feature-A' into try-merge   <- NEW commit, 2 parents
|\
| * ef9425f C2: change on feature-A                    <- SAME hash, untouched
* | 772a556 C1: change on main                          <- SAME hash, untouched
|/
* 977755b C0: base commit

AFTER REBASE:
| * 42ef98f C2: change on feature-A   <- NEW hash! same content, different commit object
| * 772a556 C1: change on main
|/
* 977755b C0: base commit
```

**Merge** = adds a new commit with **two parents**; both branches' original commits stay untouched, hashes unchanged, non-linear graph.

**Merge conflict scenario (verified separately):**
```
<<<<<<< HEAD
console.log("Hello from main");
=======
console.log("Hello from feature");
>>>>>>> feature
```
- `<<<<<<< HEAD` → current branch's version starts
- `=======` → separator between the two versions
- `>>>>>>> feature` → incoming branch's version ends

**Resolution steps:**
```bash
git merge feature          # conflict happens, Git pauses
git status                 # shows "both modified" under Unmerged paths
# manually edit the file, DELETE all 3 marker lines yourself, decide final content
git add file.js            # marks conflict resolved
git commit                 # completes the merge
# (if the conflict happened during a REBASE instead: `git rebase --continue` here, not `git commit`)
```
Tools: `git mergetool`, or VS Code's built-in "Accept Current / Incoming / Both" UI.

**Rebase** = replays feature branch's commits one-by-one on top of the new base — Git creates **brand-new commit objects with new hashes**, even though content is identical. Produces linear history.

### The Golden Rule — never rebase a shared/pushed branch

Rebase creates new hashes. If a branch was already pushed and others pulled it, rebasing + force-pushing creates **two divergent histories** — their local repo still has the old commits, yours has the rewritten ones. Confusion, duplicate commits, or **silently lost work** on merge.

**Rule:** *"Never rebase commits that exist outside your repository and that others may have based work on."* Rebase only local/unpushed/private branches. Use merge on shared branches, or coordinate `--force-with-lease` (never plain `--force`).

---

## Q3. Merge Conflicts — see Q2 above (markers + resolution steps covered together)

---

## Q4. `git stash` and `git cherry-pick`

### `git stash` — live proof

```
Working directory has uncommitted change: " M app.py"
git stash push -m "WIP: half-done feature"
After stash -- working directory clean again: (nothing shown by git status --short)
git stash list -> "stash@{0}: On main: WIP: half-done feature"
git stash pop -> " M app.py" restored, stash entry dropped
```
**Real use case:** mid-work on branch A with uncommitted changes, an urgent hotfix is needed on another branch — stash shelves the half-done work without committing it, letting you switch branches on a clean tree, then `pop` it back later.

### `git cherry-pick` — live proof

```
feature branch: C0 -> C1 (unrelated) -> C2 (critical bugfix) -> C3 (unrelated, not ready)
git cherry-pick <C2's hash> onto main
main now: C0 -> 77c85c5 (SAME bugfix content, NEW hash) -- no trace of C1/C3
```
Same as rebase — cherry-pick creates a **new commit object** with a new hash even though the diff is identical, because it's applied on a different parent.

**Real use case:** a critical bugfix commit landed on a `feature` branch that isn't otherwise production-ready. Merging the whole branch would bring in unfinished work; cherry-pick takes just that one bugfix commit onto `main`.

---

## Q5. `git reset` vs `git revert`

### `git reset` — rewrites history, moves the branch pointer

```
Before: C0 -> C1 -> C2 (bad commit)
reset --soft HEAD~1:  C2 removed from history, changes stay STAGED ("M  app.py")
reset --hard HEAD~1:  C2 removed from history AND changes DISCARDED from working dir entirely
```
`--soft` / `--mixed` (default) / `--hard` differ only in how much of the removed commit's content survives — all three move which commit the branch pointer refers to.

### `git revert` — safe on shared/pushed commits, live 2-developer proof

```
Dev1 pushes bad commit C1. Dev2 already pulled it (has C1 locally).
Dev1 runs: git revert C1  -> creates NEW commit "Revert C1", pushes it.
           History: C0 -> C1 -> Revert-C1  (C1 still exists, just its effect undone)
Dev2 runs: git pull -> works CLEANLY, no conflict, no rewritten history.
```

**Why revert is safe and reset isn't (for pushed commits):** `reset` deletes a commit from branch history — if others already have it locally, histories diverge, and reconciling can silently drop their work. `revert` never deletes anything, it adds a new commit that cancels the old one's changes — history stays append-only and consistent for everyone; `git pull` just works.

**Interview one-liner:** *"Reset rewrites history — safe only for local, unpushed commits. Revert adds new history — always safe, even on shared/pushed/production branches."*

---

## Q6. Recovery via `git reflog`

**Analogy:** a flight recorder / black box for HEAD — tracks every place HEAD has pointed to, even commits no longer reachable from any branch. Commit objects aren't deleted immediately by `reset --hard`, a bad rebase, or a deleted branch — they just become unreferenced, and stay on disk until Git's garbage collector eventually cleans them up (~90 days default).

### Live proof — full recovery from an accidental `reset --hard`

```
3 real commits: C0 -> C1 -> C2
DISASTER: git reset --hard HEAD~2  -->  git log shows only C0, C1+C2 "gone"

git reflog:
  22fbdaa HEAD@{0}: reset: moving to HEAD~2         <- the disaster
  97b445d HEAD@{1}: commit: C2: another important feature   <- still exists!
  dca052f HEAD@{2}: commit: C1: important feature            <- still exists!
  22fbdaa HEAD@{3}: commit (initial): C0: base

Recovery: git reset --hard HEAD@{1}
Result: C1 and C2 are BACK in git log, exactly as before
```

**Interview one-liner:** *"Git almost never truly loses work instantly — `reflog` is the safety net for `reset --hard`, bad rebases, and accidental branch deletions, as long as you catch it before garbage collection runs."*

**Practical recovery command:** `git reflog` → find the hash right before the mistake → `git reset --hard <hash>` (or `git checkout <hash>` first to just look, without committing to the recovery).

---

## Round 4a Scorecard

| Q | Topic | Result |
|---|---|---|
| 1 | 4-state model (working dir/staging/local/remote) | ⚠️ Confused git's staging area with a "staging" deployment branch — corrected |
| 2 | Rebase vs Merge + golden rule | ✅ Rebase definition correct; merge mechanism and golden rule needed filling in |
| 3 | Merge conflict markers + resolution | ✅ Markers explained correctly; resolution steps (add/commit, rebase --continue) added |
| 4 | stash + cherry-pick | ⚠️ Right direction, mechanism/use-case depth needed filling in |
| 5 | reset vs revert | ⚠️ Soft/hard distinction known; the "why revert is safe on pushed commits" core answer was missing |
| 6 | reflog recovery | ❌ Not known — taught fresh with full live proof |

**Action item:** Revisit Q1 (don't conflate git's internal staging area with a deployment "staging" branch) and Q6 (reflog) — these are the two weakest points and both are extremely common interview/real-recovery topics.
