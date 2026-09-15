"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
DAY 53 — GAP FILL CORE PART 2
FILE 2: Epoch / Timestamps + time MODULE (DEEP DIVE)
Architecture Level: Senior Python Backend + Agentic AI
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

THEORY (Hinglish):
  Epoch / Unix timestamp = seconds since 1970-01-01 00:00:00 UTC.
  Yeh ek ABSOLUTE point hai — timestamp me koi timezone NAHI hota.
  1718000000 ka matlab duniya me har jagah SAME instant hai.
  Timezone sirf tab aata hai jab us instant ko HUMAN-READABLE banana ho.

  Backend me 3 classic time-bugs:
  1. fromtimestamp() bina tz= ke → server ke LOCAL timezone me convert
     hota hai. Laptop pe IST, prod server pe UTC → alag-alag results!
  2. Milliseconds vs seconds confusion — JavaScript Date.now() MS deta hai,
     Python time.time() SECONDS. Direct paste karo toh date year 56246 me!
  3. time.time() se duration measure karna — NTP/admin clock adjust kare
     toh duration NEGATIVE bhi aa sakta hai. Durations ke liye monotonic().

  time module ke 5 clocks — DECISION TABLE:
  ┌────────────────┬──────────────────┬─────────────────────────────────┐
  │ Function       │ Kya hai          │ Kab use karo                    │
  ├────────────────┼──────────────────┼─────────────────────────────────┤
  │ time.time()    │ Wall clock, epoch│ Timestamps store/log karna      │
  │                │ NTP-adjustable   │ KABHI duration measure mat karo │
  │ monotonic()    │ Kabhi peeche     │ Timeouts, retries, durations    │
  │                │ nahi jaata       │ (asyncio internally yahi use)   │
  │ perf_counter() │ Highest resolution│ Benchmarking / profiling       │
  │                │ monotonic clock  │ (timeit internally yahi use)    │
  │ process_time() │ Sirf CPU time of │ CPU-bound work measure karna —  │
  │                │ THIS process     │ sleep/IO COUNT NAHI hota        │
  │ sleep()        │ Block current    │ Polling, backoff (async me      │
  │                │ thread           │ asyncio.sleep, yeh NAHI!)       │
  └────────────────┴──────────────────┴─────────────────────────────────┘
"""

import sys
import time
from datetime import datetime, timezone, timedelta

PY = (sys.version_info.major, sys.version_info.minor)
print(f"Python: {PY[0]}.{PY[1]}\n")


# ============ SECTION 1: EPOCH BASICS — time.time() AUR datetime.timestamp() ============

now_epoch = time.time()
print("Section 1 — epoch basics:")
print(f"  time.time()            = {now_epoch:.3f}  (float seconds since 1970 UTC)")

# datetime → epoch: .timestamp()
now_dt = datetime.now(timezone.utc)        # ALWAYS aware datetime banao
print(f"  datetime.timestamp()   = {now_dt.timestamp():.3f}")

# TRAP: naive datetime ka .timestamp() — Python use LOCAL time maan leta hai!
naive = datetime(2026, 6, 12, 10, 0, 0)               # koi tz nahi — "naive"
aware = datetime(2026, 6, 12, 10, 0, 0, tzinfo=timezone.utc)
print(f"  naive.timestamp() = {naive.timestamp():.0f}  ← server ke LOCAL tz se converted!")
print(f"  aware.timestamp() = {aware.timestamp():.0f}  ← deterministic, har machine pe same")
diff_hrs = (naive.timestamp() - aware.timestamp()) / 3600
print(f"  difference = {diff_hrs:+.1f} hours — yahi 'works on my machine' bug hai")
# IST laptop pe diff = -5.5h, UTC prod server pe diff = 0 → tests pass, prod broken.


# ============ SECTION 2: fromtimestamp() LOCAL-TZ TRAP (sabse common bug) ============

epoch_val = 1718000000  # koi DB se aaya timestamp

print("\nSection 2 — fromtimestamp() trap:")
# WRONG: bina tz ke — server ke local timezone me convert + NAIVE result:
local_dt = datetime.fromtimestamp(epoch_val)
print(f"  fromtimestamp(x)                  = {local_dt}  (naive! tz={local_dt.tzinfo})")

# RIGHT: hamesha tz=timezone.utc pass karo — aware UTC datetime milta hai:
utc_dt = datetime.fromtimestamp(epoch_val, tz=timezone.utc)
print(f"  fromtimestamp(x, tz=timezone.utc) = {utc_dt}")

# Display ke liye user ke timezone me convert karo (storage NAHI):
ist = timezone(timedelta(hours=5, minutes=30), name="IST")
print(f"  .astimezone(IST) for display      = {utc_dt.astimezone(ist)}")

# DEPRECATED (3.12+): datetime.utcfromtimestamp() aur datetime.utcnow()
#   Problem: yeh UTC me convert toh karte hain par NAIVE datetime dete hain —
#   aage koi .timestamp() kare toh wapas local-tz assumption lag jaata hai. Cycle of bugs.
#   Migration:
#     datetime.utcnow()              → datetime.now(timezone.utc)
#     datetime.utcfromtimestamp(x)   → datetime.fromtimestamp(x, tz=timezone.utc)
if PY >= (3, 12):
    import warnings
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        datetime.utcfromtimestamp(epoch_val)
        if caught:
            print(f"  3.12 deprecation: {caught[0].category.__name__} raised for utcfromtimestamp")

# GOLDEN RULE: "Aware everywhere" — naive datetime sirf bug ka invitation hai.


# ============ SECTION 3: MS-vs-SEC CONFUSION (JS INTEROP BUG) ============
# JavaScript: Date.now() → MILLISECONDS.  Python: time.time() → SECONDS.
# Frontend se aaya timestamp seedha fromtimestamp() me daalo toh —

js_timestamp = 1718000000000  # frontend ne bheja (ms me)

print("\nSection 3 — ms vs sec bug:")
# Milliseconds ko seconds samajh ke parse karo toh year ~56411 banta hai —
# datetime ka MAX year 9999 hai, isliye yeh seedha CRASH karta hai:
try:
    datetime.fromtimestamp(js_timestamp, tz=timezone.utc)  # treated as seconds
except (ValueError, OverflowError, OSError) as e:
    print(f"  treated as seconds → {type(e).__name__}: {e}")
    # Lucky case: crash hua toh pakda gaya. UNLUCKY case chhote ms values
    # ke saath hota hai — silent galat date, koi exception nahi.

right = datetime.fromtimestamp(js_timestamp / 1000, tz=timezone.utc)
print(f"  divided by 1000    → {right}")

# Defensive check pattern (API boundary pe):
def parse_epoch(value: float) -> datetime:
    """Heuristic: 1e11 se bada epoch-seconds ~ year 5138 — pakka ms hai."""
    if value > 1e11:
        value = value / 1000
    return datetime.fromtimestamp(value, tz=timezone.utc)

print(f"  parse_epoch(seconds) = {parse_epoch(1718000000)}")
print(f"  parse_epoch(millis)  = {parse_epoch(1718000000000)}  ← auto-detected")
# Better fix: API contract me unit FIX karo (e.g. "epoch_ms" field name) —
# heuristics last resort hain, naming first defense.


# ============ SECTION 4: DB STORAGE — EPOCH vs ISO STRING (DECISION) ============
"""
Backend design question: timestamps DB me kaise store karein?

┌──────────────┬───────────────────────────┬──────────────────────────────┐
│              │ Epoch (int/bigint)        │ ISO 8601 / native timestamptz│
├──────────────┼───────────────────────────┼──────────────────────────────┤
│ Size         │ 8 bytes                   │ 25+ bytes (string) / 8 native│
│ Human-read   │ NO (debugging painful)    │ YES                          │
│ Sorting      │ trivial int sort          │ string sort works (ISO magic)│
│ Range queries│ fast int compare          │ native type bhi fast         │
│ TZ ambiguity │ none (always UTC instant) │ string me offset hona zaroori│
│ Cross-system │ universal (JS/Go/Redis)   │ parsing libraries chahiye    │
│ Leap seconds │ smeared/ignored           │ representable                │
└──────────────┴───────────────────────────┴──────────────────────────────┘

Senior recommendation:
- Postgres/MySQL → native `timestamptz` column (DB UTC me store karta hai)
- Redis / JWT exp / cache TTL / event logs → epoch int (compact + universal)
- JSON APIs → ISO 8601 string WITH offset ("2026-06-12T10:00:00+00:00")
- Jo bhi chuno: STORE in UTC, CONVERT at display. Hamesha.
"""

# JWT-style exp claim — epoch ka classic use:
exp = int(time.time()) + 3600  # 1 hour validity
print("Section 4 — JWT exp claim (epoch):", exp,
      "→ valid till", datetime.fromtimestamp(exp, tz=timezone.utc).isoformat())


# ============ SECTION 5: time MODULE — 5 CLOCKS KA DEMO ============

print("\nSection 5 — the five clocks:")
print(f"  time.time()         = {time.time():.4f}   (epoch, NTP-adjustable)")
print(f"  time.monotonic()    = {time.monotonic():.4f}   (arbitrary start, never backwards)")
print(f"  time.perf_counter() = {time.perf_counter():.4f}   (highest resolution)")
print(f"  time.process_time() = {time.process_time():.4f}   (CPU-only, no sleep/IO)")

# TRAP: monotonic/perf_counter ki ABSOLUTE value meaningless hai —
# sirf DO readings ka DIFFERENCE meaningful hai. Inhe store/compare-across-process mat karo.

# WHY time.time() durations ke liye galat hai:
#   start = time.time(); ...work...; dur = time.time() - start
#   Beech me NTP sync ya admin ne clock change kiya → dur galat, NEGATIVE bhi possible.
#   monotonic() guaranteed never-backwards hai — timeouts/retries iske bina mat likho.

# Demo: sleep CPU time me count NAHI hota —
wall_start = time.perf_counter()
cpu_start = time.process_time()

time.sleep(0.2)                      # IO/wait simulate — CPU idle
_ = sum(i * i for i in range(500_000))  # CPU-bound work

wall_dur = time.perf_counter() - wall_start
cpu_dur = time.process_time() - cpu_start
print(f"\n  wall time (perf_counter) = {wall_dur:.3f}s  (sleep included)")
print(f"  cpu time (process_time)  = {cpu_dur:.3f}s  (sleep EXCLUDED)")
print("  → wall >> cpu hai toh process WAIT kar raha tha (IO-bound clue!)")
# Profiling me yahi comparison batata hai: optimize CPU karein ya IO/network.


# ============ SECTION 6: BENCHMARK PATTERN — perf_counter ============

def benchmark(func, *args, repeat: int = 5) -> float:
    """Best-of-N pattern — minimum lo, average nahi.
    Kyun min? Noise (OS scheduling, GC) sirf time BADHATA hai, kam nahi karta.
    Minimum = sabse clean run. timeit module bhi yahi philosophy use karta hai."""
    best = min(
        (lambda: (s := time.perf_counter(), func(*args), time.perf_counter() - s)[2])()
        for _ in range(repeat)
    )
    return best

print("\nSection 6 — benchmark demo (best of 5):")
t_list = benchmark(lambda: [i * i for i in range(100_000)])
t_gen = benchmark(lambda: sum(i * i for i in range(100_000)))
print(f"  list comprehension : {t_list * 1000:.2f} ms")
print(f"  generator sum      : {t_gen * 1000:.2f} ms")

# time.sleep() notes:
# - Current THREAD ko block karta hai (GIL release hota hai — dusre threads chalte hain)
# - Async code me time.sleep() = poora event loop freeze → asyncio.sleep() use karo
# - Precision OS-dependent hai (~1-15ms granularity) — hard-realtime ke liye nahi hai


# ============ SECTION 7: ISO FORMATS RECAP — isoformat / fromisoformat / 'Z' ============

print("\nSection 7 — ISO 8601 round-trip:")
dt = datetime(2026, 6, 12, 10, 30, 0, tzinfo=timezone.utc)
iso = dt.isoformat()
print(f"  isoformat()        = {iso}")            # 2026-06-12T10:30:00+00:00
print(f"  custom sep/spec    = {dt.isoformat(sep=' ', timespec='seconds')}")

# Round trip — fromisoformat:
parsed = datetime.fromisoformat(iso)
print(f"  fromisoformat()    = {parsed}  (aware: {parsed.tzinfo is not None})")

# 'Z' SUFFIX TRAP: JS/Go/Java "2026-06-12T10:30:00Z" bhejte hain ('Z' = Zulu = UTC).
# Python 3.11+ fromisoformat 'Z' samajh leta hai; 3.10 aur neeche ValueError!
z_string = "2026-06-12T10:30:00Z"
if PY >= (3, 11):
    parsed_z = datetime.fromisoformat(z_string)
    print(f"  'Z' parse (3.11+)  = {parsed_z}")
else:
    # Portable fallback jo har version pe chalta hai:
    parsed_z = datetime.fromisoformat(z_string.replace("Z", "+00:00"))
    print(f"  'Z' via replace()  = {parsed_z}")

# Ulta direction ka TRAP: Python isoformat() 'Z' NAHI deta, '+00:00' deta hai.
# Strict-JS consumers ke liye:
js_friendly = dt.isoformat().replace("+00:00", "Z")
print(f"  JS-friendly output = {js_friendly}")

print("\nDone — 'store UTC epoch/timestamptz, convert at the edge, "
      "monotonic for durations' — yeh 3 rules yaad rakho.")


# ============ INTERVIEW QUESTIONS ============
"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
INTERVIEW Q&A:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Q1: Epoch timestamp me timezone hota hai kya?
A:  NAHI — epoch ek absolute instant hai (seconds since 1970-01-01 UTC).
    1718000000 Mumbai me bhi wahi instant hai jo New York me. Timezone
    sirf DISPLAY ke waqt aata hai. Isliye epoch storage tz-ambiguity-free hai.

Q2: datetime.fromtimestamp() ka trap kya hai?
A:  Bina tz= argument ke yeh SERVER ke local timezone me convert karta hai
    aur NAIVE datetime return karta hai. Dev laptop (IST) aur prod (UTC)
    pe alag jawab. Fix: HAMESHA fromtimestamp(x, tz=timezone.utc).

Q3: utcnow()/utcfromtimestamp() 3.12 me deprecated kyun hue?
A:  Dono NAIVE datetime return karte the — value UTC ki hoti thi par
    Python ko pata nahi hota tha. Aage .timestamp() call karo toh local-tz
    assume hota aur galat epoch nikalta. Replacement:
    datetime.now(timezone.utc) aur fromtimestamp(x, tz=timezone.utc) —
    dono AWARE return karte hain.

Q4: time.time() vs monotonic() vs perf_counter() vs process_time()?
A:  time()        → wall clock (epoch). NTP/admin adjust kar sakta hai,
                    peeche bhi jaa sakta hai. Sirf timestamps ke liye.
    monotonic()   → kabhi backwards nahi. Timeouts/durations ka standard.
    perf_counter()→ monotonic + highest available resolution. Benchmarking.
    process_time()→ sirf is process ka CPU time; sleep/IO count nahi hota.
    One-liner: "timestamp chahiye toh time, duration chahiye toh monotonic,
    benchmark chahiye toh perf_counter, CPU profile chahiye toh process_time."

Q5: time.time() se timeout measure karne me kya bug hai?
A:  NTP sync ya manual clock change hone par elapsed = end - start galat
    ho jaata hai — negative bhi. Ek real incident pattern: clock 30s
    peeche gaya, saare timeouts 30s extra wait karne lage. monotonic()
    is problem se immune hai (asyncio internally isi liye use karta hai).

Q6: JS frontend se timestamp aaya, Python me 'year 56411 out of range' kyon?
A:  JavaScript Date.now() MILLISECONDS deta hai, Python seconds expect
    karta hai. 1000x bada number = ~54,000 saal future = datetime ke
    max year 9999 ke bahar → ValueError. Fix: /1000 karo, ya API contract
    me field ka naam epoch_ms/epoch_s rakho taaki unit ambiguity hi na rahe.
    Zyada dangerous ulta case hai: Python seconds JS me bhejo toh JS use
    ms samajh ke 1970 ke paas ki date dikhata hai — SILENT bug, no crash.

Q7: DB me epoch int store karein ya ISO string / timestamptz?
A:  Relational DB → native timestamptz (Postgres UTC me normalize karta hai,
    indexes + range queries native). Redis/JWT/event-streams → epoch int
    (compact, universal, language-agnostic). JSON APIs → ISO 8601 with
    offset. Common rule: STORE UTC, CONVERT at display layer.

Q8: fromisoformat() 'Z' suffix handle karta hai?
A:  Python 3.11+ haan; 3.10 aur neeche ValueError deta hai —
    string.replace("Z", "+00:00") karna padta tha. Reverse trap bhi hai:
    isoformat() '+00:00' deta hai, 'Z' nahi — strict JS consumers ke liye
    manually replace karo.

Q9: process_time() < perf_counter() difference se kya diagnose hota hai?
A:  Agar wall time (perf_counter) CPU time (process_time) se bahut zyada
    hai toh process zyada time WAIT kar raha tha — IO/network/sleep bound.
    Dono barabar → CPU bound. Optimization strategy isi se decide hoti hai
    (async/connection-pooling vs algorithm/C-extension).

Q10: Benchmark me average ki jagah minimum kyun lete hain?
A:  System noise (OS scheduling, GC, cache misses) timing sirf BADHA
    sakta hai, ghata nahi. Isliye minimum = code ka true cost ke sabse
    paas. timeit.repeat() docs bhi yahi recommend karte hain.
"""
