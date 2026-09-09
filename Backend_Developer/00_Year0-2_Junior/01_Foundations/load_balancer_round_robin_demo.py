"""
Load Balancer -- verified practical: real round-robin dispatch across real
backend HTTP servers, with a real health check skipping an unhealthy one.
"""

import itertools
import threading
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


def make_backend(name, healthy):
    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def do_GET(self):
            if self.path == "/health":
                status, body = (200, b"ok") if healthy else (500, b"unhealthy")
            else:
                status, body = 200, f"response from {name}".encode()
            self.send_response(status)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format, *args):
            pass

    return Handler


def start_backend(name, healthy):
    server = ThreadingHTTPServer(("127.0.0.1", 0), make_backend(name, healthy))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


def health_check(host, port):
    try:
        resp = urllib.request.urlopen(f"http://{host}:{port}/health", timeout=1)
        return resp.status == 200
    except Exception:
        return False


if __name__ == "__main__":
    backends = [
        ("Backend-1", start_backend("Backend-1", healthy=True)),
        ("Backend-2", start_backend("Backend-2", healthy=False)),
        ("Backend-3", start_backend("Backend-3", healthy=True)),
    ]

    for name, srv in backends:
        print(f"{name} listening on {srv.server_address}")
    print()

    print("=== Health checks (GET /health on each backend) ===")
    healthy_backends = []
    for name, srv in backends:
        host, port = srv.server_address
        ok = health_check(host, port)
        print(f"  {name} ({host}:{port}) -> {'HEALTHY' if ok else 'UNHEALTHY, removed from rotation'}")
        if ok:
            healthy_backends.append((name, host, port))

    print(f"\n=== Round-robin dispatch of 6 requests across {len(healthy_backends)} healthy backends ===")
    pool = itertools.cycle(healthy_backends)
    for i in range(6):
        name, host, port = next(pool)
        resp = urllib.request.urlopen(f"http://{host}:{port}/")
        print(f"  Request {i + 1} -> {name}: {resp.read().decode()}")

    for _, srv in backends:
        srv.shutdown()
