"""
PHASE 2 FastAPI — Practical 01: Routing, Params, Request Body, File Upload, Lifespan
Run: uvicorn 01_routing_params:app --reload
Docs: http://127.0.0.1:8000/docs
"""

from __future__ import annotations

import io
import os
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated, Optional

import aiofiles
from fastapi import (
    APIRouter,
    Body,
    FastAPI,
    File,
    Path as FPath,
    Query,
    Request,
    Response,
    UploadFile,
    status,
)
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, EmailStr, Field, model_validator


# ═══════════════════════════════════════════════════════
# SECTION 1: Pydantic Models
# ═══════════════════════════════════════════════════════

class Address(BaseModel):
    street: str
    city: str
    pincode: str
    country: str = "India"


class UserCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=100, examples=["Alice"])
    email: EmailStr
    age: int = Field(..., ge=1, le=120)
    address: Optional[Address] = None


class UserUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=100)
    age: Optional[int] = Field(None, ge=1, le=120)

    @model_validator(mode="after")
    def at_least_one_field(self) -> UserUpdate:
        if self.name is None and self.age is None:
            raise ValueError("At least one field required for update")
        return self


class UserResponse(BaseModel):
    id: str
    name: str
    email: str
    age: int

    model_config = {"from_attributes": True}


class ItemCreate(BaseModel):
    name: str
    price: float = Field(..., gt=0)
    quantity: int = Field(1, ge=0)
    tags: list[str] = []


# ─── In-memory store (simulating DB) ───
USERS: dict[str, dict] = {}
ITEMS: dict[str, dict] = {}
UPLOAD_DIR = Path("uploads")


# ═══════════════════════════════════════════════════════
# SECTION 2: Lifespan — startup / shutdown
# ═══════════════════════════════════════════════════════

@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── STARTUP ──
    print("🚀 App starting...")
    UPLOAD_DIR.mkdir(exist_ok=True)

    # Seed some data
    uid = str(uuid.uuid4())
    USERS[uid] = {"id": uid, "name": "Alice", "email": "alice@example.com", "age": 28}

    iid = str(uuid.uuid4())
    ITEMS[iid] = {"id": iid, "name": "Laptop", "price": 75000.0, "quantity": 10, "tags": ["electronics"]}

    app.state.start_time = time.time()
    print(f"✅ Startup done. {len(USERS)} users, {len(ITEMS)} items seeded.")

    yield  # App runs here

    # ── SHUTDOWN ──
    print("🛑 App shutting down...")
    # Close DB, Redis, etc. here


app = FastAPI(
    title="FastAPI Routing Practical",
    description="Phase 2 — Routing, Params, Request Body, File Upload",
    version="1.0.0",
    lifespan=lifespan,
)


# ═══════════════════════════════════════════════════════
# SECTION 3: Basic Routes — GET / POST / PUT / DELETE
# ═══════════════════════════════════════════════════════

user_router = APIRouter(prefix="/users", tags=["Users"])
item_router = APIRouter(prefix="/items", tags=["Items"])


# ─── GET with path + query params ───
@user_router.get("", summary="List users with pagination")
async def list_users(
    skip: int = Query(0, ge=0, description="Records to skip"),
    limit: int = Query(10, ge=1, le=100, description="Max records to return"),
    search: Optional[str] = Query(None, min_length=2, description="Search by name"),
    sort_by: str = Query("name", pattern="^(name|email|age)$"),
):
    users = list(USERS.values())

    if search:
        users = [u for u in users if search.lower() in u["name"].lower()]

    if sort_by in ("name", "email", "age"):
        users.sort(key=lambda u: u[sort_by])

    return {
        "total": len(users),
        "skip": skip,
        "limit": limit,
        "data": users[skip: skip + limit],
    }


@user_router.get(
    "/{user_id}",
    response_model=UserResponse,
    summary="Get user by ID",
    responses={404: {"description": "User not found"}},
)
async def get_user(
    user_id: str = FPath(..., description="User UUID"),
):
    user = USERS.get(user_id)
    if not user:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=f"User '{user_id}' not found")
    return user


# ─── POST — create with request body ───
@user_router.post(
    "",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create new user",
)
async def create_user(user: UserCreate):
    uid = str(uuid.uuid4())
    new_user = {"id": uid, **user.model_dump(exclude={"address"})}
    USERS[uid] = new_user
    return new_user


# ─── PUT — full update ───
@user_router.put("/{user_id}", response_model=UserResponse)
async def update_user(user_id: str, user: UserCreate):
    from fastapi import HTTPException
    if user_id not in USERS:
        raise HTTPException(status_code=404, detail="User not found")
    USERS[user_id] = {"id": user_id, **user.model_dump(exclude={"address"})}
    return USERS[user_id]


# ─── PATCH — partial update ───
@user_router.patch("/{user_id}", response_model=UserResponse)
async def partial_update_user(user_id: str, update: UserUpdate):
    from fastapi import HTTPException
    if user_id not in USERS:
        raise HTTPException(status_code=404, detail="User not found")
    user = USERS[user_id]
    patch_data = update.model_dump(exclude_none=True)
    user.update(patch_data)
    return user


# ─── DELETE ───
@user_router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(user_id: str):
    from fastapi import HTTPException
    if user_id not in USERS:
        raise HTTPException(status_code=404, detail="User not found")
    del USERS[user_id]


# ═══════════════════════════════════════════════════════
# SECTION 4: Query Param Patterns
# ═══════════════════════════════════════════════════════

@item_router.get("", summary="Filter items — multi-value query params")
async def list_items(
    tags: list[str] = Query(default=[], description="Filter by tags (repeat param)"),
    min_price: Optional[float] = Query(None, ge=0),
    max_price: Optional[float] = Query(None, ge=0),
    in_stock: bool = Query(True),
):
    """
    Multi-value query param: /items?tags=electronics&tags=sale
    """
    items = list(ITEMS.values())

    if tags:
        items = [i for i in items if any(t in i["tags"] for t in tags)]
    if min_price is not None:
        items = [i for i in items if i["price"] >= min_price]
    if max_price is not None:
        items = [i for i in items if i["price"] <= max_price]
    if in_stock:
        items = [i for i in items if i["quantity"] > 0]

    return {"count": len(items), "data": items}


@item_router.post("", status_code=201)
async def create_item(item: ItemCreate):
    iid = str(uuid.uuid4())
    new_item = {"id": iid, **item.model_dump()}
    ITEMS[iid] = new_item
    return new_item


# ─── Path + Query + Body together ───
@item_router.put("/{item_id}")
async def update_item_price(
    item_id: str = FPath(...),
    notify: bool = Query(False, description="Send price change notification"),
    update: Annotated[dict, Body(examples=[{"price": 999.0}])] = ...,
):
    from fastapi import HTTPException
    if item_id not in ITEMS:
        raise HTTPException(status_code=404, detail="Item not found")
    ITEMS[item_id]["price"] = update.get("price", ITEMS[item_id]["price"])
    return {"item": ITEMS[item_id], "notified": notify}


# ═══════════════════════════════════════════════════════
# SECTION 5: File Upload + Download
# ═══════════════════════════════════════════════════════

file_router = APIRouter(prefix="/files", tags=["Files"])

ALLOWED_TYPES = {"image/jpeg", "image/png", "application/pdf", "text/csv"}
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5 MB


@file_router.post("/upload", status_code=201)
async def upload_file(file: UploadFile = File(...)):
    """Upload single file — validates type and size."""
    from fastapi import HTTPException

    # Validate content type
    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported type: {file.content_type}. Allowed: {ALLOWED_TYPES}"
        )

    # Read and check size
    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail=f"File too large. Max: {MAX_FILE_SIZE // 1024}KB")

    # Save to disk
    safe_name = f"{uuid.uuid4().hex}_{file.filename}"
    file_path = UPLOAD_DIR / safe_name

    async with aiofiles.open(file_path, "wb") as f:
        await f.write(content)

    return {
        "filename": file.filename,
        "saved_as": safe_name,
        "size_bytes": len(content),
        "content_type": file.content_type,
    }


@file_router.post("/upload-multiple", status_code=201)
async def upload_multiple(files: list[UploadFile] = File(...)):
    """Upload multiple files."""
    results = []
    for file in files:
        content = await file.read()
        safe_name = f"{uuid.uuid4().hex}_{file.filename}"
        async with aiofiles.open(UPLOAD_DIR / safe_name, "wb") as f:
            await f.write(content)
        results.append({"original": file.filename, "saved": safe_name, "bytes": len(content)})
    return {"uploaded": len(results), "files": results}


@file_router.get("/download/{filename}")
async def download_file(filename: str):
    """Download a previously uploaded file."""
    from fastapi import HTTPException

    # Security: prevent path traversal
    file_path = UPLOAD_DIR / Path(filename).name
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")

    return FileResponse(
        path=str(file_path),
        filename=filename,
        media_type="application/octet-stream",
    )


@file_router.get("/stream/{filename}")
async def stream_large_file(filename: str):
    """Stream large file in 1MB chunks — memory efficient."""
    from fastapi import HTTPException

    file_path = UPLOAD_DIR / Path(filename).name
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")

    CHUNK = 1024 * 1024  # 1 MB

    async def chunks():
        async with aiofiles.open(file_path, "rb") as f:
            while data := await f.read(CHUNK):
                yield data

    return StreamingResponse(
        chunks(),
        media_type="application/octet-stream",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


# ═══════════════════════════════════════════════════════
# SECTION 6: Response Customization
# ═══════════════════════════════════════════════════════

meta_router = APIRouter(prefix="/meta", tags=["Meta"])


@meta_router.get("/info")
async def app_info(request: Request):
    """App info including uptime."""
    uptime = time.time() - request.app.state.start_time
    return {
        "app": "FastAPI Routing Practical",
        "uptime_seconds": round(uptime, 2),
        "users_count": len(USERS),
        "items_count": len(ITEMS),
    }


@meta_router.get("/headers-demo")
async def headers_demo(response: Response, request: Request):
    """Custom response headers."""
    response.headers["X-Custom-Header"] = "hello-from-fastapi"
    response.headers["X-Request-ID"] = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    return {"message": "Check response headers in browser/curl"}


@meta_router.get("/redirect")
async def redirect_example():
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/docs", status_code=302)


# ─── Register all routers ───
app.include_router(user_router)
app.include_router(item_router)
app.include_router(file_router)
app.include_router(meta_router)


@app.get("/", tags=["Root"])
async def root():
    return {"message": "FastAPI Routing Practical — visit /docs"}


# ═══════════════════════════════════════════════════════
# RUN
# ═══════════════════════════════════════════════════════

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("01_routing_params:app", host="0.0.0.0", port=8000, reload=True)
