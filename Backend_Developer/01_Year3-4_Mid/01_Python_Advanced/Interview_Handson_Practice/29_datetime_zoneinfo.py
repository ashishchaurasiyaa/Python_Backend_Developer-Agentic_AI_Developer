"""
================================================================================
TOPIC: datetime + zoneinfo (UTC discipline) — naive vs aware, ZoneInfo, conversion,
       isoformat round-trip, timedelta, store-in-UTC display-in-local
================================================================================

KYA HOTA HAI:
    datetime ek timestamp hota hai jo do flavours me aata hai: "naive" (jisme
    koi timezone info nahi — bas wall-clock numbers) aur "aware" (jisme tzinfo
    attached hai, yaani ek absolute instant). zoneinfo.ZoneInfo (Python 3.9+,
    stdlib) IANA timezone database se zones load karta hai (e.g. "Asia/Kolkata"),
    jo purane third-party `pytz` ko replace kar deta hai. astimezone() ek aware
    datetime ko ek zone se doosre me convert karta hai — same instant, alag display.

KYO NEED PADI:
    Distributed backend me servers, DBs, users alag-alag timezones me hote hain.
    Agar har jagah naive local time store karein to DST jumps, server move, ya
    cross-region compare pe data corrupt/ambiguous ho jaata hai. UTC ek single
    canonical reference hai. Aur datetime.utcnow() ka classic footgun: wo UTC ka
    *wall clock* deta hai par tzinfo=None (NAIVE) — log dikhta UTC, par object ko
    code local maan baith sakta hai, ya aware se compare pe TypeError de sakta hai.

KAISE USE KARTE HAIN:
    Rule: STORE + COMPUTE in UTC, DISPLAY in local. Aware-now hamesha
    datetime.now(timezone.utc) se lo (utcnow() kabhi nahi — 3.12 me deprecated).
    User ko dikhane ke liye dt.astimezone(ZoneInfo("Asia/Kolkata")). Persist/transport
    ke liye .isoformat() (offset ke saath) aur wapas datetime.fromisoformat().
    Durations ke liye timedelta arithmetic — deadline = created + ttl.

KAHAN USE HOTA HAI (backend scenarios):
    1. Invoice / audit timestamps: created_at, posted_at hamesha UTC aware me store,
       Niroskos tenant ke locale (Asia/Kolkata) me invoice PDF pe render.
    2. TTL / expiry: payment session, OTP, signed URL — expires_at = now_utc + ttl;
       check `now(utc) >= expires_at`. Razorpay/PayU order expiry isi pattern pe.
    3. Celery scheduled job: stored deadline (UTC) vs now(utc) compare karke
       "overdue" invoices/dunning emails trigger — naive/aware mix yahan crash karta.
    4. SAP HANA connector idempotency: har sync attempt ka attempted_at UTC me;
       retry windows aur "last successful sync" comparisons UTC me reliable.
    5. Exotel webhook / dialer events: provider ka ISO timestamp fromisoformat()
       se parse, UTC me normalize, phir reporting ke liye IST me convert.
    6. Cross-region logs: sab UTC me, taaki Mumbai aur Frankfurt ke logs merge ho.

INTERVIEW ANSWER (English — recite this):
    "My core rule is store and compute in UTC, display in local. I represent every
    persisted instant as a timezone-aware datetime in UTC, obtained from
    datetime.now(timezone.utc), and I never use datetime.utcnow(): utcnow() returns
    the UTC wall clock but with tzinfo=None, so it is a naive value that looks like
    UTC but isn't tagged as such, and it was deprecated in Python 3.12 for exactly
    that reason. For timezone data I use the stdlib zoneinfo.ZoneInfo, which reads
    the IANA database and replaces pytz, so converting for display is just
    dt.astimezone(ZoneInfo('Asia/Kolkata')) on the same instant. For persistence and
    transport I round-trip through isoformat and fromisoformat, which preserve the
    offset, and I do all duration math with timedelta. The classic bug I guard
    against is mixing naive and aware datetimes: comparing them raises 'can't compare
    offset-naive and offset-aware datetimes', and comparing two naive datetimes from
    different real zones is silently wrong. The subtle one is storing utcnow() and
    later comparing it to an aware now(timezone.utc) — it throws — or attaching UTC
    to a value that was actually local. The fix is to be aware end to end and only
    drop the tzinfo at the very edge, for a UI string."

================================================================================
Run:
    python 29_datetime_zoneinfo.py          # saare sections chalao
    python 29_datetime_zoneinfo.py 1 4      # sirf section 1 aur 4

Sections:
    1. DEMO  — naive vs aware datetime (kya farq hai, kaise pehchaane)
    2. DEMO  — now(timezone.utc) SAHI vs utcnow() NAIVE footgun (3.12 deprecated)
    3. DEMO  — ZoneInfo + astimezone() UTC<->Asia/Kolkata, isoformat round-trip
    4. REAL  — invoice/audit: store UTC, display IST + timedelta TTL/expiry
    5. REAL  — Celery scheduled job: now(utc) vs stored deadline -> overdue?
    6. BREAK — naive vs aware compare -> TypeError; utcnow() stored as "UTC" bug
    7. TODO  — tum khud likho: make_expiry() + is_expired() fully tz-aware UTC
================================================================================
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")  # IANA zone — pytz ki zaroorat nahi (stdlib)


# === SECTION 1: DEMO — naive vs aware datetime ===
def section1() -> None:
    print("\n=== SECTION 1: naive vs aware datetime ===")

    # NAIVE: sirf wall-clock numbers, koi zone nahi -> tzinfo is None.
    # Ye ek "instant" nahi hai; "kaunse zone me" pata nahi.
    naive = datetime(2026, 6, 18, 12, 0, 0)
    print(f"  naive  = {naive}  | tzinfo={naive.tzinfo}  | aware? {naive.tzinfo is not None}")

    # AWARE: tzinfo attached -> ek absolute instant ko represent karta hai.
    aware_utc = datetime(2026, 6, 18, 12, 0, 0, tzinfo=timezone.utc)
    print(f"  aware  = {aware_utc}  | tzinfo={aware_utc.tzinfo} | aware? "
          f"{aware_utc.tzinfo is not None}")

    # Pehchaan ka rule: dt.tzinfo is not None  AND  utcoffset() is not None
    def is_aware(dt: datetime) -> bool:
        return dt.tzinfo is not None and dt.utcoffset() is not None

    print(f"  is_aware(naive)     -> {is_aware(naive)}")
    print(f"  is_aware(aware_utc) -> {is_aware(aware_utc)}")
    print("  Lesson: backend me hamesha AWARE store karo. Naive = 'kis zone ka?' "
          "ambiguity = future bug.")


# === SECTION 2: DEMO — now(timezone.utc) SAHI vs utcnow() NAIVE footgun ===
def section2() -> None:
    print("\n=== SECTION 2: now(timezone.utc) SAHI vs utcnow() ka NAIVE footgun ===")

    # SAHI tareeka: aware UTC instant. Isme tzinfo=UTC set hai.
    correct = datetime.now(timezone.utc)
    print(f"  datetime.now(timezone.utc) = {correct}")
    print(f"    tzinfo -> {correct.tzinfo}  | aware? {correct.tzinfo is not None}  (SAHI)")

    # FOOTGUN: utcnow() UTC ka wall-clock to deta hai PAR tzinfo=None (NAIVE!).
    # 3.12 me deprecated. Dikhta UTC jaisa, par tag UTC ka nahi hai.
    legacy = datetime.utcnow()  # noqa: DTZ003  (jaan-boojh ke footgun dikhane ke liye)
    print(f"  datetime.utcnow()          = {legacy}")
    print(f"    tzinfo -> {legacy.tzinfo}  | aware? {legacy.tzinfo is not None}  (FOOTGUN: NAIVE)")

    print("  Dono ka time same dikhta hai, par utcnow() ka object NAIVE hai —")
    print("  isse aware se compare karoge to TypeError, aur log me 'UTC' samajh ke")
    print("  galti se local maan loge. Hamesha now(timezone.utc) use karo.")


# === SECTION 3: DEMO — ZoneInfo + astimezone() + isoformat round-trip ===
def section3() -> None:
    print("\n=== SECTION 3: ZoneInfo astimezone() UTC<->IST + isoformat round-trip ===")

    # Ek fixed instant UTC me (store/compute layer).
    instant_utc = datetime(2026, 6, 18, 6, 30, 0, tzinfo=timezone.utc)
    print(f"  stored (UTC)      : {instant_utc.isoformat()}")

    # astimezone() SAME instant ko IST me dikhata hai (display layer).
    # IST = UTC+05:30, to 06:30 UTC -> 12:00 IST.
    in_ist = instant_utc.astimezone(IST)
    print(f"  display (IST)     : {in_ist.isoformat()}  (same instant, +05:30)")

    # Wapas UTC me — instant nahi badla, sirf representation.
    back_utc = in_ist.astimezone(timezone.utc)
    print(f"  back to UTC       : {back_utc.isoformat()}  | same instant? "
          f"{back_utc == instant_utc}")

    # isoformat() <-> fromisoformat() round-trip — offset preserve hota hai,
    # isliye transport/persist ke liye safe. (3.11+ 'Z' suffix bhi parse karta.)
    s = instant_utc.isoformat()
    parsed = datetime.fromisoformat(s)
    print(f"  isoformat str     : {s!r}")
    print(f"  fromisoformat()   : {parsed.isoformat()}  | round-trip equal? "
          f"{parsed == instant_utc}  | still aware? {parsed.tzinfo is not None}")

    z = "2026-06-18T06:30:00Z"  # 'Z' = Zulu = UTC (common API format)
    print(f"  parse 'Z' suffix  : {datetime.fromisoformat(z).isoformat()}")
    print("  Lesson: aware ISO string offset carry karta -> bina zone bheje "
          "receiver exact instant reconstruct kar leta.")


# === SECTION 4: REAL — invoice/audit: store UTC, display IST + TTL/expiry ===
def section4() -> None:
    print("\n=== SECTION 4: REAL — invoice/audit timestamps + timedelta TTL ===")

    # Niroskos invoice: created_at UTC me store hota hai (canonical).
    created_at = datetime(2026, 6, 18, 5, 0, 0, tzinfo=timezone.utc)

    # TTL arithmetic timedelta se — payment session 15 min valid.
    ttl = timedelta(minutes=15)
    expires_at = created_at + ttl  # aware + timedelta -> aware (instant aage badha)
    print(f"  created_at (UTC)  : {created_at.isoformat()}")
    print(f"  expires_at (UTC)  : {expires_at.isoformat()}  (created + 15min TTL)")

    # DB me ye UTC ISO strings jaate hain (persistence boundary).
    print(f"  -> DB store        : {created_at.isoformat()!r}")

    # Tenant ko invoice IST me dikhao (display boundary, astimezone).
    print(f"  invoice shows (IST): {created_at.astimezone(IST):%Y-%m-%d %H:%M %Z}")
    print(f"  session ends (IST) : {expires_at.astimezone(IST):%Y-%m-%d %H:%M %Z}")

    # "Kitna time bacha" — do aware instants ka difference ek timedelta.
    checkpoint = created_at + timedelta(minutes=10)  # pretend "abhi" 10 min baad
    remaining = expires_at - checkpoint
    print(f"  at +10min, remaining session = {remaining}  "
          f"({int(remaining.total_seconds())}s left)")
    print("  Pattern: STORE+COMPUTE in UTC (created_at, expires_at), DISPLAY in IST.")


# === SECTION 5: REAL — Celery scheduled job: now(utc) vs stored deadline ===
def section5() -> None:
    print("\n=== SECTION 5: REAL — Celery job compares now(UTC) vs stored deadline ===")

    # Celery beat job har X min chalti hai aur 'overdue' invoices dhoondti hai.
    # Har invoice ka deadline DB me aware UTC me stored hai (canonical).
    now_utc = datetime.now(timezone.utc)

    invoices = [
        ("INV-001", now_utc - timedelta(hours=2)),   # deadline beet chuki -> overdue
        ("INV-002", now_utc + timedelta(hours=5)),   # abhi time hai
        ("INV-003", now_utc - timedelta(minutes=1)),  # abhi-abhi miss hui -> overdue
    ]

    print(f"  job tick now (UTC): {now_utc.isoformat(timespec='seconds')}")
    for inv_id, deadline_utc in invoices:
        # SAHI: dono aware UTC -> safe compare, no TypeError.
        overdue = now_utc >= deadline_utc
        late_by = now_utc - deadline_utc if overdue else timedelta(0)
        status = f"OVERDUE by {late_by}" if overdue else "on time"
        # display ke liye IST, decision ke liye UTC
        print(f"  {inv_id}: deadline(IST)={deadline_utc.astimezone(IST):%H:%M:%S} -> {status}")
    print("  Decision UTC me hua (deterministic), tenant ko IST me dikhaya. "
          "Naive/aware mix hota to ye loop crash karta (next section dekho).")


# === SECTION 6: BREAK IT / GOTCHA — naive vs aware compare + utcnow() trap ===
def section6() -> None:
    print("\n=== SECTION 6: BREAK IT — naive vs aware compare + utcnow() stored-as-UTC ===")

    # ---- GOTCHA A: aware (sahi) vs naive (utcnow) compare -> TypeError ----
    deadline_aware = datetime.now(timezone.utc) + timedelta(hours=1)
    now_naive = datetime.utcnow()  # NAIVE! (utcnow footgun)  # noqa: DTZ003
    print("  GALAT: stored deadline aware hai, par 'now' utcnow() (naive) se liya:")
    try:
        _ = now_naive >= deadline_aware  # mixing naive + aware
        print("    (yahan tak nahi aana chahiye)")
    except TypeError as e:
        print(f"    -> TypeError: {e}")
        print("    Reason: offset-naive aur offset-aware datetimes compare nahi hote.")

    # ---- GOTCHA B: utcnow() ko 'UTC instant' maan ke local-attach kar dena ----
    # Dev sochta hai "utcnow() to UTC hai", par tzinfo=None. Agar koi galti se
    # ISKO local zone (IST) maan ke attach kar de, to instant 5.5h shift ho jaata.
    wall = datetime.utcnow()  # ye actually UTC ka wall-clock hai  # noqa: DTZ003
    wrong = wall.replace(tzinfo=IST)   # GALAT: UTC numbers ko IST tag de diya
    right = wall.replace(tzinfo=timezone.utc)  # SAHI: UTC numbers -> UTC tag
    drift = right.astimezone(timezone.utc) - wrong.astimezone(timezone.utc)
    print("  GALAT: utcnow() (UTC numbers) ko replace(tzinfo=IST) se tag kiya:")
    print(f"    mislabel drift = {drift}  (instant 5h30m galat ho gaya!)")

    # ---- GOTCHA C: do naive datetimes alag real-zones ke -> silently galat ----
    # Mumbai office ne local IST naive store kiya, London ne local UK naive store
    # kiya. Compare karoge to numbers compare honge, real instant nahi -> chup-chaap galat.
    mumbai_naive = datetime(2026, 6, 18, 12, 0, 0)  # actually IST
    london_naive = datetime(2026, 6, 18, 12, 0, 0)  # actually BST(UK)
    print("  GALAT: do naive (alag real zones), numbers same -> 'equal' dikhte:")
    print(f"    mumbai_naive == london_naive ? {mumbai_naive == london_naive}  "
          "(par real instants alag hain!)")

    # ---- FIX: end-to-end aware UTC ----
    print("  FIX: end-to-end aware UTC ->")
    now_utc = datetime.now(timezone.utc)             # aware now (utcnow nahi)
    deadline = now_utc + timedelta(hours=1)          # aware arithmetic
    print(f"    now_utc >= deadline ? {now_utc >= deadline}  (compare safe, no TypeError)")
    mumbai = datetime(2026, 6, 18, 12, 0, tzinfo=IST).astimezone(timezone.utc)
    london = datetime(2026, 6, 18, 12, 0, tzinfo=ZoneInfo("Europe/London")).astimezone(timezone.utc)
    print(f"    aware mumbai == london ? {mumbai == london}  (ab sahi: real instants compare)")
    print("  Lesson: NEVER mix naive+aware; NEVER store utcnow() as if UTC-aware. "
          "Aware UTC end to end, tzinfo sirf edge pe drop karo.")


# === SECTION 7: TODO — tum khud likho: make_expiry() + is_expired() ===
def make_expiry(created_at: datetime, ttl: timedelta) -> datetime:
    """
    TODO (tum implement karo):
      Ek payment-session expiry banao, fully tz-aware UTC discipline ke saath.
      - Pehle VALIDATE karo ki `created_at` AWARE hai (tzinfo is not None).
        Agar naive hai to ValueError raise karo — naive ko silently UTC mat
        maan lo (yahi footgun hai jise hum rok rahe hain).
      - created_at ko UTC me normalize karo: created_at.astimezone(timezone.utc).
      - return karo (normalized_utc + ttl)  -> ye aware UTC expiry instant hoga.
      Expected behaviour:
          c = datetime(2026, 6, 18, 5, 0, tzinfo=timezone.utc)
          make_expiry(c, timedelta(minutes=15)).isoformat()  # '2026-06-18T05:15:00+00:00'
          make_expiry(datetime(2026,6,18,5,0), timedelta(minutes=15))  # ValueError (naive)
      Hint: aware check = (dt.tzinfo is not None and dt.utcoffset() is not None).
    """
    raise NotImplementedError(
        "TODO: aware-check karo, UTC me normalize, phir + ttl return karo"
    )


def is_expired(expires_at: datetime, now: datetime | None = None) -> bool:
    """
    TODO (tum implement karo):
      - `now` agar None hai to now = datetime.now(timezone.utc)  (utcnow MAT use karo).
      - VALIDATE: dono expires_at aur now AWARE hone chahiye, warna ValueError.
      - return karo:  now >= expires_at   (dono UTC-aware, to compare safe hai).
      Expected behaviour:
          exp = datetime(2026,6,18,5,15, tzinfo=timezone.utc)
          is_expired(exp, datetime(2026,6,18,5,10, tzinfo=timezone.utc))  # False
          is_expired(exp, datetime(2026,6,18,5,20, tzinfo=timezone.utc))  # True
    """
    raise NotImplementedError(
        "TODO: now default now(timezone.utc), aware-check, phir now >= expires_at"
    )


def section7() -> None:
    print("\n=== SECTION 7: TODO — make_expiry() + is_expired() (tum likho) ===")
    created = datetime(2026, 6, 18, 5, 0, 0, tzinfo=timezone.utc)
    try:
        expiry = make_expiry(created, timedelta(minutes=15))
        before = datetime(2026, 6, 18, 5, 10, 0, tzinfo=timezone.utc)
        after = datetime(2026, 6, 18, 5, 20, 0, tzinfo=timezone.utc)
        print(f"  expiry            -> {expiry.isoformat()}  (expected ...05:15:00+00:00)")
        print(f"  is_expired @05:10 -> {is_expired(expiry, before)}  (expected False)")
        print(f"  is_expired @05:20 -> {is_expired(expiry, after)}  (expected True)")
        # naive input ko reject karna chahiye
        try:
            make_expiry(datetime(2026, 6, 18, 5, 0, 0), timedelta(minutes=15))
            print("  naive input       -> koi error nahi (GALAT: naive reject hona chahiye)")
        except ValueError:
            print("  naive input       -> ValueError (sahi: naive ko reject kiya)")
        ok = (
            expiry.isoformat() == "2026-06-18T05:15:00+00:00"
            and is_expired(expiry, before) is False
            and is_expired(expiry, after) is True
        )
        print("  correct! UTC-aware TTL discipline kaam kar rahi." if ok
              else "  output galat hai — aware-check / UTC normalize / compare dobara dekho.")
    except NotImplementedError as e:
        print(f"  abhi tak unimplemented (TODO complete karo): {e}")


# === MAIN DISPATCHER ===
def main() -> None:
    sections = {
        "1": section1,
        "2": section2,
        "3": section3,
        "4": section4,
        "5": section5,
        "6": section6,
        "7": section7,
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
