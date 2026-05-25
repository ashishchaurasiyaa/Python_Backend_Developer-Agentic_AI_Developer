# Django Security Hardening — Production Checklist

## Why It Matters (Senior 5 YOE Context)

Django ka default config dev-friendly hai, NOT prod-secure. Security audits regularly find:

- `DEBUG = True` in prod (huge data leak via 500 pages)
- Missing HSTS / CSP / X-Frame-Options
- Weak secret keys committed to repo
- SQL injection via raw queries
- XSS via unsafe template marks
- CSRF disabled "because frontend"

Senior 5 YOE = **owns the security posture**. Interview ask: "Walk me through your Django prod security checklist."

---

## Core Concepts

### Mandatory Settings (Prod)

```python
# settings/prod.py
import os

DEBUG = False
ALLOWED_HOSTS = ['app.example.com']
SECRET_KEY = os.environ['DJANGO_SECRET_KEY']   # min 50 chars, never in repo

# HTTPS / HSTS
SECURE_SSL_REDIRECT = True
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')  # behind LB

SECURE_HSTS_SECONDS = 31_536_000        # 1 year
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

# Cookies
SESSION_COOKIE_SECURE = True            # HTTPS only
SESSION_COOKIE_HTTPONLY = True          # no JS access
SESSION_COOKIE_SAMESITE = 'Lax'         # or 'Strict'
SESSION_COOKIE_AGE = 60 * 60 * 24 * 14  # 2 weeks

CSRF_COOKIE_SECURE = True
CSRF_COOKIE_HTTPONLY = True
CSRF_TRUSTED_ORIGINS = ['https://app.example.com']

# Content-Type sniffing
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_BROWSER_XSS_FILTER = True

# Clickjacking
X_FRAME_OPTIONS = 'DENY'

# Referrer
SECURE_REFERRER_POLICY = 'same-origin'
```

Run `python manage.py check --deploy` — Django will warn about missing settings.

### Content Security Policy (CSP)

```python
# pip install django-csp
MIDDLEWARE = ['csp.middleware.CSPMiddleware'] + MIDDLEWARE

CSP_DEFAULT_SRC = ("'self'",)
CSP_SCRIPT_SRC = ("'self'", "'unsafe-inline'", "https://cdn.example.com")
CSP_STYLE_SRC = ("'self'", "'unsafe-inline'")
CSP_IMG_SRC = ("'self'", "data:", "https:")
CSP_CONNECT_SRC = ("'self'", "https://api.example.com")
CSP_FRAME_ANCESTORS = ("'none'",)
CSP_OBJECT_SRC = ("'none'",)
CSP_REPORT_URI = '/csp-report/'
```

**Goal:** Browser blocks any script from unknown origin — XSS impact reduced.

### Secret Key Rotation

```python
# Multiple secret keys (rolling rotation)
SECRET_KEY = os.environ['DJANGO_SECRET_KEY']
SECRET_KEY_FALLBACKS = [
    os.environ.get('DJANGO_SECRET_KEY_OLD', ''),
]

# Django uses SECRET_KEY for new signing, falls back to old for verification
# Rotate old → fallback → remove after sessions expire
```

### Password Hashing

```python
PASSWORD_HASHERS = [
    'django.contrib.auth.hashers.Argon2PasswordHasher',
    'django.contrib.auth.hashers.PBKDF2PasswordHasher',  # fallback
    'django.contrib.auth.hashers.BCryptSHA256PasswordHasher',
]

# pip install argon2-cffi
```

Default Django PBKDF2 is OK; Argon2 is best (memory-hard, GPU-resistant).

### Password Validators

```python
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
     'OPTIONS': {'min_length': 12}},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]
```

Add custom: HaveIBeenPwned check, complexity rules.

### Rate Limiting Login

```python
# pip install django-axes (or django-ratelimit)
INSTALLED_APPS += ['axes']
MIDDLEWARE += ['axes.middleware.AxesMiddleware']
AUTHENTICATION_BACKENDS = [
    'axes.backends.AxesStandaloneBackend',
    'django.contrib.auth.backends.ModelBackend',
]

AXES_FAILURE_LIMIT = 5
AXES_COOLOFF_TIME = 1  # hours
AXES_RESET_ON_SUCCESS = True
```

### File Upload Hardening

```python
# settings.py
FILE_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024  # 5 MB
DATA_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024
DATA_UPLOAD_MAX_NUMBER_FIELDS = 1000

# Validate MIME type, not just extension
# Always serve uploads from separate domain (no cookie leak)
MEDIA_URL = 'https://media.example.com/media/'
```

### Raw SQL Safety

```python
# DANGER — SQL injection
User.objects.raw(f"SELECT * FROM users WHERE id = {user_input}")

# SAFE — parameterized
User.objects.raw("SELECT * FROM users WHERE id = %s", [user_input])

# Cursor — same rule
with connection.cursor() as c:
    c.execute("SELECT * FROM users WHERE email = %s", [email])
```

### Template XSS

```django
{# Django auto-escapes — safe by default #}
{{ user_input }}                  {# escaped #}

{# DANGER — manual disable #}
{{ user_input|safe }}             {# UNSAFE if user_input contains HTML #}
{% autoescape off %}{{ x }}{% endautoescape %}

{# Mark trusted HTML #}
from django.utils.safestring import mark_safe
mark_safe("<b>Trusted</b>")
```

### CSRF — Don't Disable

```python
# DRF needs CSRF for session auth, not for token/JWT auth
# Class-based exempts:
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt

@method_decorator(csrf_exempt, name='dispatch')
class MyAPIView(View):
    ...

# Only exempt if auth is token-based (no cookie)
```

### Open Redirect

```python
# DANGER
return redirect(request.GET.get('next'))

# SAFE
from django.utils.http import url_has_allowed_host_and_scheme

next_url = request.GET.get('next', '/')
if url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
    return redirect(next_url)
return redirect('/')
```

### Subresource Integrity (SRI) for CDN Scripts

```html
<script src="https://cdn.example.com/lib.js"
        integrity="sha384-abc123..."
        crossorigin="anonymous"></script>
```

### Dependency Audit

```bash
pip install pip-audit safety
pip-audit                          # check installed packages
safety check --full-report
```

CI integration: fail build if HIGH/CRITICAL CVEs detected.

---

## How It Works Internally

### `check --deploy` Output

```
?: (security.W004) You have not set a value for the SECURE_HSTS_SECONDS setting.
?: (security.W008) Your SECURE_SSL_REDIRECT setting is not set to True.
?: (security.W009) Your SECRET_KEY has less than 50 characters or less than 5 unique characters.
?: (security.W018) You should not have DEBUG set to True in deployment.
...
```

Run before every deploy.

### CSRF Middleware Flow

1. View renders form → middleware injects `csrftoken` cookie + hidden form field
2. POST request → middleware checks form CSRF token matches cookie
3. Mismatch → 403 Forbidden

### Session Backend Considerations

```python
# Default: database
SESSION_ENGINE = 'django.contrib.sessions.backends.db'

# Cached (faster, but volatile)
SESSION_ENGINE = 'django.contrib.sessions.backends.cache'

# Cached + DB fallback (recommended for HA)
SESSION_ENGINE = 'django.contrib.sessions.backends.cached_db'
```

---

## Common Pitfalls

### 1. `DEBUG = True` in Prod

500 error page exposes settings, env vars, SQL queries, request data. Always `DEBUG = False` in prod, verify via `/check`.

### 2. `ALLOWED_HOSTS = ['*']`

Allows Host header injection → email link poisoning, password reset to attacker.

### 3. Hardcoded `SECRET_KEY`

In repo or `settings.py` = bad. Env var only. Rotate after any compromise.

### 4. CSRF Exempted Globally

API teams sometimes disable CSRF — only safe if auth is purely token (no cookie). Session+CSRF must coexist.

### 5. JWT in `localStorage`

XSS → token stolen. Use `httpOnly` cookies + CSRF for SPA auth.

### 6. Untrusted `mark_safe()` / `|safe`

User-submitted HTML through `|safe` = stored XSS. Use `bleach` library to sanitize first.

### 7. Open S3 Buckets

`MEDIA_URL` points to public S3 bucket without auth → data leak. Use presigned URLs.

### 8. SQL Injection in Raw Queries

Format strings with user input = injection. Always parameterized.

### 9. SSRF via URL Field

User submits URL → server fetches it → can access internal AWS metadata (169.254.169.254). Validate URL against allowlist.

---

## Interview Q&A

**Q1:** Production Django pe security checklist batao.
**A:** (1) `DEBUG=False`, (2) tight `ALLOWED_HOSTS`, (3) env-var `SECRET_KEY`, (4) HSTS + SSL redirect, (5) Secure cookies (Secure, HttpOnly, SameSite), (6) CSP via django-csp, (7) X-Frame-Options DENY, (8) Argon2 password hasher, (9) django-axes for login rate limiting, (10) `pip-audit` in CI, (11) `manage.py check --deploy` in CI.

**Q2:** XSS Django mein kaise prevent karte ho?
**A:** Default auto-escape in templates is the first line. Never use `|safe` or `mark_safe()` on untrusted input. For user-submitted HTML (rich text), sanitize via `bleach` with allowlist. CSP as second line — even if XSS happens, browser blocks unknown scripts.

**Q3:** CSRF kab disable karna safe hai?
**A:** Only when auth is purely token-based (JWT/Bearer in header) and you don't accept cookies. DRF SessionAuth = CSRF required. DRF TokenAuth + no cookies = safe to exempt. Be careful with mixed setups.

**Q4:** SECRET_KEY leak ho gaya — kya karoge?
**A:** (1) Rotate immediately — generate new, set in env. (2) Use `SECRET_KEY_FALLBACKS` for grace period (old sessions still valid). (3) Invalidate all sessions (`Session.objects.all().delete()`). (4) Force password resets if leak was old. (5) Audit access logs for misuse.

**Q5:** SQL injection Django ORM mein possible hai?
**A:** ORM auto-parameterizes. Vulnerabilities only via `raw()`/`extra()` with string formatting, or unparameterized `cursor.execute()`. Rule: never f-string user input into SQL. Use placeholders.

**Q6:** Password hashing — kaunsa algorithm aur kyun?
**A:** Argon2id is best — memory-hard, GPU-resistant, winner of Password Hashing Competition. Django default PBKDF2 is acceptable but weaker against GPU attacks. bcrypt is OK but slower for higher work factors.

**Q7:** Rate limiting login attempts kaise karoge?
**A:** django-axes — tracks failed attempts per IP/username, locks out after N failures, configurable cooloff. Alternative: django-ratelimit (decorator-based, more flexible). Combine with Cloudflare/WAF rate limit at edge.

**Q8:** CSP report-only mode kab use karoge?
**A:** Initial rollout — `CSP_REPORT_ONLY = True` + report endpoint. Browser logs violations without blocking. After 1-2 weeks of analysis, fix violations, then enforce.

---

## Real-World Use Cases

### 1. CI Security Gate

```yaml
# .github/workflows/security.yml
- run: python manage.py check --deploy --fail-level WARNING
- run: pip-audit --vulnerability-service osv
- run: bandit -r . -ll       # static analysis
- run: safety check
```

### 2. CSP Rollout

```python
# Week 1: report-only
CSP_REPORT_ONLY = True
CSP_REPORT_URI = '/csp-report/'

# Week 2-3: analyze reports, fix violations

# Week 4: enforce
CSP_REPORT_ONLY = False
```

### 3. Sanitize User HTML

```python
import bleach

ALLOWED_TAGS = ['p', 'br', 'b', 'i', 'a', 'ul', 'li']
ALLOWED_ATTRS = {'a': ['href']}

def clean_user_html(raw):
    return bleach.clean(raw, tags=ALLOWED_TAGS, attributes=ALLOWED_ATTRS, strip=True)
```

---

## References

- [Django security docs](https://docs.djangoproject.com/en/5.0/topics/security/)
- [OWASP Django cheatsheet](https://cheatsheetseries.owasp.org/cheatsheets/Django_Security_Cheat_Sheet.html)
- `pip-audit`, `safety`, `bandit` — static + dep scan
- `django-csp`, `django-axes`, `bleach`
- Mozilla Observatory — `https://observatory.mozilla.org/`
