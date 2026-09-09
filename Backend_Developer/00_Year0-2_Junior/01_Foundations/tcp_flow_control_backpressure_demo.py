"""
Flow Control -- verified practical: shrink the receiver's socket buffer and
show that a fast sender's send() genuinely BLOCKS because the receiver's
advertised window fills up -- real OS-level backpressure, not simulated.
"""

import socket
import threading
import time


def receiver_slow(sock, read_event, results):
    read_event.wait()
    total = 0
    while total < 5 * 1024 * 1024:
        chunk = sock.recv(4096)
        if not chunk:
            break
        total += len(chunk)
        time.sleep(0.001)
    results["received"] = total


if __name__ == "__main__":
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 4096)
    server.bind(("127.0.0.1", 0))
    server.listen(1)
    host, port = server.getsockname()

    client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client.connect((host, port))
    conn, _ = server.accept()

    actual_rcvbuf = conn.getsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF)
    print(f"Receiver's SO_RCVBUF requested: 4096 bytes | actual (OS-adjusted): {actual_rcvbuf} bytes")

    payload_size = 5 * 1024 * 1024
    payload = b"x" * payload_size

    read_event = threading.Event()
    results = {}
    receiver_thread = threading.Thread(target=receiver_slow, args=(conn, read_event, results), daemon=True)
    receiver_thread.start()

    print(f"\nSending {payload_size / (1024 * 1024):.0f} MB WITHOUT the receiver reading yet...")
    t0 = time.perf_counter()

    sender_thread = threading.Thread(target=lambda: client.sendall(payload))
    sender_thread.start()

    time.sleep(0.5)
    still_blocked = sender_thread.is_alive()
    print(f"After 0.5s, is sendall() still blocked? {still_blocked}")
    print("(True means the OS refused to accept more data into the send buffer because")
    print(" the receiver's advertised window (rwnd) filled up -- this IS flow control,")
    print(" not a simulation)")

    read_event.set()
    sender_thread.join()
    elapsed = time.perf_counter() - t0
    receiver_thread.join()

    print(f"\nTotal time until sendall() fully completed: {elapsed:.2f}s")
    print(f"Receiver eventually drained: {results['received'] / (1024 * 1024):.1f} MB")

    client.close()
    conn.close()
    server.close()
