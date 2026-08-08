# CORS Handling — Django + DRF

## Why It Matters (Senior 5 YOE Context)

The moment an API is split from its frontend — React/Vue/mobile app on one
origin, Django on another — the browser's Same-Origin Policy blocks every
cross-origin `fetch`/`XHR` by default unless the server explicitly opts in via
CORS headers. This is one of the most common "works with curl/Postman, fails
in the browser" bugs juniors hit, and a near-universal production requirement
the moment `16_security_hardening.md`'s cookie/session hardening meets a
separate-origin SPA.

Senior interview: "Your React app on `app.example.com` calls your Django API
on `api.example.com` and every request fails in the browser console with a
CORS error, but works fine in Postman — what's happening and how do you fix
it?" → Same-Origin Policy is a **browser** enforcement mechanism, not a
server one; Postman doesn't enforce it. The server must send back
`Access-Control-Allow-Origin` (and friends) for the browser to allow the
response through to JS — you fix it server-side with `django-cors-headers`,
not by "disabling CORS" (there's nothing to disable server-side; you're
*enabling* explicit permission).

---

## Core Concepts

### What CORS Actually Is

```
Browser JS on https://app.example.com
        │
        │  fetch('https://api.example.com/orders/')
        ▼
Browser sees: different scheme/host/port than the page origin → CROSS-ORIGIN
        │
        ▼
Browser sends the request anyway (or a preflight OPTIONS first — see below),
receives the response, but WITHOLDS it from JS unless the response carries
Access-Control-Allow-Origin: https://app.example.com (or *)
```

CORS is enforced entirely by the **browser**, using headers the **server**
chooses to send. The request often still *hits* your Django view — CORS
doesn't stop the server from processing it, it stops the *browser* from
handing the response back to the calling JS. That's why "it works in
Postman/curl" is not evidence the server is fine — those tools don't run a
same-origin check at all.

### Simple Requests vs Preflighted Requests

```
SIMPLE request (no preflight) — GET/HEAD/POST with only "simple" headers
(Content-Type: application/x-www-form-urlencoded / multipart/form-data / text/plain)
        │
        ▼
Browser sends the real request directly, checks Access-Control-Allow-Origin
on the response before releasing it to JS.


PREFLIGHTED request — anything else: PUT/PATCH/DELETE, custom headers
(Authorization, X-CSRFToken, Content-Type: application/json), credentials
        │
        ▼
Browser sends an OPTIONS request FIRST:
  OPTIONS /orders/1/
  Origin: https://app.example.com
  Access-Control-Request-Method: PATCH
  Access-Control-Request-Headers: content-type, authorization
        │
        ▼
Server must respond with Access-Control-Allow-Origin,
Access-Control-Allow-Methods, Access-Control-Allow-Headers BEFORE the
browser will even send the real PATCH request.
```

Almost every real DRF API (JSON body, `Authorization` header, PATCH/DELETE)
triggers preflight — this is why CORS setup is unavoidable for a JSON API
consumed by browser JS, unlike a classic server-rendered Django app where it
never comes up.

### Setup — `django-cors-headers`

```bash
pip install django-cors-headers
```

```python
# settings.py
INSTALLED_APPS = [
    "corsheaders",
    # ...
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",   # must be HIGH in the list —
    "django.middleware.common.CommonMiddleware",  # before CommonMiddleware
    # ...
]

# Explicit allowlist (recommended over CORS_ALLOW_ALL_ORIGINS)
CORS_ALLOWED_ORIGINS = [
    "https://app.example.com",
    "https://staging.example.com",
]

# Dev convenience only — never in prod
# CORS_ALLOW_ALL_ORIGINS = True

# Regex form, for wildcard subdomains (e.g. per-tenant subdomains)
CORS_ALLOWED_ORIGIN_REGEXES = [
    r"^https://\w+\.example\.com$",
]
```

`CorsMiddleware` must sit **before** anything that could short-circuit the
response (like `CommonMiddleware`'s `APPEND_SLASH` redirect) — otherwise the
CORS headers never get attached and preflight fails even though your
allowlist is correct.

### Credentials (cookies / session auth) — the strict mode

```python
CORS_ALLOW_CREDENTIALS = True   # server: allow cookies on cross-origin requests
```

```javascript
// client: must opt in too, or the cookie won't be sent at all
fetch("https://api.example.com/orders/", { credentials: "include" })
```

With `CORS_ALLOW_CREDENTIALS = True`, **`Access-Control-Allow-Origin` can no
longer be `*`** — the spec forbids wildcard origin when credentials are
involved, browsers will reject it outright. `django-cors-headers` handles
this automatically by echoing back the specific matched origin instead of
`*` once `CORS_ALLOW_CREDENTIALS` is on — but if you were ever tempted to
hand-roll CORS headers instead of using the library, this is the rule that
trips people up.

### CORS vs CSRF — two different browsers-security mechanisms

| | **CORS** | **CSRF** |
|---|---|---|
| Protects | The API's data from being read by unauthorized JS origins | The API from unauthorized *state-changing* requests riding on a victim's existing session cookie |
| Enforced by | Browser, based on server's `Access-Control-*` response headers | Server, by validating a token the attacker's page can't forge |
| Relevant for | Any cross-origin JS `fetch`/`XHR` | Cookie/session-based auth specifically — **not** needed for token/JWT auth sent via `Authorization` header |
| Django mechanism | `django-cors-headers` middleware | `CsrfViewMiddleware` + `X-CSRFToken` header |

If your frontend uses **cookie-based session auth** across origins, you need
**both** CORS (to let the browser hand the response to JS) **and** CSRF
protection (to stop a malicious third-party site from riding the same
cookie) — see `16_security_hardening.md`'s CSRF section for the token side.
If you use **token/JWT auth** (`Authorization: Bearer <token>`), CSRF isn't
relevant (no ambient cookie for an attacker to ride), but CORS still is —
the browser still needs permission to let JS read the response.

```python
# settings.py — needed alongside CORS when using cookie-based auth
# cross-origin (Django's CSRF check is separate from CORS's origin check)
CSRF_TRUSTED_ORIGINS = [
    "https://app.example.com",
]
```

### Restricting Headers/Methods Precisely

```python
CORS_ALLOW_METHODS = ["GET", "POST", "PATCH", "DELETE"]

CORS_ALLOW_HEADERS = [
    "accept",
    "authorization",
    "content-type",
    "x-csrftoken",
]

CORS_EXPOSE_HEADERS = ["X-Total-Count"]  # custom response headers JS can read
```

By default, JS can only read a small "safelisted" set of response headers
(`Content-Type`, `Content-Length`, etc.) even on an allowed origin — anything
custom (pagination totals, rate-limit headers) needs
`Access-Control-Expose-Headers`, set via `CORS_EXPOSE_HEADERS`. This trips
people building custom pagination headers (`X-Total-Count`) that work fine
server-side but silently read as `undefined` in the frontend.

---

## How It Works Internally

### `CorsMiddleware`'s Two Jobs

```
1. On OPTIONS preflight requests matching CORS_URLS_REGEX:
   short-circuits the request, returns a bare response with
   Access-Control-Allow-* headers, never reaches your view at all.

2. On the actual GET/POST/etc response (after your view runs):
   inspects the Origin header, checks it against
   CORS_ALLOWED_ORIGINS / CORS_ALLOWED_ORIGIN_REGEXES / CORS_ALLOW_ALL_ORIGINS,
   and if allowed, attaches Access-Control-Allow-Origin (+ credentials/expose
   headers as configured) to the OUTGOING response.
```

Critically: on the real request, your Django view **still runs** even for a
disallowed origin — `CorsMiddleware` doesn't block the request from being
processed, it only controls whether the *browser* releases the response to
JS. Server-side logs will show a 200 that the frontend dev swears never
arrived — that's the CORS gap, not a server bug, and it's the single most
common confusion point.

### Preflight Caching

```python
CORS_PREFLIGHT_MAX_AGE = 86400   # seconds browser may cache a preflight result
```

Without this, every single PATCH/DELETE/custom-header request pays for a
full extra OPTIONS round-trip. Setting a sane max-age lets the browser skip
re-preflighting the same origin+method+headers combination for that long —
real latency win on API-heavy frontends.

---

## Common Pitfalls

### 1. `CORS_ALLOW_ALL_ORIGINS = True` Left On in Production
Fine for local dev against a frontend on a random port; in prod it means any
website can read your API's responses from a logged-in user's browser if
they're also using cookie auth (compounds badly with #2 below). Use an
explicit `CORS_ALLOWED_ORIGINS` list per environment.

### 2. `CORS_ALLOW_ALL_ORIGINS = True` + `CORS_ALLOW_CREDENTIALS = True`
`django-cors-headers` will actually refuse to combine these safely (it won't
emit a literal `*` when credentials are on), but hand-rolled CORS
middleware or a misconfigured reverse proxy doing this combination is a
real vulnerability — it means any origin can make authenticated
requests using a victim's session cookie and read the response.

### 3. `CorsMiddleware` Ordered After `CommonMiddleware`
`CommonMiddleware`'s slash-redirect / other short-circuits can return a
response before `CorsMiddleware` gets a chance to attach headers, so
preflight passes but the real (redirected) response comes back with no
`Access-Control-Allow-Origin` — browser blocks it, and the failure looks
identical to a plain misconfigured allowlist. Always put
`corsheaders.middleware.CorsMiddleware` near the top, before
`CommonMiddleware`.

### 4. Forgetting `CSRF_TRUSTED_ORIGINS` for Cross-Origin Cookie Auth
CORS being configured correctly does **not** exempt you from CSRF — a
cross-origin POST with cookie auth still needs the frontend's origin listed
in `CSRF_TRUSTED_ORIGINS` (Django 4+) or the request gets a 403 from
`CsrfViewMiddleware`, independent of whatever CORS says.

### 5. Wildcard Subdomain Regex Too Loose
`CORS_ALLOWED_ORIGIN_REGEXES = [r"^https://.*\.example\.com$"]` (unescaped
`.` matching any character, not just a literal dot) can accidentally match
an attacker-controlled `evilexample.com` if the regex isn't anchored
carefully — always anchor with `^` / `$` and escape literal dots as `\.`.

### 6. Testing Only With Postman/curl, Never a Real Browser
Postman and curl don't enforce Same-Origin Policy at all, so "it works in
Postman" proves nothing about whether the browser will actually release the
response to your frontend's JS. CORS bugs only show up in an actual browser
console (or a headless browser test) — see the practical file's
`APITestCase` example for a way to assert the headers server-side without
needing a real browser.

---

## Interview Q&A

**Q: A request works fine in Postman but fails in the browser with a CORS error — is the server broken?**
A: Not necessarily. CORS is enforced by the browser, not the server —
Postman never applies Same-Origin Policy. The server may be returning a
perfectly valid 200; the browser is just refusing to hand that response to
the page's JS because the response is missing
`Access-Control-Allow-Origin` for that origin. Check server logs: if the
request landed and returned 200, it's a CORS config issue, not a server bug.

**Q: Do you need CORS if your frontend uses JWT auth instead of cookies?**
A: Yes — CORS is about which origins the *browser* lets JS read responses
from, completely independent of the auth mechanism. What you likely
**don't** need with JWT-in-header auth is CSRF protection (no ambient
cookie for a third-party site to ride) — but CORS still applies.

**Q: Why does `Access-Control-Allow-Origin: *` stop working the moment you enable credentials?**
A: The CORS spec explicitly forbids combining a wildcard origin with
`Access-Control-Allow-Credentials: true` — allowing any origin to make
authenticated (cookie-carrying) requests would defeat the same-origin
protection entirely. Browsers reject the combination outright; you must
echo back the specific requesting origin instead, which is what
`django-cors-headers` does automatically once `CORS_ALLOW_CREDENTIALS = True`.

**Q: What's the difference between what CORS protects against and what CSRF protects against?**
A: CORS controls whether cross-origin JS can *read* your API's responses.
CSRF protects against a malicious site *causing* state-changing requests
using a victim's existing session cookie, without needing to read the
response at all (a form POST or `<img>`-triggered GET doesn't care about
CORS). They're independent — a correctly CORS-configured API using cookie
auth still needs CSRF tokens, and a token-auth API needs CORS but not CSRF.

**Q: Your frontend adds a custom `X-Total-Count` response header for pagination, and it works via curl but reads as `undefined` in the frontend JS — why?**
A: Browsers only expose a small safelisted set of response headers to JS by
default (`Content-Type`, `Content-Length`, a few others), regardless of
whether the origin itself is CORS-allowed. Custom headers need to be
explicitly listed in `Access-Control-Expose-Headers`
(`CORS_EXPOSE_HEADERS` in `django-cors-headers`) or JS simply can't see
them, even though curl/Postman show them fine (again — those tools don't
enforce browser header-visibility rules either).

---

## Real-World Use Cases

### 1. SPA + API on Separate Subdomains
`app.example.com` (React, deployed to a CDN) calling `api.example.com`
(Django). Token auth (no cookies) → CORS needed, CSRF not needed. Explicit
`CORS_ALLOWED_ORIGINS = ["https://app.example.com"]`.

### 2. Multi-Tenant SaaS with Per-Tenant Subdomains
`{tenant}.app.example.com` frontends all calling one shared API —
`CORS_ALLOWED_ORIGIN_REGEXES` with a tight, anchored, escaped pattern,
cross-referenced with `10_multitenant_apidocs.md`'s tenant-resolution
middleware (tenant identified from the same `Origin`/`Host` the CORS check
already parses).

### 3. Mobile App + Web Admin Sharing One Django API
Native mobile clients (no browser, no CORS enforcement at all — CORS is
irrelevant to them) alongside a browser-based admin SPA on a separate
origin — `CORS_ALLOWED_ORIGINS` only needs to list the admin SPA's origin;
mobile traffic is unaffected either way since there's no browser Same-Origin
Policy involved.

---

Related: [16_security_hardening.md](16_security_hardening.md) (CSRF token
setup this doc assumes for cookie-based cross-origin auth),
[27_custom_user_model_auth.md](27_custom_user_model_auth.md) (JWT auth,
which sidesteps CSRF but still needs CORS),
[10_multitenant_apidocs.md](10_multitenant_apidocs.md) (per-tenant origin
patterns), [43_drf_content_negotiation.md](43_drf_content_negotiation.md)
(the `Accept`/`Content-Type` headers negotiated on the same requests CORS
gates).

## References

- [django-cors-headers documentation](https://github.com/adamchainz/django-cors-headers)
- [MDN — Cross-Origin Resource Sharing (CORS)](https://developer.mozilla.org/en-US/docs/Web/HTTP/CORS)
- [Django — CSRF_TRUSTED_ORIGINS](https://docs.djangoproject.com/en/stable/ref/settings/#csrf-trusted-origins)
