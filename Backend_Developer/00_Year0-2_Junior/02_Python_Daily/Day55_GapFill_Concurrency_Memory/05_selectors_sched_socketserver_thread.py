"""
DAY 55 — selectors (DEEP: asyncio ka engine), sched, socketserver, _thread
Architecture Level: Mid → Senior Python Backend

WHY THIS MATTERS:
- Interview ka GOLD question: "asyncio andar se kaise kaam karta hai?"
  Jawab ka core hai `selectors` module — OS ko bolo "in 10,000 sockets me se
  jis pe data aaye, mujhe batana" → EK thread me hazaaron connections.
- Threads-per-connection model C10K problem pe mar jaata hai (10k threads =
  10k stacks + context-switch storm). I/O multiplexing (select/epoll/kqueue)
  isi liye bana — aur Python me uska clean wrapper hai `selectors`.
- Baaki teen (sched, socketserver, _thread) chhote corners hain — legacy code
  aur stdlib internals me dikhte hain, awareness-level par interviews me
  "http.server kis pe bana hai?" jaise side-questions aate hain.

BIG PICTURE:
    raw socket loop      → 1 connection at a time (blocking recv)
    thread-per-conn      → N connections = N threads (socketserver ThreadingMixIn)
    selectors            → 1 thread, N connections (event-driven) ← asyncio ki neev
    asyncio              → selectors + event loop + coroutines (nice API upar)

NOTE: Saare network demos localhost pe self-contained hain (port 0 = OS-assigned),
koi external dependency nahi. Threads sirf demo-clients banane ke liye use kiye
hain — selector loop khud SINGLE thread me chalta hai (wahi to point hai!).
"""

import selectors
import socket
import sched
import socketserver
import threading
import _thread
import time
import sys


# ============ SECTION 1: selectors — DEEP (asyncio ka foundation) ============
#
# PROBLEM: blocking I/O
#   data = conn.recv(1024)   # ← thread YAHIN atak gaya jab tak data na aaye
#   2 clients? Dusra wait karega. Solution #1: thread per client (mehenga).
#   Solution #2: OS se poocho "kaunse sockets READY hain?" → sirf unhi pe
#   recv() karo (jo ready hai wo block NAHI karega). Yehi I/O multiplexing hai.
#
# OS-LEVEL MECHANISMS (selectors inhi ko wrap karta hai):
#
#   ┌──────────┬───────────────┬────────────┬─────────────────────────────────┐
#   │ Syscall  │ Platform      │ Complexity │ Notes                           │
#   ├──────────┼───────────────┼────────────┼─────────────────────────────────┤
#   │ select   │ sab jagah     │ O(n)       │ Har call pe PURI fd list kernel │
#   │          │ (POSIX+Win)   │            │ ko copy + scan. FD_SETSIZE      │
#   │          │               │            │ limit (~1024 fds). Oldest.      │
#   ├──────────┼───────────────┼────────────┼─────────────────────────────────┤
#   │ poll     │ POSIX         │ O(n)       │ 1024 limit gaya, par har call   │
#   │          │ (Windows NahI)│            │ pe ab bhi pura scan → 10k conn  │
#   │          │               │            │ pe slow.                        │
#   ├──────────┼───────────────┼────────────┼─────────────────────────────────┤
#   │ epoll    │ Linux only    │ O(1)*      │ Kernel me interest-list EK BAAR │
#   │          │               │ (ready fds │ register, kernel khud ready fds │
#   │          │               │  ke prop.) │ ki list deta hai. nginx/Redis/  │
#   │          │               │            │ uvloop sab isi pe.              │
#   ├──────────┼───────────────┼────────────┼─────────────────────────────────┤
#   │ kqueue   │ macOS/BSD     │ O(1)*      │ epoll ka BSD bhai. Files, sock, │
#   │          │               │            │ signals, timers sab events.     │
#   ├──────────┼───────────────┼────────────┼─────────────────────────────────┤
#   │ IOCP     │ Windows       │ O(1)*      │ Completion-based (readiness     │
#   │          │               │            │ nahi). selectors me NAHI —      │
#   │          │               │            │ asyncio ProactorEventLoop use   │
#   │          │               │            │ karta hai (Win default 3.8+).   │
#   └──────────┴───────────────┴────────────┴─────────────────────────────────┘
#
#   KEY INSIGHT: select/poll me kernel ko HAR BAAR puri list scan karni padti
#   hai (O(n) per call) — epoll/kqueue me kernel events PUSH karta hai, tum
#   sirf ready wale process karte ho. 10,000 idle connections + 10 active:
#   select = 10,000 checks, epoll = 10 events. Yehi C10K ka solution tha.
#
# selectors.DefaultSelector = "is OS pe jo BEST hai wo do":
#   Linux → EpollSelector, macOS/BSD → KqueueSelector,
#   fallback → PollSelector → SelectSelector
#
# API (bas 4 cheezein yaad rakho):
#   sel.register(fileobj, events, data=...)  # interest declare karo
#       events = selectors.EVENT_READ / EVENT_WRITE (| se combine)
#       data   = kuch bhi attach karo (callback, state, addr...) — TUMHARA bag
#   sel.select(timeout)  → [(key, mask), ...]  sirf READY fds
#       key.fileobj = socket, key.data = jo tumne attach kiya
#   sel.unregister(fileobj)  # interest hatao (close se PEHLE!)
#   sel.close()

def demo_selectors_deep():
    print("=" * 60)
    print("SECTION 1: selectors — single-thread multi-client echo")
    print("=" * 60)

    print(f"Is OS ka best selector: {selectors.DefaultSelector().__class__.__name__}")
    # Linux pe 'EpollSelector', macOS pe 'KqueueSelector' print hoga.

    sel = selectors.DefaultSelector()

    # --- Listening socket (port 0 = OS koi bhi free port de de) ---
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.bind(('127.0.0.1', 0))
    listener.listen()
    listener.setblocking(False)        # CRITICAL: selector loop me sab non-blocking
    port = listener.getsockname()[1]

    # data=None ka matlab "ye listener hai" — accept karna hai, recv nahi.
    sel.register(listener, selectors.EVENT_READ, data=None)

    # --- 3 demo clients (alag threads me, sirf traffic generate karne ko) ---
    # NOTE: server side SINGLE thread hai. Clients threads me isliye hain
    # taaki ek hi script me dono roles chal sakein.
    def client(i):
        with socket.create_connection(('127.0.0.1', port)) as c:
            c.sendall(f"hello-from-client-{i}".encode())
            reply = c.recv(1024)
            print(f"   client-{i} ko echo mila: {reply.decode()!r}")

    for i in range(3):
        threading.Thread(target=client, args=(i,), daemon=True).start()

    # --- THE EVENT LOOP (yehi asyncio ka dil hai, haath se likha hua) ---
    closed = 0
    deadline = time.time() + 5          # safety: demo kabhi hang na ho
    while closed < 3 and time.time() < deadline:
        events = sel.select(timeout=1)  # BLOCK: "koi bhi registered fd ready ho to jagao"
        for key, mask in events:
            if key.data is None:
                # Listener ready = naya connection aaya → accept + register
                conn, addr = key.fileobj.accept()
                conn.setblocking(False)
                sel.register(conn, selectors.EVENT_READ, data=addr)
                print(f"   [loop] naya client registered: {addr}")
            else:
                # Client socket ready = data aaya (ya client ne close kiya)
                conn = key.fileobj
                data = conn.recv(1024)          # ready hai → block NAHI karega
                if data:
                    conn.sendall(data.upper())  # echo (uppercase, taaki dikhe)
                else:
                    # recv() ne b'' diya = peer ne connection close kiya
                    sel.unregister(conn)        # PEHLE unregister, PHIR close
                    conn.close()
                    closed += 1
                    print(f"   [loop] client {key.data} closed ({closed}/3)")

    sel.unregister(listener)
    listener.close()
    sel.close()
    print("   → 3 clients, EK server thread, ZERO server-side threads. Yehi magic hai.")

    # --- ASYNCIO CONNECTION (interview gold) ---
    # asyncio.SelectorEventLoop andar se BILKUL upar wala loop hai (simplified):
    #
    #   while True:
    #       timeout = next_timer_deadline - now          # call_later/sleep ke timers
    #       events = self._selector.select(timeout)      # ← YEHI selectors module!
    #       for key, mask in events:
    #           self._ready.append(key.data)             # data = (reader/writer callback)
    #       while self._ready:
    #           handle = self._ready.popleft()
    #           handle._run()                            # callback → coroutine.send()
    #                                                    #   → coroutine agle await tak chalta hai
    #
    # Mapping samjho:
    #   await reader.read()  → loop selector me socket EVENT_READ register karta hai,
    #                          coroutine SUSPEND (yield) ho jaata hai
    #   data aaya            → selector event → callback → coroutine RESUME
    #   "concurrency"        → bas ready coroutines ko baari-baari ek step chalana
    #
    # Isliye: asyncio me CPU-bound code loop ko FREEZE kar deta hai — kyunki
    # loop tab tak sel.select() pe wapas hi nahi pahunchta. Single thread hai!
    #
    # Platform note: Unix pe SelectorEventLoop default; Windows pe 3.8+ se
    # ProactorEventLoop (IOCP, completion-based) default hai. uvloop = same
    # idea, libuv (C) me — isliye 2-4x fast.
    print("\n   asyncio = selectors + timers + coroutine scheduling. await = ")
    print("   'socket ready hone tak mujhe suspend karo, loop dusro ko chalaye'.")


# ============ SECTION 2: sched — stdlib event scheduler (BRIEF) ============
#
# sched.scheduler = "in-process, single-shot events ko time pe chalao".
#   s = sched.scheduler(timefunc=time.monotonic, delayfunc=time.sleep)
#   s.enter(delay, priority, action, argument=())   # ab-se-delay-baad
#   s.enterabs(abs_time, priority, action)          # absolute timestamp pe
#   s.run()                                         # BLOCKING — sab events chala ke lautega
# Same time pe 2 events? → priority chhota number pehle (1 beats 2).
# vs cron/Celery beat (ONE-LINER): sched in-process & process-mar-gaya-to-sab-gaya;
# cron/Celery beat OS/infra-level hain — persistent, distributed, retry-capable.
# sched sirf chhote scripts/simulations ke liye; production scheduling NAHI.

def demo_sched():
    print("\n" + "=" * 60)
    print("SECTION 2: sched — enter/enterabs/run")
    print("=" * 60)

    s = sched.scheduler(time.monotonic, time.sleep)
    t0 = time.monotonic()

    def fire(name):
        print(f"   +{time.monotonic() - t0:.2f}s → event {name!r} fired")

    s.enter(0.30, 1, fire, argument=('late',))            # 0.3s baad
    # TRAP: enter(0.10,...) do baar likho to times EXACTLY equal nahi hote
    # (enter call ke waqt now+delay compute hota hai, microseconds ka farak)
    # → priority tie tabhi dikhega jab enterabs se SAME absolute time do:
    s.enterabs(t0 + 0.10, 2, fire, argument=('early-prio2',))  # same time, prio 2
    s.enterabs(t0 + 0.10, 1, fire, argument=('early-prio1',))  # same time, prio 1 → PEHLE
    s.enterabs(t0 + 0.20, 1, fire, argument=('absolute',))     # absolute monotonic time pe

    print(f"   queue me {len(s.queue)} events, run() blocking hai...")
    s.run()    # sab events time-order (tie → priority-order) me chalenge
    # cancel karna ho to: ev = s.enter(...); s.cancel(ev)


# ============ SECTION 3: socketserver — server framework (BRIEF) ============
#
# Raw socket loop me tum khud likhte ho: bind/listen/accept/loop/close.
# socketserver wo boilerplate framework bana deta hai:
#   class Handler(socketserver.BaseRequestHandler):
#       def handle(self): ...           # PER-CONNECTION logic sirf yahan
#   socketserver.TCPServer((host, port), Handler).serve_forever()
# TCPServer = sequential (ek waqt me EK client — dusra wait karega!).
# ThreadingMixIn → har connection NAYA thread:
#   class TS(socketserver.ThreadingMixIn, socketserver.TCPServer): pass
#   (shortcut: socketserver.ThreadingTCPServer — yehi pre-mixed hai)
# FAMILY TREE: http.server.HTTPServer = socketserver.TCPServer ka subclass!
# (aur ForkingMixIn / UDPServer bhi hain). Thread-per-conn vs selectors:
# yeh wahi do model hain — socketserver = threads, asyncio = multiplexing.

class EchoHandler(socketserver.BaseRequestHandler):
    def handle(self):
        # self.request = client socket; har connection pe naya handler instance
        data = self.request.recv(1024)
        thread_name = threading.current_thread().name
        self.request.sendall(b'[echo via ' + thread_name.encode() + b'] ' + data)


def demo_socketserver():
    print("\n" + "=" * 60)
    print("SECTION 3: socketserver — ThreadingTCPServer echo")
    print("=" * 60)

    srv = socketserver.ThreadingTCPServer(('127.0.0.1', 0), EchoHandler)
    srv.daemon_threads = True       # handler threads program exit pe na atkayein
    port = srv.server_address[1]

    # serve_forever() blocking hai → background thread me chalao (demo ke liye)
    threading.Thread(target=srv.serve_forever, daemon=True).start()

    for i in range(2):
        with socket.create_connection(('127.0.0.1', port)) as c:
            c.sendall(f"ping-{i}".encode())
            print(f"   client-{i}: {c.recv(1024).decode()}")
            # Output me alag thread names dikhenge → ThreadingMixIn ka kaam

    srv.shutdown()        # serve_forever loop ko rukne bolo
    srv.server_close()    # listening socket release
    print("   → handle() likho, baaki (bind/accept/threading) framework ka kaam.")


# ============ SECTION 4: _thread — low-level awareness (BRIEF) ============
#
# _thread = CPython ka RAW thread primitive (pehle naam tha `thread`, Py3 me
# underscore laga = "mat use karo, internal hai"). threading module ISI ke
# UPAR bana hai (threading.Thread andar _thread.start_new_thread hi karta hai).
# Kab dikhega:
#   - LEGACY/ported Py2 code me: _thread.start_new_thread(func, args)
#   - threading module ke source me (stdlib internals padhte waqt)
#   - _thread.interrupt_main() → main thread me KeyboardInterrupt uthao
#     (watchdog/timeout patterns me — "x seconds me kaam nahi hua to main ko roko")
# Naya code HAMESHA threading use kare: join(), daemon, names, locals sab wahan.

def demo_low_level_thread():
    print("\n" + "=" * 60)
    print("SECTION 4: _thread — threading iske upar bana hai")
    print("=" * 60)

    # start_new_thread me join() NAHI hota → khud signal karna padta hai.
    # Classic pattern: lock le lo, thread khatam hone pe release kare.
    done = _thread.allocate_lock()    # threading.Lock bhi andar se YEHI hai
    done.acquire()

    def worker(msg):
        print(f"   _thread worker bola: {msg}")
        done.release()                # "main khatam" ka signal

    _thread.start_new_thread(worker, ("no join(), no Thread object, raw API",))
    done.acquire()                    # release hone tak block = jugaad-wala join()

    # interrupt_main(): background thread se MAIN thread me KeyboardInterrupt
    def watchdog():
        time.sleep(0.1)
        _thread.interrupt_main()      # main thread me Ctrl+C jaisa effect

    _thread.start_new_thread(watchdog, ())
    try:
        time.sleep(2)                 # watchdog 0.1s me todega isko
    except KeyboardInterrupt:
        print("   interrupt_main() ne main thread me KeyboardInterrupt phenka!")
    print("   → naya code: threading. _thread sirf pehchanne ke liye.")


# ============ SECTION 5: queue priority — RECAP POINTER ============
#
# (Detail Day51_Concurrency_Senior me ho chuka hai; heapq Day53_Part2 me.)
# 10-second recap: queue.PriorityQueue = thread-safe queue jo SABSE CHHOTA
# item pehle deta hai (andar heapq hai). Pattern: (priority, payload) tuples —
# par equal priorities pe payload compare hoga (crash if uncomparable) →
# (priority, counter, payload) use karo ya dataclass(order=True) + field(compare=False).

def demo_queue_recap():
    print("\n" + "=" * 60)
    print("SECTION 5: queue.PriorityQueue — 10-second recap")
    print("=" * 60)
    import queue
    pq = queue.PriorityQueue()
    for prio, task in [(3, 'cleanup'), (1, 'pager-alert'), (2, 'email')]:
        pq.put((prio, task))
    out = [pq.get()[1] for _ in range(3)]
    print(f"   nikla order: {out}  (lowest number = highest priority)")
    print("   → full detail: Day51_Concurrency_Senior (queue), Day53_Part2 (heapq)")


# ============ INTERVIEW QUESTIONS ============
"""
Q1: asyncio andar se kaise kaam karta hai? (THE question)
A : Core me ek event loop hai jo `selectors` module use karta hai. Loop har
    iteration me sel.select(timeout) call karta hai — OS batata hai kaunse
    sockets ready hain. Ready fds ke callbacks chalte hain, jo suspended
    coroutines ko resume karte hain (coroutine.send()). `await socket-op` ka
    matlab: "fd ko selector me register karo, mujhe suspend karo"; data aane
    par loop coroutine ko agle await tak chalata hai. Single thread + OS-level
    readiness notification = hazaaron concurrent connections.

Q2: select vs poll vs epoll — difference aur kaun kab?
A : select/poll dono O(n): har call pe kernel PURI fd list scan karta hai
    (select me upar se ~1024 fd limit). epoll (Linux) / kqueue (BSD/macOS)
    me interest-list kernel me EK BAAR register hoti hai aur kernel sirf
    READY fds push karta hai → O(1)-ish per call. 10k idle + 10 active conn:
    select 10k checks karega, epoll sirf 10 events dega. Isliye nginx, Redis,
    uvloop sab epoll/kqueue pe hain. selectors.DefaultSelector OS ka best
    automatically chunta hai.

Q3: selectors loop me sockets non-blocking kyun karne padte hain?
A : select() sirf "READY hai" batata hai — guarantee phir bhi race ho sakti
    hai (spurious wakeup, ya tumne ready se ZYADA read kar liya). Blocking
    socket pe ek galat recv() PURA loop freeze kar dega — aur single thread
    hai, baaki saare clients bhi atak gaye. Non-blocking + ready-check =
    worst case BlockingIOError milta hai, hang nahi.

Q4: asyncio app me ek CPU-heavy function call kiya — baaki requests kyon
    hang ho gayin?
A : Event loop single thread hai. Loop tabhi naye events process karta hai
    jab control wapas sel.select() tak pahunche. CPU-bound code me koi await
    nahi → coroutine yield hi nahi karta → loop block. Fix: loop.
    run_in_executor() (thread/process pool) ya ProcessPoolExecutor me bhejo.

Q5: recv() ne b'' (empty bytes) diya — iska matlab kya hai selector loop me?
A : Peer ne connection close kar diya (EOF). Ye "no data yet" NAHI hai —
    no-data-yet pe non-blocking socket BlockingIOError deta, aur select to
    use ready batata hi nahi. b'' pe: sel.unregister(conn) PEHLE, conn.close()
    BAAD me — warna closed fd selector me reh jaata hai (ValueError/leak).

Q6: sched module production scheduling ke liye kyon nahi?
A : In-process hai — process restart hua to saare pending events GAYAB (koi
    persistence nahi), single machine, no retries, run() blocking. Cron =
    OS-level persistent; Celery beat = distributed + retries + monitoring.
    sched sirf scripts/simulations/test-harness ke liye theek hai.

Q7: socketserver.TCPServer aur ThreadingTCPServer me kya farak? http.server
    ka relation?
A : TCPServer SEQUENTIAL hai — handle() khatam hone tak agla accept nahi
    (dusra client wait karega). ThreadingMixIn har connection ke liye naya
    thread spawn karta hai → ThreadingTCPServer = ThreadingMixIn + TCPServer.
    http.server.HTTPServer TCPServer ka hi subclass hai — isliye stdlib ka
    dev-server bhi yehi accept-loop use karta hai (aur isliye production-grade
    nahi — gunicorn/uvicorn lao).

Q8: _thread aur threading ka relation? interrupt_main() kab kaam aata hai?
A : _thread C-level raw primitive hai (start_new_thread, allocate_lock);
    threading USKE UPAR ka high-level API (Thread objects, join, daemon).
    Naye code me hamesha threading. _thread legacy Py2-ported code me dikhega.
    interrupt_main() background thread se main thread me KeyboardInterrupt
    uthata hai — watchdog/timeout pattern ("X sec me kaam nahi to abort").

Q9: PriorityQueue me (priority, obj) tuples daale, kabhi-kabhi TypeError
    aata hai — kyun?
A : Equal priority pe tuple comparison agle element (obj) pe chala jaata hai;
    agar obj comparable nahi (e.g. dict) to TypeError. Fix: (priority,
    monotonic_counter, obj) — counter tie tod deta hai, obj compare hi nahi
    hota. Ya dataclass(order=True) me payload ko field(compare=False) karo.
"""


if __name__ == '__main__':
    demo_selectors_deep()
    demo_sched()
    demo_socketserver()
    demo_low_level_thread()
    demo_queue_recap()
