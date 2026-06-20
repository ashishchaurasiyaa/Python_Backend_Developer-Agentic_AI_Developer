"""
================================================================================
TOPIC: Structural Pattern Matching (match/case) — PEP 634, Python 3.10+
================================================================================

KYA HOTA HAI:
    match/case ek SWITCH nahi hai — ye STRUCTURAL DESTRUCTURING hai. Subject ke
    SHAPE pe match hota hai: dict ke keys, list ka structure, ya class ke attrs.
    Match ke saath-saath wo pieces ko variables me BIND (capture) bhi kar deta —
    ek hi line me "ye shape hai kya?" + "uske andar ke values nikaal do". Pehla
    matching case jeetta hai (top-to-bottom), aur `_` wildcard sabkuch match karta.

KYO NEED PADI:
    Heterogeneous JSON (webhook/event payloads, command dispatch) ko handle karne
    me if/elif ka ek ganda jungle ban jaata: type check + key existence check +
    nested indexing + var assignment — sab manually. match/case ye sab ek readable
    declarative block me samet leta, aur galat shape pe gracefully `_` me gir jaata.

KAISE USE KARTE HAIN:
    `match subject:` ke neeche `case <pattern>:`. Patterns: mapping {"k": var},
    sequence [a, *rest], class Point(x=0, y=y), OR pattern a | b, aur `if` guard
    extra condition ke liye. Niche bare naam = CAPTURE (bind hota), Dotted naam
    (status.OK) ya literal (200) = VALUE/LITERAL match (compare hota, bind nahi).

KAHAN USE HOTA HAI (backend scenarios):
    1. MCP tool dispatch: incoming JSON-RPC request ko {"method": m, "params": p}
       pe match karke sahi handler route karna.
    2. Stripe/Razorpay webhook: {"type": "payment.succeeded", "data": {...}} ke
       event type pe branch — har event ka payload alag shape ka hota.
    3. SAP HANA sync result: ok / retryable-error / fatal-error responses ko shape
       se classify karke retry-with-backoff ya dead-letter decide karna.
    4. CLI / Celery command parsing: ["sync", tenant, *flags] jaise argv ko
       destructure karke command + args alag karna.
    5. Multi-tenant config normalize: purana aur naya config schema dono ko ek hi
       match block me handle karna (backward-compatible migration).

INTERVIEW ANSWER (English — recite this):
    "Structural pattern matching is destructuring, not a C-style switch — each case
    tests the shape of the subject and binds the matching pieces to names in one
    step. I use mapping patterns to pull fields out of heterogeneous JSON like
    webhook or JSON-RPC payloads, sequence patterns with a star to split a head
    from a tail, and class patterns with __match_args__ to match positionally on my
    own types. The single most important nuance is capture versus value: a bare
    name in a case is always a capture that binds and matches anything, whereas a
    literal or a dotted name like Status.OK is compared by value. That trips people
    up because writing `case OK:` does not test against a constant — it shadows it
    and matches everything, so I always use a dotted name, an enum, or a literal for
    constants. Cases are tried top to bottom and the first match wins, guards with
    `if` add runtime conditions the pattern alone cannot express, OR patterns let
    one case cover alternatives, and a trailing `case _` is the wildcard default.
    In production I reach for it most when routing events — it keeps a dispatcher
    declarative and far more readable than a nested if/elif tree."

================================================================================
Run:
    python 26_pattern_matching.py          # saare sections chalao
    python 26_pattern_matching.py 1 4      # sirf section 1 aur 4

Sections:
    1. DEMO  — mapping + sequence patterns (destructuring, not switch)
    2. DEMO  — class pattern + __match_args__, OR pattern, guard if, wildcard _
    3. REAL  — webhook/JSON-RPC event dispatch (Stripe + MCP tool routing)
    4. REAL  — SAP HANA sync result -> retry / dead-letter classification
    5. BREAK — capture vs value: `case OK:` binds & matches EVERYTHING (galti+fix)
    6. TODO  — tum khud likho: parse Celery command argv via match/case
================================================================================
"""
from __future__ import annotations

import sys
from dataclasses import dataclass
from enum import Enum
from typing import Any


# === SECTION 1: DEMO — mapping + sequence patterns (destructuring, NOT switch) ===
def describe_payload(event: dict[str, Any]) -> str:
    """Mapping pattern {"type": ..., "x": x} sirf check karta hai ki ye keys
    HAIN kya, aur unke values ko bind kar deta. Extra keys allowed hain (mapping
    pattern partial match karta — poora dict match karna zaroori nahi)."""
    match event:
        # mapping pattern: "kind" key honi chahiye value "point", aur x/y bind ho
        case {"kind": "point", "x": x, "y": y}:
            return f"point at ({x}, {y})"
        # value bind + nested: "user" key ke andar "id" nikaalo
        case {"kind": "user", "id": uid}:
            return f"user id={uid}"
        case _:
            return "unknown payload shape"


def split_sequence(items: list[Any]) -> str:
    """Sequence pattern [first, *rest]: list ka HEAD alag, baaki *rest me capture.
    Note: ye str pe match NAHI karta (str ko sequence-pattern jaanbujh ke skip
    karta — warna har char match ho jaata). Tuple/list dono chalte hain."""
    match items:
        case []:
            return "empty"
        case [only]:
            return f"single: {only}"
        case [first, *rest]:
            return f"head={first!r}, tail={rest!r} (len rest={len(rest)})"
        case _:
            return "not a sequence"


def section1() -> None:
    print("\n=== SECTION 1: mapping + sequence patterns (destructuring) ===")
    print("  mapping pattern (keys check + value bind, extra keys OK):")
    for ev in (
        {"kind": "point", "x": 3, "y": 7, "extra": "ignored"},
        {"kind": "user", "id": 42},
        {"kind": "ufo"},
    ):
        print(f"    {ev!r:50} -> {describe_payload(ev)}")

    print("  sequence pattern [first, *rest]:")
    for seq in ([], ["a"], ["sync", "acme", "--force", "--dry-run"]):
        print(f"    {seq!r:40} -> {split_sequence(seq)}")


# === SECTION 2: DEMO — class pattern + __match_args__, OR, guard, wildcard ===
class Point:
    """Plain class. __match_args__ batata hai positional class-pattern me kaunsa
    arg kis attr pe map hota. Iske bina `case Point(0, 0)` TypeError dega
    (positional sub-patterns allowed nahi without __match_args__)."""

    __match_args__ = ("x", "y")

    def __init__(self, x: int, y: int) -> None:
        self.x = x
        self.y = y


@dataclass
class Circle:
    """@dataclass automatically __match_args__ set kar deta (field order me).
    Isliye dataclasses pattern matching ke saath sabse smooth chalte hain."""

    radius: float


def classify_shape(shape: object) -> str:
    match shape:
        # class pattern: Point(x=0, y=0) -> literal sub-pattern (VALUE match)
        case Point(x=0, y=0):
            return "origin"
        # positional via __match_args__: pehla arg x, dusra y; y ko capture karo
        case Point(0, y):
            return f"on Y-axis at y={y}"
        # bare 'x','y' capture hote (kuch bhi match), guard se extra condition
        case Point(x=x, y=y) if x == y:
            return f"on diagonal at ({x},{y})"
        case Point(x=x, y=y):
            return f"generic point ({x},{y})"
        # OR pattern: dono alternatives ko SAME naam bind karna zaroori hai —
        # yahan dono `r` bind karte (alag naam likhoge to SyntaxError aata).
        case Circle(radius=0 as r) | Circle(radius=r) if r <= 0:
            return "degenerate circle"
        case Circle(radius=r):
            return f"circle r={r}"
        # wildcard _: kuch bhi, bind nahi karta (sirf catch-all)
        case _:
            return "unknown shape"


def section2() -> None:
    print("\n=== SECTION 2: class pattern + __match_args__, OR, guard, wildcard _ ===")
    for s in (
        Point(0, 0),
        Point(0, 5),
        Point(4, 4),
        Point(2, 9),
        Circle(0),
        Circle(2.5),
        "banana",
    ):
        label = repr(s) if not isinstance(s, str) else repr(s)
        print(f"    {label:24} -> {classify_shape(s)}")
    print("  NOTE: Point(0, y) positional sirf __match_args__=('x','y') ki wajah se chala")


# === SECTION 3: REAL — webhook / JSON-RPC event dispatch (Stripe + MCP) ===
def handle_webhook(event: dict[str, Any]) -> str:
    """Stripe/Razorpay-style webhook router. Har event type ka payload ALAG shape
    ka hota — match/case se shape ke hisaab se destructure + route. if/elif tree
    me ye 'type check + key exists? + nested index' ka jungle ban jaata."""
    match event:
        case {"type": "payment.succeeded", "data": {"id": pid, "amount": amt}}:
            return f"ACK charge {pid} for {amt} (mark order paid, idempotent)"
        case {"type": "payment.failed", "data": {"id": pid, "reason": why}}:
            return f"FAIL {pid}: {why} (notify + schedule retry)"
        # OR pattern: do alag refund event types ek hi handler me
        case {"type": "refund.created" | "refund.updated", "data": {"id": rid}}:
            return f"refund {rid} -> reconcile ledger"
        case {"type": t}:
            return f"unhandled event type {t!r} (log + 200 so Stripe stops retrying)"
        case _:
            return "malformed webhook (no 'type') -> 400"


def dispatch_mcp(request: dict[str, Any]) -> str:
    """MCP / JSON-RPC tool dispatch. {"method": m, "params": {...}} ko match karke
    sahi tool pe route. Guard se params validate bhi kar lete (e.g. limit > 0)."""
    match request:
        case {"method": "tools/call", "params": {"name": name, "arguments": args}}:
            return f"invoke tool {name!r} with {args!r}"
        case {"method": "resources/read", "params": {"uri": uri}} if uri.startswith("file://"):
            return f"read local resource {uri}"
        case {"method": "resources/read", "params": {"uri": uri}}:
            return f"REJECT non-file uri {uri!r} (guard blocked it)"
        case {"method": m}:
            return f"unknown method {m!r} -> JSON-RPC -32601"
        case _:
            return "invalid request -> JSON-RPC -32600"


def section3() -> None:
    print("\n=== SECTION 3: REAL — webhook + MCP/JSON-RPC dispatch ===")
    print("  Stripe-style webhook:")
    for ev in (
        {"type": "payment.succeeded", "data": {"id": "pi_1", "amount": 4999}},
        {"type": "payment.failed", "data": {"id": "pi_2", "reason": "card_declined"}},
        {"type": "refund.updated", "data": {"id": "re_9"}},
        {"type": "invoice.weird", "data": {}},
        {"data": {}},
    ):
        print(f"    -> {handle_webhook(ev)}")

    print("  MCP / JSON-RPC tool dispatch:")
    for req in (
        {"method": "tools/call", "params": {"name": "search", "arguments": {"q": "x"}}},
        {"method": "resources/read", "params": {"uri": "file:///etc/cfg"}},
        {"method": "resources/read", "params": {"uri": "http://evil.com"}},
        {"method": "ping"},
    ):
        print(f"    -> {dispatch_mcp(req)}")


# === SECTION 4: REAL — SAP HANA sync result -> retry / dead-letter ===
class Action(Enum):
    COMMIT = "commit"
    RETRY = "retry"
    DEAD_LETTER = "dead_letter"


def classify_sync_result(result: dict[str, Any]) -> Action:
    """SAP HANA bi-directional connector: har upstream response ko shape se
    classify — transient error -> RETRY (backoff), permanent -> DEAD_LETTER,
    success -> COMMIT. Guard se HTTP-style codes ko range me bucket karte hain."""
    match result:
        case {"status": "ok"}:
            return Action.COMMIT
        # transient: 429 / 5xx -> retry. Guard se code range check.
        case {"status": "error", "code": code} if code == 429 or 500 <= code < 600:
            return Action.RETRY
        # connection-level transient errors (OR pattern over reasons)
        case {"status": "error", "reason": "timeout" | "connection_reset"}:
            return Action.RETRY
        # permanent client errors 4xx (except 429) -> no point retrying
        case {"status": "error", "code": code} if 400 <= code < 500:
            return Action.DEAD_LETTER
        case _:
            # shape hi unknown -> safest: dead-letter for human review
            return Action.DEAD_LETTER


def section4() -> None:
    print("\n=== SECTION 4: REAL — SAP HANA sync result classification ===")
    samples = [
        {"status": "ok", "rows": 12},
        {"status": "error", "code": 503},               # transient -> retry
        {"status": "error", "code": 429},               # rate limit -> retry
        {"status": "error", "reason": "connection_reset"},  # transient -> retry
        {"status": "error", "code": 422},               # bad data -> dead-letter
        {"weird": "shape"},                              # unknown -> dead-letter
    ]
    for r in samples:
        action = classify_sync_result(r)
        print(f"    {r!r:48} -> {action.name}")


# === SECTION 5: BREAK IT / GOTCHA — capture vs value (bare name binds!) ===
OK_STATUS = 200       # module-level constant we WANT to compare against
NOT_FOUND = 404


def route_wrong(status: int) -> str:
    """GALAT: bare name `OK_STATUS` ek CAPTURE pattern hai — ye constant se
    compare NAHI karta. Ye har value ko match karta aur OK_STATUS ko local var
    ki tarah REBIND kar deta (subject ki value usme aa jaati). Isliye 200, 404,
    500 — SAB "ok" branch me chale jaate hain.

    GOTCHA, level 2: agar iske neeche koi bhi aur case (`case NOT_FOUND:` ya
    `case _:`) likho, Python 3.10+ KHUD `SyntaxError: name capture makes
    remaining patterns unreachable` de deta — compiler hi bata deta ki bare
    capture sabkuch kha gaya. Isliye yahan ek hi case hai, aur ye HAR input pe
    match karke OK_STATUS me usi input ko bind kar deta (200 nahi)."""
    match status:
        case OK_STATUS:        # <- BUG: binds anything; OK_STATUS = status ho gaya
            # captured OK_STATUS = subject value, NOT the module constant 200.
            return f"ok (captured OK_STATUS={OK_STATUS})"


class Status(Enum):
    OK = 200
    NOT_FOUND = 404


def route_fixed(status: int) -> str:
    """SAHI: VALUE match ke liye ya to literal (200) likho, ya DOTTED name
    (Status.OK.value) — dotted name ko Python value samajhta hai, capture nahi.
    Enum members khud bhi value-pattern hote, isliye unhe direct match kar sakte."""
    match status:
        case 200:                  # literal -> value compare
            return "ok"
        case Status.NOT_FOUND.value:   # dotted -> value compare (404)
            return "not found"
        case _:
            return "other"


def section5() -> None:
    print("\n=== SECTION 5: BREAK IT — capture vs value (bare name binds everything) ===")
    print("  WRONG (`case OK_STATUS:` is a CAPTURE, not a comparison):")
    for code in (200, 404, 500):
        # 404 aur 500 bhi "ok" aa rahe — aur captured OK_STATUS me wahi code aa gaya
        print(f"    route_wrong({code}) -> {route_wrong(code)!r}")
    print("    -> 404/500 bhi 'ok'?! aur captured OK_STATUS = subject value (200/404/500).")
    print("       bare name HAMESHA match + rebind karta; module constant 200 ignore ho gaya.")

    print("  FIXED (literal 200 + dotted Status.NOT_FOUND.value):")
    for code in (200, 404, 500):
        print(f"    route_fixed({code}) -> {route_fixed(code)!r}")
    print("    -> rule: case me constant chahiye to literal / dotted / Enum use karo,")
    print("       kabhi bare local name nahi (wo capture ban jaata hai).")


# === SECTION 6: TODO — tum khud likho: parse Celery command argv via match/case ===
def parse_command(argv: list[str]) -> dict[str, Any]:
    """
    TODO (tum implement karo) — match/case se Celery/CLI command argv parse karo.

    Input: argv ek list of strings (command + args), jaise:
        ["sync", "acme"]
        ["sync", "acme", "--force"]
        ["retry", "job-42"]
        ["status"]
        []  ya  ["bogus", ...]

    Expected return (dict):
        ["sync", tenant]           -> {"cmd": "sync", "tenant": tenant, "force": False}
        ["sync", tenant, "--force"]-> {"cmd": "sync", "tenant": tenant, "force": True}
        ["retry", job_id]          -> {"cmd": "retry", "job_id": job_id}
        ["status"]                 -> {"cmd": "status"}
        anything else              -> {"cmd": "unknown", "argv": argv}

    Hints:
      - match argv: aur SEQUENCE patterns use karo: case ["sync", tenant]:, etc.
      - "--force" jaisi LITERAL string ko case me direct likho (value match).
      - OR pattern / guard ki yahan zaroorat nahi, sirf sequence shapes chahiye.
      - Last me `case _:` wildcard -> {"cmd": "unknown", "argv": argv}.
    """
    raise NotImplementedError("TODO: parse_command ko match/case se implement karo")


def section6() -> None:
    print("\n=== SECTION 6: TODO — parse Celery command argv via match/case (tum likho) ===")
    cases = [
        ["sync", "acme"],
        ["sync", "globex", "--force"],
        ["retry", "job-42"],
        ["status"],
        ["bogus", "x", "y"],
        [],
    ]
    for argv in cases:
        try:
            print(f"    {argv!r:34} -> {parse_command(argv)!r}")
        except NotImplementedError as e:
            print(f"    abhi unimplemented (TODO complete karo): {e}")
            break


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
    main()
