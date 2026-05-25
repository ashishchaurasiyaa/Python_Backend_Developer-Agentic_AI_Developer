"""
Phase3_Security — Security Testing Practical
===============================================
Topics covered:
  1. SAST patterns (what bandit/semgrep catches)
  2. SCA — dependency vulnerability check
  3. DAST — security tests via pytest
  4. Pre-commit hook setup (detect-secrets, gitleaks)
  5. Container scanning patterns (Trivy)
  6. Test injection attacks (SQL, XSS, command)
  7. Test auth bypass attempts
  8. Test rate limiting
  9. Fuzz testing with Hypothesis
  10. Penetration test scenarios

Run:
  pip install pytest pytest-asyncio httpx hypothesis bandit safety
  python 04_security_testing_practical.py
"""

import asyncio
import json
import re
from typing import Optional

# ─────────────────────────────────────────────────────────────────────────────
# SECTION 1: SAST — Code Patterns That Bandit Catches
# INTERVIEW: Static analysis findings
# ─────────────────────────────────────────────────────────────────────────────

SAST_ISSUES_EXAMPLES = """
# ─── Issue 1: Hardcoded password ──────────────
PASSWORD = "admin123"                           # ❌ B105

# ─── Issue 2: SQL injection ───────────────────
def get_user(user_id):
    cursor.execute(f"SELECT * FROM users WHERE id = {user_id}")    # ❌ B608

# ─── Issue 3: Command injection ───────────────
def ping(host):
    os.system(f"ping -c 1 {host}")              # ❌ B605

# ─── Issue 4: subprocess shell=True ───────────
subprocess.run(cmd, shell=True)                 # ❌ B602

# ─── Issue 5: Weak crypto ─────────────────────
import hashlib
password_hash = hashlib.md5(password.encode()).hexdigest()    # ❌ B303

# ─── Issue 6: Insecure deserialization ────────
import pickle
data = pickle.loads(untrusted_data)             # ❌ B301

# ─── Issue 7: eval() ──────────────────────────
eval(user_input)                                # ❌ B307

# ─── Issue 8: SSL verification disabled ───────
import requests
requests.get(url, verify=False)                 # ❌ B501

# ─── Issue 9: Insecure temp file ──────────────
tmpfile = '/tmp/data.txt'                        # ❌ B108

# ─── Issue 10: Use of assert in non-test ──────
def check_user(user):
    assert user.is_admin                         # ❌ B101 (asserts skipped in -O mode)
"""

# Run bandit
RUN_BANDIT = """
# Install
pip install bandit

# Scan code
bandit -r ./app

# CI-friendly (JSON output)
bandit -r ./app -f json -o bandit-report.json

# Severity filter
bandit -r ./app -ll        # Low severity and up
bandit -r ./app -lll       # High severity only
"""

# Semgrep (multi-language)
SEMGREP_USAGE = """
# Install
pip install semgrep

# Run with curated rules
semgrep --config auto ./app

# OWASP Top 10 ruleset
semgrep --config p/owasp-top-ten ./app

# Python security
semgrep --config p/python ./app

# Custom rule
cat > rules/no-eval.yml <<EOF
rules:
  - id: no-eval
    pattern: eval(...)
    message: eval() executes arbitrary code
    severity: ERROR
    languages: [python]
EOF

semgrep --config rules/ ./app
"""

# ─────────────────────────────────────────────────────────────────────────────
# SECTION 2: SCA — Dependency Scanning
# INTERVIEW: Catch CVEs in dependencies
# ─────────────────────────────────────────────────────────────────────────────

SAFETY_USAGE = """
# Install
pip install safety

# Check installed packages
safety check

# Check requirements file
safety check -r requirements.txt

# JSON output
safety check --json --output safety-report.json

# Ignore specific CVE
safety check --ignore 12345

# Fix command (suggests upgrades)
safety check --bare    # Just CVE IDs
"""


PIP_AUDIT_USAGE = """
# Install (newer, official PyPI)
pip install pip-audit

# Scan
pip-audit

# Auto-fix
pip-audit --fix

# Specific file
pip-audit -r requirements.txt

# JSON
pip-audit --format json --output audit.json

# Skip dev dependencies
pip-audit --skip-editable
"""


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 3: DAST Tests (Custom pytest security tests)
# INTERVIEW: Test running app like attacker
# ─────────────────────────────────────────────────────────────────────────────

class SecurityTestSuite:
    """
    INTERVIEW: Custom DAST tests against running app.
    Run on staging environment.
    """
    def __init__(self, base_url: str):
        self.base_url = base_url

    def test_security_headers(self, response_headers: dict) -> list:
        """Verify all required security headers."""
        issues = []

        # HSTS
        hsts = response_headers.get("Strict-Transport-Security", "")
        if not hsts:
            issues.append("Missing HSTS header")
        elif "max-age=" not in hsts:
            issues.append("HSTS missing max-age")
        else:
            try:
                max_age = int(hsts.split("max-age=")[1].split(";")[0])
                if max_age < 31536000:
                    issues.append(f"HSTS max-age too short: {max_age}")
            except (IndexError, ValueError):
                issues.append("HSTS max-age parse error")

        # CSP
        if "Content-Security-Policy" not in response_headers:
            issues.append("Missing Content-Security-Policy")

        # X-Frame-Options
        xfo = response_headers.get("X-Frame-Options", "")
        if xfo not in ["DENY", "SAMEORIGIN"]:
            issues.append(f"X-Frame-Options invalid: {xfo}")

        # X-Content-Type-Options
        if response_headers.get("X-Content-Type-Options") != "nosniff":
            issues.append("X-Content-Type-Options should be 'nosniff'")

        # Referrer-Policy
        if "Referrer-Policy" not in response_headers:
            issues.append("Missing Referrer-Policy")

        # Server header (should NOT be present)
        if "Server" in response_headers:
            issues.append(f"Server header leak: {response_headers['Server']}")

        return issues


# Sample pytest tests
PYTEST_SECURITY_TESTS = """
# tests/security/test_security.py
import pytest
import httpx

BASE_URL = "https://staging.example.com"


class TestSQLInjection:
    \"\"\"Try SQL injection payloads on all input endpoints.\"\"\"

    SQL_PAYLOADS = [
        "' OR '1'='1",
        "'; DROP TABLE users--",
        "1' UNION SELECT * FROM users--",
        "admin'--",
        "1; INSERT INTO users VALUES (...)--",
    ]

    @pytest.mark.parametrize("payload", SQL_PAYLOADS)
    async def test_login_sql_injection(self, payload):
        async with httpx.AsyncClient() as client:
            response = await client.post(f"{BASE_URL}/api/login", json={
                "email": payload, "password": "test"
            })

        # Should reject, not crash, not leak SQL errors
        assert response.status_code in [400, 401]
        body = response.text.lower()
        assert "syntax error" not in body
        assert "sql" not in body
        assert "database" not in body


class TestXSS:
    \"\"\"Test for XSS vulnerabilities.\"\"\"

    XSS_PAYLOADS = [
        "<script>alert('xss')</script>",
        "<img src=x onerror=alert(1)>",
        "<svg/onload=alert(1)>",
        "javascript:alert(1)",
        "'\"<script>alert(1)</script>",
    ]

    @pytest.mark.parametrize("payload", XSS_PAYLOADS)
    async def test_user_input_escaped(self, payload):
        async with httpx.AsyncClient() as client:
            # Save XSS payload as user data
            await client.post(f"{BASE_URL}/api/users", json={
                "name": payload, "email": "test@x.com"
            })

            # Retrieve and verify escaped
            response = await client.get(f"{BASE_URL}/api/users/1")
            assert "<script>" not in response.text
            assert "javascript:" not in response.text


class TestAuthBypass:
    \"\"\"Authentication bypass attempts.\"\"\"

    async def test_no_token_blocked(self):
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{BASE_URL}/api/admin/users")
        assert response.status_code == 401

    async def test_invalid_jwt(self):
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{BASE_URL}/api/admin/users",
                headers={"Authorization": "Bearer invalid-token"}
            )
        assert response.status_code == 401

    async def test_jwt_alg_none_attack(self):
        \"\"\"JWT alg=none attack must be rejected.\"\"\"
        import jwt
        token = jwt.encode(
            {"role": "admin"},
            key="",
            algorithm="none"
        )
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{BASE_URL}/api/admin",
                headers={"Authorization": f"Bearer {token}"}
            )
        assert response.status_code == 401

    async def test_path_traversal(self):
        \"\"\"Try path traversal in file endpoints.\"\"\"
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{BASE_URL}/api/files/../../etc/passwd"
            )
        assert response.status_code in [400, 404]


class TestRateLimit:
    \"\"\"Verify rate limiting protects sensitive endpoints.\"\"\"

    async def test_login_rate_limit(self):
        async with httpx.AsyncClient() as client:
            statuses = []
            for i in range(20):
                response = await client.post(f"{BASE_URL}/api/login", json={
                    "email": "test@test.com", "password": "wrong"
                })
                statuses.append(response.status_code)

        # Should hit rate limit
        assert 429 in statuses
        # Verify Retry-After header
        # last_response.headers should have "Retry-After"


class TestCSRF:
    \"\"\"CSRF protection on state-changing endpoints.\"\"\"

    async def test_state_change_requires_token(self):
        async with httpx.AsyncClient() as client:
            # No CSRF token
            response = await client.post(
                f"{BASE_URL}/api/account/email",
                json={"email": "new@x.com"},
                cookies={"session": "valid-session"}
            )
        # Should reject without CSRF token
        assert response.status_code == 403
"""


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 4: Pre-commit Hooks
# INTERVIEW: Catch issues before commit
# ─────────────────────────────────────────────────────────────────────────────

PRE_COMMIT_CONFIG = """
# .pre-commit-config.yaml

repos:
  # Detect secrets in code
  - repo: https://github.com/Yelp/detect-secrets
    rev: v1.4.0
    hooks:
      - id: detect-secrets
        args: ['--baseline', '.secrets.baseline']

  # Gitleaks (faster, Go-based)
  - repo: https://github.com/gitleaks/gitleaks
    rev: v8.18.0
    hooks:
      - id: gitleaks

  # Python security (SAST)
  - repo: https://github.com/PyCQA/bandit
    rev: 1.7.5
    hooks:
      - id: bandit
        args: ['-c', 'pyproject.toml']

  # Linting + formatting
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
        additional_dependencies: [types-requests]


# Setup
# pip install pre-commit
# pre-commit install
# pre-commit run --all-files
"""

DETECT_SECRETS_USAGE = """
# Create baseline (lists known false positives)
detect-secrets scan > .secrets.baseline

# Audit baseline interactively (mark real vs false positive)
detect-secrets audit .secrets.baseline

# Re-run scan against baseline
detect-secrets scan --baseline .secrets.baseline

# Now pre-commit will fail on NEW secrets only
"""


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 5: Container Scanning
# INTERVIEW: Docker image vulnerabilities
# ─────────────────────────────────────────────────────────────────────────────

TRIVY_USAGE = """
# Install
brew install aquasecurity/trivy/trivy

# Scan local image
trivy image myapp:latest

# Only critical/high
trivy image --severity HIGH,CRITICAL myapp:latest

# Exit non-zero if found (for CI)
trivy image --severity CRITICAL --exit-code 1 myapp:latest

# JSON output
trivy image --format json -o trivy.json myapp:latest

# Scan Dockerfile (before building)
trivy config Dockerfile

# Scan source code dependencies
trivy fs ./

# Scan running container
trivy image $(docker ps -q --filter ancestor=myapp:latest)
"""


GITHUB_ACTIONS_TRIVY = """
# .github/workflows/security.yml
name: Security Scan

on:
  pull_request:
  push:
    branches: [main]

jobs:
  container-scan:
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
          exit-code: '1'              # ⭐ Fail PR

      - name: Upload to GitHub Security
        if: always()
        uses: github/codeql-action/upload-sarif@v3
        with:
          sarif_file: 'trivy-results.sarif'

  python-sast:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v4
      - run: pip install bandit safety
      - name: Bandit (SAST)
        run: bandit -r app/ -ll
      - name: Safety (SCA)
        run: safety check -r requirements.txt
"""


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 6: Fuzz Testing
# INTERVIEW: Random input testing
# ─────────────────────────────────────────────────────────────────────────────

HYPOTHESIS_USAGE = """
# pip install hypothesis

from hypothesis import given, strategies as st


@given(st.text())
def test_parse_doesnt_crash(input_str):
    \"\"\"Parser should handle any string without crashing.\"\"\"
    try:
        result = my_parser.parse(input_str)
    except ValueError:
        # Expected for invalid input
        pass


@given(st.integers(min_value=1, max_value=10**18))
def test_user_id_validation(user_id):
    \"\"\"User ID validation should be consistent.\"\"\"
    assert isinstance(myapp.validate_user_id(user_id), bool)


@given(st.dictionaries(st.text(), st.text()))
def test_json_roundtrip(data):
    \"\"\"JSON encode/decode should preserve data.\"\"\"
    import json
    encoded = json.dumps(data)
    decoded = json.loads(encoded)
    assert decoded == data


@given(st.binary(min_size=1, max_size=10**6))
def test_file_upload_doesnt_crash(file_content):
    \"\"\"File upload handler shouldn't crash on any input.\"\"\"
    try:
        process_file(file_content)
    except (ValueError, FileFormatError):
        pass  # Expected errors OK
    # Other exceptions = bug!


@given(st.lists(st.integers(), min_size=0, max_size=1000))
def test_sort_is_idempotent(numbers):
    \"\"\"Sorting twice = sorting once.\"\"\"
    sorted_once = sorted(numbers)
    sorted_twice = sorted(sorted_once)
    assert sorted_once == sorted_twice
"""


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 7: Penetration Test Scenarios
# INTERVIEW: Manual testing checklist
# ─────────────────────────────────────────────────────────────────────────────

PEN_TEST_CHECKLIST = """
# Manual Penetration Testing Checklist

## Authentication
- [ ] Try common passwords (admin/admin, test/test)
- [ ] Password complexity bypass
- [ ] Account enumeration via login error messages
- [ ] Brute force protection (lock after N attempts?)
- [ ] Session timeout enforcement
- [ ] Session fixation (login keeps same ID?)
- [ ] JWT alg=none attack
- [ ] JWT key confusion (RS256 → HS256)
- [ ] Expired token still works?
- [ ] Logout truly invalidates session?

## Authorization
- [ ] IDOR (Insecure Direct Object Reference)
  - GET /api/users/123/orders → can I see user 456's orders?
- [ ] Horizontal privilege escalation (user → other user)
- [ ] Vertical privilege escalation (user → admin)
- [ ] API endpoints check permissions per resource?
- [ ] HTTP method bypass (PUT instead of POST?)

## Input Validation
- [ ] SQL injection (all parameters)
- [ ] XSS (stored + reflected)
- [ ] Command injection
- [ ] LDAP injection
- [ ] XXE (XML External Entity)
- [ ] Path traversal (../../etc/passwd)
- [ ] SSRF (server-side request forgery)
- [ ] File upload bypasses (.exe disguised as .jpg)

## Session/Cookies
- [ ] HttpOnly flag set?
- [ ] Secure flag set?
- [ ] SameSite set?
- [ ] Session ID truly random?
- [ ] Session ID changes on login?

## CSRF
- [ ] State-changing endpoints require CSRF token?
- [ ] Token validated server-side?
- [ ] Token unique per session?

## Information Disclosure
- [ ] Stack traces in production responses?
- [ ] Verbose error messages?
- [ ] Server fingerprinting (X-Powered-By)?
- [ ] Internal IP leakage?
- [ ] API documentation publicly accessible?

## Rate Limiting
- [ ] Login attempts?
- [ ] Password reset attempts?
- [ ] API endpoints overall?

## Cryptography
- [ ] Weak hashing (MD5, SHA1)?
- [ ] Hardcoded keys/secrets?
- [ ] Insecure random?
- [ ] TLS 1.0/1.1?

## DoS
- [ ] Large request body limits?
- [ ] Slow request attacks (Slowloris)?
- [ ] Recursive payloads (billion laughs)?

## Business Logic
- [ ] Price manipulation in checkout?
- [ ] Coupon code abuse?
- [ ] Race conditions in critical operations?
- [ ] Bulk operations bypass quotas?
"""


# ─────────────────────────────────────────────────────────────────────────────
# Demos
# ─────────────────────────────────────────────────────────────────────────────

def demo_sast_findings():
    print("\n[SAST Common Findings]")
    findings = [
        ("Hardcoded password", "B105", "Use Secrets Manager"),
        ("SQL injection (f-string)", "B608", "Parameterized queries"),
        ("Command injection (os.system)", "B605", "subprocess with array args"),
        ("Weak crypto (MD5)", "B303", "Use SHA-256 / bcrypt"),
        ("pickle.loads()", "B301", "Use json.loads or msgpack"),
        ("eval() on user input", "B307", "Avoid eval entirely"),
        ("SSL verify=False", "B501", "Always verify in prod"),
        ("subprocess shell=True", "B602", "Use array args"),
    ]
    print(f"  {'Finding':<30} {'Bandit Code':<12} {'Fix'}")
    print(f"  {'-'*30} {'-'*12} {'-'*30}")
    for finding, code, fix in findings:
        print(f"  {finding:<30} {code:<12} {fix}")


def demo_security_test_results():
    print("\n[Security Header Verification Demo]")

    # Simulate response from app
    sample_headers = {
        "Strict-Transport-Security": "max-age=31536000; includeSubDomains; preload",
        "Content-Security-Policy": "default-src 'self'",
        "X-Frame-Options": "DENY",
        "X-Content-Type-Options": "nosniff",
        "Referrer-Policy": "strict-origin-when-cross-origin",
        # Missing: Permissions-Policy
        # Bad: Server header
        "Server": "nginx/1.18.0",
    }

    suite = SecurityTestSuite("https://staging.example.com")
    issues = suite.test_security_headers(sample_headers)

    print(f"  Headers checked: {len(sample_headers)}")
    print(f"  Issues found: {len(issues)}")
    for issue in issues:
        print(f"  ❌ {issue}")


def demo_injection_payloads():
    print("\n[Common Injection Payloads to Test]")

    payloads = {
        "SQL Injection": [
            "' OR '1'='1",
            "'; DROP TABLE users--",
            "1' UNION SELECT * FROM users--",
        ],
        "XSS": [
            "<script>alert('xss')</script>",
            "<img src=x onerror=alert(1)>",
            "javascript:alert(1)",
        ],
        "Command Injection": [
            "; cat /etc/passwd",
            "| whoami",
            "$(rm -rf /)",
        ],
        "Path Traversal": [
            "../../etc/passwd",
            "..\\..\\windows\\system32",
            "%2e%2e%2f%2e%2e%2fetc%2fpasswd",
        ],
        "SSRF": [
            "http://169.254.169.254/latest/meta-data/",  # AWS metadata
            "http://localhost:6379/",                     # Redis
            "file:///etc/passwd",
        ],
    }

    for category, items in payloads.items():
        print(f"\n  {category}:")
        for p in items:
            print(f"    - {p}")


# ─────────────────────────────────────────────────────────────────────────────
# Q&A
# ─────────────────────────────────────────────────────────────────────────────

QA = [
    ("SAST vs DAST vs SCA?",
     "SAST: static code analysis (bandit, semgrep)\n"
     "     DAST: running app testing (ZAP, custom pytest)\n"
     "     SCA: dependency vulnerabilities (safety, snyk)"),

    ("Why bandit + safety + Trivy in CI?",
     "Defense in depth — each catches different things:\n"
     "     bandit: code patterns\n"
     "     safety: known CVEs in deps\n"
     "     Trivy: OS-level + container vulns"),

    ("Common SAST false positives?",
     "Test files (asserts), hardcoded test data, intentional unsafe patterns.\n"
     "     Use .bandit config to exclude OR # nosec comment."),

    ("How to handle hardcoded secrets after detection?",
     "1. Rotate secret IMMEDIATELY (git history exposes it)\n"
     "     2. Remove from code → use Secrets Manager\n"
     "     3. Add detect-secrets baseline to prevent regression"),

    ("Distroless images for security?",
     "Minimal attack surface (no shell, no package manager).\n"
     "     gcr.io/distroless/python3-debian12\n"
     "     Smaller, fewer CVEs, harder to exploit."),

    ("Why fuzz testing?",
     "Manual testing misses edge cases.\n"
     "     Hypothesis generates many random inputs.\n"
     "     Atheris does mutation-based fuzzing."),

    ("Pen test vs bug bounty?",
     "Pen test: scheduled (quarterly), defined scope, paid consultants\n"
     "     Bug bounty: continuous, crowd, pay per finding"),

    ("Most-common IDOR mistake?",
     "GET /api/users/{id} — returns user even if not yours\n"
     "     Fix: verify session.user_id == requested user_id"),
]


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("SECURITY TESTING PRACTICAL")
    print("=" * 60)

    demo_sast_findings()
    demo_security_test_results()
    demo_injection_payloads()

    print("\n[Security Testing Layers]")
    layers = [
        ("Pre-commit", "detect-secrets, bandit", "Developer machine"),
        ("CI Pipeline", "bandit, safety, Trivy", "Per PR"),
        ("Staging", "pytest security, OWASP ZAP", "Pre-release"),
        ("Production", "WAF logs, bug bounty", "Continuous"),
        ("Periodic", "pen test, security audit", "Quarterly"),
    ]
    print(f"  {'Layer':<15} {'Tools':<30} {'Frequency'}")
    print(f"  {'-'*15} {'-'*30} {'-'*15}")
    for layer, tools, freq in layers:
        print(f"  {layer:<15} {tools:<30} {freq}")

    print("\n[Q&A Summary]")
    for q, a in QA:
        print(f"\n  Q: {q}")
        print(f"  A: {a}")

    print("\n" + "=" * 60)
    print("FILES TO KNOW:")
    print("  .pre-commit-config.yaml  → hook setup")
    print("  .github/workflows/       → security CI")
    print("  tests/security/          → pytest DAST tests")
    print("  Dockerfile               → distroless, multi-stage")
    print("=" * 60)


if __name__ == "__main__":
    main()
