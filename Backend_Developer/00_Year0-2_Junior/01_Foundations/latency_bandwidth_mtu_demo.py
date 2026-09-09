"""
Latency / Bandwidth / MTU -- verified practical.
Loopback numbers are NOT real-network numbers (no NIC, no real link) --
they only demonstrate the concept and the measurement technique.
"""

import platform
import socket
import subprocess
import threading
import time


def demo_latency_local():
    print("=== Latency (local loopback round-trip) ===")
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind(("127.0.0.1", 0))
    server.listen(1)
    host, port = server.getsockname()

    def echo_server():
        conn, _ = server.accept()
        while True:
            data = conn.recv(64)
            if not data:
                break
            conn.sendall(data)
        conn.close()

    t = threading.Thread(target=echo_server, daemon=True)
    t.start()

    client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client.connect((host, port))
    rtts = []
    for _ in range(5):
        t0 = time.perf_counter()
        client.sendall(b"ping")
        client.recv(64)
        rtts.append((time.perf_counter() - t0) * 1000)
    print(f"Loopback RTT samples (ms): {[round(r, 3) for r in rtts]}")
    print(f"Average: {sum(rtts) / len(rtts):.3f} ms")
    client.close()
    server.close()
    print()


def demo_bandwidth_local():
    print("=== Bandwidth (local loopback throughput) ===")
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind(("127.0.0.1", 0))
    server.listen(1)
    host, port = server.getsockname()

    payload_size = 10 * 1024 * 1024

    def receiver():
        conn, _ = server.accept()
        received = 0
        while received < payload_size:
            chunk = conn.recv(65536)
            if not chunk:
                break
            received += len(chunk)
        conn.close()

    t = threading.Thread(target=receiver, daemon=True)
    t.start()

    client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client.connect((host, port))
    payload = b"x" * payload_size
    t0 = time.perf_counter()
    client.sendall(payload)
    client.close()
    t.join()
    elapsed = time.perf_counter() - t0
    mbps = (payload_size * 8 / 1_000_000) / elapsed
    print(f"Sent {payload_size / (1024 * 1024):.0f} MB over loopback in {elapsed:.3f}s -> {mbps:.1f} Mbps")
    server.close()
    print()


def demo_mtu():
    print("=== MTU (real interfaces on this machine) ===")
    cmd = ["ifconfig"] if platform.system() == "Darwin" else ["ip", "link"]
    out = subprocess.run(cmd, capture_output=True, text=True, timeout=5).stdout
    for line in out.splitlines():
        if "mtu" in line.lower():
            print(" ", line.strip())
    print()


if __name__ == "__main__":
    demo_latency_local()
    demo_bandwidth_local()
    demo_mtu()
