"""
HTTP/1.1 connection reuse -- verified practical: measure REAL latency
difference between a fresh TCP connection per request vs one reused
persistent connection.
"""

import http.client
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def do_GET(self):
        body = b"pong"
        self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        pass


if __name__ == "__main__":
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    host, port = server.server_address
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()

    N = 50

    t0 = time.perf_counter()
    for _ in range(N):
        conn = http.client.HTTPConnection(host, port)
        conn.request("GET", "/ping")
        conn.getresponse().read()
        conn.close()
    fresh_time = time.perf_counter() - t0

    t0 = time.perf_counter()
    conn = http.client.HTTPConnection(host, port)
    for _ in range(N):
        conn.request("GET", "/ping")
        conn.getresponse().read()
    conn.close()
    reused_time = time.perf_counter() - t0

    print(f"{N} requests, NEW TCP connection each time: {fresh_time * 1000:.1f} ms total ({fresh_time / N * 1000:.3f} ms/req)")
    print(f"{N} requests, ONE reused connection:         {reused_time * 1000:.1f} ms total ({reused_time / N * 1000:.3f} ms/req)")
    print(f"Speedup from reuse: {fresh_time / reused_time:.1f}x")

    server.shutdown()
