"""
Network / IP / Port / MAC / Loopback vs 0.0.0.0 / Ephemeral port -- verified practical.
Pure stdlib, no network access required (all sockets are local).
"""

import socket
import uuid


def get_outbound_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    finally:
        s.close()


def get_mac_address():
    mac = uuid.getnode()
    return ":".join(f"{(mac >> ele) & 0xff:02x}" for ele in range(40, -1, -8))


def demo_multiple_services():
    sockets = []
    for _ in range(3):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.bind(("127.0.0.1", 0))
        s.listen(1)
        sockets.append(s)
    print("Three 'services' bound on same IP, different ports:")
    for s in sockets:
        ip, port = s.getsockname()
        print(f"  {ip}:{port}")
    for s in sockets:
        s.close()


def demo_ephemeral_port():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind(("127.0.0.1", 0))
    server.listen(1)
    server_ip, server_port = server.getsockname()
    print(f"Server listening at {server_ip}:{server_port}")

    client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client.connect((server_ip, server_port))
    client_ip, client_port = client.getsockname()
    print(f"Client's OS-assigned ephemeral port: {client_ip}:{client_port}")

    conn, addr = server.accept()
    print(f"Server sees incoming connection from: {addr}")

    client.close()
    conn.close()
    server.close()


def demo_loopback_vs_0000():
    for host in ("127.0.0.1", "0.0.0.0"):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.bind((host, 0))
        s.listen(1)
        note = "ALL interfaces (any IP the machine has)" if host == "0.0.0.0" else "ONLY loopback (same machine)"
        print(f"Bound to {host}:{s.getsockname()[1]} -> listens on {note}")
        s.close()


if __name__ == "__main__":
    print("=== Network / IP ===")
    print("Hostname:", socket.gethostname())
    print("Outbound-facing local IP (what this machine would use to reach the internet):", get_outbound_ip())
    print()

    print("=== MAC Address ===")
    print("MAC:", get_mac_address())
    print()

    print("=== Port: multiple services, same IP ===")
    demo_multiple_services()
    print()

    print("=== Ephemeral Port ===")
    demo_ephemeral_port()
    print()

    print("=== Loopback (127.0.0.1) vs 0.0.0.0 ===")
    demo_loopback_vs_0000()
