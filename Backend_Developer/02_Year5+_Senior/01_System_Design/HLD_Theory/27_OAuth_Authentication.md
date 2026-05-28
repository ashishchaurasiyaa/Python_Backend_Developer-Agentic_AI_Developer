# OAuth Authentication — OAuth 2.0 Flows

## Quick Reference Card
```
OAuth 2.0      → Authorization framework — "Login with Google/Facebook" — DELEGATED auth
Not AuthN      → OAuth = AuthZ (who you delegate to), OpenID Connect adds AuthN on top
Flows          → Authorization Code (web), PKCE (mobile), Client Credentials (server-server), Implicit (deprecated)
Roles          → Resource Owner (user), Client (your app), Auth Server (Google), Resource Server (API)
Tokens         → Access token (API calls) + optionally Refresh token + ID token (OpenID)
Interview hook → "SAP HANA OAuth client_credentials flow | Social login = Authorization Code + PKCE"
```

---

## PART 1: HINGLISH — Samjhne ke liye

### 1.1 OAuth Problem Statement

**Analogy: Hotel valet parking**

Tum hotel pe aaye, valet parking chahiye. Tum apni CAR ki MASTER KEY nahi doge valets ko (password sharing = bad). Tum ek VALET KEY doge — sirf ignition chalane ke liye, boot open nahi hoga, glovebox lock rahega.

```
WITHOUT OAUTH (password sharing anti-pattern):
  User: "Mujhe third-party app ko access chahiye meri Google Drive files"
  OLD way: "Enter your Google password in our app"
  
  PROBLEM:
  - Third party has your Google password!
  - If third party is hacked → your Google password compromised
  - To revoke: Change your Google password (affects ALL apps)
  - Third party has FULL access (not just files you wanted)

WITH OAUTH:
  User authorizes: "App X can access my Google Drive (read-only)"
  Google issues: ACCESS TOKEN to App X (limited scope: drive.readonly)
  App X uses token to access Drive (never had your password!)
  
  To revoke: Revoke App X's token (other apps unaffected)
  Scope: Only what was explicitly granted
```

---

### 1.2 OAuth 2.0 Roles

```
4 ROLES:

1. RESOURCE OWNER (User):
   Tum — jo data ka owner ho aur authorize karta hai
   "I allow this app to access my..."

2. CLIENT (Your Application):
   Jo app access maang raha hai
   Niroskos app, Youngman dashboard

3. AUTHORIZATION SERVER:
   Identity verify karta hai + tokens issue karta hai
   Google, Facebook, GitHub, or your own OAuth server

4. RESOURCE SERVER:
   Protected resources/APIs
   Google Drive API, GitHub API, or your own API

RELATIONSHIP:
  Resource Owner → Authorizes → Client
  Client → Gets token from → Authorization Server
  Client → Uses token to access → Resource Server
  Resource Server → Validates token with → Authorization Server
```

---

### 1.3 Authorization Code Flow (Web Apps — Most Common)

```
SCENARIO: "Login with Google" on Niroskos website

STEP 1: User clicks "Login with Google"
  Niroskos → Redirect user to Google's Auth Server
  
  GET https://accounts.google.com/o/oauth2/v2/auth?
    response_type=code
    &client_id=niroskos_client_id
    &redirect_uri=https://niroskos.com/auth/google/callback/
    &scope=openid+email+profile
    &state=random_csrf_token_xyz
  
  state parameter = CSRF protection (random value stored in session)

STEP 2: User logs in on Google (not your server!)
  Google shows: "Niroskos wants to access your: email address"
  User clicks: "Allow"

STEP 3: Google redirects back with CODE
  GET https://niroskos.com/auth/google/callback/?
    code=4/0AeaYSH...short_code...
    &state=random_csrf_token_xyz

STEP 4: Niroskos exchanges CODE for TOKEN (server-side)
  POST https://oauth2.googleapis.com/token
  Content-Type: application/x-www-form-urlencoded
  
  code=4/0AeaYSH...
  &client_id=niroskos_client_id
  &client_secret=niroskos_client_secret  ← Secret! Server-side only
  &redirect_uri=https://niroskos.com/auth/google/callback/
  &grant_type=authorization_code

STEP 5: Google returns tokens
  {
    "access_token": "ya29.a0AfH6...",
    "expires_in": 3600,
    "token_type": "Bearer",
    "id_token": "eyJhbGci...",  ← OpenID Connect — user identity
    "refresh_token": "1//0ggQ..."
  }

STEP 6: Niroskos uses ID token to identify user
  Decode id_token (JWT) → get email, name, Google user ID
  Create or find user in Niroskos DB
  Create Niroskos session/JWT for user

WHY TWO STEPS (code → token)?
  Code is short-lived (1-2 minutes) and single-use
  Exchange happens server-side (client_secret not in browser!)
  If code intercepted → useless without client_secret
  This is the SECURITY of Authorization Code flow
```

---

### 1.4 PKCE — Authorization Code for Mobile/SPA

```
PROBLEM WITH MOBILE APPS:
  Authorization Code needs client_secret for token exchange
  Mobile app → client_secret in APK → Anyone can decompile and extract!
  Mobile apps can't have client_secret (it would be public)

PKCE (Proof Key for Code Exchange):
  Replaces client_secret with dynamically generated code challenge
  
  1. App generates: code_verifier (random string, 43-128 chars)
  2. App computes: code_challenge = BASE64URL(SHA256(code_verifier))
  3. Auth request includes: code_challenge + code_challenge_method=S256
  4. After getting code, token exchange includes: code_verifier
  5. Auth server: SHA256(code_verifier) must equal stored code_challenge
  
  If attacker intercepts code → They don't have code_verifier → Useless!
  code_verifier never transmitted initially → can't be intercepted
  
  FLOW (same as Auth Code + code_challenge in step 1):
  
  App: Generate code_verifier = "dBjftJeZ4CVP-mB92K27uhbUJU1p1r..."
       code_challenge = BASE64URL(SHA256(code_verifier)) = "E9Melhoa02..."
  
  Auth Request:
  GET /authorize?
    ...
    &code_challenge=E9Melhoa02...
    &code_challenge_method=S256
  
  Token Exchange:
  POST /token
  code=...
  &code_verifier=dBjftJeZ4CVP-mB92K27uhbUJU1p1r...  ← verifier sent now
  (No client_secret needed!)

Django + PKCE (python-social-auth or allauth handles this automatically)
```

---

### 1.5 Client Credentials Flow — Machine to Machine

```
SCENARIO: Youngman backend → SAP HANA API
  No user involved — machine-to-machine
  "Our backend service accessing their API"

FLOW:
  Youngman Server → POST /token → SAP Auth Server
  
  POST https://sap.auth.server/oauth/token
  Authorization: Basic base64(client_id:client_secret)
  Content-Type: application/x-www-form-urlencoded
  
  grant_type=client_credentials
  &scope=sap_api_read sap_api_write
  
  SAP Auth Server → 200 OK
  {
    "access_token": "eyJhbGci...",
    "token_type": "Bearer",
    "expires_in": 43199  ← 12 hours
  }
  
  Now Youngman uses access_token for all SAP API calls:
  GET https://sap.api.server/invoices/
  Authorization: Bearer eyJhbGci...

YOUNGMAN IMPLEMENTATION:
  class SAPOAuthClient:
      def __init__(self):
          self.redis = redis.Redis()
          self.token_key = 'sap:access_token'
      
      def get_token(self):
          cached = self.redis.get(self.token_key)
          if cached:
              return cached.decode()
          
          return self._fetch_new_token()
      
      def _fetch_new_token(self):
          credentials = base64.b64encode(
              f"{settings.SAP_CLIENT_ID}:{settings.SAP_CLIENT_SECRET}".encode()
          ).decode()
          
          response = requests.post(
              settings.SAP_TOKEN_URL,
              headers={"Authorization": f"Basic {credentials}"},
              data={"grant_type": "client_credentials"},
              timeout=10
          )
          response.raise_for_status()
          token_data = response.json()
          
          # Cache token (expire 5 minutes before actual expiry)
          ttl = token_data['expires_in'] - 300
          self.redis.setex(self.token_key, ttl, token_data['access_token'])
          
          return token_data['access_token']
```

---

### 1.6 OAuth vs OpenID Connect (OIDC)

```
OAuth 2.0: AUTHORIZATION framework
  "Can this app access my resources?"
  Returns: Access token (for API access)
  
  Problem: OAuth 2.0 doesn't say HOW to authenticate user
           Different providers implement user identity differently

OpenID Connect (OIDC): AUTHENTICATION layer on top of OAuth 2.0
  "Who is this user?" + OAuth
  Returns: Access token + ID token (JWT with user identity)
  
  ID Token contains (standardized claims):
  {
    "iss": "https://accounts.google.com",
    "sub": "1234567890",     ← Unique user ID at Google
    "email": "user@gmail.com",
    "name": "Ashish Kumar",
    "picture": "https://...",
    "email_verified": true,
    "iat": 1516239022,
    "exp": 1516242622
  }

OIDC Standard Scopes:
  openid: Request OIDC (ID token) — required for OIDC
  profile: name, picture, website
  email: email, email_verified
  address: address
  phone: phone_number

"Login with Google" = OAuth 2.0 + OpenID Connect
  OAuth: Delegates authorization
  OIDC: Provides standardized user identity

DJANGO IMPLEMENTATION:
  # Using python-social-auth or django-allauth
  # pip install social-auth-app-django
  
  AUTHENTICATION_BACKENDS = [
      'social_core.backends.google.GoogleOAuth2',
      'django.contrib.auth.backends.ModelBackend',
  ]
  
  SOCIAL_AUTH_GOOGLE_OAUTH2_KEY = settings.GOOGLE_CLIENT_ID
  SOCIAL_AUTH_GOOGLE_OAUTH2_SECRET = settings.GOOGLE_CLIENT_SECRET
  SOCIAL_AUTH_GOOGLE_OAUTH2_SCOPE = ['openid', 'email', 'profile']
  
  # urls.py
  urlpatterns += social_django.urls.urlpatterns
  
  # After Google login:
  # python-social-auth automatically creates User with email from ID token
  # Associates Google social auth with Django user
  # Returns Django session or JWT (configure pipeline)
```

---

### 1.7 OAuth Flows Summary

```
FLOW              USE CASE                    SECRET SHARING
──────────────────────────────────────────────────────────────
Authorization     Web apps (server-side)       client_secret safe
Code              Niroskos "Login with Google"  (server-side only)

Auth Code + PKCE  Mobile apps, SPAs            No secret needed
                  React Native, Flutter

Client            Machine-to-machine           client_secret
Credentials       Youngman → SAP HANA           (server-side)

Device Code       IoT, TV apps                 No browser
                  "Enter code at URL"

Implicit          DEPRECATED (replaced by PKCE) Access token in URL
                  Never use for new apps         (insecure)
                  
Password/ROPC     DEPRECATED (legacy only)      User password to app
                  Never use (you get the        (against OAuth purpose)
                  user's password directly)
```

---

### 1.8 OAuth Security Best Practices

```
1. STATE PARAMETER (CSRF protection):
   Always include state = random value stored in session
   Verify returned state matches → prevents CSRF
   
   If attacker crafts malicious auth URL:
   → state won't match → reject → safe

2. REDIRECT URI VALIDATION:
   Auth server must EXACTLY match redirect_uri
   No wildcards: NOT "https://yourapp.com/*"
   YES: "https://yourapp.com/auth/callback/"
   Prevents: Attacker registering similar domain

3. PKCE FOR PUBLIC CLIENTS:
   Mobile apps, SPAs → Always use PKCE
   No exceptions — protects against authorization code interception

4. HTTPS EVERYWHERE:
   All OAuth flows must use HTTPS
   Authorization codes in URLs are one-time-use but still sensitive

5. ACCESS TOKEN SCOPE MINIMIZATION:
   Request only scopes you actually need
   NOT: scope=* (everything)
   YES: scope=drive.readonly (just what you need)
   Principle of least privilege

6. SHORT ACCESS TOKEN LIFETIME:
   Google default: 1 hour
   Sensitive APIs: 15-30 minutes
   Refresh tokens: Longer, but rotated

7. CLIENT SECRET SECURITY:
   Never in client-side code (JS, mobile apps)
   Environment variables, not hardcoded
   Different secrets per environment (dev/staging/prod)
```

---

## PART 2: ENGLISH — Interviewer ko bolne ke liye

### 2.1 Definitions

> **OAuth 2.0**: An authorization framework that enables third-party applications to obtain limited access to a user's resources on another service, without exposing the user's credentials. Defines 4 roles (Resource Owner, Client, Authorization Server, Resource Server) and several grant flows.

> **OpenID Connect (OIDC)**: An identity layer built on top of OAuth 2.0. Standardizes user authentication by adding an ID Token (JWT) containing user identity claims. Enables "Login with Google/Facebook" functionality with standardized user information.

> **Authorization Code Flow**: The most secure OAuth flow for server-side web apps. Authorization code is exchanged server-side (using client_secret) for tokens — code interception without client_secret is useless.

---

### 2.2 OAuth Flows Comparison

| Flow | App Type | Client Secret | User Interaction |
|------|----------|---------------|-----------------|
| Authorization Code | Web apps (server-side) | Required | Yes (consent screen) |
| Auth Code + PKCE | Mobile, SPA | Not needed | Yes (consent screen) |
| Client Credentials | Server-to-server | Required | No (no user) |
| Device Code | IoT, TV | Required | Yes (enter code) |
| Implicit | DEPRECATED | Not needed | Yes — don't use |
| Password (ROPC) | DEPRECATED | Required | Yes — don't use |

---

### 2.3 OAuth vs Simple JWT (Internal)

```
When to use OAuth 2.0:
  - Third-party integrations (Google, GitHub login)
  - Delegating access to external service
  - Multiple apps sharing same auth server
  - Need fine-grained scope control
  - Standard compliance required

When to use simple JWT (internal):
  - Single app, your own users
  - You control both client and server
  - Simple use case (login to your own app)
  - Less infrastructure overhead

Youngman uses both:
  - Internal user login: Simple JWT (Django simplejwt)
  - SAP HANA access: OAuth 2.0 Client Credentials flow
  - Social login (if added): OAuth 2.0 + OIDC (python-social-auth)
```

---

### 2.4 Real Project Answer

> "In Youngman, we use OAuth in the Client Credentials flow for SAP HANA API access — our backend is the client, SAP's auth server issues tokens, and the SAP API is the resource server. We exchange our client_id and client_secret for a Bearer token, which we cache in Redis with a TTL 5 minutes before actual expiry. All SAP API calls use this cached token. For user-facing authentication, we use our own JWT system (simplejwt) — a custom OAuth server isn't needed when we control both client and server. If we were to add 'Login with Google', we'd use python-social-auth with the Authorization Code + PKCE flow — PKCE is now best practice even for server-side apps per OAuth 2.1 RFC."

---

### 2.5 Common Follow-up Q&A

**Q1: Why was the Implicit Flow deprecated?**
> "The Implicit Flow returned the access token directly in the URL fragment (e.g., `#access_token=eyJ...`). Two problems: (1) URL fragments are stored in browser history, potentially exposing tokens. (2) Access tokens in URLs can be leaked via the HTTP Referer header. The Authorization Code + PKCE flow solves both issues — no access token in the URL, and code interception is prevented by the PKCE verifier. OAuth 2.1 (draft) makes PKCE mandatory and removes Implicit entirely."

**Q2: What is the purpose of the state parameter in OAuth?**
> "The state parameter is a CSRF protection mechanism. Before redirecting to the authorization server, your application generates a random value, stores it in the user's session, and includes it as the `state` parameter in the auth request. When the user is redirected back after authorization, the auth server returns the same state value. Your application verifies that the returned state matches what it stored. If it doesn't match, the request is rejected — this prevents CSRF attacks where an attacker tricks a user into authorizing malicious requests."

**Q3: How does token revocation work in OAuth?**
> "OAuth 2.0 defines a Token Revocation endpoint (RFC 7009): `POST /revoke` with the token and token type hint. Calling this endpoint asks the authorization server to mark the token as invalid. For opaque tokens, the auth server simply removes it from its database. For JWT access tokens — which are self-contained — revocation is harder: the auth server can maintain a blacklist that resource servers check, but this adds latency. The practical solution is short-lived access tokens (15 minutes) so even if revocation fails, the token expires quickly. Long-lived refresh tokens should use proper revocation. This is why the access+refresh token split is valuable — you can revoke long-lived refresh tokens reliably."

---

## Interview Cheat Sheet

```
OAuth 2.0 Roles:
  Resource Owner: User who owns the data
  Client: Your app (requesting access)
  Authorization Server: Issues tokens (Google, GitHub, or your own)
  Resource Server: API being accessed

Authorization Code Flow (web):
  1. Redirect user to auth server
  2. User logs in + consents
  3. Auth server redirects back with code
  4. Server exchanges code + client_secret for tokens
  5. Use access_token for API calls

PKCE (mobile/SPA):
  code_verifier (random) → SHA256 → code_challenge
  Auth request: send code_challenge
  Token exchange: send code_verifier (no client_secret)

Client Credentials (machine-to-machine):
  POST /token with client_id + client_secret
  No user interaction
  Returns: access_token
  Use: Service-to-service (Youngman → SAP)

OAuth vs OIDC:
  OAuth: Authorization (can this app access my resources?)
  OIDC: Authentication + OAuth (who is this user?)
  OIDC adds: ID Token (JWT with user claims)

Security essentials:
  state parameter: CSRF protection
  Redirect URI: Exact match only
  PKCE: Required for public clients
  HTTPS: Mandatory for all flows
  Scope minimization: Request only what you need

My project:
  SAP HANA: Client Credentials flow
    → client_id + client_secret → access_token → cache in Redis
  User login: simplejwt (own auth server, no OAuth needed)
  Social login: Would use Authorization Code + PKCE (python-social-auth)
```
