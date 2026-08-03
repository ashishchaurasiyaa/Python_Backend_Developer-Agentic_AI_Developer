# Security — IAM, RBAC & Vulnerability Scanning

**DevOps Track · Phase 14: Security**

## Quick Concepts

- **IAM (Identity and Access Management)** = cloud-provider system for controlling who/what can do what to which resources
- **Least privilege** = grant only the permissions a principal actually needs, nothing more, revisited regularly
- **Long-lived access keys** = static IAM access key/secret pairs that don't expire — a standing liability if leaked
- **Role assumption (STS)** = temporary, auto-expiring credentials issued when a principal assumes an IAM role, instead of using permanent keys
- **RBAC (Role-Based Access Control)** = permission model built on Roles (sets of permissions) bound to Subjects (users/service accounts) — used by both cloud IAM and Kubernetes
- **Service account** = non-human identity used by an application/pod to authenticate to APIs
- **Vulnerability scanning** = automated detection of known CVEs in OS packages, language dependencies, and container images
- **SCA (Software Composition Analysis)** = the specific practice of scanning third-party/open-source dependencies for known vulnerabilities
- **SBOM (Software Bill of Materials)** = a machine-readable manifest of every component (OS package, library, transitive dependency, version) that went into building an artifact
- **SLSA (Supply-chain Levels for Software Artifacts)** = a maturity framework (Levels 1-4) for how tamper-resistant and verifiable your build process is
- **Provenance** = signed, verifiable metadata proving WHERE and HOW an artifact was built (which repo, which commit, which CI run) — not just what's inside it

---

## Why This Matters

```
Most real-world cloud breaches are not "someone found a zero-day."
They're:
   - An IAM user with permanent access keys, keys leaked via a public
     repo or a misconfigured CI log, keys never rotated.
   - A role with far broader permissions than the workload needs
     ("just give it AdministratorAccess, we'll fix it later" — never
     fixed later).
   - A Kubernetes ServiceAccount bound to cluster-admin because a
     Helm chart's default RBAC was never reviewed.
   - A container image built 8 months ago with a since-patched
     CRITICAL CVE, never rebuilt, still running in prod.

IAM/RBAC discipline and scanning are boring, unglamorous, and
are exactly what separates "we noticed and rotated in 10 minutes"
from "we found out from a Reddit post about our leaked data."
```

---

## IAM Best Practices

### Least Privilege in Practice

```json
// BAD — broad wildcard, common "just make it work" shortcut
{
  "Effect": "Allow",
  "Action": "s3:*",
  "Resource": "*"
}

// GOOD — scoped to exactly what the workload needs
{
  "Effect": "Allow",
  "Action": ["s3:GetObject", "s3:PutObject"],
  "Resource": "arn:aws:s3:::my-app-uploads/*"
}
```

```bash
# AWS IAM Access Analyzer — finds unused permissions granted to a role
aws accessanalyzer list-findings --analyzer-arn <arn>

# Generate a least-privilege policy from actual CloudTrail usage
aws accessanalyzer start-policy-generation \
    --policy-generation-details '{"principalArn":"arn:aws:iam::123:role/app-role"}'
```

### No Long-Lived Access Keys — Use Role Assumption

```
Long-lived keys (AKIA...) are the single most common leak vector:
committed to git, pasted into a Slack message, left in a Lambda
env var visible to anyone with function read access. They don't
expire on their own — a leak from 2 years ago is still valid today
unless someone remembered to rotate it.

Fix: never issue long-lived keys to humans or workloads that can
instead assume a role.
```

```bash
# Human: assume a role via SSO/temporary session instead of static keys
aws sts assume-role \
    --role-arn arn:aws:iam::123456789012:role/DeployRole \
    --role-session-name ashish-deploy
# Returns temp AccessKeyId/SecretAccessKey/SessionToken, expires in ~1hr

# Workload (EC2/ECS/Lambda): use an instance/task/execution role —
# the SDK auto-fetches temp creds from the instance metadata service,
# NO keys ever stored on disk or in env vars
aws ec2 run-instances --iam-instance-profile Name=app-role ...

# Kubernetes on EKS: IRSA (IAM Roles for Service Accounts) — pods get
# temp AWS creds via a service account annotation, not mounted keys
apiVersion: v1
kind: ServiceAccount
metadata:
  name: app-sa
  annotations:
    eks.amazonaws.com/role-arn: arn:aws:iam::123456789012:role/app-role
```

### If Long-Lived Keys Are Unavoidable

```bash
# Rotate on a schedule, enforce via policy
aws iam update-access-key --access-key-id AKIA... --status Inactive
aws iam create-access-key --user-name svc-legacy-app
aws iam delete-access-key --access-key-id AKIA_OLD...

# Alert on key age
aws iam generate-credential-report
aws iam get-credential-report --query 'Content' --output text | base64 -d
```

---

## RBAC — Kubernetes, Tied to Real Incidents

### The Model

```
Role / ClusterRole  = WHAT (a set of permissions — verbs on resources)
RoleBinding / ClusterRoleBinding = WHO gets it (bound to a user,
                                     group, or ServiceAccount)

Role       → namespace-scoped permissions
ClusterRole → cluster-wide permissions (or reusable across namespaces)
```

### Real Incident Scenario — Over-Privileged Service Account

```
Scenario: a monitoring agent DaemonSet is deployed with a Helm chart.
The chart's default ServiceAccount is bound to a ClusterRole with
get/list/watch on ALL resources cluster-wide, including Secrets —
because the chart author wanted it to "just work" everywhere without
per-cluster tuning.

Consequence: the monitoring pod runs on every node. If ONE pod on
ONE node is compromised via an unrelated app vulnerability, the
attacker can use that pod's mounted ServiceAccount token to call
the K8s API directly and read every Secret in every namespace —
DB passwords, API keys, TLS private keys — cluster-wide.

This is not hypothetical — "over-permissioned monitoring/logging
agent as the pivot point" is one of the most common real-world
K8s lateral-movement patterns.
```

```yaml
# BAD — matches the incident above
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: monitoring-agent
rules:
- apiGroups: ["*"]
  resources: ["*"]
  verbs: ["get", "list", "watch"]

# GOOD — scoped to exactly what a metrics agent needs
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: monitoring-agent
rules:
- apiGroups: [""]
  resources: ["pods", "nodes", "nodes/metrics"]
  verbs: ["get", "list", "watch"]
# explicitly no access to "secrets" at all
```

```bash
# Audit what a ServiceAccount can actually do
kubectl auth can-i --list --as=system:serviceaccount:monitoring:agent-sa

# Find every ClusterRoleBinding granting cluster-admin — audit these first
kubectl get clusterrolebindings -o json | \
  jq '.items[] | select(.roleRef.name=="cluster-admin") | .metadata.name'
```

---

## Vulnerability Scanning — Trivy / Grype for Dependencies

```bash
# Trivy — filesystem/dependency scan (not just container images)
trivy fs --scanners vuln .
trivy fs requirements.txt

# Grype — Anchore's scanner, good complementary second opinion
grype dir:.
grype myapp:latest

# Python-specific SCA
pip-audit                          # scans installed/declared deps against PyPI advisory DB
safety check -r requirements.txt   # similar, different DB source

# Node equivalent (for context — polyglot shops mix these)
npm audit
```

```
Why run two scanners (Trivy + Grype) in serious setups: different
vulnerability databases and update cadences mean each catches CVEs
the other sometimes misses or reports later. For a single-repo
side project, one is enough — for a production pipeline gating
releases, cross-checking is common practice.
```

---

## Image Scanning in a CI Pipeline

The pattern that matters most day-to-day: fail the build automatically
if a container image has a HIGH/CRITICAL vulnerability, before it's
pushed to a registry a cluster could pull from.

```yaml
# .github/workflows/build.yml
name: Build and Scan

on:
  push:
    branches: [main]

jobs:
  build-and-scan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Build image
        run: docker build -t myapp:${{ github.sha }} .

      - name: Scan image with Trivy
        uses: aquasecurity/trivy-action@master
        with:
          image-ref: myapp:${{ github.sha }}
          format: table
          severity: HIGH,CRITICAL
          exit-code: 1          # fails the job — blocks the merge/deploy
          ignore-unfixed: true  # skip CVEs with no available patch yet

      - name: Push image (only reached if scan passed)
        run: |
          docker tag myapp:${{ github.sha }} registry.example.com/myapp:${{ github.sha }}
          docker push registry.example.com/myapp:${{ github.sha }}
```

```bash
# Equivalent raw CLI form (what the action wraps, useful to know
# for debugging why a CI step failed)
trivy image --severity HIGH,CRITICAL --exit-code 1 --ignore-unfixed \
    myapp:${GITHUB_SHA}
echo "exit code: $?"     # non-zero = vulnerabilities found, build should stop here
```

### Practical Gate Policy

```
CRITICAL  → always block the build, no exceptions
HIGH      → block by default; allow a documented, time-boxed
            exception (e.g. via .trivyignore) with a ticket reference
MEDIUM/LOW → report, don't block — track in a dashboard, fix on a cadence

Never scan and ignore the output. A scan step that always passes
regardless of findings is worse than no scan — it creates false
confidence in the pipeline.
```

---

## Software Supply Chain Security — SBOM & Provenance

```
Vulnerability scanning (above) answers "does this image have a KNOWN
CVE right now?" SBOM + provenance answer a different question: "if a
NEW CVE drops tomorrow in some library, do we even know which of our
100 services are affected — without re-scanning everything?"

This distinction became a boardroom-level concern after incidents
like Log4Shell (2021) and the SolarWinds build-system compromise —
"scan the image" wasn't enough when the question was "which of our
1,000 deployed artifacts contain log4j-core 2.14, transitively,
three dependency levels deep?" Without a stored SBOM per build, that
question takes days of manual archaeology. With one, it's a grep.
```

### Generating an SBOM

```bash
# Syft (Anchore) — generates an SBOM from a container image, directory, or repo
syft myapp:latest -o cyclonedx-json=sbom.json
syft myapp:latest -o spdx-json=sbom.spdx.json

# Docker Scout (built into recent Docker Desktop/CLI) — also SBOM-capable
docker scout sbom myapp:latest

# Two competing SBOM formats you'll see in the wild — know both exist:
#   CycloneDX  → OWASP-maintained, security-tooling-first origin
#   SPDX       → Linux Foundation-maintained, license-compliance-first origin
# Neither is "more correct" — pick whichever your scanning/compliance
# tooling consumes; most modern tools (Trivy, Grype, Syft) speak both.
```

### Wiring It Into CI — Generate, Attach, Store

```yaml
# .github/workflows/build.yml (extending the scan job from above)
      - name: Generate SBOM
        uses: anchore/sbom-action@v0
        with:
          image: myapp:${{ github.sha }}
          format: cyclonedx-json
          output-file: sbom.json

      - name: Attach SBOM to the build
        uses: actions/upload-artifact@v4
        with:
          name: sbom-${{ github.sha }}
          path: sbom.json
```

```
Store the SBOM alongside (or attached to, via OCI artifact/registry
attestation) each image you push — so 6 months from now, when a new
CVE is announced for some obscure transitive dependency, the answer
to "are we affected, and where" is "query the stored SBOMs," not
"re-pull and re-scan every image we've ever shipped."
```

### SLSA — How Trustworthy Is the Build Itself

```
SLSA asks a different question than "what's IN the artifact" —
it asks "can we PROVE how this artifact was built, and can anyone
tamper with that process undetected?"

Level 1  → build process is scripted/automated (not a human's laptop)
Level 2  → build runs on a hosted/managed CI service, generates
           signed provenance (GitHub Actions + OIDC-based attestation
           already gets you most of the way here)
Level 3  → build platform is hardened against tampering FROM WITHIN
           a build itself (isolated, ephemeral, no cross-build state)
Level 4  → two-person review of all changes + hermetic, reproducible builds

Most teams targeting "senior/product-company good practice" in 2026
sit at Level 2 — automated CI + signed provenance — not Level 4,
which is reserved for extremely high-assurance software (OS kernels,
critical infra). Know where the bar realistically is for the roles
you're targeting.
```

```bash
# GitHub Actions can generate SLSA provenance natively for build artifacts
# (attests: built by this workflow, from this commit, at this time)
gh attestation verify myapp-image --owner my-org
```

**Interview framing:** SBOM tells you *what's inside* an artifact; SLSA/provenance tells you *whether you can trust how it got built*. A mature supply-chain security posture needs both — a perfectly-scanned image built by an untraceable, tamperable process is still a supply-chain risk, just a different one than a vulnerable dependency.

---

## Senior Tip

```
Run `kubectl get clusterrolebindings -o json | jq '.items[] |
select(.roleRef.name=="cluster-admin")'` on any cluster you inherit,
on day one. It is astonishing how often the answer includes a
monitoring/logging/CI ServiceAccount that has zero business having
cluster-admin. This single command has caught real over-privilege
in production clusters more often than any automated tool.
```

## Interview Angle

**Q: Why is a long-lived IAM access key worse than a role assumed via STS?**
A long-lived key is valid indefinitely until manually rotated or
revoked — if it leaks, the exposure window is unbounded. STS temporary
credentials expire automatically (typically 1 hour), so a leaked
credential has a small, bounded blast radius even if nobody notices
the leak immediately.

**Q: How would you audit whether a Kubernetes cluster has RBAC over-privilege?**
Enumerate all ClusterRoleBindings/RoleBindings bound to `cluster-admin`
or wildcard (`resources: ["*"], verbs: ["*"]`) ClusterRoles, cross-reference
which ServiceAccounts they're bound to, and confirm each one actually
needs that scope. `kubectl auth can-i --list --as=<sa>` per service
account is the direct way to see effective permissions.

**Q: Where in the CI/CD pipeline should image scanning happen, and why there?**
Right after the image build, before push to a registry a cluster
can pull from. Scanning post-deploy means a vulnerable image already
ran in production; scanning pre-build (source only) misses vulnerabilities
introduced by the base image or installed OS packages.

**Q: A CVE is announced today for a library. How do you find every production service that's affected, without re-scanning everything?**
Query the stored SBOMs generated at build time for every deployed artifact (CycloneDX/SPDX, generated via Syft and archived per image) — a direct search for the affected package/version across stored manifests, instead of re-pulling and re-scanning every image in the registry. This is the entire reason SBOM generation happens at build time rather than on-demand: the inventory has to already exist before the question gets asked.

---

## Related

- [01_ssh_ssl_tls_hardening.md](01_ssh_ssl_tls_hardening.md) — SSH, TLS, secrets management
- [02_owasp_container_k8s_security.md](02_owasp_container_k8s_security.md) — OWASP, Docker/K8s hardening
- [../10_CICD/](../10_CICD/) — pipeline fundamentals this scanning step plugs into
