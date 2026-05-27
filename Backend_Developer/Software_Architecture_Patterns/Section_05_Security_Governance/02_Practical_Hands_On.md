# Lecture 2 — Practical Hands-On: OAuth 2.0 + OpenID Connect

> **Theory file:** [02_OAuth_OpenID_Connect.md](02_OAuth_OpenID_Connect.md)

---

## 🎯 Is Practical Mein Kya Banayenge?

Working OAuth/OIDC implementations:

1. ✅ **Authorization Code Flow + PKCE** — full mobile-style flow
2. ✅ **Client Credentials Flow** — service-to-service
3. ✅ **Device Code Flow** — for smart TVs/IoT
4. ✅ **JWT** issuance, signing, verification
5. ✅ **OpenID Connect** — ID tokens, UserInfo
6. ✅ **Keycloak** local setup
7. ✅ **FastAPI integration** with Auth0/Keycloak
8. ✅ **Token refresh** flow
9. ✅ **Logout** + revocation
10. ✅ **SSO across multiple apps**

By end: aap **production OAuth/OIDC** flows ko implement kar sakte ho.

---

## 1. Project Structure

```
oauth_oidc_demo/
├── docker-compose.yml
├── README.md
│
├── auth_server/
│   ├── authorization_code.py   # Auth code + PKCE
│   ├── client_credentials.py
│   ├── device_code.py
│   └── jwt_utils.py
│
├── resource_server/
│   └── main.py                 # API protected by OAuth
│
├── client_apps/
│   ├── web_app/                # Authorization Code
│   ├── mobile_app/             # Authorization Code + PKCE
│   ├── spa/                    # Authorization Code + PKCE
│   ├── service/                # Client Credentials
│   └── tv_app/                 # Device Code
│
├── keycloak/
│   └── realm-config.json
│
└── tests/
    └── test_oauth_flows.py
```

---

## 2. Setup & Dependencies

```bash
pip install fastapi uvicorn
pip install authlib              # OAuth client/server
pip install python-jose[cryptography]  # JWT
pip install httpx
pip install pyjwt[crypto]
pip install python-multipart
```

---

## 3. 🔐 Authorization Code Flow with PKCE

### Client Side (Mobile/SPA)

```python
"""
Authorization Code + PKCE flow.
This is the BEST flow for public clients.
"""
import secrets
import hashlib
import base64
import httpx
from urllib.parse import urlencode

# ─────────────────────────────────────────────────────────────
# STEP 1: Generate PKCE code verifier + challenge
# ─────────────────────────────────────────────────────────────
def generate_pkce_pair():
    """Generate code_verifier and code_challenge"""
    # Random 32-byte URL-safe string
    code_verifier = secrets.token_urlsafe(32)
    
    # SHA-256 hash of verifier, base64 URL-safe encoded
    challenge_bytes = hashlib.sha256(code_verifier.encode()).digest()
    code_challenge = base64.urlsafe_b64encode(challenge_bytes).decode().rstrip("=")
    
    return code_verifier, code_challenge

# ─────────────────────────────────────────────────────────────
# STEP 2: Build authorization URL
# ─────────────────────────────────────────────────────────────
def get_authorization_url(client_id: str, redirect_uri: str):
    code_verifier, code_challenge = generate_pkce_pair()
    state = secrets.token_urlsafe(16)  # CSRF protection
    
    params = {
        "client_id": client_id,
        "response_type": "code",
        "redirect_uri": redirect_uri,
        "scope": "openid profile email",
        "state": state,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
    }
    
    auth_url = f"https://auth.example.com/authorize?{urlencode(params)}"
    
    # Store verifier and state securely (memory, session)
    return auth_url, code_verifier, state

# ─────────────────────────────────────────────────────────────
# STEP 3: Exchange authorization code for tokens
# ─────────────────────────────────────────────────────────────
async def exchange_code_for_tokens(
    code: str,
    code_verifier: str,
    client_id: str,
    redirect_uri: str,
):
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://auth.example.com/token",
            data={
                "grant_type": "authorization_code",
                "client_id": client_id,
                "code": code,
                "code_verifier": code_verifier,  # ← Critical PKCE step!
                "redirect_uri": redirect_uri,
            }
        )
        response.raise_for_status()
        return response.json()
        # Returns:
        # {
        #   "access_token": "eyJ...",
        #   "refresh_token": "...",
        #   "id_token": "eyJ...",
        #   "expires_in": 3600,
        #   "token_type": "Bearer"
        # }

# ─────────────────────────────────────────────────────────────
# COMPLETE FLOW
# ─────────────────────────────────────────────────────────────
async def login_flow():
    CLIENT_ID = "my_mobile_app"
    REDIRECT_URI = "myapp://callback"
    
    # 1. Generate auth URL
    auth_url, verifier, state = get_authorization_url(CLIENT_ID, REDIRECT_URI)
    print(f"Open this URL: {auth_url}")
    
    # 2. User logs in & approves (in browser)
    # 3. Auth server redirects to: myapp://callback?code=...&state=...
    
    # Simulated callback handling
    callback_code = input("Enter code from redirect: ")
    callback_state = input("Enter state from redirect: ")
    
    # Verify state matches (CSRF protection)
    assert callback_state == state, "State mismatch - possible CSRF"
    
    # 4. Exchange code for tokens
    tokens = await exchange_code_for_tokens(
        code=callback_code,
        code_verifier=verifier,
        client_id=CLIENT_ID,
        redirect_uri=REDIRECT_URI,
    )
    
    print(f"Access token: {tokens['access_token'][:30]}...")
    print(f"Refresh token: {tokens['refresh_token'][:30]}...")
    return tokens
```

---

## 4. 🤖 Client Credentials Flow (Service-to-Service)

```python
"""
Client Credentials - for server-to-server, no user involved.
"""
import httpx

async def get_service_token(client_id: str, client_secret: str):
    """Service authenticates with its own credentials"""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://auth.example.com/token",
            data={
                "grant_type": "client_credentials",
                "client_id": client_id,
                "client_secret": client_secret,
                "scope": "internal_api:read internal_api:write",
            }
        )
        response.raise_for_status()
        return response.json()["access_token"]

# Usage in service
class InternalAPIClient:
    def __init__(self):
        self.client_id = "billing-service"
        self.client_secret = "service-secret-from-vault"
        self._token = None
        self._token_expiry = 0
    
    async def _ensure_token(self):
        """Get token, refresh if expired"""
        import time
        if not self._token or time.time() >= self._token_expiry:
            self._token = await get_service_token(self.client_id, self.client_secret)
            self._token_expiry = time.time() + 3500  # Refresh before 3600 expiry
    
    async def call_api(self, endpoint: str):
        await self._ensure_token()
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"https://internal-api.example.com{endpoint}",
                headers={"Authorization": f"Bearer {self._token}"}
            )
            return response.json()
```

---

## 5. 📺 Device Code Flow

```python
"""
Device Code Flow - for smart TVs, IoT devices with limited input.
"""
import httpx
import asyncio
import time

async def device_code_flow(client_id: str):
    """Login on a device with limited input"""
    
    # ─── STEP 1: Device requests user code ───
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://auth.example.com/device/code",
            data={
                "client_id": client_id,
                "scope": "openid profile",
            }
        )
        device_response = response.json()
        # {
        #   "device_code": "abc123...",
        #   "user_code": "FDQR-MJST",
        #   "verification_uri": "https://example.com/device",
        #   "verification_uri_complete": "https://example.com/device?code=FDQR-MJST",
        #   "expires_in": 900,
        #   "interval": 5
        # }
    
    # ─── STEP 2: Show user the code ───
    print(f"\n🔑 Visit: {device_response['verification_uri']}")
    print(f"🔑 Enter code: {device_response['user_code']}")
    print("Waiting for you to log in on another device...\n")
    
    # ─── STEP 3: Poll for token ───
    interval = device_response['interval']
    expires_at = time.time() + device_response['expires_in']
    
    while time.time() < expires_at:
        await asyncio.sleep(interval)
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://auth.example.com/token",
                data={
                    "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
                    "device_code": device_response['device_code'],
                    "client_id": client_id,
                }
            )
            
            if response.status_code == 200:
                # Success!
                tokens = response.json()
                print("✓ Logged in!")
                return tokens
            
            error = response.json().get('error')
            if error == 'authorization_pending':
                continue  # Keep polling
            elif error == 'slow_down':
                interval += 5  # Server says slow down
            elif error == 'expired_token':
                raise Exception("Code expired")
            else:
                raise Exception(f"Error: {error}")
    
    raise Exception("Timeout waiting for user")

asyncio.run(device_code_flow("smart_tv_client"))
```

---

## 6. 🔑 JWT Implementation

### `auth_server/jwt_utils.py`

```python
"""
JWT (JSON Web Token) creation and verification.
"""
import jwt
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
from datetime import datetime, timedelta
from typing import Optional

# ─────────────────────────────────────────────────────────────
# KEY GENERATION (do once, store securely)
# ─────────────────────────────────────────────────────────────
def generate_rsa_keys():
    """Generate RSA key pair for JWT signing"""
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
    )
    
    # PEM encoded private key
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption()
    )
    
    # PEM encoded public key
    public_pem = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    )
    
    return private_pem, public_pem

# ─────────────────────────────────────────────────────────────
# TOKEN CREATION
# ─────────────────────────────────────────────────────────────
class JWTService:
    def __init__(self, private_key: bytes, public_key: bytes):
        self.private_key = private_key
        self.public_key = public_key
        self.algorithm = "RS256"  # Asymmetric - secure for distribution
    
    def create_access_token(
        self,
        user_id: str,
        roles: list[str],
        scopes: list[str],
        expires_minutes: int = 15,
    ) -> str:
        """Create signed access token"""
        now = datetime.utcnow()
        payload = {
            "sub": user_id,
            "iss": "https://auth.example.com",
            "aud": "https://api.example.com",
            "iat": now,
            "exp": now + timedelta(minutes=expires_minutes),
            "scope": " ".join(scopes),
            "roles": roles,
            "jti": str(uuid.uuid4()),  # Unique ID (for revocation)
        }
        return jwt.encode(payload, self.private_key, algorithm=self.algorithm)
    
    def create_id_token(self, user_info: dict, expires_minutes: int = 60) -> str:
        """Create OpenID Connect ID token"""
        now = datetime.utcnow()
        payload = {
            "iss": "https://auth.example.com",
            "sub": user_info["id"],
            "aud": user_info["client_id"],
            "iat": now,
            "exp": now + timedelta(minutes=expires_minutes),
            "nonce": user_info.get("nonce"),  # Prevents replay
            # Identity claims
            "name": user_info["name"],
            "email": user_info["email"],
            "email_verified": user_info.get("email_verified", False),
            "picture": user_info.get("picture"),
        }
        return jwt.encode(payload, self.private_key, algorithm=self.algorithm)
    
    def create_refresh_token(self, user_id: str) -> str:
        """Create long-lived refresh token"""
        now = datetime.utcnow()
        payload = {
            "sub": user_id,
            "iss": "https://auth.example.com",
            "iat": now,
            "exp": now + timedelta(days=30),
            "type": "refresh",
            "jti": str(uuid.uuid4()),
        }
        return jwt.encode(payload, self.private_key, algorithm=self.algorithm)
    
    def verify_token(self, token: str, expected_audience: str = None) -> dict:
        """Verify and decode token"""
        try:
            payload = jwt.decode(
                token,
                self.public_key,
                algorithms=[self.algorithm],  # ← LOCK to specific algorithm!
                audience=expected_audience,
                options={
                    "verify_exp": True,
                    "verify_aud": expected_audience is not None,
                    "verify_signature": True,
                }
            )
            return payload
        except jwt.ExpiredSignatureError:
            raise ValueError("Token expired")
        except jwt.InvalidAudienceError:
            raise ValueError("Invalid audience")
        except jwt.InvalidTokenError as e:
            raise ValueError(f"Invalid token: {e}")
```

---

## 7. 🛡 Protected API (Resource Server)

### `resource_server/main.py`

```python
"""
API protected by OAuth 2.0 access tokens.
"""
from fastapi import FastAPI, HTTPException, Depends, Header
from typing import Optional
from .jwt_utils import JWTService

app = FastAPI(title="Protected API")

# Load public key from auth server (download from JWKS endpoint)
PUBLIC_KEY = """
-----BEGIN PUBLIC KEY-----
...
-----END PUBLIC KEY-----
"""

jwt_service = JWTService(private_key=None, public_key=PUBLIC_KEY)

# ─────────────────────────────────────────────────────────────
# DEPENDENCY: Extract and verify token
# ─────────────────────────────────────────────────────────────
def get_current_user(authorization: Optional[str] = Header(None)) -> dict:
    """Verify Bearer token and return user claims"""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Missing or invalid Authorization header")
    
    token = authorization.replace("Bearer ", "")
    
    try:
        claims = jwt_service.verify_token(
            token,
            expected_audience="https://api.example.com"  # This API
        )
        return claims
    except ValueError as e:
        raise HTTPException(401, str(e))

# ─────────────────────────────────────────────────────────────
# SCOPE-BASED ACCESS
# ─────────────────────────────────────────────────────────────
def require_scope(required_scope: str):
    """Dependency factory for scope checking"""
    def check_scope(user: dict = Depends(get_current_user)):
        scopes = user.get("scope", "").split()
        if required_scope not in scopes:
            raise HTTPException(403, f"Missing scope: {required_scope}")
        return user
    return check_scope

# ─────────────────────────────────────────────────────────────
# ENDPOINTS
# ─────────────────────────────────────────────────────────────
@app.get("/me")
def get_me(user: dict = Depends(get_current_user)):
    """Anyone with valid token can call"""
    return {
        "user_id": user["sub"],
        "roles": user.get("roles", []),
        "scope": user.get("scope"),
    }

@app.get("/orders")
def list_orders(user: dict = Depends(require_scope("read:orders"))):
    """Requires read:orders scope"""
    return {"orders": [...]}

@app.delete("/orders/{order_id}")
def delete_order(
    order_id: str,
    user: dict = Depends(require_scope("delete:orders"))
):
    """Requires delete:orders scope"""
    return {"deleted": order_id}
```

---

## 8. 🔄 Token Refresh Implementation

```python
"""
Refresh token flow with rotation.
"""
import httpx
import asyncio

class TokenManager:
    """Manages access + refresh tokens with auto-refresh"""
    
    def __init__(self, client_id: str, token_endpoint: str):
        self.client_id = client_id
        self.token_endpoint = token_endpoint
        self.access_token: Optional[str] = None
        self.refresh_token: Optional[str] = None
        self.expires_at: Optional[float] = None
    
    def set_tokens(self, tokens: dict):
        """Store tokens from initial login"""
        import time
        self.access_token = tokens["access_token"]
        self.refresh_token = tokens["refresh_token"]
        self.expires_at = time.time() + tokens["expires_in"] - 30  # Refresh 30s early
    
    async def get_access_token(self) -> str:
        """Get valid access token, refresh if needed"""
        import time
        if not self.access_token:
            raise Exception("No tokens - please log in first")
        
        # Check if expired or about to expire
        if time.time() >= self.expires_at:
            await self._refresh()
        
        return self.access_token
    
    async def _refresh(self):
        """Use refresh token to get new access token"""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.token_endpoint,
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": self.refresh_token,
                    "client_id": self.client_id,
                }
            )
            
            if response.status_code != 200:
                # Refresh token may also be expired
                raise Exception("Refresh failed - re-login required")
            
            new_tokens = response.json()
            self.set_tokens(new_tokens)
            
            # ROTATION: refresh token might be replaced
            if "refresh_token" in new_tokens:
                self.refresh_token = new_tokens["refresh_token"]

# Usage
token_manager = TokenManager(
    client_id="my_app",
    token_endpoint="https://auth.example.com/token"
)

# After initial login
token_manager.set_tokens(initial_tokens)

# In API client
async def call_api(endpoint: str):
    token = await token_manager.get_access_token()
    async with httpx.AsyncClient() as client:
        response = await client.get(
            endpoint,
            headers={"Authorization": f"Bearer {token}"}
        )
        return response.json()
```

---

## 9. 🚪 Logout & Revocation

```python
"""
Logout flow with token revocation.
"""
async def logout(access_token: str, refresh_token: str, client_id: str):
    """Properly log out: revoke both tokens"""
    async with httpx.AsyncClient() as client:
        # Revoke refresh token
        await client.post(
            "https://auth.example.com/revoke",
            data={
                "token": refresh_token,
                "token_type_hint": "refresh_token",
                "client_id": client_id,
            }
        )
        
        # Revoke access token
        await client.post(
            "https://auth.example.com/revoke",
            data={
                "token": access_token,
                "token_type_hint": "access_token",
                "client_id": client_id,
            }
        )
    
    # Clear local storage
    token_manager.access_token = None
    token_manager.refresh_token = None

# Single Sign-Out (SLO) - logout from IdP
async def sso_logout(id_token: str, client_id: str):
    """Log out from Identity Provider (terminates session everywhere)"""
    logout_url = (
        "https://auth.example.com/logout?"
        f"id_token_hint={id_token}&"
        f"post_logout_redirect_uri=https://myapp.com/goodbye&"
        f"client_id={client_id}"
    )
    # Redirect user to this URL
    return logout_url
```

---

## 10. 🐳 Keycloak Local Setup

### `docker-compose.yml`

```yaml
version: '3.8'

services:
  postgres:
    image: postgres:15
    environment:
      POSTGRES_DB: keycloak
      POSTGRES_USER: keycloak
      POSTGRES_PASSWORD: keycloak
    volumes:
      - postgres_data:/var/lib/postgresql/data
  
  keycloak:
    image: quay.io/keycloak/keycloak:23.0
    command: start-dev
    environment:
      KC_DB: postgres
      KC_DB_URL: jdbc:postgresql://postgres/keycloak
      KC_DB_USERNAME: keycloak
      KC_DB_PASSWORD: keycloak
      KEYCLOAK_ADMIN: admin
      KEYCLOAK_ADMIN_PASSWORD: admin
    ports:
      - "8080:8080"
    depends_on: [postgres]

volumes:
  postgres_data:
```

### Setup Steps

```bash
# 1. Start Keycloak
$ docker-compose up -d

# 2. Open admin console
$ open http://localhost:8080
# Login: admin/admin

# 3. Create realm: myapp
# 4. Create client:
#    - Client ID: my-mobile-app
#    - Client type: OpenID Connect
#    - Authentication flow: Standard flow (Authorization Code)
#    - Valid redirect URIs: myapp://callback
#    - Web origins: *
#    - Authentication: Public (PKCE required)

# 5. Create user:
#    - Username: ashish
#    - Password: test123
#    - Email: ashish@example.com
```

### Use Keycloak in Python

```python
"""Connect to local Keycloak"""
from authlib.integrations.httpx_client import OAuth2Client

KEYCLOAK_URL = "http://localhost:8080"
REALM = "myapp"
CLIENT_ID = "my-mobile-app"

# Discovery endpoint (provides all URLs)
discovery_url = f"{KEYCLOAK_URL}/realms/{REALM}/.well-known/openid-configuration"

# Auth URL
auth_url = f"{KEYCLOAK_URL}/realms/{REALM}/protocol/openid-connect/auth"
token_url = f"{KEYCLOAK_URL}/realms/{REALM}/protocol/openid-connect/token"
userinfo_url = f"{KEYCLOAK_URL}/realms/{REALM}/protocol/openid-connect/userinfo"

client = OAuth2Client(
    client_id=CLIENT_ID,
    redirect_uri="myapp://callback",
    scope="openid profile email",
    code_challenge_method="S256",
)

# Get auth URL with PKCE
uri, state = client.create_authorization_url(
    auth_url,
    code_verifier=client.generate_code_verifier(),
)
print(f"Open: {uri}")
```

---

## 11. 🌐 FastAPI + Auth0/Keycloak Integration

```python
"""
FastAPI app with Auth0/Keycloak integration.
"""
from fastapi import FastAPI, Depends, HTTPException, Security
from fastapi.security import OAuth2AuthorizationCodeBearer
from authlib.integrations.starlette_client import OAuth
from starlette.middleware.sessions import SessionMiddleware
from starlette.responses import RedirectResponse, HTMLResponse
import os

app = FastAPI()
app.add_middleware(SessionMiddleware, secret_key="your-secret")

oauth = OAuth()
oauth.register(
    name="keycloak",
    server_metadata_url="http://localhost:8080/realms/myapp/.well-known/openid-configuration",
    client_id="my-web-app",
    client_secret="client-secret-from-keycloak",
    client_kwargs={
        "scope": "openid profile email",
    },
)

# ─────────────────────────────────────────────────────────────
# LOGIN FLOW
# ─────────────────────────────────────────────────────────────
@app.get("/login")
async def login(request):
    redirect_uri = request.url_for("auth_callback")
    return await oauth.keycloak.authorize_redirect(request, redirect_uri)

@app.get("/auth/callback")
async def auth_callback(request):
    token = await oauth.keycloak.authorize_access_token(request)
    
    # ID token contains user info
    user = token.get("userinfo")
    
    # Store in session
    request.session["user"] = dict(user)
    request.session["tokens"] = {
        "access_token": token["access_token"],
        "refresh_token": token.get("refresh_token"),
    }
    
    return RedirectResponse("/dashboard")

@app.get("/dashboard")
def dashboard(request):
    user = request.session.get("user")
    if not user:
        return RedirectResponse("/login")
    
    return HTMLResponse(f"""
        <h1>Welcome {user['name']}!</h1>
        <p>Email: {user['email']}</p>
        <a href="/logout">Logout</a>
    """)

@app.get("/logout")
async def logout(request):
    request.session.clear()
    
    # Keycloak SSO logout
    logout_url = (
        "http://localhost:8080/realms/myapp/protocol/openid-connect/logout"
        f"?client_id=my-web-app"
        f"&post_logout_redirect_uri=http://localhost:8000/"
    )
    return RedirectResponse(logout_url)
```

---

## 12. 🧪 Testing OAuth Flows

```python
"""tests/test_oauth_flows.py"""
import pytest
import httpx
import hashlib
import base64
import secrets

@pytest.mark.asyncio
async def test_authorization_code_flow():
    """Test full flow: auth → code → token → API call"""
    
    # Generate PKCE pair
    verifier = secrets.token_urlsafe(32)
    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode()).digest()
    ).decode().rstrip("=")
    
    # In real test: use playwright/selenium for browser steps
    # For this test, assume we have the code already
    code = await get_auth_code_via_browser_automation()
    
    # Exchange for tokens
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:8080/realms/myapp/protocol/openid-connect/token",
            data={
                "grant_type": "authorization_code",
                "client_id": "my-mobile-app",
                "code": code,
                "code_verifier": verifier,
                "redirect_uri": "myapp://callback",
            }
        )
    
    tokens = response.json()
    assert "access_token" in tokens
    assert "id_token" in tokens
    
    # Call protected API
    async with httpx.AsyncClient() as client:
        response = await client.get(
            "http://localhost:8000/api/me",
            headers={"Authorization": f"Bearer {tokens['access_token']}"}
        )
    
    assert response.status_code == 200

@pytest.mark.asyncio
async def test_jwt_validation_rejects_modified_token():
    """Ensure modified tokens are rejected"""
    valid_token = await get_valid_token()
    
    # Modify payload (e.g., change role)
    parts = valid_token.split(".")
    modified_token = f"{parts[0]}.MODIFIED.{parts[2]}"
    
    async with httpx.AsyncClient() as client:
        response = await client.get(
            "http://localhost:8000/api/me",
            headers={"Authorization": f"Bearer {modified_token}"}
        )
    
    assert response.status_code == 401

@pytest.mark.asyncio
async def test_expired_token_rejected():
    """Ensure expired tokens are rejected"""
    # Create token with past expiry
    expired_token = create_test_token(expires_minutes=-10)
    
    async with httpx.AsyncClient() as client:
        response = await client.get(
            "http://localhost:8000/api/me",
            headers={"Authorization": f"Bearer {expired_token}"}
        )
    
    assert response.status_code == 401
    assert "expired" in response.json().get("detail", "").lower()
```

---

## 13. Key Learnings Summary

```
✅ Authorization Code + PKCE for mobile/SPA (most secure)
✅ Client Credentials for service-to-service
✅ Device Code for IoT/TVs
✅ JWT with RS256 (asymmetric, distributable)
✅ ID tokens for OIDC user identity
✅ Always validate: signature, exp, aud, iss
✅ Token rotation on refresh
✅ Proper revocation on logout
✅ Keycloak for self-hosted OIDC
✅ Auth0/Okta for managed solutions

🎯 Production OAuth/OIDC stack:
   - IdP: Keycloak/Auth0/Okta
   - Mobile: Auth Code + PKCE
   - Web: Auth Code + secure cookies
   - SPA: Auth Code + PKCE + memory storage
   - Internal services: Client Credentials
   - Smart TV: Device Code
```

---

## 🎬 What's Next?

In **Lecture 3**, we'll cover **API and Service Security** — API keys, JWT in production, mTLS, and defense in depth.

> **Next lecture:** [03_API_Service_Security.md](03_API_Service_Security.md)

---

## 📚 Try It Yourself

1. Set up **Keycloak** with custom realm + clients
2. Build **mobile-style** auth flow with PKCE
3. Implement **SSO** across 3 different apps
4. Add **role mapping** from IdP to your app
5. Build **logout with token revocation**
