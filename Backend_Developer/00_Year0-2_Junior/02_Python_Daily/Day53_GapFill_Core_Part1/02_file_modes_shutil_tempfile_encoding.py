"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
DAY 53 (Part 1) — File Modes ('x', r+/w+/a+, seek), shutil, tempfile, Encoding
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

WHY THIS MATTERS:
  - 'x' mode + os.replace = atomic file operations — lock files, safe config
    writes, deploy scripts. Race-condition-free code isi se banta hai.
  - shutil = har backup/deploy/cleanup script ka backbone.
  - tempfile = secure temp handling (predictable /tmp names = security bug).
  - encoding explicit na likhna = "mere laptop pe chalta hai, Windows server
    pe UnicodeDecodeError" — classic production incident.

ARCHITECTURE UNDERSTANDING:
  MODE TABLE (sab read+write modes):
  ┌──────┬────────┬─────────┬──────────────┬─────────────────────────┐
  │ Mode │ Read?  │ Write?  │ File exists? │ Pointer / Truncate      │
  ├──────┼────────┼─────────┼──────────────┼─────────────────────────┤
  │ r+   │  ✓     │  ✓      │ HONI CHAHIYE │ start pe, NO truncate   │
  │ w+   │  ✓     │  ✓      │ TRUNCATE!    │ start pe, sab UDA dega  │
  │ a+   │  ✓     │  ✓      │ create/append│ END pe; write HAMESHA   │
  │      │        │         │              │ end pe jaata hai        │
  │ x    │  ✗     │  ✓      │ ERROR if     │ atomic exclusive create │
  │      │        │         │ exists!      │ (FileExistsError)       │
  └──────┴────────┴─────────┴──────────────┴─────────────────────────┘

  seek(offset, whence):  whence 0 = file start, 1 = current pos, 2 = file end
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import io
import os
import pathlib
import shutil
import sys
import tempfile

# Saara demo ek scratch directory me — system gandha nahi karenge
SCRATCH = pathlib.Path(tempfile.mkdtemp(prefix="day53_"))
os.chdir(SCRATCH)
print(f"Scratch dir: {SCRATCH}\n")

# ============ SECTION 1: 'x' MODE — EXCLUSIVE CREATE (ATOMIC) ============

print("=== SECTION 1: 'x' mode ===")

# 'x' = create ONLY IF file exist nahi karti. Exist karti hai → FileExistsError.
# Check + create EK atomic syscall (O_CREAT|O_EXCL) — TOCTOU race impossible.
with open("app.lock", "x") as f:
    f.write(str(os.getpid()))
print("Lock file ban gayi (x mode)")

try:
    with open("app.lock", "x") as f:    # dubara try — file already hai
        f.write("dusra process")
except FileExistsError:
    print("FileExistsError: koi aur process already lock liye baitha hai")

# REAL USE CASE — single-instance lock (cron job double-run rokna):
def acquire_lock(lock_path: str) -> bool:
    try:
        with open(lock_path, "x") as f:   # atomic: ya to MAINE banayi, ya kisi aur ne
            f.write(str(os.getpid()))
        return True
    except FileExistsError:
        return False

print(f"Lock mila? {acquire_lock('app.lock')}")   # False — already held
os.remove("app.lock")

# ❌ GALAT tarika (race-prone LBYL):
#   if not os.path.exists(lock):  ← yahan tak nahi thi...
#       open(lock, 'w')           ← ...par yahan tak DO process pahunch sakte hain!


# ============ SECTION 2: r+ vs w+ vs a+ — POINTER AUR TRUNCATION DEMOS ============

print("\n=== SECTION 2: r+ / w+ / a+ ===")

pathlib.Path("data.txt").write_text("AAAA BBBB CCCC", encoding="utf-8")

# r+ : pointer START pe, truncate NAHI — write OVERWRITE karta hai in-place
with open("data.txt", "r+", encoding="utf-8") as f:
    print(f"r+ open hote hi pointer: {f.tell()}")   # 0
    f.write("XXXX")                                  # pehle 4 chars overwrite
print(f"r+ ke baad: {pathlib.Path('data.txt').read_text(encoding='utf-8')}")
# 'XXXX BBBB CCCC' — sirf utna replace hua jitna likha, baaki bacha raha. TRAP!

# w+ : pointer start pe, par file pehle hi TRUNCATE (khali) ho chuki hoti hai
with open("data.txt", "w+", encoding="utf-8") as f:
    print(f"w+ open hote hi file size: {os.path.getsize('data.txt')}")  # 0 — sab uda!
    f.write("fresh content")
    f.seek(0)                       # wapas start pe jao tabhi padh paoge
    print(f"w+ readback: {f.read()}")

# a+ : pointer END pe, write HAMESHA end pe — seek() karke bhi beech me
#      write NAHI kar sakte (O_APPEND kernel-level guarantee hai)
with open("data.txt", "a+", encoding="utf-8") as f:
    print(f"a+ open hote hi pointer: {f.tell()}")    # file ke end pe
    f.seek(0)                       # start pe le gaye...
    f.write(" +appended")           # ...par write END pe hi gaya!
    f.seek(0)
    print(f"a+ readback: {f.read()}")
# Output: 'fresh content +appended' — seek(0) ignore hua write ke liye

# r+ pe missing file = FileNotFoundError (w+/a+ create kar dete hain)
try:
    open("nahi_hai.txt", "r+")
except FileNotFoundError:
    print("r+ ko existing file chahiye — FileNotFoundError")


# ============ SECTION 3: seek() WHENCE MODES 0/1/2 ============

print("\n=== SECTION 3: seek whence ===")

# whence=1 (current) aur whence=2 (end) NON-ZERO offset ke saath
# SIRF BINARY MODE me chalte hain — text mode me character≠byte hota hai
# (multi-byte UTF-8), isliye Python mana kar deta hai.
with open("bytes.bin", "wb") as f:
    f.write(b"0123456789")

with open("bytes.bin", "rb") as f:
    f.seek(2, 0)                    # whence 0: start se 2 bytes aage
    print(f"seek(2, 0)  → read(1) = {f.read(1)}")    # b'2'
    f.seek(3, 1)                    # whence 1: CURRENT se 3 aage (3 → 6)
    print(f"seek(3, 1)  → read(1) = {f.read(1)}")    # b'6'
    f.seek(-2, 2)                   # whence 2: END se 2 peeche
    print(f"seek(-2, 2) → read(1) = {f.read(1)}")    # b'8'

# Text mode trap demo:
with open("data.txt", "r", encoding="utf-8") as f:
    try:
        f.seek(5, 1)                # text mode + nonzero cur-relative = error
    except (io.UnsupportedOperation, OSError) as e:
        print(f"Text mode me seek(5, 1) → {type(e).__name__}")
# REAL USE: log tailing — binary me seek(-1024, 2) karke last 1KB padho.


# ============ SECTION 4: shutil — COPY FAMILY ============

print("\n=== SECTION 4: shutil copy family ===")

src = pathlib.Path("report.txt")
src.write_text("quarterly numbers", encoding="utf-8")
os.utime(src, (1000000000, 1000000000))     # purana mtime set kiya (demo ke liye)

# TEEN copy functions — फर्क METADATA aur DESTINATION me:
shutil.copyfile("report.txt", "c1.txt")   # SIRF content; dest FILE hi hona chahiye
shutil.copy("report.txt", "c2.txt")       # content + PERMISSIONS; dest dir bhi chalega
shutil.copy2("report.txt", "c3.txt")      # copy + TIMESTAMPS/metadata (cp -p jaisa)

print(f"original mtime: {os.path.getmtime('report.txt'):.0f}")
print(f"copy    mtime: {os.path.getmtime('c2.txt'):.0f}   (abhi ka time — metadata nahi gaya)")
print(f"copy2   mtime: {os.path.getmtime('c3.txt'):.0f}   (preserve hua!)")
# RULE: backup bana rahe ho → copy2 (mtime-based tools ko sahi info milegi).
# NOTE: koi bhi copy OWNER/ACL preserve nahi karta — wo sirf root-level tools me.

# copytree — poora directory tree
pathlib.Path("project/src").mkdir(parents=True)
pathlib.Path("project/src/main.py").write_text("print('hi')", encoding="utf-8")
pathlib.Path("project/.env").write_text("SECRET=123", encoding="utf-8")

shutil.copytree("project", "project_bak")
# Dubara chalao to FileExistsError — UNLESS dirs_exist_ok=True (Python 3.8+):
shutil.copytree("project", "project_bak", dirs_exist_ok=True)   # merge/overwrite
print(f"copytree done: {sorted(p.name for p in pathlib.Path('project_bak').rglob('*'))}")

# ignore param — .env, __pycache__ jaisi cheezein skip karo:
shutil.copytree("project", "project_clean",
                ignore=shutil.ignore_patterns(".env", "__pycache__", "*.pyc"))
print(f".env copy hua clean me? {pathlib.Path('project_clean/.env').exists()}")

# move — same filesystem pe = sasta rename; cross-device pe = copy2 + delete
shutil.move("c1.txt", "moved.txt")
print(f"moved.txt exists: {pathlib.Path('moved.txt').exists()}")

# disk_usage — deploy se pehle space check (named tuple: total/used/free)
usage = shutil.disk_usage("/")
print(f"Disk free: {usage.free / 1e9:.1f} GB / {usage.total / 1e9:.1f} GB")


# ============ SECTION 5: shutil — rmtree, ARCHIVES, BACKUP SCRIPT ============

print("\n=== SECTION 5: rmtree + archives ===")

# rmtree — recursive delete. Read-only file pe Windows me fail hota hai;
# error handler de sakte ho jo chmod karke retry kare:
def _force_remove(func, path, exc_info):
    """rmtree error handler: read-only file? writable banao, phir retry."""
    os.chmod(path, 0o600)
    func(path)

# Python 3.12+ me 'onerror' deprecated, 'onexc' aaya (signature thoda alag) —
# version-safe call:
if sys.version_info >= (3, 12):
    shutil.rmtree("project_clean", onexc=lambda f, p, e: _force_remove(f, p, e))
else:
    shutil.rmtree("project_clean", onerror=_force_remove)
print("project_clean rmtree se uda diya")
# Quick-n-dirty: shutil.rmtree(path, ignore_errors=True) — par errors CHHUP jaati hain.

# make_archive / unpack_archive — zip/tar bina subprocess ke
archive = shutil.make_archive("project_backup", "zip", root_dir="project")
print(f"Archive bana: {pathlib.Path(archive).name} "
      f"({os.path.getsize(archive)} bytes)")
shutil.unpack_archive(archive, "restored")
print(f"Restore hua: {sorted(p.name for p in pathlib.Path('restored').rglob('*'))}")

# ── REAL-WORLD: backup script (sab pieces ek saath) ──
def backup_project(src_dir: str, backup_root: str, keep: int = 3) -> str:
    """Timestamped zip backup + purane backups rotate karo."""
    backup_dir = pathlib.Path(backup_root)
    backup_dir.mkdir(exist_ok=True)

    # Space check — kam se kam 100MB free chahiye
    if shutil.disk_usage(backup_dir).free < 100 * 1024 * 1024:
        raise OSError("Disk full — backup skip")

    from datetime import datetime
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    archive = shutil.make_archive(str(backup_dir / f"backup_{stamp}"),
                                  "zip", root_dir=src_dir)

    # Rotation: sirf latest `keep` backups rakho
    backups = sorted(backup_dir.glob("backup_*.zip"))
    for old in backups[:-keep]:
        old.unlink()
    return archive

print(f"Backup script: {pathlib.Path(backup_project('project', 'backups')).name}")


# ============ SECTION 6: tempfile — SECURE TEMPORARY FILES ============

print("\n=== SECTION 6: tempfile ===")

# KYUN tempfile? open('/tmp/myapp.txt','w') me:
#   (1) naam predictable → attacker pehle se symlink rakh sakta hai (security!)
#   (2) do process same naam → data corruption
# tempfile random naam + O_EXCL + 0o600 perms deta hai — sab solve.

# TemporaryFile — NAAM HI NAHI hai (Unix pe disk se turant unlink ho jaati hai)
# → kisi aur process se share NAHI kar sakte; pure scratch space
with tempfile.TemporaryFile(mode="w+", encoding="utf-8") as tf:
    tf.write("scratch data")
    tf.seek(0)
    print(f"TemporaryFile read: {tf.read()}")
# block khatam = file gayab, koi cleanup nahi karna

# NamedTemporaryFile — naam HAI (.name) → dusre tool/process ko path de sakte ho
with tempfile.NamedTemporaryFile(mode="w+", suffix=".json", delete=False) as ntf:
    ntf.write('{"job": "demo"}')
    temp_path = ntf.name
print(f"NamedTemporaryFile path: {pathlib.Path(temp_path).name}")

# ⚠️ WINDOWS TRAP: delete=True (default) ke saath file OPEN rehte hue
# usi naam se DUSRA open() Windows pe FAIL hota hai (Unix pe chal jaata hai).
# Isliye cross-platform pattern: delete=False → band karo → use karo → khud unlink:
os.unlink(temp_path)
# (Python 3.12+ me delete_on_close=False aaya jo ye dard kam karta hai.)

# TemporaryDirectory — poori disposable directory, exit pe rmtree automatic
with tempfile.TemporaryDirectory(prefix="build_") as td:
    (pathlib.Path(td) / "artifact.txt").write_text("compiled", encoding="utf-8")
    print(f"TemporaryDirectory me files: {os.listdir(td)}")
print(f"Block ke baad dir exists? {pathlib.Path(td).exists()}")   # False

# mkstemp — LOW-LEVEL: (os-level fd, path) deta hai, cleanup TUMHARI zimmedari
fd, mkpath = tempfile.mkstemp(suffix=".tmp")
os.write(fd, b"low level bytes")
os.close(fd)                       # ⚠️ fd close karna MAT bhoolna — fd leak!
os.unlink(mkpath)
print("mkstemp: fd manually close + unlink kiya")

# ── KILLER PATTERN: ATOMIC WRITE (temp + os.replace) ──
# Problem: open('config.json','w') crash ho gaya beech me → ADHA-LIKHA file,
# poora config corrupt. Reader ko ya PURANA file dikhe ya NAYA — adha kabhi nahi.
def atomic_write(target: str, data: str):
    target_path = pathlib.Path(target)
    # Temp file USI DIRECTORY me banao — os.replace sirf same filesystem
    # pe atomic hai (/tmp alag mount ho sakta hai!)
    fd, tmp = tempfile.mkstemp(dir=target_path.parent, prefix=".tmp_")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())        # OS buffer se disk tak pakka pahunche
        os.replace(tmp, target)         # ATOMIC rename — POSIX guarantee
    except BaseException:
        os.unlink(tmp)                  # fail hue to temp file mat chhodo
        raise

atomic_write("config.json", '{"version": 2}')
print(f"Atomic write done: {pathlib.Path('config.json').read_text(encoding='utf-8')}")
# os.rename vs os.replace: Windows pe rename existing target pe FAIL karta hai,
# replace overwrite karta hai — isliye HAMESHA os.replace use karo.


# ============ SECTION 7: ENCODING — UTF-8 EXPLICIT KYUN ============

print("\n=== SECTION 7: encoding ===")

# RULE 0: open() me encoding na do to LOCALE DEFAULT lagta hai:
#   Linux/Mac → (aksar) utf-8     Windows → cp1252!! (legacy ANSI)
# Matlab: tumhare Mac pe likhi file Windows server pe padhte hi
# UnicodeDecodeError ya — aur bura — SILENT galat characters (mojibake).
import locale
print(f"Is system ka locale default: {locale.getpreferredencoding(False)}")
# Python 3.15 se UTF-8 default hoga (PEP 686); tab tak EXPLICIT likho.
# python -X utf8 ya PYTHONUTF8=1 se abhi bhi force kar sakte ho.

text = "Café bill: ₹450 😀"
with open("note.txt", "w", encoding="utf-8") as f:    # ✓ HAMESHA explicit
    f.write(text)

raw = pathlib.Path("note.txt").read_bytes()
print(f"chars = {len(text)}, bytes = {len(raw)}")     # ₹=3 bytes, 😀=4 bytes!
# YAHI hai bytes vs str boundary: len, slicing, seek — sab BYTES pe alag,
# CHARS pe alag. Kabhi mat maano 1 char = 1 byte.

# ── UnicodeDecodeError + errors= modes ──
# cp1252 (Windows) se likhi file ko utf-8 me padhne ki koshish:
pathlib.Path("windows_export.txt").write_bytes("Café".encode("cp1252"))  # é = b'\xe9'

try:
    pathlib.Path("windows_export.txt").read_text(encoding="utf-8")  # strict default
except UnicodeDecodeError as e:
    print(f"UnicodeDecodeError: byte {e.object[e.start]!r} position {e.start} pe")

# errors= ke teen kaam ke modes:
for mode in ("replace", "ignore"):
    with open("windows_export.txt", encoding="utf-8", errors=mode) as f:
        print(f"errors={mode!r:9} → {f.read()!r}")
# strict  → exception (DEFAULT — data pipelines me YAHI chahiye, fail loud!)
# replace → � (U+FFFD) daal deta hai — log viewers ke liye theek
# ignore  → byte chupchap UDA deta hai — DATA LOSS, last resort only
# Asli fix: SAHI encoding se kholo → encoding='cp1252'
print(f"Sahi fix     → {pathlib.Path('windows_export.txt').read_text(encoding='cp1252')!r}")

# ── utf-8-sig: BOM (Byte Order Mark) ──
# Excel/Notepad CSV export me shuru me 3 bytes EF BB BF daal dete hain.
pathlib.Path("excel.csv").write_text("name,city\nAshish,Mumbai", encoding="utf-8-sig")
raw = pathlib.Path("excel.csv").read_bytes()
print(f"File ke pehle 3 bytes: {raw[:3]}")                       # b'\xef\xbb\xbf'

plain = pathlib.Path("excel.csv").read_text(encoding="utf-8")
print(f"utf-8 se padha     → pehla char {plain[0]!r}")           # '﻿' GHUS GAYA!
# TRAP: ab row['name'] KeyError dega kyunki header '﻿name' hai!
clean = pathlib.Path("excel.csv").read_text(encoding="utf-8-sig")
print(f"utf-8-sig se padha → pehla char {clean[0]!r}")           # 'n' — BOM strip
# RULE: CSV/text jo Excel/Windows se aa sakta hai → encoding='utf-8-sig' READ me.
# WRITE me utf-8-sig tabhi jab consumer Excel ho (warna BOM mat daalo).

# ── BYTES vs STR BOUNDARY RULE ──
# str   = TEXT (Unicode codepoints) — program ke ANDAR sirf yahi
# bytes = RAW DATA (network, disk, subprocess) — sirf BOUNDARY pe
# Pattern: "decode at input boundary, encode at output boundary" —
# beech ke code ko encoding ki KHABAR hi nahi honi chahiye.
payload: bytes = text.encode("utf-8")     # OUTPUT boundary: str → bytes
restored: str = payload.decode("utf-8")   # INPUT boundary:  bytes → str
print(f"Round-trip sahi? {restored == text}")

# ============ CLEANUP ============
os.chdir("/")
shutil.rmtree(SCRATCH)
print(f"\nScratch dir saaf. Done — 02_file_modes_shutil_tempfile_encoding.py")

"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
INTERVIEW QUESTIONS:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Q1: 'x' mode kya hai aur 'w' se kaise alag?
A:  'x' = exclusive create — file exist kare to FileExistsError.
    Check+create ek atomic syscall (O_CREAT|O_EXCL) hai → TOCTOU race nahi.
    'w' chupchap existing file truncate kar deta hai. Lock files,
    "ek hi baar process karo" semantics ke liye 'x' lo.

Q2: r+ vs w+ vs a+?
A:  r+ → read/write, file EXIST honi chahiye, truncate NAHI, pointer start pe,
         write in-place overwrite karta hai (partial overwrite trap!).
    w+ → read/write, TRUNCATE/create, pointer start pe.
    a+ → read/append, create, pointer end pe; seek() ke baad bhi WRITE
         hamesha end pe jaata hai (O_APPEND kernel guarantee).

Q3: seek() ke whence values?
A:  0 = file start se (default), 1 = current position se, 2 = end se.
    Non-zero offset ke saath whence 1/2 SIRF binary mode me — text mode me
    chars≠bytes isliye Python io.UnsupportedOperation deta hai.
    Use case: f.seek(-1024, 2) se log file ka last 1KB tail karna.

Q4: shutil.copy vs copy2 vs copyfile?
A:  copyfile → sirf content, dest exact file path chahiye.
    copy     → content + permission bits, dest directory bhi ho sakti hai.
    copy2    → copy + timestamps/metadata (cp -p). Backups me copy2.
    Koi bhi owner/ACLs copy nahi karta.

Q5: NamedTemporaryFile ka Windows trap?
A:  delete=True (default) me file open rehte hue Windows pe usi path se
    dusra open() fail hota hai. Cross-platform fix: delete=False, file band
    karo, use karo, phir khud os.unlink(). (3.12+ me delete_on_close=False.)

Q6: Atomic file write kaise karte ho? Kyun?
A:  Same directory me temp file (mkstemp) → write → flush + os.fsync →
    os.replace(tmp, target). os.replace POSIX rename hai = atomic: reader ko
    ya purana complete file milta hai ya naya — kabhi adha-likha nahi.
    Direct open('f','w') me crash = corrupt/empty file.
    os.replace (overwrite, cross-platform) > os.rename (Windows pe fail).

Q7: open() me encoding='utf-8' explicitly kyun likhna?
A:  Default = locale encoding: Linux/Mac utf-8, par WINDOWS cp1252 —
    same code do machines pe alag behave karta hai (DeprecationWarning bhi
    aata hai EncodingWarning ke saath -X warn_default_encoding pe).
    PEP 686: Python 3.15 se utf-8 default. Tab tak explicit likho.

Q8: errors='replace' vs 'ignore' vs 'strict'?
A:  strict (default) → UnicodeDecodeError — pipelines me yahi chahiye (fail fast).
    replace → invalid byte ki jagah � — display/logging ke liye.
    ignore → byte silently drop — DATA LOSS, sirf last resort.
    Asli fix hamesha: source ki SAHI encoding pata karke wahi use karo.

Q9: utf-8-sig kab use karna?
A:  Jab file Excel/Windows Notepad se aayi ho — wo BOM (EF BB BF) prepend
    karte hain. Plain utf-8 se padhoge to '﻿' pehle header/char me ghus
    jaata hai (CSV DictReader me '﻿name' KeyError classic bug).
    utf-8-sig read me BOM strip karta hai, aur BOM ho hi na to bhi safe hai.

Q10: bytes vs str ka boundary rule?
A:  str = Unicode text (program ke andar), bytes = raw data (wire/disk).
    Decode at input boundary, encode at output boundary — core logic ko
    encoding pata hi nahi honi chahiye. Python 2 ka implicit conversion
    hata ke Python 3 ne ye boundary FORCE ki — isliye TypeError milta hai
    bytes+str concat pe.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
