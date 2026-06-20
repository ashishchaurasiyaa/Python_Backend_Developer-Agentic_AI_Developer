"""
================================================================================
TOPIC: Logging (production-grade) — hierarchy/propagation, dictConfig, structured
       JSON logs, QueueHandler/Listener, library NullHandler, correlation-id Filter
================================================================================

KYA HOTA HAI:
    Python ka logging ek HIERARCHY hai — "a.b.c" logger ka parent "a.b", uska "a",
    aur sabse upar root. Default me child ka record propagate hoke parent ke
    handlers tak jaata hai. Levels (DEBUG<INFO<WARNING<ERROR<CRITICAL) filter
    karte hain; Handlers (Stream/File/Rotating) record ko kahin bhejte hain;
    Formatter usse string banata hai; Filter record ko enrich/drop karta hai.
    Real config dictConfig (logging.config) se hoti hai — code me handlers haath
    se jodna nahi.

KYO NEED PADI:
    print() debugging production me kaam nahi karta — na levels, na routing, na
    rotation, na machine-readable output. ELK/Datadog ko chahiye STRUCTURED JSON
    (grep/filter ho sake), aur har line pe trace_id/order_id taaki month-end pe ek
    failed invoice ko poore pipeline me trace kar sako. Synchronous file/network
    logging request hot-path ko block karta hai — isiliye QueueHandler chahiye.

KAISE USE KARTE HAIN:
    Har module me `log = logging.getLogger(__name__)` — getLogger() singleton/cached
    hai. App startup pe EK baar dictConfig() se handlers+formatters+levels wire
    karo. Structured fields `log.info("msg", extra={"order_id": ...})` se bhejo,
    custom JSON Formatter unhe emit kare. Correlation-id ek logging.Filter se
    inject karo jo contextvar se trace_id uthata hai. Library me NEVER basicConfig.

KAHAN USE HOTA HAI (backend scenarios):
    1. SAP HANA invoice pipeline: structured JSON logs with trace_id + order_id —
       month-end failure ko Datadog me grep karke ek invoice ka full journey dikhe.
    2. Niroskos multi-tenant Django: har log line pe tenant_id (Filter via
       contextvar) taaki ek tenant ka traffic isolate karke debug ho.
    3. Celery/Redis workers: QueueHandler se logging worker hot-path se hatao —
       I/O slow handler request latency me na ghuse.
    4. Razorpay/PayU webhook handler: payment_id + idempotency_key structured fields
       me — duplicate webhook ko logs se confirm karna.
    5. Reusable connector LIBRARY: NullHandler attach, basicConfig kabhi nahi — app
       decide kare logs kahan jaayein.

INTERVIEW ANSWER (English — recite this):
    "Loggers form a dotted hierarchy rooted at the root logger, and by default a
    child's records propagate up to every ancestor's handlers, so the classic bug is
    adding a handler to both the root and a named logger, which prints every line
    twice; the fix is to attach handlers at exactly one level or set
    logger.propagate=False. I configure logging once at startup with dictConfig
    rather than wiring handlers in code, because it is declarative, environment-driven,
    and avoids import-order surprises. For observability I emit structured logs: I
    pass business fields through extra={} like order_id and tenant_id and use a
    custom JSON formatter so ELK or Datadog can index them, instead of grepping
    free-text. Correlation is handled by a logging.Filter that reads a request-id or
    trace-id from a contextvar and stamps it onto every record, so one logical
    operation is joinable across services. To keep logging off the async or request
    hot path I use a QueueHandler in the app with a QueueListener draining to the
    real file or network handler on a background thread, so slow I/O never blocks the
    request. In libraries I never call basicConfig and instead attach a NullHandler
    to my package logger, letting the application own configuration. The senior nuance
    is that the effective level is resolved up the hierarchy and handlers have their
    own independent levels, so a record can pass the logger yet be dropped by a
    handler, or be emitted twice if propagation is misconfigured."

================================================================================
Run:
    python 28_logging_production.py        # saare sections chalao
    python 28_logging_production.py 1 7    # sirf section 1 aur 7

Sections:
    1. DEMO  — hierarchy + propagation + levels (effective level resolve)
    2. DEMO  — dictConfig: real config method (handlers/formatters/levels declare)
    3. DEMO  — Stream/File/RotatingFileHandler (tmp dir me, rotation dikhao)
    4. REAL  — structured JSON formatter + extra={} (trace_id/order_id) — HANA invoice
    5. REAL  — correlation-id Filter via contextvar (per-request trace_id stamp)
    6. REAL  — QueueHandler + QueueListener (logging OFF the hot path)
    7. BREAK — handler on BOTH root + child -> har line TWICE; fix = propagate/one-level
    8. LIB   — basicConfig in library = anti-pattern; NullHandler = right way
    9. TODO  — tum khud likho: webhook_log() with payment_id + idempotency_key extra
================================================================================
"""
from __future__ import annotations

import io
import json
import logging
import logging.config
import logging.handlers
import os
import queue
import sys
import tempfile
import time
from contextvars import ContextVar


# Shared correlation-id contextvar (sections 5 + 7 + TODO isse uthate hain)
_trace_id: ContextVar[str] = ContextVar("trace_id", default="-")


def _fresh_logger(name: str) -> logging.Logger:
    """Helper: ek clean logger do — purane handlers hata ke, taaki demos
    ek dusre ko pollute na karein (getLogger cached hota hai)."""
    log = logging.getLogger(name)
    log.handlers.clear()
    log.propagate = True
    log.setLevel(logging.NOTSET)
    return log


# === SECTION 1: DEMO — hierarchy + propagation + levels ===
def section1() -> None:
    print("\n=== SECTION 1: hierarchy + propagation + effective level ===")

    # Hierarchy dotted-name se banti hai: "svc" parent, "svc.db" child.
    root_like = _fresh_logger("svc")
    child = _fresh_logger("svc.db")
    child.handlers.clear()  # child pe koi handler nahi -> record parent tak propagate

    # Sirf PARENT pe handler -> child ka log bhi yahin print hoga (propagation).
    out = io.StringIO()
    h = logging.StreamHandler(out)
    h.setFormatter(logging.Formatter("[%(name)s/%(levelname)s] %(message)s"))
    root_like.addHandler(h)
    root_like.setLevel(logging.INFO)

    # child ka apna level NOTSET -> effective level parent se inherit (INFO).
    print(f"  child.level set?      -> {child.level} (0 == NOTSET, inherit karega)")
    print(f"  child.getEffectiveLevel() -> {logging.getLevelName(child.getEffectiveLevel())}")

    child.debug("debug line")   # INFO se neeche -> drop
    child.info("invoice synced")  # parent ke handler se print
    print("  captured output:")
    for line in out.getvalue().splitlines():
        print(f"    {line}")
    print("  Lesson: child handler-less hai par parent ke handler tak propagate hua;"
          " level parent se inherit (NOTSET=0).")


# === SECTION 2: DEMO — dictConfig (the real config method) ===
def section2() -> None:
    print("\n=== SECTION 2: dictConfig — declarative config (real method) ===")

    buf = io.StringIO()
    config = {
        "version": 1,
        "disable_existing_loggers": False,  # IMPORTANT: warna baaki loggers mute ho jaate
        "formatters": {
            "plain": {"format": "[%(levelname)s] %(name)s: %(message)s"},
        },
        "handlers": {
            "mem": {
                "class": "logging.StreamHandler",
                "formatter": "plain",
                "level": "INFO",
                "stream": buf,  # demo ke liye buffer; prod me ext://sys.stdout
            },
        },
        "loggers": {
            "billing": {"handlers": ["mem"], "level": "INFO", "propagate": False},
        },
    }
    logging.config.dictConfig(config)
    log = logging.getLogger("billing")
    log.debug("ye drop hoga (level INFO)")
    log.info("dictConfig se wired logger")
    log.warning("rate limit close")
    print("  output from dict-configured logger:")
    for line in buf.getvalue().splitlines():
        print(f"    {line}")
    print("  Lesson: startup pe EK dictConfig() — handlers/formatters/levels"
          " declarative, env-driven; code me addHandler scatter karna anti-pattern.")


# === SECTION 3: DEMO — Stream / File / RotatingFileHandler ===
def section3() -> None:
    print("\n=== SECTION 3: Stream / File / RotatingFileHandler (rotation) ===")

    log = _fresh_logger("section3.rot")
    log.propagate = False
    log.setLevel(logging.INFO)

    # Tmp dir use karte hain taaki repo me file na bane (clean run).
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "app.log")
        # maxBytes chhota rakha taaki rotation turant trigger ho -> .1/.2 backups
        rot = logging.handlers.RotatingFileHandler(
            path, maxBytes=120, backupCount=2, encoding="utf-8"
        )
        rot.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        log.addHandler(rot)

        for i in range(12):
            log.info("invoice row %02d processed for tenant=acme", i)
        rot.close()

        files = sorted(os.listdir(d))
        print(f"  rotation ke baad files: {files}")
        print("    (app.log = current, .1/.2 = older rotated backups)")
        with open(path, encoding="utf-8") as f:
            current = f.read().strip().splitlines()
        print(f"  current app.log me {len(current)} line(s) (purani rotate ho gayi)")
    print("  Lesson: RotatingFileHandler size cross hone pe rename karke nayi file"
          " kholta; backupCount se disk bounded rehta — prod me must.")


# === SECTION 4: REAL — structured JSON formatter + extra={} (HANA invoice) ===
class JsonFormatter(logging.Formatter):
    """Custom JSON formatter for ELK/Datadog. Standard fields + jo bhi business
    fields extra={} se aaye (order_id, trace_id, tenant_id) unhe top-level JSON
    me daal deta — taaki Datadog inhe index/facet kar sake (free-text grep nahi)."""

    # LogRecord ke built-in attrs — inhe skip karke baaki "extra" pick karte hain.
    _RESERVED = set(vars(logging.LogRecord("", 0, "", 0, "", (), None)).keys()) | {
        "message", "asctime", "taskName",
    }

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        # Jo bhi extra={} se aaya (reserved ke alawa) usse JSON me merge karo.
        for k, v in record.__dict__.items():
            if k not in self._RESERVED and not k.startswith("_"):
                payload[k] = v
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str, sort_keys=True)


def section4() -> None:
    print("\n=== SECTION 4: structured JSON logs (SAP HANA invoice pipeline) ===")

    out = io.StringIO()
    log = _fresh_logger("hana.invoice")
    log.propagate = False
    log.setLevel(logging.INFO)
    h = logging.StreamHandler(out)
    h.setFormatter(JsonFormatter())
    log.addHandler(h)

    # Business context extra={} se -> machine-readable, greppable.
    log.info("invoice fetch start", extra={"trace_id": "T-77", "order_id": "ORD-9001"})
    log.info("posted to HANA", extra={"trace_id": "T-77", "order_id": "ORD-9001",
                                      "tenant_id": "acme", "rows": 14})
    try:
        raise ValueError("HANA: duplicate document number")
    except ValueError:
        log.error("invoice post failed", extra={"trace_id": "T-77",
                                                "order_id": "ORD-9002"}, exc_info=True)

    print("  emitted JSON lines (Datadog/ELK inhe field-wise index karega):")
    for line in out.getvalue().splitlines():
        obj = json.loads(line)
        # demo: ek-do key dikhao taaki structured nature clear ho
        print(f"    level={obj['level']:<7} order_id={obj.get('order_id')} "
              f"trace_id={obj.get('trace_id')} msg={obj['msg']!r}")
    print("  Lesson: month-end pe `order_id:ORD-9002` filter karke ek invoice ka"
          " poora journey nikal lo — free-text grep ki zaroorat nahi.")


# === SECTION 5: REAL — correlation-id Filter via contextvar ===
class TraceIdFilter(logging.Filter):
    """Har record pe trace_id stamp karo contextvar se. Log call me id pass nahi
    karni padti — middleware contextvar set karta, filter khud uthata. Yahi
    distributed correlation ka core hai."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.trace_id = _trace_id.get()
        return True


def section5() -> None:
    print("\n=== SECTION 5: correlation-id Filter (contextvar -> every line) ===")

    out = io.StringIO()
    log = _fresh_logger("svc.api")
    log.propagate = False
    log.setLevel(logging.INFO)
    h = logging.StreamHandler(out)
    h.setFormatter(logging.Formatter("[trace=%(trace_id)s] %(message)s"))
    h.addFilter(TraceIdFilter())  # filter handler pe -> trace_id attr guarantee
    log.addHandler(h)

    def deep_service_call() -> None:
        # Yahan trace_id KAHIN pass nahi hua — phir bhi line me aa jaata.
        log.info("charging via PayU")

    def handle_request(tid: str) -> None:
        token = _trace_id.set(tid)  # middleware boundary: set on enter
        try:
            log.info("request received")
            deep_service_call()
        finally:
            _trace_id.reset(token)  # reset on exit (clean teardown)

    handle_request("REQ-AAA")
    handle_request("REQ-BBB")
    log.info("outside any request")  # default '-' dikhega
    print("  every line apne request ke trace_id se tagged (deep call me bhi):")
    for line in out.getvalue().splitlines():
        print(f"    {line}")
    print("  Lesson: contextvar + logging.Filter = correlation-id without threading"
          " it through every signature; async-safe per-task.")


# === SECTION 6: REAL — QueueHandler + QueueListener (off the hot path) ===
def section6() -> None:
    print("\n=== SECTION 6: QueueHandler + QueueListener (logging off hot path) ===")

    out = io.StringIO()
    # 'real' (possibly slow) handler — file/network. QueueListener isse bg thread
    # par drain karta, isliye request thread sirf queue.put karta (fast, non-block).
    real = logging.StreamHandler(out)
    real.setFormatter(logging.Formatter("%(message)s"))

    log_q: queue.Queue[logging.LogRecord] = queue.Queue(-1)
    listener = logging.handlers.QueueListener(log_q, real, respect_handler_level=True)
    listener.start()  # background thread shuru

    log = _fresh_logger("worker.hot")
    log.propagate = False
    log.setLevel(logging.INFO)
    log.addHandler(logging.handlers.QueueHandler(log_q))  # app side: sirf enqueue

    t0 = time.perf_counter()
    for i in range(5):
        log.info("celery task processed id=%d", i)  # returns fast (just enqueue)
    enqueue_ms = (time.perf_counter() - t0) * 1000

    listener.stop()  # flush + bg thread band (records drain ho jaate)
    print(f"  5 log calls enqueued in ~{enqueue_ms:.2f} ms (slow I/O bg thread pe)")
    print("  drained output:")
    for line in out.getvalue().splitlines():
        print(f"    {line}")
    print("  Lesson: QueueHandler request/async hot-path ko non-blocking rakhta;"
          " actual slow handler (file/HTTP) listener ke bg thread pe chalta.")


# === SECTION 7: BREAK IT / GOTCHA — handler on BOTH root + child = duplicate logs ===
def section7() -> None:
    print("\n=== SECTION 7: BREAK IT — duplicate logs (handler on root + child) ===")

    # ---- GALAT: same logical sink root par bhi, named logger par bhi ----
    wrong = io.StringIO()
    root = _fresh_logger("")          # root logger
    rh = logging.StreamHandler(wrong)
    rh.setFormatter(logging.Formatter("%(message)s"))
    root.addHandler(rh)
    root.setLevel(logging.INFO)

    # NOTE: top-level naam "dupdemo" liya hai jiska koi configured parent nahi —
    # taaki kisi aur section ka propagate=False intermediate beech me na aaye.
    child = _fresh_logger("dupdemo.export")
    ch = logging.StreamHandler(wrong)  # SAME-ish sink child pe BHI
    ch.setFormatter(logging.Formatter("%(message)s"))
    child.addHandler(ch)
    child.setLevel(logging.INFO)
    # child.propagate default True -> record child handler me bhi, phir root tak bhi

    child.info("month-end invoice exported")
    wrong_lines = wrong.getvalue().splitlines()
    print("  WRONG output (handler on child AND propagated to root):")
    for line in wrong_lines:
        print(f"    {line}")
    print(f"    -> printed {len(wrong_lines)} times (expected 1)  [DUPLICATE BUG]")

    # ---- FIX option A: child.propagate = False (root tak na jaaye) ----
    fixed = io.StringIO()
    root2 = _fresh_logger("")
    rh2 = logging.StreamHandler(fixed)
    rh2.setFormatter(logging.Formatter("%(message)s"))
    root2.addHandler(rh2)
    root2.setLevel(logging.INFO)

    child2 = _fresh_logger("dupdemo.export")
    ch2 = logging.StreamHandler(fixed)
    ch2.setFormatter(logging.Formatter("%(message)s"))
    child2.addHandler(ch2)
    child2.setLevel(logging.INFO)
    child2.propagate = False  # <-- THE FIX (or: handler sirf ek hi level pe rakho)

    child2.info("month-end invoice exported")
    fixed_lines = fixed.getvalue().splitlines()
    print("  FIX (child.propagate=False, ya handler sirf one level pe):")
    for line in fixed_lines:
        print(f"    {line}")
    print(f"    -> printed {len(fixed_lines)} time (correct)")

    _fresh_logger("")  # cleanup: root handlers hata do (baaki sections clean rahein)
    print("  Lesson: ek hi sink ko do levels pe mat lagao. Either handler one level"
          " pe rakho, ya propagate=False set karo. Duplicate-log bug #1 hai.")


# === SECTION 8: LIB — basicConfig anti-pattern + NullHandler (libraries) ===
def section8() -> None:
    print("\n=== SECTION 8: library logging — basicConfig BAD, NullHandler GOOD ===")

    # ANTI-PATTERN (mat karo): library import hote hi basicConfig() call kare ->
    # root logger ko hijack karta, app ki config override/conflict; "No handlers"
    # warnings ko hide karke side-effects deta. Library ko OUTPUT decide nahi karna.
    print("  ANTI-PATTERN: library me basicConfig()/addHandler(StreamHandler) ->")
    print("    root config hijack, app ke handlers se conflict, duplicate output.")

    # SAHI: package logger pe NullHandler — taaki agar app ne config nahi kiya to
    # "No handlers could be found" warning na aaye, aur output app decide kare.
    libname = "myconnector"  # e.g. SAP HANA connector library
    lib_log = _fresh_logger(libname)
    lib_log.addHandler(logging.NullHandler())  # <-- right way for a library
    lib_log.propagate = True  # app ke handlers tak jaane do (agar app config kare)

    # Library code aise log karta — par OUTPUT app ke handlers decide karenge.
    lib_log.info("connector did work")  # NullHandler -> silently absorbed (no app cfg)
    has_null = any(isinstance(h, logging.NullHandler) for h in lib_log.handlers)
    print(f"  library logger {libname!r} handlers -> NullHandler present: {has_null}")
    print("  (NullHandler ke saath: koi spurious output nahi, app jab chahe config kare)")
    print("  Lesson: app me basicConfig OK (entrypoint). Library me NEVER —"
          " bas getLogger(__name__) + NullHandler; routing app ka kaam hai.")


# === SECTION 9: TODO — tum khud likho: webhook_log() with structured extra ===
def webhook_log(logger: logging.Logger, event: str, payment_id: str,
                idempotency_key: str) -> None:
    """
    TODO (tum implement karo):
      Ek Razorpay/PayU webhook handler ke liye structured log line emit karo.
      - `logger.info(event, extra={...})` call karo.
      - extra={} me ye fields ho: "payment_id", "idempotency_key", aur
        "trace_id": _trace_id.get()  (correlation-id contextvar se).
      Expected behaviour (JsonFormatter ke saath, section4 wala):
          handler ki JSON line me top-level keys aayein:
          payment_id, idempotency_key, trace_id, level=INFO, msg=event.
      Hint: bas `logger.info(event, extra={"payment_id": payment_id,
            "idempotency_key": idempotency_key, "trace_id": _trace_id.get()})`.
      (Yaad rahe: reserved attr names — message/args/levelname etc. — extra me
       mat daalna, warna KeyError aayega.)
    """
    raise NotImplementedError(
        "TODO: logger.info(event, extra={payment_id, idempotency_key, trace_id})"
    )


def section9() -> None:
    print("\n=== SECTION 9: TODO — webhook_log() structured fields (tum likho) ===")
    out = io.StringIO()
    log = _fresh_logger("webhook.payu")
    log.propagate = False
    log.setLevel(logging.INFO)
    h = logging.StreamHandler(out)
    h.setFormatter(JsonFormatter())
    log.addHandler(h)

    token = _trace_id.set("TR-555")
    try:
        webhook_log(log, "payment.captured", payment_id="pay_999",
                    idempotency_key="idem-abc")
        line = out.getvalue().strip()
        obj = json.loads(line) if line else {}
        ok = (obj.get("payment_id") == "pay_999"
              and obj.get("idempotency_key") == "idem-abc"
              and obj.get("trace_id") == "TR-555"
              and obj.get("level") == "INFO")
        print(f"  emitted -> {line}")
        print("  correct! structured webhook log with all fields." if ok
              else "  output galat hai — extra={} fields/keys dobara dekho.")
    except NotImplementedError as e:
        print(f"  abhi tak unimplemented (TODO complete karo): {e}")
    finally:
        _trace_id.reset(token)


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
        "8": section8,
        "9": section9,
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
