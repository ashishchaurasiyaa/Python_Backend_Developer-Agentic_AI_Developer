"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
DAY 53 (Part 1) — itertools.tee, contextlib.closing, ExitStack & friends
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

WHY THIS MATTERS:
  - Iterator EK BAAR consume hota hai — "do baar chahiye" problem har
    data-pipeline me aati hai. tee() iska standard jawab hai (with traps!).
  - Legacy objects (sockets, urllib responses, DB cursors) jinme close()
    hai par `with` support nahi — closing() unhe context-manager bana deta hai.
  - "N files kholo jahan N runtime pe pata chalega" — `with` statement se
    nahi hota, ExitStack se hota hai. Senior-level resource management yahi hai.

ARCHITECTURE UNDERSTANDING:
  tee(iterable, n=2) → n independent iterators
    → internally ek shared FIFO buffer: jo item SABSE SLOW copy ne abhi
      tak nahi padha, wo buffer me pada rehta hai
    → ek copy poora aage, dusra zero pe = PURA DATA buffer me = list() jaisa!

  contextlib toolbox:
    closing(obj)        → close() wale object ko CM banao
    suppress(Exc)       → specific exception chupchap ignore
    redirect_stdout(f)  → print() output kahin aur bhejo
    ExitStack()         → dynamic/conditional CMs ka stack
    nullcontext(val)    → "kuch nahi karne wala" CM (conditional CM pattern)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import contextlib
import io
import itertools
import os
import pathlib
import sys
import tempfile

# ============ SECTION 1: PROBLEM — ITERATOR EK BAAR HI CHALTA HAI ============

print("=== SECTION 1: one-shot iterator problem ===")

def temperature_stream():
    """Sensor readings ka generator — socha lo ye network se aa raha hai."""
    for t in [21.5, 22.0, 23.8, 22.9, 24.1]:
        yield t

readings = temperature_stream()
print(f"max = {max(readings)}")
# Ab generator EXHAUST ho chuka — dusra pass khali hai:
print(f"dusri baar list() = {list(readings)}")    # [] — classic silent bug!
# min(readings) yahan ValueError deta: "min() arg is an empty sequence"


# ============ SECTION 2: itertools.tee — EK SE INDEPENDENT COPIES ============

print("\n=== SECTION 2: tee basics ===")

# tee ek iterable se n INDEPENDENT iterators bana deta hai:
it_for_max, it_for_min = itertools.tee(temperature_stream(), 2)
print(f"max = {max(it_for_max)}, min = {min(it_for_min)}")   # dono chal gaye!

# ⚠️ RULE 1: tee karne ke baad ORIGINAL iterator ko HAATH MAT lagao.
# tee original se hi items kheenchta hai — tumne original se next() le liya
# to wo item copies ko KABHI nahi milega (silently skip ho jayega).
original = iter([1, 2, 3, 4])
a, b = itertools.tee(original)
next(original)                       # ❌ 1 ko original se kha liya...
print(f"a se mila: {list(a)}")       # [2, 3, 4] — 1 GAYAB, koi error nahi!
print(f"b se mila: {list(b)}")


# ============ SECTION 3: tee MEMORY CAUTION — LAGGING COPY SAB BUFFER KARTI HAI ============

print("\n=== SECTION 3: tee memory trap ===")

"""
tee kaam kaise karta hai (mental model):
    source ──► [ shared buffer (deque) ] ──► copy_a (pointer aage)
                                        └──► copy_b (pointer peeche)

  copy_a ne 1000 items padh liye, copy_b ne 0 →
  WOH SAARE 1000 items buffer me pade hain (copy_b ke intezaar me).

  Matlab: copies ko ROUGHLY SAATH-SAATH consume karo to buffer chhota
  rehta hai (O(gap) memory). Ek poora aage nikal gaya to memory-wise
  tee ≈ list() — fayda khatam.
"""

source = iter(range(1_000_000))
fast, slow = itertools.tee(source)

count = sum(1 for _ in itertools.islice(fast, 100_000))   # fast 1 lakh aage
# Ab un 100k items ka buffer memory me hai kyunki slow ne kuch nahi padha.
print(f"fast ne {count} consume kiye; slow abhi {next(slow)} pe hai")
print("→ wo 100k items abhi BUFFER me the (lagging copy ka cost)")
del fast, slow, source     # buffer free

"""
DECISION TABLE: tee vs list()
  ┌────────────────────────────────────────────┬──────────────────┐
  │ Situation                                  │ Kya use karo     │
  ├────────────────────────────────────────────┼──────────────────┤
  │ Copies LOCKSTEP me chalenge (pairwise,     │ tee ✓ (buffer    │
  │ sliding window, zip ke saath)              │ chhota rahega)   │
  │ Data chhota hai / dono baar poora chahiye  │ list() — simple, │
  │                                            │ re-iterable, fast│
  │ Infinite/huge stream + copies saath chalti │ tee ✓ (list ho   │
  │                                            │ hi nahi sakti)   │
  │ Ek copy poori pehle consume hogi           │ list() — tee ka  │
  │                                            │ koi fayda nahi   │
  └────────────────────────────────────────────┴──────────────────┘
  + tee ke iterators THREAD-SAFE NAHI hain — alag threads me mat baanto.
"""

# ── PAIRWISE RECIPE via tee (sliding window ka classic) ──
def pairwise_recipe(iterable):
    """s → (s0,s1), (s1,s2), (s2,s3)... — official itertools recipe."""
    a, b = itertools.tee(iterable)
    next(b, None)            # b ko EK STEP aage khiska do (default=None: empty-safe)
    return zip(a, b)         # zip lockstep me chalata hai → buffer max 1 item!

temps = [21.5, 22.0, 23.8, 22.9, 24.1]
changes = [round(curr - prev, 1) for prev, curr in pairwise_recipe(temps)]
print(f"Temperature changes: {changes}")    # [0.5, 1.8, -0.9, 1.2]

# Python 3.10+ me ye built-in hai: itertools.pairwise(temps) — wahi cheez,
# C-speed me. Recipe isliye samjho kyunki interview me "implement pairwise"
# poocha jaata hai aur ye tee ka perfect (lockstep) use-case dikhata hai.
print(f"Built-in pairwise: {list(itertools.pairwise(temps))[:2]}...")


# ============ SECTION 4: contextlib.closing — close() HAI, with SUPPORT NAHI ============

print("\n=== SECTION 4: contextlib.closing ===")

# Kuch (aksar LEGACY) objects me close() to hai par __enter__/__exit__ nahi —
# unhe `with` me daalo to TypeError / AttributeError.
# Classic examples: purane socket wrappers, urllib.request.urlopen (purane
# Python me), kai DB cursors, third-party SDK ke connection objects.

class LegacyFTPConnection:
    """Socha lo ye 2010 ki third-party library hai — sirf close() deti hai."""
    def __init__(self, host):
        self.host = host
        self.open_flag = True
        print(f"  [conn] {host} se juda")

    def fetch(self, path):
        if not self.open_flag:
            raise RuntimeError("connection band hai!")
        return f"<data of {path}>"

    def close(self):
        self.open_flag = False
        print(f"  [conn] {self.host} band — resource free")

# ❌ with LegacyFTPConnection(...) → AttributeError: __enter__
# ✓ closing() us object ko wrap karke CM bana deta hai:
#     __enter__ → object hi return, __exit__ → object.close() (exception me BHI)
with contextlib.closing(LegacyFTPConnection("ftp.example.com")) as conn:
    print(f"  fetched: {conn.fetch('/report.csv')}")
print(f"  block ke baad open? {conn.open_flag}")    # False — guaranteed close

# Exception aane par bhi close hota hai — yahi poora point hai:
try:
    with contextlib.closing(LegacyFTPConnection("ftp.flaky.com")) as conn:
        raise ConnectionError("network gir gaya beech me!")
except ConnectionError:
    print(f"  error ke baad bhi open? {conn.open_flag}")   # False!

# urllib pattern (purane codebases me milega):
#   from contextlib import closing
#   with closing(urllib.request.urlopen(url)) as page:
#       data = page.read()
# NOTE: aaj urlopen ka response khud CM hai; requests/sockets bhi.
# closing() ki zaroorat = legacy/third-party objects. Ek line ka adapter,
# khud ka wrapper class likhne ki zaroorat nahi.


# ============ SECTION 5: contextlib RECAP TABLE + suppress / redirect_stdout ============

print("\n=== SECTION 5: suppress + redirect_stdout ===")

"""
contextlib CHEAT TABLE:
  ┌─────────────────────┬───────────────────────────────────────────────┐
  │ Tool                │ Kab use karna                                 │
  ├─────────────────────┼───────────────────────────────────────────────┤
  │ closing(obj)        │ close() wala legacy object `with` me chahiye  │
  │ suppress(Exc, ...)  │ "ye exception aaye to ignore" — try/pass se   │
  │                     │ saaf aur intent-clear                         │
  │ redirect_stdout(f)  │ print()/stdout kisi file ya StringIO me       │
  │ redirect_stderr(f)  │ bhejna (legacy code ka output capture)        │
  │ ExitStack()         │ DYNAMIC number of CMs / conditional cleanup   │
  │ nullcontext(val)    │ "CM chahiye ya nahi" runtime pe decide hota   │
  │ @contextmanager     │ generator se custom CM (yield = beech ka kaam)│
  └─────────────────────┴───────────────────────────────────────────────┘
"""

# suppress — "file nahi hai to koi baat nahi" wala intent, bina try/pass ke:
with contextlib.suppress(FileNotFoundError):
    os.remove("kabhi_thi_hi_nahi.txt")
print("suppress: FileNotFoundError chupchap ignore hua")
# = try: os.remove(...) except FileNotFoundError: pass — par padhne me saaf.
# ⚠️ SIRF narrow, expected exceptions suppress karo —
# suppress(Exception) likha to bugs bhi chup ho jayenge!

# redirect_stdout — print-heavy legacy function ka output capture:
def legacy_report():
    print("Revenue: 42 lakh")          # purana code, return nahi karta, print karta hai
    print("Costs: 30 lakh")

buffer = io.StringIO()
with contextlib.redirect_stdout(buffer):
    legacy_report()                     # ye prints buffer me gaye, screen pe nahi
captured = buffer.getvalue()
print(f"redirect_stdout ne pakda: {captured.splitlines()}")
# ⚠️ Ye sys.stdout GLOBALLY swap karta hai — threads/async me sab affect honge.


# ============ SECTION 6: ExitStack — VARIABLE NUMBER OF FILES (SOLID DEMO) ============

print("\n=== SECTION 6: ExitStack ===")

# PROBLEM: `with open(a) as f1, open(b) as f2:` tab chalta hai jab files
# ka COUNT compile-time pe pata ho. Par "merge karo jitni bhi CSV folder
# me hain" — count RUNTIME pe aata hai. Loop me with nesting impossible.

workdir = pathlib.Path(tempfile.mkdtemp(prefix="day53_stack_"))
for i, region in enumerate(["north", "south", "east"], 1):
    (workdir / f"sales_{region}.csv").write_text(
        f"region,amount\n{region},{i * 1000}\n", encoding="utf-8")

input_paths = sorted(workdir.glob("sales_*.csv"))   # count runtime pe pata chala!

def merge_files(paths, out_path):
    with contextlib.ExitStack() as stack:
        # enter_context() har file ko stack pe REGISTER karta hai —
        # block ke end pe (ya exception pe) sab REVERSE ORDER me close hongi.
        files = [stack.enter_context(open(p, encoding="utf-8")) for p in paths]
        out = stack.enter_context(open(out_path, "w", encoding="utf-8"))

        # KHOOBSURTI: agar 3rd file kholte waqt exception aayi,
        # to pehli 2 files PHIR BHI close hongi — manually try/finally
        # ka pyramid likhne ki zaroorat nahi.
        out.write("region,amount\n")
        for f in files:
            next(f)                        # har file ka header skip
            for line in f:
                out.write(line)
    # yahan tak aate-aate SAARI files (N inputs + 1 output) band ho chuki hain

merged = workdir / "merged.csv"
merge_files(input_paths, merged)
print(f"{len(input_paths)} files merge hui:")
print(merged.read_text(encoding="utf-8").strip())

# ExitStack ke 2 aur power-moves:
#   stack.callback(func, *args) → koi BHI cleanup function register karo (CM na ho to bhi)
#   stack.pop_all()             → cleanup ka ownership TRANSFER karo (sab theek
#                                 raha to abhi close mat karo, baad me caller karega)
def open_all_or_nothing(paths):
    """Ya saari files khulengi, ya (kisi ek ke fail pe) saari close ho jayengi."""
    with contextlib.ExitStack() as stack:
        files = [stack.enter_context(open(p, encoding="utf-8")) for p in paths]
        keeper = stack.pop_all()    # success! cleanup is `with` se DETACH kar do
        return files, keeper        # caller baad me keeper.close() karega

files, keeper = open_all_or_nothing(input_paths)
print(f"pop_all ke baad files khuli hain? {not files[0].closed}")
keeper.close()                       # ab caller ne close kiya
print(f"keeper.close() ke baad band? {files[0].closed}")


# ============ SECTION 7: nullcontext — CONDITIONAL CM PATTERN ============

print("\n=== SECTION 7: nullcontext ===")

# PROBLEM: function file me BHI likh sake aur stdout pe BHI — par `with`
# stdout ko CLOSE kar dega (galat!). Do branches me duplicate code? Nahi —
# nullcontext(val) ek dummy CM hai: __enter__ val return karta hai,
# __exit__ KUCH NAHI karta (close nahi!).

def write_report(lines, out_file=None):
    # out_file diya → asli file kholo (close hogi).
    # nahi diya → stdout use karo (close NAHI hogi — nullcontext dhanyavaad).
    ctx = open(out_file, "w", encoding="utf-8") if out_file else contextlib.nullcontext(sys.stdout)
    with ctx as sink:
        for line in lines:
            sink.write(line + "\n")

print("stdout par:")
write_report(["row-1", "row-2"])                       # stdout zinda raha!
report_path = workdir / "report.txt"
write_report(["row-1", "row-2"], out_file=str(report_path))
print(f"file me bhi gaya: {report_path.read_text(encoding='utf-8').split()}")

# Dusra classic use: optional lock —
#   lock_ctx = threading.Lock() if thread_safe else contextlib.nullcontext()
#   with lock_ctx: ...
# Ek hi code path, condition sirf CM choose karne me.

# ============ CLEANUP ============
import shutil
shutil.rmtree(workdir)
print("\nDone — 03_itertools_tee_contextlib_closing.py")

"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
INTERVIEW QUESTIONS:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Q1: itertools.tee kya karta hai? Internally kaise?
A:  Ek iterable se n independent iterators banata hai. Internally shared
    FIFO buffer: source se item ek hi baar khincha jaata hai, aur tab tak
    buffer me rehta hai jab tak SABSE PEECHE wali copy use padh na le.
    Isliye memory = copies ke beech ka GAP.

Q2: tee ka memory trap?
A:  Agar ek copy poori consume ho gayi aur dusri ne kuch nahi padha,
    to PURA stream buffer me hai — tee effectively list() ban gaya,
    bina list() ki re-iterability ke. Rule: copies lockstep me chalao
    (zip/pairwise style), warna seedha list() lo. Aur tee ke baad
    ORIGINAL iterator use mat karo — items silently skip ho jaate hain.

Q3: tee vs list() copy — decision kaise?
A:  Lockstep consumption ya infinite/huge stream → tee.
    Chhota data, ya ek pass poora pehle hoga → list() (simple, re-iterable).
    Threads me share karna ho → tee bilkul nahi (thread-safe nahi hai).

Q4: pairwise ko tee se kaise implement karoge?
A:  a, b = tee(iterable); next(b, None); return zip(a, b)
    b ek step aage hai, zip lockstep me chalata hai → buffer max 1 item.
    Python 3.10+ me itertools.pairwise built-in hai.

Q5: contextlib.closing kab chahiye?
A:  Jab object me close() hai par __enter__/__exit__ nahi (legacy sockets,
    purane urllib responses, kai SDK connections). closing(obj) ka
    __exit__ guarantee karta hai obj.close() — exception path me bhi.
    Khud adapter class likhne se ek-line better.

Q6: ExitStack kab use karte ho? enter_context vs callback vs pop_all?
A:  Jab CMs ka COUNT ya HONA runtime pe decide hota hai (N files merge,
    conditional resources). enter_context(cm) → CM ko stack pe register
    (reverse-order cleanup, partial-failure me bhi jo khula wo band hoga).
    callback(fn) → koi bhi cleanup function register (non-CM ke liye).
    pop_all() → cleanup ownership transfer — "sab set ho gaya to ab close
    mat karo, caller karega" (all-or-nothing acquisition pattern).

Q7: nullcontext kya solve karta hai?
A:  Conditional CM: "kabhi asli resource (file/lock), kabhi kuch nahi" —
    dono ke liye EK with-block. nullcontext(sys.stdout) stdout return
    karta hai par exit pe close NAHI karta. Optional lock bhi classic:
    with (lock if thread_safe else nullcontext()): ...

Q8: suppress(Exception) likhna kyun galat hai?
A:  suppress sirf NARROW expected exceptions ke liye hai
    (FileNotFoundError jaise). Exception-level suppress karne se asli
    bugs (TypeError, KeyError) bhi silently kha jaayega — debugging
    nightmare. Wahi bare-except wali galti, naye kapdon me.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
