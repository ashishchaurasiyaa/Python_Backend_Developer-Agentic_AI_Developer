# Process Management

**DevOps Track · Phase 1: Linux**

## Quick Concepts

- **Process** = a running instance of a program, identified by a PID
- **Parent/child** = every process (except PID 1) is spawned by a parent process (PPID)
- **Signal** = an async notification sent to a process (SIGTERM, SIGKILL, SIGHUP...)
- **Foreground/background job** = whether a process holds your terminal or runs detached
- **Nice value** = scheduling priority, -20 (highest priority) to 19 (lowest), default 0
- **Zombie process** = a finished child whose exit status hasn't been reaped by its parent yet
- **Orphan process** = a child whose parent died before it did — gets re-parented to PID 1 (init)

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
ps aux                       # ALL processes, BSD-style columns (USER PID %CPU %MEM ...)
ps -ef                        # ALL processes, System V-style (UID PID PPID ...)
ps aux | grep python           # find python processes
ps -ef --forest                 # show as a parent/child tree

top                               # live, interactive (q to quit, k to kill, M sort by mem, P sort by cpu)
htop                               # nicer top — colored, scrollable, mouse support (install separately)

pgrep -f "uvicorn"                  # PIDs matching a pattern
pgrep -u deploy                       # PIDs owned by user 'deploy'
pstree -p                               # process tree with PIDs

cat /proc/1234/status                     # detailed info on PID 1234
cat /proc/1234/cmdline                      # exact command line it was started with
ls -la /proc/1234/fd                          # open file descriptors (great for "who has this file open")
```

### Reading `ps aux` columns

```
USER   PID  %CPU %MEM    VSZ   RSS TTY  STAT START   TIME COMMAND
app   1234   2.1  1.5 412300 61200 ?    Sl   09:01   0:42 python app.py

STAT codes:  R=running  S=sleeping  D=uninterruptible sleep (usually I/O)
             Z=zombie   T=stopped   <=high priority   N=low priority
             s=session leader   l=multi-threaded
```

---

## Signals

| Signal | Number | Meaning |
|---|---|---|
| **SIGHUP** | 1 | Hangup — traditionally "reload config" for daemons (nginx, sshd) |
| **SIGINT** | 2 | Interrupt — what Ctrl+C sends |
| **SIGKILL** | 9 | Force kill — kernel terminates immediately, process CANNOT catch/ignore it |
| **SIGTERM** | 15 | Graceful terminate — process CAN catch it and clean up (default signal for `kill`) |
| **SIGSTOP** | 19 | Pause the process (cannot be caught) |
| **SIGCONT** | 18 | Resume a stopped process |

```bash
kill 1234              # sends SIGTERM by default — graceful, program can catch and clean up
kill -15 1234            # explicit SIGTERM
kill -9 1234               # SIGKILL — last resort, no cleanup, use when SIGTERM is ignored
kill -HUP 1234                # SIGHUP — many daemons treat this as "reload config"

pkill -f "celery worker"        # kill by matching the full command line
pkill -9 -u deploy                # kill everything owned by user deploy (force)
killall python3                    # kill ALL processes named exactly "python3"
killall -9 nginx                     # force-kill all nginx processes
```

### Senior Tip

```
ALWAYS try SIGTERM (kill, no -9) first. It gives the process a chance
to: close DB connections, flush buffers, finish in-flight requests,
write a clean shutdown log line. SIGKILL skips all of that — the OS
just erases the process, which can leave locks held, temp files
orphaned, or data half-written.

Standard escalation pattern:
   kill $PID
   sleep 5
   kill -0 $PID 2>/dev/null && kill -9 $PID   # still alive? force it
```

---

## Job Control — fg, bg, jobs, nohup

```bash
long_command &          # start in background, prompt returns immediately
jobs                      # list background jobs for this shell session
jobs -l                     # include PIDs

fg                            # bring most recent bg job to foreground
fg %2                           # bring job number 2 to foreground
bg %1                             # resume a stopped job in the background

Ctrl+Z                              # suspend (STOP) the current foreground job
Ctrl+C                                # SIGINT the foreground job

nohup ./long_script.sh &                # immune to SIGHUP — survives terminal/SSH disconnect
nohup ./long_script.sh > out.log 2>&1 &   # + redirect output (nohup alone still writes nohup.out)

disown -h %1                                # detach job from shell without killing it
setsid ./script.sh &                          # fully detach into a new session (stronger than nohup)
```

```
Why does closing an SSH session kill your script?
  Closing the terminal sends SIGHUP to all jobs attached to it.
  nohup (or setsid, or a proper daemon/systemd unit, or tmux/screen)
  are the standard fixes. In production, prefer systemd over nohup —
  nohup has no restart-on-crash, no logging integration, no boot-start.
```

---

## Priority — nice / renice

```bash
nice -n 10 ./heavy_batch_job.sh       # start a NEW process with lower priority (higher nice value)
nice -n -5 ./urgent_job.sh              # higher priority (needs sudo for negative values)

renice 10 -p 1234                          # change priority of an ALREADY running process
renice -5 -p 1234                            # needs root for negative (higher-priority) values

top                                             # NI column shows current nice value
```

```
Nice value range: -20 (most CPU priority) to 19 (least CPU priority)
Default: 0

Use case: a nightly backup or log-compression job shouldn't compete
with your live app for CPU —
   nice -n 15 tar -czf backup.tar.gz /data
```

---

## Senior Walkthrough: Find and Kill a Process Eating CPU / Holding a Port

### CPU hog

```bash
# 1. Spot it
top                              # sort default is %CPU, watch for the outlier
ps aux --sort=-%cpu | head -5     # confirm from a static snapshot

# 2. Investigate before killing
ls -la /proc/$PID/                  # confirm what it is
cat /proc/$PID/cmdline                # exact command that started it
cat /proc/$PID/status                   # state, threads, memory

# 3. If it's a Python process — get a stack trace WITHOUT killing it first
py-spy dump --pid $PID

# 4. Escalate gracefully
kill $PID
sleep 5
kill -0 $PID 2>/dev/null && kill -9 $PID   # only force-kill if it's still alive
```

### Process holding a port

```bash
lsof -i :8080                     # who is listening/connected on port 8080
ss -tlnp | grep :8080               # alternative, often faster than lsof, shows PID/program

kill $(lsof -t -i:8080)               # one-liner: kill whatever holds port 8080
```

---

## Interview Angle

**Q: `kill -9` vs `kill -15` — when would you use each?**
`-15` (SIGTERM) first, always — it lets the process clean up. `-9` (SIGKILL) only if the process ignores SIGTERM or is unresponsive (e.g. deadlocked) — the kernel terminates it immediately with no chance to run cleanup code.

**Q: What's a zombie process and should you worry about it?**
A zombie is a process that has exited but whose exit status hasn't been read by its parent yet — it's just an entry in the process table, using no real resources. A handful appearing/disappearing is normal; large numbers of persistent zombies point to a parent process bug that never calls `wait()`.

**Q: How do you find what's listening on a given port?**
`ss -tlnp | grep :<port>` or `lsof -i :<port>` — both show the PID and process name bound to that port.

**Q: Why prefer `nohup ./x.sh &` over just `./x.sh &`?**
Plain `&` still ties the job to the terminal session — closing the terminal sends SIGHUP and kills it. `nohup` makes the process ignore SIGHUP so it survives disconnect. In production, a systemd unit is the more robust answer to the same problem.
