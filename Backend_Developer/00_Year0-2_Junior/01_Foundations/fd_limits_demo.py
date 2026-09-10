"""
File Descriptors + Resource Limits (ulimit) -- verified practical demo.
"""

import os
import resource
import socket


def demo_fd_growth():
    print("=== Proof 1: opening files/sockets grows the FD table, one integer at a time ===")
    fds = []
    print(f"  fd 0/1/2 are always stdin/stdout/stderr (reserved)")
    for i in range(5):
        f = open(f"/tmp/fd_demo_{i}.txt", "w")
        fds.append(f)
        print(f"  opened file {i}: fd number = {f.fileno()}")
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    fds.append(s)
    print(f"  opened a socket: fd number = {s.fileno()}  <- SAME fd space as files")
    print("  (this is exactly Part 6's point: sockets/pipes/files are ALL just")
    print("   integers in the same per-process table -- 'everything is a file')\n")
    for f in fds:
        f.close()
    for f in fds[:5]:
        os.remove(f.name)


def demo_ulimit_and_exhaustion():
    print("=== Proof 2: lower the FD limit ourselves, then actually hit it ===")
    soft, hard = resource.getrlimit(resource.RLIMIT_NOFILE)
    print(f"  Current limit: soft={soft}, hard={hard}")

    new_soft = 50
    resource.setrlimit(resource.RLIMIT_NOFILE, (new_soft, hard))
    print(f"  Lowered soft limit to {new_soft} (like `ulimit -n 50`)")

    opened = []
    error = None
    try:
        for i in range(200):
            opened.append(open(f"/tmp/fd_exhaust_{i}.txt", "w"))
    except OSError as e:
        error = e

    print(f"  Managed to open {len(opened)} files before hitting the limit")
    print(f"  Error raised: {error}")
    print("  (this is the EXACT real-world 'Too many open files' production")
    print("   error -- reproduced deliberately, not waiting for it in prod)\n")

    for f in opened:
        f.close()
        os.remove(f.name)
    resource.setrlimit(resource.RLIMIT_NOFILE, (soft, hard))  # restore


if __name__ == "__main__":
    demo_fd_growth()
    demo_ulimit_and_exhaustion()
