"""
File Descriptors -- verified practical: a Python socket IS an OS file
descriptor. Cross-checked with lsof (macOS has no /proc/<pid>/fd, so
lsof -p <pid> is the FD-listing tool used here instead).
"""

import os
import socket
import subprocess

if __name__ == "__main__":
    pid = os.getpid()
    print(f"This process PID: {pid}\n")

    sockets = []
    for _ in range(3):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.bind(("127.0.0.1", 0))
        sockets.append(s)
        print(f"Created socket bound to {s.getsockname()} -> Python-level FD number: {s.fileno()}")

    print("\n=== lsof -p <this PID> -- the real OS view of the same FDs ===")
    print("(macOS equivalent of Linux's ls /proc/<pid>/fd)")
    out = subprocess.run(["lsof", "-p", str(pid)], capture_output=True, text=True, timeout=5).stdout
    lines = out.splitlines()
    print(lines[0])
    for line in lines[1:]:
        if "TCP" in line:
            print(line)

    print("\nulimit -n (max FDs this shell/process is allowed):")
    subprocess.run(["bash", "-c", "ulimit -n"])

    for s in sockets:
        s.close()
