# Singleton Pattern
> **Category:** Creational | **Difficulty:** Easy | **Interview Frequency:** ★★★★★

---

## Quick Reference Card
```
Kya karta hai : Ek class ka sirf EK hi instance banta hai — dobara banane ki koshish karo toh wahi purana milta hai
Kab use karo  : DB connection, Redis client, Logger, Config manager, SAP token cache
Key mechanism : __new__ override ya metaclass — instance already hai toh wahi return karo
Real project  : Niroskos → Redis connection | Youngman → PostgreSQL DB connection
Pattern type  : Creational
```

---

## PART 1: HINGLISH — Samjhne ke liye

### 1.1 Kya hai?

Singleton ek aisa pattern hai jisme **poori application mein sirf ek hi object banta hai** ek particular class ka.

Socho agar tum baar baar `DatabaseConnection()` call karo — har baar naya connection bane toh:
- 100 users → 100 DB connections → server crash!
- Bahut resources waste honge

Singleton ensure karta hai ki **pehli baar bana, baaki baar wahi milta hai**.

**Simple analogy:**
```
Desh mein ek hi President hota hai.
Agar koi president banana chahta hai → already wala mil jaata hai.
Naya nahi banta.
```

---

### 1.2 Kab use karo?

```
✅ Database connection     → Ek connection pool — baar baar open/close nahi
✅ Redis / Cache client    → Ek hi client instance puri app mein
✅ Logger                  → Ek logger sab jagah — settings ek jagah
✅ Config Manager          → App settings ek jagah load — bar bar file read nahi
✅ SAP Token Cache         → Token ek baar fetch karo, 5 min tak same use karo
✅ Thread Pool             → Workers ek baar banao — reuse karo
```

---

### 1.3 Kab mat use karo?

```
❌ Jab multiple instances chahiye ho (alag alag users ke liye alag state)
❌ Unit testing mein dikkat aati hai — state shared hoti hai tests ke beech
❌ Jab object ka lifetime manage karna ho alag alag jagah
```

---

### 1.4 Code — Hinglish Comments ke saath

```python
import threading

# ─── Basic Singleton ───
class Singleton:
    _instance = None  # Class variable — sirf ek hi instance store hoga

    def __new__(cls):
        # __new__ constructor se pehle call hota hai
        # Check karo — kya pehle se bana hai?
        if cls._instance is None:
            print("Pehli baar ban raha hai...")
            cls._instance = super().__new__(cls)  # Tabhi banao
        return cls._instance  # Wahi purana return karo

a = Singleton()
b = Singleton()
print(a is b)  # True — dono same object hain!


# ─── Thread-Safe Singleton ───
# Problem: 2 threads simultaneously check karein → dono "None" dekhein → dono banayein
# Solution: Lock lagao — ek baar mein ek hi thread andar jaaye

class ThreadSafeSingleton:
    _instance = None
    _lock = threading.Lock()  # Darwaaza — ek hi thread andar

    def __new__(cls):
        with cls._lock:  # Lock liya — doosra thread wait karega
            if cls._instance is None:
                cls._instance = super().__new__(cls)
        return cls._instance


# ─── Real Project Example — Redis Connection (Niroskos) ───
import redis

class RedisClient:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                print("Redis connection ban raha hai — sirf ek baar")
                cls._instance = super().__new__(cls)
                # Actual Redis connect karo
                cls._instance._client = redis.Redis(
                    host='localhost',
                    port=6379,
                    db=0,
                    decode_responses=True
                )
        return cls._instance

    def get(self, key: str):
        return self._client.get(key)

    def set(self, key: str, value: str, ttl: int = None):
        if ttl:
            self._client.setex(key, ttl, value)
        else:
            self._client.set(key, value)

    def set_nx(self, key: str, value: str, ttl: int) -> bool:
        # NX = set only if Not eXists — distributed lock ke liye
        return self._client.set(key, value, nx=True, ex=ttl)


# Usage — koi bhi jagah se call karo, same connection milega
r1 = RedisClient()
r2 = RedisClient()
print(r1 is r2)  # True ✅

r1.set("booking:123", "CONFIRMED", ttl=300)
print(r2.get("booking:123"))  # "CONFIRMED" — same instance hai


# ─── Real Project Example — SAP HANA Token Cache (Youngman) ───
from datetime import datetime, timedelta

class SAPTokenCache:
    """
    SAP HANA token 5 minute valid hota hai.
    Baar baar fetch karna = extra API calls = slow + rate limit risk.
    Singleton mein cache karo — ek baar fetch, 5 min reuse.
    """
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._token = None
                cls._instance._expires_at = None
        return cls._instance

    def get_token(self) -> str:
        # Token valid hai toh wahi do — naya mat bano
        if self._token and datetime.now() < self._expires_at:
            return self._token

        # Token expire ho gaya — naya fetch karo
        self._token = self._fetch_from_sap()
        self._expires_at = datetime.now() + timedelta(minutes=5)
        return self._token

    def _fetch_from_sap(self) -> str:
        print("SAP se naya token fetch ho raha hai...")
        # SAP HANA auth API call
        return "sap_token_xyz_" + str(datetime.now().timestamp())


# Ek baar token liya — 5 min baad hi dobara API call
cache = SAPTokenCache()
token1 = cache.get_token()  # "SAP se naya token..."
token2 = cache.get_token()  # Same token — no API call
print(token1 == token2)     # True ✅
```

---

### 1.5 Tumhara Real Project Mein Kahan Use Hua

```
Project 1 — Niroskos Safari Platform:
  → Redis distributed lock: client.set(key, 1, nx=True, ex=60)
    Ek hi Redis client puri app mein use hota tha
    Booking attraction sync mein concurrent requests rokne ke liye

Project 2 — Youngman ERP:
  → SAP HANA token: 5-min TTL cache
    4858+ line connector mein token ek baar fetch,
    5 minute baad automatically refresh

Project 3 — Youngman Django (tumhara existing code):
  → psycopg2 PostgreSQL connection Singleton
    DataBaseConnection class — ek hi connection object
    Multiple queries same connection se
```

---

## PART 2: ENGLISH — Interviewer ko bolne ke liye

### 2.1 Definition

> **Singleton is a creational design pattern that ensures a class has only one instance throughout the application's lifetime, while providing a global access point to that instance.**

---

### 2.2 Problem It Solves

```
Without Singleton:
  Every call to DatabaseConnection() → new TCP connection
  100 requests → 100 connections → DB server overwhelmed

With Singleton:
  First call → creates connection
  All subsequent calls → return the SAME connection
  Resource efficient, consistent state
```

---

### 2.3 Key Components

| Component | Role | Example |
|-----------|------|---------|
| `_instance` | Stores the single instance | Class variable |
| `__new__` / metaclass | Controls instantiation | Override to check existing instance |
| `_lock` | Thread safety | `threading.Lock()` |
| Public accessor | Global access point | `RedisClient()` or `getInstance()` |

---

### 2.4 Clean Code Example

```python
import threading

class SingletonMeta(type):
    _instances = {}
    _lock: threading.Lock = threading.Lock()

    def __call__(cls, *args, **kwargs):
        with cls._lock:
            if cls not in cls._instances:
                instance = super().__call__(*args, **kwargs)
                cls._instances[cls] = instance
        return cls._instances[cls]


class RedisClient(metaclass=SingletonMeta):
    def __init__(self):
        import redis
        self._client = redis.Redis(host='localhost', port=6379, db=0)

    def get(self, key: str):
        return self._client.get(key)

    def set(self, key: str, value: str, ttl: int = None):
        if ttl:
            self._client.setex(key, ttl, value)
        else:
            self._client.set(key, value)

    def acquire_lock(self, key: str, ttl: int = 60) -> bool:
        """Distributed lock — SET NX pattern"""
        return bool(self._client.set(key, 1, nx=True, ex=ttl))


# Verify singleton behavior
client1 = RedisClient()
client2 = RedisClient()
assert client1 is client2  # Same instance ✅
```

---

### 2.5 Real Project Answer

**"Tell me about Singleton pattern usage in your projects"**

> "I used Singleton in two places in production:
>
> **First**, in Niroskos, I used a Redis Singleton client to implement distributed locking. When multiple Celery workers tried to sync the same package's attraction data simultaneously, I used `client.set(lock_key, 1, nx=True, ex=60)` — the SET NX pattern. This prevented duplicate sync operations. The Redis client itself was a Singleton — same connection reused across all workers.
>
> **Second**, in the Youngman ERP SAP HANA connector — 4858 lines of integration code. The SAP auth token was valid for 5 minutes. Instead of calling the auth API on every request, I cached the token in a Singleton with a 5-minute TTL. The `get_token()` method checked expiry first — if valid, returned cached token; if expired, fetched a new one. This reduced SAP API calls by ~95% and improved response time significantly."

---

### 2.6 Follow-up Q&A

**Q: "How do you handle Singleton in multithreaded environment?"**
> "Using `threading.Lock()`. The double-checked locking pattern — first check without lock (fast path), then check again inside lock (safe path). In Python, using metaclass with `with cls._lock` is the cleanest approach."

**Q: "How can Singleton be broken?"**
> "Four ways: (1) `copy.deepcopy()` creates new object, (2) `pickle.loads(pickle.dumps(obj))` deserializes new instance, (3) Direct `__new__` call bypasses control logic, (4) Race condition in multithreading without locks. Fix: implement `__deepcopy__`, `__reduce__` methods to return the same instance."

**Q: "Singleton vs Global Variable — difference?"**
> "Global variable is just a variable — no control over instantiation, no lazy initialization, no thread safety. Singleton is a controlled class — instantiation is managed, lazy (created only when needed), thread-safe, and can have methods and state."

**Q: "Is Django's ORM connection a Singleton?"**
> "Yes, essentially. Django maintains a connection registry per thread using `django.db.connections`. Each thread gets its own connection object but it's reused within that thread — similar to thread-local Singleton."

---

## Ways to Break Singleton (Bonus — Impresses Interviewers)

```python
import copy, pickle

s1 = Singleton()

# Break 1: deepcopy
s2 = copy.deepcopy(s1)      # New instance!

# Break 2: pickle
s3 = pickle.loads(pickle.dumps(s1))  # New instance!

# Fix: Override these methods
class Singleton:
    def __deepcopy__(self, memo):
        return self  # Return same instance

    def __reduce__(self):
        return (self.__class__, ())  # Return same class call
```

---

*Last Updated: April 2026 | SDE-2 Interview Prep*
