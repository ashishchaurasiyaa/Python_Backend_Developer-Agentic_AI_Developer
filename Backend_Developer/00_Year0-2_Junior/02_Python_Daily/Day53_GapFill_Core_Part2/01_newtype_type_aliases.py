"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
DAY 53 — GAP FILL CORE PART 2
FILE 1: typing.NewType + Type Aliases (DEEP DIVE)
Architecture Level: Senior Python Backend + Agentic AI
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

THEORY (Hinglish):
  Problem statement: backend me sab IDs `int` hote hain — user_id, order_id,
  product_id. Type checker ke liye sab same hai, isliye galat ID pass kar do
  toh mypy chup rehta hai. Yeh bug production me hi pakda jaata hai
  (galat user ka order delete ho gaya — classic incident).

  Solution: typing.NewType — mypy ke liye DISTINCT type banata hai,
  but runtime pe ZERO cost (basically identity function hai).

  UserId = NewType("UserId", int)
  → mypy ke liye: UserId aur int alag types hain (UserId → int allowed,
    int → UserId NOT allowed without explicit wrap)
  → runtime pe: UserId(5) bas 5 return karta hai. No new class, no object,
    no isinstance support. FREE abstraction.

  3 options jab "int ko meaningful type" banana ho:
  ┌──────────────┬─────────────────┬───────────────┬──────────────────┐
  │              │ Type Alias      │ NewType       │ Subclass         │
  ├──────────────┼─────────────────┼───────────────┼──────────────────┤
  │ Syntax       │ UserId = int    │ NewType(...)  │ class UserId(int)│
  │ mypy distinct│ NO (same as int)│ YES           │ YES              │
  │ Runtime cost │ zero            │ zero (~)      │ object creation  │
  │ isinstance() │ N/A (it IS int) │ NOT allowed   │ works            │
  │ Methods add  │ no              │ no            │ yes (can add)    │
  │ Use case     │ readability     │ ID safety     │ behavior change  │
  └──────────────┴─────────────────┴───────────────┴──────────────────┘

  Rule of thumb (senior answer):
  - Sirf readability chahiye (complex generic short karna) → type alias
  - mypy se ID-mixing bugs pakadne hain, runtime cost nahi chahiye → NewType
  - Actual naya behavior/methods chahiye → subclass (but cost hai)
"""

import sys
import timeit
from typing import NewType, TypeAlias

print(f"Python: {sys.version_info.major}.{sys.version_info.minor}")


# ============ SECTION 1: TYPE ALIAS RECAP — 3 SYNTAXES ============
# Type alias = bas ek NAYA NAAM, type checker ke liye 100% interchangeable.

# (a) Implicit alias — purana style, har version me chalta hai
ConnectionOptions = dict[str, str]
Vector = list[float]

# (b) Explicit TypeAlias annotation (3.10+) — mypy ko clearly batata hai
#     ki yeh alias hai, normal assignment nahi. Forward-ref strings allowed.
Matrix: TypeAlias = list[list[float]]

# (c) Python 3.12+ ka `type` statement — LAZY evaluated, scoped, cleanest:
#         type IntList = list[int]
#         type Tree = dict[str, "Tree"]   # forward ref bina string-quotes issue ke
#     NOTE: yeh syntax 3.11 ya neeche SyntaxError dega, isliye yahan
#     comment me rakha hai (file har version pe runnable rahe).

# ┌─────────────────────────────┬─────────────┬────────────────────────────┐
# │ Syntax                      │ Min version │ Note                       │
# ├─────────────────────────────┼─────────────┼────────────────────────────┤
# │ X = list[int]   (implicit)  │ 3.9         │ mypy guess karta hai       │
# │ X: TypeAlias = list[int]    │ 3.10        │ explicit, recommended 3.10 │
# │ type X = list[int]          │ 3.12        │ lazy eval, best forward ref│
# └─────────────────────────────┴─────────────┴────────────────────────────┘

def scale(v: Vector, factor: float) -> Vector:
    return [x * factor for x in v]

# TRAP: alias INTERCHANGEABLE hota hai — yeh mypy ke liye bilkul valid hai:
plain_list: list[float] = [1.0, 2.0]
result: Vector = scale(plain_list, 2.0)   # alias != safety, sirf readability
print("Section 1 — scaled vector:", result)


# ============ SECTION 2: NewType BASICS — DISTINCT TYPE, ZERO COST ============

UserId = NewType("UserId", int)
OrderId = NewType("OrderId", int)

uid = UserId(42)        # runtime pe: bas 42 hai
oid = OrderId(42)       # runtime pe: bas 42 hai

print("\nSection 2 — runtime reality check:")
print("  UserId(42) ==", uid, "| type:", type(uid))   # type: <class 'int'>!
print("  uid == oid ?", uid == oid)                    # True — runtime me same int

# Yeh proof hai ki NewType ~identity function hai — SAME object wapas milta hai:
forty_two = 42
print("  UserId(x) is x ?", UserId(forty_two) is forty_two)  # True — no new object!

# TRAP 1: isinstance(uid, UserId) — TypeError! NewType class nahi hai.
try:
    isinstance(uid, UserId)  # type: ignore[arg-type]
except TypeError as e:
    print("  isinstance trap:", e)

# TRAP 2: NewType ko subclass nahi kar sakte:
#   class AdminId(UserId): ...   → TypeError at runtime, mypy bhi error dega
# Chain banana ho toh: AdminId = NewType("AdminId", UserId)  ← yeh allowed hai
AdminId = NewType("AdminId", UserId)
admin = AdminId(UserId(1))
print("  Chained NewType — AdminId:", admin)


# ============ SECTION 3: THE MIXING-IDS BUG — JO NewType PAKADTA HAI ============
# Real incident pattern: do functions, dono int lete hain, order ulta ho gaya.

def get_order_for_user_UNSAFE(user_id: int, order_id: int) -> str:
    """Plain ints — mypy KUCH NAHI bolega agar arguments swap ho jaayein."""
    return f"order#{order_id} of user#{user_id}"


def get_order_for_user_SAFE(user_id: UserId, order_id: OrderId) -> str:
    """NewType — swap karo toh mypy turant error dega."""
    return f"order#{order_id} of user#{user_id}"


u, o = 7, 1001  # imagine yeh DB se aaye

# BUG: arguments swapped — runtime pe chalta hai, output GALAT hai:
print("\nSection 3 — the bug mypy can't see with plain ints:")
print("  UNSAFE swapped:", get_order_for_user_UNSAFE(o, u))  # silently wrong!

# Ab NewType version:
safe_u = UserId(7)
safe_o = OrderId(1001)
print("  SAFE correct:  ", get_order_for_user_SAFE(safe_u, safe_o))

# get_order_for_user_SAFE(safe_o, safe_u)
#   ^ mypy ERROR: Argument 1 has incompatible type "OrderId"; expected "UserId"
#   Runtime pe yeh chal jaayega (dono int hain) — isliye CI me mypy zaroori hai.

# One-way street rule (interview favorite):
#   UserId → int   : ALLOWED  (UserId "is-a" int for reading)
#   int → UserId   : NOT allowed implicitly — explicitly UserId(x) wrap karo
def double(x: int) -> int:
    return x * 2

print("  UserId passed where int expected (OK):", double(safe_u))
# Lekin: y: UserId = double(safe_u)  → mypy ERROR (int → UserId nahi hota)
# Kyun? double() ka result ab "validated user id" nahi raha — semantics gone.


# ============ SECTION 4: 3-WAY COMPARISON — ALIAS vs NewType vs SUBCLASS ============

# Option A: alias — no safety
UserIdAlias = int

# Option B: NewType — mypy safety, zero runtime cost
UserIdNT = NewType("UserIdNT", int)

# Option C: subclass — runtime distinct type, but object creation cost
class UserIdSub(int):
    """Real class — isinstance works, methods add kar sakte ho,
    but har creation pe naya int object banta hai + sab int ops
    wapas plain int return karte hain (UserIdSub + 1 → int, type lost!)."""
    def masked(self) -> str:
        return f"user_***{int(self) % 1000}"


sub = UserIdSub(98765)
print("\nSection 4 — subclass extras:")
print("  isinstance(sub, UserIdSub):", isinstance(sub, UserIdSub))  # True
print("  custom method:", sub.masked())
print("  TRAP — sub + 1 type:", type(sub + 1).__name__)  # 'int' — type LOST on ops!

# Runtime cost benchmark — NewType vs subclass creation:
t_newtype = timeit.timeit(lambda: UserIdNT(12345), number=1_000_000)
t_subclass = timeit.timeit(lambda: UserIdSub(12345), number=1_000_000)
print(f"  1M creations — NewType: {t_newtype:.3f}s | subclass: {t_subclass:.3f}s")
# NewType ~identity-call cost; subclass me int.__new__ + class machinery lagti hai.


# ============ SECTION 5: PRACTICAL — DOMAIN MODELING IN A BACKEND ============
# E-commerce service: customers, orders, money. Money wala part sabse
# dangerous hai — paise (int) vs rupees (float) mixing = real financial bug.

CustomerId = NewType("CustomerId", int)
ProdOrderId = NewType("ProdOrderId", int)
Paise = NewType("Paise", int)      # money ALWAYS integer paise me store karo
# (float rupees me 0.1 + 0.2 != 0.3 wali problem hai — Day42 datetime/decimal recap)

_ORDERS: dict[ProdOrderId, dict] = {}
_next_order_id = 0


def rupees_to_paise(rupees: float) -> Paise:
    """Boundary function — yahi EK jagah hai jahan float → Paise conversion hota hai.
    round() zaroori hai: 199.99 * 100 = 19998.999999999996 in float!"""
    return Paise(round(rupees * 100))


def create_order(customer: CustomerId, amount: Paise) -> ProdOrderId:
    global _next_order_id
    _next_order_id += 1
    order_id = ProdOrderId(_next_order_id)
    _ORDERS[order_id] = {"customer": customer, "amount_paise": amount}
    return order_id


def format_amount(amount: Paise) -> str:
    return f"₹{amount // 100}.{amount % 100:02d}"


print("\nSection 5 — domain modeling demo:")
cust = CustomerId(501)
amt = rupees_to_paise(199.99)
oid2 = create_order(cust, amt)
print(f"  Order {oid2} for customer {cust}: {format_amount(amt)}")

# Yeh sab ab mypy errors hain (runtime pe chalenge, isliye CI gate chahiye):
#   create_order(oid2, amt)            # OrderId passed as CustomerId
#   create_order(cust, 19999)          # raw int passed as Paise — conversion skip!
#   format_amount(199.99)              # float rupees passed as Paise
#
# Pattern ka naam: "Parse, don't validate" — boundary pe ek baar wrap karo
# (DB read, API input), uske baad pura codebase typed IDs me baat karta hai.

# Agentic AI me same pattern:
PromptTokens = NewType("PromptTokens", int)
CompletionTokens = NewType("CompletionTokens", int)

def billing_cost(prompt: PromptTokens, completion: CompletionTokens) -> Paise:
    # input/output token rates alag hote hain — swap hua toh billing galat!
    return Paise(prompt * 1 + completion * 3)

print("  LLM billing:", format_amount(
    billing_cost(PromptTokens(1000), CompletionTokens(500))))


# ============ SECTION 6: WHEN NOT TO USE NewType ============
# 1. Validation chahiye toh NewType KAAFI NAHI — UserId(-5) chal jaayega.
#    Validation ke liye: Pydantic / dataclass with __post_init__.
print("\nSection 6 — NewType does NOT validate:")
print("  UserId(-5) =", UserId(-5), "← koi error nahi, sirf static label hai")

# 2. Runtime dispatch chahiye (isinstance branching) → subclass lo.
# 3. Team me mypy/pyright CI me nahi chalta → NewType bekar hai,
#    kyunki saari safety STATIC hai, runtime pe kuch enforce nahi hota.

print("\nDone — run `mypy 01_newtype_type_aliases.py` to see static errors "
      "by uncommenting the trap lines.")


# ============ INTERVIEW QUESTIONS ============
"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
INTERVIEW Q&A:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Q1: NewType aur type alias me kya difference hai?
A:  Type alias sirf naya NAAM hai — mypy ke liye `Vector = list[float]`
    aur `list[float]` 100% interchangeable hain. NewType ek DISTINCT
    static type banata hai: `UserId` jahan expected hai wahan plain `int`
    pass karoge toh mypy error. Runtime pe dono ka cost ~zero hai.

Q2: NewType runtime pe kya hota hai?
A:  Essentially identity function/callable — UserId(5) bas 5 return karta
    hai. Koi naya object nahi banta (3.10+ me yeh optimized class hai,
    but behavior identity hi hai). type(UserId(5)) == int. Isliye
    isinstance(x, UserId) TypeError deta hai — class hai hi nahi
    isinstance ke matlab me.

Q3: int subclass vs NewType — kab kya?
A:  Subclass: jab runtime behavior chahiye (custom methods, isinstance
    checks, repr). Cost: har creation pe object banta hai, aur arithmetic
    ops type lose kar dete hain (UserIdSub + 1 → plain int).
    NewType: jab sirf static safety chahiye, zero cost me. 95% backend
    ID cases me NewType hi sahi answer hai.

Q4: `UserId → int` allowed but `int → UserId` not — kyun one-way?
A:  UserId conceptually "int + extra guarantee (yeh validated user id hai)"
    hai. Guarantee wali cheez ko general jagah dena safe hai (upcast).
    Ulta direction me guarantee kahan se aayi? Isliye explicit UserId(x)
    wrap karna padta hai — "main jaanta hoon yeh user id hai" assertion.

Q5: Python 3.12 ka `type X = ...` statement implicit alias se better kyun?
A:  (1) LAZY evaluation — RHS turant evaluate nahi hota, isliye forward
    references bina string quotes ke chalte hain (type Tree = dict[str, Tree]).
    (2) Explicitly alias declare hota hai — mypy ko guess nahi karna padta
    ki yeh alias hai ya normal variable. (3) TypeAliasType object banta hai
    jiska apna __name__ hota hai — better error messages.

Q6: NewType validation karta hai kya? UserId(-5) pe error aayega?
A:  NAHI. NewType pure static-level label hai — runtime pe koi check nahi.
    Validation chahiye toh Pydantic model / Annotated + Field /
    dataclass __post_init__ use karo. Common misconception hai yeh.

Q7: Money ko Paise (int NewType) me kyun store karte hain, float rupees kyun nahi?
A:  Float binary representation me 0.1 exactly store nahi hota —
    199.99 * 100 = 19998.999999999996. Crores transactions me paise leak
    ho jaate hain. Int paise exact hai. NewType upar se yeh guarantee
    deta hai ki koi raw int/float galti se amount ki jagah na ghus jaaye.
    Alternative: decimal.Decimal (jab fractional paise/interest chahiye).

Q8: NewType ki safety production me enforce kaise hoti hai?
A:  CI pipeline me mypy/pyright gate — kyunki runtime pe NewType kuch
    enforce nahi karta. Bina static checker ke NewType sirf documentation
    hai. Senior answer: "NewType + mypy --strict in CI, warnings as errors."
"""
