"""
Connection refused vs Connection timed out -- verified practical: two REAL
distinct socket errors, not simulated.
"""

import socket
import time


def try_connect(host, port, timeout, label):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(timeout)
    t0 = time.perf_counter()
    try:
        s.connect((host, port))
        print(f"{label}: connected (unexpected)")
    except ConnectionRefusedError as e:
        elapsed = time.perf_counter() - t0
        print(f"{label}: ConnectionRefusedError after {elapsed:.3f}s -- {e}")
    except socket.timeout:
        elapsed = time.perf_counter() - t0
        print(f"{label}: socket.timeout after {elapsed:.3f}s")
    except OSError as e:
        elapsed = time.perf_counter() - t0
        print(f"{label}: {type(e).__name__} after {elapsed:.3f}s -- {e}")
    finally:
        s.close()


if __name__ == "__main__":
    probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    probe.bind(("127.0.0.1", 0))
    closed_port = probe.getsockname()[1]
    probe.close()

    print("=== Connection REFUSED (real: nothing listening on this port) ===")
    try_connect("127.0.0.1", closed_port, timeout=3, label="localhost:closed-port")

    print("\n=== Connection TIMED OUT (real: a non-routable TEST-NET-style address) ===")
    try_connect("10.255.255.1", 81, timeout=3, label="10.255.255.1:81")
