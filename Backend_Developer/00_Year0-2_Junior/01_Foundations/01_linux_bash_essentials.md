# Foundations — Linux & Bash Essentials for Backend Devs
**Foundations · Year 0-2 | Zero → Senior**

## Quick Concepts

- **Shell** = program that interprets your commands (bash, zsh, fish)
- **Bash** = Bourne Again Shell — most common Linux shell
- **POSIX** = portable standard (works across most Unix-likes)
- **Process** = running instance of a program
- **PID** = process ID (unique number)
- **File descriptor** = number representing an open file (0=stdin, 1=stdout, 2=stderr)
- **Pipe (`|`)** = stdout of left command → stdin of right
- **Permissions** = `rwx` for user / group / others (e.g., `755` = `rwxr-xr-x`)
- **Environment variable** = key-value pair available to processes (e.g., `PATH`, `HOME`)
- **Shebang (`#!`)** = first line of script telling OS which interpreter to use

---

## Why Every Backend Dev Must Know This

```
Backend = code running on Linux servers.

Daily tasks that require Linux/Bash:
   ✓ SSH into prod / staging
   ✓ Check logs (tail, grep, less)
   ✓ Inspect processes (ps, top, htop)
   ✓ Debug network issues (curl, netstat, ss)
   ✓ Manage files + permissions
   ✓ Write deployment scripts
   ✓ Read CI/CD pipeline configs
   ✓ Quick one-liners to extract data

You can avoid this for ~2 years using cloud UIs.
Past that, no.
```

---

## Filesystem & Navigation

### Directory Structure (FHS — Filesystem Hierarchy Standard)

```
/                  root
├── /bin           essential binaries (ls, cat, etc.)
├── /sbin          system binaries (root-only)
├── /usr           user programs (/usr/bin, /usr/local)
├── /etc           system config files
├── /var           variable data (logs, mail, cache)
│   ├── /var/log   ← LOGS — first place to look
│   └── /var/lib   service data
├── /tmp           temporary (cleared on reboot)
├── /home          user home dirs
├── /opt           optional / third-party software
├── /proc          virtual fs: process info
├── /sys           virtual fs: kernel/hardware
├── /dev           device files
└── /mnt /media    mount points
```

### Essential Commands

```bash
pwd                    # print working directory
ls -la                 # list all (incl hidden), long format
cd /var/log            # change dir
cd ~                   # home dir
cd -                   # previous dir

mkdir -p a/b/c         # create nested dirs
rmdir empty_dir        # remove empty dir
rm -rf dir             # remove dir + contents (CAREFUL)

cp -r src/ dst/        # copy recursive
mv old new             # move/rename

touch file.txt         # create empty file or update timestamp
file foo               # detect file type
stat foo               # detailed file metadata
du -sh *               # disk usage per item, human-readable
df -h                  # disk free across filesystems
```

---

## File Permissions

### Numeric Notation

```
   r=4   w=2   x=1

   chmod 755 script.sh     →  rwxr-xr-x
   chmod 644 config.yml    →  rw-r--r--
   chmod 600 .ssh/id_rsa   →  rw------- (private key MUST be this)
   chmod +x script.sh      →  add execute (any user)
```

### Symbolic Notation

```bash
chmod u+x file              # add execute for user
chmod g-w file              # remove write for group
chmod o=r file              # set other to read-only
chmod a+rx file             # all: read + execute
```

### Ownership

```bash
chown user:group file       # change owner + group
chown -R deploy:deploy /var/www
chgrp group file
```

### Senior Tip

```
Production secret files:
   chmod 600 .env
   chmod 600 private_key.pem
   chmod 700 ~/.ssh/

Anything 777 in production = security audit failure.
```

---

## Viewing & Searching Files

### View

```bash
cat file.txt                # entire file
less file.log               # paginated (q to quit, /search)
head -n 50 file.log         # first 50 lines
tail -n 100 file.log        # last 100 lines
tail -f /var/log/app.log    # FOLLOW (live)
tail -F file                # follow even if rotated
```

### Search

```bash
grep "ERROR" app.log                    # lines matching
grep -i "error" app.log                 # case-insensitive
grep -r "TODO" .                        # recursive
grep -E "(ERROR|FATAL)" app.log         # regex
grep -v "DEBUG" app.log                 # invert (exclude)
grep -c "ERROR" app.log                 # count matches
grep -n "ERROR" app.log                 # show line numbers

# show 3 lines before + 3 after match
grep -A3 -B3 "exception" app.log
```

### Find Files

```bash
find . -name "*.py"                     # by pattern
find . -name "*.log" -mtime -1          # modified < 24h
find . -size +100M                      # bigger than 100M
find . -name "*.pyc" -delete            # remove all .pyc
find /var/log -mtime +30 -delete        # logs older than 30 days
```

---

## Text Processing (Pipe + Filter Pattern)

### Pipe Composition

```bash
# Top 5 IPs hitting your API
cat nginx.log | awk '{print $1}' | sort | uniq -c | sort -rn | head -5

# Count of HTTP status codes
cat nginx.log | awk '{print $9}' | sort | uniq -c | sort -rn

# Lines per minute
cat app.log | awk '{print $1}' | cut -d: -f1-2 | uniq -c
```

### Core Tools

```bash
wc -l file              # line count
sort file               # sort
sort -u file            # unique (sort + dedupe)
uniq -c                 # count consecutive duplicates

cut -d',' -f2,4 file.csv  # extract cols 2 + 4 from CSV
cut -c1-10 file           # first 10 chars per line

tr 'a-z' 'A-Z' < file     # translate (lowercase → upper)
tr -d '\r' < file         # delete carriage returns

awk '{print $2, $4}' file # column 2 + 4
awk -F',' '{print $1}'    # CSV first column

sed 's/old/new/g' file    # find/replace
sed -n '10,20p' file      # print lines 10-20
sed -i 's/foo/bar/g' file # in-place edit (LINUX)
                          # macOS: sed -i '' 's/.../.../g' file
```

### Real-World One-Liners

```bash
# Count unique users in access log
awk '{print $1}' access.log | sort -u | wc -l

# Find largest 10 files
find / -type f -exec du -h {} \; 2>/dev/null | sort -rh | head -10

# Process IDs of nginx
pgrep nginx

# CPU + memory of top processes
ps aux --sort=-%cpu | head

# Disk usage of current dir, sorted
du -sh */ | sort -rh

# All TCP connections to port 5432 (Postgres)
ss -tn 'sport = :5432'
```

---

## Process Management

### Inspect

```bash
ps aux                     # all processes (BSD style)
ps -ef                     # all processes (System V style)
ps aux | grep python       # find python processes
top                        # live
htop                       # better live (install)
pgrep -f "uvicorn"        # PIDs matching pattern

# Show parent/child tree
pstree -p
```

### Control

```bash
kill 1234                  # SIGTERM (graceful)
kill -9 1234              # SIGKILL (force, last resort)
kill -HUP 1234            # SIGHUP (reload, used by nginx)

pkill -f "celery"          # kill by name pattern
killall python             # kill all named python

# Background + foreground
long_command &             # run in background
jobs                       # list bg jobs
fg %1                      # bring job 1 to foreground
bg %1                      # send job 1 to bg
nohup ./run.sh &           # immune to logout

disown -h %1               # don't kill on shell exit
```

### Resource Monitoring

```bash
top                        # CPU + mem live
htop                       # nicer (sudo apt install htop)
free -h                    # memory summary
vmstat 1                   # CPU + memory every 1s
iostat -x 1                # disk I/O
iotop                      # I/O per process
mpstat -P ALL 1            # per-CPU usage
uptime                     # load averages
```

### Senior Pattern: Find a Runaway Process

```bash
# 1. Spot it
top                        # see PID using 100% CPU
ps aux --sort=-%cpu | head # confirm

# 2. Investigate
ls -la /proc/$PID/         # what is it
cat /proc/$PID/cmdline     # how was it started
cat /proc/$PID/status      # state, parent, threads

# 3. Capture stack trace (Python)
py-spy dump --pid $PID

# 4. Send SIGTERM, then SIGKILL if it doesn't respond
kill $PID
sleep 5
kill -9 $PID
```

---

## I/O Redirection

### Streams

```
stdin  (0) ← keyboard or pipe input
stdout (1) → terminal or next pipe
stderr (2) → terminal (NOT captured by pipe by default)
```

### Redirection

```bash
cmd > file                 # stdout to file (overwrite)
cmd >> file                # stdout to file (append)
cmd 2> err.log             # stderr to file
cmd > out 2> err           # split stdout + stderr
cmd > out 2>&1             # both to out (stderr → stdout)
cmd &> out                 # shorthand for 2>&1

cmd < input.txt            # stdin from file

cmd1 | cmd2                # stdout of cmd1 → stdin of cmd2
cmd1 |& cmd2               # also pipe stderr (bash 4+)

# tee — write to file AND continue piping
cmd | tee out.log | grep ERROR
```

### Real Examples

```bash
# Capture all output of a long-running process
./deploy.sh > deploy.log 2>&1 &

# Silent (discard output)
cmd > /dev/null 2>&1

# Save stderr only
cmd 2> errors.log

# Check exit code
cmd; echo $?    # 0 = success, non-zero = failure
```

---

## Networking Commands (Daily Backend Use)

```bash
# DNS
dig example.com               # query DNS
dig +short example.com        # just the answer
nslookup example.com          # alternative
host example.com              # simple

# Test HTTP
curl -v https://api.example.com           # verbose
curl -X POST -d '{"x":1}' \
     -H "Content-Type: application/json" url
curl -I https://example.com               # headers only (HEAD)
curl -o file.zip https://...              # save to file

# Test connectivity
ping example.com              # ICMP
ping -c 4 example.com         # 4 packets then stop
traceroute example.com        # network path
mtr example.com               # ping + traceroute combined

# Port scanning / connection testing
nc -zv host 5432              # is port open?
telnet host 5432              # connect (legacy)
nmap -p 80,443 host           # scan ports

# What's listening on my machine
ss -tlnp                      # TCP listening + process
ss -tnp                       # all TCP + process
netstat -tlnp                 # older alternative
lsof -i :8000                 # what's using port 8000

# Connection inspection
ss -s                         # summary
ss -tn 'state established'    # active connections
```

---

## SSH & Remote Work

### Connect

```bash
ssh user@host                 # basic
ssh -p 2222 user@host         # custom port
ssh -i ~/.ssh/key user@host   # specific key

# Run remote command + exit
ssh user@host 'tail -100 /var/log/app.log'

# Copy files
scp local.txt user@host:/tmp/
scp -r ./dir user@host:/tmp/
rsync -avz local/ user@host:/remote/   # better for large transfers
```

### Config (`~/.ssh/config`)

```
Host prod
    HostName 1.2.3.4
    User deploy
    Port 22
    IdentityFile ~/.ssh/prod_key

Host staging
    HostName staging.example.com
    User deploy

# Now: ssh prod  →  connects with all above
```

### Tunneling

```bash
# Local port-forward — access remote DB locally
ssh -L 5433:db.internal:5432 jump-host
# → localhost:5433 connects to db.internal:5432 via jump-host

# Reverse tunnel — expose local to remote
ssh -R 8080:localhost:3000 server

# SOCKS proxy
ssh -D 1080 user@host
```

---

## Bash Scripting Essentials

### Shebang + Strict Mode

```bash
#!/usr/bin/env bash
set -euo pipefail        # safer scripts
IFS=$'\n\t'

# -e: exit on error
# -u: error on unset variable
# -o pipefail: pipe fails if any command fails
```

### Variables

```bash
name="alice"
echo "hello, $name"      # interpolation
readonly PI=3.14         # constant
unset name               # delete

# Default values
echo "${USER:-default}"  # use 'default' if unset/empty

# Command substitution
date_str=$(date +%Y-%m-%d)
file_count=$(ls | wc -l)
```

### Conditionals

```bash
if [ "$x" -gt 10 ]; then
    echo "big"
elif [ "$x" -eq 10 ]; then
    echo "exact"
else
    echo "small"
fi

# String comparison
if [ "$env" = "prod" ]; then ...

# File tests
if [ -f /etc/passwd ]; then ...    # is file
if [ -d /var/log ]; then ...        # is dir
if [ -x ./run.sh ]; then ...        # is executable
if [ ! -e file ]; then ...          # does NOT exist

# Modern test [[ ]] — preferred
if [[ "$x" =~ ^[0-9]+$ ]]; then     # regex match
    echo "is number"
fi
```

### Loops

```bash
for f in *.log; do
    gzip "$f"
done

for i in {1..10}; do
    echo $i
done

# C-style
for ((i=0; i<10; i++)); do
    echo $i
done

# Read file line by line
while IFS= read -r line; do
    echo "$line"
done < input.txt
```

### Functions

```bash
deploy() {
    local env=$1
    local version=$2
    echo "deploying $version to $env"
    # ...
}

deploy "prod" "v1.2.3"
```

### Real-World Script Example

```bash
#!/usr/bin/env bash
set -euo pipefail

# Backup script

BACKUP_DIR="${BACKUP_DIR:-/var/backups}"
DATE=$(date +%Y%m%d-%H%M%S)
TARGET="$BACKUP_DIR/db-$DATE.sql.gz"

mkdir -p "$BACKUP_DIR"

if ! command -v pg_dump &> /dev/null; then
    echo "ERROR: pg_dump not found" >&2
    exit 1
fi

echo "Backing up to $TARGET"
pg_dump "$DATABASE_URL" | gzip > "$TARGET"

# Keep only last 7 backups
find "$BACKUP_DIR" -name "db-*.sql.gz" -mtime +7 -delete

echo "Backup complete: $(du -h "$TARGET" | cut -f1)"
```

---

## systemd (Linux Service Manager)

### Run Your Service as a Daemon

```ini
# /etc/systemd/system/myapp.service
[Unit]
Description=My FastAPI App
After=network.target

[Service]
User=app
Group=app
WorkingDirectory=/opt/myapp
EnvironmentFile=/opt/myapp/.env
ExecStart=/opt/myapp/venv/bin/uvicorn main:app --port 8000
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable myapp        # start on boot
sudo systemctl start myapp
sudo systemctl status myapp
sudo systemctl restart myapp
journalctl -u myapp -f             # follow logs
journalctl -u myapp --since "1h ago"
```

---

## Environment Variables

```bash
# Set + use
export DATABASE_URL="postgres://..."
echo $DATABASE_URL

# Persistent (login shells)
echo 'export PATH=$HOME/bin:$PATH' >> ~/.bashrc
source ~/.bashrc

# Run command with custom env (no export)
DEBUG=1 python app.py

# .env file pattern
set -a
source .env
set +a
```

### PATH Explained

```bash
echo $PATH      # colon-separated list of dirs

# When you type `ls`, shell searches each dir in $PATH
# until it finds an executable named `ls`

which python    # which binary will run
type python     # alias / function / file
```

---

## Common Senior Gotchas

```
1. ✗ rm -rf $VAR/something    when $VAR is empty
   → rm -rf /something — catastrophic
   ✓ Use [ -n "$VAR" ] check first
   ✓ rm -rf "${VAR:?missing}"/something

2. ✗ Unquoted variables with spaces
   → for f in $files; do rm $f; done
     If file is "foo bar.txt" — broken
   ✓ Quote: rm "$f"

3. ✗ Parsing ls output
   → for f in $(ls *.log); do ...
   ✓ Use globs: for f in *.log; do ...

4. ✗ Not setting set -e
   → script continues after errors
   ✓ Always: set -euo pipefail

5. ✗ Forgetting permissions on private keys
   ✓ chmod 600 .ssh/id_rsa

6. ✗ Running everything as root
   ✓ Use sudo selectively
   ✓ Production services run as dedicated user (deploy, app)

7. ✗ Editing files on prod with vim
   → forget to save, edit wrong line, no version control
   ✓ Edit in git, deploy via CI/CD

8. ✗ Tail -f without follow-by-name
   → log rotates, tail keeps watching deleted file
   ✓ tail -F (capital F)
```

---

## Cheat Sheet — Daily Backend Use

```
# Logs
tail -F /var/log/app.log
journalctl -u myapp -f
grep ERROR /var/log/app.log | tail -50

# Processes
ps aux | grep python
top
htop
pgrep -f gunicorn
sudo systemctl status myapp

# Disk
df -h
du -sh /var/log/*
ncdu /        # interactive disk usage

# Memory
free -h
vmstat 1

# Network
ss -tlnp
curl -v https://api.example.com/health
dig example.com

# Git quick
git status
git log --oneline -10
git diff
git stash; git pull; git stash pop

# Service
sudo systemctl restart nginx
sudo systemctl reload myapp     # SIGHUP, no downtime

# SSH
ssh prod
ssh prod 'tail -100 /var/log/app.log'
scp local.txt prod:/tmp/

# Find + clean
find / -size +1G 2>/dev/null
find /var/log -mtime +30 -delete
```

---

## Interview Questions

### Q1: Difference between `>` and `>>`?

`>` overwrites the file; `>>` appends. Both redirect stdout. Pair with `2>&1` to also capture stderr.

### Q2: Diff between `kill -9` and `kill -15`?

`kill -15` = SIGTERM = graceful shutdown (program can clean up). `kill -9` = SIGKILL = force (kernel kills it immediately, no chance to flush buffers or clean state). Always try `-15` first.

### Q3: Find lines in file1 NOT in file2?

```bash
comm -23 <(sort file1) <(sort file2)
# OR
grep -vxFf file2 file1
```

### Q4: Run command every 5 seconds?

```bash
watch -n 5 'ps aux | grep python'

# Or cron (every minute minimum)
* * * * * /opt/script.sh
```

### Q5: Why is `lsof -i :8000` useful?

Shows the process listening on port 8000. Standard "what's using my port" debug.

### Q6: How does `&&` differ from `;`?

```bash
cmd1 && cmd2    # run cmd2 ONLY if cmd1 succeeded
cmd1 ; cmd2     # run cmd2 regardless
cmd1 || cmd2    # run cmd2 ONLY if cmd1 failed
```

### Q7: How does `chmod 755` differ from `chmod 644`?

```
755 = rwxr-xr-x  (executable script: owner can edit, all can run)
644 = rw-r--r--  (config file: owner can edit, all can read)
```

---

## Resources

```
✓ man <command>                          # always-available reference
✓ tldr <command>                          # human-friendly examples (install tldr)
✓ https://explainshell.com — paste any command
✓ "The Linux Command Line" by William Shotts (free PDF)
✓ "Learn Bash the Hard Way" — Ian Miell
```

---

## Senior Mantras

```
1. Always `set -euo pipefail` in scripts.

2. Quote your variables. Always: "$x" not $x.

3. Test scripts on staging before prod.

4. Production services run as dedicated users, never root.

5. Log everything. Logs > guesswork.

6. Use systemd or supervisord for daemons. Not nohup hacks.

7. Backup before destructive operations.

8. Read `man` pages. They're underrated.

9. Bash is for glue scripts. Past 100 lines → use Python.

10. Permissions matter. 600 for secrets, 755 for scripts.
```

---

## Related

- [02_os_concepts.md](02_os_concepts.md) — what's under Bash
- [03_networking_fundamentals.md](03_networking_fundamentals.md) — packet flow
- [04_git_workflows.md](04_git_workflows.md) — version control
- [../01_Year3-4_Mid/04_DevOps/](../../01_Year3-4_Mid/04_DevOps) — production usage
