# FastAPI — Forms, Cookies, File Upload & OpenAPI Customization

## Quick Concepts
- **`Form()`** = HTML form data (`Content-Type: multipart/form-data`)
- **`File()`** = binary file upload
- **`UploadFile`** = streaming file upload — memory-efficient
- **`Cookie()`** = HTTP cookie read/write
- **`response.set_cookie()`** = HttpOnly secure cookie set karo
- **Custom OpenAPI** = `app.openapi()` override — custom schema, security schemes
- **`include_in_schema=False`** = route OpenAPI docs se hide karo

---

## Interview Questions & Answers

### Q1: Form data aur file upload FastAPI mein kaise handle karte hain?

**Answer:**
```python
from fastapi import FastAPI, Form, File, UploadFile, HTTPException
from typing import Annotated
import aiofiles
import uuid

# ─── Simple Form ───
@app.post("/login")
async def login(
    email:    Annotated[str, Form()],
    password: Annotated[str, Form()],
):
    # Content-Type: application/x-www-form-urlencoded
    return {"email": email}

# ─── File Upload ───
@app.post("/upload")
async def upload_file(
    file: Annotated[UploadFile, File(description="Upload any file")],
):
    # Validate file type
    allowed_types = {"image/jpeg", "image/png", "application/pdf"}
    if file.content_type not in allowed_types:
        raise HTTPException(400, f"File type {file.content_type} not allowed")

    # Validate file size (read in chunks)
    max_size = 5 * 1024 * 1024  # 5 MB
    contents = await file.read()
    if len(contents) > max_size:
        raise HTTPException(413, "File too large. Max 5MB.")

    # Save to disk
    filename = f"{uuid.uuid4()}_{file.filename}"
    async with aiofiles.open(f"uploads/{filename}", "wb") as f:
        await f.write(contents)

    return {"filename": filename, "size": len(contents)}

# ─── File + Form Together ───
@app.post("/posts")
async def create_post(
    title:   Annotated[str, Form()],
    content: Annotated[str, Form()],
    cover:   Annotated[UploadFile | None, File()] = None,
):
    # multipart/form-data — text + binary together
    if cover:
        img_data = await cover.read()
        # save image...

    return {"title": title}

# INTERVIEW: UploadFile vs bytes?
# bytes: whole file memory mein load → small files only
# UploadFile: streaming — SpooledTemporaryFile → memory efficient
#   file.read()       → async read all
#   file.read(1024)   → read chunk
#   file.seek(0)      → rewind
```

---

### Q2: Cookie authentication FastAPI mein kaise karte hain?

**Answer:**
```python
from fastapi import Cookie, Response
from datetime import timedelta

# ─── Set Cookie (Login) ───
@app.post("/auth/login")
async def login(response: Response, email: str, password: str):
    user = authenticate(email, password)
    token = create_access_token({"sub": str(user.id)})

    response.set_cookie(
        key="access_token",
        value=f"Bearer {token}",
        max_age=1800,           # 30 minutes (seconds)
        httponly=True,           # JS se access nahi — XSS protection
        secure=True,             # HTTPS only (False for localhost dev)
        samesite="lax",          # CSRF protection
        path="/",
    )
    return {"message": "Login successful"}

# ─── Read Cookie ───
@app.get("/me")
async def get_me(access_token: Annotated[str | None, Cookie()] = None):
    if not access_token:
        raise HTTPException(401, "Not authenticated")

    token = access_token.removeprefix("Bearer ")
    payload = verify_token(token)
    return {"user_id": payload["sub"]}

# ─── Delete Cookie (Logout) ───
@app.post("/auth/logout")
async def logout(response: Response):
    response.delete_cookie("access_token")
    return {"message": "Logged out"}

# INTERVIEW: JWT in Cookie vs Authorization header?
# Cookie:
#   + Automatic sending — browser sends automatically
#   + HttpOnly — XSS se safe
#   - CSRF attack possible (mitigate: SameSite=Strict/Lax)
#   - Mobile apps ke liye awkward
# Authorization Header:
#   + CSRF nahi (browser auto-send nahi karta custom headers)
#   + Mobile/SPA friendly
#   - XSS se vulnerable (localStorage mein store karna risky)
```

---

### Q3: OpenAPI schema customize kaise karte hain?

**Answer:**
```python
from fastapi.openapi.utils import get_openapi
from fastapi.openapi.docs import get_swagger_ui_html, get_redoc_html
from fastapi import FastAPI

app = FastAPI(docs_url=None, redoc_url=None)  # disable default docs

# ─── Custom OpenAPI schema ───
def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema

    schema = get_openapi(
        title="My Production API",
        version="2.0.0",
        description="Complete API documentation",
        routes=app.routes,
        tags=[
            {"name": "auth",  "description": "Authentication endpoints"},
            {"name": "users", "description": "User management"},
            {"name": "blog",  "description": "Blog posts"},
        ],
    )

    # Add security schemes
    schema["components"]["securitySchemes"] = {
        "BearerAuth": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
        },
        "CookieAuth": {
            "type": "apiKey",
            "in": "cookie",
            "name": "access_token",
        },
    }

    # Apply security globally
    schema["security"] = [{"BearerAuth": []}]

    app.openapi_schema = schema
    return app.openapi_schema

app.openapi = custom_openapi

# ─── Custom Swagger UI ───
@app.get("/docs", include_in_schema=False)
async def swagger_ui():
    return get_swagger_ui_html(
        openapi_url="/openapi.json",
        title="My API Docs",
        swagger_ui_parameters={
            "deepLinking": True,
            "persistAuthorization": True,  # token save karo page reload pe
            "displayRequestDuration": True,
        },
    )

@app.get("/redoc", include_in_schema=False)
async def redoc_ui():
    return get_redoc_html(openapi_url="/openapi.json", title="My API — ReDoc")

# ─── Route-level OpenAPI customization ───
@app.get(
    "/users/{id}",
    summary="Get user by ID",
    description="Retrieve a single user with full profile.\n\n**Note:** Admin only.",
    response_description="User object with profile",
    operation_id="get_user_by_id",     # unique ID for code generation
    deprecated=False,
    tags=["users"],
    responses={
        404: {"description": "User not found"},
        403: {"description": "Insufficient permissions"},
    },
)
async def get_user(id: int): ...

# ─── Hide internal routes ───
@app.get("/internal/health", include_in_schema=False)
async def internal_health(): return {"ok": True}
```

---

### Q4: File download — streaming response kaise karte hain?

**Answer:**
```python
from fastapi.responses import FileResponse, StreamingResponse
import aiofiles

# ─── Small file — FileResponse ───
@app.get("/files/{filename}")
async def download_file(filename: str):
    file_path = f"uploads/{filename}"
    return FileResponse(
        path=file_path,
        filename=filename,          # Content-Disposition header
        media_type="application/octet-stream",
    )

# ─── Large file — StreamingResponse (memory efficient) ───
@app.get("/export/large-csv")
async def export_large_csv():
    async def generate_rows():
        yield "id,name,email\n"  # header
        async for user in stream_users_from_db():
            yield f"{user.id},{user.name},{user.email}\n"

    return StreamingResponse(
        generate_rows(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=users.csv"},
    )

# INTERVIEW: FileResponse vs StreamingResponse?
# FileResponse:   file disk pe hai — path dedo, FastAPI serve karega
# StreamingResponse: data dynamically generate karo (DB query, LLM tokens)
#                    memory efficient for large responses
```

---

## Summary Table

| Feature | FastAPI | Code |
|---------|---------|------|
| Form field | `Form()` | `email: Annotated[str, Form()]` |
| File upload | `File()` + `UploadFile` | `file: Annotated[UploadFile, File()]` |
| Cookie read | `Cookie()` | `token: Annotated[str, Cookie()] = None` |
| Cookie write | `response.set_cookie()` | httponly=True, secure=True, samesite="lax" |
| Hide route | `include_in_schema=False` | `@app.get("/internal", include_in_schema=False)` |
| Mark deprecated | `deprecated=True` | `@app.get("/v1/old", deprecated=True)` |
| Custom OpenAPI | override `app.openapi` | add securitySchemes, tags |
