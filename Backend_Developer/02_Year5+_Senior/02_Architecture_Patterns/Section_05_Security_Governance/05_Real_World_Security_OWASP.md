# Lecture 5: Real-World Security Scenarios — OWASP Top 10

> *"Security isn't theoretical. It's the same vulnerabilities breaching the news every week."*

**Section 5 — Security & Governance in Architecture**

---

## 🎯 Is Lecture Mein Kya Seekhenge?

- **Why vulnerabilities keep appearing** — complexity, speed, priority
- **What is OWASP Top 10** — industry-standard threat ranking
- **Walking through each of OWASP Top 10:**
  1. Broken Access Control
  2. Cryptographic Failures
  3. Injection
  4. Insecure Design
  5. Security Misconfiguration
  6. Vulnerable Components
  7. Authentication Failures
  8. Software/Data Integrity Failures
  9. Logging/Monitoring Failures
  10. Server-Side Request Forgery (SSRF)
- **Layered defenses** across the stack
- **OWASP as a workflow tool**
- **Real breaches & lessons**

---

## 1. Why Security Threats Keep Showing Up

### The Paradox

```
We've known about SQL injection since 1998.
Why is it still in the OWASP Top 10 in 2024?
```

### Reason 1: Software Complexity

```
Modern systems = MASSIVE complexity:
   ✗ Hundreds of microservices
   ✗ Thousands of third-party libraries
   ✗ Multiple cloud providers
   ✗ Multi-region deployments
   ✗ Many development teams
   
→ Easy to overlook security in one place.
```

### Reason 2: Speed of Development

```
"Move fast and break things" culture:
   ✗ Ship features fast
   ✗ Security review = bottleneck
   ✗ Catch issues "later"
   ✗ "Later" never comes
   
→ Security debt accumulates.
```

### Reason 3: Misunderstood Risk

```
Common mistakes:
   ✗ "Authentication is enough" (forgets authorization)
   ✗ "We're internal, no risk" (assumes trust)
   ✗ "We're a small target" (everyone is targeted now)
   ✗ "We'll fix it after launch" (never happens)
   
→ Wrong priorities = wrong defenses.
```

### Reason 4: Human Error

```
Despite all the tools:
   ✗ Engineer commits secret to git
   ✗ Admin uses weak password
   ✗ Developer clicks phishing link
   ✗ Ops misconfigures S3 bucket
   
→ Most breaches start with human error.
```

---

## 2. What Is OWASP Top 10?

### The Industry Standard

**OWASP = Open Worldwide Application Security Project**

The Top 10 = the most critical security risks facing web applications, data-driven.

### Updated Regularly

```
Major releases:
   ✓ 2003 (first version)
   ✓ 2007, 2010, 2013, 2017
   ✓ 2021 (current at time of writing)
   ✓ Updates every 3-4 years

Each update reflects:
   ✓ New threats emerging
   ✓ Industry trends
   ✓ Real-world breach data
```

### How It's Compiled

```
Based on:
   ✓ Data from thousands of real applications
   ✓ Survey of security experts
   ✓ Industry consultation
   ✓ Real CVE data

→ Not opinion. Data-driven priorities.
```

### Why It Matters

```
✓ Common language for security teams
✓ Compliance frameworks reference it
✓ Used by auditors
✓ Required for many certifications
✓ Foundation for secure SDLC
```

---

## 3. #1 — Broken Access Control

### What It Is

**Users access data or actions they shouldn't.**

### Statistics

```
🚨 Found in 94% of tested applications.
🚨 #1 risk for 2 cycles in a row.
🚨 Often the root cause of high-profile breaches.
```

### Real Examples

```
1. HORIZONTAL PRIVILEGE ESCALATION
   GET /users/123/orders → my orders
   GET /users/456/orders → someone else's orders (BUG!)

2. VERTICAL PRIVILEGE ESCALATION
   Regular user calls admin endpoint
   /api/admin/users → returns user list (BUG!)

3. INSECURE DIRECT OBJECT REFERENCE (IDOR)
   /documents/?id=42 → my doc
   /documents/?id=43 → someone else's doc (BUG!)

4. METADATA MANIPULATION
   Cookie: role=user → Cookie: role=admin (BUG accepts it!)

5. CORS MISCONFIGURATION
   Access-Control-Allow-Origin: *
   → Any site can call your API on user's behalf
```

### Why It's So Common

```
✗ Checking permissions only in UI (client-side)
✗ Forgetting to check ownership on resource
✗ Trusting hidden form fields
✗ Default-allow architecture
✗ Inconsistent enforcement across endpoints
```

### Mitigations

```
✓ Enforce ALL permissions SERVER-SIDE
✓ Deny by default, allow explicitly
✓ Check object ownership on every request
✓ Use centralized authorization (not scattered)
✓ Test access controls with multiple user types
✓ Audit log all access decisions
```

### Real Breach: Facebook (2018)

```
50 million accounts compromised.
Root cause: Access control flaw in "View As" feature.
Allowed attackers to take over any user account.
```

---

## 4. #2 — Cryptographic Failures

### What It Is

**Failure to protect data through encryption.**

### Previously Called

"Sensitive Data Exposure" (renamed in 2021 to emphasize root cause)

### Common Failures

```
1. SENDING SENSITIVE DATA OVER HTTP
   ✗ Login over plain HTTP
   ✗ Mixed content on HTTPS pages

2. WEAK ENCRYPTION ALGORITHMS
   ✗ MD5, SHA1 for hashing
   ✗ DES, 3DES for encryption
   ✗ ECB mode (deterministic)

3. WEAK KEYS
   ✗ Short keys (RSA-1024)
   ✗ Hardcoded keys
   ✗ Reused keys across systems

4. NO ENCRYPTION AT REST
   ✗ Unencrypted databases
   ✗ Plaintext passwords
   ✗ Sensitive data in S3 buckets

5. MISCONFIGURATIONS
   ✗ Outdated TLS (1.0, 1.1)
   ✗ Weak cipher suites
   ✗ No certificate pinning on mobile
```

### Real Examples

```
🚨 Equifax 2017 Breach (147M people)
   - Did not encrypt sensitive data at rest
   - Weak TLS configuration

🚨 Adobe 2013 Breach (153M users)
   - Stored passwords with weak encryption (3DES ECB)
   - Same encrypted password = same plaintext

🚨 Marriott 2018 Breach (500M guests)
   - Some data encrypted, some plaintext
   - Encryption keys also stolen
```

### Mitigations

```
✓ TLS 1.2+ everywhere (1.3 preferred)
✓ Strong hashing: bcrypt, scrypt, Argon2 for passwords
✓ Strong encryption: AES-256-GCM, ChaCha20-Poly1305
✓ Use libraries, don't roll your own
✓ Key management with KMS/HSM
✓ Encrypt at rest (DB, files, backups)
✓ Encrypt in transit (TLS everywhere)
✓ Don't log/store sensitive data unnecessarily
✓ Use envelope encryption for large data
```

### Quick Reference: Modern Crypto

```
For passwords: 
   ✓ Argon2id (best)
   ✓ bcrypt (still good)
   ✗ MD5, SHA-256 alone

For symmetric encryption:
   ✓ AES-256-GCM
   ✓ ChaCha20-Poly1305

For asymmetric:
   ✓ RSA-2048 minimum (4096 better)
   ✓ Curve25519 / Ed25519

For TLS:
   ✓ TLS 1.3 (or 1.2 minimum)
   ✗ TLS 1.0, 1.1, SSL
```

---

## 5. #3 — Injection

### What It Is

**Untrusted input interpreted as a command or query.**

### Types

```
1. SQL INJECTION
   user_input = "1' OR '1'='1"
   SELECT * FROM users WHERE id = '1' OR '1'='1'
   → Returns ALL users!

2. NOSQL INJECTION
   {"username": {"$ne": null}, "password": {"$ne": null}}
   → Bypasses authentication

3. COMMAND INJECTION
   filename = "doc.pdf; rm -rf /"
   os.system(f"convert {filename}")
   → Runs malicious command

4. LDAP INJECTION
   user_input = "*)(uid=*"
   → Returns all LDAP users

5. XML EXTERNAL ENTITY (XXE)
   <!DOCTYPE foo [<!ENTITY xxe SYSTEM "file:///etc/passwd">]>
   → Reads server files
```

### Why Still Common

```
✗ Developers concatenate strings
✗ ORMs don't fully protect (especially raw queries)
✗ New languages/frameworks repeat old mistakes
✗ Lack of input validation
✗ Trust in "internal" inputs
```

### Real Examples

```
🚨 Heartland Payment Systems (2008)
   SQL injection → 130M credit card records stolen

🚨 TalkTalk (2015)
   SQL injection → 4M customer records

🚨 Sony Pictures (2014)
   Multiple injection points contributed to massive breach
```

### Mitigations

```
✓ PARAMETERIZED QUERIES (never concatenate!)
   ❌ f"SELECT * FROM users WHERE id = {user_id}"
   ✅ "SELECT * FROM users WHERE id = %s", (user_id,)

✓ Use ORM properly (avoid raw queries)
✓ Input validation (whitelist allowed values)
✓ Output encoding (context-aware)
✓ Stored procedures (when configured securely)
✓ Least privilege DB users
✓ WAF as defense in depth
✓ Code review focused on data flow
```

### Code Examples

```python
# ❌ DON'T - SQL Injection vulnerable
def get_user(user_id):
    query = f"SELECT * FROM users WHERE id = {user_id}"
    return db.execute(query)

# ✅ DO - Parameterized
def get_user(user_id):
    query = "SELECT * FROM users WHERE id = %s"
    return db.execute(query, (user_id,))

# ✅ Better - ORM
def get_user(user_id):
    return User.objects.filter(id=user_id).first()
```

---

## 6. #4 — Insecure Design

### What It Is

**Flaws baked into architecture, not just code bugs.**

### Why It's Different

```
Coding bugs:
   ✗ Specific lines of bad code
   ✓ Can be patched

Design flaws:
   ✗ Whole system architecture has issues
   ✗ Patching = redesign
   ✗ Much harder to fix later

→ Get the design RIGHT from the start.
```

### Examples of Insecure Design

```
1. NO RATE LIMITING
   → Brute force passwords
   → Abuse APIs
   → Cost-amplification attacks

2. NO ABUSE PROTECTION FOR WORKFLOWS
   → Sign up bots
   → Coupon code stuffing
   → Account enumeration

3. BUSINESS LOGIC FLAWS
   → Negative quantities in orders
   → Race conditions in money transfers
   → Skipping payment workflow steps

4. TRUSTING CLIENT-SIDE LOGIC
   → Discount calculated in browser
   → Permissions checked in UI

5. INSECURE WORKFLOWS
   → Password reset doesn't expire
   → MFA can be bypassed
```

### Mitigations

```
✓ THREAT MODEL during design phase
✓ Apply secure design patterns (Zero Trust, etc.)
✓ Reference architectures + checklists
✓ Security architect involvement
✓ Misuse case planning
✓ Test for abuse, not just happy path
✓ Build security into SDLC, not after
```

### Threat Modeling Reminder

```
For every new feature, ask:
   ✓ What's the most valuable asset here?
   ✓ Who would want to attack it?
   ✓ How could they attack it?
   ✓ What if they succeed?
   ✓ How do we prevent + detect + respond?
```

---

## 7. #5 — Security Misconfiguration

### What It Is

**System left in insecure state due to defaults, mistakes, or oversights.**

### Most Common Misconfigurations

```
1. DEFAULT CREDENTIALS LEFT
   admin/admin, root/password
   "I'll change it later"

2. UNNECESSARY FEATURES ENABLED
   Sample apps, debug ports, demo accounts

3. VERBOSE ERROR MESSAGES
   Stack traces revealing implementation
   "Password column 'pwd' not found in users table"

4. MISSING SECURITY HEADERS
   No CSP, no HSTS, no X-Frame-Options

5. UNNECESSARY EXPOSURE
   Database directly on internet
   Admin panel publicly accessible
   .git/ directory served
   /robots.txt revealing internal paths

6. CLOUD MISCONFIGURATIONS
   Public S3 buckets
   Open security groups
   IAM roles too permissive

7. OUT-OF-DATE SOFTWARE
   Patches not applied
   Container images stale
```

### Real Examples

```
🚨 Capital One (2019, 100M records)
   - Misconfigured WAF + SSRF
   - Accessed sensitive S3 data

🚨 Booking.com Customers (many incidents)
   - Open Elasticsearch on internet
   - Public MongoDB instances

🚨 Verizon Partner (2017, 14M records)
   - Public S3 bucket
```

### Mitigations

```
✓ Security baselines (CIS Benchmarks)
✓ Infrastructure as Code (versioned, reviewed)
✓ Automated config scanning (Checkov, tfsec)
✓ Default-secure architecture
✓ Regular configuration audits
✓ Cloud Security Posture Management (CSPM)
✓ Disable unused features
✓ Generic error messages in production
✓ Security headers (CSP, HSTS, etc.)
```

### Essential Security Headers

```
Strict-Transport-Security: max-age=31536000; includeSubDomains
Content-Security-Policy: default-src 'self'
X-Frame-Options: DENY
X-Content-Type-Options: nosniff
Referrer-Policy: strict-origin-when-cross-origin
Permissions-Policy: geolocation=(), camera=(), microphone=()
```

---

## 8. #6 — Vulnerable & Outdated Components

### What It Is

**Using software with known vulnerabilities.**

### Why It's So Common

```
Modern apps = MASSIVE dependency trees:
   ✓ Direct dependencies: 50-100
   ✓ Transitive (indirect): 500-5000
   ✓ Updated constantly
   ✓ Some unmaintained
   
→ Hard to keep track.
```

### Real Examples

```
🚨 Equifax 2017 (147M records)
   - Apache Struts CVE-2017-5638
   - Patch available for 2+ months
   - Equifax didn't apply it
   - Cost: $700M+ in damages

🚨 Log4Shell (CVE-2021-44228)
   - Log4j 2.x vulnerability
   - Affected basically every Java app
   - Days of patching across industry

🚨 Heartbleed (CVE-2014-0160)
   - OpenSSL vulnerability
   - 2 years before disclosure
   - Millions of servers vulnerable
```

### Mitigations

```
✓ Inventory all dependencies (SBOM)
✓ Automated vulnerability scanning
   - Snyk, Dependabot, Renovate
   - GitHub Security Advisories
✓ Patch promptly (especially CRITICAL CVEs)
✓ Remove unused dependencies
✓ Pin versions, but update them
✓ Use signed packages where possible
✓ Stay informed (security mailing lists)
```

### Modern Tooling

```
✓ GitHub Dependabot (free)
✓ Snyk (free + paid tiers)
✓ Renovate Bot (open-source)
✓ OWASP Dependency Check
✓ JFrog Xray (commercial)
```

---

## 9. #7 — Authentication Failures

### What It Is

**Weak or improperly implemented authentication.**

### Common Issues

```
1. WEAK PASSWORD POLICY
   - 6 characters minimum
   - No complexity requirements
   - "password123" allowed

2. NO BRUTE FORCE PROTECTION
   - No rate limit
   - No account lockout
   - No CAPTCHA

3. WEAK SESSION MANAGEMENT
   - Long-lived sessions
   - Session IDs in URL
   - Sessions don't expire after logout

4. NO MFA
   - Single factor only
   - Especially bad for admin accounts

5. CREDENTIAL STUFFING VULNERABILITY
   - Reused breached passwords
   - No check against HIBP

6. INSECURE PASSWORD RECOVERY
   - Security questions easily guessed
   - Email reset without verification
   - Password reset link doesn't expire
```

### Real Examples

```
🚨 Twitter 2020 hack
   - Internal tool with weak admin auth
   - Compromise via phishing
   - Hijacked celebrity accounts

🚨 LinkedIn 2012 breach (164M)
   - Weak password storage
   - Slow detection

🚨 Many SaaS breaches
   - Credential stuffing
   - No MFA on admin accounts
```

### Mitigations

```
✓ Strong password policies (NIST 800-63B guidelines):
   - 8 characters minimum (length > complexity!)
   - Check against breach databases (HIBP)
   - No periodic rotation (unless compromised)

✓ MFA mandatory for:
   - Admins
   - Sensitive operations
   - Optional for users (but encouraged)

✓ Rate limiting:
   - Per IP, per user
   - Account lockout after N failures
   - CAPTCHAs after suspicious activity

✓ Secure session management:
   - Short access tokens (15 min)
   - Secure cookies (HTTP-only, Secure)
   - Invalidate on logout
   - Rotate session IDs on privilege change

✓ Use established providers:
   - Auth0, Okta, Azure AD
   - Don't build your own auth!
```

---

## 10. #8 — Software & Data Integrity Failures

### What It Is

**Trusting code/data without verifying integrity.**

### Common Issues

```
1. UNSIGNED UPDATES
   ✗ Auto-updater downloads + runs code
   ✗ No signature verification
   ✗ Man-in-the-middle = malicious code execution

2. UNTRUSTED DEPENDENCIES
   ✗ Public package registries (npm, PyPI)
   ✗ Compromised packages
   ✗ Typosquatting attacks

3. INSECURE CI/CD PIPELINE
   ✗ Untrusted source code committed → deployed
   ✗ No code review enforcement
   ✗ Secrets exposed in pipeline

4. DESERIALIZATION OF UNTRUSTED DATA
   ✗ Pickling Python objects from API
   ✗ Java serialization vulnerabilities
   ✗ Can lead to remote code execution
```

### Real Examples

```
🚨 SolarWinds (2020)
   - Compromised CI/CD pipeline
   - Malicious code in software updates
   - 18,000 customers affected
   - Including US government agencies

🚨 event-stream NPM package (2018)
   - Maintainer added malicious dependency
   - Stole crypto wallet keys
   - 8M weekly downloads

🚨 Codecov (2021)
   - CI tool compromised
   - Leaked customer environment variables
   - Used to attack downstream
```

### Mitigations

```
✓ Sign all code releases (Cosign, GPG)
✓ Verify signatures on installation
✓ Use lockfiles (package-lock.json, etc.)
✓ Software Bill of Materials (SBOM)
✓ Audit dependencies before adding
✓ Use trusted package registries
✓ Code review enforcement
✓ Multi-step approval for deploys
✓ Avoid deserializing untrusted data
✓ Trusted Build environments
✓ Use SLSA framework
```

---

## 11. #9 — Security Logging & Monitoring Failures

### What It Is

**Can't detect or respond to attacks because you can't see them.**

### Why It Matters

```
Average time to detect a breach: 207 days (IBM 2023).
Average time to contain: 70 days.
277 days total.

With good monitoring: detect within hours/days.
```

### Common Failures

```
1. NO LOGS FOR SECURITY EVENTS
   ✗ Logins not logged
   ✗ Access failures ignored
   ✗ Admin actions untracked

2. LOGS NOT MONITORED
   ✗ Stored but never reviewed
   ✗ No alerts configured
   ✗ No real-time analysis

3. LOGS WITHOUT CONTEXT
   ✗ No correlation IDs
   ✗ Missing user/action details
   ✗ Hard to investigate

4. LOGS NOT SECURED
   ✗ Tamperable
   ✗ Stored on same system as app
   ✗ Sensitive data not scrubbed

5. NO INCIDENT RESPONSE
   ✗ Detection but no action
   ✗ No runbook
   ✗ No team trained
```

### Real Examples

```
🚨 Equifax (2017)
   - Network monitoring tool's expired cert
   - Couldn't see attackers exfiltrate data
   - 76 days undetected

🚨 Target (2013)
   - Alerts WERE triggered
   - But ignored by staff
   - 40M credit cards stolen
```

### What to Log

```
Security-relevant events:
   ✓ Authentication (success + failure)
   ✓ Authorization (permission denied)
   ✓ Account changes (creation, deletion, role change)
   ✓ Sensitive data access
   ✓ Configuration changes
   ✓ Privilege escalation
   ✓ Unusual patterns (rate, geography)
```

### Mitigations

```
✓ Centralized log aggregation (ELK, Splunk, Datadog)
✓ Structured logging (JSON)
✓ Include correlation IDs across services
✓ SIEM for analysis
✓ Real-time alerting on suspicious patterns
✓ Retention for forensics (90+ days)
✓ Tamper-evident logs (append-only)
✓ Regular log review
✓ Incident response runbooks
✓ Practice incident response (game days)
```

---

## 12. #10 — Server-Side Request Forgery (SSRF)

### What It Is

**Application is tricked into making requests on attacker's behalf.**

### How It Works

```
App accepts URL from user:
   POST /import
   {"url": "https://my-data.com/data.json"}

App fetches the URL → returns content to user.

Attacker sends:
   {"url": "http://169.254.169.254/latest/meta-data/"}
   
   ↑ AWS metadata service (only accessible from EC2 instance)
   → Returns AWS credentials!
   
Or:
   {"url": "http://internal-service:8080/admin"}
   → Accesses internal-only service!
```

### Why It's Bad

```
✗ Bypasses firewalls (request comes from "trusted" server)
✗ Accesses cloud metadata services
✗ Probes internal network
✗ Can pivot to internal services
✗ Can read local files via file:// scheme
```

### Real Example

```
🚨 Capital One (2019)
   - SSRF in WAF
   - Accessed AWS metadata service
   - Got temporary credentials
   - Exfiltrated 100M customer records
   - $190M fine
```

### Mitigations

```
✓ URL allowlist (specific domains only)
✓ Block private IP ranges:
   - 10.0.0.0/8
   - 172.16.0.0/12
   - 192.168.0.0/16
   - 169.254.0.0/16 (cloud metadata!)
   - 127.0.0.0/8

✓ Block dangerous schemes:
   - file://
   - ftp://
   - gopher://

✓ Don't follow redirects (or limit)
✓ Use IMDSv2 (requires session token)
✓ Network segmentation (deny internal access)
✓ DNS rebinding protection
```

### Code Example

```python
"""SSRF-safe URL fetching"""
import ipaddress
import socket
from urllib.parse import urlparse

ALLOWED_SCHEMES = {"http", "https"}
ALLOWED_HOSTS = {"trusted-api.com", "*.partner.com"}

def is_safe_url(url: str) -> bool:
    parsed = urlparse(url)
    
    # Check scheme
    if parsed.scheme not in ALLOWED_SCHEMES:
        return False
    
    # Resolve hostname
    try:
        ip = socket.gethostbyname(parsed.hostname)
    except socket.error:
        return False
    
    # Block private/internal IPs
    ip_obj = ipaddress.ip_address(ip)
    if ip_obj.is_private or ip_obj.is_loopback or ip_obj.is_link_local:
        return False
    
    # Block AWS metadata
    if ip == "169.254.169.254":
        return False
    
    # Allowlist check
    if parsed.hostname not in ALLOWED_HOSTS:
        return False
    
    return True

# Usage
def fetch_url(url):
    if not is_safe_url(url):
        raise ValueError("URL not allowed")
    return requests.get(url, timeout=10, allow_redirects=False)
```

---

## 13. Layered Defenses Across the Stack

### The OWASP Top 10 Maps to All Layers

```
Layer 1: UI / Frontend
   ✓ Input validation (defense in depth)
   ✓ Output encoding (XSS prevention)
   ✓ CSP headers
   ✓ Secure cookies

Layer 2: API Gateway
   ✓ Authentication
   ✓ Authorization
   ✓ Rate limiting
   ✓ Request validation
   ✓ WAF rules

Layer 3: Application Logic
   ✓ Business logic validation
   ✓ Object-level authorization
   ✓ Idempotency
   ✓ Input sanitization

Layer 4: Data Access
   ✓ Parameterized queries
   ✓ Least privilege DB users
   ✓ Query timeouts
   ✓ Sensitive data encryption

Layer 5: Storage
   ✓ Encryption at rest
   ✓ Access controls
   ✓ Backup encryption
   ✓ Tokenization

Layer 6: Network
   ✓ TLS everywhere
   ✓ mTLS for service-to-service
   ✓ Network segmentation
   ✓ Egress filtering (SSRF prevention)

Layer 7: Monitoring
   ✓ Centralized logging
   ✓ SIEM analysis
   ✓ Real-time alerts
   ✓ Incident response
```

### Defense in Depth

```
✓ One layer fails → others catch the attack
✓ Attacker must breach multiple defenses
✓ Time to respond increases
✓ Cost of attack increases
```

---

## 14. OWASP as a Workflow Tool

### Make It Part of Your Process

```
During DESIGN:
   ✓ Threat model new features
   ✓ Map to OWASP Top 10 risks
   ✓ Plan mitigations

During CODE:
   ✓ Static analysis (SAST)
   ✓ Code review with OWASP lens
   ✓ Dependency scanning

During TEST:
   ✓ DAST (Dynamic testing)
   ✓ Penetration testing
   ✓ Bug bounty

During DEPLOY:
   ✓ Config validation
   ✓ Secrets scanning
   ✓ Container scanning

During OPERATE:
   ✓ Monitor for attacks
   ✓ Patch vulnerabilities
   ✓ Incident response
```

### Sprint Planning Integration

```
For every story, ask:
   "Does this introduce any OWASP Top 10 risk?"

If YES → add security tasks:
   ✓ Review with security team
   ✓ Add test cases for security
   ✓ Update threat model
```

### CI/CD Integration

```yaml
# Security gates in every pipeline
stages:
  - secret_scan      # Pre-commit, in CI
  - sast             # Static analysis
  - dependency_scan  # SCA
  - build
  - container_scan   # Image security
  - deploy_staging
  - dast             # Dynamic testing
  - deploy_prod      # Only if all pass!
```

---

## 15. The OWASP Top 10 Cheat Sheet

```
┌────────────────────────────────────────────────────────────────┐
│  #  RISK                          | KEY DEFENSE                 │
├────────────────────────────────────────────────────────────────┤
│  1  Broken Access Control         | Server-side checks ALWAYS   │
│  2  Cryptographic Failures        | TLS + modern crypto         │
│  3  Injection                     | Parameterized queries       │
│  4  Insecure Design               | Threat model upfront        │
│  5  Security Misconfiguration     | IaC + automated scanning    │
│  6  Vulnerable Components         | Dependency scanning + patch │
│  7  Authentication Failures       | MFA + rate limit + strong PW│
│  8  Data Integrity Failures       | Signed code + lockfiles     │
│  9  Logging/Monitoring Failures   | Centralized logs + alerts   │
│  10 SSRF                          | URL allowlist + IP blocks   │
└────────────────────────────────────────────────────────────────┘
```

---

## 16. Summary — Key Takeaways

```
┌──────────────────────────────────────────────────────────────┐
│  ✅ OWASP Top 10 = data-driven security priorities            │
│  ✅ Broken Access Control is the #1 risk (94% of apps!)       │
│  ✅ Injection still common despite 25+ years of awareness     │
│  ✅ Insecure Design = patching can't fix it                   │
│  ✅ Misconfigurations cause most breaches                     │
│  ✅ Vulnerable components = supply chain attacks              │
│  ✅ Authentication failures + missing MFA                     │
│  ✅ CI/CD pipeline integrity matters                          │
│  ✅ Without logging, breaches go undetected for months        │
│  ✅ SSRF = under-rated, used in major breaches                │
└──────────────────────────────────────────────────────────────┘
```

### The Universal Rules

```
1. Server-side authorization on EVERY endpoint
2. Parameterized queries, NEVER concatenation
3. TLS everywhere, modern crypto only
4. Threat model before coding
5. Default-secure configurations
6. Patch dependencies regularly
7. MFA mandatory for admins
8. Sign everything (code, deployments)
9. Log security events + alert in real-time
10. Validate URLs to prevent SSRF
```

---

## 🎬 Section Complete!

Congratulations! You've completed **Section 5: Security & Governance in Architecture**!

### What You've Learned

```
✓ Zero Trust architecture principles
✓ OAuth 2.0 + OpenID Connect flows
✓ API + service security (mTLS, JWT, keys)
✓ Secrets and token management
✓ OWASP Top 10 in practice
```

### Practical file: [05_Practical_Hands_On.md](05_Practical_Hands_On.md)

---

## 🚀 What's Next?

Continue with:
- **Section 6**: Event-Driven & Reactive Systems
- **Section 7**: Cloud-Native & Scalable Architecture
- **Section 8**: UI Architecture Patterns
- **Section 9**: Architectural Decision-Making
- **Section 10**: Conclusion & Next Steps

---

## 📚 References

- **OWASP Top 10 2021** — owasp.org/Top10
- OWASP Application Security Verification Standard (ASVS)
- *Threat Modeling: Designing for Security* — Adam Shostack
- *Web Application Security* — Andrew Hoffman
- *Real-World Bug Hunting* — Peter Yaworski
- NIST SP 800-53 — Security Controls
