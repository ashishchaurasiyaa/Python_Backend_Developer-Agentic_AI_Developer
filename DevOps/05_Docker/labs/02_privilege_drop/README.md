# Lab 2 — Non-root privilege enforcement (deeper than `whoami`)

**Goal:** `../practical/01_docker_lab.md` Lab 1 already checks that a
non-root container reports the right username via `whoami`. This lab goes
further: it proves the user actually **can't do root things**, not just
that its name isn't "root" — an identity check and a privilege check are
not the same thing.

**Task:** Open `Dockerfile`. It creates `appuser` and gives it ownership of
`/app`, but never switches to it — the container still runs as root. Add
`USER appuser` at the end.

**Verify:**
```bash
./verify.sh
```
Checks three things: (1) `whoami` is not `root`, (2) writing to `/root`
fails with Permission denied, (3) `apk add` (which needs to write to a
root-owned package database) also fails — while writing to its own `/app`
(which it owns) still succeeds. PASS requires all four.

> **A dead end worth knowing about:** an earlier version of this lab also
> tried to prove non-root couldn't bind to port 80 (the classic "privileged
> ports need root" fact). Live-testing showed that check is **not
> portable** — this host's kernel has
> `net.ipv4.ip_unprivileged_port_start=0`, meaning literally any user can
> bind any port here, a per-host kernel sysctl that Docker itself doesn't
> control. Check yours with
> `docker run --rm alpine cat /proc/sys/net/ipv4/ip_unprivileged_port_start`
> — file permissions and package-manager writes don't have this problem,
> which is exactly why the lab uses those instead.

**SOCH:**
- Why does `apk add` fail for a non-root user even though `/app` (which the
  same user owns) accepts writes just fine? What's actually different about
  the two paths, permission-wise?
- The port-binding dead end above is a real example of "the theory is
  right, but the specific number (1024) isn't guaranteed on every host."
  Where else in Linux/Docker have you seen a "well-known constant" that
  actually turns out to be host/kernel-configurable rather than fixed?
