# Linux — Hands-On Lab
**DevOps Track · Phase 1 Practical**

## Prerequisites

You need a real Linux shell — not just reading commands, actually typing them and seeing what breaks.

- **Best option**: a free-tier AWS/GCP/Oracle Cloud VM (Ubuntu 22.04/24.04), or any spare Raspberry Pi / old laptop with Ubuntu installed.
- **No cloud account**: WSL2 on Windows (`wsl --install`), or Docker Desktop + `docker run -it --name linuxlab ubuntu:24.04 bash` (fast, but you lose systemd — see the note in Lab 4).
- **macOS users**: the built-in shell is close enough for Labs 1-3 (BSD tool differences are called out inline), but Lab 4 (systemd) needs a real Linux box or VM — macOS has no systemd. A free option: [Killercoda](https://killercoda.com/) or [Play with Docker](https://labs.play-with-docker.com/) give you disposable Linux shells in a browser, no signup friction.
- `sudo` access is assumed for permission/user/service labs.

Work in a scratch directory so you can nuke it and restart: `mkdir -p ~/linux-lab && cd ~/linux-lab`.

---

## Lab 1: Permissions, Ownership, and a Broken Deploy Script

**Objective:** Get fluent with `chmod`/`chown`/`useradd` — the stuff that breaks deploys at 2am.

**Task:**
1. Create a file `deploy.sh` with `echo '#!/usr/bin/env bash' > deploy.sh` and try to run it with `./deploy.sh`. Note the error.
2. Fix it so it's executable by the owner only (not group, not others) — verify with `ls -l`.
3. Create a fake "secrets" file `secrets.env`, and set its permissions so ONLY the owner can read or write it, nobody else can do anything.
4. Create a new local user called `deploy` (don't worry about a real login shell setup, just create it) and a group called `appteam`. Add `deploy` to `appteam` using the flag that does NOT wipe their other group memberships.
5. Create a directory `/tmp/myapp-lab`, and change its ownership so user `deploy` and group `appteam` both own it, recursively.
6. Verify everything: read the permission bits back with `ls -la` and `id deploy`, and explain in one sentence why `chmod 777` would be wrong here.

<details>
<summary>Solution / walkthrough</summary>

```bash
# 1. Try running without exec bit
echo '#!/usr/bin/env bash' > deploy.sh
echo 'echo deploying...' >> deploy.sh
./deploy.sh
# bash: ./deploy.sh: Permission denied

# 2. Owner-only execute (755 would let group/others execute too — for a
# deploy script, 700 is safer if it's not meant to be run by anyone else)
chmod 700 deploy.sh
ls -l deploy.sh
# -rwx------ 1 you you ... deploy.sh
./deploy.sh   # now runs

# 3. Owner-only read/write, common for secrets/.env files
touch secrets.env
chmod 600 secrets.env
ls -l secrets.env
# -rw------- 1 you you ... secrets.env

# 4. Create user + group, add with -a (append, never plain -G)
sudo useradd -m deploy          # -m makes a home dir; skip if just testing groups
sudo groupadd appteam
sudo usermod -aG appteam deploy
id deploy
# uid=.. gid=.. groups=..(deploy),...(appteam)

# 5. Ownership, recursive
sudo mkdir -p /tmp/myapp-lab/logs
sudo chown -R deploy:appteam /tmp/myapp-lab
ls -la /tmp/myapp-lab

# 6. Why not 777:
# 777 makes the directory world-writable — ANY user on the box (or any
# process that got a foothold) could write/replace files inside it,
# including replacing your app's code or dropping malicious scripts.
# Permissions should be the minimum that lets the intended owner/group
# work, nothing broader — this is the "least privilege" principle
# applied at the filesystem level.
```

**Why `-aG` and not `-G`:** `usermod -G appteam deploy` (no `-a`) REPLACES the user's entire supplementary group list with just `appteam` — if `deploy` was already in `docker` or `sudo`, those memberships silently vanish. This is a real production incident category, not a theoretical warning.
</details>

---

## Lab 2: Log Triage — Find the Needle in the Haystack

**Objective:** Chain `grep`/`awk`/`sort`/`uniq` the way you would during an actual incident, without reaching for Python.

**Task:**

First, generate a fake nginx-style access log to work with:

```bash
cat > access.log << 'EOF'
10.0.0.5 - - [25/Jul/2026:10:01:02] "GET /api/orders HTTP/1.1" 200 512
10.0.0.7 - - [25/Jul/2026:10:01:05] "GET /api/orders HTTP/1.1" 500 128
10.0.0.5 - - [25/Jul/2026:10:01:07] "POST /api/users HTTP/1.1" 201 256
10.0.0.9 - - [25/Jul/2026:10:02:00] "GET /api/orders HTTP/1.1" 500 128
10.0.0.5 - - [25/Jul/2026:10:02:11] "GET /health HTTP/1.1" 200 32
10.0.0.7 - - [25/Jul/2026:10:03:22] "GET /api/orders HTTP/1.1" 500 128
10.0.0.3 - - [25/Jul/2026:10:03:40] "DELETE /api/orders/9 HTTP/1.1" 403 64
10.0.0.5 - - [25/Jul/2026:10:04:01] "GET /api/orders HTTP/1.1" 200 512
10.0.0.9 - - [25/Jul/2026:10:04:15] "GET /api/orders HTTP/1.1" 500 128
EOF
```

1. Count how many `500` status-code lines exist.
2. List each unique status code and how many times it occurs, sorted from most to least frequent.
3. Find which IP address is responsible for the most `500` errors.
4. Extract just the request paths (e.g. `/api/orders`) from every line, and print each unique path with a count.
5. Do all of #3 as a single one-liner pipeline.

<details>
<summary>Solution / walkthrough</summary>

```bash
# 1. Count 500s
grep -c " 500 " access.log
# 4

# 2. Status code frequency — status is field 8 here (space-delimited,
# quoted request string counts as multiple fields)
awk '{print $8}' access.log | sort | uniq -c | sort -rn
#    4 500
#    3 200
#    1 403
#    1 201

# 3. Which IP has the most 500s — filter first, then extract IP, then tally
grep " 500 " access.log | awk '{print $1}' | sort | uniq -c | sort -rn
#    2 10.0.0.7
#    2 10.0.0.9
# (tied — both are worth investigating, this is realistic: incidents
# rarely point at exactly one culprit on the first pass)

# 4. Unique request paths + counts (path is inside the quoted request,
# field 7 when the quote itself splits fields — verify by eyeballing
# one line first, log formats vary)
awk -F'"' '{print $2}' access.log | awk '{print $2}' | sort | uniq -c | sort -rn
#    6 /api/orders
#    1 /api/users
#    1 /health
#    1 /api/orders/9

# 5. One-liner for #3
grep " 500 " access.log | awk '{print $1}' | sort | uniq -c | sort -rn | head -1
```

**Why this matters:** this exact pipeline shape — `grep filter | awk extract-column | sort | uniq -c | sort -rn` — is the single most reusable pattern in production log triage. Memorize the shape, not just this example.
</details>

---

## Lab 3: Disk Full Emergency

**Objective:** Diagnose and fix a disk-full scenario the way the lesson's Senior Walkthrough describes, hands-on.

**Task:**
1. Create a directory tree that simulates a bloated log directory: make `~/linux-lab/var/log/app/` and inside it, write a 50MB file called `huge.log` (use `dd` or similar), plus a handful of small `.log.gz` files.
2. Use `du` to find which subdirectory of `~/linux-lab/var` is the biggest offender, one level at a time (simulate the "walk down from root" pattern from the lesson, just rooted at your lab dir instead of `/`).
3. Simulate the "deleted-but-still-open file" scenario: in one terminal/session, run `tail -f huge.log &` to keep a file descriptor open, then `rm huge.log` in the same shell. Check `df`-style behavior conceptually — explain in your own words why space isn't freed yet (you don't have a real filesystem you can `df` in a home dir, so this is a written explanation, not a command output).
4. Correctly free the file's actual content without waiting for the process to exit — figure out which command from the lesson does this without deleting the inode, and explain why `rm` alone wouldn't have helped here.
5. Clean up: kill the background `tail`, remove the lab files.

<details>
<summary>Solution / walkthrough</summary>

```bash
# 1. Build the bloated tree
mkdir -p ~/linux-lab/var/log/app
dd if=/dev/zero of=~/linux-lab/var/log/app/huge.log bs=1M count=50
touch ~/linux-lab/var/log/app/old1.log.gz ~/linux-lab/var/log/app/old2.log.gz

# 2. Walk down, one level at a time
du -h --max-depth=1 ~/linux-lab/var 2>/dev/null | sort -rh
du -h --max-depth=1 ~/linux-lab/var/log 2>/dev/null | sort -rh
du -h --max-depth=1 ~/linux-lab/var/log/app 2>/dev/null | sort -rh
ls -lhS ~/linux-lab/var/log/app   # huge.log jumps out immediately

# 3. Keep an fd open, then rm it
cd ~/linux-lab/var/log/app
tail -f huge.log &
TAIL_PID=$!
rm huge.log
# The directory entry ("filename") is gone — `ls` no longer shows huge.log.
# But the KERNEL keeps the actual disk blocks allocated as long as ANY
# process (here, the backgrounded tail) still holds an open file
# descriptor to it. This is exactly why `df` (which reports real block
# usage from the kernel) can show a filesystem as still full even after
# `rm`, while `du` (which walks the visible directory tree) sees nothing
# there anymore — they're looking at two different truths.

# 4. Free the content without waiting for the process to exit
# `rm` already ran — it wouldn't have helped anyway, since content isn't
# actually released until the fd closes. The real fix targets the fd:
ls -la /proc/$TAIL_PID/fd | grep deleted   # find the fd number pointing at the deleted file
# > /proc/$TAIL_PID/fd/<fd_number>          # truncate via the fd, frees blocks immediately
# (in a real incident you'd typically just restart/kill the offending
# process — the /proc/<pid>/fd/<n> truncate trick is the "can't restart
# it right now" escape hatch)

# 5. Cleanup
kill $TAIL_PID
rm -f ~/linux-lab/var/log/app/*.gz
rmdir ~/linux-lab/var/log/app ~/linux-lab/var/log ~/linux-lab/var 2>/dev/null
```

**Key insight to internalize:** `df` and `du` disagreeing is the #1 sign of a held-open deleted file — not filesystem corruption, not a `du` bug.
</details>

---

## Lab 4: Diagnose a Runaway Service (Production-Style Scenario)

**Objective:** A service is eating CPU and not responding. Find it, understand it, and fix it gracefully — without immediately reaching for `kill -9`.

> **Note:** this lab needs a real systemd-based Linux box (a cloud VM, WSL2, or a VM — NOT a plain `docker run ubuntu` container, which doesn't run systemd by default). If you only have Docker, do steps 1-4 (process hunting) against a background shell loop instead of a real systemd service, and skip the `systemctl`/`journalctl` portions.

**Task:**
1. Simulate a CPU hog: run `yes > /dev/null &` (this pins one core at 100% forever, harmlessly). Note its PID.
2. Using **two different tools**, confirm it's the top CPU consumer on the box.
3. Before killing anything, inspect what it actually is via `/proc/<pid>/` — confirm the exact command line that started it.
4. Kill it gracefully first, escalate only if needed, using the standard escalation pattern from the lesson (signal, wait, check, force if still alive).
5. **If you have a real systemd Linux box**: write a minimal systemd unit file for a fake "service" (use `ExecStart=/usr/bin/yes` as a stand-in for a real app) with `Restart=always` and `RestartSec=5`. Enable and start it, confirm it's running with `systemctl status`, then kill the underlying process manually and watch systemd restart it on its own. Check `journalctl` to see the restart event.
6. Clean up: stop and disable the unit, remove the unit file, `daemon-reload`.

<details>
<summary>Solution / walkthrough</summary>

```bash
# 1. Start the hog
yes > /dev/null &
HOG_PID=$!
echo "hog pid: $HOG_PID"

# 2. Confirm via two tools
top -b -n 1 | head -15                    # snapshot mode, one iteration
ps aux --sort=-%cpu | head -5             # static, sorted

# 3. Inspect before touching it
cat /proc/$HOG_PID/cmdline; echo
cat /proc/$HOG_PID/status | head -5

# 4. Graceful escalation pattern
kill $HOG_PID                              # SIGTERM
sleep 5
kill -0 $HOG_PID 2>/dev/null && kill -9 $HOG_PID   # only force if still alive
# `yes` actually dies cleanly on SIGTERM, so the -9 branch usually
# won't even trigger — that's the point: always give SIGTERM a chance.

# 5. systemd unit (requires real systemd)
sudo tee /etc/systemd/system/lab-hog.service > /dev/null << 'EOF'
[Unit]
Description=Lab CPU hog (stand-in for a real app)

[Service]
Type=simple
ExecStart=/usr/bin/yes
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload         # REQUIRED after creating/editing a unit file
sudo systemctl enable --now lab-hog
systemctl status lab-hog             # should show "active (running)"

# Now kill the underlying process directly and watch it come back
MAINPID=$(systemctl show -p MainPID lab-hog --value)
sudo kill -9 $MAINPID
sleep 6
systemctl status lab-hog             # active again, with a NEW PID

journalctl -u lab-hog -n 20 --no-pager   # shows the stop + restart events

# 6. Cleanup
sudo systemctl disable --now lab-hog
sudo rm /etc/systemd/system/lab-hog.service
sudo systemctl daemon-reload
```

**Why this matters in production:** this is exactly the pattern that separates a plain `nohup ./app &` from a real deployment. `Restart=always` + `RestartSec=5` self-heals a crash without you paging anyone — but it will also happily mask a crash-looping bad deploy if you don't also watch `journalctl` and alert on restart frequency. Auto-restart is not the same as "the problem is fixed."
</details>

---

## Self-Check Checklist

- [ ] Can you explain, without looking it up, why `chmod 600 id_rsa` matters and what breaks if you skip it?
- [ ] Can you set up a user + group and add the user to a supplementary group WITHOUT wiping their existing group memberships?
- [ ] Can you write a one-liner that finds the top 5 IPs hitting a specific endpoint from a raw access log?
- [ ] Can you explain why `df` and `du` sometimes disagree, and fix it without restarting the offending process?
- [ ] Can you name the difference between `find` and `locate`, and say when you'd reach for each?
- [ ] Given a PID, can you find out exactly what command started it and what files/sockets it has open?
- [ ] Can you walk through the graceful kill escalation (SIGTERM → wait → check → SIGKILL) from memory?
- [ ] Can you write a working systemd unit file from scratch for a Python/uvicorn app, including `Restart=always`?
- [ ] Do you know the one command you always run after editing a systemd unit file, and why forgetting it is a classic mistake?
- [ ] Can you find what's listening on a given port and kill it, using either `ss` or `lsof`?
