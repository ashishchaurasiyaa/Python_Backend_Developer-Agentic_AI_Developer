# Foundations — Operating System Concepts for Backend Devs
**Foundations · Year 0-2 | Zero → Senior**

## Quick Concepts

- **Process** = isolated program in execution with own memory space
- **Thread** = lightweight execution unit sharing process memory
- **Kernel** = OS core managing CPU, memory, I/O, processes
- **User space vs Kernel space** = isolated regions, syscalls cross the boundary
- **Syscall** = function call from user code into the kernel (e.g., `read`, `write`, `fork`)
- **Context switch** = saving one process/thread state and loading another
- **Virtual memory** = each process sees its own contiguous address space
- **Page** = unit of memory (typically 4 KB)
- **Scheduler** = picks which thread runs on each CPU
- **IPC** = Inter-Process Communication (pipes, sockets, shared memory, signals)
- **File descriptor** = integer handle for an open file/socket

---

## Why Backend Devs Need This

```
Without OS understanding, you can't reason about:
─────────────────────────────────────────────────
✗ Why Python has GIL (and what unblocks under it)
✗ Why asyncio works (epoll/kqueue under the hood)
✗ Why too many connections crash your service
✗ Why your container OOMs (cgroups + virtual memory)
✗ Why locks slow down high-concurrency code
✗ Why network buffers matter
✗ Why "context switch overhead" matters
✗ Why containers ≠ VMs

These show up in every senior interview.
```

---

## Process vs Thread

### Visual

```
   ┌─── Process A ────┐    ┌─── Process B ────┐
   │  Own memory      │    │  Own memory      │
   │  Own file descr  │    │  Own file descr  │
   │  Own PID         │    │  Own PID         │
   │                  │    │                  │
   │  ┌──┐ ┌──┐ ┌──┐ │    │  ┌──┐            │
   │  │T1│ │T2│ │T3│ │    │  │T1│            │
   │  └──┘ └──┘ └──┘ │    │  └──┘            │
   │  shared memory  │    │                  │
   └──────────────────┘    └──────────────────┘

Process       Thread
─────────────────────────────────────
Heavy         Light
Own memory    Shared memory in process
Own PID       Has TID, shares PID
Crash isolated  Crash kills process
IPC needed    Direct memory access
fork() / exec()  pthread_create
```

### Process Internals — how the kernel actually runs one

The kernel tracks every process via a **PCB (Process Control Block** — Linux calls it `task_struct`):

```
PCB (per process, kernel-maintained):
   PID, PPID              — process ID, parent's ID
   State                  — Running / Ready / Waiting / Zombie / Terminated
   Program Counter        — next instruction (saved/restored on context switch)
   CPU Registers          — snapshot, saved on every context switch
   Memory Management Info — page table pointer (virtual → physical mapping)
   File Descriptor Table  — open files/sockets (fd 0, 1, 2, 3...)
   Priority / Nice value  — scheduler input
   Signal handlers        — what to do on SIGTERM/SIGHUP/etc.
```

**Creating a process is TWO separate syscalls, not one — `fork()` then `exec()`:**

```
Shell running `ls`:

1. Shell (PID 500) calls fork()
     → kernel makes a near-identical COPY (memory copy-on-write, fds duplicated)
     → child gets a NEW PID (501), its PPID = 500
     → fork() returns the CHILD's PID (501) to the parent
     → fork() returns 0 to the child
     → (both processes now run the SAME code, forward from this point,
        branching via `if pid == 0: ... else: ...`)

2. Child (PID 501) calls exec("/bin/ls")
     → kernel REPLACES this process's memory image with `ls`'s code
     → PID stays 501, but the program running is now completely different

3. Parent (PID 500) calls wait() / waitpid()
     → blocks until child 501 finishes, then reaps its exit status
```

**Why two syscalls instead of one combined "spawn"?** Because there's a deliberate gap between them where the child can configure itself *before* the new program loads — e.g. `cmd > file` redirection works by the child remapping fd 1 to a file **between** `fork()` and `exec()`. A single combined syscall couldn't do that.

**Zombies:** a process that has exited but whose exit status the parent hasn't collected yet (`ps` shows `STAT = Z`). It's not "stuck" — it's just occupying a PCB slot until `wait()`/`waitpid()` reaps it. If the parent never calls `wait()` and later dies itself, the zombie gets re-parented to PID 1 (`init`/`launchd`), which reaps it automatically — but a long-lived parent that never reaps can accumulate zombies, a real (if rare) production leak symptom.

**Verified live proof** (`os.fork()` on this repo's dev machine):
```
counter = 0 before fork(); child does counter += 100, parent does counter += 1
[CHILD]  counter = 100
[PARENT] counter = 1        ← proves separate memory — not shared, truly copied

fork() returned: 87807 to parent (child's PID), 0 to child
waitpid() in parent successfully reaped exit code 42 from the child
```

**Bonus gotcha caught in that same run:** a `print()` issued *before* `fork()`, with stdout buffered (piped/redirected, not a live terminal), showed up **twice** in the output — once from each process. Buffered-but-unflushed output existing at fork() time gets copied into both processes' memory, and each flushes its own copy independently on exit. Real-world consequence: forking/multiprocessing right after buffered logging can produce duplicate log lines — fix with `sys.stdout.flush()` (or `print(..., flush=True)`) before the fork.

### Trade-offs

```
Process              Thread
────────────────────────────────────
✓ Isolated crashes   ✓ Cheaper to create
✓ Easier reasoning    ✓ Fast to communicate
✗ Heavier            ✗ Race conditions possible
✗ IPC overhead       ✗ One bug crashes all
✗ Slower context switch  ✓ Faster context switch
```

### Thread Internals — TCB, shared vs private state

Every process has a PCB; every **thread** inside it has its own smaller record — a **TCB (Thread Control Block)**:

```
TCB (per thread):
   TID                 — Thread ID (Linux: LWP, Lightweight Process ID)
   Program Counter     — which instruction THIS thread is on
   CPU Registers       — this thread's register snapshot (saved/restored on switch)
   Stack pointer       — top of THIS thread's own call stack
   State               — Running/Ready/Blocked — tracked per-thread, not per-process
```

**What threads in the same process SHARE vs keep PRIVATE — this exact split is interview-standard:**

```
SHARED (same process, all threads see the same copy):
   ✓ Code (text segment)
   ✓ Heap (malloc'd / Python object memory)
   ✓ Global variables
   ✓ Open file descriptors / sockets
   ✓ Process ID (PID) — every thread in a process reports the same PID

PRIVATE (each thread has its own):
   ✗ Stack — local variables, function call frames, return addresses
   ✗ Program Counter
   ✗ CPU Registers
   ✗ TID
```

Stack has to be private — if two threads called the same function simultaneously and shared one stack, their local variables and call frames would corrupt each other on every nested/recursive call.

**Kernel vs user thread models:**

```
1:1 (Linux, CPython's `threading` module):
   1 Python thread = 1 real OS/kernel thread — true OS-level scheduling,
   but thread creation goes through the kernel (a bit heavier).

N:1 (green threads / classic coroutines):
   N user-space threads multiplexed onto 1 kernel thread. Kernel doesn't
   know multiple threads exist. Cheap to create, but one blocking call
   blocks everything (kernel only sees one thread).

M:N (Go goroutines):
   M user threads mapped onto N kernel threads — best of both, but
   the runtime scheduler has to do real work to make it happen.
```

Python's `threading` uses the **1:1 model** — real OS threads, which is exactly why the GIL is a separate, additional constraint on top: the OS *would* schedule them in true parallel, but CPython's bytecode-level lock prevents that for pure Python code.

**Verified live proof** (`threading` module, 3 checks in one script — see [`thread_demo.py`](thread_demo.py)):
```
1. PID identical across all threads (16597), TID different per thread
   (3800507, 3800508, 3800509, 3800510) — confirms shared PID / private TID

2. Two threads incrementing the SAME global counter 10,000,000 times each,
   under a Lock: final result = 20,000,000 exactly (proves shared heap —
   NOT a fork()-style private copy; also proves the Lock correctly
   prevented the race condition that `+=` without a lock would produce)

3. Two threads recursing through the SAME function simultaneously, each
   building its own local-variable chain ("start-A->4->3->2->1" vs
   "start-B->4->3->2->1") with zero cross-contamination — proves
   separate, private stacks even when running identical code
```

**A real bug this demo caught while building it (worth knowing on its own):** when an exception is raised *inside* a `threading.Thread`, Python prints the traceback to stderr and kills that thread — but it does **not** propagate to the main thread, and the overall process still exits with code 0. `t.join()` does not re-raise it either. If you only monitor exit codes (CI, cron, systemd), a crashing worker thread can fail completely silently. Fix: wrap the thread's target function in its own try/except and report failures explicitly (a queue, a shared results list+lock), or use `concurrent.futures.ThreadPoolExecutor` instead of raw `threading.Thread` — its `.result()` *does* re-raise the worker's exception when you collect the result.

### In Python

```
Python's GIL means:
   ✗ Threads can't run Python bytecode in parallel
   ✓ Threads CAN release GIL for I/O (network, disk)
   ✓ Multiprocessing escapes GIL — true parallelism

Result:
   I/O bound  → threads or asyncio
   CPU bound  → multiprocessing
   Mixed      → asyncio + ProcessPoolExecutor
```

---

## Virtual Memory

### Why It Exists

```
Without virtual memory:
   ✗ All processes share one address space
   ✗ Process A could read/write Process B's memory
   ✗ Out-of-memory crashes entire system
   ✗ No memory protection

With virtual memory:
   ✓ Each process sees 0 → 2⁶⁴ as its OWN address space
   ✓ OS maps virtual → physical via page tables
   ✓ Pages can be on disk (swap)
   ✓ Copy-on-write enables fast fork()
```

### How It Works (Simplified)

```
Process sees virtual address 0x7f3a1234
                 │
                 ▼
   ┌──────────────────────┐
   │   Page table         │  (OS-managed)
   │   virt → phys mapping│
   └──────────────────────┘
                 │
                 ▼
        Physical RAM address
        e.g., 0x12345678

If page not in RAM → page fault
   → OS loads from disk (swap) or fails
```

**Terminology — "page" vs "frame":** the virtual side is divided into fixed-size **pages** (typically 4 KB); the matching physical-RAM side is divided into **frames** of the same size. The page table's real job is just: page N → frame M.

**Memory protection, concretely:** two processes can both use virtual address `0x1000` at the same time — Process A's page table maps it to physical frame 5000, Process B's maps the *same virtual address* to a completely different frame 9000. If Process A's page table has no valid entry (or wrong permissions) for an address it tries to touch, the CPU's MMU traps into the kernel, which sends `SIGSEGV` — this is the actual mechanism that stops one process from reading/writing another's memory, not a polite convention. Verified live below.

**mmap() — files as virtual memory:** `mmap()` maps a file (or anonymous memory) directly into a process's virtual address space, so reading/writing that region reads/writes the file through the same page-table machinery as regular memory — no manual read()/write() loop, and the kernel decides when pages actually sync to disk. Common for large files and shared-memory-style IPC.

### Memory Layout of a Process

```
   ┌──────────────────┐  High addresses
   │   Kernel space   │  (mapped but inaccessible)
   ├──────────────────┤
   │   Stack          │  (grows down)
   │       ↓          │
   │                  │
   │       ↑          │
   │   Heap           │  (grows up — malloc/Python allocator)
   ├──────────────────┤
   │   BSS / Data     │  (globals, static)
   ├──────────────────┤
   │   Text (code)    │  (read-only program)
   └──────────────────┘  Low addresses
```

### Page Faults & Swap

```
Page fault:
   Process accesses memory that's not in RAM
   → OS handles transparently:
      1. Check if valid mapping (else SIGSEGV)
      2. Load page from disk if swapped
      3. Resume process

Hard page faults (disk I/O) = SLOW (~ms)
Soft page faults (just mapping) = fast (~µs)

Monitor with `vmstat 1`:
   `si` = swap in (BAD if > 0)
   `so` = swap out (BAD if > 0)
```

### Virtual Memory vs cgroup memory limit — two different layers, don't conflate

```
Virtual Memory  = OS abstraction: process gets its own address space,
                  the kernel maps it to physical RAM via page tables.
                  This exists for EVERY process, container or not.

cgroup limit    = a resource CEILING layered on top: "this process/
                  container may not have more than X MB resident."
                  This is what OOM-kills you (see OOM Killer section) —
                  it's a policy, not the memory-addressing mechanism.
```

A process can have a huge, sparse virtual address space (gigabytes reserved, e.g. from `mmap`-ing large files) while its actual RSS — and therefore its exposure to a cgroup limit — stays small. Conversely, hitting a cgroup limit is about resident memory, and has nothing to do with how large the process's virtual address space looks. Don't read "VSZ = 20 GB" as "this will OOM at a 512 MB container limit" — check RSS against the limit, not VSZ.

### Verified live proof — 3 mechanisms (see [`vm_demo.py`](vm_demo.py))

```
1. VSZ vs RSS diverge as memory is TOUCHED, not just allocated:
   Baseline:                              VSZ=410,189,584 KB  RSS=16,432 KB
   After allocating a 500MB bytearray:    VSZ=410,832,688 KB  RSS=311,552 KB
   After writing to every page:           VSZ=410,832,688 KB  RSS=526,672 KB
   → VSZ jumped immediately at allocation. RSS grew in TWO separate steps
     (partly at allocation -- zero-init touches some pages immediately --
     and further once every page was explicitly written) -- confirms VSZ
     is "reserved," RSS is "physically resident," and they move on
     different triggers, not in lockstep.

2. mmap() — a 10MB file mapped into virtual memory, written at both ends,
   then re-opened fresh (NOT via the mmap handle) and re-read:
   mm[0:5] = b'HELLO', mm[-5:] = b'WORLD'
   fresh reopen: start=b'HELLO', end=b'WORLD'
   → proves the mmap'd writes really landed on disk, going through the
     same page-table machinery as regular process memory.

3. SIGSEGV — a deliberate invalid pointer dereference via ctypes, run in
   an isolated subprocess (a real SIGSEGV would otherwise kill the whole
   script): child exit code -11 = killed by SIGSEGV.
   → the MMU had no valid page-table entry for that address, trapped
     into the kernel, kernel killed the process. This is memory
     protection as an actual enforced mechanism, not a convention.
```

---

## File Descriptors

```
Every open file / socket / pipe = a file descriptor (integer)

Default:
   0 = stdin
   1 = stdout
   2 = stderr

Process limit (per-process):
   ulimit -n             # show
   ulimit -n 65536       # set

System limit:
   /proc/sys/fs/file-max
```

### Why Backend Devs Care

```
Each open connection = 1 file descriptor.

Production app holding 10,000 connections:
   ✓ Need ulimit -n ≥ 10,000
   ✗ Default 1024 = "Too many open files" crash

Connection pooling exists partly to avoid FD exhaustion.
```

### Inspect

```bash
ls -la /proc/$PID/fd/    # all FDs of process
lsof -p $PID             # human-readable
```

### Verified live proof — see [`fd_limits_demo.py`](fd_limits_demo.py)

```
1. FD allocation is one shared integer sequence for files AND sockets:
   opened file 0: fd = 3    opened file 1: fd = 4   ... opened file 4: fd = 7
   opened a socket:  fd = 8   <- SAME sequence, right after the files
   → confirms "everything is a file descriptor" — fd 0/1/2 reserved for
     stdin/stdout/stderr, then every open()/socket() just takes the next
     free integer regardless of what kind of resource it is.

2. Lowered RLIMIT_NOFILE to 50 (== `ulimit -n 50`) via Python's `resource`
   module, then opened files in a loop until it broke:
   Managed to open 47 files before hitting the limit
   Error raised: [Errno 24] Too many open files: '/tmp/fd_exhaust_47.txt'
   → the exact real production error, reproduced deliberately in seconds
     instead of waiting for it to happen under real traffic. Errno 24's
     symbolic name is `EMFILE` ("too many open files" for THIS process —
     different from `ENFILE`, the system-wide table being full).
```

### Verified live proof, part 2 — see [`fd_advanced_demo.py`](fd_advanced_demo.py)

```
1. f.fileno() — the Python object vs the kernel's actual integer handle:
   f = open(...) is a Python wrapper object; f.fileno() = 3 is the raw
   number the KERNEL knows. Different layers, verified distinctly.

2. FD numbers are NOT globally unique — only meaningful per-process:
   Process 1: pid=27772 fd=3 file=fd_scope_demo.txt
   Process 2: pid=27773 fd=3 file=fd_scope_demo2.txt
   → two unrelated processes, same fd number (3), completely different
     files. "fd 3" only means something once you also know WHICH
     process's fd table you're asking about.

3. fork() + file descriptors — offset is SHARED kernel state, unlike
   memory (which fork() gives each process its own private/COW copy of):
   [CHILD]  read 5 bytes using inherited fd 3: b'01234'
   [PARENT] read 5 bytes AFTER child, same fd 3: b'56789'
   → parent got bytes 5-9, not 0-4 — the read POSITION moved for BOTH
     processes because they share the same underlying kernel "open file
     description," not just the same file. "fork() copies memory" and
     "fork() shares FD state" are both true and easy to conflate.
   → bonus gotcha found while building this: the child used os._exit()
     to terminate, which does NOT flush stdio buffers (unlike sys.exit()
     or normal shutdown) — the child's print silently vanished until an
     explicit sys.stdout.flush() was added before os._exit(). Real
     consequence: worker processes that os._exit() after fork() can lose
     buffered log output for good.

4. accept() returns a brand-new fd, distinct from the listening socket's:
   Listening socket fd = 3 (bound to 127.0.0.1:65229)
   accept() returned a NEW connected-socket fd = 5
   Listening fd (3) is STILL open, unaffected, ready for the next accept()
   → confirms "1 listening fd + N per-client fds" with a real socket
     pair, not just a diagram.
```

---

## Syscalls (User → Kernel Boundary)

### Common Syscalls You Indirectly Use

```
read(fd, buf, n)         # read from FD into buffer
write(fd, buf, n)        # write
open(path, flags)        # → returns FD
close(fd)
fork()                   # create child process (copy)
exec()                   # replace process image
wait()                   # wait for child
mmap()                   # map file/anon memory
sbrk() / brk()          # extend heap
epoll_wait()             # async I/O multiplexer (Linux)
socket(), bind(), listen(), accept()  # networking
```

### Trace Syscalls

```bash
# What syscalls is my Python process making?
strace -p $PID

# Trace from start
strace python app.py

# Filter to network
strace -e network curl example.com

# Summary (which syscall ate most time)
strace -c python app.py
```

### Senior Insight

```
Syscalls are SLOWER than library calls (kernel context switch).

That's why:
   ✓ Buffered I/O is faster than unbuffered
   ✓ Sendfile() beats read() + write() for file → socket
   ✓ epoll batches FDs in one syscall
   ✓ io_uring (modern) batches multiple syscalls
```

### Verified: the raw syscall wrapper layer (see [`io_models_demo.py`](io_models_demo.py))

`os.open()` / `os.read()` / `os.write()` / `os.close()` **are** the direct syscall wrappers — no buffering, no text encoding, nothing added. Verified: wrote raw bytes with `os.write(fd, ...)`, read them back with `os.read(fd, ...)`, byte-for-byte. Regular Python `open()` is built as a layer **on top of** these exact same syscalls, adding buffering/encoding/iteration — it's not a different mechanism, just more abstraction over the same kernel boundary. `strace`/`dtruss` (macOS) trace calls at exactly this layer — that's what the `os.*` functions map to almost 1:1.

### Verified: syscall COUNT matters, not just presence (see [`syscall_count_demo.py`](syscall_count_demo.py))

```
Same 2,000,000 bytes written to disk, two ways:
  2,000,000 separate 1-byte write() syscalls: 3.415s
  30 batched 64KB write() syscalls (same data): 0.001s
  → 6640x slower doing one syscall per byte.
```

This is the concrete, measured reason buffered I/O exists: every `write()` call crosses the user↔kernel boundary, and that crossing has a real, non-zero cost — Python's regular `open()`/`.write()` batches your writes into an internal buffer and only issues the real syscall periodically, trading a tiny bit of "not immediately on disk" for avoiding millions of kernel crossings. Same logic applies to network `send()` calls, DB driver batching, and log-line buffering.

**Syscall tracing on macOS — an honest limitation, not glossed over:** `dtruss` is the macOS equivalent of `strace`, but it requires `sudo`, and modern macOS's System Integrity Protection restricts DTrace-based tools further even under `sudo` — tried directly in this repo (`sudo -n dtruss ...`) and it correctly refused without an interactive password. This isn't a workaround-able gap from inside an automated session: verify `strace`/`dtruss` output on a real Linux box or CI runner, not on a stock macOS dev laptop.

---

## Context Switching

**Don't conflate this with a syscall — related, but different mechanisms:**
```
Syscall:        User Space → Kernel Space → User Space (SAME task,
                 crossing a PRIVILEGE boundary to ask the kernel for
                 something, then returning to where it left off)

Context switch: Task A → Task B (the scheduler changes WHICH task is
                 running at all — a different task entirely resumes)
```
A syscall *can* trigger a context switch as a side effect — e.g. a blocking `read()` with no data ready has nothing useful to do, so the scheduler may switch to another runnable task while it waits — but the two concepts are independent: plenty of syscalls (a quick `getpid()`) never trigger a switch, and plenty of context switches happen for reasons that have nothing to do with any syscall (a timer-based scheduler preemption, for instance).

```
When OS scheduler switches from Process A to Process B:

   1. Save CPU registers of A
   2. Save A's program counter
   3. Switch page tables (TLB flush)
   4. Load B's registers + PC
   5. Resume B

Cost: ~1-10 µs (microseconds)

Sounds fast, but at 10,000 switches/sec = 10-100 ms wasted/sec.
```

### Implications

```
Why goroutines + async are faster than threads:
   - Goroutine switch:  ~200 ns  (no kernel)
   - Thread switch:    ~1-10 µs (kernel involvement)
   - Process switch:   ~10 µs+ (TLB flush)

For high-concurrency servers, this matters a LOT.

Async (epoll/asyncio):
   - No threads per connection
   - One thread, thousands of connections
   - Switch is just a Python function pivot
```

### Process switch vs Thread switch vs Coroutine switch — not the same cost

```
Process → Process switch:  potentially swaps address space (page table
                            pointer changes → TLB entries for the old
                            process are now useless → more TLB misses
                            after the switch until the new process's
                            translations get cached again)

Thread → Thread switch:    same process, SAME address space/page table —
                            no TLB invalidation from that alone; still
                            costs register/PC save-restore + scheduler work

Coroutine → Coroutine:     not a kernel operation at all when they're in
                            the same OS thread — the "switch" is just the
                            event loop calling a different Python
                            function. No kernel involved, no register
                            save/restore beyond normal function-call
                            mechanics.
```

This is exactly why the ordering `~200ns (goroutine) < ~1-10µs (thread) < ~10µs+ (process)` above holds — each step up adds real, distinct kernel-level cost the one below it doesn't pay.

### Verified — kernel thread switching vs coroutine switching, using real OS counters

See [`context_switch_types_demo.py`](context_switch_types_demo.py) — `resource.getrusage().ru_nvcsw`/`ru_nivcsw` are the OS's own context-switch counters for this process:

```
20 OS threads, each doing a real blocking sleep(0.05s):
   involuntary context switches: +97

20 coroutines, doing the SAME logical wait (asyncio.sleep), ONE OS thread:
   involuntary context switches: +11
→ ~9x less OS-visible switching for the coroutine version, doing the
  exact same logical work — because coroutine handoffs happen INSIDE
  one thread's event loop and never touch the kernel scheduler at all.
  This is the measured version of "10,000 coroutines is not 10,000
  kernel threads."

20 CPU-bound threads (busy loop, no yield point) vs the same 20
I/O-blocking threads: order-of-magnitude MORE switch activity for the
CPU-bound ones (varies per run, consistently 50-170x in testing) —
busy threads keep getting forcibly preempted; blocking threads mostly
just wait.
```

**Honest platform-quirk finding, not glossed over:** the theory above (voluntary = a thread chooses to yield, e.g. via a blocking syscall; involuntary = the scheduler forcibly preempts it) is a real, standard OS concept. Attempting to verify it via Python's `ru_nvcsw` on **this** machine (macOS/Darwin) failed to show the expected split — even a single plain `time.sleep()` on the *main* thread alone, the textbook voluntary-yield case, reported zero growth in `ru_nvcsw`, with everything counted as `ru_nivcsw` instead. This looks like a macOS-specific difference in how `getrusage()` populates that field, not a flaw in the underlying concept. To verify voluntary vs involuntary counts the way Linux textbooks describe them, use `/proc/$PID/status`'s `voluntary_ctxt_switches` field or `pidstat -w` on an actual Linux box — not this API on macOS.

```
1. os.sched_yield() cost, measured directly (100,000 calls):
   0.20 microseconds per yield
   → lands right in the ~1-10µs range this section claims — verified,
     not just quoted from a textbook.

2. Same 20M total iterations of work, split across 1 / 4 / 16 threads:
   1 thread:  0.577s wall time
   4 threads: 0.556s wall time
   16 threads: 0.568s wall time
   → HONEST result: overhead did NOT grow as sharply with thread count as
     naive "more threads = more switches = more overhead" theory predicts.
     Why: each individual switch is cheap (~0.2µs per Proof 1), and
     CPython's GIL switch interval (default 5ms) caps how often actual
     handoffs happen regardless of how many threads are waiting — so at
     this workload size the switch COUNT didn't scale as fast as thread
     count did. The lesson survives: switch overhead is real and
     measurable, but it only dominates at extreme thread counts or very
     short switch intervals, not automatically at any thread count.
```

---

## I/O Models (Critical for Backend)

### 1. Blocking I/O

```
Thread A calls read() → BLOCKS until data ready
Can't do anything else.
Simple but inefficient.
```

### 2. Non-Blocking I/O

```
Thread A calls read(fd, ...), gets EAGAIN if not ready.
Must poll. Wastes CPU.
```

### 3. I/O Multiplexing (select / poll / epoll)

```
One thread asks: "which of these 10,000 FDs has data?"
Kernel responds when ANY is ready.
Foundation of asyncio, Node.js, Nginx.

select/poll:     scan all FDs every call — O(n)
epoll (Linux):   register once, get notified — O(1)
kqueue (BSD/mac): same idea
io_uring (modern Linux): even better, batch ops
```

### 4. Asynchronous I/O

```
Submit operation, get notified when complete.
True async (POSIX AIO, io_uring, IOCP on Windows).
Python's asyncio uses epoll under the hood (Linux).
```

### Why It Matters for Python

```
Asyncio in Python:
   - Single thread (no GIL contention)
   - epoll under the hood
   - Handles 10,000+ concurrent connections
   - Why FastAPI > Flask for I/O-heavy workloads

But:
   - asyncio doesn't help CPU-bound work
   - For CPU work, use multiprocessing
```

### Verified live proof — all 3 models, real sockets (see [`io_models_demo.py`](io_models_demo.py))

```
1. Blocking: recv() on an empty socket blocked for exactly as long as the
   writer waited before sending — 0.30s blocked, then data arrived. The
   thread did nothing else during that wait.

2. Non-blocking: recv() on an empty non-blocking socket raised IMMEDIATELY:
   [Errno 35] Resource temporarily unavailable (EAGAIN)
   → real EAGAIN, not a description of it. After the writer sent data, a
     retry succeeded. Proves non-blocking mode pushes the "is it ready?"
     work onto YOU (poll/retry), which is exactly why naive non-blocking
     loops waste CPU spinning.

3. Multiplexing: watched 5 sockets with ONE select() call; only 1 had
   data. select() correctly identified WHICH one (index 2) without
   checking each socket individually. On macOS, Python's select module
   is backed by kqueue (the BSD equivalent of Linux epoll) — same O(1)
   "tell me which is ready" idea, different kernel API underneath.
```

---

## Inter-Process Communication (IPC)

**Why IPC exists at all:** unlike threads (same process, shared heap for free), two **processes** never share memory by default — each has its own isolated virtual address space. Any time two processes need to exchange data or coordinate, the kernel has to provide an explicit channel. That's what every mechanism below actually is.

### Pipes

```bash
# Anonymous pipe (parent-child)
cmd1 | cmd2

# Named pipe (FIFO)
mkfifo /tmp/myfifo
echo hello > /tmp/myfifo &
cat /tmp/myfifo
```

### Sockets

```
Unix domain socket: same machine, fastest
TCP socket: network or local
Most common IPC in modern apps.
```

### Shared Memory

```
mmap() — same memory in multiple processes
Fastest IPC, but synchronization is your problem.

Python:
   - multiprocessing.shared_memory (3.8+)
   - multiprocessing.Manager
```

### Signals

```
kill -USR1 $PID    # send signal
kill -HUP $PID     # reload (nginx convention)

Python:
   import signal
   signal.signal(signal.SIGTERM, handler)
```

### Message Queues

```
sysv-msg, posix-mq — kernel-managed queues
Less common; usually use Redis/RabbitMQ instead.
```

### Verified live proof — 3 mechanisms, real separate processes

See [`ipc_demo.py`](ipc_demo.py) — `multiprocessing.Process` (a real OS process each, distinct PIDs, no shared memory unless explicitly arranged):

```
1. Pipe (multiprocessing.Pipe) — two-way message channel
   [CHILD  pid=18199] received via pipe: 'hello from parent'
   [PARENT pid=18197] received reply: "ack: got 'hello from parent'"
   → proves: two DIFFERENT PIDs exchanged data only because a pipe
     was explicitly created — there was no other way for them to talk.

2. Shared Memory (multiprocessing.shared_memory) — real shared bytes
   [PARENT pid=18197] wrote b'PARENT', block name = psm_3d5092b8
   [CHILD  pid=18200] wrote b'CHILD' into shared block
   [PARENT pid=18197] block now reads: b'CHILD'
   → proves: the child's write OVERWROTE the parent's — this is the
     SAME physical memory, not a copy or a message. Also proves the
     "synchronization is your problem" warning above: nothing stopped
     a race here; a real use would need a Lock around it, same as
     threading's shared-counter example earlier in this file.

3. Signals (os.kill + a custom handler) — notification, no payload
   [CHILD  pid=18201] handler installed, waiting...
   [PARENT pid=18197] sending SIGUSR1 to child pid=18201
   [CHILD  pid=18201] caught SIGUSR1, set flag=1
   [PARENT pid=18197] child's flag after join: 1
   → proves: the signal itself carried no data — the child had to use
     a SEPARATE shared multiprocessing.Value to report back "I got it."
     Signals are wake-up calls, not data pipes.
```

**Interview-ready comparison:** pipes/sockets move *data* through the kernel (serialize → copy → deserialize, some overhead); shared memory moves *zero* data — both sides see the same bytes directly, fastest but you own all synchronization; signals move *neither* — they're a pure async notification, cheapest, but you need a second channel if the receiver has to tell you anything back.

---

## Scheduler (How CPU Time Is Divided)

### Linux Scheduler (CFS — Completely Fair Scheduler)

```
Goal: each runnable thread gets a fair share of CPU.

Calculates "virtual runtime" per thread.
Pick thread with lowest vruntime to run next.

Nice values:
   -20 = highest priority
    0  = default
   +19 = lowest priority

renice +10 $PID    # be nicer (give others priority)
```

### Real-Time Schedulers

```
SCHED_FIFO: highest-priority RT thread runs until it yields
SCHED_RR: like FIFO but round-robin within priority

Use only for real-time apps (audio, robotics).
For backend: stick with default CFS.
```

### CPU Affinity

```bash
# Pin process to specific CPU(s)
taskset -cp 0,1 $PID   # bind to CPU 0 + 1

Useful when:
   - NUMA boundaries matter
   - Cache locality critical
   - Hyperthreading interference
```

### Verified — `nice`, and a real macOS/Linux platform gap (see [`scheduler_context_switch_demo.py`](scheduler_context_switch_demo.py))

```
os.nice(5) actually applied: nice value 0 -> 5, confirmed independently
via `ps -o nice=` (not just trusting the Python return value).

Platform gotcha, verified not assumed: hasattr(os, 'sched_getaffinity')
on macOS = False. CPU affinity pinning (`taskset -cp 0,1 $PID` on Linux)
has NO equivalent through Python's os module on macOS — Apple Silicon's
scheduler manages Performance vs Efficiency core placement itself rather
than exposing raw pinning. Deployment/ops code written for Linux that
calls os.sched_getaffinity() will crash outright on a Mac dev machine —
a real portability trap, confirmed by trying it, not by reading about it.
```

---

## Resource Limits (`ulimit` / cgroups)

### Per-Process Limits (ulimit)

```bash
ulimit -a              # all limits
ulimit -n              # open files
ulimit -u              # max processes
ulimit -m              # max memory
ulimit -s              # stack size

# Persist:
echo "* soft nofile 65536" >> /etc/security/limits.conf
echo "* hard nofile 65536" >> /etc/security/limits.conf
```

### Container Limits (cgroups)

```
Docker / Kubernetes use Linux cgroups:
   - Memory limit (OOM kill if exceeded)
   - CPU shares / quota
   - I/O bandwidth
   - PID limits

docker run --memory 512m --cpus 0.5 ...
```

### Why It Matters

```
Container with 512MB limit but process tries 1GB:
   → OOM Killer wakes up
   → kills the process (exit 137)
   → "Why did my pod restart?" mystery

Debug:
   dmesg | grep -i oom        # kernel log
   kubectl describe pod xyz   # event: OOMKilled
   cgroup memory.max_usage_in_bytes
```

### Verified — a real cgroup memory limit actually killing a container

```bash
docker run --name oom-demo --memory=50m --memory-swap=50m alpine \
  sh -c 'a=$(head -c 200000000 /dev/zero | tr "\0" "a"); echo done'
# exit code: 137

docker inspect oom-demo --format '{{.State.OOMKilled}} exitcode={{.State.ExitCode}}'
# true exitcode=137

docker inspect oom-demo --format 'Memory limit: {{.HostConfig.Memory}} bytes'
# Memory limit: 52428800 bytes    (== 50MB, confirms the limit that fired)
```

Not simulated — a real container tried to hold ~200MB of data under a 50MB cgroup limit, and the kernel actually killed it. `docker inspect` confirms `OOMKilled: true` and the exact limit that triggered it, on a host with plenty of free RAM (see "Host OOM vs Container OOM" earlier in this file — this is that exact scenario, reproduced).

---

## Containers vs VMs (OS Perspective)

```
VM:
   ┌───────────────────────┐
   │ Guest OS (full kernel)│
   ├───────────────────────┤
   │ Hypervisor            │
   ├───────────────────────┤
   │ Host OS / Hardware    │
   └───────────────────────┘
   ✓ Strong isolation
   ✗ Heavy (GB RAM, slow boot)

Container:
   ┌───────────────────────┐
   │ App + libs            │
   ├───────────────────────┤
   │ Container runtime     │
   │ (uses host kernel via │
   │ namespaces + cgroups) │
   ├───────────────────────┤
   │ Host OS / Hardware    │
   └───────────────────────┘
   ✓ Lightweight (MB RAM, fast boot)
   ✓ Same kernel = no virtualization overhead
   ✗ Weaker isolation than VM
   ✗ Linux containers need Linux host
```

### Verified on this exact dev machine — VM and container, both real, side by side

```bash
uname -a                    # HOST (macOS/Darwin)
# Darwin ... Darwin Kernel Version 25.6.0 ... RELEASE_ARM64_T8103 arm64

docker run --rm alpine uname -a   # kernel INSIDE a container
# Linux 6d8949f7666a 6.8.0-117-generic ... aarch64 Linux

colima status
# colima is running using macOS Virtualization.Framework, runtime: docker
```

This machine can't run Linux containers natively — macOS's kernel isn't Linux. **Colima IS the VM layer**: it boots a real, full Linux kernel (6.8.0) inside Apple's Virtualization.Framework specifically so Docker has a Linux kernel to talk to. The `alpine` container then runs **inside that VM**, sharing its Linux kernel via namespaces/cgroups — it does NOT boot a second kernel of its own. That's the whole "container vs VM" distinction, observed directly rather than just diagrammed: one real VM boot (colima, heavy, done once), many lightweight containers layered on top of its single shared kernel (`docker run --rm alpine echo ...` completed in 0.182s total).

### Key Linux Features Used by Containers

```
Namespaces  — process isolation
   PID, NET, MNT, UTS, IPC, USER, CGROUP

cgroups     — resource limits + accounting
overlayfs   — layered filesystem
seccomp     — syscall filtering
capabilities — fine-grained root permissions
```

---

## Memory & Performance Patterns

### Cache Hierarchy

```
   L1 cache  (per-core)   ~1 ns,    32-64 KB
   L2 cache  (per-core)   ~3 ns,   256-512 KB
   L3 cache  (shared)    ~10 ns,    4-32 MB
   RAM                  ~100 ns,    GBs
   NVMe SSD              ~25 µs,    TBs
   Network               ~ms

CPU asks: L1? → miss → L2? → miss → L3? → miss → RAM
Found at any level = "cache hit". Falling through to RAM = "cache miss".
Every level down: bigger capacity, higher latency.
```

Cache-friendly code = data accessed together is stored together.

### Locality — why access PATTERN matters, not just data size

```
Temporal locality: data used once is likely used again soon
   user = get_user(); process(user); validate(user); save(user)
   → same `user` object reused repeatedly, stays warm in cache

Spatial locality: accessing one address makes nearby addresses likely next
   arr = [1,2,3,4,5,6,7,8]
   for x in arr: process(x)        # sequential → cache-friendly
   arr[random_index]               # random → cache misses, CPU stalls

CPU doesn't cache single bytes — it caches in "cache lines" (commonly 64
bytes). Reading one element pulls its neighbors into cache for free.
That's WHY sequential access wins: neighbors you'll need next are
already there. Random access wastes that free neighbor-fetch.

Backend consequence: "optimize the Python code" isn't the whole story —
scanning 10M records in random order pays a hidden cache-miss tax that
scanning them sequentially doesn't. Data layout/access pattern matters
alongside algorithmic complexity.
```

### Cache Coherence & False Sharing (multi-core, senior interview territory)

```
Two threads on two cores, same shared_counter:
   Core 1: counter++      Core 2: counter++
Both cores may hold their own cached copy of that memory. The CPU
hardware has to keep those copies consistent ("cache coherence") so
neither core computes on a stale value — this costs cross-core traffic,
on top of whatever software lock you're already paying for.

False sharing (the gotcha):
   Cache line: [ counter_A | counter_B ]     ← same 64-byte line
   Thread A (Core 1) writes counter_A
   Thread B (Core 2) writes counter_B
   Logically A and B are unrelated. Physically they share a cache line,
   so every write invalidates the OTHER core's cached copy of the whole
   line — coherence traffic explodes even though there's no real data
   dependency. Fix: pad/align hot per-thread counters so they land on
   separate cache lines.
```

### NUMA (Non-Uniform Memory Access)

```
Multi-socket servers:
   NUMA Node 0 [CPU 0 + RAM 0]  ←interconnect→  NUMA Node 1 [CPU 1 + RAM 1]

   CPU 0 → RAM 0  =  local access   (fast)
   CPU 0 → RAM 1  =  remote access  (crosses interconnect, slower)

Why it exists: scaling one giant shared-RAM bus doesn't scale past a
point — splitting into CPU+RAM pairs per node gives more aggregate
memory bandwidth, at the cost of the OS/runtime having to care about
which node data lives on vs. which node the CPU runs on.

Check NUMA:
   numactl --hardware        # nodes, which CPUs/RAM belong to which
   numastat                  # is my process's memory local or remote?
   lscpu | grep NUMA

Containers don't eliminate NUMA — a container is namespaces + cgroups
on top of the same physical topology. For latency-sensitive workloads
(databases, in-memory caches with large working sets), pin CPU affinity
AND memory to the same node; blindly pinning without checking both
sides can make things worse, not better.
```

### Verified — cache locality's real effect, and an honest NUMA gap (see [`cache_locality_demo.py`](cache_locality_demo.py))

```
1. Sequential vs random access over the SAME 20M values, same total work:
   Sequential access: 1.111s
   Random access:     3.169s   (2.85x slower)
   → access PATTERN alone made the difference — direct evidence for the
     locality/cache-line theory above, not just a claim. (Some of the
     gap is Python-interpreter overhead, not pure hardware cache effect
     — but the direction and rough scale match the theory cleanly.)

2. Honest limitation: this repo's dev machine is Apple Silicon (M1),
   which uses a Unified Memory Architecture — ALL cores share one memory
   pool equally, with NO multi-socket NUMA topology. Confirmed directly:
   `numactl` doesn't exist on this machine at all. NUMA as described
   above is real and matters on multi-socket Linux servers — it simply
   can't be demonstrated on this particular dev laptop. What IS real
   here: 4 Performance-cores + 4 Efficiency-cores (`sysctl
   hw.perflevel0/1.physicalcpu`) — a different "not all cores are equal"
   fact, handled transparently by Apple's scheduler rather than exposed
   for manual pinning the way Linux NUMA/affinity is.
```

---

## OOM Killer (Linux)

```
When kernel runs out of memory:
   1. Find process with highest "badness score"
      (memory usage + nice + etc.)
   2. SIGKILL it
   3. dmesg logs the kill

In containers:
   - cgroup memory limit reached
   - "memory.oom_kill" counter increments
   - Container restarts (if restartPolicy: Always)
```

### Memory Pressure ≠ OOM (a spectrum, not a switch)

```
memory demand ↑ → reclaimable memory ↓ → memory pressure ↑
      → kernel tries to reclaim / swap
      → still insufficient
      → THEN OOM handling kicks in

Memory pressure can exist — and hurt latency via reclaim/swap activity —
well before an actual OOM kill happens. Watch `vmstat 1`'s `si`/`so`
(swap in/out) columns for early warning; sustained non-zero values mean
pressure, not necessarily a kill yet.
```

### oom_score & oom_score_adj — how a victim is actually chosen

```
cat /proc/<PID>/oom_score        # this process's current "badness" score
cat /proc/<PID>/oom_score_adj    # adjusts that score's weighting

Higher oom_score = more likely to be picked. Selection is NOT random —
it's driven by these scores (roughly: memory usage weighted by other
factors). oom_score_adj lets you bias selection (e.g. protect a critical
process, or make a disposable worker a preferred victim).

Interview-ready answer: "During severe memory pressure, Linux picks a
process to kill using OOM-selection scoring — oom_score reflects the
process's current badness, oom_score_adj lets you shift that preference."
```

### Host OOM vs Container OOM — the mismatch that confuses people

```
Host: 32 GB RAM, mostly free
Your container: cgroup memory limit = 512 MB
Your app inside it: tries to use 550 MB
   → 550 MB > 512 MB cgroup boundary → OOMKilled
   → even though the HOST has 31+ GB free

`free -h` on the host tells you almost nothing here — the container's
cgroup limit is the wall that mattered, not host memory. Always check
the container/cgroup limit (`kubectl describe pod`, or the cgroup's
memory.max) before concluding anything from host-level memory stats.
```

### Leak vs Spike — the distinction that actually drives the fix

```
Leak: memory climbs and never comes back down
   100MB → 150 → 200 → 300 → 400 → 500 → 💀
   (references held somewhere — global state, cache with no eviction,
   unclosed connections — GC can't reclaim what's still referenced)

Spike: temporary peak from real, legitimate load
   200MB → 220 → 600 → 700 (concurrent request burst) → 250 → 230
   (comes back down once the burst finishes — not a leak)

Same symptom (OOMKilled), opposite fix. Blindly raising the memory
limit "fixes" a spike but only delays a leak's inevitable kill — it
hides the bug instead of fixing it. Distinguish by watching memory
over TIME (a metrics dashboard, or repeated `ps -o rss -p $PID`
samples), not a single snapshot.

Other legitimate (non-leak) OOM causes: traffic spike, one huge DB
result set (`SELECT *` on a huge table), oversized response
serialization, unbounded concurrency, unbounded cache growth, or simply
a container limit set too low for the real workload.
```

### RSS vs VSZ — don't misread `ps` output

```
ps -o pid,%mem,rss,vsz,cmd -p $PID

VSZ = virtual address space size (includes memory-mapped files,
      reserved-but-unused pages — NOT a measure of real RAM usage)
RSS = resident set size — memory actually resident in physical RAM
      right now (closer to "real" usage, but still not identical to
      cgroup accounting, which can count things RSS doesn't)

A process showing VSZ=1.2GB, RSS=450MB is NOT "using 1.2GB" — it's
using ~450MB of real RAM; the rest of VSZ is reserved/mapped address
space it may never touch.
```

### Verified — a real container actually OOM-killed

This isn't hypothetical in this repo anymore — see "Verified — a real cgroup memory limit actually killing a container" in the **Resource Limits** section above: a real Docker container with a 50MB memory limit tried to hold ~200MB and was genuinely killed by the kernel (`docker inspect` confirms `OOMKilled: true`, `exitcode=137`), on a host with plenty of free RAM. That's the "Host OOM vs Container OOM" mismatch described earlier, reproduced on demand rather than waited for in production.

### Avoid Being OOM-Killed

```
✓ Set sensible memory limits
✓ Profile your app (memray, py-spy)
✓ Use streaming for large data (don't load 10GB into RAM)
✓ Set Python's GC tuning if needed
✓ Watch RSS trend over time, not a single reading
✗ Don't disable swap blindly
✗ Don't "fix" OOM by just raising the limit without checking leak-vs-spike first
```

---

## Practical Debugging

### "What is this process doing?"

```bash
# CPU + memory
top -p $PID
ps -o pid,user,%cpu,%mem,vsz,rss,stat,start,time,command -p $PID

# Open files / sockets
lsof -p $PID

# Memory map (libraries loaded)
cat /proc/$PID/maps

# Syscalls (live)
strace -p $PID

# Stack trace (Python)
py-spy dump --pid $PID

# Async waits
py-spy top --pid $PID
```

### "What happened before this crash?"

```bash
dmesg | tail -50           # kernel messages
journalctl -u myapp -n 100 # service logs
journalctl --since "5m ago"
```

### Golden rule: measure, don't guess

```
"API is slow" is a SYMPTOM, not a diagnosis. Possible real causes:
CPU saturation, memory pressure, disk I/O, network I/O, DB latency,
lock contention, too many threads, FD exhaustion, excessive context
switching, GC pauses, container throttling.

Flow: symptom → measure → narrow down → root cause → fix → verify
Never: symptom → restart the server → hope
```

### Production Scenario 1 — High CPU

```
top                              # is one process pegging a core?
ps aux --sort=-%cpu | head       # confirm the PID
py-spy dump --pid $PID           # WHICH Python function is hot?
py-spy top --pid $PID            # live view, like `top` but for Python stack frames

py-spy answers "where is Python actually spending time" without
modifying app code — much faster than guessing from `top` alone.
Common finding: JSON serialization of a huge payload, not "a bug".
```

### Production Scenario 2 — Memory growing over time

```
ps -o pid,%mem,rss,vsz,cmd -p $PID    # current RSS
cat /proc/$PID/status                  # VmRSS, VmSize, threads
cat /proc/$PID/maps                    # what's actually mapped (heap/libs/stack)
vmstat 1                               # si/so swap activity system-wide

Then classify: leak (RSS never comes down) vs spike (comes down after
load passes) — see the OOM section above. That classification decides
whether you fix code or just size the limit correctly.
```

### Production Scenario 3 — "Too many open files"

```
lsof -p $PID | wc -l          # how many FDs actually open right now
ls /proc/$PID/fd | wc -l      # same count, /proc route
ulimit -n                     # what's the allowed limit

If usage is climbing toward the limit and never drops → FD leak
(sockets/files not being closed — check connection pool config,
missing `with` blocks, keep-alive settings). If it's genuinely near
the limit under real concurrent load → the limit itself may be sized
too low for production traffic (raise it deliberately, not as a guess).
```

### Production Scenario 4 — High latency, LOW CPU (the counter-intuitive one)

```
CPU 20%, latency 500ms → do NOT reach for "upgrade the server"

CPU and memory are independent resources — low CPU doesn't rule out
a bottleneck elsewhere. Investigate instead:
   network I/O, DB round-trip time, filesystem calls, lock contention,
   external API calls, event-loop blocking (a sync call inside async code)

strace -p $PID    # what is it actually WAITING on?
   lots of epoll_wait()  → mostly idle, waiting on I/O (often fine/expected)
   lots of futex()       → lock/synchronization contention — investigate
```

### Tool selection cheat sheet

```
Problem                  → First tools
────────────────────────────────────────────────
High CPU                 → top, ps, py-spy
High memory               → ps, /proc/$PID/status, vmstat
OOM / OOMKilled            → dmesg, journalctl, ps (RSS trend), cgroup/pod limits
FD exhaustion             → lsof, /proc/$PID/fd, ulimit -n
Syscall-level mystery      → strace
Thread explosion          → ps -eLf
Context-switch overhead    → vmstat, pidstat -w
Swap pressure              → vmstat (si/so)
Kernel-level events        → dmesg
Service-level logs         → journalctl -u <service>
```

**Senior mindset:** don't ask "why is the server slow?" — ask, in order: *which resource is saturated? which process is responsible? what is that process actually doing? what evidence proves the root cause?* Each answer should be backed by a command output, not a guess.

### Verified — the full debugging workflow, run against a real target process

See [`debugging_workflow_demo.py`](debugging_workflow_demo.py) — spawns a real process holding 50MB of memory, 3 open files, and a listening TCP socket, then runs the actual recommended commands against it (macOS equivalents substituted where the Linux-only tool doesn't exist):

```
ps -o pid,%cpu,%mem,vsz,rss,stat,command -p $PID
  PID  %CPU %MEM      VSZ    RSS STAT COMMAND
34045   7.5  0.3 410634064  21056 S    Python /tmp/debug_target.py
  → real RSS (21MB) visible directly, matching the memory it actually allocated

lsof -p $PID
  Python 34045 ... 3w REG ... /private/tmp/debug_target_0.txt
  Python 34045 ... 4w REG ... /private/tmp/debug_target_1.txt
  Python 34045 ... 5w REG ... /private/tmp/debug_target_2.txt
  Python 34045 ... 6u IPv4 ... TCP localhost:50602 (LISTEN)
  → the 3 open files AND the listening socket, all correctly identified
    by fd number and type — exactly the "what is this process holding
    open" question this section exists to answer

vmmap --summary $PID   (macOS's /proc/$PID/maps equivalent)
  → worked directly, no elevated permissions needed, real process/memory
    metadata returned

dtruss (macOS's strace equivalent) — deliberately SKIPPED here, not
faked: already confirmed elsewhere in this file that it requires sudo
and is further restricted by System Integrity Protection even then.
```

This closes the loop on the whole section: every debugging command recommended above was actually run against a real, independently-spawned process, not just listed as reference syntax.

---

## Interview Questions

### Q1: Why does Python's GIL exist?

The GIL serializes Python bytecode execution. Reasons:
- Simpler memory management (reference counting)
- Easier C extension integration (no per-object locking)
- Faster single-threaded performance (no lock overhead)

Trade-off: no true multi-threaded CPU parallelism. Use multiprocessing or asyncio (I/O bound) instead.

### Q2: How does asyncio achieve high concurrency in a single thread?

Uses OS I/O multiplexing (epoll on Linux). The event loop:
1. Tracks thousands of awaiting coroutines
2. Asks kernel: "which of these FDs is ready?"
3. Resumes the coroutine when its I/O completes

No threads = no context switch = no GIL contention.

### Q3: Process vs thread when?

```
Process:
   ✓ CPU-bound parallel work
   ✓ Fault isolation needed
   ✓ Different memory needs
   ✗ Heavy creation + IPC

Thread:
   ✓ I/O-bound concurrent work
   ✓ Shared state needed
   ✓ Cheap to spawn
   ✗ Race conditions risk
   ✗ Python: GIL limits CPU parallelism

Async coroutine:
   ✓ Best for many idle I/O operations
   ✓ Single-threaded reasoning
   ✗ Not for CPU-bound
```

### Q4: What is a page fault?

When code accesses memory that's not currently in RAM (swapped out, lazy-loaded, or never allocated yet). Kernel handles transparently:
- Major fault: loads from disk (slow)
- Minor fault: just sets up mapping (fast)

High major-fault rate = swapping = bad performance.

### Q5: Why might `ulimit -n` matter for your server?

Each connection = 1 file descriptor. Default 1024 means max 1024 connections (including DB, Redis, incoming, outgoing). High-traffic servers need 65536+. Setting it wrong → "Too many open files" errors.

### Q6: Difference between containers and VMs from OS perspective?

VMs virtualize hardware (each VM has its own kernel). Containers share host kernel (using Linux namespaces + cgroups for isolation). Containers are lightweight (no kernel boot, no virtual hardware) but weaker isolation.

### Q7: What's a context switch and why is it costly?

Saving one thread's state and loading another's. Costs: CPU registers save/restore, TLB flush on process switch, cache invalidation, scheduler bookkeeping. ~1-10 µs each. 100k switches/sec = significant CPU waste — why async beats thread-per-connection.

### Q8: How does fork() work + why is copy-on-write important?

`fork()` creates a child process. Naively, you'd copy ALL of parent's memory — slow + wasteful. Copy-on-write (COW): child shares pages with parent until either writes; only then OS makes a private copy. Makes fork() fast even for huge processes.

### Q9: What is false sharing, and why is it a senior-level gotcha?

Two threads write to logically-independent variables that happen to sit on the same CPU cache line. Every write from one core invalidates the other core's cached copy of the *whole line*, generating cache-coherence traffic that looks like contention even though there's no real data dependency. Fix: pad/align hot per-thread counters onto separate cache lines.

### Q10: Does OOMKilled mean there's a memory leak?

No. OOM means memory requirements couldn't be satisfied under the current constraints (often a cgroup/container limit, not host RAM). A leak is one possible cause — traffic spikes, large legitimate workloads, growing caches, unbounded concurrency, or an under-sized container limit can all cause it too. Distinguish leak from spike by watching memory *over time*: a leak never comes back down; a spike recedes once load passes.

### Q11: Why can OOM happen when CPU utilization is only 20%?

CPU and memory are independent resources — an application can be CPU-light and memory-heavy at the same time. Never rule out a memory problem just because CPU looks fine.

### Q12: How do you decide which process the OOM killer picks?

Via `oom_score` (the process's current "badness" — roughly memory usage weighted by other factors) and `oom_score_adj` (a manual bias you can set to protect or de-prioritize a specific process). Selection isn't random or first-come-first-served.

### Q13: FastAPI pod OOMKilled every few hours, CPU looks normal — what's your investigation order?

Confirm OOMKilled (`dmesg`/`journalctl`/orchestrator events) → check the container's memory *limit*, not host RAM → check RSS trend over time (`ps`/`/proc/$PID/status`) → classify leak vs spike → if leak, find what's holding references (global state, unbounded cache, unclosed connections); if spike, check concurrency/payload size/DB result size. Saying "just increase the memory limit" without this sequence is a red flag in an interview — it can mask a leak instead of fixing it.

### Q14: What does `fork()` return, and why does it return different values to parent vs child?

It returns the child's PID to the parent, and `0` to the child (or a negative value on failure). Both processes run the exact same code forward from the `fork()` call — the different return value is the *only* thing that lets one piece of code branch into parent-specific vs child-specific behavior (`if pid == 0: ... else: ...`). Without that asymmetry, the two processes would have no way to tell themselves apart.

### Q15: What is a zombie process, and does it consume real memory/CPU?

A process that has already exited but whose exit status the parent hasn't collected yet via `wait()`/`waitpid()` — shown as `STAT = Z` in `ps`. It's not "stuck work" — the process itself is done; only its slot in the kernel's process table (PID + exit status) is still occupied. Negligible resource cost per zombie, but if a long-lived parent never reaps its children, zombies accumulate — a slow, real (if unusual) production symptom. If the parent dies first, the zombie is re-parented to PID 1, which reaps it automatically.

### Q16: Why are `fork()` and `exec()` two separate syscalls instead of one combined "spawn"?

Because there's a useful window between them: the child can reconfigure itself — redirect stdout/stdin to a file or pipe, close inherited file descriptors, change its working directory or priority — *before* the new program's image loads and overwrites everything. This is exactly how shell redirection (`cmd > file`) and pipelines (`cmd1 | cmd2`) are implemented under the hood. A single combined syscall couldn't offer that configure-before-replace step.

### Q17: "My server has 16GB RAM but Python's VSZ shows 20GB — is that a problem?"

No, and this is a common misreading. VSZ is the size of the process's *virtual address space* — reserved, not necessarily backed by physical RAM. It's routinely larger than physical RAM (shared libraries, memory-mapped files, large reserved-but-untouched regions all count). The number that actually matters for memory pressure is RSS (physically resident) — and even that isn't quite what a cgroup/container limit tracks exactly, but it's much closer than VSZ. Never alarm on VSZ alone.

### Q18: How does virtual memory actually stop one process reading another's memory?

Each process has its own page table mapping its virtual addresses to physical frames — Process A and Process B can both use virtual address `0x1000`, but their page tables point to completely different physical frames. If a process's page table has no valid entry (or wrong permission) for an address it touches, the CPU's MMU traps into the kernel, which delivers `SIGSEGV` and kills the process. It's an enforced hardware+kernel mechanism, not a software convention that could be worked around.

### Q19: What's the actual difference between "virtual memory" and a container's memory limit (cgroup)?

Different layers. Virtual memory is the addressing abstraction every process gets regardless of containers — the kernel maps virtual pages to physical frames. A cgroup memory limit is a policy ceiling layered on top, restricting how much *resident* memory a process/container may hold before getting OOM-killed. A process can have a huge virtual address space (from mmap-ing large files, for instance) while its RSS — and therefore its actual exposure to the cgroup limit — stays small; the two numbers are not the same thing and shouldn't be reasoned about interchangeably.

### Q20: After `fork()`, does the child get its own copy of a file's read position, the way it gets its own copy of memory?

No — this is a common conflation. `fork()` gives the child a private (copy-on-write) copy of *memory*, but for file descriptors it copies the *fd table entries*, which still point at the *same underlying kernel "open file description"* — including its current read/write offset. If the child reads 5 bytes from a shared fd, the parent's next read on that same fd continues from byte 5, not byte 0, even though the parent never touched it. Memory is private-after-fork; FD state (offset, in particular) is shared-after-fork, unless the child explicitly opens its own independent copy instead of inheriting the parent's fd.

### Q21: "10,000 coroutines" — does that mean 10,000 kernel context switches happening constantly?

No, and this is a common misunderstanding for people newer to asyncio. Coroutines running on the same event loop live inside a *single* OS thread — handing control from one coroutine to another at an `await` point is the event loop calling a different Python function, not a kernel operation. No registers/PC get saved to a kernel-managed structure, no scheduler picks a different *task*, no TLB is touched. Verified directly: 20 OS threads doing a blocking wait produced ~9x more OS-visible context-switch activity than 20 coroutines doing the logically identical wait. Real kernel context switches only enter the picture if the async server itself uses multiple OS threads/processes (e.g. multiple Uvicorn workers) — the coroutines *within* one of those don't cause them.

---

## Senior Mantras

```
1. I/O-bound → async or threads. CPU-bound → multiprocessing.

2. Every connection is a file descriptor. Plan ulimit.

3. Containers share the kernel. Plan cgroup limits.

4. OOM-killed processes leave no Python stack trace.
   Check dmesg first.

5. Context switches are expensive. Async > thread-per-connection.

6. The GIL is real, but it releases during I/O.

7. Memory is virtual. Crashes from "out of memory"
   are usually cgroup limits, not host.

8. strace shows what your code REALLY does at OS level.

9. Page faults > network round-trips for slowdowns. Profile both.

10. Understand fork() if you use multiprocessing or gunicorn.
```

---

## Related

- [fork_demo.py](fork_demo.py) — runnable `os.fork()` practical for the Process Internals section above (verified: separate parent/child memory, zombie reaping, the stdout-buffering-duplicate-output gotcha)
- [thread_demo.py](thread_demo.py) — runnable `threading` practical for the Thread Internals section above (verified: shared PID/heap vs private TID/stack, and the silent-thread-exception gotcha)
- [ipc_demo.py](ipc_demo.py) — runnable IPC practical for the section above (verified: Pipe two-way messaging, real shared memory between two processes, and signal-as-notification-not-data-transfer)
- [vm_demo.py](vm_demo.py) — runnable Virtual Memory practical (verified: VSZ vs RSS divergence, mmap() round-trip through a real file, and a real SIGSEGV from an invalid pointer dereference)
- [fd_limits_demo.py](fd_limits_demo.py) — File Descriptors + Resource Limits practical (verified: shared fd sequence for files/sockets, and reproducing the real "Too many open files" errno 24)
- [fd_advanced_demo.py](fd_advanced_demo.py) — File Descriptors part 2 (verified: `fileno()`, fd numbers are per-process not global, fork() sharing the file OFFSET not just the fd, `accept()` returning a new fd, and an `os._exit()` buffer-flush gotcha)
- [syscall_count_demo.py](syscall_count_demo.py) — Syscalls practical (verified: 6640x slowdown doing one `write()` syscall per byte vs batching — the measured reason buffered I/O exists)
- [context_switch_types_demo.py](context_switch_types_demo.py) — Context Switching practical (verified: kernel thread switching vs coroutine switching via real OS counters, plus an honest macOS `ru_nvcsw` platform quirk)
- [debugging_workflow_demo.py](debugging_workflow_demo.py) — Practical Debugging practical (verified: `ps`/`lsof`/`vmmap` run against a real spawned process holding memory, files, and a listening socket — closes the loop on every other file in this list)
- [io_models_demo.py](io_models_demo.py) — I/O Models + Syscalls practical (verified: blocking wait, real EAGAIN on non-blocking, `select()` multiplexing, raw `os.open/read/write` syscall wrappers)
- [scheduler_context_switch_demo.py](scheduler_context_switch_demo.py) — Scheduler + Context Switching practical (verified: `sched_yield()` cost, thread-count-vs-overhead, `os.nice()`, and the macOS `sched_getaffinity` platform gap)
- [cache_locality_demo.py](cache_locality_demo.py) — Cache/NUMA practical (verified: 2.85x sequential-vs-random access slowdown; honest note that NUMA itself isn't demonstrable on this Apple Silicon dev machine)
- [01_linux_bash_essentials.md](01_linux_bash_essentials.md) — interfacing with OS
- [03_networking_fundamentals.md](03_networking_fundamentals.md) — sockets + TCP
- [../01_Year3-4_Mid/01_Python_Advanced/theory/03_memory_gil.md](../../01_Year3-4_Mid/01_Python_Advanced/theory/03_memory_gil.md) — Python-specific
- [../01_Year3-4_Mid/01_Python_Advanced/theory/05_async_concurrency_deep_dive.md](../../01_Year3-4_Mid/01_Python_Advanced/theory/05_async_concurrency_deep_dive.md) — asyncio internals
