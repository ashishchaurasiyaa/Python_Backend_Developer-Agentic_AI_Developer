"""
uvloop — Practical Demos
========================
Install: pip install uvloop

Compares default asyncio vs uvloop performance.
"""
import asyncio
import time
import sys


# ============================================================
# DEMO 1: Check which loop is active
# ============================================================
def show_loop_info():
    print("=" * 60)
    print("DEMO 1: Active event loop info")
    print("=" * 60)

    try:
        import uvloop
        print(f"  uvloop version: {uvloop.__version__}")
    except ImportError:
        print("  ❌ uvloop not installed — pip install uvloop")
        return False

    async def show():
        loop = asyncio.get_running_loop()
        print(f"  Running loop class: {type(loop).__name__}")
        print(f"  Module           : {type(loop).__module__}")

    # Default asyncio
    print("\n  -- Default asyncio --")
    asyncio.run(show())

    # uvloop
    print("\n  -- With uvloop.install() --")
    uvloop.install()
    asyncio.run(show())
    return True


# ============================================================
# DEMO 2: Benchmark — create_task overhead
# ============================================================
async def task_creation_workload(n=100_000):
    async def noop():
        return 1

    tasks = [asyncio.create_task(noop()) for _ in range(n)]
    await asyncio.gather(*tasks)


def demo_task_creation_benchmark():
    print("\n" + "=" * 60)
    print("DEMO 2: Task creation/scheduling benchmark (100k tasks)")
    print("=" * 60)

    # Reset to default asyncio
    asyncio.set_event_loop_policy(asyncio.DefaultEventLoopPolicy())
    start = time.perf_counter()
    asyncio.run(task_creation_workload())
    default_time = time.perf_counter() - start
    print(f"  Default asyncio: {default_time:.3f}s")

    # Switch to uvloop
    try:
        import uvloop
        asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
        start = time.perf_counter()
        asyncio.run(task_creation_workload())
        uvloop_time = time.perf_counter() - start
        print(f"  uvloop         : {uvloop_time:.3f}s")
        print(f"  Speedup        : {default_time/uvloop_time:.2f}x")
    except ImportError:
        print("  uvloop not available")


# ============================================================
# DEMO 3: Sleep(0) — pure scheduling benchmark
# ============================================================
async def sleep_workload(n=50_000):
    await asyncio.gather(*[asyncio.sleep(0) for _ in range(n)])


def demo_sleep_benchmark():
    print("\n" + "=" * 60)
    print("DEMO 3: 50k sleep(0) — pure event loop overhead")
    print("=" * 60)

    asyncio.set_event_loop_policy(asyncio.DefaultEventLoopPolicy())
    start = time.perf_counter()
    asyncio.run(sleep_workload())
    default_t = time.perf_counter() - start
    print(f"  Default: {default_t:.3f}s")

    try:
        import uvloop
        asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
        start = time.perf_counter()
        asyncio.run(sleep_workload())
        uvloop_t = time.perf_counter() - start
        print(f"  uvloop : {uvloop_t:.3f}s")
        print(f"  Speedup: {default_t/uvloop_t:.2f}x")
    except ImportError:
        pass


# ============================================================
# DEMO 4: TCP echo server benchmark (lightweight)
# ============================================================
async def echo_server(host, port, stop_event):
    async def handle(reader, writer):
        data = await reader.read(1024)
        writer.write(data)
        await writer.drain()
        writer.close()

    server = await asyncio.start_server(handle, host, port)
    try:
        await stop_event.wait()
    finally:
        server.close()
        await server.wait_closed()


async def echo_client(host, port, n_requests):
    sent = 0
    for _ in range(n_requests):
        reader, writer = await asyncio.open_connection(host, port)
        writer.write(b"hello")
        await writer.drain()
        await reader.read(1024)
        writer.close()
        await writer.wait_closed()
        sent += 1
    return sent


async def run_echo_benchmark(n=500):
    stop = asyncio.Event()
    server_task = asyncio.create_task(echo_server("127.0.0.1", 8765, stop))
    await asyncio.sleep(0.05)  # let server start

    start = time.perf_counter()
    await echo_client("127.0.0.1", 8765, n)
    elapsed = time.perf_counter() - start

    stop.set()
    await server_task
    return elapsed


def demo_echo_benchmark():
    print("\n" + "=" * 60)
    print("DEMO 4: TCP echo benchmark (500 sequential requests)")
    print("=" * 60)

    asyncio.set_event_loop_policy(asyncio.DefaultEventLoopPolicy())
    default_t = asyncio.run(run_echo_benchmark(500))
    print(f"  Default: {default_t:.3f}s ({500/default_t:.0f} req/sec)")

    try:
        import uvloop
        asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
        uvloop_t = asyncio.run(run_echo_benchmark(500))
        print(f"  uvloop : {uvloop_t:.3f}s ({500/uvloop_t:.0f} req/sec)")
        print(f"  Speedup: {default_t/uvloop_t:.2f}x")
    except ImportError:
        pass


# ============================================================
# DEMO 5: API compatibility check
# ============================================================
async def compat_test():
    """Verify common asyncio APIs work identically with uvloop."""
    # Queue
    q = asyncio.Queue(maxsize=5)
    await q.put(1)
    item = await q.get()
    assert item == 1

    # Lock
    lock = asyncio.Lock()
    async with lock:
        pass

    # Semaphore
    sem = asyncio.Semaphore(2)
    async with sem:
        pass

    # Event
    e = asyncio.Event()
    e.set()
    assert e.is_set()

    # gather + wait
    results = await asyncio.gather(asyncio.sleep(0, result=i) for i in range(3))

    # wait_for
    await asyncio.wait_for(asyncio.sleep(0.01), timeout=1)

    # subprocess (may not work on all platforms with uvloop)
    proc = await asyncio.create_subprocess_shell("echo hi", stdout=asyncio.subprocess.PIPE)
    stdout, _ = await proc.communicate()

    return "ALL_OK"


def demo_compatibility():
    print("\n" + "=" * 60)
    print("DEMO 5: API compatibility")
    print("=" * 60)

    asyncio.set_event_loop_policy(asyncio.DefaultEventLoopPolicy())
    print(f"  Default asyncio: {asyncio.run(compat_test())}")

    try:
        import uvloop
        asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
        print(f"  uvloop         : {asyncio.run(compat_test())}")
        print("  ✅ All common asyncio APIs compatible")
    except ImportError:
        pass


# ============================================================
# DEMO 6: FastAPI production command reference
# ============================================================
def demo_production_command():
    print("\n" + "=" * 60)
    print("DEMO 6: Production FastAPI launch")
    print("=" * 60)
    print("""
  # Install
  pip install fastapi uvicorn[standard] uvloop httptools

  # Run
  uvicorn app:app \\
      --host 0.0.0.0 \\
      --port 8000 \\
      --workers 4 \\
      --loop uvloop \\
      --http httptools \\
      --proxy-headers \\
      --access-log

  # Behind nginx/traefik for TLS termination
  # Behind gunicorn (if needed):
  gunicorn app:app \\
      -w 4 \\
      -k uvicorn.workers.UvicornWorker \\
      --bind 0.0.0.0:8000
    """)


# ============================================================
# DEMO 7: Verify uvloop is being used in running app
# ============================================================
async def assert_uvloop():
    loop = asyncio.get_running_loop()
    is_uvloop = "uvloop" in type(loop).__module__
    print(f"  Current loop: {type(loop).__name__}")
    print(f"  Is uvloop  : {is_uvloop} {'✅' if is_uvloop else '❌'}")


def demo_runtime_check():
    print("\n" + "=" * 60)
    print("DEMO 7: Runtime check — am I using uvloop?")
    print("=" * 60)

    asyncio.set_event_loop_policy(asyncio.DefaultEventLoopPolicy())
    print("  -- Without uvloop --")
    asyncio.run(assert_uvloop())

    try:
        import uvloop
        asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
        print("  -- With uvloop --")
        asyncio.run(assert_uvloop())
    except ImportError:
        pass


# ============================================================
# MAIN
# ============================================================
if __name__ == "__main__":
    if not show_loop_info():
        sys.exit(0)

    demo_task_creation_benchmark()
    demo_sleep_benchmark()
    demo_echo_benchmark()
    demo_compatibility()
    demo_runtime_check()
    demo_production_command()

    print("\n" + "=" * 60)
    print("KEY TAKEAWAYS")
    print("=" * 60)
    print("1. uvloop = 2-4x faster than default asyncio (Linux/macOS)")
    print("2. Drop-in replacement: uvloop.install() one line")
    print("3. FastAPI: uvicorn --loop uvloop --http httptools")
    print("4. Don't use on Windows (use winloop or default)")
    print("5. Best gains for I/O-heavy, high-concurrency workloads")
    print("6. CPU-bound work — uvloop doesn't help (GIL is bottleneck)")
