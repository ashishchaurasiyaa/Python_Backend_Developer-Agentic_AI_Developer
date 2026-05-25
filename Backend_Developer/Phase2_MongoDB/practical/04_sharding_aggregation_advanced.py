"""
============================================================
MONGODB SHARDING + AGGREGATION ADVANCED — Practical
============================================================
Setup:
    docker-compose up   # for sharded cluster (see compose below)
    pip install motor pymongo
"""


# ============================================================
# 1. DOCKER COMPOSE — Sharded Cluster
# ============================================================
DOCKER_COMPOSE = """
# docker-compose.yml — minimal sharded cluster

version: '3'
services:
  config1:
    image: mongo:7
    command: mongod --configsvr --replSet configReplSet --port 27019

  shard1a:
    image: mongo:7
    command: mongod --shardsvr --replSet shard1ReplSet --port 27018

  shard2a:
    image: mongo:7
    command: mongod --shardsvr --replSet shard2ReplSet --port 27018

  mongos:
    image: mongo:7
    depends_on: [config1, shard1a, shard2a]
    command: mongos --configdb configReplSet/config1:27019 --port 27017
    ports: ["27017:27017"]

# Initialize:
# mongosh --port 27019 --eval 'rs.initiate({_id: "configReplSet", configsvr: true, members: [{_id:0, host:"config1:27019"}]})'
# mongosh --port 27018 --eval 'rs.initiate({_id: "shard1ReplSet", members: [{_id:0, host:"shard1a:27018"}]})'
# mongosh --port 27018 --eval 'rs.initiate({_id: "shard2ReplSet", members: [{_id:0, host:"shard2a:27018"}]})'

# Add shards via mongos
# sh.addShard("shard1ReplSet/shard1a:27018")
# sh.addShard("shard2ReplSet/shard2a:27018")
# sh.enableSharding("mydb")
# sh.shardCollection("mydb.orders", { user_id: "hashed" })
"""


# ============================================================
# 2. SHARDING COMMANDS
# ============================================================
SHARDING_COMMANDS = """
// Enable sharding on database
sh.enableSharding("mydb")

// Shard a collection (hashed — even distribution)
sh.shardCollection("mydb.orders", { user_id: "hashed" })

// Compound shard key (better for range queries)
sh.shardCollection("mydb.events", { region: 1, user_id: 1 })

// Range-based (good when you want range queries to one shard)
sh.shardCollection("mydb.time_series", { timestamp: 1 })

// View status
sh.status()

// Check chunk distribution
db.orders.getShardDistribution()

// Manually split + move chunk (rarely needed)
sh.splitAt("mydb.orders", { user_id: 1000 })
sh.moveChunk("mydb.orders", { user_id: 500 }, "shard1ReplSet")

// Balancer controls
sh.startBalancer()
sh.stopBalancer()
sh.getBalancerState()

// Set balancer window (only run during off-hours)
db.settings.updateOne(
    { _id: "balancer" },
    { $set: { activeWindow: { start: "23:00", stop: "06:00" } } },
    { upsert: true }
)
"""


# ============================================================
# 3. PYTHON: MOTOR (ASYNC)
# ============================================================
MOTOR_USAGE = '''
from motor.motor_asyncio import AsyncIOMotorClient
import asyncio


# Connect to mongos
client = AsyncIOMotorClient("mongodb://localhost:27017")
db = client.mydb


# ===== TARGETED QUERY (uses shard key) =====
async def get_user_orders(user_id: int):
    cursor = db.orders.find({"user_id": user_id})    # Hits one shard
    return await cursor.to_list(length=None)


# ===== SCATTER-GATHER (avoid in hot path) =====
async def find_by_email(email: str):
    return await db.orders.find_one({"email": email})    # All shards


# ===== BULK INSERT =====
async def bulk_insert(orders):
    if not orders:
        return
    result = await db.orders.insert_many(orders, ordered=False)
    return result.inserted_ids


# ===== BULK WRITE (mixed ops) =====
from pymongo import InsertOne, UpdateOne, DeleteOne

async def bulk_operations(operations):
    ops = []
    for op in operations:
        if op["type"] == "insert":
            ops.append(InsertOne(op["doc"]))
        elif op["type"] == "update":
            ops.append(UpdateOne(op["filter"], op["update"]))
        elif op["type"] == "delete":
            ops.append(DeleteOne(op["filter"]))
    return await db.orders.bulk_write(ops, ordered=False)
'''


# ============================================================
# 4. ADVANCED AGGREGATION PIPELINES
# ============================================================
ADVANCED_AGGREGATION = '''
# ===== DAILY REVENUE BY CATEGORY =====
async def daily_revenue():
    pipeline = [
        # 1. Filter (uses index)
        {"$match": {
            "status": "completed",
            "created_at": {"$gte": datetime(2024, 1, 1)},
        }},

        # 2. Group by day + category
        {"$group": {
            "_id": {
                "day": {"$dateToString": {"format": "%Y-%m-%d", "date": "$created_at"}},
                "category": "$category",
            },
            "revenue": {"$sum": "$amount"},
            "order_count": {"$sum": 1},
            "unique_customers": {"$addToSet": "$user_id"},
        }},

        # 3. Compute size of set
        {"$project": {
            "day": "$_id.day",
            "category": "$_id.category",
            "revenue": 1,
            "order_count": 1,
            "unique_customers": {"$size": "$unique_customers"},
            "_id": 0,
        }},

        # 4. Sort
        {"$sort": {"day": -1, "revenue": -1}},
    ]
    return await db.orders.aggregate(pipeline).to_list(None)


# ===== TOP-N PER GROUP =====
async def top3_products_per_category():
    pipeline = [
        {"$sort": {"category": 1, "sales": -1}},
        {"$group": {
            "_id": "$category",
            "products": {"$push": {"name": "$name", "sales": "$sales"}},
        }},
        {"$project": {
            "category": "$_id",
            "top3": {"$slice": ["$products", 3]},
            "_id": 0,
        }},
    ]
    return await db.products.aggregate(pipeline).to_list(None)


# ===== $FACET — multiple metrics in one query =====
async def dashboard_metrics():
    pipeline = [{
        "$facet": {
            "total_revenue": [
                {"$group": {"_id": None, "sum": {"$sum": "$amount"}}}
            ],
            "by_status": [
                {"$group": {"_id": "$status", "count": {"$sum": 1}}}
            ],
            "top_customers": [
                {"$group": {"_id": "$user_id", "total": {"$sum": "$amount"}}},
                {"$sort": {"total": -1}},
                {"$limit": 10}
            ],
            "daily_trend": [
                {"$match": {"created_at": {"$gte": datetime.now() - timedelta(days=30)}}},
                {"$group": {
                    "_id": {"$dateToString": {"format": "%Y-%m-%d", "date": "$created_at"}},
                    "count": {"$sum": 1},
                }},
                {"$sort": {"_id": 1}},
            ],
        }
    }]
    result = await db.orders.aggregate(pipeline).to_list(1)
    return result[0]


# ===== $BUCKET — histogram =====
async def order_size_histogram():
    pipeline = [{
        "$bucket": {
            "groupBy": "$amount",
            "boundaries": [0, 100, 500, 1000, 5000, float("inf")],
            "default": "Other",
            "output": {
                "count": {"$sum": 1},
                "avg_amount": {"$avg": "$amount"},
                "total": {"$sum": "$amount"},
            }
        }
    }]
    return await db.orders.aggregate(pipeline).to_list(None)


# ===== $LOOKUP (JOIN) =====
async def orders_with_users():
    pipeline = [
        {"$match": {"status": "completed"}},
        {"$lookup": {
            "from": "users",
            "localField": "user_id",
            "foreignField": "_id",
            "as": "user"
        }},
        {"$unwind": "$user"},
        {"$project": {
            "order_id": "$_id",
            "amount": 1,
            "user_name": "$user.name",
            "user_tier": "$user.tier",
        }}
    ]
    return await db.orders.aggregate(pipeline).to_list(None)


# ===== $GRAPHLOOKUP — recursive (org tree, social graph) =====
async def employee_hierarchy(manager_id):
    pipeline = [
        {"$match": {"_id": manager_id}},
        {"$graphLookup": {
            "from": "employees",
            "startWith": "$_id",
            "connectFromField": "_id",
            "connectToField": "manager_id",
            "as": "reports",
            "maxDepth": 5,
            "depthField": "depth",
        }}
    ]
    return await db.employees.aggregate(pipeline).to_list(1)
'''


# ============================================================
# 5. MATERIALIZED VIEWS via $out / $merge
# ============================================================
MATERIALIZED_VIEWS = '''
# Pre-compute heavy aggregation, save to collection

async def update_daily_stats():
    """Run nightly — pre-computes daily stats."""
    pipeline = [
        {"$match": {"created_at": {"$gte": yesterday}}},
        {"$group": {
            "_id": {
                "day": {"$dateToString": {"format": "%Y-%m-%d", "date": "$created_at"}},
                "user_id": "$user_id",
            },
            "total": {"$sum": "$amount"},
            "count": {"$sum": 1},
        }},
        # $merge upserts into another collection
        {"$merge": {
            "into": "user_daily_stats",
            "on": "_id",
            "whenMatched": "merge",      # update existing
            "whenNotMatched": "insert",  # insert new
        }}
    ]
    await db.orders.aggregate(pipeline).to_list(None)
    # user_daily_stats collection now has aggregated data
    # Fast queries from dashboard

# Schedule via cron, Celery beat, or Airflow
'''


# ============================================================
# 6. CHANGE STREAMS (real-time)
# ============================================================
CHANGE_STREAMS = '''
async def watch_orders():
    """Real-time stream of new orders."""
    pipeline = [
        {"$match": {
            "operationType": {"$in": ["insert", "update"]}
        }}
    ]
    async with db.orders.watch(pipeline, full_document="updateLookup") as stream:
        async for change in stream:
            op = change["operationType"]
            doc = change.get("fullDocument", {})

            if op == "insert":
                # Send to Kafka, update cache, notify subscribers
                await notify_new_order(doc)
            elif op == "update":
                await invalidate_cache(doc["_id"])


# Resume from token (after restart)
async def resumable_watcher(resume_token=None):
    kwargs = {"resume_after": resume_token} if resume_token else {}
    async with db.orders.watch(**kwargs) as stream:
        async for change in stream:
            await process(change)
            # Save resume token periodically
            await save_resume_token(change["_id"])


# Cluster-wide change stream
async def watch_all_writes():
    async with client.watch() as stream:
        async for change in stream:
            print(f"{change['ns']['db']}.{change['ns']['coll']}: {change['operationType']}")
'''


# ============================================================
# 7. TRANSACTIONS
# ============================================================
TRANSACTIONS = '''
async def transfer(from_id, to_id, amount):
    """Multi-document transaction (sharded transactions work too)."""
    async with await client.start_session() as session:
        async with session.start_transaction():
            try:
                # Decrement source
                result = await db.accounts.update_one(
                    {"_id": from_id, "balance": {"$gte": amount}},
                    {"$inc": {"balance": -amount}},
                    session=session,
                )
                if result.matched_count == 0:
                    raise ValueError("Insufficient balance")

                # Increment destination
                await db.accounts.update_one(
                    {"_id": to_id},
                    {"$inc": {"balance": amount}},
                    session=session,
                )

                # Record transaction
                await db.transactions.insert_one(
                    {"from": from_id, "to": to_id, "amount": amount, "ts": datetime.utcnow()},
                    session=session,
                )
                # Auto-commit on success
            except Exception:
                # Auto-rollback on exception
                raise
'''


# ============================================================
# 8. INDEXES FOR AGGREGATION
# ============================================================
INDEXES = """
// ===== INDEXES MATCHING PIPELINE =====

// For: {$match: {status, created_at}} → {$sort: {created_at}}
db.orders.createIndex({status: 1, created_at: -1})

// For: {$match: {user_id, status}} → {$group: {user_id}}
db.orders.createIndex({user_id: 1, status: 1})

// Text index for search
db.products.createIndex({name: "text", description: "text"})
db.products.find({$text: {$search: "iphone"}})

// Geospatial
db.locations.createIndex({coords: "2dsphere"})

// TTL (auto-expire)
db.sessions.createIndex({last_active: 1}, {expireAfterSeconds: 3600})

// Sparse (only docs with field)
db.users.createIndex({email: 1}, {sparse: true, unique: true})

// Partial (subset of docs)
db.orders.createIndex(
    {created_at: -1},
    {partialFilterExpression: {status: "active"}}
)

// Compound covering index — query satisfied entirely from index
db.orders.createIndex({user_id: 1, status: 1, created_at: -1, amount: 1})
"""


# ============================================================
# 9. FASTAPI INTEGRATION
# ============================================================
FASTAPI_INTEGRATION = '''
from fastapi import FastAPI, Query, Depends
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel
from datetime import datetime

app = FastAPI()


@app.get("/users/{user_id}/orders")
async def user_orders(
    user_id: int,
    limit: int = Query(20, le=100),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """Targeted query — uses shard key."""
    cursor = db.orders.find({"user_id": user_id}).sort("created_at", -1).limit(limit)
    return await cursor.to_list(length=limit)


@app.get("/analytics/dashboard")
async def dashboard(db: AsyncIOMotorDatabase = Depends(get_db)):
    """Pre-aggregated, fast query."""
    return await db.daily_stats.find_one({"date": datetime.utcnow().date()})


@app.post("/orders")
async def create_order(order: OrderCreate, db: AsyncIOMotorDatabase = Depends(get_db)):
    """Insert with shard key for targeted writes."""
    doc = order.dict()
    doc["created_at"] = datetime.utcnow()
    doc["status"] = "pending"
    result = await db.orders.insert_one(doc)
    return {"order_id": str(result.inserted_id)}


@app.get("/search")
async def search_products(
    q: str = Query(..., min_length=2),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """Atlas Search (or fallback to text index)."""
    cursor = db.products.aggregate([
        {
            "$search": {
                "index": "products_search",
                "text": {
                    "query": q,
                    "path": ["name", "description"],
                    "fuzzy": {"maxEdits": 1},
                }
            }
        },
        {"$project": {"name": 1, "price": 1, "score": {"$meta": "searchScore"}}},
        {"$limit": 20}
    ])
    return await cursor.to_list(length=20)
'''


# ============================================================
# MAIN
# ============================================================
if __name__ == "__main__":
    print("=" * 60)
    print("MONGODB SHARDING + AGGREGATION ADVANCED")
    print("=" * 60)

    print("\n--- DOCKER COMPOSE (sharded cluster) ---")
    print(DOCKER_COMPOSE)
    print("\n--- SHARDING COMMANDS ---")
    print(SHARDING_COMMANDS)
    print("\n--- MOTOR USAGE ---")
    print(MOTOR_USAGE)
    print("\n--- ADVANCED AGGREGATION ---")
    print(ADVANCED_AGGREGATION)
    print("\n--- MATERIALIZED VIEWS ---")
    print(MATERIALIZED_VIEWS)
    print("\n--- CHANGE STREAMS ---")
    print(CHANGE_STREAMS)
    print("\n--- TRANSACTIONS ---")
    print(TRANSACTIONS)
    print("\n--- INDEXES ---")
    print(INDEXES)
    print("\n--- FASTAPI INTEGRATION ---")
    print(FASTAPI_INTEGRATION)
