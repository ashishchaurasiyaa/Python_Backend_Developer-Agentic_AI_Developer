# Foundations — Operating System Concepts for Backend Devs
**Phase 0 Foundations | Zero → Senior**

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

---

## Context Switching

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

---

## Inter-Process Communication (IPC)

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
```

Cache-friendly code = data accessed together is stored together.

### NUMA (Non-Uniform Memory Access)

```
Multi-socket servers:
   CPU 0 → fast access to local RAM
   CPU 0 → slower access to "remote" RAM (other socket)

Check NUMA:
   numactl --hardware
   lscpu | grep NUMA

For latency-sensitive apps, bind to one NUMA node.
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

### Avoid Being OOM-Killed

```
✓ Set sensible memory limits
✓ Profile your app (memray, py-spy)
✓ Use streaming for large data (don't load 10GB into RAM)
✓ Set Python's GC tuning if needed
✗ Don't disable swap blindly
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

- [01_linux_bash_essentials.md](01_linux_bash_essentials.md) — interfacing with OS
- [03_networking_fundamentals.md](03_networking_fundamentals.md) — sockets + TCP
- [../Phase1_Python_Advanced/theory/03_memory_gil.md](../Phase1_Python_Advanced/theory/03_memory_gil.md) — Python-specific
- [../Phase1_Python_Advanced/theory/05_async_concurrency_deep_dive.md](../Phase1_Python_Advanced/theory/05_async_concurrency_deep_dive.md) — asyncio internals
