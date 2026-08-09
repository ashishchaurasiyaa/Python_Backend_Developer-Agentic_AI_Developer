"""
Azure Cosmos DB via MongoDB API — Wire-Compatibility Practical
===============================================================
Point: SAME pymongo code, different connection string → Cosmos DB.
Yeh file ../theory/10_cosmos_db_azure.md ke concepts ko runnable banati hai.

Run: python 09_cosmos_db_emulator.py

Connection targets (first one that works wins):
    1. COSMOS_MONGO_URI env var — real Cosmos account (Mongo API) ya emulator
    2. Local MongoDB (MONGO_URI / localhost) — wire-compat proof: same code
    3. Nothing reachable → MOCK MODE — har step apna expected Cosmos
       behavior print karta hai (interview-prep value bina infra ke)

Cosmos emulator setup (agar try karna ho):
    Windows emulator (classic) — Mongo endpoint enable karna padta hai:
        .\\CosmosDB.Emulator.exe /EnableMongoDbEndpoint=4.0
    Connection string (well-known emulator key, sabke liye same):
        mongodb://localhost:C2y6yDjf5%2FR%2Bob0N8A7Cgv30VRDJIWEHLM%2B4QDU5DE2nQ9nDuVTqobD4b8mGGyPMbIZnqyMsEcaGQy67XIw%2FJw%3D%3D@localhost:10255/admin?ssl=true&retrywrites=false
    NOTE: Linux/Docker emulator historically sirf NoSQL API deta hai —
    Mongo endpoint ke liye Windows emulator ya real account (free tier:
    1000 RU/s + 25GB) ya vCore free tier use karo.

Gotchas is file me LIVE dikhte hain (theory lesson section 7):
    - retrywrites=false connection-string requirement
    - error 16500 (= HTTP 429 throttling) retry handling
    - getLastRequestStatistics — per-op RU charge (Cosmos ka explain())
    - customAction: CreateCollection — shard key + throughput via Mongo API
"""

import os
import sys
import time
import random
from datetime import datetime, timezone

# ── DEPENDENCIES CHECK ──
try:
    from pymongo import MongoClient, ASCENDING
    from pymongo.errors import (
        ConnectionFailure,
        ServerSelectionTimeoutError,
        OperationFailure,
        WriteError,
    )
except ImportError:
    print("ERROR: pymongo not installed. Run: pip install pymongo")
    sys.exit(1)

# ── CONFIGURATION ──
# Cosmos connection strings ALWAYS look like this (note the differences
# from a vanilla MongoDB URI — yeh khud me ek interview talking point hai):
#   - port 10255 (not 27017)
#   - ssl=true mandatory
#   - retrywrites=false (classic RU-based Cosmos does NOT support
#     retryable writes; pymongo 4+ defaults to true → connect/write fail)
#   - username = account name, password = account key
COSMOS_URI = os.getenv("COSMOS_MONGO_URI", "")
LOCAL_URI = os.getenv(
    "MONGO_URI",
    "mongodb://localhost:27017/?directConnection=true",
)

DB_NAME = "cosmos_lab"
COLL_NAME = "orders"
SEPARATOR = "=" * 70

# Cosmos throttling error code — MongoDB API me HTTP 429 iske roop me aata
# hai. Real MongoDB me yeh code exist nahi karta.
COSMOS_THROTTLE_CODE = 16500


def print_section(title: str) -> None:
    print(f"\n{SEPARATOR}\n  {title}\n{SEPARATOR}")


# ==========================================================================
# 1. CONNECTION MODE DETECTION — cosmos / local mongo / mock
# ==========================================================================
# Graceful degradation: pehle Cosmos try karo, phir local MongoDB (proof
# that the code is identical), warna mock mode me concepts print karo.

def try_connect(uri: str, label: str):
    """Short-timeout connect attempt. Returns client ya None."""
    if not uri:
        return None
    try:
        client = MongoClient(uri, serverSelectionTimeoutMS=3000)
        client.admin.command("ping")
        print(f"[OK] Connected to {label}")
        return client
    except (ConnectionFailure, ServerSelectionTimeoutError, OperationFailure) as e:
        print(f"[SKIP] {label} not reachable: {type(e).__name__}")
        return None


def detect_mode():
    """
    Returns (mode, client):
        mode = 'cosmos' | 'mongo' | 'mock'
    Cosmos detection: buildInfo/hello response me Cosmos apna version
    string alag deta hai, but sabse reliable cheap check =
    getLastRequestStatistics command sirf Cosmos me exist karta hai.
    """
    client = try_connect(COSMOS_URI, "Cosmos DB (COSMOS_MONGO_URI)")
    if client is not None:
        return "cosmos", client

    client = try_connect(LOCAL_URI, "local MongoDB")
    if client is not None:
        print("     → Wire-compat demo: SAME code chalega, Cosmos-only "
              "commands gracefully skip honge.")
        return "mongo", client

    print("[MOCK] No database reachable — running in mock/teaching mode.")
    return "mock", None


# ==========================================================================
# 2. RETRY DECORATOR — error 16500 (429) handling
# ==========================================================================
# Theory lesson section 2: RU budget exceed → HTTP 429 → Mongo error 16500.
# Generic Mongo retry logic isko nahi pakadta (code Mongo me exist nahi
# karta), isliye Cosmos-aware backoff explicitly likhna padta hai.

def cosmos_retry(max_attempts: int = 5, base_delay: float = 0.5):
    """Exponential backoff + jitter for Cosmos throttling (16500)."""
    def decorator(fn):
        def wrapper(*args, **kwargs):
            for attempt in range(1, max_attempts + 1):
                try:
                    return fn(*args, **kwargs)
                except (OperationFailure, WriteError) as e:
                    if getattr(e, "code", None) != COSMOS_THROTTLE_CODE:
                        raise  # not throttling — real error, don't mask it
                    if attempt == max_attempts:
                        raise
                    # Production: RetryAfterMs error detail respect karo
                    # agar available ho; yahan exponential + jitter.
                    delay = base_delay * (2 ** (attempt - 1)) + random.uniform(0, 0.1)
                    print(f"    [429/16500] throttled — retry {attempt}/"
                          f"{max_attempts} after {delay:.2f}s")
                    time.sleep(delay)
        return wrapper
    return decorator


# ==========================================================================
# 3. COLLECTION SETUP — Cosmos extension command vs plain Mongo
# ==========================================================================
# Cosmos Mongo API me collection-level RU + shard (partition) key set
# karne ka tarika = customAction extension command. Real MongoDB is
# command ko nahi samajhta — isliye guarded.

def setup_collection(db, mode: str):
    print_section("SETUP: collection with shard key (partition key)")

    db.drop_collection(COLL_NAME)

    if mode == "cosmos":
        # Partition key = /user_id, throughput 400 RU/s (minimum).
        # Yeh 'sh.shardCollection' ka Cosmos-flavored equivalent hai —
        # theory lesson section 3: shard key ↔ partition key.
        try:
            db.command({
                "customAction": "CreateCollection",
                "collection": COLL_NAME,
                "shardKey": "user_id",
                "offerThroughput": 400,
            })
            print("[cosmos] Created collection: partition key=/user_id, 400 RU/s")
        except OperationFailure as e:
            print(f"[cosmos] customAction failed ({e.code}): {e.details}")
            print("         (serverless account? throughput param hata do)")
            db.create_collection(COLL_NAME)
    else:
        db.create_collection(COLL_NAME)
        print(f"[{mode}] Plain create_collection — real MongoDB me shard key "
              "sh.shardCollection() se lagti (lesson 04).")

    # GOTCHA (theory section 7.4): Cosmos me unique index sirf EMPTY
    # collection pe ban sakta hai. Isliye setup me hi banao — data ke
    # baad yeh operation Cosmos me fail ho jaata hai (Mongo me nahi).
    db[COLL_NAME].create_index(
        [("user_id", ASCENDING), ("order_no", ASCENDING)],
        unique=True,
        name="uniq_user_order",
    )
    print("[OK] Unique index created BEFORE inserting data "
          "(Cosmos requires empty collection for this)")

    # GOTCHA (theory section 7.3): Cosmos RU-based me non-indexed sort
    # FAIL hota hai (Mongo in-memory sort kar leta). Sort field pe index:
    db[COLL_NAME].create_index([("created_at", ASCENDING)], name="idx_created")
    print("[OK] Index on created_at — Cosmos me iske bina "
          ".sort('created_at') query hi fail ho jaati")


# ==========================================================================
# 4. CRUD — THE WIRE-COMPATIBILITY PROOF
# ==========================================================================
# Yeh section me EK BHI line Cosmos-specific nahi hai. Yehi point hai:
# pymongo skills transfer as-is. (Interview line: "my MongoDB code ran
# against Cosmos unchanged — only ops/index/RU semantics differed.")

@cosmos_retry()
def insert_orders(coll, n: int = 20):
    docs = [
        {
            "user_id": f"user_{i % 5}",         # 5 logical partitions
            "order_no": i,
            "amount": round(random.uniform(100, 5000), 2),
            "status": random.choice(["paid", "pending", "refunded"]),
            "created_at": datetime.now(timezone.utc),
        }
        for i in range(n)
    ]
    result = coll.insert_many(docs)
    return len(result.inserted_ids)


@cosmos_retry()
def query_in_partition(coll):
    """
    Filter me user_id (shard/partition key) hai → Cosmos me IN-PARTITION
    query (cheap, targeted). Lesson 04 ka 'targeted query' — same concept.
    """
    return list(coll.find({"user_id": "user_1", "status": "paid"}))


@cosmos_retry()
def query_cross_partition(coll):
    """
    Partition key filter me NAHI hai → Cosmos me CROSS-PARTITION fan-out.
    Chalega, lekin RU charge partition count ke saath multiply hota hai.
    MongoDB ka scatter-gather — wahi cost model, RU-billed.
    """
    return list(
        coll.find({"status": "paid"}).sort("created_at", ASCENDING).limit(5)
    )


def run_crud(db, mode: str):
    print_section("CRUD: identical pymongo code (the whole point)")
    coll = db[COLL_NAME]

    inserted = insert_orders(coll)
    print(f"[OK] insert_many: {inserted} docs (user_id spreads over 5 "
          "logical partitions)")

    targeted = query_in_partition(coll)
    print(f"[OK] IN-PARTITION query (user_id in filter): {len(targeted)} docs "
          "— cheap RU charge")

    fanout = query_cross_partition(coll)
    print(f"[OK] CROSS-PARTITION query (no partition key): {len(fanout)} docs "
          "— RU charge x partition count")

    # Unique index enforcement — works same on both engines
    try:
        coll.insert_one({
            "user_id": "user_1", "order_no": 1,   # duplicate of existing
            "amount": 1.0, "status": "paid",
            "created_at": datetime.now(timezone.utc),
        })
        print("[??] Duplicate insert succeeded — unique index missing?")
    except (WriteError, OperationFailure) as e:
        # DuplicateKeyError is a WriteError subclass; Cosmos code differs
        print(f"[OK] Duplicate blocked by unique index (code={e.code})")


# ==========================================================================
# 5. RU CHARGE INSPECTION — Cosmos ka explain()
# ==========================================================================
# getLastRequestStatistics = Cosmos-only extension command: pichhle
# operation ka RU charge deta hai. Theory lesson: high RU = bad index /
# cross-partition query. Real MongoDB me command exist nahi karta → guard.

def show_ru_charge(db, mode: str):
    print_section("RU CHARGE: getLastRequestStatistics (Cosmos-only)")

    if mode != "cosmos":
        print(f"[{mode}] Command not available outside Cosmos. What you'd see:")
        print("""
    > db.command({"getLastRequestStatistics": 1})
    {
        "CommandName": "find",
        "RequestCharge": 2.79,        <- RU charge of the LAST operation
        "RequestDurationInMilliSeconds": 4.0,
        ...
    }
    Interpretation cheatsheet:
      point read ~1 RU | indexed in-partition find: single digits
      cross-partition + no index: 10s-100s of RU  → fix index/PK, not budget
""")
        return

    coll = db[COLL_NAME]
    coll.find_one({"user_id": "user_1"})
    stats = db.command({"getLastRequestStatistics": 1})
    print(f"[cosmos] In-partition find_one  → {stats.get('RequestCharge')} RU")

    list(coll.find({"status": "paid"}))
    stats = db.command({"getLastRequestStatistics": 1})
    print(f"[cosmos] Cross-partition find   → {stats.get('RequestCharge')} RU")
    print("Compare the two numbers — that gap IS the partition-key lesson.")


# ==========================================================================
# 6. MOCK MODE — full walkthrough when no DB is reachable
# ==========================================================================

def run_mock():
    print_section("MOCK MODE: what each step does against real Cosmos")
    print("""
1. CONNECTION
   URI shape:  mongodb://<account>:<key>@<account>.mongo.cosmos.azure.com:10255/
               ?ssl=true&retrywrites=false&maxIdleTimeMS=120000
   - port 10255, TLS mandatory
   - retrywrites=false  ← #1 day-one failure with pymongo 4+ defaults

2. COLLECTION SETUP (Cosmos extension command over Mongo wire)
   db.command({customAction: "CreateCollection", collection: "orders",
               shardKey: "user_id", offerThroughput: 400})
   → partition key /user_id, 400 RU/s dedicated throughput
   → unique indexes MUST be created now, while empty (Cosmos rule)
   → index every sort field — non-indexed sort FAILS on Cosmos RU

3. CRUD — identical pymongo calls (wire-compat proof)
   insert_many / find / sort / unique-index violation → same code as
   01_pymongo_basics.py. Only differences observable:
   - error 16500 when RU budget exceeded (handle with backoff)
   - in-partition vs cross-partition RU gap in getLastRequestStatistics

4. RU INSPECTION
   db.command({getLastRequestStatistics: 1}) → RequestCharge per op.
   Treat like explain(): high charge = missing index or missing
   partition key in filter — fix the query before raising RU/s.

5. WHAT WON'T PORT (test before claiming a migration works)
   - multi-doc transactions beyond a single partition (RU-based)
   - change streams: no deletes, limited pipeline
   - $graphLookup / parts of the aggregation surface
   - capped collections
""")
    print("Setup options to run this for real:")
    print("  a) Azure free tier: Cosmos DB account (Mongo API) — 1000 RU/s free")
    print("  b) Windows emulator: CosmosDB.Emulator.exe /EnableMongoDbEndpoint=4.0")
    print("  c) export COSMOS_MONGO_URI='mongodb://...' then re-run this file")
    print("  d) Or just start local MongoDB — the code path is identical\n")


# ==========================================================================
# 7. MAIN
# ==========================================================================

def main() -> None:
    print("Cosmos DB via MongoDB API — wire-compatibility practical")
    print("(theory: ../theory/10_cosmos_db_azure.md | mode auto-detected)")

    mode, client = detect_mode()

    if mode == "mock":
        run_mock()
        print("SOCH (bolke jawab do):")
        print("  1. Same pymongo code Cosmos pe kyun chal jaata hai lekin")
        print("     'same database' phir bhi kyun nahi hai? (engine vs wire)")
        print("  2. 16500 retry decorator me sirf throttle code pe retry")
        print("     kyun — saare OperationFailure pe kyun nahi?")
        print("  3. Unique index ko setup me hi kyun banaya, data ke baad kyun nahi?")
        return

    db = client[DB_NAME]
    try:
        setup_collection(db, mode)
        run_crud(db, mode)
        show_ru_charge(db, mode)
    finally:
        # Lab hygiene — Cosmos me idle collections bhi RU/s bill karti hain
        # (provisioned mode me), isliye cleanup meaningful hai, sirf polite nahi.
        db.drop_collection(COLL_NAME)
        client.close()
        print(f"\n[OK] Cleaned up ({DB_NAME}.{COLL_NAME} dropped). Done.")

    print("""
SOCH (bolke jawab do):
  1. In-partition vs cross-partition query ka RU gap kis MongoDB concept
     ka mirror hai? (Hint: lesson 04 — targeted vs scatter-gather)
  2. retrywrites=false kyun chahiye classic Cosmos pe, aur iska matlab
     tumhare write-error handling ke liye kya hai?
  3. Agar production me 16500 errors aa rahe hain lekin overall RU
     utilization 30% hai — sabse likely diagnosis kya hai?
     (Hint: RU/s evenly split across physical partitions)
""")


if __name__ == "__main__":
    main()
