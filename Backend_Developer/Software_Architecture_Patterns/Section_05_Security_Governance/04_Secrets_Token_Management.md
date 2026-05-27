# Lecture 4: Secrets and Token Management

> *"No secret should live forever."*

**Section 5 — Security & Governance in Architecture**

---

## 🎯 Is Lecture Mein Kya Seekhenge?

- **Why secrets management matters** — leaks = instant compromise
- **Types of secrets** in modern systems
- **Where to store secrets** — never in code!
- **Vault services** — HashiCorp Vault, AWS Secrets Manager
- **Secret rotation** — short-lived secrets
- **Encryption at rest + in transit**
- **Handling expiring tokens**
- **Refresh token strategies** — rotation, secure storage
- **Detecting secret leaks** — scanning, prevention
- **Best practices** — recap and integration

---

## 1. Why Secrets Management Matters

### What Are Secrets?

```
Anything that grants access or proves identity:
   ✓ API keys
   ✓ Database credentials
   ✓ Access tokens (OAuth)
   ✓ Refresh tokens
   ✓ Cryptographic keys (signing, encryption)
   ✓ Certificates + private keys
   ✓ Service account credentials
   ✓ SSH keys
   ✓ Encryption keys
   ✓ Webhook secrets
```

### The Real Risk

```
Secret leak = instant compromise
   ✗ Attacker impersonates service
   ✗ Reads/modifies sensitive data
   ✗ Moves laterally through system
   ✗ Often undetected for months

Examples of catastrophic leaks:
   • AWS keys in public GitHub repo → $50k cloud bill
   • Slack tokens leaked → workspace dumps
   • DB credentials in .env in repo → data breach
   • SSH keys in image → instance takeover
```

### Why Secret Leaks Happen

```
Common causes (mostly HUMAN ERROR):
   ✗ Hardcoded in source code
   ✗ Committed to git (even "private" repos)
   ✗ In environment files in production
   ✗ In container images
   ✗ In log files
   ✗ Shared via Slack/email
   ✗ Forgotten in old branches
   ✗ Public S3 buckets / wiki pages

→ It's NOT a tool problem. It's a process problem.
```

---

## 2. Types of Secrets

### Categorize Your Secrets

```
1. APPLICATION CREDENTIALS
   - Database passwords
   - API keys for third parties
   - Service account credentials

2. CRYPTOGRAPHIC MATERIAL
   - JWT signing keys
   - Encryption keys (AES, RSA)
   - TLS certificate private keys
   - SSH keys

3. SESSION TOKENS
   - OAuth access tokens
   - Refresh tokens
   - Session cookies

4. INFRASTRUCTURE SECRETS
   - Cloud credentials (AWS, Azure, GCP)
   - Kubernetes secrets
   - Container registry passwords
   - VPN credentials

5. WEBHOOK SECRETS
   - HMAC keys for signature verification
   - Shared secrets with partners
```

### Different Lifecycles

```
LONG-LIVED:
   - Encryption keys (months/years)
   - Root CA certificates (years)
   - SSH keys (months)

MEDIUM-LIVED:
   - API keys (30-90 days, rotated)
   - Database passwords (rotated quarterly)

SHORT-LIVED:
   - JWT access tokens (5-15 minutes)
   - OAuth tokens (hours)
   - Session tokens (varies)

EPHEMERAL:
   - K8s pod service account tokens
   - One-time codes
   - CSRF tokens
```

---

## 3. Where NOT to Store Secrets

### Anti-Pattern 1: In Code

```
❌ DON'T:
   DATABASE_URL = "postgresql://admin:password123@prod-db/myapp"
   STRIPE_SECRET = "sk_live_abc..."
   
   git push origin main
   
   → Secrets in git history FOREVER
   → Even if deleted, still in history
```

### Anti-Pattern 2: In Config Files in Repo

```
❌ DON'T:
   # config.json
   {
     "db_password": "secret123",
     "api_key": "key_xyz"
   }
   
   Even .gitignore-d files leak:
   - Accidental commits
   - Different OS file structure
   - Shared via screenshots
```

### Anti-Pattern 3: In Container Images

```
❌ DON'T:
   FROM python:3.10
   ENV API_KEY="secret_value"
   COPY .env /app/.env
   
   → Anyone who pulls image has secrets
   → Visible in image history
```

### Anti-Pattern 4: In Environment Variables (sometimes)

```
⚠️ BE CAREFUL:
   export API_KEY="..."
   
   Pros: Common, simple
   Cons:
   - Visible in `ps aux` output
   - Logged on errors
   - Leaked in stack traces
   - Visible to processes spawning children
```

### Anti-Pattern 5: In Plaintext at Rest

```
❌ DON'T:
   /opt/app/secrets.txt   # plaintext file
   redis://localhost      # secrets in cache without encryption
   
   → Anyone with file system access = full compromise
```

---

## 4. Where to Store Secrets

### Best Practice 1: Use a Dedicated Vault

```
✓ HashiCorp Vault (self-hosted, multi-cloud)
✓ AWS Secrets Manager
✓ Azure Key Vault
✓ GCP Secret Manager
✓ Doppler (developer-friendly)
✓ 1Password Secrets Automation
```

### Best Practice 2: Encrypted at Rest

```
✓ Vault encrypts internally
✓ Disk-level encryption (EBS encryption, etc.)
✓ Database-level encryption (TDE)
✓ Application-level encryption for ultra-sensitive
```

### Best Practice 3: Access Control

```
✓ Fine-grained policies (per-secret access)
✓ Identity-based (not network-based)
✓ Audit logs (who accessed what when)
✓ Least privilege
```

### Best Practice 4: Just-in-Time Access

```
Don't deploy with secrets in environment.

Instead:
   ✓ App starts up
   ✓ Authenticates to vault (via workload identity)
   ✓ Fetches secrets at startup
   ✓ Re-fetches on rotation
   ✓ Secrets exist only in app memory
```

---

## 5. Vault Services Deep Dive

### HashiCorp Vault

```
Most popular open-source secrets manager.

Features:
   ✓ Secrets engines (KV, database creds, PKI, AWS, etc.)
   ✓ Dynamic secrets (generated on demand)
   ✓ Encryption as a service
   ✓ Lease + revocation
   ✓ Detailed audit logs
   ✓ HA + multi-region

Use cases:
   ✓ Multi-cloud
   ✓ On-premises + cloud hybrid
   ✓ Need fine-grained control
```

### AWS Secrets Manager

```
Native to AWS.

Features:
   ✓ Automatic rotation
   ✓ Integration with IAM
   ✓ Encryption with KMS
   ✓ Cross-region replication

Use cases:
   ✓ AWS-only workloads
   ✓ Simple setup
```

### Azure Key Vault

```
Azure equivalent.

Features:
   ✓ Keys, secrets, certificates
   ✓ HSM-backed option
   ✓ RBAC integration
   ✓ Soft delete + purge protection
```

### Comparison

```
┌────────────────────┬──────────────┬──────────────┬──────────────┐
│  FEATURE            │  Vault        │  AWS SM       │  Azure KV    │
├────────────────────┼──────────────┼──────────────┼──────────────┤
│  Self-hosted        │  ✓             │  ✗             │  ✗             │
│  Multi-cloud        │  ✓             │  ✗             │  ✗             │
│  Dynamic secrets    │  ✓             │  Limited       │  Limited       │
│  Auto rotation      │  ✓ (via Lambda)│  ✓             │  ✓             │
│  Cost               │  Self-host    │  Per secret    │  Per operation│
│  Learning curve     │  Higher        │  Lower         │  Lower         │
└────────────────────┴──────────────┴──────────────┴──────────────┘
```

---

## 6. Secret Rotation

### Why Rotate?

```
"No secret should live forever."

Reasons:
   ✓ Limits exposure if compromised
   ✓ Reduces blast radius
   ✓ Forces detection of stale dependencies
   ✓ Compliance requirements (PCI-DSS, etc.)
```

### Rotation Frequencies

```
Typical schedules:
   Database credentials:   30-90 days
   API keys:               60-90 days
   Signing keys:           90-180 days
   TLS certificates:       90 days (Let's Encrypt!)
   SSH keys:               180-365 days
   Root CA:                Years (but harder to rotate!)
```

### Manual vs Automatic Rotation

```
MANUAL (BAD):
   ✗ Engineer rotates → updates apps → restarts
   ✗ Error-prone
   ✗ Skipped or delayed
   ✗ "I'll do it later" → never done

AUTOMATIC (GOOD):
   ✓ Vault rotates on schedule
   ✓ Apps fetch new on next request
   ✓ No downtime
   ✓ Consistent across system
```

### Dynamic Secrets (The Best Approach)

```
Vault GENERATES secrets on-demand:

   App: "Vault, I need DB access"
   Vault: "Here's a credential, valid for 1 hour"
   
   App uses it → 1 hour later → credential auto-revoked
   No long-lived secrets at all!

Benefits:
   ✓ Every credential is unique
   ✓ Short-lived (low blast radius)
   ✓ Auto-revoked
   ✓ Full audit trail
```

### Rotation Patterns

```
1. ROLLING ROTATION
   Old secret + new secret both work during transition
   Apps gradually pick up new
   Old eventually deactivated

2. BLUE-GREEN
   Deploy new secrets
   Switch traffic to apps using new
   Deactivate old

3. INSTANT
   Generate new, deactivate old
   ✗ Risk of downtime if any app is slow to update
```

---

## 7. Encryption: At Rest + In Transit

### Encryption at Rest

```
Where secrets live:
   ✓ Database
   ✓ Filesystem
   ✓ Backups
   ✓ Container volumes
   ✓ Object storage (S3, etc.)

ALL must be encrypted!

Levels:
   1. Disk encryption (EBS, LUKS) - protects against stolen disk
   2. Database encryption (TDE) - protects DB files
   3. Application encryption - protects from DB admin
   4. Field-level encryption - protects specific fields
```

### Encryption in Transit

```
Anywhere secrets move:
   ✓ App ↔ Vault
   ✓ App ↔ Database
   ✓ Service ↔ Service
   ✓ Client ↔ Server

ALL must use TLS!

Modern requirements:
   ✓ TLS 1.2 minimum (TLS 1.3 preferred)
   ✓ Strong cipher suites
   ✓ Certificate validation
   ✓ HSTS for web
```

### Why Both Matter

```
Encryption at rest WITHOUT transit:
   - DB encrypted, but secrets sent over plain HTTP
   - Attacker sniffs network → captures secrets

Encryption in transit WITHOUT at rest:
   - HTTPS everywhere, but DB unencrypted
   - Backup stolen → all secrets exposed

→ NEED BOTH
```

### Key Management

```
Encryption keys also need protection!

Best practices:
   ✓ Use Key Management Service (KMS)
   ✓ Hardware Security Module (HSM) for high-security
   ✓ Envelope encryption (data key encrypted by master key)
   ✓ Key rotation
   ✓ Separate key management from data storage
```

---

## 8. Handling Expiring Tokens

### Why Tokens Expire

```
Short-lived tokens = better security
   ✓ Limit window of misuse
   ✓ Force re-authentication
   ✓ Reduce blast radius

Typical lifetimes:
   ✓ Access tokens: 5-60 minutes
   ✓ Refresh tokens: hours to days
   ✓ Session tokens: hours
```

### Detecting Expiration

```
Two ways to know token expired:

1. CHECK BEFORE USE (proactive)
   if now() >= token.expires_at - 30:  # 30s buffer
       refresh()

2. HANDLE 401 RESPONSE (reactive)
   try:
       response = call_api()
   except UnauthorizedError:
       refresh()
       retry()
```

### Best Practice: Both

```
Combined approach:
   1. Check proactively if you have expiry info
   2. Always handle 401 gracefully (token may be revoked)
   3. Refresh in background, don't disrupt user
```

### Avoid Hard Failure

```
❌ ANTI-PATTERN:
   if token_expired:
       logout_user()
       redirect_to_login()
   
   → Bad UX, user has to log in again

✅ BETTER:
   if token_expired:
       try:
           new_token = refresh()
           save_token(new_token)
           retry_original_request()
       except RefreshFailed:
           # Only THEN log out
           logout_user()
```

---

## 9. Refresh Token Strategies

### What Are Refresh Tokens?

```
Long-lived token that gets you NEW access tokens.

Why they exist:
   ✓ Access tokens are short-lived (security)
   ✓ Re-login is friction
   ✓ Refresh token solves this:
      → Get new access token without password
```

### Best Practices

```
1. NEVER expose in browser storage
   ✗ localStorage (XSS-vulnerable)
   ✗ sessionStorage (same)
   ✓ HTTP-only Secure cookies
   ✓ Native secure storage (mobile)

2. ROTATE ON USE
   Each refresh → new refresh token
   Old one immediately invalid
   → If stolen, becomes invalid as soon as user logs in

3. DETECT REUSE = COMPROMISE
   If old refresh token used after rotation:
   → Someone has stolen the token
   → Invalidate entire token family
   → Force re-login

4. SHORTER LIFETIMES IN HIGH-SECURITY APPS
   Banking: hours
   Social media: days/weeks
```

### Rotation Pattern

```
Time T0: Login
   Issued: access_v1, refresh_v1

Time T1 (15 min): Access expires
   Use refresh_v1 to get:
   - New access_v2
   - New refresh_v2 (rotated!)
   - refresh_v1 now INVALID

Time T2 (15 min): Access expires
   Use refresh_v2 to get:
   - New access_v3
   - New refresh_v3
   - refresh_v2 now INVALID

If attacker uses old refresh_v1 → DETECTED, all tokens revoked
```

### Storage Decision

```
Web (browser):
   ✓ HTTP-only Secure cookies for refresh tokens
   ✓ Memory for access tokens
   ✗ NOT localStorage

Mobile:
   ✓ iOS Keychain
   ✓ Android Keystore
   ✓ Encrypted with biometric for sensitive apps

Native:
   ✓ Windows Credential Manager
   ✓ macOS Keychain
   ✓ Linux secret service
```

---

## 10. Detecting Secret Leaks

### Pre-Commit Scanning

```
Stop secrets before they're committed:

Tools:
   ✓ git-secrets (AWS)
   ✓ TruffleHog
   ✓ Gitleaks
   ✓ detect-secrets

Pre-commit hook example:
   - Scan staged files
   - Block commit if secret found
   - Show what was detected
```

### Repository Scanning

```
Scan existing code:

Tools:
   ✓ TruffleHog (open-source)
   ✓ GitGuardian (commercial, very good)
   ✓ Snyk Secrets
   ✓ GitHub Secret Scanning (free for public repos)

Scan:
   ✓ All files
   ✓ Full git history (deleted files too!)
   ✓ All branches
```

### Log Scanning

```
Secrets accidentally logged are very common.

Mitigations:
   ✓ Scrub logs before storage
   ✓ Pattern matching for known secret formats
   ✓ Library-level filtering
   ✓ Alert on detected secrets in logs
```

### Continuous Detection

```
In CI/CD pipeline:
   1. Lint commits for secrets
   2. Scan PRs before merge
   3. Periodic scans of repos
   4. Public exposure monitoring (GitHub)
```

---

## 11. Prevention Best Practices

### Practice 1: Never Log Secrets

```
✗ logger.info(f"Calling API with key {api_key}")
✗ logger.error(f"Failed login for user {user}: password={password}")

✅ logger.info("Calling API")
✅ Use structured logging with safe fields
✅ Define a "do not log" field list
```

### Practice 2: Mask in Error Output

```
def mask_secret(value: str) -> str:
    """Show only first/last few chars"""
    if len(value) < 8:
        return "***"
    return f"{value[:4]}***{value[-2:]}"

# Use everywhere
logger.error(f"Auth failed with key: {mask_secret(api_key)}")
```

### Practice 3: Pre-Commit Hooks

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/Yelp/detect-secrets
    rev: v1.4.0
    hooks:
      - id: detect-secrets
        args: ['--baseline', '.secrets.baseline']
```

### Practice 4: CI/CD Gates

```yaml
# Block PRs with secrets
name: Secret Scanning
on: pull_request

jobs:
  scan:
    runs-on: ubuntu-latest
    steps:
      - uses: trufflesecurity/trufflehog@main
        with:
          base: ${{ github.event.repository.default_branch }}
          head: HEAD
          extra_args: --debug --only-verified
```

### Practice 5: Education

```
Train developers:
   ✓ Why secrets matter
   ✓ Common leak patterns
   ✓ How to use vault
   ✓ What to do if leaked
   ✓ Regular security awareness
```

---

## 12. Incident Response

### When a Secret Is Leaked

```
Time is critical. Respond fast.

Step 1: ROTATE IMMEDIATELY
   ✓ Generate new secret
   ✓ Update production
   ✓ Invalidate old

Step 2: ASSESS DAMAGE
   ✓ Check logs for unauthorized use
   ✓ Review audit trails
   ✓ Identify what data was accessible

Step 3: NOTIFY
   ✓ Security team
   ✓ Affected users (if applicable)
   ✓ Compliance officer (GDPR breach notification)

Step 4: REMEDIATE
   ✓ Find root cause
   ✓ Add detection for similar leaks
   ✓ Update procedures

Step 5: POSTMORTEM
   ✓ What happened?
   ✓ Why?
   ✓ How to prevent recurrence?
```

### Be Prepared

```
✓ Runbook for secret rotation
✓ List of all secrets and their owners
✓ Incident response team contacts
✓ Communication templates
✓ Practice game days
```

---

## 13. Real-World Examples

### AWS Lambda + Secrets Manager

```python
# Lambda function fetching DB credentials at startup
import boto3
import json

secrets_client = boto3.client('secretsmanager')

def get_db_credentials():
    response = secrets_client.get_secret_value(
        SecretId='prod/myapp/db'
    )
    return json.loads(response['SecretString'])

# At Lambda startup
db_creds = get_db_credentials()

def handler(event, context):
    # Use db_creds in handler
    pass
```

### Kubernetes External Secrets

```yaml
# Sync secrets from Vault to K8s
apiVersion: external-secrets.io/v1beta1
kind: ExternalSecret
metadata:
  name: my-app-secrets
spec:
  refreshInterval: 1h
  secretStoreRef:
    name: vault-backend
    kind: SecretStore
  target:
    name: my-app-secret
    creationPolicy: Owner
  data:
    - secretKey: db-password
      remoteRef:
        key: secret/myapp
        property: db_password
    - secretKey: api-key
      remoteRef:
        key: secret/myapp
        property: api_key
```

### GitHub Actions with Vault

```yaml
- name: Get secrets from Vault
  uses: hashicorp/vault-action@v2
  with:
    url: https://vault.example.com
    method: jwt
    role: github-actions
    secrets: |
      secret/data/production/aws ACCESS_KEY_ID ;
      secret/data/production/aws SECRET_ACCESS_KEY

- name: Deploy
  env:
    AWS_ACCESS_KEY_ID: ${{ env.ACCESS_KEY_ID }}
    AWS_SECRET_ACCESS_KEY: ${{ env.SECRET_ACCESS_KEY }}
  run: ./deploy.sh
```

---

## 14. Summary — Key Takeaways

```
┌──────────────────────────────────────────────────────────────┐
│  ✅ Secrets in code = catastrophic leaks                       │
│  ✅ Use a VAULT (Vault, AWS SM, Azure KV)                      │
│  ✅ Encrypt at rest AND in transit                             │
│  ✅ Rotate secrets regularly (automatic > manual)              │
│  ✅ Dynamic secrets are the gold standard                      │
│  ✅ Short-lived access tokens + refresh tokens                  │
│  ✅ Rotate refresh tokens on every use                         │
│  ✅ NEVER log secrets, mask in errors                          │
│  ✅ Detect leaks: pre-commit + CI + public scanning            │
│  ✅ Be prepared with incident response runbook                 │
└──────────────────────────────────────────────────────────────┘
```

### The Universal Rules

```
1. NEVER commit secrets to git
2. NEVER put secrets in container images
3. ALWAYS use a vault for production secrets
4. ROTATE everything regularly
5. Use SHORT-LIVED tokens where possible
6. PREFER dynamic secrets over static
7. ENCRYPT everything (at rest + in transit)
8. STORE refresh tokens securely (HTTP-only cookies, secure storage)
9. DETECT leaks: pre-commit, CI, monitoring
10. PRACTICE incident response BEFORE you need it
```

---

## 🎬 What's Next?

In **Lecture 5**, we'll put it all together with **Real-World Security Scenarios** — exploring OWASP Top 10 in practice and how to defend against the most common breaches.

> **Practical file:** [04_Practical_Hands_On.md](04_Practical_Hands_On.md)

---

## 📚 References

- HashiCorp Vault documentation
- AWS Secrets Manager docs
- *Secrets Management: A Practical Approach* — HashiCorp
- OWASP Cryptographic Storage Cheat Sheet
- NIST SP 800-57 — Key Management
- GitHub Secret Scanning docs
