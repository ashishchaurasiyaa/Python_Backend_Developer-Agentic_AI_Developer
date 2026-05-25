# Content Negotiation, API Anti-patterns & Design Principles

---

# PART 1: Content Negotiation

## What is Content Negotiation?
- **Content Negotiation** = client aur server ke beech agreement on format
- Client `Accept` header mein batata hai kya chahiye
- Server `Content-Type` header mein batata hai kya bhej raha hai
- Same endpoint → multiple formats (JSON, XML, CSV, MessagePack)

## Why?
```
✓ Same API endpoint → mobile (JSON), legacy system (XML), analytics (CSV)
✓ Versioning without URL change (Accept: application/vnd.myapp.v2+json)
✓ Bandwidth optimization (binary formats like MessagePack)
```

## How

### Q1: FastAPI mein content negotiation kaise implement karte hain?

**Answer:**
```python
from fastapi import FastAPI, Request
from fastapi.responses import Response, JSONResponse
import csv
import io

@app.get("/users")
async def list_users(request: Request):
    """
    Accept: application/json  → JSON response
    Accept: text/csv          → CSV download
    Accept: application/xml   → XML response
    """
    accept = request.headers.get("accept", "application/json")
    users  = await get_all_users()

    if "text/csv" in accept:
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=["id", "name", "email", "plan"])
        writer.writeheader()
        writer.writerows([u.dict() for u in users])
        return Response(
            content=output.getvalue(),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=users.csv"},
        )

    elif "application/xml" in accept:
        xml = "<users>" + "".join(
            f"<user><id>{u.id}</id><name>{u.name}</name><email>{u.email}</email></user>"
            for u in users
        ) + "</users>"
        return Response(content=xml, media_type="application/xml")

    # Default: JSON
    return JSONResponse([u.dict() for u in users])


# ─── Vendor media types (API versioning via Accept header) ───
# Accept: application/vnd.myapp.v1+json  → v1 response shape
# Accept: application/vnd.myapp.v2+json  → v2 response shape

@app.get("/posts/{id}")
async def get_post(id: int, request: Request):
    accept = request.headers.get("accept", "")

    if "vnd.myapp.v2" in accept:
        return {"id": id, "full_name": "Alice Smith", "metadata": {}}  # v2 shape

    return {"id": id, "name": "Alice"}  # v1 shape (default)


# ─── INTERVIEW: Accept header parse karo (quality values) ───
# Accept: text/html, application/json;q=0.9, */*;q=0.8
# Meaning: prefer text/html, then JSON (0.9 priority), then anything (0.8)
# q=1.0 (default) = highest preference

def best_match(accept_header: str, available: list[str]) -> str:
    """Parse Accept header and return best matching format."""
    if not accept_header:
        return available[0]

    preferences = []
    for part in accept_header.split(","):
        part = part.strip()
        if ";q=" in part:
            mime, q = part.split(";q=")
            preferences.append((mime.strip(), float(q)))
        else:
            preferences.append((part, 1.0))

    preferences.sort(key=lambda x: x[1], reverse=True)

    for mime, _ in preferences:
        if mime in available or mime == "*/*":
            return available[0] if mime == "*/*" else mime

    return available[0]  # fallback
```

---

# PART 2: API Design Anti-patterns (Common Mistakes)

## What are Anti-patterns?
- **Anti-patterns** = commonly used solutions jo actually problems create karte hain
- Interview mein: "kya galat design dekha hai?" → yahan se examples lo

## Why Avoid Them?
```
Bad API design → tight coupling → hard to change, version, maintain
Good design → clean, predictable, evolvable API
```

## How — Kya avoid karo + sahi solution kya hai

### Q1: Common REST API Anti-patterns kya hain?

**Answer:**
```python
# ─── Anti-pattern 1: Verbs in URLs ───
# BAD:
GET  /getUser/1
POST /createPost
PUT  /updateUser/1
DELETE /deletePost/1

# GOOD: Nouns, HTTP methods se action clear hai
GET    /users/1
POST   /posts
PUT    /users/1
DELETE /posts/1


# ─── Anti-pattern 2: Inconsistent response format ───
# BAD: har endpoint alag format
GET  /users/1  → { "user": { "id": 1 } }
GET  /posts/1  → { "data": { "post_id": 1 } }
POST /login    → { "token": "..." }  (no wrapper)
GET  /errors   → "Not found"  (plain string!)

# GOOD: Consistent wrapper
{
  "success": true,
  "data": { ... },
  "meta": { ... },
  "error": null
}


# ─── Anti-pattern 3: Wrong HTTP status codes ───
# BAD:
POST /login → 200 OK + { "error": "invalid password" }
DELETE /posts/1 → 200 OK + { "message": "deleted" }
POST /users → 200 OK + { "id": 1 }  # should be 201

# GOOD:
POST /login (success)     → 200 OK
POST /login (wrong pass)  → 401 Unauthorized
DELETE /posts/1           → 204 No Content
POST /users               → 201 Created + Location: /users/42


# ─── Anti-pattern 4: Exposing internal implementation ───
# BAD:
GET /mysql_users_table
GET /getUserById?sql=SELECT * FROM users WHERE id=1
GET /api/v1/postgres_posts

# GOOD: Resource-focused, implementation-agnostic
GET /users
GET /users/1
GET /posts


# ─── Anti-pattern 5: Breaking changes without versioning ───
# BAD:
# v1: { "name": "Alice" }
# "Update" to: { "full_name": "Alice Smith" }  ← existing clients BREAK!

# GOOD:
# Keep old field + add new:  { "name": "Alice", "full_name": "Alice Smith" }
# Or proper versioning: v2 endpoint with new shape

# Non-breaking changes (safe to do):
#   ✓ Add new optional field
#   ✓ Add new endpoint
#   ✓ Make required field optional
#   ✓ Add new enum value

# Breaking changes (need new version):
#   ✗ Remove field
#   ✗ Rename field
#   ✗ Change field type
#   ✗ Remove endpoint
#   ✗ Change error format


# ─── Anti-pattern 6: Ignoring idempotency ───
# BAD: POST /orders called twice → two orders created (network retry!)

# GOOD: Idempotency-Key header
POST /orders + Idempotency-Key: uuid-123
→ Same key dobara aaye → same response, no duplicate


# ─── Anti-pattern 7: God endpoint ───
# BAD: One endpoint does everything
POST /api/action
{ "type": "CREATE_USER" | "DELETE_POST" | "SEND_EMAIL" | ... }

# GOOD: Resource-specific endpoints
POST /users
DELETE /posts/1
POST /emails/send


# ─── Anti-pattern 8: Chatty API (too many small requests) ───
# BAD: App startup = 10 API calls
GET /user/1
GET /user/1/settings
GET /user/1/notifications
GET /user/1/unread_count
...

# GOOD: Aggregate endpoint
GET /user/1/dashboard  → all needed data in one call
# Or: GraphQL (client picks exactly what it needs)


# ─── Anti-pattern 9: Ignoring pagination ───
# BAD:
GET /users → returns ALL 10 million users in one response

# GOOD:
GET /users?page=1&limit=20
GET /users?cursor=abc&limit=20


# ─── Anti-pattern 10: No rate limiting ───
# BAD: API completely open → abuse, DDoS, cost explosion
# GOOD: Rate limit headers + 429 Too Many Requests response
```

---

# PART 3: API Design Principles (Richardson Maturity Model)

## What is Richardson Maturity Model?
```
Level 0: The Swamp of POX (Plain Old XML/JSON)
  POST /api
  { "action": "getUser", "id": 1 }
  
Level 1: Resources
  POST /users/1
  POST /posts/42
  (URLs identify resources, but wrong methods)

Level 2: HTTP Verbs ← Most APIs are here
  GET    /users/1
  POST   /users
  DELETE /posts/42
  Proper status codes

Level 3: HATEOAS
  GET /users/1 → { ..., "_links": { "posts": "/users/1/posts" } }
  Self-describing API
```

### Q1: REST API design ke 6 constraints kya hain?

**Answer:**
```
1. Client-Server:
   UI aur data storage alag karo → portability + scalability
   Frontend team alag, backend team alag

2. Stateless:
   Har request self-contained — server session store nahi karta
   Auth: JWT (stateless) not session cookie (stateful)
   Scale karna easy → koi bhi server handle kar sakta hai

3. Cacheable:
   Responses explicitly cacheable/non-cacheable mark karo
   Cache-Control, ETag headers → clients/CDN cache karte hain

4. Uniform Interface:
   - Resource identification (URI)
   - Manipulation through representations (JSON/XML)
   - Self-descriptive messages (Content-Type, status codes)
   - HATEOAS (optional at level 3)

5. Layered System:
   Client ko pata nahi koi proxy/load balancer beech mein hai
   API Gateway, CDN, reverse proxy — client transparent

6. Code on Demand (optional):
   Server JavaScript ya code download kara sakta hai
   Rarely used in practice
```

---

# PART 4: API Security Headers

## What & Why
```
Security headers = HTTP response headers jo browser ko security enforce karate hain
API bhi inhe bhejni chahiye — especially browser-facing APIs
```

### Q1: Kaunse security headers API mein zaroori hain?

**Answer:**
```python
from fastapi.middleware.base import BaseHTTPMiddleware

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)

        # Prevent MIME type sniffing
        response.headers["X-Content-Type-Options"] = "nosniff"

        # Prevent clickjacking (API → deny, web → sameorigin)
        response.headers["X-Frame-Options"] = "DENY"

        # Force HTTPS (HSTS)
        response.headers["Strict-Transport-Security"] = (
            "max-age=31536000; includeSubDomains; preload"
        )

        # Disable caching for sensitive endpoints
        if "/auth" in request.url.path or "/payments" in request.url.path:
            response.headers["Cache-Control"] = "no-store"
            response.headers["Pragma"]        = "no-cache"

        # Remove server fingerprint
        response.headers.pop("Server", None)
        response.headers.pop("X-Powered-By", None)

        # Referrer policy
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # Permissions policy
        response.headers["Permissions-Policy"] = "geolocation=(), camera=(), microphone=()"

        return response

app.add_middleware(SecurityHeadersMiddleware)
```

---

## Summary Table

| Anti-pattern | Problem | Solution |
|---|---|---|
| Verbs in URLs | `/getUser`, `/createPost` | Nouns + HTTP methods |
| Inconsistent response | Different formats per endpoint | `APIResponse` wrapper always |
| Wrong status codes | 200 for errors | 201 Created, 204 No Content, 429 Rate Limit |
| Breaking changes | Old clients break | Non-breaking: add fields; Breaking: new version |
| God endpoint | One POST for everything | Resource-specific endpoints |
| No pagination | 10M rows in one response | Cursor or offset pagination |
| No idempotency | Duplicate on retry | `Idempotency-Key` header |
| Chatty API | 10 calls on startup | Aggregate endpoint or GraphQL |

| Content Type | Use When |
|---|---|
| `application/json` | Default API responses |
| `text/csv` | Data export, analytics |
| `text/event-stream` | SSE / streaming |
| `multipart/form-data` | File upload |
| `application/problem+json` | RFC 7807 errors |
| `application/vnd.app.v2+json` | Versioning via Accept header |
