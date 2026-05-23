# Token-Based Authentication — JWT, Refresh Tokens, Stateless vs Stateful

## Quick Reference Card
```
JWT           → JSON Web Token — header.payload.signature (Base64 encoded)
Stateless     → Server doesn't store session — JWT is self-contained
Access Token  → Short-lived (15min) — used for API requests
Refresh Token → Long-lived (30 days) — used to get new access token
HS256         → HMAC-SHA256 — symmetric signing (same key for sign+verify)
RS256         → RSA — asymmetric — public key to verify, private to sign
Interview hook → "JWT HS256 + 15min access + 30day refresh tokens in Youngman/Niroskos"
```

---

## PART 1: HINGLISH — Samjhne ke liye

### 1.1 Why Token-Based Auth?

**Analogy: Concert wristband**

Concert mein: Entry gate pe security tumhara ticket check karta hai → wristband deta hai. Ab hall ke andar kisi bhi counter pe sirf wristband dikhao — hamesha ticket nahi dikhana padta. Wristband pe information encoded hai: VIP ya General.

```
SESSION-BASED (old way):
  Login → Server creates session in DB → Session ID in cookie
  Next request → Cookie sent → Server looks up session in DB
  
  PROBLEM:
  → DB hit on every request (slow)
  → Multiple servers: Server 1 has session, request goes to Server 2?
    → Session not found! Must use sticky sessions or shared session store (Redis)
  → Horizontal scaling hard

TOKEN-BASED (modern way):
  Login → Server creates token → Token given to client
  Next request → Token in header → Server VERIFIES token (no DB hit!)
  
  Token is SELF-CONTAINED:
  → Contains user_id, role, expiry
  → Server just verifies signature (cryptographic — can't be faked)
  → No DB lookup needed!
  → Any server can verify any token (stateless!)
```

---

### 1.2 JWT Structure

```
JWT = Three Base64Url-encoded parts separated by dots:
  header.payload.signature

EXAMPLE:
  eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.
  eyJ1c2VyX2lkIjo1LCJlbWFpbCI6ImFzaGlzaEB5b3VuZ21hbi5jb20iLCJyb2xlIjoibWFuYWdlciIsImV4cCI6MTcwNTAwMDAwMH0.
  SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c

PART 1 — HEADER (algorithm + token type):
  {
    "alg": "HS256",   ← Algorithm (HMAC-SHA256)
    "typ": "JWT"
  }
  → Base64Url encode → "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"

PART 2 — PAYLOAD (claims — data):
  {
    "user_id": 5,
    "email": "ashish@youngman.com",
    "role": "manager",
    "company_id": 12,
    "exp": 1705000000,   ← Expiry (Unix timestamp)
    "iat": 1704913600,   ← Issued at
    "jti": "unique-jwt-id"  ← JWT ID (for blacklisting)
  }
  → Base64Url encode → "eyJ1c2VyX2lkIjo1..."

PART 3 — SIGNATURE:
  HMAC-SHA256(
    base64Url(header) + "." + base64Url(payload),
    SECRET_KEY
  )
  
  SECRET_KEY = "my-very-secret-key-that-only-server-knows"
  
  If payload modified → Signature invalid → Server rejects!
  Without SECRET_KEY → Can't forge valid signature

IMPORTANT: JWT payload is ENCODED, not ENCRYPTED!
  Anyone can decode base64 and READ the payload
  Never put sensitive data (passwords, credit cards) in JWT!
  OK to put: user_id, role, company_id (non-sensitive)
  Signature only ensures INTEGRITY (data not modified), not CONFIDENTIALITY
```

---

### 1.3 JWT Verification Flow

```
CLIENT                              SERVER
  │                                    │
  │── POST /api/auth/login/ ──────────►│
  │   {email, password}                │ 1. Check credentials
  │                                    │ 2. Create JWT:
  │                                    │    header.payload.signature
  │◄── {access_token, refresh_token} ──│
  │                                    │
  │── GET /api/invoices/ ─────────────►│
  │   Authorization: Bearer {token}    │ 1. Extract token from header
  │                                    │ 2. Split into header.payload.signature
  │                                    │ 3. Compute: HMAC-SHA256(header.payload, SECRET_KEY)
  │                                    │ 4. Compare with token's signature
  │                                    │ 5. Match? → Valid
  │                                    │    No match? → 401 Invalid signature
  │                                    │ 6. Check exp claim: not expired?
  │                                    │ 7. Extract user_id → load user
  │◄── 200 OK {invoices} ─────────────│
  │                                    │

NO DATABASE LOOKUP for verification!
  All info in token → cryptographic verification → done
  Horizontal scaling: Any server can verify any token
```

---

### 1.4 Access Token + Refresh Token Pattern

```
WHY TWO TOKENS?

Access Token:
  Short-lived: 15 minutes
  Used: Every API request (Authorization header)
  If stolen: Attacker can use for 15 minutes MAX
  
Refresh Token:
  Long-lived: 30 days (or more)
  Used: Only to get new access token
  Stored: Securely (HttpOnly cookie or secure storage)
  Revocable: Stored in DB → can be invalidated

FLOW:
  ┌────────────────────────────────────────────────────────┐
  │ Login                                                   │
  │  POST /auth/login → access_token (15min) + refresh_token│
  └────────────────────────────────────────────────────────┘
  
  ┌────────────────────────────────────────────────────────┐
  │ Normal usage                                            │
  │  Every API call → Bearer {access_token}                │
  └────────────────────────────────────────────────────────┘
  
  ┌────────────────────────────────────────────────────────┐
  │ Access token expires (15 min)                           │
  │  POST /auth/refresh → {refresh_token} → new access_token│
  │  (Refresh token stays valid for 30 days)               │
  └────────────────────────────────────────────────────────┘
  
  ┌────────────────────────────────────────────────────────┐
  │ Logout                                                  │
  │  POST /auth/logout → Delete refresh_token from DB      │
  │  Future refresh attempts → Invalid (DB says "deleted") │
  └────────────────────────────────────────────────────────┘

SECURITY:
  Access token stolen?
    → Attacker has 15 minutes. Token expires. Problem solved.
  
  Refresh token stolen?
    → Attacker can keep refreshing forever!
    → Solution: Refresh token rotation + detection
    
REFRESH TOKEN ROTATION:
  Each refresh request → Issue NEW refresh token, invalidate OLD
  
  If attacker uses stolen refresh token:
    → Server sees the same token used twice!
    → First use by legitimate user → issued new RT
    → Second use by attacker with same RT → REJECT and flag!
    → Potentially revoke ALL sessions for this user (compromise detected)
```

---

### 1.5 HS256 vs RS256

```
HS256 (HMAC-SHA256) — Symmetric:
  Same key: Sign AND Verify
  
  Sign:    signature = HMAC(header.payload, SECRET_KEY)
  Verify:  HMAC(header.payload, SECRET_KEY) == signature?
  
  Pro: Simple, fast
  Con: All services that verify tokens need the SECRET_KEY
       If one service is compromised → key leaked → tokens forgeable
  
  Use: Single backend (one server signs AND verifies)

RS256 (RSA) — Asymmetric:
  PRIVATE key: Sign
  PUBLIC key:  Verify
  
  Sign:    signature = RSA_sign(header.payload, PRIVATE_KEY)
  Verify:  RSA_verify(header.payload, signature, PUBLIC_KEY)
  
  Pro: Distribute PUBLIC_KEY to all services — safe!
       Auth server has PRIVATE_KEY (only it can issue tokens)
       Other services have PUBLIC_KEY (can verify, can't issue)
  Con: Slower than HS256
       More complex key management
  
  Use: Microservices where auth service issues tokens
       Other services verify with public key (no secret sharing)
  
  Auth Server: Has PRIVATE_KEY → issues JWTs
  Service A, B, C: Have PUBLIC_KEY → verify JWTs (can't forge)

YOUNGMAN:
  HS256 (single backend, simpler)
  SECRET_KEY in environment variable (never in code!)
  
  NIROSKOS:
  HS256 (still single Django service)
  
  Hypothetical microservices:
  RS256 (auth service with private key, other services with public key)
```

---

### 1.6 JWT Implementation in Django

```python
# pip install djangorestframework-simplejwt

# settings.py
from datetime import timedelta

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=15),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=30),
    'ROTATE_REFRESH_TOKENS': True,       # Issue new refresh token on each refresh
    'BLACKLIST_AFTER_ROTATION': True,    # Invalidate old refresh token
    'UPDATE_LAST_LOGIN': True,
    
    'ALGORITHM': 'HS256',
    'SIGNING_KEY': settings.SECRET_KEY,  # From env variable, never hardcode!
    
    'AUTH_HEADER_TYPES': ('Bearer',),
    'AUTH_HEADER_NAME': 'HTTP_AUTHORIZATION',
    
    'USER_ID_FIELD': 'id',
    'USER_ID_CLAIM': 'user_id',
    
    # Custom claims
    'TOKEN_OBTAIN_SERIALIZER': 'myapp.serializers.CustomTokenObtainPairSerializer',
}

# Custom serializer to add extra claims to JWT payload
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        
        # Add custom claims
        token['email'] = user.email
        token['role'] = user.profile.role
        token['company_id'] = user.company_id
        token['tenant_id'] = user.company.tenant_id
        
        return token

# urls.py
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
    TokenBlacklistView,
)

urlpatterns = [
    path('auth/login/', TokenObtainPairView.as_view()),
    path('auth/refresh/', TokenRefreshView.as_view()),
    path('auth/logout/', TokenBlacklistView.as_view()),  # Blacklists refresh token
]

# In views — JWT is validated automatically by JWTAuthentication class
# Access user from request:
class InvoiceView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        # request.user is set by JWTAuthentication
        # request.auth is the JWT token itself
        
        # Access custom claims:
        company_id = request.auth.payload.get('company_id')
        
        invoices = Invoice.objects.filter(company_id=company_id)
        return Response(InvoiceSerializer(invoices, many=True).data)

# Token blacklisting (for logout + rotation):
# Requires: 'rest_framework_simplejwt.token_blacklist' in INSTALLED_APPS
# Stores blacklisted tokens in DB
# Cleanup: TokenBlacklist has management command to purge expired
```

---

### 1.7 Where to Store JWT on Client

```
OPTION 1: localStorage:
  Pros: Simple, persists across tabs
  Cons: XSS attack → script reads localStorage → token stolen!
  
  Never: localStorage if XSS is possible
  XSS = Cross-Site Scripting → malicious JS runs in user's browser

OPTION 2: sessionStorage:
  Pros: Cleared when tab closed
  Cons: Same XSS risk as localStorage
  
OPTION 3: HttpOnly Cookie:
  Pros: 
    JS CANNOT read HttpOnly cookies → XSS can't steal!
    Browser sends automatically with every request
  Cons:
    CSRF attack possible (browser sends cookie automatically to any request)
    Fix with: CSRF token + SameSite=Strict cookie flag
  
  RECOMMENDED for web apps:
  Set-Cookie: access_token={jwt}; HttpOnly; Secure; SameSite=Strict; Path=/
  
  Django:
  response.set_cookie(
      'access_token',
      access_token_string,
      httponly=True,
      secure=True,        # HTTPS only
      samesite='Strict',  # Only sent for same-site requests (CSRF protection)
      max_age=15*60       # 15 minutes
  )

OPTION 4: Memory (JavaScript variable):
  Pros: Can't be read by XSS (not in accessible storage)
  Cons: Lost on page refresh → need refresh token in HttpOnly cookie to recover
  
  Best practice for SPAs:
  access_token: Memory (JavaScript)
  refresh_token: HttpOnly cookie
  
  On refresh/page load:
  → Use refresh_token cookie to get new access_token
  → Store new access_token in memory
```

---

### 1.8 Stateless vs Stateful Session Comparison

```
STATEFUL SESSIONS (Traditional):
  Login → Session created in DB/Redis
  Session ID in cookie → Sent every request
  Server: Look up session → Find user → Process request
  
  Pros:
  ✓ Instant logout (delete session from DB)
  ✓ Server controls everything
  ✓ Small cookie (just ID, no payload)
  
  Cons:
  ✗ DB hit on every request
  ✗ Horizontal scaling: shared session store needed (Redis)
  ✗ Session store = SPOF (if Redis down → all users logged out)
  ✗ Doesn't work well for mobile/API clients

STATELESS JWT:
  Login → JWT issued
  JWT in header → Sent every request
  Server: Verify signature → Extract claims → Process request
  
  Pros:
  ✓ No DB hit for auth (just crypto verification)
  ✓ Any server can verify any token (horizontal scaling)
  ✓ Works for APIs, mobile apps, microservices
  ✓ Payload can contain user info (no extra lookup)
  
  Cons:
  ✗ Logout is hard (can't "delete" a valid token)
     → Solution: Token blacklist (DB table) or short expiry
  ✗ Payload visible (don't put sensitive data)
  ✗ Token revocation requires additional mechanism

HYBRID APPROACH (best of both):
  Access token: JWT (stateless, 15 min)
  Refresh token: Stored in DB (stateful, revocable)
  
  Regular requests: JWT (fast, no DB)
  Refresh/logout: DB lookup (revoke refresh token)
  
  This is what simple-jwt implements!
```

---

### 1.9 Ashish ke projects

```python
# Youngman JWT setup (simplified):

# Login → Returns both tokens
# Access token: 15 min, JWT, stateless
# Refresh token: 30 days, stored in DB (revocable)

# Access token payload:
{
    "user_id": 5,
    "email": "ashish@youngman.com",
    "company_id": 12,
    "role": "admin",
    "exp": 1705000000,
    "jti": "unique-id"
}

# Request flow:
# GET /api/invoices/ HTTP/1.1
# Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
#
# JWTAuthentication:
# 1. Extract token
# 2. Verify signature (no DB hit!)
# 3. Check expiry
# 4. Load user from user_id claim
# 5. request.user = user → view proceeds

# Token refresh (every 15 minutes):
# POST /api/auth/refresh/
# {"refresh": "eyJhbGc...long_refresh_token..."}
# → Returns new access_token
# → If ROTATE_REFRESH_TOKENS=True: also returns new refresh_token

# Logout:
# POST /api/auth/logout/
# {"refresh": "eyJhbGc..."}
# → Blacklists refresh token in DB
# → Future refreshes fail → user effectively logged out
# → Active access tokens still valid for up to 15 min (acceptable)
```

---

## PART 2: ENGLISH — Interviewer ko bolne ke liye

### 2.1 Definitions

> **JWT (JSON Web Token)**: A compact, URL-safe token format consisting of three Base64URL-encoded parts: header (algorithm), payload (claims), and signature. Self-contained — the server can verify the token without a database lookup.

> **Stateless Authentication**: Authentication where the server stores no session state. Each request includes a self-verifying token. The server verifies cryptographic signature rather than looking up session in storage.

> **Access Token**: Short-lived JWT (15 minutes) used in API requests. Stolen tokens have limited window of misuse.

> **Refresh Token**: Long-lived credential (30 days) stored securely, used only to obtain new access tokens. Revocable via database entry.

---

### 2.2 JWT Claims Reference

```
REGISTERED CLAIMS (standard):
  iss: Issuer (api.youngman.com)
  sub: Subject (user_id)
  aud: Audience (who token is for)
  exp: Expiration time (Unix timestamp)
  iat: Issued at time
  nbf: Not before time
  jti: JWT ID (unique ID, for blacklisting)

PUBLIC CLAIMS (application-defined):
  email, role, company_id, tenant_id, etc.
  
NEVER IN JWT:
  Password, credit card, SSN — payload is readable by anyone
```

---

### 2.3 Real Project Answer

> "In Youngman, we use JWT with the djangorestframework-simplejwt library. On login, we issue an access token (15-minute expiry) and a refresh token (30-day expiry). The access token payload contains user_id, company_id, and role — enough information for the server to make authorization decisions without a database lookup. We use HS256 signing with the SECRET_KEY from environment variables. The refresh token is stored in the database — this is our 'logout' mechanism: on logout, we blacklist the refresh token. We've also configured refresh token rotation (ROTATE_REFRESH_TOKENS=True) so each refresh gives a new refresh token and invalidates the old one, providing replay attack protection."

---

### 2.4 Common Follow-up Q&A

**Q1: How do you invalidate JWT tokens before expiry?**
> "Stateless JWTs can't be 'invalidated' in the traditional sense since there's no central state. Three approaches: (1) Short expiry — 15 minutes means stolen tokens have limited usefulness. (2) Token blacklist — maintain a DB/Redis set of invalidated `jti` claims. On each request, check if jti is blacklisted. Adds a DB lookup but enables instant invalidation. (3) Token version in user profile — user has `token_version` field; JWT includes it. On 'logout all devices', increment version. Server rejects tokens with old version. For our use case: short access token TTL + refresh token blacklisting (via simplejwt's TokenBlacklist) is sufficient."

**Q2: What is the difference between JWT and opaque tokens?**
> "A JWT is self-describing — it contains claims (user_id, role, expiry) encoded in the token itself. The server verifies the signature without any database lookup. An opaque token is a random string — meaningless on its own. The server must look up the opaque token in a database to find the associated user and permissions. Trade-offs: JWT = no DB lookup (faster, stateless, scales easily), but difficult to revoke. Opaque token = DB lookup on every request (slower), but instant revocation by deleting the DB record. Django's default TokenAuthentication uses opaque tokens. Simple-JWT uses JWTs."

**Q3: What security issues are specific to JWTs?**
> "Key issues: (1) Algorithm confusion attack — an attacker changes the alg header to 'none', removing the signature. Fix: always verify alg is what you expect; never accept 'none'. (2) Weak SECRET_KEY — short or guessable keys can be brute-forced. Use cryptographically random 256-bit key. (3) Information disclosure — JWT payload is readable (Base64 decoded). Never put sensitive data in payload. (4) Missing expiry validation — always check `exp` claim. (5) Missing signature verification — always verify! Python-jose and simplejwt do this correctly by default. (6) Token stored in localStorage — vulnerable to XSS. Use HttpOnly cookies. (7) Refresh token not rotated — allows token replay attacks."

---

## Interview Cheat Sheet

```
JWT Structure:
  header.payload.signature (Base64URL encoded)
  
  Header: {"alg": "HS256", "typ": "JWT"}
  Payload: {"user_id": 5, "role": "admin", "exp": 1705000000}
  Signature: HMAC-SHA256(header.payload, SECRET_KEY)

Key properties:
  - Self-contained (no DB lookup for verification)
  - Stateless (any server can verify)
  - Payload readable (NOT encrypted — don't put secrets)
  - Signature ensures integrity (can't modify without key)

Access + Refresh token pattern:
  Access: 15min, JWT, stateless verification
  Refresh: 30 days, stored in DB, revocable
  
  On expire: POST /auth/refresh → new access token
  On logout: Blacklist refresh token in DB

HS256 vs RS256:
  HS256: Symmetric (same key sign+verify) — single backend
  RS256: Asymmetric (private sign, public verify) — microservices

Token storage (web):
  Best: access_token in memory + refresh_token in HttpOnly cookie
  Acceptable: HttpOnly cookie (for both)
  BAD: localStorage (XSS vulnerable)

Revocation strategies:
  1. Short TTL (15min) — stolen tokens expire soon
  2. jti blacklist in Redis/DB — instant revocation
  3. User token_version — invalidate all user's tokens

simplejwt config:
  ACCESS_TOKEN_LIFETIME: 15 minutes
  REFRESH_TOKEN_LIFETIME: 30 days
  ROTATE_REFRESH_TOKENS: True
  BLACKLIST_AFTER_ROTATION: True
```
