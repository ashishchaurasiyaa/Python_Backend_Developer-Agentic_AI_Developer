"""
============================================================
NEGATIVE CACHING — Practical
============================================================
Implements:
1. Sentinel-based negative cache
2. Bloom filter integration
3. Cache creation invalidation
4. Stale-while-error fallback
5. Permission caching
6. External API failure caching
"""
from __future__ import annotations
import asyncio
import time
import hashlib
from dataclasses import dataclass


# ============================================================
# Fake dependencies
# ============================================================
class FakeDB:
    def __init__(self):
        self._users = {1: "Alice", 2: "Bob", 5: "Eve"}
        self.fetch_count = 0

    async def fetch(self, user_id):
        await asyncio.sleep(0.02)
        self.fetch_count += 1
        return self._users.get(user_id)

    async def create(self, user_id, name):
        self._users[user_id] = name


class FakeCache:
    def __init__(self):
        self._store: dict = {}
        self.gets = 0

    async def get(self, key):
        self.gets += 1
        entry = self._store.get(key)
        if not entry: return None
        value, expiry = entry
        if time.time() > expiry:
            del self._store[key]
            return None
        return value

    async def set(self, key, value, ttl=300):
        self._store[key] = (value, time.time() + ttl)

    async def delete(self, key):
        self._store.pop(key, None)

    async def exists(self, key):
        return await self.get(key) is not None


# ============================================================
# 1. SENTINEL-BASED NEGATIVE CACHE
# ============================================================
NOT_FOUND = "__NOT_FOUND__"


class NegativeAwareCache:
    """Wraps a cache to distinguish 'miss' vs 'cached not-found'."""

    def __init__(self, cache: FakeCache, positive_ttl=300, negative_ttl=30):
        self.cache = cache
        self.positive_ttl = positive_ttl
        self.negative_ttl = negative_ttl

    async def get(self, key) -> tuple[any, str]:
        """Returns (value, status). Status: 'hit' | 'negative_hit' | 'miss'."""
        cached = await self.cache.get(key)
        if cached is None:
            return None, "miss"
        if cached == NOT_FOUND:
            return None, "negative_hit"
        return cached, "hit"

    async def set_positive(self, key, value):
        await self.cache.set(key, value, ttl=self.positive_ttl)

    async def set_negative(self, key):
        await self.cache.set(key, NOT_FOUND, ttl=self.negative_ttl)

    async def invalidate(self, key):
        await self.cache.delete(key)


# ============================================================
# 2. WRAPPED ENDPOINT WITH NEGATIVE CACHING
# ============================================================
class UserService:
    def __init__(self, db: FakeDB):
        self.db = db
        self.cache = NegativeAwareCache(FakeCache())

    async def get_user(self, user_id: int):
        cache_key = f"user:{user_id}"
        value, status = await self.cache.get(cache_key)

        if status == "negative_hit":
            return None     # cached 404 — no DB call
        if status == "hit":
            return value

        # Real fetch
        user = await self.db.fetch(user_id)
        if user is None:
            await self.cache.set_negative(cache_key)
            return None
        await self.cache.set_positive(cache_key, user)
        return user

    async def create_user(self, user_id: int, name: str):
        await self.db.create(user_id, name)
        # CRITICAL: invalidate negative cache so new user is fetchable
        await self.cache.invalidate(f"user:{user_id}")


# ============================================================
# 3. BLOOM FILTER (simplified implementation)
# ============================================================
class BloomFilter:
    """Simple bloom filter — production use pybloom_live or redis bloom."""

    def __init__(self, size: int = 1_000_000, num_hashes: int = 5):
        self.size = size
        self.num_hashes = num_hashes
        self.bits = bytearray(size // 8 + 1)

    def _hashes(self, key: str):
        result = []
        for i in range(self.num_hashes):
            h = int(hashlib.md5(f"{key}-{i}".encode()).hexdigest(), 16)
            result.append(h % self.size)
        return result

    def add(self, key: str):
        for h in self._hashes(key):
            self.bits[h // 8] |= 1 << (h % 8)

    def __contains__(self, key: str) -> bool:
        return all(
            self.bits[h // 8] & (1 << (h % 8))
            for h in self._hashes(key)
        )


# ============================================================
# 4. BLOOM-PROTECTED ENDPOINT
# ============================================================
class BloomProtectedUserService:
    def __init__(self, db: FakeDB):
        self.db = db
        self.bloom = BloomFilter()
        self.cache = FakeCache()

    async def prime_bloom(self):
        """Load all valid user IDs into bloom filter at startup."""
        for user_id in self.db._users:
            self.bloom.add(str(user_id))

    async def get_user(self, user_id: int):
        # Fast bloom check — definitely not in set?
        if str(user_id) not in self.bloom:
            return None     # 100% confident → no DB call

        # Maybe in set — check cache + DB
        cached = await self.cache.get(f"user:{user_id}")
        if cached:
            return cached
        user = await self.db.fetch(user_id)
        if user:
            await self.cache.set(f"user:{user_id}", user, ttl=300)
        return user


# ============================================================
# 5. STALE-WHILE-ERROR PATTERN
# ============================================================
class ResilientCache:
    """Serve last-known-good value when source errors."""

    def __init__(self, cache: FakeCache):
        self.cache = cache

    async def get_with_fallback(self, key, fetch_fn):
        try:
            value = await fetch_fn(key)
            await self.cache.set(key, value, ttl=300)
            await self.cache.set(f"{key}:backup", value, ttl=86400)
            return value, "fresh"
        except Exception as e:
            backup = await self.cache.get(f"{key}:backup")
            if backup is not None:
                return backup, f"stale_due_to_error: {e}"
            raise


# ============================================================
# 6. EXTERNAL API FAILURE CACHING (cooldown)
# ============================================================
class CooldownCache:
    """Cache recent failures to prevent retry storms."""

    def __init__(self, cache: FakeCache, cooldown_seconds: int = 30):
        self.cache = cache
        self.cooldown = cooldown_seconds

    async def call_with_cooldown(self, url, fetch_fn):
        cooldown_key = f"failure:{url}"
        if await self.cache.exists(cooldown_key):
            raise RuntimeError(f"Recent failure on {url} — cooldown active")
        try:
            return await fetch_fn(url)
        except Exception as e:
            await self.cache.set(cooldown_key, "1", ttl=self.cooldown)
            raise


# ============================================================
# 7. PERMISSION CACHING
# ============================================================
class PermissionCache:
    """Cache positive and negative permission checks."""

    def __init__(self, cache: FakeCache):
        self.cache = cache

    async def is_allowed(self, user_id: int, resource: str, check_fn):
        key = f"perm:{user_id}:{resource}"
        cached = await self.cache.get(key)

        if cached == "ALLOWED":
            return True
        if cached == "DENIED":
            return False

        allowed = await check_fn(user_id, resource)
        await self.cache.set(
            key, "ALLOWED" if allowed else "DENIED",
            ttl=300 if allowed else 60,
        )
        return allowed

    async def revoke(self, user_id: int, resource: str = None):
        """Call when permissions change."""
        if resource:
            await self.cache.delete(f"perm:{user_id}:{resource}")
        else:
            # Production: scan + delete all perm:user_id:*
            pass


# ============================================================
# DEMOS
# ============================================================
async def demo_negative_cache():
    print("=" * 60)
    print("NEGATIVE CACHE — Prevents DB hammering on bot 404 attacks")
    print("=" * 60)
    db = FakeDB()
    svc = UserService(db)

    # Bot enumerates user IDs 999-1010 (mostly not found)
    print("\n  Bot requests user IDs 999-1010 (5 times each):")
    for _ in range(5):
        for user_id in range(999, 1011):
            await svc.get_user(user_id)
    print(f"  Total bot requests: {5 * 12} = 60")
    print(f"  DB calls: {db.fetch_count} (expected 12, not 60)")
    print(f"  ✅ Negative cache saved {60 - db.fetch_count} DB calls")


async def demo_creation_invalidation():
    print("\n" + "=" * 60)
    print("CREATION INVALIDATION")
    print("=" * 60)
    db = FakeDB()
    svc = UserService(db)

    # Lookup non-existent user
    user = await svc.get_user(100)
    print(f"  user 100: {user} (not found, cached negative)")

    # User created
    await svc.create_user(100, "Charlie")
    print(f"  Created user 100")

    # Should now be fetchable (negative cache invalidated)
    user = await svc.get_user(100)
    print(f"  user 100: {user} ✅ (creation invalidated negative cache)")


async def demo_bloom_filter():
    print("\n" + "=" * 60)
    print("BLOOM FILTER PROTECTION")
    print("=" * 60)
    db = FakeDB()
    svc = BloomProtectedUserService(db)
    await svc.prime_bloom()

    # Try 1000 random IDs — most don't exist
    db.fetch_count = 0
    for user_id in range(1, 1001):
        await svc.get_user(user_id)
    print(f"  1000 random ID lookups (only 3 valid):")
    print(f"  DB calls: {db.fetch_count} (close to 3, not 1000)")
    print(f"  ✅ Bloom filter blocked ~99.7% of invalid lookups before cache/DB")


async def demo_stale_while_error():
    print("\n" + "=" * 60)
    print("STALE-WHILE-ERROR")
    print("=" * 60)
    rc = ResilientCache(FakeCache())

    async def db_call(key):
        return f"fresh_{key}"

    # First call OK
    val, status = await rc.get_with_fallback("config", db_call)
    print(f"  First call: {val} ({status})")

    async def db_call_fails(key):
        raise ConnectionError("DB down!")

    # Second call — DB fails, returns stale
    val, status = await rc.get_with_fallback("config", db_call_fails)
    print(f"  Second call (DB down): {val} ({status})")
    print(f"  ✅ Last-known-good served instead of 500 error")


async def demo_cooldown():
    print("\n" + "=" * 60)
    print("EXTERNAL API COOLDOWN")
    print("=" * 60)
    cc = CooldownCache(FakeCache(), cooldown_seconds=2)
    call_count = 0

    async def flaky_api(url):
        nonlocal call_count
        call_count += 1
        raise ConnectionError("API timeout")

    # First call fails — cools down
    try: await cc.call_with_cooldown("https://api.example.com", flaky_api)
    except: print(f"  Call 1: failed (recorded cooldown)")

    # Next 5 calls — short-circuited
    for i in range(5):
        try: await cc.call_with_cooldown("https://api.example.com", flaky_api)
        except RuntimeError as e: print(f"  Call {i+2}: cooldown active → {e}")

    print(f"  Total API calls during cooldown: {call_count} (only 1, not 6)")


async def demo_permission_cache():
    print("\n" + "=" * 60)
    print("PERMISSION CACHING")
    print("=" * 60)
    pc = PermissionCache(FakeCache())
    check_count = 0

    async def check_perm(uid, resource):
        nonlocal check_count
        check_count += 1
        return uid % 2 == 0   # even users allowed

    # Check 100 times
    for _ in range(100):
        await pc.is_allowed(42, "doc-1", check_perm)
        await pc.is_allowed(43, "doc-1", check_perm)

    print(f"  200 permission checks, real lookups: {check_count}")
    print(f"  ✅ Cached after first check per (user, resource)")

    # Revoke
    await pc.revoke(42, "doc-1")
    check_count = 0
    await pc.is_allowed(42, "doc-1", check_perm)
    print(f"  After revoke: 1 real lookup (cache invalidated)")


# ============================================================
# MAIN
# ============================================================
if __name__ == "__main__":
    async def main():
        await demo_negative_cache()
        await demo_creation_invalidation()
        await demo_bloom_filter()
        await demo_stale_while_error()
        await demo_cooldown()
        await demo_permission_cache()

        print("\n" + "=" * 60)
        print("KEY TAKEAWAYS")
        print("=" * 60)
        print("""
1. Cache the 404 — prevents bot attacks hammering DB
2. Sentinel value differentiates miss from cached-miss
3. Negative TTL < positive TTL (typically 30s-5min)
4. ALWAYS invalidate negative cache on create
5. Bloom filter for huge key spaces (probabilistic, no false negatives)
6. Stale-while-error: serve last-known-good on failure
7. Cooldown caching prevents retry storms on external APIs
8. Permission caching with short TTL + revocation hooks
9. Never cache transient errors (500/timeout) as 404
""")

    asyncio.run(main())
