# Security — SAST, DAST & Supply Chain Security (Production Pipeline)
**Phase 3 Security | Senior Backend + Agentic AI**

## Quick Concepts
- **SAST** = Static Application Security Testing — scan source code without running it
- **DAST** = Dynamic Application Security Testing — scan running app (black-box)
- **IAST** = Interactive AST — instrumented runtime analysis (combines SAST + DAST)
- **SCA** = Software Composition Analysis — scan dependencies for known CVEs
- **Supply chain** = malicious deps, typosquatting, compromised packages
- **SBOM** = Software Bill of Materials — JSON/XML inventory of all dependencies
- **CVE** = Common Vulnerabilities and Exposures — public ID for security bugs
- **CVSS** = scoring system (0-10) — critical/high/medium/low

---

## The Modern Threat Landscape (2026)

```
Real incidents:
─────────────────
• 2024: PyTorch nightly compromised via dep confusion
• 2024: XZ Utils backdoor (CVE-2024-3094) — caught by accident
• 2023: 3CX supply chain attack — signed installer compromised
• 2023: PyPI malicious packages (typosquatting "requests" → "requestes")
• ongoing: Log4Shell (CVE-2021-44228) still exploited
```

**Defense-in-depth = SAST + DAST + SCA + secrets scanning + SBOM tracking.**

---

## Tool Stack Overview

| Layer | Open Source | Commercial |
|---|---|---|
| **SAST (Python)** | Bandit, Semgrep | Snyk Code, Checkmarx, SonarQube |
| **DAST** | OWASP ZAP, Nuclei | Burp Suite Pro, Acunetix |
| **SCA / Deps** | pip-audit, Safety, OSV-Scanner | Snyk Open Source, Dependabot, Renovate |
| **Container scan** | Trivy, Grype | Snyk Container, Prisma Cloud |
| **Secrets** | gitleaks, trufflehog, detect-secrets | GitGuardian |
| **IaC scan** | Checkov, tfsec, kics | Snyk IaC |
| **SBOM** | Syft, CycloneDX | — |

---

## Interview Questions & Answers

### Q1: Bandit (Python SAST) — basic setup + CI?

**Answer:** Bandit scans Python AST for common security issues.

```bash
pip install bandit[toml]

# Run scan
bandit -r app/                            # recursive
bandit -r app/ -ll                         # only low+
bandit -r app/ -iii                        # high severity, high confidence
bandit -r app/ -f json -o bandit.json     # JSON for CI
```

**Config file:**
```toml
# pyproject.toml
[tool.bandit]
exclude_dirs = ["tests", "migrations", ".venv"]
tests = []
skips = ["B101", "B601"]  # B101=assert (used in tests), B601=shell=True (false positives)

[tool.bandit.assert_used]
skips = ["*test*.py"]
```

**Common findings:**
| ID | Issue | Fix |
|---|---|---|
| B102 | `exec_used` | Avoid `exec()` |
| B201 | `flask_debug_true` | Disable in prod |
| B301 | `pickle` | Use JSON or `pickle` with HMAC |
| B303 | `md5` (weak) | Use SHA-256 |
| B501 | SSL verify disabled | Set `verify=True` |
| B608 | SQL string concat | Use parameterized queries |
| B701 | jinja2 autoescape off | Enable autoescape |

**CI integration:**
```yaml
# .github/workflows/security.yml
- name: Bandit SAST
  run: |
    pip install bandit[toml]
    bandit -r app/ -ll -ii -f json -o bandit-results.json

- name: Upload SARIF
  uses: github/codeql-action/upload-sarif@v3
  with:
    sarif_file: bandit-results.json
```

---

### Q2: Semgrep — beyond Bandit (cross-language, custom rules)?

**Answer:** Semgrep — pattern-based, supports custom rules in YAML.

```bash
pip install semgrep
# or: brew install semgrep

# Use OWASP/secure-defaults rule packs
semgrep --config=p/python --config=p/owasp-top-ten --config=p/security-audit app/

# JSON output for CI
semgrep --config=auto --json --output=semgrep.json app/
```

**Custom rule (find unsafe Django ORM use):**
```yaml
# .semgrep/django-raw-sql.yaml
rules:
  - id: django-raw-sql-injection
    pattern-either:
      - pattern: $MODEL.objects.raw($QUERY % ...)
      - pattern: $MODEL.objects.raw(f"...{$VAR}...")
      - pattern: cursor.execute(f"...{$VAR}...")
    message: |
      Potential SQL injection — use parameterized queries.
      Use: cursor.execute("SELECT ... WHERE id = %s", [user_id])
    languages: [python]
    severity: ERROR
    metadata:
      cwe: "CWE-89: SQL Injection"
      owasp: "A03:2021 - Injection"
```

```bash
semgrep --config .semgrep/ app/
```

**Custom rule for hardcoded secrets:**
```yaml
rules:
  - id: hardcoded-aws-key
    pattern-regex: "AKIA[0-9A-Z]{16}"
    message: AWS access key hardcoded
    severity: ERROR
    languages: [python, yaml, json]
```

**CI:**
```yaml
- name: Semgrep
  uses: returntocorp/semgrep-action@v1
  with:
    config: >-
      p/python
      p/owasp-top-ten
      p/secrets
      .semgrep/
```

---

### Q3: Dependency scanning (SCA) — pip-audit, Safety, OSV?

**Answer:** Scan installed packages against CVE databases.

```bash
# Option 1: pip-audit (PyPA official)
pip install pip-audit
pip-audit                                  # scan current env
pip-audit -r requirements.txt              # scan file
pip-audit --fix                             # auto-upgrade vulnerable packages
pip-audit --format json --output audit.json

# Option 2: Safety (free for OSS)
pip install safety
safety check --json

# Option 3: OSV-Scanner (Google, multi-ecosystem)
brew install osv-scanner
osv-scanner --lockfile poetry.lock
osv-scanner --lockfile package-lock.json   # also Node, Go, Rust, etc.
```

**Output (pip-audit):**
```
Found 2 known vulnerabilities in 2 packages
Name      Version  ID                  Fix Versions
--------  -------  ------------------  ------------
requests  2.28.0   GHSA-j8r2-6x86-q33q 2.31.0
urllib3   1.26.5   GHSA-5phf-pp7p-vc2r 1.26.18, 2.0.7
```

**CI gate:**
```yaml
- name: Dependency audit
  run: |
    pip install pip-audit
    pip-audit -r requirements.txt --strict
  # `--strict` returns non-zero on any vulnerability
```

---

### Q4: Dependabot / Renovate (automated PR updates)?

**Answer:** Bots that open PRs when deps have updates or CVEs.

**Dependabot config:**
```yaml
# .github/dependabot.yml
version: 2
updates:
  - package-ecosystem: "pip"
    directory: "/"
    schedule:
      interval: "weekly"
      day: "monday"
    open-pull-requests-limit: 10
    groups:
      production-deps:
        patterns: ["*"]
        exclude-patterns: ["pytest*", "ruff*", "mypy*"]
      dev-deps:
        patterns: ["pytest*", "ruff*", "mypy*"]
    versioning-strategy: "lockfile-only"  # don't loosen ranges
    labels: ["dependencies", "security"]
    reviewers: ["backend-team"]

  - package-ecosystem: "docker"
    directory: "/"
    schedule:
      interval: "weekly"

  - package-ecosystem: "github-actions"
    directory: "/"
    schedule:
      interval: "monthly"
```

**Renovate (more powerful, requires renovate-bot.com or self-host):**
```json
// renovate.json
{
  "extends": ["config:recommended", ":semanticCommits"],
  "schedule": ["before 9am on monday"],
  "packageRules": [
    {
      "matchUpdateTypes": ["patch", "minor"],
      "matchPackagePatterns": ["*"],
      "automerge": true
    },
    {
      "matchPackagePatterns": ["fastapi", "pydantic"],
      "groupName": "fastapi-stack"
    }
  ],
  "vulnerabilityAlerts": {
    "enabled": true,
    "labels": ["security"]
  }
}
```

---

### Q5: OWASP ZAP (DAST) — automated black-box scanning?

**Answer:** Run ZAP against deployed staging URL.

```bash
# Docker (easiest)
docker run -t ghcr.io/zaproxy/zaproxy:stable \
  zap-baseline.py \
  -t https://staging.acme.com \
  -r zap-report.html \
  -J zap-report.json
```

**Authenticated scan (with login):**
```bash
docker run -v $(pwd):/zap/wrk/:rw -t ghcr.io/zaproxy/zaproxy:stable \
  zap-full-scan.py \
  -t https://staging.acme.com \
  -z "-config replacer.full_list(0).description=auth1 \
      -config replacer.full_list(0).enabled=true \
      -config replacer.full_list(0).matchtype=REQ_HEADER \
      -config replacer.full_list(0).matchstr=Authorization \
      -config replacer.full_list(0).replacement=Bearer YOUR_TEST_TOKEN" \
  -r report.html
```

**ZAP API (Python control):**
```python
from zapv2 import ZAPv2

zap = ZAPv2(apikey="YOUR_KEY", proxies={"http": "http://localhost:8090"})

target = "https://staging.acme.com"

# Spider (crawl)
print("Spidering...")
scan_id = zap.spider.scan(target)
while int(zap.spider.status(scan_id)) < 100:
    print(f"Spider progress: {zap.spider.status(scan_id)}%")
    time.sleep(5)

# Active scan
print("Active scanning...")
scan_id = zap.ascan.scan(target)
while int(zap.ascan.status(scan_id)) < 100:
    print(f"Scan progress: {zap.ascan.status(scan_id)}%")
    time.sleep(10)

# Get alerts
alerts = zap.core.alerts(baseurl=target)
high_alerts = [a for a in alerts if a["risk"] == "High"]
if high_alerts:
    print(f"Found {len(high_alerts)} HIGH severity issues")
    sys.exit(1)
```

**CI workflow:**
```yaml
name: DAST Scan
on:
  schedule: [{cron: "0 2 * * *"}]  # nightly
  workflow_dispatch:

jobs:
  zap:
    runs-on: ubuntu-latest
    steps:
      - name: ZAP Full Scan
        uses: zaproxy/action-full-scan@v0.10.0
        with:
          target: 'https://staging.acme.com'
          rules_file_name: '.zap/rules.tsv'
          fail_action: true
```

---

### Q6: Container & IaC scanning (Trivy + Checkov)?

**Answer:** Scan Docker images + Terraform/K8s configs.

**Trivy (container + IaC + secrets):**
```bash
brew install trivy

# Scan container image
trivy image yourorg/app:latest

# Scan Dockerfile
trivy config Dockerfile

# Scan Kubernetes manifests
trivy config k8s/

# Scan filesystem (mixed)
trivy fs .

# CycloneDX SBOM generation
trivy image --format cyclonedx --output sbom.json yourorg/app:latest

# Severity filter
trivy image --severity HIGH,CRITICAL yourorg/app:latest --exit-code 1
```

**Checkov (IaC misconfigurations):**
```bash
pip install checkov

checkov -d . --framework terraform
checkov -d . --framework kubernetes
checkov -d . --framework dockerfile
checkov -d . --skip-check CKV_DOCKER_2  # skip specific check
```

**Catches:**
- S3 buckets without encryption
- Public RDS instances
- K8s containers running as root
- Missing resource limits
- Hardcoded secrets in IaC

**CI:**
```yaml
- name: Trivy scan
  uses: aquasecurity/trivy-action@master
  with:
    image-ref: 'yourorg/app:${{ github.sha }}'
    severity: 'CRITICAL,HIGH'
    exit-code: '1'
    format: 'sarif'
    output: 'trivy.sarif'

- name: Upload SARIF
  uses: github/codeql-action/upload-sarif@v3
  with:
    sarif_file: trivy.sarif
```

---

### Q7: Secret detection (gitleaks + pre-commit)?

**Answer:** Block commits with leaked API keys, tokens.

```bash
brew install gitleaks

# Scan repo
gitleaks detect --source=. --verbose

# Scan single commit
gitleaks detect --source=. --log-opts="--all -- HEAD~1..HEAD"
```

**Pre-commit hook (block locally):**
```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/gitleaks/gitleaks
    rev: v8.18.0
    hooks:
      - id: gitleaks
  - repo: https://github.com/Yelp/detect-secrets
    rev: v1.4.0
    hooks:
      - id: detect-secrets
        args: ['--baseline', '.secrets.baseline']
```

```bash
pip install pre-commit
pre-commit install
```

**Custom gitleaks rules:**
```toml
# .gitleaks.toml
[allowlist]
description = "global allowlist"
paths = ['''\.lock$''', '''__pycache__''']

[[rules]]
id = "company-api-key"
description = "Our internal API key format"
regex = '''ACME_[A-Z0-9]{32}'''
tags = ["api-key"]
severity = "HIGH"

[[rules.allowlists]]
regexes = ['''ACME_EXAMPLE_KEY_FOR_DOCS''']
```

**GitHub secret scanning** (enable in repo settings):
- Free for public repos
- $0.42/active committer/month for private
- Catches 100+ provider keys (AWS, Stripe, Slack, etc.)

---

### Q8: SBOM generation + supply chain provenance (SLSA)?

**Answer:** Generate, sign, and publish SBOM with builds.

**Generate SBOM with Syft:**
```bash
brew install syft
syft yourorg/app:latest -o cyclonedx-json > sbom.cdx.json
syft yourorg/app:latest -o spdx-json > sbom.spdx.json
```

**Sample SBOM (CycloneDX):**
```json
{
  "bomFormat": "CycloneDX",
  "specVersion": "1.5",
  "components": [
    {
      "type": "library",
      "name": "fastapi",
      "version": "0.110.0",
      "purl": "pkg:pypi/fastapi@0.110.0",
      "licenses": [{"license": {"id": "MIT"}}]
    }
  ],
  "vulnerabilities": [
    {
      "id": "CVE-2024-XXXXX",
      "affects": [{"ref": "fastapi@0.110.0"}]
    }
  ]
}
```

**Sign with cosign (sigstore):**
```bash
# Sign container
cosign sign --key cosign.key yourorg/app:latest

# Attach SBOM as attestation
cosign attest --predicate sbom.cdx.json \
  --type cyclonedx \
  --key cosign.key \
  yourorg/app:latest

# Verify on consumer side
cosign verify-attestation --key cosign.pub \
  --type cyclonedx \
  yourorg/app:latest
```

**SLSA (Supply chain Levels for Software Artifacts):**
- Level 1: Build automation
- Level 2: Tamper resistance
- Level 3: Verifiable build environment
- Level 4: Highest assurance (two-party review)

```yaml
# .github/workflows/slsa.yml
name: SLSA Build
on:
  release:
    types: [published]

jobs:
  build:
    permissions:
      id-token: write
      contents: read
      packages: write
    uses: slsa-framework/slsa-github-generator/.github/workflows/builder_docker-based_slsa3.yml@v1.10.0
    with:
      builder-image: "yourorg/builder:latest"
      registry-username: ${{ github.actor }}
      image: yourorg/app
      tag: ${{ github.event.release.tag_name }}
```

---

## Full Security Pipeline (GitHub Actions)

```yaml
# .github/workflows/security-pipeline.yml
name: Security Pipeline
on:
  push:
    branches: [main]
  pull_request:
  schedule:
    - cron: '0 2 * * *'  # nightly

jobs:
  sast:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5

      - name: Bandit
        run: |
          pip install bandit[toml]
          bandit -r app/ -ll -f sarif -o bandit.sarif

      - name: Semgrep
        uses: returntocorp/semgrep-action@v1
        with:
          config: p/python p/owasp-top-ten p/security-audit

      - name: Upload SARIF
        uses: github/codeql-action/upload-sarif@v3
        with: { sarif_file: bandit.sarif }

  sca:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: pip-audit
        run: |
          pip install pip-audit
          pip-audit -r requirements.txt --strict

      - name: OSV Scanner
        uses: google/osv-scanner-action@v1.5.0
        with: { scan-args: --lockfile=poetry.lock }

  secrets:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with: { fetch-depth: 0 }
      - uses: gitleaks/gitleaks-action@v2
        env: { GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }} }

  container:
    runs-on: ubuntu-latest
    needs: [sast]
    steps:
      - uses: actions/checkout@v4
      - name: Build image
        run: docker build -t app:${{ github.sha }} .
      - name: Trivy
        uses: aquasecurity/trivy-action@master
        with:
          image-ref: app:${{ github.sha }}
          severity: HIGH,CRITICAL
          exit-code: '1'

  iac:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Checkov
        uses: bridgecrewio/checkov-action@master
        with:
          directory: infra/
          framework: terraform,kubernetes,dockerfile

  dast:
    runs-on: ubuntu-latest
    needs: [container]
    if: github.event_name == 'schedule'
    steps:
      - name: Deploy to staging
        run: # ... your deploy script

      - name: ZAP scan
        uses: zaproxy/action-full-scan@v0.10.0
        with:
          target: 'https://staging.acme.com'
          fail_action: true
```

---

## Severity Triage Matrix

| Severity | SLA | Example |
|---|---|---|
| **Critical** (CVSS 9-10) | Fix within 24h | RCE in framework, exposed secrets in prod |
| **High** (CVSS 7-8.9) | Fix within 1 week | SQL injection, auth bypass |
| **Medium** (CVSS 4-6.9) | Next sprint | XSS, weak crypto, info disclosure |
| **Low** (CVSS 0-3.9) | Backlog | Verbose errors, missing headers |
| **False positive** | Document + ignore | Add to allowlist with comment |

---

## Production Gotchas

| Gotcha | Fix |
|---|---|
| 200 false positives → ignored output | Tune rules; use baselines |
| CI fails on dev branches → bypassed | Required check only on main |
| Bandit + ruff overlap | Disable overlapping rules in one tool |
| `pip-audit` slow | Cache results; run nightly not per commit |
| ZAP authenticated scan broken | Use replacer plugin or session script |
| Dependabot PR storm | Use grouping rules |
| Container scan takes 10 min | Use Trivy cache; scan layers |
| Secrets in `.env.example` flagged | Add to allowlist |
| Patch increments fix CVE but break API | Test before merge; semantic versioning |
| Devs commit-bypass pre-commit | Use server-side hook + branch protection |

---

## Senior-level Checklist

- [ ] **SAST**: Bandit + Semgrep on every PR (required check)
- [ ] **SCA**: pip-audit on every PR + nightly OSV scan
- [ ] **Container**: Trivy on every image build, fail on CRITICAL/HIGH
- [ ] **IaC**: Checkov on Terraform/K8s files
- [ ] **Secrets**: gitleaks + GitHub secret scanning enabled
- [ ] **DAST**: ZAP weekly against staging
- [ ] **SBOM**: Syft generates SBOM per release
- [ ] **Signing**: cosign signs all production containers
- [ ] **Dependabot/Renovate**: auto-PRs configured with grouping
- [ ] **Severity SLAs**: documented + tracked (Linear/Jira labels)
- [ ] **Allowlists**: false positives documented with reason
- [ ] **SARIF upload**: GitHub Code Scanning enabled
- [ ] **Pre-commit hooks**: installed locally
- [ ] **Security training**: annual for engineers
- [ ] **Bug bounty / VDP**: published security.txt
- [ ] **Incident runbook**: documented for CVE response

---

## When to Escalate

```
CVE in production dep:
  CRITICAL → page on-call immediately
  HIGH → notify team, fix within week
  MEDIUM → ticket, next sprint
  LOW → backlog

Found in CI:
  ALWAYS block merge if critical/high
  Require justification for ignoring

Found in staging DAST:
  CRITICAL → block release
  HIGH → must fix before launch
```

---

## Related Docs
- `12_security_testing.md` — general security testing
- `13_waf_protection.md` — runtime protection
- `15_pen_testing_methodology.md` — manual testing
- `20_owasp_api_top10.md` — common vulnerabilities
- `Phase3_DevOps/03_github_actions_cicd.md` — CI integration

## External References
- OWASP ASVS: https://owasp.org/www-project-application-security-verification-standard/
- NIST SP 800-218 (SSDF): https://csrc.nist.gov/publications/detail/sp/800-218/final
- SLSA: https://slsa.dev
- CycloneDX: https://cyclonedx.org
- Sigstore: https://www.sigstore.dev
