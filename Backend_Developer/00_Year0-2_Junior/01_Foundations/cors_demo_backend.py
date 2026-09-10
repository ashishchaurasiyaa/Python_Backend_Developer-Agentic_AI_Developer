"""
CORS demo backend -- verified practical: a real API server on one origin,
with a --with-cors flag to toggle Access-Control-Allow-Origin on/off,
to prove CORS is a BROWSER-enforced restriction, not a server-side one.
"""

import sys
from http.server import BaseHTTPRequestHandler, HTTPServer

WITH_CORS = "--with-cors" in sys.argv


class Handler(BaseHTTPRequestHandler):
    def _cors_headers(self):
        if WITH_CORS:
            self.send_header("Access-Control-Allow-Origin", "http://127.0.0.1:8092")
            self.send_header("Access-Control-Allow-Methods", "GET")

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors_headers()
        self.end_headers()

    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self._cors_headers()
        self.end_headers()
        self.wfile.write(b'{"message": "hello from API on port 8091"}')

    def log_message(self, fmt, *args):
        print(f"[BACKEND:8091] {fmt % args}")


if __name__ == "__main__":
    print(f"Backend API on http://127.0.0.1:8091  (CORS headers {'ENABLED' if WITH_CORS else 'DISABLED'})")
    HTTPServer(("127.0.0.1", 8091), Handler).serve_forever()
