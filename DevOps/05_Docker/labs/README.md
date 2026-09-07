# Docker Labs — Runnable Exercises

`../practical/01_docker_lab.md` already has 4 solid walkthroughs (multi-stage
build + cache, compose startup ordering with healthchecks, bind mounts vs
volumes + custom networks, OOM-killed container diagnosis) — with solutions
shipped inline. This folder is 5 **different** labs, chosen specifically to
not overlap: build-secret leakage, deeper privilege-drop enforcement,
restart-policy semantics, filesystem hardening, and BuildKit cache mounts.
Each has a TODO-stub `Dockerfile`/`docker-compose.yml` and a `verify.sh`
that checks real container/image state and tells you PASS or FAIL.

## Setup

Just Docker itself (with BuildKit — enabled by default in modern Docker, or
export `DOCKER_BUILDKIT=1` if not):
```bash
docker version
docker buildx version   # needed for labs 1 and 5 (secret + cache mounts)
```

## Labs

| # | Lab | What it proves | New vs. `../practical/` |
|---|---|---|---|
| 1 | [01_build_secrets](01_build_secrets) | An `ARG` value is permanently readable via `docker history`; `--mount=type=secret` leaves zero trace | Not covered — the existing lab teaches layer-cache ordering, not secret handling |
| 2 | [02_privilege_drop](02_privilege_drop) | A non-root user genuinely can't write to `/root` or install packages — not just "whoami says something else" | Existing Lab 1 only checks `whoami`; this proves actual privilege enforcement (and documents a real dead end: port-binding as non-root isn't a portable test — depends on a host kernel sysctl) |
| 3 | [03_restart_policy](03_restart_policy) | `restart: on-failure:3` retries exactly 3 times then genuinely stops — not 0, not forever | Not covered — the existing labs don't touch restart policy semantics at all |
| 4 | [04_readonly_rootfs](04_readonly_rootfs) | `read_only: true` + a `tmpfs` mount locks the whole filesystem except one deliberate scratch path | Not covered — a different hardening axis from non-root or resource limits |
| 5 | [05_buildkit_cache_mount](05_buildkit_cache_mount) | `--mount=type=cache` survives a `requirements.txt` change that busts the normal layer cache | Complements the existing lab's layer-ORDER trick with the case that trick can't fix: the dependency file itself changing |

## Protocol

```
1. Open the lab's Dockerfile/docker-compose.yml, read the comment block at the top
2. Fill in the TODO(s)
3. Run ./verify.sh -> PASS moves you to the next lab; FAIL tells you
   specifically what it expected vs what it saw
4. Answer the README's SOCH questions out loud before moving on
```

## Checklist

- [ ] Lab 1 — Build secrets: `ARG` leaks, `--mount=type=secret` doesn't
- [ ] Lab 2 — Non-root privilege enforcement
- [ ] Lab 3 — Restart policy semantics (`on-failure:N`)
- [ ] Lab 4 — Read-only rootfs + tmpfs scratch space
- [ ] Lab 5 — BuildKit cache mounts
