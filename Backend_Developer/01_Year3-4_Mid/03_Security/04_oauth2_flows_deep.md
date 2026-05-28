# OAuth2 Flows Deep Dive — All 6 Flows + PKCE + OIDC

## Quick Concepts

**WHAT:**
- **OAuth2** = Authorization framework (NOT authentication — that's OIDC)
- **OIDC** = OpenID Connect — authentication layer on top of OAuth2
- **Access Token** = Short-lived token for API access
- **Refresh Token** = Long-lived token to get new access tokens
- **Authorization Server** = Issues tokens (Auth0, Cognito, Keycloak)
- **Resource Server** = Your API that validates tokens
- **Client** = Application requesting tokens (web, mobile, SPA, CLI)
- **PKCE** = Proof Key for Code Exchange (security for public clients)

**WHY OAuth2 over other auth:**
- ✅ Industry standard (interoperable)
- ✅ Delegation (Google login = "I trust Google's auth")
- ✅ Scoped permissions (user can grant partial access)
- ✅ Token rotation built-in
- ✅ Multiple flows for different client types

**HOW OAuth2 actors interact:**
```
┌──────────┐                              ┌──────────────────────┐
│  User    │                              │ Authorization Server │
│ (Browser)│                              │   (Auth0, Cognito)   │
└────┬─────┘                              └──────────┬───────────┘
     │                                               │
     │ 1. Login + Consent                            │
     ├──────────────────────────────────────────────►│
     │                                               │
     │ 2. Auth code (redirect)                       │
     │◄──────────────────────────────────────────────┤
     │                                               │
     │ 3. Code to client                             │
     ↓                                               │
┌──────────┐    4. Exchange code+secret for token    │
│  Client  │────────────────────────────────────────►│
│ (Backend)│◄────────────────────────────────────────┤
└────┬─────┘    5. Access token + Refresh token     │
     │                                               │
     │ 6. API call with Bearer token                 │
     ↓                                               │
┌──────────────────┐                                 │
│ Resource Server  │  7. Validate token (JWKS)       │
│  (Your API)      │────────────────────────────────►│
└──────────────────┘                                 │
```

---

## Interview Questions & Answers

### Q1: OAuth2 ke 6 flows kaun se hain? Kab kya use karein?

**Answer:**

**WHAT:** OAuth2 defines multiple flows for different client types.

**HOW — Decision matrix:**

| Flow | When to Use | Example | Security |
|---|---|---|---|
| **Authorization Code** | Web app with backend | Traditional Django app | ✅ High |
| **Authorization Code + PKCE** | SPA, mobile app | React, iOS, Android | ✅ High |
| **Client Credentials** | Service-to-service | Microservice → microservice | ✅ High |
| **Refresh Token** | Renew access token | All flows | ✅ High |
| **Device Code** | TV, CLI, IoT | Smart TV, GitHub CLI | ✅ Medium |
| **Implicit** | ❌ DEPRECATED | (old SPAs) | ❌ Low |
| **Password (ROPC)** | ❌ AVOID | (legacy migration only) | ❌ Low |

**WHY Implicit is deprecated:**
- Access token in URL fragment → exposed in browser history, referrer
- No client secret = no authentication of client
- PKCE solves these issues

---

### Q2: Authorization Code Flow with PKCE explain karo — kaise kaam karta hai?

**Answer:**

**WHAT:** PKCE = Proof Key for Code Exchange. Prevents authorization code interception.

**WHY PKCE:**
- Public clients (mobile, SPA) can't safely store `client_secret`
- Without PKCE: stolen code can be exchanged for tokens
- With PKCE: stolen code useless without `code_verifier`

**HOW — Step-by-step:**

```python
# ─── Step 1: Client generates code_verifier + code_challenge ──
import secrets
import hashlib
import base64

def generate_pkce_pair():
    """
    INTERVIEW: code_verifier = random string
                code_challenge = SHA256(verifier) base64url-encoded
    """
    # Random 32-bytes → base64url
    code_verifier = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode().rstrip("=")

    # SHA256 hash → base64url
    challenge_bytes = hashlib.sha256(code_verifier.encode()).digest()
    code_challenge = base64.urlsafe_b64encode(challenge_bytes).decode().rstrip("=")

    return code_verifier, code_challenge


# ─── Step 2: Redirect user to Auth Server ────────────────────
verifier, challenge = generate_pkce_pair()

# Store verifier in session (localStorage for SPA, secure session for mobile)
session["pkce_verifier"] = verifier

# Build authorization URL
import urllib.parse
auth_url = "https://auth.example.com/oauth/authorize?" + urllib.parse.urlencode({
    "response_type": "code",
    "client_id": "my-spa-client",
    "redirect_uri": "https://app.example.com/callback",
    "scope": "openid profile email",
    "state": secrets.token_urlsafe(16),       # CSRF protection
    "code_challenge": challenge,
    "code_challenge_method": "S256",          # SHA256 (NOT plain)
})
# Redirect browser to auth_url


# ─── Step 3: User logs in + consents at Auth Server ──────────
# Auth server redirects back: https://app.example.com/callback?code=AUTH_CODE&state=STATE


# ─── Step 4: Exchange code for tokens (WITH verifier) ────────
import httpx

async def exchange_code(code: str, verifier: str):
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://auth.example.com/oauth/token",
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": "https://app.example.com/callback",
                "client_id": "my-spa-client",
                "code_verifier": verifier,    # ⭐ Server verifies SHA256(verifier) == challenge
            }
        )
        return response.json()
        # {
        #   "access_token": "eyJhbGc...",
        #   "refresh_token": "...",
        #   "id_token": "eyJhbGc...",    # OIDC
        #   "token_type": "Bearer",
        #   "expires_in": 3600
        # }
```

**HOW — Why this is secure:**
```
Attacker scenario:
1. Attacker intercepts auth code (somehow)
2. Tries to exchange code for token
3. BUT needs code_verifier (only client knows)
4. Without verifier → Auth server rejects ❌
```

---

### Q3: Client Credentials Flow — service-to-service auth?

**Answer:**

**WHAT:** Service authenticates as itself (no user).

**WHY:**
- Backend → backend communication
- Cron jobs
- Server-to-server APIs
- No user context needed

**HOW:**

```python
import httpx
import time
import asyncio
from typing import Optional

class ClientCredentialsTokenProvider:
    """
    INTERVIEW: Caches token + auto-refreshes before expiry.
    Used for service-to-service authentication.
    """
    def __init__(self, token_url: str, client_id: str, client_secret: str, scope: str):
        self.token_url = token_url
        self.client_id = client_id
        self.client_secret = client_secret
        self.scope = scope
        self._token: Optional[str] = None
        self._expires_at: float = 0
        self._lock = asyncio.Lock()

    async def get_token(self) -> str:
        async with self._lock:
            # Return cached if still valid (60s buffer)
            if self._token and time.time() < self._expires_at - 60:
                return self._token

            # Fetch new token
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.token_url,
                    data={
                        "grant_type": "client_credentials",      # ⭐ Different grant
                        "client_id": self.client_id,
                        "client_secret": self.client_secret,     # ⭐ Confidential
                        "scope": self.scope,                     # e.g., "users:read"
                    },
                    auth=(self.client_id, self.client_secret),   # OR basic auth
                )
                response.raise_for_status()
                data = response.json()

            self._token = data["access_token"]
            self._expires_at = time.time() + data["expires_in"]
            return self._token


# Usage in service
token_provider = ClientCredentialsTokenProvider(
    token_url="https://auth.example.com/oauth/token",
    client_id="order-service",
    client_secret="...",          # In Secrets Manager
    scope="users:read users:write"
)

# In any API call
token = await token_provider.get_token()
headers = {"Authorization": f"Bearer {token}"}
response = await client.get("https://user-service/users/123", headers=headers)
```

**Critical:** Never expose `client_secret` to browsers (confidential clients only).

---

### Q4: Refresh Token Flow — rotation strategy?

**Answer:**

**WHAT:** Exchange refresh token for new access token (without re-login).

**WHY rotation:**
- ✅ Refresh tokens are long-lived (days/months)
- ✅ If stolen, attacker can keep generating access tokens
- ✅ Rotation: each use issues NEW refresh + invalidates old
- ✅ Detect theft: old refresh used twice = revoke ALL tokens

**HOW — Refresh token rotation:**

```python
# Client side
class TokenManager:
    def __init__(self, refresh_token: str):
        self.refresh_token = refresh_token
        self.access_token = None
        self.access_expires_at = 0

    async def get_access_token(self) -> str:
        # Return cached if valid
        if self.access_token and time.time() < self.access_expires_at - 30:
            return self.access_token

        # Refresh
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://auth.example.com/oauth/token",
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": self.refresh_token,
                    "client_id": "my-client",
                    "client_secret": "...",            # Confidential only
                }
            )
            data = response.json()

        # ⭐ ROTATION: server returns NEW refresh token
        self.access_token = data["access_token"]
        self.access_expires_at = time.time() + data["expires_in"]

        # ⭐ Replace old refresh with new
        if "refresh_token" in data:
            old_refresh = self.refresh_token
            self.refresh_token = data["refresh_token"]
            # Old refresh now INVALIDATED on server
            await self._persist_refresh_token(self.refresh_token)

        return self.access_token


# Server side (FastAPI example)
@app.post("/oauth/token")
async def token_endpoint(grant_type: str = Form(...), refresh_token: str = Form(None)):
    if grant_type == "refresh_token":
        # 1. Validate refresh token exists + not blacklisted
        token_record = await db.get_refresh_token(refresh_token)
        if not token_record or token_record.revoked:
            raise HTTPException(401, "Invalid refresh token")

        # 2. DETECT REUSE (stolen token scenario)
        if token_record.used_at:
            # Token was already used once → THEFT DETECTED
            # Revoke ALL refresh tokens for this user
            await db.revoke_all_user_tokens(token_record.user_id)
            await alert_security_team(token_record.user_id, "Refresh token reuse detected")
            raise HTTPException(401, "Token reused — all sessions revoked")

        # 3. Mark old refresh as used
        await db.mark_refresh_used(refresh_token)

        # 4. Issue new pair
        new_access = create_access_token(token_record.user_id, ttl=900)        # 15 min
        new_refresh = create_refresh_token(token_record.user_id, ttl=604800)   # 7 days

        # 5. Link new refresh to user
        await db.save_refresh_token(new_refresh, token_record.user_id)

        return {
            "access_token": new_access,
            "refresh_token": new_refresh,
            "expires_in": 900,
            "token_type": "Bearer",
        }
```

---

### Q5: Device Code Flow — TV, CLI ke liye kaise kaam karta hai?

**Answer:**

**WHAT:** Auth for devices without browser (TV, CLI, IoT).

**WHY:**
- TVs can't easily type passwords
- CLI tools can't open browser reliably
- IoT devices may lack UI

**HOW — Flow:**

```
Step 1: CLI requests device + user code
CLI → Auth Server: POST /device/code
                   ↓
                   { device_code, user_code, verification_uri, expires_in }

Step 2: Show user_code to user
CLI displays: "Go to https://auth.com/device and enter: ABCD-1234"

Step 3: User opens URL on phone/browser
       Enters ABCD-1234, logs in, approves

Step 4: CLI polls for token
CLI → Auth Server: POST /token (with device_code)
       (every 5 seconds, until success or expiry)
                   ↓
                   { access_token, refresh_token }
```

**HOW — Python CLI implementation:**

```python
import time
import httpx
import sys

async def device_flow_login(client_id: str):
    """
    INTERVIEW: Device flow for CLI tools (like gh CLI).
    """
    # Step 1: Request device code
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://auth.example.com/oauth/device/code",
            data={
                "client_id": client_id,
                "scope": "read:user write:user",
            }
        )
        data = response.json()
        # {
        #   "device_code": "GmRhmhcxhwAzkoEqiMEg_DnyEysNkuNhszIySk9eS",
        #   "user_code": "WDJB-MJHT",
        #   "verification_uri": "https://example.com/device",
        #   "expires_in": 900,
        #   "interval": 5
        # }

    device_code = data["device_code"]
    user_code = data["user_code"]
    verification_uri = data["verification_uri"]
    interval = data["interval"]
    expires_in = data["expires_in"]

    # Step 2: Display to user
    print(f"\n📱 Please visit: {verification_uri}")
    print(f"🔑 Enter code: {user_code}\n")

    # Optionally open browser
    import webbrowser
    webbrowser.open(verification_uri)

    # Step 3: Poll for token
    start_time = time.time()
    while time.time() - start_time < expires_in:
        await asyncio.sleep(interval)

        async with httpx.AsyncClient() as client:
            token_response = await client.post(
                "https://auth.example.com/oauth/token",
                data={
                    "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
                    "device_code": device_code,
                    "client_id": client_id,
                }
            )
            result = token_response.json()

        # Possible responses:
        if "access_token" in result:
            print("✅ Authenticated!")
            return result

        error = result.get("error")
        if error == "authorization_pending":
            continue                              # User hasn't approved yet
        elif error == "slow_down":
            interval += 5                         # Server wants us to slow down
        elif error == "expired_token":
            print("❌ Code expired — try again")
            return None
        elif error == "access_denied":
            print("❌ User denied access")
            return None
        else:
            print(f"❌ Error: {error}")
            return None

    print("⏰ Timed out")
    return None
```

---

### Q6: OIDC (OpenID Connect) kya hai? OAuth2 se kaise different?

**Answer:**

**WHAT:**
- **OAuth2** = Authorization (what can you do?)
- **OIDC** = OAuth2 + Authentication (who are you?)

**WHY both needed:**
- Pure OAuth2 only authorizes API access
- OIDC adds **ID Token** with user identity (email, name, picture)

**HOW — Differences:**

| | OAuth2 | OIDC |
|---|---|---|
| Purpose | Authorization | Authentication + Authorization |
| Returns | Access token | Access token + **ID token** |
| User info | Not standardized | `/userinfo` endpoint |
| ID Token | ❌ | ✅ JWT with claims |
| Scopes | Custom | Custom + `openid`, `profile`, `email` |
| Discovery | ❌ | `/.well-known/openid-configuration` |

**HOW — ID Token structure:**

```python
import jwt

# Sample ID token (decoded)
id_token = jwt.decode(id_token_jwt, options={"verify_signature": False})

# {
#   "iss": "https://auth.example.com",           # Issuer
#   "sub": "auth0|abc123",                       # Subject (user ID)
#   "aud": "my-client-id",                       # Audience (client)
#   "exp": 1736000000,                           # Expires at
#   "iat": 1735996400,                           # Issued at
#   "nonce": "random-value",                     # CSRF protection
#   "email": "alice@example.com",
#   "email_verified": true,
#   "name": "Alice Smith",
#   "picture": "https://...",
#   "given_name": "Alice",
#   "family_name": "Smith",
# }


# Server-side ID token validation
import jwt
from jwt import PyJWKClient

def validate_id_token(id_token: str, expected_audience: str):
    """
    INTERVIEW: ID token validation steps.
    """
    # 1. Fetch signing keys from JWKS endpoint
    jwks_client = PyJWKClient("https://auth.example.com/.well-known/jwks.json")
    signing_key = jwks_client.get_signing_key_from_jwt(id_token)

    # 2. Decode + verify
    payload = jwt.decode(
        id_token,
        signing_key.key,
        algorithms=["RS256"],
        audience=expected_audience,             # MUST match
        issuer="https://auth.example.com",      # MUST match
    )

    # 3. Additional checks
    if payload.get("email_verified") is False:
        raise ValueError("Email not verified")

    return payload
```

**HOW — OIDC Discovery:**

```python
import httpx

async def discover_oidc_config(issuer: str):
    """
    INTERVIEW: OIDC auto-discovery (no hardcoding URLs).
    """
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{issuer}/.well-known/openid-configuration")
        config = response.json()

    return {
        "auth_url": config["authorization_endpoint"],
        "token_url": config["token_endpoint"],
        "userinfo_url": config["userinfo_endpoint"],
        "jwks_url": config["jwks_uri"],
        "issuer": config["issuer"],
        "supported_scopes": config.get("scopes_supported", []),
    }
```

---

### Q7: Token Introspection (RFC 7662) — kab use karein?

**Answer:**

**WHAT:** Endpoint to check if token is valid + get metadata.

**WHY:**
- Opaque tokens (not JWT) need server lookup
- Real-time revocation check
- Get scopes/metadata for token

**HOW:**

```python
import httpx

async def introspect_token(token: str, client_id: str, client_secret: str):
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://auth.example.com/oauth/introspect",
            data={"token": token},
            auth=(client_id, client_secret),
        )
        result = response.json()

    # {
    #   "active": true,                  # ⭐ Most important
    #   "scope": "read:users write:users",
    #   "client_id": "user-service",
    #   "username": "alice",
    #   "exp": 1736000000,
    #   "sub": "auth0|abc123",
    # }

    return result


# Usage in API middleware
async def verify_token_middleware(request: Request):
    token = request.headers.get("Authorization", "").replace("Bearer ", "")
    introspection = await introspect_token(token, CLIENT_ID, CLIENT_SECRET)

    if not introspection.get("active"):
        raise HTTPException(401, "Token inactive/revoked")

    # Check scopes
    required_scope = "users:read"
    if required_scope not in introspection.get("scope", "").split():
        raise HTTPException(403, f"Missing scope: {required_scope}")
```

**JWT vs Introspection trade-offs:**

| | JWT (self-contained) | Introspection (opaque) |
|---|---|---|
| **Performance** | Fast (local validation) | Slow (network call) |
| **Revocation** | Hard (need blacklist) | Easy (real-time) |
| **Privacy** | Claims visible | Opaque token |
| **Cache** | Easy | Cache introspection result (short TTL) |
| **Best for** | Internal APIs | External, high-security |

---

### Q8: JWKS — public key rotation kaise handle karein?

**Answer:**

**WHAT:** JWKS (JSON Web Key Set) = endpoint exposing public keys for JWT signature verification.

**WHY:**
- Auth server rotates signing keys periodically (security)
- Clients need to fetch new keys without code changes
- JWT `kid` (Key ID) header identifies which key signed it

**HOW — Server publishes JWKS:**

```python
# /.well-known/jwks.json
{
  "keys": [
    {
      "kty": "RSA",
      "use": "sig",
      "kid": "key-2024-01",            # Old key (still valid)
      "n": "...",                       # Modulus
      "e": "AQAB",                      # Exponent
    },
    {
      "kty": "RSA",
      "use": "sig",
      "kid": "key-2024-04",            # New key (current)
      "n": "...",
      "e": "AQAB",
    }
  ]
}
```

**HOW — Client validates JWT with auto key rotation:**

```python
import jwt
from jwt import PyJWKClient
from functools import lru_cache

class JWTValidator:
    """
    INTERVIEW: Validates JWT with automatic key rotation.
    Caches JWKS but refreshes on miss.
    """
    def __init__(self, jwks_url: str, issuer: str, audience: str):
        self.jwks_url = jwks_url
        self.issuer = issuer
        self.audience = audience
        # PyJWKClient handles caching + auto-refresh
        self.jwks_client = PyJWKClient(jwks_url, cache_keys=True, lifespan=3600)

    def validate(self, token: str) -> dict:
        # 1. Extract `kid` from JWT header (without verifying yet)
        unverified_header = jwt.get_unverified_header(token)
        kid = unverified_header.get("kid")

        if not kid:
            raise ValueError("Token missing kid header")

        # 2. Fetch matching public key from JWKS
        try:
            signing_key = self.jwks_client.get_signing_key_from_jwt(token)
        except jwt.exceptions.PyJWKClientError:
            # Key not in cache — force refresh
            self.jwks_client = PyJWKClient(self.jwks_url)
            signing_key = self.jwks_client.get_signing_key_from_jwt(token)

        # 3. Verify signature + claims
        payload = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            audience=self.audience,
            issuer=self.issuer,
            options={
                "verify_signature": True,
                "verify_exp": True,
                "verify_iat": True,
                "verify_aud": True,
                "verify_iss": True,
            }
        )

        return payload
```

---

## Provider-Specific Implementations

### Auth0
```python
from authlib.integrations.starlette_client import OAuth

oauth = OAuth()
oauth.register(
    name="auth0",
    client_id=AUTH0_CLIENT_ID,
    client_secret=AUTH0_CLIENT_SECRET,
    client_kwargs={"scope": "openid profile email"},
    server_metadata_url=f"https://{AUTH0_DOMAIN}/.well-known/openid-configuration",
)
```

### AWS Cognito
```python
oauth.register(
    name="cognito",
    server_metadata_url=f"https://cognito-idp.{REGION}.amazonaws.com/{USER_POOL_ID}/.well-known/openid-configuration",
)
```

### Keycloak (self-hosted)
```python
oauth.register(
    name="keycloak",
    server_metadata_url=f"https://keycloak.example.com/realms/{REALM}/.well-known/openid-configuration",
)
```

### Google
```python
oauth.register(
    name="google",
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
)
```

---

## OAuth2 Security Checklist

```markdown
### Token Storage
- [ ] Access tokens: in-memory only (NOT localStorage for SPA)
- [ ] Refresh tokens: HttpOnly Secure cookies OR encrypted storage
- [ ] NEVER store tokens in URL/query string
- [ ] NEVER log tokens

### Token Validation
- [ ] Validate signature with JWKS (not hardcoded keys)
- [ ] Verify issuer, audience, expiration
- [ ] Check nonce on ID tokens
- [ ] Validate scopes for each endpoint

### Flow Selection
- [ ] Use PKCE for ALL public clients (SPA, mobile)
- [ ] Use Authorization Code for confidential clients (backend)
- [ ] Use Client Credentials for service-to-service
- [ ] NEVER use Implicit flow (deprecated)
- [ ] NEVER use ROPC (password grant) — security anti-pattern

### Refresh Token
- [ ] Implement rotation (one-time use)
- [ ] Detect reuse → revoke all
- [ ] Short TTL (7-30 days)
- [ ] Bind to client fingerprint (optional)

### CSRF Protection
- [ ] Use `state` parameter (random, validate on callback)
- [ ] Use `nonce` for OIDC ID tokens

### General
- [ ] HTTPS only (no HTTP)
- [ ] Validate `redirect_uri` exact match
- [ ] Rate limit token endpoints
- [ ] Monitor for token theft patterns
```

---

## Common OAuth2 Pitfalls

| Pitfall | Risk | Fix |
|---|---|---|
| Storing access token in localStorage | XSS = stolen token | Use HttpOnly cookies or memory |
| No `state` parameter | CSRF | Generate random state, validate |
| Using Implicit flow for SPA | Token in URL | Use Auth Code + PKCE |
| Long-lived access tokens | Window of abuse | Short TTL (15min) + refresh |
| Hard-coded JWKS keys | Can't rotate | Fetch from JWKS endpoint |
| No PKCE for mobile | Code interception | Always use PKCE |
| Wildcard `redirect_uri` | Open redirect | Exact match only |
| Sharing client_secret in SPA | Confidentiality broken | Use public client + PKCE |
