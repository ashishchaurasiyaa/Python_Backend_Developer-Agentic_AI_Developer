# Lab 1 — Build secrets: `ARG` leaks, `--mount=type=secret` doesn't

**Goal:** Prove, live, one of the most common real Docker security mistakes:
an `ARG` value is baked into the image's build **history** permanently —
anyone who ever gets a copy of the image can read it straight back out with
`docker history`, even if nothing at runtime ever touches it again.
BuildKit's `--mount=type=secret` fixes this: the secret exists as a file for
exactly one `RUN` step and is never written to any layer or recorded
anywhere.

**Task:** Open `Dockerfile`. It currently takes the secret via
`ARG SECRET_TOKEN`. Replace it with:
```dockerfile
RUN --mount=type=secret,id=token \
    echo "using token: $(cat /run/secrets/token)" && echo "build step complete"
```
(and delete the `ARG SECRET_TOKEN` line — it's no longer needed).

**Verify:**
```bash
./verify.sh
```
Builds the image supplying the SAME secret value **both** ways
(`--build-arg` and `--secret`) so the same command works whether or not
you've done the TODO — whichever mechanism the Dockerfile actually
references picks it up. PASS requires the secret string appears **nowhere**
in `docker history --no-trunc`, and nowhere in the raw exported image
tarball either (not just the human-readable history view).

**SOCH:**
- The unfilled stub's failure output shows the secret twice — once on the
  `ARG` line, once on the `RUN` line that references it. Why does the value
  show up on BOTH, even though only the `RUN` line actually "uses" it in
  the command?
- `--mount=type=secret` is scoped to a single `RUN` instruction — the file
  disappears once that step finishes. If you needed the same secret in
  TWO separate `RUN` steps, what would you have to do differently, and why
  can't you just rely on it "still being there" from the first step?
