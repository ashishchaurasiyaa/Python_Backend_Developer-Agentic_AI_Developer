# CORS + CSP + Security Headers Deep Dive

## Quick Concepts

**WHAT:**
- **CORS** = Cross-Origin Resource Sharing (browser security)
- **CSP** = Content Security Policy (XSS defense)
- **HSTS** = HTTP Strict Transport Security (force HTTPS)
- **X-Frame-Options** = Clickjacking defense
- **Referrer-Policy** = Control referer header leakage
- **Permissions-Policy** = Control browser features
- **SRI** = Subresource Integrity (third-party script verification)

---

## Andar kya hota hai — CORS BROWSER Enforce Karta Hai, Server Nahi

### Server request ko process to KARTA HAI — CORS sirf JS ko response PADHNE se rokta hai

```
Browser JS: fetch("https://api.other-site.com/data")
Server: request receive karta hai, PROCESS karta hai, response bhej deta hai
        (server ko koi fark nahi padta CORS ka — woh hamesha kaam karta hai)

Browser: response aane ke BAAD check karta hai — response headers mein
         "Access-Control-Allow-Origin" hai jo is calling-page ke origin
         ko allow karta hai?
           HAAN → JS ko response data milta hai
           NAHI → JS ko response BLOCKED dikhta hai (network tab mein
                  response aaya tha, par JS use READ nahi kar sakta)
```

Yehi wajah hai `curl`/Postman/server-to-server calls CORS se kabhi affect
nahi hote — CORS ek BROWSER-ONLY enforcement hai, server-side protection
nahi. Server apni taraf se hamesha request process karta hai; CORS sirf
decide karta hai ki JAVASCRIPT us response ko dekh sakta hai ya nahi.

### Preflight — "non-simple" requests ke liye ek EXTRA round-trip

Custom headers, JSON content-type, ya GET/POST/HEAD ke alawa method wali
request "non-simple" maani jaati hai — browser pehle ek `OPTIONS` request
(preflight) khud-ba-khud bhejta hai, poochta hai "kya yeh actual request
allowed hai?" (`Access-Control-Allow-Methods`/`-Headers` check karke). Sirf
preflight response allow kare TABHI browser ASLI request bhejta hai — yehi
wajah hai custom-header wali API calls mein ek EXTRA network round-trip
dikhta hai jo simple GET requests mein nahi hota.

**WHY security headers critical:**
- Most are browser-enforced (server just sets them)
- One missing header = XSS, clickjacking, MITM possible
- Free defense layer (no app code changes needed)
- SecurityHeaders.com / Mozilla Observatory grade your site

**HOW headers stack:**
```
Browser request
    ↓
Server response with headers:
    Content-Security-Policy: ...     ← XSS protection
    Strict-Transport-Security: ...   ← Force HTTPS
    X-Frame-Options: DENY            ← Clickjacking
    X-Content-Type-Options: nosniff  ← MIME sniffing
    Referrer-Policy: same-origin     ← Privacy
    Permissions-Policy: ...          ← Feature restrictions
    Access-Control-Allow-Origin: ... ← CORS
    ↓
Browser enforces these rules client-side
```

---

## Interview Questions & Answers

### Q1: CORS deep dive — Simple vs Preflight requests?

**Answer:**

**WHAT:** Browser security mechanism that prevents JavaScript from making requests to different origins.

**WHY CORS exists:**
```
Without CORS:
- Malicious site evil.com runs JS
- JS calls bank.com API (with your cookies)
- Money transferred!

With CORS:
- Browser checks if bank.com allows requests from evil.com
- bank.com says NO (Access-Control-Allow-Origin: only-allowed-sites)
- Browser blocks the request
```

**HOW — Two types of requests:**

**Type 1: Simple Request (no preflight)**

Conditions ALL must be true:
- Method: GET, POST, or HEAD
- Headers: only "safe" headers (Accept, Content-Type [limited])
- Content-Type: text/plain, multipart/form-data, application/x-www-form-urlencoded

```
Browser → Server:
  GET /api/data HTTP/1.1
  Origin: https://app.example.com

Server → Browser:
  HTTP/1.1 200 OK
  Access-Control-Allow-Origin: https://app.example.com
```

**Type 2: Preflight Request (OPTIONS first)**

Triggered by:
- Methods: PUT, DELETE, PATCH
- Custom headers: Authorization, X-Custom-*
- Content-Type: application/json

```
Browser → Server (PREFLIGHT):
  OPTIONS /api/users HTTP/1.1
  Origin: https://app.example.com
  Access-Control-Request-Method: POST
  Access-Control-Request-Headers: Content-Type, Authorization

Server → Browser:
  HTTP/1.1 204 No Content
  Access-Control-Allow-Origin: https://app.example.com
  Access-Control-Allow-Methods: POST, PUT, DELETE
  Access-Control-Allow-Headers: Content-Type, Authorization
  Access-Control-Max-Age: 86400      ← Cache for 24h

Then actual request:
Browser → Server:
  POST /api/users HTTP/1.1
  Origin: https://app.example.com
  ...
```

**HOW — FastAPI CORS setup:**

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

# ⭐ Production setup
app.add_middleware(
    CORSMiddleware,
    # NEVER use "*" with credentials
    allow_origins=[
        "https://app.example.com",
        "https://admin.example.com",
    ],
    allow_credentials=True,        # Send cookies
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=[
        "Accept",
        "Accept-Language",
        "Content-Type",
        "Authorization",
        "X-Request-ID",
    ],
    expose_headers=[
        "X-RateLimit-Limit",
        "X-RateLimit-Remaining",
        "X-Request-ID",
    ],
    max_age=86400,                # Cache preflight 24 hours
)


# ⭐ Multi-environment: allow per env
import os

def get_cors_origins():
    env = os.getenv("ENVIRONMENT", "development")
    return {
        "development": ["http://localhost:3000", "http://localhost:5173"],
        "staging": ["https://staging.example.com"],
        "production": ["https://app.example.com"],
    }.get(env, [])
```

**Django REST Framework CORS:**

```python
# settings.py
INSTALLED_APPS = [..., "corsheaders"]
MIDDLEWARE = ["corsheaders.middleware.CorsMiddleware", ...]

CORS_ALLOWED_ORIGINS = [
    "https://app.example.com",
]
CORS_ALLOW_CREDENTIALS = True
CORS_PREFLIGHT_MAX_AGE = 86400

# Or regex
CORS_ALLOWED_ORIGIN_REGEXES = [
    r"^https://.*\.example\.com$",
]
```

---

### Q2: CORS critical gotchas — what mistakes break apps?

**Answer:**

**Mistake 1: Wildcard with credentials**
```python
# ❌ WRONG
allow_origins=["*"]
allow_credentials=True
# Browser will BLOCK — security violation
# Spec: "*" not allowed with credentials

# ✅ RIGHT
allow_origins=["https://app.example.com"]
allow_credentials=True
```

**Mistake 2: Forgetting expose_headers**
```python
# Backend returns custom header
response.headers["X-Total-Count"] = "100"

# JS tries to read it
const total = response.headers.get("X-Total-Count");  // ❌ undefined!

# Fix: expose_headers
allow_origins=["https://app.example.com"]
expose_headers=["X-Total-Count"]
```

**Mistake 3: OPTIONS not allowed**
```python
# ❌ DRF view that doesn't allow OPTIONS
class MyView(APIView):
    http_method_names = ["get", "post"]  # No OPTIONS!

# ✅ Always allow OPTIONS for preflight
http_method_names = ["get", "post", "options"]
```

**Mistake 4: Origin reflected (wildcard via header reflection)**
```python
# ❌ DANGEROUS — reflects any origin
@app.middleware("http")
async def add_cors(request, call_next):
    response = await call_next(request)
    response.headers["Access-Control-Allow-Origin"] = request.headers.get("Origin", "*")
    response.headers["Access-Control-Allow-Credentials"] = "true"
    return response
# Attacker: Origin: https://evil.com → reflected → works ❌

# ✅ Whitelist
ALLOWED = ["https://app.example.com"]
origin = request.headers.get("Origin")
if origin in ALLOWED:
    response.headers["Access-Control-Allow-Origin"] = origin
```

**Mistake 5: Cookies + cross-site**
```python
# Backend: api.example.com
# Frontend: app.example.com (different subdomain!)

# Need both:
# 1. CORS allows credentials
# 2. Cookie SameSite=None + Secure (modern browsers)
response.set_cookie(
    "session",
    "abc123",
    httponly=True,
    secure=True,           # ⭐ HTTPS only
    samesite="none",       # ⭐ Allow cross-site
    domain=".example.com", # Available to all subdomains
)
```

---

### Q3: CSP (Content Security Policy) — full directives?

**Answer:**

**WHAT:** Browser-enforced policy declaring allowed sources for scripts, styles, images, etc.

**WHY:**
- Best XSS defense (blocks unauthorized script execution)
- Even if attacker injects `<script>`, browser blocks it
- Reduces impact of dependency vulnerabilities

**HOW — All CSP directives:**

```python
def build_csp_header():
    """
    INTERVIEW: Production CSP header.
    """
    policy = {
        # ⭐ Default fallback for all resource types
        "default-src": ["'self'"],

        # Scripts
        "script-src": [
            "'self'",
            "https://cdn.example.com",
            # "'unsafe-inline'",   # ❌ Avoid! Enables inline scripts
            "'nonce-{request_nonce}'",  # ✅ Allow inline with nonce
        ],

        # Styles
        "style-src": [
            "'self'",
            "https://fonts.googleapis.com",
            # "'unsafe-inline'",   # ⚠️ Often needed for CSS-in-JS
        ],

        # Images
        "img-src": [
            "'self'",
            "data:",                # Base64 images
            "https:",               # Any HTTPS source
            "https://cdn.example.com",
        ],

        # Fonts
        "font-src": [
            "'self'",
            "https://fonts.gstatic.com",
        ],

        # AJAX/WebSocket
        "connect-src": [
            "'self'",
            "https://api.example.com",
            "wss://ws.example.com",
        ],

        # Frames (iframes you embed)
        "frame-src": ["'self'"],

        # Who can embed YOU
        "frame-ancestors": ["'none'"],   # ⭐ Stops clickjacking

        # Form submission targets
        "form-action": ["'self'"],

        # Base URI for relative URLs
        "base-uri": ["'self'"],

        # Object/embed/applet
        "object-src": ["'none'"],

        # Media
        "media-src": ["'self'", "https://media.example.com"],

        # Workers
        "worker-src": ["'self'"],

        # Manifest
        "manifest-src": ["'self'"],

        # Force HTTPS
        "upgrade-insecure-requests": [],

        # Block mixed content
        "block-all-mixed-content": [],

        # Report violations
        "report-uri": ["https://example.com/csp-report"],
        "report-to": ["csp-endpoint"],
    }

    return "; ".join(
        f"{k} {' '.join(v)}" if v else k
        for k, v in policy.items()
    )
```

**HOW — FastAPI CSP middleware:**

```python
import secrets
from starlette.middleware.base import BaseHTTPMiddleware

class CSPMiddleware(BaseHTTPMiddleware):
    """
    INTERVIEW: CSP with per-request nonce for inline scripts.
    """
    async def dispatch(self, request, call_next):
        # Generate nonce per request (for inline scripts)
        nonce = secrets.token_urlsafe(16)
        request.state.csp_nonce = nonce

        response = await call_next(request)

        csp = (
            "default-src 'self'; "
            f"script-src 'self' 'nonce-{nonce}' https://cdn.example.com; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "img-src 'self' data: https:; "
            "font-src 'self' https://fonts.gstatic.com; "
            "connect-src 'self' https://api.example.com; "
            "frame-ancestors 'none'; "
            "form-action 'self'; "
            "base-uri 'self'; "
            "object-src 'none'; "
            "upgrade-insecure-requests; "
            "report-uri /csp-report;"
        )

        response.headers["Content-Security-Policy"] = csp
        return response

app.add_middleware(CSPMiddleware)


# ⭐ CSP violation reporting endpoint
@app.post("/csp-report")
async def csp_report(request: Request):
    body = await request.json()
    report = body.get("csp-report", {})
    log.warning("csp_violation",
                violated_directive=report.get("violated-directive"),
                blocked_uri=report.get("blocked-uri"),
                document_uri=report.get("document-uri"))
    return {"status": "received"}
```

---

### Q4: HSTS — full setup including preload?

**Answer:**

**WHAT:** Header telling browsers "always use HTTPS for this domain."

**WHY:**
- Prevents HTTP downgrade attacks
- First connection vulnerable (TOFU), preload solves this
- Browser refuses HTTP entirely after first HTTPS visit

**HOW — Layered setup:**

**Level 1: Basic HSTS**
```python
response.headers["Strict-Transport-Security"] = "max-age=31536000"
# 1 year, this domain only
```

**Level 2: Include subdomains**
```python
response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
# Apply to all *.example.com
```

**Level 3: Preload eligible (max security)**
```python
response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains; preload"
# Submit to https://hstspreload.org
# Browsers ship preload list — HTTPS enforced before first visit
```

**Critical: Preload is PERMANENT**
- Can take months to remove
- Test extensively before submitting
- Ensure ALL subdomains support HTTPS

**HOW — Nginx HSTS:**

```nginx
server {
    listen 443 ssl http2;
    server_name example.com;

    # Always HSTS on HTTPS responses
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains; preload" always;
}

# Redirect HTTP → HTTPS
server {
    listen 80;
    server_name example.com;
    return 301 https://$host$request_uri;
}
```

---

### Q5: X-Frame-Options, X-Content-Type-Options — what + why?

**Answer:**

**X-Frame-Options (Clickjacking defense)**

**WHAT:** Controls if your site can be embedded in iframes.

**WHY:**
```
Clickjacking attack:
1. Attacker embeds your-bank.com in invisible iframe
2. Overlays fake button "Click here for prize"
3. User clicks → actually clicks "Transfer money" in iframe
4. Money sent (you're logged in)
```

**HOW:**
```python
# Option 1: Deny all framing
response.headers["X-Frame-Options"] = "DENY"

# Option 2: Allow same origin
response.headers["X-Frame-Options"] = "SAMEORIGIN"

# Option 3: Allow specific origin (deprecated, use CSP frame-ancestors)
response.headers["X-Frame-Options"] = "ALLOW-FROM https://example.com"

# ⭐ MODERN: Use CSP instead
response.headers["Content-Security-Policy"] = "frame-ancestors 'none'"
# More flexible, supports multiple origins
```

---

**X-Content-Type-Options (MIME Sniffing prevention)**

**WHAT:** Prevents browser from guessing content type.

**WHY:**
```
Attack scenario:
1. User uploads "image.png" (actually contains <script>)
2. Browser MIME-sniffs → "looks like JavaScript"
3. Executes the script
4. XSS!
```

**HOW:**
```python
response.headers["X-Content-Type-Options"] = "nosniff"
# Browser strictly respects Content-Type header
```

---

### Q6: Referrer-Policy aur Permissions-Policy?

**Answer:**

**Referrer-Policy**

**WHAT:** Controls Referer header sent in outgoing requests.

**WHY:**
```
Without policy:
You visit: https://app.com/admin/users/secret-token-abc
Click external link → external site receives Referer header
External site logs: "User came from /admin/users/secret-token-abc"
TOKEN LEAKED!
```

**HOW — All values:**

```python
# Don't send any referer
response.headers["Referrer-Policy"] = "no-referrer"

# Only origin (https://app.com, no path)
response.headers["Referrer-Policy"] = "origin"

# Origin only for cross-origin requests
response.headers["Referrer-Policy"] = "strict-origin"

# Full URL same-origin, origin only cross-origin
response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"   # ⭐ Recommended

# Same-origin: send full URL, cross-origin: nothing
response.headers["Referrer-Policy"] = "same-origin"
```

---

**Permissions-Policy (formerly Feature-Policy)**

**WHAT:** Restrict browser features (geolocation, camera, etc.).

**WHY:**
- Prevent third-party scripts from accessing sensitive APIs
- Disable features you don't use
- Defense in depth

**HOW:**

```python
permissions_policy = ", ".join([
    "accelerometer=()",                  # Disabled entirely
    "camera=()",
    "geolocation=()",
    "gyroscope=()",
    "magnetometer=()",
    "microphone=()",
    "payment=(self)",                    # Only same-origin
    "usb=()",
    "fullscreen=(self https://video.example.com)",
])

response.headers["Permissions-Policy"] = permissions_policy
```

---

### Q7: Subresource Integrity (SRI) — third-party scripts?

**Answer:**

**WHAT:** Hash verification for external resources.

**WHY:**
```
You include: <script src="https://cdn.example.com/jquery.js"></script>

Threat: CDN compromised → malicious code injected → XSS on your site

With SRI:
- Hash of jquery.js computed at build time
- Browser verifies hash matches before executing
- Mismatch = script blocked
```

**HOW — Add SRI:**

```html
<!-- Compute hash: openssl dgst -sha384 -binary jquery.js | base64 -A -->

<script
    src="https://cdn.jquery.com/jquery-3.6.0.min.js"
    integrity="sha384-vtXRMe3mGCbOeY7l30aIg8H9p3GdeSe4IFlP6G8t3IHb5UHGgRkj7XbGGGYrLLEN"
    crossorigin="anonymous">
</script>

<link
    rel="stylesheet"
    href="https://cdn.example.com/style.css"
    integrity="sha384-..."
    crossorigin="anonymous">
```

**Bundler auto-SRI (Vite/Webpack):**

```javascript
// vite.config.js
import { defineConfig } from 'vite';
import sri from 'vite-plugin-sri';

export default defineConfig({
  plugins: [
    sri({ algorithms: ['sha384'] })
  ]
});
```

---

### Q8: Complete security headers middleware — production-ready?

**Answer:**

```python
# security_middleware.py
import secrets
from starlette.middleware.base import BaseHTTPMiddleware

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    INTERVIEW: All security headers in one middleware.
    Aim for Mozilla Observatory A+ grade.
    """
    def __init__(self, app, allowed_origins: list[str] = None):
        super().__init__(app)
        self.allowed_origins = allowed_origins or []

    async def dispatch(self, request, call_next):
        # Generate nonce for CSP
        nonce = secrets.token_urlsafe(16)
        request.state.csp_nonce = nonce

        response = await call_next(request)

        # ⭐ HSTS — force HTTPS for 1 year
        response.headers["Strict-Transport-Security"] = (
            "max-age=31536000; includeSubDomains; preload"
        )

        # ⭐ CSP — XSS defense
        response.headers["Content-Security-Policy"] = (
            f"default-src 'self'; "
            f"script-src 'self' 'nonce-{nonce}'; "
            f"style-src 'self' 'unsafe-inline'; "
            f"img-src 'self' data: https:; "
            f"font-src 'self' https://fonts.gstatic.com; "
            f"connect-src 'self'; "
            f"frame-ancestors 'none'; "
            f"form-action 'self'; "
            f"base-uri 'self'; "
            f"object-src 'none'; "
            f"upgrade-insecure-requests;"
        )

        # ⭐ Clickjacking
        response.headers["X-Frame-Options"] = "DENY"

        # ⭐ MIME sniffing
        response.headers["X-Content-Type-Options"] = "nosniff"

        # ⭐ Referrer privacy
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # ⭐ Permissions
        response.headers["Permissions-Policy"] = (
            "accelerometer=(), camera=(), geolocation=(), "
            "gyroscope=(), magnetometer=(), microphone=(), "
            "payment=(self), usb=()"
        )

        # ⭐ Cross-Origin policies (Spectre/Meltdown defense)
        response.headers["Cross-Origin-Opener-Policy"] = "same-origin"
        response.headers["Cross-Origin-Embedder-Policy"] = "require-corp"
        response.headers["Cross-Origin-Resource-Policy"] = "same-site"

        # Remove server fingerprinting
        if "server" in response.headers:
            del response.headers["server"]
        if "x-powered-by" in response.headers:
            del response.headers["x-powered-by"]

        return response


# Add to FastAPI
app.add_middleware(SecurityHeadersMiddleware)


# Django version
class SecurityHeadersMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        # Set headers...
        return response
```

---

## Security Headers Checklist

```markdown
### Mandatory (set on all responses)
- [ ] Strict-Transport-Security (HSTS, 1 year, includeSubDomains)
- [ ] Content-Security-Policy (XSS defense)
- [ ] X-Frame-Options: DENY (or CSP frame-ancestors)
- [ ] X-Content-Type-Options: nosniff
- [ ] Referrer-Policy: strict-origin-when-cross-origin

### Recommended
- [ ] Permissions-Policy (disable unused features)
- [ ] Cross-Origin-Opener-Policy
- [ ] Cross-Origin-Embedder-Policy
- [ ] Cross-Origin-Resource-Policy

### CORS
- [ ] Whitelist exact origins (NEVER "*" with credentials)
- [ ] Explicit allowed methods
- [ ] Explicit allowed headers
- [ ] expose_headers for custom response headers
- [ ] max_age for preflight cache

### Third-Party
- [ ] SRI on external scripts/styles
- [ ] crossorigin="anonymous" on SRI elements

### Cookies
- [ ] HttpOnly (prevent JS access)
- [ ] Secure (HTTPS only)
- [ ] SameSite=Strict (or Lax for OAuth)
- [ ] __Host- prefix for session cookies (optional)

### Server Fingerprinting
- [ ] Remove Server header
- [ ] Remove X-Powered-By header

### Testing
- [ ] Mozilla Observatory: A+ grade
- [ ] securityheaders.com: A+ grade
- [ ] SSL Labs: A+ rating
- [ ] CSP violation monitoring
```

---

## Quick Reference Table

| Header | Purpose | Recommended Value |
|---|---|---|
| `Strict-Transport-Security` | Force HTTPS | `max-age=31536000; includeSubDomains; preload` |
| `Content-Security-Policy` | XSS defense | See full example above |
| `X-Frame-Options` | Clickjacking | `DENY` |
| `X-Content-Type-Options` | MIME sniffing | `nosniff` |
| `Referrer-Policy` | Privacy | `strict-origin-when-cross-origin` |
| `Permissions-Policy` | Feature lockdown | Disable unused (camera, geo, etc.) |
| `Cross-Origin-Opener-Policy` | Process isolation | `same-origin` |
| `Cross-Origin-Embedder-Policy` | Cross-origin embedding | `require-corp` |
| `Access-Control-Allow-Origin` | CORS | Exact origin (never `*` with credentials) |
| `Access-Control-Allow-Credentials` | CORS cookies | `true` (if needed) |
