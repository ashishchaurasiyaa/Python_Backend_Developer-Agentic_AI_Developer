# 15 — Pen Testing Methodology

> Authorized simulation of attacks to find vulnerabilities before bad actors do. Standard practice for production systems.

---

## What is Pen Testing

**Penetration test:** authorized adversarial assessment of a system to identify exploitable vulnerabilities.

**Difference from:**
- **Vulnerability scan:** automated, surface-level. (e.g., Nessus.)
- **Bug bounty:** crowdsourced, ongoing.
- **Red team exercise:** simulates a real attacker over weeks, broader scope.

---

## Types of Tests

### Black box
Tester has no internal knowledge. Realistic "what an external attacker sees."

### White box
Tester has full source code + architecture access. Deeper findings, faster.

### Grey box
Limited knowledge. Compromise.

For backend apps: **grey box** most common (tester gets user credentials + brief intro to architecture).

---

## Scope Definition

Before starting:
1. **Targets**: which domains, IPs, services.
2. **In scope**: web app, API, mobile API.
3. **Out of scope**: third-party services, DDoS, phishing employees (unless red team).
4. **Time window**: avoid black-Friday peaks.
5. **Notification protocol**: who to contact if real damage detected.
6. **Reporting deadline**.
7. **Legal agreement** (SOW with explicit authorization).

**Never pen-test without written authorization.** Computer fraud laws are strict.

---

## OWASP Top 10 — The Core Targets

The most common web vulnerabilities (2021 list, still relevant):

### A01: Broken Access Control
- Direct object references: `/api/orders/{id}` works even if id isn't yours.
- Path traversal: `../../../etc/passwd`.
- Missing function-level access checks (admin endpoints reachable by users).
- JWT misconfiguration.

**Test:** Try accessing other users' data with your token. Try escalating to admin.

### A02: Cryptographic Failures
- Plaintext password storage.
- Weak hashing (MD5, SHA1 for passwords).
- TLS misconfigured.
- Secrets in URLs.

**Test:** Inspect storage; review TLS config (SSL Labs scan).

### A03: Injection
- SQL injection.
- NoSQL injection.
- OS command injection.
- LDAP / XML / template injection.

**Test:** Send `' OR '1'='1`, `'; DROP TABLE users;--`, `{$where: 'this'}`, `; cat /etc/passwd` etc.

### A04: Insecure Design
- Missing rate limits.
- No business logic checks.
- Insufficient validation.

**Test:** Race conditions, replay attacks, business logic abuse.

### A05: Security Misconfiguration
- Default credentials.
- Verbose error messages exposing internals.
- Debug mode in production.
- Open admin interfaces.

**Test:** Check error messages, default URLs, headers.

### A06: Vulnerable and Outdated Components
- Old library versions with known CVEs.
- Outdated OS, web server.

**Test:** Run `pip-audit`, `npm audit`, `safety check`, `trivy`.

### A07: Identification & Authentication Failures
- Weak passwords allowed.
- No rate limit on login.
- Session fixation.
- Predictable session tokens.

**Test:** Try weak passwords, brute force, session manipulation.

### A08: Software & Data Integrity Failures
- Unsigned updates.
- Dependency chain attacks.
- Insecure deserialization.

**Test:** Tamper with serialized data, check update verification.

### A09: Security Logging & Monitoring Failures
- Insufficient logging.
- Logs not monitored.
- No alerting on suspicious activity.

**Test:** Perform attacks; check if logged + detected.

### A10: SSRF (Server-Side Request Forgery)
- App fetches user-supplied URL → tester points to internal services.

**Test:** Submit `http://localhost:8080/admin` or `http://169.254.169.254/latest/meta-data/` (AWS metadata).

---

## Methodology (5 Phases)

### Phase 1: Reconnaissance
Gather information.
- DNS records, subdomains.
- Public services (Shodan, censys.io).
- Tech stack (Wappalyzer).
- Employee LinkedIn (for phishing scope).
- Public GitHub repos (secrets?).

### Phase 2: Scanning
- Nmap port scan.
- Burp Suite spider.
- nikto / dirb (directory enumeration).
- Subdomain enumeration (Sublist3r, amass).

### Phase 3: Exploitation
- Try OWASP Top 10 attacks.
- Custom for app logic.
- Privilege escalation.
- Data exfiltration.

### Phase 4: Post-Exploitation
- Lateral movement.
- Persistence.
- Impact assessment.

### Phase 5: Reporting
- Vulnerabilities found.
- Severity (CVSS scores).
- Reproduction steps.
- Recommended fixes.

---

## Tools Used by Pen Testers

### Network / Recon
- **Nmap**: port + service discovery.
- **Masscan**: faster Nmap.
- **Amass / Sublist3r**: subdomain enumeration.
- **Shodan / Censys**: search engines for exposed services.

### Web Application
- **Burp Suite** (Pro / Community): intercepting proxy, scanner, fuzzer. Industry standard.
- **OWASP ZAP**: open-source alternative.
- **Postman**: manual API testing.
- **Caido**: modern Burp alternative.

### Vulnerability Scanning
- **Nessus**: commercial.
- **OpenVAS**: open source.
- **Nuclei**: template-based fast scanner.

### Exploitation
- **Metasploit**: exploit framework.
- **SQLmap**: automated SQL injection.
- **XSStrike**: XSS detection.

### Brute Force
- **Hydra**: protocol brute-force.
- **John the Ripper**: password cracking.
- **Hashcat**: GPU-accelerated.

### Mobile
- **Frida**: dynamic instrumentation.
- **MobSF**: mobile app testing.

---

## API-Specific Testing

For REST/GraphQL APIs:

### Authentication
- Try without token → must return 401.
- Try with expired token → 401.
- Try with malformed token → 401.
- Try with another user's token → check what's accessible.

### Authorization
- Access /api/users/{other_id} → should 403 unless admin.
- Modify other user's data via PATCH.
- Hit /api/admin/* with non-admin token.

### Input fuzzing
- Send strings where numbers expected.
- Send huge payloads (10MB JSON).
- Deeply nested JSON (10000 levels).
- Special characters (null bytes, unicode).
- SQL injection in every field.
- XSS in every field.

### Rate limiting
- 1000 requests/sec to login endpoint.
- Check for IP-based block.

### IDOR (Insecure Direct Object Reference)
```
GET /api/orders/123 → your order
GET /api/orders/124 → someone else's order? Should 403.
```

### Mass assignment
```
PATCH /api/users/me
Body: {"name": "Alice", "is_admin": true}
```
Should ignore is_admin (not in allowed fields).

---

## GraphQL Testing

### Introspection
```graphql
{ __schema { types { name fields { name } } } }
```
Should be disabled in prod.

### Complex queries
Deeply nested → DoS test.

### Authorization
Field-level checks present?

### Batching attack
Many ops in one request → bypass rate limits.

---

## Common Findings (Real-World)

### Critical (must-fix immediately)
- SQL injection.
- Stored XSS.
- Authentication bypass.
- Remote code execution.
- Sensitive data exposure.

### High
- IDOR.
- SSRF.
- Privilege escalation.
- Weak crypto.

### Medium
- CORS misconfiguration.
- Information disclosure.
- Missing rate limits.

### Low
- Missing security headers.
- Verbose error messages.
- Outdated libraries (without known exploits).

### Informational
- Default fonts loaded from CDN.
- Stack traces sometimes shown.

---

## Reporting

### Format
```
Title: SQL Injection in /api/v1/search
Severity: Critical (CVSS 9.8)

Description:
The /api/v1/search endpoint passes the `q` parameter directly into a SQL query
without parameterization, allowing arbitrary SQL execution.

Reproduction:
GET /api/v1/search?q=test' UNION SELECT password FROM users--

Response:
{"results": [{"id": 1, "password_hash": "..."}, ...]}

Impact:
Attacker can exfiltrate entire user database including password hashes,
which can be cracked offline.

Recommendation:
Use parameterized queries via SQLAlchemy ORM or asyncpg:
  await db.fetch_all("SELECT * FROM ... WHERE name = $1", req.q)

References:
- OWASP A03:2021
- CWE-89
```

### Severity scoring (CVSS)
- 9.0-10.0: Critical
- 7.0-8.9: High
- 4.0-6.9: Medium
- 0.1-3.9: Low

Use CVSS 3.1 calculator.

---

## Remediation Workflow

1. Receive report → triage by severity.
2. Critical: emergency hotfix, deploy ASAP.
3. High: fix in current sprint.
4. Medium: next sprint or two.
5. Low: backlog.
6. Verify fixes (retest).
7. Track until 100% closed.

---

## Continuous Security

Pen test annually + before major releases. Between:

### Static Analysis (SAST)
- **Bandit** (Python).
- **Semgrep** (multi-language).
- **SonarQube**.

Run in CI on every PR.

### Dynamic Analysis (DAST)
- **OWASP ZAP** in CI (against staging).
- **Burp** scheduled scans.

### Dependency Scanning (SCA)
- **Snyk**, **Dependabot**, **pip-audit**.

### Secret Scanning
- **gitleaks**, **trufflehog**.

### Container Scanning
- **Trivy**, **Clair**, **Snyk Container**.

### Cloud Security
- **Prowler** (AWS).
- **CloudSploit**.
- **Wiz** (commercial).

### Runtime Monitoring
- **Falco**: K8s runtime threats.
- **Sysdig**.

---

## Bug Bounty Programs

Crowdsource security testing.

### Platforms
- **HackerOne**: largest.
- **Bugcrowd**.
- **Intigriti** (EU).

### Setup
- Scope clearly.
- Bounty levels by severity.
- Triage team.
- SLAs for response.

Cost: bounties + triage time. Benefit: continuous testing, edge cases caught.

---

## Compliance Drivers

Pen testing required for:
- **PCI DSS**: annually + after major changes.
- **HIPAA**: regularly.
- **SOC 2 Type 2**: annually.
- **ISO 27001**: regularly.
- **Various federal regulations**.

Use a qualified third party (CREST, OSCP-certified testers).

---

## Internal vs External Testers

### Internal team
- Knows the system deeply.
- Cheaper long-term.
- Bias risk (familiarity blindness).

### External firm
- Fresh perspective.
- Required for compliance.
- $$ — typically $10K-$100K per engagement.

Best: rotate (internal continuous + annual external).

---

## Notable Tester Certifications

- **OSCP** (Offensive Security Certified Professional): hands-on, respected.
- **CEH** (Certified Ethical Hacker): theoretical.
- **GPEN** (GIAC Penetration Tester).
- **OSCE** (advanced OSCP).
- **CRTP / CRTE** (red team).

---

## Common Mistakes (Defender Side)

### 1. Pen testing only annually
Attackers don't wait.

### 2. Not retesting after fixes
"We fixed it" — confirmed?

### 3. Ignoring low-severity findings
They aggregate; chained attacks.

### 4. No prod-equivalent staging
Tests miss prod-only issues.

### 5. Slow response to critical findings
Window of vulnerability widens.

### 6. No post-mortem on findings
Pattern: same class of bug keeps appearing.

---

## Common Mistakes (Tester Side)

### 1. No scope agreement
Legal trouble.

### 2. Destructive actions in prod
Take down site, lose data.

### 3. Generic report
"Found XSS." Where? How to reproduce? Fix?

### 4. Out-of-scope testing
Privacy / legal violation.

---

## TL;DR

- Pen testing = authorized adversarial assessment.
- OWASP Top 10 is the core checklist.
- Burp Suite + Nmap + custom for web apps.
- Phases: recon → scan → exploit → post-exploit → report.
- Continuous: SAST/DAST/SCA in CI + annual pen test.
- Bug bounty for ongoing coverage.
- Required for PCI/SOC 2/HIPAA compliance.
- Report = severity + repro + recommendation.
- Fix critical immediately; retest after.
