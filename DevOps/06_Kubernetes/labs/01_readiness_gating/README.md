# Lab 1 — Readiness gating & Service endpoint exclusion

**Goal:** Prove, live, that a failed **readiness** probe does something
different from a failed **liveness** probe. Liveness failures get a container
killed and restarted (already covered in `../../practical/01_kubernetes_lab.md`
Lab 4). Readiness failures are quieter and, in real production incidents,
more common: the Pod keeps running exactly as before, but Kubernetes silently
pulls it out of the Service's endpoint list so no new traffic reaches it —
until it reports Ready again.

**Task:** Open `manifest.yaml`. It deploys 3 replicas of a tiny busybox HTTP
server exposing `/index.html` and `/healthz.html`, behind a Service — but
with **no readinessProbe at all** right now (a Pod is considered Ready the
instant its container starts). Add a `readinessProbe`:
- `httpGet` on path `/healthz.html`, port `8080`
- `periodSeconds: 2`, `failureThreshold: 2`

**Verify:**
```bash
./verify.sh
```
The script applies your manifest, confirms 3/3 Service endpoints, deletes
`/healthz.html` on one Pod *without killing it*, and polls for up to 15s to
see whether the Service actually drops to 2 endpoints. It then restores the
file and confirms the Pod rejoins. If you never added the probe, this
correctly times out and FAILs with a message pointing at the TODO — it does
not just "look for a probe key in the YAML", it exercises the real behavior.

**SOCH:**
- The verifier also checks `restartCount == 0` throughout. Why would seeing a
  non-zero restart count here mean you'd actually configured a **liveness**
  probe instead of a readiness one, even if the YAML key said `readinessProbe`?
- `periodSeconds: 2, failureThreshold: 2` reacts in ~4-6s here so a lab
  doesn't take minutes. What's the real tradeoff of setting these that
  aggressively on a production Service — what happens on a brief GC pause or
  a slow disk read that makes one health check late?
