# Git — Hands-On Lab
**DevOps Track · Phase 4 Practical**

## Prerequisites

- Git installed locally (`git --version` — anything 2.30+ is fine). No account or remote needed for Labs 1-3; Lab 4 mentions `gh` (GitHub CLI) as optional, not required.
- Work entirely in a throwaway local repo — nothing here touches a real remote, so there's zero risk to any existing project.
- Set up the lab: `mkdir -p ~/git-lab && cd ~/git-lab && git init && git config user.email "lab@example.com" && git config user.name "Lab User"`.

---

## Lab 1: Branching, Merging, and Reading History

**Objective:** Build muscle memory for the everyday branch/commit/merge flow and get comfortable reading `git log --graph`.

**Task:**
1. On `main`, create a file `app.py` with a single line `print("v1")`, commit it.
2. Create and switch to a branch `feature/greeting`, change the line to `print("hello, v2")`, commit.
3. Switch back to `main`, create a DIFFERENT change on `main` itself — add a second file `README.md` with any content, commit it (this is what creates true divergence, not a fast-forward).
4. Merge `feature/greeting` into `main` using `--no-ff` explicitly (even though a normal merge here wouldn't fast-forward anyway, since main has diverged) and confirm a merge commit was created with two parents.
5. Run `git log --oneline --graph --all` and identify, just from the ASCII graph, where the branch split and where it merged back.
6. Delete the now-merged `feature/greeting` branch safely (the flag that refuses if unmerged — confirm it succeeds because it WAS merged).

<details>
<summary>Solution / walkthrough</summary>

```bash
# 1. main baseline
echo 'print("v1")' > app.py
git add app.py
git commit -m "initial app.py"

# 2. feature branch
git checkout -b feature/greeting
echo 'print("hello, v2")' > app.py
git add app.py
git commit -m "update greeting to v2"

# 3. diverge main independently
git checkout main
echo "# Lab Project" > README.md
git add README.md
git commit -m "add README"

# 4. merge with an explicit merge commit
git merge --no-ff feature/greeting -m "merge feature/greeting into main"
git show --no-patch --format="%H %P" HEAD
# HEAD's output line shows TWO parent hashes after the commit hash —
# that's the concrete proof this is a real merge commit, not a fast-forward

# 5. Visualize
git log --oneline --graph --all
# *   a1b2c3d (HEAD -> main) merge feature/greeting into main
# |\
# | * f4e5d6c (feature/greeting) update greeting to v2
# * | 9c8b7a6 add README
# |/
# * 1234567 initial app.py
#
# Reading this: the branch splits at 1234567 (the first commit both
# share), feature/greeting adds one commit on its own line, main adds
# a DIFFERENT commit on its own line, and the merge commit at the top
# is where both lines converge back into one.

# 6. Safe delete
git branch -d feature/greeting
# Deleted branch feature/greeting (was f4e5d6c).
# (-d, not -D, succeeds here specifically because its commit is
# reachable from main after the merge — try -d on an UNMERGED branch
# and git will refuse, which is the whole point of the safe flag)
```
</details>

---

## Lab 2: Rebase, Cherry-Pick, and Conflict Resolution

**Objective:** Get hands dirty with the operations that actually rewrite history, and resolve a real conflict from raw markers to a clean commit — the skill from the lesson's "Conflict Resolution — Walked Through" section, done yourself instead of just read.

**Task:**
1. Starting fresh (or continuing from Lab 1), create a file `pricing.py` on `main` with `def discount(price):\n    return price * 0.9\n`, commit it.
2. Create branch `feature/pricing`, change the discount to `0.85`, commit.
3. Switch back to `main`, independently change the SAME line to `0.8` (simulating two people editing the same function differently), commit.
4. Attempt `git merge feature/pricing` on `main` — it should conflict. Open the file, see the `<<<<<<<`/`=======`/`>>>>>>>` markers, resolve it by picking `0.85` as the final answer (write the file to have ONLY that value, no markers left), stage, and complete the merge commit.
5. Now practice rebase separately: create a NEW branch `feature/tax` off `main`, add a `def tax(price): return price * 0.18` function to `pricing.py`, commit. Meanwhile add one more unrelated commit directly on `main` (e.g. a comment). Rebase `feature/tax` onto the new `main` tip with `git rebase main`, resolving any conflict if one appears.
6. Practice cherry-pick: note the SHA of the `tax` commit, create a fresh branch `release/1.0` from the ORIGINAL pre-rebase point (or just from current main, whichever is available), and cherry-pick ONLY that tax commit onto it — confirm `pricing.py` on `release/1.0` has the tax function but nothing else from `feature/tax`'s other work (there isn't other work in this lab, but describe how you'd verify that with `git log`/`git diff` if there were).

<details>
<summary>Solution / walkthrough</summary>

```bash
# 1. Baseline
printf 'def discount(price):\n    return price * 0.9\n' > pricing.py
git add pricing.py
git commit -m "add discount function"

# 2. feature branch changes it to 0.85
git checkout -b feature/pricing
sed -i.bak 's/0.9/0.85/' pricing.py && rm pricing.py.bak   # macOS-safe sed -i
git add pricing.py
git commit -m "bump discount to 0.85"

# 3. main independently changes it to 0.8
git checkout main
sed -i.bak 's/0.9/0.8/' pricing.py && rm pricing.py.bak
git add pricing.py
git commit -m "bump discount to 0.8"

# 4. Merge -> conflict
git merge feature/pricing
# CONFLICT (content): Merge conflict in pricing.py

cat pricing.py
# def discount(price):
# <<<<<<< HEAD
#     return price * 0.8
# =======
#     return price * 0.85
# >>>>>>> feature/pricing

# Resolve by hand — decide 0.85 is correct, remove ALL marker lines
printf 'def discount(price):\n    return price * 0.85\n' > pricing.py
git add pricing.py
git status                    # confirm no other files still conflicted
git commit                    # opens editor pre-filled with a merge message; save and close

# 5. Rebase practice
git checkout -b feature/tax
cat >> pricing.py << 'EOF'

def tax(price):
    return price * 0.18
EOF
git add pricing.py
git commit -m "add tax function"

git checkout main
echo "# pricing helpers" | cat - pricing.py > tmp && mv tmp pricing.py
git add pricing.py
git commit -m "add file header comment"

git checkout feature/tax
git rebase main
# if a conflict appears (likely, since both touched pricing.py), resolve
# the same way as step 4: edit -> remove markers -> git add -> then:
# git rebase --continue
git log --oneline --graph --all
# feature/tax's commit now sits ON TOP of main's latest tip, with a
# NEW SHA — same content, different parent, different hash (this is
# the "why does rebase change commit hashes" point from the lesson,
# now visible in your own history)

# 6. Cherry-pick onto a release branch
TAX_SHA=$(git log feature/tax --oneline --grep="add tax function" --format="%H")
git checkout main
git checkout -b release/1.0
git cherry-pick "$TAX_SHA"
git log release/1.0 --oneline
# shows the base main history PLUS exactly one extra commit (the tax
# function) — none of feature/tax's other commits came along, because
# cherry-pick applies exactly the one SHA you named, unlike merge which
# would have pulled in the whole branch
grep -A2 "def tax" pricing.py    # confirm the function landed correctly
```

**Key distinction to walk away with:** merge/rebase move or combine entire branches; cherry-pick moves exactly one named commit. This is precisely why cherry-pick is the standard tool for backporting a single hotfix to a release branch without dragging in everything else that happened on `main` since the branch point.
</details>

---

## Lab 3: Reset vs Revert — Recover From Mistakes Safely

**Objective:** Prove to yourself, hands-on, why `reset --hard` on shared history is dangerous and `revert` is the safe alternative — and that `reflog` really is a safety net.

**Task:**
1. On a fresh branch `experiment` (branch off `main` from any state above), make 3 separate commits, each appending one line to a file `notes.txt` (`line1`, `line2`, `line3`).
2. Use `git reset --soft HEAD~1` to undo the LAST commit only. Confirm with `git status` that `line3`'s change is now staged (not committed, not lost).
3. Commit it again with a different message, so you're back to 3 commits total but the last one has new wording.
4. Now simulate "oops, I need to fully discard my last commit and its changes" — use `git reset --hard HEAD~1`. Confirm `notes.txt` only has `line1` and `line2`, and `git status` is clean.
5. Recover the "lost" commit using `git reflog` — find the SHA from before the hard reset, and `git reset --hard` back to it. Confirm `line3` is back.
6. Now simulate the SAFE way to undo a commit that's already been "shared" (pretend the last commit was pushed and a teammate might have it): use `git revert` instead of reset. Confirm it creates a NEW commit whose diff removes `line3`'s change, while the original commit still exists in `git log`.
7. Explain in one sentence why step 6's approach is the only safe option once history is shared, referencing what would happen to a teammate's clone if you'd used `reset --hard` + force-push instead.

<details>
<summary>Solution / walkthrough</summary>

```bash
git checkout main
git checkout -b experiment

echo "line1" > notes.txt && git add notes.txt && git commit -m "add line1"
echo "line2" >> notes.txt && git add notes.txt && git commit -m "add line2"
echo "line3" >> notes.txt && git add notes.txt && git commit -m "add line3"

# 2. Soft reset — undo last commit, keep staged
git reset --soft HEAD~1
git status
# Changes to be committed:
#   modified: notes.txt
cat notes.txt         # still has all 3 lines — soft reset never touches
                        # the working directory, only the commit pointer

# 3. Recommit with different wording
git commit -m "add line3 (reworded)"

# 4. Hard reset — fully discard
git reset --hard HEAD~1
cat notes.txt
# line1
# line2
git status
# nothing to commit, working tree clean
# line3 is GONE from both the commit history and the working file

# 5. Recover via reflog
git reflog
# a1b2c3d (HEAD -> experiment) HEAD@{0}: reset: moving to HEAD~1
# f4e5d6c HEAD@{1}: commit: add line3 (reworded)     <- this is what we want back
# ...
git reset --hard f4e5d6c    # use the actual SHA from your own reflog output
cat notes.txt
# line1
# line2
# line3 (reworded)          <- recovered

# 6. Revert instead of reset (the "already shared" safe path)
git log --oneline
# f4e5d6c add line3 (reworded)     <- pretend this is already pushed/shared
# ...
git revert f4e5d6c --no-edit
git log --oneline
# 7g8h9i0 Revert "add line3 (reworded)"    <- NEW commit
# f4e5d6c add line3 (reworded)             <- ORIGINAL commit, still present
# ...
cat notes.txt
# line1
# line2
# (line3 is gone from the FILE, but the commit that added it is still
# visible in history — nothing was erased, only counter-applied)

# 7.
# If f4e5d6c had genuinely been pushed and a teammate already pulled it,
# `git reset --hard` + `git push --force` would rewrite the branch tip
# out from under them — their local branch would now contain a commit
# (f4e5d6c) that no longer exists in the remote's ancestry, producing a
# diverged branch and confusing conflicts on their NEXT pull; `git
# revert` avoids this entirely because it only ADDS a new commit, never
# rewrites or removes anything anyone else may have already based work on.
```
</details>

---

## Lab 4: Recover From a Force-Push Disaster (Production-Style Scenario)

**Objective:** Simulate the exact "someone force-pushed and now history looks wrong" incident, and practice `push --force-with-lease` as the safer alternative — closest thing to a real Git incident you can safely rehearse.

**Task:**

Since this needs two "copies" of a repo to be realistic, simulate a remote using a second local bare repo instead of GitHub (works identically for this exercise, zero setup friction, no account needed).

1. Create a bare "remote": `git init --bare ~/git-lab-remote.git`.
2. Clone it twice into two separate working directories, simulating you and a teammate: `git clone ~/git-lab-remote.git ~/git-lab-you` and `git clone ~/git-lab-remote.git ~/git-lab-teammate`.
3. In `~/git-lab-you`: make a commit, push to `origin main`.
4. In `~/git-lab-teammate`: pull, make a DIFFERENT commit, push to `origin main`.
5. In `~/git-lab-you`: WITHOUT pulling teammate's change first, amend your own last commit (`git commit --amend`) and attempt a bare `git push --force`. Observe that it succeeds and silently discards the teammate's commit from the remote's history (this is the disaster).
6. In `~/git-lab-teammate`: run `git fetch` and `git log --oneline --graph --all` — observe that their commit now only exists locally, orphaned from `origin/main`.
7. Recover: in `~/git-lab-teammate`, find their orphaned commit's SHA via `git reflog` or `git log` on their local branch before the fetch overwrote the remote-tracking ref, and re-apply it on top of the current `origin/main` (cherry-pick it back on), then push normally.
8. Redo the disaster scenario from step 5, but this time use `git push --force-with-lease` instead of `--force` after a teammate has pushed in between — confirm it REFUSES and tells you why, instead of silently clobbering.

<details>
<summary>Solution / walkthrough</summary>

```bash
# 1-2. Set up a fake remote + two clones
git init --bare ~/git-lab-remote.git
git clone ~/git-lab-remote.git ~/git-lab-you
git clone ~/git-lab-remote.git ~/git-lab-teammate

# 3. You push first
cd ~/git-lab-you
git config user.email you@example.com && git config user.name "You"
echo "feature A" > work.txt
git add work.txt && git commit -m "you: feature A"
git push origin main

# 4. Teammate pulls, adds their own work, pushes
cd ~/git-lab-teammate
git config user.email teammate@example.com && git config user.name "Teammate"
git pull origin main
echo "feature B" >> work.txt
git add work.txt && git commit -m "teammate: feature B"
git push origin main

# 5. THE DISASTER — you amend + force push without pulling first
cd ~/git-lab-you
git commit --amend -m "you: feature A (amended, forgot to pull teammate's work first)"
git push --force origin main
# Everything up-to-date... wait, actually:
# + a1b2c3d...f4e5d6c main -> main (forced update)
# This SUCCEEDED — and it just silently overwrote teammate's pushed
# commit on the shared remote. This is the disaster.

# 6. Teammate discovers the damage
cd ~/git-lab-teammate
git fetch origin
git log --oneline --graph --all
# origin/main now points at YOUR amended commit — teammate's "feature B"
# commit is no longer reachable from origin/main at all, only from their
# own local branch ref / reflog

# 7. Recovery
cd ~/git-lab-teammate
git reflog
# shows teammate's own "teammate: feature B" commit SHA, still intact
# LOCALLY even though origin/main no longer contains it
TEAMMATE_SHA=$(git log --all --oneline --grep="feature B" --format="%H" | head -1)
git checkout main
git reset --hard origin/main         # sync to the new (damaged) remote tip first
git cherry-pick "$TEAMMATE_SHA"       # re-apply the orphaned commit on top
git push origin main
# teammate's work is restored on the shared remote, now sitting on top
# of your amended commit instead of being lost

# 8. Redo safely with --force-with-lease
cd ~/git-lab-you
echo "another change" >> work.txt
git add work.txt && git commit --amend -m "you: another amend, still haven't pulled"

# Meanwhile pretend teammate pushed again in ~/git-lab-teammate (or just
# push directly from that clone to simulate it):
cd ~/git-lab-teammate
echo "feature C" >> work.txt
git add work.txt && git commit -m "teammate: feature C"
git push origin main

# Back in ~/git-lab-you, attempt the same reckless force push:
cd ~/git-lab-you
git push --force-with-lease origin main
# ! [rejected] main -> main (stale info)
# error: failed to push some refs
# — REFUSED, because --force-with-lease checks that origin/main is
# still exactly where YOUR local knowledge of it last saw it; since
# teammate pushed in between, the lease is stale and git fails safe
# instead of clobbering their new commit.
git pull --rebase origin main    # the correct next step: integrate first
git push origin main              # now a normal, safe push
```

**The one-sentence takeaway:** `--force` overwrites the remote unconditionally based on nothing but your own local state; `--force-with-lease` overwrites the remote ONLY if nobody else has pushed since you last looked — which is why the lesson's rule ("never bare `--force`, always `--force-with-lease`") isn't pedantry, it's the difference between "safe by default" and "silently destroys a teammate's work."
</details>

---

## Self-Check Checklist

- [ ] Can you explain fast-forward vs three-way merge, and identify which one just happened from reading `git log --graph` output?
- [ ] Can you resolve a real merge conflict from raw `<<<<<<<`/`=======`/`>>>>>>>` markers to a clean commit, without panicking?
- [ ] Can you explain why rebase changes commit hashes even when the code diff is identical?
- [ ] Do you know the golden rule for when it's safe to rebase vs when it's never safe?
- [ ] Can you cherry-pick exactly one commit onto a different branch and verify nothing else came along with it?
- [ ] Can you explain `--soft` vs `--mixed` vs `--hard` reset clearly enough to teach it to someone else?
- [ ] Have you actually used `git reflog` to recover from a hard reset, at least once?
- [ ] Can you explain reset vs revert and state the rule for which one to use on shared/pushed history?
- [ ] Can you explain, from having watched it happen, exactly what `--force` does wrong that `--force-with-lease` prevents?
- [ ] Can you walk someone through backporting a single hotfix to a release branch using cherry-pick, without merging unreleased work?
