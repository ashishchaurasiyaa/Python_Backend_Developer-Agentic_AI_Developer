# Lab 2 — ConfigMap volume hot-reload vs env-var staleness

**Goal:** Prove, live, the single most common "why didn't my config change
take effect" production incident: a ConfigMap value delivered as a **mounted
file** updates on its own while the Pod keeps running; the *same* value
delivered as an **env var** never updates without a restart — ever.

**Task:** Open `manifest.yaml`. `config-test` currently reads `MESSAGE` only
as env var `MESSAGE_ENV`. Add:
1. a `volumes:` entry named `config-vol`, type `configMap`, backed by
   `app-config`
2. a `volumeMounts:` entry on the container mounting `config-vol` at
   `/etc/config` (so `/etc/config/MESSAGE` appears)

**Verify:**
```bash
./verify.sh
```
It applies the manifest, checks both delivery paths read `v1`, patches the
ConfigMap to `v2` **without touching the Pod**, then polls up to 120s (the
real kubelet re-sync isn't instant — expect ~60-90s in practice, this is not
a bug in the script, it's the actual mechanism) for `/etc/config/MESSAGE` to
become `v2`, and asserts `MESSAGE_ENV` is *still* `v1` throughout, with
`restartCount` staying at 0 the whole time.

**SOCH:**
- The env var never updates — not "updates slowly", never, until the Pod
  restarts. Why is that not a bug, given the file-mount path clearly *can*
  propagate a change without a restart? What does that tell you about when
  env vars actually get evaluated?
- If a teammate says "I updated the ConfigMap, just wait a minute for it to
  pick up," under what exact condition (which of the two delivery methods)
  is that true, and under which is it simply wrong no matter how long they wait?
