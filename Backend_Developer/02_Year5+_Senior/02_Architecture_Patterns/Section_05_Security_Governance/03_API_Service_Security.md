# Lecture 3: API and Service Security

> *"APIs handle 80% of internet traffic. If they're not secure, nothing else matters."*

**Section 5 — Security & Governance in Architecture**

---

## 🎯 Is Lecture Mein Kya Seekhenge?

- **Why API security matters** — every request is sensitive
- **Knowing your enemy** — OWASP API Top 10
- **Authentication vs Authorization** — two different things
- **API Keys** — simple but limited
- **Hardening API keys** — least privilege, rotation
- **JWT for APIs** — self-contained tokens
- **JWT pitfalls** — algorithm confusion, kid validation
- **Mutual TLS (mTLS)** — service-to-service trust
- **External vs Internal interfaces** — different needs
- **Defense-in-depth** mindset

---

## 1. Why API Security Matters

### The Scale of API Traffic

```
80%+ of all internet traffic flows through APIs.

Every API request can:
   ✓ Carry sensitive user data
   ✓ Trigger financial transactions
   ✓ Modify critical system state
   ✓ Grant or revoke access
```

### The Real Risk

```
One compromised token = full backend access.

Past breaches:
   ✗ Facebook API leak (50M user data)
   ✗ Twitter API tokens exposed
   ✗ T-Mobile API breach (37M customers)
   ✗ Optus API leak (10M customer records)

Common cause: weak API security.
```

### The Stakes

```
API breach = ALL of these:
   ✗ Customer trust loss
   ✗ Regulatory fines (GDPR, etc.)
   ✗ Brand reputation damage
   ✗ Legal liability
   ✗ Direct financial loss

Security isn't optional. It's foundational.
```

---

## 2. Knowing Your Enemy — OWASP API Top 10

### Common API Attacks

```
1. BROKEN OBJECT LEVEL AUTHORIZATION
   GET /users/123/orders
   GET /users/456/orders  ← Can I see someone else's?

2. BROKEN AUTHENTICATION
   Weak tokens, no MFA, predictable session IDs

3. BROKEN OBJECT PROPERTY LEVEL AUTHORIZATION
   Mass assignment: client sends extra fields
   {"name": "test", "is_admin": true}  ← Privilege escalation!

4. UNRESTRICTED RESOURCE CONSUMPTION
   1 request → 1 GB response (DoS)
   No rate limit, no pagination

5. BROKEN FUNCTION LEVEL AUTHORIZATION
   /users/* (any user)
   /admin/users/* (admin only)
   → Forgot to check on admin endpoint!

6. UNRESTRICTED ACCESS TO SENSITIVE BUSINESS FLOWS
   Brute force OTP, password reset abuse

7. SERVER-SIDE REQUEST FORGERY (SSRF)
   App makes request based on user input
   Attacker tricks app to call internal services

8. SECURITY MISCONFIGURATION
   Default credentials, verbose errors, open CORS

9. IMPROPER INVENTORY MANAGEMENT
   Old API versions still accessible
   /v1/users (deprecated, insecure)
   /v2/users (current, secure)

10. UNSAFE CONSUMPTION OF APIs
    Trusting third-party data without validation
```

### Beyond OWASP

```
✗ Replay attacks
   Capture valid request, replay it
   
✗ Man-in-the-middle (MITM)
   Intercept unencrypted traffic
   
✗ Insider threats
   Compromised employee credentials
   
✗ Third-party misuse
   Leaked API keys, partner breach
```

---

## 3. Authentication vs Authorization

### Two Different Questions

```
AUTHENTICATION (AuthN):
   "Who are you?"
   
   Methods:
   ✓ Username + password
   ✓ API keys
   ✓ Certificates
   ✓ Tokens

AUTHORIZATION (AuthZ):
   "What are you allowed to do?"
   
   Methods:
   ✓ RBAC (roles)
   ✓ ABAC (attributes)
   ✓ Scopes
   ✓ Permissions
```

### Visual

```
   ┌────────────┐                ┌──────────────────┐
   │ Request    │                │  API Server      │
   └────┬───────┘                └──────────┬───────┘
        │                                    │
        │ Authorization: Bearer eyJ...      │
        ├───────────────────────────────────►│
        │                                    │
        │       ┌────────────────────────┐  │
        │       │ 1. AUTHENTICATION       │  │
        │       │    Is this token valid? │  │
        │       │    Who is this user?    │  │
        │       └─────────────┬──────────┘  │
        │                      │              │
        │                      ▼              │
        │       ┌────────────────────────┐  │
        │       │ 2. AUTHORIZATION        │  │
        │       │    Can this user do     │  │
        │       │    this operation?      │  │
        │       └─────────────┬──────────┘  │
        │                      │              │
        │                      ▼              │
        │              Allow or Deny         │
```

### Both Required

```
Authenticated but not authorized:
   "I know who you are, but you can't do this"
   → 403 Forbidden

Not authenticated:
   "I don't know who you are"
   → 401 Unauthorized

Many breaches = correct AuthN, missing AuthZ!
```

---

## 4. API Keys

### What Is an API Key?

**A static, randomly generated string used to identify a client making API requests.**

### When to Use API Keys

```
✓ Server-to-server communication
✓ Anonymous read-only APIs (public weather, etc.)
✓ Usage tracking for free tier
✓ Quick prototypes
✓ Internal tools
```

### When NOT to Use API Keys

```
✗ Public APIs with sensitive data
✗ User-facing apps (use OAuth instead)
✗ Anything beyond basic authentication
✗ When you need user identity (use OAuth/OIDC)
```

### Usage Patterns

```
1. As header (recommended):
   GET /api/v1/users
   X-API-Key: ak_live_abc123def456

2. As query parameter (avoid - logged everywhere):
   GET /api/v1/users?api_key=ak_live_abc123def456

3. As basic auth:
   Authorization: Basic base64(api_key:)
```

### Limitations

```
✗ Static (no expiry by default)
✗ Hard to invalidate quickly
✗ All-or-nothing (no fine-grained scope by default)
✗ If leaked, full access until rotated
✗ Often shared between team members (anti-pattern!)
```

---

## 5. Hardening API Keys

### Practice 1: Least Privilege

```
✗ One key with all permissions
✅ Many keys, each scoped narrowly

Examples:
   ✓ read-only key for reporting service
   ✓ write key for specific endpoints
   ✓ admin key for management ops
   ✓ Per-tenant keys for SaaS
```

### Practice 2: Key Rotation

```
✓ Automatic rotation in CI/CD
✓ Schedule: every 30/60/90 days
✓ Overlap: support old + new for transition
✓ Audit trail of who rotated what

Example workflow:
   1. Generate new key
   2. Deploy with both old + new
   3. Switch traffic to new
   4. Wait for any stragglers
   5. Revoke old
```

### Practice 3: Binding to Attributes

```
Restrict where keys can be used:

   ✓ IP allowlist
   ✓ Domain (Referer header)
   ✓ Device fingerprint
   ✓ Geographic region
   ✓ Time of day
   ✓ Specific API operations

Example:
   key_id: ak_live_abc
   restrictions:
     - ip_range: 10.0.0.0/24
     - allowed_paths: ["/api/v1/products/*"]
     - allowed_methods: ["GET"]
     - rate_limit: 1000/hour
```

### Practice 4: Pair with Rate Limiting

```
Even if leaked, can't be abused at scale.

   key_id: ak_live_abc
   limits:
     - 100 requests/minute
     - 10,000 requests/day
     - 1 MB response size max
   
   beyond → 429 Too Many Requests
```

### Practice 5: Detection & Revocation

```
Monitor for:
   ✓ Unusual usage spikes
   ✓ Access from new locations
   ✓ Failed authentication attempts
   ✓ Public exposure (GitHub scanning)

Quick revocation:
   ✓ One-click invalidation
   ✓ Force re-issue
   ✓ Audit log of revocations
```

### Example: GitHub Personal Access Tokens

```
Modern features:
   ✓ Fine-grained (per repository, per organization)
   ✓ Per-permission selection (read/write specific resources)
   ✓ Expiration dates
   ✓ Audit log
   ✓ Auto-detection if exposed
```

---

## 6. JWT for APIs

### Quick Recap

```
JWT = signed, self-contained token

Three parts:
   HEADER . PAYLOAD . SIGNATURE

Decoded:
   header: {"alg": "RS256", "typ": "JWT", "kid": "key-1"}
   payload: {
     "sub": "user-123",
     "exp": 1735689600,
     "scope": "read:users write:posts",
     "roles": ["editor"]
   }
   signature: signed using private key
```

### Why JWTs for APIs?

```
✓ Self-contained — no DB lookup needed
✓ Stateless — scales horizontally
✓ Standard — widely supported
✓ Cryptographic verification
✓ Can carry claims (roles, permissions)
✓ Time-limited (exp claim)
```

### The Flow

```
┌──────┐                ┌──────┐               ┌──────┐
│Client│                │ Auth │               │ API  │
└──┬───┘                └───┬──┘               └──┬───┘
   │                         │                     │
   │ 1. Login (user/pass)   │                     │
   ├────────────────────────►│                     │
   │                         │ 2. Verify           │
   │                         │    & sign JWT       │
   │ ◄───── JWT ──────────────                    │
   │                                                │
   │ 3. Subsequent requests                        │
   │    Authorization: Bearer JWT                  │
   ├──────────────────────────────────────────────►│
   │                                                │
   │                         ┌──────────────────┐  │
   │                         │ 4. Verify JWT     │  │
   │                         │    - Signature    │  │
   │                         │    - Expiry       │  │
   │                         │    - Audience     │  │
   │                         │    - Claims       │  │
   │                         └──────────────────┘  │
   │ ◄───── Response ──────────────────────────── │
```

### JWT Best Practices

```
✓ Short expiry (5-15 minutes for access)
✓ Use refresh tokens for long sessions
✓ Asymmetric keys (RS256) - public key distributed
✓ Validate signature, exp, aud, iss
✓ Hardcode allowed algorithms
✓ Use 'kid' header for key rotation
✓ Implement revocation strategy
```

---

## 7. JWT Pitfalls & Mitigations

### Pitfall 1: Algorithm Confusion (alg=none)

```
Attack:
   Change JWT header:
   {"alg": "none", "typ": "JWT"}
   
   No signature needed!
   Server might accept → forged tokens

Mitigation:
   ✗ Don't accept "alg" from token
   ✅ Hardcode in server:
      jwt.decode(token, key, algorithms=["RS256"])  # ONLY RS256!
```

### Pitfall 2: HMAC + RSA Confusion

```
Attack:
   Server uses RS256 (asymmetric, public key known)
   Attacker sends JWT signed with HS256 using public key as secret
   Server: "Is this signed with my public key?" YES
   → Accepts forged token!

Mitigation:
   ✅ Library should NOT accept any algorithm
   ✅ Hardcode expected algorithm
   ✅ Use libraries that enforce this
```

### Pitfall 3: Forgot 'kid' Validation

```
Attack:
   {"alg": "RS256", "kid": "../../etc/passwd"}
   
   Some libraries use 'kid' to find key
   Attacker tricks app into reading wrong file

Mitigation:
   ✅ Validate 'kid' is in known key set
   ✅ Whitelist allowed kid values
```

### Pitfall 4: No Revocation Strategy

```
Problem:
   JWTs are stateless → can't easily revoke
   User logs out → token still valid until expiry
   Token stolen → still valid for full lifetime

Mitigations:
   ✅ Short access token expiry (5-15 min)
   ✅ Refresh token rotation
   ✅ Denylist for emergency revocation
   ✅ Use token introspection for sensitive ops
```

### Pitfall 5: Sensitive Data in Payload

```
Problem:
   JWT payload is base64-encoded, NOT encrypted!
   Anyone can decode and read it.

❌ Don't put in JWT:
   - Passwords
   - SSNs
   - Credit card numbers
   - PII

✅ Put in JWT:
   - User ID
   - Roles
   - Scopes
   - Standard claims (exp, iat, etc.)
```

### Pitfall 6: No Key Rotation

```
Problem:
   Signing key compromised → all tokens forgeable
   
Mitigation:
   ✅ Rotate keys periodically
   ✅ Use 'kid' header to identify current key
   ✅ Publish public keys via JWKS endpoint
   ✅ Support multiple active keys during rotation
```

### Example: JWKS Endpoint

```
GET https://auth.example.com/.well-known/jwks.json

{
    "keys": [
        {
            "kid": "key-1",
            "alg": "RS256",
            "kty": "RSA",
            "n": "...",
            "e": "AQAB"
        },
        {
            "kid": "key-2",  // New key, both active during rotation
            "alg": "RS256",
            "kty": "RSA",
            "n": "...",
            "e": "AQAB"
        }
    ]
}
```

---

## 8. Mutual TLS (mTLS)

### What Is mTLS?

**Both client AND server present certificates and verify each other before any data is exchanged.**

### Standard TLS vs mTLS

```
Standard TLS (HTTPS):
   Server presents cert → Client verifies
   ✓ Server is authenticated
   ✗ Client identity unknown to server
   
   Example: User → Google.com

Mutual TLS:
   Both present certs → Both verify
   ✓ Server authenticated
   ✓ Client authenticated
   
   Example: Service A → Service B (internal)
```

### Visual

```
   ┌────────┐                          ┌────────┐
   │ Client │                          │ Server │
   └────┬───┘                          └────┬───┘
        │                                    │
        │ "Hello, here's my cert"           │
        ├──── Client cert ──────────────────►│
        │                                    │
        │                          (Verify client cert)
        │                                    │
        │ "Hello, here's my cert"           │
        ◄──── Server cert ───────────────────┤
        │                                    │
        │ (Verify server cert)               │
        │                                    │
        │ Both verified, secure channel     │
        ◄══════════════════════════════════►│
        │                                    │
```

### Why mTLS?

```
✓ Strong identity for both parties
✓ No passwords/tokens to manage
✓ Cryptographically enforced
✓ Network-level (transparent to apps)
✓ Perfect for zero-trust architecture
✓ Encryption + authentication in one
```

### When to Use mTLS

```
✓ Service-to-service communication (microservices)
✓ B2B integrations (banks, partners)
✓ Internal admin APIs
✓ IoT device authentication
✓ Banking APIs (FAPI standard)
✓ Zero-trust networks
```

### Service Mesh + mTLS

```
Istio/Linkerd automatically handle mTLS:

   Service A           Service B
       │                   │
       ▼                   ▼
   ┌─────────┐        ┌─────────┐
   │ Sidecar │  mTLS  │ Sidecar │
   │ proxy   │◄══════►│ proxy   │
   └─────────┘        └─────────┘
   
   ✓ Apps don't need to know about TLS
   ✓ Certs auto-rotated
   ✓ Identity built-in (SPIFFE)
```

---

## 9. External vs Internal Interfaces

### Different Trust Levels

```
EXTERNAL (Public APIs):
   ✗ Untrusted clients
   ✗ Subject to attacks
   ✓ Need maximum protection

INTERNAL (Service-to-service):
   ✓ Known clients (your services)
   ✓ Internal network (less exposed)
   ✓ Different threats (lateral movement)

SHARED (Between trust zones):
   API gateways, ingress controllers
```

### Different Security Approaches

```
┌──────────────────┬──────────────────┬──────────────────┐
│  EXTERNAL         │  INTERNAL         │  SHARED          │
├──────────────────┼──────────────────┼──────────────────┤
│  OAuth 2.0 / OIDC │  mTLS             │  API gateway     │
│  JWT validation   │  Service mesh     │  Edge protection │
│  Rate limit (low) │  Rate limit (high)│  Rate limit (mid)│
│  Strict CORS      │  No CORS needed   │  Configured CORS │
│  WAF, DDoS proof  │  Network policies │  Edge WAF        │
│  Public schemas   │  Internal schemas │  Versioned APIs  │
└──────────────────┴──────────────────┴──────────────────┘
```

### Layered Defense

```
Internet
   │
   ▼
┌────────────────┐
│ CDN / DDoS     │ ← Layer 1: Edge protection
└────────┬───────┘
         │
         ▼
┌────────────────┐
│ WAF            │ ← Layer 2: Web Application Firewall
└────────┬───────┘
         │
         ▼
┌────────────────┐
│ API Gateway    │ ← Layer 3: Auth, rate limit, routing
└────────┬───────┘
         │
         ▼
┌────────────────┐
│ Service Mesh   │ ← Layer 4: mTLS, policies
└────────┬───────┘
         │
         ▼
┌────────────────┐
│ Services       │ ← Layer 5: App-level authZ
└────────────────┘
```

---

## 10. Defense in Depth — The Complete Stack

### At the Edge

```
✓ DDoS protection (Cloudflare, AWS Shield)
✓ Web Application Firewall (WAF)
   - Block known attack patterns
   - SQL injection detection
   - XSS protection
✓ Rate limiting per IP
✓ Geo-blocking if needed
✓ TLS termination
```

### At the API Gateway

```
✓ Authentication (JWT, API keys)
✓ Authorization (scopes, roles)
✓ Rate limiting per user/key
✓ Request validation
✓ Schema enforcement
✓ Audit logging
```

### At the Service Layer

```
✓ Input validation (defense in depth!)
✓ Output sanitization
✓ Business logic checks
✓ Database query parameterization
✓ Secrets from vault (not env)
```

### At the Network Layer

```
✓ mTLS between services
✓ Network policies (microsegmentation)
✓ VPC + private subnets
✓ Egress filtering
✓ DNS protection
```

### At the Data Layer

```
✓ Encryption at rest
✓ Encryption in transit
✓ Access controls (IAM)
✓ Auditing all reads/writes
✓ Tokenization of sensitive fields
```

### Monitoring & Response

```
✓ Centralized logging
✓ SIEM correlation
✓ Anomaly detection
✓ Real-time alerts
✓ Incident response runbooks
✓ Regular security audits
```

---

## 11. API Security Anti-Patterns

### Anti-Pattern 1: Tokens in URLs

```
❌ GET /api/users?token=eyJ...

Problems:
   ✗ Logged in browser history
   ✗ Logged in web server logs
   ✗ Sent in Referer header
   ✗ Visible in proxies

✅ Use Authorization header
```

### Anti-Pattern 2: Trusting Client-Side Filters

```
❌ Frontend hides delete button for non-admin
   But backend doesn't check role

Attacker just calls DELETE directly!

✅ ALWAYS check authorization server-side
```

### Anti-Pattern 3: Verbose Error Messages

```
❌ "User 'admin' not found in users table"
❌ "Wrong password for ashish@example.com"
❌ Stack traces in production

→ Helps attackers enumerate users, gather info

✅ Generic messages:
   "Invalid credentials"
   "Resource not found"
   Hide internal details
```

### Anti-Pattern 4: No Input Validation

```
❌ Trust everything from client

Attack:
   {"user_id": 123, "is_admin": true}
   ← Client sets their own is_admin!

✅ Validate every input
✅ Whitelist allowed fields
✅ Strong types (Pydantic)
```

### Anti-Pattern 5: No Versioning

```
❌ /api/users (no version)

Problem: Breaking changes break ALL clients

✅ /api/v1/users
✅ Deprecation policy
✅ Sunset headers
```

### Anti-Pattern 6: Open CORS

```
❌ Access-Control-Allow-Origin: *

→ Any website can call your API on behalf of users

✅ Whitelist specific origins
✅ Different policies for public vs internal
```

---

## 12. Real-World Best Practices

### Stripe-Style API Security

```
✓ API keys with prefixes:
   pk_live_xxx (publishable)
   sk_live_xxx (secret)
   sk_test_xxx (test mode)

✓ Idempotency-Key for safe retries
✓ Versioned API (date-based)
✓ Webhooks with HMAC signatures
✓ Detailed audit logs
✓ Rate limiting per key
✓ Per-customer encryption
```

### Banking API Security (FAPI)

```
✓ mTLS mandatory
✓ JWS signed requests
✓ Short token expiry
✓ Detailed audit trail
✓ Strong customer authentication (SCA)
✓ Per-transaction confirmation
```

### Google/GitHub API Security

```
✓ OAuth 2.0 + PKCE
✓ Fine-grained scopes
✓ Auto-revoke on suspicious activity
✓ Token leak detection (scans GitHub for leaked tokens)
✓ Webhook signature verification
✓ Rate limits + quotas
```

---

## 13. Security Checklist

### Pre-Production Checklist

```
Authentication:
   □ All endpoints require auth (except public ones)
   □ Strong token validation (signature, exp, aud)
   □ Hardcoded allowed algorithms (no "none"!)
   □ Token revocation strategy

Authorization:
   □ Permission check on every endpoint
   □ Object-level checks (user owns resource)
   □ Server-side enforcement only
   □ Audit log of access decisions

Input/Output:
   □ Validate all inputs (schema)
   □ Whitelist allowed fields
   □ Sanitize outputs (no XSS)
   □ Parameterized DB queries
   □ Limit response size

Transport:
   □ HTTPS everywhere (TLS 1.2+)
   □ HSTS header
   □ Secure cookies (HTTP-only, Secure)
   □ mTLS for internal traffic

Operational:
   □ Rate limiting
   □ Centralized logging
   □ Alerts on anomalies
   □ Regular security scans
   □ Penetration testing
   □ Bug bounty program
```

---

## 14. Summary — Key Takeaways

```
┌──────────────────────────────────────────────────────────────┐
│  ✅ APIs handle 80%+ of traffic — security is critical       │
│  ✅ OWASP API Top 10 = your threat model baseline            │
│  ✅ Authentication ≠ Authorization                            │
│  ✅ API keys for simple cases, OAuth/JWT for users           │
│  ✅ Harden API keys: rotation, scoping, binding              │
│  ✅ JWT pitfalls: alg=none, kid validation, rotation         │
│  ✅ mTLS for service-to-service (zero trust)                 │
│  ✅ External vs internal: different threat models            │
│  ✅ Defense in depth: layer your protections                 │
│  ✅ Visibility + monitoring = essential for response          │
└──────────────────────────────────────────────────────────────┘
```

### The Universal Rules

```
1. HTTPS everywhere, no exceptions
2. Hardcode JWT algorithms (no "none"!)
3. Short access tokens, refresh securely
4. API keys: scoped, rotated, bound
5. mTLS for internal services
6. Validate ALL inputs server-side
7. Log security events centrally
8. Rate limit EVERYTHING
9. Generic error messages
10. Defense in depth = layered security
```

---

## 🎬 What's Next?

In **Lecture 4**, we'll cover **Secrets and Token Management** — how to store, rotate, and protect the sensitive credentials your system depends on.

> **Practical file:** [03_Practical_Hands_On.md](03_Practical_Hands_On.md)

---

## 📚 References

- *API Security in Action* — Neil Madden
- OWASP API Security Top 10
- *OAuth 2.0 in Action* — Justin Richer
- NIST SP 800-204 — API security
- *The Tangled Web* — Michał Zalewski
- Cloudflare API Security blog
