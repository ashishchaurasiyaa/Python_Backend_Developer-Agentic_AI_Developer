"""
Trivial metrics-emitting app for Lab 03 (Prometheus scrape + query).
`/metrics` Prometheus text format me expose karta hai. Har GET request (jo
/metrics NAHI hai) ek Counter increment karti hai — Lab 03 isi Counter ko
directly HTTP se badhaata hai, phir Prometheus se query karke confirm karta
hai ki scrape pipeline ne wahi value uthayi.
"""
import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from prometheus_client import Counter, generate_latest, CONTENT_TYPE_LATEST

REQUESTS = Counter("lab_requests_total", "Total non-metrics requests handled by lab app")


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/metrics":
            payload = generate_latest()
            self.send_response(200)
            self.send_header("Content-Type", CONTENT_TYPE_LATEST)
            self.end_headers()
            self.wfile.write(payload)
            return

        REQUESTS.inc()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({"ok": True}).encode())

    def log_message(self, format, *args):
        pass  # quiet


if __name__ == "__main__":
    print("metrics-app listening on 0.0.0.0:8000")
    HTTPServer(("0.0.0.0", 8000), Handler).serve_forever()
