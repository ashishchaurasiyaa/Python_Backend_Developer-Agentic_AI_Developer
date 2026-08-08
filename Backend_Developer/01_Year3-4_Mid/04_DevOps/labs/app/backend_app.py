"""
Trivial backend for Lab 02 (nginx reverse proxy).
Har request pe apna hostname (= container ID) aur jo bhi X-Forwarded-For
header mila, dono JSON me wapas bhejta hai — isse Lab 02 prove kar sakta hai
ki response NGINX se nahi, is BACKEND se aaya, aur header sahi forward hua.
"""
import json
import socket
from http.server import BaseHTTPRequestHandler, HTTPServer


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        body = {
            "source": "backend",
            "hostname": socket.gethostname(),
            "forwarded_for": self.headers.get("X-Forwarded-For", ""),
            "path": self.path,
        }
        payload = json.dumps(body).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, format, *args):
        pass  # quiet


if __name__ == "__main__":
    print("backend listening on 0.0.0.0:8000")
    HTTPServer(("0.0.0.0", 8000), Handler).serve_forever()
