# Security — Container & Image Scanning
**Security · Year 3-4 | Senior Backend + Agentic AI**

## Quick Concepts
- **Image scanning** = checking a container image's layers for known-vulnerable OS packages and language dependencies (CVEs)
- **Base image** = the starting `FROM` layer (e.g., `python:3.12-slim`) — most inherited vulnerabilities come from here, not your own code
- **Distroless** = base image with no shell, package manager, or OS utilities — drastically smaller attack surface
- **SBOM** (Software Bill of Materials) = generated per-image, same concept as `16_sast_dast_supply_chain.md`'s dependency SBOM, but covering OS-level packages too
- **Admission controller** = Kubernetes component that can **block** a pod from scheduling if its image fails a policy check
- Directly extends [16_sast_dast_supply_chain.md](16_sast_dast_supply_chain.md) — SCA scans your `requirements.txt`; image scanning covers the OS layer underneath it that SCA alone misses

---

## Why a container needs its own scan (beyond `pip audit`)

```
Your Dockerfile:
FROM python:3.12-slim         ← inherits Debian's OS packages (glibc, openssl, etc.)
RUN pip install -r requirements.txt   ← your app's Python deps

pip-level scanning (SCA) only checks requirements.txt.
It does NOT see vulnerabilities in the base OS layer above it —
a vulnerable openssl or glibc version ships silently inside every image
built from that base, even if your Python code is perfectly clean.
```

A 2023-2024-era real pattern: teams pass their SAST/SCA gates on application
code, then ship a container built from a 2-year-old base image with dozens of
unpatched OS-level CVEs — the scan never looked at that layer.

---

## Trivy — the standard open-source scanner

```bash
# pip install nothing — trivy is a standalone binary
brew install trivy   # or apt/docker pull aquasec/trivy

# Scan a built image for OS + language-dependency CVEs
trivy image myapp:latest

# Fail CI if any CRITICAL/HIGH severity found
trivy image --severity CRITICAL,HIGH --exit-code 1 myapp:latest

# Scan the Dockerfile itself for misconfigurations (not just the built image)
trivy config .
```

```yaml
# GitHub Actions — gate the build on scan results
- name: Build image
  run: docker build -t myapp:${{ github.sha }} .

- name: Scan image
  uses: aquasecurity/trivy-action@master
  with:
    image-ref: myapp:${{ github.sha }}
    severity: CRITICAL,HIGH
    exit-code: '1'      # fails the pipeline if vulnerabilities found
```

### Snyk (commercial alternative, common in enterprise pipelines)

```bash
snyk container test myapp:latest
snyk container monitor myapp:latest   # ongoing monitoring after deploy, alerts on newly-disclosed CVEs
```

Key difference from Trivy: Snyk continuously re-checks images **already
deployed** against newly published CVEs (a CVE disclosed after your last scan
still gets flagged), not just at build time.

---

## Reducing attack surface — base image choice

```dockerfile
# Common but larger attack surface — full Debian userland
FROM python:3.12

# Better — Debian slim, fewer packages
FROM python:3.12-slim

# Best for attack-surface reduction — no shell, no package manager,
# nothing to scan for OS-level CVEs beyond glibc itself
FROM gcr.io/distroless/python3-debian12
```

```dockerfile
# Multi-stage build — compile/install in a full image, ship only the
# runtime artifacts in a minimal final image (fewer scannable layers)
FROM python:3.12 AS builder
COPY requirements.txt .
RUN pip install --user -r requirements.txt

FROM gcr.io/distroless/python3-debian12
COPY --from=builder /root/.local /root/.local
COPY . /app
WORKDIR /app
ENTRYPOINT ["python", "main.py"]
```

**Tradeoff to mention in an interview:** distroless has no shell, so you
can't `docker exec` into a running container to debug — a real operational
cost traded for a much smaller scan surface. Teams often keep a `-debug`
variant image with a shell for troubleshooting, distinct from the prod image.

---

## Kubernetes admission control (blocking bad images at deploy time)

```yaml
# Example policy (OPA Gatekeeper / Kyverno pattern) — block images
# that haven't been scanned, or that fail a severity threshold
apiVersion: kyverno.io/v1
kind: ClusterPolicy
metadata:
  name: require-image-scan-passed
spec:
  validationFailureAction: Enforce
  rules:
    - name: check-image-labels
      match:
        resources:
          kinds: ["Pod"]
      validate:
        message: "Image must have a passing scan label"
        pattern:
          spec:
            containers:
              - image: "*"
                # in practice: verify via image signature/attestation (cosign),
                # not just a label — labels can be forged
```

This ties directly into [20_opa_abac_policy_as_code.md](20_opa_abac_policy_as_code.md)
— image-scan enforcement is one more policy-as-code rule enforced the same way.

---

## SBOM generation for containers

```bash
# Generate an SBOM for a container image (same SBOM concept as dependency
# scanning in 16_sast_dast_supply_chain.md, applied to the whole image)
trivy image --format cyclonedx --output sbom.json myapp:latest

# Or with syft (Anchore)
syft myapp:latest -o cyclonedx-json > sbom.json
```

---

## Interview Q&A

**Q: Your app's `requirements.txt` passed `pip audit` clean — is the
container secure?**
A: Not necessarily — that only checked the Python dependency layer. The base
OS image (Debian/Alpine packages, glibc, openssl) can carry its own unpatched
CVEs invisible to a Python-only SCA tool. Need a separate image scan (Trivy/Snyk).

**Q: Why use a distroless base image instead of `python:3.12-slim`?**
A: Smaller attack surface — no shell, package manager, or OS utilities means
fewer things to scan and fewer tools available to an attacker who gets code
execution inside the container. Tradeoff: harder to debug interactively.

**Q: How do you stop a vulnerable image from ever reaching production?**
A: Two gates — (1) CI pipeline scan (Trivy) with `exit-code 1` on
CRITICAL/HIGH, blocking the merge/build; (2) Kubernetes admission controller
(OPA/Kyverno) rejecting unscanned or failing images at deploy time, so even a
bypassed CI gate can't reach the cluster.

**Q: A CVE gets published for a package already running in production — how do you find out?**
A: Continuous monitoring (`snyk container monitor` or a scheduled re-scan of
deployed image tags), not just a one-time build-time scan — new CVEs are
disclosed daily against old, unchanged images.

---

Related: [16_sast_dast_supply_chain.md](16_sast_dast_supply_chain.md) (SBOM/SCA
concepts this extends to the OS layer), [20_opa_abac_policy_as_code.md](20_opa_abac_policy_as_code.md)
(admission-control enforcement), `04_DevOps/01_docker.md`.
