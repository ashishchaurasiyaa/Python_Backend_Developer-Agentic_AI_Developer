# DRF Content Negotiation

## Why It Matters

Every DRF request goes through content negotiation twice — once for the request body
(parsing) and once for the response body (rendering) — even if you never touch it.
Most shops only ever serve JSON, so this stays invisible. It becomes an interview
question the moment an API must serve **multiple formats** (JSON + XML + CSV) or
support the **browsable API** in dev while forcing JSON in prod.

Senior interview: "How does DRF decide whether to return JSON, the browsable HTML
API, or something else?" → content negotiation, driven by the `Accept` header.

---

## Core Concept: What Negotiation Actually Does

```
Client sends:  Accept: application/json
                    ↓
DRF's negotiation class picks a matching Renderer from your
`DEFAULT_RENDERER_CLASSES` (or the view's `renderer_classes`)
                    ↓
That renderer serializes the response body
```

The same happens in reverse for **incoming** data via `Parser` classes, driven by
the request's `Content-Type` header — not `Accept`.

| Header | Direction | Picks |
|---|---|---|
| `Accept` | Response (what client wants back) | **Renderer** |
| `Content-Type` | Request (what client sent) | **Parser** |

---

## Renderers — controlling the response format

```python
# settings.py
REST_FRAMEWORK = {
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
        "rest_framework.renderers.BrowsableAPIRenderer",  # remove in prod
    ],
}
```

```python
# Per-view override — force JSON-only, no browsable API
from rest_framework.renderers import JSONRenderer
from rest_framework.views import APIView

class OrderView(APIView):
    renderer_classes = [JSONRenderer]
```

**Production pattern:** keep `BrowsableAPIRenderer` in `DEFAULT_RENDERER_CLASSES` for
local dev convenience, but strip it via `settings` override in the prod settings
module (`DEBUG=False` branch) — browsable API leaks schema info and is slower to render.

```python
# settings/production.py
REST_FRAMEWORK["DEFAULT_RENDERER_CLASSES"] = [
    "rest_framework.renderers.JSONRenderer",
]
```

### Custom renderer (e.g., CSV export)

```python
from rest_framework.renderers import BaseRenderer
import csv, io

class CSVRenderer(BaseRenderer):
    media_type = "text/csv"
    format = "csv"

    def render(self, data, accepted_media_type=None, renderer_context=None):
        buf = io.StringIO()
        writer = csv.DictWriter(buf, fieldnames=data[0].keys() if data else [])
        writer.writeheader()
        writer.writerows(data)
        return buf.getvalue()
```

Client requests it with `Accept: text/csv` or the URL-suffix shortcut `?format=csv`
(enabled automatically when `URL_FORMAT_SUFFIX` negotiation is on, DRF's default).

---

## Parsers — controlling accepted request formats

```python
REST_FRAMEWORK = {
    "DEFAULT_PARSER_CLASSES": [
        "rest_framework.parsers.JSONParser",
        "rest_framework.parsers.MultiPartParser",   # file uploads
        "rest_framework.parsers.FormParser",
    ],
}
```

If a client sends `Content-Type: application/xml` and you haven't registered an XML
parser, DRF returns **415 Unsupported Media Type** automatically — this is the
negotiation failure path, worth knowing for debugging weird client integration bugs.

---

## The Negotiation Class Itself

DRF's default is `DefaultContentNegotiation`, which:
1. Reads `Accept` header, splits on `,` for multiple accepted types with `q=` weights
2. Walks your `renderer_classes` in order, matches the first one whose `media_type`
   satisfies the `Accept` header
3. Falls back to the **first renderer in the list** if `Accept: */*` or no header

```python
# Custom negotiation — e.g., force format via query param only, ignore Accept header
from rest_framework.negotiation import BaseContentNegotiation

class IgnoreClientContentNegotiation(BaseContentNegotiation):
    def select_parser(self, request, parsers):
        return parsers[0]

    def select_renderer(self, request, renderers, format_suffix):
        return renderers[0], renderers[0].media_type
```

Set via `DEFAULT_CONTENT_NEGOTIATION_CLASS` in settings, or per-view
`content_negotiation_class`.

---

## Interview Q&A

**Q: What's the difference between content negotiation and API versioning?**
A: Versioning picks *which representation* of a resource (v1 vs v2 shape);
negotiation picks *which format* to serialize the chosen representation in
(JSON vs XML). They're orthogonal — DRF supports combining both
(`Accept: application/json; version=2.0` is a real pattern via `AcceptHeaderVersioning`).

**Q: Why disable BrowsableAPIRenderer in production?**
A: It renders full HTML forms reflecting your serializer schema — useful in dev,
but it's extra render cost per request and can expose internal field structure
to anyone poking the API with a browser instead of a JSON client.

**Q: Client gets 415 error — what does that mean?**
A: They sent a `Content-Type` your `DEFAULT_PARSER_CLASSES` doesn't include a
parser for. Fix: either add the parser, or tell the client to send JSON.

---

Related: [26_drf_api_versioning.md](26_drf_api_versioning.md) (orthogonal concern —
version selection vs format selection), [28_drf_exception_handler.md](28_drf_exception_handler.md)
(the 415/406 error responses this produces flow through your custom exception handler).
