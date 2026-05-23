"""
MongoDB PyMongo Basics — Production-Quality Practice File
==========================================================
Target: 5 YOE Python Backend + Agentic AI | 20 LPA
Topics: Connection, CRUD, Bulk Write, explain(), Aggregation, Motor (Async)

Usage:
    python 01_pymongo_basics.py                    # Run all demos
    python 01_pymongo_basics.py connection         # Only connection demo
    python 01_pymongo_basics.py insert             # Only insert demo
    python 01_pymongo_basics.py find               # Only find demo
    python 01_pymongo_basics.py update             # Only update demo
    python 01_pymongo_basics.py delete             # Only delete demo
    python 01_pymongo_basics.py bulk               # Only bulk_write demo
    python 01_pymongo_basics.py explain            # Only explain/index demo
    python 01_pymongo_basics.py aggregation        # Only aggregation demo
    python 01_pymongo_basics.py motor              # Only async motor demo

Docker Setup:
    docker run -d --name mongodb -p 27017:27017 \
      -e MONGO_INITDB_ROOT_USERNAME=admin \
      -e MONGO_INITDB_ROOT_PASSWORD=secret \
      mongo:7.0
"""

import os
import sys
import time
import asyncio
import random
import re
from datetime import datetime, timezone
from typing import Optional

# ── DEPENDENCIES CHECK ──
try:
    from pymongo import (
        MongoClient,
        ASCENDING,
        DESCENDING,
        InsertOne,
        UpdateOne,
        UpdateMany,
        DeleteOne,
        DeleteMany,
        ReplaceOne,
    )
    from pymongo.errors import (
        ConnectionFailure,
        ServerSelectionTimeoutError,
        BulkWriteError,
        OperationFailure,
    )
    from pymongo import ReturnDocument
    from bson import ObjectId
    from bson.decimal128 import Decimal128
    from bson.errors import InvalidId
except ImportError:
    print("ERROR: pymongo not installed. Run: pip install pymongo")
    sys.exit(1)

try:
    import motor.motor_asyncio
    MOTOR_AVAILABLE = True
except ImportError:
    MOTOR_AVAILABLE = False
    print("WARNING: motor not installed. Async demo will be skipped. Run: pip install motor")

# ── CONFIGURATION ──
MONGO_URI = os.getenv(
    "MONGO_URI",
    "mongodb://admin:secret@localhost:27017/practice_db?authSource=admin"
)
DB_NAME = "practice_db"
SEPARATOR = "=" * 65


# ── HELPER FUNCTIONS ──

def print_section(title: str) -> None:
    """Section header print karo with visual separator."""
    print(f"\n{SEPARATOR}")
    print(f"  {title}")
    print(SEPARATOR)


def print_doc(doc: dict, label: str = "Document") -> None:
    """Single document nicely print karo."""
    if doc is None:
        print(f"  {label}: None (not found)")
        return
    # _id ko string mein convert karo readability ke liye
    display = {k: (str(v) if isinstance(v, ObjectId) else v) for k, v in doc.items()}
    print(f"  {label}: {display}")


def get_client() -> MongoClient:
    """
    MongoClient create karo with production-ready settings.
    Connection pool automatically manage hota hai — ek instance kaafi hai.
    """
    return MongoClient(
        MONGO_URI,
        serverSelectionTimeoutMS=5000,
        connectTimeoutMS=10000,
        socketTimeoutMS=45000,
        maxPoolSize=50,
        minPoolSize=5,
        retryWrites=True,
        retryReads=True,
    )


def check_connection(client: MongoClient) -> bool:
    """Ping karke verify karo ki MongoDB available hai."""
    try:
        client.admin.command("ping")
        return True
    except (ConnectionFailure, ServerSelectionTimeoutError):
        return False


def clear_collection(db, collection_name: str) -> None:
    """Collection drop karke fresh start karo."""
    db.drop_collection(collection_name)


def build_sample_products(count: int = 20) -> list[dict]:
    """
    Sample products generate karo — realistic data with all BSON types.
    3 categories: electronics, clothing, books
    """
    categories = ["electronics", "clothing", "books"]
    electronics = [
        ("Laptop Pro X1", 85000, {"ram": "16GB", "storage": "512GB SSD", "display": "15.6 FHD"}),
        ("Wireless Mouse", 599, {"dpi": 1600, "connectivity": "USB-C", "battery": "AA"}),
        ("Mechanical Keyboard", 3500, {"switches": "Cherry MX Red", "layout": "TKL", "backlit": True}),
        ("4K Monitor", 28000, {"resolution": "3840x2160", "panel": "IPS", "hz": 60}),
        ("USB-C Hub", 1299, {"ports": 7, "usb3": 4, "hdmi": 1}),
        ("SSD 1TB", 6500, {"interface": "NVMe", "read_speed": "3500 MB/s", "write_speed": "3000 MB/s"}),
        ("Noise-Cancelling Headphones", 12000, {"driver": "40mm", "battery": "30h", "anc": True}),
    ]
    clothing = [
        ("Cotton T-Shirt", 299, {"material": "100% Cotton", "fit": "Regular"}),
        ("Denim Jeans", 1299, {"material": "Denim", "fit": "Slim"}),
        ("Running Shoes", 2499, {"sole": "EVA Foam", "upper": "Mesh"}),
        ("Hoodie", 899, {"material": "80% Cotton 20% Poly", "style": "Pullover"}),
        ("Formal Shirt", 699, {"material": "Poly-Cotton", "collar": "Regular"}),
        ("Winter Jacket", 2999, {"insulation": "Synthetic", "waterproof": True}),
        ("Sports Shorts", 499, {"material": "Polyester", "length": "7 inch"}),
    ]
    books = [
        ("Clean Code", 799, {"author": "Robert C. Martin", "pages": 431, "edition": "1st"}),
        ("Designing Data-Intensive Applications", 1299, {"author": "Martin Kleppmann", "pages": 562, "edition": "1st"}),
        ("Python Crash Course", 649, {"author": "Eric Matthes", "pages": 544, "edition": "3rd"}),
        ("The Pragmatic Programmer", 899, {"author": "Hunt & Thomas", "pages": 352, "edition": "20th"}),
        ("System Design Interview", 999, {"author": "Alex Xu", "pages": 322, "edition": "2nd"}),
        ("Deep Learning", 1499, {"author": "Goodfellow et al.", "pages": 800, "edition": "1st"}),
    ]

    all_items = (
        [(n, p, s, "electronics") for n, p, s in electronics]
        + [(n, p, s, "clothing") for n, p, s in clothing]
        + [(n, p, s, "books") for n, p, s in books]
    )

    # Shuffle aur requested count tak trim
    random.shuffle(all_items)
    selected = all_items[:count]

    tag_pool = {
        "electronics": ["tech", "gadget", "premium", "bestseller", "new-arrival", "sale"],
        "clothing": ["fashion", "casual", "summer", "winter", "sports", "premium"],
        "books": ["programming", "bestseller", "must-read", "learning", "reference"],
    }

    products = []
    for name, price, specs, category in selected:
        tags = random.sample(tag_pool[category], k=random.randint(2, 3))
        products.append({
            "name": name,
            "category": category,
            "price": price,
            "price_decimal": Decimal128(str(price) + ".00"),  # Decimal128 BSON type
            "stock": random.randint(0, 200),
            "rating": round(random.uniform(3.5, 5.0), 1),
            "in_stock": True,
            "featured": False,
            "tags": tags,
            "specs": specs,
            "views": random.randint(100, 5000),
            "sold_count": random.randint(10, 500),
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        })
    return products


# ── SECTION 1 — CONNECTION & PING ──

def demo_connection() -> Optional[MongoClient]:
    """
    MongoDB se connect karo aur basic server info print karo.
    Returns client if successful, else None.
    """
    print_section("SECTION 1 — Connection & Ping")

    print(f"  URI: {MONGO_URI}")
    print("  Connecting...")

    client = get_client()

    # Ping check
    if not check_connection(client):
        print("\n  ERROR: MongoDB not reachable!")
        print("\n  Fix karo — Docker se MongoDB start karo:")
        print("    docker run -d --name mongodb -p 27017:27017 \\")
        print("      -e MONGO_INITDB_ROOT_USERNAME=admin \\")
        print("      -e MONGO_INITDB_ROOT_PASSWORD=secret \\")
        print("      mongo:7.0")
        print("\n  Ya custom URI set karo:")
        print("    export MONGO_URI='mongodb://user:pass@host:27017/db?authSource=admin'")
        client.close()
        return None

    print("  Ping: OK (returned {ok: 1})")

    # Server info
    server_info = client.server_info()
    print(f"  MongoDB Version: {server_info['version']}")
    print(f"  Storage Engine: {server_info.get('storageEngine', {}).get('name', 'N/A')}")

    # Available databases
    db_names = client.list_database_names()
    print(f"  Databases: {db_names}")

    # practice_db collections
    db = client[DB_NAME]
    collections = db.list_collection_names()
    print(f"  Collections in '{DB_NAME}': {collections if collections else '(empty)'}")

    print("  Connection demo complete.")
    return client


# ── SECTION 2 — INSERT OPERATIONS ──

def demo_insert(client: MongoClient) -> None:
    """
    insert_one() aur insert_many() demonstrate karo.
    Sab BSON types use karo realistic data ke saath.
    """
    print_section("SECTION 2 — Insert Operations")

    db = client[DB_NAME]
    clear_collection(db, "products")
    products = db.products

    # ── insert_one() with all BSON types ──
    print("\n  [insert_one] Single product with all BSON types:")
    single_product = {
        # String
        "name": "Gaming Laptop Ultra",
        # Int (Python int → BSON Int32 or Int64)
        "price": 125000,
        "stock": 15,
        # Float → BSON Double
        "rating": 4.7,
        # Boolean
        "in_stock": True,
        "featured": False,
        # datetime → BSON Date
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
        # List → BSON Array
        "tags": ["gaming", "laptop", "premium", "rtx"],
        # dict → BSON Embedded Document
        "specs": {
            "ram": "32GB DDR5",
            "storage": "1TB NVMe SSD",
            "gpu": "RTX 4070",
            "display": "16 inch 165Hz QHD",
            "weight_kg": 2.1,
        },
        # Nested list of objects
        "reviews": [
            {"user": "user_001", "rating": 5, "comment": "Excellent build quality!", "verified": True},
            {"user": "user_002", "rating": 4, "comment": "Good value for money", "verified": True},
        ],
        # Decimal128 for precise prices (financial data)
        "price_decimal": Decimal128("125000.00"),
        # None → BSON Null
        "discount": None,
        # bytes → BSON Binary (simulated)
        "category": "electronics",
        "sold_count": 42,
        "views": 1250,
    }

    result = products.insert_one(single_product)
    print(f"    inserted_id: {result.inserted_id}  (type: {type(result.inserted_id).__name__})")
    print(f"    acknowledged: {result.acknowledged}")
    print(f"    generation_time (from ObjectId): {result.inserted_id.generation_time}")

    # Store first product id for later use
    first_product_id = result.inserted_id

    # ── insert_many() — 20 products ──
    print("\n  [insert_many] 20 products (3 categories):")
    sample_products = build_sample_products(count=20)

    t0 = time.perf_counter()
    result = products.insert_many(sample_products)
    elapsed = (time.perf_counter() - t0) * 1000

    print(f"    inserted_count: {len(result.inserted_ids)}")
    print(f"    first inserted_id: {result.inserted_ids[0]}")
    print(f"    last inserted_id: {result.inserted_ids[-1]}")
    print(f"    acknowledged: {result.acknowledged}")
    print(f"    time taken: {elapsed:.2f} ms")

    total = products.count_documents({})
    print(f"    total docs in collection now: {total}")

    # Store IDs for other demos
    db["_demo_meta"].replace_one(
        {"key": "first_product_id"},
        {"key": "first_product_id", "value": str(first_product_id)},
        upsert=True,
    )
    print("\n  Insert demo complete.")


# ── SECTION 3 — FIND & QUERY ──

def demo_find(client: MongoClient) -> None:
    """
    find_one(), find() with all major query operators demonstrate karo.
    Projection, sort, limit, skip, count bhi cover.
    """
    print_section("SECTION 3 — Find & Query Operations")

    db = client[DB_NAME]
    products = db.products

    if products.count_documents({}) == 0:
        print("  WARNING: Collection empty. Running insert demo first...")
        demo_insert(client)

    # ── find_one by _id ──
    print("\n  [find_one] By _id (str → ObjectId conversion):")
    any_doc = products.find_one({})
    if any_doc:
        oid_str = str(any_doc["_id"])
        try:
            recovered = products.find_one({"_id": ObjectId(oid_str)})
            print(f"    Found by string→ObjectId: {recovered['name']}")
        except InvalidId as e:
            print(f"    InvalidId error: {e}")

    # ── find_one with field filter ──
    print("\n  [find_one] First electronics product:")
    doc = products.find_one({"category": "electronics"})
    print_doc(doc, "Result")

    # ── find() with $gt/$lt ──
    print("\n  [find] Price > 5000 AND < 30000 ($gt, $lt):")
    docs = list(products.find(
        {"price": {"$gt": 5000, "$lt": 30000}},
        {"name": 1, "price": 1, "category": 1, "_id": 0}
    ))
    for d in docs[:5]:
        print(f"    {d}")
    print(f"    ... total: {len(docs)} docs")

    # ── find() with $in ──
    print("\n  [find] Category $in ['electronics', 'books']:")
    docs = list(products.find(
        {"category": {"$in": ["electronics", "books"]}},
        {"name": 1, "category": 1, "price": 1, "_id": 0}
    ).limit(6))
    for d in docs:
        print(f"    {d}")

    # ── find() with $regex ──
    print("\n  [find] Name contains 'pro' (case-insensitive $regex):")
    docs = list(products.find(
        {"name": {"$regex": "pro", "$options": "i"}},
        {"name": 1, "category": 1, "_id": 0}
    ))
    if docs:
        for d in docs[:5]:
            print(f"    {d}")
    else:
        # Python re.compile approach bhi same hai
        docs = list(products.find(
            {"name": re.compile(r"(pro|ultra|plus)", re.IGNORECASE)},
            {"name": 1, "category": 1, "_id": 0}
        ))
        for d in docs[:5]:
            print(f"    {d}")
    print(f"    total matching: {len(docs)}")

    # ── find() with $elemMatch on nested array ──
    print("\n  [find] Reviews where rating >= 5 AND verified=True ($elemMatch):")
    docs = list(products.find(
        {"reviews": {"$elemMatch": {"rating": {"$gte": 5}, "verified": True}}},
        {"name": 1, "reviews.$": 1, "_id": 0}
    ))
    if docs:
        for d in docs[:3]:
            print(f"    {d['name']}")
    else:
        print("    No docs with reviews array (only first insert_one has it).")
        doc = products.find_one({"reviews": {"$exists": True}})
        if doc:
            print(f"    Found via $exists: {doc['name']}")

    # ── $all operator ──
    print("\n  [find] Tags $all containing ['tech', 'premium'] or similar:")
    # Use tags that we know exist from tag_pool
    docs = list(products.find(
        {"tags": {"$all": ["premium"]}},
        {"name": 1, "tags": 1, "_id": 0}
    ).limit(4))
    for d in docs:
        print(f"    {d}")

    # ── Projection ──
    print("\n  [projection] Include name,price,category — exclude _id:")
    docs = list(products.find(
        {},
        {"name": 1, "price": 1, "category": 1, "_id": 0}
    ).limit(5))
    for d in docs:
        print(f"    {d}")

    # ── sort() + limit() + skip() ──
    print("\n  [sort+limit+skip] Top 5 most expensive, skip first 2:")
    docs = list(
        products.find({}, {"name": 1, "price": 1, "_id": 0})
        .sort("price", DESCENDING)
        .skip(2)
        .limit(5)
    )
    for i, d in enumerate(docs, 1):
        print(f"    #{i+2}: {d['name']} — ₹{d['price']}")

    # ── count_documents() ──
    print("\n  [count_documents] Counts by category:")
    for cat in ["electronics", "clothing", "books"]:
        n = products.count_documents({"category": cat})
        print(f"    {cat}: {n} docs")

    total = products.count_documents({})
    print(f"    TOTAL: {total} docs")

    print("\n  Find demo complete.")


# ── SECTION 4 — UPDATE OPERATIONS ──

def demo_update(client: MongoClient) -> None:
    """
    update_one(), update_many(), upsert, find_one_and_update() demonstrate karo.
    $set, $unset, $inc, $push, $pull, $addToSet operators.
    """
    print_section("SECTION 4 — Update Operations")

    db = client[DB_NAME]
    products = db.products

    if products.count_documents({}) == 0:
        print("  WARNING: Empty collection. Running insert demo first...")
        demo_insert(client)

    # Get a product to work with
    target = products.find_one({"category": "electronics"})
    if not target:
        print("  No electronics found, using any doc.")
        target = products.find_one({})

    target_name = target["name"]
    print(f"\n  Working with product: '{target_name}'")

    # ── $set — fields update/add ──
    print("\n  [update_one] $set — price update + new field 'last_modified':")
    new_price = target["price"] + 500
    result = products.update_one(
        {"_id": target["_id"]},
        {"$set": {
            "price": new_price,
            "last_modified": datetime.now(timezone.utc),
            "status": "active",
        }}
    )
    print(f"    matched: {result.matched_count}, modified: {result.modified_count}")
    updated = products.find_one({"_id": target["_id"]}, {"name": 1, "price": 1, "status": 1})
    print_doc(updated, "After $set")

    # ── $unset — field remove ──
    print("\n  [update_one] $unset — remove 'status' field:")
    result = products.update_one(
        {"_id": target["_id"]},
        {"$unset": {"status": ""}}  # Value irrelevant, field hata deta hai
    )
    print(f"    modified: {result.modified_count}")

    # ── $inc — increment/decrement ──
    print("\n  [update_one] $inc — stock -5, views +100:")
    current_stock = target.get("stock", 50)
    result = products.update_one(
        {"_id": target["_id"]},
        {"$inc": {"stock": -5, "views": 100}}
    )
    print(f"    modified: {result.modified_count}")
    after = products.find_one({"_id": target["_id"]}, {"stock": 1, "views": 1, "_id": 0})
    print(f"    stock was ~{current_stock}, now: {after.get('stock')}")
    print(f"    views now: {after.get('views')}")

    # ── $push — array mein element add ──
    print("\n  [update_one] $push — add 'top-rated' to tags array:")
    result = products.update_one(
        {"_id": target["_id"]},
        {"$push": {"tags": "top-rated"}}
    )
    print(f"    modified: {result.modified_count}")
    after = products.find_one({"_id": target["_id"]}, {"tags": 1, "_id": 0})
    print(f"    tags now: {after.get('tags')}")

    # ── $pull — array se element remove ──
    print("\n  [update_one] $pull — remove 'top-rated' from tags:")
    result = products.update_one(
        {"_id": target["_id"]},
        {"$pull": {"tags": "top-rated"}}
    )
    print(f"    modified: {result.modified_count}")

    # ── $addToSet — unique add (set behaviour) ──
    print("\n  [update_one] $addToSet — add 'sale' (won't duplicate):")
    # Pehli baar add hoga
    result1 = products.update_one({"_id": target["_id"]}, {"$addToSet": {"tags": "sale"}})
    # Doosri baar no-op (already exists)
    result2 = products.update_one({"_id": target["_id"]}, {"$addToSet": {"tags": "sale"}})
    print(f"    1st call modified: {result1.modified_count}  (should be 1)")
    print(f"    2nd call modified: {result2.modified_count}  (should be 0, already exists)")

    # ── update_many() ──
    print("\n  [update_many] Mark ALL electronics as featured=True:")
    result = products.update_many(
        {"category": "electronics"},
        {"$set": {"featured": True, "updated_at": datetime.now(timezone.utc)}}
    )
    print(f"    matched: {result.matched_count}, modified: {result.modified_count}")

    # ── upsert=True ──
    print("\n  [update_one] upsert=True — insert if not found:")
    sku = "PROMO-DESK-MAT-001"
    result = products.update_one(
        {"sku": sku},
        {"$set": {
            "sku": sku,
            "name": "Large Desk Mat",
            "price": 699,
            "category": "accessories",
            "stock": 100,
            "created_at": datetime.now(timezone.utc),
        }},
        upsert=True
    )
    if result.upserted_id:
        print(f"    INSERTED (upsert) — new _id: {result.upserted_id}")
    else:
        print(f"    UPDATED (existed) — modified: {result.modified_count}")

    # Call again — should update this time
    result2 = products.update_one(
        {"sku": sku},
        {"$inc": {"stock": 50}},
        upsert=True
    )
    print(f"    2nd call upserted_id: {result2.upserted_id}  (None = updated, not inserted)")

    # ── find_one_and_update() ──
    print("\n  [find_one_and_update] Return AFTER update — decrement stock:")
    doc = products.find_one_and_update(
        {"category": "electronics", "stock": {"$gt": 5}},
        {"$inc": {"stock": -1}, "$set": {"updated_at": datetime.now(timezone.utc)}},
        projection={"name": 1, "stock": 1, "_id": 0},
        return_document=ReturnDocument.AFTER,
    )
    print_doc(doc, "After (AFTER mode)")

    print("\n  Update demo complete.")


# ── SECTION 5 — DELETE OPERATIONS ──

def demo_delete(client: MongoClient) -> None:
    """
    delete_one(), delete_many(), find_one_and_delete() demonstrate karo.
    deleted_count check karo.
    """
    print_section("SECTION 5 — Delete Operations")

    db = client[DB_NAME]
    products = db.products

    # Upsert se banaya hua accessory delete karo
    print("\n  [delete_one] Delete accessory product:")
    before_count = products.count_documents({})
    result = products.delete_one({"category": "accessories"})
    after_count = products.count_documents({})
    print(f"    deleted_count: {result.deleted_count}")
    print(f"    before: {before_count}, after: {after_count}")

    # ── delete_many() ──
    print("\n  [delete_many] Delete products with stock=0:")
    # Kuch zero-stock docs banao
    products.insert_many([
        {"name": "Out of Stock A", "price": 100, "stock": 0, "category": "test"},
        {"name": "Out of Stock B", "price": 200, "stock": 0, "category": "test"},
        {"name": "Out of Stock C", "price": 300, "stock": 0, "category": "test"},
    ])
    result = products.delete_many({"stock": 0})
    print(f"    deleted_count: {result.deleted_count}")

    # ── find_one_and_delete() ──
    print("\n  [find_one_and_delete] Delete cheapest product and return it:")
    cheapest = products.find_one_and_delete(
        {"category": {"$in": ["electronics", "clothing", "books"]}},
        sort=[("price", ASCENDING)],
        projection={"name": 1, "price": 1, "category": 1, "_id": 0},
    )
    print_doc(cheapest, "Deleted doc")

    final_count = products.count_documents({})
    print(f"\n  Remaining docs after all deletes: {final_count}")
    print("\n  Delete demo complete.")


# ── SECTION 6 — bulk_write() ──

def demo_bulk_write(client: MongoClient) -> None:
    """
    bulk_write() demonstrate karo — InsertOne, UpdateOne, DeleteOne mix.
    ordered=False for better performance.
    Timing aur result stats print karo.
    """
    print_section("SECTION 6 — bulk_write()")

    db = client[DB_NAME]
    products = db.products

    # Prepare targets
    existing_docs = list(products.find({}, {"_id": 1, "name": 1, "category": 1}).limit(10))
    electronics_doc = next((d for d in existing_docs if d.get("category") == "electronics"), None)
    books_doc = next((d for d in existing_docs if d.get("category") == "books"), None)

    # ── Build mixed operations ──
    operations = [
        # InsertOne — 3 naye documents
        InsertOne({
            "name": "Bulk Insert Product 1",
            "price": 450,
            "category": "bulk_test",
            "created_at": datetime.now(timezone.utc),
            "stock": 50,
        }),
        InsertOne({
            "name": "Bulk Insert Product 2",
            "price": 750,
            "category": "bulk_test",
            "created_at": datetime.now(timezone.utc),
            "stock": 30,
        }),
        InsertOne({
            "name": "Bulk Insert Product 3",
            "price": 999,
            "category": "bulk_test",
            "created_at": datetime.now(timezone.utc),
            "stock": 20,
        }),
    ]

    # UpdateOne — 2 existing documents
    if electronics_doc:
        operations.append(
            UpdateOne(
                {"_id": electronics_doc["_id"]},
                {"$set": {"bulk_updated": True, "updated_at": datetime.now(timezone.utc)}}
            )
        )
    if books_doc:
        operations.append(
            UpdateOne(
                {"_id": books_doc["_id"]},
                {"$inc": {"views": 10}, "$set": {"bulk_updated": True}}
            )
        )

    # UpdateMany — all bulk_test products
    operations.append(
        UpdateMany(
            {"category": "bulk_test"},
            {"$set": {"processed": True}}
        )
    )

    # DeleteOne — ek bulk_test doc
    operations.append(
        DeleteOne({"category": "bulk_test", "price": {"$lt": 500}})
    )

    # Upsert — naya doc ya update
    operations.append(
        UpdateOne(
            {"sku": "BULK-UPSERT-001"},
            {"$setOnInsert": {
                "name": "Upserted via Bulk",
                "sku": "BULK-UPSERT-001",
                "price": 1200,
                "category": "bulk_test",
            }},
            upsert=True
        )
    )

    print(f"\n  Total operations prepared: {len(operations)}")
    print("  Operations breakdown:")
    from collections import Counter
    op_types = Counter(type(op).__name__ for op in operations)
    for op_type, count in op_types.items():
        print(f"    {op_type}: {count}")

    # ── Execute with ordered=False (better performance) ──
    print("\n  Executing with ordered=False...")
    t0 = time.perf_counter()
    try:
        result = products.bulk_write(operations, ordered=False)
        elapsed = (time.perf_counter() - t0) * 1000

        print(f"\n  Results:")
        print(f"    inserted_count: {result.inserted_count}")
        print(f"    matched_count:  {result.matched_count}")
        print(f"    modified_count: {result.modified_count}")
        print(f"    deleted_count:  {result.deleted_count}")
        print(f"    upserted_count: {result.upserted_count}")
        if result.upserted_ids:
            for idx, oid in result.upserted_ids.items():
                print(f"    upserted_ids[{idx}]: {oid}")
        print(f"\n  Time taken: {elapsed:.2f} ms")

    except BulkWriteError as bwe:
        elapsed = (time.perf_counter() - t0) * 1000
        print(f"  BulkWriteError (partial success possible with ordered=False)")
        print(f"  Write errors: {len(bwe.details.get('writeErrors', []))}")
        print(f"  nInserted: {bwe.details.get('nInserted', 0)}")
        print(f"  nModified: {bwe.details.get('nModified', 0)}")
        print(f"  Time taken: {elapsed:.2f} ms")

    # ── Performance comparison: loop vs bulk ──
    print("\n  [Performance] Loop insert vs bulk_write — 200 docs:")
    temp = db.perf_test
    temp.drop()

    # Loop insert
    t0 = time.perf_counter()
    for i in range(200):
        temp.insert_one({"i": i, "val": f"item_{i}"})
    loop_ms = (time.perf_counter() - t0) * 1000
    temp.drop()

    # Bulk insert
    ops = [InsertOne({"i": i, "val": f"item_{i}"}) for i in range(200)]
    t0 = time.perf_counter()
    temp.bulk_write(ops, ordered=False)
    bulk_ms = (time.perf_counter() - t0) * 1000
    temp.drop()

    print(f"    Loop  insert (200 docs): {loop_ms:.1f} ms")
    print(f"    Bulk  insert (200 docs): {bulk_ms:.1f} ms")
    if bulk_ms > 0:
        print(f"    Speedup: {loop_ms / bulk_ms:.1f}x")

    print("\n  bulk_write demo complete.")


# ── SECTION 7 — explain() & Query Analysis ──

def demo_explain(client: MongoClient) -> None:
    """
    Indexes create karo aur explain() se query plan analyze karo.
    COLLSCAN vs IXSCAN difference dikhao.
    """
    print_section("SECTION 7 — explain() & Query Analysis")

    db = client[DB_NAME]
    products = db.products

    if products.count_documents({}) == 0:
        demo_insert(client)

    # ── Check existing indexes ──
    print("\n  [list_indexes] Existing indexes:")
    for idx in products.list_indexes():
        print(f"    {idx['name']}: {idx['key']}")

    # ── BEFORE index — explain karo ──
    print("\n  [explain BEFORE index] Query on 'price' field:")
    plan_before = products.find({"price": {"$gt": 5000}}).explain("executionStats")
    stats = plan_before["executionStats"]
    winning_stage = plan_before["queryPlanner"]["winningPlan"].get("stage", "")

    # Handle compound winningPlan (inputStage)
    if winning_stage == "FETCH":
        winning_stage = (
            plan_before["queryPlanner"]["winningPlan"]
            .get("inputStage", {})
            .get("stage", winning_stage)
        )

    print(f"    winningPlan.stage: {winning_stage}  ← Should be COLLSCAN (no index)")
    print(f"    nReturned:         {stats['nReturned']}")
    print(f"    totalDocsExamined: {stats['totalDocsExamined']}")
    print(f"    executionTimeMs:   {stats['executionTimeMillis']} ms")

    # ── Create index on price ──
    print("\n  [create_index] Creating index on 'price' (ASCENDING):")
    index_name = products.create_index([("price", ASCENDING)], name="idx_price_asc")
    print(f"    Index created: {index_name}")

    # ── Compound index — category + price ──
    compound_idx = products.create_index(
        [("category", ASCENDING), ("price", DESCENDING)],
        name="idx_category_price"
    )
    print(f"    Compound index created: {compound_idx}")

    # ── AFTER index — explain ──
    print("\n  [explain AFTER index] Same query on 'price':")
    plan_after = products.find({"price": {"$gt": 5000}}).explain("executionStats")
    stats_after = plan_after["executionStats"]
    winning_stage_after = plan_after["queryPlanner"]["winningPlan"].get("stage", "")
    if winning_stage_after == "FETCH":
        winning_stage_after = (
            plan_after["queryPlanner"]["winningPlan"]
            .get("inputStage", {})
            .get("stage", winning_stage_after)
        )

    print(f"    winningPlan.stage: {winning_stage_after}  ← Should be IXSCAN (index used!)")
    print(f"    nReturned:         {stats_after['nReturned']}")
    print(f"    totalDocsExamined: {stats_after['totalDocsExamined']}")
    print(f"    totalKeysExamined: {stats_after.get('totalKeysExamined', 'N/A')}")
    print(f"    executionTimeMs:   {stats_after['executionTimeMillis']} ms")

    # ── All indexes after creation ──
    print("\n  [list_indexes] All indexes after creation:")
    for idx in products.list_indexes():
        print(f"    name: {idx['name']:30s} | key: {dict(idx['key'])}")

    # ── hint() — force specific index ──
    print("\n  [hint] Force use of compound index idx_category_price:")
    docs = list(
        products.find({"category": "electronics", "price": {"$gt": 1000}})
        .hint("idx_category_price")
        .limit(3)
    )
    print(f"    docs found with hint: {len(docs)}")

    print("\n  explain() demo complete.")


# ── SECTION 8 — Aggregation Basics ──

def demo_aggregation_basics(client: MongoClient) -> None:
    """
    Aggregation pipeline basics demonstrate karo.
    $match, $group, $sort, $limit, $project stages.
    """
    print_section("SECTION 8 — Aggregation Pipeline Basics (Preview)")

    db = client[DB_NAME]
    products = db.products

    if products.count_documents({}) == 0:
        demo_insert(client)

    # ── Pipeline 1: Avg price per category ──
    print("\n  [aggregate] Average price per category ($match + $group):")
    pipeline1 = [
        {"$match": {"category": {"$in": ["electronics", "clothing", "books"]}}},
        {
            "$group": {
                "_id": "$category",
                "avg_price": {"$avg": "$price"},
                "max_price": {"$max": "$price"},
                "min_price": {"$min": "$price"},
                "count": {"$sum": 1},
                "total_stock": {"$sum": "$stock"},
            }
        },
        {"$sort": {"avg_price": -1}},
    ]
    results = list(products.aggregate(pipeline1))
    print(f"  {'Category':<15} {'Avg Price':>12} {'Max':>10} {'Min':>8} {'Count':>7}")
    print(f"  {'-'*15} {'-'*12} {'-'*10} {'-'*8} {'-'*7}")
    for r in results:
        print(
            f"  {r['_id']:<15} {r['avg_price']:>12.0f} {r['max_price']:>10} "
            f"{r['min_price']:>8} {r['count']:>7}"
        )

    # ── Pipeline 2: Top 5 most expensive ──
    print("\n  [aggregate] Top 5 most expensive products ($sort + $limit + $project):")
    pipeline2 = [
        {"$match": {"category": {"$in": ["electronics", "clothing", "books"]}}},
        {"$sort": {"price": -1}},
        {"$limit": 5},
        {
            "$project": {
                "_id": 0,
                "name": 1,
                "category": 1,
                "price": 1,
                "rating": 1,
            }
        },
    ]
    top5 = list(products.aggregate(pipeline2))
    for i, p in enumerate(top5, 1):
        print(f"    #{i}: {p['name']:<40} ₹{p['price']:>8} [{p['category']}] ⭐{p.get('rating', 'N/A')}")

    # ── Pipeline 3: Products with tag count ──
    print("\n  [aggregate] Tag frequency ($unwind + $group):")
    pipeline3 = [
        {"$match": {"tags": {"$exists": True, "$ne": []}}},
        {"$unwind": "$tags"},
        {"$group": {"_id": "$tags", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
        {"$limit": 8},
    ]
    tag_freq = list(products.aggregate(pipeline3))
    print(f"  {'Tag':<20} {'Count':>6}")
    print(f"  {'-'*20} {'-'*6}")
    for t in tag_freq:
        print(f"  {t['_id']:<20} {t['count']:>6}")

    print("\n  Aggregation basics demo complete.")


# ── SECTION 9 — Async with Motor ──

async def motor_demo() -> None:
    """
    Motor (async pymongo) demonstrate karo — asyncio compatible.
    FastAPI / async backends ke liye use hota hai.
    """
    if not MOTOR_AVAILABLE:
        print("  Motor not installed. Skipping. Run: pip install motor")
        return

    from motor.motor_asyncio import AsyncIOMotorClient

    print("\n  [motor] Async MongoDB client with motor:")
    client = AsyncIOMotorClient(
        MONGO_URI,
        serverSelectionTimeoutMS=5000,
    )

    try:
        # Ping
        await client.admin.command("ping")
        print("  Async ping: OK")

        db = client[DB_NAME]

        # find_one (async)
        doc = await db.products.find_one({"category": "electronics"})
        if doc:
            print(f"  find_one (async): {doc.get('name')} — ₹{doc.get('price')}")
        else:
            print("  find_one (async): No electronics found")

        # count_documents (async)
        count = await db.products.count_documents({})
        print(f"  count_documents (async): {count} total products")

        # Cursor iteration (async for)
        print("  find() cursor (async for) — first 3 books:")
        async for book in db.products.find({"category": "books"}, {"name": 1, "_id": 0}).limit(3):
            print(f"    {book.get('name')}")

        # insert_one (async)
        result = await db.products.insert_one({
            "name": "Motor Async Product",
            "price": 1111,
            "category": "test_motor",
            "created_at": datetime.now(timezone.utc),
        })
        print(f"  insert_one (async): inserted_id = {result.inserted_id}")

        # Delete it
        del_result = await db.products.delete_one({"category": "test_motor"})
        print(f"  delete_one (async): deleted_count = {del_result.deleted_count}")

    except Exception as e:
        print(f"  Motor error: {e}")
    finally:
        client.close()


def demo_motor_basic(client: MongoClient = None) -> None:
    """Sync wrapper for async motor demo."""
    print_section("SECTION 9 — Async Motor Demo")
    if not MOTOR_AVAILABLE:
        print("  Skipped: motor not installed.")
        return
    asyncio.run(motor_demo())
    print("\n  Motor demo complete.")


# ── RUN ALL ──

def run_all(client: MongoClient) -> None:
    """All demos sequentially run karo."""
    demo_insert(client)
    demo_find(client)
    demo_update(client)
    demo_delete(client)
    demo_bulk_write(client)
    demo_explain(client)
    demo_aggregation_basics(client)
    demo_motor_basic(client)


# ── MAIN — CLI Interface ──

def main() -> None:
    print(f"\n{'#' * 65}")
    print("  MongoDB PyMongo Basics — Interview Prep Practical")
    print(f"{'#' * 65}")
    print(f"  URI: {MONGO_URI}")
    print(f"  DB:  {DB_NAME}")

    # Connection establish karo
    client = demo_connection()
    if client is None:
        sys.exit(1)

    # CLI demo map
    demos = {
        "connection": lambda: demo_connection(),
        "insert":     lambda: demo_insert(client),
        "find":       lambda: demo_find(client),
        "update":     lambda: demo_update(client),
        "delete":     lambda: demo_delete(client),
        "bulk":       lambda: demo_bulk_write(client),
        "explain":    lambda: demo_explain(client),
        "aggregation": lambda: demo_aggregation_basics(client),
        "motor":      lambda: demo_motor_basic(client),
        "all":        lambda: run_all(client),
    }

    # Argument parse karo
    args = sys.argv[1:]

    if not args or args[0] == "all":
        # No argument ya "all" — sab run karo
        print("\n  Running ALL demos...\n")
        total_start = time.perf_counter()
        run_all(client)
        total_elapsed = time.perf_counter() - total_start
        print(f"\n{SEPARATOR}")
        print(f"  All demos completed in {total_elapsed:.2f}s")
        print(SEPARATOR)
    elif args[0] in demos:
        demo_fn = demos[args[0]]
        t0 = time.perf_counter()
        demo_fn()
        elapsed = time.perf_counter() - t0
        print(f"\n  Demo '{args[0]}' completed in {elapsed:.2f}s")
    else:
        print(f"\n  Unknown demo: '{args[0]}'")
        print(f"  Available: {', '.join(demos.keys())}")
        sys.exit(1)

    # Cleanup
    client.close()
    print("\n  MongoDB connection closed. Bye!\n")


if __name__ == "__main__":
    main()
