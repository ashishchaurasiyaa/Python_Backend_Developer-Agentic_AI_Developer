"""
OAuth2 Full Flows — Production Patterns

Google OAuth + PKCE, GitHub OAuth, refresh token rotation, scopes.
"""

import os
import secrets
import hashlib
import base64
from datetime import datetime, timedelta
from urllib.parse import urlencode

import httpx
import jwt
from fastapi import FastAPI, Depends, HTTPException, Request, status, Security
from fastapi.responses import RedirectResponse, JSONResponse
from fastapi.security import OAuth2PasswordBearer, SecurityScopes
from pydantic import BaseModel
from starlette.middleware.sessions import SessionMiddleware


app = FastAPI()
app.add_middleware(SessionMiddleware, secret_key=os.environ.get('SESSION_SECRET', 'dev'))


# ==========================================================================
# 1. CONFIG
# ==========================================================================

GOOGLE_CLIENT_ID = os.environ.get('GOOGLE_CLIENT_ID', '')
GOOGLE_CLIENT_SECRET = os.environ.get('GOOGLE_CLIENT_SECRET', '')
GOOGLE_REDIRECT_URI = os.environ.get('GOOGLE_REDIRECT_URI', 'http://localhost:8000/auth/google/callback')

GITHUB_CLIENT_ID = os.environ.get('GITHUB_CLIENT_ID', '')
GITHUB_CLIENT_SECRET = os.environ.get('GITHUB_CLIENT_SECRET', '')
GITHUB_REDIRECT_URI = os.environ.get('GITHUB_REDIRECT_URI', 'http://localhost:8000/auth/github/callback')

JWT_SECRET = os.environ.get('JWT_SECRET', 'dev-secret')
ACCESS_TOKEN_TTL = timedelta(minutes=15)
REFRESH_TOKEN_TTL = timedelta(days=30)


# ==========================================================================
# 2. PKCE HELPER
# ==========================================================================

def generate_pkce_pair():
    """Generate (verifier, challenge) — challenge is S256-hash of verifier."""
    verifier = secrets.token_urlsafe(64)[:128]
    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode()).digest()
    ).decode().rstrip('=')
    return verifier, challenge


# ==========================================================================
# 3. JWT HELPERS
# ==========================================================================

def create_access_token(user_id: int, scopes: list[str] = None) -> str:
    payload = {
        'sub': str(user_id),
        'scopes': scopes or [],
        'exp': datetime.utcnow() + ACCESS_TOKEN_TTL,
        'iat': datetime.utcnow(),
        'type': 'access',
    }
    return jwt.encode(payload, JWT_SECRET, algorithm='HS256')


def decode_access_token(token: str) -> dict:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=['HS256'])
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, 'Token expired')
    except jwt.InvalidTokenError:
        raise HTTPException(401, 'Invalid token')


# ==========================================================================
# 4. REFRESH TOKEN STORE (in-memory for demo; use DB in prod)
# ==========================================================================

# Simulated DB
refresh_tokens_db: dict[str, dict] = {}


def create_refresh_token(user_id: int, user_agent: str = '', ip: str = '') -> str:
    token = secrets.token_urlsafe(64)
    refresh_tokens_db[token] = {
        'user_id': user_id,
        'expires_at': datetime.utcnow() + REFRESH_TOKEN_TTL,
        'revoked': False,
        'user_agent': user_agent,
        'ip': ip,
        'created_at': datetime.utcnow(),
    }
    return token


def revoke_refresh_token(token: str):
    if token in refresh_tokens_db:
        refresh_tokens_db[token]['revoked'] = True


def get_refresh_token(token: str) -> dict | None:
    row = refresh_tokens_db.get(token)
    if not row:
        return None
    if row['revoked'] or row['expires_at'] < datetime.utcnow():
        return None
    return row


# ==========================================================================
# 5. GOOGLE OAUTH + PKCE
# ==========================================================================

@app.get("/auth/google/login")
def google_login(request: Request):
    state = secrets.token_urlsafe(32)
    verifier, challenge = generate_pkce_pair()

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
        'access_type': 'offline',  # for refresh_token
        'prompt': 'consent',
    }
    return RedirectResponse(
        f'https://accounts.google.com/o/oauth2/v2/auth?{urlencode(params)}'
    )


@app.get("/auth/google/callback")
async def google_callback(request: Request, code: str, state: str):
    # CSRF protection — verify state
    saved_state = request.session.pop('oauth_state', None)
    if not saved_state or not secrets.compare_digest(saved_state, state):
        raise HTTPException(400, 'Invalid state')

    verifier = request.session.pop('oauth_verifier', None)
    if not verifier:
        raise HTTPException(400, 'Missing PKCE verifier')

    # Exchange code for tokens
    async with httpx.AsyncClient(timeout=10.0) as client:
        token_resp = await client.post(
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

        if token_resp.status_code != 200:
            raise HTTPException(401, 'Token exchange failed')

        tokens = token_resp.json()

        # Fetch user info
        userinfo_resp = await client.get(
            'https://www.googleapis.com/oauth2/v3/userinfo',
            headers={'Authorization': f'Bearer {tokens["access_token"]}'},
        )
        user_info = userinfo_resp.json()

    # Create/update user (pseudo-code; replace with DB)
    user_id = user_info['sub']  # Google's stable user ID

    # Save Google's refresh token (encrypted in real DB)
    # await save_google_refresh(user_id, tokens.get('refresh_token'))

    # Issue OUR tokens
    our_access = create_access_token(user_id, scopes=['user:read'])
    our_refresh = create_refresh_token(
        user_id,
        user_agent=request.headers.get('user-agent', ''),
        ip=request.client.host,
    )

    response = JSONResponse({
        'access_token': our_access,
        'expires_in': int(ACCESS_TOKEN_TTL.total_seconds()),
        'user': {
            'email': user_info['email'],
            'name': user_info.get('name'),
            'picture': user_info.get('picture'),
        },
    })

    # Refresh in httpOnly cookie
    response.set_cookie(
        'refresh_token',
        our_refresh,
        max_age=int(REFRESH_TOKEN_TTL.total_seconds()),
        httponly=True,
        secure=True,
        samesite='strict',
    )
    return response


# ==========================================================================
# 6. GITHUB OAUTH (simpler — no PKCE since we have secret)
# ==========================================================================

@app.get("/auth/github/login")
def github_login(request: Request):
    state = secrets.token_urlsafe(32)
    request.session['github_state'] = state
    params = {
        'client_id': GITHUB_CLIENT_ID,
        'redirect_uri': GITHUB_REDIRECT_URI,
        'scope': 'read:user user:email',
        'state': state,
    }
    return RedirectResponse(
        f'https://github.com/login/oauth/authorize?{urlencode(params)}'
    )


@app.get("/auth/github/callback")
async def github_callback(request: Request, code: str, state: str):
    saved_state = request.session.pop('github_state', None)
    if not saved_state or not secrets.compare_digest(saved_state, state):
        raise HTTPException(400, 'Invalid state')

    async with httpx.AsyncClient(timeout=10.0) as client:
        token_resp = await client.post(
            'https://github.com/login/oauth/access_token',
            json={
                'client_id': GITHUB_CLIENT_ID,
                'client_secret': GITHUB_CLIENT_SECRET,
                'code': code,
            },
            headers={'Accept': 'application/json'},
        )
        token_data = token_resp.json()

        user_resp = await client.get(
            'https://api.github.com/user',
            headers={'Authorization': f'Bearer {token_data["access_token"]}'},
        )
        gh_user = user_resp.json()

    user_id = str(gh_user['id'])
    our_access = create_access_token(user_id, scopes=['user:read'])
    our_refresh = create_refresh_token(user_id)

    return JSONResponse({
        'access_token': our_access,
        'refresh_token': our_refresh,
        'user': {'login': gh_user['login'], 'email': gh_user.get('email')},
    })


# ==========================================================================
# 7. REFRESH TOKEN ROTATION
# ==========================================================================

class RefreshIn(BaseModel):
    refresh_token: str | None = None


@app.post("/auth/refresh")
async def refresh(payload: RefreshIn, request: Request):
    # Prefer cookie, fall back to body
    token = request.cookies.get('refresh_token') or payload.refresh_token
    if not token:
        raise HTTPException(401, 'Missing refresh token')

    row = get_refresh_token(token)
    if not row:
        raise HTTPException(401, 'Invalid or expired refresh token')

    user_id = row['user_id']

    # Rotation: revoke old, issue new
    revoke_refresh_token(token)
    new_refresh = create_refresh_token(user_id)
    new_access = create_access_token(user_id, scopes=['user:read'])

    response = JSONResponse({
        'access_token': new_access,
        'expires_in': int(ACCESS_TOKEN_TTL.total_seconds()),
    })
    response.set_cookie(
        'refresh_token',
        new_refresh,
        max_age=int(REFRESH_TOKEN_TTL.total_seconds()),
        httponly=True,
        secure=True,
        samesite='strict',
    )
    return response


@app.post("/auth/logout")
async def logout(request: Request):
    token = request.cookies.get('refresh_token')
    if token:
        revoke_refresh_token(token)
    response = JSONResponse({'ok': True})
    response.delete_cookie('refresh_token')
    return response


# ==========================================================================
# 8. SCOPES — Fine-grained permissions
# ==========================================================================

oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="token",
    scopes={
        "user:read": "Read own profile",
        "articles:read": "Read articles",
        "articles:write": "Create/update articles",
        "admin": "Admin access",
    },
)


async def get_current_user(
    security_scopes: SecurityScopes,
    token: str = Depends(oauth2_scheme),
):
    payload = decode_access_token(token)
    token_scopes = set(payload.get('scopes', []))

    for required in security_scopes.scopes:
        if required not in token_scopes:
            auth_value = (
                f'Bearer scope="{security_scopes.scope_str}"'
                if security_scopes.scopes else 'Bearer'
            )
            raise HTTPException(
                status_code=403,
                detail=f"Not enough permissions: needs {required}",
                headers={"WWW-Authenticate": auth_value},
            )

    return {'user_id': payload['sub'], 'scopes': list(token_scopes)}


@app.get(
    "/articles/",
    dependencies=[Security(get_current_user, scopes=['articles:read'])],
)
def list_articles():
    return [{'id': 1, 'title': 'Sample'}]


@app.post(
    "/articles/",
    dependencies=[Security(get_current_user, scopes=['articles:write'])],
)
def create_article():
    return {'created': True}


@app.get(
    "/admin/users/",
    dependencies=[Security(get_current_user, scopes=['admin'])],
)
def admin_list_users():
    return []


# ==========================================================================
# 9. CLIENT CREDENTIALS FLOW (service-to-service)
# ==========================================================================

async def get_service_token(client_id: str, client_secret: str, scope: str):
    """Service A getting token to call Service B."""
    async with httpx.AsyncClient() as c:
        resp = await c.post(
            'https://auth.example.com/token',
            data={
                'grant_type': 'client_credentials',
                'client_id': client_id,
                'client_secret': client_secret,
                'scope': scope,
            },
        )
    return resp.json().get('access_token')


# ==========================================================================
# 10. TOKEN STORAGE (RECOMMENDED FRONTEND PATTERN)
# ==========================================================================
"""
Frontend strategy:
- Access token: in JS memory only (variable, NOT localStorage)
- Refresh token: httpOnly + Secure cookie set by server
- API calls: Authorization: Bearer <access>
- On 401: silent POST /auth/refresh — cookie sent automatically
- Logout: POST /auth/logout — server revokes + clears cookie

CSRF protection for cookie-based:
- SameSite=Strict on refresh cookie
- Plus CSRF token in header for state-changing requests
"""
