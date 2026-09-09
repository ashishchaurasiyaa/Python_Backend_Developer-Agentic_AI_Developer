"""
DNS / raw HTTP / TLS handshake -- verified practical. Needs internet access.
"""

import socket
import ssl
import time

HOST = "example.com"


def demo_dns():
    print("=== DNS resolution ===")
    t0 = time.perf_counter()
    ip = socket.gethostbyname(HOST)
    t1 = time.perf_counter()
    print(f"{HOST} -> {ip}  (resolved in {(t1 - t0) * 1000:.1f} ms)")
    infos = socket.getaddrinfo(HOST, 443)
    ips = sorted({info[4][0] for info in infos})
    print(f"All A/AAAA records seen via getaddrinfo: {ips}")
    print()


def demo_raw_http():
    print("=== Raw HTTP request over a socket (no requests/urllib) ===")
    with socket.create_connection((HOST, 80), timeout=5) as sock:
        request = f"GET / HTTP/1.1\r\nHost: {HOST}\r\nConnection: close\r\n\r\n"
        sock.sendall(request.encode())
        response = b""
        while True:
            chunk = sock.recv(4096)
            if not chunk:
                break
            response += chunk
    status_line = response.split(b"\r\n", 1)[0].decode()
    print("Status line:", status_line)
    print("Total bytes received:", len(response))
    print()


def demo_tls_handshake():
    print("=== TLS handshake (HTTPS) ===")
    ctx = ssl.create_default_context()
    t0 = time.perf_counter()
    with socket.create_connection((HOST, 443), timeout=5) as sock:
        with ctx.wrap_socket(sock, server_hostname=HOST) as tls_sock:
            t1 = time.perf_counter()
            print(f"TLS version negotiated: {tls_sock.version()}")
            print(f"Cipher: {tls_sock.cipher()}")
            cert = tls_sock.getpeercert()
            subject = dict(x[0] for x in cert["subject"])
            print(f"Certificate subject: {subject.get('commonName')}")
            print(f"TCP connect + TLS handshake took: {(t1 - t0) * 1000:.1f} ms")
    print()


if __name__ == "__main__":
    demo_dns()
    demo_raw_http()
    demo_tls_handshake()
