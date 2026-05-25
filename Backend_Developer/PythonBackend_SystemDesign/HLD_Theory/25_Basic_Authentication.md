# Basic Authentication

## Quick Reference Card
```
Basic Auth    → "username:password" ko Base64 encode karke Header mein bhejo
Base64        → Encoding, NOT encryption! Anyone can decode it
HTTPS needed  → Without HTTPS, Basic Auth = plain text password sent over network
Stateless     → Each request carries credentials — no session needed
Limitation    → Logout impossible (browser caches credentials), no token revocation
Interview hook → "Basic Auth for internal admin/Swagger UI — not for production user APIs"
```

---

## PART 1: HINGLISH — Samjhne ke liye

### 1.1 Basic Authentication Kya Hai?

**Analogy: Library card**

Old library system: Tu apna naam aur ID number harr baar jab bhi book issue karne aata tha, counter pe deta tha. Librarian har baar register check karta tha. Koi session nahi — har request ke saath credentials.

```
HOW IT WORKS:

1. Client sends request WITHOUT credentials:
   GET /api/invoices/ HTTP/1.1
   Host: api.youngman.com

2. Server responds with 401 + challenge:
   HTTP/1.1 401 Unauthorized
   WWW-Authenticate: Basic realm="Youngman API"

3. Client encodes credentials:
   "username:password" → Base64 encode
   "ashish:secret123" → "YXNoaXNoOnNlY3JldDEyMw=="

4. Client sends with credentials:
   GET /api/invoices/ HTTP/1.1
   Authorization: Basic YXNoaXNoOnNlY3JldDEyMw==

5. Server decodes + verifies:
   Base64 decode → "ashish:secret123"
   Hash("secret123") compare with DB
   Match? → 200 OK
   No match? → 401 Unauthorized

BASE64 IS NOT ENCRYPTION:
   Base64 is just encoding — anyone can decode!
   "YXNoaXNoOnNlY3JldDEyMw==" → decode → "ashish:secret123"
   
   HTTPS is MANDATORY for Basic Auth security
   HTTP + Basic Auth = password sent in clear text (essentially)
```

---

### 1.2 Basic Auth — Implementation

```python
# Django REST Framework Basic Authentication

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.BasicAuthentication',
        'rest_framework.authentication.SessionAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
}

# DRF's BasicAuthentication:
# 1. Reads Authorization header
# 2. Base64 decodes
# 3. Splits on first ':'
# 4. authenticate_credentials(username, password)
#    → Django authenticate() → check DB
# 5. Returns (user, None) on success

# Custom Basic Auth (for API keys instead of username/password):
class APIKeyAuthentication(BasicAuthentication):
    """
    Use API key as username, empty password.
    Authorization: Basic base64(api_key:)
    """
    
    def authenticate_credentials(self, userid, password, request=None):
        try:
            api_key = APIKey.objects.get(key=userid, is_active=True)
            return (api_key.user, api_key)
        except APIKey.DoesNotExist:
            raise AuthenticationFailed('Invalid API key')

# Usage for Swagger/DRF browsable API:
# /api/swagger/ → Basic Auth popup in browser
# Useful for internal tools, not public user-facing APIs

# SAP HANA Basic Auth (machine-to-machine):
import base64
import requests

def sap_authenticate(username, password):
    credentials = f"{username}:{password}"
    encoded = base64.b64encode(credentials.encode()).decode()
    
    response = requests.post(
        f"{SAP_BASE_URL}/auth/token",
        headers={"Authorization": f"Basic {encoded}"},
    )
    return response.json()['access_token']
```

---

### 1.3 Problems with Basic Authentication

```
1. NO LOGOUT:
   Browser caches "Authorization: Basic ..." header
   User clicks "Logout" → Application clears local state
   But browser still sends cached credentials!
   
   Only way to "logout": Clear browser cache or wait for session timeout
   
   Workaround: Force browser credential prompt by returning 401 on logout
   
2. CREDENTIALS ON EVERY REQUEST:
   Every single request carries username + password
   If TLS has any issue → credentials exposed on every request
   Compare: JWT → credentials verified ONCE at login, token issued
   
3. NO REVOCATION WITHOUT PASSWORD CHANGE:
   If someone stole your Basic Auth credentials:
   → Must change your password to revoke access
   Compare: JWT → just invalidate specific token
   
4. NO FINE-GRAINED SCOPE:
   Basic Auth is all-or-nothing
   Can't say: "This credential can only READ, not WRITE"
   
5. PASSWORD COMPLEXITY:
   Each service that uses Basic Auth needs a password
   Machine-to-machine: API keys better (random, revocable)

WHEN BASIC AUTH IS OK:
  ✓ Internal development tools
  ✓ DRF browsable API / Swagger UI (developer-facing)
  ✓ Machine-to-machine (initial auth to get OAuth token)
  ✓ Simple internal admin tools (not customer-facing)
  ✓ Protected static content (Nginx basic_auth)
  
  NOT OK:
  ✗ Customer-facing login
  ✗ Mobile apps (token-based is better)
  ✗ Long-lived sessions
  ✗ Any scenario needing logout or token revocation
```

---

### 1.4 Nginx Basic Auth (Protecting Static Resources)

```nginx
# Protect internal tool with Basic Auth at Nginx level

# Generate password file:
# htpasswd -c /etc/nginx/.htpasswd ashish
# Enter password: (entered securely)

server {
    listen 443 ssl;
    server_name flower.youngman.internal;  # Celery monitoring
    
    # Basic Auth protection
    auth_basic "Youngman Internal";
    auth_basic_user_file /etc/nginx/.htpasswd;
    
    location / {
        proxy_pass http://localhost:5555;  # Celery Flower
    }
}

# This protects Celery Flower from public access
# Only people with username+password can access the monitoring dashboard
# Simple, effective for internal tools
# MUST be behind HTTPS!
```

---

### 1.5 Digest Authentication (Improvement over Basic)

```
DIGEST AUTHENTICATION (HTTP protocol):
  Problem with Basic: Password sent (even if encoded) each request
  
  Digest improvement:
  1. Server sends: challenge (nonce = random string)
  2. Client computes: MD5(username:realm:password:nonce:method:uri)
  3. Client sends: HASH, not password!
  
  Server verifies hash using same formula
  Password never travels over network!
  
  BUT:
  - Still vulnerable to man-in-the-middle (nonce can be replayed)
  - MD5 is weak (use SHA-256 in Digest-SHA-256)
  - More complex than Basic
  - Not as secure as modern token-based auth
  
  IN PRACTICE:
  Digest auth is rarely used in modern web applications
  JWT / OAuth replaced it for web APIs
  
  HTTP spec supports it but most developers go straight to token-based auth
```

---

### 1.6 Ashish ke projects mein

```
Youngman:
  Basic Auth used for:
    - DRF Browsable API (developer testing)
    - Swagger UI (internal API documentation)
    - Celery Flower (Nginx basic_auth protection)
    - Initial SAP HANA token exchange (OAuth 2.0 with basic auth for initial request)
  
  NOT used for:
    - Customer login (JWT)
    - User-facing APIs (JWT)
    - Mobile API (JWT)
  
  SAP Authentication flow:
    Step 1: Basic Auth to get OAuth token
      POST /oauth/token
      Authorization: Basic base64(client_id:client_secret)
      grant_type=client_credentials
      
    Step 2: Use OAuth token for actual API calls
      GET /api/invoices/
      Authorization: Bearer {oauth_token}
    
    (Basic auth just for initial token exchange — standard OAuth pattern)

  Django settings for admin basic auth (browsable API only):
    REST_FRAMEWORK = {
        'DEFAULT_AUTHENTICATION_CLASSES': [
            'rest_framework_simplejwt.authentication.JWTAuthentication',
            # BasicAuthentication only for browsable API in dev:
            'rest_framework.authentication.BasicAuthentication',
        ],
    }
    
    # In production: Remove BasicAuthentication from default classes
    # Only enable for specific internal views if needed
```

---

## PART 2: ENGLISH — Interviewer ko bolne ke liye

### 2.1 Definition

> **HTTP Basic Authentication**: An authentication scheme defined in RFC 7617 where the client sends a Base64-encoded string of `username:password` in the `Authorization` header. Base64 is encoding, not encryption — HTTPS is mandatory for security. Simple, stateless, but lacks logout capability and token revocation.

---

### 2.2 Basic vs Digest vs Token Comparison

| Feature | Basic Auth | Digest Auth | Token (JWT) |
|---------|-----------|-------------|-------------|
| Password transmitted | Encoded (not encrypted) | Never (hash only) | Never |
| HTTPS required | Yes (mandatory) | Recommended | Recommended |
| Logout | Very hard | Hard | Easy (expire/blacklist token) |
| Revocation | Must change password | Must change password | Invalidate token |
| Scoping | None | None | JWT claims (scope) |
| Stateless | Yes | Yes | Yes |
| Complexity | Low | Medium | Medium |
| Best for | Internal tools | Legacy systems | Modern APIs |

---

### 2.3 Real Project Answer

> "In Youngman, Basic Authentication is used in two narrow scenarios. First, the DRF Browsable API and Swagger UI use it for developer testing — developers can quickly test APIs without needing to set up JWT tokens. Second, our SAP HANA integration uses Basic Auth in the OAuth 2.0 client credentials flow: we send the client_id and client_secret as Basic Auth credentials to the SAP token endpoint, which returns an OAuth Bearer token. That Bearer token is then used for all actual SAP API calls. For all customer-facing and user APIs, we use JWT authentication — it's stateless, supports token expiry, and allows refresh without re-authentication."

---

### 2.4 Common Follow-up Q&A

**Q1: Is Base64 the same as encryption?**
> "No. Base64 is an encoding scheme that converts binary data to printable ASCII characters using 64 characters (A-Z, a-z, 0-9, +, /). It's completely reversible without any key — `atob('YXNoaXNoOnNlY3JldDEyMw==')` gives you `ashish:secret123` in any browser console. It's used in Basic Auth only to ensure the credentials can be safely transmitted in HTTP headers (which require ASCII). HTTPS/TLS is what provides actual encryption — TLS encrypts the entire HTTP transaction including the Authorization header. Without HTTPS, Basic Auth sends your password essentially in plain text."

**Q2: How would you implement a logout for Basic Auth?**
> "It's genuinely difficult because Basic Auth credentials are stored in the browser's credential cache, not in application-controlled storage. The standard trick: when the user clicks logout, make an AJAX request to the protected endpoint with intentionally wrong credentials. The server returns 401. Most browsers then clear the cached credentials for that realm. Alternatively, change the realm on the server side — the browser's cached credentials for the old realm no longer apply. But this is hacky. The real answer is: don't use Basic Auth for user-facing apps that need proper logout. Use session cookies or JWT tokens where you control the client-side storage and can clear it explicitly."

**Q3: When is Basic Auth appropriate in production?**
> "Basic Auth is appropriate in production for: (1) machine-to-machine authentication where the 'user' is a service account with a strong, random password and credentials are stored securely (not hardcoded). (2) Internal admin tools accessed over VPN where network security is already ensured. (3) As the initial credential exchange in OAuth 2.0 client credentials flow — the client_id:client_secret is sent as Basic Auth to get an access token, which is then used for all subsequent calls. (4) Simple internal dashboards (Grafana, Flower, Jenkins) behind HTTPS. What it's NOT appropriate for: end-user login/logout workflows, mobile apps, any scenario needing fine-grained token scoping or revocation without password change."

---

## Interview Cheat Sheet

```
Basic Authentication:
  Header: Authorization: Basic base64(username:password)
  Base64 = ENCODING, not encryption
  HTTPS is MANDATORY

Problems:
  Can't really logout (browser caches)
  Password sent every request (vs JWT: once at login)
  No revocation without password change
  No scope/granularity

When OK to use:
  Internal tools (Flower, Swagger, Grafana)
  Developer testing (DRF Browsable API)
  Machine-to-machine initial auth (OAuth client_credentials)
  Simple internal tools behind HTTPS + VPN

When NOT to use:
  Customer-facing login
  Mobile applications
  APIs needing token revocation
  Long-lived user sessions

Common pattern: Basic Auth → get OAuth token → use Bearer token
  POST /auth/token
  Authorization: Basic base64(client_id:client_secret)
  → Returns: access_token (Bearer)
  
  Subsequent: Authorization: Bearer {access_token}

HTTP 401 = Authentication failed (credentials wrong/missing)
HTTP 403 = Authorized failed (credentials valid but no permission)
```
