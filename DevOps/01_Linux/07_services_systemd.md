# Services & systemd

**DevOps Track · Phase 1: Linux**

## Quick Concepts

- **systemd** = the init system (PID 1) and service manager on almost all modern Linux distros
- **Unit** = a systemd-managed resource — a `.service`, `.timer`, `.socket`, `.mount`, etc.
- **Unit file** = the config describing how to start/stop/restart a unit (`/etc/systemd/system/*.service`)
- **journald / journalctl** = systemd's structured logging daemon + its query tool
- **Target** = systemd's replacement for old SysV runlevels (`multi-user.target`, `graphical.target`)
- **enable vs start** = `enable` = start on boot; `start` = start right now — independent, do both for prod services

---

## Why This Matters for Backend/DevOps Work

```
- Every app you deploy to a bare VM/EC2 instance should run as a
  systemd service, not a nohup'd background process
- Auto-restart on crash, structured logs, boot-time startup — all
  free once you write one unit file correctly
- journalctl is the FIRST place to look when a service won't start
- systemctl is what CI/CD deploy scripts call to restart your app
```

---

## systemctl — The Main Interface

```bash
sudo systemctl start myapp            # start now
sudo systemctl stop myapp               # stop now
sudo systemctl restart myapp              # stop then start
sudo systemctl reload myapp                 # ask the service to reload config WITHOUT restarting (if supported)
sudo systemctl reload-or-restart myapp        # reload if supported, else restart

sudo systemctl enable myapp                     # start automatically on boot
sudo systemctl disable myapp                      # don't start on boot
sudo systemctl enable --now myapp                   # enable AND start in one command

systemctl status myapp                                # current state, recent log lines, PID
systemctl is-active myapp                               # just prints active/inactive (script-friendly)
systemctl is-enabled myapp                                # just prints enabled/disabled

systemctl list-units --type=service                        # all loaded service units
systemctl list-units --state=failed                          # everything currently failed
systemctl list-unit-files | grep enabled                       # everything set to start on boot

sudo systemctl daemon-reload                                     # re-read unit files after editing one (REQUIRED)
sudo systemctl mask myapp                                          # prevent ANY start (even manual) — stronger than disable
sudo systemctl unmask myapp
```

### `service` — Legacy Wrapper (still common, especially RHEL habits)

```bash
sudo service myapp start        # roughly equivalent to systemctl start myapp
sudo service myapp status
# systemctl is the modern/preferred tool; `service` is a compatibility
# shim that under the hood usually just calls systemctl now.
```

---

## Writing a systemd Service for a Python App

```ini
# /etc/systemd/system/myapp.service

[Unit]
Description=My FastAPI Backend
After=network.target postgresql.service
# "After" = ordering only, not a hard dependency — pair with Requires= if it must be up

[Service]
Type=simple
User=app
Group=app
WorkingDirectory=/opt/myapp
EnvironmentFile=/opt/myapp/.env
ExecStart=/opt/myapp/venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000
ExecReload=/bin/kill -HUP $MAINPID
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

# Resource limits (optional but good practice)
LimitNOFILE=65536
MemoryMax=1G

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload           # required after creating/editing the unit file
sudo systemctl enable --now myapp        # start on boot AND right now
systemctl status myapp                     # confirm it's running
```

### Key Directives Explained

```
[Unit]
  Description   human-readable name shown in status/logs
  After         ordering — start after these units (doesn't force them to exist)
  Requires      hard dependency — if this fails/stops, so does yours

[Service]
  Type=simple    process itself IS the main process (most common for web apps)
  Type=forking   process forks and the parent exits (traditional daemons)
  Type=oneshot   runs once and exits (migrations, setup scripts)
  Restart=always restart no matter how it exits — good default for services
  RestartSec=5    wait 5s before restarting (avoid crash-loop hammering)
  User/Group      run as a DEDICATED non-root user — never run app services as root
  EnvironmentFile load KEY=VALUE pairs from a file (.env-style, no "export" prefix)

[Install]
  WantedBy=multi-user.target   which boot target pulls this in when enabled
```

---

## journalctl — Reading Logs

```bash
journalctl -u myapp                  # all logs for this unit
journalctl -u myapp -f                 # follow live (like tail -f)
journalctl -u myapp --since "1h ago"     # time-windowed
journalctl -u myapp --since "2026-07-24" --until "2026-07-25"
journalctl -u myapp -n 100                # last 100 lines
journalctl -u myapp -p err                  # only priority "error" and above
journalctl -u myapp --no-pager                # print all, don't page (script-friendly)

journalctl -b                                    # logs since last boot
journalctl -b -1                                   # logs from the PREVIOUS boot
journalctl --disk-usage                              # how much space the journal is using
sudo journalctl --vacuum-time=7d                        # trim logs older than 7 days
sudo journalctl --vacuum-size=500M                        # cap total journal size

journalctl -k                                                # kernel messages only (like dmesg)
journalctl -f -u myapp -u nginx                                # follow multiple units at once
```

### Senior Debug Flow: "My Service Won't Start"

```bash
sudo systemctl start myapp
systemctl status myapp              # shows the last few log lines + exit code inline

journalctl -u myapp -n 50 --no-pager   # full recent history
journalctl -u myapp -p err               # jump straight to errors

# Common findings:
#  - wrong path in ExecStart (binary not found)
#  - .env file missing / wrong permissions for User=
#  - port already in use (check with: ss -tlnp | grep 8000)
#  - Python venv not activated properly (ExecStart must use the venv's python/uvicorn directly)
```

---

## Timers — systemd's cron Alternative

```ini
# /etc/systemd/system/backup.timer
[Unit]
Description=Run backup daily

[Timer]
OnCalendar=daily
Persistent=true

[Install]
WantedBy=timers.target
```

```bash
sudo systemctl enable --now backup.timer
systemctl list-timers                       # see all scheduled timers + next run time
```

```
systemd timers vs cron:
  Timers integrate with journalctl logging, can depend on other units,
  and handle "missed run while machine was off" via Persistent=true.
  cron is simpler and more universally known — either is fine, timers
  are the more "systemd-native" answer if asked in an interview.
```

---

## Senior Tip

```
1. ALWAYS run app services as a dedicated non-root User=/Group=.
2. Restart=always + RestartSec=5 is the standard resilience pair —
   crashes self-heal without hammering the system in a tight loop.
3. Forgot `daemon-reload` after editing a unit file is the #1 "why
   isn't my change taking effect" mistake.
4. Use `systemctl reload` (SIGHUP) over `restart` when the app
   supports config hot-reload — zero dropped connections vs a restart.
5. journalctl -p err first, then widen the window — don't scroll
   through thousands of INFO lines manually.
```

## Interview Angle

**Q: Difference between `systemctl enable` and `systemctl start`?**
`start` runs it right now, in the current boot session only. `enable` creates the symlink so it starts automatically on future boots — it does NOT start it immediately. Production services need both, typically via `enable --now`.

**Q: Why `Restart=always` with `RestartSec=5` instead of restarting instantly?**
Instant restart on a crash-looping process (e.g. bad config after a bad deploy) hammers the CPU and can flood logs. A short delay throttles the restart rate while still self-healing.

**Q: How do you tail logs for a systemd service the same way you'd `tail -f` a file?**
`journalctl -u myapp -f` — follows live, and unlike a raw log file it survives log rotation automatically since journald manages storage itself.

**Q: What's the difference between `Type=simple` and `Type=forking`?**
`simple` assumes the command in `ExecStart` IS the long-running main process (typical for modern apps like uvicorn/gunicorn run in foreground). `forking` is for traditional daemons that fork into the background and exit the parent — systemd needs `PIDFile=` to track the real child in that case.
