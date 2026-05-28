# Security Testing — SAST, DAST, Dependency Scanning, Pen Testing

## Quick Concepts

**WHAT:**
- **SAST** = Static Application Security Testing (code analysis without running)
- **DAST** = Dynamic Application Security Testing (running app testing)
- **SCA** = Software Composition Analysis (dependency vulnerabilities)
- **Container scanning** = Image vulnerability scanning
- **Pen testing** = Manual exploitation attempts
- **Bug bounty** = Crowd-sourced security testing
- **Fuzz testing** = Random/malformed inputs

**WHY security testing in dev cycle:**
- ❌ Find security bugs LATE = expensive fix
- ❌ Manual review misses things
- ❌ Dependencies have known CVEs
- ✅ Automated checks catch 80% of common issues
- ✅ "Shift left" — security earlier in SDLC

**HOW testing layers stack:**

```
┌──────────────────────────────────────────────────┐
│  Pre-commit hooks (developer machine)             │
│  - Secret detection                               │
│  - Linting + basic SAST                           │
├──────────────────────────────────────────────────┤
│  CI pipeline (per PR)                             │
│  - SAST (bandit, semgrep)                         │
│  - SCA (safety, snyk)                             │
│  - Container scan (Trivy)                         │
├──────────────────────────────────────────────────┤
│  Staging environment                              │
│  - DAST (OWASP ZAP)                               │
│  - Integration security tests                     │
├──────────────────────────────────────────────────┤
│  Production (continuous)                          │
│  - Runtime monitoring                             │
│  - WAF logs                                       │
│  - Bug bounty program                             │
├──────────────────────────────────────────────────┤
│  Periodic (quarterly/annual)                      │
│  - Pen testing                                    │
│  - Security audit                                 │
└──────────────────────────────────────────────────┘
```

---

## Interview Questions & Answers

### Q1: SAST — Python me kaise integrate karein?

**Answer:**

**WHAT:** Static analysis = check code without running it.

**WHY:**
- ✅ Catches known patterns (SQL injection, hardcoded secrets)
- ✅ Fast (no app deployment needed)
- ✅ Runs on every PR
- ❌ False positives common
- ❌ Can't catch logic bugs

**HOW — Bandit (Python-specific):**

```bash
# Install
pip install bandit

# Run
bandit -r ./app

# Output example:
# >> Issue: [B105:hardcoded_password_string] Possible hardcoded password: 'admin123'
#    Severity: Low   Confidence: Medium
#    Location: app/auth.py:42
# 41    def authenticate(username):
# 42        if username == "admin" and password == "admin123":
#                                                  ^^^^^^^^^
```

**HOW — Bandit config + CI:**

```yaml
# .bandit.yml
exclude_dirs:
  - tests
  - .venv
  - migrations

skips:
  - B101    # assert_used (OK in tests)

# Run only on changes
```

```yaml
# .github/workflows/security.yml
name: Security Scan

on:
  pull_request:

jobs:
  sast:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Bandit
        run: |
          pip install bandit
          bandit -r app/ -ll -ii -f json -o bandit-report.json
          # -ll: low severity, -ii: medium confidence

      - name: Upload report
        if: always()
        uses: actions/upload-artifact@v3
        with:
          name: bandit-report
          path: bandit-report.json
```

**HOW — Semgrep (multi-language, modern):**

```bash
# Install
pip install semgrep

# Run with auto-config (downloads rules from registry)
semgrep --config auto ./app

# Or specific rule packs
semgrep --config p/python --config p/security-audit ./app
semgrep --config p/owasp-top-ten ./app

# Custom rule example
cat > rules/no-pickle.yml <<EOF
rules:
  - id: no-pickle-loads
    pattern: pickle.loads(...)
    message: |
      pickle.loads() can execute arbitrary code.
      Use json.loads or msgpack instead.
    severity: ERROR
    languages: [python]
EOF

semgrep --config rules/ ./app
```

**Common issues SAST catches:**

```python
# 1. Hardcoded secrets
PASSWORD = "admin123"                    # ❌ Caught

# 2. SQL injection
cursor.execute(f"SELECT * FROM users WHERE id = {user_id}")    # ❌ Caught

# 3. Command injection
os.system(f"ping {user_input}")          # ❌ Caught

# 4. Weak crypto
hashlib.md5(password)                    # ❌ MD5 weak

# 5. Insecure deserialization
pickle.loads(untrusted_data)            # ❌ Caught

# 6. SSL verification disabled
requests.get(url, verify=False)         # ❌ Caught

# 7. Subprocess shell=True
subprocess.run(cmd, shell=True)         # ⚠️ Warned

# 8. Use of eval
eval(user_input)                         # ❌ Caught
```

---

### Q2: SCA — dependency vulnerability scanning?

**Answer:**

**WHAT:** Check if dependencies have known CVEs (Common Vulnerabilities and Exposures).

**WHY critical:**
- 80% of code in modern apps = dependencies
- One vulnerable package = breach
- Examples: Log4Shell, Heartbleed, Equifax

**HOW — safety (Python):**

```bash
# Install
pip install safety

# Check installed packages
safety check

# Check requirements file
safety check -r requirements.txt

# Output:
# +══════════════════════════════════════════════════════════════════════════════+
# │ REPORT                                                                       │
# │ checked 145 packages, using free DB                                          │
# +══════════════════════════════════════════════════════════════════════════════+
# +══════════════════════════════════════════════════════════════════════════════+
# │ VULNERABILITY ID:  43622                                                     │
# │ AFFECTED:          urllib3<1.26.5                                            │
# │ INSTALLED:         1.26.4                                                    │
# │ DESCRIPTION:                                                                 │
# │  urllib3 contains a vulnerability in the URL parser...                       │
# │ CVE:               CVE-2021-33503                                            │
# +══════════════════════════════════════════════════════════════════════════════+

# JSON output for CI
safety check --json --output safety-report.json
```

**HOW — pip-audit (newer, official PyPI):**

```bash
pip install pip-audit

# Scan
pip-audit

# Auto-fix (where possible)
pip-audit --fix

# Specific requirement
pip-audit -r requirements.txt
```

**HOW — Snyk (commercial, more comprehensive):**

```bash
# Install
npm install -g snyk

# Authenticate
snyk auth

# Test
snyk test
snyk test --json > snyk-report.json

# Monitor (track over time)
snyk monitor

# Fix
snyk wizard    # Interactive fix
```

**HOW — Dependabot (GitHub native):**

```yaml
# .github/dependabot.yml
version: 2
updates:
  - package-ecosystem: "pip"
    directory: "/"
    schedule:
      interval: "weekly"
    open-pull-requests-limit: 10
    versioning-strategy: increase
    labels:
      - "dependencies"
      - "security"

  - package-ecosystem: "docker"
    directory: "/"
    schedule:
      interval: "weekly"

  - package-ecosystem: "github-actions"
    directory: "/"
    schedule:
      interval: "monthly"
```

**HOW — Lock files (reproducibility):**

```bash
# Generate lock file (Poetry / pip-tools)
pip-compile requirements.in > requirements.txt
# OR
poetry lock

# Install exact versions
pip install -r requirements.txt --no-deps
```

---

### Q3: DAST — running app security testing?

**Answer:**

**WHAT:** Test the running application like an attacker would.

**WHY beyond SAST:**
- ✅ Finds runtime issues (auth bypass, IDOR)
- ✅ Tests integration
- ❌ Slower (needs running app)
- ❌ Needs test environment

**HOW — OWASP ZAP (free, popular):**

```bash
# Docker version (easiest)
docker run -t owasp/zap2docker-stable zap-baseline.py \
  -t https://staging.example.com

# Baseline scan (passive, safe)
docker run -t owasp/zap2docker-stable zap-baseline.py \
  -t https://staging.example.com \
  -r zap-report.html

# Full active scan (more thorough, can break things)
docker run -t owasp/zap2docker-stable zap-full-scan.py \
  -t https://staging.example.com \
  -r zap-report.html
```

**HOW — ZAP in CI/CD:**

```yaml
# .github/workflows/dast.yml
name: DAST Scan

on:
  schedule:
    - cron: '0 0 * * 0'    # Weekly
  workflow_dispatch:

jobs:
  zap:
    runs-on: ubuntu-latest
    steps:
      - name: ZAP Baseline Scan
        uses: zaproxy/action-baseline@v0.10.0
        with:
          target: 'https://staging.example.com'
          cmd_options: '-a'   # Active mode

      - name: Upload report
        if: always()
        uses: actions/upload-artifact@v3
        with:
          name: zap-report
          path: report_html.html
```

**HOW — Custom DAST tests with pytest:**

```python
# tests/security/test_security.py
import pytest
import httpx


@pytest.fixture
def base_url():
    return "http://staging.example.com"


class TestSecurityHeaders:
    """Verify security headers present."""

    async def test_hsts_header(self, base_url):
        async with httpx.AsyncClient() as client:
            response = await client.get(base_url)

        hsts = response.headers.get("Strict-Transport-Security", "")
        assert "max-age=" in hsts
        max_age = int(hsts.split("max-age=")[1].split(";")[0])
        assert max_age >= 31536000, f"HSTS max-age too short: {max_age}"

    async def test_csp_header(self, base_url):
        async with httpx.AsyncClient() as client:
            response = await client.get(base_url)

        assert "Content-Security-Policy" in response.headers

    async def test_x_frame_options(self, base_url):
        async with httpx.AsyncClient() as client:
            response = await client.get(base_url)

        assert response.headers.get("X-Frame-Options") in ["DENY", "SAMEORIGIN"]


class TestSQLInjection:
    """Try common SQL injection payloads."""

    @pytest.mark.parametrize("payload", [
        "' OR '1'='1",
        "'; DROP TABLE users--",
        "1' UNION SELECT * FROM users--",
        "admin'--",
    ])
    async def test_login_sql_injection(self, base_url, payload):
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{base_url}/api/login",
                json={"email": payload, "password": "test"}
            )

        # Should reject, not return DB data
        assert response.status_code in [400, 401]
        assert "syntax error" not in response.text.lower()
        assert "sql" not in response.text.lower()


class TestAuthBypass:
    """Test authentication bypass attempts."""

    async def test_no_token_blocked(self, base_url):
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{base_url}/api/admin/users")
        assert response.status_code == 401

    async def test_invalid_jwt(self, base_url):
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{base_url}/api/admin/users",
                headers={"Authorization": "Bearer invalid-token"}
            )
        assert response.status_code == 401

    async def test_alg_none_attack(self, base_url):
        """JWT alg=none attack should be rejected."""
        # Create unsigned JWT with admin role
        import jwt
        token = jwt.encode(
            {"role": "admin", "user_id": 1},
            key="",
            algorithm="none"
        )

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{base_url}/api/admin/users",
                headers={"Authorization": f"Bearer {token}"}
            )

        assert response.status_code == 401


class TestRateLimit:
    """Verify rate limiting works."""

    async def test_login_rate_limit(self, base_url):
        async with httpx.AsyncClient() as client:
            # Hammer login endpoint
            for i in range(20):
                response = await client.post(
                    f"{base_url}/api/login",
                    json={"email": "test@test.com", "password": "wrong"}
                )

        # Should hit rate limit
        assert response.status_code == 429
        assert "Retry-After" in response.headers
```

---

### Q4: Container scanning — Docker image security?

**Answer:**

**WHAT:** Scan Docker images for known vulnerabilities.

**HOW — Trivy (free, fast):**

```bash
# Install
brew install aquasecurity/trivy/trivy

# Scan image
trivy image myapp:latest

# Output:
# myapp:latest (debian 12.0)
# =================================
# Total: 5 (UNKNOWN: 0, LOW: 0, MEDIUM: 2, HIGH: 2, CRITICAL: 1)
#
# ┌─────────┬────────────────┬──────────┬──────────────┐
# │ Library │ Vulnerability  │ Severity │ Fixed Version │
# ├─────────┼────────────────┼──────────┼──────────────┤
# │ libssl  │ CVE-2024-1234  │ CRITICAL │ 3.0.10        │
# │ curl    │ CVE-2023-5678  │ HIGH     │ 8.0.1         │
# └─────────┴────────────────┴──────────┴──────────────┘

# Scan only high/critical
trivy image --severity HIGH,CRITICAL myapp:latest

# Output formats
trivy image --format json -o trivy-report.json myapp:latest
trivy image --format sarif -o trivy.sarif myapp:latest    # GitHub integration
```

**HOW — Trivy in CI/CD:**

```yaml
# .github/workflows/container-scan.yml
name: Container Scan

on:
  pull_request:
    paths: ['Dockerfile', 'requirements.txt']

jobs:
  scan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Build image
        run: docker build -t myapp:${{ github.sha }} .

      - name: Trivy scan
        uses: aquasecurity/trivy-action@master
        with:
          image-ref: myapp:${{ github.sha }}
          format: 'sarif'
          output: 'trivy-results.sarif'
          severity: 'CRITICAL,HIGH'
          exit-code: '1'      # Fail PR on findings

      - name: Upload to GitHub Security
        if: always()
        uses: github/codeql-action/upload-sarif@v3
        with:
          sarif_file: 'trivy-results.sarif'
```

**HOW — ECR scanning (AWS):**

```hcl
resource "aws_ecr_repository" "myapp" {
  name = "myapp"

  image_scanning_configuration {
    scan_on_push = true   # ⭐ Auto-scan every push
  }
}

# Continuous scanning (rescans existing for new CVEs)
resource "aws_inspector2_enabler" "ecr" {
  account_ids    = [data.aws_caller_identity.current.account_id]
  resource_types = ["ECR"]
}
```

**HOW — Distroless images (reduce attack surface):**

```dockerfile
# Multi-stage with distroless
FROM python:3.12-slim AS builder
WORKDIR /app
COPY requirements.txt .
RUN pip install --prefix=/install -r requirements.txt

# ⭐ Distroless: no shell, no package manager, no busybox
FROM gcr.io/distroless/python3-debian12
WORKDIR /app
COPY --from=builder /install /usr/local
COPY . .
USER nonroot
CMD ["app.py"]
```

---

### Q5: Pre-commit hooks — secrets detection?

**Answer:**

**WHAT:** Run security checks BEFORE commit (catch on developer machine).

**HOW — Setup pre-commit framework:**

```bash
# Install
pip install pre-commit

# .pre-commit-config.yaml
```

```yaml
# .pre-commit-config.yaml
repos:
  # Detect secrets
  - repo: https://github.com/Yelp/detect-secrets
    rev: v1.4.0
    hooks:
      - id: detect-secrets
        args: ['--baseline', '.secrets.baseline']

  # gitleaks (Go-based, fast)
  - repo: https://github.com/gitleaks/gitleaks
    rev: v8.18.0
    hooks:
      - id: gitleaks

  # SAST
  - repo: https://github.com/PyCQA/bandit
    rev: 1.7.5
    hooks:
      - id: bandit
        args: ['-c', 'pyproject.toml']

  # Linting
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.1.0
    hooks:
      - id: ruff
      - id: ruff-format

  # Type checking
  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.7.0
    hooks:
      - id: mypy
```

```bash
# Install hooks
pre-commit install

# Test on all files
pre-commit run --all-files

# Now runs automatically on every commit
git commit -m "test"
# > detect-secrets..........................Passed
# > bandit..................................Failed
# >   - hit: app/auth.py:42: Hardcoded password
```

**HOW — Baseline secrets (allow known false positives):**

```bash
# Create baseline
detect-secrets scan > .secrets.baseline

# Commit .secrets.baseline (it lists known "secrets" that are OK)

# Audit baseline interactively (mark each as real secret or false positive)
detect-secrets audit .secrets.baseline
```

---

### Q6: Pen testing — when + what?

**Answer:**

**WHAT:** Manual security testing by humans (find what automation misses).

**WHEN to do pen test:**
- Major releases
- Before SOC2/compliance audit
- After major architecture changes
- Annually at minimum
- Customer requirement (enterprise deals)

**HOW — Engagement types:**

| Type | Description | Time | Cost |
|---|---|---|---|
| **Black box** | Tester has no inside info | 2-3 weeks | $$$$ |
| **Grey box** | Tester has user account | 2 weeks | $$$ |
| **White box** | Tester has source code | 1-2 weeks | $$ |

**HOW — Pen test scope (typical):**

```markdown
# Pen Test Scope Document

## In Scope
- Web application: https://app.example.com
- API: https://api.example.com
- Mobile app: iOS + Android
- User accounts: 3 test accounts (admin, user, guest)

## Out of Scope
- Production database (test in staging)
- Physical security
- Social engineering of employees
- DoS attacks
- Third-party services (Stripe, Auth0)

## Testing Hours
- 9am-6pm IST, Mon-Fri only (no nights/weekends without approval)

## Reporting
- Critical findings: notify within 24h
- Final report: PDF + executive summary
- Each finding: severity, CVSS score, reproduction, recommendation

## Remediation SLA
- Critical: 7 days
- High: 30 days
- Medium: 90 days
- Low: best effort
```

**HOW — Common pen test findings:**

| Finding | Common Cause | Fix |
|---|---|---|
| IDOR (Insecure Direct Object Reference) | No ownership check | Verify resource owner |
| Privilege escalation | Bug in RBAC | Method-level checks |
| Stored XSS | User input rendered HTML | Sanitize/escape |
| CSRF | Missing token | CSRF middleware |
| Information disclosure | Verbose errors in prod | Generic error messages |
| Weak password policy | No complexity check | Enforce 8+ chars, etc. |
| Session fixation | Same ID after login | Regenerate on login |
| Sensitive data in logs | Logging PII | Redact before log |

---

### Q7: Bug bounty program — setup karein?

**Answer:**

**WHAT:** Pay external researchers for finding vulnerabilities.

**WHY:**
- ✅ Crowd > internal team
- ✅ Pay only for results (no salary)
- ✅ Continuous testing (not periodic)
- ✅ Marketing benefit (security-focused company image)

**HOW — Platform options:**

| Platform | Cost | Best For |
|---|---|---|
| **HackerOne** | Commission + retainer | Large companies |
| **Bugcrowd** | Commission | Mid-sized |
| **Intigriti** | Commission | EU focus |
| **Self-hosted** | Free (but ops cost) | Strict control |

**HOW — Bug bounty policy:**

```markdown
# Bug Bounty Program — Example Policy

## Scope
- ✅ *.example.com, *.api.example.com
- ✅ iOS/Android apps
- ❌ test.example.com (intentional vulnerabilities for learning)
- ❌ Third-party services

## Rewards (USD)
| Severity | Reward Range |
|----------|--------------|
| Critical | $5,000 - $10,000 |
| High     | $1,000 - $5,000 |
| Medium   | $500 - $1,000 |
| Low      | $100 - $500 |

## Severity Examples
**Critical:**
- Remote code execution
- Authentication bypass to admin
- Full database access

**High:**
- IDOR exposing other users' data
- Privilege escalation
- Stored XSS in admin panel

**Medium:**
- Reflected XSS
- CSRF without sensitive impact
- Open redirect

**Low:**
- Missing security headers
- Verbose error messages

## Rules
- Don't access/modify other users' data
- Don't perform DoS
- Don't share findings publicly until fixed
- 90-day disclosure timeline

## Response SLA
- Acknowledge: 24 hours
- Triage: 7 days
- Fix critical: 7 days
- Fix high: 30 days
- Payment: within 60 days of fix

## Out of Scope (Won't pay for)
- Theoretical vulnerabilities without PoC
- Best-practice issues without exploitability
- Self-XSS
- Open ports without exploit
- Missing rate limiting (without amplification attack)
```

---

### Q8: Fuzz testing — Python ke liye?

**Answer:**

**WHAT:** Test with random/malformed inputs to find crashes.

**WHY:**
- Catches edge cases manual testing misses
- Finds buffer overflows, parser bugs
- Used by Google OSS-Fuzz for major projects

**HOW — Atheris (Python fuzzer by Google):**

```python
# pip install atheris

import atheris
import sys

with atheris.instrument_imports():
    import myapp.parser

def fuzz_parser(data):
    """
    Atheris will call this with random bytes.
    Find inputs that crash the parser.
    """
    try:
        result = myapp.parser.parse_input(data.decode("utf-8", errors="ignore"))
    except (UnicodeDecodeError, ValueError):
        # Expected exceptions — not interesting
        pass
    except Exception as e:
        # ⭐ UNEXPECTED exception = bug found
        raise

atheris.Setup(sys.argv, fuzz_parser)
atheris.Fuzz()
```

**HOW — Hypothesis (property-based testing):**

```python
# pip install hypothesis

from hypothesis import given, strategies as st


@given(st.text())
def test_parse_doesnt_crash(input_str):
    """Parser should handle any string without crashing."""
    try:
        result = myapp.parser.parse(input_str)
    except ValueError:
        # Expected for invalid input
        pass


@given(st.integers(min_value=1, max_value=10**18))
def test_user_id_validation(user_id):
    """User ID validation should be consistent."""
    assert isinstance(myapp.validate_user_id(user_id), bool)


@given(st.dictionaries(st.text(), st.text()))
def test_json_roundtrip(data):
    """JSON encode/decode should preserve data."""
    import json
    encoded = json.dumps(data)
    decoded = json.loads(encoded)
    assert decoded == data
```

---

## Security Testing Checklist

```markdown
### Pre-commit (Developer)
- [ ] detect-secrets / gitleaks
- [ ] bandit / semgrep
- [ ] Linting (ruff)
- [ ] Type checking (mypy)

### CI/CD Pipeline (Every PR)
- [ ] SAST (bandit, semgrep)
- [ ] SCA (safety, snyk, pip-audit)
- [ ] Container scan (Trivy)
- [ ] Dependency check (Dependabot)
- [ ] Block PR on critical findings

### Pre-Release (Staging)
- [ ] DAST (OWASP ZAP)
- [ ] Custom security tests (pytest)
- [ ] API contract testing
- [ ] Load testing (security under load)

### Production (Continuous)
- [ ] WAF logs monitoring
- [ ] Anomaly detection (failed logins, unusual API calls)
- [ ] Bug bounty program
- [ ] Penetration testing (quarterly/annual)
- [ ] Security audit (annual)

### Periodic Reviews
- [ ] Quarterly dependency review
- [ ] Quarterly access review
- [ ] Annual pen test
- [ ] Compliance audit (SOC2, etc.)
- [ ] Tabletop exercise (incident response practice)
```

---

## Top Tools Summary

| Tool | Type | Best For | Cost |
|---|---|---|---|
| **Bandit** | SAST | Python | Free |
| **Semgrep** | SAST | Multi-language | Free + paid |
| **safety / pip-audit** | SCA | Python deps | Free |
| **Snyk** | SCA + container | All | Paid (free tier) |
| **Trivy** | Container | Docker images | Free |
| **OWASP ZAP** | DAST | Web apps | Free |
| **Burp Suite** | DAST | Manual pen testing | Paid |
| **detect-secrets** | Secrets scan | Pre-commit | Free |
| **gitleaks** | Secrets scan | Pre-commit | Free |
| **Atheris** | Fuzzing | Python | Free |
| **Hypothesis** | Property testing | Python | Free |
| **HackerOne / Bugcrowd** | Bug bounty | Production | Paid |
