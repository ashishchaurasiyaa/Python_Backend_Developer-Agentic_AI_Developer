"""
HTTP/2 -- verified practical: real ALPN negotiation and protocol upgrade
via curl. This machine's curl has nghttp2 built in (HTTP/2 works); HTTP/3
is NOT available here -- confirmed via `curl -V`, no http3 in the protocol
list, so that part of Part 5 cannot be demoed on this machine.
"""

import subprocess

HOST = "https://example.com"


def curl_status_line(extra_args, label):
    print(f"=== {label} ===")
    result = subprocess.run(
        ["curl", "-s", "-o", "/dev/null", "-D", "-", *extra_args, HOST],
        capture_output=True, text=True, timeout=10,
    )
    for line in result.stdout.splitlines()[:1]:
        print(" ", line)
    print()


if __name__ == "__main__":
    print("=== curl -V (confirms nghttp2 present -> HTTP/2 available; no http3 listed) ===")
    subprocess.run(["curl", "-V"])
    print()

    curl_status_line(["--http1.1"], "Forced HTTP/1.1")
    curl_status_line(["--http2"], "Negotiated HTTP/2 (via ALPN during TLS handshake)")

    print("=== Verbose ALPN negotiation (real TLS handshake extension, not asserted) ===")
    result = subprocess.run(
        ["curl", "-v", "--http2", "-o", "/dev/null", HOST],
        capture_output=True, text=True, timeout=10,
    )
    for line in result.stderr.splitlines():
        if "ALPN" in line or "using HTTP" in line or "Connected to" in line:
            print(" ", line.strip())
