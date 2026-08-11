# Services & systemd

**DevOps Track · Phase 1: Linux**

## Quick Concepts

| Concept | One-line definition |
|-----------------------------------|----------------------------------------------------------------------|
| **systemd** | Init system (PID 1) and service manager on all modern Linux distros |
| **Unit** | A systemd-managed resource: `.service`, `.timer`, `.socket`, `.mount` |
| **Unit file** | Config describing how to start/stop/restart a unit |
| **journald / journalctl** | systemd's structured logging daemon + its query tool |
| **Target** | A group of units — replaces SysV runlevels (`multi-user.target`) |
| **enable vs start** | `enable` = start on boot; `start` = start right now — do BOTH for prod |

---

## Quick Concepts — In Depth

### systemd as PID 1

```
The kernel boots, mounts the root filesystem, then executes exactly one process: PID 1.
On modern Linux: PID 1 = systemd.

systemd then:
  1. Reads unit files from /etc/systemd/system/ and /lib/systemd/system/
  2. Resolves dependency order (After=, Requires=, Wants=)
  3. Starts units in parallel where possible
  4. Manages their entire lifecycle: start / stop / restart / log
  5. Becomes the parent of every service it launches

If PID 1 dies → kernel panic. Everything stops.
This is why containers use a minimal init (tini, s6) inside Docker
to forward signals properly to child processes.
```

### Unit Types

```
.service   → a process (web app, DB, background worker)
.timer     → cron replacement — triggers a .service on a schedule
.socket    → socket activation — starts a service when traffic arrives on a port
.mount     → filesystem mount managed like a service
.target    → a group of units — "reach this state" (multi-user.target = fully booted)
.path      → watches a file/dir, triggers a service when it changes
```

### `enable` vs `start` — What They Actually Do

```bash
systemctl enable myapp
# Creates a symlink:
# /etc/systemd/system/multi-user.target.wants/myapp.service
#   → /etc/systemd/system/myapp.service
# Effect: systemd adds myapp to the startup list for every future boot.
# Does NOT start the service right now.

systemctl start myapp
# Tells the running systemd to start the unit right now.
# Has NO effect on whether it starts at next boot.

systemctl enable --now myapp
# Does BOTH: creates the symlink AND starts immediately.
# This is what production deploys use.
```

---

## Why This Matters for Backend/DevOps Work

```
- Every app deployed to a bare VM/EC2 should run as a systemd service,
  not a nohup'd background process
- Auto-restart on crash, structured logs, boot-time startup — all free
  once you write one unit file correctly
- journalctl is the FIRST place to look when a service won't start
- systemctl is what CI/CD deploy scripts call to restart your app
```

---

## systemctl — The Main Interface

```bash
sudo systemctl start myapp              # start now
sudo systemctl stop myapp                # stop now
sudo systemctl restart myapp              # stop then start
sudo systemctl reload myapp               # ask service to reload config (no restart, if supported)
sudo systemctl reload-or-restart myapp     # reload if supported, else restart

sudo systemctl enable myapp                # start automatically on boot
sudo systemctl disable myapp                # don't start on boot
sudo systemctl enable --now myapp            # enable AND start — use this in prod deploys

systemctl status myapp                       # state, recent logs, PID, memory, CPU
systemctl is-active myapp                     # prints active/inactive (script-friendly)
systemctl is-enabled myapp                     # prints enabled/disabled

systemctl list-units --type=service             # all loaded service units
systemctl list-units --state=failed              # everything currently failed
systemctl list-unit-files | grep enabled          # everything set to start on boot

sudo systemctl daemon-reload                       # REQUIRED after editing any unit file
sudo systemctl mask myapp                           # prevent ANY start (stronger than disable)
sudo systemctl unmask myapp
```

### Reading `systemctl status` Output

```bash
systemctl status myapp
# ● myapp.service - My FastAPI Backend
#      Loaded: loaded (/etc/systemd/system/myapp.service; enabled; vendor preset: enabled)
#      Active: active (running) since Mon 2026-08-10 09:01:22 UTC; 3h 12min ago
#    Main PID: 1234 (uvicorn)
#       Tasks: 4 (limit: 4915)
#      Memory: 142.3M
#         CPU: 1.243s
#      CGroup: /system.slice/myapp.service
#              └─1234 /opt/myapp/venv/bin/uvicorn main:app

# Loaded line:
#   enabled  = will start on boot
#   disabled = won't start on boot
#   masked   = completely blocked, can't start at all

# Active states:
#   active (running)  = running fine
#   active (exited)   = oneshot ran and exited cleanly
#   failed            = last run exited non-zero or killed by a signal
#   inactive (dead)   = not running, not failed — just stopped
```

### `mask` vs `disable`

```bash
systemctl disable myapp   # remove boot symlink, manual start still works
systemctl mask myapp      # symlink → /dev/null: start/restart/enable ALL fail
# Use: prevent a packaged service (e.g. apache2) from ever starting,
#      even if a dependency tries to enable it.
systemctl unmask myapp    # restore (removes the /dev/null symlink)
```

### Legacy `service` Command

```bash
sudo service myapp start   # equivalent to systemctl start myapp
sudo service myapp status
# `service` is a compatibility shim — it calls systemctl under the hood.
# Know it for RHEL habits and older scripts; use systemctl in new work.
```

---

## Writing a systemd Service — In Depth

### Full Production-Grade Unit File

```ini
# /etc/systemd/system/myapp.service

[Unit]
Description=My FastAPI Backend
Documentation=https://github.com/myorg/myapp

# Ordering: start AFTER these units are up
After=network-online.target postgresql.service redis.service

# Hard dependency: if postgresql fails to start, myapp won't start either
Requires=postgresql.service

# Soft dependency: try to start redis but proceed even if it's not there
Wants=redis.service

[Service]
Type=simple
User=app
Group=app
WorkingDirectory=/opt/myapp

# Load env vars from file — KEY=VALUE format, no "export" prefix
EnvironmentFile=/opt/myapp/.env

# Main process — always use absolute path to the venv binary:
ExecStart=/opt/myapp/venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000

# Signal app to reload config (if it handles SIGHUP):
ExecReload=/bin/kill -HUP $MAINPID

# Graceful stop: send SIGTERM, wait TimeoutStopSec, then SIGKILL:
TimeoutStopSec=30

# Restart policy:
Restart=always      # restart on any exit: crash, OOM, signal, etc.
RestartSec=5        # wait 5s before restarting (avoid hammering on crash loop)

# Logging:
StandardOutput=journal
StandardError=journal
SyslogIdentifier=myapp    # prefix in journal (grep-friendly)

# Resource limits:
LimitNOFILE=65536     # max open FDs (default 1024 is too low for web apps)
MemoryMax=1G           # OOM-kill this service if it exceeds 1GB
CPUQuota=80%            # cap at 80% of one CPU core

[Install]
WantedBy=multi-user.target
```

```bash
# After creating/editing — mandatory steps:
sudo systemctl daemon-reload
sudo systemctl enable --now myapp
systemctl status myapp
```

### Key Directives — Explained

```
[Unit]
  After=       ordering — start after these (doesn't force them to exist)
  Requires=    hard dependency — this won't start if the dependency fails
  Wants=       soft dependency — prefers dep to be up but starts anyway

[Service]
  Type=simple    ExecStart IS the main process, foreground — most web apps
  Type=forking   process forks and parent exits — traditional Unix daemons
  Type=oneshot   runs once and exits — migrations, setup scripts
  Type=notify    process calls sd_notify("READY=1") when truly ready
                 systemd waits for this before marking "active"
  Restart=always restart on any exit — good default for services
  RestartSec=5   wait before restart — avoids crash-loop hammering
  User/Group     DEDICATED non-root user — never run app services as root
  EnvironmentFile  load KEY=VALUE pairs from a file (.env-style)
  LimitNOFILE    open file descriptor limit (web apps need 65536+)

[Install]
  WantedBy=multi-user.target   the boot target that pulls this in when enabled
```

### `After=network.target` vs `After=network-online.target`

```
network.target          = kernel initialised network interfaces
                          IP may not be assigned yet, DNS may not work
                          Use for: services that retry connections internally

network-online.target   = at least one interface has a routable IP + DNS works
                          Use for: services that connect to DB/APIs at startup
                          and CANNOT retry — they need the network actually up
```

---

## journalctl — Reading Logs

```bash
journalctl -u myapp                  # all logs for this unit
journalctl -u myapp -f                # follow live (like tail -f)
journalctl -u myapp -n 100             # last 100 lines
journalctl -u myapp -p err              # errors and above only
journalctl -u myapp --no-pager           # print all, no pager (script-friendly)

journalctl -u myapp --since "1 hour ago"
journalctl -u myapp --since "2026-08-10 09:00:00" --until "2026-08-10 10:00:00"

journalctl -u myapp -b                   # since this boot
journalctl -u myapp -b -1                 # from the PREVIOUS boot (what caused reboot?)

journalctl -f -u myapp -u nginx -u postgresql   # tail multiple units together
journalctl -k                                    # kernel messages only (like dmesg)
journalctl -k --since "10 min ago"               # recent kernel events (OOM? hardware?)
```

### Priority Levels

```
0 = emerg    1 = alert    2 = crit    3 = err
4 = warning  5 = notice   6 = info    7 = debug

journalctl -p err       → shows: err, crit, alert, emerg
journalctl -p warning   → shows: warning, err, crit, alert, emerg
```

### Output Formats

```bash
journalctl -u myapp -o short-precise    # precise timestamps with microseconds
journalctl -u myapp -o json-pretty       # full structured JSON (all fields)
journalctl -u myapp -o cat               # message only, no metadata (for piping to grep)
```

### Journal Disk Management

```bash
journalctl --disk-usage                  # total space journal is using
sudo journalctl --vacuum-time=7d          # delete entries older than 7 days
sudo journalctl --vacuum-size=500M         # trim until size is under 500MB

# Permanent cap in /etc/systemd/journald.conf:
# [Journal]
# SystemMaxUse=500M
# MaxRetentionSec=7day
sudo systemctl restart systemd-journald    # apply journald config changes
```

### Why journald Over Flat Log Files

```
Traditional logging: each daemon writes its own /var/log/app.log
Problems:
  - Each app invents its own timestamp format
  - Logs scattered across multiple files
  - No structured fields — you grep strings only
  - Log rotation is a separate tool (logrotate)

journald:
  - Every unit's stdout/stderr captured automatically — no config needed
  - Structured fields: unit name, PID, boot ID, priority, hostname
  - Binary + indexed: fast filtered queries by time, unit, priority
  - journalctl handles time filtering, field filtering, output formatting
  - Survives log rotation — manages its own storage
```

---

## Senior Debug Flow: "My Service Won't Start"

```bash
# Step 1: attempt start, status gives immediate feedback
sudo systemctl start myapp
systemctl status myapp
# Look for: exit code (status=1/FAILURE) or signal (signal=SIGSEGV)

# Step 2: full log history
journalctl -u myapp -n 100 --no-pager

# Step 3: jump to errors only
journalctl -u myapp -p err --no-pager

# Step 4: check previous boot too
journalctl -u myapp -b -1 -p err    # was it failing before the last reboot?

# Common problems and fixes:

# "No such file or directory" in ExecStart
#   → ExecStart path is wrong, or binary not installed in venv
#   → Use absolute path: /opt/myapp/venv/bin/uvicorn (not uvicorn)

# "Permission denied"
#   → User= can't read WorkingDirectory or EnvironmentFile
#   → Fix: chown -R app:app /opt/myapp; chmod 600 /opt/myapp/.env

# "Address already in use"
#   → Something else is on port 8000
#   → Fix: ss -tlnp | grep :8000; kill that process

# "Failed to load environment files"
#   → EnvironmentFile path doesn't exist or not readable by User=
#   → Fix: create the .env file, check permissions

# Service crash-loops (journalctl shows rapid repeated restarts):
#   → Temporarily set Restart=no; daemon-reload; start; read logs carefully
```

---

## Timers — systemd's cron Replacement

```ini
# /etc/systemd/system/backup.service
[Unit]
Description=Nightly Backup

[Service]
Type=oneshot
User=backup
ExecStart=/opt/scripts/backup.sh
StandardOutput=journal
StandardError=journal
```

```ini
# /etc/systemd/system/backup.timer
[Unit]
Description=Run backup daily at 02:00

[Timer]
OnCalendar=*-*-* 02:00:00    # every day at 02:00 UTC
Persistent=true               # if machine was off at 02:00, run on next boot
RandomizedDelaySec=300         # 0–300s random jitter (prevents thundering herd across fleet)

[Install]
WantedBy=timers.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now backup.timer

systemctl list-timers            # all timers + next run time
systemctl list-timers --all       # including inactive timers
journalctl -u backup.service       # logs from each backup run
```

### `OnCalendar` Syntax

```
daily                    = *-*-* 00:00:00
weekly                   = Mon *-*-* 00:00:00
monthly                  = *-*-01 00:00:00
hourly                   = *-*-* *:00:00
*-*-* 02:00:00           = every day at 02:00
Mon,Thu *-*-* 14:30:00   = Monday and Thursday at 14:30
*-*-* 00/6:00:00         = every 6 hours
```

### systemd Timers vs cron

```
cron:
  + Universally known, simple one-line syntax
  + No extra files needed
  - No built-in logging
  - Can't depend on other systemd units
  - Doesn't handle "machine was off when task should have run"

systemd timers:
  + Logs to journalctl automatically
  + Can depend on units (wait for network-online.target, DB, etc.)
  + Persistent=true handles missed runs
  + RandomizedDelaySec prevents thundering herd across a fleet
  - Two files instead of one line

Verdict: either works. Timers are the systemd-native answer in interviews.
```

---

## Senior Tips

```
1. ALWAYS run services as a dedicated non-root User=/Group=.
   A compromised web app running as root owns the entire server.

2. Restart=always + RestartSec=5 is the standard resilience pair.
   Instant restart on crash loops can trigger systemd's rate limit
   (5 restarts in 10s → unit enters failed state, stops restarting).

3. Forgetting daemon-reload after editing a unit file is the #1 cause
   of "why isn't my change taking effect?" — always run it.

4. Use systemctl reload (SIGHUP) over restart when the app supports
   config hot-reload — zero dropped connections vs a brief outage.

5. journalctl -p err first, then widen — don't scroll through
   thousands of INFO lines manually.

6. LimitNOFILE=65536 in the unit file — default kernel ulimit of 1024
   is too low for any web server handling real traffic.
```

---

## Interview Angle

**Q: Difference between `systemctl enable` and `systemctl start`?**

```
start:  run it right now, this boot only. No effect on future boots.

enable: create symlink in the target's .wants/ directory.
        Service starts automatically at every future boot.
        Does NOT start it right now.

enable --now: both. Standard for production deploys.

You can enable a service, reboot → it starts at boot.
You can start a service, reboot → it's gone (unless also enabled).
```

**Q: Why `Restart=always` with `RestartSec=5` instead of instant restart?**

```
Instant restart on a crash-looping process:
  - Hammers CPU/disk with rapid start→crash→start cycles
  - Floods journalctl with thousands of identical error lines
  - Triggers systemd's rate limit: 5 restarts in 10s → unit enters
    "failed" state and stops restarting completely

RestartSec=5 throttles the rate:
  - Gives a crashed DB time to release its lock file before restarting
  - Reduces log noise
  - Service still self-heals, just not in a tight spin loop
```

**Q: How do you tail logs for a systemd service?**

```bash
journalctl -u myapp -f

Better than tail -f /var/log/app.log because:
  - Works even if the app writes only to stdout (journal captures it)
  - Survives log rotation — journal manages its own storage
  - Can add -p err to filter while following
  - Shows logs from the PREVIOUS crash run before the service restarted
```

**Q: What's `Type=simple` vs `Type=notify`?**

```
Type=simple: systemd marks "active" as soon as ExecStart is forked.
             It doesn't know if the app finished initialising
             (loaded DB connections, bound port, etc.).

Type=notify: app sends sd_notify("READY=1") when genuinely ready.
             systemd waits for this before marking "active" and before
             starting units that depend on this one.

Real-world impact: if database.service is Type=simple and myapp.service
depends on it, myapp may start before the DB finishes recovery.
Type=notify eliminates this race condition.
PostgreSQL uses Type=notify for exactly this reason.
```

**Q: What does `daemon-reload` do and why is it needed?**

```
systemd reads unit files into memory at boot.
When you edit /etc/systemd/system/myapp.service, the running systemd
still has the old version in memory.

daemon-reload: "re-scan all unit file directories, update in-memory state."

Without it: systemctl restart myapp will use the OLD unit file.
Your config changes have zero effect until daemon-reload runs.
```