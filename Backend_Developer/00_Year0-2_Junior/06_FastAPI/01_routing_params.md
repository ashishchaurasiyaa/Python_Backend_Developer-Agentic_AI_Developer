# FastAPI — Routing, Path/Query Params, Request Body

## Quick Concepts
- **Path params** = URL ka part `{item_id}` — required hote hain
- **Query params** = URL ke baad `?skip=0&limit=10` — optional ho sakte hain
- **Request body** = Pydantic model se automatic validation
- **Response model** = output schema define karo — extra fields strip ho jaate hain
- **Status codes** = `status_code=201` create ke liye

---

## Andar kya hota hai — Route Matching + Param Resolution

### Routes ek ORDERED LIST hain, hash-map/trie nahi

```python
@app.get("/users/{user_id}")
def get_user(user_id: int): ...

@app.get("/users/me")
def get_current_user(): ...
```

Startup pe FastAPI (Starlette ke through) har route ko ek COMPILED REGEX bana ke ek
**list** mein rakhta hai, registration order mein. Har incoming request path ko is
list ke against **top se neeche, ek-ek karke** try kiya jaata hai — **PEHLA match
jeetta hai**, best-match ya most-specific-match nahi.

```
GET /users/me  aaya:
  1. /users/{user_id} ke regex se match? HAAN — {user_id} = "me" (string, koi type
     check abhi nahi hui, path param abhi sirf STRING extract hui)
     → yehi route CHOSEN, /users/me wala route kabhi try hi nahi hoga
  2. get_current_user() KABHI CALL NAHI HOGA jab tak /users/{user_id} PEHLE
     registered na ho
```

**Fix:** specific routes (`/users/me`) generic/parameterized routes
(`/users/{user_id}`) se PEHLE register karo. Ye ek real production bug pattern hai,
interview me directly poocha jaata hai.

### Param extraction + validation — tumhare function call hone SE PEHLE

```
1. Route match ho gaya → regex se named groups nikalte hain (path params, as strings)
2. Function signature ke type hints padhte hain (`user_id: int`)
3. Pydantic se COERCE + VALIDATE karte hain (string "42" → int 42; "abc" → 422 error)
4. Query params bhi isi step mein: URL ke `?skip=0` ko signature ke against validate
5. Body params: request body ko declared Pydantic model se parse+validate
6. SAB validate hone ke BAAD hi tumhara function actually call hota hai
```

Yehi wajah hai galat type wale request ko tumhara function BODY kabhi dekhta hi
nahi — validation FastAPI ke andar, function call se pehle hi fail ho jaati hai
(422 response, tumhara code touch nahi hota).

---

## Interview Questions & Answers

### Q1: FastAPI mein routing kaise kaam karta hai? Path aur Query params ka fark?
**Answer:**
```python
from fastapi import FastAPI, Path, Query, Body
from pydantic import BaseModel
from typing import Optional

app = FastAPI()

# Path param — URL mein required
@app.get("/users/{user_id}")
async def get_user(
    user_id: int = Path(..., gt=0, description="User ID must be positive")
):
    return {"user_id": user_id}

# Query params — URL ke baad optional
@app.get("/users")
async def list_users(
    skip: int = Query(0, ge=0),
    limit: int = Query(10, le=100),
    search: Optional[str] = Query(None, min_length=2),
    is_active: bool = True,
):
    return {"skip": skip, "limit": limit, "search": search}

# Request body (Pydantic model)
class UserCreate(BaseModel):
    name: str
    email: str
    age: int

class UserResponse(BaseModel):
    id: int
    name: str
    email: str

    class Config:
        from_attributes = True  # ORM objects se kaam kare

@app.post("/users", response_model=UserResponse, status_code=201)
async def create_user(user: UserCreate):
    # DB mein save karo...
    return {"id": 1, **user.model_dump()}

# Path + Query + Body ek saath
@app.put("/users/{user_id}")
async def update_user(
    user_id: int = Path(..., gt=0),
    notify: bool = Query(False),
    user: UserCreate = Body(...),
):
    return {"user_id": user_id, "notify": notify, "data": user}
```

---

### Q2: Nested routes aur APIRouter kaise use karte hain?
**Answer:**
```python
# routers/users.py
from fastapi import APIRouter

router = APIRouter(prefix="/users", tags=["users"])

@router.get("/")
async def list_users(): ...

@router.get("/{user_id}")
async def get_user(user_id: int): ...

@router.get("/{user_id}/orders")
async def get_user_orders(user_id: int): ...

# routers/orders.py
router = APIRouter(prefix="/orders", tags=["orders"])

@router.post("/")
async def create_order(): ...

# main.py
from fastapi import FastAPI
from routers import users, orders

app = FastAPI()
app.include_router(users.router, prefix="/api/v1")
app.include_router(orders.router, prefix="/api/v1")

# Final URLs:
# GET /api/v1/users/
# GET /api/v1/users/{user_id}
# GET /api/v1/users/{user_id}/orders
# POST /api/v1/orders/
```

---

### Q3: Response model aur error handling kaise karte hain?
**Answer:**
```python
from fastapi import FastAPI, HTTPException, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel
from typing import Optional

app = FastAPI()

# Standard error response schema
class ErrorResponse(BaseModel):
    code: str
    message: str
    details: Optional[dict] = None

# Custom exception
class NotFoundException(Exception):
    def __init__(self, resource: str, id: int):
        self.resource = resource
        self.id = id

# Global exception handler
@app.exception_handler(NotFoundException)
async def not_found_handler(request, exc: NotFoundException):
    return JSONResponse(
        status_code=404,
        content=ErrorResponse(
            code="NOT_FOUND",
            message=f"{exc.resource} with id {exc.id} not found"
        ).model_dump()
    )

# Validation error handler
@app.exception_handler(RequestValidationError)
async def validation_handler(request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content=ErrorResponse(
            code="VALIDATION_ERROR",
            message="Invalid input",
            details={"errors": exc.errors()}
        ).model_dump()
    )

@app.get("/users/{user_id}")
async def get_user(user_id: int):
    user = await db.get(user_id)
    if not user:
        raise NotFoundException("User", user_id)
    return user

# HTTPException direct use
@app.delete("/users/{user_id}")
async def delete_user(user_id: int):
    if not await has_permission():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to delete users"
        )
```

---

### Q4: File upload/download FastAPI mein kaise karte hain?
**Answer:**
```python
from fastapi import FastAPI, UploadFile, File
from fastapi.responses import FileResponse, StreamingResponse
import aiofiles
import os

app = FastAPI()

@app.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    description: str = ""
):
    # Validate file type
    allowed_types = ["image/jpeg", "image/png", "application/pdf"]
    if file.content_type not in allowed_types:
        raise HTTPException(400, "File type not allowed")

    # Validate size (max 5MB)
    contents = await file.read()
    if len(contents) > 5 * 1024 * 1024:
        raise HTTPException(400, "File too large")

    # Save asynchronously
    filepath = f"uploads/{file.filename}"
    async with aiofiles.open(filepath, "wb") as f:
        await f.write(contents)

    return {"filename": file.filename, "size": len(contents)}

# Multiple files
@app.post("/upload-multiple")
async def upload_multiple(files: list[UploadFile] = File(...)):
    results = []
    for file in files:
        content = await file.read()
        results.append({"name": file.filename, "size": len(content)})
    return results

# Download
@app.get("/download/{filename}")
async def download_file(filename: str):
    filepath = f"uploads/{filename}"
    if not os.path.exists(filepath):
        raise HTTPException(404, "File not found")
    return FileResponse(
        filepath,
        media_type="application/octet-stream",
        filename=filename
    )

# Streaming response (large files)
@app.get("/stream/{filename}")
async def stream_file(filename: str):
    async def iterfile():
        async with aiofiles.open(f"uploads/{filename}", "rb") as f:
            while chunk := await f.read(64 * 1024):
                yield chunk
    return StreamingResponse(iterfile(), media_type="application/octet-stream")
```

---

### Q5: Lifespan events (startup/shutdown) kaise handle karte hain?
**Answer:**
```python
from contextlib import asynccontextmanager
from fastapi import FastAPI
import asyncpg
import redis.asyncio as aioredis

# App state store
class AppState:
    db_pool: asyncpg.Pool = None
    redis: aioredis.Redis = None

state = AppState()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # STARTUP
    state.db_pool = await asyncpg.create_pool(DATABASE_URL, min_size=5, max_size=20)
    state.redis = await aioredis.from_url(REDIS_URL)
    print("App started — DB pool and Redis connected")

    yield  # app run hota hai

    # SHUTDOWN
    await state.db_pool.close()
    await state.redis.close()
    print("App stopped — connections closed")

app = FastAPI(lifespan=lifespan)

@app.get("/users")
async def get_users():
    async with state.db_pool.acquire() as conn:
        return await conn.fetch("SELECT * FROM users LIMIT 10")
```

---

### Q6: OpenAPI docs customize kaise karte hain?
**Answer:**
```python
app = FastAPI(
    title="My API",
    description="Production-ready FastAPI application",
    version="1.0.0",
    docs_url="/docs",          # Swagger UI
    redoc_url="/redoc",        # ReDoc
    openapi_url="/openapi.json",
)

# Route level documentation
@app.post(
    "/users",
    response_model=UserResponse,
    status_code=201,
    summary="Create a new user",
    description="Creates a new user with email validation and hashed password.",
    response_description="The created user",
    responses={
        409: {"description": "User already exists"},
        422: {"description": "Validation error"},
    },
    tags=["users"],
)
async def create_user(user: UserCreate):
    """
    Create a user with:
    - **name**: Full name
    - **email**: Must be unique
    - **age**: Must be > 0
    """
    ...
```
