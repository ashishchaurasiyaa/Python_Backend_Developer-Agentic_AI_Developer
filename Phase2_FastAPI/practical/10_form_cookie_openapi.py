"""
PHASE 2 FastAPI — Practical 10: Form Data + Cookie Auth + OpenAPI Customization
Run: uvicorn 10_form_cookie_openapi:app --reload
Docs: http://127.0.0.1:8000/docs

Topics:
  - Form() — HTML form data handling
  - File + Form together (multipart)
  - Cookie-based authentication (HttpOnly JWT)
  - Response.set_cookie / delete_cookie
  - OpenAPI customization — tags metadata, examples, operation IDs
  - include_in_schema=False — hide routes from docs
  - Custom OpenAPI schema (add security schemes)
"""

from __future__ import annotations

import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from typing import Annotated, Optional

from fastapi import (
    APIRouter,
    Cookie,
    Depends,
    FastAPI,
    File,
    Form,
    HTTPException,
    Request,
    Response,
    UploadFile,
    status,
)
from fastapi.openapi.utils import get_openapi
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.security import HTTPBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel, EmailStr, Field


# ═══════════════════════════════════════════════════════
# SECTION 1: Config
# ═══════════════════════════════════════════════════════

SECRET_KEY = "cookie-secret-key-for-learning"
ALGORITHM  = "HS256"
ACCESS_EXPIRE_MINUTES = 60

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

USERS_DB: dict[str, dict] = {
    "alice@example.com": {
        "id": 1, "name": "Alice", "email": "alice@example.com",
        "hashed_password": pwd_context.hash("Password1"),
        "role": "admin",
    },
}


# ═══════════════════════════════════════════════════════
# SECTION 2: Form Data Handling
# ═══════════════════════════════════════════════════════

form_router = APIRouter(prefix="/forms", tags=["Form Data"])


# ─── Simple form ───
@form_router.post("/login", summary="Login with HTML form data")
async def form_login(
    username: str = Form(..., description="Email address"),
    password: str = Form(..., min_length=6),
    remember_me: bool = Form(default=False),
):
    """
    Handles: Content-Type: application/x-www-form-urlencoded
    HTML <form> sends this format by default.
    """
    return {
        "username": username,
        "remember_me": remember_me,
        "message": f"Form login attempt for {username}",
    }


# ─── Form with validation ───
class ProductFormData(BaseModel):
    """Used to document form fields."""
    name: str
    price: float
    category: str
    description: Optional[str] = None


@form_router.post("/products", status_code=201, summary="Create product with form")
async def create_product_form(
    name: str        = Form(..., min_length=2, max_length=100),
    price: float     = Form(..., gt=0),
    category: str    = Form(...),
    description: str = Form(default=""),
    quantity: int    = Form(default=0, ge=0),
):
    """
    Pure form data — no JSON body.
    Test with: curl -X POST -F "name=Laptop" -F "price=75000" -F "category=electronics"
    """
    product_id = str(uuid.uuid4())[:8]
    return {
        "id": product_id,
        "name": name,
        "price": price,
        "category": category,
        "description": description,
        "quantity": quantity,
    }


# ─── File + Form together (multipart/form-data) ───
@form_router.post("/products/with-image", status_code=201, summary="Product with image upload")
async def create_product_with_image(
    name:        str        = Form(...),
    price:       float      = Form(..., gt=0),
    category:    str        = Form(...),
    image:       UploadFile = File(..., description="Product image"),
    thumbnail:   Optional[UploadFile] = File(None, description="Optional thumbnail"),
):
    """
    Multipart form: text fields + file together.
    Content-Type: multipart/form-data (browser sets this for <form enctype="multipart/form-data">)

    curl example:
    curl -X POST \\
      -F "name=Laptop" \\
      -F "price=75000" \\
      -F "category=electronics" \\
      -F "image=@/path/to/image.jpg" \\
      http://localhost:8000/forms/products/with-image
    """
    image_content = await image.read()

    result = {
        "name": name,
        "price": price,
        "category": category,
        "image": {
            "filename": image.filename,
            "content_type": image.content_type,
            "size_bytes": len(image_content),
        },
    }

    if thumbnail:
        thumb_content = await thumbnail.read()
        result["thumbnail"] = {
            "filename": thumbnail.filename,
            "size_bytes": len(thumb_content),
        }

    return result


# ─── Multiple files + form ───
@form_router.post("/documents/bulk", summary="Upload multiple docs with metadata")
async def upload_documents_with_meta(
    project_name: str              = Form(...),
    tags:         str              = Form(default="", description="Comma-separated tags"),
    files:        list[UploadFile] = File(...),
):
    """Upload multiple files with form metadata."""
    tag_list = [t.strip() for t in tags.split(",") if t.strip()]
    results  = []

    for f in files:
        content = await f.read()
        results.append({
            "filename": f.filename,
            "size_bytes": len(content),
            "content_type": f.content_type,
        })

    return {
        "project": project_name,
        "tags": tag_list,
        "files": results,
        "total_files": len(results),
    }


# ─── Form test page ───
@form_router.get("/test-page", response_class=HTMLResponse, include_in_schema=False)
async def form_test_page():
    return HTMLResponse("""
    <!DOCTYPE html><html><body>
    <h2>Form Data Test</h2>

    <h3>Login Form</h3>
    <form action="/forms/login" method="post">
        <input name="username" placeholder="Email" value="alice@example.com"><br>
        <input name="password" type="password" placeholder="Password" value="Password1"><br>
        <label><input name="remember_me" type="checkbox" value="true"> Remember me</label><br>
        <button type="submit">Login</button>
    </form>

    <h3>File + Form Upload</h3>
    <form action="/forms/products/with-image" method="post" enctype="multipart/form-data">
        <input name="name" placeholder="Product name" value="Test Laptop"><br>
        <input name="price" placeholder="Price" value="75000"><br>
        <input name="category" placeholder="Category" value="electronics"><br>
        <input name="image" type="file"><br>
        <button type="submit">Upload Product</button>
    </form>
    </body></html>
    """)


# ═══════════════════════════════════════════════════════
# SECTION 3: Cookie Authentication
# ═══════════════════════════════════════════════════════

cookie_router = APIRouter(prefix="/cookie-auth", tags=["Cookie Auth"])

COOKIE_NAME = "access_token"


def create_token(user_id: int, email: str, role: str) -> str:
    payload = {
        "sub": str(user_id),
        "email": email,
        "role": role,
        "exp": datetime.now(timezone.utc) + timedelta(minutes=ACCESS_EXPIRE_MINUTES),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


async def get_current_user_from_cookie(
    access_token: Optional[str] = Cookie(None, alias=COOKIE_NAME),
) -> dict:
    """Read JWT from HttpOnly cookie instead of Authorization header."""
    if not access_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated — please login",
        )
    try:
        payload = jwt.decode(access_token, SECRET_KEY, algorithms=[ALGORITHM])
        return {
            "user_id": int(payload["sub"]),
            "email": payload["email"],
            "role": payload["role"],
        }
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired session")


CookieUser = Annotated[dict, Depends(get_current_user_from_cookie)]


# ─── Login: set cookie ───
@cookie_router.post("/login")
async def cookie_login(
    response: Response,
    username: str = Form(...),
    password: str = Form(...),
):
    """
    Login with form data → sets HttpOnly cookie.
    HttpOnly = JS cannot read it (XSS protection).
    Secure  = only sent over HTTPS.
    SameSite = CSRF protection.
    """
    user = USERS_DB.get(username)
    if not user or not pwd_context.verify(password, user["hashed_password"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = create_token(user["id"], user["email"], user["role"])

    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        httponly=True,                              # JS cannot access (XSS safe)
        secure=False,                               # True in production (HTTPS only)
        samesite="lax",                             # CSRF protection
        max_age=ACCESS_EXPIRE_MINUTES * 60,         # seconds
        path="/",
    )

    return {"message": f"Logged in as {user['name']}. Cookie set."}


# ─── Protected route using cookie ───
@cookie_router.get("/me")
async def cookie_me(current_user: CookieUser):
    return {"message": "Authenticated via cookie", "user": current_user}


@cookie_router.get("/dashboard")
async def cookie_dashboard(current_user: CookieUser):
    return {
        "dashboard": "Welcome!",
        "user_id": current_user["user_id"],
        "role": current_user["role"],
    }


# ─── Logout: delete cookie ───
@cookie_router.post("/logout")
async def cookie_logout(response: Response):
    response.delete_cookie(
        key=COOKIE_NAME,
        path="/",
        samesite="lax",
    )
    return {"message": "Logged out. Cookie cleared."}


# ─── Refresh cookie ───
@cookie_router.post("/refresh")
async def cookie_refresh(
    response: Response,
    current_user: CookieUser,
):
    """Issue a fresh cookie for active sessions."""
    user = next((u for u in USERS_DB.values() if u["id"] == current_user["user_id"]), None)
    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    new_token = create_token(user["id"], user["email"], user["role"])
    response.set_cookie(
        key=COOKIE_NAME, value=new_token,
        httponly=True, secure=False, samesite="lax",
        max_age=ACCESS_EXPIRE_MINUTES * 60,
    )
    return {"message": "Session refreshed"}


# ─── Cookie test page ───
@cookie_router.get("/test-page", response_class=HTMLResponse, include_in_schema=False)
async def cookie_test_page():
    return HTMLResponse("""
    <!DOCTYPE html><html><body>
    <h2>Cookie Auth Test</h2>
    <p>Login sets HttpOnly cookie — inspect DevTools > Application > Cookies</p>

    <h3>Login</h3>
    <form action="/cookie-auth/login" method="post">
        <input name="username" value="alice@example.com"><br>
        <input name="password" type="password" value="Password1"><br>
        <button type="submit">Login (sets cookie)</button>
    </form>

    <h3>Access Protected</h3>
    <button onclick="fetch('/cookie-auth/me',{credentials:'include'}).then(r=>r.json()).then(d=>alert(JSON.stringify(d)))">
        GET /me (uses cookie automatically)
    </button>

    <h3>Logout</h3>
    <button onclick="fetch('/cookie-auth/logout',{method:'POST',credentials:'include'}).then(()=>alert('Logged out'))">
        Logout (clears cookie)
    </button>
    </body></html>
    """)


# ═══════════════════════════════════════════════════════
# SECTION 4: OpenAPI Customization
# ═══════════════════════════════════════════════════════

openapi_router = APIRouter(tags=["OpenAPI Examples"])

# ─── Custom tags metadata ───
tags_metadata = [
    {
        "name": "Form Data",
        "description": "HTML form data handling — `application/x-www-form-urlencoded` and `multipart/form-data`",
        "externalDocs": {
            "description": "HTML Forms MDN",
            "url": "https://developer.mozilla.org/en-US/docs/Web/HTML/Element/form",
        },
    },
    {
        "name": "Cookie Auth",
        "description": "HttpOnly cookie-based JWT authentication — browser-friendly, XSS-safe",
    },
    {
        "name": "OpenAPI Examples",
        "description": "Custom OpenAPI schema features — examples, operation IDs, hidden routes",
    },
]


# ─── Custom response examples ───
class ItemCreate(BaseModel):
    name:     str   = Field(..., examples=["Gaming Laptop"])
    price:    float = Field(..., examples=[89999.0])
    category: str   = Field(..., examples=["electronics"])
    in_stock: bool  = Field(default=True)


@openapi_router.post(
    "/items",
    operation_id="create_item_v1",       # custom operation ID (used in generated client code)
    summary="Create a new item",
    description="""
Create a new catalog item.

**Rules:**
- `name` must be 2-100 characters
- `price` must be positive
- `category` must be one of: electronics, clothing, books, home
    """,
    response_description="The created item with generated ID",
    responses={
        201: {
            "description": "Item created",
            "content": {
                "application/json": {
                    "example": {
                        "id": "abc123",
                        "name": "Gaming Laptop",
                        "price": 89999.0,
                        "category": "electronics",
                        "in_stock": True,
                    }
                }
            },
        },
        400: {"description": "Invalid category"},
        409: {"description": "Item already exists"},
    },
    status_code=201,
)
async def create_item(body: ItemCreate):
    VALID_CATEGORIES = {"electronics", "clothing", "books", "home"}
    if body.category not in VALID_CATEGORIES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid category. Must be one of: {VALID_CATEGORIES}",
        )
    return {"id": str(uuid.uuid4())[:8], **body.model_dump()}


# ─── include_in_schema=False — hide from Swagger ───
@openapi_router.get(
    "/internal/cache-clear",
    include_in_schema=False,   # invisible in /docs and /openapi.json
)
async def internal_cache_clear(secret: str):
    """Internal endpoint — not shown in Swagger docs."""
    if secret != "super-secret":
        raise HTTPException(status_code=403, detail="Forbidden")
    return {"cache": "cleared"}


# ─── Deprecated route ───
@openapi_router.get(
    "/items/legacy",
    deprecated=True,               # shows strikethrough in Swagger
    summary="[DEPRECATED] Old items list",
    description="Use GET /v2/items instead. Will be removed in v3.",
    include_in_schema=True,
)
async def legacy_items():
    return {"items": [], "warning": "This endpoint is deprecated. Use /v2/items"}


# ═══════════════════════════════════════════════════════
# SECTION 5: App Setup
# ═══════════════════════════════════════════════════════

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("🚀 Form + Cookie + OpenAPI app starting...")
    yield
    print("🛑 Shutting down...")


app = FastAPI(
    title="FastAPI — Form, Cookie, OpenAPI",
    description="""
## Complete Guide

### Form Data
- `application/x-www-form-urlencoded` — simple HTML forms
- `multipart/form-data` — files + form fields together

### Cookie Auth
- HttpOnly cookie → XSS safe (JS can't read)
- Secure flag → HTTPS only
- SameSite=lax → CSRF protection

### OpenAPI
- Custom tag descriptions with external docs
- Per-route examples, operation IDs
- Hide internal routes with `include_in_schema=False`
    """,
    version="1.0.0",
    openapi_tags=tags_metadata,
    lifespan=lifespan,
)

app.include_router(form_router)
app.include_router(cookie_router)
app.include_router(openapi_router)


# ─── Custom OpenAPI schema modification ───
def custom_openapi():
    """Add cookie security scheme to OpenAPI spec."""
    if app.openapi_schema:
        return app.openapi_schema

    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
        tags=tags_metadata,
    )

    # Add cookie security scheme
    openapi_schema["components"]["securitySchemes"] = {
        "cookieAuth": {
            "type": "apiKey",
            "in": "cookie",
            "name": COOKIE_NAME,
            "description": "HttpOnly JWT cookie set by /cookie-auth/login",
        },
        "bearerAuth": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
        },
    }

    app.openapi_schema = openapi_schema
    return app.openapi_schema


app.openapi = custom_openapi  # type: ignore


@app.get("/", tags=["Root"])
async def root():
    return {
        "message": "Form + Cookie + OpenAPI Practical",
        "test_pages": {
            "form_test":   "http://localhost:8000/forms/test-page",
            "cookie_test": "http://localhost:8000/cookie-auth/test-page",
            "swagger":     "http://localhost:8000/docs",
        },
        "test_credentials": "alice@example.com / Password1",
    }


# ═══════════════════════════════════════════════════════
# SECTION 6: Interview Q&A
# ═══════════════════════════════════════════════════════

"""
Q1: Form() aur Body() mein kya fark hai?
    Body() = JSON (Content-Type: application/json)
    Form() = HTML form (Content-Type: application/x-www-form-urlencoded)
    File() = multipart/form-data
    Ek route mein Form() + File() saath ho sakta hai.
    Ek route mein Form() + Body(JSON) NAHI ho sakta (HTTP limitation).

Q2: Cookie auth vs JWT bearer — kab kya use karo?
    Cookie (HttpOnly):
      - Browser-based apps (SPA, SSR)
      - XSS protection (JS nahi padh sakta)
      - CSRF risk → SameSite=lax se mitigate karo
    Bearer token:
      - Mobile apps, API clients, service-to-service
      - Client storage mein store karta hai
      - CSRF risk nahi, XSS risk hai

Q3: Cookie security settings kya hain?
    httponly=True  → JS access block (XSS protection)
    secure=True    → HTTPS only (production mein must)
    samesite="lax" → Cross-site CSRF protection
    max_age        → Expiry in seconds
    path="/"       → All routes pe valid

Q4: include_in_schema=False kab use karte hain?
    Internal routes (health check, cache clear, admin tools)
    jo public API documentation mein nahi dikhane
    Phir bhi accessible hote hain — just hidden from Swagger

Q5: Custom OpenAPI schema kaise add karte hain?
    app.openapi = custom_openapi_function
    us function mein get_openapi() call karo
    Phir openapi_schema["components"]["securitySchemes"] modify karo.

Q6: Operation ID kya hai?
    OpenAPI spec mein har route ka unique identifier.
    Auto-generated client SDKs mein function name banta hai.
    Custom rakhna better: operation_id="create_user_v2"
"""


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("10_form_cookie_openapi:app", host="0.0.0.0", port=8009, reload=True)
