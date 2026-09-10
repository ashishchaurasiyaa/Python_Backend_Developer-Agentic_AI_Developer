"""
Practical Debugging -- end-to-end verified proof.
Spawns a real "misbehaving" target process (holds memory, opens files/
sockets, burns some CPU), then runs the ACTUAL debugging commands this
file recommends against it, on macOS (substituting macOS equivalents
where the Linux-only tool doesn't exist), and shows real output.
"""

import os
import socket
import subprocess
import sys
import time

TARGET_SCRIPT = """
import socket
import time

# Hold some memory
data = bytearray(50 * 1024 * 1024)  # 50MB

# Open a few files
files = [open(f"/tmp/debug_target_{i}.txt", "w") for i in range(3)]

# Open a socket
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.bind(("127.0.0.1", 0))
s.listen(1)

# Burn a little CPU, then idle so the parent has time to inspect us
total = 0
for i in range(3_000_000):
    total += i * i

time.sleep(5)
"""


def main():
    path = "/tmp/debug_target.py"
    with open(path, "w") as f:
        f.write(TARGET_SCRIPT)

    proc = subprocess.Popen([sys.executable, path])
    pid = proc.pid
    time.sleep(1.0)  # let it allocate memory / open resources first

    print(f"=== Real target process spawned: PID {pid} ===\n")

    print("--- 'What is this process doing?' -- ps (macOS equivalent of `top -p`) ---")
    out = subprocess.check_output(
        ["ps", "-o", "pid,%cpu,%mem,vsz,rss,stat,command", "-p", str(pid)], text=True
    )
    print(out)

    print("--- Open files/sockets -- lsof -p $PID ---")
    try:
        out = subprocess.check_output(["lsof", "-p", str(pid)], text=True, stderr=subprocess.DEVNULL)
        lines = out.strip().splitlines()
        print(lines[0])
        for line in lines[1:]:
            if "REG" in line or "IPv4" in line or "TCP" in line:
                print(line)
    except subprocess.CalledProcessError as e:
        print(f"  lsof needs elevated perms in this sandbox: {e}")

    print("\n--- macOS equivalent of /proc/$PID/maps: vmmap (may need permission) ---")
    try:
        out = subprocess.run(
            ["vmmap", "--summary", str(pid)], capture_output=True, text=True, timeout=5
        )
        print(out.stdout[:500] if out.stdout else f"  (no output; stderr: {out.stderr[:200]})")
    except Exception as e:
        print(f"  vmmap unavailable/restricted: {e}")

    print("\n--- macOS equivalent of strace: dtruss (needs sudo -- already confirmed blocked earlier) ---")
    print("  Skipped deliberately -- see syscall_count_demo.py's honest note on this.")

    proc.wait()
    for i in range(3):
        p = f"/tmp/debug_target_{i}.txt"
        if os.path.exists(p):
            os.remove(p)
    os.remove(path)

    print(f"\n=== Target process {pid} finished naturally, cleaned up ===")


if __name__ == "__main__":
    main()
