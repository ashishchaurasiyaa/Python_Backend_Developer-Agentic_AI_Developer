# Bash Scripting — Hands-On Lab
**DevOps Track · Phase 2 Practical**

## Prerequisites

- Any Linux/macOS terminal with bash 4+ (macOS ships an ancient bash 3.2 by default — associative arrays in Lab 2 need `brew install bash` or just use WSL2/a Linux VM/Docker instead).
- No cloud account needed — everything here runs locally.
- Quick check: `bash --version` — if it says `3.2.x` on macOS, either `brew install bash` or run these labs inside `docker run -it --rm -v $(pwd):/lab -w /lab ubuntu:24.04 bash` (install bash/coreutils are already there).
- Work in a scratch directory: `mkdir -p ~/bash-lab && cd ~/bash-lab`.

---

## Lab 1: Argument Parsing and Safe Scripting Habits

**Objective:** Write a script that behaves like a real CLI tool — validates its inputs, fails loudly, and doesn't silently do the wrong thing.

**Task:**

Write a script `greet.sh` that:
1. Starts with the correct shebang and `set -euo pipefail`.
2. Requires exactly 2 positional arguments: a name and an environment (`dev`, `staging`, or `prod`). If the wrong number of args is given, print a usage message to stderr and exit with a non-zero code.
3. If the environment given isn't one of the three valid values, print an error and exit non-zero (use a `case` statement).
4. Otherwise prints: `Hello <name>, you are targeting <env>.`
5. Test it: run with 0 args, 1 arg, 2 valid args, and 2 args with an invalid environment. Confirm `$?` after each run.

<details>
<summary>Solution / walkthrough</summary>

```bash
#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -ne 2 ]; then
    echo "Usage: $0 <name> <dev|staging|prod>" >&2
    exit 1
fi

NAME="$1"
ENV="$2"

case "$ENV" in
    dev|staging|prod)
        ;;
    *)
        echo "ERROR: invalid environment '$ENV' (must be dev, staging, or prod)" >&2
        exit 1
        ;;
esac

echo "Hello $NAME, you are targeting $ENV."
```

```bash
chmod +x greet.sh

./greet.sh; echo "exit: $?"                    # usage error, exit 1
./greet.sh alice; echo "exit: $?"               # usage error, exit 1
./greet.sh alice prod; echo "exit: $?"          # "Hello alice, you are targeting prod.", exit 0
./greet.sh alice qa; echo "exit: $?"            # invalid env error, exit 1
```

**Why `set -euo pipefail` matters here:** without `-u`, a typo like `$ENVV` instead of `$ENV` would silently expand to an empty string instead of erroring — you'd get a confusing "invalid environment ''" instead of an immediate, obvious bug report.
</details>

---

## Lab 2: Config-Driven Health Checker (Arrays + Loops + Functions)

**Objective:** Build something closer to a real ops tool — loop over a list of services, check each one, and report a pass/fail summary. This combines associative arrays, functions, loops, and `curl` health-check patterns from the lesson.

**Task:**

Write a script `healthcheck.sh` that:
1. Defines an associative array mapping service names to URLs, e.g. `httpbin` → `https://httpbin.org/status/200`, `httpbin-fail` → `https://httpbin.org/status/500`, and one you expect to time out/fail (a bad hostname).
2. Writes a function `check_service` that takes a name and URL, curls it with a short timeout, and returns 0 if the HTTP status is 200-299, non-zero otherwise (use `curl -s -o /dev/null -w "%{http_code}"` and compare).
3. Loops over every entry in the associative array, calls `check_service` for each, and tracks pass/fail counts using `local` variables inside functions where appropriate and script-level counters at the top level.
4. At the end, prints a summary table: service name, status (UP/DOWN), and a final line like `3 checked, 2 up, 1 down`.
5. Exits with code 0 if everything passed, 1 if anything failed (so it's usable as a CI gate).

<details>
<summary>Solution / walkthrough</summary>

```bash
#!/usr/bin/env bash
set -uo pipefail
# NOTE: deliberately NOT using -e here — we WANT curl failures to be
# handled by our own logic (an early exit on the first down service
# would defeat the point of checking all of them)

declare -A SERVICES=(
    [httpbin-ok]="https://httpbin.org/status/200"
    [httpbin-fail]="https://httpbin.org/status/500"
    [bad-host]="https://this-host-does-not-exist.invalid/"
)

TOTAL=0
UP=0
DOWN=0

check_service() {
    local name=$1
    local url=$2
    local code
    code=$(curl -s -o /dev/null -m 3 -w "%{http_code}" "$url" 2>/dev/null || echo "000")

    if [[ "$code" =~ ^2[0-9][0-9]$ ]]; then
        echo "UP   $name ($code)"
        return 0
    else
        echo "DOWN $name ($code)"
        return 1
    fi
}

echo "Running health checks..."
echo "------------------------"

for name in "${!SERVICES[@]}"; do
    TOTAL=$((TOTAL + 1))
    if check_service "$name" "${SERVICES[$name]}"; then
        UP=$((UP + 1))
    else
        DOWN=$((DOWN + 1))
    fi
done

echo "------------------------"
echo "$TOTAL checked, $UP up, $DOWN down"

if [ "$DOWN" -gt 0 ]; then
    exit 1
fi
exit 0
```

```bash
chmod +x healthcheck.sh
./healthcheck.sh
echo "final exit code: $?"
```

**Why not `set -e` here:** `-e` would abort the whole script the instant the first `curl` fails (non-2xx or timeout), which is the opposite of what a health-check-everything tool should do. This is a deliberate exception to the "always use `set -euo pipefail`" default — know the rule well enough to know when NOT to apply it.

**Why `${!SERVICES[@]}`:** this is the syntax for iterating over an associative array's KEYS — `${SERVICES[@]}` alone would give you just the VALUES with no way to know which service they belong to.
</details>

---

## Lab 3: Idempotent Backup Script with Locking and Cleanup (Production-Style)

**Objective:** Build the real backup-script pattern from the lesson — lockfile, idempotency, trap-based cleanup, retention rotation — and prove it's actually safe to re-run and safe against overlapping executions.

**Task:**

Write a script `backup.sh` that:
1. Takes a source directory as `$1` and backs it up into `~/bash-lab/backups/`, as a timestamped `tar.gz` (e.g. `data-20260725-140501.tar.gz`).
2. Uses a lockfile so a second concurrent run refuses to start (print an error and exit non-zero if the lock exists).
3. Uses `trap` to guarantee the lockfile is removed on exit — success, failure, or Ctrl+C — not just on the happy path.
4. Logs each step with a timestamped `log()` function, both to stdout and appended to `~/bash-lab/backups/backup.log`.
5. After creating the archive, deletes any backup older than a `RETENTION_DAYS` variable (set it to `0` for testing purposes so you can actually observe deletion, or fake old timestamps with `touch -t`).
6. Test idempotency: run it twice in a row on the same source dir and confirm the second run doesn't error out or corrupt anything (each run makes its own new timestamped file, no naming collision, no leftover lock).
7. Test the lock: start a long-running fake backup (e.g. by adding a `sleep 5` before cleanup) in the background, then immediately try running it again in a second terminal — confirm the second invocation refuses to run.

<details>
<summary>Solution / walkthrough</summary>

```bash
#!/usr/bin/env bash
set -euo pipefail

SOURCE_DIR="${1:?usage: backup.sh <source-dir>}"
BACKUP_DIR=~/bash-lab/backups
RETENTION_DAYS=0          # set to 0 for testing so you can observe deletion happen
DATE=$(date +%Y%m%d-%H%M%S)
ARCHIVE="$BACKUP_DIR/data-$DATE.tar.gz"
LOCKFILE=/tmp/bash-lab-backup.lock
LOG_FILE="$BACKUP_DIR/backup.log"

mkdir -p "$BACKUP_DIR"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"
}

if [ -e "$LOCKFILE" ]; then
    log "ERROR: backup already running (lockfile exists), exiting"
    exit 1
fi

cleanup() {
    rm -f "$LOCKFILE"
    log "cleanup done"
}
trap cleanup EXIT
touch "$LOCKFILE"

log "Starting backup of $SOURCE_DIR"
tar -czf "$ARCHIVE" -C "$(dirname "$SOURCE_DIR")" "$(basename "$SOURCE_DIR")"
log "Archive created: $ARCHIVE ($(du -h "$ARCHIVE" | cut -f1))"

# uncomment to test the lock manually in a second terminal:
# sleep 5

log "Rotating backups older than $RETENTION_DAYS days"
find "$BACKUP_DIR" -name "data-*.tar.gz" -mtime "+$RETENTION_DAYS" -print -delete

log "Backup complete."
```

```bash
chmod +x backup.sh
mkdir -p ~/bash-lab/sample-data && echo "hello" > ~/bash-lab/sample-data/file.txt

# 6. Idempotency test — run twice back to back
./backup.sh ~/bash-lab/sample-data
./backup.sh ~/bash-lab/sample-data
ls ~/bash-lab/backups/
# two distinct timestamped archives, no errors, no leftover .lock file

# 7. Lock test — uncomment the `sleep 5` line above first, then:
./backup.sh ~/bash-lab/sample-data &     # start in background
sleep 1
./backup.sh ~/bash-lab/sample-data       # second run, should immediately refuse
# ERROR: backup already running (lockfile exists), exiting
wait   # let the background one finish and clean up its lock
```

**What makes this idempotent, specifically:**
- Timestamped filenames mean re-running never collides with or overwrites a previous archive.
- `mkdir -p` (not `mkdir`) means re-running never errors because the directory already exists.
- The lockfile pattern means two overlapping runs can't corrupt each other's output or double-rotate retention.
- `trap cleanup EXIT` guarantees the lock is released even if `tar` fails partway or you Ctrl+C mid-run — a plain `rm "$LOCKFILE"` at the bottom of the script would NOT run if an earlier command failed under `set -e`.
</details>

---

## Lab 4: Debug a Broken Cron Script (Troubleshooting Scenario)

**Objective:** This is the single most common real-world bash failure mode: "it works when I run it manually, but cron silently fails." Reproduce it, diagnose it, fix it.

**Task:**

1. Write a deliberately broken script `broken_cron_job.sh` that relies on things that exist in your interactive shell but NOT in cron's minimal environment:
   - Calls a command using just its bare name assuming it's on `PATH` in a way that's actually installed via a user-level tool (pick something like `python3` if it's aliased/managed by a version manager, or simulate it by calling a script that isn't using an absolute path)
   - References a relative path instead of an absolute one
   - Assumes an environment variable is set (like `$HOME` behaving unexpectedly, or a custom var you only set in `.bashrc`)
2. Simulate cron's minimal environment locally WITHOUT actually needing to wait for a real cron run, using `env -i` (this strips almost the entire environment, closely mimicking what cron gives your script):
   ```bash
   env -i /bin/bash ./broken_cron_job.sh
   ```
3. Observe it fail differently (or identically) to how it behaves in your normal shell. Diagnose exactly which assumption broke.
4. Fix the script: absolute paths everywhere, explicit `PATH` set at the top if needed, no reliance on interactive-shell-only config.
5. Re-run under `env -i` again and confirm it now works cleanly.
6. Bonus: write the actual crontab line you'd use to run this every day at 2:30 AM, with output redirected to a log file (per the lesson's cheat sheet).

<details>
<summary>Solution / walkthrough</summary>

```bash
# --- broken_cron_job.sh (the BEFORE version) ---
#!/usr/bin/env bash
echo "Home is: $HOME"
echo "Custom var is: $MY_CUSTOM_VAR"        # only ever set in ~/.bashrc, never exported to cron
python3 --version                             # relies on PATH being fully populated
cat ./notes.txt                                # relative path — cron's CWD is often NOT what you expect
```

```bash
chmod +x broken_cron_job.sh
echo "some notes" > notes.txt

# Normal shell — probably looks fine
./broken_cron_job.sh

# Simulated cron environment — minimal env, no .bashrc sourced
env -i /bin/bash ./broken_cron_job.sh
# Home is:                              <- $HOME often unset entirely under env -i
# Custom var is:                          <- empty, as expected, was never exported anyway
# ./broken_cron_job.sh: line 4: python3: command not found   <- PATH is nearly empty under env -i
# cat: ./notes.txt: No such file or directory (if run from a different CWD than expected)
```

```bash
# --- broken_cron_job.sh (the FIXED version) ---
#!/usr/bin/env bash
set -euo pipefail

PATH="/usr/local/bin:/usr/bin:/bin:$PATH"     # explicit PATH, don't trust the caller's environment
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"   # absolute dir of THIS script, robust to CWD

echo "Script dir is: $SCRIPT_DIR"
/usr/bin/python3 --version                    # absolute path to the binary, no PATH guessing
cat "$SCRIPT_DIR/notes.txt"                    # absolute path, works regardless of caller's CWD
```

```bash
env -i /bin/bash ./broken_cron_job.sh
# now works cleanly — no assumptions about caller's environment or CWD
```

```
# 6. Crontab line — absolute path to the script, output captured, errors included
30 2 * * * /home/deploy/bash-lab/broken_cron_job.sh >> /home/deploy/bash-lab/cron.log 2>&1
```

**Why `env -i` is the right local reproduction tool:** cron doesn't source `.bashrc`/`.bash_profile` and starts with a nearly bare environment (`PATH=/usr/bin:/bin` at most, no `HOME`-dependent config, no aliases/functions). `env -i` strips almost everything, giving you a fast, no-wait way to catch "works for me, fails in cron" bugs before they actually fail in cron at 2:30 AM with nobody watching.
</details>

---

## Self-Check Checklist

- [ ] Can you explain what each of `-e`, `-u`, and `-o pipefail` actually protects against, without looking it up?
- [ ] Do you know when it's correct to NOT use `set -e` (hint: Lab 2)?
- [ ] Can you write a function that uses `local` correctly and explain why skipping `local` is dangerous in longer scripts?
- [ ] Can you write a lockfile pattern with `trap ... EXIT` from memory?
- [ ] Can you explain the difference between `"$@"` and `"$*"` and why it matters when forwarding arguments?
- [ ] Can you iterate over an associative array's keys AND values correctly?
- [ ] Given a script that "works manually but fails under cron," can you reproduce and diagnose it locally without waiting for an actual cron run?
- [ ] Can you write a valid crontab line for "every day at 2:30 AM, log both stdout and stderr"?
- [ ] Do you know why `mkdir -p` is idempotent-safe but plain `mkdir` is not?
- [ ] Can you explain the difference between `trap ... EXIT` and `trap ... ERR`?
