# OS Concepts — Recap Q&A (Interview Deep Dive)

> Self-test recap of [02_os_concepts.md](02_os_concepts.md). Format: question → correct answer → deep dive → live proof (with real numbers from this machine) where applicable.

---

## Q1. Process vs Thread — memory sharing + GIL (CPU-bound vs I/O-bound)

**Memory layout:**
```
          PROCESS
     ┌─────────────────┐
     │ Code            │ ← Shared across threads
     │ Global/Static   │ ← Shared across threads
     │ Heap            │ ← Shared across threads
     │                 │
     │ Thread 1 Stack  │ ← Private
     │ Thread 2 Stack  │ ← Private
     │ Thread 3 Stack  │ ← Private
     └─────────────────┘
```
Each **process** gets its own separate virtual address space. **Threads** within a process share code/globals/heap, but each has its own private stack (and its own register/PC state at any instant).

### GIL (Global Interpreter Lock) — Teacher's Analogy

Ek office mein 8 employees (= 8 threads), lekin **ek hi washroom, ek hi chaabi** (= GIL). Chaahe 8 alag desks (cores) ho, sirf jiske paas chaabi hai wo hi "andar" (executing bytecode) hai — baaki line mein khade hain.

- **CPU-bound kaam** (apne desk pe calculation) → washroom chaahiye hi nahi, par agar chaabi ka wait karna pade to sab slow ho jaate hain — **8 desks ka koi fayda nahi**.
- **I/O-bound kaam** (courier ka wait) → wait karte waqt chaabi kisi aur ko de sakte ho — **yahan real parallelism ka fayda milta hai**.
- **Multiprocessing** = har employee ko apna alag office hi de do — koi line nahi, sab sach mein parallel. Cost: naya office banana (process spawn) mehenga, aur seedha baat nahi kar sakte (separate memory, IPC chahiye).

**GIL release mechanism (modern, Python 3.2+):** Time-based, not instruction-count-based. `sys.getswitchinterval()` = **5ms** default — every 5ms the interpreter forces the current thread to release the GIL. Even so, **only one thread executes Python bytecode at any instant**, regardless of core count.

**Escape hatch:** C extensions (NumPy, hashlib, zlib, most I/O) explicitly release the GIL around their C-level compute (`Py_BEGIN_ALLOW_THREADS`), so those specific calls *can* run in true parallel across threads even in CPython.

### Live Proof — CPU-bound (see [gil_cpu_bound_demo.py](gil_cpu_bound_demo.py))

Task: pure-Python loop computing `sum(i*i for i in range(20_000_000))`, run twice.

```
Sequential (1 thread, 2x work): 1.90s
Threading  (2 threads, GIL):    1.81s   <- ~same as sequential, GIL blocked real parallelism
Multiproc  (2 processes):       1.01s   <- ~half — real 2-core parallelism (separate GIL per process)
```

### Live Proof — I/O-bound (see [gil_io_bound_demo.py](gil_io_bound_demo.py))

Task: `time.sleep(1.5)` (simulates network/DB/file wait) x2.

```
Sequential (2x 1.5s wait, one after another): 3.01s
Threading  (2 threads, I/O-bound):            1.51s   <- ~half! GIL released during sleep, both wait in parallel
Multiproc  (2 processes, I/O-bound):          1.61s   <- same speed, but paid unnecessary process-spawn overhead
```

**Golden rule:** I/O-bound → threading (or asyncio, even cheaper). CPU-bound → multiprocessing.

---

## Q2. Virtual Memory — why it exists, page faults

**Reason 1 — Process isolation/security:** Every process gets its own virtual address space. Process A accessing `0x2000` never touches Process B's physical memory at that same virtual address — the MMU/page tables map each process's virtual addresses to different physical frames. Benefit: isolation, security, stability (one process can't corrupt another's memory).

**Reason 2 — Flexible/larger address space:** A process doesn't need a contiguous block of physical RAM. Virtual pages 0,1,2,3 can map to scattered physical frames (17, 4, 91, 22) — and a program can be given a virtual address space larger than physical RAM, with the OS backing the excess via disk (swap).

**Page fault:** CPU accesses a virtual page whose mapping/data isn't currently valid/resident → traps into the kernel's page fault handler. Not automatically an error — the OS can usually resolve it.

| | Minor Page Fault | Major Page Fault |
|---|---|---|
| Disk I/O needed? | No | Yes |
| Cost | Cheap | Expensive |
| Common cause | Mapping fix-up only — page already in memory somewhere, just needs a page-table entry (e.g. **copy-on-write**, lazy `mmap` first-touch) | Page must be pulled from disk/swap into RAM |

### Deep Dive — Copy-on-Write (COW) after `fork()`

**Analogy:** Shared textbook, personal notes. Parent and child initially share the exact same physical pages (marked **read-only**) after `fork()` — no copying happens at fork time, it's instant. The moment **either one writes**, the CPU detects "this page is read-only" → **minor page fault** → kernel copies **just that one page** for the writer. Pages never written stay shared forever.

**Why this matters:** `fork()` is cheap even for multi-GB processes, because nothing is actually duplicated upfront — only page-table entries are shared.

### Live Proof (see [cow_fork_demo.py](cow_fork_demo.py))

Parent allocates + fully touches a 50MB buffer, then `fork()`s a child that first checks minor-fault count (no write yet), then writes to every page and checks again.

```
[CHILD] minor faults right after fork (no write yet): 136
[CHILD] minor faults AFTER writing to every page:      3376
[CHILD] extra faults caused by COW writes:             3240
```

**Interpretation:**
- Only 136 faults right after fork → confirms **no copying at fork time**, pages are shared.
- 3240 extra faults after writing to the whole 50MB buffer. Expected ~12,800 assuming 4KB pages (`50MB / 4KB`) — but got 3240.
- `50MB / 3240 ≈ 16KB` per fault — revealed this Mac (Apple Silicon) uses a **16KB page size**, not the traditional 4KB. Confirmed independently:
  ```bash
  $ getconf PAGESIZE
  16384
  ```
  **Real-world implication:** the same demo on a typical Linux x86 cloud server (4KB pages) would show ~4x more minor faults for an identical buffer size — worth remembering when comparing memory behavior between a Mac dev machine and a Linux prod server.

### Virtual Memory vs cgroup limit — don't conflate

Virtual memory is the OS addressing mechanism (every process has it). A cgroup memory limit is a resource **ceiling** layered on top ("this container may not exceed X MB **resident**"). A process can have a huge virtual address space (e.g. from `mmap`-ing a large file) while its actual RSS stays small — don't read a large VSZ as "will OOM soon." Check RSS against the cgroup limit, not VSZ.

---

## Q3. File Descriptors + `ulimit -n`

**FD = an integer handle** a process uses to refer to any open resource — not just regular files:
- Regular files
- TCP/UDP sockets
- Pipes
- stdin (0) / stdout (1) / stderr (2)

**`ulimit -n`** = max number of FDs a single process can have open simultaneously. Note: shell `ulimit` only affects the current shell/session — a systemd service gets its own limit via `LimitNOFILE=` in the unit file, or `/etc/security/limits.conf` for login sessions.

**When "too many open files" (`OSError: [Errno 24] EMFILE`) actually happens in production:**
- **Connection/file-handle leak** — opening a DB connection / HTTP client / file inside a request handler without closing it (missing `finally`/context manager). Each request leaks 1 FD; eventually hits the limit under sustained traffic.
- **High concurrency without raising the default limit** — thousands of simultaneous client sockets on a service still running the OS default (`1024`); production services explicitly raise it (`LimitNOFILE=65536` in systemd).
- **Unbounded connection pools** — HTTP keep-alive or DB pools with no max size slowly eat all available FDs.
- **Unrotated/unclosed log file handles.**

**Debugging approach:** find the leak first — `lsof -p <pid> | wc -l` to see how many FDs a process actually holds — don't just raise the ulimit as a band-aid.

---

## Q4. Context Switching — what's saved/restored, cost order

**Saved/restored per switch:**
```
CPU Registers · Program Counter (PC) · Stack Pointer (SP) · CPU flags/status register
(+ additional architecture/OS-specific state)
```

**Cost order (most → least expensive): Process switch > Thread switch > Coroutine switch**

| Switch type | What changes | Why it costs what it costs |
|---|---|---|
| **Process** | Full address space change | Changing the page-table base register (CR3 on x86) forces a **TLB flush/invalidation** — every subsequent memory access briefly pays a TLB-miss penalty. Also **cache pollution**: L1/L2 cache lines from the old process get evicted as the new one runs, so there's a "cold cache" tax right after. |
| **Thread** | Same address space, just registers/PC/SP swap | No TLB flush needed (same page tables), but still requires a **trap into kernel mode** — the kernel scheduler code has to run, which has fixed CPU cost regardless of address space. |
| **Coroutine** | Same OS thread, runtime just saves/restores a small execution state (e.g. `await` in asyncio) | **100% user-space — zero syscalls, zero kernel trap.** The kernel never even knows the switch happened. This is the real reason it's cheapest, not just "OS doesn't *need* to get involved." |

---

## Q5. I/O Models — Blocking / Non-blocking / Multiplexing / Async

```
1. Blocking I/O:
   thread calls read() → thread SLEEPS (not runnable) → data arrives → wakes, gets data
   → 1 thread per connection; 10,000 connections = 10,000 threads = huge overhead (classic scalability wall)

2. Non-blocking I/O:
   thread calls read() → returns IMMEDIATELY with EAGAIN/EWOULDBLOCK if nothing ready
   → thread never sleeps on this call, but naive re-polling in a loop burns 100% CPU checking nothing
   → non-blocking alone isn't a solution, it's a building block

3. I/O multiplexing (select/poll/epoll):
   thread registers many FDs with the kernel → calls select()/poll()/epoll_wait() → BLOCKS efficiently
   → kernel wakes it ONLY when ≥1 FD is ready → thread loops over just the ready ones
   → ONE thread handles thousands of connections (nginx, Redis event loops)
   → READINESS-based: "you may read now without blocking" — you still issue the syscall + copy yourself

4. Async I/O (true, e.g. io_uring, Windows IOCP, POSIX AIO):
   thread submits a read request → returns immediately, does other work
   → kernel does the ENTIRE read (including copying data into your buffer) in the background
   → kernel notifies "here's your completed data" — no read() call needed at notification time
   → COMPLETION-based, fundamentally different from readiness-based multiplexing
```

### Why epoll beats select/poll at high connection count (the C10K problem)

| | select | poll | epoll |
|---|---|---|---|
| Max FDs | Hard limit **1024** (`FD_SETSIZE`) | No hard limit | No hard limit |
| Per-call cost | Kernel rescans **all registered FDs** every call — O(n) | Same — O(n) scan every call | Kernel maintains a ready-list; `epoll_wait` returns only ready FDs — cost scales with **active**, not total, connections |
| Data copied per call | Entire fd_set copied user↔kernel **every call** | Entire array copied every call | FD interest registered **once** via `epoll_ctl`; `epoll_wait` only copies back the ready subset |

With 10,000 connections but only 5 active: `select`/`poll` still scan/copy all 10,000 every call. `epoll` only touches what's ready. This is why every modern high-concurrency server (nginx, Node.js/libuv, Python asyncio on Linux) uses epoll.

---

## Q6. CFS Scheduler + `nice`

**Note:** Modern kernels (Linux 6.6+, 2023) replaced CFS with **EEVDF** (Earliest Eligible Virtual Deadline First), but CFS remains the standard interview/fundamentals model.

**Core idea:** the runnable task with the **lowest `vruntime`** (virtual runtime — actual CPU time normalized by weight/priority) gets scheduled next.

```
Process A → vruntime = 10
Process B → vruntime = 5   ← lowest → gets CPU next
Process C → vruntime = 20
```
As a task runs, its vruntime increases → it becomes less preferred → scheduler naturally rotates to whoever has consumed the least proportional share. This is what makes it "fair."

**`nice` value:** range `-20` (highest priority) to `+19` (lowest priority), default `0`. Crucially — **`nice` does NOT mean "run before everyone."** It changes the task's **scheduler weight**, which changes how fast its vruntime accumulates relative to others.

**Concrete weight numbers:** `nice 0 = weight 1024`. Each nice step changes weight by a factor of **~1.25x** — so `nice +1 ≈ 820`, `nice -1 ≈ 1280`. This means nice values compound **multiplicatively**, not linearly: `nice +19` gives a dramatically smaller CPU share than `nice 0`, not just "19 units less."

**Interview trap:** the scheduler doesn't decide based on `nice` alone — real-time scheduling classes, task state (runnable/blocked), CPU topology, and total runnable task count all matter too.

---

## Round 2 Scorecard (from live recap session)

| Q | Topic | Result |
|---|---|---|
| 1 | Process vs Thread + GIL | ✅ Excellent (verified with live CPU-bound + I/O-bound benchmarks) |
| 2 | Virtual Memory + Page Faults | ✅ Excellent (verified with live COW fork demo, discovered real 16KB page size) |
| 3 | File Descriptors + ulimit | ✅ Correct core; needed prompting for real production trigger scenarios |
| 4 | Context Switching cost order | ✅ Excellent — correct save/restore list and cost ordering |
| 5 | I/O Models (blocking→async) | ⚠️ High-level only initially — full depth filled in above |
| 6 | CFS Scheduler + nice | ✅ Excellent, senior-level (correctly flagged EEVDF too) |

**Action item:** Re-read the I/O Models section above once more — it's the one gap this round, and it's a very common backend interview topic (comes up in "how does nginx/Node.js handle thousands of connections" style questions).
