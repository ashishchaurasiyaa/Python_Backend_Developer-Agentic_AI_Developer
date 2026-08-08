"""
Trivial health-checkable app for Lab 04 (deployment health gate).
`LAB_BROKEN_HEALTH=1` env var toggle karo to /health 500 dega — isse
"deliberately broken deploy" simulate karte hain.
"""
import json
import os
from http.server import BaseHTTPRequestHandler, HTTPServer

BROKEN = os.environ.get("LAB_BROKEN_HEALTH", "0") == "1"


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/health":
            if BROKEN:
                self.send_response(500)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"status": "unhealthy"}).encode())
            else:
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"status": "ok"}).encode())
            return
        self.send_response(404)
        self.end_headers()

    def log_message(self, format, *args):
        pass  # quiet


if __name__ == "__main__":
    print(f"health-app listening on 0.0.0.0:8000 (broken={BROKEN})")
    HTTPServer(("0.0.0.0", 8000), Handler).serve_forever()
