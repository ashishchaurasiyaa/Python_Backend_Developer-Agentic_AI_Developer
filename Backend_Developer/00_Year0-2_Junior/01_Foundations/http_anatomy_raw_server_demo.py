"""
HTTP Request anatomy -- verified practical: parse a REAL HTTP request
byte-by-byte with a raw socket server (no framework help).
"""

import socket
import threading
import urllib.request


def parse_http_request(raw):
    header_part, _, body = raw.partition(b"\r\n\r\n")
    lines = header_part.decode().split("\r\n")
    method, path, version = lines[0].split(" ")
    headers = {}
    for line in lines[1:]:
        if ": " in line:
            k, v = line.split(": ", 1)
            headers[k] = v
    return method, path, version, headers, body


def server(port_holder, ready_event):
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("127.0.0.1", 0))
    srv.listen(1)
    port_holder.append(srv.getsockname()[1])
    ready_event.set()

    conn, _ = srv.accept()
    conn.settimeout(2)
    raw = b""
    try:
        while b"\r\n\r\n" not in raw:
            raw += conn.recv(4096)
        header_part, _, rest = raw.partition(b"\r\n\r\n")
        content_length = 0
        for line in header_part.decode().split("\r\n")[1:]:
            if line.lower().startswith("content-length:"):
                content_length = int(line.split(":", 1)[1].strip())
        while len(rest) < content_length:
            rest += conn.recv(4096)
        raw = header_part + b"\r\n\r\n" + rest
    except socket.timeout:
        pass

    method, path, version, headers, body = parse_http_request(raw)
    print("=== Parsed by hand from raw bytes (no framework) ===")
    print(f"Method:  {method}")
    print(f"Path:    {path}")
    print(f"Version: {version}")
    print("Headers:")
    for k, v in headers.items():
        print(f"  {k}: {v}")
    print(f"Body:    {body!r}")

    response = b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\nConnection: close\r\n\r\nOK"
    conn.sendall(response)
    conn.close()
    srv.close()


if __name__ == "__main__":
    port_holder = []
    ready = threading.Event()
    t = threading.Thread(target=server, args=(port_holder, ready))
    t.start()
    ready.wait()
    port = port_holder[0]

    req = urllib.request.Request(
        f"http://127.0.0.1:{port}/api/users",
        data=b'{"name": "Ashish", "age": 25}',
        headers={"Content-Type": "application/json", "Authorization": "Bearer abc123"},
        method="POST",
    )
    try:
        urllib.request.urlopen(req, timeout=2)
    except Exception:
        pass
    t.join()
