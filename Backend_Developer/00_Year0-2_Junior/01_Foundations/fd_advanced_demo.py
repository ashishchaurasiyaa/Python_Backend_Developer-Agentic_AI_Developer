"""
File Descriptors -- Part 6 advanced proofs (fileno, process-scoping,
fork+FD sharing, accept() giving a NEW fd). Builds on fd_limits_demo.py.
"""

import os
import socket
import subprocess
import sys


def demo_fileno():
    print("=== Proof 1: fileno() -- Python object vs the kernel's integer handle ===")
    f = open("/tmp/fileno_demo.txt", "w")
    print(f"  Python object: {f!r}")
    print(f"  f.fileno() = {f.fileno()}  <- this integer is what the KERNEL knows")
    f.close()
    os.remove("/tmp/fileno_demo.txt")
    print()


def demo_fd_not_globally_unique():
    print("=== Proof 2: the SAME fd number in two DIFFERENT processes means DIFFERENT things ===")
    code = (
        "import os\n"
        "f = open('/tmp/fd_scope_demo.txt', 'w')\n"
        "print(f'pid={os.getpid()} fd={f.fileno()} file=fd_scope_demo.txt')\n"
    )
    r1 = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    r2 = subprocess.run(
        [sys.executable, "-c", code.replace("fd_scope_demo.txt", "fd_scope_demo2.txt")],
        capture_output=True, text=True,
    )
    print(f"  Process 1: {r1.stdout.strip()}")
    print(f"  Process 2: {r2.stdout.strip()}")
    print("  (both unrelated processes got the SAME fd number for DIFFERENT files --")
    print("   fd numbers are only meaningful WITHIN a process's own fd table)\n")
    os.remove("/tmp/fd_scope_demo.txt")
    os.remove("/tmp/fd_scope_demo2.txt")


def demo_fork_fd_sharing():
    print("=== Proof 3: fork() + FDs -- offset is SHARED, unlike memory (which is COW-copied) ===")
    path = "/tmp/fork_fd_demo.txt"
    with open(path, "w") as f:
        f.write("0123456789ABCDEFGHIJ")  # 20 bytes, known content

    fd = os.open(path, os.O_RDONLY)
    pid = os.fork()

    if pid == 0:
        # CHILD: inherited the SAME fd number, pointing to the SAME
        # underlying "open file description" in the kernel -- including
        # its current read offset.
        chunk = os.read(fd, 5)
        print(f"  [CHILD]  read 5 bytes using inherited fd {fd}: {chunk!r}")
        # GOTCHA (found by actually running this): os._exit() does NOT
        # flush stdio buffers (unlike sys.exit() / normal interpreter
        # shutdown). Without this explicit flush, the [CHILD] print above
        # silently vanishes -- verified by first writing this demo WITHOUT
        # the flush and watching the line never appear. Real consequence:
        # worker processes that call os._exit() (common after fork(), to
        # skip parent cleanup code) can lose buffered log output for good.
        sys.stdout.flush()
        os.close(fd)
        os._exit(0)
    else:
        os.waitpid(pid, 0)
        # PARENT reads NEXT, using the SAME fd -- if offset were private
        # (like memory is, post-fork), we'd see the file from the start
        # again (bytes 0-4). Because the OFFSET is shared kernel state,
        # not per-process, we should see bytes 5-9 instead.
        chunk = os.read(fd, 5)
        print(f"  [PARENT] read 5 bytes AFTER child, same fd {fd}: {chunk!r}")
        print("  (parent got bytes 5-9, NOT bytes 0-4 -- proves the file offset is")
        print("   SHARED kernel state between parent and child after fork(), unlike")
        print("   process MEMORY, which fork() gives each its own private/COW copy of.")
        print("   This is a real, easy-to-miss distinction: 'fork copies memory' is")
        print("   true, but 'fork copies fd table entries that point at shared state'")
        print("   is a DIFFERENT and equally real fact about the same syscall.)\n")
        os.close(fd)
        os.remove(path)


def demo_accept_new_fd():
    print("=== Proof 4: accept() returns a NEW fd, separate from the listening socket's fd ===")
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.bind(("127.0.0.1", 0))
    listener.listen(1)
    port = listener.getsockname()[1]
    print(f"  Listening socket fd = {listener.fileno()} (bound to 127.0.0.1:{port})")

    client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client.connect(("127.0.0.1", port))

    server_side, addr = listener.accept()
    print(f"  accept() returned a NEW connected-socket fd = {server_side.fileno()}")
    print(f"  Listening fd ({listener.fileno()}) is STILL open, unaffected, ready for the next accept()")
    print("  (this is exactly '1 listening fd + N per-client fds' from the theory --")
    print("   verified with a real socket pair, not just diagrammed)\n")

    client.close(); server_side.close(); listener.close()


if __name__ == "__main__":
    demo_fileno()
    demo_fd_not_globally_unique()
    demo_fork_fd_sharing()
    demo_accept_new_fd()
