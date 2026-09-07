# Lab 3 — Restart policy semantics: retry N times, then genuinely stop

**Goal:** Prove, live, that `restart: on-failure:N` does exactly what it
says — retries up to N times, then **stops for good** — as distinct from
`restart: "no"` (0 retries, gives up instantly) and `restart: always`/
`unless-stopped` (retries forever, even for something permanently broken).
Picking the wrong one means either "one blip and it's dead" or "a broken
container loops forever, burning CPU and filling logs."

**Task:** Open `docker-compose.yml`. The `flaky` service always exits 1 and
currently has `restart: "no"`. Change it to `restart: on-failure:3`.

**Verify:**
```bash
./verify.sh
```
Brings the stack up and polls `RestartCount` for up to 20s, waiting for it
to hold steady for 4 consecutive seconds (proving it's actually settled, not
just caught mid-retry). PASS requires it settles at **exactly 3**, with the
container ending in `exited` status — not still looping.

**SOCH:**
- The restarts here happened almost instantly (Docker's backoff for a
  container that dies in milliseconds starts very small and doubles). For a
  container that takes 30 seconds to start up before crashing, would 3
  `on-failure` retries still "fail fast," or could that policy alone leave
  something down for minutes before giving up?
- `restart: on-failure:3` with `docker compose up -d` (detached) vs the same
  policy under Kubernetes' `restartPolicy: OnFailure` +
  `backoffLimit` (`../../06_Kubernetes/labs/05_jobs_cronjobs`) are solving
  the same underlying problem in two different orchestration layers. What's
  the actual difference between "Docker restarts a container" and
  "Kubernetes recreates a Pod" here — is it the same mechanism with
  different names, or genuinely different?
