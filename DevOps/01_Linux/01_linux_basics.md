# Linux Basics — Distros, Filesystem, Permissions, Users, Shells

**DevOps Track · Phase 1: Linux**

## Quick Concepts

- **Distribution (distro)** = a packaged Linux OS (kernel + userland + package manager) — Ubuntu, CentOS, Amazon Linux, Debian, RHEL
- **Package manager** = tool that installs/updates/removes software (`apt`, `yum`, `dnf`)
- **FHS** = Filesystem Hierarchy Standard — the standard directory layout every distro follows
- **Permission** = `rwx` (read/write/execute) applied to user/group/others
- **UID/GID** = numeric IDs identifying a user/group under the hood
- **sudo** = "substitute user do" — run a command as another user (usually root) with logging
- **Environment variable** = key-value pair processes inherit (`PATH`, `HOME`, `USER`)
- **Shell** = the command interpreter you type into (`bash`, `zsh`, `sh`, `fish`)
- **POSIX** = portability standard — scripts written to POSIX `sh` run on almost any Unix-like system

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
|---|---|---|---|
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

```
/                  root of everything
├── /bin, /sbin    essential binaries (often symlinked into /usr on modern distros)
├── /usr           user programs — /usr/bin, /usr/local/bin, /usr/lib
├── /etc           system-wide config files (nginx.conf, passwd, hosts, crontab)
├── /var           variable data
│   ├── /var/log   ← application + system logs, first place to check
│   ├── /var/lib   service data (databases, package manager state)
│   ├── /var/run   runtime data, PID files (often symlinked to /run)
│   └── /var/spool cron jobs, mail queues
├── /home          user home directories (/home/deploy)
├── /root          root user's home directory
├── /opt           optional/third-party software (often where you drop your app)
├── /tmp           temporary files, cleared on reboot — never store anything you need
├── /proc          virtual filesystem — live process/kernel info (/proc/<pid>/status)
├── /sys           virtual filesystem — kernel/device/hardware info
├── /dev           device files (/dev/sda, /dev/null, /dev/tty)
└── /mnt, /media   mount points for external/network filesystems
```

### Where things actually live in practice

```bash
/etc/nginx/nginx.conf         # nginx main config
/etc/systemd/system/          # your custom systemd unit files
/var/log/nginx/access.log     # nginx access logs
/var/log/syslog               # Debian/Ubuntu system log
/var/log/messages             # RHEL/CentOS/Amazon Linux system log
/opt/myapp/                   # common place to deploy a custom app
/home/deploy/.ssh/             # deploy user's SSH keys
```

---

## Permissions

### The rwx Model

```
Every file/dir has 3 permission sets: owner (u) / group (g) / others (o)

   r=4   w=2   x=1   (add them up per set)

   -rwxr-xr--
    │└┬┘└┬┘└┬┘
    │ u  g  o
    └ file type (- = file, d = dir, l = symlink)
```

### Numeric (octal) Notation

```bash
chmod 755 script.sh     # rwxr-xr-x — owner: rwx, group/others: r-x — typical script/binary
chmod 644 config.yml    # rw-r--r-- — owner: rw, group/others: r  — typical config/data file
chmod 600 id_rsa        # rw------- — owner only              — SSH private keys, secrets
chmod 700 ~/.ssh         # rwx------ — owner only              — private directories
chmod 777 anything      # rwxrwxrwx — DO NOT DO THIS IN PROD
```

### Symbolic Notation

```bash
chmod u+x file           # add execute for owner
chmod g-w file           # remove write for group
chmod o=r file            # set others to read-only, nothing else
chmod a+rx file           # all (u+g+o): read + execute
chmod -R g+rw /var/www    # recursive
```

### Ownership: chown / chgrp

```bash
chown deploy file              # change owner only
chown deploy:deploy file       # change owner + group
chown -R deploy:www-data /opt/myapp   # recursive, common on deploy
chgrp developers file          # change group only
```

### Senior Tip

```
Production checklist:
   chmod 600 .env
   chmod 600 ~/.ssh/id_rsa       (SSH refuses to use a key with looser perms)
   chmod 700 ~/.ssh
   chmod 755 deploy.sh
   chown -R app:app /opt/myapp   (never leave app files owned by root)

Anything world-writable (777, or *w for others) in prod = automatic
security audit finding.
```

---

## Users & Groups

### Key Files

```
/etc/passwd   one line per user: username:x:UID:GID:comment:home:shell
/etc/shadow   hashed passwords + expiry, root-readable only
/etc/group    one line per group: groupname:x:GID:member1,member2
/etc/sudoers  who can sudo, and with what restrictions (edit with visudo, never directly)
```

```bash
cat /etc/passwd | grep deploy
# deploy:x:1001:1001::/home/deploy:/bin/bash
#   │     │  │    │       │            └ login shell
#   │     │  │    │       └ home dir
#   │     │  │    └ GID
#   │     │  └ UID
#   │     └ password placeholder (real hash is in /etc/shadow)
#   └ username
```

### Managing Users & Groups

```bash
sudo useradd -m -s /bin/bash deploy       # create user, make home dir, set shell
sudo useradd -m -G sudo,docker deploy     # create + add to supplementary groups
sudo passwd deploy                        # set/change password
sudo usermod -aG docker deploy            # ADD to a group (-a = append, don't drop others!)
sudo userdel -r deploy                    # delete user + home dir

sudo groupadd developers                  # create group
sudo groupmod -n newname oldname          # rename group
sudo gpasswd -d deploy developers         # remove user from group

id deploy                                 # show UID/GID/groups
groups deploy                             # show groups
whoami                                    # current user
```

### sudo / sudoers

```bash
sudo <command>              # run command as root (prompts for YOUR password)
sudo -u postgres psql       # run as a specific user, not just root
sudo -i                     # interactive root shell
sudo -l                     # list what you're allowed to run

sudo visudo                 # edit sudoers safely (syntax-checks before saving)
```

```
# /etc/sudoers or /etc/sudoers.d/deploy — grant passwordless restart of one service
deploy ALL=(ALL) NOPASSWD: /usr/bin/systemctl restart myapp
```

### Senior Tip

```
- Never SSH in as root in production. Create a named user per engineer,
  add to a sudo/wheel group, disable root SSH login (PermitRootLogin no).
- Service accounts (the user your app RUNS as) should NOT have sudo and
  should NOT have a login shell (/usr/sbin/nologin).
- `usermod -aG` — always the -a flag. Forgetting it WIPES the user's
  other group memberships (classic footgun).
```

---

## Environment Variables

```bash
export DATABASE_URL="postgres://user:pass@host/db"   # set + export to child processes
echo $DATABASE_URL
env                          # list all env vars
printenv PATH                # print one var
unset DATABASE_URL           # remove

DEBUG=1 python app.py        # set for a single command, not exported/persisted
```

### Where variables get set persistently

```
~/.bashrc          non-login interactive shells (opens a new terminal tab)
~/.bash_profile    login shells (SSH login) — on Ubuntu, often sources .bashrc
~/.profile         POSIX-generic login shell config, read by sh/bash if no .bash_profile
~/.zshrc           zsh equivalent of .bashrc (default shell on macOS since Catalina)
/etc/environment   system-wide, NOT shell-parsed — simple KEY=VALUE only
/etc/profile.d/*.sh  system-wide, sourced by login shells for all users
```

```bash
echo 'export PATH="$HOME/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc             # reload without logging out
```

### PATH

```bash
echo $PATH
# /usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/home/deploy/bin

# Shell searches each colon-separated dir, in order, for the executable.
# First match wins — this is why a rogue script named `ls` earlier in
# PATH can shadow the real /bin/ls.

which python        # full path of what would run
type python          # shows if it's an alias/function/builtin/file
whereis python        # binary + man page + source locations
```

---

## Shell Types

| Shell | Notes |
|---|---|
| **sh** | Original Bourne shell / POSIX baseline. Scripts written for `sh` are maximally portable. |
| **bash** | Bourne Again Shell — default on most Linux distros and servers. Arrays, `[[ ]]`, process substitution. |
| **zsh** | Default on macOS since Catalina. Bash-compatible-ish with better completion/theming (oh-my-zsh). |
| **fish** | Friendly Interactive Shell — great UX (autosuggestions) but NOT POSIX-compatible; scripts written for fish don't run in bash. |

### Senior Tip

```
Write deployment/CI scripts with #!/usr/bin/env bash, not #!/bin/sh,
UNLESS you specifically need POSIX portability (e.g. Alpine's default
/bin/sh is actually `dash`, which lacks bash arrays and [[ ]]).

Alpine Docker images without `bash` installed will fail on any script
using bash-only syntax — this bites people constantly with slim images.
```

---

## Interview Angle

**Q: Difference between `apt` and `yum`/`dnf`?**
Both are package managers; the real difference is the packaging format underneath — `.deb` (APT/dpkg, Debian/Ubuntu) vs `.rpm` (YUM/DNF, RHEL/CentOS/Amazon Linux). DNF is the modern successor to YUM with a faster dependency resolver but near-identical command syntax.

**Q: Why does a private SSH key need `chmod 600`?**
SSH refuses to use a key readable by group/others — if any other user (or a leaked backup) could read your private key, that's the security model broken. `600` enforces owner-only access.

**Q: What's the difference between `/etc/passwd` and `/etc/shadow`?**
`passwd` holds user metadata (UID, home dir, shell) and is world-readable. `shadow` holds the actual password hashes and expiry policy, and is readable only by root — separated for exactly this security reason.

**Q: Why `usermod -aG` and not just `usermod -G`?**
`-G` alone *replaces* the user's supplementary group list. Without `-a` (append) you silently remove them from every other group they were in — a classic production incident.
