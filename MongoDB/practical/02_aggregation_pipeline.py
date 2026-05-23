"""
MongoDB Aggregation Pipeline + Indexes — Production-Quality Demo
================================================================
Interview Prep Series: Python Backend Developer (5 YOE | 20 LPA)

Topics covered:
  - Data Seeding (100+ orders, 30 products, 20 users)
  - $group analytics (revenue, avg order value, top users)
  - $lookup joins (users + products + double lookup + pipeline lookup)
  - $unwind + array operations ($filter, $map)
  - $facet (multi-facet search — category + price range + count)
  - Date/Time analytics (monthly revenue, day-of-week, hour distribution)
  - $project computed fields (discounts, $cond, $ifNull, $dateToString)
  - Index management (single, compound, TTL, text, explain())
  - Schema validation ($jsonSchema, OperationFailure demo)
  - Performance tips (timing, allowDiskUse, hint())

Usage:
  python 02_aggregation_pipeline.py seed
  python 02_aggregation_pipeline.py group
  python 02_aggregation_pipeline.py lookup
  python 02_aggregation_pipeline.py unwind
  python 02_aggregation_pipeline.py facet
  python 02_aggregation_pipeline.py dates
  python 02_aggregation_pipeline.py project
  python 02_aggregation_pipeline.py indexes
  python 02_aggregation_pipeline.py validation
  python 02_aggregation_pipeline.py performance
  python 02_aggregation_pipeline.py all
"""

import os
import sys
import time
import random
import string
import pprint
from datetime import datetime, timedelta
from typing import Optional

# ---------------------------------------------------------------------------
# Dependencies: pip install pymongo
# ---------------------------------------------------------------------------
try:
    import pymongo
    from pymongo import MongoClient, IndexModel, ASCENDING, DESCENDING, TEXT, GEOSPHERE, HASHED
    from pymongo.errors import OperationFailure, ServerSelectionTimeoutError, ConnectionFailure
    from bson import ObjectId
    PYMONGO_AVAILABLE = True
except ImportError:
    PYMONGO_AVAILABLE = False
    print("ERROR: pymongo not installed. Run: pip install pymongo")
    sys.exit(1)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
MONGO_URI = os.getenv(
    "MONGO_URI",
    "mongodb://admin:secret@localhost:27017/practice_db?authSource=admin"
)
DB_NAME = "practice_db"

# Collection names
COL_PRODUCTS = "products"
COL_USERS = "users"
COL_ORDERS = "orders"
COL_VALIDATED = "validated_products"
COL_TTL_DEMO = "ttl_demo"

# ---------------------------------------------------------------------------
# Connection Helper
# ---------------------------------------------------------------------------

def get_db() -> Optional[pymongo.database.Database]:
    """Get MongoDB database connection with graceful fallback."""
    try:
        client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=3000)
        client.admin.command("ping")
        db = client[DB_NAME]
        print(f"[OK] Connected to MongoDB | DB: {DB_NAME}")
        return db
    except (ServerSelectionTimeoutError, ConnectionFailure) as e:
        print(f"[ERROR] Cannot connect to MongoDB: {e}")
        print(
            "[INFO] Start MongoDB with:\n"
            "  docker run -d -p 27017:27017 "
            "-e MONGO_INITDB_ROOT_USERNAME=admin "
            "-e MONGO_INITDB_ROOT_PASSWORD=secret "
            "--name mongo17 mongo:7\n"
            "  OR set MONGO_URI env variable"
        )
        return None


def separator(title: str = "") -> None:
    line = "=" * 65
    if title:
        print(f"\n{line}\n  {title}\n{line}")
    else:
        print(line)


def pprint_docs(docs: list, max_docs: int = 5) -> None:
    """Pretty-print a list of documents (truncate if long)."""
    for i, doc in enumerate(docs[:max_docs]):
        # Convert ObjectId to string for readable output
        clean = {k: str(v) if isinstance(v, ObjectId) else v for k, v in doc.items()}
        pprint.pprint(clean, width=100)
    if len(docs) > max_docs:
        print(f"  ... and {len(docs) - max_docs} more documents")


# ---------------------------------------------------------------------------
# Section 1 — Data Seeding
# ---------------------------------------------------------------------------

CATEGORIES = ["electronics", "clothing", "books", "food", "sports"]
REGIONS = ["north", "south", "east", "west"]
ORDER_STATUSES = ["completed", "pending", "cancelled"]

TAGS_MAP = {
    "electronics": ["tech", "gadget", "wireless", "smart", "premium", "sale"],
    "clothing":    ["fashion", "cotton", "summer", "winter", "sale", "trendy"],
    "books":       ["education", "fiction", "bestseller", "tech-book", "self-help"],
    "food":        ["organic", "vegan", "gluten-free", "sale", "fresh", "imported"],
    "sports":      ["outdoor", "fitness", "premium", "sale", "waterproof", "tech"],
}

PRODUCT_NAMES = {
    "electronics": [
        "Wireless Headphones Pro", "Smart Watch Series X", "Bluetooth Speaker Max",
        "4K OLED Monitor", "Mechanical Keyboard RGB", "Gaming Mouse Ultra",
    ],
    "clothing": [
        "Premium Cotton T-Shirt", "Slim Fit Jeans", "Winter Jacket Down",
        "Running Shoes Air", "Formal Shirt Oxford", "Casual Hoodie Fleece",
    ],
    "books": [
        "Clean Code by Martin", "Designing Data-Intensive Apps", "Python Cookbook",
        "System Design Interview", "The Pragmatic Programmer", "Database Internals",
    ],
    "food": [
        "Organic Almond Butter", "Dark Chocolate 85%", "Green Tea Premium",
        "Protein Granola Bar", "Himalayan Pink Salt", "Cold-Pressed Olive Oil",
    ],
    "sports": [
        "Yoga Mat Premium", "Resistance Bands Set", "Dumbbell Set Adjustable",
        "Running Water Bottle", "Jump Rope Speed", "Foam Roller Recovery",
    ],
}


def seed_data(db: pymongo.database.Database) -> None:
    """Seed 30 products, 20 users, 100+ orders into MongoDB."""
    separator("Section 1 — Data Seeding")

    # Clear existing data
    db[COL_PRODUCTS].drop()
    db[COL_USERS].drop()
    db[COL_ORDERS].drop()
    print("[INFO] Dropped existing collections")

    # -----------------------------------------------------------------------
    # Seed 30 Products (5 categories × 6 products)
    # -----------------------------------------------------------------------
    products = []
    now = datetime.utcnow()

    for cat in CATEGORIES:
        for i, name in enumerate(PRODUCT_NAMES[cat]):
            base_price = {
                "electronics": random.uniform(500, 50000),
                "clothing":    random.uniform(200, 5000),
                "books":       random.uniform(300, 2500),
                "food":        random.uniform(100, 2000),
                "sports":      random.uniform(200, 8000),
            }[cat]

            products.append({
                "name":        name,
                "category":    cat,
                "price":       round(base_price, 2),
                "stock":       random.randint(10, 500),
                "rating":      round(random.uniform(3.0, 5.0), 1),
                "review_count": random.randint(5, 2000),
                "tags":        random.sample(TAGS_MAP[cat], k=random.randint(2, 4)),
                "description": f"High quality {cat} product: {name}. Great value!",
                "created_at":  now - timedelta(days=random.randint(0, 365)),
            })

    result = db[COL_PRODUCTS].insert_many(products)
    product_ids = result.inserted_ids
    print(f"[OK] Inserted {len(product_ids)} products")

    # -----------------------------------------------------------------------
    # Seed 20 Users
    # -----------------------------------------------------------------------
    first_names = ["Rahul", "Priya", "Amit", "Sneha", "Vikas", "Anjali",
                   "Rohit", "Pooja", "Suresh", "Neha", "Raj", "Kavya",
                   "Arjun", "Divya", "Kiran", "Meera", "Nitin", "Sanya",
                   "Deepak", "Ritu"]

    users = []
    for i, fname in enumerate(first_names):
        users.append({
            "name":      fname + " Sharma" if i % 2 == 0 else fname + " Gupta",
            "email":     f"{fname.lower()}{i+1}@example.com",
            "region":    REGIONS[i % 4],
            "joined_at": now - timedelta(days=random.randint(30, 730)),
            "is_premium": random.choice([True, False]),
        })

    result = db[COL_USERS].insert_many(users)
    user_ids = result.inserted_ids
    print(f"[OK] Inserted {len(user_ids)} users")

    # -----------------------------------------------------------------------
    # Seed 120 Orders (12 months span)
    # -----------------------------------------------------------------------
    orders = []
    for _ in range(120):
        user_id = random.choice(user_ids)
        product = random.choice(products)
        product_id = product_ids[products.index(product)]
        quantity = random.randint(1, 5)
        days_ago = random.randint(0, 365)
        order_date = now - timedelta(days=days_ago)

        # Weight: 70% completed, 20% pending, 10% cancelled
        status = random.choices(
            ORDER_STATUSES,
            weights=[70, 20, 10],
            k=1
        )[0]

        orders.append({
            "user_id":    user_id,
            "product_id": product_id,
            "product_name": product["name"],
            "category":   product["category"],
            "price":      product["price"],
            "quantity":   quantity,
            "total_amount": round(product["price"] * quantity, 2),
            "status":     status,
            "region":     random.choice(REGIONS),
            "order_date": order_date,
        })

    result = db[COL_ORDERS].insert_many(orders)
    print(f"[OK] Inserted {len(result.inserted_ids)} orders")
    print(f"\nData seeding complete! Collections: {db.list_collection_names()}")


# ---------------------------------------------------------------------------
# Section 2 — Basic $group Analytics
# ---------------------------------------------------------------------------

def demo_group_analytics(db: pymongo.database.Database) -> None:
    """$group stage: revenue, AOV, status counts, top users."""
    separator("Section 2 — Basic $group Analytics")

    # 2a. Total revenue per category (completed orders only)
    print("\n[2a] Total Revenue per Category (completed orders):")
    pipeline = [
        {"$match": {"status": "completed"}},
        {"$group": {
            "_id": "$category",
            "total_revenue": {"$sum": "$total_amount"},
            "order_count":   {"$sum": 1},
            "avg_order":     {"$avg": "$total_amount"},
        }},
        {"$sort": {"total_revenue": -1}},
        {"$project": {
            "_id": 0,
            "category":      "$_id",
            "total_revenue": {"$round": ["$total_revenue", 2]},
            "order_count":   1,
            "avg_order":     {"$round": ["$avg_order", 2]},
        }},
    ]
    results = list(db[COL_ORDERS].aggregate(pipeline))
    for r in results:
        print(f"  {r['category']:<15} | Revenue: ₹{r['total_revenue']:>12,.2f} | Orders: {r['order_count']:>3}")

    # 2b. Average order value per region
    print("\n[2b] Average Order Value per Region:")
    pipeline = [
        {"$group": {
            "_id": "$region",
            "avg_order_value": {"$avg": "$total_amount"},
            "total_orders":    {"$sum": 1},
        }},
        {"$sort": {"avg_order_value": -1}},
    ]
    results = list(db[COL_ORDERS].aggregate(pipeline))
    for r in results:
        print(f"  {r['_id']:<10} | Avg: ₹{r['avg_order_value']:>10,.2f} | Orders: {r['total_orders']}")

    # 2c. Count orders by status
    print("\n[2c] Orders by Status:")
    pipeline = [
        {"$group": {"_id": "$status", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
    ]
    results = list(db[COL_ORDERS].aggregate(pipeline))
    total = sum(r["count"] for r in results)
    for r in results:
        pct = r["count"] / total * 100
        print(f"  {r['_id']:<12} | Count: {r['count']:>4} | {pct:5.1f}%")

    # 2d. Top 5 users by total spend
    print("\n[2d] Top 5 Users by Total Spend:")
    pipeline = [
        {"$match": {"status": "completed"}},
        {"$group": {
            "_id":        "$user_id",
            "total_spend": {"$sum": "$total_amount"},
            "order_count": {"$sum": 1},
            "categories":  {"$addToSet": "$category"},  # Unique categories
        }},
        {"$sort": {"total_spend": -1}},
        {"$limit": 5},
        {"$project": {
            "_id": 0,
            "user_id":     "$_id",
            "total_spend": {"$round": ["$total_spend", 2]},
            "order_count": 1,
            "unique_categories": {"$size": "$categories"},
        }},
    ]
    results = list(db[COL_ORDERS].aggregate(pipeline))
    for i, r in enumerate(results, 1):
        uid = str(r["user_id"])[-6:]  # Last 6 chars of ObjectId
        print(f"  #{i} User ...{uid} | Spend: ₹{r['total_spend']:>10,.2f} | Orders: {r['order_count']} | Cats: {r['unique_categories']}")


# ---------------------------------------------------------------------------
# Section 3 — $lookup (Joins)
# ---------------------------------------------------------------------------

def demo_lookup_joins(db: pymongo.database.Database) -> None:
    """$lookup: users, products, double lookup, pipeline lookup."""
    separator("Section 3 — $lookup (Join) Demos")

    # 3a. Orders joined with Users
    print("\n[3a] Orders + User Details (basic $lookup):")
    pipeline = [
        {"$limit": 3},
        {"$lookup": {
            "from":         COL_USERS,
            "localField":   "user_id",
            "foreignField": "_id",
            "as":           "user_info",
        }},
        {"$unwind": "$user_info"},
        {"$project": {
            "_id": 0,
            "order_date":  {"$dateToString": {"format": "%Y-%m-%d", "date": "$order_date"}},
            "status":      1,
            "total_amount": 1,
            "user_name":   "$user_info.name",
            "user_region": "$user_info.region",
        }},
    ]
    results = list(db[COL_ORDERS].aggregate(pipeline))
    pprint_docs(results)

    # 3b. Orders joined with Products
    print("\n[3b] Orders + Product Details:")
    pipeline = [
        {"$limit": 3},
        {"$lookup": {
            "from":         COL_PRODUCTS,
            "localField":   "product_id",
            "foreignField": "_id",
            "as":           "product_info",
        }},
        {"$unwind": {"path": "$product_info", "preserveNullAndEmptyArrays": True}},
        {"$project": {
            "_id": 0,
            "product_name": "$product_info.name",
            "category":     "$product_info.category",
            "order_qty":    "$quantity",
            "unit_price":   "$price",
            "total":        "$total_amount",
            "rating":       "$product_info.rating",
        }},
    ]
    results = list(db[COL_ORDERS].aggregate(pipeline))
    pprint_docs(results)

    # 3c. Double $lookup — orders + users + products in one pipeline
    print("\n[3c] Double $lookup (Orders + Users + Products):")
    pipeline = [
        {"$match": {"status": "completed"}},
        {"$limit": 2},
        {"$lookup": {
            "from":         COL_USERS,
            "localField":   "user_id",
            "foreignField": "_id",
            "as":           "user",
        }},
        {"$lookup": {
            "from":         COL_PRODUCTS,
            "localField":   "product_id",
            "foreignField": "_id",
            "as":           "product",
        }},
        {"$unwind": {"path": "$user",    "preserveNullAndEmptyArrays": True}},
        {"$unwind": {"path": "$product", "preserveNullAndEmptyArrays": True}},
        {"$project": {
            "_id": 0,
            "order_date":   {"$dateToString": {"format": "%Y-%m-%d", "date": "$order_date"}},
            "buyer":        "$user.name",
            "buyer_region": "$user.region",
            "product":      "$product.name",
            "category":     "$product.category",
            "quantity":     1,
            "total":        "$total_amount",
        }},
    ]
    results = list(db[COL_ORDERS].aggregate(pipeline))
    pprint_docs(results)

    # 3d. Pipeline $lookup — lookup only completed orders per user
    print("\n[3d] Pipeline $lookup (Users → their completed orders only):")
    pipeline = [
        {"$limit": 3},
        {"$lookup": {
            "from": COL_ORDERS,
            "let":  {"uid": "$_id"},
            "pipeline": [
                {"$match": {
                    "$expr": {"$eq": ["$$uid", "$user_id"]},
                    "status": "completed",
                }},
                {"$project": {"_id": 0, "total_amount": 1, "order_date": 1, "category": 1}},
                {"$sort": {"order_date": -1}},
                {"$limit": 3},
            ],
            "as": "recent_completed_orders",
        }},
        {"$project": {
            "_id": 0,
            "user_name":   "$name",
            "region":      1,
            "order_count": {"$size": "$recent_completed_orders"},
            "orders":      "$recent_completed_orders",
        }},
    ]
    results = list(db[COL_USERS].aggregate(pipeline))
    for r in results:
        print(f"  {r['user_name']:<20} ({r['region']:<6}) | Completed orders fetched: {r['order_count']}")


# ---------------------------------------------------------------------------
# Section 4 — $unwind + Array Operations
# ---------------------------------------------------------------------------

def demo_unwind(db: pymongo.database.Database) -> None:
    """$unwind: tag analytics, preserveNullAndEmptyArrays, $filter arrays."""
    separator("Section 4 — $unwind + Array Operations")

    # 4a. $unwind tags — count products per tag
    print("\n[4a] Products per Tag (via $unwind + $group):")
    pipeline = [
        {"$unwind": "$tags"},
        {"$group": {
            "_id":          "$tags",
            "product_count": {"$sum": 1},
            "categories":   {"$addToSet": "$category"},
        }},
        {"$sort": {"product_count": -1}},
        {"$project": {
            "_id": 0,
            "tag":          "$_id",
            "product_count": 1,
            "in_categories": {"$size": "$categories"},
        }},
    ]
    results = list(db[COL_PRODUCTS].aggregate(pipeline))
    for r in results:
        print(f"  #{r['tag']:<20} | Products: {r['product_count']:>3} | Categories: {r['in_categories']}")

    # 4b. $unwind with preserveNullAndEmptyArrays demo
    print("\n[4b] preserveNullAndEmptyArrays Demo:")
    # Insert test docs with edge-case arrays
    test_col = db["unwind_test"]
    test_col.drop()
    test_col.insert_many([
        {"_id": 1, "name": "Normal",  "tags": ["a", "b"]},
        {"_id": 2, "name": "Empty",   "tags": []},
        {"_id": 3, "name": "Null",    "tags": None},
        {"_id": 4, "name": "Missing"},                     # No tags field
    ])

    # Without preserveNullAndEmptyArrays
    without_preserve = list(test_col.aggregate([{"$unwind": "$tags"}]))
    print(f"  Without preserveNullAndEmptyArrays: {len(without_preserve)} docs (only non-empty arrays)")

    # With preserveNullAndEmptyArrays
    with_preserve = list(test_col.aggregate([
        {"$unwind": {"path": "$tags", "preserveNullAndEmptyArrays": True}}
    ]))
    print(f"  With    preserveNullAndEmptyArrays: {len(with_preserve)} docs (includes null/missing/empty)")

    test_col.drop()

    # 4c. $filter — keep only 'tech' or 'sale' tags
    print("\n[4c] $filter array (tags starting with 'tech' or equal 'sale'):")
    pipeline = [
        {"$limit": 5},
        {"$project": {
            "_id": 0,
            "name":      1,
            "all_tags":  "$tags",
            "tech_tags": {
                "$filter": {
                    "input": "$$ROOT.tags",
                    "as":    "t",
                    "cond":  {"$or": [
                        {"$eq": ["$$t", "tech"]},
                        {"$eq": ["$$t", "sale"]},
                        {"$eq": ["$$t", "tech-book"]},
                    ]},
                }
            },
        }},
    ]
    results = list(db[COL_PRODUCTS].aggregate(pipeline))
    for r in results:
        tech = r.get("tech_tags", [])
        print(f"  {r['name']:<35} | all: {r['all_tags']} → filtered: {tech}")

    # 4d. $map — add GST to all product prices (demonstration)
    print("\n[4d] $map — compute prices with 18% GST:")
    # Create a doc with prices array for demo
    test_col2 = db["price_test"]
    test_col2.drop()
    test_col2.insert_one({"item": "bundle", "prices": [100, 500, 1200, 3000, 50000]})
    pipeline = [
        {"$project": {
            "item": 1,
            "prices_with_gst": {
                "$map": {
                    "input": "$prices",
                    "as":    "p",
                    "in":    {"$round": [{"$multiply": ["$$p", 1.18]}, 2]},
                }
            },
        }}
    ]
    result = list(test_col2.aggregate(pipeline))[0]
    print(f"  Original:     {result['prices_with_gst']} ← wait, showing GST prices:")
    original = [100, 500, 1200, 3000, 50000]
    gst = result["prices_with_gst"]
    for o, g in zip(original, gst):
        print(f"  ₹{o:>6} + 18% GST = ₹{g:>8.2f}")
    test_col2.drop()


# ---------------------------------------------------------------------------
# Section 5 — $facet (Multi-Facet Search)
# ---------------------------------------------------------------------------

def demo_facet_search(db: pymongo.database.Database) -> None:
    """$facet: simulate e-commerce search with multiple simultaneous sub-pipelines."""
    separator("Section 5 — $facet (Multi-Facet Search)")

    search_term = "pro"  # Simulate searching for "pro"

    pipeline = [
        {"$match": {"name": {"$regex": search_term, "$options": "i"}}},
        {"$facet": {
            "totalCount": [
                {"$count": "count"}
            ],
            "byCategory": [
                {"$sortByCount": "$category"}
            ],
            "byPriceRange": [
                {"$bucket": {
                    "groupBy":    "$price",
                    "boundaries": [0, 100, 500, 1000, 5000],
                    "default":    "5000+",
                    "output": {
                        "count":    {"$sum": 1},
                        "min_price": {"$min": "$price"},
                        "max_price": {"$max": "$price"},
                    },
                }}
            ],
            "topProducts": [
                {"$sort": {"rating": -1}},
                {"$limit": 5},
                {"$project": {
                    "_id":    0,
                    "name":   1,
                    "price":  1,
                    "rating": 1,
                    "category": 1,
                }},
            ],
            "byRatingBucket": [
                {"$bucketAuto": {
                    "groupBy": "$rating",
                    "buckets": 3,
                    "output":  {"count": {"$sum": 1}},
                }}
            ],
        }},
    ]

    result = list(db[COL_PRODUCTS].aggregate(pipeline))

    if not result:
        print("[WARN] No results from $facet pipeline")
        return

    facets = result[0]

    total = facets["totalCount"][0]["count"] if facets["totalCount"] else 0
    print(f"\n  Search: '{search_term}' → {total} products found\n")

    print("  By Category:")
    for c in facets["byCategory"]:
        bar = "#" * c["count"]
        print(f"    {c['_id']:<15} | {c['count']:>3} | {bar}")

    print("\n  By Price Range:")
    for b in facets["byPriceRange"]:
        print(f"    Range: {str(b['_id']):<10} | Count: {b['count']:>3} | "
              f"Min: ₹{b.get('min_price', 0):>8,.0f} | Max: ₹{b.get('max_price', 0):>8,.0f}")

    print("\n  Top Rated Products:")
    for i, p in enumerate(facets["topProducts"], 1):
        print(f"    #{i} {p['name']:<35} | ₹{p['price']:>8,.0f} | Rating: {p['rating']}")

    print("\n  Rating Distribution (Auto Buckets):")
    for b in facets["byRatingBucket"]:
        lo = b["_id"]["min"]
        hi = b["_id"]["max"]
        print(f"    [{lo:.1f} – {hi:.1f}] → {b['count']} products")


# ---------------------------------------------------------------------------
# Section 6 — Date/Time Analytics
# ---------------------------------------------------------------------------

def demo_date_analytics(db: pymongo.database.Database) -> None:
    """Date grouping: monthly revenue, day-of-week, hour-of-day patterns."""
    separator("Section 6 — Date/Time Analytics")

    # 6a. Monthly revenue for last 12 months
    print("\n[6a] Monthly Revenue (last 12 months, completed orders):")
    cutoff = datetime.utcnow() - timedelta(days=365)
    pipeline = [
        {"$match": {"status": "completed", "order_date": {"$gte": cutoff}}},
        {"$group": {
            "_id": {
                "year":  {"$year":  "$order_date"},
                "month": {"$month": "$order_date"},
            },
            "revenue":     {"$sum": "$total_amount"},
            "order_count": {"$sum": 1},
        }},
        {"$sort": {"_id.year": 1, "_id.month": 1}},
        {"$project": {
            "_id": 0,
            "month_year": {
                "$dateToString": {
                    "format": "%b-%Y",
                    "date": {
                        "$dateFromParts": {
                            "year":  "$_id.year",
                            "month": "$_id.month",
                        }
                    },
                }
            },
            "revenue":     {"$round": ["$revenue", 0]},
            "order_count": 1,
        }},
    ]
    results = list(db[COL_ORDERS].aggregate(pipeline))
    for r in results:
        bar_len = int(r["revenue"] / 5000)
        bar = "█" * min(bar_len, 40)
        print(f"  {r['month_year']:<12} | Orders: {r['order_count']:>3} | "
              f"₹{r['revenue']:>10,.0f} {bar}")

    # 6b. Day-of-week order patterns
    print("\n[6b] Orders by Day of Week:")
    day_names = {1: "Sun", 2: "Mon", 3: "Tue", 4: "Wed", 5: "Thu", 6: "Fri", 7: "Sat"}
    pipeline = [
        {"$group": {
            "_id":   {"$dayOfWeek": "$order_date"},
            "count": {"$sum": 1},
            "total": {"$sum": "$total_amount"},
        }},
        {"$sort": {"_id": 1}},
    ]
    results = list(db[COL_ORDERS].aggregate(pipeline))
    for r in results:
        day = day_names.get(r["_id"], "?")
        bar = "#" * r["count"]
        print(f"  {day}: {r['count']:>4} orders | ₹{r['total']:>10,.0f} | {bar}")

    # 6c. Hour-of-day distribution (simulated — orders spread across day)
    print("\n[6c] Orders by Hour of Day:")
    pipeline = [
        {"$group": {
            "_id":   {"$hour": "$order_date"},
            "count": {"$sum": 1},
        }},
        {"$sort": {"_id": 1}},
    ]
    results = list(db[COL_ORDERS].aggregate(pipeline))
    for r in results:
        bar = "▓" * r["count"]
        print(f"  Hour {r['_id']:02d}: {r['count']:>3} | {bar}")

    # 6d. Revenue by category and month (compound grouping)
    print("\n[6d] Top Category Revenue per Month (last 3 months):")
    cutoff_3m = datetime.utcnow() - timedelta(days=90)
    pipeline = [
        {"$match": {"status": "completed", "order_date": {"$gte": cutoff_3m}}},
        {"$group": {
            "_id": {
                "category": "$category",
                "year":     {"$year": "$order_date"},
                "month":    {"$month": "$order_date"},
            },
            "revenue": {"$sum": "$total_amount"},
        }},
        {"$sort": {"_id.year": 1, "_id.month": 1, "revenue": -1}},
        {"$group": {
            "_id": {
                "year":  "$_id.year",
                "month": "$_id.month",
            },
            "top_category": {"$first": "$_id.category"},
            "top_revenue":  {"$first": "$revenue"},
        }},
        {"$sort": {"_id.year": 1, "_id.month": 1}},
    ]
    results = list(db[COL_ORDERS].aggregate(pipeline))
    for r in results:
        print(f"  {r['_id']['year']}-{r['_id']['month']:02d} | "
              f"Top: {r['top_category']:<15} | ₹{r['top_revenue']:>10,.0f}")


# ---------------------------------------------------------------------------
# Section 7 — $project with Computed Fields
# ---------------------------------------------------------------------------

def demo_project_computed(db: pymongo.database.Database) -> None:
    """$project: computed fields, discounts, $cond, $ifNull, $dateToString."""
    separator("Section 7 — $project Computed Fields")

    # 7a. Compute total_value and apply conditional discount
    print("\n[7a] Price + Quantity → total_value + discount with $cond:")
    pipeline = [
        {"$match": {"status": {"$in": ["completed", "pending"]}}},
        {"$limit": 8},
        {"$project": {
            "_id": 0,
            "product":     "$product_name",
            "category":    1,
            "qty":         "$quantity",
            "unit_price":  "$price",
            "total_value": {"$round": [{"$multiply": ["$price", "$quantity"]}, 2]},
            "discount_pct": {
                "$cond": {
                    "if":   {"$gte": ["$price", 5000]},
                    "then": 15,
                    "else": {
                        "$cond": {
                            "if":   {"$gte": ["$price", 1000]},
                            "then": 10,
                            "else": 0,
                        }
                    },
                }
            },
            "discounted_price": {
                "$round": [
                    {"$multiply": [
                        "$price",
                        {"$cond": {
                            "if":   {"$gte": ["$price", 5000]},
                            "then": 0.85,
                            "else": {"$cond": {"if": {"$gte": ["$price", 1000]}, "then": 0.90, "else": 1.0}},
                        }},
                    ]},
                    2,
                ]
            },
        }},
    ]
    results = list(db[COL_ORDERS].aggregate(pipeline))
    for r in results:
        disc = r.get("discount_pct", 0)
        print(f"  {r['product']:<35} | qty:{r['qty']} | "
              f"₹{r['unit_price']:>8,.0f} → disc:{disc}% → ₹{r['discounted_price']:>8,.0f}")

    # 7b. Format date + $ifNull for missing fields
    print("\n[7b] Date formatting + $ifNull defaults:")
    pipeline = [
        {"$limit": 5},
        {"$lookup": {
            "from":         COL_USERS,
            "localField":   "user_id",
            "foreignField": "_id",
            "as":           "user",
        }},
        {"$unwind": {"path": "$user", "preserveNullAndEmptyArrays": True}},
        {"$project": {
            "_id": 0,
            "order_formatted": {
                "$dateToString": {
                    "format": "%d %b %Y %H:%M",
                    "date":   "$order_date",
                }
            },
            "status":     1,
            "total":      "$total_amount",
            "user_name":  {"$ifNull": ["$user.name", "Anonymous User"]},
            "region":     {"$ifNull": ["$user.region", "unknown"]},
            "is_premium": {"$ifNull": ["$user.is_premium", False]},
        }},
    ]
    results = list(db[COL_ORDERS].aggregate(pipeline))
    for r in results:
        premium = "★" if r.get("is_premium") else " "
        print(f"  {premium} {r['order_formatted']} | {r['status']:<10} | "
              f"₹{r['total']:>10,.2f} | {r['user_name']} ({r['region']})")

    # 7c. $switch for tier labeling
    print("\n[7c] Product tier labeling with $switch:")
    pipeline = [
        {"$project": {
            "_id": 0,
            "name":     1,
            "price":    1,
            "category": 1,
            "tier": {
                "$switch": {
                    "branches": [
                        {"case": {"$gte": ["$price", 20000]}, "then": "Premium"},
                        {"case": {"$gte": ["$price", 5000]},  "then": "Mid-Range"},
                        {"case": {"$gte": ["$price", 1000]},  "then": "Budget"},
                    ],
                    "default": "Economy",
                }
            },
            "name_upper":  {"$toUpper": "$name"},
            "name_snippet": {"$substr": ["$name", 0, 15]},
        }},
        {"$sort": {"price": -1}},
        {"$limit": 8},
    ]
    results = list(db[COL_PRODUCTS].aggregate(pipeline))
    for r in results:
        print(f"  [{r['tier']:<10}] {r['name']:<35} | ₹{r['price']:>10,.0f} | {r['category']}")


# ---------------------------------------------------------------------------
# Section 8 — Index Management
# ---------------------------------------------------------------------------

def demo_index_management(db: pymongo.database.Database) -> None:
    """Create single, compound, TTL, text indexes; explain() before/after."""
    separator("Section 8 — Index Management")

    products_col = db[COL_PRODUCTS]
    orders_col   = db[COL_ORDERS]

    # Drop all non-_id indexes first (fresh start)
    for col in [products_col, orders_col]:
        for idx in col.list_indexes():
            if idx["name"] != "_id_":
                col.drop_index(idx["name"])
    print("[INFO] Dropped all non-_id indexes for fresh demo")

    # 8a. explain() BEFORE index — expect COLLSCAN
    print("\n[8a] explain() BEFORE index (expect COLLSCAN):")
    explain_before = orders_col.find(
        {"status": "completed", "total_amount": {"$gte": 1000}}
    ).explain("executionStats")
    winning_stage = explain_before["queryPlanner"]["winningPlan"].get("stage", "?")
    docs_examined = explain_before["executionStats"]["totalDocsExamined"]
    n_returned    = explain_before["executionStats"]["nReturned"]
    exec_ms       = explain_before["executionStats"]["executionTimeMillis"]
    print(f"  Stage: {winning_stage} | docsExamined: {docs_examined} | "
          f"nReturned: {n_returned} | time: {exec_ms}ms")

    # 8b. Single field index
    print("\n[8b] Creating single field index on products.price:")
    idx1 = products_col.create_index([("price", ASCENDING)], name="idx_price_asc")
    print(f"  Created: {idx1}")

    # 8c. Compound index (ESR — category + order_date + amount)
    print("\n[8c] Creating compound index on orders (ESR: status, order_date, total_amount):")
    idx2 = orders_col.create_index(
        [("status", ASCENDING), ("order_date", DESCENDING), ("total_amount", ASCENDING)],
        name="idx_orders_esr"
    )
    print(f"  Created: {idx2}")

    # 8d. explain() AFTER compound index — expect IXSCAN
    print("\n[8d] explain() AFTER compound index (expect IXSCAN):")
    explain_after = orders_col.find(
        {"status": "completed", "total_amount": {"$gte": 1000}}
    ).hint("idx_orders_esr").explain("executionStats")
    winning_plan  = explain_after["queryPlanner"]["winningPlan"]
    after_stage   = winning_plan.get("stage", "?")
    # Traverse to find IXSCAN stage
    input_stage = winning_plan.get("inputStage", {})
    ixscan_stage = input_stage.get("stage", after_stage)
    docs_after    = explain_after["executionStats"]["totalDocsExamined"]
    keys_after    = explain_after["executionStats"]["totalKeysExamined"]
    ret_after     = explain_after["executionStats"]["nReturned"]
    ms_after      = explain_after["executionStats"]["executionTimeMillis"]
    print(f"  Stage: {ixscan_stage} | keysExamined: {keys_after} | "
          f"docsExamined: {docs_after} | nReturned: {ret_after} | time: {ms_after}ms")
    print(f"  Improvement: {docs_examined} → {docs_after} docs examined")

    # 8e. Unique index
    print("\n[8e] Unique index on products.name + category combo:")
    try:
        idx3 = products_col.create_index(
            [("name", ASCENDING), ("category", ASCENDING)],
            unique=True,
            name="idx_product_unique"
        )
        print(f"  Created: {idx3}")
    except pymongo.errors.DuplicateKeyError as e:
        print(f"  [WARN] Duplicate keys exist, skipping unique index: {e}")

    # 8f. TTL index
    print("\n[8f] TTL Index (expireAfterSeconds=3600) on ttl_demo collection:")
    ttl_col = db[COL_TTL_DEMO]
    ttl_col.drop()
    ttl_idx = ttl_col.create_index(
        [("created_at", ASCENDING)],
        expireAfterSeconds=3600,
        name="idx_ttl_1hour"
    )
    ttl_col.insert_many([
        {"session_id": "sess_abc", "user": "rahul", "created_at": datetime.utcnow()},
        {"session_id": "sess_xyz", "user": "priya", "created_at": datetime.utcnow() - timedelta(hours=2)},
    ])
    print(f"  Created TTL index: {ttl_idx}")
    print(f"  Inserted 2 session docs (one already expired after 1 hour)")

    # 8g. Text index with weights
    print("\n[8g] Text index on products (name weight=10, description weight=3):")
    text_idx = products_col.create_index(
        [("name", TEXT), ("description", TEXT)],
        weights={"name": 10, "description": 3},
        name="idx_products_text"
    )
    print(f"  Created: {text_idx}")

    # Text search demo
    print("\n[8h] Text search: 'wireless bluetooth'")
    text_results = list(products_col.find(
        {"$text": {"$search": "wireless bluetooth"}},
        {"score": {"$meta": "textScore"}, "name": 1, "category": 1, "_id": 0}
    ).sort([("score", {"$meta": "textScore"})]).limit(5))
    if text_results:
        for r in text_results:
            print(f"  Score: {r.get('score', 0):5.2f} | {r['name']:<40} | {r['category']}")
    else:
        print("  No text search results (try different search terms)")

    # 8i. Partial index (only index active status)
    print("\n[8i] Partial index — only 'completed' orders:")
    partial_idx = orders_col.create_index(
        [("order_date", DESCENDING)],
        partialFilterExpression={"status": "completed"},
        name="idx_completed_orders_date"
    )
    print(f"  Created: {partial_idx}")

    # 8j. Wildcard index on product attributes
    print("\n[8j] Wildcard index on products (all fields):")
    # Note: wildcard index uses string key in Python driver
    wildcard_idx = products_col.create_index([("$**", ASCENDING)], name="idx_wildcard")
    print(f"  Created: {wildcard_idx}")

    # 8k. List all indexes
    print("\n[8k] All indexes on 'orders' collection:")
    for idx in orders_col.list_indexes():
        key_str = str(dict(idx["key"]))
        sparse  = "[sparse]"  if idx.get("sparse")  else ""
        unique  = "[unique]"  if idx.get("unique")   else ""
        partial = "[partial]" if idx.get("partialFilterExpression") else ""
        ttl_val = f"[TTL:{idx.get('expireAfterSeconds')}s]" if idx.get("expireAfterSeconds") else ""
        flags   = " ".join(filter(None, [sparse, unique, partial, ttl_val]))
        print(f"  {idx['name']:<40} | {key_str} {flags}")

    print("\n[8l] All indexes on 'products' collection:")
    for idx in products_col.list_indexes():
        key_str = str(dict(idx["key"]))
        print(f"  {idx['name']:<40} | {key_str}")


# ---------------------------------------------------------------------------
# Section 9 — Schema Validation
# ---------------------------------------------------------------------------

def demo_schema_validation(db: pymongo.database.Database) -> None:
    """Create validated collection, demo valid/invalid inserts."""
    separator("Section 9 — Schema Validation ($jsonSchema)")

    # Drop and recreate
    try:
        db.drop_collection(COL_VALIDATED)
    except Exception:
        pass

    validator = {
        "$jsonSchema": {
            "bsonType": "object",
            "required": ["name", "category", "price", "status"],
            "properties": {
                "_id": {"bsonType": "objectId"},
                "name": {
                    "bsonType": "string",
                    "minLength": 3,
                    "maxLength": 100,
                    "description": "Product name: 3-100 chars required",
                },
                "category": {
                    "bsonType": "string",
                    "enum": ["electronics", "clothing", "books", "food", "sports"],
                    "description": "Must be a valid category",
                },
                "price": {
                    "bsonType": ["double", "int"],
                    "minimum": 0,
                    "description": "Price must be >= 0",
                },
                "stock": {
                    "bsonType": "int",
                    "minimum": 0,
                    "description": "Stock must be non-negative integer",
                },
                "status": {
                    "bsonType": "string",
                    "enum": ["active", "inactive", "draft"],
                    "description": "Status must be: active, inactive, or draft",
                },
                "tags": {
                    "bsonType": "array",
                    "items": {"bsonType": "string"},
                    "description": "Tags must be array of strings",
                },
                "rating": {
                    "bsonType": "double",
                    "minimum": 0.0,
                    "maximum": 5.0,
                    "description": "Rating between 0 and 5",
                },
            },
        }
    }

    db.create_collection(
        COL_VALIDATED,
        validator=validator,
        validationLevel="strict",
        validationAction="error",
    )
    print(f"[OK] Created '{COL_VALIDATED}' with $jsonSchema validator")
    print("     Required fields: name, category, price, status")
    print("     category enum: electronics/clothing/books/food/sports")
    print("     status enum: active/inactive/draft")

    val_col = db[COL_VALIDATED]

    # Valid insert
    print("\n[9a] Valid insert (should SUCCEED):")
    valid_doc = {
        "name":     "Sony WH-1000XM5 Headphones",
        "category": "electronics",
        "price":    29990.0,
        "stock":    45,
        "status":   "active",
        "tags":     ["wireless", "noise-cancelling", "premium"],
        "rating":   4.8,
    }
    try:
        result = val_col.insert_one(valid_doc)
        print(f"  [OK] Inserted with _id: {result.inserted_id}")
    except OperationFailure as e:
        print(f"  [FAIL] Unexpected: {e}")

    # Test cases that should FAIL
    invalid_cases = [
        ("Missing required field 'status'",
         {"name": "Test Product", "category": "electronics", "price": 100.0}),

        ("Price is negative",
         {"name": "Bad Price", "category": "clothing", "price": -500.0, "status": "active"}),

        ("Invalid category enum",
         {"name": "Unknown Cat", "category": "furniture", "price": 200.0, "status": "active"}),

        ("Invalid status enum",
         {"name": "Bad Status", "category": "books", "price": 300.0, "status": "deleted"}),

        ("Name too short (< 3 chars)",
         {"name": "AB", "category": "food", "price": 50.0, "status": "draft"}),

        ("Rating out of range (> 5.0)",
         {"name": "Over Rated Product", "category": "sports", "price": 999.0, "status": "active", "rating": 6.5}),
    ]

    print("\n[9b] Invalid inserts (each should raise OperationFailure):")
    for description, bad_doc in invalid_cases:
        try:
            val_col.insert_one(bad_doc)
            print(f"  [UNEXPECTED PASS] {description}")
        except OperationFailure as e:
            # Extract the validation details
            details = str(e)[:120]
            print(f"  [OK - Rejected] {description}")
            print(f"           Error: {details}...")

    count = val_col.count_documents({})
    print(f"\n[INFO] Final count in '{COL_VALIDATED}': {count} (only valid docs)")


# ---------------------------------------------------------------------------
# Section 10 — Aggregation Performance Tips
# ---------------------------------------------------------------------------

def demo_performance(db: pymongo.database.Database) -> None:
    """Performance: early $match timing, allowDiskUse, hint() in aggregation."""
    separator("Section 10 — Aggregation Performance Tips")

    orders_col = db[COL_ORDERS]
    total_docs = orders_col.count_documents({})
    print(f"[INFO] Total orders in collection: {total_docs}")

    # 10a. Timing: pipeline without early $match vs with early $match
    print("\n[10a] Timing — Early $match vs Late $match:")

    # Pipeline WITHOUT early $match (inefficient — $group on all docs first)
    pipeline_no_match = [
        {"$group": {
            "_id":     "$category",
            "revenue": {"$sum": "$total_amount"},
            "count":   {"$sum": 1},
        }},
        {"$match": {"count": {"$gte": 5}}},  # Filter AFTER group
    ]

    # Pipeline WITH early $match (efficient — filter before $group)
    pipeline_with_match = [
        {"$match": {"status": "completed"}},  # Filter EARLY — uses index
        {"$group": {
            "_id":     "$category",
            "revenue": {"$sum": "$total_amount"},
            "count":   {"$sum": 1},
        }},
        {"$match": {"count": {"$gte": 5}}},
    ]

    # Time both
    runs = 20
    t0 = time.perf_counter()
    for _ in range(runs):
        _ = list(orders_col.aggregate(pipeline_no_match))
    t1 = time.perf_counter()
    time_no_match = (t1 - t0) / runs * 1000  # ms per run

    t0 = time.perf_counter()
    for _ in range(runs):
        _ = list(orders_col.aggregate(pipeline_with_match))
    t1 = time.perf_counter()
    time_with_match = (t1 - t0) / runs * 1000

    print(f"  Without early $match: {time_no_match:.2f} ms/run (avg of {runs} runs)")
    print(f"  With    early $match: {time_with_match:.2f} ms/run (avg of {runs} runs)")
    if time_with_match < time_no_match:
        speedup = time_no_match / time_with_match
        print(f"  Speedup: {speedup:.2f}x faster with early $match!")
    else:
        print(f"  [NOTE] Small dataset — difference more pronounced with larger data")

    # 10b. allowDiskUse=True demo
    print("\n[10b] allowDiskUse=True for large sort pipelines:")
    pipeline_large_sort = [
        {"$match": {"status": "completed"}},
        {"$sort": {"total_amount": -1, "order_date": -1}},  # Sort on all docs
        {"$group": {
            "_id":         "$user_id",
            "max_order":   {"$first": "$total_amount"},
            "total_spend": {"$sum": "$total_amount"},
        }},
        {"$sort": {"total_spend": -1}},
        {"$limit": 10},
    ]
    try:
        results = list(orders_col.aggregate(pipeline_large_sort, allowDiskUse=True))
        print(f"  [OK] Pipeline with allowDiskUse=True returned {len(results)} results")
        print(f"  [INFO] allowDiskUse=True lets MongoDB spill to disk if 100MB RAM exceeded")
    except Exception as e:
        print(f"  [ERROR] {e}")

    # 10c. hint() to force specific index in aggregation
    print("\n[10c] hint() — force specific index in aggregation pipeline:")

    # Make sure compound index exists
    try:
        orders_col.create_index(
            [("status", ASCENDING), ("total_amount", DESCENDING)],
            name="idx_hint_demo"
        )
    except Exception:
        pass

    pipeline_with_hint = [
        {"$match": {"status": "completed"}},
        {"$group": {"_id": "$category", "revenue": {"$sum": "$total_amount"}}},
        {"$sort": {"revenue": -1}},
    ]

    try:
        results = list(orders_col.aggregate(
            pipeline_with_hint,
            hint="idx_hint_demo",     # Force this specific index
            allowDiskUse=True
        ))
        print(f"  [OK] Aggregation with hint='idx_hint_demo' returned {len(results)} categories")
    except Exception as e:
        print(f"  [WARN] hint() failed (index may not exist): {e}")
        results = list(orders_col.aggregate(pipeline_with_hint))
        print(f"  [OK] Fallback without hint: {len(results)} categories")

    for r in results:
        print(f"  {r['_id']:<15} | ₹{r['revenue']:>12,.2f}")

    # 10d. explain() on aggregation pipeline
    print("\n[10d] explain() on aggregation pipeline:")
    try:
        explain_result = db.command(
            "aggregate",
            COL_ORDERS,
            pipeline=pipeline_with_hint,
            explain=True,
            allowDiskUse=True,
        )
        stages = explain_result.get("stages", [])
        if stages:
            first_stage = stages[0]
            stage_name = list(first_stage.keys())[0]
            print(f"  First explain stage: {stage_name}")
            # Look for index usage
            cursor_info = first_stage.get("$cursor", {})
            query_planner = cursor_info.get("queryPlanner", {})
            winning_plan = query_planner.get("winningPlan", {})
            stage = winning_plan.get("stage", "N/A")
            print(f"  Query planner winning stage: {stage}")
        else:
            # MongoDB 5.0+ format
            server_info = explain_result.get("serverInfo", {})
            print(f"  explain() successful — check full output with pprint.pprint(explain_result)")
    except Exception as e:
        print(f"  [WARN] explain via command failed: {e}")

    # 10e. $count stage vs countDocuments() — performance note
    print("\n[10e] $count stage in pipeline vs separate countDocuments():")
    t0 = time.perf_counter()
    for _ in range(50):
        cnt = list(orders_col.aggregate([
            {"$match": {"status": "completed"}},
            {"$count": "total"}
        ]))[0]["total"]
    t1 = time.perf_counter()
    agg_count_ms = (t1 - t0) / 50 * 1000

    t0 = time.perf_counter()
    for _ in range(50):
        cnt2 = orders_col.count_documents({"status": "completed"})
    t1 = time.perf_counter()
    count_doc_ms = (t1 - t0) / 50 * 1000

    print(f"  aggregate $count:   {agg_count_ms:.3f} ms/call | result: {cnt}")
    print(f"  count_documents():  {count_doc_ms:.3f} ms/call | result: {cnt2}")
    print(f"  [TIP] count_documents() is usually faster for simple counts")
    print(f"        Use $count in pipeline when combining with other stages")


# ---------------------------------------------------------------------------
# run_all — run every demo in sequence
# ---------------------------------------------------------------------------

def run_all(db: pymongo.database.Database) -> None:
    """Run all demo sections."""
    seed_data(db)
    demo_group_analytics(db)
    demo_lookup_joins(db)
    demo_unwind(db)
    demo_facet_search(db)
    demo_date_analytics(db)
    demo_project_computed(db)
    demo_index_management(db)
    demo_schema_validation(db)
    demo_performance(db)
    separator("ALL DEMOS COMPLETE")
    print("[OK] All sections executed successfully!")


# ---------------------------------------------------------------------------
# CLI Entry Point
# ---------------------------------------------------------------------------

def main() -> None:
    demos = {
        "seed":        seed_data,
        "group":       demo_group_analytics,
        "lookup":      demo_lookup_joins,
        "unwind":      demo_unwind,
        "facet":       demo_facet_search,
        "dates":       demo_date_analytics,
        "project":     demo_project_computed,
        "indexes":     demo_index_management,
        "validation":  demo_schema_validation,
        "performance": demo_performance,
        "all":         run_all,
    }

    usage = (
        f"\nUsage: python {os.path.basename(__file__)} <command>\n\n"
        "Commands:\n"
        + "\n".join(f"  {cmd:<14} — {fn.__doc__.split(chr(10))[0].strip()}"
                    for cmd, fn in demos.items())
        + "\n\nExample:\n"
        "  python 02_aggregation_pipeline.py seed\n"
        "  python 02_aggregation_pipeline.py all\n"
    )

    if len(sys.argv) < 2 or sys.argv[1] not in demos:
        print(usage)
        sys.exit(0)

    command = sys.argv[1]

    # Auto-seed if not seeded yet and command is not "seed" or "all"
    db = get_db()
    if db is None:
        sys.exit(1)

    if command not in ("seed", "all"):
        count = db[COL_ORDERS].count_documents({})
        if count == 0:
            print(f"[INFO] No data found. Auto-seeding first...")
            seed_data(db)

    fn = demos[command]
    if command == "all":
        fn(db)
    else:
        fn(db)

    print("\n[DONE]")


if __name__ == "__main__":
    main()
