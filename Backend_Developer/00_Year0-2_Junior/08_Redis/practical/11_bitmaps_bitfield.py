"""
Redis Practical 11 — Bitmaps & BITFIELD (Memory-Efficient Tracking)
Run: python 11_bitmaps_bitfield.py [dau|retention|streak|bitfield|memory|all]

Prerequisites:
  pip install redis[hiredis]
  docker run -d --name redis -p 6379:6379 redis:7-alpine
"""

import sys
import datetime
import redis

r = redis.Redis(host='localhost', port=6379, decode_responses=True)


# ════════════════════════════════════════════
# SECTION 1: DAU TRACKING — SETBIT / BITCOUNT
# ════════════════════════════════════════════
def demo_dau():
    print("\n" + "=" * 50)
    print("  SECTION 1: DAU TRACKING")
    print("=" * 50)

    today = "2026-08-03"
    key = f"dau:{today}"
    r.delete(key)

    # ─── Users active hote hi bit set karo — O(1) ───
    active_users = [3, 17, 42, 99, 1024, 50000, 123456]
    for uid in active_users:
        r.setbit(key, uid, 1)

    print(f"✅ Marked {len(active_users)} users active")
    print(f"📊 DAU (BITCOUNT): {r.bitcount(key)}")

    # ─── Membership check — kya user X active tha? ───
    print(f"   User 42 active?     {bool(r.getbit(key, 42))}")
    print(f"   User 43 active?     {bool(r.getbit(key, 43))}")

    # ─── First active user ───
    print(f"   First active (BITPOS): user {r.bitpos(key, 1)}")

    # Note: key ka size = highest_offset / 8 bytes
    print(f"   Key memory: {r.memory_usage(key)} bytes (highest uid=123456 → ~15KB)")


# ════════════════════════════════════════════
# SECTION 2: RETENTION — BITOP AND/OR/XOR
# ════════════════════════════════════════════
def demo_retention():
    print("\n" + "=" * 50)
    print("  SECTION 2: RETENTION / COHORTS")
    print("=" * 50)

    # ─── 3 din ka activity simulate karo ───
    days = {
        "dau:mon": [1, 2, 3, 4, 5],
        "dau:tue": [2, 3, 4, 7],
        "dau:wed": [3, 4, 8, 9],
    }
    for key, users in days.items():
        r.delete(key)
        for uid in users:
            r.setbit(key, uid, 1)

    # ─── AND = teeno din active (retained) ───
    r.bitop("AND", "cohort:retained_3d", *days.keys())
    retained = r.bitcount("cohort:retained_3d")
    print(f"📊 3-day retained users (AND): {retained}")          # users 3, 4

    # ─── OR = kisi bhi din active (weekly-active style) ───
    r.bitop("OR", "cohort:any_active", *days.keys())
    print(f"📊 Active any day (OR):        {r.bitcount('cohort:any_active')}")

    # ─── Mon active par Tue nahi = potential churn ───
    # (mon AND NOT tue) — NOT direct combine nahi hota, XOR+AND se nikalo
    r.bitop("XOR", "tmp:mon_xor_tue", "dau:mon", "dau:tue")
    r.bitop("AND", "cohort:churned", "tmp:mon_xor_tue", "dau:mon")
    print(f"📊 Mon-active, Tue-absent:     {r.bitcount('cohort:churned')}")  # 1, 5

    for k in ["cohort:retained_3d", "cohort:any_active", "tmp:mon_xor_tue", "cohort:churned"]:
        r.delete(k)


# ════════════════════════════════════════════
# SECTION 3: LOGIN STREAK (Duolingo-style)
# ════════════════════════════════════════════
def demo_streak():
    print("\n" + "=" * 50)
    print("  SECTION 3: LOGIN STREAK")
    print("=" * 50)

    # Per-user bitmap: bit index = days since signup
    key = "streak:user:777"
    r.delete(key)

    # ─── User ne day 0-4 login kiya, day 5 miss, day 6-9 login ───
    for day in [0, 1, 2, 3, 4, 6, 7, 8, 9]:
        r.setbit(key, day, 1)

    # ─── Current streak nikalo (aaj = day 9, peeche jao jab tak 1 hai) ───
    today_index = 9
    streak = 0
    for day in range(today_index, -1, -1):
        if r.getbit(key, day):
            streak += 1
        else:
            break
    print(f"🔥 Current streak: {streak} days (day 5 miss ne pehla streak toda)")
    print(f"📊 Total active days: {r.bitcount(key)} / 10")
    print(f"   365 days of streak data = sirf {365 // 8 + 1} bytes per user")


# ════════════════════════════════════════════
# SECTION 4: BITFIELD — PACKED COUNTERS
# ════════════════════════════════════════════
def demo_bitfield():
    print("\n" + "=" * 50)
    print("  SECTION 4: BITFIELD PACKED COUNTERS")
    print("=" * 50)

    # 1000 products ke u16 view-counters EK key me (2KB total)
    # vs 1000 alag INCR keys (~90KB overhead)
    key = "product:views"
    r.delete(key)

    # ─── SET / INCRBY on slots (#N = Nth u16 slot) ───
    r.bitfield(key).set("u16", "#0", 100).execute()
    r.bitfield(key).incrby("u16", "#0", 5).execute()
    r.bitfield(key).incrby("u16", "#7", 42).execute()

    # ─── Multiple GETs ek hi round-trip me ───
    values = r.bitfield(key).get("u16", "#0").get("u16", "#7").get("u16", "#3").execute()
    print(f"📊 Product 0 views: {values[0]}")    # 105
    print(f"   Product 7 views: {values[1]}")    # 42
    print(f"   Product 3 views: {values[2]}")    # 0 (untouched slot)

    # ─── OVERFLOW behaviour: SAT = saturate (u8 max 255 pe ruk jao) ───
    r.bitfield(key).set("u8", "#100", 250).execute()
    result = (r.bitfield(key, default_overflow="SAT")
                .incrby("u8", "#100", 100).execute())
    print(f"   u8 SAT overflow: 250 + 100 = {result[0]} (255 pe saturate, wrap nahi)")

    print(f"   Total key size: {r.memory_usage(key)} bytes for all counters")


# ════════════════════════════════════════════
# SECTION 5: MEMORY COMPARISON — bitmap vs set
# ════════════════════════════════════════════
def demo_memory():
    print("\n" + "=" * 50)
    print("  SECTION 5: MEMORY — BITMAP vs SET (100K users)")
    print("=" * 50)

    n = 100_000
    r.delete("m:bitmap", "m:set")

    # ─── Bitmap: 1 bit per user ───
    pipe = r.pipeline()
    for uid in range(0, n, 7):          # har 7th user active
        pipe.setbit("m:bitmap", uid, 1)
    pipe.execute()

    # ─── Set: full member storage ───
    pipe = r.pipeline()
    for uid in range(0, n, 7):
        pipe.sadd("m:set", uid)
    pipe.execute()

    bm, st = r.memory_usage("m:bitmap"), r.memory_usage("m:set")
    print(f"📊 Bitmap: {bm:>10,} bytes")
    print(f"   Set:    {st:>10,} bytes")
    print(f"   Bitmap is {st / bm:.0f}x smaller — same membership data")
    print("   (100M users pe: ~12.5 MB vs multiple GB)")

    r.delete("m:bitmap", "m:set")


if __name__ == "__main__":
    sections = {
        "dau": demo_dau,
        "retention": demo_retention,
        "streak": demo_streak,
        "bitfield": demo_bitfield,
        "memory": demo_memory,
    }
    choice = sys.argv[1] if len(sys.argv) > 1 else "all"
    if choice == "all":
        for fn in sections.values():
            fn()
    elif choice in sections:
        sections[choice]()
    else:
        print(f"Usage: python 11_bitmaps_bitfield.py [{'|'.join(sections)}|all]")
