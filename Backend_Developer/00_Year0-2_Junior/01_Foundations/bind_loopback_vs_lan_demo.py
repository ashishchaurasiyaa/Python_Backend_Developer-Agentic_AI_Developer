"""
127.0.0.1 vs 0.0.0.0 bind -- verified practical: proven via REAL connect()
attempts using this machine's own LAN IP, not just getsockname().
"""

import socket


def get_lan_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    finally:
        s.close()


def try_connect(host, port):
    client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client.settimeout(2)
    try:
        client.connect((host, port))
        print(f"  Connecting via {host}:{port} -> SUCCESS")
        client.close()
    except (ConnectionRefusedError, socket.timeout, OSError) as e:
        print(f"  Connecting via {host}:{port} -> FAILED: {type(e).__name__}: {e}")


def demo(bind_host, lan_ip):
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((bind_host, 0))
    server.listen(1)
    port = server.getsockname()[1]
    print(f"Server bound to {bind_host}:{port}")

    try_connect(lan_ip, port)
    try_connect("127.0.0.1", port)
    server.close()


if __name__ == "__main__":
    lan_ip = get_lan_ip()
    print(f"This machine's LAN IP: {lan_ip}\n")

    print("=== Bound to 127.0.0.1 (loopback only) ===")
    demo("127.0.0.1", lan_ip)
    print()
    print("=== Bound to 0.0.0.0 (all interfaces) ===")
    demo("0.0.0.0", lan_ip)
