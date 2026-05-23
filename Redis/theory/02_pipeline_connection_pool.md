# Redis — Pipeline, Connection Pool & Session Store
**Intermediate Level | What, Why, How**

---

## Quick Concepts
- **Pipeline** = Multiple commands ek saath bhejo — N round trips → 1 round trip
- **Connection Pool** = Pre-created connections reuse karo — connection overhead khatam
- **Session Store** = User login sessions Redis mein store karo
- **Atomic Pipeline** = Pipeline + MULTI/EXEC — sab commands ek transaction
- **max_connections** = Pool size — production mein carefully set karo

---

## Interview Questions & Answers

---

### Q1: Pipeline kya hai? Kyu use karo?

**Answer:**
```
Without Pipeline:
  Client → SET key1 val1 → Server → OK    (round trip 1)
  Client → SET key2 val2 → Server → OK    (round trip 2)
  Client → SET key3 val3 → Server → OK    (round trip 3)
  Total: 3 * (network latency) = ~3ms (local) or ~300ms (remote)

With Pipeline:
  Client → [SET key1, SET key2, SET key3] → Server → [OK, OK, OK]
  Total: 1 * (network latency) = ~1ms (local) or ~100ms (remote)
  3x faster! ✅

Use cases:
  - Bulk data insert (1000 records ek saath)
  - Multiple keys ek saath update
  - Startup mein cache warm karna
  - Analytics counters batch increment
```

```python
import redis
import time

r = redis.Redis(host='localhost', port=6379, decode_responses=True)

# ─── Without Pipeline — Slow ───
start = time.time()
for i in range(1000):
    r.set(f"key:{i}", f"value:{i}")
print(f"Without pipeline: {time.time() - start:.3f}s")

# ─── With Pipeline — Fast ───
start = time.time()
pipe = r.pipeline()

for i in range(1000):
    pipe.set(f"key:{i}", f"value:{i}")

results = pipe.execute()   # ek baar mein sab bhejo
print(f"With pipeline: {time.time() - start:.3f}s")
# ~10x faster on remote connections

# ─── Pipeline with Mixed Commands ───
pipe = r.pipeline()
pipe.set("user:1:name", "Alice")
pipe.set("user:1:email", "alice@test.com")
pipe.incr("counter:users")
pipe.expire("user:1:name", 3600)
pipe.hset("user:1:profile", mapping={"age": "25", "city": "Mumbai"})
results = pipe.execute()
# returns: [True, True, 1, True, 1]
print(f"Pipeline results: {results}")

# ─── Pipeline with GET operations ───
pipe = r.pipeline()
pipe.get("user:1:name")
pipe.get("user:1:email")
pipe.hgetall("user:1:profile")
name, email, profile = pipe.execute()
print(f"Name: {name}, Email: {email}, Profile: {profile}")
```

---

### Q2: Async Pipeline kaise use karo?

**Answer:**
```python
import asyncio
import redis.asyncio as aioredis

async def pipeline_demo():
    r = await aioredis.from_url("redis://localhost:6379", decode_responses=True)

    # ─── Async Pipeline ───
    async with r.pipeline(transaction=False) as pipe:
        for i in range(1000):
            pipe.set(f"async:key:{i}", f"value:{i}", ex=3600)
        results = await pipe.execute()
    print(f"Inserted {len(results)} keys")

    # ─── Atomic Pipeline (transaction=True = MULTI/EXEC) ───
    async with r.pipeline(transaction=True) as pipe:
        pipe.incr("order:count")
        pipe.lpush("recent:orders", "order:123")
        pipe.ltrim("recent:orders", 0, 99)   # keep last 100
        results = await pipe.execute()
    print(f"Atomic pipeline results: {results}")

    # ─── Pipeline for bulk read ───
    async with r.pipeline(transaction=False) as pipe:
        keys = [f"async:key:{i}" for i in range(0, 10)]
        for key in keys:
            pipe.get(key)
        values = await pipe.execute()
    print(f"Bulk read: {dict(zip(keys, values))}")

    await r.aclose()

asyncio.run(pipeline_demo())
```

---

### Q3: Connection Pool kya hai? FastAPI mein kaise setup karo?

**Answer:**
```
Without Pool:
  Request 1 → new TCP connection → query → close connection
  Request 2 → new TCP connection → query → close connection
  1000 requests → 1000 connections → expensive ❌

With Pool:
  App start → 10 connections create (pool)
  Request 1 → pool se connection lo → query → wapas pool mein
  Request 2 → pool se connection lo → query → wapas pool mein
  1000 requests → max 10 connections → efficient ✅
```

```python
import redis
import redis.asyncio as aioredis
from fastapi import FastAPI, Depends, Request
from contextlib import asynccontextmanager
from typing import AsyncGenerator

# ─── SYNC Connection Pool ───
sync_pool = redis.ConnectionPool(
    host='localhost',
    port=6379,
    db=0,
    password=None,
    max_connections=20,        # maximum pool size
    decode_responses=True,
    socket_timeout=5,          # 5 sec read timeout
    socket_connect_timeout=2,  # 2 sec connect timeout
    retry_on_timeout=True,
    health_check_interval=30   # 30 sec health check
)
sync_redis = redis.Redis(connection_pool=sync_pool)


# ─── ASYNC Connection Pool (FastAPI ke liye) ───
async_pool = aioredis.ConnectionPool(
    host='localhost',
    port=6379,
    db=0,
    max_connections=50,        # production mein 50-100
    decode_responses=True,
)


# ─── FastAPI + Redis — Correct Pattern ───
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup — pool create karo
    app.state.redis = aioredis.Redis(connection_pool=async_pool)
    print("Redis pool created!")
    yield
    # Shutdown — pool close karo
    await app.state.redis.aclose()
    await async_pool.aclose()
    print("Redis pool closed!")

app = FastAPI(lifespan=lifespan)


# ─── Dependency — request mein Redis inject karo ───
async def get_redis(request: Request) -> aioredis.Redis:
    return request.app.state.redis


# ─── Use in endpoints ───
from pydantic import BaseModel

class UserProfile(BaseModel):
    name: str
    email: str
    age: int

@app.get("/users/{user_id}")
async def get_user(user_id: int, redis: aioredis.Redis = Depends(get_redis)):
    # Cache check
    cached = await redis.get(f"user:{user_id}:profile")
    if cached:
        import json
        return {"source": "cache", "data": json.loads(cached)}

    # DB se fetch karo (simulate)
    user = {"id": user_id, "name": "Alice", "email": "alice@test.com"}

    # Cache store karo
    import json
    await redis.setex(f"user:{user_id}:profile", 3600, json.dumps(user))
    return {"source": "db", "data": user}

@app.post("/users/{user_id}/view")
async def track_view(user_id: int, redis: aioredis.Redis = Depends(get_redis)):
    count = await redis.incr(f"views:user:{user_id}")
    return {"user_id": user_id, "total_views": count}
```

---

### Q4: Redis as Session Store — FastAPI mein kaise implement karo?

**Answer:**
```python
import asyncio
import json
import uuid
from datetime import datetime
from fastapi import FastAPI, HTTPException, Cookie, Response, Depends
import redis.asyncio as aioredis
from pydantic import BaseModel

# Session Manager
class RedisSessionManager:
    def __init__(self, redis_client: aioredis.Redis):
        self.redis = redis_client
        self.session_ttl = 86400   # 24 hours

    async def create_session(self, user_data: dict) -> str:
        """Login ke baad session create karo"""
        session_id = str(uuid.uuid4())
        session_data = {
            **user_data,
            "created_at": datetime.now().isoformat(),
            "last_active": datetime.now().isoformat()
        }
        await self.redis.setex(
            f"session:{session_id}",
            self.session_ttl,
            json.dumps(session_data)
        )
        return session_id

    async def get_session(self, session_id: str) -> dict | None:
        """Session validate karo + data fetch karo"""
        data = await self.redis.get(f"session:{session_id}")
        if not data:
            return None

        session = json.loads(data)
        # Last active update karo + TTL refresh
        session["last_active"] = datetime.now().isoformat()
        await self.redis.setex(
            f"session:{session_id}",
            self.session_ttl,
            json.dumps(session)
        )
        return session

    async def delete_session(self, session_id: str):
        """Logout — session delete karo"""
        await self.redis.delete(f"session:{session_id}")

    async def delete_all_user_sessions(self, user_id: int):
        """User ke sabhi sessions delete karo (password change etc.)"""
        async for key in self.redis.scan_iter(f"session:*"):
            data = await self.redis.get(key)
            if data:
                session = json.loads(data)
                if session.get("user_id") == user_id:
                    await self.redis.delete(key)


# FastAPI endpoints
class LoginRequest(BaseModel):
    username: str
    password: str

@app.post("/auth/login")
async def login(
    request: LoginRequest,
    response: Response,
    redis: aioredis.Redis = Depends(get_redis)
):
    # Password verify karo (simulate)
    if request.username != "alice" or request.password != "secret":
        raise HTTPException(status_code=401, detail="Invalid credentials")

    user_data = {"user_id": 1, "username": "alice", "role": "admin"}

    session_manager = RedisSessionManager(redis)
    session_id = await session_manager.create_session(user_data)

    # Cookie mein set karo
    response.set_cookie(
        key="session_id",
        value=session_id,
        httponly=True,    # JS access nahi
        secure=True,      # HTTPS only
        samesite="lax",
        max_age=86400
    )
    return {"message": "Login successful", "user": user_data}


@app.get("/auth/me")
async def get_me(
    session_id: str = Cookie(None),
    redis: aioredis.Redis = Depends(get_redis)
):
    if not session_id:
        raise HTTPException(status_code=401, detail="No session")

    session_manager = RedisSessionManager(redis)
    session = await session_manager.get_session(session_id)

    if not session:
        raise HTTPException(status_code=401, detail="Session expired or invalid")

    return {"user": session}


@app.post("/auth/logout")
async def logout(
    response: Response,
    session_id: str = Cookie(None),
    redis: aioredis.Redis = Depends(get_redis)
):
    if session_id:
        session_manager = RedisSessionManager(redis)
        await session_manager.delete_session(session_id)

    response.delete_cookie("session_id")
    return {"message": "Logged out"}
```

---

### Q5: Pipeline vs Transaction (MULTI/EXEC) — kya fark hai?

**Answer:**
```python
import redis
r = redis.Redis(decode_responses=True)

# Pipeline (transaction=False) — batch bhejo, no atomicity
pipe = r.pipeline(transaction=False)
pipe.set("a", 1)
pipe.set("b", 2)
# Agar beech mein koi fail kare → baaki execute honge
# Order guaranteed, atomicity nahi
results = pipe.execute()

# Pipeline (transaction=True) = MULTI/EXEC — atomic
pipe = r.pipeline(transaction=True)
pipe.incr("balance:user:1")
pipe.decr("balance:user:2")
# Ya dono execute honge ya koi nahi
# MULTI...EXEC wrap hota hai internally
results = pipe.execute()

# Kab kaunsa?
# transaction=False → speed chahiye, atomicity nahi (bulk insert)
# transaction=True  → atomicity chahiye (transfers, counters)
```

---

## Summary Table

```
┌──────────────────────────────────────────────────────────────┐
│ Feature          │ Without           │ With                  │
├──────────────────────────────────────────────────────────────┤
│ Pipeline         │ N round trips     │ 1 round trip          │
│ Connection Pool  │ New conn each req │ Reuse connections     │
│ Session Store    │ DB/file sessions  │ In-memory, fast       │
├──────────────────────────────────────────────────────────────┤
│ Pipeline use:    │ Bulk insert/read, startup cache warm       │
│ Pool use:        │ Every production FastAPI app               │
│ Session use:     │ Login, auth, user state                    │
└──────────────────────────────────────────────────────────────┘
```
