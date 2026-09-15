"""
DAY 54 — Multiprocessing Shared State: Value, Array, Manager, shared_memory
Architecture Level: Mid → Senior Python Backend

WHY THIS MATTERS:
- Processes ka memory ALAG hota hai (alag GIL, alag heap). Threads jaise
  ek variable "automatically share" nahi hota — har process ke paas apni copy.
- Toh agar 4 workers ek hi counter increment karein, ya ek bada array share
  karna ho, toh tumhe EXPLICIT shared-state mechanism chahiye.
- Yeh trap interview me bahut aata hai: "multiprocessing me ek global counter
  increment kiya, value badhi hi nahi" — kyunki har child ne apni copy badhai.

DEKHO BIG PICTURE:
    Threads  → shared memory by default, par GIL race condition (lock chahiye)
    Processes→ NO shared memory by default, IPC chahiye:
               Value/Array      → C-level shared scalars/arrays (fast, fixed type)
               Manager          → arbitrary Python objects (slow, proxy/network)
               shared_memory    → raw bytes buffer (zero-copy, large arrays)
               Queue/Pipe       → message passing (pickle through karta hai)

NOTE: SAARE demos `if __name__ == '__main__'` ke andar hain. macOS/Windows par
default start method 'spawn' hai — child process pura module RE-IMPORT karta hai.
Agar demo code top-level pe hota toh import ke time hi fork ho jaata aur
infinite process bomb / RuntimeError aata. Isliye guard MANDATORY hai.
"""

import multiprocessing as mp
from multiprocessing import shared_memory
import time


# ============ SECTION 1: Value/Array — C-level shared scalars ============
#
# Value(typecode, initial)  → ek shared scalar (ek number)
# Array(typecode, size/seq) → shared fixed-size array
#
# typecode = ctypes type code (array module jaisa):
#   'i' = signed int,  'd' = double,  'f' = float,
#   'l' = long,  'b' = signed char,  'c' = char (bytes)
# Ye actual C variable shared memory me banata hai — pickle nahi, fast.

def increment_NO_lock(counter, n):
    """Race condition demo — WITHOUT lock.

    counter.value += 1 atomic NAHI hai. Ye 3 steps me hota hai:
      1. read counter.value
      2. add 1
      3. write back
    Do process beech me ghus jaate hain → lost updates → final count galat.
    """
    for _ in range(n):
        counter.value += 1   # NON-atomic read-modify-write → race!


def increment_WITH_lock(counter, n):
    """Same kaam, par get_lock() se protect kiya.

    Value/Array ke andar ek built-in lock hota hai → counter.get_lock().
    Uske bina simultaneous writes corrupt ho sakte hain.
    """
    for _ in range(n):
        with counter.get_lock():       # acquire → modify → release (atomic block)
            counter.value += 1


def fill_array(a):
    """Child process target — MODULE LEVEL hona zaroori hai.

    'spawn' start method child me target ko PICKLE karke bhejta hai. Nested/local
    function (function ke andar def) pickle nahi hota → AttributeError. Isliye
    saare process targets top-level rakhe gaye hain.
    """
    for i in range(len(a)):
        a[i] = (i + 1) * 1.5


def demo_value_array():
    print("=" * 55)
    print("SECTION 1: Value / Array — race WITHOUT vs WITH lock")
    print("=" * 55)

    PROCS, PER_PROC = 4, 50_000
    EXPECTED = PROCS * PER_PROC

    # --- WITHOUT lock: race condition, count usually < expected ---
    counter = mp.Value('i', 0)         # shared int, init 0
    procs = [mp.Process(target=increment_NO_lock, args=(counter, PER_PROC))
             for _ in range(PROCS)]
    for p in procs: p.start()
    for p in procs: p.join()
    print(f"WITHOUT lock: expected {EXPECTED}, got {counter.value}  "
          f"(<-- usually LESS, lost updates due to race)")

    # --- WITH lock: always correct ---
    counter = mp.Value('i', 0)
    procs = [mp.Process(target=increment_WITH_lock, args=(counter, PER_PROC))
             for _ in range(PROCS)]
    for p in procs: p.start()
    for p in procs: p.join()
    print(f"WITH get_lock(): expected {EXPECTED}, got {counter.value}  "
          f"(<-- always correct)")

    # --- Array example ---
    arr = mp.Array('d', [0.0, 0.0, 0.0])    # 3 doubles, shared
    p = mp.Process(target=fill_array, args=(arr,))   # module-level target (spawn-safe)
    p.start(); p.join()
    print(f"Shared Array after child wrote: {list(arr)}")
    # WHY useful: fixed-type, fixed-size numeric data → fast, no pickle overhead.


# ============ SECTION 2: Manager — arbitrary Python objects ============
#
# Manager ek SEPARATE server process spin karta hai jo real object hold karta
# hai. Baaki workers ko sirf "proxy" milta hai. Har proxy operation
# (append, __setitem__) ek IPC round-trip hai → pickle + socket → SLOW.
#
# Value/Array sirf C scalars/arrays kar sakte. Manager nested dict, list,
# arbitrary picklable objects share kar sakta hai — par network/IPC cost ke saath.

def manager_worker(shared_dict, shared_list, idx):
    # Har operation manager server se baat karta hai (network overhead)
    shared_dict[idx] = idx * idx
    shared_list.append(idx)
    # NESTED MUTATION TRAP: shared_dict['x'].append(..) DIRECTLY kaam nahi karega
    # kyunki inner list ek normal (non-proxy) object hai jab tak tum
    # manager.list() se nested proxy na banao. Reassign karna padta hai.


def demo_manager():
    print("\n" + "=" * 55)
    print("SECTION 2: Manager — dict/list proxies (IPC overhead)")
    print("=" * 55)

    with mp.Manager() as mgr:
        shared_dict = mgr.dict()          # proxy to dict in manager process
        shared_list = mgr.list()          # proxy to list

        procs = [mp.Process(target=manager_worker, args=(shared_dict, shared_list, i))
                 for i in range(5)]
        for p in procs: p.start()
        for p in procs: p.join()

        print(f"Manager dict: {dict(shared_dict)}")
        print(f"Manager list (sorted): {sorted(shared_list)}")

    print("\nManager vs Value — kab worth it?")
    print("  Value/Array : fast, par sirf C scalars/arrays (int, float, char)")
    print("  Manager     : 10-100x slower per op (pickle+socket), PAR")
    print("                arbitrary/nested Python objects share kar sakta")
    print("  RULE: chhoti dict/list jo kabhi-kabhi update ho → Manager OK.")
    print("        Hot loop me lakhon updates → Manager se BACHO (IPC kills you).")


# ============ SECTION 3: shared_memory (3.8+) — zero-copy raw buffer ============
#
# multiprocessing.shared_memory.SharedMemory ek RAW bytes buffer deta hai jo
# OS-level shared hai. Koi pickle nahi — dono process SAME physical memory
# dekhte hain → ZERO-COPY. Bade arrays (numpy) ke liye game-changer.
#
# Lifecycle (BAHUT IMPORTANT — warna leak):
#   shm = SharedMemory(create=True, size=N)  → creator
#   shm2 = SharedMemory(name=shm.name)       → attacher (dusra process)
#   shm.close()    → is process ka view band (har process karta hai)
#   shm.unlink()   → physical block delete (SIRF EK BAAR, creator karta hai)
#
# resource_tracker WARNING: agar tum unlink bhool jao, Python ka resource_tracker
# exit pe "leaked shared_memory objects" warning deta hai. Yeh by-design hai —
# tumhe explicitly unlink karna chahiye.

def shm_writer(name, n):
    shm = shared_memory.SharedMemory(name=name)   # attach existing
    buf = shm.buf                                  # memoryview into shared block
    for i in range(n):
        buf[i] = i % 256                           # raw byte write, zero-copy
    shm.close()                                    # detach (unlink NAHI — creator karega)


def demo_shared_memory():
    print("\n" + "=" * 55)
    print("SECTION 3: shared_memory — zero-copy raw buffer")
    print("=" * 55)

    N = 16
    shm = shared_memory.SharedMemory(create=True, size=N)   # creator
    try:
        p = mp.Process(target=shm_writer, args=(shm.name, N))
        p.start(); p.join()

        print(f"Shared block name: {shm.name}")
        print(f"Bytes child wrote (zero-copy, no pickle): {bytes(shm.buf[:N])}")
    finally:
        shm.close()       # is process ka view band
        shm.unlink()      # physical block free — RESOURCE LEAK warna!

    # --- NUMPY ZERO-COPY pattern (commented — numpy optional) ---
    # import numpy as np
    # shm = shared_memory.SharedMemory(create=True, size=arr.nbytes)
    # view = np.ndarray(arr.shape, dtype=arr.dtype, buffer=shm.buf)
    # view[:] = arr[:]                 # copy data INTO shared block ONCE
    # # child process: attach by name, wrap same buffer in np.ndarray → SAME memory
    # # 1 GB array bhi pickle-through-Queue (serialize+copy) ke bina share hota.
    #
    # PICKLE-THROUGH-QUEUE ka cost:
    #   q.put(big_array)  → pickle (CPU) + copy bytes into pipe + unpickle in child
    #   1 GB array  → ~seconds + 2x memory (sender copy + receiver copy)
    #   shared_memory→ ek baar likho, dono read karein → MB/s nahi, pointer share.

    print("\nWHY zero-copy matters:")
    print("  Queue.put(big_arr) = pickle + copy + unpickle (2x RAM, slow)")
    print("  shared_memory      = ek hi physical block, no serialize → bade")
    print("                       numeric arrays (ML batches, frames) ke liye best")


# ============ SECTION 4: Decision Table — kab kya use karein ============

def decision_table():
    print("\n" + "=" * 55)
    print("SECTION 4: IPC Decision Table — kab kya?")
    print("=" * 55)
    table = """
    ┌──────────────────┬───────────────────────────────────────────────────┐
    │ Mechanism        │ Kab use karein (use case)                         │
    ├──────────────────┼───────────────────────────────────────────────────┤
    │ Queue            │ Producer/consumer, kaam baant-na (task → worker). │
    │                  │ Many→one ya one→many. Pickle karta hai. Thread-   │
    │                  │ /process-safe by default. DEFAULT choice for jobs.│
    ├──────────────────┼───────────────────────────────────────────────────┤
    │ Pipe             │ Sirf 2 endpoints ke beech (one-to-one). Queue se  │
    │                  │ thoda fast, par no built-in locking → 2+ writers  │
    │                  │ corrupt kar sakte. Bidirectional duplex channel.  │
    ├──────────────────┼───────────────────────────────────────────────────┤
    │ Value / Array    │ Chhota fixed-type numeric shared state (counter,  │
    │                  │ flag, fixed array). Fast, C-level. get_lock()     │
    │                  │ se race se bacho. NO arbitrary objects.           │
    ├──────────────────┼───────────────────────────────────────────────────┤
    │ Manager          │ Arbitrary/nested Python objects (dict of lists,   │
    │                  │ custom classes). Convenient PAR slow (IPC/proxy   │
    │                  │ per op). Low-frequency shared config/state ke liye.│
    ├──────────────────┼───────────────────────────────────────────────────┤
    │ shared_memory    │ Bade numeric buffers (numpy arrays, image frames),│
    │                  │ zero-copy. Manual lifecycle (close+unlink).       │
    │                  │ Tum khud serialization/layout manage karte ho.    │
    └──────────────────┴───────────────────────────────────────────────────┘

    THUMB RULE:
      "Message bhejna hai?"          → Queue (default), Pipe (2 peer)
      "Ek chhota number/flag share?" → Value (+ get_lock())
      "Random nested object share?"  → Manager (rare updates only)
      "Gigabyte array share fast?"   → shared_memory (zero-copy)
    """
    print(table)


# ============ INTERVIEW QUESTIONS ============
"""
Q1: multiprocessing me ek global counter increment kiya, value badhi hi nahi —
    kyun?
A : Har child process ko parent ka memory ka COPY milta hai (spawn/fork).
    Child ne apni copy badhai, parent ki global untouched. Cross-process share
    ke liye mp.Value/Array, Manager, ya shared_memory chahiye — plain global nahi.

Q2: Value('i', 0) thread/process-safe hai? counter.value += 1 atomic hai?
A : NAHI. += read-modify-write 3 steps me hota hai → race condition. Value ke
    andar lock hota hai par += use nahi karta. Manually `with counter.get_lock():`
    karo, ya RawValue (lock-less) avoid karo jab tak khud sync na manage karo.

Q3: Manager dict aur Value me performance difference kya hai?
A : Manager ek alag server process me object rakhta hai; har operation pickle +
    socket round-trip hai (10-100x slower). Value/Array same-host shared C memory,
    no pickle. Manager → flexibility (arbitrary objects), Value → speed (scalars).

Q4: 2 GB numpy array ko 4 workers me bina copy kiye kaise share karein?
A : shared_memory.SharedMemory(create=True, size=arr.nbytes) banao, np.ndarray ko
    us buffer pe wrap karke data ek baar likho, workers ko sirf shm.name pass karo;
    wo attach karke same buffer pe ndarray banate hain → zero-copy. Queue se bhejne
    par pickle + double RAM lagega.

Q5: shared_memory ke saath "leaked shared_memory objects" warning kyun aati hai?
A : Tumne unlink() nahi kiya. close() sirf is process ka view band karta hai;
    physical block delete karne ke liye creator ko EK BAAR unlink() call karna
    padta hai. Na karne par resource_tracker exit pe warn karta hai (real leak).

Q6: __name__ == '__main__' guard kyun mandatory hai multiprocessing me?
A : 'spawn' start method (macOS/Windows default) par child pura module re-import
    karta hai. Guard ke bina top-level process-spawn code import ke time chal jaayega
    → recursive process creation / RuntimeError. Guard ensures sirf parent spawn kare.

Q7: Queue vs Pipe — kab Pipe choose karein?
A : Pipe jab sirf 2 endpoints ho (one-to-one) aur thodi extra speed chahiye. Par
    Pipe me built-in locking nahi — 2+ writers/readers data corrupt kar sakte.
    Queue me locking built-in + many-to-many → general purpose default Queue hi rakho.
"""


if __name__ == '__main__':
    # spawn explicit set kar diya taaki har OS pe consistent behaviour mile.
    mp.set_start_method('spawn', force=True)
    demo_value_array()
    demo_manager()
    demo_shared_memory()
    decision_table()
