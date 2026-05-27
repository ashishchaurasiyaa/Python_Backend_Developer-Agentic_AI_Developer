# Foundations — Git Workflows for Backend Devs
**Phase 0 Foundations | Zero → Senior**

## Quick Concepts

- **Repository (repo)** = the entire project history + tracked files
- **Working directory** = files you see/edit in your filesystem
- **Staging area (index)** = the proposed next commit
- **Commit** = snapshot with hash, author, message, parent commit
- **Branch** = movable pointer to a commit
- **HEAD** = pointer to your current commit/branch
- **Remote** = a server-side copy (e.g., GitHub)
- **Origin** = default name for the remote you cloned from
- **Merge** = combine two histories into a new commit
- **Rebase** = move commits onto a different base
- **Pull = fetch + merge** (or fetch + rebase)
- **Push** = send local commits to remote
- **Stash** = temporary save of uncommitted changes

---

## Why Every Backend Dev Must Know This

```
Git is the universal version control. You'll touch it daily:

   ✓ Commit your code
   ✓ Review someone else's PR
   ✓ Resolve merge conflicts
   ✓ Cherry-pick a hotfix to a release branch
   ✓ Bisect to find which commit broke prod
   ✓ Rebase your feature branch before merging
   ✓ Tag releases

Senior interviews ALWAYS probe Git fluency.
"How do you handle merge conflicts?" — bad answer is a red flag.
```

---

## The Core Model

```
   Working Directory   →    Staging Area   →    Repository
   (your files)             (git add)            (git commit)

   git add foo.py     adds to staging
   git commit -m "X"  snapshots staging
   git checkout HEAD~ replays working from repo

Anything not committed is "lost" on hard operations.
Git's golden rule: COMMIT EARLY, COMMIT OFTEN.
```

### State Diagram

```
   ┌─────────────┐   git add    ┌──────────┐   git commit   ┌──────────┐
   │ Working dir │ ───────────► │ Staging  │  ────────────► │  Repo    │
   │ (modified)  │              │ (index)  │                │ (HEAD)   │
   └─────────────┘              └──────────┘                └──────────┘
        ▲                                                        │
        │            git checkout / git reset --hard             │
        └────────────────────────────────────────────────────────┘
```

---

## Daily Commands (Cheat Sheet)

```bash
# Status + history
git status
git log --oneline -10
git log --graph --oneline --all --decorate
git diff
git diff --staged           # what will go into next commit

# Commit
git add file.py
git add .                   # all changes
git add -p                  # interactive (pick chunks)
git commit -m "feat: add login"
git commit --amend          # edit last commit (CAREFUL if pushed)

# Push / pull
git push                    # to current branch's remote
git push -u origin feature  # set upstream + push
git pull                    # fetch + merge
git pull --rebase           # fetch + rebase (cleaner history)
git fetch                   # download but don't merge

# Branch
git branch                  # list local
git branch -a               # local + remote
git checkout -b feature     # create + switch
git switch feature          # newer syntax
git switch -c feature       # create + switch (new syntax)
git branch -d feature       # delete (must be merged)
git branch -D feature       # FORCE delete

# Sync
git checkout main
git pull
git checkout feature
git rebase main             # OR: git merge main
```

---

## Commit Discipline

### Anatomy of a Good Commit

```
feat: add OAuth2 PKCE flow for mobile clients

- Adds /auth/pkce/start and /finish endpoints
- Stores code_verifier in Redis with 5min TTL
- Updates docs with new flow diagram

Closes #234
```

### Conventional Commits Format

```
<type>(<scope>): <subject>

Common types:
   feat     — new feature
   fix      — bug fix
   docs     — documentation only
   style    — formatting (no logic change)
   refactor — internal restructure (no behavior change)
   perf     — performance improvement
   test     — tests only
   chore    — tooling / build / deps
   ci       — CI/CD config
   build    — build system / deps

Examples:
   feat(auth): add passkey support
   fix(db): handle connection pool exhaustion
   refactor(api): extract pagination utility
   test(orders): add saga compensation cases
   chore(deps): bump fastapi to 0.110.0
```

### Why It Matters

```
✓ Easy to scan git log
✓ Auto-generate CHANGELOG (semantic-release)
✓ Auto-version bumps (major/minor/patch)
✓ Easier code reviews
✓ Better git bisect (find which commit broke)
```

---

## Branching Strategies

### 1. GitHub Flow (Simple — Recommended for Most)

```
main ─────●─────●─────●─────●─────●─────●─────
              │       │           │
              └───────●           │
              feature              │
              (PR merged)          │
                                   │
                                   ●─── hotfix
```

- One long-running branch: `main`
- Feature branches off `main`, PR back to `main`
- Deploy from `main` continuously (CI/CD)

Pros: simple, fast, modern
Cons: needs strong CI + feature flags

### 2. Git Flow (Heavyweight — Releases)

```
main      ●─────●─────●  (production releases only)
              ╲   ╱
develop   ●─●─●─●─●─●  (integration branch)
            │       │
            └───────●  (feature branches)
                    │
release branches    ●─── hotfix branches
```

- `main` = production, `develop` = next release
- `release/*`, `hotfix/*`, `feature/*` branches
- Pros: clear separation, good for versioned releases
- Cons: slower, more ceremony

### 3. Trunk-Based Development

```
main ─●─●─●─●─●─●─●─●─●─●─●─●─
        │ │     │     │
        └─┘ short-lived feature branches (hours-days)
            merged via PR + CI
```

- Pioneered by Google, Facebook
- All work on `main` (or short branches)
- Pros: continuous integration, no merge hell
- Cons: requires high-trust + feature flags

### Senior Recommendation

```
✓ Small team (< 10 devs) → GitHub Flow
✓ Mature CI/CD + feature flags → Trunk-based
✓ Versioned releases (libraries, mobile) → Git Flow
✓ Default for most companies → GitHub Flow
```

---

## Pull Request Workflow

### Typical Flow

```
1. git checkout -b feature/oauth-pkce main
2. work, commit, work, commit
3. git push -u origin feature/oauth-pkce
4. Open PR on GitHub
5. CI runs (tests, linters)
6. Code review
7. Address feedback (more commits)
8. Squash and merge (or rebase and merge)
9. Delete branch
```

### PR Description Template

```markdown
## Summary
Brief explanation of WHAT and WHY.

## Changes
- Bullet list of major changes
- Each item explained

## Test Plan
- [ ] Unit tests added
- [ ] Integration tests pass
- [ ] Manual smoke test

## Screenshots / Demos
(if UI changes)

## Related Issues
Closes #123
```

### Senior Pattern: Small PRs

```
✗ "Refactor user module + add login + fix bug + style"
   → 2000 lines, takes 2 hours to review, bugs slip through

✓ Three separate PRs, each ~200 lines
   → Fast review, easier rollback, better git history
```

---

## Rebase vs Merge

### Merge

```
   main  ─●─●─●─●─────●(merge commit)
                       │
   feature ●─●─●──────┘

   Result: history shows divergence + merge point
   ✓ Preserves exact branch history
   ✓ Non-destructive
   ✗ Cluttered log over time
```

### Rebase

```
   main    ─●─●─●─●
                    \
   feature           ●─●─●  (rebased onto latest main)

   Result: linear history, no merge commit
   ✓ Clean linear log
   ✗ Rewrites history (DON'T rebase pushed/shared branches!)
```

### Workflow

```bash
# Before merging your feature to main, sync with main:
git checkout feature
git fetch origin
git rebase origin/main

# Resolve conflicts (if any)
# After successful rebase:
git push --force-with-lease    # NOT --force, safer

# THEN open PR / merge
```

### Senior Rule of Thumb

```
✓ Rebase YOUR branch onto main before opening PR
✓ Squash + merge for feature → main (clean history)
✗ NEVER rebase shared / pushed-to-by-others branches
✗ NEVER force push to main
```

---

## Merge Conflicts

### Step-by-Step Resolution

```bash
# 1. Try the merge/rebase
git merge main      # or: git rebase main

# 2. Conflict — Git shows:
# Auto-merging app/auth.py
# CONFLICT (content): Merge conflict in app/auth.py

# 3. Check status
git status
# Shows files in conflict

# 4. Open conflicted file — looks like:
def authenticate(user):
<<<<<<< HEAD
    return verify_password(user.password)
=======
    return verify_with_passkey(user.passkey)
>>>>>>> main

# 5. Edit the file to the correct final state
# (combine both, pick one, etc.)

def authenticate(user):
    if user.passkey:
        return verify_with_passkey(user.passkey)
    return verify_password(user.password)

# 6. Mark resolved
git add app/auth.py

# 7. Continue
git rebase --continue   # or: git merge --continue (for merge)

# 8. Abort if stuck
git rebase --abort      # or: git merge --abort
```

### Tools

```
✓ git mergetool          — opens visual tool
✓ VS Code built-in       — three-way diff UI
✓ IntelliJ git merge     — best UI
```

### Senior Tip: Reduce Conflicts

```
✓ Pull/rebase often (daily, not weekly)
✓ Small PRs merged fast
✓ Discuss big refactors in advance
✓ Clear module boundaries
```

---

## Useful Advanced Commands

### Stash

```bash
git stash               # save current changes
git stash list          # see saved stashes
git stash pop           # restore last stash
git stash apply         # restore but keep in list
git stash drop          # delete a stash

# With message
git stash push -m "WIP: trying X approach"
```

### Cherry-Pick

```bash
# Apply one commit from another branch to current
git cherry-pick abc123

# Apply range
git cherry-pick abc123^..def456

# Use case: hotfix on main, need same fix on release branch
git checkout release/v2.0
git cherry-pick <hotfix-commit-hash>
```

### Bisect (Find Bug-Introducing Commit)

```bash
git bisect start
git bisect bad              # current is broken
git bisect good v1.5        # last known good

# Git checks out middle commit
# Test it, then:
git bisect good    # or: git bisect bad

# Git narrows down via binary search
# Eventually: "abc123 is the first bad commit"

git bisect reset   # done
```

### Reflog (Recover "Lost" Commits)

```bash
git reflog            # shows EVERY HEAD movement
# Example output:
#   abc1234 HEAD@{0}: rebase: feat/auth
#   def5678 HEAD@{1}: commit: WIP
#   ghi9012 HEAD@{2}: checkout: feature

git reset --hard HEAD@{2}   # go back to that state

→ Almost nothing is truly lost in git
   (until garbage collection ~30 days)
```

### Tags (Release Markers)

```bash
git tag v1.0.0                  # lightweight
git tag -a v1.0.0 -m "Release"  # annotated (recommended)
git push origin v1.0.0
git push --tags                 # push all tags

git tag -l                      # list
git checkout v1.0.0             # detached HEAD
```

### Diff Variants

```bash
git diff                  # working dir vs staging
git diff --staged         # staging vs HEAD
git diff main feature     # branch comparison
git diff HEAD~3 HEAD      # last 3 commits
git diff --stat           # summary only
git diff --name-only      # just filenames
```

### Blame (Who Wrote This?)

```bash
git blame app/auth.py
git blame -L 50,100 app/auth.py    # line range
```

### Reset (Powerful, Use Carefully)

```bash
# Soft: move HEAD, keep staging + working
git reset --soft HEAD~1     # undo last commit, keep changes staged

# Mixed (default): move HEAD, reset staging, keep working
git reset HEAD~1            # undo last commit, unstage but keep edits

# Hard: move HEAD, reset staging + working (DANGEROUS)
git reset --hard HEAD~1     # nuke last commit + all changes
```

### Revert (Safe Undo of Pushed Commits)

```bash
git revert abc1234   # creates a NEW commit that undoes abc1234
# Safe for shared history (vs reset which rewrites)
```

---

## .gitignore Patterns

```gitignore
# Python
__pycache__/
*.pyc
*.pyo
.venv/
venv/
*.egg-info/

# Environment
.env
.env.local
*.local

# IDEs
.vscode/
.idea/
*.swp

# OS
.DS_Store
Thumbs.db

# Build
build/
dist/
*.so

# Coverage
.coverage
htmlcov/
coverage.xml

# Logs
*.log
logs/

# Secrets (NEVER commit)
*.pem
*.key
credentials.json

# Node (if frontend mixed in)
node_modules/
```

### Senior Mantra

```
.gitignore goes in FIRST.
Once a file is committed, removing from .gitignore won't untrack it.
Use git rm --cached <file> to untrack already-committed files.
```

---

## Hooks (Automation)

### Pre-Commit Hook

```bash
# .git/hooks/pre-commit (executable)
#!/usr/bin/env bash
set -e

# Run formatters + linters before commit
ruff check . || exit 1
ruff format --check . || exit 1
pytest -x tests/ || exit 1
```

### Pre-Commit Framework (Recommended)

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.4.0
    hooks:
      - id: ruff
      - id: ruff-format

  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.10.0
    hooks:
      - id: mypy
        additional_dependencies: [pydantic]

  - repo: https://github.com/zricethezav/gitleaks
    rev: v8.18.0
    hooks:
      - id: gitleaks   # detect committed secrets
```

```bash
pip install pre-commit
pre-commit install
# Now hooks run on every commit
```

---

## Submodules vs Subtrees vs Monorepo

### Submodule

```bash
git submodule add https://github.com/x/y libs/y
git submodule update --init --recursive

# Painful in practice
# Use only if you must reference specific external git repo
```

### Subtree

```bash
git subtree add --prefix=libs/y https://github.com/x/y main --squash

# Less painful than submodule
# Vendored copy with history
```

### Monorepo

```
One repo with everything: backend, frontend, infra, libs
✓ Atomic commits across services
✓ Shared tooling
✓ Easier refactoring
✗ Bigger repo, slower clone
✗ Needs sparse-checkout for large teams

Tools: Bazel, Nx, Turborepo, pants
Used by: Google, Meta, Twitter
```

---

## Git Best Practices

### Commit Messages

```
✓ Imperative mood: "Add feature" not "Added feature"
✓ < 72 chars per line
✓ Subject + blank + body
✓ Explain WHY not just WHAT
✗ "fixes" / "updates" / "changes"
```

### Branch Names

```
feature/oauth-pkce-flow
fix/payment-timeout
hotfix/critical-cve
refactor/extract-auth-module
docs/update-readme
chore/upgrade-fastapi
```

### Before Pushing Checklist

```
□ Code compiles / runs
□ Tests pass locally (pytest)
□ Linter passes (ruff)
□ Type checker passes (mypy)
□ No print() / debug code left
□ No secrets committed (gitleaks)
□ Commit message is descriptive
□ Squashed WIP commits if needed
```

### What to NEVER Commit

```
✗ .env files
✗ Secrets (keys, tokens, passwords)
✗ Generated files (compile, build artifacts)
✗ Large binaries (use Git LFS)
✗ Personal IDE configs (.idea, .vscode personal)
✗ OS metadata (.DS_Store, Thumbs.db)
✗ node_modules / .venv / __pycache__
✗ Database files
```

---

## Recovery Scenarios

### "I committed to the wrong branch"

```bash
git log               # find your commit hash
git checkout correct-branch
git cherry-pick <commit>
git checkout wrong-branch
git reset --hard HEAD~1
```

### "I committed a secret"

```bash
# Same day, not pushed yet:
git reset --soft HEAD~1
# remove secret from file
git add .
git commit -m "feat: ..."

# Already pushed:
# 1. ROTATE the secret immediately
# 2. Use git-filter-repo or BFG to clean history
# 3. Force push (CAREFUL — coordinate with team)
git filter-repo --invert-paths --path .env
git push --force-with-lease
```

### "I want to undo the last commit but keep changes"

```bash
git reset --soft HEAD~1     # keep staged
git reset HEAD~1            # keep but unstaged
```

### "I want to abandon all my local changes"

```bash
git fetch origin
git reset --hard origin/main
git clean -fdx              # also remove untracked + ignored
```

### "I rebased and want to undo"

```bash
git reflog
git reset --hard HEAD@{5}   # back before the rebase
```

### "Pushed wrong code, can't force push"

```bash
git revert <bad-commit>
git push
# Creates a NEW commit undoing the bad one
# Safe for protected branches
```

---

## GitHub-Specific Workflows

### Forking + Upstream

```bash
git clone git@github.com:youruser/forked-repo.git
cd forked-repo
git remote add upstream git@github.com:original/repo.git

# Sync with upstream
git fetch upstream
git checkout main
git merge upstream/main
git push
```

### GitHub Actions Trigger Patterns

```yaml
on:
  push:
    branches: [main]              # on push to main
  pull_request:
    branches: [main]              # on PR to main
  workflow_dispatch:              # manual trigger
  schedule:
    - cron: '0 2 * * *'           # nightly
  release:
    types: [created]              # on release
```

### Protecting Main Branch

```
Settings → Branches → Add rule for `main`:

✓ Require pull request before merging
✓ Require status checks (CI)
✓ Require code reviews (1-2 approvers)
✓ Dismiss stale reviews
✓ Require branches to be up-to-date
✗ Allow force pushes (DISABLE)
✗ Allow deletions (DISABLE)
```

---

## Senior Interview Questions

### Q1: Merge vs Rebase — when to use each?

Merge preserves the exact history with a merge commit. Rebase rewrites history to be linear. Use merge when merging long-running branches or to preserve audit trail. Use rebase to clean up your feature branch before opening a PR (so the final history is linear). Never rebase shared branches.

### Q2: What's wrong with `git push --force`?

It overwrites remote history, potentially losing teammates' work. Use `--force-with-lease` instead — it fails if someone else pushed since you last fetched. Better. Never force-push to `main`.

### Q3: How do you find which commit broke a feature?

`git bisect`. Tell git which commit is good and which is bad, it does binary search by checking out middle commits for you to test. Logs ~log₂(n) commits to test instead of n.

### Q4: How do you safely revert a deployed commit?

`git revert <commit>` creates a new commit that undoes the changes — safe for shared history. NEVER use `git reset --hard` on shared branches; it rewrites history and breaks others' clones.

### Q5: What's git stash and when is it useful?

Saves uncommitted changes temporarily. Use when you need to switch branches but aren't ready to commit. `git stash` saves; `git stash pop` restores. Better than committing junk.

### Q6: How do you resolve a merge conflict in a SQL migration file?

Two strategies:
1. **Sequence conflict**: rename your migration to come after the conflicting one, regenerate sequence
2. **Schema conflict**: drop one migration, create a unified migration

Senior pattern: avoid two PRs touching the same migration file — coordinate.

### Q7: What's `.git/objects` directory?

Git stores everything as objects (blobs, trees, commits, tags) hashed by SHA. The `.git/objects/` directory is the database. Branches are just pointers to commits, which point to trees, which point to blobs.

### Q8: How do you reduce repo size after committing large files?

`git filter-repo` (or BFG Repo-Cleaner) to rewrite history removing those files, then force-push and have everyone re-clone. Use Git LFS for large binaries going forward.

---

## Senior Mantras

```
1. Commit early, commit often. Push at end of day minimum.

2. Pull (rebase) often to avoid big conflicts.

3. Force push only with --force-with-lease. Never to main.

4. Small PRs > big PRs. 200 lines each, 2 days each.

5. Conventional commit messages. Future-you will thank present-you.

6. Branch protection on main. CI required. Reviews required.

7. .gitignore EARLY. Untracking is painful.

8. Pre-commit hooks save you from yourself.

9. git bisect is magic for "when did X break"

10. The reflog is your safety net. Almost nothing is truly lost.
```

---

## Resources

```
✓ Pro Git book (free): https://git-scm.com/book
✓ Oh Shit, Git!?!:  https://ohshitgit.com (recovery scenarios)
✓ Git Branching: https://learngitbranching.js.org (interactive)
✓ tig — git CLI with curses UI (install: brew install tig)
✓ delta — better diff output (install: brew install git-delta)
✓ gh — GitHub CLI (install: brew install gh)
```

---

## Related

- [01_linux_bash_essentials.md](01_linux_bash_essentials.md) — terminal usage
- [02_os_concepts.md](02_os_concepts.md) — file systems
- [03_networking_fundamentals.md](03_networking_fundamentals.md) — git over SSH/HTTPS
- [../Phase3_DevOps/03_github_actions_cicd.md](../Phase3_DevOps/03_github_actions_cicd.md) — CI/CD on top of git
