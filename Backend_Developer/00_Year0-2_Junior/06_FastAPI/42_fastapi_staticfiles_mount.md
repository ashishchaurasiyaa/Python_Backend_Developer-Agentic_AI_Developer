# FastAPI StaticFiles Mount

## Why It Matters

FastAPI is usually API-only (a separate frontend/CDN serves static assets), so
this is lower-frequency than most topics in this folder — but it still comes
up: serving uploaded file previews, a small admin dashboard bundled with the
API, OpenAPI docs assets in an air-gapped environment, or a simple server-rendered
health-check page. Knowing `StaticFiles` exists and its limits (not a CDN
replacement) is enough depth for interviews.

Senior interview: "Your API also needs to serve user-uploaded images. Options?"
→ `StaticFiles` for small/internal scale, S3 + CDN (CloudFront) for anything
production-scale — know when each applies.

---

## Core Concepts

### Basic mount

```python
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

app = FastAPI()

app.mount("/static", StaticFiles(directory="static"), name="static")
```

Directory layout:
```
project/
├── main.py
└── static/
    ├── style.css
    └── logo.png
```

Now `GET /static/logo.png` serves the file directly — `StaticFiles` handles
MIME-type detection, `ETag`/`Last-Modified` headers, and range requests
(needed for video/audio seeking) automatically.

---

### Serving uploaded files (user-generated content)

```python
import os
from fastapi import FastAPI, UploadFile
from fastapi.staticfiles import StaticFiles

app = FastAPI()

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

@app.post("/upload")
async def upload_file(file: UploadFile):
    path = os.path.join(UPLOAD_DIR, file.filename)
    with open(path, "wb") as f:
        f.write(await file.read())
    return {"url": f"/uploads/{file.filename}"}

app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")
```

**Gotcha:** never trust `file.filename` directly — sanitize it (strip path
separators) or you've built a path-traversal vulnerability
(`../../etc/passwd` as a filename). Use `uuid4()`-generated names in practice.

---

### Single-Page-App (SPA) fallback pattern

```python
from fastapi.staticfiles import StaticFiles
from starlette.responses import FileResponse

class SPAStaticFiles(StaticFiles):
    async def get_response(self, path: str, scope):
        response = await super().get_response(path, scope)
        if response.status_code == 404:
            # unknown route → let the SPA's client-side router handle it
            response = await super().get_response("index.html", scope)
        return response

app.mount("/", SPAStaticFiles(directory="frontend/dist", html=True), name="spa")
```

This is the pattern for bundling a React/Vue build output directly with a
FastAPI backend — any unmatched path falls back to `index.html` so client-side
routing (`/dashboard`, `/settings`) still works on a hard refresh.

---

### `html=True` shortcut

```python
app.mount("/", StaticFiles(directory="public", html=True), name="public")
```

`html=True` auto-serves `index.html` for directory requests (`GET /` →
`public/index.html`) — useful for a minimal server-rendered docs/status page.

---

## When NOT to use StaticFiles (the actual interview point)

| Scale | Use |
|---|---|
| Few files, internal tool, low traffic | `StaticFiles` — simplest, zero extra infra |
| User uploads, production, need durability | **S3** (or equivalent object storage) — `StaticFiles` has no built-in redundancy/backup |
| High traffic, global users | **CDN in front of S3** (CloudFront/Cloudflare) — `StaticFiles` serves through your app process, no edge caching, adds load to your API workers |
| Video/large media | S3 + CDN + signed URLs — streaming large files through the FastAPI process wastes worker capacity that should be handling API requests |

The interview-correct answer for "how do you serve user file uploads at
scale" is **never** "StaticFiles alone" — it's presigned S3 URLs (see
`17_storage_backends_s3.md` equivalent pattern in the Django/DRF folder) so
the file bytes never round-trip through your application server at all.

---

## Interview Q&A

**Q: Does StaticFiles support byte-range requests (video seeking)?**
A: Yes — Starlette's `StaticFiles` handles `Range` headers automatically, so
`<video>` seeking works. Still not a CDN substitute for scale/latency.

**Q: How do you prevent path traversal via StaticFiles?**
A: `StaticFiles` itself normalizes and validates paths against the mounted
directory (raises 404 on traversal attempts) — the real risk is in your
*upload* endpoint if you build the save-path from unsanitized user input.

**Q: Why mount static files at `/static` instead of `/`?**
A: Mounting at `/` claims the entire path namespace for that `StaticFiles`
instance — fine for a pure SPA host, but conflicts with API routes if you're
serving both from one app. Namespace them (`/static`, `/uploads`) unless doing
the SPA-fallback pattern deliberately.

---

Related: [24_health_checks_k8s.md](24_health_checks_k8s.md) (health-check
endpoints sometimes serve a tiny static status page), rate limiting in
[41_fastapi_rate_limiting.md](41_fastapi_rate_limiting.md) (apply it to
`/upload` too — unrestricted uploads are a resource-exhaustion vector).
