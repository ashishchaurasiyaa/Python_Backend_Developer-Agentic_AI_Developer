# Lab 4 — Secrets Manager: AWSCURRENT vs AWSPREVIOUS

**Goal:** Prove, live, why a rotated secret doesn't just disappear — during
the rotation **window**, anything already connected (or reading the secret
a split-second before your app finishes rolling out) still needs the OLD
value to keep working. Secrets Manager keeps it tagged `AWSPREVIOUS`
specifically for this reason.

**Task:** Open `lab.py`. `get_secret()` always fetches `AWSCURRENT`
regardless of what `stage` you ask for — it silently ignores the argument.
Pass it through:
```python
resp = client_.get_secret_value(SecretId=secret_id, VersionStage=stage)
return resp["SecretString"]
```

**Verify:**
```bash
./verify.sh
```
Runs `lab.py` (creates a secret at `password-v1`, "rotates" it to
`password-v2`), then **independently** fetches both `AWSCURRENT` and
`AWSPREVIOUS` via the AWS CLI as ground truth. PASS requires
`get_secret(stage="AWSPREVIOUS")` actually returns `'password-v1'`, not the
current value.

**SOCH:**
- The unfilled stub's `get_secret(stage="AWSPREVIOUS")` call doesn't error —
  it just quietly returns the wrong (current) value. Why is that worse, in
  a real incident, than if it had raised an exception instead?
- A real rotation Lambda typically moves through THREE stages —
  `AWSPENDING` (new value, not yet trusted) → `AWSCURRENT` (promoted) →
  `AWSPREVIOUS` (demoted) — not just the two this lab exercises. What real
  problem does the `AWSPENDING` stage solve that jumping straight from "old
  current" to "new current" wouldn't?
