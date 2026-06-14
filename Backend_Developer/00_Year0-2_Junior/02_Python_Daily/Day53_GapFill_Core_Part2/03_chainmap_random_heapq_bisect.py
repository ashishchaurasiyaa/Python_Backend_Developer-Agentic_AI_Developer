"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
DAY 53 — GAP FILL CORE PART 2
FILE 3: ChainMap + random + heapq + bisect (DEEP DIVE)
Architecture Level: Senior Python Backend + Agentic AI
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

THEORY (Hinglish):
  Char "chhote but powerful" stdlib tools jo interviews aur production
  dono me baar-baar aate hain:

  1. collections.ChainMap → multiple dicts ka LAYERED VIEW (copy nahi!)
     Classic use: config precedence — CLI args > env vars > defaults.
     {**a, **b} merge se difference: ChainMap LIVE view hai, underlying
     dict change karo toh ChainMap me turant dikhega.

  2. random → PRNG (Mersenne Twister). Simulations, sampling, testing,
     load balancing ke liye. SECURITY ke liye KABHI NAHI (predictable hai!)
     → tokens/OTP ke liye secrets module.

  3. heapq → min-heap as a list. "Top-K" aur "priority queue" problems
     ka standard answer. heapify O(n), push/pop O(log n).

  4. bisect → sorted list me binary search O(log n) + sorted insert.
     bisect_left vs bisect_right ka difference equal elements pe hi
     dikhta hai — interview me yahi poocha jaata hai.

  DECISION CHEAT (sorted data maintain karna ho):
  - Sirf min/max baar-baar nikalna hai → heapq (full order ki zaroorat nahi)
  - Range queries / "kahan insert hoga" / membership in sorted → bisect
  - Top-K from N (K << N) → heapq.nlargest — full sort O(N log N) se sasta
"""

import heapq
import bisect
import random
import secrets
from collections import ChainMap


# ============ SECTION 1: ChainMap — LAYERED CONFIG (PRECEDENCE) ============
# Real backend pattern: settings 3 jagah se aa sakti hain —
# CLI args (highest priority) > environment vars > hardcoded defaults.

defaults = {"host": "localhost", "port": 8000, "debug": False, "workers": 4}
env_vars = {"port": 9000, "debug": True}        # os.environ se parse hua maan lo
cli_args = {"workers": 8}                        # argparse se aaya

# ChainMap LEFT se RIGHT search karta hai — pehla match jeet jaata hai:
config = ChainMap(cli_args, env_vars, defaults)

print("Section 1 — layered config:")
print(f"  host    = {config['host']}    (defaults se — kahin aur nahi mila)")
print(f"  port    = {config['port']}         (env ne default override kiya)")
print(f"  workers = {config['workers']}            (CLI ne sabko override kiya)")
print(f"  flattened: {dict(config)}")

# LIVE VIEW vs {**a, **b} merge — THE difference:
merged = {**defaults, **env_vars, **cli_args}   # note: merge me RIGHT jeetta hai (ulta order!)
env_vars["port"] = 9999                          # underlying dict badla...

print(f"\n  after env change → ChainMap port: {config['port']}  ← LIVE! change dikha")
print(f"  after env change → merged port:   {merged['port']}  ← frozen snapshot, stale")
# Trade-off: ChainMap har lookup pe layers scan karta hai (thoda slow per-lookup),
# merge ek baar O(n) copy hai phir O(1) lookup. Config layers kam hote hain → ChainMap fine.

# WRITES TRAP: ChainMap pe likho toh SIRF FIRST map me jaata hai:
config["debug"] = False
print(f"\n  write 'debug' → gaya cli_args me: {cli_args}")
print(f"  env_vars untouched: debug is still {env_vars['debug']}")

# DELETE bhi sirf first map se — agar key wahan nahi hai toh KeyError,
# chahe deeper layer me ho:
try:
    del config["host"]   # host sirf defaults me hai, first map (cli_args) me nahi
except KeyError as e:
    print(f"  delete trap: KeyError {e} — first map me 'host' hai hi nahi")

# new_child() — naya EMPTY layer front me push (scoping/interpreter pattern):
request_overrides = config.new_child({"debug": True})  # per-request override
print(f"  new_child debug = {request_overrides['debug']}, parent untouched = {config['debug']}")
print(f"  .maps inspect   = {len(request_overrides.maps)} layers (child + 3)")
# .parents → first layer hata ke baaki ka ChainMap (scope pop karna)
# Yahi pattern Python khud nested scope resolution (LEGB-jaisa lookup) me use hota hai.


# ============ SECTION 2: random MODULE — PROPER TOUR ============

print("\nSection 2 — random module:")

# seed() → reproducibility. Tests/simulations me FIXED seed = same sequence har run:
random.seed(42)
run1 = [random.randint(1, 100) for _ in range(5)]
random.seed(42)
run2 = [random.randint(1, 100) for _ in range(5)]
print(f"  seed(42) twice → {run1} == {run2}: {run1 == run2}")

# choice vs choices vs sample — interview me confusion hota hai:
servers = ["srv-a", "srv-b", "srv-c"]
print(f"  choice (ek item)              : {random.choice(servers)}")

# choices = WITH replacement + WEIGHTS support → weighted load balancing!
# srv-a ko 70% traffic, b ko 20%, c ko 10%:
traffic = random.choices(servers, weights=[70, 20, 10], k=1000)
dist = {s: traffic.count(s) for s in servers}
print(f"  choices(weights=[70,20,10])   : 1000 requests → {dist}")

# sample = WITHOUT replacement (lottery / random test subset):
print(f"  sample (no repeats, k=2)      : {random.sample(servers, k=2)}")
# TRAP: sample(k > len(population)) → ValueError; choices me allowed (repeat hota hai).

# shuffle — IN-PLACE hai aur None return karta hai (classic gotcha):
deck = list(range(10))
result = random.shuffle(deck)
print(f"  shuffle returns: {result}, deck (in-place): {deck}")
# Original chahiye preserved → shuffled_copy = random.sample(deck, k=len(deck))

# randint vs randrange — INCLUSIVE vs EXCLUSIVE end:
#   randint(1, 6)    → 1..6 dono INCLUSIVE (dice)
#   randrange(1, 6)  → 1..5, end EXCLUSIVE (range() jaisa)
#   randrange(0, 101, 5) → step support: 0,5,10..100
print(f"  randint(1,6)={random.randint(1,6)}  randrange(1,6)={random.randrange(1,6)}"
      f"  randrange(0,101,5)={random.randrange(0, 101, 5)}")

# Continuous distributions:
print(f"  uniform(1.0, 2.0) = {random.uniform(1.0, 2.0):.3f}   (flat distribution)")
print(f"  gauss(mu=100, sigma=15) = {random.gauss(100, 15):.1f}  (bell curve — latency simulation)")

# Random CLASS instances — independent generators, global state share nahi karte.
# Concurrency/tests me global random.seed() race conditions deta hai; instances safe:
rng_test = random.Random(1234)        # test fixtures ke liye dedicated generator
rng_sim = random.Random(5678)         # simulation ka apna stream
print(f"  Random(1234).randint: {rng_test.randint(1, 100)} (isolated from global)")

# WHY NOT FOR SECURITY (one-line recap of Day38/secrets):
# random = Mersenne Twister — 624 outputs observe karke poora future PREDICT
# ho jaata hai. Tokens/OTP/password-reset → secrets module (OS entropy, CSPRNG):
print(f"  secrets.token_urlsafe(16) = {secrets.token_urlsafe(16)}  ← yeh use karo tokens ke liye")


# ============ SECTION 3: heapq — PRIORITY QUEUES & TOP-K ============

print("\nSection 3 — heapq:")

# heapify — list ko IN-PLACE min-heap banata hai, O(n) (sort O(n log n) se sasta!):
latencies = [120, 45, 800, 30, 250, 95, 15]
heapq.heapify(latencies)
print(f"  heapified: {latencies}  ← heap[0] hamesha MIN: {latencies[0]}")
# NOTE: baaki elements sorted NAHI hote — sirf heap property hai
# (parent <= children). heap[1] second-smallest hona zaroori nahi!

# push/pop — O(log n) each:
heapq.heappush(latencies, 5)
print(f"  after push(5), pop() → {heapq.heappop(latencies)} then {heapq.heappop(latencies)}")
# heappushpop(h, x) aur heapreplace(h, x) — push+pop combos, ek operation me efficient.

# MIN-HEAP ONLY — max-heap chahiye toh NEGATE trick:
scores = [88, 95, 70, 99, 60]
max_heap = [-s for s in scores]
heapq.heapify(max_heap)
print(f"  max via negate: {-heapq.heappop(max_heap)}, {-heapq.heappop(max_heap)}")

# PRIORITY QUEUE — tuples se: heap tuple ko element-wise compare karta hai.
# TRAP: (priority, task_dict) crash karta hai jab priorities equal hon —
# tie pe Python AGLA element compare karega aur dict comparable nahi hai!
task_a = {"name": "send_email"}
task_b = {"name": "resize_image"}
try:
    h = []
    heapq.heappush(h, (1, task_a))
    heapq.heappush(h, (1, task_b))   # same priority → dict < dict attempt!
except TypeError as e:
    print(f"  tie-break trap: TypeError: {e}")

# FIX — (priority, counter, item) pattern: counter UNIQUE hai, tie wahin
# break ho jaata hai, item tak comparison kabhi pahunchta hi nahi.
# Bonus: same priority me FIFO order milta hai (counter insertion order hai):
from itertools import count
counter = count()
pq: list[tuple[int, int, dict]] = []
heapq.heappush(pq, (2, next(counter), {"name": "report_gen"}))
heapq.heappush(pq, (1, next(counter), task_a))
heapq.heappush(pq, (1, next(counter), task_b))   # ab koi crash nahi

print("  priority order:", end=" ")
while pq:
    prio, _, task = heapq.heappop(pq)
    print(f"p{prio}:{task['name']}", end="  ")
print()

# nlargest / nsmallest — Top-K ka idiomatic answer, key= bhi leta hai:
requests_log = [
    {"path": "/api/chat", "ms": 1200}, {"path": "/health", "ms": 5},
    {"path": "/api/search", "ms": 450}, {"path": "/api/users", "ms": 90},
    {"path": "/api/embed", "ms": 2300},
]
slowest = heapq.nlargest(3, requests_log, key=lambda r: r["ms"])
print(f"  3 slowest endpoints: {[r['path'] for r in slowest]}")

# DECISION — nlargest vs sort:
#   K chhota, N bada (top-10 of 10M)  → nlargest: O(N log K), memory O(K)
#   K ~ N ya sab chahiye sorted       → sorted(): O(N log N), simpler + stable
#   K == 1                            → max()/min() — sabse sasta, ye hi lo


# ============ SECTION 4: bisect — BINARY SEARCH ON SORTED LISTS ============

print("\nSection 4 — bisect:")

# bisect_left vs bisect_right — difference SIRF equal elements pe:
data = [10, 20, 20, 20, 30]
print(f"  data = {data}, searching 20:")
print(f"  bisect_left  → {bisect.bisect_left(data, 20)}   (pehle 20 se PEHLE — index 1)")
print(f"  bisect_right → {bisect.bisect_right(data, 20)}   (aakhri 20 ke BAAD — index 4)")
# Memory trick: left = "equal block ke LEFT edge", right = "RIGHT edge ke baad".
# bisect.bisect == bisect_right (default).
# Count of 20s in O(log n): right - left = 4 - 1 = 3 (sorted data me Counter se sasta!)
print(f"  count via bisect: {bisect.bisect_right(data, 20) - bisect.bisect_left(data, 20)}")

# EXACT SEARCH pattern — bisect index deta hai, "mila ya nahi" khud check karo:
def binary_search(sorted_list: list, target) -> int:
    """Index of target, -1 if absent — bisect_left + verify."""
    i = bisect.bisect_left(sorted_list, target)
    if i < len(sorted_list) and sorted_list[i] == target:
        return i
    return -1

print(f"  binary_search(data, 30) = {binary_search(data, 30)}, "
      f"(data, 25) = {binary_search(data, 25)}")

# CLASSIC EXAMPLE — grade boundaries (Python docs ka famous example):
def grade(score: int, boundaries=(60, 70, 80, 90), grades="FDCBA") -> str:
    """bisect index hi grade ka index ban jaata hai — zero if/elif chains!"""
    return grades[bisect.bisect(boundaries, score)]

print(f"  grades for [55,60,72,89,90,100] = {[grade(s) for s in (55, 60, 72, 89, 90, 100)]}")
# NOTE: bisect (right) use kiya isliye score == boundary (60) UPAR wale grade me
# jaata hai (D). bisect_left hota toh 60 → F. Boundary inclusive kis taraf hai —
# yahi left/right ka business-logic matlab hai. Same pattern: tax slabs,
# rate-limit tiers, latency buckets (histogram binning).

# insort — sorted position pe insert (search O(log n) + shift O(n)):
leaderboard = [1500, 1800, 2100, 2400]
bisect.insort(leaderboard, 2000)
print(f"  insort(2000) → {leaderboard}")
# insort_left/insort_right bhi hain — equal scores me naya KAHAN ghusega (stability).

# key= parameter (3.10+) — objects ki sorted list me direct kaam:
players = [("dia", 1500), ("raj", 1800), ("amy", 2400)]
pos = bisect.bisect_left(players, 2000, key=lambda p: p[1])
print(f"  rating 2000 insert position (key=) = {pos}")

# DECISION — sorted list (bisect) vs heapq:
#   "kth element / range / membership / neighbors" queries → bisect wali sorted list
#   sirf "sabse chhota/bada nikalo repeatedly"            → heapq
#   Kyun na hamesha bisect? insort ka shift O(n) hai; heap push O(log n).
#   Bahut saare random inserts + sirf min/max → heap jeet jaata hai.
#   (Heavy inserts + sorted queries dono chahiye → 3rd party `sortedcontainers`.)

print("\nDone — config layers, weighted randomness, top-K, binary search: "
      "chaar tools, chaar one-liner superpowers.")


# ============ INTERVIEW QUESTIONS ============
"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
INTERVIEW Q&A:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Q1: ChainMap aur {**a, **b} merge me kya difference hai?
A:  (1) ChainMap LIVE VIEW hai — underlying dict badle toh lookup me
    turant reflect hota hai; merge frozen snapshot hai. (2) ChainMap me
    LEFT map jeetta hai, merge me RIGHT (ulta order — common bug!).
    (3) ChainMap copy nahi banata (memory-cheap on huge dicts), merge
    O(n) copy karta hai but phir O(1) lookup deta hai.

Q2: ChainMap pe write/delete kahan jaata hai?
A:  SIRF first map me. config["x"] = 1 hamesha maps[0] me likhta hai,
    chahe "x" deeper layer me already ho (effectively override banta hai).
    del bhi sirf first map se — key deeper ho toh KeyError. Yeh design
    hi precedence-layering ko safe banata hai: defaults kabhi corrupt
    nahi hote.

Q3: new_child() ka use case?
A:  Front me naya layer push karta hai — nested scopes ka pattern.
    Per-request config override, interpreter ke variable scopes,
    template context inheritance. .parents se layer pop hota hai.

Q4: random.choice vs choices vs sample?
A:  choice  → ek element. choices → k elements WITH replacement + weights
    support (weighted load balancing / A-B traffic split). sample → k
    elements WITHOUT replacement (lottery, random test subset).
    sample me k > population → ValueError; choices me valid hai.

Q5: random module security ke liye kyun nahi?
A:  Mersenne Twister deterministic PRNG hai — internal state 624 outputs
    se reconstruct ho jaata hai, phir saare future values predictable.
    Session tokens/OTP/reset links ke liye secrets module (OS-level
    CSPRNG entropy): secrets.token_urlsafe(), secrets.choice(),
    secrets.randbelow().

Q6: Tests me randomness reproducible kaise banate ho?
A:  Fixed seed: random.seed(42) → same sequence har run. Better: apna
    random.Random(42) INSTANCE banao — global state share nahi hota,
    isliye parallel tests / libraries ke random calls tumhara sequence
    disturb nahi karte.

Q7: heapify O(n) kaise — n elements push karna toh O(n log n) hota?
A:  heapify bottom-up sift-down karta hai: aadhe elements leaves hote
    hain (0 work), upar ke levels par exponentially kam nodes par zyada
    work — mathematical sum O(n) nikalta hai. Isliye "list ko ek baar
    heap banao" hamesha heapify se karo, loop-of-heappush se nahi.

Q8: Python me max-heap kaise banaoge?
A:  heapq sirf min-heap hai. Standard trick: values NEGATE karke push
    karo, pop pe wapas negate. Objects ke liye: (-priority, counter, item)
    tuple. (Ya nlargest use karo agar one-shot top-K hai.)

Q9: (priority, item) tuple heap me kab crash hota hai? Fix?
A:  Jab do items ki priority EQUAL ho — tuple comparison agla element
    compare karta hai, aur dicts/custom objects me < defined nahi →
    TypeError. Fix: (priority, counter, item) — itertools.count() ka
    unique counter tie wahin break kar deta hai aur FIFO order free
    me milta hai. asyncio aur queue.PriorityQueue patterns yahi use karte hain.

Q10: nlargest(k, data) vs sorted(data)[:k]?
A:  nlargest O(N log K) time + O(K) memory — K chhota ho (top-10 of
    millions) toh clear winner, streaming data pe bhi chalta hai.
    sorted O(N log N) + full copy — jab K ~ N ho ya poora sorted output
    chahiye. K == 1 → max()/min() best. Senior answer me ye teeno
    thresholds bolo.

Q11: bisect_left vs bisect_right ka exact difference?
A:  Difference SIRF tab jab target already list me ho. bisect_left equal
    elements ke block ke PEHLE ka index deta hai, bisect_right BAAD ka.
    Uses: left → exact-search/"pehli occurrence"; right → "kitne elements
    <= x" / boundary-inclusive binning. right - left = count of x in
    O(log n).

Q12: Grade-boundary jaisa binning bisect se kaise?
A:  boundaries=(60,70,80,90), grades="FDCBA" — bisect(boundaries, score)
    ka return index seedha grades me index ban jaata hai. if/elif chain
    khatam, O(log n), aur boundary-inclusion left/right choice se control
    hota hai. Same pattern: tax slabs, rate-limit tiers, histogram buckets.

Q13: Sorted list maintain karni hai — bisect.insort lo ya heapq?
A:  Dekho QUERIES kya hain. Sirf min/max repeatedly → heapq (push O(log n)
    vs insort ka O(n) shift). Arbitrary position/range/neighbor queries →
    bisect sorted list. Dono heavy ho → stdlib me nahi hai, third-party
    sortedcontainers.SortedList (industry standard answer).
"""
