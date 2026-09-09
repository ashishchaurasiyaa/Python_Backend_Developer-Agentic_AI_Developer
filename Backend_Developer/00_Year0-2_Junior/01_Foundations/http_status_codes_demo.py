"""
HTTP Status Codes -- verified practical: a real server returning real
status codes per route, hit with a real HTTP client.
"""

import threading
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ROUTES = {
    "/ok": (200, b"OK"),
    "/created": (201, b'{"id": 1}'),
    "/no-content": (204, b""),
    "/not-modified": (304, b""),
    "/bad-request": (400, b'{"error": "bad request"}'),
    "/unauthorized": (401, b'{"error": "unauthorized"}'),
    "/forbidden": (403, b'{"error": "forbidden"}'),
    "/not-found": (404, b'{"error": "not found"}'),
    "/conflict": (409, b'{"error": "conflict"}'),
    "/unprocessable": (422, b'{"error": "validation failed"}'),
    "/rate-limited": (429, b'{"error": "too many requests"}'),
    "/server-error": (500, b'{"error": "internal error"}'),
}


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def do_GET(self):
        status, body = ROUTES.get(self.path, (404, b"unknown route"))
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        if self.path == "/rate-limited":
            self.send_header("Retry-After", "30")
        self.end_headers()
        if body:
            self.wfile.write(body)

    def log_message(self, format, *args):
        pass


if __name__ == "__main__":
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    port = server.server_address[1]
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()

    for path in ROUTES:
        url = f"http://127.0.0.1:{port}{path}"
        try:
            resp = urllib.request.urlopen(url, timeout=2)
            extra = f"  Retry-After: {resp.headers.get('Retry-After')}" if resp.headers.get("Retry-After") else ""
            print(f"{path:16s} -> {resp.status} {resp.reason}{extra}")
        except urllib.error.HTTPError as e:
            print(f"{path:16s} -> {e.code} {e.reason}  (raised as HTTPError, exactly like real clients see it)")

    server.shutdown()
