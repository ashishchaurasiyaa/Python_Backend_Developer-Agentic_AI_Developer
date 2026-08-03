# Security — Hands-On Lab
**DevOps Track · Phase 14 Practical**

## Prerequisites

- A Linux host you can SSH into and are willing to reconfigure — options, cheapest first: a local VM via **Multipass** (`multipass launch`, free, fastest) or **Vagrant**; a Docker container with `sshd` running (works for the SSH labs, not ideal for the systemd/service-restart parts); or an AWS EC2 `t3.micro` free-tier instance if you want a "real" cloud target
- **Do this on a throwaway VM, never a box you actually depend on** — Lab 1 deliberately practices changes that CAN lock you out if done wrong; that's the point of practicing the safe ordering somewhere low-stakes first
- `openssl` (built into macOS/Linux) for the TLS labs — no real domain needed, self-signed certs are fine for local practice
- Docker, for the Trivy image-scanning lab (`brew install trivy` or run it via `docker run aquasec/trivy`)
- Optional: an AWS account (free tier) for the IAM least-privilege exercise — the exercise also works as a pure JSON-authoring exercise without actually applying it, if you'd rather not touch a real account

---

## Lab 1: Harden SSH — The Correct, Non-Lockout Order

**Objective:** Apply the exact hardening sequence from the lesson file, on a real host, in the order that prevents locking yourself out — and prove to yourself why the order matters by understanding what would go wrong in the wrong order.

**Task:**
1. Spin up a throwaway VM (Multipass: `multipass launch --name ssh-lab`) and get a working password/default-key SSH session to it.
2. Generate a dedicated key pair for this lab: `ssh-keygen -t ed25519 -C "lab-key" -f ~/.ssh/ssh_lab_key`.
3. Push the public key to the VM's `authorized_keys` with `ssh-copy-id`.
4. **Open a second terminal and confirm key-based login works, while keeping your FIRST session open.** Do not proceed until this step succeeds.
5. Only now, edit `/etc/ssh/sshd_config`: set `PasswordAuthentication no`, `PubkeyAuthentication yes`, `PermitEmptyPasswords no`.
6. Run `sudo sshd -t` (syntax check) before restarting anything.
7. `sudo systemctl restart sshd`, then — using your STILL-OPEN first session, or a fresh third terminal — confirm key login still works and password login is now rejected.
8. Only after confirming step 7, add `PermitRootLogin no` and `MaxAuthTries 3`, restart again, re-verify.
9. Install and configure `fail2ban` watching `sshd`, with `maxretry=5`, `bantime=3600`. Deliberately fail a login 5 times from a throwaway session (wrong key/password) and confirm your IP gets banned (`fail2ban-client status sshd`), then unban yourself (`fail2ban-client set sshd unbanip <ip>`).

<details>
<summary>Solution / walkthrough</summary>

```bash
multipass launch --name ssh-lab
multipass shell ssh-lab   # first session — get the VM's IP with `multipass info ssh-lab`

# From your host machine:
ssh-keygen -t ed25519 -C "lab-key" -f ~/.ssh/ssh_lab_key
ssh-copy-id -i ~/.ssh/ssh_lab_key.pub ubuntu@<vm-ip>

# Second terminal — verify BEFORE touching sshd_config
ssh -i ~/.ssh/ssh_lab_key ubuntu@<vm-ip> "echo key login works"
```

```ini
# /etc/ssh/sshd_config — first pass, password auth only
PasswordAuthentication no
PubkeyAuthentication yes
PermitEmptyPasswords no
```
```bash
sudo sshd -t                       # syntax check FIRST, every time
sudo systemctl restart sshd

# From a NEW terminal (leave any existing session open as a safety net)
ssh -i ~/.ssh/ssh_lab_key ubuntu@<vm-ip>            # should work
ssh -o PreferredAuthentications=password ubuntu@<vm-ip>   # should be REJECTED now
```

```ini
# Second pass, only after step above is confirmed working
PermitRootLogin no
MaxAuthTries 3
LoginGraceTime 20
ChallengeResponseAuthentication no
KbdInteractiveAuthentication no
X11Forwarding no
ClientAliveInterval 300
ClientAliveCountMax 2
```
```bash
sudo sshd -t && sudo systemctl restart sshd
ssh -i ~/.ssh/ssh_lab_key ubuntu@<vm-ip>   # re-verify AGAIN
```

```bash
sudo apt install fail2ban
```
```ini
# /etc/fail2ban/jail.local
[sshd]
enabled = true
port = 22
filter = sshd
logpath = /var/log/auth.log
maxretry = 5
bantime = 3600
findtime = 600
```
```bash
sudo systemctl restart fail2ban

# From a third session, deliberately fail 5 logins
for i in $(seq 5); do ssh -o PreferredAuthentications=password -o PubkeyAuthentication=no ubuntu@<vm-ip>; done

sudo fail2ban-client status sshd
# Currently banned: 1, Banned IP list: <your IP>

sudo fail2ban-client set sshd unbanip <your-ip>
```

**Why the order matters, concretely**: if you'd set `PasswordAuthentication no` BEFORE confirming key login works (step 4), and your key push had silently failed (wrong path, wrong permissions on `~/.ssh` — a very common real mistake), you'd have just cut off the only remaining way into the box, with no password fallback and no key that actually works. The "keep a second session open" rule exists because a broken `sshd_config` reload doesn't kill your CURRENT session (SSH daemons apply new config to NEW connections, existing sessions stay alive) — so your first session becomes your escape hatch to fix a mistake, but only if you never closed it before verifying.
</details>

---

## Lab 2: TLS Hardening — Self-Signed Cert, Modern Ciphers, Verify with Tooling

**Objective:** Configure and then independently VERIFY a hardened TLS setup, rather than trusting that a config "looks right."

**Task:**
1. Generate a self-signed cert for a fake internal hostname: `openssl req -x509 -newkey rsa:4096 -keyout key.pem -out cert.pem -days 365 -nodes -subj "/CN=internal.lab"`.
2. Configure nginx (reuse your Web Servers lab setup, or a fresh minimal `server{}` block) with this cert, `ssl_protocols TLSv1.2 TLSv1.3` only, and a restrictive `ssl_ciphers` list.
3. Add `Strict-Transport-Security` and confirm it's present in the response headers.
4. Verify with `openssl s_client -connect localhost:443 -showcerts` — read the output and identify the negotiated protocol and cipher.
5. Verify with `nmap --script ssl-enum-ciphers -p 443 localhost` — confirm no weak/legacy ciphers are offered.
6. Deliberately WEAKEN the config (`ssl_protocols TLSv1 TLSv1.1 TLSv1.2 TLSv1.3;`, remove the cipher restriction) and re-run the nmap scan — confirm it now reports the weak protocols as available, so you've SEEN the tool actually catch a real misconfiguration, not just read about what it would catch.
7. Revert to the hardened config.

<details>
<summary>Solution / walkthrough</summary>

```bash
openssl req -x509 -newkey rsa:4096 -keyout /tmp/lab-key.pem -out /tmp/lab-cert.pem \
  -days 365 -nodes -subj "/CN=internal.lab"
```

```nginx
server {
    listen 443 ssl;
    server_name internal.lab;

    ssl_certificate     /tmp/lab-cert.pem;
    ssl_certificate_key /tmp/lab-key.pem;
    ssl_protocols       TLSv1.2 TLSv1.3;
    ssl_ciphers         HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;

    add_header Strict-Transport-Security "max-age=63072000" always;

    location / {
        return 200 "hardened TLS ok\n";
    }
}
```

```bash
sudo nginx -t && sudo nginx -s reload

curl -Ik https://localhost/ 2>&1 | grep -i strict-transport
# strict-transport-security: max-age=63072000

openssl s_client -connect localhost:443 -showcerts </dev/null 2>/dev/null | grep -i "Protocol\|Cipher"
# Protocol  : TLSv1.3
# Cipher    : TLS_AES_256_GCM_SHA384

nmap --script ssl-enum-ciphers -p 443 localhost
# TLSv1.2, TLSv1.3 only listed, cipher strength: A
```

**Deliberately weakened config (for comparison only — revert immediately after):**
```nginx
ssl_protocols TLSv1 TLSv1.1 TLSv1.2 TLSv1.3;
# ssl_ciphers line removed entirely — nginx falls back to a much broader default set
```
```bash
sudo nginx -s reload
nmap --script ssl-enum-ciphers -p 443 localhost
# now reports TLSv1.0 and TLSv1.1 as offered — both deprecated (POODLE/BEAST-era
# weaknesses), and typically flags weaker cipher suites in the output
```

**Why you ran nmap instead of trusting the config file**: a config that LOOKS restrictive can still have a mistake (wrong directive order, an included snippet overriding it elsewhere, a typo nginx silently ignores) — actually connecting and observing what protocols/ciphers are negotiated is the only way to know what's REALLY being served, which is exactly why the lesson file lists `nmap --script ssl-enum-ciphers` as the verification tool, not just "write the config and move on."
</details>

---

## Lab 3: Trivy Scan-and-Fix Loop + IAM Least Privilege

**Objective:** Practice the two "boring but this is what actually prevents real breaches" disciplines from the lesson file: iteratively fixing scan findings until an image is clean, and writing a least-privilege IAM policy instead of a wildcard.

**Task (Part A — image hardening):**
1. Write a deliberately bad `Dockerfile`: `FROM ubuntu:20.04`, installs Python via `apt`, runs as root (no `USER` directive), copies in a `requirements.txt` with at least one intentionally old/vulnerable package (e.g. an old `requests` or `pyyaml` version known to have a patched CVE).
2. Build it and scan with `trivy image --severity HIGH,CRITICAL yourimage:v1`. Note the finding count.
3. Fix iteratively: switch to `python:3.12-slim`, add a non-root `USER`, bump the vulnerable package version, rebuild, rescan.
4. Repeat until `trivy image --severity HIGH,CRITICAL --exit-code 1 yourimage:vN` exits 0 (no HIGH/CRITICAL findings) — confirm with `echo $?`.
5. Run `trivy config .` against your Dockerfile itself (not just the built image) and see if it flags the root-user issue at the Dockerfile-authoring stage, before you even build.

**Task (Part B — IAM least privilege):**
6. Write a "BAD" IAM policy granting `s3:*` on `Resource: "*"` (the "just make it work" shortcut from the lesson file).
7. Rewrite it as a "GOOD" policy scoped to only `s3:GetObject`/`s3:PutObject` on one specific bucket ARN.
8. If you have an AWS account: create both as actual IAM policies (don't attach the bad one to anything real), and use `aws iam simulate-principal-policy` (or just read them side by side) to articulate, in writing, exactly what blast radius the bad policy has that the good one doesn't.

<details>
<summary>Solution / walkthrough</summary>

**Part A:**
```dockerfile
# Dockerfile — deliberately bad, v1
FROM ubuntu:20.04
RUN apt-get update && apt-get install -y python3 python3-pip
COPY requirements.txt .
RUN pip3 install -r requirements.txt
COPY . /app
CMD ["python3", "/app/main.py"]
```
```
# requirements.txt — deliberately old/vulnerable
pyyaml==5.3.1
requests==2.20.0
```
```bash
docker build -t lab-app:v1 .
trivy image --severity HIGH,CRITICAL lab-app:v1
# Total: N (HIGH: x, CRITICAL: y) — likely both OS-package CVEs from ubuntu:20.04's
# age AND Python dependency CVEs from the pinned old versions
```

```dockerfile
# Dockerfile — fixed, v2
FROM python:3.12-slim AS builder
WORKDIR /app
COPY requirements.txt .
RUN pip install --target=/app/deps -r requirements.txt

FROM python:3.12-slim
RUN groupadd -r app && useradd -r -g app app
WORKDIR /app
COPY --from=builder /app/deps /app/deps
COPY --chown=app:app . /app
ENV PYTHONPATH=/app/deps
USER app
CMD ["python", "/app/main.py"]
```
```
# requirements.txt — bumped to patched versions
pyyaml==6.0.1
requests==2.31.0
```
```bash
docker build -t lab-app:v2 .
trivy image --severity HIGH,CRITICAL --exit-code 1 lab-app:v2
echo $?
# 0 — clean
```

```bash
trivy config .
# scans the Dockerfile itself for misconfigurations — a non-root USER missing
# in v1 would be flagged here even before a build/scan cycle
```

**What actually fixed most of the findings**: switching the BASE image (`ubuntu:20.04` → `python:3.12-slim`) typically eliminates far more CVEs than bumping the two Python packages did — an older general-purpose OS base image carries years of accumulated (eventually patched-upstream, but still-present-in-that-snapshot) OS package CVEs that a purpose-built, regularly-rebuilt slim image doesn't. This is worth noticing directly: base image choice usually matters more than dependency pinning for CVE count, though both matter.

**Part B:**
```json
// BAD — s3-wildcard.json
{
  "Version": "2012-10-17",
  "Statement": [
    { "Effect": "Allow", "Action": "s3:*", "Resource": "*" }
  ]
}
```
```json
// GOOD — s3-scoped.json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": ["s3:GetObject", "s3:PutObject"],
      "Resource": "arn:aws:s3:::my-app-uploads/*"
    }
  ]
}
```

**Blast radius comparison, written out**: the BAD policy grants every S3 action (`CreateBucket`, `DeleteBucket`, `PutBucketPolicy`, `PutBucketAcl`, `DeleteObject`, and everything else in the S3 API) against EVERY bucket in the account — a workload that only needed to read/write files in one uploads bucket can, if compromised, delete arbitrary buckets, exfiltrate data from unrelated buckets, or rewrite bucket policies to grant itself further access. The GOOD policy limits a compromise of this exact credential to read/write on one specific bucket's objects — it cannot delete the bucket, touch any other bucket, or modify permissions at all. This is the concrete meaning behind "least privilege" beyond the phrase itself: enumerate the blast radius difference, don't just cite the principle.

```bash
# If you have a real AWS account, sanity check the good policy's actual grant:
aws iam simulate-principal-policy \
  --policy-source-arn arn:aws:iam::123456789012:role/app-role \
  --action-names s3:DeleteBucket s3:GetObject \
  --resource-arns arn:aws:s3:::my-app-uploads/somefile.txt
# s3:GetObject -> allowed, s3:DeleteBucket -> implicitDeny (not granted at all)
```
</details>

---

## Lab 4: Troubleshooting — SSH Audit Checklist Against Your Own Server

**Objective:** Run your Lab 1 hardened server through a structured audit checklist, the way an actual security review would, and find (or confirm the absence of) real gaps.

**Task:**
1. Using the server from Lab 1, go through this checklist item by item, and for each, actually run the command that verifies it (not just assert it from memory):
   - [ ] Password authentication is disabled (`sshd -T | grep passwordauthentication`)
   - [ ] Root login is disabled (`sshd -T | grep permitrootlogin`)
   - [ ] Only modern KexAlgorithms/Ciphers/MACs are configured (`sshd -T | grep -E "kexalgorithms|ciphers|macs"`)
   - [ ] `MaxAuthTries` is set to a low number (`sshd -T | grep maxauthtries`)
   - [ ] fail2ban is active and its `sshd` jail is enabled (`fail2ban-client status sshd`)
   - [ ] No empty passwords permitted (`sshd -T | grep permitemptypasswords`)
   - [ ] Idle sessions time out (`sshd -T | grep clientalive`)
2. For any item that FAILS the check, fix it using the safe-ordering discipline from Lab 1 (verify a working session before restarting sshd).
3. Bonus: install and run `ssh-audit` (a real open-source tool, `pip install ssh-audit` or `brew install ssh-audit`) against your server (`ssh-audit <vm-ip>`) and compare its findings against your manual checklist — note anything it caught that your manual list missed (it typically checks key exchange/cipher strength in more depth than a manual grep would).

<details>
<summary>Solution / walkthrough</summary>

```bash
# Run each check against the live, effective config (sshd -T dumps the FULLY
# resolved config, catching cases where a value is set in an included file
# you forgot about — more reliable than grepping sshd_config directly)

sudo sshd -T | grep -i passwordauthentication
# passwordauthentication no                    <- PASS

sudo sshd -T | grep -i permitrootlogin
# permitrootlogin no                           <- PASS

sudo sshd -T | grep -iE "kexalgorithms|ciphers|macs"
# kexalgorithms curve25519-sha256,...
# ciphers chacha20-poly1305@openssh.com,...
# macs hmac-sha2-512-etm@openssh.com,...        <- PASS, all modern algorithms

sudo sshd -T | grep -i maxauthtries
# maxauthtries 3                                <- PASS

sudo fail2ban-client status sshd
# Status for the jail: sshd
# |- Currently failed: 0
# |- Total failed:     5
# `- Currently banned: 0                        <- PASS, jail is active

sudo sshd -T | grep -i permitemptypasswords
# permitemptypasswords no                       <- PASS

sudo sshd -T | grep -i clientalive
# clientaliveinterval 300
# clientalivecountmax 2                         <- PASS
```

```bash
pip install ssh-audit
ssh-audit <vm-ip>
```
Typical `ssh-audit` output flags things a quick manual grep might miss: specific weak key-exchange algorithms still technically enabled even if your intended list looks fine (ordering/fallback behavior), server host key type/size recommendations, and CVE cross-references for the specific OpenSSH version running. This is the practical value of a purpose-built audit tool over a manual checklist — it encodes far more accumulated security knowledge (known-weak algorithm lists, version-specific CVEs) than a hand-written grep list realistically can, and it's exactly the kind of tool a real security review would run before signing off on a hardened box.

**If any check fails**: fix it the SAME way as Lab 1 — edit `sshd_config`, `sudo sshd -t` to check syntax, keep an existing session open, `sudo systemctl restart sshd`, verify from a NEW session before closing the old one. This checklist isn't a one-time audit either — re-running it after any `sshd_config` change (including ones made for unrelated reasons months later) is exactly the discipline that catches configuration drift before it becomes an incident.
</details>

---

## Self-Check Checklist

- [ ] Can you recite the correct SSH-hardening ORDER (key first, verify, THEN disable password auth, THEN change port/root login) and explain why the order specifically prevents lockout?
- [ ] Can you explain why changing the SSH port is "defense-in-depth, not real security," in your own words?
- [ ] Can you configure fail2ban's `maxretry`/`bantime`/`findtime` and explain what each controls?
- [ ] Can you generate a self-signed cert with `openssl req -x509` and explain when a self-signed cert is (and isn't) acceptable?
- [ ] Can you explain the chain of trust (root CA → intermediate → leaf) and what breaks that chain in a browser's eyes?
- [ ] Can you verify a live TLS config's actual negotiated protocol/cipher with `openssl s_client` or `nmap --script ssl-enum-ciphers`, rather than trusting the config file alone?
- [ ] Can you explain why TLS 1.3 is preferred at scale (fewer round trips, mandatory forward secrecy, no legacy cipher fallback)?
- [ ] Can you write a least-privilege IAM policy from a wildcard one, and articulate the concrete blast-radius difference?
- [ ] Can you run Trivy against both a built image and a raw Dockerfile, and explain why base-image choice usually matters more than dependency version bumps for total CVE count?
- [ ] Can you explain where a database password should live in production (never `.env`/config map — a secrets manager, fetched at runtime via IAM role) and why?
