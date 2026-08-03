# Automation, Cron & Production Scripting Patterns

**DevOps Track · Phase 2: Bash Scripting**

## Quick Concepts

- **cron** = Linux's built-in job scheduler, driven by a per-user or system-wide crontab
- **crontab** = the file/table defining when a job runs (`crontab -e` to edit yours)
- **Idempotent** = running a script twice has the same effect as running it once (safe to retry)
- **trap** = intercept a signal/exit in a script to run cleanup code
- **Log rotation** = keeping logs from growing unbounded (via `logrotate` or your own script logic)
- **systemd timer** = a `.timer` unit that triggers a `.service` unit on a schedule — the modern, systemd-native alternative to a crontab entry
- **Signal** = an OS-level notification sent to a process (SIGTERM = "please stop," SIGINT = Ctrl+C, SIGKILL = unconditional, uncatchable kill)
- **`xargs`** = builds and runs commands from piped input, the standard way to parallelize or batch a shell pipeline

---

## Why This Matters for Backend/DevOps Work

```
- Nightly DB backups, log cleanup, report generation — all cron-driven
- Parsing production logs during an incident to find the root cause fast
- Writing backup scripts that are safe to re-run without doubling data
- Every "scheduled task" ticket you'll get as a backend/DevOps engineer
  eventually comes down to: a bash script + cron (or a systemd timer)
```

---

## Cron

### Crontab Syntax

```
┌───────────── minute (0-59)
│ ┌───────────── hour (0-23)
│ │ ┌───────────── day of month (1-31)
│ │ │ ┌───────────── month (1-12)
│ │ │ │ ┌───────────── day of week (0-6, Sun=0, or names: SUN-SAT)
│ │ │ │ │
* * * * *  command-to-run
```

### Cheat Sheet

| Schedule | Cron Expression | Meaning |
|---|---|---|
| Every minute | `* * * * *` | runs 1,440 times/day — rare, mostly for testing |
| Every 5 minutes | `*/5 * * * *` | health checks, polling |
| Every hour | `0 * * * *` | at minute 0 of every hour |
| Every day at midnight | `0 0 * * *` | classic nightly job |
| Every day at 2:30 AM | `30 2 * * *` | low-traffic-window backup |
| Every Sunday at 3 AM | `0 3 * * 0` | weekly maintenance |
| First of every month | `0 0 1 * *` | monthly billing/reports |
| Every weekday at 9 AM | `0 9 * * 1-5` | business-hours job |
| Every 15 minutes | `*/15 * * * *` | frequent polling |
| Twice a day (6am, 6pm) | `0 6,18 * * *` | list of specific hours |

### Managing Crontab

```bash
crontab -e                    # edit your user's crontab (opens $EDITOR)
crontab -l                      # list current crontab
crontab -r                        # REMOVE entire crontab (careful — no confirmation)
crontab -u deploy -l                # list another user's crontab (needs root)

sudo crontab -e -u deploy             # edit another user's crontab as root

# system-wide cron locations (no user field needed in personal crontab, but these DO need one)
/etc/crontab
/etc/cron.d/*
/etc/cron.daily/  /etc/cron.hourly/  /etc/cron.weekly/  /etc/cron.monthly/
```

### A Real Crontab Entry

```
# backup the database nightly at 2:30 AM, log output, alert on failure
30 2 * * * /opt/scripts/backup.sh >> /var/log/backup.log 2>&1 || echo "backup failed" | mail -s "ALERT" ops@example.com
```

```
Gotchas:
  - cron runs with a MINIMAL environment — no PATH, no .bashrc sourced.
    Always use absolute paths in cron scripts, or set PATH explicitly
    at the top of the crontab.
  - cron's "%" character is special (means newline) — escape it as \%
    if your command needs a literal percent (e.g. date +\%Y).
  - Always redirect output (>> log 2>&1) — cron emails output to the
    crontab owner by default, which is easy to miss/ignore.
```

---

## systemd Timers — The Modern Cron Alternative

Most current Linux distros ship systemd, and a `.timer` unit paired with a `.service` unit is increasingly the preferred way to schedule a job — cron still works fine and is far from deprecated, but systemd timers fix several of cron's rough edges natively.

```ini
# /etc/systemd/system/backup.service
[Unit]
Description=Nightly database backup

[Service]
Type=oneshot
ExecStart=/opt/scripts/backup.sh
User=deploy
```

```ini
# /etc/systemd/system/backup.timer
[Unit]
Description=Run backup.service nightly at 2:30 AM

[Timer]
OnCalendar=*-*-* 02:30:00
Persistent=true
# Persistent=true → if the machine was OFF at 2:30 AM (maintenance,
# reboot), the job runs ONCE as soon as the system is back up, instead
# of silently skipping that day entirely — cron has no equivalent

[Install]
WantedBy=timers.target
```

```bash
sudo systemctl enable --now backup.timer   # enable + start immediately
systemctl list-timers                        # see all timers + next/last run time
journalctl -u backup.service                   # FULL structured logs for every run —
                                                  # no more `>> log.txt 2>&1` by hand
systemctl status backup.service                  # exit code + last-run result at a glance
```

**Why teams reach for this over cron:**

```
cron                              systemd timer
──────────────────────────────    ──────────────────────────────────────
Missed run (machine was off)      Persistent=true catches up automatically
  → silently skipped forever
Logs                              journalctl gives structured, queryable
  → wherever you redirected them    logs for every run, centrally, no
    (or a cron-mail nobody reads)   per-script logging convention needed
Dependencies                      Can require another service/target be
  → none — cron has no concept      up first (After=, Requires=) before
    of "wait for X first"           the timer's job runs
Retry on failure                  Restart= / retry directives available
  → you write it yourself           at the unit level
```

**Honest tradeoff:** cron's syntax is universally known and works identically on literally any Unix system, including ones without systemd (containers, minimal images, older systems) — a `.timer`/`.service` PAIR of files is more verbose than one crontab line for a genuinely simple job. Know both; reach for systemd timers when you're already systemd-managing the service doing the work (so failure/restart/logging is unified), reach for cron for a quick standalone one-liner or a non-systemd environment.

---

## Log Parsing Pipelines

```bash
# Count error lines by hour (nginx/app log with timestamp as $4)
awk -F'[:[]' '{print $2":"$3}' access.log | sort | uniq -c

# Top 10 slowest requests (assuming response time is the last field)
awk '{print $NF, $0}' access.log | sort -rn | head -10

# Extract all 5xx errors with timestamp + URL
awk '$9 ~ /^5/ {print $4, $7, $9}' access.log

# Count occurrences of each exception type in an app log
grep -oP '(?<=Exception: )\w+' app.log | sort | uniq -c | sort -rn

# Tail live errors only, from a rotating log
tail -F app.log | grep --line-buffered -i error

# Extract unique failed login IPs from auth.log (fail2ban-style analysis)
grep "Failed password" /var/log/auth.log | awk '{print $(NF-3)}' | sort | uniq -c | sort -rn
```

### Parsing JSON in Bash — `jq`

Log lines and `awk`/`grep` cover plain text; a huge share of real bash-as-glue work is actually calling an API or reading a JSON log line, where `jq` is the standard tool.

```bash
# Extract one field from an API response
curl -s https://api.example.com/health | jq -r '.status'

# Filter an array of objects, extract specific fields
curl -s https://api.example.com/orders | jq -r '.[] | select(.status == "failed") | .id'

# Pretty-print structured JSON logs (common when app logs are JSON-per-line)
tail -f app.log | jq -r 'select(.level == "ERROR") | "\(.timestamp) \(.message)"'

# Build a JSON payload FROM bash variables (safer than string-concatenating JSON by hand)
jq -n --arg env "$ENV" --arg version "$VERSION" '{environment: $env, version: $version}'
```

`-r` (raw output) strips the surrounding quotes `jq` normally adds around string results — almost always what you want when piping the result into another shell command rather than displaying JSON for a human.

### `xargs` — Parallelizing and Batching a Pipeline

`xargs` takes lines from stdin and turns each one into an argument to a command — the standard way to run something once PER LINE, optionally in parallel, without a `for` loop.

```bash
# Run one command per line (equivalent to a for loop, more concise)
find /var/log -name "*.log" -mtime +30 | xargs rm

# -I{} lets you place the argument anywhere in the command, not just at the end
find . -name "*.tar.gz" | xargs -I{} tar -tzf {}

# -P N runs up to N in PARALLEL instead of one at a time —
# the single biggest reason to reach for xargs over a plain for loop
find /data/backups -name "*.sql" | xargs -P 4 -I{} gzip {}

# -0 / find -print0 — the SAFE combination for filenames containing
# spaces or newlines, which a plain newline-delimited pipe breaks on
find . -name "*.log" -print0 | xargs -0 -I{} mv {} /archive/
```

```
A plain `for f in $(find ...)` loop breaks on filenames with spaces
(word-splitting) and runs strictly sequentially. `xargs -P4` gives you
real parallelism with almost no extra code — e.g. compressing 40 backup
files 4-at-a-time instead of one-at-a-time cuts wall-clock time
roughly 4x on a multi-core box, for exactly the kind of "gzip a pile
of independent files" task that shows up constantly in ops scripts.
```

---

## Backup Automation Script (rsync + tar + rotation)

```bash
#!/usr/bin/env bash
set -euo pipefail
trap 'echo "backup.sh FAILED at line $LINENO" >&2' ERR

BACKUP_DIR="/var/backups/myapp"
SOURCE_DIR="/opt/myapp/data"
RETENTION_DAYS=7
DATE=$(date +%Y%m%d-%H%M%S)
ARCHIVE="$BACKUP_DIR/data-$DATE.tar.gz"
LOCKFILE="/tmp/backup.lock"

# prevent overlapping runs
if [ -e "$LOCKFILE" ]; then
    echo "backup already running (lockfile exists), exiting" >&2
    exit 1
fi
trap 'rm -f "$LOCKFILE"' EXIT
touch "$LOCKFILE"

mkdir -p "$BACKUP_DIR"

echo "[$(date)] Starting backup of $SOURCE_DIR"
tar -czf "$ARCHIVE" -C "$(dirname "$SOURCE_DIR")" "$(basename "$SOURCE_DIR")"
echo "[$(date)] Archive created: $ARCHIVE ($(du -h "$ARCHIVE" | cut -f1))"

# mirror to a remote backup host (delta transfer, resumable)
rsync -avz --delete "$BACKUP_DIR/" "backup@remote-host:/backups/myapp/"
echo "[$(date)] Synced to remote host"

# rotate — keep only last N days locally
find "$BACKUP_DIR" -name "data-*.tar.gz" -mtime "+$RETENTION_DAYS" -delete
echo "[$(date)] Rotated backups older than $RETENTION_DAYS days"

echo "[$(date)] Backup complete."
```

```bash
# crontab entry
0 2 * * * /opt/scripts/backup.sh >> /var/log/backup.log 2>&1
```

---

## Senior Tip: Idempotent, Safe Scripting Habits

```bash
#!/usr/bin/env bash
set -euo pipefail
# -e          exit immediately if any command exits non-zero
# -u          error on any USE of an unset variable (catches typos)
# -o pipefail a pipeline's exit status is the LAST non-zero command,
#             not just the final command (without this, `false | true`
#             looks like success)

IFS=$'\n\t'    # safer word-splitting default (avoids splitting on plain spaces)

trap 'echo "ERROR on line $LINENO. Exit code: $?" >&2' ERR
trap 'cleanup' EXIT               # ALWAYS runs, success or failure — great for lockfiles/tempfiles

cleanup() {
    rm -f "$LOCKFILE"
    echo "cleanup done"
}
```

### `set -e` Gotchas — Where It Silently Doesn't Fire

`set -e` is presented above as "exit immediately if any command fails" — true, but incomplete enough to be a real interview trap. Several common constructs suppress `-e` entirely, by design:

```bash
set -e

# 1. Inside an if/while/until CONDITION — -e does NOT fire here,
#    because the exit code is being intentionally TESTED, not ignored
if some_command_that_fails; then
    echo "this branch runs based on the exit code, script does NOT exit"
fi

# 2. Left side of && or || — same reasoning, the code is being tested
some_command_that_fails && echo "won't reach here, but script continues"

# 3. Inside a pipeline, only the LAST command's exit status counts
#    for -e purposes — grep failing here does NOT stop the script
#    (this is exactly what `pipefail` fixes — see the flag above)
grep "pattern" missing_file.txt | wc -l

# 4. Inside a function called as part of a condition
check_health() { curl -sf http://localhost/health; }
if check_health; then echo "up"; fi     # check_health failing does NOT trigger -e here either

# 5. Command substitution's exit status is IGNORED by -e unless the
#    result is used in a context that itself checks it
result=$(some_command_that_fails)      # script does NOT stop here,
                                          # $result is just empty/partial
```

**Why this matters in an interview:** "does `set -e` guarantee the script stops on any failure" is a genuine trick question — the honest answer is "no, and knowing the five exceptions above is exactly what separates someone who's read about `set -e` from someone who's been bitten by it in production." The practical fix for case 5 (and similar) is to check `$?` explicitly right after, rather than assuming `-e` caught it:

```bash
result=$(some_command_that_fails) || { echo "command failed" >&2; exit 1; }
```

### Signal Handling — Beyond `EXIT`/`ERR`

`trap ... EXIT` and `trap ... ERR` (above) handle a script's own termination. A long-running script (a health-check loop, a worker process) also needs to react to signals sent to it **from outside** — most importantly `SIGTERM`, the polite "please stop" signal `kubectl`, `systemctl stop`, and `docker stop` all send before escalating to `SIGKILL`.

```bash
#!/usr/bin/env bash
set -euo pipefail

RUNNING=true

graceful_shutdown() {
    echo "received SIGTERM — finishing current iteration, then stopping"
    RUNNING=false
}
trap graceful_shutdown SIGTERM
trap graceful_shutdown SIGINT     # Ctrl+C in an interactive terminal

while $RUNNING; do
    process_next_job
    sleep 1
done

echo "shutdown complete"
```

```
SIGTERM  → "please stop" — catchable, the standard shutdown signal
           sent by `docker stop`, `kubectl delete pod`, `systemctl stop`
SIGINT   → Ctrl+C from an interactive terminal — catchable, same idea
SIGKILL  → unconditional, UNCATCHABLE — the process is killed
           immediately with no chance to run cleanup code at all;
           this is what `docker stop` escalates to if the container
           doesn't exit within its grace period (default 10s)
```

This is the bash-side mechanics behind the graceful-shutdown checklist already covered in `20_Best_Practices/01_deployment_dr_incident_cost.md` — "on SIGTERM: stop accepting new connections, finish in-flight requests, then exit" is exactly the `trap ... SIGTERM` pattern above, and the reason a container's `terminationGracePeriodSeconds` must exceed how long this loop's cleanup actually takes: if the grace period is too short, Kubernetes sends `SIGKILL` before the script finishes its polite shutdown, and none of this trap logic ever gets to run.

### Making a Script Idempotent

```bash
# BAD — fails the second time it runs
mkdir /opt/myapp/releases/v1

# GOOD — safe to re-run
mkdir -p /opt/myapp/releases/v1

# BAD — duplicates a cron entry every time the script runs
echo "0 2 * * * backup.sh" >> /etc/crontab

# GOOD — check before adding
grep -qF "backup.sh" /etc/crontab || echo "0 2 * * * backup.sh" >> /etc/crontab

# BAD — assumes the directory doesn't exist yet
tar -xzf release.tar.gz -C /opt/myapp

# GOOD — clean/overwrite deterministically
rm -rf /opt/myapp/current
tar -xzf release.tar.gz -C /opt/myapp/current
```

### Logging Pattern for Production Scripts

```bash
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"
}

log "Starting deploy of version $VERSION"
# ...
log "Deploy finished with status $?"
```

---

## Interview Angle

**Q: What does `set -euo pipefail` actually protect against?**
`-e` stops the script on the first failing command instead of plowing ahead with bad state. `-u` catches typo'd/unset variable names immediately instead of silently treating them as empty strings. `-o pipefail` makes a pipeline fail if ANY stage fails, not just the last one — without it, `grep pattern file | wc -l` can report `0` even if `grep` itself errored, masking the real problem.

**Q: Why does a cron job that works fine when run manually fail when cron runs it?**
Cron executes with a minimal environment — no interactive shell config (`.bashrc`), often a bare `PATH` (just `/usr/bin:/bin`). Scripts that rely on `python` or `node` being on `PATH`, or environment variables normally set at login, silently fail. Fix: use absolute paths, explicitly source needed env, or set `PATH=` at the top of the crontab.

**Q: How do you make a backup script safe to re-run if it crashes halfway?**
Use a lockfile (`trap 'rm -f "$LOCKFILE"' EXIT`) to avoid overlapping runs, make destination operations idempotent (`mkdir -p`, overwrite rather than append-and-assume-empty), and always verify partial output before rotating/deleting old backups.

**Q: `trap ... EXIT` vs `trap ... ERR` — when does each fire?**
`EXIT` fires on ANY script termination — success, failure, or an explicit `exit` — making it the right place for cleanup (lockfiles, tempfiles). `ERR` fires only when a command fails (with `set -e` active) — useful for logging/alerting on the specific failure without necessarily stopping cleanup logic.

**Q: Does `set -e` guarantee a script stops on the first failing command?**
No — it has well-known exceptions: a failing command used as an `if`/`while` condition, the left side of `&&`/`||`, all but the last stage of a pipeline (unless `pipefail` is also set), and a failing command inside `$(...)` command substitution all do NOT trigger `-e`, because in each case the exit code is being deliberately inspected rather than ignored. Relying on `-e` alone for those cases is a common production bug; check `$?` or use `||` explicitly instead.

**Q: A container isn't shutting down cleanly — `docker stop` seems to just hard-kill it after 10 seconds every time. What's likely missing?**
The process inside the container almost certainly isn't handling `SIGTERM` at all — `docker stop` sends `SIGTERM`, waits its grace period (default 10s), then escalates to the uncatchable `SIGKILL`. If the app/script has no `trap ... SIGTERM` (or, for a compiled app, no signal handler) that stops accepting new work and exits cleanly, every stop hits the hard-kill path, skipping any graceful in-flight-request draining. The fix is adding a SIGTERM handler and making sure the grace period given (`terminationGracePeriodSeconds` in Kubernetes, `--time` on `docker stop`) is long enough for that handler to actually finish.
