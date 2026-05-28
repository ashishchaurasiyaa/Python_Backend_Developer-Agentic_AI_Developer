# OAuth2 Full Flows — Authorization Code, PKCE, Refresh Tokens

## Why It Matters (Senior 5 YOE Context)

JWT + simple login is "auth for toy apps". Production apps need:

- **OAuth2 Authorization Code + PKCE** → mobile/SPA secure flow
- **Refresh tokens** → long sessions without compromising security
- **Scopes** → fine-grained permissions
- **Third-party login** → Google/GitHub/Apple SSO
- **Token introspection** → validate opaque tokens server-side

Senior interview: "Implement Google login in FastAPI" → not just `redirect`+`callback` — explain PKCE, state, nonce, token storage, refresh.

---

## Core Concepts

### OAuth2 Flows Overview

| Flow | Use Case | PKCE | Refresh |
|---|---|---|---|
| Authorization Code | Server-side web app | Optional | Yes |
| Authorization Code + PKCE | SPA, mobile, CLI | **Required** | Yes |
| Client Credentials | Service-to-service | No | No |
| Device Code | TV, CLI without browser | No | Yes |
| Implicit | DEPRECATED — don't use | — | — |
| Resource Owner Password | DEPRECATED (legacy only) | — | Yes |

### Authorization Code Flow (Server-Side)

```
1. User clicks "Login with Google"
2. App redirects to: https://accounts.google.com/o/oauth2/v2/auth?
       client_id=X&
       redirect_uri=https://app.example.com/auth/callback&
       response_type=code&
       scope=openid email profile&
       state=<random>
3. User logs in, approves
4. Google redirects back: https://app.example.com/auth/callback?code=ABC&state=<same>
5. App POSTs to token endpoint:
       https://oauth2.googleapis.com/token
       {code, client_id, client_secret, grant_type=authorization_code, redirect_uri}
6. Receives: {access_token, refresh_token, id_token, expires_in}
7. App creates session/JWT, stores refresh_token securely (DB)
```

### Authorization Code + PKCE (SPA/Mobile)

Adds PKCE = Proof Key for Code Exchange. SPA can't safely store client_secret.

```
1. Client generates code_verifier (random 43-128 chars)
2. Computes code_challenge = base64url(sha256(code_verifier))
3. Includes code_challenge in /authorize
4. User authorizes
5. On /token call, client sends code_verifier
6. Server verifies sha256(code_verifier) == code_challenge → issues token
```

Prevents auth code interception attacks.

### FastAPI OAuth2 + PKCE Implementation

```python
import secrets
import hashlib
import base64
from urllib.parse import urlencode
from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.responses import RedirectResponse, JSONResponse
import httpx

app = FastAPI()

# In real app: load from env
GOOGLE_CLIENT_ID = 'your-client-id'
GOOGLE_CLIENT_SECRET = 'your-secret'
GOOGLE_REDIRECT_URI = 'https://app.example.com/auth/google/callback'


def generate_pkce_pair():
    verifier = secrets.token_urlsafe(64)[:128]
    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode()).digest()
    ).decode().rstrip('=')
    return verifier, challenge


@app.get("/auth/google/login")
def google_login(request: Request):
    state = secrets.token_urlsafe(32)
    verifier, challenge = generate_pkce_pair()

    # Store state + verifier in session (or Redis with TTL)
    request.session['oauth_state'] = state
    request.session['oauth_verifier'] = verifier

    params = {
        'client_id': GOOGLE_CLIENT_ID,
        'redirect_uri': GOOGLE_REDIRECT_URI,
        'response_type': 'code',
        'scope': 'openid email profile',
        'state': state,
        'code_challenge': challenge,
        'code_challenge_method': 'S256',
        'access_type': 'offline',  # request refresh_token
        'prompt': 'consent',
    }
    return RedirectResponse(
        f'https://accounts.google.com/o/oauth2/v2/auth?{urlencode(params)}'
    )


@app.get("/auth/google/callback")
async def google_callback(request: Request, code: str, state: str):
    # Verify state to prevent CSRF
    saved_state = request.session.pop('oauth_state', None)
    if not saved_state or not secrets.compare_digest(saved_state, state):
        raise HTTPException(400, 'Invalid state')

    verifier = request.session.pop('oauth_verifier', None)
    if not verifier:
        raise HTTPException(400, 'Missing verifier')

    # Exchange code for tokens
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            'https://oauth2.googleapis.com/token',
            data={
                'code': code,
                'client_id': GOOGLE_CLIENT_ID,
                'client_secret': GOOGLE_CLIENT_SECRET,
                'redirect_uri': GOOGLE_REDIRECT_URI,
                'grant_type': 'authorization_code',
                'code_verifier': verifier,
            },
        )

    if resp.status_code != 200:
        raise HTTPException(401, 'Token exchange failed')

    tokens = resp.json()
    # tokens = {access_token, refresh_token, expires_in, id_token, ...}

    # Get user info
    async with httpx.AsyncClient() as client:
        userinfo_resp = await client.get(
            'https://www.googleapis.com/oauth2/v3/userinfo',
            headers={'Authorization': f'Bearer {tokens["access_token"]}'},
        )
    user_info = userinfo_resp.json()

    # Create/update user in DB
    user = await get_or_create_user(
        email=user_info['email'],
        name=user_info['name'],
        avatar=user_info.get('picture'),
    )

    # Store refresh token securely in DB (encrypted)
    await save_refresh_token(user.id, tokens.get('refresh_token'))

    # Issue our own JWT/session
    our_jwt = create_jwt(user.id)
    return {'access_token': our_jwt, 'user': user.email}
```

### Refresh Token Pattern

```python
from datetime import datetime, timedelta
import jwt


JWT_SECRET = 'your-secret'
ACCESS_TOKEN_TTL = timedelta(minutes=15)
REFRESH_TOKEN_TTL = timedelta(days=30)


def create_access_token(user_id: int) -> str:
    return jwt.encode(
        {'sub': str(user_id), 'exp': datetime.utcnow() + ACCESS_TOKEN_TTL, 'type': 'access'},
        JWT_SECRET,
        algorithm='HS256',
    )


async def create_refresh_token(user_id: int) -> str:
    # Opaque token stored in DB (not JWT) — easier to revoke
    token = secrets.token_urlsafe(64)
    await db.execute(
        'INSERT INTO refresh_tokens (user_id, token, expires_at) VALUES ($1, $2, $3)',
        user_id, token, datetime.utcnow() + REFRESH_TOKEN_TTL,
    )
    return token


@app.post("/auth/refresh")
async def refresh(refresh_token: str):
    # Look up in DB
    row = await db.fetchrow(
        'SELECT user_id, expires_at, revoked FROM refresh_tokens WHERE token = $1',
        refresh_token,
    )
    if not row or row['revoked'] or row['expires_at'] < datetime.utcnow():
        raise HTTPException(401, 'Invalid refresh token')

    user_id = row['user_id']

    # Rotate — revoke old, issue new (defense against replay)
    new_refresh = await create_refresh_token(user_id)
    await db.execute(
        'UPDATE refresh_tokens SET revoked = true WHERE token = $1',
        refresh_token,
    )

    return {
        'access_token': create_access_token(user_id),
        'refresh_token': new_refresh,
        'expires_in': int(ACCESS_TOKEN_TTL.total_seconds()),
    }
```

### Scopes (Fine-Grained Permissions)

```python
from fastapi.security import OAuth2PasswordBearer, SecurityScopes
from fastapi import Security


oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="token",
    scopes={
        "articles:read": "Read articles",
        "articles:write": "Create/update articles",
        "admin": "Admin access",
    },
)


async def get_current_user(
    security_scopes: SecurityScopes,
    token: str = Depends(oauth2_scheme),
):
    payload = jwt.decode(token, JWT_SECRET, algorithms=['HS256'])
    token_scopes = payload.get('scopes', [])

    for required in security_scopes.scopes:
        if required not in token_scopes:
            raise HTTPException(
                status_code=403,
                detail=f"Not enough permissions: {required}",
                headers={"WWW-Authenticate": f'Bearer scope="{required}"'},
            )

    return payload['sub']


@app.get("/articles/", dependencies=[Security(get_current_user, scopes=['articles:read'])])
def list_articles():
    return [...]


@app.post("/articles/", dependencies=[Security(get_current_user, scopes=['articles:write'])])
def create_article():
    return {}
```

### GitHub OAuth (Simpler — no PKCE for backend)

```python
GITHUB_CLIENT_ID = '...'
GITHUB_CLIENT_SECRET = '...'


@app.get("/auth/github/login")
def github_login(request: Request):
    state = secrets.token_urlsafe(32)
    request.session['github_state'] = state
    params = {
        'client_id': GITHUB_CLIENT_ID,
        'redirect_uri': 'https://app.example.com/auth/github/callback',
        'scope': 'read:user user:email',
        'state': state,
    }
    return RedirectResponse(
        f'https://github.com/login/oauth/authorize?{urlencode(params)}'
    )


@app.get("/auth/github/callback")
async def github_callback(request: Request, code: str, state: str):
    if state != request.session.pop('github_state', ''):
        raise HTTPException(400, 'Invalid state')

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            'https://github.com/login/oauth/access_token',
            json={
                'client_id': GITHUB_CLIENT_ID,
                'client_secret': GITHUB_CLIENT_SECRET,
                'code': code,
            },
            headers={'Accept': 'application/json'},
        )
        token_data = resp.json()
        # token_data = {access_token, scope, token_type}

        # Get user
        user_resp = await client.get(
            'https://api.github.com/user',
            headers={'Authorization': f'Bearer {token_data["access_token"]}'},
        )
        gh_user = user_resp.json()

    # Create local user, issue JWT
    ...
```

### Token Storage in Frontend

```
SPA cookies vs localStorage:
- localStorage: XSS reads it → token stolen
- httpOnly Secure cookies: XSS can't read, but need CSRF protection

Recommendation:
- Access token: short-lived (15 min), in memory (or short-lived cookie)
- Refresh token: httpOnly, Secure, SameSite=Strict cookie
- API calls: include access token in Authorization header
- Refresh: silent fetch /refresh on 401, server reads refresh cookie
```

---

## How It Works Internally

### State Parameter

Random opaque value. Echoed back by IdP. App compares. Prevents CSRF on auth callback (attacker can't forge callback with their code, your session).

### Nonce in OpenID Connect

Similar to state but for ID token. Included in `id_token`, app verifies — prevents token replay.

### Refresh Token Rotation

Every refresh = new refresh token + old one revoked. If attacker steals + uses, victim's next refresh fails → IdP detects replay → revoke all sessions for user.

### Token Storage in DB

```sql
CREATE TABLE refresh_tokens (
    id SERIAL PRIMARY KEY,
    user_id INT REFERENCES users(id),
    token VARCHAR(255) UNIQUE,
    expires_at TIMESTAMP,
    revoked BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW(),
    -- For audit
    user_agent TEXT,
    ip_address INET,
    INDEX idx_user (user_id),
    INDEX idx_token (token)
);
```

Hash token in DB if paranoid (`sha256(token)`) — leaked DB doesn't expose tokens.

---

## Common Pitfalls

### 1. No State Verification

Without state check, attacker can complete OAuth for any victim → account takeover.

### 2. Token in URL

```
GET /callback?access_token=xyz   ← leaks via referer header, browser history, server logs
```

Always POST or use code flow.

### 3. JWT for Refresh

JWT can't be revoked (only by short TTL). Use opaque DB tokens for refresh.

### 4. No Refresh Token Rotation

Long-lived static refresh tokens = compromise = forever access. Rotate on every use.

### 5. Storing Tokens in localStorage

XSS → token theft. Use httpOnly cookies.

### 6. PKCE Missing for Public Clients

SPA / mobile / CLI = public clients (can't keep secrets). Require PKCE.

### 7. Implicit Flow Still Used

Deprecated. Returns token in URL fragment. Use code flow + PKCE.

### 8. Insufficient Scope Check

Granting `admin` scope by default. Always check requested scopes against required.

---

## Interview Q&A

**Q1:** PKCE kya hai aur kab use karte ho?
**A:** Proof Key for Code Exchange — extension to authorization code flow. Client generates random verifier + sha256 challenge. Challenge sent with /authorize, verifier with /token. Prevents auth code interception (e.g., malicious app on same device). Required for public clients (SPA, mobile, CLI); recommended for all OAuth.

**Q2:** Refresh token rotation kya hai?
**A:** On every /refresh, issue new refresh token + revoke old. If attacker steals old token + uses, victim's next refresh fails → detect compromise → revoke all sessions. Trades complexity for security. Standard for high-value apps (banking, healthcare).

**Q3:** OAuth state parameter ka purpose?
**A:** CSRF protection. Random value generated before /authorize, stored in session. IdP echoes back. App compares — if mismatch, reject. Without state, attacker can authorize with their account, get code, send victim to callback URL → victim's session linked to attacker's account.

**Q4:** Refresh token kahan store karoge frontend mein?
**A:** httpOnly + Secure + SameSite=Strict cookie. Browser sends automatically; JS can't read. Combined with CSRF token for state-changing operations. Access token in memory (or short-lived JS-readable cookie). Never localStorage for refresh.

**Q5:** Scope-based authorization kaise implement karoge?
**A:** Encode scopes in JWT/token. On endpoint, check `required_scope ⊆ token_scopes`. FastAPI: `Security(get_current_user, scopes=['articles:write'])`. For dynamic scopes (RBAC), check against user's granted scopes from DB.

**Q6:** OAuth2 vs OIDC ka difference?
**A:** OAuth2 = authorization (what can you do). OIDC = OAuth2 + identity layer (who are you). OIDC adds `id_token` (signed JWT with user claims), `/userinfo` endpoint, nonce, standard scopes (openid, profile, email). Most "Login with X" = OIDC.

**Q7:** Token revocation OAuth2 mein kaise karte ho?
**A:** Access tokens (JWT): can't revoke individually (stateless). Solutions: short TTL (15 min), token denylist (Redis SET with expiry = original token TTL), session ID in token + DB lookup. Refresh tokens (opaque): mark `revoked=true` in DB.

**Q8:** Google login + multiple identity providers kaise unify karoge?
**A:** Common `User` table + separate `OAuthIdentity` table:
```python
class OAuthIdentity:
    user_id: FK
    provider: str  # 'google', 'github', 'apple'
    provider_user_id: str  # ID from that provider
    UNIQUE(provider, provider_user_id)
```
On login: look up by (provider, provider_user_id). If exists, log in. Else create user + identity.

---

## Real-World Use Cases

### 1. SPA with Refresh Cookie

Backend issues short access token (header) + long refresh in httpOnly cookie. Frontend silent-refreshes on 401.

### 2. Mobile App with PKCE

Native browser tab for OAuth (Custom Tabs on Android, SFAuthenticationSession on iOS). PKCE protects against rogue apps intercepting the redirect.

### 3. Service-to-Service (Client Credentials)

```python
# Backend service calls another backend service
async def get_service_token():
    async with httpx.AsyncClient() as c:
        resp = await c.post(
            'https://auth.example.com/token',
            data={
                'grant_type': 'client_credentials',
                'client_id': SERVICE_ID,
                'client_secret': SERVICE_SECRET,
                'scope': 'internal:read',
            },
        )
    return resp.json()['access_token']
```

---

## References

- [OAuth2 RFC 6749](https://datatracker.ietf.org/doc/html/rfc6749)
- [PKCE RFC 7636](https://datatracker.ietf.org/doc/html/rfc7636)
- [OAuth2 best current practice](https://datatracker.ietf.org/doc/html/draft-ietf-oauth-security-topics)
- [Authlib library](https://authlib.org/) — Python OAuth client/server
- FastAPI OAuth2 tutorial
