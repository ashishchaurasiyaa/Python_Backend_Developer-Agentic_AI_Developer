"""
OSI layers in a real request -- verified practical: time each phase of a
real HTTPS request and map it to the OSI layer responsible.
"""

import socket
import ssl
import time

HOST = "example.com"


if __name__ == "__main__":
    timings = {}

    t0 = time.perf_counter()
    ip = socket.gethostbyname(HOST)
    timings["DNS resolution (application-support, ~L7)"] = time.perf_counter() - t0

    t0 = time.perf_counter()
    sock = socket.create_connection((ip, 443), timeout=5)
    timings["TCP handshake (Transport, L4)"] = time.perf_counter() - t0

    t0 = time.perf_counter()
    ctx = ssl.create_default_context()
    tls_sock = ctx.wrap_socket(sock, server_hostname=HOST)
    timings["TLS handshake (Presentation, L6)"] = time.perf_counter() - t0

    t0 = time.perf_counter()
    request = f"GET / HTTP/1.1\r\nHost: {HOST}\r\nConnection: close\r\n\r\n"
    tls_sock.sendall(request.encode())
    response = b""
    while True:
        chunk = tls_sock.recv(4096)
        if not chunk:
            break
        response += chunk
    timings["HTTP request/response (Application, L7)"] = time.perf_counter() - t0

    tls_sock.close()

    print(f"Resolved {HOST} -> {ip}\n")
    print("=== Time spent per OSI-mapped phase ===")
    total = sum(timings.values())
    for label, dur in timings.items():
        print(f"  {label:45s} {dur * 1000:8.1f} ms")
    print(f"  {'TOTAL':45s} {total * 1000:8.1f} ms")

    status_line = response.split(b"\r\n", 1)[0].decode()
    print(f"\nStatus line: {status_line}")
