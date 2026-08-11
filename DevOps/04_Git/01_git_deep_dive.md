# Git Deep Dive — The Canonical Reference

**DevOps Track · Phase 4: Git**

## Quick Concepts

- **Repository** = a directory tracked by Git, containing the full history in `.git/`
- **Commit** = a snapshot of the repo at a point in time, with a unique SHA hash and a parent pointer
- **Branch** = a movable pointer to a commit — "main," "feature/x" are just labels on a commit graph
- **HEAD** = pointer to whatever commit/branch you currently have checked out
- **Working directory / staging area / repository** = the three states a file moves through (`git add` stages, `git commit` records)
- **Merge** = combines two branch histories, creating a new commit with two parents
- **Rebase** = replays your commits onto a new base, rewriting history (different commit hashes)
- **Remote** = a named reference to another copy of the repo (usually `origin`)
- **`git fetch`** = downloads new commits from a remote WITHOUT touching your current branch or working directory
- **`git pull`** = `git fetch` + merge (or rebase) in one step — the command that actually changes your current branch
- **Git hook** = a script Git runs automatically at a specific point (`pre-commit`, `pre-push`, etc.) — the mechanism behind "this commit was blocked by a failing lint check"
- **`git bisect`** = binary search through commit history to find exactly which commit introduced a bug
- **Signed commit** = a commit cryptographically signed (GPG or SSH key) so Git/GitHub can verify who actually authored it, not just whose name is in the author field

There is a lighter Git primer at `Backend_Developer/00_Year0-2_Junior/01_Foundations/04_git_workflows.md` — this file is the deeper, canonical reference for the whole repo; read that one for a quick refresher, this one when you need the full mental model.

---

## Git Internals — How Git Actually Stores Data

Understanding this section makes EVERY git command make sense instead of
feeling like magic.

```
Git stores four types of objects in .git/objects/:

  blob    = the raw content of ONE file (no filename, no path, no metadata)
  tree    = a directory listing — maps filenames to blob SHAs or other tree SHAs
  commit  = points to ONE root tree + has parent commit SHA(s) + author/date/message
  tag     = annotated tag object — points to a commit with its own message

A commit SHA is computed by SHA-1 hashing of:
  - the tree it points to
  - its parent commit SHA
  - author name + email + timestamp
  - committer name + email + timestamp
  - the commit message

This is why rebase CHANGES commit hashes even if the code diff is identical:
  The parent SHA changes → input to the hash function changes → new hash.
  C' and D' are brand-new commit objects, just with the same code diff as C and D.
```

```bash
# Explore the object database yourself:
git cat-file -t HEAD              # type of the HEAD object → "commit"
git cat-file -p HEAD              # contents: tree SHA + parent SHA + author + message
git cat-file -p HEAD^{tree}       # the tree the commit points to: filenames + blob SHAs
git cat-file -p <blob-sha>        # the raw file content
```

```
.git/ directory structure:
  .git/HEAD              → "ref: refs/heads/main" (what branch is checked out)
  .git/refs/heads/main   → the SHA of the latest commit on main
  .git/refs/heads/feature/login → SHA of latest commit on that branch
  .git/refs/remotes/origin/main → what we LAST FETCHED from origin/main
  .git/ORIG_HEAD         → the HEAD before the last merge/rebase/reset
                           (used by git reset ORIG_HEAD to undo a merge)
  .git/MERGE_HEAD        → during a merge conflict: the SHA of the incoming branch
  .git/index             → the staging area (binary file, not human-readable directly)
  .git/objects/          → all blobs, trees, commits, tags

Branch = a file containing ONE SHA. That's all. "main" = a text file
with a 40-char SHA in it. Moving a branch pointer = rewriting that file.
Delete a branch = delete that file. Branches are cheap because of this.
```

```
Why commit hashes are the foundation of Git's trustworthiness:
  Any change to any file, in any commit, anywhere in history, changes that
  commit's SHA. That change propagates through every subsequent commit's SHA
  (because each commit includes its parent's SHA in its hash input).
  Result: the current HEAD SHA is a cryptographic fingerprint of the ENTIRE
  history — you cannot silently modify history without changing the HEAD SHA.
  This is why GitOps (ArgoCD, Flux) pins deployments to commit SHAs, not
  branch names — a SHA is immutable evidence, a branch name is just a pointer.
```

---

## Why This Matters for Backend/DevOps Work

```
- Git is the source of truth GitOps and CI/CD are built on — a bad
  rebase or force-push can break a pipeline or teammates' history
- Cherry-picking a hotfix to a release branch under pressure
- Resolving merge conflicts correctly instead of guessing and
  accidentally dropping someone's changes
- reset vs revert — the difference between rewriting shared history
  (dangerous) and safely undoing a change (always safe)
- Reading `git log`/`git blame` to find who/why something changed,
  during an incident
```

---

## Initial Setup — Identity, Config Levels, Aliases

Before any of the commands below matter, Git needs to know who you are — every commit's author field comes from this, not from your OS login or GitHub session.

```bash
git config --global user.name "Ashish Chaurasiya"
git config --global user.email "you@example.com"
git config --global init.defaultBranch main       # new repos default to "main", not "master"
git config --global core.editor "vim"                # or "code --wait", "nano", etc.
```

```
Config levels, checked in this priority order (most specific wins):
  --local   (default if you omit a flag) → this ONE repo only,
             stored in .git/config
  --global                                  → this user, ALL repos,
             stored in ~/.gitconfig
  --system                                    → every user on the machine,
             rarely touched directly

git config --list --show-origin    # see every active setting AND
                                      # which file it came from — the
                                      # fastest way to debug "why is
                                      # this repo using the wrong email"
```

```bash
# Aliases — shorthand for commands you type constantly
git config --global alias.co checkout
git config --global alias.st status
git config --global alias.br branch
git config --global alias.last "log -1 HEAD --stat"
git config --global alias.unstage "reset HEAD --"

# Now:  git co main   ==   git checkout main
```

---

## Repository, Clone, Commit

```bash
git init                                 # create a new repo in the current directory
git clone https://github.com/org/repo.git  # copy an existing remote repo locally
git clone --depth 1 <url>                    # shallow clone — history-truncated, faster for CI

git status                                     # see staged/unstaged/untracked files
git add file.py                                  # stage a specific file
git add .                                          # stage everything in current dir (be deliberate)
git add -p                                           # interactively stage HUNKS, not whole files

git commit -m "add health check endpoint"              # commit staged changes
git commit -am "quick fix"                                # stage tracked-file changes + commit in one step
git commit --amend                                          # rewrite the LAST commit (message and/or content)
git commit --amend --no-edit                                  # amend content, keep the same message

git log                                                          # full history
git log --oneline                                                  # condensed, one line per commit
git log --oneline --graph --all                                      # visualize branch structure
git log -p -- file.py                                                   # show the actual diffs for a file's history
git log --author="alice"                                                  # filter by author
git show <sha>                                                              # full diff of a single commit

git rm file.py                # delete the file AND stage the deletion, in one step
git rm --cached file.py         # unstage/untrack it, but KEEP the file on disk
                                   # (the correct fix for "I added a file to git before adding it to .gitignore")
git mv old_name.py new_name.py     # rename/move + stage the rename, in one step —
                                     # equivalent to `mv` + `git rm` + `git add`, done atomically
```

---

## `git restore` and `git clean` — Modern "Undo Working Directory" Commands

`git restore` was introduced in Git 2.23 to separate two distinct jobs that `git checkout` used to conflate: "switch branches" and "restore file contents." You will see both in the wild — knowing both prevents confusion.

```bash
# Discard UNSTAGED changes to a file (restore from the last commit)
git restore file.py                    # modern
git checkout -- file.py                  # old equivalent (still works)

# Discard changes to ALL tracked files at once
git restore .

# Unstage a file (move it back from staging area to working directory)
git restore --staged file.py           # modern
git reset HEAD file.py                   # old equivalent

# Restore a file from a SPECIFIC commit (not just HEAD)
git restore --source=HEAD~3 file.py    # get file.py as it was 3 commits ago
git restore --source=abc1234 file.py   # from a specific commit SHA

# Restore a file that was deleted (recover it from the last commit)
git restore deleted_file.py
```

```
git restore vs git reset for unstaging:
  git restore --staged file.py    → unstages the file, keeps working dir content
  git reset HEAD file.py           → same effect, just older syntax
  Both are safe — neither deletes your work.

git restore (without --staged) vs git reset --hard:
  git restore file.py      → discards changes to ONE file
  git restore .             → discards changes to ALL files
  git reset --hard HEAD     → discards ALL changes (all files, staged and unstaged)
  All three discard LOCAL, UNCOMMITTED changes — they are NOT recoverable via reflog.
```

```bash
# git clean — remove UNTRACKED files (not in staging, not in history)
git clean -n           # dry run — SHOW what would be deleted, delete nothing
                          # ALWAYS run -n first before any clean
git clean -f           # actually delete untracked files
git clean -fd          # also delete untracked DIRECTORIES
git clean -fdx         # also delete files that .gitignore would normally ignore
                          # (build artifacts, __pycache__, node_modules)
git clean -fdxn        # dry run of the most aggressive clean
```

```
When to use git clean:
  After a build that scattered output files everywhere:
    git clean -fd       # remove output files (not in .gitignore)
  To reproduce a "fresh checkout" state (for debugging "works on my machine"):
    git clean -fdx      # removes EVERYTHING not tracked, including ignored files
    git restore .        # discard any modified tracked files
    # Now the repo looks exactly as if you cloned it fresh
  NEVER run git clean -fdx without -n first — you can lose hours of untracked work.
```

---

## Remotes, Fetch, and Pull — The Commands You Actually Run Daily

### `git diff` — Every Way You'll Actually Use It

```bash
git diff                          # unstaged changes vs the last commit (what `git add` would stage)
git diff --staged                   # staged changes vs the last commit (what `git commit` would commit)
git diff --cached                     # identical to --staged, just the older name for the same flag
git diff HEAD~1                         # working directory vs one commit back
git diff main..feature/login              # what feature/login has that main doesn't (two dots: direct diff)
git diff main...feature/login               # what feature/login has changed since it DIVERGED from main
                                               # (three dots: from the common ancestor, not main's current tip —
                                               # the one people actually want when reviewing a feature branch)
git diff --stat                                 # just a summary — files changed + line counts, no actual diff text
git diff -- path/to/file.py                       # scope the diff to one file/path
```

```
The two-dot vs three-dot distinction above is a genuine, common
confusion point: `main..feature` shows literally what's different
between the two tips right now (including commits main has that
feature doesn't); `main...feature` shows only what feature ADDED
since it branched off main — almost always the one you actually want
when asking "what will this PR actually introduce."
```

### `git remote` — Managing Where a Repo's Remotes Point

```bash
git remote -v                                    # list all remotes + their URLs (fetch AND push)
git remote add upstream https://github.com/original-org/repo.git   # common fork workflow —
                                                                        # "origin" = your fork,
                                                                        # "upstream" = the original repo
git remote rename origin old-origin                  # rename a remote
git remote remove upstream                             # remove a remote
git remote set-url origin git@github.com:org/repo.git   # switch a remote from HTTPS to SSH (or vice versa)
```

### `git fetch` vs `git pull` — The Distinction That Actually Matters

```bash
git fetch origin                # downloads new commits/branches from the remote,
                                   # updates your LOCAL remote-tracking branches
                                   # (origin/main) — but does NOT touch your
                                   # current branch or working directory AT ALL

git pull origin main               # git fetch + git merge (or rebase, if configured),
                                      # in ONE command — this is the step that
                                      # actually changes YOUR current branch
```

```
git fetch is always safe to run — it never modifies your working
directory or current branch, it only updates Git's KNOWLEDGE of what
the remote looks like. This is why "fetch first, THEN decide" is the
safer habit for anything you're unsure about:

git fetch origin
git log HEAD..origin/main --oneline    # see what's NEW on the remote,
                                          # before deciding to merge it in
git diff HEAD origin/main                  # see what would actually change
git merge origin/main                        # NOW pull it in, once you've
                                                # looked — equivalent to what
                                                # `git pull` would have done blindly

git pull --rebase origin main       # fetch + REBASE your local commits on
                                       # top, instead of merge — keeps
                                       # history linear, avoids an extra
                                       # merge commit on every pull
```

```
Why this distinction is a common interview/real-incident question:
`git pull` silently does a MERGE (creating a merge commit) by default
on many setups — a team expecting a clean linear history gets
surprised by merge commits appearing on every pull. Configuring
`git config --global pull.rebase true` makes `git pull` always rebase
instead of merge, matching the "rebase your own unpushed work" habit
from the Rebase section above — but know this is a deliberate config
choice, not Git's universal default.
```

---

## `.gitignore` and `.gitattributes` — Repo Hygiene From Day One

### `.gitignore` — What Never Gets Tracked

```
# .gitignore
__pycache__/
*.pyc
.env
.venv/
node_modules/
*.log
.DS_Store
dist/
build/
*.egg-info/
```

```
Patterns are matched anywhere in the tree unless anchored with a
leading /. A trailing / matches directories only. `!pattern` NEGATES
a previous ignore (re-includes something a broader pattern excluded)
— useful for "ignore all .env files EXCEPT .env.example":

.env*
!.env.example
```

```bash
git check-ignore -v path/to/file      # WHY is this file ignored — shows the exact
                                         # pattern + .gitignore line that matches it
git rm -r --cached .                    # untrack everything currently tracked
git add .                                 # re-add — anything matching .gitignore
                                             # now gets correctly excluded (fixes the
                                             # common "I added .gitignore too late,
                                             # the file's already tracked" problem)
```

```
A COMMITTED .env file (secrets already in history before .gitignore
was added) is NOT fixed by adding it to .gitignore afterward — the
file is still in every past commit. That requires actually rewriting
history (git filter-repo, or BFG Repo-Cleaner) AND rotating whatever
secret leaked, since the old commit is unrecoverable from a security
standpoint the moment it was ever pushed.
```

### `.gitattributes` — Per-File Handling Rules

```
# .gitattributes
*.sh text eol=lf              # force LF line endings for shell scripts,
                                 # even on a Windows checkout — a script
                                 # with CRLF endings fails with a cryptic
                                 # "bad interpreter" error on Linux/macOS
*.png binary                    # never try to diff/merge as text
*.psd filter=lfs diff=lfs merge=lfs -text   # route through Git LFS (below)
docs/* linguist-documentation      # tell GitHub's language stats to
                                      # ignore this path when computing
                                      # "this repo is 80% Python" on the repo page
```

```
The eol=lf line ending rule is the one that actually bites teams in
practice: a Windows contributor's editor silently converts a shell
script's line endings to CRLF, it works fine locally (Windows doesn't
care), then fails mysteriously the moment it runs in CI or on a
Linux/macOS teammate's machine. `.gitattributes` fixes this at the
repo level instead of relying on every contributor's editor config
being correct.
```

---

## Branch, Merge

```bash
git branch                          # list local branches
git branch -a                         # list local + remote-tracking branches
git branch feature/login                # create a branch (doesn't switch to it)
git checkout feature/login                # switch to it
git checkout -b feature/login               # create + switch in one step
git switch feature/login                      # modern equivalent of checkout for switching
git switch -c feature/login                     # modern equivalent of checkout -b

git branch -d feature/login          # delete a branch (safe — refuses if unmerged)
git branch -D feature/login            # force-delete (even if unmerged — be sure)

git merge feature/login                  # merge feature/login INTO the current branch
git merge --no-ff feature/login            # force a merge commit even if fast-forward is possible
                                              # (preserves the fact that a feature branch existed —
                                              #  common team policy for readable history)
```

### Fast-Forward vs Three-Way Merge

```
Fast-forward (no divergence — main hasn't moved since branching):
   main:     A---B
   feature:       \--C---D
   after merge: A---B---C---D   (main pointer just moves forward, no new commit)

Three-way merge (both branches have new commits):
   main:     A---B-------E
   feature:       \--C---D
   after merge: A---B-------E---M   (M = new merge commit, TWO parents: E and D)
```

---

## Detached HEAD — What It Is and How to Escape

This confuses nearly every developer the first time they see it.

```
HEAD normally points to a BRANCH NAME (indirect reference):
  HEAD → refs/heads/main → abc1234

Detached HEAD: HEAD points DIRECTLY to a commit SHA (no branch):
  HEAD → abc1234

You are "detached" — not on any named branch.
```

**How you get into detached HEAD state:**

```bash
git checkout v1.2.3          # checking out a tag → detached HEAD
git checkout abc1234           # checking out a specific commit SHA → detached HEAD
git checkout origin/main         # checking out a remote-tracking branch → detached HEAD
                                    # (remote-tracking branches are read-only pointers)
git bisect start                     # bisect moves HEAD to test commits → detached HEAD
```

**What detached HEAD looks like:**

```bash
git status
# HEAD detached at abc1234
# nothing to commit, working tree clean

git log --oneline | head -3
# abc1234 (HEAD) add payment validation
# def5678 fix null check in user service
# ...
```

**The danger: making commits while detached**

```
If you make commits while detached, they are NOT on any branch.
Once you checkout a different branch, those commits become ORPHANED
— they have no branch pointing to them and Git will garbage-collect
them eventually.

They're not immediately gone (reflog keeps them ~90 days) but they're
easy to lose if you don't know they're there.
```

**How to escape detached HEAD:**

```bash
# Option 1: You just wanted to look around, go back to your branch
git checkout main            # or git switch main
git checkout feature/login   # go back to wherever you were

# Option 2: You made commits while detached and want to KEEP them
git checkout -b recovery-branch    # create a NEW branch at current HEAD
                                      # now HEAD → recovery-branch → your commit

# Option 3: You made commits while detached but already switched away
git reflog                           # find the SHA of your detached commits
# abc1234 HEAD@{3}: commit: my important work
git checkout -b recovery-branch abc1234   # create branch at that SHA
```

---

## `git push` — All the Flags You Actually Need

```bash
git push origin main                  # push local main to origin/main
git push -u origin feature/login        # --set-upstream: link local branch to remote
                                           # after this, plain `git push` works (no origin + branch needed)
git push                                     # push current branch to its tracked remote
                                                # (only works after -u is set)

git push --tags                              # push all local tags to remote
git push origin v1.2.3                         # push a single tag
git push origin --delete feature/old-branch      # delete a branch on the remote
git push origin --delete v1.0.0                    # delete a tag on the remote

# Pushing when the remote has diverged (dangerous zone):
git push --force-with-lease          # SAFER force push — fails if remote has
                                        # commits you haven't fetched yet
                                        # (protects against clobbering a teammate's push)
git push --force                       # DANGEROUS — overwrites unconditionally
                                          # Never use on shared branches (main, develop)
```

```
The --force-with-lease vs --force distinction:

Scenario: you rebase your feature branch and need to force-push.
  git push --force          → even if Alice pushed to the same branch while
                              you were rebasing, her commits are silently gone.
  git push --force-with-lease → checks that origin/feature-branch matches what
                               you last fetched. If Alice pushed in the meantime,
                               this REFUSES the push → you fetch first, see her
                               commits, and incorporate them. Fails safe.

Rule: force-with-lease always, bare --force never on shared branches.
```

```bash
# See tracking configuration (which remote branch does this local branch push to?)
git branch -vv
# * feature/login  abc1234 [origin/feature/login] add login form
#   main           def5678 [origin/main] merge PR #42

# The [origin/feature/login] tells you: push goes there, pull comes from there

# Change the tracking target for a branch:
git branch --set-upstream-to=origin/main main
```

---

## Submodules — What They Are and Why They Cause Pain

```
A submodule is a Git repo EMBEDDED inside another Git repo.
The outer repo stores a pointer to a specific COMMIT SHA in the inner repo.
The inner repo's content is NOT copied — only the SHA pointer is stored.
```

```bash
git submodule add https://github.com/org/library.git lib/library
# Creates .gitmodules file + records the SHA pointer
# The library/ directory is a separate git repo inside this one

git submodule init       # initialize .gitmodules config after cloning
git submodule update     # checkout the correct commit in each submodule
git clone --recurse-submodules <url>   # clone + all submodules in one step
                                          # without this flag, submodules stay EMPTY after clone
```

```
Why submodules cause so much pain:

1. Cloning without --recurse-submodules → subdirectory is empty directory
   Fix: git submodule update --init --recursive

2. Submodule points to a commit that was force-pushed away:
   The outer repo's pointer is now a SHA that doesn't exist on the remote.
   Fix: the inner repo needs to preserve that commit (never force-push past
   a submodule reference).

3. "Detached HEAD" in every submodule:
   Submodules always check out in detached HEAD state (they're pinned to
   a SHA, not a branch). Making commits inside a submodule requires
   extra steps to ensure those commits get pushed.

4. Merge conflicts involving submodules:
   Conflicts show as a single line in the outer repo ("both sides modified
   the submodule pointer") — you must manually decide which SHA to use.

Alternatives to consider before adding submodules:
  - pip/npm/go.mod package managers — for library dependencies
  - git subtree — simpler integration, no .gitmodules file
  - Docker image references — for entire services
```

---

## Rebase

```bash
git checkout feature/login
git rebase main                    # replay feature/login's commits on top of main's latest tip

git rebase -i HEAD~3                 # interactive rebase — squash/reword/reorder last 3 commits
git rebase --continue                  # after resolving a conflict mid-rebase
git rebase --abort                       # bail out, restore pre-rebase state
```

```
Before rebase:
   main:     A---B---E
   feature:       \--C---D

After `git rebase main` (on feature branch):
   main:     A---B---E
   feature:            \--C'---D'   (NEW commits C', D' — different SHAs, same changes)

Merge vs Rebase:
   merge    — preserves true history, creates a merge commit, NON-destructive
   rebase   — LINEAR history, no merge commit, but REWRITES commit hashes

Golden rule: NEVER rebase commits that have been pushed and that
others may have already pulled/based work on. Rebasing shared history
means everyone else's local history now diverges from the rewritten
remote — a mess of "diverged branches" for the whole team.
Rebase freely on your OWN local, unpushed feature branch.
```

---

## Cherry-Pick

```bash
git cherry-pick <sha>              # apply ONE specific commit from anywhere onto current branch
git cherry-pick <sha1> <sha2>        # apply multiple specific commits
git cherry-pick --no-commit <sha>      # apply the changes but don't auto-commit (review first)
git cherry-pick --continue               # after resolving a conflict mid-cherry-pick
```

```
Classic use case: a critical bugfix landed on `main`, and you need it
on `release/v2.3` WITHOUT merging all of main's other unreleased work.

git checkout release/v2.3
git cherry-pick abc1234        # pulls just that one fix commit onto the release branch
```

---

## Stash

```bash
git stash                       # shelve uncommitted changes, restore clean working dir
git stash -u                      # also stash untracked files
git stash list                      # see all stashed entries
git stash pop                         # reapply the most recent stash AND remove it from the list
git stash apply                         # reapply without removing from the list (can apply again elsewhere)
git stash apply stash@{2}                 # apply a specific (non-latest) stash
git stash drop stash@{0}                    # delete a specific stash entry without applying
git stash show -p stash@{0}                   # preview what's in a stash before applying
```

```
Common flow: mid-feature, need to urgently switch branches to fix a
prod bug, but current work isn't commit-ready yet:
   git stash
   git checkout main
   ... fix the bug, commit, push ...
   git checkout feature/login
   git stash pop
```

---

## Reset — soft, mixed, hard (this trips everyone up)

```bash
git reset --soft <commit>     # move HEAD + branch pointer only. Changes stay STAGED.
git reset --mixed <commit>      # (DEFAULT if you omit the flag) move HEAD + unstage changes.
                                   # Changes stay in your WORKING DIRECTORY, just unstaged.
git reset --hard <commit>         # move HEAD + wipe changes from staging AND working directory.
                                     # UNCOMMITTED work matching the reset range is GONE.
```

```
Think of it as three concentric circles being rewound:

              WORKING DIRECTORY
           ┌───────────────────┐
           │   STAGING AREA    │
           │  ┌─────────────┐  │
           │  │  COMMITTED  │  │
           │  │  (HEAD)     │  │
           │  └─────────────┘  │
           └───────────────────┘

--soft   → only rewinds the innermost circle (HEAD/commit pointer).
           Staging + working dir untouched — everything from the
           "undone" commits reappears as STAGED changes.

--mixed  → rewinds HEAD AND staging. Working dir untouched — changes
           reappear as UNSTAGED (modified but not staged) changes.
           This is the safe middle ground and the default.

--hard   → rewinds HEAD, staging, AND working directory. Nothing
           reappears anywhere — it's actually gone (unless you can
           recover it via `git reflog`, which tracks HEAD movements
           for ~90 days by default).
```

```bash
# Practical examples
git reset --soft HEAD~1     # "undo my last commit but keep everything staged, ready to re-commit differently"
git reset HEAD~1              # "undo my last commit, keep the changes but unstaged"
git reset --hard HEAD~1         # "completely discard my last commit and its changes" (DANGEROUS)
git reset --hard origin/main      # "throw away all local commits/changes, match remote exactly" (DANGEROUS)

# Un-stage a file without losing changes (mixed reset on a single file)
git reset file.py

# Recover from an accidental --hard
git reflog                       # find the SHA you were at before the reset
git reset --hard <sha-from-reflog>
```

### Senior Tip: reset --hard on a Pushed Branch

```
Never run `git reset --hard` + `git push --force` on a branch others
have pulled from, without coordinating. It rewrites history that
already exists on the remote — anyone who pulled the old commits now
has a diverged branch and will hit confusing conflicts or silently
keep working on now-orphaned commits.

If you MUST fix pushed history, use `git push --force-with-lease`
instead of a bare `--force` — it refuses to overwrite the remote if
someone else pushed in the meantime (fails safe instead of clobbering).
```

---

## Revert (vs Reset)

```bash
git revert <sha>                # create a NEW commit that undoes the changes from <sha>
git revert HEAD                   # undo the most recent commit, safely, with a new commit
git revert --no-commit <sha1> <sha2>  # revert multiple commits, stage them, commit once yourself
```

```
reset vs revert — the single most important distinction:

reset   REWRITES history — moves the branch pointer backward, the
        "undone" commits are no longer in the branch's ancestry
        (dangerous on shared/pushed branches).

revert  ADDS to history — creates a brand new commit whose diff is
        the inverse of the target commit. The original commit still
        exists in history; you're not erasing anything.

RULE OF THUMB:
  - Undoing LOCAL, unpushed work → reset is fine (nothing to break)
  - Undoing something already PUSHED / on a shared branch → revert
    (safe for collaborators, doesn't rewrite shared history)
```

---

## Tags

```bash
git tag v1.2.3                       # lightweight tag on current commit
git tag -a v1.2.3 -m "Release 1.2.3"   # annotated tag — has its own metadata (author, date, message) — preferred for releases
git tag                                  # list all tags
git tag -d v1.2.3                          # delete a local tag
git push origin v1.2.3                       # push a single tag
git push origin --tags                         # push all tags
git push origin --delete v1.2.3                  # delete a tag on the remote
git checkout v1.2.3                                # check out the exact state at that tag (detached HEAD)
```

```
Use annotated tags (-a) for anything release-related — they store who
tagged it, when, and why, and are what most CI/CD "trigger on tag
push" pipelines expect (e.g. tag v1.2.3 → deploy pipeline fires).
```

---

## Commit Signing — Verifying WHO Actually Authored a Commit

Git's author field (`git commit --author="alice <alice@example.com>"`) is just TEXT — anyone can set it to anything, with no verification at all. Signing proves authorship cryptographically, and is the Git-level piece of the same supply-chain-trust chain as the SBOM/provenance concepts in `14_Security`.

```bash
# GPG-based signing (the traditional approach)
gpg --full-generate-key                          # create a GPG keypair, if you don't have one
gpg --list-secret-keys --keyid-format=long          # find your key ID
git config --global user.signingkey <KEY_ID>
git config --global commit.gpgsign true               # sign EVERY commit automatically

git commit -S -m "add health check endpoint"             # sign one commit explicitly
git tag -s v1.2.3 -m "Release 1.2.3"                        # signed (not just annotated) tag

# SSH-based signing (newer, simpler if you already have an SSH key)
git config --global gpg.format ssh
git config --global user.signingkey ~/.ssh/id_ed25519.pub
git config --global commit.gpgsign true
```

```bash
git log --show-signature       # verify signatures on past commits
git verify-commit <sha>          # verify a single commit's signature
```

```
GitHub/GitLab show a "Verified" badge on signed commits whose public
key is registered to that account — an UNVERIFIED commit claiming to
be from you is a real, if uncommon, social-engineering vector (anyone
can `git commit --author="you <you@email>"` against a repo they have
write access to, and it looks exactly like your commit in `git log`
unless signing is enforced).

Branch protection rules can REQUIRE signed commits before merge —
common in security-conscious orgs and increasingly expected on open-
source projects accepting outside contributions.
```

**Why this belongs next to the SBOM/SLSA material in Security:** SBOM answers "what's inside this artifact," provenance/SLSA answers "how was it built," and commit signing answers "who actually wrote the source that went into it" — three different links in the same supply-chain-trust chain, and commit signing is the one that lives entirely in Git itself.

---

## Git Flow — Branching Model

```
main ────────────────────────────●──────────────●───────  (always production-ready, tagged releases)
                                  │              │
release/1.2 ──────────●──────────┘              │          (stabilize before release, only bugfixes)
                       │                         │
develop ───●───●───●───●───●───●───●───●─────────┘         (integration branch, always deployable-ish)
            \       \       \       /
feature/a    ●───●───●        \    /
feature/b            ●───●─────●──/

hotfix/critical-bug ────●   (branches off main, merges to BOTH main and develop)

Branch roles:
  main        production, every commit is a release, tag here
  develop     integration branch, features merge here first
  feature/*   one branch per feature, branches FROM develop, merges BACK to develop
  release/*   cut from develop when preparing a release, only bugfixes allowed, merges to main + develop
  hotfix/*    branches FROM main for an urgent prod fix, merges to BOTH main and develop
```

```
Git Flow is heavyweight — many modern teams use a simpler variant:
   Trunk-based development: main + short-lived feature branches,
   merged via PR, deployed continuously. Less ceremony, favored when
   you have strong CI/CD and feature flags to de-risk incomplete work.

Know Git Flow for interviews and for legacy/regulated codebases that
still use it; expect trunk-based in most modern fast-moving teams.
```

---

## Pull Requests (PRs)

```
A PR is a request to merge one branch into another, with a review
step attached — not a native `git` command, it's a GitHub/GitLab/
Bitbucket platform feature built ON TOP of git branches.

Typical flow:
  1. git checkout -b feature/add-caching
  2. ... work, commit ...
  3. git push -u origin feature/add-caching
  4. Open a PR on GitHub: feature/add-caching → main
  5. CI runs (tests, lint), reviewers comment/approve
  6. Merge (regular merge commit, squash, or rebase-merge — team policy)
  7. Delete the feature branch
```

```bash
gh pr create --title "Add caching layer" --body "..."   # GitHub CLI
gh pr view --web                                            # open in browser
gh pr merge --squash                                          # merge via CLI
```

```
Merge strategies at PR-merge time:
  Merge commit    — preserves full branch history, adds a merge commit
  Squash and merge — collapses all feature commits into ONE commit on
                      main — clean history, loses granular commit detail
  Rebase and merge — replays feature commits onto main individually,
                      no merge commit, linear history

Squash is the most common default for feature branches with messy
"wip", "fix typo" commit noise — keeps main's history clean.
```

---

## Git Hooks — Automating Checks at Commit/Push Time

A hook is a script Git runs automatically at a specific point in the commit/push lifecycle — the mechanism behind "my commit got blocked because linting failed" before code ever reaches CI.

```bash
ls .git/hooks/          # every hook Git supports has a *.sample file here by default —
                           # rename/remove the .sample suffix and make it executable to activate
```

```bash
#!/usr/bin/env bash
# .git/hooks/pre-commit — runs BEFORE a commit is created; non-zero exit BLOCKS the commit
set -euo pipefail
ruff check . || { echo "lint failed — commit blocked"; exit 1; }
```

```bash
#!/usr/bin/env bash
# .git/hooks/pre-push — runs BEFORE a push leaves your machine
set -euo pipefail
pytest -x || { echo "tests failed — push blocked"; exit 1; }
```

```
Common hook points:
  pre-commit    → before a commit is created (lint, format-check, secret-scanning)
  commit-msg    → validate the commit MESSAGE itself (e.g. enforce
                    Conventional Commits format: "feat: add caching")
  pre-push      → before commits leave your machine (run tests, block
                    a push directly to main)
  post-checkout → after switching branches (e.g. auto-install deps if
                    package.json changed between branches)
```

**The real-world problem with raw `.git/hooks/`:** it lives in `.git/`, which is NOT tracked by Git itself — hooks placed there directly don't get shared with the team automatically. This is exactly why the **`pre-commit` framework** (a popular tool, confusingly named the same as the hook it usually configures) exists:

```yaml
# .pre-commit-config.yaml — THIS file IS committed and shared with the team
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.4.4
    hooks:
      - id: ruff
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.6.0
    hooks:
      - id: check-added-large-files
      - id: detect-private-key
```

```bash
pip install pre-commit
pre-commit install          # wires this config into .git/hooks/pre-commit for
                               # everyone who runs this once after cloning
pre-commit run --all-files    # run every configured hook against the whole repo,
                                 # not just staged files — useful for a first-time check
```

```
This is the standard way a team shares hook config instead of every
developer manually copying scripts into their own local .git/hooks/ —
the tool INSTALLS the plumbing, the YAML file is what's actually
version-controlled and reviewed like any other config.

Honest caveat, and exactly why Phase 14's Trivy/tfsec scans ALSO run
in CI, not just as a local hook: hooks are LOCAL and skippable
(`git commit --no-verify` bypasses them entirely) — they're a fast
feedback loop for the developer, never a substitute for the same
checks running unskippably in CI before merge.
```

---

## Conflict Resolution — Walked Through

```bash
git merge feature/pricing
# Auto-merging pricing.py
# CONFLICT (content): Merge conflict in pricing.py
# Automatic merge failed; fix conflicts and then commit the result.
```

```python
# pricing.py — what you'll see inside the file
def calculate_discount(price):
<<<<<<< HEAD
    return price * 0.9   # main's version: 10% discount
=======
    return price * 0.85  # feature/pricing's version: 15% discount
>>>>>>> feature/pricing
```

```
<<<<<<< HEAD           everything down to ======= is YOUR current branch's version
=======                 the divider
>>>>>>> feature/pricing everything from ======= up to here is the INCOMING branch's version
```

### Step-by-step resolution

```bash
# 1. Open the file, decide the correct outcome (talk to the other
#    author if unclear — don't guess on business logic)

# 2. Edit the file to the FINAL desired state, removing ALL conflict markers
def calculate_discount(price):
    return price * 0.85   # decided: use the feature branch's new discount rate

# 3. Stage the resolved file
git add pricing.py

# 4. Check for any other conflicted files
git status

# 5. Complete the merge
git commit                  # opens editor with a pre-filled merge commit message
# or, if this conflict arose during a rebase instead of a merge:
git rebase --continue
```

### Useful tools mid-conflict

```bash
git diff                      # see the conflict markers in context
git checkout --ours file.py      # discard incoming changes, keep YOUR version entirely
git checkout --theirs file.py      # discard your changes, keep the INCOMING version entirely
git merge --abort                    # bail out of the merge entirely, back to pre-merge state
git mergetool                          # launch a configured 3-way merge GUI (vimdiff, meld, VS Code, etc.)
```

---

## Investigating History — `bisect`, `blame`, and Pickaxe Search

The Senior Tip elsewhere in this file says `git blame`/`git log -p` are how you debug an incident by understanding intent — here's the actual toolkit, beyond a plain `git log`.

### `git bisect` — Binary Search for the Commit That Broke Something

```bash
git bisect start
git bisect bad                    # current commit (HEAD) is confirmed broken
git bisect good v1.4.0               # this older tag/commit is confirmed WORKING

# Git checks out a commit roughly halfway between good and bad —
# test it, then tell git the result:
git bisect good     # this commit is fine, the bug is somewhere LATER
git bisect bad        # this commit is broken, the bug is somewhere EARLIER

# ... repeat — each answer halves the remaining search space ...
# Git eventually reports: "abc1234 is the first bad commit"

git bisect reset      # return to your original HEAD when done
```

```bash
# Automate the whole thing with a script that exits 0 (good) or non-zero (bad)
git bisect start HEAD v1.4.0
git bisect run pytest tests/test_regression.py
# git checks out and tests EVERY candidate commit automatically,
# no manual good/bad typing — reports the culprit directly
```

```
Why this matters more than "just read the diffs": in a real incident,
you often don't know WHICH of 40-200 commits since the last known-good
release introduced a regression. Manually reading each is slow;
bisect finds it in log2(N) steps — 200 commits takes at most ~8 tests,
not 200. `git bisect run` with an automated test is the fast path;
manual good/bad is the fallback when the bug needs a human to judge
(a visual glitch, a subtle behavior change pytest doesn't cover).
```

### Pickaxe Search — "When Was This Line Added or Removed?"

```bash
# -S searches for commits that changed the NUMBER of occurrences of a
# string (added it where it wasn't, or removed the last occurrence)
git log -S"MAX_RETRIES" --oneline

# -G searches using a REGEX against the actual diff content — broader
# than -S, matches any commit whose diff contains a line matching the pattern
git log -G"def calculate_.*discount" --oneline

# Combine with -p to see the actual diff for each matching commit
git log -S"MAX_RETRIES" -p -- config.py
```

```
-S vs -G: -S is precise ("show me commits that changed how many times
this EXACT string appears") — it won't match a commit that just moved
the string to a different line. -G is a regex search over diff
content — broader net, more false positives, but catches partial/
pattern matches -S would miss. Start with -S for "when did this
specific constant/function name get added," reach for -G when you
need a pattern rather than a literal string.
```

### `blame` Refinements

```bash
git blame -w file.py            # ignore WHITESPACE-only changes when
                                   # attributing lines — without this, a
                                   # commit that only reformatted/reindented
                                   # a file falsely "owns" every line in it
git blame -C file.py               # detect lines MOVED or COPIED from
                                     # elsewhere in the same commit, attribute
                                     # them to their ORIGINAL commit instead
git blame -L 50,80 file.py            # blame only a line range, not the whole file
```

```
Plain `git blame` on a file that was recently auto-formatted (black,
prettier, gofmt) is nearly useless — every line shows the formatting
commit as its "author," hiding the actual meaningful history. `-w`
and `-C` are the fix, and knowing to reach for them the moment blame
output looks suspiciously uniform is a real, checkable signal of
having actually used blame to debug something in anger.
```

---

## A Few More Tools Worth Knowing

```
git worktree add ../hotfix-wt release/2.3
```
`git worktree` checks out a SECOND branch into a separate directory, sharing the same `.git` history — lets you work on an urgent hotfix on `release/2.3` in one terminal/editor window while your feature branch stays checked out, untouched, in the original directory. Solves the same problem `git stash` does (need to switch context without losing in-progress work), without the stash-apply round-trip.

```
Git LFS (Large File Storage) replaces large binary files (images,
video, datasets, model weights) with small TEXT POINTERS inside the
actual Git history, storing the real file content in separate LFS
storage — because Git's design (full history, every version, on every
clone) makes it badly suited to large binaries that change often;
repo size balloons and clones get slow. `git lfs track "*.psd"` adds
the pattern to `.gitattributes` (see above) and is the standard fix
when a repo starts accumulating large media/data files directly.
```

---

## Senior Tip

```
1. --soft/--mixed/--hard reset: when in doubt, use --mixed (the
   default) — it's the safe middle ground that never deletes work.
2. `push --force-with-lease`, never bare `--force`, on any branch
   others might have touched.
3. `git reflog` is your safety net — HEAD movements (including from
   resets and rebases) are kept ~90 days by default, so "I force-pushed
   over my work" is USUALLY recoverable if you act fast.
4. Squash-merge feature branches with messy commit history into main;
   keep meaningful, atomic commits on long-lived/shared branches.
5. Rebase your OWN unpushed local branch freely to keep history clean
   before opening a PR; never rebase something already shared.
6. Write commit messages that answer WHY, not just what — `git blame`
   and `git log -p` are how future-you (or a teammate) debugs an
   incident by understanding intent, not just the diff.
```

## Interview Angle

**Q: `git reset --soft` vs `--mixed` vs `--hard` — explain clearly.**
All three move the HEAD/branch pointer to a target commit. `--soft` leaves the difference STAGED (as if you just `git add`-ed it). `--mixed` (the default) leaves it UNSTAGED but present in the working directory. `--hard` discards it entirely from both staging and the working directory — the changes are gone unless recovered via `git reflog`.

**Q: `git reset` vs `git revert` — when do you use each?**
`reset` rewrites history by moving the branch pointer — safe only on local/unpushed commits. `revert` creates a new commit that undoes a previous one, leaving history intact — the only safe option for undoing something already pushed/shared, since it doesn't require anyone to rewrite their local history.

**Q: What's actually happening during a rebase, and why does it create new commit hashes?**
Rebase takes your branch's commits, temporarily sets them aside, moves your branch pointer to the new base commit, then replays each of your commits one by one on top of it. Because a commit's hash is derived from its content AND its parent, changing the parent (the new base) changes the hash — even if the code diff is identical, it's technically a brand-new commit object.

**Q: Why is `git cherry-pick` useful when you already have `merge`?**
Merge brings in an entire branch's history. Cherry-pick lets you take exactly ONE commit's changes without pulling in everything else on that branch — the standard tool for backporting a single hotfix to a release branch without merging unreleased work.

**Q: Walk through resolving a merge conflict from the raw conflict markers to a completed merge.**
Identify `<<<<<<< HEAD` (your branch) through `=======` (divider) to `>>>>>>> branch-name` (incoming branch); decide the correct final code (not just picking one side blindly — often it's a combination); remove all marker lines; `git add` the resolved file; verify no other files are still conflicted with `git status`; then `git commit` (or `git rebase --continue` if conflict arose during a rebase).

**Q: What's the actual difference between `git fetch` and `git pull`, and why does it matter which one you reach for?**
`git fetch` only downloads new commits/branches from the remote and updates your local remote-tracking branches (`origin/main`) — it never touches your current branch or working directory, so it's always safe to run. `git pull` is `git fetch` + an automatic merge (or rebase, if configured) — it's the step that actually changes your current branch, and can surprise you with an unexpected merge commit or conflict if you weren't expecting new upstream changes. "Fetch first, inspect with `git log HEAD..origin/main`, then merge/rebase deliberately" is the safer habit when you're not sure what's changed upstream.

**Q: Reviewing a PR, `git diff main..feature/login` and `git diff main...feature/login` show different results — why, and which one do you actually want?**
Two dots shows the literal difference between the two branch tips right now, which can include commits `main` has that `feature/login` doesn't (if `main` moved forward after the branch was created). Three dots shows only what `feature/login` added since it diverged from `main` — i.e., from their common ancestor — which is almost always the one you actually want when reviewing "what will this PR introduce."

**Q: A regression shipped somewhere in the last 60 commits, but you don't know which one. How do you find it faster than reading every diff?**
`git bisect` — mark the current commit `bad` and a known-working older commit/tag `good`, and Git checks out the midpoint for you to test; each good/bad answer halves the remaining range, finding the culprit in about log2(60) ≈ 6 steps instead of up to 60. If there's an automated test that reproduces the bug, `git bisect run <test-command>` does the entire search unattended.

**Q: `git blame` on a file shows one person "owning" almost every line, even though you know several people have worked on it. What's likely wrong, and how do you fix it?**
The file was probably auto-formatted or reindented at some point (black, prettier, a linter's `--fix`), and that reformatting commit now falsely "blames" every line it touched, hiding the real history. `git blame -w` ignores whitespace-only changes when attributing lines, and `git blame -C` detects code moved or copied within the same commit and attributes it back to its original commit — both fix the false-ownership problem.

**Q: What actually prevents someone from committing code under your name in a repo they have write access to?**
Nothing, by default — the author field in a commit is unverified plain text. Commit signing (GPG or SSH-based, `git config commit.gpgsign true`) cryptographically ties a commit to a specific key, and platforms like GitHub show a "Verified" badge only when the signature matches a key registered to that account — an unsigned commit claiming your name and email is otherwise indistinguishable from a real one in `git log`.

**Q: Your team keeps merging code with linting failures and broken tests straight into main — how would you prevent that at the Git level, not just in CI?**
A `pre-commit` hook (or the `pre-commit` framework, sharing `.pre-commit-config.yaml` so the whole team gets the same checks after running `pre-commit install`) blocks a commit locally if lint fails, and a `pre-push` hook can block a push if tests fail — fast local feedback before code even reaches CI. The important caveat: hooks are local and skippable (`--no-verify`), so the SAME checks still need to run unskippably in CI as the actual enforcement layer; hooks are a fast feedback loop, not a substitute for that.

---

## Related

- [`Backend_Developer/00_Year0-2_Junior/01_Foundations/04_git_workflows.md`](../../Backend_Developer/00_Year0-2_Junior/01_Foundations/04_git_workflows.md) — the lighter/quicker primer version of this file
- [`../14_Security/03_iam_vuln_scanning.md`](../14_Security/03_iam_vuln_scanning.md) — SBOM and SLSA provenance, the other two links in the same supply-chain-trust chain commit signing belongs to
- [`../10_CICD/`](../10_CICD/) — where the same lint/test checks a pre-commit hook runs locally get enforced unskippably in CI
- [`practical/01_git_lab.md`](practical/01_git_lab.md) — hands-on labs for the workflows above
