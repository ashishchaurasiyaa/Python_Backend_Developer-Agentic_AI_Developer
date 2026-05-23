# Redis — Geospatial, HyperLogLog & RedisJSON
**Intermediate to Advanced | What, Why, How**

---

## Quick Concepts
- **Geospatial** = Location data store — lat/lng, distance, nearby search
- **HyperLogLog** = Approximate unique count — billion items, 12KB memory
- **RedisJSON** = JSON natively store/query — serialize/deserialize nahi karna
- **GEOADD** = Location add karo
- **GEODIST** = 2 points ke beech distance
- **GEOSEARCH** = Radius ke andar sab locations
- **PFADD/PFCOUNT** = HyperLogLog add/count

---

## Interview Questions & Answers

---

### Q1: Redis Geospatial kya hai? Kab use karo?

**Answer:**
```
Use cases:
  - Delivery app: nearest rider find karo
  - Food app: nearby restaurants
  - Ride hailing: drivers within 5km
  - Store locator: nearest branch
  - Dating app: users within radius

How it works:
  Redis internally Sorted Set use karta hai
  Geohash = lat/lng → single number (score)
  → Sorted Set pe range queries geography ke liye work karte hain
```

```python
import redis
r = redis.Redis(host='localhost', port=6379, decode_responses=True)

# ─── GEOADD — locations add karo ───
r.geoadd("restaurants", [
    (72.8777, 19.0760, "Pizza Palace"),     # Mumbai (lng, lat, name)
    (72.8856, 19.0821, "Burger Barn"),
    (72.8650, 19.0701, "Sushi Station"),
    (72.9005, 19.0900, "Dosa Delight"),
    (77.2090, 28.6139, "Delhi Dhaba"),      # Delhi — far away
])

# ─── GEODIST — 2 locations ke beech distance ───
dist_km = r.geodist("restaurants", "Pizza Palace", "Burger Barn", unit="km")
dist_m  = r.geodist("restaurants", "Pizza Palace", "Sushi Station", unit="m")
print(f"Pizza Palace → Burger Barn: {dist_km:.2f} km")
print(f"Pizza Palace → Sushi Station: {dist_m:.0f} m")

# ─── GEOPOS — location coordinates lo ───
positions = r.geopos("restaurants", "Pizza Palace", "Burger Barn")
for name, pos in zip(["Pizza Palace", "Burger Barn"], positions):
    if pos:
        print(f"{name}: lng={pos[0]:.4f}, lat={pos[1]:.4f}")

# ─── GEOSEARCH — radius ke andar sab dhundo ───
# User location: 72.88, 19.08 (Mumbai)
nearby = r.geosearch(
    "restaurants",
    longitude=72.88,
    latitude=19.08,
    radius=2,            # 2 km radius
    unit="km",
    sort="ASC",          # nearest first
    count=5,             # max 5 results
    withcoord=True,      # coordinates include
    withdist=True,       # distance include
)
print("\nNearby restaurants (within 2km):")
for item in nearby:
    name, dist, coord = item
    print(f"  {name}: {dist:.2f}km away")

# ─── GEOSEARCH by bounding box ───
box_results = r.geosearch(
    "restaurants",
    longitude=72.88,
    latitude=19.08,
    width=5,    # 5km wide box
    height=5,   # 5km tall box
    unit="km",
    sort="ASC"
)
print(f"\nIn bounding box: {box_results}")

# ─── GEOHASH — Geohash value lo ───
hashes = r.geohash("restaurants", "Pizza Palace", "Burger Barn")
print(f"\nGeohashes: {hashes}")
# geohash = location ka encoded string — share karne ke liye
```

**FastAPI integration:**
```python
from fastapi import FastAPI, Query
import redis.asyncio as aioredis

app = FastAPI()
redis_client = aioredis.Redis(host='localhost', decode_responses=True)

@app.post("/drivers/{driver_id}/location")
async def update_driver_location(
    driver_id: str,
    lat: float = Query(...),
    lng: float = Query(...)
):
    """Driver ka live location update karo"""
    await redis_client.geoadd("active_drivers", [(lng, lat, driver_id)])
    # TTL set karo — driver offline → expire
    await redis_client.expire(f"driver:{driver_id}:active", 300)  # 5 min
    return {"status": "location updated"}

@app.get("/drivers/nearby")
async def find_nearby_drivers(
    lat: float = Query(...),
    lng: float = Query(...),
    radius_km: float = Query(default=5.0)
):
    """User ke paas ke drivers dhundo"""
    drivers = await redis_client.geosearch(
        "active_drivers",
        longitude=lng,
        latitude=lat,
        radius=radius_km,
        unit="km",
        sort="ASC",
        count=10,
        withdist=True
    )
    return {
        "drivers": [
            {"id": d[0], "distance_km": round(float(d[1]), 2)}
            for d in drivers
        ]
    }
```

---

### Q2: HyperLogLog kya hai? Kab use karo?

**Answer:**
```
Problem:
  Daily unique visitors count karo — millions of users
  Set mein store karo → 1M user IDs → 100MB+ RAM ❌

HyperLogLog:
  Probabilistic data structure
  ~0.81% error rate
  FIXED 12KB memory — chahe 1 billion items ho ✅
  Add karo + approximate count lo — that's it

Use cases:
  - Unique page visitors per day
  - Unique search queries
  - Unique API callers
  - AB testing — unique users per variant
  - Approximate distinct count ANY scenario
```

```python
import redis
r = redis.Redis(host='localhost', port=6379, decode_responses=True)

# ─── PFADD — elements add karo ───
r.pfadd("visitors:2024-01-15", "user:1001", "user:1002", "user:1003")
r.pfadd("visitors:2024-01-15", "user:1001")  # duplicate — count nahi badhega
r.pfadd("visitors:2024-01-15", "user:1004", "user:1005")

# ─── PFCOUNT — approximate unique count ───
count = r.pfcount("visitors:2024-01-15")
print(f"Unique visitors today: ~{count}")  # ~5

# ─── Multiple HyperLogs merge ───
r.pfadd("visitors:2024-01-15", *[f"user:{i}" for i in range(1000)])
r.pfadd("visitors:2024-01-16", *[f"user:{i}" for i in range(500, 1500)])

# Dono days ka unique count
total_unique = r.pfcount("visitors:2024-01-15", "visitors:2024-01-16")
print(f"2-day unique visitors: ~{total_unique}")

# ─── PFMERGE — merge karke ek mein store karo ───
r.pfmerge("visitors:weekly", "visitors:2024-01-15", "visitors:2024-01-16")
weekly_count = r.pfcount("visitors:weekly")
print(f"Weekly unique: ~{weekly_count}")

# ─── Real production pattern ───
import asyncio
import redis.asyncio as aioredis

async def track_unique_visitor(user_id: str, page: str, date: str):
    r = await aioredis.from_url("redis://localhost", decode_responses=True)

    # Page-level unique
    await r.pfadd(f"unique:{page}:{date}", user_id)

    # Site-wide unique
    await r.pfadd(f"unique:site:{date}", user_id)

    # TTL — 30 days rakhо
    await r.expire(f"unique:{page}:{date}", 30 * 86400)
    await r.expire(f"unique:site:{date}", 30 * 86400)
    await r.aclose()

async def get_unique_stats(page: str, date: str):
    r = await aioredis.from_url("redis://localhost", decode_responses=True)
    page_unique = await r.pfcount(f"unique:{page}:{date}")
    site_unique = await r.pfcount(f"unique:site:{date}")
    await r.aclose()
    return {"page_unique": page_unique, "site_unique": site_unique}

# Usage
asyncio.run(track_unique_visitor("user:1001", "home", "2024-01-15"))
asyncio.run(track_unique_visitor("user:1002", "home", "2024-01-15"))
stats = asyncio.run(get_unique_stats("home", "2024-01-15"))
print(stats)
```

---

### Q3: RedisJSON kya hai? Normal String se better kyu hai?

**Answer:**
```
Without RedisJSON:
  # JSON store karo
  user = {"name": "Alice", "age": 25, "city": "Mumbai"}
  r.set("user:1", json.dumps(user))     # serialize karo

  # Update age only
  data = r.get("user:1")               # 1. fetch all
  user = json.loads(data)              # 2. deserialize
  user["age"] = 26                     # 3. change one field
  r.set("user:1", json.dumps(user))    # 4. serialize + store all
  # → 4 steps + full JSON read/write for 1 field ❌

With RedisJSON:
  r.json().set("user:1", "$", user)    # store once
  r.json().set("user:1", "$.age", 26)  # update 1 field directly ✅
  age = r.json().get("user:1", "$.age")  # get 1 field only ✅
  # → Direct field access, no serialize/deserialize overhead
```

```python
# pip install redis[hiredis]
# Docker: docker run -d -p 6379:6379 redis/redis-stack-server:latest
# (redis-stack has JSON, Search, TimeSeries modules)

import redis
r = redis.Redis(host='localhost', port=6379, decode_responses=True)

# ─── JSON.SET — store JSON ───
user = {
    "id": 1,
    "name": "Alice",
    "email": "alice@test.com",
    "age": 25,
    "address": {
        "city": "Mumbai",
        "pincode": "400001"
    },
    "skills": ["Python", "FastAPI", "Redis"],
    "score": 95.5
}
r.json().set("user:1", "$", user)   # $ = root path

# ─── JSON.GET — fetch karo ───
full_user = r.json().get("user:1", "$")         # full JSON
name_only = r.json().get("user:1", "$.name")    # sirf name
city = r.json().get("user:1", "$.address.city") # nested field
print(f"Name: {name_only}")   # ['Alice']
print(f"City: {city}")        # ['Mumbai']

# ─── JSON.SET — update specific field ───
r.json().set("user:1", "$.age", 26)          # age update
r.json().set("user:1", "$.address.city", "Delhi")  # nested update

# ─── JSON.NUMINCRBY — number increment ───
r.json().numincrby("user:1", "$.score", 4.5)   # 95.5 + 4.5 = 100.0

# ─── JSON.ARRAPPEND — array mein add karo ───
r.json().arrappend("user:1", "$.skills", "LangChain", "FastAPI")
skills = r.json().get("user:1", "$.skills")
print(f"Skills: {skills}")  # ['Python', 'FastAPI', 'Redis', 'LangChain', 'FastAPI']

# ─── JSON.ARRLEN — array length ───
length = r.json().arrlen("user:1", "$.skills")
print(f"Skills count: {length}")  # [5]

# ─── JSON.DEL — field delete karo ───
r.json().delete("user:1", "$.address.pincode")

# ─── JSON.TYPE — field type check ───
field_type = r.json().type("user:1", "$.skills")  # ['array']
num_type   = r.json().type("user:1", "$.age")      # ['integer']

# ─── Multiple JSONs ───
users = [
    {"id": i, "name": f"User{i}", "score": i * 10, "active": True}
    for i in range(1, 6)
]
for user in users:
    r.json().set(f"user:{user['id']}", "$", user)

# ─── Async version ───
import redis.asyncio as aioredis
import asyncio

async def json_async_demo():
    r = await aioredis.from_url("redis://localhost", decode_responses=True)

    # Store
    product = {"id": 42, "name": "Laptop", "price": 75000, "stock": 10}
    await r.json().set("product:42", "$", product)

    # Read
    price = await r.json().get("product:42", "$.price")
    print(f"Price: {price}")

    # Update stock
    await r.json().numincrby("product:42", "$.stock", -1)
    stock = await r.json().get("product:42", "$.stock")
    print(f"Remaining stock: {stock}")

    await r.aclose()

asyncio.run(json_async_demo())
```

---

### Q4: Kab RedisJSON use karo vs normal String JSON?

**Answer:**
```
Use RedisJSON when:
  ✅ Frequently partial updates chahiye (ek field change)
  ✅ Nested data query/filter karna hai
  ✅ Array operations (append, length, index)
  ✅ Type-safe field access
  ✅ RediSearch ke saath index karna hai

Use String+JSON when:
  ✅ Simple kaam — store + full fetch only
  ✅ Redis Stack module nahi hai (basic Redis)
  ✅ Small JSON — serialize overhead negligible
  ✅ Always full object read/write karna hai

Production tip:
  redis-stack image use karo (JSON + Search built-in)
  docker pull redis/redis-stack-server
```

---

## Summary Table

```
┌───────────────────────────────────────────────────────────────┐
│ Feature       │ Commands              │ Use Case             │
├───────────────────────────────────────────────────────────────┤
│ Geospatial    │ GEOADD, GEODIST,      │ Nearby search,       │
│               │ GEOSEARCH, GEOPOS     │ location tracking    │
│ HyperLogLog   │ PFADD, PFCOUNT,       │ Unique visitors,     │
│               │ PFMERGE               │ distinct counts      │
│ RedisJSON     │ JSON.SET, JSON.GET,   │ Nested JSON,         │
│               │ JSON.NUMINCRBY,       │ partial updates      │
│               │ JSON.ARRAPPEND        │                      │
└───────────────────────────────────────────────────────────────┘
```
