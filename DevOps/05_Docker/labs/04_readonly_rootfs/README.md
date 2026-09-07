# Lab 4 — Read-only root filesystem + tmpfs scratch space

**Goal:** `read_only: true` locks a container's entire filesystem — if
compromised, an attacker can't drop a binary, tamper with an installed one,
or persist anything. The catch: almost every real app needs to write
*somewhere* (temp files, a cache). `tmpfs` gives it exactly that, in memory,
without reopening the whole filesystem.

**Task:** Open `docker-compose.yml`. The `app` service is already
`read_only: true` — but has no `tmpfs` mount at all, so even `/tmp` is
locked. Add:
```yaml
tmpfs:
  - /tmp
```

**Verify:**
```bash
./verify.sh
```
Checks two things: writing outside `/tmp` (e.g. `/app-testfile`) must
**always** fail (read-only root, unconditionally — this isn't part of the
TODO), and writing inside `/tmp` must **only** succeed once the tmpfs mount
exists. PASS requires both.

**SOCH:**
- A `tmpfs` mount is backed by RAM, not disk, and disappears entirely when
  the container stops. What's one real category of app data that would be a
  correctness bug to accidentally put in a tmpfs-mounted path, versus one
  that's a perfect fit for it?
- `read_only: true` at the container level and `USER appuser` (Lab 2) are
  both "assume this will be compromised" hardening moves, but they defend
  against different attacker actions. If an attacker got code execution
  inside this container, what could `read_only` stop them from doing that
  a non-root user alone would NOT stop, and vice versa?
