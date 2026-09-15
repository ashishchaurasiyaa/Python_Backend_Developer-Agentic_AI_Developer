"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
DAY 53 (Part 1) — assert, __debug__, EAFP vs LBYL
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

WHY THIS MATTERS:
  Production codebases me sabse common security bug ye hota hai ki
  developer ne `assert` ko input validation ke liye use kar liya —
  aur production me `python -O` chalte hi WOH PURA CHECK GAYAB ho gaya.

  Dusri taraf — EAFP vs LBYL Python ki core philosophy hai.
  Interview me "Pythonic code kya hota hai?" ka asli jawab yahi hai.

ARCHITECTURE UNDERSTANDING:
  assert cond, msg
    → compile hota hai roughly is form me:
        if __debug__:
            if not cond:
                raise AssertionError(msg)
    → `python -O` chalao to __debug__ = False ho jaata hai
      aur assert statements BYTECODE ME HI NAHI AATE (strip ho jaate hain)

  EAFP = "Easier to Ask Forgiveness than Permission"
    → pehle action karo, exception aaye to handle karo (try/except)
  LBYL = "Look Before You Leap"
    → pehle check karo, phir action karo (if condition)

  Python culture = EAFP. Kyun? Neeche detail me.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import os
import subprocess
import sys

# ============ SECTION 1: assert — SYNTAX AUR BASIC BEHAVIOR ============

# Syntax: assert <condition>, <optional_message>
# Condition False hua → AssertionError raise hota hai (message ke saath)

def calculate_discount(price: float, discount_pct: float) -> float:
    # Internal invariant: ye function ke ANDAR ka contract hai —
    # caller (hamara apna code) ko kabhi negative price nahi bhejna chahiye.
    # Agar bheja, to ye PROGRAMMER BUG hai — isliye assert theek hai.
    assert price >= 0, f"price negative nahi ho sakta, mila: {price}"
    assert 0 <= discount_pct <= 100, f"discount 0-100 ke beech hona chahiye: {discount_pct}"
    return price * (1 - discount_pct / 100)


print("=== SECTION 1: basic assert ===")
print(f"Discounted: {calculate_discount(1000, 10)}")    # 900.0

try:
    calculate_discount(-50, 10)
except AssertionError as e:
    print(f"AssertionError pakda: {e}")

# TRAP: assert me TUPLE mat do!
# assert (cond, "msg")  ← ye HAMESHA True hai (non-empty tuple truthy hota hai)
# Python 3 me iske liye SyntaxWarning aata hai, par code chal jaata hai.
# Sahi: assert cond, "msg"   (comma assert ka hissa hai, tuple nahi)


# ============ SECTION 2: KAB assert USE KARNA, KAB NAHI ============

"""
USE KARO (dev-time checks, internal invariants):
  ✓ Function ke andar ke assumptions:  assert node is not None  (algorithm invariant)
  ✓ "Ye branch kabhi nahi aani chahiye": assert False, "unreachable"
  ✓ Test files me (pytest to assert pe hi bana hai)
  ✓ Sanity checks jo sirf debugging me madad karte hain

KABHI MAT KARO (assert hata do to bhi program SAHI chalna chahiye):
  ✗ User input validation        → raise ValueError karo
  ✗ API request validation       → HTTPException / ValidationError
  ✗ Security checks (auth/perms) → raise PermissionError
  ✗ Data integrity jisse business logic depend karta hai
  ✗ Side-effect wale expressions: assert db.save(user) ← -O me save() HI NAHI CHALEGA!

GOLDEN RULE:
  assert = "agar ye fail hua to MERE CODE me bug hai"
  raise  = "agar ye fail hua to BAHAR se galat data aaya hai"
"""

def transfer_money_WRONG(balance: float, amount: float) -> float:
    # ❌ GALAT — security check assert se. python -O me ye check GAYAB!
    assert amount <= balance, "Insufficient funds"
    return balance - amount

def transfer_money_RIGHT(balance: float, amount: float) -> float:
    # ✓ SAHI — explicit raise, ye -O me bhi chalega, hamesha
    if amount > balance:
        raise ValueError(f"Insufficient funds: balance={balance}, amount={amount}")
    return balance - amount

print("\n=== SECTION 2: assert vs raise for validation ===")
try:
    transfer_money_RIGHT(100, 500)
except ValueError as e:
    print(f"ValueError (sahi tarika): {e}")


# ============ SECTION 3: python -O, __debug__, PYTHONOPTIMIZE — LIVE DEMO ============

# __debug__ ek compile-time constant hai:
#   normal run     → __debug__ = True,  asserts CHALTE hain
#   python -O      → __debug__ = False, asserts STRIP (docstrings rehte hain)
#   python -OO     → -O + docstrings bhi strip
#   PYTHONOPTIMIZE=1 env var → same as -O (Docker images me aksar set hota hai!)

print("\n=== SECTION 3: -O flag demo (subprocess se) ===")
print(f"Is process me __debug__ = {__debug__}")

demo_code = (
    "assert False, 'ye assertion fail honi chahiye thi!'\n"
    "print(f'assert SKIP ho gaya! __debug__ = {__debug__}')\n"
)

# Normal run — assert fail karega, exit code 1
normal = subprocess.run([sys.executable, "-c", demo_code],
                        capture_output=True, text=True)
print(f"Normal run   → exit={normal.returncode} (AssertionError aaya)")

# -O run — wahi code, assert bytecode me hi nahi hai, print chal gaya
optimized = subprocess.run([sys.executable, "-O", "-c", demo_code],
                           capture_output=True, text=True)
print(f"-O run       → exit={optimized.returncode}, output: {optimized.stdout.strip()}")

# PYTHONOPTIMIZE env var — bina -O flag ke bhi wahi effect
env = {**os.environ, "PYTHONOPTIMIZE": "1"}
env_run = subprocess.run([sys.executable, "-c", demo_code],
                         capture_output=True, text=True, env=env)
print(f"PYTHONOPTIMIZE=1 → exit={env_run.returncode}, output: {env_run.stdout.strip()}")

"""
YE TRAP ISLIYE KHATARNAK HAI KYUNKI:
  - Dev machine pe sab asserts chalte hain → tests pass
  - Kisi ne prod Dockerfile me PYTHONOPTIMIZE=1 daal diya (perf ke naam pe)
  - Saare auth/validation asserts SILENTLY gayab → security hole, koi error nahi
  - Isliye: assert for validation/security = NEVER. Period.
"""


# ============ SECTION 4: EAFP vs LBYL — PHILOSOPHY ============

"""
EAFP — "Easier to Ask Forgiveness than Permission"
  → Seedha kaam karo, gadbad hui to exception handle karo.
  → try / except style.

LBYL — "Look Before You Leap"
  → Pehle conditions check karo, phir kaam karo.
  → if / else style.

PYTHON CULTURE = EAFP. Kyun?
  1. ATOMICITY: check aur action ke BEECH state badal sakti hai
     (threads, dusra process, filesystem) — EAFP me check+action ek hi step hai.
  2. SPEED (happy path): dict me key 99% baar hoti hai to 'in' check
     har baar EXTRA lookup hai; try/except me success pe zero overhead.
     (Note: exception RAISE hona mehnga hai — try block lagana sasta hai.)
  3. DUCK TYPING: "kya ye object file-like hai?" ke 10 checks likhne se
     behtar — .read() call karo, TypeError/AttributeError aaye to handle.
  C/Java culture LBYL hai kyunki wahan exceptions mehngi/awkward hain.
"""

# ============ SECTION 5: EXAMPLE 1 — DICT ACCESS ============

print("\n=== SECTION 5: dict access — EAFP vs LBYL ===")
config = {"host": "localhost", "port": 8000}

# LBYL — do lookups: ek 'in' me, ek access me
if "port" in config:
    port = config["port"]
else:
    port = 8080
print(f"LBYL port: {port}")

# EAFP — ek hi lookup, missing case exception me
try:
    timeout = config["timeout"]
except KeyError:
    timeout = 30
print(f"EAFP timeout: {timeout}")

# KAB KAUN JEETTA HAI:
#  - Key MOSTLY present → EAFP jeetta hai (no double lookup, no raise)
#  - Key MOSTLY absent  → LBYL jeetta hai (exception raise karna ~10x slow)
#  - Real life me: config.get("timeout", 30) — dono se behtar idiom yahan!
#    Par .get() sirf dict pe hai; EAFP pattern HAR jagah kaam karta hai.


# ============ SECTION 6: EXAMPLE 2 — FILE OPEN (TOCTOU RACE!) ============

print("\n=== SECTION 6: file open — TOCTOU race condition ===")

# ❌ LBYL — RACE CONDITION (TOCTOU = Time-Of-Check to Time-Of-Use)
# os.path.exists() ke True return karne KE BAAD, open() chalne SE PEHLE,
# dusra process/thread file DELETE kar sakta hai → crash anyway!
filename = "day53_demo_missing.txt"
if os.path.exists(filename):              # CHECK  ← yahan tak file thi...
    # ...yahan koi aur process file uda sakta hai...
    with open(filename) as f:             # USE    ← ...aur yahan FileNotFoundError!
        data = f.read()
else:
    print("LBYL: file nahi mili (par ye check race-prone hai)")

# ✓ EAFP — check aur use EK HI atomic operation me; race impossible
try:
    with open(filename) as f:
        data = f.read()
except FileNotFoundError:
    print("EAFP: FileNotFoundError handle kiya — koi race window nahi")

# Security angle: TOCTOU bugs (CWE-367) attackers exploit karte hain —
# check ke baad file ko symlink se replace karke privileged process se
# galat file likhwa dete hain. EAFP + 'x' mode (next file me) iska ilaaj hai.


# ============ SECTION 7: EXAMPLE 3 — ATTRIBUTE ACCESS ============

print("\n=== SECTION 7: attribute access — hasattr vs try ===")

class StripePayment:
    def refund(self):
        return "Stripe refund processed"

class CashPayment:
    pass  # refund support nahi hai

payments = [StripePayment(), CashPayment()]

# LBYL — hasattr (jo internally khud try/except getattr hi hai!)
for p in payments:
    if hasattr(p, "refund"):
        print(f"LBYL: {p.refund()}")
    else:
        print(f"LBYL: {type(p).__name__} refund support nahi karta")

# EAFP — duck typing ka asli roop
for p in payments:
    try:
        print(f"EAFP: {p.refund()}")
    except AttributeError:
        print(f"EAFP: {type(p).__name__} refund support nahi karta")

# SUBTLE TRAP: EAFP version me agar refund() KE ANDAR koi aur
# AttributeError aaya, to wo bhi "support nahi karta" me chala jayega —
# bug chhup gaya! Isliye attribute-check jaise NARROW case me
# hasattr/getattr(obj, 'refund', None) zyada precise hota hai.
# EAFP ≠ "har jagah try/except thopo". Exception SPECIFIC rakho, block CHHOTA rakho.


# ============ SECTION 8: BARE except RECAP — KYA SWALLOW HO JATA HAI ============

print("\n=== SECTION 8: bare except trap ===")

# Exception hierarchy (simplified):
#   BaseException
#    ├── SystemExit          ← sys.exit() yahi raise karta hai
#    ├── KeyboardInterrupt   ← Ctrl+C yahi raise karta hai
#    └── Exception           ← saare "normal" errors yahan (ValueError, KeyError...)

def bad_worker():
    try:
        sys.exit(1)              # graceful shutdown ki koshish...
    except:                      # ❌ bare except = except BaseException
        print("bare except ne sys.exit() KHA LIYA — process band hi nahi hua!")

def good_worker():
    try:
        sys.exit(1)
    except Exception:            # ✓ SystemExit/KeyboardInterrupt Exception se
        print("ye print NAHI hoga")  # inherit NAHI karte → pass through

bad_worker()
try:
    good_worker()
except SystemExit:
    print("except Exception ne SystemExit ko jaane diya — sahi behavior")

"""
KYUN MATTER KARTA HAI:
  - while True + bare except wala worker loop = Ctrl+C se band hi nahi hota,
    `kill` karna padta hai. Kubernetes me SIGTERM handling bhi toot jaati hai.
  - RULE: `except Exception` likho jab "sab kuch" pakadna ho (top-level
    handler, request loop), aur log + re-raise/return karo.
    Bare `except:` sirf tab jab turant `raise` kar rahe ho (wo bhi rare).
"""

print("\nDone — 01_assert_eafp_lbyl.py")

"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
INTERVIEW QUESTIONS:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Q1: assert aur raise me kya difference hai? Kab kaunsa?
A:  assert = dev-time internal invariant check; python -O me strip ho jaata hai.
    raise = runtime error handling; hamesha chalta hai.
    User input / API validation / security = HAMESHA raise.
    "Ye condition kabhi false ho hi nahi sakti agar mera code sahi hai" = assert.

Q2: python -O karne se kya hota hai? -OO?
A:  -O → __debug__ = False, saare assert statements bytecode se strip,
        .pyc files alag tag ke saath banti hain (opt-1).
    -OO → -O + docstrings bhi strip (opt-2).
    PYTHONOPTIMIZE env var se bhi same effect — isliye Docker base images
    check karo, kahin ye set to nahi.

Q3: assert (x > 0, "x positive hona chahiye") me kya bug hai?
A:  Ye tuple hai — non-empty tuple HAMESHA truthy — assert kabhi fail
    nahi hoga. Sahi syntax: assert x > 0, "x positive hona chahiye"
    (Python 3.x SyntaxWarning deta hai is mistake pe.)

Q4: EAFP aur LBYL full form aur Python kaunsa prefer karta hai?
A:  EAFP = Easier to Ask Forgiveness than Permission (try/except first).
    LBYL = Look Before You Leap (if-check first).
    Python EAFP prefer karta hai: (1) check+action atomic → no race,
    (2) happy path fast, (3) duck typing ke saath natural fit.

Q5: TOCTOU race condition kya hai? Example do.
A:  Time-Of-Check to Time-Of-Use: os.path.exists(f) True aaya (check),
    par open(f) (use) se pehle file delete/replace ho gayi.
    Fix: EAFP — seedha open() karo aur FileNotFoundError handle karo;
    create ke liye open(f, 'x') jo atomic exclusive-create hai.

Q6: dict.get(key, default) EAFP hai ya LBYL?
A:  Technically dono nahi — ye ek built-in idiom hai jo dono ke
    double-lookup/exception cost se bachata hai. Jab dict pe kaam ho
    to .get()/.setdefault() best; EAFP general pattern hai jo
    files/attributes/network sab pe lagta hai.

Q7: bare except: kyun nahi use karna chahiye?
A:  Ye BaseException pakadta hai — KeyboardInterrupt (Ctrl+C) aur
    SystemExit (sys.exit) bhi swallow ho jaate hain → process unkillable,
    graceful shutdown toot jaata hai. `except Exception:` use karo —
    wo normal errors pakadta hai par interrupt/exit signals jaane deta hai.

Q8: Kya exception handling slow hoti hai Python me?
A:  try block SET KARNA almost free hai (zero-cost jab exception nahi aati,
    Python 3.11+ me literally zero). Exception RAISE + UNWIND hona mehnga
    hai (~10x ek if-check se). Isliye: exception RARE case ke liye,
    expected/frequent case ke liye nahi (wahan LBYL/.get() lo).
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
