# Redis — Bitmaps & BITFIELD (Memory-Efficient Tracking)

## Quick Concepts

- **Bitmap** = ek string jise bit-array ki tarah treat karte ho — har bit ek user/item ka boolean state
- **SETBIT/GETBIT** = ek bit set/read karo at offset — O(1)
- **BITCOUNT** = kitne bits 1 hain — "kitne users active the?"
- **BITOP** = do bitmaps ka AND/OR/XOR — "Monday AUR Tuesday dono din active kaun?"
- **BITFIELD** = ek hi key me packed chhote integers (u8/i16 etc.) — counters ka array
- **Memory math** = 1 bit per user → **100M users = ~12.5 MB**. Set me yehi data ~4-5 GB hota.

## Why It Matters (Interview Classic)

> **Q: "Track daily active users for 100M users, minimal memory. Design it."**
> Expected answer: bitmap per day. `SETBIT dau:2026-08-03 <user_id> 1` on activity.
> DAU = `BITCOUNT dau:2026-08-03`. Weekly retention = `BITOP AND` across 7 daily keys.
> Memory: 100M bits ≈ 12.5 MB/day. Sorted set ya table yahan 300x+ zyada leta.

Bitmap tab kaam karta hai jab **ID dense integer ho** (auto-increment user_id). UUID users ke liye pehle int mapping chahiye, warna offset explode karega — yeh caveat bolna hi senior answer hai.

---

## Commands

```bash
# ─── Basic bits ───
SETBIT dau:2026-08-03 12345 1     # user 12345 aaj active — O(1)
GETBIT dau:2026-08-03 12345        # 1
BITCOUNT dau:2026-08-03            # total active users today
BITCOUNT dau:2026-08-03 0 99 BYTE  # sirf pehle 100 bytes (users 0-799) me count
BITPOS dau:2026-08-03 1            # pehla active user (first set bit)

# ─── Combine days — retention/cohorts ───
BITOP AND weekly:active dau:mon dau:tue dau:wed    # sabhi 3 din active
BITOP OR  weekly:any    dau:mon dau:tue dau:wed    # kisi bhi din active
BITOP XOR churn:diff    dau:mon dau:tue            # sirf ek din active
BITCOUNT weekly:active                              # retention number

# ─── BITFIELD — packed integer array ───
# Ek key me 1000 products ke u16 counters (2 bytes each = 2KB total)
BITFIELD product:views SET u16 #0 100      # product 0 ka counter = 100 (#N = Nth slot)
BITFIELD product:views INCRBY u16 #0 1     # product 0 ka view +1
BITFIELD product:views GET u16 #0 GET u16 #1   # multiple reads ek call me
BITFIELD product:views OVERFLOW SAT INCRBY u8 #5 200   # saturate at max, wrap nahi
```

```python
# pip install redis[hiredis]
import redis
r = redis.Redis(decode_responses=True)

def mark_active(user_id: int, day: str):
    r.setbit(f"dau:{day}", user_id, 1)

def dau(day: str) -> int:
    return r.bitcount(f"dau:{day}")

def retained_7d(days: list[str]) -> int:
    """Saaton din active users — classic retention metric."""
    r.bitop("AND", "tmp:retained", *[f"dau:{d}" for d in days])
    count = r.bitcount("tmp:retained")
    r.delete("tmp:retained")
    return count
```

## Real Use Cases

| Use case | Pattern |
|---|---|
| DAU/MAU tracking | bitmap per day, `BITOP OR` for MAU |
| N-day retention / streaks | `BITOP AND` across daily bitmaps; streak = user ke apne bitmap me consecutive bits |
| Feature rollout cohort | `SETBIT feature:dark_mode <user_id> 1`, check with GETBIT — 10M users ka flag = 1.25 MB |
| A/B test membership | ek bitmap per variant, XOR se overlap check |
| Online status (dense IDs) | bitmap + BITCOUNT for "online now" count |
| Packed counters (BITFIELD) | rate-limit buckets, per-product small counters, game inventory slots |

## Gotchas

```
1. Sparse high offset = full allocation: SETBIT key 4000000000 1
   turant ~500MB allocate karega (string offset tak grow hoti hai).
   Dense/small IDs ke liye hi bitmap sahi hai.
2. BITCOUNT on huge bitmap is O(n) — hot path pe range (BYTE/BIT) do
   ya counter alag INCR me maintain karo.
3. BITOP destination me FULL result likhta hai — bade bitmaps pe
   heavy; batch job me karo, request path pe nahi.
4. Bit offset LEFT-to-RIGHT hota hai byte ke andar (MSB first) —
   manual byte-parsing karte time confuse mat hona.
```

## Interview Q&A

**Q: Bitmap vs Set vs HyperLogLog — DAU ke liye kya chuno?**
- **Bitmap**: exact count + membership check ("kya user X active tha?") + combine (AND/OR). Dense int IDs chahiye. 12.5 MB/100M.
- **Set (SADD)**: exact + arbitrary IDs, par ~50-100 bytes/member → GBs. Chhote scale pe fine.
- **HyperLogLog**: sirf approximate COUNT (±0.8%), membership check NAHI de sakta. 12 KB flat, IDs kuch bhi ho. Agar sirf "kitne" chahiye aur "kaun" nahi — HLL jeet gaya.

**Q: BITFIELD kab use karoge normal INCR ke bajaye?**
Jab lakhs of chhote counters chahiye — har counter ka alag key (INCR) = per-key ~90 bytes overhead; BITFIELD ek key me packed array rakhta hai (u8/u16 slots), overhead ~zero. Trade-off: max value chhota (u16 = 65535), aur ek key = ek shard (cluster me hot key ban sakta hai).

**Q: Streak feature (Duolingo-style) kaise banaoge?**
Per-user bitmap `streak:<user_id>` jisme bit = day-index since signup. Login pe SETBIT today-index. Current streak = aaj se peeche consecutive 1s count karo (BITFIELD se bytes fetch karke ya Lua me). 365 din = 46 bytes per user.

---

**Related:** [03_geo_hyperloglog_json.md](03_geo_hyperloglog_json.md) (HLL comparison) · [09_persistence_memory.md](09_persistence_memory.md) (memory encodings) · System Design [67_Probabilistic_Data_Structures](../../../02_Year5+_Senior/01_System_Design/HLD_Theory/67_Probabilistic_Data_Structures.md)
