# Lab 5 — Job completion guarantees & `backoffLimit`

**Goal:** Prove two things about Jobs that theory alone doesn't make visceral:
(1) `restartPolicy: OnFailure` retries the *same* Pod in place — its volumes
survive across retries, so a container can track its own attempt count; and
(2) an unset `backoffLimit` doesn't mean "sane default", it means "this will
keep retrying, with a growing delay between attempts, for minutes before
anyone notices it gave up."

**Task:** Open `manifest.yaml`. `job-succeeds` needs no changes — it retries
in place (same Pod, same `emptyDir`) until an attempt counter hits 3, then
exits 0. `job-fails` is deliberately, permanently broken (`exit 1` always)
and currently has **no `backoffLimit` set** (defaults to 6, with growing
retry delays — several minutes to actually give up). Add `backoffLimit: 1`
to its spec so it gives up fast (2 total attempts).

**Verify:**
```bash
./verify.sh
```
Polls `job-succeeds` for up to 75s for `.status.succeeded == 1`, and polls
`job-fails` for up to 40s for its `Failed` condition to become `True`. If you
left `backoffLimit` unset, the second poll correctly times out — that IS the
lesson, not a flaky test: the default really does take far longer than 40s
for a job this reliably broken.

**SOCH:**
- `job-succeeds` uses `restartPolicy: OnFailure` (retries the same Pod) while
  `job-fails` uses `restartPolicy: Never` (each attempt is a brand-new Pod).
  If `job-succeeds` needed 3 attempts but used `restartPolicy: Never`
  instead, would the attempt-counter-on-emptyDir trick above still work?
  Why or why not?
- A Job stuck retrying against the SLOW default backoff for a genuinely
  broken task (bad credentials, a typo'd image) looks, from `kubectl get
  jobs`, almost identical to one that's legitimately working through
  transient failures. What field(s) would you actually check to tell those
  two situations apart in a production incident?
