# Security — OWASP Top 10, Docker & Kubernetes Security

**DevOps Track · Phase 14: Security**

## Quick Concepts

- **OWASP Top 10** = industry-standard list of the most critical web application security risks, refreshed periodically by the Open Web Application Security Project
- **WAF (Web Application Firewall)** = sits in front of your app, inspects HTTP traffic, blocks known attack patterns before they reach your code
- **Reverse proxy** = nginx/Envoy/HAProxy sitting between the internet and your app — a natural place to enforce headers, rate limits, TLS
- **Distroless image** = container image with only your app + runtime deps, no shell, no package manager, no OS utilities — nothing for an attacker to pivot with
- **Trivy / `docker scan`** = tools that scan container images for known CVEs in OS packages and language dependencies
- **Pod Security Standards (PSS)** = Kubernetes-native policy levels (Privileged / Baseline / Restricted) replacing the deprecated PodSecurityPolicy
- **Admission controller** = intercepts API server requests before an object is created, to validate or mutate it — what enforces custom policy beyond PSS's fixed three levels (OPA Gatekeeper, Kyverno)
- **CSP (Content-Security-Policy)** = a header telling the browser which sources scripts/styles/etc are allowed to load from — the header that actually blunts a successful XSS injection, not just clickjacking/MIME-sniffing
- **NetworkPolicy** = Kubernetes resource that restricts which pods can talk to which — a firewall inside the cluster
- **Secrets encryption at rest** = etcd (K8s's backing store) encrypting Secret objects on disk, not just relying on RBAC to gate access

---

## Why This Matters

```
The app-level Security docs (Backend_Developer/03_Security/) teach
you to write code that resists SQL injection, XSS, CSRF.

This file teaches the layer OUTSIDE the code:
   - Is the reverse proxy/WAF catching attacks before they hit the app?
   - Is the container the app runs in itself a liability (running as
     root, full of unpatched OS packages)?
   - Can a compromised pod move laterally across your whole cluster,
     or is it contained?

A perfectly-coded app running as root in a container with a bloated
base image, on a cluster with no NetworkPolicies, is still one
container escape away from a full breach.
```

---

## OWASP Top 10 — DevOps-Relevant Notes

The list changes over releases (2017 → 2021), but the shape is stable.
Below: what it is, and what a DevOps engineer specifically controls
for each — not how to fix it in application code.

| # | Risk | DevOps-Relevant Mitigation |
|---|---|---|
| 1 | **Broken Access Control** | Enforce authz at the gateway/reverse-proxy layer too, not just in-app; audit IAM/RBAC policies (see 03_iam_vuln_scanning.md) |
| 2 | **Cryptographic Failures** | Enforce TLS 1.2+ only at the load balancer, terminate/re-encrypt correctly, rotate certs before expiry (see 01_ssh_ssl_tls_hardening.md) |
| 3 | **Injection** | WAF rules (ModSecurity/AWS WAF) as a second layer of defense catching SQLi/command-injection payloads in transit |
| 4 | **Insecure Design** | Threat-model infra topology itself — e.g. is the DB reachable from the public internet at the network layer, regardless of app auth? |
| 5 | **Security Misconfiguration** | The one most owned by DevOps — default creds, verbose error pages, open S3 buckets, permissive security groups. Config-as-code + scanning catches this |
| 6 | **Vulnerable & Outdated Components** | Image scanning (Trivy/Grype) in CI, dependency scanning, automated base-image rebuilds |
| 7 | **Identification & Auth Failures** | Rate-limit login endpoints at the reverse proxy; enforce MFA at the IdP/SSO layer |
| 8 | **Software & Data Integrity Failures** | Signed container images, verified CI/CD pipeline supply chain, no pulling `:latest` from untrusted registries |
| 9 | **Security Logging & Monitoring Failures** | Centralized log aggregation (see Phase 12), alerting on auth failures/anomalies — this is infra's job to build, not app's |
| 10 | **Server-Side Request Forgery (SSRF)** | Network segmentation/egress rules so even a successful SSRF can't reach internal metadata endpoints (e.g. AWS IMDS) or internal-only services |

### WAF / Reverse Proxy as a Mitigation Layer

```nginx
# nginx as a lightweight WAF — rate limiting + basic header hardening
limit_req_zone $binary_remote_addr zone=login:10m rate=5r/m;

server {
    location /api/login {
        limit_req zone=login burst=3 nodelay;
        proxy_pass http://backend;
    }

    # Security headers — defense-in-depth, catches what app forgot
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-Frame-Options "DENY" always;
    add_header Strict-Transport-Security "max-age=63072000" always;
    add_header Content-Security-Policy "default-src 'self'; script-src 'self' cdn.example.com; object-src 'none'" always;
}
```

```
Content-Security-Policy (CSP) is the header that actually stops a
successful XSS injection from doing damage, rather than just
preventing clickjacking/MIME-sniffing (what the other three headers
above cover). `default-src 'self'` tells the browser to only load
scripts/styles/images/etc from your own origin by default; even if an
attacker manages to inject a `<script src="evil.com/steal.js">` tag
into a page, the BROWSER itself refuses to execute or fetch it because
evil.com isn't in the allowed source list. This is why CSP is
considered a genuine last line of defense for XSS specifically,
distinct from the other headers which address different attack classes
entirely (clickjacking, MIME-type confusion, protocol downgrade).
```

```
Real-world pattern: even with perfect app-level input validation,
a WAF (Cloudflare, AWS WAF, ModSecurity) catches:
   - Known bad payloads before they hit your servers at all
   - Zero-day-class attacks via signature/anomaly detection
   - Volumetric abuse (credential stuffing, scraping) via rate limits

It's not a replacement for secure code — it's the layer that buys
you time when code has a bug you haven't found yet.
```

---

## Docker Security

### Don't Run as Root Inside Containers

By default, a container process runs as root (UID 0) unless told
otherwise. If an attacker breaks out of the app into the container
shell, root-in-container is one misconfiguration away from
root-on-host (e.g. via a mounted Docker socket or kernel exploit).

```dockerfile
# BAD — implicit root
FROM python:3.12-slim
COPY . /app
CMD ["python", "app.py"]

# GOOD — dedicated non-root user
FROM python:3.12-slim
RUN groupadd -r app && useradd -r -g app app
COPY --chown=app:app . /app
USER app
CMD ["python", "app.py"]
```

```bash
# Verify at runtime
docker exec mycontainer whoami        # should NOT print root
docker run --user 1000:1000 myimage   # force non-root at run time
```

### Minimal Base Images / Distroless

```dockerfile
# Bloated — full OS, shell, package manager = large attack surface
FROM ubuntu:22.04
RUN apt-get update && apt-get install -y python3 python3-pip
COPY . /app
CMD ["python3", "/app/main.py"]

# Better — slim variant, smaller surface
FROM python:3.12-slim
COPY . /app
CMD ["python", "/app/main.py"]

# Best for security — distroless, no shell, no package manager at all
# (multi-stage build: build with a full image, run with distroless)
FROM python:3.12 AS builder
COPY . /app
RUN pip install --target=/app/deps -r /app/requirements.txt

FROM gcr.io/distroless/python3-debian12
COPY --from=builder /app /app
ENV PYTHONPATH=/app/deps
CMD ["/app/main.py"]
```

```
Why distroless matters: even if an attacker achieves code execution
inside the container, there's no `sh`, no `bash`, no `curl`, no
package manager to pivot with. It doesn't stop the initial exploit,
but it collapses post-exploitation options dramatically.
```

### Scanning Images — Trivy / `docker scan`

```bash
# Trivy — most common open-source scanner
trivy image myapp:latest

# Fail on HIGH/CRITICAL only (what you'd wire into CI)
trivy image --severity HIGH,CRITICAL --exit-code 1 myapp:latest

# Scan a Dockerfile itself for misconfigurations (e.g. running as root)
trivy config .

# docker scan (Snyk-powered, built into Docker Desktop, being phased
# out in favor of `docker scout`)
docker scan myapp:latest
docker scout cves myapp:latest
```

---

## Kubernetes Security

### Pod Security Standards (PSS)

Replaces the deprecated PodSecurityPolicy. Three levels, enforced via
namespace labels:

```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: prod
  labels:
    pod-security.kubernetes.io/enforce: restricted
    pod-security.kubernetes.io/audit: restricted
    pod-security.kubernetes.io/warn: restricted
```

| Level | Meaning |
|---|---|
| **Privileged** | No restrictions — avoid in any real namespace |
| **Baseline** | Blocks known privilege escalations (no privileged containers, no host namespaces) |
| **Restricted** | Heavily locked down — no root, must drop all capabilities, no privilege escalation, seccomp required |

```yaml
# Pod spec matching "restricted" — the pattern to actually write
apiVersion: v1
kind: Pod
metadata:
  name: app
spec:
  securityContext:
    runAsNonRoot: true
    runAsUser: 1000
    seccompProfile:
      type: RuntimeDefault
  containers:
  - name: app
    image: myapp:latest
    securityContext:
      allowPrivilegeEscalation: false
      readOnlyRootFilesystem: true
      capabilities:
        drop: ["ALL"]
```

### Admission Controllers — Enforcing Policy Beyond PSS's Fixed Levels

Pod Security Standards give you exactly three levels (Privileged/Baseline/Restricted) — real orgs often need CUSTOM rules PSS doesn't express at all: "every image must come from our internal registry," "every Deployment must have resource limits set," "no `:latest` tag ever." **Admission controllers** are what enforce arbitrary policy like this, rejecting non-compliant objects at the API server before they're ever created.

```yaml
# OPA Gatekeeper — a ConstraintTemplate defines the POLICY LOGIC (Rego)
apiVersion: templates.gatekeeper.sh/v1
kind: ConstraintTemplate
metadata:
  name: requiredresourcelimits
spec:
  crd:
    spec:
      names:
        kind: RequiredResourceLimits
  targets:
    - target: admission.k8s.gatekeeper.sh
      rego: |
        package requiredresourcelimits
        violation[{"msg": msg}] {
          container := input.review.object.spec.containers[_]
          not container.resources.limits
          msg := sprintf("Container '%v' has no resource limits set", [container.name])
        }
---
# A Constraint applies that policy, scoped to specific namespaces
apiVersion: constraints.gatekeeper.sh/v1beta1
kind: RequiredResourceLimits
metadata:
  name: require-resource-limits-prod
spec:
  match:
    namespaces: ["prod"]
```

```yaml
# Kyverno — same idea, plain YAML instead of Rego (lower barrier to entry)
apiVersion: kyverno.io/v1
kind: ClusterPolicy
metadata:
  name: disallow-latest-tag
spec:
  validationFailureAction: Enforce
  rules:
    - name: no-latest-tag
      match:
        resources:
          kinds: ["Pod"]
      validate:
        message: "Images must use an explicit tag, not :latest"
        pattern:
          spec:
            containers:
              - image: "!*:latest"
```

```
OPA Gatekeeper vs Kyverno — the practical distinction: Gatekeeper's
policies are written in Rego (a real, if unusual, purpose-built
policy language — more expressive, steeper learning curve, and the
SAME Rego used by the Terraform/CI policy-as-code tools in Phase 8).
Kyverno's policies are plain Kubernetes-native YAML — faster to pick
up, covers the large majority of common real-world rules (required
labels, disallowed tags, mandatory resource limits) without needing
to learn a new language at all.

Both operate as VALIDATING (reject non-compliant objects outright) or
MUTATING (silently fix/inject defaults, e.g. auto-adding a missing
resource limit) admission webhooks — the same admission-control point
in the API server's request pipeline that Pod Security Standards
themselves are built on, just with arbitrary custom logic instead of
three fixed levels.
```

**Senior framing:** PSS is the right tool for "every pod must at least meet this baseline security bar" — built-in, zero extra components, but limited to its three fixed levels. Gatekeeper/Kyverno are the right tool the moment a policy is organization-specific rather than a general security baseline ("must pull from our registry," "must have a `team` label," "must not exceed 2 replicas in dev") — the same policy-as-code philosophy as Phase 8's tfsec/Checkov, just enforced live at the Kubernetes API server instead of at CI time against Terraform plans.

### NetworkPolicies — Defense-in-Depth Inside the Cluster

By default, every pod in a Kubernetes cluster can talk to every other
pod. A NetworkPolicy restricts that — so if one service is compromised,
it can't just walk laterally to the DB or an unrelated internal API.

```yaml
# Default-deny all ingress in a namespace, then explicitly allow
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: default-deny
  namespace: prod
spec:
  podSelector: {}
  policyTypes: ["Ingress"]

---
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-api-to-db
  namespace: prod
spec:
  podSelector:
    matchLabels:
      app: postgres
  ingress:
  - from:
    - podSelector:
        matchLabels:
          app: api-server
    ports:
    - port: 5432
```

```
Real incident this prevents: a compromised, low-privilege internal
"reporting" service pod pivots to the payments DB pod simply because
nothing stopped it at the network layer — the DB pod trusted anything
inside the cluster's pod network. NetworkPolicies make lateral
movement require an explicit rule, not just cluster membership.
```

### Secrets Encryption at Rest

Kubernetes Secrets are base64-encoded, NOT encrypted, by default —
anyone with etcd read access or `kubectl get secret -o yaml` access
can trivially decode them. Encryption at rest protects the etcd
disk/backup itself.

```yaml
# /etc/kubernetes/enc/encryption-config.yaml — passed to kube-apiserver
# via --encryption-provider-config
apiVersion: apiserver.config.k8s.io/v1
kind: EncryptionConfiguration
resources:
  - resources: ["secrets"]
    providers:
      - aescbc:
          keys:
            - name: key1
              secret: <base64-encoded-32-byte-key>
      - identity: {}   # fallback for reading unencrypted-at-rest existing secrets
```

```bash
# Verify secrets are actually stored encrypted (not just base64 in etcd)
ETCDCTL_API=3 etcdctl get /registry/secrets/prod/db-creds --print-value-only
# should show ciphertext (k8s:enc:aescbc:...), not readable base64 JSON
```

In managed clusters (EKS, GKE, AKS), this is usually available as a
one-flag setting (e.g. EKS envelope encryption via KMS) rather than
something you hand-roll.

---

## Senior Tip

```
"Baseline" or "Restricted" Pod Security Standards should be the
DEFAULT for every prod namespace, not an opt-in you add after an
incident. The same goes for NetworkPolicies — default-deny ingress,
then explicitly allow. Least-privilege-by-default at the cluster
level catches the mistakes that app-level review misses.
```

## Interview Angle

**Q: Why scan container images in CI instead of just at deploy time?**
Shift-left — catching a CRITICAL CVE in a PR build blocks it before
it ever reaches a registry or a running cluster. Scanning only at
deploy time (or not at all) means vulnerable images can sit in
production for the lifetime of the base image's unpatched CVE.

**Q: What's the actual risk of running a container as root?**
It's not root-in-container itself that's catastrophic — it's what
that enables if the container is compromised: writing to mounted
host volumes with root perms, exploiting a kernel vuln for container
escape, or abusing a mounted Docker socket to control the host
daemon directly.

**Q: Why do you need NetworkPolicies if Pods already have RBAC?**
RBAC controls who can call the Kubernetes API (create/delete/read
resources). NetworkPolicy controls actual network traffic between
running pods — a completely different plane. A pod with zero RBAC
permissions can still open a raw TCP connection to another pod
unless a NetworkPolicy blocks it.

**Q: You want to enforce "every Pod must specify resource limits" and "no image may use the :latest tag" cluster-wide — Pod Security Standards don't express either rule. What do you reach for?**
An admission controller — OPA Gatekeeper (policy written in Rego) or Kyverno (policy written in plain Kubernetes YAML) — rather than PSS, which is limited to its three fixed levels (Privileged/Baseline/Restricted) and can't express organization-specific rules like these. Both intercept the API server's admission chain and reject (or auto-fix, in mutating mode) non-compliant objects before they're ever created.

**Q: An attacker successfully injects a malicious `<script>` tag via an XSS vulnerability in the app. Which of the security headers shown actually stops it from doing damage?**
Content-Security-Policy. `X-Content-Type-Options`, `X-Frame-Options`, and `Strict-Transport-Security` each address a different attack class (MIME-sniffing, clickjacking, protocol downgrade) but don't restrict what an already-injected script can load or execute. CSP's `default-src`/`script-src` directives make the BROWSER itself refuse to fetch or execute anything from a source not on the allowed list — so even a successfully injected `<script src="evil.com/steal.js">` simply won't load.

---

## Related

- [01_ssh_ssl_tls_hardening.md](01_ssh_ssl_tls_hardening.md) — SSH, TLS, secrets management
- [03_iam_vuln_scanning.md](03_iam_vuln_scanning.md) — IAM, RBAC, vulnerability/image scanning in CI
- [../06_Kubernetes/](../06_Kubernetes/) — core Kubernetes concepts
- [../05_Docker/](../05_Docker/) — core Docker concepts
