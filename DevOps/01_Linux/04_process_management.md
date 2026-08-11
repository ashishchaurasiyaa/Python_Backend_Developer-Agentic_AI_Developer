# Process Management

**DevOps Track · Phase 1: Linux**

## Quick Concepts

| Concept | One-line definition |
|------------------------|----------------------------------------------------------------------|
| **Process** | A running instance of a program, identified by a PID |
| **Parent/child** | Every process (except PID 1) is spawned by a parent — identified by PPID |
| **Signal** | An async notification sent to a process (SIGTERM, SIGKILL, SIGHUP...) |
| **Foreground/background job** | Whether a process holds your terminal or runs detached |
| **Nice value** | Scheduling priority: -20 (highest) to 19 (lowest), default 0 |
| **Zombie process** | A finished child whose exit status hasn't been reaped by its parent yet |
| **Orphan process** | A child whose parent died — gets re-parented to PID 1 (init/systemd) |

---

## Quick Concepts — In Depth

### Process

```bash
# A process = running program + its own:
#   - PID (Process ID) — unique number assigned by kernel
#   - memory space (code, heap, stack)
#   - open file descriptors (files, sockets, pipes)
#   - environment variables (inherited from parent at fork)
#   - working directory
#   - signal handlers

# Same binary → many processes:
ps aux | grep python3
# deploy  1234  python3 app.py        ← PID 1234
# deploy  1235  python3 worker.py     ← PID 1235
# deploy  1236  python3 scheduler.py  ← PID 1236
```

### Parent / Child — The fork/exec Model

```bash
# Every process is created by fork() + exec():
# fork()  = create an IDENTICAL copy of the parent (gets a new PID)
# exec()  = replace the copy's memory with a new program

# The family tree:
pstree -p
# systemd(1)─┬─sshd(892)───sshd(1200)───bash(1201)───ps(9999)
#            ├─nginx(950)─┬─nginx(951)
#            │            └─nginx(952)
#            └─postgres(1050)─┬─postgres(1051)
#                             └─postgres(1052)

# PID 1 is the ancestor of everything — it has no parent (PPID=0)
ps -ef | awk 'NR<=5 {print $1,$2,$3,$8}'
# UID  PID  PPID  CMD
# root   1     0  systemd     ← PPID 0 = no parent
# root 892     1  sshd        ← parent is systemd
# deploy 1201 1200 bash       ← parent is sshd session
```

### Zombie vs Orphan

```bash
# Zombie: process FINISHED, parent hasn't called wait() to collect exit code
# - Just a row in the process table — no CPU, no memory, just a PID slot
# - STAT column shows Z
# - A few transient zombies = normal
# - Many persistent zombies = parent process bug (never calls wait())
# - Fix: kill the PARENT — zombie children get reaped automatically

# Find zombies:
ps aux | awk '$8 == "Z" {print}'

# Orphan: parent DIED before the child
# - Kernel re-parents orphans to PID 1 (systemd)
# - systemd calls wait() automatically → orphans become normal processes
```

### Nice Value

```bash
# Linux CFS (Completely Fair Scheduler) gives each process a share of CPU.
# Nice value shifts that share:

# nice =  0  → default equal share
# nice = 19  → "use my CPU for anything else" (~10% of a share)
# nice = -20 → "give me CPU before everyone else" (needs root)

# Real-world impact:
# Without nice: nightly backup spikes CPU, live app slows down
# With nice 15: backup gets minimal CPU, app barely notices
```

---

## Why This Matters for Backend/DevOps Work

```
- Finding which process is eating 100% CPU or holding a port your app needs
- Gracefully restarting an app (SIGTERM/SIGHUP) instead of hard-killing it
- Running long deploy/migration scripts that must survive an SSH disconnect
- Prioritizing a backup job so it doesn't starve the live app of CPU
- Debugging "port already in use" errors before starting a service
```

---

## Inspecting Processes

```bash
ps aux                          # ALL processes, BSD-style columns
ps -ef                           # ALL processes, System V-style (shows PPID)
ps aux | grep python              # find python processes
ps -ef --forest                    # show as parent/child tree
ps aux --sort=-%cpu | head -5       # top 5 CPU consumers
ps aux --sort=-%mem | head -5        # top 5 memory consumers
ps -eo pid,ni,comm | head -20         # PID, nice value, command name

top                                    # live, interactive
htop                                    # nicer top (install separately)

pgrep -f "uvicorn"                       # PIDs matching full command line
pgrep -u deploy                           # PIDs owned by user 'deploy'
pgrep -a nginx                             # PID + command line
pgrep -c nginx                              # count of matching processes
pstree -p                                    # process tree with PIDs
```

### Reading `ps aux` Columns

```
USER   PID  %CPU %MEM    VSZ    RSS  TTY  STAT  START   TIME  COMMAND
app   1234   2.1  1.5  412300  61200  ?    Sl   09:01   0:42  python app.py

VSZ = Virtual memory size: total address space mapped (may not all be in RAM)
RSS = Resident Set Size: actual RAM in use RIGHT NOW — use this for troubleshooting
%MEM = RSS as percentage of total RAM
TIME = total CPU time consumed (not wall-clock time)
```

**STAT codes — reading process state:**

```
R   Running — actively executing on a CPU core
S   Sleeping (interruptible) — waiting for I/O, signal, or timer — normal
D   Sleeping (uninterruptible) — waiting for I/O, CANNOT be killed even with -9
    Many D processes = I/O bottleneck (disk slow, NFS hanging)
Z   Zombie — finished, waiting to be reaped by parent
T   Stopped — paused (Ctrl+Z or SIGSTOP)
<   High priority (negative nice value)
N   Low priority (positive nice value)
s   Session leader
l   Multi-threaded
+   In the foreground process group
```

### Reading `top` — Header Decoded

```
top - 14:32:01 up 12 days, 3:21,  2 users,  load average: 0.42, 0.38, 0.35
Tasks: 183 total,   1 running, 182 sleeping,   0 stopped,   0 zombie
%Cpu(s):  2.1 us,  0.5 sy,  0.0 ni, 97.0 id,  0.3 wa,  0.0 hi,  0.1 si
MiB Mem:  7821.4 total,  1204.3 free,  4512.1 used,  2105.0 buff/cache

Load average: 0.42, 0.38, 0.35 = 1min, 5min, 15min
  On a 4-core server: load 4.0 = fully saturated, load > 4 = overloaded

%Cpu breakdown:
  us = user space → your app's CPU
  sy = kernel/system calls → overhead
  wa = I/O wait → waiting for disk/network (high wa = I/O bottleneck)
  id = idle → free CPU

Mem buff/cache: kernel using RAM for disk cache — CAN be reclaimed, not "really used"
avail Mem: what's actually available to new processes (more accurate than "free")
```

**`top` keyboard shortcuts:**

```bash
P   # sort by CPU (default)
M   # sort by memory
T   # sort by cumulative CPU time
1   # toggle per-core CPU view
k   # kill a process (prompts for PID + signal)
r   # renice a process
u   # filter by username
q   # quit
```

### `/proc` — Live Process Deep-Dive

```bash
cat /proc/1234/cmdline | tr '\0' '\n'    # exact command (null-byte separated)
cat /proc/1234/status                    # name, state, UID, GID, threads, memory
cat /proc/1234/environ | tr '\0' '\n' | grep DATABASE  # env vars

ls -la /proc/1234/fd/                    # all open file descriptors
ls /proc/1234/fd | wc -l                 # count of open FDs (high = FD leak?)

cat /proc/1234/limits         # ulimits (max open files, max threads, etc.)
cat /proc/1234/wchan          # kernel function it's currently sleeping in
cat /proc/1234/net/tcp        # TCP connections (raw hex)

# Memory details:
cat /proc/1234/status | grep -E "VmRSS|VmSize|VmPeak"
# VmPeak: peak virtual memory ever used
# VmSize: current virtual memory
# VmRSS:  current RAM in use — the real number
```

---

## Signals

| Signal | Number | Can Be Caught? | Meaning |
|------------|--------|----------------|----------------------------------------------|
| **SIGHUP** | 1 | Yes | Hangup — daemons treat as "reload config" |
| **SIGINT** | 2 | Yes | Interrupt — what Ctrl+C sends |
| **SIGQUIT** | 3 | Yes | Quit + core dump — Ctrl+\ |
| **SIGKILL** | 9 | **NO** | Force kill — kernel terminates immediately |
| **SIGUSR1** | 10 | Yes | User-defined (e.g. nginx: reopen logs) |
| **SIGTERM** | 15 | Yes | Graceful terminate — default signal for `kill` |
| **SIGSTOP** | 19 | **NO** | Pause process — cannot be caught or ignored |
| **SIGCONT** | 18 | Yes | Resume a stopped process |
| **SIGCHLD** | 17 | Yes | Child process died — parent is notified |
| **SIGPIPE** | 13 | Yes | Write to broken pipe |

### What Signals Actually Are

```
A signal is a software interrupt delivered asynchronously to a process.
The kernel delivers it — the process doesn't need to be asking for it.

When a process receives a signal, it can:
  1. Run a custom signal handler (code you wrote)
  2. Use the default action (kernel-defined per signal)
  3. Ignore it (for most signals)

SIGKILL and SIGSTOP CANNOT be caught, ignored, or handled — kernel enforces them.
```

### Sending Signals

```bash
# By PID
kill 1234               # SIGTERM (default)
kill -15 1234            # explicit SIGTERM
kill -9 1234              # SIGKILL
kill -HUP 1234             # SIGHUP
kill -0 1234               # no signal sent — just tests if process exists
                            # exit 0 = alive, exit 1 = not found/no permission

# By name
pkill nginx                 # SIGTERM to all processes named "nginx"
pkill -9 nginx               # SIGKILL
pkill -HUP nginx              # SIGHUP to all nginx
pkill -f "celery worker"       # match full command line
pkill -u deploy                 # kill all processes owned by "deploy"

killall python3                  # SIGTERM to all named "python3"
killall -9 python3                # SIGKILL

# From keyboard
# Ctrl+C = SIGINT (interrupt)
# Ctrl+Z = SIGSTOP (suspend)
# Ctrl+\ = SIGQUIT (core dump)
```

### How Daemons Use Signals

```bash
# nginx uses signals for zero-downtime operations:
sudo kill -HUP  $(cat /run/nginx.pid)    # reload config without dropping connections
sudo kill -USR1 $(cat /run/nginx.pid)    # reopen log files (after rotation)
sudo kill -QUIT $(cat /run/nginx.pid)    # graceful shutdown (finish current requests)
sudo kill -TERM $(cat /run/nginx.pid)    # fast shutdown

# Python app with signal handler for clean DB shutdown:
# import signal, sys
# def handle_sigterm(signum, frame):
#     db.close()
#     cache.flush()
#     sys.exit(0)
# signal.signal(signal.SIGTERM, handle_sigterm)
# Now `kill <pid>` triggers clean shutdown instead of abrupt exit
```

### The `-0` Signal — Test If Process Is Alive

```bash
kill -0 $PID 2>/dev/null
# Exit 0: process exists and you have permission to signal it
# Exit 1: process doesn't exist OR you lack permission

# Standard escalation pattern:
kill $PID
sleep 10
if kill -0 $PID 2>/dev/null; then
    echo "Still alive after 10s — force killing"
    kill -9 $PID
else
    echo "Exited cleanly"
fi
```

### Senior Tip

```
ALWAYS try SIGTERM (kill, no -9) first. It gives the process a chance to:
  - Close DB connections
  - Flush write buffers
  - Finish in-flight HTTP requests
  - Write clean shutdown log line
  - Remove PID files and lock files

SIGKILL skips ALL of that — the kernel erases the process instantly.
Can leave: locks held, temp files orphaned, transactions uncommitted,
           DB connections open from the server's perspective.

Standard escalation:
  kill $PID
  sleep 5
  kill -0 $PID 2>/dev/null && kill -9 $PID   # still alive? force it
```

---

## Job Control — fg, bg, jobs, nohup

### Why Closing SSH Kills Your Script

```
When you SSH in, the kernel creates a session:
  Session
    └── Terminal (pts/0)
        └── Process group: bash
            ├── foreground process group (your running command)
            └── background process groups (jobs in bg)

Closing the terminal → SIGHUP to session leader (bash) →
bash forwards SIGHUP to all attached process groups → everything dies.
```

### `jobs`, `fg`, `bg`, `Ctrl+Z`

```bash
sleep 300 &       # start in background
# [1] 9876        # [job number] PID

jobs              # [1]+  Running    sleep 300 &
jobs -l           # [1]+ 9876  Running    sleep 300 &  (with PID)

# Suspend current foreground job
# Ctrl+Z
# [1]+  Stopped   long_process

bg %1             # resume stopped job 1 in background
fg %1             # bring job 1 to foreground
fg                # fg with no args = most recent job

# Job references:
# %1    job number 1
# %+    most recent job
# %-    second most recent job
```

### `nohup` — Survive Terminal Disconnect

```bash
nohup ./long_migration.sh &                    # ignores SIGHUP, output → nohup.out
nohup ./long_migration.sh > /var/log/migration.log 2>&1 &  # explicit output
echo "Migration PID: $!"                        # $! = PID of last bg process
tail -f /var/log/migration.log                  # watch it live
```

### `nohup` vs `disown` vs `setsid` vs `tmux`

```
nohup ./x.sh &    Process ignores SIGHUP. Still a child of this shell.
                   Good for: quick one-off ops tasks.

disown -h %1      Remove job from shell's table + immune to SIGHUP.
                   Good for: forgot to nohup an already-running job.

setsid ./x.sh &   New session, fully detached from terminal.
                   More thorough than nohup.

tmux / screen     Persistent terminal session — detach and reattach.
                   Good for: interactive long-running tasks you want to monitor.
                   tmux new -s migration
                   python manage.py migrate
                   Ctrl+B D  (detach)
                   tmux attach -t migration  (reattach later)

systemd unit      THE production answer.
                   Restart-on-crash, logging, boot-start, proper lifecycle.
                   Use nohup only for one-off ops, never for persistent services.
```

**Practical: migration that must survive SSH disconnect:**

```bash
# Option 1 — nohup (quick)
nohup python manage.py migrate > /tmp/migration.log 2>&1 &
echo "PID $!, logs at /tmp/migration.log"
tail -f /tmp/migration.log

# Option 2 — tmux (interactive, can reattach)
tmux new -s migration
python manage.py migrate
# Ctrl+B D to detach — come back later with: tmux attach -t migration
```

---

## Priority — nice / renice

```bash
# Start a new process at lower priority
nice -n 10 tar -czvf backup.tar.gz /data    # backup gets less CPU
nice -n 19 ./batch_job.sh                    # near-lowest priority
sudo nice -n -5 ./critical_job.sh            # higher priority (root required for negative)

# Change priority of an ALREADY running process
renice 15 -p 1234             # lower priority of PID 1234
sudo renice -5 -p 1234         # higher priority (root required)
renice 10 -u deploy             # lower priority of ALL deploy's processes

# Check current nice values
ps -eo pid,ni,comm | head -20   # NI column
top                              # NI column live

# Nice value range: -20 (most CPU) to 19 (least CPU), default 0
```

**Real scenario — backup vs live app:**

```bash
# Without nice: nightly tar can spike CPU, app slows down
tar -czvf /backup/data.tar.gz /data/

# With nice 15: backup gets ~10% of CPU share, app barely notices
nice -n 15 tar -czvf /backup/data.tar.gz /data/

# In cron:
# 2 0 * * * nice -n 15 /opt/scripts/backup.sh
```

---

## `lsof` — List Open Files

On Linux everything is a file: regular files, sockets, pipes, devices. `lsof` shows what every process has open.

```bash
lsof -p 1234              # all files opened by PID 1234
lsof -u deploy             # all files opened by user "deploy"
lsof /var/log/app.log       # which processes have this file open
lsof -i                      # all network connections
lsof -i :8080                 # what's on port 8080
lsof -i :8080 -sTCP:LISTEN     # only the LISTENING socket
lsof -i TCP -sTCP:ESTABLISHED   # all established TCP connections
lsof +D /opt/myapp              # all files opened anywhere under /opt/myapp
lsof -t -i:8080                 # PIDs only (no headers) — use in kill one-liners
```

**`lsof` output columns:**

```
COMMAND  PID    USER   FD   TYPE  DEVICE  SIZE  NODE  NAME
nginx    950    root   6u   IPv4  12345   0t0   TCP   *:http (LISTEN)
python  1234   deploy  3u   REG   8,1    1024   456   /opt/myapp/app.log

FD column:
  0 = stdin, 1 = stdout, 2 = stderr
  3+ = application-opened files
  u = read+write, r = read, w = write

TYPE column:
  REG = regular file, DIR = directory
  IPv4/IPv6 = network socket
  unix = Unix domain socket (inter-process on same host)
  FIFO = named pipe
```

---

## `ss` — Socket Statistics

Faster than `netstat`, built into the kernel.

```bash
ss -tlnp          # TCP Listening Numeric with Process — most common
ss -ulnp           # UDP Listening Numeric Process
ss -tlnp | grep :8080   # is anything on port 8080?
ss -s               # summary: total sockets by state
ss -tn              # all established TCP connections
ss -tp              # established TCP + process info
```

**Reading `ss -tlnp` output:**

```
State   Recv-Q  Send-Q  Local Address:Port   Peer Address:Port   Process
LISTEN  0       128     0.0.0.0:8080        0.0.0.0:*           users:(("gunicorn",pid=1234,fd=5))

0.0.0.0:8080   = listening on ALL interfaces (accessible from outside)
127.0.0.1:8080 = listening on localhost only (not reachable externally)
:::8080        = IPv6 any (usually also accepts IPv4)
```

---

## Senior Walkthrough: Process Debugging

### CPU Hog

```bash
# 1. Spot it
top                               # sort by %CPU, watch for outlier
ps aux --sort=-%cpu | head -5     # static snapshot

# 2. Identify precisely
PID=1234
cat /proc/$PID/cmdline | tr '\0' ' '        # exact command line
cat /proc/$PID/status | grep -E "Name|State|Uid"

# 3. Investigate without killing
cat /proc/$PID/wchan               # kernel function it's sleeping in
sudo strace -p $PID -c             # count syscalls by type (10s, then Ctrl+C)
sudo py-spy dump --pid $PID        # Python stack trace without interrupting

# 4. Escalate gracefully
kill $PID
sleep 10
kill -0 $PID 2>/dev/null && kill -9 $PID || echo "Exited cleanly"
```

### Port Already in Use

```bash
# "Address already in use" — port 8080 is taken

lsof -i :8080                   # shows PID, program, user
ss -tlnp | grep :8080            # faster alternative

# Kill it and restart
kill $(lsof -t -i:8080)
sleep 2
systemctl start myapp
```

### Memory Leak Investigation

```bash
# App slowly consuming more RAM over hours

# Watch memory over time
watch -n 5 'ps aux --sort=-%mem | head -5'

# Check if it's a file descriptor leak (FD count climbing)
ls /proc/$PID/fd | wc -l
cat /proc/$PID/limits | grep "open files"

# Memory breakdown
cat /proc/$PID/status | grep -E "VmRSS|VmSize|VmPeak"
# VmRSS climbing = memory leak
# FD count climbing = file descriptor leak

# Temporarily renice to slow impact while investigating
renice 10 -p $PID
```

---

## Interview Angle

**Q: `kill -9` vs `kill -15` — when would you use each?**

```
SIGTERM (15) — always try first:
  Process CAN catch it and run cleanup:
    - Close DB connections
    - Flush write buffers
    - Finish in-flight HTTP requests
    - Write clean shutdown log line
    - Remove PID files, release locks

SIGKILL (9) — last resort only:
  Kernel terminates immediately — NO cleanup code runs.
  Can leave: open transactions, held locks, half-written data,
             DB connections still "open" from server's perspective.
  Use when: process is deadlocked, stuck in D state, ignores SIGTERM.

Standard pattern:
  kill $PID            # SIGTERM
  sleep 10             # wait for clean shutdown
  kill -0 $PID 2>/dev/null && kill -9 $PID   # force only if still alive
```

**Q: What's a zombie process and should you worry about it?**

```
Zombie (Z): process exited, parent hasn't called wait() to collect exit code.
  - No CPU, no memory — just a PID slot
  - A few transient zombies = normal
  - Many PERSISTENT zombies = parent process bug (never calls wait())

Fix: kill the PARENT — zombie children get reaped automatically when parent exits.
Identify parent: ps -p <zombie_pid> -o ppid=
```

**Q: How do you find what's listening on a port?**

```bash
ss -tlnp | grep :8080        # fastest — always available
lsof -i :8080                 # more detail (FD number, full socket info)
netstat -tlnp | grep :8080    # legacy — may not be installed on minimal servers
```

**Q: Why `nohup` instead of just `&`?**

```
./x.sh &    Background but still attached to terminal.
            Close terminal → SIGHUP → script dies.

nohup ./x.sh &    Process ignores SIGHUP → survives terminal close.

In production: systemd unit is the right answer.
  - Restart on crash
  - Boot-start
  - Logging integration
  - Proper lifecycle management
nohup = quick one-off ops task only.
```

**Q: What does the load average actually mean?**

```
Load average = average number of processes RUNNING or WAITING for CPU
               measured over 1min / 5min / 15min

On a 4-core server:
  load 4.0 = fully saturated (4 processes always running)
  load 2.0 = 50% utilised
  load 8.0 = overloaded (4 running + 4 waiting for CPU)

Rule: load > number of CPU cores = system is overloaded.
A spike is fine. Sustained load > cores = investigate.

cat /proc/cpuinfo | grep "^processor" | wc -l   # number of cores
uptime                                            # current load averages
```

**Q: What's the difference between VSZ and RSS in `ps`?**

```
VSZ (Virtual Memory Size): total address space the process has mapped.
  Includes: code, heap, stack, shared libraries, memory-mapped files.
  May include memory mapped but NOT yet loaded into RAM.
  Often much larger than what's actually in RAM.

RSS (Resident Set Size): bytes actually in RAM right now.
  This is the REAL memory consumption figure.
  Use RSS when troubleshooting memory issues — VSZ is misleading.

Example: a Python process might show VSZ=500MB but RSS=80MB.
  The 500MB is address space reserved; only 80MB is actually in RAM.
```