"""
Reverse Proxy + X-Forwarded-For/Proto -- verified practical: a real
minimal reverse proxy that receives a client request, injects forwarded
headers, and relays it to a backend -- the backend never sees the client
directly, only the proxy.
"""

import http.client
import socket
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class BackendHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def do_GET(self):
        print(f"  [BACKEND] connection peer (proxy's IP, not real client): {self.client_address}")
        print(f"  [BACKEND] X-Forwarded-For header: {self.headers.get('X-Forwarded-For')}")
        print(f"  [BACKEND] X-Forwarded-Proto header: {self.headers.get('X-Forwarded-Proto')}")
        body = b"backend response"
        self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        pass


class ProxyHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    backend_host = None
    backend_port = None

    def do_GET(self):
        real_client_ip = self.client_address[0]
        print(f"[PROXY] real client connected from: {self.client_address}")

        conn = http.client.HTTPConnection(self.backend_host, self.backend_port)
        forwarded_headers = {
            "X-Forwarded-For": real_client_ip,
            "X-Forwarded-Proto": "http",
            "X-Forwarded-Host": self.headers.get("Host", ""),
        }
        print(f"[PROXY] injecting headers before forwarding: {forwarded_headers}")
        conn.request("GET", self.path, headers=forwarded_headers)
        resp = conn.getresponse()
        body = resp.read()
        conn.close()

        self.send_response(resp.status)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        pass


if __name__ == "__main__":
    backend = ThreadingHTTPServer(("127.0.0.1", 0), BackendHandler)
    backend_host, backend_port = backend.server_address
    threading.Thread(target=backend.serve_forever, daemon=True).start()
    print(f"Backend listening on {backend_host}:{backend_port} (never exposed to real client)\n")

    ProxyHandler.backend_host = backend_host
    ProxyHandler.backend_port = backend_port
    proxy = ThreadingHTTPServer(("127.0.0.1", 0), ProxyHandler)
    proxy_host, proxy_port = proxy.server_address
    threading.Thread(target=proxy.serve_forever, daemon=True).start()
    print(f"Reverse proxy listening on {proxy_host}:{proxy_port} (this is what the client hits)\n")

    print("=== Client sends request to the PROXY, not the backend ===")
    client = socket.create_connection((proxy_host, proxy_port), timeout=3)
    client.sendall(f"GET /orders HTTP/1.1\r\nHost: api.example.com\r\nConnection: close\r\n\r\n".encode())
    response = b""
    while True:
        chunk = client.recv(4096)
        if not chunk:
            break
        response += chunk
    client.close()
    print(f"\n[CLIENT] received: {response.splitlines()[0]}")

    backend.shutdown()
    proxy.shutdown()
