"""
================================================================================
TOPIC: Type Hints + Runtime Introspection (how FastAPI/Pydantic actually work)
================================================================================

KYA HOTA HAI:
  Type hints sirf "documentation" nahi hote — Python inhe runtime pe object ke
  taur pe store karta hai (func.__annotations__). Introspection ka matlab:
  signature aur annotations ko PROGRAM se padho — get_type_hints / get_origin /
  get_args / inspect.signature — aur uske basis pe decision lo (coerce, validate,
  route). Yahi FastAPI/Pydantic ka asli engine hai: woh tumhari hint padh ke
  request ko us type me convert + validate karte hain.

KYO NEED PADI:
  Bina introspection ke har endpoint pe manually int(request["age"]) likhna padta
  hai — boilerplate, bug-prone, aur galti se validation chhoot jati hai.
  Agar framework annotation padh le, to ek hi generic layer raw string ko sahi
  type me coerce + validate kar deta hai, aur tum sirf clean typed function
  likhte ho. Yahi DRY + safety ka combo senior code ko alag banata hai.

KAISE USE KARTE HAIN:
  Likhna: X | Y (union), list[int]/dict[str,int] (generics), Protocol (shape),
  TypeVar (generic fn), Literal["a","b"] (allowed values), Self (chained methods).
  Padhna: inspect.signature(fn) se params nikalo, get_type_hints(fn) se actual
  type objects lo (string-evaluated), get_origin()/get_args() se generic/Annotated
  ko todo, aur Annotated[T, meta] me extra rules (gt=0, max_len) attach karo.

KAHAN USE HOTA HAI (backend scenarios):
  - SAP HANA connector: ek generic "call" wrapper jo param annotations padh ke
    raw config strings ko int/bool me coerce kare (retries="3" -> 3).
  - Niroskos multi-tenant: Literal["active","suspended"] se tenant status validate,
    galat value request-time pe reject ho jaye.
  - Payment idempotency: Annotated[str, MaxLen(64)] se idempotency-key length
    introspection se enforce ho — har handler me dubara check nahi.
  - Celery task: ek decorator jo task ki hints padh ke serialized JSON payload ko
    typed kwargs me coerce kare before run().
  - Mini-router (is file ka core demo): "FastAPI kaise jaanta hai type" — signature
    + annotation introspect karke string query-params ko coerce + validate.

INTERVIEW ANSWER (English):
  In Python, type hints are not erased at runtime — they are stored as objects on
  the function's __annotations__, which is exactly why frameworks like FastAPI and
  Pydantic can read them and do real work. The clean way to read them is
  typing.get_type_hints(), because it resolves string ("from __future__") and
  forward-reference annotations into real type objects, which raw __annotations__
  does not. To inspect a generic like list[int] or a Union you use typing.get_origin()
  to get the container (list, or types.UnionType for X|Y) and typing.get_args()
  to get the parameters. The real backbone is typing.Annotated[T, metadata]: the
  first argument is the actual type used for coercion, and the remaining items are
  arbitrary metadata objects — that is how Pydantic and FastAPI attach validation
  rules (gt, max_length) and dependency markers without changing the runtime type.
  Combine that with inspect.signature() to walk each parameter, and you can build
  exactly what FastAPI does: read the annotation, coerce the incoming string into
  the declared type, and validate the metadata constraints. The senior gotcha is
  that get_type_hints strips Annotated metadata by default — you must pass
  include_extras=True or you silently lose every validation rule.

Run:
  python 27_type_hints_and_runtime_introspection.py          # saare sections
  python 27_type_hints_and_runtime_introspection.py 2 6      # sirf section 2 aur 6

Sections:
  1. DEMO  — Writing hints: X|Y, generics, Literal, Self (chained builder)
  2. DEMO  — Protocol + TypeVar: generic, decoupled, type-safe function
  3. DEMO  — Reading hints at runtime: __annotations__ vs get_type_hints
  4. DEMO  — get_origin / get_args: union aur generic ko program se todna
  5. DEMO  — typing.Annotated: type + metadata (Pydantic/FastAPI backbone)
  6. REAL  — Mini FastAPI router: signature introspect karke string args coerce
  7. BREAK — get_type_hints Annotated metadata DROP kar deta hai (include_extras)
  8. TODO  — tum khud likho: Celery-style typed-kwargs coercer
"""

from __future__ import annotations

import inspect
import sys
from dataclasses import dataclass
from typing import (
    Annotated,
    Literal,
    Protocol,
    Self,
    TypeVar,
    get_args,
    get_origin,
    get_type_hints,
)


# === SECTION 1: DEMO — Writing hints: X|Y, generics, Literal, Self ===
def section_1() -> None:
    print("\n=== SECTION 1: Writing hints (X|Y, generics, Literal, Self) ===")

    # Literal => sirf in exact values me se ek allowed (mypy enforce karta hai).
    Status = Literal["active", "suspended", "deleted"]

    @dataclass
    class QueryBuilder:
        table: str
        filters: dict[str, str]  # generic: dict[key_type, value_type]

        # Self => method chaining; ye QUERYBUILDER ko hardcode karne se behtar hai
        # kyunki subclass me Self automatically subclass type ban jata hai.
        def where(self, col: str, val: str) -> Self:
            self.filters[col] = val
            return self

        def status(self, s: Status) -> Self:
            self.filters["status"] = s
            return self

        # X | Y union => limit int ya None (no Optional import needed in 3.10+).
        def build(self, limit: int | None = None) -> str:
            conds = " AND ".join(f"{k}={v!r}" for k, v in self.filters.items())
            sql = f"SELECT * FROM {self.table} WHERE {conds}"
            return sql + (f" LIMIT {limit}" if limit is not None else "")

    q = QueryBuilder("invoices", {}).where("tenant_id", "7").status("active").build(limit=50)
    print("chained build ->", q)
    print("Self -> har step phir se QueryBuilder return karta hai, isliye chain chalti hai.")


# === SECTION 2: DEMO — Protocol + TypeVar (generic + decoupled) ===
def section_2() -> None:
    print("\n=== SECTION 2: Protocol + TypeVar (generic, decoupled) ===")

    # Protocol: sirf shape; koi inheritance nahi chahiye.
    class HasId(Protocol):
        id: int

    # TypeVar bound=HasId => "koi bhi cheez jisme .id ho" par return type same rahega.
    T = TypeVar("T", bound=HasId)

    def first_by_id(items: list[T], target: int) -> T | None:
        # T preserve hota hai: input Invoice list do to Invoice | None milega (mypy).
        return next((x for x in items if x.id == target), None)

    @dataclass
    class Invoice:
        id: int
        amount: int

    rows = [Invoice(1, 500), Invoice(2, 999)]
    print("first_by_id(rows, 2) ->", first_by_id(rows, 2))
    print("first_by_id(rows, 9) ->", first_by_id(rows, 9))
    print("TypeVar -> generic function, par return type concrete type preserve karta hai.")


# === SECTION 3: DEMO — __annotations__ vs get_type_hints ===
def section_3() -> None:
    print("\n=== SECTION 3: __annotations__ vs get_type_hints ===")

    def handler(tenant_id: int, name: str, active: bool = True) -> dict:
        return {"tenant_id": tenant_id, "name": name, "active": active}

    # 'from __future__ import annotations' ke karan raw __annotations__ STRINGS hote hain.
    raw = handler.__annotations__
    print("raw __annotations__ ->", raw)
    print("type of raw['tenant_id'] ->", type(raw["tenant_id"]).__name__, "(string, not a type!)")

    # get_type_hints inhe ACTUAL type objects me resolve karta hai — yahi use karo.
    resolved = get_type_hints(handler)
    print("get_type_hints ->", resolved)
    print("type of resolved['tenant_id'] ->", resolved["tenant_id"])  # <class 'int'>
    print("Lesson: framework hamesha get_type_hints use karta hai, raw dict pe bharosa nahi.")


# === SECTION 4: DEMO — get_origin / get_args (todo generics & unions) ===
def section_4() -> None:
    print("\n=== SECTION 4: get_origin / get_args (break generics & unions) ===")

    samples = {
        "list[int]": list[int],
        "dict[str, int]": dict[str, int],
        "int | None": int | None,
        "str | int": str | int,
    }
    for label, tp in samples.items():
        origin = get_origin(tp)  # container: list / dict / types.UnionType
        args = get_args(tp)      # parameters: (int,), (str,int), (int,NoneType)...
        print(f"{label:16} origin={origin!s:22} args={args}")

    # Practical use: ye detect karna ki annotation Optional (X | None) hai.
    tp = int | None
    is_optional = get_origin(tp) is not None and type(None) in get_args(tp)
    print("int | None optional hai? ->", is_optional)
    print("Yahi tarika hai jisse coercer container/union ko program se samajhta hai.")


# --- Module-level markers + annotated fns (sec 5/6/7 ke liye) ---
# GOTCHA: 'from __future__ import annotations' ke karan saare hints STRING ban
# jaate hain, aur get_type_hints unhe function ke MODULE globals me evaluate karta
# hai — local (function ke andar) classes resolve NAHI hote. Isliye markers aur
# annotated functions module level pe rakhe hain (jaise real Pydantic models hote hain).
@dataclass(frozen=True)
class Gt:
    value: int


@dataclass(frozen=True)
class MaxLen:
    value: int


@dataclass(frozen=True)
class OneOf:
    values: tuple[str, ...]


# Annotated[ACTUAL_TYPE, marker1, marker2, ...]: pehla arg coercion ke liye type,
# baaki sab validation rules. Runtime type to bas 'int' / 'str' hi rehta hai.
Amount = Annotated[int, Gt(0)]
IdemKey = Annotated[str, MaxLen(64)]


def _charge(amount: Amount, idempotency_key: IdemKey) -> str:
    return f"charged {amount} key={idempotency_key}"


# === SECTION 5: DEMO — typing.Annotated (type + metadata backbone) ===
def section_5() -> None:
    print("\n=== SECTION 5: typing.Annotated (Pydantic/FastAPI backbone) ===")

    charge = _charge
    # include_extras=True => metadata bhi milta hai (default me drop ho jata, sec 7 dekho).
    hints = get_type_hints(charge, include_extras=True)
    for name, tp in hints.items():
        if name == "return":
            continue
        actual = get_args(tp)[0]        # asli type (int/str) coercion ke liye
        markers = get_args(tp)[1:]      # validation rules
        print(f"{name:16} actual={actual.__name__:4} markers={markers}")

    print("charge(500, 'k1') ->", charge(500, "k1"))
    print("Annotated -> ek hint me TYPE + RULES dono; isi pe Pydantic khada hai.")


# Clean typed handler (module level taki get_type_hints string hints resolve kar sake) —
# coercion/validation framework karta hai, hum sirf typed function likhte hain.
def list_invoices(
    tenant_id: Annotated[int, Gt(0)],
    status: Annotated[str, OneOf(("active", "suspended"))],
    limit: int = 20,
    include_paid: bool = False,
) -> dict:
    return {
        "tenant_id": tenant_id,
        "status": status,
        "limit": limit,
        "include_paid": include_paid,
    }


# === SECTION 6: REAL — Mini FastAPI router (how FastAPI knows the types) ===
def section_6() -> None:
    print("\n=== SECTION 6: REAL — mini router coerces string args via introspection ===")

    def coerce(raw: str, target: type) -> object:
        # HTTP me sab kuch string aata hai; declared type me convert karte hain.
        if target is bool:
            return raw.lower() in {"1", "true", "yes", "on"}
        if target is int:
            return int(raw)
        if target is str:
            return raw
        raise TypeError(f"unsupported target type: {target}")

    def call_endpoint(fn, query: dict[str, str]):
        """FastAPI ka chhota dimaag: signature + annotations padho, coerce + validate karo."""
        sig = inspect.signature(fn)
        hints = get_type_hints(fn, include_extras=True)
        kwargs: dict[str, object] = {}
        for pname, param in sig.parameters.items():
            ann = hints.get(pname, str)
            # Annotated ko todo: actual type + markers alag karo.
            if get_origin(ann) is Annotated:
                actual, *markers = get_args(ann)
            else:
                actual, markers = ann, []
            # Query me value nahi -> default lo (FastAPI bhi yahi karta hai).
            if pname not in query:
                if param.default is inspect.Parameter.empty:
                    raise ValueError(f"missing required query param: {pname!r}")
                kwargs[pname] = param.default
                continue
            value = coerce(query[pname], actual)
            # Metadata rules enforce karo — yahi validation layer hai.
            for m in markers:
                if isinstance(m, Gt) and not (value > m.value):
                    raise ValueError(f"{pname}={value} must be > {m.value}")
                if isinstance(m, OneOf) and value not in m.values:
                    raise ValueError(f"{pname}={value!r} must be one of {m.values}")
            kwargs[pname] = value
        return fn(**kwargs)

    # Raw "HTTP" query (sab string) — exactly jaisa request me aata.
    ok = call_endpoint(
        list_invoices,
        {"tenant_id": "7", "status": "active", "limit": "50", "include_paid": "true"},
    )
    print("coerced+validated ->", ok)
    print("note: limit '50' -> 50 (int), include_paid 'true' -> True (bool).")

    # Validation fail demo: status galat -> framework reject kare.
    try:
        call_endpoint(list_invoices, {"tenant_id": "7", "status": "deleted"})
    except ValueError as e:
        print("rejected bad status ->", type(e).__name__, ":", e)

    # Missing required param demo.
    try:
        call_endpoint(list_invoices, {"status": "active"})
    except ValueError as e:
        print("rejected missing param ->", type(e).__name__, ":", e)
    print('Yahi answer hai "FastAPI ko type kaise pata?" -> signature + get_type_hints.')


def _transfer(amount: Annotated[int, Gt(0)]) -> str:
    return f"transfer {amount}"


# === SECTION 7: BREAK IT / GOTCHA — get_type_hints DROPS Annotated metadata ===
def section_7() -> None:
    print("\n=== SECTION 7: BREAK IT — get_type_hints drops Annotated metadata ===")

    transfer = _transfer
    # GALTI: default get_type_hints (include_extras MISSING). Validation rules gayab.
    wrong = get_type_hints(transfer)
    print("WRONG  get_type_hints(transfer) ->", wrong)
    print("WRONG  amount hint ->", wrong["amount"], "(<class 'int'> — Gt(0) GONE!)")
    # Iska seedha asar: coercer ke paas koi rule nahi -> -100 bhi 'valid' nikal jayega.
    bad_markers = get_args(wrong["amount"])  # () -> kuch validate hi nahi hoga
    print("WRONG  markers extracted ->", bad_markers, "(empty -> -100 bhi paas ho jata)")

    # FIX: include_extras=True. Tabhi Annotated metadata survive karta hai.
    right = get_type_hints(transfer, include_extras=True)
    actual, *markers = get_args(right["amount"])
    print("FIX    get_type_hints(..., include_extras=True) ->", right)
    print("FIX    actual ->", actual.__name__, " markers ->", markers, "(Gt(0) zinda!)")
    print("Lesson: framework me hamesha include_extras=True; warna validation chupchaap mar jata hai.")


# === SECTION 8: TODO (tum khud likho) — Celery-style typed-kwargs coercer ===
def section_8() -> None:
    print("\n=== SECTION 8: TODO — typed-kwargs coercer for a Celery task (tum likho) ===")

    # GOAL (Celery/Redis pipeline jaisa):
    #   Celery payload JSON se aata hai -> sab values string/loose hoti hain.
    #   1. Function 'coerce_task_kwargs(fn, payload: dict[str, str]) -> dict' banao.
    #   2. inspect.signature(fn) + get_type_hints(fn) use karke har param ke liye:
    #        - int hint  -> int(value)
    #        - bool hint -> value.lower() in {"1","true","yes"}
    #        - str hint  -> value as-is
    #      coerce karke ek kwargs dict return karo.
    #   3. Missing param -> agar default hai to default use karo, warna KeyError raise.
    #   Expected (example task below):
    #     coerce_task_kwargs(sync_tenant, {"tenant_id": "7", "force": "true"})
    #       -> {"tenant_id": 7, "force": True, "batch_size": 100}   # batch_size default

    def sync_tenant(tenant_id: int, force: bool = False, batch_size: int = 100) -> dict:
        return {"tenant_id": tenant_id, "force": force, "batch_size": batch_size}

    def coerce_task_kwargs(fn, payload: dict[str, str]) -> dict:
        raise NotImplementedError("TODO: signature + get_type_hints se kwargs coerce karo")

    try:
        coerce_task_kwargs(sync_tenant, {"tenant_id": "7", "force": "true"})
    except NotImplementedError as e:
        print("TODO pending ->", e)


# === MAIN DISPATCHER ===
_SECTIONS = {
    1: section_1,
    2: section_2,
    3: section_3,
    4: section_4,
    5: section_5,
    6: section_6,
    7: section_7,
    8: section_8,
}


def main(argv: list[str]) -> None:
    args = argv[1:]
    if not args:
        to_run = sorted(_SECTIONS)
    else:
        to_run = []
        for a in args:
            if not a.isdigit() or int(a) not in _SECTIONS:
                print(f"skip invalid section: {a!r} (valid: {sorted(_SECTIONS)})")
                continue
            to_run.append(int(a))
    for num in to_run:
        _SECTIONS[num]()


if __name__ == "__main__":
    main(sys.argv)
