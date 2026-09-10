"""
IPC (Inter-Process Communication) — verified practical demo.
Three real mechanisms, each between TWO SEPARATE PROCESSES (not threads --
processes do NOT share memory, so every one of these needs an explicit
kernel-provided channel).

macOS/spawn note: everything is wrapped in main() and guarded by
`if __name__ == "__main__":` -- same lesson as the GIL practical file
(see 03_memory_gil_practical.py's commit history) -- spawn re-imports
this module in each child, so nothing with side effects can sit at
module level outside main() / the worker functions.
"""

import os
import signal
import time
import multiprocessing
from multiprocessing import shared_memory


# ─── Mechanism 1: Pipe (two-way, parent <-> child) ───

def pipe_child(conn):
    """Runs in a SEPARATE process -- has its own memory, must use the pipe."""
    msg = conn.recv()
    print(f"  [CHILD  pid={os.getpid()}] received via pipe: {msg!r}")
    conn.send(f"ack: got '{msg}'")
    conn.close()


def demo_pipe():
    print("=== Mechanism 1: Pipe (multiprocessing.Pipe) ===")
    parent_conn, child_conn = multiprocessing.Pipe()
    p = multiprocessing.Process(target=pipe_child, args=(child_conn,))
    p.start()

    parent_conn.send("hello from parent")
    reply = parent_conn.recv()
    print(f"  [PARENT pid={os.getpid()}] received reply: {reply!r}")

    p.join()
    print(f"  child exit code: {p.exitcode}\n")


# ─── Mechanism 2: Shared Memory (real shared bytes, kernel-backed) ───

def shm_child(shm_name):
    """Attaches to the SAME physical memory block by name -- not a copy."""
    existing = shared_memory.SharedMemory(name=shm_name)
    existing.buf[0:5] = b"CHILD"
    print(f"  [CHILD  pid={os.getpid()}] wrote b'CHILD' into shared block")
    existing.close()


def demo_shared_memory():
    print("=== Mechanism 2: Shared Memory (multiprocessing.shared_memory) ===")
    shm = shared_memory.SharedMemory(create=True, size=10)
    shm.buf[0:6] = b"PARENT"
    print(f"  [PARENT pid={os.getpid()}] wrote b'PARENT', block name = {shm.name}")

    p = multiprocessing.Process(target=shm_child, args=(shm.name,))
    p.start()
    p.join()

    # Parent reads the SAME physical memory the child just wrote to --
    # no send()/recv() needed, no serialization -- fastest IPC there is.
    print(f"  [PARENT pid={os.getpid()}] block now reads: {bytes(shm.buf[0:5])!r}")
    print("  (parent's own write was OVERWRITTEN by the child -- proves it's")
    print("   the SAME memory, not a message/copy -- and also why shared")
    print("   memory needs YOUR OWN synchronization, the OS gives you none)\n")

    shm.close()
    shm.unlink()  # release the OS-level shared memory block


# ─── Mechanism 3: Signals (async notification, not data transfer) ───

received_signal = multiprocessing.Value("b", 0)  # shared flag, 1 byte


def signal_child(flag):
    def handle_usr1(signum, frame):
        flag.value = 1
        print(f"  [CHILD  pid={os.getpid()}] caught SIGUSR1, set flag=1")

    signal.signal(signal.SIGUSR1, handle_usr1)
    print(f"  [CHILD  pid={os.getpid()}] handler installed, waiting...")
    time.sleep(2)  # give the parent time to send the signal


def demo_signals():
    print("=== Mechanism 3: Signals (async notification, no data payload) ===")
    received_signal.value = 0
    p = multiprocessing.Process(target=signal_child, args=(received_signal,))
    p.start()
    time.sleep(0.5)  # let the child install its handler first

    print(f"  [PARENT pid={os.getpid()}] sending SIGUSR1 to child pid={p.pid}")
    os.kill(p.pid, signal.SIGUSR1)

    p.join()
    print(f"  [PARENT pid={os.getpid()}] child's flag after join: {received_signal.value}")
    print("  (signals carry NO data payload -- just a notification. That's")
    print("   why the child used a SEPARATE shared Value to report back what")
    print("   happened -- signals alone can't move a message, unlike a pipe)\n")


def main():
    demo_pipe()
    demo_shared_memory()
    demo_signals()


if __name__ == "__main__":
    main()
