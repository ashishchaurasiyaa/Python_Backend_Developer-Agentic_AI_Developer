"""
UDP -- verified practical: connectionless, datagram-based communication.
Compare with tcp_states_demo.py's 3-way handshake + persistent connection.
"""

import socket
import threading


def udp_server(sock, ready_event):
    ready_event.set()
    for _ in range(3):
        data, addr = sock.recvfrom(1024)
        print(f"  [server] received {data!r} from {addr}")
        sock.sendto(b"ack:" + data, addr)


def udp_client(host, port):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(2)
    for i in range(3):
        msg = f"packet-{i}".encode()
        sock.sendto(msg, (host, port))
        try:
            data, _ = sock.recvfrom(1024)
            print(f"  [client] server replied: {data!r}")
        except socket.timeout:
            print("  [client] no reply (timeout) -- UDP does not guarantee delivery")
    sock.close()


if __name__ == "__main__":
    server_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    server_sock.bind(("127.0.0.1", 0))
    host, port = server_sock.getsockname()
    print(f"=== UDP server bound at {host}:{port} (no listen(), no accept()) ===")

    ready = threading.Event()
    t = threading.Thread(target=udp_server, args=(server_sock, ready))
    t.start()
    ready.wait()

    print("=== Client sends datagrams -- no connect(), no handshake ===")
    udp_client(host, port)
    t.join()
    server_sock.close()
