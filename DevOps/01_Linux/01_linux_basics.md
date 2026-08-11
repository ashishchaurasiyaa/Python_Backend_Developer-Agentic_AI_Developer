# Linux Basics — Distros, Filesystem, Permissions, Users, Shells

**DevOps Track · Phase 1: Linux**

## Quick Concepts

| Concept | One-line definition |
|---------|---------------------|

| **Distribution (distro)** | A packaged Linux OS (kernel + userland + package manager) — Ubuntu, CentOS, Amazon Linux, Debian, RHEL |
| **Package manager** | Tool that installs/updates/removes software (`apt`, `yum`, `dnf`) |
| **FHS** | Filesystem Hierarchy Standard — the standard directory layout every distro follows |
| **Permission** | `rwx` (read/write/execute) applied to user/group/others |
| **UID/GID** | Numeric IDs identifying a user/group under the hood |
| **sudo** | "Substitute user do" — run a command as another user (usually root) with logging |
| **Environment variable** | Key-value pair processes inherit (`PATH`, `HOME`, `USER`) |
| **Shell** | The command interpreter you type into (`bash`, `zsh`, `sh`, `fish`) |
| **POSIX** | Portability standard — scripts written to POSIX `sh` run on almost any Unix-like system |

---

## Quick Concepts — In Depth

### 1. Distribution (Distro)

`Distribution = Linux Kernel + Userland + Package Manager + Init System + Default Config`

The kernel is the same across all distros (give or take version). What differs is **everything around it**:

```
Linux Kernel
    │
    ├── Userland (GNU tools: ls, cp, grep, bash, glibc)
    ├── Init system (systemd, OpenRC, SysV)
    ├── Package manager (apt, dnf, apk)
    ├── Default shell (bash, ash)
    ├── Default filesystem layout
    └── Release cycle (LTS, rolling, stable)
```

**Why the same kernel produces totally different systems:**

```bash
# Ubuntu — glibc, bash, apt, systemd, large package repo
cat /etc/os-release
# NAME="Ubuntu"  VERSION="22.04.3 LTS"

# Alpine — musl libc (NOT glibc), ash shell, apk, OpenRC, ~5MB base image
cat /etc/os-release
# NAME="Alpine Linux"  VERSION_ID="3.19.0"

# Run the same binary on both:
./my-go-binary     # works on Ubuntu (glibc)
./my-go-binary     # might fail on Alpine (musl) if compiled against glibc
# Error: "not found" or "illegal instruction" — not a PATH problem, it's a libc mismatch
```

**Release cycle matters in production:**

```
LTS (Long-Term Support) — Ubuntu 22.04, 24.04
   → 5 years of security patches
   → Safe to deploy, don't need to upgrade OS every year
   → What you pick for production servers

Rolling release — Arch, openSUSE Tumbleweed
   → Always latest packages, higher breakage risk
   → Never for prod servers

RHEL/CentOS model:
   → RHEL 9 = paid, 10-year support cycle
   → CentOS Stream = free, rolling upstream to RHEL (not a stable clone)
   → AlmaLinux / Rocky Linux = free, stable RHEL 1:1 clones
```

**Checking which distro you're on:**

```bash
cat /etc/os-release        # standard — works everywhere
lsb_release -a             # Ubuntu/Debian
cat /etc/redhat-release    # RHEL/CentOS/Amazon Linux
uname -r                   # kernel version only (not distro)
hostnamectl                # distro + kernel + arch in one shot
```

---

### 2. Package Manager

A tool that installs, upgrades, removes, and resolves dependencies for software. It is the **only safe way to install software** on a Linux server.

**The two-layer architecture:**

```
You run:   sudo apt install nginx
                │
         ┌──────▼──────────────────────────────┐
         │  APT (high-level)                    │
         │  - Downloads package index from repos │
         │  - Resolves dependency tree           │
         │  - Checks for conflicts               │
         └──────┬───────────────────────────────┘
                │
         ┌──────▼──────────────────────────────┐
         │  dpkg (low-level)                    │
         │  - Unpacks and installs .deb file    │
         │  - Runs pre/post install scripts     │
         │  - Updates installed packages DB     │
         └─────────────────────────────────────┘
```

**What a package actually contains:**

```bash
# Inspect a .deb package without installing
dpkg -c nginx.deb      # list contents
dpkg -I nginx.deb      # metadata (dependencies, version, maintainer)

# A .deb contains:
# - Binary files    → /usr/bin, /usr/sbin
# - Config files    → /etc/nginx/
# - Service files   → /lib/systemd/system/
# - Man pages       → /usr/share/man/
# - Pre/post scripts → run before/after install (create users, set permissions)
```

**Repository system — where packages come from:**

```bash
# Ubuntu repos defined in:
cat /etc/apt/sources.list
cat /etc/apt/sources.list.d/

# A repo entry:
# deb https://deb.nodesource.com/node_20.x jammy main
#  │   └── URL                              └── codename
#  └── binary packages

# Adding a third-party repo (Node.js):
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install -y nodejs
# That script: adds repo URL, adds GPG signing key, runs apt update
```

**Why `apt update` before `apt install`:**

```bash
# apt keeps a LOCAL CACHE of the package index — goes stale

sudo apt update         # download fresh index from repos
sudo apt install nginx  # install from fresh index

# Without apt update: might install old version or fail with "package not found"
```

**Holding a package version (important in prod):**

```bash
sudo apt-mark hold nginx             # pin version — apt upgrade won't touch it
sudo apt-mark showhold               # list held packages
sudo apt-mark unhold nginx           # release hold

apt-cache show nginx | grep Version  # see available versions
sudo apt install nginx=1.24.0-1ubuntu1  # install exact version
```

**Cleaning up:**

```bash
sudo apt autoremove     # remove packages no longer needed by anything
sudo apt clean          # delete downloaded .deb files from cache
df -h /var/cache/apt/   # see how much space the cache uses
```

---

### 3. FHS (Filesystem Hierarchy Standard)

A specification that defines **where specific types of files must live** on a Linux system, so software can find what it needs without being told where to look.

**Why it exists:**

```
Without FHS:
  nginx config in /opt/nginx/conf/
  Apache config in /usr/local/apache/conf/
  Every app makes up its own layout — no tool can find logs/configs predictably

With FHS:
  Every app's config  → /etc/<appname>/
  Every app's logs    → /var/log/<appname>/
  Every binary        → /usr/bin/ or /usr/local/bin/
  Any script knows to look in /var/log/ for logs — always
```

**The two axes FHS uses:**

```
Static vs Variable:
  Static   = doesn't change after install (/bin, /lib, /usr)
  Variable = changes as system runs (/var/log, /var/lib, /run)

Shareable vs Unshareable:
  Shareable   = can be shared via NFS (/usr, /home)
  Unshareable = machine-specific (/etc, /boot, /var/run)
```

**Memory hook:**

```
Something broken?          → /var/log/
Config wrong?              → /etc/
App deployed?              → /opt/myapp/
Running process info?      → /proc/<PID>/
System binaries?           → /usr/bin/, /usr/sbin/
Custom compiled software?  → /usr/local/bin/
Temporary scratch space?   → /tmp/
Hardware/device info?      → /sys/, /dev/
```

---

### 4. Permission (rwx)

Every file and directory has three permission sets — owner (u), group (g), others (o) — each with read (r=4), write (w=2), execute (x=1) bits.

**On a FILE vs on a DIRECTORY:**

```
On a FILE:
  r = read contents (cat, cp, less)
  w = modify contents (vim, truncate)
  x = run as a program (./script.sh)

On a DIRECTORY:
  r = list contents (ls)
  w = create/delete/rename files inside
  x = enter/traverse (cd, access files inside)
  ← x on directories is the most commonly forgotten
```

**The check order stops at first match:**

```bash
# Linux stops at the FIRST matching set — doesn't combine

ls -la secret.txt
# -rw-rw---- deploy www-data secret.txt
# owner=rw, group=rw, others=none

# You ARE "deploy" (owner) AND in group "www-data"
# You get rw — from the OWNER set only
# The group set is never consulted
# You cannot use the group to RESTRICT the owner
```

**Why the three-way split (u/g/o) covers most real cases:**

```
Unix was designed for shared university computers:
  - Each person has a login (u)
  - Research groups share files (g)
  - Public data is world-accessible (o)

Real-world mapping:
  - App owned by deploy user (u)
  - Readable by www-data group for nginx (g)
  - Not accessible to anyone else (o = ---)
```

---

### 5. UID/GID

Every user has a numeric User ID (UID) and primary Group ID (GID). The kernel tracks numbers — names are just human-readable labels resolved via `/etc/passwd`.

**Why numbers, not names:**

```
Names are mutable — you can rename a user.
Numbers are permanent — stored in file inodes on disk.

If you rename user "deploy" to "deployer":
  UID is still 1001. Files still show UID 1001. Name resolves correctly.

If you DELETE user "deploy" and CREATE a NEW user with UID 1001:
  All of "deploy"'s old files now appear owned by the new user.
  This is a real security issue when recycling UIDs after deletion.
```

**Seeing the raw numbers:**

```bash
ls -ln /opt/myapp        # -n = numeric UIDs/GIDs, no name resolution
# -rw-r--r--  1001  1001  app.py
#                ↑     ↑
#               UID   GID

stat /opt/myapp/app.py
# Uid: ( 1001/  deploy)   Gid: ( 1001/  deploy)
```

**UID ranges:**

```
0           → root — bypasses ALL permission checks
1–99        → static system accounts (distro-reserved: daemon, bin, sys)
100–999     → dynamic system accounts (nginx→www-data:33, postgres:113)
1000+       → real human users
65534       → "nobody" — minimal access (NFS anonymous, sandboxed processes)
```

**Why UID 0 is different from just "any high-privilege user":**

```bash
# Root (UID 0) bypasses permission checks entirely:
chmod 000 secret.txt        # no one can read it
sudo cat secret.txt         # root reads it anyway — check skipped

# sudo doesn't give you UID 0 permanently:
id                          # still shows your UID
sudo id                     # shows uid=0(root)
```

**GID and the setgid directory problem:**

```bash
# Alice (primary group: alice) creates file in /shared/project
# → file owned by group "alice", not group "project"
# Bob (in group "project") can't read it

# Fix: setgid on the directory
chmod g+s /shared/project
# New files now inherit the directory's group, not creator's primary group
```

---

### 6. sudo

`sudo` = "Substitute User Do" — runs a single command as another user (usually root), with authentication, authorization checking, and a full audit log.

**What sudo does that `su` does not:**

```
su root:
  - Asks for ROOT's password (shared secret — bad)
  - Opens a full shell as root (no scoping — bad)
  - Logs "su was used" — no detail on what was done

sudo command:
  - Asks for YOUR password (no shared secret)
  - Runs ONE command (scoped — grant "restart nginx" only)
  - Logs exact command with timestamp, user, tty
  - 15-minute credential cache
  - Can be restricted per user, per command, per host
```

**What the audit log looks like:**

```bash
sudo grep sudo /var/log/auth.log
# Aug 11 09:15:32 webserver sudo: deploy : TTY=pts/0 ;
#   PWD=/opt/myapp ; USER=root ; COMMAND=/usr/bin/systemctl restart nginx

# Records: timestamp, who ran it, from where, what, allowed or DENIED
```

**The sudoers rule anatomy:**

```
deploy   ALL=(ALL)   NOPASSWD: /usr/bin/systemctl restart myapp
  │       │    │         │              └── specific command allowed
  │       │    │         └── no password prompt
  │       │    └── run as any user
  │       └── from any host
  └── who this rule applies to (%groupname for a group)
```

**`sudo -u` — become any user, not just root:**

```bash
sudo -u postgres psql                                   # manage DB as postgres
sudo -u www-data ls /var/www/html                       # test nginx permissions
sudo -u myapp /opt/myapp/venv/bin/python check.py       # reproduce permission error
```

**Least-privilege sudoers pattern:**

```bash
# BAD — grants full root:
deploy  ALL=(ALL:ALL)  ALL

# BETTER — only specific restart:
deploy  ALL=(ALL)  NOPASSWD: /usr/bin/systemctl restart myapp

# BEST for CI/CD — only a specific deploy script:
ci-runner  ALL=(ALL)  NOPASSWD: /opt/myapp/scripts/deploy.sh
# The script only does what it's designed to — no shell escape possible
```

---

### 7. Environment Variable

A key-value pair stored in a process's environment — a private dictionary every process inherits from its parent at launch.

**Why they exist — the problem they solve:**

```
Without env vars:
  - Config is hardcoded in the binary
  - Different environments (dev/staging/prod) need different builds
  - Secrets live in source code
  - Config change = code change + redeploy

With env vars:
  - Same binary, different environment = different behavior
  - Secrets never touch source code
  - Config change = update env var, restart process
```

**The fork/exec model — how inheritance works:**

```
bash → export DB_URL="postgres://localhost/mydb"

bash forks a child: python app.py
  └── child gets a COPY of bash's env at fork time
      └── python sees DB_URL = "postgres://localhost/mydb"
          └── python forks: subprocess.run(["psql"])
              └── psql also inherits DB_URL

Key: it's a COPY at fork time.
Child modifying env doesn't affect parent.
Parent modifying env after fork doesn't affect child.
```

**Env vars vs config files — when to use which:**

```
Use env vars for:
  - Secrets (DB passwords, API keys) — never in git-committed files
  - Per-environment values (dev vs prod hostname, log level, debug mode)
  - Simple on/off feature flags

Use config files for:
  - Complex structured config (YAML/TOML with many nested options)
  - Config that needs inline comments
  - Large lists or maps
  - Values that rarely change

Example:
  DATABASE_URL=postgres://...    ← env var (secret, per-environment)
  /etc/nginx/nginx.conf          ← config file (complex, structured, not secret)
```

---

### 8. Shell

A program that acts as the command interpreter between you and the kernel. You type text, the shell parses it, translates it into system calls, and shows you the result.

**What the shell actually does with your command:**

```bash
# You type:
ls -la /opt/myapp | grep deploy

# Shell does:
# 1. Parse command line — find the pipe
# 2. Look up "ls" in PATH → /usr/bin/ls
# 3. Look up "grep" in PATH → /usr/bin/grep
# 4. Create a pipe (kernel buffer connecting the two)
# 5. fork() → child 1: execve("/usr/bin/ls", ["-la", "/opt/myapp"], env)
#    stdout → write end of pipe
# 6. fork() → child 2: execve("/usr/bin/grep", ["deploy"], env)
#    stdin → read end of pipe
# 7. Wait for both children to finish
# 8. Print next prompt
```

**The shell is NOT the terminal:**

```
Terminal emulator (iTerm2, GNOME Terminal):
  - The window you see
  - Renders text, handles fonts, colours
  - Creates a pseudo-terminal device (/dev/pts/0)

Shell (bash, zsh, fish):
  - The program running INSIDE the terminal
  - Reads input, interprets commands, manages processes

You can swap the shell without swapping the terminal:
  chsh -s /usr/bin/zsh    # change default shell for your user
  exec zsh                # replace current bash with zsh right now
```

**The shell as a programming language:**

```bash
#!/usr/bin/env bash
set -euo pipefail

log() { echo "[$(date +%T)] $*"; }

if [[ ! -d "/opt/myapp" ]]; then
    log "Deploy dir missing, creating..."
    mkdir -p "/opt/myapp"
fi

for server in web1 web2 web3; do
    log "Deploying to $server"
    ssh "$server" "cd /opt/myapp && git pull"
done
```

**Interactive features for daily work:**

```bash
# History
!!          # run last command
!$          # last argument of previous command
Ctrl+R      # reverse-search history

# Navigation
Ctrl+A      # go to start of line
Ctrl+E      # go to end of line
Ctrl+W      # delete word backward

# Job control
Ctrl+Z      # suspend current process
bg          # resume in background
fg          # bring to foreground
jobs        # list background/suspended jobs
command &   # run in background immediately
```

---

### 9. POSIX

Portable Operating System Interface — a family of IEEE standards that define the API, shell syntax, and utilities that a Unix-like system must provide, so software written to POSIX runs on any compliant system without modification.

**Why it was created:**

```
In the 1980s: dozens of competing Unix variants (BSD, SysV, HP-UX, AIX, Solaris)
Problem: code written for one Unix wouldn't compile/run on another
Solution: POSIX (1988) — agree on a standard API that all must implement

Today: Linux, macOS, FreeBSD, Solaris are all POSIX-compliant (or close to it)
This is why a shell script written on macOS mostly runs on Ubuntu.
```

**What POSIX specifies:**

```
1. C API (system calls):
   open(), read(), write(), fork(), exec(), wait()
   file permissions, signals, pipes, sockets
   C code using only POSIX calls → compiles on Linux, macOS, FreeBSD

2. Shell language (sh):
   Basic variable assignment, if/for/while
   [ ] test command, command substitution $()
   Does NOT include bash arrays, [[ ]], brace expansion

3. Standard utilities:
   ls, cp, mv, rm, find, grep, sed, awk, sort, uniq, cut
   Their flags and behavior are standardized
   grep -E is POSIX; grep -P (Perl regex) is NOT

4. Environment:
   PATH, HOME, USER, TERM must exist
   Mandatory signal names (SIGTERM, SIGKILL, etc.)
```

**POSIX sh vs bash — what's safe to use where:**

```bash
# POSIX sh (#!/bin/sh) — runs on Alpine (dash), macOS, any Linux
command -v python3      # check if command exists
. ~/.profile            # source a file (not 'source')
[ -f /etc/file ]        # test condition
result=$(command)       # command substitution
"$@"                    # all arguments

# Bash-only — breaks in /bin/sh on Alpine/Debian
[[ "$x" =~ regex ]]     # regex test
arr=(1 2 3)             # arrays
echo {1..10}            # brace expansion
source file             # use '.' instead
```

**POSIX and portability — the Alpine Docker scenario:**

```bash
# Works on Ubuntu, breaks in Alpine:
#!/bin/bash
servers=(web1 web2 web3)     # bash array
for s in "${servers[@]}"; do ssh $s "systemctl restart app"; done

# Alpine: "bash: not found"

# Dockerfile fix 1 — install bash:
# RUN apk add --no-cache bash

# Fix 2 — rewrite to POSIX sh:
#!/bin/sh
for s in web1 web2 web3; do  # no arrays needed
    ssh "$s" "systemctl restart app"
done
```

**POSIX signals — universal process control:**

```bash
kill -SIGTERM <PID>   # 15 — polite shutdown (process can clean up)
kill -SIGKILL <PID>   # 9  — forceful kill (cannot be caught or ignored)
kill -SIGHUP  <PID>   # 1  — many daemons reload config on this signal
kill -SIGINT  <PID>   # 2  — interrupt (same as Ctrl+C)

# Standard shutdown sequence:
kill -SIGTERM <PID>
sleep 10
kill -0 <PID> 2>/dev/null && kill -SIGKILL <PID>  # force if still alive

# Why SIGTERM before SIGKILL:
# SIGTERM: process flushes buffers, closes DB connections, removes lock files
# SIGKILL: skips all that — use only when SIGTERM fails
```

**macOS vs Linux — POSIX edge cases:**

```bash
# macOS ships BSD tools, not GNU — some flags differ:

# GNU (Linux):
sed -i 's/foo/bar/' file    # edit in-place, no backup
date -d "2 days ago"        # date arithmetic

# BSD (macOS):
sed -i '' 's/foo/bar/' file # empty string required after -i
date -v-2d                  # different flag

# Portable workaround:
python3 -c "
import sys
content = open(sys.argv[1]).read().replace('foo','bar')
print(content)
" file.txt
```

---

### How All Nine Concepts Connect

```
DISTRO
  └── ships a PACKAGE MANAGER
      └── installs software into FHS directories
          ├── binaries → /usr/bin/  (run via the SHELL using PATH)
          ├── configs  → /etc/      (read by processes)
          └── creates service USERs (UID/GID)
              └── files owned by those UIDs/GIDs
                  └── access controlled by PERMISSIONS (rwx)
                      └── sudo allows controlled UID-switching
                          └── all processes inherit ENV VARS
                              └── scripts written to POSIX work everywhere
```

A broken deploy is almost always one of:

```
Wrong UID owns the files         → Permission denied
Missing env var                  → App crashes with KeyError / undefined
Bash-ism in a POSIX-only env     → Script fails silently or cryptic error
Package not installed             → "command not found" at runtime
Wrong directory (violates FHS)   → Config not found, log not written
```

---

## Why This Matters for Backend/DevOps Work

```
Every server you deploy to, every Docker base image, every EC2 instance,
every Kubernetes node — is Linux underneath.

Things you cannot avoid once you own infra:
   - Choosing a base image / AMI (which distro, why)
   - Fixing a "permission denied" on a deploy script at 2am
   - Creating a locked-down service user for your app (never root)
   - Reading /etc/passwd or sudoers when access is misconfigured
   - Debugging a broken PATH that makes a cron job silently fail

Backend devs who only ever `docker run` and never look inside the
container hit a wall the moment something breaks in production.
```

---

## Linux Distributions

| Distro | Package Manager | Base | Typical Use Case |
|--------|-----------------|------|------------------|
| **Ubuntu** | `apt` (APT/dpkg, `.deb`) | Debian | Most common cloud/dev default. Huge community, predictable LTS releases (20.04, 22.04, 24.04) |
| **Debian** | `apt` (APT/dpkg, `.deb`) | — | Stability-first, minimal, common for embedded/servers wanting long-term boringness |
| **CentOS** (Stream now) | `yum` / `dnf` (RPM, `.rpm`) | RHEL | Historically the free RHEL clone for production servers; CentOS Stream is now a rolling upstream to RHEL, not a 1:1 clone anymore |
| **RHEL** (Red Hat Enterprise Linux) | `dnf` (RPM) | — | Enterprise, paid support, common in banks/regulated industries |
| **Amazon Linux 2/2023** | `yum` (AL2) / `dnf` (AL2023) | RHEL-ish, AWS-optimized | Default for EC2/ECS/Lambda — tuned for AWS, free, tight AWS SDK/CLI integration |
| **Alpine** | `apk` | musl libc, not glibc | Tiny Docker base images (~5MB) — fast pulls, but musl can break glibc-only binaries |

### Package Manager Cheat Sheet

```bash
# Debian/Ubuntu (apt)
sudo apt update                    # refresh package index
sudo apt upgrade                   # upgrade installed packages
sudo apt install nginx             # install
sudo apt remove nginx              # remove (keep config)
sudo apt purge nginx               # remove + config
apt list --installed | grep nginx  # check installed
apt-cache search redis             # search

# RHEL/CentOS/Amazon Linux 2 (yum)
sudo yum update
sudo yum install nginx
sudo yum remove nginx
yum list installed | grep nginx
yum search redis

# RHEL 8+/CentOS Stream/Amazon Linux 2023 (dnf — yum's successor)
sudo dnf install nginx
sudo dnf remove nginx
dnf list installed
dnf search redis

# Alpine (apk — common inside Docker)
apk add --no-cache curl
apk del curl
```

### Two-Layer Architecture — Both Families Have It

```
High-level (dependency resolver):   apt          dnf/yum
                                     │               │
Low-level (install the package):    dpkg            rpm

# Bypass high-level layer (airgapped servers / debugging):
dpkg -i package.deb     # installs without resolving dependencies
rpm -ivh package.rpm    # installs without resolving dependencies

# Inspect installed packages:
dpkg -L nginx           # list files installed by package (Debian)
dpkg -S /usr/bin/nginx  # which package owns this file (Debian)
rpm -ql nginx           # list files installed by package (RHEL)
rpm -qf /usr/bin/nginx  # which package owns this file (RHEL)
```

### Why DNF Replaced YUM

```
YUM had a slow dependency resolver written in Python —
on large package sets it could take minutes to calculate
what to install. DNF rewrote the resolver in C (libsolv),
making it significantly faster with better conflict detection.
Commands are nearly identical:

yum install nginx   →   dnf install nginx
yum update          →   dnf upgrade
yum list installed  →   dnf list installed
```

### Senior Tip

```
apt = .deb packages, dependency resolution via APT
yum/dnf = .rpm packages, dependency resolution via RPM + repo metadata
dnf is yum's modern replacement (faster resolver, same commands mostly)

Pick your distro based on:
  - What your cloud provider optimizes for (AWS → Amazon Linux for EC2)
  - What your team already knows (Ubuntu is the safe default)
  - Image size if it's a container base (Alpine/distroless for prod images)
  - Compliance requirements (RHEL if you need paid enterprise support/certs)
```

---

## File System Hierarchy Standard (FHS)

### The Mental Model First

The Linux filesystem is a **single unified tree** rooted at `/`. There are no drive letters (no `C:\`, `D:\`). Everything — local disks, network shares, USB drives, virtual kernel interfaces — is mounted somewhere in this one tree.

```
Windows:                        Linux:
C:\Windows\System32             /usr/lib
C:\Users\ashish                 /home/ashish
D:\Projects                     /mnt/projects  (or anywhere you mount it)
\\server\share                  /mnt/nfs/share
```

### The Full Directory Tree

```
/
├── bin       → essential user binaries (ls, cp, mv, cat, bash)
├── sbin      → essential system/admin binaries (fdisk, ifconfig, init)
├── lib       → shared libraries for /bin and /sbin
├── lib64     → 64-bit shared libraries
├── usr       → the bulk of installed software
│   ├── bin   → user commands (git, python3, nginx, curl)
│   ├── sbin  → admin commands (useradd, sshd, cron)
│   ├── lib   → libraries for /usr/bin and /usr/sbin
│   ├── local → locally compiled/installed software (not from package manager)
│   │   ├── bin
│   │   ├── lib
│   │   └── share
│   ├── share → architecture-independent data (man pages, icons, locale)
│   └── include → C header files
├── etc       → system-wide configuration files
├── var       → variable data (logs, databases, mail, spool)
├── home      → user home directories
├── root      → root user's home directory
├── opt       → optional/third-party software
├── tmp       → temporary files (cleared on reboot)
├── proc      → virtual: live kernel/process info
├── sys       → virtual: kernel, hardware, device info
├── dev       → device files
├── run       → runtime data (PIDs, sockets) — cleared on boot
├── boot      → bootloader, kernel image, initrd
├── mnt       → manual mount points
└── media     → auto-mount points (USB, CD-ROM)
```

### /bin vs /usr/bin History

```
Originally (1970s): / was on a small root disk, /usr on a larger second disk.
/bin held only what was needed to boot and repair before /usr was mounted.

Modern Linux (most distros since ~2012):
/bin  → symlink to /usr/bin
/sbin → symlink to /usr/sbin
/lib  → symlink to /usr/lib

ls -la /bin
# lrwxrwxrwx  /bin -> usr/bin

Everything is in /usr now. The split is historical artifact.
```

### /etc — Configuration

Every system-wide config file lives here:

```bash
/etc/
├── passwd          # user accounts
├── shadow          # password hashes (root-only)
├── group           # groups
├── sudoers         # sudo rules
├── hosts           # static hostname→IP mappings
├── hostname        # this machine's hostname
├── resolv.conf     # DNS resolver config
├── fstab           # filesystems to mount at boot
├── crontab         # system-wide cron jobs
├── environment     # system-wide env vars (KEY=VALUE, no shell syntax)
├── profile         # system-wide shell config (login shells)
├── profile.d/      # drop-in shell scripts sourced by /etc/profile
├── ssh/
│   ├── sshd_config     # SSH server config
│   └── ssh_config      # SSH client config (system-wide)
├── nginx/
│   ├── nginx.conf
│   ├── sites-available/
│   └── sites-enabled/
├── systemd/
│   └── system/         # systemd unit files you create
├── cron.d/             # per-package cron jobs
├── apt/
│   └── sources.list.d/ # APT repository definitions
└── ssl/
    └── certs/          # trusted CA certificates
```

```bash
# /etc/hosts — override DNS locally
cat /etc/hosts
# 127.0.0.1   localhost
# 127.0.0.1   myapp.local      ← add for local dev
# 10.0.1.50   db-primary       ← reference internal servers by name

# /etc/fstab — what gets mounted at boot
# UUID=abc123  /           ext4  defaults  0 1
# UUID=def456  /boot       ext4  defaults  0 2
# 10.0.1.10:/exports  /mnt/nfs  nfs  defaults  0 0

# /etc/resolv.conf — DNS config
# nameserver 8.8.8.8
# search internal.company.com   ← appended to bare hostnames
# So `ping db` resolves as `ping db.internal.company.com`
```

### /var — Variable Data

```bash
/var/
├── log/            ← first place to check when something breaks
│   ├── syslog          # Ubuntu/Debian: kernel + system messages
│   ├── messages         # RHEL/Amazon Linux: kernel + system messages
│   ├── auth.log         # authentication (sudo, ssh, su)
│   ├── kern.log         # kernel messages only
│   ├── dpkg.log         # package installs/removals
│   ├── nginx/
│   │   ├── access.log   # every HTTP request
│   │   └── error.log    # nginx errors
│   └── myapp/           # your app's logs
├── lib/            # persistent service state
│   ├── postgresql/ # postgres data directory (if default)
│   └── apt/        # dpkg package database
├── spool/          # queued work
│   ├── cron/       # per-user crontabs (edited via crontab -e)
│   └── mail/       # local mail queue
├── run/            # runtime data (often /run symlink)
│   ├── sshd.pid
│   └── nginx.pid
├── tmp/            # temp files that survive reboots (unlike /tmp)
└── cache/          # cached data that can be regenerated
    └── apt/        # downloaded .deb package cache
```

**Reading logs:**

```bash
tail -f /var/log/nginx/access.log               # follow in real time
tail -f /var/log/nginx/access.log /var/log/nginx/error.log  # multiple files
tail -n 100 /var/log/syslog                     # last 100 lines
grep "ERROR" /var/log/myapp/app.log             # search
grep "ERROR" /var/log/myapp/app.log | grep "2026-08-11"

# Systemd journal (modern alternative to syslog)
journalctl -u nginx                             # logs for nginx service
journalctl -u myapp -f                          # follow myapp logs
journalctl -u myapp --since "1 hour ago"
journalctl -u myapp --since "2026-08-11 09:00" --until "2026-08-11 10:00"
journalctl -p err                               # only errors and above
journalctl --disk-usage                         # journal disk usage
```

**Log rotation:**

```bash
# logrotate config example at /etc/logrotate.d/nginx:
# /var/log/nginx/*.log {
#     daily
#     rotate 14          ← keep 14 rotated files
#     compress           ← gzip old logs
#     delaycompress
#     postrotate
#         nginx -s reopen
#     endscript
# }

# Rotated files:
# access.log        ← current
# access.log.1      ← yesterday
# access.log.2.gz   ← day before (compressed)
```

### /proc — Live Kernel and Process Window

`/proc` is a virtual filesystem — nothing stored on disk. Kernel generates contents on the fly:

```bash
# Every running process has a directory named by its PID
cat /proc/1234/status          # process name, state, UID, GID, memory
cat /proc/1234/cmdline         # exact command line it was started with
cat /proc/1234/environ         # environment variables the process sees
ls  /proc/1234/fd/             # file descriptors open (links to actual files)
cat /proc/self/status          # info about the process running the cat command

# System-wide info
cat /proc/cpuinfo              # CPU model, cores, features
cat /proc/meminfo              # RAM: total, free, cached, swap
cat /proc/uptime               # seconds since boot
cat /proc/loadavg              # 1/5/15 min load averages
cat /proc/version              # kernel version
cat /proc/mounts               # currently mounted filesystems
cat /proc/net/dev              # network interface stats

# Practical uses
cat /proc/<PID>/status | grep State
# State: S (sleeping)  R (running)  D (uninterruptible I/O wait)  Z (zombie)

cat /proc/<PID>/status | grep -E "VmRSS|VmSize"
# VmSize: total virtual memory
# VmRSS:  actual RAM in use (Resident Set Size)

# Tune kernel parameters at runtime (no reboot)
echo 10 > /proc/sys/vm/swappiness
sysctl vm.swappiness=10        # same thing, persistent via sysctl.conf
```

### /sys — Hardware and Kernel Internals

```bash
# Network interfaces
ls /sys/class/net/
cat /sys/class/net/eth0/speed         # interface speed in Mbps
cat /sys/class/net/eth0/carrier       # 1=link up, 0=link down

# Disk info
cat /sys/block/sda/size               # disk size in 512-byte sectors
cat /sys/block/sda/queue/scheduler    # I/O scheduler

# CPU frequency
cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor
# performance / powersave / ondemand
```

### /dev — Device Files

```bash
/dev/
├── sda           # first SATA/SCSI disk
├── sda1          # first partition of sda
├── nvme0n1       # first NVMe SSD
├── nvme0n1p1     # first partition of nvme0n1
├── tty           # current terminal
├── pts/          # pseudo-terminals (SSH sessions, terminal windows)
├── null          # black hole — discard anything written here
├── zero          # infinite stream of null bytes
├── random        # cryptographically secure random bytes
└── urandom       # non-blocking random (safe for most uses)
```

```bash
# /dev/null — discard output
command > /dev/null            # discard stdout
command 2> /dev/null           # discard stderr
command > /dev/null 2>&1       # discard both

# Cron jobs that shouldn't email on success:
0 2 * * * /opt/scripts/backup.sh > /dev/null 2>&1

# /dev/urandom — generate random data
dd if=/dev/urandom bs=16 count=1 2>/dev/null | base64  # random 16-byte key
openssl rand -hex 32                                    # easier way

# Inspect disks
lsblk                  # list block devices in tree format
lsblk -f               # include filesystem type and UUID
fdisk -l /dev/sda      # partition table
df -h                  # disk space usage by mounted filesystem
```

### /tmp — Temporary Files

```bash
# /tmp is world-writable with sticky bit
ls -ld /tmp
# drwxrwxrwt  root  root  /tmp
#          ^ sticky — you can only delete YOUR OWN files

# Cleared on reboot. Never store anything you need across reboots.
# Use /var/tmp for temp files that need to survive reboots.

# WRONG — predictable filename, race condition (TOCTOU attack)
TMPFILE=/tmp/myapp-$$

# CORRECT — mktemp creates with random name and correct permissions
TMPFILE=$(mktemp)                    # /tmp/tmp.XXXXXXXXXX
TMPDIR=$(mktemp -d)                  # directory
trap "rm -f $TMPFILE" EXIT           # cleanup on script exit
```

### /opt — Application Deployment

```bash
# Convention for deploying custom applications:
/opt/myapp/
├── bin/
│   └── myapp
├── config/
├── logs/
├── venv/                     # Python virtualenv
├── current -> releases/v2.1  # symlink to current release
└── releases/
    ├── v2.0/
    └── v2.1/

# Ownership:
sudo chown -R deploy:myapp /opt/myapp
sudo chmod -R 750 /opt/myapp
sudo chmod -R 770 /opt/myapp/logs    # app needs to write logs
```

**Symlink-based zero-downtime deployment:**

```bash
# 1. Upload new code to releases/v2.2/
# 2. Atomically swap the symlink (single syscall — instantaneous):
ln -sfn /opt/myapp/releases/v2.2 /opt/myapp/current
# 3. Restart service
sudo systemctl restart myapp

# Rollback is instant:
ln -sfn /opt/myapp/releases/v2.1 /opt/myapp/current
sudo systemctl restart myapp
```

### Mounting

```bash
# See all currently mounted filesystems
mount
df -h
findmnt          # tree view

# Mount a disk manually
sudo mount /dev/sdb1 /mnt/data
sudo mount -o ro /dev/sdb1 /mnt/data          # read-only
sudo mount -o remount,rw /mnt/data            # remount read-write
sudo umount /mnt/data

# Permanent mounts go in /etc/fstab
# Get UUID first:
blkid /dev/sdb1
# Then add to /etc/fstab:
# UUID=abc123  /mnt/data  ext4  defaults  0 2
```

**Filesystem types you'll encounter:**

```
ext4        standard Linux filesystem — most servers use this
xfs         high-performance, default on RHEL/Amazon Linux
btrfs       copy-on-write, snapshots, RAID — newer
tmpfs       RAM-backed — used for /tmp, /run, /dev/shm
nfs         network filesystem — mount remote dirs
overlayfs   union filesystem — how Docker layers work
```

### Disk Space Debugging — The Workflow

```bash
# 1. Where is disk being used?
df -h
# /dev/sda1  50G  48G  2.0G  96%  /  ← 96% full

# 2. Which directory is consuming the most?
du -sh /* 2>/dev/null | sort -h
du -sh /var/* 2>/dev/null | sort -h
du -sh /var/log/* 2>/dev/null | sort -h

# 3. Fix huge log file — truncate (safe while process is running), don't delete
> /var/log/myapp.log

# 4. Inodes — disk can be "full" with space remaining (too many small files)
df -i
find /tmp -type f -mtime +7 -delete    # delete tmp files older than 7 days
```

### Where Things Actually Live in Practice

```bash
/etc/nginx/nginx.conf                 # nginx main config
/etc/systemd/system/                  # your custom systemd unit files
/var/log/nginx/access.log             # nginx access logs
/var/log/syslog                       # Debian/Ubuntu system log
/var/log/messages                     # RHEL/CentOS/Amazon Linux system log
/opt/myapp/                           # common place to deploy a custom app
/home/deploy/.ssh/                    # deploy user's SSH keys
```

---

## Permissions

### The Mental Model First

Every file and directory has **three permission sets** attached to it, and Linux checks them **in order, stopping at the first match**:

```
1. Are you the OWNER?       → apply owner (u) permissions
2. Are you in the GROUP?    → apply group (g) permissions
3. Neither?                 → apply others (o) permissions
```

This means even if "others" have full access, if you're the owner, only owner permissions apply to you — group and others are ignored.

### The rwx Model

```
Every file/dir has 3 permission sets: owner (u) / group (g) / others (o)

   r=4   w=2   x=1   (add them up per set)

   -rwxr-xr--
    │└┬┘└┬┘└┬┘
    │ u  g  o
    └ file type (- = file, d = dir, l = symlink)
```

### Dissecting the Permission String

```bash
ls -l deploy.sh
# -rwxr-xr--  1  deploy  www-data  4096  Aug 10  deploy.sh
#  │└┬┘└┬┘└┬┘     └──┬──┘ └──┬───┘
#  │  u   g   o      owner   group
#  └── file type

# File types:
# -   regular file
# d   directory
# l   symbolic link
# c   character device (/dev/tty)
# b   block device     (/dev/sda)
```

### rwx on Files vs Directories

**On a FILE:**
```
r (read)    → can read its contents     (cat, less, cp)
w (write)   → can modify its contents   (vim, echo >>)
x (execute) → can run it as a program   (./script.sh)
```

**On a DIRECTORY — the meanings shift:**
```
r (read)    → can LIST contents         (ls /dir)
w (write)   → can CREATE/DELETE files inside  (touch, rm, mv)
x (execute) → can ENTER / TRAVERSE it   (cd /dir, access files inside)
```

```bash
# dir has r but NOT x:
ls /secret-dir        # you can see filenames
cat /secret-dir/file  # DENIED — can't traverse into it

# dir has x but NOT r:
ls /secret-dir        # DENIED — can't list contents
cat /secret-dir/file  # works IF you know the exact filename

# dir has w but NOT x:
touch /secret-dir/newfile  # DENIED — can't enter to create
```

### Numeric (Octal) Notation

```
r = 4   (binary 100)
w = 2   (binary 010)
x = 1   (binary 001)
- = 0

Permission    Binary    Octal
---------     ------    -----
---           000       0
--x           001       1
-w-           010       2
-wx           011       3
r--           100       4
r-x           101       5
rw-           110       6
rwx           111       7
```

```bash
chmod 755 script.sh     # rwxr-xr-x — owner: rwx, group/others: r-x — typical script/binary
chmod 644 config.yml    # rw-r--r-- — owner: rw, group/others: r  — typical config/data file
chmod 600 id_rsa        # rw------- — owner only              — SSH private keys, secrets
chmod 700 ~/.ssh         # rwx------ — owner only              — private directories
chmod 777 anything      # rwxrwxrwx — DO NOT DO THIS IN PROD
```

**Full cheatsheet of common values:**

```
chmod 400   r--------   owner read-only          (AWS .pem keys downloaded)
chmod 600   rw-------   owner rw, nobody else    (SSH private keys, .env)
chmod 644   rw-r--r--   owner rw, others read    (config files, HTML)
chmod 700   rwx------   owner full, nobody else  (~/.ssh directory)
chmod 755   rwxr-xr-x   owner full, others r+x   (scripts, binaries, dirs)
chmod 775   rwxrwxr-x   owner+group full         (shared project dirs)
chmod 777   rwxrwxrwx   everyone everything      (NEVER in prod)
```

### Symbolic Notation

```bash
# Syntax:  chmod [who][operator][permissions] file
#   who:   u=user/owner  g=group  o=others  a=all
#   op:    + add   - remove   = set exactly

chmod u+x script.sh       # add execute for owner only
chmod g-w shared.txt      # remove write from group
chmod o= private.txt      # others: nothing at all (strips all their perms)
chmod a+r public.html     # everyone: add read
chmod ug+rw file.txt      # owner + group: add read+write
chmod -R o-w /var/www     # recursive: remove others' write on entire tree
```

**Symbolic vs Octal — when to use which:**

```
Octal:    when you want to SET the exact final state  → chmod 644 file
Symbolic: when you want to ADD/REMOVE one bit safely  → chmod u+x file
          (doesn't accidentally wipe bits you forgot to include)
```

### Ownership: chown / chgrp

```bash
chown deploy file              # change owner only
chown deploy:deploy file       # change owner + group
chown -R deploy:www-data /opt/myapp   # recursive, common on deploy
chgrp developers file          # change group only
chown :developers file.txt     # change group only (colon prefix form)
```

**Real deploy scenario:**

```bash
# You deployed as root, now nginx (running as www-data) can't read it
ls -l /opt/myapp
# -rw------- 1 root root  app.py   ← only root can read this

chown -R deploy:www-data /opt/myapp
chmod -R 750 /opt/myapp
# Now: deploy owns it, www-data group can read+execute, others nothing
```

### Special Permission Bits (Beyond rwx)

#### setuid (SUID) — bit 4

```bash
chmod u+s /usr/bin/passwd    # or chmod 4755
# When a user runs this file, it executes as the FILE'S OWNER (root).
# This is how `passwd` lets a normal user change their password —
# it needs root access to write /etc/shadow.

ls -l /usr/bin/passwd
# -rwsr-xr-x  root  root  passwd
#    ^ lowercase s = suid set AND x set
#    S = suid set but x NOT set (broken — won't execute)
```

#### setgid (SGID) — bit 2

```bash
chmod g+s /shared/team-dir   # or chmod 2775
# New files created inside inherit the DIRECTORY'S GROUP,
# not the creating user's primary group.

mkdir /shared/project
chown -R :developers /shared/project
chmod 2775 /shared/project
# Everyone in 'developers' creates files owned by group 'developers'
```

#### Sticky Bit — bit 1

```bash
chmod +t /tmp                # or chmod 1777
# Users can only DELETE their OWN files, even if they have write on the dir.
# This is why /tmp is world-writable (1777) but you can't delete others' files.

ls -ld /tmp
# drwxrwxrwt  root  root  /tmp
#          ^ t = sticky bit set
```

**Combined examples:**

```bash
chmod 2755 /shared    # setgid + standard 755
chmod 1777 /tmp       # sticky + world-writable
chmod 4755 /usr/bin/somecmd  # suid + standard 755
```

### umask — Default Permissions for New Files

```
Default for files:  666  (rw-rw-rw-)
Default for dirs:   777  (rwxrwxrwx)
Common umask:       022

666 - 022 = 644   → new files get rw-r--r--
777 - 022 = 755   → new dirs  get rwxr-xr-x
```

```bash
umask              # show current value (usually 0022)
umask 027          # new files → 640, new dirs → 750

# Set persistently:
echo 'umask 027' >> ~/.bashrc
```

### Debugging Permission Errors

```bash
# Step 1: see what permissions actually are
ls -la /path/to/file
stat /path/to/file

# Step 2: who are you running as?
whoami
id          # shows all groups you're in

# Step 3: trace the directory chain — every dir needs x for your user
namei -l /path/to/resource    # shows permissions for every path component

# Step 4: check if SELinux/AppArmor is blocking (even with correct perms)
ausearch -m avc -ts recent    # SELinux
dmesg | grep -E "apparmor|selinux"

# Real example — nginx can't serve static files:
ls -la /opt/myapp/static/
# drwx------ 2 deploy deploy  static/
#    ^^^^^^^ group and others have no x — nginx (www-data) can't enter

# Fix:
chown -R deploy:www-data /opt/myapp/static/
chmod -R 750 /opt/myapp/static/
```

### Production Permissions Checklist

```bash
# SSH
chmod 700 ~/.ssh
chmod 600 ~/.ssh/id_rsa          # private key
chmod 644 ~/.ssh/id_rsa.pub      # public key (ok to be readable)
chmod 600 ~/.ssh/authorized_keys

# App secrets
chmod 600 .env
chmod 600 config/secrets.yml

# App directory (deploy owns, app group can read)
chown -R deploy:app /opt/myapp
chmod -R 750 /opt/myapp

# Writable dirs app needs at runtime
chmod 770 /opt/myapp/logs
chmod 770 /opt/myapp/uploads

# Web-served static files
chmod 755 /opt/myapp/static
chmod 644 /opt/myapp/static/*

# NEVER
chmod 777 /anything/in/prod      # world-writable = instant security finding
chmod 666 .env                   # your DB password readable by every user
```

### One-Line Mental Model

```
Owner (u)  → the person responsible for the file
Group (g)  → a team that shares access (www-data, docker, developers)
Others (o) → everyone else on the system — minimize this in prod

r on file  → read contents
w on file  → modify contents
x on file  → run it

r on dir   → list it
w on dir   → create/delete inside
x on dir   → enter/traverse it   ← most commonly forgotten
```

---

## Users & Groups

### The Mental Model First

Linux is a **multi-user OS**. Every process, every file, every socket is owned by a user. The kernel tracks **numbers (UID/GID)**, not names:

```
You type:   ls -l /opt/myapp
Kernel sees: UID=1001 owns this file
OS resolves: UID 1001 → "deploy"   (via /etc/passwd)
You see:    deploy
```

Three categories of users:

```
UID 0          → root (superuser, bypasses ALL permission checks)
UID 1–999      → system/service accounts (nginx, postgres, www-data)
UID 1000+      → real human users
```

### /etc/passwd — User Database (World-Readable)

```
username:x:UID:GID:comment:home_dir:login_shell
```

```bash
cat /etc/passwd

root:x:0:0:root:/root:/bin/bash
daemon:x:1:1:daemon:/usr/sbin:/usr/sbin/nologin
www-data:x:33:33:www-data:/var/www:/usr/sbin/nologin
postgres:x:113:117:PostgreSQL:/var/lib/postgresql:/bin/bash
deploy:x:1001:1001:Deploy User:/home/deploy:/bin/bash
ci-runner:x:1002:1002::/home/ci-runner:/usr/sbin/nologin
```

Decoded:

```bash
cat /etc/passwd | grep deploy
# deploy:x:1001:1001:Deploy User:/home/deploy:/bin/bash
#   │     │  │    │       │            └ login shell
#   │     │  │    │       └ home dir
#   │     │  │    └ GID
#   │     │  └ UID
#   │     └ password placeholder (real hash is in /etc/shadow)
#   └ username
```

**Why world-readable:** Programs like `ls`, `ps`, `ssh` need to resolve UIDs to names. The actual passwords are NOT here.

### /etc/shadow — Password Hashes (Root-Only)

```
username:hashed_password:last_changed:min:max:warn:inactive:expire
```

```bash
sudo cat /etc/shadow
# deploy:$6$rounds=656000$salt$hashhash...:19200:0:99999:7:::
# root:!:19200:0:99999:7:::    ← ! means locked
# www-data:*:19200:...         ← * means no password (service account)
```

**Hash format: `$id$salt$hash`**

```
$1$   MD5        (old, insecure)
$5$   SHA-256
$6$   SHA-512    (current standard on most distros)
$y$   yescrypt   (Ubuntu 22.04+, strongest)
```

**Why separate from passwd?** `/etc/passwd` is world-readable (needed by many programs). If hashes were there, any user could run offline dictionary attacks. Shadow is root-only — that attack surface is removed.

**Special password field values:**

```
*   — no password, account cannot be used for password login (service accounts)
!   — account is locked (passwd -l prepends !)
!!  — password was never set (useradd without passwd)
x   — in passwd file only, means "check shadow"
```

### /etc/group — Group Database

```
groupname:x:GID:member1,member2,member3
```

```bash
cat /etc/group
# sudo:x:27:deploy,alice
# docker:x:999:deploy,ci-runner
# www-data:x:33:deploy
# developers:x:1050:alice,bob,deploy
```

A user has:
- One **primary group** (set in `/etc/passwd`, GID column)
- Zero or more **supplementary groups** (listed in `/etc/group`)

```bash
id deploy
# uid=1001(deploy) gid=1001(deploy) groups=1001(deploy),27(sudo),999(docker),33(www-data)
#                  └── primary group          └── supplementary groups
```

### /etc/sudoers — Who Can Run What as Whom

**Never edit directly — always use `visudo`** (syntax-checks before saving; a broken sudoers locks you out):

```bash
sudo visudo

# Syntax: WHO  WHERE=(AS_WHOM)  WHAT

# Full sudo for all commands (standard admin setup)
deploy  ALL=(ALL:ALL)  ALL

# Passwordless sudo for one specific command (deploy hook)
deploy  ALL=(ALL)  NOPASSWD: /usr/bin/systemctl restart myapp

# Only allow running as the postgres user, not root
deploy  ALL=(postgres)  /usr/bin/psql

# Group-based rule (% prefix = group)
%sudo   ALL=(ALL:ALL)  ALL
%wheel  ALL=(ALL)  NOPASSWD: ALL
```

**Real-world CI/CD deploy user (principle of least privilege):**

```bash
# /etc/sudoers.d/deploy
deploy  ALL=(ALL)  NOPASSWD: /usr/bin/systemctl restart myapp
deploy  ALL=(ALL)  NOPASSWD: /usr/bin/systemctl reload nginx
```

### Managing Users

```bash
# Minimal — creates user, NO home dir
sudo useradd deploy

# Proper — home dir + shell
sudo useradd -m -s /bin/bash deploy

# Full — home dir + shell + groups + comment
sudo useradd -m -s /bin/bash -G sudo,docker,www-data -c "Deploy User" deploy

# Service account (no login shell, no home dir)
sudo useradd --system --no-create-home --shell /usr/sbin/nologin myapp
```

**`/usr/sbin/nologin` vs `/bin/false`:**

```
/usr/sbin/nologin  → prints "This account is currently not available" then exits
/bin/false         → just exits with code 1, no message
Both prevent interactive login. Use nologin — it's explicit about intent.
```

**Setting passwords:**

```bash
sudo passwd deploy              # interactive prompt
sudo passwd -l deploy           # LOCK account (prepends ! to hash)
sudo passwd -u deploy           # UNLOCK
sudo passwd -e deploy           # expire — force change on next login
```

**Modifying users:**

```bash
sudo usermod -s /bin/zsh deploy          # change shell
sudo usermod -d /opt/deploy deploy       # change home directory
sudo usermod -l newname deploy           # rename user
sudo usermod -L deploy                   # lock account
sudo usermod -U deploy                   # unlock account

# Groups — the most important flags
sudo usermod -aG docker deploy           # APPEND to groups (safe)
sudo usermod -G docker deploy            # REPLACE group list (DANGEROUS!)
sudo usermod -g developers deploy        # change PRIMARY group
```

**The `-aG` vs `-G` footgun — most common production mistake:**

```bash
# Current state:
id deploy
# groups=1001(deploy),27(sudo),999(docker),33(www-data)

# WRONG — wipes sudo, docker, www-data memberships silently:
sudo usermod -G developers deploy
id deploy
# groups=1001(deploy),1050(developers)   ← everything else GONE

# RIGHT — appends:
sudo usermod -aG developers deploy
id deploy
# groups=1001(deploy),27(sudo),999(docker),33(www-data),1050(developers)
```

**Deleting users:**

```bash
sudo userdel deploy              # delete user only, keep home dir
sudo userdel -r deploy           # delete user + home dir + mail spool
```

### Managing Groups

```bash
sudo groupadd developers                 # create group
sudo groupadd -g 1500 developers         # create with specific GID
sudo groupmod -n devteam developers      # rename group
sudo groupdel developers                 # delete group

# Add/remove members without usermod
sudo gpasswd -a deploy developers        # add user to group
sudo gpasswd -d deploy developers        # remove user from group
sudo gpasswd -M alice,bob,deploy developers  # SET full member list (replaces)
```

### sudo in Practice

```bash
sudo command                    # run as root
sudo -u postgres psql           # run as specific user
sudo -u www-data ls /var/www    # check what www-data can see

sudo -i                         # interactive root shell (login shell, loads root's env)
sudo -s                         # root shell but keeps YOUR environment
sudo -l                         # what am I allowed to run?
sudo -l -U deploy               # what is deploy allowed to run?

sudo -v                         # refresh sudo timestamp (extend 15min window)
sudo -k                         # invalidate sudo timestamp immediately
```

**`sudo -i` vs `sudo -s`:**

```
sudo -i → Becomes root with root's HOME, PATH, env — clean root env
sudo -s → Becomes root but keeps YOUR PATH, HOME — can cause "command not found"
Use -i for clean root env, -s for quick one-offs
```

### Inspecting Users — Read-Only Commands

```bash
whoami                      # current username
id                          # current user's UID, GID, all groups
id deploy                   # another user's UID, GID, groups
who                         # who is currently logged in
w                           # who is logged in + what they're doing
last                        # login history
last deploy                 # login history for specific user
lastb                       # failed login attempts

getent passwd deploy        # look up via NSS (works with LDAP too)
getent group docker         # look up group
```

`getent` is better than `grep /etc/passwd` because it queries the **Name Service Switch** — works whether users are in flat files, LDAP, or Active Directory.

### Real-World Scenarios

**Scenario 1 — Set up a deploy user for a web app:**

```bash
sudo useradd -m -s /bin/bash deploy
sudo passwd deploy

# Locked service account the app runs as
sudo useradd --system --no-create-home --shell /usr/sbin/nologin myapp

# App directory setup
sudo mkdir -p /opt/myapp
sudo chown -R deploy:myapp /opt/myapp
sudo chmod -R 750 /opt/myapp

# Least-privilege sudo
echo "deploy ALL=(ALL) NOPASSWD: /usr/bin/systemctl restart myapp" \
  | sudo tee /etc/sudoers.d/deploy
sudo chmod 440 /etc/sudoers.d/deploy
```

**Scenario 2 — Add developer to docker group:**

```bash
sudo usermod -aG docker alice

# She must log out and back in for group to take effect
# OR activate in current session:
newgrp docker

# Verify:
id alice
```

**Scenario 3 — Audit who has sudo access:**

```bash
sudo cat /etc/sudoers
sudo ls /etc/sudoers.d/
getent group sudo
getent group wheel
sudo -l -U alice
```

**Scenario 4 — Lock a departed employee's account:**

```bash
sudo passwd -l alice
sudo usermod -L alice

# Disable SSH keys
sudo mv /home/alice/.ssh/authorized_keys \
        /home/alice/.ssh/authorized_keys.disabled

# Archive then delete
sudo tar -czf /backup/alice-home-$(date +%Y%m%d).tar.gz /home/alice
sudo userdel -r alice
```

### newgrp — Group Activation Without Re-Login

```bash
sudo usermod -aG docker $USER
# Group only takes effect at next login. In current session:
newgrp docker    # opens a subshell with docker as active group
id               # now shows docker in groups
```

### Key Rules

```
1. Never run your app as root. Create a dedicated service account.

2. Service accounts: --system, --no-create-home, --shell /usr/sbin/nologin
   They own app files. They do not need to log in.

3. Deploy/human accounts: -m (home dir), -s /bin/bash, in relevant groups.
   They SSH in. They do NOT own the running process.

4. usermod -aG — ALWAYS the -a. No -a = wipe all other groups.

5. sudo = logged, audited, time-limited.
   Direct root login = no audit trail.
   Disable root SSH login: PermitRootLogin no in /etc/ssh/sshd_config

6. sudoers = principle of least privilege. Grant exactly one command
   if that's all they need — not ALL.

7. visudo always. Never `nano /etc/sudoers`. A syntax error locks everyone out.
```

---

## Environment Variables

### The Mental Model First

Every process runs in an **environment** — a private key-value store it inherits from its parent at launch:

```
systemd (PID 1)
└── sshd
    └── bash (your shell)          ← inherits sshd's env
        └── python app.py          ← inherits bash's env
            └── subprocess.run()   ← inherits python's env
```

**Key rules:**

```
1. A child inherits the parent's environment at fork time
2. A child CANNOT modify the parent's environment
3. export makes a variable visible to child processes
4. Without export, a variable exists only in the current shell
```

### Variable vs Exported Variable

```bash
# Shell variable — exists in THIS shell only
NAME="deploy"
echo $NAME              # works: "deploy"
bash -c 'echo $NAME'    # empty — child didn't inherit it

# Exported variable — passed to all child processes
export NAME="deploy"
bash -c 'echo $NAME'    # "deploy" — child inherited it

# Prove it with Python:
SECRET="abc123"
python3 -c "import os; print(os.environ.get('SECRET', 'NOT FOUND'))"
# NOT FOUND

export SECRET="abc123"
python3 -c "import os; print(os.environ.get('SECRET', 'NOT FOUND'))"
# abc123
```

### Reading Variables

```bash
echo $DATABASE_URL          # simple expansion
echo ${DATABASE_URL}        # explicit boundary — needed when concatenating
echo "${DATABASE_URL}"      # quoted — prevents word splitting on spaces

printenv DATABASE_URL       # prints value, exits 1 if unset
env | grep DATABASE         # search all exported vars
env                         # list everything exported
set                         # list ALL vars (exported + unexported + functions)
```

**`${VAR}` vs `$VAR` — when braces matter:**

```bash
VER="3"
echo "$VERsuffix"      # empty — shell looks for variable named "VERsuffix"
echo "${VER}suffix"    # "3suffix" — correct
```

### Default / Fallback Syntax

```bash
echo ${PORT:-8080}           # 8080 if PORT unset, else PORT's value
echo ${PORT:=8080}           # sets PORT=8080 if unset, then uses it
echo ${API_KEY:?'API_KEY must be set'}   # exits with error if unset
echo ${DEBUG:+'-v'}          # prints -v only if DEBUG is set
```

**In scripts:**

```bash
#!/usr/bin/env bash
PORT=${PORT:-8080}
HOST=${HOST:-0.0.0.0}
ENV=${APP_ENV:?'APP_ENV must be set to development or production'}
echo "Starting on $HOST:$PORT in $ENV mode"
```

### Unsetting Variables

```bash
export TEMP_TOKEN="abc"
unset TEMP_TOKEN
echo $TEMP_TOKEN        # empty (no error)
printenv TEMP_TOKEN     # exits with code 1 (unset)
```

### Scope — Four Distinct Lifetimes

```bash
# 1. Single command — sets var for that command only, not exported, not persisted
DEBUG=1 python app.py
echo $DEBUG              # empty — it's gone

# 2. Current shell session — gone when terminal closes
export DATABASE_URL="postgres://localhost/mydb"

# 3. All new shells for your user — add to ~/.bashrc or ~/.zshrc
echo 'export GOPATH="$HOME/go"' >> ~/.bashrc
source ~/.bashrc         # reload now without logging out

# 4. System-wide all users — add to /etc/environment or /etc/profile.d/
```

**Per-command is extremely useful for:**

```bash
APP_ENV=staging python manage.py migrate      # override for one run
CONFIG_FILE=/etc/myapp/prod.conf ./start.sh   # run with different config
DATABASE_URL="postgres://testdb" pytest tests/ # test with specific DB
```

### Where Variables Live Persistently

```
Login shell (SSH in, or `bash -l`):
   /etc/environment          ← system-wide, KEY=VALUE only, NOT shell syntax
   /etc/profile              ← system-wide shell script
   /etc/profile.d/*.sh       ← system-wide drop-in scripts
   ~/.bash_profile           ← user's login config
     └── usually sources ~/.bashrc

Interactive non-login shell (new terminal tab):
   ~/.bashrc                 ← user's interactive config
```

```bash
# ~/.bashrc — loaded every time you open a terminal
export EDITOR="vim"
export GOPATH="$HOME/go"
export PATH="$GOPATH/bin:$PATH"

# /etc/environment — system-wide, plain KEY=VALUE, no shell syntax
JAVA_HOME=/usr/lib/jvm/java-17
APP_ENV=production

# /etc/profile.d/ — system-wide shell scripts
sudo tee /etc/profile.d/myapp.sh << 'EOF'
export MYAPP_HOME=/opt/myapp
export PATH="$MYAPP_HOME/bin:$PATH"
EOF
```

### PATH — The Most Important Variable

`PATH` is a colon-separated list of directories searched left to right for executables:

```bash
echo $PATH
# /home/deploy/.local/bin:/usr/local/bin:/usr/bin:/bin

# Shell checks each dir in order, first match wins

# Prepend — your version wins over system version
export PATH="$HOME/.local/bin:$PATH"

# Append — system version wins, yours is fallback
export PATH="$PATH:$HOME/scripts"

# Diagnosing PATH problems:
which python3           # full path of what would run
type python3            # shows if it's alias/function/builtin/file
type -a python3         # shows ALL matches in PATH order
echo $PATH | tr ':' '\n'  # print each dir on its own line
```

**The cron PATH footgun:**

```bash
# Your terminal works: aws s3 sync ...
# Cron job fails with "aws: command not found"
# Because cron has a minimal PATH: /usr/bin:/bin
# aws was installed in /usr/local/bin — not in cron's PATH

# Fix — set PATH explicitly in crontab:
PATH=/usr/local/bin:/usr/bin:/bin
0 2 * * * aws s3 sync /backup s3://my-bucket
```

### Special Built-in Variables

```bash
$HOME       # /home/deploy — current user's home
$USER       # deploy — current username
$SHELL      # /bin/bash — current shell binary
$PWD        # /opt/myapp — current working directory
$OLDPWD     # previous directory (cd - uses this)
$HOSTNAME   # server's hostname
$LANG       # locale (en_US.UTF-8)
$TZ         # timezone (America/New_York, UTC)

# Shell-specific
$?          # exit code of last command (0 = success)
$$          # PID of current shell
$!          # PID of last background process
$0          # name of current script/shell
$#          # number of arguments passed to script
$@          # all arguments as separate words
```

**Exit code in practice:**

```bash
if ! python manage.py migrate; then
    echo "Migration failed, exit code: $?"
    exit 1
fi
```

### Reading Variables in Code

```python
# Python
import os

db_url = os.environ["DATABASE_URL"]              # crash if missing
port = int(os.environ.get("PORT", 8080))         # default if missing
debug = os.environ.get("DEBUG", "false").lower() == "true"
```

```javascript
// Node.js
const dbUrl = process.env.DATABASE_URL;
const port = parseInt(process.env.PORT ?? "8080");
if (!process.env.API_KEY) {
    throw new Error("API_KEY environment variable is required");
}
```

```bash
# Bash
DB_URL="${DATABASE_URL:?'DATABASE_URL must be set'}"
PORT="${PORT:-8080}"
```

### .env Files — The Dev Pattern

```bash
# .env file — NEVER commit to git
DATABASE_URL=postgres://localhost/mydb_dev
SECRET_KEY=dev-secret-not-for-prod
DEBUG=true
PORT=8000
```

```bash
# Load into current shell
set -a; source .env; set +a

# .gitignore — must be there
echo ".env" >> .gitignore
chmod 600 .env
```

**In production — use secrets management, NOT a .env file on disk:**

```
AWS      → Secrets Manager / Parameter Store
Heroku   → Config Vars
K8s      → Secrets
Docker   → --env-file or secrets
```

### env Command

```bash
env                                    # print all current env vars
env -i PATH=/usr/bin:/bin bash         # run with completely clean environment
env DATABASE_URL="postgres://testdb" PORT=9000 python app.py  # add/override vars
env -u DATABASE_URL python app.py      # run with a var removed
```

### Debugging — What Does a Process Actually See?

```bash
# Check env vars of a running process
cat /proc/<PID>/environ | tr '\0' '\n'

# Find the PID first
pgrep -f "python app.py"
```

### Systemd Service — Passing Env Vars to a Daemon

```ini
# /etc/systemd/system/myapp.service
[Service]
User=myapp
WorkingDirectory=/opt/myapp
EnvironmentFile=/etc/myapp/env     # load from file
Environment="APP_ENV=production"   # inline
ExecStart=/opt/myapp/venv/bin/gunicorn app:app
```

```bash
# /etc/myapp/env  (chmod 600, owned by root)
DATABASE_URL=postgres://prod-db/myapp
SECRET_KEY=abc123...
```

### Key Rules

```
1. export = visible to children. No export = this shell only.

2. A child CANNOT change its parent's environment.
   That's why `source script.sh` exists — it runs in current shell.

3. Cron has a minimal PATH. Always use absolute paths in cron jobs
   or set PATH at the top of the crontab.

4. Never commit .env to git. Use chmod 600 on it.

5. In production, use a secrets manager — not a .env file on disk.

6. ${VAR:-default} for optional vars, ${VAR:?'message'} for required.

7. source file.sh runs in current shell (env changes stick).
   bash file.sh runs in a subshell (env changes lost on exit).
```

---

## Shell Types

### The Mental Model First

A shell is just a program — it reads your input, interprets it, and talks to the kernel on your behalf. When you type `ls`:

```
1. Parses your input
2. Looks up "ls" in PATH
3. Calls fork() to create a child process
4. Calls execve("/bin/ls", args, env) in the child
5. Waits for it to finish
6. Prints the next prompt
```

The shell you're using matters because:
- Scripts have a shebang (`#!/bin/bash`) — the wrong shell silently breaks them
- Syntax differs between shells — `[[ ]]` works in bash, not in `sh`/`dash`
- Docker base images often have no bash — only `sh` (which may be `dash`)

### The Shell Family Tree

```
Thompson shell (1971, Bell Labs)
└── Bourne shell — sh (1979, Steve Bourne)
    ├── bash — Bourne Again Shell (1989, GNU)
    ├── dash — Debian Almquist Shell (POSIX, fast)
    ├── ksh  — KornShell (1983, AT&T)
    └── zsh  — Z Shell (1990)

C shell (1978, Bill Joy)
└── tcsh

fish (2005, completely independent)
```

| Shell | Notes |
|-------|-------|
| **sh** | Original Bourne shell / POSIX baseline — scripts written for `sh` are maximally portable. |
| **bash** | Bourne Again Shell — default on most Linux distros and servers. Arrays, `[[ ]]`, process substitution. |
| **zsh** | Default on macOS since Catalina. Bash-compatible-ish with better completion/theming (oh-my-zsh). |
| **fish** | Friendly Interactive Shell — great UX (autosuggestions) but NOT POSIX-compatible; scripts written for fish don't run in bash. |

### sh — The Baseline

`sh` is not one program — it's a **specification** (POSIX). Different systems put different programs at `/bin/sh`:

```
Ubuntu/Debian  →  /bin/sh is dash   (fast, minimal)
macOS          →  /bin/sh is bash (in compatibility mode)
Alpine         →  /bin/sh is busybox sh
RHEL/CentOS    →  /bin/sh is bash
```

```bash
ls -la /bin/sh
# lrwxrwxrwx  /bin/sh -> dash    (Ubuntu)
# lrwxrwxrwx  /bin/sh -> bash    (macOS/RHEL)
```

**What POSIX sh guarantees — safe to use anywhere:**

```sh
#!/bin/sh
NAME="world"
if [ "$NAME" = "world" ]; then echo "it matches"; fi
for f in *.txt; do echo "$f"; done
DATE=$(date +%Y-%m-%d)   # command substitution (POSIX form)
```

**What `sh` does NOT have — bash-only syntax:**

```sh
[[ "$x" == "foo" ]]     # double brackets — bash only
[[ "$x" =~ regex ]]     # regex matching — bash only
array=(1 2 3)           # arrays — bash only
echo {1..10}            # brace expansion — bash only
source file.sh          # 'source' — use '.' instead in sh
```

### bash — The Server Standard

#### Double brackets `[[ ]]` vs single `[ ]`

```bash
# Single bracket [ ] — POSIX, works in sh
[ "$name" = "deploy" ]    # string equality
[ -f /etc/passwd ]        # file exists
[ "$a" -eq "$b" ]         # numeric equality

# Double bracket [[ ]] — bash builtin, safer, more powerful
[[ "$name" == "deploy" ]]
[[ "$name" == dep* ]]             # glob matching
[[ "$name" =~ ^dep[a-z]+$ ]]      # regex matching
[[ -f /etc/passwd && -r /etc/passwd ]]  # && inside brackets

# Why [[ ]] is safer:
name=""
[ $name = "x" ]     # BREAKS — expands to [ = "x" ], missing left operand
[[ $name = "x" ]]   # fine — no word splitting inside [[ ]]
```

#### Arrays

```bash
servers=("web1" "web2" "db1" "cache1")
echo ${servers[0]}          # web1
echo ${servers[@]}          # all elements
echo ${#servers[@]}         # count: 4

for s in "${servers[@]}"; do
    echo "Pinging $s"
    ping -c 1 "$s"
done

# Associative array (bash 4+)
declare -A config
config[host]="localhost"
config[port]="5432"
for key in "${!config[@]}"; do
    echo "$key=${config[$key]}"
done
```

#### Process Substitution

```bash
diff <(ls /etc) <(ls /etc.bak)         # compare command output without temp files

while IFS= read -r line; do
    echo "Processing: $line"
done < <(grep ERROR /var/log/app.log)
```

#### Here-Docs

```bash
# Here-doc — multi-line stdin
cat << 'EOF'              # single-quoted EOF: variables NOT expanded
This is line 1
$HOME is literal here
EOF

cat << EOF                # unquoted EOF: variables ARE expanded
HOME is $HOME
EOF

# Here-doc into a file
sudo tee /etc/myapp/config.yml << EOF
database:
  host: ${DB_HOST}
  port: ${DB_PORT:-5432}
EOF
```

#### Bash Strict Mode — Use in Every Script

```bash
#!/usr/bin/env bash
set -euo pipefail
#   │││
#   ││└── pipefail: pipe fails if ANY command fails (not just last)
#   │└─── u: treat unset variables as errors
#   └──── e: exit immediately on any error

# Without strict mode — silent failure:
DB_URL=$DATABSE_URL    # typo — silently becomes empty string

# With set -u:
DB_URL=$DATABSE_URL    # immediate exit: "DATABSE_URL: unbound variable"
```

### dash — The Fast sh

`dash` is Ubuntu's `/bin/sh`. ~4x faster than bash to start — matters for scripts called thousands of times.

```bash
dash -n script.sh       # syntax check without executing
dash script.sh          # run explicitly with dash

# Common bash-isms that silently break in dash:
echo {1..5}             # bash: "1 2 3 4 5" | dash: "{1..5}" (literal)
source ~/.bashrc        # bash: ok | dash: "source: not found" — use . instead
[[ -z "$x" ]]           # bash: ok | dash: syntax error
```

**The Alpine Docker trap:**

```dockerfile
FROM alpine:3.19
# Alpine has NO bash by default — /bin/sh is busybox sh

# This FAILS with bash-specific syntax:
RUN source /etc/profile

# Fix option 1 — install bash
RUN apk add --no-cache bash
SHELL ["/bin/bash", "-c"]

# Fix option 2 — rewrite to POSIX sh
RUN . /etc/profile        # '.' is the POSIX equivalent of 'source'
```

### zsh — The Developer Shell

Default on macOS since Catalina. Bash-compatible for most things, better quality-of-life:

```zsh
# More powerful globbing
ls **/*.py          # recursive glob (need shopt -s globstar in bash)
ls *(.)             # files only
ls *(/)             # directories only

# Zsh arrays are 1-indexed (bash is 0-indexed!)
arr=("a" "b" "c")
echo $arr[1]        # "a" in zsh
echo ${arr[0]}      # "a" in bash — DIFFERENT!
```

```zsh
# ~/.zshrc
export PATH="$HOME/.local/bin:$PATH"
autoload -U compinit && compinit
setopt HIST_IGNORE_DUPS
setopt AUTO_CD
HISTSIZE=10000

# oh-my-zsh
ZSH_THEME="robbyrussell"
plugins=(git docker kubectl python)
```

### fish — The Friendly Shell

Completely independent design — NOT POSIX compatible. Great UX, terrible for scripting portability:

```fish
# fish syntax — completely different from bash
set NAME "deploy"
set -x DATABASE_URL "postgres://localhost/mydb"    # -x = export

if test "$NAME" = "deploy"
    echo "matched"
end

for f in *.txt
    echo $f
end
```

**What's great:** Autosuggestions from history, syntax highlighting as you type, no setup needed.

**Why you don't write deployment scripts in fish:** Copy a fish script to a bash system → fails immediately. The entire variable model is different.

### The Shebang Line — Critical Detail

```bash
#!/bin/bash              # hardcoded — fails if bash is elsewhere
#!/usr/bin/env bash      # searches PATH for bash — portable, preferred
#!/usr/bin/env sh        # POSIX sh — maximally portable
#!/usr/bin/env python3   # works for any interpreter
```

**What happens without a shebang:**

```bash
./script.sh   # kernel sees no shebang → runs with /bin/sh
              # if you used [[ ]] or arrays, it silently breaks
```

**Shebang decision tree:**

```
Need Alpine / minimal Docker image?  → #!/bin/sh  (POSIX only)
Normal Linux server?                 → #!/usr/bin/env bash
Personal scripts?                    → #!/usr/bin/env bash
Fish script (interactive only)?      → #!/usr/bin/env fish
```

### Login vs Interactive vs Non-Interactive Shells

```
Login shell        — SSH login or `bash -l`
                     reads: /etc/profile → ~/.bash_profile → ~/.bashrc

Interactive shell  — new terminal tab, subshell
                     reads: ~/.bashrc only

Non-interactive    — runs a script, no human typing
                     reads: nothing by default (just inherits parent's env)
```

```bash
# Check what kind of shell you have:
[[ $- == *i* ]] && echo "interactive" || echo "non-interactive"

# Force login shell:
bash -l
bash --login
```

**Why your cron job can't find commands:**

```bash
# Cron = NON-login, NON-interactive shell — does NOT read ~/.bashrc
# Your ~/.bashrc might add node to PATH via nvm
# Cron doesn't run this → node not in PATH → job fails silently

# Fix 1: use absolute paths
0 * * * *  /home/deploy/.nvm/versions/node/v20.0.0/bin/node /opt/app/script.js

# Fix 2: source your profile in the script
#!/usr/bin/env bash
source /home/deploy/.bashrc
node /opt/app/script.js

# Fix 3: set PATH in crontab
PATH=/home/deploy/.nvm/versions/node/v20.0.0/bin:/usr/local/bin:/usr/bin:/bin
0 * * * *  node /opt/app/script.js
```

### Subshells vs Source

```bash
# Subshell — runs in child process, env changes are LOST on exit
bash script.sh
./script.sh
( export X=1 )   # explicit subshell

# Source — runs IN current shell, env changes PERSIST
source script.sh
. script.sh      # POSIX equivalent

# Practical example — virtualenv:
source venv/bin/activate    # modifies YOUR shell's PATH — works
./venv/bin/activate         # activates in a child then exits — useless
```

### Key Rules

```
1. Use #!/usr/bin/env bash for scripts — portable across systems.

2. Use #!/bin/sh only when you need Alpine/minimal-container portability.
   Test with: dash -n script.sh

3. fish is for your terminal. Never deploy fish scripts.

4. set -euo pipefail at the top of every bash script — catches unset
   variables, command failures, and pipe failures silently.

5. [[ ]] over [ ] in bash scripts — safer quoting, supports regex,
   supports && and || inside the brackets.

6. Cron runs a non-login, non-interactive shell — no ~/.bashrc.
   Always use absolute paths or source your profile explicitly.

7. source / . runs in current shell (env changes stick).
   bash script.sh runs in a subshell (env changes are lost).
```

---

## Interview Angle

### How Linux Interviews Actually Work

Senior backend/DevOps interviews test three things:

```
1. Do you know WHY, not just what command to run?
2. Have you hit this in production, or just read about it?
3. Can you reason from first principles when you don't know the answer?
```

Every question has a surface answer and a deep answer. Interviewers hear the surface answer 100 times a day. The deep answer is what gets you hired.

---

**Q: Difference between `apt` and `yum`/`dnf`?**

**Surface answer:** "apt is for Debian/Ubuntu, yum/dnf is for RHEL/CentOS."

**Deep answer:**

The real difference is the **packaging format and dependency model underneath**:

```
apt  → .deb packages → dpkg as the low-level tool → APT as the resolver
yum  → .rpm packages → rpm  as the low-level tool → YUM/DNF as the resolver
```

```
High-level (dependency resolver):   apt          dnf/yum
                                     │               │
Low-level (install the package):    dpkg            rpm

# Bypass high-level layer (airgapped servers / debugging):
dpkg -i package.deb     # installs without resolving dependencies
rpm -ivh package.rpm    # installs without resolving dependencies
```

Why DNF replaced YUM:
```
YUM had a slow resolver written in Python — could take minutes on large
package sets. DNF rewrote it in C (libsolv) — significantly faster.
Commands are nearly identical: yum install nginx → dnf install nginx
```

**Follow-up — "Which distro for a new EC2 instance?":**

```
Amazon Linux 2023 for AWS workloads — optimized for EC2, free, integrates
with AWS SDK/CLI, uses dnf.

Ubuntu 22.04 LTS if team already knows it — huge community, 5-year support.

Alpine only for Docker base images where size matters — verify your
binaries don't need glibc (musl is not drop-in compatible).
```

---

**Q: Why does a private SSH key need `chmod 600`?**

**Surface answer:** "SSH requires it."

**Deep answer:**

SSH enforces this as a **security guarantee in the protocol implementation**:

```bash
# What actually happens with wrong permissions:
ssh -i ~/.ssh/id_rsa deploy@server
# WARNING: UNPROTECTED PRIVATE KEY FILE!
# Permissions 0644 are too open.
# This private key will be ignored.
```

The threat model:
```
If your private key is readable by group or others:
  - Any user on the same machine can copy your private key
  - They have permanent access to every server it's authorized on
  - You'd never know — no alert, no log, no revocation needed
  - The private key IS the identity

600 = only UID owner can read/write. No other user (except root) can touch it.
```

Full SSH permission model:
```bash
chmod 700 ~/.ssh                  # directory: only owner can enter
chmod 600 ~/.ssh/id_rsa           # private key: owner read/write only
chmod 644 ~/.ssh/id_rsa.pub       # public key: readable by all (it's public)
chmod 600 ~/.ssh/authorized_keys  # writable by others = they can add their own key
chmod 600 ~/.ssh/config           # may contain hostnames/users
```

**Follow-up — "How do you manage SSH keys across a team of 20 engineers?":**

```
Don't use static keys at scale. Move to:
  - SSH CA: sign short-lived certificates (TTL: 8 hours).
    No static keys on servers — just trust the CA's public key.
    Revocation is instant — certificates expire.
  - AWS SSM Session Manager: no SSH keys needed at all.
  - HashiCorp Vault SSH secrets engine: dynamic, short-lived keys.

With static keys: when someone leaves, you find and remove their key
from every server manually. With certificates: they just expire.
```

---

**Q: Difference between `/etc/passwd` and `/etc/shadow`?**

**Surface answer:** "passwd has user info, shadow has passwords."

**Deep answer:**

The split exists for a **specific security reason rooted in Unix history**:

```
Original Unix: /etc/passwd held password hashes AND was world-readable
(world-readable because many programs need to resolve UIDs to names:
ls, ps, mail, finger, etc.)

Problem: any user could copy /etc/passwd and run offline dictionary attacks
against every account's hash. Hardware got fast enough to make this viable.

Solution: split into two files:
  /etc/passwd  — metadata only, still world-readable, 'x' as password placeholder
  /etc/shadow  — actual hashes, root-readable only (mode 640 or 000)
```

The shadow hash format decoded:
```
$6$rounds=656000$salt$hash

$6$  = SHA-512
rounds=656000 = iterations (higher = slower = harder to brute-force)
salt = random value (prevents rainbow table attacks)
hash = the actual hashed result
```

Special password field values:
```
*   — no password, account cannot be used for password login (service accounts)
!   — account is locked (passwd -l prepends !)
!!  — password was never set (useradd without passwd)
```

**Follow-up — "If you got shell access to a server, what would you check?":**

```bash
# Who can log in? (accounts with real shells)
cat /etc/passwd | grep -v nologin | grep -v false

# Anyone with UID 0 besides root? (hidden root accounts)
awk -F: '($3 == 0) {print}' /etc/passwd

# Who has sudo?
cat /etc/sudoers; cat /etc/sudoers.d/*
getent group sudo wheel

# Recently modified sensitive files
find /etc -mtime -7 -ls

# What's listening on the network?
ss -tlnp

# Recent logins and failed logins
last
lastb
```

---

**Q: Why `usermod -aG` and not `usermod -G`?**

**Surface answer:** "-a means append."

**Deep answer:**

This is a **classic production incident** — the mistake is easy, consequence is immediate:

```bash
# Current state:
id deploy
# groups=1001(deploy),27(sudo),999(docker),33(www-data),1050(developers)

# You want to add "monitoring" group:
sudo usermod -G monitoring deploy    # WRONG — no -a

# Result:
id deploy
# groups=1001(deploy),1051(monitoring)   ← EVERYTHING ELSE GONE

# Consequences:
# - deploy cannot run sudo → locked out of admin tasks
# - deploy cannot run docker → CI/CD breaks
# - deploy cannot read /var/www → nginx configs break
# - Zero error messages — it silently happened
```

Why the design is this way:
```
-G sets the COMPLETE supplementary group list.
It's "replace with exactly this list", not "add to list".
-aG means "append to the existing list".
-a ONLY makes sense with -G.
```

Recovery if you made the mistake:
```bash
sudo usermod -aG sudo,docker,www-data,developers deploy

# If deploy LOST sudo and you're logged in as deploy:
# You cannot run sudo anymore. You need:
#   - Another session already open as root
#   - Another user with sudo access
#   - AWS: SSM Session Manager (doesn't need sudo)
# This is why you NEVER close your root session until you've
# verified the new user/permissions work.
```

---

### Additional Interview Questions

**Q: A process is failing with "Permission denied" — how do you debug it?**

```bash
# 1. What user is the process running as?
ps aux | grep myapp
cat /proc/<PID>/status | grep -E "^(Name|Uid|Gid)"

# 2. Check the error — if unclear, use strace:
strace -p <PID> -e trace=file 2>&1 | grep "EACCES\|EPERM"
# EACCES = permission denied on file
# EPERM  = operation not permitted (capability issue)

# 3. Check the file's permissions and entire path
ls -la /path/to/resource
namei -l /path/to/resource    # shows permissions for every path component

# 4. Check if SELinux/AppArmor is blocking (even with correct perms)
ausearch -m avc -ts recent
dmesg | grep -E "apparmor|selinux"
```

**Q: How would you set up a new server for a web application from scratch?**

```bash
sudo apt update && sudo apt upgrade -y

# Create non-root deploy user
sudo useradd -m -s /bin/bash deploy
sudo usermod -aG sudo deploy

# SSH key auth, disable password login
sudo mkdir -p /home/deploy/.ssh
sudo cp ~/.ssh/authorized_keys /home/deploy/.ssh/
sudo chown -R deploy:deploy /home/deploy/.ssh
sudo chmod 700 /home/deploy/.ssh
sudo chmod 600 /home/deploy/.ssh/authorized_keys

# Disable root SSH and password auth
sudo sed -i 's/PermitRootLogin yes/PermitRootLogin no/' /etc/ssh/sshd_config
sudo sed -i 's/#PasswordAuthentication yes/PasswordAuthentication no/' /etc/ssh/sshd_config
sudo systemctl reload sshd

# Locked service account for the app
sudo useradd --system --no-create-home --shell /usr/sbin/nologin myapp

# App directory with correct ownership
sudo mkdir -p /opt/myapp
sudo chown -R deploy:myapp /opt/myapp
sudo chmod -R 750 /opt/myapp

# Least-privilege sudo
echo "deploy ALL=(ALL) NOPASSWD: /usr/bin/systemctl restart myapp" \
  | sudo tee /etc/sudoers.d/deploy
sudo chmod 440 /etc/sudoers.d/deploy

# Firewall
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
```

**Q: Difference between `su` and `sudo`?**

```
su  — Switch User. Asks for TARGET user's password.
      Opens a full login shell as that user.
      No audit trail beyond "su was run."

sudo — Substitute User Do. Asks for YOUR password.
       Runs one command with elevated privileges.
       Every command is logged to /var/log/auth.log.
       You grant specific commands, not blanket access.
       Timeout: sudo remembers your password for 15 minutes.

In production:
  su root  requires knowing root's password — shared secrets are a problem
  sudo     requires only your password + being in sudoers — auditable
  sudo lets you grant "restart nginx" without granting "delete /etc"
  su gives full root — no scoping possible
```

### The Meta-Skill: Reasoning From First Principles

The best answer to any Linux question follows this structure:

```
1. State what the thing IS (not just what it does)
2. Explain WHY it was designed this way (the problem it solves)
3. Give a real consequence if you get it wrong
4. Name the production scenario where you'd actually use it
```

Example applied to `/etc/shadow`:

```
WHAT:   A file holding password hashes, readable only by root

WHY:    /etc/passwd must be world-readable for UID resolution.
        Hashes in a world-readable file enables offline attacks.
        Splitting them into a root-only file removes that attack surface.

WRONG:  If shadow is misconfigured to be world-readable (chmod 644),
        any user can copy the hashes and run hashcat/john against them
        offline — no rate limiting, no lockout, no detection.

WHEN:   You'd look at this when auditing a server for security misconfigs,
        when debugging PAM authentication failures, or when setting up
        an LDAP migration and understanding where credentials live.
```

That depth is what separates a candidate who studied from one who has operated systems.