# Lab 5 — BuildKit cache mounts: surviving a layer-cache bust

**Goal:** `../practical/01_docker_lab.md` Lab 1 already teaches
`COPY requirements.txt . && RUN pip install` — placing dependency
installation before app-code copy so code-only changes don't re-trigger
`pip install`. That trick does nothing the moment `requirements.txt` itself
changes (a real dependency bump) — the layer cache is correctly invalidated,
and pip re-downloads every package from PyPI from scratch. A
`--mount=type=cache` gives the `RUN` step a directory that persists across
**separate** `docker build` invocations (not baked into any image layer),
so pip's own download cache survives even when the layer has to re-run.

**Task:** Open `Dockerfile`. Add a cache mount to the pip install step:
```dockerfile
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install -r requirements.txt
```

**Verify:**
```bash
./verify.sh
```
Builds once (cold), then edits `requirements.txt` (adding a comment line —
busts the Docker layer cache, but the actual package stays
`requests==2.31.0`) and builds again with `--progress=plain` so pip's own
log is visible. PASS requires build 2's output says **"Using cached
requests..."**, not "Downloading requests..." — proof pip found the package
already sitting in the persistent cache mount instead of re-fetching it.

**SOCH:**
- A cache mount's contents are explicitly **not** part of any image layer —
  they don't bloat the final image and don't get pushed to a registry with
  it. What real problem would you have if `--mount=type=cache` behaved like
  a normal layer instead (i.e., if the pip cache DID end up baked into the
  image)?
- If two different Dockerfiles in two different projects both used
  `--mount=type=cache,target=/root/.cache/pip`, would they share the same
  cache or get separate ones? What would you need to add to control that
  explicitly? *(hint: the mount takes an `id=` option)*
