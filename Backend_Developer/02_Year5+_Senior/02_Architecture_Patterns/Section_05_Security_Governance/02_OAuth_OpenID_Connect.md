# Lecture 2: Authentication & Identity — OAuth 2.0 + OpenID Connect

> *"OAuth answers 'what can you access?'. OpenID Connect answers 'who are you?'"*

**Section 5 — Security & Governance in Architecture**

---

## 🎯 Is Lecture Mein Kya Seekhenge?

- **Why auth/identity matters** in modern systems
- **What is OAuth 2.0?** — delegated authorization
- **Core OAuth 2.0 flows** — authorization code, client credentials, device
- **Authorization Code Flow with PKCE** — step-by-step
- **Tokens explained** — access, refresh, ID tokens
- **OpenID Connect** — identity on top of OAuth
- **Identity federation & SSO** — Single Sign-On
- **RBAC vs ABAC** revisited
- **Session vs Token lifecycle** — trade-offs
- **Best practices** — security in real-world implementations

---

## 1. Why Authentication & Identity Matters

### The User Experience Side

```
Modern users expect:
   ✓ One login across web, mobile, partner apps
   ✓ No managing 50 different passwords
   ✓ Secure but seamless
   ✓ "Sign in with Google" simplicity
```

### The Microservices Reality

```
Modern systems = many services:
   ✗ Can't rely on user session alone
   ✗ Services need to talk to each other securely
   ✗ Each call may need different permissions
   ✗ Service-to-service identity

→ Need DELEGATED, GRANULAR access control.
```

### Compliance Requirements

```
Regulations demand strong identity:
   ✓ GDPR — user consent and data access
   ✓ HIPAA — healthcare identity
   ✓ SOC 2 — access controls + audit
   ✓ PCI-DSS — payment authentication
   ✓ Industry-specific standards

Strong identity = legal requirement, not optional.
```

---

## 2. What Is OAuth 2.0?

### Definition

**OAuth 2.0 = A DELEGATED AUTHORIZATION protocol that allows applications to access resources on a user's behalf without seeing their credentials.**

> 🚨 **Critical:** OAuth 2.0 is about AUTHORIZATION (what you can access), NOT AUTHENTICATION (who you are).

### The Classic Example

```
You want to: Log in to abc.com using your Google account.

Without OAuth:
   ✗ Give abc.com your Google password
   ✗ abc.com has full access forever
   ✗ Can't revoke

With OAuth:
   ✓ abc.com asks Google for permission
   ✓ Google asks you: "Allow abc.com to access your name and email?"
   ✓ You approve
   ✓ Google gives abc.com a limited TOKEN
   ✓ abc.com uses TOKEN to get just name+email
   ✓ Your password never leaves Google
   ✓ You can revoke anytime
```

### The Four Roles

```
1. RESOURCE OWNER (you)
   The user with data others want to access

2. CLIENT (abc.com)
   The app wanting access

3. AUTHORIZATION SERVER (Google's login)
   Verifies user, issues tokens

4. RESOURCE SERVER (Google Calendar/Profile API)
   Holds the protected data
```

### Visual

```
   ┌─────────┐                  ┌─────────────┐
   │ User    │                  │ abc.com     │
   │ (Owner) │                  │ (Client)    │
   └────┬────┘                  └──────┬──────┘
        │                                │
        │  1. "Sign in with Google"     │
        ◄────────────────────────────────┤
        │                                │
        │  2. Login + approve scopes    │
        ┼───────────────────────────────►│
                                         │
   ┌─────────────────────────────────────┴──┐
   │  Google's OAuth Authorization Server   │
   │                                          │
   │  3. Returns access TOKEN                │
   └─────────────────────────────────────────┘
                                         │
        ┌────────────────────────────────┘
        │
        │ 4. Use TOKEN
        ▼
   ┌─────────────────────────────┐
   │ Google API (Resource Server) │
   │                              │
   │ 5. Returns data              │
   └─────────────────────────────┘
```

---

## 3. Core OAuth 2.0 Flows

### Not One-Size-Fits-All

Different client types need different flows.

### Flow 1: Authorization Code Flow with PKCE

```
Best for: Mobile apps, SPAs (JavaScript), public clients
Why: Most secure for clients that can't keep secrets
```

### Flow 2: Client Credentials Flow

```
Best for: Service-to-service, machine-to-machine
Why: No user involved
```

### Flow 3: Device Code Flow

```
Best for: Smart TVs, IoT devices, CLIs
Why: Hard to type passwords on TV remote
```

### Flow 4 (Legacy): Implicit Flow — DEPRECATED

```
🚨 Don't use! Replaced by Authorization Code + PKCE.
```

### Flow 5 (Legacy): Resource Owner Password — DEPRECATED

```
🚨 Don't use! User gives password to client. Defeats purpose.
```

### Quick Decision Tree

```
What kind of client?
   │
   ├─ Web app with backend → Authorization Code (with PKCE optional but recommended)
   ├─ Mobile/Native app    → Authorization Code + PKCE
   ├─ SPA (browser only)    → Authorization Code + PKCE
   ├─ Service-to-service    → Client Credentials
   ├─ Smart TV / IoT        → Device Code
   └─ CLI tool              → Device Code or Authorization Code
```

---

## 4. Authorization Code Flow with PKCE (Deep Dive)

### Why PKCE?

```
PKCE = Proof Key for Code Exchange (pronounced "pixie")

Problem PKCE solves:
   - Public clients (mobile, SPA) can't keep secrets
   - Attackers could intercept authorization code
   - Use it to steal tokens

PKCE solution:
   - Client generates a "code verifier" (random secret)
   - Sends HASH of verifier (code challenge) at start
   - Sends original verifier at end
   - Server compares: only original client can complete
```

### Step-by-Step Flow

```
┌────────────────────────────────────────────────────────────┐
│                                                              │
│  CLIENT                AUTH SERVER          RESOURCE SERVER  │
│                                                              │
│  1. Generate                                                 │
│     verifier = random_string                                 │
│     challenge = SHA256(verifier)                             │
│                                                              │
│  2. Redirect user to authorize                               │
│     ─── code_challenge ──────►                              │
│                                                              │
│  3. User logs in & approves                                  │
│     (in browser - secure)                                    │
│                                                              │
│  4. Redirect back with code                                  │
│     ◄────── authorization_code ───────                       │
│                                                              │
│  5. Exchange code for token                                  │
│     (send original verifier!)                                │
│     ──── code + verifier ──────►                            │
│                                                              │
│  6. Server checks:                                           │
│     SHA256(verifier) == challenge?                           │
│     If yes: issue tokens                                     │
│                                                              │
│  7. Receive tokens                                           │
│     ◄────── access_token + refresh_token + id_token ──      │
│                                                              │
│  8. Call API with access token                               │
│     ──── Bearer token ──────────────────────────►           │
│                                                              │
│  9. Get user's data                                          │
│     ◄────── user data ──────────────────────────────        │
└────────────────────────────────────────────────────────────┘
```

### Why PKCE Stops Attackers

```
Attacker steals authorization_code from redirect:
   - Tries to exchange for token
   - Server: "Where's the code_verifier?"
   - Attacker doesn't have it (never sent over network)
   - Server: REJECTED

→ Even if code is intercepted, attacker can't use it!
```

### Code Example (Conceptual)

```python
import secrets
import hashlib
import base64

# Step 1: Generate verifier + challenge
code_verifier = secrets.token_urlsafe(64)
code_challenge = base64.urlsafe_b64encode(
    hashlib.sha256(code_verifier.encode()).digest()
).decode().rstrip("=")

# Step 2: Redirect user to auth server with code_challenge
auth_url = (
    f"https://auth.example.com/authorize?"
    f"client_id=my_app&"
    f"redirect_uri=myapp://callback&"
    f"response_type=code&"
    f"scope=openid profile email&"
    f"code_challenge={code_challenge}&"
    f"code_challenge_method=S256"
)

# ... user redirected to auth URL, logs in ...
# ... server redirects back with code ...

# Step 5: Exchange code for token (with original verifier!)
response = requests.post("https://auth.example.com/token", data={
    "grant_type": "authorization_code",
    "client_id": "my_app",
    "code": authorization_code,
    "code_verifier": code_verifier,  # Server verifies SHA256 matches
    "redirect_uri": "myapp://callback",
})

tokens = response.json()
# {"access_token": "...", "refresh_token": "...", "id_token": "..."}
```

---

## 5. Tokens Explained

### The Three Token Types

```
1. ACCESS TOKEN
   - Short-lived (5-60 min)
   - Used to call APIs
   - Bearer token in Authorization header
   - Scoped to specific permissions

2. REFRESH TOKEN
   - Long-lived (days to months)
   - Used to get new access tokens
   - Never sent to APIs
   - Should be rotated on use

3. ID TOKEN (OpenID Connect only)
   - Contains user identity info
   - JWT format
   - "Who logged in?"
   - Used by client app, not for API access
```

### Access Token Structure

```
A JWT access token has 3 parts:

   HEADER.PAYLOAD.SIGNATURE

   header:    {"alg": "RS256", "typ": "JWT", "kid": "key-id-1"}
   payload:   {
                "sub": "user-123",      # Subject (user ID)
                "iss": "auth-server",   # Issuer
                "aud": "api-server",    # Audience
                "exp": 1735689600,      # Expiry
                "iat": 1735686000,      # Issued at
                "scope": "read:profile write:orders",
                "roles": ["user"]
              }
   signature: signed with private key
```

### Token Usage

```python
# Client makes API call
headers = {
    "Authorization": f"Bearer {access_token}"
}
response = requests.get("https://api.example.com/orders", headers=headers)

# Server validates token:
# 1. Verify signature (using public key)
# 2. Check expiry
# 3. Check audience (this server)
# 4. Check scope (allowed operations)
# → If all good, process request
```

### Refresh Token Flow

```
Access token expires → use refresh token to get new one

POST /token
{
    "grant_type": "refresh_token",
    "refresh_token": "old_refresh_token",
    "client_id": "my_app"
}

Response:
{
    "access_token": "new_access_token",
    "refresh_token": "new_refresh_token",  # Rotated!
    "expires_in": 3600
}

→ User stays logged in without re-entering password
```

---

## 6. OpenID Connect (OIDC)

### What Problem Does It Solve?

```
OAuth 2.0 gives you access tokens.
   But access token tells you NOTHING about the user.

OpenID Connect (OIDC) adds:
   ✓ ID tokens (user identity)
   ✓ UserInfo endpoint (more user details)
   ✓ Standard scopes (openid, profile, email)
```

### OIDC = OAuth 2.0 + Identity Layer

```
┌─────────────────────────────────────────────────────────────┐
│                  OPENID CONNECT                              │
│                                                              │
│   ┌─────────────────────────────────────────────────────┐   │
│   │              OAuth 2.0                               │   │
│   │  (authorization protocol)                            │   │
│   └─────────────────────────────────────────────────────┘   │
│                       +                                      │
│   ┌─────────────────────────────────────────────────────┐   │
│   │            Identity layer                            │   │
│   │  - ID Token (JWT with user info)                    │   │
│   │  - UserInfo endpoint                                 │   │
│   │  - Standard scopes (openid, profile, email)         │   │
│   └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

### ID Token Structure

```
ID Token payload (JWT):
{
    "iss": "https://auth.example.com",   # Issuer
    "sub": "user-123",                    # Subject (user ID)
    "aud": "my_client_id",                # Audience (client)
    "exp": 1735689600,                    # Expiry
    "iat": 1735686000,                    # Issued at
    "nonce": "random-value",              # Prevent replay
    
    # User identity claims
    "name": "Ashish Chaurasiya",
    "email": "ashish@example.com",
    "email_verified": true,
    "picture": "https://cdn/avatar.jpg",
    "given_name": "Ashish",
    "family_name": "Chaurasiya"
}
```

### Standard Scopes

```
openid       → Required for OIDC
profile      → Name, picture, etc.
email        → Email + verification status
address      → Postal address
phone        → Phone number

Plus custom scopes:
   read:orders, write:profile, admin:users
```

### UserInfo Endpoint

```
GET /userinfo
Authorization: Bearer <access_token>

Response:
{
    "sub": "user-123",
    "name": "Ashish Chaurasiya",
    "email": "ashish@example.com",
    "picture": "https://...",
    "updated_at": 1735000000
}

→ Get fresh user info anytime with access token
```

---

## 7. Identity Federation & SSO

### Single Sign-On (SSO)

**Login once, access many apps.**

```
Without SSO:
   ✗ Login to Gmail
   ✗ Login to Slack
   ✗ Login to GitHub
   ✗ Login to Jira
   ✗ Login to Salesforce
   ✗ 50+ passwords to manage!

With SSO:
   ✓ Login once (via Identity Provider)
   ✓ Access all integrated apps
   ✓ Centralized password reset, MFA, etc.
```

### How SSO Works

```
   ┌───────┐                                ┌──────────────┐
   │ User  │                                │   App 1      │
   └───┬───┘                                └──────┬───────┘
       │                                            │
       │  1. Access App 1                          │
       ├───────────────────────────────────────────►│
       │                                            │
       │  2. Redirect to Identity Provider          │
       ◄───────────────────────────────────────────┤
       │                                            │
       │            ┌────────────────────────────┐  │
       │            │  Identity Provider (IdP)   │  │
       │  3. Login  │  - Okta                    │  │
       ├───────────►│  - Azure AD                │  │
       │            │  - Google Workspace        │  │
       │  4. Verify │  - Auth0                   │  │
       │            └────────────────┬───────────┘  │
       │                              │              │
       │  5. Redirect back with token │              │
       ├──────────────────────────────►              │
       │                                            │
       │  6. App 1 trusts IdP, grants access        │
       │                                            │
       │  7. Later, access App 2                    │
       │      (still logged in!)                    │
       │                                            │
```

### Federation Standards

```
1. SAML 2.0
   ✓ Enterprise standard
   ✓ XML-based
   ✓ Common in B2B
   ✗ Verbose, complex

2. OpenID Connect
   ✓ Modern
   ✓ JSON/JWT-based
   ✓ Web + mobile friendly
   ✓ Increasingly preferred

3. OAuth 2.0 (auth only)
   ✗ Not for SSO directly (no identity)
```

### Provisioning

```
Just-in-Time (JIT):
   User logs in for first time via SSO
   → App auto-creates account
   → Uses identity from IdP
   
SCIM (System for Cross-domain Identity Management):
   IdP pushes user lifecycle events
   - User added → create account
   - User updated → sync changes
   - User removed → deactivate
```

### Centralized Logout

```
Single Logout (SLO):
   Logout once → terminates session everywhere
   
   ✓ Better UX
   ✓ Security: no orphaned sessions
   ✓ Compliance: clean shutdown
```

---

## 8. RBAC vs ABAC Revisited

### RBAC: Role-Based Access Control

```
Simple model:
   User → Role → Permissions

Example:
   Alice → Admin → [all permissions]
   Bob   → Editor → [read, write]
   Carol → Viewer → [read]

✓ Simple to implement
✓ Easy to audit
✓ Predictable
✗ Doesn't scale to fine-grained needs
```

### ABAC: Attribute-Based Access Control

```
Rich model:
   Permission = f(user_attrs, resource_attrs, env_attrs)

Example policy:
   "Allow IF:
      user.department = 'finance'
      AND resource.type = 'invoice'
      AND time.is_working_hours()
      AND request.ip in trusted_ips"

✓ Highly flexible
✓ Context-aware
✓ Fine-grained
✗ More complex
✗ Harder to audit
```

### When to Use Which

```
Use RBAC when:
   ✓ Clear, static roles
   ✓ Simple organization structure
   ✓ Auditability is critical

Use ABAC when:
   ✓ Need contextual decisions
   ✓ Resources have varying ownership
   ✓ Time/location/device-aware access needed
```

### Real-World Reality

```
Most production systems use BOTH:
   1. RBAC for broad strokes (admin vs user)
   2. ABAC for fine details (admin BUT only their tenant)
```

### Hybrid Example

```
RBAC Layer:
   - role: "support_agent"
   - permissions: ["read:tickets", "update:tickets"]

ABAC Layer (on top):
   - "Can update tickets assigned to your team"
   - "Cannot access tickets older than 1 year"
   - "Cannot access tickets marked confidential"
```

---

## 9. Session vs Token Lifecycle

### Session-Based Authentication

```
   ┌────────┐                ┌──────────┐
   │ Browser│                │ Server   │
   └────┬───┘                └─────┬────┘
        │                            │
        │ 1. Login                  │
        ├───────────────────────────►│
        │                            │
        │                            │ 2. Create session
        │                            │    Store in DB/memory
        │                            │
        │ 3. Set cookie              │
        ◄───────────────────────────┤
        │ Set-Cookie: session=abc123 │
        │                            │
        │ 4. Subsequent requests    │
        │    Cookie sent automatically
        ├───────────────────────────►│
        │                            │ 5. Lookup session
        │                            │    in DB/memory
        │                            │
        ◄───────────────────────────┤
```

```
Pros:
   ✓ Simple
   ✓ Easy revocation (delete from DB)
   ✓ Server has full control

Cons:
   ✗ Server-side state (scaling issue)
   ✗ Sticky sessions or shared session store needed
   ✗ Doesn't scale well to microservices
```

### Token-Based Authentication

```
   ┌────────┐                ┌──────────┐
   │ Client │                │ Server   │
   └────┬───┘                └─────┬────┘
        │                            │
        │ 1. Login                  │
        ├───────────────────────────►│
        │                            │
        │ 2. Server signs JWT       │
        │    (NO session storage!)   │
        │                            │
        │ 3. Return token            │
        ◄───────────────────────────┤
        │                            │
        │ 4. Send token with each   │
        │    request                 │
        ├───────────────────────────►│
        │ Authorization: Bearer ... │
        │                            │ 5. Verify signature
        │                            │    No DB lookup!
        │                            │
        ◄───────────────────────────┤
```

```
Pros:
   ✓ Stateless server
   ✓ Scales horizontally
   ✓ Perfect for microservices
   ✓ Mobile-friendly

Cons:
   ✗ Can't revoke until expiry (without blacklist)
   ✗ Token storage on client (security risk)
   ✗ Token size larger than session ID
```

### Side-by-Side

```
┌─────────────────────┬─────────────────────┬─────────────────────┐
│  ASPECT              │  SESSION             │  TOKEN              │
├─────────────────────┼─────────────────────┼─────────────────────┤
│  State               │  Server-side         │  Client-side        │
│  Revocation          │  Easy                │  Hard (need denylist)│
│  Scalability         │  Limited             │  Excellent          │
│  Security risk       │  CSRF (cookies)      │  XSS (storage)      │
│  Mobile-friendly     │  Hard                │  Easy               │
│  Microservices       │  Hard (shared state) │  Easy (stateless)   │
│  Storage location    │  HTTP-only cookie    │  Memory/localStorage│
│  Best for            │  Traditional web apps│  APIs, mobile, SPAs │
└─────────────────────┴─────────────────────┴─────────────────────┘
```

---

## 10. Best Practices

### Practice 1: Always HTTPS

```
OAuth tokens = passwords. Never send over HTTP.

✓ HTTPS everywhere (including localhost in dev)
✓ Use TLS 1.2+
✓ Enable HSTS (Strict-Transport-Security header)
```

### Practice 2: Use PKCE for Public Clients

```
✗ Don't use Implicit Flow (deprecated)
✗ Don't store client_secret in mobile/SPA

✅ Authorization Code Flow + PKCE
```

### Practice 3: Short-Lived Access Tokens

```
✓ Access tokens: 5-15 minutes typical
✓ Refresh tokens: longer (hours/days)
✓ Reduces window if compromised

Example expiry:
   Access token: 15 min
   Refresh token: 24 hours (rotated on use)
```

### Practice 4: Secure Token Storage

```
Frontend storage options:

❌ localStorage (XSS-vulnerable)
❌ sessionStorage (same problem)
⚠️ Cookies (CSRF risk if not configured)

✅ HTTP-only Secure cookies (best for web)
✅ Memory only (cleared on page refresh)
✅ Native secure storage (mobile keychain/keystore)
```

### Practice 5: Token Introspection & Revocation

```
Introspection endpoint:
   POST /introspect
   token=eyJ...
   
   Response: {"active": true/false, "scope": "...", "exp": ...}

Revocation endpoint:
   POST /revoke
   token=eyJ...
   
   Use case: User logs out, suspicious activity
```

### Practice 6: Monitor Auth Events

```
Log and alert on:
   ✓ Failed logins (brute force)
   ✓ Logins from new locations
   ✓ Unusual access patterns
   ✓ Token theft indicators
   ✓ Mass logouts

→ Detect & respond to threats early
```

### Practice 7: Use Established Libraries

```
Don't implement OAuth yourself!

✓ Auth0
✓ Okta
✓ Keycloak (self-hosted)
✓ AWS Cognito
✓ Azure AD B2C
✓ Firebase Auth

For library-based:
✓ Authlib (Python)
✓ Passport (Node.js)
✓ Spring Security OAuth2 (Java)
```

---

## 11. Common Vulnerabilities

### Vulnerability 1: Open Redirect

```
Attack:
   /oauth/callback?redirect=https://evil.com
   → If app blindly redirects → attacker harvests token

Defense:
   ✓ Whitelist redirect URIs
   ✓ Exact match (not prefix)
   ✓ Validate before redirecting
```

### Vulnerability 2: Algorithm Confusion

```
Attack:
   Change JWT header from RS256 to "none"
   → Server skips signature verification
   → Attacker forges any token

Defense:
   ✓ Hardcode expected algorithm
   ✓ Never accept "none" algorithm
   ✓ Use library defaults
```

### Vulnerability 3: Token in URL

```
Attack:
   Tokens in URL get logged everywhere:
   - Browser history
   - Web server logs
   - Proxy logs
   - Referer header to other sites

Defense:
   ✓ Tokens in Authorization header
   ✓ Never in query strings
```

### Vulnerability 4: Insecure Storage

```
Attack:
   localStorage compromised by XSS
   → Steals tokens

Defense:
   ✓ HTTP-only cookies (web)
   ✓ Secure native storage (mobile)
   ✓ Content Security Policy (CSP)
   ✓ Sanitize all input
```

### Vulnerability 5: No Token Audience Check

```
Attack:
   Get token for API A
   Use it on API B (which trusts same auth server)
   → Cross-API misuse

Defense:
   ✓ Always validate "aud" claim
   ✓ Each API has own audience identifier
```

---

## 12. Real-World Examples

### Google Sign-In

```
Authorization Code + PKCE flow
ID Token returned (OIDC)
Standard scopes: openid, profile, email
```

### GitHub OAuth Apps

```
Authorization Code flow
Personal Access Tokens for API access
Fine-grained permissions via scopes
```

### Login with Apple

```
Privacy-focused OAuth/OIDC
Anonymous email forwarding option
Required by App Store for apps with social login
```

### Banking APIs (Open Banking)

```
OAuth 2.0 + FAPI (Financial-grade API)
PKCE mandatory
JWS signed requests
mTLS for client authentication
```

---

## 13. Summary — Key Takeaways

```
┌──────────────────────────────────────────────────────────────┐
│  ✅ OAuth 2.0 = delegated AUTHORIZATION                       │
│  ✅ OpenID Connect = OAuth + AUTHENTICATION (identity)        │
│  ✅ Authorization Code + PKCE for public clients              │
│  ✅ Client Credentials for service-to-service                  │
│  ✅ Short-lived access tokens + refresh tokens                 │
│  ✅ HTTPS everywhere, store tokens securely                    │
│  ✅ ID tokens carry user identity                              │
│  ✅ SSO via SAML or OIDC for enterprise                        │
│  ✅ Combine RBAC + ABAC for flexible access                    │
│  ✅ Use established libraries, never roll your own             │
└──────────────────────────────────────────────────────────────┘
```

### The Universal Rules

```
1. OAuth ≠ OpenID Connect (authorize vs authenticate)
2. PKCE for public clients (mobile, SPA)
3. Short-lived access tokens (15 min)
4. Rotate refresh tokens on use
5. Validate ALL token claims (signature, exp, aud)
6. Never store tokens in localStorage
7. Always HTTPS, never tokens in URLs
8. Hardcode allowed signing algorithms
9. Use SSO via OIDC/SAML for enterprise
10. Use established libraries (don't roll your own!)
```

---

## 🎬 What's Next?

In **Lecture 3**, we'll dive into **API and Service Security** — protecting your endpoints with API keys, JWTs, mTLS, and defense-in-depth strategies.

> **Practical file:** [02_Practical_Hands_On.md](02_Practical_Hands_On.md)

---

## 📚 References

- *OAuth 2.0 in Action* — Justin Richer, Antonio Sanso
- RFC 6749 — OAuth 2.0 Specification
- RFC 7636 — PKCE for OAuth Public Clients
- OpenID Connect Core 1.0 spec
- *Auth0 Identity 101* (free online)
- *OWASP Authentication Cheat Sheet*
