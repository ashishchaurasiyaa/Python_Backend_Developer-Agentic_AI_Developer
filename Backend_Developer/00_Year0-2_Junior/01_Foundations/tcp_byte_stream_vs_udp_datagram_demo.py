"""
TCP byte-stream vs UDP datagram-oriented -- verified practical.
"""

import socket
import threading
import time


def tcp_demo():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind(("127.0.0.1", 0))
    server.listen(1)
    host, port = server.getsockname()

    def tcp_server():
        conn, _ = server.accept()
        conn.sendall(b"HELLO")
        conn.sendall(b"WORLD")
        time.sleep(0.3)
        conn.close()

    t = threading.Thread(target=tcp_server, daemon=True)
    t.start()

    client = socket.create_connection((host, port))
    time.sleep(0.15)
    data = client.recv(4096)
    print(f"TCP: ONE recv() call returned: {data!r}")
    print("'HELLO' and 'WORLD' were two separate send() calls but arrived as ONE blob --")
    print("TCP has no message boundaries, only an ordered byte stream.")
    client.close()
    server.close()
    t.join()


def udp_demo():
    server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    server.bind(("127.0.0.1", 0))
    host, port = server.getsockname()

    client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    client.sendto(b"HELLO", (host, port))
    client.sendto(b"WORLD", (host, port))

    data1, _ = server.recvfrom(4096)
    data2, _ = server.recvfrom(4096)
    print(f"\nUDP: TWO separate recvfrom() calls returned: {data1!r} and {data2!r}")
    print("Each sendto() maps to exactly one recvfrom() -- UDP preserves datagram boundaries.")
    client.close()
    server.close()


if __name__ == "__main__":
    tcp_demo()
    udp_demo()
