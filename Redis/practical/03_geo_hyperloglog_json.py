"""
Redis Practical 03 — Geospatial, HyperLogLog & RedisJSON
Run: python 03_geo_hyperloglog_json.py [geo|hyperloglog|json|all]

Prerequisites:
  pip install redis[hiredis]
  docker run -d --name redis-stack -p 6379:6379 redis/redis-stack-server:latest
  (redis-stack required for RedisJSON module)
"""

import asyncio
import json
import time
import sys
import redis
import redis.asyncio as aioredis

r = redis.Redis(host='localhost', port=6379, decode_responses=True)


# ════════════════════════════════════════════
# SECTION 1: GEOSPATIAL
# ════════════════════════════════════════════
def demo_geospatial():
    print("\n" + "="*50)
    print("  SECTION 1: GEOSPATIAL")
    print("="*50)

    # ─── GEOADD — locations store karo ───
    # Format: (longitude, latitude, name)  ← NOTE: lng first, then lat!
    r.geoadd("restaurants:mumbai", [
        (72.8777, 19.0760, "Pizza Palace"),      # Mumbai Andheri
        (72.8856, 19.0821, "Burger Barn"),        # Nearby
        (72.8650, 19.0701, "Sushi Station"),      # 2km away
        (72.9005, 19.0900, "Dosa Delight"),       # 3km away
        (72.8100, 19.0500, "Idli Inn"),           # Far
    ])
    r.geoadd("restaurants:delhi", [
        (77.2090, 28.6139, "Delhi Dhaba"),        # Delhi — completely different city
        (77.2167, 28.6208, "Curry Castle"),
    ])

    print(f"✅ Added Mumbai restaurants: {r.zcard('restaurants:mumbai')}")
    print(f"✅ Added Delhi restaurants: {r.zcard('restaurants:delhi')}")

    # ─── GEOPOS — coordinates fetch karo ───
    positions = r.geopos("restaurants:mumbai", "Pizza Palace", "Burger Barn")
    print("\n📍 GEOPOS:")
    for name, pos in zip(["Pizza Palace", "Burger Barn"], positions):
        if pos:
            print(f"  {name}: lng={pos[0]:.4f}, lat={pos[1]:.4f}")

    # ─── GEODIST — 2 locations ke beech distance ───
    dist_km = r.geodist("restaurants:mumbai", "Pizza Palace", "Burger Barn", unit="km")
    dist_m  = r.geodist("restaurants:mumbai", "Pizza Palace", "Sushi Station", unit="m")
    print(f"\n📏 GEODIST:")
    print(f"  Pizza Palace → Burger Barn: {dist_km:.3f} km")
    print(f"  Pizza Palace → Sushi Station: {dist_m:.0f} m")

    # ─── GEOSEARCH by radius ───
    print(f"\n🔍 GEOSEARCH — User at (72.88, 19.08), radius 2km:")
    nearby = r.geosearch(
        "restaurants:mumbai",
        longitude=72.88,
        latitude=19.08,
        radius=2,
        unit="km",
        sort="ASC",         # nearest first
        count=5,
        withcoord=True,     # coordinates include
        withdist=True,      # distance include
    )
    for item in nearby:
        name = item[0]
        dist = item[1]
        coord = item[2]
        print(f"  {name:<20} {dist:.3f}km away  (lng={coord[0]:.4f}, lat={coord[1]:.4f})")

    # ─── GEOSEARCH by bounding box ───
    print(f"\n📦 GEOSEARCH — Bounding Box (5km x 5km):")
    box_results = r.geosearch(
        "restaurants:mumbai",
        longitude=72.88,
        latitude=19.08,
        width=5,
        height=5,
        unit="km",
        sort="ASC",
    )
    print(f"  Found: {box_results}")

    # ─── GEOSEARCHSTORE — result ko dusri key mein store karo ───
    r.geosearchstore(
        "nearby:restaurants:cache",   # destination
        "restaurants:mumbai",          # source
        longitude=72.88,
        latitude=19.08,
        radius=2,
        unit="km",
        storedist=True,               # distance bhi store karo (as score)
    )
    cached = r.zrange("nearby:restaurants:cache", 0, -1, withscores=True)
    print(f"\n💾 GEOSEARCHSTORE result: {cached}")

    # ─── GEOHASH — encoded string ───
    hashes = r.geohash("restaurants:mumbai", "Pizza Palace", "Burger Barn")
    print(f"\n🔢 GEOHASH: {hashes}")
    # Same prefix = nearby locations (longer prefix = more precise)

    # ─── Real-world pattern: Rider tracking ───
    print("\n🚗 Real-world: Ride Tracking")
    # Drivers ka location update karo
    drivers = [
        (72.8810, 19.0780, "driver:D001"),
        (72.8820, 19.0790, "driver:D002"),
        (72.8900, 19.0850, "driver:D003"),
        (73.0000, 19.1200, "driver:D004"),  # Far away
    ]
    r.geoadd("drivers:active", drivers)

    # User ka nearest driver dhundo
    user_lng, user_lat = 72.882, 19.079
    nearby_drivers = r.geosearch(
        "drivers:active",
        longitude=user_lng,
        latitude=user_lat,
        radius=1.5,
        unit="km",
        sort="ASC",
        count=3,
        withdist=True,
    )
    print(f"  User at ({user_lng}, {user_lat}) — Nearby drivers (1.5km):")
    for driver in nearby_drivers:
        print(f"    {driver[0]}: {driver[1]:.3f}km away")

    # Cleanup
    r.delete("restaurants:mumbai", "restaurants:delhi",
             "nearby:restaurants:cache", "drivers:active")
    print("\n✅ Geospatial demo complete!")


# ════════════════════════════════════════════
# SECTION 2: HYPERLOGLOG
# ════════════════════════════════════════════
def demo_hyperloglog():
    print("\n" + "="*50)
    print("  SECTION 2: HYPERLOGLOG")
    print("="*50)

    # ─── PFADD — elements add karo ───
    print("\n📊 Basic HyperLogLog:")
    r.pfadd("visitors:2024-01-15", "user:1001", "user:1002", "user:1003")
    r.pfadd("visitors:2024-01-15", "user:1001")  # duplicate — count nahi badhega
    r.pfadd("visitors:2024-01-15", "user:1004", "user:1005")

    # ─── PFCOUNT — unique count ───
    count = r.pfcount("visitors:2024-01-15")
    print(f"  Added 6 (with 1 dup) → Unique count: {count}")

    # ─── Large scale test ───
    print("\n📈 Large Scale Test:")
    # 10,000 unique users simulate
    r.delete("hll:large:test")
    batch_size = 500
    for batch_start in range(0, 5000, batch_size):
        users = [f"user:{i}" for i in range(batch_start, batch_start + batch_size)]
        r.pfadd("hll:large:test", *users)

    actual   = 5000
    approx   = r.pfcount("hll:large:test")
    error    = abs(approx - actual) / actual * 100
    mem      = r.memory_usage("hll:large:test")
    print(f"  Actual unique: {actual}")
    print(f"  HLL estimate:  {approx}")
    print(f"  Error rate:    {error:.2f}% (expected ~0.81%)")
    print(f"  Memory used:   {mem} bytes (~{mem/1024:.1f} KB)")

    # Compare: Set would use much more memory
    # r.sadd("exact:test", *[f"user:{i}" for i in range(5000)])
    # Much more memory for 5000 string members

    # ─── Multiple days merge ───
    print("\n📅 Multi-day Unique Visitors:")
    r.delete("visitors:day1", "visitors:day2", "visitors:day3")

    # Day 1: users 0-999
    r.pfadd("visitors:day1", *[f"user:{i}" for i in range(1000)])
    # Day 2: users 500-1499 (500 overlap with day1)
    r.pfadd("visitors:day2", *[f"user:{i}" for i in range(500, 1500)])
    # Day 3: users 1200-1699 (some overlap)
    r.pfadd("visitors:day3", *[f"user:{i}" for i in range(1200, 1700)])

    day1_unique = r.pfcount("visitors:day1")
    day2_unique = r.pfcount("visitors:day2")
    day3_unique = r.pfcount("visitors:day3")

    # Multi-key PFCOUNT — union count
    three_day_unique = r.pfcount("visitors:day1", "visitors:day2", "visitors:day3")

    print(f"  Day 1 unique: ~{day1_unique}")
    print(f"  Day 2 unique: ~{day2_unique}")
    print(f"  Day 3 unique: ~{day3_unique}")
    print(f"  3-day total unique: ~{three_day_unique} (actual: ~1700)")

    # ─── PFMERGE — merge into new key ───
    r.pfmerge("visitors:weekly", "visitors:day1", "visitors:day2", "visitors:day3")
    weekly = r.pfcount("visitors:weekly")
    print(f"\n🔀 PFMERGE weekly unique: ~{weekly}")

    # ─── Production pattern: Page-level tracking ───
    print("\n🌐 Production Pattern: Page Analytics")

    def track_page_view(user_id: str, page: str):
        today = "2024-01-15"
        pipe = r.pipeline()
        pipe.pfadd(f"unique:page:{page}:{today}", user_id)
        pipe.pfadd(f"unique:site:{today}", user_id)
        pipe.expire(f"unique:page:{page}:{today}", 7 * 86400)  # 7 days
        pipe.expire(f"unique:site:{today}", 7 * 86400)
        pipe.execute()

    # Simulate visits
    pages = ["home", "products", "home", "checkout", "products", "home"]
    users = ["u1", "u2", "u1", "u3", "u2", "u4"]
    for user, page in zip(users, pages):
        track_page_view(user, page)

    today = "2024-01-15"
    home_unique     = r.pfcount(f"unique:page:home:{today}")
    products_unique = r.pfcount(f"unique:page:products:{today}")
    site_unique     = r.pfcount(f"unique:site:{today}")
    print(f"  Home page unique: {home_unique}")
    print(f"  Products page unique: {products_unique}")
    print(f"  Site-wide unique: {site_unique}")

    # Cleanup
    r.delete("visitors:2024-01-15", "hll:large:test",
             "visitors:day1", "visitors:day2", "visitors:day3", "visitors:weekly")
    for key in r.scan_iter("unique:*"):
        r.delete(key)
    print("\n✅ HyperLogLog demo complete!")


# ════════════════════════════════════════════
# SECTION 3: REDIS JSON
# ════════════════════════════════════════════
def demo_redis_json():
    print("\n" + "="*50)
    print("  SECTION 3: REDIS JSON")
    print("="*50)

    # Check if RedisJSON is available
    try:
        r.json().set("test:json:check", "$", {"test": True})
        r.delete("test:json:check")
    except Exception as e:
        print(f"⚠️  RedisJSON not available: {e}")
        print("   Use: docker run -d -p 6379:6379 redis/redis-stack-server:latest")
        return

    # ─── JSON.SET — Store full JSON ───
    print("\n📦 JSON.SET — Store:")
    user = {
        "id":      1,
        "name":    "Alice",
        "email":   "alice@example.com",
        "age":     25,
        "address": {
            "city":    "Mumbai",
            "state":   "Maharashtra",
            "pincode": "400001"
        },
        "skills": ["Python", "FastAPI", "Redis"],
        "score":   95.5,
        "active":  True,
        "tags":    ["developer", "senior"],
    }
    r.json().set("user:json:1", "$", user)
    print("  ✅ User JSON stored at user:json:1")

    # ─── JSON.GET — Fetch ───
    print("\n📖 JSON.GET — Fetch:")
    full = r.json().get("user:json:1", "$")
    name = r.json().get("user:json:1", "$.name")
    city = r.json().get("user:json:1", "$.address.city")
    skills = r.json().get("user:json:1", "$.skills")
    print(f"  Full (abbreviated): id={full[0]['id']}, name={full[0]['name']}")
    print(f"  Name only: {name}")
    print(f"  City only: {city}")
    print(f"  Skills: {skills}")

    # Multiple paths ek call mein
    result = r.json().get("user:json:1", "$.name", "$.age", "$.address.city")
    print(f"  Multi-path: {result}")

    # ─── JSON.SET — Update specific field ───
    print("\n✏️  JSON.SET — Update Fields:")
    r.json().set("user:json:1", "$.age", 26)
    r.json().set("user:json:1", "$.address.city", "Pune")
    r.json().set("user:json:1", "$.active", False)
    print(f"  Updated age: {r.json().get('user:json:1', '$.age')}")
    print(f"  Updated city: {r.json().get('user:json:1', '$.address.city')}")

    # ─── JSON.NUMINCRBY — Numeric increment ───
    print("\n🔢 JSON.NUMINCRBY:")
    new_score = r.json().numincrby("user:json:1", "$.score", 4.5)
    new_age = r.json().numincrby("user:json:1", "$.age", 1)
    print(f"  Score: 95.5 + 4.5 = {new_score}")
    print(f"  Age: 26 + 1 = {new_age}")

    # ─── JSON.ARRAPPEND — Array append ───
    print("\n📝 JSON.ARRAPPEND:")
    r.json().arrappend("user:json:1", "$.skills", "LangChain", "Docker")
    skills_updated = r.json().get("user:json:1", "$.skills")
    print(f"  Skills after append: {skills_updated}")

    # ─── JSON.ARRLEN — Array length ───
    print("\n📏 JSON.ARRLEN:")
    length = r.json().arrlen("user:json:1", "$.skills")
    print(f"  Skills count: {length}")

    # ─── JSON.ARRINDEX — Find in array ───
    index = r.json().arrindex("user:json:1", "$.skills", "FastAPI")
    print(f"  FastAPI index in skills: {index}")

    # ─── JSON.ARRPOP — Remove from array ───
    popped = r.json().arrpop("user:json:1", "$.skills", -1)  # last element
    print(f"  Popped last skill: {popped}")

    # ─── JSON.ARRTRIM — Trim array ───
    r.json().arrtrim("user:json:1", "$.skills", 0, 2)  # keep first 3
    print(f"  After ARRTRIM: {r.json().get('user:json:1', '$.skills')}")

    # ─── JSON.DEL — Delete field ───
    print("\n🗑️  JSON.DEL:")
    r.json().delete("user:json:1", "$.address.pincode")
    print(f"  Address after del pincode: {r.json().get('user:json:1', '$.address')}")

    # ─── JSON.TYPE — Field type check ───
    print("\n🔍 JSON.TYPE:")
    print(f"  $.name type:   {r.json().type('user:json:1', '$.name')}")
    print(f"  $.age type:    {r.json().type('user:json:1', '$.age')}")
    print(f"  $.score type:  {r.json().type('user:json:1', '$.score')}")
    print(f"  $.skills type: {r.json().type('user:json:1', '$.skills')}")
    print(f"  $.address type:{r.json().type('user:json:1', '$.address')}")
    print(f"  $.active type: {r.json().type('user:json:1', '$.active')}")

    # ─── JSON.MSET / MGET — Multiple JSONs ───
    print("\n📦 JSON.MSET / MGET:")
    products = [
        {"id": i, "name": f"Product {i}", "price": 100 * i, "stock": 50}
        for i in range(1, 5)
    ]
    for p in products:
        r.json().set(f"product:json:{p['id']}", "$", p)

    # Mget — multiple keys ek saath
    product_ids = [1, 2, 3, 4]
    fetched = [r.json().get(f"product:json:{pid}", "$") for pid in product_ids]
    for pid, data in zip(product_ids, fetched):
        if data:
            print(f"  Product {pid}: {data[0]['name']} @ ₹{data[0]['price']}")

    # ─── JSON with Pipeline ───
    print("\n⚡ JSON with Pipeline (Bulk ops):")
    pipe = r.pipeline()
    for i in range(1, 5):
        pipe.json().numincrby(f"product:json:{i}", "$.stock", -5)  # 5 items sold
    results = pipe.execute()
    print(f"  Stock after pipeline decrement: {results}")

    # ─── Nested JSON update ───
    print("\n🌳 Nested JSON Update:")
    config = {
        "app": {
            "name":    "MyApp",
            "version": "1.0.0",
            "settings": {
                "debug":       False,
                "max_workers": 4,
                "log_level":   "INFO",
                "features": {
                    "dark_mode": True,
                    "beta":      False,
                }
            }
        }
    }
    r.json().set("config:app", "$", config)
    r.json().set("config:app", "$.app.settings.debug", True)
    r.json().numincrby("config:app", "$.app.settings.max_workers", 2)
    r.json().set("config:app", "$.app.settings.features.beta", True)

    debug    = r.json().get("config:app", "$.app.settings.debug")
    workers  = r.json().get("config:app", "$.app.settings.max_workers")
    beta     = r.json().get("config:app", "$.app.settings.features.beta")
    print(f"  debug: {debug}, max_workers: {workers}, beta: {beta}")

    # ─── String+JSON comparison ───
    print("\n⚖️  String+JSON vs RedisJSON comparison:")
    # String+JSON — update age (4 steps)
    start = time.time()
    for _ in range(100):
        raw = r.get("string:user") or json.dumps({"name": "Alice", "age": 25, "score": 90})
        data = json.loads(raw)
        data["age"] += 1
        r.set("string:user", json.dumps(data))
    string_time = time.time() - start

    # RedisJSON — update age (1 step)
    r.json().set("rjson:user", "$", {"name": "Alice", "age": 25, "score": 90})
    start = time.time()
    for _ in range(100):
        r.json().numincrby("rjson:user", "$.age", 1)
    rjson_time = time.time() - start

    print(f"  String+JSON (100 age updates): {string_time:.4f}s")
    print(f"  RedisJSON  (100 age updates):  {rjson_time:.4f}s")
    print(f"  RedisJSON speedup: {string_time/rjson_time:.1f}x faster")

    # Cleanup
    r.delete("user:json:1", "config:app", "string:user", "rjson:user")
    for i in range(1, 5):
        r.delete(f"product:json:{i}")
    print("\n✅ RedisJSON demo complete!")


# ════════════════════════════════════════════
# SECTION 4: ASYNC GEO + HLL (FastAPI pattern)
# ════════════════════════════════════════════
async def demo_async_patterns():
    print("\n" + "="*50)
    print("  SECTION 4: ASYNC PATTERNS (FastAPI-style)")
    print("="*50)

    r_async = aioredis.Redis(host='localhost', port=6379, decode_responses=True)

    # ─── Async Geo: Driver tracking ───
    print("\n🚗 Async Driver Location Tracking:")

    async def update_driver_location(driver_id: str, lat: float, lng: float):
        await r_async.geoadd("active_drivers", [(lng, lat, driver_id)])
        await r_async.setex(f"driver:{driver_id}:last_seen", 300, str(time.time()))

    async def find_nearby_drivers(lat: float, lng: float, radius_km: float = 5.0):
        drivers = await r_async.geosearch(
            "active_drivers",
            longitude=lng,
            latitude=lat,
            radius=radius_km,
            unit="km",
            sort="ASC",
            count=10,
            withdist=True
        )
        return [{"id": d[0], "distance_km": round(float(d[1]), 3)} for d in drivers]

    # Simulate updates
    await update_driver_location("D001", 19.0760, 72.8777)
    await update_driver_location("D002", 19.0780, 72.8800)
    await update_driver_location("D003", 19.1000, 72.9100)  # Far

    nearby = await find_nearby_drivers(lat=19.0770, lng=72.8785, radius_km=2.0)
    print(f"  Nearby drivers (2km): {nearby}")

    # ─── Async HyperLogLog: Page analytics ───
    print("\n📊 Async HyperLogLog: Page Analytics:")

    async def track_visitor(user_id: str, page: str):
        today = "2024-01-15"
        async with r_async.pipeline(transaction=False) as pipe:
            pipe.pfadd(f"uv:{page}:{today}", user_id)
            pipe.pfadd(f"uv:site:{today}", user_id)
            pipe.expire(f"uv:{page}:{today}", 86400 * 7)
            pipe.expire(f"uv:site:{today}", 86400 * 7)
            await pipe.execute()

    async def get_analytics(page: str):
        today = "2024-01-15"
        page_uv = await r_async.pfcount(f"uv:{page}:{today}")
        site_uv = await r_async.pfcount(f"uv:site:{today}")
        return {"page": page, "unique_visitors": page_uv, "site_total": site_uv}

    # Simulate concurrent tracking
    track_tasks = [
        track_visitor(f"user:{i}", "home") for i in range(20)
    ] + [
        track_visitor(f"user:{i}", "products") for i in range(10, 30)
    ]
    await asyncio.gather(*track_tasks)

    home_stats = await get_analytics("home")
    products_stats = await get_analytics("products")
    print(f"  Home: {home_stats}")
    print(f"  Products: {products_stats}")

    # Cleanup
    await r_async.delete("active_drivers")
    for key in r_async.scan_iter("driver:*:last_seen"):
        await r_async.delete(key)
    async for key in r_async.scan_iter("uv:*"):
        await r_async.delete(key)

    await r_async.aclose()
    print("\n✅ Async patterns demo complete!")


# ════════════════════════════════════════════
# MAIN RUNNER
# ════════════════════════════════════════════
def main():
    try:
        r.ping()
        print("✅ Redis connected!")
    except redis.ConnectionError:
        print("❌ Redis not running!")
        print("   For JSON: docker run -d -p 6379:6379 redis/redis-stack-server:latest")
        sys.exit(1)

    cmd = sys.argv[1] if len(sys.argv) > 1 else "all"

    sync_demos = {
        "geo":        demo_geospatial,
        "hyperloglog": demo_hyperloglog,
        "json":        demo_redis_json,
    }

    if cmd == "all":
        for fn in sync_demos.values():
            fn()
        asyncio.run(demo_async_patterns())
    elif cmd == "async":
        asyncio.run(demo_async_patterns())
    elif cmd in sync_demos:
        sync_demos[cmd]()
    else:
        print(f"Usage: python {sys.argv[0]} [{'|'.join(sync_demos.keys())}|async|all]")


if __name__ == "__main__":
    main()
