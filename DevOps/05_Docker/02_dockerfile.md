# Dockerfile — Full Instruction Set
**DevOps Track · Phase 5: Docker**

## Quick Concepts

- **Dockerfile** = declarative build script, one instruction per layer, read top to bottom
- **FROM** = base image to start from (every Dockerfile needs at least one)
- **RUN** = execute a command at *build* time, result baked into the image
- **CMD** = default command at *container start* time, overridable from the CLI
- **ENTRYPOINT** = fixed executable at container start time, harder to override
- **COPY** = copy files from build context into the image
- **ADD** = COPY plus extra magic (URL fetch, tar auto-extract) — mostly avoid it
- **ENV** = persistent environment variable, baked into the image, visible at runtime
- **ARG** = build-time-only variable, NOT present in the running container
- **WORKDIR** = sets the working directory for subsequent instructions and the container's default CWD
- **Build context** = the directory sent to the daemon for the build (`.` in `docker build .`)
- **Multi-stage build** = multiple `FROM` blocks in one Dockerfile, only the last stage ships

---

## Why This Matters

```
The Dockerfile is the single source of truth for "how is this image
built." Every instruction choice affects:
   - final image size (RUN vs COPY vs ADD, layer ordering)
   - build speed (cache invalidation)
   - runtime behavior (CMD vs ENTRYPOINT — does `docker run img extra-arg`
     REPLACE the command or APPEND to it?)
   - security (running as root, leaking build secrets via ARG)

Getting CMD vs ENTRYPOINT wrong is one of the most common Dockerfile
mistakes people carry into production without noticing.
```

---

## FROM

```dockerfile
FROM python:3.12-slim              # official image, specific tag (NEVER use :latest in prod)
FROM python:3.12-slim AS builder   # named stage, referenced later in multi-stage builds
FROM scratch                       # empty base — for statically linked binaries (Go, Rust)
FROM --platform=linux/amd64 node:20  # pin platform for multi-arch build hosts
```

- Always pin a specific tag (`3.12-slim`, not `latest`) — `latest` drifts and breaks reproducibility.
- `-slim` / `-alpine` variants trade some compatibility (musl libc on Alpine can break native wheels) for much smaller size.
- `scratch` is the literal empty base — only works for binaries with zero external dependencies (statically compiled).

---

## Multi-Platform Builds — `docker buildx`

`FROM --platform=...` (above) pins a SINGLE target architecture. Building an image that actually runs on BOTH `linux/amd64` (most cloud instances, Intel/AMD Macs) and `linux/arm64` (Apple Silicon Macs, and — per `07_Cloud_AWS`'s own recommendation — AWS Graviton instances, which are meaningfully cheaper for the same performance class) needs `buildx`.

```bash
# One-time setup — creates a builder that can actually cross-compile,
# not just tag an image as a platform it wasn't really built for
docker buildx create --name multiarch --use
docker buildx inspect --bootstrap

# Build AND push a single tag backed by BOTH architectures at once
docker buildx build \
  --platform linux/amd64,linux/arm64 \
  -t myrepo/myapp:1.0 \
  --push \
  .
```

```
The result is ONE tag (myrepo/myapp:1.0) backed by a multi-arch
MANIFEST LIST — when a host pulls it, Docker automatically fetches
the layer set matching THAT host's actual architecture. A Graviton
(arm64) EC2 instance and an Intel (amd64) laptop both `docker pull
myrepo/myapp:1.0` and each gets the correct architecture's image,
transparently — no separate :amd64/:arm64 tags for consumers to
manage themselves.
```

```bash
# Local-only build for a single non-native platform (testing, no push)
# uses QEMU emulation under the hood — noticeably slower than native,
# fine for a smoke test, not for your actual CI build path
docker buildx build --platform linux/arm64 -t myapp:arm-test --load .

# Inspect what architectures an existing tag actually supports
docker buildx imagetools inspect myrepo/myapp:1.0
```

```
Why `--load` can't be combined with multi-platform: `--load` puts the
built image into your LOCAL Docker image store, which can only hold
one architecture's image at a time under a given tag — `--push`
(straight to a registry) is required for genuinely multi-arch output,
since a manifest list is a registry-level concept, not a local one.
```

**Senior framing:** the CI-relevant version of this is a single pipeline step — `docker buildx build --platform linux/amd64,linux/arm64 --push` — replacing what would otherwise be two separate build jobs (one per architecture) plus a manual manifest-list assembly step. Worth knowing this exists the moment ARM-based compute (Graviton, Apple Silicon dev machines building images that also need to run on amd64 prod) enters the picture at all.

---

## COPY vs ADD — and Why COPY Wins

| | COPY | ADD |
|---|---|---|
| Copy local files | Yes | Yes |
| Copy from a URL | No | Yes — downloads remote file into image |
| Auto-extract local `.tar`/`.tar.gz` | No | Yes — auto-untars into destination |
| Behavior transparency | Fully predictable | "Magic" — easy to trigger unintentionally |
| Recommended default | **Yes, always prefer this** | Only when you specifically need tar auto-extraction |

```dockerfile
# COPY — explicit, predictable, cacheable
COPY requirements.txt .
COPY src/ ./src/
COPY --chown=appuser:appgroup . .     # set ownership while copying

# ADD — avoid for plain file copies
ADD https://example.com/file.tar.gz /tmp/   # fetches over network at BUILD time,
                                             # no caching of the download, no checksum
                                             # verification by default — security risk
ADD archive.tar.gz /app/                    # auto-extracts — convenient but implicit,
                                             # can surprise you if a filename ever changes
                                             # from a normal file to a tarball
```

**Why COPY is preferred:** Docker's own best practices explicitly recommend COPY unless you need ADD's specific extraction/URL behavior. ADD's implicit magic makes builds harder to reason about and its URL-fetch has no build-time caching or integrity check — prefer an explicit `RUN curl` (which you control, and can checksum) if you need a remote file.

---

## RUN

Executes at **build time**. Each `RUN` is a new layer.

```dockerfile
# Bad — 3 layers, and apt cache stays baked into the image
RUN apt-get update
RUN apt-get install -y curl
RUN rm -rf /var/lib/apt/lists/*

# Good — one layer, cache cleaned in the SAME instruction
# (cleaning in a later RUN doesn't shrink earlier layers — they're already committed)
RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*
```

```dockerfile
# Shell form — runs via /bin/sh -c, supports shell features ($VAR, &&, |)
RUN echo "hello $NAME"

# Exec form — runs directly, no shell, no variable expansion
RUN ["echo", "hello"]
```

---

## CMD vs ENTRYPOINT — Worked Example

Both define what runs when the container starts. The difference is **overridability**.

```dockerfile
# --- Scenario A: CMD only ---
CMD ["python", "app.py"]
```

```dockerfile
# --- Scenario B: ENTRYPOINT only ---
ENTRYPOINT ["python", "app.py"]
```

```dockerfile
# --- Scenario C: ENTRYPOINT + CMD together (the recommended pattern) ---
ENTRYPOINT ["python", "app.py"]
CMD ["--port", "8000"]
```

| `docker run <image>` variant | Scenario A (CMD only) | Scenario B (ENTRYPOINT only) | Scenario C (both) |
|---|---|---|---|
| `docker run img` | `python app.py` | `python app.py` | `python app.py --port 8000` |
| `docker run img /bin/bash` | `/bin/bash` (CMD fully replaced) | `python app.py /bin/bash` (appended as an ARG to entrypoint — likely breaks!) | `python app.py /bin/bash` (CMD's default replaced by `/bin/bash`, appended to entrypoint) |
| `docker run img --port 9000` | `--port 9000` (tries to exec a binary called `--port`, fails) | `python app.py --port 9000` | `python app.py --port 9000` |
| `--entrypoint` flag override | Can add an entrypoint | `docker run --entrypoint /bin/bash img` overrides it | Same — `--entrypoint` is the only way to override ENTRYPOINT |

**Rule of thumb:**
- `CMD` alone = "default command, fully replaceable" — good for generic dev images.
- `ENTRYPOINT` alone = "this container IS this program" — but a bare arg like `docker run img /bin/bash` gets appended as an argument, not substituted, which usually errors.
- `ENTRYPOINT` + `CMD` together = fixed program (ENTRYPOINT), overridable default arguments (CMD) — this is the production pattern for a "container that always runs one binary but takes configurable flags."

```dockerfile
# Real pattern: entrypoint script for startup logic (migrations, env checks),
# then hand off to CMD
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh
ENTRYPOINT ["/entrypoint.sh"]
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

```bash
#!/bin/sh
# entrypoint.sh
set -e
python manage.py migrate --noinput
exec "$@"    # hands off to whatever CMD (or docker run override) provided
```

---

## ENV vs ARG

| | ENV | ARG |
|---|---|---|
| Available at build time | Yes | Yes |
| Available at container runtime | **Yes** — baked into image, visible via `docker inspect` / `printenv` | **No** — gone once the image is built |
| Set via `docker build` | No (fixed in Dockerfile, or override with `docker run -e`) | Yes — `docker build --build-arg KEY=value` |
| Typical use | App config that should exist at runtime (`PYTHONUNBUFFERED=1`, `PORT=8000`) | Build-time parameters (`PYTHON_VERSION`, feature flags for the build, NOT secrets) |
| Security note | Visible in `docker history` / `docker inspect` — never put secrets here | Also visible in `docker history` unless using BuildKit secret mounts — **never put secrets here either** |

```dockerfile
ARG PYTHON_VERSION=3.12
FROM python:${PYTHON_VERSION}-slim

ARG BUILD_ENV=production
ENV APP_ENV=${BUILD_ENV} \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# ARG PYTHON_VERSION above is scoped BEFORE the first FROM;
# ARGs declared after FROM are scoped to that build stage only
```

```bash
docker build --build-arg PYTHON_VERSION=3.11 --build-arg BUILD_ENV=staging -t myapp .
```

**Real secrets belong in BuildKit secret mounts, not ARG/ENV:**

```dockerfile
# syntax=docker/dockerfile:1
RUN --mount=type=secret,id=pip_token \
    PIP_INDEX_URL=https://$(cat /run/secrets/pip_token)@pypi.internal/simple pip install mypkg
```

```bash
DOCKER_BUILDKIT=1 docker build --secret id=pip_token,src=./token.txt -t myapp .
# secret is available only during that RUN, never persisted in any layer
```

### BuildKit Cache Mounts — Faster Rebuilds Without Bloating Layers

A separate BuildKit feature from secret mounts, solving a different problem: package manager caches (pip, npm, apt) speed up repeat installs, but naively they either get baked into the image (bloat) or get wiped every build (`rm -rf /var/lib/apt/lists/*` pattern shown earlier) and rebuilt from scratch every time (slow). A **cache mount** persists a directory ACROSS builds without it ever becoming part of any image layer.

```dockerfile
# syntax=docker/dockerfile:1

# pip — persist pip's download cache across builds
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install -r requirements.txt

# apt — persist apt's package cache across builds (note: still rm the
# LISTS as before for a clean image; the CACHE MOUNT is separate from
# what ends up in the actual image layer)
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt/lists,sharing=locked \
    apt-get update && apt-get install -y --no-install-recommends curl

# npm — same idea
RUN --mount=type=cache,target=/root/.npm \
    npm ci
```

```
Why this is genuinely different from ordinary layer caching:
  - Ordinary layer cache is invalidated the MOMENT requirements.txt
    changes at all — even adding one new package re-runs the ENTIRE
    pip install from zero, re-downloading every dependency.
  - A cache mount PERSISTS across builds regardless of layer
    invalidation — even when requirements.txt changes and the RUN
    instruction re-executes, pip's download cache is still there from
    last time, so only the NEW/changed packages actually re-download.
  - The cache mount's CONTENTS never become part of any image layer —
    it's scratch space that exists only during the build, shared
    across build invocations, not shipped in the final image at all.

sharing=locked → prevents two concurrent builds from corrupting the
                  same cache directory; use it for anything a package
                  manager writes an index/lock file into.
```

```bash
docker build .          # first build — full download, slow
# ... change one line in requirements.txt ...
docker build .          # second build — layer cache still busts on
                           # requirements.txt change, BUT pip's cache
                           # mount means only the changed package
                           # actually re-downloads, not everything
```

**Senior framing:** secret mounts solve "how do I use a credential at build time without it leaking into the image." Cache mounts solve "how do I make repeat builds fast without that speed cost showing up as bloat in the final image." Both are BuildKit `--mount` types solving adjacent-but-different problems — worth being clear on which one a given interview question is actually asking about.

---

## WORKDIR

```dockerfile
WORKDIR /app        # creates /app if missing, sets it as CWD for all following
                     # instructions (COPY, RUN, CMD) AND as the container's default CWD

# Prefer WORKDIR over `RUN cd /app && ...` — `cd` inside RUN doesn't persist
# to the NEXT RUN instruction (each RUN is its own shell invocation)
```

```dockerfile
# WRONG — cd doesn't persist across instructions
RUN cd /app
RUN pip install -r requirements.txt   # runs in the image's default dir, NOT /app

# RIGHT
WORKDIR /app
RUN pip install -r requirements.txt   # runs in /app
```

---

## Full Multi-Stage Dockerfile — Python App

```dockerfile
# syntax=docker/dockerfile:1

# ---------- Stage 1: builder ----------
FROM python:3.12-slim AS builder

ARG POETRY_VERSION=1.8.0
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# system deps needed ONLY to build wheels (gcc for psycopg2, etc.)
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# copy dependency manifests FIRST — maximizes cache hits
COPY requirements.txt .
RUN pip install --prefix=/install -r requirements.txt

# ---------- Stage 2: runtime ----------
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/usr/local/bin:${PATH}"

# runtime-only system deps (libpq5, NOT libpq-dev — no compiler needed here)
RUN apt-get update && apt-get install -y --no-install-recommends \
        libpq5 \
        curl \
    && rm -rf /var/lib/apt/lists/* \
    && addgroup --system appgroup \
    && adduser --system --ingroup appgroup appuser

WORKDIR /app

# pull only the installed packages from the builder stage — no compiler,
# no build cache, no source archives leak into the final image
COPY --from=builder /install /usr/local
COPY --chown=appuser:appgroup . .

USER appuser
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

ENTRYPOINT ["python", "-m"]
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

```bash
# build only up to the builder stage (useful for CI dependency caching layers)
docker build --target builder -t myapp:builder .

# full multi-stage build — final image only contains the runtime stage
docker build -t myapp:1.0 .

# result: builder's gcc, build-essential, and pip cache never touch the
# final image — commonly a 5-10x size reduction vs a single-stage build
```

---

## .dockerignore

Prevents files from ever entering the build context — faster builds, smaller/safer images.

```
# .dockerignore
.git
.gitignore
.venv
venv/
__pycache__/
*.pyc
*.pyo
*.pyd
.env
.env.*
*.log
.DS_Store
.pytest_cache/
.mypy_cache/
tests/
docs/
README.md
Dockerfile
.dockerignore
.github/
node_modules/
```

### Senior Tip

```
Anything matching .gitignore is usually a good STARTING point for
.dockerignore, but they solve different problems:
   .gitignore   → keep noise out of version control
   .dockerignore → keep noise out of the BUILD CONTEXT sent to the daemon

A missing .dockerignore is a classic slow-build bug: `docker build .`
silently tars up node_modules/ or .git/ (which can be hundreds of MB)
and ships it to the daemon before the build even starts.
```

---

## Interview Angle

**Q: `docker run myimage /bin/sh` does nothing you expect — why?**
Almost certainly the image uses `ENTRYPOINT` alone (not `ENTRYPOINT` + `CMD`). Any argument after the image name gets appended to the entrypoint, not substituted for it — so you likely ran `python app.py /bin/sh` instead of getting a shell. Fix: `docker run --entrypoint /bin/sh myimage`.

**Q: Why does moving `COPY . .` below `RUN pip install -r requirements.txt` actually matter?**
Docker's layer cache invalidates a layer, and every layer after it, the instant that instruction's input changes. Application code changes on every commit; `requirements.txt` changes rarely. Copying `requirements.txt` and installing first means the expensive `pip install` layer stays cached across most rebuilds — only the final `COPY . .` layer (cheap) rebuilds.

**Q: Where do build secrets go if not ARG or ENV?**
BuildKit `--mount=type=secret`. ARG and ENV both persist into `docker history`/`docker inspect` or the final image layers — anyone with pull access can extract them. Secret mounts are only available to the specific `RUN` step that requests them and are never written to a layer.

**Q: Every rebuild re-downloads all of pip's dependencies from scratch, even when only one package changed. How do you fix that without baking pip's cache into the final image?**
A BuildKit cache mount: `RUN --mount=type=cache,target=/root/.cache/pip pip install -r requirements.txt`. This persists pip's download cache ACROSS builds independent of Docker's ordinary layer cache — even when `requirements.txt` changes and invalidates the layer, only the changed/new packages actually re-download, and the cache itself never becomes part of any image layer, so the final image stays exactly as small as before.

**Q: You need one image tag that works on both Intel/AMD cloud instances and ARM-based Graviton instances. How?**
`docker buildx build --platform linux/amd64,linux/arm64 -t myrepo/myapp:1.0 --push .` — this produces a single tag backed by a multi-architecture manifest list; a host pulling that tag automatically gets the layer set matching its own architecture, with no separate `:amd64`/`:arm64` tags for consumers to manage.

---

## Related

- [`../14_Security/02_owasp_container_k8s_security.md`](../14_Security/02_owasp_container_k8s_security.md) — distroless base images as the next step past multi-stage builds for the smallest, most attack-resistant final image
- [`01_docker_basics.md`](01_docker_basics.md) — the layer/cache mechanics this file's instruction choices are built on
- [`../07_Cloud_AWS/01_iam_compute_ec2.md`](../07_Cloud_AWS/01_iam_compute_ec2.md) — why Graviton (ARM) instances are worth the multi-platform build effort in the first place
