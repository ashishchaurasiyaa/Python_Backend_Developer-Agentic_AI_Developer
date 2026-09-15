"""
DAY 55 — mmap, memoryview & Buffer Protocol: Zero-Copy Memory in Python
Architecture Level: Mid → Senior Python Backend

WHY THIS MATTERS:
- Backend ka sabse bada hidden cost: COPYING bytes. File → kernel buffer →
  Python bytes → slice (ek aur copy) → socket buffer... har step RAM+CPU khata hai.
- mmap      : file ko VIRTUAL MEMORY me map karo. 10 GB file "kholo" bina 10 GB
              RAM ke — OS sirf touched pages load karta hai (demand paging).
- memoryview: kisi bhi buffer (bytes/bytearray/array/mmap) ke andar ZERO-COPY
              window. Slice karo, data copy nahi — sirf pointer+offset+length.
- Buffer Protocol: C-level contract jo yeh sab possible banata hai — jo object
  ise support kare, uski raw memory koi aur object BINA COPY ke access kar sakta.

BIG PICTURE:
    bytes slice b[a:b]        → NEW object, data COPY hota hai
    memoryview(b)[a:b]        → NO copy, same memory ka window
    f.read() = pura file RAM me | mmap = pages on-demand, virtual memory
    memoryview(mmap_obj)      → file ke upar zero-copy window (best of both)

REAL BACKEND USES:
- Bade log files me search (grep-like) bina pura load kiye → mmap.find()
- N worker processes, same reference data                  → mmap (page cache SHARED)
- Socket receive bina naye objects banaye                  → recv_into(memoryview)
- nginx/kafka "zero-copy file serving" (sendfile)          → same idea, kernel level
"""

import mmap
import os
import struct
import sys
import time
import tempfile
import multiprocessing as mp


# ============ SECTION 1: mmap basics — file ko memory jaisa treat karo ============
#
# mmap.mmap(fileno, length) → file ka content ek mutable byte-buffer jaisa dikhta
# hai. length=0 ka matlab "poora file". OS demand paging karta hai:
#   - mm[5_000_000_000] access kiya → OS sirf WOH 4 KB page disk se laata hai
#   - f.read() hota toh POORA file RAM me aata
#
# TRAP: EMPTY file ko mmap nahi kar sakte → ValueError("cannot mmap an empty file")
# TRAP: mm[a:b] slice BYTES return karta hai → yeh COPY hai! Zero-copy ke liye
#       memoryview(mm) use karo (Section 7).

def demo_mmap_basics():
    print("=" * 60)
    print("SECTION 1: mmap basics — read/write/slice/find")
    print("=" * 60)

    # Temp file banao demo ke liye (pretend: ek bada log file)
    path = os.path.join(tempfile.gettempdir(), "day55_demo.log")
    with open(path, "wb") as f:
        f.write(b"2026-06-12 INFO  app started\n")
        f.write(b"2026-06-12 ERROR db timeout after 30s\n")
        f.write(b"2026-06-12 INFO  retrying connection\n")

    with open(path, "r+b") as f:                      # r+b → read & write dono
        mm = mmap.mmap(f.fileno(), 0)                 # 0 = map poora file

        # --- bytes jaisa READ access ---
        print(f"len(mm)        : {len(mm)} bytes (file size)")
        print(f"mm[:10]        : {mm[:10]}  (slice -> bytes COPY)")
        print(f"mm[11:16]      : {mm[11:16]}")

        # --- find(): C-speed substring search, koi Python loop nahi ---
        idx = mm.find(b"ERROR")
        print(f"mm.find(b'ERROR') -> offset {idx}")
        line_end = mm.find(b"\n", idx)
        print(f"ERROR line     : {mm[idx:line_end]}")

        # --- WRITE through mmap: file me directly change ---
        mm[idx:idx + 5] = b"FATAL"                    # in-place edit, same length!
        mm.flush()                                    # dirty pages ko disk pe force
        # TRAP: replacement ka length SAME hona chahiye — mmap insert/delete
        # nahi kar sakta, sirf overwrite. (File ek fixed-size buffer hai.)
        mm.close()

    with open(path, "rb") as f:                       # prove: change file me gaya
        print(f"File after edit: {f.read().splitlines()[1]}")

    os.remove(path)


# ============ SECTION 2: mmap resize + access modes ============
#
# Access modes:
#   ACCESS_READ  → read-only view (write karoge to TypeError)
#   ACCESS_WRITE → writes file me jaate hain (default behaviour w/ r+b)
#   ACCESS_COPY  → copy-on-write: writes sirf MEMORY me, file untouched
#                  (config file ko "patch in memory" karna ho without saving)
#
# resize(): Linux pe mremap() syscall se hota hai. macOS/BSD me mremap NAHI
# hai → SystemError aata hai. Portable pattern: close → ftruncate → re-mmap.

def demo_mmap_resize_modes():
    print("\n" + "=" * 60)
    print("SECTION 2: mmap resize + ACCESS_COPY mode")
    print("=" * 60)

    path = os.path.join(tempfile.gettempdir(), "day55_resize.bin")
    with open(path, "wb") as f:
        f.write(b"A" * 16)

    # --- ACCESS_COPY: memory me likho, file safe rahe ---
    with open(path, "r+b") as f:
        mm = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_COPY)
        mm[0:4] = b"ZZZZ"                             # sirf is process ki memory me
        print(f"ACCESS_COPY view me : {mm[:8]}")
        mm.close()
    with open(path, "rb") as f:
        print(f"File abhi bhi       : {f.read()[:8]}  (untouched!)")

    # --- resize: platform-dependent (Linux OK, macOS SystemError) ---
    with open(path, "r+b") as f:
        mm = mmap.mmap(f.fileno(), 0)
        try:
            mm.resize(32)                             # Linux: mremap, grows file
            print(f"resize(32) worked   : new len = {len(mm)}")
        except (SystemError, ValueError, OSError) as e:
            # macOS/BSD: no mremap → portable fallback
            print(f"resize() failed ({type(e).__name__}) -> portable fallback:")
            mm.close()
            f.truncate(32)                            # file ko OS level pe grow karo
            mm = mmap.mmap(f.fileno(), 0)             # re-map fresh
            print(f"ftruncate+remap     : new len = {len(mm)}")
        mm.close()

    os.remove(path)


# ============ SECTION 3: mmap as IPC — do process, ek file, shared pages ============
#
# Jab 2 processes SAME file ko mmap karte hain, OS dono ko SAME physical page
# cache pages deta hai. Ek likhe, dusra dekhe — classic shared-memory IPC.
# (multiprocessing.shared_memory andar se yahi /dev/shm mmap karta hai.)
# Backend angle: gunicorn ke 8 workers ek hi 2 GB model file mmap karein →
# RAM me EK copy (shared page cache), 8 nahi. f.read() hota toh 16 GB.

def mmap_ipc_child(path, size):
    """Child process target — module level (spawn pickle karta hai isko)."""
    with open(path, "r+b") as f:
        mm = mmap.mmap(f.fileno(), size)
        mm[0:5] = b"CHILD"                            # child shared pages me likhta hai
        mm.flush()
        mm.close()


def demo_mmap_ipc():
    print("\n" + "=" * 60)
    print("SECTION 3: mmap as IPC — child writes, parent sees")
    print("=" * 60)

    path = os.path.join(tempfile.gettempdir(), "day55_ipc.bin")
    SIZE = 16
    with open(path, "wb") as f:
        f.write(b"\x00" * SIZE)                       # file pre-size karna zaroori

    with open(path, "r+b") as f:
        mm = mmap.mmap(f.fileno(), SIZE)
        print(f"Parent BEFORE child : {bytes(mm[:5])}")

        p = mp.Process(target=mmap_ipc_child, args=(path, SIZE))
        p.start(); p.join()

        print(f"Parent AFTER child  : {bytes(mm[:5])}  (no pickle, no Queue!)")
        mm.close()
    os.remove(path)


# ============ SECTION 4: mmap vs normal read() — decision table ============

def decision_table_mmap():
    print("\n" + "=" * 60)
    print("SECTION 4: mmap vs read() — kab kya?")
    print("=" * 60)
    table = """
    ┌─────────────────────────────────┬──────────────────────────────────────┐
    │ Situation                       │ Kya use karein + kyun                │
    ├─────────────────────────────────┼──────────────────────────────────────┤
    │ Chhota file, ek baar poora      │ f.read() — simple, mmap ka setup     │
    │ padhna (config, template)       │ overhead worth nahi                  │
    ├─────────────────────────────────┼──────────────────────────────────────┤
    │ BADA file, RANDOM access        │ mmap — sirf touched pages load,      │
    │ (index lookup, binary search)   │ seek+read ka dance nahi              │
    ├─────────────────────────────────┼──────────────────────────────────────┤
    │ File > RAM (50 GB log search)   │ mmap — OS pages in/out karta hai;    │
    │                                 │ read() me MemoryError                │
    ├─────────────────────────────────┼──────────────────────────────────────┤
    │ N workers, same reference data  │ mmap — page cache SHARED, RAM me     │
    │ (ML model, geoip db)            │ 1 copy; read() me N copies           │
    ├─────────────────────────────────┼──────────────────────────────────────┤
    │ Sequential stream (ETL pipe,    │ chunked read()/readinto() — mmap ka  │
    │ network socket)                 │ random-access advantage useless      │
    ├─────────────────────────────────┼──────────────────────────────────────┤
    │ Substring search in huge file   │ mmap.find() — C speed, na chunking   │
    │ ("kaunse offset pe ERROR hai?") │ na match-split-across-chunks bug     │
    └─────────────────────────────────┴──────────────────────────────────────┘

    ZERO-COPY FILE SERVING concept (interview favourite):
      Normal serve : disk → kernel buf → COPY user space → COPY socket buf
      sendfile/mmap: kernel page cache se SEEDHA socket — user-space copy gayab.
      Python me socket.sendfile(f) yahi hai; nginx static files isi se fast hai.
    """
    print(table)


# ============ SECTION 5: Buffer Protocol + memoryview — zero-copy PROOF ============
#
# BUFFER PROTOCOL = C-API contract: "mere paas contiguous memory hai, lo pointer,
# khud padho/likho — copy mat karo." Providers: bytes, bytearray, array.array,
# mmap, numpy.ndarray, ctypes buffers. memoryview = us pointer ka safe wrapper:
#   mv = memoryview(obj) → view (obj zinda rahega jab tak view zinda hai)
#   mv[a:b]              → NAYA view, SAME memory — NO COPY
#   bytes(mv)            → ab COPY hoti hai (explicitly, jab chahiye tab)

def demo_memoryview_zero_copy():
    print("\n" + "=" * 60)
    print("SECTION 5: memoryview — slicing WITHOUT copy (proof)")
    print("=" * 60)

    MB = 1024 * 1024
    big = b"x" * (50 * MB)                            # 50 MB bytes object

    # --- PROOF 1: sys.getsizeof ---
    t0 = time.perf_counter()
    bytes_slice = big[1:]                             # bytes slicing → 50 MB COPY
    t_bytes = time.perf_counter() - t0

    mv = memoryview(big)
    t0 = time.perf_counter()
    mv_slice = mv[1:]                                 # view slicing → ~200 byte object
    t_mv = time.perf_counter() - t0

    print(f"getsizeof(big)         : {sys.getsizeof(big):>12,} bytes")
    print(f"getsizeof(big[1:])     : {sys.getsizeof(bytes_slice):>12,} bytes  <- FULL COPY")
    print(f"getsizeof(mv[1:])      : {sys.getsizeof(mv_slice):>12,} bytes  <- sirf pointer+offset")
    print(f"bytes slice time       : {t_bytes*1000:8.3f} ms")
    print(f"memoryview slice time  : {t_mv*1000:8.3f} ms  (size-independent, O(1))")

    # --- PROOF 2: id() — view ka .obj wahi original object hai ---
    print(f"id(big)                : {id(big)}")
    print(f"id(mv_slice.obj)       : {id(mv_slice.obj)}  <- SAME object, no copy")

    # --- bytes(mv) vs mv[:] ka difference ---
    sub = mv[:5]                                      # view (no copy)
    copied = bytes(sub)                               # ab explicit COPY bani
    print(f"mv[:5] type            : {type(sub).__name__} (view)")
    print(f"bytes(mv[:5])          : {copied} -> type {type(copied).__name__} (COPY)")

    # --- Mutable buffer pe view = WRITE THROUGH ---
    ba = bytearray(b"hello world")
    w = memoryview(ba)
    w[0:5] = b"HELLO"                                 # view ke through original badla
    print(f"write-through          : {ba}  (bytearray badla via view)")
    # TRAP: bytes IMMUTABLE hai → memoryview(bytes_obj) READONLY view deta hai;
    # w[0]=65 karne par TypeError. Mutation chahiye toh bytearray/mmap pe view lo.

    # TRAP: jab tak koi memoryview zinda hai, bytearray resize NAHI ho sakta:
    try:
        ba.append(33)                                 # view exported → resize blocked
    except BufferError as e:
        print(f"BufferError trap       : {e}")
    w.release()                                       # view chhodo → ab resize OK
    ba.append(33)
    print(f"release() ke baad      : append chala -> {ba}")


# ============ SECTION 6: cast(), struct on views, readinto/recv_into ============
#
# Yeh "binary protocol parsing" ka senior toolkit hai:
#   mv.cast('I')              → same bytes ko uint32 array ki tarah dekho
#   struct.unpack_from(f, mv) → view ke offset se fields nikaalo, NO slicing copy
#   f.readinto(buf)           → file data EXISTING buffer me, naya object nahi
#   sock.recv_into(mv)        → network data directly buffer me (hot path pattern)

def demo_cast_struct_readinto():
    print("\n" + "=" * 60)
    print("SECTION 6: cast() + struct + readinto — binary parsing zero-copy")
    print("=" * 60)

    # --- cast(): bytes ko typed array ki tarah dekho ---
    ba = bytearray(struct.pack("=4I", 10, 20, 30, 40))   # 4 native uint32 = 16 bytes
    ints = memoryview(ba).cast("I")                       # ab indexing int deta hai
    print(f"raw bytes              : {bytes(ba)}")
    print(f"cast('I') view         : {ints.tolist()}  (itemsize={ints.itemsize})")
    ints[0] = 999                                         # int likho → bytes badle!
    print(f"ints[0]=999 ke baad    : {bytes(ba[:4])}  <- same memory, typed write")
    ints.release()

    # --- struct.unpack_from on a view: header parsing without slice copies ---
    # Format: [magic 4s][version H][payload_len I] — typical binary protocol header
    packet = bytearray(struct.pack("=4sHI", b"PKT1", 2, 5) + b"hello")
    mv = memoryview(packet)
    magic, version, plen = struct.unpack_from("=4sHI", mv, 0)
    header_size = struct.calcsize("=4sHI")
    payload = mv[header_size:header_size + plen]          # view, NO copy
    print(f"parsed header          : magic={magic}, v={version}, len={plen}")
    print(f"payload (view)         : {bytes(payload)}")
    payload.release(); mv.release()

    # --- readinto(): file → pre-allocated buffer (object churn zero) ---
    path = os.path.join(tempfile.gettempdir(), "day55_readinto.bin")
    with open(path, "wb") as f:
        f.write(b"0123456789" * 10)

    buf = bytearray(64)                                   # EK baar allocate
    with open(path, "rb") as f:
        n = f.readinto(memoryview(buf))                   # data buffer ME aaya
        # f.read(64) hota toh: naya 64-byte bytes object HAR call pe banta.
        # Hot loop (lakhs of reads) me readinto GC pressure khatam kar deta hai.
        print(f"readinto filled        : {n} bytes -> {bytes(buf[:12])}...")
        # Partial fill bhi clean: memoryview(buf)[n:] me agla chunk daal sakte ho.
    os.remove(path)

    # --- recv_into pattern (socket hot-path ka shape yahi hota hai) ---
    # buf = bytearray(65536); view = memoryview(buf); pos = 0
    # while pos < msg_len:
    #     pos += sock.recv_into(view[pos:])  # kernel SEEDHA buf me, no new objects
    # asyncio/uvloop internals me yahi pattern hai. numpy.frombuffer(buf) bhi
    # isi protocol se SAME memory pe array banata hai — zero-copy NumPy.


# ============ SECTION 7: bytes += O(n²) vs bytearray — accumulation benchmark ============
#
# CLASSIC interview trap: loop me `data += chunk` (bytes) QUADRATIC hai —
# bytes immutable → har += pe naya object + full memcpy → 1+2+...+n = O(n²).
# bytearray mutable + overallocation (list jaisa) → amortized O(1) append.

def demo_accumulation_benchmark():
    print("\n" + "=" * 60)
    print("SECTION 7: bytes += (O(n²)) vs bytearray (O(n))")
    print("=" * 60)

    CHUNK, N = b"x" * 100, 10_000                     # 10k chunks of 100 B = ~1 MB

    t0 = time.perf_counter()
    acc_bytes = b""
    for _ in range(N):
        acc_bytes += CHUNK                            # har baar FULL copy → O(n²)
    t_bytes = time.perf_counter() - t0

    t0 = time.perf_counter()
    acc_ba = bytearray()
    for _ in range(N):
        acc_ba += CHUNK                               # in-place extend → amortized O(1)
    t_ba = time.perf_counter() - t0

    t0 = time.perf_counter()
    pre = bytearray(N * len(CHUNK))                   # size pata hai → pre-allocate
    view = memoryview(pre)
    pos = 0
    for _ in range(N):
        view[pos:pos + len(CHUNK)] = CHUNK            # seedha slot me likho, 0 realloc
        pos += len(CHUNK)
    view.release()
    t_view = time.perf_counter() - t0

    print(f"bytes  +=              : {t_bytes*1000:9.2f} ms   (quadratic copies)")
    print(f"bytearray +=           : {t_ba*1000:9.2f} ms   ({t_bytes/t_ba:6.1f}x faster)")
    print(f"prealloc + memoryview  : {t_view*1000:9.2f} ms   (zero realloc, hot-path king)")
    print("NOTE: b''.join(chunks_list) bhi O(n) hai — readable default wahi rakho;")
    print("      prealloc+view tab jab size pehle se pata ho (fixed protocol frames).")


# ============ SECTION 8: THE CONNECTION — memoryview(mmap) zero-copy ============
#
# mmap object KHUD buffer protocol support karta hai → memoryview(mm) = DISK
# FILE ke pages ke upar direct zero-copy window! mm[a:b] bytes-COPY deta hai,
# par memoryview(mm)[a:b] nahi — file → page cache → struct.unpack, copies = 0.

def demo_memoryview_on_mmap():
    print("\n" + "=" * 60)
    print("SECTION 8: memoryview(mmap) — file ke upar zero-copy window")
    print("=" * 60)

    # Binary "records file" banao: har record = (=I id, =d score) = 12 bytes
    path = os.path.join(tempfile.gettempdir(), "day55_records.bin")
    REC = "=Id"
    REC_SIZE = struct.calcsize(REC)
    with open(path, "wb") as f:
        for i in range(1000):
            f.write(struct.pack(REC, i, i * 1.5))

    with open(path, "r+b") as f:
        mm = mmap.mmap(f.fileno(), 0)
        mv = memoryview(mm)                           # mmap → buffer protocol → view!

        # Random record access: O(1) seek, ZERO copies, file kabhi pura load nahi hua
        for rec_no in (0, 500, 999):
            rid, score = struct.unpack_from(REC, mv, rec_no * REC_SIZE)
            print(f"record[{rec_no:>3}] (direct from disk pages): id={rid}, score={score}")

        # Slice comparison: mm[a:b] vs memoryview(mm)[a:b]
        s1 = mm[0:REC_SIZE]                           # bytes -> COPY hui
        s2 = mv[0:REC_SIZE]                           # memoryview -> NO copy
        print(f"mm[0:12]  type         : {type(s1).__name__}  (copy)")
        print(f"mv[0:12]  type         : {type(s2).__name__}  (zero-copy, disk-backed)")

        # Write through view → seedha file ke page me
        struct.pack_into(REC, mv, 0, 777, 99.9)
        mm.flush()
        s2.release()

        # TRAP: views release kiye BINA mm.close() → BufferError
        try:
            mm.close()                                # mv abhi bhi zinda hai!
        except BufferError as e:
            print(f"BufferError trap       : {e}")
        mv.release()                                  # pehle saare views chhodo
        mm.close()                                    # ab close clean hai

    with open(path, "rb") as f:                       # prove write disk tak gaya
        rid, score = struct.unpack(REC, f.read(REC_SIZE))
        print(f"file me record[0]      : id={rid}, score={score}  (write persisted)")
    os.remove(path)

    print("\nFULL PICTURE (yehi senior answer hai):")
    print("  buffer protocol = contract |  bytes/bytearray/array/mmap = providers")
    print("  memoryview      = universal zero-copy lens un sab ke upar")
    print("  mmap            = disk file ko bhi usi contract me le aata hai")
    print("  => struct/numpy/socket sab EK HI memory pe kaam karte hain, copies = 0")


# ============ INTERVIEW QUESTIONS ============
"""
Q1: mmap kya hai aur f.read() se kab better hai?
A : mmap file ko process ke virtual address space me map karta hai — OS demand
    paging se sirf touched 4 KB pages load karta hai. Better jab: file bada/RAM
    se bada ho, access random ho (binary search/index), ya multiple processes
    same file padhein (page cache SHARED → 1 copy). Chhota sequential → read().

Q2: Do gunicorn workers ek hi 2 GB model file mmap karein toh RAM kitni lagegi?
A : ~2 GB total, ~4 GB nahi. mmap pages OS page cache se aate hain jo processes
    ke beech SHARED hote hain (read-only mapping). f.read() karte toh har worker
    ki apni private 2 GB copy hoti. Yahi mmap ka multi-process superpower hai.

Q3: Buffer protocol kya hai? Kaun implement karta hai?
A : C-level contract jisse object apni contiguous memory ka pointer (+ shape/
    itemsize metadata) doosre code ko de sakta hai BINA copy ke. Implementers:
    bytes, bytearray, array.array, mmap, numpy.ndarray, ctypes. memoryview iska
    Python-side consumer hai; frombuffer/recv_into/readinto sab isi pe chalte hain.

Q4: memoryview slice aur bytes slice me kya difference hai? Proof kaise doge?
A : big[1:] POORA data copy karta hai (50 MB slice = 50 MB naya RAM, O(n)).
    memoryview(big)[1:] ~200-byte view banata hai — same memory, O(1). Proof:
    sys.getsizeof compare karo + mv.obj ka id() original se match karta hai.
    Copy chahiye toh explicitly bytes(mv) karo.

Q5: Loop me data += chunk (bytes) O(n²) kyun hai? Fix kya hai?
A : bytes immutable hai — har += pe (purana + naya) size ka NAYA object allocate
    hota hai aur pura data memcpy hota hai. n chunks me 1+2+...+n = O(n²) bytes
    move hote hain. Fix: (1) bytearray += (mutable, overallocation → amortized
    O(1)), (2) b''.join(list_of_chunks), ya (3) size pata ho toh pre-allocated
    bytearray + memoryview slices me seedha likho (zero realloc, hot path best).

Q6: recv_into / readinto kab use karoge plain recv/read ki jagah?
A : Hot loops me (lakhs of reads). recv(n) HAR call pe naya bytes object banata
    hai → allocation + GC churn. recv_into(memoryview(buf)[pos:]) data EXISTING
    buffer me daalta hai — zero new objects, partial reads bhi offset slide se clean.

Q7: bytearray pe memoryview liya, phir ba.append() kiya — BufferError kyun?
A : Jab tak view "exported" hai, bytearray buffer realloc/move nahi kar sakta
    (view ka pointer dangle ho jaata) → resize ops blocked. Fix: mv.release()
    (ya `with memoryview(ba) as mv:`). Same reason se views release kiye bina
    mmap.close() bhi BufferError deta hai.

Q8: mm[0:100] aur memoryview(mm)[0:100] me kya farak hai?
A : mm[0:100] bytes object return karta hai — yeh page-cache se user-space me
    COPY hai. memoryview(mm)[0:100] zero-copy view hai seedha mapped pages pe —
    struct.unpack_from/pack_into isi pe chal sakte hain bina ek bhi copy ke.
    Bade files pe per-record parsing me yeh farak measurable hota hai.

Q9: mmap.resize() production code me directly kyun nahi use karte?
A : Platform-dependent — Linux pe mremap() se chalta hai, macOS/BSD me mremap
    nahi → SystemError. Portable: mm.close() → f.truncate(new) → fresh mmap.
    Aur: empty file mmap nahi hota (ValueError) → pehle pre-size karna padta hai.

Q10: "Zero-copy file serving" kya hota hai (nginx/kafka context)?
A : Normal path: disk → kernel buf → COPY user space → COPY socket buf (2 extra
    copies + context switches). Zero-copy (sendfile syscall): page cache se data
    SEEDHA socket pe — user space me aata hi nahi. Python me socket.sendfile(f)
    yahi hai. mmap same family ka idea: file pages address karo, middlemen hatao.
"""


if __name__ == "__main__":
    # mmap IPC demo me child process hai → guard mandatory (spawn pe child
    # module re-import karta hai; guard ke bina demos recursively chalte).
    mp.set_start_method("spawn", force=True)
    demo_mmap_basics()
    demo_mmap_resize_modes()
    demo_mmap_ipc()
    decision_table_mmap()
    demo_memoryview_zero_copy()
    demo_cast_struct_readinto()
    demo_accumulation_benchmark()
    demo_memoryview_on_mmap()
