# Essential Linux Commands

**DevOps Track · Phase 1: Linux**

## Quick Concepts

| Concept | One-line definition |
|---------|---------------------|

| **Argument vs flag** | `command arg -f flagvalue` — flags modify behavior, args are the targets |
| **Glob** | Shell-expanded wildcard pattern (`*.log`) resolved BEFORE the command runs |
| **Pipe (`\|`)** | stdout of one command becomes stdin of the next — the core Unix composition tool |
| **stdin/stdout/stderr** | File descriptors 0/1/2 every process gets by default |
| **In-place edit** | Modifying a file directly instead of printing to stdout (`sed -i`, `sort -o`) |

---

## Quick Concepts — In Depth

### Argument vs Flag

```bash
# Anatomy of a command:
command  argument  -f  flagvalue
   │        │      │      │
   │        │      │      └── value passed to the flag
   │        │      └── flag: modifies HOW the command behaves
   │        └── argument: WHAT the command operates on
   └── the program

# Real example:
grep   -i   -r   "error"   /var/log/
  │    │    │      │          │
  │    │    │      │          └── argument: where to search
  │    │    │      └── argument: what to search for
  │    │    └── flag: recursive
  │    └── flag: case-insensitive
  └── command

# Flags can be combined:
ls -la  =  ls -l -a
grep -rn  =  grep -r -n
```

### Glob — Shell Expansion

```bash
# The SHELL expands globs BEFORE the command runs
# The command never sees "*.log" — it sees the expanded list

echo *.log
# app.log  error.log  access.log  (shell expanded this)

# Proof — when no files match:
ls *.xyz
# ls: cannot access '*.xyz': No such file or directory
# The shell passed the literal string because nothing matched

# Glob patterns:
# *       matches any string (including empty)
# ?       matches exactly one character
# [abc]   matches one of: a, b, or c
# [a-z]   matches any lowercase letter
# [!abc]  matches anything NOT a, b, or c

ls *.py           # all .py files
ls app?.py        # app1.py, app2.py — NOT app10.py
ls app[0-9].py    # app0.py through app9.py
ls [!.]*          # files not starting with dot (not hidden)
ls **/*.py        # recursive (needs shopt -s globstar in bash)
```

### Pipe (`|`)

```bash
# stdout of left → stdin of right
# The kernel connects them with a buffer — runs simultaneously, not sequentially

command1 | command2 | command3

# All three run in parallel:
# command1 starts writing output
# command2 starts reading as soon as bytes appear (doesn't wait for command1 to finish)
# command3 reads from command2 simultaneously

# Real: stream-process a 10GB log file without loading it all into RAM
cat huge.log | grep "ERROR" | awk '{print $4}' | sort | uniq -c
# grep starts reading before cat finishes
# awk starts reading before grep finishes — full pipeline runs concurrently
```

### stdin / stdout / stderr — File Descriptors

```bash
# Every process starts with three open file descriptors:
# 0 = stdin  (keyboard by default)
# 1 = stdout (terminal by default)
# 2 = stderr (terminal by default)

command > file           # redirect stdout (fd 1) to file
command >> file          # append stdout to file
command 2> error.log     # redirect stderr (fd 2) to file
command 2>&1             # redirect stderr TO stdout (merge them)
command > out.log 2>&1   # both stdout and stderr → file
command &> out.log       # bash shorthand for above

command < input.txt      # feed a file as stdin
command <<< "string"     # feed a string as stdin (here-string)

# IMPORTANT: order matters
command > file 2>&1      # correct: stdout→file, stderr→same as stdout (= file)
command 2>&1 > file      # WRONG: stderr→stdout (terminal), THEN stdout→file
                          # stderr still goes to terminal!

# Discard output:
command > /dev/null         # discard stdout
command 2> /dev/null        # discard stderr
command > /dev/null 2>&1    # discard both

# Cron jobs that shouldn't send email:
0 2 * * * /opt/scripts/backup.sh > /dev/null 2>&1
```

---

## Why This Matters for Backend/DevOps Work

```
This is the toolkit you reach for BEFORE you write a script:
   - Grepping a production log for an error pattern during an incident
   - Renaming 500 uploaded files in one line instead of a Python loop
   - Finding every file over 1GB filling up a disk
   - Building a one-liner in CI to extract a version number from a file
   - Piping curl output through jq/grep to check a health endpoint

Speed here is a direct multiplier on how fast you debug production.
```

### 1. Grepping a Production Log During an Incident

This is the most common thing you do during a live outage. You have 30 seconds to find what's wrong.

```bash
# Step 1 — Is there an error at all? How many?
grep -c "ERROR" /var/log/myapp/app.log
# 1482

# Step 2 — When did they start?
grep "ERROR" /var/log/myapp/app.log | head -1
grep "ERROR" /var/log/myapp/app.log | tail -1

# Step 3 — What KIND of errors? (frequency breakdown)
grep "ERROR" /var/log/myapp/app.log | awk '{print $4}' | sort | uniq -c | sort -rn
# 1201  DatabaseConnectionError
#  278  TimeoutError
#    3  KeyError

# Step 4 — Show full message with context (stacktrace lives after the error line)
grep -A10 "DatabaseConnectionError" /var/log/myapp/app.log | tail -30

# Step 5 — Did it coincide with a deploy?
grep "DatabaseConnectionError" /var/log/myapp/app.log | head -1 | awk '{print $1, $2}'
# 2026-08-11 14:23:07   ← error started

ls -lt /opt/myapp/releases/ | head -3
# 2026-08-11 14:21:55  v2.4   ← deploy was 2 minutes before errors
```

**Nginx incident commands:**

```bash
# How many 5xx in the last 5 minutes?
tail -n 5000 /var/log/nginx/access.log | grep -E " 5[0-9]{2} " | wc -l

# Which endpoints are returning 500?
grep " 500 " /var/log/nginx/access.log | awk '{print $7}' | sort | uniq -c | sort -rn | head -10

# Which IP is hammering us?
tail -n 10000 /var/log/nginx/access.log | awk '{print $1}' | sort | uniq -c | sort -rn | head -5

# Response time spikes? (last field = response time in seconds)
tail -n 1000 /var/log/nginx/access.log | awk '$NF > 5 {print $NF, $7}' | sort -rn | head -10
```

**Why this matters:** A grep one-liner takes 3 seconds to type. A Python script to do the same takes 5 minutes to write. During an incident, 5 minutes is an eternity.

---

### 2. Renaming 500 Uploaded Files in One Line

Files arrive from S3, from users, from a legacy system — with the wrong naming convention. Fix them all without writing a script.

```bash
# Files come in as: "Photo 001.JPG", "Photo 002.JPG"
# You need:         "photo_001.jpg", "photo_002.jpg"

# Dry run first — always
for f in *.JPG; do
    new=$(echo "$f" | tr ' ' '_' | tr '[:upper:]' '[:lower:]')
    echo "mv '$f' '$new'"
done
# mv 'Photo 001.JPG' 'photo_001.jpg'

# Looks right — run for real
for f in *.JPG; do
    new=$(echo "$f" | tr ' ' '_' | tr '[:upper:]' '[:lower:]')
    mv "$f" "$new"
done
```

**More patterns:**

```bash
# Add a prefix
for f in *.csv; do mv "$f" "export_$f"; done

# Remove a prefix (# strips from the front)
for f in export_*.csv; do mv "$f" "${f#export_}"; done

# Change extension (% strips from the end)
for f in *.txt; do mv "$f" "${f%.txt}.md"; done

# Timestamp all files
TS=$(date +%Y%m%d)
for f in *.log; do mv "$f" "${f%.log}_${TS}.log"; done

# Zero-padded counter
i=1
for f in report*.csv; do
    mv "$f" "$(printf 'report_%03d.csv' $i)"
    ((i++))
done
# report_001.csv, report_002.csv, ...

# Remove spaces from ALL filenames recursively
find . -name "* *" -type f | while IFS= read -r f; do
    dir=$(dirname "$f")
    base=$(basename "$f")
    mv "$f" "$dir/${base// /_}"
done

# rename command (Perl-based, Ubuntu) — regex renaming
rename 's/\.JPG$/.jpg/' *.JPG          # change extension
rename 's/ /_/g' *.JPG                 # replace spaces
rename -n 's/foo/bar/' *.txt           # -n = dry run
```

---

### 3. Finding Every File Over 1GB Filling Up a Disk

Disk full at 2am. Find what's eating space before the app crashes.

```bash
# Step 1 — which filesystem is full?
df -h
# /dev/sda1  50G  49G  500M  99%  /     ← root is full

# Step 2 — which top-level dir?
du -sh /* 2>/dev/null | sort -h -r | head -10
# 23G  /var
# 12G  /opt

# Step 3 — drill into /var
du -sh /var/* 2>/dev/null | sort -h -r | head -10
# 22G  /var/log

# Step 4 — find the specific large files
find /var/log -type f -size +1G | xargs ls -lh
# -rw-r--r--  myapp  myapp  21G  Aug 11  app.log   ← found it

# Step 5 — TRUNCATE, don't delete (process still has the file open)
> /var/log/myapp/app.log
# OR
truncate -s 0 /var/log/myapp/app.log
```

**Why truncate instead of `rm`:**

```bash
# If you rm a file a running process has open:
#   - File disappears from directory listing
#   - Process still holds the file descriptor
#   - Space is NOT freed until the process closes it
#   - df -h still shows disk full — confusing

# Check who has the file open:
lsof /var/log/myapp/app.log
# myapp  1234  myapp  3w  REG  8,1  21474836480  app.log

# Truncate is safe: file stays open, process keeps writing,
# content is cleared and space is freed immediately
```

**Other common disk culprits:**

```bash
# Docker
docker system df
docker system prune -a         # remove unused images/containers

# Old kernel packages (Ubuntu)
sudo apt autoremove --purge

# Core dump files (crashed processes)
find / -name "core" -type f -size +100M 2>/dev/null

# Temp files not cleaned up
du -sh /tmp/* 2>/dev/null | sort -h -r | head -10
```

---

### 4. Extracting a Version Number in CI

In CI/CD pipelines, pull a value out of a file without writing a Python script.

```bash
# package.json
grep '"version"' package.json | cut -d'"' -f4
# 2.1.4

# pyproject.toml
grep "^version" pyproject.toml | cut -d'=' -f2 | tr -d ' "'

# Helm Chart.yaml
grep "^version:" Chart.yaml | awk '{print $2}'

# Single-line VERSION file
cat VERSION
```

**Use in CI pipelines:**

```bash
# Build and tag a Docker image
VERSION=$(grep '"version"' package.json | cut -d'"' -f4)
docker build -t myapp:$VERSION .
docker tag myapp:$VERSION myapp:latest

# Validate version format before deploy
VERSION=$(cat VERSION)
if [[ ! "$VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    echo "ERROR: invalid version format: $VERSION"
    exit 1
fi

# Git tag from file
VERSION=$(cat VERSION)
git tag "v$VERSION"
git push origin "v$VERSION"
```

**Other CI one-liners:**

```bash
# Check required env var is set
[ -z "$API_KEY" ] && { echo "API_KEY not set"; exit 1; }

# Count test failures in JUnit XML
grep -c 'status="failed"' test-results.xml

# Get last commit hash
git log --oneline -1 | awk '{print $1}'

# Check if a port is open before starting
nc -z localhost 5432 || { echo "postgres not ready"; exit 1; }

# Wait for service to become ready
until curl -sf http://localhost:8080/health; do
    echo "Waiting for app..."
    sleep 2
done
```

---

### 5. Checking Health Endpoints with curl + grep/jq

Verify services are up, APIs are responding, deployments succeeded — from the command line.

```bash
# Basic health check
curl -sf http://localhost:8080/health
# -s = silent (no progress bar)
# -f = fail with non-zero exit code on HTTP 4xx/5xx
# exit 0 = healthy, non-zero = problem

# See the response body
curl -s http://localhost:8080/health
# {"status":"ok","db":"connected","version":"2.1.4"}

# Parse with jq (when available)
curl -s http://localhost:8080/health | jq '.status'
# "ok"
curl -s http://localhost:8080/health | jq -r '.status'
# ok  (raw — no quotes)

# Parse with grep (when jq is not available — Alpine, minimal images)
curl -s http://localhost:8080/health | grep -o '"status":"[^"]*"' | cut -d'"' -f4
# ok

# Get only the HTTP status code
curl -s -o /dev/null -w "%{http_code}" http://localhost:8080/health
# 200
```

**Authenticated endpoints:**

```bash
curl -s -H "Authorization: Bearer $API_TOKEN" http://api.example.com/v1/status
curl -s -H "X-API-Key: $API_KEY" http://api.example.com/v1/data
curl -s -u "$USERNAME:$PASSWORD" http://api.example.com/v1/status

# POST with JSON
curl -s -X POST \
     -H "Content-Type: application/json" \
     -d '{"action":"deploy","version":"2.1.4"}' \
     http://api.example.com/v1/deploy
```

**Wait for new version to go live after a deploy:**

```bash
NEW_VERSION="2.1.4"
echo "Waiting for $NEW_VERSION to be live..."
for i in $(seq 1 30); do
    LIVE=$(curl -sf http://localhost:8080/health \
           | grep -o '"version":"[^"]*"' | cut -d'"' -f4)
    if [ "$LIVE" = "$NEW_VERSION" ]; then
        echo "Version $NEW_VERSION is live!"
        exit 0
    fi
    echo "  Attempt $i: got '$LIVE', waiting..."
    sleep 5
done
echo "TIMEOUT: $NEW_VERSION never came up"
exit 1
```

**Check all microservices at once:**

```bash
SERVICES=(
    "http://api-gateway:8080/health"
    "http://user-service:8081/health"
    "http://payment-service:8082/health"
)

ALL_OK=true
for url in "${SERVICES[@]}"; do
    STATUS=$(curl -s -o /dev/null -w "%{http_code}" "$url")
    if [ "$STATUS" = "200" ]; then
        echo "OK   $url"
    else
        echo "FAIL $url (HTTP $STATUS)"
        ALL_OK=false
    fi
done

$ALL_OK || { echo "Not all services healthy"; exit 1; }
```

---

### The Multiplier in Numbers

```
Scenario: Production is down. 500 errors. Users can't log in.

Engineer A — knows these commands:
  t=0:30  grep finds 4821 DatabaseConnectionErrors
  t=1:00  awk shows it's all one error type
  t=1:30  ss -s shows 287 postgres connections (should be ~20)
  t=2:00  Found the connection leak — roll back the deploy
  t=5:00  Service restored. Total downtime: 5 minutes.

Engineer B — doesn't know these commands:
  t=2:00  Googles "how do I search a log file"
  t=5:00  Writes a Python script to parse the log
  t=8:00  Script finds the DatabaseConnectionError
  t=10:00 Googles "how do I check postgres connections"
  t=20:00 Service restored. Total downtime: 20 minutes.

Same root cause. 4x longer downtime. Not because of knowledge gap —
because of tool familiarity gap.
```

The commands are not complicated. The multiplier comes from **muscle memory** — you don't think about the tool, you think about the problem.

---

## Navigation: `ls`, `pwd`, `cd`

```bash
pwd                        # print current directory — your "you are here"
ls                         # list files
ls -la                     # long format, include hidden (dotfiles)
ls -lh                     # long format, human-readable sizes (K/M/G)
ls -lt                     # sort by modified time, newest first
ls -lS                     # sort by size, largest first
ls -R                      # recursive listing
ls -d */                   # list only directories
ls -la --color=never       # no colour codes (useful when grepping ls output)

cd /var/log                # absolute path
cd ..                      # up one level
cd ~                       # home directory
cd -                       # previous directory (toggle back and forth)
```

**Reading `ls -la` output:**

```bash
ls -la /opt/myapp
# drwxr-xr-x  5  deploy  myapp  4096  Aug 10 14:32  .
# -rw-r--r--  1  deploy  myapp   512  Aug 10 14:32  config.yml
# lrwxrwxrwx  1  deploy  myapp    18  Aug 10 14:30  current -> releases/v2.1
# │           │  │       │      │      │             └── filename (→ target for symlinks)
# │           │  │       │      │      └── last modified time
# │           │  │       │      └── size in bytes
# │           │  │       └── group
# │           │  └── owner
# │           └── hard link count
# └── permissions (type + rwx for u/g/o)
```

**`cd` tricks:**

```bash
cd -              # toggle to previous directory — very useful jumping between two dirs

# Example: jump between two dirs repeatedly:
cd /var/log/nginx
cd /opt/myapp/config
cd -              # back to /var/log/nginx
cd -              # back to /opt/myapp/config

# CDPATH — search these dirs when cd-ing to a relative path
export CDPATH=".:$HOME:$HOME/projects"
cd myapp          # checks ./myapp, ~/myapp, ~/projects/myapp in order
```

**Practical patterns:**

```bash
# Find 5 most recently modified files in a deploy dir
ls -lt /opt/myapp | head -6

# See what's biggest in /var/log — fast disk triage
ls -lhS /var/log | head -10

# List only directories
ls -d /etc/*/

# List files matching pattern
ls *.py
```

---

## Creating & Removing: `mkdir`, `rm`, `touch`

```bash
mkdir logs                    # create one dir
mkdir -p a/b/c                # create nested path, no error if exists
mkdir -p /opt/myapp/{logs,config,releases}  # brace expansion: multiple dirs at once
mkdir -m 700 secrets          # create with specific permissions

touch app.log                 # create empty file OR update mtime if exists
touch -t 202601010000 file    # set a specific timestamp (for testing mtime-based logic)
```

**`rm` — the most dangerous command:**

```bash
rm file.txt            # remove a file
rm -f file.txt         # force (no error if file doesn't exist)
rm -i file.txt         # interactive — prompt before each file
rm -rf build/          # remove directory + all contents recursively — DANGEROUS

# Two critical habits:
# 1. Echo before you remove — verify the expansion
echo rm -rf /tmp/myapp-*     # see what would be deleted
rm -rf /tmp/myapp-*          # then do it

# 2. NEVER do this (classic catastrophic typo):
# rm -rf $MYDIR/            ← if MYDIR is empty, this becomes rm -rf /
# rm -rf /tmp/myapp /       ← space before / deletes /tmp/myapp AND /

# Safe alternative — move to trash dir instead of delete:
mv file.txt /tmp/trash-$(date +%s)/
```

**`rmdir` vs `rm -rf`:**

```bash
rmdir empty_dir/       # only removes if EMPTY — safety net
rmdir -p a/b/c         # remove nested empty dirs from inside out
```

**Practical patterns:**

```bash
# Nuke all __pycache__ dirs in a Python repo
find . -type d -name "__pycache__" -exec rm -rf {} +

# Dry-run first, then delete
find . -name "*.pyc"          # LOOK first
find . -name "*.pyc" -delete  # then delete

# Delete files older than 30 days
find /var/log/myapp -name "*.log" -mtime +30 -delete

# Create a whole app directory structure at once
mkdir -p /opt/myapp/{bin,config,logs,releases,venv}
```

---

## Copying & Moving: `cp`, `mv`

```bash
cp file.txt backup.txt         # copy file
cp -r src/ dst/                 # copy directory recursively
cp -a src/ dst/                  # archive mode — preserves perms/timestamps/symlinks
cp -v file.txt backup.txt         # verbose — show what's copying
cp -n file.txt backup.txt          # no-clobber — don't overwrite existing
cp -u src/ dst/                     # update — only copy if source is newer

mv old.txt new.txt              # rename (same fs = instant, no actual copy)
mv file.txt /opt/archive/        # move into a directory
mv -i file.txt existing.txt       # prompt before overwrite
mv -n file.txt existing.txt        # silent no-overwrite
```

**`cp -r` vs `cp -a` — the important difference:**

```bash
# cp -r copies content, but:
#   - resets permissions to your umask
#   - sets timestamps to now
#   - doesn't preserve symlinks correctly

# cp -a (archive) = cp -dR --preserve=all
#   - preserves permissions exactly
#   - preserves original timestamps
#   - preserves symlinks as symlinks (not copying the target)
#   - USE THIS for backups, deploys, anything where the copy must be identical

# Backup a config dir before making changes:
cp -a /etc/nginx /etc/nginx.bak.$(date +%Y%m%d)
```

**`mv` across filesystems:**

```bash
# mv on same filesystem = instant directory entry update (even for 100GB files)
# mv across filesystems = copy then delete (slow, proportional to size)

# Check if two paths are on the same filesystem:
df /source/path /dest/path
# If "Filesystem" column matches — same fs — mv is instant
```

**Practical patterns:**

```bash
# Batch-rename all .txt to .bak
for f in *.txt; do mv "$f" "${f%.txt}.bak"; done
# ${f%.txt} = strip .txt suffix from $f

# Timestamped backup before editing a config
cp /etc/nginx/nginx.conf /etc/nginx/nginx.conf.$(date +%Y%m%d-%H%M%S).bak

# Move log files older than 7 days to archive
find /var/log/myapp -name "*.log" -mtime +7 -exec mv {} /mnt/archive/ \;

# Rename files with a zero-padded counter
i=1
for f in *.jpg; do
    mv "$f" "photo_$(printf '%03d' $i).jpg"
    ((i++))
done
# photo_001.jpg, photo_002.jpg, ...
```

---

## Finding Files: `find`

`find` walks the live filesystem and can filter by name, type, size, time, owner, permission — then act on results.

```bash
# By name
find . -name "*.py"                    # exact glob (case-sensitive)
find . -iname "*.PY"                   # case-insensitive
find . -name "app*.py"                 # glob prefix match

# By type
find . -type f                         # files only
find . -type d                         # directories only
find . -type l                         # symlinks only

# By time
find . -mtime -1                       # modified in last 24 hours
find . -mtime +30                      # modified more than 30 days ago
find . -newer /etc/passwd              # modified more recently than passwd
find . -mmin -60                       # modified in last 60 minutes

# By size
find . -size +100M                     # bigger than 100MB
find . -size -1k                       # smaller than 1KB
find . -size +1G                       # bigger than 1GB

# By permission
find . -perm 644                       # exact permission match
find . -perm -u+w                      # user has write bit set
find / -perm -4000 2>/dev/null         # SUID binaries (security audit)
find / -perm -002 2>/dev/null          # world-writable files (security audit)

# By owner
find . -user deploy                    # owned by user "deploy"
find . -group www-data                 # owned by group "www-data"
find . -nouser                         # orphaned files (no user in /etc/passwd)

# By depth
find . -maxdepth 2 -name "*.conf"      # don't recurse deeper than 2 levels
find . -mindepth 1 -maxdepth 1         # only immediate children (like ls)
```

**Acting on results:**

```bash
# Delete
find . -name "*.pyc" -delete                     # built-in delete (fastest)
find . -type d -name "__pycache__" -exec rm -rf {} +

# Run a command
find . -name "*.log" -exec gzip {} \;            # gzip each file individually
find . -name "*.log" -exec gzip {} +             # batch: gzip all at once (faster)
# \; = one process per file
# +  = batch all results as arguments to one process — much faster

# Fix permissions on all app files
find /opt/myapp -name "*.sh" -exec chmod +x {} +
find /opt/myapp -type f -exec chmod 644 {} +
find /opt/myapp -type d -exec chmod 755 {} +
```

**Combining conditions:**

```bash
# Default between expressions is AND:
find . -type f -name "*.py" -size +10k    # Python files larger than 10KB

# OR:
find . -name "*.py" -o -name "*.js"       # .py OR .js files

# NOT:
find . ! -name "*.py"                     # everything EXCEPT .py files

# Complex: Python files not in venv, modified in last day
find . -name "*.py" ! -path "*/venv/*" -mtime -1
```

**`find` vs `locate`:**

```
find:
  - Walks the live filesystem right now — always accurate
  - Slower on huge trees (scanning disk)
  - Can filter by permissions, size, time, owner
  - Can act on results (-delete, -exec)

locate:
  - Queries a pre-built index (updated by updatedb, often runs nightly)
  - Instant — doesn't touch disk
  - Can miss files created since last updatedb
  - Only searches by name, not size/permission/time

sudo updatedb    # rebuild locate index manually
locate nginx.conf
```

**Practical patterns:**

```bash
# Find all configs for a service
find /etc -name "*.conf" | xargs grep -l "myapp"

# Security audit: world-writable files
find / -perm -002 -type f 2>/dev/null

# Disk space: find large files
find / -size +500M -type f 2>/dev/null | xargs ls -lh | sort -k5 -rh

# Find recently changed configs (last 10 minutes)
find /etc -mmin -10 -type f
```

---

## Searching Inside Files: `grep`

```bash
grep "ERROR" app.log               # lines containing "ERROR"
grep -i "error" app.log            # case-insensitive
grep -n "ERROR" app.log            # show line numbers
grep -c "ERROR" app.log            # count of matching lines
grep -l "ERROR" *.log              # filenames that contain match
grep -L "ERROR" *.log              # filenames that DON'T contain match
grep -v "DEBUG" app.log            # invert — lines NOT matching
grep -w "cat" file                 # whole word match (not "concatenate")

# Recursive
grep -r "TODO" .                   # search all files under current dir
grep -rn "TODO" .                  # + line numbers
grep -rl "TODO" .                  # just filenames
grep -r "TODO" --include="*.py"    # only Python files
grep -r "TODO" --exclude="*.log"   # exclude log files
grep -r "TODO" --exclude-dir=".git"  # exclude directory

# Context around matches
grep -A3 "Traceback" app.log       # 3 lines After match
grep -B3 "Traceback" app.log       # 3 lines Before match
grep -C3 "Traceback" app.log       # 3 lines both sides (Context)

# Regex
grep -E "(ERROR|FATAL|WARN)" app.log    # extended regex — alternation
grep -E "^ERROR" app.log                # lines STARTING with ERROR
grep -E "ERROR$" app.log                # lines ENDING with ERROR
grep -E "^$" file                       # empty lines
grep -E "ERR.R" app.log                 # . matches any single character
grep -F "literal.string" file           # fixed string, no regex (fastest)
```

**`grep` mode flags — which regex engine:**

```
grep         → basic regex (BRE) — ( | ) need backslash: \( \|
grep -E      → extended regex (ERE) — ( | ) work directly — USE THIS
grep -F      → fixed string, no regex — fastest, for literal searches
grep -P      → Perl regex — most powerful, but NOT on all systems (Alpine!)
```

**Practical patterns:**

```bash
# Count 500 errors in nginx log
grep " 500 " /var/log/nginx/access.log | wc -l

# Find all 5xx errors and show the URL
grep -E " 5[0-9]{2} " /var/log/nginx/access.log | awk '{print $7, $9}'

# Find Python traceback + 10 lines of context
grep -A10 "Traceback (most recent call last)" /var/log/myapp/app.log

# Search all configs for a database hostname
grep -rn "db.internal.company.com" /etc/

# Find TODOs in codebase
grep -rn "TODO\|FIXME\|HACK" --include="*.py" .

# Check if process is running (the [n] trick prevents grep from matching itself)
ps aux | grep "[n]ginx"

# Find lines in file A that are NOT in file B
grep -Fxvf file_b.txt file_a.txt
```

---

## Stream Editing: `sed`

`sed` = Stream EDitor. Reads line by line, applies rules, prints output. Never modifies input unless you use `-i`.

**The substitution command `s`:**

```bash
sed 's/foo/bar/' file         # replace FIRST "foo" per line
sed 's/foo/bar/g' file        # replace ALL "foo" per line (global flag)
sed 's/foo/bar/2' file        # replace only the 2nd occurrence per line
sed 's/foo/bar/gi' file       # global + case-insensitive

# Delimiters don't have to be /
sed 's|/old/path|/new/path|g' file    # use | to avoid escaping slashes
sed 's,old,new,g' file                # use , as delimiter
```

**Address ranges — operate on specific lines:**

```bash
sed '5s/foo/bar/' file        # only on line 5
sed '5,10s/foo/bar/' file     # only on lines 5 through 10
sed '/ERROR/s/foo/bar/' file  # only on lines matching ERROR

sed -n '10,20p' file          # print ONLY lines 10-20 (-n = suppress normal output)
sed -n '/START/,/END/p' file  # print block between START and END patterns
```

**Delete, insert, append:**

```bash
sed '5d' file                   # delete line 5
sed '/DEBUG/d' file             # delete lines matching pattern
sed '/^$/d' file                # delete empty lines
sed '/^#/d' file                # delete comment lines
```

**In-place editing:**

```bash
sed -i 's/foo/bar/g' file            # in-place (Linux GNU sed)
sed -i '' 's/foo/bar/g' file         # in-place (macOS BSD sed — '' required!)
sed -i.bak 's/foo/bar/g' file        # in-place + keep backup as file.bak
```

**Practical patterns:**

```bash
# Bump a version string
sed -i 's/version: 1.2.3/version: 1.2.4/' config.yml

# Strip Windows CRLF line endings
sed -i 's/\r$//' script.sh

# Comment out a line containing a pattern
sed -i '/^DEBUG_MODE=true/s/^/#/' .env

# Uncomment a line
sed -i 's/^#\(DEBUG_MODE\)/\1/' .env

# Remove blank lines and comment lines from a config
sed '/^#/d; /^$/d' nginx.conf

# Replace a URL across all Python files
grep -rl "old-api.example.com" --include="*.py" . \
  | xargs sed -i 's/old-api.example.com/new-api.example.com/g'
```

---

## Column Processing: `awk`

`awk` is a full programming language for structured text. Each line is split into fields (`$1`, `$2`, ..., `$NF`).

**Field basics:**

```bash
awk '{print $1}' file          # first field (whitespace-delimited)
awk '{print $NF}' file         # last field (NF = number of fields)
awk '{print $1, $NF}' file     # first and last (comma = space in output)
awk '{print $1 ":" $2}' file   # concatenate with literal colon
awk '{print $0}' file          # whole line (same as cat)

awk -F',' '{print $2}' file.csv     # comma delimiter (CSV)
awk -F':' '{print $1}' /etc/passwd  # colon delimiter
awk -F'\t' '{print $3}' file.tsv    # tab delimiter
```

**Built-in variables:**

```bash
NF      # number of fields in current line
NR      # current line number (across all files)
FNR     # current line number within current file
$0      # the whole line
FS      # input field separator (default: whitespace)
OFS     # output field separator (default: space)
```

**Conditions and patterns:**

```bash
awk '$3 > 100' file                    # print lines where field 3 > 100
awk '$1 == "ERROR"' file               # exact match on field 1
awk '/pattern/' file                   # print lines matching regex (like grep)
awk '!/pattern/' file                  # lines NOT matching (like grep -v)
awk 'NR==5' file                       # only line 5
awk 'NR>=5 && NR<=10' file             # lines 5 through 10
```

**BEGIN and END blocks:**

```bash
awk 'BEGIN{print "Start"} {print $1} END{print "Done"}' file
# BEGIN: runs once before any input
# END:   runs once after all input

# Sum a column:
awk '{sum+=$2} END{print sum}' file
awk '{sum+=$2} END{printf "Total: %.2f\n", sum}' file

# Count lines matching a pattern:
awk '/ERROR/{count++} END{print count " errors"}' app.log

# Average:
awk '{sum+=$1; count++} END{print "avg:", sum/count}' numbers.txt
```

**Practical patterns:**

```bash
# Top 5 IPs hitting an API (nginx access log)
awk '{print $1}' access.log | sort | uniq -c | sort -rn | head -5

# Total bytes transferred (col 10 in nginx log)
awk '{sum+=$10} END{printf "%.2f MB\n", sum/1024/1024}' access.log

# HTTP status code distribution
awk '{print $9}' access.log | sort | uniq -c | sort -rn

# All 404 request URLs
awk '$9==404 {print $7}' access.log | sort | uniq -c | sort -rn | head -20

# Print lines between two markers
awk '/START_MARKER/,/END_MARKER/' logfile

# Reformat /etc/passwd to "username:UID"
awk -F':' '{print $1 ":" $3}' /etc/passwd
```

---

## `cut`, `sort`, `uniq`, `head`, `tail`

### `cut` — extract columns from structured text

```bash
cut -d',' -f1,3 file.csv      # fields 1 and 3, comma-delimited
cut -d':' -f1 /etc/passwd      # just usernames
cut -d':' -f1,3 /etc/passwd    # username and UID
cut -c1-10 file                # first 10 characters per line
cut -c-5 file                  # first 5 characters
cut -c10- file                 # from character 10 to end
cut -d' ' -f2- file            # all fields from 2 onwards

# cut vs awk:
# cut: simpler, faster, single fixed delimiter
# awk: handles multiple spaces, complex conditions, math
```

### `sort` — sort lines

```bash
sort file                      # alphabetical (lexicographic)
sort -n file                   # numeric (10 comes after 9, not between 1 and 2)
sort -h file                   # human-readable numbers (1K < 1M < 1G)
sort -r file                   # reverse
sort -u file                   # unique: sort + dedupe in one step
sort -k2 file                  # sort by second field
sort -k2,2n file               # sort by second field numerically
sort -t',' -k2 file.csv        # comma-delimited, sort by 2nd column
sort -t':' -k3 -n /etc/passwd  # sort passwd by UID (numeric)

# Sort by multiple keys:
sort -k1,1 -k2,2n file         # primary: col 1 alpha, secondary: col 2 numeric
```

### `uniq` — remove or count adjacent duplicates

```bash
uniq file                       # remove consecutive duplicate lines
uniq -c file                    # count occurrences (prepend count)
uniq -d file                    # print only lines that are duplicated
uniq -u file                    # print only lines that appear exactly once
uniq -i file                    # case-insensitive comparison

# THE RULE: uniq only works on ADJACENT lines — ALWAYS sort first
sort file | uniq -c             # correct
sort file | uniq -c | sort -rn  # most frequent first (the classic pattern)
```

### `head` and `tail`

```bash
head -n 20 file                 # first 20 lines
head -c 100 file                # first 100 bytes
head -n -5 file                 # all lines EXCEPT the last 5

tail -n 50 file                 # last 50 lines
tail -c 200 file                # last 200 bytes
tail -n +5 file                 # all lines FROM line 5 onward (skip first 4)

tail -f app.log                 # follow — watch for new lines
tail -F app.log                 # follow + reopen if file is rotated/replaced
                                # ALWAYS use -F in production, not -f
```

**`tail -f` vs `tail -F` — why it matters in production:**

```bash
# tail -f tracks by file descriptor:
#   nginx rotates the log → creates new access.log, old becomes access.log.1
#   tail -f keeps watching access.log.1 — you stop seeing new requests

# tail -F tracks by filename — notices when the file is replaced, reopens it
#   Use -F when following logs that might rotate

# Follow multiple files at once:
tail -F /var/log/nginx/access.log /var/log/myapp/app.log
```

**Practical patterns:**

```bash
# Most frequent HTTP status codes
awk '{print $9}' access.log | sort | uniq -c | sort -rn

# Unique visitor IPs
awk '{print $1}' access.log | sort -u | wc -l

# Top 10 most recently changed files under /etc
find /etc -type f | xargs ls -lt 2>/dev/null | head -10

# Skip the header line when sorting a CSV
(head -1 file.csv; tail -n +2 file.csv | sort -t',' -k2 -n) > sorted.csv
```

---

## Output Duplication: `tee`

```bash
cmd | tee output.log                  # write to file AND show on screen
cmd | tee -a output.log                # append instead of overwrite
cmd | tee file1 file2                   # write to multiple files simultaneously
cmd | tee output.log | grep ERROR        # save full output, filter what you see

# The classic deploy pattern — see live AND keep a log:
./deploy.sh 2>&1 | tee -a /var/log/deploys/deploy.log
# 2>&1 merges stderr into stdout before piping
# tee saves everything and shows it on screen in real time
```

**Why `2>&1` must come BEFORE the pipe:**

```bash
./deploy.sh > deploy.log 2>&1    # correct: both stdout and stderr → file
./deploy.sh 2>&1 > deploy.log    # wrong: stderr → terminal, stdout → file

./deploy.sh 2>&1 | tee deploy.log  # correct: merge, then tee
```

---

## Building Command Lines: `xargs`

`xargs` converts a stream of lines (stdin) into command-line arguments for another command.

```bash
find . -name "*.log" | xargs rm                      # delete all found log files
find . -name "*.log" | xargs -I{} mv {} /tmp/         # {} placeholder for each item
cat urls.txt | xargs -n1 curl -O                       # one curl call per URL
find . -name "*.jpg" | xargs -P4 -I{} convert {} {}.png # -P4 = 4 parallel jobs

echo "a b c" | xargs -n1 echo               # one arg per invocation: a, b, c
echo "a b c" | xargs -n2 echo               # two args per invocation: "a b", "c"
```

**Why you need `xargs` — stdin vs arguments:**

```bash
# Most commands take operands as ARGUMENTS, not from stdin:
find . -name "*.tmp" | rm        # WRONG — rm ignores stdin, does nothing
find . -name "*.tmp" | xargs rm  # RIGHT — xargs converts lines to arguments

# The difference:
echo "file.txt" | rm           # does nothing
echo "file.txt" | xargs rm     # rm file.txt — correct
```

**Handling spaces in filenames:**

```bash
# Naive xargs breaks on filenames with spaces:
find . -name "*.log" | xargs rm        # FAILS on "my log.log"

# Fix: null-terminated output and input
find . -name "*.log" -print0 | xargs -0 rm
# -print0: separate with null byte instead of newline
# -0: expect null-byte separators

# Or use find's built-in -exec (safest):
find . -name "*.log" -exec rm {} +
```

**Parallel execution with `xargs -P`:**

```bash
# Compress 100 log files using 8 parallel gzip processes
find /var/log -name "*.log" -print0 | xargs -0 -P8 -I{} gzip {}

# Resize images using all CPU cores
ls *.jpg | xargs -P$(nproc) -I{} convert {} -resize 800x {}
# nproc = number of CPU cores
```

---

## Combining Everything — Real Pipelines

```bash
# Who is rate-limited? (top IPs getting 429s)
awk '$9==429 {print $1}' /var/log/nginx/access.log \
  | sort | uniq -c | sort -rn | head -10

# What are the slowest endpoints? (response time as last field)
awk '{print $NF, $7}' access.log \
  | sort -rn | head -20

# Count errors per hour from app log
grep "ERROR" app.log \
  | awk '{print $1, $2}' \
  | cut -d: -f1-2 \
  | sort | uniq -c

# Disk usage per directory, sorted largest first
du -sh /var/log/* 2>/dev/null | sort -h -r | head -10

# Find Python files changed in last hour and syntax-check them
find . -name "*.py" -mmin -60 -print0 \
  | xargs -0 -I{} python3 -m py_compile {} \
  && echo "All OK" || echo "Syntax errors found"

# Find all failed deploys in the last 24 hours
find /var/log/deploys -mtime -1 -name "*.log" \
  | xargs grep -l "FAILED\|ERROR" \
  | xargs ls -lt
```

---

## Senior Tips

```
1. Prefer find ... -delete or -exec ... + over piping to xargs for
   filenames — filenames with spaces/newlines break naive pipes.

2. uniq -c only counts ADJACENT duplicates — always sort first.

3. sed -i differs between GNU (Linux) and BSD (macOS) — macOS requires
   an explicit (even empty) backup suffix: sed -i '' ...
   This breaks scripts written on a Mac when they hit a Linux CI runner.
   Use sed -i.bak to be safe on both.

4. tail -F (capital F) in production — survives log rotation.
   tail -f stops seeing new data after the file is rotated.

5. 2>&1 before the pipe — not after. Redirect stderr TO stdout first,
   then pipe the merged stream.

6. Chain tools instead of reaching for Python for quick log analysis:
   awk | sort | uniq -c | sort -rn is faster to write and run than a
   script for one-off investigation.

7. grep -E for any pattern with |, +, ?, (). Never fight with BRE escaping.
```

---

## Interview Angle

**Q: `grep -r` vs `find -exec grep`?**

`grep -r` is simpler and usually faster for "search everything under a directory." `find ... -exec grep` is for when you need to filter WHICH files first (by name, size, mtime, owner, permission) before searching their content.

```bash
# grep -r: search all Python files for a pattern
grep -rn "db.connect" --include="*.py" .

# find + grep: search only files modified in the last hour
find . -name "*.py" -mmin -60 -exec grep -n "db.connect" {} +
```

**Q: Why does `uniq -c` sometimes give wrong-looking counts?**

Because it only collapses consecutive duplicate lines. If duplicates aren't adjacent, sort first: `sort file | uniq -c`. The most common mistake is running `uniq -c` on an unsorted log and getting counts of 1 for everything.

**Q: `xargs` vs a direct pipe — when do you need it?**

When the downstream command takes its operands as command-line arguments rather than reading stdin (`rm`, `cp`, `mv`, `curl`). `xargs` bridges a stream of lines into an argument list. Also use `xargs -P` for easy parallelism.

**Q: Difference between `sed 's/a/b/g'` and `awk '{gsub("a","b"); print}'`?**

`sed` is simpler and faster for pure substitution. `awk` is for when you need to also do conditional logic, column processing, or math in the same pass. For a simple global replace across a file, `sed` wins. For "replace in column 3 only if column 5 > 100", `awk` is the right tool.

**Q: How do you find which process has a file open?**

```bash
lsof /path/to/file          # list open files — shows PID, process name, user
lsof /var/log/app.log       # which process is writing to this log
fuser /var/log/app.log      # simpler: just shows PIDs
```

This is the answer to "why can't I delete this file" or "who is holding this port open."