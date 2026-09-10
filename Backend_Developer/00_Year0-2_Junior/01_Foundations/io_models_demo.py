"""
I/O Models + Syscalls -- verified practical demo.
Blocking I/O, non-blocking I/O (EAGAIN), and multiplexing (select --
Python's select() uses epoll/kqueue/select under the hood depending on
platform; on macOS it's backed by kqueue).
"""

import errno
import os
import select
import socket
import time


def demo_blocking():
    print("=== Proof 1: Blocking I/O -- read() waits until data exists ===")
    r, w = socket.socketpair()
    r.settimeout(None)

    def writer_after_delay():
        time.sleep(0.3)
        w.send(b"data ready")

    import threading
    t = threading.Thread(target=writer_after_delay)
    t.start()

    start = time.perf_counter()
    data = r.recv(100)   # BLOCKS here until the writer sends something
    elapsed = time.perf_counter() - start
    t.join()
    print(f"  recv() blocked for {elapsed:.2f}s until data arrived: {data!r}")
    print("  (thread did nothing else during that wait -- classic blocking I/O)\n")
    r.close(); w.close()


def demo_non_blocking():
    print("=== Proof 2: Non-blocking I/O -- returns immediately with EAGAIN if not ready ===")
    r, w = socket.socketpair()
    r.setblocking(False)  # non-blocking mode

    try:
        r.recv(100)
    except BlockingIOError as e:
        print(f"  recv() on empty non-blocking socket raised immediately: {e}")
        print(f"  errno = {e.errno} ({errno.errorcode[e.errno]})")

    w.send(b"now there is data")
    time.sleep(0.05)
    data = r.recv(100)
    print(f"  after writer sent data, recv() succeeded: {data!r}")
    print("  (non-blocking I/O means YOU must poll/retry -- wastes CPU if done naively)\n")
    r.close(); w.close()


def demo_multiplexing():
    print("=== Proof 3: I/O Multiplexing (select) -- one call watches MANY FDs ===")
    pairs = [socket.socketpair() for _ in range(5)]
    readers = [r for r, w in pairs]
    writers = [w for r, w in pairs]

    # Only fd index 2 will actually have data -- select() should tell us
    # exactly which one, without us polling each individually.
    writers[2].send(b"only this one is ready")

    start = time.perf_counter()
    ready, _, _ = select.select(readers, [], [], 1.0)
    elapsed = time.perf_counter() - start

    print(f"  Watching {len(readers)} sockets with ONE select() call")
    print(f"  select() returned in {elapsed:.4f}s, {len(ready)} socket(s) ready")
    ready_index = readers.index(ready[0])
    print(f"  Ready socket was index {ready_index} (the one we wrote to)")
    print("  (this is the exact primitive behind epoll/kqueue/asyncio -- 'which")
    print("   of these thousands of FDs is ready?' answered in ONE syscall,")
    print("   instead of checking each FD one at a time)\n")

    for r, w in pairs:
        r.close(); w.close()


def demo_syscall_layer():
    print("=== Bonus: high-level open() vs the raw syscall wrapper underneath ===")
    path = "/tmp/syscall_demo.txt"

    # os.open/os.read/os.write ARE the syscall wrappers -- no buffering,
    # no Python-level abstraction. Regular open() is built on top of these.
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC)
    os.write(fd, b"raw syscall write, no buffering")
    os.close(fd)

    fd = os.open(path, os.O_RDONLY)
    data = os.read(fd, 100)
    os.close(fd)

    print(f"  os.open()/os.write()/os.read()/os.close() -- direct syscall wrappers")
    print(f"  Read back: {data!r}")
    print("  Regular Python `open()` adds buffering, text encoding, iteration")
    print("  etc. ON TOP of these same underlying syscalls.\n")
    os.remove(path)


if __name__ == "__main__":
    demo_blocking()
    demo_non_blocking()
    demo_multiplexing()
    demo_syscall_layer()
