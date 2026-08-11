# Git — Hands-On Labs
**DevOps Track · Phase 4 Practical**

Labs map directly to the theory file:
- Labs 1 + 2 → Branching, Merging, Rebase, Cherry-pick
- Lab 3      → Reset, Revert, Reflog
- Lab 4      → Force-push, --force-with-lease
- Lab 5      → Git Internals, Bisect, Blame, Pickaxe
- Lab 6      → Hooks, Stash, Restore/Clean, Detached HEAD
- Lab 7      → Production Problems Rehearsal (6 real scenarios)

---

## Prerequisites

```bash
# Check git version (2.30+ needed for git restore and switch):
git --version

# Create a throwaway lab directory — all labs live here:
mkdir -p ~/git-lab && cd ~/git-lab

# Initialize and configure:
git init
git config user.email "lab@example.com"
git config user.name "Lab User"
git config init.defaultBranch main

# Nothing here touches any real remote — zero risk to existing projects.
```

---

## Lab 1: Branching, Merging, and Reading History

**Objective:** Build muscle memory for the everyday branch/commit/merge flow and get comfortable reading `git log --graph`.

**Task:**

```
1. On main, create app.py with print("v1"), commit it.
2. Create branch feature/greeting, change line to print("hello, v2"), commit.
3. Switch back to main, add README.md (any content), commit — this creates
   TRUE divergence (both branches have unique commits), not just fast-forward.
4. Merge feature/greeting into main with --no-ff.
5. Read git log --oneline --graph --all — identify where branch split and merged.
6. Delete the merged branch using the SAFE delete flag (-d not -D).
   Understand WHY -d works here (explain it) vs why -D would be needed on
   an unmerged branch.
```

<details>
<summary>Solution / walkthrough</summary>

```bash
cd ~/git-lab
git init && git config user.email "lab@example.com" && git config user.name "Lab User"

# 1. Baseline commit on main
echo 'print("v1")' > app.py
git add app.py
git commit -m "initial app.py"

# 2. Feature branch
git checkout -b feature/greeting
echo 'print("hello, v2")' > app.py
git add app.py
git commit -m "update greeting to v2"

# 3. Diverge main independently
git checkout main
echo "# Lab Project" > README.md
git add README.md
git commit -m "add README"

# 4. Merge — force a merge commit even if fast-forward would be possible
git merge --no-ff feature/greeting -m "merge feature/greeting into main"

# Verify it's a REAL merge commit (should show TWO parent hashes):
git show --no-patch --format="%H parents: %P" HEAD
# abc1234 parents: def5678 ghi9012
# Two parents = confirmed merge commit, not a fast-forward

# 5. Read the graph
git log --oneline --graph --all
# *   a1b2c3d (HEAD -> main) merge feature/greeting into main
# |\
# | * f4e5d6c (feature/greeting) update greeting to v2    ← feature branch line
# * | 9c8b7a6 add README                                   ← main branch line
# |/
# * 1234567 initial app.py                                 ← common ancestor
#
# Read: commit graph splits at 1234567, both branches add their own commit,
# converge again at the merge commit at the top.

# 6. Safe delete — succeeds because the commit IS reachable from main
git branch -d feature/greeting
# Deleted branch feature/greeting (was f4e5d6c).

# Understanding -d vs -D:
# -d: "delete only if this branch's commits are reachable from HEAD"
#     = the work is safely merged, nothing is lost
# -D: force delete even if commits would be orphaned
#     = use only when you KNOW you want to throw the branch away
#
# Test: create an unmerged branch and try -d:
git checkout -b dead-end-branch
echo "abandoned work" > trash.txt
git add trash.txt && git commit -m "abandoned work"
git checkout main
git branch -d dead-end-branch
# error: The branch 'dead-end-branch' is not fully merged.
# -D would delete it, losing the "abandoned work" commit permanently
git branch -D dead-end-branch   # force delete (we genuinely don't want it)
```

**What the graph shape tells you:**
- Straight line = all commits on one branch (no divergence)
- Fork + rejoin = a feature branch was created and merged back
- Two forks diverging = two branches that haven't merged yet
- `*` at a junction = a merge commit (two parent lines converging)

</details>

---

## Lab 2: Rebase, Cherry-Pick, and Conflict Resolution

**Objective:** Get hands-on with history rewriting and resolve a real conflict from raw markers — the skill from the theory, done yourself instead of just read.

**Task:**

```
1. Create pricing.py on main: def discount(price): return price * 0.9 — commit.
2. Create branch feature/pricing, change discount to 0.85, commit.
3. Switch to main, change SAME line to 0.8 — simulating two people editing.
4. Merge feature/pricing → conflict. Resolve to 0.85, no markers left, commit.
5. Create branch feature/tax off main. Add: def tax(price): return price * 0.18
   Commit. Then add one more commit directly on main (a file comment).
6. Rebase feature/tax onto new main tip. Observe SHA changes.
7. Cherry-pick the tax commit SHA onto release/1.0 branch. Verify only
   that one commit came along — not the whole branch.
```

<details>
<summary>Solution / walkthrough</summary>

```bash
# 1. Baseline
printf 'def discount(price):\n    return price * 0.9\n' > pricing.py
git add pricing.py
git commit -m "add discount function"

# 2. Feature branch: 0.9 → 0.85
git checkout -b feature/pricing
sed -i.bak 's/0.9/0.85/' pricing.py && rm -f pricing.py.bak
git add pricing.py
git commit -m "bump discount to 0.85"

# 3. Main: 0.9 → 0.8 (conflicting change)
git checkout main
sed -i.bak 's/0.9/0.8/' pricing.py && rm -f pricing.py.bak
git add pricing.py
git commit -m "bump discount to 0.8"

# 4. Merge → conflict
git merge feature/pricing
# CONFLICT (content): Merge conflict in pricing.py

cat pricing.py
# def discount(price):
# <<<<<<< HEAD           ← main's version (0.8)
#     return price * 0.8
# =======                ← divider
#     return price * 0.85
# >>>>>>> feature/pricing ← incoming version (0.85)

# Resolution: decide 0.85 is correct, rewrite file with NO markers
printf 'def discount(price):\n    return price * 0.85\n' > pricing.py
git add pricing.py
git status    # no other files conflicted?
git commit    # opens pre-filled merge message editor — save it

# Verify clean resolution:
cat pricing.py
# def discount(price):
#     return price * 0.85

# 5. Tax function on new branch
git checkout -b feature/tax
cat >> pricing.py << 'EOF'

def tax(price):
    return price * 0.18
EOF
git add pricing.py
git commit -m "add tax function"

# Main moves forward independently:
git checkout main
echo "# pricing helpers" > header.txt
git add header.txt
git commit -m "add header file"

# Note the feature/tax commit SHA BEFORE rebase:
BEFORE_SHA=$(git log feature/tax --oneline --format="%H" | head -1)
echo "SHA before rebase: $BEFORE_SHA"

# 6. Rebase — replay feature/tax commits on top of main's new tip
git checkout feature/tax
git rebase main
# if conflict → resolve → git add → git rebase --continue

# SHA is NOW DIFFERENT (same code, new parent = new hash):
AFTER_SHA=$(git log feature/tax --oneline --format="%H" | head -1)
echo "SHA after rebase:  $AFTER_SHA"
# These two SHAs will be different — this IS the "why rebase changes hashes" lesson

# Visual proof:
git log --oneline --graph --all
# feature/tax commit is now ABOVE main's tip (not off to the side)
# = linear history

# 7. Cherry-pick onto release branch
TAX_SHA=$(git log feature/tax --oneline --grep="add tax function" --format="%H")
git checkout main
git checkout -b release/1.0
git cherry-pick "$TAX_SHA"

# Verify ONLY the tax commit came:
git log --oneline
# shows: base commits + ONLY the tax commit
# feature/tax's rebase commit is NOT here — cherry-pick applied exactly one SHA

grep -A2 "def tax" pricing.py    # tax function is there
```

**Key takeaway:** rebase rewrites SHA (same code, new parent), cherry-pick copies exactly one commit (not a whole branch). These are the two most important "why" explanations in the rebase/cherry-pick section.

</details>

---

## Lab 3: Reset vs Revert — Recover From Mistakes Safely

**Objective:** Prove to yourself why `reset --hard` on shared history is dangerous and `revert` is safe — and that `reflog` really is a 90-day safety net.

**Task:**

```
1. Create branch experiment. Make 3 commits adding line1, line2, line3 to notes.txt.
2. git reset --soft HEAD~1 — verify line3 is STAGED, not lost.
3. Recommit with different message. Back to 3 commits total.
4. git reset --hard HEAD~1 — verify line3 is GONE from file AND git status is clean.
5. Recover line3 via git reflog — find the SHA, reset --hard back to it.
6. git revert the last commit (safe way for "already pushed" scenario).
   Verify: new commit appears, original commit still in history, line3 gone from file.
7. Explain in one sentence why step 6 is the only safe option once history is shared.
```

<details>
<summary>Solution / walkthrough</summary>

```bash
git checkout main
git checkout -b experiment

echo "line1" > notes.txt && git add notes.txt && git commit -m "add line1"
echo "line2" >> notes.txt && git add notes.txt && git commit -m "add line2"
echo "line3" >> notes.txt && git add notes.txt && git commit -m "add line3"

# Current state: 3 commits, notes.txt has 3 lines
git log --oneline
cat notes.txt

# 2. Soft reset — undo commit, keep changes STAGED
git reset --soft HEAD~1
git status
# Changes to be committed:
#   modified: notes.txt     ← line3 addition is still STAGED
cat notes.txt    # all 3 lines still here — soft reset never touches files

# 3. Recommit with better message
git commit -m "add line3 (properly titled)"

# 4. Hard reset — discard completely
git reset --hard HEAD~1
cat notes.txt
# line1
# line2
git status
# nothing to commit, working tree clean
# line3 is GONE

# 5. Recovery via reflog
git reflog
# HEAD@{0}: reset: moving to HEAD~1          ← the bad reset happened here
# HEAD@{1}: commit: add line3 (properly titled)  ← this is what we lost
# HEAD@{2}: reset: moving to HEAD~1
# HEAD@{3}: commit: add line3
# ...
# Find the SHA of "add line3 (properly titled)":
LOST_SHA=$(git reflog | grep "add line3 (properly titled)" | head -1 | awk '{print $1}')
git reset --hard "$LOST_SHA"
cat notes.txt
# line1
# line2
# line3   ← recovered

# 6. Revert — the safe "already shared" undo
git log --oneline | head -3
# abc1234 add line3 (properly titled)   ← pretend this is already pushed
LAST_SHA=$(git rev-parse HEAD)
git revert "$LAST_SHA" --no-edit
git log --oneline | head -4
# new_sha Revert "add line3 (properly titled)"   ← NEW commit
# abc1234 add line3 (properly titled)            ← ORIGINAL commit still here
cat notes.txt
# line1
# line2
# line3 is gone from the FILE — but abc1234 still exists in history

# 7. Explanation:
# If abc1234 was already pushed and a teammate pulled it, then you
# ran git reset --hard + git push --force, their local branch would
# have abc1234 but origin/experiment would not — their next git pull
# would create conflicts or silently leave them working on an orphaned
# commit. git revert only ADDS a new commit, never removes anything
# that already exists on the remote, so teammates' history stays intact.
```

</details>

---

## Lab 4: Force-Push Disaster — Simulate and Recover

**Objective:** Watch exactly what `--force` destroys and why `--force-with-lease` is the correct default. Uses two local clones of a bare "remote" — no GitHub account needed.

**Task:**

```
1. Create bare "remote": git init --bare ~/git-lab-remote.git
2. Clone twice: ~/git-lab-you and ~/git-lab-teammate
3. "You" push a commit. "Teammate" pulls, pushes a different commit.
4. "You" amend + git push --force WITHOUT pulling first.
   Observe teammate's commit disappears from remote.
5. Teammate discovers damage via git fetch + git log --graph.
6. Teammate recovers orphaned commit via reflog + cherry-pick.
7. Redo the disaster but use --force-with-lease → confirm it REFUSES.
```

<details>
<summary>Solution / walkthrough</summary>

```bash
# 1-2. Fake remote + two clones
git init --bare ~/git-lab-remote.git
git clone ~/git-lab-remote.git ~/git-lab-you
git clone ~/git-lab-remote.git ~/git-lab-teammate

# 3. "You" push first
cd ~/git-lab-you
git config user.email you@lab.com && git config user.name "You"
echo "feature A" > work.txt
git add work.txt && git commit -m "you: feature A"
git push origin main

# 4. Teammate pulls and pushes their own work
cd ~/git-lab-teammate
git config user.email tm@lab.com && git config user.name "Teammate"
git pull origin main
echo "feature B" >> work.txt
git add work.txt && git commit -m "teammate: feature B"
git push origin main

# 5. THE DISASTER — "you" amend + force-push WITHOUT pulling teammate's work
cd ~/git-lab-you
git commit --amend -m "you: feature A (amended, forgot to pull)"
git push --force origin main
# SUCCEEDED — and silently destroyed teammate's "feature B" commit

# 6. Teammate discovers damage
cd ~/git-lab-teammate
git fetch origin
git log --oneline --graph --all
# * abc1234 (origin/main) you: feature A (amended)   ← remote tip
# * def5678 (HEAD -> main, refs/teammates-stuff) teammate: feature B
#   ← local branch still has their commit, but it's diverged from origin
# origin/main no longer contains "feature B"

# 7. Recovery
cd ~/git-lab-teammate
git reflog | head -5
# HEAD@{0}: fetch: ... origin/main moved to abc1234
# HEAD@{1}: commit: teammate: feature B   ← this SHA is still alive locally

TEAMMATE_SHA=$(git log --all --oneline | grep "feature B" | awk '{print $1}')
git reset --hard origin/main        # sync to current (damaged) remote tip
git cherry-pick "$TEAMMATE_SHA"      # re-apply orphaned commit on top
git push origin main                  # restore to remote
git log --oneline | head -3
# teammate's work is back on remote, sitting on top of "you"'s amended commit

# 8. Redo with --force-with-lease — the safe version
cd ~/git-lab-you
echo "another change" >> work.txt
git add work.txt && git commit --amend -m "you: feature A (second amend)"
# Simulate teammate pushing AGAIN:
cd ~/git-lab-teammate
echo "feature C" >> work.txt
git add work.txt && git commit -m "teammate: feature C"
git push origin main
# Now "you" tries to force-push:
cd ~/git-lab-you
git push --force-with-lease origin main
# ! [rejected] main -> main (stale info)
# error: failed to push some refs
# REFUSED — --force-with-lease detected that origin/main moved
# (teammate pushed) since "you" last fetched
git pull --rebase origin main    # correct: fetch + rebase first
git push origin main              # now a clean, safe push

# Cleanup:
rm -rf ~/git-lab-remote.git ~/git-lab-you ~/git-lab-teammate
```

**The single rule:** `--force` overwrites unconditionally. `--force-with-lease` only overwrites if nobody pushed since you last fetched. Use `--force-with-lease` by default and `--force` never on shared branches.

</details>

---

## Lab 5: Git Internals + Bisect + Blame + Pickaxe

**Objective:** Explore the `.git/` object database directly, use bisect to find a regression in O(log N) steps, and use blame/pickaxe to answer "who changed this and when?"

**Task:**

```
Part A — Internals exploration
1. In any repo, run git cat-file -t HEAD — confirm "commit".
2. Run git cat-file -p HEAD — read the tree SHA, parent SHA, author line.
3. Run git cat-file -p <tree-sha-from-step-2> — see the directory listing.
4. Run git cat-file -p <blob-sha-for-app.py> — see the raw file content.
5. cat .git/HEAD — see what it points to.
   cat .git/refs/heads/main — see the actual commit SHA.
   Prove: a branch IS just a file with a SHA in it.

Part B — Bisect
1. Create a fresh bisect-lab/ directory. Make 10 commits, numbering them 1-10.
   In commit 7, introduce a "bug" (add a line "BUG" to a file).
   In commits 8-10, add normal content (no bug removal — bug persists).
2. Run git bisect start, mark HEAD (commit 10) as bad,
   mark commit 1 tag/SHA as good.
3. Test each checkout bisect presents, marking good or bad.
4. Count how many steps it took to find commit 7 (should be ≤ log2(10) ≈ 4 steps).
5. Use git bisect run to automate it with a one-liner test script.

Part C — Blame + Pickaxe
1. Create a file with 5 commits, each changing a different function.
2. git blame -L 1,5 file.py — read which commit authored each line.
3. git log -S"BUG" --oneline — find which commit introduced the "BUG" string.
4. git log -G"def.*discount" --oneline — find commits that touched discount functions.
```

<details>
<summary>Solution / walkthrough</summary>

```bash
# Part A — Object Database Exploration
cd ~/git-lab   # use any repo with at least one commit

# Step 1: type of HEAD
git cat-file -t HEAD
# commit

# Step 2: contents of HEAD commit object
git cat-file -p HEAD
# tree 4b825dc642cb6eb9a060e54bf8d69288fbee4904
# parent def5678abc1234...
# author Lab User <lab@example.com> 1723350000 +0000
# committer Lab User <lab@example.com> 1723350000 +0000
#
# add line3 (properly titled)

# Step 3: the tree (directory listing at HEAD)
TREE_SHA=$(git cat-file -p HEAD | grep "^tree" | awk '{print $2}')
git cat-file -p "$TREE_SHA"
# 100644 blob abc123... notes.txt
# 100644 blob def456... pricing.py
# Each line: permissions type blob-SHA filename

# Step 4: raw file content
BLOB_SHA=$(git cat-file -p "$TREE_SHA" | grep "notes.txt" | awk '{print $3}')
git cat-file -p "$BLOB_SHA"
# line1
# line2
# (the raw bytes stored in the blob)

# Step 5: branch = file with SHA
cat .git/HEAD
# ref: refs/heads/experiment   (if on experiment branch)
# OR: abc1234...               (if in detached HEAD state)

cat .git/refs/heads/main
# abc1234def5678...   (40-char SHA — this IS the main branch, nothing more)

# Prove it: manually move main pointer to an older commit:
CURRENT=$(cat .git/refs/heads/main)
OLD_SHA=$(git log main --oneline | tail -1 | awk '{print $1}')
echo "$OLD_SHA" > .git/refs/heads/main    # direct file write
git log main --oneline | head -3          # main now points to old commit
echo "$CURRENT" > .git/refs/heads/main    # restore
# THIS IS WHAT git reset does internally — it rewrites this file

# Part B — Bisect
mkdir -p ~/bisect-lab && cd ~/bisect-lab
git init && git config user.email "lab@example.com" && git config user.name "Lab User"

for i in $(seq 1 10); do
  echo "commit $i content" >> history.txt
  if [ "$i" -eq 7 ]; then
    echo "BUG" >> history.txt    # introduced in commit 7
  fi
  git add history.txt
  git commit -m "commit $i"
done

# Current state: commit 10 is HEAD, commit 7 introduced "BUG"
git log --oneline

# Start bisect
git bisect start
git bisect bad                   # HEAD (commit 10) is broken
git bisect good $(git log --oneline | tail -1 | awk '{print $1}')  # commit 1 is good

# Git checks out ~commit 5 or 6 — inspect it:
# Run this manually until Git reports the first bad commit:
# grep -q "^BUG$" history.txt && git bisect bad || git bisect good

# Automate with bisect run:
git bisect reset    # reset first
git bisect start HEAD $(git log --oneline | tail -1 | awk '{print $1}')
git bisect run bash -c 'grep -q "^BUG$" history.txt && exit 1 || exit 0'
# Git will automatically find: "abc1234 is the first bad commit"
# That should be commit 7.
# Steps taken: log2(10) ≈ 3-4 checks instead of manually reading 10 commits

git bisect reset    # return to HEAD

# Part C — Blame and Pickaxe
cd ~/git-lab
cat > functions.py << 'EOF'
def discount(price):
    return price * 0.9
EOF
git add functions.py && git commit -m "add discount"

cat >> functions.py << 'EOF'

def tax(price):
    return price * 0.18
EOF
git add functions.py && git commit -m "add tax"

sed -i.bak 's/0.9/0.85/' functions.py && rm -f functions.py.bak
git add functions.py && git commit -m "change discount to 0.85"

# Blame: who authored each line?
git blame -L 1,4 functions.py
# abc1234 (Lab User 2026-...) def discount(price):    ← first commit
# abc1234 (Lab User 2026-...) return price * 0.85     ← BUT last edit was commit 3
# Note: blame shows the LAST commit that touched each line

# Blame ignoring whitespace changes:
git blame -w functions.py
# -w: if someone re-indented the file, blame shows the original author, not re-indenter

# Pickaxe: find when "BUG" was added:
cd ~/bisect-lab
git log -S"BUG" --oneline
# abc1234 commit 7   ← exactly the commit that introduced BUG

# Pickaxe with regex: find commits that changed discount functions:
cd ~/git-lab
git log -G"def.*discount" --oneline
# shows commits that have "def discount..." in their diff content

# Combine with -p for the actual diff:
git log -S"0.85" -p -- functions.py
# shows the exact commit + diff where "0.85" was added

cd ~/git-lab   # return to main lab dir
rm -rf ~/bisect-lab
```

**The production use case for bisect:** "We deployed 80 commits on Friday and something broke over the weekend. Nobody knows which commit." `git bisect run pytest tests/test_regression.py` finds the culprit in ~7 checkout-test cycles instead of reading 80 diffs. This is a real, high-value skill.

</details>

---

## Lab 6: Hooks, Stash, Restore/Clean, Detached HEAD

**Objective:** Wire up a real pre-commit hook that blocks bad commits, master the stash multi-context workflow, practice `git restore` and `git clean`, and intentionally enter/escape detached HEAD.

**Task:**

```
Part A — Hooks
1. Write a pre-commit hook that blocks any commit where a Python file
   contains the string "TODO: REMOVE" (simulate secret/debug code that
   should never be committed).
2. Verify it blocks a commit containing that string.
3. Verify it allows a commit that doesn't contain it.

Part B — Stash
1. Start editing a file (don't commit). Stash it with git stash.
2. Switch to a different branch, make a commit.
3. Switch back, git stash pop — verify your work is restored.
4. Create TWO stashes, list them, apply stash@{1} specifically.
5. git stash show -p stash@{0} — preview what's in a stash without applying.

Part C — Restore and Clean
1. Modify a tracked file. Use git restore to discard the change.
2. Stage a file. Use git restore --staged to unstage it (keep the change).
3. Create several untracked files and an untracked directory.
4. git clean -n first (dry run), then git clean -fd.

Part D — Detached HEAD
1. Check out a specific old commit SHA → enter detached HEAD.
2. Make a commit while detached. Observe it's not on any branch.
3. Checkout main → the detached commit becomes "orphaned."
4. Recover it using git checkout -b recovery-branch.
```

<details>
<summary>Solution / walkthrough</summary>

```bash
cd ~/git-lab

# Part A — Pre-commit hook
mkdir -p .git/hooks
cat > .git/hooks/pre-commit << 'HOOK'
#!/usr/bin/env bash
set -euo pipefail
if git diff --cached --name-only | grep -q '\.py$'; then
  if git diff --cached | grep -q 'TODO: REMOVE'; then
    echo "ERROR: Commit blocked — 'TODO: REMOVE' found in staged Python file."
    echo "Remove that line before committing."
    exit 1
  fi
fi
exit 0
HOOK
chmod +x .git/hooks/pre-commit

# Test 1: blocked commit
echo 'print("debug")  # TODO: REMOVE' > debug_tool.py
git add debug_tool.py
git commit -m "add debug tool"
# ERROR: Commit blocked — 'TODO: REMOVE' found in staged Python file.
# Commit was BLOCKED — good

# Fix the file and retry:
echo 'print("debug")' > debug_tool.py
git add debug_tool.py
git commit -m "add debug tool"
# Succeeds — hook exited 0

# Bypass (for emergencies — understand the escape hatch):
echo 'print("TODO: REMOVE")' > bad.py
git add bad.py
git commit --no-verify -m "bypassed hook (emergency)"
# --no-verify bypasses ALL hooks — this is why hooks are not a security control,
# only a convenience check. CI/CD must enforce the same rules unbypassably.
git rm bad.py && git commit -m "remove bad.py"

# Part B — Stash multi-context workflow
echo "work in progress" >> notes.txt
echo "more wip" >> debug_tool.py
git status
# Modified: notes.txt, debug_tool.py — NOT staged

# Stash current changes:
git stash -u    # -u: also stash UNTRACKED files
git status
# nothing to commit, working tree clean — changes are stashed

# Switch context (urgent fix):
git checkout -b hotfix/urgent-fix
echo "hotfix content" > hotfix.txt
git add hotfix.txt && git commit -m "apply urgent hotfix"
git checkout main

# Restore your work:
git stash pop
git status
# Modified: notes.txt, debug_tool.py — restored exactly as left

# Two stashes
echo "stash entry 1" >> notes.txt
git stash    # stash 1 (becomes stash@{0})
echo "stash entry 2" >> debug_tool.py
git stash    # stash 2 (becomes stash@{0}, old entry becomes stash@{1})
git stash list
# stash@{0}: WIP on main: abc1234 ...   ← newest
# stash@{1}: WIP on main: def5678 ...   ← older

git stash show -p stash@{1}    # preview without applying
git stash apply stash@{1}       # apply the older one specifically (doesn't remove)
git stash drop stash@{1}        # manually remove it after applying
git stash pop                    # apply and remove stash@{0}

# Part C — Restore and Clean
echo "unwanted change" >> notes.txt
git status
# Modified: notes.txt

# Discard the unstaged change:
git restore notes.txt
git status     # clean — change discarded, NOT recoverable (no reflog for restore)
cat notes.txt  # back to its previous committed content

# Stage something, then unstage:
echo "temporary staging" >> notes.txt
git add notes.txt
git status     # Changes to be committed
git restore --staged notes.txt
git status     # Changed but not staged — back to working dir, file still modified
git restore notes.txt    # now discard the unstaged change too

# Untracked files cleanup:
mkdir junk-dir
echo "junk1" > junk1.txt
echo "junk2" > junk2.txt
echo "junk" > junk-dir/junk3.txt
git status     # Untracked: junk1.txt, junk2.txt, junk-dir/

git clean -n   # DRY RUN — always first
# Would remove junk1.txt
# Would remove junk2.txt
# (dirs not shown without -d)

git clean -n -d    # include directories
# Would remove junk1.txt
# Would remove junk2.txt
# Would remove junk-dir/

git clean -fd      # actually delete files AND dirs
# Removing junk1.txt
# Removing junk2.txt
# Removing junk-dir/
git status         # clean

# Part D — Detached HEAD
SOME_OLD_SHA=$(git log --oneline | tail -2 | head -1 | awk '{print $1}')
git checkout "$SOME_OLD_SHA"
git status
# HEAD detached at abc1234
# Not currently on any branch.

# Make a commit while detached:
echo "detached work" > detached_file.txt
git add detached_file.txt
git commit -m "work done in detached HEAD state"
DETACHED_SHA=$(git rev-parse HEAD)
echo "Detached commit SHA: $DETACHED_SHA"

# Switch away — detached commit is now ORPHANED:
git checkout main
git log --oneline | grep "detached"   # not found — it's not on any branch

# Recover the orphaned commit:
git checkout -b recovery-branch "$DETACHED_SHA"
git log --oneline | head -3
# recovery-branch now starts at the detached commit — it's saved

# Merge recovered work into main if needed:
git checkout main
git merge recovery-branch --no-ff -m "recover detached work"
git branch -d recovery-branch   # clean up

# Alternative recovery if you already lost track of the SHA:
git reflog | grep "detached"
# HEAD@{N}: commit: work done in detached HEAD state   ← find the SHA here
```

**The hook architecture principle:** hooks are LOCAL and bypassable with `--no-verify`. The `pre-commit` framework (`.pre-commit-config.yaml`) shares hook config with the team via version control, so `pre-commit install` wires it up for every developer. But the same checks must ALSO run in CI — hooks are a fast-feedback loop, not a security control.

</details>

---

## Lab 7: Production Problems Rehearsal

**Objective:** Run through 6 real Git problem scenarios back-to-back. These are the exact situations from the theory file's Production Problems section — practice them so the fix is muscle memory, not a frantic web search at 2am.

**Setup:**

```bash
mkdir -p ~/git-prod-lab && cd ~/git-prod-lab
git init && git config user.email "lab@example.com" && git config user.name "Lab User"
# Create a realistic starting state:
echo "version = 1.0.0" > config.py
echo "DB_URL = 'postgres://localhost/mydb'" >> config.py
echo "SECRET_KEY = 'not-a-secret-in-prod'" >> config.py
git add config.py && git commit -m "initial config"
echo "def process_order(order): pass" > orders.py
git add orders.py && git commit -m "add order processor"
echo "def send_email(to, body): pass" > email.py
git add email.py && git commit -m "add email sender"
```

---

**Scenario 1: Committed to the wrong branch**

```bash
# Scenario: you added two commits to main that should have been on feature/payment

echo "def validate_card(num): pass" >> orders.py
git add orders.py && git commit -m "add card validation"
echo "def charge_card(num, amount): pass" >> orders.py
git add orders.py && git commit -m "add card charging"

# Oops — these should be on feature/payment, not main

# Fix:
WRONG_COMMIT_1=$(git log --oneline | sed -n '2p' | awk '{print $1}')
CORRECT_POINT=$(git log --oneline | sed -n '3p' | awk '{print $1}')

# Step 1: create the right branch AT current HEAD (WITH your two commits)
git checkout -b feature/payment
# feature/payment now has your 2 commits

# Step 2: move main back to before the wrong commits
git checkout main
git reset --hard "$CORRECT_POINT"

# Verify:
git log main --oneline | head -3         # main: no card commits
git log feature/payment --oneline | head -3  # feature/payment: has them
echo "Scenario 1: FIXED"
```

---

**Scenario 2: .gitignore not working — secret file already tracked**

```bash
# Scenario: someone committed .env before .gitignore existed

echo "DATABASE_PASSWORD=supersecret123" > .env
git add .env && git commit -m "add .env (mistake — should not be tracked)"

# Add .gitignore AFTER the fact:
echo ".env" > .gitignore
git add .gitignore && git commit -m "add .gitignore"

# Does git still track .env changes?
echo "DATABASE_PASSWORD=newsecret456" > .env
git status
# Modified: .env   ← YES, still tracked — .gitignore is too late

# Fix: untrack the file (keep it on disk):
git rm --cached .env
git commit -m "stop tracking .env"

# Verify:
echo "DATABASE_PASSWORD=yetanother789" > .env
git status
# .env now appears under "Untracked files" (not "Changes to be committed")
# gitignore NOW works because the file is no longer in the index
echo "Scenario 2: FIXED — .env is untracked"

# IMPORTANT: the password is STILL in git history (commits 1 and 2 above).
# In production, you must ALSO: rotate the secret AND run git filter-repo to
# remove it from history. Untracking does NOT erase past commits.
```

---

**Scenario 3: Wrong files in last commit — split a commit**

```bash
# Scenario: you committed both a feature AND a debug file in one commit

echo "def new_feature(): pass" > feature.py
echo "print('DEBUG: remove me')" > debug.py
git add feature.py debug.py
git commit -m "add new feature"

# Oops — debug.py should NOT be in this commit

# Fix: unstage everything, re-commit only the right file
git reset HEAD~1              # mixed reset: unstage all, keep files in working dir
git add feature.py             # only stage what belongs
git commit -m "add new feature (clean)"

# debug.py is still on disk, just not committed:
ls -la debug.py               # still exists
git status                    # shows as untracked — not in history
git clean -f                  # remove it
echo "Scenario 3: FIXED"
```

---

**Scenario 4: Recover commits lost to `git reset --hard`**

```bash
# Scenario: you ran reset --hard and realized you needed those commits

echo "important work A" > important.py
git add important.py && git commit -m "important work A"
echo "important work B" >> important.py
git add important.py && git commit -m "important work B"
echo "important work C" >> important.py
git add important.py && git commit -m "important work C"

# Disaster: accidentally reset --hard back 3 commits
git reset --hard HEAD~3
cat important.py 2>/dev/null || echo "file gone"   # important.py is gone

# Recovery via reflog:
git reflog | head -8
# HEAD@{0}: reset: moving to HEAD~3
# HEAD@{1}: commit: important work C   ← this is what we want
# HEAD@{2}: commit: important work B
# HEAD@{3}: commit: important work A

LOST_SHA=$(git reflog | grep "important work C" | head -1 | awk '{print $1}')
git reset --hard "$LOST_SHA"
cat important.py
# important work A
# important work B
# important work C    ← fully recovered
echo "Scenario 4: FIXED"
```

---

**Scenario 5: Undo a commit already "pushed" to a shared branch**

```bash
# Scenario: a bad commit landed on main and was "pushed"
# (We can't actually push here, but simulate by using revert as if it were)

echo "def dangerous_function(): os.system('rm -rf /')" > dangerous.py
git add dangerous.py && git commit -m "add utility function (bad code)"
BAD_SHA=$(git rev-parse HEAD)

# The WRONG approach (only safe if truly not yet pushed):
# git reset --hard HEAD~1

# The CORRECT approach for shared/pushed history:
git revert "$BAD_SHA" --no-edit
# Creates: "Revert 'add utility function (bad code)'"

git log --oneline | head -4
# revert_sha Revert "add utility function (bad code)"   ← NEW commit
# bad_sha add utility function (bad code)              ← ORIGINAL still in history
# ...

cat dangerous.py 2>/dev/null || echo "dangerous.py removed by revert"
echo "Scenario 5: FIXED — history preserved, bad code removed"
```

---

**Scenario 6: Detached HEAD with work to save**

```bash
# Scenario: you checked out an old SHA to investigate, accidentally made commits

OLD_SHA=$(git log --oneline | tail -2 | head -1 | awk '{print $1}')
git checkout "$OLD_SHA"
# HEAD is now in detached state

echo "investigation notes: issue is in line 42" > investigation.txt
git add investigation.txt
git commit -m "document investigation findings"
DETACHED_SHA=$(git rev-parse HEAD)

# Now you realize you need to keep this commit
git checkout main

# The commit is orphaned — not on any branch
git log main --oneline | head -3   # investigation.txt commit not here

# Recover it:
git checkout -b investigation-notes "$DETACHED_SHA"
git log --oneline | head -3
# investigation-notes branch now has the commit — saved

# If you want it on main:
git checkout main
git cherry-pick "$DETACHED_SHA"
git branch -d investigation-notes  # clean up
git log --oneline | head -3
# investigation commit is now on main
echo "Scenario 6: FIXED"

# Clean up lab:
cd ~/git-lab
rm -rf ~/git-prod-lab
```

---

## Self-Check Checklist

**Git Internals:**
- [ ] Can you explain what a blob, tree, commit, and tag object each store?
- [ ] Can you explain why rebase changes commit SHAs even when the code diff is identical?
- [ ] Can you explain why a branch being "just a file with a SHA" means branches are cheap to create?

**Core Commands:**
- [ ] Can you stage individual hunks within a file (not the whole file) with one flag?
- [ ] Can you explain the two-dot vs three-dot diff difference (`main..feature` vs `main...feature`) and which one you want when reviewing a PR?
- [ ] Do you know the difference between `git restore --staged file` and `git restore file`?
- [ ] Can you remove an untracked directory safely (dry run first, then actual delete)?

**Branches and Merging:**
- [ ] Can you identify a fast-forward vs three-way merge in `git log --graph` output?
- [ ] Can you explain why `--no-ff` creates a merge commit even when fast-forward is possible, and when you'd want that?
- [ ] Can you cherry-pick one commit onto a different branch and verify nothing else came along?

**Rebase:**
- [ ] Can you explain the golden rule of rebase (when safe vs never safe) in one sentence?
- [ ] Can you use `git rebase -i HEAD~N` to squash commits, reorder them, or reword messages?
- [ ] When a rebase conflict occurs, do you know what HEAD means in that context (the new base, not your branch)?

**Reset, Revert, Reflog:**
- [ ] Can you explain --soft/--mixed/--hard in terms of which circles (committed/staged/working dir) they rewind?
- [ ] Can you state the rule: "undo local work → reset, undo shared/pushed work → revert"?
- [ ] Have you actually used `git reflog` to recover commits from an accidental `git reset --hard`?

**Remote and Push:**
- [ ] Can you explain why `--force-with-lease` is safer than `--force` with a concrete scenario?
- [ ] Can you set up a remote-tracking branch with `git push -u` and then push with just `git push`?
- [ ] Can you delete a branch on the remote from the command line?

**Hooks:**
- [ ] Can you write a pre-commit hook that blocks commits containing a forbidden string?
- [ ] Can you explain why hooks are local and bypassable — and what must also run in CI as a result?
- [ ] Can you explain the role of `.pre-commit-config.yaml` vs raw `.git/hooks/` scripts?

**Production Problems:**
- [ ] Can you move commits from the wrong branch to the right one (reset + checkout -b)?
- [ ] Can you stop tracking a file that .gitignore is failing on (git rm --cached)?
- [ ] Can you recover lost commits after `git reset --hard` using reflog?
- [ ] Can you enter and exit detached HEAD state intentionally, and recover orphaned commits?
- [ ] Can you explain why reverting a revert before re-merging a branch is necessary?

---

## Related Files

- [`../01_git_deep_dive.md`](../01_git_deep_dive.md) — full theory reference
- [`../../01_Linux/practical/01_linux_lab.md`](../../01_Linux/practical/01_linux_lab.md) — Lab 6 hook scripts use bash patterns from Linux phase
- [`../../10_CICD/`](../../10_CICD/) — where the same checks as pre-commit hooks run unskippably