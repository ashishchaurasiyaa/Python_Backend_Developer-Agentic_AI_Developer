# Docker Basics — Images, Containers, Engine Architecture
**DevOps Track · Phase 5: Docker**

> Complementary to Backend_Developer/01_Year3-4_Mid/04_DevOps/01_docker.md (app-deployment angle) — this covers the full Docker engine model.

## Quick Concepts

- **Image** = read-only, immutable template built from layered instructions (a Dockerfile)
- **Container** = a running (or stopped) instance of an image, with a writable layer on top
- **Layer** = one filesystem diff produced by one Dockerfile instruction, cached and content-addressed
- **Union filesystem (UnionFS/OverlayFS)** = stacks layers into a single merged view the process sees
- **Docker Engine** = the whole client-server system: `dockerd` (daemon) + `containerd` + `runc`
- **containerd** = high-level container runtime (image pull, storage, lifecycle) — CNCF graduated project
- **runc** = low-level OCI runtime that actually creates namespaces/cgroups and execs the container process
- **OCI (Open Container Initiative)** = spec standardizing image format and runtime behavior, so Docker/Podman/containerd images are interchangeable
- **Docker Desktop** = GUI + VM wrapper for macOS/Windows (Docker Engine only runs natively on Linux)
- **Namespace** = kernel feature giving a process an isolated view (PID, NET, MNT, UTS, IPC, USER)
- **cgroup** = kernel feature limiting/accounting a process's resource usage (CPU, memory, I/O)
- **`docker exec`** = run a new process inside an ALREADY-RUNNING container (vs `docker run`, which starts a new one)
- **Dangling image** = an untagged, unreferenced image layer left behind after a rebuild — what `docker image prune` cleans up

---

## Why This Matters

```
Every "how do I deploy this" question eventually needs an answer to
"what actually IS a container" — because debugging container issues
(OOM kills, layer bloat, permission errors, slow builds, "works on my
machine") requires knowing:

   - images are layers, not a single blob → cache invalidation matters
   - containers are just Linux processes → `ps aux` on the host shows them
   - isolation comes from namespaces/cgroups, NOT a VM → no separate kernel
   - the daemon does the heavy lifting → client is just a thin CLI

An infra engineer who only knows `docker run` hits a wall the moment
something misbehaves in production. This file is the "what's under
the hood" layer — the deployment-focused file covers "how do I ship."
```

---

## Day-to-Day Docker CLI — The Commands You'll Actually Type

Before the architecture deep-dive below, the actual daily-driver commands — everything past this section explains WHY these behave the way they do.

### `docker run` — Common Flags

```bash
docker run nginx                       # foreground, attached to your terminal —
                                          # Ctrl+C stops it
docker run -d nginx                      # DETACHED — runs in the background,
                                            # returns your terminal immediately
docker run -it ubuntu bash                 # INTERACTIVE + pseudo-TTY — for a
                                              # shell session inside a container
docker run --rm alpine echo "hi"             # auto-REMOVE the container the
                                                # instant it exits — use this for
                                                # any one-off/throwaway run so
                                                # `docker ps -a` doesn't fill up
                                                # with stopped containers
docker run --name myapi -d myapp               # give it a fixed, memorable name
                                                  # instead of a random one
docker run -p 8080:80 nginx                      # host:container port mapping
docker run -e LOG_LEVEL=debug myapp                # set an env var at run time
docker run -v pgdata:/var/lib/postgresql/data postgres:16  # mount a volume

# The combination you'll actually type most often for local dev:
docker run -d --name api --rm -p 8000:8000 -e DEBUG=true myapp
```

### Inspecting What's Running

```bash
docker ps                    # running containers only
docker ps -a                   # ALL containers, including stopped/exited ones —
                                  # the first command to run when "docker run"
                                  # seemed to do nothing (it probably exited
                                  # immediately; ps -a shows the exit code)
docker images                    # all images on this host, with size
docker inspect <container>         # full JSON detail — state, mounts, network,
                                      # env vars, everything (see the OOM
                                      # debugging example below for a real use)
```

### Starting, Stopping, Restarting

```bash
docker stop myapp        # graceful — sends SIGTERM, waits (default 10s grace
                            # period), then SIGKILLs if it hasn't exited —
                            # same signal mechanics as the Bash phase's
                            # SIGTERM-handling section, just at the Docker CLI level
docker kill myapp           # immediate SIGKILL, no grace period, no chance
                               # for the process to clean up at all
docker start myapp             # start a STOPPED (not removed) container again,
                                  # same container ID, same filesystem state
docker restart myapp               # stop + start in one command
docker rm myapp                      # remove a STOPPED container entirely
                                        # (fails if it's still running — stop first,
                                        # or use `docker rm -f` to force-stop+remove)
```

### Getting Inside a Running Container

```bash
docker exec -it myapp bash        # shell into an ALREADY-RUNNING container
                                     # (vs `docker run -it` which starts a NEW one)
docker exec myapp env                 # run ONE command inside it and see the
                                         # output, without a full interactive shell
docker cp myapp:/app/logs/error.log ./     # copy a file OUT of a running container
docker cp ./config.yml myapp:/app/config.yml  # copy a file INTO a running container
```

```
docker exec vs docker attach — a common point of confusion:
  docker exec     → starts a NEW process inside the container (a new
                     shell, alongside whatever's already running) —
                     exiting the shell does NOT stop the container
  docker attach     → connects to the container's ORIGINAL PID 1
                        process's stdin/stdout directly — exiting
                        (Ctrl+C) can actually STOP the container if PID 1
                        was reading from that stdin. `exec` is almost
                        always what you actually want for debugging.
```

### Logs

```bash
docker logs myapp                 # full log history since container start
docker logs -f myapp                # FOLLOW — stream new lines live (Ctrl+C to stop watching)
docker logs --tail 100 myapp          # just the last 100 lines
docker logs --since 10m myapp            # only logs from the last 10 minutes
```

### Cleaning Up — Disk Space Management

Docker accumulates stopped containers, dangling images, unused networks, and build cache over time — a real host can quietly fill its disk with this if nobody ever cleans up.

```bash
docker container prune       # remove ALL stopped containers
docker image prune             # remove DANGLING images only (untagged, unreferenced layers)
docker image prune -a            # remove ALL unused images, not just dangling ones — more aggressive
docker volume prune                # remove unused volumes — CAREFUL, this can delete real data
                                      # if a volume isn't currently attached to any container
docker builder prune                 # clear BuildKit's build cache (the cache mounts and
                                        # layer cache from Phase 5's Dockerfile file)

docker system df                       # see how much disk Docker is actually using,
                                          # broken down by images/containers/volumes/build-cache
docker system prune -a --volumes         # the "nuclear option" — removes everything
                                            # unused across all categories at once;
                                            # NEVER run this on a host with real data
                                            # in volumes you still need
```

**Senior tip:** `docker system df` before `docker system prune -a --volumes`, always — know what you're about to delete before deleting it. A CI runner or dev machine accumulating gigabytes of unused images is normal and safe to prune aggressively; a host running production databases in Docker-managed volumes is NOT a place to run `--volumes` casually.

---

## Images vs Containers

### The Class vs Object Analogy — But Precise

```
Image                              Container
------                             ---------
Read-only                          Read-write (thin writable layer on top)
Built once, reused many times      Created fresh from an image each run
Stored as layers + manifest        Adds ONE extra writable layer + own
                                    network namespace, PID namespace, etc.
Identified by name:tag or digest   Identified by container ID / name
docker build                       docker run / docker create + start
```

### Layered Filesystem — What a Build Actually Produces

Each instruction in a Dockerfile that changes the filesystem (`RUN`, `COPY`, `ADD`) creates a new **layer** — a diff against the layer below it. Layers are content-addressed (hashed) and cached; unchanged layers are reused across builds.

```
Image "myapp:1.0" — stack of layers, bottom to top:

┌─────────────────────────────────────┐
│ Layer 5: COPY . .            (app code)   │ ← changes most often
├─────────────────────────────────────┤
│ Layer 4: RUN pip install -r req.txt │ ← changes when deps change
├─────────────────────────────────────┤
│ Layer 3: COPY requirements.txt .    │
├─────────────────────────────────────┤
│ Layer 2: RUN apt-get install curl   │ ← rarely changes
├─────────────────────────────────────┤
│ Layer 1: FROM python:3.12-slim      │ ← base image, many layers itself
└─────────────────────────────────────┘
        ↑ each layer = read-only, immutable, hashed (sha256:abc123...)
```

When you `docker run` that image, Docker adds one more layer on top:

```
┌─────────────────────────────────────┐
│ Container writable layer             │ ← RW, deleted when container is rm'd
│  (any files the app writes at runtime go here)
├─────────────────────────────────────┤
│ Layer 5 (RO) ─ Layer 1 (RO)          │ ← shared, read-only, from the image
└─────────────────────────────────────┘
```

This is **copy-on-write**: if the container modifies a file that exists in a lower read-only layer, that file is copied up into the writable layer first, then modified. The underlying image is never touched — which is why one image can back hundreds of running containers simultaneously without them stepping on each other.

### Union Filesystem

Docker doesn't literally "stack" files at the OS level — it uses a **union filesystem driver** (on Linux, almost always **OverlayFS** today; older setups used AUFS, devicemapper, btrfs, zfs) to present all the layers as one merged directory tree to the process inside the container.

```
OverlayFS terms:
  lowerdir   = the read-only image layers (can be multiple, stacked)
  upperdir   = the container's writable layer
  merged     = the final view the container process sees (mounted as /)
  workdir    = internal scratch space OverlayFS needs for atomic operations
```

```bash
# See which storage driver your daemon uses
docker info | grep "Storage Driver"

# Inspect actual layers of an image
docker history myapp:1.0
docker inspect myapp:1.0 --format '{{.RootFS.Layers}}'
```

### Why Layer Ordering Matters (Build Cache)

Docker builds top-down and invalidates a layer — and every layer after it — the moment its instruction's input changes.

```dockerfile
# BAD — any code change busts the pip install cache too
COPY . .
RUN pip install -r requirements.txt

# GOOD — requirements.txt changes far less often than app code,
# so this layer stays cached across most rebuilds
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
```

---

## Docker Engine Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                         Your Terminal                          │
│   docker build / docker run / docker ps  ──►  docker CLI      │
└───────────────────────────┬────────────────────────────────────┘
                             │ REST API over Unix socket
                             │ (/var/run/docker.sock) or TCP
                             ▼
┌──────────────────────────────────────────────────────────────┐
│                       dockerd (daemon)                          │
│  - image build orchestration                                   │
│  - network + volume management                                 │
│  - exposes Docker Engine API                                   │
└───────────────────────────┬────────────────────────────────────┘
                             │ gRPC
                             ▼
┌──────────────────────────────────────────────────────────────┐
│                        containerd                               │
│  - image pull/push, content store                              │
│  - container lifecycle (create/start/stop/delete)              │
│  - manages "shim" processes (one per container)                │
└───────────────────────────┬────────────────────────────────────┘
                             │ spawns
                             ▼
┌──────────────────────────────────────────────────────────────┐
│              containerd-shim  →  runc                           │
│  runc: OCI-compliant low-level runtime.                        │
│  Creates namespaces + cgroups, execs the container's PID 1,    │
│  then EXITS — the shim keeps the container alive so containerd │
│  isn't in the direct parent chain (allows dockerd to restart   │
│  without killing running containers).                          │
└──────────────────────────────────────────────────────────────┘
```

### Component Responsibilities

| Component | Layer | Responsibility |
|---|---|---|
| `docker` (CLI) | Client | Thin client, translates commands to REST API calls |
| `dockerd` | Daemon | High-level orchestration, build, networks, volumes, API server |
| `containerd` | Container runtime (high-level) | Image management, container lifecycle, industry-standard (also used directly by Kubernetes via CRI) |
| `containerd-shim` | Glue | Keeps container's stdin/stdout open, reports exit status, decouples container from containerd's own lifecycle |
| `runc` | Container runtime (low-level) | OCI spec implementation — actually creates the namespaces/cgroups and execs the process |

### Why This Split Matters

- **Kubernetes doesn't use `dockerd` directly anymore** — it talks to a CRI (Container Runtime Interface) implementation, which is usually **containerd** directly (or CRI-O). This is why "Docker is deprecated in Kubernetes" headlines happened in 2022 — `dockershim` was removed, but containerd (which Docker itself sits on top of) is still the same tech underneath.
- Because `runc` implements the **OCI runtime spec** and Docker builds **OCI-compliant images**, an image built with `docker build` can run under `containerd`, `CRI-O`, or `podman` without modification.

### What Isolation Actually Is

```
Container isolation = Linux kernel features, not a hypervisor.

Namespaces (what the process CAN'T SEE):
  PID     → own process tree, container's PID 1 is not the host's PID 1
  NET     → own network interfaces, routing table, ports
  MNT     → own filesystem mount points
  UTS     → own hostname
  IPC     → own shared memory / semaphores
  USER    → own UID/GID mapping (container root ≠ host root, if configured)

cgroups (what the process CAN'T EXCEED):
  cpu     → CPU shares / quota
  memory  → hard memory limit (OOM-killed if exceeded)
  blkio   → disk I/O throttling
  pids    → max number of processes (fork bomb protection)

Net effect: a container is a REGULAR LINUX PROCESS on the host.
  ps aux                 # on the host — you'll see container processes
  docker top <container> # maps back to host PIDs
```

This is why containers start in milliseconds and share the host kernel — there is no separate OS booting, unlike a VM.

---

## Resource Limits — Putting cgroups Into Practice

Namespaces (above) control what a process can SEE; cgroups control what it can CONSUME. Without explicit limits, a single container can exhaust the host's entire memory or CPU — a noisy-neighbor problem that takes down every OTHER container on that host, not just the misbehaving one.

```bash
docker run --memory=512m --memory-swap=512m myapp
# --memory        hard memory ceiling — exceeding it gets the container
#                  OOM-KILLED by the kernel, not gracefully throttled
# --memory-swap    total memory+swap ceiling; setting it EQUAL to --memory
#                  disables swap for this container entirely (usually
#                  what you want for a predictable, debuggable limit —
#                  swap thrashing is often worse than a clean OOM kill)

docker run --cpus="1.5" myapp          # max 1.5 CPU cores' worth of time
docker run --cpu-shares=512 myapp        # RELATIVE weight vs other containers
                                            # when the host is CPU-CONTENDED
                                            # (1024 = default/"normal" share)
docker run --pids-limit=100 myapp          # cap max process count — fork-bomb protection
```

```bash
# See what a running container is ACTUALLY using, live
docker stats                          # all containers
docker stats myapp --no-stream          # one snapshot, one container

# After a container has exited — was it OOM-killed, or did it crash normally?
docker inspect myapp --format '{{.State.OOMKilled}} exit={{.State.ExitCode}}'
# OOMKilled=true, exit=137 (128 + signal 9/SIGKILL) → the kernel's cgroup
# OOM killer terminated it for exceeding --memory — NOT an application crash
```

```
The single most important operational fact here: an OOM-killed
container's application logs usually show NOTHING useful. The kernel
kills the process abruptly (SIGKILL, uncatchable) the instant it
crosses the memory cgroup limit — there's no graceful "about to run
out of memory" warning the app gets a chance to log. The FIRST place
to look when a container mysteriously exits with no error in its own
logs is `docker inspect ... OOMKilled` and exit code 137, not the
application's log output.
```

```
--memory-shares vs --memory — the distinction that trips people up:
   --memory        is a HARD ceiling — enforced unconditionally
   --cpu-shares      is a RELATIVE weight — only matters when the host
                     is CPU-CONTENDED; if the host has spare CPU, a
                     container with a low cpu-shares value can still
                     use as much CPU as it wants. There is no equivalent
                     "soft" version of --memory — memory limits are
                     always hard, because unlike CPU time, memory can't
                     be time-sliced/reclaimed the same way.
```

**Senior framing:** resource limits aren't primarily about the container that gets killed — they're about protecting every OTHER container on the same host from one runaway process. An unlimited container is a shared-infrastructure risk, not just a self-contained one; this is why Kubernetes REQUIRES `resources.limits` be considered a first-class scheduling input (Phase 6), not an optional afterthought.

---

## Docker Desktop vs Docker Engine on Linux

| | Docker Engine (native Linux) | Docker Desktop (macOS/Windows) |
|---|---|---|
| Kernel | Uses host Linux kernel directly | Runs a lightweight Linux **VM** (LinuxKit) because macOS/Windows kernels can't run Linux namespaces/cgroups |
| Daemon location | Runs as a systemd service on the host | Runs inside the VM; CLI on host talks to it via a socket forwarded from the VM |
| Performance | Native — no virtualization overhead | Near-native for CPU, historically slower for bind-mount file I/O (VM boundary) |
| Networking | Direct host network namespaces | NAT'd through the VM; `host` network mode is Linux-only, doesn't work the same on Desktop |
| Licensing | Free, open source (Moby project) | Free for personal/small business use; paid for larger companies (since 2021) |
| Extras | None built in | GUI, Kubernetes single-node cluster toggle, resource limit sliders, extensions |

```bash
# Check what you're actually running
docker version              # look at "Server: OS/Arch" — linux/amd64 even on Mac (it's the VM)
docker info                 # shows kernel version — on Mac this is the LinuxKit VM's kernel, not macOS's
```

### Senior Tip

```
On production Linux servers you will NEVER use Docker Desktop —
it's a local-dev convenience tool. Production runs plain Docker
Engine (or more commonly, just containerd + Kubernetes with no
Docker CLI installed at all).

If a candidate says "I use Docker Desktop in production" — red flag.
Docker Desktop is a dev-machine GUI wrapper around a Linux VM;
it's never the production runtime.
```

---

## Interview Angle

**Q: If Kubernetes removed Docker support (dockershim), why do my images still work?**
Because Docker builds OCI-compliant images and Kubernetes talks to containerd (or CRI-O) directly via CRI. `dockerd` itself was the layer removed — the image format and the `containerd`/`runc` stack underneath Docker are unchanged and still what runs your image.

**Q: Why is a container not a "lightweight VM"?**
A VM virtualizes hardware and boots its own kernel via a hypervisor. A container is a normal process isolated by namespaces and constrained by cgroups, sharing the host kernel directly — no hypervisor, no second kernel, no boot process. That's why containers start in ~100ms and VMs take tens of seconds.

**Q: Two containers from the same image both write to `/app/data` — do they interfere?**
No. Each container gets its own writable layer via copy-on-write. Writes in one container's upperdir are invisible to the other. If you need shared, persistent data across containers, that requires an explicit volume mount, not the default layered filesystem.

**Q: You ran `docker run myapp` and it seemed to do nothing — the terminal returned instantly with no output. What do you check?**
`docker ps -a` (not just `docker ps`) — the container almost certainly started and exited immediately. `docker ps` only shows running containers, so an already-exited one is invisible there; `docker ps -a` shows it along with its exit code, and `docker logs <container>` shows whatever it printed before exiting, which is usually the actual clue (a missing file, a crashed entrypoint, a config error).

**Q: What's the actual difference between `docker exec` and `docker attach`, and why does it matter which one you use to debug a running container?**
`docker exec` starts a brand-new process inside the container (a fresh shell alongside whatever's already running) — exiting that shell doesn't affect the container at all. `docker attach` connects directly to the container's original PID 1 process's stdin/stdout — if PID 1 is reading from that stdin, exiting (Ctrl+C) can actually kill the container itself. `docker exec -it <container> bash` is almost always the safer, correct choice for debugging.

**Q: A container exits with no error in its application logs — `docker logs` shows nothing useful right before it died. What do you check first?**
Whether it was OOM-killed: `docker inspect <container> --format '{{.State.OOMKilled}} exit={{.State.ExitCode}}'`. Exit code 137 (128 + SIGKILL) with `OOMKilled: true` means the kernel's cgroup OOM killer terminated the process for exceeding its `--memory` limit — an uncatchable kill with no chance for the app to log a graceful warning first, which is exactly why the application's own logs show nothing.

---

## Related

- [`../14_Security/02_owasp_container_k8s_security.md`](../14_Security/02_owasp_container_k8s_security.md) — container hardening (`--cap-drop`, `--read-only`, seccomp, `no-new-privileges`) and distroless base images
- [`../06_Kubernetes/04_scaling_security_rbac.md`](../06_Kubernetes/04_scaling_security_rbac.md) — how these same cgroup limits become `resources.requests`/`resources.limits` in a Kubernetes Pod spec
- [`02_dockerfile.md`](02_dockerfile.md) — how these runtime concepts (layers, USER, resource behavior) get built into an image in the first place
