"""
MongoDB Advanced — Motor Async Driver + Beanie ODM + FastAPI
============================================================
Interview Prep Series | Python Backend + Agentic AI | Target: 20 LPA @ 5 YOE

Run FastAPI server:
    uvicorn 03_motor_async_fastapi:app --reload --port 8004

Test standalone (no uvicorn needed):
    python 03_motor_async_fastapi.py

Docker MongoDB (standard):
    docker run -d --name mongodb -p 27017:27017 \\
      -e MONGO_INITDB_ROOT_USERNAME=admin \\
      -e MONGO_INITDB_ROOT_PASSWORD=secret \\
      mongo:7.0

Docker MongoDB with Replica Set (for transactions + change streams):
    docker run -d --name mongo-rs -p 27017:27017 \\
      -e MONGO_INITDB_ROOT_USERNAME=admin \\
      -e MONGO_INITDB_ROOT_PASSWORD=secret \\
      mongo:7.0 --replSet rs0 --bind_ip_all
    docker exec mongo-rs mongosh -u admin -p secret \\
      --authenticationDatabase admin \\
      --eval "rs.initiate({_id:'rs0', members:[{_id:0,host:'localhost:27017'}]})"

API Docs (when running FastAPI):
    http://localhost:8004/docs
"""

import asyncio
import os
import random
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from typing import Any, Optional

from beanie import Document, PydanticObjectId, init_beanie
from beanie.operators import Inc, Set
from bson import ObjectId
from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator
from pymongo import ASCENDING, DESCENDING, IndexModel
from pymongo.errors import DuplicateKeyError, OperationFailure

# ============================================================
# CONFIGURATION
# ============================================================

MONGO_URI = os.getenv(
    "MONGO_URI",
    "mongodb://admin:secret@localhost:27017/practice_db?authSource=admin",
)
DB_NAME = "practice_db"

DOCKER_HINT = """
╔══════════════════════════════════════════════════════════════╗
║  MongoDB not reachable! Start it with Docker:                ║
║                                                              ║
║  docker run -d --name mongodb -p 27017:27017 \\              ║
║    -e MONGO_INITDB_ROOT_USERNAME=admin \\                     ║
║    -e MONGO_INITDB_ROOT_PASSWORD=secret \\                    ║
║    mongo:7.0                                                  ║
╚══════════════════════════════════════════════════════════════╝
"""


# ============================================================
# BEANIE DOCUMENT MODELS
# ============================================================


class Product(Document):
    """Product catalogue document."""

    name: str
    category: str
    price: float
    stock: int = 0
    tags: list[str] = []
    is_active: bool = True
    description: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None

    class Settings:
        name = "products"
        indexes = [
            IndexModel([("name", ASCENDING)]),
            IndexModel([("category", ASCENDING), ("price", ASCENDING)]),
            IndexModel([("tags", ASCENDING)]),
            IndexModel([("created_at", DESCENDING)]),
            IndexModel(
                [("category", ASCENDING), ("is_active", ASCENDING)],
                name="category_active_idx",
            ),
        ]


class User(Document):
    """User document."""

    name: str
    email: str
    region: str = "IN"
    is_active: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "users"
        indexes = [
            IndexModel([("email", ASCENDING)], unique=True),
        ]


class Order(Document):
    """Order document."""

    user_id: PydanticObjectId
    product_id: PydanticObjectId
    quantity: int
    total_price: float
    status: str = "pending"  # pending / completed / cancelled
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "orders"
        indexes = [
            IndexModel([("user_id", ASCENDING)]),
            IndexModel([("product_id", ASCENDING)]),
            IndexModel([("created_at", DESCENDING)]),
            IndexModel([("status", ASCENDING)]),
        ]


# ============================================================
# PYDANTIC REQUEST / RESPONSE SCHEMAS
# ============================================================


class ProductCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    category: str = Field(..., min_length=1)
    price: float = Field(..., gt=0)
    stock: int = Field(default=0, ge=0)
    tags: list[str] = []
    description: Optional[str] = None


class ProductUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1)
    category: Optional[str] = None
    price: Optional[float] = Field(default=None, gt=0)
    stock: Optional[int] = Field(default=None, ge=0)
    tags: Optional[list[str]] = None
    is_active: Optional[bool] = None
    description: Optional[str] = None


class UserCreate(BaseModel):
    name: str = Field(..., min_length=1)
    email: str
    region: str = "IN"

    @field_validator("email")
    @classmethod
    def lowercase_email(cls, v: str) -> str:
        return v.lower().strip()


class OrderCreate(BaseModel):
    user_id: str
    product_id: str
    quantity: int = Field(..., ge=1)

    @field_validator("user_id", "product_id")
    @classmethod
    def validate_object_id(cls, v: str) -> str:
        if not ObjectId.is_valid(v):
            raise ValueError(f"Invalid ObjectId: {v}")
        return v


class PaginationParams(BaseModel):
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=10, ge=1, le=100)


# ============================================================
# GLOBAL STATE & LIFESPAN
# ============================================================

_motor_client: Optional[AsyncIOMotorClient] = None


def get_motor_client() -> AsyncIOMotorClient:
    if _motor_client is None:
        raise RuntimeError("Motor client not initialised — lifespan not run?")
    return _motor_client


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: connect to MongoDB + init Beanie. Shutdown: close client."""
    global _motor_client

    print("🚀 Starting up — connecting to MongoDB...")
    _motor_client = AsyncIOMotorClient(
        MONGO_URI,
        maxPoolSize=50,
        minPoolSize=5,
        serverSelectionTimeoutMS=5000,
        connectTimeoutMS=10000,
    )

    try:
        await _motor_client.admin.command("ping")
        print("✅ MongoDB connected!")
    except Exception as exc:
        print(DOCKER_HINT)
        raise RuntimeError(f"Cannot connect to MongoDB: {exc}") from exc

    await init_beanie(
        database=_motor_client[DB_NAME],
        document_models=[Product, User, Order],
    )
    print("✅ Beanie initialised — indexes ensured.")

    yield  # ← app runs here

    print("🛑 Shutting down — closing MongoDB connection...")
    _motor_client.close()
    print("✅ MongoDB connection closed.")


# ============================================================
# FASTAPI APPLICATION
# ============================================================

app = FastAPI(
    title="E-Commerce Product Catalog & Orders API",
    description="Motor + Beanie + FastAPI — Production-ready example",
    version="1.0.0",
    lifespan=lifespan,
)


# ============================================================
# HELPER UTILITIES
# ============================================================


def parse_object_id(oid: str) -> ObjectId:
    """Validate and convert string to ObjectId, raise 400 on failure."""
    if not ObjectId.is_valid(oid):
        raise HTTPException(status_code=400, detail=f"Invalid ObjectId: {oid}")
    return ObjectId(oid)


def doc_to_dict(doc: dict) -> dict:
    """Convert MongoDB document — ObjectId fields to str."""
    if doc is None:
        return doc
    result = {}
    for k, v in doc.items():
        if isinstance(v, ObjectId):
            result[k] = str(v)
        elif isinstance(v, dict):
            result[k] = doc_to_dict(v)
        elif isinstance(v, list):
            result[k] = [str(i) if isinstance(i, ObjectId) else i for i in v]
        else:
            result[k] = v
    return result


# ============================================================
# PRODUCTS ENDPOINTS (Beanie ODM)
# ============================================================


@app.post("/products", status_code=201, tags=["Products"])
async def create_product(payload: ProductCreate) -> dict:
    """Create a single product using Beanie insert."""
    product = Product(**payload.model_dump())
    await product.insert()
    return {"id": str(product.id), "message": "Product created", "name": product.name}


@app.post("/products/bulk", status_code=201, tags=["Products"])
async def bulk_create_products(payload: list[ProductCreate]) -> dict:
    """Bulk insert products — fewer round trips than individual inserts."""
    if not payload:
        raise HTTPException(status_code=400, detail="Empty product list")

    docs = [Product(**p.model_dump()) for p in payload]
    await Product.insert_many(docs)
    return {
        "inserted_count": len(docs),
        "ids": [str(d.id) for d in docs],
    }


@app.get("/products", tags=["Products"])
async def list_products(
    category: Optional[str] = None,
    min_price: Optional[float] = Query(default=None, gt=0),
    max_price: Optional[float] = Query(default=None, gt=0),
    tag: Optional[str] = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=100),
) -> dict:
    """
    List products with optional filters and pagination.
    Demonstrates dynamic Beanie query building.
    """
    # Start with is_active filter
    conditions = [Product.is_active == True]  # noqa: E712

    if category:
        conditions.append(Product.category == category)
    if min_price is not None:
        conditions.append(Product.price >= min_price)
    if max_price is not None:
        conditions.append(Product.price <= max_price)
    if tag:
        conditions.append(Product.tags == tag)

    # Build query
    query = Product.find(*conditions)

    total = await query.count()
    skip = (page - 1) * page_size

    products = (
        await query.sort(-Product.created_at).skip(skip).limit(page_size).to_list()
    )

    return {
        "data": [
            {
                "id": str(p.id),
                "name": p.name,
                "category": p.category,
                "price": p.price,
                "stock": p.stock,
                "tags": p.tags,
                "is_active": p.is_active,
            }
            for p in products
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": max(1, (total + page_size - 1) // page_size),
    }


@app.get("/products/{product_id}", tags=["Products"])
async def get_product(product_id: str) -> dict:
    """Fetch product by ID."""
    try:
        pid = PydanticObjectId(product_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid product ID format")

    product = await Product.get(pid)
    if not product or not product.is_active:
        raise HTTPException(status_code=404, detail="Product not found")

    return {
        "id": str(product.id),
        "name": product.name,
        "category": product.category,
        "price": product.price,
        "stock": product.stock,
        "tags": product.tags,
        "description": product.description,
        "created_at": product.created_at.isoformat(),
    }


@app.put("/products/{product_id}", tags=["Products"])
async def update_product(product_id: str, payload: ProductUpdate) -> dict:
    """Partial update using Beanie Set operator."""
    try:
        pid = PydanticObjectId(product_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid product ID")

    product = await Product.get(pid)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    update_data = payload.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="No fields provided for update")

    update_data["updated_at"] = datetime.utcnow()
    await product.update(Set(update_data))
    await product.sync()  # Refresh from DB

    return {"id": str(product.id), "message": "Product updated", **update_data}


@app.delete("/products/{product_id}", status_code=204, tags=["Products"])
async def delete_product(product_id: str) -> None:
    """Soft delete — set is_active=False instead of removing document."""
    try:
        pid = PydanticObjectId(product_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid product ID")

    product = await Product.get(pid)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    await product.update(
        Set({"is_active": False, "updated_at": datetime.utcnow()})
    )
    return None


# ============================================================
# USERS ENDPOINTS
# ============================================================


@app.post("/users", status_code=201, tags=["Users"])
async def create_user(payload: UserCreate) -> dict:
    """Create user — handles duplicate email with 409."""
    user = User(**payload.model_dump())
    try:
        await user.insert()
    except DuplicateKeyError:
        raise HTTPException(
            status_code=409,
            detail=f"User with email '{payload.email}' already exists",
        )
    return {"id": str(user.id), "name": user.name, "email": user.email}


@app.get("/users/{user_id}", tags=["Users"])
async def get_user(user_id: str) -> dict:
    """Fetch user by ID."""
    try:
        uid = PydanticObjectId(user_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid user ID")

    user = await User.get(uid)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return {
        "id": str(user.id),
        "name": user.name,
        "email": user.email,
        "region": user.region,
    }


# ============================================================
# ORDERS ENDPOINTS — Transaction + Aggregation
# ============================================================


@app.post("/orders", status_code=201, tags=["Orders"])
async def create_order(payload: OrderCreate) -> dict:
    """
    Create order using Motor transaction:
    1. Check product stock
    2. Create order document
    3. Decrement stock
    All three steps run atomically.

    Note: Transactions require a Replica Set. If running standalone MongoDB,
    a fallback (non-transactional) path is used automatically.
    """
    client = get_motor_client()
    db = client[DB_NAME]
    orders_col = db["orders"]
    products_col = db["products"]

    user_oid = ObjectId(payload.user_id)
    product_oid = ObjectId(payload.product_id)

    # Verify user exists
    user = await User.get(PydanticObjectId(payload.user_id))
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    async def _transactional_create(session=None):
        """Core order creation logic — works with or without session."""
        product_doc = await products_col.find_one(
            {"_id": product_oid, "is_active": True},
            session=session,
        )
        if not product_doc:
            raise HTTPException(status_code=404, detail="Product not found")
        if product_doc["stock"] < payload.quantity:
            raise HTTPException(
                status_code=400,
                detail=f"Insufficient stock: {product_doc['stock']} available, "
                       f"{payload.quantity} requested",
            )

        total = product_doc["price"] * payload.quantity
        order_doc = {
            "user_id": user_oid,
            "product_id": product_oid,
            "quantity": payload.quantity,
            "total_price": total,
            "status": "completed",
            "created_at": datetime.utcnow(),
        }

        result = await orders_col.insert_one(order_doc, session=session)
        await products_col.update_one(
            {"_id": product_oid},
            {"$inc": {"stock": -payload.quantity}},
            session=session,
        )

        return {
            "order_id": str(result.inserted_id),
            "total_price": total,
            "status": "completed",
            "product_name": product_doc["name"],
        }

    # Try with transaction first (needs replica set)
    try:
        async with await client.start_session() as session:
            return await session.with_transaction(_transactional_create)
    except OperationFailure as exc:
        # Error code 20 = "Transaction numbers are only allowed on a replica set"
        if exc.code in (20, 263):
            print("⚠️  Replica set not available — falling back to non-transactional write")
            return await _transactional_create(session=None)
        raise HTTPException(status_code=500, detail=f"Database error: {exc.details}")


@app.get("/orders", tags=["Orders"])
async def list_orders(
    status: Optional[str] = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=50),
) -> dict:
    """
    List orders with user + product details via $lookup aggregation pipeline.
    Demonstrates multi-collection join using Motor aggregate().
    """
    client = get_motor_client()
    db = client[DB_NAME]
    orders_col = db["orders"]

    match_stage: dict[str, Any] = {}
    if status:
        match_stage["status"] = status

    pipeline = [
        *([ {"$match": match_stage} ] if match_stage else []),
        {"$sort": {"created_at": -1}},
        {"$skip": (page - 1) * page_size},
        {"$limit": page_size},
        # Join with users collection
        {
            "$lookup": {
                "from": "users",
                "localField": "user_id",
                "foreignField": "_id",
                "as": "user",
                "pipeline": [
                    {"$project": {"name": 1, "email": 1, "region": 1}}
                ],
            }
        },
        # Join with products collection
        {
            "$lookup": {
                "from": "products",
                "localField": "product_id",
                "foreignField": "_id",
                "as": "product",
                "pipeline": [
                    {"$project": {"name": 1, "category": 1, "price": 1}}
                ],
            }
        },
        # Unwind arrays from lookup (each lookup returns list)
        {"$unwind": {"path": "$user", "preserveNullAndEmptyArrays": True}},
        {"$unwind": {"path": "$product", "preserveNullAndEmptyArrays": True}},
        # Shape output
        {
            "$project": {
                "_id": {"$toString": "$_id"},
                "quantity": 1,
                "total_price": 1,
                "status": 1,
                "created_at": 1,
                "user": {
                    "id": {"$toString": "$user._id"},
                    "name": "$user.name",
                    "email": "$user.email",
                },
                "product": {
                    "id": {"$toString": "$product._id"},
                    "name": "$product.name",
                    "category": "$product.category",
                    "price": "$product.price",
                },
            }
        },
    ]

    # Count total separately
    count_pipeline = [*([ {"$match": match_stage} ] if match_stage else []), {"$count": "total"}]
    count_result = await orders_col.aggregate(count_pipeline).to_list(length=1)
    total = count_result[0]["total"] if count_result else 0

    orders = await orders_col.aggregate(pipeline).to_list(length=page_size)

    return {
        "data": orders,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": max(1, (total + page_size - 1) // page_size),
    }


@app.get("/orders/{user_id}/history", tags=["Orders"])
async def user_order_history(
    user_id: str,
    limit: int = Query(default=20, ge=1, le=100),
) -> dict:
    """User order history — sorted by most recent."""
    user_oid = parse_object_id(user_id)

    user = await User.get(PydanticObjectId(user_id))
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    client = get_motor_client()
    orders_col = client[DB_NAME]["orders"]

    pipeline = [
        {"$match": {"user_id": user_oid}},
        {"$sort": {"created_at": -1}},
        {"$limit": limit},
        {
            "$lookup": {
                "from": "products",
                "localField": "product_id",
                "foreignField": "_id",
                "as": "product",
            }
        },
        {"$unwind": {"path": "$product", "preserveNullAndEmptyArrays": True}},
        {
            "$project": {
                "_id": {"$toString": "$_id"},
                "quantity": 1,
                "total_price": 1,
                "status": 1,
                "created_at": 1,
                "product_name": "$product.name",
                "product_category": "$product.category",
            }
        },
    ]

    orders = await orders_col.aggregate(pipeline).to_list(length=limit)

    return {
        "user_id": user_id,
        "user_name": user.name,
        "orders": orders,
        "total_orders": len(orders),
        "total_spent": sum(o.get("total_price", 0) for o in orders),
    }


# ============================================================
# ANALYTICS ENDPOINTS
# ============================================================


@app.get("/analytics/revenue", tags=["Analytics"])
async def monthly_revenue(months: int = Query(default=6, ge=1, le=24)) -> dict:
    """
    Monthly revenue aggregation using $dateTrunc and $group.
    Demonstrates time-series aggregation pattern.
    """
    client = get_motor_client()
    orders_col = client[DB_NAME]["orders"]

    since = datetime.utcnow() - timedelta(days=months * 30)

    pipeline = [
        {"$match": {"status": "completed", "created_at": {"$gte": since}}},
        {
            "$group": {
                "_id": {
                    "year": {"$year": "$created_at"},
                    "month": {"$month": "$created_at"},
                },
                "revenue": {"$sum": "$total_price"},
                "order_count": {"$sum": 1},
                "avg_order_value": {"$avg": "$total_price"},
            }
        },
        {"$sort": {"_id.year": 1, "_id.month": 1}},
        {
            "$project": {
                "_id": 0,
                "period": {
                    "$concat": [
                        {"$toString": "$_id.year"},
                        "-",
                        {
                            "$cond": [
                                {"$lt": ["$_id.month", 10]},
                                {"$concat": ["0", {"$toString": "$_id.month"}]},
                                {"$toString": "$_id.month"},
                            ]
                        },
                    ]
                },
                "revenue": {"$round": ["$revenue", 2]},
                "order_count": 1,
                "avg_order_value": {"$round": ["$avg_order_value", 2]},
            }
        },
    ]

    results = await orders_col.aggregate(pipeline).to_list(length=None)
    total = sum(r["revenue"] for r in results)

    return {
        "monthly_breakdown": results,
        "total_revenue": round(total, 2),
        "period_months": months,
    }


@app.get("/analytics/top-products", tags=["Analytics"])
async def top_products(limit: int = Query(default=5, ge=1, le=20)) -> dict:
    """Top N products by total revenue."""
    client = get_motor_client()
    orders_col = client[DB_NAME]["orders"]

    pipeline = [
        {"$match": {"status": "completed"}},
        {
            "$group": {
                "_id": "$product_id",
                "total_revenue": {"$sum": "$total_price"},
                "total_units": {"$sum": "$quantity"},
                "order_count": {"$sum": 1},
            }
        },
        {"$sort": {"total_revenue": -1}},
        {"$limit": limit},
        {
            "$lookup": {
                "from": "products",
                "localField": "_id",
                "foreignField": "_id",
                "as": "product_info",
            }
        },
        {"$unwind": {"path": "$product_info", "preserveNullAndEmptyArrays": True}},
        {
            "$project": {
                "_id": 0,
                "product_id": {"$toString": "$_id"},
                "product_name": "$product_info.name",
                "category": "$product_info.category",
                "total_revenue": {"$round": ["$total_revenue", 2]},
                "total_units_sold": "$total_units",
                "order_count": 1,
            }
        },
    ]

    results = await orders_col.aggregate(pipeline).to_list(length=limit)
    return {"top_products": results, "limit": limit}


# ============================================================
# SEED ENDPOINT
# ============================================================

PRODUCT_NAMES = [
    ("Gaming Laptop", "electronics", 85000, ["gaming", "laptop", "premium"]),
    ("Wireless Mouse", "peripherals", 799, ["mouse", "wireless"]),
    ("Mechanical Keyboard", "peripherals", 3499, ["keyboard", "mechanical"]),
    ("27-inch Monitor", "electronics", 18000, ["monitor", "display"]),
    ("USB-C Hub", "accessories", 1299, ["hub", "usb-c"]),
    ("Noise Cancelling Headphones", "audio", 12000, ["headphones", "premium"]),
    ("Webcam 4K", "electronics", 4500, ["webcam", "video"]),
    ("External SSD 1TB", "storage", 7500, ["ssd", "storage"]),
    ("Smart Watch", "wearables", 15000, ["watch", "smart"]),
    ("Phone Stand", "accessories", 299, ["stand", "mobile"]),
    ("Laptop Bag", "accessories", 1899, ["bag", "laptop"]),
    ("HDMI Cable", "accessories", 399, ["cable", "hdmi"]),
    ("Gaming Chair", "furniture", 22000, ["chair", "gaming"]),
    ("Standing Desk", "furniture", 35000, ["desk", "ergonomic"]),
    ("Ring Light", "studio", 2199, ["light", "studio"]),
    ("Blue Light Glasses", "accessories", 799, ["glasses", "blue-light"]),
    ("Desk Pad XL", "accessories", 899, ["desk", "pad"]),
    ("Cable Management Kit", "accessories", 499, ["cables", "organizer"]),
    ("Smart Plug 4-Pack", "smart-home", 1499, ["smart-home", "plug"]),
    ("Portable Charger", "electronics", 2499, ["charger", "portable"]),
]

USER_DATA = [
    ("Arjun Sharma", "arjun@example.com", "North"),
    ("Priya Patel", "priya@example.com", "West"),
    ("Rahul Mehta", "rahul@example.com", "South"),
    ("Sneha Gupta", "sneha@example.com", "East"),
    ("Vikram Singh", "vikram@example.com", "North"),
    ("Ananya Reddy", "ananya@example.com", "South"),
    ("Kiran Kumar", "kiran@example.com", "West"),
    ("Divya Nair", "divya@example.com", "South"),
    ("Rohit Verma", "rohit@example.com", "Central"),
    ("Pooja Joshi", "pooja@example.com", "North"),
]


@app.post("/seed", status_code=201, tags=["Seed"])
async def seed_data(clear: bool = Query(default=False)) -> dict:
    """
    Seed 20 products, 10 users, and 50 orders.
    Pass ?clear=true to drop existing data first.
    """
    client = get_motor_client()
    db = client[DB_NAME]

    if clear:
        await db["products"].drop()
        await db["users"].drop()
        await db["orders"].drop()
        # Re-create indexes after drop
        await init_beanie(
            database=db, document_models=[Product, User, Order]
        )
        print("🗑️  Collections cleared.")

    # Seed products
    product_docs = []
    for name, category, price, tags in PRODUCT_NAMES:
        p = Product(
            name=name,
            category=category,
            price=float(price),
            stock=random.randint(0, 100),
            tags=tags,
            created_at=datetime.utcnow() - timedelta(days=random.randint(0, 365)),
        )
        product_docs.append(p)
    await Product.insert_many(product_docs)
    print(f"✅ Seeded {len(product_docs)} products")

    # Seed users
    user_docs = []
    for name, email, region in USER_DATA:
        try:
            u = User(name=name, email=email, region=region)
            await u.insert()
            user_docs.append(u)
        except DuplicateKeyError:
            existing = await User.find_one(User.email == email)
            if existing:
                user_docs.append(existing)
    print(f"✅ Seeded {len(user_docs)} users")

    # Seed orders — pick random user + product
    orders_created = 0
    for _ in range(50):
        user = random.choice(user_docs)
        product = random.choice(product_docs)
        qty = random.randint(1, 3)

        if product.stock >= qty:
            order = Order(
                user_id=user.id,
                product_id=product.id,
                quantity=qty,
                total_price=product.price * qty,
                status=random.choice(["pending", "completed", "cancelled"]),
                created_at=datetime.utcnow() - timedelta(days=random.randint(0, 180)),
            )
            await order.insert()
            orders_created += 1

    print(f"✅ Seeded {orders_created} orders")

    return {
        "products": len(product_docs),
        "users": len(user_docs),
        "orders": orders_created,
        "message": "Seed complete! Visit /docs to explore.",
    }


# ============================================================
# SECTION A — Direct Motor Demo (no Beanie)
# ============================================================


async def motor_direct_demo():
    """
    Raw Motor operations — shows driver-level API.
    Useful to understand what Beanie abstracts away.
    """
    print("\n" + "=" * 60)
    print("SECTION A — Direct Motor Demo")
    print("=" * 60)

    client = AsyncIOMotorClient(MONGO_URI, serverSelectionTimeoutMS=5000)
    try:
        await client.admin.command("ping")
    except Exception as exc:
        print(f"❌ Cannot connect: {exc}")
        print(DOCKER_HINT)
        return

    db = client["motor_demo_db"]
    items = db["items"]

    # Clean slate
    await items.drop()

    # INSERT
    result = await items.insert_one({
        "name": "Demo Item",
        "value": 42,
        "tags": ["demo", "motor"],
        "created_at": datetime.utcnow(),
    })
    print(f"Inserted ID: {result.inserted_id}")

    batch_result = await items.insert_many([
        {"name": f"Item {i}", "value": i * 10, "active": i % 2 == 0}
        for i in range(1, 6)
    ])
    print(f"Bulk inserted: {len(batch_result.inserted_ids)} docs")

    # FIND ONE
    doc = await items.find_one({"name": "Demo Item"})
    print(f"Found: {doc['name']} — value={doc['value']}")

    # FIND with async for
    print("Items with value > 20:")
    async for d in items.find({"value": {"$gt": 20}}):
        print(f"  • {d['name']}: {d['value']}")

    # to_list pattern
    all_items = await items.find({}).sort("value", 1).to_list(length=10)
    print(f"All items (sorted): {[i['name'] for i in all_items]}")

    # UPDATE
    upd = await items.update_one(
        {"name": "Demo Item"},
        {"$set": {"value": 99}, "$push": {"tags": "updated"}}
    )
    print(f"Updated: matched={upd.matched_count}, modified={upd.modified_count}")

    # COUNT
    total = await items.count_documents({})
    active = await items.count_documents({"active": True})
    print(f"Total: {total}, Active: {active}")

    # AGGREGATE
    pipeline = [
        {"$group": {"_id": "$active", "count": {"$sum": 1}, "avg_val": {"$avg": "$value"}}},
        {"$sort": {"_id": -1}},
    ]
    agg_results = await items.aggregate(pipeline).to_list(length=None)
    for r in agg_results:
        print(f"  Active={r['_id']}: count={r['count']}, avg_value={r['avg_val']:.1f}")

    # DELETE
    del_result = await items.delete_many({"active": False})
    print(f"Deleted inactive: {del_result.deleted_count} docs")

    # Cleanup
    await db.drop_collection("items")
    client.close()
    print("Motor demo complete ✅")


# ============================================================
# SECTION B — Change Stream Demo (commented out — needs replica set)
# ============================================================


async def change_stream_demo():
    """
    Real-time change notification demo.

    REQUIRES REPLICA SET — run first:
        docker run -d --name mongo-rs -p 27017:27017 \\
          -e MONGO_INITDB_ROOT_USERNAME=admin \\
          -e MONGO_INITDB_ROOT_PASSWORD=secret \\
          mongo:7.0 --replSet rs0 --bind_ip_all
        docker exec mongo-rs mongosh -u admin -p secret \\
          --authenticationDatabase admin \\
          --eval "rs.initiate({_id:'rs0',members:[{_id:0,host:'localhost:27017'}]})"
    """
    print("\n" + "=" * 60)
    print("SECTION B — Change Stream Demo")
    print("=" * 60)
    print("⚠️  This requires a Replica Set. See docstring for setup.")

    # Uncomment below to run (replica set required):
    #
    # client = AsyncIOMotorClient(MONGO_URI)
    # collection = client["cs_demo"]["events"]
    #
    # # Watch only insert operations on this collection
    # pipeline = [{"$match": {"operationType": "insert"}}]
    #
    # print("Watching for inserts (Ctrl+C to stop)...")
    # async with collection.watch(pipeline, full_document="updateLookup") as stream:
    #     # In background: insert some docs
    #     async def inserter():
    #         await asyncio.sleep(1)
    #         for i in range(3):
    #             await collection.insert_one({"event": f"event_{i}", "ts": datetime.utcnow()})
    #             await asyncio.sleep(0.5)
    #
    #     asyncio.create_task(inserter())
    #
    #     count = 0
    #     async for change in stream:
    #         op = change["operationType"]
    #         doc = change.get("fullDocument", {})
    #         print(f"  Change [{op}]: {doc.get('event')} at {doc.get('ts')}")
    #         count += 1
    #         if count >= 3:
    #             break  # Stop after 3 events
    #
    # client.close()
    print("  (Uncomment code in change_stream_demo() to run)")


# ============================================================
# SECTION C — Concurrent Operations with asyncio.gather
# ============================================================


async def concurrent_ops_demo():
    """
    Demonstrates running multiple Motor/Beanie queries concurrently
    using asyncio.gather() — much faster than sequential awaits.
    """
    print("\n" + "=" * 60)
    print("SECTION C — Concurrent Operations Demo")
    print("=" * 60)

    client = AsyncIOMotorClient(MONGO_URI, serverSelectionTimeoutMS=5000)
    try:
        await client.admin.command("ping")
    except Exception as exc:
        print(f"❌ Cannot connect: {exc}")
        return

    db = client["concurrent_demo"]
    col = db["products"]

    # Seed some data
    await col.drop()
    await col.insert_many([
        {"name": f"Product {i}", "category": "electronics" if i % 2 == 0 else "other",
         "price": float(i * 100), "stock": i * 5}
        for i in range(1, 21)
    ])

    # ✅ Sequential — slow (each awaits the previous)
    t0 = asyncio.get_event_loop().time()
    res1 = await col.find({"category": "electronics"}).to_list(length=100)
    res2 = await col.find({"price": {"$lt": 500}}).to_list(length=100)
    res3 = await col.count_documents({"stock": {"$gt": 50}})
    sequential_time = asyncio.get_event_loop().time() - t0
    print(f"Sequential: {sequential_time*1000:.1f}ms — "
          f"electronics={len(res1)}, cheap={len(res2)}, high_stock={res3}")

    # ✅ Concurrent with asyncio.gather — fast!
    t0 = asyncio.get_event_loop().time()
    results = await asyncio.gather(
        col.find({"category": "electronics"}).to_list(length=100),
        col.find({"price": {"$lt": 500}}).to_list(length=100),
        col.count_documents({"stock": {"$gt": 50}}),
    )
    concurrent_time = asyncio.get_event_loop().time() - t0
    print(f"Concurrent:  {concurrent_time*1000:.1f}ms — "
          f"electronics={len(results[0])}, cheap={len(results[1])}, high_stock={results[2]}")

    speedup = sequential_time / concurrent_time if concurrent_time > 0 else 1
    print(f"Speedup: ~{speedup:.1f}x faster with concurrent execution")

    await db.drop_collection("products")
    client.close()
    print("Concurrent demo complete ✅")


# ============================================================
# TRANSACTION DEMO (standalone — with fallback)
# ============================================================


async def transaction_demo():
    """
    Demonstrates Motor transaction — order creation with stock check.
    Falls back gracefully if no replica set is available.
    """
    print("\n" + "=" * 60)
    print("SECTION D — Transaction Demo")
    print("=" * 60)

    client = AsyncIOMotorClient(MONGO_URI, serverSelectionTimeoutMS=5000)
    try:
        await client.admin.command("ping")
    except Exception as exc:
        print(f"❌ Cannot connect: {exc}")
        return

    db = client["txn_demo"]
    products = db["products"]
    orders = db["orders"]

    await products.drop()
    await orders.drop()

    # Seed one product
    product_result = await products.insert_one({
        "name": "Test Widget",
        "price": 299.0,
        "stock": 5,
    })
    product_id = product_result.inserted_id

    user_id = ObjectId()  # Fake user ID for demo

    print(f"Product: Test Widget, stock=5, price=299")
    print(f"Attempting to buy 3 units...")

    async def txn_body(session=None):
        product = await products.find_one({"_id": product_id}, session=session)
        if product["stock"] < 3:
            raise ValueError("Insufficient stock")

        await orders.insert_one({
            "user_id": user_id,
            "product_id": product_id,
            "quantity": 3,
            "total": 299.0 * 3,
            "created_at": datetime.utcnow(),
        }, session=session)

        await products.update_one(
            {"_id": product_id},
            {"$inc": {"stock": -3}},
            session=session,
        )

    try:
        async with await client.start_session() as session:
            await session.with_transaction(txn_body)
        print("✅ Transaction committed!")
    except OperationFailure as exc:
        if exc.code in (20, 263):
            print("⚠️  No replica set — running without transaction")
            await txn_body(session=None)
            print("✅ Operations completed (non-transactional)")
        else:
            print(f"❌ DB error: {exc}")

    updated = await products.find_one({"_id": product_id})
    order = await orders.find_one({"product_id": product_id})
    print(f"Stock after purchase: {updated['stock']} (expected 2)")
    print(f"Order created: quantity={order['quantity']}, total={order['total']}")

    await db.drop_collection("products")
    await db.drop_collection("orders")
    client.close()
    print("Transaction demo complete ✅")


# ============================================================
# STANDALONE DEMO RUNNER
# ============================================================


async def standalone_demo():
    """
    Standalone demo — runs without uvicorn/FastAPI.
    Tests Motor connection and demonstrates core operations.

    Run: python 03_motor_async_fastapi.py
    """
    print("\n🚀 MongoDB + Motor Standalone Demo")
    print("=" * 60)
    print(f"Connecting to: {MONGO_URI}\n")

    # Check connectivity first
    client = AsyncIOMotorClient(MONGO_URI, serverSelectionTimeoutMS=5000)
    try:
        info = await client.admin.command("ping")
        server_info = await client.server_info()
        print(f"✅ Connected! MongoDB version: {server_info.get('version', 'unknown')}")
    except Exception as exc:
        print(f"❌ Connection failed: {exc}")
        print(DOCKER_HINT)
        return
    finally:
        client.close()

    # Run all demo sections
    await motor_direct_demo()
    await concurrent_ops_demo()
    await transaction_demo()
    await change_stream_demo()  # Will print notice, not actually run

    print("\n" + "=" * 60)
    print("✅ All standalone demos complete!")
    print("\nTo run the full FastAPI app:")
    print("  uvicorn 03_motor_async_fastapi:app --reload --port 8004")
    print("  Then open: http://localhost:8004/docs")
    print("=" * 60)


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    asyncio.run(standalone_demo())
