# Linux & Bash — Recap Q&A (Interview Deep Dive)

> Self-test recap of [01_linux_bash_essentials.md](01_linux_bash_essentials.md). Format: question → correct answer → why it matters → common mistake.

---

## Q1. `chmod 754 file.sh` — permissions kya honge?

**Answer:**
```
7 → Owner  → rwx  (read, write, execute)
5 → Group  → r-x  (read, execute — no write)
4 → Others → r--  (read only)
```
Symbolic form: `rwxr-xr--`

**Why it matters:** Each digit is a bitmask sum — `4=read, 2=write, 1=execute`. `7=4+2+1`, `5=4+1`, `4=4`. Memorize the bitmask, don't memorize the combinations — it generalizes to any number (e.g. `644` = `rw-r--r--`, the default for new files).

---

## Q2. `kill -9` vs `kill -15` — difference and which to use first?

**Answer:**
| Signal | Name | Behavior |
|---|---|---|
| `kill -15` | `SIGTERM` | **Graceful** — process can catch it, clean up (close files, flush buffers, release locks), then exit. Default signal `kill` sends if no flag given. |
| `kill -9` | `SIGKILL` | **Forceful/immediate** — OS kills the process instantly. Cannot be caught, ignored, or blocked. No cleanup happens. |

**Why it matters:** In production, **always try `-15` first**, wait a few seconds, escalate to `-9` only if the process is hung/unresponsive. Killing with `-9` first risks corrupted files, orphaned DB locks, unflushed writes.

**Common mistake:** Assuming `-9` is "the graceful one" because it's the most commonly typed (`kill -9` is muscle memory for many devs) — it's actually the *most violent* option.

---

## Q3. `command > file.txt 2>&1` vs `command 2>&1 > file.txt` — output difference?

**Answer:** Redirections apply **left to right**. `2>&1` means "point fd 2 (stderr) to wherever fd 1 (stdout) **currently** points" — it's a snapshot, not a live link.

```bash
command > file.txt 2>&1
# Step 1: stdout(1) → file.txt
# Step 2: stderr(2) → wherever stdout(1) points NOW = file.txt
# Result: BOTH stdout and stderr go to file.txt ✅

command 2>&1 > file.txt
# Step 1: stderr(2) → wherever stdout(1) points NOW = terminal (not yet redirected)
# Step 2: stdout(1) → file.txt
# Result: stderr stays on terminal, only stdout goes to file.txt ⚠️
```

**Why it matters:** This is one of the most common bash scripting gotchas — "I redirected everything to a log file but errors still print to my terminal" is almost always this ordering bug.

---

## Q4. `ps aux | grep python | awk '{print $2}' | xargs kill` — explain the pipe chain

**Answer:**
1. `ps aux` — lists all running processes (all users, full detail)
2. `grep python` — filters lines containing "python"
3. `awk '{print $2}'` — extracts column 2 (the PID field in `ps aux` output)
4. `xargs kill` — takes those PIDs as arguments and runs `kill` on each

**Gotcha:** `grep python` **matches itself** — the `grep python` process line also contains the string "python", so it tries to kill the grep process too (harmless here since it's already exiting, but bad practice).

**Better version:**
```bash
pgrep python | xargs kill
# or
ps aux | grep '[p]ython' | awk '{print $2}' | xargs kill   # bracket trick avoids self-match
```

---

## Q5. SSH config shortcut — `ssh myserver` should connect to `ubuntu@10.0.0.5 -p 2222 -i ~/.ssh/prod.pem`

**Answer:** In `~/.ssh/config`:
```
Host myserver
    HostName 10.0.0.5
    User ubuntu
    Port 2222
    IdentityFile ~/.ssh/prod.pem
```
Then just `ssh myserver` works — no need to remember the full command every time.

**Why it matters:** Real day-1 productivity tool. Also useful for jump-host / bastion setups via `ProxyJump`.

---

## Round 1 Scorecard (from live recap session)

| Q | Topic | Result |
|---|---|---|
| 1 | chmod numeric/symbolic | ✅ Correct |
| 2 | kill -9 vs -15 | ❌ Initially reversed — corrected above |
| 3 | redirection order | ❌ Gap — corrected above |
| 4 | ps\|grep\|awk\|xargs pipe | ✅ Correct components, missed self-match gotcha |
| 5 | SSH config | ❌ Gap — corrected above |

**Action item:** Re-drill signal handling (`kill -9`/`-15`) and stdout/stderr redirection order — these come up constantly in both interviews and real debugging.
