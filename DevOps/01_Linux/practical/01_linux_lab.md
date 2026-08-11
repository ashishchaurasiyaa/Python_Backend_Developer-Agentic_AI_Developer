# Linux — Hands-On Lab
**DevOps Track · Phase 1 Practical**

> One file, seven labs — one per theory file (01 through 07).
> Do them in order; later labs build on earlier ones.

---

## Prerequisites

You need a real Linux shell — not just reading, actually typing and seeing what breaks.

- **Best**: free-tier AWS/GCP/Oracle Cloud VM (Ubuntu 22.04/24.04)
- **No cloud**: WSL2 on Windows (`wsl --install`), or `docker run -it --name linuxlab ubuntu:24.04 bash`
- **macOS**: close enough for Labs 1–3 and 5–6 (BSD tool differences called out). Lab 7 (systemd) needs real Linux — use [Killercoda](https://killercoda.com/) for free browser-based Linux.
- `sudo` access assumed throughout.

```bash
# Work here — easy to nuke and restart:
mkdir -p ~/linux-lab && cd ~/linux-lab
```

---

## Lab 1 — Linux Basics: Permissions, Users, Groups, Env Vars

**Theory file:** `01_linux_basics.md`

**Objective:** Build muscle memory around the concepts that break the most deploys — file permissions, user/group management, environment variable scope, and shell hardening.

---

### Part A — Permissions

**Task:**

1. Create a script `deploy.sh` with `echo '#!/usr/bin/env bash' > deploy.sh && echo 'echo deploying...' >> deploy.sh`. Try to run it with `./deploy.sh`. Note the exact error.
2. Fix it: executable by owner only, nothing for group or others. Verify with `ls -l`.
3. Create `secrets.env` and set it so ONLY the owner can read and write — no group, no others.
4. Create a directory `app-data/`. Set the sticky bit on it. Then check what the `t` bit looks like in `ls -la`. Explain in one line what it prevents.
5. Calculate in your head: what octal number gives `rwxr-x---`? Then verify with `stat -c "%a" deploy.sh` (or `stat -f "%Lp" deploy.sh` on macOS).

<details>
<summary>Solution / walkthrough</summary>

```bash
# 1. Permission denied — no execute bit
echo '#!/usr/bin/env bash' > deploy.sh
echo 'echo deploying...' >> deploy.sh
./deploy.sh
# bash: ./deploy.sh: Permission denied

# 2. Owner-only execute
chmod 700 deploy.sh
ls -l deploy.sh
# -rwx------ 1 you you ... deploy.sh
./deploy.sh       # now works

# 3. Secrets file — owner read/write only
touch secrets.env
chmod 600 secrets.env
ls -l secrets.env
# -rw------- 1 you you ... secrets.env

# 4. Sticky bit on a directory
mkdir app-data
chmod +t app-data
ls -la | grep app-data
# drwxrwxrwt  ← the 't' at the end
# Prevents: users from deleting files they don't own (classic /tmp behavior)

# 5. Mental calculation: rwxr-x--- = 4+2+1 | 4+0+1 | 0+0+0 = 750
stat -c "%a" deploy.sh      # Linux
# stat -f "%Lp" deploy.sh   # macOS
# 700 (we set it above — now do chmod 750 to test 750)
chmod 750 deploy.sh
stat -c "%a" deploy.sh
# 750
```

**Insight:** `600` for secrets, `700` for scripts only you run, `750` when a group also needs to execute, `755` for scripts that anyone reads/runs. These four cover 90% of real deploy scenarios.
</details>

---

### Part B — Users and Groups

**Task:**

1. Create a user `deploy` (with home directory) and a group `appteam`.
2. Add `deploy` to `appteam` using the safe append flag. Then check: what does `id deploy` show?
3. Run `sudo usermod -G nobody deploy` (without `-a`). Now run `id deploy` again. What happened to the `appteam` membership? Fix it.
4. As yourself, try to `su - deploy` and list what groups it has. Then exit back.
5. Look at `/etc/passwd` for the `deploy` entry and decode each `:` delimited field.

<details>
<summary>Solution / walkthrough</summary>

```bash
# 1. Create user + group
sudo useradd -m deploy
sudo groupadd appteam

# 2. Safe append
sudo usermod -aG appteam deploy
id deploy
# uid=1001(deploy) gid=1001(deploy) groups=1001(deploy),1002(appteam)

# 3. The footgun — -G without -a REPLACES all supplementary groups
sudo usermod -G nobody deploy
id deploy
# groups now shows only nobody — appteam is GONE silently
# Fix:
sudo usermod -aG appteam deploy
id deploy
# appteam is back

# 4. Switch to deploy
sudo su - deploy
id        # confirm groups from deploy's perspective
exit

# 5. Decode /etc/passwd
grep ^deploy /etc/passwd
# deploy:x:1001:1001::/home/deploy:/bin/bash
#   1     2  3    4  5      6         7
# 1=username, 2=password placeholder (x = in /etc/shadow)
# 3=UID, 4=GID (primary group), 5=comment/GECOS, 6=home, 7=shell
```

**Why `-aG` is critical:** removing someone from the `docker` or `sudo` group by forgetting `-a` is a classic silent production incident — the user loses access and no error is shown.
</details>

---

### Part C — Environment Variables and Shell Scope

**Task:**

1. Set a variable `MY_SECRET=hello` WITHOUT export. Open a subshell with `bash`. Check if `MY_SECRET` is visible there. Exit the subshell. Now `export MY_SECRET=hello` and repeat.
2. Create a script `printenv_test.sh` that just runs `echo "MY_SECRET=$MY_SECRET"`. Run it — can it see the variable? Explain why or why not.
3. Demonstrate the cron PATH problem: create a script that runs `which python3` and saves the output to `/tmp/python_path.txt`. Run it with `bash ./script.sh`. Then simulate cron's restricted PATH by running it as: `env -i PATH=/usr/bin:/bin bash ./script.sh`. Compare outputs.
4. Set `MY_SECRET` permanently for your user: add `export MY_SECRET=hello` to `~/.bashrc`, source it, and verify it persists in a new shell.

<details>
<summary>Solution / walkthrough</summary>

```bash
# 1. Without export: NOT inherited by subshells
MY_SECRET=hello
bash -c 'echo "visible: $MY_SECRET"'
# visible:                        ← empty, not visible

export MY_SECRET=hello
bash -c 'echo "visible: $MY_SECRET"'
# visible: hello                  ← now inherited

# 2. Script can see exported variables
cat > printenv_test.sh << 'EOF'
#!/usr/bin/env bash
echo "MY_SECRET=$MY_SECRET"
EOF
chmod +x printenv_test.sh
./printenv_test.sh
# MY_SECRET=hello
# Why: the script runs in a child process forked from your shell.
# export makes the variable part of the process environment,
# which is inherited by all children via fork().

# 3. Cron PATH problem
cat > which_python.sh << 'EOF'
#!/usr/bin/env bash
which python3 > /tmp/python_path.txt 2>&1
echo "PATH was: $PATH" >> /tmp/python_path.txt
EOF
chmod +x which_python.sh

bash ./which_python.sh
cat /tmp/python_path.txt
# /usr/bin/python3
# PATH was: /usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:...  (full path)

env -i PATH=/usr/bin:/bin bash ./which_python.sh
cat /tmp/python_path.txt
# /usr/bin/python3         (found because /usr/bin is in the restricted PATH)
# But if python3 were in /usr/local/bin:
env -i PATH=/usr/bin:/bin bash ./which_python.sh
# no output or "not found" — cron would silently fail

# Rule: always use FULL paths in cron jobs or set PATH= at the top of the script

# 4. Permanent variable
echo 'export MY_SECRET=hello' >> ~/.bashrc
source ~/.bashrc
echo $MY_SECRET    # hello
# New shell also has it because .bashrc is sourced at interactive shell startup
```
</details>

---

## Lab 2 — Essential Commands: grep, awk, sed, find, Pipes

**Theory file:** `02_essential_commands.md`

**Objective:** Chain commands the way you would during an actual production incident. The shape `grep | awk | sort | uniq -c | sort -rn` is more valuable than any single command.

---

### Setup

```bash
cd ~/linux-lab
mkdir -p lab2 && cd lab2

# Generate a realistic nginx-style access log
cat > access.log << 'EOF'
10.0.0.5 - - [25/Jul/2026:10:01:02 +0000] "GET /api/orders HTTP/1.1" 200 512
10.0.0.7 - - [25/Jul/2026:10:01:05 +0000] "GET /api/orders HTTP/1.1" 500 128
10.0.0.5 - - [25/Jul/2026:10:01:07 +0000] "POST /api/users HTTP/1.1" 201 256
10.0.0.9 - - [25/Jul/2026:10:02:00 +0000] "GET /api/orders HTTP/1.1" 500 128
10.0.0.5 - - [25/Jul/2026:10:02:11 +0000] "GET /health HTTP/1.1" 200 32
10.0.0.7 - - [25/Jul/2026:10:03:22 +0000] "GET /api/orders HTTP/1.1" 500 128
10.0.0.3 - - [25/Jul/2026:10:03:40 +0000] "DELETE /api/orders/9 HTTP/1.1" 403 64
10.0.0.5 - - [25/Jul/2026:10:04:01 +0000] "GET /api/orders HTTP/1.1" 200 512
10.0.0.9 - - [25/Jul/2026:10:04:15 +0000] "GET /api/orders HTTP/1.1" 500 128
10.0.0.7 - - [25/Jul/2026:10:05:01 +0000] "POST /api/orders HTTP/1.1" 500 128
10.0.0.5 - - [25/Jul/2026:10:05:22 +0000] "GET /api/users/42 HTTP/1.1" 200 1024
10.0.0.3 - - [25/Jul/2026:10:06:01 +0000] "GET /api/orders HTTP/1.1" 200 512
EOF

# Also create a config file for sed exercises
cat > app.conf << 'EOF'
debug=true
port=8080
database_url=postgres://localhost/dev
log_level=DEBUG
workers=2
EOF
```

---

### Part A — grep and pipes

**Task:**

1. Count how many `500` status-code lines exist.
2. Show ALL 500-error lines with their line numbers.
3. Find every line that does NOT contain `200` or `201` (non-success responses).
4. List each unique status code and how many times it occurs — sorted most to least.
5. Which IP has the most 500 errors? One pipeline, one answer.

<details>
<summary>Solution</summary>

```bash
# 1. Count 500s
grep -c " 500 " access.log
# 5

# 2. With line numbers
grep -n " 500 " access.log

# 3. Non-success lines (not 200 or 201)
grep -vE " 20[01] " access.log

# 4. Status code frequency
awk '{print $9}' access.log | sort | uniq -c | sort -rn
#    5 500
#    4 200
#    1 403
#    1 201

# 5. IP with most 500s
grep " 500 " access.log | awk '{print $1}' | sort | uniq -c | sort -rn | head -1
#    3 10.0.0.7
```
</details>

---

### Part B — awk for structured extraction

**Task:**

1. Extract ONLY the request paths from the log (e.g. `/api/orders`). Print each unique path with a count.
2. Print the average response size (last field) across ALL requests.
3. Print only lines where the response size is greater than 200 bytes.
4. Add a running total column: print line number, IP, and cumulative bytes transferred.

<details>
<summary>Solution</summary>

```bash
# 1. Unique paths with counts
# The request is inside quotes: "GET /api/orders HTTP/1.1"
# -F'"' splits on double-quote, field 2 = the request string
awk -F'"' '{print $2}' access.log | awk '{print $2}' | sort | uniq -c | sort -rn
#    7 /api/orders
#    2 /api/users
#    ...

# 2. Average response size (last field = $NF)
awk '{sum += $NF; count++} END {printf "avg bytes: %.0f\n", sum/count}' access.log

# 3. Lines where response size > 200
awk '$NF > 200' access.log

# 4. Running total
awk '{total += $NF; print NR, $1, total}' access.log
```
</details>

---

### Part C — sed for config editing

**Task:**

1. Change `debug=true` to `debug=false` in `app.conf` **in-place**, then verify.
2. Change `log_level=DEBUG` to `log_level=INFO` without touching the file (just print the result).
3. Delete any line containing `localhost`.
4. Prepend `# MANAGED BY ANSIBLE` as the very first line of the file.

<details>
<summary>Solution</summary>

```bash
# 1. In-place edit (Linux: sed -i, macOS: sed -i '')
sed -i 's/debug=true/debug=false/' app.conf
grep debug app.conf
# debug=false

# 2. Print modified without touching file
sed 's/log_level=DEBUG/log_level=INFO/' app.conf

# 3. Delete lines containing localhost
sed '/localhost/d' app.conf

# 4. Prepend a line
sed -i '1i # MANAGED BY ANSIBLE' app.conf
head -3 app.conf
# # MANAGED BY ANSIBLE
# debug=false
# port=8080
```
</details>

---

### Part D — find for file discovery

**Task:**

1. Find all `.log` files anywhere in `~/linux-lab` that are larger than 1KB.
2. Find all files modified in the last 10 minutes.
3. Find all files owned by root under `/etc` (just the first 5 results — use `-quit` or `head`).
4. Find all `.conf` files and print their names + sizes in one pipeline.
5. Simulate the "delete temp files older than 7 days" pattern on `~/linux-lab` (dry run first with `-print`, then actually delete with `-delete`).

<details>
<summary>Solution</summary>

```bash
# 1. .log files larger than 1KB
find ~/linux-lab -name "*.log" -size +1k

# 2. Modified in last 10 minutes
find ~/linux-lab -mmin -10

# 3. Files owned by root under /etc (first 5)
find /etc -maxdepth 2 -user root -type f 2>/dev/null | head -5

# 4. .conf files with sizes
find ~/linux-lab -name "*.conf" -exec ls -lh {} \;
# or with awk for clean output:
find ~/linux-lab -name "*.conf" -exec du -sh {} \;

# 5. Dry run first — ALWAYS do this before -delete
find ~/linux-lab -name "*.log" -mtime +7 -print
# If output looks right, then delete:
find ~/linux-lab -name "*.log" -mtime +7 -delete
```

**Golden rule:** always `find ... -print` before `find ... -delete`. One wrong path can cascade into deleting the wrong files.
</details>

---

## Lab 3 — File Compression: tar, gzip, xz, zstd

**Theory file:** `03_file_compression.md`

**Objective:** Build, verify, and extract archives the way CI pipelines and deployment scripts actually use them. Understand when to choose gzip vs xz vs zstd.

---

### Setup

```bash
cd ~/linux-lab
mkdir -p lab3/app/{src,config,logs} && cd lab3

# Fake app files
echo 'print("hello")' > app/src/main.py
echo 'print("worker")' > app/src/worker.py
echo 'DEBUG=true\nDB_URL=postgres://localhost/dev' > app/config/.env
# Create a fake large log
dd if=/dev/urandom bs=1M count=5 | base64 > app/logs/app.log 2>/dev/null
echo "Generated fake files:"
du -sh app/
```

---

### Part A — tar fundamentals

**Task:**

1. Create a tar archive `app-backup.tar` (no compression) of the `app/` directory. Verify its size.
2. List the contents of the archive without extracting.
3. Extract it into a new directory `restored/` (not back into the original location).
4. Extract ONLY the file `app/config/.env` from the archive into `/tmp/`.
5. Show what `t`, `c`, `x`, `f`, `v`, `z` each mean — add them as comments in your commands.

<details>
<summary>Solution</summary>

```bash
# 1. Create tar (no compression)
tar -cvf app-backup.tar app/
# c=create, v=verbose, f=filename
ls -lh app-backup.tar

# 2. List without extracting
tar -tvf app-backup.tar
# t=list, v=verbose, f=filename

# 3. Extract into a different directory
mkdir restored
tar -xvf app-backup.tar -C restored/
# x=extract, v=verbose, f=filename, -C=change to this dir first
ls restored/app/

# 4. Extract a single file to /tmp/
tar -xvf app-backup.tar -C /tmp/ app/config/.env
cat /tmp/app/config/.env

# 5. Flag reference (already above but summarised):
# c = create new archive
# x = extract
# t = list (table of contents)
# v = verbose (print filenames as processed)
# f = next argument is the filename
# z = filter through gzip
# j = filter through bzip2
# J = filter through xz
# C = change to directory before operation
```
</details>

---

### Part B — compression algorithms

**Task:**

1. Compress `app-backup.tar` with each of these (run one at a time, note file size and rough time):
   - `gzip`  → `app-backup.tar.gz`
   - `xz`    → `app-backup.tar.xz`
   - `zstd`  → `app-backup.tar.zst` (install if needed: `sudo apt install zstd`)
2. Compare sizes with `ls -lh app-backup.tar*`.
3. Do all three in one go using `tar` flags directly (not piping separately) — `tar -czf`, `tar -cJf`, and `tar -c --zstd -f`.
4. Decompress the gzip one and verify the files are intact with `diff -r restored/app app/`.

<details>
<summary>Solution</summary>

```bash
# 1. Compress separately
gzip -k app-backup.tar          # -k = keep original
xz -k app-backup.tar
zstd app-backup.tar -o app-backup.tar.zst

# 2. Compare sizes
ls -lh app-backup.tar*
# .tar     ~5MB   (no compression)
# .tar.gz  ~5MB   (random/base64 data doesn't compress much, but with real text/code it's ~70% smaller)
# .tar.xz  ~5MB   (same issue with random data)
# .tar.zst ~5MB

# 3. All in one with tar flags
tar -czf app-v2.tar.gz app/            # gzip
tar -cJf app-v2.tar.xz app/            # xz (capital J)
tar -c --zstd -f app-v2.tar.zst app/   # zstd

# 4. Verify integrity
mkdir restored2
tar -xzf app-v2.tar.gz -C restored2/
diff -r restored2/app app/
# No output = files are identical
echo "Archive integrity: OK"
```

**When to choose:**
- `gzip` → CI pipelines, log archival — fast, universal
- `xz` → distributing software packages — best compression ratio
- `zstd` → anything where you need speed + good compression (backups, streaming to S3)
</details>

---

### Part C — CI/CD artifact pattern

**Task:**

This simulates a real CI pipeline: build → archive → transfer → deploy.

1. Create a `dist/` directory with some "built" files.
2. Create a versioned archive: `app-v1.2.3-$(date +%Y%m%d).tar.gz`.
3. Verify it contains exactly what you expect before "uploading" it.
4. Simulate extraction on the "remote server" using `--strip-components=1` to peel off the top-level directory.
5. Create a checksum file `app-v1.2.3.tar.gz.sha256` and then verify it.

<details>
<summary>Solution</summary>

```bash
mkdir dist
echo 'compiled binary' > dist/myapp
echo 'v1.2.3' > dist/VERSION
cp app/config/.env dist/

# 2. Versioned archive
ARCHIVE="app-v1.2.3-$(date +%Y%m%d).tar.gz"
tar -czf "$ARCHIVE" dist/
echo "Created: $ARCHIVE"

# 3. Verify contents before deploying
tar -tzf "$ARCHIVE"

# 4. Deploy with --strip-components
mkdir /tmp/deploy-test
tar -xzf "$ARCHIVE" -C /tmp/deploy-test --strip-components=1
# --strip-components=1 removes the top "dist/" prefix
ls /tmp/deploy-test
# myapp  VERSION  .env  (no wrapping dist/ directory)

# 5. Checksum
sha256sum "$ARCHIVE" > "${ARCHIVE}.sha256"
cat "${ARCHIVE}.sha256"
# Then verify:
sha256sum -c "${ARCHIVE}.sha256"
# app-v1.2.3-20260811.tar.gz: OK
```
</details>

---

## Lab 4 — Process Management: ps, signals, job control, nice

**Theory file:** `04_process_management.md`

**Objective:** Inspect, prioritize, and kill processes the way you would during a production CPU or memory incident. Build the SIGTERM→wait→SIGKILL muscle memory.

---

### Part A — Inspecting processes

**Task:**

1. Run `sleep 300 &` three times. Find all three PIDs using `pgrep`.
2. For one of the PIDs, look in `/proc/<pid>/` — read its exact command, its state, and count how many file descriptors it has open.
3. Use `ps aux --sort=-%cpu | head -5` and separately `top -b -n 1 | head -20` — compare what each shows.
4. Find your own shell's PID and its parent PID. What is the parent? (Hint: `ps -p $$ -o pid,ppid,comm`)

<details>
<summary>Solution</summary>

```bash
# 1. Start three sleeps and find them
sleep 300 &
sleep 300 &
sleep 300 &
pgrep -a sleep           # PIDs + command lines
# 12345 sleep 300
# 12346 sleep 300
# 12347 sleep 300
jobs -l                   # job table with PIDs

# 2. /proc deep dive
PID=12345
cat /proc/$PID/cmdline | tr '\0' '\n'   # exact command
cat /proc/$PID/status | grep -E "^Name|^State|^Pid|^PPid"
ls /proc/$PID/fd | wc -l                # number of open file descriptors
# sleep holds 3 FDs: 0 (stdin), 1 (stdout), 2 (stderr)

# 3. Compare ps and top
ps aux --sort=-%cpu | head -5           # static snapshot, sorted
top -b -n 1 | head -20                  # single iteration of top in batch mode

# 4. Shell PID and parent
echo "My shell PID: $$"
ps -p $$ -o pid,ppid,comm
# PID   PPID  COMM
# 1201  1200  bash     ← parent 1200 is the SSH session's sshd process
```
</details>

---

### Part B — Signals

**Task:**

1. Start `yes > /dev/null &` (pins one CPU at 100%). Confirm it with `ps aux --sort=-%cpu | head -3`.
2. Send it SIGTERM. Check if it died with `kill -0 <pid>`. If alive, send SIGKILL.
3. Start it again. This time use `kill -STOP` to pause it, verify its state changes in `ps`, then resume it with `kill -CONT`.
4. Start a process, note its PID. Delete it from the process table perspective using the full graceful escalation pattern from the theory file — as a function you can reuse.

<details>
<summary>Solution</summary>

```bash
# 1. Start and confirm CPU hog
yes > /dev/null &
HOG=$!
sleep 1
ps aux --sort=-%cpu | head -3    # should show 'yes' near top

# 2. Graceful kill
kill $HOG                           # SIGTERM
sleep 3
if kill -0 $HOG 2>/dev/null; then
    echo "Still alive — escalating to SIGKILL"
    kill -9 $HOG
else
    echo "Exited cleanly on SIGTERM"
fi

# 3. STOP / CONT
yes > /dev/null &
HOG=$!
kill -STOP $HOG                     # pause it
ps aux | grep "yes" | grep -v grep  # STAT should show T (stopped)
kill -CONT $HOG                      # resume it
ps aux | grep "yes" | grep -v grep  # STAT back to R or S
kill $HOG                            # clean up

# 4. Reusable graceful kill function
graceful_kill() {
    local pid=$1
    local timeout=${2:-10}
    echo "Sending SIGTERM to PID $pid..."
    kill "$pid" 2>/dev/null || { echo "PID $pid not found"; return 0; }
    local waited=0
    while kill -0 "$pid" 2>/dev/null; do
        sleep 1
        waited=$((waited + 1))
        if [ "$waited" -ge "$timeout" ]; then
            echo "Still alive after ${timeout}s — sending SIGKILL"
            kill -9 "$pid" 2>/dev/null
            return
        fi
    done
    echo "PID $pid exited cleanly"
}

yes > /dev/null &
graceful_kill $!
```
</details>

---

### Part C — Job control and nohup

**Task:**

1. Start `sleep 500`, then suspend it with Ctrl+Z. List jobs. Resume it in the background. Bring it to the foreground. Then kill it.
2. Start a loop that writes to a file every 2 seconds with `while true; do date >> /tmp/loop.log; sleep 2; done`. Put it in the background with `nohup`. Close and reopen your terminal (or open a new shell). Verify the loop is still running.
3. For a RUNNING background job you forgot to nohup, use `disown` to protect it from SIGHUP.

<details>
<summary>Solution</summary>

```bash
# 1. Foreground → stop → background → foreground → kill
sleep 500
# Ctrl+Z
# [1]+  Stopped   sleep 500
jobs -l             # [1]+ <PID>  Stopped  sleep 500
bg %1               # resume in background
jobs                # [1]+ Running  sleep 500 &
fg %1               # bring back to foreground
# Ctrl+C to kill

# 2. nohup loop
nohup bash -c 'while true; do date >> /tmp/loop.log; sleep 2; done' &
echo "Loop PID: $!"
# Close this terminal, open a new one:
cat /tmp/loop.log     # still growing
pgrep -f "loop.log"   # process is still there

# 3. disown for already-running job (simulate: start without nohup first)
bash -c 'while true; do date >> /tmp/disown.log; sleep 2; done' &
JOB_PID=$!
jobs -l
disown -h %1          # -h = mark immune to SIGHUP but keep in jobs table
# OR: disown %1       # remove from jobs table entirely
# Now closing the terminal won't send SIGHUP to this process

# Cleanup
kill $(pgrep -f "loop.log") 2>/dev/null
kill $(pgrep -f "disown.log") 2>/dev/null
```
</details>

---

### Part D — nice and renice

**Task:**

1. Start a CPU hog at nice value 15. Confirm the NI column in `ps -eo pid,ni,comm`.
2. Start a SECOND CPU hog at default nice (0). With `top`, observe that the default-nice process gets more CPU time.
3. Change the running nice-15 process's priority to 5 using `renice`.
4. Confirm the change and then kill both.

<details>
<summary>Solution</summary>

```bash
# 1. Start CPU hog at nice 15
nice -n 15 yes > /dev/null &
NICE_PID=$!
sleep 1
ps -eo pid,ni,comm | grep yes
# <pid>  15  yes

# 2. Second hog at default nice
yes > /dev/null &
DEFAULT_PID=$!
# In top: the nice=0 process should show higher %CPU

# 3. Renice the first process from 15 to 5
renice 5 -p $NICE_PID
ps -eo pid,ni,comm | grep yes
# NICE_PID now shows 5

# 4. Kill both
kill $NICE_PID $DEFAULT_PID
```

**Real-world use:** always nice backup/batch jobs so they don't starve your live application during the backup window.
</details>

---

## Lab 5 — Disk Management: df, du, inode, mount, truncate

**Theory file:** `05_disk_management.md`

**Objective:** Diagnose and fix disk-full scenarios. Understand the `df` vs `du` disagreement. Practice the EBS-style attach workflow.

---

### Part A — df and du drill-down

**Task:**

1. Create a bloated directory tree: `~/linux-lab/var/log/app/` with a 50MB file `huge.log` (use `dd`), several small `.log.gz` files, and a nested subdirectory with more files.
2. Use the one-level drill-down pattern to find the biggest consumer — starting from `~/linux-lab/var`, working down.
3. Find the top 3 largest files anywhere in `~/linux-lab` using `find + du`.
4. Verify your inode count on the root filesystem: `df -i /`. Then create 10,000 tiny files in a temp dir and re-check.

<details>
<summary>Solution</summary>

```bash
mkdir -p ~/linux-lab/var/log/app/archived
cd ~/linux-lab

# 50MB fake log
dd if=/dev/zero of=var/log/app/huge.log bs=1M count=50 status=progress
# Small files
touch var/log/app/old1.log.gz var/log/app/old2.log.gz
dd if=/dev/zero of=var/log/app/archived/archive1.log bs=1M count=5 status=none
dd if=/dev/zero of=var/log/app/archived/archive2.log bs=1M count=3 status=none

# 2. Drill down one level at a time
du -h --max-depth=1 var/ | sort -rh
# 58M var/log
du -h --max-depth=1 var/log/ | sort -rh
# 58M var/log/app
du -h --max-depth=1 var/log/app/ | sort -rh
# 50M var/log/app/huge.log  ← found it
# 8M  var/log/app/archived

# 3. Top 3 largest files
find ~/linux-lab -type f -exec du -h {} \; 2>/dev/null | sort -rh | head -3

# 4. Inode check
df -i /
# Before creating files
BEFORE=$(df -i / | awk 'NR==2{print $3}')

mkdir /tmp/inode_test
for i in $(seq 1 10000); do touch /tmp/inode_test/file_$i; done
AFTER=$(df -i / | awk 'NR==2{print $3}')
echo "Inodes used before: $BEFORE, after: $AFTER, diff: $((AFTER - BEFORE))"

# Cleanup
rm -rf /tmp/inode_test
```
</details>

---

### Part B — The deleted-but-open file scenario

**Task:**

1. In a subshell, open a file for writing with `tail -f huge.log &`. Note the PID.
2. Delete the file with `rm`.
3. Check with `ls`: the file is gone. But find the deleted fd in `/proc/<pid>/fd/`.
4. Free the disk blocks WITHOUT killing the process by truncating via the fd path.
5. Verify the blocks were freed — the fd still exists but the file is 0 bytes.

<details>
<summary>Solution</summary>

```bash
cd ~/linux-lab/var/log/app

# 1. Keep fd open
tail -f huge.log > /dev/null &
TAIL_PID=$!
echo "tail PID: $TAIL_PID"

# 2. Delete the filename
rm huge.log
ls -la    # huge.log is gone from directory listing

# 3. Find it in /proc
ls -la /proc/$TAIL_PID/fd/
# Should see a link with "(deleted)" — note the fd number (likely 4 or 5)
ls -la /proc/$TAIL_PID/fd/ | grep deleted
# lrwx------ ... 4 -> /home/you/linux-lab/var/log/app/huge.log (deleted)
FD_NUM=4   # replace with actual fd number from above

# 4. Truncate via the fd (frees the disk blocks immediately)
> /proc/$TAIL_PID/fd/$FD_NUM
echo "Truncated via fd — blocks freed without killing process"

# 5. Verify: the fd is now 0 bytes
ls -la /proc/$TAIL_PID/fd/$FD_NUM
# The link size won't show 0 (it's a link), but the underlying file is now 0 bytes
# The tail process still runs without error — it just reads from an empty file now

# Real check: cat through the deleted fd
wc -c /proc/$TAIL_PID/fd/$FD_NUM
# 0

# Cleanup
kill $TAIL_PID
```

**The key insight:** `df` (kernel block view) and `du` (directory walk) disagree exactly when deleted-but-open files exist. The `> /proc/<pid>/fd/<n>` trick is the escape hatch when you can't restart the process.
</details>

---

### Part C — truncate vs rm

**Task:**

1. Create a 20MB file `active.log`. Open it with `tail -f active.log &` (keep fd open).
2. Try `rm active.log`. Check if disk space is freed (conceptually — or use `lsof +L1` to confirm it's still held).
3. Restart: recreate the file. This time use `truncate -s 0 active.log`. Check the file still exists at 0 bytes AND the tail process still runs without error.
4. Explain the difference in one sentence.

<details>
<summary>Solution</summary>

```bash
cd ~/linux-lab

# 1. Create and open file
dd if=/dev/zero of=active.log bs=1M count=20 status=none
tail -f active.log > /dev/null &
TAIL_PID=$!

# 2. rm — removes the name, but blocks held until process closes fd
rm active.log
lsof +L1 2>/dev/null | grep active
# Still shows process holding the fd — blocks NOT freed yet

# 3. Recreate and truncate instead
dd if=/dev/zero of=active.log bs=1M count=20 status=none
truncate -s 0 active.log
ls -lh active.log
# -rw-r--r-- 1 you you 0 ... active.log    ← still exists, 0 bytes
# Process is still running fine — same fd, now reading from empty file

# 4. In one sentence:
# rm removes the directory entry (the name); truncate zeroes the content
# in-place — making truncate the right choice when a live process has the file open.

kill $TAIL_PID
```
</details>

---

## Lab 6 — Networking: curl, ss, nc, SSH, rsync

**Theory file:** `06_networking_commands.md`

**Objective:** Triage network connectivity at every layer. Know the difference between "connection refused" and "connection timed out". Diagnose ports, write API health checks, and set up SSH key auth.

---

### Part A — curl as a debugging tool

**Task:**

1. Make a request to `https://httpbin.org/get` and print only the HTTP status code (silent, no body).
2. Measure the response time breakdown (dns, connect, TLS, TTFB, total) using `-w`.
3. POST JSON `{"name": "test"}` to `https://httpbin.org/post` with correct Content-Type header. Pretty-print the JSON response.
4. Simulate what a deploy health-check script does: loop until `https://httpbin.org/status/200` returns 200.
5. Use `curl -I` vs `curl -v` on the same URL — explain what each shows that the other doesn't.

<details>
<summary>Solution</summary>

```bash
# 1. Status code only
curl -s -o /dev/null -w "%{http_code}\n" https://httpbin.org/get
# 200

# 2. Timing breakdown
curl -w "dns:%{time_namelookup}s  connect:%{time_connect}s  tls:%{time_appconnect}s  ttfb:%{time_starttransfer}s  total:%{time_total}s\n" \
     -o /dev/null -s https://httpbin.org/get

# 3. POST JSON
curl -s -X POST https://httpbin.org/post \
     -H "Content-Type: application/json" \
     -d '{"name":"test"}' | python3 -m json.tool
# or: | jq .   (if jq installed)

# 4. Health check loop
echo "Testing health check loop..."
until curl -sf https://httpbin.org/status/200 -o /dev/null; do
    echo "  not ready, retrying..."
    sleep 2
done
echo "Service is up!"

# 5. -I vs -v
curl -I https://httpbin.org/get        # headers only (HEAD request), fast
curl -v https://httpbin.org/get 2>&1 | head -30  # full request + response + TLS handshake
# -I: just the response headers, no body, no request detail
# -v: full debug view — shows your request headers, server's response headers,
#     AND the TLS handshake details (useful for cert debugging)
```
</details>

---

### Part B — Port inspection with ss and nc

**Task:**

1. List all TCP sockets currently in LISTEN state with the process name. Count them.
2. Find if anything is listening on port 22 (SSH). What is it?
3. Use `nc -zv` to test if port 443 is reachable on `google.com`.
4. Use the pure-bash TCP test (no nc/curl) to check if port 80 is open on `example.com`.
5. Count the number of ESTABLISHED TCP connections on your machine.

<details>
<summary>Solution</summary>

```bash
# 1. All listening TCP sockets
ss -tlnp
ss -tlnp | grep -c LISTEN    # count

# 2. What's on port 22
ss -tlnp | grep :22
# LISTEN  0  128  0.0.0.0:22  ...  users:(("sshd",pid=892,...))

# 3. nc port test
nc -zv google.com 443 2>&1
# Connection to google.com 443 port [tcp/https] succeeded!

# 4. Pure bash TCP test (no tools needed)
timeout 3 bash -c 'echo > /dev/tcp/example.com/80' 2>/dev/null \
    && echo "port 80 is OPEN" || echo "port 80 is CLOSED or TIMEOUT"

# 5. Count established connections
ss -tn state established | tail -n +2 | wc -l
```
</details>

---

### Part C — SSH key auth setup

**Task:**

1. Generate an ed25519 key pair with a comment containing your username.
2. Show the difference in permissions between the private key, the public key, and the `~/.ssh` directory itself. Why does each permission matter?
3. Add the public key to `~/.ssh/authorized_keys` manually (without `ssh-copy-id`) and set correct permissions.
4. Create a `~/.ssh/config` entry for a host alias `devbox` pointing to `localhost` on port 22 using your new key.
5. Verify the config works: `ssh devbox whoami` (will connect to localhost).

<details>
<summary>Solution</summary>

```bash
# 1. Generate key pair
ssh-keygen -t ed25519 -C "$(whoami)@$(hostname)" -f ~/.ssh/lab_key -N ""
# -N "" = no passphrase (for lab only — use a passphrase in production)
ls -la ~/.ssh/lab_key*
# -rw------- lab_key       ← private: owner-only, would be STOLEN if group/others read it
# -rw-r--r-- lab_key.pub   ← public: safe to share

# 2. Permission breakdown
ls -la ~/.ssh/
# drwx------ .ssh/         ← 700: only owner can list/enter; if group-readable, SSH refuses to use keys
# -rw------- authorized_keys  ← 600: if world-readable, SSH refuses the file
# -rw------- id_ed25519       ← 600: private key MUST be owner-only
# SSH strictly checks these — it will refuse with "bad permissions" otherwise

# 3. Manual authorized_keys setup
mkdir -p ~/.ssh
chmod 700 ~/.ssh
cat ~/.ssh/lab_key.pub >> ~/.ssh/authorized_keys
chmod 600 ~/.ssh/authorized_keys

# 4. SSH config
cat >> ~/.ssh/config << 'EOF'

Host devbox
    HostName localhost
    User YOUR_USERNAME_HERE
    IdentityFile ~/.ssh/lab_key
    Port 22
EOF
chmod 600 ~/.ssh/config

# Replace YOUR_USERNAME_HERE:
sed -i "s/YOUR_USERNAME_HERE/$(whoami)/" ~/.ssh/config

# 5. Test
ssh devbox whoami
# Should print your username with no password prompt
```
</details>

---

### Part D — rsync for deploy and backup

**Task:**

1. Create `~/linux-lab/src/` with several files. rsync it to `~/linux-lab/dst/` locally.
2. Add a new file to `src/`, delete one, and run rsync again with `--delete`. Verify `dst/` mirrors `src/` exactly.
3. Do a `--dry-run` first, then the real sync. Make it a habit.
4. Exclude `.env` files and `*.log` files from the sync.
5. Calculate the rsync "delta" benefit: sync once (full transfer), modify ONE byte in one file, sync again. Compare bytes transferred (use `-v --stats`).

<details>
<summary>Solution</summary>

```bash
mkdir -p ~/linux-lab/src ~/linux-lab/dst

# Create source files
echo "app v1" > ~/linux-lab/src/app.py
echo "config" > ~/linux-lab/src/settings.py
echo "secret" > ~/linux-lab/src/prod.env
echo "errors" > ~/linux-lab/src/error.log

# 1. First rsync
rsync -avz ~/linux-lab/src/ ~/linux-lab/dst/
ls ~/linux-lab/dst/

# 2. Modify src then mirror with --delete
echo "new file" > ~/linux-lab/src/utils.py
rm ~/linux-lab/src/settings.py

# Dry run first:
rsync -avz --delete --dry-run ~/linux-lab/src/ ~/linux-lab/dst/
# See: "deleting settings.py" and "utils.py" in output
# Then for real:
rsync -avz --delete ~/linux-lab/src/ ~/linux-lab/dst/
diff <(ls ~/linux-lab/src/) <(ls ~/linux-lab/dst/)  # should be empty (identical)

# 3. --dry-run is a habit for any --delete sync

# 4. Exclude .env and .log
rsync -avz --delete \
      --exclude='*.env' \
      --exclude='*.log' \
      ~/linux-lab/src/ ~/linux-lab/dst-clean/
ls ~/linux-lab/dst-clean/    # no .env or .log files

# 5. Delta transfer proof
rsync -avz --stats ~/linux-lab/src/ ~/linux-lab/dst/ 2>&1 | grep "bytes"
# Total transferred file size: X bytes  ← first run = everything

# Modify one byte in one file
echo "app v2" > ~/linux-lab/src/app.py
rsync -avz --stats ~/linux-lab/src/ ~/linux-lab/dst/ 2>&1 | grep "bytes"
# Total transferred file size: Y bytes  ← only the changed file (much smaller)
```
</details>

---

## Lab 7 — Services & systemd: unit files, journalctl, timers

**Theory file:** `07_services_systemd.md`

**Objective:** Write, run, and debug a real systemd service. Watch it self-heal. Use journalctl the way you would during an incident. Build a timer.

> **Note:** this lab needs a real systemd-based Linux box. Use Killercoda if you only have macOS or plain Docker.

---

### Part A — Write and run a service

**Task:**

1. Write a minimal Python/bash HTTP server as a service. Use `python3 -m http.server 9999` as the ExecStart (a real app substitute).
2. Write the unit file with: `User=nobody`, `Restart=always`, `RestartSec=5`, `StandardOutput=journal`, `LimitNOFILE=4096`.
3. Run `daemon-reload`, then `enable --now`. Confirm it's running with `status`.
4. Hit it with `curl http://localhost:9999` to prove it works.
5. Edit the unit file to change the port to 9998. Apply the change correctly (daemon-reload + restart). Verify the new port is listening.

<details>
<summary>Solution</summary>

```bash
# 1 & 2. Write the unit file
sudo tee /etc/systemd/system/lab-httpserver.service > /dev/null << 'EOF'
[Unit]
Description=Lab HTTP Server (python3 -m http.server)
After=network.target

[Service]
Type=simple
User=nobody
WorkingDirectory=/tmp
ExecStart=/usr/bin/python3 -m http.server 9999
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal
SyslogIdentifier=lab-httpserver
LimitNOFILE=4096

[Install]
WantedBy=multi-user.target
EOF

# 3. Apply and start
sudo systemctl daemon-reload
sudo systemctl enable --now lab-httpserver
systemctl status lab-httpserver
# Should show: active (running)

# 4. Test it works
curl -s http://localhost:9999 | head -20
# HTML directory listing of /tmp

# 5. Change port to 9998
sudo sed -i 's/http.server 9999/http.server 9998/' \
     /etc/systemd/system/lab-httpserver.service

sudo systemctl daemon-reload          # REQUIRED — without this, change is ignored
sudo systemctl restart lab-httpserver
systemctl status lab-httpserver
ss -tlnp | grep :9998                  # confirm new port is listening
curl -s http://localhost:9998 | head -5
```
</details>

---

### Part B — Observe self-healing (Restart=always)

**Task:**

1. Find the PID of the running `lab-httpserver` service using `systemctl show`.
2. Kill it with `kill -9 <pid>` (bypass SIGTERM — force crash).
3. Wait 6 seconds. Check `systemctl status` — it should have restarted with a NEW PID.
4. Read `journalctl -u lab-httpserver -n 20` — find the log lines showing the crash and the restart.
5. What happens if you crash it VERY rapidly (5 times in quick succession)? Does systemd give up?

<details>
<summary>Solution</summary>

```bash
# 1. Get current PID
MAINPID=$(systemctl show -p MainPID lab-httpserver --value)
echo "Current PID: $MAINPID"

# 2. Force crash (bypass graceful shutdown)
sudo kill -9 $MAINPID

# 3. Wait and check for restart
sleep 6
systemctl status lab-httpserver
NEW_PID=$(systemctl show -p MainPID lab-httpserver --value)
echo "New PID after restart: $NEW_PID"
# They should be different numbers

# 4. Read the restart event
journalctl -u lab-httpserver -n 20 --no-pager
# Look for:
# "Process ... killed by signal KILL"
# "Scheduled restart job"
# "Started Lab HTTP Server"

# 5. Rapid crash test
for i in 1 2 3 4 5 6; do
    PID=$(systemctl show -p MainPID lab-httpserver --value)
    sudo kill -9 $PID 2>/dev/null
    sleep 1
done
systemctl status lab-httpserver
# After 5 rapid restarts in 10s, systemd may enter "failed" state
# This is the start rate limit: StartLimitIntervalSec=10, StartLimitBurst=5
# Fix: sudo systemctl reset-failed lab-httpserver && sudo systemctl start lab-httpserver

sudo systemctl reset-failed lab-httpserver
sudo systemctl start lab-httpserver
```
</details>

---

### Part C — journalctl as your incident tool

**Task:**

1. Deliberately break the service: change `ExecStart` to a path that doesn't exist. `daemon-reload` + `restart`. Read the failure in journalctl.
2. Fix it. Use `journalctl -u lab-httpserver -p err` to confirm errors are gone.
3. Show logs from the LAST time the service successfully started (`--since`).
4. Use `journalctl -f -u lab-httpserver` in one terminal, and hit the service with curl in another — watch the logs appear live.
5. Check how much disk space the entire journal is using. Trim it to the last 2 days.

<details>
<summary>Solution</summary>

```bash
# 1. Break it deliberately
sudo sed -i 's|ExecStart=.*|ExecStart=/usr/bin/nonexistent-binary|' \
     /etc/systemd/system/lab-httpserver.service
sudo systemctl daemon-reload
sudo systemctl restart lab-httpserver
# Should fail — now read why:
journalctl -u lab-httpserver -n 30 --no-pager
# Look for: "No such file or directory" or "Exec format error"

systemctl status lab-httpserver
# Active: failed  (exit code: 203/EXEC)

# 2. Fix it
sudo sed -i 's|ExecStart=.*|ExecStart=/usr/bin/python3 -m http.server 9998|' \
     /etc/systemd/system/lab-httpserver.service
sudo systemctl daemon-reload
sudo systemctl restart lab-httpserver
journalctl -u lab-httpserver -p err --no-pager
# Should be empty now (no errors)

# 3. Logs since last successful start
START_TIME=$(systemctl show -p ActiveEnterTimestamp lab-httpserver --value)
journalctl -u lab-httpserver --since "$START_TIME" --no-pager

# 4. Live tail (run in one terminal, curl in another)
# Terminal 1:
journalctl -f -u lab-httpserver
# Terminal 2 (in a separate session):
# curl http://localhost:9998   ← watch Terminal 1 show the request

# 5. Journal disk usage
journalctl --disk-usage
# Trim to last 2 days:
sudo journalctl --vacuum-time=2d
journalctl --disk-usage   # should be smaller now
```
</details>

---

### Part D — systemd timer (cron alternative)

**Task:**

1. Write a service `lab-logger.service` that runs `date >> /tmp/lab-timer.log` (a oneshot that logs the current time).
2. Write a matching `lab-logger.timer` that triggers it every minute.
3. Enable and start the timer. Use `systemctl list-timers` to see when it will next fire.
4. Wait 2–3 minutes. Check `/tmp/lab-timer.log` — it should have 2-3 timestamps.
5. Check journalctl for the timer's run history.

<details>
<summary>Solution</summary>

```bash
# 1. The oneshot service
sudo tee /etc/systemd/system/lab-logger.service > /dev/null << 'EOF'
[Unit]
Description=Lab Logger (writes timestamp to file)

[Service]
Type=oneshot
ExecStart=/bin/bash -c 'date >> /tmp/lab-timer.log'
StandardOutput=journal
StandardError=journal
EOF

# 2. The timer
sudo tee /etc/systemd/system/lab-logger.timer > /dev/null << 'EOF'
[Unit]
Description=Run lab-logger every minute

[Timer]
OnCalendar=*:*:00
Persistent=true

[Install]
WantedBy=timers.target
EOF

# 3. Enable and start the timer (NOT the service — the timer controls it)
sudo systemctl daemon-reload
sudo systemctl enable --now lab-logger.timer
systemctl list-timers | grep lab-logger
# Shows: next run time is within the next minute

# 4. Wait and check
sleep 65
cat /tmp/lab-timer.log
# Mon Aug 11 09:01:00 UTC 2026
sleep 65
cat /tmp/lab-timer.log
# Mon Aug 11 09:01:00 UTC 2026
# Mon Aug 11 09:02:00 UTC 2026

# 5. Journal history for this timer
journalctl -u lab-logger.service --no-pager
# Shows each run with timestamp

# Cleanup
sudo systemctl disable --now lab-logger.timer
sudo systemctl stop lab-logger.service 2>/dev/null
sudo rm /etc/systemd/system/lab-logger.{service,timer}
sudo systemctl daemon-reload
```
</details>

---

### Final Cleanup

```bash
# Stop and remove all lab services
sudo systemctl disable --now lab-httpserver.service 2>/dev/null
sudo rm -f /etc/systemd/system/lab-httpserver.service
sudo systemctl daemon-reload

# Remove lab files
rm -rf ~/linux-lab
rm -f /tmp/lab-timer.log /tmp/loop.log /tmp/disown.log /tmp/deploy-test
```

---

## Self-Check Checklist

One question per theory file. If you can answer these cold (no looking), you own the material.

**File 01 — Linux Basics**
- [ ] Why does `chmod 777` on a deploy script violate least privilege, and what's the right mode for a script only the owner should run?
- [ ] What does `usermod -G appteam deploy` (no `-a`) silently do, and why is it dangerous?
- [ ] Why can a variable set in a parent shell be invisible in a child process?

**File 02 — Essential Commands**
- [ ] Write a one-liner that finds the top 5 IPs sending 500 errors from a raw nginx access log.
- [ ] What's the difference between `grep -c` and `grep | wc -l`? (They can give different answers.)
- [ ] When would you use `awk` instead of `cut`?

**File 03 — File Compression**
- [ ] What does `--strip-components=1` do in tar, and when would you need it?
- [ ] Why does `zip` instead of `tar.gz` matter for AWS Lambda deployment packages?
- [ ] When would you choose `zstd` over `gzip`?

**File 04 — Process Management**
- [ ] Walk through the graceful kill escalation pattern from memory (signal, wait, check, force).
- [ ] What's a zombie process and how do you find and fix it without rebooting?
- [ ] What does `kill -0 <pid>` do and why is it useful in scripts?

**File 05 — Disk Management**
- [ ] `df` shows 100% full but `du` can't account for all the space — what's happening and how do you fix it without restarting the process?
- [ ] Why use UUID in `/etc/fstab` instead of `/dev/sdb1`?
- [ ] When should you use `truncate -s 0` instead of `rm` on a log file?

**File 06 — Networking**
- [ ] "Connection refused" vs "connection timed out" — what does each tell you about the root cause?
- [ ] `ss -tlnp` shows `127.0.0.1:5432` instead of `0.0.0.0:5432` — is that a problem? Why?
- [ ] How would you securely access a database in a private VPC from your laptop without a VPN?

**File 07 — Services & systemd**
- [ ] What is the ONE command you must run after editing a systemd unit file, and what happens if you forget it?
- [ ] Explain `Restart=always` + `RestartSec=5` — why not just `Restart=always` with no delay?
- [ ] How does `systemctl enable` differ from `systemctl start` — and what does `enable --now` do?