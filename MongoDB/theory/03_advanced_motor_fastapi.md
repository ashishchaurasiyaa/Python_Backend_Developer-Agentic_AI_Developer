# 🚀 MongoDB Advanced — Motor, Beanie & FastAPI Integration
### Interview Prep Series | Python Backend + Agentic AI | Target: 20 LPA @ 5 YOE

---

## 📋 Table of Contents
1. [Motor kya hai?](#1-motor-kya-hai)
2. [Motor Setup & Connection](#2-motor-setup--connection)
3. [Motor Async CRUD Operations](#3-motor-async-crud-operations)
4. [Beanie ODM](#4-beanie-odm)
5. [FastAPI + Motor Integration](#5-fastapi--motor-integration)
6. [FastAPI + Beanie Integration](#6-fastapi--beanie-integration)
7. [Multi-Document Transactions](#7-multi-document-transactions)
8. [Change Streams](#8-change-streams)
9. [Replica Sets](#9-replica-sets)
10. [Sharding Basics](#10-sharding-basics)
11. [GridFS](#11-gridfs)
12. [Atlas Search](#12-atlas-search-mention)
13. [Performance Best Practices](#13-performance-best-practices)
14. [Interview Q&A](#14-interview-qa)

---

## 1. Motor kya hai?

### 🔑 Core Concept
**Motor** ek **async MongoDB driver** hai Python ke liye. PyMongo synchronous (blocking) operations karta hai, jabki Motor **asyncio** ke saath kaam karta hai — yaani FastAPI, aiohttp, Starlette jaise async frameworks ke saath perfectly fit hota hai.

> **Simple analogy:** PyMongo ek waiter ki tarah hai jo ek table ka order leta hai, kitchen mein jaata hai, waapas aata hai, tab doosre table ka order leta hai. Motor ek aisa waiter hai jo sabke orders le leta hai, saare dishes ek saath utha ke laata hai.

### 📊 PyMongo vs Motor Comparison Table

| Feature | PyMongo (Sync) | Motor (Async) |
|---------|---------------|---------------|
| Import | `from pymongo import MongoClient` | `from motor.motor_asyncio import AsyncIOMotorClient` |
| Connection | `MongoClient(URI)` | `AsyncIOMotorClient(URI)` |
| find_one | `collection.find_one(filter)` | `await collection.find_one(filter)` |
| insert_one | `collection.insert_one(doc)` | `await collection.insert_one(doc)` |
| Cursor iteration | `for doc in collection.find()` | `async for doc in collection.find()` |
| Thread model | Thread-based blocking | asyncio event loop |
| FastAPI compatible | ❌ (blocks event loop) | ✅ Native |
| Flask compatible | ✅ | ❌ (needs async Flask) |
| API surface | pymongo native | **Same as pymongo** (Motor wraps it) |
| Under the hood | Direct socket calls | asyncio + pymongo |
| Connection pool | Yes | Yes (same settings) |

### 🔍 Internals Samajhte Hain
Motor internally **PyMongo ko wrap karta hai** — yani vo same MongoDB wire protocol use karta hai, lekin operations ko `asyncio.get_event_loop().run_in_executor()` mein delegate karta hai. Aapka code `await` karta hai, lekin actual I/O asyncio event loop handle karta hai.

```
Your FastAPI code
     │
     ▼
  await motor_operation()
     │
     ▼
  asyncio event loop (non-blocking)
     │
     ▼
  Motor (wraps pymongo)
     │
     ▼
  MongoDB Wire Protocol (TCP)
     │
     ▼
  MongoDB Server
```

### 🏷️ Client Classes
- `AsyncIOMotorClient` — asyncio ke saath use karo (FastAPI, Starlette)
- `MotorClient` — tornado ke saath use karo (legacy)
- `AsyncIOMotorDatabase` — database reference
- `AsyncIOMotorCollection` — collection reference
- `AsyncIOMotorCursor` — cursor (NOT awaitable, iterate karo `async for` se)

---

## 2. Motor Setup & Connection

### 📦 Installation
```bash
pip install motor          # Motor async driver
pip install beanie         # ODM (Beanie uses Motor internally)
pip install fastapi uvicorn # API framework
pip install pydantic        # Data validation
```

### 🔧 Connection Setup
```python
import os
from motor.motor_asyncio import AsyncIOMotorClient

MONGO_URI = os.getenv(
    "MONGO_URI",
    "mongodb://admin:secret@localhost:27017/practice_db?authSource=admin"
)

# Client banao — yeh ek pool maintain karta hai
client = AsyncIOMotorClient(
    MONGO_URI,
    maxPoolSize=50,        # Max 50 simultaneous connections
    minPoolSize=5,         # Startup pe 5 connections maintain karo
    serverSelectionTimeoutMS=5000,   # 5 sec mein server mile ya timeout
    connectTimeoutMS=10000,          # TCP connection timeout
    socketTimeoutMS=45000,           # Individual operation timeout
    retryWrites=True,                # Failed writes auto-retry
    w="majority",                    # Write concern — majority nodes ko ack do
)

# Database aur collection reference
db = client.get_database("practice_db")
collection = db.get_collection("products")

# Shorthand (same result)
db = client["practice_db"]
collection = db["products"]
```

### ⚙️ Connection Pool Kya Hai?
**Connection pooling** matlab: ek baar MongoDB se connection banao, phir us connection ko reuse karo. Naya connection banana expensive hai (TCP handshake + auth). Pool mein 5-50 connections ready rahte hain — `maxPoolSize=50` matlab zyada concurrent requests aane pe 50 tak connections khol sakte ho.

```python
# ✅ SAHI — Client ek baar banao, reuse karo
# Application startup pe
client = AsyncIOMotorClient(MONGO_URI, maxPoolSize=50)

# ❌ GALAT — Har request mein naya client mat banao
async def get_product(id: str):
    client = AsyncIOMotorClient(MONGO_URI)  # BAD! Pool ka fayda nahin
    ...
```

### 🔒 Authentication Options
```python
# Option 1: URI mein credentials
client = AsyncIOMotorClient("mongodb://user:pass@host:27017/dbname?authSource=admin")

# Option 2: Alag parameters
client = AsyncIOMotorClient(
    host="localhost",
    port=27017,
    username="admin",
    password="secret",
    authSource="admin"
)

# Option 3: MongoDB Atlas
client = AsyncIOMotorClient(
    "mongodb+srv://user:pass@cluster.mongodb.net/dbname?retryWrites=true&w=majority"
)

# Option 4: X.509 certificate
client = AsyncIOMotorClient(
    "mongodb://host:27017",
    tls=True,
    tlsCertificateKeyFile="/path/to/client.pem",
    authMechanism="MONGODB-X509"
)
```

---

## 3. Motor Async CRUD Operations

### ✅ Insert Operations

```python
from datetime import datetime
from motor.motor_asyncio import AsyncIOMotorClient

client = AsyncIOMotorClient(MONGO_URI)
db = client.practice_db
products = db.products

# Insert ONE document
async def demo_insert():
    product = {
        "name": "Laptop Pro",
        "category": "electronics",
        "price": 75000.0,
        "stock": 10,
        "tags": ["laptop", "premium"],
        "created_at": datetime.utcnow()
    }
    
    result = await products.insert_one(product)
    print(f"Inserted ID: {result.inserted_id}")
    # result.inserted_id → ObjectId('...')

    # Insert MANY documents
    items = [
        {"name": "Mouse", "price": 599.0},
        {"name": "Keyboard", "price": 1299.0},
        {"name": "Monitor", "price": 15000.0},
    ]
    result_many = await products.insert_many(items)
    print(f"Inserted {len(result_many.inserted_ids)} documents")
    # result_many.inserted_ids → [ObjectId(...), ObjectId(...), ...]
```

### 🔍 Find Operations — IMPORTANT GOTCHA!

> **⚠️ Sabse common mistake:** `collection.find()` ka result awaitable NAHIN hai — yeh ek **cursor** return karta hai. Cursor ko `async for` ya `.to_list()` se iterate karna padta hai.

```python
from bson import ObjectId

async def demo_find():
    # find_one — yeh awaitable hai ✅
    product = await products.find_one({"name": "Laptop Pro"})
    if product:
        print(product["_id"])  # ObjectId
        print(product["name"])  # "Laptop Pro"
    
    # find_one by _id
    product = await products.find_one({"_id": ObjectId("64a7b2c3d4e5f6a7b8c9d0e1")})
    
    # find — cursor return hota hai, NOT awaitable ❌
    # cursor = await products.find({})  # ❌ YEH KAAM NAHIN KARTA
    
    # Pattern 1: async for loop
    async for doc in products.find({"category": "electronics"}):
        print(doc["name"])
    
    # Pattern 2: to_list — sabse common in FastAPI routes
    all_products = await products.find(
        {"category": "electronics"}
    ).to_list(length=100)  # length=None matlab sab fetch karo (careful with large collections!)
    
    # Pattern 3: with projection (sirf kuch fields)
    names_only = await products.find(
        {},
        projection={"name": 1, "price": 1, "_id": 0}  # _id=0 matlab exclude
    ).to_list(length=50)
    
    # Pattern 4: sort + skip + limit (pagination)
    page_products = await products.find(
        {"is_active": True}
    ).sort("price", -1).skip(20).limit(10).to_list(length=10)
    # sort: 1=ascending, -1=descending
    # skip(20) = page 3 (if page_size=10)
```

### ✏️ Update Operations

```python
async def demo_update():
    # update_one — pehla matching document update karo
    result = await products.update_one(
        {"name": "Laptop Pro"},           # filter
        {"$set": {"price": 72000.0,      # update operators
                  "stock": 8}}
    )
    print(f"Matched: {result.matched_count}, Modified: {result.modified_count}")
    
    # update_many — saare matching documents update karo
    result = await products.update_many(
        {"category": "electronics"},
        {"$mul": {"price": 0.9}}   # 10% discount
    )
    print(f"Modified: {result.modified_count} documents")
    
    # findOneAndUpdate — update karo aur updated doc return karo
    from pymongo import ReturnDocument
    updated = await products.find_one_and_update(
        {"name": "Laptop Pro"},
        {"$inc": {"stock": -1}},
        return_document=ReturnDocument.AFTER,  # Updated value chahiye
        upsert=False
    )
    
    # upsert — agar nahi mila to create karo
    result = await products.update_one(
        {"sku": "PROD-001"},
        {"$set": {"name": "New Product", "price": 999.0}},
        upsert=True  # ✅
    )
    if result.upserted_id:
        print(f"New doc created: {result.upserted_id}")

    # Common update operators:
    # $set      — fields set karo
    # $unset    — field delete karo {"$unset": {"old_field": ""}}
    # $inc      — number increment karo {"$inc": {"stock": -1}}
    # $push     — array mein element add karo {"$push": {"tags": "sale"}}
    # $pull     — array se element remove karo {"$pull": {"tags": "old"}}
    # $addToSet — array mein unique add karo
    # $mul      — multiply karo
    # $rename   — field rename karo
```

### 🗑️ Delete Operations

```python
async def demo_delete():
    # delete_one — pehla match delete karo
    result = await products.delete_one({"name": "Old Product"})
    print(f"Deleted: {result.deleted_count}")
    
    # delete_many — saare matches delete karo
    result = await products.delete_many({"is_active": False})
    print(f"Deleted: {result.deleted_count} inactive products")
    
    # find_one_and_delete — delete karo aur document return karo
    deleted_doc = await products.find_one_and_delete({"name": "Temp Product"})
    if deleted_doc:
        print(f"Deleted: {deleted_doc}")
```

### 📊 Count & Aggregate

```python
async def demo_count_aggregate():
    # count_documents — filter ke saath count karo
    total = await products.count_documents({})
    active = await products.count_documents({"is_active": True})
    expensive = await products.count_documents({"price": {"$gte": 10000}})
    
    # estimated_document_count — fast but approximate (uses metadata)
    approx = await products.estimated_document_count()
    
    # Aggregate pipeline
    pipeline = [
        {"$match": {"is_active": True}},
        {"$group": {
            "_id": "$category",
            "total_revenue": {"$sum": {"$multiply": ["$price", "$stock"]}},
            "count": {"$sum": 1},
            "avg_price": {"$avg": "$price"}
        }},
        {"$sort": {"total_revenue": -1}},
        {"$limit": 5}
    ]
    
    # aggregate() karna hai to_list() ke saath
    results = await products.aggregate(pipeline).to_list(length=None)
    for r in results:
        print(f"Category: {r['_id']}, Revenue: {r['total_revenue']}")
```

### ⚡ Bulk Write

```python
from pymongo import InsertOne, UpdateOne, DeleteOne

async def demo_bulk_write():
    operations = [
        InsertOne({"name": "Product A", "price": 100.0}),
        InsertOne({"name": "Product B", "price": 200.0}),
        UpdateOne(
            {"name": "Old Product"},
            {"$set": {"price": 500.0}},
            upsert=True
        ),
        DeleteOne({"name": "Discontinued"})
    ]
    
    result = await products.bulk_write(operations, ordered=False)
    # ordered=False — agar ek fail ho to baaki continue karo
    print(f"Inserted: {result.inserted_count}")
    print(f"Modified: {result.modified_count}")
    print(f"Deleted: {result.deleted_count}")
```

---

## 4. Beanie ODM

### 🔑 Beanie kya hai?
**Beanie** ek **Python ODM (Object-Document Mapper)** hai jo **Pydantic** models ko MongoDB documents ke saath map karta hai. Yeh Motor ke upar build hai.

> **Analogy:** Agar Motor "raw SQL queries" ki tarah hai, toh Beanie "SQLAlchemy" ki tarah hai — but MongoDB ke liye, aur Pydantic validation ke saath.

**Fayda:**
- ✅ Pydantic validation automatic
- ✅ Type hints ka full support  
- ✅ IDE autocomplete kaam karta hai
- ✅ Less boilerplate code
- ✅ Schema migrations support (via Migrator)
- ❌ Raw Motor se thoda slow (overhead)
- ❌ Complex queries mein sometimes Motor better

### 📦 Document Class Definition

```python
from datetime import datetime
from typing import Optional, List
from beanie import Document, Link, BackLink, before_event, after_event, Insert, Save
from beanie import init_beanie, PydanticObjectId
from pydantic import Field, EmailStr
from pymongo import IndexModel, ASCENDING, DESCENDING

class Product(Document):
    """Product document — MongoDB 'products' collection mein store hoga"""
    
    name: str
    category: str
    price: float
    stock: int = 0
    tags: List[str] = []
    is_active: bool = True
    description: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None
    
    class Settings:
        # Collection ka naam MongoDB mein
        name = "products"
        
        # Indexes — performance ke liye zaroori
        indexes = [
            IndexModel([("name", ASCENDING)]),
            IndexModel([("category", ASCENDING), ("price", ASCENDING)]),
            IndexModel([("tags", ASCENDING)]),
            IndexModel([("created_at", DESCENDING)]),
            # Compound index
            IndexModel(
                [("category", ASCENDING), ("is_active", ASCENDING)],
                name="category_active_idx"
            ),
        ]
    
    # Hook — save karne se pehle run hoga
    @before_event(Save)
    def update_timestamp(self):
        self.updated_at = datetime.utcnow()
    
    # Hook — insert ke baad run hoga
    @after_event(Insert)
    def log_creation(self):
        print(f"New product created: {self.name}")
    
    # Custom method
    def apply_discount(self, percent: float) -> float:
        return self.price * (1 - percent / 100)


class User(Document):
    name: str
    email: EmailStr
    region: str = "IN"
    is_active: bool = True
    
    class Settings:
        name = "users"
        indexes = [
            IndexModel([("email", ASCENDING)], unique=True),  # Unique email!
        ]


class Order(Document):
    # PydanticObjectId — MongoDB ObjectId ko Pydantic mein use karne ka tarika
    user_id: PydanticObjectId
    product_id: PydanticObjectId
    quantity: int
    total_price: float
    status: str = "pending"  # pending/completed/cancelled
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Settings:
        name = "orders"
        indexes = [
            IndexModel([("user_id", ASCENDING)]),
            IndexModel([("created_at", DESCENDING)]),
            IndexModel([("status", ASCENDING)]),
        ]
```

### 🚀 Beanie Initialization

```python
from beanie import init_beanie
from motor.motor_asyncio import AsyncIOMotorClient

async def startup():
    client = AsyncIOMotorClient(MONGO_URI)
    
    # Sabhi Document models register karo
    await init_beanie(
        database=client.practice_db,
        document_models=[Product, User, Order]
        # document_models bhi string paths accept karta hai:
        # ["myapp.models.Product", "myapp.models.User"]
    )
    print("Beanie initialized! Indexes created.")
```

### 📝 Beanie CRUD Operations

```python
async def beanie_crud_demo():
    # ===== CREATE =====
    
    # Single insert
    product = Product(
        name="Gaming Laptop",
        category="electronics",
        price=85000.0,
        stock=5,
        tags=["gaming", "laptop", "premium"]
    )
    await product.insert()
    print(f"Created: {product.id}")  # .id is PydanticObjectId
    
    # Alternative: save() — insert ya update karta hai
    new_product = Product(name="Mouse", category="peripherals", price=799.0, stock=50)
    await new_product.save()
    
    # ===== READ =====
    
    # find_one — pehla matching document
    found = await Product.find_one(Product.name == "Gaming Laptop")
    
    # get — ID se dhundho (None return karta hai agar na mile)
    product_by_id = await Product.get(product.id)
    
    # find — cursor return karta hai
    # .find() → BeanieQueryBuilder
    
    # Saare active products
    all_active = await Product.find(Product.is_active == True).to_list()
    
    # Filter with operators
    expensive = await Product.find(
        Product.price > 10000,
        Product.is_active == True
    ).to_list()
    
    # Sort + pagination
    page_1 = await Product.find(
        Product.category == "electronics"
    ).sort(-Product.price).skip(0).limit(10).to_list()
    
    # Count
    count = await Product.find(Product.category == "electronics").count()
    
    # First
    first_product = await Product.find(Product.price < 1000).first_or_none()
    
    # ===== UPDATE =====
    
    # Method 1: Object ko modify karo, phir save()
    product.price = 80000.0
    product.stock = 3
    await product.save()
    
    # Method 2: set() — specific fields update karo (partial update)
    from beanie.operators import Set, Inc, Push, Pull
    
    await Product.find_one(Product.name == "Gaming Laptop").update(
        Set({Product.price: 78000.0})
    )
    
    # Method 3: update_one on fetched doc
    if product:
        await product.update(
            Inc({Product.stock: -1}),  # stock--
            Push({Product.tags: "discounted"})  # tag add karo
        )
    
    # Update many
    await Product.find(
        Product.category == "electronics"
    ).update(
        Set({Product.is_active: True})
    )
    
    # ===== DELETE =====
    
    # Fetch karke delete karo
    product = await Product.find_one(Product.name == "Old Product")
    if product:
        await product.delete()
    
    # Direct delete (without fetching)
    await Product.find(Product.is_active == False).delete()
```

### 🔗 Link aur BackLink (References)

```python
from beanie import Link, BackLink

class Category(Document):
    name: str
    
    class Settings:
        name = "categories"

class ProductWithLink(Document):
    name: str
    price: float
    # Link — Category document ka reference store karta hai
    # MongoDB mein sirf ObjectId store hota hai, but Beanie populate kar sakta hai
    category: Link[Category]
    
    class Settings:
        name = "products_linked"

# Usage
async def link_demo():
    cat = Category(name="Electronics")
    await cat.insert()
    
    prod = ProductWithLink(name="Phone", price=15000.0, category=cat)
    await prod.insert()
    
    # Fetch with link populated (JOIN jaisa kaam)
    product = await ProductWithLink.find_one(
        ProductWithLink.name == "Phone",
        fetch_links=True  # ← Yeh category ko bhi fetch karega
    )
    print(product.category.name)  # "Electronics"
```

### 📊 Beanie Aggregation

```python
async def beanie_aggregation():
    # Raw aggregation pipeline use karo
    pipeline = [
        {"$match": {"is_active": True}},
        {"$group": {
            "_id": "$category",
            "count": {"$sum": 1},
            "avg_price": {"$avg": "$price"}
        }},
        {"$sort": {"count": -1}}
    ]
    
    results = await Product.aggregate(pipeline).to_list()
    # results → list of dicts (raw MongoDB output)
```

---

## 5. FastAPI + Motor Integration

### 🏗️ Lifespan Pattern (Modern FastAPI)

> **Note:** FastAPI mein startup/shutdown ke liye **lifespan context manager** use karo — `@app.on_event("startup")` deprecated ho gaya hai FastAPI 0.93+ mein.

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, HTTPException, status
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from bson import ObjectId
from typing import AsyncGenerator

# Global client (module level)
motor_client: AsyncIOMotorClient = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup aur shutdown handle karo"""
    global motor_client
    
    # ===== STARTUP =====
    print("Starting up — connecting to MongoDB...")
    motor_client = AsyncIOMotorClient(
        MONGO_URI,
        maxPoolSize=50,
        minPoolSize=5,
        serverSelectionTimeoutMS=5000
    )
    
    # Connection verify karo
    try:
        await motor_client.admin.command("ping")
        print("✅ MongoDB connected!")
    except Exception as e:
        print(f"❌ MongoDB connection failed: {e}")
        raise
    
    yield  # ← App yahan run hoti hai
    
    # ===== SHUTDOWN =====
    print("Shutting down — closing MongoDB connection...")
    motor_client.close()
    print("✅ MongoDB connection closed.")

app = FastAPI(title="Product API", lifespan=lifespan)
```

### 💉 Dependency Injection

```python
# Database dependency — har request mein fresh db reference
async def get_database() -> AsyncIOMotorDatabase:
    return motor_client.practice_db

# Collection dependency
async def get_products_collection(
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    return db.get_collection("products")
```

### 📐 Pydantic Response Models with ObjectId

```python
from pydantic import BaseModel, Field, ConfigDict
from bson import ObjectId
from typing import Any

# ObjectId ko JSON serializable banane ka tarika
class PyObjectId(str):
    """Custom type — ObjectId ko string mein convert karta hai JSON ke liye"""
    
    @classmethod
    def __get_validators__(cls):
        yield cls.validate
    
    @classmethod
    def validate(cls, v, info=None):
        if isinstance(v, ObjectId):
            return str(v)
        if ObjectId.is_valid(str(v)):
            return str(v)
        raise ValueError(f"Invalid ObjectId: {v}")

# Pydantic v2 approach (recommended)
class ProductResponse(BaseModel):
    model_config = ConfigDict(
        populate_by_name=True,      # Allow both 'id' and '_id'
        arbitrary_types_allowed=True
    )
    
    id: Optional[str] = Field(default=None, alias="_id")
    name: str
    category: str
    price: float
    stock: int
    tags: list[str] = []
    is_active: bool
    
    @classmethod
    def from_mongo(cls, doc: dict) -> "ProductResponse":
        """MongoDB document → Response model"""
        if doc and "_id" in doc:
            doc["_id"] = str(doc["_id"])  # ObjectId → str
        return cls(**doc)
```

### 🔄 Full CRUD Endpoints (Motor Direct)

```python
from fastapi import FastAPI, Depends, HTTPException, Query, Body
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from bson import ObjectId
from typing import Optional, List

class ProductCreate(BaseModel):
    name: str
    category: str
    price: float
    stock: int = 0
    tags: List[str] = []

class ProductUpdate(BaseModel):
    name: Optional[str] = None
    price: Optional[float] = None
    stock: Optional[int] = None
    tags: Optional[List[str]] = None
    is_active: Optional[bool] = None

@app.post("/products", status_code=201)
async def create_product(
    product: ProductCreate,
    collection=Depends(get_products_collection)
):
    doc = product.model_dump()
    doc["is_active"] = True
    doc["created_at"] = datetime.utcnow()
    
    result = await collection.insert_one(doc)
    
    # Created document return karo
    created = await collection.find_one({"_id": result.inserted_id})
    created["_id"] = str(created["_id"])
    return created

@app.get("/products")
async def list_products(
    category: Optional[str] = None,
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
    tag: Optional[str] = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=100),
    collection=Depends(get_products_collection)
):
    # Dynamic filter build karo
    filter_query = {"is_active": True}
    
    if category:
        filter_query["category"] = category
    if min_price is not None or max_price is not None:
        filter_query["price"] = {}
        if min_price is not None:
            filter_query["price"]["$gte"] = min_price
        if max_price is not None:
            filter_query["price"]["$lte"] = max_price
    if tag:
        filter_query["tags"] = tag  # Array contains check
    
    # Pagination calculate karo
    skip = (page - 1) * page_size
    
    # Total count aur data simultaneously fetch karo
    total = await collection.count_documents(filter_query)
    products = await collection.find(
        filter_query,
        projection={"__v": 0}  # Internal fields exclude karo
    ).sort("created_at", -1).skip(skip).limit(page_size).to_list(length=page_size)
    
    # ObjectId → str convert karo
    for p in products:
        p["_id"] = str(p["_id"])
    
    return {
        "data": products,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size
    }

@app.get("/products/{product_id}")
async def get_product(
    product_id: str,
    collection=Depends(get_products_collection)
):
    if not ObjectId.is_valid(product_id):
        raise HTTPException(status_code=400, detail="Invalid product ID format")
    
    product = await collection.find_one({"_id": ObjectId(product_id)})
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    
    product["_id"] = str(product["_id"])
    return product

@app.put("/products/{product_id}")
async def update_product(
    product_id: str,
    update_data: ProductUpdate,
    collection=Depends(get_products_collection)
):
    if not ObjectId.is_valid(product_id):
        raise HTTPException(status_code=400, detail="Invalid product ID")
    
    # Sirf provided fields update karo (partial update)
    update_dict = {k: v for k, v in update_data.model_dump().items() if v is not None}
    if not update_dict:
        raise HTTPException(status_code=400, detail="No fields to update")
    
    update_dict["updated_at"] = datetime.utcnow()
    
    result = await collection.update_one(
        {"_id": ObjectId(product_id)},
        {"$set": update_dict}
    )
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Product not found")
    
    updated = await collection.find_one({"_id": ObjectId(product_id)})
    updated["_id"] = str(updated["_id"])
    return updated

@app.delete("/products/{product_id}", status_code=204)
async def delete_product(
    product_id: str,
    collection=Depends(get_products_collection)
):
    """Soft delete — is_active=False karo, actual delete mat karo"""
    if not ObjectId.is_valid(product_id):
        raise HTTPException(status_code=400, detail="Invalid product ID")
    
    result = await collection.update_one(
        {"_id": ObjectId(product_id)},
        {"$set": {"is_active": False, "deleted_at": datetime.utcnow()}}
    )
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Product not found")
    
    return None  # 204 No Content

@app.post("/products/bulk", status_code=201)
async def bulk_create_products(
    products: List[ProductCreate],
    collection=Depends(get_products_collection)
):
    if not products:
        raise HTTPException(status_code=400, detail="Empty product list")
    
    docs = []
    for p in products:
        doc = p.model_dump()
        doc["is_active"] = True
        doc["created_at"] = datetime.utcnow()
        docs.append(doc)
    
    result = await collection.insert_many(docs)
    return {
        "inserted_count": len(result.inserted_ids),
        "ids": [str(id) for id in result.inserted_ids]
    }
```

### 📄 Cursor-Based Pagination (Advanced)

```python
# Skip/Limit pagination → large offsets pe slow ho jaata hai
# Cursor-based pagination → consistent performance

@app.get("/products/cursor-paginate")
async def cursor_pagination(
    last_id: Optional[str] = None,  # Last fetched document ka ID
    limit: int = Query(default=10, le=100),
    collection=Depends(get_products_collection)
):
    filter_query = {"is_active": True}
    
    # Agar last_id diya hai, toh uske baad ke documents fetch karo
    if last_id and ObjectId.is_valid(last_id):
        filter_query["_id"] = {"$gt": ObjectId(last_id)}
    
    products = await collection.find(filter_query).limit(limit).to_list(length=limit)
    
    for p in products:
        p["_id"] = str(p["_id"])
    
    next_cursor = products[-1]["_id"] if len(products) == limit else None
    
    return {
        "data": products,
        "next_cursor": next_cursor,
        "has_more": next_cursor is not None
    }
```

---

## 6. FastAPI + Beanie Integration

### 🚀 Beanie with FastAPI Lifespan

```python
from beanie import init_beanie
from motor.motor_asyncio import AsyncIOMotorClient
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    client = AsyncIOMotorClient(MONGO_URI, maxPoolSize=50)
    
    await init_beanie(
        database=client.practice_db,
        document_models=[Product, User, Order]
    )
    print("✅ Beanie initialized!")
    
    app.state.motor_client = client  # Client store karo future use ke liye
    
    yield
    
    # Shutdown
    client.close()

app = FastAPI(lifespan=lifespan)
```

### 🛣️ Beanie Route Handlers

```python
@app.post("/products", response_model=Product, status_code=201)
async def create_product_beanie(product_data: ProductCreate):
    product = Product(**product_data.model_dump())
    await product.insert()
    return product  # Beanie Document directly return ho sakta hai

@app.get("/products/{product_id}", response_model=Product)
async def get_product_beanie(product_id: str):
    try:
        pid = PydanticObjectId(product_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid ObjectId")
    
    product = await Product.get(pid)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return product

@app.put("/products/{product_id}", response_model=Product)
async def update_product_beanie(product_id: str, update_data: ProductUpdate):
    product = await Product.get(PydanticObjectId(product_id))
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    
    # Partial update — sirf provided fields
    update_dict = update_data.model_dump(exclude_unset=True)
    if update_dict:
        from beanie.operators import Set
        await product.update(Set(update_dict))
    
    return product

# Beanie ODM-level validation vs Manual validation comparison:
# 
# Beanie ODM validation:
# - Pydantic field types automatically check hote hain
# - Custom validators @field_validator likhe ja sakte hain
# - Indexes automatically enforce uniqueness
# 
# Manual validation (Motor direct):
# - Aapko khud check karna padta hai har cheez
# - More control, more code
# - Custom business logic ke liye sometimes zaroori
```

---

## 7. Multi-Document Transactions

### ⚠️ Pre-requisite: Replica Set Zaroori!
MongoDB transactions **sirf Replica Set ya Sharded Cluster** mein kaam karte hain. Standalone MongoDB instance mein transactions **support nahin hain**.

> **Kyun?** Transactions ke liye MongoDB ko oplog (operations log) chahiye hota hai — jo sirf Replica Sets maintain karte hain. Oplog se transaction rollback possible hota hai.

### 🔄 Basic Transaction Pattern

```python
async def create_order_with_transaction(
    client: AsyncIOMotorClient,
    user_id: str,
    product_id: str,
    quantity: int
):
    """
    Order creation transaction:
    1. Check stock availability
    2. Create order document
    3. Decrement product stock
    All atomically — ya saab hoga ya kuch nahin
    """
    orders = client.practice_db.orders
    inventory = client.practice_db.products
    
    async with await client.start_session() as session:
        async with session.start_transaction():
            # Step 1: Stock check karo
            product = await inventory.find_one(
                {"_id": ObjectId(product_id)},
                session=session
            )
            if not product:
                raise ValueError("Product not found")
            if product["stock"] < quantity:
                raise ValueError(f"Insufficient stock: {product['stock']} available")
            
            # Step 2: Order create karo
            order_doc = {
                "user_id": ObjectId(user_id),
                "product_id": ObjectId(product_id),
                "quantity": quantity,
                "total_price": product["price"] * quantity,
                "status": "completed",
                "created_at": datetime.utcnow()
            }
            await orders.insert_one(order_doc, session=session)
            
            # Step 3: Stock decrement karo
            await inventory.update_one(
                {"_id": ObjectId(product_id)},
                {"$inc": {"stock": -quantity}},
                session=session
            )
            
            # async with block se bahar aane pe auto-commit hoga
            # Exception aane pe auto-abort hoga (rollback)
            
            return str(order_doc["_id"])
```

### 🔁 with_transaction — Auto-retry Pattern

```python
from pymongo.errors import TransientTransactionError, UnknownTransactionCommitResult

async def reliable_order_creation(client, user_id, product_id, quantity):
    """
    with_transaction() — transient errors pe automatically retry karta hai
    (network hiccup, write conflict, etc.)
    """
    
    async def transaction_body(session):
        """Yeh function retry ho sakta hai, toh idempotent hona chahiye"""
        orders = client.practice_db.orders
        inventory = client.practice_db.products
        
        product = await inventory.find_one(
            {"_id": ObjectId(product_id)},
            session=session
        )
        if not product or product["stock"] < quantity:
            raise Exception("Insufficient stock")
        
        await orders.insert_one({
            "user_id": ObjectId(user_id),
            "product_id": ObjectId(product_id),
            "quantity": quantity,
            "total_price": product["price"] * quantity,
            "status": "pending",
            "created_at": datetime.utcnow()
        }, session=session)
        
        await inventory.update_one(
            {"_id": ObjectId(product_id)},
            {"$inc": {"stock": -quantity}},
            session=session
        )
    
    async with await client.start_session() as session:
        await session.with_transaction(
            transaction_body,
            # Optional: custom read/write concern
            # read_concern=ReadConcern("snapshot"),
            # write_concern=WriteConcern("majority")
        )

# Error types:
# TransientTransactionError — temporary failure, retry karo (network issue, write conflict)
# UnknownTransactionCommitResult — commit ka result unknown, idempotently retry karo
```

### 📋 Transaction Rules
1. **4 minute maximum** — transactions 4 min se zyada nahi chal sakte
2. **16MB document limit** — transaction ke andar 16MB se zyada data nahin likh sakte
3. **Replica Set required** — standalone MongoDB pe transactions fail honge
4. **Performance cost** — transactions overhead add karte hain, sirf zaroori ho tab use karo

---

## 8. Change Streams

### 🔔 Change Streams kya hain?
Change Streams MongoDB ka **real-time notification system** hai. Aap ek collection (ya database ya client) par "watch" laga sakte ho — jab bhi koi document change ho, aapko event milega.

> **Use cases:** Real-time dashboard, cache invalidation, audit logs, event-driven microservices, websocket push notifications

```python
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient

async def change_stream_demo(client: AsyncIOMotorClient):
    """
    Requires replica set! 
    
    Setup:
    docker run -d --name mongo-rs -p 27017:27017 mongo:7.0 --replSet rs0
    docker exec mongo-rs mongosh --eval "rs.initiate()"
    """
    products = client.practice_db.products
    
    # Basic change stream — saare changes watch karo
    async with products.watch() as stream:
        async for change in stream:
            op = change["operationType"]
            
            if op == "insert":
                print(f"New product added: {change['fullDocument']['name']}")
            elif op == "update":
                print(f"Product updated: {change['documentKey']['_id']}")
                print(f"Changes: {change['updateDescription']['updatedFields']}")
            elif op == "delete":
                print(f"Product deleted: {change['documentKey']['_id']}")
            elif op == "replace":
                print(f"Product replaced: {change['fullDocument']}")
```

### 🔍 Change Stream with Filter Pipeline

```python
async def filtered_change_stream(client: AsyncIOMotorClient):
    products = client.practice_db.products
    
    # Sirf insert events ka filter
    pipeline = [
        {
            "$match": {
                "operationType": {"$in": ["insert", "update"]},
                # Sirf electronics category ke changes
                "fullDocument.category": "electronics"  
            }
        },
        {
            "$project": {
                "operationType": 1,
                "fullDocument.name": 1,
                "fullDocument.price": 1
            }
        }
    ]
    
    # Update mein fullDocument chahiye → updateLookup
    async with products.watch(
        pipeline,
        full_document="updateLookup"  # Update pe bhi full document milega
    ) as stream:
        async for change in stream:
            print(f"Change: {change}")
```

### 🔄 Resilient Change Stream (Resume After Failure)

```python
async def resilient_change_stream(client: AsyncIOMotorClient):
    """
    Application restart ke baad change stream resume karo
    — missed events nahin jayenge
    """
    products = client.practice_db.products
    
    # Pehle se saved resume token load karo
    resume_token = load_resume_token_from_db()  # apni logic
    
    options = {}
    if resume_token:
        options["resume_after"] = resume_token  # Resume from last position
        # OR: options["start_after"] = resume_token
    
    try:
        async with products.watch(**options) as stream:
            async for change in stream:
                # Process the change
                process_change(change)
                
                # Resume token save karo (har change ke baad)
                save_resume_token(stream.resume_token)
                
    except Exception as e:
        print(f"Stream error: {e}")
        # Reconnect aur resume karo

# Change event structure:
# {
#   "_id": { ... },                  # Resume token
#   "operationType": "insert",       # insert/update/replace/delete/invalidate
#   "fullDocument": { ... },         # Document ka new state
#   "documentKey": { "_id": ... },   # Affected document ka _id
#   "ns": { "db": "...", "coll": "..." },  # Namespace
#   "updateDescription": {           # Sirf update pe
#     "updatedFields": { ... },
#     "removedFields": [ ... ]
#   }
# }
```

### 🌍 Change Stream Scope Options

```python
# Option 1: Specific collection watch karo
collection_stream = collection.watch()

# Option 2: Poora database watch karo
db_stream = client.practice_db.watch()

# Option 3: Poora client (all databases) watch karo
client_stream = client.watch()
```

---

## 9. Replica Sets

### 🔄 Replica Set kya hai?
**Replica Set** MongoDB ka high-availability solution hai. Ek primary node + 1+ secondary nodes milke ek replica set banate hain. Primary pe writes hoti hain, secondaries automatically sync karte hain.

```
      Client
        │
        ▼
   ┌─────────┐
   │ PRIMARY │  ← Writes + Reads (by default)
   └─────────┘
        │ (oplog replication)
   ┌────┴────┐
   ▼         ▼
┌─────────┐ ┌─────────┐
│SECONDARY│ │SECONDARY│  ← Read scaling possible
└─────────┘ └─────────┘
```

**Kyun zaroori hai:**
- ✅ Transactions (ACID guarantees ke liye oplog chahiye)
- ✅ Change Streams (oplog-based hai)
- ✅ High availability (primary fail ho to secondary promote hota hai)
- ✅ Read scaling (secondaries se read karo)

### 🐳 Single-Node Replica Set Setup (Development)

```bash
# Single node replica set banao (transactions + change streams ke liye)
docker run -d \
  --name mongo-rs \
  -p 27017:27017 \
  -e MONGO_INITDB_ROOT_USERNAME=admin \
  -e MONGO_INITDB_ROOT_PASSWORD=secret \
  mongo:7.0 \
  --replSet rs0 \
  --bind_ip_all

# Replica set initiate karo (sirf pehli baar)
docker exec mongo-rs mongosh \
  -u admin -p secret \
  --authenticationDatabase admin \
  --eval "rs.initiate({_id: 'rs0', members: [{_id: 0, host: 'localhost:27017'}]})"

# Verify
docker exec mongo-rs mongosh \
  -u admin -p secret \
  --authenticationDatabase admin \
  --eval "rs.status()"
```

### 🔗 Motor with Replica Set URI

```python
# Replica set URI format
MONGO_URI = "mongodb://admin:secret@localhost:27017/practice_db?authSource=admin&replicaSet=rs0"

client = AsyncIOMotorClient(
    MONGO_URI,
    replicaSet="rs0",       # Replica set naam
    readPreference="secondaryPreferred",  # Reads secondary se karo (optional)
    w="majority",           # Write concern — majority nodes ko ack
    j=True                  # Journal write confirm
)
```

---

## 10. Sharding Basics

### 📊 Sharding kya hai?
**Sharding** MongoDB ka **horizontal scaling** solution hai. Data ko multiple servers (shards) mein distribute kiya jaata hai based on a **shard key**.

```
           Client
              │
              ▼
         ┌──────────┐
         │  mongos  │  ← Query Router
         │ (router) │
         └──────────┘
         /     |     \
        /      |      \
   Shard 1  Shard 2  Shard 3
 user_id:   user_id:  user_id:
  0-1000   1001-2000  2001-3000
```

### 🗝️ Shard Key Selection — Most Important Decision!

```javascript
// ❌ BAD shard key examples:
// Monotonically increasing (all writes go to one shard)
sh.shardCollection("db.orders", { "created_at": 1 })

// Low cardinality (too few distinct values → uneven distribution)
sh.shardCollection("db.products", { "is_active": 1 })

// ✅ GOOD shard key examples:
// High cardinality + even distribution
sh.shardCollection("db.users", { "user_id": "hashed" })   // Hashed sharding

// Compound shard key
sh.shardCollection("db.orders", { "user_id": 1, "created_at": 1 })
```

### 📋 Hashed vs Ranged Sharding

| Feature | Hashed Sharding | Ranged Sharding |
|---------|----------------|-----------------|
| Distribution | Uniform (even) | Based on value ranges |
| Range queries | ❌ Scatter-gather | ✅ Efficient |
| Monotonic keys | ✅ Works well | ❌ Hotspots possible |
| Use case | Write-heavy, uniform access | Range queries, time-series |

### ⏰ When to Shard?
- Data > 1 TB per collection
- Write throughput > single server capacity
- Working set > available RAM
- Need geographic distribution

> **Interview tip:** Sharding adds operational complexity. Pehle vertical scaling (bigger machine) try karo, phir read replicas, phir sharding as last resort.

---

## 11. GridFS

### 📁 GridFS kya hai?
MongoDB documents **maximum 16MB** tak ho sakte hain. Isse bade files store karne ke liye **GridFS** use karo. GridFS file ko **255KB chunks** mein divide karta hai aur do collections mein store karta hai:
- `fs.files` — file metadata (name, size, upload date, etc.)
- `fs.chunks` — actual binary data chunks

### 📤 Motor se GridFS Operations

```python
import asyncio
import motor.motor_asyncio
from motor.motor_asyncio import AsyncIOMotorGridFSBucket

async def gridfs_demo():
    client = motor.motor_asyncio.AsyncIOMotorClient(MONGO_URI)
    db = client.practice_db
    
    # GridFS bucket create karo
    bucket = AsyncIOMotorGridFSBucket(db)
    # Custom bucket name
    # bucket = AsyncIOMotorGridFSBucket(db, bucket_name="product_images")
    
    # ===== FILE UPLOAD =====
    
    # Bytes se upload karo
    file_data = b"This is a large file content..." * 1000  # 30KB
    
    file_id = await bucket.upload_from_stream(
        "product_image.jpg",        # Filename
        file_data,                  # File content (bytes ya async generator)
        chunk_size_bytes=255 * 1024,  # 255KB chunks (default)
        metadata={                  # Custom metadata
            "product_id": "64a7b2c3",
            "content_type": "image/jpeg",
            "uploaded_by": "admin"
        }
    )
    print(f"File uploaded with ID: {file_id}")
    
    # File path se upload karo
    with open("/path/to/large_video.mp4", "rb") as f:
        video_id = await bucket.upload_from_stream("product_video.mp4", f)
    
    # ===== FILE DOWNLOAD =====
    
    # By ID download karo
    grid_out = await bucket.open_download_stream(file_id)
    file_bytes = await grid_out.read()
    
    # By name download karo (latest version)
    grid_out = await bucket.open_download_stream_by_name("product_image.jpg")
    
    # Stream to file
    with open("/tmp/downloaded.jpg", "wb") as f:
        await bucket.download_to_stream_by_name("product_image.jpg", f)
    
    # ===== FILE METADATA =====
    
    # Find files
    async for grid_in in bucket.find({"metadata.product_id": "64a7b2c3"}):
        print(f"File: {grid_in.filename}, Size: {grid_in.length} bytes")
    
    # ===== FILE DELETE =====
    await bucket.delete(file_id)

# FastAPI endpoint for file upload
from fastapi import UploadFile, File

@app.post("/products/{product_id}/image")
async def upload_product_image(
    product_id: str,
    image: UploadFile = File(...)
):
    client = motor_client  # Global client from lifespan
    bucket = AsyncIOMotorGridFSBucket(client.practice_db)
    
    contents = await image.read()
    file_id = await bucket.upload_from_stream(
        image.filename,
        contents,
        metadata={"product_id": product_id, "content_type": image.content_type}
    )
    
    return {"file_id": str(file_id), "filename": image.filename}
```

### 📋 GridFS vs Direct Storage Comparison

| Aspect | GridFS | Object Storage (S3/GCS) |
|--------|--------|------------------------|
| Setup | Simple (same MongoDB) | Separate service |
| Performance | Good for files <5GB | Better for large files |
| CDN support | ❌ | ✅ |
| Cost | MongoDB storage cost | Separate pricing |
| Replication | With MongoDB replica | Separate |
| Use case | Internal files, small apps | Production, high traffic |

---

## 12. Atlas Search (Mention)

### 🔍 Atlas Search kya hai?
**MongoDB Atlas Search** ek **full-text search engine** hai jo Atlas (MongoDB's managed cloud service) mein built-in hai. Apache Lucene pe based hai.

```python
# Atlas Search aggregation pipeline
pipeline = [
    {
        "$search": {
            "index": "products_search_index",  # Atlas Search index naam
            "compound": {
                "must": [
                    {
                        "text": {
                            "query": "gaming laptop",
                            "path": ["name", "description"],
                            "fuzzy": {"maxEdits": 1}  # Typo tolerance
                        }
                    }
                ],
                "should": [
                    {
                        "range": {
                            "path": "price",
                            "lte": 50000
                        }
                    }
                ]
            }
        }
    },
    {"$limit": 10},
    {"$project": {"name": 1, "price": 1, "score": {"$meta": "searchScore"}}}
]

# Autocomplete
search_pipeline = [
    {
        "$search": {
            "index": "products_search_index",
            "autocomplete": {
                "query": "lapt",
                "path": "name",
                "fuzzy": {"maxEdits": 1}
            }
        }
    },
    {"$limit": 5}
]
```

### Atlas Search vs Elasticsearch

| Feature | Atlas Search | Elasticsearch |
|---------|-------------|---------------|
| Setup | Atlas cluster mein built-in | Separate service |
| Data sync | Automatic (same MongoDB) | Manual ETL needed |
| Performance | Good | Excellent |
| Cost | Atlas pricing | Separate EC2 + ELK stack |
| Lucene | ✅ (under the hood) | ✅ |
| Use case | MongoDB + search needed | Dedicated search platform |

---

## 13. Performance Best Practices

### 📊 Comprehensive Tips Table

| Tip | Reason | Example |
|-----|--------|---------|
| **Use projection** | Network transfer kam karo — sirf needed fields lao | `.find({}, {"name": 1, "price": 1, "_id": 0})` |
| **Index on query fields** | COLLSCAN avoid karo — index scan much faster | `IndexModel([("category", ASCENDING)])` |
| **$match early in pipeline** | Subsequent stages mein kam documents process ho | `[{"$match": {...}}, {"$group": {...}}]` |
| **Avoid $where** | JavaScript engine use karta hai — 10x+ slow | Use `$expr` instead |
| **Use bulk_write** | Fewer network round trips | `await collection.bulk_write([...])` |
| **Connection pool sizing** | Workload concurrency match karo | `maxPoolSize=50` for high-concurrency API |
| **Avoid large arrays in docs** | 16MB limit + update performance degrades | Separate collection use karo |
| **TTL index for expiry** | Automatic cleanup — manual deletion avoid karo | `IndexModel([("expires_at", 1)], expireAfterSeconds=0)` |
| **Use covered queries** | All fields in index → document fetch skip | Project only indexed fields |
| **$lookup sparingly** | Application-side join consider karo | Embed related data where possible |
| **Compound indexes** | Multiple field queries efficiently serve karo | `[("category", 1), ("price", -1)]` |
| **explain() regularly** | Query execution plan analyze karo | `await collection.find({}).explain()` |
| **WiredTiger cache** | RAM = 50% of system RAM (default) | Production pe tune karo |
| **Avoid unbounded to_list()** | Memory exhaustion possible | `to_list(length=1000)` always |

### 🔍 Query Analysis

```python
# Explain plan — query performance analyze karo
async def analyze_query():
    explain = await products.find(
        {"category": "electronics", "price": {"$lt": 10000}}
    ).explain()
    
    # "COLLSCAN" → No index, bad!
    # "IXSCAN"  → Index scan, good!
    winning_plan = explain["queryPlanner"]["winningPlan"]
    print(winning_plan["stage"])  # IXSCAN ya COLLSCAN
```

---

## 14. Interview Q&A

### Q1: Motor vs PyMongo — kab kya use karein?

**Answer:**
> "Motor use karo jab aap **async framework** use kar rahe ho — FastAPI, Starlette, aiohttp. PyMongo use karo **sync contexts** mein — Flask, Django (bina async ke), scripts, data pipelines. Motor ko FastAPI mein use karna zaroori hai kyunki PyMongo async event loop ko **block** kar deta hai — ek database call hote waqt koi aur request process nahin ho sakti."

```python
# ❌ PyMongo in FastAPI — event loop block ho jaata hai
@app.get("/products")
async def get_products():
    products = list(pymongo_collection.find({}))  # BLOCKS! Bad!
    return products

# ✅ Motor in FastAPI — non-blocking
@app.get("/products")
async def get_products():
    products = await motor_collection.find({}).to_list(length=100)  # Good!
    return products
```

---

### Q2: Beanie kab use karein aur kab Motor directly?

**Answer:**
> "**Beanie** use karo jab aapko clean ORM-style code chahiye ho, Pydantic validation chahiye, ya codebase maintainable rakhna ho. **Motor directly** use karo jab complex aggregation pipelines ho, maximum performance chahiye, ya Beanie ka overhead acceptable nahi ho. Production mein usually hybrid approach: standard CRUD ke liye Beanie, complex analytics ke liye raw Motor aggregation."

---

### Q3: ObjectId ko JSON API mein kaise handle karein?

**Answer:**
> "ObjectId directly JSON serializable nahin hai. Teen approaches hain:
> 1. **Pydantic model mein** `str` type ya custom `PyObjectId` use karo
> 2. **FastAPI's JSONResponse** mein custom encoder — `json_encoders = {ObjectId: str}`
> 3. **Beanie** automatically handle karta hai via `PydanticObjectId`"

```python
# Approach 1: Pydantic v2
class ProductResponse(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    id: str = Field(alias="_id")
    
    @field_validator("id", mode="before")
    def convert_objectid(cls, v):
        return str(v) if isinstance(v, ObjectId) else v

# Approach 2: FastAPI custom encoder
from fastapi.encoders import jsonable_encoder

@app.get("/products")
async def get_products():
    products = await collection.find({}).to_list(100)
    return jsonable_encoder(products, custom_encoder={ObjectId: str})
```

---

### Q4: Change Streams ka real-world use case kya hai?

**Answer:**
> "Production mein change streams ke 3 main use cases hain:
> 1. **Real-time notifications** — user ke orders ka status change ho to WebSocket se frontend ko push karo
> 2. **Cache invalidation** — product price update ho to Redis cache clear karo automatically  
> 3. **Audit logs** — compliance ke liye har document change track karo, separate audit_logs collection mein"

```python
# Real-time cache invalidation example
async def cache_invalidation_watcher(client, redis_client):
    products = client.practice_db.products
    
    async with products.watch([{"$match": {"operationType": {"$in": ["update", "replace"]}}}]) as stream:
        async for change in stream:
            product_id = str(change["documentKey"]["_id"])
            # Redis cache invalidate karo
            await redis_client.delete(f"product:{product_id}")
            print(f"Cache invalidated for product: {product_id}")
```

---

### Q5: Transactions ke liye Replica Set kyun chahiye?

**Answer:**
> "MongoDB transactions **oplog** (operations log) pe depend karte hain. Oplog replica set ka part hai — har write operation atomically oplog mein record hoti hai. Transaction rollback ke liye MongoDB ko oplog se previous state restore karna hota hai. Standalone MongoDB oplog maintain nahin karta, isliye transactions support nahin karta. Development mein single-node replica set (`--replSet rs0`) setup karo."

---

### Q6: GridFS vs Direct File Storage — kab kya choose karein?

**Answer:**
> "**GridFS** simple apps ke liye theek hai jahan MongoDB already use ho. But production mein **S3 ya GCS** recommend karta hoon kyunki: CDN support milti hai, direct streaming possible hai, aur cost-effective hai. GridFS ka biggest advantage: MongoDB ke saath atomic operations — file upload aur document update ek transaction mein. Agar files >5GB ho to always object storage."

---

### Q7: Shard key kaise choose karein?

**Answer:**
> "Shard key selection most critical MongoDB design decision hai. Criteria:
> 1. **High cardinality** — bahut unique values (user_id achha, is_active bura)
> 2. **Even write distribution** — monotonic values (timestamps) avoid karo
> 3. **Query isolation** — common query patterns shard key mein ho to single shard query possible
> 4. **Immutable** — shard key update nahin ho sakta
>
> Best practice: hashed shard key on `_id` write-heavy apps ke liye; compound key range queries ke liye."

---

### Q8: Motor connection pool FastAPI mein kaise manage karein?

**Answer:**
> "**Lifespan context manager** mein ek baar client banao — application startup pe. Client pool maintain karta hai. Har request mein **naya client mat banao** — yeh expensive hai aur pool ka fayda nahin. Client ko app state ya global variable mein store karo, dependency injection se routes ko do."

```python
# ✅ Correct: Global client, reuse karo
@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.motor_client = AsyncIOMotorClient(MONGO_URI, maxPoolSize=50)
    await init_beanie(database=app.state.motor_client.practice_db, document_models=[...])
    yield
    app.state.motor_client.close()

# Dependency
async def get_db(request: Request):
    return request.app.state.motor_client.practice_db
```

---

### Q9: Pydantic v2 ke saath Beanie kaise kaam karta hai?

**Answer:**
> "Beanie v1.20+ Pydantic v2 ko support karta hai. Key changes:
> 1. `class Config` ki jagah `model_config = ConfigDict(...)` use karo
> 2. `@validator` ki jagah `@field_validator` use karo
> 3. `.dict()` deprecated — `.model_dump()` use karo
> 4. PydanticObjectId Pydantic v2 compatible hai Beanie v1.20+ mein"

---

### Q10: Async cursor iteration ka sahi pattern kya hai?

**Answer:**
> "Motor mein `find()` cursor return karta hai — awaitable nahin. Do patterns hain:
> 1. `async for doc in collection.find(filter):` — memory efficient, large collections ke liye
> 2. `await collection.find(filter).to_list(length=N)` — fast, saara data ek baar mein
>
> **Gotcha:** `to_list(length=None)` entire collection load kar sakta hai — **always limit do!**"

---

### Q11: Transaction retry pattern kya hai?

**Answer:**
> "MongoDB transient errors pe `with_transaction()` use karo — yeh automatically retry karta hai `TransientTransactionError` pe. Important: transaction body **idempotent** hona chahiye — agar retry ho to duplicate side effects nahin hone chahiye. Duplicate prevention ke liye unique fields ya idempotency keys use karo."

---

### Q12: $lookup vs Application-Level Join — kab kya?

**Answer:**
> "**$lookup** (server-side join) tab use karo jab:
> - Data same MongoDB instance mein hai
> - Complex filtering joined data pe chahiye
> - Network round trips minimize karne ho
>
> **Application-level join** tab use karo jab:
> - Documents alag databases/services mein hain
> - Caching possible ho (user data frequently needed)
> - Microservices architecture mein
>
> Performance: $lookup pipeline pe indexing zaroori hai; large collections pe slow ho sakta hai."

---

### Q13: Motor vs SQLAlchemy async — kab kya?

**Answer:**
> "**Motor** choose karo jab:
> - Flexible schema chahiye (product catalog with varying attributes)
> - Horizontal scaling required (sharding)
> - Document-oriented data model fit hota ho
> - JSON-heavy APIs
>
> **SQLAlchemy async** choose karo jab:
> - Complex relational queries + JOINs bahut hain
> - ACID transactions across multiple tables
> - Strong consistency zaroor chahiye
> - Financial/transactional data
>
> Ek hi application mein dono ho sakte hain — MongoDB analytics ke liye, PostgreSQL transactions ke liye."

---

### Q14: Motor connection lifecycle FastAPI lifespan mein explain karo

**Answer:**
> "Lifecycle:
> 1. **App startup** → `AsyncIOMotorClient()` banao — pool create hota hai (min connections)
> 2. **Request aaye** → Pool se connection liya jaata hai (available ho to), ya naya banaya jaata hai (maxPoolSize tak)
> 3. **Request complete** → Connection pool mein wapas diya jaata hai
> 4. **App shutdown** → `client.close()` — saare connections gracefully close ho jaate hain
>
> Key: Client object `application-scoped` hai, connections `request-scoped` hain."

```
Application Lifecycle:
Startup → [Create Pool] → [minPoolSize connections ready]
                                        │
Request 1 → [Borrow connection] ────────┤
Request 2 → [Borrow connection] ────────┤
...                                     │
Request N → [Borrow connection] ────────┤ (up to maxPoolSize)
                                        │
Response → [Return to pool] ────────────┤
                                        │
Shutdown → [client.close()] → [All connections closed]
```

---

## 📚 Quick Reference Cheatsheet

```python
# Motor imports
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorGridFSBucket

# Beanie imports  
from beanie import Document, Link, BackLink, init_beanie, PydanticObjectId
from beanie import before_event, after_event, Insert, Save, Delete
from beanie.operators import Set, Inc, Push, Pull, AddToSet

# Common patterns
await collection.find_one(filter)                    # Single doc
await collection.find(filter).to_list(length=100)   # Multiple docs
async for doc in collection.find(filter): ...        # Stream docs
await collection.insert_one(doc)                     # Insert
await collection.update_one(filter, {"$set": data}) # Update
await collection.delete_one(filter)                  # Delete
await collection.count_documents(filter)             # Count
await collection.aggregate(pipeline).to_list(None)  # Aggregate

# Beanie patterns
await MyDoc.insert()                    # Insert
await MyDoc.get(id)                     # Get by ID
await MyDoc.find(MyDoc.field == val).to_list()  # Query
await doc.save()                        # Save/Update
await doc.delete()                      # Delete
await doc.update(Set({MyDoc.field: val}))  # Partial update
```

---

*Interview Prep Series | Python Backend + Agentic AI | 20 LPA Target*  
*Next: 04_aggregation_advanced.md → Complex pipelines, $facet, $bucket, time-series*
